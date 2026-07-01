"""Validate overlay validator behavior under pytest and unittest loaders."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

from tests.function_test_loader import load_function_tests

from copy import deepcopy

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "validate_overlay.py"
spec = importlib.util.spec_from_file_location("validate_overlay", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)  # type: ignore[arg-type]

validate_all = module.validate_all
detect_duplicate_skill_sources = module.detect_duplicate_skill_sources


VALID_MANIFEST = {
    "name": "bears",
    "version": "0.1.0",
    "skills": "./skills/",
    "description": "test",
    "author": {"name": "test"},
    "keywords": ["governance"],
    "interface": {
        "displayName": "test",
        "shortDescription": "Bears governance overlay test fixture.",
        "longDescription": (
            "Bears repo-proof language policy keeps artifacts and subagent messages English-only "
            "with entity-bound wording."
        ),
        "capabilities": ["Guidance"],
        "defaultPrompt": [
            "Keep plugin artifacts, assignment packets, subagent task text, and subagent messages in English.",
            "Use strict concise entity-bound terms such as local_cd and kubernetes_deployment.",
            "Do not use generic deploy.",
            "Do not add sample, example, or illustrative sections.",
        ],
    },
}


VALID_ROLE = {
    "name": "test-role",
    "description": "Use test role.",
    "developer_instructions": (
        "Working mode:\n"
        "- Operate as test-role.\n\n"
        "Scope/focus:\n"
        "- Stay inside test fixtures.\n\n"
        "Forbidden actions:\n"
        "- Do not broaden fixture scope.\n\n"
        "Quality checks:\n"
        "- Check deterministic fixture validation.\n\n"
        "Return shape:\n"
        "- Return status and validation result.\n\n"
        "Validation expectations:\n"
        "- Run the fixture validator.\n"
    ),
    "model": "gpt-5.5",
    "model_reasoning_effort": "high",
    "sandbox_mode": "workspace-write",
}

VALID_AGENT_INSTRUCTIONS = "\n".join(
    [
        "Working mode:",
        "- Execute the assigned governance task.",
        "Scope/focus:",
        "- Stay inside the assigned path.",
        "Forbidden actions:",
        "- Do not expose restricted data.",
        "Quality checks:",
        "- Run the named validator.",
        "Return shape:",
        "- Return changed files and validation exits.",
        "Validation expectations:",
        "- Report exact commands.",
        "sandbox_mode is not authority proof",
        "READ_ONLY_ASSIGNMENT_BLOCKED",
        "audit subagent sessions cannot be reused for writable tasks",
    ]
)


def test_manual_validation_language_rejects_direct_repo_test_command(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    (plugin_root / "agents").mkdir(parents=True)
    (plugin_root / "skills" / "sample").mkdir(parents=True)
    (plugin_root / "AGENTS.md").write_text(
        "Validation:\n"
        "- `python3 scripts/validate_overlay.py validate`\n"
    )
    (plugin_root / "requirements.md").write_text(
        "| ID | Requirement | Evidence / check |\n"
        "| BP-X | Routing drift stays covered. | `python3 -m unittest tests/test_platform_roles.py`. |\n"
    )
    (plugin_root / "agents" / "sample.toml").write_text(
        'developer_instructions = """\n'
        "Validation expectations:\n"
        "- Run python3 scripts/platform_roles.py validate after routing changes.\n"
        '"""\n'
    )
    (plugin_root / "skills" / "sample" / "SKILL.md").write_text(
        "# Sample\n\nRun pytest after changes.\n"
    )

    errors = module.validate_manual_validation_language(plugin_root)

    assert len(errors) == 4
    assert all("local-commit-owned or operator-approved" in error for error in errors)


