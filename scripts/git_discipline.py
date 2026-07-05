#!/usr/bin/env python3
"""Validate and inspect the Bears Git closeout discipline contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/git-discipline.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
INSPECTION_SCHEMA = "bears-git-discipline-inspection.v1"
BRANCH_INVENTORY_SCHEMA = "bears-git-branch-inventory.v1"
BRANCH_CLOSEOUT_SCHEMA = "bears-git-branch-closeout-gate.v1"
GITLINK_AUDIT_SCHEMA = "bears-gitlink-target-audit.v1"
BRANCH_PREFIX_SCHEMA = "bears-branch-prefix-check.v1"
CLOSEOUT_PREFLIGHT_SCHEMA = "bears-git-closeout-preflight.v1"
BRANCH_BASE_PREFLIGHT_SCHEMA = "bears-git-branch-base-preflight.v1"
CLEAN_WORKTREE_TARGET_SCHEMA = "bears-clean-worktree-target.v1"
IGNORED_STAGING_CHECK_SCHEMA = "bears-ignored-staging-check.v1"
PLUGIN_WORKTREE_PREFLIGHT_SCHEMA = "bears-plugin-worktree-preflight.v1"
CATALOG_SCHEMA = "bears-git-discipline.v1"
CONCRETE_PART = "git_discipline"
REQUIRED_POLICY_FIELDS = {
    "schema",
    "owner_plugin",
    "concrete_part",
    "updated",
    "purpose",
    "route_target",
    "reference_doc",
    "validation",
    "closeout_order",
    "command_policy",
    "dirty_triage_policy",
    "branch_cleanup_policy",
    "path_safety",
    "output_contract",
}
REQUIRED_ORDER = [
    "status_before",
    "diff_check_before_stage",
    "surface_validation",
    "stage_all_requested_repo_changes",
    "cached_diff_check",
    "safe_worker_git_identity_preflight",
    "commit",
    "post_commit_status",
]
REQUIRED_TOP_LEVEL = {
    "schema",
    "repo_root",
    "branch",
    "head",
    "generated_at",
    "status",
    "worktree_dirty",
    "staged_dirty",
    "unstaged_dirty",
    "untracked_count",
    "diff_check_passed",
    "cached_diff_check_passed",
    "operator_review_required",
    "push_allowed",
    "commit_allowed_after_validation",
    "worker_git_identity_configured",
    "worker_git_identity_label",
    "changed_paths",
    "allowed_changed_paths",
    "disallowed_changed_paths",
}
REQUIRED_FORBIDDEN_AUTOMATIC = {
    "git push",
    "git reset",
    "git clean",
    "git checkout",
    "git switch",
    "git stash",
    "git merge",
    "git rebase",
    "git revert",
    "git config --global",
}
REQUIRED_SAFE_WORKER_IDENTITY_FIELDS = {
    "required_before_commit_authority",
    "user_name",
    "user_email",
    "fixed_public_identity_label",
    "allowed_config_sources",
    "global_config_source_allowed",
    "automatic_global_config_mutation_allowed",
    "provider_account_profile_lookup_allowed",
    "missing_or_unsafe_status",
    "preflight_output_fields",
}
REQUIRED_SAFE_WORKER_OUTPUT_FIELDS = {
    "worker_git_identity_configured",
    "worker_git_identity_label",
}
REQUIRED_SECRET_FRAGMENTS = {".env", "id_rsa", "private_key", "token", "credential", "secret"}
REQUIRED_LOG_FRAGMENTS = {".log", "logs/", "history"}
REQUIRED_CANONICAL_PLUGIN_CHECKS = {
    "pwd equals canonical_root or task packet names an approved isolated worktree",
    "git rev-parse --show-toplevel equals canonical_root for canonical checkout work",
    "git config --get core.worktree is empty or equals canonical_root",
    "git status --short --branch is captured for canonical_root",
}
REQUIRED_CANONICAL_PLUGIN_FORBIDDEN_STATES = {
    "PLUGIN_TOPLEVEL_REDIRECTED",
    "PLUGIN_CORE_WORKTREE_MISMATCH",
    "PLUGIN_CLOSEOUT_FROM_TEMP_WORKTREE",
    "UNSYNCED_CANONICAL_CHECKOUT",
    "PLUGIN_CWD_MISMATCH",
}
REQUIRED_BRANCH_CLASSES = {
    "main_branch",
    "worktree_attached",
    "backup_dirty_preserve",
    "github_merged_cleanup_candidate",
    "ancestry_merged_cleanup_candidate",
    "closed_unmerged_review_required",
    "open_pr_review_required",
    "remote_branch_without_pr_review_required",
    "local_only_review_required",
}
REQUIRED_BRANCH_INVENTORY_FIELDS = {
    "branch",
    "head",
    "upstream",
    "remote_exists",
    "worktree_attached",
    "worktree_path",
    "merged_into_base_by_ancestry",
    "github_pr_numbers",
    "github_pr_states",
    "creation_hint",
    "cleanup_class",
    "local_delete_eligible",
    "delete_blocked_reason",
    "dirty_triage_outcome",
    "dirty_triage_actions",
    "dirty_triage_proofs",
    "cleanup_plan_proof",
    "cleanup_authority",
    "owner_known",
    "auto_delete_allowed",
}
REQUIRED_REMOTE_BRANCH_CLASSES = {
    "remote_main_branch",
    "remote_tracking_local_present",
    "remote_github_merged_cleanup_candidate",
    "remote_ancestry_merged_cleanup_candidate",
    "remote_open_pr_review_required",
    "remote_closed_unmerged_review_required",
    "remote_without_pr_review_required",
}
REQUIRED_REMOTE_BRANCH_INVENTORY_FIELDS = {
    "branch",
    "remote_ref",
    "head",
    "local_branch_exists",
    "merged_into_base_by_ancestry",
    "github_pr_numbers",
    "github_pr_states",
    "cleanup_class",
    "remote_delete_eligible",
    "delete_blocked_reason",
    "dirty_triage_outcome",
    "dirty_triage_actions",
    "dirty_triage_proofs",
    "cleanup_plan_proof",
    "cleanup_authority",
    "owner_known",
    "auto_delete_allowed",
}
REQUIRED_DIRTY_TRIAGE_OUTCOMES = {
    "active_parallel_agent",
    "completed_needs_integration",
    "abandoned_needs_review",
    "useful_abandoned_code",
    "obsolete_cleanup_candidate",
    "unsafe_dirty_blocker",
}
REQUIRED_ACTIVE_PARALLEL_AGENT_PROOFS = {
    "active_worker_state",
    "heartbeat",
    "scope_lock",
    "open_pr",
    "live_session_proof",
}
REQUIRED_DIRTY_TRIAGE_ACTIONS = {
    "active_parallel_agent": {"protect_branch", "coordinate_with_active_owner", "block_auto_delete"},
    "completed_needs_integration": {"protect_branch", "request_integration_review", "block_auto_delete"},
    "abandoned_needs_review": {"protect_branch", "request_owner_review", "block_auto_delete"},
    "useful_abandoned_code": {"create_narrow_integration_assignment", "block_auto_cherry_pick", "block_auto_delete"},
    "obsolete_cleanup_candidate": {"require_cleanup_plan_proof", "allow_safe_local_cleanup_only"},
    "unsafe_dirty_blocker": {"block_auto_delete", "request_operator_review"},
}
REQUIRED_DIRTY_TRIAGE_INVENTORY_FIELDS = {
    "dirty_triage_outcome",
    "dirty_triage_actions",
    "dirty_triage_proofs",
    "cleanup_plan_proof",
    "cleanup_authority",
    "owner_known",
    "auto_delete_allowed",
}
REQUIRED_BRANCH_FORBIDDEN_AUTOMATIC = {
    "git branch -d",
    "git branch -D",
    "git push origin --delete",
    "git worktree prune",
    "git remote prune",
    "git fetch --prune",
}
REQUIRED_BRANCH_PREFIX_FIELDS = {
    "schema",
    "branch",
    "default_prefix",
    "assignment_packet",
    "override_prefix",
    "override_used",
    "status",
    "branch_prefix_check",
    "read_only",
}
REQUIRED_GITLINK_AUDIT_FIELDS = {
    "schema",
    "repo_root",
    "tree_ref",
    "gitlink_path",
    "parent_gitlink_target",
    "expected_target",
    "local_checkout",
    "local_checkout_head",
    "local_checkout_status",
    "claim_source",
    "claim_object_used",
    "local_checkout_evidence_usable",
    "status",
    "read_only",
}
REQUIRED_CLOSEOUT_PREFLIGHT_FIELDS = {
    "schema",
    "repo_root",
    "branch",
    "head",
    "status",
    "closeout_allowed",
    "commit_allowed_after_validation",
    "allowed_changed_paths",
    "disallowed_changed_paths",
    "gitlink_proofs",
    "block_reasons",
    "read_only",
}
REQUIRED_BRANCH_CLEANUP_ISSUE_MAPPING = {
    "BearsCLOUD/bears_plugin#133": "clean_worktree_and_gitlink_closeout_guard",
    "BearsCLOUD/bears_plugin#88": "branch_base_preflight",
    "BearsCLOUD/bears_plugin#144": "codex_branch_prefix_governance",
    "BearsCLOUD/bears_plugin#128": "gitlink_sync_target_audit",
    "BearsCLOUD/bears_plugin#132": "merge_authority_lane",
    "BearsCLOUD/bears_plugin#120": "durable_pass_evidence_before_merge_handoff",
}
DEFAULT_IGNORED_STAGING_BLOCK_PATTERNS = (
    "dev/**",
    "plugins/bears",
    "plugins/bears/**",
)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _resolve_plugin_owned_path(path_value: str) -> Path:
    prefix = "/srv/bears/plugins/bears/"
    if path_value.startswith(prefix):
        return PLUGIN_ROOT / path_value.removeprefix(prefix)
    return Path(path_value)


def _load_platform_roles_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("platform_roles", PLUGIN_ROOT / "scripts/subagents_roles.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load subagents_roles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def validate_catalog(
    catalog: dict[str, Any],
    *,
    role_catalog: dict[str, Any] | None = None,
    check_files: bool = True,
) -> list[str]:
    """Validate the Git discipline catalog."""
    errors: list[str] = []
    missing = sorted(REQUIRED_POLICY_FIELDS - set(catalog))
    for field in missing:
        errors.append(f"missing policy field: {field}")

    if catalog.get("schema") != CATALOG_SCHEMA:
        errors.append(f"schema must be {CATALOG_SCHEMA}")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")
    if catalog.get("concrete_part") != CONCRETE_PART:
        errors.append(f"concrete_part must be {CONCRETE_PART}")

    route_target = catalog.get("route_target")
    if not isinstance(route_target, str) or not route_target.endswith("/scripts/git_discipline.py"):
        errors.append("route_target must point to scripts/git_discipline.py")
    reference_doc = catalog.get("reference_doc")
    if not isinstance(reference_doc, str) or not reference_doc.endswith("/docs/reference/git-discipline.md"):
        errors.append("reference_doc must point to docs/reference/git-discipline.md")

    validation = catalog.get("validation")
    if not isinstance(validation, dict):
        errors.append("validation must be an object")
    else:
        commands = validation.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("validation.commands must be a non-empty list")
        if validation.get("requires_exact_role_route") is not True:
            errors.append("validation.requires_exact_role_route must be true")

    order = catalog.get("closeout_order")
    if not isinstance(order, list):
        errors.append("closeout_order must be a list")
    else:
        steps = [item.get("step") for item in order if isinstance(item, dict)]
        if steps != REQUIRED_ORDER:
            errors.append("closeout_order steps must match the canonical Git closeout order")
        for item in order:
            if not isinstance(item, dict):
                errors.append("closeout_order entries must be objects")
                continue
            if not isinstance(item.get("command"), str) or not item["command"]:
                errors.append(f"closeout_order.{item.get('step', '<unknown>')}.command must be non-empty")
            if not isinstance(item.get("required_before"), str) or not item["required_before"]:
                errors.append(f"closeout_order.{item.get('step', '<unknown>')}.required_before must be non-empty")

    command_policy = catalog.get("command_policy")
    if not isinstance(command_policy, dict):
        errors.append("command_policy must be an object")
    else:
        if command_policy.get("validator_is_read_only") is not True:
            errors.append("command_policy.validator_is_read_only must be true")
        if command_policy.get("mutating_git_commands_require_operator_request") is not True:
            errors.append("command_policy.mutating_git_commands_require_operator_request must be true")
        if command_policy.get("push_requires_explicit_operator_request") is not True:
            errors.append("command_policy.push_requires_explicit_operator_request must be true")
        if command_policy.get("commit_message_language") != "English":
            errors.append("command_policy.commit_message_language must be English")
        forbidden = command_policy.get("forbidden_automatic_commands")
        if not isinstance(forbidden, list) or not REQUIRED_FORBIDDEN_AUTOMATIC.issubset(set(forbidden)):
            errors.append("command_policy.forbidden_automatic_commands is missing required Git commands")
        safe_identity = command_policy.get("safe_worker_git_identity")
        if not isinstance(safe_identity, dict):
            errors.append("command_policy.safe_worker_git_identity must be an object")
        else:
            missing_identity_fields = sorted(REQUIRED_SAFE_WORKER_IDENTITY_FIELDS - set(safe_identity))
            for field in missing_identity_fields:
                errors.append(f"command_policy.safe_worker_git_identity.{field} is required")
            if safe_identity.get("required_before_commit_authority") is not True:
                errors.append("command_policy.safe_worker_git_identity.required_before_commit_authority must be true")
            user_name = safe_identity.get("user_name")
            user_email = safe_identity.get("user_email")
            fixed_label = safe_identity.get("fixed_public_identity_label")
            if not isinstance(user_name, str) or not user_name.strip():
                errors.append("command_policy.safe_worker_git_identity.user_name must be non-empty")
            if not isinstance(user_email, str) or not user_email.strip() or "@" not in user_email:
                errors.append("command_policy.safe_worker_git_identity.user_email must be a fixed public email")
            if isinstance(user_name, str) and isinstance(user_email, str):
                expected_label = f"{user_name} <{user_email}>"
                if fixed_label != expected_label:
                    errors.append("command_policy.safe_worker_git_identity.fixed_public_identity_label must match user_name and user_email")
            if not isinstance(fixed_label, str) or not fixed_label.strip():
                errors.append("command_policy.safe_worker_git_identity.fixed_public_identity_label must be non-empty")
            allowed_sources = safe_identity.get("allowed_config_sources")
            if not isinstance(allowed_sources, list) or set(allowed_sources) != {"local"}:
                errors.append("command_policy.safe_worker_git_identity.allowed_config_sources must be exactly ['local']")
            if safe_identity.get("global_config_source_allowed") is not False:
                errors.append("command_policy.safe_worker_git_identity.global_config_source_allowed must be false")
            if safe_identity.get("automatic_global_config_mutation_allowed") is not False:
                errors.append("command_policy.safe_worker_git_identity.automatic_global_config_mutation_allowed must be false")
            if safe_identity.get("provider_account_profile_lookup_allowed") is not False:
                errors.append("command_policy.safe_worker_git_identity.provider_account_profile_lookup_allowed must be false")
            if safe_identity.get("missing_or_unsafe_status") != "GIT_DISCIPLINE_BLOCKED":
                errors.append("command_policy.safe_worker_git_identity.missing_or_unsafe_status must be GIT_DISCIPLINE_BLOCKED")
            output_fields = safe_identity.get("preflight_output_fields")
            if not isinstance(output_fields, list) or not REQUIRED_SAFE_WORKER_OUTPUT_FIELDS.issubset(set(output_fields)):
                errors.append("command_policy.safe_worker_git_identity.preflight_output_fields is incomplete")

    dirty_policy = catalog.get("dirty_triage_policy")
    if not isinstance(dirty_policy, dict):
        errors.append("dirty_triage_policy must be an object")
    else:
        if dirty_policy.get("validator_is_read_only") is not True:
            errors.append("dirty_triage_policy.validator_is_read_only must be true")
        if dirty_policy.get("unclosed_changes_require_classification") is not True:
            errors.append("dirty_triage_policy.unclosed_changes_require_classification must be true")
        state_machine = dirty_policy.get("state_machine")
        if not isinstance(state_machine, dict):
            errors.append("dirty_triage_policy.state_machine must be an object")
        else:
            outcomes = state_machine.get("outcomes")
            if not isinstance(outcomes, list) or set(outcomes) != REQUIRED_DIRTY_TRIAGE_OUTCOMES:
                errors.append("dirty_triage_policy.state_machine.outcomes must match required outcomes")
            actions = state_machine.get("actions")
            if not isinstance(actions, dict):
                errors.append("dirty_triage_policy.state_machine.actions must be an object")
            else:
                for outcome, required_actions in REQUIRED_DIRTY_TRIAGE_ACTIONS.items():
                    outcome_actions = actions.get(outcome)
                    if not isinstance(outcome_actions, list) or not required_actions.issubset(set(outcome_actions)):
                        errors.append(f"dirty_triage_policy.state_machine.actions.{outcome} is incomplete")
            active_proofs = state_machine.get("active_parallel_agent_proofs")
            if not isinstance(active_proofs, list) or set(active_proofs) != REQUIRED_ACTIVE_PARALLEL_AGENT_PROOFS:
                errors.append("dirty_triage_policy.state_machine.active_parallel_agent_proofs must match required proofs")
        useful = dirty_policy.get("useful_abandoned_code")
        if not isinstance(useful, dict):
            errors.append("dirty_triage_policy.useful_abandoned_code must be an object")
        else:
            if useful.get("narrow_integration_assignment_required") is not True:
                errors.append("dirty_triage_policy.useful_abandoned_code.narrow_integration_assignment_required must be true")
            if useful.get("auto_cherry_pick_allowed") is not False:
                errors.append("dirty_triage_policy.useful_abandoned_code.auto_cherry_pick_allowed must be false")
        cleanup_rules = dirty_policy.get("cleanup_rules")
        if not isinstance(cleanup_rules, dict):
            errors.append("dirty_triage_policy.cleanup_rules must be an object")
        else:
            expected_cleanup_rules = {
                "auto_cleanup_requires_cleanup_plan_proof": True,
                "safe_local_candidates_only": True,
                "remote_delete_requires_explicit_cleanup_authority": True,
                "cleanup_eligibility_requires_closeout_or_merge_ready": True,
                "unknown_ownership_auto_delete_allowed": False,
                "open_pr_auto_delete_allowed": False,
                "attached_worktree_auto_delete_allowed": False,
                "backup_dirty_branch_auto_delete_allowed": False,
                "normal_worker_progress_cleanup_allowed": False,
            }
            for key, expected in expected_cleanup_rules.items():
                if cleanup_rules.get(key) is not expected:
                    errors.append(f"dirty_triage_policy.cleanup_rules.{key} must be {str(expected).lower()}")
        worker_state_files = dirty_policy.get("worker_state_files")
        if not isinstance(worker_state_files, dict):
            errors.append("dirty_triage_policy.worker_state_files must be an object")
        else:
            expected_worker_file_rules = {
                "per_worker_state_files_required_for_concurrent_workers": True,
                "root_workflow_state_still_supported": True,
                "read_only_hook_collection_allowed": True,
                "hook_collection_must_not_delete_or_mutate_git": True,
            }
            for key, expected in expected_worker_file_rules.items():
                if worker_state_files.get(key) is not expected:
                    errors.append(f"dirty_triage_policy.worker_state_files.{key} must be true")
            active_proofs = worker_state_files.get("accepted_active_proofs")
            if not isinstance(active_proofs, list) or set(active_proofs) != REQUIRED_ACTIVE_PARALLEL_AGENT_PROOFS:
                errors.append("dirty_triage_policy.worker_state_files.accepted_active_proofs must match required proofs")
            cli_flags = worker_state_files.get("cli_flags")
            if not isinstance(cli_flags, list) or not {"--workflow-state-json", "--worker-state-json"}.issubset(set(cli_flags)):
                errors.append("dirty_triage_policy.worker_state_files.cli_flags must include workflow and worker state flags")
        inventory_fields = dirty_policy.get("required_inventory_fields")
        if not isinstance(inventory_fields, list) or not REQUIRED_DIRTY_TRIAGE_INVENTORY_FIELDS.issubset(set(inventory_fields)):
            errors.append("dirty_triage_policy.required_inventory_fields is incomplete")

    branch_policy = catalog.get("branch_cleanup_policy")
    if not isinstance(branch_policy, dict):
        errors.append("branch_cleanup_policy must be an object")
    else:
        for key in (
            "validator_is_read_only",
            "inventory_required_before_branch_delete",
            "github_pr_state_must_be_checked_before_unmerged_claim",
            "squash_merge_safe_classification_required",
            "worktree_branch_delete_blocked",
            "backup_dirty_branch_delete_blocked",
            "remote_delete_requires_explicit_operator_request",
            "mutating_cleanup_commands_require_operator_request",
            "local_delete_requires_cleanup_plan_proof",
            "unknown_ownership_delete_blocked",
        ):
            if branch_policy.get(key) is not True:
                errors.append(f"branch_cleanup_policy.{key} must be true")
        backup_prefixes = branch_policy.get("backup_dirty_prefixes")
        if not isinstance(backup_prefixes, list) or not {"backup/", "codex/bears-plugin-stash-backup-"}.issubset(
            set(backup_prefixes)
        ):
            errors.append("branch_cleanup_policy.backup_dirty_prefixes is incomplete")
        required_classes = branch_policy.get("required_branch_classes")
        if not isinstance(required_classes, list) or not REQUIRED_BRANCH_CLASSES.issubset(set(required_classes)):
            errors.append("branch_cleanup_policy.required_branch_classes is incomplete")
        safe_classes = branch_policy.get("safe_local_delete_classes")
        if not isinstance(safe_classes, list) or not {
            "github_merged_cleanup_candidate",
            "ancestry_merged_cleanup_candidate",
        }.issubset(set(safe_classes)):
            errors.append("branch_cleanup_policy.safe_local_delete_classes is incomplete")
        blocked_classes = branch_policy.get("blocked_delete_classes")
        if not isinstance(blocked_classes, list) or not {
            "main_branch",
            "worktree_attached",
            "backup_dirty_preserve",
            "open_pr_review_required",
        }.issubset(set(blocked_classes)):
            errors.append("branch_cleanup_policy.blocked_delete_classes is incomplete")
        inventory_fields = branch_policy.get("required_inventory_fields")
        if not isinstance(inventory_fields, list) or not REQUIRED_BRANCH_INVENTORY_FIELDS.issubset(set(inventory_fields)):
            errors.append("branch_cleanup_policy.required_inventory_fields is incomplete")
        forbidden_cleanup = branch_policy.get("forbidden_automatic_commands")
        if not isinstance(forbidden_cleanup, list) or not REQUIRED_BRANCH_FORBIDDEN_AUTOMATIC.issubset(set(forbidden_cleanup)):
            errors.append("branch_cleanup_policy.forbidden_automatic_commands is incomplete")
        if branch_policy.get("remote_inventory_required_before_remote_delete") is not True:
            errors.append("branch_cleanup_policy.remote_inventory_required_before_remote_delete must be true")
        closeout_gate = branch_policy.get("post_merge_closeout_gate")
        if not isinstance(closeout_gate, dict):
            errors.append("branch_cleanup_policy.post_merge_closeout_gate must be an object")
        else:
            expected_gate_values = {
                "required_after_pr_merge": True,
                "must_report_zero_local_delete_eligible": True,
                "must_report_zero_remote_delete_eligible": True,
                "worktree_attached_merged_branch_blocks_closeout": True,
            }
            for key, expected in expected_gate_values.items():
                if closeout_gate.get(key) is not expected:
                    errors.append(f"branch_cleanup_policy.post_merge_closeout_gate.{key} must be true")
            if closeout_gate.get("output_schema") != BRANCH_CLOSEOUT_SCHEMA:
                errors.append(
                    f"branch_cleanup_policy.post_merge_closeout_gate.output_schema must be {BRANCH_CLOSEOUT_SCHEMA}"
                )
            command = closeout_gate.get("command")
            if not isinstance(command, str) or "branch-closeout-gate" not in command:
                errors.append("branch_cleanup_policy.post_merge_closeout_gate.command must call branch-closeout-gate")
        remote_classes = branch_policy.get("required_remote_branch_classes")
        if not isinstance(remote_classes, list) or not REQUIRED_REMOTE_BRANCH_CLASSES.issubset(set(remote_classes)):
            errors.append("branch_cleanup_policy.required_remote_branch_classes is incomplete")
        safe_remote_classes = branch_policy.get("safe_remote_delete_classes")
        if not isinstance(safe_remote_classes, list) or not {
            "remote_github_merged_cleanup_candidate",
            "remote_ancestry_merged_cleanup_candidate",
        }.issubset(set(safe_remote_classes)):
            errors.append("branch_cleanup_policy.safe_remote_delete_classes is incomplete")
        remote_inventory_fields = branch_policy.get("required_remote_inventory_fields")
        if not isinstance(remote_inventory_fields, list) or not REQUIRED_REMOTE_BRANCH_INVENTORY_FIELDS.issubset(set(remote_inventory_fields)):
            errors.append("branch_cleanup_policy.required_remote_inventory_fields is incomplete")
        gitlink_audit = branch_policy.get("gitlink_target_audit")
        if not isinstance(gitlink_audit, dict):
            errors.append("branch_cleanup_policy.gitlink_target_audit must be an object")
        else:
            if gitlink_audit.get("required_for_gitlink_closeout") is not True:
                errors.append("branch_cleanup_policy.gitlink_target_audit.required_for_gitlink_closeout must be true")
            if gitlink_audit.get("local_checkout_must_match_parent_target_for_local_claims") is not True:
                errors.append(
                    "branch_cleanup_policy.gitlink_target_audit.local_checkout_must_match_parent_target_for_local_claims must be true"
                )
            if gitlink_audit.get("stale_local_checkout_blocks_local_claims") is not True:
                errors.append("branch_cleanup_policy.gitlink_target_audit.stale_local_checkout_blocks_local_claims must be true")
            if gitlink_audit.get("output_schema") != GITLINK_AUDIT_SCHEMA:
                errors.append(f"branch_cleanup_policy.gitlink_target_audit.output_schema must be {GITLINK_AUDIT_SCHEMA}")
            command = gitlink_audit.get("command")
            if not isinstance(command, str) or "gitlink-audit" not in command:
                errors.append("branch_cleanup_policy.gitlink_target_audit.command must call gitlink-audit")
            fields = gitlink_audit.get("required_output_fields")
            if not isinstance(fields, list) or not REQUIRED_GITLINK_AUDIT_FIELDS.issubset(set(fields)):
                errors.append("branch_cleanup_policy.gitlink_target_audit.required_output_fields is incomplete")
        branch_prefix = branch_policy.get("branch_prefix_policy")
        if not isinstance(branch_prefix, dict):
            errors.append("branch_cleanup_policy.branch_prefix_policy must be an object")
        else:
            if branch_prefix.get("default_prefix") != "codex/":
                errors.append("branch_cleanup_policy.branch_prefix_policy.default_prefix must be codex/")
            if branch_prefix.get("assignment_override_required_for_non_default") is not True:
                errors.append(
                    "branch_cleanup_policy.branch_prefix_policy.assignment_override_required_for_non_default must be true"
                )
            if branch_prefix.get("required_before_push_or_pr") is not True:
                errors.append("branch_cleanup_policy.branch_prefix_policy.required_before_push_or_pr must be true")
            if branch_prefix.get("output_schema") != BRANCH_PREFIX_SCHEMA:
                errors.append(f"branch_cleanup_policy.branch_prefix_policy.output_schema must be {BRANCH_PREFIX_SCHEMA}")
            command = branch_prefix.get("command")
            if not isinstance(command, str) or "branch-prefix-check" not in command:
                errors.append("branch_cleanup_policy.branch_prefix_policy.command must call branch-prefix-check")
            fields = branch_prefix.get("required_output_fields")
            if not isinstance(fields, list) or not REQUIRED_BRANCH_PREFIX_FIELDS.issubset(set(fields)):
                errors.append("branch_cleanup_policy.branch_prefix_policy.required_output_fields is incomplete")
        issue_mapping = branch_policy.get("issue_mapping")
        if not isinstance(issue_mapping, dict):
            errors.append("branch_cleanup_policy.issue_mapping must be an object")
        else:
            for issue, lane in REQUIRED_BRANCH_CLEANUP_ISSUE_MAPPING.items():
                if issue_mapping.get(issue) != lane:
                    errors.append(f"branch_cleanup_policy.issue_mapping.{issue} must be {lane}")

    path_safety = catalog.get("path_safety")
    if not isinstance(path_safety, dict):
        errors.append("path_safety must be an object")
    else:
        secret_fragments = path_safety.get("secret_path_fragments_block_commit")
        if not isinstance(secret_fragments, list) or not REQUIRED_SECRET_FRAGMENTS.issubset(set(secret_fragments)):
            errors.append("path_safety.secret_path_fragments_block_commit is incomplete")
        log_fragments = path_safety.get("raw_log_fragments_require_operator_review")
        if not isinstance(log_fragments, list) or not REQUIRED_LOG_FRAGMENTS.issubset(set(log_fragments)):
            errors.append("path_safety.raw_log_fragments_require_operator_review is incomplete")
        if path_safety.get("external_workspace_changes_must_be_reported") is not True:
            errors.append("path_safety.external_workspace_changes_must_be_reported must be true")
        if path_safety.get("raw_file_content_scan_allowed") is not False:
            errors.append("path_safety.raw_file_content_scan_allowed must be false")
        if path_safety.get("allowed_changed_paths_required_for_closeout") is not True:
            errors.append("path_safety.allowed_changed_paths_required_for_closeout must be true")
        if path_safety.get("dirty_worktree_blocker_status") != "DIRTY_WORKTREE_BLOCKER":
            errors.append("path_safety.dirty_worktree_blocker_status must be DIRTY_WORKTREE_BLOCKER")
        canonical_policy = path_safety.get("canonical_plugin_checkout_policy")
        if not isinstance(canonical_policy, dict):
            errors.append("path_safety.canonical_plugin_checkout_policy must be an object")
        else:
            if canonical_policy.get("canonical_root") != "/srv/bears/plugins/bears":
                errors.append("path_safety.canonical_plugin_checkout_policy.canonical_root must be /srv/bears/plugins/bears")
            if canonical_policy.get("hidden_temporary_worktree_default_allowed") is not False:
                errors.append("path_safety.canonical_plugin_checkout_policy.hidden_temporary_worktree_default_allowed must be false")
            required_checks = canonical_policy.get("before_plugin_edits_required_checks")
            if not isinstance(required_checks, list) or not REQUIRED_CANONICAL_PLUGIN_CHECKS.issubset(set(required_checks)):
                errors.append("path_safety.canonical_plugin_checkout_policy.before_plugin_edits_required_checks is incomplete")
            forbidden_states = canonical_policy.get("forbidden_closeout_states")
            if not isinstance(forbidden_states, list) or not REQUIRED_CANONICAL_PLUGIN_FORBIDDEN_STATES.issubset(set(forbidden_states)):
                errors.append("path_safety.canonical_plugin_checkout_policy.forbidden_closeout_states is incomplete")
        closeout_preflight = path_safety.get("closeout_preflight")
        if not isinstance(closeout_preflight, dict):
            errors.append("path_safety.closeout_preflight must be an object")
        else:
            for key in (
                "required_for_ledger_gitlink_closeout",
                "allowed_paths_required",
                "current_branch_must_match_task",
                "carry_forward_list_is_allowed_paths",
                "gitlink_object_proof_required",
            ):
                if closeout_preflight.get(key) is not True:
                    errors.append(f"path_safety.closeout_preflight.{key} must be true")
            if closeout_preflight.get("output_schema") != CLOSEOUT_PREFLIGHT_SCHEMA:
                errors.append(f"path_safety.closeout_preflight.output_schema must be {CLOSEOUT_PREFLIGHT_SCHEMA}")
            command = closeout_preflight.get("command")
            if not isinstance(command, str) or "closeout-preflight" not in command:
                errors.append("path_safety.closeout_preflight.command must call closeout-preflight")
            elif "--gitlink-proof" not in command:
                errors.append("path_safety.closeout_preflight.command must require --gitlink-proof")
            fields = closeout_preflight.get("required_output_fields")
            if not isinstance(fields, list) or not REQUIRED_CLOSEOUT_PREFLIGHT_FIELDS.issubset(set(fields)):
                errors.append("path_safety.closeout_preflight.required_output_fields is incomplete")

    output_contract = catalog.get("output_contract")
    if not isinstance(output_contract, dict):
        errors.append("output_contract must be an object")
    else:
        if output_contract.get("schema") != INSPECTION_SCHEMA:
            errors.append(f"output_contract.schema must be {INSPECTION_SCHEMA}")
        required = output_contract.get("top_level_required")
        if not isinstance(required, list) or not REQUIRED_TOP_LEVEL.issubset(set(required)):
            errors.append("output_contract.top_level_required is incomplete")
        if output_contract.get("ready_status") != "GIT_DISCIPLINE_READY":
            errors.append("output_contract.ready_status must be GIT_DISCIPLINE_READY")
        blocked = output_contract.get("blocked_statuses")
        if not isinstance(blocked, list) or "GIT_DISCIPLINE_BLOCKED" not in blocked:
            errors.append("output_contract.blocked_statuses must include GIT_DISCIPLINE_BLOCKED")
        if isinstance(blocked, list) and "DIRTY_WORKTREE_BLOCKER" not in blocked:
            errors.append("output_contract.blocked_statuses must include DIRTY_WORKTREE_BLOCKER")

    if check_files:
        for key in ("route_target", "reference_doc"):
            value = catalog.get(key)
            if isinstance(value, str) and not _resolve_plugin_owned_path(value).is_file():
                errors.append(f"{key} file does not exist: {value}")

    if role_catalog is not None:
        try:
            platform_roles = _load_platform_roles_module()
            route = platform_roles.route_target(role_catalog, str(PLUGIN_ROOT / "scripts/git_discipline.py"), plugin_root=PLUGIN_ROOT)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot route git discipline validator: {exc}")
        else:
            if route.get("status") != "matched":
                errors.append("git discipline validator route must match")
            if route.get("concrete_part") != CONCRETE_PART:
                errors.append(f"git discipline validator must route to {CONCRETE_PART}")
            if route.get("primary_role") != "bears-subagents-roles-governor":
                errors.append("git discipline validator must route to bears-subagents-roles-governor")

    return errors


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _local_git_config(repo: Path, key: str) -> str:
    result = _run_git(repo, "config", "--local", "--get", key)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _resolve_repo_relative(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def inspect_plugin_worktree_preflight(
    repo: Path,
    catalog: dict[str, Any],
    *,
    cwd: Path | None = None,
    approved_isolated_worktree: bool = False,
) -> dict[str, Any]:
    """Check that @Bears plugin work starts in the canonical checkout."""

    path_safety = catalog.get("path_safety", {}) if isinstance(catalog.get("path_safety"), dict) else {}
    policy = path_safety.get("canonical_plugin_checkout_policy", {})
    if not isinstance(policy, dict):
        policy = {}
    canonical_root = Path(str(policy.get("canonical_root", "/srv/bears/plugins/bears"))).resolve()
    cwd_path = (cwd or Path.cwd()).resolve()
    repo_root = repo.resolve()

    top_result = _run_git(repo_root, "rev-parse", "--show-toplevel")
    git_toplevel = (
        _resolve_repo_relative(repo_root, top_result.stdout.strip())
        if top_result.returncode == 0 and top_result.stdout.strip()
        else None
    )
    core_worktree_result = _run_git(repo_root, "config", "--get", "core.worktree")
    core_worktree_raw = core_worktree_result.stdout.strip() if core_worktree_result.returncode == 0 else ""
    core_worktree = _resolve_repo_relative(git_toplevel or repo_root, core_worktree_raw) if core_worktree_raw else None
    status_result = _run_git(canonical_root, "status", "--short", "--branch")
    status_captured = status_result.returncode == 0

    block_reasons: list[str] = []
    if cwd_path != canonical_root:
        block_reasons.append("PLUGIN_CWD_MISMATCH")
    if git_toplevel != canonical_root:
        block_reasons.append("PLUGIN_TOPLEVEL_REDIRECTED")
    if core_worktree is not None and core_worktree != canonical_root:
        block_reasons.append("PLUGIN_CORE_WORKTREE_MISMATCH")
    if not status_captured:
        block_reasons.append("UNSYNCED_CANONICAL_CHECKOUT")

    if block_reasons and approved_isolated_worktree:
        status = "PLUGIN_WORKTREE_REVIEW"
        work_allowed = False
    elif block_reasons:
        status = "PLUGIN_WORKTREE_BLOCKED"
        work_allowed = False
    else:
        status = "PLUGIN_WORKTREE_PASS"
        work_allowed = True

    return {
        "schema": PLUGIN_WORKTREE_PREFLIGHT_SCHEMA,
        "status": status,
        "work_allowed": work_allowed,
        "canonical_root": str(canonical_root),
        "cwd": str(cwd_path),
        "actual_toplevel": str(git_toplevel) if git_toplevel is not None else "",
        "core_worktree": str(core_worktree) if core_worktree is not None else "",
        "canonical_status_captured": status_captured,
        "canonical_status": status_result.stdout.strip() if status_captured else "",
        "approved_isolated_worktree": approved_isolated_worktree,
        "block_reasons": block_reasons,
        "read_only": True,
    }


def inspect_worker_git_identity(repo: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    """Check the fixed local worker identity without mutating Git config."""
    command_policy = catalog.get("command_policy", {}) if isinstance(catalog.get("command_policy"), dict) else {}
    identity = command_policy.get("safe_worker_git_identity", {})
    if not isinstance(identity, dict):
        return {
            "worker_git_identity_configured": False,
            "worker_git_identity_label": "",
        }
    expected_name = str(identity.get("user_name", "")).strip()
    expected_email = str(identity.get("user_email", "")).strip()
    label = str(identity.get("fixed_public_identity_label", "")).strip()
    configured = bool(
        expected_name
        and expected_email
        and _local_git_config(repo, "user.name") == expected_name
        and _local_git_config(repo, "user.email") == expected_email
    )
    return {
        "worker_git_identity_configured": configured,
        "worker_git_identity_label": label,
    }


def _parse_changed_paths(status_output: str) -> list[dict[str, str]]:
    paths: list[dict[str, str]] = []
    for line in status_output.splitlines():
        if not line or line.startswith("##"):
            continue
        status = line[:2]
        raw_path = line[3:].strip() if len(line) > 3 else ""
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        paths.append({"status": status, "path": raw_path})
    return paths


def _contains_fragment(path_value: str, fragments: list[str]) -> bool:
    lower = path_value.casefold()
    return any(fragment.casefold() in lower for fragment in fragments)


def _matches_exception_root(path_value: str, roots: list[str]) -> bool:
    normalized = path_value.replace("\\", "/").strip().strip("/")
    for root in roots:
        if not isinstance(root, str) or not root.strip():
            continue
        normalized_root = root.replace("\\", "/").strip().strip("/")
        if normalized == normalized_root or normalized.startswith(normalized_root + "/"):
            return True
    return False


def _normalize_repo_path(path_value: str) -> str:
    return path_value.replace("\\", "/").strip().strip("/")


def _path_matches_allowed(path_value: str, allowed_roots: list[str]) -> bool:
    normalized = _normalize_repo_path(path_value)
    for root in allowed_roots:
        if not isinstance(root, str) or not root.strip():
            continue
        normalized_root = _normalize_repo_path(root)
        if normalized == normalized_root or normalized.startswith(normalized_root + "/"):
            return True
    return False


def _is_gitlink_path(repo: Path, path_value: str) -> bool:
    result = _run_git(repo, "ls-files", "-s", "--", path_value)
    if result.returncode != 0:
        return False
    return any(line.startswith("160000 ") for line in result.stdout.splitlines())


def _gitlink_head_object(repo: Path, path_value: str) -> str:
    result = _run_git(repo, "ls-tree", "HEAD", "--", path_value)
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "160000":
            return parts[2]
    return ""


def _gitlink_index_object(repo: Path, path_value: str) -> str:
    result = _run_git(repo, "ls-files", "-s", "--", path_value)
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "160000":
            return parts[1]
    return ""


def _parse_worktree_branches(output: str) -> dict[str, str]:
    branches: dict[str, str] = {}
    current_path = ""
    for line in output.splitlines():
        if line.startswith("worktree "):
            current_path = line.removeprefix("worktree ").strip()
        elif line.startswith("branch "):
            branch = line.removeprefix("branch ").strip().removeprefix("refs/heads/")
            if branch:
                branches[branch] = current_path
    return branches


def _parse_gitlink_ls_tree(output: str, gitlink_path: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"expected one gitlink entry for {gitlink_path}")
    line = lines[0]
    if "\t" not in line:
        raise RuntimeError("git ls-tree output missing path separator")
    meta, path_value = line.split("\t", 1)
    parts = meta.split()
    if len(parts) != 3:
        raise RuntimeError("git ls-tree output must contain mode, type, and object")
    mode, object_type, object_id = parts
    if path_value != gitlink_path:
        raise RuntimeError(f"git ls-tree returned {path_value}, expected {gitlink_path}")
    if mode != "160000" or object_type != "commit":
        raise RuntimeError(f"{gitlink_path} is not a gitlink commit entry")
    return object_id


def _load_branch_prefix_override(path: Path | None) -> dict[str, str]:
    if path is None:
        return {"prefix": "", "reason": "", "approved_by": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("assignment packet must be a JSON object")
    override = data.get("branch_prefix_override")
    if not isinstance(override, dict):
        return {"prefix": "", "reason": "", "approved_by": ""}
    return {
        "prefix": str(override.get("prefix", "")),
        "reason": str(override.get("reason", "")),
        "approved_by": str(override.get("approved_by", "")),
    }


def inspect_branch_prefix(
    branch: str,
    *,
    default_prefix: str = "codex/",
    assignment_packet: Path | None = None,
) -> dict[str, Any]:
    """Validate branch prefix before push or PR creation."""
    normalized_branch = branch.strip()
    if not normalized_branch:
        raise RuntimeError("branch is required")
    if not default_prefix:
        raise RuntimeError("default prefix is required")
    override = _load_branch_prefix_override(assignment_packet)
    override_prefix = override["prefix"].strip()
    override_complete = bool(override_prefix and override["reason"].strip() and override["approved_by"].strip())
    uses_default = normalized_branch.startswith(default_prefix)
    uses_override = bool(override_complete and normalized_branch.startswith(override_prefix))
    status = "BRANCH_PREFIX_PASS" if uses_default or uses_override else "BRANCH_PREFIX_BLOCKED"
    reasons: list[str] = []
    if not uses_default and not override_complete:
        reasons.append("missing_assignment_prefix_override")
    elif not uses_default and not uses_override:
        reasons.append("branch_does_not_match_assignment_prefix_override")
    return {
        "schema": BRANCH_PREFIX_SCHEMA,
        "branch": normalized_branch,
        "default_prefix": default_prefix,
        "assignment_packet": str(assignment_packet.resolve()) if assignment_packet is not None else "",
        "override_prefix": override_prefix,
        "override_used": uses_override,
        "status": status,
        "branch_prefix_check": "PASS" if status == "BRANCH_PREFIX_PASS" else "FAIL",
        "read_only": True,
        "block_reasons": reasons,
    }


def inspect_gitlink_target(
    repo: Path,
    *,
    tree_ref: str,
    gitlink_path: str,
    expected_target: str = "",
    local_checkout: Path | None = None,
    claim_source: str = "parent-gitlink",
) -> dict[str, Any]:
    """Audit a parent gitlink target without trusting a stale local checkout."""
    top_result = _run_git(repo, "rev-parse", "--show-toplevel")
    if top_result.returncode != 0:
        raise RuntimeError(top_result.stderr.strip() or "not a git repository")
    repo_root = Path(top_result.stdout.strip())
    normalized_path = _normalize_repo_path(gitlink_path)
    if not normalized_path:
        raise RuntimeError("gitlink path is required")
    ls_tree = _run_git(repo_root, "ls-tree", tree_ref, "--", normalized_path)
    if ls_tree.returncode != 0:
        raise RuntimeError(ls_tree.stderr.strip() or "git ls-tree failed")
    parent_target = _parse_gitlink_ls_tree(ls_tree.stdout, normalized_path)

    local_path = local_checkout.resolve() if local_checkout is not None else None
    local_head = ""
    local_status = "NOT_CHECKED"
    local_usable = False
    if local_path is not None:
        if not local_path.exists():
            local_status = "LOCAL_CHECKOUT_MISSING"
        else:
            local_result = _run_git(local_path, "rev-parse", "HEAD")
            if local_result.returncode != 0:
                local_status = "LOCAL_CHECKOUT_MISSING"
            else:
                local_head = local_result.stdout.strip()
                if local_head == parent_target:
                    local_status = "MATCHES_PARENT_TARGET"
                    local_usable = True
                else:
                    local_status = "STALE_LOCAL_CHECKOUT"

    if claim_source not in {"parent-gitlink", "local-checkout"}:
        raise RuntimeError("claim source must be parent-gitlink or local-checkout")
    expected_mismatch = bool(expected_target and expected_target != parent_target)
    local_claim_blocked = claim_source == "local-checkout" and not local_usable
    status = "GITLINK_AUDIT_PASS"
    if expected_mismatch or local_claim_blocked:
        status = "GITLINK_AUDIT_BLOCKED"
    claim_object = parent_target if claim_source == "parent-gitlink" else local_head
    return {
        "schema": GITLINK_AUDIT_SCHEMA,
        "repo_root": str(repo_root),
        "tree_ref": tree_ref,
        "gitlink_path": normalized_path,
        "parent_gitlink_target": parent_target,
        "expected_target": expected_target,
        "expected_target_matches": not expected_mismatch,
        "local_checkout": str(local_path) if local_path is not None else "",
        "local_checkout_head": local_head,
        "local_checkout_status": local_status,
        "claim_source": claim_source,
        "claim_object_used": claim_object,
        "local_checkout_evidence_usable": local_usable,
        "status": status,
        "read_only": True,
        "block_reasons": (
            (["expected_target_mismatch"] if expected_mismatch else [])
            + (["local_checkout_not_parent_target"] if local_claim_blocked else [])
        ),
    }


def _load_github_prs(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("pullRequests", data.get("items", []))
    if not isinstance(data, list):
        raise ValueError("github PR JSON must be a list or an object with pullRequests/items")
    by_branch: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        branch = item.get("headRefName")
        if isinstance(branch, str) and branch:
            by_branch.setdefault(branch, []).append(item)
    return by_branch


def _load_workflow_state(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_branches = data.get("branches", data.get("branch_states", data.get("items", [])))
    elif isinstance(data, list):
        raw_branches = data
    else:
        raise ValueError("workflow state JSON must be an object or list")
    by_branch: dict[str, dict[str, Any]] = {}
    if isinstance(raw_branches, dict):
        for branch, item in raw_branches.items():
            if isinstance(branch, str) and branch and isinstance(item, dict):
                branch_item = dict(item)
                branch_item.setdefault("branch", branch)
                by_branch[branch] = branch_item
    elif isinstance(raw_branches, list):
        for item in raw_branches:
            if not isinstance(item, dict):
                continue
            branch = item.get("branch", item.get("headRefName"))
            if isinstance(branch, str) and branch:
                by_branch[branch] = dict(item)
    else:
        raise ValueError("workflow state branches must be an object or list")
    return by_branch


def _merge_branch_state(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "worker_state_files":
            continue
        if key not in merged or merged.get(key) in (None, "", False, [], {}):
            merged[key] = value
        elif key == "cleanup_authority" and isinstance(merged.get(key), dict) and isinstance(value, dict):
            authority = dict(merged[key])
            authority.update(value)
            merged[key] = authority
        elif key == "worker_state" and str(value).strip().casefold() in {"active", "implementing", "in_progress", "fixing"}:
            merged[key] = value
    files = list(merged.get("worker_state_files", [])) if isinstance(merged.get("worker_state_files"), list) else []
    source = incoming.get("_source_worker_state_file")
    if isinstance(source, str) and source and source not in files:
        files.append(source)
    if files:
        merged["worker_state_files"] = files
    return merged


def _normalize_worker_state_item(data: Any, source: Path) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    branch = data.get("branch", data.get("headRefName", data.get("current_branch")))
    if isinstance(branch, dict):
        branch = branch.get("name", branch.get("branch"))
    if not isinstance(branch, str) or not branch.strip():
        return None
    item = dict(data)
    item["branch"] = branch.strip()
    item["_source_worker_state_file"] = str(source)
    heartbeat = item.get("heartbeat")
    if isinstance(heartbeat, dict):
        item.setdefault("heartbeat_fresh", heartbeat.get("fresh"))
        item.setdefault("heartbeat_at", heartbeat.get("at", heartbeat.get("updated_at")))
    pr = item.get("pr", item.get("pull_request"))
    if isinstance(pr, dict):
        item.setdefault("open_pr", str(pr.get("state", "")).strip().upper() == "OPEN")
    lock = item.get("scope_lock")
    if isinstance(lock, dict):
        item["scope_lock"] = lock.get("active", lock.get("present", bool(lock)))
    return item


def _load_worker_state_files(paths: list[Path] | None) -> dict[str, dict[str, Any]]:
    if not paths:
        return {}
    by_branch: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        items: list[Any]
        if isinstance(data, dict) and isinstance(data.get("workers"), list):
            items = data["workers"]
        elif isinstance(data, dict) and isinstance(data.get("worker_states"), list):
            items = data["worker_states"]
        else:
            items = [data]
        for raw_item in items:
            item = _normalize_worker_state_item(raw_item, path)
            if item is None:
                continue
            branch = item["branch"]
            by_branch[branch] = _merge_branch_state(by_branch.get(branch, {}), item)
    return by_branch


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, dict):
        status = value.get("status", value.get("state", value.get("proof")))
        return _truthy(status) or value.get("present") is True or value.get("fresh") is True or value.get("active") is True
    if isinstance(value, str):
        return value.strip().casefold() in {
            "1",
            "true",
            "yes",
            "present",
            "active",
            "fresh",
            "locked",
            "approved",
            "pass",
            "passed",
            "ready",
            "authorized",
            "authority",
        }
    return False


def _workflow_state_for_branch(workflow_state: dict[str, dict[str, Any]], branch: str) -> dict[str, Any]:
    item = workflow_state.get(branch, {})
    return item if isinstance(item, dict) else {}


def _combine_state_maps(*maps: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for state_map in maps:
        for branch, state in state_map.items():
            combined[branch] = _merge_branch_state(combined.get(branch, {}), state)
    return combined


def _owner_known(branch_state: dict[str, Any]) -> bool:
    for key in ("owner", "owner_role", "owning_role", "owning_agent", "assignment_id", "worker_id"):
        value = branch_state.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return branch_state.get("owner_known") is True


def _cleanup_plan_proof(branch_state: dict[str, Any]) -> bool:
    return _truthy(branch_state.get("cleanup_plan_proof")) or _truthy(branch_state.get("cleanup_plan"))


def _remote_cleanup_authority(branch_state: dict[str, Any]) -> bool:
    cleanup_authority = branch_state.get("cleanup_authority", {})
    if not isinstance(cleanup_authority, dict):
        cleanup_authority = {}
    return (
        _truthy(branch_state.get("remote_cleanup_authority"))
        or _truthy(branch_state.get("explicit_cleanup_authority"))
        or _truthy(cleanup_authority.get("remote_delete"))
        or _truthy(cleanup_authority.get("remote_cleanup"))
    )


def _local_cleanup_authority(branch_state: dict[str, Any]) -> bool:
    cleanup_authority = branch_state.get("cleanup_authority", {})
    if not isinstance(cleanup_authority, dict):
        cleanup_authority = {}
    return _cleanup_plan_proof(branch_state) and (
        _truthy(branch_state.get("local_cleanup_authority"))
        or _truthy(cleanup_authority.get("local_delete"))
        or not cleanup_authority
    )


def _cleanup_phase_ready(branch_state: dict[str, Any]) -> bool:
    values = [
        branch_state.get("cleanup_phase"),
        branch_state.get("closeout_state"),
        branch_state.get("merge_state"),
        branch_state.get("workflow_phase"),
        branch_state.get("state"),
    ]
    ready_values = {"closeout", "closeout_ready", "merge_ready", "merged", "post_merge", "cleanup_ready"}
    return any(isinstance(value, str) and value.strip().casefold() in ready_values for value in values) or (
        branch_state.get("closeout_ready") is True
        or branch_state.get("merge_ready") is True
        or branch_state.get("merged") is True
    )


def _active_dirty_proofs(prs: list[dict[str, Any]], branch_state: dict[str, Any]) -> list[str]:
    proofs: list[str] = []
    active_worker_states = {"active", "implementing", "in_progress", "fixing", "reviewing", "running"}
    worker_state = str(branch_state.get("worker_state", branch_state.get("state", ""))).strip().casefold()
    if branch_state.get("active_worker_state") is True or worker_state in active_worker_states:
        proofs.append("active_worker_state")
    if (
        _truthy(branch_state.get("heartbeat"))
        or _truthy(branch_state.get("heartbeat_fresh"))
        or bool(str(branch_state.get("heartbeat_at", "")).strip())
    ):
        proofs.append("heartbeat")
    if _truthy(branch_state.get("scope_lock")) or bool(str(branch_state.get("scope_lock_id", "")).strip()):
        proofs.append("scope_lock")
    if any(str(pr.get("state", "")).strip().upper() == "OPEN" for pr in prs):
        proofs.append("open_pr")
    if _truthy(branch_state.get("open_pr")) or str(branch_state.get("pr_state", "")).strip().upper() == "OPEN":
        proofs.append("open_pr")
    if _truthy(branch_state.get("live_session_proof")) or bool(str(branch_state.get("session_id", "")).strip()):
        proofs.append("live_session_proof")
    return sorted(dict.fromkeys(proofs))


def _dirty_triage_actions(catalog: dict[str, Any], outcome: str) -> list[str]:
    policy = catalog.get("dirty_triage_policy", {}) if isinstance(catalog.get("dirty_triage_policy"), dict) else {}
    state_machine = policy.get("state_machine", {}) if isinstance(policy.get("state_machine"), dict) else {}
    actions = state_machine.get("actions", {}) if isinstance(state_machine.get("actions"), dict) else {}
    outcome_actions = actions.get(outcome, [])
    if isinstance(outcome_actions, list):
        return [str(action) for action in outcome_actions if isinstance(action, str)]
    return sorted(REQUIRED_DIRTY_TRIAGE_ACTIONS.get(outcome, set()))


def classify_dirty_triage(
    branch: str,
    catalog: dict[str, Any],
    *,
    cleanup_class: str,
    prs: list[dict[str, Any]],
    branch_state: dict[str, Any],
    worktree_attached: bool = False,
    remote_branch: bool = False,
    safe_candidate: bool = False,
) -> dict[str, Any]:
    """Classify unclosed branch/worktree changes without deleting anything."""
    owner_known = _owner_known(branch_state)
    cleanup_plan = _cleanup_plan_proof(branch_state)
    local_authority = _local_cleanup_authority(branch_state)
    remote_authority = _remote_cleanup_authority(branch_state)
    cleanup_phase_ready = _cleanup_phase_ready(branch_state)
    active_proofs = _active_dirty_proofs(prs, branch_state)
    worker_state = str(branch_state.get("worker_state", branch_state.get("state", ""))).strip().casefold()
    useful_abandoned = _truthy(branch_state.get("useful_abandoned_code")) or _truthy(branch_state.get("useful_code"))
    abandoned = worker_state in {"abandoned", "stale", "orphaned"} or _truthy(branch_state.get("abandoned"))
    completed = worker_state in {"completed", "done", "closed"} or _truthy(branch_state.get("completed"))

    if active_proofs:
        outcome = "active_parallel_agent"
        proofs = active_proofs
    elif useful_abandoned:
        outcome = "useful_abandoned_code"
        proofs = ["useful_abandoned_code"]
    elif completed:
        outcome = "completed_needs_integration"
        proofs = ["completed_worker_state"]
    elif abandoned:
        outcome = "abandoned_needs_review"
        proofs = ["abandoned_worker_state"]
    elif (
        safe_candidate
        and owner_known
        and cleanup_plan
        and cleanup_phase_ready
        and not worktree_attached
        and cleanup_class != "backup_dirty_preserve"
        and (not remote_branch or remote_authority)
        and (remote_branch or local_authority)
    ):
        outcome = "obsolete_cleanup_candidate"
        proofs = ["known_owner", "cleanup_plan_proof"]
        if remote_branch:
            proofs.append("remote_cleanup_authority")
    else:
        outcome = "unsafe_dirty_blocker"
        proofs = []
        if not owner_known:
            proofs.append("unknown_ownership")
        if worktree_attached:
            proofs.append("attached_worktree")
        if cleanup_class == "backup_dirty_preserve":
            proofs.append("backup_dirty_branch")
        if safe_candidate and not cleanup_plan:
            proofs.append("cleanup_plan_missing")
        if safe_candidate and not cleanup_phase_ready:
            proofs.append("cleanup_not_closeout_or_merge_ready")
        if remote_branch and safe_candidate and not remote_authority:
            proofs.append("remote_cleanup_authority_missing")
        if not proofs:
            proofs.append("classification_required")

    auto_delete_allowed = outcome == "obsolete_cleanup_candidate"
    return {
        "branch": branch,
        "dirty_triage_outcome": outcome,
        "dirty_triage_actions": _dirty_triage_actions(catalog, outcome),
        "dirty_triage_proofs": proofs,
        "cleanup_plan_proof": cleanup_plan,
        "cleanup_authority": {
            "local_delete": local_authority,
            "remote_delete": remote_authority,
        },
        "cleanup_phase_ready": cleanup_phase_ready,
        "owner_known": owner_known,
        "auto_delete_allowed": auto_delete_allowed,
    }


def _match_path_pattern(path: str, pattern: str) -> bool:
    normalized = path.strip().lstrip("./")
    if not normalized:
        return False
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/") + "/"
        return normalized.startswith(prefix)
    return normalized == pattern.strip().lstrip("./")


def _matches_any_path_pattern(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    return any(_match_path_pattern(path, pattern) for pattern in patterns)


def evaluate_ignored_staging_command(
    command: str,
    *,
    explicit_allowed_paths: list[str] | None = None,
    operator_approval: bool = False,
    owning_contract: str = "",
    blocked_patterns: tuple[str, ...] = DEFAULT_IGNORED_STAGING_BLOCK_PATTERNS,
) -> dict[str, Any]:
    """Evaluate whether a staging command tries to force-add ignored workspace surfaces."""
    explicit_allowed_paths = explicit_allowed_paths or []
    tokens = command.replace("\n", " ").split()
    force_add = len(tokens) >= 3 and tokens[0:2] == ["git", "add"] and any(
        token in {"-f", "--force"} or ("f" in token[1:] and token.startswith("-") and not token.startswith("--"))
        for token in tokens[2:]
    )
    candidate_paths = [
        token
        for token in tokens[2:]
        if token not in {"-f", "--force", "-A", "--all", "--"} and not token.startswith("-")
    ]
    blocked_paths = [
        path
        for path in candidate_paths
        if _matches_any_path_pattern(path, blocked_patterns)
        and not _matches_any_path_pattern(path, explicit_allowed_paths)
    ]
    reasons: list[str] = []
    if force_add and blocked_paths:
        reasons.append("ignored_surface_force_add")
    if force_add and candidate_paths and not operator_approval:
        reasons.append("force_add_requires_operator_approval")
    if force_add and candidate_paths and not owning_contract.strip():
        reasons.append("force_add_requires_owning_contract")
    status = "IGNORED_STAGING_PASS" if not reasons else "IGNORED_STAGING_BLOCKED"
    return {
        "schema": IGNORED_STAGING_CHECK_SCHEMA,
        "status": status,
        "force_add_detected": force_add,
        "candidate_paths": candidate_paths,
        "blocked_paths": blocked_paths,
        "operator_approval": operator_approval,
        "owning_contract": owning_contract,
        "explicit_allowed_paths": explicit_allowed_paths,
        "block_patterns": list(blocked_patterns),
        "reasons": reasons,
        "read_only": True,
    }


def map_clean_worktree_target(
    *,
    canonical_root: str,
    worktree_root: str,
    worktree_target: str,
    canonical_target: str = "",
) -> dict[str, Any]:
    """Map an isolated worktree path back to the canonical route target."""
    canonical_root_path = Path(canonical_root).as_posix().rstrip("/")
    worktree_root_path = Path(worktree_root).as_posix().rstrip("/")
    worktree_target_path = Path(worktree_target).as_posix()
    reasons: list[str] = []
    mapped_target = canonical_target
    if not canonical_root_path or not worktree_root_path or not worktree_target_path:
        reasons.append("canonical_root_worktree_root_and_worktree_target_required")
    elif not worktree_target_path.startswith(worktree_root_path + "/") and worktree_target_path != worktree_root_path:
        reasons.append("worktree_target_not_under_worktree_root")
    else:
        relative = worktree_target_path.removeprefix(worktree_root_path).lstrip("/")
        inferred = f"{canonical_root_path}/{relative}" if relative else canonical_root_path
        if canonical_target and Path(canonical_target).as_posix() != inferred:
            reasons.append("canonical_target_mismatch")
        mapped_target = inferred
    status = "CLEAN_WORKTREE_TARGET_PASS" if not reasons else "CLEAN_WORKTREE_TARGET_BLOCKED"
    return {
        "schema": CLEAN_WORKTREE_TARGET_SCHEMA,
        "status": status,
        "canonical_root": canonical_root_path,
        "worktree_root": worktree_root_path,
        "worktree_target": worktree_target_path,
        "canonical_target": mapped_target,
        "route_target": mapped_target,
        "reasons": reasons,
        "read_only": True,
    }


def inspect_branch_base_preflight(
    repo: Path,
    catalog: dict[str, Any],
    *,
    intended_base: str = "origin/main",
    expected_branch: str = "",
    expected_branch_prefix: str = "",
    allowed_path: list[str] | None = None,
    allow_assigned_changes: bool = False,
    github_prs_json: Path | None = None,
) -> dict[str, Any]:
    """Inspect branch freshness before edits, staging, commit, push, or PR creation."""
    repo_root = repo.resolve()
    allowed_path = allowed_path or []
    block_reasons: list[str] = []
    branch_result = _run_git(repo_root, "symbolic-ref", "--short", "-q", "HEAD")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    if not branch:
        block_reasons.append("detached_head")

    head_result = _run_git(repo_root, "rev-parse", "HEAD")
    base_result = _run_git(repo_root, "rev-parse", "--verify", intended_base)
    head = head_result.stdout.strip() if head_result.returncode == 0 else ""
    base_sha = base_result.stdout.strip() if base_result.returncode == 0 else ""
    if not base_sha:
        block_reasons.append("intended_base_missing")

    status_result = _run_git(repo_root, "status", "--short", "--branch", "--untracked-files=all")
    status_lines = status_result.stdout.splitlines() if status_result.returncode == 0 else []
    status_head = status_lines[0] if status_lines else ""
    changed_items = _parse_changed_paths(status_result.stdout if status_result.returncode == 0 else "")
    changed_paths = [item["path"] for item in changed_items]
    normalized_allowed_paths = [_normalize_repo_path(path) for path in allowed_path if path.strip()]
    disallowed_paths = [
        path for path in changed_paths
        if normalized_allowed_paths and not _path_matches_allowed(path, normalized_allowed_paths)
    ]
    if changed_items and not allow_assigned_changes:
        block_reasons.append("dirty_worktree")
    if "[gone]" in status_head:
        block_reasons.append("upstream_gone")
    if expected_branch and branch != expected_branch:
        block_reasons.append("current_branch_mismatch")
    if expected_branch_prefix and not branch.startswith(expected_branch_prefix):
        block_reasons.append("current_branch_prefix_mismatch")
    if disallowed_paths:
        block_reasons.append("assigned_file_diff_mismatch")

    if base_sha:
        ancestor_result = _run_git(repo_root, "merge-base", "--is-ancestor", intended_base, "HEAD")
        if ancestor_result.returncode != 0:
            block_reasons.append("intended_base_not_ancestor")

    prs_by_branch = _load_github_prs(github_prs_json)
    branch_prs = prs_by_branch.get(branch, []) if branch else []
    merged_pr_numbers = [
        pr.get("number")
        for pr in branch_prs
        if pr.get("state") == "MERGED" or pr.get("mergedAt")
    ]
    if merged_pr_numbers:
        block_reasons.append("branch_has_merged_pr")

    status = "BRANCH_BASE_PREFLIGHT_PASS" if not block_reasons else "BRANCH_BASE_PREFLIGHT_BLOCKED"
    return {
        "schema": BRANCH_BASE_PREFLIGHT_SCHEMA,
        "repo_root": str(repo_root),
        "branch": branch,
        "head": head,
        "intended_base": intended_base,
        "intended_base_sha": base_sha,
        "expected_branch": expected_branch,
        "expected_branch_prefix": expected_branch_prefix,
        "allowed_changed_paths": allowed_path,
        "assigned_changes_allowed": allow_assigned_changes,
        "changed_paths": changed_paths,
        "disallowed_changed_paths": disallowed_paths,
        "github_pr_numbers": [pr.get("number") for pr in branch_prs if isinstance(pr.get("number"), int)],
        "github_pr_states": sorted({str(pr.get("state")) for pr in branch_prs if isinstance(pr.get("state"), str)}),
        "merged_pr_numbers": [number for number in merged_pr_numbers if isinstance(number, int)],
        "status": status,
        "edit_allowed": status == "BRANCH_BASE_PREFLIGHT_PASS",
        "stage_allowed": status == "BRANCH_BASE_PREFLIGHT_PASS",
        "commit_allowed_after_validation": status == "BRANCH_BASE_PREFLIGHT_PASS",
        "push_allowed": status == "BRANCH_BASE_PREFLIGHT_PASS",
        "pr_create_allowed": status == "BRANCH_BASE_PREFLIGHT_PASS",
        "block_reasons": block_reasons,
        "read_only": True,
        "catalog_issue": "BearsCLOUD/bears_plugin#88",
    }


def _branch_creation_hint(repo: Path, branch: str) -> str:
    result = _run_git(repo, "reflog", "show", "--date=iso", "--format=%gd %gs", branch)
    if result.returncode != 0:
        return ""
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _cleanup_class(branch: str, worktree_path: str, backup_prefixes: list[str], prs: list[dict[str, Any]], ancestry: bool, remote_exists: bool) -> tuple[str, str]:
    if branch in {"main", "master"}:
        return "main_branch", "main branch is never a cleanup candidate"
    if worktree_path:
        return "worktree_attached", "branch is attached to a worktree"
    if any(branch.startswith(prefix) for prefix in backup_prefixes):
        return "backup_dirty_preserve", "branch name marks preserved dirty or backup state"
    if any(pr.get("state") == "MERGED" or pr.get("mergedAt") for pr in prs):
        return "github_merged_cleanup_candidate", ""
    if ancestry:
        return "ancestry_merged_cleanup_candidate", ""
    if any(pr.get("state") == "OPEN" for pr in prs):
        return "open_pr_review_required", "branch has an open GitHub PR"
    if any(pr.get("state") == "CLOSED" and not pr.get("mergedAt") for pr in prs):
        return "closed_unmerged_review_required", "branch has a closed unmerged GitHub PR"
    if remote_exists:
        return "remote_branch_without_pr_review_required", "remote branch exists without merged PR proof"
    return "local_only_review_required", "local branch has no merged PR or ancestry proof"


def _remote_cleanup_class(branch: str, local_exists: bool, prs: list[dict[str, Any]], ancestry: bool) -> tuple[str, str]:
    if branch in {"main", "master"}:
        return "remote_main_branch", "remote main branch is never a cleanup candidate"
    if local_exists:
        return "remote_tracking_local_present", "local branch exists; local cleanup must be resolved first"
    if any(pr.get("state") == "MERGED" or pr.get("mergedAt") for pr in prs):
        return "remote_github_merged_cleanup_candidate", ""
    if ancestry:
        return "remote_ancestry_merged_cleanup_candidate", ""
    if any(pr.get("state") == "OPEN" for pr in prs):
        return "remote_open_pr_review_required", "remote branch has an open GitHub PR"
    if any(pr.get("state") == "CLOSED" and not pr.get("mergedAt") for pr in prs):
        return "remote_closed_unmerged_review_required", "remote branch has a closed unmerged GitHub PR"
    return "remote_without_pr_review_required", "remote branch lacks merged PR or ancestry proof"


def _inspect_remote_branches(
    repo_root: Path,
    catalog: dict[str, Any],
    *,
    base_ref: str,
    prs_by_branch: dict[str, list[dict[str, Any]]],
    workflow_state: dict[str, dict[str, Any]],
    worker_state: dict[str, dict[str, Any]],
    local_branches: set[str],
    safe_remote_classes: set[str],
) -> list[dict[str, Any]]:
    remote_result = _run_git(repo_root, "for-each-ref", "refs/remotes/origin", "--format=%(refname)|%(refname:short)|%(objectname:short)")
    if remote_result.returncode != 0:
        raise RuntimeError(remote_result.stderr.strip() or "cannot list remote branches")
    remote_branches: list[dict[str, Any]] = []
    for line in remote_result.stdout.splitlines():
        if not line.strip():
            continue
        full_ref, remote_ref, head = (line.split("|", 2) + ["", ""])[:3]
        if full_ref == "refs/remotes/origin/HEAD" or remote_ref in {"origin", "origin/HEAD"}:
            continue
        branch = remote_ref.removeprefix("origin/")
        local_exists = branch in local_branches
        ancestry = _run_git(repo_root, "merge-base", "--is-ancestor", remote_ref, base_ref).returncode == 0
        prs = prs_by_branch.get(branch, [])
        cleanup_class, reason = _remote_cleanup_class(branch, local_exists, prs, ancestry)
        branch_state = _combine_state_maps(workflow_state, worker_state).get(branch, {})
        triage = classify_dirty_triage(
            branch,
            catalog,
            cleanup_class=cleanup_class,
            prs=prs,
            branch_state=branch_state,
            remote_branch=True,
            safe_candidate=cleanup_class in safe_remote_classes,
        )
        eligible = cleanup_class in safe_remote_classes and triage["auto_delete_allowed"] is True
        remote_branches.append({
            "branch": branch,
            "remote_ref": remote_ref,
            "head": head,
            "local_branch_exists": local_exists,
            "merged_into_base_by_ancestry": ancestry,
            "github_pr_numbers": [pr.get("number") for pr in prs if isinstance(pr.get("number"), int)],
            "github_pr_states": sorted({str(pr.get("state")) for pr in prs if isinstance(pr.get("state"), str)}),
            "cleanup_class": cleanup_class,
            "remote_delete_eligible": eligible,
            "delete_blocked_reason": "" if eligible else (reason or ",".join(triage["dirty_triage_proofs"])),
            **{key: value for key, value in triage.items() if key != "branch"},
        })
    return remote_branches


def inspect_branch_inventory(
    repo: Path,
    catalog: dict[str, Any],
    *,
    base_ref: str = "origin/main",
    github_prs_json: Path | None = None,
    workflow_state_json: Path | None = None,
    worker_state_json: list[Path] | None = None,
) -> dict[str, Any]:
    """Classify local branches without mutating local or remote Git state."""
    top_result = _run_git(repo, "rev-parse", "--show-toplevel")
    if top_result.returncode != 0:
        raise RuntimeError(top_result.stderr.strip() or "not a git repository")
    repo_root = Path(top_result.stdout.strip())
    branch_result = _run_git(repo_root, "for-each-ref", "refs/heads", "--format=%(refname:short)|%(objectname:short)|%(upstream:short)")
    if branch_result.returncode != 0:
        raise RuntimeError(branch_result.stderr.strip() or "cannot list local branches")
    worktree_result = _run_git(repo_root, "worktree", "list", "--porcelain")
    worktrees = _parse_worktree_branches(worktree_result.stdout if worktree_result.returncode == 0 else "")
    prs_by_branch = _load_github_prs(github_prs_json)
    workflow_state = _load_workflow_state(workflow_state_json)
    worker_state = _load_worker_state_files(worker_state_json)
    combined_state = _combine_state_maps(workflow_state, worker_state)
    branch_policy = catalog.get("branch_cleanup_policy", {}) if isinstance(catalog.get("branch_cleanup_policy"), dict) else {}
    backup_prefixes = [str(x) for x in branch_policy.get("backup_dirty_prefixes", []) if isinstance(x, str)]
    safe_classes = set(str(x) for x in branch_policy.get("safe_local_delete_classes", []) if isinstance(x, str))
    safe_remote_classes = set(str(x) for x in branch_policy.get("safe_remote_delete_classes", []) if isinstance(x, str))
    branches: list[dict[str, Any]] = []
    local_branch_names: set[str] = set()
    for line in branch_result.stdout.splitlines():
        if not line.strip():
            continue
        branch, head, upstream = (line.split("|", 2) + ["", ""])[:3]
        local_branch_names.add(branch)
        worktree_path = worktrees.get(branch, "")
        ancestry = _run_git(repo_root, "merge-base", "--is-ancestor", branch, base_ref).returncode == 0
        remote_exists = _run_git(repo_root, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}").returncode == 0
        prs = prs_by_branch.get(branch, [])
        cleanup_class, reason = _cleanup_class(branch, worktree_path, backup_prefixes, prs, ancestry, remote_exists)
        branch_state = _workflow_state_for_branch(combined_state, branch)
        triage = classify_dirty_triage(
            branch,
            catalog,
            cleanup_class=cleanup_class,
            prs=prs,
            branch_state=branch_state,
            worktree_attached=bool(worktree_path),
            safe_candidate=cleanup_class in safe_classes,
        )
        eligible = cleanup_class in safe_classes and triage["auto_delete_allowed"] is True
        branches.append({
            "branch": branch,
            "head": head,
            "upstream": upstream,
            "remote_exists": remote_exists,
            "worktree_attached": bool(worktree_path),
            "worktree_path": worktree_path,
            "merged_into_base_by_ancestry": ancestry,
            "github_pr_numbers": [pr.get("number") for pr in prs if isinstance(pr.get("number"), int)],
            "github_pr_states": sorted({str(pr.get("state")) for pr in prs if isinstance(pr.get("state"), str)}),
            "creation_hint": _branch_creation_hint(repo_root, branch),
            "cleanup_class": cleanup_class,
            "local_delete_eligible": eligible,
            "delete_blocked_reason": "" if eligible else (reason or ",".join(triage["dirty_triage_proofs"])),
            **{key: value for key, value in triage.items() if key != "branch"},
        })
    remote_branches = _inspect_remote_branches(
        repo_root,
        catalog,
        base_ref=base_ref,
        prs_by_branch=prs_by_branch,
        workflow_state=workflow_state,
        worker_state=worker_state,
        local_branches=local_branch_names,
        safe_remote_classes=safe_remote_classes,
    )
    return {
        "schema": BRANCH_INVENTORY_SCHEMA,
        "repo_root": str(repo_root),
        "base_ref": base_ref,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branch_count": len(branches),
        "remote_branch_count": len(remote_branches),
        "read_only": True,
        "remote_delete_requires_operator_request": branch_policy.get("remote_delete_requires_explicit_operator_request") is True,
        "mutating_cleanup_commands_require_operator_request": branch_policy.get("mutating_cleanup_commands_require_operator_request") is True,
        "branches": branches,
        "remote_branches": remote_branches,
    }


def inspect_branch_closeout_gate(
    repo: Path,
    catalog: dict[str, Any],
    *,
    base_ref: str = "origin/main",
    github_prs_json: Path | None = None,
    workflow_state_json: Path | None = None,
    worker_state_json: list[Path] | None = None,
) -> dict[str, Any]:
    """Build a read-only post-merge branch closeout gate packet."""
    inventory = inspect_branch_inventory(
        repo,
        catalog,
        base_ref=base_ref,
        github_prs_json=github_prs_json,
        workflow_state_json=workflow_state_json,
        worker_state_json=worker_state_json,
    )
    local_candidates = [
        item
        for item in inventory["branches"]
        if item.get("local_delete_eligible") is True
    ]
    remote_candidates = [
        item
        for item in inventory["remote_branches"]
        if item.get("remote_delete_eligible") is True
    ]
    merged_worktree_branches = [
        item
        for item in inventory["branches"]
        if item.get("cleanup_class") == "worktree_attached"
        and "MERGED" in item.get("github_pr_states", [])
    ]
    status = "BRANCH_CLOSEOUT_READY"
    if local_candidates or remote_candidates or merged_worktree_branches:
        status = "BRANCH_CLOSEOUT_REQUIRED"
    return {
        "schema": BRANCH_CLOSEOUT_SCHEMA,
        "repo_root": inventory["repo_root"],
        "base_ref": inventory["base_ref"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "read_only": True,
        "cleanup_commands_require_operator_request": inventory["mutating_cleanup_commands_require_operator_request"],
        "remote_delete_requires_operator_request": inventory["remote_delete_requires_operator_request"],
        "local_delete_eligible_count": len(local_candidates),
        "remote_delete_eligible_count": len(remote_candidates),
        "merged_worktree_attached_count": len(merged_worktree_branches),
        "local_delete_eligible_branches": [
            {
                "branch": item["branch"],
                "cleanup_class": item["cleanup_class"],
                "github_pr_numbers": item["github_pr_numbers"],
                "github_pr_states": item["github_pr_states"],
                "worktree_path": item["worktree_path"],
            }
            for item in local_candidates
        ],
        "remote_delete_eligible_branches": [
            {
                "branch": item["branch"],
                "cleanup_class": item["cleanup_class"],
                "github_pr_numbers": item["github_pr_numbers"],
                "github_pr_states": item["github_pr_states"],
                "remote_ref": item["remote_ref"],
            }
            for item in remote_candidates
        ],
        "merged_worktree_attached_branches": [
            {
                "branch": item["branch"],
                "cleanup_class": item["cleanup_class"],
                "github_pr_numbers": item["github_pr_numbers"],
                "github_pr_states": item["github_pr_states"],
                "worktree_path": item["worktree_path"],
            }
            for item in merged_worktree_branches
        ],
    }


def inspect_repo(
    repo: Path,
    catalog: dict[str, Any],
    *,
    require_changes: bool = False,
    allowed_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect a Git repository without mutating it."""
    top_result = _run_git(repo, "rev-parse", "--show-toplevel")
    if top_result.returncode != 0:
        raise RuntimeError(top_result.stderr.strip() or "not a git repository")
    repo_root = Path(top_result.stdout.strip())

    branch_result = _run_git(repo_root, "branch", "--show-current")
    head_result = _run_git(repo_root, "rev-parse", "--short", "HEAD")
    status_result = _run_git(repo_root, "status", "--short", "--branch", "--untracked-files=all")
    diff_check = _run_git(repo_root, "diff", "--check")
    cached_diff_check = _run_git(repo_root, "diff", "--cached", "--check")
    worker_identity = inspect_worker_git_identity(repo_root, catalog)

    if status_result.returncode != 0:
        raise RuntimeError(status_result.stderr.strip() or "git status failed")

    changed_paths = _parse_changed_paths(status_result.stdout)
    allowed_changed_paths = [_normalize_repo_path(path) for path in (allowed_paths or []) if path.strip()]
    disallowed_changed_paths = [
        item["path"]
        for item in changed_paths
        if allowed_changed_paths and not _path_matches_allowed(item["path"], allowed_changed_paths)
    ]
    path_safety = catalog.get("path_safety", {}) if isinstance(catalog.get("path_safety"), dict) else {}
    secret_fragments = path_safety.get("secret_path_fragments_block_commit", [])
    log_fragments = path_safety.get("raw_log_fragments_require_operator_review", [])
    if not isinstance(secret_fragments, list):
        secret_fragments = []
    if not isinstance(log_fragments, list):
        log_fragments = []

    exception_roots = path_safety.get("secret_path_exception_roots", [])
    if not isinstance(exception_roots, list):
        exception_roots = []
    secret_like_paths = [
        item["path"]
        for item in changed_paths
        if _contains_fragment(item["path"], secret_fragments)
        and not _matches_exception_root(item["path"], exception_roots)
    ]
    log_like_paths = [item["path"] for item in changed_paths if _contains_fragment(item["path"], log_fragments)]

    staged_dirty = any(item["status"][0] not in (" ", "?") for item in changed_paths)
    unstaged_dirty = any(item["status"][1] != " " or item["status"] == "??" for item in changed_paths)
    untracked_count = sum(1 for item in changed_paths if item["status"] == "??")
    worktree_dirty = bool(changed_paths)
    diff_passed = diff_check.returncode == 0
    cached_diff_passed = cached_diff_check.returncode == 0

    status = "GIT_DISCIPLINE_READY"
    operator_review_required = False
    if not diff_passed or not cached_diff_passed:
        status = "GIT_DISCIPLINE_BLOCKED"
    elif not worker_identity["worker_git_identity_configured"]:
        status = "GIT_DISCIPLINE_BLOCKED"
    elif disallowed_changed_paths:
        status = "DIRTY_WORKTREE_BLOCKER"
    elif secret_like_paths or log_like_paths:
        status = "GIT_DISCIPLINE_REQUIRES_OPERATOR_REVIEW"
        operator_review_required = True
    elif require_changes and not worktree_dirty:
        status = "GIT_DISCIPLINE_NO_CHANGES"

    return {
        "schema": INSPECTION_SCHEMA,
        "repo_root": str(repo_root),
        "branch": branch_result.stdout.strip() if branch_result.returncode == 0 else "",
        "head": head_result.stdout.strip() if head_result.returncode == 0 else "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "worktree_dirty": worktree_dirty,
        "staged_dirty": staged_dirty,
        "unstaged_dirty": unstaged_dirty,
        "untracked_count": untracked_count,
        "diff_check_passed": diff_passed,
        "cached_diff_check_passed": cached_diff_passed,
        "operator_review_required": operator_review_required,
        "push_allowed": False,
        "commit_allowed_after_validation": status == "GIT_DISCIPLINE_READY",
        "worker_git_identity_configured": worker_identity["worker_git_identity_configured"],
        "worker_git_identity_label": worker_identity["worker_git_identity_label"],
        "changed_paths": changed_paths,
        "allowed_changed_paths": allowed_changed_paths,
        "disallowed_changed_paths": disallowed_changed_paths,
        "secret_like_paths": secret_like_paths,
        "raw_log_like_paths": log_like_paths,
        "diff_check_output": (diff_check.stdout + diff_check.stderr).strip(),
        "cached_diff_check_output": (cached_diff_check.stdout + cached_diff_check.stderr).strip(),
    }


