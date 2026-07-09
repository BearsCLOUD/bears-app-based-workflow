import json
import tempfile
import unittest
from pathlib import Path

from scripts import agent_action_ledger as ledger


def write_runtime(path: Path, *, heartbeat: bool = True, validation: bool = True, forbidden: bool = False) -> None:
    if heartbeat:
        (path / "heartbeat.json").write_text(json.dumps({"status": "alive", "role": "worker"}), encoding="utf-8")
    (path / "assignment.json").write_text(json.dumps({"role": "worker", "task_id": "t1"}), encoding="utf-8")
    (path / "evidence.json").write_text(json.dumps({"refs": ["docs/evidence.md"]}), encoding="utf-8")
    if validation:
        (path / "validation.json").write_text(json.dumps({"commands": [{"command": "git diff --check", "exit_code": 0}]}), encoding="utf-8")
    (path / "closeout.json").write_text(json.dumps({"blockers": []}), encoding="utf-8")
    if forbidden:
        (path / "actions.json").write_text(json.dumps({"items": [{"action": "secret_read"}]}), encoding="utf-8")


class AgentActionLedgerTests(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual(ledger.validate_catalog(), [])

    def test_missing_heartbeat_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime(root, heartbeat=False)
            _, errors = ledger.collect_runtime(root)
            self.assertIn("missing required packet: heartbeat", errors)

    def test_closeout_without_validation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime(root, validation=False)
            _, errors = ledger.collect_runtime(root)
            self.assertIn("missing required packet: validation", errors)
            self.assertIn("closeout requires validation packet", errors)

    def test_forbidden_action_recorded_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime(root, forbidden=True)
            _, errors = ledger.collect_runtime(root)
            self.assertIn("forbidden action recorded: secret_read", errors)

    def test_markdown_contains_assignment_evidence_validation_and_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime(root)
            packets, errors = ledger.collect_runtime(root)
            self.assertEqual(errors, [])
            rendered = ledger.render_markdown(packets)
            for heading in ("## Assignment", "## Evidence", "## Validation", "## Blockers"):
                self.assertIn(heading, rendered)


if __name__ == "__main__":
    unittest.main()
