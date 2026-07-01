#!/usr/bin/env python3
"""Validate the Bears plugin constitution catalog and inspect change packets."""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/plugin-constitution.v1.json"
CATALOG_SCHEMA = "bears-plugin-constitution.v1"
CHANGE_PACKET_SCHEMA = "bears-plugin-constitution-change-check.v1"
FINAL_REPORT_PACKET_SCHEMA = "bears-plugin-final-report-evidence.v1"
OWNER_PLUGIN = "bears"
ALLOWED_STATUSES = {"pass", "fail", "needs-redesign"}
REQUIRED_CATALOG_FIELDS = {
    "schema",
    "version",
    "updated",
    "owner_plugin",
    "concrete_part",
    "route_target",
    "reference_doc",
    "purpose",
    "principles",
    "required_change_fields",
    "change_packet_schema",
    "decision_rules",
    "boundary_checks",
    "blocked_patterns",
    "surface_policy",
    "validation",
}
REQUIRED_PRINCIPLES = {
    "agent_simplification",
    "token_economy",
    "bounded_context",
    "deterministic_validation",
    "future_reuse",
    "operator_boundary",
    "mode_explicitness",
    "agent_handoff_compaction",
    "no_process_weight_without_payoff",
}
REQUIRED_CHANGE_FIELDS = {
    "schema",
    "change_id",
    "changed_surfaces",
    "agent_simplification_impact",
    "token_budget_impact",
    "bounded_context_plan",
    "future_reuse_path",
    "deterministic_validation_added",
    "deterministic_validation_evidence",
    "operator_decision_boundary",
    "cost_justification_if_any",
    "status",
}
REQUIRED_BOUNDARY_CHECKS = {
    "capability_inventory_boundary",
    "single_bears_plugin",
    "no_runtime_surface",
    "external_speckit_boundary",
    "exact_role_coverage",
    "english_entity_bound_artifacts",
    "restricted_data_exclusion",
    "inventory_sync",
}
REQUIRED_BLOCKED_PATTERNS = {
    "standalone_bears_plugin",
    "runtime_surface_in_plugin",
    "upstream_speckit_vendoring",
    "generic_deploy_wording",
    "illustrative_policy_sections",
    "restricted_data_access",
}
REQUIRED_ALLOWED_PLUGIN_LAYERS = {
    ".codex-plugin",
    ".github",
    "actions",
    "agents",
    "assets/catalog",
    "capabilities",
    "docs",
    "hooks",
    "schemas",
    "scripts",
    "skills",
    "templates",
    "tests",
    "workflows",
}
REQUIRED_SURFACE_SCAN_SCOPE = {
    "git_tracked_files",
    "git_untracked_unignored_files",
}
REQUIRED_FORBIDDEN_ROOT_ENTRIES = {
    "app",
    "apps",
    "connector",
    "connectors",
    "mcp",
    "mcp-server",
    "mcp-servers",
    "server",
    "servers",
    "service",
    "services",
    "runtime-service",
    "runtime-services",
    "deploy",
    "deployment",
    "deployments",
}
REQUIRED_FORBIDDEN_REGISTRATION_FILES = {
    "ai-plugin.json",
    "app.json",
    "apps.json",
    "connector.json",
    "connectors.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "mcp.json",
    "mcp-server.json",
    "mcp-servers.json",
    "procfile",
    "runtime-service.json",
    "server.json",
    "service.json",
    "services.json",
}
REQUIRED_FORBIDDEN_REGISTRATION_SUFFIXES = {
    ".service",
    ".socket",
    ".timer",
}
REQUIRED_FORBIDDEN_PATH_PATTERNS = {
    ".codex-plugin/apps/**",
    ".codex-plugin/connectors/**",
    ".codex-plugin/mcp/**",
    ".codex-plugin/servers/**",
    ".codex-plugin/services/**",
    ".well-known/ai-plugin.json",
    "Dockerfile",
    "Dockerfile.*",
    "deploy/**",
    "deployment/**",
    "deployments/**",
    "docker-compose.*",
    "mcp.json",
    "mcp-server.json",
    "mcp-servers.json",
    "runtime-services/**",
    "services/**",
}
REQUIRED_FORBIDDEN_MANIFEST_KEYS = {
    "apps",
    "connectors",
    "deploy",
    "deployment",
    "mcp",
    "mcpServers",
    "runtime",
    "runtimeServices",
    "server",
    "servers",
    "services",
}
ROUTE_TARGET = "/srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json"
LIFECYCLE_POSITION_PROOF = "after route_gate and before research_gate"
PLUGIN_SURFACE_PREFIX = "/srv/bears/plugins/bears/"
REQUIRED_ROUTE_AUDIT_EVIDENCE = {
    "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
    "python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
}
EXPANSION_CLAIMS = {
    "add app",
    "adds app",
    "add connector",
    "adds connector",
    "add mcp",
    "adds mcp",
    "mcp server",
    "runtime service",
    "product behavior",
    "production mutation",
    "deploy behavior",
    "deployment behavior",
}
BLOCKED_TEXT_FRAGMENTS = {
    "creating another bears governance plugin",
    "standalone bears governance layer",
    "copying upstream spec kit",
    "generic deploy wording",
    "sample section",
    "example section",
    "illustrative section",
    "restricted-data reads",
    "restricted data reads",
}
REQUIRED_VALIDATION_COMMANDS = {
    "python3 scripts/plugin_constitution.py validate",
    "python3 scripts/agentic_enterprise_workflow.py validate",
    "python3 scripts/plugin_constitution.py inspect-change --packet <path>",
    "python3 scripts/plugin_constitution.py inspect-final-report --packet <path>",
    "python3 scripts/platform_roles.py validate",
    "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
    "python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
    "python3 -m unittest tests/test_plugin_constitution.py tests/test_platform_roles.py",
    "python3 scripts/validate_overlay.py --json validate --strict-overlay-skills",
}
EXPECTED_PURPOSE = "Evaluate every Bears plugin change against agent simplification, token economy, deterministic validation, and future reuse."
DOC_REQUIRED_SECTIONS = [
    "# Plugin Constitution",
    "## Purpose",
    "## Technical terms",
    "## Gate files",
    "## Principles",
    "## Required constitution check",
    "## Allowed outcomes",
    "## Blocked outcomes",
    "## Token/context cost rule",
    "## Agent simplification rule",
    "## Reusable evidence rule",
    "## Memory citation relevance rule",
    "## Human approval boundary rule",
    "## Pass/fail decision outcomes",
    "## Boundary checks",
    "## Constitution checklist",
    "## Validator usage",
]
DOC_REQUIRED_TERMS = [
    "Constitution: top-level rule set for judging whether plugin work is useful.",
    "Token cost: context and output consumed by the model.",
    "Bounded packet: short structured data that replaces broad file reads.",
    "Reusable evidence: file-backed proof a future agent can rely on.",
    "Deterministic validator: script or schema check with stable pass/fail output.",
]
FINAL_REPORT_STOPWORDS = {
    "about",
    "actual",
    "agent",
    "and",
    "artifact",
    "audit",
    "bears",
    "broad",
    "check",
    "claim",
    "closeout",
    "command",
    "context",
    "current",
    "decision",
    "evidence",
    "final",
    "for",
    "from",
    "generic",
    "hit",
    "line",
    "live",
    "memory",
    "note",
    "orientation",
    "pass",
    "path",
    "proof",
    "quick",
    "report",
    "result",
    "role",
    "run",
    "status",
    "the",
    "used",
    "validation",
    "with",
    "workspace",
}
README_REQUIRED_FRAGMENTS = [
    "assets/catalog/plugin-constitution.v1.json",
    "scripts/plugin_constitution.py",
    "docs/reference/plugin-constitution.md",
    "constitution gate",
    "Agent work simplified:",
    "Token/context cost reduced or justified:",
    "Repeated file reads reduced:",
    "Future validator/catalog/rule added:",
    "Reusable evidence path:",
    "Human decision boundary:",
    "Failure mode if this is skipped:",
]
MANIFEST_REQUIRED_FRAGMENTS = [
    "plugin constitution",
    "scripts/plugin_constitution.py validate",
    "assets/catalog/plugin-constitution.v1.json",
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _catalog_string_set(section: dict[str, Any], key: str) -> set[str]:
    return set(_string_list(section.get(key)))


def _relative_repo_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0:
        return sorted(
            path.replace("\\", "/")
            for path in result.stdout.decode("utf-8", errors="replace").split("\0")
            if path
        )

    paths: list[str] = []
    for path in root.rglob("*"):
        if ".git" in path.parts or path.is_dir():
            continue
        paths.append(path.relative_to(root).as_posix())
    return sorted(paths)


def _path_matches_pattern(path: str, pattern: str) -> bool:
    normalized = path.strip("/").replace("\\", "/")
    normalized_pattern = pattern.strip("/").replace("\\", "/")
    return fnmatch.fnmatchcase(normalized, normalized_pattern)


def _manifest_forbidden_key_errors(manifest: Any, forbidden_keys: set[str], prefix: str = "plugin.json") -> list[str]:
    errors: list[str] = []
    if isinstance(manifest, dict):
        for key, value in manifest.items():
            current = f"{prefix}.{key}"
            if key in forbidden_keys:
                errors.append(f".codex-plugin/plugin.json contains forbidden surface key: {current}")
            errors.extend(_manifest_forbidden_key_errors(value, forbidden_keys, current))
    elif isinstance(manifest, list):
        for index, value in enumerate(manifest):
            errors.extend(_manifest_forbidden_key_errors(value, forbidden_keys, f"{prefix}[{index}]"))
    return errors


def validate_surface_policy(
    catalog: dict[str, Any],
    *,
    root: Path = PLUGIN_ROOT,
    listed_paths: list[str] | None = None,
    manifest_data: Any | None = None,
) -> list[str]:
    errors: list[str] = []
    policy = catalog.get("surface_policy")
    if not isinstance(policy, dict):
        return ["surface_policy must be an object"]

    required_sets = {
        "allowed_plugin_layers": REQUIRED_ALLOWED_PLUGIN_LAYERS,
        "scan_scope": REQUIRED_SURFACE_SCAN_SCOPE,
        "forbidden_root_entries": REQUIRED_FORBIDDEN_ROOT_ENTRIES,
        "forbidden_registration_files": REQUIRED_FORBIDDEN_REGISTRATION_FILES,
        "forbidden_registration_suffixes": REQUIRED_FORBIDDEN_REGISTRATION_SUFFIXES,
        "forbidden_path_patterns": REQUIRED_FORBIDDEN_PATH_PATTERNS,
        "forbidden_manifest_keys": REQUIRED_FORBIDDEN_MANIFEST_KEYS,
    }
    for key, required_values in required_sets.items():
        actual_values = _catalog_string_set(policy, key)
        if not actual_values:
            errors.append(f"surface_policy.{key} must be a non-empty list")
            continue
        for value in sorted(required_values - actual_values):
            errors.append(f"surface_policy.{key} missing value: {value}")

    if policy.get("path_match_only") is not True:
        errors.append("surface_policy.path_match_only must be true")
    if policy.get("fail_closed_on_forbidden_surface") is not True:
        errors.append("surface_policy.fail_closed_on_forbidden_surface must be true")

    forbidden_roots = _catalog_string_set(policy, "forbidden_root_entries")
    forbidden_files = {value.casefold() for value in _catalog_string_set(policy, "forbidden_registration_files")}
    forbidden_suffixes = {value.casefold() for value in _catalog_string_set(policy, "forbidden_registration_suffixes")}
    forbidden_patterns = _catalog_string_set(policy, "forbidden_path_patterns")
    paths = listed_paths if listed_paths is not None else _relative_repo_paths(root)
    for raw_path in paths:
        path = raw_path.strip().replace("\\", "/").strip("/")
        if not path or path.startswith(".git/"):
            continue
        parts = path.split("/")
        root_entry = parts[0]
        filename = parts[-1].casefold()
        if root_entry in forbidden_roots:
            errors.append(f"forbidden plugin surface path: {path} uses root entry {root_entry}")
        if filename in forbidden_files:
            errors.append(f"forbidden plugin registration file: {path}")
        for suffix in forbidden_suffixes:
            if filename.endswith(suffix):
                errors.append(f"forbidden plugin service registration file: {path}")
                break
        for pattern in sorted(forbidden_patterns):
            if _path_matches_pattern(path, pattern):
                errors.append(f"forbidden plugin surface path: {path} matches {pattern}")

    manifest_path = root / ".codex-plugin/plugin.json"
    manifest = manifest_data
    if manifest is None and manifest_path.is_file():
        try:
            manifest = load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f".codex-plugin/plugin.json must be readable JSON for surface policy: {exc}")
            manifest = None
    if manifest is not None:
        errors.extend(_manifest_forbidden_key_errors(manifest, _catalog_string_set(policy, "forbidden_manifest_keys")))
    return errors


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _has_non_empty_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return True
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return value is not None


