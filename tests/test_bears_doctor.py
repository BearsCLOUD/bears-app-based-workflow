import shutil
import unittest
from unittest import mock

from scripts import bears_doctor


class BearsDoctorTests(unittest.TestCase):
    def test_validate_accepts_good_and_rejects_bad_fixture(self) -> None:
        self.assertEqual(bears_doctor.validate_result_packet(bears_doctor.load(bears_doctor.GOOD), "good"), [])
        self.assertTrue(bears_doctor.validate_result_packet(bears_doctor.load(bears_doctor.BAD), "bad"))

    def test_current_doctor_catalog_validates(self) -> None:
        self.assertEqual(bears_doctor.validate_all(), [])


    def test_canonical_plugin_worktree_check_passes_for_expected_root(self) -> None:
        with mock.patch.object(bears_doctor, "CANONICAL_PLUGIN_ROOT", bears_doctor.PLUGIN_ROOT):
            with mock.patch.object(
                bears_doctor,
                "git_output",
                side_effect=[(0, str(bears_doctor.PLUGIN_ROOT)), (1, "")],
            ):
                check = bears_doctor.canonical_plugin_worktree_check()
        self.assertEqual(check["status"], "pass")

    def test_canonical_plugin_worktree_check_blocks_redirected_toplevel(self) -> None:
        with mock.patch.object(bears_doctor, "CANONICAL_PLUGIN_ROOT", bears_doctor.PLUGIN_ROOT):
            with mock.patch.object(
                bears_doctor,
                "git_output",
                side_effect=[(0, "/tmp/bears-plugin-enterprise"), (0, "/tmp/bears-plugin-enterprise")],
            ):
                check = bears_doctor.canonical_plugin_worktree_check()
        self.assertEqual(check["status"], "fail")
        self.assertIn("git toplevel mismatch", check["summary"])

    def test_not_available_future_component_is_non_blocking_warning(self) -> None:
        check = bears_doctor.command_check({"id": "workspace_hygiene", "required": False, "component_issue": "#386"}, "HEAD~1..HEAD")
        self.assertEqual(check["status"], "not_available")
        self.assertFalse(check["required"])

    def test_required_failed_check_becomes_blocker(self) -> None:
        packet = {
            "schema": "bears-doctor-result.v1",
            "version": "1",
            "status": "fail",
            "commit_range": "HEAD~1..HEAD",
            "changed_files": ["scripts/bears_doctor.py"],
            "checks": [
                {"id": "decision_ledger_required", "status": "fail", "required": True, "summary": "missing decision", "exit_code": 1}
            ],
            "failed_checks": ["decision_ledger_required"],
            "warnings": [],
            "blockers": ["decision_ledger_required: missing decision"],
            "required_next_actions": ["resolve blocking closeout checks and rerun bears_doctor validate-closeout"],
            "sanitized_summary": "closeout has blocking checks",
            "closeout_summary": {
                "final_sha": "0123456789abcdef0123456789abcdef01234567",
                "delivery_id": "bears-governance-kernel-v1",
                "issue_refs": ["#391"],
                "scope": "machine-first-execution-kernel",
                "affected_range": "HEAD^..HEAD",
                "expected_evidence_paths": ["runtime/local-commit-validation/0123456789abcdef0123456789abcdef01234567.json"],
                "changelog": {"status": "linked", "reference": "release-note-gate:#384 delivery_id:bears-governance-kernel-v1", "delivery_id": "bears-governance-kernel-v1"},
                "known_blockers": [],
                "validation_result": "pass",
                "doctor_result": "fail",
                "debt_status": "none",
                "cleanup_status": "no_tracked_runtime_files",
                "final_report_policy": "Final user replies may stay short after bears_doctor emits closeout_summary with delivery_id.",
            },
        }
        self.assertEqual(bears_doctor.validate_result_packet(packet, "packet"), [])

    def test_release_gate_check_summary_is_exposed(self) -> None:
        packet = {
            "schema": "bears-issue-closeout-release-gate-summary.v1",
            "status": "pass",
            "delivery_id": "bears-governance-kernel-v1",
            "manifests": [{"release_gate": {"status": "exempt"}}],
            "errors": [],
        }
        with mock.patch.object(bears_doctor, "run_json", return_value=(0, packet)):
            check = bears_doctor.command_check(
                {
                    "id": "issue_release_gate",
                    "required": True,
                    "component_issue": "#403",
                    "command": [
                        "python3",
                        "scripts/issue_closeout.py",
                        "check-release-gate",
                        "--delivery-id",
                        "bears-governance-kernel-v1",
                    ],
                },
                "HEAD~1..HEAD",
            )
        self.assertEqual(check["status"], "pass")
        self.assertIn("release_gate=", check["summary"])

    def test_repo_routing_check_summary_is_exposed(self) -> None:
        packet = {
            "status": "pass",
            "repo": "BearsCLOUD/bears-codex-workflow-plugin",
            "route": {"worktree_path": "/srv/bears/plugins/bears"},
            "hook_proof": {"status": "pass"},
            "touched_repos": [{"access": "write_scoped"}, {"access": "read_only"}],
        }
        with mock.patch.object(bears_doctor, "run_json", return_value=(0, packet)):
            check = bears_doctor.command_check(
                {
                    "id": "issue_repo_routing",
                    "required": True,
                    "component_issue": "#402",
                    "command": ["python3", "scripts/issue_intake.py", "route", "--issue", "402", "--json"],
                },
                "HEAD~1..HEAD",
            )
        self.assertEqual(check["status"], "pass")
        self.assertIn("hook_proof=pass", check["summary"])
        self.assertIn("write_scoped=1", check["summary"])

    def test_external_review_audit_summary_is_exposed(self) -> None:
        packet = {"status": "pass", "errors": []}
        with mock.patch.object(bears_doctor, "run_json", return_value=(0, packet)):
            check = bears_doctor.command_check(
                {
                    "id": "external_review_audit",
                    "required": True,
                    "component_issue": "#425",
                    "command": ["python3", "scripts/external_review_audit.py", "validate"],
                },
                "HEAD~1..HEAD",
            )
        self.assertEqual(check["status"], "pass")
        self.assertIn("external_review=pass", check["summary"])

    def test_capability_harness_check_is_exposed(self) -> None:
        with mock.patch.object(bears_doctor, "run", return_value=(0, "ok")):
            check = bears_doctor.command_check(
                {
                    "id": "capability_harness",
                    "required": True,
                    "component_issue": "#451",
                    "command": ["python3", "scripts/capability_harness.py", "validate-catalog", "--json"],
                },
                "HEAD~1..HEAD",
            )
        self.assertEqual(check["status"], "pass")
        self.assertEqual(check["summary"], "ok")


    def test_open_validation_remediation_blocks_closeout(self) -> None:
        sha = "b" * 40
        root = bears_doctor.PLUGIN_ROOT / "runtime/validation-state" / sha
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / "remediation.v1.json").write_text(
                '{"schema":"bears-validation-remediation.v1","version":"1","status":"open","commit_sha":"'
                + sha
                + '","job_id":"plugins_bears-bbbbbbbbbbbb","failure_classification":"test_fail","sanitized_summary":"failed","next_action":"fix"}\n',
                encoding="utf-8",
            )
            check = bears_doctor.unresolved_blocker_check()
            self.assertEqual(check["status"], "fail")
            self.assertIn("blocking validation remediation", check["summary"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_parent_range_uses_exact_target_commit(self) -> None:
        commit = bears_doctor.target_commit("HEAD")
        if commit:
            self.assertTrue(bears_doctor.parent_range(commit).endswith(f"..{commit}"))

    def test_forbidden_marker_detection_is_case_insensitive(self) -> None:
        self.assertTrue(bears_doctor.has_forbidden({"summary": "Credential=value"}))
        self.assertFalse(bears_doctor.has_forbidden({"summary": "bounded summary"}))


if __name__ == "__main__":
    unittest.main()
