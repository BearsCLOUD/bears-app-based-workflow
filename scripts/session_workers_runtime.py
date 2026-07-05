#!/usr/bin/env python3
"""Validate Bears session worker runtime catalog and runtime packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets" / "catalog" / "session-workers-runtime.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets" / "catalog" / "platform-role-catalog.v1.json"
EXPECTED_SCHEMA = "bears-session-workers-runtime.v1"
EXPECTED_OWNER = "bears"
REQUIRED_RUNTIME_VALIDATION_COMMAND = "python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>"
REQUIRED_LANES = [
    "constitution",
    "specification",
    "planning",
    "docs",
    "auth",
    "gateway",
    "deploy",
    "validation",
    "review",
    "audit",
    "implementation",
]
REQUIRED_STATES = [
    "available",
    "claimed",
    "running",
    "waiting",
    "blocked",
    "stale",
    "completed",
    "closed",
]
REQUIRED_RUNTIME_ARTIFACTS = {
    "session-workers.json": "bears-session-workers.v1",
    "orchestration-state.json": "bears-session-orchestration-state.v1",
    "worker-heartbeat.json": "bears-worker-heartbeat.v1",
    "worker-closeout.json": "bears-worker-closeout.v1",
    "scope-locks.json": "bears-scope-locks.v1",
    "session-reuse-index.json": "bears-session-reuse-index.v1",
}
REQUIRED_WORKER_FIELDS = {
    "worker_id",
    "status",
    "lane",
    "registered_role",
    "goal_id",
    "roadmap_id",
    "questionnaire_ref",
    "context_policy",
    "spec_id",
    "spec_path",
    "target_paths",
    "allowed_write_scope",
    "forbidden_scope",
    "roadmap_slice",
    "pre_task_hook",
    "reuse_key",
    "spec_kit_snapshot",
    "validation_target",
    "evidence_target",
    "heartbeat_packet",
    "closeout_packet",
    "resume_policy",
}
REQUIRED_SNAPSHOT_FIELDS = {"spec_id", "spec_path", "snapshot_id", "captured_at", "repo_head", "artifacts"}
REQUIRED_SNAPSHOT_ARTIFACT_STATUSES = {"current", "missing", "stale", "blocked"}
REUSE_ENTRY_REQUIRED_FIELDS = {
    "worker_id",
    "reuse_key",
    "goal_id",
    "roadmap_id",
    "lane",
    "registered_role",
    "scope_fingerprint",
    "repo_head",
    "spec_id",
    "spec_path",
    "spec_snapshot_id",
    "roadmap_slice",
    "status",
    "validation_target",
    "continuation_packet_ref",
    "restricted_data_taint",
    "last_validation_at",
    "selection_decision",
}
REUSE_SELECTION_DECISIONS = {"reuse", "fresh", "close_then_fresh"}
REQUIRED_COMPATIBILITY_FIELDS = {
    "goal_compatible",
    "roadmap_compatible",
    "lane_compatible",
    "role_compatible",
    "scope_compatible",
    "repo_state_compatible",
    "spec_kit_snapshot_compatible",
    "roadmap_slice_compatible",
}
REQUIRED_PRE_TASK_HOOK_FIELDS = {
    "hook_id",
    "task_id",
    "task_path",
    "goal_id",
    "roadmap_id",
    "questionnaire_ref",
    "context_policy",
    "spec_id",
    "spec_path",
    "roadmap_slice",
    "repo_head",
    "missing_data_evidence",
    "drift_answer_evidence",
    "task_start_authorization",
}
REQUIRED_TASK_START_ACTIONS = {"spawn", "reuse", "manage", "close"}
AUDIT_CONTEXT_POLICY = "fresh_no_parent_context"
ACTIVE_HEARTBEAT_STATES = {"claimed", "running", "waiting", "blocked", "stale"}
CLOSEOUT_REQUIRED_STATES = {"blocked", "stale", "completed", "closed"}
SECRET_FIELD_MARKERS = ("token", "secret", "password", "private_key", "api_key", "bearer", "authorization")
RESTRICTED_DATA_FIELD_MARKERS = (
    "raw_secret",
    "secret_value",
    "env_file",
    "env_value",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "production_data",
)
CLOSEOUT_LIMITATION_SEVERITIES = {"info", "non_blocking", "blocking"}
CLOSEOUT_CLEAN_CHECKOUT_LANES = {"review", "audit"}
WAIT_CHECKPOINT_REQUIRED_FIELDS = {"target_agent", "expected_artifact", "owner_lane", "timeout", "fallback_action"}
WAIT_CHECKPOINT_FIRST_TIMEOUT_FIELDS = {"waiting_for", "owner", "needed_artifact", "next_action_if_timeout_repeats"}
WAIT_CHECKPOINT_REPEATED_TIMEOUT_ACTIONS = {"local_read_only_check", "delayed_integration", "blocker_escalation"}
WAIT_RESULT_REQUIRED_FIELDS = {
    "requested_target_ids",
    "returned_status_ids",
    "matching_target_ids",
    "stage_advance_allowed",
    "mismatch_code",
    "next_safe_action",
}
WAIT_TARGET_MISMATCH_CODE = "WAIT_AGENT_TARGET_MISMATCH"
WAIT_TARGET_MISMATCH_NEXT_SAFE_ACTIONS = {
    "keep_waiting_original_agents",
    "interrupt_original_agents",
    "explicitly_close_original_agents",
}
FANOUT_ACTIVE_RUNTIME_STATES = {"claimed", "running", "waiting", "blocked", "stale"}
FANOUT_OPEN_RUNTIME_STATES = {"claimed", "running", "waiting", "blocked", "stale", "completed"}
FANOUT_CLOSED_RUNTIME_STATES = {"closed"}
PARTIAL_STATE_BUCKET_ORDER = [
    "active",
    "completed-needs-close",
    "failed-needs-review",
    "unknown-needs-refresh",
    "blocked-needs-parent-action",
]
PARTIAL_STATE_BUCKET_SOURCE_STATES = {
    "active": {"claimed", "running", "waiting", "stale"},
    "completed-needs-close": {"completed"},
    "failed-needs-review": {"capacity", "capacity_error", "error", "errored", "failed"},
    "unknown-needs-refresh": {"missing", "no_status", "null", "unreported", "unknown"},
    "blocked-needs-parent-action": {"blocked"},
}
CAPACITY_BLOCKING_PARTIAL_BUCKETS = set(PARTIAL_STATE_BUCKET_ORDER)


def partial_state_bucket(status: Any) -> str:
    if status is None:
        return "unknown-needs-refresh"
    normalized = str(status).strip().casefold().replace("-", "_").replace(" ", "_")
    if not normalized:
        return "unknown-needs-refresh"
    for bucket in PARTIAL_STATE_BUCKET_ORDER:
        if normalized in PARTIAL_STATE_BUCKET_SOURCE_STATES[bucket]:
            return bucket
    return "unknown-needs-refresh"


def reconcile_partial_subagent_states(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets = {bucket: [] for bucket in PARTIAL_STATE_BUCKET_ORDER}
    for index, record in enumerate(records):
        worker_id = record.get("worker_id") or record.get("id") or f"unknown-{index}"
        if not isinstance(worker_id, str) or not worker_id.strip():
            worker_id = f"unknown-{index}"
        status = record.get("status", record.get("state"))
        buckets[partial_state_bucket(status)].append(worker_id)
    return buckets


def capacity_blocking_worker_ids(reconciled_buckets: dict[str, list[str]]) -> list[str]:
    blocked: list[str] = []
    for bucket in PARTIAL_STATE_BUCKET_ORDER:
        if bucket in CAPACITY_BLOCKING_PARTIAL_BUCKETS:
            blocked.extend(reconciled_buckets.get(bucket, []))
    return blocked


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def load_cli_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}")
    return load_json(path)


def _require_string(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return False
    return True


def _require_object(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return False
    return True


def _require_string_list(value: Any, path: str, errors: list[str], *, non_empty: bool = True) -> bool:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return False
    if non_empty and not value:
        errors.append(f"{path} must be non-empty")
    bad_items = [index for index, item in enumerate(value) if not isinstance(item, str) or not item.strip()]
    if bad_items:
        errors.append(f"{path} must contain only non-empty strings")
        return False
    return True


def _iter_text(value: Any, path: str = "root") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        found: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            found.extend(_iter_text(item, f"{path}[{index}]"))
        return found
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found.extend(_iter_text(item, f"{path}.{key}"))
        return found
    return []


def _validate_no_secret_like_text(payload: dict[str, Any], *, label: str) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_text(payload, label):
        lower = text.casefold()
        if any(marker in lower for marker in SECRET_FIELD_MARKERS) and any(sep in text for sep in ("=", ":")):
            errors.append(f"{path}: must not include secret-like key/value material")
        if any(marker in lower for marker in RESTRICTED_DATA_FIELD_MARKERS):
            errors.append(f"{path}: must not include restricted-data payload markers")
    return errors


def _validate_english_only_text(payload: dict[str, Any], *, label: str) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_text(payload, label):
        if any("\u0400" <= char <= "\u04ff" for char in text):
            errors.append(f"{path}: must use English-only artifact text")
    return errors


def _validate_closeout_limitations(limitations: Any, path: str, errors: list[str], *, final_status: str | None) -> None:
    if limitations is None:
        return
    if not isinstance(limitations, list):
        errors.append(f"{path} must be a list")
        return
    blocking = False
    for index, limitation in enumerate(limitations):
        item_path = f"{path}[{index}]"
        if not _require_object(limitation, item_path, errors):
            continue
        for field in ("code", "severity", "details"):
            _require_string(limitation.get(field), f"{item_path}.{field}", errors)
        severity = limitation.get("severity")
        if severity not in CLOSEOUT_LIMITATION_SEVERITIES:
            errors.append(f"{item_path}.severity must be info, non_blocking, or blocking")
        if severity == "blocking":
            blocking = True
    if blocking and final_status in {"completed", "closed"}:
        errors.append(f"{path} contains blocking limitation for passing closeout status")


def _validate_closeout_checkout(checkout: Any, path: str, errors: list[str], *, require_clean: bool) -> None:
    if checkout is None:
        if require_clean:
            errors.append(f"{path} is required for review and audit closeouts")
        return
    if not _require_object(checkout, path, errors):
        return
    for field in ("type", "path"):
        _require_string(checkout.get(field), f"{path}.{field}", errors)
    for field in ("dirty_shared_checkout_used", "validated_at_expected_sha"):
        if not isinstance(checkout.get(field), bool):
            errors.append(f"{path}.{field} must be a boolean")
    if checkout.get("dirty_shared_checkout_used") is True:
        errors.append(f"{path}.dirty_shared_checkout_used must be false")
    if require_clean and checkout.get("validated_at_expected_sha") is not True:
        errors.append(f"{path}.validated_at_expected_sha must be true for review and audit closeouts")


def _normalize_scope(path: str) -> str:
    text = path.strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    if text.endswith("/") and text != "/":
        text = text[:-1]
    return text


def _path_within_scope(path: str, scope: str) -> bool:
    normalized_path = _normalize_scope(path)
    normalized_scope = _normalize_scope(scope)
    if normalized_path == normalized_scope:
        return True
    if normalized_path.startswith(normalized_scope + "/"):
        return True
    if normalized_path.endswith("/" + normalized_scope):
        return True
    return False


def _stable_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scope_fingerprint(worker: dict[str, Any]) -> str:
    payload = {
        "target_paths": sorted(_normalize_scope(path) for path in worker.get("target_paths", []) if isinstance(path, str)),
        "allowed_write_scope": sorted(
            _normalize_scope(path) for path in worker.get("allowed_write_scope", []) if isinstance(path, str)
        ),
    }
    return "scope:" + _stable_digest(payload)


def reuse_key(worker: dict[str, Any]) -> str:
    snapshot = worker.get("spec_kit_snapshot", {})
    payload = {
        "goal_id": worker.get("goal_id"),
        "roadmap_id": worker.get("roadmap_id"),
        "lane": worker.get("lane"),
        "registered_role": worker.get("registered_role"),
        "scope_fingerprint": scope_fingerprint(worker),
        "repo_head": snapshot.get("repo_head") if isinstance(snapshot, dict) else None,
        "spec_id": worker.get("spec_id"),
        "spec_path": _normalize_scope(worker.get("spec_path", "")) if isinstance(worker.get("spec_path"), str) else None,
        "spec_snapshot_id": snapshot.get("snapshot_id") if isinstance(snapshot, dict) else None,
        "roadmap_slice": worker.get("roadmap_slice"),
    }
    return "session-reuse:" + _stable_digest(payload)


def _lane_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lanes = catalog.get("worker_lanes", [])
    return {
        lane["lane"]: lane
        for lane in lanes
        if isinstance(lane, dict) and isinstance(lane.get("lane"), str)
    }


def _role_names(role_catalog: dict[str, Any]) -> set[str]:
    return {
        role.get("name")
        for role in role_catalog.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }


def _validate_resume_policy(policy: Any, path: str, errors: list[str], *, action_field: str) -> None:
    if not _require_object(policy, path, errors):
        return
    if not _require_string(policy.get(action_field), f"{path}.{action_field}", errors):
        return
    action = policy[action_field]
    if action not in {"resume", "reuse", "fork", "fresh"}:
        errors.append(f"{path}.{action_field} must be one of resume, reuse, fork, fresh")
    compatibility = policy.get("compatibility")
    if not _require_object(compatibility, f"{path}.compatibility", errors):
        return
    missing_fields = sorted(REQUIRED_COMPATIBILITY_FIELDS - set(compatibility))
    if missing_fields:
        errors.append(f"{path}.compatibility missing fields: {', '.join(missing_fields)}")
    for field in sorted(REQUIRED_COMPATIBILITY_FIELDS):
        if field in compatibility and not isinstance(compatibility[field], bool):
            errors.append(f"{path}.compatibility.{field} must be boolean")
    if action in {"resume", "reuse", "fork"}:
        incompatible = [
            field
            for field in sorted(REQUIRED_COMPATIBILITY_FIELDS)
            if compatibility.get(field) is not True
        ]
        if incompatible:
            errors.append(
                f"{path}.{action_field}={action} requires all compatibility fields true; bad fields: {', '.join(incompatible)}"
            )
    if action in {"reuse", "fork"}:
        validation = policy.get("pre_action_validation")
        if not isinstance(validation, dict):
            errors.append(f"{path}.pre_action_validation must be present before {action}")
        else:
            if validation.get("command") != REQUIRED_RUNTIME_VALIDATION_COMMAND:
                errors.append(f"{path}.pre_action_validation.command must be the validate-runtime command")
            if validation.get("exit_code") != 0:
                errors.append(f"{path}.pre_action_validation.exit_code must be 0")
            if validation.get("compatibility_status") != "compatible":
                errors.append(f"{path}.pre_action_validation.compatibility_status must be compatible")
    if not _require_string_list(policy.get("bounded_prior_evidence", []), f"{path}.bounded_prior_evidence", errors, non_empty=False):
        return
    if action == "fresh" and "reason" in policy:
        _require_string(policy.get("reason"), f"{path}.reason", errors)


def validate_catalog(catalog: dict[str, Any], role_catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    roles = _role_names(role_catalog)

    if catalog.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if catalog.get("owner_plugin") != EXPECTED_OWNER:
        errors.append(f"owner_plugin must be {EXPECTED_OWNER}")

    truth = catalog.get("truth")
    if _require_object(truth, "truth", errors):
        if truth.get("authority") != "Spec Kit":
            errors.append("truth.authority must be 'Spec Kit'")
        if "truth source" not in str(truth.get("rule", "")):
            errors.append("truth.rule must describe current Spec Kit artifacts as the truth source")

    control = catalog.get("control")
    if _require_object(control, "control", errors):
        if control.get("owner") != "Bears plugin":
            errors.append("control.owner must be 'Bears plugin'")
        if control.get("role_catalog") != "assets/catalog/platform-role-catalog.v1.json":
            errors.append("control.role_catalog must point to assets/catalog/platform-role-catalog.v1.json")
        if control.get("validator") != "scripts/session_workers_runtime.py":
            errors.append("control.validator must point to scripts/session_workers_runtime.py")
        if control.get("docs") != "docs/reference/session-workers-runtime.md":
            errors.append("control.docs must point to docs/reference/session-workers-runtime.md")

    work = catalog.get("work")
    if _require_object(work, "work", errors):
        if work.get("surface") != "Codex sessions/session workers":
            errors.append("work.surface must be 'Codex sessions/session workers'")
        if work.get("session_model_rule") != "Codex sessions are workers, not memory.":
            errors.append("work.session_model_rule must be 'Codex sessions are workers, not memory.'")

    worker_lanes = catalog.get("worker_lanes")
    if not isinstance(worker_lanes, list):
        errors.append("worker_lanes must be a list")
    else:
        lane_names: list[str] = []
        for index, lane in enumerate(worker_lanes):
            if not _require_object(lane, f"worker_lanes[{index}]", errors):
                continue
            if not _require_string(lane.get("lane"), f"worker_lanes[{index}].lane", errors):
                continue
            lane_name = lane["lane"]
            lane_names.append(lane_name)
            _require_string(lane.get("description"), f"worker_lanes[{index}].description", errors)
            if _require_string_list(lane.get("allowed_roles"), f"worker_lanes[{index}].allowed_roles", errors):
                unknown_roles = sorted(set(lane["allowed_roles"]) - roles)
                if unknown_roles:
                    errors.append(
                        f"worker_lanes[{index}].allowed_roles unknown in subagents roles catalog: {', '.join(unknown_roles)}"
                    )
            _require_string_list(lane.get("artifact_focus"), f"worker_lanes[{index}].artifact_focus", errors)
        if lane_names != REQUIRED_LANES:
            errors.append("worker_lanes must list canonical lanes in the required order")

    if catalog.get("worker_states") != REQUIRED_STATES:
        errors.append("worker_states must match the canonical state order")

    runtime_artifacts = catalog.get("runtime_artifacts")
    if not isinstance(runtime_artifacts, list):
        errors.append("runtime_artifacts must be a list")
    else:
        artifact_map = {
            artifact.get("name"): artifact
            for artifact in runtime_artifacts
            if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
        }
        missing_artifacts = sorted(set(REQUIRED_RUNTIME_ARTIFACTS) - set(artifact_map))
        if missing_artifacts:
            errors.append("runtime_artifacts missing: " + ", ".join(missing_artifacts))
        for name, schema in REQUIRED_RUNTIME_ARTIFACTS.items():
            artifact = artifact_map.get(name)
            if not artifact:
                continue
            if artifact.get("schema") != schema:
                errors.append(f"runtime_artifact {name} schema must be {schema}")
            if artifact.get("required") is not True:
                errors.append(f"runtime_artifact {name} required must be true")
            _require_string(artifact.get("description"), f"runtime_artifact[{name}].description", errors)

    worker_contract = catalog.get("worker_contract")
    if _require_object(worker_contract, "worker_contract", errors):
        required_fields = worker_contract.get("required_fields")
        if not _require_string_list(required_fields, "worker_contract.required_fields", errors):
            required_fields = []
        if set(required_fields) != REQUIRED_WORKER_FIELDS:
            errors.append("worker_contract.required_fields must match the canonical worker field set")
        snapshot_fields = worker_contract.get("spec_kit_snapshot_required_fields")
        if not _require_string_list(snapshot_fields, "worker_contract.spec_kit_snapshot_required_fields", errors):
            snapshot_fields = []
        if set(snapshot_fields) != REQUIRED_SNAPSHOT_FIELDS:
            errors.append("worker_contract.spec_kit_snapshot_required_fields must match the canonical snapshot field set")
        pre_task_fields = worker_contract.get("pre_task_hook_required_fields")
        if not _require_string_list(pre_task_fields, "worker_contract.pre_task_hook_required_fields", errors):
            pre_task_fields = []
        if set(pre_task_fields) != REQUIRED_PRE_TASK_HOOK_FIELDS:
            errors.append("worker_contract.pre_task_hook_required_fields must match the canonical pre-task hook field set")
        if worker_contract.get("reuse_key_field") != "reuse_key":
            errors.append("worker_contract.reuse_key_field must be reuse_key")
        statuses = worker_contract.get("spec_kit_artifact_statuses")
        if not _require_string_list(statuses, "worker_contract.spec_kit_artifact_statuses", errors):
            statuses = []
        if set(statuses) != REQUIRED_SNAPSHOT_ARTIFACT_STATUSES:
            errors.append("worker_contract.spec_kit_artifact_statuses must match the canonical Spec Kit artifact statuses")
        if worker_contract.get("heartbeat_packet_schema") != "bears-worker-heartbeat.v1":
            errors.append("worker_contract.heartbeat_packet_schema must be bears-worker-heartbeat.v1")
        if worker_contract.get("closeout_packet_schema") != "bears-worker-closeout.v1":
            errors.append("worker_contract.closeout_packet_schema must be bears-worker-closeout.v1")

    resume_rule = catalog.get("resume_fork_rule")
    if _require_object(resume_rule, "resume_fork_rule", errors):
        actions = resume_rule.get("allowed_actions")
        if not _require_string_list(actions, "resume_fork_rule.allowed_actions", errors):
            actions = []
        if set(actions) != {"resume", "reuse", "fork", "fresh"}:
            errors.append("resume_fork_rule.allowed_actions must be resume, reuse, fork, fresh")
        if resume_rule.get("required_pre_action_validation") != REQUIRED_RUNTIME_VALIDATION_COMMAND:
            errors.append("resume_fork_rule.required_pre_action_validation must be the validate-runtime command")
        fallback = str(resume_rule.get("fresh_fallback", ""))
        if "fresh session" not in fallback or "bounded prior evidence" not in fallback:
            errors.append("resume_fork_rule.fresh_fallback must require fresh session with bounded prior evidence")
        compatibility_fields = resume_rule.get("compatibility_fields")
        if not _require_string_list(compatibility_fields, "resume_fork_rule.compatibility_fields", errors):
            compatibility_fields = []
        if set(compatibility_fields) != REQUIRED_COMPATIBILITY_FIELDS:
            errors.append("resume_fork_rule.compatibility_fields must match the canonical compatibility field set")
        if resume_rule.get("otherwise_action") != "fresh":
            errors.append("resume_fork_rule.otherwise_action must be fresh")
        rule = str(resume_rule.get("rule", ""))
        if "spawn fresh" not in rule or "Spec Kit truth" not in rule or "roadmap slice" not in rule or "validate-runtime" not in rule:
            errors.append("resume_fork_rule.rule must require validate-runtime and direct incompatible history to fresh work with current Spec Kit truth and roadmap slice")

    concurrency = catalog.get("concurrency_policy")
    if _require_object(concurrency, "concurrency_policy", errors):
        binding_fields = concurrency.get("spec_binding_fields")
        if not _require_string_list(binding_fields, "concurrency_policy.spec_binding_fields", errors):
            binding_fields = []
        if set(binding_fields) != {"spec_id", "spec_path", "spec_kit_snapshot"}:
            errors.append("concurrency_policy.spec_binding_fields must bind spec_id, spec_path, and spec_kit_snapshot")
        rule = str(concurrency.get("rule", ""))
        if "Concurrent workers" not in rule or "one spec_id" not in rule or "one spec_path" not in rule:
            errors.append("concurrency_policy.rule must allow concurrent workers only with one spec_id and one spec_path per worker")
        scope_rule = str(concurrency.get("scope_rule", ""))
        if "scope locks" not in scope_rule:
            errors.append("concurrency_policy.scope_rule must mention scope locks")
        fanout_rule = str(concurrency.get("fanout_preflight_rule", ""))
        for marker in (
            "count active workers and open workers",
            "close completed no-longer-needed workers",
            "reserve critical-path wait slots",
            "spawn bounded batches",
            "WORKFLOW_DRIFT",
            "instead of normal recovery",
        ):
            if marker not in fanout_rule:
                errors.append(f"concurrency_policy.fanout_preflight_rule missing {marker}")
        counted_states = concurrency.get("fanout_counted_worker_states")
        if _require_object(counted_states, "concurrency_policy.fanout_counted_worker_states", errors):
            active = counted_states.get("active")
            if not _require_string_list(active, "concurrency_policy.fanout_counted_worker_states.active", errors):
                active = []
            if set(active) != FANOUT_ACTIVE_RUNTIME_STATES:
                errors.append("concurrency_policy.fanout_counted_worker_states.active must match fanout active states")
            open_states = counted_states.get("open")
            if not _require_string_list(open_states, "concurrency_policy.fanout_counted_worker_states.open", errors):
                open_states = []
            if set(open_states) != FANOUT_OPEN_RUNTIME_STATES:
                errors.append("concurrency_policy.fanout_counted_worker_states.open must match fanout open states")
            closed = counted_states.get("closed")
            if not _require_string_list(closed, "concurrency_policy.fanout_counted_worker_states.closed", errors):
                closed = []
            if set(closed) != FANOUT_CLOSED_RUNTIME_STATES:
                errors.append("concurrency_policy.fanout_counted_worker_states.closed must match closed states")
        if concurrency.get("critical_path_wait_slots_reserved") is not True:
            errors.append("concurrency_policy.critical_path_wait_slots_reserved must be true")
        if concurrency.get("thread_limit_failure_classification") != "WORKFLOW_DRIFT":
            errors.append("concurrency_policy.thread_limit_failure_classification must be WORKFLOW_DRIFT")
        if concurrency.get("thread_limit_failure_normal_recovery_allowed") is not False:
            errors.append("concurrency_policy.thread_limit_failure_normal_recovery_allowed must be false")
        reconciliation = concurrency.get("capacity_fallback_reconciliation")
        if _require_object(reconciliation, "concurrency_policy.capacity_fallback_reconciliation", errors):
            if reconciliation.get("required_before_capacity_fallback") is not True:
                errors.append("concurrency_policy.capacity_fallback_reconciliation.required_before_capacity_fallback must be true")
            reconciliation_rule = str(reconciliation.get("rule", ""))
            for marker in (
                "Before capacity fallback",
                "session tail",
                "dirty checkout",
                "open PR",
                "unknown or completed-open agents are not free capacity",
            ):
                if marker not in reconciliation_rule:
                    errors.append(f"concurrency_policy.capacity_fallback_reconciliation.rule missing {marker}")
            buckets = reconciliation.get("buckets")
            if not isinstance(buckets, list):
                errors.append("concurrency_policy.capacity_fallback_reconciliation.buckets must be a list")
                buckets = []
            bucket_names: list[str] = []
            for index, bucket in enumerate(buckets):
                bucket_path = f"concurrency_policy.capacity_fallback_reconciliation.buckets[{index}]"
                if not _require_object(bucket, bucket_path, errors):
                    continue
                name = bucket.get("bucket")
                if not _require_string(name, f"{bucket_path}.bucket", errors):
                    continue
                bucket_names.append(name)
                expected_sources = PARTIAL_STATE_BUCKET_SOURCE_STATES.get(name)
                if expected_sources is None:
                    errors.append(f"{bucket_path}.bucket must be a canonical partial-state bucket")
                else:
                    sources = bucket.get("source_states")
                    if not _require_string_list(sources, f"{bucket_path}.source_states", errors):
                        sources = []
                    if set(sources) != expected_sources:
                        errors.append(f"{bucket_path}.source_states must match canonical source states for {name}")
                if bucket.get("counts_as_free_capacity") is not False:
                    errors.append(f"{bucket_path}.counts_as_free_capacity must be false")
                _require_string(bucket.get("required_action"), f"{bucket_path}.required_action", errors)
            if bucket_names != PARTIAL_STATE_BUCKET_ORDER:
                errors.append("concurrency_policy.capacity_fallback_reconciliation.buckets must list canonical buckets in order")
            blocking = reconciliation.get("fallback_blocking_buckets")
            if not _require_string_list(
                blocking,
                "concurrency_policy.capacity_fallback_reconciliation.fallback_blocking_buckets",
                errors,
            ):
                blocking = []
            if set(blocking) != CAPACITY_BLOCKING_PARTIAL_BUCKETS:
                errors.append("concurrency_policy.capacity_fallback_reconciliation.fallback_blocking_buckets must block every partial-state bucket")
            free_capacity_rule = str(reconciliation.get("free_capacity_rule", ""))
            for marker in ("closed", "unknown", "completed-open", "not free capacity"):
                if marker not in free_capacity_rule:
                    errors.append(f"concurrency_policy.capacity_fallback_reconciliation.free_capacity_rule missing {marker}")
            duplicate_rule = str(reconciliation.get("duplicate_launch_rule", ""))
            if "same task id" not in duplicate_rule or "partial-state check is clean" not in duplicate_rule:
                errors.append("concurrency_policy.capacity_fallback_reconciliation.duplicate_launch_rule must block duplicate launch for the same task id until clean")
            evidence_checks = reconciliation.get("required_evidence_checks")
            if not _require_string_list(
                evidence_checks,
                "concurrency_policy.capacity_fallback_reconciliation.required_evidence_checks",
                errors,
            ):
                evidence_checks = []
            evidence_text = " ".join(evidence_checks)
            for marker in ("task_complete", "PR URLs", "dirty files", "open PRs"):
                if marker not in evidence_text:
                    errors.append(f"concurrency_policy.capacity_fallback_reconciliation.required_evidence_checks missing {marker}")

    reuse_index = catalog.get("session_reuse_index")
    if _require_object(reuse_index, "session_reuse_index", errors):
        if reuse_index.get("artifact") != "session-reuse-index.json":
            errors.append("session_reuse_index.artifact must be session-reuse-index.json")
        if reuse_index.get("schema") != "bears-session-reuse-index.v1":
            errors.append("session_reuse_index.schema must be bears-session-reuse-index.v1")
        if reuse_index.get("key_algorithm") != "sha256-json-v1":
            errors.append("session_reuse_index.key_algorithm must be sha256-json-v1")
        key_fields = reuse_index.get("key_fields")
        if not _require_string_list(key_fields, "session_reuse_index.key_fields", errors):
            key_fields = []
        expected_key_fields = {
            "goal_id",
            "roadmap_id",
            "lane",
            "registered_role",
            "scope_fingerprint",
            "repo_head",
            "spec_id",
            "spec_path",
            "spec_snapshot_id",
            "roadmap_slice",
        }
        if set(key_fields) != expected_key_fields:
            errors.append("session_reuse_index.key_fields must match the deterministic reuse key fields")
        entry_fields = reuse_index.get("required_entry_fields")
        if not _require_string_list(entry_fields, "session_reuse_index.required_entry_fields", errors):
            entry_fields = []
        if set(entry_fields) != REUSE_ENTRY_REQUIRED_FIELDS:
            errors.append("session_reuse_index.required_entry_fields must match the canonical reuse entry field set")
        selection = reuse_index.get("selection_preflight")
        if _require_object(selection, "session_reuse_index.selection_preflight", errors):
            if selection.get("required_before_spawn") is not True:
                errors.append("session_reuse_index.selection_preflight.required_before_spawn must be true")
            decisions = selection.get("allowed_decisions")
            if not _require_string_list(decisions, "session_reuse_index.selection_preflight.allowed_decisions", errors):
                decisions = []
            if set(decisions) != REUSE_SELECTION_DECISIONS:
                errors.append("session_reuse_index.selection_preflight.allowed_decisions must be reuse, fresh, close_then_fresh")
            if selection.get("direct_spawn_without_preflight") != "policy_bypass_with_reason":
                errors.append("session_reuse_index.selection_preflight.direct_spawn_without_preflight must be policy_bypass_with_reason")
            if "audit" not in set(selection.get("fresh_required_lanes", [])):
                errors.append("session_reuse_index.selection_preflight.fresh_required_lanes must include audit")
            if selection.get("tainted_worker_decision") != "fresh":
                errors.append("session_reuse_index.selection_preflight.tainted_worker_decision must be fresh")
        rule = str(reuse_index.get("rule", ""))
        for marker in ("reuse_key", "session-reuse-index.json", "goal_id", "roadmap_id", "selection_decision", "restricted_data_taint", "validate-runtime"):
            if marker not in rule:
                errors.append(f"session_reuse_index.rule missing {marker}")

    audit = catalog.get("audit_lane_policy")
    if _require_object(audit, "audit_lane_policy", errors):
        if audit.get("lane") != "audit":
            errors.append("audit_lane_policy.lane must be audit")
        if audit.get("required_resume_action") != "fresh":
            errors.append("audit_lane_policy.required_resume_action must be fresh")
        if audit.get("required_context_policy") != AUDIT_CONTEXT_POLICY:
            errors.append(f"audit_lane_policy.required_context_policy must be {AUDIT_CONTEXT_POLICY}")
        if audit.get("parent_context_allowed") is not False:
            errors.append("audit_lane_policy.parent_context_allowed must be false")
        if audit.get("parent_worker_id_allowed") is not False:
            errors.append("audit_lane_policy.parent_worker_id_allowed must be false")
        if audit.get("reuse_allowed") is not False:
            errors.append("audit_lane_policy.reuse_allowed must be false")
        rule = str(audit.get("rule", ""))
        if "fresh" not in rule or "parent context" not in rule or AUDIT_CONTEXT_POLICY not in rule or "reuse disallowed" not in rule:
            errors.append("audit_lane_policy.rule must require fresh_no_parent_context, no parent context, and reuse disallowed")
        parallel = audit.get("parallel_monitoring")
        if _require_object(parallel, "audit_lane_policy.parallel_monitoring", errors):
            if parallel.get("enabled") is not True:
                errors.append("audit_lane_policy.parallel_monitoring.enabled must be true")
            if parallel.get("mode") != "non_blocking_parallel_monitoring":
                errors.append("audit_lane_policy.parallel_monitoring.mode must be non_blocking_parallel_monitoring")
            if parallel.get("implementation_authority") != "forbidden":
                errors.append("audit_lane_policy.parallel_monitoring.implementation_authority must be forbidden")
            if parallel.get("blocks_main_workflow") != "hard_stop_only":
                errors.append("audit_lane_policy.parallel_monitoring.blocks_main_workflow must be hard_stop_only")
            if parallel.get("finding_issue_policy") != "deduplicate_before_create_or_update":
                errors.append("audit_lane_policy.parallel_monitoring.finding_issue_policy must deduplicate before create or update")

    wait_policy = catalog.get("wait_checkpoint_policy")
    if _require_object(wait_policy, "wait_checkpoint_policy", errors):
        if wait_policy.get("long_wait_call") != "wait_agent":
            errors.append("wait_checkpoint_policy.long_wait_call must be wait_agent")
        before_wait = wait_policy.get("required_before_wait_fields")
        if not _require_string_list(before_wait, "wait_checkpoint_policy.required_before_wait_fields", errors):
            before_wait = []
        if set(before_wait) != WAIT_CHECKPOINT_REQUIRED_FIELDS:
            errors.append("wait_checkpoint_policy.required_before_wait_fields must match the long wait checkpoint field set")
        first_timeout = wait_policy.get("first_timeout_checkpoint_fields")
        if not _require_string_list(first_timeout, "wait_checkpoint_policy.first_timeout_checkpoint_fields", errors):
            first_timeout = []
        if set(first_timeout) != WAIT_CHECKPOINT_FIRST_TIMEOUT_FIELDS:
            errors.append("wait_checkpoint_policy.first_timeout_checkpoint_fields must match the first timeout field set")
        repeated_actions = wait_policy.get("repeated_empty_timeout_actions")
        if not _require_string_list(repeated_actions, "wait_checkpoint_policy.repeated_empty_timeout_actions", errors):
            repeated_actions = []
        if set(repeated_actions) != WAIT_CHECKPOINT_REPEATED_TIMEOUT_ACTIONS:
            errors.append("wait_checkpoint_policy.repeated_empty_timeout_actions must match the canonical fallback actions")
        after_wait_fields = wait_policy.get("required_after_wait_result_fields")
        if not _require_string_list(after_wait_fields, "wait_checkpoint_policy.required_after_wait_result_fields", errors):
            after_wait_fields = []
        if set(after_wait_fields) != WAIT_RESULT_REQUIRED_FIELDS:
            errors.append("wait_checkpoint_policy.required_after_wait_result_fields must match the wait result validation field set")
        if wait_policy.get("target_mismatch_code") != WAIT_TARGET_MISMATCH_CODE:
            errors.append(f"wait_checkpoint_policy.target_mismatch_code must be {WAIT_TARGET_MISMATCH_CODE}")
        mismatch_actions = wait_policy.get("target_mismatch_next_safe_actions")
        if not _require_string_list(mismatch_actions, "wait_checkpoint_policy.target_mismatch_next_safe_actions", errors):
            mismatch_actions = []
        if set(mismatch_actions) != WAIT_TARGET_MISMATCH_NEXT_SAFE_ACTIONS:
            errors.append("wait_checkpoint_policy.target_mismatch_next_safe_actions must match the canonical target mismatch actions")
        mismatch_rule = str(wait_policy.get("target_mismatch_rule", ""))
        if (
            "After every wait_agent" not in mismatch_rule
            or "compare returned status keys to requested target ids" not in mismatch_rule
            or WAIT_TARGET_MISMATCH_CODE not in mismatch_rule
            or "stage_advance_allowed must be false" not in mismatch_rule
            or "before dependent work" not in mismatch_rule
        ):
            errors.append("wait_checkpoint_policy.target_mismatch_rule must require target-id comparison, mismatch emission, and no stage advance")
        stage_rule = str(wait_policy.get("stage_advance_rule", ""))
        if "at least one requested target id appears" not in stage_rule or "out-of-band notifications" not in stage_rule:
            errors.append("wait_checkpoint_policy.stage_advance_rule must require a requested target match before dependent work")
        blocker_rule = str(wait_policy.get("blocker_rule", ""))
        if "missing access" not in blocker_rule or "ROLE_COVERAGE_BLOCKER" not in blocker_rule or "stop/rescope" not in blocker_rule:
            errors.append("wait_checkpoint_policy.blocker_rule must limit blockers to the canonical blocker definition")
        final_rule = str(wait_policy.get("final_integration_rule", ""))
        if "evidence artifacts" not in final_rule or "plain waiting is not accepted" not in final_rule:
            errors.append("wait_checkpoint_policy.final_integration_rule must reject plain waiting as integration evidence")

    implementation = catalog.get("implementation_lane_policy")
    if _require_object(implementation, "implementation_lane_policy", errors):
        if implementation.get("lane") != "implementation":
            errors.append("implementation_lane_policy.lane must be implementation")
        if implementation.get("speckit_command") != "/speckit-implement":
            errors.append("implementation_lane_policy.speckit_command must be /speckit-implement")
        rule = str(implementation.get("rule", ""))
        if "controlled implementation lane" not in rule or "not a global executor" not in rule:
            errors.append("implementation_lane_policy.rule must state that /speckit-implement is controlled and not global")

    validation_commands = catalog.get("validation_commands")
    if _require_string_list(validation_commands, "validation_commands", errors):
        commands = set(validation_commands)
        if "python3 scripts/session_workers_runtime.py validate" not in commands:
            errors.append("validation_commands must include catalog validation")
        if "python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>" not in commands:
            errors.append("validation_commands must include runtime validation")

    errors.extend(_validate_no_secret_like_text(catalog, label="catalog"))
    return errors


def _validate_spec_kit_snapshot(
    snapshot: Any,
    path: str,
    errors: list[str],
    *,
    worker_spec_id: str | None = None,
    worker_spec_path: str | None = None,
) -> None:
    if not _require_object(snapshot, path, errors):
        return
    missing = sorted(REQUIRED_SNAPSHOT_FIELDS - set(snapshot))
    if missing:
        errors.append(f"{path} missing fields: {', '.join(missing)}")
    _require_string(snapshot.get("spec_id"), f"{path}.spec_id", errors)
    _require_string(snapshot.get("spec_path"), f"{path}.spec_path", errors)
    _require_string(snapshot.get("snapshot_id"), f"{path}.snapshot_id", errors)
    _require_string(snapshot.get("captured_at"), f"{path}.captured_at", errors)
    _require_string(snapshot.get("repo_head"), f"{path}.repo_head", errors)
    if worker_spec_id and snapshot.get("spec_id") != worker_spec_id:
        errors.append(f"{path}.spec_id must match worker spec_id")
    if worker_spec_path and _normalize_scope(str(snapshot.get("spec_path", ""))) != _normalize_scope(worker_spec_path):
        errors.append(f"{path}.spec_path must match worker spec_path")
    artifacts = snapshot.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{path}.artifacts must be a non-empty list")
        return
    for index, artifact in enumerate(artifacts):
        if not _require_object(artifact, f"{path}.artifacts[{index}]", errors):
            continue
        _require_string(artifact.get("name"), f"{path}.artifacts[{index}].name", errors)
        _require_string(artifact.get("path"), f"{path}.artifacts[{index}].path", errors)
        status = artifact.get("status")
        if not _require_string(status, f"{path}.artifacts[{index}].status", errors):
            continue
        if status not in REQUIRED_SNAPSHOT_ARTIFACT_STATUSES:
            errors.append(f"{path}.artifacts[{index}].status must be one of {sorted(REQUIRED_SNAPSHOT_ARTIFACT_STATUSES)}")


def _validate_pre_task_hook(
    hook: Any,
    path: str,
    errors: list[str],
    *,
    worker: dict[str, Any],
    require_no_parent_context: bool = False,
) -> None:
    if not _require_object(hook, path, errors):
        return
    missing = sorted(REQUIRED_PRE_TASK_HOOK_FIELDS - set(hook))
    if missing:
        errors.append(f"{path} missing fields: {', '.join(missing)}")
    string_fields = REQUIRED_PRE_TASK_HOOK_FIELDS - {
        "missing_data_evidence",
        "drift_answer_evidence",
        "task_start_authorization",
    }
    for field in sorted(string_fields):
        _require_string(hook.get(field), f"{path}.{field}", errors)
    for field in ("goal_id", "roadmap_id", "questionnaire_ref", "context_policy", "spec_id", "spec_path", "roadmap_slice"):
        if hook.get(field) != worker.get(field):
            errors.append(f"{path}.{field} must match worker {field}")
    snapshot = worker.get("spec_kit_snapshot")
    if isinstance(snapshot, dict) and hook.get("repo_head") != snapshot.get("repo_head"):
        errors.append(f"{path}.repo_head must match worker spec_kit_snapshot.repo_head")
    _require_string_list(hook.get("missing_data_evidence"), f"{path}.missing_data_evidence", errors)
    _require_string_list(hook.get("drift_answer_evidence"), f"{path}.drift_answer_evidence", errors)
    authorization = hook.get("task_start_authorization")
    if _require_object(authorization, f"{path}.task_start_authorization", errors):
        if authorization.get("authorized") is not True:
            errors.append(f"{path}.task_start_authorization.authorized must be true")
        _require_string(authorization.get("authorized_by"), f"{path}.task_start_authorization.authorized_by", errors)
        _require_string(authorization.get("authorized_at"), f"{path}.task_start_authorization.authorized_at", errors)
        actions = authorization.get("authorized_actions")
        if _require_string_list(actions, f"{path}.task_start_authorization.authorized_actions", errors):
            missing_actions = sorted(REQUIRED_TASK_START_ACTIONS - set(actions))
            if missing_actions:
                errors.append(
                    f"{path}.task_start_authorization.authorized_actions missing actions: {', '.join(missing_actions)}"
                )
    if require_no_parent_context:
        if "parent_worker_id" in hook:
            errors.append(f"{path}.parent_worker_id is forbidden for audit lane")
        if hook.get("parent_context_allowed") is not False:
            errors.append(f"{path}.parent_context_allowed must be false for audit lane")


def _validate_string_list_value(value: Any, path: str, errors: list[str], *, non_empty: bool = True) -> list[str]:
    if not _require_string_list(value, path, errors, non_empty=non_empty):
        return []
    return list(value)


def _validate_wait_result_validation(result: Any, path: str, errors: list[str]) -> None:
    if not _require_object(result, path, errors):
        return
    missing = sorted(WAIT_RESULT_REQUIRED_FIELDS - set(result))
    if missing:
        errors.append(f"{path} missing wait result validation fields: {', '.join(missing)}")
    requested_ids = _validate_string_list_value(result.get("requested_target_ids"), f"{path}.requested_target_ids", errors)
    returned_ids = _validate_string_list_value(result.get("returned_status_ids"), f"{path}.returned_status_ids", errors)
    matching_ids = _validate_string_list_value(
        result.get("matching_target_ids"),
        f"{path}.matching_target_ids",
        errors,
        non_empty=False,
    )
    if not requested_ids:
        errors.append(f"{path}.requested_target_ids must contain at least one target id")
    expected_matches = sorted(set(requested_ids) & set(returned_ids))
    if sorted(set(matching_ids)) != expected_matches:
        errors.append(f"{path}.matching_target_ids must equal requested_target_ids intersect returned_status_ids")
    stage_allowed = result.get("stage_advance_allowed")
    if not isinstance(stage_allowed, bool):
        errors.append(f"{path}.stage_advance_allowed must be a boolean")
        stage_allowed = False
    mismatch_code = result.get("mismatch_code")
    next_safe_action = result.get("next_safe_action")
    if not expected_matches:
        if stage_allowed is not False:
            errors.append(f"{path}.stage_advance_allowed must be false when no requested target appears")
        if mismatch_code != WAIT_TARGET_MISMATCH_CODE:
            errors.append(f"{path}.mismatch_code must be {WAIT_TARGET_MISMATCH_CODE} when no requested target appears")
        if next_safe_action not in WAIT_TARGET_MISMATCH_NEXT_SAFE_ACTIONS:
            errors.append(f"{path}.next_safe_action must keep waiting, interrupt, or explicitly close original agents")
    else:
        if stage_allowed is not True:
            errors.append(f"{path}.stage_advance_allowed must be true when a requested target appears")
        if mismatch_code not in ("", None):
            errors.append(f"{path}.mismatch_code must be empty when a requested target appears")
        if next_safe_action not in ("accept_matching_wait_result", ""):
            errors.append(f"{path}.next_safe_action must accept the matching wait result when a requested target appears")


def _validate_wait_checkpoint(checkpoint: Any, path: str, errors: list[str]) -> None:
    if not _require_object(checkpoint, path, errors):
        return
    missing = sorted(WAIT_CHECKPOINT_REQUIRED_FIELDS - set(checkpoint))
    if missing:
        errors.append(f"{path} missing long wait fields: {', '.join(missing)}")
    for field in sorted(WAIT_CHECKPOINT_REQUIRED_FIELDS):
        _require_string(checkpoint.get(field), f"{path}.{field}", errors)
    timeout_count = checkpoint.get("timeout_count", 0)
    if not isinstance(timeout_count, int) or timeout_count < 0:
        errors.append(f"{path}.timeout_count must be a non-negative integer")
        timeout_count = 0
    if timeout_count >= 1:
        missing_first_timeout = sorted(WAIT_CHECKPOINT_FIRST_TIMEOUT_FIELDS - set(checkpoint))
        if missing_first_timeout:
            errors.append(f"{path} missing first timeout checkpoint fields: " + ", ".join(missing_first_timeout))
        for field in sorted(WAIT_CHECKPOINT_FIRST_TIMEOUT_FIELDS):
            _require_string(checkpoint.get(field), f"{path}.{field}", errors)
    if timeout_count >= 2:
        action = checkpoint.get("repeated_timeout_action")
        if action not in WAIT_CHECKPOINT_REPEATED_TIMEOUT_ACTIONS:
            errors.append(f"{path}.repeated_timeout_action must be one of " + ", ".join(sorted(WAIT_CHECKPOINT_REPEATED_TIMEOUT_ACTIONS)))
        if action == "blocker_escalation" and checkpoint.get("blocker_definition_match") is not True:
            errors.append(f"{path}.blocker_definition_match must be true when repeated_timeout_action is blocker_escalation")
    if "wait_result_validation" in checkpoint:
        _validate_wait_result_validation(checkpoint.get("wait_result_validation"), f"{path}.wait_result_validation", errors)


def _hooks_match(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    return {field: left.get(field) for field in sorted(REQUIRED_PRE_TASK_HOOK_FIELDS)} == {
        field: right.get(field) for field in sorted(REQUIRED_PRE_TASK_HOOK_FIELDS)
    }


def _resolve_runtime_file(runtime_dir: Path, packet: dict[str, Any], *, expected_name: str, path_label: str, errors: list[str]) -> Path | None:
    if not _require_object(packet, path_label, errors):
        return None
    if packet.get("schema") != REQUIRED_RUNTIME_ARTIFACTS[expected_name]:
        errors.append(f"{path_label}.schema must be {REQUIRED_RUNTIME_ARTIFACTS[expected_name]}")
    raw_path = packet.get("path")
    if not _require_string(raw_path, f"{path_label}.path", errors):
        return None
    if Path(raw_path).name != expected_name:
        errors.append(f"{path_label}.path must end with {expected_name}")
    return runtime_dir / raw_path


def _validate_heartbeat(
    heartbeat: dict[str, Any],
    *,
    runtime_id: str,
    worker: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    if heartbeat.get("schema") != "bears-worker-heartbeat.v1":
        errors.append(f"{path}.schema must be bears-worker-heartbeat.v1")
    if heartbeat.get("runtime_id") != runtime_id:
        errors.append(f"{path}.runtime_id must match session runtime_id")
    for field in ("worker_id", "lane", "registered_role", "summary", "validation_target", "evidence_target", "updated_at"):
        _require_string(heartbeat.get(field), f"{path}.{field}", errors)
    if heartbeat.get("worker_id") != worker.get("worker_id"):
        errors.append(f"{path}.worker_id must match worker record")
    if heartbeat.get("lane") != worker.get("lane"):
        errors.append(f"{path}.lane must match worker record")
    if heartbeat.get("registered_role") != worker.get("registered_role"):
        errors.append(f"{path}.registered_role must match worker record")
    if heartbeat.get("status") != worker.get("status"):
        errors.append(f"{path}.status must match worker status")
    if worker.get("status") == "waiting":
        _validate_wait_checkpoint(heartbeat.get("wait_checkpoint"), f"{path}.wait_checkpoint", errors)
    elif "wait_checkpoint" in heartbeat:
        _validate_wait_checkpoint(heartbeat.get("wait_checkpoint"), f"{path}.wait_checkpoint", errors)
    _validate_pre_task_hook(
        heartbeat.get("pre_task_hook"),
        f"{path}.pre_task_hook",
        errors,
        worker=worker,
        require_no_parent_context=worker.get("lane") == "audit",
    )
    if not _hooks_match(heartbeat.get("pre_task_hook"), worker.get("pre_task_hook")):
        errors.append(f"{path}.pre_task_hook must match worker pre_task_hook")


def _validate_closeout(
    closeout: dict[str, Any],
    *,
    runtime_id: str,
    worker: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    if closeout.get("schema") != "bears-worker-closeout.v1":
        errors.append(f"{path}.schema must be bears-worker-closeout.v1")
    if closeout.get("runtime_id") != runtime_id:
        errors.append(f"{path}.runtime_id must match session runtime_id")
    for field in ("worker_id", "lane", "registered_role", "summary"):
        _require_string(closeout.get(field), f"{path}.{field}", errors)
    if closeout.get("worker_id") != worker.get("worker_id"):
        errors.append(f"{path}.worker_id must match worker record")
    if closeout.get("lane") != worker.get("lane"):
        errors.append(f"{path}.lane must match worker record")
    if closeout.get("registered_role") != worker.get("registered_role"):
        errors.append(f"{path}.registered_role must match worker record")
    final_status = closeout.get("final_status")
    if not _require_string(final_status, f"{path}.final_status", errors):
        return
    if final_status not in {"blocked", "stale", "completed", "closed"}:
        errors.append(f"{path}.final_status must be blocked, stale, completed, or closed")
    if worker.get("status") in CLOSEOUT_REQUIRED_STATES and final_status != worker.get("status"):
        errors.append(f"{path}.final_status must match terminal worker status")
    _require_string_list(closeout.get("changed_files"), f"{path}.changed_files", errors, non_empty=False)
    _require_string_list(closeout.get("validation_commands"), f"{path}.validation_commands", errors, non_empty=False)
    require_evidence = final_status in {"completed", "closed"}
    evidence = closeout.get("evidence")
    _require_string_list(evidence, f"{path}.evidence", errors, non_empty=require_evidence)
    if require_evidence and isinstance(evidence, list):
        normalized_evidence = {str(item).strip().casefold() for item in evidence}
        if normalized_evidence and normalized_evidence <= {"waiting", "still waiting", "plain waiting"}:
            errors.append(f"{path}.evidence must cite evidence artifacts, not plain waiting")
    _validate_pre_task_hook(
        closeout.get("pre_task_hook"),
        f"{path}.pre_task_hook",
        errors,
        worker=worker,
        require_no_parent_context=worker.get("lane") == "audit",
    )
    if not _hooks_match(closeout.get("pre_task_hook"), worker.get("pre_task_hook")):
        errors.append(f"{path}.pre_task_hook must match worker pre_task_hook")
    _validate_closeout_limitations(
        closeout.get("limitations"),
        f"{path}.limitations",
        errors,
        final_status=final_status if isinstance(final_status, str) else None,
    )
    _validate_closeout_checkout(
        closeout.get("checkout"),
        f"{path}.checkout",
        errors,
        require_clean=worker.get("lane") in CLOSEOUT_CLEAN_CHECKOUT_LANES,
    )
    errors.extend(_validate_english_only_text(closeout, label=path))
    _validate_resume_policy(closeout.get("resume_recommendation"), f"{path}.resume_recommendation", errors, action_field="action")


def _validate_worker(
    worker: Any,
    *,
    index: int,
    runtime_dir: Path,
    runtime_id: str,
    lane_map: dict[str, dict[str, Any]],
    role_names: set[str],
    errors: list[str],
) -> dict[str, Any] | None:
    path = f"workers[{index}]"
    if not _require_object(worker, path, errors):
        return None
    missing_fields = sorted(REQUIRED_WORKER_FIELDS - set(worker))
    if missing_fields:
        errors.append(f"{path} missing fields: {', '.join(missing_fields)}")
    worker_id = worker.get("worker_id")
    if not _require_string(worker_id, f"{path}.worker_id", errors):
        return None
    status = worker.get("status")
    if not _require_string(status, f"{path}.status", errors):
        return None
    if status not in REQUIRED_STATES:
        errors.append(f"{path}.status must be one of {REQUIRED_STATES}")
    lane = worker.get("lane")
    if not _require_string(lane, f"{path}.lane", errors):
        return None
    if lane not in lane_map:
        errors.append(f"{path}.lane must be one of the canonical lanes")
        return None
    role = worker.get("registered_role")
    if not _require_string(role, f"{path}.registered_role", errors):
        return None
    if role not in role_names:
        errors.append(f"{path}.registered_role must exist in subagents roles catalog")
    else:
        allowed_roles = set(lane_map[lane].get("allowed_roles", []))
        if role not in allowed_roles:
            errors.append(f"{path}.registered_role {role} is not allowed for lane {lane}")

    _require_string(worker.get("goal_id"), f"{path}.goal_id", errors)
    _require_string(worker.get("roadmap_id"), f"{path}.roadmap_id", errors)
    _require_string(worker.get("questionnaire_ref"), f"{path}.questionnaire_ref", errors)
    _require_string(worker.get("context_policy"), f"{path}.context_policy", errors)
    spec_id = worker.get("spec_id")
    _require_string(spec_id, f"{path}.spec_id", errors)
    spec_path = worker.get("spec_path")
    _require_string(spec_path, f"{path}.spec_path", errors)
    _require_string(worker.get("roadmap_slice"), f"{path}.roadmap_slice", errors)

    for field in ("target_paths", "allowed_write_scope", "forbidden_scope"):
        _require_string_list(worker.get(field), f"{path}.{field}", errors)
    target_paths = worker.get("target_paths") if isinstance(worker.get("target_paths"), list) else []
    allowed = worker.get("allowed_write_scope") if isinstance(worker.get("allowed_write_scope"), list) else []
    forbidden = worker.get("forbidden_scope") if isinstance(worker.get("forbidden_scope"), list) else []
    for target in target_paths:
        if allowed and not any(_path_within_scope(target, scope) for scope in allowed):
            errors.append(f"{path}.target_paths item {target!r} is outside allowed_write_scope")
        if any(_path_within_scope(target, scope) for scope in forbidden):
            errors.append(f"{path}.target_paths item {target!r} must not be inside forbidden_scope")

    _validate_spec_kit_snapshot(
        worker.get("spec_kit_snapshot"),
        f"{path}.spec_kit_snapshot",
        errors,
        worker_spec_id=spec_id if isinstance(spec_id, str) else None,
        worker_spec_path=spec_path if isinstance(spec_path, str) else None,
    )
    _validate_pre_task_hook(worker.get("pre_task_hook"), f"{path}.pre_task_hook", errors, worker=worker, require_no_parent_context=lane == "audit")
    expected_reuse_key = reuse_key(worker)
    if worker.get("reuse_key") != expected_reuse_key:
        errors.append(f"{path}.reuse_key must be deterministic from lane, role, scope, repo state, Spec Kit snapshot, and roadmap slice")
    _require_string(worker.get("validation_target"), f"{path}.validation_target", errors)
    _require_string(worker.get("evidence_target"), f"{path}.evidence_target", errors)

    if worker.get("executor_command") == "/speckit-implement" and lane != "implementation":
        errors.append(f"{path}.executor_command /speckit-implement is allowed only in lane implementation")

    _validate_resume_policy(worker.get("resume_policy"), f"{path}.resume_policy", errors, action_field="requested_action")
    resume_policy = worker.get("resume_policy")
    if isinstance(resume_policy, dict):
        if lane == "audit":
            if worker.get("context_policy") != AUDIT_CONTEXT_POLICY:
                errors.append(f"{path}.context_policy must be {AUDIT_CONTEXT_POLICY} for audit lane")
            if "parent_worker_id" in worker:
                errors.append(f"{path}.parent_worker_id is forbidden for audit lane")
            if resume_policy.get("requested_action") != "fresh":
                errors.append(f"{path}.resume_policy.requested_action must be fresh for audit lane")
            if resume_policy.get("bounded_prior_evidence"):
                errors.append(f"{path}.resume_policy.bounded_prior_evidence must be empty for audit lane")
        if resume_policy.get("reuse_key") not in {None, worker.get("reuse_key")}:
            errors.append(f"{path}.resume_policy.reuse_key must match worker reuse_key")

    heartbeat_path = _resolve_runtime_file(
        runtime_dir,
        worker.get("heartbeat_packet"),
        expected_name="worker-heartbeat.json",
        path_label=f"{path}.heartbeat_packet",
        errors=errors,
    )
    closeout_path = _resolve_runtime_file(
        runtime_dir,
        worker.get("closeout_packet"),
        expected_name="worker-closeout.json",
        path_label=f"{path}.closeout_packet",
        errors=errors,
    )

    if status in ACTIVE_HEARTBEAT_STATES:
        if heartbeat_path is None or not heartbeat_path.is_file():
            errors.append(f"{path} status {status} requires an existing worker-heartbeat.json")
        else:
            _validate_heartbeat(load_json(heartbeat_path), runtime_id=runtime_id, worker=worker, path=f"{path}.heartbeat_file", errors=errors)
    elif heartbeat_path is not None and heartbeat_path.is_file():
        _validate_heartbeat(load_json(heartbeat_path), runtime_id=runtime_id, worker=worker, path=f"{path}.heartbeat_file", errors=errors)

    if status in CLOSEOUT_REQUIRED_STATES:
        if closeout_path is None or not closeout_path.is_file():
            errors.append(f"{path} status {status} requires an existing worker-closeout.json")
        else:
            _validate_closeout(load_json(closeout_path), runtime_id=runtime_id, worker=worker, path=f"{path}.closeout_file", errors=errors)
    elif closeout_path is not None and closeout_path.is_file():
        _validate_closeout(load_json(closeout_path), runtime_id=runtime_id, worker=worker, path=f"{path}.closeout_file", errors=errors)

    return worker


def validate_runtime(runtime_dir: Path, catalog: dict[str, Any], role_catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lane_map = _lane_map(catalog)
    role_names = _role_names(role_catalog)

    session_workers_path = runtime_dir / "session-workers.json"
    orchestration_path = runtime_dir / "orchestration-state.json"
    scope_locks_path = runtime_dir / "scope-locks.json"
    reuse_index_path = runtime_dir / "session-reuse-index.json"

    for required_path in (session_workers_path, orchestration_path, scope_locks_path, reuse_index_path):
        if not required_path.is_file():
            errors.append(f"missing runtime artifact: {required_path}")
    if errors:
        return errors

    session_workers = load_json(session_workers_path)
    orchestration = load_json(orchestration_path)
    scope_locks = load_json(scope_locks_path)
    reuse_index = load_json(reuse_index_path)

    if session_workers.get("schema") != "bears-session-workers.v1":
        errors.append("session-workers.json schema must be bears-session-workers.v1")
    runtime_id = session_workers.get("runtime_id")
    if not _require_string(runtime_id, "session-workers.runtime_id", errors):
        return errors
    if session_workers.get("truth") != "Spec Kit":
        errors.append("session-workers.json truth must be 'Spec Kit'")
    if session_workers.get("control") != "bears":
        errors.append("session-workers.json control must be 'bears'")
    if session_workers.get("work") != "Codex sessions/session workers":
        errors.append("session-workers.json work must be 'Codex sessions/session workers'")

    workers = session_workers.get("workers")
    if not isinstance(workers, list) or not workers:
        errors.append("session-workers.json workers must be a non-empty list")
        return errors

    worker_records: dict[str, dict[str, Any]] = {}
    for index, worker in enumerate(workers):
        validated = _validate_worker(
            worker,
            index=index,
            runtime_dir=runtime_dir,
            runtime_id=runtime_id,
            lane_map=lane_map,
            role_names=role_names,
            errors=errors,
        )
        if validated is None:
            continue
        worker_id = validated["worker_id"]
        if worker_id in worker_records:
            errors.append(f"duplicate worker_id: {worker_id}")
        worker_records[worker_id] = validated

    if orchestration.get("schema") != "bears-session-orchestration-state.v1":
        errors.append("orchestration-state.json schema must be bears-session-orchestration-state.v1")
    if orchestration.get("runtime_id") != runtime_id:
        errors.append("orchestration-state.json runtime_id must match session-workers.json")
    overall_status = orchestration.get("overall_status")
    if not _require_string(overall_status, "orchestration-state.overall_status", errors):
        pass
    elif overall_status not in REQUIRED_STATES:
        errors.append("orchestration-state.overall_status must be a canonical state")
    workers_by_state = orchestration.get("workers_by_state")
    if not _require_object(workers_by_state, "orchestration-state.workers_by_state", errors):
        workers_by_state = {}
    else:
        state_membership: dict[str, str] = {}
        for state in REQUIRED_STATES:
            ids = workers_by_state.get(state)
            if not _require_string_list(ids, f"orchestration-state.workers_by_state.{state}", errors, non_empty=False):
                continue
            for worker_id in ids:
                if worker_id not in worker_records:
                    errors.append(f"orchestration-state state {state} references unknown worker_id {worker_id}")
                    continue
                if worker_records[worker_id].get("status") != state:
                    errors.append(f"orchestration-state state {state} mismatches worker status for {worker_id}")
                if worker_id in state_membership and state_membership[worker_id] != state:
                    errors.append(f"worker_id {worker_id} appears in multiple orchestration states")
                state_membership[worker_id] = state
        missing_state_entries = sorted(set(worker_records) - set(state_membership))
        if missing_state_entries:
            errors.append("orchestration-state missing worker ids: " + ", ".join(missing_state_entries))
    if orchestration.get("scope_locks_file") != "scope-locks.json":
        errors.append("orchestration-state.scope_locks_file must be scope-locks.json")

    if scope_locks.get("schema") != "bears-scope-locks.v1":
        errors.append("scope-locks.json schema must be bears-scope-locks.v1")
    if scope_locks.get("runtime_id") != runtime_id:
        errors.append("scope-locks.json runtime_id must match session-workers.json")
    locks = scope_locks.get("locks")
    if not isinstance(locks, list):
        errors.append("scope-locks.json locks must be a list")
        locks = []
    lock_targets: dict[str, str] = {}
    for index, lock in enumerate(locks):
        lock_path = f"scope-locks.locks[{index}]"
        if not _require_object(lock, lock_path, errors):
            continue
        for field in ("lock_id", "target_path", "owner_worker_id", "lane", "status"):
            _require_string(lock.get(field), f"{lock_path}.{field}", errors)
        owner = lock.get("owner_worker_id")
        if isinstance(owner, str):
            if owner not in worker_records:
                errors.append(f"{lock_path}.owner_worker_id must reference a known worker")
                continue
            if lock.get("lane") != worker_records[owner].get("lane"):
                errors.append(f"{lock_path}.lane must match owner worker lane")
            if lock.get("status") != worker_records[owner].get("status"):
                errors.append(f"{lock_path}.status must match owner worker status")
        target_path = lock.get("target_path")
        if isinstance(target_path, str) and isinstance(owner, str):
            for existing_target, existing_owner in lock_targets.items():
                if existing_owner != owner and (
                    _path_within_scope(target_path, existing_target) or _path_within_scope(existing_target, target_path)
                ):
                    errors.append(f"overlapping active scope lock on {target_path} by {owner} and {existing_target} by {existing_owner}")
            lock_targets[target_path] = owner

    if reuse_index.get("schema") != "bears-session-reuse-index.v1":
        errors.append("session-reuse-index.json schema must be bears-session-reuse-index.v1")
    if reuse_index.get("runtime_id") != runtime_id:
        errors.append("session-reuse-index.json runtime_id must match session-workers.json")
    if reuse_index.get("key_algorithm") != "sha256-json-v1":
        errors.append("session-reuse-index.json key_algorithm must be sha256-json-v1")
    entries = reuse_index.get("entries")
    if not isinstance(entries, list):
        errors.append("session-reuse-index.json entries must be a list")
        entries = []
    index_by_worker: dict[str, dict[str, Any]] = {}
    reuse_keys: dict[str, str] = {}
    for index, entry in enumerate(entries):
        entry_path = f"session-reuse-index.entries[{index}]"
        if not _require_object(entry, entry_path, errors):
            continue
        missing_entry_fields = sorted(REUSE_ENTRY_REQUIRED_FIELDS - set(entry))
        if missing_entry_fields:
            errors.append(f"{entry_path} missing fields: {', '.join(missing_entry_fields)}")
        for field in (
            "worker_id",
            "reuse_key",
            "goal_id",
            "roadmap_id",
            "lane",
            "registered_role",
            "scope_fingerprint",
            "repo_head",
            "spec_id",
            "spec_path",
            "spec_snapshot_id",
            "roadmap_slice",
            "status",
            "validation_target",
            "continuation_packet_ref",
            "last_validation_at",
            "selection_decision",
        ):
            _require_string(entry.get(field), f"{entry_path}.{field}", errors)
        if not isinstance(entry.get("restricted_data_taint"), bool):
            errors.append(f"{entry_path}.restricted_data_taint must be a boolean")
        if entry.get("selection_decision") not in REUSE_SELECTION_DECISIONS:
            errors.append(f"{entry_path}.selection_decision must be reuse, fresh, or close_then_fresh")
        worker_id = entry.get("worker_id")
        if not isinstance(worker_id, str) or worker_id not in worker_records:
            errors.append(f"{entry_path}.worker_id must reference a known worker")
            continue
        worker = worker_records[worker_id]
        expected_fields = {
            "reuse_key": worker.get("reuse_key"),
            "goal_id": worker.get("goal_id"),
            "roadmap_id": worker.get("roadmap_id"),
            "lane": worker.get("lane"),
            "registered_role": worker.get("registered_role"),
            "scope_fingerprint": scope_fingerprint(worker),
            "repo_head": worker.get("spec_kit_snapshot", {}).get("repo_head") if isinstance(worker.get("spec_kit_snapshot"), dict) else None,
            "spec_id": worker.get("spec_id"),
            "spec_path": worker.get("spec_path"),
            "spec_snapshot_id": worker.get("spec_kit_snapshot", {}).get("snapshot_id") if isinstance(worker.get("spec_kit_snapshot"), dict) else None,
            "roadmap_slice": worker.get("roadmap_slice"),
            "status": worker.get("status"),
            "validation_target": worker.get("validation_target"),
            "continuation_packet_ref": worker.get("closeout_packet", {}).get("path") if isinstance(worker.get("closeout_packet"), dict) else None,
        }
        for field, expected in expected_fields.items():
            if entry.get(field) != expected:
                errors.append(f"{entry_path}.{field} must match worker {worker_id}")
        if entry.get("selection_decision") == "reuse" and entry.get("restricted_data_taint") is not False:
            errors.append(f"{entry_path}.restricted_data_taint must be false when selection_decision is reuse")
        if entry.get("selection_decision") == "reuse" and entry.get("continuation_packet_ref") != worker.get("closeout_packet", {}).get("path"):
            errors.append(f"{entry_path}.continuation_packet_ref must reference the worker closeout packet for reuse")
        if worker.get("lane") == "audit" and entry.get("reuse_allowed") is not False:
            errors.append(f"{entry_path}.reuse_allowed must be false for audit lane")
        if worker.get("lane") == "audit" and entry.get("selection_decision") == "reuse":
            errors.append(f"{entry_path}.selection_decision must not be reuse for audit lane")
        if worker.get("lane") != "audit" and not isinstance(entry.get("reuse_allowed"), bool):
            errors.append(f"{entry_path}.reuse_allowed must be boolean")
        key = entry.get("reuse_key")
        if isinstance(key, str):
            if key in reuse_keys and reuse_keys[key] != worker_id:
                errors.append(f"duplicate reuse_key {key} for workers {worker_id} and {reuse_keys[key]}")
            reuse_keys[key] = worker_id
        index_by_worker[worker_id] = entry
    missing_index_workers = sorted(set(worker_records) - set(index_by_worker))
    if missing_index_workers:
        errors.append("session-reuse-index missing worker ids: " + ", ".join(missing_index_workers))

    errors.extend(_validate_no_secret_like_text(session_workers, label="session-workers"))
    errors.extend(_validate_no_secret_like_text(orchestration, label="orchestration-state"))
    errors.extend(_validate_no_secret_like_text(scope_locks, label="scope-locks"))
    errors.extend(_validate_no_secret_like_text(reuse_index, label="session-reuse-index"))
    return errors


def render_summary(catalog: dict[str, Any]) -> str:
    lanes = ", ".join(lane["lane"] for lane in catalog.get("worker_lanes", []) if isinstance(lane, dict) and isinstance(lane.get("lane"), str))
    states = ", ".join(catalog.get("worker_states", []))
    artifacts = ", ".join(
        artifact["name"]
        for artifact in catalog.get("runtime_artifacts", [])
        if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
    )
    return "\n".join(
        [
            f"runtime: {catalog.get('runtime_id', '<unknown>')}",
            f"lanes: {lanes}",
            f"states: {states}",
            f"artifacts: {artifacts}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="session workers runtime catalog path")
    parser.add_argument("--role-catalog", default=str(DEFAULT_ROLE_CATALOG), help="subagents roles catalog path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate catalog only")
    validate_runtime_parser = sub.add_parser("validate-runtime", help="validate a runtime directory")
    validate_runtime_parser.add_argument("--runtime-dir", required=True, help="runtime directory containing session worker packets")
    sub.add_parser("summary", help="print compact non-secret summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_cli_json(Path(args.catalog), label="catalog")
        role_catalog = load_cli_json(Path(args.role_catalog), label="catalog")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "summary":
        print(render_summary(catalog))
        return 0

    errors = validate_catalog(catalog, role_catalog)
    if args.command == "validate-runtime" and not errors:
        try:
            runtime_dir = Path(args.runtime_dir)
            errors.extend(validate_runtime(runtime_dir, catalog, role_catalog))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.command == "validate-runtime":
        print(f"session worker runtime ok: {args.runtime_dir}")
    else:
        print(f"session worker runtime catalog ok: {args.catalog}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
