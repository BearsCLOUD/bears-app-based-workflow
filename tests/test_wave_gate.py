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

import hashlib
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

    def write_bound_document(self, name: str, binding_ref: str, block: bytes) -> str:
        """Write one exact anchor block and return its normalized content digest."""
        self.assertTrue(block.endswith((b"\n", b"\r")))
        content = (
            b"# Bound document\n"
            + f"<!-- bind:{binding_ref} -->\n".encode("ascii")
            + block
            + f"<!-- /bind:{binding_ref} -->\n".encode("ascii")
        )
        (self.root / name).write_bytes(content)
        return "sha256:" + hashlib.sha256(block.replace(b"\r\n", b"\n")).hexdigest()

    def apply_doc_binding_chain(self) -> None:
        """Bind every active task and the graph-to-spec-to-wave-doc document chain."""
        self.mutate(
            WORKFLOW.binding_apply_backend,
            wave_id="WAVE-1",
            owner_session_ref="OWNER",
            operations=[
                {
                    "action": "upsert",
                    "binding_ref": f"BINDING-GRAPH-TASK-{task['task_ref']}",
                    "binding_kind": "graph_to_task",
                    "source_refs": ["ENTITY-1"],
                    "target_ref": task["task_ref"],
                }
                for task in self.state()["tasks"]
            ],
        )
        spec_digest = self.write_bound_document(
            "spec.md", "BINDING-GRAPH-SPEC-1", b"Feature specification\r\n"
        )
        self.mutate(
            WORKFLOW.binding_apply_backend,
            wave_id="WAVE-1",
            owner_session_ref="OWNER",
            operations=[{
                "action": "upsert",
                "binding_ref": "BINDING-GRAPH-SPEC-1",
                "binding_kind": "graph_to_spec",
                "source_refs": ["ENTITY-1"],
                "target_path": "spec.md",
                "target_anchor": "BINDING-GRAPH-SPEC-1",
                "content_digest": spec_digest,
            }],
        )
        wave_doc_digest = self.write_bound_document(
            "wave-doc.md", "BINDING-SPEC-WAVE-DOC-1", b"Wave documentation\n"
        )
        self.mutate(
            WORKFLOW.binding_apply_backend,
            wave_id="WAVE-1",
            owner_session_ref="OWNER",
            operations=[{
                "action": "upsert",
                "binding_ref": "BINDING-SPEC-WAVE-DOC-1",
                "binding_kind": "spec_to_wave_doc",
                "source_refs": ["BINDING-GRAPH-SPEC-1"],
                "target_path": "wave-doc.md",
                "target_anchor": "BINDING-SPEC-WAVE-DOC-1",
                "content_digest": wave_doc_digest,
            }],
        )
        constitution_digest = self.write_bound_document(
            "constitution.md", "BINDING-WAVE-DOC-CONSTITUTION-1", b"Constitution rule\n"
        )
        self.mutate(
            WORKFLOW.binding_apply_backend,
            wave_id="WAVE-1",
            owner_session_ref="OWNER",
            operations=[{
                "action": "upsert",
                "binding_ref": "BINDING-WAVE-DOC-CONSTITUTION-1",
                "binding_kind": "wave_doc_to_constitution",
                "source_refs": ["BINDING-SPEC-WAVE-DOC-1"],
                "target_path": "constitution.md",
                "target_anchor": "BINDING-WAVE-DOC-CONSTITUTION-1",
                "content_digest": constitution_digest,
            }],
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
        self.apply_doc_binding_chain()
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

    def test_a_task_without_a_graph_to_task_binding_is_rejected(self) -> None:
        # The doc chain begins at every active task, so an otherwise valid task plan cannot
        # omit its graph binding.
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
        validation = self.validate()
        self.assertFalse(validation["ok"])
        self.assertIn("DOC_CHAIN_GAP", {finding["code"] for finding in validation["findings"]})

    def test_on_disk_drift_after_audit_breaks_the_audit(self) -> None:
        # The audit binds the exact anchored document bytes, normalized only for CRLF.
        # Editing one bound block must report drift for that exact binding.
        self.drive_clean_wave()
        audited = self.mutate(WORKFLOW.workflow_mark_audited_backend, wave_id="WAVE-1",
                              owner_session_ref="OWNER", audit_ref="AUDIT-1")
        self.assertTrue(audited["audited"])
        self.assertEqual(self.state()["workflow_status"], "audited")
        spec = self.root / "spec.md"
        spec.write_bytes(spec.read_bytes().replace(b"Feature specification\r\n", b"Changed specification\r\n"))
        validation = self.validate()
        self.assertFalse(validation["ok"])
        self.assertIn(
            {"code": "DOC_BINDING_DRIFT", "location": "doc_bindings.BINDING-GRAPH-SPEC-1",
             "message": "doc_binding_drift"},
            validation["findings"],
        )


if __name__ == "__main__":
    unittest.main()
