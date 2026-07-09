#!/usr/bin/env python3
"""Plan-only PR pipeline state and gate mechanics for Bears worker orchestration."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_STATES = (
    "implementing",
    "needs_review",
    "review_failed",
    "fixing",
    "review_passed",
    "ready_to_merge",
    "merged",
    "blocked",
)
PASS_VALUES = {"pass", "passed", "success", "successful", "review_pass", "review_passed", "approved"}
FAIL_VALUES = {"fail", "failed", "failure", "review_fail", "review_failed", "changes_requested"}
PENDING_VALUES = {"pending", "queued", "in_progress", "waiting", "none", "unknown", ""}
REQUIRED_REVIEW_PASS = "REVIEW_PASS"
REQUIRED_REVIEW_FAIL = "REVIEW_FAIL"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def normalize_status(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold().replace("-", "_").replace(" ", "_")


def is_pass(value: Any) -> bool:
    return normalize_status(value) in PASS_VALUES


def is_fail(value: Any) -> bool:
    return normalize_status(value) in FAIL_VALUES


def is_pending(value: Any) -> bool:
    return normalize_status(value) in PENDING_VALUES


def changed_files(pr: dict[str, Any]) -> list[str]:
    files = pr.get("changed_files", pr.get("files", []))
    if not isinstance(files, list):
        return []
    normalized: list[str] = []
    for item in files:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            normalized.append(item["path"].strip())
    return sorted(dict.fromkeys(normalized))


def validation_commands(pr: dict[str, Any], review: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    commands = pr.get("validation_commands", pr.get("validators", []))
    if review and not commands:
        commands = review.get("validation_commands", review.get("validator_evidence", []))
    if not isinstance(commands, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in commands:
        if isinstance(item, str):
            normalized.append({"command": item, "exit_code": None})
        elif isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


def validators_pass(commands: list[dict[str, Any]]) -> bool:
    if not commands:
        return False
    for command in commands:
        if command.get("exit_code") != 0:
            return False
    return True


def route_audit_pass(pr: dict[str, Any]) -> bool:
    value = pr.get("route_audit_status", pr.get("route_status", "pass"))
    return is_pass(value) or normalize_status(value) in {"matched", "ok"}


def merge_gate(
    pr: dict[str, Any],
    *,
    expected_head: str | None = None,
    expected_files: list[str] | None = None,
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    head_sha = str(pr.get("head_sha", pr.get("headRefOid", ""))).strip()
    files = changed_files(pr)
    review_state = review.get("status") if review else pr.get("review_state", pr.get("reviewDecision"))
    ci_state = pr.get("ci_state", pr.get("statusCheckRollup", pr.get("check_state")))
    expected_files_sorted = sorted(dict.fromkeys(expected_files or []))

    if not head_sha:
        reasons.append("missing head SHA")
    if expected_head is None or not str(expected_head).strip():
        reasons.append("missing expected head SHA")
    elif head_sha and head_sha != str(expected_head).strip():
        reasons.append("changed head SHA")
    if expected_files is None:
        reasons.append("missing exact expected file list")
    elif files != expected_files_sorted:
        reasons.append("changed file set")
    if not files:
        reasons.append("missing changed files")
    if not is_pass(review_state) and str(review_state).strip() != REQUIRED_REVIEW_PASS:
        reasons.append("missing REVIEW_PASS")
    if not is_pass(ci_state):
        reasons.append("required status checks not passing")
    if pr.get("is_draft", pr.get("draft", False)) is True:
        reasons.append("draft PR is not merge eligible")
    if pr.get("mergeable") is False:
        reasons.append("PR is not mergeable")
    if pr.get("validation_worktree") == "dirty" or pr.get("shared_checkout_dirty") is True:
        reasons.append("dirty shared checkout used for validation")
    if not route_audit_pass(pr):
        reasons.append("route/audit did not pass")
    commands = validation_commands(pr, review)
    if not validators_pass(commands):
        reasons.append("validation commands missing or failed")

    return {
        "schema": "bears-pr-pipeline-merge-gate.v1",
        "status": "MERGE_ALLOWED" if not reasons else "MERGE_BLOCKED",
        "merge_eligible": not reasons,
        "reasons": reasons,
        "pr": pr.get("number"),
        "branch": pr.get("branch", pr.get("head_ref", pr.get("headRefName"))),
        "head_sha": head_sha,
        "changed_files": files,
        "ci_state": ci_state,
        "review_state": review_state,
        "validation_commands": commands,
    }


def classify_state(pr: dict[str, Any], *, review: dict[str, Any] | None = None) -> dict[str, Any]:
    if pr.get("blocked_reason"):
        state = "blocked"
    elif pr.get("merged") is True or normalize_status(pr.get("state")) == "merged":
        state = "merged"
    elif is_fail(pr.get("review_state", pr.get("reviewDecision"))):
        state = "review_failed"
    elif pr.get("fix_in_progress") is True:
        state = "fixing"
    elif is_pass(pr.get("review_state", pr.get("reviewDecision"))):
        gate = merge_gate(
            pr,
            expected_head=str(pr.get("head_sha", pr.get("headRefOid", ""))).strip() or None,
            expected_files=changed_files(pr),
            review=review,
        )
        state = "ready_to_merge" if gate["merge_eligible"] else "review_passed"
    elif changed_files(pr) and pr.get("head_sha", pr.get("headRefOid")):
        state = "needs_review"
    else:
        state = "implementing"
    return {
        "schema": "bears-pr-pipeline-state.v1",
        "status": "ok",
        "state": state,
        "state_order": list(PIPELINE_STATES),
        "pr": pr.get("number"),
        "issue": pr.get("issue"),
        "branch": pr.get("branch", pr.get("head_ref", pr.get("headRefName"))),
        "head_sha": pr.get("head_sha", pr.get("headRefOid")),
        "changed_files": changed_files(pr),
        "ci_state": pr.get("ci_state", pr.get("check_state")),
        "review_state": pr.get("review_state", pr.get("reviewDecision")),
        "merge_gate": merge_gate(
            pr,
            expected_head=str(pr.get("head_sha", pr.get("headRefOid", ""))).strip() or None,
            expected_files=changed_files(pr) or None,
            review=review,
        ),
    }


def build_fix_packet(pr: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    status = review.get("status", review.get("verdict"))
    if not (is_fail(status) or str(status).strip() == REQUIRED_REVIEW_FAIL):
        return {
            "schema": "bears-pr-pipeline-fix-packet.v1",
            "status": "blocked",
            "reason": "review result is not REVIEW_FAIL",
        }
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    files: list[str] = []
    regression_tests: list[str] = []
    for finding in findings:
        if isinstance(finding, dict):
            file_value = finding.get("file") or finding.get("path")
            if isinstance(file_value, str) and file_value.strip():
                files.append(file_value.strip())
            test_value = finding.get("regression_test")
            if isinstance(test_value, str) and test_value.strip():
                regression_tests.append(test_value.strip())
    allowed_write_files = sorted(dict.fromkeys(files or changed_files(pr)))
    validators = validation_commands(pr, review)
    return {
        "schema": "bears-pr-pipeline-fix-packet.v1",
        "status": "FIX_PACKET_READY",
        "repository": pr.get("repo", review.get("repo")),
        "pr": pr.get("number", review.get("pr")),
        "failing_head_sha": pr.get("head_sha", review.get("head_sha")),
        "owning_role": review.get("owning_role", pr.get("role", "ROLE_COVERAGE_REQUIRED")),
        "reviewer_role": review.get("reviewer_role"),
        "reviewer_findings": findings,
        "allowed_write_files": allowed_write_files,
        "forbidden_scope": [
            "product/runtime/provider mutation outside the failing PR scope",
            "secrets, .env values, raw logs, raw chat, raw VPN configs, and production data",
            "merge, final review request, or PR approval mutation",
        ],
        "required_regression_tests": sorted(dict.fromkeys(regression_tests)),
        "required_validators": validators,
        "expected_final_status": "FIX_PASS",
    }


def post_merge_report(pr: dict[str, Any]) -> dict[str, Any]:
    merged = pr.get("merged") is True or normalize_status(pr.get("state")) == "merged"
    linked = pr.get("linked_issues", [])
    if not isinstance(linked, list):
        linked = []
    still_open = [item for item in linked if isinstance(item, dict) and normalize_status(item.get("state")) == "open"]
    ledger = pr.get("ledger", {}) if isinstance(pr.get("ledger"), dict) else {}
    ledger_followups: list[dict[str, Any]] = []
    if still_open:
        ledger_followups.append({"action": "issue_follow_up", "reason": "linked issue remains open after merge"})
    if ledger.get("root_status") in {"pending", "stale", "pending-access"}:
        ledger_followups.append({"action": "root_ledger_follow_up", "reason": "root ledger still marks the slice pending"})
    if ledger.get("child_status") in {"pending", "stale", "pending-access"}:
        ledger_followups.append({"action": "child_migration_ledger_follow_up", "reason": "child migration ledger still marks the slice pending"})
    return {
        "schema": "bears-pr-pipeline-post-merge.v1",
        "status": "ok",
        "pr": pr.get("number"),
        "merged": merged,
        "merge_commit_sha": pr.get("merge_commit_sha"),
        "linked_issues_open": still_open,
        "ledger_follow_up_required": bool(ledger_followups),
        "ledger_followups": ledger_followups,
        "next_suggested_backend_only_tasks": pr.get("next_suggested_backend_only_tasks", []),
    }


def run_gh_pr_view(repo: str, pr_number: int) -> dict[str, Any]:
    fields = "number,state,isDraft,headRefName,headRefOid,baseRefName,mergeable,reviewDecision,files"
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", fields],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr view failed")
    raw = json.loads(proc.stdout)
    return {
        "repo": repo,
        "number": raw.get("number"),
        "state": raw.get("state"),
        "is_draft": raw.get("isDraft"),
        "branch": raw.get("headRefName"),
        "head_sha": raw.get("headRefOid"),
        "base": raw.get("baseRefName"),
        "mergeable": raw.get("mergeable") != "CONFLICTING",
        "review_state": raw.get("reviewDecision"),
        "changed_files": [item.get("path") for item in raw.get("files", []) if isinstance(item, dict)],
    }


def state_command(args: argparse.Namespace) -> int:
    pr = load_json(Path(args.pr_state)) if args.pr_state else run_gh_pr_view(args.repo, args.pr)
    review = load_json(Path(args.review_result)) if args.review_result else None
    emit(classify_state(pr, review=review))
    return 0


def fix_packet_command(args: argparse.Namespace) -> int:
    pr = load_json(Path(args.pr_state)) if args.pr_state else run_gh_pr_view(args.repo, args.pr)
    review = load_json(Path(args.review_result))
    emit(build_fix_packet(pr, review))
    return 0


def merge_command(args: argparse.Namespace) -> int:
    pr = load_json(Path(args.pr_state)) if args.pr_state else run_gh_pr_view(args.repo, args.pr)
    review = load_json(Path(args.review_pass)) if args.review_pass else None
    expected_files = None
    if args.expected_files:
        expected_files = [line.strip() for line in Path(args.expected_files).read_text(encoding="utf-8").splitlines() if line.strip()]
    gate = merge_gate(pr, expected_head=args.expected_head, expected_files=expected_files, review=review)
    payload = {
        "schema": "bears-pr-pipeline-merge-plan.v1",
        "status": "plan_only" if not args.execute else "execution_requested",
        "mutation_performed": False,
        "repo": args.repo or pr.get("repo"),
        "pr": args.pr or pr.get("number"),
        "gate": gate,
    }
    if args.execute:
        if args.operator_action != "merge_pr":
            payload["status"] = "blocked"
            payload["reason"] = "execution requires --operator-action merge_pr"
        elif not gate["merge_eligible"]:
            payload["status"] = "blocked"
            payload["reason"] = "merge gate blocked"
        else:
            payload["status"] = "ready_for_explicit_github_merge"
            payload["reason"] = "script is plan-first; caller must perform approved GitHub mutation outside validation mode"
    emit(payload)
    return 0 if payload["status"] in {"plan_only", "ready_for_explicit_github_merge"} else 2


def post_merge_command(args: argparse.Namespace) -> int:
    pr = load_json(Path(args.pr_state)) if args.pr_state else run_gh_pr_view(args.repo, args.pr)
    emit(post_merge_report(pr))
    return 0


def validate_command(_: argparse.Namespace) -> int:
    fixture_pr = {
        "repo": "BearsCLOUD/bears_plugin",
        "number": 201,
        "issue": 201,
        "branch": "codex/issue-201-worker-pool-pr-pipeline",
        "head_sha": "0" * 40,
        "changed_files": ["scripts/pr_pipeline.py", "tests/test_pr_pipeline.py"],
        "ci_state": "pass",
        "review_state": "REVIEW_PASS",
        "mergeable": True,
        "validation_commands": [{"command": "python3 scripts/pr_pipeline.py validate", "exit_code": 0}],
    }
    gate = merge_gate(
        fixture_pr,
        expected_head="0" * 40,
        expected_files=["scripts/pr_pipeline.py", "tests/test_pr_pipeline.py"],
        review={"status": "REVIEW_PASS"},
    )
    errors: list[str] = []
    if classify_state(fixture_pr)["state"] != "ready_to_merge":
        errors.append("state classifier did not produce ready_to_merge")
    if not gate["merge_eligible"]:
        errors.append(f"merge gate should pass fixture: {gate['reasons']}")
    fail_packet = build_fix_packet(
        fixture_pr,
        {"status": "REVIEW_FAIL", "findings": [{"file": "scripts/pr_pipeline.py"}], "owning_role": "bears-session-worker-runtime-engineer"},
    )
    if fail_packet["status"] != "FIX_PACKET_READY":
        errors.append("fix packet fixture did not pass")
    if post_merge_report({"merged": True, "linked_issues": [{"number": 201, "state": "open"}]})["ledger_follow_up_required"] is not True:
        errors.append("post-merge fixture did not detect open issue follow-up")
    if errors:
        emit({"status": "fail", "errors": errors})
        return 1
    emit({"status": "ok", "validated": ["state", "merge_gate", "fix_packet", "post_merge"]})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    state = sub.add_parser("state", help="Classify one PR pipeline state.")
    state.add_argument("--repo")
    state.add_argument("--pr", type=int)
    state.add_argument("--pr-state")
    state.add_argument("--review-result")
    state.set_defaults(func=state_command)

    fix = sub.add_parser("fix-packet", help="Convert REVIEW_FAIL evidence into a fix assignment packet.")
    fix.add_argument("--repo")
    fix.add_argument("--pr", type=int)
    fix.add_argument("--pr-state")
    fix.add_argument("--review-result", required=True)
    fix.set_defaults(func=fix_packet_command)

    merge = sub.add_parser("merge", help="Plan or explicitly gate a guarded merge.")
    merge.add_argument("--repo")
    merge.add_argument("--pr", type=int)
    merge.add_argument("--pr-state")
    merge.add_argument("--expected-head", required=False)
    merge.add_argument("--expected-files")
    merge.add_argument("--review-pass")
    merge.add_argument("--execute", action="store_true")
    merge.add_argument("--operator-action")
    merge.set_defaults(func=merge_command)

    post = sub.add_parser("post-merge", help="Report post-merge issue and ledger follow-up.")
    post.add_argument("--repo")
    post.add_argument("--pr", type=int)
    post.add_argument("--pr-state")
    post.set_defaults(func=post_merge_command)

    validate = sub.add_parser("validate", help="Run deterministic self-validation fixtures.")
    validate.set_defaults(func=validate_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        emit({"status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
