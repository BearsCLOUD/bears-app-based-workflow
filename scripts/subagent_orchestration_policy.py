#!/usr/bin/env python3
"""Validate Bears subagent orchestration policy and relevant Codex config knobs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import posixpath
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = PLUGIN_ROOT / "assets/catalog/subagent-orchestration-policy.v1.json"
DEFAULT_CODEX_CONFIG = Path("/home/ai1/.codex/config.toml")
EXPECTED_SCHEMA = "bears-subagent-orchestration-policy.v1"
PARALLELIZATION_PLAN_SCHEMA = "bears-goal-parallelization-plan.v1"
PARALLELIZATION_REPO_BOUNDARY = "BearsCLOUD/bears_plugin"
EXPECTED_OWNER = "bears"
REQUIRED_RULE_IDS = {
    "role-gate-first",
    "spec-kit-packet-before-broad-work",
    "parent-orchestrates",
    "pre-task-hook-before-task-start",
    "roadmap-through-goal-only",
    "parallel-tasks-use-parallel-subagents",
    "nested-subagents-allowed-with-bounds",
    "max-100-active-subagents",
    "reusable-worker-pool-policy",
    "max-depth-3",
    "workspace-map-disabled",
    "secret-safe-delegation",
    "close-unused-subagents",
    "readiness-gates-before-runtime",
    "constitution-gate-before-research",
    "plugin-fit-stage-boundary-audit",
    "new-functionality-drift-stage-boundary-audit",
    "documentation-secret-safety-stage-boundary-audit",
    "user-information-capture-stage-boundary-audit",
    "audit-subagents-fresh-no-parent-context",
    "project-mandate-owned-by-bears",
    "main-agent-orchestration-only",
    "parent-control-lane-actions",
    "no-subagent-mode-decision-table",
    "read-only-agent-safety-guard",
    "pr-task-role-action-guard",
    "governed-validation-hook-runner",
    "child-reasoning-floor-medium",
    "explicit-nested-orchestrator-roles",
    "multi-orchestrator-controller-only-spawn",
    "stage-boundary-audits-only",
    "parallel-audit-lane-non-blocking",
    "parallel-gitflow-closeout-lane",
    "goal-parallelization-preflight",
    "completed-subagent-close-evidence-before-new-waves",
    "parent-plan-status-evidence-gate",
    "nested-worker-delegation-parent-authorization",
    "cache-sync-with-plugin-metadata",
    "transitional-tests-superseded-by-dev-core",
    "role-profile-fallback-parity-guard",
    "current-day-checkpoint-collector-guard",
    "current-state-source-authority-guard",
}
EXPECTED_AGENT_RUNTIME_POLICY = {
    "main_agent": {"model": "gpt-5.5", "reasoning_effort": "medium"},
    "delegated_subagents": {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "medium",
        "applies_to": {
            "audit agents",
            "complex-task agents",
            "agents that can spawn subagents",
        },
    },
    "evidence_gathering_agents": {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "medium",
        "applies_to": {
            "file reading agents",
            "log reading agents",
            "information/evidence gathering agents",
        },
        "roles": {
            "blocker-taxonomy-evaluator",
            "deploy-impact-gate",
            "governance-project-router",
            "role-coverage-gate",
            "workflow-artifact-validator",
        },
    },
    "commit_local_validation_test_closeout_lane": {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "high",
        "applies_to": {"persistent gitflow closeout subagent"},
        "required_role_profile": "bears-git-workflow-helper",
    },
}
FORBIDDEN_REASONING_EFFORTS = {"l" + "ow"}
ALLOWED_REASONING_EFFORTS = {"medium", "high"}
EXPECTED_CODEX_REASONING_ALIASES = {"operator_wording_middle": "medium"}
REQUIRED_POST_TASK_AUDITS = {
    "plugin-fit-audit": "bears-workflow-overlay-platform-engineer",
    "new-functionality-drift-audit": "bears-platform-role-governor",
    "documentation-secret-safety-audit": "bears-platform-security-reviewer",
    "user-information-capture-audit": "bears-platform-role-governor",
}
LEGACY_AUDIT_RULE_ALIASES = {
    "non-product-post-task-audit-subagents": "stage-boundary-audits-only",
    "plugin-fit-post-task-audit": "plugin-fit-stage-boundary-audit",
    "new-functionality-drift-post-task-audit": "new-functionality-drift-stage-boundary-audit",
    "documentation-secret-safety-post-task-audit": "documentation-secret-safety-stage-boundary-audit",
    "user-information-capture-post-task-audit": "user-information-capture-stage-boundary-audit",
}
REQUIRED_DELEGATION_CONTROLLERS = {
    "devops-delegation-controller": {
        "role": "bears-deploy-platform-engineer",
        "must_spawn": {"kubernetes-specialist", "bears-runtime-verifier"},
        "must_lanes": {
            "kubernetes repo boundary",
            "Proxmox read-only evidence",
            "network read-only evidence",
            "runtime verification",
            "rollback runbook review",
        },
    },
    "workflow-delegation-controller": {
        "role": "bears-subagent-orchestration-engineer",
        "must_spawn": {"bears-platform-role-governor", "bears-platform-security-reviewer"},
        "must_lanes": {"plugin policy review"},
    },
    "governance-delegation-controller": {
        "role": "bears-platform-role-governor",
        "must_spawn": {"bears-explorer", "bears-docs-maintainer"},
        "must_lanes": {"registry consistency audit"},
    },
    "l2-platform-domain-delegation-controller": {
        "role": "l2-platform-domain-orchestrator",
        "must_spawn": {
            "bears-token-budget-helper",
            "bears-git-workflow-helper",
            "bears-review-fix-helper",
        },
        "must_lanes": {
            "token economy support",
            "git local-validation cache closeout support",
            "review fix support",
        },
    },
    "l2-gitops-domain-delegation-controller": {
        "role": "l2-gitops-domain-orchestrator",
        "must_spawn": {
            "bears-token-budget-helper",
            "bears-git-workflow-helper",
            "bears-review-fix-helper",
        },
        "must_lanes": {
            "token economy support",
            "git local-validation cache closeout support",
            "review fix support",
        },
    },
    "l2-infra-domain-delegation-controller": {
        "role": "l2-infra-domain-orchestrator",
        "must_spawn": {
            "bears-token-budget-helper",
            "bears-git-workflow-helper",
            "bears-review-fix-helper",
        },
        "must_lanes": {
            "token economy support",
            "git local-validation cache closeout support",
            "review fix support",
        },
    },
    "l2-product-infra-domain-delegation-controller": {
        "role": "l2-product-infra-domain-orchestrator",
        "must_spawn": {
            "bears-token-budget-helper",
            "bears-git-workflow-helper",
            "bears-review-fix-helper",
        },
        "must_lanes": {
            "token economy support",
            "git local-validation cache closeout support",
            "review fix support",
        },
    },
}
SECRET_FIELD_MARKERS = ("token", "secret", "password", "private_key", "api_key", "bearer", "authorization")

DESIGN_ARTIFACT_PATH = "README.md#issue-22-design-artifact-contract"
PROTOTYPE_CONTRACT_ID = "issue-21-prototype-spike-gate"
PROTOTYPE_ARTIFACT_BASENAMES = {"prototype.md", "spike.md"}
REQUIRED_DESIGN_SECTIONS = (
    "problem statement",
    "current behavior",
    "target behavior",
    "decision table or policy matrix",
    "affected artifacts and ownership",
    "validator impact",
    "documentation impact",
    "test plan",
    "compatibility notes",
    "safety boundaries",
    "open questions",
    "review gate condition",
)
DESIGN_REQUIRED_CHANGE_TYPES = {
    "workflow policy",
    "orchestration policy",
    "subagent policy",
    "hook behavior",
    "roadmap control",
    "role gate",
    "runtime contract",
    "validator behavior",
    "operator interaction",
    "developer interaction",
    "ui/ux flow",
}
PROTOTYPE_REQUIRED_UNCERTAINTY_FIELDS = (
    "research_or_design_unresolved_high_risk_uncertainty",
    "cheaply_testable_before_implementation",
)
PROTOTYPE_REQUIRED_SECTIONS = (
    "hypothesis or uncertainty",
    "prototype scope and non-goals",
    "commands or checks run",
    "findings and evidence summary",
    "decision outcome",
    "validation implications",
    "cleanup or discard requirements",
)
PROTOTYPE_DECISIONS = {"proceed", "redesign", "defer", "kill"}
PROTOTYPE_SAFETY_FIELDS = (
    "production_mutation",
    "restricted_data_reads",
    "broad_implementation",
    "durable_implementation",
)
PROTOTYPE_REVIEW_CHANGE_FIELDS = (
    "material_behavior_change",
    "runtime_change",
    "boundary_change",
    "ui_ux_change",
    "architecture_change",
)
RESEARCH_CONTRACT_ID = "issue-20-research-gate"
RESEARCH_ARTIFACT_BASENAMES = {
    "research": "research.md",
    "prior_art": "prior-art.md",
    "ux_research": "ux-research.md",
}
REQUIRED_RESEARCH_SECTIONS = (
    "Decision or Recommendation",
    "Rationale",
    "Alternatives considered",
    "Risks and constraints",
    "Validation implications",
    "Sources",
)
RESEARCH_REQUIRED_CHANGE_TYPES = {
    "broad",
    "new",
    "risky",
    "drift-prone",
    "workflow",
    "workflow policy",
    "runtime",
    "runtime contract",
    "integration",
    "ui",
    "ux",
    "ui/ux flow",
    "automation",
    "plugin",
    "infra",
    "kubernetes",
    "migration",
    "boundary-sensitive",
    "orchestration policy",
    "subagent policy",
    "hook behavior",
    "roadmap control",
    "role gate",
    "validator behavior",
    "operator interaction",
    "developer interaction",
}
RESEARCH_REQUIRED_TRIGGER_FIELDS = (
    "broad_change",
    "new_workflow",
    "risky_change",
    "drift_prone_decision",
    "workflow_change",
    "runtime_change",
    "integration_change",
    "ui_change",
    "ux_change",
    "automation_pattern_change",
    "plugin_change",
    "infra_change",
    "kubernetes_change",
    "migration_change",
    "boundary_sensitive_change",
)
UX_RESEARCH_TRIGGER_FIELDS = (
    "ui_change",
    "ux_change",
    "workflow_change",
    "operator_interaction_change",
    "developer_interaction_change",
    "user_facing_change",
    "cli_change",
    "status_behavior_change",
    "error_behavior_change",
    "recovery_behavior_change",
    "notification_behavior_change",
)
REQUIRED_RESEARCH_TRACKS = {
    "github prior art/comparable implementations",
    "external best practices/mature-project patterns",
    "risks/constraints/alternatives/validation implications",
}
REQUIRED_UX_RESEARCH_TRACK = "UI/UX-friendly interface research"
REQUIRED_IMPLEMENTATION_PACKET_FIELDS = {
    "change_type",
    "research_required",
    "research_artifacts",
    "research_skip",
    "prototype_required",
    "prototype_artifact",
    "prototype_skip",
    "prototype_review",
    "design_required",
    "design_artifact",
    "design_skip",
    "affected_artifacts",
    "validator_impact",
    "documentation_impact",
    "test_plan",
    "safety_boundaries",
}
BRANCH_BEHAVIOR_FIELDS = (
    "behavior_branches",
    "policy_branches",
    "state_transitions",
    "operator_paths",
)
REQUIRED_PRE_TASK_HOOK_FIELDS = (
    "assignment packet id",
    "pre-task hook evidence",
    "operator missing data answers",
    "operator drift answers",
    "task-start authorization",
)
REQUIRED_DELEGATION_CLOSEOUT_FIELDS = (
    "spawn evidence",
    "closeout evidence",
    "validation hook result",
)
REQUIRED_MAIN_AGENT_ALLOWED_ACTIONS = (
    "route",
    "split",
    "assign",
    "wait",
    "integrate_evidence",
    "run_validators",
    "close",
    "report",
    "pre_task_hook",
)
REQUIRED_MAIN_AGENT_FORBIDDEN_ACTIONS = (
    "file_read_as_content_collector",
    "file_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_mutation",
    "implementation_tool_use",
)
REQUIRED_PARENT_CONTROL_ALLOWED_ACTIONS = (
    "route_target_and_role_selection",
    "split_assignment_packets",
    "request_named_validation_hook",
    "run_validators",
    "run_status_checks",
    "read_command_exit_codes",
    "read_bounded_summaries",
    "inspect_git_status_short",
    "inspect_changed_file_names",
    "create_github_planning_issue_when_operator_requested",
    "update_github_planning_issue_when_operator_requested",
    "integrate_subagent_evidence",
    "close_stale_or_completed_subagents",
)
REQUIRED_PARENT_CONTROL_FORBIDDEN_ACTIONS = (
    "file_write",
    "implementation_command",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_mutation_without_explicit_operator_request",
    "broad_file_content_collection",
    "raw_secret_read",
    "secret_read",
    "env_file_read",
    "raw_log_read",
    "raw_chat_read",
    "raw_vpn_config_read",
    "production_data_read",
)
REQUIRED_PARENT_CONTROL_RESTRICTED_READS = {
    "raw_secret",
    "secret",
    "env_file",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "production_data",
}
REQUIRED_READ_ONLY_AGENT_SAFETY_RULE_ID = "read-only-agent-safety-guard"
REQUIRED_READ_ONLY_FORBIDDEN_AUTHORITY = {
    "file_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_mutation",
    "runtime_mutation",
    "deployment_mutation",
    "credential_access",
    "raw_secret_read",
    "secret_read",
    "env_file_read",
    "raw_log_read",
    "raw_chat_read",
    "raw_vpn_config_read",
    "production_data_read",
}
READ_ONLY_AUTHORITY_ALIASES = {
    "file-write": "file_write",
    "file write": "file_write",
    "write": "file_write",
    "git": "git_push",
    "runtime mutation": "runtime_mutation",
    "runtime_mutation": "runtime_mutation",
    "deployment": "deployment_mutation",
    "deploy": "deployment_mutation",
    "deployment mutation": "deployment_mutation",
    "credential": "credential_access",
    "credentials": "credential_access",
    "read credentials": "credential_access",
    "raw secret": "raw_secret_read",
    "raw_secret": "raw_secret_read",
    "raw-secret": "raw_secret_read",
    "read raw secret": "raw_secret_read",
    "read raw secrets": "raw_secret_read",
    "secret": "secret_read",
    "secrets": "secret_read",
    "read secret": "secret_read",
    "read secrets": "secret_read",
    ".env read": "env_file_read",
    "read .env": "env_file_read",
    ".env": "env_file_read",
    "env file": "env_file_read",
    "env-file": "env_file_read",
    "env_file": "env_file_read",
    "env read": "env_file_read",
    "read env": "env_file_read",
    "read environment": "env_file_read",
    "environment values": "env_file_read",
    "environment value": "env_file_read",
    "environment variables": "env_file_read",
    "environment variable": "env_file_read",
    "raw log": "raw_log_read",
    "raw-log": "raw_log_read",
    "raw_log": "raw_log_read",
    "raw chat": "raw_chat_read",
    "raw-chat": "raw_chat_read",
    "raw_chat": "raw_chat_read",
    "raw vpn": "raw_vpn_config_read",
    "raw-vpn": "raw_vpn_config_read",
    "raw_vpn": "raw_vpn_config_read",
    "production data": "production_data_read",
    "production-data": "production_data_read",
    "production_data": "production_data_read",
}
READ_ONLY_ASSIGNMENT_AUTHORITY_FIELDS = {
    "assignment_authority",
    "allowed_actions",
    "allowed_writes",
    "requested_authority",
    "requested_actions",
    "tools",
    "permissions",
    "authority",
}
READ_ONLY_MUTABLE_ASSIGNMENT_FIELDS = {
    "write_scope",
    "mutable_scope",
    "changed_files",
    "target_write_paths",
    "implementation_scope",
}
READ_ONLY_EMPTY_SCOPE_VALUES = {
    "",
    "none",
    "no",
    "false",
    "read-only",
    "read_only",
    "readonly",
    "read-only review",
    "read_only_review",
    "read-only policy review",
    "read_only_policy_review",
    "n/a",
}
REQUIRED_PR_TASK_GUARD_RULE_ID = "pr-task-role-action-guard"
REQUIRED_ROLE_PROFILE_FALLBACK_RULE_ID = "role-profile-fallback-parity-guard"
PR_REVIEWER_MUTATION_STATUS = "REVIEWER_PR_MUTATION_BLOCKED"
PR_REVIEWER_MUTATION_REASON = "read_only_reviewer_pr_mutation"
PR_GOVERNOR_MUTATION_STATUS = "GOVERNOR_WRITABLE_PR_TASK_BLOCKED"
PR_GOVERNOR_MUTATION_REASON = "governor_pr_writer_lane_required"
ROLE_PROFILE_DOWNGRADE_STATUS = "ROLE_PROFILE_DOWNGRADE_BLOCKED"
ROLE_PROFILE_DOWNGRADE_REASON = "role_profile_parity_required"
GENERIC_FALLBACK_PR_MUTATION_STATUS = "GENERIC_FALLBACK_PR_MUTATION_BLOCKED"
GENERIC_FALLBACK_PR_MUTATION_REASON = "mutation_authority_lane_required"
PR_ALLOWED_STATUS = "allowed"
PR_ALLOWED_READ_ONLY_REASON = "read_only_pr_review"
PR_ALLOWED_GOVERNOR_WRITER_REASON = "explicit_governor_pr_writer_lane"
ROLE_PROFILE_FALLBACK_ALLOWED_REASON = "role_profile_parity_enforced"
ROLE_PROFILE_NOT_FALLBACK_REASON = "not_role_profile_fallback"
REQUIRED_PR_MUTATION_ACTIONS = {
    "pr_publish",
    "pr_label",
    "pr_comment",
    "pr_ready_for_review",
    "pr_merge",
    "pr_rebase",
    "pr_branch_delete",
    "git_push",
    "pr_title_edit",
    "pr_body_edit",
    "pull_request_mutation",
}
REQUIRED_PR_READ_ONLY_ACTIONS = {
    "pr_read",
    "pr_inspect",
    "pr_summarize",
    "pr_audit",
    "pr_review_read_only",
    "pr_status_read",
}
REQUIRED_PR_ACTION_FIELDS = {
    "pr_action",
    "pr_actions",
    "github_pr_action",
    "github_pr_actions",
    "requested_pr_actions",
    "assignment_authority",
    "requested_actions",
    "allowed_actions",
    "task_actions",
    "actions",
    "tools",
}
REQUIRED_PR_ROLE_FIELDS = {"child_role", "agent_role", "role", "requested_role"}
REQUIRED_PR_STATUS_REASONS = {
    (PR_ALLOWED_STATUS, PR_ALLOWED_READ_ONLY_REASON),
    (PR_ALLOWED_STATUS, PR_ALLOWED_GOVERNOR_WRITER_REASON),
    (PR_REVIEWER_MUTATION_STATUS, PR_REVIEWER_MUTATION_REASON),
    (PR_GOVERNOR_MUTATION_STATUS, PR_GOVERNOR_MUTATION_REASON),
}
PR_MUTATION_ACTION_ALIASES = {
    "publish": "pr_publish",
    "published": "pr_publish",
    "open_pr": "pr_publish",
    "create_pr": "pr_publish",
    "pr_publish": "pr_publish",
    "label": "pr_label",
    "labels": "pr_label",
    "add_label": "pr_label",
    "remove_label": "pr_label",
    "comment": "pr_comment",
    "comments": "pr_comment",
    "post_comment": "pr_comment",
    "ready": "pr_ready_for_review",
    "ready_for_review": "pr_ready_for_review",
    "mark_ready": "pr_ready_for_review",
    "merge": "pr_merge",
    "rebase": "pr_rebase",
    "branch_delete": "pr_branch_delete",
    "delete_branch": "pr_branch_delete",
    "branch_deletion": "pr_branch_delete",
    "push": "git_push",
    "git_push": "git_push",
    "title": "pr_title_edit",
    "title_edit": "pr_title_edit",
    "edit_title": "pr_title_edit",
    "body": "pr_body_edit",
    "body_edit": "pr_body_edit",
    "edit_body": "pr_body_edit",
    "description_edit": "pr_body_edit",
    "pull_request_mutation": "pull_request_mutation",
    "pr_mutation": "pull_request_mutation",
}
PR_READ_ONLY_ACTION_ALIASES = {
    "read": "pr_read",
    "inspect": "pr_inspect",
    "summarize": "pr_summarize",
    "summary": "pr_summarize",
    "audit": "pr_audit",
    "review": "pr_review_read_only",
    "read_only_review": "pr_review_read_only",
    "readonly_review": "pr_review_read_only",
    "status_read": "pr_status_read",
    "check_status": "pr_status_read",
}
REQUIRED_ROLE_PROFILE_FALLBACK_GENERIC_AGENT_TYPES = {
    "backend-developer",
    "backend_developer",
    "frontend-developer",
    "frontend_developer",
    "fullstack-developer",
    "fullstack_developer",
    "general-purpose",
    "general_purpose",
    "software-engineer",
    "software_engineer",
    "developer",
    "code-writer",
    "code_writer",
}
REQUIRED_ROLE_PROFILE_FALLBACK_AGENT_TYPE_FIELDS = {
    "agent_type",
    "fallback_agent_type",
    "fallback_role",
    "child_agent_type",
    "worker_profile",
}
REQUIRED_ROLE_PROFILE_FALLBACK_DOMAIN_OWNER_FIELDS = {
    "domain_owner",
    "domain_role",
    "bears_domain_owner",
    "requested_domain_owner",
    "requested_role",
    "owner_role",
    "primary_role",
}
REQUIRED_ROLE_PROFILE_FALLBACK_IMPLEMENTATION_FIELDS = {
    "implementation_handoff",
    "implementation_task",
    "handoff_type",
    "task_type",
    "assignment_type",
    "task_summary",
    "assignment_summary",
    "write_scope",
    "target_write_paths",
}
REQUIRED_ROLE_PARITY_PACKET_FIELDS = {
    "validated",
    "domain_owner",
    "fallback_agent_type",
    "developer_instructions_packet_attached",
    "exact_role_profile_attached",
    "role_gate_result_attached",
}
REQUIRED_ROLE_PROFILE_OPERATOR_APPROVAL_FIELDS = {"approved", "approval_reference"}
REQUIRED_ROLE_PROFILE_PARENT_PREFERENCE_ORDER = {
    "retry_same_bears_role",
    "reduce_scope",
    "split_task",
    "request_role_profile_downgrade",
}
REQUIRED_ROLE_PROFILE_MUTATION_AUTHORITY_FIELDS = {
    "lane_id",
    "approved",
    "approved_actions",
    "approval_reference",
}
REQUIRED_ROLE_PROFILE_FINAL_REPORT_FIELDS = {
    "fallback_role",
    "domain_owner",
    "profile_downgrade_status",
    "parity_enforcement",
    "mutation_authority_lane",
    "safety_rationale",
}
REQUIRED_ROLE_PROFILE_STATUS_REASONS = {
    (PR_ALLOWED_STATUS, ROLE_PROFILE_NOT_FALLBACK_REASON),
    (PR_ALLOWED_STATUS, ROLE_PROFILE_FALLBACK_ALLOWED_REASON),
    (ROLE_PROFILE_DOWNGRADE_STATUS, ROLE_PROFILE_DOWNGRADE_REASON),
    (GENERIC_FALLBACK_PR_MUTATION_STATUS, GENERIC_FALLBACK_PR_MUTATION_REASON),
}
REQUIRED_WORKER_POOL_STATES = {
    "active",
    "idle",
    "reusable",
    "fresh-required",
    "stale",
}
REQUIRED_WORKER_POOL_REUSE_REQUIREMENTS = {
    "same_role",
    "same_repo_boundary",
    "compatible_write_scope",
    "no_restricted_data_taint",
    "compact_continuation_packet",
}
REQUIRED_SESSION_RUNTIME_VALIDATION_COMMAND = "python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>"
REQUIRED_CONTINUATION_PACKET_FIELDS = {
    "worker_id",
    "role",
    "repo_boundary",
    "write_scope",
    "last_assignment_packet_id",
    "status_summary",
    "validation_target",
    "restricted_data_taint",
    "changed_files",
}
REQUIRED_CONTINUATION_FORBIDDEN_FIELDS = {
    "raw_secret",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "production_data",
}
REQUIRED_STALE_WORKER_CLOSE_CONDITIONS = {
    "role_mismatch",
    "repo_boundary_mismatch",
    "write_scope_incompatible",
    "restricted_data_taint_present",
    "missing_compact_continuation_packet",
    "validation_target_changed",
    "worker_branch_or_worktree_changed",
    "assignment_scope_completed",
    "pre_task_hook_rejected_reuse",
    "operator_requested_close",
    "audit_lane_completed",
}
REQUIRED_PARALLEL_RULE_TEXT = {
    "[P] marker": "[P]",
    "MUST requirement": "MUST",
    "maximize parallelism": "maximize parallelism",
    "parallel delegation": "parallel delegation",
    "disjoint scopes": "disjoint",
}
REQUIRED_GOAL_PARALLELIZATION_PREFLIGHT_FIELDS = {
    "enabled",
    "preflight_id",
    "applies_to",
    "fixed_assignment_packet",
    "batch_role_gate",
    "spawn_agent_argument_shape",
    "wait_agent_target_validation",
    "wait_any_loop",
    "worker_pool_ledger",
    "backend_only_scope_lock",
    "handoff_guards",
    "fanout_thread_limit_preflight",
    "new_wave_gate",
    "final_join_gate",
    "result_policy",
    "issue_mapping",
    "parent_plan_status_gate",
}
REQUIRED_FANOUT_THREAD_LIMIT_PREFLIGHT_FIELDS = {
    "required",
    "hard_max_source",
    "active_cap_source",
    "active_open_count_required",
    "active_open_count_sources",
    "active_states_counted",
    "open_states_counted",
    "completed_no_longer_needed_close_before_spawn",
    "close_completed_source",
    "critical_path_wait_slot_reservation",
    "available_slots_formula",
    "bounded_batch_spawn_when_requested_exceeds_available",
    "spawn_batch_rule",
    "reject_when_requested_active_exceeds_cap",
    "hard_max_is_safety_cap_only",
    "thread_limit_failure_classification",
    "thread_limit_failure_normal_recovery_allowed",
    "drift_evidence_required",
}
REQUIRED_FANOUT_COUNT_SOURCES = {
    "worker_pool_ledger.active_agent_ids",
    "worker_pool_ledger.open_agent_ids",
    "worker_pool_ledger.completed_agent_ids",
}
REQUIRED_FANOUT_ACTIVE_STATES = {"spawned", "active"}
REQUIRED_FANOUT_OPEN_STATES = {"spawned", "active", "completed", "stale", "partial"}
REQUIRED_GOAL_PREFLIGHT_PACKET_FIELDS = {
    "assignment_packet_id",
    "goal_id",
    "tasks_md_item_id",
    "role",
    "target_path",
    "repo_boundary",
    "write_scope",
    "validation_commands",
    "pre_task_hook_evidence",
    "backend_only_scope_lock",
    "worker_pool_ledger_id",
}
REQUIRED_GOAL_PREFLIGHT_SPAWN_ARGS = {
    "role",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
    "developer_instructions",
    "assignment_packet_id",
    "target_path",
    "write_scope",
    "validation_commands",
}
REQUIRED_GOAL_PREFLIGHT_WAIT_TARGET_SOURCES = {
    "spawn_agent_return.agent_id",
    "worker_pool_ledger.agent_id",
}
REQUIRED_GOAL_PREFLIGHT_LEDGER_FIELDS = {
    "agent_id",
    "assignment_packet_id",
    "role",
    "target_path",
    "write_scope",
    "state",
    "spawned_at",
    "last_wait_result",
    "closeout_evidence",
    "reconciliation_status",
    "parent_agent_id",
    "depth",
    "parent_authorization_id",
    "reuse_reason",
}
REQUIRED_GOAL_PREFLIGHT_LEDGER_STATES = {
    "eligible",
    "spawned",
    "active",
    "completed",
    "closed",
    "stale",
    "partial",
}
REQUIRED_FINAL_JOIN_GATE_FIELDS = {
    "required",
    "gate_id",
    "scope_source",
    "identity_fields",
    "blocks_parent_completion",
    "requires_all_spawned_agents_terminal",
    "requires_partial_state_reconciled",
    "requires_worker_pool_ledger_closed",
    "fail_closed_states",
    "conditional_terminal_states",
    "integrated_evidence_fields",
    "close_decision_field",
    "failed_disposition_field",
    "dependent_wait_sources",
    "fail_closed_conditions",
    "pass_conditions",
}
REQUIRED_FINAL_JOIN_IDENTITY_FIELDS = {"agent_id", "assignment_packet_id"}
REQUIRED_FINAL_JOIN_FAIL_CLOSED_STATES = {
    "eligible",
    "queued",
    "spawned",
    "active",
    "stale",
    "partial",
    "unknown",
}
REQUIRED_FINAL_JOIN_CONDITIONAL_TERMINAL_STATES = {"closed", "completed", "failed"}
REQUIRED_FINAL_JOIN_INTEGRATED_EVIDENCE_FIELDS = {
    "integrated_evidence",
    "closeout_evidence",
}
REQUIRED_FINAL_JOIN_DEPENDENT_WAIT_SOURCES = {
    "dependent_waits",
    "worker_pool_ledger.dependent_wait_remaining",
}
REQUIRED_FINAL_JOIN_FAIL_CLOSED_CONDITIONS = {
    "any_spawned_subagent_active",
    "any_spawned_subagent_queued",
    "any_spawned_subagent_unknown",
    "any_spawned_subagent_missing_terminal_evidence",
    "any_failed_subagent_without_disposition",
    "any_completed_subagent_without_integrated_evidence",
    "any_completed_subagent_without_close_decision",
    "any_dependent_wait_remaining",
}
REQUIRED_FINAL_JOIN_PASS_CONDITIONS = {
    "all_spawned_subagent_outcomes_integrated",
    "all_spawned_subagents_have_close_decision",
    "no_dependent_wait_remaining",
}
REQUIRED_GOAL_PREFLIGHT_ALLOWED_SURFACES = {
    "policy_catalog",
    "validator_script",
    "unit_tests",
}
REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_SURFACES = {
    "README",
    "docs/reference",
    "product",
    "runtime",
    "delivery_surface",
    "gitlink_helper",
    "credential_material",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "github_pr_issue_state",
    "frontend",
    "mobile",
    "UI",
    "web client",
    "app screens",
    "visual assets",
}
REQUIRED_GOAL_PREFLIGHT_BLOCKED_RESULTS = {
    "ROLE_COVERAGE_BLOCKER",
    "restricted_data_request",
    "overlapping_write_scope",
    "invalid_assignment_packet",
    "invalid_spawn_agent_arguments",
    "invalid_wait_agent_target_id",
    "missing_final_join_gate",
    "WORKFLOW_DRIFT",
}
REQUIRED_NEW_WAVE_CHECKPOINT_COUNT_FIELDS = {
    "active_workers",
    "active_reviewers",
    "completed_not_closed_agents",
}
REQUIRED_PARENT_PLAN_STATUS_STEPS = {"pull_request", "merge", "review"}
REQUIRED_PARENT_PLAN_COMPLETED_EVIDENCE_FIELDS = {
    "pr_url",
    "check_status",
    "reviewer_pass_evidence",
    "worker_closeout_evidence",
}
REQUIRED_PARENT_PLAN_MERGE_EVIDENCE_FIELDS = {"merge_sha"}
REQUIRED_PARENT_BLOCKER_ARTIFACT_FIELDS = {
    "artifact_id",
    "artifact_type",
    "status",
    "owner",
    "path_or_url",
}
ALLOWED_PARENT_BLOCKER_ARTIFACT_TYPES = {
    "bears-blocker-review",
    "bears-workflow-overlay.blocker-review",
}
REQUIRED_NESTED_AUTHORIZATION_FIELDS = {
    "authorization_id",
    "allowed_role",
    "scope",
    "max_nested_count",
}
REQUIRED_NESTED_TRACKING_FIELDS = {
    "agent_id",
    "parent_agent_id",
    "depth",
    "parent_authorization_id",
}
REQUIRED_GOAL_PREFLIGHT_NON_BLOCKING_RESULTS = {
    "no_eligible_task",
    "no_write",
    "needs_parent_split",
}
REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_FIELDS = {
    "raw_secret",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "production_data",
}
REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_SPAWN_ARGS = {
    *REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_FIELDS,
    "git_commit",
    "git_push",
    "pull_request_mutation",
}
REQUIRED_SPAWN_CONTENT_PATHS = ("message", "items")
REQUIRED_SPAWN_CONTENT_PATH_POLICY_FIELDS = {
    "exactly_one_of",
    "reject_when_both_present",
    "reject_when_neither_present",
    "validation_timing",
}
REQUIRED_SPAWN_PLUGIN_FORM_FIELDS = {
    "required_when_plugin_mention",
    "content_path",
    "items_length",
    "item_type",
    "text_field",
    "required_text_markers",
    "forbidden_top_level_fields",
}
REQUIRED_SPAWN_PREINVOKE_FIELDS = {
    "reject_before_tool_invocation",
    "rejection_error",
}
REQUIRED_SPAWN_RETRY_FIELDS = {
    "required",
    "drift_log_required",
    "wrapper_only_change_required",
    "preserve_sections_byte_for_byte",
}
REQUIRED_SPAWN_PLUGIN_TEXT_MARKERS = ("@bears", "PRE_TASK_HOOK", "ASSIGNMENT_PACKET")
REQUIRED_SPAWN_RETRY_PRESERVED_SECTIONS = ("PRE_TASK_HOOK", "ASSIGNMENT_PACKET")
SUBAGENT_EXECUTABLE_ASSIGNMENT_LANES = {"worker", "reviewer"}
SUBAGENT_REVIEWER_LANE_MODES = {"advisory_async", "blocking_gate"}
SUBAGENT_BLOCKING_GATE_HARD_STOP_REASONS = {
    "merge_authority",
    "role_coverage",
    "restricted_data",
    "security",
    "secret_handling",
    "explicit_operator_stop",
    "linked_contract_hard_stop",
}
SUBAGENT_REQUIRED_SPEC_KIT_BINDING_PATH_FIELDS = {
    "spec_md_path": "spec.md",
    "plan_md_path": "plan.md",
    "tasks_md_path": "tasks.md",
}
SUBAGENT_REQUIRED_SPEC_KIT_BINDING_FEATURE_FIELDS = {
    "feature_dir",
    "spec_file",
    "plan_file",
    "tasks_file",
}
SUBAGENT_FORBIDDEN_ACCEPTANCE_EVIDENCE = {
    "parent_thread_summary",
    "parent-thread-summary",
    "parent thread summary",
    "parent_context_summary",
    "parent-context-summary",
    "chat_text",
    "chat-text",
    "chat text",
    "raw_chat",
    "raw chat",
    "reviewer_opinion",
    "reviewer-opinion",
    "reviewer opinion",
    "unchecked_issue_text",
    "unchecked issue text",
}
SUBAGENT_REQUIRED_STALE_RESULT_REJECTION_FIELDS = {
    "status",
    "stale_result",
    "checked_at",
    "freshness_source",
    "assignment_packet_id",
}
EXPECTED_GOAL_PREFLIGHT_ISSUE_MAPPING = {
    "BearsCLOUD/bears_plugin#173": "central_goal_parallelization_preflight_lane",
    "BearsCLOUD/bears_plugin#76": "backend_only_parallel_prompt_guard",
    "BearsCLOUD/bears_plugin#78": "task_ledger_role_gate_before_delegation",
    "BearsCLOUD/bears_plugin#83": "spawn_template_model_capability_preflight",
    "BearsCLOUD/bears_plugin#84": "fork_context_spawn_inheritance_guard",
    "BearsCLOUD/bears_plugin#87": "parallel_shared_worktree_isolation_guard",
    "BearsCLOUD/bears_plugin#89": "mixed_role_target_split_guard",
    "BearsCLOUD/bears_plugin#90": "pr_review_repo_scope_guard",
    "BearsCLOUD/bears_plugin#95": "credential_surface_output_guard",
    "BearsCLOUD/bears_plugin#99": "english_subagent_closeout_guard",
    "BearsCLOUD/bears_plugin#112": "leaf_pr_delivery_role_guard",
    "BearsCLOUD/bears_plugin#121": "slice_scoped_final_audit_verdict_guard",
    "BearsCLOUD/bears_plugin#122": "current_day_checkpoint_collector_guard",
    "BearsCLOUD/bears_plugin#127": "current_state_source_authority_guard",
    "BearsCLOUD/bears_plugin#129": "discovery_implementation_split_guard",
    "BearsCLOUD/bears_plugin#130": "parent_control_patch_content_guard",
    "BearsCLOUD/bears_plugin#131": "draft_pr_publication_merge_guard",
    "BearsCLOUD/bears_plugin#103": "no_eligible_task_non_blocking",
    "BearsCLOUD/bears_plugin#154": "fanout_thread_limit_preflight",
    "BearsCLOUD/bears_plugin#153": "wait_agent_target_id_validation",
    "BearsCLOUD/bears_plugin#142": "spawn_agent_argument_shape_validation",
    "BearsCLOUD/bears_plugin#138": "completed_subagent_close_evidence_before_new_waves",
    "BearsCLOUD/bears_plugin#158": "final_join_gate_before_parent_completion",
    "BearsCLOUD/bears_plugin#157": "partial_state_reconciliation_before_capacity_fallback",
    "BearsCLOUD/bears_plugin#145": "parent_plan_status_evidence_gate",
    "BearsCLOUD/bears_plugin#155": "nested_worker_delegation_parent_authorization",
}
REQUIRED_BATCH_ROLE_GATE_FIELDS = {
    "required",
    "input",
    "command",
    "matched_result_fields",
    "blocker_result",
    "missing_mapping_task_fields",
    "runs_before_worker_spawn",
}
REQUIRED_BATCH_ROLE_GATE_MATCHED_FIELDS = {
    "path",
    "status",
    "primary_role",
    "validation_required",
}
REQUIRED_BATCH_ROLE_GATE_MISSING_TASK_FIELDS = {
    "path",
    "missing_role",
    "catalog_target",
    "validator_command",
}
REQUIRED_HANDOFF_GUARDS = {
    "backend_only_parallel_prompt_guard",
    "task_ledger_role_gate_before_delegation",
    "spawn_template_model_capability_preflight",
    "fork_context_spawn_inheritance_guard",
    "parallel_shared_worktree_isolation_guard",
    "mixed_role_target_split_guard",
    "pr_review_repo_scope_guard",
    "credential_surface_output_guard",
    "english_subagent_closeout_guard",
    "leaf_pr_delivery_role_guard",
    "slice_scoped_final_audit_verdict_guard",
    "current_day_checkpoint_collector_guard",
    "current_state_source_authority_guard",
    "discovery_implementation_split_guard",
    "parent_control_patch_content_guard",
    "draft_pr_publication_merge_guard",
}
REQUIRED_HANDOFF_GUARD_FIELDS = {
    "guard_id",
    "required",
    "issue",
    "enforcement",
    "required_packet_fields",
    "reject_when",
}
MODEL_UNSUPPORTED_FIELDS = {
    "gpt-5.3-codex-spark": {"reasoning.summary", "reasoning_summary"},
}
CYRILLIC_RANGE = re.compile(r"[\u0400-\u04FF]")
PATCH_CONTENT_COMMAND_RE = re.compile(r"\bgit\s+diff\b(?![^\n;|]*\s--(?:stat|name-status)\b)")
CURRENT_DAY_SESSION_SCAN_RE = re.compile(
    r"\b(?:find|rg|grep)\b[^\n]*(?:/home/ai1/\.codex/sessions|~/?\.codex/sessions)",
    re.IGNORECASE,
)
CURRENT_STATE_BROAD_SCAN_RE = re.compile(
    r"\b(?:find|rg|grep)\b[^\n]*(?:\.worktrees|dev/platform|/srv/bears)(?![^\n]*(?:--files-with-matches|--max-count=1))",
    re.IGNORECASE,
)
MEMORY_READ_RE = re.compile(r"(?:/home/ai1/\.codex/memories|MEMORY\.md|rollout_summaries)", re.IGNORECASE)
CURRENT_DAY_PACKET_MARKERS = (
    "current-day",
    "current_day",
    "current day",
    "today only",
    "today-only",
    "checkpoint-only",
    "checkpoint_only",
    "checkpoint collector",
    "session checkpoint",
)
CURRENT_STATE_PACKET_MARKERS = (
    "current-state",
    "current_state",
    "current state",
    "final audit",
    "final-audit",
    "closeout audit",
    "authoritative current",
    "current pr",
    "current heads",
)
CURRENT_STATE_AUTHORITY_FIELDS = (
    "source_authority",
    "source_authority_by_claim",
    "source_authorities",
    "fresh_source_proof",
    "fresh_command_evidence",
    "fresh_api_evidence",
)
CURRENT_STATE_CLAIM_AUTHORITY_FIELDS = (
    "source_authority",
    "fresh_source_proof",
    "fresh_command_evidence",
    "fresh_api_evidence",
    "exact_commit",
    "exact_file_list",
    "live_endpoint",
    "pr_api",
)
NO_SUBAGENT_REQUIRED_RULES = (
    "parent_applies_nearest_role_instructions",
    "required_role_gate_still_applies",
    "read_only_no_op_skips_non_product_audit_subagents",
    "mutation_upgrades_to_normal_gated_mode",
    "explicit_subagent_request_blocks_no_subagent_mode",
)
NO_SUBAGENT_ALLOWED_CASES = {
    "side-conversation-answer": {
        "request_type": "side_conversation_answer",
        "scope": "answer_only",
        "mutation_handling": "forbidden",
        "stage_boundary_audits": "not_run",
    },
    "question-only-explanation": {
        "request_type": "question_only_explanation",
        "scope": "answer_only",
        "mutation_handling": "forbidden",
        "stage_boundary_audits": "not_run",
    },
    "single-command-read-only-status-check": {
        "request_type": "single_command_read_only_status_check",
        "scope": "one_read_only_command",
        "mutation_handling": "forbidden",
        "stage_boundary_audits": "not_run",
    },
    "bounded-repo-inspection-no-mutation": {
        "request_type": "bounded_repo_inspection_no_mutation",
        "scope": "bounded_read_only_repo_inspection",
        "mutation_handling": "forbidden",
        "stage_boundary_audits": "not_run",
    },
    "small-exact-file-bugfix-policy-exception": {
        "request_type": "small_exact_file_bugfix",
        "scope": "one_exact_file_when_existing_bugfix_exception_allows",
        "mutation_handling": "upgrade_to_normal_gated_mode_before_write",
        "stage_boundary_audits": "normal_gated_mode_decides",
    },
}
NO_SUBAGENT_BLOCKED_CASES = {
    "repo-boundary-change": "normal_gated_mode_required",
    "plugin-policy-change": "normal_gated_mode_required",
    "runtime-deployment-migration-secret-change": "normal_gated_mode_required",
    "multi-file-implementation": "normal_gated_mode_required",
    "explicit-subagent-request": "subagent_mode_required",
}
REQUIRED_VALIDATION_HOOKS = {
    "platform_roles_validate": {
        "command_id": "platform_roles_validate",
        "script": "scripts/platform_roles.py",
        "args": ("validate",),
        "target_required": False,
    },
    "role_route": {
        "command_id": "platform_roles_route",
        "script": "scripts/platform_roles.py",
        "args": ("route", "{validation_target}"),
        "target_required": True,
    },
    "role_audit": {
        "command_id": "platform_roles_audit",
        "script": "scripts/platform_roles.py",
        "args": ("audit", "{validation_target}"),
        "target_required": True,
    },
    "project_registry_gate": {
        "command_id": "project_registry_gate",
        "script": "scripts/project_registry_gate.py",
        "args": ("gate", "{validation_target}"),
        "target_required": True,
    },
    "subagent_policy_validate": {
        "command_id": "subagent_policy_validate",
        "script": "scripts/subagent_orchestration_policy.py",
        "args": ("validate",),
        "target_required": False,
    },
    "overlay_validate": {
        "command_id": "overlay_validate_strict",
        "script": "scripts/validate_overlay.py",
        "args": ("--json", "validate", "--strict-overlay-skills"),
        "target_required": False,
    },
    "roadmap_validate": {
        "command_id": "roadmap_validate",
        "script": "scripts/roadmap_control.py",
        "args": ("validate",),
        "target_required": False,
    },
    "git_discipline_validate": {
        "command_id": "git_discipline_validate",
        "script": "scripts/git_discipline.py",
        "args": ("validate",),
        "target_required": False,
    },
    "plugin_constitution_validate": {
        "command_id": "plugin_constitution_validate",
        "script": "scripts/plugin_constitution.py",
        "args": ("validate",),
        "target_required": False,
    },
    "role_gate_methodology_validate": {
        "command_id": "role_gate_methodology_validate",
        "script": "scripts/role_gate_methodology.py",
        "args": ("validate",),
        "target_required": False,
    },
    "session_workers_runtime_validate": {
        "command_id": "session_workers_runtime_validate",
        "script": "scripts/session_workers_runtime.py",
        "args": ("validate",),
        "target_required": False,
    },
    "agent_github_dev_cd_validate": {
        "command_id": "agent_github_dev_cd_validate",
        "script": "scripts/agent_github_dev_cd.py",
        "args": ("validate",),
        "target_required": False,
    },
    "project_registry_validate": {
        "command_id": "project_registry_validate",
        "script": "scripts/project_registry_gate.py",
        "args": ("validate-registry",),
        "target_required": False,
    },
    "skill_catalog_generate_check": {
        "command_id": "skill_catalog_generate_check",
        "script": "scripts/skill_catalog.py",
        "args": ("generate", "--check"),
        "target_required": False,
    },
    "secret_factory_validate": {
        "command_id": "secret_factory_validate",
        "script": "scripts/secret_factory.py",
        "args": ("validate",),
        "target_required": False,
    },
    "full_tests_discover": {
        "command_id": "full_tests_discover",
        "script": "python3",
        "args": ("-m", "unittest", "discover", "-s", "tests"),
        "target_required": False,
    },
}
REQUIRED_HOOK_RESULT_FIELDS = (
    "hook_id",
    "cwd",
    "command_id",
    "exit_code",
    "sanitized_summary",
    "validation_target",
)
REQUIRED_HOOK_FORBIDDEN_REQUEST_KINDS = {
    "arbitrary_shell",
    "inline_command",
    "env_file_read",
    "credential_read",
    "raw_log_read",
    "raw_chat_read",
    "raw_vpn_config_read",
    "production_data_read",
}
REQUIRED_HOOK_FORBIDDEN_RESULT_FIELDS = {
    "raw_stdout",
    "raw_stderr",
    "env",
    "token",
    "secret",
    "password",
    "private_key",
    "api_key",
    "authorization",
    "credential",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "production_data",
}
FORBIDDEN_HOOK_ARG_TOKENS = {"sh", "bash", "zsh", "fish", "-c", "|", ">", "<", "&&", "||", ";"}
REQUIRED_PARALLEL_AUDIT_EVENT_FIELDS = {
    "event_id",
    "occurred_at",
    "actor_id",
    "actor_role",
    "lane_id",
    "action",
    "target_path",
    "assignment_packet_id",
    "evidence_ref",
    "severity",
    "deduplication_key",
    "restricted_data_policy",
}
REQUIRED_PARALLEL_AUDIT_EVENTS = {
    "route_gate_result",
    "pre_task_hook_result",
    "subagent_spawn_or_reuse_decision",
    "wait_agent_checkpoint",
    "validation_hook_result",
    "evidence_integration_decision",
    "github_issue_create_or_update",
    "stage_boundary_closeout",
    "restricted_data_safety_finding",
}
REQUIRED_PARALLEL_AUDIT_SEVERITIES = {"info": False, "warning": False, "material": False, "hard_stop": True}
REQUIRED_PARALLEL_AUDIT_HARD_STOP_MARKERS = {
    "ROLE_COVERAGE_BLOCKER",
    "restricted data",
    "allowed write scope",
    "production mutation",
    "repository-boundary",
    "write scope lock",
}
REQUIRED_PARALLEL_AUDIT_DEDUP_FIELDS = {
    "owner_repo",
    "policy_id",
    "finding_type",
    "target_path",
    "actor_role",
    "spec_id",
    "roadmap_id",
}
REQUIRED_PARALLEL_AUDIT_ISSUE_FIELDS = {
    "finding_summary",
    "severity",
    "deduplication_key",
    "bounded_evidence_refs",
    "affected_target",
    "required_next_action",
    "hard_stop_condition",
}
REQUIRED_PARALLEL_AUDIT_ISSUE_FORBIDDEN_FIELDS = {
    "raw_secret",
    "raw_log",
    "raw_chat",
    "raw_vpn_config",
    "production_data",
    "environment_values",
    "credential_material",
}
REQUIRED_PARALLEL_AUDIT_ISSUE_LINK_FIELDS = {"created_issue", "updated_issue", "existing_issue"}
REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_RESPONSIBILITIES = {
    "commit",
    "local_commit_validation_status",
    "closeout",
    "explicit_closeout_packet_handling",
}
REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_ALLOWED_CHECKS = {
    "platform_roles_route_for_changed_targets",
    "platform_roles_audit_for_changed_targets",
    "json_toml_python_syntax",
    "git_diff_check",
    "git_status_log",
    "local_commit_validation_proof_metadata",
}
REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_FORBIDDEN_CHECKS = {
    "pytest",
    "unittest",
    "repo_validator_suites",
    "raw_ci_log_read",
}
REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_CLOSEOUT_FIELDS = {
    "start_sha",
    "final_sha",
    "changed_files",
    "commit_sha",
    "push_status",
    "local_commit_validation_status",
    "local_commit_validation_proof_path",
        "local_test_policy_evidence",
    "closeout_status",
}
REQUIRED_CONCURRENT_GIT_SAFETY_POLICY = {
    "one_file_one_owner_per_wave": True,
    "git_fetch_before_commit": True,
    "git_fetch_before_push": True,
    "verify_head_origin_main_start_sha": True,
    "fast_forward_only_push": True,
    "force_push_forbidden": True,
    "stale_file_change_policy": "stop_or_explicit_rebase_diff_review",
    "changed_files_required": True,
    "parent_closeout_head_status_check_required": True,
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def _load_platform_roles_module() -> Any:
    spec = importlib.util.spec_from_file_location("platform_roles", PLUGIN_ROOT / "scripts/platform_roles.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load platform_roles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def _require_object(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return False
    return True


def _require_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    non_empty: bool = True,
    item_type: type | tuple[type, ...] | None = str,
    item_label: str = "strings",
) -> bool:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return False
    if non_empty and not value:
        errors.append(f"{path} must be non-empty")
    if item_type is not None and not all(isinstance(item, item_type) for item in value):
        errors.append(f"{path} must contain only {item_label}")
    return True


def _validate_exact_string_tokens(
    value: Any,
    path: str,
    *,
    expected: tuple[str, ...],
    errors: list[str],
) -> None:
    if not _require_list(value, path, errors):
        return
    if not all(isinstance(item, str) for item in value):
        errors.append(f"{path} must contain only strings")
        return
    actual = list(value)
    unexpected = sorted(set(actual) - set(expected))
    missing = [item for item in expected if item not in actual]
    duplicates = sorted({item for item in actual if actual.count(item) > 1})
    if missing:
        errors.append(f"{path} missing required tokens: " + ", ".join(missing))
    if unexpected:
        errors.append(f"{path} contains unexpected tokens: " + ", ".join(unexpected))
    if duplicates:
        errors.append(f"{path} contains duplicate tokens: " + ", ".join(duplicates))


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



def _as_string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _flatten_string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_string_values(item))
        return flattened
    if isinstance(value, dict):
        flattened = []
        for key, item in value.items():
            flattened.append(str(key))
            flattened.extend(_flatten_string_values(item))
        return flattened
    return [str(value)]


def _canonical_read_only_authority_tokens(value: Any) -> set[str]:
    canonical: set[str] = set()
    for raw_item in _flatten_string_values(value):
        item = raw_item.strip().casefold().replace("-", "_").replace(" ", "_")
        if item in REQUIRED_READ_ONLY_FORBIDDEN_AUTHORITY:
            canonical.add(item)
            continue
        for alias, target in READ_ONLY_AUTHORITY_ALIASES.items():
            normalized_alias = alias.casefold().replace("-", "_").replace(" ", "_")
            if normalized_alias in item:
                canonical.add(target)
    return canonical


def _normalized_action_text(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _canonical_pr_action_tokens(value: Any) -> set[str]:
    canonical: set[str] = set()
    for raw_item in _flatten_string_values(value):
        item = _normalized_action_text(raw_item)
        if item in REQUIRED_PR_MUTATION_ACTIONS or item in REQUIRED_PR_READ_ONLY_ACTIONS:
            canonical.add(item)
            continue
        for alias, target in PR_MUTATION_ACTION_ALIASES.items():
            if _normalized_action_text(alias) in item:
                canonical.add(target)
        for alias, target in PR_READ_ONLY_ACTION_ALIASES.items():
            if _normalized_action_text(alias) in item:
                canonical.add(target)
    return canonical


def _pr_assignment_role(packet: dict[str, Any], guard: dict[str, Any]) -> str:
    role_fields = guard.get("assignment_role_fields", [])
    if not isinstance(role_fields, list):
        role_fields = sorted(REQUIRED_PR_ROLE_FIELDS)
    for field in role_fields:
        if isinstance(field, str) and isinstance(packet.get(field), str) and packet[field].strip():
            return packet[field].strip()
    return ""


def _pr_assignment_action_tokens(packet: dict[str, Any], guard: dict[str, Any]) -> set[str]:
    action_fields = guard.get("assignment_action_fields", [])
    if not isinstance(action_fields, list):
        action_fields = sorted(REQUIRED_PR_ACTION_FIELDS)
    tokens: set[str] = set()
    for field in action_fields:
        if isinstance(field, str) and field in packet:
            tokens.update(_canonical_pr_action_tokens(packet.get(field)))
    if packet.get("pull_request_mutation") is True:
        tokens.add("pull_request_mutation")
    if packet.get("github_pr_mutation") is True:
        tokens.add("pull_request_mutation")
    return tokens


def _is_pr_task(packet: dict[str, Any], action_tokens: set[str]) -> bool:
    if action_tokens:
        return True
    if packet.get("pr_task") is True or packet.get("github_pr_task") is True:
        return True
    for field in ("pull_request", "pull_request_id", "pull_request_number", "pr", "pr_id", "pr_number"):
        if field in packet:
            return True
    return False


def _is_read_only_reviewer_role(role: str, packet: dict[str, Any], guard: dict[str, Any]) -> bool:
    role_set = _as_string_set(guard.get("read_only_reviewer_roles"))
    read_only_names = _read_only_agent_names()
    normalized_role = role.casefold()
    if role in role_set:
        return True
    if role in read_only_names and "reviewer" in normalized_role:
        return True
    if packet.get("read_only_agent") is True and "reviewer" in normalized_role:
        return True
    if packet.get("sandbox_mode") == "read-only" and "reviewer" in normalized_role:
        return True
    if packet.get("agent_sandbox_mode") == "read-only" and "reviewer" in normalized_role:
        return True
    if packet.get("child_sandbox_mode") == "read-only" and "reviewer" in normalized_role:
        return True
    return False


def _is_governor_role(role: str, guard: dict[str, Any]) -> bool:
    role_set = _as_string_set(guard.get("governor_roles"))
    return role in role_set or "governor" in role.casefold()


def _governor_writer_lane_allows(
    role: str,
    action_tokens: set[str],
    packet: dict[str, Any],
    guard: dict[str, Any],
) -> bool:
    lane_id = packet.get("pr_writer_lane_id") or packet.get("writer_lane_id")
    if not isinstance(lane_id, str) or not lane_id.strip():
        return False
    lanes = guard.get("governor_writer_lanes")
    if not isinstance(lanes, list):
        return False
    for lane in lanes:
        if not isinstance(lane, dict) or lane.get("id") != lane_id:
            continue
        if lane.get("writable_pr_tasks") is not True:
            continue
        if role not in _as_string_set(lane.get("roles")):
            continue
        allowed_actions = _as_string_set(lane.get("allowed_actions"))
        if action_tokens and action_tokens <= allowed_actions:
            return True
    return False


def classify_pr_task_assignment(packet: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Classify PR assignment safety for reviewer and governor roles."""

    if not isinstance(packet, dict):
        return {
            "status": "PR_TASK_PACKET_INVALID",
            "reason": "packet_must_be_object",
            "blocked": True,
            "actions": [],
        }
    guard = policy.get("orchestration_model", {}).get("pr_task_role_action_guard")
    default_guard = {
        "assignment_action_fields": sorted(REQUIRED_PR_ACTION_FIELDS),
        "assignment_role_fields": sorted(REQUIRED_PR_ROLE_FIELDS),
    }
    effective_guard = guard if isinstance(guard, dict) else default_guard
    default_action_tokens = _pr_assignment_action_tokens(packet, effective_guard)
    if not _is_pr_task(packet, default_action_tokens):
        return {
            "status": PR_ALLOWED_STATUS,
            "reason": "not_pr_task",
            "blocked": False,
            "role": _pr_assignment_role(packet, effective_guard),
            "actions": sorted(default_action_tokens),
        }
    guard_errors = _validate_pr_task_role_action_guard(policy.get("orchestration_model", {}))
    if guard_errors:
        return {
            "status": "PR_TASK_GUARD_INVALID",
            "reason": "catalog_guard_invalid",
            "blocked": True,
            "actions": [],
        }
    role = _pr_assignment_role(packet, guard)
    action_tokens = _pr_assignment_action_tokens(packet, guard)
    mutation_actions = sorted(action_tokens & _as_string_set(guard.get("writable_pr_actions")))
    if not _is_pr_task(packet, action_tokens):
        return {
            "status": PR_ALLOWED_STATUS,
            "reason": "not_pr_task",
            "blocked": False,
            "role": role,
            "actions": sorted(action_tokens),
        }
    if mutation_actions and _is_read_only_reviewer_role(role, packet, guard):
        return {
            "status": PR_REVIEWER_MUTATION_STATUS,
            "reason": PR_REVIEWER_MUTATION_REASON,
            "blocked": True,
            "role": role,
            "actions": mutation_actions,
        }
    if mutation_actions and _is_governor_role(role, guard):
        if _governor_writer_lane_allows(role, set(mutation_actions), packet, guard):
            return {
                "status": PR_ALLOWED_STATUS,
                "reason": PR_ALLOWED_GOVERNOR_WRITER_REASON,
                "blocked": False,
                "role": role,
                "actions": mutation_actions,
            }
        return {
            "status": PR_GOVERNOR_MUTATION_STATUS,
            "reason": PR_GOVERNOR_MUTATION_REASON,
            "blocked": True,
            "role": role,
            "actions": mutation_actions,
        }
    return {
        "status": PR_ALLOWED_STATUS,
        "reason": PR_ALLOWED_READ_ONLY_REASON,
        "blocked": False,
        "role": role,
        "actions": sorted(action_tokens),
    }


