#!/usr/bin/env python3
"""Manage bounded reusable sessions for file execution units."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
POLICY = PLUGIN_ROOT / "assets/catalog/session-reuse-policy.v1.json"
UNIT_SCHEMA = PLUGIN_ROOT / "assets/schemas/file-execution-unit.v1.schema.json"
REUSE_SCHEMA = PLUGIN_ROOT / "assets/schemas/session-reuse-plan.v1.schema.json"
POOL_SCHEMA = PLUGIN_ROOT / "assets/schemas/session-pool-state.v1.schema.json"
STATE = PLUGIN_ROOT / "runtime/session-pool/session-pool-state.v1.json"
OWNER_ROLE = "bears-machine-first-execution-kernel-engineer"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import file_context_index


def utc_now() -> str:
    """Return an ISO UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    """Parse an ISO UTC timestamp."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, packet: dict[str, Any]) -> None:
    """Write a stable JSON packet to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(path: str) -> str:
    """Normalize a repository path."""
    return path.replace("\\", "/").strip().strip("/")


def stable_id(prefix: str, *parts: str) -> str:
    """Return a deterministic short id."""
    return f"{prefix}-{hashlib.sha256(chr(0).join(parts).encode('utf-8')).hexdigest()[:16]}"


def policy() -> dict[str, Any]:
    """Load the session reuse policy."""
    return load(POLICY)


def context_index_version() -> str:
    """Return the compact context-index version marker."""
    packet = file_context_index.index_packet()
    return f"{packet.get('version', '1')}@{packet.get('updated', 'unknown')}"


def state_path(path_arg: str | None = None) -> Path:
    """Resolve the session-pool state path."""
    return Path(path_arg) if path_arg else STATE


def empty_state() -> dict[str, Any]:
    """Build an empty pool state packet."""
    return {"schema": "bears-session-pool-state.v1", "version": "1", "updated": utc_now(), "policy": "assets/catalog/session-reuse-policy.v1.json", "sessions": []}


def load_state(path: Path) -> dict[str, Any]:
    """Load pool state or return an empty state."""
    return load(path) if path.exists() else empty_state()


def write_paths(file_record: dict[str, Any]) -> list[str]:
    """Return allowed writes for a file plan record."""
    if file_record.get("operation") == "read":
        return []
    return [normalize(str(file_record.get("path", "")))]


def unit_from_files(plan: dict[str, Any], unit_id: str, files: list[dict[str, Any]], executor: str) -> dict[str, Any]:
    """Build one independently runnable file execution unit."""
    role_id = str(files[0].get("owner_role") or OWNER_ROLE)
    target_files = sorted({normalize(str(item.get("path", ""))) for item in files})
    write_scope = sorted({path for item in files for path in write_paths(item)})
    context_ids = sorted({str(item.get("context_id")) for item in files if item.get("context_id")})
    decision_ids = sorted({ref for item in files for ref in item.get("decision_refs", [])})
    return {
        "schema": "bears-file-execution-unit.v1",
        "version": "1",
        "unit_id": unit_id,
        "goal_id": str(plan.get("goal_id")),
        "delivery_id": str(plan.get("delivery_id")),
        "role_id": role_id,
        "executor": executor,
        "session_policy": "reuse_allowed",
        "target_files": target_files,
        "input_context_ids": context_ids,
        "allowed_read_paths": target_files,
        "allowed_write_paths": write_scope,
        "required_outputs": [f"runtime/file-scoped-execution/{plan.get('goal_id')}/results/{unit_id}.json"],
        "validation_commands": ["python3 scripts/file_execution_join.py doctor --json"],
        "max_runtime_seconds": 1800,
        "max_changed_files": max(1, len(write_scope)),
        "decision_ids": decision_ids,
        "authority_topic": files[0].get("authority_topic"),
    }


def fanout_groups(units: list[dict[str, Any]]) -> list[list[str]]:
    """Group units that have disjoint write scopes."""
    groups: list[list[str]] = []
    used_paths: list[set[str]] = []
    for unit in units:
        writes = set(unit.get("allowed_write_paths", []))
        placed = False
        for index, group_paths in enumerate(used_paths):
            if writes.isdisjoint(group_paths):
                groups[index].append(str(unit["unit_id"]))
                group_paths.update(writes)
                placed = True
                break
        if not placed:
            groups.append([str(unit["unit_id"])])
            used_paths.append(set(writes))
    return groups