def test_manual_validation_language_allows_route_audit_and_static_checks(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    (plugin_root / "agents").mkdir(parents=True)
    (plugin_root / "skills" / "sample").mkdir(parents=True)
    (plugin_root / "AGENTS.md").write_text(
        "Agent-local gates: `python3 scripts/platform_roles.py route target`; "
        "`python3 scripts/platform_roles.py audit target`.\n"
    )
    (plugin_root / "requirements.md").write_text(
        "Allowed route/audit gates: `python3 scripts/platform_roles.py route target`; "
        "`python3 scripts/platform_roles.py audit target`.\n"
        "Allowed static file-shape check: "
        "`python3 scripts/validate_overlay.py --json scan-static-safety --path requirements.md`.\n"
    )
    (plugin_root / "agents" / "sample.toml").write_text('developer_instructions = "Route only."\n')
    (plugin_root / "skills" / "sample" / "SKILL.md").write_text("# Sample\n")

    assert module.validate_manual_validation_language(plugin_root) == []


def test_manual_validation_language_allows_local_commit_owned_or_operator_approved_commands(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    (plugin_root / "agents").mkdir(parents=True)
    (plugin_root / "skills" / "sample").mkdir(parents=True)
    (plugin_root / "AGENTS.md").write_text(
        "Local-commit-owned validators/tests: `python3 scripts/validate_overlay.py validate`; "
        "manual execution requires operator approval.\n"
    )
    (plugin_root / "requirements.md").write_text(
        "Local-commit-owned validators/tests: `python3 scripts/platform_roles.py validate` and "
        "`python3 -m unittest tests/test_platform_roles.py`; "
        "manual execution requires operator approval.\n"
    )
    (plugin_root / "agents" / "sample.toml").write_text(
        'developer_instructions = "local-commit-owned: `python3 scripts/role_gate_methodology.py validate`."\n'
    )
    (plugin_root / "skills" / "sample" / "SKILL.md").write_text(
        "Operator-approved only: `python3 -m pytest -q tests/test_auth_gateway_deploy_readiness.py`.\n"
    )

    assert module.validate_manual_validation_language(plugin_root) == []


def test_manifest_visible_text_allows_secret_factory_governance_terms() -> None:
    manifest = deepcopy(VALID_MANIFEST)
    manifest["description"] = "Bears write-only Secret Factory governance."
    manifest["keywords"] = ["secret-factory", "write-only-secrets"]
    manifest["interface"]["shortDescription"] = "Secret Factory governance for Bears."
    manifest["interface"]["longDescription"] = "write-only Infisical creation governance."
    manifest["interface"]["capabilities"] = ["Secret Factory governance"]
    manifest["interface"]["defaultPrompt"] = ["Use $secret-factory without printing secret values."]

    self_errors = module.validate_manifest_visible_text(manifest)
    assert self_errors == []


def test_manifest_visible_text_rejects_unsafe_secret_claims_in_each_visible_field() -> None:
    field_updates: dict[tuple[str, ...], Any] = {
        ("description",): "Reads raw secret values for convenience.",
        ("interface", "shortDescription"): "Credential reads for live systems.",
        ("interface", "longDescription"): "Handles raw secret material.",
        ("interface", "defaultPrompt"): ["Print secret_value for debugging."],
        ("keywords",): ["bot token"],
        ("interface", "capabilities"): ["private key handling"],
    }

    for path, value in field_updates.items():
        manifest = deepcopy(VALID_MANIFEST)
        target = manifest
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        errors = module.validate_manifest_visible_text(manifest)
        assert errors, path


def test_secret_discovery_path_classifier_counts_forbidden_paths_without_printing_them() -> None:
    assert module.classify_secret_discovery_path("scripts/safe_wrapper.py") == "SAFE_WRAPPER_PATH"
    assert module.classify_secret_discovery_path("docs/reference/secret-factory.md") == "SAFE_CONTRACT_PATH"
    assert module.classify_secret_discovery_path("SERVERSPACE_API_KEY") == "SECRET_REF_NAME"
    assert module.classify_secret_discovery_path("/redacted/.env.local") == "FORBIDDEN_CREDENTIAL_FILE_PATH"
    assert module.classify_secret_discovery_path("config/token-store.json") == "FORBIDDEN_CREDENTIAL_FILE_PATH"

    closeout = module.secret_discovery_closeout(
        [
            "scripts/safe_wrapper.py",
            "SERVERSPACE_API_KEY",
            "/redacted/.env.local",
        ]
    )
    assert closeout["status"] == "SECRET_DISCOVERY_STOP"
    assert closeout["count_only"] is True
    assert closeout["printed_paths"] is False
    assert closeout["class_counts"]["FORBIDDEN_CREDENTIAL_FILE_PATH"] == 1
    assert ".env" not in json.dumps(closeout)


def test_inventory_output_redacts_sensitive_uri_defaults_before_printing() -> None:
    packet = module.scan_inventory_output(
        "src/settings/database.py",
        "DATABASE_URL = 'postgres://user:password@db.internal/app'",
    )

    assert packet["status"] == "SENSITIVE_OUTPUT_STOP"
    assert packet["redaction_count"] == 1
    assert packet["line_only_issue_flow"] is True
    assert packet["line_findings"] == [
        {"line": 1, "category": "credential_uri_default", "issue_flow": "line_only_redacted_issue"},
        {"line": 0, "category": "sensitive_inventory_path", "issue_flow": "line_only_redacted_issue"},
    ]
    assert "password" not in packet["safe_excerpt"]
    assert "<REDACTED_CREDENTIAL_URI>" in packet["safe_excerpt"]


def test_live_tool_mentions_are_classified_before_failure() -> None:
    cases = {
        "Do not perform live mutation.": "prohibition",
        "Use names-only reference output.": "names_only_reference",
        "Prepare a dry-run packet only.": "dry_run_only",
        "Run validator command before closeout.": "validation_command",
        "Apply the DNS change now.": "mutation_instruction",
    }
    for text, expected in cases.items():
        assert module.classify_live_tool_mention(text) == expected

    gate = module.live_tool_pr_safety_gate(list(cases))
    assert gate["status"] == "LIVE_TOOL_SAFETY_STOP"
    assert gate["count_only"] is True
    assert gate["printed_text"] is False
    assert gate["class_counts"]["mutation_instruction"] == 1
    assert "Apply the DNS change now" not in json.dumps(gate)


def test_static_safety_scan_reports_redacted_endpoint_and_cidr_findings() -> None:
    findings = module.scan_static_safety_text(
        "tests/test_gateway_runtime_service.py",
        "\n".join(
            [
                "endpoint = 'https://gateway.internal.service.local/path'",
                "network = '10.9.8.0/24'",
                "placeholder = 'https://example.invalid/path'",
            ]
        ),
    )

    assert [item["category"] for item in findings] == [
        "raw_endpoint_literal",
        "raw_ip_or_cidr_literal",
    ]
    assert all("policy_scope" in item for item in findings)
    assert "gateway.internal" not in json.dumps(findings)
    assert "10.9.8.0/24" not in json.dumps(findings)


def test_static_safety_gate_is_required_and_covers_infra_duplicate_plane() -> None:
    findings = module.scan_static_safety_text(
        "skills/yandex360-dns/scripts/yandex360_dns.py",
        "\n".join(
            [
                "base = 'https://dns.internal.service.local/path'",
                "cidr = '192.168.50.0/24'",
            ]
        ),
    )
    gate = module.static_safety_pr_gate(findings)

    assert gate["status"] == "STATIC_SAFETY_STOP"
    action = gate["compact_action_json"]
    assert action["action"] == "open_line_only_issue"
    assert action["issue_flow"] == "line_only_redacted_issue"
    assert action["category_counts"]["raw_endpoint_literal"] == 1
    assert action["category_counts"]["raw_ip_or_cidr_literal"] == 1
    assert action["plane_counts"]["infrastructure_network_governance"] == 2
    assert set(action["required_planes"]) >= {
        "secret_factory_governance",
        "infrastructure_network_governance",
    }


def test_abuse_probe_publication_gate_requires_all_negative_probe_classes() -> None:
    blocked = module.abuse_probe_publication_gate(
        {
            "manifest_visible_text": "pass",
            "static_literal_scan": "pass",
            "inventory_uri_redaction": "pass",
        }
    )
    assert blocked["status"] == "ABUSE_PROBE_PUBLICATION_STOP"
    assert blocked["publish_allowed"] is False
    assert "live_tool_classifier" in blocked["missing_or_not_pass"]
    assert "secret_discovery_classifier" in blocked["missing_or_not_pass"]

    passed = module.abuse_probe_publication_gate(
        {
            field: "pass"
            for field in module.ABUSE_PROBE_REQUIRED_FIELDS
        }
    )
    assert passed["status"] == "OK"
    assert passed["publish_allowed"] is True

DISABLED_TELEGRAM_SKILLS = (
    "bears-telegram-workflow",
    "telegram-aiogram-migration",
    "telegram-plugin-skill-factory",
    "telegram-quality-testing",
)


VALID_EXTENSIONS: dict[str, Any] = {
    "hooks": {
        "after_specify": [
            {
                "extension": "bears",
                "command": "bears.governance.check",
                "enabled": True,
                "optional": True,
                "advisory": True,
                "report_only": True,
                "fail_open": True,
            }
        ],
        "after_plan": [
            {
                "extension": "bears",
                "command": "bears.role.gate",
                "enabled": True,
                "optional": True,
                "advisory": True,
                "report_only": True,
                "fail_open": True,
            }
        ],
        "after_tasks": [
            {
                "extension": "bears",
                "command": "bears.workflow.validate",
                "enabled": True,
                "optional": True,
                "advisory": True,
                "report_only": True,
                "fail_open": True,
            }
        ],
        "after_analyze": [
            {
                "extension": "bears",
                "command": "bears.workflow.validate",
                "enabled": True,
                "optional": False,
                "advisory": False,
                "report_only": False,
                "fail_open": False,
            }
        ],
        "before_implement": [
            {
                "extension": "bears",
                "command": "bears.deploy.gate",
                "enabled": True,
                "optional": True,
                "advisory": True,
                "report_only": True,
                "fail_open": True,
            }
        ],
    }
}


def _write_toml(path: Path, data: dict[str, str]) -> None:
    lines = []
    for key, value in data.items():
        if key == "developer_instructions":
            lines.append(f"{key} = \"\"\"{value}\"\"\"")
        else:
            lines.append(f'{key} = "{value}"')
    path.write_text("\n".join(lines) + "\n")


def _write_agent_matrix(agents_root: Path) -> None:
    for filename, sandbox_mode in module.AGENT_SANDBOX_MODE_MATRIX.items():
        role = deepcopy(VALID_ROLE)
        role["name"] = filename.removesuffix(".toml")
        role["sandbox_mode"] = sandbox_mode
        role["developer_instructions"] = VALID_AGENT_INSTRUCTIONS
        _write_toml(agents_root / filename, role)


def _write_extensions(path: Path, extensions: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(extensions))


def _write_workspace_reference_docs(workspace_root: Path) -> None:
    dev_root = workspace_root / "dev"
    dev_root.mkdir(parents=True, exist_ok=True)
    canonical_catalog = "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json"
    canonical_validator = "/srv/bears/plugins/bears/scripts/platform_roles.py validate"
    (dev_root / "WORKSPACE.md").write_text(
        f"Use {canonical_catalog}; validate with {canonical_validator}.\n"
    )
    (dev_root / "PROJECTS.md").write_text(
        f"Use {canonical_catalog}; validate with {canonical_validator}.\n"
    )


def _write_issue_template_assets(plugin_root: Path) -> None:
    issue_template_root = plugin_root / ".github" / "ISSUE_TEMPLATE"
    issue_template_root.mkdir(parents=True, exist_ok=True)
    (issue_template_root / "config.yml").write_text(
        "blank_issues_enabled: false\n"
    )
    (issue_template_root / "01-governance-work.yml").write_text(
        yaml.safe_dump(
            {
                "name": "Bears governance work",
                "description": "Request bounded work for the Bears workflow-governance overlay.",
                "title": "[Governance]: ",
                "labels": ["type:idea"],
                "body": [
                    {
                        "type": "input",
                        "id": "target_path",
                        "attributes": {
                            "label": "Exact target path",
                            "description": "Name one repository path or file path that owns the requested change.",
                        },
                        "validations": {"required": True},
                    },
                    {
                        "type": "input",
                        "id": "concrete_part_or_role_route",
                        "attributes": {
                            "label": "Concrete part or role route",
                            "description": "Name the exact platform part, workflow part, or specialist role route.",
                        },
                        "validations": {"required": True},
                    },
                    {
                        "type": "textarea",
                        "id": "problem_statement",
                        "attributes": {
                            "label": "Problem statement",
                            "description": "State the current fault or missing behavior in concrete terms.",
                        },
                        "validations": {"required": True},
                    },
                    {
                        "type": "dropdown",
                        "id": "pre_development_gate_impact",
                        "attributes": {
                            "label": "Pre-development gate impact",
                            "description": "Select the earliest gate affected before implementation starts.",
                            "options": [
                                "Route gate",
                                "Constitution gate",
                                "Research gate",
                                "Prototype or design gate",
                                "Spec Kit gate",
                                "Role gate",
                                "Validation gate only",
                            ],
                        },
                        "validations": {"required": True},
                    },
                    {
                        "type": "dropdown",
                        "id": "research_reuse_decision",
                        "attributes": {
                            "label": "Research or reuse decision",
                            "description": "Select the required research or existing-pattern decision.",
                            "options": [
                                "Research required",
                                "Reuse existing Bears pattern",
                                "Research skip requested for narrow bounded work",
                                "Not applicable to this request",
                            ],
                        },
                        "validations": {"required": True},
                    },
                    {
                        "type": "textarea",
                        "id": "validation_command",
                        "attributes": {
                            "label": "Validation command",
                            "description": "Provide the exact command that should prove the requested change.",
                            "render": "shell",
                        },
                        "validations": {"required": True},
                    },
                    {
                        "type": "checkboxes",
                        "id": "restricted_data_safety",
                        "attributes": {
                            "label": "Restricted-data safety confirmation",
                            "description": "Confirm the issue body excludes restricted data.",
                            "options": [
                                {
                                    "label": (
                                        "I confirm this issue includes no secrets, tokens, private keys, "
                                        "raw env values, raw logs, credential files, production data, "
                                        "raw VPN configs, or shell history."
                                    ),
                                    "required": True,
                                }
                            ],
                        },
                    },
                ],
            },
            sort_keys=False,
        )
    )


def _write_canonical_fixture_assets(plugin_root: Path) -> None:
    (plugin_root / "AGENTS.md").write_text(
        "# Router\n\n"
        "- Repo-proof language validation is deterministic and repo-only. It must not claim live runtime chat proof.\n"
        "- Artifacts and subagent messages must use English only.\n"
        "- Wording must stay strict, concise, and entity-bound.\n"
        "- Do not use generic `deploy` when the entity is `local_cd` or `kubernetes_deployment`.\n"
        "- Do not add sample, example, or illustrative sections to this policy surface.\n"
    )
    (plugin_root / "README.md").write_text(
        "# README\n\n"
        "`assets/catalog/plugin-governance-language-policy.v1.json` is the hard language and wording policy for this plugin. "
        "Artifacts and subagent messages must use English only. Wording must stay strict, concise, and entity-bound. "
        "Do not use generic `deploy` when the entity is `local_cd` or `kubernetes_deployment`. "
        "Do not add sample, example, or illustrative sections.\n\n"
        "Repo-proof validation is deterministic and repo-only. It scans the configured governance artifacts and policy docs. "
        "It does not claim live runtime chat proof.\n"
    )
    (plugin_root / "SPEC.md").write_text(
        "# Spec\n\n"
        "The language policy is hard: `artifact_language=en`, `subagent_message_language=en`, and wording stays strict, concise, and entity-bound. "
        "Use `local_cd` and `kubernetes_deployment` when those entities are intended. "
        "Do not use generic `deploy`. Do not add sample, example, or illustrative sections.\n\n"
        "Repo-proof validation is deterministic and repo-only. It scans the configured governance artifacts and policy docs. "
        "It does not claim live runtime chat proof.\n"
    )
    (plugin_root / "requirements.md").write_text("# Requirements\n")
    _write_issue_template_assets(plugin_root)

    scripts = plugin_root / "scripts"
    workflows = plugin_root / "workflows" / "auth-gateway-deploy-core"
    bears_sdd_workflows = plugin_root / "workflows" / "bears-sdd"
    catalog_dir = plugin_root / "assets" / "catalog"
    docs_reference = plugin_root / "docs" / "reference"
    for path in (scripts, workflows, bears_sdd_workflows, catalog_dir, docs_reference):
        path.mkdir(parents=True, exist_ok=True)
    (scripts / "platform_roles.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "validate_overlay.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "roadmap_control.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "git_discipline.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "auth_gateway_deploy_readiness.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "project_registry_gate.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "plugin_constitution.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "agent_github_dev_cd.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "secret_factory.py").write_text("#!/usr/bin/env python3\n")
    (scripts / "subagent_orchestration_policy.py").write_text(
        (PLUGIN_ROOT / "scripts" / "subagent_orchestration_policy.py").read_text()
    )
    (scripts / "session_workers_runtime.py").write_text(
        "import json\n"
        "from pathlib import Path\n\n"
        "def load_json(path: Path):\n"
        "    return json.loads(path.read_text())\n\n"
        "def validate_catalog(_catalog, _role_catalog):\n"
        "    return []\n"
    )
    (scripts / "role_gate_methodology.py").write_text(
        "import json\n"
        "from pathlib import Path\n\n"
        "def load_json(path: Path):\n"
        "    return json.loads(path.read_text())\n\n"
        "def validate_methodology(_methodology):\n"
        "    return []\n\n"
        "def validate_catalog_alignment(_methodology, _role_catalog, *, plugin_root=None):\n"
        "    return []\n"
    )
    (workflows / "workflow.yml").write_text("workflow: {}\n")
    (bears_sdd_workflows / "workflow.yml").write_text(
        (PLUGIN_ROOT / "workflows" / "bears-sdd" / "workflow.yml").read_text()
    )
    (docs_reference / "session-workers-runtime.md").write_text("# Session Workers Runtime\n")
    (docs_reference / "role-gate-methodology.md").write_text("# Role Gate Methodology\n")
    (docs_reference / "roadmap-control.md").write_text(
        "# Roadmap Control\n\n"
        "Assignment packets, subagent task text, and subagent messages must use English only.\n"
        "Use `local_cd` or `kubernetes_deployment` when one of those entities is the concrete target. "
        "Do not fall back to generic `deploy`.\n"
        "Fresh audit subagents use no parent context.\n"
        "Repo-proof validation covers only repo artifacts. It does not claim live runtime chat proof.\n"
    )

    for script in (
        "telegram_catalog.py",
        "telegram_migration_backlog.py",
        "telegram_runtime_readiness.py",
        "telegram_skill_factory_policy.py",
        "telegram_surface_inventory.py",
    ):
        (scripts / script).write_text("#!/usr/bin/env python3\n")

    for catalog_file in (
        "telegram-aiogram-migration-backlog.v1.json",
        "telegram-plugin-skill-factory-policy.v1.json",
        "telegram-runtime-readiness.v1.json",
        "telegram-workflow-catalog.v1.json",
    ):
        (catalog_dir / catalog_file).write_text("{}\n")

    for skill in (
        "bears-role-gate",
        "bears-goal-prompt",
        "project-mandate",
        "platform-role-governance",
        "speckit-bears-flow",
        "speckit-bears-research",
    ):
        skill_dir = plugin_root / "skills" / skill
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {skill}\ndescription: test\n---\n")

    for skill in DISABLED_TELEGRAM_SKILLS:
        skill_dir = plugin_root / "skills" / skill
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.disabled.md").write_text(f"---\nname: {skill}\ndescription: test\n---\n")

    active_skill_names = [
        "bears-role-gate",
        "bears-goal-prompt",
        "project-mandate",
        "platform-role-governance",
        "speckit-bears-flow",
        "speckit-bears-research",
    ]
    skill_catalog = {
        "schema": "bears-plugin-skill-catalog.v1",
        "version": "1",
        "owner_plugin": "bears",
        "discovery_policy": {
            "active_skill_file": "SKILL.md",
            "disabled_skill_file": "SKILL.disabled.md",
            "manifest_skill_root": "./skills/",
        },
        "active_skills": [
            {"name": name, "path": f"skills/{name}", "description": "test"}
            for name in active_skill_names
        ],
        "disabled_skills": [
            {"name": name, "path": f"skills/{name}", "reason": "test"}
            for name in DISABLED_TELEGRAM_SKILLS
        ],
        "generated_fragments": {
            "readme": "docs/generated/README.skill-inventory.md",
            "spec": "docs/generated/SPEC.skill-inventory.md",
        },
    }
    (catalog_dir / "plugin-skill-catalog.v1.json").write_text(json.dumps(skill_catalog))
    skill_catalog_script = scripts / "skill_catalog.py"
    skill_catalog_script.write_text((PLUGIN_ROOT / "scripts" / "skill_catalog.py").read_text())
    import importlib.util as _importlib_util
    _spec = _importlib_util.spec_from_file_location("fixture_skill_catalog", skill_catalog_script)
    assert _spec is not None and _spec.loader is not None
    _module = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)  # type: ignore[arg-type]
    _module.generate(skill_catalog, plugin_root)

    role_names = [
        "bears-platform-role-governor",
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
    ]
    catalog = {
        "schema": "bears-platform-role-catalog.v1",
        "owner_plugin": "bears",
        "roles": [{"name": role} for role in role_names],
        "platform_parts": [
            {"name": "auth_core"},
            {"name": "bears_gateway"},
            {"name": "cd_deploy_stage"},
            {"name": "auth_gateway_deploy_core"},
            {"name": "bears_plugin"},
            {"name": "platform_role_governance"},
            {"name": "goal_prompt_generator"},
            {"name": "role_gate_methodology"},
            {"name": "session_workers_runtime"},
            {"name": "telegram_platform"},
            {"name": "telegram_aiogram"},
            {"name": "bears_telegram_workflow_skill_bundle"},
            {"name": "workspace_governance_canonical_plugin_docs"},
            {"name": "kubernetes_deploy_core"},
            {"name": "android_emulator_platform_225"},
            {"name": "sentry_observability_226"},
            {"name": "theants_product_dev_layer"},
            {"name": "theants_quality_e2e_layer"},
            {"name": "theants_ops_runbooks_layer"},
            {"name": "theants_control_provenance_layer"},
            {"name": "subagent_orchestration_policy"},
            {"name": "project_registry_gate"},
            {"name": "project_mandate_skill"},
        ],
        "workflow_routes": [
            {
                "workflow_id": "auth-gateway-deploy-core",
                "ordered_parts": ["auth_core", "bears_gateway", "cd_deploy_stage"],
            }
        ],
    }
    (catalog_dir / "platform-role-catalog.v1.json").write_text(json.dumps(catalog))
    (catalog_dir / "plugin-constitution.v1.json").write_text(
        (PLUGIN_ROOT / "assets" / "catalog" / "plugin-constitution.v1.json").read_text()
    )
    (catalog_dir / "auth-gateway-deploy-readiness.v1.json").write_text(
        (PLUGIN_ROOT / "assets" / "catalog" / "auth-gateway-deploy-readiness.v1.json").read_text()
    )
    (catalog_dir / "subagent-orchestration-policy.v1.json").write_text(
        (PLUGIN_ROOT / "assets" / "catalog" / "subagent-orchestration-policy.v1.json").read_text()
    )
    session_runtime = {
        "schema": "bears-session-workers-runtime.v1",
        "owner_plugin": "bears",
        "truth": {"authority": "Spec Kit", "rule": "Current Spec Kit artifacts are the truth source for session worker execution."},
        "control": {
            "owner": "Bears plugin",
            "role_catalog": "assets/catalog/platform-role-catalog.v1.json",
            "validator": "scripts/session_workers_runtime.py",
            "docs": "docs/reference/session-workers-runtime.md",
        },
        "work": {
            "surface": "Codex sessions/session workers",
            "session_model_rule": "Codex sessions are workers, not memory.",
        },
        "worker_lanes": [
            {"lane": "constitution", "allowed_roles": ["bears-workflow-overlay-controller"], "artifact_focus": ["constitution.md"], "description": "test"},
            {"lane": "specification", "allowed_roles": ["bears-workflow-overlay-controller"], "artifact_focus": ["spec.md"], "description": "test"},
            {"lane": "planning", "allowed_roles": ["bears-workflow-overlay-controller"], "artifact_focus": ["plan.md"], "description": "test"},
            {"lane": "docs", "allowed_roles": ["bears-workflow-overlay-controller"], "artifact_focus": ["docs/"], "description": "test"},
            {"lane": "auth", "allowed_roles": ["bears-auth-platform-engineer"], "artifact_focus": ["tasks.md"], "description": "test"},
            {"lane": "gateway", "allowed_roles": ["bears-gateway-platform-engineer"], "artifact_focus": ["tasks.md"], "description": "test"},
            {"lane": "deploy", "allowed_roles": ["bears-deploy-platform-engineer"], "artifact_focus": ["tasks.md"], "description": "test"},
            {"lane": "validation", "allowed_roles": ["bears-platform-security-reviewer"], "artifact_focus": ["tests/"], "description": "test"},
            {"lane": "review", "allowed_roles": ["bears-platform-security-reviewer"], "artifact_focus": ["review"], "description": "test"},
            {"lane": "implementation", "allowed_roles": ["bears-workflow-overlay-controller"], "artifact_focus": ["tasks.md"], "description": "test"},
        ],
        "worker_states": ["available", "claimed", "running", "waiting", "blocked", "stale", "completed", "closed"],
        "runtime_artifacts": [
            {"name": "session-workers.json", "schema": "bears-session-workers.v1", "required": True, "description": "test"},
            {"name": "orchestration-state.json", "schema": "bears-session-orchestration-state.v1", "required": True, "description": "test"},
            {"name": "worker-heartbeat.json", "schema": "bears-worker-heartbeat.v1", "required": True, "description": "test"},
            {"name": "worker-closeout.json", "schema": "bears-worker-closeout.v1", "required": True, "description": "test"},
            {"name": "scope-locks.json", "schema": "bears-scope-locks.v1", "required": True, "description": "test"},
        ],
        "worker_contract": {
            "required_fields": [
                "worker_id", "status", "lane", "registered_role", "target_paths", "allowed_write_scope",
                "forbidden_scope", "spec_kit_snapshot", "validation_target", "evidence_target",
                "heartbeat_packet", "closeout_packet", "resume_policy"
            ],
            "spec_kit_snapshot_required_fields": ["captured_at", "repo_head", "artifacts"],
            "spec_kit_artifact_statuses": ["current", "missing", "stale", "blocked"],
            "heartbeat_packet_schema": "bears-worker-heartbeat.v1",
            "closeout_packet_schema": "bears-worker-closeout.v1",
        },
        "resume_fork_rule": {
            "allowed_actions": ["resume", "fork", "fresh"],
            "compatibility_fields": [
                "lane_compatible", "role_compatible", "scope_compatible", "repo_state_compatible", "spec_kit_snapshot_compatible"
            ],
            "rule": "Historical session resume or fork is allowed only when lane, role, scope, current repo state, and current Spec Kit snapshot are compatible; otherwise spawn fresh with current Spec Kit truth plus bounded prior evidence.",
            "otherwise_action": "fresh",
        },
        "implementation_lane_policy": {
            "lane": "implementation",
            "speckit_command": "/speckit-implement",
            "rule": "/speckit-implement is one controlled implementation lane, not a global executor.",
        },
        "validation_commands": [
            "python3 scripts/session_workers_runtime.py validate",
            "python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>",
        ],
    }
    (catalog_dir / "session-workers-runtime.v1.json").write_text(json.dumps(session_runtime))
    methodology = {
        "schema": "bears-role-gate-methodology.v1",
        "owner_plugin": "bears",
    }
    (catalog_dir / "role-gate-methodology.v1.json").write_text(json.dumps(methodology))
    plugin_governance_language_policy = {
        "schema": "bears-plugin-governance-language-policy.v1",
        "version": "1",
        "owner_plugin": "bears",
        "artifact_language": "en",
        "subagent_message_language": "en",
        "wording_policy": {
            "style": "strict_entity_bound_concise",
            "abstract_drift": "blocked",
            "section_mode": "policy_only",
        "required_entity_terms": ["local_cd", "kubernetes_deployment"],
        "allowed_exact_terms": [
            "github_ci",
            "local_cd",
            "dev-cd-gate",
            "git_discipline",
            "kubernetes_deployment",
            "fresh_no_parent_context",
        ],
        "forbidden_token_rules": [
                {
                    "token": "deploy",
                    "status": "forbidden",
                    "when_entity_is": ["local_cd", "kubernetes_deployment"],
                }
            ],
        },
        "repo_proof": {
            "proof_scope": "repo_only",
            "runtime_chat_out_of_scope": True,
            "governed_artifacts": [
                {
                    "path": "AGENTS.md",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "Artifacts and subagent messages must use English only.",
                        "Wording must stay strict, concise, and entity-bound.",
                    ],
                },
                {
                    "path": "README.md",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "Artifacts and subagent messages must use English only.",
                        "Repo-proof validation is deterministic and repo-only.",
                    ],
                },
                {
                    "path": "SPEC.md",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "The language policy is hard: `artifact_language=en`, `subagent_message_language=en`, and wording stays strict, concise, and entity-bound.",
                        "Repo-proof validation is deterministic and repo-only.",
                    ],
                },
                {
                    "path": ".codex-plugin/plugin.json",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "Keep plugin artifacts, assignment packets, subagent task text, and subagent messages in English.",
                        "Do not add sample, example, or illustrative sections.",
                    ],
                },
                {
                    "path": "assets/catalog/plugin-governance-language-policy.v1.json",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "\"artifact_language\": \"en\"",
                        "\"subagent_message_language\": \"en\"",
                        "\"proof_scope\": \"repo_only\"",
                    ],
                },
                {
                    "path": "assets/catalog/subagent-orchestration-policy.v1.json",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "Assignment packets, subagent task text, and subagent messages must use English only.",
                        "\"assignment_packet_language\": \"en\"",
                        "\"task_template_language\": \"en\"",
                        "\"subagent_message_language\": \"en\"",
                    ],
                },
                {
                    "path": "docs/reference/roadmap-control.md",
                    "must_be_english_only": True,
                    "must_include_required_entity_terms": True,
                    "forbid_illustrative_sections": True,
                    "required_fragments": [
                        "Assignment packets, subagent task text, and subagent messages must use English only.",
                        "Fresh audit subagents use no parent context.",
                        "Repo-proof validation covers only repo artifacts. It does not claim live runtime chat proof.",
                    ],
                },
            ],
        },
    }
    (catalog_dir / "plugin-governance-language-policy.v1.json").write_text(
        json.dumps(plugin_governance_language_policy)
    )

