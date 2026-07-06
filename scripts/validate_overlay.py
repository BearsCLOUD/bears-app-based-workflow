#!/usr/bin/env python3
"""Validation tooling for Bears workflow-overlay plugin governance assets."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python<3.11 fallback
    import toml  # type: ignore[import-not-found]

    def _load_toml(path: Path) -> dict[str, Any]:
        return toml.loads(path.read_text())
else:
    def _load_toml(path: Path) -> dict[str, Any]:
        with path.open("rb") as handle:
            return tomllib.load(handle)


REQUIRED_TOML_FIELDS = {
    "name",
    "description",
    "developer_instructions",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
}

REQUIRED_AGENT_INSTRUCTION_SECTIONS = (
    "Working mode:",
    "Scope/focus:",
    "Forbidden actions:",
    "Quality checks:",
    "Return shape:",
    "Validation expectations:",
)

READ_ONLY_AGENT_SAFETY_MARKERS = (
    "sandbox_mode is not authority proof",
    "READ_ONLY_ASSIGNMENT_BLOCKED",
    "audit subagent sessions cannot be reused for writable tasks",
)

AGENT_SANDBOX_MODE_MATRIX = {
    "bears-analytics-quality-engineer.toml": "workspace-write",
    "bears-android-emulator-platform-engineer.toml": "workspace-write",
    "bears-app-functional-graph-orchestrator.toml": "workspace-write",
    "bears-auth-platform-engineer.toml": "workspace-write",
    "bears-clarification-architect.toml": "read-only",
    "bears-codex-daemon-engineer.toml": "workspace-write",
    "bears-codex-health-engineer.toml": "workspace-write",
    "bears-instruction-hardening-engineer.toml": "workspace-write",
    "bears-codex-workspace-config-engineer.toml": "workspace-write",
    "bears-deploy-platform-engineer.toml": "workspace-write",
    "bears-deprecated-git-remote-hygiene-engineer.toml": "workspace-write",
    "bears-docs-maintainer.toml": "workspace-write",
    "bears-gateway-platform-engineer.toml": "workspace-write",
    "bears-github-actions-access-settings-governor.toml": "workspace-write",
    "bears-github-actions-secrets-governor.toml": "workspace-write",
    "bears-github-branch-protection-settings-governor.toml": "workspace-write",
    "bears-github-project-issues-orchestrator.toml": "workspace-write",
    "bears-git-workflow-helper.toml": "workspace-write",
    "bears-kubernetes-data-platform-engineer.toml": "workspace-write",
    "bears-goal-prompt-generator.toml": "workspace-write",
    "bears-infrastructure-network-engineer.toml": "workspace-write",
    "bears-machine-first-execution-kernel-engineer.toml": "workspace-write",
    "bears-notifications-platform-engineer.toml": "workspace-write",
    "bears-observability-platform-engineer.toml": "workspace-write",
    "bears-ops-runbook-engineer.toml": "workspace-write",
    "bears-payments-platform-engineer.toml": "workspace-write",
    "bears-subagents-roles-governor.toml": "workspace-write",
    "bears-platform-security-reviewer.toml": "read-only",
    "bears-subagents-roles-governor.toml": "workspace-write",
    "bears-product-app-zone-engineer.toml": "workspace-write",
    "bears-review-fix-helper.toml": "workspace-write",
    "bears-secret-factory-engineer.toml": "workspace-write",
    "bears-session-worker-runtime-engineer.toml": "workspace-write",
    "bears-subagent-orchestration-engineer.toml": "workspace-write",
    "bears-telegram-platform-engineer.toml": "workspace-write",
    "bears-tenant-registry-platform-engineer.toml": "workspace-write",
    "bears-token-budget-helper.toml": "workspace-write",
    "bears-vpn-bot-engineer.toml": "workspace-write",
    "bears-vpn-client-app-engineer.toml": "workspace-write",
    "bears-vpn-ingress-engineer.toml": "workspace-write",
    "bears-vpn-project-governance-engineer.toml": "workspace-write",
    "bears-vpn-proxy-engineer.toml": "workspace-write",
    "bears-vpn-runtime-engineer.toml": "workspace-write",
    "bears-wb-integration-platform-engineer.toml": "workspace-write",
    "bears-auth-domain-orchestrator.toml": "workspace-write",
    "bears-development-workflow-orchestrator.toml": "workspace-write",
    "bears-gateway-domain-orchestrator.toml": "workspace-write",
    "bears-infra-domain-orchestrator.toml": "workspace-write",
    "bears-payments-domain-orchestrator.toml": "workspace-write",
    "bears-qa-governance-orchestrator.toml": "workspace-write",
    "bears-tenant-domain-orchestrator.toml": "workspace-write",
    "bears-workflow-overlay-platform-engineer.toml": "workspace-write",
    "blocker-taxonomy-evaluator.toml": "read-only",
    "deploy-impact-gate.toml": "read-only",
    "governance-project-router.toml": "read-only",
    "l2-gitops-domain-orchestrator.toml": "workspace-write",
    "l2-infra-domain-orchestrator.toml": "workspace-write",
    "l2-platform-domain-orchestrator.toml": "workspace-write",
    "l2-product-infra-domain-orchestrator.toml": "workspace-write",
    "overlay-controller.toml": "workspace-write",
    "role-coverage-gate.toml": "read-only",
    "bears-plugin-update-engineer.toml": "workspace-write",
}

SCHEMA_FILES = {
    "workflow-policy": "workflow-policy.schema.json",
    "role-coverage": "role-coverage.schema.json",
    "blocker-review": "blocker-review.schema.json",
    "deploy-gate": "deploy-gate.schema.json",
}

ARTIFACT_FILES = {
    "workflow-policy": "workflow-policy.json",
    "role-coverage": "role-coverage.json",
    "blocker-review": "blocker-review.json",
    "deploy-gate": "deploy-gate.json",
}

REQUIRED_SPEC_KIT_FILES = ("spec.md", "plan.md", "tasks.md")
SPEC_KIT_ANALYZE_ARTIFACT = "speckit-analyze.json"

SPEC_KIT_ANALYZE_SCHEMA = "bears.speckit-analyze.v1"
RESTRICTED_MUTATION_MARKERS = (
    "production mutation",
    "prod mutation",
    "secret mutation",
    "raw secret",
    "production data mutation",
)
APPROVAL_MARKERS = (
    "operator approval",
    "explicit approval",
    "approved by operator",
    "approval evidence",
    "approval required",
)

ADVISORY_EXTENSION_HOOK_GROUPS = {
    "after_specify",
    "after_plan",
    "after_tasks",
    "before_implement",
}
HARD_EXTENSION_HOOK_GROUPS = {
    "after_analyze",
}
REQUIRED_EXTENSION_HOOK_GROUPS = ADVISORY_EXTENSION_HOOK_GROUPS | HARD_EXTENSION_HOOK_GROUPS

ADVISORY_EXTENSION_FLAGS = (
    "advisory",
    "report_only",
    "fail_open",
    "optional",
)
HARD_EXTENSION_FLAGS = {
    "advisory": False,
    "report_only": False,
    "fail_open": False,
    "optional": False,
}
SPEC_KIT_ANALYZE_FIELDS = {
    "spec_path": "spec.md",
    "plan_path": "plan.md",
    "tasks_path": "tasks.md",
}
SUBAGENTS_ROLES_CATALOG_FILE = "assets/catalog/platform-role-catalog.v1.json"
BEARS_SDD_WORKFLOW_FILE = "workflows/bears-sdd/workflow.yml"
BEARS_SDD_WORKFLOW_ID = "bears-sdd"
BEARS_SDD_CONTRACT_KEY = "workflow_contracts"
DEFAULT_BEARS_SDD_WORKFLOW_CONTRACT = {
    "required_order": [
        "route-gate",
        "constitution-gate",
        "research",
        "prototype-gate",
        "design-artifact-gate",
        "spec-kit-gate",
        "role-gate",
        "subagent-execution",
        "validation",
        "stage-boundary-audit",
    ],
    "research_skip_required_inputs": ["research_skip_evidence"],
    "step_required_fragments": {
        "route-gate": ["bears.governance.check"],
        "constitution-gate": [SUBAGENTS_ROLES_CATALOG_FILE],
        "research": ["speckit.bears.research"],
        "prototype-gate": ["prototype.md or spike.md"],
        "design-artifact-gate": ["design.md"],
        "spec-kit-gate": ["spec.md", "plan.md", "tasks.md", "speckit-analyze PASS"],
        "role-gate": ["bears.role.gate"],
        "subagent-execution": ["tasks.md"],
        "validation": ["bears.workflow.validate"],
        "stage-boundary-audit": ["stage boundary"],
    },
}
WORKFLOW_DESCRIPTION_FRAGMENTS = [
    "route gate",
    "subagents-roles gate",
    "research",
    "prototype",
    "design",
    "Spec Kit",
    "role gate",
    "task-scoped subagents",
    "validation",
    "stage-boundary audit",
]
GOVERNANCE_LINK_FILES = (
    "README.md",
    "SPEC.md",
    "AGENTS.md",
)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

MANIFEST_VISIBLE_FIELD_PATHS = (
    ("description",),
    ("interface", "shortDescription"),
    ("interface", "longDescription"),
    ("interface", "defaultPrompt"),
    ("keywords",),
    ("interface", "capabilities"),
)
MANIFEST_APPROVED_SECRET_FACTORY_TERMS = (
    "Secret Factory governance",
    "write-only Secret Factory",
    "write-only Infisical creation governance",
    "secret-factory",
    "write-only-secrets",
)
MANIFEST_FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"\bbot\s+token\b", re.IGNORECASE),
    re.compile(r"\bprivate\s+key\b", re.IGNORECASE),
    re.compile(r"\bsecret[_\s-]*value\b", re.IGNORECASE),
    re.compile(r"\blive\s+secret\s+access\b", re.IGNORECASE),
    re.compile(r"\bread(?:ing|s)?\s+(?:raw\s+)?secrets?\b", re.IGNORECASE),
    re.compile(r"\bread(?:ing|s)?\s+credentials?\b", re.IGNORECASE),
    re.compile(r"\bcredentials?\s+reads?\b", re.IGNORECASE),
    re.compile(r"\b(?:print|store|log|expose|handle|handling)s?\s+(?:raw\s+)?(?:secret|credential)", re.IGNORECASE),
    re.compile(r"\.env\b", re.IGNORECASE),
)
SAFE_PROHIBITION_MARKERS = (
    "do not",
    "must not",
    "without",
    "forbidden",
    "reject",
    "block",
    "disabled",
    "require explicit operator approval",
    "security review",
    "no ",
)

STATIC_LITERAL_POLICY = {
    "scope": "pr_added_lines_only",
    "preexisting_repo_hits": "baseline_or_cleanup_issue_required",
    "reporting": "path_category_count_redacted_excerpt_only",
    "required_gate": "validate_overlay_static_safety_pr_gate",
    "issue_flow": "line_only_redacted_issue",
    "compact_action_json": True,
}
STATIC_LITERAL_REQUIRED_CATEGORIES = (
    "raw_endpoint_literal",
    "raw_ip_or_cidr_literal",
)
STATIC_SAFETY_REQUIRED_PLANES = (
    "secret_factory_governance",
    "infrastructure_network_governance",
)
APPROVED_STATIC_LITERAL_SENTINELS = (
    "example.com",
    "example.invalid",
    "example.test",
    "localhost.invalid",
    "{host}",
    "{ip}",
    "{cidr}",
    "<endpoint-ref>",
    "<cidr-ref>",
)
RAW_URL_RE = re.compile(r"https?://[A-Za-z0-9][A-Za-z0-9.-]*(?::\d+)?(?:/[^\s`\"')\]}]*)?")
RAW_IPV4_OR_CIDR_RE = re.compile(
    r"\b(?:"
    r"(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\."
    r"|(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\."
    r")"
    r"(?:\d{1,3}\.){2}\d{1,3}(?:/\d{1,2})?\b"
)
CREDENTIAL_PATH_RE = re.compile(
    r"(^|/)(?:\.env[^/]*|.*(?:credential|credentials|token|secret|secrets|key|provider-config).*)(?:$|/)",
    re.IGNORECASE,
)
SAFE_DISCOVERY_WRAPPER_RE = re.compile(r"(^|/)(?:scripts|bin)/[A-Za-z0-9_.-]+$")
SAFE_DISCOVERY_CONTRACT_RE = re.compile(r"(^|/)(?:README|AGENTS|SPEC|requirements)\.md$|(^|/)docs/reference/[A-Za-z0-9_.-]+\.md$")
SENSITIVE_URI_RE = re.compile(
    r"\b(?:postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?|mysql|redis|mongodb|amqp|https?)://[^\s'\"<>]*:[^\s'\"<>@]+@[^\s'\"<>]+",
    re.IGNORECASE,
)
INVENTORY_SENSITIVE_PATH_RE = re.compile(
    r"(^|/)(?:settings|config|database|credentials|secrets)(?:\.py|/|$)|(^|/)\.env",
    re.IGNORECASE,
)
ABUSE_PROBE_REQUIRED_FIELDS = (
    "manifest_visible_text",
    "static_literal_scan",
    "inventory_uri_redaction",
    "live_tool_classifier",
    "secret_discovery_classifier",
)


REQUIRED_CANONICAL_FILES = {
    ".github/ISSUE_TEMPLATE/01-governance-work.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    "AGENTS.md",
    "SPEC.md",
    "requirements.md",
    "assets/catalog/auth-gateway-deploy-readiness.v1.json",
    "assets/catalog/platform-role-catalog.v1.json",
    "assets/catalog/plugin-governance-language-policy.v1.json",
    "assets/catalog/platform-role-catalog.v1.json",
    "assets/catalog/role-gate-methodology.v1.json",
    "assets/catalog/session-workers-runtime.v1.json",
    "assets/catalog/subagent-orchestration-policy.v1.json",
    "docs/reference/role-gate-methodology.md",
    "docs/reference/session-workers-runtime.md",
    "docs/generated/README.skill-inventory.md",
    "docs/generated/SPEC.skill-inventory.md",
    "scripts/auth_gateway_deploy_readiness.py",
    "scripts/subagents_roles.py",
    "scripts/project_registry_gate.py",
    "scripts/role_gate_methodology.py",
    "scripts/session_workers_runtime.py",
    "scripts/skill_catalog.py",
    "scripts/subagent_orchestration_policy.py",
    "workflows/auth-gateway-deploy-core/workflow.yml",
    "workflows/bears-sdd/workflow.yml",
    "skills/bears-goal-prompt/SKILL.md",
    "skills/subagents-roles/SKILL.md",
    "assets/catalog/plugin-skill-catalog.v1.json",
    "assets/catalog/telegram-aiogram-migration-backlog.v1.json",
    "assets/catalog/telegram-runtime-readiness.v1.json",
    "scripts/telegram_migration_backlog.py",
    "scripts/telegram_runtime_readiness.py",
}

REQUIRED_CANONICAL_ROLES = {
    "bears-subagents-roles-governor",
    "bears-auth-platform-engineer",
    "bears-gateway-platform-engineer",
    "bears-deploy-platform-engineer",
    "bears-platform-security-reviewer",
    "bears-workflow-overlay-controller",
    "bears-goal-prompt-generator",
    "bears-session-worker-runtime-engineer",
    "bears-telegram-platform-engineer",
    "bears-product-app-zone-engineer",
    "bears-analytics-quality-engineer",
    "bears-android-emulator-platform-engineer",
    "bears-observability-platform-engineer",
    "bears-ops-runbook-engineer",
    "bears-subagent-orchestration-engineer",
}

REQUIRED_CANONICAL_PARTS = {
    "auth_core",
    "bears_gateway",
    "cd_deploy_stage",
    "auth_gateway_deploy_core",
    "bears_plugin",
    "subagents_roles_governance",
    "goal_prompt_generator",
    "role_gate_methodology",
    "session_workers_runtime",
    "telegram_platform",
    "workspace_governance_canonical_plugin_docs",
    "kubernetes_deploy_core",
    "android_emulator_platform_225",
    "sentry_observability_226",
    "theants_product_dev_layer",
    "theants_quality_e2e_layer",
    "theants_ops_runbooks_layer",
    "theants_control_provenance_layer",
    "subagent_orchestration_policy",
    "project_registry_gate",
}

REQUIRED_WORKSPACE_ROLE_GATE_REFERENCES = {
    "dev/WORKSPACE.md": [
        "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
        "/srv/bears/plugins/bears/scripts/subagents_roles.py validate",
    ],
    "dev/PROJECTS.md": [
        "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
        "/srv/bears/plugins/bears/scripts/subagents_roles.py validate",
    ],
}

FORBIDDEN_SHARED_ROLE_GATE_REFERENCES = (
    "/srv/bears/plugins/bears-telegram-workflow/assets/catalog/platform-role-catalog.v1.json",
    "/srv/bears/plugins/bears-telegram-workflow/scripts/subagents_roles.py",
)

REQUIRED_ISSUE_FORM_FIELDS = {
    "target_path",
    "concrete_part_or_role_route",
    "problem_statement",
    "pre_development_gate_impact",
    "research_reuse_decision",
    "validation_command",
    "restricted_data_safety",
}

REQUIRED_ISSUE_FORM_REQUIRED_FIELDS = REQUIRED_ISSUE_FORM_FIELDS - {
    "restricted_data_safety",
}

PLUGIN_GOVERNANCE_LANGUAGE_POLICY_FILE = "assets/catalog/plugin-governance-language-policy.v1.json"
PLUGIN_GOVERNANCE_LANGUAGE_POLICY_SCHEMA = "bears-plugin-governance-language-policy.v1"
PLUGIN_GOVERNANCE_REPO_PROOF_SCOPE = "repo_only"
PLUGIN_GOVERNANCE_REQUIRED_ENTITY_TERMS = {"local_cd", "kubernetes_deployment"}
PLUGIN_GOVERNANCE_ALLOWED_EXACT_TERMS = {
    "github_ci",
    "local_cd",
    "dev-cd-gate",
    "git_discipline",
    "kubernetes_deployment",
    "fresh_no_parent_context",
}
PLUGIN_GOVERNANCE_REQUIRED_ENTITY_TERM_POLICY = {
    "app": {
        "meaning_fragments": ("/srv/bears/dev/app", "BearsCLOUD/apps"),
        "forbidden_meanings": ("local repository", "plugin", "connector", "MCP server", "runtime surface"),
    },
    "project": {
        "meaning_fragments": ("GitHub Project", "Issues", "metadata fields"),
        "forbidden_meanings": (
            "product application",
            "local repository",
            "workspace directory",
            "deprecated /srv/bears/projects",
        ),
    },
}
PLUGIN_GOVERNANCE_FORBIDDEN_TOKEN = "deploy"
PLUGIN_GOVERNANCE_FORBIDDEN_SECTION_KEY_TOKENS = (
    "example",
    "sample",
    "illustrat",
)
PLUGIN_GOVERNANCE_FORBIDDEN_MARKDOWN_SECTION_RE = re.compile(
    r"^\s{0,3}#{1,6}\s+.*(?:example|sample|illustrat)",
    re.IGNORECASE | re.MULTILINE,
)
PLUGIN_GOVERNANCE_FORBIDDEN_GENERIC_DEPLOYMENT_PATTERNS = (
    re.compile(r"\bgithub\s+deploy(?:ment|ments)?\b", re.IGNORECASE),
    re.compile(r"\bdeploy(?:ment|ments)?\s+to\s+github\b", re.IGNORECASE),
    re.compile(r"\bkubernetes\s+deploy(?:ment|ments)?\b", re.IGNORECASE),
    re.compile(r"\bdeploy(?:ment|ments)?\s+to\s+kubernetes\b", re.IGNORECASE),
)

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
    "null": type(None),
}

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def warn(message: str) -> None:
    print(f"WARN: {message}")


def info(message: str) -> None:
    print(f"INFO: {message}")


def _validate_type(value: Any, expected: str | list[str], path: str) -> list[str]:
    expected_types = [expected] if isinstance(expected, str) else expected
    for expected_type in expected_types:
        py_type = TYPE_MAP.get(expected_type)
        if py_type is None:
            continue
        if isinstance(value, py_type):
            return []
    return [f"{path}: expected {expected_types}, got {type(value).__name__}"]


def _validate_schema_instance(instance: Any, schema: dict[str, Any], path: str = "root") -> list[str]:
    errors: list[str] = []

    schema_type = schema.get("type")
    if schema_type:
        errors.extend(_validate_type(instance, schema_type, path))

    if not isinstance(instance, dict):
        return errors

    for required_field in schema.get("required", []):
        if required_field not in instance:
            errors.append(f"{path}.{required_field}: required field is missing")

    for field, descriptor in schema.get("properties", {}).items():
        if field not in instance:
            continue

        value = instance[field]
        if not isinstance(descriptor, dict):
            continue

        if "enum" in descriptor:
            if value not in descriptor["enum"]:
                errors.append(f"{path}.{field}: value {value!r} not in enum {descriptor['enum']}")

        if "const" in descriptor and value != descriptor["const"]:
            errors.append(f"{path}.{field}: value {value!r} must be {descriptor['const']!r}")

        if "type" in descriptor:
            errors.extend(_validate_type(value, descriptor["type"], f"{path}.{field}"))

            if descriptor["type"] == "array" and isinstance(value, list):
                item_schema = descriptor.get("items", {})
                for i, item in enumerate(value):
                    if item_schema:
                        errors.extend(_validate_schema_instance(item, item_schema, f"{path}.{field}[{i}]"))

            if descriptor["type"] == "object" and isinstance(value, dict):
                for req in descriptor.get("required", []):
                    if req not in value:
                        errors.append(f"{path}.{field}.{req}: required nested field is missing")
                for nested_field, nested_desc in descriptor.get("properties", {}).items():
                    if nested_field not in value:
                        continue
                    if isinstance(nested_desc, dict) and "enum" in nested_desc and value[nested_field] not in nested_desc["enum"]:
                        errors.append(
                            f"{path}.{field}.{nested_field}: value {value[nested_field]!r} "
                            f"not in enum {nested_desc['enum']}"
                        )
                    if isinstance(nested_desc, dict) and "type" in nested_desc:
                        nested_value = value[nested_field]
                        errors.extend(
                            _validate_type(
                                nested_value,
                                nested_desc["type"],
                                f"{path}.{field}.{nested_field}",
                            )
                        )

    return errors


def _find_forbidden_section_keys(node: Any, error_message: str) -> list[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                normalized = key.casefold()
                leading_token = re.split(r"[^a-z]+", normalized, maxsplit=1)[0]
                if leading_token and any(leading_token.startswith(token) for token in PLUGIN_GOVERNANCE_FORBIDDEN_SECTION_KEY_TOKENS):
                    return [error_message]
            errors = _find_forbidden_section_keys(value, error_message)
            if errors:
                return errors
        return []

    if isinstance(node, list):
        for item in node:
            errors = _find_forbidden_section_keys(item, error_message)
            if errors:
                return errors

    return []


def _validate_english_only_artifact(relative_path: str, text: str) -> list[str]:
    for char in text:
        if not char.isalpha():
            continue
        if char.isascii():
            continue
        if "LATIN" in unicodedata.name(char, ""):
            continue
        return [
            f"{relative_path}: artifact must be English-only; found non-Latin letter "
            f"U+{ord(char):04X} {char!r}"
        ]
    return []


def _validate_no_illustrative_sections(relative_path: str, text: str, artifact_path: Path) -> list[str]:
    if artifact_path.suffix == ".json":
        try:
            payload = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            return [f"{relative_path}: cannot parse governed JSON artifact: {exc}"]
        return _find_forbidden_section_keys(
            payload,
            f"{relative_path}: illustrative sample sections are forbidden",
        )

    if artifact_path.suffix == ".md" and PLUGIN_GOVERNANCE_FORBIDDEN_MARKDOWN_SECTION_RE.search(text):
        return [f"{relative_path}: illustrative sample sections are forbidden"]

    return []


def _validate_concrete_deployment_terms(relative_path: str, text: str) -> list[str]:
    for pattern in PLUGIN_GOVERNANCE_FORBIDDEN_GENERIC_DEPLOYMENT_PATTERNS:
        if pattern.search(text):
            return [
                f"{relative_path}: generic deployment wording is forbidden; use exact terms "
                "local_cd or kubernetes_deployment"
            ]
    return []


def _validate_repo_proof_governed_artifacts(
    plugin_root: Path,
    repo_proof: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    if repo_proof.get("proof_scope") != PLUGIN_GOVERNANCE_REPO_PROOF_SCOPE:
        errors.append("plugin governance language policy repo_proof.proof_scope must be repo_only")
    if repo_proof.get("runtime_chat_out_of_scope") is not True:
        errors.append("plugin governance language policy repo_proof.runtime_chat_out_of_scope must be true")

    governed_artifacts = repo_proof.get("governed_artifacts")
    if not isinstance(governed_artifacts, list) or not governed_artifacts:
        errors.append("plugin governance language policy repo_proof.governed_artifacts must be a non-empty list")
        return errors

    seen_paths: set[str] = set()
    for index, artifact_rule in enumerate(governed_artifacts):
        rule_path = f"repo_proof.governed_artifacts[{index}]"
        if not isinstance(artifact_rule, dict):
            errors.append(f"plugin governance language policy {rule_path} must be an object")
            continue

        relative_path = artifact_rule.get("path")
        if not isinstance(relative_path, str) or not relative_path.strip():
            errors.append(f"plugin governance language policy {rule_path}.path must be a non-empty string")
            continue
        if relative_path in seen_paths:
            errors.append(f"plugin governance language policy {rule_path}.path must be unique: {relative_path}")
            continue
        seen_paths.add(relative_path)

        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(f"plugin governance language policy {rule_path}.path must stay inside the plugin root")
            continue

        must_be_english_only = artifact_rule.get("must_be_english_only")
        if not isinstance(must_be_english_only, bool):
            errors.append(f"plugin governance language policy {rule_path}.must_be_english_only must be boolean")
            continue

        must_include_required_entity_terms = artifact_rule.get("must_include_required_entity_terms")
        if not isinstance(must_include_required_entity_terms, bool):
            errors.append(
                f"plugin governance language policy {rule_path}.must_include_required_entity_terms must be boolean"
            )
            continue

        forbid_illustrative_sections = artifact_rule.get("forbid_illustrative_sections")
        if not isinstance(forbid_illustrative_sections, bool):
            errors.append(
                f"plugin governance language policy {rule_path}.forbid_illustrative_sections must be boolean"
            )
            continue

        required_fragments = artifact_rule.get("required_fragments")
        if not isinstance(required_fragments, list) or not all(isinstance(item, str) and item for item in required_fragments):
            errors.append(
                f"plugin governance language policy {rule_path}.required_fragments must be a list of non-empty strings"
            )
            continue

        artifact_path = plugin_root / candidate
        if not artifact_path.is_file():
            errors.append(f"missing governed artifact from plugin governance language policy: {relative_path}")
            continue

        try:
            text = artifact_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot read governed artifact {relative_path}: {exc}")
            continue

        if must_be_english_only:
            errors.extend(_validate_english_only_artifact(relative_path, text))

        if must_include_required_entity_terms:
            for term in sorted(PLUGIN_GOVERNANCE_REQUIRED_ENTITY_TERMS):
                if term not in text:
                    errors.append(f"{relative_path}: missing required entity-bound term: {term}")
            errors.extend(_validate_concrete_deployment_terms(relative_path, text))

        for fragment in required_fragments:
            if fragment not in text:
                errors.append(f"{relative_path}: missing required governance fragment: {fragment}")

        if forbid_illustrative_sections:
            errors.extend(_validate_no_illustrative_sections(relative_path, text, artifact_path))

    return errors


def validate_plugin_governance_language_policy(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    policy_path = plugin_root / PLUGIN_GOVERNANCE_LANGUAGE_POLICY_FILE
    if not policy_path.is_file():
        return errors

    try:
        policy = json.loads(policy_path.read_text())
    except Exception as exc:  # noqa: BLE001
        return [f"cannot parse plugin governance language policy: {exc}"]

    if not isinstance(policy, dict):
        return ["plugin governance language policy root must be an object"]

    if policy.get("schema") != PLUGIN_GOVERNANCE_LANGUAGE_POLICY_SCHEMA:
        errors.append(
            "plugin governance language policy schema must be bears-plugin-governance-language-policy.v1"
        )
    if policy.get("owner_plugin") != "bears":
        errors.append("plugin governance language policy owner_plugin must be bears")
    if policy.get("artifact_language") != "en":
        errors.append("plugin governance language policy artifact_language must be en")
    if policy.get("subagent_message_language") != "en":
        errors.append("plugin governance language policy subagent_message_language must be en")

    wording_policy = policy.get("wording_policy")
    if not isinstance(wording_policy, dict):
        errors.append("plugin governance language policy wording_policy must be an object")
        return errors

    if wording_policy.get("style") != "strict_entity_bound_concise":
        errors.append(
            "plugin governance language policy wording_policy.style must be strict_entity_bound_concise"
        )
    if wording_policy.get("abstract_drift") != "blocked":
        errors.append("plugin governance language policy wording_policy.abstract_drift must be blocked")
    if wording_policy.get("section_mode") != "policy_only":
        errors.append("plugin governance language policy wording_policy.section_mode must be policy_only")

    required_entity_terms = wording_policy.get("required_entity_terms")
    if not isinstance(required_entity_terms, list):
        errors.append("plugin governance language policy wording_policy.required_entity_terms must be a list")
    else:
        missing_terms = sorted(
            PLUGIN_GOVERNANCE_REQUIRED_ENTITY_TERMS
            - {item for item in required_entity_terms if isinstance(item, str)}
        )
        if missing_terms:
            errors.append(
                "plugin governance language policy wording_policy.required_entity_terms missing: "
                + ", ".join(missing_terms)
            )

    allowed_exact_terms = wording_policy.get("allowed_exact_terms")
    if not isinstance(allowed_exact_terms, list):
        errors.append("plugin governance language policy wording_policy.allowed_exact_terms must be a list")
    else:
        missing_allowed_terms = sorted(
            PLUGIN_GOVERNANCE_ALLOWED_EXACT_TERMS
            - {item for item in allowed_exact_terms if isinstance(item, str)}
        )
        if missing_allowed_terms:
            errors.append(
                "plugin governance language policy wording_policy.allowed_exact_terms missing: "
                + ", ".join(missing_allowed_terms)
            )

    entity_term_policy = wording_policy.get("entity_term_policy")
    if not isinstance(entity_term_policy, dict):
        errors.append("plugin governance language policy wording_policy.entity_term_policy must be an object")
    else:
        for term, requirement in PLUGIN_GOVERNANCE_REQUIRED_ENTITY_TERM_POLICY.items():
            term_policy = entity_term_policy.get(term)
            if not isinstance(term_policy, dict):
                errors.append(
                    f"plugin governance language policy wording_policy.entity_term_policy.{term} must be an object"
                )
                continue
            meaning = term_policy.get("meaning")
            if not isinstance(meaning, str) or not meaning.strip():
                errors.append(
                    f"plugin governance language policy wording_policy.entity_term_policy.{term}.meaning must be a non-empty string"
                )
            else:
                missing_fragments = [
                    fragment for fragment in requirement["meaning_fragments"] if fragment not in meaning
                ]
                if missing_fragments:
                    errors.append(
                        f"plugin governance language policy wording_policy.entity_term_policy.{term}.meaning missing: "
                        + ", ".join(missing_fragments)
                    )
            required_precision = term_policy.get("required_precision")
            if not isinstance(required_precision, str) or not required_precision.strip():
                errors.append(
                    f"plugin governance language policy wording_policy.entity_term_policy.{term}.required_precision must be a non-empty string"
                )
            forbidden_meanings = term_policy.get("forbidden_meanings")
            if not isinstance(forbidden_meanings, list):
                errors.append(
                    f"plugin governance language policy wording_policy.entity_term_policy.{term}.forbidden_meanings must be a list"
                )
            else:
                forbidden_text = "\n".join(item for item in forbidden_meanings if isinstance(item, str))
                missing_forbidden = [
                    fragment for fragment in requirement["forbidden_meanings"] if fragment not in forbidden_text
                ]
                if missing_forbidden:
                    errors.append(
                        f"plugin governance language policy wording_policy.entity_term_policy.{term}.forbidden_meanings missing: "
                        + ", ".join(missing_forbidden)
                    )

    token_rules = wording_policy.get("forbidden_token_rules")
    if not isinstance(token_rules, list):
        errors.append("plugin governance language policy wording_policy.forbidden_token_rules must be a list")
    else:
        deploy_rule_ok = False
        for rule in token_rules:
            if not isinstance(rule, dict):
                continue
            if rule.get("token") != PLUGIN_GOVERNANCE_FORBIDDEN_TOKEN:
                continue
            if rule.get("status") != "forbidden":
                continue
            entities = rule.get("when_entity_is")
            if not isinstance(entities, list):
                continue
            entity_set = {item for item in entities if isinstance(item, str)}
            if PLUGIN_GOVERNANCE_REQUIRED_ENTITY_TERMS <= entity_set:
                deploy_rule_ok = True
                break
        if not deploy_rule_ok:
            errors.append(
                "plugin governance language policy must forbid token deploy when entity is local_cd or kubernetes_deployment"
            )

    repo_proof = policy.get("repo_proof")
    if not isinstance(repo_proof, dict):
        errors.append("plugin governance language policy repo_proof must be an object")
    else:
        errors.extend(_validate_repo_proof_governed_artifacts(plugin_root, repo_proof))

    errors.extend(
        _find_forbidden_section_keys(
            policy,
            "plugin governance language policy must not contain illustrative sample sections",
        )
    )
    return errors


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _load_bears_sdd_contract(plugin_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = plugin_root / SUBAGENTS_ROLES_CATALOG_FILE
    if not path.is_file():
        return dict(DEFAULT_BEARS_SDD_WORKFLOW_CONTRACT), []

    try:
        constitution = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, [f"cannot parse Bears SDD canonical workflow source {SUBAGENTS_ROLES_CATALOG_FILE}: {exc}"]

    if not isinstance(constitution, dict):
        return None, [f"{SUBAGENTS_ROLES_CATALOG_FILE} root must be an object"]

    contracts = constitution.get(BEARS_SDD_CONTRACT_KEY)
    if not isinstance(contracts, dict):
        return dict(DEFAULT_BEARS_SDD_WORKFLOW_CONTRACT), []

    contract = contracts.get(BEARS_SDD_WORKFLOW_ID)
    if not isinstance(contract, dict):
        return None, [f"{SUBAGENTS_ROLES_CATALOG_FILE} missing {BEARS_SDD_CONTRACT_KEY}.{BEARS_SDD_WORKFLOW_ID}"]

    return contract, []


def _step_text(step: dict[str, Any]) -> str:
    fragments: list[str] = []
    for key in ("id", "type", "command", "message"):
        value = step.get(key)
        if isinstance(value, str):
            fragments.append(value)
    input_value = step.get("input")
    if isinstance(input_value, dict):
        for value in input_value.values():
            if isinstance(value, str):
                fragments.append(value)
    return "\n".join(fragments)


def validate_bears_sdd_workflow_parity(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    contract, contract_errors = _load_bears_sdd_contract(plugin_root)
    errors.extend(contract_errors)
    if contract is None:
        return errors

    required_order = _string_items(contract.get("required_order"))
    if not required_order:
        errors.append(
            f"{SUBAGENTS_ROLES_CATALOG_FILE} {BEARS_SDD_CONTRACT_KEY}.{BEARS_SDD_WORKFLOW_ID}.required_order must be a non-empty string list"
        )
        return errors

    workflow_path = plugin_root / BEARS_SDD_WORKFLOW_FILE
    if not workflow_path.is_file():
        return errors + [f"missing Bears SDD workflow: {BEARS_SDD_WORKFLOW_FILE}"]

    try:
        workflow_payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return errors + [f"cannot parse Bears SDD workflow {BEARS_SDD_WORKFLOW_FILE}: {exc}"]

    if not isinstance(workflow_payload, dict):
        return errors + [f"{BEARS_SDD_WORKFLOW_FILE} must contain a YAML mapping"]

    workflow = workflow_payload.get("workflow")
    if not isinstance(workflow, dict) or workflow.get("id") != BEARS_SDD_WORKFLOW_ID:
        errors.append(f"{BEARS_SDD_WORKFLOW_FILE} workflow.id must be {BEARS_SDD_WORKFLOW_ID}")
    elif isinstance(workflow.get("description"), str):
        description = workflow["description"]
        for fragment in WORKFLOW_DESCRIPTION_FRAGMENTS:
            if fragment not in description:
                errors.append(f"bears-sdd workflow.description missing lifecycle fragment: {fragment}")
        if "route gate → Spec Kit packet → role gate" in description:
            errors.append("bears-sdd workflow.description preserves old route gate to Spec Kit packet wording")

    steps = workflow_payload.get("steps")
    if not isinstance(steps, list):
        return errors + [f"{BEARS_SDD_WORKFLOW_FILE} steps must be a list"]

    step_ids: list[str] = []
    step_by_id: dict[str, dict[str, Any]] = {}
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"{BEARS_SDD_WORKFLOW_FILE} steps[{index}] must be a mapping")
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            errors.append(f"{BEARS_SDD_WORKFLOW_FILE} steps[{index}] missing non-empty id")
            continue
        step_ids.append(step_id)
        step_by_id[step_id] = step

    missing = [step_id for step_id in required_order if step_id not in step_by_id]
    if missing:
        errors.append("bears-sdd workflow missing required gate ids: " + ", ".join(missing))

    ordered_positions = [step_ids.index(step_id) for step_id in required_order if step_id in step_by_id]
    if ordered_positions != sorted(ordered_positions):
        errors.append(
            "bears-sdd workflow gate order does not match canonical lifecycle from "
            f"{SUBAGENTS_ROLES_CATALOG_FILE}"
        )

    inputs = workflow_payload.get("inputs")
    if not isinstance(inputs, dict):
        errors.append(f"{BEARS_SDD_WORKFLOW_FILE} inputs must be a mapping")
    else:
        research_input = inputs.get("research")
        if isinstance(research_input, dict) and "skip" in research_input.get("enum", []):
            missing_inputs = [
                field
                for field in _string_items(contract.get("research_skip_required_inputs"))
                if field not in inputs
            ]
            if missing_inputs:
                errors.append(
                    "bears-sdd workflow research=skip missing required evidence inputs: "
                    + ", ".join(missing_inputs)
                )
            for field in _string_items(contract.get("research_skip_required_inputs")):
                evidence_input = inputs.get(field)
                if not isinstance(evidence_input, dict) or evidence_input.get("required") is not True:
                    errors.append(f"bears-sdd workflow research=skip evidence input must be required: {field}")
                prompt = evidence_input.get("prompt") if isinstance(evidence_input, dict) else ""
                if not isinstance(prompt, str) or "Required when research=skip" not in prompt:
                    errors.append(f"bears-sdd workflow research=skip evidence input prompt must state skip requirement: {field}")

    fragment_map = contract.get("step_required_fragments")
    if not isinstance(fragment_map, dict):
        errors.append(
            f"{SUBAGENTS_ROLES_CATALOG_FILE} {BEARS_SDD_CONTRACT_KEY}.{BEARS_SDD_WORKFLOW_ID}.step_required_fragments must be an object"
        )
        return errors

    for step_id, fragments in fragment_map.items():
        if not isinstance(step_id, str) or not isinstance(fragments, list):
            errors.append("bears-sdd workflow fragment contract entries must map step id to string list")
            continue
        step = step_by_id.get(step_id)
        if step is None:
            continue
        text = _step_text(step)
        for fragment in _string_items(fragments):
            if fragment not in text:
                errors.append(f"bears-sdd workflow step {step_id} missing required fragment: {fragment}")

    if "subagent-execution" in step_by_id:
        subagent_index = step_ids.index("subagent-execution")
        following_steps = [step_by_id[step_id] for step_id in step_ids[subagent_index + 1 :]]
        for step in following_steps:
            if step.get("command") == "speckit.implement":
                text = _step_text(step)
                required = ["bounded delegated execution", "approved tasks.md", "parent-no-implementation"]
                missing_fragments = [fragment for fragment in required if fragment not in text]
                if missing_fragments:
                    errors.append(
                        "bears-sdd speckit.implement after subagent-execution missing delegated-execution wording: "
                        + ", ".join(missing_fragments)
                    )
                if step.get("id") == "implement":
                    errors.append("bears-sdd post-subagent implementation step id must not be generic implement")
                break

    return errors


def validate_governance_markdown_links(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    targets = [plugin_root / path for path in GOVERNANCE_LINK_FILES]
    targets.extend(sorted((plugin_root / "docs/reference").glob("*.md")))
    targets.extend(sorted((plugin_root / "docs/generated").glob("*.md")))
    for path in targets:
        if not path.is_file():
            continue
        rel_path = path.relative_to(plugin_root).as_posix()
        text = path.read_text(encoding="utf-8")
        if "../../contracts/" in text:
            errors.append(f"{rel_path}: external workspace contract link must use repo-local source-boundary doc")
        for match in MARKDOWN_LINK_RE.finditer(text):
            raw_target = match.group(1).split()[0].strip()
            target = raw_target.split("#", 1)[0]
            if not target or target.startswith(("#", "http://", "https://", "mailto:", "app://")):
                continue
            if target.startswith("/") or "{{" in target:
                continue
            if target.startswith("../.."):
                errors.append(f"{rel_path}: markdown link escapes repository root: {raw_target}")
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(plugin_root.resolve())
            except ValueError:
                errors.append(f"{rel_path}: markdown link escapes repository root: {raw_target}")
                continue
            if not resolved.exists():
                errors.append(f"{rel_path}: markdown link target missing: {raw_target}")
    return errors



def validate_canonical_owner_assets(plugin_root: Path) -> list[str]:
    errors: list[str] = []

    for relative in sorted(REQUIRED_CANONICAL_FILES):
        if not (plugin_root / relative).is_file():
            errors.append(f"missing canonical owner file: {relative}")

    catalog_path = plugin_root / "assets/catalog/platform-role-catalog.v1.json"
    if not catalog_path.is_file():
        return errors

    try:
        catalog = json.loads(catalog_path.read_text())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"cannot parse subagents roles catalog: {exc}")
        return errors

    if not isinstance(catalog, dict):
        errors.append("subagents roles catalog root must be an object")
        return errors

    if catalog.get("schema") != "bears-platform-role-catalog.v1":
        errors.append("subagents roles catalog schema must be bears-platform-role-catalog.v1")
    if catalog.get("owner_plugin") != "bears":
        errors.append("subagents roles catalog owner_plugin must be bears")
    errors.extend(validate_plugin_governance_language_policy(plugin_root))
    errors.extend(validate_governance_markdown_links(plugin_root))

    role_names = {
        role.get("name")
        for role in catalog.get("roles", [])
        if isinstance(role, dict) and isinstance(role.get("name"), str)
    }
    missing_roles = sorted(REQUIRED_CANONICAL_ROLES - role_names)
    if missing_roles:
        errors.append("subagents roles catalog missing canonical roles: " + ", ".join(missing_roles))

    part_names = {
        part.get("name")
        for part in catalog.get("platform_parts", [])
        if isinstance(part, dict) and isinstance(part.get("name"), str)
    }
    missing_parts = sorted(REQUIRED_CANONICAL_PARTS - part_names)
    if missing_parts:
        errors.append("subagents roles catalog missing canonical parts: " + ", ".join(missing_parts))

    workflow_routes = [
        route
        for route in catalog.get("workflow_routes", [])
        if isinstance(route, dict) and route.get("workflow_id") == "auth-gateway-deploy-core"
    ]
    if not workflow_routes:
        errors.append("subagents roles catalog missing auth-gateway-deploy-core workflow route")
    else:
        ordered_parts = workflow_routes[0].get("ordered_parts")
        if ordered_parts != ["auth_core", "bears_gateway", "cd_deploy_stage"]:
            errors.append(
                "auth-gateway-deploy-core ordered_parts must be auth_core -> bears_gateway -> cd_deploy_stage"
            )

    readiness_path = plugin_root / "assets/catalog/auth-gateway-deploy-readiness.v1.json"
    if readiness_path.is_file():
        try:
            readiness = json.loads(readiness_path.read_text())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot parse auth/gateway/deploy readiness packet: {exc}")
        else:
            if not isinstance(readiness, dict):
                errors.append("auth/gateway/deploy readiness packet root must be an object")
            else:
                if readiness.get("schema") != "bears-auth-gateway-deploy-readiness.v1":
                    errors.append("auth/gateway/deploy readiness schema must be bears-auth-gateway-deploy-readiness.v1")
                if readiness.get("owner_plugin") != "bears":
                    errors.append("auth/gateway/deploy readiness owner_plugin must be bears")
                if readiness.get("workflow_id") != "auth-gateway-deploy-core":
                    errors.append("auth/gateway/deploy readiness workflow_id must be auth-gateway-deploy-core")
                if readiness.get("ordered_spine") != ["auth_core", "bears_gateway", "cd_deploy_stage"]:
                    errors.append("auth/gateway/deploy readiness ordered_spine must be auth_core -> bears_gateway -> cd_deploy_stage")
                neutral_core_paths = {
                    "auth_core": "/srv/bears/dev/platform/src/bears_platform/auth",
                    "bears_gateway": "/srv/bears/dev/platform/src/bears_platform/gateway",
                    "cd_deploy_stage": "/srv/bears/dev/platform/src/bears_platform/deploy",
                }
                expected_repo_root = "/srv/bears/dev/platform"
                seller_root = "projects/seller/apps/"
                for surface in readiness.get("surfaces", []):
                    if not isinstance(surface, dict):
                        continue
                    surface_name = surface.get("surface")
                    expected_path = neutral_core_paths.get(surface_name)
                    if expected_path is None:
                        continue
                    for field_name in ("canonical_path", "route_target"):
                        if surface.get(field_name) != expected_path:
                            errors.append(
                                f"auth/gateway/deploy readiness {surface_name}.{field_name} must use neutral core path {expected_path}"
                            )
                        value = surface.get(field_name)
                        if isinstance(value, str) and seller_root in value:
                            errors.append(
                                f"auth/gateway/deploy readiness {surface_name}.{field_name} must not use seller path"
                            )
                    for command in surface.get("safe_validation_commands", []):
                        if isinstance(command, str) and seller_root in command:
                            errors.append(
                                f"auth/gateway/deploy readiness {surface_name}.safe_validation_commands must not require seller path"
                            )
                    repo_artifacts = surface.get("repo_artifacts")
                    if not isinstance(repo_artifacts, dict):
                        errors.append(f"auth/gateway/deploy readiness {surface_name}.repo_artifacts must be an object")
                    elif repo_artifacts.get("repo_root") != expected_repo_root:
                        errors.append(
                            f"auth/gateway/deploy readiness {surface_name}.repo_artifacts.repo_root must be {expected_repo_root}"
                        )

    session_runtime_path = plugin_root / "assets/catalog/session-workers-runtime.v1.json"
    session_runtime_script_path = plugin_root / "scripts/session_workers_runtime.py"
    if session_runtime_path.is_file() and session_runtime_script_path.is_file() and catalog_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("session_workers_runtime", session_runtime_script_path)
        if spec is None or spec.loader is None:
            errors.append("cannot load session worker runtime validator module")
        else:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[arg-type]
            try:
                session_runtime = module.load_json(session_runtime_path)
                role_catalog = module.load_json(catalog_path)
                errors.extend(module.validate_catalog(session_runtime, role_catalog))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"cannot validate session worker runtime catalog: {exc}")

    role_gate_methodology_path = plugin_root / "assets/catalog/role-gate-methodology.v1.json"
    role_gate_methodology_script_path = plugin_root / "scripts/role_gate_methodology.py"
    if role_gate_methodology_path.is_file() and role_gate_methodology_script_path.is_file() and catalog_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("role_gate_methodology", role_gate_methodology_script_path)
        if spec is None or spec.loader is None:
            errors.append("cannot load role gate methodology validator module")
        else:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[arg-type]
            try:
                methodology = module.load_json(role_gate_methodology_path)
                role_catalog = module.load_json(catalog_path)
                errors.extend(module.validate_methodology(methodology))
                errors.extend(module.validate_catalog_alignment(methodology, role_catalog, plugin_root=plugin_root))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"cannot validate role gate methodology catalog: {exc}")

    try:
        import importlib.util

        script_path = plugin_root / "scripts" / "skill_catalog.py"
        catalog_path = plugin_root / "assets/catalog/plugin-skill-catalog.v1.json"
        spec = importlib.util.spec_from_file_location("skill_catalog", script_path)
        if spec is None or spec.loader is None:
            errors.append("cannot load scripts/skill_catalog.py")
        else:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[arg-type]
            skill_catalog = module.load_catalog(catalog_path)
            errors.extend(module.validate_catalog(skill_catalog, plugin_root))
            errors.extend(module.generate(skill_catalog, plugin_root, check=True))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"skill catalog validation failed: {exc}")

    subagent_policy_path = plugin_root / "assets/catalog/subagent-orchestration-policy.v1.json"
    subagent_policy_script_path = plugin_root / "scripts/subagent_orchestration_policy.py"
    if subagent_policy_path.is_file() and subagent_policy_script_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("subagent_orchestration_policy", subagent_policy_script_path)
        if spec is None or spec.loader is None:
            errors.append("cannot load subagent orchestration policy validator module")
        else:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[arg-type]
            try:
                policy = module.load_json(subagent_policy_path)
                errors.extend(module.validate_policy(policy))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"cannot validate subagent orchestration policy: {exc}")

    return errors


def validate_workspace_role_gate_references(workspace_root: Path) -> list[str]:
    """Ensure shared dev-core docs point to the canonical Bears role gate."""

    errors: list[str] = []

    for relative, required_fragments in sorted(REQUIRED_WORKSPACE_ROLE_GATE_REFERENCES.items()):
        path = workspace_root / relative
        if not path.exists():
            continue
        if not path.is_file():
            errors.append(f"workspace role gate reference path is not a file: {relative}")
            continue

        text = path.read_text()
        for fragment in required_fragments:
            if fragment not in text:
                errors.append(f"{relative}: missing canonical role gate reference: {fragment}")
        for fragment in FORBIDDEN_SHARED_ROLE_GATE_REFERENCES:
            if fragment in text:
                errors.append(f"{relative}: stale shared role gate reference must move to plugins/bears: {fragment}")

    return errors


def _manifest_field_value(manifest: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = manifest
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_string_values(item))
        return strings
    return []


def _field_path_label(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _is_safe_prohibition(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in SAFE_PROHIBITION_MARKERS)


def _has_approved_secret_factory_term(text: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in MANIFEST_APPROVED_SECRET_FACTORY_TERMS)


def validate_manifest_visible_text(manifest: dict[str, Any]) -> list[str]:
    """Validate user-visible manifest text without blocking governed Secret Factory terms."""

    errors: list[str] = []
    for path in MANIFEST_VISIBLE_FIELD_PATHS:
        value = _manifest_field_value(manifest, path)
        strings = _string_values(value)
        if not strings:
            errors.append(f"plugin manifest visible field missing or non-string: {_field_path_label(path)}")
            continue
        for item in strings:
            item_has_secret_or_credential_term = "secret" in item.casefold() or "credential" in item.casefold()
            for pattern in MANIFEST_FORBIDDEN_CLAIM_PATTERNS:
                if not pattern.search(item):
                    continue
                if _is_safe_prohibition(item):
                    continue
                errors.append(
                    "plugin manifest user-visible field has unsafe secret or credential wording: "
                    f"{_field_path_label(path)}"
                )
                break
            else:
                if (
                    item_has_secret_or_credential_term
                    and not _has_approved_secret_factory_term(item)
                    and not _is_safe_prohibition(item)
                ):
                    errors.append(
                        "plugin manifest user-visible field has unapproved secret or credential wording: "
                        f"{_field_path_label(path)}"
                    )
    return errors


def classify_secret_discovery_path(path: str) -> str:
    """Classify secret-discovery paths without returning credential-bearing path names."""

    normalized = path.strip()
    if not normalized:
        return "FORBIDDEN_CREDENTIAL_FILE_PATH"
    if SAFE_DISCOVERY_WRAPPER_RE.search(normalized):
        return "SAFE_WRAPPER_PATH"
    if SAFE_DISCOVERY_CONTRACT_RE.search(normalized):
        return "SAFE_CONTRACT_PATH"
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", normalized):
        return "SECRET_REF_NAME"
    if CREDENTIAL_PATH_RE.search(normalized):
        return "FORBIDDEN_CREDENTIAL_FILE_PATH"
    return "UNAPPROVED_DISCOVERY_PATH"


def secret_discovery_closeout(paths: list[str]) -> dict[str, Any]:
    """Build count-only secret-discovery closeout data."""

    counts: dict[str, int] = {}
    for path in paths:
        category = classify_secret_discovery_path(path)
        counts[category] = counts.get(category, 0) + 1
    blocked = counts.get("FORBIDDEN_CREDENTIAL_FILE_PATH", 0) + counts.get("UNAPPROVED_DISCOVERY_PATH", 0)
    return {
        "status": "SECRET_DISCOVERY_STOP" if blocked else "OK",
        "count_only": True,
        "class_counts": counts,
        "printed_paths": False,
    }


def redact_inventory_output(text: str) -> tuple[str, int]:
    """Redact credential-bearing URI defaults before inventory output can be printed."""

    count = 0

    def _replace(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return "<REDACTED_CREDENTIAL_URI>"

    return SENSITIVE_URI_RE.sub(_replace, text), count


def scan_inventory_output(relative_path: str, text: str) -> dict[str, Any]:
    """Return a bounded inventory-output packet with redacted content and drift status."""

    redacted, redaction_count = redact_inventory_output(text)
    sensitive_path = bool(INVENTORY_SENSITIVE_PATH_RE.search(relative_path))
    line_findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        _redacted_line, line_count = redact_inventory_output(line)
        if line_count:
            line_findings.append(
                {
                    "line": line_number,
                    "category": "credential_uri_default",
                    "issue_flow": STATIC_LITERAL_POLICY["issue_flow"],
                }
            )
    if sensitive_path:
        line_findings.append(
            {
                "line": 0,
                "category": "sensitive_inventory_path",
                "issue_flow": STATIC_LITERAL_POLICY["issue_flow"],
            }
        )
    status = "SENSITIVE_OUTPUT_STOP" if redaction_count or sensitive_path else "OK"
    return {
        "status": status,
        "path": relative_path,
        "redaction_count": redaction_count,
        "line_only_issue_flow": bool(line_findings),
        "line_findings": line_findings,
        "safe_excerpt": redacted,
    }


def classify_live_tool_mention(text: str) -> str:
    """Classify live-tool mentions before a PR safety scan can fail."""

    lowered = text.casefold()
    if any(marker in lowered for marker in ("do not", "must not", "disabled", "blocked", "forbidden", "no live")):
        return "prohibition"
    if "names-only" in lowered or "names only" in lowered:
        return "names_only_reference"
    if "dry-run" in lowered or "dry run" in lowered:
        return "dry_run_only"
    if "validate" in lowered or "validator" in lowered or "test " in lowered:
        return "validation_command"
    if any(marker in lowered for marker in ("apply", "mutate", "mutation", "send", "write", "create", "delete")):
        return "mutation_instruction"
    return "unclassified"


def live_tool_pr_safety_gate(texts: list[str]) -> dict[str, Any]:
    """Return class-count PR safety data for live-tool wording."""

    counts: dict[str, int] = {}
    for text in texts:
        category = classify_live_tool_mention(text)
        counts[category] = counts.get(category, 0) + 1
    blocked = counts.get("mutation_instruction", 0) + counts.get("unclassified", 0)
    return {
        "status": "LIVE_TOOL_SAFETY_STOP" if blocked else "OK",
        "count_only": True,
        "class_counts": counts,
        "printed_text": False,
    }


def _allowed_static_literal(text: str) -> bool:
    lowered = text.casefold()
    return any(sentinel.casefold() in lowered for sentinel in APPROVED_STATIC_LITERAL_SENTINELS)


def classify_static_safety_plane(relative_path: str) -> str:
    normalized = relative_path.casefold()
    if any(marker in normalized for marker in ("yandex360", "dns", "network", "infrastructure")):
        return "infrastructure_network_governance"
    if any(marker in normalized for marker in ("secret-factory", "secret_factory", "infisical")):
        return "secret_factory_governance"
    return "workflow_overlay_governance"


def scan_static_safety_text(relative_path: str, text: str) -> list[dict[str, Any]]:
    """Scan changed static text for raw endpoint, URL, IP, and CIDR literals."""

    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _allowed_static_literal(line):
            continue
        for pattern, category in (
            (RAW_URL_RE, "raw_endpoint_literal"),
            (RAW_IPV4_OR_CIDR_RE, "raw_ip_or_cidr_literal"),
        ):
            if not pattern.search(line):
                continue
            redacted = pattern.sub(f"<{category}>", line)
            findings.append(
                {
                    "path": relative_path,
                    "line": line_number,
                    "category": category,
                    "plane": classify_static_safety_plane(relative_path),
                    "excerpt": redacted.strip(),
                    "policy_scope": STATIC_LITERAL_POLICY["scope"],
                }
            )
            break
    return findings


def scan_static_safety_paths(plugin_root: Path, paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        candidate = path if path.is_absolute() else plugin_root / path
        try:
            relative = candidate.resolve().relative_to(plugin_root.resolve()).as_posix()
        except ValueError:
            errors.append(f"static safety scan path must stay inside plugin root: {path}")
            continue
        if not candidate.is_file():
            errors.append(f"static safety scan path is not a file: {relative}")
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_static_safety_text(relative, text))
    return findings, errors


def static_safety_pr_gate(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Return compact action JSON for the required static safety PR gate."""

    category_counts = {category: 0 for category in STATIC_LITERAL_REQUIRED_CATEGORIES}
    plane_counts = {plane: 0 for plane in STATIC_SAFETY_REQUIRED_PLANES}
    for finding in findings:
        category = str(finding.get("category", "unknown"))
        category_counts[category] = category_counts.get(category, 0) + 1
        plane = str(finding.get("plane", "workflow_overlay_governance"))
        plane_counts[plane] = plane_counts.get(plane, 0) + 1
    blocked = any(count for count in category_counts.values())
    return {
        "status": "STATIC_SAFETY_STOP" if blocked else "OK",
        "required_gate": STATIC_LITERAL_POLICY["required_gate"],
        "compact_action_json": {
            "action": "open_line_only_issue" if blocked else "none",
            "issue_flow": STATIC_LITERAL_POLICY["issue_flow"],
            "category_counts": category_counts,
            "plane_counts": plane_counts,
            "required_categories": list(STATIC_LITERAL_REQUIRED_CATEGORIES),
            "required_planes": list(STATIC_SAFETY_REQUIRED_PLANES),
        },
    }


