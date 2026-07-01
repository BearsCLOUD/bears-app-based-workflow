#!/usr/bin/env python3
"""Validate commit-bound @bears closeout metadata and runtime evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/commit-closeout.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/commit-closeout.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/commit_closeout/good/minimal.json"
BAD = PLUGIN_ROOT / "tests/fixtures/commit_closeout/bad/missing-runtime-proof.json"
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")
DEFAULT_FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "raw log", "raw chat", "raw vpn config", "production data")
METADATA_RE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):\s*(.+?)\s*$")
ISSUE_RE = re.compile(r"#[0-9]+")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_output(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20, env=clean_env())
    except subprocess.TimeoutExpired:
        return 124, ""
    return proc.returncode, proc.stdout.strip()


def forbidden_markers() -> tuple[str, ...]:
    try:
        markers = load(CATALOG).get("forbidden_output_markers", [])
    except Exception:
        markers = []
    return tuple(str(item) for item in markers) or DEFAULT_FORBIDDEN


def has_forbidden(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True).casefold()
    return any(marker.casefold() in text for marker in forbidden_markers())


def validate_catalog(path: Path = CATALOG, label: str = "commit-closeout") -> list[str]:
    errors = validate_json_schema(load(path), SCHEMA, label)
    catalog = load(path)
    required_commands = {
        "validate",
        "check-message --commit <ref> --json",
        "validate-runtime --commit <sha> --json",
        "emit-summary --commit <sha> --from-git <range> --json",
    }
    missing = sorted(required_commands - set(catalog.get("commands", [])))
    errors.extend(f"missing command: {item}" for item in missing)
    required_metadata = set(catalog.get("required_metadata", []))
    for key in ("Issue", "Delivery-Id", "Scope", "Affected-Range", "Evidence", "Changelog", "Blockers"):
        if key not in required_metadata:
            errors.append(f"missing required metadata key: {key}")
    canonical_delivery_id = catalog.get("canonical_delivery_id")
    if canonical_delivery_id != "bears-governance-kernel-v1":
        errors.append("canonical_delivery_id must be bears-governance-kernel-v1")
    if catalog.get("changelog_gate", {}).get("delivery_id_required") != canonical_delivery_id:
        errors.append("changelog gate must require the canonical delivery id")
    if catalog.get("doctor_integration", {}).get("delivery_id_field") != "delivery_id":
        errors.append("doctor integration must expose delivery_id")
    if "<commit_sha>" not in "\n".join(catalog.get("runtime_evidence_templates", [])):
        errors.append("runtime evidence templates must use <commit_sha>")
    visible_catalog = {key: value for key, value in catalog.items() if key != "forbidden_output_markers"}
    if has_forbidden(visible_catalog):
        errors.append("catalog contains forbidden raw data marker")
    return errors


def validate_all() -> list[str]:
    errors = validate_catalog(CATALOG, "commit-closeout")
    good_errors = validate_catalog(GOOD, "good")
    errors.extend(f"good fixture failed: {item}" for item in good_errors)
    if not validate_catalog(BAD, "bad"):
        errors.append("bad fixture unexpectedly passed")
    return errors


def commit_message(commit: str) -> tuple[int, str]:
    return git_output(["show", "-s", "--format=%B", commit])


def parse_metadata(message: str) -> dict[str, list[str]]:
    metadata: dict[str, list[str]] = {}
    for line in message.splitlines():
        match = METADATA_RE.match(line.strip())
        if not match:
            continue
        key, value = match.groups()
        metadata.setdefault(key, []).append(value)
    return metadata


def inspect_commit_message(commit: str) -> dict[str, Any]:
    code, message = commit_message(commit)
    errors: list[str] = []
    if code != 0:
        return {"status": "fail", "errors": ["commit message unavailable"], "metadata": {}, "issue_refs": []}
    metadata = parse_metadata(message)
    catalog = load(CATALOG)
    for key in catalog.get("required_metadata", []):
        if not metadata.get(key):
            errors.append(f"missing metadata: {key}")
    issue_text = " ".join(metadata.get("Issue", []))
    issue_refs = sorted(set(ISSUE_RE.findall(issue_text)))
    if not issue_refs:
        errors.append("Issue metadata must include at least one GitHub issue reference")
    evidence_values = metadata.get("Evidence", [])
    if not any("runtime/local-commit-validation/<commit_sha>.json" in item for item in evidence_values):
        errors.append("Evidence metadata must include runtime/local-commit-validation/<commit_sha>.json")
    if not any("runtime/bears-doctor/<commit_sha>.closeout.json" in item for item in evidence_values):
        errors.append("Evidence metadata must include runtime/bears-doctor/<commit_sha>.closeout.json")
    delivery_values = metadata.get("Delivery-Id", [])
    canonical_delivery_id = str(catalog.get("canonical_delivery_id", "bears-governance-kernel-v1"))
    if delivery_values[-1:] != [canonical_delivery_id]:
        errors.append(f"Delivery-Id metadata must equal {canonical_delivery_id}")
    changelog_values = metadata.get("Changelog", [])
    required_changelog = catalog.get("changelog_gate", {}).get("required_metadata_value", "release-note-gate:#384")
    if not any(required_changelog in item for item in changelog_values):
        errors.append(f"Changelog metadata must link {required_changelog}")
    if not any(canonical_delivery_id in item for item in changelog_values):
        errors.append(f"Changelog metadata must include delivery id {canonical_delivery_id}")
    if has_forbidden(metadata):
        errors.append("commit metadata contains forbidden raw data marker")
    return {"status": "pass" if not errors else "fail", "errors": errors, "metadata": metadata, "issue_refs": issue_refs}


def resolve_template(path: str, commit_sha: str | None) -> str:
    return path.replace("<commit_sha>", commit_sha or "<commit_sha>")


def expected_evidence_paths(commit_sha: str | None) -> list[str]:
    return [resolve_template(str(item), commit_sha) for item in load(CATALOG).get("runtime_evidence_templates", [])]


def tracked_runtime_files() -> list[str]:
    code, output = git_output(["ls-files", "runtime", ".pytest_cache", ".ruff_cache"])
    if code != 0:
        return ["tracked runtime lookup failed"]
    return [line for line in output.splitlines() if line.strip()]


def local_validation_proof(commit_sha: str | None) -> dict[str, Any]:
    if not commit_sha:
        return {"status": "fail", "errors": ["commit sha unavailable"], "path": "runtime/local-commit-validation/<commit_sha>.json"}
    rel = f"runtime/local-commit-validation/{commit_sha}.json"
    path = PLUGIN_ROOT / rel
    if not path.exists():
        return {"status": "fail", "errors": ["exact local commit proof missing"], "path": rel}
    try:
        packet = load(path)
    except Exception:
        return {"status": "fail", "errors": ["exact local commit proof unreadable"], "path": rel}
    errors: list[str] = []
    if packet.get("schema") != "bears-local-commit-validation.v1":
        errors.append("local commit proof schema mismatch")
    if packet.get("commit_sha") != commit_sha:
        errors.append("local commit proof sha mismatch")
    if packet.get("status") != "pass":
        errors.append("local commit proof is not pass")
    plan = packet.get("validation_plan")
    if not isinstance(plan, dict) or plan.get("status") != "pass":
        errors.append("local commit validation plan missing or failed")
    elif plan.get("uncovered_changed_files"):
        errors.append("local commit validation plan has uncovered files")
    return {"status": "pass" if not errors else "fail", "errors": errors, "path": rel, "packet": packet}


def closeout_summary(commit_sha: str | None, range_spec: str, *, doctor_result: str = "pending") -> dict[str, Any]:
    message = inspect_commit_message(commit_sha or "HEAD") if commit_sha else {"status": "fail", "errors": ["commit sha unavailable"], "metadata": {}, "issue_refs": []}
    metadata = message.get("metadata", {})
    proof = local_validation_proof(commit_sha)
    tracked = tracked_runtime_files()
    blockers = []
    blockers.extend(message.get("errors", []))
    blockers.extend(proof.get("errors", []))
    declared_blockers = [item for item in metadata.get("Blockers", []) if item.casefold() not in {"none", "no", "n/a"}]
    blockers.extend(declared_blockers)
    proof_packet = proof.get("packet") if isinstance(proof.get("packet"), dict) else {}
    requires_full_suite = bool(proof_packet.get("requires_full_suite"))
    if proof.get("status") == "pass" and not requires_full_suite:
        debt_status = "none"
    elif proof.get("status") == "pass":
        debt_status = "full_suite_advisory_deferred"
    else:
        debt_status = "local_commit_validation_missing_or_failed"
    cleanup_status = "no_tracked_runtime_files" if not tracked else "tracked_runtime_files_present"
    delivery_values = metadata.get("Delivery-Id", [])
    canonical_delivery_id = str(load(CATALOG).get("canonical_delivery_id", "bears-governance-kernel-v1"))
    delivery_id = delivery_values[-1] if delivery_values else "<missing>"
    changelog_values = metadata.get("Changelog", [])
    changelog_status = "linked" if any("#384" in item and canonical_delivery_id in item for item in changelog_values) else "missing"
    return {
        "final_sha": commit_sha or "<unavailable>",
        "delivery_id": delivery_id,
        "issue_refs": message.get("issue_refs", []),
        "scope": (metadata.get("Scope") or ["<missing>"])[-1],
        "affected_range": (metadata.get("Affected-Range") or [range_spec])[-1],
        "expected_evidence_paths": expected_evidence_paths(commit_sha),
        "changelog": {"status": changelog_status, "reference": (changelog_values or ["<missing>"])[-1], "delivery_id": delivery_id},
        "known_blockers": blockers,
        "validation_result": str(proof.get("status", "fail")),
        "doctor_result": doctor_result,
        "debt_status": debt_status,
        "cleanup_status": cleanup_status,
        "final_report_policy": load(CATALOG).get("final_report_policy", "closeout_summary owns detailed final reporting"),
    }


def check_commit_closeout(commit_sha: str | None, range_spec: str) -> dict[str, Any]:
    summary = closeout_summary(commit_sha, range_spec, doctor_result="pending")
    blockers = summary["known_blockers"]
    status = "pass" if not blockers and summary["validation_result"] == "pass" and summary["changelog"]["status"] == "linked" and summary["delivery_id"] == "bears-governance-kernel-v1" else "fail"
    reason = "commit closeout metadata and exact runtime proof passed" if status == "pass" else "commit closeout metadata or exact runtime proof failed"
    return {
        "id": "commit_closeout",
        "status": status,
        "required": True,
        "summary": reason,
        "component_issue": "#391",
    }


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    msg = sub.add_parser("check-message")
    msg.add_argument("--commit", required=True)
    msg.add_argument("--json", action="store_true")
    runtime = sub.add_parser("validate-runtime")
    runtime.add_argument("--commit", required=True)
    runtime.add_argument("--json", action="store_true")
    summary = sub.add_parser("emit-summary")
    summary.add_argument("--commit", required=True)
    summary.add_argument("--from-git", default="HEAD^..HEAD")
    summary.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        print_packet({"schema": "bears-commit-closeout-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "check-message":
        packet = inspect_commit_message(args.commit)
        print_packet(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    if args.command == "validate-runtime":
        packet = local_validation_proof(args.commit)
        print_packet(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    if args.command == "emit-summary":
        packet = {"schema": "bears-commit-closeout-summary.v1", **closeout_summary(args.commit, args.from_git)}
        print_packet(packet) if args.json else print(packet["validation_result"])
        return 0 if packet["validation_result"] == "pass" and not packet["known_blockers"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