def _has_lifecycle_order(text: str) -> bool:
    normalized = text.casefold().replace("-", " ")
    start = 0
    while True:
        route_index = normalized.find("route gate", start)
        if route_index == -1:
            return False
        constitution_index = normalized.find("constitution gate", route_index)
        research_index = normalized.find("research gate", constitution_index)
        if constitution_index != -1 and research_index != -1:
            return True
        start = route_index + len("route gate")


def _normalize_changed_path(value: str) -> str:
    text = value.replace("\\", "/").strip()
    if text.startswith(PLUGIN_SURFACE_PREFIX):
        text = text.removeprefix(PLUGIN_SURFACE_PREFIX)
    if text.startswith("plugins/bears/"):
        text = text.removeprefix("plugins/bears/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _is_safe_plugin_relative_path(value: str) -> bool:
    text = value.replace("\\", "/").strip()
    if not text or "\x00" in text:
        return False
    if text.startswith("/") and not text.startswith(PLUGIN_SURFACE_PREFIX):
        return False
    normalized = _normalize_changed_path(text)
    if normalized.startswith("../") or normalized == ".." or "/../" in normalized:
        return False
    return bool(normalized)


def _command_path_candidate(token: str) -> str | None:
    if token.startswith("--") and "=" in token:
        token = token.split("=", 1)[1]
    if token in {".", "..", "scripts", "tests"}:
        return token
    if token.startswith(("/", "./", "../")):
        return token
    if "/" in token or "\\" in token:
        return token
    return None


def _is_repo_bound_command_path(value: str, *, required_prefixes: tuple[str, ...] = ()) -> bool:
    text = value.replace("\\", "/").strip()
    if not text or "\x00" in text:
        return False
    if text.startswith(PLUGIN_SURFACE_PREFIX):
        text = text.removeprefix(PLUGIN_SURFACE_PREFIX)
    raw_parts = [part for part in text.split("/") if part]
    if any(part == ".." for part in raw_parts):
        return False

    path = Path(text)
    if path.is_absolute():
        resolved = path.resolve(strict=False)
    else:
        resolved = (PLUGIN_ROOT / path).resolve(strict=False)
    try:
        relative = resolved.relative_to(PLUGIN_ROOT.resolve())
    except ValueError:
        return False

    normalized = str(relative).replace("\\", "/")
    if not normalized or normalized == ".":
        return False
    if required_prefixes and not normalized.startswith(required_prefixes):
        return False
    return True


def _command_args_are_repo_bound(tokens: list[str]) -> bool:
    path_value_flags = {"--catalog", "--packet", "--config", "--schema", "--output", "--json-output", "-s", "-p"}
    expect_path_value = False
    for token in tokens:
        if expect_path_value:
            if not _is_repo_bound_command_path(token):
                return False
            expect_path_value = False
            continue
        if token in path_value_flags:
            expect_path_value = True
            continue
        candidate = _command_path_candidate(token)
        if candidate is not None and not _is_repo_bound_command_path(candidate):
            return False
    return not expect_path_value


def _is_repo_validation_command(value: str) -> bool:
    command = value.strip()
    blocked_tokens = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r")
    if not command or any(token in command for token in blocked_tokens):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) < 2 or tokens[0] != "python3":
        return False

    if tokens[1].startswith("scripts/"):
        if not _is_repo_bound_command_path(tokens[1], required_prefixes=("scripts/",)):
            return False
        if not tokens[1].endswith(".py"):
            return False
        return _command_args_are_repo_bound(tokens[2:])

    if len(tokens) >= 4 and tokens[1:3] == ["-m", "unittest"]:
        if tokens[3] == "discover":
            return _command_args_are_repo_bound(tokens[4:])
        if not all(_is_repo_bound_command_path(token, required_prefixes=("tests/",)) for token in tokens[3:]):
            return False
        return True

    return False