def abuse_probe_publication_gate(probe_packet: dict[str, Any]) -> dict[str, Any]:
    """Gate PR publication until required negative abuse probes are represented."""

    missing = [
        field
        for field in ABUSE_PROBE_REQUIRED_FIELDS
        if probe_packet.get(field) != "pass"
    ]
    return {
        "status": "ABUSE_PROBE_PUBLICATION_STOP" if missing else "OK",
        "required_fields": list(ABUSE_PROBE_REQUIRED_FIELDS),
        "missing_or_not_pass": missing,
        "publish_allowed": not missing,
    }


def validate_static_safety_gate(plugin_root: Path) -> list[str]:
    """Validate repo-owned static safety gate wiring."""

    errors: list[str] = []
    policy_categories = set(STATIC_LITERAL_REQUIRED_CATEGORIES)
    if not {"raw_endpoint_literal", "raw_ip_or_cidr_literal"}.issubset(policy_categories):
        errors.append("static safety gate missing required endpoint and CIDR categories")
    if not set(STATIC_SAFETY_REQUIRED_PLANES).issuperset(
        {"secret_factory_governance", "infrastructure_network_governance"}
    ):
        errors.append("static safety gate missing Secret Factory and infrastructure network planes")
    if STATIC_LITERAL_POLICY.get("required_gate") != "validate_overlay_static_safety_pr_gate":
        errors.append("static safety gate must be enforced as validate_overlay_static_safety_pr_gate")
    if STATIC_LITERAL_POLICY.get("issue_flow") != "line_only_redacted_issue":
        errors.append("static safety gate issue_flow must be line_only_redacted_issue")
    for rel_path in ("docs/reference/secret-factory.md", "skills/secret-factory/SKILL.md"):
        target = plugin_root / rel_path
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        for required in ("scan-static-safety", "raw_endpoint_literal", "raw_ip_or_cidr_literal"):
            if required not in text:
                errors.append(f"{rel_path} missing static safety gate marker {required}")
    return errors

