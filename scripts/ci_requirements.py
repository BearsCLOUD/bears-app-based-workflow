#!/usr/bin/env python3
"""Validate Bears plugin GitHub push diagnostics."""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/ci-requirements.v1.json"
DEFAULT_WORKFLOW = PLUGIN_ROOT / ".github/workflows/validate.yml"
REQUIRED_SCHEMA = "bears-ci-requirements.v1"
REQUIRED_JOBS = {
    "changes",
    "schema-catalog-validation",
    "hook-policy-validation",
    "role-workflow-validation",
    "skill-inventory-validation",
    "dirty-boundary-validation",
    "ci-summary",
}
FORBIDDEN_AGENT_MANUAL_TRIGGER_EVENTS = {"repository_dispatch"}
FORBIDDEN_DUPLICATE_TEST_RUNNERS = {
    "python3 -m unittest discover -s tests",
    "python3 -m pytest -q tests",
}
LOCAL_COMMIT_VALIDATION_COMMAND = "python3 scripts/local_commit_validation.py run --commit-sha HEAD"
LOCAL_COMMIT_BLOCKING_COMMAND = "python3 scripts/local_commit_validation.py run --staged"
IMPACTED_FAST_TEST_COMMAND = "python3 scripts/test_selection.py run --tier fast"
LOCAL_HOOK_INSTALL_COMMAND = "python3 scripts/local_commit_validation.py install-hook"
REQUIRED_LOCAL_COMMIT_HOOKS = ["pre-commit", "post-commit"]
REQUIRED_TEST_CATEGORIES = {"fast", "integration", "slow"}


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def _workflow_events(workflow: dict[str, Any]) -> dict[str, Any]:
    on_data = workflow.get("on", workflow.get(True))
    if not isinstance(on_data, dict):
        raise ValueError("workflow.on must be an object")
    return on_data


