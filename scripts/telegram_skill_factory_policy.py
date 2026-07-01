#!/usr/bin/env python3
"""Validate the Telegram skill-bundle factory governance policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = PLUGIN_ROOT / "assets/catalog/telegram-plugin-skill-factory-policy.v1.json"
CANONICAL_GATE = "/srv/bears/plugins/bears/scripts/platform_roles.py"
LOCAL_GATE = "scripts/platform_roles.py"
CENTRAL_SKILL = "telegram-plugin-skill-factory"
CANONICAL_ROLE = "bears-telegram-platform-engineer"


class ValidationError(Exception):
    """Raised when the policy is invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValidationError(f"policy not found: {path}") from exc
    except OSError as exc:
        raise ValidationError(f"cannot read policy: {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"invalid JSON in policy: {path}: {exc.msg} (line {exc.lineno} column {exc.colno})"
        ) from exc
    if not isinstance(data, dict):
        raise ValidationError(f"policy root must be an object: {path}")
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _read(rel_path: str) -> str:
    path = PLUGIN_ROOT / rel_path
    _require(path.is_file(), f"missing required file: {rel_path}")
    return path.read_text(encoding="utf-8")


def _require_fields(container: dict[str, Any], key: str, required: set[str]) -> None:
    fields = container.get(key, {}).get("required_fields")
    _require(isinstance(fields, list), f"{key}.required_fields must be a list")
    missing = sorted(required - set(fields))
    _require(not missing, f"{key}.required_fields missing: {', '.join(missing)}")


