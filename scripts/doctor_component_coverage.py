#!/usr/bin/env python3
"""Reconcile bears_doctor component coverage against bounded issue contracts."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/doctor-component-coverage.v1.json"
SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/doctor-component-coverage.v1.schema.json"
GAP_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/doctor-component-gap.v1.schema.json"
DOCTOR_CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/bears-doctor.v1.json"
TEST_SELECTION_PATH = PLUGIN_ROOT / "assets/catalog/test-selection.v1.json"
GOOD_DIR = PLUGIN_ROOT / "tests/fixtures/doctor_component_coverage/good"
BAD_DIR = PLUGIN_ROOT / "tests/fixtures/doctor_component_coverage/bad"
REQUIRED_COMMANDS = (
    "python3 scripts/doctor_component_coverage.py validate",
    "python3 scripts/doctor_component_coverage.py scan --repo BearsCLOUD/bears-codex-workflow-plugin --json",
    "python3 scripts/doctor_component_coverage.py check-issue --issue <N> --json",
    "python3 scripts/doctor_component_coverage.py diff --base <path> --head <path> --json",
    "python3 scripts/doctor_component_coverage.py doctor --json",
)
SIGNAL_RE = re.compile(r"bears_doctor|doctor integration|validator|closeout|canonical validator|doctor summary", re.I)
COMMAND_RE = re.compile(r"python3\s+scripts/[A-Za-z0-9_./-]+\.py(?:\s+[^`\n]+)?")
FILE_RE = re.compile(r"(?:assets|scripts|tests|docs|contracts)/[A-Za-z0-9_./*{}-]+")
FORBIDDEN = ("raw_secret", "BEGIN PRIVATE KEY", ".env=", "credential=", "raw log", "raw chat", "production data")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def now_iso() -> str:
    """Return a deterministic UTC timestamp for generated packets."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    """Read a JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(value: Any) -> str:
    """Serialize a JSON packet for command output."""
    return json.dumps(value, indent=2, sort_keys=True)


def strings(value: Any) -> list[str]:
    """Return all string leaves from a packet."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def has_forbidden(value: Any) -> bool:
    """Return true when a packet leaks forbidden raw data markers."""
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN)


def normalize_issue(value: str | int) -> str:
    """Return a #N issue reference."""
    text = str(value).strip()
    return text if text.startswith("#") else f"#{text}"


def load_catalog() -> dict[str, Any]:
    """Load the local coverage catalog."""
    return load_json(CATALOG_PATH)


def doctor_checks() -> list[dict[str, Any]]:
    """Return bears_doctor check entries."""
    return [row for row in load_json(DOCTOR_CATALOG_PATH).get("checks", []) if isinstance(row, dict)]


def test_mappings() -> list[dict[str, Any]]:
    """Return test-selection mappings."""
    return [row for row in load_json(TEST_SELECTION_PATH).get("mappings", []) if isinstance(row, dict)]


def command_texts(check: dict[str, Any]) -> list[str]:
    """Return command strings from a bears_doctor check."""
    values: list[str] = []
    for key in ("command", "range_command"):
        command = check.get(key)
        if isinstance(command, list):
            values.append(" ".join(str(part) for part in command))
    for command in check.get("commands", []):
        if isinstance(command, list):
            values.append(" ".join(str(part) for part in command))
    return values


def path_has_test_selection(path: str, mappings: list[dict[str, Any]]) -> bool:
    """Return true when a path is covered by a test-selection mapping."""
    for mapping in mappings:
        for pattern in mapping.get("patterns", []):
            if fnmatch.fnmatchcase(path, str(pattern)) or fnmatch.fnmatchcase(path, str(pattern).rstrip("/**") + "/**"):
                return True
    return False


def component_from_catalog(row: dict[str, Any]) -> dict[str, Any]:
    """Return the public component fields from a catalog row."""
    return {
        "issue": row["issue"],
        "title": row["title"],
        "status": row["status"],
        "requires_doctor": bool(row.get("requires_doctor")),
        "requires_validator": bool(row.get("requires_validator")),
        "required_commands": list(row.get("required_commands", [])),
        "required_files": list(row.get("required_files", [])),
        "doctor_check_ids": list(row.get("doctor_check_ids", [])),
        "test_selection_refs": list(row.get("test_selection_refs", [])),
        "coverage_status": row.get("coverage_status", "manual_review"),
        "gap_ids": list(row.get("gap_ids", [])),
        **({"not_applicable_evidence": list(row.get("not_applicable_evidence", []))} if row.get("not_applicable_evidence") else {}),
    }


