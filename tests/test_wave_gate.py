"""The single wave gate.

One check, expressed in the plugin's own terms: drive a complete seven-phase wave
through the real maintainer backends against a throwaway git project, then let the
plugin judge itself. The oracle is `workflow_validate` / `validation_result` - the
same core the `validate` CLI and `workflow_mark_audited` use - so this gate passes
exactly when the plugin considers its own recorded workflow internally consistent and
auditable, and fails the moment that stops being true.

This is deliberately not a broad unit suite. It exercises the whole mutation surface
(register, wave, graph, plan, task, review, analysis, phase records, audit) as one
narrative and asserts only the plugin's own verdict about the result. Run it with
unittest, never pytest.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("app_workflow", ROOT / "scripts/app_workflow.py")
assert SPEC and SPEC.loader
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)


class WaveGate(unittest.TestCase):
    """Drive a real wave, then ask the plugin whether it holds together."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="bears-wave-gate-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.saved = {key: os.environ.get(key) for key in ("CODEX_HOME", "BEARS_APP_WORKFLOW_STATE_DIR")}
        os.environ["BEARS_APP_WORKFLOW_STATE_DIR"] = str(self.base / "state")
        os.environ.pop("CODEX_HOME", None)
        self.addCleanup(self._restore_env)
        self.counter = 0

        self.root = (self.base / "project").resolve()
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "evidence.md").write_text("source evidence\n", encoding="utf-8")
        (self.root / "code.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.project_ref = WORKFLOW.register_backend({
            "project_root": str(self.root),
            "request_id": "REQ-REGISTER",
            "expected_revision": 0,
            "expected_logical_digest": WORKFLOW.GENESIS_DIGEST,
        })["project_ref"]

    def _restore_env(self) -> None:
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def mutate(self, function, **values):
        """One CAS-guarded mutation, reading the fresh revision/digest first."""
        self.counter += 1
        status = WORKFLOW.project_status_backend(self.project_ref)
        result = function({
            "project_ref": self.project_ref,
            "request_id": f"REQ-{self.counter}",
            "expected_revision": status["revision"],
            "expected_logical_digest": status["logical_digest"],
            **values,
        })
        self.assertTrue(result.get("ok", True), result)
        return result

    def state(self) -> dict:
        return WORKFLOW.workflow_state_backend({"project_ref": self.project_ref, "wave_id": "WAVE-1"})

    def validate(self) -> dict:
        return WORKFLOW.workflow_validate_backend({"project_ref": self.project_ref, "wave_id": "WAVE-1"})

    def record_phase(self, phase: str) -> None:
        status = WORKFLOW.project_status_backend(self.project_ref)
        self.mutate(
            WORKFLOW.phase_record_backend,
            wave_id="WAVE-1",
            owner_session_ref="OWNER",
            phase=phase,
            record_ref=f"PROCESS-{phase}",
            outcome="completed",
            input_digest=status["logical_digest"],
            output_digest=status["logical_digest"],
            source_refs=["evidence.md"],
            artifact_refs=["evidence.md"],
        )

    def drive_clean_wave(self) -> None:
        """A complete, internally consistent wave: graph, plan, one done task, analysis, phases."""
        self.mutate(WORKFLOW.wave_initialize_backend, wave_id="WAVE-1", mode="DIRECT", owner_session_ref="OWNER")
        self.mutate(
            WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER",
            operations=[{"action": "upsert", "object_type": "entity", "entity_ref": "ENTITY-1",
                         "kind": "feature", "name": "Feature", "properties": {}, "source_refs": ["evidence.md"]}],
        )
        self.mutate(
            WORKFLOW.plan_replace_backend, wave_id="WAVE-1", owner_session_ref="OWNER",
            tasks=[{"task_ref": "TASK-1", "title": "Implement feature", "sequence": 1,
                    "depends_on": [], "source_refs": ["evidence.md"]}],
        )
        self.mutate(WORKFLOW.task_record_change_backend, wave_id="WAVE-1", owner_session_ref="OWNER",
                    task_ref="TASK-1", worker_ref="WORKER-1", change_refs=["code.py"])
        change_digest = self.state()["tasks"][0]["change_digest"]
        self.mutate(WORKFLOW.review_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER",
                    review_ref="REVIEW-1", task_ref="TASK-1", reviewer_ref="REVIEWER-1",
                    verdict="approved", change_digest=change_digest, source_refs=["evidence.md"], findings=[])
        for phase in WORKFLOW.PHASES:
            self.record_phase(phase)
        self.mutate(WORKFLOW.analysis_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER",
                    analysis_ref="ANALYSIS-1", source_refs=["evidence.md"], findings=[])

    def test_a_complete_wave_validates_and_audits(self) -> None:
        # The gate: a fully recorded wave is judged consistent by the plugin's own core,
        # can be attested, and the workflow then reports itself audited.
        self.drive_clean_wave()
        validation = self.validate()
        self.assertTrue(validation["ok"], validation["findings"])
        audited = self.mutate(WORKFLOW.workflow_mark_audited_backend, wave_id="WAVE-1",
                              owner_session_ref="OWNER", audit_ref="AUDIT-1")
        self.assertTrue(audited["audited"])
        self.assertEqual(self.state()["workflow_status"], "audited")

    def test_an_incomplete_wave_is_rejected(self) -> None:
        # A wave initialized but not carried through must not validate: the plugin's logic,
        # not a hand-listed assertion, is what says "not ready".
        self.mutate(WORKFLOW.wave_initialize_backend, wave_id="WAVE-1", mode="DIRECT", owner_session_ref="OWNER")
        validation = self.validate()
        self.assertFalse(validation["ok"])
        self.assertTrue(validation["findings"])

    def test_on_disk_drift_after_audit_breaks_the_audit(self) -> None:
        # The audit binds a verdict to an exact file snapshot. Editing a provenanced source
        # on disk must make the plugin stop reporting the wave as audited.
        self.drive_clean_wave()
        self.mutate(WORKFLOW.workflow_mark_audited_backend, wave_id="WAVE-1",
                    owner_session_ref="OWNER", audit_ref="AUDIT-1")
        self.assertEqual(self.state()["workflow_status"], "audited")
        (self.root / "code.py").write_text("VALUE = 999\n", encoding="utf-8")
        self.assertFalse(self.validate()["ok"])


if __name__ == "__main__":
    unittest.main()
