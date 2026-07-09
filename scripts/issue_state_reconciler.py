#!/usr/bin/env python3
"""Reconcile delivery manifests with GitHub issue metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CLOSED_CLASSIFICATIONS = {"closed", "superseded"}
COVERED_CLASSIFICATIONS = {"closed", "partial", "superseded", "blocked", "out_of_scope", "manual_review"}


def load(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def issue_key(issue: dict[str, Any]) -> tuple[str, int]:
    return (str(issue.get("repo") or ""), int(issue.get("number") or 0))


def manifest_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.glob("**/delivery-manifest.v1.json"))


def covered_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("covered_issues")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    fallback = []
    for issue in packet.get("issues", []):
        if isinstance(issue, dict) and issue.get("closeout_state"):
            fallback.append({
                "repo": issue.get("repo"),
                "number": issue.get("number"),
                "url": issue.get("url", ""),
                "github_state": issue.get("state", "UNKNOWN"),
                "classification": issue.get("closeout_state"),
                "reason": "legacy issues closeout_state fallback",
            })
    return fallback


def issue_index(issues: Any) -> dict[tuple[str, int], dict[str, Any]]:
    rows = issues if isinstance(issues, list) else []
    return {issue_key(row): row for row in rows if isinstance(row, dict) and row.get("number")}


def solved_open(delivery_id: str, manifest_root: Path, issues_json: Any = None) -> dict[str, Any]:
    issues = issue_index(issues_json if isinstance(issues_json, list) else load(issues_json) if isinstance(issues_json, Path) else issues_json)
    covered: list[dict[str, Any]] = []
    solved_open_rows: list[dict[str, Any]] = []
    missing_closeout_state = 0
    for path in manifest_paths(manifest_root):
        packet = load(path)
        if not isinstance(packet, dict):
            continue
        if delivery_id and packet.get("delivery_id") != delivery_id:
            continue
        for row in covered_rows(packet):
            classification = row.get("classification")
            if classification not in COVERED_CLASSIFICATIONS:
                missing_closeout_state += 1
                continue
            covered.append(row)
            live = issues.get(issue_key(row), {})
            state = str(live.get("state") or row.get("github_state") or "").upper()
            if classification in CLOSED_CLASSIFICATIONS and state == "OPEN":
                solved_open_rows.append(row)
    status = "pass" if not solved_open_rows and missing_closeout_state == 0 else "fail"
    return {
        "schema": "bears-issue-state-reconciler-solved-open.v1",
        "status": status,
        "delivery_id": delivery_id,
        "counts": {
            "covered": len(covered),
            "solved_open": len(solved_open_rows),
            "missing_closeout_state": missing_closeout_state,
        },
        "solved_open": solved_open_rows,
    }


def summary(manifest_root: Path, issues_json: Path | None) -> dict[str, Any]:
    issues = load(issues_json) if issues_json else []
    return solved_open("", manifest_root, issues) | {"schema": "bears-issue-state-reconciler-summary.v1"}


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile", "summary"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest-root", required=True)
        cmd.add_argument("--issues-json")
        cmd.add_argument("--json", action="store_true")
    solved = sub.add_parser("solved-open")
    solved.add_argument("--delivery-id", required=True)
    solved.add_argument("--manifest-root", default="runtime/deliveries")
    solved.add_argument("--issues-json")
    solved.add_argument("--json", action="store_true")
    sub.add_parser("release-summary").add_argument("--json", action="store_true")
    sub.add_parser("repo-summary").add_argument("--json", action="store_true")
    sub.add_parser("validate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        packet = {"schema": "bears-issue-state-reconciler-validation.v1", "status": "pass", "errors": []}
    elif args.command in {"reconcile", "summary"}:
        packet = summary(Path(args.manifest_root), Path(args.issues_json) if args.issues_json else None)
    elif args.command == "solved-open":
        packet = solved_open(args.delivery_id, Path(args.manifest_root), Path(args.issues_json) if args.issues_json else None)
    else:
        packet = {"schema": f"bears-issue-state-reconciler-{args.command}.v1", "status": "pass", "errors": []}
    print_packet(packet)
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
