#!/usr/bin/env python3
"""Validate, route, and audit Bears plugin-owned platform roles."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
DEFAULT_EVIDENCE_PATHS = [
    "/srv/bears/AGENTS.md",
    "/srv/bears/plugins/bears/AGENTS.md",
    str(DEFAULT_CATALOG),
]
BLOCKER_REASONS = {
    "unknown",
    "unmapped",
    "parent_only",
    "missing_role",
    "invalid_broad_role",
    "ambiguous_owner",
}
ROLE_KINDS = {"specialist", "reviewer", "orchestrator", "helper"}
PRIMARY_ROLE_KINDS = {"specialist", "helper"}
EXECUTION_CLASSES = {"helper", "specialist"}
HELPER_PROFILE_MARKERS = {
    "controller",
    "evaluator",
    "gate",
    "governor",
    "helper",
    "orchestrator",
    "reviewer",
    "router",
    "validator",
}
PART_KINDS = {"concrete", "group"}
REVIEWER_ALLOWED_WRITE_ZONES = {"no_write_authority"}
REVIEWER_REQUIRED_FORBIDDEN_ACTIONS = {
    "file_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_mutation",
    "runtime_mutation",
    "deployment_mutation",
    "credential_access",
    "raw_log_read",
    "raw_chat_read",
    "raw_vpn_config_read",
    "production_data_read",
}
REQUIRED_ROLE_FIELDS = {
    "name",
    "agent_file",
    "scope",
    "model",
    "sandbox_mode",
    "developer_instructions_profile",
    "allowed_write_zones",
    "forbidden_actions",
    "evidence_required",
    "handoff_contract",
    "role_kind",
    "execution_class",
    "primary_eligible",
}
REQUIRED_AGENT_PROFILE_MAPPING_FIELDS = {
    "profile_name",
    "agent_file",
    "execution_class",
    "mapped_role",
    "concrete_part",
    "coverage_kind",
}
REQUIRED_PART_FIELDS = {
    "name",
    "aliases",
    "group",
    "required_role",
    "role_required",
    "no_role_policy",
    "source",
    "part_kind",
    "write_roots",
    "concrete_scope",
    "allowed_write_boundary",
    "trust_boundary",
    "required_validations",
    "supporting_roles",
    "reviewer_triggers",
    "decomposition_required",
}
REQUIRED_AGENT_TOML_FIELDS = {
    "name",
    "description",
    "developer_instructions",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
}
REQUIRED_AGENT_TOML_CLASSIFICATION_FIELDS = {
    "role_kind",
    "execution_class",
    "primary_eligible",
}
MANDATORY_POLICY_REQUIRED_FIELDS = {
    "missing_role_status",
    "role_required_for",
    "no_role_policy",
    "unknown_child_policy",
    "main_invariant",
    "one_primary_role_required",
    "parent_group_coverage_allowed",
    "broad_fallback_matching_allowed",
    "parent_only_targets",
    "root_planning_drift_targets",
    "product_apps_monorepo_policy",
    "blocked_edits",
    "allowed_next_actions",
    "role_development",
    "blocker_reasons",
    "independent_control_audit",
    "definitions",
    "selection_rules",
}
PRODUCT_APPS_MONOREPO_POLICY_REQUIRED_FIELDS = {
    "canonical_local_root",
    "canonical_remote",
    "canonical_remote_urls",
    "invalid_canonical_targets",
    "nested_repo_policy",
    "allowed_nested_statuses",
    "required_legacy_fields",
    "issue_link_invariant",
}
ROLE_DEVELOPMENT_REQUIRED_FIELDS = {
    "lane",
    "owner_role",
    "max_attempts",
    "allowed_write_scope",
    "required_validations",
    "rerun_commands",
    "terminal_blocker_conditions",
    "unsafe_implementation_policy",
}
ROLE_DEVELOPMENT_LANE = "role-development"
ROLE_DEVELOPMENT_OWNER_ROLE = "bears-platform-role-governor"
ROLE_DEVELOPMENT_REQUIRED_VALIDATIONS = [
    "python3 scripts/platform_roles.py validate",
    "python3 scripts/role_gate_methodology.py validate",
    "python3 -m unittest tests/test_platform_roles.py tests/test_role_gate_methodology.py",
]
ROLE_DEVELOPMENT_RERUN_COMMANDS = [
    "python3 scripts/platform_roles.py route <target>",
    "python3 scripts/platform_roles.py audit <target>",
    "python3 scripts/platform_roles.py role-development-plan <target> --json",
]
ROLE_DEVELOPMENT_TERMINAL_BLOCKER_CONDITIONS = [
    "role_development_attempts_exhausted",
    "owner_conflict",
    "validated_exact_role_not_produced",
]
ROLE_DEVELOPMENT_UNSAFE_IMPLEMENTATION_POLICY = (
    "route/audit remain nonzero and implementation_handoff_allowed=false until one exact "
    "primary specialist or helper role validates at the requested write granularity."
)
VALIDATION_EXECUTION_POLICY = (
    "Only platform_roles.py route/audit gates are agent-local. Other required checks are "
    "CI/local-commit-owned automation and must not become ad-hoc manual gates."
)
AUTH_GATEWAY_DEPLOY_CORE_PARTS = {
    "auth_core": "/srv/bears/dev/platform/src/bears_platform/auth",
    "bears_gateway": "/srv/bears/dev/platform/src/bears_platform/gateway",
    "cd_deploy_stage": "/srv/bears/dev/platform/src/bears_platform/deploy",
}
SELLER_LEGACY_ROOTS = (
    "/srv/bears/legacy/seller/apps/",
    "/srv/bears/projects/seller/apps/",
)
DEFAULT_ROOT_PLANNING_DRIFT_TARGETS = (
    "/srv/bears/.specify",
    "/srv/bears/specs",
    "/srv/bears/plans.md",
    "/srv/bears/roadmap.md",
    "/srv/bears/docs/plans.md",
)


def normalize(value: str) -> str:
    return value.casefold().replace("\\", "/").strip().strip("/")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("catalog root must be an object")
    return data


def load_cli_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}")
    return load_json(path)


def load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _require_non_empty_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{path} must be a non-empty list")


def _is_path_like(target: str) -> bool:
    return "/" in target or target.startswith(".")


def _evidence_item_exists(item: str, *, plugin_root: Path = PLUGIN_ROOT) -> bool:
    if "://" in item:
        return True
    if not _is_path_like(item):
        return True
    candidate = Path(item)
    if candidate.is_absolute():
        return candidate.exists()
    return (plugin_root / candidate).exists()


def _part_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        part["name"]: part
        for part in catalog.get("platform_parts", [])
        if isinstance(part, dict) and isinstance(part.get("name"), str)
    }


def _role_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        role["name"]: role
        for role in catalog.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }


def _role_execution_class(role: dict[str, Any] | None) -> str | None:
    if not role:
        return None
    execution_class = role.get("execution_class")
    return execution_class if isinstance(execution_class, str) else None


def _helper_marker_present(*values: str) -> bool:
    for value in values:
        normalized_value = normalize(value).replace("_", "-")
        tokens = {token for token in normalized_value.split("-") if token}
        if tokens & HELPER_PROFILE_MARKERS:
            return True
    return False


def _agent_profile_mappings(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    mappings = catalog.get("agent_profile_mappings", [])
    return mappings if isinstance(mappings, list) else []


def _expected_profile_role_kind(coverage_kind: str | None) -> str | None:
    if coverage_kind == "domain_orchestrator_profile":
        return "orchestrator"
    if coverage_kind == "workflow_helper_profile":
        return "helper"
    return None


def _expected_profile_primary_eligible(coverage_kind: str | None) -> bool | None:
    if coverage_kind == "domain_orchestrator_profile":
        return False
    if coverage_kind == "workflow_helper_profile":
        return True
    return None


def _validate_agent_toml_classification(
    *,
    errors: list[str],
    agent_file: str,
    agent: dict[str, Any],
    expected_role_kind: str | None,
    expected_execution_class: str | None,
    expected_primary_eligible: bool | None,
) -> None:
    missing = REQUIRED_AGENT_TOML_CLASSIFICATION_FIELDS - agent.keys()
    if missing:
        errors.append(f"{agent_file}: missing role classification fields: {sorted(missing)}")
        return
    if expected_role_kind is not None and agent.get("role_kind") != expected_role_kind:
        errors.append(
            f"{agent_file}: role_kind {agent.get('role_kind')!r} must match expected {expected_role_kind!r}"
        )
    if expected_execution_class is not None and agent.get("execution_class") != expected_execution_class:
        errors.append(
            f"{agent_file}: execution_class {agent.get('execution_class')!r} "
            f"must match expected {expected_execution_class!r}"
        )
    if expected_primary_eligible is not None and agent.get("primary_eligible") is not expected_primary_eligible:
        errors.append(
            f"{agent_file}: primary_eligible {agent.get('primary_eligible')!r} "
            f"must match expected {expected_primary_eligible!r}"
        )


def _match_alias(target_norm: str, alias: str) -> int:
    alias_norm = normalize(alias)
    return 100_000 + len(alias_norm) if target_norm == alias_norm else -1


def _match_write_root(target_norm: str, root: str) -> tuple[int, str] | None:
    root_norm = normalize(root)
    if target_norm == root_norm:
        return (90_000 + len(root_norm), "root_exact")
    if target_norm.startswith(root_norm + "/"):
        return (80_000 + len(root_norm), "root_child")
    return None




def _target_match_candidates(target: str, *, plugin_root: Path) -> list[str]:
    candidates = [target]
    try:
        target_path = Path(target)
    except (TypeError, ValueError):
        return candidates

    def add(candidate: str) -> None:
        if candidate not in candidates:
            candidates.append(candidate)

    def add_bears_platform_worktree_pyproject_candidate(target_value: str) -> None:
        normalized = target_value.replace("\\", "/").strip().strip("/")
        prefixes = (
            ("srv/bears/dev/platform-worktrees/", False),
            ("dev/platform-worktrees/", False),
            ("srv/bears/.worktrees/", True),
            (".worktrees/", True),
        )
        for prefix, requires_bears_platform_name in prefixes:
            if not normalized.startswith(prefix):
                continue
            remainder = normalized[len(prefix) :]
            parts = remainder.split("/", 1)
            if len(parts) != 2 or not parts[0] or parts[1] != "pyproject.toml":
                return
            if requires_bears_platform_name and not parts[0].startswith("bears-platform"):
                return
            add("/srv/bears/dev/platform/pyproject.toml")
            add("dev/platform/pyproject.toml")
            return

    def add_platform_workspace_worktree_manifest_candidate(target_value: str) -> None:
        normalized = target_value.replace("\\", "/").strip().strip("/")
        prefixes = (
            "srv/bears/dev/workspace/platform-worktrees/",
            "dev/workspace/platform-worktrees/",
        )
        manifest_names = {"MANIFEST.md", "MANIFEST.json"}
        for prefix in prefixes:
            if not normalized.startswith(prefix):
                continue
            remainder = normalized[len(prefix) :]
            parts = remainder.split("/")
            if len(parts) != 2 or not parts[0] or parts[1] not in manifest_names:
                return
            add(f"/srv/bears/dev/workspace/platform-worktrees/_archive_manifest/{parts[1]}")
            add(f"dev/workspace/platform-worktrees/_archive_manifest/{parts[1]}")
            return

    add_bears_platform_worktree_pyproject_candidate(target)
    add_platform_workspace_worktree_manifest_candidate(target)

    if target_path.is_absolute():
        try:
            relative = target_path.resolve().relative_to(plugin_root.resolve()).as_posix()
        except (OSError, ValueError):
            return candidates
        add(relative)
        add(f"plugins/bears/{relative}")
    else:
        normalized_target = target.replace("\\", "/").strip().strip("/")
        if normalized_target and not normalized_target.startswith("plugins/bears/"):
            add(f"plugins/bears/{normalized_target}")
    return candidates

def _part_matches(part: dict[str, Any], target: str) -> list[dict[str, Any]]:
    target_norm = normalize(target)
    matches: list[dict[str, Any]] = []
    for alias in part.get("aliases", []):
        if isinstance(alias, str):
            score = _match_alias(target_norm, alias)
            if score >= 0:
                matches.append({"part": part, "score": score, "match_type": "alias_exact", "evidence": alias})
    for root in part.get("write_roots", []):
        if not isinstance(root, str):
            continue
        matched = _match_write_root(target_norm, root)
        if matched is None:
            continue
        score, match_type = matched
        matches.append({"part": part, "score": score, "match_type": match_type, "evidence": root})
    return matches


def _build_required_role_shape(
    *,
    target: str,
    policy: dict[str, Any],
    matched_part: dict[str, Any] | None,
    matched_role: dict[str, Any] | None,
) -> dict[str, Any]:
    suggested_name = "bears-<primary-role-name>"
    if matched_role and isinstance(matched_role.get("name"), str):
        suggested_name = matched_role["name"]
    elif matched_part and isinstance(matched_part.get("required_role"), str):
        suggested_name = matched_part["required_role"]

    validations = []
    if matched_part and isinstance(matched_part.get("required_validations"), list):
        validations = [item for item in matched_part["required_validations"] if isinstance(item, str)]
    if not validations:
        validations = [
            "python3 scripts/platform_roles.py validate",
            "add/update validators",
            "add forward-test evidence",
        ]

    return {
        "name": suggested_name,
        "execution_class": _role_execution_class(matched_role) or "specialist_or_helper",
        "concrete_scope": (
            matched_part.get("concrete_scope") if matched_part else f"Exact ownership for {target}"
        ),
        "allowed_write_boundary": (
            matched_part.get("allowed_write_boundary") if matched_part else target
        ),
        "trust_boundary": (
            matched_part.get("trust_boundary")
            if matched_part
            else "Data, secrets, external exposure, and production impact must be explicitly bounded."
        ),
        "required_validations": validations,
    }


def _is_agent_local_route_audit_gate(command: str) -> bool:
    tokens = command.split()
    if len(tokens) < 4:
        return False
    return (
        tokens[0] == "python3"
        and tokens[1].endswith("scripts/platform_roles.py")
        and tokens[2] in {"route", "audit"}
    )


def _split_validation_ownership(commands: list[str]) -> tuple[list[str], list[str]]:
    agent_local: list[str] = []
    ci_owned: list[str] = []
    for command in commands:
        if _is_agent_local_route_audit_gate(command):
            agent_local.append(command)
        else:
            ci_owned.append(command)
    return agent_local, ci_owned


def _policy_blocked_edits(policy: dict[str, Any]) -> list[str]:
    blocked = policy.get("blocked_edits")
    if isinstance(blocked, list) and all(isinstance(item, str) for item in blocked):
        return list(blocked)
    return [
        "product implementation",
        "platform implementation",
        "runtime/deploy/migration/integration edits",
    ]


def _policy_allowed_next_actions(policy: dict[str, Any]) -> list[str]:
    allowed = policy.get("allowed_next_actions")
    if isinstance(allowed, list) and all(isinstance(item, str) for item in allowed):
        return list(allowed)
    return [
        "create/refine primary role artifact",
        "add exact catalog mapping",
        "add/update validators",
        "add forward-test evidence",
    ]


def _policy_role_development(policy: dict[str, Any], *, target: str | None = None) -> dict[str, Any]:
    configured = policy.get("role_development")
    if isinstance(configured, dict):
        packet = {
            key: list(value) if isinstance(value, list) else value
            for key, value in configured.items()
            if key in ROLE_DEVELOPMENT_REQUIRED_FIELDS
        }
    else:
        packet = {}
    packet.setdefault("lane", ROLE_DEVELOPMENT_LANE)
    packet.setdefault("owner_role", ROLE_DEVELOPMENT_OWNER_ROLE)
    packet.setdefault("max_attempts", 2)
    packet.setdefault(
        "allowed_write_scope",
        [
            "agents/*.toml",
            "assets/catalog/platform-role-catalog.v1.json",
            "assets/catalog/role-gate-methodology.v1.json",
            "scripts/platform_roles.py",
            "scripts/role_gate_methodology.py",
            "tests/test_platform_roles.py",
            "tests/test_role_gate_methodology.py",
            "AGENTS.md",
            "docs/reference/capability-governance-rules.md",
        ],
    )
    packet.setdefault("required_validations", list(ROLE_DEVELOPMENT_REQUIRED_VALIDATIONS))
    packet.setdefault("rerun_commands", list(ROLE_DEVELOPMENT_RERUN_COMMANDS))
    packet.setdefault(
        "terminal_blocker_conditions",
        list(ROLE_DEVELOPMENT_TERMINAL_BLOCKER_CONDITIONS),
    )
    packet.setdefault("unsafe_implementation_policy", ROLE_DEVELOPMENT_UNSAFE_IMPLEMENTATION_POLICY)
    if target is not None:
        packet["target"] = target
        packet["ready_to_spawn"] = True
        packet["current_attempt"] = 0
    return packet


def _policy_parent_only_targets(policy: dict[str, Any]) -> set[str]:
    targets = policy.get("parent_only_targets")
    if not isinstance(targets, list):
        return set()
    return {normalize(item) for item in targets if isinstance(item, str) and item.strip()}


def _policy_root_planning_drift_targets(policy: dict[str, Any]) -> set[str]:
    targets = policy.get("root_planning_drift_targets")
    if not isinstance(targets, list):
        targets = list(DEFAULT_ROOT_PLANNING_DRIFT_TARGETS)
    return {normalize(item) for item in targets if isinstance(item, str) and item.strip()}


def _product_apps_monorepo_policy(policy: dict[str, Any]) -> dict[str, Any]:
    configured = policy.get("product_apps_monorepo_policy")
    return configured if isinstance(configured, dict) else {}


def _product_apps_invalid_targets(policy: dict[str, Any]) -> set[str]:
    configured = _product_apps_monorepo_policy(policy).get("invalid_canonical_targets")
    if not isinstance(configured, list):
        return set()
    return {normalize(item) for item in configured if isinstance(item, str) and item.strip()}


def _is_root_planning_drift_target(target: str, policy: dict[str, Any]) -> bool:
    target_norm = normalize(target)
    for root_norm in _policy_root_planning_drift_targets(policy):
        if target_norm == root_norm or target_norm.startswith(root_norm + "/"):
            return True
    return False


def _build_blocker(
    *,
    target: str,
    reason: str,
    catalog: dict[str, Any],
    matched_part: dict[str, Any] | None = None,
    matched_role: dict[str, Any] | None = None,
    extra_evidence: list[str] | None = None,
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    policy = catalog.get("mandatory_policy", {}) if isinstance(catalog.get("mandatory_policy"), dict) else {}
    evidence = list(DEFAULT_EVIDENCE_PATHS)
    if matched_part and isinstance(matched_part.get("source"), str):
        evidence.append(matched_part["source"])
    if matched_role and isinstance(matched_role.get("agent_file"), str):
        evidence.append(str(PLUGIN_ROOT / matched_role["agent_file"]))
    if extra_evidence:
        evidence.extend(extra_evidence)
    deduped_evidence: list[str] = []
    for item in evidence:
        if item not in deduped_evidence and _evidence_item_exists(item):
            deduped_evidence.append(item)

    packet: dict[str, Any] = {
        "status": "ROLE_COVERAGE_BLOCKER",
        "missing_part": target,
        "why_blocked": reason,
        "evidence_checked": deduped_evidence,
        "blocked_edits": _policy_blocked_edits(policy),
        "allowed_next_actions": _policy_allowed_next_actions(policy),
        "role_development": _policy_role_development(policy, target=target),
        "required_role_shape": _build_required_role_shape(
            target=target,
            policy=policy,
            matched_part=matched_part,
            matched_role=matched_role,
        ),
        "decomposition_required": bool(matched_part and matched_part.get("decomposition_required"))
        or reason in {"unknown", "parent_only", "invalid_broad_role", "ambiguous_owner"},
    }
    if matched_part and isinstance(matched_part.get("name"), str):
        packet["matched_platform_part"] = matched_part["name"]
    if matched_part and isinstance(matched_part.get("part_kind"), str):
        packet["matched_part_kind"] = matched_part["part_kind"]
    if matched_role and isinstance(matched_role.get("name"), str):
        packet["matched_role"] = matched_role["name"]
    matched_execution_class = _role_execution_class(matched_role)
    if matched_execution_class:
        packet["matched_execution_class"] = matched_execution_class
    if validation_errors:
        packet["validation_errors"] = validation_errors
    return packet


def _valid_supporting_roles(part: dict[str, Any], role_index: dict[str, dict[str, Any]]) -> list[str]:
    supporting: list[str] = []
    for role_name in part.get("supporting_roles", []):
        role = role_index.get(role_name)
        if role and role.get("role_kind") == "reviewer":
            supporting.append(role_name)
    return supporting


def route_target(catalog: dict[str, Any], target: str, *, plugin_root: Path = PLUGIN_ROOT) -> dict[str, Any]:
    role_index = _role_map(catalog)
    policy = catalog.get("mandatory_policy", {}) if isinstance(catalog.get("mandatory_policy"), dict) else {}
    target_norm = normalize(target)
    if target_norm in _product_apps_invalid_targets(policy):
        return _build_blocker(
            target=target,
            reason="unmapped",
            catalog=catalog,
            extra_evidence=[str(DEFAULT_CATALOG)],
        )
    root_planning_drift = _is_root_planning_drift_target(target, policy)
    if normalize(target) in _policy_parent_only_targets(policy):
        return _build_blocker(target=target, reason="parent_only", catalog=catalog)

    matches: list[dict[str, Any]] = []
    for candidate in _target_match_candidates(target, plugin_root=plugin_root):
        for part in catalog.get("platform_parts", []):
            if isinstance(part, dict):
                matches.extend(_part_matches(part, candidate))

    if not matches:
        reason = "unmapped" if _is_path_like(target) else "unknown"
        extra_evidence = ["/srv/bears/AGENTS.md"] if root_planning_drift else None
        return _build_blocker(target=target, reason=reason, catalog=catalog, extra_evidence=extra_evidence)

    best_score = max(match["score"] for match in matches)
    winners = [match for match in matches if match["score"] == best_score]
    winner_names = {winner["part"]["name"] for winner in winners}
    if len(winner_names) > 1:
        return _build_blocker(target=target, reason="ambiguous_owner", catalog=catalog, extra_evidence=[winner["part"]["name"] for winner in winners])

    winner = winners[0]
    part = winner["part"]
    if part.get("name") == "product_apps_monorepo_root" and winner.get("match_type") == "root_child":
        return _build_blocker(
            target=target,
            reason="unmapped",
            catalog=catalog,
            matched_part=part,
            matched_role=role_index.get(part.get("required_role")),
            extra_evidence=[str(DEFAULT_CATALOG)],
        )
    role = role_index.get(part.get("required_role"))

    if part.get("part_kind") != "concrete":
        return _build_blocker(target=target, reason="parent_only", catalog=catalog, matched_part=part, matched_role=role)

    if role is None:
        return _build_blocker(target=target, reason="missing_role", catalog=catalog, matched_part=part)

    agent_file = role.get("agent_file")
    agent_path = plugin_root / agent_file if isinstance(agent_file, str) else None
    if agent_path is None or not agent_path.is_file():
        return _build_blocker(target=target, reason="missing_role", catalog=catalog, matched_part=part, matched_role=role)

    role_kind = role.get("role_kind")
    execution_class = _role_execution_class(role)
    if (
        role_kind not in PRIMARY_ROLE_KINDS
        or execution_class not in EXECUTION_CLASSES
        or role.get("primary_eligible") is not True
    ):
        return _build_blocker(target=target, reason="invalid_broad_role", catalog=catalog, matched_part=part, matched_role=role)

    supporting_roles = _valid_supporting_roles(part, role_index)
    validations = [item for item in part.get("required_validations", []) if isinstance(item, str)]
    agent_local_validations, ci_owned_validations = _split_validation_ownership(validations)
    return {
        "status": "matched",
        "concrete_part": part["name"],
        "platform_part": part["name"],
        "primary_role": role["name"],
        "primary_role_kind": role_kind,
        "primary_execution_class": execution_class,
        "required_role": role["name"],
        "supporting_roles": supporting_roles,
        "reviewer_triggers": [item for item in part.get("reviewer_triggers", []) if isinstance(item, str)],
        "allowed_write_boundary": part.get("allowed_write_boundary"),
        "trust_boundary": part.get("trust_boundary"),
        "validation_required": validations,
        "validation_required_agent_local": agent_local_validations,
        "validation_required_ci_owned": ci_owned_validations,
        "manual_execution_requires_operator_approval": False,
        "validation_execution_policy": VALIDATION_EXECUTION_POLICY,
        "decomposition_required": bool(part.get("decomposition_required")),
        "no_role_policy": part.get("no_role_policy", "blocker"),
    }


def _validate_policy(policy: dict[str, Any], errors: list[str]) -> None:
    missing = MANDATORY_POLICY_REQUIRED_FIELDS - policy.keys()
    if missing:
        errors.append(f"mandatory_policy missing fields: {sorted(missing)}")
        return
    if policy.get("missing_role_status") != "ROLE_COVERAGE_BLOCKER":
        errors.append("mandatory_policy.missing_role_status must be ROLE_COVERAGE_BLOCKER")
    if policy.get("no_role_policy") != "blocker":
        errors.append("mandatory_policy.no_role_policy must be blocker")
    if policy.get("unknown_child_policy") != "ROLE_COVERAGE_BLOCKER":
        errors.append("mandatory_policy.unknown_child_policy must be ROLE_COVERAGE_BLOCKER")
    if policy.get("one_primary_role_required") is not True:
        errors.append("mandatory_policy.one_primary_role_required must be true")
    if policy.get("parent_group_coverage_allowed") is not False:
        errors.append("mandatory_policy.parent_group_coverage_allowed must be false")
    if policy.get("broad_fallback_matching_allowed") is not False:
        errors.append("mandatory_policy.broad_fallback_matching_allowed must be false")
    invariant = policy.get("main_invariant")
    if not isinstance(invariant, str) or "exactly one valid primary specialist or helper role" not in invariant:
        errors.append("mandatory_policy.main_invariant must describe the one-primary-role invariant")
    _require_non_empty_list(policy.get("role_required_for"), "mandatory_policy.role_required_for", errors)
    _require_non_empty_list(policy.get("parent_only_targets"), "mandatory_policy.parent_only_targets", errors)
    _require_non_empty_list(policy.get("blocked_edits"), "mandatory_policy.blocked_edits", errors)
    _require_non_empty_list(policy.get("allowed_next_actions"), "mandatory_policy.allowed_next_actions", errors)
    role_development = policy.get("role_development")
    if not isinstance(role_development, dict):
        errors.append("mandatory_policy.role_development must be an object")
    else:
        missing_role_development = ROLE_DEVELOPMENT_REQUIRED_FIELDS - role_development.keys()
        if missing_role_development:
            errors.append(
                "mandatory_policy.role_development missing fields: "
                + ", ".join(sorted(missing_role_development))
            )
        if role_development.get("lane") != ROLE_DEVELOPMENT_LANE:
            errors.append("mandatory_policy.role_development.lane must be role-development")
        if role_development.get("owner_role") != ROLE_DEVELOPMENT_OWNER_ROLE:
            errors.append("mandatory_policy.role_development.owner_role must be bears-platform-role-governor")
        max_attempts = role_development.get("max_attempts")
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 3:
            errors.append("mandatory_policy.role_development.max_attempts must be an integer from 1 to 3")
        _require_non_empty_list(
            role_development.get("allowed_write_scope"),
            "mandatory_policy.role_development.allowed_write_scope",
            errors,
        )
        if role_development.get("required_validations") != ROLE_DEVELOPMENT_REQUIRED_VALIDATIONS:
            errors.append("mandatory_policy.role_development.required_validations must match canonical commands")
        if role_development.get("rerun_commands") != ROLE_DEVELOPMENT_RERUN_COMMANDS:
            errors.append("mandatory_policy.role_development.rerun_commands must match canonical commands")
        if role_development.get("terminal_blocker_conditions") != ROLE_DEVELOPMENT_TERMINAL_BLOCKER_CONDITIONS:
            errors.append(
                "mandatory_policy.role_development.terminal_blocker_conditions must match canonical conditions"
            )
        if role_development.get("unsafe_implementation_policy") != ROLE_DEVELOPMENT_UNSAFE_IMPLEMENTATION_POLICY:
            errors.append("mandatory_policy.role_development.unsafe_implementation_policy must match canonical policy")
    blocker_reasons = policy.get("blocker_reasons")
    if not isinstance(blocker_reasons, list) or set(blocker_reasons) != BLOCKER_REASONS:
        errors.append(f"mandatory_policy.blocker_reasons must equal {sorted(BLOCKER_REASONS)}")
    audit = policy.get("independent_control_audit")
    if not isinstance(audit, dict):
        errors.append("mandatory_policy.independent_control_audit must be an object")
    else:
        if audit.get("required") is not True:
            errors.append("mandatory_policy.independent_control_audit.required must be true")
        if audit.get("auditor_role") != "bears-platform-role-governor":
            errors.append("mandatory_policy.independent_control_audit.auditor_role must be bears-platform-role-governor")
        _require_non_empty_list(audit.get("must_prove"), "mandatory_policy.independent_control_audit.must_prove", errors)
    if not isinstance(policy.get("definitions"), dict) or not policy["definitions"]:
        errors.append("mandatory_policy.definitions must be a non-empty object")
    _require_non_empty_list(policy.get("selection_rules"), "mandatory_policy.selection_rules", errors)
    apps_policy = policy.get("product_apps_monorepo_policy")
    if not isinstance(apps_policy, dict):
        errors.append("mandatory_policy.product_apps_monorepo_policy must be an object")
    else:
        missing_apps_policy = PRODUCT_APPS_MONOREPO_POLICY_REQUIRED_FIELDS - apps_policy.keys()
        if missing_apps_policy:
            errors.append(
                "mandatory_policy.product_apps_monorepo_policy missing fields: "
                + ", ".join(sorted(missing_apps_policy))
            )
        if apps_policy.get("canonical_local_root") != "/srv/bears/dev/app":
            errors.append("mandatory_policy.product_apps_monorepo_policy.canonical_local_root must be /srv/bears/dev/app")
        if apps_policy.get("canonical_remote") != "BearsCLOUD/apps":
            errors.append("mandatory_policy.product_apps_monorepo_policy.canonical_remote must be BearsCLOUD/apps")
        invalid_targets = apps_policy.get("invalid_canonical_targets")
        if not isinstance(invalid_targets, list):
            errors.append("mandatory_policy.product_apps_monorepo_policy.invalid_canonical_targets must be a list")
        else:
            if any(not isinstance(item, str) or not item for item in invalid_targets):
                errors.append(
                    "mandatory_policy.product_apps_monorepo_policy.invalid_canonical_targets must contain only non-empty strings"
                )


def _has_seller_legacy_path(value: str) -> bool:
    legacy_tokens = (*SELLER_LEGACY_ROOTS, "legacy/seller/apps/", "projects/seller/apps/")
    return any(token in value for token in legacy_tokens)


def _validate_no_seller_bound_core_defaults(catalog: dict[str, Any], errors: list[str]) -> None:
    part_index = _part_map(catalog)
    for part_name, neutral_path in AUTH_GATEWAY_DEPLOY_CORE_PARTS.items():
        part = part_index.get(part_name)
        if part is None:
            errors.append(f"no-seller-bound-core: missing platform part {part_name}")
            continue
        for field in ("aliases", "write_roots"):
            values = part.get(field)
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and _has_seller_legacy_path(value):
                    errors.append(
                        f"no-seller-bound-core: platform part {part_name}.{field} must not use seller path {value}"
                    )
        if neutral_path not in part.get("write_roots", []):
            errors.append(
                f"no-seller-bound-core: platform part {part_name}.write_roots must include neutral path {neutral_path}"
            )

    routes = [
        route
        for route in catalog.get("workflow_routes", [])
        if isinstance(route, dict) and route.get("workflow_id") == "auth-gateway-deploy-core"
    ]
    if not routes:
        return
    targets = routes[0].get("required_route_targets")
    if targets != AUTH_GATEWAY_DEPLOY_CORE_PARTS:
        errors.append(
            "no-seller-bound-core: auth-gateway-deploy-core required_route_targets must use neutral "
            "/srv/bears/dev/platform/src/bears_platform paths"
        )
        return
    for part_name, route_target_value in targets.items():
        if _has_seller_legacy_path(route_target_value):
            errors.append(f"no-seller-bound-core: workflow route target {part_name} must not use seller path")


def _is_product_apps_nested_value(value: str) -> bool:
    normalized = normalize(value)
    return normalized.startswith("srv/bears/dev/app/") or normalized.startswith("dev/app/")


def _is_bearscloud_repo_value(value: str) -> str | None:
    normalized = value.strip()
    prefixes = (
        "BearsCLOUD/",
        "https://github.com/BearsCLOUD/",
        "git@github.com:BearsCLOUD/",
    )
    for prefix in prefixes:
        if not normalized.startswith(prefix):
            continue
        repo = normalized[len(prefix) :]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return f"BearsCLOUD/{repo.strip('/')}"
    return None


def _validate_product_apps_monorepo_catalog(catalog: dict[str, Any], errors: list[str]) -> None:
    policy = catalog.get("mandatory_policy")
    apps_policy = _product_apps_monorepo_policy(policy if isinstance(policy, dict) else {})
    canonical_local = apps_policy.get("canonical_local_root")
    canonical_remote = apps_policy.get("canonical_remote")
    if canonical_local != "/srv/bears/dev/app" or canonical_remote != "BearsCLOUD/apps":
        return

    canonical_parts: list[str] = []
    invalid_targets = {
        normalize(item)
        for item in apps_policy.get("invalid_canonical_targets", [])
        if isinstance(item, str)
    }
    allowed_nested_statuses = {
        item
        for item in apps_policy.get("allowed_nested_statuses", [])
        if isinstance(item, str)
    }
    required_legacy_fields = {
        item
        for item in apps_policy.get("required_legacy_fields", [])
        if isinstance(item, str)
    }
    expected_legacy_fields = {
        "status",
        "active_replacement",
        "issue_link_invariant",
        "umbrella_issue_invariant",
        "source_migration_issue_invariant",
        "canonical_planning_project_invariant",
        "infra_local_cd_safety_invariant",
        "platform_boundary_exclusion_invariant",
    }
    missing_policy_fields = sorted(expected_legacy_fields - required_legacy_fields)
    if missing_policy_fields:
        errors.append(
            "product-apps-monorepo: product_apps_monorepo_policy.required_legacy_fields "
            f"missing {missing_policy_fields}"
        )

    archive_readiness = apps_policy.get("archive_readiness_invariant")
    if not isinstance(archive_readiness, str) or not all(
        token in archive_readiness
        for token in ("umbrella issue", "source migration issue", "canonical", "Project", "local_cd", "platform")
    ):
        errors.append(
            "product-apps-monorepo: archive_readiness_invariant must require umbrella issue, "
            "source migration issue, canonical Apps planning Project, infra/local_cd safety, and platform exclusion"
        )
    planning_project = apps_policy.get("canonical_planning_project")
    required_project_fields = {
        "source_repo/app_directory",
        "migration_stage",
        "infra_local_cd_status",
        "platform_boundary_status",
        "archive_readiness",
        "owner_role",
        "blocker_status",
    }
    if not isinstance(planning_project, dict):
        errors.append("product-apps-monorepo: canonical_planning_project must be declared")
    else:
        if planning_project.get("owner_repository") != canonical_remote:
            errors.append("product-apps-monorepo: canonical_planning_project.owner_repository must be BearsCLOUD/apps")
        if planning_project.get("name") != "Apps Migration & Planning":
            errors.append("product-apps-monorepo: canonical_planning_project.name must be Apps Migration & Planning")
        fields = {item for item in planning_project.get("required_issue_fields", []) if isinstance(item, str)}
        missing_fields = sorted(required_project_fields - fields)
        if missing_fields:
            errors.append(
                "product-apps-monorepo: canonical_planning_project.required_issue_fields "
                f"missing {missing_fields}"
            )
        scope = planning_project.get("scope")
        if not isinstance(scope, str) or not all(token in scope for token in ("per-source Projects", "legacy evidence", "must not be required", "used for PASS")):
            errors.append(
                "product-apps-monorepo: canonical_planning_project.scope must allow per-source Projects only as legacy evidence, not as required/PASS evidence"
            )
        if planning_project.get("api_proof_required_for_archive_pass") is not True:
            errors.append("product-apps-monorepo: canonical_planning_project.api_proof_required_for_archive_pass must be true")
    infra_invariant = apps_policy.get("infra_local_cd_archive_readiness_invariant")
    if not isinstance(infra_invariant, str) or not all(
        token in infra_invariant for token in ("Kubernetes", "local_cd", "old source repository")
    ):
        errors.append(
            "product-apps-monorepo: infra_local_cd_archive_readiness_invariant must require "
            "Kubernetes desired-state and local_cd safety proof"
        )
    platform_invariant = apps_policy.get("platform_boundary_exclusion_invariant")
    if not isinstance(platform_invariant, str) or not all(
        token in platform_invariant for token in ("/srv/bears/dev/platform", "/srv/bears/dev/workspace", "platform auditor")
    ):
        errors.append(
            "product-apps-monorepo: platform_boundary_exclusion_invariant must exclude platform temp checkouts "
            "unless classified by a platform auditor"
        )
    platform_exclusion = apps_policy.get("platform_temp_checkout_exclusion")
    if not isinstance(platform_exclusion, dict):
        errors.append("product-apps-monorepo: platform_temp_checkout_exclusion must be declared")
    else:
        excluded_roots = platform_exclusion.get("excluded_roots")
        if not isinstance(excluded_roots, list) or not {
            "/srv/bears/dev/platform",
            "/srv/bears/dev/workspace",
        }.issubset({item for item in excluded_roots if isinstance(item, str)}):
            errors.append("product-apps-monorepo: platform_temp_checkout_exclusion.excluded_roots must include platform roots")
        if platform_exclusion.get("classification_required_by") != "platform auditor":
            errors.append("product-apps-monorepo: platform_temp_checkout_exclusion.classification_required_by must be platform auditor")

    for part in catalog.get("platform_parts", []):
        if not isinstance(part, dict):
            continue
        part_name = part.get("name", "<unknown>")
        values = [
            value
            for field in ("aliases", "write_roots")
            for value in part.get(field, [])
            if isinstance(value, str)
        ]
        if any(normalize(value) in invalid_targets for value in values):
            errors.append(f"product-apps-monorepo: {part_name} must not alias invalid canonical target")

        canonical_repository = part.get("canonical_repository")
        if isinstance(canonical_repository, dict):
            if canonical_repository.get("remote") == canonical_remote:
                canonical_parts.append(str(part_name))
            elif part.get("group") == "products":
                errors.append(
                    f"product-apps-monorepo: {part_name}.canonical_repository.remote must be {canonical_remote}"
                )

        nested = any(_is_product_apps_nested_value(value) for value in values)
        old_remote = part.get("group") == "products" and any(
            repo is not None and repo != canonical_remote
            for repo in (_is_bearscloud_repo_value(value) for value in values)
        )
        if part.get("name") == "product_apps_monorepo_root":
            if canonical_repository != {
                "local_root": canonical_local,
                "remote": canonical_remote,
                "github_repo": canonical_remote,
            }:
                errors.append("product-apps-monorepo: product_apps_monorepo_root must declare canonical_repository")
            if canonical_local not in part.get("write_roots", []):
                errors.append("product-apps-monorepo: product_apps_monorepo_root.write_roots must include /srv/bears/dev/app")
            continue

        if not (nested or old_remote):
            continue
        legacy = part.get("legacy_compatibility")
        if not isinstance(legacy, dict):
            errors.append(f"product-apps-monorepo: {part_name} old app route must declare legacy_compatibility")
            continue
        missing = sorted(required_legacy_fields - legacy.keys())
        if missing:
            errors.append(f"product-apps-monorepo: {part_name}.legacy_compatibility missing {missing}")
        if legacy.get("active_replacement") != canonical_remote:
            errors.append(f"product-apps-monorepo: {part_name}.legacy_compatibility.active_replacement must be {canonical_remote}")
        deprecated_refs = {
            item for item in legacy.get("deprecated_refs", []) if isinstance(item, str)
        }
        old_remote_repos = sorted(
            {
                repo
                for repo in (_is_bearscloud_repo_value(value) for value in values)
                if repo is not None and repo != canonical_remote
            }
        )
        missing_deprecated_remote_refs = [
            repo for repo in old_remote_repos if repo not in deprecated_refs
        ]
        if missing_deprecated_remote_refs:
            errors.append(
                f"product-apps-monorepo: {part_name}.legacy_compatibility.deprecated_refs "
                f"must include old repository aliases {missing_deprecated_remote_refs}"
            )
        status = legacy.get("status")
        if status not in allowed_nested_statuses:
            errors.append(f"product-apps-monorepo: {part_name}.legacy_compatibility.status must be one of {sorted(allowed_nested_statuses)}")
        issue_link = legacy.get("issue_link_invariant")
        if not isinstance(issue_link, str) or canonical_remote not in issue_link:
            errors.append(f"product-apps-monorepo: {part_name}.legacy_compatibility.issue_link_invariant must name {canonical_remote}")
        planning_link = legacy.get("canonical_planning_project_invariant")
        if not isinstance(planning_link, str) or not all(
            token in planning_link
            for token in (canonical_remote, "Apps Migration & Planning", "canonical", "Project", "source_repo/app_directory", "archive_readiness", "API proof")
        ):
            errors.append(
                f"product-apps-monorepo: {part_name}.legacy_compatibility.canonical_planning_project_invariant "
                "must require canonical Apps planning Project membership with populated migration fields"
            )
        if "Migrate " in planning_link and " into apps" in planning_link:
            errors.append(
                f"product-apps-monorepo: {part_name}.legacy_compatibility.canonical_planning_project_invariant "
                "must not require a separate per-source Project"
            )
        per_source_policy = legacy.get("per_source_projects_policy")
        if per_source_policy != "legacy_evidence_only_not_required_not_created_not_pass":
            errors.append(
                f"product-apps-monorepo: {part_name}.legacy_compatibility.per_source_projects_policy "
                "must mark per-source Projects as legacy evidence only"
            )
        infra_safety = legacy.get("infra_local_cd_safety_invariant")
        if not isinstance(infra_safety, str) or not all(
            token in infra_safety for token in ("Kubernetes", "local_cd", "old source repository")
        ):
            errors.append(
                f"product-apps-monorepo: {part_name}.legacy_compatibility.infra_local_cd_safety_invariant "
                "must require infra/local_cd safety proof"
            )
        platform_exclusion_text = legacy.get("platform_boundary_exclusion_invariant")
        if not isinstance(platform_exclusion_text, str) or not all(
            token in platform_exclusion_text for token in ("/srv/bears/dev/platform", "platform auditor")
        ):
            errors.append(
                f"product-apps-monorepo: {part_name}.legacy_compatibility.platform_boundary_exclusion_invariant "
                "must exclude platform temp checkouts unless classified by a platform auditor"
            )

    if canonical_parts != ["product_apps_monorepo_root"]:
        errors.append(
            "product-apps-monorepo: exactly product_apps_monorepo_root must declare "
            f"canonical_repository for {canonical_remote}; got {canonical_parts}"
        )


def validate_catalog(catalog: dict[str, Any], *, plugin_root: Path = PLUGIN_ROOT) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema") != "bears-platform-role-catalog.v1":
        errors.append("schema must be bears-platform-role-catalog.v1")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")

    policy = catalog.get("mandatory_policy")
    if not isinstance(policy, dict):
        errors.append("mandatory_policy must be an object")
    else:
        _validate_policy(policy, errors)

    role_names: set[str] = set()
    alias_registry: dict[str, str] = {}
    write_root_registry: dict[str, str] = {}
    roles = catalog.get("roles")
    if not isinstance(roles, list) or not roles:
        errors.append("roles must be a non-empty list")
    else:
        for index, role in enumerate(roles):
            if not isinstance(role, dict):
                errors.append(f"roles[{index}] must be an object")
                continue
            missing = REQUIRED_ROLE_FIELDS - role.keys()
            if missing:
                errors.append(f"role {role.get('name', index)} missing fields: {sorted(missing)}")
            name = role.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"roles[{index}].name must be non-empty")
                continue
            if name in role_names:
                errors.append(f"duplicate role name: {name}")
            role_names.add(name)

            role_kind = role.get("role_kind")
            if role_kind not in ROLE_KINDS:
                errors.append(f"role {name}.role_kind must be one of {sorted(ROLE_KINDS)}")
            execution_class = role.get("execution_class")
            if execution_class not in EXECUTION_CLASSES:
                errors.append(f"role {name}.execution_class must be one of {sorted(EXECUTION_CLASSES)}")
            if role_kind in {"reviewer", "orchestrator"} and execution_class != "helper":
                errors.append(f"role {name} {role_kind} must set execution_class=helper")
            agent_file_value = role.get("agent_file")
            agent_file_name = Path(agent_file_value).name if isinstance(agent_file_value, str) else ""
            if _helper_marker_present(name, agent_file_name) and execution_class != "helper":
                errors.append(f"role {name} helper-like profile must set execution_class=helper")
            primary_eligible = role.get("primary_eligible")
            if not isinstance(primary_eligible, bool):
                errors.append(f"role {name}.primary_eligible must be boolean")
            if role_kind == "reviewer":
                if role.get("sandbox_mode") != "read-only":
                    errors.append(f"role {name} reviewer must use sandbox_mode=read-only")
                if primary_eligible is not False:
                    errors.append(f"role {name} reviewer must set primary_eligible=false")
                allowed_write_zones = set(role.get("allowed_write_zones", []))
                if allowed_write_zones != REVIEWER_ALLOWED_WRITE_ZONES:
                    errors.append(
                        f"role {name} reviewer allowed_write_zones must be "
                        f"{sorted(REVIEWER_ALLOWED_WRITE_ZONES)}"
                    )
                forbidden_actions = set(role.get("forbidden_actions", []))
                missing_forbidden_actions = sorted(
                    REVIEWER_REQUIRED_FORBIDDEN_ACTIONS - forbidden_actions
                )
                if missing_forbidden_actions:
                    errors.append(
                        f"role {name} reviewer forbidden_actions missing: "
                        + ", ".join(missing_forbidden_actions)
                    )
                for action in forbidden_actions:
                    lower_action = action.casefold()
                    if "unless" in lower_action or "write scope" in lower_action:
                        errors.append(
                            f"role {name} reviewer forbidden_actions must not include "
                            "write-scope exceptions"
                        )
            if role_kind == "orchestrator" and primary_eligible is not False:
                errors.append(f"role {name} orchestrator must set primary_eligible=false")
            if role_kind == "specialist" and primary_eligible is not True:
                errors.append(f"role {name} specialist must set primary_eligible=true")
            if role_kind == "helper" and primary_eligible is not True:
                errors.append(f"role {name} helper must set primary_eligible=true")
            if execution_class == "specialist" and primary_eligible is not True:
                errors.append(f"role {name} specialist execution_class must set primary_eligible=true")

            for list_field in ("allowed_write_zones", "forbidden_actions", "evidence_required"):
                _require_non_empty_list(role.get(list_field), f"role {name}.{list_field}", errors)

            agent_file = role.get("agent_file")
            if isinstance(agent_file, str):
                agent_path = plugin_root / agent_file
                if not agent_path.is_file():
                    errors.append(f"role {name} agent_file missing: {agent_file}")
                else:
                    try:
                        agent = load_toml(agent_path)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"cannot parse role TOML {agent_file}: {exc}")
                    else:
                        for field in REQUIRED_AGENT_TOML_FIELDS:
                            value = agent.get(field)
                            if not isinstance(value, str) or not value.strip():
                                errors.append(f"{agent_file}: missing required field {field}")
                        if agent.get("name") != name:
                            errors.append(f"{agent_file}: name {agent.get('name')!r} must match catalog role {name!r}")
                        _validate_agent_toml_classification(
                            errors=errors,
                            agent_file=agent_file,
                            agent=agent,
                            expected_role_kind=role_kind if isinstance(role_kind, str) else None,
                            expected_execution_class=execution_class if isinstance(execution_class, str) else None,
                            expected_primary_eligible=primary_eligible if isinstance(primary_eligible, bool) else None,
                        )

    role_index = _role_map(catalog)
    parts = catalog.get("platform_parts")
    part_names: set[str] = set()
    if not isinstance(parts, list) or not parts:
        errors.append("platform_parts must be a non-empty list")
    else:
        for index, part in enumerate(parts):
            if not isinstance(part, dict):
                errors.append(f"platform_parts[{index}] must be an object")
                continue
            missing = REQUIRED_PART_FIELDS - part.keys()
            if missing:
                errors.append(f"platform part {part.get('name', index)} missing fields: {sorted(missing)}")
            name = part.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"platform_parts[{index}].name must be non-empty")
                continue
            if name in part_names:
                errors.append(f"duplicate platform part name: {name}")
            part_names.add(name)

            if part.get("role_required") is not True:
                errors.append(f"platform part {name} must set role_required=true")
            if part.get("no_role_policy") != "blocker":
                errors.append(f"platform part {name} must set no_role_policy=blocker")
            part_kind = part.get("part_kind")
            if part_kind not in PART_KINDS:
                errors.append(f"platform part {name}.part_kind must be one of {sorted(PART_KINDS)}")

            required_role = part.get("required_role")
            if required_role not in role_names:
                errors.append(f"platform part {name} required_role not found in roles: {required_role}")
            else:
                required_role_entry = role_index[required_role]
                required_execution_class = _role_execution_class(required_role_entry)
                if part_kind == "concrete":
                    if required_role_entry.get("role_kind") not in PRIMARY_ROLE_KINDS:
                        errors.append(f"platform part {name} must point to a primary-capable role_kind")
                    if required_execution_class not in EXECUTION_CLASSES:
                        errors.append(f"platform part {name} must point to a helper or specialist execution_class")
                    if required_role_entry.get("primary_eligible") is not True:
                        errors.append(f"platform part {name} primary role must set primary_eligible=true")
                elif required_role_entry.get("role_kind") in PRIMARY_ROLE_KINDS:
                    errors.append(f"group part {name} must not point to a primary-capable role_kind")

            _require_non_empty_list(part.get("aliases"), f"platform part {name}.aliases", errors)
            if not isinstance(part.get("write_roots"), list):
                errors.append(f"platform part {name}.write_roots must be a list")
            if not isinstance(part.get("concrete_scope"), str) or not part["concrete_scope"].strip():
                errors.append(f"platform part {name}.concrete_scope must be non-empty")
            if not isinstance(part.get("allowed_write_boundary"), str) or not part["allowed_write_boundary"].strip():
                errors.append(f"platform part {name}.allowed_write_boundary must be non-empty")
            if not isinstance(part.get("trust_boundary"), str) or not part["trust_boundary"].strip():
                errors.append(f"platform part {name}.trust_boundary must be non-empty")
            _require_non_empty_list(part.get("required_validations"), f"platform part {name}.required_validations", errors)
            if not isinstance(part.get("supporting_roles"), list):
                errors.append(f"platform part {name}.supporting_roles must be a list")
            if not isinstance(part.get("reviewer_triggers"), list):
                errors.append(f"platform part {name}.reviewer_triggers must be a list")
            if not isinstance(part.get("decomposition_required"), bool):
                errors.append(f"platform part {name}.decomposition_required must be boolean")

            for role_name in part.get("supporting_roles", []):
                if role_name not in role_names:
                    errors.append(f"platform part {name} supporting role not found: {role_name}")
                    continue
                supporting_role = role_index[role_name]
                if supporting_role.get("role_kind") != "reviewer":
                    errors.append(f"platform part {name} supporting role {role_name} must be reviewer-only")

            for alias in part.get("aliases", []):
                if not isinstance(alias, str):
                    errors.append(f"platform part {name}.aliases entries must be strings")
                    continue
                alias_norm = normalize(alias)
                previous = alias_registry.get(alias_norm)
                if previous and previous != name:
                    errors.append(f"alias overlap between {previous} and {name}: {alias}")
                else:
                    alias_registry[alias_norm] = name
            for write_root in part.get("write_roots", []):
                if not isinstance(write_root, str):
                    errors.append(f"platform part {name}.write_roots entries must be strings")
                    continue
                root_norm = normalize(write_root)
                previous = write_root_registry.get(root_norm)
                if previous and previous != name:
                    errors.append(f"write_root overlap between {previous} and {name}: {write_root}")
                else:
                    write_root_registry[root_norm] = name

    role_agent_files = {
        role.get("agent_file")
        for role in roles
        if isinstance(role, dict) and isinstance(role.get("agent_file"), str)
    }
    mapped_agent_files: set[str] = set()
    mappings = catalog.get("agent_profile_mappings")
    if not isinstance(mappings, list):
        errors.append("agent_profile_mappings must be a list")
        mappings = []
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            errors.append(f"agent_profile_mappings[{index}] must be an object")
            continue
        missing = REQUIRED_AGENT_PROFILE_MAPPING_FIELDS - mapping.keys()
        if missing:
            errors.append(f"agent_profile_mapping {mapping.get('agent_file', index)} missing fields: {sorted(missing)}")
        agent_file = mapping.get("agent_file")
        if not isinstance(agent_file, str) or not agent_file:
            errors.append(f"agent_profile_mappings[{index}].agent_file must be non-empty")
            continue
        if agent_file in role_agent_files:
            errors.append(f"agent_profile_mapping {agent_file} duplicates catalog role agent_file")
        if agent_file in mapped_agent_files:
            errors.append(f"duplicate agent_profile_mapping agent_file: {agent_file}")
        mapped_agent_files.add(agent_file)
        agent_path = plugin_root / agent_file
        if not agent_path.is_file():
            errors.append(f"agent_profile_mapping agent_file missing: {agent_file}")
            continue
        try:
            agent = load_toml(agent_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot parse mapped agent TOML {agent_file}: {exc}")
            continue
        profile_name = mapping.get("profile_name")
        if not isinstance(profile_name, str) or not profile_name:
            errors.append(f"agent_profile_mapping {agent_file}.profile_name must be non-empty")
        elif agent.get("name") != profile_name:
            errors.append(
                f"agent_profile_mapping {agent_file}.profile_name {profile_name!r} "
                f"must match TOML name {agent.get('name')!r}"
            )
        execution_class = mapping.get("execution_class")
        if execution_class not in EXECUTION_CLASSES:
            errors.append(f"agent_profile_mapping {agent_file}.execution_class must be one of {sorted(EXECUTION_CLASSES)}")
        if _helper_marker_present(str(profile_name or ""), Path(agent_file).name) and execution_class != "helper":
            errors.append(f"agent_profile_mapping {agent_file} helper-like profile must set execution_class=helper")
        mapped_role = mapping.get("mapped_role")
        if mapped_role not in role_names:
            errors.append(f"agent_profile_mapping {agent_file} mapped_role not found in roles: {mapped_role}")
        concrete_part = mapping.get("concrete_part")
        if concrete_part not in part_names:
            errors.append(f"agent_profile_mapping {agent_file} concrete_part not found: {concrete_part}")
        coverage_kind = mapping.get("coverage_kind")
        if not isinstance(coverage_kind, str) or not coverage_kind:
            errors.append(f"agent_profile_mapping {agent_file}.coverage_kind must be non-empty")
        expected_role_kind = _expected_profile_role_kind(coverage_kind if isinstance(coverage_kind, str) else None)
        expected_primary_eligible = _expected_profile_primary_eligible(
            coverage_kind if isinstance(coverage_kind, str) else None
        )
        if expected_role_kind is None or expected_primary_eligible is None:
            errors.append(f"agent_profile_mapping {agent_file}.coverage_kind is not supported: {coverage_kind}")
        _validate_agent_toml_classification(
            errors=errors,
            agent_file=agent_file,
            agent=agent,
            expected_role_kind=expected_role_kind,
            expected_execution_class=execution_class if isinstance(execution_class, str) else None,
            expected_primary_eligible=expected_primary_eligible,
        )

    actual_agent_files = {path.relative_to(plugin_root).as_posix() for path in (plugin_root / "agents").glob("*.toml")}
    covered_agent_files = set(role_agent_files) | mapped_agent_files
    missing_agent_files = sorted(actual_agent_files - covered_agent_files)
    stale_agent_files = sorted(covered_agent_files - actual_agent_files)
    if missing_agent_files or stale_agent_files:
        errors.append(
            "agents/*.toml coverage mismatch: "
            f"missing={missing_agent_files} stale={stale_agent_files}"
        )

    for route in catalog.get("workflow_routes", []):
        if not isinstance(route, dict):
            errors.append("workflow_routes entries must be objects")
            continue
        workflow_file = route.get("workflow_file")
        workflow_path = plugin_root / workflow_file if isinstance(workflow_file, str) else None
        if workflow_path is None or not workflow_path.is_file():
            errors.append(f"workflow route {route.get('workflow_id')} workflow_file missing: {workflow_file}")
        for part_name in route.get("ordered_parts", []):
            if part_name not in part_names:
                errors.append(f"workflow route {route.get('workflow_id')} unknown ordered part: {part_name}")
        for role_name in route.get("required_roles", []):
            if role_name not in role_names:
                errors.append(f"workflow route {route.get('workflow_id')} unknown required role: {role_name}")

    for check in catalog.get("route_regression_checks", []):
        if not isinstance(check, dict):
            errors.append("route_regression_checks entries must be objects")
            continue
        target = check.get("target")
        if not isinstance(target, str) or not target:
            errors.append("route_regression_checks target must be non-empty")
            continue
        routed = route_target(catalog, target, plugin_root=plugin_root)
        expected_status = check.get("expected_status")
        if routed.get("status") != expected_status:
            errors.append(f"route check {target}: expected status {expected_status}, got {routed.get('status')}")
            continue
        expected_role = check.get("required_role")
        if expected_role and routed.get("required_role") != expected_role:
            errors.append(f"route check {target}: expected role {expected_role}, got {routed.get('required_role')}")
        expected_route_id = check.get("required_route_id")
        if expected_route_id and routed.get("concrete_part") != expected_route_id:
            errors.append(
                f"route check {target}: expected route {expected_route_id}, got {routed.get('concrete_part')}"
            )
        expected_reason = check.get("expected_why_blocked")
        if expected_reason and routed.get("why_blocked") != expected_reason:
            errors.append(f"route check {target}: expected why_blocked {expected_reason}, got {routed.get('why_blocked')}")

    if isinstance(policy, dict):
        role_required_for = policy.get("role_required_for")
        if isinstance(role_required_for, list):
            role_required_names = [item for item in role_required_for if isinstance(item, str)]
            expected_role_required_names = [
                part["name"]
                for part in catalog.get("platform_parts", [])
                if isinstance(part, dict)
                and isinstance(part.get("name"), str)
                and part.get("role_required") is True
            ]
            expected_role_required_set = set(expected_role_required_names)
            role_required_set = set(role_required_names)
            if len(role_required_names) != len(role_required_set):
                errors.append("mandatory_policy.role_required_for must not contain duplicates")
            missing_names = sorted(expected_role_required_set - role_required_set)
            extra_names = sorted(role_required_set - expected_role_required_set)
            if missing_names or extra_names:
                errors.append(
                    "mandatory_policy.role_required_for parity mismatch: "
                    f"missing={missing_names} extra={extra_names}"
                )

    _validate_no_seller_bound_core_defaults(catalog, errors)
    _validate_product_apps_monorepo_catalog(catalog, errors)

    if isinstance(roles, list):
        for role in roles:
            if not isinstance(role, dict):
                continue
            role_name = role.get("name")
            agent_file = role.get("agent_file")
            if not isinstance(role_name, str) or not isinstance(agent_file, str):
                continue
            agent_path = plugin_root / agent_file
            if not agent_path.is_file():
                continue
            routed = route_target(catalog, str(agent_path.resolve()), plugin_root=plugin_root)
            if routed.get("status") != "matched":
                errors.append(
                    f"role agent_file must route to a matched concrete part: "
                    f"{agent_file} -> {routed.get('status')}:{routed.get('why_blocked')}"
                )

    return errors


def _derive_validation_block_reason(route_packet: dict[str, Any], validation_errors: list[str]) -> str:
    if route_packet.get("status") == "ROLE_COVERAGE_BLOCKER":
        return str(route_packet.get("why_blocked"))
    joined = "\n".join(validation_errors)
    if "ambiguous" in joined:
        return "ambiguous_owner"
    if (
        "must point to a specialist" in joined
        or "must point to a helper or specialist execution_class" in joined
        or "execution_class" in joined
        or "primary_eligible" in joined
        or "part_kind" in joined
    ):
        return "invalid_broad_role"
    if "required_role not found" in joined or "agent_file missing" in joined or "missing fields" in joined:
        return "missing_role"
    return "invalid_broad_role"


def audit_target(catalog: dict[str, Any], target: str, *, plugin_root: Path = PLUGIN_ROOT) -> dict[str, Any]:
    route_packet = route_target(catalog, target, plugin_root=plugin_root)
    validation_errors = validate_catalog(catalog, plugin_root=plugin_root)
    audit_policy = catalog.get("mandatory_policy", {}).get("independent_control_audit", {})
    audit_packet = {
        "auditor_role": audit_policy.get("auditor_role", "bears-platform-role-governor"),
        "attached_reviewers": audit_policy.get("reviewer_roles", []),
        "checks": audit_policy.get(
            "must_prove",
            [
                "catalog validation passed",
                "exactly one primary specialist or helper role selected",
                "supporting roles are reviewer-only and do not replace the primary role",
                "implementation handoff is blocked until validation passes",
            ],
        ),
    }

    if route_packet.get("status") == "ROLE_COVERAGE_BLOCKER":
        route_packet["implementation_handoff_allowed"] = False
        route_packet["independent_control_audit"] = audit_packet
        if validation_errors:
            route_packet["validation_errors"] = validation_errors
        return route_packet

    if validation_errors:
        blocked = _build_blocker(
            target=target,
            reason=_derive_validation_block_reason(route_packet, validation_errors),
            catalog=catalog,
            matched_part=_part_map(catalog).get(route_packet["concrete_part"]),
            matched_role=_role_map(catalog).get(route_packet["primary_role"]),
            validation_errors=validation_errors,
        )
        blocked["implementation_handoff_allowed"] = False
        blocked["independent_control_audit"] = audit_packet
        return blocked

    route_packet["implementation_handoff_allowed"] = True
    route_packet["independent_control_audit"] = audit_packet
    return route_packet


def role_development_plan(catalog: dict[str, Any], target: str, *, plugin_root: Path = PLUGIN_ROOT) -> dict[str, Any]:
    route_packet = route_target(catalog, target, plugin_root=plugin_root)
    policy = catalog.get("mandatory_policy", {}) if isinstance(catalog.get("mandatory_policy"), dict) else {}
    role_development = _policy_role_development(policy, target=target)

    if route_packet.get("status") == "matched":
        return {
            "status": "pass",
            "lane": ROLE_DEVELOPMENT_LANE,
            "target": target,
            "action": "noop",
            "reason": "exact_primary_role_already_selected",
            "implementation_handoff_allowed": True,
            "role_development": _policy_role_development(policy),
            "route": route_packet,
        }

    owner_conflict = route_packet.get("why_blocked") == "ambiguous_owner"
    if owner_conflict:
        status = "terminal_blocker"
        action = "stop_for_owner_conflict"
    elif route_packet.get("why_blocked") == "parent_only":
        status = "needs_exact_target"
        action = "decompose_to_exact_write_scope"
    else:
        status = "ready"
        action = "spawn_role_development_worker"

    return {
        "status": status,
        "lane": ROLE_DEVELOPMENT_LANE,
        "target": target,
        "action": action,
        "reason": route_packet.get("why_blocked"),
        "implementation_handoff_allowed": False,
        "terminal_blocker": owner_conflict,
        "role_development": role_development,
        "route": route_packet,
    }


def render_packet(packet: dict[str, Any]) -> str:
    if packet.get("status") == "matched":
        lines = [
            "status: matched",
            f"concrete_part: {packet['concrete_part']}",
            f"primary_role: {packet['primary_role']}",
            f"primary_execution_class: {packet['primary_execution_class']}",
            f"allowed_write_boundary: {packet['allowed_write_boundary']}",
            f"trust_boundary: {packet['trust_boundary']}",
            "supporting_roles:",
        ]
        supporting_roles = packet.get("supporting_roles", [])
        if supporting_roles:
            lines.extend(f"  - {role}" for role in supporting_roles)
        else:
            lines.append("  - none")
        lines.append("validation_required_inventory:")
        lines.extend(f"  - {item}" for item in packet.get("validation_required", []))
        lines.append("validation_required_agent_local:")
        local_validations = packet.get("validation_required_agent_local", [])
        if local_validations:
            lines.extend(f"  - {item}" for item in local_validations)
        else:
            lines.append("  - none")
        lines.append("validation_required_ci_owned:")
        ci_validations = packet.get("validation_required_ci_owned", [])
        if ci_validations:
            lines.extend(f"  - {item}" for item in ci_validations)
        else:
            lines.append("  - none")
        lines.append(
            "manual_execution_requires_operator_approval: "
            f"{str(packet.get('manual_execution_requires_operator_approval', False)).lower()}"
        )
        lines.append(f"validation_execution_policy: {packet.get('validation_execution_policy', VALIDATION_EXECUTION_POLICY)}")
        if "reviewer_triggers" in packet:
            lines.append("reviewer_triggers:")
            triggers = packet.get("reviewer_triggers", [])
            if triggers:
                lines.extend(f"  - {item}" for item in triggers)
            else:
                lines.append("  - none")
        if "implementation_handoff_allowed" in packet:
            lines.append(f"implementation_handoff_allowed: {str(packet['implementation_handoff_allowed']).lower()}")
        if "independent_control_audit" in packet:
            audit = packet["independent_control_audit"]
            lines.append("independent_control_audit:")
            lines.append(f"  auditor_role: {audit['auditor_role']}")
            lines.append("  attached_reviewers:")
            reviewers = audit.get("attached_reviewers", [])
            if reviewers:
                lines.extend(f"    - {item}" for item in reviewers)
            else:
                lines.append("    - none")
            lines.append("  checks:")
            for item in audit.get("checks", []):
                lines.append(f"    - {item}")
        return "\n".join(lines)

    lines = [
        "status: ROLE_COVERAGE_BLOCKER",
        f"missing_part: {packet['missing_part']}",
        f"why_blocked: {packet['why_blocked']}",
    ]
    if "matched_platform_part" in packet:
        lines.append(f"matched_platform_part: {packet['matched_platform_part']}")
    if "matched_part_kind" in packet:
        lines.append(f"matched_part_kind: {packet['matched_part_kind']}")
    if "matched_role" in packet:
        lines.append(f"matched_role: {packet['matched_role']}")
    if "matched_execution_class" in packet:
        lines.append(f"matched_execution_class: {packet['matched_execution_class']}")
    lines.append("evidence_checked:")
    lines.extend(f"  - {item}" for item in packet["evidence_checked"])
    lines.append("blocked_edits:")
    lines.extend(f"  - {item}" for item in packet["blocked_edits"])
    lines.append("allowed_next_actions:")
    lines.extend(f"  - {item}" for item in packet["allowed_next_actions"])
    if "role_development" in packet:
        role_development = packet["role_development"]
        lines.append("role_development:")
        lines.append(f"  lane: {role_development['lane']}")
        lines.append(f"  owner_role: {role_development['owner_role']}")
        lines.append(f"  max_attempts: {role_development['max_attempts']}")
        lines.append("  allowed_write_scope:")
        lines.extend(f"    - {item}" for item in role_development["allowed_write_scope"])
        lines.append("  required_validations:")
        lines.extend(f"    - {item}" for item in role_development["required_validations"])
        lines.append("  rerun_commands:")
        lines.extend(f"    - {item}" for item in role_development["rerun_commands"])
        lines.append("  terminal_blocker_conditions:")
        lines.extend(f"    - {item}" for item in role_development["terminal_blocker_conditions"])
        lines.append(f"  unsafe_implementation_policy: {role_development['unsafe_implementation_policy']}")
    lines.append("required_role_shape:")
    role_shape = packet["required_role_shape"]
    lines.append(f"  name: {role_shape['name']}")
    lines.append(f"  execution_class: {role_shape['execution_class']}")
    lines.append(f"  concrete_scope: {role_shape['concrete_scope']}")
    lines.append(f"  allowed_write_boundary: {role_shape['allowed_write_boundary']}")
    lines.append(f"  trust_boundary: {role_shape['trust_boundary']}")
    lines.append("  required_validations:")
    for item in role_shape["required_validations"]:
        lines.append(f"    - {item}")
    lines.append(f"decomposition_required: {str(packet['decomposition_required']).lower()}")
    if "implementation_handoff_allowed" in packet:
        lines.append(f"implementation_handoff_allowed: {str(packet['implementation_handoff_allowed']).lower()}")
    if "validation_errors" in packet:
        lines.append("validation_errors:")
        lines.extend(f"  - {item}" for item in packet["validation_errors"])
    if "independent_control_audit" in packet:
        audit = packet["independent_control_audit"]
        lines.append("independent_control_audit:")
        lines.append(f"  auditor_role: {audit['auditor_role']}")
        lines.append("  attached_reviewers:")
        reviewers = audit.get("attached_reviewers", [])
        if reviewers:
            lines.extend(f"    - {item}" for item in reviewers)
        else:
            lines.append("    - none")
        lines.append("  checks:")
        for item in audit.get("checks", []):
            lines.append(f"    - {item}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Role catalog path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Validate plugin-owned role catalog and role TOMLs")
    route = sub.add_parser("route", help="Route a target to the required Bears plugin role")
    route.add_argument("target")
    audit = sub.add_parser("audit", help="Validate and audit whether implementation handoff is allowed")
    audit.add_argument("target")
    role_development = sub.add_parser(
        "role-development-plan",
        help="Emit a deterministic role-development plan for missing role coverage",
    )
    role_development.add_argument("target")
    role_development.add_argument("--json", action="store_true", required=True)
    summary = sub.add_parser("summary", help="Print compact role summary")
    summary.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_cli_json(Path(args.catalog), label="catalog")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        errors = validate_catalog(catalog)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"platform role catalog ok: {args.catalog}")
        return 0

    if args.command == "route":
        packet = route_target(catalog, args.target)
        print(render_packet(packet))
        return 0 if packet.get("status") == "matched" else 2

    if args.command == "audit":
        packet = audit_target(catalog, args.target)
        print(render_packet(packet))
        return 0 if packet.get("implementation_handoff_allowed") else 2

    if args.command == "role-development-plan":
        packet = role_development_plan(catalog, args.target)
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0

    if args.command == "summary":
        payload = {
            "roles": [
                {
                    "name": role["name"],
                    "role_kind": role.get("role_kind"),
                    "primary_eligible": role.get("primary_eligible"),
                }
                for role in catalog.get("roles", [])
                if isinstance(role, dict) and "name" in role
            ],
            "platform_parts": [
                {
                    "name": part["name"],
                    "part_kind": part.get("part_kind"),
                    "required_role": part.get("required_role"),
                }
                for part in catalog.get("platform_parts", [])
                if isinstance(part, dict) and "name" in part
            ],
            "workflow_routes": catalog.get("workflow_routes", []),
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Roles:")
            for role in payload["roles"]:
                print(f"- {role['name']} ({role['role_kind']})")
            print("Platform parts:")
            for part in payload["platform_parts"]:
                print(f"- {part['name']} ({part['part_kind']}) -> {part['required_role']}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
