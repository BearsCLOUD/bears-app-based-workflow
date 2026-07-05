#!/usr/bin/env python3
"""Validate the Bears agent GitHub dev CD governance contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/agent-github-dev-cd.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
CATALOG_SCHEMA = "bears-agent-github-dev-cd.v1"
CONCRETE_PART = "agent_github_dev_cd_flow"
ROUTE_CONCRETE_PART = "workflow_overlay_validation_ci_workflow"
VALIDATE_WORKFLOW_PATH = "/srv/bears/plugins/bears/.github/workflows/validate.yml"
WORKFLOW_CONTRACT_PATH = "/srv/bears/plugins/bears/workflows/agent-github-dev-cd/workflow.yml"
REFERENCE_DOC_PATH = "/srv/bears/plugins/bears/docs/reference/agent-github-dev-cd.md"
KUBERNETES_SOURCE_OF_TRUTH = "/srv/bears/kubernetes"
DEV_CD_JOB_ID = "dev-cd-gate"
DEV_CD_JOB_IF = "github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.ci-summary.result == 'success'"
DISPATCH_ARTIFACT_PATH = "artifacts/dev-cd-dispatch-gate.json"
DISPATCH_ARTIFACT_NAME = "dev-cd-dispatch-gate"
DISPATCH_SCHEMA = "bears-agent-github-dev-cd-dispatch-gate.v1"
DISPATCH_STATUS = "DISPATCH_PLAN_READY"
MODE_CLASSIFICATION_SCHEMA = "bears-agent-github-dev-cd-mode-classification.v1"
TASK_CLASSIFICATION_SCHEMA = "bears-agent-github-dev-cd-task-classification.v1"
SCENARIO_POLICY_PACKET_SCHEMA = "bears-agent-github-dev-cd-scenario-policy.v1"
SCENARIO_POLICY_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-scenario-policy-evaluation.v1"
AGENT_PICKUP_PACKET_SCHEMA = "bears-agent-github-dev-cd-agent-pickup.v1"
AGENT_PICKUP_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-agent-pickup-evaluation.v1"
ISSUE_METADATA_PACKET_SCHEMA = "bears-agent-github-dev-cd-issue-metadata.v1"
ISSUE_METADATA_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-issue-metadata-evaluation.v1"
COMMAND_SNIPPET_LINT_SCHEMA = "bears-agent-github-dev-cd-command-snippet-lint.v1"
PR_PUBLICATION_PACKET_SCHEMA = "bears-agent-github-dev-cd-pr-publication.v1"
PR_PUBLICATION_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-pr-publication-evaluation.v1"
FINAL_VERIFICATION_PACKET_SCHEMA = "bears-agent-github-dev-cd-final-verification.v1"
FINAL_VERIFICATION_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-final-verification-evaluation.v1"
HYGIENE_GATE_PACKET_SCHEMA = "bears-agent-github-dev-cd-hygiene-gate.v1"
HYGIENE_GATE_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-hygiene-gate-evaluation.v1"
AGENT_PICKUP_VERIFY_COMMAND = (
    "python3 scripts/agent_github_dev_cd.py verify-agent-pickup --issue-packet <path> --dry-run"
)
ISSUE_METADATA_VERIFY_COMMAND = "python3 scripts/agent_github_dev_cd.py verify-issue-metadata --issue-packet <path>"
MERGE_AUTHORITY_PACKET_SCHEMA = "bears-agent-github-dev-cd-merge-authority.v1"
MERGE_AUTHORITY_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-merge-authority-evaluation.v1"
MERGE_AUTHORITY_VERIFY_COMMAND = (
    "python3 scripts/agent_github_dev_cd.py merge-authority-check --packet <path> "
    "--expected-repository <owner/repo> --expected-pr-number <number> "
    "--expected-head-ref <head-ref> --expected-head-sha <head-sha> --expected-base-ref <base-ref>"
)
DEV_AUTO_MERGE_PACKET_SCHEMA = "bears-agent-github-dev-cd-dev-auto-merge.v1"
DEV_AUTO_MERGE_EVALUATION_SCHEMA = "bears-agent-github-dev-cd-dev-auto-merge-evaluation.v1"
DEV_AUTO_MERGE_VERIFY_COMMAND = (
    "python3 scripts/agent_github_dev_cd.py verify-dev-auto-merge --packet <path> "
    "--expected-repository <owner/repo> --expected-pr-number <number> "
    "--expected-head-ref <head-ref> --expected-head-sha <head-sha> --expected-base-ref dev"
)
DEV_AUTO_MERGE_ALLOWED_STATUS = "DEV_AUTO_MERGE_ALLOWED"
DEV_AUTO_MERGE_BLOCKED_STATUS = "DEV_AUTO_MERGE_BLOCKED"
DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET_REASON = "DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET"
DEV_AUTO_MERGE_BLOCKED_NON_DEV_TARGET_REASON = "DEV_AUTO_MERGE_BLOCKED_NON_DEV_TARGET"
DEV_AUTO_MERGE_BLOCKED_POLICY_REASON = "DEV_AUTO_MERGE_BLOCKED_POLICY"
DEV_AUTO_MERGE_DEPRECATED_REASON = "DEV_AUTO_MERGE_DEPRECATED_MAIN_ONLY_DELIVERY"
DEV_AUTO_MERGE_REQUIRED_CHECK_CONTEXTS = ("ci-summary",)
TASK_CLASSIFICATION_COMMAND = "python3 scripts/agent_github_dev_cd.py classify-task --prompt-file <path>"
SCENARIO_POLICY_VERIFY_COMMAND = "python3 scripts/agent_github_dev_cd.py verify-scenario-policy --packet <path>"
DEFAULT_WORKFLOW_MODE = "sequential"
ALLOWED_WORKFLOW_MODES = ("sequential", "parallel")
DECLARED_WORKFLOW_MODES = ("auto", "sequential", "parallel")
DEVELOPMENT_SCENARIOS = ("dev", "prod", "bugfix", "hot_bugfix", "issue", "goal")
AGENT_CURRENT_RUNTIME = "/srv/bears"
MODE_CLASSIFIED_STATUS = "ok"
MODE_TRANSITION_RECORDED_STATUS = "ok"
MODE_CLASSIFICATION_SKIPPED_STATUS = "not_run"
TOPOLOGY_BLOCKED_STATUS = "fail"
EVIDENCE_REPO_DIR = "docs/evidence/dev-cd"
REPO_EVIDENCE_TRAILERS = (
    "Workflow-State",
    "Merge-Authority-State",
    "Runtime-Evidence",
    "Rollback-Note",
)
GENERATED_EVIDENCE_TRAILERS = {
    "Kubernetes-Dispatch-Plan": DISPATCH_ARTIFACT_PATH,
}
FIXED_TRAILER_VALUES = {
    "Production-Deploy": "false",
}
REQUIRED_VALUE_TRAILERS = ("Goal-Id",)
REQUIRED_EVIDENCE_PATH_CONTRACT = {
    "repo_evidence_dir": EVIDENCE_REPO_DIR,
    "repo_file_trailers": list(REPO_EVIDENCE_TRAILERS),
    "generated_file_trailers": GENERATED_EVIDENCE_TRAILERS,
}
REQUIRED_POLICY_FIELDS = {
    "schema",
    "owner_plugin",
    "concrete_part",
    "updated",
    "purpose",
    "route_target",
    "reference_doc",
    "workflow",
    "validation",
    "branch_model",
    "workflow_modes",
    "pull_request_policy",
    "state_file_policy",
    "issue_type_policy",
    "merge_authority_policy",
    "dev_auto_merge_policy",
    "parent_agent_policy",
    "scenario_policy",
    "ci_policy",
    "cd_policy",
    "output_contract",
}
REQUIRED_CI_COMMANDS = {
    "python3 scripts/ci_requirements.py validate-workflow",
    "python3 scripts/subagents_roles.py validate",
    "python3 scripts/validate_overlay.py --json validate --strict-overlay-skills",
    "python3 scripts/test_selection.py validate",
}
REQUIRED_PARALLEL_CI_JOBS = (
    "changes",
    "schema-catalog-validation",
    "hook-policy-validation",
    "role-workflow-validation",
    "skill-inventory-validation",
    "dirty-boundary-validation",
    "ci-summary",
)
CI_SUMMARY_JOB_ID = "ci-summary"
FORBIDDEN_CI_RUNNER_TOKENS = (
    "python3 -m unittest discover -s tests",
    "python3 -m pytest -q tests",
)
REQUIRED_OUTPUT_FIELDS = {
    "schema",
    "status",
    "goal_id",
    "agent_branch",
    "goal_branch",
    "dev_branch",
    "state_file_gate_passed",
    "ci_required",
    "cd_target",
    "auto_dev_merge_allowed",
    "auto_dev_deploy_allowed",
    "production_deploy_allowed",
    "workflow_mode",
    "mode_classification_status",
    "topology_evidence_path",
    "stacked_branches_allowed",
    "mode_transition_recorded",
    "development_scenario",
    "scenario_policy_status",
    "agent_current_runtime",
    "scenario_auto_merge_to_main_allowed",
}
REQUIRED_PARENT_AGENT_ACTIONS = (
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
REQUIRED_PARENT_AGENT_FORBIDDEN_ACTIONS = (
    "file_read_as_content_collector",
    "file_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_mutation",
    "implementation_tool_use",
)
DRIFTED_PARENT_AGENT_ACTIONS = (
    "wait_for_subagent_evidence",
    "integrate_subagent_evidence",
    "close_subagents",
)
REQUIRED_PARENT_ACTIONS_DOC_LINE = (
    "- Allowed parent actions: `route`, `split`, `assign`, `wait`, `integrate_evidence`, "
    "`run_validators`, `close`, `report`, `pre_task_hook`."
)
REQUIRED_FORBIDDEN_ACTIONS_DOC_LINE = (
    "- Parent agent must not run `file_read_as_content_collector`, `file_write`, `git_add`, "
    "`git_commit`, `git_push`, `pull_request_mutation`, or `implementation_tool_use`."
)
REQUIRED_STATE_FILE_MARKERS = {
    "Workflow-State",
    "Merge-Authority-State",
}
REQUIRED_VERIFY_EVIDENCE_COMMAND_TOKENS = [
    "python3 scripts/agent_github_dev_cd.py verify-dev-cd-evidence",
    '--commit-sha "$GITHUB_SHA"',
    '--dispatch-artifact "$BEARS_DEV_CD_DISPATCH_ARTIFACT"',
]
REQUIRED_COMMIT_TRAILERS = [
    "Goal-Id",
    "Workflow-State",
    "Merge-Authority-State",
    f"Kubernetes-Dispatch-Plan: {DISPATCH_ARTIFACT_PATH}",
    "Runtime-Evidence",
    "Rollback-Note",
    "Production-Deploy: false",
]
REQUIRED_WRITE_DISPATCH_COMMAND_TOKENS = [
    "python3 scripts/agent_github_dev_cd.py write-dispatch-plan",
    '--commit-sha "$GITHUB_SHA"',
    '--dispatch-artifact "$BEARS_DEV_CD_DISPATCH_ARTIFACT"',
    '--kubernetes-source "$BEARS_KUBERNETES_SOURCE_OF_TRUTH"',
    '--declared-mode "$BEARS_WORKFLOW_MODE"',
    '--development-scenario "$BEARS_DEVELOPMENT_SCENARIO"',
]
REQUIRED_PLAN_FIELDS = {
    "schema",
    "status",
    "source_repo",
    "source_branch",
    "source_sha",
    "deploy_source_of_truth",
    "workflow_state_path",
    "merge_authority_state_path",
    "runtime_evidence_path",
    "rollback_note_path",
    "dispatch_plan_path",
    "operator_approval_required",
    "cluster_mutation_allowed_from_plugin",
    "production_deploy_allowed",
    "workflow_mode",
    "mode_classification_status",
    "topology_evidence_path",
    "stacked_branches_allowed",
    "mode_transition_recorded",
    "development_scenario",
    "scenario_policy_status",
    "agent_current_runtime",
    "scenario_auto_merge_to_main_allowed",
}
REQUIRED_DEV_CD_STEP_IDS = [
    "validate-governance",
    "verify-state-file-gate",
    "verify-no-secrets",
    "write-dispatch-plan",
    "upload-dispatch-plan",
]
REQUIRED_WORKFLOW_MODE_RULES = {
    "default_mode": DEFAULT_WORKFLOW_MODE,
    "allowed_modes": list(ALLOWED_WORKFLOW_MODES),
    "sequential": {
        "goal_branch_required": True,
        "agent_branches_required": False,
        "goal_to_dev_pr_allowed": True,
        "direct_main_pr_allowed": False,
        "stacked_branches_allowed_only_with_recorded_policy": True,
    },
    "parallel": {
        "goal_branch_required": True,
        "agent_branches_required": True,
        "agent_pr_target": "goal/<goal-id>",
        "goal_pr_target_for_dev": "dev",
    },
    "mode_transition_rules": {
        "sequential_to_parallel_requires_recorded_transition": True,
        "parallel_to_sequential_blocked_while_agent_prs_open": True,
    },
}
REQUIRED_WORKFLOW_MODE_SEQUENTIAL_STEPS = [
    "goal-branch",
    "classify-task",
    "classify-mode",
    "verify-scenario-policy",
    "branch-enforcement",
    "main-only-delivery",
]
REQUIRED_WORKFLOW_MODE_PARALLEL_STEPS = [
    "goal-branch",
    "classify-task",
    "classify-mode",
    "verify-scenario-policy",
    "branch-enforcement",
    "agent-branches",
    "agent-draft-prs",
    "main-only-delivery",
]
ISSUE_TYPE_IDENTIFIERS = {
    "bugfix": "type:bugfix",
    "idea": "type:idea",
    "develop_ready": "type:develop-ready",
}
FIXED_ISSUE_TYPE_LABELS = tuple(ISSUE_TYPE_IDENTIFIERS.values())
DEVELOP_READY_PRODUCERS = (
    "repository_constitution_alignment",
    "research",
    "accepted_operator_decision",
)
DEVELOP_READY_REQUIRED_EVIDENCE = (
    "constitution_alignment",
    "research",
    "accepted_operator_decision",
)
DEVELOP_READY_BODY_REQUIRED_FIELDS = (
    "concrete_problem",
    "exact_targets_surfaces",
    "required_change",
    "acceptance_criteria",
    "validation_commands",
    "duplicate_guard",
    "safety_boundary",
)
DEVELOP_READY_BODY_FIELD_HEADINGS = {
    "concrete_problem": "Concrete problem",
    "exact_targets_surfaces": "Exact targets/surfaces",
    "required_change": "Required change",
    "acceptance_criteria": "Acceptance criteria",
    "validation_commands": "Validation commands",
    "duplicate_guard": "Duplicate guard",
    "safety_boundary": "Safety boundary",
}
VAGUE_BODY_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "no",
    "tbd",
    "todo",
    "later",
    "wip",
    "fix",
    "fix it",
    "do it",
    "same",
    "see comments",
    "see comment",
    "as above",
}
AGENT_PICKUP_BLOCKED_LABELS = (
    "type:idea",
    "blocked",
    "needs-human",
    "needs-design",
    "security",
    "security-review",
    "secret",
    "credentials",
    "deploy",
    "production",
    "manual-only",
    "agent:blocked",
)
AGENT_PICKUP_REQUIRED_GATES = (
    "route_gate",
    "constitution_evidence",
    "research_evidence",
    "accepted_operator_decision_evidence",
    "owning_role",
    "task_packet",
    "duplicate_guard",
    "dry_run",
)
AGENT_PICKUP_EVIDENCE_REQUIRED_FIELDS = ("status", "evidence_path_or_source_ref", "result_or_decision")
AGENT_PICKUP_DUPLICATE_GUARD_REQUIRED_FIELDS = (
    "status",
    "duplicates_found",
    "repository",
    "normalized_scope_key",
    "search_query_or_checked_issues",
    "checked_at",
    "evidence_summary",
)
AGENT_PICKUP_TASK_PACKET_REQUIRED_FIELDS = (
    "issue",
    "bounded_target",
    "allowed_write_surfaces",
    "allowed_read_surfaces",
    "owning_role",
    "validation_commands",
    "safety_boundary",
)
ISSUE_TEMPLATE_PATH = ".github/ISSUE_TEMPLATE/01-governance-work.yml"
ISSUE_TEMPLATE_REQUIRED_DEVELOP_READY_FIELD_IDS = (
    "agent_pickup_promotion_checklist",
    "route_gate_evidence",
    "constitution_evidence",
    "research_evidence",
    "accepted_operator_decision_evidence",
    "owning_role",
    "task_packet",
    "duplicate_guard",
    "verify_agent_pickup_dry_run",
)
ISSUE_TEMPLATE_CANONICAL_GATE_OPTIONS = (
    "Route gate",
    "Subagents-roles gate",
    "Research gate",
    "Prototype gate",
    "Design gate",
    "Spec Kit gate",
    "Role gate",
    "Subagent execution",
    "Validation",
    "Stage-boundary audit",
)
PLACEHOLDER_EVIDENCE_VALUES = {"", "done", "pass", "passed", "ok", "yes", "n/a", "na", "none", "tbd", "todo", "placeholder"}
MERGE_AUTHORITY_REQUIRED_FIELDS = (
    "pre_task_hook",
    "assignment_packet",
    "repository",
    "pull_request",
    "head_ref",
    "head_sha",
    "base_ref",
    "action",
    "check_policy",
    "state_file_policy",
    "title_policy",
    "draft_policy",
    "rollback_note",
    "authority",
    "conflict_policy",
)
MERGE_AUTHORITY_ACTIONS = ("mark_ready", "merge")
MERGE_AUTHORITY_DRIFT_TOKENS = (
    "merge pr",
    "merge-ready",
    "gh pr merge",
    "gh pr ready",
    "mark ready",
)
MERGE_ALLOWED_STATUS = "MERGE_ALLOWED"
MERGE_BLOCKED_STATUS = "MERGE_BLOCKED"
MERGE_NOT_REQUESTED_STATUS = "MERGE_NOT_REQUESTED"
MERGE_BLOCKED_POLICY_REASON = "MERGE_BLOCKED_POLICY"
MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON = "MERGE_BLOCKED_EMPTY_CHECK_ROLLUP"
MERGE_BLOCKED_DRAFT_PR_REASON = "MERGE_BLOCKED_DRAFT_PR"
MERGE_BLOCKED_OUTDATED_HEAD_REASON = "MERGE_BLOCKED_OUTDATED_HEAD"
MERGE_ELIGIBILITY_GUARD_REASONS = (
    MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON,
    MERGE_BLOCKED_DRAFT_PR_REASON,
    MERGE_BLOCKED_OUTDATED_HEAD_REASON,
)
CONVENTIONAL_TITLE_RE = re.compile(r"^(feat|fix|docs|test|refactor|chore|ci|build|perf|style|revert)\([a-z0-9][a-z0-9._-]*\): .+")
FORBIDDEN_TITLE_MARKERS = ("[codex]", "[ai]", "[assistant]", "codex:")
GH_PR_DIFF_ALLOWED_FLAGS = {"--name-only", "--patch", "--color", "--repo", "-R"}
GH_PR_DIFF_FORBIDDEN_FLAGS = {"--name-status", "--stat"}
DEPLOY_CI_TRIGGER_PATTERNS = (
    ".github/workflows/**",
    "manifests/**",
    "deploy/**",
    "deployment/**",
    "scripts/deploy/**",
    "scripts/*deploy*",
    "scripts/*runtime*validator*",
    "scripts/*validator*runtime*",
)
REQUIRED_MERGE_AUTHORITY_POLICY = {
    "packet_schema": MERGE_AUTHORITY_PACKET_SCHEMA,
    "verify_command": MERGE_AUTHORITY_VERIFY_COMMAND,
    "parent_send_input_merge_directive_allowed": False,
    "plain_parent_send_input_classification": "workflow_drift",
    "required_fields": list(MERGE_AUTHORITY_REQUIRED_FIELDS),
    "allowed_actions": list(MERGE_AUTHORITY_ACTIONS),
    "exact_pr_and_head_required": True,
    "expected_pr_head_args_required": True,
    "pre_task_hook_required": True,
    "assignment_packet_required": True,
    "check_policy": {
        "green_checks_required": True,
        "empty_checks_require_named_no_ci_exception_or_operator_override": True,
    },
    "state_file_policy": {
        "state_files_required": True,
        "authoritative_state_source": "machine_readable_state_files",
        "authority_sources": ["workflow_state", "merge_authority_state"],
        "required_state_refs": ["workflow_state", "merge_authority_state"],
        "non_state_authority_allowed": False,
        "state_file_gate_required_before_merge": True,
    },
    "title_policy": {
        "validation_before_ready_required": True,
        "validation_before_merge_required": True,
    },
    "draft_policy": {
        "draft_must_be_false_before_merge": True,
    },
    "merge_eligibility_guards": {
        "allowed_status": MERGE_ALLOWED_STATUS,
        "blocked_status": MERGE_BLOCKED_STATUS,
        "empty_check_rollup_reason": MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON,
        "draft_pr_reason": MERGE_BLOCKED_DRAFT_PR_REASON,
        "outdated_head_reason": MERGE_BLOCKED_OUTDATED_HEAD_REASON,
        "empty_check_rollup_fail_closed": True,
        "no_ci_exception_allowed_for_merge": False,
        "operator_override_allowed_for_empty_rollup": False,
        "draft_pr_merge_allowed": False,
        "expected_live_head_required": True,
        "expected_live_base_required": True,
        "packet_head_must_match_expected_head": True,
        "packet_base_must_match_expected_base": True,
    },
    "authority": {
        "allowed_sources": ["operator_request", "contract_authority"],
        "parent_send_input_is_authority": False,
    },
    "conflict_policy": {
        "mergeable_state_required": "CLEAN",
        "unknown_or_conflicting_handoff": "integration-fix",
    },
}
REQUIRED_DEV_AUTO_MERGE_POLICY = {
    "packet_schema": DEV_AUTO_MERGE_PACKET_SCHEMA,
    "verify_command": DEV_AUTO_MERGE_VERIFY_COMMAND,
    "status": "deprecated_reference_only",
    "active_authority": False,
    "target_branch": "none",
    "source_branch_pattern": "none",
    "requires_merge_authority_packet": False,
    "requires_green_ci": False,
    "required_check_contexts": [],
    "requires_state_file_gate": False,
    "requires_ci_summary": False,
    "requires_draft_false": False,
    "requires_clean_mergeable_state": False,
    "requires_live_topology_verification": False,
    "authority_source": "none",
    "operator_request_required": True,
    "auto_merge_to_main_allowed": False,
    "production_deploy_allowed": False,
    "blocked_reason": DEV_AUTO_MERGE_DEPRECATED_REASON,
}
REQUIRED_ISSUE_TYPE_POLICY = {
    "issue_identifiers": ISSUE_TYPE_IDENTIFIERS,
    "develop_ready": {
        "identifier": ISSUE_TYPE_IDENTIFIERS["develop_ready"],
        "produced_by": list(DEVELOP_READY_PRODUCERS),
        "required_evidence": list(DEVELOP_READY_REQUIRED_EVIDENCE),
        "required_body_fields": list(DEVELOP_READY_BODY_REQUIRED_FIELDS),
        "body_field_headings": DEVELOP_READY_BODY_FIELD_HEADINGS,
        "empty_or_vague_body_fails_closed": True,
        "comments_do_not_substitute_body_fields": True,
    },
    "type_label_guard": {
        "fixed_type_labels": list(FIXED_ISSUE_TYPE_LABELS),
        "open_governance_issue_exactly_one_type_label_required": True,
        "api_and_automation_created_issues_in_scope": True,
        "body_text_must_not_promote_to_type_develop_ready": True,
        "zero_or_multiple_type_labels_fail_closed": True,
        "verify_command": ISSUE_METADATA_VERIFY_COMMAND,
        "packet_schema": ISSUE_METADATA_PACKET_SCHEMA,
    },
    "agent_pickup": {
        "actor": "local_agent_runner",
        "allowed_issue_type": ISSUE_TYPE_IDENTIFIERS["develop_ready"],
        "starts_bounded_development_without_user_goal_run": True,
        "blocked_when_unlabeled": True,
        "blocked_issue_types": [ISSUE_TYPE_IDENTIFIERS["idea"]],
        "blocked_labels": list(AGENT_PICKUP_BLOCKED_LABELS),
        "bugfix_only_blocked": True,
        "required_pre_dispatch_gates": list(AGENT_PICKUP_REQUIRED_GATES),
        "structured_evidence_required": {
            "route_gate": ["status", "target", "concrete_part_or_route_result", "owning_role_or_primary_role"],
            "evidence_objects": list(AGENT_PICKUP_EVIDENCE_REQUIRED_FIELDS),
            "task_packet": list(AGENT_PICKUP_TASK_PACKET_REQUIRED_FIELDS),
            "duplicate_guard": list(AGENT_PICKUP_DUPLICATE_GUARD_REQUIRED_FIELDS),
            "dry_run": ["status", "command", "result_or_proof_path"],
        },
        "dry_run_required_before_dispatch": True,
        "dispatch_allowed_after_dry_run": True,
    },
    "issue_template": {
        "path": ISSUE_TEMPLATE_PATH,
        "default_label": ISSUE_TYPE_IDENTIFIERS["idea"],
        "promotion_label": ISSUE_TYPE_IDENTIFIERS["develop_ready"],
        "required_develop_ready_field_ids": list(ISSUE_TEMPLATE_REQUIRED_DEVELOP_READY_FIELD_IDS),
        "canonical_gate_options": list(ISSUE_TEMPLATE_CANONICAL_GATE_OPTIONS),
        "blank_issues_allowed": False,
    },
}
SCENARIO_MARKER_DESCRIPTIONS = {
    "dev": ["dev", "development"],
    "prod": ["prod", "production"],
    "bugfix": ["bugfix", "bug", "fix"],
    "hot_bugfix": ["hot bugfix", "hotfix", "hot-fix", "hot fix"],
    "issue": ["issue", "#<number>"],
    "goal": ["/goal"],
}
SCENARIO_RECOMMENDED_ROLES = {
    "dev": "bears-deploy-platform-engineer",
    "prod": "bears-deploy-platform-engineer",
    "bugfix": "bears-deploy-platform-engineer",
    "hot_bugfix": "bears-deploy-platform-engineer",
    "issue": "bears-workflow-overlay-controller",
    "goal": "bears-goal-prompt-generator",
}
SCENARIO_TASK_ROUTES = {
    "dev": "main_only_delivery",
    "prod": "main_only_delivery",
    "bugfix": "main_only_delivery",
    "hot_bugfix": "external_emergency_first_then_git_backfill_then_main_only_delivery",
    "issue": "issue_metadata_then_agent_pickup_gates",
    "goal": "roadmap_control_path",
}
REQUIRED_SCENARIO_POLICY = {
    "schema": "bears-agent-github-dev-cd-scenario-policy.v1",
    "classifier": {
        "schema": TASK_CLASSIFICATION_SCHEMA,
        "command": TASK_CLASSIFICATION_COMMAND,
        "development_scenarios": list(DEVELOPMENT_SCENARIOS),
        "markers": SCENARIO_MARKER_DESCRIPTIONS,
        "conflicting_markers_create_separate_tasks": True,
        "separate_subagent_per_task_required": False,
        "no_marker_status": "needs_scenario_marker",
    },
    "runtime": {
        "agent_current_runtime": AGENT_CURRENT_RUNTIME,
        "production_branch": "main",
        "development_branch": "dev",
        "plugin_root_production_mutation_allowed": False,
        "production_mutation_authority": "external_emergency_authority_only",
    },
    "defaults": {
        "auto_merge_to_main_allowed": False,
        "plugin_root_production_mutation_allowed": False,
    },
    "verify_command": SCENARIO_POLICY_VERIFY_COMMAND,
    "scenarios": {
        "dev": {
            "merge_sequence": ["work_branch", "main"],
            "target_branch": "main",
            "runtime_target": "main_only_delivery",
            "auto_cd_allowed": False,
            "auto_merge_to_main_allowed": False,
            "main_merge_actor": "operator_direct_main_commit",
            "plugin_root_production_mutation_allowed": False,
            "required_gates": ["delivery_complete"],
        },
        "prod": {
            "merge_sequence": ["work_branch", "main"],
            "target_branch": "main",
            "runtime_target": "ci_cd",
            "auto_cd_allowed": False,
            "auto_merge_to_main_allowed": False,
            "main_merge_actor": "operator_direct_main_commit",
            "plugin_root_production_mutation_allowed": False,
            "required_gates": ["delivery_complete"],
        },
        "bugfix": {
            "merge_sequence": ["work_branch", "main"],
            "target_branch": "main",
            "runtime_target": "ci_cd",
            "auto_cd_allowed": False,
            "auto_merge_to_main_allowed": False,
            "auto_merge_to_main_requires": [],
            "main_merge_actor": "operator_direct_main_commit",
            "plugin_root_production_mutation_allowed": False,
            "required_gates": ["delivery_complete"],
        },
        "hot_bugfix": {
            "merge_sequence": ["external_emergency_task", "git_backfill", "main"],
            "target_branch": "emergency_then_git",
            "runtime_target": "external_emergency_authority",
            "auto_cd_allowed": False,
            "auto_merge_to_main_allowed": False,
            "emergency_task_first_required": True,
            "git_backfill_required": True,
            "external_emergency_authority_required": True,
            "plugin_root_production_mutation_allowed": False,
            "required_gates": ["external_emergency_authority", "git_backfill_packet", "delivery_complete"],
        },
        "issue": {
            "merge_sequence": ["issue_metadata_gate", "agent_pickup_gate", "bounded_task"],
            "target_branch": "issue_selected",
            "runtime_target": "agent_current_runtime",
            "auto_cd_allowed": False,
            "auto_merge_to_main_allowed": False,
            "plugin_root_production_mutation_allowed": False,
            "required_gates": ["verify_issue_metadata", "verify_agent_pickup"],
        },
        "goal": {
            "merge_sequence": ["roadmap_control", "tasks", "scenario_reclassify"],
            "target_branch": "goal/<goal-id>",
            "runtime_target": "roadmap_control",
            "auto_cd_allowed": False,
            "auto_merge_to_main_allowed": False,
            "plugin_root_production_mutation_allowed": False,
            "required_gates": ["roadmap_control"],
        },
    },
}
REQUIRED_REFERENCE_DOC_MARKERS = (
    "development scenario",
    "classify-task",
    "verify-scenario-policy",
    "agent_current_runtime",
    "hot_bugfix",
    "external emergency authority",
    "workflow mode",
    "sequential",
    "parallel",
    "verify-live-topology",
    "classify-mode",
    "type:bugfix",
    "type:idea",
    "type:develop-ready",
    "verify-agent-pickup",
    "verify-issue-metadata",
    "Exact targets/surfaces",
    "Validation commands",
    "Safety boundary",
    "merge-authority-check",
    "verify-dev-auto-merge",
    "typed merge packet",
    MERGE_ALLOWED_STATUS,
    MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON,
    MERGE_BLOCKED_DRAFT_PR_REASON,
    MERGE_BLOCKED_OUTDATED_HEAD_REASON,
    DEV_AUTO_MERGE_ALLOWED_STATUS,
    DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET_REASON,
    "duplicate guard",
    "structured evidence",
    ISSUE_TEMPLATE_PATH,
    EVIDENCE_REPO_DIR,
    DISPATCH_ARTIFACT_PATH,
    "referenced evidence files are absent",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data



def _resolve_plugin_owned_path(path_value: str) -> Path:
    prefix = "/srv/bears/plugins/bears/"
    if path_value.startswith(prefix):
        return PLUGIN_ROOT / path_value.removeprefix(prefix)
    return PLUGIN_ROOT / path_value if not path_value.startswith("/") else Path(path_value)



def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data



def _load_platform_roles_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("platform_roles", PLUGIN_ROOT / "scripts/subagents_roles.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load subagents_roles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module



def _load_commit_message(commit_sha: str, *, repo_root: Path = PLUGIN_ROOT) -> str:
    return subprocess.check_output(["git", "show", "-s", "--format=%B", commit_sha], cwd=repo_root, text=True)



def _parse_commit_trailers(commit_message: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in commit_message.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        values[key.strip()] = value.strip()
    return values



def _validate_repo_evidence_path(key: str, path_value: str) -> str | None:
    if "\\" in path_value:
        return f"{key} must use forward-slash repo-relative paths"
    candidate = Path(path_value)
    normalized = candidate.as_posix()
    repo_prefix = f"{EVIDENCE_REPO_DIR}/"
    if candidate.is_absolute():
        return f"{key} must be repo-relative under {EVIDENCE_REPO_DIR}/"
    if ".." in candidate.parts:
        return f"{key} must not escape {EVIDENCE_REPO_DIR}/"
    if not normalized.startswith(repo_prefix):
        return f"{key} must stay under {EVIDENCE_REPO_DIR}/"
    if normalized.endswith("/"):
        return f"{key} must name a file path, not a directory"
    if normalized == EVIDENCE_REPO_DIR:
        return f"{key} must name a file under {EVIDENCE_REPO_DIR}/"
    return None



def _validate_commit_evidence(
    trailers: dict[str, str],
    *,
    repo_root: Path,
    dispatch_artifact: str,
    require_dispatch_file: bool,
) -> list[str]:
    errors: list[str] = []
    for key, expected in FIXED_TRAILER_VALUES.items():
        value = trailers.get(key, "")
        if not value:
            errors.append(f"missing commit trailer: {key}")
        elif value != expected:
            errors.append(f"commit trailer {key} must be {expected}")

    for key in REQUIRED_VALUE_TRAILERS:
        value = trailers.get(key, "")
        if not value:
            errors.append(f"missing commit trailer: {key}")
        elif value.startswith("goal/") or value.startswith("agent/") or value in {"main", "dev"}:
            errors.append(f"commit trailer {key} must be a bare goal id")

    for key in REPO_EVIDENCE_TRAILERS:
        value = trailers.get(key, "")
        if not value:
            errors.append(f"missing commit trailer: {key}")
            continue
        path_error = _validate_repo_evidence_path(key, value)
        if path_error is not None:
            errors.append(path_error)
            continue
        if not (repo_root / value).is_file():
            errors.append(f"commit trailer {key} references a missing file: {value}")

    dispatch_value = trailers.get("Kubernetes-Dispatch-Plan", "")
    if not dispatch_value:
        errors.append("missing commit trailer: Kubernetes-Dispatch-Plan")
    elif dispatch_value != dispatch_artifact:
        errors.append(f"commit trailer Kubernetes-Dispatch-Plan must be {dispatch_artifact}")
    elif require_dispatch_file and not (repo_root / dispatch_value).is_file():
        errors.append(f"commit trailer Kubernetes-Dispatch-Plan references a missing file: {dispatch_value}")
    return errors



def _errors_for_expected_mapping(mapping: dict[str, Any], expected: dict[str, Any], *, prefix: str) -> list[str]:
    errors: list[str] = []
    for key, value in expected.items():
        if mapping.get(key) != value:
            errors.append(f"{prefix}.{key} must be {value}")
    return errors



def _workflow_joined_run_blocks(jobs: dict[str, Any]) -> str:
    run_blocks: list[str] = []
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                run_blocks.append(step["run"])
    return "\n".join(run_blocks)


def _validate_parallel_validation_jobs(jobs: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = [job_id for job_id in REQUIRED_PARALLEL_CI_JOBS if not isinstance(jobs.get(job_id), dict)]
    if missing:
        errors.append("validate workflow missing parallel jobs: " + ", ".join(missing))
    if "plugin-validation" in jobs:
        errors.append("validate workflow must not keep serial jobs.plugin-validation")
    joined_run = _workflow_joined_run_blocks(jobs)
    for command in sorted(REQUIRED_CI_COMMANDS):
        if command not in joined_run:
            errors.append(f"validate workflow must run: {command}")
    for forbidden in FORBIDDEN_CI_RUNNER_TOKENS:
        if forbidden in joined_run:
            errors.append(f"validate workflow forbids duplicate/heavy runner token: {forbidden}")
    for token in (
        "python3 scripts/agent_github_dev_cd.py classify-task",
        "python3 scripts/agent_github_dev_cd.py verify-scenario-policy",
        "python3 scripts/agent_github_dev_cd.py classify-mode",
        "python3 scripts/agent_github_dev_cd.py verify-live-topology",
        "BEARS_GOAL_ID",
        "BEARS_DEVELOPMENT_SCENARIO",
    ):
        if token not in joined_run:
            errors.append(f"validate workflow validation jobs must include mode-aware token: {token}")
    if "unit-fast" in jobs:
        errors.append("validate workflow must not define jobs.unit-fast; local commit hooks own automatic fast tests")

    summary_job = jobs.get(CI_SUMMARY_JOB_ID)
    if not isinstance(summary_job, dict):
        errors.append("validate workflow must define jobs.ci-summary")
    else:
        expected_needs = sorted(job_id for job_id in REQUIRED_PARALLEL_CI_JOBS if job_id != CI_SUMMARY_JOB_ID)
        if sorted(summary_job.get("needs") or []) != expected_needs:
            errors.append("validate workflow ci-summary.needs must include every parallel validation job")
    return errors


def _validate_dev_cd_job(job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if job.get("if") != DEV_CD_JOB_IF:
        errors.append(f"validate workflow {DEV_CD_JOB_ID}.if must be {DEV_CD_JOB_IF}")
    if job.get("needs") != [CI_SUMMARY_JOB_ID]:
        errors.append("validate workflow dev-cd-gate.needs must be ['ci-summary']")
    if "needs.ci-summary.result == 'success'" not in str(job.get("if", "")):
        errors.append("validate workflow dev-cd-gate.if must require ci-summary success")
    env = job.get("env")
    if not isinstance(env, dict):
        errors.append("validate workflow dev-cd-gate.env must be an object")
    else:
        if env.get("BEARS_KUBERNETES_SOURCE_OF_TRUTH") != KUBERNETES_SOURCE_OF_TRUTH:
            errors.append(
                f"validate workflow dev-cd-gate.env.BEARS_KUBERNETES_SOURCE_OF_TRUTH must be {KUBERNETES_SOURCE_OF_TRUTH}"
            )
        if env.get("BEARS_DEV_CD_DISPATCH_ARTIFACT") != DISPATCH_ARTIFACT_PATH:
            errors.append(
                f"validate workflow dev-cd-gate.env.BEARS_DEV_CD_DISPATCH_ARTIFACT must be {DISPATCH_ARTIFACT_PATH}"
            )
        if env.get("BEARS_WORKFLOW_MODE") != DEFAULT_WORKFLOW_MODE:
            errors.append(
                f"validate workflow dev-cd-gate.env.BEARS_WORKFLOW_MODE must be {DEFAULT_WORKFLOW_MODE}"
            )
        if env.get("BEARS_DEVELOPMENT_SCENARIO") != "dev":
            errors.append("validate workflow dev-cd-gate.env.BEARS_DEVELOPMENT_SCENARIO must be dev")
    steps = job.get("steps")
    if not isinstance(steps, list):
        return errors + ["validate workflow dev-cd-gate.steps must be a list"]

    step_map = {
        step.get("id"): step
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("id"), str)
    }
    missing = [step_id for step_id in REQUIRED_DEV_CD_STEP_IDS if step_id not in step_map]
    if missing:
        errors.append("validate workflow dev-cd-gate missing step ids: " + ", ".join(missing))
        return errors

    validate_step = step_map["validate-governance"]
    if validate_step.get("run") != "python3 scripts/agent_github_dev_cd.py validate":
        errors.append(
            "validate workflow dev-cd-gate step validate-governance must run python3 scripts/agent_github_dev_cd.py validate"
        )

    review_run = str(step_map["verify-state-file-gate"].get("run", ""))
    for token in REQUIRED_VERIFY_EVIDENCE_COMMAND_TOKENS:
        if token not in review_run:
            errors.append(
                f"validate workflow dev-cd-gate step verify-state-file-gate must include token: {token}"
            )

    secret_run = str(step_map["verify-no-secrets"].get("run", ""))
    for token in ("secrets\\.", "kubectl", "helm", "Production-Deploy:\\s*true"):
        if token not in secret_run:
            errors.append(f"validate workflow dev-cd-gate step verify-no-secrets must guard against {token}")

    dispatch_run = str(step_map["write-dispatch-plan"].get("run", ""))
    for token in REQUIRED_WRITE_DISPATCH_COMMAND_TOKENS:
        if token not in dispatch_run:
            errors.append(f"validate workflow dev-cd-gate step write-dispatch-plan must include {token}")

    upload_step = step_map["upload-dispatch-plan"]
    if upload_step.get("uses") != "actions/upload-artifact@v4":
        errors.append("validate workflow dev-cd-gate step upload-dispatch-plan must use actions/upload-artifact@v4")
    with_block = upload_step.get("with")
    if not isinstance(with_block, dict):
        errors.append("validate workflow dev-cd-gate step upload-dispatch-plan.with must be an object")
    else:
        if with_block.get("name") != DISPATCH_ARTIFACT_NAME:
            errors.append(
                f"validate workflow dev-cd-gate step upload-dispatch-plan.with.name must be {DISPATCH_ARTIFACT_NAME}"
            )
        if with_block.get("path") != DISPATCH_ARTIFACT_PATH:
            errors.append(
                f"validate workflow dev-cd-gate step upload-dispatch-plan.with.path must be {DISPATCH_ARTIFACT_PATH}"
            )
    return errors



def _validate_reference_doc(reference_doc_path: Path) -> list[str]:
    text = reference_doc_path.read_text(encoding="utf-8")
    errors: list[str] = []
    if REQUIRED_PARENT_ACTIONS_DOC_LINE not in text:
        errors.append("reference doc must list the canonical allowed parent action tokens")
    if REQUIRED_FORBIDDEN_ACTIONS_DOC_LINE not in text:
        errors.append("reference doc must list the canonical forbidden parent action tokens")
    for marker in REQUIRED_REFERENCE_DOC_MARKERS:
        if marker not in text:
            errors.append(f"reference doc must mention {marker}")
    for action in DRIFTED_PARENT_AGENT_ACTIONS:
        if action in text:
            errors.append(f"reference doc must not contain drifted parent action token: {action}")
    return errors



def _validate_workflow_modes_block(workflow_modes: dict[str, Any], *, prefix: str) -> list[str]:
    errors = _errors_for_expected_mapping(
        workflow_modes,
        {
            "default_mode": REQUIRED_WORKFLOW_MODE_RULES["default_mode"],
            "allowed_modes": REQUIRED_WORKFLOW_MODE_RULES["allowed_modes"],
            "mode_transition_rules": REQUIRED_WORKFLOW_MODE_RULES["mode_transition_rules"],
        },
        prefix=prefix,
    )
    for mode in ALLOWED_WORKFLOW_MODES:
        mode_rules = workflow_modes.get(mode)
        if not isinstance(mode_rules, dict):
            errors.append(f"{prefix}.{mode} must be an object")
            continue
        expected = REQUIRED_WORKFLOW_MODE_RULES[mode]
        errors.extend(_errors_for_expected_mapping(mode_rules, expected, prefix=f"{prefix}.{mode}"))
    return errors



def _validate_issue_type_policy(policy: Any, *, prefix: str) -> list[str]:
    if not isinstance(policy, dict):
        return [f"{prefix} must be an object"]
    return _errors_for_expected_mapping(
        policy,
        {
            "issue_identifiers": REQUIRED_ISSUE_TYPE_POLICY["issue_identifiers"],
            "develop_ready": REQUIRED_ISSUE_TYPE_POLICY["develop_ready"],
            "type_label_guard": REQUIRED_ISSUE_TYPE_POLICY["type_label_guard"],
            "agent_pickup": REQUIRED_ISSUE_TYPE_POLICY["agent_pickup"],
        },
        prefix=prefix,
    )


def _validate_merge_authority_policy(policy: Any, *, prefix: str) -> list[str]:
    if not isinstance(policy, dict):
        return [f"{prefix} must be an object"]
    return _errors_for_expected_mapping(policy, REQUIRED_MERGE_AUTHORITY_POLICY, prefix=prefix)


def _validate_dev_auto_merge_policy(policy: Any, *, prefix: str) -> list[str]:
    if not isinstance(policy, dict):
        return [f"{prefix} must be an object"]
    return _errors_for_expected_mapping(policy, REQUIRED_DEV_AUTO_MERGE_POLICY, prefix=prefix)


def _validate_scenario_policy(policy: Any, *, prefix: str) -> list[str]:
    if not isinstance(policy, dict):
        return [f"{prefix} must be an object"]
    return _errors_for_expected_mapping(policy, REQUIRED_SCENARIO_POLICY, prefix=prefix)


def _packet_value(packet: dict[str, Any], *paths: tuple[str, ...], default: Any = None) -> Any:
    for path in paths:
        value: Any = packet
        for key in path:
            if not isinstance(value, dict) or key not in value:
                break
            value = value[key]
        else:
            return value
    return default


def _packet_bool(packet: dict[str, Any], *paths: tuple[str, ...]) -> bool:
    return _packet_value(packet, *paths, default=False) is True


def _has_marker(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text) is not None for pattern in patterns)


def classify_task_prompt(prompt: str) -> dict[str, Any]:
    text = prompt.casefold()
    hot_bugfix_text = re.sub(r"\bhot[ -]?(?:bug)?fix\b|\bhot[ -]?bugfix\b|\bhotfix\b", " ", text)
    markers = {
        "dev": _has_marker(text, r"\bdev\b", r"\bdevelopment\b"),
        "prod": _has_marker(text, r"\bprod\b", r"\bproduction\b"),
        "bugfix": _has_marker(hot_bugfix_text, r"\bbugfix\b", r"\bbug\b", r"\bfix\b"),
        "hot_bugfix": _has_marker(text, r"\bhot[ -]?bugfix\b", r"\bhotfix\b", r"\bhot[ -]?fix\b"),
        "issue": _has_marker(text, r"\bissues?\b", r"#[0-9]+\b"),
        "goal": _has_marker(text, r"(?<!\S)/goal(?!\S)", r"(?<!\S)/goal\b"),
    }
    detected = [scenario for scenario in DEVELOPMENT_SCENARIOS if markers[scenario]]
    split_required = len(detected) > 1
    tasks = [
        {
            "task_id": f"development-scenario-{scenario}-{index}",
            "development_scenario": scenario,
            "route": SCENARIO_TASK_ROUTES[scenario],
            "recommended_role": SCENARIO_RECOMMENDED_ROLES[scenario],
            "requires_separate_subagent": split_required,
            "policy_command": SCENARIO_POLICY_VERIFY_COMMAND,
        }
        for index, scenario in enumerate(detected, start=1)
    ]
    status = "split_required" if split_required else "classified"
    reasons: list[str] = []
    if not detected:
        status = "needs_scenario_marker"
        reasons.append("no development scenario marker found")
    return {
        "schema": TASK_CLASSIFICATION_SCHEMA,
        "status": status,
        "markers": markers,
        "detected_scenarios": detected,
        "split_required": split_required,
        "tasks": tasks,
        "reasons": reasons,
    }


def evaluate_scenario_policy_packet(packet: dict[str, Any]) -> dict[str, Any]:
    scenario = str(packet.get("development_scenario", ""))
    reasons: list[str] = []
    if packet.get("schema") != SCENARIO_POLICY_PACKET_SCHEMA:
        reasons.append(f"schema must be {SCENARIO_POLICY_PACKET_SCHEMA}")
    if scenario not in DEVELOPMENT_SCENARIOS:
        reasons.append("development_scenario must be one of: " + ", ".join(DEVELOPMENT_SCENARIOS))
        scenario_policy: dict[str, Any] = {}
    else:
        scenario_policy = REQUIRED_SCENARIO_POLICY["scenarios"][scenario]

    source_branch = _packet_value(packet, ("branch", "source"), ("source_branch",), default="")
    target_branch = _packet_value(packet, ("branch", "target"), ("target_branch",), default="")
    runtime_target = _packet_value(packet, ("runtime", "target"), ("runtime_target",), default="")
    auto_cd_requested = _packet_bool(packet, ("cd", "auto_cd_requested"), ("auto_cd_requested",))
    auto_merge_to_main_requested = _packet_bool(
        packet,
        ("merge", "auto_merge_to_main_requested"),
        ("auto_merge_to_main_requested",),
    )
    main_merge_actor = _packet_value(packet, ("merge", "main_merge_actor"), ("main_merge_actor",), default="")
    plugin_root_production_mutation_requested = _packet_bool(
        packet,
        ("runtime", "plugin_root_production_mutation_requested"),
        ("plugin_root_production_mutation_requested",),
    )

    if plugin_root_production_mutation_requested:
        reasons.append(
            "plugin root does not mutate production; scenario may route external emergency authority"
        )
    if auto_merge_to_main_requested and not scenario_policy.get("auto_merge_to_main_allowed", False):
        reasons.append(f"auto merge to main is blocked for development_scenario={scenario}")

    if scenario == "dev":
        if target_branch and target_branch != "main":
            reasons.append("dev scenario target_branch must be main under main-only delivery")
        if runtime_target and runtime_target != "main_only_delivery":
            reasons.append("dev scenario runtime_target must be main_only_delivery")
        if auto_cd_requested:
            reasons.append("dev scenario auto CD is blocked under main-only delivery")
    elif scenario == "prod":
        if main_merge_actor and main_merge_actor != "operator_direct_main_commit":
            reasons.append("prod scenario main merge actor must be operator_direct_main_commit")
        if target_branch and target_branch != "main":
            reasons.append("prod scenario target_branch must be main under main-only delivery")
    elif scenario == "bugfix":
        if auto_merge_to_main_requested:
            reasons.append("bugfix auto merge to main is blocked under main-only delivery")
        if target_branch and target_branch != "main":
            reasons.append("bugfix scenario target_branch must be main under main-only delivery")
    elif scenario == "hot_bugfix":
        if not _packet_bool(packet, ("hot_bugfix", "emergency_task_first"), ("emergency_task_first",)):
            reasons.append("hot_bugfix requires emergency_task_first")
        if not _packet_bool(packet, ("hot_bugfix", "git_backfill_packet"), ("git_backfill_packet",)):
            reasons.append("hot_bugfix requires git_backfill_packet")
        if not _packet_bool(packet, ("hot_bugfix", "external_emergency_authority"), ("external_emergency_authority",)):
            reasons.append("hot_bugfix requires external_emergency_authority")
    elif scenario == "issue":
        if not _packet_bool(packet, ("issue", "metadata_gate_passed"), ("issue_metadata_gate_passed",)):
            reasons.append("issue scenario requires issue_metadata_gate_passed")
        if not _packet_bool(packet, ("issue", "agent_pickup_gate_passed"), ("agent_pickup_gate_passed",)):
            reasons.append("issue scenario requires agent_pickup_gate_passed")
    elif scenario == "goal":
        if not _packet_bool(packet, ("goal", "roadmap_control_gate_passed"), ("roadmap_control_gate_passed",)):
            reasons.append("goal scenario requires roadmap_control_gate_passed")

    status = "pass" if not reasons else "fail"
    return {
        "schema": SCENARIO_POLICY_EVALUATION_SCHEMA,
        "status": status,
        "development_scenario": scenario,
        "allowed": status == "pass",
        "scenario_policy": scenario_policy,
        "reasons": reasons,
    }


def _walk_string_values(value: Any, *, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, dict):
        items: list[tuple[str, str]] = []
        for key, child in value.items():
            items.extend(_walk_string_values(child, path=f"{path}.{key}"))
        return items
    if isinstance(value, list):
        items = []
        for index, child in enumerate(value):
            items.extend(_walk_string_values(child, path=f"{path}[{index}]"))
        return items
    return []


def _is_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return value is not None



def _gate_status(value: Any) -> str:
    if isinstance(value, dict):
        status = value.get("status")
        if isinstance(status, str):
            return status
    if isinstance(value, str):
        return value
    return ""


def _is_safe_relative_ref(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.casefold() in PLACEHOLDER_EVIDENCE_VALUES:
        return False
    path = Path(text)
    if path.is_absolute():
        return False
    if ".." in path.parts:
        return False
    return True


def _has_concrete_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in PLACEHOLDER_EVIDENCE_VALUES


def _validate_structured_evidence_object(value: Any, field: str) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, dict):
        return [f"agent pickup requires {field} structured evidence object"]
    status = value.get("status")
    if status not in {"pass", "ok", "approved", "accepted", "skipped"}:
        reasons.append(f"agent pickup {field}.status must be pass, ok, approved, accepted, or skipped")
    evidence_ref = value.get("evidence_path", value.get("source_ref"))
    if not _is_safe_relative_ref(evidence_ref):
        reasons.append(f"agent pickup {field} requires safe evidence_path or source_ref")
    has_command_result = _has_concrete_text(value.get("command")) and _has_concrete_text(value.get("result"))
    has_decision = _has_concrete_text(value.get("approved_skip_reason")) or _has_concrete_text(value.get("decision_reason"))
    if not has_command_result and not has_decision:
        reasons.append(f"agent pickup {field} requires command/result or approved skip/decision reason")
    return reasons


def _validate_route_gate(value: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, dict):
        return ["agent pickup requires route gate evidence"]
    if _gate_status(value) not in {"pass", "ok", "matched", "approved"}:
        reasons.append("agent pickup requires route gate evidence")
    if not _has_concrete_text(value.get("target")):
        reasons.append("agent pickup route_gate.target is required")
    if not (_has_concrete_text(value.get("concrete_part")) or _has_concrete_text(value.get("route_result"))):
        reasons.append("agent pickup route_gate requires concrete_part or route_result")
    if not (_has_concrete_text(value.get("owning_role")) or _has_concrete_text(value.get("primary_role"))):
        reasons.append("agent pickup route_gate requires owning_role or primary_role")
    return reasons


def _validate_task_packet(value: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, dict) or not value:
        return ["agent pickup requires task_packet"]
    if not (_has_concrete_text(value.get("issue")) or _has_concrete_text(value.get("issue_number")) or _has_concrete_text(value.get("id"))):
        reasons.append("agent pickup task_packet requires issue or id")
    if not (_has_concrete_text(value.get("bounded_target")) or _has_concrete_text(value.get("scope"))):
        reasons.append("agent pickup task_packet requires bounded_target or scope")
    for list_field in ("allowed_write_surfaces", "allowed_read_surfaces", "validation_commands"):
        values = value.get(list_field)
        if not isinstance(values, list) or not values or not all(_has_concrete_text(item) for item in values):
            reasons.append(f"agent pickup task_packet.{list_field} must list concrete values")
    if not _has_concrete_text(value.get("owning_role")):
        reasons.append("agent pickup task_packet.owning_role is required")
    if not _has_concrete_text(value.get("safety_boundary")):
        reasons.append("agent pickup task_packet.safety_boundary is required")
    return reasons


def _validate_duplicate_guard(value: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, dict):
        return ["agent pickup requires duplicate_guard"]
    if value.get("status") != "unique" or value.get("duplicates_found") is not False:
        reasons.append("agent pickup duplicate guard must prove unique issue scope")
    for field in ("repository", "normalized_scope_key", "checked_at", "evidence_summary"):
        if not _has_concrete_text(value.get(field)):
            reasons.append(f"agent pickup duplicate_guard.{field} is required")
    checked_issues = value.get("checked_issues")
    has_checked_issues = isinstance(checked_issues, list) and all(isinstance(item, (str, int, dict)) for item in checked_issues)
    if not _has_concrete_text(value.get("search_query")) and not has_checked_issues:
        reasons.append("agent pickup duplicate_guard requires search_query or checked_issues")
    if value.get("matching_open_issues") or value.get("active_workers") or value.get("duplicate_issue"):
        reasons.append("agent pickup duplicate guard found matching open issue or active worker")
    if value.get("repository") != "BearsCLOUD/bears_plugin":
        reasons.append("agent pickup duplicate_guard.repository must be BearsCLOUD/bears_plugin")
    return reasons


def _validate_dry_run(value: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, dict) or value.get("status") != "pass":
        return ["agent pickup requires dry_run.status pass before dispatch"]
    if not _has_concrete_text(value.get("command")):
        reasons.append("agent pickup dry_run.command is required")
    proof = value.get("proof_path")
    result = value.get("result")
    if not _is_safe_relative_ref(proof) and not _has_concrete_text(result):
        reasons.append("agent pickup dry_run requires result or safe proof_path")
    return reasons


def _validate_issue_template_contract(template: Any, config: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(template, dict):
        return [f"issue template {ISSUE_TEMPLATE_PATH} must be a YAML object"]
    labels = template.get("labels")
    if labels != [ISSUE_TYPE_IDENTIFIERS["idea"]]:
        errors.append("issue template must keep type:idea as default intake label")
    body = template.get("body")
    if not isinstance(body, list):
        return errors + ["issue template body must be a list"]
    field_ids = [item.get("id") for item in body if isinstance(item, dict)]
    missing = [item for item in ISSUE_TEMPLATE_REQUIRED_DEVELOP_READY_FIELD_IDS if item not in field_ids]
    if missing:
        errors.append("issue template missing agent pickup develop-ready fields: " + ", ".join(missing))
    gate = next((item for item in body if isinstance(item, dict) and item.get("id") == "pre_development_gate_impact"), None)
    options = None
    if isinstance(gate, dict):
        attrs = gate.get("attributes")
        if isinstance(attrs, dict):
            options = attrs.get("options")
    if options != list(ISSUE_TEMPLATE_CANONICAL_GATE_OPTIONS):
        errors.append("issue template pre_development_gate_impact options must match canonical lifecycle gates")
    if isinstance(config, dict) and config.get("blank_issues_enabled") is not False:
        errors.append("issue template config must keep blank_issues_enabled false")
    return errors


def _contains_merge_directive(text: str) -> bool:
    normalized = " ".join(text.lower().replace("#", " #").split())
    return any(token in normalized for token in MERGE_AUTHORITY_DRIFT_TOKENS)


def _status_passes(value: Any) -> bool:
    return _gate_status(value).lower() in {"pass", "ok", "approved", "green", "success"}


def _has_named_no_ci_exception(check_policy: dict[str, Any]) -> bool:
    exception = check_policy.get("no_ci_exception")
    if isinstance(exception, dict):
        return all(
            isinstance(exception.get(key), str) and exception[key].strip()
            for key in ("name", "reason", "approved_by")
        )
    override = check_policy.get("operator_override")
    if isinstance(override, dict):
        return all(
            isinstance(override.get(key), str) and override[key].strip()
            for key in ("reason", "approved_by")
        )
    return False


def _normalize_issue_label_names(labels_value: Any) -> tuple[list[str], list[str]]:
    if not isinstance(labels_value, list):
        return [], ["issue labels must be a list"]
    labels: list[str] = []
    errors: list[str] = []
    for label in labels_value:
        if isinstance(label, str):
            labels.append(label)
        elif isinstance(label, dict) and isinstance(label.get("name"), str):
            labels.append(label["name"])
        else:
            errors.append("issue labels must be strings or objects with name")
    return labels, errors


def _is_open_issue(issue: dict[str, Any]) -> bool:
    state = issue.get("state", "open")
    if isinstance(state, str):
        return state.lower() == "open"
    return True


def _issue_identity(issue: dict[str, Any]) -> str:
    number = issue.get("number")
    if isinstance(number, int):
        return f"#{number}"
    if isinstance(number, str) and number.strip():
        return number.strip()
    title = issue.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return "<unknown>"


def _normalize_body_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    aliases = {
        "problem": "concrete_problem",
        "concrete_problem": "concrete_problem",
        "target": "exact_targets_surfaces",
        "targets": "exact_targets_surfaces",
        "surface": "exact_targets_surfaces",
        "surfaces": "exact_targets_surfaces",
        "exact_targets": "exact_targets_surfaces",
        "exact_surfaces": "exact_targets_surfaces",
        "exact_targets_surfaces": "exact_targets_surfaces",
        "change": "required_change",
        "required_change": "required_change",
        "criteria": "acceptance_criteria",
        "acceptance": "acceptance_criteria",
        "acceptance_criteria": "acceptance_criteria",
        "tests": "validation_commands",
        "validation": "validation_commands",
        "commands": "validation_commands",
        "validation_commands": "validation_commands",
        "duplicate": "duplicate_guard",
        "duplicate_guard": "duplicate_guard",
        "safety": "safety_boundary",
        "boundary": "safety_boundary",
        "safety_boundary": "safety_boundary",
    }
    return aliases.get(normalized, normalized)


def _body_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    active_key = ""
    for raw_line in body.splitlines():
        line = raw_line.strip()
        inline = re.match(r"^(?:[-*]\s*)?\*{0,2}([A-Za-z][A-Za-z0-9 /_-]+?)\*{0,2}\s*:\s*(.+)$", line)
        heading = re.match(r"^(?:#{1,6}\s*)?([A-Za-z][A-Za-z0-9 /_-]+?)\s*:?\s*$", line)
        key = ""
        content = ""
        if inline:
            key = _normalize_body_key(inline.group(1))
            content = inline.group(2).strip()
        elif heading:
            key = _normalize_body_key(heading.group(1))
        if key in DEVELOP_READY_BODY_REQUIRED_FIELDS:
            active_key = key
            sections.setdefault(active_key, [])
            if content:
                sections[active_key].append(content)
            continue
        if active_key:
            sections[active_key].append(raw_line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _body_field_is_concrete(field: str, content: str) -> bool:
    normalized = " ".join(content.strip().lower().split())
    if normalized in VAGUE_BODY_VALUES or len(normalized) < 12:
        return False
    if field == "exact_targets_surfaces":
        return any(token in content for token in ("/", ".", ":", "`"))
    if field == "validation_commands":
        return bool(re.search(r"\b(python3|python|pytest|unittest|scripts/|npm|pnpm|make|gh)\b", content))
    if field == "duplicate_guard":
        return "duplicate" in normalized and any(token in normalized for token in ("none", "no ", "unique", "search", "issue"))
    if field == "safety_boundary":
        return any(token in normalized for token in ("do not", "no ", "only", "boundary", "metadata", "secret", "production"))
    return True


def _validate_develop_ready_body(body_value: Any) -> list[str]:
    if not isinstance(body_value, str) or not body_value.strip():
        return ["type:develop-ready issue body must not be empty"]
    sections = _body_sections(body_value)
    errors: list[str] = []
    for field in DEVELOP_READY_BODY_REQUIRED_FIELDS:
        content = sections.get(field, "")
        if not _body_field_is_concrete(field, content):
            heading = DEVELOP_READY_BODY_FIELD_HEADINGS[field]
            errors.append(f"type:develop-ready issue body requires concrete {heading}")
    return errors


def evaluate_issue_metadata_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Evaluate open governance issue labels and develop-ready body readiness."""

    reasons: list[str] = []
    violations: list[dict[str, Any]] = []
    if packet.get("schema") != ISSUE_METADATA_PACKET_SCHEMA:
        reasons.append(f"issue metadata packet schema must be {ISSUE_METADATA_PACKET_SCHEMA}")
    issues_value = packet.get("issues")
    issues = issues_value if isinstance(issues_value, list) else []
    if not isinstance(issues_value, list):
        reasons.append("issue metadata packet requires issues list")

    checked_open_issues = 0
    for issue_value in issues:
        if not isinstance(issue_value, dict):
            violations.append({"issue": "<invalid>", "reasons": ["issue entry must be an object"], "type_labels": []})
            continue
        if not _is_open_issue(issue_value):
            continue
        checked_open_issues += 1
        issue_reasons: list[str] = []
        labels, label_errors = _normalize_issue_label_names(issue_value.get("labels", []))
        issue_reasons.extend(label_errors)
        type_labels = [label for label in labels if label in FIXED_ISSUE_TYPE_LABELS]
        if len(type_labels) != 1:
            issue_reasons.append(
                "open governance issue must carry exactly one fixed type label among "
                + ", ".join(FIXED_ISSUE_TYPE_LABELS)
            )
        if type_labels == [ISSUE_TYPE_IDENTIFIERS["develop_ready"]]:
            issue_reasons.extend(_validate_develop_ready_body(issue_value.get("body")))
        if issue_reasons:
            violations.append(
                {
                    "issue": _issue_identity(issue_value),
                    "type_labels": type_labels,
                    "reasons": issue_reasons,
                }
            )

    status = "blocked" if reasons or violations else "pass"
    return {
        "schema": ISSUE_METADATA_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "fixed_type_labels": list(FIXED_ISSUE_TYPE_LABELS),
        "checked_open_issues": checked_open_issues,
        "violations": violations,
        "reasons": reasons,
    }


