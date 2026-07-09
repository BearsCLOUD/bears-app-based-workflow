#!/usr/bin/env python3
"""Plan file-scoped execution before bounded session fanout."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = PLUGIN_ROOT / "assets/schemas/file-change-plan.v1.schema.json"
UNIT_SCHEMA = PLUGIN_ROOT / "assets/schemas/file-execution-unit.v1.schema.json"
REUSE_SCHEMA = PLUGIN_ROOT / "assets/schemas/session-reuse-plan.v1.schema.json"
POOL_SCHEMA = PLUGIN_ROOT / "assets/schemas/session-pool-state.v1.schema.json"
CATALOG = PLUGIN_ROOT / "assets/catalog/file-scoped-execution.v1.json"
OWNER_ROLE = "bears-machine-first-execution-kernel-engineer"
WRITE_OPS = {"create", "modify", "delete", "rename"}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import file_context_index


def load(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, packet: dict[str, Any]) -> None:
    """Write a stable JSON packet to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(path: str) -> str:
    """Normalize a repository path for matching and packet output."""
    item = path.replace("\\", "/").strip().strip("/")
    while item.startswith("./"):
        item = item[2:]
    return item


def stable_id(prefix: str, *parts: str) -> str:
    """Return a short deterministic id for plan locks and units."""
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def parse_target(raw: str) -> dict[str, str]:
    """Parse path[:operation[:role]] target input."""
    parts = raw.split(":", 2)
    path = normalize(parts[0])
    operation = parts[1] if len(parts) > 1 and parts[1] else "modify"
    role = parts[2] if len(parts) > 2 and parts[2] else OWNER_ROLE
    if operation not in {"read", "create", "modify", "delete", "rename"}:
        raise ValueError(f"unsupported operation for {path}: {operation}")
    return {"path": path, "operation": operation, "owner_role": role}


def base_file_record(target: dict[str, str]) -> dict[str, Any]:
    """Build the initial file record before context coverage."""
    return {
        "path": target["path"],
        "operation": target["operation"],
        "owner_role": target["owner_role"],
        "authority_topic": None,
        "context_id": None,
        "workflow_nodes": [],
        "decision_refs": [],
        "changelog_required": target["operation"] in WRITE_OPS,
        "lock_id": None,
        "execution_unit": None,
        "coverage_status": "missing_context" if target["operation"] != "create" else "missing_lock",
    }


def build_plan(goal_id: str, delivery_id: str, source_ref: str, targets: list[str]) -> dict[str, Any]:
    """Build a draft file-change plan packet."""
    files = [base_file_record(parse_target(item)) for item in targets]
    return {
        "schema": "bears-file-change-plan.v1",
        "version": "1",
        "goal_id": goal_id,
        "delivery_id": delivery_id,
        "source_ref": source_ref,
        "state": "draft",
        "files": files,
        "conflicts": [],
        "join_gate": f"runtime/file-scoped-execution/{goal_id}/join-gate.v1.json",
    }


def context_records() -> dict[str, dict[str, Any]]:
    """Return #429 file-context records keyed by path."""
    return file_context_index.records_by_path(file_context_index.index_packet())


def coverage_status(record: dict[str, Any], context: dict[str, Any] | None) -> str:
    """Classify target coverage from file context, authority, and lock state."""
    if record["operation"] != "create" and context is None:
        return "missing_context"
    if context and (context.get("status") != "active" or file_context_index.record_is_stale(context)):
        return "manual_review"
    if not record.get("owner_role") and not (context and context.get("owner_role")):
        return "missing_authority"
    if record["operation"] in WRITE_OPS and not record.get("lock_id"):
        return "missing_lock"
    return "covered"


