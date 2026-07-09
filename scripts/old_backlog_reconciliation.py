#!/usr/bin/env python3
"""Classify old open plugin backlog with exact proof rows."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
CATALOG=PLUGIN_ROOT/'assets/catalog/old-backlog-reconciliation.v1.json'
DEFAULT_REPO='BearsCLOUD/bears_plugin'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts import issue_state_reconciler

def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def now()->str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def gh_issue(repo:str,num:int)->dict[str,Any]:
    proc=subprocess.run(['gh','issue','view',str(num),'--repo',repo,'--json','number,title,state,url'],cwd=str(PLUGIN_ROOT),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=20)
    if proc.returncode!=0: return {'number':num,'state':'UNKNOWN','title':'','url':'','repo':repo}
    row=json.loads(proc.stdout); row['repo']=repo; return row
def read_issues(repo:str, issues_json:Path|None)->list[dict[str,Any]]:
    if issues_json: return load(issues_json)
    return [gh_issue(repo,int(n)) for n in load(CATALOG)['target_issues']]
def build(repo:str=DEFAULT_REPO, issues_json:Path|None=None)->dict[str,Any]:
    cat=load(CATALOG); proofs={int(k):v for k,v in cat.get('proof_map',{}).items()}; rows=[]
    for issue in read_issues(repo,issues_json):
        num=int(issue['number']); proof=proofs.get(num); cls=proof.get('classification') if proof else cat['default_open_classification']
        action='close_completed' if issue.get('state')=='OPEN' and cls in {'completed','superseded'} and proof else ('leave_open_classified' if issue.get('state')=='OPEN' else 'no_action_closed')
        rows.append({'issue':num,'github_state':issue.get('state','UNKNOWN'),'proposed_classification':cls,'proof_commit':proof.get('proof_commit') if proof else None,'proof_path':proof.get('proof_path') if proof else None,'related_delivery_id':proof.get('delivery_id') if proof else None,'action':action,'reason':proof.get('reason') if proof else 'phase 2 or manual review needs separate exact proof'})
    packet={'schema':'bears-old-open-backlog-reconciliation.v1','version':'1','generated_at':now(),'repo':repo,'status':'pass','rows':rows,'actions_taken':[],'blockers':[],'remaining_phase_2':[r['issue'] for r in rows if r['proposed_classification']=='phase_2']}
    return packet
def validate_all()->list[str]:
    errors=[]; cat=load(CATALOG)
    if not cat.get('target_issues'): errors.append('target_issues missing')
    for key,val in cat.get('proof_map',{}).items():
        if val.get('classification') in {'completed','superseded'} and not (val.get('proof_commit') and val.get('proof_path')): errors.append(f'proof missing for {key}')
    # #404 solved-open detector must be importable and expose solved_open.
    if not hasattr(issue_state_reconciler,'solved_open'): errors.append('solved-open closeout detector missing')
    return errors
def doctor()->dict[str,Any]:
    errs=validate_all(); return {'schema':'bears-old-backlog-reconciliation-doctor.v1','status':'pass' if not errs else 'fail','evidence_path':'runtime/issue-reconciliation/old-open-backlog.v1.json','errors':errs}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    b=sub.add_parser('build'); b.add_argument('--repo',default=DEFAULT_REPO); b.add_argument('--issues-json'); b.add_argument('--write'); b.add_argument('--json',action='store_true')
    v=sub.add_parser('validate'); v.add_argument('--json',action='store_true')
    d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='build':
        pkt=build(a.repo, Path(a.issues_json) if a.issues_json else None)
        if a.write:
            out=PLUGIN_ROOT/a.write if not Path(a.write).is_absolute() else Path(a.write); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(pkt,indent=2,sort_keys=True)+'\n')
        print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    if a.cmd=='validate': errs=validate_all(); pkt={'schema':'bears-old-backlog-reconciliation-validation.v1','status':'pass' if not errs else 'fail','errors':errs}; print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if not errs else 1
    if a.cmd=='doctor': pkt=doctor(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