def _path_matches_pattern(path: str, pattern: str) -> bool:
    value = path.strip().lstrip("./")
    if not value:
        return False
    pattern = pattern.strip().lstrip("./")
    if pattern.endswith("/**"):
        return value.startswith(pattern[:-3].rstrip("/") + "/")
    if "*" in pattern:
        regex = "^" + re.escape(pattern).replace("\\*", "[^/]*") + "$"
        return re.match(regex, value) is not None
    return value == pattern


def _path_matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(_path_matches_pattern(path, pattern) for pattern in patterns)


def validate_public_title(value: str) -> list[str]:
    """Return blocking reasons for a PR title or commit headline."""
    title = value.strip()
    reasons: list[str] = []
    lowered = title.lower()
    if not title:
        reasons.append("title_required")
    if any(marker in lowered for marker in FORBIDDEN_TITLE_MARKERS):
        reasons.append("title_contains_agent_marker")
    if not CONVENTIONAL_TITLE_RE.match(title):
        reasons.append("title_must_match_conventional_type_scope")
    return reasons


def lint_command_snippet(command: str, *, expected_input: bool = False) -> dict[str, Any]:
    """Lint shell/GitHub command snippets before review or merge execution."""
    reasons: list[str] = []
    normalized = command.strip()
    if re.search(r"gh\s+pr\s+diff\b[^\n]*\s--name-status\b", normalized):
        reasons.append("GH_PR_DIFF_UNSUPPORTED_NAME_STATUS")
    if re.search(r"gh\s+pr\s+diff\b[^\n]*\s--stat\b", normalized):
        reasons.append("GH_PR_DIFF_UNSUPPORTED_STAT")
    if re.search(r"gh\s+pr\s+diff\b[^\n]*\s--\s+\S+", normalized):
        reasons.append("GH_PR_DIFF_PATH_ARGS_UNSUPPORTED")
    if re.search(r"gh\s+api\b[^\n]*/contents/[^\n]*\s-f\s+ref=", normalized):
        reasons.append("GH_API_CONTENTS_REF_FLAG_UNSUPPORTED")
    if re.search(r"\b(?:urllib\.request|curl)\b[^\n]*(?:api\.github\.com|raw\.githubusercontent\.com)", normalized):
        reasons.append("AUTH_METHOD_INVALID")
    if re.search(r"\|\s*python3\s+-\s*<<['\"]?PY", normalized):
        reasons.append("STDIN_SWALLOWING_HEREDOC")
    if expected_input and re.search(r"input_bytes\s*=\s*0|diff_bytes\s*=\s*0|json_bytes\s*=\s*0", normalized):
        reasons.append("EXPECTED_INPUT_BYTES_ZERO")
    if re.search(
        r"print\([^)]*EXIT:1|echo\s+EXIT:\$rc(?!\s*;\s*exit\s+\$rc)|;\s*rc=\$\?;\s*echo\s+EXIT:\$rc(?!\s*;\s*exit\s+\$rc)",
        normalized,
    ):
        reasons.append("NONZERO_RC_NOT_PROPAGATED")
    if re.search(r"\|\|\s*true", normalized) and re.search(
        r"gh\s+pr\s+checks|validate|pytest|unittest|merge-authority",
        normalized,
    ):
        reasons.append("GATE_COMMAND_SOFTENED_WITH_OR_TRUE")
    if re.search(r"printf\s+['\"]---", normalized):
        reasons.append("UNSAFE_PRINTF_HEADING")
    if re.search(r"python3\s+-m\s+py_compile\b[^\n]*\.sh\b", normalized):
        reasons.append("COMMAND_SHAPE_DRIFT")
    if re.search(r"platform_roles\.py\s+route/audit\b", normalized):
        reasons.append("COMMAND_SHAPE_DRIFT")
    status = "COMMAND_SNIPPET_PASS" if not reasons else "COMMAND_SNIPPET_BLOCKED"
    return {
        "schema": COMMAND_SNIPPET_LINT_SCHEMA,
        "status": status,
        "allowed": status == "COMMAND_SNIPPET_PASS",
        "expected_input": expected_input,
        "reasons": reasons,
    }


