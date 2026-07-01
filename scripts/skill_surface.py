#!/usr/bin/env python3
"""Decide when Bears skill and role surfaces must split or index."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
DECISION_SCHEMA=PLUGIN_ROOT/'assets/schemas/skill-split-decision.v1.schema.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import context_budget
MIXED_MARKERS=('## Scope','## Workflow gates','## Validation','## Runtime','## Deployment')
def split_decision(path:Path)->dict[str,Any]:
    s=context_budget.surface(path); text=(PLUGIN_ROOT/s['path']).read_text(encoding='utf-8') if (PLUGIN_ROOT/s['path']).exists() else ''
    mixed=sum(1 for m in MIXED_MARKERS if m in text)>=3
    if s['split_policy']=='split_required': decision,reason='split','too_large'
    elif mixed: decision,reason='split','mixed_authority'
    elif s['split_policy']=='index_required': decision,reason='index','too_large'
    else: decision,reason='keep','ok'
    pkt={'schema':'bears-skill-split-decision.v1','surface_id':s['surface_id'],'decision':decision,'reason_code':reason,'target_surfaces':[] if decision=='keep' else [s['path']+':shard-index'],'evidence_paths':[s['path']]}
    errs=validate_json_schema(pkt,DECISION_SCHEMA,'skill-split-decision')
    if errs: pkt['target_surfaces'].extend(errs)
    return pkt
def doctor()->dict[str,Any]:
    errs=context_budget.validate_all(); return {'schema':'bears-skill-surface-doctor.v1','status':'pass' if not errs else 'fail','errors':errs}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    sd=sub.add_parser('split-decision'); sd.add_argument('--path',required=True); sd.add_argument('--json',action='store_true')
    d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='split-decision': pkt=split_decision(Path(a.path)); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['decision']); return 0
    if a.cmd=='doctor': pkt=doctor(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
