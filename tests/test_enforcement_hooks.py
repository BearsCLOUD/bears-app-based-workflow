"""Tests for the plugin enforcement hooks (claude/hooks.json + claude/hooks/enforce.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_JSON = os.path.join(ROOT, "claude", "hooks.json")
HOOK_SCRIPT = os.path.join(ROOT, "claude", "hooks", "enforce.py")
GENESIS = "sha256:" + "0" * 64


def load_module():
    spec = importlib.util.spec_from_file_location("enforce_hook", HOOK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enforce = load_module()


def run_hook(mode, payload):
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT, mode],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    return result


class HooksManifestTests(unittest.TestCase):
    def test_manifest_wires_all_three_events(self):
        with open(HOOKS_JSON, encoding="utf-8") as handle:
            data = json.load(handle)
        hooks = data["hooks"]
        self.assertEqual({"PreToolUse", "Stop", "SubagentStop"}, set(hooks))
        for event, entries in hooks.items():
            self.assertTrue(entries, event)
            for entry in entries:
                for hook in entry["hooks"]:
                    self.assertEqual("command", hook["type"])
                    self.assertIn("${CLAUDE_PLUGIN_ROOT}", hook["command"])
                    self.assertIn("claude/hooks/enforce.py", hook["command"])
                    self.assertIsInstance(hook["timeout"], int)
        self.assertEqual(
            "mcp__.*app-workflow-maintainer__.*", hooks["PreToolUse"][0]["matcher"]
        )
        # Stop does not support a matcher.
        self.assertNotIn("matcher", hooks["Stop"][0])

    def test_matcher_covers_plain_and_plugin_scoped_tool_names(self):
        import re

        matcher = re.compile("mcp__.*app-workflow-maintainer__.*")
        for name in (
            "mcp__app-workflow-maintainer__phase_record",
            "mcp__plugin_bears-app-based-workflow_app-workflow-maintainer__graph_apply",
        ):
            self.assertTrue(matcher.fullmatch(name), name)
        for name in (
            "mcp__app-workflow__workflow_state",
            "Bash",
        ):
            self.assertFalse(matcher.fullmatch(name), name)


class CasHookTests(unittest.TestCase):
    def valid_input(self, **overrides):
        payload = {
            "project_ref": "PRJ-1",
            "request_id": "REQ-1",
            "expected_revision": 3,
            "expected_logical_digest": GENESIS,
        }
        payload.update(overrides)
        return payload

    def decision(self, tool_name, tool_input):
        result = run_hook(
            "cas",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": tool_name,
                "tool_input": tool_input,
            },
        )
        self.assertEqual(0, result.returncode, result.stderr)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)["hookSpecificOutput"]

    def test_valid_cas_is_not_blocked(self):
        self.assertIsNone(
            self.decision(
                "mcp__app-workflow-maintainer__phase_record", self.valid_input()
            )
        )

    def test_missing_request_id_is_denied(self):
        payload = self.valid_input()
        del payload["request_id"]
        out = self.decision("mcp__app-workflow-maintainer__phase_record", payload)
        self.assertEqual("deny", out["permissionDecision"])
        self.assertIn("request_id", out["permissionDecisionReason"])

    def test_plugin_scoped_tool_name_is_guarded(self):
        payload = self.valid_input()
        del payload["request_id"]
        out = self.decision(
            "mcp__plugin_bears-app-based-workflow_app-workflow-maintainer__graph_apply",
            payload,
        )
        self.assertEqual("deny", out["permissionDecision"])

    def test_reader_tools_are_ignored(self):
        self.assertIsNone(
            self.decision("mcp__app-workflow__workflow_state", {"wave_id": "W"})
        )

    def test_bad_cas_shapes(self):
        cases = [
            ({"request_id": ""}, "request_id"),
            ({"request_id": 7}, "request_id"),
            ({"expected_revision": -1}, "expected_revision"),
            ({"expected_revision": True}, "expected_revision"),
            ({"expected_revision": "3"}, "expected_revision"),
            ({"expected_logical_digest": "sha256:zz"}, "expected_logical_digest"),
            ({"expected_logical_digest": GENESIS.upper()}, "expected_logical_digest"),
        ]
        for override, needle in cases:
            with self.subTest(override=override):
                problems = enforce.cas_violations(self.valid_input(**override))
                self.assertTrue(any(needle in item for item in problems), problems)

    def test_non_object_input_is_denied(self):
        self.assertTrue(enforce.cas_violations(["not", "an", "object"]))

    def test_malformed_stdin_fails_open(self):
        result = subprocess.run(
            [sys.executable, HOOK_SCRIPT, "cas"],
            input="{not json",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())


class PhaseHookTests(unittest.TestCase):
    def build_db(self, path, phase_status="completed", with_record=True,
                 wave_status="completed", current_phase="app-research",
                 audited=False, open_correction=False,
                 recorded_phase="app-constitution", record_active=1):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE waves (wave_id TEXT PRIMARY KEY, mode TEXT, owner_session_ref TEXT,
                status TEXT, current_phase TEXT, created_revision INTEGER, updated_revision INTEGER);
            CREATE TABLE phases (wave_id TEXT, phase TEXT, ordinal INTEGER, status TEXT,
                process_record_ref TEXT, reopened_by TEXT, revision INTEGER);
            CREATE TABLE process_records (record_ref TEXT PRIMARY KEY, wave_id TEXT, phase TEXT,
                active INTEGER);
            CREATE TABLE tasks (task_ref TEXT PRIMARY KEY, wave_id TEXT);
            CREATE TABLE corrections (correction_ref TEXT PRIMARY KEY, task_ref TEXT, status TEXT);
            CREATE TABLE audit_attestations (audit_ref TEXT PRIMARY KEY, wave_id TEXT, status TEXT);
            """
        )
        connection.execute(
            "INSERT INTO waves VALUES('W1','DIRECT','OWNER',?,?,1,1)",
            (wave_status, current_phase),
        )
        for ordinal, phase in enumerate(enforce.PHASES):
            if phase == recorded_phase:
                connection.execute(
                    "INSERT INTO phases VALUES('W1',?,?,?,?,NULL,1)",
                    (phase, ordinal, phase_status, "REC-1" if with_record else None),
                )
            else:
                connection.execute(
                    "INSERT INTO phases VALUES('W1',?,?,'pending',NULL,NULL,1)",
                    (phase, ordinal),
                )
        if with_record:
            connection.execute(
                "INSERT INTO process_records VALUES('REC-1','W1',?,?)",
                (recorded_phase, record_active),
            )
        if audited:
            connection.execute(
                "INSERT INTO audit_attestations VALUES('AUD-1','W1','active')"
            )
        if open_correction:
            connection.execute("INSERT INTO tasks VALUES('T-1','W1')")
            connection.execute("INSERT INTO corrections VALUES('C-1','T-1','open')")
        connection.commit()
        connection.close()

    def decision(self, cwd, stop_hook_active=False):
        result = run_hook(
            "phase",
            {
                "hook_event_name": "Stop",
                "cwd": cwd,
                "stop_hook_active": stop_hook_active,
            },
        )
        self.assertEqual(0, result.returncode, result.stderr)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)

    def test_no_database_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self.decision(tmp))

    def test_healthy_mid_workflow_state_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(os.path.join(tmp, ".bears", "app-workflow.sqlite3"))
            self.assertIsNone(self.decision(tmp))

    def test_completed_phase_without_active_record_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"), with_record=False
            )
            out = self.decision(tmp)
            self.assertEqual("block", out["decision"])
            self.assertIn("app-constitution", out["reason"])

    def test_plan_replace_completing_app_plan_without_record_is_allowed(self):
        # plan_replace marks app-plan completed without a process record.
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"),
                recorded_phase="app-plan",
                with_record=False,
                phase_status="completed",
                current_phase="app-dev",
                wave_status="plan-ready",
            )
            self.assertIsNone(self.decision(tmp))

    def test_analysis_record_readying_app_analyze_without_record_is_allowed(self):
        # analysis_record marks app-analyze ready without a process record.
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"),
                recorded_phase="app-analyze",
                with_record=False,
                phase_status="ready",
                current_phase="app-analyze",
                wave_status="ready",
            )
            self.assertIsNone(self.decision(tmp))

    def test_dangling_process_record_pointer_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"), record_active=0
            )
            out = self.decision(tmp)
            self.assertEqual("block", out["decision"])
            self.assertIn("REC-1", out["reason"])

    def test_unknown_current_phase_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"),
                current_phase="app-nonsense",
            )
            out = self.decision(tmp)
            self.assertEqual("block", out["decision"])
            self.assertIn("app-nonsense", out["reason"])

    def test_open_corrections_at_audit_time_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"),
                wave_status="ready",
                current_phase="app-analyze",
                open_correction=True,
            )
            out = self.decision(tmp)
            self.assertEqual("block", out["decision"])
            self.assertIn("open correction", out["reason"])

    def test_open_corrections_before_audit_do_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"),
                open_correction=True,
            )
            self.assertIsNone(self.decision(tmp))

    def test_active_attestation_with_open_corrections_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"),
                audited=True,
                open_correction=True,
            )
            out = self.decision(tmp)
            self.assertEqual("block", out["decision"])

    def test_stop_hook_active_short_circuits(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_db(
                os.path.join(tmp, ".bears", "app-workflow.sqlite3"), with_record=False
            )
            self.assertIsNone(self.decision(tmp, stop_hook_active=True))

    def test_corrupt_database_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".bears", "app-workflow.sqlite3")
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not a database")
            self.assertIsNone(self.decision(tmp))


if __name__ == "__main__":
    unittest.main()
