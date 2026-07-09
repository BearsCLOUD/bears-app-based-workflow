from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import github_issue_ref

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/github_issue_ref.py"


class GitHubIssueRefTests(unittest.TestCase):
    def test_full_repo_refs_with_same_number_are_distinct(self) -> None:
        platform = github_issue_ref.normalize_issue_ref(ref="BearsCLOUD/bears-platform#66")
        infra = github_issue_ref.normalize_issue_ref(ref="BearsCLOUD/bears-infra#66")
        self.assertEqual(platform["status"], "pass")
        self.assertEqual(infra["status"], "pass")
        self.assertNotEqual(platform["canonical_ref"], infra["canonical_ref"])

    def test_local_ref_requires_explicit_repo(self) -> None:
        blocked = github_issue_ref.normalize_issue_ref(ref="#66")
        self.assertEqual(blocked["status"], "blocked")
        normalized = github_issue_ref.normalize_issue_ref(ref="#66", repo="BearsCLOUD/bears-platform")
        self.assertEqual(normalized["canonical_ref"], "BearsCLOUD/bears-platform#66")
        self.assertEqual(normalized["legacy_local_ref"], "#66")

    def test_proposed_requires_repo_without_issue_number(self) -> None:
        proposed = github_issue_ref.normalize_issue_ref(repo="BearsCLOUD/future-seller", state="proposed")
        self.assertEqual(proposed["status"], "pass")
        self.assertEqual(proposed["repo"], "BearsCLOUD/future-seller")
        self.assertIsNone(proposed["issue_number"])
        self.assertEqual(github_issue_ref.validate_packet(proposed), [])

    def test_validate_all_accepts_good_and_expected_bad_fixtures(self) -> None:
        self.assertEqual(github_issue_ref.validate_all(), [])

    def test_compare_cli_reports_different_identities(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "compare",
                "--left",
                "BearsCLOUD/bears-platform#66",
                "--right",
                "BearsCLOUD/bears-infra#66",
                "--json",
            ],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["same_identity"])
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