def authority_topic(unit: dict[str, Any]) -> str | None:
    """Derive authority topic from unit metadata or target file contexts."""
    if unit.get("authority_topic") is not None:
        return str(unit.get("authority_topic"))
    contexts = file_context_index.records_by_path(file_context_index.index_packet())
    topics = {
        str(contexts[path].get("authority_topic"))
        for path in [normalize(str(item)) for item in unit.get("target_files", [])]
        if path in contexts and contexts[path].get("authority_topic")
    }
    return sorted(topics)[0] if len(topics) == 1 else None


def decision_ids(unit: dict[str, Any]) -> list[str]:
    """Derive compact decision ids from unit metadata or target file contexts."""
    if unit.get("decision_ids"):
        return sorted(str(item) for item in unit.get("decision_ids", []))
    contexts = file_context_index.records_by_path(file_context_index.index_packet())
    refs = {
        str(ref)
        for path in [normalize(str(item)) for item in unit.get("target_files", [])]
        if path in contexts
        for ref in contexts[path].get("decision_refs", [])
    }
    return sorted(refs)


def raw_context_marker(value: Any) -> bool:
    """Return true when nested session state contains raw/non-compact chat markers."""
    forbidden_keys = {"raw_chat", "raw_chat_context", "chat_history", "messages", "transcript", "parent_context", "prompt", "completion"}
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).casefold()
            if lowered in forbidden_keys:
                return True
            if "raw" in lowered and ("chat" in lowered or "context" in lowered):
                return True
            if raw_context_marker(nested):
                return True
    elif isinstance(value, list):
        return any(raw_context_marker(item) for item in value)
    return False


def session_has_raw_context(session: dict[str, Any]) -> bool:
    """Return true when a session contains raw chat or non-compact context fields."""
    return raw_context_marker(session)


def compatible(unit: dict[str, Any], session: dict[str, Any], model_tier: str) -> tuple[bool, str]:
    """Check strict reusable-session compatibility."""
    if session_has_raw_context(session):
        return False, "raw chat context forbidden"
    if session.get("state") != "available":
        return False, "session not available"
    if session.get("degraded") or session.get("failed"):
        return False, "previous run failed or degraded"
    if parse_time(str(session.get("expires_at"))) <= datetime.now(timezone.utc):
        return False, "ttl expired"
    checks = [
        (session.get("executor") == unit.get("executor"), "executor mismatch"),
        (session.get("role_id") == unit.get("role_id"), "role profile mismatch"),
        (session.get("model_tier") == model_tier, "model tier mismatch"),
        (session.get("repo_root") == str(PLUGIN_ROOT), "repo or worktree mismatch"),
        (session.get("authority_topic") == authority_topic(unit), "authority topic mismatch"),
        (sorted(session.get("allowed_write_paths", [])) == sorted(unit.get("allowed_write_paths", [])), "allowed write scope mismatch"),
        (session.get("context_index_version") == context_index_version(), "context index version mismatch"),
    ]
    for ok, reason in checks:
        if not ok:
            return False, reason
    return True, "compatible compact session"


def select_session(unit: dict[str, Any], pool: dict[str, Any], model_tier: str) -> tuple[str | None, str]:
    """Return a compatible available session id when one exists."""
    for session in pool.get("sessions", []):
        ok, reason = compatible(unit, session, model_tier)
        if ok:
            return str(session.get("session_id")), reason
    return None, "fresh session required"


