from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "temporal_evaluation.py"
spec = importlib.util.spec_from_file_location("temporal_evaluation", SCRIPT_PATH)
temporal_evaluation = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(temporal_evaluation)  # type: ignore[arg-type]


class TemporalEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = temporal_evaluation.load_json(
            PLUGIN_ROOT / "assets" / "catalog" / "temporal-evaluation.v1.json"
        )

    def test_catalog_validates(self) -> None:
        self.assertEqual(temporal_evaluation.validate_catalog(self.catalog), [])

    def test_doc_validates(self) -> None:
        self.assertEqual(temporal_evaluation.validate_doc(), [])

    def test_cli_validate_succeeds(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "not_adopted")
        self.assertEqual(payload["status"], "pass")

    def test_cli_report_json_succeeds(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "report", "--json"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "bears-temporal-evaluation-report.v1")
        self.assertEqual(payload["decision"], "not_adopted")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual({item["option"] for item in payload["comparison"]}, {
            "local_worker_state_file_model",
            "dagger_wrapper",
            "simple_queue_lease",
            "temporal",
        })

    def test_adopt_requires_preconditions(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["decision"] = "adopt"
        catalog["adoption_gate"]["preconditions_met"] = False

        errors = temporal_evaluation.validate_catalog(catalog)

        self.assertTrue(any("adopt requires preconditions" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
