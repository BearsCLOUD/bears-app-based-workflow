import json
import unittest

from scripts import delivery_manifest

GOOD = delivery_manifest.PLUGIN_ROOT / "tests/fixtures/delivery_manifest/good/minimal.json"
BAD = delivery_manifest.PLUGIN_ROOT / "tests/fixtures/delivery_manifest/bad/closed-without-doctor.json"


class DeliveryManifestTests(unittest.TestCase):
    def test_validate_all_accepts_good_and_rejects_bad(self) -> None:
        self.assertEqual(delivery_manifest.validate_all(), [])

    def test_closed_manifest_requires_doctor_and_validation_pass(self) -> None:
        packet = json.loads(BAD.read_text(encoding="utf-8"))
        joined = "\n".join(delivery_manifest.validate_manifest(packet))
        self.assertIn("closed delivery requires doctor pass", joined)
        self.assertIn("closed delivery requires validation pass", joined)

    def test_good_manifest_is_operator_reference_by_delivery_id(self) -> None:
        packet = json.loads(GOOD.read_text(encoding="utf-8"))
        self.assertEqual(packet["delivery_id"], "bears-governance-kernel-v1")
        self.assertEqual(packet["validation"]["status"], "pass")
        self.assertEqual(delivery_manifest.validate_manifest(packet), [])

    def test_closeout_ready_manifest_requires_canonical_delivery_id(self) -> None:
        packet = json.loads((delivery_manifest.PLUGIN_ROOT / "tests/fixtures/delivery_manifest/bad/delivery-id-mismatch.json").read_text(encoding="utf-8"))
        joined = "\n".join(delivery_manifest.validate_manifest(packet))
        self.assertIn("delivery_id must equal canonical bears-governance-kernel-v1", joined)

    def test_closeout_ready_manifest_requires_covered_issues(self) -> None:
        packet = json.loads(GOOD.read_text(encoding="utf-8"))
        packet.pop("covered_issues")
        for issue in packet["issues"]:
            issue.pop("closeout_state", None)
        joined = "\n".join(delivery_manifest.validate_manifest(packet))
        self.assertIn("closeout delivery requires covered_issues classifications", joined)

    def test_covered_issues_prefer_canonical_rows(self) -> None:
        packet = json.loads(GOOD.read_text(encoding="utf-8"))
        packet["issues"][0]["closeout_state"] = "manual_review"
        rows = delivery_manifest.covered_issues(packet)
        self.assertEqual(rows[0]["classification"], "closed")


if __name__ == "__main__":
    unittest.main()
