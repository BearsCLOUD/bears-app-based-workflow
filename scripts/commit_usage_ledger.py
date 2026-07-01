#!/usr/bin/env python3
"""Build per-commit Bears usage ledgers."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
POLICY=PLUGIN_ROOT/'assets/catalog/agent-usage-policy.v1.json'
LEDGER_SCHEMA=PLUGIN_ROOT/'assets/schemas/commit-usage-ledger.v1.schema.json'
DEFAULT_STORE=PLUGIN_ROOT/'runtime/agent-usage/events.jsonl'
DEFAULT_LEDGER_ROOT=PLUGIN_ROOT/'runtime/commit-usage-ledger'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import agent_usage
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def policy()->dict[str,Any]: return load(POLICY)
def build(commit:str, store:Path=DEFAULT_STORE, write:bool=False)->dict[str,Any]:
    rows=[e for e in agent_usage.events(store) if e.get('commit_sha') in {commit,None}]
    delivery=next((e.get('delivery_id') for e in rows if e.get('delivery_id')), None)
    total=sum(int(e.get('input_estimated_tokens',0))+int(e.get('output_estimated_tokens',0)) for e in rows)
    by_executor={}; by_role={}; surfaces={}
    for e in rows:
        tokens=int(e.get('input_estimated_tokens',0))+int(e.get('output_estimated_tokens',0))
        by_executor[e.get('executor','unknown')]=by_executor.get(e.get('executor','unknown'),0)+tokens
        role=e.get('role_id') or 'unknown'; by_role[role]=by_role.get(role,0)+tokens
        for sid in e.get('context_surface_ids',[]): surfaces[sid]=surfaces.get(sid,0)+tokens
    largest=[{'surface_id':k,'estimated_tokens':v} for k,v in sorted(surfaces.items(),key=lambda x:(-x[1],x[0]))[:10]]
    pol=policy(); budget='blocked' if total>=pol.get('token_block_threshold',100000) else ('warning' if total>=pol.get('token_warning_threshold',50000) else 'pass')
    pkt={'schema':'bears-commit-usage-ledger.v1','commit_sha':commit,'delivery_id':delivery,'events':rows,'total_estimated_tokens':total,'by_executor':by_executor,'by_role':by_role,'largest_context_surfaces':largest,'budget_status':budget,'regressions':[]}
    errs=validate_json_schema(pkt,LEDGER_SCHEMA,'commit-usage-ledger')
    if errs: pkt['regressions'].append({'type':'schema_error','errors':errs})
    if write:
        DEFAULT_LEDGER_ROOT.mkdir(parents=True,exist_ok=True); (DEFAULT_LEDGER_ROOT/f'{commit}.json').write_text(json.dumps(pkt,indent=2,sort_keys=True)+'\n')
    return pkt
def diff(base:str, head:str, ledger_root:Path=DEFAULT_LEDGER_ROOT)->dict[str,Any]:
    def get(sha):
        p=ledger_root/f'{sha}.json'; return load(p) if p.exists() else build(sha)
    b,h=get(base),get(head); delta=int(h.get('total_estimated_tokens',0))-int(b.get('total_estimated_tokens',0))
    ratio=(h.get('total_estimated_tokens',0)/(b.get('total_estimated_tokens',1) or 1))
    regs=[]
    if ratio>=policy().get('regression_ratio_warning',1.25) and delta>0: regs.append({'type':'token_regression','base':b.get('total_estimated_tokens',0),'head':h.get('total_estimated_tokens',0),'ratio':ratio})
    return {'schema':'bears-commit-usage-diff.v1','status':'warning' if regs else 'pass','base':base,'head':head,'token_delta':delta,'regressions':regs}
def doctor()->dict[str,Any]:
    errs=agent_usage.validate_all()
    return {'schema':'bears-commit-usage-ledger-doctor.v1','status':'pass' if not errs else 'fail','errors':errs}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    b=sub.add_parser('build'); b.add_argument('--commit',required=True); b.add_argument('--store'); b.add_argument('--write',action='store_true'); b.add_argument('--json',action='store_true')
    d=sub.add_parser('diff'); d.add_argument('--base',required=True); d.add_argument('--head',required=True); d.add_argument('--json',action='store_true')
    doc=sub.add_parser('doctor'); doc.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='build': pkt=build(a.commit,Path(a.store) if a.store else DEFAULT_STORE,a.write); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['budget_status']); return 0 if pkt['budget_status']!='blocked' else 1
    if a.cmd=='diff': pkt=diff(a.base,a.head); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    if a.cmd=='doctor': pkt=doctor(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
