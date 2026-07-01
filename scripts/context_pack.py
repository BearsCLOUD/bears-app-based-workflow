#!/usr/bin/env python3
"""Build deterministic prompt context packs from accepted Bears proof inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts import decision_graph, file_context_index, formal_semantics, workflow_inference  # noqa: E402
from scripts.local_json_schema import validate_json_schema  # noqa: E402

CATALOG = PLUGIN_ROOT / "assets/catalog/prompt-compiler.v1.json"
REQUEST_SCHEMA = PLUGIN_ROOT / "assets/schemas/prompt-compile-request.v1.schema.json"
PACK_SCHEMA = PLUGIN_ROOT / "assets/schemas/context-pack.v1.schema.json"
RESULT_SCHEMA = PLUGIN_ROOT / "assets/schemas/prompt-compile-result.v1.schema.json"
ROLE_PROFILES = PLUGIN_ROOT / "assets/catalog/opencode-agent-profiles.v1.json"
LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
FULL_READ_PREDICATES = {"full_file_read_allowed", "full_file_context_allowed", "can_read_full_file"}


def load_json(path: Path) -> Any:
    """Read a JSON packet from disk."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(packet: dict[str, Any]) -> str:
    """Render stable JSON for hashes, prompts, and CLI output."""
    return json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False)


def canonical_hash(packet: Any) -> str:
    """Return a stable SHA-256 hash of a JSON-compatible value."""
    data = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def estimate_tokens(value: Any) -> int:
    """Estimate prompt tokens from deterministic JSON text length."""
    text = dump_json(value) if not isinstance(value, str) else value
    return (len(text) + 3) // 4