def _workflow_run_text(workflow: dict[str, Any]) -> str:
    chunks: list[str] = []
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return ""
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                chunks.append(step["run"])
    return "\n".join(chunks)


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema") != REQUIRED_SCHEMA:
        errors.append(f"catalog.schema must be {REQUIRED_SCHEMA}")
    trigger_policy = catalog.get("trigger_policy")
    if not isinstance(trigger_policy, dict):
        errors.append("trigger_policy must be an object")
    else:
        if trigger_policy.get("automatic_local_on_commit") is not True:
            errors.append("trigger_policy.automatic_local_on_commit must be true")
        if trigger_policy.get("automatic_github_on_commit") is not True:
            errors.append("trigger_policy.automatic_github_on_commit must be true")
        if trigger_policy.get("automatic_on_pull_request") is not False:
            errors.append("trigger_policy.automatic_on_pull_request must be false for main-only delivery")
        if trigger_policy.get("agent_manual_ci_dispatch_allowed") is not False:
            errors.append("trigger_policy.agent_manual_ci_dispatch_allowed must be false")
        if set(trigger_policy.get("allowed_events", [])) != {"push", "workflow_dispatch"}:
            errors.append("trigger_policy.allowed_events must be push and workflow_dispatch only")
        if trigger_policy.get("push_branches") != ["main"]:
            errors.append("trigger_policy.push_branches must be [main]")
        if trigger_policy.get("operator_emergency_dispatch_allowed") is not True:
            errors.append("trigger_policy.operator_emergency_dispatch_allowed must be true")
        if trigger_policy.get("local_commit_hooks") != REQUIRED_LOCAL_COMMIT_HOOKS:
            errors.append("trigger_policy.local_commit_hooks must be pre-commit, post-commit")
        if trigger_policy.get("blocking_local_commit_hook") != "pre-commit":
            errors.append("trigger_policy.blocking_local_commit_hook must be pre-commit")
        if trigger_policy.get("proof_local_commit_hook") != "post-commit":
            errors.append("trigger_policy.proof_local_commit_hook must be post-commit")
        if trigger_policy.get("local_commit_hook") != "post-commit":
            errors.append("trigger_policy.local_commit_hook must remain post-commit for exact-SHA proof compatibility")
        if trigger_policy.get("local_commit_hook_command") != LOCAL_HOOK_INSTALL_COMMAND:
            errors.append(f"trigger_policy.local_commit_hook_command must be {LOCAL_HOOK_INSTALL_COMMAND}")
        diff_policy = trigger_policy.get("changed_path_diff_policy")
        if not isinstance(diff_policy, dict):
            errors.append("trigger_policy.changed_path_diff_policy must be an object")
        else:
            expected = {
                "local_post_commit": "HEAD^..HEAD",
                "github_push": "HEAD^..HEAD",
            }
            for key, value in expected.items():
                if diff_policy.get(key) != value:
                    errors.append(f"trigger_policy.changed_path_diff_policy.{key} must be {value}")
    jobs = catalog.get("parallel_jobs")
    if not isinstance(jobs, list) or set(jobs) != REQUIRED_JOBS:
        errors.append("parallel_jobs must match the required parallel CI job set")
    test_policy = catalog.get("test_policy")
    if not isinstance(test_policy, dict):
        errors.append("test_policy must be an object")
    else:
        if test_policy.get("single_runner") != "local_commit_validation":
            errors.append("test_policy.single_runner must be local_commit_validation")
        if test_policy.get("selector_runner") != "test_selection":
            errors.append("test_policy.selector_runner must be test_selection")
        if test_policy.get("fast_command") != LOCAL_COMMIT_VALIDATION_COMMAND:
            errors.append(f"test_policy.fast_command must be {LOCAL_COMMIT_VALIDATION_COMMAND}")
        if test_policy.get("blocking_command") != LOCAL_COMMIT_BLOCKING_COMMAND:
            errors.append(f"test_policy.blocking_command must be {LOCAL_COMMIT_BLOCKING_COMMAND}")
        if test_policy.get("impacted_fast_test_command") != IMPACTED_FAST_TEST_COMMAND:
            errors.append(f"test_policy.impacted_fast_test_command must be {IMPACTED_FAST_TEST_COMMAND}")
        if int(test_policy.get("fast_timeout_minutes", 0)) > 12:
            errors.append("test_policy.fast_timeout_minutes must be <= 12")
        if set(test_policy.get("required_categories", [])) != REQUIRED_TEST_CATEGORIES:
            errors.append("test_policy.required_categories must be fast, integration, slow")
    cd_gate = catalog.get("cd_gate")
    if not isinstance(cd_gate, dict):
        errors.append("cd_gate must be an object")
    else:
        if cd_gate.get("local_commit_hooks") != REQUIRED_LOCAL_COMMIT_HOOKS:
            errors.append("cd_gate.local_commit_hooks must be pre-commit, post-commit")
        if cd_gate.get("blocking_local_commit_hook") != "pre-commit":
            errors.append("cd_gate.blocking_local_commit_hook must be pre-commit")
        if cd_gate.get("proof_local_commit_hook") != "post-commit":
            errors.append("cd_gate.proof_local_commit_hook must be post-commit")
        if cd_gate.get("diagnostic_summary_job") != "ci-summary":
            errors.append("cd_gate.diagnostic_summary_job must be ci-summary")
        if cd_gate.get("local_validation_proof_file") != "runtime/local-commit-validation/<main_sha>.json":
            errors.append("cd_gate.local_validation_proof_file must point to exact local commit validation proof")
        if cd_gate.get("delivery_branch") != "main":
            errors.append("cd_gate.delivery_branch must be main")
        if cd_gate.get("cache_sync_state_file") != "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json":
            errors.append("cd_gate.cache_sync_state_file must point to plugin cache sync state")
        for key in (
            "runtime_apply_requires_exact_commit_local_validation_pass",
            "runtime_apply_requires_degradation_continue",
            "local_validation_fail_creates_workflow_defect",
            "cache_sync_requires_exact_commit_local_validation_pass",
            "closeout_requires_cache_sync_done",
            "closeout_requires_effective_hooks_proof",
        ):
            if cd_gate.get(key) is not True:
                errors.append(f"cd_gate.{key} must be true")
    return errors


