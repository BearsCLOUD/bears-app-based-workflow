from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("app_workflow", ROOT / "scripts/app_workflow.py")
assert SPEC and SPEC.loader
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)


class WorkflowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="bears-workflow-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.old_codex_home = os.environ.get("CODEX_HOME")
        self.old_state_dir = os.environ.get("BEARS_APP_WORKFLOW_STATE_DIR")
        os.environ["CODEX_HOME"] = str(self.base / "codex")
        os.environ.pop("BEARS_APP_WORKFLOW_STATE_DIR", None)
        self.addCleanup(self.restore_environment)
        self.counter = 0

    def restore_environment(self) -> None:
        if self.old_codex_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = self.old_codex_home
        if self.old_state_dir is None:
            os.environ.pop("BEARS_APP_WORKFLOW_STATE_DIR", None)
        else:
            os.environ["BEARS_APP_WORKFLOW_STATE_DIR"] = self.old_state_dir

    def make_project(self, name: str = "project") -> Path:
        root = (self.base / name).resolve()
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "evidence.md").write_text("source evidence\n", encoding="utf-8")
        (root / "code.py").write_text("VALUE = 1\n", encoding="utf-8")
        return root

    def register(self, root: Path) -> dict[str, object]:
        self.counter += 1
        return WORKFLOW.register_backend(
            {
                "project_root": str(root),
                "request_id": f"REQ-REGISTER-{self.counter}",
                "expected_revision": 0,
                "expected_logical_digest": WORKFLOW.GENESIS_DIGEST,
            }
        )

    def call(self, project_ref: str, operation: str, function, **values):
        self.counter += 1
        status = WORKFLOW.project_status_backend(project_ref)
        return function(
            {
                "project_ref": project_ref,
                "request_id": f"REQ-{operation}-{self.counter}",
                "expected_revision": status["revision"],
                "expected_logical_digest": status["logical_digest"],
                **values,
            }
        )

    def initialize(self, project_ref: str, mode: str = "DIRECT", wave_id: str = "WAVE-1", owner: str = "OWNER-1"):
        return self.call(
            project_ref,
            "WAVE",
            WORKFLOW.wave_initialize_backend,
            wave_id=wave_id,
            mode=mode,
            owner_session_ref=owner,
        )

    def phase(self, project_ref: str, phase: str, owner: str = "OWNER-1", wave_id: str = "WAVE-1", outcome: str = "completed"):
        status = WORKFLOW.project_status_backend(project_ref)
        return self.call(
            project_ref,
            "PHASE",
            WORKFLOW.phase_record_backend,
            wave_id=wave_id,
            owner_session_ref=owner,
            phase=phase,
            record_ref=f"PROCESS-{phase}-{self.counter}",
            outcome=outcome,
            input_digest=status["logical_digest"],
            output_digest=status["logical_digest"],
            source_refs=["evidence.md"],
            artifact_refs=["evidence.md"],
        )

    def clean_wave(self, root: Path, project_ref: str, mode: str = "DIRECT", owner: str = "OWNER-1") -> None:
        self.initialize(project_ref, mode=mode, owner=owner)
        self.call(
            project_ref,
            "GRAPH",
            WORKFLOW.graph_apply_backend,
            wave_id="WAVE-1",
            owner_session_ref=owner,
            operations=[
                {
                    "action": "upsert",
                    "object_type": "entity",
                    "entity_ref": "ENTITY-1",
                    "kind": "feature",
                    "name": "Feature",
                    "properties": {},
                    "source_refs": ["evidence.md"],
                }
            ],
        )
        self.call(
            project_ref,
            "PLAN",
            WORKFLOW.plan_replace_backend,
            wave_id="WAVE-1",
            owner_session_ref=owner,
            tasks=[
                {
                    "task_ref": "TASK-1",
                    "title": "Implement feature",
                    "sequence": 1,
                    "depends_on": [],
                    "source_refs": ["evidence.md"],
                }
            ],
        )
        self.call(
            project_ref,
            "CHANGE",
            WORKFLOW.task_record_change_backend,
            wave_id="WAVE-1",
            owner_session_ref=owner,
            task_ref="TASK-1",
            worker_ref="WORKER-1",
            change_refs=["code.py"],
        )
        change_digest = WORKFLOW.workflow_state_backend(
            {"project_ref": project_ref, "wave_id": "WAVE-1"}
        )["tasks"][0]["change_digest"]
        self.call(
            project_ref,
            "REVIEW",
            WORKFLOW.review_record_backend,
            wave_id="WAVE-1",
            owner_session_ref=owner,
            review_ref="REVIEW-1",
            task_ref="TASK-1",
            reviewer_ref="REVIEWER-1",
            verdict="approved",
            change_digest=change_digest,
            source_refs=["evidence.md"],
            findings=[],
        )
        for phase in WORKFLOW.PHASES:
            self.phase(project_ref, phase, owner=owner)
        self.call(
            project_ref,
            "ANALYSIS",
            WORKFLOW.analysis_record_backend,
            wave_id="WAVE-1",
            owner_session_ref=owner,
            analysis_ref="ANALYSIS-1",
            source_refs=["evidence.md"],
            findings=[],
        )


