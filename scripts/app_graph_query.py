"""Build-bound bounded graph queries with typed edge metadata and query caching."""

from __future__ import annotations

from collections import defaultdict
import copy
import json
from typing import Any

from app_graph_store import *


class GraphStore:
    """Bound read view; every query is tied to one immutable build receipt."""

    def __init__(self, root: RepoRoot, trace: dict[str, Any], process: dict[str, Any], build: dict[str, Any], workflow: dict[str, Any], ledger: dict[str, Any]) -> None:
        self.root, self.trace, self.process, self.build, self.workflow, self.ledger = root, trace, process, build, workflow, ledger
        self.entities = {x["ref"]:x for x in trace.get("entities",[])}; self.edges = list(trace.get("edges",[]))

    @classmethod
    def load(cls, arguments: dict[str, Any]) -> "GraphStore":
        root = safe_root(arguments.get("app_root"))
        try:
            source_manifest = manifest(root)
            pointer, _ = read_json(root, CURRENT_BUILD_PATH, max_bytes=262144)
            receipt_ref = validate_current_pointer(pointer)
            build, _ = read_json(root, receipt_ref, max_bytes=262144)
            trace, _ = read_json(root, TRACE_PATH)
            process, _ = read_json(root, PROCESS_PATH)
            workflow, workflow_raw = read_json(root, source_manifest["sources"]["workflow"])
            ledger, _ = read_json(root, source_manifest["sources"]["task_ledger"])
            validate_build_bundle(pointer, build, trace, process)
            if workflow.get("schema") != "app-workflow-definition.v3" or ledger.get("schema") != "app-task-ledger.v3":
                raise GraphError("SCHEMA_UNSUPPORTED", "bound workflow or ledger is unsupported")
            if (
                process.get("workflow_definition_ref") != source_manifest["sources"]["workflow"]
                or process.get("workflow_definition_digest") != digest_bytes(workflow_raw)
            ):
                raise GraphError("SOURCE_DRIFT", "workflow binding disagrees with the process index")
            _, locators, snapshot = source_snapshot(root, source_manifest["sources"])
            if snapshot != build["source_snapshot_digest"] or locators != trace.get("generated_from"):
                raise GraphError("SOURCE_DRIFT", "source drift requires compile")
            expected = arguments.get("expected_build_ref")
            if expected is not None and not valid_build_ref(expected):
                raise GraphError("QUERY_INVALID", "expected build ref is invalid")
            if expected not in (None, build["build_ref"]):
                raise GraphError("SOURCE_DRIFT", "expected build is stale")
            return cls(root, trace, process, build, workflow, ledger)
        except Exception:
            root.close()
            raise

    def close(self) -> None: self.root.close()

    def _page(self, items: list[Any], bounds: QueryBounds, query: str) -> dict[str, Any]:
        offset=cursor_decode(bounds.cursor,self.build["build_ref"],query); page=items[offset:offset+bounds.limit]; next_offset=offset+len(page); truncated=next_offset<len(items)
        return {"items":page,"truncated":truncated,"next_cursor":cursor_encode(self.build["build_ref"],query,next_offset) if truncated else None,"build_ref":self.build["build_ref"]}

    def dependency_slice(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds=QueryBounds.from_args(arguments); refs=arguments.get("refs",[]); direction=arguments.get("direction","dependencies")
        if not isinstance(refs,list) or direction not in {"dependencies","dependents"}: raise GraphError("QUERY_INVALID", "refs or direction is invalid")
        registry=self.workflow.get("graph",{}).get("edge_types",{}); adjacency=defaultdict(list)
        for edge in self.edges:
            if registry.get(edge.get("kind"),{}).get("family") != "dependency" or not edge.get("active",True): continue
            left,right=edge["from_ref"],edge["to_ref"]; adjacency[left if direction=="dependencies" else right].append((right if direction=="dependencies" else left,edge))
        seen=set(refs); frontier=[(x,0) for x in refs]; found=[]
        while frontier:
            current,depth=frontier.pop(0)
            if depth>=bounds.depth: continue
            for target,edge in sorted(adjacency[current],key=lambda x:(x[0],x[1]["ref"])):
                found.append({"from_ref":current,"to_ref":target,"edge_ref":edge["ref"],"edge_kind":edge["kind"],"direction":direction,"depth":depth+1})
                if target not in seen and registry[edge["kind"]].get("transitive",False): seen.add(target); frontier.append((target,depth+1))
        return self._page(sorted(found,key=lambda x:(x["depth"],x["from_ref"],x["to_ref"])),bounds,f"dependency:{direction}:{json.dumps(sorted(refs))}:{bounds.depth}")

    def impact_analysis(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds=QueryBounds.from_args(arguments); refs=arguments.get("refs",[]); registry=self.workflow.get("graph",{}).get("edge_types",{}); adjacency=defaultdict(list)
        for edge in self.edges:
            if edge.get("active",True) and registry.get(edge.get("kind"),{}).get("impact") is True:
                adjacency[edge["from_ref"]].append((edge["to_ref"],edge,"forward")); adjacency[edge["to_ref"]].append((edge["from_ref"],edge,"reverse"))
        seen=set(refs); frontier=[(x,0) for x in refs]; found=[]
        while frontier:
            current,depth=frontier.pop(0)
            if depth>=bounds.depth: continue
            for target,edge,direction in sorted(adjacency[current],key=lambda x:(x[0],x[1]["ref"],x[2])):
                found.append({"from_ref":current,"to_ref":target,"edge_ref":edge["ref"],"edge_kind":edge["kind"],"direction":direction,"depth":depth+1})
                if target not in seen: seen.add(target); frontier.append((target,depth+1))
        return self._page(sorted(found,key=lambda x:(x["depth"],x["from_ref"],x["edge_ref"],x["direction"])),bounds,"impact:"+json.dumps(sorted(refs))+f":{bounds.depth}")

    def graph_trace(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds=QueryBounds.from_args(arguments); refs=set(arguments.get("refs",[])); items=[x for x in self.edges if not refs or x["from_ref"] in refs or x["to_ref"] in refs]
        return self._page(sorted(items,key=lambda x:x["ref"]),bounds,"trace:"+json.dumps(sorted(refs)))

    def diagnostics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._page(sorted(self.trace.get("findings",[])+self.process.get("findings",[]),key=lambda x:str(x.get("ref",""))),QueryBounds.from_args(arguments),"diagnostics")

    def topological_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds=QueryBounds.from_args(arguments); task_data={x["task_id"]:x for x in self.ledger.get("tasks",[]) if x.get("status")!="superseded"}; prerequisites={x:set() for x in task_data}; dependents=defaultdict(set)
        for task, data in task_data.items():
            for prerequisite in data.get("depends_on",[]):
                if prerequisite not in task_data: raise GraphError("DANGLING_REF", "active prerequisite is missing", task_ref=task)
                prerequisites[task].add(prerequisite); dependents[prerequisite].add(task)
        key=lambda ref:(task_data[ref].get("queue_sequence",2**31),ref); ready=sorted((x for x in task_data if not prerequisites[x]),key=key); ordered=[]
        while ready:
            ref=ready.pop(0); ordered.append(ref)
            for target in sorted(dependents[ref],key=key):
                prerequisites[target].discard(ref)
                if not prerequisites[target] and target not in ready: ready.append(target); ready.sort(key=key)
        if len(ordered)!=len(task_data): raise GraphError("GRAPH_CYCLE", "task dependency graph contains a cycle")
        return self._page(ordered,bounds,"topological-plan")

    def workflow_state(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds=QueryBounds.from_args(arguments); run_ref=arguments.get("run_ref"); events=[x for x in self.process.get("events",[]) if not run_ref or x.get("run_ref")==run_ref]
        return self._page(causal_order(events),bounds,"workflow-state:"+str(run_ref or "*"))

def execute_query(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    store=GraphStore.load(arguments)
    try:
        normalized={k:v for k,v in arguments.items() if k!="app_root"}; key=(store.build["build_ref"],name,json.dumps(normalized,sort_keys=True,separators=(",",":")))
        if key in QUERY_CACHE: return copy.deepcopy(QUERY_CACHE[key])
        method="diagnostics" if name=="graph_diagnostics" else name; result=getattr(store,method)(arguments); QUERY_CACHE[key]=copy.deepcopy(result); return result
    finally: store.close()
