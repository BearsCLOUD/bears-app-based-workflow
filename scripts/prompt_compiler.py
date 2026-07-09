#!/usr/bin/env python3
"""Compile deterministic zero-context prompts from Bears proof context packs."""
from __future__ import annotations

import argparse
import json
import tempfile
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts import context_pack, decision_graph  # noqa: E402
from scripts.local_json_schema import validate_json_schema  # noqa: E402

CATALOG = PLUGIN_ROOT / "assets/catalog/prompt-compiler.v1.json"
RESULT_SCHEMA = PLUGIN_ROOT / "assets/schemas/prompt-compile-result.v1.schema.json"


def load_json(path: Path) -> Any:
    """Read a JSON packet from disk."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_path(value: str) -> Path:
    """Resolve a request path under the plugin checkout unless absolute."""
    path = Path(value)
    return path if path.is_absolute() else PLUGIN_ROOT / value


def output_schema() -> dict[str, Any]:
    """Return the required executor JSON output schema."""
    return dict(load_json(CATALOG)["required_output_schema"])


def compact_role_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Return role fields allowed inside a compiled prompt."""
    if not isinstance(profile, dict):
        return {}
    return {
        "profile_id": profile.get("profile_id"),
        "agent_class": profile.get("agent_class"),
        "mode": profile.get("mode"),
        "model_tier": profile.get("model_tier"),
        "permission_profile": profile.get("permission_profile", {}),
        "workspace_write_policy": profile.get("workspace_write_policy"),
        "allowed_outputs": profile.get("allowed_outputs", []),
        "denied_capabilities": profile.get("denied_capabilities", []),
        "fallback_policy": profile.get("fallback_policy"),
    }


