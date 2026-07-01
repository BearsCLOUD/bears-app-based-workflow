#!/usr/bin/env python3
"""Validate Bears development workflow orchestration packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = PLUGIN_ROOT / "skills/development-workflow-orchestration/contracts"
FIXTURE_DIR = PLUGIN_ROOT / "tests/fixtures/development_workflow"

SCHEMA_FILES = {
    "user-agreement": "user-agreement.v1.schema.json",
    "workspace-bootstrap": "workspace-bootstrap.v1.schema.json",
    "architecture-packet": "architecture-packet.v1.schema.json",
    "task-graph": "task-graph.v1.schema.json",
    "domain-orchestrator-assignment": "domain-orchestrator-assignment.v1.schema.json",
    "worker-assignment": "worker-assignment.v1.schema.json",
    "worker-closeout": "worker-closeout.v1.schema.json",
    "review-result": "review-result.v1.schema.json",
    "merge-decision": "merge-decision.v1.schema.json",
    "stage-boundary-audit": "stage-boundary-audit.v1.schema.json",
}

PACKET_KIND_SCHEMA_ALIASES = {
    "global-review-result": "review-result",
    "closeout-packet": "worker-closeout",
    "merge-ready-packet": "merge-decision",
    "stage-boundary-audit": "stage-boundary-audit",
}

LOCAL_METADATA_PACKET_KINDS = {
    "workflow-state",
    "workflow-worker-state",
}

LOCAL_METADATA_PACKET_FIXTURE_NAMES = {
    "workflow-state": "workflow-state.json",
    "workflow-worker-state": "worker-state.json",
    "worker-state": "worker-state.json",
    "worker_state": "worker-state.json",
}

REVIEW_DECISIONS = {"REVIEW_PASS", "REVIEW_CHANGES_REQUESTED", "REVIEW_BLOCKED"}
MERGE_DECISIONS = {"MERGE_ALLOWED", "MERGE_BLOCKED", "MERGE_NOT_REQUESTED"}
RESTRICTED_MARKERS = (
    "raw_secret",
    "BEGIN PRIVATE KEY",
    ".env=",
    "raw log",
    "raw chat",
    "raw vpn config",
    "credential file",
    "production data",
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_walk_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_walk_strings(item))
        return out
    return []


def _has_restricted_marker(packet: Any) -> bool:
    text = "\n".join(_walk_strings(packet)).casefold()
    return any(marker.casefold() in text for marker in RESTRICTED_MARKERS)


def _require_string(packet: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(packet.get(field), str) or not packet[field].strip():
        errors.append(f"{field} must be a non-empty string")


def _require_string_list(packet: dict[str, Any], field: str, errors: list[str]) -> None:
    value = packet.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{field} must be a non-empty string list")


def _schema_required(kind: str) -> list[str]:
    if kind not in SCHEMA_FILES:
        return []
    schema_path = CONTRACT_DIR / SCHEMA_FILES[kind]
    schema = load_json(schema_path)
    required = schema.get("required")
    return required if isinstance(required, list) else []


def _common_errors(packet: Any, kind: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{kind} packet must be an object"]
    for field in _schema_required(kind):
        if field not in packet:
            errors.append(f"{kind}.{field} is required")
    if packet.get("restricted_data_taint") != "none":
        errors.append(f"{kind}.restricted_data_taint must be none")
    if _has_restricted_marker(packet):
        errors.append(f"{kind} packet contains restricted data marker")
    return errors


def validate_packet(packet: Any, kind: str) -> list[str]:
    if kind not in SCHEMA_FILES:
        return [f"unknown packet kind: {kind}"]
    errors = _common_errors(packet, kind)
    if not isinstance(packet, dict):
        return errors
    for field in ("goal_id", "role", "repo_boundary", "status"):
        if field in packet:
            _require_string(packet, field, errors)
    for field in ("allowed_write_scope", "forbidden_scope", "validation_commands"):
        if field in packet:
            _require_string_list(packet, field, errors)

    if kind == "user-agreement":
        for field in ("forbidden_surfaces", "allowed_repositories", "accepted_assumptions"):
            _require_string_list(packet, field, errors)
        if packet.get("parallelization_permission") is not True:
            errors.append("user-agreement.parallelization_permission must be true or the workflow cannot spawn workers")
    elif kind == "task-graph":
        errors.extend(_validate_task_graph(packet))
    elif kind == "domain-orchestrator-assignment":
        if packet.get("smart_reuse_required") is not True:
            errors.append("domain-orchestrator-assignment.smart_reuse_required must be true")
        _require_string_list(packet, "task_ids", errors)
    elif kind == "worker-closeout":
        validations = packet.get("validation_results")
        if not isinstance(validations, list) or not validations:
            errors.append("worker-closeout.validation_results must list command exit codes")
        elif not all(isinstance(row, dict) and isinstance(row.get("command"), str) and isinstance(row.get("exit_code"), int) for row in validations):
            errors.append("worker-closeout.validation_results entries require command and exit_code")
    elif kind == "review-result":
        if packet.get("decision") not in REVIEW_DECISIONS:
            errors.append("review-result.decision must be REVIEW_PASS, REVIEW_CHANGES_REQUESTED, or REVIEW_BLOCKED")
        if packet.get("forbidden_surfaces_touched") is not False:
            errors.append("review-result.forbidden_surfaces_touched must be false")
    elif kind == "merge-decision":
        if packet.get("decision") not in MERGE_DECISIONS:
            errors.append("merge-decision.decision is not valid")
        if packet.get("decision") == "MERGE_ALLOWED":
            if packet.get("review_decision") != "REVIEW_PASS":
                errors.append("merge-decision MERGE_ALLOWED requires review_decision REVIEW_PASS")
            _require_string(packet, "unchanged_head_evidence", errors)
    elif kind == "stage-boundary-audit":
        if packet.get("forbidden_surfaces_untouched") is not True:
            errors.append("stage-boundary-audit.forbidden_surfaces_untouched must be true")
        _require_string_list(packet, "claims_not_made", errors)
    return errors


def _validate_task_graph(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tasks = packet.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return ["task-graph.tasks must be a non-empty list"]
    ids: set[str] = set()
    deps: dict[str, list[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            errors.append("task-graph.tasks entries must be objects")
            continue
        task_id = task.get("id")
        role = task.get("role")
        if not isinstance(task_id, str) or not task_id:
            errors.append("task-graph task id is required")
            continue
        if task_id in ids:
            errors.append(f"task-graph duplicate task id: {task_id}")
        ids.add(task_id)
        if not isinstance(role, str) or not role:
            errors.append(f"task-graph task {task_id} requires one owner role")
        dep_list = task.get("depends_on", [])
        if not isinstance(dep_list, list):
            errors.append(f"task-graph task {task_id}.depends_on must be a list")
            dep_list = []
        deps[task_id] = [str(item) for item in dep_list]
    for task_id, dep_list in deps.items():
        for dep in dep_list:
            if dep not in ids:
                errors.append(f"task-graph task {task_id} depends on unknown task {dep}")
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            errors.append("task-graph dependencies must be acyclic")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in deps.get(node, []):
            visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in ids:
        visit(node)
    return errors


def normalize_packet_schema_kind(packet_kind: str | None) -> str | None:
    if not isinstance(packet_kind, str):
        return None
    normalized = packet_kind.strip().lower().replace("_", "-")
    if normalized in SCHEMA_FILES:
        return normalized
    return PACKET_KIND_SCHEMA_ALIASES.get(normalized)


def _get_dotted_section(packet: Any, dotted_path: str) -> Any:
    current = packet
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _is_local_packet_ref(value: str) -> bool:
    lowered = value.casefold()
    return "://" not in value and not lowered.startswith(("gh:", "git@", "ssh:"))


def _normalized_ref_parts(path_value: str) -> tuple[str, ...]:
    return PurePosixPath(path_value.replace("\\", "/")).parts


def _has_path_traversal(path_value: str) -> bool:
    return ".." in _normalized_ref_parts(path_value)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _approved_packet_ref_roots(base_dir: Path | None) -> list[Path]:
    root_dir = (base_dir or FIXTURE_DIR).resolve(strict=False)
    approved_roots = [root_dir]
    runtime_root = (PLUGIN_ROOT / "runtime/agent-workflow").resolve(strict=False)
    if _is_relative_to(root_dir, runtime_root):
        approved_roots.append(runtime_root)
    return approved_roots


def _iter_candidate_packet_paths(path_value: str, *, base_dir: Path | None) -> list[Path]:
    ref_path = Path(path_value)
    root_dir = (base_dir or FIXTURE_DIR).resolve(strict=False)
    candidates = [(root_dir / ref_path).resolve(strict=False)]
    repo_candidate = (PLUGIN_ROOT.resolve(strict=False) / ref_path).resolve(strict=False)
    if repo_candidate not in candidates:
        candidates.append(repo_candidate)
    return candidates


def validate_local_packet_ref_path(
    path_value: str,
    *,
    base_dir: Path | None = None,
) -> tuple[list[str], Path | None]:
    if not _is_local_packet_ref(path_value):
        return ["path must be a local file path"], None
    if Path(path_value).is_absolute():
        return ["path must not be absolute"], None
    if _has_path_traversal(path_value):
        return ["path must not contain path traversal"], None

    approved_roots = _approved_packet_ref_roots(base_dir)
    for candidate in _iter_candidate_packet_paths(path_value, base_dir=base_dir):
        if any(_is_relative_to(candidate, root) for root in approved_roots):
            return [], candidate
    return ["path must stay within the approved local boundary"], None


def resolve_local_packet_path(
    path_value: str,
    *,
    base_dir: Path | None = None,
    packet_kind: str | None = None,
) -> Path | None:
    errors, candidate = validate_local_packet_ref_path(path_value, base_dir=base_dir)
    if errors:
        return None
    if candidate is not None and candidate.is_file():
        return candidate

    if not isinstance(packet_kind, str):
        return None
    normalized_kind = packet_kind.strip().lower().replace("_", "-")
    fallback_name = LOCAL_METADATA_PACKET_FIXTURE_NAMES.get(normalized_kind)
    if fallback_name is None:
        return None
    fallback = (base_dir or FIXTURE_DIR).resolve(strict=False) / fallback_name
    return fallback if fallback.is_file() else None


def _extract_packet_refs(section: Any) -> list[tuple[str, str | None]]:
    refs: list[tuple[str, str | None]] = []
    if isinstance(section, str):
        refs.append((section, None))
        return refs
    if isinstance(section, list):
        for item in section:
            refs.extend(_extract_packet_refs(item))
        return refs
    if not isinstance(section, dict):
        return refs

    explicit_kind = section.get("packet_kind")
    if not isinstance(explicit_kind, str):
        explicit_kind = section.get("kind") if isinstance(section.get("kind"), str) else None

    for path_key in ("path", "packet_path"):
        path_value = section.get(path_key)
        if isinstance(path_value, str):
            refs.append((path_value, explicit_kind))
    packet_ref = section.get("packet_ref")
    if isinstance(packet_ref, str):
        refs.append((packet_ref, explicit_kind))
    elif packet_ref is not None:
        refs.extend(_extract_packet_refs(packet_ref))
    packet_refs = section.get("packet_refs")
    if isinstance(packet_refs, list):
        for item in packet_refs:
            refs.extend(_extract_packet_refs(item))
    packet = section.get("packet")
    if packet is not None:
        refs.extend(_extract_packet_refs(packet))
    return refs


def _iter_packet_ref_records(value: Any, path: str = "workflow-state") -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            records.extend(_iter_packet_ref_records(item, f"{path}[{index}]"))
        return records
    if not isinstance(value, dict):
        return records
    if isinstance(value.get("kind"), str) and isinstance(value.get("path"), str):
        records.append((path, value))
    for key, item in value.items():
        records.extend(_iter_packet_ref_records(item, f"{path}.{key}"))
    return records


def _validate_packet_ref_record(
    record_path: str,
    record: dict[str, Any],
    *,
    base_dir: Path | None,
    expected_kind: str | None = None,
) -> list[str]:
    errors: list[str] = []
    kind = record.get("kind")
    if not isinstance(kind, str):
        kind = expected_kind
    if not isinstance(kind, str) or not kind.strip():
        errors.append(f"{record_path}.kind must be a non-empty string")
        return errors
    path_value = record.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        errors.append(f"{record_path}.path must be a non-empty string")
        return errors
    if record.get("requires_network") not in (None, False):
        errors.append(f"{record_path}.requires_network must be false for local workflow-state validation")
    path_errors, resolved_candidate = validate_local_packet_ref_path(path_value, base_dir=base_dir)
    if path_errors:
        errors.extend(f"{record_path}.{message}" for message in path_errors)
        return errors
    schema_kind = normalize_packet_schema_kind(kind)
    if schema_kind is None:
        return errors
    ref_path = resolve_local_packet_path(path_value, base_dir=base_dir, packet_kind=kind)
    if ref_path is None:
        if record.get("source") == "metadata_only":
            return errors
        candidate_path = resolved_candidate
        if candidate_path is None:
            candidate_path = (base_dir or FIXTURE_DIR).resolve(strict=False) / Path(path_value)
        errors.append(f"{record_path}.path does not exist for packet kind {kind}: {candidate_path}")
        return errors
    packet = load_json(ref_path)
    packet_errors = validate_packet(packet, schema_kind)
    errors.extend(f"{record_path} -> {ref_path}: {error}" for error in packet_errors)
    return errors


def validate_local_packet_ref_records(
    packet: Any,
    *,
    base_dir: Path | None = None,
    root_path: str = "workflow-state",
) -> list[str]:
    errors: list[str] = []
    for record_path, record in _iter_packet_ref_records(packet, root_path):
        errors.extend(_validate_packet_ref_record(record_path, record, base_dir=base_dir))
    return errors


def validate_workflow_state_references(
    workflow_state_packet: Any,
    state_bindings: dict[str, Any] | None = None,
    *,
    base_dir: Path | None = None,
) -> list[str]:
    if not isinstance(workflow_state_packet, dict):
        return ["workflow-state packet must be an object"]

    errors: list[str] = []
    bindings = state_bindings if isinstance(state_bindings, dict) else {}
    for stage, binding in bindings.items():
        if not isinstance(binding, dict):
            errors.append(f"workflow-state binding {stage} must be an object")
            continue
        expected_kind = binding.get("packet_kind")
        section_path = binding.get("workflow_state_section")
        if not isinstance(section_path, str) or not section_path.strip():
            errors.append(f"workflow-state binding {stage}.workflow_state_section must be a non-empty string")
            continue
        section = _get_dotted_section(workflow_state_packet, section_path)
        if section is None:
            continue
        schema_kind = normalize_packet_schema_kind(expected_kind if isinstance(expected_kind, str) else None)
        if schema_kind is None:
            continue
        refs = _extract_packet_refs(section)
        for ref_value, explicit_kind in refs:
            if not isinstance(ref_value, str) or not ref_value.strip():
                errors.append(f"workflow-state section {section_path} contains an empty packet ref")
                continue
            explicit_schema_kind = normalize_packet_schema_kind(explicit_kind)
            if explicit_schema_kind is not None and explicit_schema_kind != schema_kind:
                errors.append(
                    f"workflow-state section {section_path} packet kind {explicit_kind} does not match binding {expected_kind}"
                )
                continue
            errors.extend(
                _validate_packet_ref_record(
                    section_path,
                    {"kind": expected_kind, "path": ref_value, "source": "local_state"},
                    base_dir=base_dir,
                    expected_kind=expected_kind,
                )
            )
    errors.extend(validate_local_packet_ref_records(workflow_state_packet, base_dir=base_dir))
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    for kind, filename in SCHEMA_FILES.items():
        path = CONTRACT_DIR / filename
        if not path.is_file():
            errors.append(f"missing schema: {filename}")
            continue
        schema = load_json(path)
        if schema.get("type") != "object":
            errors.append(f"{filename}.type must be object")
        required = schema.get("required")
        if not isinstance(required, list) or not required:
            errors.append(f"{filename}.required must be non-empty")
        desc = str(schema.get("description", ""))
        for marker in ("raw secrets", "raw logs", "raw chats", "raw VPN configs", "production data"):
            if marker not in desc:
                errors.append(f"{filename}.description must mention {marker}")
    for path in sorted((FIXTURE_DIR / "positive").glob("*.json")):
        kind = path.stem
        if kind == "workflow-state":
            errors.extend(
                f"{path}: {error}"
                for error in validate_workflow_state_references(load_json(path), base_dir=path.parent)
            )
            continue
        if kind not in SCHEMA_FILES:
            continue
        errors.extend(f"{path}: {error}" for error in validate_packet(load_json(path), kind))
    for path in sorted((FIXTURE_DIR / "negative").glob("*.json")):
        kind = path.stem.split("--", 1)[0]
        if kind == "workflow-state":
            packet_errors = validate_workflow_state_references(load_json(path), base_dir=path.parent)
            if not packet_errors:
                errors.append(f"{path}: negative fixture unexpectedly passed")
            continue
        if kind not in SCHEMA_FILES:
            continue
        packet_errors = validate_packet(load_json(path), kind)
        if not packet_errors:
            errors.append(f"{path}: negative fixture unexpectedly passed")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    for command, kind in (
        ("validate-user-agreement", "user-agreement"),
        ("validate-bootstrap", "workspace-bootstrap"),
        ("validate-task-graph", "task-graph"),
        ("validate-stage-audit", "stage-boundary-audit"),
    ):
        p = sub.add_parser(command)
        p.add_argument("packet")
        p.set_defaults(kind=kind)
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
    else:
        errors = validate_packet(load_json(Path(args.packet)), args.kind)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("development workflow ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
