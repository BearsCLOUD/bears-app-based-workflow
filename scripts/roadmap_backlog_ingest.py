#!/usr/bin/env python3
"""Ingest open GitHub backlog into executable roadmap packets."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROADMAP = PLUGIN_ROOT / "assets/catalog/workflow-roadmap.v1.json"
CATALOG = PLUGIN_ROOT / "assets/catalog/roadmap-backlog-ingestion.v1.json"
INGEST_SCHEMA = PLUGIN_ROOT / "assets/schemas/roadmap-backlog-ingestion.v1.schema.json"
FILLABILITY_SCHEMA = PLUGIN_ROOT / "assets/schemas/roadmap-fillability-report.v1.schema.json"
RUNTIME_ROOT = PLUGIN_ROOT / "runtime/roadmap-backlog-ingest"
DEFAULT_SCAN = RUNTIME_ROOT / "latest-scan.v1.json"
DEFAULT_PROPOSAL = RUNTIME_ROOT / "latest-proposal.v1.json"
DEFAULT_REPO = "BearsCLOUD/bears-codex-workflow-plugin"
FILLABLE_STATES = {"queued", "running"}
BLOCKED_STATES = {"blocked", "manual_review", "closed", "validated"}
CLASSIFICATIONS = {
    "already_in_roadmap",
    "needs_roadmap_node",
    "duplicate_of_existing_node",
    "blocked_by_missing_contract",
    "manual_review",
    "closeout_candidate",
    "unsafe_for_autostart",
}
FORBIDDEN_MARKERS = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import workflow_roadmap


def utc_now() -> str:
    """Return an RFC3339 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> Any:
    """Read JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, packet: dict[str, Any]) -> None:
    """Write JSON to disk with parent directory creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strings(value: Any) -> list[str]:
    """Flatten nested string values for safety checks."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def has_forbidden(value: Any) -> bool:
    """Return true when a packet contains forbidden raw evidence markers."""
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN_MARKERS)


def gh_issue_list(repo: str) -> list[dict[str, Any]]:
    """Read open issues through gh without mutating GitHub."""
    proc = subprocess.run(
        [
            "gh", "issue", "list", "--repo", repo, "--state", "open", "--limit", "200",
            "--json", "number,title,state,url,labels,updatedAt,body",
        ],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "gh issue list failed")
    data = json.loads(proc.stdout or "[]")
    if not isinstance(data, list):
        raise RuntimeError("gh issue list returned non-list JSON")
    return [row for row in data if isinstance(row, dict)]


def extract_required_files(body: str) -> list[str]:
    """Extract path-like lines from issue body code fences and text."""
    out: list[str] = []
    for line in body.splitlines():
        text = line.strip().strip("`- ")
        text = re.split(r"[\s`:,]", text, maxsplit=1)[0].strip()
        if not text:
            continue
        if re.search(r"^(assets|scripts|docs|tests|\.github|hooks)/|\.json$|\.py$|\.md$", text):
            out.append(text)
    return sorted(set(out))[:40]


def extract_acceptance(body: str) -> list[str]:
    """Extract compact acceptance lines."""
    lines: list[str] = []
    capture = False
    for line in body.splitlines():
        low = line.lower()
        if "acceptance" in low:
            capture = True
            continue
        if capture and line.startswith("##"):
            break
        if capture and line.strip().startswith("-"):
            lines.append(line.strip().lstrip("- "))
    return lines[:20]


def risk_class(labels: list[str], title: str) -> str:
    """Classify issue risk from labels and title."""
    text = " ".join(labels + [title]).casefold()
    if "p0" in text:
        return "p0"
    if "manual" in text or "unsafe" in text:
        return "manual_review"
    return "normal"


def normalize_issue(row: dict[str, Any], repo: str) -> dict[str, Any]:
    """Normalize GitHub issue JSON into a bounded source issue row."""
    labels = row.get("labels") or []
    label_names = [str(item.get("name")) for item in labels if isinstance(item, dict) and item.get("name")]
    number = int(row.get("number") or 0)
    body = str(row.get("body") or "")
    title = str(row.get("title") or "")
    required_files = extract_required_files(body)
    return {
        "repo": repo,
        "number": number,
        "issue_ref": f"#{number}",
        "title": title,
        "state": str(row.get("state") or "UNKNOWN").upper(),
        "url": str(row.get("url") or ""),
        "labels": sorted(label_names),
        "updated_at": str(row.get("updatedAt") or row.get("updated_at") or ""),
        "source": "github_issue_list" if row.get("url") else "fixture",
        "risk_class": risk_class(label_names, title),
        "required_files": required_files,
        "acceptance_criteria": extract_acceptance(body),
    }


def scan(repo: str, *, issues: list[dict[str, Any]] | None = None, write_latest: bool = False) -> dict[str, Any]:
    """Build a deterministic open-backlog scan packet."""
    raw = issues if issues is not None else gh_issue_list(repo)
    rows = [normalize_issue(row, repo) for row in raw]
    rows.sort(key=lambda item: item["number"])
    packet = {
        "schema": "bears-roadmap-backlog-scan.v1",
        "version": "1",
        "status": "pass",
        "repo": repo,
        "generated_at": utc_now(),
        "issue_count": len(rows),
        "issues": rows,
        "source": "fixture" if issues is not None else "github_read_only",
    }
    if write_latest:
        write(DEFAULT_SCAN, packet)
    return packet


def roadmap_nodes(roadmap_path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Index roadmap nodes by issue reference."""
    data = load(roadmap_path or ROADMAP)
    out: dict[str, list[dict[str, Any]]] = {}
    for node in data.get("nodes", []):
        if isinstance(node, dict):
            issue = str(node.get("issue") or "")
            if issue:
                out.setdefault(issue, []).append(node)
    return out


