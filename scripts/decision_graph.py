#!/usr/bin/env python3
"""Build and validate Bears decision graphs from accepted question proofs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import question_calculus, formal_semantics
BANK=PLUGIN_ROOT/'assets/catalog/question-bank.v1.json'
GRAPH_SCHEMA=PLUGIN_ROOT/'assets/schemas/decision-graph.v1.schema.json'

def load(path:Path)->Any:
 with path.open(encoding='utf-8') as f: return json.load(f)

def build_graph(goal_id:str)->dict[str,Any]:
 bank=load(BANK); graph=dict(bank['decision_graph_template']); graph['goal_id']=goal_id
 return graph

def normalize_graph(graph:dict[str,Any])->dict[str,Any]:
 return {k:v for k,v in graph.items() if k not in {'status','errors'}}

def validate_graph(graph:dict[str,Any])->list[str]:
 graph=normalize_graph(graph)
 errs=validate_json_schema(graph,GRAPH_SCHEMA,'decision-graph')
 if not graph.get('semantic_fact_refs'): errs.append('decision graph must reference semantic facts from #435')
 for ref in graph.get('semantic_fact_refs',[]):
  if not formal_semantics.query_fact(ref).get('accepted'): errs.append(f'decision graph semantic fact is not accepted: {ref}')
 proofs={p['proof_id']:p for p in question_calculus.catalog().get('accepted_answer_proofs',[])}
 for node in graph.get('nodes',[]):
  proof=proofs.get(node.get('proof_id'))
  if not proof: errs.append(f"node {node.get('node_id')} missing accepted proof")
  else:
   result=question_calculus.prove_answer(proof)
   if result['status']!='pass': errs.append(f"node {node.get('node_id')} proof invalid")
 unlocked=set(graph.get('unlocked_gates',[]))
 for gate in unlocked:
  if not any(gate in proofs.get(node.get('proof_id'),{}).get('unlocked_gates',[]) for node in graph.get('nodes',[])):
   errs.append(f'gate lacks accepted proof: {gate}')
 return sorted(set(errs))

def check_gate(goal_id:str, gate:str, graph_path:str|None=None)->dict[str,Any]:
 if graph_path:
  graph=normalize_graph(load(Path(graph_path)))
 else:
  graph=build_graph(goal_id)
 errs=validate_graph(graph)
 if gate in graph.get('unlocked_gates',[]) and not errs:
  status='pass'; allowed=True
 elif gate in graph.get('blocked_gates',[]):
  status='blocked'; allowed=False; errs.append(f'gate is blocked: {gate}')
 else:
  status='blocked'; allowed=False; errs.append(f'gate is not unlocked: {gate}')
 return {'schema':'bears-decision-graph-gate-result.v1','status':status,'goal_id':goal_id,'gate':gate,'unlocked':allowed,'errors':errs}

def doctor()->dict[str,Any]:
 graph=build_graph('doctor')
 errs=question_calculus.validate_all()+validate_graph(graph)
 return {'schema':'bears-decision-graph-doctor.v1','status':'pass' if not errs else 'fail','decision_graph_coverage':'pass' if not errs else 'fail','nodes':len(graph.get('nodes',[])),'unlocked_gates':len(graph.get('unlocked_gates',[])),'blocked_gates':len(graph.get('blocked_gates',[])),'errors':errs}

def print_json(p): print(json.dumps(p,indent=2,sort_keys=True))
def main(argv=None):
 ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
 b=sub.add_parser('build'); b.add_argument('--goal-id',required=True); b.add_argument('--json',action='store_true')
 c=sub.add_parser('check-gate'); c.add_argument('--goal-id',required=True); c.add_argument('--gate',required=True); c.add_argument('--graph'); c.add_argument('--json',action='store_true')
 d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
 v=sub.add_parser('validate'); v.add_argument('--json',action='store_true')
 args=ap.parse_args(argv)
 if args.cmd=='build':
  g=build_graph(args.goal_id); e=validate_graph(g); g['status']='pass' if not e else 'fail'; g['errors']=e; print_json(g) if args.json else print(g['status']); return 0 if not e else 1
 if args.cmd=='check-gate':
  p=check_gate(args.goal_id,args.gate,args.graph); print_json(p) if args.json else print(p['status']); return 0 if p['status']=='pass' else 1
 if args.cmd=='doctor':
  p=doctor(); print_json(p) if args.json else print(p['status']); return 0 if p['status']=='pass' else 1
 if args.cmd=='validate':
  p=doctor(); print_json(p) if args.json else print(p['status']); return 0 if p['status']=='pass' else 1
 return 2
if __name__=='__main__': raise SystemExit(main())
