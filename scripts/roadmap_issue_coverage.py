#!/usr/bin/env python3
"""Validate local roadmap issue coverage and priority freshness gates.

Entrypoints: validate, check-roadmap, check-priority, and doctor. The module
reads only repo catalogs or caller-provided metadata fixtures. It never needs
raw issue bodies, raw logs, prompts, secrets, or production data.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_CATALOG = PLUGIN_ROOT / "assets/catalog/workflow-roadmap.v1.json"
PRIORITY_CATALOG = PLUGIN_ROOT / "assets/catalog/issue-execution-priority.v1.json"
COVERAGE_CATALOG = PLUGIN_ROOT / "assets/catalog/roadmap-issue-coverage.v1.json"
PRIORITY_FRESHNESS_CATALOG = PLUGIN_ROOT / "assets/catalog/issue-priority-freshness.v1.json"
COVERAGE_SCHEMA = PLUGIN_ROOT / "assets/schemas/roadmap-issue-coverage.v1.schema.json"
PRIORITY_SCHEMA = PLUGIN_ROOT / "assets/schemas/issue-priority-freshness.v1.schema.json"

REQUIRED_COMMANDS = {
    "python3 scripts/roadmap_issue_coverage.py validate --json",
    "python3 scripts/roadmap_issue_coverage.py check-roadmap --json",
    "python3 scripts/roadmap_issue_coverage.py check-priority --json",
    "python3 scripts/roadmap_issue_coverage.py doctor --json",
}
FORBIDDEN_ISSUE_FIELDS = {
    "body",
    "bodytext",
    "body_text",
    "raw_body",
    "rawbody",
    "raw_log",
    "raw_logs",
    "prompt",
    "secret",
    "token",
    "credential",
    "private_key",
}
FORBIDDEN_VALUE_MARKERS = (
    "BEGIN PRIVATE KEY",
    "raw_secret",
    "authorization:",
    "bearer ",
    "password=",
    ".env=",
)
ISSUE_REF_RE = re.compile(r"^#[0-9]+$")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> Any:
    """Read JSON from a repo-local or caller-provided path."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def rel(path: Path) -> str:
    """Render a path relative to the plugin root when possible."""
    try:
        return str(path.relative_to(PLUGIN_ROOT))
    except ValueError:
        return str(path)


def path_from_arg(value: str | None, default: Path) -> Path:
    """Resolve a CLI path without requiring it to exist."""
    if not value:
        return default
    candidate = Path(value)
    return candidate if candidate.is_absolute() else PLUGIN_ROOT / candidate