def existing_node_refs(index: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    """Return compact node references for ingestion packets."""
    rows: list[dict[str, str]] = []
    for issue, nodes in sorted(index.items()):
        for node in nodes:
            rows.append({
                "node_id": str(node.get("node_id")),
                "issue": issue,
                "state": str(node.get("state")),
                "node_type": str(node.get("node_type")),
            })
    return rows


def classify_issue(issue: dict[str, Any], nodes: list[dict[str, Any]]) -> tuple[str, str]:
    """Classify one issue for roadmap ingestion."""
    if len(nodes) > 1:
        kinds = [(node.get("node_type"), tuple(node.get("outputs", []))) for node in nodes]
        if len(kinds) != len(set(kinds)):
            return "duplicate_of_existing_node", "duplicate roadmap node mapping"
    if nodes:
        return "already_in_roadmap", "issue already has roadmap node"
    labels = set(issue.get("labels", []))
    if "unsafe-for-autostart" in labels:
        return "unsafe_for_autostart", "unsafe autostart label present"
    if "manual-review" in labels:
        return "manual_review", "manual review label present"
    if issue.get("risk_class") == "p0" and not issue.get("required_files"):
        return "manual_review", "p0 issue missing required file proof"
    return "needs_roadmap_node", "bounded issue needs roadmap node"


def node_id_for(issue: dict[str, Any]) -> str:
    """Build a stable roadmap node id for an issue."""
    return f"issue-{issue['number']}-backlog-ingest"


def proposed_node(issue: dict[str, Any]) -> dict[str, Any]:
    """Create one proposed workflow-roadmap node from a source issue."""
    labels = set(issue.get("labels", []))
    safe = "bears:auto-start" in labels and issue.get("risk_class") != "p0"
    required_files = list(issue.get("required_files") or [])
    outputs = required_files or [f"github_issue:{issue['issue_ref']}"]
    return {
        "node_id": node_id_for(issue),
        "issue": issue["issue_ref"],
        "node_type": "implementation",
        "state": "queued" if safe else "manual_review",
        "owner_role": "roadmap_executor",
        "source_of_truth": ["github_issue", "catalog"],
        "inputs": [issue["url"] or issue["issue_ref"]],
        "outputs": outputs[:20],
        "depends_on": [],
        "decomposes_to": [],
        "blocked_by": [],
        "autostart_policy": "eligible" if safe else "manual_review",
        "evidence_paths": [issue["url"] or issue["issue_ref"]],
        "source_issue_url": issue["url"],
        "risk_class": issue.get("risk_class", "normal"),
        "required_files": required_files,
        "acceptance_criteria": list(issue.get("acceptance_criteria") or []),
        "labels": list(issue.get("labels") or []),
    }


def duplicate_output_rows(nodes: list[dict[str, Any]], proposed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect duplicate output/evidence paths across existing and proposed nodes."""
    seen: dict[str, str] = {}
    duplicates: list[dict[str, Any]] = []
    for node in [*nodes, *proposed]:
        node_id = str(node.get("node_id"))
        for field in ("outputs", "evidence_paths"):
            for value in node.get(field, []) or []:
                if not isinstance(value, str) or value.startswith("https://github.com/"):
                    continue
                prior = seen.get(value)
                if prior and prior != node_id:
                    duplicates.append({"kind": f"duplicate_{field}", "path": value, "node_ids": [prior, node_id]})
                seen[value] = node_id
    return duplicates


def proposal_from_scan(scan_packet: dict[str, Any], roadmap_path: Path | None = None) -> dict[str, Any]:
    """Create a roadmap backlog ingestion proposal without mutating the roadmap."""
    index = roadmap_nodes(roadmap_path)
    existing = existing_node_refs(index)
    proposed: list[dict[str, Any]] = []
    source_issues: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for issue in scan_packet.get("issues", []):
        if not isinstance(issue, dict):
            continue
        classification, reason = classify_issue(issue, index.get(str(issue.get("issue_ref")), []))
        row = dict(issue)
        row["classification"] = classification
        source_issues.append(row)
        compact = {"issue_ref": issue.get("issue_ref"), "number": issue.get("number"), "classification": classification, "reason": reason}
        if classification == "needs_roadmap_node":
            proposed.append(proposed_node(issue))
        elif classification == "manual_review":
            manual_review.append(compact)
        elif classification in {"blocked_by_missing_contract", "unsafe_for_autostart"}:
            blocked.append(compact)
        elif classification == "duplicate_of_existing_node":
            duplicates.append(compact)
    existing_nodes = [node for nodes in index.values() for node in nodes]
    duplicates.extend(duplicate_output_rows(existing_nodes, proposed))
    counts = {
        "open_issue_count": len(source_issues),
        "already_in_roadmap": sum(1 for row in source_issues if row["classification"] == "already_in_roadmap"),
        "needs_node": sum(1 for row in source_issues if row["classification"] == "needs_roadmap_node"),
        "safe_autostart_candidates": sum(1 for node in proposed if node.get("autostart_policy") == "eligible"),
        "manual_review_count": len(manual_review),
        "blocked_count": len(blocked),
    }
    packet = {
        "schema": "bears-roadmap-backlog-ingestion.v1",
        "version": "1",
        "repo": scan_packet.get("repo", DEFAULT_REPO),
        "updated_at": utc_now(),
        "source_issues": source_issues,
        "existing_nodes": existing,
        "proposed_nodes": proposed,
        "duplicates": duplicates,
        "manual_review": manual_review,
        "blocked": blocked,
        "fillability": counts,
    }
    return packet


def validate_ingestion_packet(packet: dict[str, Any]) -> list[str]:
    """Validate an ingestion packet and proposed roadmap nodes."""
    errors = validate_json_schema(packet, INGEST_SCHEMA, "roadmap-backlog-ingestion")
    if has_forbidden(packet):
        errors.append("packet contains forbidden raw data marker")
    node_ids: set[str] = set()
    for node in packet.get("proposed_nodes", []):
        node_id = str(node.get("node_id"))
        if node_id in node_ids:
            errors.append(f"duplicate proposed node_id: {node_id}")
        node_ids.add(node_id)
        roadmap_node = {key: node[key] for key in ("node_id", "issue", "node_type", "state", "owner_role", "source_of_truth", "inputs", "outputs", "depends_on", "decomposes_to", "blocked_by", "autostart_policy", "evidence_paths") if key in node}
        errors.extend(workflow_roadmap.validate_node_for_add(roadmap_node))
    if packet.get("duplicates"):
        errors.append("packet contains duplicate blockers")
    return errors


def propose(repo: str, *, issues: list[dict[str, Any]] | None = None, write_latest: bool = False) -> dict[str, Any]:
    """Build and optionally persist a read-only proposal packet."""
    scan_packet = scan(repo, issues=issues, write_latest=False)
    packet = proposal_from_scan(scan_packet)
    errors = validate_ingestion_packet(packet)
    packet["status"] = "pass" if not errors else "fail"
    if errors:
        packet["errors"] = errors
    if write_latest:
        write(DEFAULT_PROPOSAL, packet)
    return packet


def classify_fillability(issue: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify whether an open issue can be picked up from roadmap state."""
    if not nodes:
        return {"fillable": False, "reason": "missing_roadmap_node", "node_ids": [], "node_states": []}
    node_ids = [str(node.get("node_id")) for node in nodes]
    states = [str(node.get("state")) for node in nodes]
    blocked_by = [item for node in nodes for item in node.get("blocked_by", []) if item]
    eligible = [node for node in nodes if node.get("state") in FILLABLE_STATES and not node.get("blocked_by")]
    if eligible:
        return {"fillable": True, "reason": "roadmap_node_fillable", "node_ids": node_ids, "node_states": states, "selected_node_id": eligible[0].get("node_id")}
    reason = "blocked_by_dependency" if blocked_by else ("roadmap_node_not_fillable" if any(state in BLOCKED_STATES for state in states) else "roadmap_node_not_ready")
    return {"fillable": False, "reason": reason, "node_ids": node_ids, "node_states": states}


def fillability(scan_packet: dict[str, Any] | None = None, roadmap_path: Path | None = None) -> dict[str, Any]:
    """Compare a scan packet with the workflow roadmap."""
    packet = scan_packet or load(DEFAULT_SCAN)
    nodes = roadmap_nodes(roadmap_path)
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for issue in packet.get("issues", []):
        if not isinstance(issue, dict):
            continue
        classification = classify_fillability(issue, nodes.get(str(issue.get("issue_ref")), []))
        row = {"repo": issue.get("repo"), "number": issue.get("number"), "issue_ref": issue.get("issue_ref"), "title": issue.get("title"), "state": issue.get("state"), **classification}
        rows.append(row)
        if not row.get("fillable"):
            blockers.append({"issue_ref": row["issue_ref"], "reason": row["reason"], "node_ids": row["node_ids"]})
    report = {
        "schema": "bears-roadmap-fillability-report.v1",
        "version": "1",
        "status": "pass",
        "repo": packet.get("repo", DEFAULT_REPO),
        "generated_at": utc_now(),
        "source_scan": packet.get("schema"),
        "counts": {
            "issues": len(rows),
            "fillable": sum(1 for row in rows if row.get("fillable")),
            "missing_roadmap_node": sum(1 for row in rows if row.get("reason") == "missing_roadmap_node"),
            "blocked_or_manual": sum(1 for row in rows if row.get("reason") in {"blocked_by_dependency", "roadmap_node_not_fillable"}),
        },
        "issues": rows,
        "blockers": blockers,
    }
    errors = validate_json_schema(report, FILLABILITY_SCHEMA, "roadmap-fillability")
    if errors:
        report["status"] = "fail"
        report["errors"] = errors
    return report


def apply_packet(packet_path: Path, roadmap_path: Path | None = None) -> dict[str, Any]:
    """Apply a validated proposal packet to the workflow roadmap."""
    packet = load(packet_path)
    errors = validate_ingestion_packet(packet)
    if errors:
        return {"schema": "bears-roadmap-backlog-apply.v1", "status": "fail", "errors": errors, "applied": []}
    roadmap = load(roadmap_path or ROADMAP)
    existing = workflow_roadmap.node_index(roadmap)
    applied: list[str] = []
    for node in packet.get("proposed_nodes", []):
        roadmap_node = {key: node[key] for key in ("node_id", "issue", "node_type", "state", "owner_role", "source_of_truth", "inputs", "outputs", "depends_on", "decomposes_to", "blocked_by", "autostart_policy", "evidence_paths")}
        if roadmap_node["node_id"] in existing:
            continue
        roadmap.setdefault("nodes", []).append(roadmap_node)
        existing[roadmap_node["node_id"]] = roadmap_node
        applied.append(roadmap_node["node_id"])
    errors = workflow_roadmap.validate_roadmap(roadmap)
    if errors:
        return {"schema": "bears-roadmap-backlog-apply.v1", "status": "fail", "errors": errors, "applied": []}
    roadmap["updated"] = datetime.now(timezone.utc).date().isoformat()
    write(roadmap_path, roadmap)
    return {"schema": "bears-roadmap-backlog-apply.v1", "status": "pass", "applied": applied, "node_count": len(roadmap.get("nodes", []))}


def validate_all() -> list[str]:
    """Validate catalog, schemas, fixtures, and current commands."""
    errors: list[str] = []
    if not CATALOG.exists():
        errors.append("roadmap backlog ingestion catalog missing")
    else:
        catalog = load(CATALOG)
        for path in catalog.get("authoritative_artifacts", []):
            if not (PLUGIN_ROOT / str(path)).exists():
                errors.append(f"authoritative artifact missing: {path}")
        for command in ("python3 scripts/roadmap_backlog_ingest.py scan --repo BearsCLOUD/bears-codex-workflow-plugin --json", "python3 scripts/roadmap_backlog_ingest.py propose --repo BearsCLOUD/bears-codex-workflow-plugin --json", "python3 scripts/roadmap_backlog_ingest.py apply --packet <path>", "python3 scripts/roadmap_backlog_ingest.py fillability --json", "python3 scripts/roadmap_backlog_ingest.py validate"):
            if command not in catalog.get("commands", []):
                errors.append(f"catalog missing command: {command}")
    good = PLUGIN_ROOT / "tests/fixtures/roadmap_backlog_ingest/good/propose-10-issues.json"
    bad = PLUGIN_ROOT / "tests/fixtures/roadmap_backlog_ingest/bad/duplicate-node.invalid.json"
    if good.exists():
        packet = load(good)
        errors.extend(f"good fixture failed: {item}" for item in validate_ingestion_packet(packet))
    else:
        errors.append("good fixture missing")
    if bad.exists() and not validate_ingestion_packet(load(bad)):
        errors.append("bad fixture unexpectedly passed")
    elif not bad.exists():
        errors.append("bad fixture missing")
    errors.extend(f"workflow-roadmap: {item}" for item in workflow_roadmap.validate_roadmap(load(ROADMAP)))
    return errors


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    scan_parser = sub.add_parser("scan")
    scan_parser.add_argument("--repo", default=DEFAULT_REPO)
    scan_parser.add_argument("--issues-json")
    scan_parser.add_argument("--write", default=str(DEFAULT_SCAN))
    scan_parser.add_argument("--no-write", action="store_true")
    scan_parser.add_argument("--json", action="store_true")
    prop = sub.add_parser("propose")
    prop.add_argument("--repo", default=DEFAULT_REPO)
    prop.add_argument("--issues-json")
    prop.add_argument("--write", default=str(DEFAULT_PROPOSAL))
    prop.add_argument("--no-write", action="store_true")
    prop.add_argument("--json", action="store_true")
    apply = sub.add_parser("apply")
    apply.add_argument("--packet", required=True)
    apply.add_argument("--roadmap", default=str(ROADMAP))
    apply.add_argument("--json", action="store_true")
    fill = sub.add_parser("fillability")
    fill.add_argument("--scan-json")
    fill.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run roadmap backlog ingestion commands."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_all()
            packet = {"schema": "bears-roadmap-backlog-ingestion-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
        elif args.command == "scan":
            issues = load(Path(args.issues_json)) if args.issues_json else None
            packet = scan(str(args.repo), issues=issues, write_latest=not args.no_write)
            if not args.no_write and args.write != str(DEFAULT_SCAN):
                write(Path(args.write), packet)
        elif args.command == "propose":
            issues = load(Path(args.issues_json)) if args.issues_json else None
            packet = propose(str(args.repo), issues=issues, write_latest=not args.no_write)
            if not args.no_write and args.write != str(DEFAULT_PROPOSAL):
                write(Path(args.write), packet)
        elif args.command == "apply":
            packet = apply_packet(Path(args.packet), Path(args.roadmap))
        else:
            source = load(Path(args.scan_json)) if args.scan_json else None
            packet = fillability(source)
    except Exception as exc:
        packet = {"schema": "bears-roadmap-backlog-error.v1", "status": "fail", "error": str(exc)}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
