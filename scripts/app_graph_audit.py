"""Whole-branch semantic and exact-run process audits for compiled app graphs."""

from __future__ import annotations

from collections import defaultdict, deque
import json
from typing import Any

from app_graph_store import GraphError, QueryBounds, canonical, cursor_decode, cursor_encode, digest_bytes


def finding(kind: str, route: str, subject: str, **extra: Any) -> dict[str, Any]:
    return {"ref":f"{kind}:{subject}","kind":kind.lower(),"subject_ref":subject,"route":route,**extra}


def route(findings: list[dict[str, Any]]) -> str:
    routes = {x.get("route") for x in findings}
    return next((x for x in ("blocked","needs-research","needs-spec","needs-graph","needs-plan","needs-evidence") if x in routes), "needs-plan")


def bounded(result: dict[str, Any], bounds: QueryBounds, selector: dict[str, Any]) -> dict[str, Any]:
    query = "audit:" + json.dumps({"schema":result["schema"],**selector}, sort_keys=True, separators=(",",":")); offset = cursor_decode(bounds.cursor,result["build_ref"],query)
    findings = result["findings"]; page = findings[offset:offset+bounds.limit]; next_offset = offset + len(page); truncated = next_offset < len(findings)
    return {**result,"findings":page,"truncated":truncated,"next_cursor":cursor_encode(result["build_ref"],query,next_offset) if truncated else None,"complete":result["complete"] and not truncated}


def process_audit(store: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    bounds = QueryBounds.from_args(arguments); run_ref = arguments.get("run_ref")
    if not isinstance(run_ref, str) or not run_ref: raise GraphError("QUERY_INVALID", "process_audit requires exact run_ref")
    events = {x["event_ref"]:x for x in store.process.get("events",[]) if x.get("run_ref") == run_ref}
    if not events: raise GraphError("QUERY_INVALID", "run_ref does not identify a compiled run")
    findings = []; starts = [x for x in events.values() if x.get("event_kind") == "run-start"]
    if len(starts) != 1: findings.append(finding("RUN-SCOPE","needs-plan",run_ref))
    scope = starts[0] if starts else {"task_refs":[]}; tasks = set(scope.get("task_refs",[]))
    results = {x.get("task_ref") for x in events.values() if x.get("event_kind") == "task-result" and x.get("terminal_result") in {"done","failed","blocked"}}
    if results != tasks: findings.append(finding("TASK-RESULTS","needs-plan",run_ref,missing_task_refs=sorted(tasks-results)))
    reviews = [x for x in events.values() if x.get("event_kind") == "review" and set(x.get("reviewed_task_refs",[])) == tasks and x.get("commit_range")]
    if not reviews: findings.append(finding("REVIEW-COVERAGE","needs-plan",run_ref))
    remediation_runs = {x.get("remediates_run_ref") for x in store.process.get("events",[]) if x.get("event_kind") == "run-start"}
    for review in reviews:
        if review.get("finding_refs") and run_ref not in remediation_runs: findings.append(finding("REMEDIATION-RUN","needs-plan",review["event_ref"]))
    terminal = arguments.get("terminal") is True; candidates = [x for x in events.values() if x.get("status") == "audited"]
    if terminal and not candidates: findings.append(finding("TERMINAL-MISSING","needs-evidence",run_ref))
    for candidate in candidates:
        required = (candidate.get("build_ref") == store.build["build_ref"] and candidate.get("source_snapshot_digest") == store.build["source_snapshot_digest"] and candidate.get("journal_digest") == store.build["journal_digest"] and candidate.get("audit_receipt_ref"))
        if not required: findings.append(finding("TERMINAL-REFS","needs-plan",candidate["event_ref"]))
        if candidate.get("automation_status") == "not_run": findings.append(finding("ACCEPTANCE-NOT-RUN","needs-evidence",candidate["event_ref"]))
    complete = not findings and (not terminal or bool(candidates))
    result = {"schema":"app-process-audit-result.v1","profile":"terminal" if terminal else "handoff","run_ref":run_ref,"complete":complete,"build_ref":store.build["build_ref"],"journal_digest":store.build["journal_digest"],"candidate_final_event_refs":sorted(x["event_ref"] for x in candidates),"open_remediation_task_refs":[],"findings":findings,"route":"none" if complete else route(findings)}
    return bounded(result,bounds,{"run_ref":run_ref,"terminal":terminal})


def trace_audit(store: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    bounds = QueryBounds.from_args(arguments); profile = arguments.get("profile","semantic")
    if profile not in {"semantic","planning","convergence"}: raise GraphError("QUERY_INVALID", "unknown trace audit profile")
    adjacency: dict[tuple[str,str],set[str]] = defaultdict(set)
    for edge in store.edges:
        if edge.get("active",True): adjacency[(edge["from_ref"],edge["kind"])].add(edge["to_ref"])
    findings=[]; replaced={x.get("old_ref") for x in store.trace.get("replacements",[])}
    steps=[("defines",{"functionality","behavior"},"requirement-to-functionality"),("decomposes_to",{"task"},"functionality-to-task"),("implemented_by",{"code"},"task-to-code"),("verified_by",{"test"},"code-to-test"),("evidenced_by",{"evidence"},"test-to-evidence")]
    end={"semantic":1,"planning":2,"convergence":5}[profile]
    for req, entity in sorted(store.entities.items()):
        if entity["kind"] != "requirement" or not entity.get("active",True) or req in replaced: continue
        decisions={source for (source,kind),targets in adjacency.items() if kind=="defines" and req in targets and store.entities.get(source,{}).get("kind")=="decision"}
        specs={source for (source,kind),targets in adjacency.items() if kind=="defines" and targets.intersection(decisions) and store.entities.get(source,{}).get("kind")=="spec"}
        if not decisions: findings.append(finding("TRACE-GAP","needs-spec",req,missing_segment="decision-to-requirement")); continue
        if not specs: findings.append(finding("TRACE-GAP","needs-research",req,missing_segment="spec-to-decision")); continue
        states={req}
        for edge_kind,kinds,label in steps[:end]:
            next_states={target for state in states for target in adjacency.get((state,edge_kind),set()) if store.entities.get(target,{}).get("kind") in kinds and store.entities[target].get("active",True)}
            if not next_states: findings.append(finding("TRACE-GAP","needs-graph" if profile=="semantic" else "needs-plan",req,missing_segment=label,branch_ref=sorted(states)[0])); break
            # Audit every active branch independently so one good branch cannot hide another.
            for state in states:
                if not any(target in next_states for target in adjacency.get((state,edge_kind),set())): findings.append(finding("TRACE-BRANCH-GAP","needs-plan",state,missing_segment=label,requirement_ref=req))
            states=next_states
    complete=not findings; result={"schema":"app-trace-audit-result.v1","profile":profile,"complete":complete,"build_ref":store.build["build_ref"],"source_snapshot_digest":store.build["source_snapshot_digest"],"findings":findings,"route":"none" if complete else route(findings)}
    return bounded(result,bounds,{"profile":profile})
