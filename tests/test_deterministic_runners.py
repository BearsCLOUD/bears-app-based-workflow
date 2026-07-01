import json
import unittest

from scripts import cache_sync_runner, evidence_compactor, git_workflow_runner, validation_job_runner
from scripts.local_json_schema import validate_json_schema


class DeterministicRunnerTests(unittest.TestCase):
    def test_runner_validate_all_accepts_good_and_rejects_bad_fixtures(self) -> None:
        self.assertEqual(git_workflow_runner.validate_all(), [])
        self.assertEqual(validation_job_runner.validate_all(), [])
        self.assertEqual(cache_sync_runner.validate_all(), [])
        self.assertEqual(evidence_compactor.validate_all(), [])

    def test_packet_schemas_accept_good_fixtures(self) -> None:
        pairs = [
            (git_workflow_runner.GOOD, git_workflow_runner.SCHEMA),
            (validation_job_runner.GOOD, validation_job_runner.SCHEMA),
            (cache_sync_runner.GOOD, cache_sync_runner.SCHEMA),
            (evidence_compactor.GOOD, evidence_compactor.SCHEMA),
        ]
        for packet_path, schema_path in pairs:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(validate_json_schema(packet, schema_path, packet_path.name), [])

    def test_evidence_compactor_emits_bounded_packet(self) -> None:
        packet = json.loads(evidence_compactor.GOOD.read_text(encoding="utf-8"))
        result = evidence_compactor.run_packet(packet)
        self.assertEqual(result["schema"], "bears-deterministic-runner-result.v1")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["evidence"][0]["status"], "pass")
        self.assertNotIn("secret", json.dumps(result).lower())

    def test_validation_runner_rejects_unallowlisted_validator(self) -> None:
        packet = json.loads(validation_job_runner.GOOD.read_text(encoding="utf-8"))
        packet["allowed_validators"] = ["python3 -m unittest discover"]
        errors = validation_job_runner.validate_packet(packet)
        self.assertIn("validator not allowlisted", "\n".join(errors))

    def test_git_runner_rejects_unowned_staged_file_logic(self) -> None:
        self.assertTrue(git_workflow_runner.in_allowed("scripts/git_workflow_runner.py", ["scripts"]))
        self.assertFalse(git_workflow_runner.in_allowed("docs/reference/file.md", ["scripts"]))


if __name__ == "__main__":
    unittest.main()