def _is_validator_or_test_path(value: str) -> bool:
    if not _is_safe_plugin_relative_path(value):
        return False
    normalized = _normalize_changed_path(value)
    return normalized.startswith("scripts/") or normalized.startswith("tests/")


def _validate_deterministic_validation_evidence(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict) or not value:
        return ["deterministic_validation_evidence must be a non-empty object"]

    required = {
        "command",
        "target_surface",
        "expected_status",
        "actual_status",
        "validator_path",
    }
    missing = sorted(required - set(value))
    for field in missing:
        errors.append(f"deterministic_validation_evidence.{field} is required")

    command = value.get("command")
    if not isinstance(command, str) or not command.strip():
        errors.append("deterministic_validation_evidence.command must be a non-empty string")
    elif not _is_repo_validation_command(command):
        errors.append("deterministic_validation_evidence.command must be a bounded repo-only validation command")

    target_surface = value.get("target_surface")
    if not isinstance(target_surface, str) or not target_surface.strip():
        errors.append("deterministic_validation_evidence.target_surface must be a non-empty string")
    elif not _is_safe_plugin_relative_path(target_surface):
        errors.append("deterministic_validation_evidence.target_surface must stay inside the plugin repository")

    for field in ("expected_status", "actual_status"):
        status_value = value.get(field)
        if status_value != "pass":
            errors.append(f"deterministic_validation_evidence.{field} must be pass")

    validator_path = value.get("validator_path")
    if not isinstance(validator_path, str) or not validator_path.strip():
        errors.append("deterministic_validation_evidence.validator_path must be a non-empty string")
    elif not _is_validator_or_test_path(validator_path):
        errors.append("deterministic_validation_evidence.validator_path must be a repo validator or test path")

    result_summary = value.get("result_summary")
    evidence_path = value.get("evidence_path")
    has_summary = isinstance(result_summary, str) and bool(result_summary.strip())
    has_path = isinstance(evidence_path, str) and bool(evidence_path.strip())
    if not has_summary and not has_path:
        errors.append("deterministic_validation_evidence requires result_summary or evidence_path")
    if has_path and not _is_safe_plugin_relative_path(evidence_path):
        errors.append("deterministic_validation_evidence.evidence_path must stay inside the plugin repository")
    return errors


