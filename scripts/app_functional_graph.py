#!/usr/bin/env python3
"""Manage app functional graph and app task ledger files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path("/srv/bears/dev/app")
GRAPH_NAME = "app-functional-graph.v1.json"
LEDGER_NAME = "app-task-ledger.v1.json"
EXECUTION_STATUSES = {"ready", "in_progress", "done", "blocked", "needs-review"}
AUTOCI_GRAPH_PATH = PLUGIN_ROOT / "assets/catalog/autoci-graph.v1.json"
NOTIFICATION_REASONS = {"blocker", "incident", "bug", "operator-question"}
SECRET_VALUE_PATTERNS = (
    re.compile(r"[A-Za-z0-9_\-]{32,}"),
    re.compile(r"(?i)(bearer\s+|token\s*=|password\s*=|secret\s*=|api[_-]?key\s*=)"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def app_dir_path(raw: str) -> Path:
    path = Path(raw).resolve()
    try:
        path.relative_to(APP_ROOT)
    except ValueError as exc:
        raise ValueError(f"app-dir must be under {APP_ROOT}: {path}") from exc
    return path


def app_name(app_dir: Path) -> str:
    return app_dir.name


def docs_dir(app_dir: Path) -> Path:
    return app_dir / "docs"


def graph_path(app_dir: Path) -> Path:
    return docs_dir(app_dir) / GRAPH_NAME


def ledger_path(app_dir: Path) -> Path:
    return docs_dir(app_dir) / LEDGER_NAME


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def empty_graph(app_dir: Path) -> dict[str, Any]:
    return {
        "schema": "app-functional-graph.v1",
        "version": "1",
        "app": app_name(app_dir),
        "owner_repo": "BearsCLOUD/apps",
        "app_directory": app_dir.as_posix(),
        "updated": utc_now(),
        "source_docs": [],
        "functionalities": [],
    }


def empty_ledger(app_dir: Path) -> dict[str, Any]:
    return {
        "schema": "app-task-ledger.v1",
        "version": "1",
        "app": app_name(app_dir),
        "app_directory": app_dir.as_posix(),
        "updated": utc_now(),
        "tasks": [],
    }


def list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_autoci_graph() -> dict[str, Any]:
    if not AUTOCI_GRAPH_PATH.is_file():
        return {"schema": "autoci-graph.v1", "zones": []}
    return load_json(AUTOCI_GRAPH_PATH)


def normalize_task_path(app_dir: Path, raw_path: str) -> str:
    value = str(raw_path).strip()
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(app_dir).as_posix()
        except ValueError:
            return path.as_posix()
    app_prefix = f"{app_name(app_dir)}/"
    if value.startswith(app_prefix):
        return value[len(app_prefix) :]
    return value


def pattern_matches(pattern: str, path: str) -> bool:
    from fnmatch import fnmatch

    return fnmatch(path, pattern)


def autoci_zones_for_paths(paths: list[str], app_dir: Path, graph: dict[str, Any] | None = None) -> list[str]:
    graph = graph or load_autoci_graph()
    zones: set[str] = set()
    normalized = [normalize_task_path(app_dir, path) for path in paths if str(path).strip()]
    for zone in list_items(graph.get("zones")):
        if not isinstance(zone, dict):
            continue
        zid = str(zone.get("id", ""))
        patterns = [str(item) for item in list_items(zone.get("path_patterns"))]
        if zid and any(pattern_matches(pattern, path) for path in normalized for pattern in patterns):
            zones.add(zid)
    return sorted(zones)


def expected_statuses_for_zones(zone_ids: list[str], graph: dict[str, Any] | None = None) -> list[str]:
    graph = graph or load_autoci_graph()
    expected: set[str] = set()
    wanted = set(zone_ids)
    for zone in list_items(graph.get("zones")):
        if isinstance(zone, dict) and str(zone.get("id", "")) in wanted:
            expected.update(str(item) for item in list_items(zone.get("expected_statuses")) if str(item))
    return sorted(expected)


def node_key(functionality_id: str, node_id: str) -> str:
    return f"{functionality_id}.{node_id}"


def node_ref_exists(functionality: dict[str, Any], ref: str) -> bool:
    fid = str(functionality.get("id", ""))
    nodes = {str(node.get("id", "")) for node in list_items(functionality.get("nodes")) if isinstance(node, dict)}
    return ref in nodes or (ref.startswith(f"{fid}.") and ref[len(fid) + 1 :] in nodes)


def build_graph_index(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str], set[str]]:
    functionalities: dict[str, dict[str, Any]] = {}
    node_refs: set[str] = set()
    edge_refs: set[str] = set()
    for functionality in list_items(graph.get("functionalities")):
        if not isinstance(functionality, dict):
            continue
        fid = str(functionality.get("id", ""))
        if not fid:
            continue
        functionalities[fid] = functionality
        for node in list_items(functionality.get("nodes")):
            if isinstance(node, dict) and node.get("id"):
                node_refs.add(node_key(fid, str(node["id"])))
                node_refs.add(str(node["id"]))
        for edge in list_items(functionality.get("edges")):
            if isinstance(edge, dict):
                start = edge.get("from")
                end = edge.get("to")
                if isinstance(start, str) and isinstance(end, str):
                    edge_refs.add(f"{fid}.{start}->{end}")
                    edge_refs.add(f"{start}->{end}")
    return functionalities, node_refs, edge_refs


def looks_like_secret(value: str) -> bool:
    if value in {"none", "secret-name-only"}:
        return False
    if value.startswith("secret-ref:") or value.startswith("secret-name:"):
        return False
    if " " in value and not value.startswith("name:"):
        return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS) and not value.startswith("name:")


def validate_graph(graph: dict[str, Any], app_dir: Path) -> list[str]:
    errors: list[str] = []
    if graph.get("schema") != "app-functional-graph.v1":
        errors.append("graph.schema must be app-functional-graph.v1")
    if graph.get("app") != app_name(app_dir):
        errors.append(f"graph.app must be {app_name(app_dir)}")
    if graph.get("app_directory") != app_dir.as_posix():
        errors.append(f"graph.app_directory must be {app_dir.as_posix()}")
    seen_functionalities: set[str] = set()
    for index, functionality in enumerate(list_items(graph.get("functionalities"))):
        if not isinstance(functionality, dict):
            errors.append(f"functionalities[{index}] must be an object")
            continue
        fid = str(functionality.get("id", ""))
        if not fid:
            errors.append(f"functionalities[{index}].id is required")
            continue
        if fid in seen_functionalities:
            errors.append(f"duplicate functionality id: {fid}")
        seen_functionalities.add(fid)
        seen_nodes: set[str] = set()
        for node_index, node in enumerate(list_items(functionality.get("nodes"))):
            if not isinstance(node, dict):
                errors.append(f"{fid}.nodes[{node_index}] must be an object")
                continue
            nid = str(node.get("id", ""))
            if not nid:
                errors.append(f"{fid}.nodes[{node_index}].id is required")
                continue
            if nid in seen_nodes:
                errors.append(f"duplicate node id in {fid}: {nid}")
            seen_nodes.add(nid)
        for edge in list_items(functionality.get("edges")):
            if not isinstance(edge, dict):
                continue
            start = str(edge.get("from", ""))
            end = str(edge.get("to", ""))
            if start not in seen_nodes:
                errors.append(f"{fid}.edge.from missing node: {start}")
            if end not in seen_nodes:
                errors.append(f"{fid}.edge.to missing node: {end}")
        for api_call in list_items(functionality.get("api_calls")):
            if not isinstance(api_call, dict):
                continue
            caller = str(api_call.get("caller_node_ref", ""))
            if caller and not node_ref_exists(functionality, caller):
                errors.append(f"{fid}.api_call caller_node_ref missing node: {caller}")
            auth_ref = str(api_call.get("auth_ref", ""))
            if auth_ref and looks_like_secret(auth_ref):
                errors.append(f"{fid}.api_call auth_ref must be name-only, not a secret value: {api_call.get('id', '<missing>')}")
        for cycle in list_items(functionality.get("async_cycles")):
            if not isinstance(cycle, dict):
                continue
            for field in ("trigger_node_ref", "worker_node_ref"):
                ref = str(cycle.get(field, ""))
                if ref and not node_ref_exists(functionality, ref):
                    errors.append(f"{fid}.async_cycle {field} missing node: {ref}")
    return errors


def validate_ledger(ledger: dict[str, Any], graph: dict[str, Any], app_dir: Path) -> list[str]:
    errors: list[str] = []
    if ledger.get("schema") != "app-task-ledger.v1":
        errors.append("ledger.schema must be app-task-ledger.v1")
    if ledger.get("app") != app_name(app_dir):
        errors.append(f"ledger.app must be {app_name(app_dir)}")
    if ledger.get("app_directory") != app_dir.as_posix():
        errors.append(f"ledger.app_directory must be {app_dir.as_posix()}")
    functionalities, node_refs, edge_refs = build_graph_index(graph)
    seen_tasks: set[str] = set()
    for index, task in enumerate(list_items(ledger.get("tasks"))):
        if not isinstance(task, dict):
            errors.append(f"tasks[{index}] must be an object")
            continue
        tid = str(task.get("task_id", ""))
        if not tid:
            errors.append(f"tasks[{index}].task_id is required")
            continue
        if tid in seen_tasks:
            errors.append(f"duplicate task_id: {tid}")
        seen_tasks.add(tid)
        status = str(task.get("status", ""))
        functionality_refs = [str(item) for item in list_items(task.get("functionality_refs"))]
        node_ref_values = [str(item) for item in list_items(task.get("graph_node_refs"))]
        if status in EXECUTION_STATUSES:
            if not functionality_refs:
                errors.append(f"{tid} status {status} requires functionality_refs")
            if not node_ref_values:
                errors.append(f"{tid} status {status} requires graph_node_refs")
            if not list_items(task.get("autoci_zones")):
                errors.append(f"{tid} status {status} requires autoci_zones")
            if not list_items(task.get("expected_statuses")):
                errors.append(f"{tid} status {status} requires expected_statuses")
        if status == "legacy_unbound" and (functionality_refs or node_ref_values):
            errors.append(f"{tid} legacy_unbound must not carry execution refs")
        if not functionality_refs and task.get("functional_scope") == "none":
            if task.get("reason") not in {"repo cleanup", "migration", "infra-only", "platform-only", "governance-only"}:
                errors.append(f"{tid} functional_scope=none requires an allowed reason")
        for ref in functionality_refs:
            if ref not in functionalities:
                errors.append(f"{tid} functionality_ref not found: {ref}")
        for ref in node_ref_values:
            if ref not in node_refs:
                errors.append(f"{tid} graph_node_ref not found: {ref}")
        for ref in [str(item) for item in list_items(task.get("graph_edge_refs"))]:
            if ref not in edge_refs:
                errors.append(f"{tid} graph_edge_ref not found: {ref}")
        for notification in list_items(task.get("notification_refs")):
            if not isinstance(notification, dict):
                errors.append(f"{tid} notification_refs entries must be objects")
                continue
            if notification.get("reason") not in NOTIFICATION_REASONS:
                errors.append(f"{tid} notification reason must be one of {sorted(NOTIFICATION_REASONS)}")
            issue_url = str(notification.get("issue_url", ""))
            if issue_url and "github.com" not in issue_url:
                errors.append(f"{tid} notification issue_url must be a GitHub URL")
    return errors


def validate_app(app_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        graph = load_json(graph_path(app_dir))
    except Exception as exc:  # noqa: BLE001
        graph = empty_graph(app_dir)
        errors.append(f"cannot load graph: {exc}")
    try:
        ledger = load_json(ledger_path(app_dir))
    except Exception as exc:  # noqa: BLE001
        ledger = empty_ledger(app_dir)
        errors.append(f"cannot load ledger: {exc}")
    errors.extend(validate_graph(graph, app_dir))
    errors.extend(validate_ledger(ledger, graph, app_dir))
    return {
        "schema": "app-functional-graph.validation.v1",
        "status": "pass" if not errors else "fail",
        "app": app_name(app_dir),
        "functional_graph": graph_path(app_dir).as_posix(),
        "task_ledger": ledger_path(app_dir).as_posix(),
        "functionality_count": len(list_items(graph.get("functionalities"))),
        "task_count": len(list_items(ledger.get("tasks"))),
        "errors": errors,
    }


def find_task(ledger: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in list_items(ledger.get("tasks")):
        if isinstance(task, dict) and task.get("task_id") == task_id:
            return task
    raise KeyError(f"task not found: {task_id}")


def command_init(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    docs_dir(app_dir).mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    if not graph_path(app_dir).exists():
        write_json(graph_path(app_dir), empty_graph(app_dir))
        created.append(graph_path(app_dir).as_posix())
    if not ledger_path(app_dir).exists():
        write_json(ledger_path(app_dir), empty_ledger(app_dir))
        created.append(ledger_path(app_dir).as_posix())
    print(json.dumps({"schema": "app-functional-graph.init.v1", "status": "created" if created else "exists", "created": created}, indent=2, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    packet = validate_app(app_dir_path(args.app_dir))
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def command_summary(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    graph = load_json(graph_path(app_dir))
    ledger = load_json(ledger_path(app_dir))
    statuses: dict[str, int] = {}
    for task in list_items(ledger.get("tasks")):
        if isinstance(task, dict):
            statuses[str(task.get("status", "<missing>"))] = statuses.get(str(task.get("status", "<missing>")), 0) + 1
    print(json.dumps({
        "schema": "app-functional-graph.summary.v1",
        "app": app_name(app_dir),
        "functionalities": [item.get("id") for item in list_items(graph.get("functionalities")) if isinstance(item, dict)],
        "task_statuses": statuses,
        "task_count": len(list_items(ledger.get("tasks"))),
    }, indent=2, sort_keys=True))
    return 0


def command_create_task(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    graph = load_json(graph_path(app_dir))
    ledger = load_json(ledger_path(app_dir))
    funcs, nodes, _ = build_graph_index(graph)
    if args.functionality_ref not in funcs:
        raise SystemExit(f"functionality_ref not found: {args.functionality_ref}")
    if args.node_ref not in nodes:
        raise SystemExit(f"node_ref not found: {args.node_ref}")
    try:
        find_task(ledger, args.task_id)
        raise SystemExit(f"task already exists: {args.task_id}")
    except KeyError:
        pass
    graph_catalog = load_autoci_graph()
    zones = sorted(set(args.autoci_zone or autoci_zones_for_paths(args.allowed_path, app_dir, graph_catalog)))
    expected_statuses = sorted(set(args.expected_status or expected_statuses_for_zones(zones, graph_catalog)))
    task = {
        "task_id": args.task_id,
        "title": args.title or args.task_id,
        "status": "ready",
        "target_layer": args.target_layer,
        "lane": args.lane,
        "owner_role": args.owner_role,
        "functionality_refs": [args.functionality_ref],
        "graph_node_refs": [args.node_ref],
        "graph_edge_refs": [],
        "allowed_paths": args.allowed_path,
        "autoci_zones": zones,
        "expected_statuses": expected_statuses,
        "status_evidence_refs": [],
        "worker_role": "none",
        "worker_id": "none",
        "started_at": "none",
        "closed_at": "none",
        "dependencies": args.dependency,
        "project_refs": [],
        "notification_refs": [],
        "commit_sha": "none",
        "status_matrix": [],
        "critic_confirmation": "none",
        "evidence_refs": [],
        "updated": utc_now(),
    }
    ledger.setdefault("tasks", []).append(task)
    ledger["updated"] = utc_now()
    write_json(ledger_path(app_dir), ledger)
    packet = validate_app(app_dir)
    print(json.dumps({"schema": "app-functional-graph.task-created.v1", "status": packet["status"], "task_id": args.task_id, "errors": packet["errors"]}, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def command_audit_task_packet(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    packet_path = Path(args.packet)
    packet = load_json(packet_path)
    ledger = load_json(ledger_path(app_dir))
    graph = load_json(graph_path(app_dir))
    funcs, nodes, _ = build_graph_index(graph)
    ledger_tasks = {task.get("task_id") for task in list_items(ledger.get("tasks")) if isinstance(task, dict)}
    errors: list[str] = []
    for task in list_items(packet.get("tasks")):
        if not isinstance(task, dict):
            errors.append("packet tasks entries must be objects")
            continue
        tid = str(task.get("task_id", ""))
        if tid not in ledger_tasks:
            errors.append(f"packet task missing from ledger: {tid}")
        for ref in list_items(task.get("functionality_refs")):
            if ref not in funcs:
                errors.append(f"packet functionality_ref missing from graph: {ref}")
        for ref in list_items(task.get("graph_node_refs")):
            if ref not in nodes:
                errors.append(f"packet graph_node_ref missing from graph: {ref}")
    print(json.dumps({"schema": "app-functional-graph.task-packet-audit.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_claim_task(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    ledger = load_json(ledger_path(app_dir))
    task = find_task(ledger, args.task_id)
    current = str(task.get("status", ""))
    if current not in {"ready", "in_progress"}:
        raise SystemExit(f"task must be ready or in_progress to claim: {args.task_id}")
    if current == "in_progress" and task.get("worker_id") not in {"none", args.worker_id}:
        raise SystemExit(f"task already claimed by another worker: {task.get('worker_id')}")
    task["status"] = "in_progress"
    task["worker_id"] = args.worker_id
    task["worker_role"] = args.worker_role
    if task.get("started_at") in {None, "", "none"}:
        task["started_at"] = utc_now()
    task["updated"] = utc_now()
    ledger["updated"] = utc_now()
    write_json(ledger_path(app_dir), ledger)
    packet = validate_app(app_dir)
    print(json.dumps({"schema": "app-functional-graph.task-claimed.v1", "status": packet["status"], "task_id": args.task_id, "errors": packet["errors"]}, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def command_mark_task_status(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    ledger = load_json(ledger_path(app_dir))
    task = find_task(ledger, args.task_id)
    if args.worker_id and task.get("worker_id") not in {"none", args.worker_id}:
        raise SystemExit(f"task worker mismatch: {task.get('worker_id')}")
    task["status"] = args.status
    if args.worker_id:
        task["worker_id"] = args.worker_id
    if args.worker_role:
        task["worker_role"] = args.worker_role
    if args.commit_sha:
        task["commit_sha"] = args.commit_sha
    for evidence_ref in args.evidence_ref:
        if evidence_ref not in task.setdefault("evidence_refs", []):
            task["evidence_refs"].append(evidence_ref)
    for status_ref in args.status_evidence_ref:
        if status_ref not in task.setdefault("status_evidence_refs", []):
            task["status_evidence_refs"].append(status_ref)
    if args.expected_status:
        task["expected_statuses"] = sorted(set(list_items(task.get("expected_statuses")) + args.expected_status))
    if args.status in {"done", "blocked", "needs-review"}:
        task["closed_at"] = utc_now()
    task["updated"] = utc_now()
    ledger["updated"] = utc_now()
    write_json(ledger_path(app_dir), ledger)
    packet = validate_app(app_dir)
    print(json.dumps({"schema": "app-functional-graph.task-status-marked.v1", "status": packet["status"], "task_id": args.task_id, "errors": packet["errors"]}, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def command_close_task(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    ledger = load_json(ledger_path(app_dir))
    task = find_task(ledger, args.task_id)
    task["commit_sha"] = args.commit_sha
    if args.evidence_ref not in task.setdefault("evidence_refs", []):
        task["evidence_refs"].append(args.evidence_ref)
    task["critic_confirmation"] = args.critic_confirmation
    task["status"] = args.status
    task["updated"] = utc_now()
    ledger["updated"] = utc_now()
    write_json(ledger_path(app_dir), ledger)
    packet = validate_app(app_dir)
    print(json.dumps({"schema": "app-functional-graph.task-closed.v1", "status": packet["status"], "task_id": args.task_id, "errors": packet["errors"]}, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def command_link_project_item(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    ledger = load_json(ledger_path(app_dir))
    task = find_task(ledger, args.task_id)
    refs = task.setdefault("project_refs", [])
    if args.project_item_ref not in refs:
        refs.append(args.project_item_ref)
    task["updated"] = utc_now()
    ledger["updated"] = utc_now()
    write_json(ledger_path(app_dir), ledger)
    print(json.dumps({"schema": "app-functional-graph.project-linked.v1", "status": "updated", "task_id": args.task_id}, indent=2, sort_keys=True))
    return 0


def command_record_notification(args: argparse.Namespace) -> int:
    app_dir = app_dir_path(args.app_dir)
    if args.reason not in NOTIFICATION_REASONS:
        raise SystemExit(f"reason must be one of {sorted(NOTIFICATION_REASONS)}")
    ledger = load_json(ledger_path(app_dir))
    task = find_task(ledger, args.task_id)
    refs = task.setdefault("notification_refs", [])
    entry = {"issue_url": args.issue_url, "reason": args.reason}
    if entry not in refs:
        refs.append(entry)
    task["updated"] = utc_now()
    ledger["updated"] = utc_now()
    write_json(ledger_path(app_dir), ledger)
    packet = validate_app(app_dir)
    print(json.dumps({"schema": "app-functional-graph.notification-recorded.v1", "status": packet["status"], "task_id": args.task_id, "errors": packet["errors"]}, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("init", command_init), ("validate", command_validate), ("summary", command_summary)):
        item = sub.add_parser(name)
        item.add_argument("--app-dir", required=True)
        item.set_defaults(func=func)
    create = sub.add_parser("create-task")
    create.add_argument("--app-dir", required=True)
    create.add_argument("--task-id", required=True)
    create.add_argument("--functionality-ref", required=True)
    create.add_argument("--node-ref", required=True)
    create.add_argument("--title")
    create.add_argument("--target-layer", default="app", choices=["app", "platform", "infra", "plugin"])
    create.add_argument("--lane", default="app")
    create.add_argument("--owner-role", default="bears-product-app-zone-engineer")
    create.add_argument("--allowed-path", action="append", default=[])
    create.add_argument("--dependency", action="append", default=[])
    create.add_argument("--autoci-zone", action="append", default=[])
    create.add_argument("--expected-status", action="append", default=[])
    create.set_defaults(func=command_create_task)
    audit = sub.add_parser("audit-task-packet")
    audit.add_argument("--app-dir", required=True)
    audit.add_argument("--packet", required=True)
    audit.set_defaults(func=command_audit_task_packet)
    claim = sub.add_parser("claim-task")
    claim.add_argument("--app-dir", required=True)
    claim.add_argument("--task-id", required=True)
    claim.add_argument("--worker-id", required=True)
    claim.add_argument("--worker-role", required=True)
    claim.set_defaults(func=command_claim_task)
    mark = sub.add_parser("mark-task-status")
    mark.add_argument("--app-dir", required=True)
    mark.add_argument("--task-id", required=True)
    mark.add_argument("--status", required=True, choices=["done", "blocked", "needs-review"])
    mark.add_argument("--worker-id")
    mark.add_argument("--worker-role")
    mark.add_argument("--commit-sha")
    mark.add_argument("--evidence-ref", action="append", default=[])
    mark.add_argument("--status-evidence-ref", action="append", default=[])
    mark.add_argument("--expected-status", action="append", default=[])
    mark.set_defaults(func=command_mark_task_status)
    close = sub.add_parser("close-task")
    close.add_argument("--app-dir", required=True)
    close.add_argument("--task-id", required=True)
    close.add_argument("--commit-sha", required=True)
    close.add_argument("--evidence-ref", required=True)
    close.add_argument("--critic-confirmation", default="confirmed")
    close.add_argument("--status", default="done", choices=["done", "blocked"])
    close.set_defaults(func=command_close_task)
    link = sub.add_parser("link-project-item")
    link.add_argument("--app-dir", required=True)
    link.add_argument("--task-id", required=True)
    link.add_argument("--project-item-ref", required=True)
    link.set_defaults(func=command_link_project_item)
    note = sub.add_parser("record-notification")
    note.add_argument("--app-dir", required=True)
    note.add_argument("--task-id", required=True)
    note.add_argument("--issue-url", required=True)
    note.add_argument("--reason", required=True, choices=sorted(NOTIFICATION_REASONS))
    note.set_defaults(func=command_record_notification)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
