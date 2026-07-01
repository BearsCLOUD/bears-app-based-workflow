#!/usr/bin/env python3
"""Normalize and validate repo-qualified GitHub issue references for @Bears."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PLUGIN_ROOT / "assets/schemas/github-issue-ref.v1.schema.json"
POLICY = PLUGIN_ROOT / "assets/catalog/github-issue-ref-policy.v1.json"
GOOD_FIXTURES = PLUGIN_ROOT / "tests/fixtures/github_issue_ref/good"
BAD_FIXTURES = PLUGIN_ROOT / "tests/fixtures/github_issue_ref/bad"
PACKET_SCHEMA = "bears-github-issue-ref.v1"
POLICY_SCHEMA = "bears-github-issue-ref-policy.v1"
FIXTURE_SCHEMA = "bears-github-issue-ref-fixture.v1"
VERSION = "1"
STATES = ("resolved", "proposed", "unresolved", "blocked")
PASS_STATES = {"resolved", "proposed", "unresolved"}
REPO_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)$")
FULL_REF_RE = re.compile(r"^(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(?P<number>[1-9][0-9]*)$")
LOCAL_REF_RE = re.compile(r"^#(?P<number>[1-9][0-9]*)$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(packet: Any) -> str:
    return json.dumps(packet, indent=2, sort_keys=True) + "\n"


def split_repo(repo: str | None) -> tuple[str | None, str | None]:
    if repo is None:
        return None, None
    match = REPO_RE.match(repo)
    if not match:
        return None, None
    return match.group("owner"), match.group("repo")


def github_url(repo: str, issue_number: int) -> str:
    return f"https://github.com/{repo}/issues/{issue_number}"


def empty_packet(state: str = "blocked", *, status: str = "blocked") -> dict[str, Any]:
    return {
        "schema": PACKET_SCHEMA,
        "version": VERSION,
        "repo": None,
        "owner": None,
        "repo_name": None,
        "issue_number": None,
        "canonical_ref": None,
        "github_url": None,
        "state": state,
        "source_snapshot_ref": None,
        "source_snapshot_sha256": None,
        "legacy_local_ref": None,
        "status": status,
    }


def normalize_issue_ref(
    *,
    ref: str | None = None,
    repo: str | None = None,
    issue: int | str | None = None,
    state: str = "resolved",
    source_snapshot_ref: str | None = None,
    source_snapshot_sha256: str | None = None,
) -> dict[str, Any]:
    """Return the canonical packet for a repo-qualified issue reference.

    The function is static and never calls GitHub.
    """
    packet = empty_packet(state=state, status="pass" if state in PASS_STATES else "blocked")
    packet["source_snapshot_ref"] = source_snapshot_ref
    packet["source_snapshot_sha256"] = source_snapshot_sha256

    if state not in STATES:
        packet["state"] = "blocked"
        packet["status"] = "blocked"
        return packet
    if state == "unresolved":
        packet["status"] = "pass"
        return packet

    issue_number: int | None = None
    explicit_repo = repo
    legacy_local_ref: str | None = None

    if ref:
        full = FULL_REF_RE.match(ref)
        local = LOCAL_REF_RE.match(ref)
        if full:
            explicit_repo = full.group("repo")
            issue_number = int(full.group("number"))
        elif local:
            legacy_local_ref = ref
            if explicit_repo is None:
                packet["state"] = "blocked"
                packet["status"] = "blocked"
                packet["legacy_local_ref"] = legacy_local_ref
                return packet
            issue_number = int(local.group("number"))
        else:
            packet["state"] = "blocked"
            packet["status"] = "blocked"
            return packet

    if issue is not None:
        try:
            issue_number = int(issue)
        except (TypeError, ValueError):
            packet["state"] = "blocked"
            packet["status"] = "blocked"
            return packet
        if issue_number < 1:
            packet["state"] = "blocked"
            packet["status"] = "blocked"
            return packet

    owner, repo_name = split_repo(explicit_repo)
    if explicit_repo is None or owner is None or repo_name is None:
        packet["state"] = "blocked"
        packet["status"] = "blocked"
        return packet

    packet["repo"] = explicit_repo
    packet["owner"] = owner
    packet["repo_name"] = repo_name
    packet["legacy_local_ref"] = legacy_local_ref

    if state == "proposed":
        if issue_number is not None:
            packet["state"] = "blocked"
            packet["status"] = "blocked"
        return packet

    if issue_number is None:
        packet["state"] = "blocked"
        packet["status"] = "blocked"
        return packet

    packet["issue_number"] = issue_number
    packet["canonical_ref"] = f"{explicit_repo}#{issue_number}"
    packet["github_url"] = github_url(explicit_repo, issue_number)
    return packet


def validate_policy(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if packet.get("schema") != POLICY_SCHEMA:
        errors.append("policy.schema must be bears-github-issue-ref-policy.v1")
    if packet.get("version") != VERSION:
        errors.append("policy.version must be 1")
    allowed_states = packet.get("allowed_states")
    if allowed_states != list(STATES):
        errors.append("policy.allowed_states must list resolved, proposed, unresolved, blocked")
    contract = packet.get("contract", {})
    if not isinstance(contract, dict):
        errors.append("policy.contract must be an object")
    else:
        for field in ("schema_path", "script_path", "doc_path"):
            value = contract.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"policy.contract.{field} must be a non-empty path")
            elif not (PLUGIN_ROOT / value).exists():
                errors.append(f"policy.contract.{field} path does not exist: {value}")
    local_policy = packet.get("local_ref_policy", {})
    if not isinstance(local_policy, dict) or local_policy.get("allowed_only_when_repo_is_explicit") is not True:
        errors.append("policy.local_ref_policy.allowed_only_when_repo_is_explicit must be true")
    validation = packet.get("validation", {})
    commands = validation.get("commands") if isinstance(validation, dict) else None
    required = {
        "python3 scripts/github_issue_ref.py validate",
        "python3 scripts/github_issue_ref.py normalize --ref BearsCLOUD/bears_plugin#424 --json",
        "python3 scripts/github_issue_ref.py normalize --repo BearsCLOUD/bears-platform --issue 66 --json",
        "python3 scripts/github_issue_ref.py compare --left BearsCLOUD/bears-platform#66 --right BearsCLOUD/bears-infra#66 --json",
    }
    if not isinstance(commands, list) or not required.issubset({str(item) for item in commands}):
        errors.append("policy.validation.commands must include required github_issue_ref.py commands")
    return errors


def validate_packet(packet: dict[str, Any], *, label: str = "packet") -> list[str]:
    errors = validate_json_schema(packet, SCHEMA, label)
    if errors:
        return errors

    state = packet["state"]
    status = packet["status"]
    repo = packet["repo"]
    issue_number = packet["issue_number"]
    canonical_ref = packet["canonical_ref"]
    url = packet["github_url"]
    owner, repo_name = split_repo(repo)

    if state == "blocked":
        if status != "blocked":
            errors.append(f"{label}.status: blocked state requires blocked status")
        return errors
    if status != "pass":
        errors.append(f"{label}.status: {state} state requires pass status")

    if packet["source_snapshot_sha256"] is not None and not SHA256_RE.match(packet["source_snapshot_sha256"]):
        errors.append(f"{label}.source_snapshot_sha256: must be lowercase sha256 or null")

    if state == "unresolved":
        for field in ("repo", "owner", "repo_name", "issue_number", "canonical_ref", "github_url", "legacy_local_ref"):
            if packet[field] is not None:
                errors.append(f"{label}.{field}: unresolved state requires null")
        return errors

    if repo is None or owner is None or repo_name is None:
        errors.append(f"{label}.repo: {state} state requires explicit owner/repo")
        return errors
    if packet["owner"] != owner:
        errors.append(f"{label}.owner: must match repo owner")
    if packet["repo_name"] != repo_name:
        errors.append(f"{label}.repo_name: must match repo name")

    if state == "proposed":
        for field in ("issue_number", "canonical_ref", "github_url", "legacy_local_ref"):
            if packet[field] is not None:
                errors.append(f"{label}.{field}: proposed state requires null")
        return errors

    if issue_number is None:
        errors.append(f"{label}.issue_number: resolved state requires issue number")
        return errors
    expected_ref = f"{repo}#{issue_number}"
    if canonical_ref != expected_ref:
        errors.append(f"{label}.canonical_ref: must equal {expected_ref}")
    expected_url = github_url(repo, issue_number)
    if url != expected_url:
        errors.append(f"{label}.github_url: must equal {expected_url}")
    legacy = packet["legacy_local_ref"]
    if legacy is not None and legacy != f"#{issue_number}":
        errors.append(f"{label}.legacy_local_ref: must match issue number")
    return errors


def validate_fixture(packet: dict[str, Any], *, label: str) -> list[str]:
    if packet.get("schema") == PACKET_SCHEMA:
        clean_packet = dict(packet)
        clean_packet.pop("expected_error", None)
        return validate_packet(clean_packet, label=label)
    if packet.get("schema") != FIXTURE_SCHEMA:
        return [f"{label}.schema: unsupported fixture schema"]

    kind = packet.get("fixture_kind")
    if kind == "issue_ref":
        normalized = normalize_issue_ref(
            ref=packet.get("ref"),
            repo=packet.get("repo"),
            state=str(packet.get("state") or "resolved"),
        )
        errors = validate_packet(normalized, label=label)
        if normalized["status"] == "blocked":
            errors.append(f"{label}.issue_ref: blocked normalized reference")
        scope = packet.get("scope")
        if scope != "plugin_local_compat" and LOCAL_REF_RE.match(str(packet.get("ref") or "")):
            errors.append(f"{label}.issue_ref: local ref requires plugin_local_compat scope and explicit repo")
        return errors

    if kind == "generated_issue_packet":
        target_repo = packet.get("target_repo")
        target_issue = packet.get("target_issue_number_or_null")
        if not isinstance(target_repo, str) or not REPO_RE.match(target_repo):
            return [f"{label}.target_repo: explicit owner/repo is required"]
        normalized = normalize_issue_ref(repo=target_repo, issue=target_issue, state="resolved" if target_issue else "proposed")
        return validate_packet(normalized, label=label)

    if kind == "delivery_identity_lineage_match":
        source_ref = packet.get("source_ref")
        target_issue_ref = packet.get("target_issue_ref")
        source = normalize_issue_ref(ref=source_ref if isinstance(source_ref, str) else None)
        target = normalize_issue_ref(ref=target_issue_ref if isinstance(target_issue_ref, str) else None)
        errors = validate_packet(source, label=f"{label}.source_ref") + validate_packet(target, label=f"{label}.target_issue_ref")
        if source.get("canonical_ref") != target.get("canonical_ref"):
            errors.append(f"{label}.source_ref: must equal normalized target_issue_ref")
        return errors

    return [f"{label}.fixture_kind: unsupported fixture kind"]


def validate_all() -> list[str]:
    errors: list[str] = []
    errors.extend(validate_policy(load(POLICY)))

    for path in sorted(GOOD_FIXTURES.glob("*.json")):
        fixture_errors = validate_fixture(load(path), label=str(path.relative_to(PLUGIN_ROOT)))
        errors.extend(fixture_errors)

    for path in sorted(BAD_FIXTURES.glob("*.json")):
        packet = load(path)
        expected = packet.get("expected_error")
        fixture_errors = validate_fixture(packet, label=str(path.relative_to(PLUGIN_ROOT)))
        if not fixture_errors:
            errors.append(f"{path.relative_to(PLUGIN_ROOT)}: bad fixture unexpectedly passed")
        elif isinstance(expected, str) and expected not in "\n".join(fixture_errors):
            errors.append(f"{path.relative_to(PLUGIN_ROOT)}: expected error not observed: {expected}")
    return errors


def compare_refs(left: str, right: str) -> dict[str, Any]:
    left_packet = normalize_issue_ref(ref=left)
    right_packet = normalize_issue_ref(ref=right)
    left_errors = validate_packet(left_packet, label="left")
    right_errors = validate_packet(right_packet, label="right")
    return {
        "schema": "bears-github-issue-ref-compare.v1",
        "version": VERSION,
        "status": "pass" if not left_errors and not right_errors else "blocked",
        "same_identity": left_packet.get("canonical_ref") is not None
        and left_packet.get("canonical_ref") == right_packet.get("canonical_ref"),
        "left": left_packet,
        "right": right_packet,
        "errors": left_errors + right_errors,
    }


def command_validate(args: argparse.Namespace) -> int:
    errors = validate_all()
    packet = {
        "schema": "bears-github-issue-ref-validation.v1",
        "version": VERSION,
        "status": "pass" if not errors else "blocked",
        "validation_mode": "static_local_read_only",
        "errors": errors,
    }
    if args.json:
        sys.stdout.write(dump(packet))
    elif errors:
        sys.stdout.write("\n".join(errors) + "\n")
    else:
        sys.stdout.write("github issue ref validation passed\n")
    return 0 if not errors else 1


def command_normalize(args: argparse.Namespace) -> int:
    packet = normalize_issue_ref(
        ref=args.ref,
        repo=args.repo,
        issue=args.issue,
        state=args.state,
        source_snapshot_ref=args.source_snapshot_ref,
        source_snapshot_sha256=args.source_snapshot_sha256,
    )
    if args.json:
        sys.stdout.write(dump(packet))
    else:
        sys.stdout.write(str(packet.get("canonical_ref") or packet.get("state")) + "\n")
    return 0 if packet["status"] == "pass" else 1


def command_compare(args: argparse.Namespace) -> int:
    packet = compare_refs(args.left, args.right)
    if args.json:
        sys.stdout.write(dump(packet))
    else:
        sys.stdout.write(("same" if packet["same_identity"] else "different") + "\n")
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate schema, policy, and local fixtures")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)

    normalize = sub.add_parser("normalize", help="normalize a GitHub issue reference")
    normalize.add_argument("--ref", help="owner/repo#number or #number when --repo is explicit")
    normalize.add_argument("--repo", help="explicit owner/repo")
    normalize.add_argument("--issue", type=int, help="positive GitHub issue number")
    normalize.add_argument("--state", choices=STATES, default="resolved")
    normalize.add_argument("--source-snapshot-ref")
    normalize.add_argument("--source-snapshot-sha256")
    normalize.add_argument("--json", action="store_true")
    normalize.set_defaults(func=command_normalize)

    compare = sub.add_parser("compare", help="compare two canonical issue identities")
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    compare.add_argument("--json", action="store_true")
    compare.set_defaults(func=command_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
