#!/usr/bin/env python3
"""Detect Bears role degradation from usage, context, and execution evidence."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
POLICY=PLUGIN_ROOT/'assets/catalog/role-degradation-policy.v1.json'
EVENT_SCHEMA=PLUGIN_ROOT/'assets/schemas/role-degradation-event.v1.schema.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import commit_usage_ledger, context_budget
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def policy()->dict[str,Any]: return load(POLICY)
def event(signal:str, role_id='unknown-role', severity='warning', base='baseline', cur='current', delivery_id=None, issue=None, commit_sha=None, action=None)->dict[str,Any]:
    actions={'token_regression':'audit_role','context_surface_growth':'split_skill','repeated_validation_failure':'tighten_prompt','repeated_fixer_failure':'manual_review','role_output_invalid':'tighten_prompt','scope_violation':'manual_review','dirty_scope':'manual_review','timeout_regression':'change_executor','manual_review_rate_growth':'manual_review','same_issue_retry_loop':'manual_review'}
    return {'schema':'bears-role-degradation-event.v1','delivery_id':delivery_id,'issue':issue,'commit_sha':commit_sha,'role_id':role_id,'role_kind':'platform_role','signal':signal,'severity':severity,'baseline_ref':base,'current_ref':cur,'evidence_paths':[], 'recommended_action':action or actions[signal]}
def validate_event(e:dict[str,Any])->list[str]: return validate_json_schema(e,EVENT_SCHEMA,'role-degradation-event')
def compare(base:str, head:str)->dict[str,Any]:
    diff=commit_usage_ledger.diff(base,head, ledger_root=commit_usage_ledger.DEFAULT_LEDGER_ROOT); events=[]
    for r in diff.get('regressions',[]): events.append(event('token_regression', severity='warning', base=base, cur=head, commit_sha=head))
    return {'schema':'bears-role-degradation-compare.v1','status':'warning' if events else 'pass','base':base,'head':head,'events':events,'errors':[err for e in events for err in validate_event(e)]}
def scan(delivery_id:str|None=None)->dict[str,Any]:
    events=[]; cb=context_budget.scan()
    if delivery_id and cb.get('oversized_surfaces'):
        first=cb['oversized_surfaces'][0]; events.append(event('context_surface_growth', role_id=first.get('surface_id','context'), severity='candidate', delivery_id=delivery_id, base='policy', cur=first.get('path','surface'), action='split_skill'))
    errors=[err for e in events for err in validate_event(e)]
    return {'schema':'bears-role-degradation-scan.v1','status':'warning' if events else 'pass','delivery_id':delivery_id,'events':events,'degradation':'detected' if events else 'none','errors':errors}
def validate_all()->list[str]:
    pol=policy(); req={'scripts/role_degradation.py scan --delivery-id <id> --json','scripts/role_degradation.py compare --base <sha> --head <sha> --json','scripts/role_remediation.py plan --event <path> --json','scripts/role_remediation.py validate-plan --plan <path>','scripts/role_degradation.py doctor --json'}
    errors=[f'missing command: {x}' for x in sorted(req-set(pol.get('commands',[])))]
    if set(pol.get('signals',[])) != {'token_regression','context_surface_growth','repeated_validation_failure','repeated_fixer_failure','role_output_invalid','scope_violation','dirty_scope','timeout_regression','manual_review_rate_growth','same_issue_retry_loop'}: errors.append('signals mismatch')
    return errors
def doctor()->dict[str,Any]:
    errs=validate_all(); return {'schema':'bears-role-degradation-doctor.v1','status':'pass' if not errs else 'fail','errors':errs}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('scan'); s.add_argument('--delivery-id'); s.add_argument('--json',action='store_true')
    c=sub.add_parser('compare'); c.add_argument('--base',required=True); c.add_argument('--head',required=True); c.add_argument('--json',action='store_true')
    d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='scan': pkt=scan(a.delivery_id); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    if a.cmd=='compare': pkt=compare(a.base,a.head); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    if a.cmd=='doctor': pkt=doctor(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
