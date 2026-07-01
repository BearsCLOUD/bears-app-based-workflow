from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from scripts import agent_usage, commit_usage_ledger, role_degradation, role_remediation

class RoleDegradationTest(unittest.TestCase):
    def usage(self, eid, commit, tokens):
        return {'schema':'bears-agent-usage-event.v1','event_id':eid,'delivery_id':'delivery-420','issue':'#420','commit_sha':commit,'executor':'codex_exec','role_id':'role-a','role_kind':'platform_role','model_tier':'standard','input_estimated_tokens':tokens,'output_estimated_tokens':0,'context_surface_ids':['role-a'], 'decision_packet':None,'result_packet':None,'status':'pass','reason_code':'ok'}
    def test_token_regression_creates_event(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); store=root/'events.jsonl'; ledgers=root/'ledgers'; ledgers.mkdir()
            for e in (self.usage('base','base',100), self.usage('head','head',200)):
                p=root/f"{e['event_id']}.json"; p.write_text(json.dumps(e)); agent_usage.record(p,store)
            (ledgers/'base.json').write_text(json.dumps(commit_usage_ledger.build('base',store=store)))
            (ledgers/'head.json').write_text(json.dumps(commit_usage_ledger.build('head',store=store)))
            old=commit_usage_ledger.DEFAULT_LEDGER_ROOT; commit_usage_ledger.DEFAULT_LEDGER_ROOT=ledgers
            try: result=role_degradation.compare('base','head')
            finally: commit_usage_ledger.DEFAULT_LEDGER_ROOT=old
            self.assertEqual('token_regression', result['events'][0]['signal'])
    def test_invalid_role_output_requires_audit(self):
        e=role_degradation.event('role_output_invalid', role_id='role-a')
        plan=role_remediation.plan_from_event(e)
        self.assertTrue(plan['manual_review_required'])
        self.assertIn('audit_role_output', plan['actions'])
    def test_repeated_fixer_failure_blocks_autofix(self):
        e=role_degradation.event('repeated_fixer_failure', role_id='role-a', severity='blocking')
        plan=role_remediation.plan_from_event(e)
        self.assertFalse(plan['auto_fix_allowed'])
        self.assertTrue(plan['manual_review_required'])
    def test_doctor(self):
        self.assertEqual('pass', role_degradation.doctor()['status'])

if __name__ == '__main__': unittest.main()
