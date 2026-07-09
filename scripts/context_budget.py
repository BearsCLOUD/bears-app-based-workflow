#!/usr/bin/env python3
"""Measure Bears skills, role profiles, and durable context surfaces."""
from __future__ import annotations
import argparse, glob, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
POLICY=PLUGIN_ROOT/'assets/catalog/context-budget-policy.v1.json'
SURFACE_SCHEMA=PLUGIN_ROOT/'assets/schemas/context-surface.v1.schema.json'
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def policy()->dict[str,Any]: return load(POLICY)
def estimate_tokens(text:str)->int: return max(1,(len(text)+3)//4) if text else 0
def surface_type(path:str)->str:
    if path.endswith('/SKILL.md') or '/skills/' in path: return 'skill'
    if path.startswith('agents/') and path.endswith('.toml'): return 'agent_role_profile'
    if path.endswith('AGENTS.md'): return 'AGENTS.md'
    if path.startswith('docs/runbooks/'): return 'runbook'
    if path.startswith('docs/'): return 'reference_doc'
    if path.startswith('assets/catalog/'): return 'catalog'
    if path.startswith('assets/schemas/'): return 'schema'
    return 'reference_doc'
def surface(path:Path)->dict[str,Any]:
    rel=str(path.relative_to(PLUGIN_ROOT)) if path.is_absolute() and path.is_relative_to(PLUGIN_ROOT) else str(path)
    full=PLUGIN_ROOT/rel if not path.is_absolute() else path
    text=full.read_text(encoding='utf-8') if full.exists() else ''
    tokens=estimate_tokens(text); sections=sum(1 for line in text.splitlines() if line.lstrip().startswith('#')) or 1
    pol=policy(); hard=pol.get('hard_token_limit',6000); default=pol.get('default_token_limit',3000)
    split='split_required' if tokens>hard else ('index_required' if tokens>default else 'ok')
    load='shard_only' if split=='split_required' else ('on_demand' if tokens>default else 'on_demand')
    return {'schema':'bears-context-surface.v1','surface_id':rel.replace('/','_').replace('.','_'),'path':rel,'surface_type':surface_type(rel),'char_count':len(text),'estimated_tokens':tokens,'sections':sections,'required_by_default':False,'load_policy':load,'split_policy':split,'canonical_owner':'bears-machine-first-execution-kernel-engineer','validator':'scripts/context_budget.py surface --path <path> --json'}
def list_paths()->list[Path]:
    paths=[]
    for pat in policy().get('surface_globs',[]): paths += [Path(p) for p in glob.glob(str(PLUGIN_ROOT/pat), recursive=True)]
    return sorted(set(p for p in paths if p.is_file()))
def scan()->dict[str,Any]:
    surfaces=[surface(p) for p in list_paths()]
    errors=[]
    for s in surfaces: errors += [f'{s["path"]}: {e}' for e in validate_json_schema(s,SURFACE_SCHEMA,s['path'])]
    oversized=[s for s in surfaces if s['split_policy']!='ok']
    return {'schema':'bears-context-budget-scan.v1','status':'blocked' if any(s['split_policy']=='split_required' and s['required_by_default'] for s in surfaces) else 'pass','surface_count':len(surfaces),'surfaces':surfaces,'oversized_surfaces':oversized[:50],'errors':errors}
def validate_all()->list[str]:
    errors=[]; pol=policy(); req={'scripts/context_budget.py scan --json','scripts/context_budget.py validate','scripts/context_budget.py surface --path <path> --json','scripts/skill_surface.py split-decision --path <path> --json','scripts/skill_surface.py doctor --json'}
    errors += [f'missing command: {x}' for x in sorted(req-set(pol.get('commands',[])))]
    if set(pol.get('surface_types',[])) != {'skill','agent_role_profile','developer_instructions','AGENTS.md','reference_doc','runbook','catalog','schema'}: errors.append('surface_types mismatch')
    pkt=scan(); errors += pkt.get('errors',[])
    return errors
def select_sections(path:Path, max_tokens:int=1200)->dict[str,Any]:
    text=path.read_text(encoding='utf-8'); lines=text.splitlines(); chunks=[]; cur=[]; title='intro'
    for line in lines:
        if line.startswith('#') and cur:
            chunks.append((title,'\n'.join(cur))); title=line.strip('# ').strip() or 'section'; cur=[line]
        else: cur.append(line)
    if cur: chunks.append((title,'\n'.join(cur)))
    selected=[]; used=0
    for title,body in chunks:
        t=estimate_tokens(body)
        if used+t<=max_tokens: selected.append({'title':title,'estimated_tokens':t}); used+=t
    return {'schema':'bears-bounded-section-selection.v1','status':'pass','path':str(path),'max_tokens':max_tokens,'selected_sections':selected,'estimated_tokens':used}
def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    sc=sub.add_parser('scan'); sc.add_argument('--json',action='store_true')
    v=sub.add_parser('validate')
    sf=sub.add_parser('surface'); sf.add_argument('--path',required=True); sf.add_argument('--json',action='store_true')
    ss=sub.add_parser('select-sections'); ss.add_argument('--path',required=True); ss.add_argument('--max-tokens',type=int,default=1200); ss.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if a.cmd=='scan': pkt=scan(); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0 if pkt['status']=='pass' else 1
    if a.cmd=='validate': errs=validate_all(); print(json.dumps({'schema':'bears-context-budget-validation.v1','status':'pass' if not errs else 'fail','errors':errs},indent=2,sort_keys=True)); return 0 if not errs else 1
    if a.cmd=='surface': pkt=surface(Path(a.path)); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['split_policy']); return 0
    if a.cmd=='select-sections': pkt=select_sections(Path(a.path),a.max_tokens); print(json.dumps(pkt,indent=2,sort_keys=True) if a.json else pkt['status']); return 0
    return 2
if __name__=='__main__': raise SystemExit(main())