def prompt_payload(request: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic prompt payload from a passing context pack."""
    return {
        "schema": "bears-compiled-prompt-text.v1",
        "authority": "Use only this compiled prompt packet and its context_pack fields.",
        "rules": [
            "Use accepted_facts, accepted_proofs, inference_proofs, selected_contexts, role_profile, and gates only.",
            "Do not use chat history, arbitrary markdown, issue excerpts, or unlisted files as task authority.",
            "Do not read a full file unless selected_contexts contains L4 full_file_content for that path.",
            "Return exactly one JSON object that matches required_output_schema.",
        ],
        "task": request.get("task"),
        "goal_id": pack.get("goal_id"),
        "role_id": pack.get("role_id"),
        "execution_unit": pack.get("execution_unit"),
        "required_outputs": pack.get("required_outputs", []),
        "gates": pack.get("gates", {}),
        "role_profile": compact_role_profile(pack.get("role_profile")),
        "accepted_fact_ids": sorted(str(row.get("id")) for row in pack.get("accepted_facts", []) if row.get("id")),
        "accepted_proof_ids": sorted(str(row.get("proof_id")) for row in pack.get("accepted_proofs", []) if row.get("proof_id")),
        "inference_proof_ids": sorted(str(row.get("proof_id") or row.get("fact_id")) for row in pack.get("inference_proofs", [])),
        "context_ids": sorted(str(row.get("context_id")) for row in pack.get("selected_contexts", [])),
        "allowed_path_hashes": [
            {"path": row.get("path"), "source_hash": row.get("source_hash"), "level": row.get("level")}
            for row in pack.get("selected_contexts", [])
        ],
        "context_pack": pack,
        "required_output_schema": output_schema(),
    }


def compile_request(request: dict[str, Any]) -> dict[str, Any]:
    """Compile a prompt result from a request packet."""
    pack = context_pack.build_context_pack(request)
    pack_hash = context_pack.canonical_hash(pack)
    prompt_id = f"prompt:{request.get('goal_id')}:{request.get('role_id')}:{pack_hash[:16]}"
    errors = list(pack.get("errors", []))
    if pack.get("status") != "pass":
        result = {
            "schema": "bears-prompt-compile-result.v1",
            "status": "blocked",
            "prompt_id": prompt_id,
            "prompt_hash": context_pack.canonical_hash({"blocked": errors, "context_pack_hash": pack_hash}),
            "goal_id": str(request.get("goal_id", "")),
            "role_id": str(request.get("role_id", "")),
            "execution_unit": request.get("execution_unit"),
            "context_pack_hash": pack_hash,
            "max_tokens": int(request.get("max_tokens") or 1),
            "token_estimate": int(pack.get("token_estimate") or 0),
            "prompt_text": "",
            "required_output_schema": output_schema(),
            "metadata": {"context_pack_status": pack.get("status"), "context_pack_errors": errors},
            "errors": sorted(set(errors)),
        }
    else:
        payload = prompt_payload(request, pack)
        prompt_text = context_pack.dump_json(payload)
        prompt_hash = context_pack.canonical_hash(prompt_text)
        result = {
            "schema": "bears-prompt-compile-result.v1",
            "status": "pass",
            "prompt_id": prompt_id,
            "prompt_hash": prompt_hash,
            "goal_id": str(request.get("goal_id", "")),
            "role_id": str(request.get("role_id", "")),
            "execution_unit": request.get("execution_unit"),
            "context_pack_hash": pack_hash,
            "max_tokens": int(request.get("max_tokens")),
            "token_estimate": context_pack.estimate_tokens(prompt_text),
            "prompt_text": prompt_text,
            "required_output_schema": output_schema(),
            "metadata": {
                "compiler_catalog_hash": context_pack.canonical_hash(load_json(CATALOG)),
                "decision_graph": request.get("decision_graph"),
                "context_ids": payload["context_ids"],
                "accepted_proof_ids": payload["accepted_proof_ids"],
                "inference_proof_ids": payload["inference_proof_ids"],
                "allowed_path_hashes": payload["allowed_path_hashes"],
            },
            "errors": [],
        }
        if result["token_estimate"] > result["max_tokens"]:
            result["status"] = "blocked"
            result["prompt_text"] = ""
            result["errors"] = ["prompt budget exceeded"]
            result["prompt_hash"] = context_pack.canonical_hash({"blocked": result["errors"], "context_pack_hash": pack_hash})
    schema_errors = validate_json_schema(result, RESULT_SCHEMA, "prompt-compile-result")
    if schema_errors:
        result["status"] = "blocked"
        result["prompt_text"] = ""
        result["errors"] = sorted(set(result["errors"] + schema_errors))
        result["prompt_hash"] = context_pack.canonical_hash({"blocked": result["errors"], "context_pack_hash": pack_hash})
    return result


def diff_results(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """Compare two prompt compile result packets deterministically."""
    changed_fields = []
    for field in ("status", "prompt_hash", "context_pack_hash", "token_estimate", "required_output_schema"):
        if base.get(field) != head.get(field):
            changed_fields.append(field)
    return {
        "schema": "bears-prompt-compile-diff.v1",
        "status": "pass",
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "base_prompt_hash": base.get("prompt_hash"),
        "head_prompt_hash": head.get("prompt_hash"),
        "token_delta": int(head.get("token_estimate") or 0) - int(base.get("token_estimate") or 0),
    }


def doctor_packet() -> dict[str, Any]:
    """Run static validation and one zero-context compile smoke check."""
    errors = context_pack.validate_catalog()
    smoke_status = "blocked"
    if not errors:
        graph = decision_graph.build_graph("goal-441-doctor")
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=True) as handle:
            json.dump(graph, handle, sort_keys=True)
            handle.flush()
            request = {
                "schema": "bears-prompt-compile-request.v1",
                "goal_id": "goal-441-doctor",
                "role_id": "oc_reviewer",
                "execution_unit": None,
                "task": "Run prompt compiler doctor smoke compile.",
                "required_outputs": ["JSON doctor packet"],
                "decision_graph": handle.name,
                "inference_proofs": [],
                "context_ids": [],
                "max_tokens": 4096,
                "allow_full_file_read": False,
                "context_level": "L1",
            }
            result = compile_request(request)
        smoke_status = result["status"]
        errors.extend(result.get("errors", []))
    return {
        "schema": "bears-prompt-compiler-doctor.v1",
        "status": "pass" if not errors and smoke_status == "pass" else "fail",
        "prompt_compiler_status": "pass" if not errors and smoke_status == "pass" else "fail",
        "smoke_compile_status": smoke_status,
        "errors": sorted(set(errors)),
    }


def command_compile(args: argparse.Namespace) -> int:
    """CLI handler for prompt compilation."""
    result = compile_request(load_json(resolve_path(args.request)))
    print(context_pack.dump_json(result))
    return 0 if result["status"] == "pass" else 1


def command_diff(args: argparse.Namespace) -> int:
    """CLI handler for prompt compile result diffs."""
    packet = diff_results(load_json(resolve_path(args.base)), load_json(resolve_path(args.head)))
    print(context_pack.dump_json(packet))
    return 0


def command_doctor(_: argparse.Namespace) -> int:
    """CLI handler for prompt compiler doctor."""
    packet = doctor_packet()
    print(context_pack.dump_json(packet))
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the prompt compiler CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--request", required=True)
    compile_parser.add_argument("--json", action="store_true")
    diff = sub.add_parser("diff")
    diff.add_argument("--base", required=True)
    diff.add_argument("--head", required=True)
    diff.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the prompt compiler CLI."""
    args = build_parser().parse_args(argv)
    if args.command == "compile":
        return command_compile(args)
    if args.command == "diff":
        return command_diff(args)
    if args.command in {"doctor", "validate"}:
        return command_doctor(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
