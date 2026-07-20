from __future__ import annotations

import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
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
        self.assertEqual(reader[0]["result"]["serverInfo"]["version"], WORKFLOW.VERSION)
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

    def test_rebind_rejects_unregistered_project_ref(self) -> None:
        root = self.make_project()
        WORKFLOW.initialize_project_database(root / WORKFLOW.DATABASE_RELATIVE, "PROJECT-GHOST")
        connection = WORKFLOW.connect_sqlite(root / WORKFLOW.DATABASE_RELATIVE, writable=False)
        digest = WORKFLOW.logical_digest(connection)
        connection.close()
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            WORKFLOW.rebind_backend({"project_ref": "PROJECT-GHOST", "project_root": str(root), "request_id": "REQ-REBIND", "expected_revision": 0, "expected_logical_digest": digest})
        self.assertEqual(caught.exception.code, "PROJECT_NOT_REGISTERED")

    def test_rebind_rejects_stale_clone_while_canonical_root_is_reachable(self) -> None:
        # Tier-A #4: a stale/forked clone of the same project, parked at a different path,
        # must not be able to roll the registry's canonical binding backward while the real
        # (more advanced) canonical root is still reachable on disk.
        old_root = self.make_project("old")
        registered = self.register(old_root)
        project_ref = registered["project_ref"]
        stale_clone = self.base / "stale-clone"
        shutil.copytree(old_root, stale_clone)
        # Advance the real, still-reachable canonical database past the clone's snapshot.
        advanced = self.initialize(project_ref)
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            WORKFLOW.rebind_backend({
                "project_ref": project_ref,
                "project_root": str(stale_clone),
                "request_id": "REQ-REBIND-ATTACK",
                "expected_revision": registered["revision"],
                "expected_logical_digest": registered["logical_digest"],
            })
        self.assertEqual(caught.exception.code, "REBIND_CANONICAL_DRIFT")
        # The registry binding must still point at the real canonical root, untouched.
        still_canonical = WORKFLOW.project_status_backend(project_ref)
        self.assertEqual(still_canonical["revision"], advanced["revision"])


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

    def test_audit_status_does_not_survive_on_disk_file_drift(self) -> None:
        # Tier-A #2: editing an evidenced file on disk with no MCP mutation at all must
        # not keep project_status/workflow_state reporting the stale attestation as audited,
        # even though revision and logical_digest are untouched.
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.clean_wave(root, project_ref)
        self.call(project_ref, "AUDIT", WORKFLOW.workflow_mark_audited_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", audit_ref="AUDIT-1")
        before = WORKFLOW.project_status_backend(project_ref)
        self.assertTrue(before["audited"])
        self.assertEqual(WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})["workflow_status"], "audited")
        (root / "code.py").write_text("VALUE = 2\n", encoding="utf-8")
        after = WORKFLOW.project_status_backend(project_ref)
        self.assertEqual(after["revision"], before["revision"])
        self.assertFalse(after["audited"])
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