def evaluate_hygiene_gate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Evaluate path-triggered deploy/CI gates for hygiene and text-cleanup workers."""
    reasons: list[str] = []
    if packet.get("schema") != HYGIENE_GATE_PACKET_SCHEMA:
        reasons.append(f"hygiene gate packet schema must be {HYGIENE_GATE_PACKET_SCHEMA}")
    paths_value = packet.get("changed_paths")
    changed_paths = paths_value if isinstance(paths_value, list) else []
    normalized_paths = [path for path in changed_paths if isinstance(path, str)]
    if len(normalized_paths) != len(changed_paths):
        reasons.append("changed_paths must be strings")
    triggered_paths = [
        path for path in normalized_paths if _path_matches_any(path, DEPLOY_CI_TRIGGER_PATTERNS)
    ]
    gate = packet.get("deploy_ci_gate")
    if triggered_paths:
        if not isinstance(gate, dict):
            reasons.append("deploy_ci_gate is required for CI, manifest, deploy, or runtime-validator paths")
        else:
            gate_status = gate.get("status")
            if gate_status in {None, "", "not-applicable", "not_applicable"}:
                reasons.append("deploy_ci_gate.status cannot be not-applicable for triggered paths")
            if gate_status not in {"pass", "needs-review", "no-runtime-impact"}:
                reasons.append("deploy_ci_gate.status must be pass, needs-review, or no-runtime-impact")
            if not _is_present(gate.get("owner_role")):
                reasons.append("deploy_ci_gate.owner_role is required")
            if not _is_present(gate.get("validation")):
                reasons.append("deploy_ci_gate.validation is required")
    status = "pass" if not reasons else "blocked"
    return {
        "schema": HYGIENE_GATE_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "triggered_paths": triggered_paths,
        "reasons": reasons,
    }


def evaluate_final_verification_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Evaluate fetch/verify/read ordering for final verification evidence."""
    reasons: list[str] = []
    if packet.get("schema") != FINAL_VERIFICATION_PACKET_SCHEMA:
        reasons.append(f"final verification packet schema must be {FINAL_VERIFICATION_PACKET_SCHEMA}")
    fetched_commit = packet.get("verified_commit")
    if not isinstance(fetched_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", fetched_commit):
        reasons.append("verified_commit must be a 40-character commit id")
    steps_value = packet.get("steps")
    steps = steps_value if isinstance(steps_value, list) else []
    if not isinstance(steps_value, list) or not steps:
        reasons.append("steps must be a non-empty list")
    step_names: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            reasons.append("steps entries must be objects")
            continue
        name = step.get("name")
        if isinstance(name, str):
            step_names.append(name)

    def _index(name: str) -> int:
        try:
            return step_names.index(name)
        except ValueError:
            return -1

    fetch_i = _index("fetch")
    verify_i = _index("verify_commit")
    if fetch_i < 0:
        reasons.append("fetch step is required")
    if verify_i < 0:
        reasons.append("verify_commit step is required")
    if fetch_i >= 0 and verify_i >= 0 and fetch_i > verify_i:
        reasons.append("fetch must complete before verify_commit")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        if step.get("reads_dependent_ref") is True:
            if verify_i < 0 or index < verify_i:
                reasons.append("dependent reads must run after verify_commit")
            ref = step.get("ref")
            if ref in {"origin/main", "HEAD"}:
                reasons.append("dependent reads must use verified_commit, not moving ref")
            if fetched_commit and step.get("commit") != fetched_commit:
                reasons.append("dependent read commit must match verified_commit")
        if step.get("parallel_with_fetch") is True and step.get("reads_dependent_ref") is True:
            reasons.append("dependent reads cannot run in parallel with fetch")
    status = "pass" if not reasons else "blocked"
    return {
        "schema": FINAL_VERIFICATION_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "verified_commit": fetched_commit if isinstance(fetched_commit, str) else "",
        "reasons": reasons,
    }


def evaluate_pr_publication_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Evaluate PR publication, ready, or merge guard evidence."""
    reasons: list[str] = []
    if packet.get("schema") != PR_PUBLICATION_PACKET_SCHEMA:
        reasons.append(f"PR publication packet schema must be {PR_PUBLICATION_PACKET_SCHEMA}")
    for field in ("pr_title", "commit_headline"):
        value = packet.get(field)
        if not isinstance(value, str):
            reasons.append(f"{field} must be a string")
        else:
            for reason in validate_public_title(value):
                reasons.append(f"{field}:{reason}")
    branch_preflight = packet.get("branch_base_preflight")
    if not isinstance(branch_preflight, dict) or branch_preflight.get("status") != "BRANCH_BASE_PREFLIGHT_PASS":
        reasons.append("branch_base_preflight must pass before publish")
    checks_gate = packet.get("github_checks_gate")
    if isinstance(checks_gate, dict):
        gate_status = checks_gate.get("status")
        if gate_status in {"FAIL_NO_CHECKS", "fail", "blocked"}:
            reasons.append("github_checks_gate blocks publication")
        if checks_gate.get("exit_code") not in (0, None) and checks_gate.get("override") is not True:
            reasons.append("github_checks_gate nonzero exit requires explicit override")
    elif packet.get("action") in {"merge", "mark_ready"}:
        reasons.append("github_checks_gate is required before ready or merge")
    hygiene_packet = packet.get("hygiene_gate")
    if isinstance(hygiene_packet, dict):
        hygiene_result = evaluate_hygiene_gate_packet(hygiene_packet)
        if hygiene_result["status"] != "pass":
            reasons.extend(f"hygiene_gate:{reason}" for reason in hygiene_result["reasons"])
    status = "pass" if not reasons else "blocked"
    return {
        "schema": PR_PUBLICATION_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "reasons": reasons,
    }


def _append_unique_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _is_false(value: Any) -> bool:
    return value is False


def _pull_request_indicates_outdated_head(pull_request: Any, packet: dict[str, Any]) -> bool:
    if not isinstance(pull_request, dict):
        return False

    packet_head_sha = packet.get("head_sha")
    packet_head_ref = packet.get("head_ref")
    packet_base_ref = packet.get("base_ref")
    current_head_sha = (
        pull_request.get("current_head_sha")
        or pull_request.get("head_sha")
        or pull_request.get("headRefOid")
        or pull_request.get("headRefOid".lower())
    )
    current_head_ref = pull_request.get("current_head_ref") or pull_request.get("head_ref") or pull_request.get("headRefName")
    current_base_ref = pull_request.get("current_base_ref") or pull_request.get("base_ref") or pull_request.get("baseRefName")

    if isinstance(current_head_sha, str) and isinstance(packet_head_sha, str) and current_head_sha != packet_head_sha:
        return True
    if isinstance(current_head_ref, str) and isinstance(packet_head_ref, str) and current_head_ref != packet_head_ref:
        return True
    if isinstance(current_base_ref, str) and isinstance(packet_base_ref, str) and current_base_ref != packet_base_ref:
        return True

    for flag in (
        "head_is_current",
        "base_is_current",
        "branch_is_current",
        "head_current",
        "base_current",
        "branch_current",
        "is_current",
    ):
        if _is_false(pull_request.get(flag)):
            return True

    behind_by = pull_request.get("behind_by")
    if isinstance(behind_by, int) and behind_by > 0:
        return True

    merge_state_status = pull_request.get("merge_state_status") or pull_request.get("mergeStateStatus")
    if isinstance(merge_state_status, str) and merge_state_status.upper() in {"BEHIND", "OUTDATED", "STALE"}:
        return True

    return False


def _merge_eligibility_guard_reasons(
    packet: dict[str, Any],
    *,
    action: Any,
    expected: dict[str, Any] | None,
) -> list[str]:
    if action != "merge":
        return []

    guard_reasons: list[str] = []

    check_policy = packet.get("check_policy")
    if isinstance(check_policy, dict) and check_policy.get("check_count") == 0:
        _append_unique_reason(guard_reasons, MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON)

    draft_policy = packet.get("draft_policy")
    if isinstance(draft_policy, dict) and draft_policy.get("is_draft") is not False:
        _append_unique_reason(guard_reasons, MERGE_BLOCKED_DRAFT_PR_REASON)

    if not expected:
        _append_unique_reason(guard_reasons, MERGE_BLOCKED_OUTDATED_HEAD_REASON)
    else:
        for field in ("head_ref", "head_sha", "base_ref"):
            expected_value = expected.get(field)
            if _is_present(expected_value) and packet.get(field) != expected_value:
                _append_unique_reason(guard_reasons, MERGE_BLOCKED_OUTDATED_HEAD_REASON)
                break

    if _pull_request_indicates_outdated_head(packet.get("pull_request"), packet):
        _append_unique_reason(guard_reasons, MERGE_BLOCKED_OUTDATED_HEAD_REASON)

    return guard_reasons


def _merge_eligibility_result(*, action: Any, status: str, reasons: list[str]) -> tuple[str, str]:
    if action != "merge":
        return MERGE_NOT_REQUESTED_STATUS, ""
    if status == "pass":
        return MERGE_ALLOWED_STATUS, MERGE_ALLOWED_STATUS
    guard_reasons = [reason for reason in MERGE_ELIGIBILITY_GUARD_REASONS if reason in reasons]
    return MERGE_BLOCKED_STATUS, (guard_reasons[0] if guard_reasons else MERGE_BLOCKED_POLICY_REASON)




def _expected_merge_authority_from_assignment(assignment_packet: Any) -> dict[str, Any]:
    if not isinstance(assignment_packet, dict):
        return {}
    merge_authority = assignment_packet.get("merge_authority")
    if isinstance(merge_authority, dict):
        return merge_authority
    return {}


def _pull_request_number(value: Any) -> int | None:
    if isinstance(value, dict):
        number = value.get("number")
        return number if isinstance(number, int) else None
    return None


def _merge_expected_values_from_args(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if getattr(args, "expected_repository", ""):
        values["repository"] = args.expected_repository
    if getattr(args, "expected_pr_number", None) is not None:
        values["pull_request_number"] = args.expected_pr_number
    if getattr(args, "expected_head_ref", ""):
        values["head_ref"] = args.expected_head_ref
    if getattr(args, "expected_head_sha", ""):
        values["head_sha"] = args.expected_head_sha
    if getattr(args, "expected_base_ref", ""):
        values["base_ref"] = args.expected_base_ref
    return values


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _check_policy_passed_contexts(check_policy: Any) -> set[str]:
    if not isinstance(check_policy, dict):
        return set()
    contexts = _string_list(check_policy.get("passed_contexts"))
    if not contexts:
        contexts = _string_list(check_policy.get("check_contexts"))
    if not contexts:
        contexts = _string_list(check_policy.get("checks"))
    return set(contexts)


def _dev_auto_merge_context_reasons(check_policy: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(check_policy, dict):
        return ["dev auto-merge requires check_policy object"]
    passed_contexts = _check_policy_passed_contexts(check_policy)
    required_contexts = set(DEV_AUTO_MERGE_REQUIRED_CHECK_CONTEXTS)
    if not required_contexts.issubset(passed_contexts):
        missing = sorted(required_contexts - passed_contexts)
        reasons.append("dev auto-merge check_policy.passed_contexts must include: " + ", ".join(missing))
    return reasons


def _append_expected_mismatch_errors(
    reasons: list[str],
    packet: dict[str, Any],
    expected: dict[str, Any],
    *,
    source: str,
) -> None:
    if not expected:
        return
    comparisons = {
        "repository": packet.get("repository"),
        "pull_request_number": _pull_request_number(packet.get("pull_request")),
        "head_ref": packet.get("head_ref"),
        "head_sha": packet.get("head_sha"),
        "base_ref": packet.get("base_ref"),
    }
    for key, expected_value in expected.items():
        if key not in comparisons:
            continue
        if comparisons[key] != expected_value:
            reasons.append(f"{source}.{key} must match packet {key}")


def evaluate_merge_authority_packet(
    packet: dict[str, Any],
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate merge or ready authority without mutating GitHub state."""

    reasons: list[str] = []
    workflow_drift = False
    handoff_required = False

    request_source = packet.get("request_source")
    if isinstance(request_source, dict):
        instruction_text = request_source.get("instruction_text")
        if (
            request_source.get("actor") == "parent_control"
            and request_source.get("channel") == "send_input"
            and isinstance(instruction_text, str)
            and _contains_merge_directive(instruction_text)
            and packet.get("schema") != MERGE_AUTHORITY_PACKET_SCHEMA
        ):
            workflow_drift = True
            reasons.append("plain parent send_input merge directive is workflow drift")

    if packet.get("schema") != MERGE_AUTHORITY_PACKET_SCHEMA:
        reasons.append(f"merge authority packet schema must be {MERGE_AUTHORITY_PACKET_SCHEMA}")
    else:
        for field in MERGE_AUTHORITY_REQUIRED_FIELDS:
            if not _is_present(packet.get(field)):
                reasons.append(f"merge authority packet requires {field}")
        expected_required_fields = ("repository", "pull_request_number", "head_ref", "head_sha", "base_ref")
        if not expected:
            reasons.append("merge authority check requires live expected PR/head binding")
        else:
            for field in expected_required_fields:
                if not _is_present(expected.get(field)):
                    reasons.append(f"expected.{field} is required")

        if not _status_passes(packet.get("pre_task_hook")):
            reasons.append("pre_task_hook must pass before merge authority")
        assignment_packet = packet.get("assignment_packet")
        if not isinstance(assignment_packet, dict):
            reasons.append("assignment_packet must be an object")
        assignment_expected = _expected_merge_authority_from_assignment(assignment_packet)
        if not assignment_expected:
            reasons.append("assignment_packet.merge_authority must bind exact PR and head")
        else:
            for field in ("repository", "pull_request_number", "head_ref", "head_sha", "base_ref"):
                if field not in assignment_expected:
                    reasons.append(f"assignment_packet.merge_authority requires {field}")
            _append_expected_mismatch_errors(reasons, packet, assignment_expected, source="assignment_packet.merge_authority")
        _append_expected_mismatch_errors(reasons, packet, expected or {}, source="expected")

        pull_request = packet.get("pull_request")
        if not isinstance(pull_request, dict):
            reasons.append("pull_request must be an object")
        else:
            number = pull_request.get("number")
            if not isinstance(number, int) or number <= 0:
                reasons.append("pull_request.number must be a positive integer")

        for field in ("repository", "head_ref", "head_sha", "base_ref", "rollback_note"):
            value = packet.get(field)
            if not isinstance(value, str) or not value.strip():
                reasons.append(f"{field} must be a non-empty string")
        head_sha = packet.get("head_sha")
        if isinstance(head_sha, str) and not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha.strip()):
            reasons.append("head_sha must be the exact 40-character PR head SHA")

        action = packet.get("action")
        if action not in MERGE_AUTHORITY_ACTIONS:
            reasons.append("action must be mark_ready or merge")

        check_policy = packet.get("check_policy")
        if not isinstance(check_policy, dict):
            reasons.append("check_policy must be an object")
        else:
            if not _status_passes(check_policy):
                reasons.append("check_policy.status must be pass before merge authority")
            if check_policy.get("github_checks_gate") == "FAIL_NO_CHECKS":
                reasons.append(MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON)
            if check_policy.get("exit_code") not in (0, None):
                reasons.append("check_policy.exit_code must be zero for required gates")
            check_count = check_policy.get("check_count")
            if not isinstance(check_count, int) or check_count < 0:
                reasons.append("check_policy.check_count must be a non-negative integer")
            elif action == "merge" and check_count == 0:
                reasons.append(MERGE_BLOCKED_EMPTY_CHECK_ROLLUP_REASON)

        state_file_policy = packet.get("state_file_policy")
        if not isinstance(state_file_policy, dict):
            reasons.append("state_file_policy must be an object")
        else:
            if not _status_passes(state_file_policy):
                reasons.append("state_file_policy.status must be pass before merge authority")
            required_refs = state_file_policy.get("required_state_refs")
            if not isinstance(required_refs, list) or not {"workflow_state", "merge_authority_state"}.issubset(set(required_refs)):
                reasons.append("state_file_policy.required_state_refs must include workflow_state and merge_authority_state")
            state_refs = state_file_policy.get("state_refs")
            if not isinstance(state_refs, dict):
                reasons.append("state_file_policy.state_refs must be an object")
            else:
                for ref_name in ("workflow_state", "merge_authority_state"):
                    if not _is_present(state_refs.get(ref_name)):
                        reasons.append(f"state_file_policy.state_refs.{ref_name} is required")
            if state_file_policy.get("authoritative_state_source") != "machine_readable_state_files":
                reasons.append("state_file_policy.authoritative_state_source must be machine_readable_state_files")
            authority_sources = state_file_policy.get("authority_sources")
            if not isinstance(authority_sources, list) or not {"workflow_state", "merge_authority_state"}.issubset(set(authority_sources)):
                reasons.append("state_file_policy.authority_sources must include workflow_state and merge_authority_state")
            if state_file_policy.get("non_state_authority_allowed") is not False:
                reasons.append("state_file_policy.non_state_authority_allowed must be false")

        title_policy = packet.get("title_policy")
        if not isinstance(title_policy, dict):
            reasons.append("title_policy must be an object")
        else:
            if not _status_passes(title_policy):
                reasons.append("title_policy.status must be pass")
            if title_policy.get("validated_before_ready") is not True:
                reasons.append("PR title validation must run before gh pr ready")
            if action == "merge" and title_policy.get("validated_before_merge") is not True:
                reasons.append("PR title validation must run before merge")
            title_value = title_policy.get("title") or packet.get("pr_title")
            if isinstance(title_value, str):
                reasons.extend(f"title_policy:{reason}" for reason in validate_public_title(title_value))
            commit_headline = title_policy.get("commit_headline") or packet.get("commit_headline")
            if isinstance(commit_headline, str):
                reasons.extend(f"commit_policy:{reason}" for reason in validate_public_title(commit_headline))

        draft_policy = packet.get("draft_policy")
        if not isinstance(draft_policy, dict):
            reasons.append("draft_policy must be an object")
        elif action == "merge" and draft_policy.get("is_draft") is not False:
            reasons.append(MERGE_BLOCKED_DRAFT_PR_REASON)

        authority = packet.get("authority")
        if not isinstance(authority, dict):
            reasons.append("authority must be an object")
        else:
            source = authority.get("source")
            if source not in REQUIRED_MERGE_AUTHORITY_POLICY["authority"]["allowed_sources"]:
                reasons.append("authority.source must be operator_request or contract_authority")
            if source == "parent_send_input":
                workflow_drift = True
                reasons.append("parent send_input is not merge authority")
            if not _is_present(authority.get("evidence")):
                reasons.append("authority.evidence is required")

        conflict_policy = packet.get("conflict_policy")
        if not isinstance(conflict_policy, dict):
            reasons.append("conflict_policy must be an object")
        else:
            mergeable_state = conflict_policy.get("mergeable_state")
            if action == "merge" and mergeable_state != "CLEAN":
                handoff_required = True
                reasons.append("mergeable_state must be CLEAN before merge")

        for guard_reason in _merge_eligibility_guard_reasons(packet, action=action, expected=expected):
            _append_unique_reason(reasons, guard_reason)

    status = "pass" if not reasons else ("workflow_drift" if workflow_drift else "blocked")
    merge_eligibility_status, merge_eligibility_reason = _merge_eligibility_result(
        action=packet.get("action"),
        status=status,
        reasons=reasons,
    )
    return {
        "schema": MERGE_AUTHORITY_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "merge_eligibility_status": merge_eligibility_status,
        "merge_eligibility_reason": merge_eligibility_reason,
        "classification": (
            "MERGE_AUTHORITY_READY"
            if status == "pass"
            else ("MERGE_AUTHORITY_DRIFT" if workflow_drift else "MERGE_AUTHORITY_BLOCKED")
        ),
        "handoff_required": handoff_required,
        "handoff_target": "integration-fix" if handoff_required else "",
        "reasons": reasons,
    }