def _create_plugin_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    plugin_root = tmp_path / "plugin"
    agents = plugin_root / "agents"
    skills = plugin_root / "skills"
    schemas = plugin_root / "schemas"
    codex = plugin_root / ".codex-plugin"
    feature = tmp_path / "feature"

    plugin_root.mkdir()
    agents.mkdir()
    skills.mkdir()
    schemas.mkdir()
    (skills / "speckit-bears-flow").mkdir()
    codex.mkdir()
    feature.mkdir()
    (feature / "spec.md").write_text("# Spec\n")
    (feature / "plan.md").write_text("# Plan\n")
    (feature / "tasks.md").write_text(
        "# Tasks\n- [ ] Route work through bears-telegram-platform-engineer.\n"
    )

    (codex / "plugin.json").write_text(json.dumps(VALID_MANIFEST))

    _write_agent_matrix(agents)
    _write_canonical_fixture_assets(plugin_root)

    for schema_file in (PLUGIN_ROOT / "schemas").glob("*.json"):
        target = schemas / schema_file.name
        target.write_text(schema_file.read_text())

    workspace_root = tmp_path
    _write_extensions(workspace_root / ".specify" / "extensions.yml", VALID_EXTENSIONS)
    _write_workspace_reference_docs(workspace_root)

    return plugin_root, feature, workspace_root


