#!/usr/bin/env python3
"""Mine compact Bears workflow traces against a bounded formal model."""
from __future__ import annotations
import argparse, glob, hashlib, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
POLICY=PLUGIN_ROOT/'assets/catalog/process-mining-policy.v1.json'
EVENT_SCHEMA=PLUGIN_ROOT/'assets/schemas/process-trace-event.v1.schema.json'
REPORT_SCHEMA=PLUGIN_ROOT/'assets/schemas/process-mining-report.v1.schema.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
FORBIDDEN=('raw prompt','raw chat','raw log','BEGIN PRIVATE KEY','credential=','.env=','production data')
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def policy()->dict[str,Any]: return load(POLICY)
def forbidden(v:Any)->bool: return any(x in json.dumps(v,ensure_ascii=False).casefold() for x in [m.casefold() for m in FORBIDDEN])
def normalize(raw:dict[str,Any], source:str)->dict[str,Any]:
    from_state=str(raw.get('from_state') or raw.get('from') or raw.get('previous_state') or 'unknown')
    to_state=str(raw.get('to_state') or raw.get('to') or raw.get('state') or raw.get('status') or 'unknown')
    transition=str(raw.get('transition') or f'{from_state}->{to_state}')
    status=str(raw.get('status') or ('fail' if raw.get('error_class') else 'pass'))
    if status not in {'pass','fail','warning','blocked'}: status='warning'
    stable=json.dumps({'source':source,'raw_id':raw.get('event_id') or raw.get('id'), 'transition':transition},sort_keys=True)
    return {'schema':'bears-process-trace-event.v1','event_id':str(raw.get('event_id') or raw.get('id') or hashlib.sha1(stable.encode()).hexdigest()[:16]),'delivery_id':raw.get('delivery_id'),'issue':raw.get('issue'),'source_path':source,'timestamp':raw.get('timestamp') or raw.get('created_at'),'from_state':from_state,'to_state':to_state,'transition':transition,'status':status,'role_id':raw.get('role_id'),'error_class':raw.get('error_class'),'estimated_tokens':int(raw.get('estimated_tokens') or raw.get('total_estimated_tokens') or raw.get('input_estimated_tokens') or 0),'evidence_paths':[source]}
def read_jsonish(path:Path)->list[dict[str,Any]]:
    try: text=path.read_text(encoding='utf-8')
    except UnicodeDecodeError: return []
    rows=[]
    if path.suffix=='.jsonl':
        for line in text.splitlines():
            if line.strip():
                try:
                    obj=json.loads(line); rows.append(obj) if isinstance(obj,dict) else None
                except Exception: pass
    else:
        try:
            obj=json.loads(text)
            if isinstance(obj,dict): rows=[obj]
            elif isinstance(obj,list): rows=[x for x in obj if isinstance(x,dict)]
        except Exception: pass
    return rows
def expand_patterns(patterns:list[str])->list[Path]:
    out=[]; max_files=int(policy().get('max_event_files',200))
    for pat in patterns:
        p=PLUGIN_ROOT/pat if not Path(pat).is_absolute() else Path(pat)
        matches=[Path(x) for x in glob.glob(str(p),recursive=True)]
        if p.exists(): matches.append(p)
        for m in matches:
            if m.is_dir(): out.extend(sorted(m.rglob('*.json'))+sorted(m.rglob('*.jsonl')))
            elif m.suffix in {'.json','.jsonl'}: out.append(m)
            if len(out)>=max_files: break
        if len(out)>=max_files: break
    return sorted(set(out))[:max_files]
def ingest(patterns:list[str])->dict[str,Any]:
    events=[]; errors=[]; max_events=int(policy().get('max_events',2000))
    for path in expand_patterns(patterns):
        rel=path.relative_to(PLUGIN_ROOT).as_posix() if path.is_relative_to(PLUGIN_ROOT) else str(path)
        for raw in read_jsonish(path):
            evt=normalize(raw,rel)
            errs=validate_json_schema(evt,EVENT_SCHEMA,'process-trace-event')
            if forbidden(raw): errs.append('source contains forbidden raw data marker')
            if errs: errors.extend(errs[:3]); continue
            events.append(evt)
            if len(events)>=max_events: break
        if len(events)>=max_events: break
    return {'schema':'bears-process-trace-ingest.v1','status':'pass' if not errors else 'warning','event_count':len(events),'events':events,'errors':errors[:20]}
