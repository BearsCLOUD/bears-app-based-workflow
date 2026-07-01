#!/usr/bin/env python3
"""Generate dry-run workflow improvement issue candidates from mining reports."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
SCHEMA=PLUGIN_ROOT/'assets/schemas/workflow-improvement-candidate.v1.schema.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def candidate_type(ftype:str)->str:
    return {'non_fitting_trace':'state_machine_rule','validator_gap':'validator_gap','context_budget_candidate':'context_budget'}[ftype]
def make_candidate(f:dict[str,Any])->dict[str,Any]:
    ctype=candidate_type(f['finding_type'])
    key=ctype+':'+'|'.join(sorted(f.get('affected_nodes',[])))
    cid='wic-'+hashlib.sha1(key.encode()).hexdigest()[:12]
    title={'state_machine_rule':'Review workflow transition model','validator_gap':'Add validator coverage for repeated failure','context_budget':'Reduce high context-cost branch'}[ctype]
    body=json.dumps({'source_finding_id':f['finding_id'],'summary':f['summary'],'evidence_paths':f.get('evidence_paths',[])},sort_keys=True)
    return {'schema':'bears-workflow-improvement-candidate.v1','candidate_id':cid,'source_finding_id':f['finding_id'],'candidate_type':ctype,'title':title,'dedupe_key':key,'issue_body':body,'evidence_paths':f.get('evidence_paths',[]),'dry_run_only':True}
def generate(report_path:Path)->dict[str,Any]:
    report=load(report_path); candidates=[]; seen=set(); errors=[]
    for f in report.get('findings',[]):
        c=make_candidate(f)
        if c['dedupe_key'] in seen: continue
        seen.add(c['dedupe_key'])
        errors.extend(validate_json_schema(c,SCHEMA,'workflow-improvement-candidate'))
        candidates.append(c)
    return {'schema':'bears-workflow-improvement-candidates.v1','status':'pass' if not errors else 'fail','candidate_count':len(candidates),'candidates':candidates,'errors':errors}
def create_issues(candidates_path:Path, dry_run:bool)->dict[str,Any]:
    data=load(candidates_path); seen=set(); rows=[]
    for c in data.get('candidates',[]):
        key=c.get('dedupe_key')
        if key in seen: continue
        seen.add(key)
        rows.append({'dedupe_key':key,'title':c.get('title'),'action':'would_create' if dry_run else 'blocked_non_dry_run'})
    return {'schema':'bears-workflow-improvement-create-issues.v1','status':'pass' if dry_run else 'blocked','dry_run':dry_run,'unique_candidate_count':len(rows),'would_create':rows if dry_run else [],'errors':[] if dry_run else ['non-dry-run issue creation is not enabled for process mining']}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    g=sub.add_parser('generate'); g.add_argument('--report',required=True); g.add_argument('--json',action='store_true')
    c=sub.add_parser('create-issues'); c.add_argument('--candidates',required=True); c.add_argument('--dry-run',action='store_true'); c.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='generate': pkt=generate(Path(a.report)); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    if a.cmd=='create-issues': pkt=create_issues(Path(a.candidates),a.dry_run); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
