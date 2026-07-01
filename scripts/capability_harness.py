#!/usr/bin/env python3
"""Measure @Bears issue workflow capability growth with deterministic packets."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/bears-plugin-capability-scenarios.v1.json"
STUB_CATALOG = PLUGIN_ROOT / "tests/fixtures/capability/catalogs/l0_l3_stub_matrix.valid.json"
SCENARIO_SCHEMA = PLUGIN_ROOT / "assets/schemas/bears-capability-scenario.v1.schema.json"
REPORT_SCHEMA = PLUGIN_ROOT / "assets/schemas/bears-capability-report.v1.schema.json"
BOOTSTRAP_SCHEMA = PLUGIN_ROOT / "assets/schemas/knowledge-bootstrap-packet.v1.schema.json"
EXTERNAL_FACT_SCHEMA = PLUGIN_ROOT / "assets/schemas/external-fact.v1.schema.json"
USAGE_LEDGER_SCHEMA = PLUGIN_ROOT / "assets/schemas/usage-ledger.v1.schema.json"
CAPABILITY_PROGRESS_SCHEMA = PLUGIN_ROOT / "assets/schemas/capability-progress.v1.schema.json"
COST_QUALITY_SCHEMA = PLUGIN_ROOT / "assets/schemas/cost-quality-summary.v1.schema.json"
RUNTIME_DIR = PLUGIN_ROOT / "runtime/capability-harness"
REPO = "BearsCLOUD/bears-codex-workflow-plugin"
STABLE_FIXTURE_AT = "2026-06-25T00:00:00Z"

TASK_LEVELS = {
    "L1": "classify_issue",
    "L2": "build_context",
    "L3": "produce_plan",
    "L4": "local_one_file_patch",
    "L5": "local_multi_file_patch",
    "L6": "solve_issue_requiring_external_facts",
    "L7": "coordinate_subagents",
}
STUB_LEVELS = ("L0", "L1", "L2", "L3")
COMPARISON_MODES = ["no_bootstrap", "bootstrap_only", "bootstrap_plus_external", "bootstrap_plus_subagents"]
MODE_PROFILES = {
    "no_bootstrap": {"bootstrap": False, "external": False, "subagents": False},
    "bootstrap_only": {"bootstrap": True, "external": False, "subagents": False},
    "bootstrap_plus_external": {"bootstrap": True, "external": True, "subagents": False},
    "bootstrap_plus_subagents": {"bootstrap": True, "external": True, "subagents": True},
}
LEVEL_QUALITY = {"L1": 0.62, "L2": 0.70, "L3": 0.76, "L4": 0.82, "L5": 0.86, "L6": 0.90, "L7": 0.93}
MODE_QUALITY_DELTA = {"no_bootstrap": -0.18, "bootstrap_only": 0.0, "bootstrap_plus_external": 0.05, "bootstrap_plus_subagents": 0.08}
FORBIDDEN_MARKERS = ("begin private key", "raw_secret", "token=", "password=", "credential=")
REQUIRED_LEDGER_FIELDS = [
    "run_id", "issue_task_id", "level", "model_executor", "input_estimated_tokens",
    "output_estimated_tokens", "wall_time_ms", "files_read", "files_changed", "tools_called",
    "external_facts_count", "retries", "failure_class", "result_quality_score",
    "validation_status", "closeout_allowed", "quality_score_basis",
]
REPORT_SCHEMAS = {
    "capability_report.v1.json": REPORT_SCHEMA,
    "capability_progress.v1.json": CAPABILITY_PROGRESS_SCHEMA,
    "cost_quality_summary.v1.json": COST_QUALITY_SCHEMA,
}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, packet: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def append_jsonl(path: Path, packet: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(packet, sort_keys=True) + "\n")
    return path


def print_json(packet: Any) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def stable_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_path(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path.is_file() else None


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PLUGIN_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(path: str | None, default: Path = DEFAULT_CATALOG) -> Path:
    if not path:
        return default
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PLUGIN_ROOT / candidate


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PLUGIN_ROOT / candidate


def git_sha() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unknown"


def run_id_for(seed: Any) -> str:
    return f"capability-{stable_sha(seed)[:16]}"


def catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    return load(path)


def raw_tasks(path: Path = DEFAULT_CATALOG) -> list[dict[str, Any]]:
    data = catalog(path)
    rows = data.get("tasks") or data.get("scenarios") or []
    return [row for row in rows if isinstance(row, dict)]


def is_stub_catalog(path: Path) -> bool:
    data = catalog(path)
    return "scenarios" in data and "tasks" not in data


def stub_catalog(path: Path = STUB_CATALOG) -> dict[str, Any]:
    return load(path)


def stub_scenarios(path: Path = STUB_CATALOG) -> list[dict[str, Any]]:
    data = stub_catalog(path)
    rows = data.get("scenarios") or []
    return [row for row in rows if isinstance(row, dict)]


def scenario_by_id(scenario_id: str, path: Path = STUB_CATALOG) -> dict[str, Any] | None:
    return next((row for row in stub_scenarios(path) if row.get("scenario_id") == scenario_id), None)


def scenario_level(row: dict[str, Any]) -> str:
    return str(row.get("level") or "L0")


def scenario_expected_result(row: dict[str, Any]) -> str:
    harness_stub = row.get("harness_stub") or {}
    return str(harness_stub.get("expected_result") or "pass")


def scenario_closeout_packet(row: dict[str, Any]) -> dict[str, Any] | None:
    harness_stub = row.get("harness_stub")
    path = harness_stub.get("closeout_packet") if isinstance(harness_stub, dict) else None
    if not path:
        return None
    resolved = resolve_repo_path(str(path))
    return load(resolved) if resolved.exists() else None


def validate_stub_catalog_errors(path: Path = STUB_CATALOG) -> list[dict[str, str]]:
    if not path.exists():
        return [{"code": "CATALOG_MISSING", "message": f"catalog missing: {path}"}]
    data = stub_catalog(path)
    errors: list[dict[str, str]] = []
    if data.get("schema_version") != "bears-plugin-capability-scenarios.v1":
        errors.append({"code": "CATALOG_SCHEMA_MISMATCH", "message": "schema_version must be bears-plugin-capability-scenarios.v1"})
    rows = stub_scenarios(path)
    if not rows:
        errors.append({"code": "SCENARIO_MISSING", "message": "catalog must contain scenarios"})
    seen: set[str] = set()
    for index, row in enumerate(rows):
        scenario_id = str(row.get("scenario_id") or f"index-{index}")
        if scenario_id in seen:
            errors.append({"code": "DUPLICATE_SCENARIO_ID", "message": f"duplicate scenario_id: {scenario_id}", "scenario_id": scenario_id})
        seen.add(scenario_id)
        if row.get("schema_version") != "bears-capability-scenario.v1":
            errors.append({"code": "SCENARIO_SCHEMA_MISMATCH", "message": "scenario schema_version must be bears-capability-scenario.v1", "scenario_id": scenario_id})
        if scenario_level(row) not in STUB_LEVELS:
            errors.append({"code": "SCENARIO_LEVEL_INVALID", "message": "level must be L0..L3", "scenario_id": scenario_id})
        if not isinstance(row.get("harness_stub"), dict):
            errors.append({"code": "SCENARIO_STUB_MISSING", "message": "harness_stub must be an object", "scenario_id": scenario_id})
    return sorted(errors, key=lambda row: (row.get("scenario_id", ""), row["code"], row["message"]))


def stub_catalog_summary(path: Path, errors: list[dict[str, str]]) -> dict[str, Any]:
    rows = stub_scenarios(path) if path.exists() else []
    levels: dict[str, int] = {}
    for row in rows:
        level = scenario_level(row)
        levels[level] = levels.get(level, 0) + 1
    return {
        "schema": "bears-capability-harness-validation.v1",
        "status": "pass" if not errors else "fail",
        "catalog": rel(path),
        "scenario_count": len(rows),
        "scenario_levels": {key: levels[key] for key in sorted(levels)},
        "errors": errors,
    }


def overall_result_for_rows(rows: list[dict[str, Any]]) -> str:
    statuses = {str(row.get("status") or "pass") for row in rows}
    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses:
        return "blocked"
    return "pass"


def task_by_id(task_id: str, path: Path = DEFAULT_CATALOG) -> dict[str, Any] | None:
    return next((row for row in raw_tasks(path) if row.get("task_id") == task_id or row.get("scenario_id") == task_id), None)


def level_for_task(task: dict[str, Any]) -> str:
    return str(task.get("level") or "L1")


def issue_task_id(task: dict[str, Any]) -> str:
    return str(task.get("issue_task_id") or task.get("task_id") or task.get("scenario_id") or "task")


def contains_forbidden(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).casefold()
    return any(marker in text for marker in FORBIDDEN_MARKERS)


def fixture_file_errors(row: dict[str, Any], task_id: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for field in ("files_read", "files_changed"):
        for item in row.get(field, []) or []:
            if not isinstance(item, str):
                continue
            path = resolve_repo_path(item)
            try:
                relative = path.resolve().relative_to(PLUGIN_ROOT)
            except ValueError:
                relative = None
            if relative and relative.as_posix().startswith("tests/fixtures/capability/") and not path.exists():
                errors.append({
                    "code": "MISSING_FIXTURE_FILE",
                    "message": f"{field} fixture does not exist: {item}",
                    "task_id": task_id,
                })
    return errors


def validate_task(row: dict[str, Any], index: int) -> list[dict[str, str]]:
    task_id = str(row.get("task_id") or row.get("scenario_id") or f"index-{index}")
    errors = [{"code": "TASK_SCHEMA_INVALID", "message": item, "task_id": task_id} for item in validate_json_schema(row, SCENARIO_SCHEMA, task_id)]
    if level_for_task(row) not in TASK_LEVELS:
        errors.append({"code": "TASK_LEVEL_INVALID", "message": "level must be L1..L7", "task_id": task_id})
    if contains_forbidden(row):
        errors.append({"code": "FORBIDDEN_MARKER", "message": "task contains forbidden raw data marker", "task_id": task_id})
    errors.extend(fixture_file_errors(row, task_id))
    return errors


def validate_catalog_errors(path: Path = DEFAULT_CATALOG) -> list[dict[str, str]]:
    if not path.exists():
        return [{"code": "CATALOG_MISSING", "message": f"catalog missing: {path}"}]
    if is_stub_catalog(path):
        return validate_stub_catalog_errors(path)
    data = catalog(path)
    errors: list[dict[str, str]] = []
    if data.get("schema") != "bears-plugin-capability-scenarios.v1":
        errors.append({"code": "CATALOG_SCHEMA_MISMATCH", "message": "schema must be bears-plugin-capability-scenarios.v1"})
    for schema_path in (SCENARIO_SCHEMA, REPORT_SCHEMA, BOOTSTRAP_SCHEMA, EXTERNAL_FACT_SCHEMA, USAGE_LEDGER_SCHEMA, CAPABILITY_PROGRESS_SCHEMA, COST_QUALITY_SCHEMA):
        if not schema_path.exists():
            errors.append({"code": "SCHEMA_MISSING", "message": f"missing schema: {rel(schema_path)}"})
    seen: set[str] = set()
    for index, row in enumerate(raw_tasks(path)):
        task_id = str(row.get("task_id") or row.get("scenario_id") or f"index-{index}")
        if task_id in seen:
            errors.append({"code": "DUPLICATE_TASK_ID", "message": f"duplicate task_id: {task_id}", "task_id": task_id})
        seen.add(task_id)
        errors.extend(validate_task(row, index))
    declared_levels = {item.get("level"): item.get("capability") for item in data.get("task_levels", []) if isinstance(item, dict)}
    for level, capability in TASK_LEVELS.items():
        if declared_levels.get(level) != capability:
            errors.append({"code": "TASK_LEVEL_MISSING", "message": f"missing task level {level}: {capability}"})
    declared_modes = set(data.get("comparison_modes", []))
    missing_modes = set(COMPARISON_MODES) - declared_modes
    if missing_modes:
        errors.append({"code": "COMPARISON_MODE_MISSING", "message": ", ".join(sorted(missing_modes))})
    return sorted(errors, key=lambda row: (row.get("task_id", ""), row["code"], row["message"]))


def catalog_summary(path: Path, errors: list[dict[str, str]]) -> dict[str, Any]:
    rows = raw_tasks(path) if path.exists() else []
    stub_rows = stub_scenarios(path) if path.exists() and is_stub_catalog(path) else []
    levels: dict[str, int] = {}
    for row in rows:
        levels[level_for_task(row)] = levels.get(level_for_task(row), 0) + 1
    scenario_levels: dict[str, int] = {}
    for row in stub_rows:
        level = scenario_level(row)
        scenario_levels[level] = scenario_levels.get(level, 0) + 1
    return {
        "schema": "bears-capability-harness-validation.v1",
        "status": "pass" if not errors else "fail",
        "catalog": rel(path),
        "task_count": len(rows),
        "task_levels": {key: levels[key] for key in sorted(levels)},
        "scenario_count": len(stub_rows),
        "scenario_levels": {key: scenario_levels[key] for key in sorted(scenario_levels)},
        "comparison_modes": COMPARISON_MODES,
        "errors": errors,
    }


def short_file(path: Path, max_chars: int = 1600) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return {"path": rel(path), "sha256": sha256_path(path), "excerpt": text[:max_chars], "truncated": len(text) > max_chars}


def repo_map() -> dict[str, Any]:
    return {
        "repo": REPO,
        "worktree": str(PLUGIN_ROOT),
        "head_sha": git_sha(),
        "owned_paths": ["assets/catalog", "assets/schemas", "scripts", "tests/fixtures/capability", "tests"],
        "runtime_output": rel(RUNTIME_DIR),
    }


def file_matches(patterns: list[str], limit: int = 12) -> list[str]:
    matches: list[str] = []
    for path in sorted(PLUGIN_ROOT.rglob("*")):
        if len(matches) >= limit:
            break
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        relative = rel(path)
        if any(fnmatch.fnmatch(relative, pattern) for pattern in patterns):
            matches.append(relative)
    return matches


def gh_issue_fact(issue_ref: str, collected_at: str) -> list[dict[str, Any]]:
    if "#" not in issue_ref:
        return []
    repo, number = issue_ref.rsplit("#", 1)
    proc = subprocess.run(
        ["gh", "issue", "view", number, "--repo", repo, "--json", "number,title,state,url,labels"],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        return [{
            "schema": "bears-external-fact.v1", "fact_id": f"github-issue-{number}-unavailable", "fact_type": "github_issue",
            "source": "github", "source_ref": issue_ref, "collected_at": collected_at, "confidence": "low",
            "value": {"available": False, "reason": "gh issue view failed"},
        }]
    data = json.loads(proc.stdout)
    return [{
        "schema": "bears-external-fact.v1", "fact_id": f"github-issue-{data.get('number')}", "fact_type": "github_issue",
        "source": "github", "source_ref": issue_ref, "collected_at": collected_at, "confidence": "high",
        "value": {"number": data.get("number"), "title": data.get("title"), "state": data.get("state"), "url": data.get("url"), "labels": data.get("labels", [])},
    }]



def gh_pr_facts(repo: str, collected_at: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--limit", "3", "--json", "number,title,state,url"],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        return [{
            "schema": "bears-external-fact.v1", "fact_id": "github-pr-list-unavailable", "fact_type": "github_pull_request",
            "source": "github", "source_ref": f"{repo}:pull_requests", "collected_at": collected_at, "confidence": "low",
            "value": {"available": False, "reason": "gh pr list failed"},
        }]
    data = json.loads(proc.stdout)
    facts: list[dict[str, Any]] = []
    for index, pr in enumerate(data, 1):
        facts.append({
            "schema": "bears-external-fact.v1", "fact_id": f"github-pr-{pr.get('number', index)}", "fact_type": "github_pull_request",
            "source": "github", "source_ref": str(pr.get("url") or f"{repo}:pr:{pr.get('number')}"), "collected_at": collected_at, "confidence": "high",
            "value": {"number": pr.get("number"), "title": pr.get("title"), "state": pr.get("state"), "url": pr.get("url")},
        })
    return facts

def git_commit_facts(collected_at: str, limit: int = 3) -> list[dict[str, Any]]:
    proc = subprocess.run(["git", "log", f"-{limit}", "--pretty=format:%H%x09%s"], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False)
    facts: list[dict[str, Any]] = []
    if proc.returncode != 0:
        return facts
    for index, line in enumerate(proc.stdout.splitlines(), 1):
        sha, _, subject = line.partition("\t")
        facts.append({
            "schema": "bears-external-fact.v1", "fact_id": f"git-commit-{index}", "fact_type": "git_commit",
            "source": "git", "source_ref": sha, "collected_at": collected_at, "confidence": "high",
            "value": {"sha": sha, "subject": subject},
        })
    return facts


def repo_search_facts(patterns: list[str], collected_at: str) -> list[dict[str, Any]]:
    matches = file_matches(patterns)
    return [{
        "schema": "bears-external-fact.v1", "fact_id": "repo-file-search", "fact_type": "repo_file_search",
        "source": "local_repo", "source_ref": ",".join(patterns), "collected_at": collected_at, "confidence": "high",
        "value": {"patterns": patterns, "matches": matches},
    }]


def validate_external_facts(facts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, fact in enumerate(facts):
        errors.extend(validate_json_schema(fact, EXTERNAL_FACT_SCHEMA, f"external_facts[{index}]"))
    return errors


def collect_external_facts(
    issue_ref: str | None,
    policy: str,
    task: dict[str, Any] | None = None,
    *,
    collected_at: str | None = None,
) -> dict[str, Any]:
    collected_at = collected_at or utc_now()
    patterns = list((task or {}).get("related_file_patterns", ["scripts/capability_harness.py", "assets/schemas/*.json", "assets/catalog/*.json"]))
    facts = repo_search_facts(patterns, collected_at) + git_commit_facts(collected_at)
    if policy in {"read_only", "mcp_readonly"}:
        if issue_ref:
            facts.extend(gh_issue_fact(issue_ref, collected_at))
        facts.extend(gh_pr_facts(REPO, collected_at))
    if policy == "mcp_readonly":
        facts.append({
            "schema": "bears-external-fact.v1", "fact_id": "mcp-research-policy", "fact_type": "mcp_research",
            "source": "mcp_policy", "source_ref": "explicit:mcp_readonly", "collected_at": collected_at, "confidence": "medium",
            "value": {"allowed": True, "mutation": "forbidden", "policy": "explicit_policy_only"},
        })
    if policy == "fixture" and task:
        facts.append({
            "schema": "bears-external-fact.v1", "fact_id": "fixture-issue", "fact_type": "github_issue",
            "source": "fixture", "source_ref": issue_task_id(task), "collected_at": collected_at, "confidence": "medium",
            "value": task.get("synthetic_issue", {}),
        })
    errors = validate_external_facts(facts)
    return {"schema": "bears-external-fact-collection.v1", "status": "pass" if not errors else "fail", "policy": policy, "facts": facts, "errors": errors}


def build_bootstrap_packet(
    task: dict[str, Any],
    *,
    issue_ref: str | None = None,
    mode: str = "bootstrap_only",
    external_facts: list[dict[str, Any]] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    now = created_at or utc_now()
    agents = [short_file(PLUGIN_ROOT.parents[1] / "AGENTS.md"), short_file(PLUGIN_ROOT / "AGENTS.md")]
    related_patterns = list(task.get("related_file_patterns", ["scripts/capability_harness.py", "assets/catalog/bears-plugin-capability-scenarios.v1.json"]))
    related_files = file_matches(related_patterns)
    schemas = [rel(path) for path in [SCENARIO_SCHEMA, REPORT_SCHEMA, BOOTSTRAP_SCHEMA, EXTERNAL_FACT_SCHEMA, USAGE_LEDGER_SCHEMA, CAPABILITY_PROGRESS_SCHEMA, COST_QUALITY_SCHEMA]]
    catalogs = ["assets/catalog/bears-plugin-capability-scenarios.v1.json", "assets/catalog/mcp-agent-policy.v1.json", "assets/catalog/context-budget-policy.v1.json", "assets/catalog/workflow-roadmap.v1.json"]
    packet = {
        "schema": "bears-knowledge-bootstrap-packet.v1",
        "status": "pass",
        "run_id": run_id_for({"task": issue_task_id(task), "mode": mode, "bootstrap_at": now}),
        "created_at": now,
        "repo_map": repo_map(),
        "instructions": agents,
        "roadmap_node": task.get("roadmap_node", {"node_id": "capability-growth", "state": "local_fixture"}),
        "issue_facts": task.get("synthetic_issue", {"title": issue_ref or issue_task_id(task), "labels": []}),
        "related_files": related_files,
        "schemas": schemas,
        "catalogs": catalogs,
        "prior_local_decisions_evidence": ["assets/catalog/agent-usage-policy.v1.json", "assets/catalog/mcp-agent-policy.v1.json", "assets/catalog/subagent-orchestration-policy.v1.json"],
        "allowed_tools_mcp_policy": {
            "github": "read_only",
            "repo_search": "read_only",
            "mcp_research": "explicit_policy_only",
            "mutation": "local_fixtures_only_for_harness",
        },
        "context_budget": task.get("context_budget", {"max_files": 16, "max_bytes": 120000, "estimated_tokens": 3000}),
        "external_facts": external_facts or [],
        "errors": [],
    }
    errors = validate_json_schema(packet, BOOTSTRAP_SCHEMA, "knowledge-bootstrap-packet")
    if errors:
        packet["status"] = "blocked"
        packet["errors"] = errors
    return packet


def files_read_for(task: dict[str, Any], bootstrap: dict[str, Any] | None, facts: list[dict[str, Any]]) -> list[str]:
    files = set(task.get("files_read", []))
    if bootstrap:
        files.update(item.get("path") for item in bootstrap.get("instructions", []) if isinstance(item, dict))
        files.update(bootstrap.get("related_files", []))
        files.update(bootstrap.get("schemas", []))
        files.update(bootstrap.get("catalogs", []))
    for fact in facts:
        if fact.get("source") == "local_repo":
            files.update(fact.get("value", {}).get("matches", []))
    return sorted(str(item) for item in files if item)


def tool_calls_for(mode: str, facts: list[dict[str, Any]], subagents: bool) -> list[str]:
    tools = ["capability_harness"]
    if mode != "no_bootstrap":
        tools.append("bootstrap_builder")
    if facts:
        tools.extend(sorted({"gh_issue_view" if fact.get("source") == "github" else str(fact.get("source")) for fact in facts}))
    if subagents:
        tools.append("l7_governance_packet_builder")
    return sorted(set(tools))


def quality_score(level: str, mode: str, facts_count: int, subagents: bool) -> float:
    score = LEVEL_QUALITY.get(level, 0.6) + MODE_QUALITY_DELTA.get(mode, 0.0)
    if facts_count:
        score += min(0.04, facts_count * 0.005)
    if subagents:
        score += 0.02
    return round(max(0.0, min(1.0, score)), 3)


def build_usage_ledger(run_id: str, task: dict[str, Any], mode: str, wall_time_ms: int, bootstrap: dict[str, Any] | None, facts: list[dict[str, Any]], subagents: bool) -> dict[str, Any]:
    level = level_for_task(task)
    files_read = files_read_for(task, bootstrap, facts)
    files_changed = list(task.get("files_changed", [])) if level in {"L4", "L5", "L6"} else []
    tools_called = tool_calls_for(mode, facts, subagents)
    input_estimate = int((len(json.dumps(bootstrap or {}, sort_keys=True)) + len(json.dumps(facts, sort_keys=True))) / 4) + 128
    output_estimate = 220 + 30 * len(files_changed) + 15 * len(facts)
    failure_class = "none"
    if level == "L6" and not facts:
        failure_class = "external_facts_missing"
    if level == "L7" and not subagents:
        failure_class = "subagent_coordination_not_enabled"
    result_quality = quality_score(level, mode, len(facts), subagents)
    packet = {
        "schema": "bears-usage-ledger.v1",
        "run_id": run_id,
        "issue_task_id": issue_task_id(task),
        "level": level,
        "model_executor": str(task.get("model_executor", "deterministic_harness")),
        "input_estimated_tokens": input_estimate,
        "output_estimated_tokens": output_estimate,
        "wall_time_ms": wall_time_ms,
        "files_read": files_read,
        "files_changed": files_changed,
        "tools_called": tools_called,
        "external_facts_count": len(facts),
        "retries": 0,
        "failure_class": failure_class,
        "result_quality_score": result_quality,
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "quality_score_basis": "deterministic_harness_estimate_not_unittest_or_local_commit_validation",
    }
    errors = validate_json_schema(packet, USAGE_LEDGER_SCHEMA, "usage-ledger")
    if errors:
        raise ValueError("usage ledger schema failed: " + "; ".join(errors))
    return packet


def task_result(task: dict[str, Any], mode: str, ledger: dict[str, Any], bootstrap: dict[str, Any] | None, facts: list[dict[str, Any]]) -> dict[str, Any]:
    level = level_for_task(task)
    status = "pass"
    blockers: list[str] = []
    if level == "L6" and not facts:
        status = "blocked"
        blockers.append("external facts required")
    if level == "L7" and not MODE_PROFILES[mode]["subagents"]:
        status = "blocked"
        blockers.append("subagent coordination mode required")
    return {
        "task_id": issue_task_id(task),
        "level": level,
        "capability": TASK_LEVELS[level],
        "mode": mode,
        "status": status,
        "bootstrap_packet": bool(bootstrap),
        "external_facts_count": len(facts),
        "files_changed": ledger["files_changed"],
        "quality_score": ledger["result_quality_score"],
        "validation_status": ledger["validation_status"],
        "closeout_allowed": ledger["closeout_allowed"],
        "quality_score_basis": ledger["quality_score_basis"],
        "blockers": blockers,
    }


def write_governance_packets(run_dir: Path, run_id: str, task: dict[str, Any], bootstrap: dict[str, Any] | None, facts_packet: dict[str, Any]) -> list[str]:
    packets = []
    scopes = {
        "bootstrap_context": {"owner": "L2.context", "inputs": ["knowledge_bootstrap_packet"], "status": "ready" if bootstrap else "skipped"},
        "external_facts": {"owner": "L2.research", "inputs": ["external_fact_collection"], "status": facts_packet.get("status", "skipped")},
        "complexity_ladder": {"owner": "L2.capability", "inputs": [level_for_task(task), TASK_LEVELS[level_for_task(task)]], "status": "ready"},
        "metrics_reports": {"owner": "L2.analytics", "inputs": REQUIRED_LEDGER_FIELDS, "status": "ready"},
    }
    for name, body in scopes.items():
        packet = {"schema": "bears-l2-governance-packet.v1", "run_id": run_id, "scope": name, **body}
        path = write(run_dir / "governance" / f"{name}.json", packet)
        packets.append(rel(path))
    return packets


def progress_report(run_id: str, task: dict[str, Any], result: dict[str, Any], ledger: dict[str, Any], governance_packets: list[str]) -> dict[str, Any]:
    completed = [level for level in TASK_LEVELS if int(level[1:]) <= int(level_for_task(task)[1:])]
    packet = {
        "schema": "bears-capability-progress.v1",
        "run_id": run_id,
        "repo": REPO,
        "head_sha": git_sha(),
        "task_id": issue_task_id(task),
        "current_level": level_for_task(task),
        "levels_completed": completed if result["status"] == "pass" else completed[:-1],
        "next_level": next_higher_level(level_for_task(task)),
        "mode": result["mode"],
        "status": result["status"],
        "governance_packets": governance_packets,
        "quality_score": ledger["result_quality_score"],
        "validation_status": ledger["validation_status"],
        "closeout_allowed": ledger["closeout_allowed"],
        "quality_score_basis": ledger["quality_score_basis"],
    }
    errors = validate_json_schema(packet, CAPABILITY_PROGRESS_SCHEMA, "capability-progress")
    if errors:
        packet["status"] = "fail"
        packet["errors"] = errors
    return packet


def cost_quality_summary(run_id: str, ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    total_input = sum(int(row["input_estimated_tokens"]) for row in ledgers)
    total_output = sum(int(row["output_estimated_tokens"]) for row in ledgers)
    avg_quality = round(sum(float(row["result_quality_score"]) for row in ledgers) / max(1, len(ledgers)), 3)
    packet = {
        "schema": "bears-cost-quality-summary.v1",
        "run_id": run_id,
        "total_input_estimated_tokens": total_input,
        "total_output_estimated_tokens": total_output,
        "total_estimated_tokens": total_input + total_output,
        "average_quality_score": avg_quality,
        "run_count": len(ledgers),
        "best_mode": None,
    }
    if ledgers:
        best = max(ledgers, key=lambda row: (row["result_quality_score"], -row["input_estimated_tokens"] - row["output_estimated_tokens"]))
        packet["best_mode"] = best.get("mode")
    errors = validate_json_schema(packet, COST_QUALITY_SCHEMA, "cost-quality-summary")
    if errors:
        packet["errors"] = errors
    return packet


def capability_report(run_id: str, mode: str, result_rows: list[dict[str, Any]], ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    overall = overall_result_for_rows(result_rows)
    packet = {
        "schema_version": "bears-capability-report.v1",
        "run_id": run_id,
        "repo": REPO,
        "git_sha": git_sha(),
        "executor_mode": "deterministic_harness",
        "mode": mode,
        "overall_result": overall,
        "task_levels_added": [{"level": level, "capability": capability} for level, capability in TASK_LEVELS.items()],
        "metric_fields_added": REQUIRED_LEDGER_FIELDS,
        "results": result_rows,
        "ledger_refs": [f"runtime/capability-harness/{run_id}/usage_ledger.v1.jsonl"],
        "reports": ["capability_progress.v1.json", "usage_ledger.v1.jsonl", "cost_quality_summary.v1.json"],
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "quality_score_basis": "deterministic_harness_estimate_not_unittest_or_local_commit_validation",
    }
    errors = validate_json_schema(packet, REPORT_SCHEMA, "capability-report")
    if errors:
        packet["overall_result"] = "fail"
        packet["errors"] = errors
    return packet


def stub_result_row(scenario: dict[str, Any], catalog_path: Path) -> dict[str, Any]:
    harness_stub = scenario.get("harness_stub")
    harness_stub = harness_stub if isinstance(harness_stub, dict) else {}
    expected_gates = scenario.get("expected_gates") or {}
    result = str(harness_stub.get("expected_result") or "pass")
    return {
        "scenario_id": str(scenario.get("scenario_id") or ""),
        "level": scenario_level(scenario),
        "task_id": str(scenario.get("scenario_id") or scenario.get("task_id") or ""),
        "capability": str(scenario.get("capability") or ""),
        "mode": "stub",
        "status": result,
        "executor": "stub",
        "expected_failed_gate": harness_stub.get("expected_failed_gate"),
        "expected_gates": expected_gates,
        "closeout_decision": harness_stub.get("closeout_decision"),
        "closeout_packet": scenario_closeout_packet(scenario),
        "files_changed": list(harness_stub.get("files_changed") or []),
        "validators_run": list(harness_stub.get("validators_run") or []),
        "required_reports": list(scenario.get("required_reports") or []),
        "mutation_mode": "fixture_only",
        "catalog": rel(catalog_path),
    }


def stub_report(run_id: str, mode: str, result_rows: list[dict[str, Any]], catalog_path: Path) -> dict[str, Any]:
    packet = {
        "schema_version": "bears-capability-report.v1",
        "run_id": run_id,
        "repo": REPO,
        "git_sha": git_sha(),
        "executor_mode": "deterministic_harness",
        "mode": mode,
        "overall_result": overall_result_for_rows(result_rows),
        "task_levels_added": [{"level": row["level"], "scenario_id": row["scenario_id"]} for row in result_rows],
        "metric_fields_added": REQUIRED_LEDGER_FIELDS,
        "results": result_rows,
        "ledger_refs": [f"runtime/capability-harness/{run_id}/usage_ledger.v1.jsonl"],
        "reports": ["capability_progress.v1.json", "usage_ledger.v1.jsonl", "cost_quality_summary.v1.json", "capability_report.v1.json"],
        "catalog": rel(catalog_path),
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "quality_score_basis": "deterministic_harness_estimate_not_unittest_or_local_commit_validation",
    }
    errors = validate_json_schema(packet, REPORT_SCHEMA, "capability-report")
    if errors:
        packet["overall_result"] = "fail"
        packet["errors"] = errors
    return packet


def stub_run_artifacts(run_id: str, scenario: dict[str, Any], catalog_path: Path) -> dict[str, Any]:
    run_dir = RUNTIME_DIR / run_id
    result_row = stub_result_row(scenario, catalog_path)
    current_level = result_row["level"]
    next_level = None if current_level == "L3" else f"L{int(current_level[1:]) + 1}"
    ledger = {
        "schema": "bears-usage-ledger.v1",
        "run_id": run_id,
        "issue_task_id": result_row["scenario_id"],
        "level": result_row["level"],
        "model_executor": "stub",
        "input_estimated_tokens": 128,
        "output_estimated_tokens": 64,
        "wall_time_ms": 0,
        "files_read": [],
        "files_changed": result_row["files_changed"],
        "tools_called": ["capability_harness", "stub_executor"],
        "external_facts_count": 0,
        "retries": 0,
        "failure_class": "none" if result_row["status"] == "pass" else f"stub_{result_row['status']}",
        "result_quality_score": 0.5,
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "quality_score_basis": "stub_run_fixture",
        "mode": "stub",
    }
    progress = {
        "schema": "bears-capability-progress.v1",
        "run_id": run_id,
        "repo": REPO,
        "head_sha": git_sha(),
        "task_id": result_row["scenario_id"],
        "current_level": current_level,
        "levels_completed": [result_row["level"]] if result_row["status"] == "pass" else [],
        "next_level": next_level,
        "mode": "stub",
        "status": result_row["status"],
        "governance_packets": [],
        "quality_score": ledger["result_quality_score"],
        "validation_status": ledger["validation_status"],
        "closeout_allowed": ledger["closeout_allowed"],
        "quality_score_basis": ledger["quality_score_basis"],
    }
    report = stub_report(run_id, "stub", [result_row], catalog_path)
    write(run_dir / "stub_result.v1.json", {
        "schema_version": "bears-stub-executor-result.v1",
        "scenario_id": result_row["scenario_id"],
        "level": result_row["level"],
        "files_changed": result_row["files_changed"],
        "mutation_mode": result_row["mutation_mode"],
    })
    ledger_path = run_dir / "usage_ledger.v1.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()
    append_jsonl(ledger_path, ledger)
    write(run_dir / "capability_progress.v1.json", progress)
    write(run_dir / "cost_quality_summary.v1.json", cost_quality_summary(run_id, [ledger]))
    write(run_dir / "capability_report.v1.json", report)
    write(RUNTIME_DIR / "latest-report.v1.json", report)
    return {
        "schema": "bears-capability-run.v1",
        "status": report["overall_result"],
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "scenario_id": result_row["scenario_id"],
        "level": result_row["level"],
        "executor": "stub",
        "result": result_row,
        "report_path": rel(run_dir / "capability_report.v1.json"),
    }


def stub_run_matrix_artifacts(run_id: str, levels: list[str], catalog_path: Path) -> dict[str, Any]:
    rows = [row for row in stub_scenarios(catalog_path) if scenario_level(row) in set(levels)]
    if not rows:
        return {
            "schema": "bears-capability-matrix.v1",
            "status": "fail",
            "run_id": run_id,
            "run_dir": rel(RUNTIME_DIR / run_id),
            "levels": levels,
            "executor": "stub",
            "results": [],
            "errors": ["no matching scenarios"],
        }
    run_dir = RUNTIME_DIR / run_id
    result_rows = [stub_result_row(row, catalog_path) for row in rows]
    report = stub_report(run_id, "stub", result_rows, catalog_path)
    ledgers = []
    for index, row in enumerate(result_rows, 1):
        ledger = {
            "schema": "bears-usage-ledger.v1",
            "run_id": run_id,
            "issue_task_id": row["scenario_id"],
            "level": row["level"],
            "model_executor": "stub",
            "input_estimated_tokens": 128 + index,
            "output_estimated_tokens": 32 + index,
            "wall_time_ms": 0,
            "files_read": [],
            "files_changed": row["files_changed"],
            "tools_called": ["capability_harness", "stub_executor"],
            "external_facts_count": 0,
            "retries": 0,
            "failure_class": "none" if row["status"] == "pass" else f"stub_{row['status']}",
            "result_quality_score": 0.5,
            "validation_status": "pending_local_commit_validation",
            "closeout_allowed": False,
            "quality_score_basis": "stub_matrix_fixture",
            "mode": "stub",
        }
        ledgers.append(ledger)
    progress = {
        "schema": "bears-capability-progress.v1",
        "run_id": run_id,
        "repo": REPO,
        "head_sha": git_sha(),
        "task_id": "stub_matrix",
        "current_level": levels[-1] if levels else "L0",
        "levels_completed": levels,
        "next_level": None,
        "mode": "stub",
        "status": report["overall_result"],
        "governance_packets": [],
        "quality_score": round(sum(float(row["result_quality_score"]) for row in ledgers) / max(1, len(ledgers)), 3),
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "quality_score_basis": "stub_matrix_fixture",
    }
    matrix_ledger = run_dir / "usage_ledger.v1.jsonl"
    if matrix_ledger.exists():
        matrix_ledger.unlink()
    for ledger in ledgers:
        append_jsonl(matrix_ledger, ledger)
    write(run_dir / "capability_progress.v1.json", progress)
    write(run_dir / "cost_quality_summary.v1.json", cost_quality_summary(run_id, ledgers))
    write(run_dir / "capability_report.v1.json", report)
    write(RUNTIME_DIR / "latest-report.v1.json", report)
    matrix_report = {
        "schema": "bears-capability-matrix.v1",
        "status": report["overall_result"] if report["overall_result"] != "pass" else "pass",
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "executor": "stub",
        "levels": levels,
        "results": result_rows,
        "report_paths": {
            "capability_report": rel(run_dir / "capability_report.v1.json"),
            "usage_ledger": rel(run_dir / "usage_ledger.v1.jsonl"),
        },
        "schema_validation": "pass",
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "errors": [],
        "report": report,
    }
    write(run_dir / "matrix_report.v1.json", matrix_report)
    return matrix_report


def run_task(
    task: dict[str, Any],
    mode: str,
    policy: str = "fixture",
    run_id: str | None = None,
    *,
    stable_runtime: bool = False,
    collected_at: str | None = None,
) -> dict[str, Any]:
    if mode not in MODE_PROFILES:
        raise ValueError(f"unknown mode: {mode}")
    start = time.monotonic()
    run_id = run_id or run_id_for({"task": issue_task_id(task), "mode": mode, "head": git_sha()})
    run_dir = RUNTIME_DIR / run_id
    profile = MODE_PROFILES[mode]
    facts_packet = {"schema": "bears-external-fact-collection.v1", "status": "pass", "policy": policy, "facts": [], "errors": []}
    if profile["external"]:
        facts_packet = collect_external_facts(
            str(task.get("issue_ref", "")) or None,
            policy,
            task,
            collected_at=collected_at or (STABLE_FIXTURE_AT if stable_runtime else None),
        )
        write(run_dir / "external_facts.v1.json", facts_packet)
    facts = facts_packet.get("facts", [])
    bootstrap = None
    if profile["bootstrap"]:
        bootstrap = build_bootstrap_packet(
            task,
            issue_ref=task.get("issue_ref"),
            mode=mode,
            external_facts=facts,
            created_at=collected_at or (STABLE_FIXTURE_AT if stable_runtime else None),
        )
        write(run_dir / "knowledge_bootstrap_packet.v1.json", bootstrap)
    wall_time_ms = 0 if stable_runtime else max(1, int((time.monotonic() - start) * 1000))
    ledger = build_usage_ledger(run_id, task, mode, wall_time_ms, bootstrap, facts, bool(profile["subagents"]))
    ledger["mode"] = mode
    ledger_path = run_dir / "usage_ledger.v1.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()
    append_jsonl(ledger_path, ledger)
    result = task_result(task, mode, ledger, bootstrap, facts)
    governance_packets = write_governance_packets(run_dir, run_id, task, bootstrap, facts_packet)
    progress = progress_report(run_id, task, result, ledger, governance_packets)
    cost = cost_quality_summary(run_id, [ledger])
    report = capability_report(run_id, mode, [result], [ledger])
    write(run_dir / "capability_progress.v1.json", progress)
    write(run_dir / "cost_quality_summary.v1.json", cost)
    write(run_dir / "capability_report.v1.json", report)
    write(RUNTIME_DIR / "latest-report.v1.json", report)
    return {"schema": "bears-capability-run.v1", "status": report["overall_result"], "run_id": run_id, "run_dir": rel(run_dir), "result": result, "usage_ledger": ledger, "reports": report["reports"], "governance_packets": governance_packets}


def next_higher_level(level: str) -> str | None:
    value = int(level[1:])
    return f"L{value + 1}" if value < 7 else None


def run_level(level: str, task_id: str | None, mode: str, policy: str, path: Path) -> dict[str, Any]:
    candidates = [row for row in raw_tasks(path) if level_for_task(row) == level]
    task = task_by_id(task_id, path) if task_id else (candidates[0] if candidates else None)
    if not task:
        return {"schema": "bears-capability-run.v1", "status": "fail", "errors": [f"task not found for {level}/{task_id}"]}
    if level_for_task(task) != level:
        return {
            "schema": "bears-capability-run.v1",
            "status": "fail",
            "errors": [f"invalid level/task combination: requested {level}, task {issue_task_id(task)} is {level_for_task(task)}"],
        }
    return run_task(task, mode, policy)


def parse_levels(value: str | None, fallback: list[str]) -> list[str]:
    if not value:
        return list(fallback)
    levels = [item.strip() for item in value.split(",") if item.strip()]
    if not levels:
        return list(fallback)
    invalid = [level for level in levels if level not in STUB_LEVELS]
    if invalid:
        raise ValueError(f"unknown level(s): {', '.join(invalid)}")
    return levels


def run_stub_scenario_command(scenario_id: str, catalog_path: Path) -> dict[str, Any]:
    scenario = scenario_by_id(scenario_id, catalog_path)
    if not scenario:
        return {
            "schema": "bears-capability-run.v1",
            "status": "fail",
            "errors": [f"scenario not found: {scenario_id}"],
            "scenario_id": scenario_id,
            "executor": "stub",
        }
    run_id = run_id_for({"scenario": scenario_id, "executor": "stub", "head": git_sha()})
    return stub_run_artifacts(run_id, scenario, catalog_path)


def run_stub_matrix_command(levels: list[str], catalog_path: Path) -> dict[str, Any]:
    run_id = run_id_for({"levels": levels, "executor": "stub", "head": git_sha()})
    return stub_run_matrix_artifacts(run_id, levels, catalog_path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_report_files(run_dir: Path) -> list[str]:
    errors: list[str] = []
    for name, schema in REPORT_SCHEMAS.items():
        path = run_dir / name
        if not path.exists():
            errors.append(f"missing report: {name}")
            continue
        errors.extend(validate_json_schema(load(path), schema, name))
    ledger_path = run_dir / "usage_ledger.v1.jsonl"
    if not ledger_path.exists():
        errors.append("missing report: usage_ledger.v1.jsonl")
    for index, row in enumerate(read_jsonl(ledger_path)):
        errors.extend(validate_json_schema(row, USAGE_LEDGER_SCHEMA, f"usage_ledger[{index}]"))
    return errors


def matrix_task_by_level(level: str, path: Path) -> dict[str, Any] | None:
    return next((row for row in raw_tasks(path) if level_for_task(row) == level), None)


def matrix_progress_report(
    run_id: str,
    mode: str,
    results: list[dict[str, Any]],
    ledgers: list[dict[str, Any]],
    governance_packets: list[str],
) -> dict[str, Any]:
    quality = round(sum(float(row["result_quality_score"]) for row in ledgers) / max(1, len(ledgers)), 3)
    status = "pass" if all(row["status"] == "pass" for row in results) else "fail"
    packet = {
        "schema": "bears-capability-progress.v1",
        "run_id": run_id,
        "repo": REPO,
        "head_sha": git_sha(),
        "task_id": "fixture_matrix_l1_l7",
        "current_level": "L7",
        "levels_completed": [row["level"] for row in results if row["status"] == "pass"],
        "next_level": None,
        "mode": mode,
        "status": status,
        "governance_packets": sorted(set(governance_packets)),
        "quality_score": quality,
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "quality_score_basis": "deterministic_harness_estimate_not_unittest_or_local_commit_validation",
    }
    errors = validate_json_schema(packet, CAPABILITY_PROGRESS_SCHEMA, "matrix-capability-progress")
    if errors:
        packet["status"] = "fail"
        packet["errors"] = errors
    return packet


def run_matrix(mode: str, policy: str, path: Path) -> dict[str, Any]:
    catalog_errors = validate_catalog_errors(path)
    if catalog_errors:
        return {"schema": "bears-capability-matrix.v1", "status": "fail", "errors": catalog_errors, "results": []}

    levels = list(TASK_LEVELS)
    run_id = run_id_for({"matrix": levels, "mode": mode, "policy": policy, "catalog_sha": sha256_path(path), "head": git_sha()})
    run_dir = RUNTIME_DIR / run_id
    results: list[dict[str, Any]] = []
    ledgers: list[dict[str, Any]] = []
    governance_packets: list[str] = []
    errors: list[str] = []

    for level in levels:
        task = matrix_task_by_level(level, path)
        if not task:
            errors.append(f"missing matrix task for {level}")
            continue
        task_run_id = f"{run_id}-{level.lower()}"
        row = run_task(
            task,
            mode,
            policy,
            run_id=task_run_id,
            stable_runtime=True,
            collected_at=STABLE_FIXTURE_AT,
        )
        results.append(row["result"])
        ledgers.append(row["usage_ledger"])
        governance_packets.extend(row["governance_packets"])
        if row["status"] != "pass":
            errors.append(f"{level} failed with status {row['status']}")

    matrix_ledger = run_dir / "usage_ledger.v1.jsonl"
    if matrix_ledger.exists():
        matrix_ledger.unlink()
    for ledger in ledgers:
        ledger["run_id"] = run_id
        append_jsonl(matrix_ledger, ledger)

    progress = matrix_progress_report(run_id, mode, results, ledgers, governance_packets)
    cost = cost_quality_summary(run_id, ledgers)
    report = capability_report(run_id, mode, results, ledgers)
    report["report_kind"] = "fixture_matrix_l1_l7"
    write(run_dir / "capability_progress.v1.json", progress)
    write(run_dir / "cost_quality_summary.v1.json", cost)
    write(run_dir / "capability_report.v1.json", report)
    report["ledger_refs"] = [f"runtime/capability-harness/{run_id}/usage_ledger.v1.jsonl"]
    report["reports"] = ["capability_progress.v1.json", "usage_ledger.v1.jsonl", "cost_quality_summary.v1.json", "capability_report.v1.json"]
    write(run_dir / "capability_report.v1.json", report)
    schema_errors = validate_report_files(run_dir)
    if schema_errors:
        errors.extend(schema_errors)
    matrix_report = {
        "schema": "bears-capability-matrix.v1",
        "status": "pass" if not errors and report["overall_result"] == "pass" else "fail",
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "mode": mode,
        "policy": policy,
        "levels": levels,
        "results": [
            {
                "level": row["level"],
                "task_id": row["task_id"],
                "status": row["status"],
                "external_facts_count": row["external_facts_count"],
                "quality_score": row["quality_score"],
            }
            for row in results
        ],
        "report_paths": {
            "capability_progress": rel(run_dir / "capability_progress.v1.json"),
            "usage_ledger": rel(run_dir / "usage_ledger.v1.jsonl"),
            "cost_quality_summary": rel(run_dir / "cost_quality_summary.v1.json"),
            "capability_report": rel(run_dir / "capability_report.v1.json"),
        },
        "schema_validation": "pass" if not schema_errors else "fail",
        "validation_status": "pending_local_commit_validation",
        "closeout_allowed": False,
        "errors": errors,
    }
    write(run_dir / "matrix_report.v1.json", matrix_report)
    write(RUNTIME_DIR / "latest-report.v1.json", report)
    return matrix_report


def compare_task(task_id: str, modes: list[str], policy: str, path: Path) -> dict[str, Any]:
    task = task_by_id(task_id, path)
    if not task:
        return {"schema": "bears-capability-comparison.v1", "status": "fail", "task_id": task_id, "results": [], "errors": ["task not found"]}
    run_id = run_id_for({"task": issue_task_id(task), "modes": modes, "head": git_sha()})
    rows = []
    ledgers = []
    for mode in modes:
        row = run_task(task, mode, policy, run_id=f"{run_id}-{mode}")
        rows.append({"mode": mode, "status": row["status"], "quality_score": row["usage_ledger"]["result_quality_score"], "estimated_tokens": row["usage_ledger"]["input_estimated_tokens"] + row["usage_ledger"]["output_estimated_tokens"], "run_id": row["run_id"]})
        ledgers.append(row["usage_ledger"])
    best = max(rows, key=lambda row: (row["status"] == "pass", row["quality_score"], -row["estimated_tokens"]))["mode"] if rows else None
    packet = {"schema": "bears-capability-comparison.v1", "status": "pass", "run_id": run_id, "task_id": issue_task_id(task), "level": level_for_task(task), "modes": modes, "best_mode": best, "results": rows, "errors": []}
    compare_dir = RUNTIME_DIR / run_id
    write(compare_dir / "comparison.v1.json", packet)
    write(compare_dir / "cost_quality_summary.v1.json", cost_quality_summary(run_id, ledgers))
    return packet


def bootstrap_command(args: argparse.Namespace) -> dict[str, Any]:
    path = resolve_path(args.catalog)
    task = task_by_id(args.task, path) if args.task else (raw_tasks(path)[0] if raw_tasks(path) else None)
    if args.fixture:
        task = load(resolve_path(args.fixture, Path(args.fixture)))
    if not task:
        return {"schema": "bears-knowledge-bootstrap-packet.v1", "status": "blocked", "errors": ["task missing"]}
    return build_bootstrap_packet(task, issue_ref=args.issue, mode="bootstrap_only")


def report_latest(run_id: str | None) -> dict[str, Any]:
    if run_id:
        path = RUNTIME_DIR / run_id / "capability_report.v1.json"
        return load(path) if path.exists() else {"schema_version": "bears-capability-report.v1", "run_id": run_id, "repo": REPO, "git_sha": git_sha(), "executor_mode": "deterministic_harness", "mode": "unknown", "overall_result": "fail", "task_levels_added": [], "metric_fields_added": [], "results": [], "ledger_refs": [], "reports": [], "errors": ["report not found"]}
    latest = RUNTIME_DIR / "latest-report.v1.json"
    if latest.exists():
        return load(latest)
    task = raw_tasks(DEFAULT_CATALOG)[0]
    run = run_task(task, "bootstrap_only")
    return load(RUNTIME_DIR / run["run_id"] / "capability_report.v1.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate-catalog"); v.add_argument("--catalog"); v.add_argument("--json", action="store_true")
    b = sub.add_parser("bootstrap"); b.add_argument("--catalog"); b.add_argument("--task"); b.add_argument("--issue"); b.add_argument("--fixture"); b.add_argument("--json", action="store_true")
    e = sub.add_parser("collect-external"); e.add_argument("--catalog"); e.add_argument("--task"); e.add_argument("--issue"); e.add_argument("--policy", choices=["read_only", "fixture", "mcp_readonly"], default="fixture"); e.add_argument("--json", action="store_true")
    s = sub.add_parser("run"); s.add_argument("--catalog"); s.add_argument("--scenario", required=True); s.add_argument("--executor", choices=["stub"], default="stub"); s.add_argument("--json", action="store_true")
    r = sub.add_parser("run-level"); r.add_argument("--catalog"); r.add_argument("--level", required=True, choices=sorted(TASK_LEVELS)); r.add_argument("--task"); r.add_argument("--mode", choices=COMPARISON_MODES, default="bootstrap_only"); r.add_argument("--policy", choices=["read_only", "fixture", "mcp_readonly"], default="fixture"); r.add_argument("--json", action="store_true")
    m = sub.add_parser("run-matrix"); m.add_argument("--catalog"); m.add_argument("--levels"); m.add_argument("--executor", choices=["stub"]); m.add_argument("--mode", choices=COMPARISON_MODES, default="bootstrap_plus_subagents"); m.add_argument("--policy", choices=["read_only", "fixture", "mcp_readonly"], default="fixture"); m.add_argument("--json", action="store_true")
    vm = sub.add_parser("validate-matrix"); vm.add_argument("--catalog"); vm.add_argument("--levels"); vm.add_argument("--executor", choices=["stub"]); vm.add_argument("--mode", choices=COMPARISON_MODES, default="bootstrap_plus_subagents"); vm.add_argument("--policy", choices=["read_only", "fixture", "mcp_readonly"], default="fixture"); vm.add_argument("--json", action="store_true")
    c = sub.add_parser("compare"); c.add_argument("--catalog"); c.add_argument("--task", required=True); c.add_argument("--modes", default=",".join(COMPARISON_MODES)); c.add_argument("--policy", choices=["read_only", "fixture", "mcp_readonly"], default="fixture"); c.add_argument("--json", action="store_true")
    rep = sub.add_parser("report"); rep.add_argument("--latest", action="store_true"); rep.add_argument("--run-id"); rep.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "validate-catalog":
        path = resolve_path(args.catalog)
        errors = validate_catalog_errors(path)
        packet = catalog_summary(path, errors)
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    if args.cmd == "bootstrap":
        packet = bootstrap_command(args)
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet.get("status") == "pass" else 1
    if args.cmd == "collect-external":
        path = resolve_path(args.catalog)
        task = task_by_id(args.task, path) if args.task else (raw_tasks(path)[0] if raw_tasks(path) else None)
        packet = collect_external_facts(args.issue, args.policy, task)
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    if args.cmd == "run":
        catalog_path = resolve_path(args.catalog, STUB_CATALOG)
        packet = run_stub_scenario_command(args.scenario, catalog_path)
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet.get("status") == "pass" else 1
    if args.cmd == "run-level":
        packet = run_level(args.level, args.task, args.mode, args.policy, resolve_path(args.catalog))
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet.get("status") == "pass" else 1
    if args.cmd in {"run-matrix", "validate-matrix"}:
        if args.executor == "stub" or args.levels:
            catalog_path = resolve_path(args.catalog, STUB_CATALOG)
            levels = parse_levels(args.levels, list(STUB_LEVELS))
            packet = run_stub_matrix_command(levels, catalog_path)
        else:
            packet = run_matrix(args.mode, args.policy, resolve_path(args.catalog))
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    if args.cmd == "compare":
        modes = [item.strip() for item in args.modes.split(",") if item.strip()]
        packet = compare_task(args.task, modes, args.policy, resolve_path(args.catalog))
        print_json(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    if args.cmd == "report":
        packet = report_latest(args.run_id)
        print_json(packet) if args.json else print(packet.get("overall_result", packet.get("status")))
        return 0 if packet.get("overall_result", packet.get("status")) == "pass" else 1
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - script runtime guard
        print_json({"schema": "bears-capability-command-error.v1", "status": "fail", "error": str(exc)})
        raise SystemExit(1)
