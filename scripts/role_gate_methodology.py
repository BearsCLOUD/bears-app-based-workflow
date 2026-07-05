#!/usr/bin/env python3
"""Validate Bears role-gate methodology and catalog alignment."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METHODOLOGY = PLUGIN_ROOT / "assets/catalog/role-gate-methodology.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
EXPECTED_SCHEMA = "bears-role-gate-methodology.v1"
EXPECTED_OWNER = "bears"
STALE_ROLE_GATE_SOURCE_STATUS = "STALE_ROLE_GATE_SOURCE"
SOURCE_FRESHNESS_PACKET_INVALID_STATUS = "ROLE_GATE_SOURCE_FRESHNESS_PACKET_INVALID"
BLOCKER_REASONS = [
    "unknown",
    "unmapped",
    "parent_only",
    "missing_role",
    "invalid_broad_role",
    "ambiguous_owner",
]
BLOCKED_EDITS = [
    "product implementation",
    "platform implementation",
    "runtime/deploy/migration/integration edits",
]
ALLOWED_NEXT_ACTIONS = [
    "create/refine primary role artifact",
    "add exact catalog mapping",
    "add/update validators",
    "add forward-test evidence",
]
SOURCE_FRESHNESS_SHA_FIELDS = [
    "current_plugin_checkout_sha",
    "root_gitlink_sha",
    "root_origin_main_plugin_gitlink_sha",
]
SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS = [
    "sync plugin checkout",
    "switch to a clean root-sync worktree",
]
SOURCE_FRESHNESS_PACKET_FIELDS = [
    "status",
    "requested_target",
    *SOURCE_FRESHNESS_SHA_FIELDS,
    "requested_mapping_exists_in_newer_merged_plugin_state",
    "safe_next_action",
    "exact_role_policy",
]
REQUIRED_PACKET_FIELDS = [
    "status",
    "missing_part",
    "why_blocked",
    "evidence_checked",
    "blocked_edits",
    "allowed_next_actions",
    "role_development",
    "required_role_shape",
    "decomposition_required",
]
REQUIRED_ROLE_DEVELOPMENT_FIELDS = [
    "lane",
    "owner_role",
    "max_attempts",
    "allowed_write_scope",
    "required_validations",
    "rerun_commands",
    "terminal_blocker_conditions",
    "unsafe_implementation_policy",
]
ROLE_DEVELOPMENT_REQUIRED_VALIDATIONS = [
    "python3 scripts/subagents_roles.py validate",
    "python3 scripts/role_gate_methodology.py validate",
    "python3 -m unittest tests/test_subagents_roles.py tests/test_role_gate_methodology.py",
]
ROLE_DEVELOPMENT_RERUN_COMMANDS = [
    "python3 scripts/subagents_roles.py route <target>",
    "python3 scripts/subagents_roles.py audit <target>",
    "python3 scripts/subagents_roles.py role-development-plan <target> --json",
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
REQUIRED_ROLE_SHAPE_FIELDS = [
    "name",
    "concrete_scope",
    "allowed_write_boundary",
    "trust_boundary",
    "required_validations",
]
REQUIRED_METHODOLOGY_ITEMS = [
    ("concrete_part", ("smallest explicit", "write scope")),
    ("valid_specialist_role", ("role_kind=specialist", "primary_eligible=true")),
    ("parent_role_insufficient", ("classification-only", "cannot authorize")),
    ("broad_role_requires_decomposition", ("invalid_broad_role", "decomposition")),
    (
        "choose_exactly_one_primary_role",
        ("exact aliases", "declared write roots", "longest exact concrete match", "ambiguous_owner"),
    ),
    ("attach_supporting_security_qa_roles", ("after the primary role is selected", "reviewer-only")),
    ("exact_blocker_packet", ("ROLE_COVERAGE_BLOCKER", "required_role_shape", "decomposition_required")),
    (
        "auto_role_development",
        ("role-development", "bears-subagents-roles-governor", "role-development-plan", "implementation_handoff_allowed=false"),
    ),
    ("mandatory_validators", ("validator", "test")),
    ("forward_tests", ("child-under-group", "alias/path drift", "one-primary-role", "broad fallback")),
    (
        "independent_control_audit_evidence",
        ("audit", "implementation handoff", "no product/runtime/deploy edits"),
    ),
    (
        "source_freshness_preflight",
        ("STALE_ROLE_GATE_SOURCE", "current plugin checkout SHA", "root gitlink SHA", "root origin/main plugin gitlink SHA"),
    ),
]
REQUIRED_DEFINITIONS = {
    "concrete_part",
    "valid_specialist_role",
    "parent_role_insufficient",
    "broad_role_invalid",
    "primary_role",
    "supporting_roles",
    "implementation_handoff",
}
REQUIRED_VALIDATOR_IDS = {
    "known_concrete_part_one_primary",
    "unknown_or_unmapped_blocks",
    "parent_group_only_rejected",
    "overly_broad_role_rejected",
    "decomposition_required_for_broad_scope",
    "supporting_roles_attach_on_risk",
    "handoff_blocked_before_validation",
    "stale_source_distinguished_from_missing_coverage",
    "auto_role_development_plan_ready",
}
REQUIRED_FORWARD_TEST_IDS = {
    "new_child_under_known_group_blocks",
    "alias_path_drift_does_not_widen",
    "catalog_growth_keeps_one_primary",
    "broad_fallback_matching_cannot_reappear",
    "deploy_core_has_exact_specialist",
    "session_runtime_has_exact_specialist",
    "missing_exact_target_emits_role_development",
}
REQUIRED_AUDIT_CONFIRMATIONS = {
    "methodology is generic, not domain-specific",
    "blocker rule is unambiguous",
    "broad roles are invalidated",
    "parent-only coverage cannot authorize edits",
    "validators/tests/forward-tests pass",
    "no product/runtime/deploy edits happened before role coverage",
    "source freshness preflight ran before blocker closeout",
    "stale role-gate source is reported as STALE_ROLE_GATE_SOURCE with safe next action",
}
NARROW_BUGFIX_SKIP_REQUIRED_FIELDS = [
    "exact_file_scope",
    "no_boundary_change",
    "no_runtime_change",
    "no_deploy_change",
    "no_restricted_data_change",
    "no_public_behavior_change",
    "no_contract_or_proof_schema_change",
]
CONTRACT_SHAPE_MARKERS = (
    "contract field",
    "contract test",
    "docs/reference/packets/",
    "evidence shape",
    "evidence-shape",
    "packet field",
    "proof field",
    "runbook evidence",
    "schema field",
    "validator field",
)
VALIDATION_COMMAND_POLICY_REQUIRED_FIELDS = {
    "working_directory",
    "canonical_unittest_command",
    "blocked_unittest_patterns",
    "failure_classification_rule",
    "handoff_rule",
}
REQUIRED_CONTROL_AUDIT_EVIDENCE_FIELDS = [
    "required_document",
    "must_record",
]
REQUIRED_CONTROL_AUDIT_RECORDS = {
    "selected concrete part and exactly one primary specialist or helper role",
    "exact blocker reasons covered by validators and forward tests",
    "allowed-before-coverage versus forbidden-before-coverage write boundary",
    "validation commands and results",
    "no product/runtime/deploy edits before role coverage",
    "source freshness preflight SHAs before blocker closeout",
    "STALE_ROLE_GATE_SOURCE versus true ROLE_COVERAGE_BLOCKER classification",
}
SECRET_FIELD_MARKERS = ("token", "secret", "password", "private_key", "api_key", "bearer", "authorization")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

DESIGN_ARTIFACT_PATH = "README.md#issue-22-design-artifact-contract"
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
REQUIRED_IMPLEMENTATION_PACKET_FIELDS = {
    "change_type",
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


def load_json(path: Path, *, label: str = "json document") -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"{label} not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read {label}: {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in {label}: {path}: {exc.msg} (line {exc.lineno} column {exc.colno})"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be an object: {path}")
    return data


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _require_object(value: Any, path: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return None
    return value


def _require_non_empty_string(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def _iter_text(value: Any, path: str = "root") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        found: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            found.extend(_iter_text(item, f"{path}[{index}]"))
        return found
    if isinstance(value, dict):
        found: list[tuple[str, str]] = []
        for key, item in value.items():
            found.extend(_iter_text(item, f"{path}.{key}"))
        return found
    return []


def _as_string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


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
        narrow_skip = skip_policy.get("narrow_bugfix_skip")
        if isinstance(narrow_skip, dict):
            fields = _string_list(narrow_skip.get("required_fields"))
            if fields != NARROW_BUGFIX_SKIP_REQUIRED_FIELDS:
                errors.append(f"{path}.skip_policy.narrow_bugfix_skip.required_fields must match contract guard fields")
            use = narrow_skip.get("use")
            for fragment in ("contract/proof/schema", "non-interface rationale", "route-specific checklist"):
                if not isinstance(use, str) or fragment not in use:
                    errors.append(f"{path}.skip_policy.narrow_bugfix_skip.use must include {fragment!r}")
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


def _packet_indicates_contract_shape_change(packet: dict[str, Any]) -> bool:
    for field in ("affected_artifacts", "validator_impact", "documentation_impact", "test_plan"):
        for _, text in _iter_text(packet.get(field), field):
            normalized = text.casefold().replace("_", " ").replace("-", " ")
            raw = text.casefold().replace("\\", "/")
            if any(marker in normalized or marker in raw for marker in CONTRACT_SHAPE_MARKERS):
                return True
            if "schema" in normalized and ("field" in normalized or "packet" in normalized):
                return True
            if "proof" in normalized and ("field" in normalized or "packet" in normalized):
                return True
    return False


def _design_skip_errors(skip: Any, packet: dict[str, Any]) -> list[str]:
    if not isinstance(skip, dict):
        return ["implementation packet design_skip missing required design"]
    skip_type = skip.get("type")
    if skip_type == "approved_skip":
        missing = [
            field
            for field in ("approved_by", "approval_reference", "reason")
            if not isinstance(skip.get(field), str) or not skip[field].strip()
        ]
        if missing:
            return ["approved_skip missing fields: " + ", ".join(missing)]
        return []
    if skip_type == "narrow_bugfix_skip":
        if not (isinstance(skip.get("exact_file_scope"), str) and skip["exact_file_scope"].strip()):
            return ["narrow_bugfix_skip.exact_file_scope must be a non-empty string"]
        boolean_fields = NARROW_BUGFIX_SKIP_REQUIRED_FIELDS[1:]
        missing_booleans = [field for field in boolean_fields if skip.get(field) is not True]
        contract_shape_change = _packet_indicates_contract_shape_change(packet)
        if contract_shape_change:
            rationale = skip.get("non_interface_contract_rationale")
            checklist_accepted = skip.get("route_specific_checklist_accepts_internal_only") is True
            if not (isinstance(rationale, str) and rationale.strip() and checklist_accepted):
                return [
                    "narrow_bugfix_skip for contract/proof/schema field changes requires Spec Kit or non-interface rationale accepted by route checklist"
                ]
            missing_booleans = [
                field for field in missing_booleans if field != "no_contract_or_proof_schema_change"
            ]
        if missing_booleans:
            return ["narrow_bugfix_skip missing true fields: " + ", ".join(missing_booleans)]
        return []
    return ["design_skip.type must be approved_skip or narrow_bugfix_skip"]


def _design_skip_valid(skip: Any, packet: dict[str, Any] | None = None) -> bool:
    return not _design_skip_errors(skip, packet or {})


def validate_validation_command_policy(policy: Any, path: str = "validation_command_policy") -> list[str]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return [f"{path} must be an object"]
    missing = sorted(VALIDATION_COMMAND_POLICY_REQUIRED_FIELDS - set(policy))
    if missing:
        errors.append(f"{path} missing fields: " + ", ".join(missing))
    if policy.get("working_directory") != "/srv/bears/plugins/bears":
        errors.append(f"{path}.working_directory must be /srv/bears/plugins/bears")
    canonical = policy.get("canonical_unittest_command")
    if not isinstance(canonical, str) or not canonical.strip():
        errors.append(f"{path}.canonical_unittest_command must be a non-empty string")
    else:
        if canonical != "python3 -m unittest tests/test_subagents_roles.py tests/test_role_gate_methodology.py":
            errors.append(f"{path}.canonical_unittest_command must use repo-relative test paths")
        if "/srv/bears/plugins/bears/tests/" in canonical:
            errors.append(f"{path}.canonical_unittest_command must not use absolute test paths")
    blocked = _string_list(policy.get("blocked_unittest_patterns"))
    if not blocked:
        errors.append(f"{path}.blocked_unittest_patterns must be a non-empty list")
    elif not any("/srv/bears/plugins/bears/tests/" in command for command in blocked):
        errors.append(f"{path}.blocked_unittest_patterns must include the absolute-path unittest form")
    failure_rule = policy.get("failure_classification_rule")
    if not isinstance(failure_rule, str) or "command_shape_failure" not in failure_rule or "test_assertion_failure" not in failure_rule:
        errors.append(f"{path}.failure_classification_rule must distinguish command_shape_failure and test_assertion_failure")
    handoff_rule = policy.get("handoff_rule")
    if not isinstance(handoff_rule, str) or "repo-relative" not in handoff_rule or "subagent handoffs" not in handoff_rule:
        errors.append(f"{path}.handoff_rule must require repo-relative unittest commands in subagent handoffs")
    return errors


def validate_implementation_packet(packet: Any, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["implementation packet must be an object"]
    missing_fields = sorted(REQUIRED_IMPLEMENTATION_PACKET_FIELDS - set(packet))
    if missing_fields:
        errors.append("implementation packet missing fields: " + ", ".join(missing_fields))
    change_type = packet.get("change_type")
    design_required = packet.get("design_required") is True or change_type in DESIGN_REQUIRED_CHANGE_TYPES
    if not design_required:
        return errors
    skip_errors = _design_skip_errors(packet.get("design_skip"), packet)
    if not skip_errors:
        return errors
    if packet.get("design_skip") is not None:
        errors.extend(skip_errors)
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


def _is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(GIT_SHA_RE.fullmatch(value))


def validate_source_freshness_preflight_contract(contract: Any, path: str = "source_freshness_preflight") -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"{path} must be an object"]
    if contract.get("status_on_stale_source") != STALE_ROLE_GATE_SOURCE_STATUS:
        errors.append(f"{path}.status_on_stale_source must be {STALE_ROLE_GATE_SOURCE_STATUS}")
    required_before = contract.get("required_before")
    if not isinstance(required_before, str) or "ROLE_COVERAGE_BLOCKER" not in required_before:
        errors.append(f"{path}.required_before must bind preflight before ROLE_COVERAGE_BLOCKER closeout")
    if _string_list(contract.get("required_sha_fields")) != SOURCE_FRESHNESS_SHA_FIELDS:
        errors.append(f"{path}.required_sha_fields must record the three canonical SHA fields")
    if _string_list(contract.get("stale_packet_fields")) != SOURCE_FRESHNESS_PACKET_FIELDS:
        errors.append(f"{path}.stale_packet_fields must match canonical stale-source packet fields")
    if _string_list(contract.get("safe_next_actions")) != SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS:
        errors.append(f"{path}.safe_next_actions must match canonical stale-source recovery actions")
    mapping_check = contract.get("mapping_check")
    if not isinstance(mapping_check, str) or "newer merged plugin state" not in mapping_check:
        errors.append(f"{path}.mapping_check must mention newer merged plugin state")
    exact_role_policy = contract.get("exact_role_policy")
    if not isinstance(exact_role_policy, str) or "generic role substitution" not in exact_role_policy or "forbidden" not in exact_role_policy:
        errors.append(f"{path}.exact_role_policy must forbid generic role substitution")
    return errors


def validate_source_freshness_packet(packet: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["source freshness packet must be an object"]
    if packet.get("status") != STALE_ROLE_GATE_SOURCE_STATUS:
        errors.append(f"source freshness packet status must be {STALE_ROLE_GATE_SOURCE_STATUS}")
    missing = [field for field in SOURCE_FRESHNESS_PACKET_FIELDS if field not in packet]
    if missing:
        errors.append("source freshness packet missing fields: " + ", ".join(missing))
    if not isinstance(packet.get("requested_target"), str) or not packet.get("requested_target", "").strip():
        errors.append("source freshness packet requested_target must be a non-empty string")
    for field in SOURCE_FRESHNESS_SHA_FIELDS:
        if field in packet and not _is_git_sha(packet.get(field)):
            errors.append(f"source freshness packet {field} must be a 40-character git SHA")
    if packet.get("requested_mapping_exists_in_newer_merged_plugin_state") is not True:
        errors.append("source freshness packet requested_mapping_exists_in_newer_merged_plugin_state must be true")
    if packet.get("safe_next_action") not in SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS:
        errors.append("source freshness packet safe_next_action must be a canonical safe next action")
    exact_role_policy = packet.get("exact_role_policy")
    if not isinstance(exact_role_policy, str) or "generic role substitution" not in exact_role_policy or "forbidden" not in exact_role_policy:
        errors.append("source freshness packet exact_role_policy must preserve exact-role policy")
    return errors


def classify_blocker_decision(route_packet: dict[str, Any], freshness_packet: dict[str, Any]) -> dict[str, Any]:
    if route_packet.get("status") != "ROLE_COVERAGE_BLOCKER":
        return route_packet
    if freshness_packet.get("requested_mapping_exists_in_newer_merged_plugin_state") is not True:
        return route_packet
    requested_target = (
        route_packet.get("missing_part")
        or route_packet.get("target")
        or freshness_packet.get("requested_target")
        or ""
    )
    source_packet_errors = validate_source_freshness_packet(freshness_packet)
    if source_packet_errors:
        return {
            "status": SOURCE_FRESHNESS_PACKET_INVALID_STATUS,
            "requested_target": requested_target,
            "validation_errors": source_packet_errors,
            "safe_next_action": freshness_packet.get("safe_next_action"),
            "allowed_safe_next_actions": SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS,
            "exact_role_policy": "Exact-role policy remains active; generic role substitution is forbidden.",
        }
    stale_packet = {
        "status": STALE_ROLE_GATE_SOURCE_STATUS,
        "requested_target": requested_target,
        "current_plugin_checkout_sha": freshness_packet.get("current_plugin_checkout_sha"),
        "root_gitlink_sha": freshness_packet.get("root_gitlink_sha"),
        "root_origin_main_plugin_gitlink_sha": freshness_packet.get("root_origin_main_plugin_gitlink_sha"),
        "requested_mapping_exists_in_newer_merged_plugin_state": True,
        "safe_next_action": freshness_packet.get("safe_next_action"),
        "exact_role_policy": "Exact-role policy remains active; generic role substitution is forbidden.",
    }
    packet_errors = validate_source_freshness_packet(stale_packet)
    if packet_errors:
        return {
            "status": SOURCE_FRESHNESS_PACKET_INVALID_STATUS,
            "requested_target": stale_packet["requested_target"],
            "validation_errors": packet_errors,
            "safe_next_action": freshness_packet.get("safe_next_action"),
            "allowed_safe_next_actions": SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS,
            "exact_role_policy": "Exact-role policy remains active; generic role substitution is forbidden.",
        }
    return stale_packet


def _run_git(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _gitlink_sha(root: Path, ref: str, submodule_path: str) -> str:
    line = _run_git(["ls-tree", ref, submodule_path], cwd=root)
    parts = line.split()
    if len(parts) < 3 or parts[0] != "160000" or not _is_git_sha(parts[2]):
        raise ValueError(f"cannot resolve gitlink SHA for {ref}:{submodule_path}")
    return parts[2]


def collect_source_freshness_packet(
    *,
    plugin_root: Path,
    workspace_root: Path,
    target: str,
    mapping_exists_in_newer_merged_plugin_state: bool,
    safe_next_action: str,
    root_main_ref: str = "origin/main",
    submodule_path: str = "plugins/bears",
) -> dict[str, Any]:
    return {
        "status": STALE_ROLE_GATE_SOURCE_STATUS if mapping_exists_in_newer_merged_plugin_state else "ROLE_GATE_SOURCE_FRESH",
        "requested_target": target,
        "current_plugin_checkout_sha": _run_git(["rev-parse", "HEAD"], cwd=plugin_root),
        "root_gitlink_sha": _gitlink_sha(workspace_root, "HEAD", submodule_path),
        "root_origin_main_plugin_gitlink_sha": _gitlink_sha(workspace_root, root_main_ref, submodule_path),
        "requested_mapping_exists_in_newer_merged_plugin_state": mapping_exists_in_newer_merged_plugin_state,
        "safe_next_action": safe_next_action,
        "exact_role_policy": "Exact-role policy remains active; generic role substitution is forbidden.",
    }



def validate_no_secret_like_text(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_text(payload):
        lower = text.casefold()
        if any(marker in lower for marker in SECRET_FIELD_MARKERS) and any(sep in text for sep in ("=", ":")):
            errors.append(f"{path}: must not include secret-like key/value material")
    return errors


def validate_methodology(methodology: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if methodology.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if methodology.get("owner_plugin") != EXPECTED_OWNER:
        errors.append(f"owner_plugin must be {EXPECTED_OWNER}")

    main_rule = methodology.get("main_rule")
    _require_non_empty_string(main_rule, "main_rule", errors)
    if isinstance(main_rule, str):
        for fragment in ("ROLE_COVERAGE_BLOCKER", "exactly one valid primary specialist or helper role", "same granularity"):
            if fragment not in main_rule:
                errors.append(f"main_rule must include {fragment!r}")

    definitions = _require_object(methodology.get("definitions"), "definitions", errors)
    if definitions is not None:
        missing = sorted(REQUIRED_DEFINITIONS - set(definitions))
        if missing:
            errors.append("definitions missing keys: " + ", ".join(missing))
        for key in REQUIRED_DEFINITIONS & set(definitions):
            _require_non_empty_string(definitions[key], f"definitions.{key}", errors)

    methodology_items = methodology.get("methodology_items")
    if not isinstance(methodology_items, list):
        errors.append("methodology_items must be a list")
    else:
        item_index = {
            item.get("id"): item
            for item in methodology_items
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        required_ids = [item_id for item_id, _ in REQUIRED_METHODOLOGY_ITEMS]
        seen_ids = [item.get("id") for item in methodology_items if isinstance(item, dict)]
        if seen_ids != required_ids:
            errors.append("methodology_items ids/order must match canonical methodology")
        for item_id, fragments in REQUIRED_METHODOLOGY_ITEMS:
            item = item_index.get(item_id)
            if not isinstance(item, dict):
                continue
            _require_non_empty_string(item.get("title"), f"methodology_items[{item_id}].title", errors)
            _require_non_empty_string(item.get("rule"), f"methodology_items[{item_id}].rule", errors)
            rule = item.get("rule")
            if isinstance(rule, str):
                for fragment in fragments:
                    if fragment not in rule:
                        errors.append(f"methodology_items[{item_id}].rule must include {fragment!r}")

    blocker_cases = methodology.get("blocker_cases")
    if not isinstance(blocker_cases, list):
        errors.append("blocker_cases must be a list")
    else:
        reasons = []
        for index, case in enumerate(blocker_cases):
            if not isinstance(case, dict):
                errors.append(f"blocker_cases[{index}] must be an object")
                continue
            if case.get("status") != "ROLE_COVERAGE_BLOCKER":
                errors.append(f"blocker_cases[{index}].status must be ROLE_COVERAGE_BLOCKER")
            reasons.append(case.get("why_blocked"))
            _require_non_empty_string(case.get("meaning"), f"blocker_cases[{index}].meaning", errors)
        if reasons != BLOCKER_REASONS:
            errors.append("blocker_cases why_blocked values must match canonical enum/order")

    packet = _require_object(methodology.get("blocker_packet"), "blocker_packet", errors)
    if packet is not None:
        if packet.get("status") != "ROLE_COVERAGE_BLOCKER":
            errors.append("blocker_packet.status must be ROLE_COVERAGE_BLOCKER")
        if _string_list(packet.get("required_fields")) != REQUIRED_PACKET_FIELDS:
            errors.append("blocker_packet.required_fields must match exact packet shape")
        if _string_list(packet.get("why_blocked_enum")) != BLOCKER_REASONS:
            errors.append("blocker_packet.why_blocked_enum must match canonical blocker reasons")
        if _string_list(packet.get("blocked_edits")) != BLOCKED_EDITS:
            errors.append("blocker_packet.blocked_edits must match canonical blocked edits")
        if _string_list(packet.get("allowed_next_actions")) != ALLOWED_NEXT_ACTIONS:
            errors.append("blocker_packet.allowed_next_actions must match canonical allowed actions")
        role_development = _require_object(packet.get("role_development"), "blocker_packet.role_development", errors)
        if role_development is not None:
            if _string_list(role_development.get("required_fields")) != REQUIRED_ROLE_DEVELOPMENT_FIELDS:
                errors.append("blocker_packet.role_development.required_fields must match canonical role-development shape")
            if role_development.get("lane") != "role-development":
                errors.append("blocker_packet.role_development.lane must be role-development")
            if role_development.get("owner_role") != "bears-subagents-roles-governor":
                errors.append("blocker_packet.role_development.owner_role must be bears-subagents-roles-governor")
            max_attempts = role_development.get("max_attempts")
            if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 3:
                errors.append("blocker_packet.role_development.max_attempts must be an integer from 1 to 3")
            if _string_list(role_development.get("required_validations")) != ROLE_DEVELOPMENT_REQUIRED_VALIDATIONS:
                errors.append("blocker_packet.role_development.required_validations must match canonical commands")
            if _string_list(role_development.get("rerun_commands")) != ROLE_DEVELOPMENT_RERUN_COMMANDS:
                errors.append("blocker_packet.role_development.rerun_commands must match canonical commands")
            if (
                _string_list(role_development.get("terminal_blocker_conditions"))
                != ROLE_DEVELOPMENT_TERMINAL_BLOCKER_CONDITIONS
            ):
                errors.append("blocker_packet.role_development.terminal_blocker_conditions must match canonical conditions")
            if role_development.get("unsafe_implementation_policy") != ROLE_DEVELOPMENT_UNSAFE_IMPLEMENTATION_POLICY:
                errors.append("blocker_packet.role_development.unsafe_implementation_policy must match canonical policy")
        if _string_list(packet.get("required_role_shape_fields")) != REQUIRED_ROLE_SHAPE_FIELDS:
            errors.append("blocker_packet.required_role_shape_fields must match required role shape")

    allowed = set(_string_list(methodology.get("allowed_before_coverage")))
    for required in (*ALLOWED_NEXT_ACTIONS, "governance docs"):
        if required not in allowed:
            errors.append(f"allowed_before_coverage missing {required!r}")
    forbidden = set(_string_list(methodology.get("forbidden_before_coverage")))
    for required in (
        "product code edits",
        "platform implementation edits",
        "runtime edits",
        "deploy edits",
        "migration edits",
        "integration behavior edits",
    ):
        if required not in forbidden:
            errors.append(f"forbidden_before_coverage missing {required!r}")

    validators = methodology.get("required_validators")
    if not isinstance(validators, list):
        errors.append("required_validators must be a list")
    else:
        ids = {item.get("id") for item in validators if isinstance(item, dict)}
        missing = sorted(REQUIRED_VALIDATOR_IDS - ids)
        if missing:
            errors.append("required_validators missing ids: " + ", ".join(missing))

    forward_tests = methodology.get("forward_tests")
    if not isinstance(forward_tests, list):
        errors.append("forward_tests must be a list")
    else:
        ids = {item.get("id") for item in forward_tests if isinstance(item, dict)}
        missing = sorted(REQUIRED_FORWARD_TEST_IDS - ids)
        if missing:
            errors.append("forward_tests missing ids: " + ", ".join(missing))

    audit = _require_object(methodology.get("independent_control_audit"), "independent_control_audit", errors)
    if audit is not None:
        if audit.get("required") is not True:
            errors.append("independent_control_audit.required must be true")
        if audit.get("auditor_role") != "bears-subagents-roles-governor":
            errors.append("independent_control_audit.auditor_role must be bears-subagents-roles-governor")
        confirmations = set(_string_list(audit.get("must_confirm")))
        missing = sorted(REQUIRED_AUDIT_CONFIRMATIONS - confirmations)
        if missing:
            errors.append("independent_control_audit.must_confirm missing: " + ", ".join(missing))

    control_audit_evidence = _require_object(
        methodology.get("control_audit_evidence"), "control_audit_evidence", errors
    )
    if control_audit_evidence is not None:
        for field in REQUIRED_CONTROL_AUDIT_EVIDENCE_FIELDS:
            if field not in control_audit_evidence:
                errors.append(f"control_audit_evidence missing {field}")
        required_document = control_audit_evidence.get("required_document")
        _require_non_empty_string(required_document, "control_audit_evidence.required_document", errors)
        if isinstance(required_document, str) and required_document.strip():
            evidence_path = PLUGIN_ROOT / required_document
            if not evidence_path.is_file():
                errors.append(f"control_audit_evidence.required_document missing: {required_document}")
        records = set(_string_list(control_audit_evidence.get("must_record")))
        missing_records = sorted(REQUIRED_CONTROL_AUDIT_RECORDS - records)
        if missing_records:
            errors.append("control_audit_evidence.must_record missing: " + ", ".join(missing_records))

    errors.extend(validate_design_artifact_contract(methodology.get("design_artifact_contract")))
    errors.extend(validate_validation_command_policy(methodology.get("validation_command_policy")))
    errors.extend(validate_source_freshness_preflight_contract(methodology.get("source_freshness_preflight")))
    errors.extend(validate_no_secret_like_text(methodology))
    return errors


def validate_catalog_alignment(methodology: dict[str, Any], role_catalog: dict[str, Any], *, plugin_root: Path = PLUGIN_ROOT) -> list[str]:
    errors: list[str] = []
    sys.path.insert(0, str(plugin_root / "scripts"))
    try:
        import platform_roles  # type: ignore
    finally:
        try:
            sys.path.remove(str(plugin_root / "scripts"))
        except ValueError:
            pass

    catalog_errors = platform_roles.validate_catalog(role_catalog, plugin_root=plugin_root)
    errors.extend(f"subagents roles catalog: {error}" for error in catalog_errors)

    policy = role_catalog.get("mandatory_policy")
    if isinstance(policy, dict):
        if policy.get("one_primary_role_required") is not True:
            errors.append("catalog mandatory_policy.one_primary_role_required must be true")
        if policy.get("parent_group_coverage_allowed") is not False:
            errors.append("catalog mandatory_policy.parent_group_coverage_allowed must be false")
        if policy.get("broad_fallback_matching_allowed") is not False:
            errors.append("catalog mandatory_policy.broad_fallback_matching_allowed must be false")
        if policy.get("blocker_reasons") != BLOCKER_REASONS:
            errors.append("catalog mandatory_policy.blocker_reasons must match methodology")
        if policy.get("blocked_edits") != BLOCKED_EDITS:
            errors.append("catalog mandatory_policy.blocked_edits must match methodology")
        if policy.get("allowed_next_actions") != ALLOWED_NEXT_ACTIONS:
            errors.append("catalog mandatory_policy.allowed_next_actions must match methodology")
        role_development = policy.get("role_development")
        packet_role_development = methodology.get("blocker_packet", {}).get("role_development")
        if not isinstance(role_development, dict):
            errors.append("catalog mandatory_policy.role_development must be an object")
        elif not isinstance(packet_role_development, dict):
            errors.append("methodology blocker_packet.role_development must be an object")
        else:
            for field in REQUIRED_ROLE_DEVELOPMENT_FIELDS:
                if field not in role_development:
                    errors.append(f"catalog mandatory_policy.role_development missing {field}")
            for field in ("lane", "owner_role", "max_attempts", "required_validations", "rerun_commands", "terminal_blocker_conditions", "unsafe_implementation_policy"):
                if role_development.get(field) != packet_role_development.get(field):
                    errors.append(f"catalog mandatory_policy.role_development.{field} must match methodology")
    else:
        errors.append("catalog mandatory_policy must be an object")

    for check in methodology.get("catalog_alignment_checks", []):
        if not isinstance(check, dict):
            errors.append("catalog_alignment_checks entries must be objects")
            continue
        target = check.get("target")
        if not isinstance(target, str) or not target:
            errors.append("catalog_alignment_checks target must be a non-empty string")
            continue
        packet = platform_roles.route_target(role_catalog, target, plugin_root=plugin_root)
        if packet.get("status") != check.get("expected_status"):
            errors.append(f"alignment {target}: expected status {check.get('expected_status')}, got {packet.get('status')}")
            continue
        if check.get("required_role") and packet.get("required_role") != check.get("required_role"):
            errors.append(f"alignment {target}: expected role {check.get('required_role')}, got {packet.get('required_role')}")
        if check.get("required_route_id") and packet.get("concrete_part") != check.get("required_route_id"):
            errors.append(
                f"alignment {target}: expected route {check.get('required_route_id')}, got {packet.get('concrete_part')}"
            )
        if check.get("why_blocked") and packet.get("why_blocked") != check.get("why_blocked"):
            errors.append(f"alignment {target}: expected why_blocked {check.get('why_blocked')}, got {packet.get('why_blocked')}")
        if packet.get("status") == "ROLE_COVERAGE_BLOCKER":
            for field in REQUIRED_PACKET_FIELDS:
                if field not in packet:
                    errors.append(f"alignment {target}: blocker packet missing {field}")
            role_development = packet.get("role_development")
            if not isinstance(role_development, dict):
                errors.append(f"alignment {target}: role_development must be an object")
            else:
                for field in REQUIRED_ROLE_DEVELOPMENT_FIELDS:
                    if field not in role_development:
                        errors.append(f"alignment {target}: role_development missing {field}")
            shape = packet.get("required_role_shape")
            if not isinstance(shape, dict):
                errors.append(f"alignment {target}: required_role_shape must be an object")
            else:
                for field in REQUIRED_ROLE_SHAPE_FIELDS:
                    if field not in shape:
                        errors.append(f"alignment {target}: required_role_shape missing {field}")

    return errors


def validate_all(methodology_path: Path, role_catalog_path: Path, *, plugin_root: Path = PLUGIN_ROOT) -> list[str]:
    methodology = load_json(methodology_path, label="role-gate methodology")
    role_catalog = load_json(role_catalog_path, label="role catalog")
    errors = validate_methodology(methodology)
    errors.extend(validate_catalog_alignment(methodology, role_catalog, plugin_root=plugin_root))
    return errors


def render_summary(methodology: dict[str, Any]) -> str:
    audit = methodology.get("independent_control_audit", {}) if isinstance(methodology.get("independent_control_audit"), dict) else {}
    lines = [
        f"schema: {methodology.get('schema')}",
        f"owner_plugin: {methodology.get('owner_plugin')}",
        "status: enforceable",
        f"blocker_reasons: {', '.join(BLOCKER_REASONS)}",
        f"auditor_role: {audit.get('auditor_role', 'bears-subagents-roles-governor')}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--methodology", default=str(DEFAULT_METHODOLOGY), help="role-gate methodology catalog path")
    parser.add_argument("--role-catalog", default=str(DEFAULT_ROLE_CATALOG), help="subagents roles catalog path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate methodology and catalog alignment")
    sub.add_parser("summary", help="print compact methodology summary")
    classify = sub.add_parser("classify-blocker", help="classify stale source versus true role coverage blocker")
    classify.add_argument("--route-packet", required=True, help="JSON route/blocker packet path")
    classify.add_argument("--source-freshness-packet", required=True, help="JSON source freshness packet path")
    freshness = sub.add_parser("source-freshness", help="emit local source freshness SHA packet")
    freshness.add_argument("--target", required=True, help="requested target path or alias")
    freshness.add_argument("--workspace-root", default="/srv/bears", help="workspace root containing the plugin gitlink")
    freshness.add_argument("--plugin-root", default=str(PLUGIN_ROOT), help="plugin checkout root")
    freshness.add_argument("--root-main-ref", default="origin/main", help="root ref used for merged gitlink truth")
    freshness.add_argument("--submodule-path", default="plugins/bears", help="plugin submodule path inside workspace root")
    freshness.add_argument(
        "--mapping-exists-in-newer-merged-plugin-state",
        action="store_true",
        help="set when the requested mapping exists only in newer merged plugin state",
    )
    freshness.add_argument(
        "--safe-next-action",
        choices=SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS,
        default=SOURCE_FRESHNESS_SAFE_NEXT_ACTIONS[0],
        help="operator-safe next action when stale source is detected",
    )
    args = parser.parse_args(argv)

    methodology_path = Path(args.methodology)
    role_catalog_path = Path(args.role_catalog)
    try:
        if args.command == "validate":
            errors = validate_all(methodology_path, role_catalog_path, plugin_root=PLUGIN_ROOT)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print(f"role gate methodology ok: {methodology_path}")
            return 0
        if args.command == "summary":
            print(render_summary(load_json(methodology_path, label="role-gate methodology")))
            return 0
        if args.command == "classify-blocker":
            route_packet = load_json(Path(args.route_packet), label="route packet")
            source_freshness_packet = load_json(Path(args.source_freshness_packet), label="source freshness packet")
            decision = classify_blocker_decision(route_packet, source_freshness_packet)
            print(json.dumps(decision, indent=2, sort_keys=True))
            if decision.get("status") == SOURCE_FRESHNESS_PACKET_INVALID_STATUS:
                return 1
            return 0
        if args.command == "source-freshness":
            packet = collect_source_freshness_packet(
                plugin_root=Path(args.plugin_root),
                workspace_root=Path(args.workspace_root),
                target=args.target,
                mapping_exists_in_newer_merged_plugin_state=args.mapping_exists_in_newer_merged_plugin_state,
                safe_next_action=args.safe_next_action,
                root_main_ref=args.root_main_ref,
                submodule_path=args.submodule_path,
            )
            print(json.dumps(packet, indent=2, sort_keys=True))
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