def _load_platform_roles_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("platform_roles", PLUGIN_ROOT / "scripts/platform_roles.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load platform_roles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def _changed_surface_route_error(path_value: str) -> str | None:
    if not _is_safe_plugin_relative_path(path_value):
        return f"changed_surfaces contains path outside plugin governance boundary: {path_value}"
    normalized = _normalize_changed_path(path_value)
    try:
        platform_roles = _load_platform_roles_module()
        role_catalog = load_json(PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json")
        packet = platform_roles.route_target(role_catalog, normalized, plugin_root=PLUGIN_ROOT)
    except Exception as exc:
        return f"changed_surfaces route check failed for {path_value}: {exc}"
    if packet.get("status") != "matched":
        return f"changed_surfaces lacks exact role route: {path_value}"
    return None


def _iter_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            found.extend(_iter_text(item))
        return found
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_iter_text(item))
        return found
    return []


def _report_tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    normalized = value.casefold().replace("_", " ").replace("-", " ")
    tokens = set()
    for raw in normalized.split():
        token = "".join(char for char in raw if char.isalnum() or char == "#")
        if len(token) >= 3 and token not in FINAL_REPORT_STOPWORDS:
            tokens.add(token)
    return tokens


def _validate_final_report_citation(citation: Any, claims: list[str], index: int) -> list[str]:
    errors: list[str] = []
    path = f"memory_citations[{index}]"
    if not isinstance(citation, dict):
        return [f"{path} must be an object"]
    source = citation.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append(f"{path}.source must be a non-empty string")
    elif not (
        source == "MEMORY.md"
        or source.startswith("rollout_summaries/")
        or source.startswith("skills/")
    ):
        errors.append(f"{path}.source must be a memory file path")
    for field in ("line_start", "line_end"):
        if not isinstance(citation.get(field), int) or citation[field] < 1:
            errors.append(f"{path}.{field} must be a positive integer")
    if (
        isinstance(citation.get("line_start"), int)
        and isinstance(citation.get("line_end"), int)
        and citation["line_end"] < citation["line_start"]
    ):
        errors.append(f"{path}.line_end must be greater than or equal to line_start")

    note = citation.get("note")
    cited_text = citation.get("cited_text")
    claim = citation.get("claim")
    if not isinstance(note, str) or not note.strip():
        errors.append(f"{path}.note must be a non-empty string")
    if not isinstance(cited_text, str) or not cited_text.strip():
        errors.append(f"{path}.cited_text must be a non-empty string")
    if not isinstance(claim, str) or not claim.strip():
        errors.append(f"{path}.claim must be a non-empty string")

    if errors:
        return errors

    note_tokens = _report_tokens(note)
    cited_tokens = _report_tokens(cited_text)
    claim_tokens = _report_tokens(claim)
    if not note_tokens:
        errors.append(f"{path}.note must include a specific memory-use term")
    elif not note_tokens.intersection(cited_tokens):
        errors.append(f"{path}.note must match cited_text content")
    if not claim_tokens:
        errors.append(f"{path}.claim must include a specific report claim term")
    elif not claim_tokens.intersection(cited_tokens):
        errors.append(f"{path}.cited_text must directly support claim")
    if claim not in claims:
        errors.append(f"{path}.claim must reference one report claim")
    return errors


def validate_catalog(catalog: dict[str, Any], *, check_files: bool = True) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_CATALOG_FIELDS - set(catalog))
    for field in missing:
        errors.append(f"missing catalog field: {field}")

    if catalog.get("schema") != CATALOG_SCHEMA:
        errors.append(f"schema must be {CATALOG_SCHEMA}")
    if catalog.get("owner_plugin") != OWNER_PLUGIN:
        errors.append("owner_plugin must be bears")
    if catalog.get("concrete_part") != "plugin_constitution_governance":
        errors.append("concrete_part must be plugin_constitution_governance")
    if catalog.get("route_target") != ROUTE_TARGET:
        errors.append("route_target must point to the plugin constitution catalog")
    if catalog.get("reference_doc") != "/srv/bears/plugins/bears/docs/reference/plugin-constitution.md":
        errors.append("reference_doc must point to docs/reference/plugin-constitution.md")
    if catalog.get("change_packet_schema") != CHANGE_PACKET_SCHEMA:
        errors.append(f"change_packet_schema must be {CHANGE_PACKET_SCHEMA}")
    if catalog.get("purpose") != EXPECTED_PURPOSE:
        errors.append(f"purpose must be {EXPECTED_PURPOSE}")

    principles = catalog.get("principles")
    if not isinstance(principles, list) or not principles:
        errors.append("principles must be a non-empty list")
    else:
        ids = {item.get("id") for item in principles if isinstance(item, dict)}
        missing_principles = sorted(REQUIRED_PRINCIPLES - ids)
        for principle in missing_principles:
            errors.append(f"missing principle: {principle}")
        for item in principles:
            if not isinstance(item, dict):
                errors.append("principles entries must be objects")
                continue
            if not isinstance(item.get("rule"), str) or not item["rule"].strip():
                errors.append(f"principles.{item.get('id', '<unknown>')}.rule must be non-empty")

    fields = set(_string_list(catalog.get("required_change_fields")))
    if fields != REQUIRED_CHANGE_FIELDS:
        errors.append("required_change_fields must match the canonical constitution change-check packet fields")

    decision_rules = catalog.get("decision_rules")
    if not isinstance(decision_rules, dict):
        errors.append("decision_rules must be an object")
    else:
        statuses = set(_string_list(decision_rules.get("allowed_statuses")))
        if statuses != ALLOWED_STATUSES:
            errors.append("decision_rules.allowed_statuses must be pass, fail, and needs-redesign")
        if decision_rules.get("pass_requires_deterministic_validation_added") is not True:
            errors.append("decision_rules.pass_requires_deterministic_validation_added must be true")
        if decision_rules.get("pass_requires_deterministic_validation_evidence") is not True:
            errors.append("decision_rules.pass_requires_deterministic_validation_evidence must be true")
        if decision_rules.get("fail_closed_on_missing_required_fields") is not True:
            errors.append("decision_rules.fail_closed_on_missing_required_fields must be true")
        if decision_rules.get("fail_closed_on_unknown_status") is not True:
            errors.append("decision_rules.fail_closed_on_unknown_status must be true")
        order = _string_list(decision_rules.get("lifecycle_order"))
        if "constitution_gate" not in order:
            errors.append("decision_rules.lifecycle_order must include constitution_gate")
        elif not (order.index("route_gate") < order.index("constitution_gate") < order.index("research_gate")):
            errors.append("constitution_gate must be after route_gate and before research_gate")

    boundary_checks = catalog.get("boundary_checks")
    if not isinstance(boundary_checks, dict):
        errors.append("boundary_checks must be an object")
    else:
        missing_checks = sorted(REQUIRED_BOUNDARY_CHECKS - set(boundary_checks))
        for check in missing_checks:
            errors.append(f"missing boundary check: {check}")

    blocked = catalog.get("blocked_patterns")
    if not isinstance(blocked, list) or not blocked:
        errors.append("blocked_patterns must be a non-empty list")
    else:
        ids = {item.get("id") for item in blocked if isinstance(item, dict)}
        missing_patterns = sorted(REQUIRED_BLOCKED_PATTERNS - ids)
        for pattern in missing_patterns:
            errors.append(f"missing blocked pattern: {pattern}")

    errors.extend(
        validate_surface_policy(
            catalog,
            listed_paths=None if check_files else [],
            manifest_data=None if check_files else {},
        )
    )

    validation = catalog.get("validation")
    if not isinstance(validation, dict):
        errors.append("validation must be an object")
    else:
        commands = set(_string_list(validation.get("commands")))
        missing_commands = sorted(REQUIRED_VALIDATION_COMMANDS - commands)
        for command in missing_commands:
            errors.append(f"missing validation command: {command}")
        if validation.get("readme_inventory_required") is not True:
            errors.append("validation.readme_inventory_required must be true")
        if validation.get("manifest_prompt_required") is not True:
            errors.append("validation.manifest_prompt_required must be true")

    if check_files:
        errors.extend(validate_file_coverage())
    return errors


