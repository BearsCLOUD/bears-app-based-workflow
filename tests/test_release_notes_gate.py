import json
import tempfile
import unittest
from pathlib import Path

from scripts import release_notes_gate


class ReleaseNotesGateTests(unittest.TestCase):
    def test_validate_accepts_catalog_notes_and_fixtures(self) -> None:
        self.assertEqual(release_notes_gate.validate_all(), [])

    def test_behavior_change_without_entry_fails(self) -> None:
        errors = release_notes_gate.check_paths(["scripts/uncovered_validator.py"])
        self.assertIn("missing release note coverage: scripts/uncovered_validator.py", errors)

    def test_behavior_change_with_entry_passes(self) -> None:
        errors = release_notes_gate.check_paths(["scripts/release_notes_gate.py"])
        self.assertEqual(errors, [])

    def test_tests_only_change_does_not_require_release_note(self) -> None:
        errors = release_notes_gate.check_paths(["tests/test_release_notes_gate.py"])
        self.assertEqual(errors, [])

    def test_schema_requires_entry_impact(self) -> None:
        bad = release_notes_gate.BAD / "missing-entry-field.json"
        errors = release_notes_gate.validate_notes(bad)
        self.assertTrue(errors)

    def test_explicit_exemption_covers_matched_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_notes = release_notes_gate.RELEASE_NOTES
            path = Path(tmp) / "release-notes.json"
            packet = {
                "schema": "bears-release-notes.v1",
                "version": "1",
                "updated": "2026-06-24",
                "entries": [],
                "exemptions": [
                    {
                        "date": "2026-06-24",
                        "issue_ref": "#384",
                        "reason": "Comment-only catalog wording; no runtime behavior change.",
                        "files": ["assets/catalog/comment-only.v1.json"],
                    }
                ],
            }
            path.write_text(json.dumps(packet), encoding="utf-8")
            release_notes_gate.RELEASE_NOTES = path
            try:
                self.assertEqual(release_notes_gate.validate_notes(path), [])
                self.assertEqual(release_notes_gate.check_paths(["assets/catalog/comment-only.v1.json"]), [])
            finally:
                release_notes_gate.RELEASE_NOTES = original_notes


if __name__ == "__main__":
    unittest.main()