def _normalized_role_profile_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().casefold().replace("_", "-")


def _ordered_unique_fields(*field_groups: Any) -> list[str]:
    ordered: list[str] = []
    for group in field_groups:
        if isinstance(group, (list, tuple, set)):
            iterable = group
        else:
            iterable = [group]
        for field in iterable:
            if isinstance(field, str) and field and field not in ordered:
                ordered.append(field)
    return ordered


def _first_packet_string(packet: dict[str, Any], fields: list[str] | set[str] | tuple[str, ...]) -> str:
    for field in _ordered_unique_fields(fields):
        value = packet.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _packet_string_values(packet: dict[str, Any], fields: list[str] | set[str] | tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for field in _ordered_unique_fields(fields):
        value = packet.get(field)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


def _is_bears_platform_role(value: Any) -> bool:
    token = _normalized_role_profile_token(value)
    return token.startswith("bears-") and token != "bears"


def _is_generic_fallback_agent_type(value: Any, guard: dict[str, Any]) -> bool:
    token = _normalized_role_profile_token(value)
    if not token:
        return False
    configured = {
        _normalized_role_profile_token(item)
        for item in _as_string_set(guard.get("generic_agent_types"))
    }
    if not configured:
        configured = {
            _normalized_role_profile_token(item)
            for item in REQUIRED_ROLE_PROFILE_FALLBACK_GENERIC_AGENT_TYPES
        }
    return token in configured


def _role_profile_fallback_guard(policy: dict[str, Any]) -> dict[str, Any]:
    guard = policy.get("orchestration_model", {}).get("role_profile_fallback_guard")
    return guard if isinstance(guard, dict) else {}


def _handoff_agent_type(packet: dict[str, Any], guard: dict[str, Any]) -> str:
    fields = _ordered_unique_fields(
        guard.get("fallback_agent_type_fields"),
        sorted(REQUIRED_ROLE_PROFILE_FALLBACK_AGENT_TYPE_FIELDS),
    )
    for value in _packet_string_values(packet, fields):
        if _is_generic_fallback_agent_type(value, guard):
            return value
    return _first_packet_string(packet, fields)


def _handoff_domain_owner(packet: dict[str, Any], guard: dict[str, Any]) -> str:
    domain_fields = _ordered_unique_fields(
        guard.get("domain_owner_fields"),
        sorted(REQUIRED_ROLE_PROFILE_FALLBACK_DOMAIN_OWNER_FIELDS),
    )
    for value in _packet_string_values(packet, domain_fields):
        if _is_bears_platform_role(value):
            return value
    agent_fields = _ordered_unique_fields(
        guard.get("fallback_agent_type_fields"),
        sorted(REQUIRED_ROLE_PROFILE_FALLBACK_AGENT_TYPE_FIELDS),
    )
    for value in _packet_string_values(packet, agent_fields):
        if _is_bears_platform_role(value):
            return value
    return _first_packet_string(packet, domain_fields)


def _is_implementation_handoff(packet: dict[str, Any], guard: dict[str, Any]) -> bool:
    if packet.get("implementation_handoff") is True or packet.get("implementation_task") is True:
        return True
    fields = set(REQUIRED_ROLE_PROFILE_FALLBACK_IMPLEMENTATION_FIELDS)
    fields.update(_as_string_set(guard.get("implementation_handoff_fields")))
    for field in sorted(fields):
        value = packet.get(field)
        if value is True:
            return True
        if field in {"write_scope", "target_write_paths"} and isinstance(value, list):
            return bool(value)
        if not isinstance(value, str):
            continue
        normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
        if "implementation" in normalized or normalized.startswith("implement"):
            return True
        if field in {"write_scope", "target_write_paths"} and normalized not in READ_ONLY_EMPTY_SCOPE_VALUES:
            return True
    return False


def _is_role_profile_fallback(packet: dict[str, Any], guard: dict[str, Any]) -> tuple[bool, str, str]:
    fallback_role = _handoff_agent_type(packet, guard)
    domain_owner = _handoff_domain_owner(packet, guard)
    if not _is_implementation_handoff(packet, guard):
        return False, fallback_role, domain_owner
    if not _is_generic_fallback_agent_type(fallback_role, guard):
        return False, fallback_role, domain_owner
    if not _is_bears_platform_role(domain_owner):
        return False, fallback_role, domain_owner
    return True, fallback_role, domain_owner


def _has_role_profile_downgrade_record(packet: dict[str, Any], guard: dict[str, Any]) -> bool:
    expected = guard.get("required_downgrade_record") or "ROLE_PROFILE_DOWNGRADE"
    if packet.get("role_profile_downgrade") == expected:
        return True
    record = packet.get("downgrade_record") or packet.get("role_profile_downgrade_record")
    if isinstance(record, dict):
        return record.get("type") == expected or record.get("status") == expected
    return False


def _has_explicit_operator_approval(packet: dict[str, Any]) -> bool:
    if packet.get("explicit_operator_approval") is True:
        return True
    approval = packet.get("operator_approval") or packet.get("role_profile_downgrade_approval")
    if not isinstance(approval, dict):
        return False
    return approval.get("approved") is True and isinstance(approval.get("approval_reference"), str) and bool(
        approval["approval_reference"].strip()
    )


def _has_valid_role_parity_packet(packet: dict[str, Any], fallback_role: str, domain_owner: str) -> bool:
    parity = packet.get("role_parity_packet") or packet.get("validated_role_parity_packet")
    if not isinstance(parity, dict):
        return False
    if REQUIRED_ROLE_PARITY_PACKET_FIELDS - set(parity):
        return False
    if parity.get("validated") is not True:
        return False
    if parity.get("developer_instructions_packet_attached") is not True:
        return False
    if parity.get("exact_role_profile_attached") is not True:
        return False
    if parity.get("role_gate_result_attached") is not True:
        return False
    if _normalized_role_profile_token(parity.get("fallback_agent_type")) != _normalized_role_profile_token(fallback_role):
        return False
    if _normalized_role_profile_token(parity.get("domain_owner")) != _normalized_role_profile_token(domain_owner):
        return False
    return True


def _role_profile_parity_is_approved(
    packet: dict[str, Any],
    guard: dict[str, Any],
    fallback_role: str,
    domain_owner: str,
) -> bool:
    if not _has_role_profile_downgrade_record(packet, guard):
        return False
    return _has_explicit_operator_approval(packet) or _has_valid_role_parity_packet(
        packet,
        fallback_role,
        domain_owner,
    )


def _mutation_authority_lane_allows(packet: dict[str, Any], mutation_actions: set[str]) -> bool:
    lane = packet.get("mutation_authority_lane") or packet.get("pr_mutation_authority_lane")
    if not isinstance(lane, dict):
        return False
    if lane.get("approved") is not True:
        return False
    if not isinstance(lane.get("lane_id"), str) or not lane["lane_id"].strip():
        return False
    if not isinstance(lane.get("approval_reference"), str) or not lane["approval_reference"].strip():
        return False
    approved_actions = _as_string_set(lane.get("approved_actions"))
    return bool(mutation_actions) and mutation_actions <= approved_actions


def classify_role_profile_fallback_assignment(
    packet: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Classify generic fallback for Bears implementation handoffs."""

    if not isinstance(packet, dict):
        return {
            "status": "ROLE_PROFILE_FALLBACK_PACKET_INVALID",
            "reason": "packet_must_be_object",
            "blocked": True,
            "fallback_role": "",
            "domain_owner": "",
            "actions": [],
        }
    guard = _role_profile_fallback_guard(policy)
    guard_errors = _validate_role_profile_fallback_guard(policy.get("orchestration_model", {}))
    if guard_errors:
        return {
            "status": "ROLE_PROFILE_FALLBACK_GUARD_INVALID",
            "reason": "catalog_guard_invalid",
            "blocked": True,
            "fallback_role": _handoff_agent_type(packet, guard),
            "domain_owner": _handoff_domain_owner(packet, guard),
            "actions": [],
        }
    is_fallback, fallback_role, domain_owner = _is_role_profile_fallback(packet, guard)
    if not is_fallback:
        return {
            "status": PR_ALLOWED_STATUS,
            "reason": ROLE_PROFILE_NOT_FALLBACK_REASON,
            "blocked": False,
            "fallback_role": fallback_role,
            "domain_owner": domain_owner,
            "actions": sorted(_pr_assignment_action_tokens(packet, policy["orchestration_model"]["pr_task_role_action_guard"])),
            "parity_enforcement": "not_required",
        }

    pr_guard = policy["orchestration_model"]["pr_task_role_action_guard"]
    mutation_actions = _pr_assignment_action_tokens(packet, pr_guard) & _as_string_set(
        pr_guard.get("writable_pr_actions")
    )
    parity_allowed = _role_profile_parity_is_approved(packet, guard, fallback_role, domain_owner)
    mutation_allowed = not mutation_actions or _mutation_authority_lane_allows(packet, mutation_actions)
    if not parity_allowed:
        return {
            "status": ROLE_PROFILE_DOWNGRADE_STATUS,
            "reason": ROLE_PROFILE_DOWNGRADE_REASON,
            "blocked": True,
            "mutation_blocked": bool(mutation_actions) and not mutation_allowed,
            "fallback_role": fallback_role,
            "domain_owner": domain_owner,
            "actions": sorted(mutation_actions),
            "parity_enforcement": "missing",
        }
    if not mutation_allowed:
        return {
            "status": GENERIC_FALLBACK_PR_MUTATION_STATUS,
            "reason": GENERIC_FALLBACK_PR_MUTATION_REASON,
            "blocked": True,
            "mutation_blocked": True,
            "fallback_role": fallback_role,
            "domain_owner": domain_owner,
            "actions": sorted(mutation_actions),
            "parity_enforcement": "recorded",
        }
    return {
        "status": PR_ALLOWED_STATUS,
        "reason": ROLE_PROFILE_FALLBACK_ALLOWED_REASON,
        "blocked": False,
        "mutation_blocked": False,
        "fallback_role": fallback_role,
        "domain_owner": domain_owner,
        "actions": sorted(mutation_actions),
        "parity_enforcement": "recorded",
    }


def validate_role_profile_fallback_packet(
    packet: dict[str, Any],
    policy: dict[str, Any],
    path: str = "role_profile_fallback_packet",
) -> list[str]:
    """Validate generic fallback for Bears implementation handoffs."""

    classification = classify_role_profile_fallback_assignment(packet, policy)
    if not classification.get("blocked"):
        return []
    errors = [
        f"{path}.role_profile_fallback_guard {classification['status']}: "
        f"{classification['reason']} fallback_role={classification.get('fallback_role', '')} "
        f"domain_owner={classification.get('domain_owner', '')}"
    ]
    if classification.get("mutation_blocked"):
        errors.append(
            f"{path}.role_profile_fallback_guard {GENERIC_FALLBACK_PR_MUTATION_STATUS}: "
            f"{GENERIC_FALLBACK_PR_MUTATION_REASON} actions="
            + ",".join(classification.get("actions", []))
        )
    return errors


def _missing_required_report_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return not bool(value)
    return False


def validate_role_profile_fallback_final_report_packet(
    packet: Any,
    policy: dict[str, Any],
    path: str = "role_profile_fallback_final_report",
) -> list[str]:
    """Validate final-report fields required by the role-profile fallback guard."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    guard = _role_profile_fallback_guard(policy)
    required_fields = _as_string_set(guard.get("final_report_required_fields"))
    if not required_fields:
        required_fields = set(REQUIRED_ROLE_PROFILE_FINAL_REPORT_FIELDS)
    for field in sorted(required_fields):
        if _missing_required_report_value(packet.get(field)):
            errors.append(f"{path} missing required final report field: {field}")
    return errors


def _is_read_only_scope_marker(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    allowed = {item.replace("-", "_").replace(" ", "_") for item in READ_ONLY_EMPTY_SCOPE_VALUES}
    return normalized in allowed


def _read_only_agent_names(agents_dir: Path | None = None) -> set[str]:
    directory = agents_dir or PLUGIN_ROOT / "agents"
    names: set[str] = set()
    if not directory.is_dir():
        return names
    for path in sorted(directory.glob("*.toml")):
        try:
            agent = load_toml(path)
        except Exception:
            continue
        if agent.get("sandbox_mode") == "read-only" and isinstance(agent.get("name"), str):
            names.add(agent["name"])
    return names


def _packet_has_any_field(packet: dict[str, Any], fields: tuple[str, ...] | set[str]) -> bool:
    for field in fields:
        value = packet.get(field)
        if value not in (None, "", [], {}):
            return True
    return False


def _packet_has_any_truthy(packet: dict[str, Any], fields: tuple[str, ...] | set[str]) -> bool:
    return any(packet.get(field) is True for field in fields)


def _packet_mentions_any(packet: dict[str, Any], markers: tuple[str, ...]) -> bool:
    lowered = _packet_text(packet).casefold()
    return any(marker in lowered for marker in markers)


def _is_current_day_checkpoint_packet(packet: dict[str, Any]) -> bool:
    if _packet_has_any_truthy(
        packet,
        {
            "current_day_collector",
            "current_day_monitor",
            "checkpoint_collector",
            "today_only",
            "today_only_task",
        },
    ):
        return True
    return _packet_mentions_any(packet, CURRENT_DAY_PACKET_MARKERS)


def _is_current_state_audit_packet(packet: dict[str, Any]) -> bool:
    if _packet_has_any_truthy(
        packet,
        {
            "current_state_audit",
            "final_audit",
            "final_state_audit",
            "closeout_audit",
        },
    ):
        return True
    return _packet_mentions_any(packet, CURRENT_STATE_PACKET_MARKERS)


def _has_session_checkpoint_scope(packet: dict[str, Any]) -> bool:
    if _packet_has_any_field(
        packet,
        {
            "session_checkpoints",
            "checkpoint_ranges",
            "line_checkpoints",
            "assigned_session_checkpoints",
        },
    ):
        return True
    evidence_scope = packet.get("evidence_scope")
    if isinstance(evidence_scope, dict):
        has_paths = _packet_has_any_field(evidence_scope, {"file_paths", "paths", "session_paths"})
        has_ranges = _packet_has_any_field(evidence_scope, {"line_ranges", "ranges", "checkpoints"})
        return has_paths and has_ranges
    return False


def _has_bounded_read_controls(packet: dict[str, Any]) -> bool:
    has_allowlist = _packet_has_any_field(
        packet,
        {
            "bounded_read_allowlist",
            "path_allowlist",
            "file_allowlist",
            "exact_file_list",
        },
    )
    has_output_cap = _packet_has_any_field(
        packet,
        {
            "max_output_lines",
            "max_output_bytes",
            "output_cap",
            "bounded_output",
        },
    )
    return has_allowlist and has_output_cap


def _current_state_claims_missing_source_authority(packet: dict[str, Any]) -> list[int]:
    claims = packet.get("claims")
    if isinstance(claims, list) and claims:
        missing: list[int] = []
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict) or not _packet_has_any_field(
                claim,
                CURRENT_STATE_CLAIM_AUTHORITY_FIELDS,
            ):
                missing.append(index)
        return missing
    return []


def _has_fresh_source_authority(packet: dict[str, Any]) -> bool:
    claims = packet.get("claims")
    if isinstance(claims, list) and claims:
        for claim in claims:
            if not isinstance(claim, dict):
                return False
            if not _packet_has_any_field(claim, CURRENT_STATE_CLAIM_AUTHORITY_FIELDS):
                return False
        return True
    if _packet_has_any_field(packet, CURRENT_STATE_AUTHORITY_FIELDS):
        return True
    return False


def validate_current_day_checkpoint_packet(
    packet: dict[str, Any],
    path: str = "current_day_checkpoint_packet",
) -> list[str]:
    """Validate current-day collector packets against explicit checkpoint scope."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]
    if not _is_current_day_checkpoint_packet(packet):
        return errors

    text = _packet_text(packet)
    if not _has_session_checkpoint_scope(packet):
        errors.append(
            f"{path}.session_checkpoints required for current-day checkpoint collectors"
        )
    if MEMORY_READ_RE.search(text) and packet.get("memory_correlation_explicitly_allowed") is not True:
        errors.append(
            f"{path}.memory_read SCOPE_EXPANSION_REQUIRED before reading memories"
        )
    if CURRENT_DAY_SESSION_SCAN_RE.search(text) and packet.get("bounded_uuid_lookup") is not True:
        errors.append(
            f"{path}.broad_session_scan SCOPE_EXPANSION_REQUIRED before broad session discovery"
        )
    if packet.get("evidence_scope") in (None, "", [], {}):
        errors.append(f"{path}.evidence_scope must list actual file paths and line ranges")
    return errors


def validate_current_state_audit_packet(
    packet: dict[str, Any],
    path: str = "current_state_audit_packet",
) -> list[str]:
    """Validate final/current-state audit packets against fresh source authority."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]
    if not _is_current_state_audit_packet(packet):
        return errors

    text = _packet_text(packet)
    has_memory = MEMORY_READ_RE.search(text) is not None
    locator_only = packet.get("memory_locator_only") is True
    if has_memory and not locator_only:
        errors.append(
            f"{path}.memory_read is not valid current-state evidence"
        )
    if has_memory and locator_only and not _has_fresh_source_authority(packet):
        errors.append(
            f"{path}.memory_locator_only requires fresh source proof"
        )
    if CURRENT_STATE_BROAD_SCAN_RE.search(text) and not _has_bounded_read_controls(packet):
        errors.append(
            f"{path}.broad_scan requires explicit file/path allowlist and output cap"
        )
    missing_claim_authority = _current_state_claims_missing_source_authority(packet)
    if missing_claim_authority:
        for claim_index in missing_claim_authority:
            errors.append(
                f"{path}.claims[{claim_index}].source_authority required per current-state claim"
            )
    elif not _has_fresh_source_authority(packet):
        errors.append(
            f"{path}.source_authority required per current-state claim"
        )
    return errors


def validate_design_artifact_contract(contract: Any, path: str = "design_artifact_contract") -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"{path} must be an object"]
    if contract.get("contract_id") != "issue-22-design-artifact-contract":
        errors.append(f"{path}.contract_id must be issue-22-design-artifact-contract")
    if contract.get("artifact_path") != DESIGN_ARTIFACT_PATH:
        errors.append(f"{path}.artifact_path must be {DESIGN_ARTIFACT_PATH}")
    required_before = contract.get("required_before")
    if not isinstance(required_before, str) or "plan" not in required_before or "tasks" not in required_before or "analyze" not in required_before or "implementation" not in required_before:
        errors.append(f"{path}.required_before must bind design before plan, tasks, analyze, and implementation")
    sections = contract.get("required_sections")
    if not isinstance(sections, list) or sections != list(REQUIRED_DESIGN_SECTIONS):
        errors.append(f"{path}.required_sections must match the issue #22 required section order")
    required_for = _as_string_set(contract.get("required_for"))
    missing_required_for = sorted(DESIGN_REQUIRED_CHANGE_TYPES - required_for)
    if missing_required_for:
        errors.append(f"{path}.required_for missing: " + ", ".join(missing_required_for))
    durable = contract.get("durable_artifact")
    if not isinstance(durable, dict):
        errors.append(f"{path}.durable_artifact must be an object")
    else:
        if "design.md" not in str(durable.get("with_spec_kit_packet", "")):
            errors.append(f"{path}.durable_artifact.with_spec_kit_packet must mention design.md")
        if "bounded section" not in str(durable.get("without_spec_kit_packet", "")):
            errors.append(f"{path}.durable_artifact.without_spec_kit_packet must mention bounded section")
    branch_fields = contract.get("branch_behavior_requires_matrix_when_any_present")
    if not isinstance(branch_fields, list) or set(branch_fields) != set(BRANCH_BEHAVIOR_FIELDS):
        errors.append(f"{path}.branch_behavior_requires_matrix_when_any_present must match branch behavior fields")
    skip_policy = contract.get("skip_policy")
    if not isinstance(skip_policy, dict):
        errors.append(f"{path}.skip_policy must be an object")
    else:
        for key in ("approved_skip", "narrow_bugfix_skip"):
            if not isinstance(skip_policy.get(key), dict):
                errors.append(f"{path}.skip_policy.{key} must be an object")
    packet = contract.get("implementation_packet")
    if not isinstance(packet, dict):
        errors.append(f"{path}.implementation_packet must be an object")
    else:
        fields = _as_string_set(packet.get("required_fields"))
        missing = sorted(REQUIRED_IMPLEMENTATION_PACKET_FIELDS - fields)
        if missing:
            errors.append(f"{path}.implementation_packet.required_fields missing: " + ", ".join(missing))
        if packet.get("rejection_status") != "DESIGN_ARTIFACT_REQUIRED":
            errors.append(f"{path}.implementation_packet.rejection_status must be DESIGN_ARTIFACT_REQUIRED")
    return errors


def validate_prototype_artifact_contract(contract: Any, path: str = "prototype_artifact_contract") -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"{path} must be an object"]
    if contract.get("contract_id") != PROTOTYPE_CONTRACT_ID:
        errors.append(f"{path}.contract_id must be {PROTOTYPE_CONTRACT_ID}")
    basenames = _as_string_set(contract.get("artifact_basenames"))
    if basenames != PROTOTYPE_ARTIFACT_BASENAMES:
        errors.append(f"{path}.artifact_basenames must be prototype.md and spike.md")
    sections = contract.get("required_sections")
    if not isinstance(sections, list) or sections != list(PROTOTYPE_REQUIRED_SECTIONS):
        errors.append(f"{path}.required_sections must match the issue #21 required section order")
    required_when = contract.get("required_when")
    if not isinstance(required_when, dict):
        errors.append(f"{path}.required_when must be an object")
    else:
        for field in PROTOTYPE_REQUIRED_UNCERTAINTY_FIELDS:
            if field not in required_when:
                errors.append(f"{path}.required_when missing {field}")
    skip_policy = contract.get("skip_policy")
    if not isinstance(skip_policy, dict):
        errors.append(f"{path}.skip_policy must be an object")
    else:
        for key in ("narrow_bugfix_skip", "already_proven_pattern_skip"):
            if not isinstance(skip_policy.get(key), dict):
                errors.append(f"{path}.skip_policy.{key} must be an object")
    safety = _as_string_set(contract.get("safety_rejections"))
    missing_safety = sorted(set(PROTOTYPE_SAFETY_FIELDS) - safety)
    if missing_safety:
        errors.append(f"{path}.safety_rejections missing: " + ", ".join(missing_safety))
    decisions = _as_string_set(contract.get("allowed_decisions"))
    if decisions != PROTOTYPE_DECISIONS:
        errors.append(f"{path}.allowed_decisions must be defer, kill, proceed, and redesign")
    review_gate = contract.get("review_gate")
    if not isinstance(review_gate, dict):
        errors.append(f"{path}.review_gate must be an object")
    else:
        triggers = _as_string_set(review_gate.get("operator_approval_required_when_any_remain"))
        missing = sorted(set(PROTOTYPE_REVIEW_CHANGE_FIELDS) - triggers)
        if missing:
            errors.append(f"{path}.review_gate.operator_approval_required_when_any_remain missing: " + ", ".join(missing))
    packet = contract.get("implementation_packet")
    if not isinstance(packet, dict):
        errors.append(f"{path}.implementation_packet must be an object")
    else:
        fields = _as_string_set(packet.get("required_fields"))
        missing = sorted(REQUIRED_IMPLEMENTATION_PACKET_FIELDS - fields)
        if missing:
            errors.append(f"{path}.implementation_packet.required_fields missing: " + ", ".join(missing))
        if packet.get("rejection_status") != "PROTOTYPE_ARTIFACT_REQUIRED":
            errors.append(f"{path}.implementation_packet.rejection_status must be PROTOTYPE_ARTIFACT_REQUIRED")
    return errors


