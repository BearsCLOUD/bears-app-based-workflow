#!/usr/bin/env python3
"""Validate and execute deterministic Bears question operators."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
PLUGIN_ROOT=Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path: sys.path.insert(0,str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import formal_semantics
CALC=PLUGIN_ROOT/'assets/catalog/question-calculus.v1.json'
BANK=PLUGIN_ROOT/'assets/catalog/question-bank.v1.json'
OP_SCHEMA=PLUGIN_ROOT/'assets/schemas/question-operator.v1.schema.json'
PROOF_SCHEMA=PLUGIN_ROOT/'assets/schemas/question-answer-proof.v1.schema.json'
REQUIRED_OPERATORS={'resolve_source_of_truth','classify_task_type','find_smallest_verifiable_goal','infer_required_research','infer_required_plan','select_semantic_context','select_role_profile','select_executor','select_model_tier','select_mcp_policy','select_file_scope','select_validation_gate','select_closeout_gate','select_roadmap_update','select_self_improvement_action'}

def load(path:Path)->Any:
 with path.open(encoding='utf-8') as f: return json.load(f)

def catalog()->dict[str,Any]: return load(CALC)
def operators()->dict[str,dict[str,Any]]: return {o.get('operator_id',''):o for o in catalog().get('operators',[]) if isinstance(o,dict)}

def validate_all()->list[str]:
 errs=[]; cat=catalog(); ops=operators()
 if cat.get('schema')!='bears-question-calculus.v1': errs.append('question-calculus schema mismatch')
 if set(ops)!=REQUIRED_OPERATORS: errs.append('question-calculus operators must equal required #437 operator set')
 for i,o in enumerate(cat.get('operators',[])):
  errs.extend(validate_json_schema(o,OP_SCHEMA,f'question-calculus.operators[{i}]'))
  for ref in o.get('semantic_fact_refs',[]):
   q=formal_semantics.query_fact(ref)
   if not q.get('accepted'): errs.append(f'operator {o.get("operator_id")} references non-accepted semantic fact {ref}')
 for i,p in enumerate(cat.get('accepted_answer_proofs',[])):
  r=prove_answer(p)
  if r['status']!='pass': errs.append(f'accepted_answer_proofs[{i}] invalid: '+'; '.join(r['errors']))
 if not BANK.exists(): errs.append('question-bank catalog missing')
 else:
  bank=load(BANK)
  if bank.get('schema')!='bears-question-bank.v1': errs.append('question-bank schema mismatch')
 return sorted(set(errs))

def _operator(id:str)->dict[str,Any]|None: return operators().get(id)

def ask(operator_id:str, input_packet:dict[str,Any])->dict[str,Any]:
 op=_operator(operator_id)
 if not op: return {'schema':'bears-question-answer.v1','status':'blocked','operator_id':operator_id,'errors':[f'unknown operator: {operator_id}']}
 answer=str(input_packet.get('answer',''))
 if not answer:
  if operator_id=='select_executor' and len(input_packet.get('executor_candidates',[]))!=1: answer='manual_review'
  elif operator_id=='infer_required_research' and input_packet.get('risk')=='high': answer='research_required'
  else: answer=op['allowed_answers'][0]
 answer_type='manual_review' if answer=='manual_review' else 'research_required' if answer=='research_required' else 'execution'
 blocked=[] if answer_type=='execution' else ['execution_allowed']
 unlocked=list(op.get('unlocks',[])) if answer_type=='execution' else []
 return {'schema':'bears-question-answer.v1','status':'pass','operator_id':operator_id,'answer':answer,'answer_type':answer_type,'unlocked_gates':unlocked,'blocked_gates':blocked,'errors':[]}

def prove_answer(packet:dict[str,Any])->dict[str,Any]:
 errors=[]
 errors.extend(validate_json_schema(packet,PROOF_SCHEMA,'question-answer-proof'))
 op=_operator(str(packet.get('operator_id')))
 if not op: errors.append(f"unknown operator: {packet.get('operator_id')}")
 else:
  if packet.get('answer') not in op.get('allowed_answers',[]): errors.append(f"answer not allowed for operator: {packet.get('answer')}")
  missing=sorted(set(op.get('required_evidence_types',[]))-set(packet.get('evidence_types',[])))
  if missing: errors.append('missing required evidence types: '+','.join(missing))
 answer_type=packet.get('answer_type')
 if packet.get('answer') in {'manual_review','research_required'} and answer_type=='execution': errors.append('ambiguous answer cannot have execution answer_type')
 for ref in packet.get('semantic_fact_refs',[]):
  q=formal_semantics.query_fact(ref)
  if not q.get('accepted'): errors.append(f'semantic fact is not accepted: {ref}')
 accepted=packet.get('status')=='accepted' and not errors
 if packet.get('unlocked_gates') and not accepted: errors.append('gate unlock requires accepted answer proof')
 if answer_type in {'manual_review','research_required'} and packet.get('unlocked_gates'):
  errors.append('manual_review or research_required answer cannot unlock execution gates')
 if packet.get('answer')=='manual_review' and 'execution_allowed' not in packet.get('blocked_gates',[]):
  errors.append('manual_review answer must block execution_allowed')
 return {'schema':'bears-question-answer-proof-result.v1','status':'pass' if not errors else 'blocked','proof_id':packet.get('proof_id'),'accepted':accepted,'unlocked_gates':packet.get('unlocked_gates',[]) if accepted else [],'blocked_gates':packet.get('blocked_gates',[]),'errors':errors}

def doctor()->dict[str,Any]:
 errs=validate_all(); cat=catalog()
 return {'schema':'bears-question-calculus-doctor.v1','status':'pass' if not errs else 'fail','decision_graph_coverage':'pass' if not errs else 'fail','operator_count':len(cat.get('operators',[])),'accepted_answer_proofs':len(cat.get('accepted_answer_proofs',[])),'errors':errs}

def print_json(p): print(json.dumps(p,indent=2,sort_keys=True))
def main(argv=None):
 ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
 v=sub.add_parser('validate'); v.add_argument('--json',action='store_true')
 a=sub.add_parser('ask'); a.add_argument('--operator',required=True); a.add_argument('--input',required=True); a.add_argument('--json',action='store_true')
 pr=sub.add_parser('prove-answer'); pr.add_argument('--packet',required=True); pr.add_argument('--json',action='store_true')
 d=sub.add_parser('doctor'); d.add_argument('--json',action='store_true')
 args=ap.parse_args(argv)
 if args.cmd=='validate':
  e=validate_all(); p={'schema':'bears-question-calculus-validate-result.v1','status':'pass' if not e else 'fail','errors':e}; print_json(p) if args.json else print(p['status']); return 0 if not e else 1
 if args.cmd=='ask':
  p=ask(args.operator, load(Path(args.input))); print_json(p) if args.json else print(p['status']); return 0 if p['status']=='pass' else 1
 if args.cmd=='prove-answer':
  p=prove_answer(load(Path(args.packet))); print_json(p) if args.json else print(p['status']); return 0 if p['status']=='pass' else 1
 if args.cmd=='doctor':
  p=doctor(); print_json(p) if args.json else print(p['status']); return 0 if p['status']=='pass' else 1
 return 2
if __name__=='__main__': raise SystemExit(main())
