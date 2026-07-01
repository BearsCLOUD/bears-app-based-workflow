import json
import unittest

from scripts import artifact_registry


class ArtifactRegistryTests(unittest.TestCase):
    def test_validate_registry_accepts_good_and_rejects_bad_fixture(self) -> None:
        self.assertEqual(artifact_registry.validate_registry(artifact_registry.GOOD), [])
        self.assertTrue(artifact_registry.validate_registry(artifact_registry.BAD))

    def test_current_registry_validates(self) -> None:
        self.assertEqual(artifact_registry.validate_registry(artifact_registry.REGISTRY), [])

    def test_capability_harness_artifacts_are_registered(self) -> None:
        registry = artifact_registry.load(artifact_registry.REGISTRY)
        errors = artifact_registry.check_paths(
            [
                "assets/catalog/bears-plugin-capability-scenarios.v1.json",
                "docs/reference/capability-harness.md",
                "scripts/capability_harness.py",
                "tests/fixtures/capability/catalogs/l0_l3_stub_matrix.valid.json",
                "tests/test_capability_harness.py",
            ],
            registry,
        )
        self.assertEqual(errors, [])

    def test_check_path_requires_registered_tracked_file(self) -> None:
        registry = artifact_registry.load(artifact_registry.REGISTRY)
        self.assertEqual(artifact_registry.check_paths(["scripts/artifact_registry.py"], registry), [])
        errors = artifact_registry.check_paths(["unregistered/new-file.txt"], registry)
        self.assertIn("missing artifact registry entry", "\n".join(errors))

    def test_runtime_path_is_rejected_when_staged(self) -> None:
        registry = artifact_registry.load(artifact_registry.REGISTRY)
        errors = artifact_registry.check_paths(["runtime/tmp.json"], registry)
        self.assertIn("runtime or temporary file staged", "\n".join(errors))

    def test_default_record_has_required_owner_fields(self) -> None:
        record = artifact_registry.default_record("docs/reference/new.md", "doc", "#382", "bears-machine-first-execution-kernel-engineer")
        self.assertEqual(record["owner_issue"], "#382")
        self.assertEqual(record["source_of_truth_status"], "canonical")
        self.assertTrue(record["git_tracked"])

    def test_report_shape_is_bounded(self) -> None:
        registry = artifact_registry.load(artifact_registry.REGISTRY)
        tracked = [record for record in artifact_registry.records(registry) if record.get("git_tracked") is True]
        self.assertGreaterEqual(len(tracked), 1)
        self.assertNotIn("secret", json.dumps(tracked).lower())


if __name__ == "__main__":
    unittest.main()
