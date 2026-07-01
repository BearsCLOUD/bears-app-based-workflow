#!/usr/bin/env python3
"""Build governed Bears repository onboarding inventory."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
WORKSPACE_ROOT=Path('/srv/bears')
POLICY=PLUGIN_ROOT/'assets/catalog/repo-onboarding-policy.v1.json'
SCHEMA=PLUGIN_ROOT/'assets/schemas/repo-onboarding-inventory.v1.schema.json'
AUTOSTART=PLUGIN_ROOT/'assets/catalog/issue-autostart.v1.json'
AUTHORITY=PLUGIN_ROOT/'assets/catalog/authority-map.v1.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def now()->str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def catalog_routes()->list[dict[str,Any]]:
    cat=load(AUTOSTART); rp=cat.get('routing_policy',{})
    routes=[]
    routes += [r for r in rp.get('repository_allowlist',[]) if isinstance(r,dict)]
    routes += [r for r in rp.get('governed_repositories',[]) if isinstance(r,dict)]
    routes += [r for r in rp.get('related_read_only',[]) if isinstance(r,dict)]
    return routes
def authority_topics()->set[str]:
    try: return {str(t.get('topic')) for t in load(AUTHORITY).get('topics',[]) if isinstance(t,dict) and t.get('topic')}
    except Exception: return set()
def hook_status(route:dict[str,Any])->str:
    if route.get('access')!='write_scoped': return 'not_required'
    hp=str(route.get('hook_proof') or '')
    if not hp: return 'missing'
    path=Path(hp) if Path(hp).is_absolute() else PLUGIN_ROOT/hp
    if not path.exists(): return 'missing'
    try: pkt=load(path)
    except Exception: return 'fail'
    return 'pass' if pkt.get('status')=='pass' else 'fail'
def agents_status(path:str|None)->str:
    if not path: return 'unknown'
    p=Path(path)
    if (p/'AGENTS.md').exists(): return 'present'
    return 'missing' if p.exists() else 'unknown'
def project_info(path:str|None)->str|None:
    if not path: return None
    p=Path(path)
    for rel in ('AGENTS.md','README.md','docs/project-info.md'):
        if (p/rel).exists(): return (p/rel).as_posix()
    return None
def route_row(route:dict[str,Any])->dict[str,Any]:
    access=str(route.get('access') or 'read_only')
    status=access if access in {'read_only','candidate','write_scoped','blocked','manual_review'} else 'unknown'
    path=str(route.get('worktree_path') or '') or None
    topics=[str(x) for x in route.get('authority_topics',[])]
    mapped=all(t in authority_topics() for t in topics) if topics else access!='write_scoped'
    allowed=[str(x) for x in route.get('allowed_write_scope') or route.get('allowed_write_paths') or []]
    h=hook_status(route)
    blockers=[]
    if status=='write_scoped':
        if not path: blockers.append('missing worktree')
        if agents_status(path)!='present': blockers.append('missing AGENTS.md')
        if h!='pass': blockers.append('missing hook proof')
        if not mapped: blockers.append('authority topic missing')
        if not allowed: blockers.append('allowed write paths missing')
    return {'repo':str(route.get('repo') or route.get('name') or route.get('repo_id') or 'unknown'),'worktree_path':path,'governance_status':'blocked' if blockers else status,'agents_status':agents_status(path),'hook_proof_status':h,'authority_topic_status':'mapped' if mapped and topics else ('not_required' if not topics else 'missing'),'project_info_location':project_info(path),'allowed_write_paths':allowed,'closeout_policy':str(route.get('closeout_policy') or ('bears_doctor_validate_closeout' if status=='write_scoped' else 'read_only_evidence_only')),'reason':'; '.join(blockers) if blockers else ('write scope proof complete' if status=='write_scoped' else 'non-plugin repositories remain read-only until proof exists')}
def inventory()->dict[str,Any]:
    rows=[]; seen=set()
    for r in catalog_routes():
        row=route_row(r); key=row['repo']
        if key in seen: continue
        seen.add(key); rows.append(row)
    pkt={'schema':'bears-repo-onboarding-inventory.v1','version':'1','generated_at':now(),'status':'pass','repositories':rows,'errors':[]}
    pkt['errors'].extend(validate_json_schema(pkt,SCHEMA,'repo-onboarding-inventory'))
    pkt['status']='pass' if not pkt['errors'] else 'blocked'
    return pkt
def validate_all()->list[str]:
    errors=[]; pol=load(POLICY); cat=load(AUTOSTART); rp=cat.get('routing_policy',{})
    for state in ['read_only','candidate','write_scoped','blocked','manual_review']:
        if state not in pol.get('governance_states',[]): errors.append(f'missing governance state: {state}')
    if not rp.get('governed_repositories'): errors.append('routing_policy.governed_repositories missing')
    rows=inventory()['repositories']
    if not any(r['governance_status']=='write_scoped' for r in rows): errors.append('no write_scoped repository')
    if not any(r['governance_status']=='read_only' and r['repo']!='BearsCLOUD/bears-codex-workflow-plugin' for r in rows): errors.append('no non-plugin read_only repository')
    return errors
def doctor()->dict[str,Any]:
    errs=validate_all(); inv=inventory()
    counts={}
    for r in inv['repositories']: counts[r['governance_status']]=counts.get(r['governance_status'],0)+1
    return {'schema':'bears-repo-onboarding-doctor.v1','status':'pass' if not errs else 'fail','counts':counts,'inventory_evidence':'runtime/repo-onboarding/repo-onboarding-inventory.v1.json','errors':errs}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    i=sub.add_parser('inventory'); i.add_argument('--json',action='store_true'); i.add_argument('--write')
    v=sub.add_parser('validate'); v.add_argument('--json',action='store_true')
    d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='inventory':
        pkt=inventory()
        if a.write:
            out=PLUGIN_ROOT/a.write if not Path(a.write).is_absolute() else Path(a.write); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(pkt,indent=2,sort_keys=True)+'\n')
        print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    if a.cmd=='validate':
        errs=validate_all(); pkt={'schema':'bears-repo-onboarding-validation.v1','status':'pass' if not errs else 'fail','errors':errs}; print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if not errs else 1
    if a.cmd=='doctor': pkt=doctor(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
