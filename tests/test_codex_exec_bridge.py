from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_exec_bridge", ROOT / "scripts/codex_exec_bridge.py")
assert SPEC and SPEC.loader
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)


class BridgeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="bears-codex-exec-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()

    def make_repository(self, name: str = "target") -> Path:
        root = (self.base / name).resolve()
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "keep.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "drop.txt").write_text("temporary\n", encoding="utf-8")
        (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
        return root

    def make_stub(self, name: str, body: str) -> Path:
        """Write an executable stand-in for the `codex` binary."""
        path = self.base / name
        path.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body), encoding="utf-8")
        path.chmod(0o755)
        return path


class CommandBuildTests(BridgeTestCase):
    def test_command_disables_network_and_uses_stdin_marker(self) -> None:
        command = BRIDGE.build_command(
            binary="/usr/bin/codex",
            target=Path("/srv/project"),
            sandbox="workspace-write",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            network_access=False,
            json_events=False,
            last_message_path=Path("/tmp/last.txt"),
        )
        self.assertEqual(command[:2], ["/usr/bin/codex", "exec"])
        self.assertEqual(command[-1], "-", "the brief must arrive over stdin, never as an interpolated string")
        self.assertIn("--cd", command)
        self.assertEqual(command[command.index("--cd") + 1], "/srv/project")
        self.assertEqual(command[command.index("--sandbox") + 1], "workspace-write")
        self.assertIn("sandbox_workspace_write.network_access=false", command)
        self.assertIn('model_reasoning_effort="high"', command)
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-terra")
        self.assertEqual(command[command.index("--output-last-message") + 1], "/tmp/last.txt")

    def test_network_can_be_enabled_explicitly(self) -> None:
        command = BRIDGE.build_command(
            binary="codex",
            target=Path("/srv/project"),
            sandbox="workspace-write",
            model=None,
            reasoning_effort=None,
            network_access=True,
            json_events=True,
            last_message_path=Path("/tmp/last.txt"),
        )
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        self.assertIn("--json", command)
        self.assertNotIn("--model", command)

    def test_read_only_sandbox_omits_workspace_network_override(self) -> None:
        command = BRIDGE.build_command(
            binary="codex",
            target=Path("/srv/project"),
            sandbox="read-only",
            model=None,
            reasoning_effort=None,
            network_access=False,
            json_events=False,
            last_message_path=Path("/tmp/last.txt"),
        )
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertFalse([item for item in command if item.startswith("sandbox_workspace_write.")])

    def test_brief_metacharacters_are_never_shell_interpolated(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-echo",
            """
            import sys
            sys.stdout.write(sys.stdin.read())
            """,
        )
        hazard = "rm -rf / ; $(touch /tmp/pwned) `id` \"quoted\" 'single'\n"
        result = BRIDGE.run_assignment(brief=hazard, target_dir=root, binary=str(stub))
        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], hazard)
        self.assertEqual(result["changed_file_count"], 0)


class ValidationTests(BridgeTestCase):
    def test_danger_full_access_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=self.base, sandbox="danger-full-access")
        self.assertEqual(caught.exception.code, "SANDBOX_MODE_FORBIDDEN")

    def test_unknown_sandbox_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=self.base, sandbox="wide-open")
        self.assertEqual(caught.exception.code, "SANDBOX_MODE_INVALID")

    def test_empty_brief_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="   \n", target_dir=self.base)
        self.assertEqual(caught.exception.code, "BRIEF_EMPTY")

    def test_oversized_brief_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="x" * (BRIDGE.MAX_BRIEF_BYTES + 1), target_dir=self.base)
        self.assertEqual(caught.exception.code, "BRIEF_TOO_LARGE")

    def test_invalid_timeout_is_refused(self) -> None:
        for value in (0, -1, BRIDGE.MAX_TIMEOUT_SECONDS + 1):
            with self.assertRaises(BRIDGE.CodexExecError) as caught:
                BRIDGE.run_assignment(brief="work", target_dir=self.base, timeout_seconds=value)
            self.assertEqual(caught.exception.code, "TIMEOUT_INVALID")

    def test_invalid_reasoning_effort_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=self.base, reasoning_effort="turbo")
        self.assertEqual(caught.exception.code, "REASONING_EFFORT_INVALID")

    def test_missing_binary_is_refused(self) -> None:
        root = self.make_repository()
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=root, binary=str(self.base / "absent"))
        self.assertEqual(caught.exception.code, "CODEX_BINARY_MISSING")

    def test_non_git_target_is_refused(self) -> None:
        plain = self.base / "plain"
        plain.mkdir()
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=plain)
        self.assertEqual(caught.exception.code, "TARGET_NOT_GIT")

    def test_absent_target_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=self.base / "nowhere")
        self.assertEqual(caught.exception.code, "TARGET_DIR_INVALID")