def validate_file_coverage() -> list[str]:
    errors: list[str] = []
    paths = {
        "doc": PLUGIN_ROOT / "docs/reference/plugin-constitution.md",
        "readme": PLUGIN_ROOT / "README.md",
        "agents": PLUGIN_ROOT / "AGENTS.md",
        "spec": PLUGIN_ROOT / "SPEC.md",
        "manifest": PLUGIN_ROOT / ".codex-plugin/plugin.json",
        "tests": PLUGIN_ROOT / "tests/test_plugin_constitution.py",
    }
    for label, path in paths.items():
        if not path.is_file():
            errors.append(f"missing {label} file: {path.relative_to(PLUGIN_ROOT)}")

    doc_path = paths["doc"]
    if doc_path.is_file():
        doc = doc_path.read_text(encoding="utf-8")
        for section in DOC_REQUIRED_SECTIONS:
            if section not in doc:
                errors.append(f"docs/reference/plugin-constitution.md missing section: {section}")
        for term in DOC_REQUIRED_TERMS:
            if term not in doc:
                errors.append(f"docs/reference/plugin-constitution.md missing term: {term}")
        if "```" in doc:
            errors.append("docs/reference/plugin-constitution.md must not contain code sample blocks")
        lowered = doc.lower()
        if "## examples" in lowered or "## samples" in lowered or "## illustrative" in lowered:
            errors.append("docs/reference/plugin-constitution.md must not contain sample, example, or illustrative sections")
    readme_path = paths["readme"]
    if readme_path.is_file():
        readme = readme_path.read_text(encoding="utf-8")
        for fragment in README_REQUIRED_FRAGMENTS:
            if fragment not in readme:
                errors.append(f"README.md missing constitution fragment: {fragment}")
        if not _has_lifecycle_order(readme):
            errors.append("README.md must place constitution gate after route gate and before research gate")
        if "principle results" in readme.lower():
            errors.append("README.md contains stale principle-results wording")

    agents_path = paths["agents"]
    if agents_path.is_file():
        agents = agents_path.read_text(encoding="utf-8")
        if "Canonical plugin constitution" not in agents:
            errors.append("AGENTS.md missing canonical plugin constitution ownership")
        if not _has_lifecycle_order(agents):
            errors.append("AGENTS.md must place constitution gate after route gate and before research gate")

    spec_path = paths["spec"]
    if spec_path.is_file():
        spec = spec_path.read_text(encoding="utf-8")
        if "## Plugin Constitution" not in spec:
            errors.append("SPEC.md missing Plugin Constitution section")
        if "scripts/plugin_constitution.py validate" not in spec:
            errors.append("SPEC.md missing plugin constitution validation command")

    manifest_path = paths["manifest"]
    if manifest_path.is_file():
        manifest_text = manifest_path.read_text(encoding="utf-8").lower()
        for fragment in MANIFEST_REQUIRED_FRAGMENTS:
            if fragment not in manifest_text:
                errors.append(f".codex-plugin/plugin.json missing constitution fragment: {fragment}")

    tests_path = paths["tests"]
    if tests_path.is_file():
        tests = tests_path.read_text(encoding="utf-8")
        for fragment in ("PluginConstitutionTests", "inspect-change", "validate_catalog", "validate_surface_policy"):
            if fragment not in tests:
                errors.append(f"tests/test_plugin_constitution.py missing test fragment: {fragment}")
    return errors


