#!/usr/bin/env python3
"""Validate and query the Bears workspace dictionary."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/workspace-dictionary.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/workspace-dictionary.v1.schema.json"
COMMANDS = [
    "python3 scripts/workspace_dictionary.py validate",
    "python3 scripts/workspace_dictionary.py extract-candidates --json",
    "python3 scripts/workspace_dictionary.py canonicalize --term <term> --json",
]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_all() -> list[str]:
    errors: list[str] = []
    if not CATALOG.exists():
        return ["dictionary catalog missing"]
    if not SCHEMA.exists():
        errors.append("dictionary schema missing")
    packet = load(CATALOG)
    errors.extend(validate_json_schema(packet, SCHEMA, CATALOG.name))
    for command in COMMANDS:
        if command not in packet.get("commands", []):
            errors.append(f"missing command: {command}")
    canonical = [term.get("canonical_term") for term in packet.get("terms", [])]
    if len(canonical) != len(set(canonical)):
        errors.append("duplicate canonical term")
    forbidden = [alias for term in packet.get("terms", []) for alias in term.get("forbidden_aliases", [])]
    if any(alias in canonical for alias in forbidden):
        errors.append("forbidden alias used as canonical term")
    return errors


def canonicalize(term: str) -> dict[str, Any]:
    normalized = term.casefold().strip()
    packet = load(CATALOG)
    for row in packet.get("terms", []):
        aliases = [str(item).casefold() for item in row.get("aliases", []) + row.get("forbidden_aliases", [])]
        if normalized == str(row.get("canonical_term", "")).casefold() or normalized in aliases:
            return {"schema": "bears-workspace-dictionary-canonicalize.v1", "status": "pass", "input": term, "canonical_term": row["canonical_term"], "term_id": row["term_id"], "forbidden": normalized in [str(item).casefold() for item in row.get("forbidden_aliases", [])]}
    return {"schema": "bears-workspace-dictionary-canonicalize.v1", "status": "candidate", "input": term, "canonical_term": None, "term_id": None, "forbidden": False}


def extract_candidates() -> dict[str, Any]:
    words: Counter[str] = Counter()
    for root in (PLUGIN_ROOT / "assets/catalog", PLUGIN_ROOT / "docs/reference"):
        for path in root.glob("*.json") if root.name == "catalog" else root.glob("*.md"):
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for match in re.findall(r"\b[a-z][a-z0-9-]{4,}\b", text):
                words[match] += 1
    known = {str(row.get("canonical_term", "")).casefold() for row in load(CATALOG).get("terms", [])}
    candidates = [{"term": term, "count": count} for term, count in words.most_common(50) if count >= 2 and term not in known]
    return {"schema": "bears-workspace-dictionary-candidates.v1", "status": "pass", "candidates": candidates[:25]}


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    cand = sub.add_parser("extract-candidates")
    cand.add_argument("--json", action="store_true")
    canon = sub.add_parser("canonicalize")
    canon.add_argument("--term", required=True)
    canon.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        print_packet({"schema": "bears-workspace-dictionary-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "extract-candidates":
        print_packet(extract_candidates())
        return 0
    if args.command == "canonicalize":
        packet = canonicalize(args.term)
        print_packet(packet)
        return 0 if packet["status"] in {"pass", "candidate"} else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
