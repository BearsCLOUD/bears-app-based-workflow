"""Validate the declarative DIRECT route contract for app-solo-route."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/app-solo-route/SKILL.md"

EXPECTED_ROUTES = {
    "constitution-ready": "app-research",
    "needs-research": "app-research",
    "research-ready": "app-specify",
    "needs-spec": "app-specify",
    "spec-ready": "app-functional-graph",
    "needs-graph": "app-functional-graph",
    "graph-ready": "app-plan",
    "waiting": "app-plan",
    "needs-plan": "app-plan",
    "no-work": "app-analyze",
    "implemented": "app-analyze",
    "plan-ready": "app-dev",
    "ready": "app-dev",
    "pass": "none",
    "blocked": "none",
}


class AppSoloRouteContractTests(unittest.TestCase):
    """Keep the skill's route and stop invariants machine-checked."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")
        match = re.search(
            r"<!-- route-map:start -->\s*```json\s*(\{.*?\})\s*```\s*<!-- route-map:end -->",
            cls.text,
            flags=re.DOTALL,
        )
        if match is None:
            raise AssertionError("app-solo-route route map is missing")
        cls.routes = json.loads(match.group(1))

    def test_resume_and_all_forward_and_feedback_routes(self) -> None:
        self.assertEqual(self.routes, EXPECTED_ROUTES)
        self.assertIn("route only by its validated `target_stage`", self.text)
        self.assertIn("select the earliest incomplete stage", self.text)

    def test_stops_before_external_development(self) -> None:
        self.assertEqual(self.routes["plan-ready"], "app-dev")
        self.assertEqual(self.routes["ready"], "app-dev")
        self.assertIn("do not execute them", self.text)

    def test_direct_route_has_no_dispatch_surface(self) -> None:
        forbidden = ("$subagents", "dispatch-packet", "spawn_agent", "followup_task")
        self.assertFalse([token for token in forbidden if token in self.text])
        self.assertIn("Run only when the workstream is already classified `DIRECT`", self.text)

    def test_unchanged_handoff_cannot_loop(self) -> None:
        self.assertIn("Never execute the same target again from an unchanged fingerprint", self.text)
        self.assertIn("`unchanged-waiting`", self.text)

    def test_user_question_requires_architectural_fork(self) -> None:
        self.assertIn("Ask the user only when the current stage exposes an architectural fork", self.text)
        self.assertIn("at least two materially different architecture paths", self.text)
        self.assertIn("no artifact, accepted decision, constraint, or user answer selects one", self.text)

    def test_invalid_status_target_pair_is_rejected(self) -> None:
        self.assertIn("mismatched status/target pair before executing another stage", self.text)
        self.assertEqual(self.routes["pass"], "none")
        self.assertEqual(self.routes["blocked"], "none")


if __name__ == "__main__":
    unittest.main()
