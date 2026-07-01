from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from scripts import process_mining, workflow_improvement_candidates

class ProcessMiningTest(unittest.TestCase):
    def write_events(self, root: Path) -> Path:
        events={'events':[
            {'schema':'bears-process-trace-event.v1','event_id':'bad-transition','delivery_id':'d446','issue':'#446','source_path':'fixture','timestamp':None,'from_state':'queued','to_state':'closed','transition':'queued->closed','status':'pass','role_id':'role','error_class':None,'estimated_tokens':10,'evidence_paths':['fixture']},
            {'schema':'bears-process-trace-event.v1','event_id':'fail-1','delivery_id':'d446','issue':'#446','source_path':'fixture','timestamp':None,'from_state':'running','to_state':'validation','transition':'running->validation','status':'fail','role_id':'role','error_class':'validation_failure','estimated_tokens':10,'evidence_paths':['fixture']},
            {'schema':'bears-process-trace-event.v1','event_id':'fail-2','delivery_id':'d446','issue':'#446','source_path':'fixture','timestamp':None,'from_state':'running','to_state':'validation','transition':'running->validation','status':'fail','role_id':'role','error_class':'validation_failure','estimated_tokens':10,'evidence_paths':['fixture']},
            {'schema':'bears-process-trace-event.v1','event_id':'cost','delivery_id':'d446','issue':'#446','source_path':'fixture','timestamp':None,'from_state':'validation','to_state':'closed','transition':'validation->closed','status':'pass','role_id':'role','error_class':None,'estimated_tokens':13000,'evidence_paths':['fixture']}
        ]}
        p=root/'events.json'; p.write_text(json.dumps(events)); return p
    def test_compare_and_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); events=self.write_events(root); model=root/'model.json'; model.write_text(json.dumps({'allowed_transitions':['queued->running','running->validation','validation->closed']}))
            report=process_mining.compare(model, events)
            types={f['finding_type'] for f in report['findings']}
            self.assertIn('non_fitting_trace', types)
            self.assertIn('validator_gap', types)
            self.assertIn('context_budget_candidate', types)
            rp=root/'report.json'; rp.write_text(json.dumps(report))
            candidates=workflow_improvement_candidates.generate(rp)
            cp=root/'candidates.json'; cp.write_text(json.dumps(candidates))
            created=workflow_improvement_candidates.create_issues(cp, dry_run=True)
            self.assertEqual(candidates['candidate_count'], created['unique_candidate_count'])
    def test_ingest_rejects_raw_log_marker(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d)/'event.json'; p.write_text(json.dumps({'from_state':'queued','to_state':'running','status':'pass','reason':'raw log content'}))
            result=process_mining.ingest([str(p)])
            self.assertEqual(0, result['event_count'])
            self.assertTrue(result['errors'])
    def test_doctor(self):
        self.assertEqual('pass', process_mining.doctor()['status'])

if __name__ == '__main__': unittest.main()
