#!/usr/bin/env python3
"""Build and validate bounded file-context records for goal orchestration."""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
INDEX = PLUGIN_ROOT / "assets/file-context/index.v1.json"
POLICY = PLUGIN_ROOT / "assets/catalog/file-context-policy.v1.json"
RECORD_SCHEMA = PLUGIN_ROOT / "assets/schemas/file-context.v1.schema.json"
INDEX_SCHEMA = PLUGIN_ROOT / "assets/schemas/file-context-index.v1.schema.json"
REFRESH_SCHEMA = PLUGIN_ROOT / "assets/schemas/file-context-refresh.v1.schema.json"
DECISION_LEDGER = PLUGIN_ROOT / "assets/catalog/decision-ledger.v1.json"
ROADMAP = PLUGIN_ROOT / "assets/catalog/workflow-roadmap.v1.json"
OWNER_ROLE = "bears-machine-first-execution-kernel-engineer"
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def utc_today() -> str:
    """Return the current UTC date for durable catalog packets."""
    return datetime.now(timezone.utc).date().isoformat()


def clean_env() -> dict[str, str]:
    """Return a git-safe environment without inherited hook variables."""
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> dict[str, Any]:
    """Read a JSON object from a repository path."""
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, packet: dict[str, Any]) -> None:
    """Write a sorted JSON packet to a repository path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    """Render a plugin-root-relative path when possible."""
    try:
        return path.resolve().relative_to(PLUGIN_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize(path: str) -> str:
    """Normalize a path for catalog matching."""
    return path.replace("\\", "/").strip().strip("/")


def source_path(path: str) -> Path:
    """Resolve a repository-relative source path."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PLUGIN_ROOT / normalize(path)


def sha256(path: Path) -> str:
    """Hash a source file for stale detection."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Hash already-read source bytes for git-index validation."""
    return hashlib.sha256(data).hexdigest()


def git_index_bytes(path_value: str) -> bytes | None:
    """Return the git-index blob for a repository path when it is tracked."""
    item = normalize(path_value)
    try:
        proc = subprocess.run(
            ["git", "show", f":{item}"],
            cwd=PLUGIN_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
            env=clean_env(),
        )
    except subprocess.TimeoutExpired:
        return None
    return proc.stdout if proc.returncode == 0 else None


def validation_source_hash(path_value: str) -> str | None:
    """Return the hash for commit-scoped validation, falling back to disk."""
    indexed = git_index_bytes(path_value)
    if indexed is not None:
        return sha256_bytes(indexed)
    path = source_path(path_value)
    return sha256(path) if path.exists() else None


def validation_source_exists(path_value: str) -> bool:
    """Return true when a source exists in the git index or working tree."""
    return validation_source_hash(path_value) is not None


def record_source_bytes(path_value: str) -> bytes:
    """Return bytes used to build a context record."""
    indexed = git_index_bytes(path_value)
    if indexed is not None:
        return indexed
    return source_path(path_value).read_bytes()


def record_source_text(path_value: str) -> str:
    """Return UTF-8 text used to build a context record."""
    return record_source_bytes(path_value).decode("utf-8")


def language_for(path: str) -> str:
    """Classify a file language for context policy."""
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix == ".json":
        return "json"
    if suffix == ".md":
        return "markdown"
    if suffix == ".toml":
        return "toml"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    return "other"


def context_id(path: str) -> str:
    """Create a stable context id from a repository path."""
    stem = normalize(path).replace("/", ":")
    for old, new in (("_", "-"), (".", "-")):
        stem = stem.replace(old, new)
    return "fc:" + stem


def first_docstring(tree: ast.AST) -> str:
    """Return the module docstring as a compact purpose hint."""
    text = ast.get_docstring(tree) or ""
    return text.splitlines()[0].strip() if text.strip() else "Repository file context record."


def ast_context(path: Path, text: str | None = None) -> dict[str, list[str] | str]:
    """Extract public Python symbols and imports with AST."""
    try:
        tree = ast.parse(text if text is not None else path.read_text(encoding="utf-8"))
    except SyntaxError:
        return {"purpose": "Python file requires manual review.", "functions": [], "classes": [], "imports": []}
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    return {
        "purpose": first_docstring(tree),
        "functions": sorted(set(functions)),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
    }