class StateDirEnvTests(WorkflowTestCase):
    def test_state_dir_override_ignores_codex_home(self) -> None:
        state_dir = self.base / "state-dir"
        state_dir.mkdir()
        self.addCleanup(os.environ.pop, "BEARS_APP_WORKFLOW_STATE_DIR", None)
        os.environ["BEARS_APP_WORKFLOW_STATE_DIR"] = str(state_dir)
        os.environ["CODEX_HOME"] = str(self.base / "ignored-codex-home")
        self.assertEqual(WORKFLOW.registry_path(), state_dir.expanduser() / WORKFLOW.REGISTRY_RELATIVE.name)

    def test_registry_path_uses_codex_home_when_state_dir_is_unset(self) -> None:
        self.addCleanup(os.environ.pop, "BEARS_APP_WORKFLOW_STATE_DIR", None)
        os.environ.pop("BEARS_APP_WORKFLOW_STATE_DIR", None)
        self.assertEqual(WORKFLOW.registry_path(), WORKFLOW.codex_home() / WORKFLOW.REGISTRY_RELATIVE)


class McpLifecycleTests(WorkflowTestCase):
    def rpc(self, mode: str, messages: list[dict[str, object]]) -> list[dict[str, object]]:
        completed = subprocess.run(
            ["python3", str(ROOT / "scripts/app_workflow.py"), "serve", "--mode", mode],
            input="".join(json.dumps(message) + "\n" for message in messages),
            text=True,
            capture_output=True,
            check=True,
            env={**os.environ, "CODEX_HOME": str(self.base / "rpc-home")},
        )
        return [json.loads(line) for line in completed.stdout.splitlines()]

    def test_lifecycle_and_exact_tool_split(self) -> None:
        base = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        reader = self.rpc("reader", base)
        maintainer = self.rpc("maintainer", base)
        self.assertEqual(reader[0]["result"]["serverInfo"]["version"], "0.6.0")
        self.assertEqual(len(reader[1]["result"]["tools"]), 12)
        self.assertEqual(len(maintainer[1]["result"]["tools"]), 13)
        self.assertNotIn("graph_apply", {tool["name"] for tool in reader[1]["result"]["tools"]})
        self.assertNotIn("graph_read", {tool["name"] for tool in maintainer[1]["result"]["tools"]})

    def test_tool_results_have_text_and_structured_content(self) -> None:
        response = self.rpc(
            "reader",
            [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "project_list", "arguments": {}}}],
        )[0]["result"]
        self.assertEqual(json.loads(response["content"][0]["text"]), response["structuredContent"])

    def test_request_limit_is_enforced(self) -> None:
        completed = subprocess.run(
            ["python3", str(ROOT / "scripts/app_workflow.py"), "serve", "--mode", "reader"],
            input=b"{" + b"x" * WORKFLOW.MAX_REQUEST_BYTES + b"}\n",
            capture_output=True,
            check=True,
        )
        self.assertIn(b"REQUEST_LIMIT_EXCEEDED", completed.stdout)