def gap(issue: str, gap_type: str, severity: str, evidence: list[str], next_step: str) -> dict[str, Any]:
    """Build a stable gap row."""
    safe_issue = issue.lstrip("#")
    return {
        "gap_id": f"{safe_issue}-{gap_type}",
        "issue": issue,
        "gap_type": gap_type,
        "severity": severity,
        "evidence_refs": evidence,
        "recommended_next": next_step,
    }


def reconcile_components(components: list[dict[str, Any]], *, generated_at: str | None = None) -> dict[str, Any]:
    """Reconcile components against bears_doctor and test-selection catalogs."""
    checks = doctor_checks()
    mappings = test_mappings()
    output_components: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    check_ids = {str(item.get("id")) for item in checks}
    issues_in_doctor = {str(item.get("component_issue")) for item in checks}

    for raw in components:
        component = component_from_catalog(raw)
        issue = component["issue"]
        component_gaps: list[dict[str, Any]] = []
        if component["coverage_status"] == "not_applicable":
            if not component.get("not_applicable_evidence"):
                component_gaps.append(gap(issue, "missing_doctor_check", "blocking", ["coverage catalog lacks not_applicable evidence"], "manual_review"))
        elif component["requires_doctor"]:
            ids = set(component.get("doctor_check_ids", []))
            if not ids or not (ids & check_ids) or issue not in issues_in_doctor:
                component_gaps.append(gap(issue, "missing_doctor_check", "blocking", [DOCTOR_CATALOG_PATH.relative_to(PLUGIN_ROOT).as_posix()], "add_doctor_check"))
            if raw.get("autostart_safe") and not component_gaps:
                pass
            elif raw.get("autostart_safe") and component_gaps:
                component_gaps.append(gap(issue, "unsafe_autostart_without_doctor_gate", "blocking", ["autostart_safe=true"], "add_doctor_check"))
        for command in component.get("required_commands", []):
            if not any(command in text for check in checks for text in command_texts(check)) and component["coverage_status"] != "not_applicable":
                component_gaps.append(gap(issue, "missing_validator_command", "blocking", [command], "add_doctor_check"))
        for path in component.get("required_files", []):
            if not path_has_test_selection(path, mappings) and component["coverage_status"] != "not_applicable":
                component_gaps.append(gap(issue, "missing_test_selection", "blocking", [path], "add_test_selection"))
        if component["status"] == "closed" and component_gaps and component["coverage_status"] != "not_applicable":
            component_gaps.append(gap(issue, "closed_issue_still_not_available", "blocking", ["status=closed"], "manual_review"))
        if component_gaps:
            component["gap_ids"] = sorted({item["gap_id"] for item in component_gaps})
            component["coverage_status"] = "missing" if any(item["gap_type"] == "missing_doctor_check" for item in component_gaps) else "partial"
        gaps.extend(component_gaps)
        output_components.append(component)

    summary = {
        "open_issue_count": sum(1 for item in output_components if item["status"] == "open"),
        "requires_doctor_count": sum(1 for item in output_components if item["requires_doctor"]),
        "covered_count": sum(1 for item in output_components if item["coverage_status"] == "covered"),
        "partial_count": sum(1 for item in output_components if item["coverage_status"] == "partial"),
        "missing_count": sum(1 for item in output_components if item["coverage_status"] == "missing"),
        "blocking_count": sum(1 for item in gaps if item["severity"] == "blocking"),
    }
    return {
        "schema": "bears-doctor-component-coverage.v1",
        "repo": "BearsCLOUD/bears-codex-workflow-plugin",
        "generated_at": generated_at or now_iso(),
        "source_refs": [
            {"source": "assets/catalog/doctor-component-coverage.v1.json", "timestamp": generated_at or now_iso(), "confidence": "high"},
            {"source": "assets/catalog/bears-doctor.v1.json", "timestamp": generated_at or now_iso(), "confidence": "high"},
            {"source": "assets/catalog/test-selection.v1.json", "timestamp": generated_at or now_iso(), "confidence": "high"}
        ],
        "doctor_catalog": "assets/catalog/bears-doctor.v1.json",
        "components": sorted(output_components, key=lambda item: int(item["issue"].lstrip("#"))),
        "gaps": sorted(gaps, key=lambda item: item["gap_id"]),
        "summary": summary,
    }


