#!/usr/bin/env python3
"""Validate compact Bears /goal prompt contracts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

IDEAL_LIMIT = 500
NORMAL_LIMIT = 2000
MAX_LIMIT = 4000

REQUIRED_PATTERNS = {
    "goal_prefix": re.compile(r"^\s*/goal\b", re.IGNORECASE),
    "truth": re.compile(r"\bTruth\s*:", re.IGNORECASE),
    "done": re.compile(r"\bDone\s*(?:when)?\s*:", re.IGNORECASE),
    "validate": re.compile(r"\bValidate\s*:", re.IGNORECASE),
    "forbidden": re.compile(r"\bForbidden\s*:", re.IGNORECASE),
}

SECRET_LIKE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\b(?:password|token|secret)\s*=\s*[^\s,;]+", re.IGNORECASE),
]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    character_count: int
    band: str
    errors: list[str]
    warnings: list[str]


def _band(count: int) -> str:
    if count <= IDEAL_LIMIT:
        return "ideal"
    if count <= NORMAL_LIMIT:
        return "normal_edge"
    if count <= MAX_LIMIT:
        return "extended_max"
    return "over_max"


def _missing(patterns: dict[str, re.Pattern[str]], text: str) -> list[str]:
    return [name for name, pattern in patterns.items() if not pattern.search(text)]


def validate_text(text: str, *, reason: str = "", allow_extended: bool = False) -> ValidationResult:
    count = len(text)
    errors: list[str] = []
    warnings: list[str] = []

    for name in _missing(REQUIRED_PATTERNS, text):
        errors.append(f"missing required field: {name}")

    if count > MAX_LIMIT:
        errors.append(f"prompt exceeds {MAX_LIMIT} characters")
    elif count > NORMAL_LIMIT and not allow_extended:
        errors.append(f"prompt exceeds {NORMAL_LIMIT} characters without --allow-extended")
    elif count > IDEAL_LIMIT:
        warnings.append(f"prompt exceeds ideal {IDEAL_LIMIT} characters")

    if count > IDEAL_LIMIT and not reason.strip():
        errors.append(f"prompt exceeds {IDEAL_LIMIT} characters without --reason")

    for pattern in SECRET_LIKE_PATTERNS:
        if pattern.search(text):
            errors.append("secret-like value detected")
            break

    return ValidationResult(
        ok=not errors,
        character_count=count,
        band=_band(count),
        errors=errors,
        warnings=warnings,
    )


def _self_test_cases() -> Iterable[tuple[str, dict[str, object], bool]]:
    compact = (
        "/goal Harden skill. Truth: /srv/bears/plugins/bears/skills/bears-goal-prompt/SKILL.md. "
        "Done: validator and docs pass. Validate: python3 skills/bears-goal-prompt/scripts/validate_goal_prompt.py --prompt-file /tmp/goal.txt --json. "
        "Forbidden: secrets, runtime edits, broad scope."
    )
    too_long = "/goal " + "x" * 4010 + " Truth: x. Done: x. Validate: x. Forbidden: x."
    missing = "/goal Do work. Truth: file. Done: tests. Validate: tests."
    edge = compact + " A" * 500
    yield compact, {}, True
    yield too_long, {"allow_extended": True, "reason": "max-boundary test"}, False
    yield missing, {}, False
    yield edge, {}, False
    yield edge, {"reason": "validator coverage"}, True


def run_self_test() -> int:
    failed: list[str] = []
    for index, (text, kwargs, expected) in enumerate(_self_test_cases(), start=1):
        result = validate_text(text, **kwargs)
        if result.ok is not expected:
            failed.append(f"case {index}: expected {expected}, got {result.ok}, errors={result.errors}")
    if failed:
        for line in failed:
            print(line, file=sys.stderr)
        return 1
    print("self-test passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Bears /goal prompt contract.")
    parser.add_argument("--prompt-file", type=Path, help="File containing the prompt text.")
    parser.add_argument("--reason", default="", help="Required reason for prompts over 500 characters.")
    parser.add_argument("--allow-extended", action="store_true", help="Allow 2001-4000 character prompts.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--self-test", action="store_true", help="Run built-in validator self-tests.")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()
    if not args.prompt_file:
        parser.error("--prompt-file is required unless --self-test is used")

    text = args.prompt_file.read_text(encoding="utf-8")
    result = validate_text(text, reason=args.reason, allow_extended=args.allow_extended)
    payload = {
        "ok": result.ok,
        "character_count": result.character_count,
        "band": result.band,
        "errors": result.errors,
        "warnings": result.warnings,
        "reason": args.reason,
        "limits": {"ideal": IDEAL_LIMIT, "normal": NORMAL_LIMIT, "max": MAX_LIMIT},
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if result.ok else "FAIL")
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
