#!/usr/bin/env python3
"""Fast hook helpers for Bears agentic enterprise workflow."""

from __future__ import annotations

import json
import sys
import time
import importlib.util
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = PLUGIN_ROOT / "scripts/agentic_enterprise_workflow.py"
DEFAULT_STATE = PLUGIN_ROOT / "runtime/agent-workflow/current-enterprise-orchestrator-state/workflow-matrix/orchestrator-state.json"
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/agentic-enterprise-workflow.v1.json"


def _load_controller() -> Any:
    spec = importlib.util.spec_from_file_location("agentic_enterprise_workflow_controller", CONTROLLER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load controller: {CONTROLLER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _ensure_runtime_state(path: Path, catalog: dict[str, Any], event_name: str) -> tuple[dict[str, Any], bool]:
    if path.is_file():
        return _load_json(path), False
    scope_policy = catalog.get("scope_policy") if isinstance(catalog.get("scope_policy"), dict) else {}
    token_budget = scope_policy.get("max_token_budget_default")
    if not isinstance(token_budget, int) or token_budget <= 0:
        token_budget = 12000
    now = time.time()
    state = {
        "schema": "bears-agentic-enterprise-runtime-state.v1",
        "agent_layer": "l1",
        "l1_mode": "normal",
        "state_created_by_hook": True,
        "created_by_event": event_name,
        "started_at_epoch": now,
        "duration_min": 0,
        "token_budget": token_budget,
        "split_state": "none",
        "workflow_block": {"block_goal_run": False},
        "scopes": [],
    }
    _atomic_write_json(path, state)
    return state, True


def _duration_from_state(state: dict[str, Any]) -> float | None:
    started = state.get("started_at_epoch")
    if isinstance(started, (int, float)) and not isinstance(started, bool):
        return max(0.0, (time.time() - float(started)) / 60.0)
    return None


def _has_scope_runtime(state: dict[str, Any]) -> bool:
    """Return true only when the state contains a real task/scope timer."""
    if isinstance(state.get("active_scope"), dict):
        return True
    scopes = state.get("scopes")
    return isinstance(scopes, list) and any(isinstance(scope, dict) for scope in scopes)


def read_stdin_event() -> dict[str, Any]:
    text = sys.stdin.read()
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _event_field(event: dict[str, Any], *names: str) -> str:
    for name in names:
        value = event.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    nested = event.get("metadata")
    if isinstance(nested, dict):
        metadata.update(nested)
    for key in (
        "duration_min",
        "durationMin",
        "elapsed_min",
        "elapsedMin",
        "timebox_min",
        "timeboxMin",
        "token_budget",
        "tokenBudget",
        "token_spend",
        "tokenSpend",
        "tokens_used",
        "tokensUsed",
        "split_state",
        "splitState",
        "decomposition_state",
        "decompositionState",
        "throttle_state",
        "throttleState",
    ):
        if key in event:
            metadata[key] = event[key]
    aliases = {
        "durationMin": "duration_min",
        "elapsedMin": "elapsed_min",
        "timeboxMin": "timebox_min",
        "tokenBudget": "token_budget",
        "tokenSpend": "token_spend",
        "tokensUsed": "tokens_used",
        "splitState": "split_state",
        "decompositionState": "decomposition_state",
        "throttleState": "throttle_state",
    }
    for source, target in aliases.items():
        if source in metadata and target not in metadata:
            metadata[target] = metadata[source]
    return metadata


def _codex_hook_stdout(event_name: str, decision: dict[str, Any]) -> dict[str, Any]:
    """Return the current Codex hook stdout shape for command hooks."""
    reason = str(decision.get("reason") or "").strip() or "Bears workflow hook blocked this action."
    hook_specific: dict[str, Any] = {"hookEventName": event_name}
    if decision.get("decision") == "deny":
        if event_name == "PreToolUse":
            hook_specific["permissionDecision"] = "deny"
            hook_specific["permissionDecisionReason"] = reason
            return {"hookSpecificOutput": hook_specific}
        if event_name == "UserPromptSubmit":
            return {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": hook_specific,
            }
    if event_name == "SessionStart":
        agent_message = decision.get("agent_message")
        if isinstance(agent_message, str) and agent_message.strip():
            hook_specific["additionalContext"] = agent_message.strip()
    elif event_name == "UserPromptSubmit":
        control_status = decision.get("control_status")
        control_reason = decision.get("control_reason")
        if control_status == "armed" and isinstance(control_reason, str) and control_reason:
            hook_specific["additionalContext"] = f"Bears workflow guard: {control_reason}"
    return {"hookSpecificOutput": hook_specific}


def run_decision(event_name: str, event: dict[str, Any]) -> int:
    state_path = _event_field(event, "state_path", "orchestrator_state") or str(DEFAULT_STATE)
    tool_name = _event_field(event, "tool_name", "toolName", "name")
    agent_layer = _event_field(event, "agent_layer", "agentLayer", "layer")
    scope_id = _event_field(event, "scope_id", "scopeId")
    try:
        controller = _load_controller()
        catalog = _load_json(DEFAULT_CATALOG)
        errors = controller.validate_workflow(catalog)
        if errors:
            print(json.dumps({"status": "fail", "errors": errors}, indent=2, sort_keys=True))
            return 1
        state_file = Path(state_path)
        state, state_created = _ensure_runtime_state(state_file, catalog, event_name)
        metadata = _event_metadata(event)
        duration = _duration_from_state(state)
        if duration is not None and not any(key in metadata for key in ("duration_min", "elapsed_min", "active_scope_duration_min", "scope_age_min", "timebox_min")):
            if _has_scope_runtime(state):
                metadata["duration_min"] = duration
        decision = controller.hook_decision(
            event_name,
            state,
            catalog,
            tool_name=tool_name,
            agent_layer=agent_layer or str(state.get("agent_layer", "")),
            scope_id=scope_id,
            metadata=metadata,
        )
        decision["state_path"] = str(state_file)
        decision["state_created"] = state_created
        packet = _codex_hook_stdout(event_name, decision)
        print(json.dumps(packet, indent=2, sort_keys=True))
        if decision.get("decision") == "allow":
            return 0
        reason = str(decision.get("reason") or "").strip() or "Bears workflow hook blocked this action."
        print(reason, file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