class RegistrationTests(WorkflowTestCase):
    def test_multiple_projects_persist_with_stable_refs(self) -> None:
        first = self.register(self.make_project("first"))
        second = self.register(self.make_project("second"))
        self.assertNotEqual(first["project_ref"], second["project_ref"])
        listed = WORKFLOW.project_list_backend()["projects"]
        self.assertEqual({item["project_ref"] for item in listed}, {first["project_ref"], second["project_ref"]})
        self.assertTrue(all(item["available"] for item in listed))

    def test_registration_rejects_relative_nonroot_and_symlink(self) -> None:
        root = self.make_project()
        child = root / "child"
        child.mkdir()
        link = self.base / "link"
        link.symlink_to(root, target_is_directory=True)
        for invalid, code in (("relative", "PROJECT_ROOT_NOT_ABSOLUTE"), (str(child), "PROJECT_ROOT_NOT_GIT_ROOT"), (str(link), "PROJECT_ROOT_SYMLINK_FORBIDDEN")):
            with self.subTest(invalid=invalid), self.assertRaises(WORKFLOW.WorkflowError) as caught:
                WORKFLOW.register_backend({"project_root": invalid, "request_id": "REQ-X", "expected_revision": 0, "expected_logical_digest": WORKFLOW.GENESIS_DIGEST})
            self.assertEqual(caught.exception.code, code)

    def test_database_has_safe_pragmas_git_rules_and_no_path(self) -> None:
        root = self.make_project()
        result = self.register(root)
        status = WORKFLOW.project_status_backend(result["project_ref"])
        self.assertEqual(status["settings"], {"foreign_keys": 1, "journal_mode": "delete", "synchronous": 2, "busy_timeout_ms": 5000})
        self.assertIn(".bears/app-workflow.sqlite3 binary", (root / ".gitattributes").read_text())
        self.assertIn(".bears/app-workflow.sqlite3-wal", (root / ".gitignore").read_text())
        database = root / WORKFLOW.DATABASE_RELATIVE
        self.assertFalse(Path(str(database) + "-wal").exists())
        with sqlite3.connect(database) as connection:
            for table in WORKFLOW.list_project_tables(connection):
                for row in connection.execute(f"SELECT * FROM {table}"):
                    self.assertNotIn(str(root), repr(tuple(row)))

    def test_rebind_requires_same_database_identity_and_unregister_keeps_file(self) -> None:
        root = self.make_project("old")
        result = self.register(root)
        project_ref = result["project_ref"]
        new_root = self.base / "new"
        root.rename(new_root)
        rebound = WORKFLOW.rebind_backend({"project_ref": project_ref, "project_root": str(new_root), "request_id": "REQ-REBIND", "expected_revision": result["revision"], "expected_logical_digest": result["logical_digest"]})
        self.assertEqual(rebound["project_ref"], project_ref)
        removed = WORKFLOW.unregister_backend({"project_ref": project_ref, "request_id": "REQ-UNREGISTER", "expected_revision": rebound["revision"], "expected_logical_digest": rebound["logical_digest"]})
        self.assertTrue(removed["unregistered"])
        self.assertTrue((new_root / WORKFLOW.DATABASE_RELATIVE).is_file())
        self.assertEqual(WORKFLOW.unregister_backend({"project_ref": project_ref, "request_id": "REQ-UNREGISTER", "expected_revision": rebound["revision"], "expected_logical_digest": rebound["logical_digest"]}), removed)


