#!/usr/bin/env python3
"""Extract compact code property graph facts for governed Bears files."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/code-property-graph.v1.json"
GRAPH_SCHEMA = PLUGIN_ROOT / "assets/schemas/code-property-graph.v1.schema.json"
NODE_SCHEMA = PLUGIN_ROOT / "assets/schemas/code-property-node.v1.schema.json"
EDGE_SCHEMA = PLUGIN_ROOT / "assets/schemas/code-property-edge.v1.schema.json"
FACT_TYPES = [
    "file_contains_symbol",
    "symbol_imports_module",
    "function_calls_symbol",
    "function_reads_name",
    "function_writes_name",
    "script_exposes_command",
    "script_validates_schema",
    "schema_validates_packet",
    "catalog_references_schema",
    "test_targets_script",
]
COMMANDS = [
    "python3 scripts/code_property_graph.py validate",
    "python3 scripts/code_property_graph.py extract --path <path> --json",
    "python3 scripts/code_property_graph.py build --paths <paths> --json",
    "python3 scripts/code_property_graph.py query --selector <path> --json",
    "python3 scripts/code_property_graph.py stale --json",
    "python3 scripts/code_property_graph.py doctor --json",
]
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PLUGIN_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def source_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PLUGIN_ROOT / normalize(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower() or "item"


def node(node_type: str, path: str, name: str, source_hash: str, **metadata: Any) -> dict[str, Any]:
    return {
        "schema": "bears-code-property-node.v1",
        "node_id": f"cpg:{slug(path)}:{node_type}:{slug(name)}",
        "node_type": node_type,
        "path": path,
        "name": name,
        "source_hash": source_hash,
        "confidence": "candidate",
        "metadata": metadata,
    }


def edge(fact_type: str, source: str, target: str, path: str, source_hash: str, **metadata: Any) -> dict[str, Any]:
    return {
        "schema": "bears-code-property-edge.v1",
        "edge_id": f"cpg-edge:{slug(path)}:{fact_type}:{slug(source)}:{slug(target)}"[:180],
        "fact_type": fact_type,
        "source": source,
        "target": target,
        "path": path,
        "source_hash": source_hash,
        "confidence": "candidate",
        "extraction_validated": True,
        "metadata": metadata,
    }


class FunctionFacts(ast.NodeVisitor):
    def __init__(self, function_id: str, path: str, source_hash: str) -> None:
        self.function_id = function_id
        self.path = path
        self.source_hash = source_hash
        self.edges: list[dict[str, Any]] = []

    def visit_Call(self, ast_node: ast.Call) -> Any:
        target = call_name(ast_node.func)
        if target:
            self.edges.append(edge("function_calls_symbol", self.function_id, target, self.path, self.source_hash))
        self.generic_visit(ast_node)

    def visit_Name(self, ast_node: ast.Name) -> Any:
        if isinstance(ast_node.ctx, ast.Load):
            self.edges.append(edge("function_reads_name", self.function_id, ast_node.id, self.path, self.source_hash))
        elif isinstance(ast_node.ctx, (ast.Store, ast.Del)):
            self.edges.append(edge("function_writes_name", self.function_id, ast_node.id, self.path, self.source_hash))

    def visit_Attribute(self, ast_node: ast.Attribute) -> Any:
        if isinstance(ast_node.ctx, ast.Load):
            self.edges.append(edge("function_reads_name", self.function_id, ast_node.attr, self.path, self.source_hash))
        elif isinstance(ast_node.ctx, (ast.Store, ast.Del)):
            self.edges.append(edge("function_writes_name", self.function_id, ast_node.attr, self.path, self.source_hash))
        self.generic_visit(ast_node)


def call_name(ast_node: ast.AST) -> str | None:
    if isinstance(ast_node, ast.Name):
        return ast_node.id
    if isinstance(ast_node, ast.Attribute):
        base = call_name(ast_node.value)
        return f"{base}.{ast_node.attr}" if base else ast_node.attr
    return None


def literal_strings(ast_node: ast.AST | list[ast.AST]) -> list[str]:
    values: list[str] = []
    roots = ast_node if isinstance(ast_node, list) else [ast_node]
    for root in roots:
        for child in ast.walk(root):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                values.append(child.value)
    return values


def extract_python(path: str, file_path: Path, source_hash: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    nodes = [node("file", path, path, source_hash)]
    edges: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return nodes, edges, [f"syntax error: {exc}"]
    file_id = nodes[0]["node_id"]
    for child in tree.body:
        if isinstance(child, ast.Import):
            for alias in child.names:
                edges.append(edge("symbol_imports_module", file_id, alias.name, path, source_hash))
        elif isinstance(child, ast.ImportFrom) and child.module:
            edges.append(edge("symbol_imports_module", file_id, child.module, path, source_hash))
        elif isinstance(child, ast.ClassDef):
            class_node = node("class", path, child.name, source_hash, decorators=literal_strings(child.decorator_list))
            nodes.append(class_node)
            edges.append(edge("file_contains_symbol", file_id, class_node["node_id"], path, source_hash))
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async_function" if isinstance(child, ast.AsyncFunctionDef) else "function"
            func_node = node(kind, path, child.name, source_hash, args=[arg.arg for arg in child.args.args], returns=ast.unparse(child.returns) if child.returns else None)
            nodes.append(func_node)
            edges.append(edge("file_contains_symbol", file_id, func_node["node_id"], path, source_hash))
            visitor = FunctionFacts(func_node["node_id"], path, source_hash)
            visitor.visit(child)
            edges.extend(visitor.edges)
    for call in [item for item in ast.walk(tree) if isinstance(item, ast.Call)]:
        name = call_name(call.func)
        if name and name.endswith("add_parser"):
            for value in literal_strings(call):
                if value and " " not in value and len(value) < 40:
                    command_node = node("command", path, value, source_hash)
                    nodes.append(command_node)
                    edges.append(edge("script_exposes_command", file_id, command_node["node_id"], path, source_hash))
    for value in literal_strings(tree):
        if value.endswith(".schema.json"):
            edges.append(edge("script_validates_schema", file_id, value, path, source_hash))
    if path.startswith("tests/"):
        for value in literal_strings(tree):
            if value.startswith("scripts/") and value.endswith(".py"):
                edges.append(edge("test_targets_script", file_id, value, path, source_hash))
    return dedupe(nodes, "node_id"), dedupe(edges, "edge_id"), errors


def extract_json(path: str, file_path: Path, source_hash: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    try:
        packet = load(file_path)
    except Exception as exc:
        return [node("file", path, path, source_hash)], [], [f"json error: {exc}"]
    node_type = "schema" if path.endswith(".schema.json") else "catalog"
    root = node(node_type, path, str(packet.get("schema") or packet.get("$id") or path), source_hash)
    edges: list[dict[str, Any]] = []
    for command in packet.get("commands", []) if isinstance(packet.get("commands"), list) else []:
        edges.append(edge("script_exposes_command", root["node_id"], str(command), path, source_hash))
    text = json.dumps(packet, sort_keys=True)
    for token in sorted(set(part.strip('" ,') for part in text.replace("\\", "/").split() if ".schema.json" in part)):
        edges.append(edge("catalog_references_schema", root["node_id"], token, path, source_hash))
    if path.endswith(".schema.json"):
        edges.append(edge("schema_validates_packet", root["node_id"], str(packet.get("title") or path), path, source_hash))
    return [root], dedupe(edges, "edge_id"), []


def dedupe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result[str(row[key])] = row
    return [result[item] for item in sorted(result)]


def extract_path(path: str) -> dict[str, Any]:
    item = normalize(path)
    file_path = source_path(item)
    if not file_path.exists():
        return graph_packet([], [], errors=[f"source file missing: {item}"])
    source_hash = sha256(file_path)
    if file_path.suffix == ".py":
        nodes, edges, errors = extract_python(item, file_path, source_hash)
    elif file_path.suffix == ".json":
        nodes, edges, errors = extract_json(item, file_path, source_hash)
    else:
        nodes, edges, errors = [node("file", item, item, source_hash)], [], []
    return graph_packet(nodes, edges, errors=errors, tracked_sources=[{"path": item, "source_hash": source_hash}])


def graph_packet(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], *, errors: list[str] | None = None, tracked_sources: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "schema": "bears-code-property-graph.v1",
        "version": "1",
        "updated": today(),
        "owner_role": "bears-machine-first-execution-kernel-engineer",
        "commands": COMMANDS,
        "fact_types": FACT_TYPES,
        "nodes": nodes,
        "edges": edges,
        "tracked_sources": tracked_sources or [],
        **({"errors": errors or []} if errors is not None else {}),
    }


def build(paths: list[str]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    tracked: list[dict[str, str]] = []
    errors: list[str] = []
    for path in paths:
        packet = extract_path(path)
        nodes.extend(packet["nodes"])
        edges.extend(packet["edges"])
        tracked.extend(packet.get("tracked_sources", []))
        errors.extend(packet.get("errors", []))
    return graph_packet(dedupe(nodes, "node_id"), dedupe(edges, "edge_id"), errors=errors, tracked_sources=tracked)


def validate_catalog(path: Path = CATALOG) -> list[str]:
    errors: list[str] = []
    for schema in (GRAPH_SCHEMA, NODE_SCHEMA, EDGE_SCHEMA):
        if not schema.exists():
            errors.append(f"missing schema: {rel(schema)}")
    if not path.exists():
        return errors + ["catalog missing"]
    packet = load(path)
    errors.extend(validate_json_schema(packet, GRAPH_SCHEMA, path.name))
    for command in COMMANDS:
        if command not in packet.get("commands", []):
            errors.append(f"missing command: {command}")
    for fact_type in FACT_TYPES:
        if fact_type not in packet.get("fact_types", []):
            errors.append(f"missing fact type: {fact_type}")
    if any(edge.get("confidence") == "accepted" for edge in packet.get("edges", [])):
        errors.append("catalog must not store accepted CPG facts directly")
    return errors


def stale_sources(packet: dict[str, Any] | None = None) -> list[str]:
    packet = packet or load(CATALOG)
    stale: list[str] = []
    for row in packet.get("tracked_sources", []):
        if not isinstance(row, dict):
            continue
        path = normalize(str(row.get("path", "")))
        file_path = source_path(path)
        if file_path.exists() and row.get("source_hash") != sha256(file_path):
            stale.append(path)
    return sorted(set(stale))


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    extract = sub.add_parser("extract")
    extract.add_argument("--path", required=True)
    extract.add_argument("--json", action="store_true")
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--paths", nargs="+", required=True)
    build_cmd.add_argument("--json", action="store_true")
    query = sub.add_parser("query")
    query.add_argument("--selector", required=True)
    query.add_argument("--json", action="store_true")
    sub.add_parser("stale").add_argument("--json", action="store_true")
    sub.add_parser("doctor").add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog()
        print_packet({"schema": "bears-code-property-graph-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "extract":
        packet = extract_path(args.path)
        packet["status"] = "pass" if not packet.get("errors") else "fail"
        print_packet(packet)
        return 0 if packet["status"] == "pass" else 1
    if args.command == "build":
        packet = build(args.paths)
        packet["status"] = "pass" if not packet.get("errors") else "fail"
        print_packet(packet)
        return 0 if packet["status"] == "pass" else 1
    if args.command == "query":
        packet = extract_path(args.selector)
        print_packet({"schema": "bears-code-property-graph-query.v1", "status": "pass" if not packet.get("errors") else "fail", "selector": normalize(args.selector), "nodes": packet["nodes"][:50], "edges": packet["edges"][:100], "errors": packet.get("errors", [])})
        return 0 if not packet.get("errors") else 1
    if args.command == "stale":
        stale = stale_sources()
        print_packet({"schema": "bears-code-property-graph-stale.v1", "status": "pass" if not stale else "fail", "stale_sources": stale})
        return 0 if not stale else 1
    if args.command == "doctor":
        errors = validate_catalog()
        stale = stale_sources()
        errors.extend(f"stale source: {item}" for item in stale)
        print_packet({"schema": "bears-code-property-graph-doctor.v1", "status": "pass" if not errors else "fail", "cpg_freshness": "pass" if not stale else "fail", "rule_errors": errors, "fact_type_count": len(FACT_TYPES)})
        return 0 if not errors else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
