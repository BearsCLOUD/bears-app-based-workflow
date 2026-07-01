#!/usr/bin/env python3
"""Validate Bears agentic enterprise workflow catalogs and compact packets."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONSTITUTION = PLUGIN_ROOT / "assets/catalog/agentic-enterprise-constitution.v1.json"
DEFAULT_WORKFLOW = PLUGIN_ROOT / "assets/catalog/agentic-enterprise-workflow.v1.json"
DEFAULT_HOOKS_JSON = PLUGIN_ROOT / "hooks.json"
DEFAULT_SCOPE_MATRIX_SCHEMA = "bears-scope-matrix.v1"
DEFAULT_DECISION_LOG_SCHEMA = "bears-decision-log.v1"
CONSTITUTION_SCHEMA = "bears-agentic-enterprise-constitution.v1"
WORKFLOW_SCHEMA = "bears-agentic-enterprise-workflow.v1"
REQUIRED_REPO_DOMAINS = ["platform", "gitops", "infra", "product_infra"]
REQUIRED_DECISION_TYPES = [
    "user_fact",
    "user_directive",
    "agent_decision",
    "contradiction",
    "needs_user_input",
]
REQUIRED_DEGRADATION_ACTIONS = [
    "continue",
    "throttle_scope",
    "isolate_scope",
    "block_workflow",
    "rollback_runtime_activation",
]
REQUIRED_STAGE_PREFIX = [
    "scope_row",
    "research",
    "clarification_gate",
    "l1_task_decomposition",
    "l2_governance_review",
]
REQUIRED_GOAL_AGENT_MODES = ("goal_1_agent", "goal_parallel_l1")
REQUIRED_GOAL_1_AGENT_SEQUENCE = [
    "create_own_state_file",
    "research",
    "decompose_operator_goal_prompt_into_scopes",
    "persist_scopes_in_state",
    "solve_scopes_sequentially_through_bears_spec_kit_flow",
    "use_helper_agents_for_token_economy_git_ci_cache_closeout_review_fix_support",
]
REQUIRED_GOAL_PARALLEL_L1_SEQUENCE = [
    "create_own_state_file",
    "normalize_operator_goal_prompt_into_scopes",
    "persist_scopes_in_state",
    "selected_scope_research",
    "selected_scope_development_area_design",
    "selected_scope_requirements",
    "selected_scope_spec_kit_logic",
    "spawn_l2_subagent_for_approved_spec_kit_plan",
    "continue_own_sequential_workflow",
]
REQUIRED_HELPER_PURPOSES = ("token_economy", "git_ci_cache_closeout", "review_fix_support")
CONTROL_NOT_ARMED_CODE = "control_not_armed"
MISSING_CONTROL_METADATA_REASON = "control_not_armed: missing scope time or token metadata"
NO_SPLIT_STATES = {"", "none", "missing", "not_started", "false", "0"}
ACTIVE_CONTROL_EVENTS = {"PreTask", "UserPromptSubmit", "PreToolUse"}
REQUIRED_HOOK_COMMAND_SCRIPTS = {
    "SessionStart": "hooks/session_start.py",
    "UserPromptSubmit": "hooks/pre_task_guard.py",
    "PreToolUse": "hooks/pre_tool_policy.py",
    "Stop": "hooks/stop_closeout_guard.py",
}
REQUIRED_CONSTITUTION_PRINCIPLES = {
    "docs_as_code",
    "contract_first",
    "schema_first",
    "dry",
    "modularity",
    "single_responsibility",
    "reusable_executable_logic",
    "interface_based_design",
    "composition_over_inheritance",
    "executable_validation",
    "bounded_context",
    "file_backed_state",
    "no_hidden_state",
    "deterministic_output",
    "idempotency",
    "fixtures_as_proof",
    "metrics_required",
    "docs_causal_map",
    "role_gated_edits",
    "boundary_first",
    "fail_closed",
    "versioned_contracts",
    "backward_compatibility",
    "single_source_of_truth",
    "policy_as_code",
    "observability_as_code",
    "small_composable_units",
    "golden_path",
    "adr",
}
L1_ALLOWED_TOOLS = {
    "orchestrator_controller",
    "agentic_enterprise_workflow",
    "write_task_decomposition",
    "write_l2_governance_packet",
    "block_goal_run",
    "unblock_goal_run",
    "emit_l1_summary",
}
L1_DENY_TOOL_PREFIXES = (
    "mcp__",
    "tool_search",
    "list_available_plugins_to_install",
    "request_plugin_install",
    "web.",
    "image_gen.",
)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_hook_wiring(path: Path = DEFAULT_HOOKS_JSON) -> list[str]:
    errors: list[str] = []
    try:
        packet = _load_json(path)
    except Exception as exc:  # noqa: BLE001
        return [f"hooks.json must be readable JSON: {exc}"]
    hooks = packet.get("hooks")
    if not isinstance(hooks, dict):
        return ["hooks.json.hooks must be an object"]
    expected_events = set(REQUIRED_HOOK_COMMAND_SCRIPTS)
    if set(hooks) != expected_events:
        errors.append("hooks.json.hooks must contain exactly: " + ", ".join(sorted(expected_events)))
    for event, script in REQUIRED_HOOK_COMMAND_SCRIPTS.items():
        entries = hooks.get(event)
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            errors.append(f"hooks.json.{event} must contain exactly one hook group")
            continue
        group = entries[0]
        if event == "SessionStart" and group.get("matcher") != "startup|resume":
            errors.append("hooks.json.SessionStart.matcher must be startup|resume")
        if event == "PreToolUse" and group.get("matcher") != "*":
            errors.append("hooks.json.PreToolUse.matcher must be *")
        commands = group.get("hooks")
        if not isinstance(commands, list) or len(commands) != 1 or not isinstance(commands[0], dict):
            errors.append(f"hooks.json.{event}.hooks must contain exactly one command hook")
            continue
        hook = commands[0]
        if hook.get("type") != "command":
            errors.append(f"hooks.json.{event}.hooks[0].type must be command")
        command = str(hook.get("command", ""))
        if script not in command:
            errors.append(f"hooks.json.{event}.hooks[0].command must call {script}")
        script_path = PLUGIN_ROOT / script
        if not script_path.is_file():
            errors.append(f"hook script missing: {script}")
        if event == "Stop" and hook.get("timeout") != 5:
            errors.append("hooks.json.Stop.hooks[0].timeout must be 5")
    return errors


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(PLUGIN_ROOT))
    except ValueError:
        return str(path)


def _list_ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _has_bool(obj: dict[str, Any], key: str, expected: bool) -> bool:
    return isinstance(obj, dict) and obj.get(key) is expected


def _sequence_ids(mode: dict[str, Any]) -> list[str]:
    sequence = mode.get("required_sequence")
    return sequence if isinstance(sequence, list) and all(isinstance(step, str) for step in sequence) else []


def _requires_no_parent_context(obj: dict[str, Any], path: str, errors: list[str]) -> None:
    if obj.get("fork_context") is not False:
        errors.append(f"{path}.fork_context must be false")
    if obj.get("parent_context") != "none":
        errors.append(f"{path}.parent_context must be none")


def _validate_helper_policy(mode: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    helper = mode.get(key) if isinstance(mode.get(key), dict) else {}
    if helper.get("required") is not True:
        errors.append(f"{path}.{key}.required must be true")
    purposes = helper.get("purposes")
    if purposes != list(REQUIRED_HELPER_PURPOSES):
        errors.append(f"{path}.{key}.purposes must be exact and ordered")
    _requires_no_parent_context(helper, f"{path}.{key}", errors)


def validate_goal_agent_modes(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    modes = catalog.get("goal_agent_modes")
    if not isinstance(modes, dict):
        return ["goal_agent_modes must be an object"]
    mode_ids = set(modes)
    if mode_ids != set(REQUIRED_GOAL_AGENT_MODES):
        return ["goal_agent_modes must contain exactly: " + ", ".join(REQUIRED_GOAL_AGENT_MODES)]
    for mode_id in REQUIRED_GOAL_AGENT_MODES:
        if not isinstance(modes.get(mode_id), dict):
            errors.append(f"goal_agent_modes.{mode_id} must be an object")
    goal_1 = modes.get("goal_1_agent") if isinstance(modes.get("goal_1_agent"), dict) else {}
    goal_1_sequence = _sequence_ids(goal_1)
    if goal_1_sequence != REQUIRED_GOAL_1_AGENT_SEQUENCE:
        errors.append("goal_agent_modes.goal_1_agent.required_sequence must be exact and ordered")
    if not goal_1_sequence or goal_1_sequence[0] != "create_own_state_file":
        errors.append("goal_agent_modes.goal_1_agent.required_sequence must start with create_own_state_file")
    state = goal_1.get("state_file") if isinstance(goal_1.get("state_file"), dict) else {}
    if state.get("create_own_state_file_first") is not True:
        errors.append("goal_agent_modes.goal_1_agent.state_file.create_own_state_file_first must be true")
    scope_execution = goal_1.get("scope_execution") if isinstance(goal_1.get("scope_execution"), dict) else {}
    if scope_execution.get("order") != "sequential":
        errors.append("goal_agent_modes.goal_1_agent.scope_execution.order must be sequential")
    if scope_execution.get("flow") != "bears_spec_kit_flow":
        errors.append("goal_agent_modes.goal_1_agent.scope_execution.flow must be bears_spec_kit_flow")
    _validate_helper_policy(goal_1, "helper_agents", "goal_agent_modes.goal_1_agent", errors)
    spawn_policy = goal_1.get("subagent_spawn_policy") if isinstance(goal_1.get("subagent_spawn_policy"), dict) else {}
    _requires_no_parent_context(spawn_policy, "goal_agent_modes.goal_1_agent.subagent_spawn_policy", errors)
    review_fix = goal_1.get("review_fix_policy") if isinstance(goal_1.get("review_fix_policy"), dict) else {}
    if review_fix.get("real_blocker_only_stops_agent") is not True:
        errors.append("goal_agent_modes.goal_1_agent.review_fix_policy.real_blocker_only_stops_agent must be true")

    parallel = modes.get("goal_parallel_l1") if isinstance(modes.get("goal_parallel_l1"), dict) else {}
    parallel_sequence = _sequence_ids(parallel)
    if parallel_sequence != REQUIRED_GOAL_PARALLEL_L1_SEQUENCE:
        errors.append("goal_agent_modes.goal_parallel_l1.required_sequence must be exact and ordered")
    if not parallel_sequence or parallel_sequence[0] != "create_own_state_file":
        errors.append("goal_agent_modes.goal_parallel_l1.required_sequence must start with create_own_state_file")
    state = parallel.get("state_file") if isinstance(parallel.get("state_file"), dict) else {}
    if state.get("create_own_state_file_first") is not True:
        errors.append("goal_agent_modes.goal_parallel_l1.state_file.create_own_state_file_first must be true")
    scope_execution = parallel.get("scope_execution") if isinstance(parallel.get("scope_execution"), dict) else {}
    if scope_execution.get("selected_scope_order") != "sequential":
        errors.append("goal_agent_modes.goal_parallel_l1.scope_execution.selected_scope_order must be sequential")
    if scope_execution.get("flow") != "spec_kit_logic":
        errors.append("goal_agent_modes.goal_parallel_l1.scope_execution.flow must be spec_kit_logic")
    l2_spawn = parallel.get("l2_spawn") if isinstance(parallel.get("l2_spawn"), dict) else {}
    if l2_spawn.get("required") is not True:
        errors.append("goal_agent_modes.goal_parallel_l1.l2_spawn.required must be true")
    if l2_spawn.get("step") != "spawn_l2_subagent_for_approved_spec_kit_plan":
        errors.append("goal_agent_modes.goal_parallel_l1.l2_spawn.step must be spawn_l2_subagent_for_approved_spec_kit_plan")
    _requires_no_parent_context(l2_spawn, "goal_agent_modes.goal_parallel_l1.l2_spawn", errors)
    if l2_spawn.get("l1_tracks_l2_after_spawn") is not False:
        errors.append("goal_agent_modes.goal_parallel_l1.l2_spawn.l1_tracks_l2_after_spawn must be false")
    if l2_spawn.get("l1_waits_for_l2_after_spawn") is not False:
        errors.append("goal_agent_modes.goal_parallel_l1.l2_spawn.l1_waits_for_l2_after_spawn must be false")
    if l2_spawn.get("after_spawn_l1_execution") != "continue_own_sequential_workflow":
        errors.append("goal_agent_modes.goal_parallel_l1.l2_spawn.after_spawn_l1_execution must be continue_own_sequential_workflow")
    if any(step in parallel_sequence for step in ("track_l2_execution", "wait_for_l2_completion", "l1_wait_for_l2")):
        errors.append("goal_agent_modes.goal_parallel_l1.required_sequence must not include L1 L2 tracking or waiting after spawn")
    _validate_helper_policy(parallel, "l2_helper_agents", "goal_agent_modes.goal_parallel_l1", errors)
    spawn_policy = parallel.get("subagent_spawn_policy") if isinstance(parallel.get("subagent_spawn_policy"), dict) else {}
    _requires_no_parent_context(spawn_policy, "goal_agent_modes.goal_parallel_l1.subagent_spawn_policy", errors)
    return errors


def validate_constitution(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema") != CONSTITUTION_SCHEMA:
        errors.append(f"schema must be {CONSTITUTION_SCHEMA}")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")
    principle_ids = set(_list_ids(catalog.get("principles")))
    missing = sorted(REQUIRED_CONSTITUTION_PRINCIPLES - principle_ids)
    extra = sorted(principle_ids - REQUIRED_CONSTITUTION_PRINCIPLES)
    if missing:
        errors.append("missing constitution principles: " + ", ".join(missing))
    if extra:
        errors.append("unknown constitution principles: " + ", ".join(extra))
    scoped = catalog.get("role_scoped_principles")
    if not isinstance(scoped, dict) or not scoped:
        errors.append("role_scoped_principles must be a non-empty object")
    else:
        for role, principles in scoped.items():
            if not isinstance(principles, list) or not principles:
                errors.append(f"role_scoped_principles.{role} must be a non-empty list")
                continue
            unknown = sorted(set(principles) - principle_ids)
            if unknown:
                errors.append(f"role_scoped_principles.{role} unknown principles: " + ", ".join(unknown))
        all_values = [p for values in scoped.values() if isinstance(values, list) for p in values]
        if len(all_values) == len(scoped) * len(principle_ids):
            errors.append("role_scoped_principles must not assign every principle to every role")
    references = catalog.get("references")
    if not isinstance(references, list) or not references:
        errors.append("references must be a non-empty list")
    else:
        for ref in references:
            if not isinstance(ref, str) or not ref.strip():
                errors.append("references entries must be non-empty strings")
                continue
            if ref.startswith(("http://", "https://")):
                continue
            ref_path = Path(ref)
            if ref_path.is_absolute():
                try:
                    ref_path.relative_to(PLUGIN_ROOT)
                except ValueError:
                    continue
                if not ref_path.exists():
                    errors.append(f"reference path missing: {ref}")
            elif not (PLUGIN_ROOT / ref_path).exists():
                errors.append(f"reference path missing: {ref}")
    validation = catalog.get("validation")
    if not isinstance(validation, dict) or validation.get("command") != "python3 scripts/agentic_enterprise_workflow.py validate-constitution":
        errors.append("validation.command must be python3 scripts/agentic_enterprise_workflow.py validate-constitution")
    return errors


def validate_workflow(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema") != WORKFLOW_SCHEMA:
        errors.append(f"schema must be {WORKFLOW_SCHEMA}")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")
    boundary = catalog.get("plugin_boundary") if isinstance(catalog.get("plugin_boundary"), dict) else {}
    if not _has_bool(boundary, "plugin_is_governance_control_plane", True):
        errors.append("plugin_boundary.plugin_is_governance_control_plane must be true")
    if not _has_bool(boundary, "plugin_generates_repo_payload", False):
        errors.append("plugin_boundary.plugin_generates_repo_payload must be false")
    forbidden = set(boundary.get("forbidden_surfaces", [])) if isinstance(boundary.get("forbidden_surfaces"), list) else set()
    for item in ("apps", "connectors", "mcp_servers", "runtime_services", "production_mutation", "product_code_generation", "gitops_generation"):
        if item not in forbidden:
            errors.append(f"plugin_boundary.forbidden_surfaces missing {item}")

    domains = catalog.get("repo_domains")
    if not isinstance(domains, list):
        errors.append("repo_domains must be a list")
        domain_ids: list[str] = []
    else:
        domain_ids = [domain.get("id") for domain in domains if isinstance(domain, dict)]
        if domain_ids != REQUIRED_REPO_DOMAINS:
            errors.append("repo_domains must be exactly: " + ", ".join(REQUIRED_REPO_DOMAINS))
        for domain in domains:
            if not isinstance(domain, dict):
                errors.append("repo_domains entries must be objects")
                continue
            for key in ("purpose", "primary_l2_role"):
                if not isinstance(domain.get(key), str) or not domain[key].strip():
                    errors.append(f"repo_domains.{domain.get('id')}.{key} must be non-empty")
            for key in ("owns", "must_not_own"):
                if not isinstance(domain.get(key), list) or not domain[key]:
                    errors.append(f"repo_domains.{domain.get('id')}.{key} must be non-empty")
    scope_policy = catalog.get("scope_policy") if isinstance(catalog.get("scope_policy"), dict) else {}
    for key in ("one_domain_per_scope", "measurable_output_required", "timebox_required", "token_budget_required"):
        if scope_policy.get(key) is not True:
            errors.append(f"scope_policy.{key} must be true")
    split = set(scope_policy.get("auto_split_triggers", [])) if isinstance(scope_policy.get("auto_split_triggers"), list) else set()
    for key in ("multiple_repo_domains", "write_scope_overlap", "missing_owner_lineage", "hard_split_threshold_exceeded", "token_budget_over_policy"):
        if key not in split:
            errors.append(f"scope_policy.auto_split_triggers missing {key}")
    hard_split = scope_policy.get("hard_split_threshold_min")
    if not isinstance(hard_split, int):
        errors.append("scope_policy.hard_split_threshold_min must be an integer")
    elif hard_split <= 0 or hard_split > 5:
        errors.append("scope_policy.hard_split_threshold_min must be between 1 and 5")
    max_tokens = scope_policy.get("max_token_budget_default")
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        errors.append("scope_policy.max_token_budget_default must be a positive integer")

    lineage = catalog.get("owner_lineage_policy") if isinstance(catalog.get("owner_lineage_policy"), dict) else {}
    for key in ("sticky_l2_by_domain", "l3_bound_to_l2", "doc_l3_bound_to_l2", "role_profile_not_chat_memory"):
        if lineage.get(key) is not True:
            errors.append(f"owner_lineage_policy.{key} must be true")
    required_lineage_fields = set(lineage.get("required_fields", [])) if isinstance(lineage.get("required_fields"), list) else set()
    for key in ("l2_owner_role", "l2_owner_id", "scope_family", "l3_executor_role", "l3_doc_role", "artifact_type"):
        if key not in required_lineage_fields:
            errors.append(f"owner_lineage_policy.required_fields missing {key}")

    layers = catalog.get("layer_workflow") if isinstance(catalog.get("layer_workflow"), dict) else {}
    l1 = layers.get("l1_head_orchestrator") if isinstance(layers.get("l1_head_orchestrator"), dict) else {}
    l1_allowed = set(l1.get("allowed_actions", [])) if isinstance(l1.get("allowed_actions"), list) else set()
    l1_forbidden = set(l1.get("forbidden_actions", [])) if isinstance(l1.get("forbidden_actions"), list) else set()
    if l1.get("max_context_files") != 1:
        errors.append("layer_workflow.l1_head_orchestrator.max_context_files must be 1")
    if "test_execution" not in l1_forbidden:
        errors.append("layer_workflow.l1_head_orchestrator.forbidden_actions missing test_execution")
    for action in ("task_decomposition", "task_matrix_write", "l2_governance_packet_write"):
        if action not in l1_allowed:
            errors.append(f"layer_workflow.l1_head_orchestrator.allowed_actions missing {action}")
    if "l2_spawn_packet_write" in l1_allowed:
        errors.append("layer_workflow.l1_head_orchestrator.allowed_actions must not include l2_spawn_packet_write")
    if "subagent_spawn_per_task" not in l1_forbidden:
        errors.append("layer_workflow.l1_head_orchestrator.forbidden_actions missing subagent_spawn_per_task")
    l2 = layers.get("l2_domain_orchestrator") if isinstance(layers.get("l2_domain_orchestrator"), dict) else {}
    l2_allowed = set(l2.get("allowed_actions", [])) if isinstance(l2.get("allowed_actions"), list) else set()
    l2_forbidden = set(l2.get("forbidden_actions", [])) if isinstance(l2.get("forbidden_actions"), list) else set()
    for action in ("domain_governance", "scope_boundary_review", "l3_assignment_packet_review"):
        if action not in l2_allowed:
            errors.append(f"layer_workflow.l2_domain_orchestrator.allowed_actions missing {action}")
    for action in ("task_decomposition", "subagent_spawn_per_task"):
        if action not in l2_forbidden:
            errors.append(f"layer_workflow.l2_domain_orchestrator.forbidden_actions missing {action}")
    if "task_split" in l2_allowed or "remediation_scope_spawn" in l2_allowed:
        errors.append("layer_workflow.l2_domain_orchestrator.allowed_actions must not include task_split or remediation_scope_spawn")
    if scope_policy.get("task_decomposition_owner") != "l1_head_orchestrator":
        errors.append("scope_policy.task_decomposition_owner must be l1_head_orchestrator")
    if scope_policy.get("governance_owner") != "l2_domain_orchestrator":
        errors.append("scope_policy.governance_owner must be l2_domain_orchestrator")
    if scope_policy.get("spawn_per_task_forbidden") is not True:
        errors.append("scope_policy.spawn_per_task_forbidden must be true")
    errors.extend(validate_goal_agent_modes(catalog))

    stage_order = catalog.get("stage_order") if isinstance(catalog.get("stage_order"), list) else []
    if stage_order[: len(REQUIRED_STAGE_PREFIX)] != REQUIRED_STAGE_PREFIX:
        errors.append("stage_order must start with " + " -> ".join(REQUIRED_STAGE_PREFIX))
    msg_rule = catalog.get("message_to_scope_rule") if isinstance(catalog.get("message_to_scope_rule"), dict) else {}
    for key in ("operator_message_creates_scope_row", "scope_row_requires_research_first", "operator_messages_count_must_equal_scope_rows_count"):
        if msg_rule.get(key) is not True:
            errors.append(f"message_to_scope_rule.{key} must be true")
    if msg_rule.get("missing_scope_row_status") != "blocker":
        errors.append("message_to_scope_rule.missing_scope_row_status must be blocker")

    decision = catalog.get("decision_log_policy") if isinstance(catalog.get("decision_log_policy"), dict) else {}
    if decision.get("schema") != DEFAULT_DECISION_LOG_SCHEMA:
        errors.append(f"decision_log_policy.schema must be {DEFAULT_DECISION_LOG_SCHEMA}")
    if decision.get("required_types") != REQUIRED_DECISION_TYPES:
        errors.append("decision_log_policy.required_types must be exact and ordered")
    for key in ("user_input_has_priority_over_agent_decision", "contradiction_blocks_scope", "raw_chat_forbidden"):
        if decision.get(key) is not True:
            errors.append(f"decision_log_policy.{key} must be true")

    gate = catalog.get("clarification_gate") if isinstance(catalog.get("clarification_gate"), dict) else {}
    if gate.get("ask_only_after_research") is not True:
        errors.append("clarification_gate.ask_only_after_research must be true")
    reasons = set(gate.get("allowed_reasons", [])) if isinstance(gate.get("allowed_reasons"), list) else set()
    for reason in ("architecture_cost_security_impact", "default_conflicts_with_saas_standard", "default_conflicts_with_agent_development_standard", "user_facts_or_directives_conflict"):
        if reason not in reasons:
            errors.append(f"clarification_gate.allowed_reasons missing {reason}")

    hooks = catalog.get("hook_policy") if isinstance(catalog.get("hook_policy"), dict) else {}
    errors.extend(validate_hook_wiring())
    slo = hooks.get("slo_ms") if isinstance(hooks.get("slo_ms"), dict) else {}
    for event, max_ms in (("PreToolUse", 150), ("PreTask", 250), ("SessionStart", 500)):
        if not isinstance(slo.get(event), int) or slo[event] > max_ms:
            errors.append(f"hook_policy.slo_ms.{event} must be <= {max_ms}")
    forbidden_hot_path = set(hooks.get("forbidden_hot_path_actions", [])) if isinstance(hooks.get("forbidden_hot_path_actions"), list) else set()
    for action in ("tests", "broad_search", "network", "raw_logs"):
        if action not in forbidden_hot_path:
            errors.append(f"hook_policy.forbidden_hot_path_actions missing {action}")

    degradation = catalog.get("runtime_degradation_policy") if isinstance(catalog.get("runtime_degradation_policy"), dict) else {}
    if degradation.get("actions") != REQUIRED_DEGRADATION_ACTIONS:
        errors.append("runtime_degradation_policy.actions must be exact and ordered")
    if degradation.get("stop_only_problem_scope") is not True:
        errors.append("runtime_degradation_policy.stop_only_problem_scope must be true")
    if degradation.get("unrelated_scopes_continue_parallel") is not True:
        errors.append("runtime_degradation_policy.unrelated_scopes_continue_parallel must be true")
    if degradation.get("l1_during_stop") != "open_l2_governance_review_only":
        errors.append("runtime_degradation_policy.l1_during_stop must be open_l2_governance_review_only")
    mapping = catalog.get("symphony_pattern_mapping") if isinstance(catalog.get("symphony_pattern_mapping"), dict) else {}
    adopted = set(mapping.get("adopted_patterns", [])) if isinstance(mapping.get("adopted_patterns"), list) else set()
    for pattern in ("issue_or_scope_as_state_machine", "single_authoritative_state", "isolated_workspace_or_write_scope", "proof_of_work_packet", "stall_restart_or_remediation"):
        if pattern not in adopted:
            errors.append(f"symphony_pattern_mapping.adopted_patterns missing {pattern}")
    l1_deny_probe = hook_decision("PreToolUse", {"agent_layer": "l1"}, catalog, tool_name="rg", agent_layer="l1")
    if l1_deny_probe.get("decision") != "deny":
        errors.append("hook_decision must deny non-controller L1 tools")
    if int(l1_deny_probe.get("elapsed_ms", 9999)) > 150:
        errors.append("hook_decision L1 deny probe exceeds PreToolUse SLO")
    session_probe = hook_decision("SessionStart", {}, catalog, agent_layer="l1")
    if "L1 head orchestrator" not in str(session_probe.get("agent_message", "")):
        errors.append("SessionStart hook decision must initialize the L1 head orchestrator prompt")
    if int(session_probe.get("elapsed_ms", 9999)) > 500:
        errors.append("hook_decision SessionStart probe exceeds SessionStart SLO")
    hard_split_probe = hook_decision("PreTask", {}, catalog, agent_layer="l1", metadata={"duration_min": 6})
    if hard_split_probe.get("decision") != "deny" or "hard_split_threshold" not in str(hard_split_probe.get("reason", "")):
        errors.append("hook_decision must deny scopes over the hard split threshold")
    pretool_hard_split_probe = hook_decision(
        "PreToolUse",
        {"agent_layer": "l3"},
        catalog,
        tool_name="implementation_tool",
        agent_layer="l3",
        scope_id="scope-a",
        metadata={"duration_min": 6},
    )
    if pretool_hard_split_probe.get("decision") != "deny" or pretool_hard_split_probe.get("control_reason") != "hard_split_threshold_exceeded":
        errors.append("hook_decision PreToolUse must deny scoped tools over the hard split threshold")
    split_probe = hook_decision("PreTask", {}, catalog, agent_layer="l1", metadata={"duration_min": 6, "split_state": "split_started"})
    if split_probe.get("decision") != "allow" or split_probe.get("control_status") != "armed":
        errors.append("hook_decision must allow over-threshold work only after split/decomposition starts")
    token_probe = hook_decision("PreTask", {}, catalog, agent_layer="l1", metadata={"token_budget": int(max_tokens or 12000) + 1})
    if token_probe.get("decision") != "deny" or "token_budget_over_policy" not in str(token_probe.get("reason", "")):
        errors.append("hook_decision must deny token budgets over policy without throttle or split state")
    token_spend_probe = hook_decision(
        "PreToolUse",
        {"agent_layer": "l3"},
        catalog,
        tool_name="implementation_tool",
        agent_layer="l3",
        scope_id="scope-a",
        metadata={"token_spend": int(max_tokens or 12000) + 1},
    )
    if token_spend_probe.get("decision") != "deny" or token_spend_probe.get("control_reason") != "token_budget_over_policy":
        errors.append("hook_decision PreToolUse must deny token spend over policy without throttle or split state")
    missing_probe = hook_decision("PreTask", {}, catalog, agent_layer="unknown")
    if missing_probe.get("decision") != "allow" or missing_probe.get("control_status") != CONTROL_NOT_ARMED_CODE:
        errors.append("hook_decision must allow unmanaged missing metadata with control_not_armed status")
    governed_missing_probe = hook_decision("PreTask", {}, catalog, agent_layer="l1")
    if governed_missing_probe.get("decision") != "deny" or governed_missing_probe.get("control_reason") != "missing_scope_time_token_metadata":
        errors.append("hook_decision must deny governed L1 work when time/token control metadata is absent")
    delivery = catalog.get("delivery_policy") if isinstance(catalog.get("delivery_policy"), dict) else {}
    if delivery.get("branch_model") != "main_only":
        errors.append("delivery_policy.branch_model must be main_only")
    if delivery.get("task_commits_target") != "main":
        errors.append("delivery_policy.task_commits_target must be main")
    if delivery.get("pull_request_required") is not False:
        errors.append("delivery_policy.pull_request_required must be false")
    if delivery.get("github_review_required") is not False:
        errors.append("delivery_policy.github_review_required must be false")
    required_delivery_stages = ["commit_to_main", "local_commit_validation_pass", "cache_sync_done", "effective_hooks_proof"]
    if delivery.get("delivery_complete_requires") != required_delivery_stages:
        errors.append("delivery_policy.delivery_complete_requires must be commit_to_main -> local_commit_validation_pass -> cache_sync_done -> effective_hooks_proof")
    required_stage_tail = ["local_commit_validation_read", *required_delivery_stages, "delivery_complete"]
    if stage_order[-len(required_stage_tail):] != required_stage_tail:
        errors.append("stage_order must end with local_commit_validation_read -> commit_to_main -> local_commit_validation_pass -> cache_sync_done -> effective_hooks_proof -> delivery_complete")

    validation = catalog.get("validation") if isinstance(catalog.get("validation"), dict) else {}
    for fixture in validation.get("fixtures", []) if isinstance(validation.get("fixtures"), list) else []:
        if not (PLUGIN_ROOT / fixture).is_file():
            errors.append(f"validation fixture missing: {fixture}")
    return errors


def _record_identity(record: dict[str, Any]) -> str:
    return str(record.get("id", "<missing>"))


def validate_decision_log(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if packet.get("schema") != DEFAULT_DECISION_LOG_SCHEMA:
        errors.append(f"schema must be {DEFAULT_DECISION_LOG_SCHEMA}")
    records = packet.get("records")
    if not isinstance(records, list):
        return errors + ["records must be a list"]
    seen: set[str] = set()
    active_values: dict[str, tuple[Any, str]] = {}
    conflicts: set[str] = set()
    has_contradiction = False
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            errors.append(f"records[{index}].id must be non-empty")
        elif record_id in seen:
            errors.append(f"duplicate record id: {record_id}")
        seen.add(str(record_id))
        record_type = record.get("type")
        if record_type not in REQUIRED_DECISION_TYPES:
            errors.append(f"records[{index}].type must be one of {', '.join(REQUIRED_DECISION_TYPES)}")
        for key in ("decision_key", "summary", "status", "source", "created_by_role"):
            if not isinstance(record.get(key), str) or not record[key].strip():
                errors.append(f"records[{index}].{key} must be non-empty")
        if "raw_text" in record or "raw_chat" in record:
            errors.append(f"records[{index}] must not include raw_text or raw_chat")
        if record_type == "contradiction":
            has_contradiction = True
            if record.get("status") != "blocked":
                errors.append(f"records[{index}] contradiction status must be blocked")
            if record.get("needs_user_input") is not True:
                errors.append(f"records[{index}] contradiction must set needs_user_input=true")
        if record.get("status") == "active" and record_type in {"user_fact", "user_directive"}:
            decision_key = str(record.get("decision_key"))
            value = record.get("value")
            if decision_key in active_values and active_values[decision_key][0] != value:
                conflicts.add(decision_key)
            else:
                active_values[decision_key] = (value, _record_identity(record))
    if conflicts and not has_contradiction:
        errors.append("active user facts/directives conflict without contradiction record: " + ", ".join(sorted(conflicts)))
    return errors


def validate_scope_matrix(packet: dict[str, Any], workflow: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if packet.get("schema") != DEFAULT_SCOPE_MATRIX_SCHEMA:
        errors.append(f"schema must be {DEFAULT_SCOPE_MATRIX_SCHEMA}")
    scopes = packet.get("scopes")
    if not isinstance(scopes, list):
        return errors + ["scopes must be a list"]
    count = packet.get("operator_messages_count")
    if isinstance(count, int) and count != len(scopes):
        errors.append("operator_messages_count must equal scope rows count")
    elif not isinstance(count, int):
        errors.append("operator_messages_count must be an integer")
    max_time = 45
    max_tokens = 12000
    if workflow:
        scope_policy = workflow.get("scope_policy") if isinstance(workflow.get("scope_policy"), dict) else {}
        max_time = int(scope_policy.get("max_timebox_min_default", max_time))
        max_tokens = int(scope_policy.get("max_token_budget_default", max_tokens))
    for index, scope in enumerate(scopes):
        if not isinstance(scope, dict):
            errors.append(f"scopes[{index}] must be an object")
            continue
        for key in ("scope_id", "user_message_ref", "repo_domain", "measurable_output", "status"):
            if not isinstance(scope.get(key), str) or not scope[key].strip():
                errors.append(f"scopes[{index}].{key} must be non-empty")
        if scope.get("repo_domain") not in REQUIRED_REPO_DOMAINS:
            errors.append(f"scopes[{index}].repo_domain must be one of {', '.join(REQUIRED_REPO_DOMAINS)}")
        repo_domains = scope.get("repo_domains")
        if isinstance(repo_domains, list) and len(set(repo_domains)) != 1:
            errors.append(f"scopes[{index}] spans multiple repo_domains and must be split")
        if not isinstance(scope.get("timebox_min"), int) or scope["timebox_min"] <= 0:
            errors.append(f"scopes[{index}].timebox_min must be a positive integer")
        elif scope["timebox_min"] > max_time:
            errors.append(f"scopes[{index}].timebox_min exceeds policy max {max_time}")
        if not isinstance(scope.get("token_budget"), int) or scope["token_budget"] <= 0:
            errors.append(f"scopes[{index}].token_budget must be a positive integer")
        elif scope["token_budget"] > max_tokens:
            errors.append(f"scopes[{index}].token_budget exceeds policy max {max_tokens}")
        lineage = scope.get("owner_lineage")
        if not isinstance(lineage, dict):
            errors.append(f"scopes[{index}].owner_lineage must be an object")
        else:
            for key in ("l2_owner_role", "l2_owner_id", "scope_family", "l3_executor_role", "l3_doc_role", "artifact_type"):
                if not isinstance(lineage.get(key), str) or not lineage[key].strip():
                    errors.append(f"scopes[{index}].owner_lineage.{key} must be non-empty")
        stages = scope.get("stages")
        if not isinstance(stages, list) or not stages:
            errors.append(f"scopes[{index}].stages must be a non-empty list")
        elif stages[0] != "research":
            errors.append(f"scopes[{index}].stages[0] must be research")
    return errors


def validate_default_fixtures(workflow: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    fixtures = workflow.get("validation", {}).get("fixtures", []) if isinstance(workflow.get("validation"), dict) else []
    if not isinstance(fixtures, list):
        return ["validation.fixtures must be a list"]
    for fixture in fixtures:
        path = PLUGIN_ROOT / str(fixture)
        if not path.is_file():
            errors.append(f"fixture missing: {fixture}")
            continue
        try:
            packet = _load_json(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fixture {_rel(path)} parse failed: {exc}")
            continue
        if "decision-log" in path.name:
            packet_errors = validate_decision_log(packet)
        elif "scope-matrix" in path.name:
            packet_errors = validate_scope_matrix(packet, workflow)
        else:
            packet_errors = []
        should_fail = "/bad/" in str(path).replace("\\", "/") or path.name.endswith(".invalid.json")
        if should_fail and not packet_errors:
            errors.append(f"negative fixture unexpectedly passes: {_rel(path)}")
        if not should_fail and packet_errors:
            errors.append(f"positive fixture failed: {_rel(path)}: " + "; ".join(packet_errors))
    return errors


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _scope_records(state: dict[str, Any], scope_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    active = state.get("active_scope")
    if isinstance(active, dict):
        records.append(active)
    scopes = state.get("scopes")
    if isinstance(scopes, list):
        for scope in scopes:
            if not isinstance(scope, dict):
                continue
            if scope_id and scope.get("scope_id") != scope_id:
                continue
            records.append(scope)
    if state:
        records.append(state)
    return records


def _metadata_records(state: dict[str, Any], metadata: dict[str, Any], scope_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    active = metadata.get("active_scope")
    if isinstance(active, dict):
        records.append(active)
    if metadata:
        records.append(metadata)
    records.extend(_scope_records(state, scope_id))
    return records


def _first_number(records: list[dict[str, Any]], keys: tuple[str, ...]) -> tuple[float | None, str]:
    for record in records:
        for key in keys:
            if key not in record:
                continue
            value = _as_number(record.get(key))
            if value is not None:
                return value, key
    return None, ""


def _has_control_state(records: list[dict[str, Any]], names: tuple[str, ...], truthy_names: tuple[str, ...]) -> bool:
    for record in records:
        for name in names:
            value = record.get(name)
            if isinstance(value, bool) and value:
                return True
            if isinstance(value, str) and value.strip().casefold() not in NO_SPLIT_STATES:
                return True
        for name in truthy_names:
            if record.get(name) is True:
                return True
        stages = record.get("stages")
        if isinstance(stages, list):
            stage_names = {str(stage).casefold() for stage in stages}
            if any("split" in stage or "decomposition" in stage for stage in stage_names):
                return True
    return False


def _add_warning(decision: dict[str, Any], code: str, reason: str) -> None:
    warnings = decision.setdefault("warnings", [])
    if isinstance(warnings, list):
        warnings.append({"code": code, "reason": reason})


def _apply_scope_controls(
    decision: dict[str, Any],
    *,
    event: str,
    state: dict[str, Any],
    catalog: dict[str, Any],
    metadata: dict[str, Any],
    scope_id: str,
    controlled_layer: bool = False,
) -> None:
    if event not in ACTIVE_CONTROL_EVENTS:
        return
    scope_policy = catalog.get("scope_policy") if isinstance(catalog.get("scope_policy"), dict) else {}
    hard_split = scope_policy.get("hard_split_threshold_min")
    hard_split_min = int(hard_split) if isinstance(hard_split, int) else 5
    max_tokens = scope_policy.get("max_token_budget_default")
    max_token_budget = int(max_tokens) if isinstance(max_tokens, int) else 12000
    records = _metadata_records(state, metadata, scope_id)
    duration_value, duration_key = _first_number(
        records,
        ("duration_min", "elapsed_min", "active_scope_duration_min", "scope_age_min", "timebox_min"),
    )
    token_value, token_key = _first_number(
        records,
        ("token_budget", "max_token_budget", "token_spend", "tokens_used", "token_count"),
    )
    split_or_decomposed = _has_control_state(
        records,
        ("split_state", "decomposition_state", "decomposed_state"),
        ("split_started", "split_complete", "decomposition_started", "decomposition_complete"),
    )
    throttle_or_split = split_or_decomposed or _has_control_state(
        records,
        ("throttle_state", "token_throttle_state"),
        ("throttle_started", "throttle_active"),
    )

    if duration_value is not None and duration_value > hard_split_min and not split_or_decomposed:
        decision.update(
            {
                "decision": "deny",
                "reason": f"hard_split_threshold_exceeded: {duration_key}={duration_value:g} > {hard_split_min}",
                "control_status": "enforced",
                "control_reason": "hard_split_threshold_exceeded",
            }
        )
        return
    if token_value is not None and token_value > max_token_budget and not throttle_or_split:
        decision.update(
            {
                "decision": "deny",
                "reason": f"token_budget_over_policy: {token_key}={token_value:g} > {max_token_budget}",
                "control_status": "enforced",
                "control_reason": "token_budget_over_policy",
            }
        )
        return
    if duration_value is None and token_value is None:
        decision["control_status"] = CONTROL_NOT_ARMED_CODE
        decision["control_reason"] = "missing_scope_time_token_metadata"
        if controlled_layer:
            decision.update(
                {
                    "decision": "deny",
                    "reason": MISSING_CONTROL_METADATA_REASON,
                    "control_status": "enforced",
                }
            )
            return
        if decision.get("decision") == "allow":
            decision["reason"] = MISSING_CONTROL_METADATA_REASON
        _add_warning(decision, CONTROL_NOT_ARMED_CODE, "missing scope time or token metadata")
    else:
        decision.setdefault("control_status", "armed")


def hook_decision(
    event: str,
    state: dict[str, Any],
    catalog: dict[str, Any],
    *,
    tool_name: str = "",
    agent_layer: str = "",
    scope_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    mode = state.get("l1_mode", "normal") if isinstance(state, dict) else "normal"
    block = state.get("workflow_block", {}) if isinstance(state.get("workflow_block"), dict) else {}
    event_metadata = metadata if isinstance(metadata, dict) else {}
    decision: dict[str, Any] = {
        "schema": "bears-agentic-enterprise-hook-decision.v1",
        "event": event,
        "decision": "allow",
        "reason": "compact policy passed",
        "agent_layer": agent_layer or "unknown",
        "l1_mode": mode,
        "scope_id": scope_id,
        "hookSpecificOutput": {},
    }
    if event == "SessionStart":
        decision["agent_message"] = (
            "You are the Bears L1 head orchestrator: use one compact controller state, "
            "create small one-domain scopes, start research first, decompose tasks in L1, "
            "send governance packets to L2, and do not spawn a subagent for each task."
        )
    effective_layer = agent_layer or str(state.get("agent_layer", ""))
    controlled_layer = effective_layer in {"l1", "l2", "l3"}
    _apply_scope_controls(
        decision,
        event=event,
        state=state,
        catalog=catalog,
        metadata=event_metadata,
        scope_id=scope_id,
        controlled_layer=controlled_layer,
    )
    if block.get("block_goal_run") is True:
        decision.update({"decision": "deny", "reason": str(block.get("reason", "workflow_block"))})
    if event == "PreToolUse" and (agent_layer == "l1" or state.get("agent_layer") == "l1"):
        lower_tool = tool_name.casefold()
        if tool_name and tool_name not in L1_ALLOWED_TOOLS:
            if lower_tool.startswith(L1_DENY_TOOL_PREFIXES):
                decision.update({"decision": "deny", "reason": f"L1 tool denied: {tool_name}"})
    if event in {"PreTask", "PreToolUse"} and agent_layer in {"l2", "l3"} and not scope_id:
        decision.update({"decision": "deny", "reason": f"{agent_layer.upper()} requires scope_id"})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    decision["elapsed_ms"] = elapsed_ms
    if decision["decision"] == "deny":
        decision["hookSpecificOutput"] = {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": decision["reason"],
        }
    else:
        decision["hookSpecificOutput"] = {"hookEventName": event}
    return decision


def emit_result(status: str, errors: list[str], **extra: Any) -> int:
    payload = {"status": status, "errors": errors, **extra}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    vc = sub.add_parser("validate-constitution")
    vc.add_argument("--catalog", default=str(DEFAULT_CONSTITUTION))
    vw = sub.add_parser("validate-workflow")
    vw.add_argument("--catalog", default=str(DEFAULT_WORKFLOW))
    vd = sub.add_parser("validate-decision-log")
    vd.add_argument("--packet", required=True)
    vs = sub.add_parser("validate-scope-matrix")
    vs.add_argument("--packet", required=True)
    vs.add_argument("--catalog", default=str(DEFAULT_WORKFLOW))
    val = sub.add_parser("validate")
    val.add_argument("--constitution", default=str(DEFAULT_CONSTITUTION))
    val.add_argument("--workflow", default=str(DEFAULT_WORKFLOW))
    hd = sub.add_parser("hook-decision")
    hd.add_argument("--event", required=True, choices=["SessionStart", "PreTask", "PreToolUse"])
    hd.add_argument("--state", default="")
    hd.add_argument("--catalog", default=str(DEFAULT_WORKFLOW))
    hd.add_argument("--tool-name", default="")
    hd.add_argument("--agent-layer", default="")
    hd.add_argument("--scope-id", default="")
    hd.add_argument("--duration-min", type=float, default=None)
    hd.add_argument("--token-budget", type=float, default=None)
    hd.add_argument("--token-spend", type=float, default=None)
    hd.add_argument("--timebox-min", type=float, default=None)
    hd.add_argument("--split-state", default="")
    hd.add_argument("--decomposition-state", default="")
    hd.add_argument("--throttle-state", default="")
    args = parser.parse_args(argv)

    try:
        if args.command == "validate-constitution":
            catalog = _load_json(Path(args.catalog))
            errors = validate_constitution(catalog)
            return emit_result("pass" if not errors else "fail", errors, checked=[_rel(Path(args.catalog))])
        if args.command == "validate-workflow":
            catalog = _load_json(Path(args.catalog))
            errors = validate_workflow(catalog) + validate_default_fixtures(catalog)
            return emit_result("pass" if not errors else "fail", errors, checked=[_rel(Path(args.catalog))])
        if args.command == "validate-decision-log":
            packet = _load_json(Path(args.packet))
            errors = validate_decision_log(packet)
            return emit_result("pass" if not errors else "fail", errors, checked=[_rel(Path(args.packet))])
        if args.command == "validate-scope-matrix":
            packet = _load_json(Path(args.packet))
            workflow = _load_json(Path(args.catalog))
            errors = validate_scope_matrix(packet, workflow)
            return emit_result("pass" if not errors else "fail", errors, checked=[_rel(Path(args.packet))])
        if args.command == "validate":
            constitution = _load_json(Path(args.constitution))
            workflow = _load_json(Path(args.workflow))
            errors = validate_constitution(constitution) + validate_workflow(workflow) + validate_default_fixtures(workflow)
            return emit_result(
                "pass" if not errors else "fail",
                errors,
                checked=[_rel(Path(args.constitution)), _rel(Path(args.workflow))],
            )
        if args.command == "hook-decision":
            state: dict[str, Any] = {}
            if args.state:
                state_path = Path(args.state)
                if state_path.is_file():
                    state = _load_json(state_path)
            catalog = _load_json(Path(args.catalog))
            errors = validate_workflow(catalog)
            if errors:
                return emit_result("fail", errors, checked=[_rel(Path(args.catalog))])
            decision = hook_decision(
                args.event,
                state,
                catalog,
                tool_name=args.tool_name,
                agent_layer=args.agent_layer,
                scope_id=args.scope_id,
                metadata={
                    key: value
                    for key, value in {
                        "duration_min": args.duration_min,
                        "token_budget": args.token_budget,
                        "token_spend": args.token_spend,
                        "timebox_min": args.timebox_min,
                        "split_state": args.split_state,
                        "decomposition_state": args.decomposition_state,
                        "throttle_state": args.throttle_state,
                    }.items()
                    if value not in (None, "")
                },
            )
            print(json.dumps(decision, indent=2, sort_keys=True))
            return 0 if decision["decision"] == "allow" else 2
    except Exception as exc:  # noqa: BLE001
        return emit_result("fail", [str(exc)])
    return emit_result("fail", ["unhandled command"])


if __name__ == "__main__":
    sys.exit(main())
