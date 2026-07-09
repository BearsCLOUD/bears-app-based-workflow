#!/usr/bin/env python3
"""Evaluate @Bears closeout and audit policy invariants."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/policy-invariants.v1.json"
RESULT_SCHEMA = PLUGIN_ROOT / "assets/schemas/policy-invariant-result.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/policy_invariants/good"
BAD = PLUGIN_ROOT / "tests/fixtures/policy_invariants/bad"
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")
NON_FINAL_CLASSIFICATIONS = {"partial", "manual_review", "blocked", "out_of_scope"}
SOLVED_CLASSIFICATIONS = {"closed", "superseded"}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import decision_ledger
from scripts import release_notes_gate


def utc_now() -> str:
    """Return an RFC3339 UTC timestamp for result packets."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_env() -> dict[str, str]:
    """Return an environment without inherited Git path overrides."""
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> Any:
    """Load a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(path: str) -> str:
    """Normalize a repository path for catalog matching."""
    return path.replace("\\", "/").strip().strip("/")


def matches(path: str, patterns: list[str]) -> bool:
    """Return true when path matches at least one glob pattern."""
    item = normalize(path)
    return any(fnmatch.fnmatch(item, pattern) for pattern in patterns)


def strings(value: Any) -> list[str]:
    """Flatten JSON scalar strings for forbidden-marker checks."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def forbidden_hits(value: Any, catalog: dict[str, Any]) -> list[str]:
    """Return forbidden markers found in a policy input packet."""
    text = "\n".join(strings(value)).casefold()
    hits: list[str] = []
    for marker in catalog.get("forbidden_output_markers", []):
        item = str(marker)
        if item.casefold() in text:
            hits.append(item)
    return sorted(set(hits))


