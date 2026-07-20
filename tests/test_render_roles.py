from __future__ import annotations

import contextlib
import copy
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("render_roles", ROOT / "scripts/render_roles.py")
render_roles = importlib.util.module_from_spec(_spec)
sys.modules["render_roles"] = render_roles
_spec.loader.exec_module(render_roles)


class RenderRolesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ir = render_roles.load_ir()

    def test_ir_defines_exactly_the_three_bounded_roles(self) -> None:
        self.assertEqual({role["name"] for role in self.ir["roles"]}, {"app-worker", "app-reviewer", "app-analyst"})
        self.assertEqual({role["kind"] for role in self.ir["roles"]}, {"worker", "critic", "reader"})
        self.assertEqual(set(self.ir["servers"]), {"app-workflow", "app-workflow-maintainer"})

    def test_committed_artifacts_match_a_fresh_render(self) -> None:
        for path, content in render_roles.render_all(self.ir).items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), content, path)
        self.assertEqual(render_roles.stale_artifacts(self.ir), [])

    @staticmethod
    def check() -> int:
        """Run --check quietly; the renderer reports drift on stdout/stderr."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return render_roles.main(["--check"])

    def test_check_mode_passes_on_the_committed_tree(self) -> None:
        self.assertEqual(self.check(), 0)

    def test_check_mode_detects_a_perturbed_artifact(self) -> None:
        path = ROOT / "claude/agents/app-reviewer.md"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original.replace("model: opus", "model: haiku"), encoding="utf-8")
            self.assertEqual(self.check(), 1)
        finally:
            path.write_text(original, encoding="utf-8")
        self.assertEqual(self.check(), 0)

    def test_check_mode_detects_a_stale_artifact_file(self) -> None:
        path = ROOT / "agents/repo-orchestrator.toml"
        self.assertFalse(path.exists())
        try:
            path.write_text('name = "repo-orchestrator"\n', encoding="utf-8")
            self.assertIn(path, render_roles.stale_artifacts(self.ir))
            self.assertEqual(self.check(), 1)
        finally:
            path.unlink(missing_ok=True)

    def test_ir_rejects_maintainer_access_for_a_bounded_role(self) -> None:
        broken = copy.deepcopy(self.ir)
        self.role_of(broken, "app-analyst")["mcp"]["app-workflow-maintainer"] = ["phase_record"]
        with self.assertRaises(render_roles.IRError):
            self.validate(broken)

    def test_ir_rejects_mcp_access_for_the_worker(self) -> None:
        broken = copy.deepcopy(self.ir)
        self.role_of(broken, "app-worker")["mcp"] = {"app-workflow": ["project_status"]}
        with self.assertRaises(render_roles.IRError):
            self.validate(broken)

    def test_ir_rejects_text_that_would_break_an_artifact(self) -> None:
        for field, value in (("description", 'a "quoted" summary'), ("identity", "line one\nline two"), ("final_message", 'ends with """')):
            broken = copy.deepcopy(self.ir)
            self.role_of(broken, "app-worker")[field] = value
            with self.assertRaises(render_roles.IRError, msg=field):
                self.validate(broken)

    def test_ir_rejects_unknown_tool_names(self) -> None:
        broken = copy.deepcopy(self.ir)
        self.role_of(broken, "app-reviewer")["mcp"]["app-workflow"] = ["not_a_tool"]
        with self.assertRaises(render_roles.IRError):
            self.validate(broken)

    @staticmethod
    def role_of(ir: dict, name: str) -> dict:
        return next(role for role in ir["roles"] if role["name"] == name)

    def validate(self, ir: dict) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.json"
            path.write_text(json.dumps(ir), encoding="utf-8")
            render_roles.load_ir(path)


if __name__ == "__main__":
    unittest.main()
