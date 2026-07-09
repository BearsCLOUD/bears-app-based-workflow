#!/usr/bin/env python3
"""Record and summarize compact Bears agent usage events."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
POLICY=PLUGIN_ROOT/'assets/catalog/agent-usage-policy.v1.json'
EVENT_SCHEMA=PLUGIN_ROOT/'assets/schemas/agent-usage-event.v1.schema.json'
STORE=PLUGIN_ROOT/'runtime/agent-usage/events.jsonl'
SESSION_POOL_STATE=PLUGIN_ROOT/'runtime/session-pool/session-pool-state.v1.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
FORBIDDEN=("BEGIN PRIVATE KEY","raw_secret",".env=","credential=","raw prompt","raw chat","raw log","production data")
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def has_forbidden(v:Any)->bool:
    text=json.dumps(v,ensure_ascii=False).casefold(); return any(x.casefold() in text for x in FORBIDDEN)
def validate_event(event:dict[str,Any])->list[str]:
    errors=validate_json_schema(event,EVENT_SCHEMA,'agent-usage-event')
    if has_forbidden(event): errors.append('usage event contains forbidden raw data marker')
    return errors
def record(event_path:Path, store:Path=STORE)->dict[str,Any]:
    event=load(event_path); errors=validate_event(event)
    if not errors:
        store.parent.mkdir(parents=True,exist_ok=True)
        with store.open('a',encoding='utf-8') as h: h.write(json.dumps(event,sort_keys=True)+'\n')
    return {'schema':'bears-agent-usage-record-result.v1','status':'pass' if not errors else 'fail','event_id':event.get('event_id'),'errors':errors,'store':str(store.relative_to(PLUGIN_ROOT) if store.is_relative_to(PLUGIN_ROOT) else store)}
def events(store:Path=STORE)->list[dict[str,Any]]:
    if not store.exists(): return []
    out=[]
    for line in store.read_text(encoding='utf-8').splitlines():
        if line.strip():
            try: out.append(json.loads(line))
            except Exception: pass
    return out
def summarize(delivery_id:str|None=None, issue:str|None=None, store:Path=STORE)->dict[str,Any]:
    rows=[e for e in events(store) if (not delivery_id or e.get('delivery_id')==delivery_id) and (not issue or e.get('issue')==issue)]
    total=sum(int(e.get('input_estimated_tokens',0))+int(e.get('output_estimated_tokens',0)) for e in rows)
    by_executor={}; by_role={}; surfaces={}
    for e in rows:
        tokens=int(e.get('input_estimated_tokens',0))+int(e.get('output_estimated_tokens',0))
        by_executor[e.get('executor','unknown')]=by_executor.get(e.get('executor','unknown'),0)+tokens
        role=e.get('role_id') or 'unknown'; by_role[role]=by_role.get(role,0)+tokens
        for sid in e.get('context_surface_ids',[]): surfaces[sid]=surfaces.get(sid,0)+tokens
    largest=[{'surface_id':k,'estimated_tokens':v} for k,v in sorted(surfaces.items(),key=lambda x:(-x[1],x[0]))[:10]]
    return {'schema':'bears-agent-usage-summary.v1','status':'pass','delivery_id':delivery_id,'issue':issue,'event_count':len(rows),'total_estimated_tokens':total,'by_executor':by_executor,'by_role':by_role,'largest_context_surfaces':largest,'errors':[]}

def summarize_packet()->dict[str,Any]:
    unit_ids:set[str]=set(); session_ids:set[str]=set()
    if SESSION_POOL_STATE.exists():
        try: state=json.loads(SESSION_POOL_STATE.read_text(encoding='utf-8'))
        except Exception: state={}
        for session in state.get('sessions',[]) if isinstance(state,dict) else []:
            if not isinstance(session,dict): continue
            sid=session.get('session_id')
            if isinstance(sid,str) and sid: session_ids.add(sid)
            usage=session.get('usage_summary',{})
            if isinstance(usage,dict):
                for unit_id in usage.get('unit_ids',[]):
                    if isinstance(unit_id,str) and unit_id: unit_ids.add(unit_id)
                for usage_session_id in usage.get('session_ids',[]):
                    if isinstance(usage_session_id,str) and usage_session_id: session_ids.add(usage_session_id)
    return {'schema':'bears-agent-usage-summary.v1','status':'pass','usage_state':'local_unmetered','unit_ids':sorted(unit_ids),'session_ids':sorted(session_ids),'errors':[]}

def validate_all()->list[str]:
    errors=[]; pol=load(POLICY)
    req={'scripts/agent_usage.py record --event <path>','scripts/agent_usage.py summarize --delivery-id <id> --json','scripts/commit_usage_ledger.py build --commit <sha> --json','scripts/commit_usage_ledger.py diff --base <sha> --head <sha> --json','scripts/commit_usage_ledger.py doctor --json'}
    missing=req-set(pol.get('commands',[])); errors += [f'missing command: {m}' for m in sorted(missing)]
    if pol.get('owner_issue')!='#419': errors.append('owner_issue must be #419')
    return errors
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    r=sub.add_parser('record'); r.add_argument('--event',required=True); r.add_argument('--store')
    s=sub.add_parser('summarize'); s.add_argument('--delivery-id'); s.add_argument('--issue'); s.add_argument('--store'); s.add_argument('--json',action='store_true')
    v=sub.add_parser('validate'); v.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='record': pkt=record(Path(a.event), Path(a.store) if a.store else STORE); print(json.dumps(pkt,indent=2,sort_keys=True)); return 0 if pkt['status']=='pass' else 1
    if a.cmd=='summarize': pkt=summarize(a.delivery_id,a.issue,Path(a.store) if a.store else STORE); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    if a.cmd=='validate': errs=validate_all(); pkt={'schema':'bears-agent-usage-validation.v1','status':'pass' if not errs else 'fail','errors':errs}; print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if not errs else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