def evaluate_dev_auto_merge_packet(
    packet: dict[str, Any],
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate dev-only automatic merge readiness without mutating GitHub state."""

    reasons: list[str] = [DEV_AUTO_MERGE_DEPRECATED_REASON]
    if packet.get("schema") != DEV_AUTO_MERGE_PACKET_SCHEMA:
        reasons.append(f"dev auto-merge packet schema must be {DEV_AUTO_MERGE_PACKET_SCHEMA}")

    target_branch = packet.get("target_branch")
    if target_branch == "main":
        reasons.append(DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET_REASON)
    elif target_branch != "dev":
        reasons.append(DEV_AUTO_MERGE_BLOCKED_NON_DEV_TARGET_REASON)

    source_branch = packet.get("source_branch")
    if not isinstance(source_branch, str) or not source_branch.startswith("goal/"):
        reasons.append("dev auto-merge source_branch must match goal/<goal-id>")

    topology_policy = packet.get("topology_policy")
    if not isinstance(topology_policy, dict):
        reasons.append("dev auto-merge requires topology_policy object")
    else:
        if not _status_passes(topology_policy):
            reasons.append("topology_policy.status must be pass before dev auto-merge")
        command = topology_policy.get("verification_command")
        if not isinstance(command, str) or "verify-live-topology" not in command:
            reasons.append("topology_policy.verification_command must run verify-live-topology")

    merge_packet = packet.get("merge_authority_packet")
    if not isinstance(merge_packet, dict):
        reasons.append("dev auto-merge requires merge_authority_packet object")
        merge_result: dict[str, Any] = {
            "allowed": False,
            "merge_eligibility_status": MERGE_BLOCKED_STATUS,
            "merge_eligibility_reason": MERGE_BLOCKED_POLICY_REASON,
            "reasons": ["merge_authority_packet missing"],
        }
    else:
        merge_result = evaluate_merge_authority_packet(merge_packet, expected=expected)
        if not merge_result.get("allowed"):
            reasons.extend(f"merge_authority:{reason}" for reason in merge_result.get("reasons", []))
        if merge_packet.get("action") != "merge":
            reasons.append("dev auto-merge requires merge_authority_packet.action merge")
        if merge_packet.get("base_ref") == "main":
            reasons.append(DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET_REASON)
        elif merge_packet.get("base_ref") != "dev":
            reasons.append("dev auto-merge requires merge_authority_packet.base_ref dev")
        authority = merge_packet.get("authority")
        if not isinstance(authority, dict) or authority.get("source") != "contract_authority":
            reasons.append("dev auto-merge requires authority.source contract_authority")
        state_file_policy = merge_packet.get("state_file_policy")
        if not isinstance(state_file_policy, dict) or not _status_passes(state_file_policy):
            reasons.append("dev auto-merge requires passing state_file_policy")
        elif state_file_policy.get("non_state_authority_allowed") is not False:
            reasons.append("dev auto-merge requires non_state_authority_allowed false")
        draft_policy = merge_packet.get("draft_policy")
        if not isinstance(draft_policy, dict) or draft_policy.get("is_draft") is not False:
            reasons.append("dev auto-merge requires draft false")
        conflict_policy = merge_packet.get("conflict_policy")
        if not isinstance(conflict_policy, dict) or conflict_policy.get("mergeable_state") != "CLEAN":
            reasons.append("dev auto-merge requires mergeable_state CLEAN")
        reasons.extend(_dev_auto_merge_context_reasons(merge_packet.get("check_policy")))

    status = "pass" if not reasons else "blocked"
    return {
        "schema": DEV_AUTO_MERGE_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "classification": DEV_AUTO_MERGE_ALLOWED_STATUS if status == "pass" else DEV_AUTO_MERGE_BLOCKED_STATUS,
        "target_branch": target_branch,
        "merge_eligibility_status": merge_result.get("merge_eligibility_status", MERGE_BLOCKED_STATUS),
        "merge_eligibility_reason": merge_result.get("merge_eligibility_reason", MERGE_BLOCKED_POLICY_REASON),
        "reasons": reasons,
    }



def evaluate_agent_pickup_packet(packet: dict[str, Any], *, dry_run_invoked: bool = True) -> dict[str, Any]:
    """Evaluate whether an issue can be picked up by agent for bounded development."""

    labels_value = packet.get("labels")
    labels = labels_value if isinstance(labels_value, list) else []
    normalized_labels = [label for label in labels if isinstance(label, str)]
    reasons: list[str] = []

    if packet.get("schema") != AGENT_PICKUP_PACKET_SCHEMA:
        reasons.append(f"agent pickup packet schema must be {AGENT_PICKUP_PACKET_SCHEMA}")
    if labels_value is None or not normalized_labels:
        reasons.append("agent pickup blocked for unlabeled issue")
    elif len(normalized_labels) != len(labels):
        reasons.append("agent pickup labels must be strings")

    develop_ready_label = ISSUE_TYPE_IDENTIFIERS["develop_ready"]
    if develop_ready_label not in normalized_labels:
        if ISSUE_TYPE_IDENTIFIERS["bugfix"] in normalized_labels:
            reasons.append("agent pickup blocked for bugfix-only issue without type:develop-ready")
        elif ISSUE_TYPE_IDENTIFIERS["idea"] not in normalized_labels and normalized_labels:
            reasons.append("agent pickup requires type:develop-ready")
    else:
        reasons.extend(_validate_develop_ready_body(packet.get("body")))

    for label in AGENT_PICKUP_BLOCKED_LABELS:
        if label in normalized_labels:
            reasons.append(f"agent pickup blocked by label: {label}")

    reasons.extend(_validate_route_gate(packet.get("route_gate")))

    for key in (
        "constitution_evidence",
        "research_evidence",
        "accepted_operator_decision_evidence",
    ):
        reasons.extend(_validate_structured_evidence_object(packet.get(key), key))

    owning_role = packet.get("owning_role")
    if not isinstance(owning_role, str) or not owning_role.strip():
        reasons.append("agent pickup requires owning_role")

    reasons.extend(_validate_task_packet(packet.get("task_packet")))
    reasons.extend(_validate_duplicate_guard(packet.get("duplicate_guard")))

    dry_run = packet.get("dry_run")
    if not dry_run_invoked:
        reasons.append("agent pickup verification must run with --dry-run before dispatch")
    reasons.extend(_validate_dry_run(dry_run))

    status = "blocked" if reasons else "pass"
    return {
        "schema": AGENT_PICKUP_EVALUATION_SCHEMA,
        "status": status,
        "allowed": status == "pass",
        "required_issue_type": develop_ready_label,
        "labels": normalized_labels,
        "reasons": reasons,
    }



def _normalize_refname(ref: str) -> str:
    value = ref.strip()
    if value.startswith("refs/heads/"):
        return value.removeprefix("refs/heads/")
    if value.startswith("refs/remotes/origin/"):
        return value.removeprefix("refs/remotes/origin/")
    if value.startswith("origin/"):
        return value.removeprefix("origin/")
    return value



def _goal_branch_for(goal_id: str) -> str:
    return f"goal/{goal_id}"



def _agent_prefix_for(goal_id: str) -> str:
    return f"agent/{goal_id}/"



def _infer_goal_id_from_branch(branch: str) -> str | None:
    if branch.startswith("goal/"):
        suffix = branch.removeprefix("goal/")
        return suffix or None
    if branch.startswith("agent/"):
        parts = branch.split("/", 3)
        if len(parts) >= 2 and parts[1]:
            return parts[1]
    return None



def _git_current_branch(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
        text=True,
    ).strip()



def _git_refs(repo_root: Path) -> set[str]:
    refs_output = subprocess.check_output(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin"],
        cwd=repo_root,
        text=True,
    )
    return {_normalize_refname(line) for line in refs_output.splitlines() if line.strip()}



def _git_goal_is_ancestor(repo_root: Path, goal_branch: str, agent_branch: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", goal_branch, agent_branch],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode == 0



def _load_topology_file(path: Path) -> dict[str, Any]:
    data = load_json(path)
    refs: set[str] = set()
    refs_data = data.get("refs")
    if isinstance(refs_data, list):
        refs.update(_normalize_refname(str(ref)) for ref in refs_data)
    branches = data.get("branches")
    if isinstance(branches, dict):
        for key in ("main", "dev", "goal"):
            value = branches.get(key)
            if isinstance(value, str) and value:
                refs.add(_normalize_refname(value))
        agents = branches.get("agent")
        if isinstance(agents, list):
            refs.update(_normalize_refname(str(ref)) for ref in agents)
        elif isinstance(agents, str) and agents:
            refs.add(_normalize_refname(agents))
    branch_bases: dict[str, str] = {}
    raw_bases = data.get("branch_bases")
    if isinstance(raw_bases, dict):
        for branch, base in raw_bases.items():
            if isinstance(branch, str) and isinstance(base, str):
                branch_bases[_normalize_refname(branch)] = _normalize_refname(base)
    stacked_branches: set[str] = set()
    raw_stacked = data.get("stacked_branches")
    if isinstance(raw_stacked, list):
        stacked_branches.update(_normalize_refname(str(branch)) for branch in raw_stacked if str(branch).strip())
    return {
        "goal_id": data.get("goal_id"),
        "current_branch": data.get("current_branch"),
        "refs": refs,
        "branch_bases": branch_bases,
        "stacked_branches": stacked_branches,
        "stacked_branches_allowed": bool(data.get("stacked_branches_allowed", False)),
        "mode_transition_recorded": bool(data.get("mode_transition_recorded", False)),
    }



def classify_mode(
    *,
    goal_id: str,
    declared_mode: str,
    repo_root: Path,
    development_scenario: str = "goal",
    topology_file: Path | None = None,
    current_branch: str | None = None,
    stacked_branches_allowed: bool | None = None,
    mode_transition_recorded: bool | None = None,
) -> dict[str, Any]:
    if declared_mode not in DECLARED_WORKFLOW_MODES:
        raise ValueError(f"declared mode must be one of {', '.join(DECLARED_WORKFLOW_MODES)}")
    if development_scenario not in DEVELOPMENT_SCENARIOS:
        raise ValueError(f"development scenario must be one of {', '.join(DEVELOPMENT_SCENARIOS)}")

    topology_data = _load_topology_file(topology_file) if topology_file else None
    effective_goal_id = goal_id or ""
    if not effective_goal_id and topology_data:
        raw_goal_id = topology_data.get("goal_id")
        if isinstance(raw_goal_id, str):
            effective_goal_id = raw_goal_id
    effective_current_branch = current_branch
    if effective_current_branch is None and topology_data:
        raw_current_branch = topology_data.get("current_branch")
        if isinstance(raw_current_branch, str) and raw_current_branch:
            effective_current_branch = _normalize_refname(raw_current_branch)
    if effective_current_branch is None:
        effective_current_branch = _git_current_branch(repo_root)
    effective_current_branch = _normalize_refname(effective_current_branch)
    if not effective_goal_id:
        inferred_goal_id = _infer_goal_id_from_branch(effective_current_branch)
        if inferred_goal_id is None:
            raise ValueError("goal_id is required when the current branch does not encode it")
        effective_goal_id = inferred_goal_id

    goal_branch = _goal_branch_for(effective_goal_id)
    agent_prefix = _agent_prefix_for(effective_goal_id)
    refs = set(topology_data["refs"]) if topology_data else _git_refs(repo_root)
    refs.add(effective_current_branch)
    goal_branch_present = goal_branch in refs
    dev_branch_present = "dev" in refs
    agent_branches = sorted(ref for ref in refs if ref.startswith(agent_prefix))
    active_agent_branch_count = len(agent_branches)

    branch_bases = dict(topology_data["branch_bases"]) if topology_data else {}
    effective_stacked_branches_allowed = (
        bool(topology_data.get("stacked_branches_allowed", False)) if topology_data else False
    )
    if stacked_branches_allowed is not None:
        effective_stacked_branches_allowed = stacked_branches_allowed
    effective_mode_transition_recorded = (
        bool(topology_data.get("mode_transition_recorded", False)) if topology_data else False
    )
    if mode_transition_recorded is not None:
        effective_mode_transition_recorded = mode_transition_recorded

    explicit_stacked_branches = set(topology_data.get("stacked_branches", set())) if topology_data else set()
    stacked_branches: list[str] = sorted(explicit_stacked_branches)
    bypass_branches: list[str] = []
    main_target_branches: list[str] = []
    for branch, base in branch_bases.items():
        if base == "main" and (branch == goal_branch or branch.startswith(agent_prefix) or branch.startswith("codex/")):
            main_target_branches.append(branch)
    for branch in agent_branches:
        base = branch_bases.get(branch)
        if base is None:
            continue
        if base.startswith(agent_prefix):
            stacked_branches.append(branch)
            bypass_branches.append(branch)
        elif base != goal_branch:
            bypass_branches.append(branch)
    if not topology_data and goal_branch_present:
        for branch in agent_branches:
            if not _git_goal_is_ancestor(repo_root, goal_branch, branch):
                bypass_branches.append(branch)
    stacked_branch_count = len(set(stacked_branches))

    if active_agent_branch_count > 0 and stacked_branch_count > 0 and not effective_mode_transition_recorded:
        detected_mode = "invalid_mixed_topology"
    elif active_agent_branch_count > 0:
        detected_mode = "parallel"
    elif goal_branch_present or stacked_branch_count > 0:
        detected_mode = "sequential"
    else:
        detected_mode = "undetermined"
    mode_transition_required = (
        declared_mode != "auto"
        and detected_mode in ALLOWED_WORKFLOW_MODES
        and declared_mode != detected_mode
    ) or detected_mode == "invalid_mixed_topology"
    effective_mode = detected_mode if declared_mode == "auto" and detected_mode in ALLOWED_WORKFLOW_MODES else declared_mode
    reasons: list[str] = []

    if main_target_branches:
        reasons.append(
            f"main is not an allowed {development_scenario} direct auto-merge target for: "
            + ", ".join(sorted(main_target_branches))
        )
    if not goal_branch_present:
        reasons.append(f"goal branch is missing: {goal_branch}")
    if not dev_branch_present:
        reasons.append("dev branch is missing: dev")
    if effective_mode == "sequential" and active_agent_branch_count > 0 and not effective_mode_transition_recorded:
        reasons.append("sequential mode has unapproved agent branches")
    if effective_mode == "sequential" and stacked_branch_count > 0 and not effective_stacked_branches_allowed:
        reasons.append("sequential mode has unapproved stacked branches")
    if effective_mode == "parallel" and active_agent_branch_count == 0:
        reasons.append("parallel mode is missing agent branches")
    if effective_mode == "parallel" and bypass_branches:
        reasons.append("parallel mode bypasses agent->goal for: " + ", ".join(sorted(set(bypass_branches))))
    if mode_transition_required and not effective_mode_transition_recorded:
        reasons.append("mixed topology shapes require a recorded mode transition")
    if detected_mode == "undetermined":
        reasons.append("workflow mode is undetermined from branch topology")

    topology_valid = not reasons
    status = MODE_CLASSIFIED_STATUS if topology_valid else TOPOLOGY_BLOCKED_STATUS

    return {
        "schema": MODE_CLASSIFICATION_SCHEMA,
        "status": status,
        "goal_id": effective_goal_id,
        "development_scenario": development_scenario,
        "declared_mode": declared_mode,
        "detected_mode": detected_mode,
        "current_branch": effective_current_branch,
        "goal_branch_present": goal_branch_present,
        "dev_branch_present": dev_branch_present,
        "active_agent_branch_count": active_agent_branch_count,
        "stacked_branch_count": stacked_branch_count,
        "stacked_branches_allowed": effective_stacked_branches_allowed,
        "mode_transition_required": mode_transition_required,
        "mode_transition_recorded": effective_mode_transition_recorded,
        "topology_valid": topology_valid,
        "reasons": reasons,
    }



def validate_catalog(
    catalog: dict[str, Any],
    *,
    role_catalog: dict[str, Any] | None = None,
    check_files: bool = True,
    strict_route: bool = True,
) -> list[str]:
    errors: list[str] = []
    for field in sorted(REQUIRED_POLICY_FIELDS - set(catalog)):
        errors.append(f"missing policy field: {field}")

    expected_catalog_fields = {
        "schema": CATALOG_SCHEMA,
        "owner_plugin": "bears",
        "concrete_part": CONCRETE_PART,
    }
    if strict_route:
        expected_catalog_fields.update(
            {
                "route_target": VALIDATE_WORKFLOW_PATH,
                "reference_doc": REFERENCE_DOC_PATH,
                "workflow": WORKFLOW_CONTRACT_PATH,
            }
        )
    errors.extend(_errors_for_expected_mapping(catalog, expected_catalog_fields, prefix="catalog"))

    validation = catalog.get("validation")
    if not isinstance(validation, dict):
        errors.append("validation must be an object")
    else:
        commands = validation.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("validation.commands must be a non-empty list")
        if validation.get("requires_exact_role_route") is not True:
            errors.append("validation.requires_exact_role_route must be true")
        if validation.get("route_target_must_match_concrete_part") != ROUTE_CONCRETE_PART:
            errors.append(f"validation.route_target_must_match_concrete_part must be {ROUTE_CONCRETE_PART}")

    branch_model = catalog.get("branch_model")
    if not isinstance(branch_model, dict):
        errors.append("branch_model must be an object")
    else:
        errors.extend(
            _errors_for_expected_mapping(
                branch_model,
                {
                    "entrypoint": "/goal",
                    "main_branch": "main",
                    "dev_branch": "dev",
                    "goal_branch_pattern": "goal/<goal-id>",
                    "agent_branch_pattern": "agent/<goal-id>/<role>/<slice-id>",
                    "agent_pr_target": "goal/<goal-id>",
                    "goal_pr_target_for_dev": "dev",
                    "main_pr_target": "main",
                },
                prefix="branch_model",
            )
        )
        if branch_model.get("per_agent_remote_branch_required") is not True:
            errors.append("branch_model.per_agent_remote_branch_required must be true")
        for key in ("direct_push_to_main_allowed", "direct_push_to_dev_allowed"):
            if branch_model.get(key) is not False:
                errors.append(f"branch_model.{key} must be false")

    workflow_modes = catalog.get("workflow_modes")
    if not isinstance(workflow_modes, dict):
        errors.append("workflow_modes must be an object")
    else:
        errors.extend(_validate_workflow_modes_block(workflow_modes, prefix="workflow_modes"))

    pr_policy = catalog.get("pull_request_policy")
    if not isinstance(pr_policy, dict):
        errors.append("pull_request_policy must be an object")
    else:
        for key in (
            "agent_prs_are_draft_until_validation_passes",
            "agent_pr_to_goal_requires_state_file_gate",
            "goal_to_dev_pr_requires_state_file_gate",
            "delete_agent_branch_after_merge",
        ):
            if pr_policy.get(key) is not True:
                errors.append(f"pull_request_policy.{key} must be true for historical packet checks")
        for key in (
            "final_main_pr_requires_state_authority",
            "merge_to_dev_after_state_file_gate_allowed",
            "auto_merge_to_dev_after_green_ci_allowed",
            "auto_merge_to_dev_after_state_file_gate_and_ci_required",
        ):
            if pr_policy.get(key) is not False:
                errors.append(f"pull_request_policy.{key} must be false for main-only delivery")
        if pr_policy.get("auto_merge_to_main_allowed") is not False:
            errors.append("pull_request_policy.auto_merge_to_main_allowed must be false")

    state_file_policy = catalog.get("state_file_policy")
    if not isinstance(state_file_policy, dict):
        errors.append("state_file_policy must be an object")
    else:
        if state_file_policy.get("authoritative_state_source") != "machine_readable_state_files":
            errors.append("state_file_policy.authoritative_state_source must be machine_readable_state_files")
        authority_sources = state_file_policy.get("authority_sources")
        if not isinstance(authority_sources, list) or not {"workflow_state", "merge_authority_state"}.issubset(set(authority_sources)):
            errors.append("state_file_policy.authority_sources must include workflow_state and merge_authority_state")
        if state_file_policy.get("non_state_authority_allowed") is not False:
            errors.append("state_file_policy.non_state_authority_allowed must be false")
        required_state_refs = state_file_policy.get("required_state_refs")
        if not isinstance(required_state_refs, list) or not {"workflow_state", "merge_authority_state"}.issubset(set(required_state_refs)):
            errors.append("state_file_policy.required_state_refs must include workflow_state and merge_authority_state")
        required_markers = state_file_policy.get("required_commit_trailers")
        if not isinstance(required_markers, list) or not REQUIRED_STATE_FILE_MARKERS.issubset(set(required_markers)):
            errors.append("state_file_policy.required_commit_trailers must include state-file marker contract")

    errors.extend(_validate_issue_type_policy(catalog.get("issue_type_policy"), prefix="issue_type_policy"))
    try:
        template_data = _load_yaml_mapping(PLUGIN_ROOT / ISSUE_TEMPLATE_PATH)
        config_data = _load_yaml_mapping(PLUGIN_ROOT / ".github/ISSUE_TEMPLATE/config.yml")
        errors.extend(_validate_issue_template_contract(template_data, config_data))
    except FileNotFoundError as exc:
        errors.append(f"issue template file missing: {exc}")
    errors.extend(
        _validate_merge_authority_policy(catalog.get("merge_authority_policy"), prefix="merge_authority_policy")
    )
    errors.extend(_validate_dev_auto_merge_policy(catalog.get("dev_auto_merge_policy"), prefix="dev_auto_merge_policy"))
    errors.extend(_validate_scenario_policy(catalog.get("scenario_policy"), prefix="scenario_policy"))

    parent_agent_policy = catalog.get("parent_agent_policy")
    if not isinstance(parent_agent_policy, dict):
        errors.append("parent_agent_policy must be an object")
    else:
        if parent_agent_policy.get("mode") != "orchestration_only_in_subagent_mode":
            errors.append("parent_agent_policy.mode must be orchestration_only_in_subagent_mode")
        if parent_agent_policy.get("parent_context_allowed") is not False:
            errors.append("parent_agent_policy.parent_context_allowed must be false")
        parent_actions = parent_agent_policy.get("parent_actions")
        if not isinstance(parent_actions, list) or not all(isinstance(action, str) for action in parent_actions):
            errors.append("parent_agent_policy.parent_actions must be a string list")
        else:
            if parent_actions != list(REQUIRED_PARENT_AGENT_ACTIONS):
                errors.append("parent_agent_policy.parent_actions must match the canonical orchestration token list")
            drifted_actions = sorted(set(parent_actions) & set(DRIFTED_PARENT_AGENT_ACTIONS))
            if drifted_actions:
                errors.append(
                    "parent_agent_policy.parent_actions contains drifted tokens: " + ", ".join(drifted_actions)
                )
            forbidden_actions = sorted(set(parent_actions) & set(REQUIRED_PARENT_AGENT_FORBIDDEN_ACTIONS))
            if forbidden_actions:
                errors.append(
                    "parent_agent_policy.parent_actions contains forbidden actions: " + ", ".join(forbidden_actions)
                )
        forbidden_actions = parent_agent_policy.get("forbidden_actions")
        if not isinstance(forbidden_actions, list) or not all(isinstance(action, str) for action in forbidden_actions):
            errors.append("parent_agent_policy.forbidden_actions must be a string list")
        else:
            if forbidden_actions != list(REQUIRED_PARENT_AGENT_FORBIDDEN_ACTIONS):
                errors.append("parent_agent_policy.forbidden_actions must match the canonical forbidden token list")

    ci_policy = catalog.get("ci_policy")
    if not isinstance(ci_policy, dict):
        errors.append("ci_policy must be an object")
    else:
        for key in ("required_on_agent_pr", "required_on_goal_pr", "required_on_dev_branch", "required_pull_request_event"):
            if ci_policy.get(key) is not False:
                errors.append(f"ci_policy.{key} must be false for main-only delivery")
        if ci_policy.get("required_pull_request_targets") != []:
            errors.append("ci_policy.required_pull_request_targets must be [] for main-only delivery")
        if ci_policy.get("required_push_branches") != ["main"]:
            errors.append("ci_policy.required_push_branches must be [main] for automatic post-commit diagnostics")
        if strict_route and ci_policy.get("validation_workflow") != VALIDATE_WORKFLOW_PATH:
            errors.append(f"ci_policy.validation_workflow must be {VALIDATE_WORKFLOW_PATH}")
        required_commands = ci_policy.get("required_commands")
        if not isinstance(required_commands, list) or set(required_commands) != REQUIRED_CI_COMMANDS:
            errors.append("ci_policy.required_commands must match the deterministic CI command set")
        if ci_policy.get("branch_based_dev_cd_gate_allowed") is not False:
            errors.append("ci_policy.branch_based_dev_cd_gate_allowed must be false for main-only delivery")
        if "dev_cd_job" in ci_policy:
            errors.append("ci_policy.dev_cd_job must be absent for main-only delivery")

    cd_policy = catalog.get("cd_policy")
    if not isinstance(cd_policy, dict):
        errors.append("cd_policy must be an object")
    else:
        errors.extend(
            _errors_for_expected_mapping(
                cd_policy,
                {
                    "dev_environment": "dev",
                    "dev_branch": "dev",
                    "deploy_source_of_truth": KUBERNETES_SOURCE_OF_TRUTH,
                    "deploy_role": "bears-deploy-platform-engineer",
                    "authority_status": "deprecated_reference_only",
                    "active_authority": False,
                    "dev_cd_trigger_event": "none",
                    "dev_cd_trigger_branch": "none",
                },
                prefix="cd_policy",
            )
        )
        for key in (
            "auto_deploy_to_dev_on_merge",
            "kubernetes_holds_dev",
            "dev_deploy_requires_state_file_gate",
            "dev_deploy_requires_green_ci",
            "dev_deploy_requires_readonly_runtime_evidence",
        ):
            if cd_policy.get(key) is not False:
                errors.append(f"cd_policy.{key} must be false for main-only delivery")
        if cd_policy.get("production_requires_explicit_operator_request") is not True:
            errors.append("cd_policy.production_requires_explicit_operator_request must be true")
        if cd_policy.get("production_deploy_allowed") is not False:
            errors.append("cd_policy.production_deploy_allowed must be false")
        if cd_policy.get("cluster_mutation_allowed_from_plugin") is not False:
            errors.append("cd_policy.cluster_mutation_allowed_from_plugin must be false")
        secret_source = cd_policy.get("secret_source")
        if not isinstance(secret_source, str) or "Infisical" not in secret_source or "no repo-stored secrets" not in secret_source:
            errors.append("cd_policy.secret_source must require Infisical and no repo-stored secrets")
        dispatch_plan_contract = cd_policy.get("dispatch_plan_contract")
        if not isinstance(dispatch_plan_contract, dict):
            errors.append("cd_policy.dispatch_plan_contract must be an object")
        else:
            errors.extend(
                _errors_for_expected_mapping(
                    dispatch_plan_contract,
                    {
                        "schema": DISPATCH_SCHEMA,
                        "mode": "deprecated_reference_only",
                        "artifact_path": DISPATCH_ARTIFACT_PATH,
                        "artifact_name": DISPATCH_ARTIFACT_NAME,
                        "status": "DEPRECATED_REFERENCE_ONLY",
                        "active_authority": False,
                    },
                    prefix="cd_policy.dispatch_plan_contract",
                )
            )
            if dispatch_plan_contract.get("required_commit_trailers") != REQUIRED_COMMIT_TRAILERS:
                errors.append(
                    "cd_policy.dispatch_plan_contract.required_commit_trailers must match the deterministic marker contract"
                )
            if dispatch_plan_contract.get("evidence_path_contract") != REQUIRED_EVIDENCE_PATH_CONTRACT:
                errors.append(
                    "cd_policy.dispatch_plan_contract.evidence_path_contract must match the deterministic evidence path contract"
                )
            required_plan_fields = dispatch_plan_contract.get("required_plan_fields")
            if not isinstance(required_plan_fields, list) or set(required_plan_fields) != REQUIRED_PLAN_FIELDS:
                errors.append(
                    "cd_policy.dispatch_plan_contract.required_plan_fields must match the deterministic dispatch plan shape"
                )
            if dispatch_plan_contract.get("operator_approval_required") is not True:
                errors.append("cd_policy.dispatch_plan_contract.operator_approval_required must be true")
            if dispatch_plan_contract.get("fail_closed_when_evidence_missing") is not True:
                errors.append("cd_policy.dispatch_plan_contract.fail_closed_when_evidence_missing must be true")

    output_contract = catalog.get("output_contract")
    if not isinstance(output_contract, dict):
        errors.append("output_contract must be an object")
    else:
        required = output_contract.get("top_level_required")
        if not isinstance(required, list) or set(required) != REQUIRED_OUTPUT_FIELDS:
            errors.append("output_contract.top_level_required must match the deterministic output shape")
        if output_contract.get("ready_status") != "AGENT_GITHUB_DEV_CD_READY":
            errors.append("output_contract.ready_status must be AGENT_GITHUB_DEV_CD_READY")

    if check_files:
        for key in ("route_target", "reference_doc", "workflow"):
            value = catalog.get(key)
            if isinstance(value, str) and not _resolve_plugin_owned_path(value).is_file():
                errors.append(f"{key} file does not exist: {value}")

        reference_doc_path_value = catalog.get("reference_doc", REFERENCE_DOC_PATH)
        reference_doc_path = _resolve_plugin_owned_path(str(reference_doc_path_value))
        if reference_doc_path.is_file():
            errors.extend(_validate_reference_doc(reference_doc_path))

        validation_workflow_path_value = (
            ci_policy.get("validation_workflow") if isinstance(ci_policy, dict) else VALIDATE_WORKFLOW_PATH
        )
        validation_workflow_data = _load_yaml_mapping(_resolve_plugin_owned_path(str(validation_workflow_path_value)))
        on_data = validation_workflow_data.get("on")
        if not isinstance(on_data, dict):
            errors.append("validate workflow on must be an object")
        else:
            if "pull_request" in on_data or "merge_group" in on_data:
                errors.append("validate workflow must not include pull_request or merge_group in main-only delivery")
            allowed_events = {"push", "workflow_dispatch"}
            if set(on_data) != allowed_events:
                errors.append("validate workflow must expose only main push and operator workflow_dispatch")
            push_data = on_data.get("push")
            if not isinstance(push_data, dict) or push_data.get("branches") != ["main"]:
                errors.append("validate workflow push.branches must be [main]")
            dispatch_data = on_data.get("workflow_dispatch")
            dispatch_inputs = dispatch_data.get("inputs") if isinstance(dispatch_data, dict) else None
            if not isinstance(dispatch_inputs, dict) or "emergency_full_suite" not in dispatch_inputs:
                errors.append("validate workflow workflow_dispatch must keep emergency_full_suite input")
        jobs = validation_workflow_data.get("jobs")
        if not isinstance(jobs, dict):
            errors.append("validate workflow must define jobs")
        else:
            errors.extend(_validate_parallel_validation_jobs(jobs))
            if DEV_CD_JOB_ID in jobs:
                errors.append("validate workflow must not define jobs.dev-cd-gate in main-only delivery")

        workflow_path_value = catalog.get("workflow", WORKFLOW_CONTRACT_PATH)
        workflow_data = _load_yaml_mapping(_resolve_plugin_owned_path(str(workflow_path_value)))
        workflow_meta = workflow_data.get("workflow")
        if not isinstance(workflow_meta, dict) or workflow_meta.get("id") != "agent-github-dev-cd":
            errors.append("workflow.id must be agent-github-dev-cd")
        inputs = workflow_data.get("inputs")
        if not isinstance(inputs, dict):
            errors.append("workflow.inputs must be an object")
        else:
            workflow_mode_input = inputs.get("workflow_mode")
            if not isinstance(workflow_mode_input, dict):
                errors.append("workflow.inputs.workflow_mode must be an object")
            else:
                errors.extend(
                    _errors_for_expected_mapping(
                        workflow_mode_input,
                        {
                            "type": "string",
                            "default": DEFAULT_WORKFLOW_MODE,
                            "allowed": list(ALLOWED_WORKFLOW_MODES),
                        },
                        prefix="workflow.inputs.workflow_mode",
                    )
                )
            scenario_input = inputs.get("development_scenario")
            if not isinstance(scenario_input, dict):
                errors.append("workflow.inputs.development_scenario must be an object")
            else:
                errors.extend(
                    _errors_for_expected_mapping(
                        scenario_input,
                        {
                            "type": "string",
                            "default": "goal",
                            "allowed": list(DEVELOPMENT_SCENARIOS),
                        },
                        prefix="workflow.inputs.development_scenario",
                    )
                )
        branches = workflow_data.get("branches")
        if not isinstance(branches, dict):
            errors.append("workflow.branches must be an object")
        else:
            if branches.get("goal") != "goal/<goal-id>":
                errors.append("workflow branches.goal must match goal branch pattern")
            if branches.get("agent") != "agent/<goal-id>/<role>/<slice-id>":
                errors.append("workflow branches.agent must match agent branch pattern")
            if branches.get("dev") != "dev":
                errors.append("workflow branches.dev must be dev")
        workflow_modes_data = workflow_data.get("workflow_modes")
        if not isinstance(workflow_modes_data, dict):
            errors.append("workflow.workflow_modes must be an object")
        else:
            errors.extend(_validate_workflow_modes_block(workflow_modes_data, prefix="workflow.workflow_modes"))
        errors.extend(_validate_scenario_policy(workflow_data.get("scenario_policy"), prefix="workflow.scenario_policy"))
        issue_type_flow = workflow_data.get("issue_type_flow")
        if not isinstance(issue_type_flow, dict):
            errors.append("workflow.issue_type_flow must be an object")
        else:
            errors.extend(_validate_issue_type_policy(issue_type_flow.get("policy"), prefix="workflow.issue_type_flow.policy"))
            if issue_type_flow.get("verify_command") != AGENT_PICKUP_VERIFY_COMMAND:
                errors.append(f"workflow.issue_type_flow.verify_command must be {AGENT_PICKUP_VERIFY_COMMAND}")
            if issue_type_flow.get("metadata_verify_command") != ISSUE_METADATA_VERIFY_COMMAND:
                errors.append(f"workflow.issue_type_flow.metadata_verify_command must be {ISSUE_METADATA_VERIFY_COMMAND}")
        if workflow_data.get("sequential_steps") != REQUIRED_WORKFLOW_MODE_SEQUENTIAL_STEPS:
            errors.append("workflow.sequential_steps must match the deterministic sequential step order")
        if workflow_data.get("parallel_steps") != REQUIRED_WORKFLOW_MODE_PARALLEL_STEPS:
            errors.append("workflow.parallel_steps must match the deterministic parallel step order")
        archive_policy = workflow_data.get("archive_policy")
        if not isinstance(archive_policy, dict):
            errors.append("workflow.archive_policy must be an object")
        else:
            errors.extend(
                _errors_for_expected_mapping(
                    archive_policy,
                    {
                        "status": "deprecated_reference_only",
                        "active_authority": False,
                        "replacement_authority": "assets/catalog/agentic-enterprise-workflow.v1.json delivery_policy",
                        "main_only_delivery_required": True,
                        "github_actions_dev_cd_gate_allowed": False,
                    },
                    prefix="workflow.archive_policy",
                )
            )
        if "github_actions_gate" in workflow_data:
            errors.append("workflow.github_actions_gate must be absent for main-only delivery")
        steps = workflow_data.get("steps")
        if not isinstance(steps, list):
            errors.append("workflow.steps must be a list")
        else:
            step_map = {
                step.get("id"): step
                for step in steps
                if isinstance(step, dict) and isinstance(step.get("id"), str)
            }
            for step_id in ("state-file-gate-agent-pr", "state-file-gate-goal-pr"):
                step = step_map.get(step_id)
                if not isinstance(step, dict):
                    errors.append(f"workflow must define {step_id} step")
                elif "state-file" not in str(step.get("action", "")):
                    errors.append(f"workflow {step_id} must use a state-file gate action")
            for step_id in ("merge-authority-agent-pr", "merge-authority-dev-pr"):
                step = step_map.get(step_id)
                if not isinstance(step, dict):
                    errors.append(f"workflow must define {step_id} step")
                    continue
                if step.get("action") != "verify-merge-authority":
                    errors.append(f"workflow {step_id} must use verify-merge-authority")
                if step.get("command") != MERGE_AUTHORITY_VERIFY_COMMAND:
                    errors.append(f"workflow {step_id} command must be {MERGE_AUTHORITY_VERIFY_COMMAND}")
                if step.get("parent_send_input_authority_allowed") is not False:
                    errors.append(f"workflow {step_id} must reject parent send_input authority")
            classify_step = step_map.get("classify-mode")
            if not isinstance(classify_step, dict) or classify_step.get("action") != "classify-workflow-mode":
                errors.append("workflow must define classify-mode as classify-workflow-mode")
            branch_enforcement_step = step_map.get("branch-enforcement")
            if not isinstance(branch_enforcement_step, dict) or branch_enforcement_step.get("action") != "enforce-workflow-mode-branches":
                errors.append("workflow must define branch-enforcement as enforce-workflow-mode-branches")
            verify_live_topology_step = step_map.get("verify-live-topology")
            if not isinstance(verify_live_topology_step, dict) or verify_live_topology_step.get("action") != "verify-live-topology":
                errors.append("workflow must define verify-live-topology as verify-live-topology")
            for deprecated_step_id in ("auto-merge-dev", "dev-cd-gate", "cd-dev"):
                if deprecated_step_id in step_map:
                    errors.append(f"workflow {deprecated_step_id} step must be absent for main-only delivery")
            main_only_step = step_map.get("main-only-delivery")
            if not isinstance(main_only_step, dict):
                errors.append("workflow must define main-only-delivery step")
            else:
                if main_only_step.get("action") != "reference-main-only-delivery-policy":
                    errors.append("workflow main-only-delivery step must reference main-only delivery policy")
                if main_only_step.get("authority") != "assets/catalog/agentic-enterprise-workflow.v1.json delivery_policy":
                    errors.append("workflow main-only-delivery step must point to agentic-enterprise delivery_policy")
            step_ids = [step.get("id") for step in steps if isinstance(step, dict)]
            if "classify-mode" in step_ids and "branch-enforcement" in step_ids:
                if step_ids.index("classify-mode") > step_ids.index("branch-enforcement"):
                    errors.append("workflow classify-mode must run before branch-enforcement")
            if "merge-authority-agent-pr" in step_ids and "merge-agent-pr" in step_ids:
                if step_ids.index("merge-authority-agent-pr") > step_ids.index("merge-agent-pr"):
                    errors.append("workflow merge-authority-agent-pr must run before merge-agent-pr")

    if role_catalog is not None and strict_route:
        try:
            platform_roles = _load_platform_roles_module()
            route = platform_roles.route_target(
                role_catalog,
                str(catalog.get("route_target", VALIDATE_WORKFLOW_PATH)),
                plugin_root=PLUGIN_ROOT,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot route agent GitHub dev CD workflow: {exc}")
        else:
            if route.get("status") != "matched":
                errors.append("agent GitHub dev CD route target must match")
            if route.get("concrete_part") != ROUTE_CONCRETE_PART:
                errors.append(f"agent GitHub dev CD route target must route to {ROUTE_CONCRETE_PART}")
            if route.get("primary_role") != "bears-deploy-platform-engineer":
                errors.append("agent GitHub dev CD route target must route to bears-deploy-platform-engineer")

    return errors



def cmd_validate(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    role_catalog = load_json(args.role_catalog) if args.role_catalog else None
    errors = validate_catalog(catalog, role_catalog=role_catalog)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"agent github dev cd catalog ok: {args.catalog}")
    return 0


def cmd_classify_task(args: argparse.Namespace) -> int:
    prompt = args.prompt_file.read_text(encoding="utf-8")
    payload = classify_task_prompt(prompt)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_verify_scenario_policy(args: argparse.Namespace) -> int:
    packet = load_json(args.packet)
    payload = evaluate_scenario_policy_packet(packet)
    print(json.dumps(payload, indent=2))
    if payload["status"] != "pass":
        for reason in payload["reasons"]:
            print(f"ERROR: {reason}", file=sys.stderr)
        return 1
    return 0


def cmd_verify_dev_auto_merge(args: argparse.Namespace) -> int:
    packet = load_json(args.packet)
    payload = evaluate_dev_auto_merge_packet(packet, expected=_merge_expected_values_from_args(args))
    print(json.dumps(payload, indent=2))
    if payload["status"] != "pass":
        for reason in payload["reasons"]:
            print(f"ERROR: {reason}", file=sys.stderr)
        return 1
    return 0



def cmd_verify_dev_cd_evidence(args: argparse.Namespace) -> int:
    commit_message = _load_commit_message(args.commit_sha, repo_root=args.repo_root)
    trailers = _parse_commit_trailers(commit_message)
    errors = _validate_commit_evidence(
        trailers,
        repo_root=args.repo_root,
        dispatch_artifact=args.dispatch_artifact,
        require_dispatch_file=False,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"dev cd evidence ok: {args.commit_sha}")
    return 0



def cmd_verify_agent_pickup(args: argparse.Namespace) -> int:
    packet = load_json(args.issue_packet)
    payload = evaluate_agent_pickup_packet(packet, dry_run_invoked=args.dry_run)
    print(json.dumps(payload, indent=2))
    if payload["status"] != "pass":
        for reason in payload["reasons"]:
            print(f"ERROR: {reason}", file=sys.stderr)
        return 1
    return 0


def cmd_verify_issue_metadata(args: argparse.Namespace) -> int:
    packet = load_json(args.issue_packet)
    payload = evaluate_issue_metadata_packet(packet)
    print(json.dumps(payload, indent=2))
    if payload["status"] != "pass":
        for reason in payload["reasons"]:
            print(f"ERROR: {reason}", file=sys.stderr)
        for violation in payload["violations"]:
            issue = violation.get("issue", "<unknown>")
            for reason in violation.get("reasons", []):
                print(f"ERROR: {issue}: {reason}", file=sys.stderr)
        return 1
    return 0


def cmd_lint_command_snippet(args: argparse.Namespace) -> int:
    command = args.command
    if args.command_file is not None:
        command = args.command_file.read_text(encoding="utf-8")
    payload = lint_command_snippet(command, expected_input=args.expected_input)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "COMMAND_SNIPPET_PASS" else 1


def cmd_verify_pr_publication(args: argparse.Namespace) -> int:
    packet = load_json(args.packet)
    payload = evaluate_pr_publication_packet(packet)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


def cmd_verify_final_verification(args: argparse.Namespace) -> int:
    packet = load_json(args.packet)
    payload = evaluate_final_verification_packet(packet)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


def cmd_verify_hygiene_gate(args: argparse.Namespace) -> int:
    packet = load_json(args.packet)
    payload = evaluate_hygiene_gate_packet(packet)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


def cmd_merge_authority_check(args: argparse.Namespace) -> int:
    packet = load_json(args.packet)
    payload = evaluate_merge_authority_packet(packet, expected=_merge_expected_values_from_args(args))
    print(json.dumps(payload, indent=2))
    if payload["status"] != "pass":
        for reason in payload["reasons"]:
            print(f"ERROR: {reason}", file=sys.stderr)
        return 1
    return 0



def _classification_from_args(args: argparse.Namespace) -> dict[str, Any]:
    goal_id = args.goal_id
    if not goal_id and getattr(args, "commit_sha", None):
        commit_message = _load_commit_message(args.commit_sha, repo_root=args.repo_root)
        goal_id = _parse_commit_trailers(commit_message).get("Goal-Id", "")
    return classify_mode(
        goal_id=goal_id,
        declared_mode=args.declared_mode,
        repo_root=args.repo_root,
        development_scenario=args.development_scenario,
        topology_file=args.topology_file,
        current_branch=args.current_branch,
        stacked_branches_allowed=args.stacked_branches_allowed,
        mode_transition_recorded=args.mode_transition_recorded,
    )



def cmd_classify_mode(args: argparse.Namespace) -> int:
    payload = _classification_from_args(args)
    print(json.dumps(payload, indent=2))
    return 0



def cmd_verify_live_topology(args: argparse.Namespace) -> int:
    payload = _classification_from_args(args)
    print(json.dumps(payload, indent=2))
    if not payload["topology_valid"]:
        for reason in payload["reasons"]:
            print(f"ERROR: {reason}", file=sys.stderr)
        return 1
    return 0



def cmd_write_dispatch_plan(args: argparse.Namespace) -> int:
    commit_message = _load_commit_message(args.commit_sha, repo_root=args.repo_root)
    trailers = _parse_commit_trailers(commit_message)
    errors = _validate_commit_evidence(
        trailers,
        repo_root=args.repo_root,
        dispatch_artifact=args.dispatch_artifact,
        require_dispatch_file=False,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    classification_status = MODE_CLASSIFICATION_SKIPPED_STATUS
    topology_evidence_path = args.topology_evidence_path or ""
    stacked_branches_allowed = False
    mode_transition_recorded = False
    goal_id = args.goal_id or trailers.get("Goal-Id", "")
    if goal_id:
        payload = classify_mode(
            goal_id=goal_id,
            declared_mode=args.declared_mode,
            repo_root=args.repo_root,
            development_scenario=args.development_scenario,
            topology_file=args.topology_file,
            current_branch=args.current_branch,
            stacked_branches_allowed=args.stacked_branches_allowed,
            mode_transition_recorded=args.mode_transition_recorded,
        )
        classification_status = str(payload["status"])
        topology_evidence_path = topology_evidence_path or (
            str(args.topology_file) if args.topology_file is not None else ""
        )
        stacked_branches_allowed = bool(payload["stacked_branches_allowed"])
        mode_transition_recorded = bool(payload["mode_transition_recorded"])
        if not payload["topology_valid"]:
            for reason in payload["reasons"]:
                print(f"ERROR: {reason}", file=sys.stderr)
            return 1

    artifact_path = args.repo_root / args.dispatch_artifact
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    dispatch_payload = {
        "schema": DISPATCH_SCHEMA,
        "status": DISPATCH_STATUS,
        "source_repo": "/srv/bears/plugins/bears",
        "source_branch": "dev",
        "source_sha": args.commit_sha,
        "deploy_source_of_truth": args.kubernetes_source,
        "workflow_state_path": trailers["Workflow-State"],
        "merge_authority_state_path": trailers["Merge-Authority-State"],
        "runtime_evidence_path": trailers["Runtime-Evidence"],
        "rollback_note_path": trailers["Rollback-Note"],
        "dispatch_plan_path": args.dispatch_artifact,
        "operator_approval_required": True,
        "cluster_mutation_allowed_from_plugin": False,
        "production_deploy_allowed": False,
        "development_scenario": args.development_scenario,
        "scenario_policy_status": "pass",
        "agent_current_runtime": AGENT_CURRENT_RUNTIME,
        "scenario_auto_merge_to_main_allowed": REQUIRED_SCENARIO_POLICY["scenarios"][args.development_scenario][
            "auto_merge_to_main_allowed"
        ],
        "workflow_mode": str(payload["detected_mode"]) if args.goal_id and str(payload.get("detected_mode")) in ALLOWED_WORKFLOW_MODES else args.declared_mode,
        "mode_classification_status": classification_status,
        "topology_evidence_path": topology_evidence_path,
        "stacked_branches_allowed": stacked_branches_allowed,
        "mode_transition_recorded": mode_transition_recorded,
    }
    artifact_path.write_text(json.dumps(dispatch_payload, indent=2) + "\n", encoding="utf-8")
    if not artifact_path.is_file():
        print(f"ERROR: dispatch artifact was not written: {args.dispatch_artifact}", file=sys.stderr)
        return 1
    print(f"dispatch plan written: {args.dispatch_artifact}")
    return 0



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--role-catalog", type=Path, default=DEFAULT_ROLE_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.set_defaults(func=cmd_validate)

    classify_task_parser = subparsers.add_parser("classify-task")
    classify_task_parser.add_argument("--prompt-file", type=Path, required=True)
    classify_task_parser.set_defaults(func=cmd_classify_task)

    scenario_policy_parser = subparsers.add_parser("verify-scenario-policy")
    scenario_policy_parser.add_argument("--packet", type=Path, required=True)
    scenario_policy_parser.set_defaults(func=cmd_verify_scenario_policy)

    dev_auto_merge_parser = subparsers.add_parser("verify-dev-auto-merge")
    dev_auto_merge_parser.add_argument("--packet", type=Path, required=True)
    dev_auto_merge_parser.add_argument("--expected-repository", required=True)
    dev_auto_merge_parser.add_argument("--expected-pr-number", type=int, required=True)
    dev_auto_merge_parser.add_argument("--expected-head-ref", required=True)
    dev_auto_merge_parser.add_argument("--expected-head-sha", required=True)
    dev_auto_merge_parser.add_argument("--expected-base-ref", required=True)
    dev_auto_merge_parser.set_defaults(func=cmd_verify_dev_auto_merge)

    verify_parser = subparsers.add_parser("verify-dev-cd-evidence")
    verify_parser.add_argument("--commit-sha", required=True)
    verify_parser.add_argument("--dispatch-artifact", default=DISPATCH_ARTIFACT_PATH)
    verify_parser.add_argument("--repo-root", type=Path, default=PLUGIN_ROOT)
    verify_parser.set_defaults(func=cmd_verify_dev_cd_evidence)

    agent_pickup_parser = subparsers.add_parser("verify-agent-pickup")
    agent_pickup_parser.add_argument("--issue-packet", type=Path, required=True)
    agent_pickup_parser.add_argument("--dry-run", action="store_true")
    agent_pickup_parser.set_defaults(func=cmd_verify_agent_pickup)

    issue_metadata_parser = subparsers.add_parser("verify-issue-metadata")
    issue_metadata_parser.add_argument("--issue-packet", type=Path, required=True)
    issue_metadata_parser.set_defaults(func=cmd_verify_issue_metadata)

    command_lint_parser = subparsers.add_parser("lint-command-snippet")
    command_lint_parser.add_argument("--command", default="")
    command_lint_parser.add_argument("--command-file", type=Path)
    command_lint_parser.add_argument("--expected-input", action="store_true")
    command_lint_parser.set_defaults(func=cmd_lint_command_snippet)

    pr_publication_parser = subparsers.add_parser("verify-pr-publication")
    pr_publication_parser.add_argument("--packet", type=Path, required=True)
    pr_publication_parser.set_defaults(func=cmd_verify_pr_publication)

    final_verification_parser = subparsers.add_parser("verify-final-verification")
    final_verification_parser.add_argument("--packet", type=Path, required=True)
    final_verification_parser.set_defaults(func=cmd_verify_final_verification)

    hygiene_gate_parser = subparsers.add_parser("verify-hygiene-gate")
    hygiene_gate_parser.add_argument("--packet", type=Path, required=True)
    hygiene_gate_parser.set_defaults(func=cmd_verify_hygiene_gate)

    merge_parser = subparsers.add_parser("merge-authority-check")
    merge_parser.add_argument("--packet", type=Path, required=True)
    merge_parser.add_argument("--expected-repository", required=True)
    merge_parser.add_argument("--expected-pr-number", type=int, required=True)
    merge_parser.add_argument("--expected-head-ref", required=True)
    merge_parser.add_argument("--expected-head-sha", required=True)
    merge_parser.add_argument("--expected-base-ref", required=True)
    merge_parser.set_defaults(func=cmd_merge_authority_check)

    classify_parser = subparsers.add_parser("classify-mode")
    classify_parser.add_argument("--goal-id", default="")
    classify_parser.add_argument("--declared-mode", choices=DECLARED_WORKFLOW_MODES, default="auto")
    classify_parser.add_argument("--development-scenario", choices=DEVELOPMENT_SCENARIOS, default="goal")
    classify_parser.add_argument("--repo-root", type=Path, default=PLUGIN_ROOT)
    classify_parser.add_argument("--commit-sha")
    classify_parser.add_argument("--topology-file", type=Path)
    classify_parser.add_argument("--current-branch")
    classify_parser.add_argument("--stacked-branches-allowed", action="store_true")
    classify_parser.add_argument("--mode-transition-recorded", action="store_true")
    classify_parser.set_defaults(func=cmd_classify_mode)

    verify_topology_parser = subparsers.add_parser("verify-live-topology")
    verify_topology_parser.add_argument("--goal-id", default="")
    verify_topology_parser.add_argument("--declared-mode", "--expected-mode", dest="declared_mode", choices=DECLARED_WORKFLOW_MODES, default=DEFAULT_WORKFLOW_MODE)
    verify_topology_parser.add_argument("--development-scenario", choices=DEVELOPMENT_SCENARIOS, default="goal")
    verify_topology_parser.add_argument("--repo-root", type=Path, default=PLUGIN_ROOT)
    verify_topology_parser.add_argument("--commit-sha")
    verify_topology_parser.add_argument("--topology-file", type=Path)
    verify_topology_parser.add_argument("--current-branch")
    verify_topology_parser.add_argument("--stacked-branches-allowed", action="store_true")
    verify_topology_parser.add_argument("--mode-transition-recorded", action="store_true")
    verify_topology_parser.set_defaults(func=cmd_verify_live_topology)

    write_dispatch_parser = subparsers.add_parser("write-dispatch-plan")
    write_dispatch_parser.add_argument("--commit-sha", required=True)
    write_dispatch_parser.add_argument("--dispatch-artifact", default=DISPATCH_ARTIFACT_PATH)
    write_dispatch_parser.add_argument("--kubernetes-source", default=KUBERNETES_SOURCE_OF_TRUTH)
    write_dispatch_parser.add_argument("--repo-root", type=Path, default=PLUGIN_ROOT)
    write_dispatch_parser.add_argument("--goal-id", default="")
    write_dispatch_parser.add_argument("--declared-mode", choices=DECLARED_WORKFLOW_MODES, default=DEFAULT_WORKFLOW_MODE)
    write_dispatch_parser.add_argument("--development-scenario", choices=DEVELOPMENT_SCENARIOS, default="dev")
    write_dispatch_parser.add_argument("--topology-file", type=Path)
    write_dispatch_parser.add_argument("--topology-evidence-path", default="")
    write_dispatch_parser.add_argument("--current-branch")
    write_dispatch_parser.add_argument("--stacked-branches-allowed", action="store_true")
    write_dispatch_parser.add_argument("--mode-transition-recorded", action="store_true")
    write_dispatch_parser.set_defaults(func=cmd_write_dispatch_plan)
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