def changed_files_from_git(range_spec: str | None, *, staged: bool = False) -> list[str]:
    """Return changed files from Git without mutating the repository."""
    if staged:
        command = ["git", "diff", "--cached", "--name-only"]
    elif range_spec:
        command = ["git", "diff", "--name-only", range_spec]
    else:
        raise ValueError("from-git or --staged is required")
    proc = subprocess.run(command, cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    if proc.returncode != 0:
        raise RuntimeError("git changed-file lookup failed")
    return sorted({normalize(line) for line in proc.stdout.splitlines() if line.strip()})


def behavior_files(paths: list[str], catalog: dict[str, Any]) -> list[str]:
    """Return changed files that require changelog or release-note coverage."""
    behavior = [str(item) for item in catalog.get("behavior_patterns", [])]
    non_behavior = [str(item) for item in catalog.get("non_behavior_patterns", [])]
    return [path for path in sorted({normalize(item) for item in paths}) if matches(path, behavior) and not matches(path, non_behavior)]


def decision_required_files(paths: list[str], catalog: dict[str, Any]) -> list[str]:
    """Return changed files that require an accepted decision-ledger record."""
    patterns = [str(item) for item in catalog.get("decision_required_patterns", [])]
    exempt = {normalize(str(item)) for item in catalog.get("decision_exempt_paths", [])}
    return [path for path in sorted({normalize(item) for item in paths}) if path not in exempt and matches(path, patterns)]


def check(check_id: str, ok: bool, message: str, details: list[str] | None = None) -> dict[str, Any]:
    """Build one invariant check result."""
    return {
        "id": check_id,
        "status": "pass" if ok else "fail",
        "severity": "blocking",
        "message": message,
        "details": sorted(details or []),
    }


def release_note_missing(packet: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    """Compute changed behavior files without release-note coverage."""
    explicit = packet.get("missing_changelog_files")
    if isinstance(explicit, list):
        return sorted(normalize(str(item)) for item in explicit)
    changed = [normalize(str(item)) for item in packet.get("changed_files", [])]
    required = behavior_files(changed, catalog)
    covered = {normalize(str(item)) for item in packet.get("release_note_covered_files", [])}
    if packet.get("release_note_status") == "pass":
        return []
    return [path for path in required if path not in covered]


def decision_missing(packet: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    """Compute governance files without accepted decision coverage."""
    explicit = packet.get("missing_decision_files")
    if isinstance(explicit, list):
        return sorted(normalize(str(item)) for item in explicit)
    changed = [normalize(str(item)) for item in packet.get("changed_files", [])]
    required = decision_required_files(changed, catalog)
    covered = {normalize(str(item)) for item in packet.get("decision_covered_files", [])}
    if packet.get("decision_status") == "pass":
        return []
    return [path for path in required if path not in covered]


def issue_open_violations(packet: dict[str, Any]) -> list[str]:
    """Return covered solved issues that still appear open."""
    violations: list[str] = []
    for item in packet.get("covered_issues", []):
        if not isinstance(item, dict):
            continue
        classification = str(item.get("classification", "")).lower()
        solved = bool(item.get("solved")) or classification in SOLVED_CLASSIFICATIONS
        state = str(item.get("github_state", item.get("state", ""))).upper()
        if solved and state == "OPEN":
            violations.append(str(item.get("number", item.get("id", "unknown"))))
    return sorted(set(violations))


def auto_close_violations(packet: dict[str, Any]) -> list[str]:
    """Return non-final covered issues that request auto close."""
    violations: list[str] = []
    for item in packet.get("covered_issues", []):
        if not isinstance(item, dict):
            continue
        classification = str(item.get("classification", "")).lower()
        requested = bool(item.get("auto_close_requested")) or bool(item.get("auto_close_allowed")) or str(item.get("close_action", "")).lower() == "close"
        if classification in NON_FINAL_CLASSIFICATIONS and requested:
            violations.append(str(item.get("number", item.get("id", "unknown"))))
    return sorted(set(violations))


def evaluate_packet(packet: dict[str, Any], *, input_ref: str) -> dict[str, Any]:
    """Evaluate every configured invariant against one packet."""
    catalog = load(CATALOG)
    open_issues = issue_open_violations(packet)
    auto_close = auto_close_violations(packet)
    missing_changelog = release_note_missing(packet, catalog)
    missing_decision = decision_missing(packet, catalog)
    raw_hits = forbidden_hits(packet, catalog)
    checks = [
        check("solved_covered_issue_not_open", not open_issues, "solved covered issues are not open", open_issues),
        check("non_final_issue_not_auto_closed", not auto_close, "non-final issues are not auto-closed", auto_close),
        check("behavior_change_has_changelog", not missing_changelog, "behavior changes have release-note coverage", missing_changelog),
        check("governance_change_has_decision", not missing_decision, "governance changes have accepted decision coverage", missing_decision),
        check("audit_artifacts_no_forbidden_raw_data", not raw_hits, "policy input contains no forbidden raw data markers", raw_hits),
    ]
    errors = [f"{item['id']}: {detail}" for item in checks if item["status"] == "fail" for detail in item["details"]]
    return {
        "schema": "bears-policy-invariant-result.v1",
        "status": "pass" if not errors else "fail",
        "evaluated_at": utc_now(),
        "input_ref": input_ref,
        "summary": {
            "passed": sum(1 for item in checks if item["status"] == "pass"),
            "failed": sum(1 for item in checks if item["status"] == "fail"),
            "changed_files": len(packet.get("changed_files", [])) if isinstance(packet.get("changed_files"), list) else 0,
            "covered_issues": len(packet.get("covered_issues", [])) if isinstance(packet.get("covered_issues"), list) else 0,
            "forbidden_marker_hits": len(raw_hits),
        },
        "checks": checks,
        "errors": errors,
    }


def packet_from_git(range_spec: str | None, *, staged: bool) -> dict[str, Any]:
    """Build a closeout invariant input packet from local Git and catalogs."""
    files = changed_files_from_git(range_spec, staged=staged)
    release_errors = release_notes_gate.validate_catalog() + release_notes_gate.validate_notes()
    release_errors.extend(release_notes_gate.check_paths(files))
    ledger = decision_ledger.load(decision_ledger.LEDGER)
    decision_errors = decision_ledger.validate_ledger(decision_ledger.LEDGER)
    decision_errors.extend(decision_ledger.missing_required_decisions(files, ledger))
    return {
        "schema": "bears-policy-invariant-input.v1",
        "source": "git_staged" if staged else "git_range",
        "range": "<staged>" if staged else range_spec,
        "changed_files": files,
        "missing_changelog_files": [item.removeprefix("missing release note coverage: ") for item in release_errors if item.startswith("missing release note coverage: ")],
        "missing_decision_files": [item.removeprefix("missing accepted decision for ") for item in decision_errors if item.startswith("missing accepted decision for ")],
        "release_note_status": "pass" if not release_errors else "fail",
        "decision_status": "pass" if not decision_errors else "fail",
        "covered_issues": [],
    }


def validate_catalog() -> list[str]:
    """Validate the policy catalog and command references."""
    errors: list[str] = []
    try:
        catalog = load(CATALOG)
    except Exception as exc:
        return [f"cannot read catalog: {exc}"]
    if catalog.get("schema") != "bears-policy-invariants.v1":
        errors.append("catalog schema must be bears-policy-invariants.v1")
    if catalog.get("component_issue") != "#460":
        errors.append("component_issue must be #460")
    required_commands = {
        "python3 scripts/policy_invariants.py validate",
        "python3 scripts/policy_invariants.py evaluate --input <packet.json> --json",
    }
    commands = set(catalog.get("commands", [])) if isinstance(catalog.get("commands"), list) else set()
    for command in sorted(required_commands - commands):
        errors.append(f"catalog missing command: {command}")
    invariant_ids = {item.get("id") for item in catalog.get("invariants", []) if isinstance(item, dict)}
    for invariant_id in {
        "solved_covered_issue_not_open",
        "non_final_issue_not_auto_closed",
        "behavior_change_has_changelog",
        "governance_change_has_decision",
        "audit_artifacts_no_forbidden_raw_data",
    }:
        if invariant_id not in invariant_ids:
            errors.append(f"catalog missing invariant: {invariant_id}")
    if not RESULT_SCHEMA.exists():
        errors.append("result schema missing")
    return errors


def validate_all() -> list[str]:
    """Validate catalog, result schema, and fixture expectations."""
    errors = validate_catalog()
    for path in sorted(GOOD.glob("*.json")):
        result = evaluate_packet(load(path), input_ref=path.relative_to(PLUGIN_ROOT).as_posix())
        errors.extend(validate_json_schema(result, RESULT_SCHEMA, path.name))
        if result.get("status") != "pass":
            errors.append(f"good fixture failed: {path.name}: {result.get('errors')}")
    for path in sorted(BAD.glob("*.json")):
        result = evaluate_packet(load(path), input_ref=path.relative_to(PLUGIN_ROOT).as_posix())
        errors.extend(validate_json_schema(result, RESULT_SCHEMA, path.name))
        if result.get("status") != "fail":
            errors.append(f"bad fixture unexpectedly passed: {path.name}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--input", required=True)
    evaluate.add_argument("--json", action="store_true")
    closeout = sub.add_parser("evaluate-closeout")
    closeout.add_argument("--from-git")
    closeout.add_argument("--staged", action="store_true")
    closeout.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the policy invariant CLI."""
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        packet = {"schema": "bears-policy-invariant-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0 if not errors else 1
    if args.command == "evaluate":
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = PLUGIN_ROOT / input_path
        try:
            packet = evaluate_packet(load(input_path), input_ref=input_path.relative_to(PLUGIN_ROOT).as_posix())
        except Exception as exc:
            packet = {"schema": "bears-policy-invariant-result.v1", "status": "fail", "evaluated_at": utc_now(), "input_ref": str(input_path), "summary": {"passed": 0, "failed": 1, "changed_files": 0, "covered_issues": 0, "forbidden_marker_hits": 0}, "checks": [], "errors": [str(exc)]}
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0 if packet.get("status") == "pass" else 1
    input_packet = packet_from_git(args.from_git, staged=bool(args.staged))
    packet = evaluate_packet(input_packet, input_ref=str(input_packet.get("range")))
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