def validate_manifest(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        return [f"missing manifest at {manifest_path}"]

    for forbidden in (".app.json", ".mcp.json"):
        if (plugin_root / forbidden).exists():
            errors.append(f"forbidden file present: {forbidden}")

    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:  # noqa: BLE001
        return [f"cannot parse plugin manifest: {exc}"]

    if manifest.get("name") != "bears":
        errors.append("plugin manifest name must be 'bears'")

    skills_value = manifest.get("skills")
    if skills_value != "./skills/":
        errors.append("plugin manifest 'skills' must be './skills/'")

    errors.extend(validate_manifest_visible_text(manifest))

    return errors


def _load_issue_template_yaml(path: Path) -> tuple[Any | None, str | None]:
    try:
        return yaml.safe_load(path.read_text()), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def validate_issue_templates(plugin_root: Path) -> list[str]:
    """Validate GitHub issue-form intake coverage for governance work."""

    errors: list[str] = []
    template_root = plugin_root / ".github" / "ISSUE_TEMPLATE"
    config_path = template_root / "config.yml"

    if not template_root.is_dir():
        return ["missing GitHub issue template directory: .github/ISSUE_TEMPLATE"]

    config, config_error = _load_issue_template_yaml(config_path)
    if config_error is not None:
        errors.append(f"cannot parse issue template config.yml: {config_error}")
    elif not isinstance(config, dict):
        errors.append("issue template config.yml root must be an object")
    else:
        if not isinstance(config.get("blank_issues_enabled"), bool):
            errors.append("issue template config.yml blank_issues_enabled must be boolean")

    form_paths = sorted(
        path
        for path in template_root.glob("*.yml")
        if path.name != "config.yml"
    ) + sorted(template_root.glob("*.yaml"))

    if not form_paths:
        errors.append("missing GitHub issue form files under .github/ISSUE_TEMPLATE")
        return errors

    governance_form_found = False
    for path in form_paths:
        relative = path.relative_to(plugin_root).as_posix()
        form, form_error = _load_issue_template_yaml(path)
        if form_error is not None:
            errors.append(f"cannot parse issue form {relative}: {form_error}")
            continue
        if not isinstance(form, dict):
            errors.append(f"{relative}: issue form root must be an object")
            continue

        for key in ("name", "description", "body"):
            if key not in form:
                errors.append(f"{relative}: missing required top-level key {key}")
        body = form.get("body")
        if not isinstance(body, list):
            errors.append(f"{relative}: body must be a list")
            continue

        fields: dict[str, dict[str, Any]] = {
            item.get("id"): item
            for item in body
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }

        if REQUIRED_ISSUE_FORM_FIELDS <= set(fields):
            governance_form_found = True

        missing = sorted(REQUIRED_ISSUE_FORM_FIELDS - set(fields))
        if missing:
            errors.append(f"{relative}: missing governance intake fields: {', '.join(missing)}")
            continue

        for field_id in sorted(REQUIRED_ISSUE_FORM_REQUIRED_FIELDS):
            validations = fields[field_id].get("validations")
            if not isinstance(validations, dict) or validations.get("required") is not True:
                errors.append(f"{relative}: field {field_id} must be required")

        safety = fields["restricted_data_safety"]
        if safety.get("type") != "checkboxes":
            errors.append(f"{relative}: restricted_data_safety must be checkboxes")
        options = safety.get("attributes", {}).get("options") if isinstance(safety.get("attributes"), dict) else None
        if not isinstance(options, list) or not options:
            errors.append(f"{relative}: restricted_data_safety must define required options")
        else:
            if not any(isinstance(option, dict) and option.get("required") is True for option in options):
                errors.append(f"{relative}: restricted_data_safety must require a confirmation option")
            safety_text = " ".join(
                str(option.get("label", ""))
                for option in options
                if isinstance(option, dict)
            ).lower()
            for term in ("secrets", "raw logs", "raw env", "production data"):
                if term not in safety_text:
                    errors.append(f"{relative}: restricted_data_safety must mention {term}")

    if not governance_form_found:
        errors.append("missing governance issue form with required intake fields")

    return errors


def validate_no_tracked_generated_specify(plugin_root: Path) -> list[str]:
    """Fail when generated .specify state is tracked as plugin source."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(plugin_root),
                "ls-files",
                "-z",
                "--",
                ".specify",
            ],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return [f"cannot inspect tracked .specify files: {exc}"]

    if result.returncode != 0:
        return []

    tracked = [
        item.decode("utf-8", errors="replace")
        for item in result.stdout.split(b"\0")
        if item
    ]
    if not tracked:
        return []

    return [
        "generated .specify files must not be tracked as plugin source: "
        f"{len(tracked)} tracked path(s)"
    ]


def validate_skill_boundary(plugin_root: Path, strict: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    skills_root = plugin_root / "skills"
    if not skills_root.exists():
        return ["missing skills directory"], []

    violations = [
        path.name
        for path in skills_root.iterdir()
        if path.is_dir()
        and path.name.startswith("speckit-")
        and not path.name.startswith("speckit-bears-")
    ]

    if violations:
        message = "upstream core speckit-* skill dirs found: " + ", ".join(sorted(violations))
        if strict:
            errors.append(message)
        else:
            warnings.append(message + " (allowed in non-strict advisory mode)")

    return errors, warnings


def validate_agent_tomls(agents_root: Path) -> list[str]:
    errors: list[str] = []

    tomls = sorted(agents_root.glob("*.toml"))
    if not tomls:
        return ["no agent role TOML files found under agents/"]

    actual_names = {path.name for path in tomls}
    matrix_names = set(AGENT_SANDBOX_MODE_MATRIX)
    if actual_names & matrix_names and agents_root.resolve() == (Path(__file__).resolve().parents[1] / "agents"):
        missing_from_matrix = sorted(actual_names - matrix_names)
        missing_from_agents = sorted(matrix_names - actual_names)
        if missing_from_matrix:
            errors.append(
                "agent sandbox matrix missing TOML entries: " + ", ".join(missing_from_matrix)
            )
        if missing_from_agents:
            errors.append(
                "agent sandbox matrix lists missing TOMLs: " + ", ".join(missing_from_agents)
            )

    for path in tomls:
        try:
            data = _load_toml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cannot parse TOML {path}: {exc}")
            continue

        for field in REQUIRED_TOML_FIELDS:
            if field not in data:
                errors.append(f"{path}: missing required field '{field}'")
            elif not isinstance(data[field], str) or not data[field].strip():
                errors.append(f"{path}: required field '{field}' must be a non-empty string")

        expected_sandbox = AGENT_SANDBOX_MODE_MATRIX.get(path.name)
        if expected_sandbox and data.get("sandbox_mode") != expected_sandbox:
            errors.append(
                f"{path}: sandbox_mode must be '{expected_sandbox}' per agents/README.md matrix"
            )

        instructions = data.get("developer_instructions")
        if isinstance(instructions, str):
            for section in REQUIRED_AGENT_INSTRUCTION_SECTIONS:
                if section not in instructions:
                    errors.append(f"{path}: developer_instructions missing section '{section}'")
            if data.get("sandbox_mode") == "read-only":
                for marker in READ_ONLY_AGENT_SAFETY_MARKERS:
                    if marker not in instructions:
                        errors.append(
                            f"{path}: read-only developer_instructions missing marker '{marker}'"
                        )

    return errors


def _load_schema(schema_root: Path, artifact: str) -> dict[str, Any]:
    schema_path = schema_root / SCHEMA_FILES[artifact]
    if not schema_path.exists():
        raise FileNotFoundError(f"schema missing: {schema_path}")
    return json.loads(schema_path.read_text())


def _governance_dir(feature_dir: Path) -> Path:
    if feature_dir.name == "governance":
        return feature_dir

    candidate = feature_dir / "governance"
    if candidate.exists():
        if not candidate.is_dir():
            return candidate
        return candidate

    return feature_dir


def _feature_root(feature_dir: Path) -> Path:
    if feature_dir.name == "governance":
        return feature_dir.parent
    return feature_dir


def _role_coverage_markers(role_coverage_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    markers: list[str] = []

    if not role_coverage_path.exists():
        return markers, errors

    try:
        payload = json.loads(role_coverage_path.read_text())
    except Exception as exc:  # noqa: BLE001
        return markers, [f"cannot parse role coverage for Spec Kit binding: {role_coverage_path}: {exc}"]

    if not isinstance(payload, dict):
        return markers, ["role coverage artifact must be an object for Spec Kit binding"]

    route_target = payload.get("route_target")
    if isinstance(route_target, str) and route_target.strip():
        markers.append(route_target)

    roles = payload.get("roles")
    if isinstance(roles, list):
        for role in roles:
            if not isinstance(role, dict):
                continue
            name = role.get("name")
            if isinstance(name, str) and name.strip():
                markers.append(name)

    return markers, errors


def _expected_spec_kit_paths(feature_root: Path) -> dict[str, str]:
    return {
        field: str((feature_root / file_name).resolve())
        for field, file_name in SPEC_KIT_ANALYZE_FIELDS.items()
    }


def _validate_spec_kit_analyze_artifact(
    artifact_dir: Path,
    expected_paths: dict[str, str],
    require_artifacts: bool,
) -> list[str]:
    analyze_path = artifact_dir / SPEC_KIT_ANALYZE_ARTIFACT
    if not analyze_path.exists():
        if require_artifacts:
            return [f"missing required Spec Kit analyze artifact: {analyze_path}"]
        return []

    try:
        payload = json.loads(analyze_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"invalid Spec Kit analyze JSON in {analyze_path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"Spec Kit analyze artifact must be an object: {analyze_path}"]

    errors: list[str] = []
    if payload.get("schema") != SPEC_KIT_ANALYZE_SCHEMA:
        errors.append(f"{SPEC_KIT_ANALYZE_ARTIFACT}.schema must be {SPEC_KIT_ANALYZE_SCHEMA}")
    status = payload.get("status")
    if not isinstance(status, str) or status.casefold() != "pass":
        errors.append(f"{SPEC_KIT_ANALYZE_ARTIFACT}.status must be PASS")

    for field, expected in expected_paths.items():
        if payload.get(field) != expected:
            errors.append(f"{SPEC_KIT_ANALYZE_ARTIFACT}.{field} must match current file: {expected}")

    return errors


def _validate_spec_kit_gate(feature_dir: Path, artifact_dir: Path, require_artifacts: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    feature_root = _feature_root(feature_dir)

    missing_spec_files = [
        str(feature_root / file_name)
        for file_name in REQUIRED_SPEC_KIT_FILES
        if not (feature_root / file_name).is_file()
    ]
    if missing_spec_files:
        message = "missing required Spec Kit artifact: "
        if require_artifacts:
            errors.extend(message + path for path in missing_spec_files)
        else:
            warnings.extend(message + path for path in missing_spec_files)
        return errors, warnings

    tasks_path = feature_root / "tasks.md"
    try:
        tasks_text = tasks_path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return [f"cannot read Spec Kit tasks artifact {tasks_path}: {exc}"], warnings

    role_markers, role_errors = _role_coverage_markers(artifact_dir / "role-coverage.json")
    errors.extend(role_errors)
    tasks_lower = tasks_text.casefold()

    if role_markers and not any(marker.casefold() in tasks_lower for marker in role_markers):
        errors.append("Spec Kit tasks.md must mention the route_target or primary role from role-coverage.json")

    has_restricted_mutation = any(marker in tasks_lower for marker in RESTRICTED_MUTATION_MARKERS)
    has_approval = any(marker in tasks_lower for marker in APPROVAL_MARKERS)
    if has_restricted_mutation and not has_approval:
        errors.append("Spec Kit tasks.md mentions restricted mutation without operator approval evidence")

    errors.extend(
        _validate_spec_kit_analyze_artifact(
            artifact_dir,
            _expected_spec_kit_paths(feature_root),
            require_artifacts,
        )
    )

    return errors, warnings


def validate_feature_artifacts(feature_dir: Path, schema_root: Path, require_artifacts: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not feature_dir.exists():
        if require_artifacts:
            return [f"feature dir does not exist: {feature_dir}"], []
        return [], [f"feature dir does not exist (advisory): {feature_dir}"]

    artifact_dir = _governance_dir(feature_dir)
    if artifact_dir.exists() and not artifact_dir.is_dir():
        return [f"governance path is not a directory: {artifact_dir}"], []

    spec_errors, spec_warnings = _validate_spec_kit_gate(feature_dir, artifact_dir, require_artifacts)
    errors.extend(spec_errors)
    warnings.extend(spec_warnings)

    for artifact, file_name in ARTIFACT_FILES.items():
        schema = _load_schema(schema_root, artifact)
        path = artifact_dir / file_name
        if not path.exists():
            continue

        try:
            payload = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{artifact}: invalid JSON in {path}: {exc}")
            continue

        errors.extend(_validate_schema_instance(payload, schema, artifact))

    if require_artifacts:
        for artifact, file_name in ARTIFACT_FILES.items():
            path = artifact_dir / file_name
            if not path.exists():
                errors.append(f"missing required governance artifact: {path}")

    return errors, warnings


def validate_extensions(workspace_root: Path) -> list[str]:
    messages: list[str] = []
    extensions_file = workspace_root / ".specify" / "extensions.yml"
    if not extensions_file.exists():
        messages.append(f"missing required file: {extensions_file}")
        return messages

    try:
        extensions = yaml.safe_load(extensions_file.read_text())
    except Exception as exc:  # noqa: BLE001
        return [f"cannot parse extensions file {extensions_file}: {exc}"]

    if not isinstance(extensions, dict):
        return [f"extensions file {extensions_file} must contain a YAML mapping"]

    hooks = extensions.get("hooks")
    if not isinstance(hooks, dict):
        return [f"extensions file {extensions_file}: top-level 'hooks' must be a mapping"]

    missing_groups = sorted(REQUIRED_EXTENSION_HOOK_GROUPS - set(hooks))
    if missing_groups:
        messages.append(f"extensions file {extensions_file} is missing required hook groups: {', '.join(missing_groups)}")

    for group_name in sorted(REQUIRED_EXTENSION_HOOK_GROUPS):
        hooks_for_group = hooks.get(group_name)
        if not isinstance(hooks_for_group, list):
            messages.append(f"extensions hook group '{group_name}' must be a list")
            continue

        for index, hook in enumerate(hooks_for_group):
            if not isinstance(hook, dict):
                messages.append(
                    f"extensions hook '{group_name}[{index}]' must be a mapping",
                )
                continue

            if group_name in HARD_EXTENSION_HOOK_GROUPS:
                for flag, expected in HARD_EXTENSION_FLAGS.items():
                    value = hook.get(flag)
                    if value is not expected:
                        messages.append(
                            f"extensions hook '{group_name}[{index}]' must set '{flag}: false' for hard gate mode",
                        )
                continue

            for flag in ADVISORY_EXTENSION_FLAGS:
                value = hook.get(flag)
                if value is not True:
                    messages.append(
                        f"extensions hook '{group_name}[{index}]' must set '{flag}: true' for advisory mode",
                    )
    return messages


def _collect_source_skills(source: Path) -> list[str]:
    if not source.exists() or not source.is_dir():
        return []
    return sorted([
        path.name
        for path in source.iterdir()
        if path.is_dir() and path.name.startswith("speckit-") and not path.name.startswith("speckit-bears-")
    ])


def detect_duplicate_skill_sources(skill_sources: list[Path]) -> dict[str, list[Path]]:
    source_hits: dict[str, list[Path]] = {}

    for source in skill_sources:
        for skill in _collect_source_skills(source):
            source_hits.setdefault(skill, []).append(source)

    duplicates: dict[str, list[Path]] = {
        skill: paths for skill, paths in source_hits.items() if len(paths) > 1
    }
    return duplicates


def check_duplicate_sources(skill_sources: list[Path], fail_on_duplicates: bool = True) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    duplicates = detect_duplicate_skill_sources(skill_sources)
    if not duplicates:
        return errors, warnings

    lines = []
    for skill, paths in sorted(duplicates.items()):
        lines.append(f"{skill}: {', '.join(str(p) for p in paths)}")

    message = "duplicate upstream core skill sources detected:\n" + "\n".join(lines)
    if fail_on_duplicates:
        errors.append(message)
    else:
        warnings.append(message)

    return errors, warnings


def _resolve_workspace_root(
    plugin_root: Path,
    workspace_root: Path | None = None,
) -> Path:
    if workspace_root is not None:
        return workspace_root

    default_plugin_root = Path(__file__).resolve().parents[1]
    if (
        plugin_root == default_plugin_root
        and plugin_root.name == "bears"
        and plugin_root.parent.name == "plugins"
    ):
        return default_plugin_root.parent.parent

    if plugin_root.name == "bears" and plugin_root.parent.name == "plugins":
        return plugin_root.parent.parent

    return plugin_root


def validate_all(
    plugin_root: Path,
    workspace_root: Path | None = None,
    feature_dir: Path | None = None,
    strict_overlay_skills: bool = False,
    require_artifacts: bool = False,
    skill_sources: list[Path] | None = None,
) -> tuple[int, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    resolved_workspace_root = _resolve_workspace_root(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
    )

    errors.extend(validate_manifest(plugin_root))
    errors.extend(validate_issue_templates(plugin_root))
    errors.extend(validate_no_tracked_generated_specify(plugin_root))

    boundary_errors, boundary_warnings = validate_skill_boundary(
        plugin_root,
        strict=strict_overlay_skills,
    )
    errors.extend(boundary_errors)
    warnings.extend(boundary_warnings)

    errors.extend(validate_agent_tomls(plugin_root / "agents"))
    errors.extend(validate_canonical_owner_assets(plugin_root))
    errors.extend(validate_bears_sdd_workflow_parity(plugin_root))
    errors.extend(validate_static_safety_gate(plugin_root))

    if feature_dir is not None:
        artifact_errors, artifact_warnings = validate_feature_artifacts(
            feature_dir=feature_dir,
            schema_root=plugin_root / "schemas",
            require_artifacts=require_artifacts,
        )
        errors.extend(artifact_errors)
        warnings.extend(artifact_warnings)

    workspace_checks_enabled = (
        workspace_root is not None
        or resolved_workspace_root != plugin_root
    )
    if workspace_checks_enabled:
        errors.extend(validate_extensions(resolved_workspace_root))
        errors.extend(validate_workspace_role_gate_references(resolved_workspace_root))

    if skill_sources:
        dup_errors, dup_warnings = check_duplicate_sources(skill_sources, fail_on_duplicates=True)
        errors.extend(dup_errors)
        warnings.extend(dup_warnings)

    return len(errors), errors, warnings


def _run_validate(args: argparse.Namespace) -> int:
    feature_dir = Path(args.feature_dir) if args.feature_dir else None
    skill_sources = [Path(p) for p in args.skill_source] if args.skill_source else None

    errors_count, errors, warnings = validate_all(
        plugin_root=Path(args.plugin_root),
        workspace_root=Path(args.workspace_root) if args.workspace_root else None,
        feature_dir=feature_dir,
        strict_overlay_skills=args.strict_overlay_skills,
        require_artifacts=args.require_artifacts,
        skill_sources=skill_sources,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "ok": errors_count == 0,
                    "errors": errors,
                    "warnings": warnings,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        if warnings:
            for item in warnings:
                warn(item)
        if errors:
            for item in errors:
                fail(item)
            print(f"plugin validation failed: {errors_count} error(s)")
        else:
            print("plugin validation passed")

    return 1 if errors else 0


def _run_detect_duplicates(args: argparse.Namespace) -> int:
    skill_sources = [Path(path) for path in args.skill_source]
    duplicates = detect_duplicate_skill_sources(skill_sources)
    if not duplicates:
        print("no upstream core duplicate skill sources detected")
        return 0

    print("duplicate upstream source overlap detected:")
    for skill, paths in sorted(duplicates.items()):
        print(f"- {skill} -> {', '.join(str(path) for path in paths)}")

    return 1


def _run_scan_static_safety(args: argparse.Namespace) -> int:
    findings, errors = scan_static_safety_paths(
        plugin_root=Path(args.plugin_root),
        paths=[Path(path) for path in args.path],
    )
    gate = static_safety_pr_gate(findings)
    ok = not errors and not findings
    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "policy": STATIC_LITERAL_POLICY,
                    "gate": gate,
                    "errors": errors,
                    "findings": findings,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for error in errors:
            fail(error)
        for finding in findings:
            fail(
                f"{finding['path']}:{finding['line']}: "
                f"{finding['category']} ({finding['policy_scope']})"
            )
        if ok:
            print("static safety scan passed")
    return 0 if ok else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Bears workflow-overlay plugin roles/schemas and governance packets.",
    )
    parser.add_argument(
        "--plugin-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="plugin root path (defaults to current plugin)",
    )
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="workspace root path containing .specify/extensions.yml",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="run plugin validation")
    validate.set_defaults(func=_run_validate)
    validate.add_argument("--feature-dir", help="feature directory with governance artifacts")
    validate.add_argument("--require-artifacts", action="store_true", help="require governance artifact presence")
    validate.add_argument(
        "--strict-overlay-skills",
        action="store_true",
        help="fail when upstream core speckit-* skill dirs are found",
    )
    validate.add_argument(
        "--skill-source",
        action="append",
        help="additional spec source dirs to check for duplicate upstream speckit-* skill names",
    )

    dup = subparsers.add_parser("detect-duplicates", help="check duplicate upstream speckit-* skill names across sources")
    dup.set_defaults(func=_run_detect_duplicates)
    dup.add_argument("--skill-source", action="append", required=True)

    scan_static = subparsers.add_parser("scan-static-safety", help="scan selected files for raw endpoint and CIDR literals")
    scan_static.set_defaults(func=_run_scan_static_safety)
    scan_static.add_argument("--path", action="append", required=True, help="repo-relative file path to scan")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
