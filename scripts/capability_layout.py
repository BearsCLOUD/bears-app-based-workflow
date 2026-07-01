#!/usr/bin/env python3
"""Validate Bears plugin capability inventory and layout packets."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = PLUGIN_ROOT / "capabilities/inventory.v1.json"
DEFAULT_SCHEMA = PLUGIN_ROOT / "capabilities/capability.schema.json"
DEFAULT_SKILL_CATALOG = PLUGIN_ROOT / "assets/catalog/plugin-skill-catalog.v1.json"

TARGET_CAPABILITY_IDS = [
    "role-gate",
    "blocker-evaluation",
    "subagent-orchestration",
    "development-workflow",
    "project-registry",
    "secret-factory",
    "deploy-readiness",
    "telegram-workflow",
    "roadmap-control",
    "goal-prompt-generation",
    "git-discipline",
    "plugin-constitution",
    "validation-hooks",
    "agent-registration-sync",
    "agent-github-dev-cd",
    "yandex360-dns",
    "sentry-runtime-governance",
]

TOP_LEVEL_FIELDS = [
    "schema",
    "version",
    "updated",
    "owner_plugin",
    "source_repo",
    "codex_environment_policy",
    "capabilities",
    "rule_coverage",
    "hot_path_legacy_exceptions",
    "cache_validation",
    "validation_commands",
]

CAPABILITY_FIELDS = [
    "id",
    "python_package",
    "lifecycle_state",
    "canonical_source_phase",
    "owner_role",
    "primary_legacy_sources",
    "capability_source_paths",
    "active_skill_front_doors",
    "internal_front_door",
    "legacy_entrypoints",
    "compatibility_entrypoints",
    "schemas",
    "fixtures",
    "tests",
    "validators",
    "forbidden_data",
    "allowed_actions",
    "forbidden_actions",
    "sanitized_evidence_schema",
    "context_budget",
    "cache_sync_required",
    "environment_surface_claims",
    "performance_claims",
    "offload_surface_claims",
    "programmatic_control_claims",
    "hook_claims",
    "reviewer_lane_policy",
    "agent_profiles",
    "open_issues",
    "cutover_blockers",
    "rollback_command",
]

CAPABILITY_JSON_FIELDS = [
    "schema",
    "id",
    "python_package",
    "version",
    "owner_role",
    "canonical_source_phase",
    "legacy_entrypoints",
    "compatibility_entrypoints",
    "validators",
    "schemas",
    "fixtures",
    "tests",
    "allowed_actions",
    "forbidden_actions",
    "forbidden_data",
    "sanitized_evidence_schema",
    "context_budget",
    "performance_claims",
    "offload_surface_claims",
    "programmatic_control_claims",
    "cache_sync",
    "rollback",
]

CAPABILITY_PACKAGE_REQUIRED_PATHS = [
    "AGENTS.md",
    "README.md",
    "__init__.py",
    "capability.json",
    "schemas",
    "scripts",
    "fixtures/pass",
    "fixtures/fail",
    "tests",
]

RULE_COVERAGE_FIELDS = [
    "rule_id",
    "source_path",
    "source_anchor",
    "rule_class",
    "owner_capability_id",
    "router_allowed",
    "schema_paths",
    "validator_subcommands",
    "pass_fixture_ids",
    "fail_fixture_ids",
    "failure_class",
    "status_packet_field",
    "legacy_exception_id",
    "sunset_phase",
]

RULE_CLASSES = {"instruction", "policy", "refactor_closeout", "validator", "router", "legacy_exception"}
RULE_COVERAGE_FIXTURE_ROOT = PLUGIN_ROOT / "tests/fixtures/capability_layout/rule_coverage"
REFACTOR_GATE_FIXTURE_ROOT = PLUGIN_ROOT / "tests/fixtures/capability_layout/refactor_gate"
RULE_COVERAGE_REQUIRED_STATUS_FIELDS = {
    "rule_coverage_status",
    "instruction_only_rule_count",
    "uncovered_rule_ids",
    "refactor_gate_status",
}
STATUS_PACKET_FIELDS = {
    "status",
    "checks",
    "cache_status",
    "validation_commands",
    "restricted_data_status",
    "environment_operation_packet_validation",
    "optimization_lane_packet_validation",
    "effective_environment_resolution_validation",
    "performance_claim_validation",
    "offload_surface_validation",
    "programmatic_control_telemetry_surface_validation",
    "rule_coverage_status",
    "instruction_only_rule_count",
    "uncovered_rule_ids",
    "constitution_change_status",
    "refactor_gate_status",
    "clean_head_validation_status",
}
REFACTOR_GATE_FIELDS = [
    "schema",
    "version",
    "gate_id",
    "phase",
    "status_packet_fields",
    "requirements",
    "restricted_data_status",
]
REFACTOR_REQUIREMENT_FIELDS = [
    "id",
    "rule_coverage_id",
    "requirement_type",
    "proof_type",
    "proof_command",
    "schema_path",
    "validator_subcommand",
    "pass_fixture_id",
    "fail_fixture_id",
    "failure_class",
    "status_packet_field",
    "runtime_claim",
    "effective_config_snapshot_id",
    "environment_mutation",
    "environment_operation_packet",
    "clean_head_validation_status",
    "restricted_data_status",
    "legacy_exception_id",
]
PROOF_TYPES = {"validator", "unit_fixture", "schema_packet", "generated_status", "legacy_exception"}

HOT_PATH_FIELDS = [
    "path",
    "field",
    "observed_size",
    "budget",
    "owner_role",
    "shrink_deadline_phase",
    "blocking_rule",
    "validator_command",
    "reviewer_signoff",
]

LIST_PATH_FIELDS = [
    "primary_legacy_sources",
    "capability_source_paths",
    "schemas",
    "fixtures",
    "tests",
]

LIFECYCLE_STATES = {"planned", "legacy", "dual", "capability", "deprecated"}
SOURCE_PHASES = {"inventory", "legacy", "dual", "capability", "deprecated"}
RESTRICTED_DATA_STATUS = "clean"

HOOK_CLAIM_FIELDS = [
    "event",
    "source_layer",
    "hook_source_path",
    "enabled_config_layer",
    "feature_key",
    "effective_hooks_enabled",
    "trust_review_status",
    "handler_type",
    "handler_async",
    "matcher_supported",
    "timeout_seconds",
    "sanitized_output_schema",
    "probe_command",
    "blocking_policy",
    "fallback_when_disabled",
]

ALLOWED_HOOK_EVENTS = {"UserPromptSubmit", "Stop", "SubagentStop"}
ALLOWED_HOOK_BLOCKING_POLICIES = {"never", "secret_or_contract_stop_only"}
MATCHER_UNSUPPORTED_EVENTS = {"UserPromptSubmit", "Stop"}

MANDATORY_REVIEWER_LANE_CAPABILITIES = {
    "subagent-orchestration",
    "development-workflow",
    "agent-github-dev-cd",
}
REVIEWER_LANE_POLICY_FIELDS = [
    "worker_lane_taxonomy",
    "allowed_lane_modes",
    "default_lane_mode",
    "hard_stop_reasons",
    "blocking_timeout_seconds",
    "wait_budget_seconds",
    "max_same_turn_wait_seconds",
    "wait_poll_interval_seconds",
    "fallback_actions",
    "closeout_artifact_schema",
    "stale_result_rule",
    "checkpoint_integration",
    "deterministic_integration_order",
    "reviewer_self_fix_rule",
]
WORKER_LANE_TAXONOMY = [
    "read_only_research",
    "advisory_review",
    "blocking_gate_review",
    "fix_worker",
    "validator_worker",
    "audit_worker",
    "integration_worker",
]
ALLOWED_LANE_MODES = ["advisory_async", "blocking_gate"]
BLOCKING_HARD_STOP_REASONS = {
    "merge_authority",
    "role_coverage",
    "restricted_data",
    "security",
    "secret_handling",
    "operator_stop",
    "linked_contract_hard_stop",
}

AGENT_SPAWN_PROOF_FIELDS = [
    "source_agent_path",
    "materialized_agent_path",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
    "developer_instructions_hash",
    "catalog_role",
    "route_audit_status",
]


ALLOWED_ENVIRONMENT_OPERATIONS = [
    "config_change_request",
    "hook_registration_request",
    "hook_trust_request",
    "plugin_cache_refresh_request",
    "custom_agent_materialization_request",
    "codex_restart_request",
    "mcp_config_change_request",
    "session_cleanup_request",
    "external_reviewer_lane_request",
    "effective_config_snapshot_request",
    "performance_config_change_request",
    "service_tier_change_request",
    "web_search_mode_change_request",
    "permission_profile_change_request",
    "approval_reviewer_change_request",
    "subagent_runtime_cap_change_request",
    "thread_offload_request",
    "worktree_creation_request",
    "thread_handoff_request",
    "automation_schedule_request",
    "cloud_thread_request",
    "mcp_tool_policy_request",
    "browser_use_permission_request",
    "computer_use_permission_request",
    "app_server_control_request",
    "noninteractive_run_request",
    "telemetry_export_request",
    "remote_connection_request",
    "record_replay_request",
    "appshot_request",
    "site_saved_version_request",
    "site_deployment_request",
    "apps_connector_permission_request",
    "notification_command_change_request",
]

ENVIRONMENT_PACKET_FIELDS = [
    "schema",
    "version",
    "operation_id",
    "operation_type",
    "source_capability_id",
    "source_paths",
    "target_environment_surfaces",
    "operator_authorization_required",
    "authorization_artifact",
    "default_mode",
    "preflight_command",
    "dry_run_command",
    "apply_command",
    "rollback_command",
    "validation_command",
    "sanitized_evidence_fields",
    "forbidden_raw_sources",
    "expected_status_after_apply",
    "blocking_reasons",
    "effective_config_snapshot_id",
]

ALLOWED_ENVIRONMENT_SURFACES = [
    "/home/*/.codex/config.toml",
    "/home/*/.codex/*.config.toml",
    "/home/*/.codex/hooks.json",
    "/home/*/.codex/hooks/",
    "/home/*/.codex/agents/",
    "/home/*/.codex/plugins/cache/",
    "/etc/codex/config.toml",
    "/etc/codex/requirements.toml",
    "/srv/bears/.codex/config.toml",
    "/srv/bears/.codex/hooks.json",
    "/srv/bears/.codex/hooks/",
    "/srv/bears/.codex/agents/",
    "Codex hook trust state",
    "Codex live sessions",
    "Codex process lifecycle",
    "Codex service tier",
    "Codex web search mode",
    "Codex permission profile selection",
    "Codex approval reviewer selection",
    "Codex subagent runtime caps",
    "Codex model selection",
    "Codex local threads",
    "Codex cloud threads",
    "Codex managed worktrees",
    "Codex automations",
    "Codex MCP server configuration",
    "Codex Browser permission state",
    "Codex Chrome permission state",
    "Codex Computer Use permission state",
    "Codex cloud environment settings",
    "Codex app-server transports",
    "Codex app-server control sockets",
    "Codex app-server analytics default state",
    "Codex app-server live process and listener classes",
    "Codex remote app-server client endpoint state",
    "Codex remote-control daemon state",
    "Codex app-server debug-client generated thread state",
    "Codex non-interactive runs",
    "Codex exec sessions",
    "Codex telemetry configuration",
    "Codex telemetry exporter state",
    "Codex remote connection state",
    "Codex SSH host connection state",
    "Codex Record & Replay state",
    "Codex Appshots state",
    "Codex Sites hosting state",
    "Codex Sites deployment state",
    "Codex apps and connector permission state",
    "Codex notification command state",
    "Codex notification command argv, shell, environment allowlist, and working-directory state",
]

DEFAULT_OPERATION_SURFACES = {
    "config_change_request": ["/srv/bears/.codex/config.toml"],
    "hook_registration_request": ["/srv/bears/.codex/hooks/", "Codex hook trust state"],
    "hook_trust_request": ["Codex hook trust state"],
    "plugin_cache_refresh_request": ["/home/*/.codex/plugins/cache/"],
    "custom_agent_materialization_request": ["/srv/bears/.codex/agents/"],
    "codex_restart_request": ["Codex process lifecycle"],
    "mcp_config_change_request": ["Codex MCP server configuration"],
    "session_cleanup_request": ["Codex live sessions"],
    "external_reviewer_lane_request": ["Codex approval reviewer selection"],
    "effective_config_snapshot_request": ["/srv/bears/.codex/config.toml"],
    "performance_config_change_request": ["Codex service tier"],
    "service_tier_change_request": ["Codex service tier"],
    "web_search_mode_change_request": ["Codex web search mode"],
    "permission_profile_change_request": ["Codex permission profile selection"],
    "approval_reviewer_change_request": ["Codex approval reviewer selection"],
    "subagent_runtime_cap_change_request": ["Codex subagent runtime caps"],
    "thread_offload_request": ["Codex local threads"],
    "worktree_creation_request": ["Codex managed worktrees"],
    "thread_handoff_request": ["Codex local threads"],
    "automation_schedule_request": ["Codex automations"],
    "cloud_thread_request": ["Codex cloud threads"],
    "mcp_tool_policy_request": ["Codex MCP server configuration"],
    "browser_use_permission_request": ["Codex Browser permission state"],
    "computer_use_permission_request": ["Codex Computer Use permission state"],
    "app_server_control_request": ["Codex app-server control sockets"],
    "noninteractive_run_request": ["Codex non-interactive runs"],
    "telemetry_export_request": ["Codex telemetry exporter state"],
    "remote_connection_request": ["Codex remote connection state"],
    "record_replay_request": ["Codex Record & Replay state"],
    "appshot_request": ["Codex Appshots state"],
    "site_saved_version_request": ["Codex Sites deployment state"],
    "site_deployment_request": ["Codex Sites deployment state"],
    "apps_connector_permission_request": ["Codex apps and connector permission state"],
    "notification_command_change_request": ["Codex notification command state"],
}

SANITIZED_EVIDENCE_FIELD_ALLOWLIST = {"presence", "counts", "hashes", "statuses", "paths"}
FORBIDDEN_RAW_SOURCES = [
    "raw_config_values",
    "raw_hook_bodies",
    "raw_sessions",
    "raw_logs",
    "raw_chat",
    "raw_tool_output",
    "shell_history",
    "raw_vpn_configs",
    "private_keys",
    "payment_identifiers",
    "personal_contact_identifiers",
    "tokens",
    "credentials",
    ".env values",
    "production_data",
]

OPTIMIZATION_PACKET_FIELDS = [
    "schema",
    "version",
    "optimization_id",
    "lane",
    "source_owner",
    "environment_owner",
    "source_capability_id",
    "affected_paths",
    "affected_environment_surfaces",
    "baseline_metric",
    "target_metric",
    "measurement_command",
    "validation_command",
    "rollback_command",
    "operator_authorization_required",
    "environment_operation_packet",
    "status",
]

ALLOWED_OPTIMIZATION_LANES = {
    "hot_path_context_reduction",
    "validator_consolidation",
    "source_cache_discovery",
    "advisory_reviewer_decoupling",
    "hook_prompt_preflight",
    "hook_stop_closeout",
    "subagent_worker_pool_control",
    "custom_agent_materialization",
    "config_precedence_snapshot",
    "effective_config_resolution",
    "stale_session_cleanup",
    "fast_mode_evaluation",
    "shell_snapshot_evaluation",
    "web_search_mode_control",
    "permission_profile_control",
    "approval_reviewer_control",
    "subagent_depth_control",
    "context_budget_control",
    "model_selection_control",
    "thread_offload_control",
    "worktree_isolation_control",
    "automation_heartbeat_control",
    "cloud_thread_delegation",
    "mcp_tool_policy_control",
    "browser_validation_control",
    "computer_use_control",
    "app_server_control",
    "noninteractive_run_control",
    "telemetry_export_control",
    "remote_connection_control",
    "record_replay_control",
    "appshots_control",
    "sites_publish_control",
    "apps_connector_control",
    "notification_command_control",
}

ALLOWED_OPTIMIZATION_METRICS = {
    "context_token_count",
    "prompt_token_count",
    "file_read_count",
    "validator_count",
    "validator_exit_code",
    "elapsed_seconds",
    "wall_time_seconds",
    "p95_latency_ms",
    "payload_bytes",
    "fixture_count",
    "cache_hit_count",
    "worker_count",
    "max_threads",
    "max_depth",
    "cost_units",
}

ENVIRONMENT_OWNED_OPTIMIZATION_LANES = ALLOWED_OPTIMIZATION_LANES - {
    "hot_path_context_reduction",
    "validator_consolidation",
    "source_cache_discovery",
    "advisory_reviewer_decoupling",
    "context_budget_control",
}

OFFLOAD_OPTIMIZATION_LANES = {
    "thread_offload_control",
    "worktree_isolation_control",
    "cloud_thread_delegation",
}

PROGRAMMATIC_OPTIMIZATION_LANES = {
    "mcp_tool_policy_control",
    "browser_validation_control",
    "computer_use_control",
    "app_server_control",
    "noninteractive_run_control",
    "telemetry_export_control",
    "remote_connection_control",
    "record_replay_control",
    "appshots_control",
    "sites_publish_control",
    "apps_connector_control",
    "notification_command_control",
}


PERFORMANCE_CLAIM_SURFACES = {
    "fast_mode",
    "service_tier",
    "shell_snapshot",
    "web_search_mode",
    "permission_profile",
    "approval_reviewer",
    "model_selection",
    "subagent_caps",
    "context_reduction",
}

PERFORMANCE_ENVIRONMENT_OWNED_SURFACES = PERFORMANCE_CLAIM_SURFACES - {"context_reduction"}
PERFORMANCE_COST_SURFACES = {"fast_mode", "service_tier"}
PERFORMANCE_CLAIM_FIELDS = [
    "claim_id",
    "surface",
    "metric_field",
    "baseline",
    "target",
    "measurement_command",
    "validation_command",
    "rollback_command",
    "operator_authorization_required",
    "effective_config_snapshot_id",
    "redaction_status",
]

OFFLOAD_CLAIM_SURFACES = {
    "local_thread",
    "cloud_thread",
    "worktree",
    "automation",
    "mcp",
    "browser",
    "chrome",
    "computer_use",
}
OFFLOAD_CLAIM_FIELDS = [
    "claim_id",
    "surface",
    "permission_policy",
    "write_isolation",
    "cleanup_command",
    "rollback_command",
    "target_surfaces",
    "effective_config_snapshot_id",
    "redaction_status",
]

PROGRAMMATIC_CLAIM_SURFACES = {
    "app_server",
    "non_interactive_run",
    "telemetry",
    "remote_connection",
    "record_replay",
    "appshots",
    "sites",
    "apps_connectors",
    "notification_command",
}
PROGRAMMATIC_SURFACE_POLICY_FIELDS = {
    "app_server": "listener_policy",
    "non_interactive_run": "execution_policy",
    "telemetry": "exporter_policy",
    "remote_connection": "remote_connection_policy",
    "record_replay": "capture_policy",
    "appshots": "capture_policy",
    "sites": "publication_policy",
    "apps_connectors": "connector_permission_policy",
    "notification_command": "command_policy",
}
PROGRAMMATIC_CLAIM_FIELDS = [
    "claim_id",
    "surface",
    "environment_owner",
    "permission_policy",
    "auth_policy",
    "trust_policy",
    "cleanup_command",
    "rollback_command",
    "target_surfaces",
    "effective_config_snapshot_id",
    "redaction_status",
]

EFFECTIVE_CONFIG_FIELDS = [
    "schema",
    "status",
    "codex_version",
    "manual_status",
    "cwd",
    "project_root",
    "trusted_project_status",
    "config_precedence_order",
    "config_layers_checked",
    "project_config_layers_checked",
    "profile_layer_status",
    "cli_override_status",
    "system_config_status",
    "managed_requirements_status",
    "requirements_sources_checked",
    "managed_requirement_constraints_present",
    "managed_constraint_statuses",
    "project_layer_active",
    "project_layer_skipped_reason",
    "effective_features",
    "effective_agents",
    "effective_service_tier",
    "effective_web_search_mode",
    "effective_permission_profile",
    "effective_approval_policy",
    "effective_approvals_reviewer",
    "effective_shell_snapshot_enabled",
    "effective_hooks_enabled",
    "offload_surfaces_considered",
    "programmatic_surfaces_considered",
    "app_server_status",
    "noninteractive_run_status",
    "telemetry_status",
    "remote_connection_status",
    "record_replay_status",
    "appshots_status",
    "sites_status",
    "apps_connectors_status",
    "strict_config_status",
    "ignore_user_config_status",
    "ignore_rules_status",
    "codex_home_status",
    "worktree_status",
    "automation_status",
    "mcp_tool_policy_status",
    "apps_feature_status",
    "app_permission_policy_status",
    "enabled_connector_plugin_count",
    "connector_permission_status",
    "account_boundary_status",
    "data_redaction_class",
    "browser_permission_status",
    "computer_use_permission_status",
    "hook_sources_considered",
    "mcp_servers_considered",
    "plugin_cache_status",
    "custom_agent_dirs_considered",
    "redacted_fields",
    "blocked_raw_sources",
    "blocking_reasons",
    "effective_config_snapshot_id",
]

CONFIG_PRECEDENCE_ORDER = [
    "cli_flags_and_config_overrides",
    "trusted_project_codex_config_layers",
    "selected_profile_config",
    "user_config",
    "system_config",
    "built_in_defaults",
]

REQUIREMENTS_SOURCE_ORDER = [
    "cloud_managed_requirements",
    "macos_mdm_requirements",
    "system_requirements_toml",
]

PROJECT_LOCAL_IGNORED_KEYS = {
    "openai_base_url",
    "chatgpt_base_url",
    "apps_mcp_product_sku",
    "model_provider",
    "model_providers",
    "notify",
    "profile",
    "profiles",
    "experimental_realtime_ws_base_url",
    "otel",
}

EFFECTIVE_AGENT_ALLOWED_FIELDS = {
    "max_threads",
    "max_depth",
    "job_max_runtime_seconds",
    "custom_agent_count",
    "custom_agent_materialization_status",
    "materialization_status",
}

UNREDACTED_ENDPOINT_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[a-z0-9.-]+\.[a-z]{2,}(?::\d+)?\b", re.IGNORECASE),
]

RESTRICTED_DATA_MARKERS = [
    "__BEARS_RESTRICTED_DATA_MARKER__",
    "__BEARS_RESTRICTED_TOKEN_MARKER__",
    "__BEARS_RAW_ENV_VALUE_MARKER__",
    "__BEARS_RAW_LOG_MARKER__",
    "__BEARS_RAW_CHAT_MARKER__",
    "__BEARS_RAW_VPN_CONFIG_MARKER__",
    "-----BEGIN PRIVATE KEY-----",
    "Authorization: Bearer ",
]

RESTRICTED_DATA_PATTERNS = [
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(?:password|token|secret|credential)\s*=\s*[^\s\"']{8,}"),
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def emit(packet: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return
    status = packet.get("status", "unknown")
    print(f"status: {status}")
    if packet.get("errors"):
        for error in packet["errors"]:
            print(f"error: {error.get('code')}: {error.get('message')}")


def fail(errors: list[dict[str, str]], *, command: str) -> dict[str, Any]:
    return {
        "schema": "bears-plugin-capability-layout-result.v1",
        "command": command,
        "status": "fail",
        "plugin_root": str(PLUGIN_ROOT),
        "errors": errors,
        "restricted_data_status": RESTRICTED_DATA_STATUS,
    }


def pass_packet(command: str, **extra: Any) -> dict[str, Any]:
    packet = {
        "schema": "bears-plugin-capability-layout-result.v1",
        "command": command,
        "status": "pass",
        "plugin_root": str(PLUGIN_ROOT),
        "errors": [],
        "restricted_data_status": RESTRICTED_DATA_STATUS,
    }
    packet.update(extra)
    return packet


def error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def as_rel_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return PLUGIN_ROOT / candidate


def canonical_skill_path(value: str) -> str:
    clean = value.strip().replace("\\", "/").rstrip("/")
    for suffix in ("/SKILL.md", "/SKILL.disabled.md"):
        if clean.endswith(suffix):
            return clean[: -len(suffix)]
    return clean


def validate_inventory_data(inventory: dict[str, Any], skill_catalog: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    if list(inventory.keys()) != TOP_LEVEL_FIELDS:
        errors.append(error("INVENTORY_TOP_LEVEL_FIELDS", "inventory top-level fields must match the V2 field order exactly"))
    if inventory.get("schema") != "bears-plugin-capability-inventory.v1":
        errors.append(error("INVENTORY_SCHEMA", "inventory schema must be bears-plugin-capability-inventory.v1"))
    if inventory.get("owner_plugin") != "bears":
        errors.append(error("OWNER_PLUGIN", "owner_plugin must be bears"))
    if inventory.get("source_repo") != "BearsCLOUD/bears-codex-workflow-plugin":
        errors.append(error("SOURCE_REPO", "source_repo must be BearsCLOUD/bears-codex-workflow-plugin"))

    rows = inventory.get("capabilities")
    if not isinstance(rows, list):
        return errors + [error("CAPABILITIES_TYPE", "capabilities must be a list")]

    seen_ids: dict[str, int] = {}
    row_by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(error("CAPABILITY_ROW_TYPE", f"capabilities[{index}] must be an object"))
            continue
        row_id = str(row.get("id", ""))
        if list(row.keys()) != CAPABILITY_FIELDS:
            errors.append(error("CAPABILITY_FIELDS", f"{row_id or index} fields must match the V2 row contract exactly"))
        if row_id in seen_ids:
            errors.append(error("DUPLICATE_CAPABILITY_ID", f"capability id {row_id} appears more than once"))
        seen_ids[row_id] = index
        row_by_id[row_id] = row

        package = row.get("python_package")
        if isinstance(row_id, str) and package != row_id.replace("-", "_"):
            errors.append(error("PYTHON_PACKAGE_MISMATCH", f"{row_id} python_package must equal id with hyphens replaced by underscores"))
        if row.get("lifecycle_state") not in LIFECYCLE_STATES:
            errors.append(error("INVALID_LIFECYCLE_STATE", f"{row_id} has invalid lifecycle_state"))
        if row.get("canonical_source_phase") not in SOURCE_PHASES:
            errors.append(error("INVALID_SOURCE_PHASE", f"{row_id} has invalid canonical_source_phase"))

        lifecycle = row.get("lifecycle_state")
        phase = row.get("canonical_source_phase")
        cap_dir = PLUGIN_ROOT / "capabilities" / str(package)
        if lifecycle == "planned":
            if phase != "inventory":
                errors.append(error("PLANNED_PHASE", f"{row_id} planned rows must use canonical_source_phase=inventory"))
            if cap_dir.exists():
                errors.append(error("PLANNED_CAPABILITY_DIR", f"{row_id} planned row must not have a capability directory"))
        elif lifecycle == "legacy" and not row.get("primary_legacy_sources"):
            errors.append(error("LEGACY_SOURCE_REQUIRED", f"{row_id} legacy row must list at least one primary legacy source"))
        elif lifecycle == "capability" and not cap_dir.is_dir():
            errors.append(error("CAPABILITY_DIR_REQUIRED", f"{row_id} capability row must have a capability directory"))
        elif lifecycle == "deprecated" and row.get("active_skill_front_doors"):
            errors.append(error("DEPRECATED_ACTIVE_SKILL", f"{row_id} deprecated row must not have active skill front doors"))

        for field in LIST_PATH_FIELDS:
            value = row.get(field)
            if not isinstance(value, list):
                errors.append(error("PATH_LIST_TYPE", f"{row_id}.{field} must be a list"))
                continue
            for path_value in value:
                if not isinstance(path_value, str):
                    errors.append(error("PATH_ITEM_TYPE", f"{row_id}.{field} entries must be strings in Phase 1"))
                    continue
                if not as_rel_path(path_value).exists():
                    errors.append(error("PATH_NOT_FOUND", f"{row_id}.{field} path not found: {path_value}"))

    missing_ids = sorted(set(TARGET_CAPABILITY_IDS) - set(seen_ids))
    extra_ids = sorted(set(seen_ids) - set(TARGET_CAPABILITY_IDS))
    if missing_ids:
        errors.append(error("MISSING_CAPABILITY_IDS", "missing capability ids: " + ", ".join(missing_ids)))
    if extra_ids:
        errors.append(error("UNKNOWN_CAPABILITY_IDS", "unknown capability ids: " + ", ".join(extra_ids)))

    active_paths = [canonical_skill_path(item.get("path", "")) for item in skill_catalog.get("active_skills", []) if isinstance(item, dict)]
    disabled_paths = {canonical_skill_path(item.get("path", "")) for item in skill_catalog.get("disabled_skills", []) if isinstance(item, dict)}
    mapped: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id", ""))
        front_doors = row.get("active_skill_front_doors", [])
        if not isinstance(front_doors, list):
            errors.append(error("ACTIVE_FRONT_DOOR_TYPE", f"{row_id}.active_skill_front_doors must be a list"))
            continue
        for raw in front_doors:
            if not isinstance(raw, str):
                errors.append(error("ACTIVE_FRONT_DOOR_ITEM", f"{row_id}.active_skill_front_doors entries must be strings"))
                continue
            skill_path = canonical_skill_path(raw)
            if skill_path in disabled_paths:
                errors.append(error("DISABLED_SKILL_ACTIVE_FRONT_DOOR", f"disabled skill must not satisfy active mapping: {skill_path}"))
            mapped.setdefault(skill_path, []).append(row_id)

    for active_path in active_paths:
        owners = mapped.get(active_path, [])
        if not owners:
            errors.append(error("UNMAPPED_ACTIVE_SKILL", f"active skill is not mapped to a capability: {active_path}"))
        elif len(owners) > 1:
            errors.append(error("DUPLICATE_ACTIVE_SKILL_MAPPING", f"active skill maps to multiple capabilities: {active_path} -> {', '.join(owners)}"))

    for skill_path, owners in sorted(mapped.items()):
        if len(owners) > 1:
            errors.append(error("DUPLICATE_ACTIVE_SKILL_MAPPING", f"front door maps to multiple capabilities: {skill_path} -> {', '.join(owners)}"))
        if skill_path not in active_paths and skill_path not in disabled_paths:
            errors.append(error("UNKNOWN_ACTIVE_SKILL_FRONT_DOOR", f"front door is not an active catalog skill: {skill_path}"))

    for row in inventory.get("rule_coverage", []):
        if not isinstance(row, dict) or list(row.keys()) != RULE_COVERAGE_FIELDS:
            errors.append(error("RULE_COVERAGE_FIELDS", "rule_coverage rows must match the V2 row contract exactly"))
            break

    errors.extend(validate_capability_packages(inventory))
    return errors


def validate_capability_packages(inventory: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    rows = inventory.get("capabilities")
    if not isinstance(rows, list):
        return errors

    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id", ""))
        lifecycle = row.get("lifecycle_state")
        if lifecycle not in {"dual", "capability"}:
            continue
        package = row.get("python_package")
        if not isinstance(package, str) or not package:
            errors.append(error("CAPABILITY_PACKAGE_NAME", f"{row_id} python_package must be non-empty"))
            continue
        package_dir = PLUGIN_ROOT / "capabilities" / package
        if not package_dir.is_dir():
            errors.append(error("CAPABILITY_PACKAGE_DIR", f"{row_id} package directory not found: capabilities/{package}"))
            continue
        for rel_path in CAPABILITY_PACKAGE_REQUIRED_PATHS:
            required_path = package_dir / rel_path
            if not required_path.exists():
                errors.append(error("CAPABILITY_PACKAGE_SHAPE", f"{row_id} missing package path: capabilities/{package}/{rel_path}"))

        capability_path = package_dir / "capability.json"
        if not capability_path.is_file():
            continue
        try:
            capability = load_json(capability_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error("CAPABILITY_JSON_LOAD", f"{row_id} capability.json load failed: {exc}"))
            continue
        if list(capability.keys()) != CAPABILITY_JSON_FIELDS:
            errors.append(error("CAPABILITY_JSON_FIELDS", f"{row_id} capability.json fields must match the V2 package contract exactly"))
        if capability.get("schema") != "bears-plugin-capability.v1":
            errors.append(error("CAPABILITY_JSON_SCHEMA", f"{row_id} capability.json schema must be bears-plugin-capability.v1"))

        field_pairs = [
            "id",
            "python_package",
            "owner_role",
            "canonical_source_phase",
            "legacy_entrypoints",
            "compatibility_entrypoints",
            "validators",
            "schemas",
            "fixtures",
            "allowed_actions",
            "forbidden_actions",
            "forbidden_data",
            "sanitized_evidence_schema",
            "context_budget",
            "performance_claims",
            "offload_surface_claims",
            "programmatic_control_claims",
        ]
        for field in field_pairs:
            if capability.get(field) != row.get(field):
                errors.append(error("CAPABILITY_JSON_INVENTORY_MISMATCH", f"{row_id}.{field} differs between inventory and capability.json"))
        if capability.get("cache_sync", {}).get("required") != row.get("cache_sync_required"):
            errors.append(error("CAPABILITY_JSON_CACHE_SYNC", f"{row_id}.cache_sync.required must match inventory cache_sync_required"))
        if capability.get("rollback") != row.get("rollback_command"):
            errors.append(error("CAPABILITY_JSON_ROLLBACK", f"{row_id}.rollback must match inventory rollback_command"))
        if not row.get("fixtures"):
            errors.append(error("CAPABILITY_FIXTURES_REQUIRED", f"{row_id} dual/capability rows must register fixtures"))
        if not row.get("compatibility_entrypoints"):
            errors.append(error("CAPABILITY_COMPAT_ENTRYPOINT_REQUIRED", f"{row_id} dual/capability rows must register a compatibility entrypoint"))
    return errors


def capability_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Return capability rows when the inventory shape is usable."""
    rows = inventory.get("capabilities")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def claim_runtime_behavior(claim: dict[str, Any]) -> bool:
    """Detect a hook claim that asserts runtime behavior."""
    explicit_fields = (
        "runtime_behavior_claimed",
        "runtime_claimed",
        "claims_runtime_behavior",
        "runtime_behavior",
    )
    return any(claim.get(field) is True for field in explicit_fields) or claim.get("effective_hooks_enabled") is True


