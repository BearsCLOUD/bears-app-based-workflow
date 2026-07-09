"""Regression tests for the Telegram runtime readiness registry."""
from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path
import unittest


def _load_module(module_name: str, relative_path: str):
    plugin_root = Path(__file__).resolve().parents[1]
    module_path = plugin_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_READINESS = _load_module(
    "telegram_runtime_readiness",
    "scripts/telegram_runtime_readiness.py",
)


class TelegramRuntimeReadinessValidationTests(unittest.TestCase):
    def setUp(self):
        plugin_root = _READINESS.PLUGIN_ROOT
        self.registry = _READINESS.load_registry(
            plugin_root / "assets" / "catalog" / "telegram-runtime-readiness.v1.json"
        )
        self.backlog = _READINESS.load_backlog(
            plugin_root / "assets" / "catalog" / "telegram-aiogram-migration-backlog.v1.json"
        )
        self.role_catalog = _READINESS.load_json(
            plugin_root / "assets" / "catalog" / "platform-role-catalog.v1.json"
        )

    def _build_open_gate_candidate(self):
        registry = copy.deepcopy(self.registry)
        backlog = copy.deepcopy(self.backlog)
        packet = registry["packets"]["seller-bot-marketplace-fbs"]
        packet["readiness_status"] = "ready"
        packet["implementation_gate"] = "open"
        packet["approval_status"] = "approved"
        packet["security_signoff"] = "approved"
        packet["missing_evidence"] = []
        packet["characterization_tests"] = {
            "status": "complete",
            "command_flows": "complete",
            "callback_flows": "complete",
            "rendering_snapshots": "complete",
            "startup_import": "complete",
            "side_effect_baseline": "complete",
            "evidence": ["tests/fixtures/characterization-marketplace-fbs.json"],
        }
        packet["behavior_inventory"] = {
            "status": "complete",
            "commands": "complete",
            "message_flows": "complete",
            "fsm_states": "complete",
            "background_jobs": "complete",
            "side_effects": "complete",
            "evidence": ["tests/fixtures/behavior-marketplace-fbs.json"],
        }
        packet["callback_governance"] = {
            "status": "complete",
            "inventory": "complete",
            "schema": "complete",
            "privilege_model": "complete",
            "integrity": "complete",
            "replay_protection": "complete",
            "audit_binding": "complete",
            "evidence": ["tests/fixtures/callbacks-marketplace-fbs.json"],
        }
        packet["security_controls"] = {
            "status": "complete",
            "trust_boundary": "complete",
            "rbac": "complete",
            "idempotency": "complete",
            "audit_redaction": "complete",
            "external_side_effects": "complete",
            "evidence": ["tests/fixtures/security-marketplace-fbs.json"],
        }
        packet["secret_governance"] = {
            "status": "complete",
            "telegram_bot_token_source_class": "env-runtime",
            "webhook_secret_source_class": "not-applicable",
            "wb_supplier_token_source_class": "vault-reference",
            "chat_id_classification": "service-chat",
            "rotation_owner_classification": "platform-team",
        }
        for item in backlog["items"]:
            if item.get("surface") == "seller-bot-marketplace-fbs":
                item["artifact_gate"]["status"] = "open"
                break
        return registry, backlog

    def test_validate_default_registry(self):
        errors = _READINESS.validate_registry(
            copy.deepcopy(self.registry),
            copy.deepcopy(self.backlog),
            copy.deepcopy(self.role_catalog),
        )
        self.assertEqual(errors, [])

    def test_theants_uses_product_dev_core_role_not_telegram_primary(self):
        packet = self.registry["packets"]["theants"]
        backlog_item = next(
            item for item in self.backlog["items"] if item.get("surface") == "theants"
        )

        self.assertEqual(packet["path"], "dev/app/theants")
        self.assertEqual(backlog_item["path"], "dev/app/theants")
        self.assertEqual(packet["role_route_target"], "/srv/bears/dev/app/theants")
        self.assertEqual(backlog_item["role_route_target"], "/srv/bears/dev/app/theants")
        self.assertEqual(packet["primary_role"], "bears-product-app-zone-engineer")
        self.assertEqual(backlog_item["primary_role"], "bears-product-app-zone-engineer")
        self.assertIn("bears-telegram-platform-engineer", packet["supporting_roles"])

        route = _READINESS.route_target(self.role_catalog, packet["role_route_target"])
        self.assertEqual(route["status"], "matched")
        self.assertEqual(route["primary_role"], "bears-product-app-zone-engineer")

    def test_rejects_unknown_surface(self):
        registry = copy.deepcopy(self.registry)
        packet = registry["packets"].pop("seller-bot-marketplace-fbs")
        packet["surface"] = "unknown-surface"
        packet["backlog_item"] = "unknown-surface"
        packet["backlog_link"]["surface"] = "unknown-surface"
        registry["packets"]["unknown-surface"] = packet

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "surface unknown-surface is missing from telegram-aiogram-migration backlog",
            errors,
        )

    def test_rejects_primary_role_mismatch(self):
        registry = copy.deepcopy(self.registry)
        registry["packets"]["seller-bot-marketplace-fbs"]["primary_role"] = (
            "bears-product-app-zone-engineer"
        )

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs primary_role bears-product-app-zone-engineer does not match backlog primary_role bears-telegram-platform-engineer",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs primary_role bears-product-app-zone-engineer does not match route role bears-telegram-platform-engineer",
            errors,
        )

    def test_rejects_open_gate_without_approval_and_evidence(self):
        registry = copy.deepcopy(self.registry)
        packet = registry["packets"]["seller-bot-marketplace-fbs"]
        packet["implementation_gate"] = "open"
        packet["readiness_status"] = "ready"

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs cannot open implementation_gate while backlog artifact_gate.status=blocked-before-code",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires approval_status=approved",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires empty missing_evidence",
            errors,
        )

    def test_rejects_open_gate_when_characterization_tests_missing(self):
        registry, backlog = self._build_open_gate_candidate()
        del registry["packets"]["seller-bot-marketplace-fbs"]["characterization_tests"]

        errors = _READINESS.validate_registry(registry, backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs missing fields: ['characterization_tests']",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires characterization_tests object",
            errors,
        )

    def test_rejects_open_gate_when_characterization_tests_incomplete(self):
        registry, backlog = self._build_open_gate_candidate()
        packet = registry["packets"]["seller-bot-marketplace-fbs"]
        packet["characterization_tests"] = {
            "status": "blocked",
            "command_flows": "blocked",
            "callback_flows": "complete",
            "rendering_snapshots": "missing",
            "startup_import": "complete",
            "side_effect_baseline": "not-applicable",
            "evidence": [],
        }

        errors = _READINESS.validate_registry(registry, backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires characterization_tests.status=complete",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires characterization_tests.evidence",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires characterization_tests.command_flows complete or not-applicable",
            errors,
        )
        self.assertIn(
            "surface seller-bot-marketplace-fbs implementation_gate open requires characterization_tests.rendering_snapshots complete or not-applicable",
            errors,
        )

    def test_rejects_missing_eligible_packet(self):
        registry = copy.deepcopy(self.registry)
        del registry["packets"]["theants"]

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "eligible backlog surface theants requires readiness packet",
            errors,
        )

    def test_rejects_missing_already_aiogram_packet(self):
        registry = copy.deepcopy(self.registry)
        del registry["packets"]["vpnbot"]

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "eligible backlog surface vpnbot requires readiness packet",
            errors,
        )

    def test_rejects_missing_core_seed_packet(self):
        registry = copy.deepcopy(self.registry)
        del registry["packets"]["codex-telegram"]

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "eligible backlog surface codex-telegram requires readiness packet",
            errors,
        )

    def test_rejects_missing_metamask_eligible_packet(self):
        registry = copy.deepcopy(self.registry)
        del registry["packets"]["metamask-telegram-bot"]

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "eligible backlog surface metamask-telegram-bot requires readiness packet",
            errors,
        )

    def test_rejects_secret_value_like_field(self):
        registry = copy.deepcopy(self.registry)
        packet = registry["packets"]["seller-bot-marketplace-fbs"]
        packet["secret_governance"]["bot_token"] = "unexpected-placeholder"

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs.secret_governance has unexpected fields: ['bot_token']",
            errors,
        )

    def test_rejects_secret_like_value_in_free_text_field(self):
        registry = copy.deepcopy(self.registry)
        token_like = "".join(["123", "456", ":", "ABCdef", "GhIJkl", "MNopQR"])
        registry["packets"]["seller-bot-marketplace-fbs"]["missing_evidence"].append(
            f"Token-like placeholder {token_like} must not appear here."
        )

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs.missing_evidence[8] contains secret-like value",
            errors,
        )

    def test_rejects_non_workspace_relative_role_route_target(self):
        registry = copy.deepcopy(self.registry)
        registry["packets"]["seller-bot-marketplace-fbs"]["role_route_target"] = "bot_marketplace_fbs"

        errors = _READINESS.validate_registry(registry, self.backlog, self.role_catalog)

        self.assertIn(
            "surface seller-bot-marketplace-fbs role_route_target does not match backlog role_route_target",
            errors,
        )


class TelegramValidatorCliErrorTests(unittest.TestCase):
    def test_migration_backlog_cli_missing_role_catalog_has_stable_error(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_READINESS.PLUGIN_ROOT / "scripts/telegram_migration_backlog.py"),
                "--role-catalog",
                "/tmp/does-not-exist.json",
                "validate",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "ERROR: role catalog not found: /tmp/does-not-exist.json\n")
        self.assertNotIn("Traceback", result.stderr)

    def test_runtime_readiness_cli_missing_role_catalog_has_stable_error(self):
        result = subprocess.run(
            [
                sys.executable,
                str(_READINESS.PLUGIN_ROOT / "scripts/telegram_runtime_readiness.py"),
                "--role-catalog",
                "/tmp/does-not-exist.json",
                "validate",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "ERROR: role catalog not found: /tmp/does-not-exist.json\n")
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