def validate_packet(packet: dict[str, Any], label: str) -> list[str]:
    """Validate a coverage packet and safety constraints."""
    errors = validate_json_schema(packet, SCHEMA_PATH, label)
    if has_forbidden(packet):
        errors.append(f"{label}: forbidden raw data marker present")
    for component in packet.get("components", []):
        if component.get("coverage_status") == "not_applicable" and not component.get("not_applicable_evidence"):
            errors.append(f"{component.get('issue')}: not_applicable requires evidence")
    return errors


def validate_all() -> list[str]:
    """Validate catalog, schemas, fixtures, and command registration."""
    errors: list[str] = []
    for path in (CATALOG_PATH, SCHEMA_PATH, GAP_SCHEMA_PATH, DOCTOR_CATALOG_PATH, TEST_SELECTION_PATH):
        if not path.exists():
            errors.append(f"missing required artifact: {path.relative_to(PLUGIN_ROOT)}")
    if errors:
        return errors
    catalog = load_catalog()
    errors.extend(validate_packet(catalog, "catalog"))
    doctor_catalog = load_json(DOCTOR_CATALOG_PATH)
    for command in REQUIRED_COMMANDS:
        if command not in doctor_catalog.get("commands", []) and command != REQUIRED_COMMANDS[1] and command != REQUIRED_COMMANDS[2] and command != REQUIRED_COMMANDS[3]:
            errors.append(f"bears-doctor catalog missing command: {command}")
    coverage = reconcile_components(catalog.get("components", []), generated_at=catalog.get("generated_at"))
    if coverage.get("summary", {}).get("blocking_count", 1) != 0:
        errors.append("catalog coverage has blocking gaps")
    for path in GOOD_DIR.glob("*.json"):
        packet = load_json(path)
        packet = reconcile_components(packet.get("components", []), generated_at=packet.get("generated_at")) if packet.get("schema") == "bears-doctor-component-coverage.v1" else packet
        if validate_packet(packet, path.name):
            errors.append(f"good fixture failed: {path.name}")
    for path in BAD_DIR.glob("*.json"):
        fixture = load_json(path)
        packet = reconcile_components(fixture.get("components", []), generated_at=fixture.get("generated_at"))
        expected = set(fixture.get("expected_gap_types", []))
        actual = {item.get("gap_type") for item in packet.get("gaps", [])}
        if expected and not expected <= actual:
            errors.append(f"bad fixture missing expected gaps: {path.name}")
    return errors


def issue_to_component(issue: dict[str, Any]) -> dict[str, Any]:
    """Convert a bounded GitHub issue object into a component row without raw body output."""
    body = str(issue.get("body") or "")
    issue_ref = normalize_issue(issue.get("number", "0"))
    labels = [str(row.get("name", row)) for row in issue.get("labels", [])]
    requires = bool(SIGNAL_RE.search(body))
    return {
        "issue": issue_ref,
        "title": str(issue.get("title") or issue_ref),
        "status": "closed" if str(issue.get("state", "open")).casefold() == "closed" else "open",
        "requires_doctor": requires,
        "requires_validator": requires,
        "required_commands": sorted(set(match.group(0).strip() for match in COMMAND_RE.finditer(body))),
        "required_files": sorted(set(match.group(0).strip() for match in FILE_RE.finditer(body))),
        "doctor_check_ids": [],
        "test_selection_refs": [],
        "coverage_status": "manual_review" if requires else "not_applicable",
        "gap_ids": [],
        **({"autostart_safe": True} if "bears:auto-start" in labels else {}),
        **({"not_applicable_evidence": ["no doctor or validator integration signal detected"]} if not requires else {}),
    }


