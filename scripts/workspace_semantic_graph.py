#!/usr/bin/env python3
"""Build a bounded workspace semantic graph from Bears JSON authority layers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/workspace-semantic-graph.v1.json"
GRAPH_SCHEMA = PLUGIN_ROOT / "assets/schemas/workspace-semantic-graph.v1.schema.json"
NODE_SCHEMA = PLUGIN_ROOT / "assets/schemas/workspace-semantic-node.v1.schema.json"
EDGE_SCHEMA = PLUGIN_ROOT / "assets/schemas/workspace-semantic-edge.v1.schema.json"
DICTIONARY = PLUGIN_ROOT / "assets/catalog/workspace-dictionary.v1.json"
STORE_POLICY = PLUGIN_ROOT / "assets/catalog/metadata-store-policy.v1.json"
FILE_CONTEXT_INDEX = PLUGIN_ROOT / "assets/file-context/index.v1.json"
DECISION_LEDGER = PLUGIN_ROOT / "assets/catalog/decision-ledger.v1.json"
RELEASE_NOTES = PLUGIN_ROOT / "assets/catalog/release-notes.v1.json"
COMMANDS = [
    "python3 scripts/workspace_semantic_graph.py validate",
    "python3 scripts/workspace_semantic_graph.py extract --paths <paths> --json",
    "python3 scripts/workspace_semantic_graph.py build --json",
    "python3 scripts/workspace_semantic_graph.py query --selector <path> --json",
    "python3 scripts/workspace_semantic_graph.py diff --base <ref> --head <ref> --json",
]
NODE_TYPES = ["repo", "worktree", "directory", "file", "symbol", "function", "class", "schema", "catalog", "script", "validator", "workflow_node", "roadmap_node", "decision", "changelog_entry", "principle", "goal", "standard", "technology", "agent_role", "skill", "context_surface", "execution_unit", "runtime_evidence", "issue", "commit"]
EDGE_TYPES = ["contains", "imports", "calls", "reads", "writes", "validates", "implements", "owned_by", "uses_standard", "uses_technology", "has_context", "has_decision", "has_changelog", "requires", "blocks", "supersedes", "duplicates", "related_to", "feeds", "consumes", "changed_by", "verified_by", "executed_by"]
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import code_property_graph


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def source_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PLUGIN_ROOT / normalize(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower() or "item"


def node(node_type: str, name: str, *, path: str | None = None, source_refs: list[str] | None = None, **metadata: Any) -> dict[str, Any]:
    return {"schema": "bears-workspace-semantic-node.v1", "node_id": f"{node_type}:{slug(path or name)}", "node_type": node_type, "name": name, "path": path, "source_refs": source_refs or ([path] if path else []), "metadata": metadata}


def edge(edge_type: str, source: str, target: str, *, source_refs: list[str] | None = None, **metadata: Any) -> dict[str, Any]:
    return {"schema": "bears-workspace-semantic-edge.v1", "edge_id": f"edge:{edge_type}:{slug(source)}:{slug(target)}"[:180], "edge_type": edge_type, "source": source, "target": target, "source_refs": source_refs or [], "metadata": metadata}


def dedupe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result[str(row[key])] = row
    return [result[item] for item in sorted(result)]


def context_record(path: str) -> dict[str, Any] | None:
    if not FILE_CONTEXT_INDEX.exists():
        return None
    target = normalize(path)
    for record in load(FILE_CONTEXT_INDEX).get("records", []):
        if isinstance(record, dict) and normalize(str(record.get("path", ""))) == target:
            return record
    return None


def decisions_for_path(path: str) -> list[dict[str, Any]]:
    if not DECISION_LEDGER.exists():
        return []
    target = normalize(path)
    return [row for row in load(DECISION_LEDGER).get("records", []) if isinstance(row, dict) and target in [normalize(str(item)) for item in row.get("affected_paths", [])]]


def changelog_for_path(path: str) -> list[dict[str, Any]]:
    if not RELEASE_NOTES.exists():
        return []
    target = normalize(path)
    return [row for row in load(RELEASE_NOTES).get("entries", []) if isinstance(row, dict) and target in [normalize(str(item)) for item in row.get("files", [])]]


def node_type_for_path(path: str) -> str:
    if path.endswith(".schema.json"):
        return "schema"
    if path.startswith("assets/catalog/"):
        return "catalog"
    if path.startswith("scripts/") and path.endswith(".py"):
        return "script"
    return "file"


def extract_path(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    item = normalize(path)
    file_path = source_path(item)
    if not file_path.exists():
        return [], [], [f"source file missing: {item}"]
    nodes = [node(node_type_for_path(item), item, path=item, source_hash=sha256(file_path))]
    edges: list[dict[str, Any]] = []
    file_node = nodes[0]["node_id"]
    directory = str(Path(item).parent)
    dir_node = node("directory", directory, path=directory, source_refs=[item])
    nodes.append(dir_node)
    edges.append(edge("contains", dir_node["node_id"], file_node, source_refs=[item]))
    ctx = context_record(item)
    if ctx:
        ctx_node = node("context_surface", str(ctx["context_id"]), path=item, source_refs=["assets/file-context/index.v1.json"], status=ctx.get("status"), read_policy=ctx.get("read_policy"))
        nodes.append(ctx_node)
        edges.append(edge("has_context", file_node, ctx_node["node_id"], source_refs=["assets/file-context/index.v1.json"]))
        for ref in ctx.get("decision_refs", [])[:20]:
            dec_node = node("decision", str(ref), source_refs=["assets/catalog/decision-ledger.v1.json"])
            nodes.append(dec_node)
            edges.append(edge("has_decision", file_node, dec_node["node_id"], source_refs=["assets/file-context/index.v1.json"]))
    for decision in decisions_for_path(item)[:20]:
        dec_node = node("decision", str(decision["decision_id"]), source_refs=["assets/catalog/decision-ledger.v1.json"], owner_issue=decision.get("owner_issue"))
        nodes.append(dec_node)
        edges.append(edge("has_decision", file_node, dec_node["node_id"], source_refs=["assets/catalog/decision-ledger.v1.json"]))
        issue = str(decision.get("owner_issue", ""))
        if issue.startswith("#"):
            issue_node = node("issue", issue, source_refs=[issue])
            nodes.append(issue_node)
            edges.append(edge("implements", issue_node["node_id"], file_node, source_refs=[issue]))
    for entry in changelog_for_path(item)[:20]:
        change_node = node("changelog_entry", str(entry.get("issue_ref")), source_refs=["assets/catalog/release-notes.v1.json"], impact=entry.get("impact"))
        nodes.append(change_node)
        edges.append(edge("has_changelog", file_node, change_node["node_id"], source_refs=["assets/catalog/release-notes.v1.json"]))
    if file_path.suffix in {".py", ".json"}:
        cpg = code_property_graph.extract_path(item)
        for cpg_node in cpg.get("nodes", [])[:100]:
            symbol_type = "function" if cpg_node.get("node_type") in {"function", "async_function"} else "class" if cpg_node.get("node_type") == "class" else "symbol"
            sym = node(symbol_type, str(cpg_node.get("name")), path=item, source_refs=[item], cpg_node_id=cpg_node.get("node_id"))
            nodes.append(sym)
            edges.append(edge("contains", file_node, sym["node_id"], source_refs=[item]))
        for cpg_edge in cpg.get("edges", [])[:100]:
            fact = str(cpg_edge.get("fact_type", "related_to"))
            semantic_edge = "imports" if "imports" in fact else "calls" if "calls" in fact else "reads" if "reads" in fact else "writes" if "writes" in fact else "validates" if "validates" in fact else "related_to"
            target = node("symbol", str(cpg_edge.get("target")), path=item, source_refs=[item])
            nodes.append(target)
            edges.append(edge(semantic_edge, file_node, target["node_id"], source_refs=[item], cpg_fact_type=fact))
    return dedupe(nodes, "node_id"), dedupe(edges, "edge_id"), []


def graph_packet(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], errors: list[str] | None = None) -> dict[str, Any]:
    return {"schema": "bears-workspace-semantic-graph.v1", "version": "1", "updated": today(), "owner_role": "bears-machine-first-execution-kernel-engineer", "commands": COMMANDS, "node_types": NODE_TYPES, "edge_types": EDGE_TYPES, "nodes": nodes, "edges": edges, "integration_points": load(CATALOG).get("integration_points", {}) if CATALOG.exists() else {}, "errors": errors or []}


def build(paths: list[str] | None = None) -> dict[str, Any]:
    paths = paths or ["assets/catalog/file-context-policy.v1.json", "scripts/file_context_index.py", "scripts/bears_doctor.py", "assets/catalog/workflow-inference-rules.v1.json"]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        n, e, err = extract_path(path)
        nodes.extend(n)
        edges.extend(e)
        errors.extend(err)
    return graph_packet(dedupe(nodes, "node_id"), dedupe(edges, "edge_id"), errors)


def validate_all() -> list[str]:
    errors: list[str] = []
    for schema in (GRAPH_SCHEMA, NODE_SCHEMA, EDGE_SCHEMA):
        if not schema.exists():
            errors.append(f"missing schema: {schema.relative_to(PLUGIN_ROOT).as_posix()}")
    for required in (DICTIONARY, STORE_POLICY):
        if not required.exists():
            errors.append(f"missing required catalog: {required.relative_to(PLUGIN_ROOT).as_posix()}")
    if not CATALOG.exists():
        return errors + ["semantic graph catalog missing"]
    packet = load(CATALOG)
    errors.extend(validate_json_schema(packet, GRAPH_SCHEMA, CATALOG.name))
    for command in COMMANDS:
        if command not in packet.get("commands", []):
            errors.append(f"missing command: {command}")
    for node_type in NODE_TYPES:
        if node_type not in packet.get("node_types", []):
            errors.append(f"missing node type: {node_type}")
    for edge_type in EDGE_TYPES:
        if edge_type not in packet.get("edge_types", []):
            errors.append(f"missing edge type: {edge_type}")
    sample = build(["scripts/file_context_index.py"])
    if not sample["nodes"] or not sample["edges"]:
        errors.append("sample extraction produced empty graph")
    return errors


def git_diff(base: str, head: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}..{head}"], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    return [normalize(line) for line in proc.stdout.splitlines() if line.strip()] if proc.returncode == 0 else []


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    extract = sub.add_parser("extract")
    extract.add_argument("--paths", nargs="+", required=True)
    extract.add_argument("--json", action="store_true")
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--json", action="store_true")
    query = sub.add_parser("query")
    query.add_argument("--selector", required=True)
    query.add_argument("--json", action="store_true")
    diff = sub.add_parser("diff")
    diff.add_argument("--base", required=True)
    diff.add_argument("--head", required=True)
    diff.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        print_packet({"schema": "bears-workspace-semantic-graph-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "extract":
        packet = build(args.paths)
        packet["status"] = "pass" if not packet.get("errors") else "fail"
        print_packet(packet)
        return 0 if packet["status"] == "pass" else 1
    if args.command == "build":
        packet = build()
        packet["status"] = "pass" if not packet.get("errors") else "fail"
        print_packet(packet)
        return 0 if packet["status"] == "pass" else 1
    if args.command == "query":
        packet = build([args.selector])
        ctx = context_record(args.selector)
        print_packet({"schema": "bears-workspace-semantic-graph-query.v1", "status": "pass" if not packet.get("errors") else "fail", "selector": normalize(args.selector), "bounded": True, "context_selector": None if not ctx else {"context_id": ctx.get("context_id"), "read_policy": ctx.get("read_policy"), "status": ctx.get("status")}, "nodes": packet["nodes"][:50], "edges": packet["edges"][:100], "errors": packet.get("errors", [])})
        return 0 if not packet.get("errors") else 1
    if args.command == "diff":
        files = git_diff(args.base, args.head)
        print_packet({"schema": "bears-workspace-semantic-graph-diff.v1", "status": "pass", "base": args.base, "head": args.head, "changed_files": files, "changed_count": len(files), "graph": build(files[:20])})
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
