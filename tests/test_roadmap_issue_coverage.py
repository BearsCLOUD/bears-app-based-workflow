from __future__ import annotations

import json
import unittest

from scripts import roadmap_issue_coverage

FIXTURE_ROOT = roadmap_issue_coverage.PLUGIN_ROOT / "tests/fixtures/roadmap_issue_coverage"
GOOD_ISSUES = FIXTURE_ROOT / "good/issues-metadata.v1.json"
BAD_ISSUES = FIXTURE_ROOT / "bad/issues-metadata-missing.v1.json"
GOOD_ROADMAP = FIXTURE_ROOT / "good/workflow-roadmap.v1.json"
GOOD_PRIORITY = FIXTURE_ROOT / "good/issue-execution-priority.v1.json"


class RoadmapIssueCoverageTests(unittest.TestCase):
    def test_validate_all_accepts_catalogs_and_fixture_expectations(self) -> None:
        self.assertEqual(roadmap_issue_coverage.validate_all(), [])

    def test_check_roadmap_passes_covered_fixture(self) -> None:
        issues, errors, source = roadmap_issue_coverage.issue_metadata_from_arg(str(GOOD_ISSUES), roadmap_issue_coverage.COVERAGE_CATALOG)
        packet = roadmap_issue_coverage.check_roadmap(
            issues=issues,
            issue_errors=errors,
            issue_source=source,
            roadmap_path=GOOD_ROADMAP,
        )
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["counts"]["missing"], 0)

    def test_check_roadmap_fails_missing_issue(self) -> None:
        issues, errors, source = roadmap_issue_coverage.issue_metadata_from_arg(str(BAD_ISSUES), roadmap_issue_coverage.COVERAGE_CATALOG)
        packet = roadmap_issue_coverage.check_roadmap(
            issues=issues,
            issue_errors=errors,
            issue_source=source,
            roadmap_path=GOOD_ROADMAP,
        )
        self.assertEqual(packet["status"], "fail")
        self.assertEqual(packet["missing_roadmap_issues"][0]["issue_ref"], "#3")

    def test_check_priority_passes_covered_p0_fixture(self) -> None:
        issues, errors, source = roadmap_issue_coverage.issue_metadata_from_arg(str(GOOD_ISSUES), roadmap_issue_coverage.PRIORITY_FRESHNESS_CATALOG)
        packet = roadmap_issue_coverage.check_priority(
            issues=issues,
            issue_errors=errors,
            issue_source=source,
            priority_path=GOOD_PRIORITY,
        )
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["counts"]["missing_priority_issues"], 0)

    def test_check_priority_fails_missing_p0_issue(self) -> None:
        issues, errors, source = roadmap_issue_coverage.issue_metadata_from_arg(str(BAD_ISSUES), roadmap_issue_coverage.PRIORITY_FRESHNESS_CATALOG)
        packet = roadmap_issue_coverage.check_priority(
            issues=issues,
            issue_errors=errors,
            issue_source=source,
            priority_path=GOOD_PRIORITY,
        )
        self.assertEqual(packet["status"], "fail")
        self.assertEqual(packet["missing_priority_issues"][0]["issue_ref"], "#3")

    def test_raw_body_metadata_is_rejected_without_persisted_fixture(self) -> None:
        _, errors = roadmap_issue_coverage.normalize_issues([
            {
                "number": 9,
                "issue_ref": "#9",
                "title": "P0: raw body rejected",
                "state": "OPEN",
                "url": "https://github.com/example/repo/issues/9",
                "labels": ["P0"],
                "updated_at": "2026-06-27T00:00:00Z",
                "body": "not persisted by this gate",
            }
        ])
        self.assertTrue(any("forbidden issue metadata fields" in item for item in errors))

    def test_cli_commands_emit_json_packets(self) -> None:
        self.assertEqual(roadmap_issue_coverage.main(["validate", "--json"]), 0)
        self.assertEqual(
            roadmap_issue_coverage.main([
                "check-roadmap",
                "--issues-json",
                str(GOOD_ISSUES),
                "--roadmap",
                str(GOOD_ROADMAP),
                "--json",
            ]),
            0,
        )
        self.assertEqual(
            roadmap_issue_coverage.main([
                "check-priority",
                "--issues-json",
                str(GOOD_ISSUES),
                "--priority",
                str(GOOD_PRIORITY),
                "--json",
            ]),
            0,
        )

    def test_current_catalog_defaults_report_missing_freshness(self) -> None:
        packet = roadmap_issue_coverage.doctor_packet(None, roadmap_issue_coverage.ROADMAP_CATALOG, roadmap_issue_coverage.PRIORITY_CATALOG)
        self.assertEqual(packet["status"], "fail")
        self.assertTrue(packet["checks"][0]["missing_roadmap_issues"])
        self.assertTrue(packet["checks"][1]["missing_priority_issues"])


if __name__ == "__main__":
    unittest.main()