def strings(value: Any) -> list[str]:
    """Collect string leaves for forbidden marker checks."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for row in value for item in strings(row)]
    if isinstance(value, dict):
        return [item for row in value.values() for item in strings(row)]
    return []


def has_forbidden_value(value: Any) -> bool:
    """Return true when metadata carries raw secret-like text."""
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN_VALUE_MARKERS)


def issue_ref(number: int) -> str:
    """Render a GitHub issue reference."""
    return f"#{number}"


def normalize_labels(raw: Any) -> list[str]:
    """Normalize labels from strings or GitHub metadata objects."""
    labels: list[str] = []
    if not isinstance(raw, list):
        return labels
    for item in raw:
        if isinstance(item, str) and item:
            labels.append(item)
        elif isinstance(item, dict) and item.get("name"):
            labels.append(str(item["name"]))
    return sorted(set(labels))


def derive_priority(issue: dict[str, Any]) -> str:
    """Derive issue priority from explicit metadata, labels, or title."""
    explicit = str(issue.get("priority") or "").upper()
    if explicit in {"P0", "P1", "P2"}:
        return explicit
    text = " ".join([str(issue.get("title") or ""), *normalize_labels(issue.get("labels"))]).upper()
    for priority in ("P0", "P1", "P2"):
        if re.search(rf"(^|[^A-Z0-9]){priority}([^A-Z0-9]|$)", text):
            return priority
    return "unknown"


def normalize_issue(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize one metadata-only issue row and return validation errors."""
    errors: list[str] = []
    forbidden_keys = sorted(set(row) & FORBIDDEN_ISSUE_FIELDS)
    if forbidden_keys:
        errors.append(f"forbidden issue metadata fields: {', '.join(forbidden_keys)}")
    if has_forbidden_value(row):
        errors.append("forbidden raw value marker present")
    try:
        number = int(row.get("number"))
    except (TypeError, ValueError):
        number = 0
        errors.append("issue number must be an integer")
    ref = str(row.get("issue_ref") or issue_ref(number))
    if not ISSUE_REF_RE.match(ref):
        errors.append(f"invalid issue_ref: {ref}")
    state = str(row.get("state") or "OPEN").upper()
    if state not in {"OPEN", "CLOSED"}:
        errors.append(f"invalid issue state: {state}")
    title = str(row.get("title") or "").strip()
    if not title:
        errors.append(f"{ref}: title is required")
    updated_at = str(row.get("updated_at") or row.get("updatedAt") or "").strip()
    if not updated_at:
        errors.append(f"{ref}: updated_at is required")
    url = str(row.get("url") or row.get("html_url") or "").strip()
    if not url:
        errors.append(f"{ref}: url is required")
    labels = normalize_labels(row.get("labels"))
    normalized = {
        "number": number,
        "issue_ref": ref,
        "title": title,
        "state": state,
        "url": url,
        "labels": labels,
        "updated_at": updated_at,
        "priority": derive_priority({**row, "labels": labels}),
    }
    return normalized, errors