def validate_workflow(workflow: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    errors = validate_catalog(catalog)
    on_data = _workflow_events(workflow)
    events = set(str(event) for event in on_data)
    if events & FORBIDDEN_AGENT_MANUAL_TRIGGER_EVENTS:
        errors.append("workflow must not expose repository dispatch trigger events")
    if events != {"push", "workflow_dispatch"}:
        errors.append("workflow must expose only push and operator emergency workflow_dispatch")
    push = on_data.get("push")
    if not isinstance(push, dict) or push.get("branches") != ["main"]:
        errors.append("workflow push trigger must be limited to main")
    if "pull_request" in events or "merge_group" in events:
        errors.append("workflow must not include pull_request or merge_group in main-only delivery")
    dispatch = on_data.get("workflow_dispatch")
    if not isinstance(dispatch, dict) or not isinstance(dispatch.get("inputs"), dict) or "emergency_full_suite" not in dispatch["inputs"]:
        errors.append("workflow_dispatch must be limited to operator emergency_full_suite input")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return errors + ["workflow.jobs must be an object"]
    missing = sorted(REQUIRED_JOBS - set(jobs))
    if missing:
        errors.append("workflow missing required jobs: " + ", ".join(missing))
    if "plugin-validation" in jobs:
        errors.append("workflow must not keep the old serial plugin-validation job")
    if "unit-fast" in jobs:
        errors.append("workflow must not define jobs.unit-fast; local commit hooks own automatic fast tests")
    summary = jobs.get("ci-summary")
    if isinstance(summary, dict):
        expected_needs = sorted(REQUIRED_JOBS - {"ci-summary"})
        if sorted(summary.get("needs") or []) != expected_needs:
            errors.append("ci-summary.needs must include every parallel diagnostics job")
    else:
        errors.append("ci-summary diagnostics must be a job object")
    run_text = _workflow_run_text(workflow)
    workflow_text = json.dumps(workflow, sort_keys=True)
    for token in FORBIDDEN_DUPLICATE_TEST_RUNNERS:
        if token in run_text:
            errors.append(f"workflow forbids duplicate/heavy runner token: {token}")
    for token in (
        "HEAD_SHA",
        "changed-files.txt",
    ):
        if token not in workflow_text:
            errors.append(f"workflow changed-path classifier must include manual diagnostics token: {token}")
    if "refs/heads/dev" in workflow_text or "origin/main...HEAD" in workflow_text:
        errors.append("workflow changed-path classifier must not keep branch/PR diff policy")
    for token in (
        "python3 scripts/ci_requirements.py validate-workflow",
        "python3 scripts/ci_requirements.py enforce-test-categories",
        "hooks.json",
        "python3 scripts/platform_roles.py validate",
        "python3 scripts/plugin_cache_sync.py validate-state",
        "python3 scripts/agentic_enterprise_workflow.py validate",
        "python3 scripts/git_discipline.py validate",
    ):
        if token not in run_text:
            errors.append(f"workflow must include operator diagnostics token: {token}")
    for job_id in REQUIRED_JOBS - {"changes", "ci-summary"}:
        job = jobs.get(job_id)
        if isinstance(job, dict):
            timeout = int(job.get("timeout-minutes", 0))
            if timeout <= 0 or timeout > 12:
                errors.append(f"{job_id}.timeout-minutes must be in 1..12")
            if "changes" not in (job.get("needs") or []):
                errors.append(f"{job_id}.needs must include changes for path-based execution")
    if "dev-cd-gate" in jobs:
        errors.append("workflow must not keep branch-based dev-cd-gate in main-only delivery")
    emergency = jobs.get("emergency-full-suite")
    if not isinstance(emergency, dict):
        errors.append("workflow must keep operator-only emergency-full-suite job")
    else:
        if emergency.get("if") != "github.event_name == 'workflow_dispatch' && inputs.emergency_full_suite == true":
            errors.append("emergency-full-suite.if must require workflow_dispatch and emergency_full_suite")
        emergency_run = "\n".join(
            step.get("run", "")
            for step in emergency.get("steps") or []
            if isinstance(step, dict) and isinstance(step.get("run"), str)
        )
        if "python3 scripts/test_selection.py run --suite full --tier full" not in emergency_run:
            errors.append("emergency-full-suite must run test_selection full suite only under operator dispatch")
    return errors


def enforce_test_categories(catalog: dict[str, Any], root: Path) -> list[str]:
    errors = validate_catalog(catalog)
    policy = catalog.get("test_policy") if isinstance(catalog.get("test_policy"), dict) else {}
    entries = policy.get("test_files", []) if isinstance(policy, dict) else []
    if not isinstance(entries, list):
        return errors + ["test_policy.test_files must be a list"]
    catalog_map: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("test_policy.test_files entries must be objects")
            continue
        path = entry.get("path")
        category = entry.get("category")
        if not isinstance(path, str) or not path.startswith("tests/test_") or not path.endswith(".py"):
            errors.append("test_policy.test_files.path must be tests/test_*.py")
            continue
        if category not in REQUIRED_TEST_CATEGORIES:
            errors.append(f"test_policy.test_files category for {path} must be fast, integration, or slow")
            continue
        catalog_map[path] = category
    actual = sorted(str(path.relative_to(root)) for path in (root / "tests").glob("test_*.py"))
    missing = sorted(set(actual) - set(catalog_map))
    stale = sorted(set(catalog_map) - set(actual))
    if missing:
        errors.append("test files missing category catalog entries: " + ", ".join(missing))
    if stale:
        errors.append("test category catalog entries reference missing files: " + ", ".join(stale))
    return errors


def emit_path_flags(files: list[str]) -> dict[str, bool]:
    files = [f for f in files if f]
    if not files:
        return {name: False for name in ("docs_only", "schema_catalog", "hooks", "skills", "workflow_core", "dirty_boundary", "unit_fast", "full_fast")}

    def any_match(patterns: list[str]) -> bool:
        return any(any(fnmatch.fnmatch(path, pattern) for pattern in patterns) for path in files)

    docs_patterns = ["docs/**", "README.md", "SPEC.md", "requirements.md"]
    docs_only = all(any(fnmatch.fnmatch(path, pattern) for pattern in docs_patterns) for path in files)
    schema_catalog = any_match([".codex-plugin/plugin.json", "assets/catalog/**", "assets/schemas/**", "schemas/**", "pyproject.toml", "requirements-dev.txt"])
    hooks = any_match(["hooks/**", "hooks.json"])
    skills = any_match(["skills/**", "assets/catalog/plugin-skill-catalog.v1.json", "docs/generated/*skill*", "scripts/skill_catalog.py"])
    workflow_core = any_match([".github/workflows/**", "workflows/**", "agents/**", "scripts/**", "assets/catalog/*workflow*", "assets/catalog/*role*", "assets/catalog/subagent-*", "assets/catalog/agent-github-dev-cd.v1.json"])
    dirty_boundary = any_match(["docs/generated/dirty-baseline-inventory.v1.json", "scripts/git_discipline.py", "scripts/development_workflow_validate.py"])
    unit_fast = (not docs_only) and any_match(["tests/**", "scripts/**", "hooks/**", "assets/**", "agents/**", "workflows/**", ".codex-plugin/plugin.json", ".github/workflows/**"])
    full_fast = any_match([".github/workflows/**", "scripts/**", "tests/**"])
    return {
        "docs_only": docs_only,
        "schema_catalog": schema_catalog,
        "hooks": hooks,
        "skills": skills,
        "workflow_core": workflow_core,
        "dirty_boundary": dirty_boundary,
        "unit_fast": unit_fast,
        "full_fast": full_fast,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-catalog").add_argument("catalog", nargs="?", default=str(DEFAULT_CATALOG))
    vwf = sub.add_parser("validate-workflow")
    vwf.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))
    vwf.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    etc = sub.add_parser("enforce-test-categories")
    etc.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    etc.add_argument("--root", default=str(PLUGIN_ROOT))
    epf = sub.add_parser("emit-path-flags")
    epf.add_argument("--files", required=True)
    args = parser.parse_args()
    if args.command == "validate-catalog":
        errors = validate_catalog(_load_json(Path(args.catalog)))
    elif args.command == "validate-workflow":
        errors = validate_workflow(_load_yaml(Path(args.workflow)), _load_json(Path(args.catalog)))
    elif args.command == "enforce-test-categories":
        errors = enforce_test_categories(_load_json(Path(args.catalog)), Path(args.root))
    elif args.command == "emit-path-flags":
        files = Path(args.files).read_text(encoding="utf-8").splitlines()
        print(json.dumps({"schema": "bears-ci-path-flags.v1", "flags": emit_path_flags(files)}, indent=2))
        return 0
    else:
        raise AssertionError(args.command)
    if errors:
        print(json.dumps({"schema": REQUIRED_SCHEMA, "status": "fail", "errors": errors}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"schema": REQUIRED_SCHEMA, "status": "pass"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
