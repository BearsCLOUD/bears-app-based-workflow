from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/plugin_cache_sync.py"
FIXTURE_PATH = PLUGIN_ROOT / "tests/fixtures/plugin_cache_sync/plugin-cache-sync-state.valid.json"

spec = importlib.util.spec_from_file_location("plugin_cache_sync", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scripts/plugin_cache_sync.py")
plugin_cache_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_cache_sync)


class PluginCacheSyncTests(unittest.TestCase):
    def test_valid_fixture_has_delivery_complete_shape(self) -> None:
        packet = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(packet["schema"], plugin_cache_sync.SCHEMA)
        self.assertTrue(packet["delivery_complete"])
        self.assertEqual(packet["local_commit_validation"]["status"], "pass")
        self.assertEqual(packet["local_commit_validation"]["commit_sha"], packet["main_sha"])
        self.assertEqual(packet["cache_sync"]["status"], "success")
        self.assertEqual(packet["effective_hooks_proof"]["manifest_hooks"], "./hooks.json")

    def test_verify_cache_requires_exact_sha_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin/plugin.json").write_text(json.dumps({"hooks": "./hooks.json"}), encoding="utf-8")
            (root / "hooks.json").write_text("{}", encoding="utf-8")
            (root / "hooks").mkdir()
            result = plugin_cache_sync.verify_cache(root, "abc")
        self.assertEqual(result["status"], "fail")
        self.assertIn("installed cache SHA does not match passed main SHA", result["errors"])
        self.assertEqual(result["manifest_hooks"], "./hooks.json")
        self.assertTrue(result["hooks_json_present"])
        self.assertTrue(result["hooks_dir_present"])

    def test_defect_state_keeps_cache_unchanged(self) -> None:
        packet = plugin_cache_sync.build_defect_state(
            state_path=Path("runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"),
            sha="0" * 40,
            status="fail",
            action="workflow_defect",
            reason="local commit validation failed",
        )
        self.assertFalse(packet["delivery_complete"])
        self.assertEqual(packet["cache_sync"]["action"], "cache_unchanged")
        self.assertEqual(packet["workflow_defect"]["status"], "open")
        self.assertEqual(packet["local_commit_validation"]["status"], "fail")

    def test_async_validation_state_falls_back_to_exact_lcv_when_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = "1" * 40
            state_dir = root / "validation-state" / sha
            state_dir.mkdir(parents=True)
            (state_dir / "validation-state.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "bears-validation-state.v1",
                        "status": "queued",
                        "commit_sha": sha,
                    }
                ),
                encoding="utf-8",
            )
            proof_dir = root / "local-commit-validation"
            proof_dir.mkdir()
            (proof_dir / f"{sha}.json").write_text(
                json.dumps(
                    {
                        "schema": "bears-local-commit-validation.v1",
                        "status": "pass",
                        "commit_sha": sha,
                    }
                ),
                encoding="utf-8",
            )
            packet, error = plugin_cache_sync.read_validation_gate(
                root / "validation-state",
                proof_dir,
                sha,
            )
        self.assertIsNone(error)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["schema"], "bears-local-commit-validation.v1")

    def test_async_validation_state_pass_satisfies_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = "2" * 40
            state_dir = root / "validation-state" / sha
            state_dir.mkdir(parents=True)
            (state_dir / "validation-state.v1.json").write_text(
                json.dumps(
                    {
                        "schema": "bears-validation-state.v1",
                        "status": "pass",
                        "commit_sha": sha,
                        "selected_tests": ["tests/test_async_validation.py"],
                    }
                ),
                encoding="utf-8",
            )
            packet, error = plugin_cache_sync.read_validation_gate(
                root / "validation-state",
                root / "local-commit-validation",
                sha,
            )
        self.assertIsNone(error)
        self.assertEqual(packet["status"], "pass")


if __name__ == "__main__":
    unittest.main()