def validate_research_artifact_contract(contract: Any, path: str = "research_artifact_contract") -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"{path} must be an object"]
    if contract.get("contract_id") != RESEARCH_CONTRACT_ID:
        errors.append(f"{path}.contract_id must be {RESEARCH_CONTRACT_ID}")
    basenames = contract.get("artifact_basenames")
    if not isinstance(basenames, dict):
        errors.append(f"{path}.artifact_basenames must be an object")
    else:
        for key, basename in RESEARCH_ARTIFACT_BASENAMES.items():
            if basenames.get(key) != basename:
                errors.append(f"{path}.artifact_basenames.{key} must be {basename}")
    sections = contract.get("required_sections")
    if not isinstance(sections, list) or sections != list(REQUIRED_RESEARCH_SECTIONS):
        errors.append(f"{path}.required_sections must match the issue #20 required section order")
    required_for = _as_string_set(contract.get("required_for"))
    missing_required_for = sorted(RESEARCH_REQUIRED_CHANGE_TYPES - required_for)
    if missing_required_for:
        errors.append(f"{path}.required_for missing: " + ", ".join(missing_required_for))
    tracks = _as_string_set(contract.get("required_tracks"))
    missing_tracks = sorted(REQUIRED_RESEARCH_TRACKS - tracks)
    if missing_tracks:
        errors.append(f"{path}.required_tracks missing: " + ", ".join(missing_tracks))
    if REQUIRED_UX_RESEARCH_TRACK not in tracks:
        errors.append(f"{path}.required_tracks missing: {REQUIRED_UX_RESEARCH_TRACK}")
    durable = contract.get("durable_artifact")
    if not isinstance(durable, dict):
        errors.append(f"{path}.durable_artifact must be an object")
    else:
        if not all(name in str(durable.get("with_spec_kit_packet", "")) for name in RESEARCH_ARTIFACT_BASENAMES.values()):
            errors.append(f"{path}.durable_artifact.with_spec_kit_packet must mention research.md, prior-art.md, and ux-research.md")
        if "bounded section" not in str(durable.get("without_spec_kit_packet", "")):
            errors.append(f"{path}.durable_artifact.without_spec_kit_packet must mention bounded section")
    skip_policy = contract.get("skip_policy")
    if not isinstance(skip_policy, dict):
        errors.append(f"{path}.skip_policy must be an object")
    else:
        for key in ("operator_skip", "narrow_exact_file_skip"):
            if not isinstance(skip_policy.get(key), dict):
                errors.append(f"{path}.skip_policy.{key} must be an object")
    bounded = contract.get("bounded_source_policy")
    if not isinstance(bounded, dict):
        errors.append(f"{path}.bounded_source_policy must be an object")
    else:
        if bounded.get("bounded_summaries_only") is not True:
            errors.append(f"{path}.bounded_source_policy.bounded_summaries_only must be true")
        if bounded.get("reject_large_source_copy") is not True:
            errors.append(f"{path}.bounded_source_policy.reject_large_source_copy must be true")
        if bounded.get("reject_proprietary_copy_claim") is not True:
            errors.append(f"{path}.bounded_source_policy.reject_proprietary_copy_claim must be true")
    packet = contract.get("implementation_packet")
    if not isinstance(packet, dict):
        errors.append(f"{path}.implementation_packet must be an object")
    else:
        fields = _as_string_set(packet.get("required_fields"))
        missing = sorted(REQUIRED_IMPLEMENTATION_PACKET_FIELDS - fields)
        if missing:
            errors.append(f"{path}.implementation_packet.required_fields missing: " + ", ".join(missing))
        if packet.get("rejection_status") != "RESEARCH_ARTIFACT_REQUIRED":
            errors.append(f"{path}.implementation_packet.rejection_status must be RESEARCH_ARTIFACT_REQUIRED")
    return errors


def _research_required(packet: dict[str, Any]) -> bool:
    change_type = packet.get("change_type")
    normalized_change = change_type.casefold() if isinstance(change_type, str) else ""
    return (
        packet.get("research_required") is True
        or normalized_change in RESEARCH_REQUIRED_CHANGE_TYPES
        or any(packet.get(field) is True for field in RESEARCH_REQUIRED_TRIGGER_FIELDS)
    )


def _ux_research_required(packet: dict[str, Any]) -> bool:
    change_type = packet.get("change_type")
    normalized_change = change_type.casefold() if isinstance(change_type, str) else ""
    return (
        normalized_change in {"ui", "ux", "ui/ux flow", "workflow", "workflow policy", "operator interaction", "developer interaction"}
        or any(packet.get(field) is True for field in UX_RESEARCH_TRIGGER_FIELDS)
    )


def _research_skip_valid(skip: Any) -> bool:
    if not isinstance(skip, dict):
        return False
    skip_type = skip.get("type")
    if skip_type == "operator_skip":
        return all(isinstance(skip.get(field), str) and skip[field].strip() for field in ("approved_by", "approval_reference", "reason"))
    if skip_type == "narrow_exact_file_skip":
        if not (isinstance(skip.get("exact_file_scope"), str) and skip["exact_file_scope"].strip()):
            return False
        return all(skip.get(field) is True for field in (
            "no_boundary_change",
            "no_runtime_change",
            "no_deploy_change",
            "no_restricted_data_change",
            "no_public_behavior_change",
            "no_workflow_change",
            "no_ui_change",
            "no_ux_change",
            "no_automation_pattern_change",
        ))
    return False


def _validate_research_artifact(name: str, artifact: Any, errors: list[str]) -> None:
    if not isinstance(artifact, dict):
        errors.append(f"implementation packet research_artifacts.{name} missing required artifact")
        return
    expected_basename = RESEARCH_ARTIFACT_BASENAMES[name]
    if not isinstance(artifact.get("path"), str) or Path(artifact["path"]).name != expected_basename:
        errors.append(f"implementation packet research_artifacts.{name}.path must end with {expected_basename}")
    sections = artifact.get("sections")
    if not isinstance(sections, list):
        errors.append(f"implementation packet research_artifacts.{name}.sections must be a list")
    else:
        missing_sections = [section for section in REQUIRED_RESEARCH_SECTIONS if section not in sections]
        if missing_sections:
            errors.append(f"implementation packet research_artifacts.{name}.sections missing: " + ", ".join(missing_sections))
    if not isinstance(artifact.get("decision_or_recommendation"), str) or not artifact["decision_or_recommendation"].strip():
        errors.append(f"implementation packet research_artifacts.{name}.decision_or_recommendation is required")
    if artifact.get("used_web_or_repository_research") is True:
        sources = artifact.get("sources")
        if not isinstance(sources, list) or not sources or not all(isinstance(source, str) and source.strip() for source in sources):
            errors.append(f"implementation packet research_artifacts.{name}.sources are required when web or repository research was used")
    for field in ("bounded_summary", "no_large_source_copy", "no_proprietary_copy"):
        if artifact.get(field) is not True:
            errors.append(f"implementation packet research_artifacts.{name}.{field} must be true")


def _validate_research_artifacts(packet: dict[str, Any], errors: list[str]) -> None:
    artifacts = packet.get("research_artifacts")
    if not isinstance(artifacts, dict):
        errors.append("implementation packet research_artifacts missing required artifacts")
        return
    for name in ("research", "prior_art"):
        _validate_research_artifact(name, artifacts.get(name), errors)
    if _ux_research_required(packet):
        _validate_research_artifact("ux_research", artifacts.get("ux_research"), errors)


def _design_skip_valid(skip: Any) -> bool:
    if not isinstance(skip, dict):
        return False
    skip_type = skip.get("type")
    if skip_type == "approved_skip":
        return all(isinstance(skip.get(field), str) and skip[field].strip() for field in ("approved_by", "approval_reference", "reason"))
    if skip_type == "narrow_bugfix_skip":
        if not (isinstance(skip.get("exact_file_scope"), str) and skip["exact_file_scope"].strip()):
            return False
        return all(skip.get(field) is True for field in (
            "no_boundary_change",
            "no_runtime_change",
            "no_deploy_change",
            "no_restricted_data_change",
            "no_public_behavior_change",
        ))
    return False


def _prototype_skip_valid(skip: Any) -> bool:
    if not isinstance(skip, dict):
        return False
    skip_type = skip.get("type")
    if skip_type == "narrow_bugfix_skip":
        if not (isinstance(skip.get("exact_file_scope"), str) and skip["exact_file_scope"].strip()):
            return False
        return all(skip.get(field) is True for field in (
            "no_boundary_change",
            "no_runtime_change",
            "no_deploy_change",
            "no_restricted_data_change",
            "no_public_behavior_change",
        ))
    if skip_type == "already_proven_pattern_skip":
        return all(isinstance(skip.get(field), str) and skip[field].strip() for field in (
            "pattern_reference",
            "evidence",
        ))
    return False


def _prototype_required(packet: dict[str, Any]) -> bool:
    return packet.get("prototype_required") is True or all(
        packet.get(field) is True for field in PROTOTYPE_REQUIRED_UNCERTAINTY_FIELDS
    )


def _prototype_artifact_basename_valid(path: Any) -> bool:
    return isinstance(path, str) and Path(path).name in PROTOTYPE_ARTIFACT_BASENAMES


def _validate_prototype_artifact(artifact: Any, errors: list[str]) -> None:
    if not isinstance(artifact, dict):
        errors.append("implementation packet prototype_artifact missing required artifact")
        return
    if not _prototype_artifact_basename_valid(artifact.get("path")):
        errors.append("implementation packet prototype_artifact.path must end with prototype.md or spike.md")
    sections = artifact.get("sections")
    if not isinstance(sections, list):
        errors.append("implementation packet prototype_artifact.sections must be a list")
    else:
        missing_sections = [section for section in PROTOTYPE_REQUIRED_SECTIONS if section not in sections]
        if missing_sections:
            errors.append("implementation packet prototype_artifact.sections missing: " + ", ".join(missing_sections))
    decision = artifact.get("decision")
    if decision not in PROTOTYPE_DECISIONS:
        errors.append("implementation packet prototype_artifact.decision must be proceed, redesign, defer, or kill")
    for field in PROTOTYPE_SAFETY_FIELDS:
        if artifact.get(field) is True:
            errors.append(f"implementation packet prototype_artifact.{field} is forbidden")
    if not artifact.get("cleanup_or_discard_requirements"):
        errors.append("implementation packet prototype_artifact.cleanup_or_discard_requirements is required")