class EvidenceTests(BridgeTestCase):
    def test_changed_files_are_reported_exactly(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-edit",
            """
            import os
            import pathlib
            import sys

            brief = sys.stdin.read()
            target = pathlib.Path(sys.argv[sys.argv.index("--cd") + 1])
            (target / "keep.py").write_text("VALUE = 2\\n", encoding="utf-8")
            (target / "added.py").write_text("NEW = True\\n", encoding="utf-8")
            os.remove(target / "drop.txt")
            (target / "ignored").mkdir(exist_ok=True)
            (target / "ignored" / "noise.txt").write_text("noise\\n", encoding="utf-8")
            last = sys.argv[sys.argv.index("--output-last-message") + 1]
            pathlib.Path(last).write_text("done: " + brief.strip(), encoding="utf-8")
            sys.stdout.write("agent stdout\\n")
            sys.stderr.write("agent stderr\\n")
            """,
        )
        result = BRIDGE.run_assignment(brief="edit the repo", target_dir=root, binary=str(stub))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(result["exit_status"], 0)
        self.assertFalse(result["timed_out"])
        # Gitignored output is part of the evidence set on purpose: ignore rules
        # are executor-controlled and must never decide what the caller sees.
        self.assertEqual(result["changed_files"]["added"], ["added.py", "ignored/noise.txt"])
        self.assertEqual(result["changed_files"]["modified"], ["keep.py"])
        self.assertEqual(result["changed_files"]["deleted"], ["drop.txt"])
        self.assertEqual(result["changed_file_count"], 4)
        self.assertEqual(result["stdout"], "agent stdout\n")
        self.assertEqual(result["stderr"], "agent stderr\n")
        self.assertEqual(result["last_message"], "done: edit the repo")
        self.assertEqual(result["brief_digest"], BRIDGE.sha256_bytes(b"edit the repo"))
        self.assertTrue(any(line.endswith("added.py") for line in result["status_after"]))

    def test_self_hiding_gitignore_cannot_erase_the_evidence(self) -> None:
        """An executor that ignores its own output is still reported."""
        root = self.make_repository()
        stub = self.make_stub(
            "codex-hide",
            """
            import pathlib
            import sys

            sys.stdin.read()
            target = pathlib.Path(sys.argv[sys.argv.index("--cd") + 1])
            (target / "backdoor.py").write_text("EVIL = True\\n", encoding="utf-8")
            (target / ".gitignore").write_text("*\\n", encoding="utf-8")
            """,
        )
        result = BRIDGE.run_assignment(brief="hide yourself", target_dir=root, binary=str(stub))
        self.assertTrue(result["ok"], result)
        self.assertIn("backdoor.py", result["changed_files"]["added"])
        self.assertIn(".gitignore", result["changed_files"]["modified"])

    def test_file_mode_only_change_is_reported(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-chmod",
            """
            import os
            import pathlib
            import sys

            sys.stdin.read()
            target = pathlib.Path(sys.argv[sys.argv.index("--cd") + 1])
            os.chmod(target / "keep.py", 0o755)
            """,
        )
        result = BRIDGE.run_assignment(brief="chmod", target_dir=root, binary=str(stub))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["changed_files"]["modified"], ["keep.py"])


    def test_pre_existing_dirty_state_is_not_attributed_to_the_run(self) -> None:
        root = self.make_repository()
        (root / "keep.py").write_text("VALUE = 99\n", encoding="utf-8")
        (root / "preexisting.txt").write_text("already here\n", encoding="utf-8")
        stub = self.make_stub(
            "codex-noop",
            """
            import sys
            sys.stdin.read()
            """,
        )
        result = BRIDGE.run_assignment(brief="do nothing", target_dir=root, binary=str(stub))
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed_files"], {"added": [], "modified": [], "deleted": []})
        self.assertTrue(result["status_before"])

    def test_second_modification_of_an_already_dirty_file_is_detected(self) -> None:
        root = self.make_repository()
        (root / "keep.py").write_text("VALUE = 99\n", encoding="utf-8")
        stub = self.make_stub(
            "codex-touch",
            """
            import pathlib
            import sys

            sys.stdin.read()
            target = pathlib.Path(sys.argv[sys.argv.index("--cd") + 1])
            (target / "keep.py").write_text("VALUE = 100\\n", encoding="utf-8")
            """,
        )
        result = BRIDGE.run_assignment(brief="bump", target_dir=root, binary=str(stub))
        self.assertEqual(result["changed_files"]["modified"], ["keep.py"])

    def test_non_zero_exit_is_a_typed_failure_with_evidence(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-fail",
            """
            import sys
            sys.stdin.read()
            sys.stderr.write("boom\\n")
            sys.exit(7)
            """,
        )
        result = BRIDGE.run_assignment(brief="fail", target_dir=root, binary=str(stub))
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "CODEX_EXEC_FAILED")
        self.assertEqual(result["exit_status"], 7)
        self.assertEqual(result["stderr"], "boom\n")

    def test_executor_runs_outside_the_orchestrator_cwd_and_state(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-report",
            """
            import json
            import os
            import sys

            sys.stdin.read()
            sys.stdout.write(json.dumps({
                "cwd": os.getcwd(),
                "codex_home": os.environ.get("CODEX_HOME"),
                "state_dir": os.environ.get("BEARS_APP_WORKFLOW_STATE_DIR"),
            }))
            """,
        )
        os.environ["BEARS_APP_WORKFLOW_STATE_DIR"] = str(self.base / "orchestrator-state")
        self.addCleanup(os.environ.pop, "BEARS_APP_WORKFLOW_STATE_DIR", None)
        home = self.base / "codex-home"
        result = BRIDGE.run_assignment(brief="report", target_dir=root, binary=str(stub), codex_home=home)
        payload = json.loads(result["stdout"])
        self.assertNotEqual(Path(payload["cwd"]).resolve(), root)
        self.assertNotEqual(Path(payload["cwd"]).resolve(), Path.cwd().resolve())
        self.assertEqual(payload["codex_home"], str(home))
        self.assertIsNone(payload["state_dir"], "orchestrator state must not leak into the executor")

    def test_scratch_directory_is_removed_after_the_run(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-cwd",
            """
            import os
            import sys

            sys.stdin.read()
            sys.stdout.write(os.getcwd())
            """,
        )
        result = BRIDGE.run_assignment(brief="report cwd", target_dir=root, binary=str(stub))
        self.assertFalse(Path(result["stdout"]).exists())

    def test_output_is_bounded(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-flood",
            """
            import sys
            sys.stdin.read()
            sys.stdout.write("x" * (600 * 1024))
            """,
        )
        result = BRIDGE.run_assignment(brief="flood", target_dir=root, binary=str(stub))
        self.assertTrue(result["stdout_truncated"])
        self.assertEqual(len(result["stdout"].encode("utf-8")), BRIDGE.MAX_CAPTURE_BYTES)