def rel(path: Path) -> str:
    """Return a plugin-root-relative path when possible."""
    try:
        return path.resolve().relative_to(PLUGIN_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(value: str) -> Path:
    """Resolve a request path under the plugin checkout unless absolute."""
    path = Path(value)
    return path if path.is_absolute() else PLUGIN_ROOT / value


def validate_catalog() -> list[str]:
    """Validate prompt compiler static assets and command declarations."""
    errors: list[str] = []
    for path in (CATALOG, REQUEST_SCHEMA, PACK_SCHEMA, RESULT_SCHEMA):
        if not path.exists():
            errors.append(f"missing asset: {rel(path)}")
    if errors:
        return errors
    catalog = load_json(CATALOG)
    if catalog.get("schema") != "bears-prompt-compiler.v1":
        errors.append("prompt-compiler catalog schema mismatch")
    expected_commands = {
        "python3 scripts/context_pack.py validate",
        "python3 scripts/context_pack.py build --request <path> --json",
        "python3 scripts/prompt_compiler.py compile --request <path> --json",
        "python3 scripts/prompt_compiler.py diff --base <path> --head <path> --json",
        "python3 scripts/prompt_compiler.py doctor --json",
    }
    missing = sorted(expected_commands - set(catalog.get("commands", [])))
    errors.extend(f"missing command: {item}" for item in missing)
    schema_refs = catalog.get("schemas", {})
    for field in ("request", "context_pack", "result"):
        target = schema_refs.get(field)
        if not isinstance(target, str) or not resolve_path(target).exists():
            errors.append(f"catalog.schemas.{field} must point to an existing file")
    if [item.get("level") for item in catalog.get("context_levels", [])] != ["L0", "L1", "L2", "L3", "L4"]:
        errors.append("context levels must be exactly L0,L1,L2,L3,L4")
    return sorted(set(errors))


def role_profile(role_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Load one deterministic OpenCode role profile by profile_id."""
    errors: list[str] = []
    try:
        packet = load_json(ROLE_PROFILES)
    except FileNotFoundError:
        return None, ["role profile catalog missing"]
    for profile in packet.get("profiles", []):
        if isinstance(profile, dict) and profile.get("profile_id") == role_id:
            return profile, errors
    return None, [f"role profile not found: {role_id}"]


def request_level(request: dict[str, Any]) -> str:
    """Return the default context level for the request."""
    level = str(request.get("context_level") or "L2")
    return level if level in LEVEL_ORDER else "L2"


def context_request_item(item: Any, default_level: str) -> tuple[str, str]:
    """Normalize a context id request into id and context level."""
    if isinstance(item, dict):
        return str(item.get("context_id", "")), str(item.get("level") or default_level)
    return str(item), default_level


def accepted_fact_refs(graph: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return accepted semantic facts referenced by a decision graph."""
    facts: list[dict[str, Any]] = []
    errors: list[str] = []
    for fact_id in sorted(set(str(item) for item in graph.get("semantic_fact_refs", []))):
        result = formal_semantics.query_fact(fact_id)
        if not result.get("accepted"):
            errors.append(f"semantic fact is not accepted: {fact_id}")
            continue
        fact = dict(result.get("fact", {}))
        facts.append(fact)
    return facts, errors


def accepted_decision_proofs(graph: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return accepted proof nodes from a validated decision graph."""
    proofs: list[dict[str, Any]] = []
    errors: list[str] = []
    proof_ids = {node.get("proof_id") for node in graph.get("nodes", []) if isinstance(node, dict)}
    available = {
        proof.get("proof_id"): proof
        for proof in decision_graph.question_calculus.catalog().get("accepted_answer_proofs", [])
        if isinstance(proof, dict)
    }
    for proof_id in sorted(str(item) for item in proof_ids if item):
        proof = available.get(proof_id)
        if not proof:
            errors.append(f"required decision proof missing: {proof_id}")
            continue
        result = decision_graph.question_calculus.prove_answer(proof)
        if result.get("status") != "pass" or proof.get("status") != "accepted":
            errors.append(f"required decision proof is not accepted: {proof_id}")
            continue
        proofs.append(proof)
    return proofs, errors


def accepted_inference_proofs(items: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return accepted inference proof packets from request input."""
    proofs: list[dict[str, Any]] = []
    errors: list[str] = []
    derived = {fact.get("fact_id"): fact for fact in workflow_inference.derive().get("facts", []) if isinstance(fact, dict)}
    for item in items:
        if isinstance(item, str):
            fact = derived.get(item)
            if not fact or fact.get("confidence") != "accepted":
                errors.append(f"inference proof is not accepted: {item}")
                continue
            proofs.append(fact)
            continue
        if not isinstance(item, dict):
            errors.append("inference proof must be a string id or object")
            continue
        confidence = item.get("confidence", item.get("status"))
        if confidence != "accepted":
            errors.append(f"inference proof is not accepted: {item.get('proof_id')}")
            continue
        proofs.append(dict(item))
    return sorted(proofs, key=lambda row: str(row.get("proof_id") or row.get("fact_id"))), errors


def full_read_proved(
    request: dict[str, Any],
    inference_proofs: list[dict[str, Any]],
    accepted_proof_ids: set[str],
    context_id: str,
    path: str,
) -> bool:
    """Return true when accepted question proof and inference proof authorize L4."""
    if not request.get("allow_full_file_read"):
        return False
    role_id = str(request.get("role_id"))
    targets = {context_id, path, role_id, "*"}
    for proof in inference_proofs:
        predicate = str(proof.get("predicate", ""))
        args = {str(item) for item in proof.get("arguments", [])}
        proof_trace = {str(item) for item in proof.get("proof_trace", [])}
        question_proved = bool(proof_trace & accepted_proof_ids)
        if predicate in FULL_READ_PREDICATES and question_proved and (context_id in args or path in args or "*" in args):
            if not args.isdisjoint(targets):
                return True
    return False


def selected_context(
    record: dict[str, Any],
    level: str,
    request: dict[str, Any],
    inference_proofs: list[dict[str, Any]],
    accepted_proof_ids: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Convert one fresh file-context record to a bounded prompt context item."""
    errors: list[str] = []
    path = str(record.get("path"))
    context_id = str(record.get("context_id"))
    if record.get("status") == "stale" or file_context_index.record_is_stale(record):
        return None, [f"selected context is stale: {context_id}"]
    if level not in LEVEL_ORDER:
        return None, [f"unknown context level: {level}"]
    symbols = sorted(set(record.get("functions", []) + record.get("classes", []))) if LEVEL_ORDER[level] >= 3 else []
    full_content: str | None = None
    if level == "L4":
        if not full_read_proved(request, inference_proofs, accepted_proof_ids, context_id, path):
            return None, [f"full-file read lacks accepted proof: {context_id}"]
        full_content = file_context_index.source_path(path).read_text(encoding="utf-8")
    item = {
        "context_id": context_id,
        "path": path,
        "level": level if LEVEL_ORDER[level] >= 2 else "L2",
        "source_hash": str(record.get("source_hash")),
        "summary": str(record.get("purpose")),
        "public_interfaces": sorted(str(row) for row in record.get("public_interfaces", [])),
        "symbols": symbols,
        "contracts": sorted(str(row) for row in record.get("contracts", [])),
        "policy": {
            "read_policy": record.get("read_policy"),
            "write_policy": record.get("write_policy"),
            "prompt_hints": sorted(str(row) for row in record.get("prompt_hints", [])),
        },
        "full_file_content": full_content,
    }
    return item, errors


def load_decision_graph(request: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate the request decision graph."""
    graph_path = resolve_path(str(request.get("decision_graph", "")))
    if not graph_path.exists():
        return None, [f"decision graph missing: {request.get('decision_graph')}"]
    graph = decision_graph.normalize_graph(load_json(graph_path))
    errors = decision_graph.validate_graph(graph)
    return graph, errors


def build_context_pack(request: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic context pack or a fail-closed blocked packet."""
    errors = validate_json_schema(request, REQUEST_SCHEMA, "prompt-compile-request")
    graph: dict[str, Any] = {}
    if not errors:
        loaded_graph, graph_errors = load_decision_graph(request)
        errors.extend(graph_errors)
        graph = loaded_graph or {}
    facts, fact_errors = accepted_fact_refs(graph)
    decision_proofs, proof_errors = accepted_decision_proofs(graph)
    inference_proofs, inference_errors = accepted_inference_proofs(list(request.get("inference_proofs", [])))
    profile, role_errors = role_profile(str(request.get("role_id", "")))
    errors.extend(fact_errors + proof_errors + inference_errors + role_errors)

    default_level = request_level(request)
    accepted_proof_ids = {str(row.get("proof_id")) for row in decision_proofs if row.get("proof_id")}
    records_by_id = {row.get("context_id"): row for row in file_context_index.index_packet().get("records", []) if isinstance(row, dict)}
    contexts: list[dict[str, Any]] = []
    for raw in request.get("context_ids", []):
        context_id, level = context_request_item(raw, default_level)
        if LEVEL_ORDER.get(level, 0) < 2:
            continue
        record = records_by_id.get(context_id)
        if not record:
            errors.append(f"selected context missing: {context_id}")
            continue
        item, item_errors = selected_context(record, level, request, inference_proofs, accepted_proof_ids)
        errors.extend(item_errors)
        if item:
            contexts.append(item)

    gates = {"unlocked": sorted(str(row) for row in graph.get("unlocked_gates", [])), "blocked": sorted(str(row) for row in graph.get("blocked_gates", []))}
    packet = {
        "schema": "bears-context-pack.v1",
        "status": "blocked" if errors else "pass",
        "goal_id": str(request.get("goal_id", "")),
        "role_id": str(request.get("role_id", "")),
        "execution_unit": request.get("execution_unit"),
        "context_level": default_level,
        "max_tokens": int(request.get("max_tokens") or 1),
        "token_estimate": 0,
        "required_outputs": sorted(str(row) for row in request.get("required_outputs", [])),
        "accepted_facts": facts,
        "accepted_proofs": decision_proofs,
        "inference_proofs": inference_proofs,
        "selected_contexts": sorted(contexts, key=lambda row: (row["path"], row["context_id"])),
        "gates": gates,
        "role_profile": profile,
        "errors": sorted(set(errors)),
    }
    packet["token_estimate"] = estimate_tokens({key: value for key, value in packet.items() if key != "token_estimate"})
    if packet["token_estimate"] > packet["max_tokens"]:
        packet["status"] = "blocked"
        packet["errors"] = sorted(set(packet["errors"] + ["context budget exceeded"]))
    schema_errors = validate_json_schema(packet, PACK_SCHEMA, "context-pack")
    if schema_errors:
        packet["status"] = "blocked"
        packet["errors"] = sorted(set(packet["errors"] + schema_errors))
    return packet


def command_validate(_: argparse.Namespace) -> int:
    """CLI handler for static prompt compiler validation."""
    errors = validate_catalog()
    packet = {"schema": "bears-context-pack-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
    print(dump_json(packet))
    return 0 if not errors else 1


def command_build(args: argparse.Namespace) -> int:
    """CLI handler that builds a context pack from a request path."""
    request = load_json(resolve_path(args.request))
    packet = build_context_pack(request)
    print(dump_json(packet))
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the context-pack CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    build = sub.add_parser("build")
    build.add_argument("--request", required=True)
    build.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the context-pack CLI."""
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return command_validate(args)
    if args.command == "build":
        return command_build(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
