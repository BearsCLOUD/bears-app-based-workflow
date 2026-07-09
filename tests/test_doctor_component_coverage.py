"""Tests for bears_doctor component coverage reconciliation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import doctor_component_coverage as coverage


class DoctorComponentCoverageTests(unittest.TestCase):
    """Validate issue-to-doctor coverage behavior."""

    def test_validate_catalog_passes(self) -> None:
        self.assertEqual([], coverage.validate_all())

    def test_missing_doctor_check_gap(self) -> None:
        fixture = coverage.load_json(coverage.BAD_DIR / "missing_doctor_check.json")
        packet = coverage.reconcile_components(fixture["components"], generated_at=fixture["generated_at"])
        self.assertIn("missing_doctor_check", {row["gap_type"] for row in packet["gaps"]})
        self.assertEqual("fail", "fail" if packet["summary"]["blocking_count"] else "pass")

    def test_missing_test_selection_gap(self) -> None:
        fixture = coverage.load_json(coverage.BAD_DIR / "missing_test_selection.json")
        packet = coverage.reconcile_components(fixture["components"], generated_at=fixture["generated_at"])
        self.assertIn("missing_test_selection", {row["gap_type"] for row in packet["gaps"]})

    def test_closed_issue_still_not_available_gap(self) -> None:
        fixture = coverage.load_json(coverage.BAD_DIR / "closed_missing.json")
        packet = coverage.reconcile_components(fixture["components"], generated_at=fixture["generated_at"])
        self.assertIn("closed_issue_still_not_available", {row["gap_type"] for row in packet["gaps"]})

    def test_unsafe_autostart_gap(self) -> None:
        fixture = coverage.load_json(coverage.BAD_DIR / "unsafe_autostart.json")
        packet = coverage.reconcile_components(fixture["components"], generated_at=fixture["generated_at"])
        self.assertIn("unsafe_autostart_without_doctor_gate", {row["gap_type"] for row in packet["gaps"]})

    def test_not_applicable_with_evidence_is_not_missing(self) -> None:
        fixture = coverage.load_json(coverage.GOOD_DIR / "not_applicable.json")
        packet = coverage.reconcile_components(fixture["components"], generated_at=fixture["generated_at"])
        self.assertEqual([], packet["gaps"])
        self.assertEqual(0, packet["summary"]["blocking_count"])

    def test_doctor_packet_passes_with_summary_fields(self) -> None:
        packet = coverage.doctor_packet()
        self.assertEqual("pass", packet["status"])
        self.assertIn("doctor_component_coverage_status", packet)
        self.assertIn("missing_doctor_check_count", packet)
        self.assertIn("partial_doctor_coverage_count", packet)
        self.assertIn("closed_issue_still_not_available_count", packet)
        self.assertIn("unsafe_autostart_without_doctor_gate_count", packet)

    def test_scan_fixture_is_bounded_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "issues.json"
            fixture.write_text(
                json.dumps(
                    {
                        "issues": [
                            {
                                "number": 903,
                                "title": "Fixture issue",
                                "state": "OPEN",
                                "body": "bears_doctor must report fixture_status\npython3 scripts/fixture.py validate\nassets/catalog/fixture.v1.json",
                                "labels": [{"name": "bears:auto-start"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            packet = coverage.scan("BearsCLOUD/bears_plugin", fixture)
        self.assertEqual("bears-doctor-component-coverage.v1", packet["schema"])
        self.assertNotIn("bears_doctor must report", json.dumps(packet))
        self.assertGreater(packet["summary"]["blocking_count"], 0)

    def test_diff_reports_new_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.json"
            head = Path(tmp) / "head.json"
            base.write_text(json.dumps(coverage.reconcile_components([], generated_at="2026-06-25T00:00:00Z")), encoding="utf-8")
            fixture = coverage.load_json(coverage.BAD_DIR / "missing_doctor_check.json")
            head.write_text(json.dumps(coverage.reconcile_components(fixture["components"], generated_at=fixture["generated_at"])), encoding="utf-8")
            packet = coverage.diff_packets(base, head)
        self.assertEqual("fail", packet["status"])
        self.assertTrue(packet["new_gaps"])


if __name__ == "__main__":
    unittest.main()