def json_context(path: Path, text: str | None = None) -> dict[str, Any]:
    """Extract machine-contract hints from JSON catalogs and schemas."""
    try:
        packet = json.loads(text) if text is not None else load(path)
    except Exception:
        return {"purpose": "JSON file requires manual review.", "contracts": [], "public_interfaces": []}
    schema = str(packet.get("schema") or packet.get("$id") or packet.get("$schema") or "")
    commands = [str(item) for item in packet.get("commands", []) if isinstance(item, str)]
    owner = str(packet.get("owner_role", OWNER_ROLE))
    purpose = schema or str(packet.get("title") or "JSON contract file")
    return {
        "purpose": purpose,
        "contracts": [schema] if schema else [],
        "public_interfaces": commands[:20],
        "owner_role": owner,
    }


def authority_topic_for(path: str) -> str | None:
    """Return the authority-map topic that owns a path, when declared."""
    authority = PLUGIN_ROOT / "assets/catalog/authority-map.v1.json"
    if not authority.exists():
        return None
    target = normalize(path)
    try:
        for topic in load(authority).get("topics", []):
            if not isinstance(topic, dict):
                continue
            surfaces = [topic.get("canonical_source"), *topic.get("secondary_docs", []), *topic.get("generated_outputs", [])]
            if any(normalize(str(item)) == target for item in surfaces if item):
                return str(topic.get("topic"))
    except Exception:
        return None
    return None



def decisions_by_path() -> dict[str, list[str]]:
    """Return accepted decision ids keyed by affected repository path."""
    out: dict[str, list[str]] = {}
    if not DECISION_LEDGER.exists():
        return out
    try:
        records = load(DECISION_LEDGER).get("records", [])
    except Exception:
        return out
    for record in records:
        if not isinstance(record, dict) or record.get("status") != "accepted":
            continue
        decision_id = str(record.get("decision_id", ""))
        for path in record.get("affected_paths", []):
            if isinstance(path, str) and decision_id:
                out.setdefault(normalize(path), []).append(decision_id)
    return out


def workflow_by_path() -> dict[str, list[str]]:
    """Return roadmap node ids keyed by evidence path."""
    out: dict[str, list[str]] = {}
    if not ROADMAP.exists():
        return out
    try:
        nodes = load(ROADMAP).get("nodes", [])
    except Exception:
        return out
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id", ""))
        for path in node.get("evidence_paths", []):
            if isinstance(path, str) and node_id:
                out.setdefault(normalize(path), []).append(node_id)
    return out