def _validate_prototype_review(packet: dict[str, Any], errors: list[str]) -> None:
    material_change_remains = any(packet.get(field) is True for field in PROTOTYPE_REVIEW_CHANGE_FIELDS)
    if not material_change_remains:
        return
    review = packet.get("prototype_review")
    if not isinstance(review, dict):
        errors.append("implementation packet prototype_review requires operator approval for remaining material changes")
        return
    if review.get("operator_approved_to_implement") is not True:
        errors.append("implementation packet prototype_review.operator_approved_to_implement must be true")
    for field in ("approved_by", "approval_reference"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            errors.append(f"implementation packet prototype_review.{field} is required")


def validate_implementation_packet(packet: Any, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["implementation packet must be an object"]
    missing_fields = sorted(REQUIRED_IMPLEMENTATION_PACKET_FIELDS - set(packet))
    if missing_fields:
        errors.append("implementation packet missing fields: " + ", ".join(missing_fields))
    if _research_required(packet):
        if not _research_skip_valid(packet.get("research_skip")):
            _validate_research_artifacts(packet, errors)
    if _prototype_required(packet):
        if _prototype_skip_valid(packet.get("prototype_skip")):
            _validate_prototype_review(packet, errors)
        else:
            _validate_prototype_artifact(packet.get("prototype_artifact"), errors)
            _validate_prototype_review(packet, errors)
    elif isinstance(packet.get("prototype_artifact"), dict):
        _validate_prototype_artifact(packet.get("prototype_artifact"), errors)
    change_type = packet.get("change_type")
    design_required = packet.get("design_required") is True or change_type in DESIGN_REQUIRED_CHANGE_TYPES
    if not design_required:
        return errors
    if _design_skip_valid(packet.get("design_skip")):
        return errors
    artifact = packet.get("design_artifact")
    if not isinstance(artifact, dict):
        errors.append("implementation packet design_artifact missing required design")
        return errors
    if artifact.get("path") != DESIGN_ARTIFACT_PATH:
        errors.append(f"implementation packet design_artifact.path must be {DESIGN_ARTIFACT_PATH}")
    sections = artifact.get("sections")
    if not isinstance(sections, list):
        errors.append("implementation packet design_artifact.sections must be a list")
    else:
        missing_sections = [section for section in REQUIRED_DESIGN_SECTIONS if section not in sections]
        if missing_sections:
            errors.append("implementation packet design_artifact.sections missing: " + ", ".join(missing_sections))
    has_branch_behavior = any(bool(packet.get(field)) for field in BRANCH_BEHAVIOR_FIELDS)
    if has_branch_behavior and (not isinstance(sections, list) or "decision table or policy matrix" not in sections):
        errors.append("implementation packet branch behavior requires decision table or policy matrix")
    for field in ("affected_artifacts", "validator_impact", "documentation_impact", "test_plan", "safety_boundaries"):
        value = packet.get(field)
        if value in (None, "", []):
            errors.append(f"implementation packet {field} is required when design is required")
    return errors


def _validate_no_secret_like_text(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_text(policy):
        lower = text.casefold()
        if any(marker in lower for marker in SECRET_FIELD_MARKERS) and any(sep in text for sep in ("=", ":")):
            errors.append(f"{path}: policy text must not include secret-like key/value material")
    return errors


def _validate_no_forbidden_reasoning_effort(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                item_path = f"{path}.{key}"
                if key == "reasoning_effort":
                    if item in FORBIDDEN_REASONING_EFFORTS:
                        errors.append(f"{item_path} uses a forbidden reasoning effort value")
                    elif item not in ALLOWED_REASONING_EFFORTS:
                        errors.append(f"{item_path} must be medium or high")
                visit(item, item_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(policy, "policy")
    return errors


def _validate_agent_runtime_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runtime_policy = policy.get("agent_runtime_policy")
    if not _require_object(runtime_policy, "agent_runtime_policy", errors):
        return errors
    errors.extend(_validate_no_forbidden_reasoning_effort({"agent_runtime_policy": runtime_policy}))

    aliases = runtime_policy.get("codex_schema_value_aliases")
    if aliases != EXPECTED_CODEX_REASONING_ALIASES:
        errors.append("agent_runtime_policy.codex_schema_value_aliases must map operator_wording_middle to medium")

    main = runtime_policy.get("main_agent")
    if _require_object(main, "agent_runtime_policy.main_agent", errors):
        if main.get("model") != EXPECTED_AGENT_RUNTIME_POLICY["main_agent"]["model"]:
            errors.append("agent_runtime_policy.main_agent.model must be gpt-5.5")
        if main.get("reasoning_effort") != EXPECTED_AGENT_RUNTIME_POLICY["main_agent"]["reasoning_effort"]:
            errors.append("agent_runtime_policy.main_agent.reasoning_effort must be medium")

    delegated = runtime_policy.get("delegated_subagents")
    if _require_object(delegated, "agent_runtime_policy.delegated_subagents", errors):
        if delegated.get("model") != EXPECTED_AGENT_RUNTIME_POLICY["delegated_subagents"]["model"]:
            errors.append("agent_runtime_policy.delegated_subagents.model must be gpt-5.4-mini")
        if delegated.get("reasoning_effort") != EXPECTED_AGENT_RUNTIME_POLICY["delegated_subagents"]["reasoning_effort"]:
            errors.append("agent_runtime_policy.delegated_subagents.reasoning_effort must be medium")
        applies_to = delegated.get("applies_to")
        _require_list(applies_to, "agent_runtime_policy.delegated_subagents.applies_to", errors)
        if isinstance(applies_to, list):
            expected_applies_to = EXPECTED_AGENT_RUNTIME_POLICY["delegated_subagents"]["applies_to"]
            missing = sorted(expected_applies_to - set(applies_to))
            if missing:
                errors.append(
                    "agent_runtime_policy.delegated_subagents.applies_to missing: "
                    + ", ".join(missing)
                )
            unexpected = sorted(set(applies_to) - expected_applies_to)
            if unexpected:
                errors.append(
                    "agent_runtime_policy.delegated_subagents.applies_to unexpected: "
                    + ", ".join(unexpected)
                )

    evidence = runtime_policy.get("evidence_gathering_agents")
    if _require_object(evidence, "agent_runtime_policy.evidence_gathering_agents", errors):
        if evidence.get("model") != EXPECTED_AGENT_RUNTIME_POLICY["evidence_gathering_agents"]["model"]:
            errors.append("agent_runtime_policy.evidence_gathering_agents.model must be gpt-5.4-mini")
        if evidence.get("reasoning_effort") != EXPECTED_AGENT_RUNTIME_POLICY["evidence_gathering_agents"]["reasoning_effort"]:
            errors.append("agent_runtime_policy.evidence_gathering_agents.reasoning_effort must be medium")
        applies_to = evidence.get("applies_to")
        _require_list(applies_to, "agent_runtime_policy.evidence_gathering_agents.applies_to", errors)
        if isinstance(applies_to, list):
            expected_applies_to = EXPECTED_AGENT_RUNTIME_POLICY["evidence_gathering_agents"]["applies_to"]
            missing_applies_to = sorted(expected_applies_to - set(applies_to))
            if missing_applies_to:
                errors.append(
                    "agent_runtime_policy.evidence_gathering_agents.applies_to missing: "
                    + ", ".join(missing_applies_to)
                )
            unexpected_applies_to = sorted(set(applies_to) - expected_applies_to)
            if unexpected_applies_to:
                errors.append(
                    "agent_runtime_policy.evidence_gathering_agents.applies_to unexpected: "
                    + ", ".join(unexpected_applies_to)
                )
        roles = evidence.get("roles")
        _require_list(roles, "agent_runtime_policy.evidence_gathering_agents.roles", errors)
        if isinstance(roles, list):
            missing_roles = sorted(EXPECTED_AGENT_RUNTIME_POLICY["evidence_gathering_agents"]["roles"] - set(roles))
            if missing_roles:
                errors.append(
                    "agent_runtime_policy.evidence_gathering_agents.roles missing: "
                    + ", ".join(missing_roles)
                )
            unexpected_roles = sorted(set(roles) - EXPECTED_AGENT_RUNTIME_POLICY["evidence_gathering_agents"]["roles"])
            if unexpected_roles:
                errors.append(
                    "agent_runtime_policy.evidence_gathering_agents.roles unexpected: "
                    + ", ".join(unexpected_roles)
                )

    commit_local_validation = runtime_policy.get("commit_local_validation_test_closeout_lane")
    if _require_object(
        commit_local_validation,
        "agent_runtime_policy.commit_local_validation_test_closeout_lane",
        errors,
    ):
        expected_commit_local_validation = EXPECTED_AGENT_RUNTIME_POLICY["commit_local_validation_test_closeout_lane"]
        if commit_local_validation.get("model") != expected_commit_local_validation["model"]:
            errors.append("agent_runtime_policy.commit_local_validation_test_closeout_lane.model must be gpt-5.4-mini")
        if commit_local_validation.get("reasoning_effort") != expected_commit_local_validation["reasoning_effort"]:
            errors.append("agent_runtime_policy.commit_local_validation_test_closeout_lane.reasoning_effort must be high")
        if commit_local_validation.get("required_role_profile") != expected_commit_local_validation["required_role_profile"]:
            errors.append(
                "agent_runtime_policy.commit_local_validation_test_closeout_lane.required_role_profile "
                "must be bears-git-workflow-helper"
            )
        applies_to = commit_local_validation.get("applies_to")
        _require_list(
            applies_to,
            "agent_runtime_policy.commit_local_validation_test_closeout_lane.applies_to",
            errors,
        )
        if isinstance(applies_to, list):
            missing = sorted(expected_commit_local_validation["applies_to"] - set(applies_to))
            if missing:
                errors.append(
                    "agent_runtime_policy.commit_local_validation_test_closeout_lane.applies_to missing: "
                    + ", ".join(missing)
                )
    return errors


def _validate_non_product_post_task_audit(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    packet = policy.get("non_product_post_task_audit")
    if not isinstance(packet, dict):
        return ["non_product_post_task_audit must be an object"]

    applies_to = packet.get("applies_to")
    if not isinstance(applies_to, str) or "non-product" not in applies_to:
        errors.append("non_product_post_task_audit.applies_to must describe non-product scope")

    excluded = packet.get("excluded_scope_markers")
    if _require_list(
        excluded,
        "non_product_post_task_audit.excluded_scope_markers",
        errors,
    ):
        expected_markers = {"nearest product repo", "product AGENTS/SPEC/requirements"}
        missing_markers = [marker for marker in expected_markers if marker not in excluded]
        if missing_markers:
            errors.append(
                "non_product_post_task_audit.excluded_scope_markers missing: "
                + ", ".join(missing_markers)
            )

    audits = packet.get("required_subagents")
    if _require_list(
        audits,
        "non_product_post_task_audit.required_subagents",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        seen = {
            audit.get("id"): audit
            for audit in audits
            if isinstance(audit, dict) and isinstance(audit.get("id"), str)
        }
        missing = sorted(set(REQUIRED_POST_TASK_AUDITS) - set(seen))
        if missing:
            errors.append(
                "non_product_post_task_audit.required_subagents missing: "
                + ", ".join(missing)
            )
        for audit_id, expected_role in sorted(REQUIRED_POST_TASK_AUDITS.items()):
            audit = seen.get(audit_id)
            if not isinstance(audit, dict):
                continue
            if audit.get("role") != expected_role:
                errors.append(
                    f"post-task audit {audit_id} role must be {expected_role}"
                )
            if audit.get("spawn_fresh") is not True:
                errors.append(f"post-task audit {audit_id}.spawn_fresh must be true")
            if audit.get("inherit_parent_context") is not False:
                errors.append(
                    f"post-task audit {audit_id}.inherit_parent_context must be false"
                )
            for field in ("purpose", "must_answer", "allowed_writes", "closeout"):
                value = audit.get(field)
                if field == "purpose":
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"post-task audit {audit_id}.purpose must be non-empty")
                else:
                    _require_list(
                        value,
                        f"post-task audit {audit_id}.{field}",
                        errors,
                    )

    destinations = packet.get("user_information_destinations")
    if _require_object(
        destinations,
        "non_product_post_task_audit.user_information_destinations",
        errors,
    ):
        required_destinations = {
            "plugin_workflow_rule": "plugins/bears",
            "workspace_boundary_fact": "/srv/bears",
            "runtime_or_deploy_fact": "infra",
            "product_behavior_fact": "product repo",
        }
        for key, expected_fragment in required_destinations.items():
            value = destinations.get(key)
            if not isinstance(value, str) or expected_fragment not in value:
                errors.append(
                    "non_product_post_task_audit.user_information_destinations."
                    f"{key} must mention {expected_fragment}"
                )

    closeout = packet.get("closeout_requirements")
    _require_list(
        closeout,
        "non_product_post_task_audit.closeout_requirements",
        errors,
    )
    return errors


def _validate_no_subagent_decision_entry(entry: dict[str, Any], errors: list[str]) -> None:
    """Validate one no-subagent mode decision row."""
    case_id = entry.get("id")
    if case_id in NO_SUBAGENT_ALLOWED_CASES:
        expected = NO_SUBAGENT_ALLOWED_CASES[case_id]
        if entry.get("decision") != "allowed_no_subagent_mode":
            errors.append(f"no_subagent_mode decision {case_id}.decision must be allowed_no_subagent_mode")
        for field, expected_value in expected.items():
            if entry.get(field) != expected_value:
                errors.append(
                    f"no_subagent_mode decision {case_id}.{field} must be {expected_value}"
                )
        if entry.get("role_gate") != "apply_when_required":
            errors.append(f"no_subagent_mode decision {case_id}.role_gate must be apply_when_required")
        if case_id == "small-exact-file-bugfix-policy-exception":
            required_policy = entry.get("required_existing_policy")
            if required_policy != "small exact-file bugfix exception":
                errors.append(
                    "no_subagent_mode decision small-exact-file-bugfix-policy-exception."
                    "required_existing_policy must be small exact-file bugfix exception"
                )
        return

    if case_id in NO_SUBAGENT_BLOCKED_CASES:
        expected_result = NO_SUBAGENT_BLOCKED_CASES[case_id]
        if entry.get("decision") != "blocked_no_subagent_mode":
            errors.append(f"no_subagent_mode decision {case_id}.decision must be blocked_no_subagent_mode")
        if entry.get("required_result") != expected_result:
            errors.append(f"no_subagent_mode decision {case_id}.required_result must be {expected_result}")
        if entry.get("role_gate") != "apply_when_required":
            errors.append(f"no_subagent_mode decision {case_id}.role_gate must be apply_when_required")
        return

    errors.append(f"no_subagent_mode decision has unexpected id: {case_id!r}")


def _validate_no_subagent_mode(orchestration: dict[str, Any]) -> list[str]:
    """Validate the bounded no-subagent mode policy table."""
    errors: list[str] = []
    mode = orchestration.get("no_subagent_mode")
    if not _require_object(mode, "orchestration_model.no_subagent_mode", errors):
        return errors
    if mode.get("enabled") is not True:
        errors.append("orchestration_model.no_subagent_mode.enabled must be true")
    if mode.get("parent_instruction_rule") != "nearest_role_instructions_still_apply":
        errors.append(
            "orchestration_model.no_subagent_mode.parent_instruction_rule must be "
            "nearest_role_instructions_still_apply"
        )
    if mode.get("role_gate_rule") != "required_role_gate_still_applies":
        errors.append(
            "orchestration_model.no_subagent_mode.role_gate_rule must be "
            "required_role_gate_still_applies"
        )
    if mode.get("mutation_upgrade_rule") != "upgrade_to_normal_gated_mode_before_write":
        errors.append(
            "orchestration_model.no_subagent_mode.mutation_upgrade_rule must be "
            "upgrade_to_normal_gated_mode_before_write"
        )
    if mode.get("read_only_audit_rule") != "do_not_run_non_product_audit_subagents":
        errors.append(
            "orchestration_model.no_subagent_mode.read_only_audit_rule must be "
            "do_not_run_non_product_audit_subagents"
        )

    rules = mode.get("required_rules")
    if _require_list(rules, "orchestration_model.no_subagent_mode.required_rules", errors):
        missing_rules = [rule for rule in NO_SUBAGENT_REQUIRED_RULES if rule not in rules]
        if missing_rules:
            errors.append(
                "orchestration_model.no_subagent_mode.required_rules missing: "
                + ", ".join(missing_rules)
            )

    table = mode.get("decision_table")
    if _require_list(
        table,
        "orchestration_model.no_subagent_mode.decision_table",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        seen_ids = {
            entry.get("id")
            for entry in table
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        expected_ids = set(NO_SUBAGENT_ALLOWED_CASES) | set(NO_SUBAGENT_BLOCKED_CASES)
        missing = sorted(expected_ids - seen_ids)
        extra = sorted(seen_ids - expected_ids)
        if missing:
            errors.append(
                "orchestration_model.no_subagent_mode.decision_table missing: "
                + ", ".join(missing)
            )
        if extra:
            errors.append(
                "orchestration_model.no_subagent_mode.decision_table unexpected: "
                + ", ".join(extra)
            )
        for entry in table:
            if isinstance(entry, dict):
                _validate_no_subagent_decision_entry(entry, errors)

    return errors


def _validate_hook_result_schema(schema: Any, errors: list[str]) -> None:
    if not _require_object(
        schema,
        "orchestration_model.validation_hook_runner.result_schema",
        errors,
    ):
        return
    required_fields = schema.get("required_fields")
    if _require_list(
        required_fields,
        "orchestration_model.validation_hook_runner.result_schema.required_fields",
        errors,
    ):
        missing = [
            field for field in REQUIRED_HOOK_RESULT_FIELDS
            if field not in required_fields
        ]
        if missing:
            errors.append(
                "orchestration_model.validation_hook_runner.result_schema."
                "required_fields missing: " + ", ".join(missing)
            )
    forbidden_fields = _as_string_set(schema.get("forbidden_fields"))
    missing_forbidden = sorted(REQUIRED_HOOK_FORBIDDEN_RESULT_FIELDS - forbidden_fields)
    if missing_forbidden:
        errors.append(
            "orchestration_model.validation_hook_runner.result_schema."
            "forbidden_fields missing: " + ", ".join(missing_forbidden)
        )


def _validate_validation_hook_runner(orchestration: dict[str, Any]) -> list[str]:
    """Validate the governed hook allowlist for plugin control checks."""
    errors: list[str] = []
    runner = orchestration.get("validation_hook_runner")
    if not _require_object(
        runner,
        "orchestration_model.validation_hook_runner",
        errors,
    ):
        return errors

    if runner.get("required") is not True:
        errors.append("orchestration_model.validation_hook_runner.required must be true")
    if runner.get("request_model") != "named_hook_only":
        errors.append(
            "orchestration_model.validation_hook_runner.request_model must be "
            "named_hook_only"
        )
    if runner.get("cwd_policy") != "plugin_root_only":
        errors.append(
            "orchestration_model.validation_hook_runner.cwd_policy must be "
            "plugin_root_only"
        )
    controls = runner.get("controls")
    if _require_list(
        controls,
        "orchestration_model.validation_hook_runner.controls",
        errors,
    ):
        for control in ("run_validators", "close"):
            if control not in controls:
                errors.append(
                    "orchestration_model.validation_hook_runner.controls missing "
                    + control
                )
    output_modes = runner.get("allowed_output_modes")
    if _require_list(
        output_modes,
        "orchestration_model.validation_hook_runner.allowed_output_modes",
        errors,
    ):
        for mode in ("bounded_json", "concise_text"):
            if mode not in output_modes:
                errors.append(
                    "orchestration_model.validation_hook_runner."
                    "allowed_output_modes missing " + mode
                )
    forbidden_request_kinds = _as_string_set(runner.get("forbidden_request_kinds"))
    missing_request_kinds = sorted(
        REQUIRED_HOOK_FORBIDDEN_REQUEST_KINDS - forbidden_request_kinds
    )
    if missing_request_kinds:
        errors.append(
            "orchestration_model.validation_hook_runner.forbidden_request_kinds "
            "missing: " + ", ".join(missing_request_kinds)
        )

    _validate_hook_result_schema(runner.get("result_schema"), errors)

    hooks = runner.get("allowed_hooks")
    if not _require_list(
        hooks,
        "orchestration_model.validation_hook_runner.allowed_hooks",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        return errors

    seen_ids = [
        hook.get("hook_id")
        for hook in hooks
        if isinstance(hook, dict) and isinstance(hook.get("hook_id"), str)
    ]
    duplicate_ids = sorted({hook_id for hook_id in seen_ids if seen_ids.count(hook_id) > 1})
    if duplicate_ids:
        errors.append(
            "orchestration_model.validation_hook_runner.allowed_hooks duplicate "
            "hook_id: " + ", ".join(duplicate_ids)
        )
    actual_ids = set(seen_ids)
    missing_ids = sorted(set(REQUIRED_VALIDATION_HOOKS) - actual_ids)
    extra_ids = sorted(actual_ids - set(REQUIRED_VALIDATION_HOOKS))
    if missing_ids:
        errors.append(
            "orchestration_model.validation_hook_runner.allowed_hooks missing: "
            + ", ".join(missing_ids)
        )
    if extra_ids:
        errors.append(
            "orchestration_model.validation_hook_runner.allowed_hooks unexpected: "
            + ", ".join(extra_ids)
        )

    command_ids = [
        hook.get("command_id")
        for hook in hooks
        if isinstance(hook, dict) and isinstance(hook.get("command_id"), str)
    ]
    duplicate_command_ids = sorted(
        {command_id for command_id in command_ids if command_ids.count(command_id) > 1}
    )
    if duplicate_command_ids:
        errors.append(
            "orchestration_model.validation_hook_runner.allowed_hooks duplicate "
            "command_id: " + ", ".join(duplicate_command_ids)
        )

    for hook in hooks:
        if not isinstance(hook, dict):
            continue
        hook_id = hook.get("hook_id")
        expected = REQUIRED_VALIDATION_HOOKS.get(hook_id)
        if expected is None:
            continue
        path = f"validation hook {hook_id}"
        if hook.get("command_id") != expected["command_id"]:
            errors.append(f"{path}.command_id must be {expected['command_id']}")
        script = hook.get("script")
        if script != expected["script"]:
            errors.append(f"{path}.script must be {expected['script']}")
        elif script == "python3":
            pass
        elif not script.startswith("scripts/") or not script.endswith(".py"):
            errors.append(f"{path}.script must be a repo-local Python script")
        elif not (PLUGIN_ROOT / script).is_file():
            errors.append(f"{path}.script does not exist: {script}")
        args = hook.get("args")
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            errors.append(f"{path}.args must be a string list")
        else:
            actual_args = tuple(args)
            if actual_args != expected["args"]:
                errors.append(f"{path}.args must be {list(expected['args'])}")
            forbidden_args = sorted(set(args) & FORBIDDEN_HOOK_ARG_TOKENS)
            if forbidden_args:
                errors.append(
                    f"{path}.args contains forbidden shell token: "
                    + ", ".join(forbidden_args)
                )
            target_marker_present = "{validation_target}" in args
            if target_marker_present != expected["target_required"]:
                errors.append(
                    f"{path}.args validation_target marker must match target_required"
                )
        if hook.get("target_required") is not expected["target_required"]:
            errors.append(f"{path}.target_required must be {expected['target_required']}")

    return errors


def _validate_parent_control_lane(orchestration: dict[str, Any]) -> list[str]:
    """Validate the parent control lane under orchestration-only mode."""
    errors: list[str] = []
    lane = orchestration.get("parent_control_lane")
    if not _require_object(lane, "orchestration_model.parent_control_lane", errors):
        return errors
    if lane.get("enabled") is not True:
        errors.append("orchestration_model.parent_control_lane.enabled must be true")
    if lane.get("lane_id") != "parent_control_lane":
        errors.append(
            "orchestration_model.parent_control_lane.lane_id must be parent_control_lane"
        )
    if lane.get("mode") != "orchestration_control_only":
        errors.append(
            "orchestration_model.parent_control_lane.mode must be "
            "orchestration_control_only"
        )
    if lane.get("action_policy_reference") != "main_agent_action_policy":
        errors.append(
            "orchestration_model.parent_control_lane.action_policy_reference must be "
            "main_agent_action_policy"
        )
    if lane.get("implementation_authority") != "forbidden":
        errors.append(
            "orchestration_model.parent_control_lane.implementation_authority must be "
            "forbidden"
        )
    _validate_exact_string_tokens(
        lane.get("allowed_control_actions"),
        "orchestration_model.parent_control_lane.allowed_control_actions",
        expected=REQUIRED_PARENT_CONTROL_ALLOWED_ACTIONS,
        errors=errors,
    )
    _validate_exact_string_tokens(
        lane.get("forbidden_control_actions"),
        "orchestration_model.parent_control_lane.forbidden_control_actions",
        expected=REQUIRED_PARENT_CONTROL_FORBIDDEN_ACTIONS,
        errors=errors,
    )

    status_policy = lane.get("status_output_policy")
    if _require_object(
        status_policy,
        "orchestration_model.parent_control_lane.status_output_policy",
        errors,
    ):
        for field in ("exit_codes_allowed", "bounded_summaries_allowed", "changed_file_names_allowed"):
            if status_policy.get(field) is not True:
                errors.append(
                    "orchestration_model.parent_control_lane.status_output_policy."
                    f"{field} must be true"
                )
        if status_policy.get("file_content_collection") != "forbidden":
            errors.append(
                "orchestration_model.parent_control_lane.status_output_policy."
                "file_content_collection must be forbidden"
            )

    github_policy = lane.get("github_policy")
    if _require_object(
        github_policy,
        "orchestration_model.parent_control_lane.github_policy",
        errors,
    ):
        if github_policy.get("planning_issue_mutation") != "operator_requested_only":
            errors.append(
                "orchestration_model.parent_control_lane.github_policy."
                "planning_issue_mutation must be operator_requested_only"
            )
        if github_policy.get("pull_request_mutation") != "forbidden_without_explicit_operator_request":
            errors.append(
                "orchestration_model.parent_control_lane.github_policy."
                "pull_request_mutation must be forbidden_without_explicit_operator_request"
            )

    restricted_policy = lane.get("restricted_data_policy")
    if _require_object(
        restricted_policy,
        "orchestration_model.parent_control_lane.restricted_data_policy",
        errors,
    ):
        blocked_reads = _as_string_set(restricted_policy.get("blocked_reads"))
        missing_reads = sorted(REQUIRED_PARENT_CONTROL_RESTRICTED_READS - blocked_reads)
        if missing_reads:
            errors.append(
                "orchestration_model.parent_control_lane.restricted_data_policy."
                "blocked_reads missing: " + ", ".join(missing_reads)
            )

    return errors


def validate_validation_hook_result(
    result: Any,
    policy: dict[str, Any],
    path: str = "validation hook result",
) -> list[str]:
    """Validate one bounded hook result packet."""
    errors: list[str] = []
    if not isinstance(result, dict):
        return [f"{path} must be an object"]

    runner = policy.get("orchestration_model", {}).get("validation_hook_runner", {})
    if not isinstance(runner, dict):
        return ["policy orchestration_model.validation_hook_runner must be an object"]
    hooks = runner.get("allowed_hooks", [])
    hook_by_id = {
        hook.get("hook_id"): hook
        for hook in hooks
        if isinstance(hook, dict) and isinstance(hook.get("hook_id"), str)
    }

    for field in REQUIRED_HOOK_RESULT_FIELDS:
        value = result.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"{path} missing required field: {field}")

    hook_id = result.get("hook_id")
    hook = hook_by_id.get(hook_id)
    if not isinstance(hook, dict):
        errors.append(f"{path}.hook_id {hook_id!r} is not allowed")
    elif result.get("command_id") != hook.get("command_id"):
        errors.append(
            f"{path}.command_id must match hook {hook_id}: {hook.get('command_id')}"
        )

    if runner.get("cwd_policy") == "plugin_root_only" and result.get("cwd") != str(PLUGIN_ROOT):
        errors.append(f"{path}.cwd must be {PLUGIN_ROOT}")
    if not isinstance(result.get("exit_code"), int):
        errors.append(f"{path}.exit_code must be an integer")
    if not isinstance(result.get("sanitized_summary"), str) or not result.get("sanitized_summary", "").strip():
        errors.append(f"{path}.sanitized_summary must be non-empty text")

    forbidden_fields = _as_string_set(
        runner.get("result_schema", {}).get("forbidden_fields")
        if isinstance(runner.get("result_schema"), dict)
        else []
    )
    forbidden_present = sorted(field for field in result if field in forbidden_fields)
    if forbidden_present:
        errors.append(
            f"{path} contains forbidden fields: " + ", ".join(forbidden_present)
        )
    for text_path, text in _iter_text(result, path):
        lower = text.casefold()
        if any(marker in lower for marker in SECRET_FIELD_MARKERS) and any(sep in text for sep in ("=", ":")):
            errors.append(f"{text_path}: hook result must not include secret-like key/value material")

    return errors


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_non_empty_text(value: Any, path: str, errors: list[str]) -> None:
    if not _has_text(value):
        errors.append(f"{path} must be non-empty text")


def _require_non_empty_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{path} must be a non-empty list")
        return
    for index, item in enumerate(value):
        if not _has_text(item):
            errors.append(f"{path}[{index}] must be non-empty text")


def _validate_spec_kit_binding(binding: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(binding, dict):
        return [f"{path} must be an object"]

    has_path_binding = all(_has_text(binding.get(field)) for field in SUBAGENT_REQUIRED_SPEC_KIT_BINDING_PATH_FIELDS)
    if has_path_binding:
        for field, basename in SUBAGENT_REQUIRED_SPEC_KIT_BINDING_PATH_FIELDS.items():
            value = str(binding.get(field))
            if Path(value).name != basename:
                errors.append(f"{path}.{field} must point to {basename}")
        return errors

    has_feature_binding = all(_has_text(binding.get(field)) for field in SUBAGENT_REQUIRED_SPEC_KIT_BINDING_FEATURE_FIELDS)
    if has_feature_binding:
        expected_files = {
            "spec_file": "spec.md",
            "plan_file": "plan.md",
            "tasks_file": "tasks.md",
        }
        for field, expected in expected_files.items():
            if binding.get(field) != expected:
                errors.append(f"{path}.{field} must be {expected}")
        return errors

    errors.append(
        f"{path} must include spec_md_path, plan_md_path, tasks_md_path "
        "or feature_dir with spec_file, plan_file, tasks_file"
    )
    return errors


def _validate_speckit_analyze_evidence(evidence: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return [f"{path} must be an object"]
    status = evidence.get("status") or evidence.get("result")
    if status != "PASS":
        errors.append(f"{path}.status must be PASS")
    artifact = evidence.get("artifact_ref") or evidence.get("path")
    if not _has_text(artifact):
        errors.append(f"{path}.artifact_ref must be non-empty text")
    elif Path(str(artifact)).name != "speckit-analyze.json":
        errors.append(f"{path}.artifact_ref must point to speckit-analyze.json")
    return errors


def _validate_expected_executable_proof(proof: Any, path: str) -> list[str]:
    errors: list[str] = []
    proofs = proof if isinstance(proof, list) else [proof]
    if not proofs or proofs == [None]:
        return [f"{path} must be a non-empty object or list"]
    for index, item in enumerate(proofs):
        item_path = f"{path}[{index}]" if isinstance(proof, list) else path
        if not isinstance(item, dict):
            errors.append(f"{item_path} must be an object")
            continue
        _require_non_empty_text(item.get("proof_type"), f"{item_path}.proof_type", errors)
        if not any(
            _has_text(item.get(field))
            for field in (
                "proof_command",
                "validator_subcommand",
                "artifact_ref",
                "schema_packet_ref",
                "status_packet_ref",
            )
        ):
            errors.append(
                f"{item_path} must include proof_command, validator_subcommand, "
                "artifact_ref, schema_packet_ref, or status_packet_ref"
            )
    return errors


def _validate_reviewer_lane(packet: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    lane = packet.get("lane_mode")
    if lane not in SUBAGENT_REVIEWER_LANE_MODES:
        return [f"{path}.lane_mode must be advisory_async or blocking_gate for reviewer assignments"]

    if lane == "advisory_async":
        if packet.get("wait_budget_seconds") != 0:
            errors.append(f"{path}.wait_budget_seconds must be 0 for advisory_async")
        if packet.get("hard_stop_reason") != "none":
            errors.append(f"{path}.hard_stop_reason must be none for advisory_async")
        return errors

    reason = packet.get("hard_stop_reason")
    if reason not in SUBAGENT_BLOCKING_GATE_HARD_STOP_REASONS:
        errors.append(f"{path}.hard_stop_reason is not an allowed blocking_gate hard-stop reason")
    timeout = packet.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout <= 0:
        errors.append(f"{path}.timeout_seconds must be a positive integer for blocking_gate")
    _require_non_empty_text(packet.get("expected_closeout_artifact"), f"{path}.expected_closeout_artifact", errors)
    _require_non_empty_text(packet.get("fallback_action"), f"{path}.fallback_action", errors)
    _require_non_empty_text(packet.get("blocking_condition"), f"{path}.blocking_condition", errors)
    return errors


def validate_subagent_speckit_assignment_packet(
    packet: dict[str, Any],
    path: str = "subagent_speckit_assignment_packet",
) -> list[str]:
    """Validate a worker or reviewer assignment packet against executable Spec Kit gates."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]

    _require_non_empty_text(packet.get("assignment_packet_id"), f"{path}.assignment_packet_id", errors)
    lane = packet.get("agent_lane")
    if lane not in SUBAGENT_EXECUTABLE_ASSIGNMENT_LANES:
        errors.append(f"{path}.agent_lane must be worker or reviewer")

    errors.extend(_validate_spec_kit_binding(packet.get("spec_kit_binding"), f"{path}.spec_kit_binding"))
    errors.extend(_validate_speckit_analyze_evidence(packet.get("speckit_analyze"), f"{path}.speckit_analyze"))
    _require_non_empty_list(packet.get("source_task_ids"), f"{path}.source_task_ids", errors)
    _require_non_empty_list(packet.get("rule_coverage_ids"), f"{path}.rule_coverage_ids", errors)
    _require_non_empty_list(packet.get("validator_subcommands"), f"{path}.validator_subcommands", errors)
    errors.extend(
        _validate_expected_executable_proof(
            packet.get("expected_executable_proof"),
            f"{path}.expected_executable_proof",
        )
    )
    if packet.get("restricted_data_status") != "clean":
        errors.append(f"{path}.restricted_data_status must be clean")
    if lane == "reviewer":
        errors.extend(_validate_reviewer_lane(packet, path))
    return errors


def _validate_validator_exit_codes(exit_codes: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(exit_codes, dict):
        items = list(exit_codes.items())
    elif isinstance(exit_codes, list):
        items = [(str(index), item) for index, item in enumerate(exit_codes)]
    else:
        return [f"{path} must be an object or list"]
    if not items:
        errors.append(f"{path} must not be empty")
    for key, value in items:
        if not isinstance(value, int):
            errors.append(f"{path}.{key} must be an integer exit code")
    return errors


def _validate_schema_or_status_refs(packet: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    schema_refs = packet.get("schema_packet_refs")
    status_refs = packet.get("status_packet_refs")
    has_schema = isinstance(schema_refs, list) and bool(schema_refs)
    has_status = isinstance(status_refs, list) and bool(status_refs)
    if not has_schema and not has_status:
        errors.append(f"{path} must include schema_packet_refs or status_packet_refs")
    if has_schema:
        _require_non_empty_list(schema_refs, f"{path}.schema_packet_refs", errors)
    if has_status:
        _require_non_empty_list(status_refs, f"{path}.status_packet_refs", errors)
    return errors


def _validate_no_forbidden_acceptance_evidence(packet: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    for text_path, value in _iter_text(packet, path):
        lowered = value.casefold()
        for marker in SUBAGENT_FORBIDDEN_ACCEPTANCE_EVIDENCE:
            if marker in lowered:
                errors.append(f"{text_path} uses forbidden acceptance evidence: {marker}")
    return errors


def _validate_stale_result_rejection(packet: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    stale = packet.get("stale_result_rejection")
    if not isinstance(stale, dict):
        return [f"{path}.stale_result_rejection must be an object"]
    missing = sorted(field for field in SUBAGENT_REQUIRED_STALE_RESULT_REJECTION_FIELDS if stale.get(field) in (None, "", []))
    if missing:
        errors.append(f"{path}.stale_result_rejection missing required fields: " + ", ".join(missing))
    if stale.get("status") != "checked":
        errors.append(f"{path}.stale_result_rejection.status must be checked")
    if stale.get("stale_result") is not False:
        errors.append(f"{path}.stale_result_rejection.stale_result must be false")
    if stale.get("assignment_packet_id") not in (None, packet.get("assignment_packet_id")):
        errors.append(f"{path}.stale_result_rejection.assignment_packet_id must match assignment_packet_id")
    return errors


def validate_subagent_speckit_closeout_packet(
    packet: dict[str, Any],
    path: str = "subagent_speckit_closeout_packet",
) -> list[str]:
    """Validate a worker or reviewer closeout/result packet against executable proof gates."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]

    if not (_has_text(packet.get("closeout_packet_id")) or _has_text(packet.get("result_packet_id"))):
        errors.append(f"{path} must include closeout_packet_id or result_packet_id")
    _require_non_empty_text(packet.get("assignment_packet_id"), f"{path}.assignment_packet_id", errors)
    _require_non_empty_list(packet.get("rule_coverage_ids"), f"{path}.rule_coverage_ids", errors)
    _require_non_empty_list(packet.get("executable_proof_refs"), f"{path}.executable_proof_refs", errors)
    errors.extend(_validate_validator_exit_codes(packet.get("validator_exit_codes"), f"{path}.validator_exit_codes"))
    errors.extend(_validate_schema_or_status_refs(packet, path))
    errors.extend(_validate_stale_result_rejection(packet, path))
    errors.extend(_validate_no_forbidden_acceptance_evidence(packet, path))

    if packet.get("restricted_data_status") != "clean":
        errors.append(f"{path}.restricted_data_status must be clean")

    lane = packet.get("lane_mode")
    if lane == "reviewer":
        errors.append(f"{path}.lane_mode must be advisory_async or blocking_gate, not reviewer")
    elif lane in SUBAGENT_REVIEWER_LANE_MODES:
        errors.extend(_validate_reviewer_lane(packet, path))
    elif lane is not None and lane != "worker":
        errors.append(f"{path}.lane_mode must be worker, advisory_async, or blocking_gate")
    return errors


def _validate_compact_continuation_packet(packet: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]
    missing = sorted(field for field in REQUIRED_CONTINUATION_PACKET_FIELDS if not packet.get(field) and field != "restricted_data_taint")
    if "restricted_data_taint" not in packet:
        missing.append("restricted_data_taint")
    if missing:
        errors.append(f"{path} missing required fields: " + ", ".join(missing))
    forbidden = sorted(field for field in packet if field in REQUIRED_CONTINUATION_FORBIDDEN_FIELDS)
    if forbidden:
        errors.append(f"{path} contains forbidden fields: " + ", ".join(forbidden))
    if packet.get("restricted_data_taint") is not False:
        errors.append(f"{path}.restricted_data_taint must be false")
    return errors


def _validate_session_runtime_validation(packet: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]
    if packet.get("command") != REQUIRED_SESSION_RUNTIME_VALIDATION_COMMAND:
        errors.append(f"{path}.command must be the session runtime validation command")
    if packet.get("exit_code") != 0:
        errors.append(f"{path}.exit_code must be 0")
    if packet.get("compatibility_status") != "compatible":
        errors.append(f"{path}.compatibility_status must be compatible")
    if not isinstance(packet.get("runtime_dir"), str) or not packet.get("runtime_dir"):
        errors.append(f"{path}.runtime_dir must be non-empty text")
    return errors


def validate_worker_pool_policy(pool: Any, path: str = "orchestration_model.worker_pool_policy") -> list[str]:
    errors: list[str] = []
    if not isinstance(pool, dict):
        return [f"{path} must be an object"]

    hard_max = pool.get("hard_max_active_subagents")
    default_active = pool.get("default_active_executing_subagents")
    if hard_max != 100:
        errors.append(f"{path}.hard_max_active_subagents must be 100")
    if not isinstance(default_active, int):
        errors.append(f"{path}.default_active_executing_subagents must be an integer")
    elif default_active >= 100:
        errors.append(
            f"{path}.default_active_executing_subagents must be lower than hard_max_active_subagents"
        )
    elif default_active < 1:
        errors.append(f"{path}.default_active_executing_subagents must be positive")
    if pool.get("default_cap_applies_to") != "actively_executing_workers_only":
        errors.append(f"{path}.default_cap_applies_to must be actively_executing_workers_only")
    if pool.get("warm_reusable_workers_count_against_default_active_cap") is not False:
        errors.append(
            f"{path}.warm_reusable_workers_count_against_default_active_cap must be false"
        )
    precondition = pool.get("reuse_or_fork_session_runtime_precondition")
    if not isinstance(precondition, dict):
        errors.append(f"{path}.reuse_or_fork_session_runtime_precondition must be an object")
    else:
        if precondition.get("command") != REQUIRED_SESSION_RUNTIME_VALIDATION_COMMAND:
            errors.append(
                f"{path}.reuse_or_fork_session_runtime_precondition.command must be the session runtime validation command"
            )
        required_before = _as_string_set(precondition.get("required_before"))
        if required_before != {"session reuse", "session fork"}:
            errors.append(
                f"{path}.reuse_or_fork_session_runtime_precondition.required_before must include session reuse and session fork"
            )
        fallback = str(precondition.get("on_compatibility_failure", ""))
        if "spawn fresh session" not in fallback or "bounded prior evidence" not in fallback:
            errors.append(
                f"{path}.reuse_or_fork_session_runtime_precondition.on_compatibility_failure must require fresh session with bounded prior evidence"
            )
    hard_max_semantics = pool.get("hard_max_semantics")
    if not isinstance(hard_max_semantics, str) or "absolute safety cap" not in hard_max_semantics or "normal active target" not in hard_max_semantics:
        errors.append(f"{path}.hard_max_semantics must state absolute safety cap and not normal active target")

    states = pool.get("worker_states")
    if _require_list(states, f"{path}.worker_states", errors, item_type=dict, item_label="objects"):
        seen_states = {
            state.get("state")
            for state in states
            if isinstance(state, dict) and isinstance(state.get("state"), str)
        }
        missing_states = sorted(REQUIRED_WORKER_POOL_STATES - seen_states)
        if missing_states:
            errors.append(f"{path}.worker_states missing: " + ", ".join(missing_states))

    reuse = _as_string_set(pool.get("reuse_required_all"))
    missing_reuse = sorted(REQUIRED_WORKER_POOL_REUSE_REQUIREMENTS - reuse)
    if missing_reuse:
        errors.append(f"{path}.reuse_required_all missing: " + ", ".join(missing_reuse))

    if "equal to or narrower" not in str(pool.get("compatible_write_scope_rule", "")):
        errors.append(f"{path}.compatible_write_scope_rule must require equal to or narrower scope")

    continuation = pool.get("compact_continuation_packet")
    if not isinstance(continuation, dict):
        errors.append(f"{path}.compact_continuation_packet must be an object")
    else:
        if continuation.get("required") is not True:
            errors.append(f"{path}.compact_continuation_packet.required must be true")
        fields = _as_string_set(continuation.get("required_fields"))
        missing_fields = sorted(REQUIRED_CONTINUATION_PACKET_FIELDS - fields)
        if missing_fields:
            errors.append(
                f"{path}.compact_continuation_packet.required_fields missing: "
                + ", ".join(missing_fields)
            )
        forbidden_fields = _as_string_set(continuation.get("forbidden_fields"))
        missing_forbidden = sorted(REQUIRED_CONTINUATION_FORBIDDEN_FIELDS - forbidden_fields)
        if missing_forbidden:
            errors.append(
                f"{path}.compact_continuation_packet.forbidden_fields missing: "
                + ", ".join(missing_forbidden)
            )

    fresh = pool.get("fresh_required_lanes")
    if not isinstance(fresh, dict):
        errors.append(f"{path}.fresh_required_lanes must be an object")
    else:
        if fresh.get("when_inherit_parent_context_is_false") != "fresh-required":
            errors.append(
                f"{path}.fresh_required_lanes.when_inherit_parent_context_is_false must be fresh-required"
            )
        if fresh.get("reuse") != "forbidden":
            errors.append(f"{path}.fresh_required_lanes.reuse must be forbidden")
        if fresh.get("parent_context") != "forbidden":
            errors.append(f"{path}.fresh_required_lanes.parent_context must be forbidden")
        applies_to = _as_string_set(fresh.get("applies_to"))
        missing_audits = sorted(set(REQUIRED_POST_TASK_AUDITS) - applies_to)
        if missing_audits:
            errors.append(f"{path}.fresh_required_lanes.applies_to missing: " + ", ".join(missing_audits))

    stale_conditions = _as_string_set(pool.get("stale_worker_close_conditions"))
    missing_stale = sorted(REQUIRED_STALE_WORKER_CLOSE_CONDITIONS - stale_conditions)
    if missing_stale:
        errors.append(f"{path}.stale_worker_close_conditions missing: " + ", ".join(missing_stale))

    return errors


def validate_worker_reuse_request(
    request: dict[str, Any],
    policy: dict[str, Any],
    path: str = "worker reuse request",
) -> list[str]:
    """Validate one worker reuse decision packet."""
    errors: list[str] = []
    pool = policy.get("orchestration_model", {}).get("worker_pool_policy", {})
    if validate_worker_pool_policy(pool):
        return ["worker pool policy is invalid"]

    if request.get("lane_inherit_parent_context") is False:
        if request.get("requested_worker_state") != "fresh-required":
            errors.append(f"{path}.requested_worker_state must be fresh-required")
        if request.get("reuse_requested") is not False:
            errors.append(f"{path}.reuse_requested must be false for fresh-required lanes")
        if request.get("parent_context_attached") is not False:
            errors.append(f"{path}.parent_context_attached must be false for fresh-required lanes")
        return errors

    if request.get("reuse_requested") is not True:
        return errors

    if request.get("worker_state") != "reusable":
        errors.append(f"{path}.worker_state must be reusable")
    if request.get("worker_role") != request.get("requested_role"):
        errors.append(f"{path} requires same_role")
    if request.get("worker_repo_boundary") != request.get("requested_repo_boundary"):
        errors.append(f"{path} requires same_repo_boundary")
    if request.get("write_scope_compatible") is not True:
        errors.append(f"{path} requires compatible_write_scope")
    if request.get("restricted_data_taint") is not False:
        errors.append(f"{path} requires no_restricted_data_taint")
    errors.extend(
        _validate_session_runtime_validation(
            request.get("session_runtime_validation"),
            f"{path}.session_runtime_validation",
        )
    )
    errors.extend(
        _validate_compact_continuation_packet(
            request.get("compact_continuation_packet"),
            f"{path}.compact_continuation_packet",
        )
    )
    return errors


def validate_read_only_assignment_packet(
    packet: dict[str, Any],
    policy: dict[str, Any],
    path: str = "read_only_assignment_packet",
) -> list[str]:
    """Validate one assignment packet against the read-only agent safety guard."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return [f"{path} must be an object"]
    errors.extend(validate_current_day_checkpoint_packet(packet, path))
    errors.extend(validate_current_state_audit_packet(packet, path))

    guard = policy.get("orchestration_model", {}).get("read_only_agent_safety_guard")
    guard_errors = _validate_read_only_agent_safety_guard(
        policy.get("orchestration_model", {}),
        include_agent_files=False,
    )
    if guard_errors:
        return ["read_only_agent_safety_guard is invalid before assignment validation"]

    if "role_profile_fallback_guard" in policy.get("orchestration_model", {}):
        errors.extend(validate_role_profile_fallback_packet(packet, policy, path))

    pr_task_classification = classify_pr_task_assignment(packet, policy)
    if pr_task_classification.get("blocked") is True:
        errors.append(
            f"{path}.pr_task_role_action_guard {pr_task_classification['status']}: "
            f"{pr_task_classification['reason']}"
        )

    read_only_modes = set(guard.get("read_only_sandbox_modes", []))
    role = packet.get("child_role") or packet.get("agent_role") or packet.get("role")
    agent_name = packet.get("agent_name") or role
    sandbox_mode = (
        packet.get("child_sandbox_mode")
        or packet.get("agent_sandbox_mode")
        or packet.get("sandbox_mode")
    )
    read_only_names = _read_only_agent_names()
    is_read_only_assignment = (
        packet.get("read_only_agent") is True
        or sandbox_mode in read_only_modes
        or (isinstance(agent_name, str) and agent_name in read_only_names)
    )
    if not is_read_only_assignment:
        return errors

    for field in sorted(READ_ONLY_ASSIGNMENT_AUTHORITY_FIELDS):
        tokens = _canonical_read_only_authority_tokens(packet.get(field))
        if tokens:
            errors.append(
                f"{path}.{field} grants forbidden read-only authority: "
                + ", ".join(sorted(tokens))
            )

    for field in sorted(READ_ONLY_MUTABLE_ASSIGNMENT_FIELDS):
        value = packet.get(field)
        if value is None:
            continue
        values = [item.strip().casefold() for item in _flatten_string_values(value)]
        has_mutable_scope = any(item not in READ_ONLY_EMPTY_SCOPE_VALUES for item in values)
        if has_mutable_scope:
            errors.append(f"{path}.{field} must be empty for read-only agents")

    parent_override = (
        packet.get("parent_live_sandbox_override")
        or packet.get("parent_sandbox_override")
        or packet.get("parent_sandbox_mode")
    )
    widening_modes = {"workspace-write", "danger-full-access"}
    if parent_override in widening_modes:
        allowed_policy_allowances = set(
            guard.get("parent_live_sandbox_override", {}).get("allowed_policy_allowances", [])
            if isinstance(guard.get("parent_live_sandbox_override"), dict)
            else []
        )
        requested_allowance = packet.get("explicit_bears_policy_allowance_id")
        boolean_allowance = packet.get("explicit_bears_policy_allowance")
        if not allowed_policy_allowances:
            errors.append(
                f"{path}.parent_live_sandbox_override cannot widen a read-only child; "
                "policy allows no read-only widening allowances"
            )
        elif boolean_allowance is not True or requested_allowance not in allowed_policy_allowances:
            errors.append(
                f"{path}.parent_live_sandbox_override cannot widen a read-only child "
                "without a named Bears policy allowance"
            )

    if packet.get("audit_subagent") is True:
        if packet.get("reuse_requested") is True:
            errors.append(f"{path}.reuse_requested must be false for audit subagents")
        if packet.get("assigned_to_writable_task") is True:
            errors.append(f"{path}.assigned_to_writable_task is blocked for audit subagents")

    if packet.get("read_only_safety_claim") is True:
        evidence_command = packet.get("validator_evidence_command")
        expected = guard["validator_command"]
        if evidence_command != expected:
            errors.append(
                f"{path}.validator_evidence_command must be {expected!r} "
                "when read_only_safety_claim is true"
            )

    return errors


def _validate_read_only_agent_files(agents_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    directory = agents_dir or PLUGIN_ROOT / "agents"
    if not directory.is_dir():
        return [f"{directory} must exist for read-only agent safety validation"]
    for path in sorted(directory.glob("*.toml")):
        try:
            agent = load_toml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.relative_to(PLUGIN_ROOT)} cannot be parsed: {exc}")
            continue
        if agent.get("sandbox_mode") != "read-only":
            continue
        display_path = str(path.relative_to(PLUGIN_ROOT))
        instructions = agent.get("developer_instructions")
        if not isinstance(instructions, str):
            errors.append(f"{display_path}.developer_instructions must be a string")
            continue
        required_markers = (
            "sandbox_mode is not authority proof",
            "READ_ONLY_ASSIGNMENT_BLOCKED",
            "audit subagent sessions cannot be reused for writable tasks",
        )
        for marker in required_markers:
            if marker not in instructions:
                errors.append(f"{display_path} missing read-only safety marker: {marker}")
        synthetic_packet = {
            "agent_name": agent.get("name"),
            "sandbox_mode": "read-only",
            "read_only_safety_claim": True,
            "validator_evidence_command": "python3 scripts/subagent_orchestration_policy.py validate",
        }
        synthetic_policy = {
            "orchestration_model": {
                "read_only_agent_safety_guard": {
                    "required": True,
                    "validator_command": "python3 scripts/subagent_orchestration_policy.py validate",
                    "read_only_sandbox_modes": ["read-only"],
                    "forbidden_authority_tokens": sorted(REQUIRED_READ_ONLY_FORBIDDEN_AUTHORITY),
                    "mutable_assignment_fields": sorted(READ_ONLY_MUTABLE_ASSIGNMENT_FIELDS),
                    "sandbox_mode_is_not_authority_proof": True,
                    "parent_live_sandbox_override": {
                        "may_widen_child_read_only_assignment": False,
                        "explicit_policy_allowance_required": True,
                    },
                    "audit_subagent_reuse": {
                        "fresh_required": True,
                        "writable_task_reuse": "blocked",
                    },
                    "stage_boundary_audit_wording": "sandbox_mode is not sufficient proof by itself",
                    "documentation": {
                        "active_validation_command": "python3 scripts/subagent_orchestration_policy.py validate"
                    },
                }
            }
        }
        errors.extend(validate_read_only_assignment_packet(synthetic_packet, synthetic_policy, display_path))
    return errors


def _validate_read_only_agent_safety_guard(
    orchestration: dict[str, Any],
    *,
    include_agent_files: bool = True,
) -> list[str]:
    errors: list[str] = []
    guard = orchestration.get("read_only_agent_safety_guard")
    if not _require_object(
        guard,
        "orchestration_model.read_only_agent_safety_guard",
        errors,
    ):
        return errors
    if guard.get("required") is not True:
        errors.append("orchestration_model.read_only_agent_safety_guard.required must be true")
    expected_command = "python3 scripts/subagent_orchestration_policy.py validate"
    if guard.get("validator_command") != expected_command:
        errors.append(
            "orchestration_model.read_only_agent_safety_guard.validator_command "
            f"must be {expected_command}"
        )
    if guard.get("sandbox_mode_is_not_authority_proof") is not True:
        errors.append(
            "orchestration_model.read_only_agent_safety_guard."
            "sandbox_mode_is_not_authority_proof must be true"
        )
    if set(guard.get("read_only_sandbox_modes", [])) != {"read-only"}:
        errors.append(
            "orchestration_model.read_only_agent_safety_guard.read_only_sandbox_modes "
            "must be ['read-only']"
        )
    missing_forbidden = sorted(
        REQUIRED_READ_ONLY_FORBIDDEN_AUTHORITY
        - _as_string_set(guard.get("forbidden_authority_tokens"))
    )
    if missing_forbidden:
        errors.append(
            "orchestration_model.read_only_agent_safety_guard."
            "forbidden_authority_tokens missing: "
            + ", ".join(missing_forbidden)
        )
    missing_mutable_fields = sorted(
        READ_ONLY_MUTABLE_ASSIGNMENT_FIELDS
        - _as_string_set(guard.get("mutable_assignment_fields"))
    )
    if missing_mutable_fields:
        errors.append(
            "orchestration_model.read_only_agent_safety_guard."
            "mutable_assignment_fields missing: "
            + ", ".join(missing_mutable_fields)
        )
    parent_override = guard.get("parent_live_sandbox_override")
    if _require_object(
        parent_override,
        "orchestration_model.read_only_agent_safety_guard.parent_live_sandbox_override",
        errors,
    ):
        if parent_override.get("may_widen_child_read_only_assignment") is not False:
            errors.append(
                "orchestration_model.read_only_agent_safety_guard."
                "parent_live_sandbox_override.may_widen_child_read_only_assignment "
                "must be false"
            )
        if parent_override.get("explicit_policy_allowance_required") is not True:
            errors.append(
                "orchestration_model.read_only_agent_safety_guard."
                "parent_live_sandbox_override.explicit_policy_allowance_required "
                "must be true"
            )
    audit_reuse = guard.get("audit_subagent_reuse")
    if _require_object(
        audit_reuse,
        "orchestration_model.read_only_agent_safety_guard.audit_subagent_reuse",
        errors,
    ):
        if audit_reuse.get("fresh_required") is not True:
            errors.append(
                "orchestration_model.read_only_agent_safety_guard."
                "audit_subagent_reuse.fresh_required must be true"
            )
        if audit_reuse.get("writable_task_reuse") != "blocked":
            errors.append(
                "orchestration_model.read_only_agent_safety_guard."
                "audit_subagent_reuse.writable_task_reuse must be blocked"
            )
    wording = guard.get("stage_boundary_audit_wording")
    if not isinstance(wording, str) or "sandbox_mode" not in wording or "not sufficient proof by itself" not in wording:
        errors.append(
            "orchestration_model.read_only_agent_safety_guard."
            "stage_boundary_audit_wording must state sandbox_mode is not sufficient "
            "proof by itself"
        )
    documentation = guard.get("documentation")
    if _require_object(
        documentation,
        "orchestration_model.read_only_agent_safety_guard.documentation",
        errors,
    ):
        if documentation.get("active_validation_command") != expected_command:
            errors.append(
                "orchestration_model.read_only_agent_safety_guard.documentation."
                f"active_validation_command must be {expected_command}"
            )
    if include_agent_files:
        errors.extend(_validate_read_only_agent_files())
    return errors


def _validate_pr_task_role_action_guard(orchestration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    guard = orchestration.get("pr_task_role_action_guard")
    if not _require_object(
        guard,
        "orchestration_model.pr_task_role_action_guard",
        errors,
    ):
        return errors
    expected_command = "python3 scripts/subagent_orchestration_policy.py validate"
    if guard.get("required") is not True:
        errors.append("orchestration_model.pr_task_role_action_guard.required must be true")
    if guard.get("validator_command") != expected_command:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.validator_command "
            f"must be {expected_command}"
        )
    if guard.get("fail_closed_by_default") is not True:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.fail_closed_by_default must be true"
        )
    missing_roles = sorted(
        {"bears-platform-security-reviewer"} - _as_string_set(guard.get("read_only_reviewer_roles"))
    )
    if missing_roles:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.read_only_reviewer_roles missing: "
            + ", ".join(missing_roles)
        )
    missing_governors = sorted(
        {"bears-platform-role-governor", "bears-plugin-constitution-governor"}
        - _as_string_set(guard.get("governor_roles"))
    )
    if missing_governors:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.governor_roles missing: "
            + ", ".join(missing_governors)
        )
    missing_role_fields = sorted(
        REQUIRED_PR_ROLE_FIELDS - _as_string_set(guard.get("assignment_role_fields"))
    )
    if missing_role_fields:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.assignment_role_fields missing: "
            + ", ".join(missing_role_fields)
        )
    missing_action_fields = sorted(
        REQUIRED_PR_ACTION_FIELDS - _as_string_set(guard.get("assignment_action_fields"))
    )
    if missing_action_fields:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.assignment_action_fields missing: "
            + ", ".join(missing_action_fields)
        )
    missing_mutations = sorted(
        REQUIRED_PR_MUTATION_ACTIONS - _as_string_set(guard.get("writable_pr_actions"))
    )
    if missing_mutations:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.writable_pr_actions missing: "
            + ", ".join(missing_mutations)
        )
    missing_read_actions = sorted(
        REQUIRED_PR_READ_ONLY_ACTIONS - _as_string_set(guard.get("read_only_pr_actions"))
    )
    if missing_read_actions:
        errors.append(
            "orchestration_model.pr_task_role_action_guard.read_only_pr_actions missing: "
            + ", ".join(missing_read_actions)
        )
    status_reasons = guard.get("status_reasons")
    if _require_list(
        status_reasons,
        "orchestration_model.pr_task_role_action_guard.status_reasons",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        found_status_reasons = {
            (item.get("status"), item.get("reason"))
            for item in status_reasons
            if isinstance(item, dict)
        }
        missing_status_reasons = sorted(REQUIRED_PR_STATUS_REASONS - found_status_reasons)
        if missing_status_reasons:
            errors.append(
                "orchestration_model.pr_task_role_action_guard.status_reasons missing: "
                + ", ".join(f"{status}:{reason}" for status, reason in missing_status_reasons)
            )
    writer_lanes = guard.get("governor_writer_lanes")
    if _require_list(
        writer_lanes,
        "orchestration_model.pr_task_role_action_guard.governor_writer_lanes",
        errors,
        non_empty=False,
        item_type=dict,
        item_label="objects",
    ):
        governor_roles = _as_string_set(guard.get("governor_roles"))
        writable_actions = _as_string_set(guard.get("writable_pr_actions"))
        for index, lane in enumerate(writer_lanes):
            lane_path = f"orchestration_model.pr_task_role_action_guard.governor_writer_lanes[{index}]"
            lane_id = lane.get("id")
            if not isinstance(lane_id, str) or not lane_id.strip():
                errors.append(f"{lane_path}.id must be a non-empty string")
            if lane.get("writable_pr_tasks") is not True:
                errors.append(f"{lane_path}.writable_pr_tasks must be true")
            lane_roles = _as_string_set(lane.get("roles"))
            if not lane_roles:
                errors.append(f"{lane_path}.roles must name governor roles")
            invalid_roles = sorted(lane_roles - governor_roles)
            if invalid_roles:
                errors.append(f"{lane_path}.roles contains non-governor roles: " + ", ".join(invalid_roles))
            lane_actions = _as_string_set(lane.get("allowed_actions"))
            if not lane_actions:
                errors.append(f"{lane_path}.allowed_actions must name writable PR actions")
            invalid_actions = sorted(lane_actions - writable_actions)
            if invalid_actions:
                errors.append(f"{lane_path}.allowed_actions contains unknown actions: " + ", ".join(invalid_actions))
            if not isinstance(lane.get("policy_reference"), str) or not lane["policy_reference"].strip():
                errors.append(f"{lane_path}.policy_reference must be a non-empty string")
    documentation = guard.get("documentation")
    if _require_object(
        documentation,
        "orchestration_model.pr_task_role_action_guard.documentation",
        errors,
    ):
        if documentation.get("active_validation_command") != expected_command:
            errors.append(
                "orchestration_model.pr_task_role_action_guard.documentation."
                f"active_validation_command must be {expected_command}"
            )
    return errors


def _validate_role_profile_fallback_guard(orchestration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    guard = orchestration.get("role_profile_fallback_guard")
    if not _require_object(
        guard,
        "orchestration_model.role_profile_fallback_guard",
        errors,
    ):
        return errors
    expected_command = "python3 scripts/subagent_orchestration_policy.py validate"
    if guard.get("required") is not True:
        errors.append("orchestration_model.role_profile_fallback_guard.required must be true")
    if guard.get("validator_command") != expected_command:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.validator_command "
            f"must be {expected_command}"
        )
    if guard.get("fail_closed_by_default") is not True:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.fail_closed_by_default must be true"
        )
    for field, marker in (
        ("model_fallback_definition", "Bears role profile stays attached"),
        ("role_profile_fallback_definition", "generic role"),
    ):
        value = guard.get(field)
        if not isinstance(value, str) or marker not in value:
            errors.append(
                f"orchestration_model.role_profile_fallback_guard.{field} must document {marker}"
            )
    missing_generic = sorted(
        REQUIRED_ROLE_PROFILE_FALLBACK_GENERIC_AGENT_TYPES
        - _as_string_set(guard.get("generic_agent_types"))
    )
    if missing_generic:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.generic_agent_types missing: "
            + ", ".join(missing_generic)
        )
    missing_agent_fields = sorted(
        REQUIRED_ROLE_PROFILE_FALLBACK_AGENT_TYPE_FIELDS
        - _as_string_set(guard.get("fallback_agent_type_fields"))
    )
    if missing_agent_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.fallback_agent_type_fields missing: "
            + ", ".join(missing_agent_fields)
        )
    missing_owner_fields = sorted(
        REQUIRED_ROLE_PROFILE_FALLBACK_DOMAIN_OWNER_FIELDS
        - _as_string_set(guard.get("domain_owner_fields"))
    )
    if missing_owner_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.domain_owner_fields missing: "
            + ", ".join(missing_owner_fields)
        )
    missing_implementation_fields = sorted(
        REQUIRED_ROLE_PROFILE_FALLBACK_IMPLEMENTATION_FIELDS
        - _as_string_set(guard.get("implementation_handoff_fields"))
    )
    if missing_implementation_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.implementation_handoff_fields missing: "
            + ", ".join(missing_implementation_fields)
        )
    if guard.get("required_downgrade_record") != "ROLE_PROFILE_DOWNGRADE":
        errors.append(
            "orchestration_model.role_profile_fallback_guard.required_downgrade_record "
            "must be ROLE_PROFILE_DOWNGRADE"
        )
    if {"explicit_operator_approval", "validated_role_parity_packet"} - _as_string_set(
        guard.get("approval_paths")
    ):
        errors.append(
            "orchestration_model.role_profile_fallback_guard.approval_paths must include "
            "explicit_operator_approval and validated_role_parity_packet"
        )
    missing_parity_fields = sorted(
        REQUIRED_ROLE_PARITY_PACKET_FIELDS
        - _as_string_set(guard.get("role_parity_packet_required_fields"))
    )
    if missing_parity_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard."
            "role_parity_packet_required_fields missing: "
            + ", ".join(missing_parity_fields)
        )
    missing_approval_fields = sorted(
        REQUIRED_ROLE_PROFILE_OPERATOR_APPROVAL_FIELDS
        - _as_string_set(guard.get("operator_approval_required_fields"))
    )
    if missing_approval_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard."
            "operator_approval_required_fields missing: "
            + ", ".join(missing_approval_fields)
        )
    if set(guard.get("parent_preference_order", [])) != REQUIRED_ROLE_PROFILE_PARENT_PREFERENCE_ORDER:
        errors.append(
            "orchestration_model.role_profile_fallback_guard.parent_preference_order must "
            "retry same Bears role, reduce scope, split task, then request downgrade"
        )
    missing_forbidden = sorted(
        {"pr_publish", "pr_ready_for_review", "pr_merge", "pull_request_mutation", "git_push"}
        - _as_string_set(guard.get("generic_fallback_forbidden_without_mutation_authority"))
    )
    if missing_forbidden:
        errors.append(
            "orchestration_model.role_profile_fallback_guard."
            "generic_fallback_forbidden_without_mutation_authority missing: "
            + ", ".join(missing_forbidden)
        )
    if guard.get("mutation_authority_lane_required") is not True:
        errors.append(
            "orchestration_model.role_profile_fallback_guard."
            "mutation_authority_lane_required must be true"
        )
    missing_lane_fields = sorted(
        REQUIRED_ROLE_PROFILE_MUTATION_AUTHORITY_FIELDS
        - _as_string_set(guard.get("mutation_authority_lane_fields"))
    )
    if missing_lane_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard."
            "mutation_authority_lane_fields missing: "
            + ", ".join(missing_lane_fields)
        )
    missing_report_fields = sorted(
        REQUIRED_ROLE_PROFILE_FINAL_REPORT_FIELDS
        - _as_string_set(guard.get("final_report_required_fields"))
    )
    if missing_report_fields:
        errors.append(
            "orchestration_model.role_profile_fallback_guard."
            "final_report_required_fields missing: "
            + ", ".join(missing_report_fields)
        )
    status_reasons = guard.get("status_reasons")
    if _require_list(
        status_reasons,
        "orchestration_model.role_profile_fallback_guard.status_reasons",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        found_status_reasons = {
            (item.get("status"), item.get("reason"))
            for item in status_reasons
            if isinstance(item, dict)
        }
        missing_status_reasons = sorted(
            REQUIRED_ROLE_PROFILE_STATUS_REASONS - found_status_reasons
        )
        if missing_status_reasons:
            errors.append(
                "orchestration_model.role_profile_fallback_guard.status_reasons missing: "
                + ", ".join(f"{status}:{reason}" for status, reason in missing_status_reasons)
            )
    documentation = guard.get("documentation")
    if _require_object(
        documentation,
        "orchestration_model.role_profile_fallback_guard.documentation",
        errors,
    ):
        if documentation.get("active_validation_command") != expected_command:
            errors.append(
                "orchestration_model.role_profile_fallback_guard.documentation."
                f"active_validation_command must be {expected_command}"
            )
    return errors


def _validate_parallel_audit_lane(orchestration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lane = orchestration.get("parallel_audit_lane")
    if not _require_object(lane, "orchestration_model.parallel_audit_lane", errors):
        return errors
    if lane.get("enabled") is not True:
        errors.append("orchestration_model.parallel_audit_lane.enabled must be true")
    if lane.get("mode") != "non_blocking_parallel_monitoring":
        errors.append("orchestration_model.parallel_audit_lane.mode must be non_blocking_parallel_monitoring")
    if lane.get("implementation_authority") != "forbidden":
        errors.append("orchestration_model.parallel_audit_lane.implementation_authority must be forbidden")
    if lane.get("blocks_main_workflow") != "hard_stop_only":
        errors.append("orchestration_model.parallel_audit_lane.blocks_main_workflow must be hard_stop_only")
    fields = lane.get("required_event_fields")
    if _require_list(fields, "orchestration_model.parallel_audit_lane.required_event_fields", errors):
        missing = sorted(REQUIRED_PARALLEL_AUDIT_EVENT_FIELDS - set(fields))
        if missing:
            errors.append("orchestration_model.parallel_audit_lane.required_event_fields missing: " + ", ".join(missing))
    events = lane.get("auditable_events")
    if _require_list(events, "orchestration_model.parallel_audit_lane.auditable_events", errors):
        missing = sorted(REQUIRED_PARALLEL_AUDIT_EVENTS - set(events))
        if missing:
            errors.append("orchestration_model.parallel_audit_lane.auditable_events missing: " + ", ".join(missing))
    severity_rows = lane.get("severity_levels")
    if _require_list(severity_rows, "orchestration_model.parallel_audit_lane.severity_levels", errors, item_type=dict, item_label="objects"):
        severity_by_level = {row.get("level"): row for row in severity_rows if isinstance(row, dict) and isinstance(row.get("level"), str)}
        missing = sorted(set(REQUIRED_PARALLEL_AUDIT_SEVERITIES) - set(severity_by_level))
        if missing:
            errors.append("orchestration_model.parallel_audit_lane.severity_levels missing: " + ", ".join(missing))
        for level, expected_blocking in sorted(REQUIRED_PARALLEL_AUDIT_SEVERITIES.items()):
            row = severity_by_level.get(level)
            if not isinstance(row, dict):
                continue
            if row.get("blocks_main_workflow") is not expected_blocking:
                errors.append(f"orchestration_model.parallel_audit_lane.severity_levels {level} blocks_main_workflow must be {expected_blocking}")
            if level != "info" and row.get("github_issue_required") is not True:
                errors.append(f"orchestration_model.parallel_audit_lane.severity_levels {level} must require GitHub issue create or update")
    hard_stops = lane.get("hard_stop_conditions")
    if _require_list(hard_stops, "orchestration_model.parallel_audit_lane.hard_stop_conditions", errors):
        hard_stop_text = " ".join(str(item) for item in hard_stops)
        missing = sorted(marker for marker in REQUIRED_PARALLEL_AUDIT_HARD_STOP_MARKERS if marker not in hard_stop_text)
        if missing:
            errors.append("orchestration_model.parallel_audit_lane.hard_stop_conditions missing markers: " + ", ".join(missing))
    issue_policy = lane.get("github_issue_policy")
    if _require_object(issue_policy, "orchestration_model.parallel_audit_lane.github_issue_policy", errors):
        if issue_policy.get("owner_repo") != "BearsCLOUD/bears_plugin":
            errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.owner_repo must be BearsCLOUD/bears_plugin")
        if issue_policy.get("operator_request_required") is not False:
            errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.operator_request_required must be false")
        create_or_update = str(issue_policy.get("create_or_update", ""))
        if "warning" not in create_or_update or "material" not in create_or_update or "hard_stop" not in create_or_update:
            errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.create_or_update must cover warning, material, and hard_stop findings")
        dedup = issue_policy.get("deduplication_key_fields")
        if _require_list(dedup, "orchestration_model.parallel_audit_lane.github_issue_policy.deduplication_key_fields", errors):
            missing = sorted(REQUIRED_PARALLEL_AUDIT_DEDUP_FIELDS - set(dedup))
            if missing:
                errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.deduplication_key_fields missing: " + ", ".join(missing))
        body_fields = issue_policy.get("issue_body_required_fields")
        if _require_list(body_fields, "orchestration_model.parallel_audit_lane.github_issue_policy.issue_body_required_fields", errors):
            missing = sorted(REQUIRED_PARALLEL_AUDIT_ISSUE_FIELDS - set(body_fields))
            if missing:
                errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.issue_body_required_fields missing: " + ", ".join(missing))
        forbidden = issue_policy.get("issue_body_forbidden_fields")
        if _require_list(forbidden, "orchestration_model.parallel_audit_lane.github_issue_policy.issue_body_forbidden_fields", errors):
            missing = sorted(REQUIRED_PARALLEL_AUDIT_ISSUE_FORBIDDEN_FIELDS - set(forbidden))
            if missing:
                errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.issue_body_forbidden_fields missing: " + ", ".join(missing))
        link_fields = issue_policy.get("required_report_linkage_fields")
        if _require_list(link_fields, "orchestration_model.parallel_audit_lane.github_issue_policy.required_report_linkage_fields", errors):
            missing = sorted(REQUIRED_PARALLEL_AUDIT_ISSUE_LINK_FIELDS - set(link_fields))
            if missing:
                errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.required_report_linkage_fields missing: " + ", ".join(missing))
        update_rule = str(issue_policy.get("update_rule", ""))
        if "deduplication_key" not in update_rule or "Search" not in update_rule or "create" not in update_rule:
            errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.update_rule must require deduplication_key lookup before create")
        if issue_policy.get("report_only_blockers_rejected") is not True:
            errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.report_only_blockers_rejected must be true")
        continue_rule = str(issue_policy.get("continue_monitoring_rule", ""))
        if "continues monitoring" not in continue_rule or "hard_stop" not in continue_rule:
            errors.append("orchestration_model.parallel_audit_lane.github_issue_policy.continue_monitoring_rule must keep monitoring non-blocking except hard_stop")
    return errors


def _validate_commit_local_validation_test_closeout_lane(orchestration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    path = "orchestration_model.commit_local_validation_test_closeout_lane"
    lane = orchestration.get("commit_local_validation_test_closeout_lane")
    if not _require_object(lane, path, errors):
        return errors

    exact_fields = {
        "enabled": True,
        "lane_id": "parallel-gitflow-closeout-lane",
        "mode": "non_blocking_parallel_delivery_closeout",
        "start_condition": "immediately_after_governed_workflow_start",
        "required_subagent_count": 1,
        "parallel_with_parent_orchestrator": True,
        "parent_wait_policy": "do_not_wait",
        "model": "gpt-5.4-mini",
        "reasoning_effort": "high",
        "required_prompt_token": "/goal",
        "assignment_packet_required": True,
        "pre_task_hook_required": True,
        "required_role_profile": "bears-git-workflow-helper",
    }
    for field, expected in exact_fields.items():
        if lane.get(field) != expected:
            errors.append(f"{path}.{field} must be {expected}")
    prompt_prefix = str(lane.get("prompt_prefix", ""))
    required_prompt_token = str(lane.get("required_prompt_token", ""))
    if "/goal" not in prompt_prefix and "/goal" not in required_prompt_token:
        errors.append(f"{path} prompt_prefix or required_prompt_token must include /goal")

    responsibilities = lane.get("responsibilities")
    if _require_list(responsibilities, f"{path}.responsibilities", errors):
        missing = sorted(
            REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_RESPONSIBILITIES - set(responsibilities)
        )
        if missing:
            errors.append(f"{path}.responsibilities missing: " + ", ".join(missing))

    local_test_policy = lane.get("local_test_policy")
    if _require_object(local_test_policy, f"{path}.local_test_policy", errors):
        if local_test_policy.get("pytest_unittest_repo_validators") != "local_commit_validation_owned_only":
            errors.append(
                f"{path}.local_test_policy.pytest_unittest_repo_validators "
                "must be local_commit_validation_owned_only"
            )
        if (
            local_test_policy.get("manual_local_execution")
            != "forbidden_without_explicit_operator_lift"
        ):
            errors.append(
                f"{path}.local_test_policy.manual_local_execution must be "
                "forbidden_without_explicit_operator_lift"
            )
        allowed = local_test_policy.get("allowed_local_checks")
        if _require_list(allowed, f"{path}.local_test_policy.allowed_local_checks", errors):
            missing = sorted(REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_ALLOWED_CHECKS - set(allowed))
            if missing:
                errors.append(
                    f"{path}.local_test_policy.allowed_local_checks missing: "
                    + ", ".join(missing)
                )
        forbidden = local_test_policy.get("forbidden_manual_checks")
        if _require_list(
            forbidden,
            f"{path}.local_test_policy.forbidden_manual_checks",
            errors,
        ):
            missing = sorted(
                REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_FORBIDDEN_CHECKS - set(forbidden)
            )
            if missing:
                errors.append(
                    f"{path}.local_test_policy.forbidden_manual_checks missing: "
                    + ", ".join(missing)
                )

    hook_safety = lane.get("hook_safety_policy")
    if _require_object(hook_safety, f"{path}.hook_safety_policy", errors):
        if hook_safety.get("fast_hooks_only") is not True:
            errors.append(f"{path}.hook_safety_policy.fast_hooks_only must be true")
        if hook_safety.get("impacted_fast_tests_in_hooks") != "required":
            errors.append(
                f"{path}.hook_safety_policy.impacted_fast_tests_in_hooks must be required"
            )
        for field in (
            "broad_tests_in_hooks",
            "network_calls_in_hooks",
            "raw_logs_in_hooks",
            "secret_reads_in_hooks",
        ):
            if hook_safety.get(field) != "forbidden":
                errors.append(f"{path}.hook_safety_policy.{field} must be forbidden")

    closeout_fields = lane.get("closeout_required_fields")
    if _require_list(closeout_fields, f"{path}.closeout_required_fields", errors):
        missing = sorted(REQUIRED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_CLOSEOUT_FIELDS - set(closeout_fields))
        if missing:
            errors.append(f"{path}.closeout_required_fields missing: " + ", ".join(missing))

    git_safety = lane.get("concurrent_git_safety_policy")
    if _require_object(git_safety, f"{path}.concurrent_git_safety_policy", errors):
        for field, expected in REQUIRED_CONCURRENT_GIT_SAFETY_POLICY.items():
            if git_safety.get(field) != expected:
                errors.append(
                    f"{path}.concurrent_git_safety_policy.{field} must be {expected}"
                )

    return errors


def validate_parallel_audit_finding_packet(packet: Any) -> list[str]:
    """Validate mechanical remediation issue linkage for audit findings."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["parallel audit finding packet must be an object"]
    severity = packet.get("severity")
    if severity not in REQUIRED_PARALLEL_AUDIT_SEVERITIES:
        errors.append("parallel audit finding severity is invalid")
    issue_links = [field for field in REQUIRED_PARALLEL_AUDIT_ISSUE_LINK_FIELDS if packet.get(field)]
    if severity in {"warning", "material", "hard_stop"} and len(issue_links) != 1:
        errors.append("warning, material, and hard_stop findings require exactly one of created_issue, updated_issue, or existing_issue")
    if severity == "hard_stop" and not issue_links:
        errors.append("report-only hard_stop finding is rejected without remediation issue linkage")
    issue_body = packet.get("issue_body")
    if severity in {"warning", "material", "hard_stop"}:
        if not isinstance(issue_body, dict):
            errors.append("parallel audit finding issue_body must be an object")
        else:
            missing = sorted(REQUIRED_PARALLEL_AUDIT_ISSUE_FIELDS - set(issue_body))
            if missing:
                errors.append("parallel audit finding issue_body missing: " + ", ".join(missing))
            body_text = json.dumps(issue_body).casefold()
            forbidden = sorted(field for field in REQUIRED_PARALLEL_AUDIT_ISSUE_FORBIDDEN_FIELDS if field in body_text)
            if forbidden:
                errors.append("parallel audit finding issue_body contains forbidden fields: " + ", ".join(forbidden))
    return errors


def validate_goal_parallelization_preflight(
    preflight: Any,
    path: str = "orchestration_model.goal_parallelization_preflight",
) -> list[str]:
    errors: list[str] = []
    if not _require_object(preflight, path, errors):
        return errors

    missing_top = sorted(REQUIRED_GOAL_PARALLELIZATION_PREFLIGHT_FIELDS - set(preflight))
    if missing_top:
        errors.append(f"{path} missing fields: " + ", ".join(missing_top))
    unexpected_top = sorted(set(preflight) - REQUIRED_GOAL_PARALLELIZATION_PREFLIGHT_FIELDS)
    if unexpected_top:
        errors.append(f"{path} contains unexpected fields: " + ", ".join(unexpected_top))

    if preflight.get("enabled") is not True:
        errors.append(f"{path}.enabled must be true")
    if preflight.get("preflight_id") != "goal_parallelization_preflight":
        errors.append(f"{path}.preflight_id must be goal_parallelization_preflight")
    if "goal-driven workflow parallelization" not in str(preflight.get("applies_to", "")):
        errors.append(f"{path}.applies_to must target goal-driven workflow parallelization")

    batch = preflight.get("batch_role_gate")
    if _require_object(batch, f"{path}.batch_role_gate", errors):
        missing_batch = sorted(REQUIRED_BATCH_ROLE_GATE_FIELDS - set(batch))
        if missing_batch:
            errors.append(f"{path}.batch_role_gate missing fields: " + ", ".join(missing_batch))
        if batch.get("required") is not True:
            errors.append(f"{path}.batch_role_gate.required must be true")
        if batch.get("input") != "target_paths":
            errors.append(f"{path}.batch_role_gate.input must be target_paths")
        if batch.get("command") != "python3 scripts/subagent_orchestration_policy.py batch-role-gate --paths-json <paths-json> --json":
            errors.append(f"{path}.batch_role_gate.command must be the batch-role-gate command")
        if batch.get("runs_before_worker_spawn") is not True:
            errors.append(f"{path}.batch_role_gate.runs_before_worker_spawn must be true")
        missing_matched = sorted(
            REQUIRED_BATCH_ROLE_GATE_MATCHED_FIELDS - _as_string_set(batch.get("matched_result_fields"))
        )
        if missing_matched:
            errors.append(
                f"{path}.batch_role_gate.matched_result_fields missing: "
                + ", ".join(missing_matched)
            )
        if batch.get("blocker_result") != "ROLE_COVERAGE_BLOCKER":
            errors.append(f"{path}.batch_role_gate.blocker_result must be ROLE_COVERAGE_BLOCKER")
        missing_mapping_task = sorted(
            REQUIRED_BATCH_ROLE_GATE_MISSING_TASK_FIELDS
            - _as_string_set(batch.get("missing_mapping_task_fields"))
        )
        if missing_mapping_task:
            errors.append(
                f"{path}.batch_role_gate.missing_mapping_task_fields missing: "
                + ", ".join(missing_mapping_task)
            )

    packet = preflight.get("fixed_assignment_packet")
    if _require_object(packet, f"{path}.fixed_assignment_packet", errors):
        if packet.get("packet_shape") != "fixed":
            errors.append(f"{path}.fixed_assignment_packet.packet_shape must be fixed")
        if packet.get("required") is not True:
            errors.append(f"{path}.fixed_assignment_packet.required must be true")
        missing_packet = sorted(
            REQUIRED_GOAL_PREFLIGHT_PACKET_FIELDS - _as_string_set(packet.get("required_fields"))
        )
        if missing_packet:
            errors.append(
                f"{path}.fixed_assignment_packet.required_fields missing: "
                + ", ".join(missing_packet)
            )
        missing_forbidden = sorted(
            REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_FIELDS
            - _as_string_set(packet.get("forbidden_fields"))
        )
        if missing_forbidden:
            errors.append(
                f"{path}.fixed_assignment_packet.forbidden_fields missing: "
                + ", ".join(missing_forbidden)
            )

    spawn_shape = preflight.get("spawn_agent_argument_shape")
    if _require_object(spawn_shape, f"{path}.spawn_agent_argument_shape", errors):
        if spawn_shape.get("strict_args_only") is not True:
            errors.append(f"{path}.spawn_agent_argument_shape.strict_args_only must be true")
        if spawn_shape.get("assignment_packet_reference_required") is not True:
            errors.append(
                f"{path}.spawn_agent_argument_shape.assignment_packet_reference_required must be true"
            )
        missing_spawn = sorted(
            REQUIRED_GOAL_PREFLIGHT_SPAWN_ARGS - _as_string_set(spawn_shape.get("required_args"))
        )
        if missing_spawn:
            errors.append(
                f"{path}.spawn_agent_argument_shape.required_args missing: "
                + ", ".join(missing_spawn)
            )
        missing_spawn_forbidden = sorted(
            REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_SPAWN_ARGS
            - _as_string_set(spawn_shape.get("forbidden_args"))
        )
        if missing_spawn_forbidden:
            errors.append(
                f"{path}.spawn_agent_argument_shape.forbidden_args missing: "
                + ", ".join(missing_spawn_forbidden)
            )
        content_policy = spawn_shape.get("content_path_policy")
        if _require_object(
            content_policy,
            f"{path}.spawn_agent_argument_shape.content_path_policy",
            errors,
        ):
            missing_content_fields = sorted(
                REQUIRED_SPAWN_CONTENT_PATH_POLICY_FIELDS - set(content_policy)
            )
            if missing_content_fields:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.content_path_policy missing fields: "
                    + ", ".join(missing_content_fields)
                )
            if list(content_policy.get("exactly_one_of", [])) != list(REQUIRED_SPAWN_CONTENT_PATHS):
                errors.append(
                    f"{path}.spawn_agent_argument_shape.content_path_policy.exactly_one_of "
                    "must be message, items"
                )
            if content_policy.get("reject_when_both_present") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.content_path_policy."
                    "reject_when_both_present must be true"
                )
            if content_policy.get("reject_when_neither_present") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.content_path_policy."
                    "reject_when_neither_present must be true"
                )
            if content_policy.get("validation_timing") != "before_spawn_agent_invocation":
                errors.append(
                    f"{path}.spawn_agent_argument_shape.content_path_policy.validation_timing "
                    "must be before_spawn_agent_invocation"
                )
        plugin_form = spawn_shape.get("plugin_mention_canonical_form")
        if _require_object(
            plugin_form,
            f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form",
            errors,
        ):
            missing_plugin_form = sorted(REQUIRED_SPAWN_PLUGIN_FORM_FIELDS - set(plugin_form))
            if missing_plugin_form:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form "
                    "missing fields: "
                    + ", ".join(missing_plugin_form)
                )
            if plugin_form.get("required_when_plugin_mention") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "required_when_plugin_mention must be true"
                )
            if plugin_form.get("content_path") != "items":
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "content_path must be items"
                )
            if plugin_form.get("items_length") != 1:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "items_length must be 1"
                )
            if plugin_form.get("item_type") != "text":
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "item_type must be text"
                )
            if plugin_form.get("text_field") != "text":
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "text_field must be text"
                )
            missing_markers = [
                marker
                for marker in REQUIRED_SPAWN_PLUGIN_TEXT_MARKERS
                if marker not in _as_string_set(plugin_form.get("required_text_markers"))
            ]
            if missing_markers:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "required_text_markers missing: "
                    + ", ".join(missing_markers)
                )
            if "message" not in _as_string_set(plugin_form.get("forbidden_top_level_fields")):
                errors.append(
                    f"{path}.spawn_agent_argument_shape.plugin_mention_canonical_form."
                    "forbidden_top_level_fields missing message"
                )
        preinvoke = spawn_shape.get("preinvoke_rejection")
        if _require_object(
            preinvoke,
            f"{path}.spawn_agent_argument_shape.preinvoke_rejection",
            errors,
        ):
            missing_preinvoke = sorted(REQUIRED_SPAWN_PREINVOKE_FIELDS - set(preinvoke))
            if missing_preinvoke:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.preinvoke_rejection missing fields: "
                    + ", ".join(missing_preinvoke)
                )
            if preinvoke.get("reject_before_tool_invocation") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.preinvoke_rejection."
                    "reject_before_tool_invocation must be true"
                )
            if preinvoke.get("rejection_error") != "invalid_spawn_agent_arguments":
                errors.append(
                    f"{path}.spawn_agent_argument_shape.preinvoke_rejection.rejection_error "
                    "must be invalid_spawn_agent_arguments"
                )
        retry = spawn_shape.get("retry_path_preservation")
        if _require_object(
            retry,
            f"{path}.spawn_agent_argument_shape.retry_path_preservation",
            errors,
        ):
            missing_retry = sorted(REQUIRED_SPAWN_RETRY_FIELDS - set(retry))
            if missing_retry:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.retry_path_preservation missing fields: "
                    + ", ".join(missing_retry)
                )
            if retry.get("required") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.retry_path_preservation.required "
                    "must be true"
                )
            if retry.get("drift_log_required") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.retry_path_preservation."
                    "drift_log_required must be true"
                )
            if retry.get("wrapper_only_change_required") is not True:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.retry_path_preservation."
                    "wrapper_only_change_required must be true"
                )
            missing_preserved = [
                section
                for section in REQUIRED_SPAWN_RETRY_PRESERVED_SECTIONS
                if section not in _as_string_set(retry.get("preserve_sections_byte_for_byte"))
            ]
            if missing_preserved:
                errors.append(
                    f"{path}.spawn_agent_argument_shape.retry_path_preservation."
                    "preserve_sections_byte_for_byte missing: "
                    + ", ".join(missing_preserved)
                )

    wait_target = preflight.get("wait_agent_target_validation")
    if _require_object(wait_target, f"{path}.wait_agent_target_validation", errors):
        for field in (
            "target_id_required",
            "reject_missing_target_id",
            "reject_unknown_target_id",
            "reject_non_active_target_id",
        ):
            if wait_target.get(field) is not True:
                errors.append(f"{path}.wait_agent_target_validation.{field} must be true")
        missing_sources = sorted(
            REQUIRED_GOAL_PREFLIGHT_WAIT_TARGET_SOURCES
            - _as_string_set(wait_target.get("target_id_sources"))
        )
        if missing_sources:
            errors.append(
                f"{path}.wait_agent_target_validation.target_id_sources missing: "
                + ", ".join(missing_sources)
            )

    wait_any = preflight.get("wait_any_loop")
    if _require_object(wait_any, f"{path}.wait_any_loop", errors):
        if wait_any.get("enabled") is not True:
            errors.append(f"{path}.wait_any_loop.enabled must be true")
        if wait_any.get("mode") != "wait_any":
            errors.append(f"{path}.wait_any_loop.mode must be wait_any")
        if wait_any.get("target_set_source") != "worker_pool_ledger.active_agent_ids":
            errors.append(
                f"{path}.wait_any_loop.target_set_source must be worker_pool_ledger.active_agent_ids"
            )
        if wait_any.get("required_before_capacity_fallback") is not True:
            errors.append(f"{path}.wait_any_loop.required_before_capacity_fallback must be true")
        if wait_any.get("partial_state_reconciliation_required_before_capacity_fallback") is not True:
            errors.append(
                f"{path}.wait_any_loop.partial_state_reconciliation_required_before_capacity_fallback must be true"
            )
        terminal_events = _as_string_set(wait_any.get("terminal_events"))
        for event in ("agent_completed", "agent_failed", "hard_stop_result"):
            if event not in terminal_events:
                errors.append(f"{path}.wait_any_loop.terminal_events missing {event}")

    ledger = preflight.get("worker_pool_ledger")
    if _require_object(ledger, f"{path}.worker_pool_ledger", errors):
        if ledger.get("required") is not True:
            errors.append(f"{path}.worker_pool_ledger.required must be true")
        if ledger.get("ledger_id") != "goal_parallelization_worker_pool_ledger":
            errors.append(
                f"{path}.worker_pool_ledger.ledger_id must be goal_parallelization_worker_pool_ledger"
            )
        missing_ledger = sorted(
            REQUIRED_GOAL_PREFLIGHT_LEDGER_FIELDS - _as_string_set(ledger.get("required_fields"))
        )
        if missing_ledger:
            errors.append(
                f"{path}.worker_pool_ledger.required_fields missing: "
                + ", ".join(missing_ledger)
            )
        missing_states = sorted(
            REQUIRED_GOAL_PREFLIGHT_LEDGER_STATES - _as_string_set(ledger.get("allowed_states"))
        )
        if missing_states:
            errors.append(
                f"{path}.worker_pool_ledger.allowed_states missing: "
                + ", ".join(missing_states)
            )
        if ledger.get("completed_close_evidence_required_before_new_wave") is not True:
            errors.append(
                f"{path}.worker_pool_ledger.completed_close_evidence_required_before_new_wave must be true"
            )
        if ledger.get("partial_state_reconciliation_required_before_capacity_fallback") is not True:
            errors.append(
                f"{path}.worker_pool_ledger.partial_state_reconciliation_required_before_capacity_fallback must be true"
            )
        if ledger.get("same_ledger_for_nested_subagents") is not True:
            errors.append(
                f"{path}.worker_pool_ledger.same_ledger_for_nested_subagents must be true"
            )
        missing_nested_tracking = sorted(
            REQUIRED_NESTED_TRACKING_FIELDS
            - _as_string_set(ledger.get("nested_tracking_fields"))
        )
        if missing_nested_tracking:
            errors.append(
                f"{path}.worker_pool_ledger.nested_tracking_fields missing: "
                + ", ".join(missing_nested_tracking)
            )
        if ledger.get("completed_not_closed_reuse_reason_required_before_new_wave") is not True:
            errors.append(
                f"{path}.worker_pool_ledger.completed_not_closed_reuse_reason_required_before_new_wave must be true"
            )

    lock = preflight.get("backend_only_scope_lock")
    if _require_object(lock, f"{path}.backend_only_scope_lock", errors):
        if lock.get("required") is not True:
            errors.append(f"{path}.backend_only_scope_lock.required must be true")
        if lock.get("scope") != "backend_only":
            errors.append(f"{path}.backend_only_scope_lock.scope must be backend_only")
        missing_allowed = sorted(
            REQUIRED_GOAL_PREFLIGHT_ALLOWED_SURFACES - _as_string_set(lock.get("allowed_task_surfaces"))
        )
        if missing_allowed:
            errors.append(
                f"{path}.backend_only_scope_lock.allowed_task_surfaces missing: "
                + ", ".join(missing_allowed)
            )
        missing_forbidden_surfaces = sorted(
            REQUIRED_GOAL_PREFLIGHT_FORBIDDEN_SURFACES
            - _as_string_set(lock.get("forbidden_task_surfaces"))
        )
        if missing_forbidden_surfaces:
            errors.append(
                f"{path}.backend_only_scope_lock.forbidden_task_surfaces missing: "
                + ", ".join(missing_forbidden_surfaces)
            )
        if lock.get("blocks_frontend_or_product_scope") is not True:
            errors.append(
                f"{path}.backend_only_scope_lock.blocks_frontend_or_product_scope must be true"
            )

    guards = preflight.get("handoff_guards")
    if _require_list(
        guards,
        f"{path}.handoff_guards",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        seen_guard_ids = {
            guard.get("guard_id")
            for guard in guards
            if isinstance(guard, dict) and isinstance(guard.get("guard_id"), str)
        }
        missing_guards = sorted(REQUIRED_HANDOFF_GUARDS - seen_guard_ids)
        if missing_guards:
            errors.append(f"{path}.handoff_guards missing: " + ", ".join(missing_guards))
        for index, guard in enumerate(guards):
            guard_path = f"{path}.handoff_guards[{index}]"
            missing_guard_fields = sorted(REQUIRED_HANDOFF_GUARD_FIELDS - set(guard))
            if missing_guard_fields:
                errors.append(f"{guard_path} missing fields: " + ", ".join(missing_guard_fields))
            if guard.get("required") is not True:
                errors.append(f"{guard_path}.required must be true")
            guard_id = str(guard.get("guard_id", ""))
            if guard_id and not str(guard.get("issue", "")).startswith(
                "BearsCLOUD/bears_plugin#"
            ):
                errors.append(f"{guard_path}.issue must name the owning GitHub issue")
            if not _as_string_set(guard.get("required_packet_fields")):
                errors.append(f"{guard_path}.required_packet_fields must be non-empty")
            if not _as_string_set(guard.get("reject_when")):
                errors.append(f"{guard_path}.reject_when must be non-empty")
            if guard_id == "fork_context_spawn_inheritance_guard":
                for marker in ("fork_context=true", "agent_type", "model", "reasoning_effort"):
                    if marker not in str(guard.get("enforcement", "")):
                        errors.append(f"{guard_path}.enforcement missing {marker}")
            if guard_id == "parent_control_patch_content_guard":
                for marker in ("git diff --stat", "git diff --name-status", "patch content"):
                    if marker not in str(guard.get("enforcement", "")):
                        errors.append(f"{guard_path}.enforcement missing {marker}")
            if guard_id == "draft_pr_publication_merge_guard":
                for marker in ("draft PR", "NO_CHECKS_REPORTED", "MERGE_NOT_AUTHORIZED"):
                    if marker not in str(guard.get("enforcement", "")):
                        errors.append(f"{guard_path}.enforcement missing {marker}")
            if guard_id == "current_day_checkpoint_collector_guard":
                for marker in ("SCOPE_EXPANSION_REQUIRED", "evidence_scope", "session checkpoints"):
                    if marker not in str(guard.get("enforcement", "")):
                        errors.append(f"{guard_path}.enforcement missing {marker}")
            if guard_id == "current_state_source_authority_guard":
                for marker in ("source_authority", "MEMORY.md", "bounded read"):
                    if marker not in str(guard.get("enforcement", "")):
                        errors.append(f"{guard_path}.enforcement missing {marker}")

    fanout = preflight.get("fanout_thread_limit_preflight")
    if _require_object(fanout, f"{path}.fanout_thread_limit_preflight", errors):
        missing_fanout = sorted(REQUIRED_FANOUT_THREAD_LIMIT_PREFLIGHT_FIELDS - set(fanout))
        if missing_fanout:
            errors.append(
                f"{path}.fanout_thread_limit_preflight missing fields: "
                + ", ".join(missing_fanout)
            )
        unexpected_fanout = sorted(set(fanout) - REQUIRED_FANOUT_THREAD_LIMIT_PREFLIGHT_FIELDS)
        if unexpected_fanout:
            errors.append(
                f"{path}.fanout_thread_limit_preflight contains unexpected fields: "
                + ", ".join(unexpected_fanout)
            )
        if fanout.get("required") is not True:
            errors.append(f"{path}.fanout_thread_limit_preflight.required must be true")
        if fanout.get("hard_max_source") != "limits.hard_max_active_subagents":
            errors.append(
                f"{path}.fanout_thread_limit_preflight.hard_max_source must be limits.hard_max_active_subagents"
            )
        if fanout.get("active_cap_source") != "limits.default_active_executing_subagents":
            errors.append(
                f"{path}.fanout_thread_limit_preflight.active_cap_source must be limits.default_active_executing_subagents"
            )
        if fanout.get("active_open_count_required") is not True:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.active_open_count_required must be true"
            )
        count_sources = fanout.get("active_open_count_sources")
        if _require_list(
            count_sources,
            f"{path}.fanout_thread_limit_preflight.active_open_count_sources",
            errors,
        ):
            missing_sources = sorted(REQUIRED_FANOUT_COUNT_SOURCES - set(count_sources))
            if missing_sources:
                errors.append(
                    f"{path}.fanout_thread_limit_preflight.active_open_count_sources missing: "
                    + ", ".join(missing_sources)
                )
        active_states = _as_string_set(fanout.get("active_states_counted"))
        if active_states != REQUIRED_FANOUT_ACTIVE_STATES:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.active_states_counted must be "
                + ", ".join(sorted(REQUIRED_FANOUT_ACTIVE_STATES))
            )
        open_states = _as_string_set(fanout.get("open_states_counted"))
        if open_states != REQUIRED_FANOUT_OPEN_STATES:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.open_states_counted must be "
                + ", ".join(sorted(REQUIRED_FANOUT_OPEN_STATES))
            )
        if fanout.get("completed_no_longer_needed_close_before_spawn") is not True:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.completed_no_longer_needed_close_before_spawn must be true"
            )
        if fanout.get("close_completed_source") != "worker_pool_ledger.closeout_evidence":
            errors.append(
                f"{path}.fanout_thread_limit_preflight.close_completed_source must be worker_pool_ledger.closeout_evidence"
            )
        reservation = fanout.get("critical_path_wait_slot_reservation")
        if _require_object(
            reservation,
            f"{path}.fanout_thread_limit_preflight.critical_path_wait_slot_reservation",
            errors,
        ):
            if reservation.get("required") is not True:
                errors.append(
                    f"{path}.fanout_thread_limit_preflight.critical_path_wait_slot_reservation.required must be true"
                )
            if reservation.get("reserved_slots_min") != 1:
                errors.append(
                    f"{path}.fanout_thread_limit_preflight.critical_path_wait_slot_reservation.reserved_slots_min must be 1"
                )
            if "critical-path wait_agent targets" not in str(reservation.get("applies_to", "")):
                errors.append(
                    f"{path}.fanout_thread_limit_preflight.critical_path_wait_slot_reservation.applies_to must name critical-path wait_agent targets"
                )
        formula = str(fanout.get("available_slots_formula", ""))
        for marker in (
            "limits.default_active_executing_subagents",
            "active_open_count",
            "reserved_critical_wait_slots",
            "limits.hard_max_active_subagents",
            "open_count",
        ):
            if marker not in formula:
                errors.append(
                    f"{path}.fanout_thread_limit_preflight.available_slots_formula missing {marker}"
                )
        if fanout.get("bounded_batch_spawn_when_requested_exceeds_available") is not True:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.bounded_batch_spawn_when_requested_exceeds_available must be true"
            )
        spawn_batch_rule = str(fanout.get("spawn_batch_rule", ""))
        for marker in (
            "requested worker count exceeds available slots",
            "spawn at most available_slots",
            "wait_any",
            "reconcile the worker_pool_ledger",
            "close completed no-longer-needed agents",
            "next bounded batch",
        ):
            if marker not in spawn_batch_rule:
                errors.append(
                    f"{path}.fanout_thread_limit_preflight.spawn_batch_rule missing {marker}"
                )
        if fanout.get("reject_when_requested_active_exceeds_cap") is not True:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.reject_when_requested_active_exceeds_cap must be true"
            )
        if fanout.get("hard_max_is_safety_cap_only") is not True:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.hard_max_is_safety_cap_only must be true"
            )
        if fanout.get("thread_limit_failure_classification") != "WORKFLOW_DRIFT":
            errors.append(
                f"{path}.fanout_thread_limit_preflight.thread_limit_failure_classification must be WORKFLOW_DRIFT"
            )
        if fanout.get("thread_limit_failure_normal_recovery_allowed") is not False:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.thread_limit_failure_normal_recovery_allowed must be false"
            )
        if fanout.get("drift_evidence_required") is not True:
            errors.append(
                f"{path}.fanout_thread_limit_preflight.drift_evidence_required must be true"
            )

    new_wave = preflight.get("new_wave_gate")
    if _require_object(new_wave, f"{path}.new_wave_gate", errors):
        if new_wave.get("completed_subagent_close_evidence_required") is not True:
            errors.append(
                f"{path}.new_wave_gate.completed_subagent_close_evidence_required must be true"
            )
        if new_wave.get("close_evidence_source") != "worker_pool_ledger.closeout_evidence":
            errors.append(
                f"{path}.new_wave_gate.close_evidence_source must be worker_pool_ledger.closeout_evidence"
            )
        if new_wave.get("forbid_new_wave_when_completed_worker_unclosed") is not True:
            errors.append(
                f"{path}.new_wave_gate.forbid_new_wave_when_completed_worker_unclosed must be true"
            )
        if new_wave.get("block_completed_not_closed_without_reuse_reason") is not True:
            errors.append(
                f"{path}.new_wave_gate.block_completed_not_closed_without_reuse_reason must be true"
            )
        if new_wave.get("reuse_reason_source") != "worker_pool_ledger.reuse_reason":
            errors.append(
                f"{path}.new_wave_gate.reuse_reason_source must be worker_pool_ledger.reuse_reason"
            )
        missing_counts = sorted(
            REQUIRED_NEW_WAVE_CHECKPOINT_COUNT_FIELDS
            - _as_string_set(new_wave.get("checkpoint_count_fields"))
        )
        if missing_counts:
            errors.append(
                f"{path}.new_wave_gate.checkpoint_count_fields missing: "
                + ", ".join(missing_counts)
            )
        if new_wave.get("completed_not_closed_state") != "completed":
            errors.append(
                f"{path}.new_wave_gate.completed_not_closed_state must be completed"
            )
        if new_wave.get("explicit_reuse_reason_required_per_agent") is not True:
            errors.append(
                f"{path}.new_wave_gate.explicit_reuse_reason_required_per_agent must be true"
            )

    final_join = preflight.get("final_join_gate")
    if _require_object(final_join, f"{path}.final_join_gate", errors):
        missing_join_fields = sorted(REQUIRED_FINAL_JOIN_GATE_FIELDS - set(final_join))
        if missing_join_fields:
            errors.append(
                f"{path}.final_join_gate missing fields: "
                + ", ".join(missing_join_fields)
            )
        for field in (
            "required",
            "blocks_parent_completion",
            "requires_all_spawned_agents_terminal",
            "requires_partial_state_reconciled",
            "requires_worker_pool_ledger_closed",
        ):
            if final_join.get(field) is not True:
                errors.append(f"{path}.final_join_gate.{field} must be true")
        if final_join.get("gate_id") != "final_subagent_join_gate_before_parent_completion":
            errors.append(
                f"{path}.final_join_gate.gate_id must be final_subagent_join_gate_before_parent_completion"
            )
        if final_join.get("scope_source") != "worker_pool_ledger.all_spawned_agent_ids":
            errors.append(
                f"{path}.final_join_gate.scope_source must be worker_pool_ledger.all_spawned_agent_ids"
            )
        missing_identity = sorted(
            REQUIRED_FINAL_JOIN_IDENTITY_FIELDS
            - _as_string_set(final_join.get("identity_fields"))
        )
        if missing_identity:
            errors.append(
                f"{path}.final_join_gate.identity_fields missing: "
                + ", ".join(missing_identity)
            )
        missing_fail_states = sorted(
            REQUIRED_FINAL_JOIN_FAIL_CLOSED_STATES
            - _as_string_set(final_join.get("fail_closed_states"))
        )
        if missing_fail_states:
            errors.append(
                f"{path}.final_join_gate.fail_closed_states missing: "
                + ", ".join(missing_fail_states)
            )
        missing_terminal_states = sorted(
            REQUIRED_FINAL_JOIN_CONDITIONAL_TERMINAL_STATES
            - _as_string_set(final_join.get("conditional_terminal_states"))
        )
        if missing_terminal_states:
            errors.append(
                f"{path}.final_join_gate.conditional_terminal_states missing: "
                + ", ".join(missing_terminal_states)
            )
        missing_evidence_fields = sorted(
            REQUIRED_FINAL_JOIN_INTEGRATED_EVIDENCE_FIELDS
            - _as_string_set(final_join.get("integrated_evidence_fields"))
        )
        if missing_evidence_fields:
            errors.append(
                f"{path}.final_join_gate.integrated_evidence_fields missing: "
                + ", ".join(missing_evidence_fields)
            )
        if final_join.get("close_decision_field") != "close_decision":
            errors.append(f"{path}.final_join_gate.close_decision_field must be close_decision")
        if final_join.get("failed_disposition_field") != "failure_disposition":
            errors.append(
                f"{path}.final_join_gate.failed_disposition_field must be failure_disposition"
            )
        missing_wait_sources = sorted(
            REQUIRED_FINAL_JOIN_DEPENDENT_WAIT_SOURCES
            - _as_string_set(final_join.get("dependent_wait_sources"))
        )
        if missing_wait_sources:
            errors.append(
                f"{path}.final_join_gate.dependent_wait_sources missing: "
                + ", ".join(missing_wait_sources)
            )
        missing_fail_conditions = sorted(
            REQUIRED_FINAL_JOIN_FAIL_CLOSED_CONDITIONS
            - _as_string_set(final_join.get("fail_closed_conditions"))
        )
        if missing_fail_conditions:
            errors.append(
                f"{path}.final_join_gate.fail_closed_conditions missing: "
                + ", ".join(missing_fail_conditions)
            )
        missing_pass_conditions = sorted(
            REQUIRED_FINAL_JOIN_PASS_CONDITIONS
            - _as_string_set(final_join.get("pass_conditions"))
        )
        if missing_pass_conditions:
            errors.append(
                f"{path}.final_join_gate.pass_conditions missing: "
                + ", ".join(missing_pass_conditions)
            )

    result_policy = preflight.get("result_policy")
    if _require_object(result_policy, f"{path}.result_policy", errors):
        allowed_results = _as_string_set(result_policy.get("allowed_results"))
        for result in ("ready", "no_eligible_task", "no_write", "needs_parent_split", "blocked"):
            if result not in allowed_results:
                errors.append(f"{path}.result_policy.allowed_results missing {result}")
        missing_non_blocking = sorted(
            REQUIRED_GOAL_PREFLIGHT_NON_BLOCKING_RESULTS
            - _as_string_set(result_policy.get("non_blocking_results"))
        )
        if missing_non_blocking:
            errors.append(
                f"{path}.result_policy.non_blocking_results missing: "
                + ", ".join(missing_non_blocking)
            )
        if result_policy.get("no_eligible_task_status") != "non_blocker":
            errors.append(
                f"{path}.result_policy.no_eligible_task_status must be non_blocker"
            )
        missing_blocked = sorted(
            REQUIRED_GOAL_PREFLIGHT_BLOCKED_RESULTS
            - _as_string_set(result_policy.get("blocked_results"))
        )
        if missing_blocked:
            errors.append(
                f"{path}.result_policy.blocked_results missing: "
                + ", ".join(missing_blocked)
            )

    issue_mapping = preflight.get("issue_mapping")
    if issue_mapping != EXPECTED_GOAL_PREFLIGHT_ISSUE_MAPPING:
        errors.append(f"{path}.issue_mapping must match first-slice issue mapping")

    plan_gate = preflight.get("parent_plan_status_gate")
    if _require_object(plan_gate, f"{path}.parent_plan_status_gate", errors):
        if plan_gate.get("required") is not True:
            errors.append(f"{path}.parent_plan_status_gate.required must be true")
        missing_steps = sorted(
            REQUIRED_PARENT_PLAN_STATUS_STEPS
            - _as_string_set(plan_gate.get("applies_to_steps"))
        )
        if missing_steps:
            errors.append(
                f"{path}.parent_plan_status_gate.applies_to_steps missing: "
                + ", ".join(missing_steps)
            )
        missing_evidence = sorted(
            REQUIRED_PARENT_PLAN_COMPLETED_EVIDENCE_FIELDS
            - _as_string_set(plan_gate.get("completed_required_evidence_fields"))
        )
        if missing_evidence:
            errors.append(
                f"{path}.parent_plan_status_gate.completed_required_evidence_fields missing: "
                + ", ".join(missing_evidence)
            )
        missing_merge_evidence = sorted(
            REQUIRED_PARENT_PLAN_MERGE_EVIDENCE_FIELDS
            - _as_string_set(plan_gate.get("merge_completed_extra_required_fields"))
        )
        if missing_merge_evidence:
            errors.append(
                f"{path}.parent_plan_status_gate.merge_completed_extra_required_fields missing: "
                + ", ".join(missing_merge_evidence)
            )
        pass_values = _as_string_set(plan_gate.get("pass_check_status_values"))
        if not {"PASS", "success", "passed"} <= pass_values:
            errors.append(
                f"{path}.parent_plan_status_gate.pass_check_status_values must include PASS, success, passed"
            )
        if plan_gate.get("reviewer_pass_marker") != "PASS":
            errors.append(f"{path}.parent_plan_status_gate.reviewer_pass_marker must be PASS")
        if plan_gate.get("in_progress_while_worker_active") is not True:
            errors.append(
                f"{path}.parent_plan_status_gate.in_progress_while_worker_active must be true"
            )
        for source in ("worker_pool_ledger.active_agent_ids", "worker_pool_ledger.state=active"):
            if source not in _as_string_set(plan_gate.get("active_worker_sources")):
                errors.append(
                    f"{path}.parent_plan_status_gate.active_worker_sources missing {source}"
                )
        if plan_gate.get("blocked_requires_bears_blocker_artifact") is not True:
            errors.append(
                f"{path}.parent_plan_status_gate.blocked_requires_bears_blocker_artifact must be true"
            )
        missing_artifact_fields = sorted(
            REQUIRED_PARENT_BLOCKER_ARTIFACT_FIELDS
            - _as_string_set(plan_gate.get("blocker_artifact_required_fields"))
        )
        if missing_artifact_fields:
            errors.append(
                f"{path}.parent_plan_status_gate.blocker_artifact_required_fields missing: "
                + ", ".join(missing_artifact_fields)
            )
        missing_artifact_types = sorted(
            ALLOWED_PARENT_BLOCKER_ARTIFACT_TYPES
            - _as_string_set(plan_gate.get("allowed_blocker_artifact_types"))
        )
        if missing_artifact_types:
            errors.append(
                f"{path}.parent_plan_status_gate.allowed_blocker_artifact_types missing: "
                + ", ".join(missing_artifact_types)
            )

    return errors