def _is_full_object_id(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value)


def parse_gitlink_proof(value: str) -> dict[str, str]:
    """Parse one gitlink proof argument without reading repository content."""

    parts = value.split(":")
    if len(parts) != 4:
        raise ValueError("gitlink proof must use <path>:<old-object>:<target-object>:<source-pr-merge-commit>")
    path, old_object, target_object, source_pr_merge_commit = (part.strip() for part in parts)
    if not path:
        raise ValueError("gitlink proof path is required")
    return {
        "path": _normalize_repo_path(path),
        "old_object": old_object,
        "target_object": target_object,
        "source_pr_merge_commit": source_pr_merge_commit,
    }


def inspect_closeout_preflight(
    repo: Path,
    catalog: dict[str, Any],
    *,
    allowed_paths: list[str],
    expected_branch: str = "",
    expected_branch_prefix: str = "",
    gitlink_proofs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Inspect a ledger or gitlink closeout before commit, push, or merge."""

    inspection = inspect_repo(repo, catalog, allowed_paths=allowed_paths)
    block_reasons: list[str] = []
    gitlink_proofs = gitlink_proofs or []
    allowed_changed_paths = inspection["allowed_changed_paths"]
    repo_root = Path(inspection["repo_root"])
    changed_gitlink_paths = [
        item["path"]
        for item in inspection["changed_paths"]
        if _path_matches_allowed(item["path"], allowed_changed_paths)
        and _is_gitlink_path(repo_root, item["path"])
    ]
    gitlink_objects = {
        path: {
            "old_object": _gitlink_head_object(repo_root, path),
            "target_object": _gitlink_index_object(repo_root, path),
        }
        for path in changed_gitlink_paths
    }
    proof_paths = {proof.get("path", "") for proof in gitlink_proofs}

    if not allowed_changed_paths:
        block_reasons.append("allowed_paths_required")
    if not expected_branch and not expected_branch_prefix:
        block_reasons.append("expected_branch_or_prefix_required")

    branch = inspection["branch"]
    if expected_branch and branch != expected_branch:
        block_reasons.append("current_branch_mismatch")
    if expected_branch_prefix and not branch.startswith(expected_branch_prefix):
        block_reasons.append("current_branch_prefix_mismatch")
    if inspection["status"] != "GIT_DISCIPLINE_READY":
        block_reasons.append(f"repo_inspection_status:{inspection['status']}")
    for path in changed_gitlink_paths:
        if path not in proof_paths:
            block_reasons.append(f"gitlink_proof_required:{path}")

    for proof in gitlink_proofs:
        path = proof.get("path", "")
        if not any(_path_matches_allowed(path, [allowed_path]) for allowed_path in allowed_changed_paths):
            block_reasons.append(f"gitlink_proof_path_not_allowed:{path}")
        if path not in changed_gitlink_paths:
            block_reasons.append(f"gitlink_proof_path_not_changed_gitlink:{path}")
        for field in ("old_object", "target_object", "source_pr_merge_commit"):
            value = proof.get(field, "")
            if not isinstance(value, str) or not _is_full_object_id(value):
                block_reasons.append(f"gitlink_proof_{field}_must_be_full_object:{path}")
        if proof.get("old_object") == proof.get("target_object"):
            block_reasons.append(f"gitlink_proof_target_must_change:{path}")
        objects = gitlink_objects.get(path)
        if objects:
            if proof.get("old_object") != objects["old_object"]:
                block_reasons.append(f"gitlink_proof_old_object_mismatch:{path}")
            if proof.get("target_object") != objects["target_object"]:
                block_reasons.append(f"gitlink_proof_target_object_mismatch:{path}")

    if inspection["status"] == "DIRTY_WORKTREE_BLOCKER":
        status = "DIRTY_WORKTREE_BLOCKER"
    elif block_reasons:
        status = "CLOSEOUT_PREFLIGHT_BLOCKED"
    else:
        status = "CLOSEOUT_PREFLIGHT_PASS"

    return {
        "schema": CLOSEOUT_PREFLIGHT_SCHEMA,
        "repo_root": inspection["repo_root"],
        "branch": branch,
        "head": inspection["head"],
        "status": status,
        "closeout_allowed": status == "CLOSEOUT_PREFLIGHT_PASS",
        "commit_allowed_after_validation": status == "CLOSEOUT_PREFLIGHT_PASS",
        "allowed_changed_paths": allowed_changed_paths,
        "disallowed_changed_paths": inspection["disallowed_changed_paths"],
        "changed_paths": inspection["changed_paths"],
        "changed_gitlink_paths": changed_gitlink_paths,
        "gitlink_objects": gitlink_objects,
        "expected_branch": expected_branch,
        "expected_branch_prefix": expected_branch_prefix,
        "gitlink_proofs": gitlink_proofs,
        "block_reasons": block_reasons,
        "inspection_status": inspection["status"],
        "read_only": True,
    }


def cmd_validate(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    role_catalog = load_json(args.role_catalog) if args.role_catalog else None
    errors = validate_catalog(catalog, role_catalog=role_catalog)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"git discipline catalog ok: {args.catalog}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_repo(
        args.repo.resolve(),
        catalog,
        require_changes=args.require_changes,
        allowed_paths=args.allowed_path,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"status: {packet['status']}")
        print(f"repo_root: {packet['repo_root']}")
        print(f"branch: {packet['branch']}")
        print(f"head: {packet['head']}")
        print(f"worktree_dirty: {packet['worktree_dirty']}")
        print(f"diff_check_passed: {packet['diff_check_passed']}")
        print(f"cached_diff_check_passed: {packet['cached_diff_check_passed']}")
        print(f"worker_git_identity_configured: {packet['worker_git_identity_configured']}")
        print(f"worker_git_identity_label: {packet['worker_git_identity_label']}")
        print(f"changed_paths: {len(packet['changed_paths'])}")
        print(f"disallowed_changed_paths: {len(packet['disallowed_changed_paths'])}")
    return 0 if packet["status"] in {"GIT_DISCIPLINE_READY", "GIT_DISCIPLINE_NO_CHANGES"} else 1


def cmd_closeout_preflight(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    try:
        gitlink_proofs = [parse_gitlink_proof(item) for item in args.gitlink_proof]
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    packet = inspect_closeout_preflight(
        args.repo.resolve(),
        catalog,
        allowed_paths=args.allowed_path,
        expected_branch=args.expected_branch,
        expected_branch_prefix=args.expected_branch_prefix,
        gitlink_proofs=gitlink_proofs,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"repo_root: {packet['repo_root']}")
        print(f"branch: {packet['branch']}")
        print(f"head: {packet['head']}")
        print(f"status: {packet['status']}")
        print(f"closeout_allowed: {packet['closeout_allowed']}")
        print(f"disallowed_changed_paths: {len(packet['disallowed_changed_paths'])}")
        print(f"gitlink_proofs: {len(packet['gitlink_proofs'])}")
    return 0 if packet["status"] == "CLOSEOUT_PREFLIGHT_PASS" else 1


def cmd_plugin_worktree_preflight(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_plugin_worktree_preflight(
        args.repo.resolve(),
        catalog,
        cwd=args.cwd.resolve() if args.cwd else None,
        approved_isolated_worktree=args.approved_isolated_worktree,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"status: {packet['status']}")
        print(f"canonical_root: {packet['canonical_root']}")
        print(f"cwd: {packet['cwd']}")
        print(f"actual_toplevel: {packet['actual_toplevel']}")
        print(f"block_reasons: {','.join(packet['block_reasons'])}")
    return 0 if packet["status"] == "PLUGIN_WORKTREE_PASS" else 1


def cmd_branch_inventory(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_branch_inventory(
        args.repo.resolve(),
        catalog,
        base_ref=args.base,
        github_prs_json=args.github_prs_json,
        workflow_state_json=args.workflow_state_json,
        worker_state_json=args.worker_state_json,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"repo_root: {packet['repo_root']}")
        print(f"base_ref: {packet['base_ref']}")
        print(f"branch_count: {packet['branch_count']}")
        print(f"remote_branch_count: {packet['remote_branch_count']}")
        for item in packet["branches"]:
            print(f"{item['cleanup_class']}: {item['branch']} prs={item['github_pr_numbers']} ancestry={item['merged_into_base_by_ancestry']}")
    return 0


def cmd_branch_closeout_gate(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_branch_closeout_gate(
        args.repo.resolve(),
        catalog,
        base_ref=args.base,
        github_prs_json=args.github_prs_json,
        workflow_state_json=args.workflow_state_json,
        worker_state_json=args.worker_state_json,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"repo_root: {packet['repo_root']}")
        print(f"base_ref: {packet['base_ref']}")
        print(f"status: {packet['status']}")
        print(f"local_delete_eligible_count: {packet['local_delete_eligible_count']}")
        print(f"remote_delete_eligible_count: {packet['remote_delete_eligible_count']}")
        print(f"merged_worktree_attached_count: {packet['merged_worktree_attached_count']}")
    return 0 if packet["status"] == "BRANCH_CLOSEOUT_READY" else 1

def cmd_gitlink_audit(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_gitlink_target(
        args.repo.resolve(),
        tree_ref=args.tree_ref,
        gitlink_path=args.path,
        expected_target=args.expected_target or "",
        local_checkout=args.local_checkout,
        claim_source=args.claim_source,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"repo_root: {packet['repo_root']}")
        print(f"tree_ref: {packet['tree_ref']}")
        print(f"gitlink_path: {packet['gitlink_path']}")
        print(f"parent_gitlink_target: {packet['parent_gitlink_target']}")
        print(f"local_checkout_head: {packet['local_checkout_head']}")
        print(f"local_checkout_status: {packet['local_checkout_status']}")
        print(f"claim_source: {packet['claim_source']}")
        print(f"claim_object_used: {packet['claim_object_used']}")
        print(f"status: {packet['status']}")
    return 0 if packet["status"] == "GITLINK_AUDIT_PASS" else 1


def cmd_branch_prefix_check(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_branch_prefix(
        args.branch,
        default_prefix=args.default_prefix,
        assignment_packet=args.assignment_packet,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"branch: {packet['branch']}")
        print(f"default_prefix: {packet['default_prefix']}")
        print(f"override_prefix: {packet['override_prefix']}")
        print(f"branch_prefix_check: {packet['branch_prefix_check']}")
        print(f"status: {packet['status']}")
    return 0 if packet["status"] == "BRANCH_PREFIX_PASS" else 1


def cmd_branch_base_preflight(args: argparse.Namespace) -> int:
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog, role_catalog=None)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    packet = inspect_branch_base_preflight(
        args.repo.resolve(),
        catalog,
        intended_base=args.intended_base,
        expected_branch=args.expected_branch,
        expected_branch_prefix=args.expected_branch_prefix,
        allowed_path=args.allowed_path,
        allow_assigned_changes=args.allow_assigned_changes,
        github_prs_json=args.github_prs_json,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"repo_root: {packet['repo_root']}")
        print(f"branch: {packet['branch']}")
        print(f"intended_base_sha: {packet['intended_base_sha']}")
        print(f"status: {packet['status']}")
        print(f"block_reasons: {','.join(packet['block_reasons'])}")
    return 0 if packet["status"] == "BRANCH_BASE_PREFLIGHT_PASS" else 1


def cmd_clean_worktree_target(args: argparse.Namespace) -> int:
    packet = map_clean_worktree_target(
        canonical_root=args.canonical_root,
        worktree_root=args.worktree_root,
        worktree_target=args.worktree_target,
        canonical_target=args.canonical_target,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"canonical_target: {packet['canonical_target']}")
        print(f"status: {packet['status']}")
        print(f"reasons: {','.join(packet['reasons'])}")
    return 0 if packet["status"] == "CLEAN_WORKTREE_TARGET_PASS" else 1


def cmd_ignored_staging_check(args: argparse.Namespace) -> int:
    command = args.command
    if args.command_file is not None:
        command = args.command_file.read_text(encoding="utf-8")
    packet = evaluate_ignored_staging_command(
        command,
        explicit_allowed_paths=args.allowed_path,
        operator_approval=args.operator_approval,
        owning_contract=args.owning_contract,
    )
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"schema: {packet['schema']}")
        print(f"force_add_detected: {packet['force_add_detected']}")
        print(f"blocked_paths: {','.join(packet['blocked_paths'])}")
        print(f"status: {packet['status']}")
        print(f"reasons: {','.join(packet['reasons'])}")
    return 0 if packet["status"] == "IGNORED_STAGING_PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--role-catalog", type=Path, default=DEFAULT_ROLE_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.set_defaults(func=cmd_validate)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--repo", type=Path, default=PLUGIN_ROOT)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.add_argument("--require-changes", action="store_true")
    inspect_parser.add_argument("--allowed-path", action="append", default=[])
    inspect_parser.set_defaults(func=cmd_inspect)

    closeout_preflight_parser = subparsers.add_parser("closeout-preflight")
    closeout_preflight_parser.add_argument("--repo", type=Path, default=PLUGIN_ROOT)
    closeout_preflight_parser.add_argument("--json", action="store_true")
    closeout_preflight_parser.add_argument("--allowed-path", action="append", default=[])
    closeout_preflight_parser.add_argument("--expected-branch", default="")
    closeout_preflight_parser.add_argument("--expected-branch-prefix", default="")
    closeout_preflight_parser.add_argument("--gitlink-proof", action="append", default=[])
    closeout_preflight_parser.set_defaults(func=cmd_closeout_preflight)

    plugin_worktree_parser = subparsers.add_parser("plugin-worktree-preflight")
    plugin_worktree_parser.add_argument("--repo", type=Path, default=PLUGIN_ROOT)
    plugin_worktree_parser.add_argument("--cwd", type=Path)
    plugin_worktree_parser.add_argument("--approved-isolated-worktree", action="store_true")
    plugin_worktree_parser.add_argument("--json", action="store_true")
    plugin_worktree_parser.set_defaults(func=cmd_plugin_worktree_preflight)

    inventory_parser = subparsers.add_parser("branch-inventory")
    inventory_parser.add_argument("--repo", type=Path, default=PLUGIN_ROOT)
    inventory_parser.add_argument("--base", default="origin/main")
    inventory_parser.add_argument("--github-prs-json", type=Path)
    inventory_parser.add_argument("--workflow-state-json", type=Path)
    inventory_parser.add_argument("--worker-state-json", type=Path, action="append", default=[])
    inventory_parser.add_argument("--json", action="store_true")
    inventory_parser.set_defaults(func=cmd_branch_inventory)

    closeout_parser = subparsers.add_parser("branch-closeout-gate")
    closeout_parser.add_argument("--repo", type=Path, default=PLUGIN_ROOT)
    closeout_parser.add_argument("--base", default="origin/main")
    closeout_parser.add_argument("--github-prs-json", type=Path)
    closeout_parser.add_argument("--workflow-state-json", type=Path)
    closeout_parser.add_argument("--worker-state-json", type=Path, action="append", default=[])
    closeout_parser.add_argument("--json", action="store_true")
    closeout_parser.set_defaults(func=cmd_branch_closeout_gate)

    gitlink_parser = subparsers.add_parser("gitlink-audit")
    gitlink_parser.add_argument("--repo", type=Path, required=True)
    gitlink_parser.add_argument("--tree-ref", default="origin/main")
    gitlink_parser.add_argument("--path", required=True)
    gitlink_parser.add_argument("--expected-target", default="")
    gitlink_parser.add_argument("--local-checkout", type=Path)
    gitlink_parser.add_argument("--claim-source", choices=("parent-gitlink", "local-checkout"), default="parent-gitlink")
    gitlink_parser.add_argument("--json", action="store_true")
    gitlink_parser.set_defaults(func=cmd_gitlink_audit)

    prefix_parser = subparsers.add_parser("branch-prefix-check")
    prefix_parser.add_argument("--branch", required=True)
    prefix_parser.add_argument("--default-prefix", default="codex/")
    prefix_parser.add_argument("--assignment-packet", type=Path)
    prefix_parser.add_argument("--json", action="store_true")
    prefix_parser.set_defaults(func=cmd_branch_prefix_check)

    branch_base_parser = subparsers.add_parser("branch-base-preflight")
    branch_base_parser.add_argument("--repo", type=Path, default=PLUGIN_ROOT)
    branch_base_parser.add_argument("--intended-base", default="origin/main")
    branch_base_parser.add_argument("--expected-branch", default="")
    branch_base_parser.add_argument("--expected-branch-prefix", default="")
    branch_base_parser.add_argument("--allowed-path", action="append", default=[])
    branch_base_parser.add_argument("--allow-assigned-changes", action="store_true")
    branch_base_parser.add_argument("--github-prs-json", type=Path)
    branch_base_parser.add_argument("--json", action="store_true")
    branch_base_parser.set_defaults(func=cmd_branch_base_preflight)

    clean_target_parser = subparsers.add_parser("clean-worktree-target")
    clean_target_parser.add_argument("--canonical-root", required=True)
    clean_target_parser.add_argument("--worktree-root", required=True)
    clean_target_parser.add_argument("--worktree-target", required=True)
    clean_target_parser.add_argument("--canonical-target", default="")
    clean_target_parser.add_argument("--json", action="store_true")
    clean_target_parser.set_defaults(func=cmd_clean_worktree_target)

    ignored_staging_parser = subparsers.add_parser("ignored-staging-check")
    ignored_staging_parser.add_argument("--command", default="")
    ignored_staging_parser.add_argument("--command-file", type=Path)
    ignored_staging_parser.add_argument("--allowed-path", action="append", default=[])
    ignored_staging_parser.add_argument("--operator-approval", action="store_true")
    ignored_staging_parser.add_argument("--owning-contract", default="")
    ignored_staging_parser.add_argument("--json", action="store_true")
    ignored_staging_parser.set_defaults(func=cmd_ignored_staging_check)
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