def model_transitions(model_path:Path)->set[str]:
    data=load(model_path) if model_path.exists() else policy()
    vals=data.get('allowed_transitions') or data.get('transitions') or policy().get('allowed_transitions',[])
    out=set()
    for v in vals:
        if isinstance(v,str): out.add(v)
        elif isinstance(v,dict): out.add(f"{v.get('from_state') or v.get('from')}->{v.get('to_state') or v.get('to')}")
    return out
def finding(ftype:str, severity:str, nodes:list[str], paths:list[str], summary:str)->dict[str,Any]:
    fid='pm-'+hashlib.sha1(json.dumps([ftype,nodes,paths,summary],sort_keys=True).encode()).hexdigest()[:12]
    return {'finding_id':fid,'finding_type':ftype,'severity':severity,'affected_nodes':nodes,'evidence_paths':paths[:10],'summary':summary}
def compare(model_path:Path, events_path:Path)->dict[str,Any]:
    data=load(events_path); rows=data.get('events',data if isinstance(data,list) else [])
    allowed=model_transitions(model_path); findings=[]; errors=[]
    for e in rows:
        errs=validate_json_schema(e,EVENT_SCHEMA,'process-trace-event')
        if errs: errors.extend(errs[:2]); continue
        if e['transition'] not in allowed:
            findings.append(finding('non_fitting_trace','warning',[e['from_state'],e['to_state']],e['evidence_paths'],f"transition {e['transition']} is not in workflow model"))
    failures={}; costs={}
    for e in rows:
        key=e.get('error_class') or e.get('transition')
        if e.get('status') in {'fail','blocked'} or e.get('error_class')=='validation_failure': failures.setdefault(key,[]).append(e)
        if int(e.get('estimated_tokens',0))>=int(policy().get('high_context_token_threshold',12000)): costs.setdefault(e.get('transition','unknown'),[]).append(e)
    for key, vals in failures.items():
        if len(vals)>=int(policy().get('repeated_failure_threshold',2)):
            findings.append(finding('validator_gap','candidate',[str(key)],[p for v in vals for p in v.get('evidence_paths',[])],f"repeated validation failure class {key}"))
    for key, vals in costs.items():
        findings.append(finding('context_budget_candidate','candidate',[str(key)],[p for v in vals for p in v.get('evidence_paths',[])],f"high context cost on branch {key}"))
    pkt={'schema':'bears-process-mining-report.v1','model_path':str(model_path),'event_count':len(rows),'finding_count':len(findings),'findings':findings,'errors':errors[:20]}
    pkt['errors'].extend(validate_json_schema(pkt,REPORT_SCHEMA,'process-mining-report'))
    return pkt
def validate_all()->list[str]:
    pol=policy(); req={'scripts/process_mining.py validate','scripts/process_mining.py ingest --paths <glob> --json','scripts/process_mining.py compare --model <path> --events <path> --json','scripts/workflow_improvement_candidates.py generate --report <path> --json','scripts/workflow_improvement_candidates.py create-issues --candidates <path> --dry-run --json','scripts/process_mining.py doctor --json'}
    errors=[f'missing command: {x}' for x in sorted(req-set(pol.get('commands',[])))]
    for p in (EVENT_SCHEMA,REPORT_SCHEMA,PLUGIN_ROOT/'assets/schemas/workflow-improvement-candidate.v1.schema.json'):
        if not p.exists(): errors.append(f'missing schema: {p.name}')
    return errors
def doctor()->dict[str,Any]:
    errs=validate_all(); return {'schema':'bears-process-mining-doctor.v1','status':'pass' if not errs else 'fail','errors':errs,'summary':'process mining contracts validate' if not errs else 'process mining contract errors'}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    v=sub.add_parser('validate'); v.add_argument('--json',action='store_true')
    ing=sub.add_parser('ingest'); ing.add_argument('--paths',nargs='+',required=True); ing.add_argument('--json',action='store_true')
    cmp=sub.add_parser('compare'); cmp.add_argument('--model',required=True); cmp.add_argument('--events',required=True); cmp.add_argument('--json',action='store_true')
    d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='validate': errs=validate_all(); pkt={'schema':'bears-process-mining-validation.v1','status':'pass' if not errs else 'fail','errors':errs}; print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if not errs else 1
    if a.cmd=='ingest': pkt=ingest(a.paths); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    if a.cmd=='compare': pkt=compare(Path(a.model),Path(a.events)); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['finding_count']); return 0 if not pkt['errors'] else 1
    if a.cmd=='doctor': pkt=doctor(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    return 2
if __name__=='__main__': raise SystemExit(main())
