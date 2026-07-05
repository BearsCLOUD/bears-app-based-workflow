#!/usr/bin/env python3
"""Validate Bears deterministic roadmap control catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets" / "catalog" / "roadmap-control.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets" / "catalog" / "platform-role-catalog.v1.json"
DEFAULT_SUBAGENT_POLICY = PLUGIN_ROOT / "assets" / "catalog" / "subagent-orchestration-policy.v1.json"
EXPECTED_SCHEMA = "bears-roadmap-control.v1"
EXPECTED_OWNER = "bears"
EXPECTED_ENTRYPOINT = "/goal"
EXPECTED_MAX_ACTIVE_SUBAGENTS = 100
EXPECTED_MAX_DEPTH = 3
REQUIRED_GOAL_FIELDS = {
    "goal_id",
    "roadmap_id",
    "objective",
    "operator_authorization",
    "active_spec_set",
    "validation_targets",
}
REQUIRED_SPEC_FIELDS = {
    "spec_id",
    "spec_path",
    "spec_snapshot_id",
    "spec_snapshot_digest",
    "tasks_snapshot_digest",
    "lane",
    "role",
    "scope",
    "validation_target",
}
REQUIRED_SCOPE_LOCK_FIELDS = {
    "roadmap_id",
    "roadmap_slice",
    "spec_id",
    "scope",
    "owner_worker_id",
    "repo_state",
    "validation_target",
}
REQUIRED_OPERATOR_ANSWERS = {"missing_data_answers", "drift_answers"}
REQUIRED_PRE_TASK_EVIDENCE = {
    "hook_id",
    "goal_id",
    "roadmap_id",
    "roadmap_slice",
    "spec_snapshot_id",
    "assignment_packet_id",
    "operator_missing_data_answers",
    "operator_drift_answers",
    "task_start_authorization",
}
REQUIRED_SPAWN_BLOCKERS = {
    "missing_data_answers_absent",
    "drift_answers_absent",
    "assignment_packet_absent",
    "task_start_authorization_absent",
    "spec_snapshot_absent_or_stale",
    "scope_lock_overlap",
}
EXPECTED_MAIN_AGENT_ALLOWED_ACTIONS = (
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
EXPECTED_MAIN_AGENT_FORBIDDEN_ACTIONS = (
    "file_read_as_content_collector",
    "file_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_mutation",
    "implementation_tool_use",
)
REQUIRED_EXPLICIT_CONTROLLER_ROLES = {
    "bears-deploy-platform-engineer",
    "bears-subagent-orchestration-engineer",
    "bears-subagents-roles-governor",
}
REQUIRED_AUDIT_FIELDS = {
    "audit_id",
    "fresh_worker_id",
    "context_policy=fresh_no_parent_context",
    "parent_context_allowed=false",
    "reuse_allowed=false",
    "resume_allowed=false",
    "validation_target",
    "audit_closeout_evidence",
}
REQUIRED_REUSE_BINDINGS = {
    "goal_id",
    "roadmap_id",
    "roadmap_slice",
    "spec_snapshot_id",
    "spec_snapshot_digest",
    "lane",
    "role",
    "scope_fingerprint",
    "repo_state",
    "validation_target",
}
REQUIRED_REUSE_COMPATIBILITY = {
    "goal_id_compatible",
    "roadmap_id_compatible",
    "roadmap_slice_compatible",
    "spec_snapshot_compatible",
    "lane_compatible",
    "role_compatible",
    "scope_compatible",
    "repo_state_compatible",
    "validation_target_compatible",
}
REQUIRED_VALIDATION_COMMANDS = {
    "python3 scripts/subagents_roles.py validate",
    "python3 scripts/roadmap_control.py validate",
    "python3 -m unittest tests/test_roadmap_control.py tests/test_subagents_roles.py",
}
EXPECTED_PHASE_MAP: dict[str, dict[str, Any]] = {
    "phase-1-route-and-baseline": {
        "lane": "audit",
        "role": "bears-workflow-overlay-platform-engineer",
        "scope": [
            "assets/catalog/roadmap-control.v1.json",
            "scripts/roadmap_control.py",
            "tests/test_roadmap_control.py",
            "docs/reference/roadmap-control.md",
        ],
    },
    "phase-2-catalog-and-validator": {
        "lane": "implementation",
        "role": "bears-workflow-overlay-platform-engineer",
        "scope": [
            "assets/catalog/roadmap-control.v1.json",
            "scripts/roadmap_control.py",
        ],
    },
    "phase-3-tests-and-reference": {
        "lane": "validation",
        "role": "bears-workflow-overlay-platform-engineer",
        "scope": [
            "tests/test_roadmap_control.py",
            "docs/reference/roadmap-control.md",
        ],
    },
    "phase-4-closeout": {
        "lane": "review",
        "role": "bears-workflow-overlay-platform-engineer",
        "scope": [
            "assets/catalog/roadmap-control.v1.json",
            "scripts/roadmap_control.py",
            "tests/test_roadmap_control.py",
            "docs/reference/roadmap-control.md",
        ],
    },
}
REQUIRED_PHASE_IDS = set(EXPECTED_PHASE_MAP)
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


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def load_cli_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}")
    return load_json(path)


def _require_object(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return False
    return True


def _require_bool(value: Any, path: str, errors: list[str], *, expected: bool = True) -> bool:
    if value is not expected:
        errors.append(f"{path} must be {str(expected).lower()}")
        return False
    return True


def _require_string_list(value: Any, path: str, errors: list[str], *, non_empty: bool = True) -> bool:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return False
    if non_empty and not value:
        errors.append(f"{path} must be non-empty")
    if not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{path} must contain only non-empty strings")
        return False
    return True


def _require_field_set(value: Any, path: str, required: set[str], errors: list[str]) -> None:
    if not _require_string_list(value, path, errors):
        return
    missing = sorted(required - set(value))
    if missing:
        errors.append(f"{path} missing fields: {', '.join(missing)}")


def _validate_exact_string_tokens(
    value: Any,
    path: str,
    *,
    expected: tuple[str, ...],
    errors: list[str],
) -> None:
    if not _require_string_list(value, path, errors):
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
    if not missing and not unexpected and not duplicates and actual != list(expected):
        errors.append(f"{path} must match exact ordered tokens")


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


def _validate_no_secret_like_text(payload: dict[str, Any], errors: list[str]) -> None:
    for path, text in _iter_text(payload):
        lower = text.casefold()
        if any(marker in lower for marker in SECRET_FIELD_MARKERS) and any(sep in text for sep in ("=", ":")):
            errors.append(f"{path}: must not include secret-like key/value material")


def _role_names(role_catalog: dict[str, Any]) -> set[str]:
    return {
        role.get("name")
        for role in role_catalog.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }


def _controller_roles_from_policy(policy: dict[str, Any]) -> set[str]:
    model = policy.get("orchestration_model", {})
    if not isinstance(model, dict):
        return set()
    controllers = model.get("delegation_controller_roles", [])
    return {
        controller.get("role")
        for controller in controllers
        if isinstance(controller, dict) and isinstance(controller.get("role"), str)
    }


def _roadmap_control_required_validations(role_catalog: dict[str, Any]) -> set[str]:
    for part in role_catalog.get("platform_parts", []):
        if isinstance(part, dict) and part.get("name") == "roadmap_control":
            validations = part.get("required_validations", [])
            if isinstance(validations, list) and all(isinstance(command, str) for command in validations):
                return set(validations)
            return set()
    return set()


def _validate_entrypoint(catalog: dict[str, Any], errors: list[str]) -> None:
    entrypoint = catalog.get("entrypoint")
    if not _require_object(entrypoint, "entrypoint", errors):
        return
    if entrypoint.get("required_command") != EXPECTED_ENTRYPOINT:
        errors.append("entrypoint.required_command must be /goal")
    _require_bool(entrypoint.get("roadmap_runs_only_through_goal"), "entrypoint.roadmap_runs_only_through_goal", errors)
    _require_field_set(entrypoint.get("required_goal_fields"), "entrypoint.required_goal_fields", REQUIRED_GOAL_FIELDS, errors)
    forbidden = entrypoint.get("forbidden_entrypoints")
    if _require_string_list(forbidden, "entrypoint.forbidden_entrypoints", errors):
        joined = " ".join(forbidden)
        for term in ("ad hoc", "subagent spawn before /goal"):
            if term not in joined:
                errors.append(f"entrypoint.forbidden_entrypoints must mention {term}")


def _validate_limits(catalog: dict[str, Any], errors: list[str]) -> None:
    limits = catalog.get("limits")
    if not _require_object(limits, "limits", errors):
        return
    if limits.get("max_active_subagents") != EXPECTED_MAX_ACTIVE_SUBAGENTS:
        errors.append("limits.max_active_subagents must be 100")
    if limits.get("max_depth") != EXPECTED_MAX_DEPTH:
        errors.append("limits.max_depth must be 3")


def _validate_multi_spec(catalog: dict[str, Any], errors: list[str]) -> None:
    multi = catalog.get("multi_spec_control")
    if not _require_object(multi, "multi_spec_control", errors):
        return
    _require_bool(multi.get("enabled"), "multi_spec_control.enabled", errors)
    _require_field_set(multi.get("required_spec_fields"), "multi_spec_control.required_spec_fields", REQUIRED_SPEC_FIELDS, errors)
    _require_field_set(multi.get("scope_lock_fields"), "multi_spec_control.scope_lock_fields", REQUIRED_SCOPE_LOCK_FIELDS, errors)
    rules = multi.get("concurrency_rules")
    if not isinstance(rules, list) or not rules:
        errors.append("multi_spec_control.concurrency_rules must be a non-empty list")
        return
    joined = " ".join(rule.get("rule", "") for rule in rules if isinstance(rule, dict))
    for term in ("Multiple Spec Kit specs", "non-overlapping write scope locks", "snapshot drift"):
        if term not in joined:
            errors.append(f"multi_spec_control.concurrency_rules must mention {term}")


def _validate_pre_task_hook(catalog: dict[str, Any], errors: list[str]) -> None:
    hook = catalog.get("pre_task_hook")
    if not _require_object(hook, "pre_task_hook", errors):
        return
    _require_bool(hook.get("required"), "pre_task_hook.required", errors)
    _require_bool(hook.get("blocks_worker_spawn_until_answers"), "pre_task_hook.blocks_worker_spawn_until_answers", errors)
    _require_field_set(
        hook.get("operator_answers_required_before_spawn"),
        "pre_task_hook.operator_answers_required_before_spawn",
        REQUIRED_OPERATOR_ANSWERS,
        errors,
    )
    _require_field_set(hook.get("required_evidence_fields"), "pre_task_hook.required_evidence_fields", REQUIRED_PRE_TASK_EVIDENCE, errors)
    _require_field_set(hook.get("spawn_blockers"), "pre_task_hook.spawn_blockers", REQUIRED_SPAWN_BLOCKERS, errors)
    runs_before = hook.get("runs_before")
    _require_field_set(runs_before, "pre_task_hook.runs_before", {"spawn", "resume", "reuse", "manage", "close"}, errors)


def _validate_main_agent_policy(catalog: dict[str, Any], errors: list[str]) -> None:
    policy = catalog.get("main_agent_policy")
    if not _require_object(policy, "main_agent_policy", errors):
        return
    if policy.get("mode") != "orchestration_only":
        errors.append("main_agent_policy.mode must be orchestration_only")
    _validate_exact_string_tokens(
        policy.get("allowed_actions"),
        "main_agent_policy.allowed_actions",
        expected=EXPECTED_MAIN_AGENT_ALLOWED_ACTIONS,
        errors=errors,
    )
    _validate_exact_string_tokens(
        policy.get("forbidden_actions"),
        "main_agent_policy.forbidden_actions",
        expected=EXPECTED_MAIN_AGENT_FORBIDDEN_ACTIONS,
        errors=errors,
    )


def _validate_orchestrator_control(
    catalog: dict[str, Any],
    role_catalog: dict[str, Any],
    subagent_policy: dict[str, Any],
    errors: list[str],
) -> None:
    control = catalog.get("orchestrator_control")
    if not _require_object(control, "orchestrator_control", errors):
        return
    _require_bool(control.get("multiple_orchestrators_allowed"), "orchestrator_control.multiple_orchestrators_allowed", errors)
    _require_bool(
        control.get("allowed_only_for_explicit_controller_roles"),
        "orchestrator_control.allowed_only_for_explicit_controller_roles",
        errors,
    )
    roles = control.get("explicit_controller_roles")
    _require_field_set(roles, "orchestrator_control.explicit_controller_roles", REQUIRED_EXPLICIT_CONTROLLER_ROLES, errors)
    if isinstance(roles, list):
        role_set = set(roles)
        unknown_catalog_roles = sorted(role_set - _role_names(role_catalog))
        if unknown_catalog_roles:
            errors.append("orchestrator_control.explicit_controller_roles unknown in role catalog: " + ", ".join(unknown_catalog_roles))
        unknown_policy_roles = sorted(role_set - _controller_roles_from_policy(subagent_policy))
        if unknown_policy_roles:
            errors.append("orchestrator_control.explicit_controller_roles unknown in subagent policy: " + ", ".join(unknown_policy_roles))
    rules = control.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("orchestrator_control.rules must be a non-empty list")
        return
    joined = " ".join(rule.get("rule", "") for rule in rules if isinstance(rule, dict))
    for term in ("Only explicit controller roles", "pre-task hook", "active-count", "close evidence"):
        if term not in joined:
            errors.append(f"orchestrator_control.rules must mention {term}")


def _validate_audit_policy(catalog: dict[str, Any], errors: list[str]) -> None:
    policy = catalog.get("audit_policy")
    if not _require_object(policy, "audit_policy", errors):
        return
    _require_bool(policy.get("fresh_subagent_required_every_audit"), "audit_policy.fresh_subagent_required_every_audit", errors)
    if policy.get("parent_context_allowed") is not False:
        errors.append("audit_policy.parent_context_allowed must be false")
    if policy.get("reuse_allowed") is not False:
        errors.append("audit_policy.reuse_allowed must be false")
    if policy.get("resume_allowed") is not False:
        errors.append("audit_policy.resume_allowed must be false")
    if policy.get("context_policy") != "fresh_no_parent_context":
        errors.append("audit_policy.context_policy must be fresh_no_parent_context")
    if policy.get("context_policy_rule") != "context_policy = fresh_no_parent_context":
        errors.append("audit_policy.context_policy_rule must be context_policy = fresh_no_parent_context")
    _require_field_set(policy.get("required_audit_fields"), "audit_policy.required_audit_fields", REQUIRED_AUDIT_FIELDS, errors)


def _validate_session_reuse(catalog: dict[str, Any], errors: list[str]) -> None:
    reuse = catalog.get("session_reuse")
    if not _require_object(reuse, "session_reuse", errors):
        return
    _require_bool(reuse.get("allowed"), "session_reuse.allowed", errors)
    if reuse.get("reuse_key_algorithm") != "sha256-json-v1":
        errors.append("session_reuse.reuse_key_algorithm must be sha256-json-v1")
    _require_field_set(reuse.get("required_binding_fields"), "session_reuse.required_binding_fields", REQUIRED_REUSE_BINDINGS, errors)
    _require_field_set(reuse.get("compatibility_fields"), "session_reuse.compatibility_fields", REQUIRED_REUSE_COMPATIBILITY, errors)
    rule = reuse.get("rule")
    if not isinstance(rule, str):
        errors.append("session_reuse.rule must be a string")
        return
    for term in ("goal", "slice", "spec snapshot", "lane", "role", "scope", "repo state", "validation target", "Audit workers never reuse"):
        if term not in rule:
            errors.append(f"session_reuse.rule must mention {term}")


def _validate_objective_roadmap(catalog: dict[str, Any], errors: list[str]) -> None:
    roadmap = catalog.get("roadmap_for_this_objective")
    if not _require_object(roadmap, "roadmap_for_this_objective", errors):
        return
    for field in ("goal_id", "roadmap_id", "objective"):
        if not isinstance(roadmap.get(field), str) or not roadmap[field].strip():
            errors.append(f"roadmap_for_this_objective.{field} must be a non-empty string")
    phases = roadmap.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("roadmap_for_this_objective.phases must be a non-empty list")
        return
    phase_ids = {phase.get("id") for phase in phases if isinstance(phase, dict)}
    missing = sorted(REQUIRED_PHASE_IDS - phase_ids)
    if missing:
        errors.append("roadmap_for_this_objective.phases missing: " + ", ".join(missing))
    extra = sorted(phase_id for phase_id in phase_ids - REQUIRED_PHASE_IDS if isinstance(phase_id, str))
    if extra:
        errors.append("roadmap_for_this_objective.phases has unexpected phases: " + ", ".join(extra))
    commands: set[str] = set()
    seen_phase_ids: set[str] = set()
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"roadmap_for_this_objective.phases[{index}] must be an object")
            continue
        phase_id = phase.get("id")
        if isinstance(phase_id, str):
            if phase_id in seen_phase_ids:
                errors.append(f"roadmap_for_this_objective.phases duplicate phase id: {phase_id}")
            seen_phase_ids.add(phase_id)
        for field in ("id", "lane", "role"):
            if not isinstance(phase.get(field), str) or not phase[field].strip():
                errors.append(f"roadmap_for_this_objective.phases[{index}].{field} must be a non-empty string")
        for field in ("scope", "actions", "validation_commands"):
            _require_string_list(phase.get(field), f"roadmap_for_this_objective.phases[{index}].{field}", errors)
        if isinstance(phase_id, str) and phase_id in EXPECTED_PHASE_MAP:
            expected = EXPECTED_PHASE_MAP[phase_id]
            for field in ("lane", "role"):
                if phase.get(field) != expected[field]:
                    errors.append(
                        f"roadmap_for_this_objective.phases[{phase_id}].{field} "
                        f"must be {expected[field]}"
                    )
            if phase.get("scope") != expected["scope"]:
                errors.append(
                    f"roadmap_for_this_objective.phases[{phase_id}].scope "
                    "must match exact expected scope"
                )
        if isinstance(phase.get("validation_commands"), list):
            commands.update(phase["validation_commands"])
    missing_commands = sorted(REQUIRED_VALIDATION_COMMANDS - commands)
    if missing_commands:
        errors.append("roadmap_for_this_objective validation commands missing: " + ", ".join(missing_commands))


def _validate_validation(catalog: dict[str, Any], errors: list[str], role_catalog: dict[str, Any] | None = None) -> None:
    validation = catalog.get("validation")
    if not _require_object(validation, "validation", errors):
        return
    if validation.get("validator") != "scripts/roadmap_control.py":
        errors.append("validation.validator must be scripts/roadmap_control.py")
    required_commands = REQUIRED_VALIDATION_COMMANDS
    if role_catalog is not None:
        catalog_commands = _roadmap_control_required_validations(role_catalog)
        if not catalog_commands:
            errors.append("platform-role-catalog roadmap_control required_validations missing")
        elif catalog_commands != REQUIRED_VALIDATION_COMMANDS:
            errors.append("platform-role-catalog roadmap_control required_validations drift from validator")
        else:
            required_commands = catalog_commands
    commands = validation.get("commands")
    _require_field_set(commands, "validation.commands", required_commands, errors)
    if isinstance(commands, list) and set(commands) != required_commands:
        errors.append("validation.commands must match roadmap_control required_validations from platform-role-catalog")


def validate_catalog(
    catalog: dict[str, Any],
    role_catalog: dict[str, Any] | None = None,
    subagent_policy: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if catalog.get("owner_plugin") != EXPECTED_OWNER:
        errors.append(f"owner_plugin must be {EXPECTED_OWNER}")
    _validate_entrypoint(catalog, errors)
    _validate_limits(catalog, errors)
    _validate_multi_spec(catalog, errors)
    _validate_pre_task_hook(catalog, errors)
    _validate_main_agent_policy(catalog, errors)
    if role_catalog is not None and subagent_policy is not None:
        _validate_orchestrator_control(catalog, role_catalog, subagent_policy, errors)
    else:
        control = catalog.get("orchestrator_control")
        if isinstance(control, dict):
            _require_field_set(
                control.get("explicit_controller_roles"),
                "orchestrator_control.explicit_controller_roles",
                REQUIRED_EXPLICIT_CONTROLLER_ROLES,
                errors,
            )
    _validate_audit_policy(catalog, errors)
    _validate_session_reuse(catalog, errors)
    _validate_objective_roadmap(catalog, errors)
    _validate_validation(catalog, errors, role_catalog)
    errors.extend(validate_research_artifact_contract(catalog.get("research_artifact_contract")))
    errors.extend(validate_design_artifact_contract(catalog.get("design_artifact_contract")))
    errors.extend(validate_prototype_artifact_contract(catalog.get("prototype_artifact_contract")))
    _validate_no_secret_like_text(catalog, errors)
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="roadmap control catalog path")
    parser.add_argument("--role-catalog", type=Path, default=DEFAULT_ROLE_CATALOG, help="subagents roles catalog path")
    parser.add_argument("--subagent-policy", type=Path, default=DEFAULT_SUBAGENT_POLICY, help="subagent orchestration policy path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the roadmap control catalog")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        catalog = load_cli_json(args.catalog, label="catalog")
        role_catalog = load_cli_json(args.role_catalog, label="role catalog")
        subagent_policy = load_cli_json(args.subagent_policy, label="subagent policy")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        errors = validate_catalog(catalog, role_catalog, subagent_policy)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("roadmap control catalog ok")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
