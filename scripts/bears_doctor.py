#!/usr/bin/env python3
"""Run the unified @bears closeout validator."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PLUGIN_ROOT = Path("/srv/bears/plugins/bears")
CATALOG = PLUGIN_ROOT / "assets/catalog/bears-doctor.v1.json"
RESULT_SCHEMA = PLUGIN_ROOT / "assets/schemas/bears-doctor-result.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/bears_doctor/good/minimal-result.json"
BAD = PLUGIN_ROOT / "tests/fixtures/bears_doctor/bad/raw-data-result.json"
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")
DEFAULT_FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "raw log", "raw chat", "raw vpn config", "production data")
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import commit_closeout
from scripts import goal_orchestrator
from scripts import file_context_index
from scripts import issue_state_reconciler


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def forbidden_markers() -> tuple[str, ...]:
    try:
        markers = load(CATALOG).get("forbidden_output_markers", [])
    except Exception:
        markers = []
    return tuple(str(item) for item in markers) or DEFAULT_FORBIDDEN


def has_forbidden(value: Any) -> bool:
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in forbidden_markers())


def run(argv: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout, env=clean_env())
    except FileNotFoundError:
        return 127, "command not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return proc.returncode, "ok" if proc.returncode == 0 else "command failed"


def run_json(argv: list[str], *, timeout: int = 30) -> tuple[int, dict[str, Any] | None]:
    try:
        proc = subprocess.run(argv, cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout, env=clean_env())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, None
    try:
        packet = json.loads(proc.stdout)
    except Exception:
        packet = None
    return proc.returncode, packet if isinstance(packet, dict) else None


def git_output(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20, env=clean_env())
    except subprocess.TimeoutExpired:
        return 124, ""
    return proc.returncode, proc.stdout.strip()


def changed_files(range_spec: str) -> list[str]:
    code, output = git_output(["diff", "--name-only", range_spec])
    if code != 0:
        return []
    return sorted({line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()})


def target_commit(range_spec: str) -> str | None:
    ref = range_spec.split("..")[-1] if ".." in range_spec else range_spec
    code, output = git_output(["rev-parse", "--verify", ref])
    return output if code == 0 and output else None


def parent_range(commit_sha: str) -> str:
    code, output = git_output(["rev-list", "--parents", "-n", "1", commit_sha])
    if code != 0:
        return f"{EMPTY_TREE_SHA}..{commit_sha}"
    parts = output.split()
    return f"{parts[1] if len(parts) > 1 else EMPTY_TREE_SHA}..{commit_sha}"


def check_packet(check_id: str, status: str, required: bool, summary: str, *, exit_code: int | None = None, component_issue: str | None = None) -> dict[str, Any]:
    packet: dict[str, Any] = {"id": check_id, "status": status, "required": required, "summary": summary}
    if exit_code is not None:
        packet["exit_code"] = exit_code
    if component_issue:
        packet["component_issue"] = component_issue
    return packet


def validate_catalog() -> list[str]:
    errors: list[str] = []
    catalog = load(CATALOG)
    if catalog.get("schema") != "bears-doctor.v1":
        errors.append("catalog schema mismatch")
    for command in ("validate", "validate-closeout --from-git <range> --json", "closeout --fail-on-solved-open-issues", "validate-node --workflow-tree <path> --node-id <id> --json", "validate-goal --state <path> --json", "emit-summary --from-git <range> --json"):
        if command not in catalog.get("commands", []):
            errors.append(f"catalog missing command: {command}")
    if not RESULT_SCHEMA.exists():
        errors.append("result schema missing")
    for item in catalog.get("checks", []):
        if not item.get("id"):
            errors.append("catalog check missing id")
        for field in ("command", "range_command"):
            command = item.get(field)
            if isinstance(command, list) and command and command[0] == "python3" and len(command) > 1:
                if not (PLUGIN_ROOT / str(command[1])).exists():
                    errors.append(f"catalog check script missing: {item.get('id')} {command[1]}")
        for command in item.get("commands", []):
            if isinstance(command, list) and command and command[0] == "python3" and len(command) > 1:
                if not (PLUGIN_ROOT / str(command[1])).exists():
                    errors.append(f"catalog check script missing: {item.get('id')} {command[1]}")
    return errors


def validate_result_packet(packet: dict[str, Any], label: str) -> list[str]:
    errors = validate_json_schema(packet, RESULT_SCHEMA, label)
    if has_forbidden(packet):
        errors.append(f"{label}: forbidden raw data marker present")
    if packet.get("status") == "pass" and packet.get("failed_checks"):
        errors.append(f"{label}: pass result has failed_checks")
    if packet.get("status") == "pass" and packet.get("blockers"):
        errors.append(f"{label}: pass result has blockers")
    return errors


def validate_all() -> list[str]:
    errors = validate_catalog()
    good_errors = validate_result_packet(load(GOOD), GOOD.name)
    errors.extend(f"good fixture failed: {item}" for item in good_errors)
    if not validate_result_packet(load(BAD), BAD.name):
        errors.append("bad fixture unexpectedly passed")
    return errors


def command_check(item: dict[str, Any], range_spec: str) -> dict[str, Any]:
    required = bool(item.get("required"))
    issue = item.get("component_issue")
    if item.get("id") == "bears_goals_principles" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            summary = (
                f"active_goals={packet.get('active_goal_count', 'unknown')}; "
                f"active_principles={packet.get('active_principle_count', 'unknown')}; "
                f"missing_required={len(packet.get('missing_required_active_principles', []))}"
            )
        else:
            summary = "command failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "opencode_executor" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            summary = (
                f"available={packet.get('available', 'unknown')}; "
                f"policy_enabled={packet.get('policy_enabled', 'unknown')}; "
                f"profiles={packet.get('profile_count', 'unknown')}"
            )
        else:
            summary = "command failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "issue_autostart_observability" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            summary = f"ok: {packet.get('packet_path', 'runtime/issue-autostart/metrics/issue-autostart-metrics.v1.json')}; events: {packet.get('events_glob', 'runtime/issue-autostart/events/*.json')}"
        else:
            summary = "command failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "issue_autostart_ops" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            summary = f"service_state={packet.get('service_state', 'unknown')}; kill_switch={packet.get('kill_switch', {}).get('enabled', 'unknown')}; auto_install={packet.get('auto_install', 'unknown')}"
        else:
            summary = "command failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "roadmap_first_autostart" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            policy = packet.get("policy", {}) if isinstance(packet.get("policy"), dict) else {}
            source = packet.get("roadmap_source", {}) if isinstance(packet.get("roadmap_source"), dict) else {}
            decision = packet.get("decision_packet", {}) if isinstance(packet.get("decision_packet"), dict) else {}
            summary = (
                f"roadmap_first_workflow_status={packet.get('roadmap_first_workflow_status', 'unknown')}; "
                f"roadmap_source={source.get('status', 'unknown')}; "
                f"selected_node={packet.get('selected_node', {}).get('node_id', 'none') if isinstance(packet.get('selected_node'), dict) else 'none'}; "
                f"decision={decision.get('action', 'unknown')}; "
                f"fallback_default={policy.get('direct_issue_fallback_default', 'unknown')}; "
                f"no_leaf_action={policy.get('no_leaf_action', 'unknown')}"
            )
        else:
            summary = "roadmap-first autostart status failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "issue_release_gate" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            statuses: dict[str, int] = {}
            for row in packet.get("manifests", []):
                gate = row.get("release_gate", {}) if isinstance(row, dict) else {}
                state = str(gate.get("status", "missing"))
                statuses[state] = statuses.get(state, 0) + 1
            state_summary = ",".join(f"{key}={statuses[key]}" for key in sorted(statuses)) or "none"
            summary = f"delivery_id={packet.get('delivery_id', 'unknown')}; release_gate={state_summary}"
        else:
            summary = "command failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "external_review_audit" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            summary = f"external_review={packet.get('status', 'unknown')}; errors={len(packet.get('errors', []))}"
        else:
            summary = "external review audit failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "doctor_component_coverage" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            summary = (
                f"doctor_component_coverage_status={packet.get('doctor_component_coverage_status', 'unknown')}; "
                f"missing_doctor_check_count={packet.get('missing_doctor_check_count', 'unknown')}; "
                f"partial_doctor_coverage_count={packet.get('partial_doctor_coverage_count', 'unknown')}; "
                f"closed_issue_still_not_available_count={packet.get('closed_issue_still_not_available_count', 'unknown')}; "
                f"unsafe_autostart_without_doctor_gate_count={packet.get('unsafe_autostart_without_doctor_gate_count', 'unknown')}"
            )
        else:
            summary = "doctor component coverage failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)

    if item.get("id") == "file_context_index" and "range_command" in item:
        command = [str(part) for part in item["range_command"]] + [range_spec]
        code, packet = run_json(command)
        if code == 0 and packet:
            summary = (
                f"stale={len(packet.get('stale_records', []))}; "
                f"missing={len(packet.get('missing_context_paths', []))}; "
                f"orphaned={len(packet.get('orphaned_records', []))}"
            )
        else:
            summary = "file-context doctor failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if item.get("id") == "issue_repo_routing" and "command" in item:
        code, packet = run_json([str(part) for part in item["command"]])
        if code == 0 and packet:
            route = packet.get("route", {}) if isinstance(packet.get("route"), dict) else {}
            hook = packet.get("hook_proof", {}) if isinstance(packet.get("hook_proof"), dict) else {}
            counts: dict[str, int] = {}
            for row in packet.get("touched_repos", []):
                if isinstance(row, dict):
                    access = str(row.get("access", "unknown"))
                    counts[access] = counts.get(access, 0) + 1
            touched_summary = ",".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"
            summary = f"repo={packet.get('repo', 'unknown')}; worktree={route.get('worktree_path', 'unknown')}; hook_proof={hook.get('status', 'unknown')}; touched={touched_summary}"
        else:
            summary = "command failed"
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if "command" in item:
        code, summary = run([str(part) for part in item["command"]])
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if "range_command" in item:
        code, summary = run([str(part) for part in item["range_command"]] + [range_spec])
        return check_packet(item["id"], "pass" if code == 0 else "fail", required, summary, exit_code=code, component_issue=issue)
    if "commands" in item:
        exits = [run([str(part) for part in command])[0] for command in item["commands"]]
        status = "pass" if all(code == 0 for code in exits) else "fail"
        return check_packet(item["id"], status, required, "ok" if status == "pass" else "command failed", exit_code=max(exits) if exits else 0, component_issue=issue)
    return check_packet(item["id"], "not_available", required, "component not available yet", component_issue=issue)



def _resolve_worktree_value(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PLUGIN_ROOT / path
    return path.resolve()


def canonical_plugin_worktree_check() -> dict[str, Any]:
    expected = CANONICAL_PLUGIN_ROOT.resolve()
    actual_root = PLUGIN_ROOT.resolve()
    if actual_root != expected:
        return check_packet(
            "canonical_plugin_worktree",
            "fail",
            True,
            f"plugin closeout root mismatch: expected {expected}, got {actual_root}",
            component_issue="#402",
        )

    code, toplevel = git_output(["rev-parse", "--show-toplevel"])
    if code != 0 or not toplevel:
        return check_packet("canonical_plugin_worktree", "fail", True, "git toplevel unavailable", exit_code=code, component_issue="#402")
    if _resolve_worktree_value(toplevel) != expected:
        return check_packet(
            "canonical_plugin_worktree",
            "fail",
            True,
            f"git toplevel mismatch: expected {expected}, got {_resolve_worktree_value(toplevel)}",
            exit_code=code,
            component_issue="#402",
        )

    config_code, core_worktree = git_output(["config", "--get", "core.worktree"])
    if config_code == 0 and core_worktree and _resolve_worktree_value(core_worktree) != expected:
        return check_packet(
            "canonical_plugin_worktree",
            "fail",
            True,
            f"core.worktree mismatch: expected {expected}, got {_resolve_worktree_value(core_worktree)}",
            exit_code=config_code,
            component_issue="#402",
        )

    return check_packet("canonical_plugin_worktree", "pass", True, "canonical plugin checkout is active", component_issue="#402")

def local_proof_check(commit_sha: str | None) -> dict[str, Any]:
    if not commit_sha:
        return check_packet("local_commit_validation_proof", "fail", True, "target commit unavailable")
    path = PLUGIN_ROOT / "runtime/local-commit-validation" / f"{commit_sha}.json"
    if not path.exists():
        return check_packet("local_commit_validation_proof", "fail", True, "exact local commit proof missing")
    try:
        packet = load(path)
    except Exception:
        return check_packet("local_commit_validation_proof", "fail", True, "exact local commit proof unreadable")
    if packet.get("commit_sha") != commit_sha:
        return check_packet("local_commit_validation_proof", "fail", True, "stale local commit proof sha mismatch")
    if packet.get("status") != "pass":
        return check_packet("local_commit_validation_proof", "fail", True, "exact local commit proof is not pass")
    plan = packet.get("validation_plan")
    if not isinstance(plan, dict) or plan.get("status") != "pass":
        return check_packet("local_commit_validation_proof", "fail", True, "local commit validation plan missing or failed")
    if plan.get("uncovered_changed_files"):
        return check_packet("local_commit_validation_proof", "fail", True, "local commit validation plan has uncovered files")
    return check_packet("local_commit_validation_proof", "pass", True, "exact local commit proof passed")


def tracked_runtime_check() -> dict[str, Any]:
    code, output = git_output(["ls-files", "runtime", ".pytest_cache", ".ruff_cache"])
    if code != 0:
        return check_packet("tracked_runtime_files", "fail", True, "tracked runtime lookup failed")
    return check_packet("tracked_runtime_files", "pass" if not output else "fail", True, "no tracked runtime files" if not output else "tracked runtime files present")


def unresolved_blocker_check() -> dict[str, Any]:
    paths = [PLUGIN_ROOT / "runtime/validation-state", PLUGIN_ROOT / "runtime/validation-jobs"]
    blockers: list[str] = []
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            try:
                packet = load(path)
            except Exception:
                continue
            remediation = packet.get("remediation_packet")
            if packet.get("status") in {"fail", "timeout", "infra_fail", "selector_gap"} and remediation:
                blockers.append(path.relative_to(PLUGIN_ROOT).as_posix())
            if path.name == "remediation.v1.json" and packet.get("status") in {"open", "blocked"}:
                blockers.append(path.relative_to(PLUGIN_ROOT).as_posix())
            if len(blockers) >= 5:
                break
        if len(blockers) >= 5:
            break
    return check_packet("unresolved_blockers", "pass" if not blockers else "fail", True, "no unresolved blocker records" if not blockers else "blocking validation remediation records present")


def plugin_cache_check(commit_sha: str | None) -> dict[str, Any]:
    path = PLUGIN_ROOT / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"
    if not path.exists():
        return check_packet("plugin_cache_sync_state", "warning", False, "plugin cache sync state missing")
    packet = load(path)
    if commit_sha and packet.get("commit_sha") not in {commit_sha, None}:
        return check_packet("plugin_cache_sync_state", "warning", False, "plugin cache sync state is for a different commit")
    status = "pass" if packet.get("delivery_complete") is True else "warning"
    return check_packet("plugin_cache_sync_state", status, False, "plugin cache sync delivery complete" if status == "pass" else "plugin cache sync delivery not complete")


def closeout_result(range_spec: str) -> dict[str, Any]:
    files = changed_files(range_spec)
    commit_sha = target_commit(range_spec)
    checks: list[dict[str, Any]] = []
    for item in load(CATALOG).get("checks", []):
        check_id = item.get("id")
        if check_id == "local_commit_validation_proof":
            checks.append(local_proof_check(commit_sha))
        elif check_id == "canonical_plugin_worktree":
            checks.append(canonical_plugin_worktree_check())
        elif check_id == "tracked_runtime_files":
            checks.append(tracked_runtime_check())
        elif check_id == "unresolved_blockers":
            checks.append(unresolved_blocker_check())
        elif check_id == "plugin_cache_sync_state":
            checks.append(plugin_cache_check(commit_sha))
        elif check_id == "commit_closeout":
            checks.append(commit_closeout.check_commit_closeout(commit_sha, range_spec))
        else:
            checks.append(command_check(item, range_spec))
    failed = [item["id"] for item in checks if item["required"] and item["status"] not in {"pass", "not_available"}]
    blockers = [f"{item['id']}: {item['summary']}" for item in checks if item["required"] and item["status"] in {"fail", "blocked"}]
    warnings = [f"{item['id']}: {item['summary']}" for item in checks if item["status"] in {"warning", "not_available"}]
    next_actions = ["resolve blocking closeout checks and rerun bears_doctor validate-closeout"] if blockers else []
    status = "pass" if not failed and not blockers else "fail"
    closeout_summary = commit_closeout.closeout_summary(commit_sha, range_spec, doctor_result=status)
    release_gate_check = next((item for item in checks if item.get("id") == "issue_release_gate"), None)
    if release_gate_check:
        closeout_summary["release_gate"] = {
            "status": release_gate_check.get("status", "not_available"),
            "summary": release_gate_check.get("summary", "release gate check unavailable"),
            "delivery_id": closeout_summary.get("delivery_id", "<missing>"),
        }
    repo_routing_check = next((item for item in checks if item.get("id") == "issue_repo_routing"), None)
    if repo_routing_check:
        closeout_summary["repo_routing"] = {
            "status": repo_routing_check.get("status", "not_available"),
            "summary": repo_routing_check.get("summary", "repo routing check unavailable"),
        }
    packet = {
        "schema": "bears-doctor-result.v1",
        "version": "1",
        "status": status,
        "commit_range": range_spec,
        "changed_files": files,
        "checks": checks,
        "failed_checks": failed,
        "warnings": warnings,
        "blockers": blockers,
        "required_next_actions": next_actions,
        "sanitized_summary": "closeout checks passed" if not blockers else "closeout has blocking checks",
        "closeout_summary": closeout_summary,
    }
    if has_forbidden(packet):
        packet["status"] = "fail"
        packet["blockers"].append("doctor result contains forbidden raw data marker")
        packet["failed_checks"].append("forbidden_output")
        packet["required_next_actions"].append("remove forbidden raw data from closeout result")
        packet["sanitized_summary"] = "closeout result failed safety check"
    return packet


def summary_result(range_spec: str) -> dict[str, Any]:
    packet = closeout_result(range_spec)
    return {
        "schema": "bears-doctor-summary.v1",
        "status": packet["status"],
        "commit_range": packet["commit_range"],
        "changed_count": len(packet["changed_files"]),
        "failed_checks": packet["failed_checks"],
        "warning_count": len(packet["warnings"]),
        "blocker_count": len(packet["blockers"]),
        "sanitized_summary": packet["sanitized_summary"],
        "closeout_summary": packet["closeout_summary"],
    }


def closeout_gate_result(
    *,
    delivery_id: str,
    manifest_root: Path,
    issues_json: Path | None,
    fail_on_solved_open_issues: bool,
) -> dict[str, Any]:
    issue_data = load(issues_json) if issues_json else None
    packet = issue_state_reconciler.solved_open(delivery_id, manifest_root, issue_data)
    checks = [
        check_packet(
            "solved_open_issues",
            "pass" if packet.get("status") == "pass" else "fail",
            fail_on_solved_open_issues,
            f"covered={packet.get('counts', {}).get('covered', 0)}; solved_open={packet.get('counts', {}).get('solved_open', 0)}; missing_closeout_state={packet.get('counts', {}).get('missing_closeout_state', 0)}",
            component_issue="#404",
        )
    ]
    blockers = [] if packet.get("status") == "pass" or not fail_on_solved_open_issues else ["solved covered issues remain open"]
    return {
        "schema": "bears-doctor-closeout-gate.v1",
        "status": "pass" if not blockers else "fail",
        "delivery_id": delivery_id,
        "checks": checks,
        "blockers": blockers,
        "issue_reconciliation": packet,
        "sanitized_summary": "issue closeout reconciliation passed" if not blockers else "issue closeout reconciliation blocked",
    }


def validate_goal(state: Path) -> dict[str, Any]:
    goal_errors = goal_orchestrator.validate_goal_state(str(state))
    errors = list(goal_errors)
    context_packet = file_context_index.doctor_packet()
    if context_packet.get("status") != "pass":
        errors.extend(f"file-context: {item}" for item in context_packet.get("errors", []))
    status = "pass" if not errors else "fail"
    goal_status = "pass" if not goal_errors else "fail"
    context_status = "pass" if context_packet.get("status") == "pass" else "fail"
    return {
        "schema": "bears-doctor-goal-validation.v1",
        "status": status,
        "state": str(state),
        "checks": [
            check_packet("goal_state_and_decision_graph", goal_status, True, "goal state and decision graph validate" if goal_status == "pass" else "goal state validation failed"),
            check_packet("file_context_index", context_status, True, "file-context freshness validates" if context_status == "pass" else "file-context freshness failed"),
        ],
        "errors": errors,
        "sanitized_summary": "goal state validates" if status == "pass" else "goal state validation failed",
    }


def validate_node(workflow_tree: Path, node_id: str) -> dict[str, Any]:
    code, summary = run([sys.executable, "scripts/workflow_tree.py", "check-node", "--tree", str(workflow_tree), "--node-id", node_id])
    status = "pass" if code == 0 else "fail"
    return {
        "schema": "bears-doctor-node-validation.v1",
        "status": status,
        "workflow_tree": str(workflow_tree),
        "node_id": node_id,
        "checks": [check_packet("workflow_tree_node", status, True, summary, exit_code=code)],
        "sanitized_summary": "workflow node is valid" if status == "pass" else "workflow node validation failed",
    }


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    closeout = sub.add_parser("validate-closeout")
    closeout.add_argument("--from-git", required=True)
    closeout.add_argument("--json", action="store_true")
    closeout_gate = sub.add_parser("closeout")
    closeout_gate.add_argument("--delivery-id", default="bears-governance-kernel-v1")
    closeout_gate.add_argument("--manifest-root", default="runtime/deliveries")
    closeout_gate.add_argument("--issues-json")
    closeout_gate.add_argument("--fail-on-solved-open-issues", action="store_true")
    closeout_gate.add_argument("--json", action="store_true")
    node = sub.add_parser("validate-node")
    node.add_argument("--workflow-tree", required=True)
    node.add_argument("--node-id", required=True)
    node.add_argument("--json", action="store_true")
    goal = sub.add_parser("validate-goal")
    goal.add_argument("--state", required=True)
    goal.add_argument("--json", action="store_true")
    summary = sub.add_parser("emit-summary")
    summary.add_argument("--from-git", required=True)
    summary.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        packet = {"schema": "bears-doctor-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
        print_packet(packet)
        return 0 if not errors else 1
    if args.command == "validate-closeout":
        packet = closeout_result(args.from_git)
        errors = validate_result_packet(packet, "closeout")
        if errors:
            packet["status"] = "fail"
            packet["blockers"].extend(errors)
            packet["failed_checks"].append("result_schema")
        print_packet(packet) if args.json else print(packet["sanitized_summary"])
        return 0 if packet["status"] == "pass" else 1
    if args.command == "closeout":
        packet = closeout_gate_result(
            delivery_id=str(args.delivery_id),
            manifest_root=Path(args.manifest_root),
            issues_json=Path(args.issues_json) if args.issues_json else None,
            fail_on_solved_open_issues=bool(args.fail_on_solved_open_issues),
        )
        print_packet(packet) if args.json else print(packet["sanitized_summary"])
        return 0 if packet["status"] == "pass" else 1
    if args.command == "validate-node":
        packet = validate_node(Path(args.workflow_tree), args.node_id)
        print_packet(packet) if args.json else print(packet["sanitized_summary"])
        return 0 if packet["status"] == "pass" else 1
    if args.command == "validate-goal":
        packet = validate_goal(Path(args.state))
        print_packet(packet) if args.json else print(packet["sanitized_summary"])
        return 0 if packet["status"] == "pass" else 1
    if args.command == "emit-summary":
        packet = summary_result(args.from_git)
        print_packet(packet) if args.json else print(packet["sanitized_summary"])
        return 0 if packet["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
