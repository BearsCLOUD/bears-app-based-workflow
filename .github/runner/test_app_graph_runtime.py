"""Exercise deterministic Graph Workflow v3 compiler, journal, audit, and cursor contracts."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from app_graph_engine import GraphError, execute_tool  # noqa: E402


class AppGraphRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        manifest = json.loads((ROOT / "docs/app-graph-source-manifest.v1.json").read_text())
        fixed = [
            "docs/app-graph-source-manifest.v1.json",
            manifest["sources"]["workflow"],
            manifest["sources"]["functional_map"],
            manifest["sources"]["task_ledger"],
            *manifest["tracked_paths"],
        ]
        events = (ROOT / manifest["sources"]["event_root"]).rglob("*.json")
        for relative in sorted(set(fixed) | {path.relative_to(ROOT).as_posix() for path in events}):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        self.compile = self.call("graph_compile", maintainer=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def call(self, name: str, *, maintainer: bool = False, **arguments: object) -> dict[str, object]:
        return execute_tool(name, {"app_root": str(self.root), **arguments}, maintainer=maintainer)

    def test_unchanged_compile_is_byte_identical_no_op(self) -> None:
        paths = [
            "docs/app-traceability-index.v3.json",
            "docs/app-process-index.v2.json",
            "docs/app-index-build.v1.json",
            "docs/app-context-index-result.v1.json",
        ]
        before = {path: (self.root / path).read_bytes() for path in paths}
        result = self.call(
            "graph_compile",
            maintainer=True,
            expected_build_ref=self.compile["build_ref"],
        )
        self.assertTrue(result["no_op"])
        self.assertEqual(before, {path: (self.root / path).read_bytes() for path in paths})

    def test_source_drift_rebuilds_and_stales_cursor(self) -> None:
        page = self.call("graph_trace", limit=1)
        cursor = page["next_cursor"]
        self.assertIsNotNone(cursor)
        readme = self.root / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\n")
        rebuilt = self.call(
            "graph_compile",
            maintainer=True,
            expected_build_ref=self.compile["build_ref"],
        )
        self.assertNotEqual(rebuilt["build_ref"], self.compile["build_ref"])
        with self.assertRaisesRegex(GraphError, "stale graph snapshot") as caught:
            self.call("graph_trace", limit=1, cursor=cursor)
        self.assertEqual(caught.exception.code, "CURSOR_STALE")

    def test_event_append_is_idempotent_and_conflict_safe(self) -> None:
        event = {
            "schema": "app-process-event.v1",
            "run_ref": "RUN-GRAPH-WORKFLOW-V2",
            "event_ref": "EVT-IDEMPOTENCY-TEST",
            "event_kind": "review",
            "stage": "app-dev",
            "status": "in_progress",
            "actor": "DIRECT-primary",
            "causal_refs": ["EVT-TASK-RESULT-V3-001"],
            "trace_refs": ["SPEC-GRAPH-WORKFLOW-V3"],
            "artifact_refs": [],
            "origin": "native",
            "automation_status": "not_run",
        }
        recorded = self.call("process_record_event", maintainer=True, event=event)
        current = self.call("process_record_event", maintainer=True, event=event)
        self.assertFalse(recorded["no_op"])
        self.assertTrue(current["no_op"])
        with self.assertRaises(GraphError) as caught:
            self.call("process_record_event", maintainer=True, event={**event, "status": "failed"})
        self.assertEqual(caught.exception.code, "EVENT_CONFLICT")

    def test_causal_cycle_is_rejected_before_publication(self) -> None:
        event = self.root / "docs/app-process-events/v1/RUN-GRAPH-WORKFLOW-V2/EVT-CONSTITUTION-001.json"
        value = json.loads(event.read_text())
        value["causal_refs"] = ["EVT-RESEARCH-001"]
        event.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(GraphError) as caught:
            self.call("graph_compile", maintainer=True, expected_build_ref=self.compile["build_ref"])
        self.assertEqual(caught.exception.code, "GRAPH_CYCLE")

    def test_illegal_transition_routes_to_graph_remediation(self) -> None:
        event = self.root / "docs/app-process-events/v1/RUN-GRAPH-WORKFLOW-V2/EVT-REMEDIATION-PLAN-V3-001.json"
        value = json.loads(event.read_text())
        value["stage"] = "app-specify"
        event.write_text(json.dumps(value), encoding="utf-8")
        rebuilt = self.call("graph_compile", maintainer=True, expected_build_ref=self.compile["build_ref"])
        result = self.call("process_audit", expected_build_ref=rebuilt["build_ref"])
        self.assertEqual(result["route"], "needs-graph")
        self.assertIn("illegal-transition", {finding["kind"] for finding in result["findings"]})

    def test_disabled_maintainer_and_path_escape_fail_closed(self) -> None:
        manifest = self.root / "docs/app-graph-source-manifest.v1.json"
        value = json.loads(manifest.read_text())
        value["maintainer_enabled"] = False
        manifest.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(GraphError) as caught:
            self.call("graph_compile", maintainer=True, expected_build_ref=self.compile["build_ref"])
        self.assertEqual(caught.exception.code, "MAINTAINER_DISABLED")
        value["maintainer_enabled"] = True
        manifest.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(GraphError) as caught:
            self.call(
                "process_record_event",
                maintainer=True,
                event={
                    "schema": "app-process-event.v1",
                    "run_ref": "RUN-GRAPH-WORKFLOW-V2",
                    "event_ref": "../escape",
                    "event_kind": "review",
                    "stage": "app-dev",
                    "status": "in_progress",
                    "actor": "DIRECT-primary",
                    "causal_refs": [],
                    "trace_refs": [],
                    "artifact_refs": [],
                    "origin": "native",
                    "automation_status": "not_run",
                },
            )
        self.assertEqual(caught.exception.code, "PATH_ESCAPE")


if __name__ == "__main__":
    unittest.main()
