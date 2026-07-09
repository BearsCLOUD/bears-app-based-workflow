#!/usr/bin/env python3
"""Classify and clean safe local @bears workspace artifacts."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
POLICY = PLUGIN_ROOT / "assets/catalog/workspace-hygiene.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/workspace-hygiene.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/workspace_hygiene/good/minimal.json"
BAD = PLUGIN_ROOT / "tests/fixtures/workspace_hygiene/bad/tracked-cleanup.json"
ARTIFACT_REGISTRY = PLUGIN_ROOT / "assets/catalog/artifact-registry.v1.json"
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")
FORBIDDEN_PATH_MARKERS = (".env", "secret", "credential", "raw-log", "raw-chat", "raw-vpn", "production-data")
SCAN_ROOTS = ("runtime", ".pytest_cache", ".ruff_cache", "tmp", ".tmp")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./").strip("/")


def classes(policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in policy.get("classes", []) if isinstance(item, dict)]


def match_class(path: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    target = normalize(path)
    for item in classes(policy):
        for pattern in item.get("path_patterns", []):
            pat = normalize(str(pattern))
            if fnmatch.fnmatchcase(target, pat):
                return item
            if pat.endswith("/**"):
                root = pat[:-3].rstrip("/")
                if target == root or target.startswith(root + "/"):
                    return item
    return None


def git_output(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20, env=clean_env())
    return proc.returncode, proc.stdout.strip()


def tracked_paths() -> set[str]:
    code, output = git_output(["ls-files"])
    return {normalize(line) for line in output.splitlines() if line.strip()} if code == 0 else set()


def ignored_paths() -> set[str]:
    code, output = git_output(["status", "--ignored", "--porcelain", "--untracked-files=all"])
    paths: set[str] = set()
    if code != 0:
        return paths
    for line in output.splitlines():
        if line.startswith("!! ") or line.startswith("?? "):
            paths.add(normalize(line[3:]))
    return paths


def is_safe_cleanup_path(path: str) -> bool:
    target = normalize(path).casefold()
    if not target or target in {".", "/"}:
        return False
    if target.startswith("/") or ".." in target.split("/"):
        return False
    return not any(marker in target for marker in FORBIDDEN_PATH_MARKERS)


def record_errors(policy: dict[str, Any]) -> list[str]:
    errors = validate_json_schema(policy, SCHEMA, "workspace-hygiene")
    seen: set[str] = set()
    for index, item in enumerate(classes(policy)):
        cid = str(item.get("class_id"))
        if cid in seen:
            errors.append(f"classes[{index}] duplicate class_id: {cid}")
        seen.add(cid)
        if item.get("git_tracked") is True and item.get("cleanup_policy") != "preserve":
            errors.append(f"classes[{index}] tracked class must use preserve cleanup_policy")
        if item.get("lifecycle_class") == "generated_tracked" and not item.get("source_of_truth"):
            errors.append(f"classes[{index}] generated_tracked class missing source_of_truth")
        for pattern in item.get("path_patterns", []):
            if not is_safe_cleanup_path(str(pattern).replace("**", "item")) and item.get("cleanup_policy") != "preserve":
                errors.append(f"classes[{index}] unsafe cleanup pattern: {pattern}")
    return errors


def registry_agreement_errors(policy: dict[str, Any]) -> list[str]:
    if not ARTIFACT_REGISTRY.exists():
        return []
    registry = load(ARTIFACT_REGISTRY)
    errors: list[str] = []
    for record in registry.get("records", []):
        if not isinstance(record, dict):
            continue
        path = str(record.get("path", ""))
        klass = match_class(path, policy)
        if record.get("git_tracked") is False and klass is None:
            errors.append(f"untracked registry path lacks hygiene class: {path}")
        if record.get("git_tracked") is True and klass and klass.get("git_tracked") is False:
            errors.append(f"tracked registry path matches untracked hygiene class: {path}")
    return errors


def validate_policy(path: Path = POLICY) -> list[str]:
    policy = load(path)
    errors = record_errors(policy)
    if path == POLICY:
        errors.extend(registry_agreement_errors(policy))
    return errors


def validate_all() -> list[str]:
    errors = validate_policy(POLICY)
    good_errors = validate_policy(GOOD)
    errors.extend(f"good fixture failed: {item}" for item in good_errors)
    if not validate_policy(BAD):
        errors.append("bad fixture unexpectedly passed")
    return errors


def scan_entries(limit: int = 200) -> list[dict[str, Any]]:
    policy = load(POLICY)
    tracked = tracked_paths()
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for root_name in SCAN_ROOTS:
        root = PLUGIN_ROOT / root_name
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if len(entries) >= limit:
                return entries
            rel = normalize(path.relative_to(PLUGIN_ROOT).as_posix())
            if rel in seen:
                continue
            seen.add(rel)
            klass = match_class(rel, policy)
            entries.append({
                "path": rel,
                "class_id": klass.get("class_id") if klass else "unclassified",
                "lifecycle_class": klass.get("lifecycle_class") if klass else "unclassified",
                "git_tracked": rel in tracked,
                "age_seconds": max(0, int(time.time() - path.stat().st_mtime)) if path.exists() else 0,
            })
    return entries


def stale_entries() -> list[dict[str, Any]]:
    policy = load(POLICY)
    stale: list[dict[str, Any]] = []
    for entry in scan_entries():
        klass = match_class(entry["path"], policy)
        ttl = klass.get("ttl_seconds") if klass else None
        if isinstance(ttl, int) and entry["age_seconds"] > ttl:
            item = dict(entry)
            item["ttl_seconds"] = ttl
            stale.append(item)
    return stale


def cleanup_plan() -> dict[str, Any]:
    policy = load(POLICY)
    tracked = tracked_paths()
    candidates: list[dict[str, Any]] = []
    for entry in stale_entries():
        klass = match_class(entry["path"], policy)
        if not klass:
            continue
        allowed = klass.get("cleanup_policy") == "allow_apply_with_allow_path" and entry["path"] not in tracked and is_safe_cleanup_path(entry["path"])
        candidates.append({"path": entry["path"], "class_id": entry["class_id"], "action": "remove", "apply_allowed": allowed})
    return {"schema": "bears-workspace-hygiene-cleanup-plan.v1", "status": "pass", "candidates": candidates, "dry_run_default": True}


def cleanup_path(path: str, *, apply: bool) -> dict[str, Any]:
    rel = normalize(path)
    policy = load(POLICY)
    tracked = tracked_paths()
    klass = match_class(rel, policy)
    errors: list[str] = []
    if rel in tracked:
        errors.append("refuses tracked file")
    if not klass:
        errors.append("path has no hygiene class")
    elif klass.get("git_tracked") is True:
        errors.append("refuses tracked file")
    elif klass.get("cleanup_policy") != "allow_apply_with_allow_path":
        errors.append("class cleanup_policy does not allow apply")
    if not is_safe_cleanup_path(rel):
        errors.append("unsafe cleanup path")
    target = (PLUGIN_ROOT / rel).resolve()
    if not str(target).startswith(str(PLUGIN_ROOT.resolve()) + os.sep):
        errors.append("path outside plugin root")
    if errors:
        return {"schema": "bears-workspace-hygiene-cleanup.v1", "status": "fail", "path": rel, "applied": False, "errors": errors}
    if apply and target.exists():
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    return {"schema": "bears-workspace-hygiene-cleanup.v1", "status": "pass", "path": rel, "applied": bool(apply), "errors": []}


def command_validate(args: argparse.Namespace) -> int:
    errors = validate_all()
    print(json.dumps({"schema": "bears-workspace-hygiene-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_scan(args: argparse.Namespace) -> int:
    entries = scan_entries()
    packet = {"schema": "bears-workspace-hygiene-scan.v1", "status": "pass", "entries": entries, "entry_count": len(entries), "truncated": len(entries) >= 200}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def command_plan(args: argparse.Namespace) -> int:
    print(json.dumps(cleanup_plan(), indent=2, sort_keys=True))
    return 0


def command_stale(args: argparse.Namespace) -> int:
    entries = stale_entries()
    packet = {"schema": "bears-workspace-hygiene-stale.v1", "status": "pass", "stale_count": len(entries), "stale": entries[:50], "truncated": len(entries) > 50}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def command_cleanup(args: argparse.Namespace) -> int:
    packet = cleanup_path(args.allow_path, apply=bool(args.apply))
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=command_validate)
    scan = sub.add_parser("scan")
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=command_scan)
    plan = sub.add_parser("plan-cleanup")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)
    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("--apply", action="store_true")
    cleanup.add_argument("--allow-path", required=True)
    cleanup.set_defaults(func=command_cleanup)
    stale = sub.add_parser("check-stale")
    stale.add_argument("--json", action="store_true")
    stale.set_defaults(func=command_stale)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