def _write_policy_packet(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "bears-workflow-overlay.policy-packet",
                "version": "1",
                "status": "draft",
                "project_router": "agent-router",
                "policy_id": "P-1",
                "owner": {"name": "Ops", "team": "Workflow", "contact": "ops@local"},
                "scope": {"project_group": "overlay", "artifact_type": "plugin"},
            }
        )
    )


def _write_role_coverage(path: Path, route_target: str = "/srv/bears/test/route") -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "bears-workflow-overlay.role-coverage",
                "version": "1",
                "status": "ok",
                "route_target": route_target,
                "coverage_status": "complete",
                "roles": [
                    {
                        "name": "bears-telegram-platform-engineer",
                        "covered": True,
                        "owner": "Bears",
                    }
                ],
            }
        )
    )


def _write_speckit_analyze(
    path: Path,
    feature_dir: Path,
    *,
    schema: str = "bears.speckit-analyze.v1",
    status: str = "PASS",
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": schema,
                "status": status,
                "spec_path": str((feature_dir / "spec.md").resolve()),
                "plan_path": str((feature_dir / "plan.md").resolve()),
                "tasks_path": str((feature_dir / "tasks.md").resolve()),
            }
        )
    )



def test_validate_passes_without_feature_artifacts(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count == 0
    assert errors == []


def test_validate_passes_as_standalone_plugin_repo(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)

    errors_count, errors, warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=None,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count == 0
    assert errors == []
    assert warnings == []


def test_validate_requires_github_issue_template_config(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    (plugin_root / ".github" / "ISSUE_TEMPLATE" / "config.yml").write_text(
        "blank_issues_enabled: maintainer-only\n"
    )

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("issue template config.yml blank_issues_enabled must be boolean" in e for e in errors)


def test_validate_requires_governance_issue_form_fields(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    form_path = plugin_root / ".github" / "ISSUE_TEMPLATE" / "01-governance-work.yml"
    form = yaml.safe_load(form_path.read_text())
    form["body"] = [
        item for item in form["body"] if item.get("id") != "validation_command"
    ]
    form_path.write_text(yaml.safe_dump(form, sort_keys=False))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("missing governance intake fields: validation_command" in e for e in errors)


def test_validate_requires_issue_form_restricted_data_confirmation(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    form_path = plugin_root / ".github" / "ISSUE_TEMPLATE" / "01-governance-work.yml"
    form = yaml.safe_load(form_path.read_text())
    for item in form["body"]:
        if item.get("id") == "restricted_data_safety":
            item["attributes"]["options"][0]["required"] = False
            item["attributes"]["options"][0]["label"] = "I confirm this issue is safe."
    form_path.write_text(yaml.safe_dump(form, sort_keys=False))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("restricted_data_safety must require a confirmation option" in e for e in errors)
    assert any("restricted_data_safety must mention secrets" in e for e in errors)


def test_validate_requires_plugin_governance_artifact_language_en(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "plugin-governance-language-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy["artifact_language"] = "ru"
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert "plugin governance language policy artifact_language must be en" in errors


def test_validate_requires_plugin_governance_subagent_message_language_en(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "plugin-governance-language-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy.pop("subagent_message_language")
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert "plugin governance language policy subagent_message_language must be en" in errors


def test_validate_requires_plugin_governance_strict_entity_bound_wording(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "plugin-governance-language-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy["wording_policy"]["style"] = "loose"
    policy["wording_policy"]["forbidden_token_rules"] = []
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert "plugin governance language policy wording_policy.style must be strict_entity_bound_concise" in errors
    assert any("must forbid token deploy" in error for error in errors)


def test_validate_requires_plugin_governance_allowed_exact_terms(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "plugin-governance-language-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy["wording_policy"]["allowed_exact_terms"] = ["local_cd", "kubernetes_deployment"]
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("wording_policy.allowed_exact_terms missing" in error for error in errors)


def test_validate_blocks_plugin_governance_illustrative_sample_sections(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "plugin-governance-language-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy["wording_policy"]["sample_section"] = {"title": "forbidden"}
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert "plugin governance language policy must not contain illustrative sample sections" in errors


def test_validate_requires_repo_proof_scope_to_stay_repo_only(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "plugin-governance-language-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy["repo_proof"]["proof_scope"] = "runtime_chat"
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert "plugin governance language policy repo_proof.proof_scope must be repo_only" in errors


def test_validate_requires_governed_artifacts_to_be_english_only(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    readme_path = plugin_root / "README.md"
    readme_path.write_text(readme_path.read_text() + "\nРусский текст\n")

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("README.md: artifact must be English-only" in error for error in errors)


def test_validate_requires_subagent_policy_language_fragments(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    policy_path = plugin_root / "assets" / "catalog" / "subagent-orchestration-policy.v1.json"
    policy = json.loads(policy_path.read_text())
    policy.pop("language_policy")
    policy_path.write_text(json.dumps(policy))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any(
        "assets/catalog/subagent-orchestration-policy.v1.json: missing required governance fragment" in error
        for error in errors
    )


def test_validate_blocks_illustrative_markdown_sections_in_governed_artifacts(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    roadmap_path = plugin_root / "docs" / "reference" / "roadmap-control.md"
    roadmap_path.write_text(roadmap_path.read_text() + "\n## Example\nForbidden section\n")

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert "docs/reference/roadmap-control.md: illustrative sample sections are forbidden" in errors


def test_validate_blocks_generic_github_deployment_wording_in_governed_markdown(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    readme_path = plugin_root / "README.md"
    readme_path.write_text(readme_path.read_text() + "\nGitHub deployment stays open.\n")

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert (
        "README.md: generic deployment wording is forbidden; use exact terms local_cd or "
        "kubernetes_deployment"
    ) in errors


def test_validate_blocks_generic_kubernetes_deployment_wording_in_governed_json(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["interface"]["defaultPrompt"].append("Use Kubernetes deployment for the concrete target.")
    manifest_path.write_text(json.dumps(manifest))

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert (
        ".codex-plugin/plugin.json: generic deployment wording is forbidden; use exact terms local_cd or "
        "kubernetes_deployment"
    ) in errors


def test_validate_catches_invalid_role_and_manifest(tmp_path: Path) -> None:
    plugin_root, _feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    manifest = plugin_root / ".codex-plugin/plugin.json"
    manifest_data = json.loads(manifest.read_text())
    manifest_data["name"] = "not-bears"
    manifest.write_text(json.dumps(manifest_data))

    # break role required fields
    (plugin_root / "agents/bears-workflow-overlay-platform-engineer.toml").write_text('name = "x"\n')

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=None,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("plugin manifest name must be 'bears'" in e for e in errors)
    assert any("bears-workflow-overlay-platform-engineer.toml: missing required field 'description'" in e for e in errors)


def test_validate_bears_sdd_workflow_parity_rejects_missing_gate(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    workflow_path = plugin_root / "workflows" / "bears-sdd" / "workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    workflow["steps"] = [
        step for step in workflow["steps"] if step.get("id") != "design-artifact-gate"
    ]
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))

    errors = module.validate_bears_sdd_workflow_parity(plugin_root)

    assert any("missing required gate ids: design-artifact-gate" in error for error in errors)


def test_validate_bears_sdd_workflow_parity_rejects_reordered_gate(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    workflow_path = plugin_root / "workflows" / "bears-sdd" / "workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    steps = workflow["steps"]
    route_index = next(index for index, step in enumerate(steps) if step.get("id") == "route-gate")
    constitution_index = next(index for index, step in enumerate(steps) if step.get("id") == "constitution-gate")
    steps[route_index], steps[constitution_index] = steps[constitution_index], steps[route_index]
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))

    errors = module.validate_bears_sdd_workflow_parity(plugin_root)

    assert any("gate order does not match canonical lifecycle" in error for error in errors)


def test_validate_bears_sdd_workflow_parity_requires_skip_evidence_inputs(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    workflow_path = plugin_root / "workflows" / "bears-sdd" / "workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    del workflow["inputs"]["research_skip_evidence"]
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))

    errors = module.validate_bears_sdd_workflow_parity(plugin_root)

    assert any("research=skip missing required evidence inputs: research_skip_evidence" in error for error in errors)


def test_validate_bears_sdd_workflow_parity_rejects_optional_skip_evidence(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    workflow_path = plugin_root / "workflows" / "bears-sdd" / "workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    workflow["inputs"]["research_skip_evidence"]["required"] = False
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))

    errors = module.validate_bears_sdd_workflow_parity(plugin_root)

    assert any("research=skip evidence input must be required: research_skip_evidence" in error for error in errors)


def test_validate_bears_sdd_workflow_parity_rejects_stale_description(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    workflow_path = plugin_root / "workflows" / "bears-sdd" / "workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    workflow["workflow"]["description"] = "Runs route gate → Spec Kit packet → role gate."
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))

    errors = module.validate_bears_sdd_workflow_parity(plugin_root)

    assert any("workflow.description missing lifecycle fragment: constitution gate" in error for error in errors)
    assert any("old route gate to Spec Kit packet wording" in error for error in errors)


def test_validate_bears_sdd_workflow_parity_rejects_global_implement_after_subagents(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    workflow_path = plugin_root / "workflows" / "bears-sdd" / "workflow.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    for step in workflow["steps"]:
        if step.get("id") == "bounded-delegated-execution":
            step["id"] = "implement"
            step["input"]["args"] = "{{ inputs.spec }}"
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False))

    errors = module.validate_bears_sdd_workflow_parity(plugin_root)

    assert any("missing delegated-execution wording" in error for error in errors)
    assert any("step id must not be generic implement" in error for error in errors)


def test_validate_governance_markdown_links_rejects_external_contract_escape(tmp_path: Path) -> None:
    plugin_root, _feature_dir, _workspace_root = _create_plugin_fixture(tmp_path)
    (plugin_root / "README.md").write_text(
        "Boundary [bad](../../contracts/spec_kit_skill_source_architecture.md)\n",
        encoding="utf-8",
    )

    errors = module.validate_governance_markdown_links(plugin_root)

    assert any("external workspace contract link" in error for error in errors)


def test_agent_tomls_match_instruction_contract_and_sandbox_matrix() -> None:
    errors = module.validate_agent_tomls(PLUGIN_ROOT / "agents")
    assert errors == []

    actual = {
        path.name: module._load_toml(path)["sandbox_mode"]
        for path in sorted((PLUGIN_ROOT / "agents").glob("*.toml"))
    }
    assert actual == module.AGENT_SANDBOX_MODE_MATRIX


def test_agent_toml_validation_rejects_missing_instruction_section(tmp_path: Path) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    broken_role = deepcopy(VALID_ROLE)
    broken_role["developer_instructions"] = "Working mode:\n- Missing the rest.\n"
    _write_toml(agents / "role-one.toml", broken_role)

    errors = module.validate_agent_tomls(agents)

    assert any("developer_instructions missing section 'Scope/focus:'" in error for error in errors)


def test_agent_toml_validation_rejects_sandbox_matrix_drift(tmp_path: Path) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    drift_role = deepcopy(VALID_ROLE)
    drift_role["name"] = "bears-workflow-overlay-blocker-taxonomy-evaluator"
    drift_role["sandbox_mode"] = "workspace-write"
    _write_toml(agents / "blocker-taxonomy-evaluator.toml", drift_role)

    errors = module.validate_agent_tomls(agents)

    assert any("sandbox_mode must be 'read-only'" in error for error in errors)


def test_validate_feature_schema_success(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()

    _write_policy_packet(governance_dir / "policy-packet.json")

    errors_count, errors, _warnings = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count == 0
    assert errors == []


def test_validate_extensions_requires_workspace_root_hooks(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    extensions_data = deepcopy(VALID_EXTENSIONS)
    extensions_data["hooks"]["after_specify"][0]["optional"] = False

    _write_extensions(workspace_root / ".specify" / "extensions.yml", extensions_data)

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("extensions hook 'after_specify[0]' must set 'optional: true' for advisory mode" in e for e in errors)


def test_validate_extensions_requires_after_analyze_hard_gate(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    extensions_data = deepcopy(VALID_EXTENSIONS)
    extensions_data["hooks"]["after_analyze"][0]["fail_open"] = True

    _write_extensions(workspace_root / ".specify" / "extensions.yml", extensions_data)

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("extensions hook 'after_analyze[0]' must set 'fail_open: false' for hard gate mode" in e for e in errors)


def test_validate_extensions_requires_all_hook_groups(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    extensions_data = deepcopy(VALID_EXTENSIONS)
    hooks = extensions_data["hooks"]
    hooks.pop("after_tasks")
    _write_extensions(workspace_root / ".specify" / "extensions.yml", extensions_data)

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("missing required hook groups" in e and "after_tasks" in e for e in errors)


def test_validate_catches_stale_shared_dev_role_gate_refs(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    stale = (
        "/srv/bears/plugins/bears-telegram-workflow/assets/catalog/platform-role-catalog.v1.json "
        "/srv/bears/plugins/bears-telegram-workflow/scripts/platform_roles.py validate\n"
    )
    (workspace_root / "dev" / "WORKSPACE.md").write_text(stale)

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("dev/WORKSPACE.md: stale shared role gate reference" in e for e in errors)
    assert any("dev/WORKSPACE.md: missing canonical role gate reference" in e for e in errors)


def test_validate_feature_artifacts_requires_governance_packets_and_analyze_pass(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_policy_packet(governance_dir / "policy-packet.json")

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=True,
    )

    assert errors_count == 4
    for required in (
        "role-coverage.json",
        "blocker-review.json",
        "deploy-gate.json",
        "speckit-analyze.json",
    ):
        assert any(required in e for e in errors)


def test_validate_feature_artifacts_tolerates_governance_directory(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    (governance_dir / "policy-packet.json").write_text("{}")
    (governance_dir / "role-coverage.json").write_text("{}")
    (governance_dir / "blocker-review.json").write_text("{}")
    (governance_dir / "deploy-gate.json").write_text("{}")

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=governance_dir,
        strict_overlay_skills=False,
        require_artifacts=True,
    )

    assert any("required field" in e for e in errors)


def test_validate_requires_spec_kit_files_with_required_artifacts(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    (feature_dir / "tasks.md").unlink()

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=True,
    )

    assert errors_count > 0
    assert any("missing required Spec Kit artifact" in e and "tasks.md" in e for e in errors)


def test_validate_requires_speckit_analyze_pass_with_required_artifacts(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_speckit_analyze(governance_dir / "speckit-analyze.json", feature_dir, status="FAIL")

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=True,
    )

    assert errors_count > 0
    assert any("speckit-analyze.json.status must be PASS" in e for e in errors)


def test_validate_accepts_speckit_analyze_pass_case_insensitively(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_speckit_analyze(governance_dir / "speckit-analyze.json", feature_dir, status="pass")

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count == 0
    assert errors == []


def test_validate_requires_speckit_analyze_schema(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_speckit_analyze(governance_dir / "speckit-analyze.json", feature_dir, schema="wrong.schema")

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("speckit-analyze.json.schema must be bears.speckit-analyze.v1" in e for e in errors)


def test_validate_requires_speckit_analyze_paths_to_match_current_files(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    analyze = {
        "schema": "bears.speckit-analyze.v1",
        "status": "PASS",
        "spec_path": "/srv/bears/wrong/spec.md",
        "plan_path": str((feature_dir / "plan.md").resolve()),
        "tasks_path": str((feature_dir / "tasks.md").resolve()),
    }
    (governance_dir / "speckit-analyze.json").write_text(json.dumps(analyze))

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("speckit-analyze.json.spec_path must match current file" in e for e in errors)


def test_validate_requires_tasks_to_link_role_coverage(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_role_coverage(governance_dir / "role-coverage.json")
    (feature_dir / "tasks.md").write_text("# Tasks\n- [ ] unrelated task.\n")

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("tasks.md must mention the route_target or primary role" in e for e in errors)


def test_validate_blocks_restricted_mutation_without_operator_approval(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_role_coverage(governance_dir / "role-coverage.json")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n- [ ] bears-telegram-platform-engineer performs production mutation.\n"
    )

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count > 0
    assert any("operator approval" in e for e in errors)


def test_validate_allows_restricted_mutation_with_operator_approval(tmp_path: Path) -> None:
    plugin_root, feature_dir, workspace_root = _create_plugin_fixture(tmp_path)
    governance_dir = feature_dir / "governance"
    governance_dir.mkdir()
    _write_role_coverage(governance_dir / "role-coverage.json")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n"
        "- [ ] bears-telegram-platform-engineer performs production mutation after operator approval.\n"
    )

    errors_count, errors, _ = validate_all(
        plugin_root=plugin_root,
        workspace_root=workspace_root,
        feature_dir=feature_dir,
        strict_overlay_skills=False,
        require_artifacts=False,
    )

    assert errors_count == 0
    assert errors == []


def test_validate_no_tracked_generated_specify_allows_untracked_generated_state(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    (plugin_root / ".specify").mkdir(parents=True)
    (plugin_root / ".specify" / "extensions.yml").write_text("hooks: {}\n")

    assert module.validate_no_tracked_generated_specify(plugin_root) == []


def test_validate_no_tracked_generated_specify_rejects_git_tracked_state(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    (plugin_root / ".specify").mkdir(parents=True)
    (plugin_root / ".specify" / "extensions.yml").write_text("hooks: {}\n")

    subprocess.run(["git", "init"], cwd=plugin_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "add", "-f", ".specify/extensions.yml"],
        cwd=plugin_root,
        check=True,
        capture_output=True,
    )

    errors = module.validate_no_tracked_generated_specify(plugin_root)

    assert errors == [
        "generated .specify files must not be tracked as plugin source: 1 tracked path(s)"
    ]


def test_detect_duplicate_skill_sources(tmp_path: Path) -> None:
    src1 = tmp_path / "src1"
    src2 = tmp_path / "src2"
    src1.mkdir()
    src2.mkdir()

    for base in (src1, src2):
        (base / "speckit-specify").mkdir()
        (base / "speckit-bears-flow").mkdir()

    dup = detect_duplicate_skill_sources([src1, src2])
    assert "speckit-specify" in dup
    assert set(dup["speckit-specify"]) == {src1, src2}


def test_detect_duplicates_command_from_cli(tmp_path: Path) -> None:
    src1 = tmp_path / "a"
    src2 = tmp_path / "b"
    (src1 / "speckit-specify").mkdir(parents=True)
    (src2 / "speckit-specify").mkdir(parents=True)
    (src2 / "speckit-bears-flow").mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "detect-duplicates",
            "--skill-source",
            str(src1),
            "--skill-source",
            str(src2),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "speckit-specify" in result.stdout


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Expose pytest-style function tests to unittest discovery."""
    del loader, pattern
    return load_function_tests(globals(), tests)