class PlanReplaceReorderTests(WorkflowTestCase):
    def replace(self, project_ref: str, tasks: list[dict[str, object]]):
        return self.call(project_ref, "PLAN", WORKFLOW.plan_replace_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1", tasks=tasks)

    def active_sequences(self, project_ref: str) -> dict[str, int]:
        state = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        return {task["task_ref"]: task["sequence"] for task in state["tasks"] if task["record_status"] == "active"}

    def test_plan_replace_reorders_and_reuses_sequences(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.initialize(project_ref)

        def task(ref: str, seq: int) -> dict[str, object]:
            return {"task_ref": ref, "title": ref, "sequence": seq, "depends_on": [], "source_refs": ["code.py"]}

        self.replace(project_ref, [task("TASK-A", 1), task("TASK-B", 2)])
        # Swapping the sequences of two active tasks used to trip the full UNIQUE(wave_id, sequence).
        self.replace(project_ref, [task("TASK-B", 1), task("TASK-A", 2)])
        self.assertEqual(self.active_sequences(project_ref), {"TASK-B": 1, "TASK-A": 2})
        # Dropping a task and reusing its sequence for a new one used to collide with the retired row.
        self.replace(project_ref, [task("TASK-C", 1), task("TASK-B", 2)])
        self.assertEqual(self.active_sequences(project_ref), {"TASK-C": 1, "TASK-B": 2})


class CrossWaveGuardTests(WorkflowTestCase):
    def test_task_change_rejects_foreign_wave_task(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.initialize(project_ref, wave_id="WAVE-1", owner="OWNER-1")
        self.initialize(project_ref, wave_id="WAVE-2", owner="OWNER-2")
        self.call(project_ref, "PLAN", WORKFLOW.plan_replace_backend, wave_id="WAVE-2", owner_session_ref="OWNER-2",
                  tasks=[{"task_ref": "TASK-X", "title": "X", "sequence": 1, "depends_on": [], "source_refs": ["code.py"]}])
        # TASK-X lives in WAVE-2; recording a change while claiming WAVE-1 must not reach it.
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            self.call(project_ref, "CHANGE", WORKFLOW.task_record_change_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1",
                      task_ref="TASK-X", worker_ref="WORKER-1", change_refs=["code.py"])
        self.assertEqual(caught.exception.code, "TASK_NOT_FOUND")

    def test_correction_record_rejects_reused_foreign_correction_ref(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.initialize(project_ref, wave_id="WAVE-1", owner="OWNER-1")
        self.initialize(project_ref, wave_id="WAVE-2", owner="OWNER-2")
        for wave, owner, suffix in (("WAVE-1", "OWNER-1", "1"), ("WAVE-2", "OWNER-2", "2")):
            self.call(project_ref, f"PLAN-{suffix}", WORKFLOW.plan_replace_backend, wave_id=wave, owner_session_ref=owner,
                      tasks=[{"task_ref": f"TASK-{suffix}", "title": "T", "sequence": 1, "depends_on": [], "source_refs": ["evidence.md"]}])
            self.call(project_ref, f"CHANGE-{suffix}", WORKFLOW.task_record_change_backend, wave_id=wave, owner_session_ref=owner,
                      task_ref=f"TASK-{suffix}", worker_ref=f"WORKER-{suffix}", change_refs=["code.py"])
            digest = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": wave})["tasks"][0]["change_digest"]
            self.call(project_ref, f"REVIEW-{suffix}", WORKFLOW.review_record_backend, wave_id=wave, owner_session_ref=owner,
                      review_ref=f"REVIEW-{suffix}", task_ref=f"TASK-{suffix}", reviewer_ref=f"REVIEWER-{suffix}", verdict="changes_requested",
                      change_digest=digest, source_refs=["evidence.md"],
                      findings=[{"finding_ref": f"FINDING-{suffix}", "kind": "behavior", "summary": "Fix", "source_refs": ["evidence.md"]}])
        # WAVE-2's owner opens a correction; its ref must stay bound to WAVE-2's finding/task.
        self.call(project_ref, "CORR-2", WORKFLOW.correction_record_backend, wave_id="WAVE-2", owner_session_ref="OWNER-2",
                  correction_ref="CORR-SHARED", finding_ref="FINDING-2", task_ref="TASK-2", status="open", source_refs=["evidence.md"])
        # WAVE-1's owner reuses that correction_ref with their own wave-legal refs; ON CONFLICT must not
        # let them flip a foreign wave's correction. The binding is immutable -> rejected.
        with self.assertRaises(WORKFLOW.WorkflowError) as caught:
            self.call(project_ref, "CORR-1", WORKFLOW.correction_record_backend, wave_id="WAVE-1", owner_session_ref="OWNER-1",
                      correction_ref="CORR-SHARED", finding_ref="FINDING-1", task_ref="TASK-1", status="resolved",
                      evidence_refs=["code.py"], source_refs=["evidence.md"])
        self.assertEqual(caught.exception.code, "CORRECTION_BINDING_INVALID")


V1_TASKS_DDL = """
CREATE TABLE tasks (
    task_ref TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL REFERENCES waves(wave_id),
    title TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    status TEXT NOT NULL,
    record_status TEXT NOT NULL CHECK (record_status IN ('active', 'retired')),
    replacement_ref TEXT,
    owner_session_ref TEXT NOT NULL,
    worker_ref TEXT,
    change_digest TEXT,
    change_refs_json TEXT NOT NULL,
    created_revision INTEGER NOT NULL,
    updated_revision INTEGER NOT NULL,
    UNIQUE (wave_id, sequence)
)
"""


class SchemaMigrationTests(WorkflowTestCase):
    def task(self, ref: str, seq: int, depends_on=None) -> dict[str, object]:
        return {
            "task_ref": ref,
            "title": ref,
            "sequence": seq,
            "depends_on": depends_on or [],
            "source_refs": ["code.py"],
        }

    def replace(self, project_ref: str, tasks: list[dict[str, object]]):
        return self.call(
            project_ref,
            "PLAN",
            WORKFLOW.plan_replace_backend,
            wave_id="WAVE-1",
            owner_session_ref="OWNER-1",
            tasks=tasks,
        )

    def active_sequences(self, project_ref: str) -> dict[str, int]:
        state = WORKFLOW.workflow_state_backend({"project_ref": project_ref, "wave_id": "WAVE-1"})
        return {t["task_ref"]: t["sequence"] for t in state["tasks"] if t["record_status"] == "active"}

    def tasks_table_sql(self, database: Path) -> str:
        with contextlib.closing(sqlite3.connect(database)) as raw:
            row = raw.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
        return row[0]

    def downgrade_to_v1(self, database: Path) -> None:
        """Rebuild the on-disk tasks table back into the pre-migration v1 shape.

        Mirrors the migration's own build-tmp / drop / rename-into-place pattern so
        that the stable table name ``tasks`` keeps child FK references intact.
        """
        with contextlib.closing(sqlite3.connect(database, isolation_level=None)) as raw:
            raw.execute("PRAGMA foreign_keys=OFF")
            raw.execute("BEGIN IMMEDIATE")
            raw.execute("DROP INDEX IF EXISTS tasks_active_sequence")
            raw.execute(V1_TASKS_DDL.replace("CREATE TABLE tasks", "CREATE TABLE tasks_tmp"))
            raw.execute(
                "INSERT INTO tasks_tmp "
                "(task_ref,wave_id,title,sequence,status,record_status,replacement_ref,"
                "owner_session_ref,worker_ref,change_digest,change_refs_json,created_revision,updated_revision) "
                "SELECT task_ref,wave_id,title,sequence,status,record_status,replacement_ref,"
                "owner_session_ref,worker_ref,change_digest,change_refs_json,created_revision,updated_revision "
                "FROM tasks"
            )
            raw.execute("DROP TABLE tasks")
            raw.execute("ALTER TABLE tasks_tmp RENAME TO tasks")
            raw.execute("CREATE INDEX tasks_wave_status ON tasks(wave_id, record_status, sequence)")
            raw.execute("UPDATE metadata SET value='app-workflow-db.v1' WHERE key='schema_version'")
            raw.execute("PRAGMA user_version=1")
            if raw.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise AssertionError("downgrade fixture left dangling foreign keys")
            raw.execute("COMMIT")
            raw.execute("PRAGMA foreign_keys=ON")

    def user_version(self, database: Path) -> int:
        with contextlib.closing(sqlite3.connect(database)) as raw:
            return int(raw.execute("PRAGMA user_version").fetchone()[0])

    def schema_version(self, database: Path) -> str:
        with contextlib.closing(sqlite3.connect(database)) as raw:
            row = raw.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        return row[0]

    def test_old_full_unique_rejects_sequence_reuse(self) -> None:
        # Pins the pre-migration defect: the full UNIQUE(wave_id, sequence) counts
        # retired rows, so a freed sequence cannot be reused by a new active task.
        database = self.base / "legacy.sqlite3"
        with contextlib.closing(sqlite3.connect(database, isolation_level=None)) as raw:
            raw.execute("CREATE TABLE waves (wave_id TEXT PRIMARY KEY)")
            raw.executescript(V1_TASKS_DDL)
            raw.execute("INSERT INTO waves(wave_id) VALUES('WAVE-1')")
            raw.execute(
                "INSERT INTO tasks VALUES('T-A','WAVE-1','A',1,'pending','active',NULL,'O',NULL,NULL,'[]',1,1)"
            )
            raw.execute("UPDATE tasks SET record_status='retired' WHERE task_ref='T-A'")
            with self.assertRaises(sqlite3.IntegrityError):
                raw.execute(
                    "INSERT INTO tasks VALUES('T-B','WAVE-1','B',1,'pending','active',NULL,'O',NULL,NULL,'[]',2,2)"
                )

    def test_writable_open_migrates_v1_and_enables_reuse(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        self.initialize(project_ref)
        # Seed a dependency so child-table referential integrity is exercised.
        self.replace(project_ref, [self.task("TASK-A", 1), self.task("TASK-B", 2, depends_on=["TASK-A"])])
        database = root / WORKFLOW.DATABASE_RELATIVE

        # Downgrade the registered DB back to genuine v1 on disk.
        self.downgrade_to_v1(database)
        self.assertEqual(self.schema_version(database), "app-workflow-db.v1")
        self.assertEqual(self.user_version(database), 1)
        self.assertIn("UNIQUE (wave_id, sequence)", self.tasks_table_sql(database))

        # Read-only access must NOT migrate or write.
        status = WORKFLOW.project_status_backend(project_ref)
        self.assertEqual(self.schema_version(database), "app-workflow-db.v1")
        self.assertEqual(self.user_version(database), 1)

        # First mutation after downgrade: opening writable migrates in place and must
        # NOT raise CAS_MISMATCH even though expected_digest came from the v1 read above.
        self.replace(project_ref, [self.task("TASK-B", 1), self.task("TASK-A", 2, depends_on=["TASK-B"])])

        # DB is now v2.
        self.assertEqual(self.schema_version(database), WORKFLOW.SCHEMA_VERSION)
        self.assertEqual(self.schema_version(database), "app-workflow-db.v2")
        self.assertEqual(self.user_version(database), 2)
        self.assertNotIn("UNIQUE (wave_id, sequence)", self.tasks_table_sql(database))
        with contextlib.closing(sqlite3.connect(database)) as raw:
            self.assertIsNotNone(
                raw.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='index' AND name='tasks_active_sequence'"
                ).fetchone()
            )
            # Child rows survived with intact task_ref references.
            self.assertEqual(raw.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0], 1)
            fk = raw.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(fk, [])
        self.assertEqual(self.active_sequences(project_ref), {"TASK-B": 1, "TASK-A": 2})

        # Retire a task and reuse its freed sequence -- impossible under the old full UNIQUE.
        self.replace(project_ref, [self.task("TASK-C", 1), self.task("TASK-B", 2)])
        self.assertEqual(self.active_sequences(project_ref), {"TASK-C": 1, "TASK-B": 2})

    def test_migration_is_idempotent_noop_on_v2(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        database = root / WORKFLOW.DATABASE_RELATIVE
        # Freshly created DB is already v2.
        self.assertEqual(self.schema_version(database), WORKFLOW.SCHEMA_VERSION)
        with contextlib.closing(WORKFLOW.connect_sqlite(database, writable=True)) as conn:
            WORKFLOW.migrate_project_database(conn)  # no-op
            WORKFLOW.migrate_project_database(conn)  # still no-op
            self.assertEqual(int(conn.execute("PRAGMA foreign_keys").fetchone()[0]), 1)
        self.assertEqual(self.schema_version(database), "app-workflow-db.v2")
        self.assertEqual(self.user_version(database), 2)

    def test_unknown_schema_version_rejected(self) -> None:
        root = self.make_project()
        project_ref = self.register(root)["project_ref"]
        database = root / WORKFLOW.DATABASE_RELATIVE
        with contextlib.closing(sqlite3.connect(database, isolation_level=None)) as raw:
            raw.execute("UPDATE metadata SET value='app-workflow-db.v99' WHERE key='schema_version'")
        with contextlib.closing(WORKFLOW.connect_sqlite(database, writable=True)) as conn:
            with self.assertRaises(WORKFLOW.WorkflowError) as caught:
                WORKFLOW.migrate_project_database(conn)
        self.assertEqual(caught.exception.code, "PROJECT_SCHEMA_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