def build_reuse_plan(file_plan: dict[str, Any], output_dir: Path | None = None) -> dict[str, Any]:
    """Build session reuse decisions and optional unit packets from a covered file plan."""
    cfg = policy().get("policy", {})
    executor = str(cfg.get("default_executor", "codex_exec"))
    files = [item for item in file_plan.get("files", []) if isinstance(item, dict)]
    errors = [f"uncovered file: {item.get('path')}" for item in files if item.get("coverage_status") != "covered"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in files:
        grouped.setdefault(str(item.get("execution_unit") or stable_id("unit", str(item.get("path")))), []).append(item)
    units = [unit_from_files(file_plan, unit_id, grouped[unit_id], executor) for unit_id in sorted(grouped)]
    pool = load_state(STATE)
    model_tier = str(cfg.get("default_model_tier", "standard"))
    unit_refs: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for unit in units:
        packet_path = f"runtime/file-scoped-execution/{file_plan.get('goal_id')}/units/{unit['unit_id']}.json"
        if output_dir:
            packet_path = (output_dir / f"{unit['unit_id']}.json").as_posix()
            write(Path(packet_path), {k: v for k, v in unit.items() if k not in {"decision_ids", "authority_topic"}})
        session_id, reason = select_session(unit, pool, model_tier)
        decisions.append({"unit_id": unit["unit_id"], "status": "reuse_candidate" if session_id else "fresh_required", "reason": reason, "session_id": session_id})
        unit_refs.append({"unit_id": unit["unit_id"], "packet_path": packet_path, "target_files": unit["target_files"]})
    return {
        "schema": "bears-session-reuse-plan.v1",
        "version": "1",
        "goal_id": str(file_plan.get("goal_id")),
        "delivery_id": str(file_plan.get("delivery_id")),
        "state": "blocked" if errors or file_plan.get("state") == "blocked" else "ready",
        "context_index_version": context_index_version(),
        "units": unit_refs,
        "reuse_decisions": decisions,
        "fanout_groups": fanout_groups(units),
        "errors": errors,
    }


def new_session(unit: dict[str, Any], model_tier: str, ttl_seconds: int, existing_ids: set[str] | None = None) -> dict[str, Any]:
    """Create a compact collision-resistant session record without raw chat context."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    existing = existing_ids or set()
    nonce = 0
    sid = stable_id("session", unit["unit_id"], now.isoformat(), str(nonce))
    while sid in existing:
        nonce += 1
        sid = stable_id("session", unit["unit_id"], now.isoformat(), str(nonce))
    return {
        "session_id": sid,
        "state": "leased",
        "executor": unit["executor"],
        "role_id": unit["role_id"],
        "model_tier": model_tier,
        "repo_root": str(PLUGIN_ROOT),
        "authority_topic": authority_topic(unit),
        "allowed_write_paths": sorted(unit.get("allowed_write_paths", [])),
        "context_index_version": context_index_version(),
        "context_ids": sorted(unit.get("input_context_ids", [])),
        "decision_ids": decision_ids(unit),
        "previous_result_refs": [],
        "usage_summary": {"unit_count": 1, "unit_ids": [unit["unit_id"]], "session_ids": [sid]},
        "last_validated_ref": None,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z"),
        "degraded": False,
        "failed": False,
    }


def command_validate(args: argparse.Namespace) -> int:
    """Validate session reuse policy and sample state packets."""
    errors: list[str] = []
    for path in (POLICY, UNIT_SCHEMA, REUSE_SCHEMA, POOL_SCHEMA):
        if not path.exists():
            errors.append(f"missing required artifact: {path.relative_to(PLUGIN_ROOT)}")
    if POLICY.exists() and policy().get("schema") != "bears-session-reuse-policy.v1":
        errors.append("session reuse policy schema mismatch")
    errors.extend(validate_json_schema(empty_state(), POOL_SCHEMA, "empty-session-pool"))
    print(json.dumps({"schema": "bears-session-pool-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_plan(args: argparse.Namespace) -> int:
    """Emit a session reuse plan for a covered file plan."""
    output_dir = Path(args.output_dir) if args.output_dir else None
    packet = build_reuse_plan(load(Path(args.file_plan)), output_dir)
    errors = validate_json_schema(packet, REUSE_SCHEMA, "session-reuse-plan")
    print(json.dumps({**packet, "validation_errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors and packet["state"] != "blocked" else 1


def command_acquire(args: argparse.Namespace) -> int:
    """Lease a compatible session or create a fresh compact session."""
    unit = load(Path(args.unit))
    pool_path = state_path(args.state)
    pool = load_state(pool_path)
    pool_errors = validate_json_schema(pool, POOL_SCHEMA, "session-pool-state")
    if pool_errors:
        print(json.dumps({"schema": "bears-session-acquire.v1", "status": "fail", "session_id": None, "reuse": False, "reason": "invalid session pool state", "errors": pool_errors}, indent=2, sort_keys=True))
        return 1
    cfg = policy().get("policy", {})
    model_tier = args.model_tier or str(cfg.get("default_model_tier", "standard"))
    enriched_unit = {**unit, "authority_topic": authority_topic(unit), "decision_ids": decision_ids(unit)}
    session_id, reason = select_session(enriched_unit, pool, model_tier)
    if session_id:
        for session in pool["sessions"]:
            if session.get("session_id") == session_id:
                session["state"] = "leased"
                session["updated_at"] = utc_now()
    else:
        existing_ids = {str(session.get("session_id")) for session in pool.get("sessions", []) if session.get("session_id")}
        session = new_session(enriched_unit, model_tier, int(cfg.get("ttl_seconds", 3600)), existing_ids)
        session_id = str(session["session_id"])
        pool["sessions"].append(session)
    pool["updated"] = utc_now()
    write(pool_path, pool)
    errors = validate_json_schema(pool, POOL_SCHEMA, "session-pool-state")
    print(json.dumps({"schema": "bears-session-acquire.v1", "status": "pass" if not errors else "fail", "session_id": session_id, "reuse": reason != "fresh session required", "reason": reason, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_release(args: argparse.Namespace) -> int:
    """Release a leased session and record pass, failed, or degraded status."""
    pool_path = state_path(args.state)
    pool = load_state(pool_path)
    matches = [session for session in pool.get("sessions", []) if session.get("session_id") == args.session]
    if len(matches) != 1:
        errors = ["session not found"] if not matches else ["duplicate session id"]
        print(json.dumps({"schema": "bears-session-release.v1", "status": "fail", "session_id": args.session, "result": args.result, "errors": errors}, indent=2, sort_keys=True))
        return 1
    session = matches[0]
    session["state"] = "available" if args.result == "pass" else "blocked"
    session["failed"] = args.result == "failed"
    session["degraded"] = args.result == "degraded"
    if args.result_packet:
        session.setdefault("previous_result_refs", []).append(args.result_packet)
    session["updated_at"] = utc_now()
    pool["updated"] = utc_now()
    write(pool_path, pool)
    print(json.dumps({"schema": "bears-session-release.v1", "status": "pass", "session_id": args.session, "result": args.result, "errors": []}, indent=2, sort_keys=True))
    return 0


def command_gc(args: argparse.Namespace) -> int:
    """Expire sessions whose TTL has passed."""
    pool_path = state_path(args.state)
    pool = load_state(pool_path)
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    kept = []
    for session in pool.get("sessions", []):
        if parse_time(str(session.get("expires_at"))) <= now:
            expired.append(str(session.get("session_id")))
        else:
            kept.append(session)
    pool["sessions"] = kept
    pool["updated"] = utc_now()
    write(pool_path, pool)
    print(json.dumps({"schema": "bears-session-pool-gc.v1", "status": "pass", "expired_sessions": expired}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=command_validate)
    plan = sub.add_parser("plan")
    plan.add_argument("--file-plan", required=True)
    plan.add_argument("--output-dir")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)
    acquire = sub.add_parser("acquire")
    acquire.add_argument("--unit", required=True)
    acquire.add_argument("--state")
    acquire.add_argument("--model-tier")
    acquire.add_argument("--json", action="store_true")
    acquire.set_defaults(func=command_acquire)
    release = sub.add_parser("release")
    release.add_argument("--session", required=True)
    release.add_argument("--state")
    release.add_argument("--result", choices=("pass", "failed", "degraded"), default="pass")
    release.add_argument("--result-packet")
    release.add_argument("--json", action="store_true")
    release.set_defaults(func=command_release)
    gc = sub.add_parser("gc")
    gc.add_argument("--state")
    gc.add_argument("--json", action="store_true")
    gc.set_defaults(func=command_gc)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the session pool CLI."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
