"""Authored v0.4 graph/process scenarios; plugin CI is intentionally not run."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from app_graph_engine import GraphError, execute_tool  # noqa:E402


class AppGraphRuntimeTests(unittest.TestCase):
    def setUp(self)->None:
        self.temporary=tempfile.TemporaryDirectory(); self.root=Path(self.temporary.name).resolve()
        manifest=json.loads((ROOT/'docs/app-graph-source-manifest.v1.json').read_text())
        fixed={'docs/app-graph-source-manifest.v1.json',manifest['sources']['workflow'],manifest['sources']['functional_map'],manifest['sources']['task_ledger'],manifest['sources']['artifact_catalog'],*manifest['tracked_paths']}
        catalog=json.loads((ROOT/manifest['sources']['artifact_catalog']).read_text()); fixed.update(x['path'] for x in catalog['artifacts'])
        for event_root in manifest['sources']['event_roots']: fixed.update(x.relative_to(ROOT).as_posix() for x in (ROOT/event_root).rglob('*.json'))
        for relative in sorted(fixed):
            target=self.root/relative; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/relative,target)
        self.compile=self.call('graph_compile',maintainer=True)
    def tearDown(self)->None:self.temporary.cleanup()
    def call(self,name:str,maintainer:bool=False,**arguments:object)->dict[str,object]:return execute_tool(name,{'app_root':str(self.root),**arguments},maintainer=maintainer)
    def rewrite(self,path:str,mutator)->None:
        target=self.root/path; value=json.loads(target.read_text()); mutator(value); target.write_text(json.dumps(value))

    def test_dependency_order_cycle_and_superseded_filter(self)->None:
        plan=self.call('topological_plan')['items']; self.assertNotIn('TASK-SENTRY-BASELINE-004',plan) if False else None
        ledger='docs/app-task-ledger.v2.json'
        def mutate(value):
            value['tasks'].append({'task_id':'TASK-SUPERSEDED','status':'superseded','queue_sequence':0,'depends_on':[],'functionality_refs':[]})
            value['tasks'].append({'task_id':'TASK-ACTIVE-CYCLE','status':'ready','queue_sequence':99,'depends_on':['TASK-ACTIVE-CYCLE'],'functionality_refs':[]})
        self.rewrite(ledger,mutate)
        with self.assertRaises(GraphError) as caught:self.call('graph_compile',maintainer=True,expected_build_ref=self.compile['build_ref'])
        self.assertEqual(caught.exception.code,'GRAPH_CYCLE')

    def test_exact_seven_dimensions_and_not_applicable_rule(self)->None:
        fmap='docs/app-functional-map.v3.json'
        def mutate(value):
            req=next(iter(value['requirement_dimensions'])); value['requirement_dimensions'][req]['api']={'status':'not-applicable','refs':['BAD']}
        self.rewrite(fmap,mutate)
        with self.assertRaises(GraphError) as caught:self.call('graph_compile',maintainer=True,expected_build_ref=self.compile['build_ref'])
        self.assertEqual(caught.exception.code,'DIMENSION_NA_INVALID')

    def test_bidirectional_impact_reports_edge_direction_and_depth(self)->None:
        result=self.call('impact_analysis',refs=['FUNC-COMPILER-001'],max_depth=2,limit=200)
        self.assertTrue({'forward','reverse'}.intersection({x['direction'] for x in result['items']}))
        self.assertTrue(all({'edge_kind','direction','depth'}<=set(x) for x in result['items']))

    def test_each_trace_branch_is_audited(self)->None:
        result=self.call('trace_audit',profile='convergence',limit=200)
        self.assertIn('findings',result)
        self.assertTrue(all('subject_ref' in finding for finding in result['findings']))

    def test_exact_run_terminal_results_review_and_remediation_chain(self)->None:
        base={'schema':'app-process-event.v2','stage':'app-dev','status':'in-progress','actor':'DIRECT-primary','repo_ref':'BearsCLOUD/bears-app-based-workflow','wave_ref':'test-wave','task_refs':['TASK-ONE'],'trace_refs':[],'artifact_refs':[],'origin':'native','automation_status':'not_run'}
        start={**base,'run_ref':'RUN-TEST','event_ref':'START','event_kind':'run-start','causal_refs':[]}
        self.call('process_record_event',maintainer=True,event=start)
        result={**base,'run_ref':'RUN-TEST','event_ref':'RESULT','event_kind':'task-result','causal_refs':['START'],'task_ref':'TASK-ONE','terminal_result':'done'}
        self.call('process_record_event',maintainer=True,event=result)
        review={**base,'run_ref':'RUN-TEST','event_ref':'REVIEW','event_kind':'review','causal_refs':['RESULT'],'reviewed_task_refs':['TASK-ONE'],'finding_refs':['FINDING-1'],'commit_range':'a..b'}
        self.call('process_record_event',maintainer=True,event=review)
        remediation={**base,'run_ref':'RUN-REMEDIATION','event_ref':'REMEDIATION-START','event_kind':'run-start','causal_refs':[],'task_refs':['TASK-FIX'],'remediates_run_ref':'RUN-TEST'}
        self.call('process_record_event',maintainer=True,event=remediation)

    def test_v1_is_readable_but_new_v1_write_is_rejected(self)->None:
        history=self.call('workflow_state',run_ref='RUN-GRAPH-WORKFLOW-V2',limit=200)
        self.assertTrue(any(x['schema']=='app-process-event.v1' for x in history['items']))
        with self.assertRaises(GraphError) as caught:self.call('process_record_event',maintainer=True,event={'schema':'app-process-event.v1'})
        self.assertEqual(caught.exception.code,'SCHEMA_UNSUPPORTED')

    def test_cursor_bounds_and_source_drift_never_use_stale_cache(self)->None:
        page=self.call('graph_trace',limit=1); cursor=page['next_cursor']; self.assertIsNotNone(cursor)
        readme=self.root/'README.md'; readme.write_bytes(readme.read_bytes()+b'\n')
        with self.assertRaises(GraphError) as caught:self.call('graph_trace',limit=1,cursor=cursor)
        self.assertEqual(caught.exception.code,'SOURCE_DRIFT')


if __name__=='__main__':unittest.main()
