#!/usr/bin/env python3
"""Build bounded Bears role remediation plans from degradation events."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
PLAN_SCHEMA=PLUGIN_ROOT/'assets/schemas/role-remediation-plan.v1.schema.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import role_degradation

def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))

def plan_from_event(event:dict[str,Any])->dict[str,Any]:
    signal=event.get('signal','unknown')
    rid=event.get('role_id','unknown-role')
    manual=signal in {'repeated_fixer_failure','scope_violation','dirty_scope','manual_review_rate_growth','same_issue_retry_loop'} or event.get('severity')=='blocking'
    audit=signal in {'role_output_invalid','scope_violation','dirty_scope','token_regression'}
    actions={
        'token_regression':['audit_role_context','reduce_context_surfaces'],
        'context_surface_growth':['split_context_surface','add_section_index'],
        'repeated_validation_failure':['tighten_validation_contract','add_fixture'],
        'repeated_fixer_failure':['manual_review','freeze_auto_fix'],
        'role_output_invalid':['audit_role_output','tighten_prompt_contract'],
        'scope_violation':['manual_review','repair_scope_gate'],
        'dirty_scope':['manual_review','repair_checkout_gate'],
        'timeout_regression':['change_executor_profile','add_timeout_budget'],
        'manual_review_rate_growth':['manual_review','inspect_role_drift'],
        'same_issue_retry_loop':['manual_review','break_retry_loop']
    }.get(signal,['manual_review'])
    if audit and 'audit_role_output' not in actions and 'audit_role_context' not in actions:
        actions.append('audit_role_output')
    plan_id='role-remediation-'+hashlib.sha1(json.dumps(event,sort_keys=True).encode()).hexdigest()[:12]
    return {'schema':'bears-role-remediation-plan.v1','plan_id':plan_id,'event':event,'target_role_id':rid,'target_surfaces':list(event.get('evidence_paths') or []),'actions':actions,'auto_fix_allowed':not manual,'manual_review_required':manual or audit,'evidence_paths':list(event.get('evidence_paths') or [])}

def validate_plan(packet:dict[str,Any])->list[str]:
    packet={k:v for k,v in packet.items() if k not in {'status','errors'}}
    errors=validate_json_schema(packet,PLAN_SCHEMA,'role-remediation-plan')
    errors.extend(role_degradation.validate_event(packet.get('event',{})))
    ev=packet.get('event',{})
    if ev.get('signal')=='repeated_fixer_failure' and packet.get('auto_fix_allowed'):
        errors.append('repeated fixer failure must block auto-fix')
    if ev.get('signal')=='role_output_invalid' and not packet.get('manual_review_required'):
        errors.append('invalid role output must require audit/manual review')
    return errors

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    pl=sub.add_parser('plan'); pl.add_argument('--event',required=True); pl.add_argument('--json',action='store_true')
    vp=sub.add_parser('validate-plan'); vp.add_argument('--plan',required=True); vp.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='plan':
        pkt=plan_from_event(load(Path(a.event))); errs=validate_plan(pkt); pkt['status']='pass' if not errs else 'fail'; pkt['errors']=errs
        print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if not errs else 1
    if a.cmd=='validate-plan':
        errs=validate_plan(load(Path(a.plan))); pkt={'schema':'bears-role-remediation-validation.v1','status':'pass' if not errs else 'fail','errors':errs}
        print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if not errs else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