def build_record(path_value: str, *, role: str | None = None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build one compact context record from the current source file."""
    item = normalize(path_value)
    path = source_path(item)
    source_bytes = record_source_bytes(item)
    source_text = source_bytes.decode("utf-8")
    decisions = decisions_by_path().get(item, [])
    workflows = workflow_by_path().get(item, [])
    language = language_for(item)
    owner_role = role or OWNER_ROLE
    purpose = f"Context for {item}."
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    public_interfaces: list[str] = []
    contracts: list[str] = []
    technologies = [language]
    if language == "python":
        extracted = ast_context(path, source_text)
        purpose = str(extracted["purpose"])
        functions = list(extracted["functions"])
        classes = list(extracted["classes"])
        imports = list(extracted["imports"])
        public_interfaces = functions[:20] + classes[:20]
        technologies.append("python-ast")
    elif language == "json":
        extracted = json_context(path, source_text)
        purpose = str(extracted["purpose"])
        owner_role = str(extracted.get("owner_role") or owner_role)
        public_interfaces = list(extracted.get("public_interfaces", []))
        contracts = list(extracted.get("contracts", []))
    elif language == "markdown":
        first_heading = next((line.lstrip("# ").strip() for line in source_text.splitlines() if line.startswith("#")), "Reference document")
        purpose = first_heading
    return {
        "schema": "bears-file-context.v1",
        "context_id": str(previous.get("context_id", context_id(item))) if previous else context_id(item),
        "path": item,
        "source_hash": sha256_bytes(source_bytes),
        "language": language,
        "status": "active",
        "owner_role": str(previous.get("owner_role", owner_role)) if previous else owner_role,
        "authority_topic": (previous.get("authority_topic") if previous and previous.get("authority_topic") not in {"", "None"} else authority_topic_for(item)) if previous else authority_topic_for(item),
        "purpose": purpose,
        "technologies": sorted(set(technologies)),
        "public_interfaces": public_interfaces,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "reads": [],
        "writes": [],
        "contracts": contracts,
        "workflow_nodes": sorted(set(workflows + (previous.get("workflow_nodes", []) if previous else []))),
        "decision_refs": sorted(set(decisions + (previous.get("decision_refs", []) if previous else []))),
        "changelog_refs": previous.get("changelog_refs", []) if previous else [],
        "related_contexts": previous.get("related_contexts", []) if previous else [],
        "read_policy": previous.get("read_policy", "summary_first") if previous else "summary_first",
        "write_policy": previous.get("write_policy", "role_required" if language in {"python", "json"} else "packet_required") if previous else ("role_required" if language in {"python", "json"} else "packet_required"),
        "prompt_hints": sorted(set(["Use this context record before reading the full source file."] + (previous.get("prompt_hints", []) if previous else []))),
        "last_verified_commit": current_commit(),
    }


def current_commit() -> str | None:
    """Return the current commit sha, if git is available."""
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10, env=clean_env())
    except subprocess.TimeoutExpired:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def policy() -> dict[str, Any]:
    """Load the file-context policy catalog."""
    return load(POLICY)


def index_packet() -> dict[str, Any]:
    """Load the file-context index or return an empty packet."""
    if INDEX.exists():
        return load(INDEX)
    return {"schema": "bears-file-context-index.v1", "version": "1", "updated": utc_today(), "owner_role": OWNER_ROLE, "policy": rel(POLICY), "records": []}


def records_by_path(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map context records by normalized source path."""
    return {normalize(str(item.get("path"))): item for item in index.get("records", []) if isinstance(item, dict)}


def changed_files(range_spec: str) -> list[str]:
    """Return changed files for a git range."""
    proc = subprocess.run(["git", "diff", "--name-only", range_spec], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    return [normalize(line) for line in proc.stdout.splitlines() if line.strip()] if proc.returncode == 0 else []


def added_files(range_spec: str) -> list[str]:
    """Return added files for a git range."""
    proc = subprocess.run(["git", "diff", "--name-only", "--diff-filter=A", range_spec], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    return [normalize(line) for line in proc.stdout.splitlines() if line.strip()] if proc.returncode == 0 else []


def matches(path: str, patterns: list[str]) -> bool:
    """Return true when a path matches one of the policy globs."""
    return any(fnmatch.fnmatch(normalize(path), pattern) for pattern in patterns)


def governed(path: str) -> bool:
    """Return true when a path requires file-context coverage."""
    packet = policy()
    item = normalize(path)
    if matches(item, [str(row) for row in packet.get("exempt_path_patterns", [])]):
        return False
    return matches(item, [str(row) for row in packet.get("governed_path_patterns", [])])


def record_is_stale(record: dict[str, Any]) -> bool:
    """Return true when a record source hash no longer matches its file."""
    if record.get("status") not in {"active", "stale"}:
        return False
    expected_hash = validation_source_hash(str(record.get("path", "")))
    return expected_hash is not None and record.get("source_hash") != expected_hash


def stale_paths(index: dict[str, Any]) -> list[str]:
    """Return active context paths whose source hash no longer matches."""
    stale: list[str] = []
    for record in index.get("records", []):
        if not isinstance(record, dict) or record.get("status") not in {"active", "stale"}:
            continue
        if record_is_stale(record):
            stale.append(normalize(str(record.get("path"))))
    return sorted(set(stale))


def orphaned_paths(index: dict[str, Any]) -> list[str]:
    """Return context paths whose source file was deleted."""
    result = []
    for record in index.get("records", []):
        if isinstance(record, dict) and not validation_source_exists(str(record.get("path", ""))):
            result.append(normalize(str(record.get("path"))))
    return sorted(set(result))


def tracked_files() -> list[str]:
    """Return repository paths tracked in the git index."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
            env=clean_env(),
        )
    except subprocess.TimeoutExpired:
        return []
    return [normalize(line) for line in proc.stdout.splitlines() if line.strip()] if proc.returncode == 0 else []



def all_governed_paths() -> list[str]:
    """Return governed source paths tracked in the git index."""
    return sorted({path for path in tracked_files() if governed(path) and validation_source_exists(path)})

def missing_required_paths(index: dict[str, Any], *, from_git: str | None = None) -> list[str]:
    """Return required or newly added governed paths without context records."""
    covered = set(records_by_path(index))
    candidates = [normalize(str(path)) for path in policy().get("required_context_paths", [])]
    candidates.extend(all_governed_paths())
    if from_git:
        candidates.extend(path for path in added_files(from_git) if governed(path))
    return sorted({path for path in candidates if path not in covered and validation_source_exists(path)})


def validate_record(record: dict[str, Any], label: str) -> list[str]:
    """Validate one record schema and source consistency."""
    errors = validate_json_schema(record, RECORD_SCHEMA, label)
    source_hash = validation_source_hash(str(record.get("path", "")))
    if record.get("status") in {"active", "stale"} and source_hash is None:
        errors.append(f"{label}.path source file missing")
    if record.get("status") == "active" and source_hash is not None and record.get("source_hash") != source_hash:
        errors.append(f"{label}.source_hash stale for {record.get('path')}")
    if record.get("status") == "stale" and record.get("write_policy") != "manual_review":
        errors.append(f"{label}.write_policy stale records must use manual_review")
    return errors


def validate_index(path: Path = INDEX) -> list[str]:
    """Validate schemas, policy, index, uniqueness, freshness, and required coverage."""
    errors: list[str] = []
    for schema_path in (RECORD_SCHEMA, INDEX_SCHEMA, REFRESH_SCHEMA):
        if not schema_path.exists():
            errors.append(f"missing schema: {rel(schema_path)}")
    if not POLICY.exists():
        errors.append("missing policy catalog")
        return errors
    policy_packet = policy()
    if policy_packet.get("schema") != "bears-file-context-policy.v1":
        errors.append("policy schema mismatch")
    if policy_packet.get("owner_role") != OWNER_ROLE:
        errors.append("policy owner_role mismatch")
    if not path.exists():
        errors.append("file-context index missing")
        return errors
    packet = load(path)
    errors.extend(validate_json_schema(packet, INDEX_SCHEMA, path.name))
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, record in enumerate(packet.get("records", [])):
        if not isinstance(record, dict):
            continue
        cid = str(record.get("context_id", ""))
        rpath = normalize(str(record.get("path", "")))
        if cid in seen_ids:
            errors.append(f"records[{index}].context_id duplicate: {cid}")
        if rpath in seen_paths:
            errors.append(f"records[{index}].path duplicate: {rpath}")
        seen_ids.add(cid)
        seen_paths.add(rpath)
        errors.extend(validate_record(record, f"records[{index}]"))
    errors.extend(f"missing required file context: {item}" for item in missing_required_paths(packet))
    return errors


def command_validate(args: argparse.Namespace) -> int:
    """Validate the current file-context index."""
    errors = validate_index(INDEX)
    print(json.dumps({"schema": "bears-file-context-index-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_scan(args: argparse.Namespace) -> int:
    """Emit generated context records for explicit paths."""
    records = [build_record(path) for path in args.paths]
    print(json.dumps({"schema": "bears-file-context-scan.v1", "status": "pass", "records": records}, indent=2, sort_keys=True))
    return 0


def command_build_index(args: argparse.Namespace) -> int:
    """Rebuild tracked context records from current source files."""
    packet = index_packet()
    existing = records_by_path(packet)
    paths = [normalize(path) for path in (args.paths or all_governed_paths())]
    records = []
    errors: list[str] = []
    for path in sorted(set(paths)):
        if not source_path(path).exists():
            errors.append(f"source file missing: {path}")
            continue
        records.append(build_record(path, previous=existing.get(path)))
    packet["records"] = records
    packet["updated"] = utc_today()
    write(INDEX, packet)
    errors.extend(validate_index(INDEX))
    print(json.dumps({"schema": "bears-file-context-build-index.v1", "status": "pass" if not errors else "fail", "record_count": len(records), "index": rel(INDEX), "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_select(args: argparse.Namespace) -> int:
    """Select one compact context record for a role/path pair."""
    packet = index_packet()
    record = records_by_path(packet).get(normalize(args.path))
    errors: list[str] = []
    status = "pass"
    if not record:
        status = "fail"
        errors.append(f"context missing for {normalize(args.path)}")
    elif record.get("status") == "stale" or record_is_stale(record):
        status = "blocked"
        errors.append("stale context cannot be used for write-scoped execution")
    selected = None if not record else {
        "context_id": record.get("context_id"),
        "path": record.get("path"),
        "status": "stale" if record_is_stale(record) else record.get("status"),
        "owner_role": record.get("owner_role"),
        "authority_topic": record.get("authority_topic"),
        "purpose": record.get("purpose"),
        "public_interfaces": record.get("public_interfaces", []),
        "functions": record.get("functions", []),
        "classes": record.get("classes", []),
        "contracts": record.get("contracts", []),
        "workflow_nodes": record.get("workflow_nodes", []),
        "decision_refs": record.get("decision_refs", []),
        "read_policy": record.get("read_policy"),
        "write_policy": record.get("write_policy"),
        "prompt_hints": record.get("prompt_hints", []),
    }
    print(json.dumps({"schema": "bears-file-context-selection.v1", "status": status, "role": args.role, "path": normalize(args.path), "selected_context": selected, "errors": errors}, indent=2, sort_keys=True))
    return 0 if status == "pass" else 1


def command_stale(args: argparse.Namespace) -> int:
    """Report stale context records."""
    packet = index_packet()
    stale = stale_paths(packet)
    print(json.dumps({"schema": "bears-file-context-stale.v1", "status": "pass" if not stale else "fail", "stale_records": stale}, indent=2, sort_keys=True))
    return 0 if not stale else 1


def doctor_packet(from_git: str | None = None) -> dict[str, Any]:
    """Build a doctor packet for freshness, drift, and coverage checks."""
    errors = validate_index(INDEX)
    packet = index_packet()
    stale = stale_paths(packet)
    missing = missing_required_paths(packet, from_git=from_git)
    orphaned = orphaned_paths(packet)
    blocked = sorted(set(errors + [f"stale context: {item}" for item in stale] + [f"missing context: {item}" for item in missing] + [f"orphaned context: {item}" for item in orphaned]))
    return {
        "schema": "bears-file-context-refresh.v1",
        "status": "pass" if not blocked else "fail",
        "command": "doctor",
        "updated": utc_today(),
        "changed_records": [],
        "removed_records": [],
        "errors": blocked,
        "stale_records": stale,
        "missing_context_paths": missing,
        "orphaned_records": orphaned,
    }


def command_doctor(args: argparse.Namespace) -> int:
    """Run file-context doctor checks."""
    packet = doctor_packet(args.from_git)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def mark_stale_records(packet: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the index with mismatched records marked stale."""
    stale = set(stale_paths(packet))
    updated = dict(packet)
    records: list[dict[str, Any]] = []
    for record in packet.get("records", []):
        if not isinstance(record, dict):
            continue
        row = dict(record)
        if normalize(str(row.get("path"))) in stale:
            row["status"] = "stale"
            row["write_policy"] = "manual_review"
        records.append(row)
    updated["records"] = records
    updated["updated"] = utc_today()
    return updated


def refresh_path(path_value: str) -> dict[str, Any]:
    """Refresh or append one context record in the tracked index."""
    item = normalize(path_value)
    if not source_path(item).exists():
        return {"schema": "bears-file-context-refresh.v1", "status": "blocked", "command": "refresh", "updated": utc_today(), "changed_records": [], "removed_records": [], "errors": [f"source file missing: {item}"]}
    packet = mark_stale_records(index_packet())
    record = build_record(item)
    records = [row for row in packet.get("records", []) if isinstance(row, dict) and normalize(str(row.get("path"))) != item]
    records.append(record)
    packet["records"] = sorted(records, key=lambda row: row["path"])
    packet["updated"] = utc_today()
    write(INDEX, packet)
    errors = validate_index(INDEX)
    return {"schema": "bears-file-context-refresh.v1", "status": "pass" if not errors else "fail", "command": "refresh", "updated": utc_today(), "changed_records": [item], "removed_records": [], "errors": errors}


def gc_index() -> dict[str, Any]:
    """Remove orphaned context records for deleted files."""
    packet = index_packet()
    orphaned = set(orphaned_paths(packet))
    if not orphaned:
        return {"schema": "bears-file-context-refresh.v1", "status": "pass", "command": "gc", "updated": utc_today(), "changed_records": [], "removed_records": [], "errors": [], "orphaned_records": []}
    packet["records"] = [row for row in packet.get("records", []) if isinstance(row, dict) and normalize(str(row.get("path"))) not in orphaned]
    packet["updated"] = utc_today()
    write(INDEX, packet)
    errors = validate_index(INDEX)
    return {"schema": "bears-file-context-refresh.v1", "status": "pass" if not errors else "fail", "command": "gc", "updated": utc_today(), "changed_records": [], "removed_records": sorted(orphaned), "errors": errors, "orphaned_records": sorted(orphaned)}


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=command_validate)
    scan = sub.add_parser("scan")
    scan.add_argument("--paths", nargs="+", required=True)
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=command_scan)
    build = sub.add_parser("build-index")
    build.add_argument("--paths", nargs="+")
    build.add_argument("--json", action="store_true")
    build.set_defaults(func=command_build_index)
    select = sub.add_parser("select")
    select.add_argument("--path", required=True)
    select.add_argument("--role", required=True)
    select.add_argument("--json", action="store_true")
    select.set_defaults(func=command_select)
    stale = sub.add_parser("stale")
    stale.add_argument("--json", action="store_true")
    stale.set_defaults(func=command_stale)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--from-git")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the file-context CLI."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
