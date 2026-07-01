#!/usr/bin/env python3
"""Validate and run the Dagger delivery gate wrapper."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/dagger-delivery-pipeline.v1.json"
RESULT_SCHEMA = PLUGIN_ROOT / "assets/schemas/dagger-delivery-result.v1.schema.json"
VALIDATE_COMMAND = "python3 scripts/dagger_delivery.py validate"
RUN_COMMAND = "python3 scripts/dagger_delivery.py run --delivery-id <id> --json"
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
GIT_ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")
TIMEOUT_SECONDS = 900


def load_json(path: Path) -> Any:
    """Load JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def clean_env() -> dict[str, str]:
    """Return a process environment without Git path overrides."""
    env = dict(os.environ)
    for key in GIT_ENV_KEYS:
        env.pop(key, None)
    return env


def compact_text(*parts: str) -> str:
    """Flatten text to one short line."""
    lines = [line.strip() for part in parts if part for line in part.splitlines() if line.strip()]
    return " | ".join(lines)[:1000]


def render_errors(errors: list[str]) -> str:
    """Render gate errors as one short string."""
    return "; ".join(error for error in errors if error)[:1000]


def dagger_binary_path() -> str | None:
    """Return the dagger binary path when installed."""
    return shutil.which("dagger")


def run_command(command: list[str], *, timeout: int = TIMEOUT_SECONDS) -> tuple[int, str, str]:
    """Run one read-only command and capture text output."""
    try:
        proc = subprocess.run(
            command,
            cwd=PLUGIN_ROOT,
            env=clean_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    return proc.returncode, proc.stdout, proc.stderr


def run_json_command(command: list[str], *, timeout: int = TIMEOUT_SECONDS) -> tuple[int, dict[str, Any], str]:
    """Run a JSON command and parse its packet."""
    code, stdout, stderr = run_command(command, timeout=timeout)
    packet: dict[str, Any] = {}
    if stdout.strip():
        try:
            packet = json.loads(stdout)
        except json.JSONDecodeError:
            packet = {}
    return code, packet, compact_text(stderr, stdout)


def git_output(args: list[str]) -> str:
    """Run git and return stdout."""
    code, stdout, stderr = run_command(["git", *args], timeout=60)
    if code != 0:
        raise RuntimeError(compact_text(stdout, stderr) or f"git {' '.join(args)} failed")
    return stdout.strip()


def current_commit_sha() -> str:
    """Return the current HEAD commit sha."""
    return git_output(["rev-parse", "--verify", "HEAD"])


def parent_range(commit_sha: str) -> str:
    """Return the parent range for a commit sha."""
    line = git_output(["rev-list", "--parents", "-n", "1", commit_sha])
    parts = line.split()
    if len(parts) <= 1:
        return f"{EMPTY_TREE_SHA}..{commit_sha}"
    return f"{parts[1]}..{commit_sha}"


def result_packet(
    *,
    status: str,
    failed_gates: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    next_actions: list[str],
    delivery_id: str | None = None,
) -> dict[str, Any]:
    """Build a compact delivery result packet."""
    packet: dict[str, Any] = {
        "schema": "bears-dagger-delivery-result.v1",
        "status": status,
        "failed_gates": failed_gates,
        "artifacts": artifacts,
        "next_actions": next_actions,
    }
    if delivery_id:
        packet["delivery_id"] = delivery_id
    return packet


def catalog_artifacts() -> list[dict[str, Any]]:
    """Return catalog validation artifacts."""
    return [
        {"gate": "schema_catalog_validation", "kind": "catalog", "path": CATALOG.relative_to(PLUGIN_ROOT).as_posix()},
        {"gate": "schema_catalog_validation", "kind": "schema", "path": RESULT_SCHEMA.relative_to(PLUGIN_ROOT).as_posix()},
    ]


def add_artifact(artifacts: list[dict[str, Any]], gate: str, kind: str, path_value: str | None) -> None:
    """Append one artifact path when present."""
    if isinstance(path_value, str) and path_value:
        artifacts.append({"gate": gate, "kind": kind, "path": path_value})


def add_evidence_artifacts(artifacts: list[dict[str, Any]], gate: str, evidence: Any) -> None:
    """Append evidence paths when a gate packet exposes them."""
    if isinstance(evidence, str):
        add_artifact(artifacts, gate, "evidence", evidence)
    elif isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, str) and item:
                add_artifact(artifacts, gate, "evidence", item)


def dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate artifacts while preserving order."""
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in artifacts:
        key = (str(item.get("gate", "")), str(item.get("kind", "")), str(item.get("path", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    """Validate the pipeline catalog structure."""
    errors: list[str] = []
    if catalog.get("schema") != "bears-dagger-delivery-pipeline.v1":
        errors.append("catalog schema must be bears-dagger-delivery-pipeline.v1")
    if catalog.get("version") != "1":
        errors.append("catalog version must be 1")
    if catalog.get("owner_issue") != "#461":
        errors.append("catalog owner_issue must be #461")
    commands = catalog.get("commands")
    if commands != [VALIDATE_COMMAND, RUN_COMMAND]:
        errors.append("catalog commands must match validate/run wrapper commands")
    gates = catalog.get("gates")
    if not isinstance(gates, list) or len(gates) != 5:
        errors.append("catalog gates must contain five ordered gates")
        return errors
    expected_ids = [
        "schema_catalog_validation",
        "external_review_audit",
        "policy_invariants",
        "impacted_runner",
        "bears_doctor_validate_closeout",
    ]
    for index, gate_id in enumerate(expected_ids):
        gate = gates[index] if index < len(gates) and isinstance(gates[index], dict) else {}
        if gate.get("id") != gate_id:
            errors.append(f"catalog gate order mismatch at index {index}: expected {gate_id}")
    expected_commands = {
        "schema_catalog_validation": VALIDATE_COMMAND,
        "external_review_audit": "python3 scripts/external_review_audit.py check-delivery --delivery-id <id> --json",
        "policy_invariants": "python3 scripts/policy_invariants.py evaluate-closeout --from-git <range> --json",
        "impacted_runner": "python3 scripts/local_commit_validation.py run --commit-sha <sha>",
        "bears_doctor_validate_closeout": "python3 scripts/bears_doctor.py validate-closeout --from-git <range> --json",
    }
    expected_required = {
        "schema_catalog_validation": True,
        "external_review_audit": True,
        "policy_invariants": True,
        "impacted_runner": False,
        "bears_doctor_validate_closeout": True,
    }
    expected_components = {
        "schema_catalog_validation": "#461",
        "external_review_audit": "#425",
        "policy_invariants": "#460",
        "impacted_runner": "#459",
        "bears_doctor_validate_closeout": "#461",
    }
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("catalog gates must contain objects")
            continue
        gate_id = str(gate.get("id", ""))
        if gate_id not in expected_commands:
            errors.append(f"catalog gate id unsupported: {gate_id}")
            continue
        if gate.get("command") != expected_commands[gate_id]:
            errors.append(f"catalog gate command mismatch for {gate_id}")
        if gate.get("required") is not expected_required[gate_id]:
            errors.append(f"catalog gate required mismatch for {gate_id}")
        if gate.get("component_issue") != expected_components[gate_id]:
            errors.append(f"catalog gate component_issue mismatch for {gate_id}")
        if gate_id == "impacted_runner" and gate.get("when_available") is not True:
            errors.append("catalog impacted_runner gate must be when_available")
    missing_dagger = catalog.get("missing_dagger")
    if not isinstance(missing_dagger, dict):
        errors.append("catalog missing_dagger block required")
    else:
        if missing_dagger.get("status") != "tool_missing":
            errors.append("catalog missing_dagger.status must be tool_missing")
        if missing_dagger.get("next_action") != "manual_setup_required":
            errors.append("catalog missing_dagger.next_action must be manual_setup_required")
    return errors


def validate_result(result: dict[str, Any], *, label: str) -> list[str]:
    """Validate a compact result packet."""
    errors: list[str] = []
    if result.get("schema") != "bears-dagger-delivery-result.v1":
        errors.append(f"{label}: schema mismatch")
    if result.get("status") not in {"pass", "fail", "tool_missing"}:
        errors.append(f"{label}: status mismatch")
    for field in ("failed_gates", "artifacts", "next_actions"):
        if not isinstance(result.get(field), list):
            errors.append(f"{label}: {field} must be a list")
    return errors


def gate_failure(gate: str, summary: str, *, status: str = "fail", exit_code: int = 1) -> dict[str, Any]:
    """Build one failed gate record."""
    return {"gate": gate, "status": status, "exit_code": exit_code, "summary": summary}


def gate_summary(packet: dict[str, Any], stderr_text: str) -> str:
    """Render a short gate summary from a JSON packet."""
    for key in ("sanitized_summary", "summary", "message", "error"):
        value = packet.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1000]
    errors = packet.get("errors")
    if isinstance(errors, list) and errors:
        return render_errors([str(item) for item in errors])
    if stderr_text.strip():
        return stderr_text.strip()[:1000]
    return "command failed"


def record_packet_artifacts(artifacts: list[dict[str, Any]], gate: str, packet: dict[str, Any]) -> None:
    """Record known artifact paths from a gate packet."""
    add_artifact(artifacts, gate, "summary", str(packet.get("summary_path") or ""))
    add_artifact(artifacts, gate, "proof", str(packet.get("proof_path") or ""))
    closeout = packet.get("closeout_summary")
    if isinstance(closeout, dict):
        add_evidence_artifacts(artifacts, gate, closeout.get("expected_evidence_paths"))


def validate_packet() -> dict[str, Any]:
    """Return the catalog validation packet."""
    try:
        catalog = load_json(CATALOG)
    except Exception as exc:
        failed_gates = [gate_failure("schema_catalog_validation", f"cannot read catalog: {exc}")]
        return result_packet(status="fail", failed_gates=failed_gates, artifacts=catalog_artifacts(), next_actions=["fix the pipeline catalog and rerun validate"])
    errors = validate_catalog(catalog)
    if errors:
        failed_gates = [gate_failure("schema_catalog_validation", render_errors(errors))]
        return result_packet(status="fail", failed_gates=failed_gates, artifacts=catalog_artifacts(), next_actions=["fix the pipeline catalog and rerun validate"])
    return result_packet(status="pass", failed_gates=[], artifacts=catalog_artifacts(), next_actions=[])


def run_packet(delivery_id: str) -> dict[str, Any]:
    """Run the ordered delivery gates."""
    try:
        catalog = load_json(CATALOG)
    except Exception as exc:
        return result_packet(
            status="fail",
            delivery_id=delivery_id,
            failed_gates=[gate_failure("schema_catalog_validation", f"cannot read catalog: {exc}")],
            artifacts=catalog_artifacts(),
            next_actions=["fix the pipeline catalog and rerun python3 scripts/dagger_delivery.py run --delivery-id <id> --json"],
        )
    errors = validate_catalog(catalog)
    artifacts = catalog_artifacts()
    if errors:
        return result_packet(
            status="fail",
            delivery_id=delivery_id,
            failed_gates=[gate_failure("schema_catalog_validation", render_errors(errors))],
            artifacts=artifacts,
            next_actions=["fix the pipeline catalog and rerun python3 scripts/dagger_delivery.py run --delivery-id <id> --json"],
        )
    if dagger_binary_path() is None:
        missing = catalog.get("missing_dagger", {})
        return result_packet(
            status=str(missing.get("status", "tool_missing")),
            delivery_id=delivery_id,
            failed_gates=[gate_failure("dagger_binary", "dagger binary missing", status=str(missing.get("status", "tool_missing")), exit_code=127)],
            artifacts=artifacts,
            next_actions=[f"{missing.get('next_action', 'manual_setup_required')}: install dagger and rerun python3 scripts/dagger_delivery.py run --delivery-id <id> --json"],
        )

    commit_sha = current_commit_sha()
    commit_range = parent_range(commit_sha)

    gate_commands: list[tuple[str, list[str], bool]] = [
        ("external_review_audit", ["python3", "scripts/external_review_audit.py", "check-delivery", "--delivery-id", delivery_id, "--json"], True),
        ("policy_invariants", ["python3", "scripts/policy_invariants.py", "evaluate-closeout", "--from-git", commit_range, "--json"], True),
        ("impacted_runner", ["python3", "scripts/local_commit_validation.py", "run", "--commit-sha", commit_sha], False),
        ("bears_doctor_validate_closeout", ["python3", "scripts/bears_doctor.py", "validate-closeout", "--from-git", commit_range, "--json"], True),
    ]

    for gate_id, command, required in gate_commands:
        script_path = PLUGIN_ROOT / command[1]
        if gate_id == "impacted_runner" and not script_path.exists():
            continue
        if gate_id == "impacted_runner" and not required and not script_path.exists():
            continue
        code, packet, stderr_text = run_json_command(command)
        if code != 0 or packet.get("status") != "pass":
            summary = gate_summary(packet, stderr_text)
            failed_gates = [gate_failure(gate_id, summary, exit_code=code)]
            record_packet_artifacts(artifacts, gate_id, packet)
            return result_packet(
                status="fail",
                delivery_id=delivery_id,
                failed_gates=failed_gates,
                artifacts=dedupe_artifacts(artifacts),
                next_actions=[f"fix {gate_id} and rerun python3 scripts/dagger_delivery.py run --delivery-id <id> --json"],
            )
        record_packet_artifacts(artifacts, gate_id, packet)

    return result_packet(status="pass", delivery_id=delivery_id, failed_gates=[], artifacts=dedupe_artifacts(artifacts), next_actions=[])


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--delivery-id", required=True)
    run.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the wrapper CLI."""
    args = build_parser().parse_args(argv)
    packet = validate_packet() if args.command == "validate" else run_packet(str(args.delivery_id))
    print(json.dumps(packet, indent=2, sort_keys=True))
    if validate_result(packet, label=args.command):
        return 1
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
