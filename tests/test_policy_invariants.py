"""Tests for the policy invariant gate."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "policy_invariants.py"
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures" / "policy_invariants"

EXPECTED_BAD_FIXTURES = {
    "bad/solved-open.json": "solved_covered_issue_not_open",
    "bad/missing-changelog.json": "behavior_change_has_changelog",
    "bad/missing-decision.json": "governance_change_has_decision",
    "bad/partial-auto-close.json": "non_final_issue_not_auto_closed",
    "bad/forbidden-raw-data.json": "audit_artifacts_no_forbidden_raw_data",
}


class PolicyInvariantTests(unittest.TestCase):
    """Validate policy invariant CLI behavior."""

    def run_cli(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        """Run the invariant CLI and parse its JSON output."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - assertion aid
            self.fail(f"stdout is not JSON: {exc}: {result.stdout!r}; stderr={result.stderr!r}")
        return result, payload

    def test_validate_command_passes_on_required_fixtures(self) -> None:
        result, payload = self.run_cli("validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["schema"], "bears-policy-invariant-validation.v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["errors"], [])

    def test_good_fixture_passes_evaluate(self) -> None:
        packet = FIXTURES / "good" / "pass.json"
        result, payload = self.run_cli("evaluate", "--input", packet.relative_to(PLUGIN_ROOT).as_posix(), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["schema"], "bears-policy-invariant-result.v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["summary"]["passed"], 5)
        self.assertEqual(payload["summary"]["failed"], 0)
        self.assertEqual(payload["errors"], [])
        self.assertEqual({item["status"] for item in payload["checks"]}, {"pass"})

    def test_bad_fixtures_fail_expected_checks(self) -> None:
        for rel_path, expected_code in EXPECTED_BAD_FIXTURES.items():
            with self.subTest(path=rel_path):
                packet = FIXTURES / rel_path
                result, payload = self.run_cli("evaluate", "--input", packet.relative_to(PLUGIN_ROOT).as_posix(), "--json")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(payload["schema"], "bears-policy-invariant-result.v1")
                self.assertEqual(payload["status"], "fail")
                self.assertIn(expected_code, {item["id"] for item in payload["checks"] if item["status"] == "fail"})
                self.assertTrue(any(error.startswith(expected_code + ": ") for error in payload["errors"]))

    def test_evaluate_closeout_from_git_emits_stable_json(self) -> None:
        result, payload = self.run_cli("evaluate-closeout", "--from-git", "HEAD^..HEAD", "--json")
        self.assertIn(result.returncode, {0, 1}, result.stderr)
        self.assertEqual(payload["schema"], "bears-policy-invariant-result.v1")
        self.assertIn(payload["status"], {"pass", "fail"})
        self.assertIn("checks", payload)


if __name__ == "__main__":
    unittest.main()