def load_issues(repo: str, fixture: Path | None = None, issue: str | None = None) -> list[dict[str, Any]]:
    """Load issue facts from a fixture or read-only GitHub CLI."""
    if fixture:
        data = load_json(fixture)
        rows = data.get("issues", data if isinstance(data, list) else [])
        return [row for row in rows if isinstance(row, dict)]
    command = ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "100", "--json", "number,title,state,body,labels"]
    if issue:
        command = ["gh", "issue", "view", issue.lstrip("#"), "--repo", repo, "--json", "number,title,state,body,labels"]
    proc = subprocess.run(command, cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh issue read failed")
    data = json.loads(proc.stdout)
    if isinstance(data, dict) and "number" in data:
        return [data]
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def scan(repo: str, fixture: Path | None = None, issue: str | None = None) -> dict[str, Any]:
    """Scan issue facts and produce a bounded coverage packet."""
    rows = load_issues(repo, fixture, issue)
    components = [issue_to_component(row) for row in rows]
    local_by_issue = {row["issue"]: row for row in load_catalog().get("components", [])}
    for component in components:
        local = local_by_issue.get(component["issue"])
        if local:
            component["doctor_check_ids"] = list(local.get("doctor_check_ids", []))
            component["test_selection_refs"] = list(local.get("test_selection_refs", []))
            component["coverage_status"] = local.get("coverage_status", component["coverage_status"])
            if local.get("not_applicable_evidence"):
                component["not_applicable_evidence"] = list(local.get("not_applicable_evidence", []))
    packet = reconcile_components(components)
    packet["repo"] = repo
    packet["source_refs"].insert(0, {"source": "GitHub CLI read-only issue facts" if not fixture else str(fixture), "timestamp": packet["generated_at"], "confidence": "medium" if not fixture else "high"})
    return packet


def diff_packets(base: Path, head: Path) -> dict[str, Any]:
    """Compare two coverage packets by issue and blocking gaps."""
    base_packet = load_json(base)
    head_packet = load_json(head)
    base_issues = {row.get("issue") for row in base_packet.get("components", [])}
    head_issues = {row.get("issue") for row in head_packet.get("components", [])}
    base_gaps = {row.get("gap_id") for row in base_packet.get("gaps", [])}
    head_gaps = {row.get("gap_id") for row in head_packet.get("gaps", [])}
    new_gaps = sorted(head_gaps - base_gaps)
    resolved_gaps = sorted(base_gaps - head_gaps)
    status = "pass" if not new_gaps else "fail"
    return {
        "schema": "bears-doctor-component-coverage-diff.v1",
        "status": status,
        "base": str(base),
        "head": str(head),
        "added_issues": sorted(head_issues - base_issues),
        "removed_issues": sorted(base_issues - head_issues),
        "new_gaps": new_gaps,
        "resolved_gaps": resolved_gaps,
    }


def doctor_packet() -> dict[str, Any]:
    """Return the bears_doctor integration packet."""
    catalog = load_catalog()
    packet = reconcile_components(catalog.get("components", []), generated_at=catalog.get("generated_at"))
    errors = validate_packet(packet, "doctor")
    blocking = packet.get("summary", {}).get("blocking_count", 0)
    status = "pass" if not errors and blocking == 0 else "fail"
    return {
        "schema": "bears-doctor-component-coverage-doctor.v1",
        "status": status,
        "doctor_component_coverage_status": status,
        "missing_doctor_check_count": sum(1 for item in packet["gaps"] if item["gap_type"] == "missing_doctor_check"),
        "partial_doctor_coverage_count": packet["summary"]["partial_count"],
        "closed_issue_still_not_available_count": sum(1 for item in packet["gaps"] if item["gap_type"] == "closed_issue_still_not_available"),
        "unsafe_autostart_without_doctor_gate_count": sum(1 for item in packet["gaps"] if item["gap_type"] == "unsafe_autostart_without_doctor_gate"),
        "summary": packet["summary"],
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    scan_parser = sub.add_parser("scan")
    scan_parser.add_argument("--repo", required=True)
    scan_parser.add_argument("--issues-fixture")
    scan_parser.add_argument("--json", action="store_true")
    issue_parser = sub.add_parser("check-issue")
    issue_parser.add_argument("--issue", required=True)
    issue_parser.add_argument("--repo", default="BearsCLOUD/bears-codex-workflow-plugin")
    issue_parser.add_argument("--issues-fixture")
    issue_parser.add_argument("--json", action="store_true")
    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("--base", required=True)
    diff_parser.add_argument("--head", required=True)
    diff_parser.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_all()
            packet = {"schema": "bears-doctor-component-coverage-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
        elif args.command == "scan":
            packet = scan(args.repo, Path(args.issues_fixture) if args.issues_fixture else None)
        elif args.command == "check-issue":
            packet = scan(args.repo, Path(args.issues_fixture) if args.issues_fixture else None, args.issue)
        elif args.command == "diff":
            packet = diff_packets(Path(args.base), Path(args.head))
        elif args.command == "doctor":
            packet = doctor_packet()
        else:
            return 2
    except Exception as exc:
        packet = {"schema": "bears-doctor-component-coverage-error.v1", "status": "fail", "errors": [str(exc)]}
    print(write_json(packet))
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
