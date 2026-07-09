#!/usr/bin/env python3
"""Plan-only worker-pool mechanics for Bears PR pipeline orchestration."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BACKEND_FORBIDDEN_MARKERS = (
    "frontend",
    "mobile",
    "ui/",
    "web-client",
    "web_client",
    "kubernetes",
    "serverspace",
    "infisical",
    "provider/runtime mutation",
    "runtime mutation",
    "raw secrets",
    "raw secret",
    "raw logs",
    "raw log",
    "raw vpn",
    "production data",
)
WRITER_MODES = {"writer", "implementer", "fixer"}
REVIEWER_MODES = {"reviewer", "reviewer-only", "read-only", "readonly"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def normalize_scope(scope: str) -> str:
    text = scope.strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    for suffix in ("/**", "/*"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    if text.endswith("/") and text != "/":
        text = text[:-1]
    return text.strip("/")


def scope_kind(scope: str) -> str:
    return "directory" if scope.endswith("/**") or scope.endswith("/*") or scope.endswith("/") else "file"


def scope_overlap(left: str, right: str) -> dict[str, Any]:
    a = normalize_scope(left)
    b = normalize_scope(right)
    if not a or not b:
        return {"overlap": False, "reason": "empty_scope"}
    if a == b:
        reason = "exact_file_overlap" if scope_kind(left) == "file" and scope_kind(right) == "file" else "parent_directory_overlap"
        return {"overlap": True, "reason": reason, "left": left, "right": right}
    if a.startswith(b + "/") or b.startswith(a + "/"):
        return {"overlap": True, "reason": "parent_directory_overlap", "left": left, "right": right}
    return {"overlap": False, "reason": "disjoint", "left": left, "right": right}


def is_reviewer_only(item: dict[str, Any]) -> bool:
    mode = str(item.get("mode", item.get("role_mode", ""))).casefold()
    if mode in REVIEWER_MODES:
        return True
    role = str(item.get("role", "")).casefold()
    return "reviewer" in role and mode not in WRITER_MODES


def detect_conflicts(candidate_scope: list[str], active_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    candidate = {"mode": "writer"}
    for active in active_items:
        if is_reviewer_only(active) and active.get("requires_mutable_checkout") is not True:
            continue
        active_scope = active.get("write_scope", active.get("changed_files", []))
        if not isinstance(active_scope, list):
            active_scope = []
        for left in candidate_scope:
            for right in active_scope:
                if not isinstance(left, str) or not isinstance(right, str):
                    continue
                overlap = scope_overlap(left, right)
                if overlap["overlap"]:
                    conflicts.append(
                        {
                            "active_id": active.get("id", active.get("pr", active.get("number"))),
                            "active_kind": active.get("kind", "assignment"),
                            "reason": overlap["reason"],
                            "candidate_scope": left,
                            "active_scope": right,
                        }
                    )
    return conflicts


def backend_forbidden_reasons(issue: dict[str, Any]) -> list[str]:
    text_parts: list[str] = []
    for field in ("title", "body", "summary", "lane"):
        value = issue.get(field)
        if isinstance(value, str):
            text_parts.append(value)
    for scope in issue.get("write_scope", []):
        if isinstance(scope, str):
            text_parts.append(scope)
    text = "\n".join(text_parts).casefold()
    reasons = []
    for marker in BACKEND_FORBIDDEN_MARKERS:
        if marker in text:
            reasons.append(f"backend-only excludes {marker}")
    return sorted(dict.fromkeys(reasons))


def issue_number(item: dict[str, Any]) -> int | None:
    value = item.get("number", item.get("issue"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dependency_order(issues: list[dict[str, Any]]) -> list[int]:
    by_number = {issue_number(issue): issue for issue in issues if issue_number(issue) is not None}
    ordered: list[int] = []
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(number: int) -> None:
        if number in visited:
            return
        if number in visiting:
            return
        visiting.add(number)
        issue = by_number.get(number, {})
        deps = issue.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                try:
                    dep_number = int(dep)
                except (TypeError, ValueError):
                    continue
                if dep_number in by_number:
                    visit(dep_number)
        visiting.remove(number)
        visited.add(number)
        ordered.append(number)

    for number in sorted(by_number):
        visit(number)
    return ordered


def is_issue_done(number: int, prs: list[dict[str, Any]], issues: list[dict[str, Any]]) -> bool:
    for issue in issues:
        if issue_number(issue) == number and str(issue.get("state", "")).casefold() == "closed":
            return True
    for pr in prs:
        if int(pr.get("issue", -1) or -1) == number and (pr.get("merged") is True or str(pr.get("state", "")).casefold() == "merged"):
            return True
    return False


def active_items_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for assignment in state.get("assignments", state.get("active_assignments", [])):
        if isinstance(assignment, dict) and str(assignment.get("status", "active")).casefold() not in {"closed", "completed", "merged"}:
            item = dict(assignment)
            item.setdefault("kind", "assignment")
            active.append(item)
    for pr in state.get("pull_requests", state.get("prs", [])):
        if not isinstance(pr, dict):
            continue
        if pr.get("merged") is True or str(pr.get("state", "open")).casefold() in {"closed", "merged"}:
            continue
        item = {
            "id": f"pr-{pr.get('number')}",
            "kind": "pull_request",
            "pr": pr.get("number"),
            "mode": "writer",
            "write_scope": pr.get("write_scope", pr.get("changed_files", [])),
        }
        active.append(item)
    return active


def pr_merge_eligibility(pr: dict[str, Any]) -> str:
    review = str(pr.get("review_state", pr.get("reviewDecision", ""))).casefold()
    ci = str(pr.get("ci_state", pr.get("check_state", ""))).casefold()
    if pr.get("is_draft") is True:
        return "blocked:draft"
    if review in {"pass", "passed", "review_pass", "approved"} and ci in {"pass", "passed", "success"} and pr.get("mergeable", True) is not False:
        return "ready_to_merge"
    if review in {"fail", "failed", "review_fail", "changes_requested"}:
        return "needs_fix"
    if review in {"", "none", "pending", "review_required"}:
        return "needs_review"
    return "blocked:checks_or_review_pending"


def stale_cleanup(pr: dict[str, Any]) -> bool:
    branch = str(pr.get("branch", pr.get("head_ref", ""))).strip()
    if branch in {"", "main", "dev"}:
        return False
    return pr.get("merged") is True or str(pr.get("state", "")).casefold() in {"closed", "merged"}


def plan_from_state(state: dict[str, Any], *, repo: str | None, mode: str) -> dict[str, Any]:
    issues = [item for item in state.get("issues", []) if isinstance(item, dict)]
    prs = [item for item in state.get("pull_requests", state.get("prs", [])) if isinstance(item, dict)]
    active = active_items_from_state(state)
    actions: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    tracked: list[dict[str, Any]] = []

    for pr in prs:
        eligibility = pr_merge_eligibility(pr)
        tracked.append(
            {
                "assigned_issue_slice": pr.get("issue"),
                "branch": pr.get("branch", pr.get("head_ref")),
                "pr": pr.get("number"),
                "head_sha": pr.get("head_sha"),
                "ci_state": pr.get("ci_state"),
                "review_state": pr.get("review_state"),
                "merge_eligibility": eligibility,
                "stale_branch_cleanup_eligible": stale_cleanup(pr),
                "dependencies": pr.get("dependencies", []),
            }
        )
        if eligibility == "needs_review":
            actions.append({"action": "spawn_reviewer", "pr": pr.get("number"), "expected_head_sha": pr.get("head_sha"), "write_scope": []})
        elif eligibility == "needs_fix":
            actions.append({"action": "spawn_fixer", "pr": pr.get("number"), "issue": pr.get("issue"), "expected_head_sha": pr.get("head_sha"), "write_scope": pr.get("changed_files", [])})
        elif eligibility == "ready_to_merge":
            actions.append({"action": "guarded_merge_dry_run", "pr": pr.get("number"), "expected_head_sha": pr.get("head_sha"), "write_scope": []})
        if stale_cleanup(pr):
            actions.append({"action": "stale_branch_cleanup_plan", "pr": pr.get("number"), "branch": pr.get("branch", pr.get("head_ref"))})

    open_pr_issues = {int(pr.get("issue")) for pr in prs if pr.get("issue") is not None and str(pr.get("state", "open")).casefold() == "open"}
    for issue in issues:
        number = issue_number(issue)
        if number is None or number in open_pr_issues:
            continue
        if str(issue.get("state", "open")).casefold() != "open":
            continue
        scope = issue.get("write_scope", [])
        if not isinstance(scope, list):
            scope = []
        reasons: list[str] = []
        if not scope:
            reasons.append("missing write_scope")
        if issue.get("role") in (None, "", "ROLE_COVERAGE_REQUIRED"):
            reasons.append("missing exact role route")
        if mode == "backend-only":
            reasons.extend(backend_forbidden_reasons(issue))
        deps = issue.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                try:
                    dep_number = int(dep)
                except (TypeError, ValueError):
                    continue
                if not is_issue_done(dep_number, prs, issues):
                    reasons.append(f"dependency issue #{dep_number} is not complete")
        conflicts = detect_conflicts([s for s in scope if isinstance(s, str)], active)
        reasons.extend([f"write-scope conflict with {c['active_id']}: {c['reason']}" for c in conflicts])
        if reasons:
            blocked.append({"issue": number, "reason": "; ".join(sorted(dict.fromkeys(reasons)))})
        else:
            actions.append(
                {
                    "action": "spawn_implementer",
                    "issue": number,
                    "role": issue.get("role", "ROLE_COVERAGE_REQUIRED"),
                    "write_scope": scope,
                    "reason": "No active writer overlaps this scope",
                }
            )

    for pr in prs:
        if (pr.get("merged") is True or str(pr.get("state", "")).casefold() == "merged") and pr.get("issue_state") == "open":
            actions.append({"action": "post_merge_ledger_follow_up", "pr": pr.get("number"), "issue": pr.get("issue")})

    return {
        "schema": "bears-worker-pool-plan.v1",
        "status": "ok",
        "repo": repo or state.get("repo"),
        "mode": mode,
        "actions": actions,
        "blocked": blocked,
        "tracked_pipelines": tracked,
        "dependency_order": dependency_order(issues),
        "mutation_performed": False,
    }


def collect_state(repo: str) -> dict[str, Any]:
    issue_proc = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "open", "--limit", "100", "--json", "number,title,state,labels,body"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if issue_proc.returncode != 0:
        raise RuntimeError(issue_proc.stderr.strip() or "gh issue list failed")
    pr_proc = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "100", "--json", "number,title,state,isDraft,headRefName,headRefOid,reviewDecision,statusCheckRollup,files"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if pr_proc.returncode != 0:
        raise RuntimeError(pr_proc.stderr.strip() or "gh pr list failed")
    issues = []
    for raw in json.loads(issue_proc.stdout):
        issues.append({"number": raw.get("number"), "title": raw.get("title"), "state": raw.get("state"), "body": raw.get("body"), "labels": [l.get("name") for l in raw.get("labels", []) if isinstance(l, dict)], "write_scope": []})
    prs = []
    for raw in json.loads(pr_proc.stdout):
        prs.append({"number": raw.get("number"), "state": raw.get("state"), "is_draft": raw.get("isDraft"), "branch": raw.get("headRefName"), "head_sha": raw.get("headRefOid"), "review_state": raw.get("reviewDecision"), "ci_state": "unknown", "changed_files": [f.get("path") for f in raw.get("files", []) if isinstance(f, dict)]})
    return {"repo": repo, "issues": issues, "pull_requests": prs, "assignments": []}


def allocate_worktree_plan(args: argparse.Namespace) -> dict[str, Any]:
    purpose = args.purpose
    if purpose not in {"implementation", "fix", "review", "merge", "audit"}:
        raise ValueError("purpose must be implementation, fix, review, merge, or audit")
    base_ref = args.branch or ("origin/main" if purpose == "implementation" else None)
    if purpose in {"review", "merge", "audit"} and not args.expected_sha:
        raise ValueError("review, merge, and audit worktrees require --expected-sha")
    target = args.path or f"/tmp/bears-worker-{purpose}-{args.pr or 'issue'}"
    return {
        "schema": "bears-worker-pool-worktree-allocation.v1",
        "status": "plan_only" if not args.execute else "local_allocation_requested",
        "mutation_performed": False,
        "repo": args.repo,
        "purpose": purpose,
        "pr": args.pr,
        "branch": args.branch,
        "expected_sha": args.expected_sha,
        "base_ref": base_ref,
        "worktree_path": target,
        "fresh_checkout_required": True,
        "shared_dirty_checkout_allowed": False,
        "cleanup_instructions": [f"git worktree remove {target}", f"rm -rf {target}"],
    }


def plan_command(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state_file)) if args.state_file else collect_state(args.repo)
    emit(plan_from_state(state, repo=args.repo, mode=args.mode))
    return 0


def conflict_command(args: argparse.Namespace) -> int:
    candidate = load_json(Path(args.candidate))
    active_state = load_json(Path(args.active))
    scope = candidate.get("write_scope", [])
    if not isinstance(scope, list):
        scope = []
    active = active_state.get("active", active_state.get("assignments", []))
    if not isinstance(active, list):
        active = []
    conflicts = detect_conflicts([s for s in scope if isinstance(s, str)], [a for a in active if isinstance(a, dict)])
    emit({"schema": "bears-worker-pool-conflict-check.v1", "status": "blocked" if conflicts else "ok", "conflicts": conflicts})
    return 1 if conflicts else 0


def allocate_command(args: argparse.Namespace) -> int:
    payload = allocate_worktree_plan(args)
    if args.execute:
        payload["status"] = "blocked"
        payload["reason"] = "local worktree execution is disabled in validation mode; rerun only from an explicit operator action lane"
        emit(payload)
        return 2
    emit(payload)
    return 0


def validate_command(_: argparse.Namespace) -> int:
    state = {
        "repo": "BearsCLOUD/bears_plugin",
        "issues": [
            {"number": 201, "state": "open", "role": "bears-session-worker-runtime-engineer", "write_scope": ["scripts/worker_pool.py", "tests/test_worker_pool.py"], "dependencies": []},
            {"number": 202, "state": "open", "role": "bears-session-worker-runtime-engineer", "write_scope": ["frontend/app/**"], "dependencies": []},
            {"number": 203, "state": "open", "role": "bears-session-worker-runtime-engineer", "write_scope": ["scripts/pr_pipeline.py"], "dependencies": [201]},
        ],
        "pull_requests": [
            {"number": 301, "issue": 199, "state": "open", "branch": "codex/block-generic-role-fallback", "head_sha": "1" * 40, "review_state": "none", "ci_state": "pending", "changed_files": ["assets/catalog/session-workers-runtime.v1.json"]}
        ],
        "assignments": [],
    }
    plan = plan_from_state(state, repo=state["repo"], mode="backend-only")
    errors: list[str] = []
    if not any(action.get("action") == "spawn_implementer" and action.get("issue") == 201 for action in plan["actions"]):
        errors.append("issue 201 should be safe to start")
    if not any(item.get("issue") == 202 and "backend-only excludes frontend" in item.get("reason", "") for item in plan["blocked"]):
        errors.append("backend-only forbidden frontend scope was not blocked")
    if not any(item.get("issue") == 203 and "dependency issue #201" in item.get("reason", "") for item in plan["blocked"]):
        errors.append("dependency block was not reported")
    exact = detect_conflicts(["a/b.py"], [{"id": "x", "mode": "writer", "write_scope": ["a/b.py"]}])
    parent = detect_conflicts(["a/**"], [{"id": "x", "mode": "writer", "write_scope": ["a/b.py"]}])
    reviewer = detect_conflicts(["a/b.py"], [{"id": "r", "mode": "reviewer-only", "write_scope": ["a/b.py"]}])
    disjoint = detect_conflicts(["docs/a.md"], [{"id": "s", "mode": "writer", "write_scope": ["src/a.py"]}])
    if not exact or exact[0]["reason"] != "exact_file_overlap":
        errors.append("exact file overlap was not detected")
    if not parent or parent[0]["reason"] != "parent_directory_overlap":
        errors.append("parent directory overlap was not detected")
    if reviewer:
        errors.append("reviewer-only non-overlap blocked implementer")
    if disjoint:
        errors.append("docs/source disjoint scopes conflicted")
    if errors:
        emit({"status": "fail", "errors": errors})
        return 1
    emit({"status": "ok", "validated": ["plan", "conflicts", "backend_only", "dependency_order", "worktree_plan"]})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Return a deterministic worker-pool action plan.")
    plan.add_argument("--repo", required=True)
    plan.add_argument("--mode", default="backend-only", choices=["backend-only", "all"])
    plan.add_argument("--backend-only", action="store_true", help="Compatibility flag; sets --mode backend-only.")
    plan.add_argument("--state-file")
    plan.set_defaults(func=plan_command)

    conflict = sub.add_parser("conflicts", help="Check candidate write scope against active workers/PRs.")
    conflict.add_argument("--candidate", required=True)
    conflict.add_argument("--active", required=True)
    conflict.set_defaults(func=conflict_command)

    allocate = sub.add_parser("allocate-worktree", help="Plan an isolated worktree allocation.")
    allocate.add_argument("--repo", required=True)
    allocate.add_argument("--purpose", required=True)
    allocate.add_argument("--pr", type=int)
    allocate.add_argument("--branch")
    allocate.add_argument("--expected-sha")
    allocate.add_argument("--path")
    allocate.add_argument("--execute", action="store_true")
    allocate.set_defaults(func=allocate_command)

    validate = sub.add_parser("validate", help="Run deterministic self-validation fixtures.")
    validate.set_defaults(func=validate_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "backend_only", False):
        args.mode = "backend-only"
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        emit({"status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
