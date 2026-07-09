import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import external_review_contract


FIXTURES = external_review_contract.PLUGIN_ROOT / "tests/fixtures/external_review_contract"


class ExternalReviewContractTests(unittest.TestCase):
    def load(self, name: str) -> dict[str, object]:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_validate_accepts_good_fixture(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "1"}, clear=False):
            with mock.patch("scripts.external_review_contract.shutil.which", return_value=None):
                packet = external_review_contract.validate_bundle()
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["good_packet"]["status"], "pass")
        self.assertEqual(packet["cue_pilot"]["status"], "tool_missing")

    def test_check_reports_tool_missing_when_cue_is_absent(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "1"}, clear=False):
            with mock.patch("scripts.external_review_contract.shutil.which", return_value=None):
                packet = external_review_contract.check_packet_path(FIXTURES / "good/closed_with_proof.json")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["cue_pilot"]["status"], "tool_missing")

    def test_check_reports_pilot_disabled_explicitly(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "0"}, clear=False):
            packet = external_review_contract.check_packet_path(FIXTURES / "good/closed_with_proof.json")
        self.assertEqual(packet["cue_pilot"]["status"], "pilot_disabled")

    def test_good_fixture_passes(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "0"}, clear=False):
            packet = external_review_contract.check_packet_path(FIXTURES / "good/closed_with_proof.json")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["review_state"], "closed")
        self.assertEqual(packet["errors"], [])

    def test_closed_packet_needs_proof(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "0"}, clear=False):
            packet = external_review_contract.check_packet_path(FIXTURES / "bad/missing_proof.json")
        self.assertEqual(packet["status"], "fail")
        self.assertIn("closed or superseded packet requires proof", packet["errors"])

    def test_behavior_change_needs_changelog(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "0"}, clear=False):
            packet = external_review_contract.check_packet_path(FIXTURES / "bad/missing_changelog.json")
        self.assertEqual(packet["status"], "fail")
        self.assertIn("behavior-changing surface requires changelog", packet["errors"])

    def test_governance_change_needs_decision(self) -> None:
        with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "0"}, clear=False):
            packet = external_review_contract.check_packet_path(FIXTURES / "bad/missing_decision.json")
        self.assertEqual(packet["status"], "fail")
        self.assertIn("governance change requires decision", packet["errors"])

    def test_packet_requires_schema_ref_to_source_of_truth(self) -> None:
        packet = copy.deepcopy(self.load("good/closed_with_proof.json"))
        packet["json_schema_ref"] = "assets/schemas/external-review-audit.v1.schema.json#/$defs/other"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.dict(os.environ, {external_review_contract.PILOT_ENV: "0"}, clear=False):
                result = external_review_contract.check_packet_path(path)
        self.assertEqual(result["status"], "fail")
        self.assertIn("json_schema_ref must point at the external review audit contract packet schema", result["errors"])


if __name__ == "__main__":
    unittest.main()