class TransactionTests(WorkflowTestCase):
    def test_cas_and_request_id_idempotency(self) -> None:
        result = self.register(self.make_project())
        project_ref = result["project_ref"]
        arguments = {"project_ref": project_ref, "request_id": "REQ-WAVE", "expected_revision": 0, "expected_logical_digest": result["logical_digest"], "wave_id": "WAVE-1", "mode": "DIRECT", "owner_session_ref": "OWNER-1"}
        first = WORKFLOW.wave_initialize_backend(arguments)
        self.assertEqual(WORKFLOW.wave_initialize_backend(arguments), first)
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            WORKFLOW.wave_initialize_backend({**arguments, "request_id": "REQ-STALE", "wave_id": "WAVE-2"})
        self.assertEqual(caught.exception.code, "CAS_MISMATCH")

    def test_failed_graph_batch_rolls_back_every_operation(self) -> None:
        result = self.register(self.make_project())
        project_ref = result["project_ref"]
        self.initialize(project_ref)
        before = WORKFLOW.project_status_backend(project_ref)
        with self.assertRaises(WORKFLOW.WorkflowError):
            self.call(project_ref, "BAD-GRAPH", WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", operations=[{"action": "upsert", "object_type": "entity", "entity_ref": "ENTITY-1", "kind": "feature", "name": "One", "properties": {}, "source_refs": ["evidence.md"]}, {"action": "upsert", "object_type": "relation", "relation_ref": "REL-1", "from_entity_ref": "ENTITY-1", "to_entity_ref": "ENTITY-1", "relation_type": "unknown", "source_refs": ["evidence.md"]}])
        after = WORKFLOW.project_status_backend(project_ref)
        self.assertEqual((before["revision"], before["logical_digest"]), (after["revision"], after["logical_digest"]))
        self.assertEqual(WORKFLOW.graph_read_backend({"project_ref": project_ref})["items"], [])

    def test_owner_session_is_enforced_for_direct_and_delegated(self) -> None:
        for mode in ("DIRECT", "DELEGATED"):
            root = self.make_project(mode.lower())
            project_ref = self.register(root)["project_ref"]
            self.initialize(project_ref, mode=mode)
            with self.assertRaises(WORKFLOW.WorkflowError) as caught:
                self.call(project_ref, f"OWNER-{mode}", WORKFLOW.plan_replace_backend, wave_id="WAVE-1", owner_session_ref="OTHER", tasks=[])
            self.assertEqual(caught.exception.code, "OWNER_SESSION_MISMATCH")


class GraphTests(WorkflowTestCase):
    def populated_graph(self):
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.initialize(project_ref)
        operations = []
        for index in range(1, 4):
            operations.append({"action": "upsert", "object_type": "entity", "entity_ref": f"ENTITY-{index}", "kind": "feature", "name": f"Feature {index}", "properties": {}, "source_refs": ["evidence.md"]})
        operations.extend([
            {"action": "upsert", "object_type": "observation", "observation_ref": "OBS-1", "entity_ref": "ENTITY-1", "content": "Observed behavior", "source_refs": ["evidence.md"]},
            {"action": "upsert", "object_type": "relation", "relation_ref": "REL-1", "from_entity_ref": "ENTITY-1", "to_entity_ref": "ENTITY-2", "relation_type": "depends_on", "source_refs": ["evidence.md"]},
            {"action": "upsert", "object_type": "relation", "relation_ref": "REL-2", "from_entity_ref": "ENTITY-2", "to_entity_ref": "ENTITY-3", "relation_type": "depends_on", "source_refs": ["evidence.md"]},
        ])
        self.call(project_ref, "GRAPH", WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", operations=operations)
        return root, project_ref

    def test_crud_search_open_and_retirement(self) -> None:
        _, project_ref = self.populated_graph()
        self.assertGreaterEqual(WORKFLOW.graph_search_backend({"project_ref": project_ref, "query": "feature"})["total"], 3)
        opened = WORKFLOW.graph_open_backend({"project_ref": project_ref, "refs": ["ENTITY-1", "OBS-1"]})
        self.assertEqual(len(opened["items"]), 2)
        self.call(project_ref, "RETIRE", WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", operations=[{"action": "retire", "object_type": "observation", "observation_ref": "OBS-1", "replacement_ref": "OBS-2", "source_refs": ["evidence.md"]}])
        retired = WORKFLOW.graph_read_backend({"project_ref": project_ref, "object_type": "observation", "status": "retired"})["items"]
        self.assertEqual(retired[0]["replacement_ref"], "OBS-2")

    def test_traversal_impact_trace_and_cursor_revision_binding(self) -> None:
        _, project_ref = self.populated_graph()
        dependencies = WORKFLOW.traverse_graph({"project_ref": project_ref, "entity_ref": "ENTITY-1", "max_depth": 4}, reverse=False)
        impact = WORKFLOW.traverse_graph({"project_ref": project_ref, "entity_ref": "ENTITY-3", "max_depth": 4}, reverse=True)
        trace = WORKFLOW.graph_trace_backend({"project_ref": project_ref, "from_entity_ref": "ENTITY-1", "to_entity_ref": "ENTITY-3", "max_depth": 4})
        self.assertEqual(dependencies["entity_refs"], ["ENTITY-1", "ENTITY-2", "ENTITY-3"])
        self.assertEqual(impact["entity_refs"], ["ENTITY-1", "ENTITY-2", "ENTITY-3"])
        self.assertTrue(trace["found"])
        page = WORKFLOW.graph_read_backend({"project_ref": project_ref, "limit": 1})
        self.call(project_ref, "MUTATE", WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", operations=[{"action": "upsert", "object_type": "entity", "entity_ref": "ENTITY-4", "kind": "feature", "name": "Four", "properties": {}, "source_refs": ["evidence.md"]}])
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            WORKFLOW.graph_read_backend({"project_ref": project_ref, "limit": 1, "cursor": page["next_cursor"]})
        self.assertEqual(caught.exception.code, "CURSOR_STALE")

    def test_dependency_cycle_is_reported(self) -> None:
        _, project_ref = self.populated_graph()
        self.call(project_ref, "CYCLE", WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", operations=[{"action": "upsert", "object_type": "relation", "relation_ref": "REL-3", "from_entity_ref": "ENTITY-3", "to_entity_ref": "ENTITY-1", "relation_type": "depends_on", "source_refs": ["evidence.md"]}])
        diagnostics = WORKFLOW.graph_diagnostics_backend({"project_ref": project_ref})
        self.assertIn("GRAPH_CYCLE", {finding["code"] for finding in diagnostics["findings"]})


class WorkflowSemanticsTests(WorkflowTestCase):
    def test_seven_phases_and_skip_supersede_current_record(self) -> None:
        project_ref = self.register(self.make_project())["project_ref"]
        self.initialize(project_ref)
        for phase in WORKFLOW.PHASES:
            self.phase(project_ref, phase, outcome="skipped-current")
        first = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        self.phase(project_ref, WORKFLOW.PHASES[0], outcome="completed")
        second = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        current = [record for record in second["process_records"] if record["phase"] == WORKFLOW.PHASES[0] and record["active"]]
        history = [record for record in second["process_records"] if record["phase"] == WORKFLOW.PHASES[0]]
        self.assertEqual(len(first["phases"]), 7)
        self.assertEqual((len(current), len(history)), (1, 2))
        self.assertIsNotNone(current[0]["supersedes_ref"])

    def test_plan_order_and_dependency_cycle_are_enforced(self) -> None:
        project_ref = self.register(self.make_project())["project_ref"]
        self.initialize(project_ref)
        bad_tasks = [
            {"task_ref": "TASK-1", "title": "One", "sequence": 1, "depends_on": ["TASK-2"], "source_refs": ["evidence.md"]},
            {"task_ref": "TASK-2", "title": "Two", "sequence": 2, "depends_on": ["TASK-1"], "source_refs": ["evidence.md"]},
        ]
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            self.call(project_ref, "PLAN-CYCLE", WORKFLOW.plan_replace_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", tasks=bad_tasks)
        self.assertEqual(caught.exception.code, "TASK_DEPENDENCY_CYCLE")

    def test_review_correction_and_latest_change_digest(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.initialize(project_ref)
        self.call(project_ref, "PLAN", WORKFLOW.plan_replace_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", tasks=[{"task_ref": "TASK-1", "title": "One", "sequence": 1, "depends_on": [], "source_refs": ["evidence.md"]}])
        self.call(project_ref, "CHANGE-1", WORKFLOW.task_record_change_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", task_ref="TASK-1", worker_ref="WORKER-1", change_refs=["code.py"])
        first_digest = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})["tasks"][0]["change_digest"]
        self.call(project_ref, "REVIEW-1", WORKFLOW.review_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", review_ref="REVIEW-1", task_ref="TASK-1", reviewer_ref="REVIEWER-1", verdict="changes_requested", change_digest=first_digest, source_refs=["evidence.md"], findings=[{"finding_ref": "FINDING-1", "kind": "behavior", "summary": "Fix behavior", "source_refs": ["evidence.md"]}])
        self.call(project_ref, "CORRECTION", WORKFLOW.correction_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", correction_ref="CORRECTION-1", finding_ref="FINDING-1", task_ref="TASK-1", status="resolved", evidence_refs=["code.py"], source_refs=["evidence.md"])
        (root / "code.py").write_text("VALUE = 2\n", encoding="utf-8")
        self.call(project_ref, "CHANGE-2", WORKFLOW.task_record_change_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", task_ref="TASK-1", worker_ref="WORKER-1", change_refs=["code.py"])
        second_digest = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})["tasks"][0]["change_digest"]
        with self.assertRaises(WORKFLOW.WorkflowError):
            self.call(project_ref, "STALE-APPROVAL", WORKFLOW.review_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", review_ref="REVIEW-STALE", task_ref="TASK-1", reviewer_ref="REVIEWER-1", verdict="approved", change_digest=first_digest, source_refs=["evidence.md"], findings=[])
        self.call(project_ref, "APPROVAL", WORKFLOW.review_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", review_ref="REVIEW-2", task_ref="TASK-1", reviewer_ref="REVIEWER-1", verdict="approved", change_digest=second_digest, source_refs=["evidence.md"], findings=[])
        self.assertEqual(WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})["tasks"][0]["status"], "done")

    def test_analysis_findings_reopen_required_phase(self) -> None:
        project_ref = self.register(self.make_project())["project_ref"]
        self.initialize(project_ref)
        for phase in WORKFLOW.PHASES:
            self.phase(project_ref, phase)
        self.call(project_ref, "ANALYSIS", WORKFLOW.analysis_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", analysis_ref="ANALYSIS-1", source_refs=["evidence.md"], findings=[{"finding_ref": "SEMANTIC-1", "kind": "spec-gap", "summary": "Missing decision", "route": "app-specify", "source_refs": ["evidence.md"]}])
        state = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        self.assertEqual(state["wave"]["current_phase"], "app-specify")
        self.assertEqual({phase["status"] for phase in state["phases"][2:]}, {"pending"})

    def test_exact_audit_gate_and_mutation_staleness(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.clean_wave(root, project_ref)
        validation = WORKFLOW.workflow_validate_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        self.assertTrue(validation["ok"], validation["findings"])
        audited = self.call(project_ref, "AUDIT", WORKFLOW.workflow_mark_audited_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", audit_ref="AUDIT-1")
        self.assertTrue(audited["audited"])
        self.assertEqual(WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})["workflow_status"], "audited")
        self.call(project_ref, "MUTATION", WORKFLOW.graph_apply_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", operations=[{"action": "upsert", "object_type": "entity", "entity_ref": "ENTITY-2", "kind": "feature", "name": "Other", "properties": {}, "source_refs": ["evidence.md"]}])
        self.assertNotEqual(WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})["workflow_status"], "audited")

    def test_file_drift_blocks_validation_and_audit(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.clean_wave(root, project_ref)
        (root / "code.py").write_text("VALUE = 99\n", encoding="utf-8")
        result = WORKFLOW.workflow_validate_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        self.assertIn("SNAPSHOT_FILE_DRIFT", {finding["code"] for finding in result["findings"]})
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            self.call(project_ref, "BAD-AUDIT", WORKFLOW.workflow_mark_audited_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", audit_ref="AUDIT-BAD")
        self.assertEqual(caught.exception.code, "AUDIT_VALIDATION_FAILED")

    def test_cli_validator_uses_read_only_shared_core(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.clean_wave(root, project_ref)
        database = root / WORKFLOW.DATABASE_RELATIVE
        before = WORKFLOW.digest_file(database)
        completed = subprocess.run(
            ["python3", str(ROOT / "skills/app-analyze/scripts/validate_workflow.py"), "--project-ref", project_ref, "--wave-id", "WAVE-1"],
            text=True,
            capture_output=True,
            check=True,
            env=os.environ.copy(),
        )
        result = json.loads(completed.stdout)
        self.assertEqual(set(result), {"ok", "snapshot_digest", "findings"})
        self.assertTrue(result["ok"])
        self.assertEqual(WORKFLOW.digest_file(database), before)


class MigrationTests(WorkflowTestCase):
    def write_sources(self, root: Path, schema: str = "app-functional-map.v5") -> tuple[str, str]:
        graph = {"schema": schema, "nodes": [{"id": "ENTITY-1", "kind": "feature", "label": "One", "source_refs": ["evidence.md"]}], "edges": []}
        state = {"schema": "workflow-state.v1", "wave_id": "WAVE-OLD", "mode": "DIRECT", "owner_session_ref": "OWNER-1", "phases": [], "ledger": {"tasks": []}}
        (root / "map.json").write_text(json.dumps(graph), encoding="utf-8")
        (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return WORKFLOW.digest_file(root / "map.json"), WORKFLOW.digest_file(root / "state.json")

    def test_v5_migration_checks_sha_parity_and_requires_reaudit(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        map_digest, state_digest = self.write_sources(root)
        result = self.call(project_ref, "MIGRATE", WORKFLOW.migrate_json_backend, map_ref="map.json", state_ref="state.json", map_sha256=map_digest, state_sha256=state_digest)
        self.assertTrue(result["migrated"])
        self.assertTrue(all(result["parity"].values()), result["parity"])
        self.assertTrue(result["requires_reaudit"])
        self.assertIsNone(WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-OLD"})["audit"])

    def test_migration_digest_failure_rolls_back_and_v4_becomes_evidence(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        map_digest, state_digest = self.write_sources(root)
        before = WORKFLOW.project_status_backend(project_ref)
        with self.assertRaises(WORKFLOW.WorkflowError):
            self.call(project_ref, "BAD-MIGRATE", WORKFLOW.migrate_json_backend, map_ref="map.json", state_ref="state.json", map_sha256=WORKFLOW.GENESIS_DIGEST, state_sha256=state_digest)
        self.assertEqual(WORKFLOW.project_status_backend(project_ref)["revision"], before["revision"])
        self.write_sources(root, "app-functional-map.v4")
        result = self.call(project_ref, "V4", WORKFLOW.migrate_json_backend, map_ref="map.json", state_ref="state.json", map_sha256=WORKFLOW.digest_file(root / "map.json"), state_sha256=WORKFLOW.digest_file(root / "state.json"), new_wave_id="WAVE-V4", mode="DIRECT", owner_session_ref="OWNER-1")
        self.assertFalse(result["migrated"])
        self.assertEqual(result["legacy_schema"], "v4")
        self.assertTrue((root / "map.json").is_file())


if __name__ == "__main__":
    unittest.main()
