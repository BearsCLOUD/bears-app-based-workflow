from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from scripts import old_backlog_reconciliation

class OldBacklogReconciliationTest(unittest.TestCase):
    def test_build_classifies_completed_and_phase2(self):
        issues=[{'repo':'BearsCLOUD/bears-codex-workflow-plugin','number':382,'state':'OPEN','title':'artifact registry'}, {'repo':'BearsCLOUD/bears-codex-workflow-plugin','number':370,'state':'OPEN','title':'dispatcher'}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'issues.json'; p.write_text(json.dumps(issues))
            pkt=old_backlog_reconciliation.build(issues_json=p)
        rows={r['issue']:r for r in pkt['rows']}
        self.assertEqual('completed', rows[382]['proposed_classification'])
        self.assertEqual('close_completed', rows[382]['action'])
        self.assertEqual('phase_2', rows[370]['proposed_classification'])
        self.assertEqual('leave_open_classified', rows[370]['action'])
    def test_validate(self):
        self.assertEqual([], old_backlog_reconciliation.validate_all())
    def test_doctor(self):
        self.assertEqual('pass', old_backlog_reconciliation.doctor()['status'])

if __name__ == '__main__': unittest.main()