def enrich_file(record: dict[str, Any], contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Attach context, ownership, lock, and unit ids to one file record."""
    item = dict(record)
    path = normalize(str(item.get("path", "")))
    context = contexts.get(path)
    if context:
        item["context_id"] = context.get("context_id")
        item["owner_role"] = item.get("owner_role") or context.get("owner_role") or OWNER_ROLE
        item["authority_topic"] = context.get("authority_topic")
        item["workflow_nodes"] = list(context.get("workflow_nodes", []))
        item["decision_refs"] = list(context.get("decision_refs", []))
    item["lock_id"] = None if item.get("operation") == "read" else stable_id("lock", path)
    item["execution_unit"] = stable_id("unit", str(item.get("owner_role") or OWNER_ROLE), path)
    item["coverage_status"] = coverage_status(item, context)
    return item


def write_paths(file_record: dict[str, Any]) -> set[str]:
    """Return the write-scope path set for conflict checks."""
    return {normalize(str(file_record.get("path", "")))} if file_record.get("operation") in WRITE_OPS else set()


def path_conflicts(left: str, right: str) -> bool:
    """Return true when two write paths overlap."""
    return left == right or left.startswith(right.rstrip("/") + "/") or right.startswith(left.rstrip("/") + "/")


def conflict_edges(files: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build file conflict edges for overlapping write scopes."""
    conflicts: list[dict[str, str]] = []
    for left_index, left in enumerate(files):
        for right in files[left_index + 1 :]:
            for left_path in write_paths(left):
                for right_path in write_paths(right):
                    if path_conflicts(left_path, right_path):
                        conflicts.append({"left": left_path, "right": right_path, "reason": "overlapping write scope", "resolution": "merge_unit"})
    return conflicts


def cover_plan(packet: dict[str, Any]) -> dict[str, Any]:
    """Return a covered plan or blocked plan with missing coverage reasons."""
    contexts = context_records()
    files = [enrich_file(item, contexts) for item in packet.get("files", []) if isinstance(item, dict)]
    conflicts = conflict_edges(files)
    blocked = any(item.get("coverage_status") != "covered" for item in files)
    packet = dict(packet)
    packet["files"] = files
    packet["conflicts"] = conflicts
    packet["state"] = "blocked" if blocked else ("covered" if conflicts else "ready_for_fanout")
    return packet


def validate_catalog() -> list[str]:
    """Validate schemas and the file-scoped execution catalog."""
    errors: list[str] = []
    for path in (PLAN_SCHEMA, UNIT_SCHEMA, REUSE_SCHEMA, POOL_SCHEMA, CATALOG):
        if not path.exists():
            errors.append(f"missing required artifact: {path.relative_to(PLUGIN_ROOT)}")
    if CATALOG.exists():
        catalog = load(CATALOG)
        if catalog.get("schema") != "bears-file-scoped-execution.v1":
            errors.append("file-scoped catalog schema mismatch")
        for rel_path in catalog.get("required_schemas", []):
            if not (PLUGIN_ROOT / str(rel_path)).exists():
                errors.append(f"catalog required schema missing: {rel_path}")
    sample = build_plan("goal-sample", "delivery-sample", "manual", ["scripts/file_context_index.py:read"])
    errors.extend(validate_json_schema(sample, PLAN_SCHEMA, "sample-plan"))
    return errors


def command_validate(args: argparse.Namespace) -> int:
    """Run bounded validation for file-scoped planning contracts."""
    errors = validate_catalog()
    print(json.dumps({"schema": "bears-file-scoped-execution-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_plan(args: argparse.Namespace) -> int:
    """Emit a draft file-change plan."""
    packet = build_plan(args.goal_id, args.delivery_id or args.goal_id, args.source_ref, args.target_file or [])
    errors = validate_json_schema(packet, PLAN_SCHEMA, "plan")
    if args.output:
        write(Path(args.output), packet)
    print(json.dumps({**packet, "validation_errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_cover(args: argparse.Namespace) -> int:
    """Attach file-context coverage, locks, conflicts, and units to a plan."""
    packet = cover_plan(load(Path(args.plan)))
    errors = validate_json_schema(packet, PLAN_SCHEMA, "covered-plan")
    if args.output:
        write(Path(args.output), packet)
    print(json.dumps({**packet, "validation_errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors and packet["state"] != "blocked" else 1


def command_conflict_graph(args: argparse.Namespace) -> int:
    """Emit the conflict graph for a covered or draft plan."""
    packet = load(Path(args.plan))
    conflicts = conflict_edges([item for item in packet.get("files", []) if isinstance(item, dict)])
    result = {"schema": "bears-file-conflict-graph.v1", "status": "pass", "goal_id": packet.get("goal_id"), "conflicts": conflicts, "conflict_count": len(conflicts)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=command_validate)
    plan = sub.add_parser("plan")
    plan.add_argument("--goal-id", required=True)
    plan.add_argument("--delivery-id")
    plan.add_argument("--source-ref", default="manual")
    plan.add_argument("--target-file", action="append")
    plan.add_argument("--output")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)
    cover = sub.add_parser("cover")
    cover.add_argument("--plan", required=True)
    cover.add_argument("--output")
    cover.add_argument("--json", action="store_true")
    cover.set_defaults(func=command_cover)
    graph = sub.add_parser("conflict-graph")
    graph.add_argument("--plan", required=True)
    graph.add_argument("--json", action="store_true")
    graph.set_defaults(func=command_conflict_graph)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the file change planner CLI."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
