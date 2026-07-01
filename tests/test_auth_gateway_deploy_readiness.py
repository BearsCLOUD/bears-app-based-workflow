from __future__ import annotations

import copy
import importlib.util
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "auth_gateway_deploy_readiness.py"
spec = importlib.util.spec_from_file_location("auth_gateway_deploy_readiness", SCRIPT_PATH)
readiness = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(readiness)  # type: ignore[arg-type]


class AuthGatewayDeployReadinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.packet = readiness.load_json(PLUGIN_ROOT / "assets/catalog/auth-gateway-deploy-readiness.v1.json")
        cls.catalog = readiness.load_json(PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json")

    def test_current_packet_validates(self) -> None:
        self.assertEqual(readiness.validate_packet(self.packet, catalog=self.catalog), [])

    def test_cli_validate_success_has_clean_stderr(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("auth/gateway/deploy readiness ok", result.stdout)

    def test_cli_missing_packet_has_stable_stderr(self) -> None:
        missing_packet = PLUGIN_ROOT / "tmp-missing-readiness-packet.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--packet", str(missing_packet), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), f"ERROR: packet not found: {missing_packet}")
        self.assertNotIn("[Errno", result.stderr)

    def test_cli_missing_catalog_has_stable_stderr(self) -> None:
        missing_catalog = PLUGIN_ROOT / "tmp-missing-platform-role-catalog.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--catalog", str(missing_catalog), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), f"ERROR: catalog not found: {missing_catalog}")
        self.assertNotIn("[Errno", result.stderr)

    def test_rejects_wrong_spine_order(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["ordered_spine"] = ["bears_gateway", "auth_core", "cd_deploy_stage"]
        packet["surfaces"] = [packet["surfaces"][1], packet["surfaces"][0], packet["surfaces"][2]]
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertTrue(any("ordered_spine" in error for error in errors))
        self.assertTrue(any("surfaces must be ordered" in error for error in errors))

    def test_rejects_open_gate_before_auth_core(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["surfaces"][1]["implementation_gate"] = "open"
        packet["surfaces"][1]["readiness_status"] = "ready"
        packet["surfaces"][1]["blocking_evidence"] = []
        packet["surfaces"][1]["rollback_plan"]["status"] = "validated"
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertTrue(any("cannot open before earlier spine surfaces" in error for error in errors))

    def test_rejects_role_route_drift(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["surfaces"][1]["primary_role"] = "bears-auth-platform-engineer"
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertTrue(any("does not match route role" in error for error in errors))

    def test_current_packet_uses_neutral_core_route_targets(self) -> None:
        for surface in self.packet["surfaces"]:
            with self.subTest(surface=surface["surface"]):
                expected = readiness.NEUTRAL_CORE_ROUTE_TARGETS[surface["surface"]]
                self.assertEqual(surface["canonical_path"], expected)
                self.assertEqual(surface["route_target"], expected)
                self.assertEqual(
                    surface["repo_artifacts"]["repo_root"],
                    "/srv/bears/dev/platform",
                )
                self.assertFalse(
                    any("projects/seller/apps/" in command for command in surface["safe_validation_commands"])
                )
                self.assertIn("legacy_source_refs", surface)

    def test_route_only_packet_does_not_require_file_backed_command(self) -> None:
        packet = copy.deepcopy(self.packet)
        for surface in packet["surfaces"]:
            surface["safe_validation_commands"] = [
                command for command in surface["safe_validation_commands"] if "--check-files validate" not in command
            ]
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertEqual(errors, [])

    def test_rejects_seller_path_as_required_core_input(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["surfaces"][2]["canonical_path"] = "/srv/bears/projects/seller/apps/cd_deploy_stage"
        packet["surfaces"][2]["route_target"] = "/srv/bears/projects/seller/apps/cd_deploy_stage"
        packet["surfaces"][2]["safe_validation_commands"].append(
            "cd /srv/bears/projects/seller/apps/cd_deploy_stage && python3 scripts/validate_deploy_contract.py"
        )
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertTrue(any("must not use a seller legacy path" in error for error in errors))
        self.assertTrue(any("safe_validation_commands must not require seller legacy paths" in error for error in errors))

    def test_rejects_non_neutral_repo_artifact_root(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["surfaces"][0]["repo_artifacts"]["repo_root"] = "/srv/bears/projects/seller"
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertTrue(
            any("repo_artifacts.repo_root must be /srv/bears/dev/platform" in error for error in errors)
        )

    def test_check_files_validates_repo_artifacts_at_repo_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=PLUGIN_ROOT) as tmp:
            repo_root = Path(tmp) / "bears-platform"
            canonical_path = repo_root / "src" / "bears_platform" / "deploy"
            canonical_path.mkdir(parents=True)
            for filename in ("AGENTS.md", "SPEC.md", "requirements.md"):
                (repo_root / filename).write_text(f"# {filename}\n", encoding="utf-8")
            surface = {
                "surface": "cd_deploy_stage",
                "canonical_path": str(canonical_path),
                "repo_artifacts": {
                    "repo_root": str(repo_root),
                    "required": ["AGENTS.md", "SPEC.md", "requirements.md"],
                    "present": ["AGENTS.md", "SPEC.md", "requirements.md"],
                    "missing": [],
                },
            }
            errors: list[str] = []
            readiness._validate_repo_artifacts(surface, errors, check_files=True)
            self.assertEqual(errors, [])

    def test_check_files_requires_exact_root_registry_entry(self) -> None:
        canonical_path = "/srv/bears/dev/platform/src/bears_platform/deploy"
        surface = {
            "surface": "cd_deploy_stage",
            "canonical_path": canonical_path,
        }
        errors: list[str] = []
        readiness._validate_registry_exact_entry(
            surface,
            errors,
            check_files=True,
            registry={"entries": [{"status": "registered", "paths": [canonical_path]}]},
        )
        self.assertEqual(errors, [])

        errors = []
        readiness._validate_registry_exact_entry(
            surface,
            errors,
            check_files=True,
            registry={"entries": [{"status": "registered", "paths": ["/srv/bears/dev/platform"]}]},
        )
        self.assertTrue(any("root registry exact entry missing" in error for error in errors))

    def test_rejects_stale_repo_artifact_presence(self) -> None:
        with tempfile.TemporaryDirectory(dir=PLUGIN_ROOT) as tmp:
            repo_root = Path(tmp) / "bears-platform"
            canonical_path = repo_root / "src" / "bears_platform" / "auth"
            canonical_path.mkdir(parents=True)
            (repo_root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
            surface = copy.deepcopy(self.packet["surfaces"][0])
            surface["canonical_path"] = str(canonical_path)
            surface["repo_artifacts"] = {
                "repo_root": str(repo_root),
                "required": ["AGENTS.md", "SPEC.md", "requirements.md"],
                "present": ["AGENTS.md", "SPEC.md", "requirements.md"],
                "missing": [],
            }
            errors: list[str] = []
            readiness._validate_repo_artifacts(surface, errors, check_files=True)
        self.assertTrue(any("repo_artifacts.present is stale" in error for error in errors))
        self.assertTrue(any("repo_artifacts.missing is stale" in error for error in errors))

    def test_rejects_secret_value_like_text(self) -> None:
        packet = copy.deepcopy(self.packet)
        packet["surfaces"][0]["blocking_evidence"][0]["detail"] = "token = abcdefghijklmnop123456"
        errors = readiness.validate_packet(packet, catalog=self.catalog, check_files=False)
        self.assertTrue(any("raw secret value" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