def inspect_change(packet: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required_fields = set(_string_list(catalog.get("required_change_fields"))) or REQUIRED_CHANGE_FIELDS
    missing = sorted(required_fields - set(packet))
    for field in missing:
        errors.append(f"missing required field: {field}")

    if packet.get("schema") != CHANGE_PACKET_SCHEMA:
        errors.append(f"schema must be {CHANGE_PACKET_SCHEMA}")
    status = packet.get("status")
    allowed = set(_string_list(catalog.get("decision_rules", {}).get("allowed_statuses"))) or ALLOWED_STATUSES
    if status not in allowed:
        errors.append("status must be pass, fail, or needs-redesign")

    changed_surfaces = packet.get("changed_surfaces")
    if not isinstance(changed_surfaces, list) or not changed_surfaces:
        errors.append("changed_surfaces must be a non-empty list")
    elif any(not isinstance(item, str) or not item.strip() for item in changed_surfaces):
        errors.append("changed_surfaces must contain only non-empty strings")
    else:
        for item in changed_surfaces:
            route_error = _changed_surface_route_error(item)
            if route_error is not None:
                errors.append(route_error)

    skip_empty_check = {
        "schema",
        "change_id",
        "changed_surfaces",
        "deterministic_validation_added",
        "status",
    }
    for field in sorted(required_fields - skip_empty_check):
        if field in packet and not _has_non_empty_value(packet[field]):
            errors.append(f"{field} must be non-empty")

    if "change_id" in packet and (not isinstance(packet.get("change_id"), str) or not packet["change_id"].strip()):
        errors.append("change_id must be a non-empty string")

    if "deterministic_validation_added" in packet and not isinstance(packet.get("deterministic_validation_added"), bool):
        errors.append("deterministic_validation_added must be a boolean")
    if status == "pass" and packet.get("deterministic_validation_added") is not True:
        errors.append("pass status requires deterministic_validation_added=true")
    if status == "pass":
        errors.extend(_validate_deterministic_validation_evidence(packet.get("deterministic_validation_evidence")))
    token_impact = str(packet.get("token_budget_impact", "")).casefold()
    cost_justification = str(packet.get("cost_justification_if_any", "")).strip()
    process_weight_markers = ("increase", "increases", "added", "adds", "more", "new gate", "new role", "new branch", "new handoff", "process weight")
    no_cost_markers = {"", "none", "n/a", "na", "no", "not applicable"}
    if any(marker in token_impact for marker in process_weight_markers) and cost_justification.casefold() in no_cost_markers:
        errors.append("added process weight requires cost_justification_if_any")

    route_target = packet.get("route_target")
    route_audit_evidence = set(_string_list(packet.get("route_audit_evidence")))
    if route_target != ROUTE_TARGET and not REQUIRED_ROUTE_AUDIT_EVIDENCE.issubset(route_audit_evidence):
        errors.append("packet must include exact route_target or route/audit evidence for plugin constitution")

    lifecycle_proof = packet.get("lifecycle_position_proof")
    if lifecycle_proof != LIFECYCLE_POSITION_PROOF:
        errors.append("lifecycle_position_proof must be after route_gate and before research_gate")

    joined_text = "\n".join(_iter_text(packet)).casefold()
    for claim in sorted(EXPANSION_CLAIMS):
        if claim in joined_text:
            errors.append(f"packet contains forbidden expansion claim: {claim}")
    for fragment in sorted(BLOCKED_TEXT_FRAGMENTS):
        if fragment in joined_text:
            errors.append(f"packet contains blocked-pattern text: {fragment}")

    return {
        "schema": "bears-plugin-constitution-inspection.v1",
        "status": "pass" if not errors else "fail",
        "packet_status": status,
        "errors": errors,
    }


def inspect_final_report(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema") != FINAL_REPORT_PACKET_SCHEMA:
        errors.append(f"schema must be {FINAL_REPORT_PACKET_SCHEMA}")

    claims = packet.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
        claim_values: list[str] = []
    elif any(not isinstance(item, str) or not item.strip() for item in claims):
        errors.append("claims must contain only non-empty strings")
        claim_values = []
    else:
        claim_values = claims

    memory_accessed = packet.get("memory_accessed")
    memory_used = packet.get("memory_used")
    citations = packet.get("memory_citations")
    discarded_reason = packet.get("memory_discarded_reason")
    if not isinstance(memory_accessed, bool):
        errors.append("memory_accessed must be a boolean")
    if not isinstance(memory_used, bool):
        errors.append("memory_used must be a boolean")
    if citations is None:
        citation_values: list[Any] = []
    elif isinstance(citations, list):
        citation_values = citations
    else:
        errors.append("memory_citations must be a list")
        citation_values = []

    if memory_used is True and not citation_values:
        errors.append("memory_used=true requires memory_citations")
    if memory_used is False and citation_values:
        errors.append("memory_citations require memory_used=true")
    if memory_accessed is True and memory_used is False:
        if not isinstance(discarded_reason, str) or not discarded_reason.strip():
            errors.append("memory_discarded_reason is required when accessed memory is discarded")
    if memory_accessed is False and memory_used is True:
        errors.append("memory_used cannot be true when memory_accessed is false")

    for index, citation in enumerate(citation_values):
        errors.extend(_validate_final_report_citation(citation, claim_values, index))

    return {
        "schema": "bears-plugin-final-report-inspection.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        catalog = load_json(args.catalog)
    except Exception as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, indent=2), file=sys.stderr)
        return 1
    errors = validate_catalog(catalog, check_files=not args.no_check_files)
    result = {
        "schema": "bears-plugin-constitution-validation.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def cmd_inspect_change(args: argparse.Namespace) -> int:
    try:
        catalog = load_json(args.catalog)
        packet = load_json(args.packet)
    except Exception as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, indent=2), file=sys.stderr)
        return 1
    result = inspect_change(packet, catalog)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


def cmd_inspect_final_report(args: argparse.Namespace) -> int:
    try:
        packet = load_json(args.packet)
    except Exception as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, indent=2), file=sys.stderr)
        return 1
    result = inspect_final_report(packet)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Bears plugin constitution governance")
    parser.set_defaults(func=None)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--no-check-files", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    inspect_parser = subparsers.add_parser("inspect-change")
    inspect_parser.add_argument("--packet", type=Path, required=True)
    inspect_parser.set_defaults(func=cmd_inspect_change)

    inspect_report_parser = subparsers.add_parser("inspect-final-report")
    inspect_report_parser.add_argument("--packet", type=Path, required=True)
    inspect_report_parser.set_defaults(func=cmd_inspect_final_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
