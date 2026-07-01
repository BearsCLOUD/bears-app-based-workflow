from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/worker_pool.py"

spec = importlib.util.spec_from_file_location("worker_pool", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scripts/worker_pool.py")
worker_pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker_pool)


class WorkerPoolTests(unittest.TestCase):
    def test_write_scope_conflict_detector_exact_parent_reviewer_and_disjoint(self) -> None:
        exact = worker_pool.detect_conflicts(
            ["src/billing/service.py"],
            [{"id": "w1", "mode": "writer", "write_scope": ["src/billing/service.py"]}],
        )
        self.assertEqual(exact[0]["reason"], "exact_file_overlap")

        parent = worker_pool.detect_conflicts(
            ["src/billing/**"],
            [{"id": "w1", "mode": "writer", "write_scope": ["src/billing/service.py"]}],
        )
        self.assertEqual(parent[0]["reason"], "parent_directory_overlap")

        reviewer = worker_pool.detect_conflicts(
            ["src/billing/service.py"],
            [{"id": "r1", "mode": "reviewer-only", "write_scope": ["src/billing/service.py"]}],
        )
        self.assertEqual(reviewer, [])

        docs_source = worker_pool.detect_conflicts(
            ["docs/reference/session-workers-runtime.md"],
            [{"id": "w1", "mode": "writer", "write_scope": ["scripts/worker_pool.py"]}],
        )
        self.assertEqual(docs_source, [])

    def test_plan_tracks_pr_pipeline_fields_and_safe_parallel_actions(self) -> None:
        state = {
            "repo": "BearsCLOUD/bears-codex-workflow-plugin",
            "issues": [
                {
                    "number": 201,
                    "state": "open",
                    "role": "bears-session-worker-runtime-engineer",
                    "write_scope": ["scripts/worker_pool.py", "tests/test_worker_pool.py"],
                    "dependencies": [],
                }
            ],
            "pull_requests": [
                {
                    "number": 301,
                    "issue": 203,
                    "state": "open",
                    "branch": "codex/block-generic-role-fallback",
                    "head_sha": "7" * 40,
                    "ci_state": "pending",
                    "review_state": "none",
                    "changed_files": ["assets/catalog/session-workers-runtime.v1.json"],
                }
            ],
            "assignments": [],
        }
        plan = worker_pool.plan_from_state(state, repo=state["repo"], mode="backend-only")
        self.assertEqual(plan["status"], "ok")
        self.assertIn(
            {
                "assigned_issue_slice": 203,
                "branch": "codex/block-generic-role-fallback",
                "pr": 301,
                "head_sha": "7" * 40,
                "ci_state": "pending",
                "review_state": "none",
                "merge_eligibility": "needs_review",
                "stale_branch_cleanup_eligible": False,
                "dependencies": [],
            },
            plan["tracked_pipelines"],
        )
        self.assertTrue(any(action["action"] == "spawn_implementer" and action["issue"] == 201 for action in plan["actions"]))
        self.assertTrue(any(action["action"] == "spawn_reviewer" and action["pr"] == 301 for action in plan["actions"]))

    def test_plan_blocks_backend_only_forbidden_scope(self) -> None:
        plan = worker_pool.plan_from_state(
            {
                "repo": "BearsCLOUD/bears-platform",
                "issues": [{"number": 62, "state": "open", "write_scope": ["frontend/app/**"], "dependencies": []}],
                "pull_requests": [],
                "assignments": [],
            },
            repo="BearsCLOUD/bears-platform",
            mode="backend-only",
        )
        self.assertEqual(plan["actions"], [])
        self.assertIn("backend-only excludes frontend", plan["blocked"][0]["reason"])

    def test_plan_blocks_unmet_dependency(self) -> None:
        plan = worker_pool.plan_from_state(
            {
                "repo": "BearsCLOUD/bears-platform",
                "issues": [
                    {"number": 64, "state": "open", "write_scope": ["src/a.py"], "dependencies": [63]},
                    {"number": 63, "state": "open", "write_scope": ["src/b.py"], "dependencies": []},
                ],
                "pull_requests": [],
                "assignments": [],
            },
            repo="BearsCLOUD/bears-platform",
            mode="backend-only",
        )
        blocked = [item for item in plan["blocked"] if item["issue"] == 64]
        self.assertEqual(len(blocked), 1)
        self.assertIn("dependency issue #63 is not complete", blocked[0]["reason"])
        self.assertEqual(plan["dependency_order"], [63, 64])

    def test_allocate_worktree_is_plan_only_for_review_and_merge(self) -> None:
        class Args:
            repo = "BearsCLOUD/bears-codex-workflow-plugin"
            purpose = "review"
            pr = 201
            branch = None
            expected_sha = "a" * 40
            path = None
            execute = False

        payload = worker_pool.allocate_worktree_plan(Args())
        self.assertEqual(payload["status"], "plan_only")
        self.assertFalse(payload["mutation_performed"])
        self.assertFalse(payload["shared_dirty_checkout_allowed"])
        self.assertTrue(payload["fresh_checkout_required"])

    def test_cli_plan_accepts_state_file(self) -> None:
        state = {
            "repo": "BearsCLOUD/bears-codex-workflow-plugin",
            "issues": [{"number": 201, "state": "open", "role": "bears-session-worker-runtime-engineer", "write_scope": ["scripts/worker_pool.py"], "dependencies": []}],
            "pull_requests": [],
            "assignments": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "plan", "--repo", state["repo"], "--state-file", str(state_path), "--backend-only"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["actions"][0]["action"], "spawn_implementer")

    def test_cli_validate_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