def normalize_issues(rows: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize a list or packet containing metadata-only issue rows."""
    if isinstance(rows, dict):
        rows = rows.get("issues") or rows.get("tracked_open_issues") or []
    if not isinstance(rows, list):
        return [], ["issue metadata must be a list or contain issues"]
    issues: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[int] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"issues[{index}] must be an object")
            continue
        issue, row_errors = normalize_issue(row)
        errors.extend(f"issues[{index}]: {item}" for item in row_errors)
        if issue["number"] in seen:
            errors.append(f"issues[{index}]: duplicate issue number {issue['number']}")
        seen.add(issue["number"])
        issues.append(issue)
    issues.sort(key=lambda item: item["number"])
    return issues, errors


def catalog_issues(catalog_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read tracked issue metadata from a freshness catalog."""
    catalog = load(catalog_path)
    return normalize_issues(catalog.get("tracked_open_issues", []))


def issue_metadata_from_arg(path_value: str | None, catalog_path: Path) -> tuple[list[dict[str, Any]], list[str], str]:
    """Read issue metadata from a fixture path or a catalog default."""
    if path_value:
        path = path_from_arg(path_value, PLUGIN_ROOT)
        issues, errors = normalize_issues(load(path))
        return issues, errors, rel(path)
    issues, errors = catalog_issues(catalog_path)
    return issues, errors, rel(catalog_path)


def open_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return open issues only."""
    return [issue for issue in issues if issue.get("state") == "OPEN"]


def issue_exemptions(catalog: dict[str, Any]) -> set[str]:
    """Return issue refs exempted from the gate."""
    refs: set[str] = set()
    for row in catalog.get("exemptions", []) or []:
        if isinstance(row, dict) and isinstance(row.get("issue_ref"), str):
            refs.add(row["issue_ref"])
    return refs


def roadmap_nodes_by_issue(roadmap: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Index workflow-roadmap nodes by issue ref."""
    index: dict[str, list[dict[str, Any]]] = {}
    for node in roadmap.get("nodes", []) or []:
        if isinstance(node, dict):
            issue = str(node.get("issue") or "")
            if issue:
                index.setdefault(issue, []).append(node)
    return index


def priority_issue_numbers(priority: dict[str, Any]) -> set[int]:
    """Collect issues represented in the priority wave catalog."""
    numbers: set[int] = set()
    for wave in priority.get("waves", []) or []:
        if not isinstance(wave, dict):
            continue
        for value in wave.get("issues", []) or []:
            try:
                numbers.add(int(value))
            except (TypeError, ValueError):
                continue
    return numbers


def check_roadmap(
    *,
    issues: list[dict[str, Any]],
    issue_errors: list[str],
    issue_source: str,
    roadmap_path: Path = ROADMAP_CATALOG,
    catalog_path: Path = COVERAGE_CATALOG,
) -> dict[str, Any]:
    """Compare open issue metadata with the workflow-roadmap catalog."""
    catalog = load(catalog_path)
    roadmap = load(roadmap_path)
    policy = catalog.get("policy", {}) if isinstance(catalog.get("policy"), dict) else {}
    covered_states = set(policy.get("covered_states") or [])
    exemptions = issue_exemptions(catalog)
    node_index = roadmap_nodes_by_issue(roadmap)
    missing: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for issue in open_issues(issues):
        ref = str(issue["issue_ref"])
        if ref in exemptions:
            continue
        nodes = node_index.get(ref, [])
        node_ids = [str(node.get("node_id")) for node in nodes]
        node_states = [str(node.get("state")) for node in nodes]
        if not nodes:
            missing.append({"issue_ref": ref, "number": issue["number"], "reason": "missing_roadmap_node"})
            continue
        if covered_states and not any(state in covered_states for state in node_states):
            stale.append({"issue_ref": ref, "number": issue["number"], "node_ids": node_ids, "node_states": node_states, "reason": "node_state_not_covered"})
            continue
        covered.append({"issue_ref": ref, "number": issue["number"], "node_ids": node_ids, "node_states": node_states})
    errors = list(issue_errors)
    if missing:
        errors.append("open issues missing workflow-roadmap nodes")
    if stale:
        errors.append("open issues have only uncovered roadmap node states")
    return {
        "schema": "bears-roadmap-issue-coverage-result.v1",
        "version": "1",
        "status": "pass" if not errors else "fail",
        "repo": catalog.get("repo"),
        "issue_source": issue_source,
        "roadmap_catalog": rel(roadmap_path),
        "policy_status": policy.get("missing_issue_status", "manual_review"),
        "counts": {
            "open_issues": len(open_issues(issues)),
            "covered": len(covered),
            "missing": len(missing),
            "stale": len(stale),
            "exemptions": len(exemptions),
        },
        "covered_issues": covered,
        "missing_roadmap_issues": missing,
        "stale_roadmap_issues": stale,
        "errors": errors,
    }


def check_priority(
    *,
    issues: list[dict[str, Any]],
    issue_errors: list[str],
    issue_source: str,
    priority_path: Path = PRIORITY_CATALOG,
    catalog_path: Path = PRIORITY_FRESHNESS_CATALOG,
) -> dict[str, Any]:
    """Compare open priority issue metadata with the priority wave catalog."""
    catalog = load(catalog_path)
    priority = load(priority_path)
    policy = catalog.get("policy", {}) if isinstance(catalog.get("policy"), dict) else {}
    required_priorities = set(policy.get("required_priorities") or ["P0"])
    exemptions = issue_exemptions(catalog)
    assigned = priority_issue_numbers(priority)
    missing: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    for issue in open_issues(issues):
        ref = str(issue["issue_ref"])
        if ref in exemptions or issue.get("priority") not in required_priorities:
            continue
        if int(issue["number"]) in assigned:
            covered.append({"issue_ref": ref, "number": issue["number"], "priority": issue["priority"]})
        else:
            missing.append({"issue_ref": ref, "number": issue["number"], "priority": issue["priority"], "reason": "missing_priority_wave"})
    errors = list(issue_errors)
    if missing:
        errors.append("open priority issues missing issue-execution-priority waves")
    return {
        "schema": "bears-issue-priority-freshness-result.v1",
        "version": "1",
        "status": "pass" if not errors else "fail",
        "repo": catalog.get("repo"),
        "issue_source": issue_source,
        "priority_catalog": rel(priority_path),
        "policy_status": policy.get("missing_priority_status", "manual_review"),
        "required_priorities": sorted(required_priorities),
        "counts": {
            "open_issues": len(open_issues(issues)),
            "covered_priority_issues": len(covered),
            "missing_priority_issues": len(missing),
            "exemptions": len(exemptions),
        },
        "covered_priority_issues": covered,
        "missing_priority_issues": missing,
        "errors": errors,
    }


def validate_catalog(catalog_path: Path, schema_path: Path, label: str) -> list[str]:
    """Validate a freshness catalog against its JSON Schema and policy rules."""
    errors: list[str] = []
    if not catalog_path.exists():
        return [f"{label}: catalog missing: {rel(catalog_path)}"]
    if not schema_path.exists():
        return [f"{label}: schema missing: {rel(schema_path)}"]
    catalog = load(catalog_path)
    errors.extend(validate_json_schema(catalog, schema_path, label))
    commands = set(catalog.get("commands", []) or [])
    missing_commands = sorted(REQUIRED_COMMANDS - commands)
    errors.extend(f"{label}: catalog missing command: {command}" for command in missing_commands)
    for key in ("roadmap_catalog", "priority_catalog"):
        source_path = catalog.get("source_truth", {}).get(key) if isinstance(catalog.get("source_truth"), dict) else None
        if not isinstance(source_path, str) or not (PLUGIN_ROOT / source_path).exists():
            errors.append(f"{label}: source_truth missing file for {key}: {source_path}")
    policy = catalog.get("policy", {}) if isinstance(catalog.get("policy"), dict) else {}
    if policy.get("issue_metadata_only") is not True:
        errors.append(f"{label}: issue_metadata_only must be true")
    if policy.get("raw_issue_bodies_allowed") is not False:
        errors.append(f"{label}: raw_issue_bodies_allowed must be false")
    if policy.get("raw_logs_allowed") is not False:
        errors.append(f"{label}: raw_logs_allowed must be false")
    _, issue_errors = normalize_issues(catalog.get("tracked_open_issues", []))
    errors.extend(f"{label}: {item}" for item in issue_errors)
    for fixture in (catalog.get("fixtures", {}) or {}).values():
        if isinstance(fixture, str) and not (PLUGIN_ROOT / fixture).exists():
            errors.append(f"{label}: fixture missing: {fixture}")
    return errors


def validate_fixtures() -> list[str]:
    """Validate pass/fail behavior using local metadata fixtures."""
    errors: list[str] = []
    catalog = load(COVERAGE_CATALOG)
    fixtures = catalog.get("fixtures", {}) if isinstance(catalog.get("fixtures"), dict) else {}
    good_issues, good_errors, good_source = issue_metadata_from_arg(fixtures.get("good_issue_metadata"), COVERAGE_CATALOG)
    good_roadmap = path_from_arg(fixtures.get("good_roadmap"), ROADMAP_CATALOG)
    good_priority = path_from_arg(fixtures.get("good_priority"), PRIORITY_CATALOG)
    roadmap_packet = check_roadmap(issues=good_issues, issue_errors=good_errors, issue_source=good_source, roadmap_path=good_roadmap)
    priority_packet = check_priority(issues=good_issues, issue_errors=good_errors, issue_source=good_source, priority_path=good_priority)
    if roadmap_packet["status"] != "pass":
        errors.append("good roadmap fixture failed")
    if priority_packet["status"] != "pass":
        errors.append("good priority fixture failed")
    bad_issues, bad_errors, bad_source = issue_metadata_from_arg(fixtures.get("bad_issue_metadata"), COVERAGE_CATALOG)
    bad_roadmap_packet = check_roadmap(issues=bad_issues, issue_errors=bad_errors, issue_source=bad_source, roadmap_path=good_roadmap)
    bad_priority_packet = check_priority(issues=bad_issues, issue_errors=bad_errors, issue_source=bad_source, priority_path=good_priority)
    if bad_roadmap_packet["status"] == "pass":
        errors.append("bad roadmap fixture unexpectedly passed")
    if bad_priority_packet["status"] == "pass":
        errors.append("bad priority fixture unexpectedly passed")
    return errors


def validate_all() -> list[str]:
    """Validate schemas, catalogs, commands, source paths, and fixtures."""
    errors: list[str] = []
    errors.extend(validate_catalog(COVERAGE_CATALOG, COVERAGE_SCHEMA, "roadmap-issue-coverage"))
    errors.extend(validate_catalog(PRIORITY_FRESHNESS_CATALOG, PRIORITY_SCHEMA, "issue-priority-freshness"))
    if not errors:
        errors.extend(validate_fixtures())
    return errors


def doctor_packet(issues_path: str | None, roadmap_path: Path, priority_path: Path) -> dict[str, Any]:
    """Run both freshness gates and return one local doctor packet."""
    coverage_issues, coverage_errors, coverage_source = issue_metadata_from_arg(issues_path, COVERAGE_CATALOG)
    priority_issues, priority_errors, priority_source = issue_metadata_from_arg(issues_path, PRIORITY_FRESHNESS_CATALOG)
    roadmap_packet = check_roadmap(
        issues=coverage_issues,
        issue_errors=coverage_errors,
        issue_source=coverage_source,
        roadmap_path=roadmap_path,
    )
    priority_packet = check_priority(
        issues=priority_issues,
        issue_errors=priority_errors,
        issue_source=priority_source,
        priority_path=priority_path,
    )
    errors = []
    if roadmap_packet["status"] != "pass":
        errors.append("roadmap issue coverage failed")
    if priority_packet["status"] != "pass":
        errors.append("issue priority freshness failed")
    return {
        "schema": "bears-roadmap-issue-freshness-doctor.v1",
        "version": "1",
        "status": "pass" if not errors else "fail",
        "checks": [roadmap_packet, priority_packet],
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    roadmap = sub.add_parser("check-roadmap")
    roadmap.add_argument("--issues-json")
    roadmap.add_argument("--roadmap", default=str(ROADMAP_CATALOG))
    roadmap.add_argument("--json", action="store_true")
    priority = sub.add_parser("check-priority")
    priority.add_argument("--issues-json")
    priority.add_argument("--priority", default=str(PRIORITY_CATALOG))
    priority.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--issues-json")
    doctor.add_argument("--roadmap", default=str(ROADMAP_CATALOG))
    doctor.add_argument("--priority", default=str(PRIORITY_CATALOG))
    doctor.add_argument("--json", action="store_true")
    return parser


def emit(packet: dict[str, Any], as_json: bool) -> None:
    """Print a packet as JSON or compact status text."""
    if as_json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(packet.get("status", "unknown"))


def main(argv: list[str] | None = None) -> int:
    """Run the roadmap issue coverage CLI."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_all()
            packet = {
                "schema": "bears-roadmap-issue-coverage-validation.v1",
                "version": "1",
                "status": "pass" if not errors else "fail",
                "errors": errors,
            }
        elif args.command == "check-roadmap":
            issues, issue_errors, source = issue_metadata_from_arg(args.issues_json, COVERAGE_CATALOG)
            packet = check_roadmap(
                issues=issues,
                issue_errors=issue_errors,
                issue_source=source,
                roadmap_path=path_from_arg(args.roadmap, ROADMAP_CATALOG),
            )
        elif args.command == "check-priority":
            issues, issue_errors, source = issue_metadata_from_arg(args.issues_json, PRIORITY_FRESHNESS_CATALOG)
            packet = check_priority(
                issues=issues,
                issue_errors=issue_errors,
                issue_source=source,
                priority_path=path_from_arg(args.priority, PRIORITY_CATALOG),
            )
        else:
            packet = doctor_packet(
                args.issues_json,
                path_from_arg(args.roadmap, ROADMAP_CATALOG),
                path_from_arg(args.priority, PRIORITY_CATALOG),
            )
    except Exception as exc:  # pragma: no cover - CLI safety net.
        packet = {
            "schema": "bears-roadmap-issue-coverage-error.v1",
            "version": "1",
            "status": "fail",
            "error": str(exc),
        }
    emit(packet, bool(getattr(args, "json", False)))
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