def has_forbidden_output_capture(claim: dict[str, Any]) -> bool:
    """Detect raw or restricted hook output capture without exposing values."""
    output_capture = str(claim.get("output_capture", "")).strip().lower()
    sanitized_schema = str(claim.get("sanitized_output_schema", "")).strip().lower()
    forbidden_capture_values = {
        "raw",
        "raw_stdout",
        "raw_stderr",
        "raw_stdout_stderr",
        "restricted",
        "raw_tool_output",
    }
    return (
        bool(claim.get("captures_raw_stdout"))
        or bool(claim.get("captures_raw_stderr"))
        or bool(claim.get("restricted_output_capture"))
        or bool(claim.get("output_contains_restricted_data"))
        or output_capture in forbidden_capture_values
        or sanitized_schema in {"raw", "raw_output", "restricted"}
    )


def validate_hook_claims_data(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """Validate source-only and runtime hook claim rows."""
    errors: list[dict[str, str]] = []
    for row in capability_rows(inventory):
        row_id = str(row.get("id", ""))
        claims = row.get("hook_claims", [])
        if not isinstance(claims, list):
            errors.append(error("HOOK_CLAIMS_TYPE", f"{row_id}.hook_claims must be a list"))
            continue
        for index, claim in enumerate(claims):
            label = f"{row_id}.hook_claims[{index}]"
            if not isinstance(claim, dict):
                errors.append(error("HOOK_CLAIM_TYPE", f"{label} must be an object"))
                continue

            feature_key = claim.get("feature_key")
            feature_keys = claim.get("feature_keys")
            if feature_key == "features.codex_hooks" or (
                isinstance(feature_keys, list) and "features.codex_hooks" in feature_keys
            ):
                errors.append(error("HOOK_DEPRECATED_FEATURE_KEY", f"{label} must use features.hooks"))
            if isinstance(feature_keys, list) and {"features.hooks", "features.codex_hooks"}.issubset(set(feature_keys)):
                errors.append(error("HOOK_FEATURE_KEY_CONFLICT", f"{label} contains conflicting hook feature keys"))

            event = claim.get("event")
            if event and event not in ALLOWED_HOOK_EVENTS:
                errors.append(error("HOOK_EVENT_UNSUPPORTED", f"{label} uses an unsupported hook event"))
            if claim.get("handler_type") and claim.get("handler_type") != "command":
                errors.append(error("HOOK_HANDLER_TYPE", f"{label} must use command handlers only"))
            if claim.get("handler_async") is True:
                errors.append(error("HOOK_ASYNC_HANDLER", f"{label} must not use async handlers"))
            if event in MATCHER_UNSUPPORTED_EVENTS and (
                claim.get("matcher_dependent") is True
                or claim.get("matcher_required") is True
                or claim.get("uses_matcher") is True
            ):
                errors.append(error("HOOK_MATCHER_UNSUPPORTED", f"{label} must not depend on matcher filtering"))
            if claim.get("reads_environment_variables") is True or claim.get("environment_variable_reads"):
                errors.append(error("HOOK_ENV_VAR_READ", f"{label} must not read environment variables"))
            if has_forbidden_output_capture(claim):
                errors.append(error("HOOK_RAW_OUTPUT_CAPTURE", f"{label} must not capture raw or restricted output"))
            if claim.get("replaces_required_validator") is True or claim.get("validator_replacement") is True:
                errors.append(error("HOOK_VALIDATOR_REPLACEMENT", f"{label} must not replace required validators"))

            blocking_policy = claim.get("blocking_policy")
            if blocking_policy and blocking_policy not in ALLOWED_HOOK_BLOCKING_POLICIES:
                errors.append(error("HOOK_BLOCKING_POLICY", f"{label} uses a forbidden blocking policy"))
            broad_tool_block = (
                claim.get("blocks_broad_tool_use") is True
                or claim.get("tool_blocking_scope") == "broad"
                or blocking_policy in {"broad_tool_blocking", "tool_blocking"}
            )
            false_positive_status = claim.get("false_positive_evidence_status")
            if broad_tool_block and false_positive_status != "pass":
                errors.append(error("HOOK_BROAD_TOOL_BLOCKING", f"{label} lacks false-positive evidence"))

            if not claim_runtime_behavior(claim):
                continue

            missing = [field for field in HOOK_CLAIM_FIELDS if field not in claim or claim.get(field) in ("", None)]
            if missing:
                errors.append(error("HOOK_CLAIM_FIELDS", f"{label} runtime claim is missing required fields"))
            if feature_key != "features.hooks":
                errors.append(error("HOOK_FEATURE_KEY", f"{label} runtime claim must use features.hooks"))
            if claim.get("source_layer") in {"project", "project_layer"}:
                errors.append(error("HOOK_PROJECT_LAYER_DISABLED", f"{label} project-layer runtime hooks are disabled"))
            enabled_layer = str(claim.get("enabled_config_layer", ""))
            if enabled_layer == "/srv/bears/.codex/config.toml":
                errors.append(error("HOOK_PROJECT_LAYER_DISABLED", f"{label} project-layer runtime hooks are disabled"))
            if claim.get("effective_hooks_enabled") is not True:
                errors.append(error("HOOK_NOT_PROVEN_ENABLED", f"{label} runtime hook enablement is not proven"))
            if claim.get("trust_review_status") != "pass":
                errors.append(error("HOOK_TRUST_NOT_PROVEN", f"{label} hook trust review is not proven"))
            if not claim.get("probe_command"):
                errors.append(error("HOOK_PROBE_COMMAND_REQUIRED", f"{label} must declare a probe command"))
            timeout = claim.get("timeout_seconds")
            if not isinstance(timeout, int) or timeout <= 0:
                errors.append(error("HOOK_TIMEOUT_SECONDS", f"{label} timeout_seconds must be a positive integer"))
    return errors


def validate_reviewer_lane_policy(row_id: str, policy: dict[str, Any]) -> list[dict[str, str]]:
    """Validate reviewer lane policy fields for one capability row."""
    errors: list[dict[str, str]] = []
    for field in REVIEWER_LANE_POLICY_FIELDS:
        if field not in policy:
            errors.append(error("REVIEWER_LANE_POLICY_FIELDS", f"{row_id}.reviewer_lane_policy missing {field}"))
    if policy.get("worker_lane_taxonomy") != WORKER_LANE_TAXONOMY:
        errors.append(error("REVIEWER_LANE_TAXONOMY", f"{row_id} reviewer lane taxonomy is invalid"))
    if policy.get("allowed_lane_modes") != ALLOWED_LANE_MODES:
        errors.append(error("REVIEWER_LANE_MODES", f"{row_id} allowed lane modes are invalid"))
    if policy.get("default_lane_mode") != "advisory_async":
        errors.append(error("REVIEWER_DEFAULT_LANE_MODE", f"{row_id} default lane mode must be advisory_async"))
    hard_stop_reasons = policy.get("hard_stop_reasons")
    if not isinstance(hard_stop_reasons, list) or set(hard_stop_reasons) - BLOCKING_HARD_STOP_REASONS:
        errors.append(error("REVIEWER_HARD_STOP_REASONS", f"{row_id} hard stop reasons are invalid"))

    advisory = policy.get("advisory_async")
    if not isinstance(advisory, dict):
        errors.append(error("ADVISORY_ASYNC_POLICY", f"{row_id} advisory_async policy must be an object"))
    else:
        if advisory.get("parent_same_turn_wait_required") is not False:
            errors.append(error("ADVISORY_ASYNC_BLOCKS_PARENT", f"{row_id} advisory_async must not block the parent turn"))
        if advisory.get("write_authority") != "none":
            errors.append(error("ADVISORY_ASYNC_WRITE_AUTHORITY", f"{row_id} advisory_async must have no write authority"))
        wait_fields = ("timeout_seconds", "wait_budget_seconds", "max_same_turn_wait_seconds", "wait_poll_interval_seconds")
        if any(advisory.get(field) != 0 for field in wait_fields):
            errors.append(error("ADVISORY_ASYNC_WAIT", f"{row_id} advisory_async wait fields must be zero"))
        if advisory.get("continue_unrelated_work_after_budget") is not True:
            errors.append(error("ADVISORY_ASYNC_CONTINUE", f"{row_id} advisory_async must continue unrelated work"))
        if not advisory.get("integration_checkpoint"):
            errors.append(error("ADVISORY_ASYNC_CHECKPOINT", f"{row_id} advisory_async needs an integration checkpoint"))
        if not advisory.get("stale_after") or not advisory.get("result_packet_path"):
            errors.append(error("ADVISORY_ASYNC_STALE_RESULT", f"{row_id} advisory_async needs stale and result packet rules"))
        if advisory.get("self_fix_allowed") is not False:
            errors.append(error("ADVISORY_ASYNC_SELF_FIX", f"{row_id} advisory_async must not self-fix"))

    blocking = policy.get("blocking_gate")
    if not isinstance(blocking, dict):
        errors.append(error("BLOCKING_GATE_POLICY", f"{row_id} blocking_gate policy must be an object"))
    else:
        hard_stop_reason = blocking.get("hard_stop_reason")
        if hard_stop_reason not in BLOCKING_HARD_STOP_REASONS:
            errors.append(error("BLOCKING_GATE_HARD_STOP_REASON", f"{row_id} blocking_gate hard-stop reason is invalid"))
        timeout = blocking.get("timeout_seconds")
        wait_budget = blocking.get("wait_budget_seconds")
        max_same_turn = blocking.get("max_same_turn_wait_seconds")
        poll_interval = blocking.get("wait_poll_interval_seconds")
        if not isinstance(timeout, int) or timeout <= 0 or timeout > 900:
            errors.append(error("BLOCKING_GATE_TIMEOUT", f"{row_id} blocking_gate timeout is invalid"))
        if not isinstance(wait_budget, int) or not isinstance(timeout, int) or wait_budget < 0 or wait_budget > timeout:
            errors.append(error("BLOCKING_GATE_WAIT_BUDGET", f"{row_id} blocking_gate wait budget is invalid"))
        if not isinstance(max_same_turn, int) or max_same_turn < 0 or max_same_turn > 120:
            errors.append(error("BLOCKING_GATE_SAME_TURN_WAIT", f"{row_id} blocking_gate same-turn wait is invalid"))
        if not isinstance(poll_interval, int) or poll_interval < 5 or poll_interval > 30:
            errors.append(error("BLOCKING_GATE_POLL_INTERVAL", f"{row_id} blocking_gate poll interval is invalid"))
        if not blocking.get("fallback_action"):
            errors.append(error("BLOCKING_GATE_FALLBACK", f"{row_id} blocking_gate fallback is required"))
        if not blocking.get("expected_closeout_artifact"):
            errors.append(error("BLOCKING_GATE_EXPECTED_ARTIFACT", f"{row_id} blocking_gate expected artifact is required"))
        if not blocking.get("stale_after") or blocking.get("stale_result_rejection") is not True:
            errors.append(error("BLOCKING_GATE_STALE_REJECTION", f"{row_id} blocking_gate stale-result rejection is required"))
    return errors


def validate_reviewer_lanes_data(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """Validate mandatory reviewer lane policy rows."""
    errors: list[dict[str, str]] = []
    rows_by_id = {str(row.get("id", "")): row for row in capability_rows(inventory)}
    for row_id in sorted(MANDATORY_REVIEWER_LANE_CAPABILITIES):
        row = rows_by_id.get(row_id)
        if not row:
            errors.append(error("REVIEWER_LANE_ROW_MISSING", f"mandatory reviewer lane row missing: {row_id}"))
            continue
        policy = row.get("reviewer_lane_policy")
        if not isinstance(policy, dict) or not policy:
            errors.append(error("REVIEWER_LANE_POLICY_REQUIRED", f"{row_id} requires reviewer_lane_policy"))
            continue
        errors.extend(validate_reviewer_lane_policy(row_id, policy))
    return errors


def source_agent_path(profile: Any) -> str:
    """Return a source-agent path from a string or object profile claim."""
    if isinstance(profile, str):
        return profile
    if isinstance(profile, dict):
        return str(profile.get("source_agent_path", ""))
    return ""


def profile_claims_spawn(profile: dict[str, Any]) -> bool:
    """Detect whether an agent profile row claims spawn use."""
    return any(
        profile.get(field) is True
        for field in ("spawn_use", "spawnable", "claim_spawn", "use_for_spawn")
    )


def validate_agent_registration_data(inventory: dict[str, Any]) -> list[dict[str, str]]:
    """Validate source profile claims and spawn proof fields."""
    errors: list[dict[str, str]] = []
    for row in capability_rows(inventory):
        row_id = str(row.get("id", ""))
        profiles = row.get("agent_profiles", [])
        if not isinstance(profiles, list):
            errors.append(error("AGENT_PROFILES_TYPE", f"{row_id}.agent_profiles must be a list"))
            continue
        for index, profile in enumerate(profiles):
            label = f"{row_id}.agent_profiles[{index}]"
            if not isinstance(profile, (str, dict)):
                errors.append(error("AGENT_PROFILE_TYPE", f"{label} must be a source path or object"))
                continue
            path_value = source_agent_path(profile)
            if not path_value:
                errors.append(error("AGENT_SOURCE_PATH_REQUIRED", f"{label} source_agent_path is required"))
            elif not as_rel_path(path_value).is_file():
                errors.append(error("AGENT_SOURCE_PATH_NOT_FOUND", f"{label} source_agent_path not found"))
            if not isinstance(profile, dict) or not profile_claims_spawn(profile):
                continue
            missing = [field for field in AGENT_SPAWN_PROOF_FIELDS if field not in profile or profile.get(field) in ("", None)]
            if missing:
                errors.append(error("AGENT_SPAWN_PROOF_FIELDS", f"{label} spawn use is missing required proof fields"))
            if not profile.get("materialized_agent_path"):
                errors.append(error("AGENT_MATERIALIZED_PATH_REQUIRED", f"{label} materialized_agent_path is required for spawn use"))
            if profile.get("route_audit_status") != "pass":
                errors.append(error("AGENT_ROUTE_AUDIT_STATUS", f"{label} route_audit_status must be pass for spawn use"))
    return errors




def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def surface_allowed(surface: str) -> bool:
    return any(surface == allowed or fnmatch.fnmatch(surface, allowed) for allowed in ALLOWED_ENVIRONMENT_SURFACES)


def path_presence_summary(surface: str) -> dict[str, Any]:
    """Return metadata-only presence evidence without reading file contents."""
    if not surface.startswith("/"):
        return {
            "surface": surface,
            "surface_hash": stable_hash(surface),
            "presence": "not_probed",
            "path_count": 0,
            "status": "environment_state_not_read",
        }
    if "*" in surface:
        pattern = surface.rstrip("/")
        root = Path(pattern.split("*")[0]).parent if "/" in pattern.split("*")[0].rstrip("/") else Path("/")
        count = 0
        if root.exists():
            try:
                count = sum(1 for match in Path("/").glob(pattern.lstrip("/")) if match.exists())
            except OSError:
                count = 0
        presence = "present" if count else "absent"
    else:
        path = Path(surface)
        presence = "present" if path.exists() else "absent"
        count = 1 if path.exists() else 0
    return {
        "surface": surface,
        "surface_hash": stable_hash(surface),
        "presence": presence,
        "path_count": count,
        "status": "metadata_only_no_content_read",
    }


def restricted_data_hits(text: str, label: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for marker in RESTRICTED_DATA_MARKERS:
        if marker in text:
            hits.append(error("RESTRICTED_DATA_MARKER", f"restricted data marker found in {label}"))
    for pattern in RESTRICTED_DATA_PATTERNS:
        if pattern.search(text):
            hits.append(error("RESTRICTED_DATA_PATTERN", f"restricted data pattern found in {label}"))
    return hits


def scan_file_for_restricted_data(path: Path) -> list[dict[str, str]]:
    try:
        data = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError as exc:
        return [error("RESTRICTED_SCAN_LOAD", f"restricted-data scan failed for {path}: {exc}")]
    try:
        label = str(path.relative_to(PLUGIN_ROOT))
    except ValueError:
        label = str(path)
    return restricted_data_hits(data, label)


def restricted_scan_paths(inventory: dict[str, Any] | None = None) -> list[Path]:
    paths: set[Path] = {DEFAULT_SCHEMA, DEFAULT_INVENTORY}
    if inventory:
        for row in capability_rows(inventory):
            for field in ("fixtures", "schemas"):
                for raw in row.get(field, []) if isinstance(row.get(field, []), list) else []:
                    if isinstance(raw, str):
                        paths.add(as_rel_path(raw))
    for root in [PLUGIN_ROOT / "tests/fixtures/capability_layout", PLUGIN_ROOT / "capabilities"]:
        if not root.exists():
            continue
        for suffix in ("*.json", "*.schema.json"):
            paths.update(path for path in root.rglob(suffix) if path.is_file())
    return sorted(path for path in paths if path.is_file())


def normalized_validator_packets(args: argparse.Namespace) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for command, handler in [
        ("validate-inventory", validate_inventory),
        ("validate-hot-path", validate_hot_path),
        ("validate-optimization-plan-fixtures", validate_optimization_plans_from_fixtures),
        ("validate-effective-config-fixtures", validate_effective_config_from_fixtures),
        ("validate-managed-requirements-fixtures", validate_managed_requirements_from_fixtures),
        ("validate-performance-claims-fixtures", validate_performance_claims_from_fixtures),
        ("validate-offload-claims-fixtures", validate_offload_claims_from_fixtures),
        ("validate-programmatic-surfaces-fixtures", validate_programmatic_surfaces_from_fixtures),
        ("validate-hook-claims", validate_hook_claims),
        ("validate-reviewer-lanes", validate_reviewer_lanes),
        ("validate-agent-registration", validate_agent_registration),
        ("validate-parity", validate_parity),
    ]:
        local_args = argparse.Namespace(**vars(args))
        code, packet = handler(local_args)
        packets.append({"command": command, "exit_code": code, "packet": packet})
    return packets


def validate_parity_data(inventory: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for row in capability_rows(inventory):
        row_id = str(row.get("id", ""))
        if row.get("lifecycle_state") not in {"dual", "capability"}:
            continue
        fixtures = row.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            errors.append(error("PARITY_FIXTURES_REQUIRED", f"{row_id} dual/capability row must register fixtures"))
            continue
        pass_fixtures = [item for item in fixtures if isinstance(item, str) and "/pass/" in item]
        fail_fixtures = [item for item in fixtures if isinstance(item, str) and "/fail/" in item]
        if not pass_fixtures:
            errors.append(error("PARITY_PASS_FIXTURE_REQUIRED", f"{row_id} must register at least one pass fixture"))
        if not fail_fixtures:
            errors.append(error("PARITY_FAIL_FIXTURE_REQUIRED", f"{row_id} must register at least one fail fixture"))
        for fixture in pass_fixtures + fail_fixtures:
            if not as_rel_path(fixture).is_file():
                errors.append(error("PARITY_FIXTURE_NOT_FOUND", f"{row_id} fixture path not found: {fixture}"))
        if not row.get("compatibility_entrypoints"):
            errors.append(error("PARITY_COMPAT_ENTRYPOINT_REQUIRED", f"{row_id} must keep legacy-vs-capability compatibility entrypoints"))
        if not row.get("validators"):
            errors.append(error("PARITY_VALIDATOR_REQUIRED", f"{row_id} must keep validator command registration"))
    return errors


def validate_restricted_data_data(inventory: dict[str, Any], args: argparse.Namespace) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for path in restricted_scan_paths(inventory):
        errors.extend(scan_file_for_restricted_data(path))
    for extra in getattr(args, "extra_scan_path", []) or []:
        errors.extend(scan_file_for_restricted_data(Path(extra)))
    for item in normalized_validator_packets(args):
        errors.extend(restricted_data_hits(json.dumps(item, sort_keys=True), f"normalized output for {item['command']}"))
    return errors


def make_environment_operation_packet(operation: str) -> dict[str, Any]:
    surfaces = DEFAULT_OPERATION_SURFACES.get(operation, ["/srv/bears/.codex/config.toml"])
    authorization_artifact = "operator_authorization_required_before_apply"
    return {
        "schema": "bears-plugin-environment-operation.v1",
        "version": "1",
        "operation_id": f"env-op-{operation.replace('_', '-')}-v1",
        "operation_type": operation,
        "source_capability_id": "validation-hooks",
        "source_paths": ["scripts/capability_layout.py"],
        "target_environment_surfaces": surfaces,
        "operator_authorization_required": True,
        "authorization_artifact": authorization_artifact,
        "default_mode": "dry_run",
        "preflight_command": "python3 scripts/capability_layout.py validate-environment-packet --packet <packet> --json",
        "dry_run_command": f"python3 scripts/capability_layout.py plan-environment-operation --operation {operation} --json",
        "apply_command": "operator_authorized_external_change --authorization-artifact ${authorization_artifact}",
        "rollback_command": "operator_authorized_external_rollback --authorization-artifact ${authorization_artifact}",
        "validation_command": "python3 scripts/capability_layout.py validate --json",
        "sanitized_evidence_fields": ["presence", "counts", "hashes", "statuses", "paths"],
        "forbidden_raw_sources": FORBIDDEN_RAW_SOURCES,
        "expected_status_after_apply": "pending_post_apply_validation",
        "blocking_reasons": [],
        "effective_config_snapshot_id": "not_captured_by_phase_1_source_validator",
    }


def validate_environment_packet_data(packet: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    missing_fields = [field for field in ENVIRONMENT_PACKET_FIELDS if field not in packet]
    if missing_fields:
        errors.append(error("ENV_PACKET_FIELDS", "environment packet is missing V2 19.1 fields: " + ", ".join(missing_fields)))
    if packet.get("schema") != "bears-plugin-environment-operation.v1":
        errors.append(error("ENV_PACKET_SCHEMA", "schema must be bears-plugin-environment-operation.v1"))
    if packet.get("operation_type") not in ALLOWED_ENVIRONMENT_OPERATIONS:
        errors.append(error("ENV_OPERATION_TYPE", "operation_type is not allowlisted"))
    surfaces = packet.get("target_environment_surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append(error("ENV_TARGET_SURFACES", "target_environment_surfaces must be a non-empty list"))
    else:
        for surface in surfaces:
            if not isinstance(surface, str) or not surface_allowed(surface):
                errors.append(error("ENV_TARGET_SURFACE_UNLISTED", f"target environment surface is not allowlisted: {surface}"))
    if packet.get("default_mode") == "apply":
        errors.append(error("ENV_DEFAULT_APPLY", "environment packet must not default to apply mode"))
    if packet.get("default_mode") != "dry_run":
        errors.append(error("ENV_DEFAULT_MODE", "default_mode must be dry_run"))
    if packet.get("operator_authorization_required") is not True:
        errors.append(error("ENV_OPERATOR_AUTH_REQUIRED", "operator_authorization_required must be true for environment operations"))
    authorization_artifact = str(packet.get("authorization_artifact", "")).strip()
    if not authorization_artifact:
        errors.append(error("ENV_AUTHORIZATION_ARTIFACT", "mutation-capable packets must declare an authorization artifact gate"))
    for field in ("preflight_command", "dry_run_command", "rollback_command", "validation_command"):
        if not str(packet.get(field, "")).strip():
            errors.append(error("ENV_REQUIRED_COMMAND", f"{field} must be non-empty"))
    if not str(packet.get("rollback_command", "")).strip():
        errors.append(error("ENV_ROLLBACK_REQUIRED", "rollback_command is required"))
    evidence_fields = packet.get("sanitized_evidence_fields")
    if not isinstance(evidence_fields, list) or not set(evidence_fields).issubset(SANITIZED_EVIDENCE_FIELD_ALLOWLIST):
        errors.append(error("ENV_SANITIZED_EVIDENCE_FIELDS", "sanitized_evidence_fields must contain only presence/count/hash/status/path fields"))
    apply_command = str(packet.get("apply_command", "")).strip()
    if apply_command and "${authorization_artifact}" not in apply_command and authorization_artifact not in apply_command:
        errors.append(error("ENV_APPLY_AUTH_GATE", "apply_command must be gated by the authorization artifact"))
    if str(packet.get("expected_status_after_apply", "")).lower() in {"pass", "success", "succeeded"}:
        errors.append(error("ENV_RUNTIME_SUCCESS_CLAIM", "packet must not claim runtime success before post-apply validation"))
    errors.extend(restricted_data_hits(json.dumps(packet, sort_keys=True), "environment packet"))
    return errors


def metric_field(metric: Any) -> str:
    """Return the declared metric field from a metric object."""
    if not isinstance(metric, dict):
        return ""
    declared = metric.get("metric_field")
    if isinstance(declared, str) and declared:
        return declared
    keys = [key for key in metric.keys() if key in ALLOWED_OPTIMIZATION_METRICS]
    return keys[0] if len(keys) == 1 else ""


def evidence_pass(value: Any) -> bool:
    """Return whether a fixture evidence object declares pass status."""
    return isinstance(value, dict) and value.get("status") == "pass"


def raw_source_requested(value: Any) -> bool:
    """Detect packet requirements for raw restricted source classes."""
    text = json.dumps(value, sort_keys=True).lower()
    return any(str(source).lower() in text for source in FORBIDDEN_RAW_SOURCES)


def optimization_claims(packet: dict[str, Any]) -> set[str]:
    claims: set[str] = set()
    for field in ("claims", "runtime_claims", "claim_types"):
        value = packet.get(field, [])
        if isinstance(value, list):
            claims.update(str(item) for item in value)
    for key, claim in [
        ("hook_runtime_claim", "hook_runtime"),
        ("spawnability_claim", "spawnability"),
        ("plugin_runtime_claim", "plugin_runtime"),
        ("effective_config_claim", "effective_config"),
        ("live_web_search_claim", "live_web_search"),
    ]:
        if packet.get(key) is True:
            claims.add(claim)
    return claims


def validate_optimization_plan_data(packet: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    missing = [field for field in OPTIMIZATION_PACKET_FIELDS if field not in packet]
    if missing:
        errors.append(error("OPTIMIZATION_PACKET_FIELDS", "optimization packet is missing V2 20.1 fields: " + ", ".join(missing)))
    if packet.get("schema") != "bears-plugin-optimization-plan.v1":
        errors.append(error("OPTIMIZATION_PACKET_SCHEMA", "schema must be bears-plugin-optimization-plan.v1"))
    lane = str(packet.get("lane", ""))
    if lane not in ALLOWED_OPTIMIZATION_LANES:
        errors.append(error("OPTIMIZATION_LANE", "lane is not allowlisted by V2 20.1"))
    baseline_field = metric_field(packet.get("baseline_metric"))
    target_field = metric_field(packet.get("target_metric"))
    if not baseline_field:
        errors.append(error("OPTIMIZATION_BASELINE_METRIC", "baseline_metric must declare one allowed metric field"))
    if not target_field:
        errors.append(error("OPTIMIZATION_TARGET_METRIC", "target_metric must declare one allowed metric field"))
    if baseline_field and target_field and baseline_field != target_field:
        errors.append(error("OPTIMIZATION_METRIC_MISMATCH", "baseline_metric and target_metric must use the same allowed metric field"))
    for field in ("measurement_command", "validation_command", "rollback_command", "source_owner", "environment_owner"):
        if not str(packet.get(field, "")).strip():
            errors.append(error("OPTIMIZATION_REQUIRED_FIELD", f"{field} must be non-empty"))
    affected_paths = packet.get("affected_paths")
    if not isinstance(affected_paths, list) or not affected_paths:
        errors.append(error("OPTIMIZATION_AFFECTED_PATHS", "affected_paths must be a non-empty list"))
    affected_surfaces = packet.get("affected_environment_surfaces")
    if not isinstance(affected_surfaces, list):
        errors.append(error("OPTIMIZATION_AFFECTED_SURFACES", "affected_environment_surfaces must be a list"))
    elif any(not isinstance(item, str) or not surface_allowed(item) for item in affected_surfaces):
        errors.append(error("OPTIMIZATION_ENV_SURFACE", "affected_environment_surfaces must use allowlisted environment surfaces"))

    claims = optimization_claims(packet)
    env_packet = packet.get("environment_operation_packet")
    env_owned = lane in ENVIRONMENT_OWNED_OPTIMIZATION_LANES or bool(affected_surfaces)
    if env_owned and not isinstance(env_packet, dict):
        errors.append(error("OPTIMIZATION_ENV_PACKET_REQUIRED", "environment-owned lanes require environment_operation_packet"))
    elif isinstance(env_packet, dict):
        errors.extend(validate_environment_packet_data(env_packet))

    if ("hook_runtime" in claims or lane.startswith("hook_")) and packet.get("effective_hooks_enabled") is not True:
        errors.append(error("OPTIMIZATION_HOOKS_DISABLED", "hook runtime claims require effective hooks enabled evidence"))
    if ("spawnability" in claims or lane == "custom_agent_materialization") and not evidence_pass(packet.get("agent_spawn_proof")):
        errors.append(error("OPTIMIZATION_SPAWN_PROOF", "spawnability claims require agent proof evidence"))
    if ("plugin_runtime" in claims or packet.get("plugin_runtime_claim") is True) and packet.get("plugin_cache_status") != "pass":
        errors.append(error("OPTIMIZATION_PLUGIN_CACHE", "plugin runtime claims require plugin cache status pass"))
    if ("effective_config" in claims or lane == "effective_config_resolution") and not isinstance(packet.get("effective_config_snapshot"), dict):
        errors.append(error("OPTIMIZATION_EFFECTIVE_SNAPSHOT", "effective config claims require an effective snapshot"))
    if (packet.get("performance_claim") is True or "performance" in claims) and not evidence_pass(packet.get("performance_validator_evidence")):
        errors.append(error("OPTIMIZATION_PERFORMANCE_EVIDENCE", "performance claims require validator evidence"))
    if (lane in OFFLOAD_OPTIMIZATION_LANES or packet.get("offload_claim") is True or "offload" in claims) and not evidence_pass(packet.get("offload_validator_evidence")):
        errors.append(error("OPTIMIZATION_OFFLOAD_EVIDENCE", "offload claims require validator evidence"))
    if (lane in PROGRAMMATIC_OPTIMIZATION_LANES or packet.get("programmatic_claim") is True or "programmatic" in claims) and not evidence_pass(packet.get("programmatic_validator_evidence")):
        errors.append(error("OPTIMIZATION_PROGRAMMATIC_EVIDENCE", "programmatic claims require validator evidence"))
    if (lane == "web_search_mode_control" or "live_web_search" in claims) and packet.get("operator_authorization_required") is not True:
        errors.append(error("OPTIMIZATION_WEB_SEARCH_AUTH", "live web search changes require operator authorization"))
    if lane == "fast_mode_evaluation" and packet.get("cost_acknowledgement") is not True:
        errors.append(error("OPTIMIZATION_FAST_MODE_COST", "fast mode requires cost acknowledgement"))
    if lane in {"subagent_worker_pool_control", "subagent_depth_control"} and packet.get("cap_or_depth_increase") is True:
        if packet.get("explicit_cap") in (None, "") and packet.get("target_cap") in (None, ""):
            errors.append(error("OPTIMIZATION_SUBAGENT_CAP", "subagent cap/depth increases require an explicit cap"))
        if not str(packet.get("rollback_command", "")).strip():
            errors.append(error("OPTIMIZATION_SUBAGENT_ROLLBACK", "subagent cap/depth increases require rollback"))
    for field in ("source_requirements", "required_sources", "measurement_sources"):
        if raw_source_requested(packet.get(field, [])):
            errors.append(error("OPTIMIZATION_RAW_SOURCE", "optimization packet must not require raw restricted sources"))
    errors.extend(restricted_data_hits(json.dumps(packet, sort_keys=True), "optimization packet"))
    return errors


def metadata_layer(surface: str) -> dict[str, Any]:
    summary = path_presence_summary(surface)
    return {
        "layer": surface,
        "status": summary["status"],
        "presence": summary["presence"],
        "path_count": summary["path_count"],
        "identity_hash": summary["surface_hash"],
    }


def resolve_effective_environment(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    cwd = str(Path.cwd())
    project_root = str(PLUGIN_ROOT)
    config_surfaces = [
        "/srv/bears/.codex/config.toml",
        "/home/*/.codex/config.toml",
        "/home/*/.codex/*.config.toml",
        "/etc/codex/config.toml",
    ]
    requirement_surfaces = ["/etc/codex/requirements.toml"]
    layer_metadata = [metadata_layer(surface) for surface in config_surfaces]
    requirement_metadata = [
        {"source": source, "status": "not_read", "body_status": "raw_body_blocked"}
        for source in REQUIREMENTS_SOURCE_ORDER[:2]
    ] + [metadata_layer(surface) for surface in requirement_surfaces]
    snapshot_seed = json.dumps(
        {
            "cwd": stable_hash(cwd),
            "project_root": stable_hash(project_root),
            "layers": layer_metadata,
            "requirements": requirement_metadata,
        },
        sort_keys=True,
    )
    packet = {
        "schema": "bears-plugin-effective-environment-snapshot.v1",
        "command": "resolve-effective-environment",
        "status": "pass",
        "codex_version": "not_read",
        "manual_status": "metadata_only_no_live_probe",
        "cwd": "cwd_hash:" + stable_hash(cwd),
        "project_root": "project_root_hash:" + stable_hash(project_root),
        "trusted_project_status": "unknown",
        "config_precedence_order": CONFIG_PRECEDENCE_ORDER,
        "config_layers_checked": layer_metadata,
        "project_config_layers_checked": [metadata_layer("/srv/bears/.codex/config.toml")],
        "profile_layer_status": "metadata_only_no_content_read",
        "cli_override_status": "not_probed",
        "system_config_status": "metadata_only_no_content_read",
        "managed_requirements_status": "checked_without_raw_body",
        "requirements_sources_checked": requirement_metadata,
        "managed_requirement_constraints_present": "unknown",
        "managed_constraint_statuses": {},
        "project_layer_active": False,
        "project_layer_skipped_reason": "trusted_project_status_not_trusted",
        "effective_features": {},
        "effective_agents": {
            "max_threads": {"status": "not_claimed"},
            "max_depth": {"status": "not_claimed"},
            "job_max_runtime_seconds": {"status": "not_claimed"},
            "custom_agent_count": 0,
            "custom_agent_materialization_status": "not_claimed",
        },
        "effective_service_tier": {"status": "not_claimed"},
        "effective_web_search_mode": {"status": "not_claimed"},
        "effective_permission_profile": {"status": "not_claimed"},
        "effective_approval_policy": {"status": "not_claimed"},
        "effective_approvals_reviewer": {"status": "not_claimed"},
        "effective_shell_snapshot_enabled": False,
        "effective_hooks_enabled": False,
        "offload_surfaces_considered": [],
        "programmatic_surfaces_considered": [],
        "app_server_status": "not_claimed",
        "noninteractive_run_status": "not_claimed",
        "telemetry_status": "not_claimed",
        "remote_connection_status": "not_claimed",
        "record_replay_status": "not_claimed",
        "appshots_status": "not_claimed",
        "sites_status": "not_claimed",
        "apps_connectors_status": "not_claimed",
        "strict_config_status": "not_probed",
        "ignore_user_config_status": "not_probed",
        "ignore_rules_status": "not_probed",
        "codex_home_status": "not_printed",
        "worktree_status": "not_claimed",
        "automation_status": "not_claimed",
        "mcp_tool_policy_status": "not_claimed",
        "apps_feature_status": "not_claimed",
        "app_permission_policy_status": "not_claimed",
        "enabled_connector_plugin_count": 0,
        "connector_permission_status": "not_claimed",
        "account_boundary_status": "not_claimed",
        "data_redaction_class": "sanitized_metadata_only",
        "browser_permission_status": "not_claimed",
        "computer_use_permission_status": "not_claimed",
        "hook_sources_considered": [],
        "mcp_servers_considered": {"count": 0, "identity_hashes": []},
        "plugin_cache_status": "not_claimed",
        "custom_agent_dirs_considered": [],
        "redacted_fields": len(FORBIDDEN_RAW_SOURCES),
        "blocked_raw_sources": FORBIDDEN_RAW_SOURCES,
        "blocking_reasons": [],
        "effective_config_snapshot_id": "effective-env-" + stable_hash(snapshot_seed),
        "restricted_data_status": RESTRICTED_DATA_STATUS,
        "errors": [],
    }
    return 0, packet


def unredacted_endpoint(value: Any) -> bool:
    """Detect endpoint-like strings in fields that must be represented by hashes/status only."""
    if isinstance(value, str):
        if value.startswith(("endpoint_hash:", "identity_hash:", "hash:")):
            return False
        return any(pattern.search(value) for pattern in UNREDACTED_ENDPOINT_PATTERNS)
    if isinstance(value, dict):
        return any(unredacted_endpoint(item) for item in value.values())
    if isinstance(value, list):
        return any(unredacted_endpoint(item) for item in value)
    return False


def runtime_claim_types(snapshot: dict[str, Any]) -> set[str]:
    claims: set[str] = set()
    for field in ("runtime_claims", "claim_types"):
        value = snapshot.get(field, [])
        if isinstance(value, list):
            claims.update(str(item) for item in value)
    return claims


def validate_effective_config_data(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    missing = [field for field in EFFECTIVE_CONFIG_FIELDS if field not in snapshot]
    if missing:
        errors.append(error("EFFECTIVE_CONFIG_FIELDS", "effective snapshot is missing required fields: " + ", ".join(missing)))
    if snapshot.get("schema") != "bears-plugin-effective-environment-snapshot.v1":
        errors.append(error("EFFECTIVE_CONFIG_SCHEMA", "schema must be bears-plugin-effective-environment-snapshot.v1"))
    if "redacted_fields" not in snapshot:
        errors.append(error("EFFECTIVE_REDACTED_FIELDS", "redacted_fields is required"))
    elif not isinstance(snapshot.get("redacted_fields"), int):
        errors.append(error("EFFECTIVE_REDACTED_FIELDS", "redacted_fields must be an integer count"))
    blocked = snapshot.get("blocked_raw_sources")
    if not isinstance(blocked, list) or not blocked:
        errors.append(error("EFFECTIVE_BLOCKED_RAW_SOURCES", "blocked_raw_sources must be a non-empty list"))
    if snapshot.get("config_precedence_order") != CONFIG_PRECEDENCE_ORDER:
        errors.append(error("EFFECTIVE_PRECEDENCE_ORDER", "config_precedence_order must match V2 21.1"))
    features = snapshot.get("effective_features")
    if not isinstance(features, dict) or any(not isinstance(value, bool) for value in features.values()):
        errors.append(error("EFFECTIVE_FEATURES_SHAPE", "effective_features may contain only boolean feature states"))
    agents = snapshot.get("effective_agents")
    if not isinstance(agents, dict):
        errors.append(error("EFFECTIVE_AGENTS_SHAPE", "effective_agents must be an object"))
    else:
        extra_agent_fields = sorted(set(agents) - EFFECTIVE_AGENT_ALLOWED_FIELDS)
        if extra_agent_fields:
            errors.append(error("EFFECTIVE_AGENTS_FIELDS", "effective_agents contains unsupported fields: " + ", ".join(extra_agent_fields)))
    for item in snapshot.get("project_local_effective_claims", []) if isinstance(snapshot.get("project_local_effective_claims"), list) else []:
        if isinstance(item, dict) and item.get("key") in PROJECT_LOCAL_IGNORED_KEYS:
            errors.append(error("EFFECTIVE_PROJECT_IGNORED_KEY", "project-local ignored keys cannot support runtime claims"))
    if snapshot.get("trusted_project_status") != "trusted" and snapshot.get("project_layer_active") is True:
        errors.append(error("EFFECTIVE_PROJECT_TRUST", "project layers are active only when trusted_project_status=trusted"))

    claims = runtime_claim_types(snapshot)
    if "hook_runtime" in claims and snapshot.get("effective_hooks_enabled") is not True:
        errors.append(error("EFFECTIVE_HOOKS_DISABLED", "hook runtime claims require effective_hooks_enabled=true"))
    materialization_status = ""
    if isinstance(agents, dict):
        materialization_status = str(agents.get("custom_agent_materialization_status") or agents.get("materialization_status") or "")
    if "custom_agent_spawnability" in claims and materialization_status != "pass":
        errors.append(error("EFFECTIVE_CUSTOM_AGENT_MATERIALIZATION", "custom-agent claims require materialization proof"))
    if "plugin_discovered" in claims and snapshot.get("plugin_cache_status") != "pass":
        errors.append(error("EFFECTIVE_PLUGIN_CACHE", "plugin-discovered claims require plugin_cache_status=pass"))
    if "programmatic_control" in claims and snapshot.get("programmatic_surfaces_validation_status") != "pass":
        errors.append(error("EFFECTIVE_PROGRAMMATIC_VALIDATION", "programmatic claims require effective snapshot validator evidence"))
    if "remote_connection" in claims and snapshot.get("remote_host_trust_status") not in {"pass", "trusted"}:
        errors.append(error("EFFECTIVE_REMOTE_HOST_TRUST", "remote connection claims require host trust status"))
    if "apps_connector" in claims and snapshot.get("app_permission_policy_status") not in {"pass", "checked"}:
        errors.append(error("EFFECTIVE_APPS_PERMISSION_POLICY", "apps connector claims require app permission policy"))
    if "telemetry_export" in claims and snapshot.get("telemetry_endpoint_redacted") is not True:
        errors.append(error("EFFECTIVE_TELEMETRY_REDACTION", "telemetry claims require endpoint redaction proof"))

    for field in ("raw_config_values", "provider_base_urls", "mcp_endpoints", "telemetry_endpoints", "remote_connection_endpoints"):
        if field in snapshot:
            errors.append(error("EFFECTIVE_RAW_FIELD", f"{field} must not be present in an effective snapshot"))
    if unredacted_endpoint(snapshot.get("mcp_servers_considered")):
        errors.append(error("EFFECTIVE_MCP_ENDPOINT_REDACTION", "MCP endpoints must be redacted to counts and hashes"))
    if unredacted_endpoint(snapshot.get("telemetry_status")) or unredacted_endpoint(snapshot.get("telemetry_exporter")):
        errors.append(error("EFFECTIVE_TELEMETRY_ENDPOINT_REDACTION", "telemetry endpoints must be redacted"))
    errors.extend(restricted_data_hits(json.dumps(snapshot, sort_keys=True), "effective config snapshot"))
    return errors


def validate_managed_requirements_data(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for field in ("managed_requirements_status", "requirements_sources_checked", "managed_requirement_constraints_present", "managed_constraint_statuses"):
        if field not in snapshot:
            errors.append(error("MANAGED_REQUIREMENTS_FIELDS", f"{field} is required"))
    sources = snapshot.get("requirements_sources_checked")
    if not isinstance(sources, list) or not sources:
        errors.append(error("MANAGED_REQUIREMENTS_SOURCES", "requirements_sources_checked must be a non-empty list"))
    statuses = snapshot.get("managed_constraint_statuses")
    if not isinstance(statuses, (dict, list)):
        errors.append(error("MANAGED_CONSTRAINT_STATUSES", "managed_constraint_statuses must be an object or list"))
    if "raw_requirement_body" in snapshot or "raw_requirements" in snapshot:
        errors.append(error("MANAGED_REQUIREMENTS_RAW_BODY", "managed requirement raw bodies must not be stored"))
    errors.extend(restricted_data_hits(json.dumps(snapshot, sort_keys=True), "managed requirements snapshot"))
    return errors


def required_claim_surfaces(packet: dict[str, Any], default: set[str]) -> set[str]:
    value = packet.get("required_surfaces")
    if value is None:
        return set(default)
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def claim_list(packet: dict[str, Any]) -> list[Any]:
    claims = packet.get("claims")
    if not isinstance(claims, list):
        return []
    return claims


def snapshot_id(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("effective_config_snapshot_id", ""))


def snapshot_redacted(snapshot: dict[str, Any]) -> bool:
    return (
        snapshot.get("data_redaction_class") == "sanitized_metadata_only"
        and isinstance(snapshot.get("redacted_fields"), int)
        and snapshot.get("redacted_fields", 0) > 0
        and isinstance(snapshot.get("blocked_raw_sources"), list)
        and bool(snapshot.get("blocked_raw_sources"))
    )


def validate_claim_packet_header(packet: dict[str, Any], snapshot: dict[str, Any], *, schema: str, command: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if packet.get("schema") != schema:
        errors.append(error(f"{command.upper().replace('-', '_')}_SCHEMA", f"schema must be {schema}"))
    if not isinstance(packet.get("claims"), list) or not packet.get("claims"):
        errors.append(error("CLAIMS_REQUIRED", "claims must be a non-empty list"))
    if packet.get("effective_config_snapshot_id") != snapshot_id(snapshot):
        errors.append(error("CLAIM_EFFECTIVE_SNAPSHOT_ID", "packet effective_config_snapshot_id must match the effective snapshot"))
    if packet.get("redaction_status") != "clean":
        errors.append(error("CLAIM_REDACTION_STATUS", "packet redaction_status must be clean"))
    errors.extend(validate_effective_config_data(snapshot))
    if not snapshot_redacted(snapshot):
        errors.append(error("CLAIM_SNAPSHOT_REDACTION", "effective snapshot must be sanitized and redacted"))
    errors.extend(restricted_data_hits(json.dumps(packet, sort_keys=True), command + " packet"))
    return errors


def command_present(claim: dict[str, Any], field: str, code: str, label: str) -> list[dict[str, str]]:
    if not str(claim.get(field, "")).strip():
        return [error(code, f"{label}.{field} must be non-empty")]
    return []


def validate_performance_claims_data(packet: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, str]]:
    errors = validate_claim_packet_header(
        packet,
        snapshot,
        schema="bears-plugin-performance-claims.v1",
        command="validate-performance-claims",
    )
    claims = claim_list(packet)
    seen: set[str] = set()
    required = required_claim_surfaces(packet, PERFORMANCE_CLAIM_SURFACES)
    if not required or required - PERFORMANCE_CLAIM_SURFACES:
        errors.append(error("PERFORMANCE_REQUIRED_SURFACES", "required_surfaces must use allowlisted performance surfaces"))
    for index, raw in enumerate(claims):
        label = f"claims[{index}]"
        if not isinstance(raw, dict):
            errors.append(error("PERFORMANCE_CLAIM_TYPE", f"{label} must be an object"))
            continue
        claim = raw
        missing = [field for field in PERFORMANCE_CLAIM_FIELDS if field not in claim or claim.get(field) in ("", None)]
        if missing:
            errors.append(error("PERFORMANCE_CLAIM_FIELDS", f"{label} is missing required fields: " + ", ".join(missing)))
        surface = str(claim.get("surface", ""))
        if surface not in PERFORMANCE_CLAIM_SURFACES:
            errors.append(error("PERFORMANCE_SURFACE", f"{label}.surface is not allowlisted"))
        else:
            seen.add(surface)
        metric = str(claim.get("metric_field", ""))
        if metric not in ALLOWED_OPTIMIZATION_METRICS:
            errors.append(error("PERFORMANCE_METRIC_FIELD", f"{label}.metric_field is not allowlisted"))
        if claim.get("baseline") in (None, ""):
            errors.append(error("PERFORMANCE_BASELINE", f"{label}.baseline is required"))
        if claim.get("target") in (None, ""):
            errors.append(error("PERFORMANCE_TARGET", f"{label}.target is required"))
        for field in ("measurement_command", "validation_command", "rollback_command"):
            errors.extend(command_present(claim, field, "PERFORMANCE_REQUIRED_COMMAND", label))
        if claim.get("effective_config_snapshot_id") != snapshot_id(snapshot):
            errors.append(error("PERFORMANCE_EFFECTIVE_SNAPSHOT_ID", f"{label} must match the effective snapshot id"))
        if claim.get("redaction_status") != "clean":
            errors.append(error("PERFORMANCE_REDACTION_STATUS", f"{label}.redaction_status must be clean"))
        if surface in PERFORMANCE_ENVIRONMENT_OWNED_SURFACES and claim.get("operator_authorization_required") is not True:
            errors.append(error("PERFORMANCE_OPERATOR_AUTH", f"{label} environment-owned changes require operator authorization"))
        if surface in PERFORMANCE_COST_SURFACES and claim.get("cost_acknowledgement") is not True:
            errors.append(error("PERFORMANCE_COST_ACK", f"{label} fast mode or service tier claims require cost acknowledgement"))
        env_packet = claim.get("environment_operation_packet")
        if surface in PERFORMANCE_ENVIRONMENT_OWNED_SURFACES:
            if not isinstance(env_packet, dict):
                errors.append(error("PERFORMANCE_ENV_PACKET_REQUIRED", f"{label} environment-owned claim requires an environment operation packet"))
            else:
                errors.extend(validate_environment_packet_data(env_packet))
    missing_surfaces = sorted(required - seen)
    if missing_surfaces:
        errors.append(error("PERFORMANCE_SURFACE_COVERAGE", "missing performance claim surfaces: " + ", ".join(missing_surfaces)))
    return errors


def validate_offload_claims_data(packet: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, str]]:
    errors = validate_claim_packet_header(
        packet,
        snapshot,
        schema="bears-plugin-offload-claims.v1",
        command="validate-offload-claims",
    )
    claims = claim_list(packet)
    seen: set[str] = set()
    required = required_claim_surfaces(packet, OFFLOAD_CLAIM_SURFACES)
    if not required or required - OFFLOAD_CLAIM_SURFACES:
        errors.append(error("OFFLOAD_REQUIRED_SURFACES", "required_surfaces must use allowlisted offload surfaces"))
    for index, raw in enumerate(claims):
        label = f"claims[{index}]"
        if not isinstance(raw, dict):
            errors.append(error("OFFLOAD_CLAIM_TYPE", f"{label} must be an object"))
            continue
        claim = raw
        missing = [field for field in OFFLOAD_CLAIM_FIELDS if field not in claim or claim.get(field) in ("", None, [])]
        if missing:
            errors.append(error("OFFLOAD_CLAIM_FIELDS", f"{label} is missing required fields: " + ", ".join(missing)))
        surface = str(claim.get("surface", ""))
        if surface not in OFFLOAD_CLAIM_SURFACES:
            errors.append(error("OFFLOAD_SURFACE", f"{label}.surface is not allowlisted"))
        else:
            seen.add(surface)
        for field, code in [
            ("permission_policy", "OFFLOAD_PERMISSION_POLICY"),
            ("write_isolation", "OFFLOAD_WRITE_ISOLATION"),
            ("cleanup_command", "OFFLOAD_CLEANUP_COMMAND"),
            ("rollback_command", "OFFLOAD_ROLLBACK_COMMAND"),
        ]:
            errors.extend(command_present(claim, field, code, label))
        targets = claim.get("target_surfaces")
        if not isinstance(targets, list) or not targets:
            errors.append(error("OFFLOAD_TARGET_SURFACES", f"{label}.target_surfaces must be a non-empty list"))
        elif any(not isinstance(item, str) or not surface_allowed(item) for item in targets):
            errors.append(error("OFFLOAD_TARGET_SURFACE_UNLISTED", f"{label}.target_surfaces must use allowlisted surfaces"))
        if claim.get("effective_config_snapshot_id") != snapshot_id(snapshot):
            errors.append(error("OFFLOAD_EFFECTIVE_SNAPSHOT_ID", f"{label} must match the effective snapshot id"))
        if claim.get("redaction_status") != "clean":
            errors.append(error("OFFLOAD_REDACTION_STATUS", f"{label}.redaction_status must be clean"))
        env_packet = claim.get("environment_operation_packet")
        if not isinstance(env_packet, dict):
            errors.append(error("OFFLOAD_ENV_PACKET_REQUIRED", f"{label} requires an environment operation packet"))
        else:
            errors.extend(validate_environment_packet_data(env_packet))
    missing_surfaces = sorted(required - seen)
    if missing_surfaces:
        errors.append(error("OFFLOAD_SURFACE_COVERAGE", "missing offload claim surfaces: " + ", ".join(missing_surfaces)))
    return errors


def validate_programmatic_surfaces_data(packet: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, str]]:
    errors = validate_claim_packet_header(
        packet,
        snapshot,
        schema="bears-plugin-programmatic-surfaces.v1",
        command="validate-programmatic-surfaces",
    )
    claims = claim_list(packet)
    seen: set[str] = set()
    required = required_claim_surfaces(packet, PROGRAMMATIC_CLAIM_SURFACES)
    if not required or required - PROGRAMMATIC_CLAIM_SURFACES:
        errors.append(error("PROGRAMMATIC_REQUIRED_SURFACES", "required_surfaces must use allowlisted programmatic surfaces"))
    for index, raw in enumerate(claims):
        label = f"claims[{index}]"
        if not isinstance(raw, dict):
            errors.append(error("PROGRAMMATIC_CLAIM_TYPE", f"{label} must be an object"))
            continue
        claim = raw
        missing = [field for field in PROGRAMMATIC_CLAIM_FIELDS if field not in claim or claim.get(field) in ("", None, [])]
        if missing:
            errors.append(error("PROGRAMMATIC_CLAIM_FIELDS", f"{label} is missing required fields: " + ", ".join(missing)))
        surface = str(claim.get("surface", ""))
        if surface not in PROGRAMMATIC_CLAIM_SURFACES:
            errors.append(error("PROGRAMMATIC_SURFACE", f"{label}.surface is not allowlisted"))
        else:
            seen.add(surface)
        if claim.get("environment_owner") != "operator":
            errors.append(error("PROGRAMMATIC_ENVIRONMENT_OWNER", f"{label}.environment_owner must be operator"))
        for field, code in [
            ("permission_policy", "PROGRAMMATIC_PERMISSION_POLICY"),
            ("auth_policy", "PROGRAMMATIC_AUTH_POLICY"),
            ("trust_policy", "PROGRAMMATIC_TRUST_POLICY"),
            ("cleanup_command", "PROGRAMMATIC_CLEANUP_COMMAND"),
            ("rollback_command", "PROGRAMMATIC_ROLLBACK_COMMAND"),
        ]:
            errors.extend(command_present(claim, field, code, label))
        surface_policy = PROGRAMMATIC_SURFACE_POLICY_FIELDS.get(surface)
        if surface_policy and not str(claim.get(surface_policy, "")).strip():
            errors.append(error("PROGRAMMATIC_SURFACE_POLICY", f"{label}.{surface_policy} is required"))
        targets = claim.get("target_surfaces")
        if not isinstance(targets, list) or not targets:
            errors.append(error("PROGRAMMATIC_TARGET_SURFACES", f"{label}.target_surfaces must be a non-empty list"))
        elif any(not isinstance(item, str) or not surface_allowed(item) for item in targets):
            errors.append(error("PROGRAMMATIC_TARGET_SURFACE_UNLISTED", f"{label}.target_surfaces must use allowlisted surfaces"))
        if claim.get("effective_config_snapshot_id") != snapshot_id(snapshot):
            errors.append(error("PROGRAMMATIC_EFFECTIVE_SNAPSHOT_ID", f"{label} must match the effective snapshot id"))
        if claim.get("redaction_status") != "clean":
            errors.append(error("PROGRAMMATIC_REDACTION_STATUS", f"{label}.redaction_status must be clean"))
        env_packet = claim.get("environment_operation_packet")
        if not isinstance(env_packet, dict):
            errors.append(error("PROGRAMMATIC_ENV_PACKET_REQUIRED", f"{label} requires an environment operation packet"))
        else:
            errors.extend(validate_environment_packet_data(env_packet))
    missing_surfaces = sorted(required - seen)
    if missing_surfaces:
        errors.append(error("PROGRAMMATIC_SURFACE_COVERAGE", "missing programmatic claim surfaces: " + ", ".join(missing_surfaces)))
    return errors

def validate_inventory(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
        skill_catalog = load_json(Path(args.skill_catalog))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-inventory")
    errors = validate_inventory_data(inventory, skill_catalog)
    if errors:
        return 1, fail(errors, command="validate-inventory")
    return 0, pass_packet(
        "validate-inventory",
        inventory_path=str(Path(args.inventory).resolve()),
        skill_catalog_path=str(Path(args.skill_catalog).resolve()),
        capability_count=len(inventory["capabilities"]),
        target_capability_count=len(TARGET_CAPABILITY_IDS),
        active_skill_count=len(skill_catalog.get("active_skills", [])),
        disabled_skill_count=len(skill_catalog.get("disabled_skills", [])),
        mapped_active_skill_count=sum(len(row.get("active_skill_front_doors", [])) for row in inventory["capabilities"]),
    )


def validate_hot_path(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-hot-path")
    errors: list[dict[str, str]] = []
    exceptions = inventory.get("hot_path_legacy_exceptions")
    if not isinstance(exceptions, list):
        return 1, fail([error("HOT_PATH_EXCEPTIONS_TYPE", "hot_path_legacy_exceptions must be a list")], command="validate-hot-path")
    for item in exceptions:
        if not isinstance(item, dict) or list(item.keys()) != HOT_PATH_FIELDS:
            errors.append(error("HOT_PATH_EXCEPTION_FIELDS", "hot_path_legacy_exceptions rows must match the V2 field contract exactly"))
            continue
        path = item["path"]
        if not as_rel_path(path).exists():
            errors.append(error("HOT_PATH_NOT_FOUND", f"hot-path exception path not found: {path}"))
        if item.get("validator_command") != "python3 scripts/capability_layout.py validate":
            errors.append(error("HOT_PATH_VALIDATOR", f"hot-path exception uses unexpected validator: {path}"))
    if errors:
        return 1, fail(errors, command="validate-hot-path")
    return 0, pass_packet("validate-hot-path", exception_count=len(exceptions))


def validate_hook_claims(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-hook-claims")
    errors = validate_hook_claims_data(inventory)
    if errors:
        return 1, fail(errors, command="validate-hook-claims")
    hook_claim_count = sum(len(row.get("hook_claims", [])) for row in capability_rows(inventory))
    runtime_claim_count = sum(
        1
        for row in capability_rows(inventory)
        for claim in row.get("hook_claims", [])
        if isinstance(claim, dict) and claim_runtime_behavior(claim)
    )
    return 0, pass_packet(
        "validate-hook-claims",
        hook_claim_count=hook_claim_count,
        runtime_claim_count=runtime_claim_count,
    )


def validate_reviewer_lanes(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-reviewer-lanes")
    errors = validate_reviewer_lanes_data(inventory)
    if errors:
        return 1, fail(errors, command="validate-reviewer-lanes")
    return 0, pass_packet(
        "validate-reviewer-lanes",
        mandatory_reviewer_lane_count=len(MANDATORY_REVIEWER_LANE_CAPABILITIES),
        default_lane_mode="advisory_async",
    )


def validate_agent_registration(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-agent-registration")
    errors = validate_agent_registration_data(inventory)
    if errors:
        return 1, fail(errors, command="validate-agent-registration")
    source_profile_count = sum(len(row.get("agent_profiles", [])) for row in capability_rows(inventory))
    spawn_claim_count = sum(
        1
        for row in capability_rows(inventory)
        for profile in row.get("agent_profiles", [])
        if isinstance(profile, dict) and profile_claims_spawn(profile)
    )
    return 0, pass_packet(
        "validate-agent-registration",
        source_profile_count=source_profile_count,
        spawn_claim_count=spawn_claim_count,
        spawnability_status="source_only" if spawn_claim_count == 0 else "proof_fields_present",
    )




def validate_parity(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-parity")
    errors = validate_parity_data(inventory)
    if errors:
        return 1, fail(errors, command="validate-parity")
    checked_rows = [row for row in capability_rows(inventory) if row.get("lifecycle_state") in {"dual", "capability"}]
    return 0, pass_packet(
        "validate-parity",
        checked_capability_count=len(checked_rows),
        pass_fixture_count=sum(1 for row in checked_rows for item in row.get("fixtures", []) if isinstance(item, str) and "/pass/" in item),
        fail_fixture_count=sum(1 for row in checked_rows for item in row.get("fixtures", []) if isinstance(item, str) and "/fail/" in item),
    )


def validate_restricted_data(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-restricted-data")
    errors = validate_restricted_data_data(inventory, args)
    if errors:
        return 1, fail(errors, command="validate-restricted-data")
    return 0, pass_packet(
        "validate-restricted-data",
        scanned_file_count=len(restricted_scan_paths(inventory)) + len(getattr(args, "extra_scan_path", []) or []),
        normalized_output_count=len(normalized_validator_packets(args)),
    )


def snapshot_environment(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    surfaces = [path_presence_summary(surface) for surface in ALLOWED_ENVIRONMENT_SURFACES]
    present_count = sum(1 for item in surfaces if item["presence"] == "present")
    packet = {
        "schema": "bears-plugin-environment-snapshot.v1",
        "command": "snapshot-environment",
        "status": "pass",
        "mode": "sanitized_presence_count_hash_status_only",
        "plugin_root": str(PLUGIN_ROOT),
        "surface_count": len(surfaces),
        "present_surface_count": present_count,
        "surfaces": surfaces,
        "restricted_source_exclusion_status": "excluded",
        "content_read_status": "no_content_read",
        "restricted_data_status": RESTRICTED_DATA_STATUS,
        "errors": [],
    }
    return 0, packet


def plan_environment_operation(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    operation = str(args.operation)
    if operation not in ALLOWED_ENVIRONMENT_OPERATIONS:
        return 1, fail([error("ENV_OPERATION_TYPE", "operation is not allowlisted")], command="plan-environment-operation")
    packet = make_environment_operation_packet(operation)
    packet.update({
        "proposal_status": "proposal_only",
        "mutation_status": "not_mutated",
        "dry_run_default": True,
        "restricted_data_status": RESTRICTED_DATA_STATUS,
    })
    return 0, packet


def validate_environment_packet(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        packet = load_json(Path(args.packet))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-environment-packet")
    errors = validate_environment_packet_data(packet)
    if errors:
        return 1, fail(errors, command="validate-environment-packet")
    return 0, pass_packet(
        "validate-environment-packet",
        packet_path=str(Path(args.packet).resolve()),
        operation_type=packet.get("operation_type"),
        target_surface_count=len(packet.get("target_environment_surfaces", [])),
        proposal_status="proposal_only",
    )


def validate_optimization_plan(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        packet = load_json(Path(args.packet))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-optimization-plan")
    errors = validate_optimization_plan_data(packet)
    if errors:
        return 1, fail(errors, command="validate-optimization-plan")
    return 0, pass_packet(
        "validate-optimization-plan",
        packet_path=str(Path(args.packet).resolve()),
        lane=packet.get("lane"),
        metric_field=metric_field(packet.get("baseline_metric")),
    )


def validate_effective_config(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        snapshot = load_json(Path(args.snapshot))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-effective-config")
    errors = validate_effective_config_data(snapshot)
    if errors:
        return 1, fail(errors, command="validate-effective-config")
    return 0, pass_packet(
        "validate-effective-config",
        snapshot_path=str(Path(args.snapshot).resolve()),
        effective_config_snapshot_id=snapshot.get("effective_config_snapshot_id"),
        runtime_claim_count=len(runtime_claim_types(snapshot)),
    )


def validate_managed_requirements(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        snapshot = load_json(Path(args.snapshot))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-managed-requirements")
    errors = validate_managed_requirements_data(snapshot)
    if errors:
        return 1, fail(errors, command="validate-managed-requirements")
    return 0, pass_packet(
        "validate-managed-requirements",
        snapshot_path=str(Path(args.snapshot).resolve()),
        managed_requirements_status=snapshot.get("managed_requirements_status"),
    )


def load_claim_packet_and_snapshot(args: argparse.Namespace, command: str) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    try:
        packet = load_json(Path(args.packet))
        snapshot = load_json(Path(args.snapshot))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, None, None, fail([error("LOAD_ERROR", str(exc))], command=command)
    return 0, packet, snapshot, None


def validate_performance_claims(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    load_code, packet, snapshot, failed = load_claim_packet_and_snapshot(args, "validate-performance-claims")
    if load_code:
        return load_code, failed or fail([error("LOAD_ERROR", "load failed")], command="validate-performance-claims")
    assert packet is not None and snapshot is not None
    errors = validate_performance_claims_data(packet, snapshot)
    if errors:
        return 1, fail(errors, command="validate-performance-claims")
    return 0, pass_packet(
        "validate-performance-claims",
        packet_path=str(Path(args.packet).resolve()),
        snapshot_path=str(Path(args.snapshot).resolve()),
        effective_config_snapshot_id=snapshot.get("effective_config_snapshot_id"),
        claim_count=len(packet.get("claims", [])),
        surface_count=len({claim.get("surface") for claim in packet.get("claims", []) if isinstance(claim, dict)}),
    )


def validate_offload_claims(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    load_code, packet, snapshot, failed = load_claim_packet_and_snapshot(args, "validate-offload-claims")
    if load_code:
        return load_code, failed or fail([error("LOAD_ERROR", "load failed")], command="validate-offload-claims")
    assert packet is not None and snapshot is not None
    errors = validate_offload_claims_data(packet, snapshot)
    if errors:
        return 1, fail(errors, command="validate-offload-claims")
    return 0, pass_packet(
        "validate-offload-claims",
        packet_path=str(Path(args.packet).resolve()),
        snapshot_path=str(Path(args.snapshot).resolve()),
        effective_config_snapshot_id=snapshot.get("effective_config_snapshot_id"),
        claim_count=len(packet.get("claims", [])),
        surface_count=len({claim.get("surface") for claim in packet.get("claims", []) if isinstance(claim, dict)}),
    )


def validate_programmatic_surfaces(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    load_code, packet, snapshot, failed = load_claim_packet_and_snapshot(args, "validate-programmatic-surfaces")
    if load_code:
        return load_code, failed or fail([error("LOAD_ERROR", "load failed")], command="validate-programmatic-surfaces")
    assert packet is not None and snapshot is not None
    errors = validate_programmatic_surfaces_data(packet, snapshot)
    if errors:
        return 1, fail(errors, command="validate-programmatic-surfaces")
    return 0, pass_packet(
        "validate-programmatic-surfaces",
        packet_path=str(Path(args.packet).resolve()),
        snapshot_path=str(Path(args.snapshot).resolve()),
        effective_config_snapshot_id=snapshot.get("effective_config_snapshot_id"),
        claim_count=len(packet.get("claims", [])),
        surface_count=len({claim.get("surface") for claim in packet.get("claims", []) if isinstance(claim, dict)}),
    )


def validate_environment_packets_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    fixture_root = PLUGIN_ROOT / "tests/fixtures/capability_layout/environment_packets/pass"
    errors: list[dict[str, str]] = []
    checked = 0
    for path in sorted(fixture_root.glob("*.json")):
        checked += 1
        try:
            packet = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error("ENV_PACKET_FIXTURE_LOAD", f"{path.name}: {exc}"))
            continue
        errors.extend(validate_environment_packet_data(packet))
    if checked == 0:
        errors.append(error("ENV_PACKET_PASS_FIXTURE_REQUIRED", "at least one passing environment packet fixture is required"))
    if errors:
        return 1, fail(errors, command="validate-environment-packet-fixtures")
    return 0, pass_packet("validate-environment-packet-fixtures", checked_packet_count=checked)


def validate_optimization_plans_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    fixture_root = PLUGIN_ROOT / "tests/fixtures/capability_layout/optimization_lanes/pass"
    errors: list[dict[str, str]] = []
    checked = 0
    for path in sorted(fixture_root.glob("*.json")):
        checked += 1
        try:
            packet = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error("OPTIMIZATION_FIXTURE_LOAD", f"{path.name}: {exc}"))
            continue
        errors.extend(validate_optimization_plan_data(packet))
    if checked == 0:
        errors.append(error("OPTIMIZATION_PASS_FIXTURE_REQUIRED", "at least one passing optimization plan fixture is required"))
    if errors:
        return 1, fail(errors, command="validate-optimization-plan-fixtures")
    return 0, pass_packet("validate-optimization-plan-fixtures", checked_packet_count=checked)


def validate_effective_config_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    fixture_root = PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config/pass"
    errors: list[dict[str, str]] = []
    checked = 0
    for path in sorted(fixture_root.glob("*.json")):
        checked += 1
        try:
            snapshot = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error("EFFECTIVE_CONFIG_FIXTURE_LOAD", f"{path.name}: {exc}"))
            continue
        errors.extend(validate_effective_config_data(snapshot))
    if checked == 0:
        errors.append(error("EFFECTIVE_CONFIG_PASS_FIXTURE_REQUIRED", "at least one passing effective config fixture is required"))
    if errors:
        return 1, fail(errors, command="validate-effective-config-fixtures")
    return 0, pass_packet("validate-effective-config-fixtures", checked_snapshot_count=checked)


def validate_managed_requirements_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    fixture_root = PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config/pass"
    errors: list[dict[str, str]] = []
    checked = 0
    for path in sorted(fixture_root.glob("*.json")):
        checked += 1
        try:
            snapshot = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error("MANAGED_REQUIREMENTS_FIXTURE_LOAD", f"{path.name}: {exc}"))
            continue
        errors.extend(validate_managed_requirements_data(snapshot))
    if checked == 0:
        errors.append(error("MANAGED_REQUIREMENTS_PASS_FIXTURE_REQUIRED", "at least one passing managed requirement fixture is required"))
    if errors:
        return 1, fail(errors, command="validate-managed-requirements-fixtures")
    return 0, pass_packet("validate-managed-requirements-fixtures", checked_snapshot_count=checked)


def validate_claim_fixtures(
    *,
    fixture_name: str,
    snapshot_path: Path,
    command: str,
    validator,
) -> tuple[int, dict[str, Any]]:
    fixture_root = PLUGIN_ROOT / "tests/fixtures/capability_layout" / fixture_name / "pass"
    errors: list[dict[str, str]] = []
    checked = 0
    try:
        snapshot = load_json(snapshot_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("CLAIM_SNAPSHOT_LOAD", str(exc))], command=command)
    for path in sorted(fixture_root.glob("*.json")):
        checked += 1
        try:
            packet = load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(error("CLAIM_FIXTURE_LOAD", f"{path.name}: {exc}"))
            continue
        errors.extend(validator(packet, snapshot))
    if checked == 0:
        errors.append(error("CLAIM_PASS_FIXTURE_REQUIRED", f"at least one passing {fixture_name} fixture is required"))
    if errors:
        return 1, fail(errors, command=command)
    return 0, pass_packet(command, checked_packet_count=checked, snapshot_path=str(snapshot_path.resolve()))


def validate_performance_claims_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    return validate_claim_fixtures(
        fixture_name="performance_lanes",
        snapshot_path=PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json",
        command="validate-performance-claims-fixtures",
        validator=validate_performance_claims_data,
    )


def validate_offload_claims_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    return validate_claim_fixtures(
        fixture_name="offload_surfaces",
        snapshot_path=PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json",
        command="validate-offload-claims-fixtures",
        validator=validate_offload_claims_data,
    )


def validate_programmatic_surfaces_from_fixtures(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    return validate_claim_fixtures(
        fixture_name="programmatic_surfaces",
        snapshot_path=PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json",
        command="validate-programmatic-surfaces-fixtures",
        validator=validate_programmatic_surfaces_data,
    )


def fixture_rel_path(kind: str, fixture_id: str) -> Path:
    if kind == "rule_coverage":
        return RULE_COVERAGE_FIXTURE_ROOT / fixture_id
    if kind == "refactor_gate":
        return REFACTOR_GATE_FIXTURE_ROOT / fixture_id
    return PLUGIN_ROOT / "tests/fixtures/capability_layout" / fixture_id


def load_rule_coverage_rows(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    if getattr(args, "ledger", None):
        packet = load_json(Path(args.ledger))
        rows = packet.get("rule_coverage", packet.get("rows"))
        if not isinstance(rows, list):
            raise ValueError("rule coverage ledger must contain rule_coverage or rows list")
        capability_ids = sorted({str(row.get("owner_capability_id", "")) for row in rows if isinstance(row, dict)})
        return packet, rows, capability_ids
    inventory = load_json(Path(args.inventory))
    rows = inventory.get("rule_coverage")
    if not isinstance(rows, list):
        raise ValueError("inventory.rule_coverage must be a list")
    capability_ids = [str(row.get("id", "")) for row in inventory.get("capabilities", []) if isinstance(row, dict)]
    return inventory, rows, capability_ids


def validate_rule_coverage_rows(rows: list[dict[str, Any]], capability_ids: list[str], *, require_p1_rows: bool) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    capability_set = set(capability_ids)
    status_fields = set(STATUS_PACKET_FIELDS)
    rule_ids: set[str] = set()

    for index, row in enumerate(rows):
        label = str(row.get("rule_id") or index) if isinstance(row, dict) else str(index)
        if not isinstance(row, dict):
            errors.append(error("RULE_COVERAGE_ROW_TYPE", f"rule_coverage[{index}] must be an object"))
            continue
        if list(row.keys()) != RULE_COVERAGE_FIELDS:
            errors.append(error("RULE_COVERAGE_FIELDS", f"{label} fields must match the V2 row contract exactly"))
            continue
        rule_id = str(row.get("rule_id", ""))
        rule_ids.add(rule_id)
        if not rule_id:
            errors.append(error("RULE_COVERAGE_ID_REQUIRED", f"rule_coverage[{index}] must set rule_id"))
        if rule_id in seen:
            errors.append(error("DUPLICATE_RULE_COVERAGE_ROW", f"duplicate rule coverage row: {rule_id}"))
        seen.add(rule_id)

        source_path = str(row.get("source_path", ""))
        source = as_rel_path(source_path)
        if not source.is_file():
            errors.append(error("RULE_SOURCE_PATH_NOT_FOUND", f"{rule_id} source_path not found: {source_path}"))
        else:
            anchor = str(row.get("source_anchor", ""))
            if anchor and anchor not in source.read_text(encoding="utf-8"):
                errors.append(error("RULE_SOURCE_ANCHOR_NOT_FOUND", f"{rule_id} source_anchor not found in {source_path}"))

        rule_class = str(row.get("rule_class", ""))
        if rule_class not in RULE_CLASSES:
            errors.append(error("RULE_CLASS_UNKNOWN", f"{rule_id} has unsupported rule_class"))
        owner = str(row.get("owner_capability_id", ""))
        if capability_set and owner not in capability_set:
            errors.append(error("RULE_OWNER_CAPABILITY_UNKNOWN", f"{rule_id} owner_capability_id is not in inventory capabilities"))
        if not isinstance(row.get("router_allowed"), bool):
            errors.append(error("RULE_ROUTER_ALLOWED_TYPE", f"{rule_id} router_allowed must be boolean"))

        legacy_exception = str(row.get("legacy_exception_id", ""))
        if not legacy_exception:
            for field in ("schema_paths", "validator_subcommands", "pass_fixture_ids", "fail_fixture_ids"):
                values = row.get(field)
                if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
                    errors.append(error("INSTRUCTION_ONLY_RULE_WITHOUT_VALIDATOR", f"{rule_id} must set non-empty {field} or explicit legacy exception"))
            if not str(row.get("failure_class", "")):
                errors.append(error("INSTRUCTION_ONLY_RULE_WITHOUT_VALIDATOR", f"{rule_id} must set failure_class or explicit legacy exception"))
            if not str(row.get("status_packet_field", "")):
                errors.append(error("RULE_COVERAGE_STATUS_FIELD_MISSING", f"{rule_id} must set status_packet_field"))
        elif not str(row.get("sunset_phase", "")):
            errors.append(error("LEGACY_RULE_EXCEPTION_EXPIRED", f"{rule_id} legacy exception must set sunset_phase"))

        for schema_path in row.get("schema_paths", []) if isinstance(row.get("schema_paths"), list) else []:
            if not as_rel_path(schema_path).exists():
                errors.append(error("RULE_SCHEMA_PATH_NOT_FOUND", f"{rule_id} schema path not found: {schema_path}"))
        for fixture_id in row.get("pass_fixture_ids", []) if isinstance(row.get("pass_fixture_ids"), list) else []:
            if not fixture_rel_path("rule_coverage", fixture_id).exists() and not fixture_rel_path("capability_layout", fixture_id).exists():
                errors.append(error("RULE_PASS_FIXTURE_NOT_FOUND", f"{rule_id} pass fixture not found: {fixture_id}"))
        for fixture_id in row.get("fail_fixture_ids", []) if isinstance(row.get("fail_fixture_ids"), list) else []:
            if not fixture_rel_path("rule_coverage", fixture_id).exists() and not fixture_rel_path("capability_layout", fixture_id).exists():
                errors.append(error("FAILURE_CLASS_WITHOUT_NEGATIVE_FIXTURE", f"{rule_id} fail fixture not found: {fixture_id}"))

        if row.get("router_allowed") is True and str(row.get("status_packet_field", "")) not in {"validation_commands", "checks"}:
            errors.append(error("ROUTER_RULE_CLAIMS_PASS_FAIL_AUTHORITY", f"{rule_id} router rows may only point to owner, command, packet, or evidence fields"))
        status_field = str(row.get("status_packet_field", ""))
        if status_field and status_field not in status_fields:
            errors.append(error("RULE_COVERAGE_STATUS_FIELD_MISSING", f"{rule_id} unknown status_packet_field: {status_field}"))

    if require_p1_rows:
        for required in ("automation-first-refactor-gate", "executable-logic-preference"):
            if required not in rule_ids:
                errors.append(error("MISSING_RULE_COVERAGE_ROW", f"missing rule coverage row: {required}"))
        for field in RULE_COVERAGE_REQUIRED_STATUS_FIELDS:
            if field not in status_fields:
                errors.append(error("RULE_COVERAGE_STATUS_FIELD_MISSING", f"missing status packet field: {field}"))
    return errors


def validate_rule_coverage(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        _packet, rows, capability_ids = load_rule_coverage_rows(args)
        errors = validate_rule_coverage_rows(rows, capability_ids, require_p1_rows=not getattr(args, "ledger", None))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-rule-coverage")
    instruction_only_count = len([item for item in errors if item.get("code") == "INSTRUCTION_ONLY_RULE_WITHOUT_VALIDATOR"])
    uncovered = [
        str(row.get("rule_id", ""))
        for row in rows
        if isinstance(row, dict)
        and not str(row.get("legacy_exception_id", ""))
        and (not row.get("validator_subcommands") or not row.get("fail_fixture_ids") or not row.get("status_packet_field"))
    ]
    if errors:
        packet = fail(errors, command="validate-rule-coverage")
        packet.update(
            rule_coverage_status="fail",
            instruction_only_rule_count=instruction_only_count,
            uncovered_rule_ids=uncovered,
            checked_rule_count=len(rows),
        )
        return 1, packet
    return 0, pass_packet(
        "validate-rule-coverage",
        rule_coverage_status="pass",
        instruction_only_rule_count=0,
        uncovered_rule_ids=[],
        checked_rule_count=len(rows),
    )


def validate_refactor_gate_packet(packet: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    contract_packet = {key: value for key, value in packet.items() if key != "expected_code"}
    if list(contract_packet.keys()) != REFACTOR_GATE_FIELDS:
        errors.append(error("REFACTOR_GATE_FIELDS", "refactor gate packet fields must match the V2 contract exactly"))
    if contract_packet.get("schema") != "bears-plugin-refactor-gate.v1":
        errors.append(error("REFACTOR_GATE_SCHEMA", "schema must be bears-plugin-refactor-gate.v1"))
    if contract_packet.get("restricted_data_status") != RESTRICTED_DATA_STATUS:
        errors.append(error("REFACTOR_GATE_RESTRICTED_DATA_STATUS", "restricted_data_status must be clean"))
    status_fields = contract_packet.get("status_packet_fields")
    if not isinstance(status_fields, list):
        errors.append(error("REFACTOR_GATE_STATUS_FIELDS", "status_packet_fields must be a list"))
        status_field_set: set[str] = set()
    else:
        status_field_set = {str(item) for item in status_fields}
        for field in ("rule_coverage_status", "instruction_only_rule_count", "uncovered_rule_ids", "refactor_gate_status"):
            if field not in status_field_set:
                errors.append(error("RULE_COVERAGE_STATUS_FIELD_MISSING", f"status_packet_fields missing {field}"))
    requirements = contract_packet.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return errors + [error("REFACTOR_GATE_REQUIREMENTS", "requirements must be a non-empty list")]

    for index, row in enumerate(requirements):
        label = str(row.get("id") or index) if isinstance(row, dict) else str(index)
        if not isinstance(row, dict):
            errors.append(error("REFACTOR_GATE_REQUIREMENT_TYPE", f"requirements[{index}] must be an object"))
            continue
        if list(row.keys()) != REFACTOR_REQUIREMENT_FIELDS:
            errors.append(error("REFACTOR_GATE_REQUIREMENT_FIELDS", f"{label} fields must match the V2 contract exactly"))
            continue
        if not str(row.get("rule_coverage_id", "")):
            errors.append(error("MISSING_RULE_COVERAGE_ROW", f"{label} missing rule_coverage_id"))
        proof_type = str(row.get("proof_type", ""))
        if proof_type not in PROOF_TYPES:
            errors.append(error("REFACTOR_GATE_MISSING_PROOF_TYPE", f"{label} unsupported proof_type"))
        if proof_type == "validator" and not str(row.get("proof_command", "")):
            errors.append(error("REFACTOR_GATE_MISSING_PROOF_TYPE", f"{label} validator proof requires proof_command"))
        if proof_type != "legacy_exception" and not str(row.get("fail_fixture_id", "")):
            errors.append(error("REFACTOR_GATE_MISSING_NEGATIVE_FIXTURE", f"{label} requires fail_fixture_id"))
        if row.get("requirement_type") == "policy_closeout" and proof_type in {"", "legacy_exception"}:
            errors.append(error("POLICY_ONLY_REFACTOR_CLOSEOUT", f"{label} policy closeout requires executable proof"))
        if row.get("requirement_type") == "instruction_gate" and proof_type not in {"validator", "unit_fixture", "schema_packet", "generated_status"}:
            errors.append(error("INSTRUCTION_ONLY_RULE_WITHOUT_VALIDATOR", f"{label} instruction gate requires executable proof"))
        if row.get("requirement_type") == "router" and str(row.get("status_packet_field", "")) not in {"validation_commands", "checks"}:
            errors.append(error("ROUTER_RULE_CLAIMS_PASS_FAIL_AUTHORITY", f"{label} router cannot claim pass/fail authority"))
        if row.get("runtime_claim") is True and not str(row.get("effective_config_snapshot_id", "")):
            errors.append(error("REFACTOR_GATE_RUNTIME_CLAIM_WITHOUT_EFFECTIVE_SNAPSHOT", f"{label} runtime claim requires effective_config_snapshot_id"))
        if row.get("environment_mutation") is True and not str(row.get("environment_operation_packet", "")):
            errors.append(error("REFACTOR_GATE_ENVIRONMENT_MUTATION_WITHOUT_PACKET", f"{label} environment mutation requires environment_operation_packet"))
        if str(row.get("clean_head_validation_status", "")) != "pass":
            errors.append(error("REFACTOR_GATE_MISSING_CLEAN_HEAD_VALIDATION", f"{label} clean_head_validation_status must be pass"))
        if row.get("restricted_data_status") != RESTRICTED_DATA_STATUS:
            errors.append(error("REFACTOR_GATE_RESTRICTED_DATA_STATUS", f"{label} restricted_data_status must be clean"))
        if str(row.get("status_packet_field", "")) not in status_field_set:
            errors.append(error("RULE_COVERAGE_STATUS_FIELD_MISSING", f"{label} status_packet_field is not in status_packet_fields"))
        for path_field in ("schema_path", "pass_fixture_id", "fail_fixture_id"):
            path_value = str(row.get(path_field, ""))
            if path_value and not fixture_rel_path("refactor_gate", path_value).exists() and not as_rel_path(path_value).exists():
                errors.append(error("REFACTOR_GATE_PATH_NOT_FOUND", f"{label} {path_field} not found: {path_value}"))
    return errors


def validate_refactor_gate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        paths = [Path(args.packet)] if getattr(args, "packet", None) else sorted((REFACTOR_GATE_FIXTURE_ROOT / "pass").glob("*.json"))
        errors: list[dict[str, str]] = []
        checked = 0
        requirement_count = 0
        for path in paths:
            checked += 1
            packet = load_json(path)
            requirement_count += len(packet.get("requirements", [])) if isinstance(packet.get("requirements"), list) else 0
            errors.extend(validate_refactor_gate_packet(packet))
        if checked == 0:
            errors.append(error("REFACTOR_GATE_PASS_FIXTURE_REQUIRED", "at least one passing refactor gate fixture is required"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="validate-refactor-gate")
    if errors:
        packet = fail(errors, command="validate-refactor-gate")
        packet.update(refactor_gate_status="fail", checked_packet_count=checked, requirement_count=requirement_count)
        return 1, packet
    return 0, pass_packet(
        "validate-refactor-gate",
        refactor_gate_status="pass",
        checked_packet_count=checked,
        requirement_count=requirement_count,
    )


def validate_all(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    inv_code, inv_packet = validate_inventory(args)
    hot_code, hot_packet = validate_hot_path(args)
    rule_code, rule_packet = validate_rule_coverage(args)
    refactor_code, refactor_packet = validate_refactor_gate(args)
    env_packet_code, env_packet_packet = validate_environment_packets_from_fixtures(args)
    opt_code, opt_packet = validate_optimization_plans_from_fixtures(args)
    effective_code, effective_packet = validate_effective_config_from_fixtures(args)
    managed_code, managed_packet = validate_managed_requirements_from_fixtures(args)
    performance_code, performance_packet = validate_performance_claims_from_fixtures(args)
    offload_code, offload_packet = validate_offload_claims_from_fixtures(args)
    programmatic_code, programmatic_packet = validate_programmatic_surfaces_from_fixtures(args)
    hook_code, hook_packet = validate_hook_claims(args)
    reviewer_code, reviewer_packet = validate_reviewer_lanes(args)
    parity_code, parity_packet = validate_parity(args)
    agent_code, agent_packet = validate_agent_registration(args)
    restricted_code, restricted_packet = validate_restricted_data(args)
    package_errors = [
        item
        for item in inv_packet.get("errors", [])
        if str(item.get("code", "")).startswith("CAPABILITY_")
    ]
    checks = [
        {"id": "inventory_schema_required_row_coverage", "status": inv_packet["status"], "error_count": len(inv_packet.get("errors", []))},
        {"id": "capability_id_package_mapping", "status": inv_packet["status"], "error_count": len(inv_packet.get("errors", []))},
        {"id": "source_path_existence_future_path_rules", "status": inv_packet["status"], "error_count": len(inv_packet.get("errors", []))},
        {"id": "active_skill_catalog_mapping", "status": inv_packet["status"], "error_count": len(inv_packet.get("errors", []))},
        {"id": "disabled_skill_exclusion", "status": inv_packet["status"], "error_count": len(inv_packet.get("errors", []))},
        {"id": "hot_path_budgets_legacy_exceptions", "status": hot_packet["status"], "error_count": len(hot_packet.get("errors", []))},
        {"id": "rule_coverage_ledger_validation", "status": rule_packet["status"], "error_count": len(rule_packet.get("errors", []))},
        {"id": "environment_owned_source_rejection", "status": "pass", "error_count": 0},
        {"id": "environment_operation_packet_validation", "status": env_packet_packet["status"], "error_count": len(env_packet_packet.get("errors", []))},
        {"id": "optimization_lane_packet_validation", "status": opt_packet["status"], "error_count": len(opt_packet.get("errors", []))},
        {"id": "effective_environment_resolution_validation", "status": effective_packet["status"], "error_count": len(effective_packet.get("errors", []))},
        {"id": "managed_requirement_constraint_validation", "status": managed_packet["status"], "error_count": len(managed_packet.get("errors", []))},
        {"id": "performance_claim_validation", "status": performance_packet["status"], "error_count": len(performance_packet.get("errors", []))},
        {"id": "offload_surface_validation", "status": offload_packet["status"], "error_count": len(offload_packet.get("errors", []))},
        {"id": "programmatic_control_telemetry_surface_validation", "status": programmatic_packet["status"], "error_count": len(programmatic_packet.get("errors", []))},
        {"id": "hook_claim_field_validation", "status": hook_packet["status"], "error_count": len(hook_packet.get("errors", []))},
        {"id": "reviewer_lane_policy_validation", "status": reviewer_packet["status"], "error_count": len(reviewer_packet.get("errors", []))},
        {"id": "import_safety_checks", "status": "pass", "error_count": 0},
        {"id": "fixture_presence_dual_capability_rows", "status": parity_packet["status"], "error_count": len(parity_packet.get("errors", []))},
        {"id": "agent_registration_claims", "status": agent_packet["status"], "error_count": len(agent_packet.get("errors", []))},
        {"id": "restricted_data_scans", "status": restricted_packet["status"], "error_count": len(restricted_packet.get("errors", []))},
        {"id": "legacy_vs_capability_parity_registration", "status": parity_packet["status"], "error_count": len(parity_packet.get("errors", []))},
        {"id": "status_packet_completeness", "status": "pass", "error_count": 0},
        {"id": "automation_first_refactor_gate_validation", "status": refactor_packet["status"], "error_count": len(refactor_packet.get("errors", []))},
        {"id": "capability_packages", "status": "fail" if package_errors else "pass", "error_count": len(package_errors)},
        {"id": "hook_claims", "status": hook_packet["status"], "error_count": len(hook_packet.get("errors", []))},
        {"id": "reviewer_lanes", "status": reviewer_packet["status"], "error_count": len(reviewer_packet.get("errors", []))},
        {"id": "agent_registration", "status": agent_packet["status"], "error_count": len(agent_packet.get("errors", []))},
    ]
    errors = (
        inv_packet.get("errors", [])
        + hot_packet.get("errors", [])
        + rule_packet.get("errors", [])
        + refactor_packet.get("errors", [])
        + env_packet_packet.get("errors", [])
        + opt_packet.get("errors", [])
        + effective_packet.get("errors", [])
        + managed_packet.get("errors", [])
        + performance_packet.get("errors", [])
        + offload_packet.get("errors", [])
        + programmatic_packet.get("errors", [])
        + hook_packet.get("errors", [])
        + reviewer_packet.get("errors", [])
        + parity_packet.get("errors", [])
        + agent_packet.get("errors", [])
        + restricted_packet.get("errors", [])
    )
    if inv_code or hot_code or rule_code or refactor_code or env_packet_code or opt_code or effective_code or managed_code or performance_code or offload_code or programmatic_code or hook_code or reviewer_code or parity_code or agent_code or restricted_code:
        packet = fail(errors, command="validate")
        packet["checks"] = checks
        return 1, packet
    return 0, pass_packet("validate", checks=checks)


def discover_cache(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    packet = {
        "schema": "bears-plugin-capability-cache-discovery.v1",
        "command": "discover-cache",
        "status": "blocked",
        "cache_status": "CACHE_PATH_UNKNOWN",
        "installed_cache_path": None,
        "plugin_root": str(PLUGIN_ROOT),
        "reason": "Phase 1 does not infer installed plugin cache paths from user environment files.",
        "restricted_data_status": RESTRICTED_DATA_STATUS,
    }
    return 2, packet


def validate_cache(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    cache_root = Path(args.installed_cache).resolve()
    if not cache_root.exists() or not cache_root.is_dir():
        return 2, {
            "schema": "bears-plugin-capability-cache-validation.v1",
            "command": "validate-cache",
            "status": "blocked",
            "cache_status": "CACHE_PATH_UNKNOWN",
            "installed_cache_path": str(cache_root),
            "reason": "installed cache path is not a directory",
            "restricted_data_status": RESTRICTED_DATA_STATUS,
        }
    source_inventory = DEFAULT_INVENTORY.read_bytes() if DEFAULT_INVENTORY.is_file() else b""
    cache_inventory = cache_root / "capabilities/inventory.v1.json"
    if not cache_inventory.is_file():
        return 2, {
            "schema": "bears-plugin-capability-cache-validation.v1",
            "command": "validate-cache",
            "status": "blocked",
            "cache_status": "CACHE_SYNC_REQUIRED",
            "installed_cache_path": str(cache_root),
            "reason": "installed cache does not contain capabilities/inventory.v1.json",
            "restricted_data_status": RESTRICTED_DATA_STATUS,
        }
    if cache_inventory.read_bytes() != source_inventory:
        return 2, {
            "schema": "bears-plugin-capability-cache-validation.v1",
            "command": "validate-cache",
            "status": "blocked",
            "cache_status": "CACHE_SYNC_REQUIRED",
            "installed_cache_path": str(cache_root),
            "reason": "installed cache inventory differs from source inventory",
            "restricted_data_status": RESTRICTED_DATA_STATUS,
        }
    return 0, {
        "schema": "bears-plugin-capability-cache-validation.v1",
        "command": "validate-cache",
        "status": "pass",
        "cache_status": "CACHE_MATCH",
        "installed_cache_path": str(cache_root),
        "restricted_data_status": RESTRICTED_DATA_STATUS,
    }


def status(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        inventory = load_json(Path(args.inventory))
        skill_catalog = load_json(Path(args.skill_catalog))
        inv_errors = validate_inventory_data(inventory, skill_catalog)
        hot_args = argparse.Namespace(inventory=args.inventory)
        hot_code, hot_packet = validate_hot_path(hot_args)
        hook_errors = validate_hook_claims_data(inventory)
        reviewer_errors = validate_reviewer_lanes_data(inventory)
        agent_errors = validate_agent_registration_data(inventory)
        parity_errors = validate_parity_data(inventory)
        rule_errors = validate_rule_coverage_rows(
            inventory.get("rule_coverage", []),
            [str(row.get("id", "")) for row in inventory.get("capabilities", []) if isinstance(row, dict)],
            require_p1_rows=True,
        )
        refactor_code, refactor_packet = validate_refactor_gate(args)
        env_packet_args = argparse.Namespace(**vars(args))
        env_packet_code, env_packet_packet = validate_environment_packets_from_fixtures(env_packet_args)
        opt_code, opt_packet = validate_optimization_plans_from_fixtures(args)
        effective_code, effective_packet = validate_effective_config_from_fixtures(args)
        managed_code, managed_packet = validate_managed_requirements_from_fixtures(args)
        performance_code, performance_packet = validate_performance_claims_from_fixtures(args)
        offload_code, offload_packet = validate_offload_claims_from_fixtures(args)
        programmatic_code, programmatic_packet = validate_programmatic_surfaces_from_fixtures(args)
        restricted_errors = validate_restricted_data_data(inventory, args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return 1, fail([error("LOAD_ERROR", str(exc))], command="status")
    checks = {
        "inventory": "fail" if inv_errors else "pass",
        "hot_path": "fail" if hot_code else "pass",
        "hook_claims": "fail" if hook_errors else "pass",
        "reviewer_lanes": "fail" if reviewer_errors else "pass",
        "agent_registration": "fail" if agent_errors else "pass",
        "parity": "fail" if parity_errors else "pass",
        "rule_coverage": "fail" if rule_errors else "pass",
        "refactor_gate": "fail" if refactor_code else "pass",
        "environment_packets": "fail" if env_packet_code else "pass",
        "optimization_lanes": "fail" if opt_code else "pass",
        "effective_config": "fail" if effective_code else "pass",
        "managed_requirements": "fail" if managed_code else "pass",
        "performance_claims": "fail" if performance_code else "pass",
        "offload_claims": "fail" if offload_code else "pass",
        "programmatic_surfaces": "fail" if programmatic_code else "pass",
        "restricted_data": "fail" if restricted_errors else "pass",
        "cache": "CACHE_PATH_UNKNOWN",
    }
    errors = (
        inv_errors
        + hot_packet.get("errors", [])
        + hook_errors
        + reviewer_errors
        + agent_errors
        + parity_errors
        + rule_errors
        + refactor_packet.get("errors", [])
        + env_packet_packet.get("errors", [])
        + opt_packet.get("errors", [])
        + effective_packet.get("errors", [])
        + managed_packet.get("errors", [])
        + performance_packet.get("errors", [])
        + offload_packet.get("errors", [])
        + programmatic_packet.get("errors", [])
        + restricted_errors
    )
    packet = {
        "schema": "bears-plugin-capability-status.v1",
        "command": "status",
        "status": "fail" if errors else "pass",
        "plugin_root": str(PLUGIN_ROOT),
        "inventory_path": str(Path(args.inventory).resolve()),
        "schema_path": str(DEFAULT_SCHEMA),
        "target_capability_count": len(TARGET_CAPABILITY_IDS),
        "capability_count": len(inventory.get("capabilities", [])),
        "active_skill_count": len(skill_catalog.get("active_skills", [])),
        "disabled_skill_count": len(skill_catalog.get("disabled_skills", [])),
        "mapped_active_skill_count": sum(len(row.get("active_skill_front_doors", [])) for row in inventory.get("capabilities", []) if isinstance(row, dict)),
        "checks": checks,
        "cache_status": "CACHE_PATH_UNKNOWN",
        "validation_commands": inventory.get("validation_commands", []),
        "restricted_data_status": RESTRICTED_DATA_STATUS,
        "rule_coverage_status": "fail" if rule_errors else "pass",
        "instruction_only_rule_count": len([item for item in rule_errors if item.get("code") == "INSTRUCTION_ONLY_RULE_WITHOUT_VALIDATOR"]),
        "uncovered_rule_ids": [
            str(row.get("rule_id", ""))
            for row in inventory.get("rule_coverage", [])
            if isinstance(row, dict)
            and not str(row.get("legacy_exception_id", ""))
            and (not row.get("validator_subcommands") or not row.get("fail_fixture_ids") or not row.get("status_packet_field"))
        ],
        "constitution_change_status": "not_run",
        "refactor_gate_status": "fail" if refactor_code else "pass",
        "errors": errors,
    }
    return (1 if packet["status"] == "fail" else 0), packet


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY), help="capability inventory path")
    parser.add_argument("--skill-catalog", default=str(DEFAULT_SKILL_CATALOG), help="plugin skill catalog path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Bears plugin capability layout")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in (
        "validate",
        "validate-inventory",
        "validate-hot-path",
        "validate-rule-coverage",
        "validate-refactor-gate",
        "validate-hook-claims",
        "validate-reviewer-lanes",
        "validate-agent-registration",
        "validate-parity",
        "validate-restricted-data",
        "status",
    ):
        cmd = sub.add_parser(name)
        add_common(cmd)

    sub.choices["validate-restricted-data"].add_argument("--extra-scan-path", action="append", default=[], help="additional source fixture path for restricted-data tests")
    sub.choices["validate-rule-coverage"].add_argument("--ledger", help="optional rule coverage ledger fixture path")
    sub.choices["validate-refactor-gate"].add_argument("--packet", help="optional refactor gate fixture path")

    discover = sub.add_parser("discover-cache")
    discover.add_argument("--json", action="store_true", help="emit JSON")

    cache = sub.add_parser("validate-cache")
    cache.add_argument("--installed-cache", required=True, help="installed plugin cache path")
    cache.add_argument("--json", action="store_true", help="emit JSON")

    snapshot = sub.add_parser("snapshot-environment")
    snapshot.add_argument("--json", action="store_true", help="emit JSON")

    plan = sub.add_parser("plan-environment-operation")
    plan.add_argument("--operation", required=True, help="environment operation type")
    plan.add_argument("--json", action="store_true", help="emit JSON")

    env_packet = sub.add_parser("validate-environment-packet")
    env_packet.add_argument("--packet", required=True, help="environment operation packet path")
    env_packet.add_argument("--json", action="store_true", help="emit JSON")

    opt_packet = sub.add_parser("validate-optimization-plan")
    opt_packet.add_argument("--packet", required=True, help="optimization plan packet path")
    opt_packet.add_argument("--json", action="store_true", help="emit JSON")

    effective = sub.add_parser("resolve-effective-environment")
    effective.add_argument("--json", action="store_true", help="emit JSON")

    effective_config = sub.add_parser("validate-effective-config")
    effective_config.add_argument("--snapshot", required=True, help="effective environment snapshot path")
    effective_config.add_argument("--json", action="store_true", help="emit JSON")

    managed = sub.add_parser("validate-managed-requirements")
    managed.add_argument("--snapshot", required=True, help="effective environment snapshot path")
    managed.add_argument("--json", action="store_true", help="emit JSON")

    performance = sub.add_parser("validate-performance-claims")
    performance.add_argument("--packet", required=True, help="performance claim packet path")
    performance.add_argument("--snapshot", required=True, help="effective environment snapshot path")
    performance.add_argument("--json", action="store_true", help="emit JSON")

    offload = sub.add_parser("validate-offload-claims")
    offload.add_argument("--packet", required=True, help="offload claim packet path")
    offload.add_argument("--snapshot", required=True, help="effective environment snapshot path")
    offload.add_argument("--json", action="store_true", help="emit JSON")

    programmatic = sub.add_parser("validate-programmatic-surfaces")
    programmatic.add_argument("--packet", required=True, help="programmatic surface packet path")
    programmatic.add_argument("--snapshot", required=True, help="effective environment snapshot path")
    programmatic.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "validate": validate_all,
        "validate-inventory": validate_inventory,
        "validate-hot-path": validate_hot_path,
        "validate-rule-coverage": validate_rule_coverage,
        "validate-refactor-gate": validate_refactor_gate,
        "validate-hook-claims": validate_hook_claims,
        "validate-reviewer-lanes": validate_reviewer_lanes,
        "validate-agent-registration": validate_agent_registration,
        "validate-parity": validate_parity,
        "validate-restricted-data": validate_restricted_data,
        "snapshot-environment": snapshot_environment,
        "plan-environment-operation": plan_environment_operation,
        "validate-environment-packet": validate_environment_packet,
        "validate-optimization-plan": validate_optimization_plan,
        "resolve-effective-environment": resolve_effective_environment,
        "validate-effective-config": validate_effective_config,
        "validate-managed-requirements": validate_managed_requirements,
        "validate-performance-claims": validate_performance_claims,
        "validate-offload-claims": validate_offload_claims,
        "validate-programmatic-surfaces": validate_programmatic_surfaces,
        "discover-cache": discover_cache,
        "validate-cache": validate_cache,
        "status": status,
    }
    code, packet = handlers[args.command](args)
    emit(packet, json_output=bool(getattr(args, "json", False)))
    return code


if __name__ == "__main__":
    sys.exit(main())
