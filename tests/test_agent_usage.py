from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from scripts import agent_usage, commit_usage_ledger

class AgentUsageTest(unittest.TestCase):
    def event(self, event_id='e1', commit='head', tokens=100, surface='skill:a'):
        return {'schema':'bears-agent-usage-event.v1','event_id':event_id,'delivery_id':'delivery-419','issue':'#419','commit_sha':commit,'executor':'codex_exec','role_id':'bears-role','role_kind':'platform_role','model_tier':'standard','input_estimated_tokens':tokens,'output_estimated_tokens':0,'context_surface_ids':[surface],'decision_packet':None,'result_packet':None,'status':'pass','reason_code':'ok'}
    def test_event_schema_validates(self):
        self.assertEqual([], agent_usage.validate_event(self.event()))
    def test_raw_prompt_marker_rejected(self):
        e=self.event(); e['reason_code']='raw prompt payload'
        self.assertTrue(agent_usage.validate_event(e))
    def test_record_summarize_build_and_diff(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); store=root/'events.jsonl'; ledgers=root/'ledgers'; ledgers.mkdir()
            for e in (self.event('base','base',100,'skill:a'), self.event('head','head',200,'skill:b')):
                p=root/f"{e['event_id']}.json"; p.write_text(json.dumps(e))
                self.assertEqual('pass', agent_usage.record(p,store)['status'])
            summary=agent_usage.summarize('delivery-419',store=store)
            self.assertEqual(2, summary['event_count'])
            base=commit_usage_ledger.build('base',store=store); head=commit_usage_ledger.build('head',store=store)
            (ledgers/'base.json').write_text(json.dumps(base)); (ledgers/'head.json').write_text(json.dumps(head))
            diff=commit_usage_ledger.diff('base','head',ledger_root=ledgers)
            self.assertEqual('warning', diff['status'])
            self.assertEqual('token_regression', diff['regressions'][0]['type'])
    def test_doctor(self):
        self.assertEqual('pass', commit_usage_ledger.doctor()['status'])

if __name__ == '__main__': unittest.main()