def validate_policy(path: Path = DEFAULT_POLICY) -> None:
    data = _load_json(path)

    _require(data.get("schema") == "bears.telegram.plugin_skill_factory_policy.v1", "unexpected schema")
    _require(data.get("updated") == "2026-06-03", "updated must be current for this slice")

    central = data.get("central_skill")
    _require(isinstance(central, dict), "central_skill must be an object")
    _require(central.get("name") == CENTRAL_SKILL, "central_skill.name must be telegram-plugin-skill-factory")
    skill_path = central.get("path")
    _require(
        skill_path == "skills/telegram-plugin-skill-factory/SKILL.disabled.md",
        "central_skill.path mismatch",
    )
    skill_text = _read(skill_path)
    for phrase in [
        "canonical Bears role gate first",
        "skill-bundle discovery",
        "Forward-test central skills",
        "No unvalidated Telegram skill bundle, factory policy, or platform-role handoff",
    ]:
        _require(phrase in skill_text, f"central skill missing phrase: {phrase}")

    references = central.get("required_references")
    _require(isinstance(references, list) and references, "central_skill.required_references must be non-empty")
    for rel_path in references:
        ref_text = _read(rel_path)
        _require(CANONICAL_GATE in ref_text or "canonical Bears role gate first" in ref_text, f"reference lacks canonical gate language: {rel_path}")
    openai_prompt = _read(str(central.get("required_agent_prompt")))
    _require(CENTRAL_SKILL in openai_prompt, "agent prompt must mention central skill")
    _require("forward tests" in openai_prompt, "agent prompt must mention forward tests")

    canonical_plugin = data.get("canonical_plugin")
    _require(isinstance(canonical_plugin, dict), "canonical_plugin must be an object")
    _require(canonical_plugin.get("name") == "bears", "canonical plugin name must be bears")
    _require(canonical_plugin.get("root") == "/srv/bears/plugins/bears", "canonical plugin root mismatch")
    _require(canonical_plugin.get("exclusive_codex_plugin") is True, "policy must enforce one-plugin Bears model")
    _require(canonical_plugin.get("telegram_is_skill_bundle_only") is True, "policy must keep Telegram as skill bundle only")

    gate_order = data.get("gate_order")
    _require(isinstance(gate_order, list) and len(gate_order) >= 2, "gate_order must have canonical and Telegram skill-bundle steps")
    first, second = gate_order[0], gate_order[1]
    _require(first.get("step") == "canonical_role_gate", "canonical role gate must be first")
    _require(CANONICAL_GATE in first.get("command", ""), "canonical gate command missing")
    _require(first.get("required_primary_role") == CANONICAL_ROLE, "canonical role mismatch")
    _require(second.get("step") == "telegram_skill_bundle_validation", "Telegram skill-bundle validation must be second")
    _require("telegram_skill_factory_policy.py validate" in second.get("command", ""), "Telegram skill-bundle validator missing")

    shared_spine = data.get("shared_spine_order")
    _require(shared_spine == ["auth_core", "bears_gateway", "cd_deploy_stage"], "shared spine order must stay canonical")

    routing = data.get("workflow_routing")
    _require(isinstance(routing, list) and len(routing) >= 3, "workflow_routing must list canonical Telegram routes")
    routing_pairs = {(item.get("surface"), item.get("required_skill")) for item in routing if isinstance(item, dict)}
    for required in [
        ("telegram formatting/UI", "telegram-quality-testing"),
        ("telegram aiogram migration", "telegram-aiogram-migration"),
        ("telegram skill/policy lifecycle", "telegram-plugin-skill-factory"),
    ]:
        _require(required in routing_pairs, f"missing workflow route: {required[0]} -> {required[1]}")

    governed = data.get("governed_change_types")
    _require(isinstance(governed, list), "governed_change_types must be a list")
    for required in [
        "telegram_plugin_skill_create",
        "telegram_plugin_skill_update",
        "telegram_skill_bundle_discovery_metadata",
        "telegram_plugin_root_removal_guard",
        "telegram_subagent_workflow_update",
    ]:
        _require(required in governed, f"missing governed change type: {required}")

    forbidden = data.get("forbidden_before_canonical_role_coverage")
    allowed = data.get("allowed_before_canonical_role_coverage")
    _require(isinstance(forbidden, list) and "product implementation edits" in forbidden, "missing product edit blocker")
    _require(isinstance(forbidden, list) and "live Telegram actions" in forbidden, "missing live Telegram blocker")
    _require(isinstance(allowed, list) and "validators/tests" in allowed, "missing allowed validator work")

    _require_fields(
        data,
        "skill_change_packet",
        {
            "change_type",
            "target_paths",
            "canonical_role_route_status",
            "selected_primary_role",
            "allowed_write_scope",
            "forbidden_scope",
            "validation_commands",
            "forward_test_evidence",
            "closeout_status",
            "skill_bundle_boundary",
            "standalone_plugin_impact",
        },
    )
    packet = data["skill_change_packet"]
    _require(packet.get("required_route_status") == "matched", "skill packet must require matched route")
    _require(packet.get("required_primary_role") == CANONICAL_ROLE, "skill packet primary role mismatch")

    _require_fields(
        data,
        "subagent_handoff_packet",
        {
            "role",
            "lane",
            "role_artifact_path",
            "bounded_target_paths",
            "allowed_write_scope",
            "forbidden_scope",
            "disjoint_scope_statement",
            "current_spec_artifact_snapshot",
            "validation_command_or_evidence_target",
            "heartbeat_status_packet",
            "closeout_packet",
        },
    )
    handoff = data["subagent_handoff_packet"]
    _require(handoff.get("role_must_match_canonical_primary") is True, "handoff must match canonical role")
    _require(handoff.get("generic_worker_without_role") == "forbidden", "generic worker fallback must be forbidden")

    bundle = data.get("skill_bundle_boundary")
    _require(isinstance(bundle, dict), "skill_bundle_boundary must be an object")
    _require(bundle.get("root") == "/srv/bears/plugins/bears", "skill bundle root must be canonical Bears plugin")
    _require(bundle.get("mode") == "skills-catalogs-validators-only", "skill bundle mode mismatch")
    _require(bundle.get("central_skill") == "bears-telegram-workflow", "central Telegram skill mismatch")
    for rel_path in bundle.get("required_skill_paths", []):
        _require((PLUGIN_ROOT / rel_path).is_file(), f"missing required Telegram skill path: {rel_path}")
    forbidden = bundle.get("forbidden_standalone_surfaces")
    _require(isinstance(forbidden, list), "forbidden_standalone_surfaces must be a list")
    _require("/srv/bears/plugins/bears-telegram-workflow" in forbidden, "removed standalone plugin root must stay forbidden")
    _require(".app.json" in forbidden, "app manifests must stay forbidden for this skill bundle")
    _require(not (PLUGIN_ROOT / ".app.json").exists(), "canonical Bears plugin must not contain .app.json")

    validators = data.get("required_validators")
    _require(isinstance(validators, list), "required_validators must be a list")
    for required in [
        "scripts/telegram_skill_factory_policy.py validate",
        "/srv/bears/plugins/bears/scripts/platform_roles.py validate",
        "scripts/telegram_catalog.py validate",
        "scripts/telegram_migration_backlog.py validate",
        "scripts/telegram_runtime_readiness.py validate",
        "scripts/telegram_surface_inventory.py validate --workspace-root /srv/bears",
        "scripts/validate_overlay.py --json validate --strict-overlay-skills",
        "python3 -m unittest discover -s tests",
    ]:
        _require(required in validators, f"missing required validator: {required}")

    tests = data.get("forward_tests")
    _require(isinstance(tests, list) and len(tests) >= 4, "forward_tests must include at least four cases")
    test_names = {item.get("name") for item in tests if isinstance(item, dict)}
    for required in [
        "skill_creation_requires_canonical_gate_first",
        "subagent_handoff_requires_role_packet",
        "skill_bundle_boundary_is_not_live_connector",
        "duplicate_or_broad_skill_is_rejected",
    ]:
        _require(required in test_names, f"missing forward test: {required}")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "summary"))
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args(argv)

    try:
        validate_policy(args.policy)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "summary":
        data = _load_json(args.policy)
        print(f"central_skill: {data['central_skill']['name']}")
        print(f"governed_change_types: {len(data['governed_change_types'])}")
        print(f"required_validators: {len(data['required_validators'])}")
        print(f"forward_tests: {len(data['forward_tests'])}")
    else:
        print(f"skill factory policy ok: {args.policy}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
