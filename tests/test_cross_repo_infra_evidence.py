from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import cross_repo_infra_evidence, gitops_degradation


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class CrossRepoInfraEvidenceTest(unittest.TestCase):
    def test_doctor_passes(self) -> None:
        self.assertEqual("pass", cross_repo_infra_evidence.doctor()["status"])

    def test_missing_bundle_provenance_produces_required_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet = cross_repo_infra_evidence.scan(Path(tmp), "opencode-server", "issue-450-fixture")
        signals = {row["signal"] for row in packet["degradation_events"]}
        self.assertIn("infra_bundle_provenance_missing", signals)
        self.assertEqual("missing", next(row for row in packet["evidence_packets"] if row["source_issue"] == "#118")["status"])
        self.assertEqual([], cross_repo_infra_evidence.validate_packet(packet, "missing-fixture"))

    def test_failed_public_route_policy_produces_required_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for issue, packet_type in [
                ("#117", "infra_validation_matrix"),
                ("#118", "opencode_bundle_provenance"),
                ("#120", "opencode_rollout_diagnostics"),
                ("#121", "opencode_runtime_egress_policy"),
                ("#123", "opencode_runtime_health_policy"),
            ]:
                write_json(root / filename_for(packet_type), {"status": "pass", "source_issue": issue})
            write_json(root / "runtime/opencode/opencode-public-route-policy.v1.json", {"status": "fail", "errors": ["auth policy failed"]})
            packet = cross_repo_infra_evidence.scan(root, "opencode-server", "issue-450-fixture")
        signals = {row["signal"] for row in packet["degradation_events"]}
        self.assertIn("infra_public_route_policy_failed", signals)

    def test_each_required_failed_policy_signal(self) -> None:
        cases = [
            ("opencode_rollout_diagnostics", "opencode-rollout-diagnostics.v1.json", "infra_rollout_diagnostics_redaction_failed"),
            ("opencode_runtime_egress_policy", "opencode-runtime-egress-policy.v1.json", "infra_runtime_egress_policy_failed"),
            ("opencode_runtime_health_policy", "opencode-runtime-health-policy.v1.json", "infra_runtime_health_policy_failed"),
        ]
        for packet_type, filename, signal in cases:
            with self.subTest(signal=signal):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    for row in cross_repo_infra_evidence.catalog()["required_packets"]:
                        status = "fail" if row["packet_type"] == packet_type else "pass"
                        write_json(root / filename_for(row["packet_type"]), {"status": status, "errors": ["failed"] if status == "fail" else []})
                    packet = cross_repo_infra_evidence.scan(root, "opencode-server", "issue-450-fixture")
                self.assertIn(signal, {row["signal"] for row in packet["degradation_events"]})

    def test_gitops_degradation_uses_infra_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet_path = root / "infra.json"
            packet = cross_repo_infra_evidence.scan(root, "opencode-server", "issue-450-fixture")
            write_json(packet_path, packet)
            scan = gitops_degradation.scan("issue-450-fixture", root=root, infra_evidence=packet_path)
        self.assertEqual("degraded", scan["status"])
        self.assertIn("infra_bundle_provenance_missing", {row["signal"] for row in scan["events"]})

    def test_sanitization_rejects_raw_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "runtime/opencode/opencode-bundle-provenance.v1.json", {"status": "pass", "note": "token=abc"})
            packet = cross_repo_infra_evidence.scan(root, "opencode-server", "issue-450-fixture")
        bundle = next(row for row in packet["evidence_packets"] if row["packet_type"] == "opencode_bundle_provenance")
        self.assertEqual("fail", bundle["status"])
        self.assertFalse(bundle["sanitized"])
        self.assertTrue(cross_repo_infra_evidence.validate_packet(packet, "unsafe-fixture"))


def filename_for(packet_type: str) -> str:
    return {
        "infra_validation_matrix": "runtime/opencode/infra-validation-matrix.v1.json",
        "opencode_bundle_provenance": "runtime/opencode/opencode-bundle-provenance.v1.json",
        "opencode_public_route_policy": "runtime/opencode/opencode-public-route-policy.v1.json",
        "opencode_rollout_diagnostics": "runtime/opencode/opencode-rollout-diagnostics.v1.json",
        "opencode_runtime_egress_policy": "runtime/opencode/opencode-runtime-egress-policy.v1.json",
        "opencode_runtime_health_policy": "runtime/opencode/opencode-runtime-health-policy.v1.json",
    }[packet_type]


if __name__ == "__main__":
    unittest.main()