class NestedRepositoryTests(BridgeTestCase):
    def make_nested(self) -> tuple[Path, Path, str, str]:
        """An outer repository containing a nested repository with two commits."""
        outer = self.make_repository("outer")
        inner = outer / "sub"
        inner.mkdir()
        subprocess.run(["git", "init", "-q", str(inner)], check=True)
        subprocess.run(["git", "-C", str(inner), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(inner), "config", "user.name", "Test"], check=True)
        revisions = []
        for index in (1, 2):
            (inner / "value.txt").write_text(f"{index}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(inner), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(inner), "commit", "-qm", f"c{index}"], check=True)
            revisions.append(
                subprocess.run(
                    ["git", "-C", str(inner), "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            )
        return outer, inner, revisions[0], revisions[1]

    def test_nested_repository_pointer_change_is_reported(self) -> None:
        outer, inner, first, _second = self.make_nested()
        stub = self.make_stub(
            "codex-checkout",
            f"""
            import subprocess
            import sys

            sys.stdin.read()
            subprocess.run(["git", "-C", {str(inner)!r}, "checkout", "-q", {first!r}], check=True)
            """,
        )
        result = BRIDGE.run_assignment(brief="move the pointer", target_dir=outer, binary=str(stub))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["changed_files"]["modified"], ["sub"])

    def test_nested_repository_working_tree_edit_is_reported(self) -> None:
        outer, inner, _first, _second = self.make_nested()
        stub = self.make_stub(
            "codex-dirty",
            f"""
            import pathlib
            import sys

            sys.stdin.read()
            pathlib.Path({str(inner / "value.txt")!r}).write_text("tampered\\n", encoding="utf-8")
            """,
        )
        result = BRIDGE.run_assignment(brief="edit inside the nested repo", target_dir=outer, binary=str(stub))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["changed_files"]["modified"], ["sub"])

    def test_nested_repository_is_not_traversed(self) -> None:
        outer, _inner, _first, _second = self.make_nested()
        snapshot = BRIDGE.tree_snapshot(outer)
        self.assertTrue(snapshot["sub"].startswith("gitlink:"))
        self.assertNotIn("sub/value.txt", snapshot)


class TimeoutTests(BridgeTestCase):
    def test_timeout_returns_typed_failure_and_kills_the_process_tree(self) -> None:
        root = self.make_repository()
        marker = self.base / "grandchild.pid"
        stub = self.make_stub(
            "codex-hang",
            f"""
            import pathlib
            import subprocess
            import sys
            import time

            sys.stdin.read()
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
            pathlib.Path({str(marker)!r}).write_text(str(child.pid), encoding="utf-8")
            time.sleep(120)
            """,
        )
        result = BRIDGE.run_assignment(
            brief="hang", target_dir=root, binary=str(stub), timeout_seconds=2
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "CODEX_EXEC_TIMEOUT")
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["exit_status"], 0)
        self.assertLess(result["duration_seconds"], 30)
        self.assertTrue(marker.is_file(), "the stub should have spawned a grandchild")
        grandchild = int(marker.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and self.process_alive(grandchild):
            time.sleep(0.1)
        self.assertFalse(self.process_alive(grandchild), "the grandchild process was orphaned")

    @staticmethod
    def process_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split(") ", 1)[-1].split()[0] != "Z"


class SubdirectoryScopeTests(BridgeTestCase):
    def test_changes_outside_the_working_root_are_still_reported(self) -> None:
        root = self.make_repository()
        nested = root / "nested"
        nested.mkdir()
        (nested / "inner.txt").write_text("inner\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "nested"], check=True)
        stub = self.make_stub(
            "codex-escape",
            """
            import pathlib
            import sys

            sys.stdin.read()
            working_root = pathlib.Path(sys.argv[sys.argv.index("--cd") + 1])
            (working_root / "inner.txt").write_text("changed\\n", encoding="utf-8")
            (working_root.parent / "keep.py").write_text("VALUE = 42\\n", encoding="utf-8")
            """,
        )
        result = BRIDGE.run_assignment(brief="edit", target_dir=nested, binary=str(stub))
        self.assertEqual(result["target_dir"], str(nested))
        self.assertEqual(result["repository_root"], str(root))
        self.assertEqual(result["changed_files"]["modified"], ["keep.py", "nested/inner.txt"])


class ConfigOverrideTests(BridgeTestCase):
    def test_sandbox_and_network_overrides_are_refused(self) -> None:
        for override in (
            "sandbox_workspace_write.network_access=true",
            "sandbox_mode=danger-full-access",
            "approval_policy=never",
            "shell_environment_policy.inherit=all",
            "features.something=true",
        ):
            with self.assertRaises(BRIDGE.CodexExecError, msg=override) as caught:
                BRIDGE.run_assignment(brief="work", target_dir=self.base, extra_config=[override])
            self.assertEqual(caught.exception.code, "CONFIG_OVERRIDE_FORBIDDEN", override)

    def test_malformed_override_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.run_assignment(brief="work", target_dir=self.base, extra_config=["no-equals-sign"])
        self.assertEqual(caught.exception.code, "CONFIG_OVERRIDE_INVALID")

    def test_mcp_server_attachment_is_refused(self) -> None:
        """The executor must never be able to reach the maintainer MCP server."""
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.validate_extra_config(['mcp_servers.evil.command="python3"'])
        self.assertEqual(caught.exception.code, "CONFIG_OVERRIDE_FORBIDDEN")

    def test_every_escape_route_is_refused(self) -> None:
        for override in (
            'mcp_servers.evil.command="python3"',
            'mcp_servers.evil.args=["x"]',
            'model_providers.x.base_url="http://evil"',
            'model_provider="x"',
            'openai_base_url="http://evil"',
            'notify=["curl","http://evil"]',
            'profile="x"',
            'sandbox="danger-full-access"',
            "tools.web_search=true",
            'experimental_instructions_file="/tmp/x"',
            'model_reasoning_effort="high"',
            ' Sandbox ="x"',
            '"sandbox"="x"',
            ' model_verbosity ="low"',
            'MODEL_VERBOSITY="low"',
        ):
            with self.assertRaises(BRIDGE.CodexExecError, msg=override) as caught:
                BRIDGE.validate_extra_config([override])
            self.assertEqual(caught.exception.code, "CONFIG_OVERRIDE_FORBIDDEN", override)

    def test_duplicate_key_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.validate_extra_config(['model_verbosity="low"', 'model_verbosity="high"'])
        self.assertEqual(caught.exception.code, "CONFIG_OVERRIDE_DUPLICATE")

    def test_empty_key_is_refused(self) -> None:
        with self.assertRaises(BRIDGE.CodexExecError) as caught:
            BRIDGE.validate_extra_config(['="x"'])
        self.assertEqual(caught.exception.code, "CONFIG_OVERRIDE_INVALID")

    def test_benign_override_is_forwarded(self) -> None:
        overrides = BRIDGE.validate_extra_config(['model_verbosity="low"'])
        self.assertEqual(overrides, ['model_verbosity="low"'])


class DiffSnapshotTests(BridgeTestCase):
    def test_missing_markers_map_to_add_and_delete(self) -> None:
        diff = BRIDGE.diff_snapshots(
            {"a": "sha256:1", "b": "missing", "c": "sha256:3"},
            {"a": "missing", "b": "sha256:2", "c": "sha256:3"},
        )
        self.assertEqual(diff, {"added": ["b"], "modified": [], "deleted": ["a"]})

    def test_untracked_disappearance_counts_as_deleted(self) -> None:
        diff = BRIDGE.diff_snapshots({"gone": "sha256:1"}, {})
        self.assertEqual(diff["deleted"], ["gone"])


class CliTests(BridgeTestCase):
    def run_cli(self, arguments: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/codex_exec_bridge.py"), *arguments],
            check=False,
            capture_output=True,
            text=True,
            input=stdin,
            timeout=120,
        )

    def test_cli_reads_brief_from_stdin_and_emits_json(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-cli",
            """
            import pathlib
            import sys

            brief = sys.stdin.read()
            target = pathlib.Path(sys.argv[sys.argv.index("--cd") + 1])
            (target / "cli.txt").write_text(brief, encoding="utf-8")
            """,
        )
        completed = self.run_cli(
            ["run", "--cd", str(root), "--codex-binary", str(stub), "--reasoning-effort", "high"],
            stdin="write a file",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["changed_files"]["added"], ["cli.txt"])
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertFalse(payload["network_access"])
        self.assertEqual((root / "cli.txt").read_text(encoding="utf-8"), "write a file")

    def test_cli_rejects_forbidden_sandbox(self) -> None:
        completed = self.run_cli(["run", "--cd", str(self.base), "--sandbox", "danger-full-access"])
        self.assertEqual(completed.returncode, 2)
        self.assertIn("danger-full-access", completed.stderr)

    def test_cli_reports_typed_error_as_json(self) -> None:
        completed = self.run_cli(["run", "--cd", str(self.base / "nowhere"), "--brief", "work"])
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "TARGET_DIR_INVALID")

    def test_cli_exit_code_one_on_execution_failure(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-cli-fail",
            """
            import sys
            sys.stdin.read()
            sys.exit(3)
            """,
        )
        completed = self.run_cli(
            ["run", "--cd", str(root), "--codex-binary", str(stub), "--brief", "fail"]
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(json.loads(completed.stdout)["code"], "CODEX_EXEC_FAILED")

    def test_cli_reads_brief_from_file(self) -> None:
        root = self.make_repository()
        stub = self.make_stub(
            "codex-cli-file",
            """
            import sys
            sys.stdout.write(sys.stdin.read())
            """,
        )
        brief_path = self.base / "brief.md"
        brief_path.write_text("from a file\n", encoding="utf-8")
        completed = self.run_cli(
            ["run", "--cd", str(root), "--codex-binary", str(stub), "--brief-file", str(brief_path)]
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["stdout"], "from a file\n")


class RealBinaryTests(BridgeTestCase):
    def test_real_codex_binary_accepts_the_generated_flags(self) -> None:
        binary = shutil.which(BRIDGE.DEFAULT_BINARY)
        if binary is None:
            self.skipTest("the codex binary is not installed in this environment")
        completed = subprocess.run(
            [binary, "exec", "--help"], check=False, capture_output=True, text=True, timeout=60
        )
        self.assertEqual(completed.returncode, 0)
        for flag in ("--cd", "--sandbox", "--output-last-message", "--color", "--json", "--model"):
            self.assertIn(flag, completed.stdout, f"{flag} is missing from `codex exec --help`")
        for mode in BRIDGE.ALLOWED_SANDBOX_MODES:
            self.assertIn(mode, completed.stdout)


if __name__ == "__main__":
    unittest.main()