def _validate_orchestration_model(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    orchestration = policy.get("orchestration_model")
    if not _require_object(orchestration, "orchestration_model", errors):
        return errors

    for field in ("parent_responsibilities", "child_subagent_responsibilities"):
        _require_list(orchestration.get(field), f"orchestration_model.{field}", errors)

    if orchestration.get("multiple_orchestrators_allowed") is not True:
        errors.append("orchestration_model.multiple_orchestrators_allowed must be true")

    pre_task_hook = orchestration.get("pre_task_hook")
    if _require_object(pre_task_hook, "orchestration_model.pre_task_hook", errors):
        if pre_task_hook.get("required") is not True:
            errors.append("orchestration_model.pre_task_hook.required must be true")
        if pre_task_hook.get("runs_before_task_start") is not True:
            errors.append(
                "orchestration_model.pre_task_hook.runs_before_task_start must be true"
            )
        controls = pre_task_hook.get("controls")
        if _require_list(
            controls,
            "orchestration_model.pre_task_hook.controls",
            errors,
        ):
            for control in ("spawn", "manage", "close"):
                if control not in controls:
                    errors.append(
                        f"orchestration_model.pre_task_hook.controls missing {control}"
                    )
        if pre_task_hook.get("assignment_packet_required") is not True:
            errors.append(
                "orchestration_model.pre_task_hook.assignment_packet_required must be true"
            )
        operator_inputs = pre_task_hook.get("must_request_operator_inputs")
        if _require_list(
            operator_inputs,
            "orchestration_model.pre_task_hook.must_request_operator_inputs",
            errors,
        ):
            for marker in ("missing data", "drift answers"):
                if marker not in operator_inputs:
                    errors.append(
                        "orchestration_model.pre_task_hook.must_request_operator_inputs "
                        f"missing {marker}"
                    )
        if pre_task_hook.get("must_block_until_operator_answers") is not True:
            errors.append(
                "orchestration_model.pre_task_hook.must_block_until_operator_answers "
                "must be true"
            )
        if pre_task_hook.get("roadmap_entrypoint") != "/goal":
            errors.append(
                "orchestration_model.pre_task_hook.roadmap_entrypoint must be /goal"
            )
        evidence_fields = pre_task_hook.get("evidence_fields")
        if _require_list(
            evidence_fields,
            "orchestration_model.pre_task_hook.evidence_fields",
            errors,
        ):
            for field in REQUIRED_PRE_TASK_HOOK_FIELDS:
                if field not in evidence_fields:
                    errors.append(
                        "orchestration_model.pre_task_hook.evidence_fields missing "
                        + field
                    )

    parent_policy = orchestration.get("main_agent_action_policy")
    if _require_object(
        parent_policy,
        "orchestration_model.main_agent_action_policy",
        errors,
    ):
        if parent_policy.get("mode") != "orchestration_only_for_subagent_enabled_tasks":
            errors.append(
                "orchestration_model.main_agent_action_policy.mode must be "
                "orchestration_only_for_subagent_enabled_tasks"
            )
        _validate_exact_string_tokens(
            parent_policy.get("allowed_actions"),
            "orchestration_model.main_agent_action_policy.allowed_actions",
            expected=REQUIRED_MAIN_AGENT_ALLOWED_ACTIONS,
            errors=errors,
        )
        _validate_exact_string_tokens(
            parent_policy.get("forbidden_actions"),
            "orchestration_model.main_agent_action_policy.forbidden_actions",
            expected=REQUIRED_MAIN_AGENT_FORBIDDEN_ACTIONS,
            errors=errors,
        )

    errors.extend(_validate_parent_control_lane(orchestration))
    errors.extend(_validate_no_subagent_mode(orchestration))
    errors.extend(_validate_read_only_agent_safety_guard(orchestration))
    errors.extend(_validate_pr_task_role_action_guard(orchestration))
    errors.extend(_validate_role_profile_fallback_guard(orchestration))
    errors.extend(_validate_validation_hook_runner(orchestration))
    errors.extend(_validate_parallel_audit_lane(orchestration))
    errors.extend(_validate_commit_local_validation_test_closeout_lane(orchestration))
    errors.extend(validate_worker_pool_policy(orchestration.get("worker_pool_policy")))
    errors.extend(
        validate_goal_parallelization_preflight(
            orchestration.get("goal_parallelization_preflight")
        )
    )

    controllers = orchestration.get("delegation_controller_roles")
    if _require_list(
        controllers,
        "orchestration_model.delegation_controller_roles",
        errors,
        item_type=dict,
        item_label="objects",
    ):
        seen = {
            controller.get("id"): controller
            for controller in controllers
            if isinstance(controller, dict) and isinstance(controller.get("id"), str)
        }
        missing = sorted(set(REQUIRED_DELEGATION_CONTROLLERS) - set(seen))
        if missing:
            errors.append(
                "orchestration_model.delegation_controller_roles missing: "
                + ", ".join(missing)
            )
        for controller_id, expected in sorted(REQUIRED_DELEGATION_CONTROLLERS.items()):
            controller = seen.get(controller_id)
            if not isinstance(controller, dict):
                continue
            if controller.get("role") != expected["role"]:
                errors.append(
                    f"delegation controller {controller_id} role must be {expected['role']}"
                )
            spawn_roles = set(controller.get("may_spawn_roles", []))
            missing_spawn = sorted(expected["must_spawn"] - spawn_roles)
            if missing_spawn:
                errors.append(
                    f"delegation controller {controller_id} missing child roles: "
                    + ", ".join(missing_spawn)
                )
            lanes = set(controller.get("lanes", []))
            missing_lanes = sorted(expected["must_lanes"] - lanes)
            if missing_lanes:
                errors.append(
                    f"delegation controller {controller_id} missing lanes: "
                    + ", ".join(missing_lanes)
                )
            for field in ("required_packet_fields", "forbidden"):
                _require_list(
                    controller.get(field),
                    f"delegation controller {controller_id}.{field}",
                    errors,
                )
            required_packet_fields = set(controller.get("required_packet_fields", []))
            for packet_field in (*REQUIRED_PRE_TASK_HOOK_FIELDS, *REQUIRED_DELEGATION_CLOSEOUT_FIELDS):
                if packet_field not in required_packet_fields:
                    errors.append(
                        f"delegation controller {controller_id}.required_packet_fields "
                        f"missing {packet_field}"
                    )

    nested = orchestration.get("nested_subagents")
    if _require_object(nested, "orchestration_model.nested_subagents", errors):
        if nested.get("allowed") is not True:
            errors.append("orchestration_model.nested_subagents.allowed must be true")
        for field in ("who_may_spawn", "required_conditions", "forbidden_conditions"):
            _require_list(nested.get(field), f"orchestration_model.nested_subagents.{field}", errors)
        who = set(nested.get("who_may_spawn", []))
        required_roles = {item["role"] for item in REQUIRED_DELEGATION_CONTROLLERS.values()}
        missing_roles = sorted(required_roles - who)
        if missing_roles:
            errors.append(
                "orchestration_model.nested_subagents.who_may_spawn missing: "
                + ", ".join(missing_roles)
            )
        if nested.get("worker_nested_delegation_default") != "blocked_without_parent_authorization":
            errors.append(
                "orchestration_model.nested_subagents.worker_nested_delegation_default must be blocked_without_parent_authorization"
            )
        missing_authorization_fields = sorted(
            REQUIRED_NESTED_AUTHORIZATION_FIELDS
            - _as_string_set(nested.get("parent_authorization_required_fields"))
        )
        if missing_authorization_fields:
            errors.append(
                "orchestration_model.nested_subagents.parent_authorization_required_fields missing: "
                + ", ".join(missing_authorization_fields)
            )
        if nested.get("unauthorized_spawn_classification") != "WORKFLOW_DRIFT":
            errors.append(
                "orchestration_model.nested_subagents.unauthorized_spawn_classification must be WORKFLOW_DRIFT"
            )
        if nested.get("authorized_tracking_ledger") != "goal_parallelization_worker_pool_ledger":
            errors.append(
                "orchestration_model.nested_subagents.authorized_tracking_ledger must be goal_parallelization_worker_pool_ledger"
            )
        missing_tracking_fields = sorted(
            REQUIRED_NESTED_TRACKING_FIELDS
            - _as_string_set(nested.get("authorized_tracking_required_fields"))
        )
        if missing_tracking_fields:
            errors.append(
                "orchestration_model.nested_subagents.authorized_tracking_required_fields missing: "
                + ", ".join(missing_tracking_fields)
            )

    return errors


def _validate_rule_text_strength(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rules = policy.get("rules")
    if not isinstance(rules, list):
        return errors
    rules_by_id = {
        rule.get("id"): rule.get("rule")
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("id"), str)
    }
    parallel_rule = rules_by_id.get("parallel-tasks-use-parallel-subagents")
    if isinstance(parallel_rule, str):
        for label, marker in REQUIRED_PARALLEL_RULE_TEXT.items():
            haystack = parallel_rule if marker == "MUST" else parallel_rule.casefold()
            needle = marker if marker == "MUST" else marker.casefold()
            if needle not in haystack:
                errors.append(
                    "rule parallel-tasks-use-parallel-subagents text missing " + label
                )
    return errors


def _validate_lifecycle(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lifecycle = policy.get("lifecycle")
    if not _require_object(lifecycle, "lifecycle", errors):
        return errors

    required_stages = [
        "route_gate",
        "constitution_gate",
        "research_gate",
        "prototype_gate",
        "design_gate",
        "spec_kit_gate",
        "role_gate",
        "subagent_execution",
        "validation",
        "stage_boundary_audit",
    ]
    stages = lifecycle.get("stages")
    if _require_list(stages, "lifecycle.stages", errors):
        missing = [stage for stage in required_stages if stage not in stages]
        if missing:
            errors.append("lifecycle.stages missing: " + ", ".join(missing))
        if list(stages) != required_stages:
            errors.append("lifecycle.stages must match canonical plugin constitution lifecycle order")
        constitution: dict[str, Any] = {}
        try:
            constitution = load_json(DEFAULT_POLICY.parent / "plugin-constitution.v1.json")
        except Exception:  # noqa: BLE001
            constitution = {}
        if constitution:
            constitution_order = constitution.get("decision_rules", {}).get("lifecycle_order")
            if isinstance(constitution_order, list) and list(stages) != constitution_order:
                errors.append("lifecycle.stages drift from plugin constitution decision_rules.lifecycle_order")
        if "constitution_gate" in stages and "research_gate" in stages:
            if stages.index("constitution_gate") > stages.index("research_gate"):
                errors.append("lifecycle.stages must place constitution_gate before research_gate")

    research_gate = lifecycle.get("research_gate")
    if _require_object(research_gate, "lifecycle.research_gate", errors):
        required_for = _as_string_set(research_gate.get("required_for"))
        missing_required_for = sorted(RESEARCH_REQUIRED_CHANGE_TYPES - required_for)
        if missing_required_for:
            errors.append("lifecycle.research_gate.required_for missing: " + ", ".join(missing_required_for))
        artifacts = research_gate.get("artifact_basenames")
        if not isinstance(artifacts, dict):
            errors.append("lifecycle.research_gate.artifact_basenames must be an object")
        else:
            for key, basename in RESEARCH_ARTIFACT_BASENAMES.items():
                if artifacts.get(key) != basename:
                    errors.append(f"lifecycle.research_gate.artifact_basenames.{key} must be {basename}")
        skip_policy = _as_string_set(research_gate.get("skip_policy"))
        for marker in ("explicit operator skip", "narrow exact-file skip"):
            if marker not in skip_policy:
                errors.append("lifecycle.research_gate.skip_policy missing " + marker)
        narrow_conditions = _as_string_set(research_gate.get("narrow_skip_required_no_change_fields"))
        for marker in (
            "boundary",
            "runtime",
            "deploy",
            "restricted-data",
            "public behavior",
            "workflow",
            "UI",
            "UX",
            "automation pattern",
        ):
            if marker not in narrow_conditions:
                errors.append("lifecycle.research_gate.narrow_skip_required_no_change_fields missing " + marker)
        tracks = _as_string_set(research_gate.get("required_tracks"))
        missing_tracks = sorted(REQUIRED_RESEARCH_TRACKS - tracks)
        if missing_tracks:
            errors.append("lifecycle.research_gate.required_tracks missing: " + ", ".join(missing_tracks))
        if REQUIRED_UX_RESEARCH_TRACK not in tracks:
            errors.append("lifecycle.research_gate.required_tracks missing: " + REQUIRED_UX_RESEARCH_TRACK)

    prototype_gate = lifecycle.get("prototype_gate")
    if _require_object(prototype_gate, "lifecycle.prototype_gate", errors):
        if prototype_gate.get("contract_id") != PROTOTYPE_CONTRACT_ID:
            errors.append(f"lifecycle.prototype_gate.contract_id must be {PROTOTYPE_CONTRACT_ID}")
        required_for = _as_string_set(prototype_gate.get("required_for"))
        for marker in ("unresolved high-risk uncertainty", "cheaply tested"):
            if marker not in required_for:
                errors.append("lifecycle.prototype_gate.required_for missing " + marker)
        skip_policy = _as_string_set(prototype_gate.get("skip_policy"))
        for marker in ("narrow exact-file bugfix", "already-proven implementation pattern"):
            if marker not in skip_policy:
                errors.append("lifecycle.prototype_gate.skip_policy missing " + marker)
        if _as_string_set(prototype_gate.get("required_sections")) != set(PROTOTYPE_REQUIRED_SECTIONS):
            errors.append("lifecycle.prototype_gate.required_sections must include all issue #21 sections")
        if prototype_gate.get("distinguishes_durable_implementation") is not True:
            errors.append("lifecycle.prototype_gate.distinguishes_durable_implementation must be true")

    design_gate = lifecycle.get("design_gate")
    if _require_object(design_gate, "lifecycle.design_gate", errors):
        if design_gate.get("artifact_path") != DESIGN_ARTIFACT_PATH:
            errors.append(f"lifecycle.design_gate.artifact_path must be {DESIGN_ARTIFACT_PATH}")
        if _as_string_set(design_gate.get("required_sections")) != set(REQUIRED_DESIGN_SECTIONS):
            errors.append("lifecycle.design_gate.required_sections must include all issue #22 sections")
        required_before = _as_string_set(design_gate.get("required_before"))
        for marker in ("plan.md", "tasks.md", "speckit-analyze", "implementation"):
            if marker not in required_before:
                errors.append("lifecycle.design_gate.required_before missing " + marker)

    spec_gate = lifecycle.get("spec_kit_gate")
    if _require_object(spec_gate, "lifecycle.spec_kit_gate", errors):
        required_artifacts = spec_gate.get("required_artifacts")
        if _require_list(required_artifacts, "lifecycle.spec_kit_gate.required_artifacts", errors):
            for artifact in ("spec.md", "plan.md", "tasks.md"):
                if artifact not in required_artifacts:
                    errors.append(
                        "lifecycle.spec_kit_gate.required_artifacts missing "
                        + artifact
                    )
        if spec_gate.get("analyze_required") is not True:
            errors.append("lifecycle.spec_kit_gate.analyze_required must be true")

        mandatory_for = spec_gate.get("mandatory_for")
        if _require_list(mandatory_for, "lifecycle.spec_kit_gate.mandatory_for", errors):
            for marker in ("plugin", "repo-boundary", "infra", "kubernetes", "migration"):
                if marker not in mandatory_for:
                    errors.append("lifecycle.spec_kit_gate.mandatory_for missing " + marker)

        exemptions = spec_gate.get("exemptions")
        if _require_list(exemptions, "lifecycle.spec_kit_gate.exemptions", errors):
            if not any("small bugfix" in item.casefold() for item in exemptions if isinstance(item, str)):
                errors.append("lifecycle.spec_kit_gate.exemptions must mention small bugfix")

    audit = lifecycle.get("audit_policy")
    if _require_object(audit, "lifecycle.audit_policy", errors):
        if audit.get("cadence") != "stage_boundary_only":
            errors.append("lifecycle.audit_policy.cadence must be stage_boundary_only")
        required_audits = audit.get("required_audits")
        if _require_list(required_audits, "lifecycle.audit_policy.required_audits", errors):
            missing = sorted(set(REQUIRED_POST_TASK_AUDITS) - set(required_audits))
            if missing:
                errors.append(
                    "lifecycle.audit_policy.required_audits missing: "
                    + ", ".join(missing)
                )

    return errors


def validate_delegation_closeout_packet(
    packet: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    """Validate one synthetic delegation packet against existing policy fields."""

    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["delegation packet must be an object"]

    controllers = policy.get("orchestration_model", {}).get("delegation_controller_roles", [])
    if not isinstance(controllers, list):
        return ["policy orchestration_model.delegation_controller_roles must be a list"]
    controller_by_id = {
        controller.get("id"): controller
        for controller in controllers
        if isinstance(controller, dict) and isinstance(controller.get("id"), str)
    }
    controller_id = packet.get("controller_id")
    controller = controller_by_id.get(controller_id)
    if not isinstance(controller, dict):
        return [f"delegation packet controller_id {controller_id!r} is not allowed"]

    required_fields = controller.get("required_packet_fields")
    if not isinstance(required_fields, list):
        return [f"controller {controller_id} required_packet_fields must be a list"]
    for field in required_fields:
        value = packet.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"delegation packet missing required field: {field}")

    if "validation hook result" in required_fields or "validation hook result" in packet:
        errors.extend(
            validate_validation_hook_result(
                packet.get("validation hook result"),
                policy,
            )
        )
    final_report = (
        packet.get("role_profile_fallback_final_report")
        or packet.get("final_report")
        or packet.get("final report")
    )
    if final_report is not None:
        errors.extend(
            validate_role_profile_fallback_final_report_packet(
                final_report,
                policy,
                "delegation packet.final_report",
            )
        )
    closeout_packet = packet.get("closeout_packet") or packet.get("closeout") or final_report
    if closeout_packet is not None:
        errors.extend(validate_subagent_closeout_quality_packet(closeout_packet, "delegation packet.closeout"))
    if packet.get("pr_publication_closeout") is not None:
        errors.extend(
            validate_pr_publication_closeout_packet(
                packet.get("pr_publication_closeout"),
                "delegation packet.pr_publication_closeout",
            )
        )

    child_role = packet.get("child role")
    may_spawn = controller.get("may_spawn_roles", [])
    if isinstance(may_spawn, list) and child_role not in may_spawn:
        errors.append(f"delegation packet child role {child_role!r} is not allowed")

    child_lane = packet.get("child lane")
    lanes = controller.get("lanes", [])
    if isinstance(lanes, list) and child_lane not in lanes:
        errors.append(f"delegation packet child lane {child_lane!r} is not allowed")

    scope_value = (
        packet.get("write_scope")
        or packet.get("write scope")
        or packet.get("write scope or read-only scope")
    )
    normalized_write_scope = scope_value
    if _is_read_only_scope_marker(scope_value):
        normalized_write_scope = None
    assignment_packet = {
        "agent_name": packet.get("agent_name") or child_role,
        "sandbox_mode": packet.get("child_sandbox_mode") or packet.get("sandbox_mode"),
        "assignment_authority": (
            packet.get("assignment_authority")
            or packet.get("assignment authority")
            or packet.get("allowed_actions")
        ),
        "write_scope": normalized_write_scope,
        "parent_live_sandbox_override": packet.get("parent_live_sandbox_override"),
        "audit_subagent": packet.get("audit_subagent"),
        "reuse_requested": packet.get("reuse_requested"),
        "assigned_to_writable_task": packet.get("assigned_to_writable_task"),
        "read_only_safety_claim": packet.get("read_only_safety_claim"),
        "validator_evidence_command": packet.get("validator_evidence_command"),
    }
    errors.extend(validate_read_only_assignment_packet(assignment_packet, policy, "delegation packet"))

    return errors


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if policy.get("owner_plugin") != EXPECTED_OWNER:
        errors.append(f"owner_plugin must be {EXPECTED_OWNER}")
    errors.extend(_validate_no_forbidden_reasoning_effort(policy))

    limits = policy.get("limits")
    if _require_object(limits, "limits", errors):
        if limits.get("max_concurrent_subagents") != 100:
            errors.append("limits.max_concurrent_subagents must be 100")
        if limits.get("hard_max_active_subagents") != 100:
            errors.append("limits.hard_max_active_subagents must be 100")
        default_active = limits.get("default_active_executing_subagents")
        if not isinstance(default_active, int):
            errors.append("limits.default_active_executing_subagents must be an integer")
        elif default_active >= 100:
            errors.append("limits.default_active_executing_subagents must be lower than hard_max_active_subagents")
        elif default_active < 1:
            errors.append("limits.default_active_executing_subagents must be positive")
        if limits.get("active_executing_cap_applies_to") != "active workers only; idle reusable workers do not count against this default cap":
            errors.append("limits.active_executing_cap_applies_to must exclude idle reusable workers")
        hard_max_rule = limits.get("hard_max_rule")
        if not isinstance(hard_max_rule, str) or "absolute safety cap" not in hard_max_rule or "normal active execution target" not in hard_max_rule:
            errors.append("limits.hard_max_rule must state absolute safety cap and not normal active execution target")
        if limits.get("max_depth") != 3:
            errors.append("limits.max_depth must be 3")
        if limits.get("workspace_map_required") is not False:
            errors.append("limits.workspace_map_required must be false")
        if limits.get("workspace_map_must_be_disabled") is not True:
            errors.append("limits.workspace_map_must_be_disabled must be true")

    required_rule_ids = set(policy.get("required_rule_ids", [])) if isinstance(policy.get("required_rule_ids"), list) else set()
    missing_required_ids = sorted(REQUIRED_RULE_IDS - required_rule_ids)
    if missing_required_ids:
        errors.append("required_rule_ids missing: " + ", ".join(missing_required_ids))
    legacy_required = sorted(required_rule_ids & set(LEGACY_AUDIT_RULE_ALIASES))
    if legacy_required:
        errors.append("required_rule_ids contains legacy post-task aliases: " + ", ".join(legacy_required))
    legacy_aliases = policy.get("legacy_aliases", {}).get("rule_ids") if isinstance(policy.get("legacy_aliases"), dict) else None
    if legacy_aliases != LEGACY_AUDIT_RULE_ALIASES:
        errors.append("legacy_aliases.rule_ids must map legacy post-task audit ids to stage-boundary ids")

    rules = policy.get("rules")
    if _require_list(rules, "rules", errors, item_type=dict, item_label="objects"):
        seen_rule_ids = {
            rule.get("id")
            for rule in rules
            if isinstance(rule, dict) and isinstance(rule.get("id"), str)
        }
        missing_rules = sorted(REQUIRED_RULE_IDS - seen_rule_ids)
        if missing_rules:
            errors.append("rules missing required ids: " + ", ".join(missing_rules))
        legacy_rules = sorted(seen_rule_ids & set(LEGACY_AUDIT_RULE_ALIASES))
        if legacy_rules:
            errors.append("rules contain legacy post-task aliases: " + ", ".join(legacy_rules))
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"rules[{index}] must be an object")
                continue
            if rule.get("status") != "mandatory":
                errors.append(f"rule {rule.get('id', index)} status must be mandatory")
            if not isinstance(rule.get("rule"), str) or not rule["rule"].strip():
                errors.append(f"rule {rule.get('id', index)} must have non-empty rule text")

    config_expectations = policy.get("config_expectations")
    if _require_object(config_expectations, "config_expectations", errors):
        if config_expectations.get("agents.max_threads") != 100:
            errors.append("config_expectations.agents.max_threads must be 100")
        if config_expectations.get("agents.max_depth") != 3:
            errors.append("config_expectations.agents.max_depth must be 3")
        if config_expectations.get("mcp_servers.workspace-map.enabled") is not False:
            errors.append("config_expectations.mcp_servers.workspace-map.enabled must be false")

    errors.extend(_validate_orchestration_model(policy))
    errors.extend(_validate_lifecycle(policy))
    errors.extend(_validate_rule_text_strength(policy))
    errors.extend(_validate_agent_runtime_policy(policy))
    errors.extend(_validate_non_product_post_task_audit(policy))
    errors.extend(validate_research_artifact_contract(policy.get("research_artifact_contract")))
    errors.extend(validate_design_artifact_contract(policy.get("design_artifact_contract")))
    errors.extend(validate_prototype_artifact_contract(policy.get("prototype_artifact_contract")))
    errors.extend(_validate_no_secret_like_text(policy))
    return errors


def validate_codex_config(config: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = policy.get("config_expectations", {})
    if not isinstance(expected, dict):
        return ["config_expectations must be an object before config validation"]

    agents = config.get("agents")
    if not isinstance(agents, dict):
        errors.append("Codex config missing [agents] section")
    else:
        if agents.get("max_threads") != expected.get("agents.max_threads"):
            errors.append(
                f"Codex config agents.max_threads must be {expected.get('agents.max_threads')}, got {agents.get('max_threads')!r}"
            )
        if agents.get("max_depth") != expected.get("agents.max_depth"):
            errors.append(
                f"Codex config agents.max_depth must be {expected.get('agents.max_depth')}, got {agents.get('max_depth')!r}"
            )

    mcp_servers = config.get("mcp_servers")
    workspace_map = mcp_servers.get("workspace-map") if isinstance(mcp_servers, dict) else None
    if not isinstance(workspace_map, dict):
        errors.append("Codex config missing [mcp_servers.workspace-map] section")
    elif workspace_map.get("enabled") is not expected.get("mcp_servers.workspace-map.enabled"):
        errors.append(
            "Codex config mcp_servers.workspace-map.enabled must be "
            f"{expected.get('mcp_servers.workspace-map.enabled')!r}, got {workspace_map.get('enabled')!r}"
        )
    return errors


def render_summary(policy: dict[str, Any]) -> str:
    limits = policy.get("limits", {})
    nested = policy.get("orchestration_model", {}).get("nested_subagents", {})
    controllers = policy.get("orchestration_model", {}).get("delegation_controller_roles", [])
    worker_pool = policy.get("orchestration_model", {}).get("worker_pool_policy", {})
    goal_preflight = policy.get("orchestration_model", {}).get("goal_parallelization_preflight", {})
    commit_local_validation_lane = policy.get("orchestration_model", {}).get("commit_local_validation_test_closeout_lane", {})
    runtime_policy = policy.get("agent_runtime_policy", {})
    return "\n".join(
        [
            f"policy: {policy.get('policy_id', '<unknown>')}",
            f"max_concurrent_subagents: {limits.get('max_concurrent_subagents', '<unknown>')}",
            f"hard_max_active_subagents: {limits.get('hard_max_active_subagents', '<unknown>')}",
            f"default_active_executing_subagents: {limits.get('default_active_executing_subagents', '<unknown>')}",
            f"max_depth: {limits.get('max_depth', '<unknown>')}",
            f"worker_pool_states: {len(worker_pool.get('worker_states', [])) if isinstance(worker_pool, dict) else '<unknown>'}",
            f"goal_parallelization_preflight: {goal_preflight.get('enabled', '<unknown>') if isinstance(goal_preflight, dict) else '<unknown>'}",
            f"main_agent_model: {runtime_policy.get('main_agent', {}).get('model', '<unknown>')}",
            f"main_agent_reasoning_effort: {runtime_policy.get('main_agent', {}).get('reasoning_effort', '<unknown>')}",
            f"delegated_subagents_model: {runtime_policy.get('delegated_subagents', {}).get('model', '<unknown>')}",
            f"delegated_subagents_reasoning_effort: {runtime_policy.get('delegated_subagents', {}).get('reasoning_effort', '<unknown>')}",
            f"commit_local_validation_test_closeout_lane: {commit_local_validation_lane.get('parent_wait_policy', '<unknown>') if isinstance(commit_local_validation_lane, dict) else '<unknown>'}",
            f"evidence_gathering_agent_roles: {len(runtime_policy.get('evidence_gathering_agents', {}).get('roles', []))}",
            f"workspace_map_required: {limits.get('workspace_map_required', '<unknown>')}",
            f"workspace_map_must_be_disabled: {limits.get('workspace_map_must_be_disabled', '<unknown>')}",
            f"nested_subagents_allowed: {nested.get('allowed', '<unknown>')}",
            f"delegation_controller_roles: {len(controllers) if isinstance(controllers, list) else '<unknown>'}",
        ]
    )


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _task_dependencies(task: dict[str, Any]) -> list[str]:
    return _as_string_list(task.get("depends_on"))


def _task_write_scope(task: dict[str, Any], target_path: str) -> list[str]:
    if "write_scope" in task:
        return _as_string_list(task.get("write_scope"))
    scope = _as_string_list(task.get("write_scope"))
    return scope or [target_path]


def _task_has_no_write(task: dict[str, Any], write_scope: list[str]) -> bool:
    if task.get("read_only") is True:
        return True
    if task.get("write_required") is False:
        return True
    if task.get("write_capable") is False:
        return True
    if task.get("no_write") is True:
        return True
    if "write_scope" in task and not write_scope:
        return True
    return False


def _route_requires_parent_split(route_packet: dict[str, Any]) -> bool:
    if route_packet.get("status") == "matched":
        return route_packet.get("decomposition_required") is True
    if route_packet.get("why_blocked") != "parent_only":
        return False
    return bool(route_packet.get("matched_platform_part") or route_packet.get("matched_part_kind"))


def _path_resolves_inside_plugin_root(path: str) -> bool:
    value = path.strip().replace("\\", "/")
    if not value:
        return False
    plugin_root = posixpath.normpath(PLUGIN_ROOT.as_posix())
    if value.startswith("/"):
        resolved = posixpath.normpath(value)
    else:
        resolved = posixpath.normpath(posixpath.join(plugin_root, value))
    return resolved == plugin_root or resolved.startswith(plugin_root + "/")


def _plugin_root_boundary_violations(target_path: str, write_scope: list[str]) -> list[str]:
    violations: list[str] = []
    if target_path and not _path_resolves_inside_plugin_root(target_path):
        violations.append(f"target_path_outside_plugin_root:{target_path}")
    for scope_path in write_scope:
        if not _path_resolves_inside_plugin_root(scope_path):
            violations.append(f"write_scope_outside_plugin_root:{scope_path}")
    return violations


def _backend_only_scope_violations(
    task: dict[str, Any],
    preflight: dict[str, Any],
    write_scope: list[str],
) -> list[str]:
    violations: list[str] = []
    if task.get("backend_only_scope_lock") is False:
        violations.append("backend_only_scope_lock_disabled")
    target = str(task.get("target_path", ""))
    task_surface = str(task.get("task_surface", ""))
    haystack = f"{target} {task_surface} {' '.join(write_scope)}".casefold()
    forbidden = _as_string_list(preflight.get("backend_only_scope_lock", {}).get("forbidden_task_surfaces"))
    violations.extend(
        f"backend_only_forbidden_surface:{surface}"
        for surface in forbidden
        if surface.casefold() in haystack
    )
    return violations


def _route_identity(route_packet: dict[str, Any]) -> tuple[Any, ...]:
    return (
        route_packet.get("status"),
        route_packet.get("concrete_part"),
        route_packet.get("primary_role"),
        route_packet.get("allowed_write_boundary"),
    )


def _write_scope_route_violations(
    *,
    platform_roles: Any,
    platform_catalog: dict[str, Any],
    target_route_packet: dict[str, Any],
    write_scope: list[str],
) -> list[str]:
    if target_route_packet.get("status") != "matched":
        return []
    target_identity = _route_identity(target_route_packet)
    violations: list[str] = []
    for scope_path in write_scope:
        scope_route_packet = platform_roles.route_target(platform_catalog, scope_path)
        if _route_identity(scope_route_packet) != target_identity:
            violations.append(f"write_scope_route_mismatch:{scope_path}")
    return violations


def _normalized_write_scope_path(path: str) -> str:
    value = path.strip().replace("\\", "/")
    if not value:
        return ""
    normalized = posixpath.normpath(value)
    plugin_root = posixpath.normpath(PLUGIN_ROOT.as_posix())
    if normalized == plugin_root:
        return "."
    if normalized.startswith(plugin_root + "/"):
        normalized = normalized[len(plugin_root) + 1 :]
    if not value.startswith("/"):
        normalized = normalized.strip("/")
    return normalized


def _scope_overlap_marker(left: str, right: str) -> str:
    left_norm = _normalized_write_scope_path(left)
    right_norm = _normalized_write_scope_path(right)
    if left_norm == right_norm:
        return left_norm
    if right_norm.startswith(left_norm.rstrip("/") + "/"):
        return left_norm
    return right_norm


def _write_scopes_overlap(left: str, right: str) -> bool:
    left_norm = _normalized_write_scope_path(left)
    right_norm = _normalized_write_scope_path(right)
    if not left_norm or not right_norm:
        return False
    return (
        left_norm == right_norm
        or right_norm.startswith(left_norm.rstrip("/") + "/")
        or left_norm.startswith(right_norm.rstrip("/") + "/")
    )


def _add_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _add_overlapping_write_scope_blockers(lanes: list[dict[str, Any]], block_reasons: list[str]) -> None:
    for left_index, left_lane in enumerate(lanes):
        if left_lane.get("status") != "ready" or left_lane.get("mode") != "parallel":
            continue
        for right_lane in lanes[left_index + 1 :]:
            if right_lane.get("status") != "ready" or right_lane.get("mode") != "parallel":
                continue
            for left_scope in left_lane.get("write_scope", []):
                for right_scope in right_lane.get("write_scope", []):
                    if not isinstance(left_scope, str) or not isinstance(right_scope, str):
                        continue
                    if not _write_scopes_overlap(left_scope, right_scope):
                        continue
                    marker = _scope_overlap_marker(left_scope, right_scope)
                    blocker = f"overlapping_write_scope:{marker}"
                    _add_unique(left_lane["block_reasons"], blocker)
                    _add_unique(right_lane["block_reasons"], blocker)
                    _add_unique(block_reasons, blocker)
                    left_lane["status"] = "blocked"
                    right_lane["status"] = "blocked"
                    left_lane["classification"] = "blocked"
                    right_lane["classification"] = "blocked"
                    _add_unique(left_lane["classification_reasons"], blocker)
                    _add_unique(right_lane["classification_reasons"], blocker)
                    left_lane["eligible_for_parallel_wave"] = False
                    right_lane["eligible_for_parallel_wave"] = False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            _add_unique(result, item.strip())
    return result


def _object_ledger_agent_ids(ledger: Any, field: str) -> list[str]:
    if not isinstance(ledger, dict):
        return []
    return _string_list(ledger.get(field))


def _object_ledger_reuse_reason(ledger: dict[str, Any], agent_id: str) -> str:
    for field in ("reuse_reasons", "reuse_reason_by_agent_id", "per_agent_reuse_reason"):
        value = ledger.get(field)
        if isinstance(value, dict):
            reason = value.get(agent_id)
            if isinstance(reason, str) and reason.strip():
                return reason.strip()
    return ""


def _merge_object_ledger_id(
    entries: list[dict[str, Any]],
    entries_by_agent_id: dict[str, dict[str, Any]],
    ledger: dict[str, Any],
    agent_id: str,
    state: str,
) -> None:
    entry = entries_by_agent_id.get(agent_id)
    if entry is None:
        entry = {"agent_id": agent_id, "state": state, "ledger_count_source": True}
        reuse_reason = _object_ledger_reuse_reason(ledger, agent_id)
        if reuse_reason:
            entry["reuse_reason"] = reuse_reason
        entries.append(entry)
        entries_by_agent_id[agent_id] = entry
        return

    if not str(entry.get("state", "")).strip():
        entry["state"] = state
    if state == "completed" and _entry_state(entry) not in {"closed", "completed"}:
        entry["state"] = state
    if not _entry_reuse_reason(entry):
        reuse_reason = _object_ledger_reuse_reason(ledger, agent_id)
        if reuse_reason:
            entry["reuse_reason"] = reuse_reason


def _request_worker_pool_ledger(request: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = request.get("worker_pool_ledger")
    if isinstance(ledger, list):
        return [entry for entry in ledger if isinstance(entry, dict)]
    if isinstance(ledger, dict):
        ledger_entries: list[dict[str, Any]] = []
        for entries_field in ("entries", "agents"):
            entries = ledger.get(entries_field)
            if isinstance(entries, list):
                ledger_entries.extend(entry for entry in entries if isinstance(entry, dict))

        entries_by_agent_id: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(ledger_entries, start=1):
            agent_id = _ledger_agent_id(entry, index)
            if agent_id and agent_id not in entries_by_agent_id:
                entries_by_agent_id[agent_id] = entry

        for agent_id in _object_ledger_agent_ids(ledger, "active_agent_ids"):
            _merge_object_ledger_id(ledger_entries, entries_by_agent_id, ledger, agent_id, "active")
        for agent_id in _object_ledger_agent_ids(ledger, "open_agent_ids"):
            _merge_object_ledger_id(ledger_entries, entries_by_agent_id, ledger, agent_id, "active")
        for agent_id in _object_ledger_agent_ids(ledger, "completed_agent_ids"):
            _merge_object_ledger_id(ledger_entries, entries_by_agent_id, ledger, agent_id, "completed")
        return ledger_entries
    return []


def _request_all_spawned_agent_ids(
    request: dict[str, Any], ledger: list[dict[str, Any]]
) -> list[str]:
    worker_pool_ledger = request.get("worker_pool_ledger")
    agent_ids: list[str] = []
    if isinstance(worker_pool_ledger, dict):
        all_spawned_agent_ids = worker_pool_ledger.get("all_spawned_agent_ids")
        if isinstance(all_spawned_agent_ids, list):
            for raw_agent_id in all_spawned_agent_ids:
                if isinstance(raw_agent_id, str) and raw_agent_id.strip():
                    _add_unique(agent_ids, raw_agent_id.strip())
    if agent_ids:
        return agent_ids

    for index, entry in enumerate(ledger, start=1):
        _add_unique(agent_ids, _ledger_agent_id(entry, index))
    return agent_ids


def _ledger_entries_by_agent_id(ledger: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(ledger, start=1):
        agent_id = _ledger_agent_id(entry, index)
        if agent_id not in entries:
            entries[agent_id] = entry
    return entries


def _ledger_agent_id(entry: dict[str, Any], index: int) -> str:
    agent_id = entry.get("agent_id")
    if isinstance(agent_id, str) and agent_id.strip():
        return agent_id.strip()
    return f"ledger-entry-{index}"


def _entry_has_text(entry: dict[str, Any], fields: set[str]) -> bool:
    for field in fields:
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and value:
            return True
    return False


def _entry_text(entry: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _entry_state(entry: dict[str, Any]) -> str:
    return str(entry.get("state", "")).strip().casefold()


def _entry_is_reviewer(entry: dict[str, Any]) -> bool:
    role = str(entry.get("role", "")).strip().casefold()
    lane = str(entry.get("lane_type", "")).strip().casefold()
    return bool(entry.get("reviewer") is True or "reviewer" in role or lane == "reviewer")


def _entry_reuse_reason(entry: dict[str, Any]) -> str:
    return _entry_text(entry, ("reuse_reason", "explicit_reuse_reason"))


def _entry_close_evidence(entry: dict[str, Any]) -> str:
    return _entry_text(entry, ("closeout_evidence", "closed_evidence", "close_evidence"))


def build_new_wave_closeout_checkpoint(request: dict[str, Any]) -> dict[str, Any]:
    """Build the closeout checkpoint required before a new worker wave."""

    ledger = _request_worker_pool_ledger(request)
    active_worker_agent_ids: list[str] = []
    active_reviewer_agent_ids: list[str] = []
    completed_not_closed_agent_ids: list[str] = []
    completed_not_closed_missing_reuse_reason_agent_ids: list[str] = []

    for index, entry in enumerate(ledger, start=1):
        agent_id = _ledger_agent_id(entry, index)
        state = _entry_state(entry)
        if state in REQUIRED_FANOUT_ACTIVE_STATES:
            if _entry_is_reviewer(entry):
                active_reviewer_agent_ids.append(agent_id)
            else:
                active_worker_agent_ids.append(agent_id)
        if state == "completed" and not _entry_close_evidence(entry):
            completed_not_closed_agent_ids.append(agent_id)
            if not _entry_reuse_reason(entry):
                completed_not_closed_missing_reuse_reason_agent_ids.append(agent_id)

    return {
        "counts": {
            "active_workers": len(active_worker_agent_ids),
            "active_reviewers": len(active_reviewer_agent_ids),
            "completed_not_closed_agents": len(completed_not_closed_agent_ids),
        },
        "active_worker_agent_ids": active_worker_agent_ids,
        "active_reviewer_agent_ids": active_reviewer_agent_ids,
        "completed_not_closed_agent_ids": completed_not_closed_agent_ids,
        "completed_not_closed_missing_reuse_reason_agent_ids": completed_not_closed_missing_reuse_reason_agent_ids,
        "new_wave_allowed": not completed_not_closed_missing_reuse_reason_agent_ids,
    }


def _entry_outcome_integrated(entry: dict[str, Any]) -> bool:
    if entry.get("outcome_integrated") is True:
        return True
    if str(entry.get("integration_status", "")).strip() == "integrated":
        return True
    return _entry_has_text(entry, REQUIRED_FINAL_JOIN_INTEGRATED_EVIDENCE_FIELDS)


def _entry_has_close_decision(entry: dict[str, Any]) -> bool:
    decision = entry.get("close_decision")
    return isinstance(decision, str) and bool(decision.strip())


def _dependent_wait_remaining(request: dict[str, Any], ledger: list[dict[str, Any]]) -> bool:
    if request.get("dependent_wait_remaining") is True:
        return True
    waits = request.get("dependent_waits")
    if isinstance(waits, list):
        for wait in waits:
            if not isinstance(wait, dict):
                return True
            status = str(wait.get("status", "")).strip()
            if status not in {"resolved", "closed", "complete", "completed"}:
                return True
    for entry in ledger:
        if entry.get("dependent_wait_remaining") is True:
            return True
    return False


def evaluate_final_subagent_join_gate(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Return the parent-completion join decision for spawned subagents."""
    errors = validate_policy(policy)
    if errors:
        return {
            "gate_id": "final_subagent_join_gate_before_parent_completion",
            "status": "blocked",
            "blocks_parent_completion": True,
            "block_reasons": ["invalid_policy"],
            "policy_errors": errors,
            "joined_agent_ids": [],
            "pending_agent_ids": [],
        }

    ledger = _request_worker_pool_ledger(request)
    block_reasons: list[str] = []
    joined_agent_ids: list[str] = []
    pending_agent_ids: list[str] = []
    integrated_agent_ids: list[str] = []

    if _dependent_wait_remaining(request, ledger):
        block_reasons.append("any_dependent_wait_remaining")

    allowed_conditional_states = REQUIRED_FINAL_JOIN_CONDITIONAL_TERMINAL_STATES
    fail_closed_states = REQUIRED_FINAL_JOIN_FAIL_CLOSED_STATES
    scoped_agent_ids = _request_all_spawned_agent_ids(request, ledger)
    entries_by_agent_id = _ledger_entries_by_agent_id(ledger)
    for agent_id in scoped_agent_ids:
        entry = entries_by_agent_id.get(agent_id)
        if entry is None:
            pending_agent_ids.append(agent_id)
            _add_unique(block_reasons, "any_spawned_subagent_missing_terminal_evidence")
            continue

        raw_state = entry.get("state")
        state = str(raw_state).strip().casefold() if raw_state else "unknown"
        if state in fail_closed_states:
            pending_agent_ids.append(agent_id)
            if state in {"eligible", "queued"}:
                _add_unique(block_reasons, "any_spawned_subagent_queued")
            elif state == "active":
                _add_unique(block_reasons, "any_spawned_subagent_active")
            elif state in {"unknown", "partial", "stale"}:
                _add_unique(block_reasons, "any_spawned_subagent_unknown")
            else:
                _add_unique(block_reasons, f"any_spawned_subagent_{state}")
            continue

        if state not in allowed_conditional_states:
            pending_agent_ids.append(agent_id)
            _add_unique(block_reasons, "any_spawned_subagent_unknown")
            continue

        integrated = _entry_outcome_integrated(entry)
        close_decision = _entry_has_close_decision(entry)
        if state == "failed":
            disposition = entry.get("failure_disposition")
            if not isinstance(disposition, str) or not disposition.strip():
                pending_agent_ids.append(agent_id)
                _add_unique(block_reasons, "any_failed_subagent_without_disposition")
                continue
        if not integrated:
            pending_agent_ids.append(agent_id)
            _add_unique(block_reasons, "any_completed_subagent_without_integrated_evidence")
            continue
        if not close_decision:
            pending_agent_ids.append(agent_id)
            _add_unique(block_reasons, "any_completed_subagent_without_close_decision")
            continue
        joined_agent_ids.append(agent_id)
        integrated_agent_ids.append(agent_id)

    status = "blocked" if block_reasons else "passed"
    return {
        "gate_id": "final_subagent_join_gate_before_parent_completion",
        "status": status,
        "blocks_parent_completion": status == "blocked",
        "block_reasons": block_reasons,
        "joined_agent_ids": joined_agent_ids,
        "pending_agent_ids": pending_agent_ids,
        "integrated_agent_ids": integrated_agent_ids,
        "no_dependent_wait_remaining": not _dependent_wait_remaining(request, ledger),
    }


def _fanout_thread_limit_plan(
    *,
    request: dict[str, Any],
    policy: dict[str, Any],
    parallel_ready_count: int,
) -> dict[str, Any]:
    limits = policy.get("limits", {})
    active_cap = int(limits.get("default_active_executing_subagents", 0) or 0)
    hard_max = int(limits.get("hard_max_active_subagents", 0) or 0)
    ledger = _request_worker_pool_ledger(request)
    worker_pool_ledger = request.get("worker_pool_ledger")
    active_agent_ids = [
        _ledger_agent_id(entry, index)
        for index, entry in enumerate(ledger, start=1)
        if _entry_state(entry) in REQUIRED_FANOUT_ACTIVE_STATES
    ]
    for agent_id in _object_ledger_agent_ids(worker_pool_ledger, "active_agent_ids"):
        _add_unique(active_agent_ids, agent_id)

    open_agent_ids = [
        _ledger_agent_id(entry, index)
        for index, entry in enumerate(ledger, start=1)
        if _entry_state(entry) in REQUIRED_FANOUT_OPEN_STATES
    ]
    for field in ("open_agent_ids", "active_agent_ids", "completed_agent_ids"):
        for agent_id in _object_ledger_agent_ids(worker_pool_ledger, field):
            _add_unique(open_agent_ids, agent_id)
    completed_no_longer_needed_agent_ids = [
        _ledger_agent_id(entry, index)
        for index, entry in enumerate(ledger, start=1)
        if str(entry.get("state", "")).strip() == "completed"
        and entry.get("no_longer_needed") is True
    ]
    reserved_critical_wait_slots = max(
        1,
        int(request.get("reserved_critical_wait_slots", 1) or 1),
    )
    available_slots = min(
        active_cap - len(active_agent_ids) - reserved_critical_wait_slots,
        hard_max - len(open_agent_ids),
    )
    available_slots = max(0, available_slots)
    batch_capacity_after_wait = max(1, active_cap - reserved_critical_wait_slots)
    spawn_batches: list[dict[str, Any]] = []
    remaining = parallel_ready_count
    wave = 1
    while remaining > 0:
        batch_limit = available_slots if wave == 1 else batch_capacity_after_wait
        batch_size = min(remaining, batch_limit)
        if batch_size <= 0:
            break
        spawn_batches.append(
            {
                "wave": wave,
                "max_spawn_count": batch_size,
                "wait_before_next_wave": remaining > batch_size,
            }
        )
        remaining -= batch_size
        wave += 1

    spawn_failure = request.get("last_spawn_failure")
    thread_limit_failure = False
    if isinstance(spawn_failure, dict):
        failure_text = " ".join(
            str(spawn_failure.get(field, ""))
            for field in ("code", "error_code", "message", "detail")
        ).casefold()
        thread_limit_failure = "thread" in failure_text and "limit" in failure_text

    return {
        "required": True,
        "active_agent_ids": active_agent_ids,
        "open_agent_ids": open_agent_ids,
        "active_open_count": len(active_agent_ids),
        "open_count": len(open_agent_ids),
        "completed_no_longer_needed_agent_ids": completed_no_longer_needed_agent_ids,
        "close_before_spawn_required": bool(completed_no_longer_needed_agent_ids),
        "reserved_critical_wait_slots": reserved_critical_wait_slots,
        "available_slots": available_slots,
        "requested_worker_count": parallel_ready_count,
        "bounded_batches_required": parallel_ready_count > available_slots,
        "spawn_batches": spawn_batches,
        "thread_limit_failure_classification": "WORKFLOW_DRIFT" if thread_limit_failure else "",
        "normal_recovery_allowed": False if thread_limit_failure else True,
        "drift_evidence_required": thread_limit_failure,
    }


def _argument_field_present(arguments: dict[str, Any], field: str) -> bool:
    return field in arguments and arguments[field] is not None


def _spawn_argument_text_values(arguments: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    message = arguments.get("message")
    if isinstance(message, str):
        texts.append(message)
    items = arguments.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item["text"])
    return texts


def _spawn_plugin_mention_required(arguments: dict[str, Any]) -> bool:
    if arguments.get("plugin_mention_required") is True:
        return True
    return any("@bears" in text.casefold() for text in _spawn_argument_text_values(arguments))


def _packet_text(packet: Any) -> str:
    if isinstance(packet, str):
        return packet
    if isinstance(packet, dict):
        parts: list[str] = []
        for key, value in packet.items():
            if isinstance(value, str):
                parts.append(f"{key}: {value}")
            elif isinstance(value, (dict, list)):
                parts.append(_packet_text(value))
        return "\n".join(part for part in parts if part)
    if isinstance(packet, list):
        return "\n".join(_packet_text(item) for item in packet)
    return ""


def _packet_bool(packet: dict[str, Any], *fields: str) -> bool:
    return any(packet.get(field) is True for field in fields)


def _packet_role(packet: dict[str, Any]) -> str:
    for field in ("agent_type", "role", "assigned_role", "profile", "agent_name"):
        value = packet.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _assignment_action_tokens(packet: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in ("action", "actions", "task_type", "assignment_type", "allowed_actions"):
        value = packet.get(field)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str):
                tokens.add(item.strip().casefold().replace("-", "_").replace(" ", "_"))
    return {token for token in tokens if token}


def _is_leaf_pr_delivery_packet(packet: dict[str, Any]) -> bool:
    if packet.get("leaf_delivery") is True:
        return True
    actions = _assignment_action_tokens(packet)
    delivery_tokens = {"pr_merge", "merge", "mark_ready", "ready_for_review", "pr_ready", "publish_pr"}
    orchestration_tokens = {"route", "split", "assign", "wait", "integrate_evidence", "spawn_child"}
    return bool(actions & delivery_tokens) and not bool(actions & orchestration_tokens)


def validate_parent_control_packet(packet: Any, path: str = "parent_control_packet") -> list[str]:
    """Reject parent-control commands that collect child patch content."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    command = " ".join(_as_string_list(packet.get("commands")))
    if not command:
        command = str(packet.get("command", ""))
    normalized = command.casefold()
    if PATCH_CONTENT_COMMAND_RE.search(command) or ("git diff" in normalized and "| sed" in normalized):
        errors.append(
            f"{path}.command parent_control_patch_content_forbidden: use git diff --stat, "
            "git diff --name-status, validator output, or dedicated reviewer subagent"
        )
    return errors


def validate_pr_publication_closeout_packet(packet: Any, path: str = "pr_publication_closeout") -> list[str]:
    """Validate draft/default PR publication and merge-authority markers."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    is_draft = packet.get("isDraft")
    if is_draft is None:
        is_draft = packet.get("draft")
    review_decision = str(packet.get("reviewDecision") or packet.get("review_decision") or "").strip()
    checks = packet.get("checks", packet.get("statusCheckRollup", packet.get("check_status")))
    no_checks = checks in (None, "", []) or str(checks).strip().casefold() in {"no checks reported", "none"}
    markers = set(_as_string_list(packet.get("closeout_markers")))
    text = _packet_text(packet)
    if is_draft is False and not review_decision and no_checks:
        if "MERGE_NOT_AUTHORIZED" not in markers and "MERGE_NOT_AUTHORIZED" not in text:
            errors.append(f"{path}.MERGE_NOT_AUTHORIZED required for non-draft PR without review or checks")
        if "NO_CHECKS_REPORTED" not in markers and "NO_CHECKS_REPORTED" not in text:
            errors.append(f"{path}.NO_CHECKS_REPORTED required when checks are absent")
    if packet.get("merge_attempted") is True and "MERGE_NOT_AUTHORIZED" in text:
        errors.append(f"{path}.merge_attempted forbidden when MERGE_NOT_AUTHORIZED is present")
    return errors


def validate_subagent_closeout_quality_packet(packet: Any, path: str = "subagent_closeout") -> list[str]:
    """Validate English artifact text and slice-scoped final-audit vocabulary."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    text = _packet_text(packet)
    if CYRILLIC_RANGE.search(text):
        errors.append(f"{path}.artifact_language must be English-only")
    errors.extend(validate_current_day_checkpoint_packet(packet, path))
    errors.extend(validate_current_state_audit_packet(packet, path))
    verdict = str(packet.get("verdict") or packet.get("status") or "").strip()
    remaining_work = packet.get("remaining_work")
    unrelated_open = packet.get("unrelated_open_tasks")
    assigned_slice_passed = packet.get("assigned_slice_passed") is True
    if assigned_slice_passed and verdict == "FAIL" and (remaining_work or unrelated_open):
        errors.append(
            f"{path}.verdict must be PASS_WITH_REMAINING_WORK or PASS when only unrelated work remains"
        )
    if remaining_work and verdict not in {"PASS_WITH_REMAINING_WORK", "PASS", "BLOCKED", "FAIL"}:
        errors.append(f"{path}.verdict uses unsupported remaining_work vocabulary")
    return errors


def validate_model_capability_packet(packet: Any, path: str = "model_capability_packet") -> list[str]:
    """Reject known model/parameter mismatches before spawn_agent."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    model = str(packet.get("model") or "").strip()
    unsupported_fields = MODEL_UNSUPPORTED_FIELDS.get(model, set())
    if not unsupported_fields:
        return errors
    present_fields: set[str] = set()
    if packet.get("reasoning_summary") is not None:
        present_fields.add("reasoning_summary")
    reasoning = packet.get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("summary") is not None:
        present_fields.add("reasoning.summary")
    for field in sorted(present_fields & unsupported_fields):
        profile = packet.get("profile_path") or packet.get("agent_profile") or "<unknown-profile>"
        errors.append(
            f"{path}.{field} unsupported_model_parameter: profile={profile} "
            f"model={model} field={field} corrective_action=remove_field_or_select_supported_model"
        )
    return errors


def validate_spawn_agent_argument_shape(
    arguments: Any,
    policy: dict[str, Any],
    path: str = "spawn_agent_arguments",
) -> list[str]:
    """Validate spawn_agent content wrapper shape before tool invocation."""

    errors: list[str] = []
    if not _require_object(arguments, path, errors):
        return errors
    orchestration = policy.get("orchestration_model", {})
    preflight = orchestration.get("goal_parallelization_preflight", {})
    spawn_shape = preflight.get("spawn_agent_argument_shape", {})
    plugin_form = spawn_shape.get("plugin_mention_canonical_form", {})

    has_message = _argument_field_present(arguments, "message")
    has_items = _argument_field_present(arguments, "items")
    if has_message and has_items:
        errors.append(
            f"{path} invalid_spawn_agent_arguments: provide either message or items, not both"
        )
    if not has_message and not has_items:
        errors.append(
            f"{path} invalid_spawn_agent_arguments: one of message or items is required"
        )

    if not _spawn_plugin_mention_required(arguments):
        return errors

    if has_message:
        errors.append(
            f"{path}.message is forbidden for @bears plugin mention; use items"
        )
    if not has_items:
        errors.append(
            f"{path}.items is required for @bears plugin mention"
        )
        return errors

    items = arguments.get("items")
    if not isinstance(items, list):
        errors.append(f"{path}.items must be a list")
        return errors
    expected_length = plugin_form.get("items_length", 1)
    if len(items) != expected_length:
        errors.append(f"{path}.items must contain exactly {expected_length} item")
        return errors
    item = items[0]
    if not isinstance(item, dict):
        errors.append(f"{path}.items[0] must be an object")
        return errors
    expected_item_type = str(plugin_form.get("item_type", "text"))
    if item.get("type") != expected_item_type:
        errors.append(f"{path}.items[0].type must be {expected_item_type}")
    text_field = str(plugin_form.get("text_field", "text"))
    text = item.get(text_field)
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{path}.items[0].{text_field} must be non-empty text")
        return errors
    for marker in plugin_form.get("required_text_markers", REQUIRED_SPAWN_PLUGIN_TEXT_MARKERS):
        if not isinstance(marker, str):
            continue
        if marker == "@bears":
            if marker not in text.casefold():
                errors.append(f"{path}.items[0].{text_field} missing {marker}")
        elif marker not in text:
            errors.append(f"{path}.items[0].{text_field} missing {marker}")
    return errors


def validate_spawn_agent_preflight_packet(
    packet: Any,
    policy: dict[str, Any],
    path: str = "spawn_agent_preflight_packet",
) -> list[str]:
    """Validate the parent preflight packet before spawn_agent is called."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    arguments = packet.get("spawn_agent_arguments", packet)
    errors.extend(validate_spawn_agent_argument_shape(arguments, policy, f"{path}.spawn_agent_arguments"))
    if isinstance(arguments, dict):
        combined_packet = dict(packet)
        combined_packet.update(arguments)
        errors.extend(validate_current_day_checkpoint_packet(combined_packet, path))
        errors.extend(validate_current_state_audit_packet(combined_packet, path))
        errors.extend(validate_role_profile_fallback_packet(combined_packet, policy, path))
        errors.extend(validate_model_capability_packet(combined_packet, path))
        if combined_packet.get("fork_context") is True:
            for field in ("agent_type", "role", "model", "reasoning_effort", "model_reasoning_effort"):
                if field in combined_packet and combined_packet.get(field) not in (None, ""):
                    errors.append(
                        f"{path}.{field} fork_context_inheritance_violation: "
                        "omit role/model overrides when fork_context=true"
                    )
        if _is_leaf_pr_delivery_packet(combined_packet) and _packet_role(combined_packet) == "bears-orchestrator":
            errors.append(
                f"{path}.agent_type leaf_pr_delivery_role_guard: "
                "bears-orchestrator is forbidden for leaf PR delivery"
            )
        text = _packet_text(combined_packet)
        lowered = text.casefold()
        if "gh auth status" in lowered and not (
            _packet_bool(combined_packet, "auth_diagnosis", "authentication_blocker_diagnosis")
            and _packet_bool(combined_packet, "redaction_applied", "stderr_redacted")
        ):
            errors.append(
                f"{path}.credential_surface_output_guard: routine prompts must not emit gh auth status"
            )
        mixed_discovery_patterns = (
            "if an explicit task exists, implement",
            "if explicit task exists, implement",
            "inspect and implement if found",
            "discover and implement",
            "identify next explicit unblocked task and implement",
        )
        if any(pattern in lowered for pattern in mixed_discovery_patterns):
            errors.append(
                f"{path}.discovery_implementation_split_guard: "
                "discovery/scout and implementation handoffs must be separate"
            )
        if CYRILLIC_RANGE.search(text):
            errors.append(f"{path}.artifact_language must be English-only")

    if "retry_path_preservation" not in packet:
        return errors
    retry = packet.get("retry_path_preservation")
    if not _require_object(retry, f"{path}.retry_path_preservation", errors):
        return errors
    if retry.get("schema_error_retry_logged_as_workflow_drift") is not True:
        errors.append(
            f"{path}.retry_path_preservation.schema_error_retry_logged_as_workflow_drift "
            "must be true"
        )
    if retry.get("wrapper_only_change") is not True:
        errors.append(f"{path}.retry_path_preservation.wrapper_only_change must be true")
    missing_preserved = [
        section
        for section in REQUIRED_SPAWN_RETRY_PRESERVED_SECTIONS
        if section not in _as_string_set(retry.get("preserved_sections_byte_for_byte"))
    ]
    if missing_preserved:
        errors.append(
            f"{path}.retry_path_preservation.preserved_sections_byte_for_byte missing: "
            + ", ".join(missing_preserved)
        )
    return errors


def _parent_plan_step_type(packet: dict[str, Any]) -> str:
    for field in ("step_type", "plan_step_type", "task_type", "action"):
        value = packet.get(field)
        if isinstance(value, str) and value.strip():
            normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
            if normalized == "pr":
                return "pull_request"
            return normalized
    return ""


def _parent_plan_evidence(packet: dict[str, Any]) -> dict[str, Any]:
    evidence = packet.get("evidence")
    if isinstance(evidence, dict):
        return evidence
    return packet


def _parent_plan_prerequisite_worker_active(packet: dict[str, Any]) -> bool:
    if str(packet.get("prerequisite_worker_state", "")).strip().casefold() == "active":
        return True
    prerequisite_worker_id = str(packet.get("prerequisite_worker_id", "")).strip()
    ledger = _request_worker_pool_ledger(packet)
    if prerequisite_worker_id:
        for index, entry in enumerate(ledger, start=1):
            if _ledger_agent_id(entry, index) == prerequisite_worker_id and _entry_state(entry) == "active":
                return True
    worker_pool_ledger = packet.get("worker_pool_ledger")
    if isinstance(worker_pool_ledger, dict):
        active_ids = worker_pool_ledger.get("active_agent_ids")
        if isinstance(active_ids, list) and active_ids:
            if not prerequisite_worker_id:
                return True
            return prerequisite_worker_id in active_ids
    return False


def validate_parent_plan_status_update(
    packet: Any,
    policy: dict[str, Any],
    path: str = "parent_plan_status",
) -> list[str]:
    """Validate parent plan status against subagent closeout evidence."""

    errors: list[str] = []
    if not _require_object(packet, path, errors):
        return errors
    policy_errors = validate_policy(policy)
    if policy_errors:
        return [f"{path} invalid policy: " + "; ".join(policy_errors)]

    status = str(packet.get("status", "")).strip().casefold()
    step_type = _parent_plan_step_type(packet)
    evidence = _parent_plan_evidence(packet)
    preflight = policy.get("orchestration_model", {}).get("goal_parallelization_preflight", {})
    plan_gate = preflight.get("parent_plan_status_gate", {})
    pass_values = _as_string_set(plan_gate.get("pass_check_status_values"))
    reviewer_pass_marker = str(plan_gate.get("reviewer_pass_marker", "PASS"))

    if _parent_plan_prerequisite_worker_active(packet) and status != "in_progress":
        errors.append(f"{path}.status must remain in_progress while prerequisite worker is active")

    if status == "completed" and step_type in REQUIRED_PARENT_PLAN_STATUS_STEPS:
        required_fields = set(REQUIRED_PARENT_PLAN_COMPLETED_EVIDENCE_FIELDS)
        if step_type == "merge":
            required_fields |= REQUIRED_PARENT_PLAN_MERGE_EVIDENCE_FIELDS
        for field in sorted(required_fields):
            value = evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                errors.append(f"{path}.evidence missing {field}")
        check_status = str(evidence.get("check_status", "")).strip()
        if check_status and check_status not in pass_values:
            errors.append(f"{path}.evidence.check_status must be one of: " + ", ".join(sorted(pass_values)))
        reviewer_pass = str(evidence.get("reviewer_pass_evidence", ""))
        if reviewer_pass and reviewer_pass_marker not in reviewer_pass:
            errors.append(f"{path}.evidence.reviewer_pass_evidence must include {reviewer_pass_marker}")

    if status == "blocked":
        artifact = packet.get("bears_blocker_artifact")
        if not isinstance(artifact, dict):
            errors.append(f"{path}.bears_blocker_artifact required when status is blocked")
            return errors
        for field in sorted(REQUIRED_PARENT_BLOCKER_ARTIFACT_FIELDS):
            value = artifact.get(field)
            if value is None or value == "":
                errors.append(f"{path}.bears_blocker_artifact missing {field}")
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in ALLOWED_PARENT_BLOCKER_ARTIFACT_TYPES:
            errors.append(
                f"{path}.bears_blocker_artifact.artifact_type must be a named Bears blocker artifact"
            )

    return errors


def _scope_allowed_by_parent_authorization(scope: Any, target_scope: str) -> bool:
    allowed_scopes = [scope.strip()] if isinstance(scope, str) and scope.strip() else _as_string_list(scope)
    target = _normalized_write_scope_path(target_scope)
    for allowed in allowed_scopes:
        normalized_allowed = _normalized_write_scope_path(allowed)
        if target == normalized_allowed or target.startswith(normalized_allowed.rstrip("/") + "/"):
            return True
    return False


def validate_nested_delegation_request(packet: Any, policy: dict[str, Any]) -> dict[str, Any]:
    """Classify worker nested delegation before child spawn."""

    if not isinstance(packet, dict):
        return {
            "status": "blocked",
            "classification": "WORKFLOW_DRIFT",
            "block_reasons": ["packet_must_be_object"],
            "allowed": False,
        }
    policy_errors = validate_policy(policy)
    if policy_errors:
        return {
            "status": "blocked",
            "classification": "WORKFLOW_DRIFT",
            "block_reasons": ["invalid_policy"],
            "policy_errors": policy_errors,
            "allowed": False,
        }

    nested_policy = policy.get("orchestration_model", {}).get("nested_subagents", {})
    authorization = packet.get("parent_authorization")
    block_reasons: list[str] = []
    if not isinstance(authorization, dict):
        return {
            "status": "blocked",
            "classification": nested_policy.get("unauthorized_spawn_classification", "WORKFLOW_DRIFT"),
            "block_reasons": ["parent_authorization_required"],
            "allowed": False,
        }

    for field in sorted(REQUIRED_NESTED_AUTHORIZATION_FIELDS):
        value = authorization.get(field)
        if value is None or value == "" or value == []:
            block_reasons.append(f"parent_authorization_missing:{field}")

    requested_role = str(packet.get("requested_role") or packet.get("child_role") or packet.get("role") or "").strip()
    allowed_role = str(authorization.get("allowed_role", "")).strip()
    if requested_role != allowed_role:
        block_reasons.append("parent_authorization_role_mismatch")

    target_scope = str(packet.get("write_scope") or packet.get("target_path") or "").strip()
    if target_scope and not _scope_allowed_by_parent_authorization(authorization.get("scope"), target_scope):
        block_reasons.append("parent_authorization_scope_mismatch")

    max_nested_count = authorization.get("max_nested_count")
    try:
        max_nested_count_int = int(max_nested_count)
    except (TypeError, ValueError):
        max_nested_count_int = 0
    if max_nested_count_int < 1:
        block_reasons.append("parent_authorization_max_nested_count_invalid")
    current_nested_count = int(packet.get("current_nested_count", 0) or 0)
    requested_nested_count = int(packet.get("requested_nested_count", 1) or 1)
    if max_nested_count_int and current_nested_count + requested_nested_count > max_nested_count_int:
        block_reasons.append("parent_authorization_max_nested_count_exceeded")

    ledger_id = str(packet.get("worker_pool_ledger_id") or packet.get("ledger_id") or "").strip()
    if ledger_id != nested_policy.get("authorized_tracking_ledger") or packet.get("tracked_in_worker_pool_ledger") is not True:
        block_reasons.append("authorized_nested_subagent_not_tracked_in_worker_pool_ledger")

    status = "blocked" if block_reasons else "allowed"
    return {
        "status": status,
        "classification": nested_policy.get("unauthorized_spawn_classification", "WORKFLOW_DRIFT") if block_reasons else "allowed",
        "block_reasons": block_reasons,
        "allowed": not block_reasons,
        "authorization_id": authorization.get("authorization_id"),
        "worker_pool_ledger_id": ledger_id,
    }


def batch_role_gate(paths: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    """Route a batch of target paths before worker spawn."""

    policy_errors = validate_policy(policy)
    if policy_errors:
        return {
            "schema": "bears-batch-role-gate.v1",
            "status": "invalid_policy",
            "errors": policy_errors,
            "matched": [],
            "blockers": [],
            "generated_governance_tasks": [],
        }
    platform_roles = _load_platform_roles_module()
    catalog = load_json(platform_roles.DEFAULT_CATALOG)
    matched: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    generated_tasks: list[dict[str, Any]] = []
    for raw_path in paths:
        target_path = str(raw_path).strip()
        if not target_path:
            continue
        route = platform_roles.route_target(catalog, target_path)
        if route.get("status") == "matched":
            matched.append(
                {
                    "path": target_path,
                    "status": "matched",
                    "primary_role": route.get("primary_role"),
                    "validation_required": route.get("validation_required", []),
                }
            )
            continue
        blocker = {
            "path": target_path,
            "status": "ROLE_COVERAGE_BLOCKER",
            "why_blocked": route.get("why_blocked", route.get("status", "unmatched")),
        }
        blockers.append(blocker)
        generated_tasks.append(
            {
                "path": target_path,
                "missing_role": route.get("required_role") or route.get("primary_role") or "unmapped",
                "catalog_target": "assets/catalog/platform-role-catalog.v1.json",
                "validator_command": "python3 scripts/platform_roles.py validate",
            }
        )
    return {
        "schema": "bears-batch-role-gate.v1",
        "status": "ROLE_COVERAGE_BLOCKER" if blockers else "matched",
        "matched": matched,
        "blockers": blockers,
        "generated_governance_tasks": generated_tasks,
    }


def plan_goal_parallelization(
    request: dict[str, Any],
    policy: dict[str, Any],
    *,
    platform_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic lane graph before any worker spawn."""

    orchestration = policy.get("orchestration_model", {})
    preflight = orchestration.get("goal_parallelization_preflight", {})
    limits = policy.get("limits", {})
    goal_id = str(request.get("goal_id", "")).strip()
    tasks = request.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    request_backend_only_disabled = request.get("backend_only_scope_lock") is False
    backend_only = True
    active_cap = int(limits.get("default_active_executing_subagents", 0) or 0)
    hard_max = int(limits.get("hard_max_active_subagents", 0) or 0)
    platform_roles = _load_platform_roles_module()
    if platform_catalog is None:
        platform_catalog = platform_roles.load_json(PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json")

    lanes: list[dict[str, Any]] = []
    assignment_packets: list[dict[str, Any]] = []
    role_gaps: list[dict[str, Any]] = []
    worker_pool_ledger: list[dict[str, Any]] = []
    block_reasons: list[str] = []
    classification_reasons: list[str] = []
    new_wave_closeout_checkpoint = build_new_wave_closeout_checkpoint(request)
    missing_reuse_reason_agent_ids = new_wave_closeout_checkpoint[
        "completed_not_closed_missing_reuse_reason_agent_ids"
    ]

    if not goal_id:
        block_reasons.append("goal_id_required")
    if not tasks:
        classification_reasons.append("no_tasks")

    for index, raw_task in enumerate(tasks, start=1):
        if not isinstance(raw_task, dict):
            block_reasons.append(f"task_{index}_must_be_object")
            continue
        task_id = str(raw_task.get("id") or raw_task.get("tasks_md_item_id") or f"task-{index}").strip()
        target_path = str(raw_task.get("target_path", "")).strip()
        dependencies = _task_dependencies(raw_task)
        lane_mode = "sequential" if dependencies else "parallel"
        eligible_for_parallel_wave = not dependencies
        write_scope = _task_write_scope(raw_task, target_path)
        no_write = _task_has_no_write(raw_task, write_scope)
        lane_blockers: list[str] = []
        lane_classification_reasons: list[str] = []
        repo_boundary = str(raw_task.get("repo_boundary", PARALLELIZATION_REPO_BOUNDARY)).strip()
        if not eligible_for_parallel_wave:
            lane_classification_reasons.append("waiting_for_dependencies")
        if no_write:
            lane_classification_reasons.append("no_write_capable_work")
        if not target_path:
            lane_blockers.append("target_path_required")
        if repo_boundary != PARALLELIZATION_REPO_BOUNDARY:
            lane_blockers.append(f"repo_boundary_mismatch:{repo_boundary}")
        lane_blockers.extend(_plugin_root_boundary_violations(target_path, write_scope))
        if request_backend_only_disabled:
            lane_blockers.append("backend_only_scope_lock_disabled")
        lane_blockers.extend(_backend_only_scope_violations(raw_task, preflight, write_scope))

        route_packet = (
            platform_roles.route_target(platform_catalog, target_path)
            if target_path
            else {"status": "ROLE_COVERAGE_BLOCKER", "why_blocked": "missing_target_path"}
        )
        role = route_packet.get("primary_role", "")
        validation_commands = route_packet.get("validation_required", [])
        needs_parent_split = _route_requires_parent_split(route_packet)
        if needs_parent_split:
            lane_classification_reasons.append("parent_scope_requires_split")
        if route_packet.get("status") != "matched" and not needs_parent_split:
            missing_path = target_path or task_id
            gap = {
                "task_id": task_id,
                "target_path": missing_path,
                "status": "ROLE_COVERAGE_BLOCKER",
                "why_blocked": route_packet.get("why_blocked", "unmapped"),
                "governance_task": f"Add exact role coverage for {missing_path}",
            }
            role_gaps.append(gap)
            lane_blockers.append(f"ROLE_COVERAGE_BLOCKER:{missing_path}")

        lane_blockers.extend(
            _write_scope_route_violations(
                platform_roles=platform_roles,
                platform_catalog=platform_catalog,
                target_route_packet=route_packet,
                write_scope=write_scope,
            )
        )
        pr_task_probe = dict(raw_task)
        pr_task_probe.setdefault("role", role)
        pr_task_probe["write_scope"] = write_scope
        pr_task_classification = classify_pr_task_assignment(pr_task_probe, policy)
        if pr_task_classification.get("blocked") is True:
            lane_blockers.append(str(pr_task_classification["status"]))
            lane_classification_reasons.append(str(pr_task_classification["reason"]))

        for blocker in lane_blockers:
            _add_unique(block_reasons, blocker)

        if lane_blockers:
            lane_status = "blocked"
        elif needs_parent_split:
            lane_status = "needs_parent_split"
        elif no_write:
            lane_status = "no_write"
        elif eligible_for_parallel_wave:
            lane_status = "ready"
        else:
            lane_status = "waiting"
        assignment_packet_id = f"{goal_id}:{task_id}" if goal_id else task_id
        lane = {
            "lane_id": task_id,
            "mode": lane_mode,
            "status": lane_status,
            "eligible_for_parallel_wave": lane_status == "ready",
            "target_path": target_path,
            "role": role,
            "dependencies": dependencies,
            "write_scope": write_scope,
            "repo_boundary": repo_boundary,
            "validation_commands": validation_commands,
            "block_reasons": lane_blockers,
            "classification": lane_status,
            "classification_reasons": lane_classification_reasons,
            "assignment_packet_id": assignment_packet_id,
            "pr_task_guard": pr_task_classification,
        }
        for reason in lane_classification_reasons:
            _add_unique(classification_reasons, reason)
        lanes.append(lane)

    _add_overlapping_write_scope_blockers(lanes, block_reasons)

    parallel_ready_count = sum(1 for lane in lanes if lane.get("status") == "ready")
    if parallel_ready_count and missing_reuse_reason_agent_ids:
        for agent_id in missing_reuse_reason_agent_ids:
            _add_unique(
                block_reasons,
                f"completed_not_closed_subagent_without_reuse_reason:{agent_id}",
            )
        _add_unique(classification_reasons, "completed_not_closed_subagent_without_reuse_reason")
    fanout_preflight = _fanout_thread_limit_plan(
        request=request,
        policy=policy,
        parallel_ready_count=parallel_ready_count,
    )
    fanout_blocks_spawn = fanout_preflight["thread_limit_failure_classification"] == "WORKFLOW_DRIFT"
    if fanout_blocks_spawn:
        _add_unique(block_reasons, "WORKFLOW_DRIFT:thread_limit_spawn_failure")
    new_wave_blocks_spawn = bool(parallel_ready_count and missing_reuse_reason_agent_ids)
    for lane in lanes:
        if lane.get("status") == "ready" and not fanout_blocks_spawn and not new_wave_blocks_spawn:
            assignment = {
                "assignment_packet_id": lane["assignment_packet_id"],
                "goal_id": goal_id,
                "tasks_md_item_id": lane["lane_id"],
                "role": lane["role"],
                "target_path": lane["target_path"],
                "repo_boundary": lane["repo_boundary"],
                "write_scope": lane["write_scope"],
                "validation_commands": lane["validation_commands"],
                "pre_task_hook_evidence": "required_before_spawn",
                "backend_only_scope_lock": backend_only,
                "worker_pool_ledger_id": preflight.get("worker_pool_ledger", {}).get(
                    "ledger_id", "goal_parallelization_worker_pool_ledger"
                ),
            }
            assignment_packets.append(assignment)
            worker_pool_ledger.append(
                {
                    "agent_id": "",
                    "assignment_packet_id": lane["assignment_packet_id"],
                    "role": lane["role"],
                    "target_path": lane["target_path"],
                    "write_scope": lane["write_scope"],
                    "state": "eligible",
                    "spawned_at": "",
                    "last_wait_result": "",
                    "closeout_evidence": "",
                    "reconciliation_status": "not_started",
                    "parent_agent_id": "",
                    "depth": 1,
                    "parent_authorization_id": "",
                    "reuse_reason": "",
                }
            )

    default_active_worker_count = min(fanout_preflight["available_slots"], parallel_ready_count)
    if default_active_worker_count > hard_max:
        block_reasons.append("requested_active_exceeds_hard_max")
    if role_gaps:
        block_reasons.append("role_coverage_gaps")

    if role_gaps or block_reasons:
        status = "blocked"
    elif not lanes:
        status = "no_eligible_task"
    elif not assignment_packets:
        lane_statuses = {lane.get("status") for lane in lanes}
        if "needs_parent_split" in lane_statuses:
            status = "needs_parent_split"
        elif lane_statuses == {"no_write"}:
            status = "no_write"
        else:
            status = "no_eligible_task"
    else:
        status = "ready"
    _add_unique(classification_reasons, status)

    return {
        "schema": PARALLELIZATION_PLAN_SCHEMA,
        "preflight_id": "goal_parallelization_preflight",
        "goal_id": goal_id,
        "status": status,
        "classification": status,
        "classification_reasons": classification_reasons,
        "default_active_worker_count": default_active_worker_count,
        "active_worker_cap": active_cap,
        "hard_max_active_subagents": hard_max,
        "fanout_thread_limit_preflight": fanout_preflight,
        "new_wave_closeout_checkpoint": new_wave_closeout_checkpoint,
        "lanes": lanes,
        "role_gaps": role_gaps,
        "assignment_packets": assignment_packets,
        "worker_pool_ledger": worker_pool_ledger,
        "wait_any_loop": {
            "mode": "wait_any",
            "target_set_source": "worker_pool_ledger.active_agent_ids",
        },
        "backend_only_scope_lock": backend_only,
        "block_reasons": block_reasons,
        "read_only": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY), help="subagent orchestration policy path")
    parser.add_argument("--codex-config", default=str(DEFAULT_CODEX_CONFIG), help="Codex config path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate policy only")
    sub.add_parser("validate-config", help="validate policy and non-secret Codex config knobs")
    assignment = sub.add_parser("validate-assignment", help="validate one read-only assignment packet")
    assignment.add_argument("--packet", required=True, help="assignment packet JSON path")
    spawn = sub.add_parser(
        "validate-spawn-preflight",
        help="validate one spawn_agent preflight packet before invocation",
    )
    spawn.add_argument("--packet", required=True, help="spawn_agent preflight packet JSON path")
    plan = sub.add_parser(
        "plan-parallelization",
        help="build a read-only goal parallelization plan from a request JSON file",
    )
    plan.add_argument("--request", required=True, help="goal parallelization request JSON path")
    plan.add_argument("--json", action="store_true", required=True, help="emit deterministic JSON")
    batch = sub.add_parser(
        "batch-role-gate",
        help="route a batch of target paths before worker spawn",
    )
    batch.add_argument("--paths-json", required=True, help="JSON file with a list of paths or {paths: [...]}")
    batch.add_argument("--json", action="store_true", required=True, help="emit deterministic JSON")
    speckit_assignment = sub.add_parser(
        "validate-speckit-assignment",
        help="validate one worker or reviewer Spec Kit assignment packet",
    )
    speckit_assignment.add_argument("--packet", required=True, help="assignment packet JSON path")
    speckit_closeout = sub.add_parser(
        "validate-speckit-closeout",
        help="validate one worker or reviewer executable closeout/result packet",
    )
    speckit_closeout.add_argument("--packet", required=True, help="closeout/result packet JSON path")
    sub.add_parser("summary", help="print compact non-secret summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy_path = Path(args.policy)
    try:
        policy = load_json(policy_path)
    except FileNotFoundError:
        print(f"ERROR: policy not found: {policy_path}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot read policy: {exc}", file=sys.stderr)
        return 1

    if args.command == "summary":
        print(render_summary(policy))
        return 0

    if args.command == "plan-parallelization":
        try:
            request = load_json(Path(args.request))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot read parallelization request: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(plan_goal_parallelization(request, policy), indent=2, sort_keys=True))
        return 0

    if args.command == "batch-role-gate":
        try:
            raw_paths = json.loads(Path(args.paths_json).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot read paths JSON: {exc}", file=sys.stderr)
            return 1
        paths = raw_paths.get("paths") if isinstance(raw_paths, dict) else raw_paths
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            print("ERROR: paths JSON must be a list of strings or {\"paths\": [...]}", file=sys.stderr)
            return 1
        print(json.dumps(batch_role_gate(paths, policy), indent=2, sort_keys=True))
        return 0

    errors = validate_policy(policy)
    if args.command == "validate-assignment":
        try:
            packet = load_json(Path(args.packet))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot read assignment packet: {exc}", file=sys.stderr)
            return 1
        errors.extend(validate_read_only_assignment_packet(packet, policy))
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"read-only assignment packet ok: {args.packet}")
        return 0

    if args.command == "validate-spawn-preflight":
        try:
            packet = load_json(Path(args.packet))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot read spawn preflight packet: {exc}", file=sys.stderr)
            return 1
        errors.extend(validate_spawn_agent_preflight_packet(packet, policy))
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"spawn_agent preflight packet ok: {args.packet}")
        return 0

    if args.command == "validate-speckit-assignment":
        try:
            packet = load_json(Path(args.packet))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot read assignment packet: {exc}", file=sys.stderr)
            return 1
        errors.extend(validate_subagent_speckit_assignment_packet(packet))
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"subagent Spec Kit assignment packet ok: {args.packet}")
        return 0

    if args.command == "validate-speckit-closeout":
        try:
            packet = load_json(Path(args.packet))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot read closeout packet: {exc}", file=sys.stderr)
            return 1
        errors.extend(validate_subagent_speckit_closeout_packet(packet))
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"subagent Spec Kit closeout packet ok: {args.packet}")
        return 0

    if args.command == "validate-config":
        try:
            config = load_toml(Path(args.codex_config))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot parse Codex config: {exc}", file=sys.stderr)
            return 1
        errors.extend(validate_codex_config(config, policy))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.command == "validate-config":
        print(f"subagent orchestration policy and Codex config ok: {args.policy}")
    else:
        print(f"subagent orchestration policy ok: {args.policy}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
