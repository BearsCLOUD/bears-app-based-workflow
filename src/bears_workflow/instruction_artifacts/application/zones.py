"""Build normalized instruction zones for callers that do not need metadata."""

from __future__ import annotations

import re
import tomllib
import json
from pathlib import Path
from typing import Any

from bears_workflow.instruction_artifacts.adapters import exporter
from bears_workflow.instruction_artifacts.domain.constants import (
    default_codex_config,
    default_personal_agents,
    default_root,
)

DEFAULT_RESPONSE_LINE_BUDGET = 200
MAX_RESPONSE_LINE_BUDGET = 1000
INSTRUCTION_HARDENING_SCHEMA = "bears.instruction_hardening.graphs.v1"
INSTRUCTION_HARDENING_STARTUP_SCHEMA = "bears.instruction_hardening.startup.v1"
INSTRUCTION_HARDENING_SKILL_PATH = "skills/instruction-hardening/SKILL.md"
INSTRUCTION_HARDENING_ROLE_PATH = "agents/bears-instruction-hardening-engineer.toml"
DECISION_LEDGER_PATH = "assets/catalog/decision-ledger.v1.json"
INSTRUCTION_HARDENING_DECISION_SCOPE_ID = "instruction-artifacts-hardening-mcp"
OPERATOR_DECISION_MENTION_TERMS = (
    "operator decision",
    "operator-approved",
    "operator approved",
    "operator requested",
    "operator request",
)
EXPLICIT_OPERATOR_DECISION_SOURCE_KINDS: tuple[str, ...] = ("decision_ledger",)
OPERATOR_CONTRADICTION_TERMS = (
    "contradicts operator",
    "contradict operator",
    "conflicts with operator",
    "conflict with operator",
    "operator decision conflict",
    "against operator decision",
)
ESCALATION_SIGNAL_TERMS = (
    "kubernetes",
    "deploy",
    "deployment",
    "runtime",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "cd",
    "local_cd",
    "dagger",
    "proof",
    "workflow policy",
    "role policy",
    "git/cd",
    "cross-owner",
    "cross owner",
)
FALLBACK_POLICY_MODES = ["Allowed", "Forbidden", "Required", "Ask", "Escalate", "Conflict"]
FALLBACK_CANONICAL_ACTIONS = [
    "read",
    "inspect",
    "search",
    "edit",
    "write",
    "create",
    "delete",
    "execute",
    "test",
    "install",
    "network",
    "commit",
    "push",
    "ask",
    "escalate",
]
FALLBACK_WEAK_TERMS = [
    "handle",
    "process",
    "work with",
    "use",
    "touch",
    "check",
    "carefully",
    "when appropriate",
    "if needed",
    "generally",
    "try to",
    "avoid",
]
INSTRUCTION_SURFACE_GLOBS = (
    "AGENTS.md",
    "skills/*/SKILL.md",
    "agents/*.toml",
    "docs/reference/*.md",
    "docs/runbooks/*",
    "assets/catalog/*.v1.json",
    "workflows/*/workflow.yml",
)
INSTRUCTION_SURFACE_KINDS = (
    ("AGENTS.md", "agents_router"),
    ("skills/", "skill"),
    ("agents/", "role"),
    ("docs/reference/", "reference"),
    ("docs/runbooks/", "runbook"),
    ("assets/catalog/", "catalog"),
    ("workflows/", "workflow"),
)


def _resolve_path(value: str | None, fallback: Any) -> Path:
    if value is None:
        return fallback()
    return Path(value).expanduser()


def _bounded_budget(value: int) -> int:
    return max(1, min(int(value), MAX_RESPONSE_LINE_BUDGET))


def _plugin_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".codex-plugin" / "plugin.json").is_file():
            return parent
    return Path(__file__).resolve().parents[4]


def _decision_ledger() -> dict[str, Any]:
    ledger_path = _plugin_root() / DECISION_LEDGER_PATH
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"records": [], "warnings": ["decision_ledger_unavailable"]}
    if not isinstance(payload, dict):
        return {"records": [], "warnings": ["decision_ledger_invalid"]}
    records = payload.get("records", [])
    if not isinstance(records, list):
        return {"records": [], "warnings": ["decision_ledger_records_invalid"]}
    return {"records": [record for record in records if isinstance(record, dict)], "warnings": []}


def _normalize_plugin_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = value.strip()
    if path.startswith("$workspace/"):
        return path.removeprefix("$workspace/").lstrip("/")
    if path.startswith("$codex/"):
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(_plugin_root()).as_posix()
        except (OSError, ValueError):
            return None
    return path.removeprefix("./").lstrip("/")


def _instruction_hardening_grammar() -> dict[str, Any]:
    role_path = _plugin_root() / INSTRUCTION_HARDENING_ROLE_PATH
    grammar: dict[str, Any] = {
        "policy_modes": FALLBACK_POLICY_MODES,
        "canonical_actions": FALLBACK_CANONICAL_ACTIONS,
        "weak_terms": FALLBACK_WEAK_TERMS,
        "source": "fallback",
        "source_path": INSTRUCTION_HARDENING_SKILL_PATH,
        "role_path": INSTRUCTION_HARDENING_ROLE_PATH,
    }
    try:
        role = tomllib.loads(role_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return grammar

    archive = role.get("archive_developer_instructions")
    if not isinstance(archive, dict):
        return grammar

    policy_modes = archive.get("policy_modes")
    canonical_actions = archive.get("canonical_actions")
    weak_terms = archive.get("avoid_terms")
    if isinstance(policy_modes, list) and all(isinstance(item, str) for item in policy_modes):
        grammar["policy_modes"] = policy_modes
    if isinstance(canonical_actions, list) and all(
        isinstance(item, str) for item in canonical_actions
    ):
        grammar["canonical_actions"] = canonical_actions
    if isinstance(weak_terms, list) and all(isinstance(item, str) for item in weak_terms):
        grammar["weak_terms"] = weak_terms
    grammar["source"] = "role_archive_fields"
    return grammar


def _surface_kind(relative_path: str) -> str:
    for prefix, kind in INSTRUCTION_SURFACE_KINDS:
        if relative_path == prefix or relative_path.startswith(prefix):
            return kind
    return "unknown"


def _instruction_surface_paths(plugin_root: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for pattern in INSTRUCTION_SURFACE_GLOBS:
        for path in sorted(plugin_root.glob(pattern), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            try:
                key = str(path.resolve().relative_to(plugin_root.resolve()))
            except (OSError, ValueError):
                continue
            if key in seen:
                continue
            seen.add(key)
            paths.append(path)
    return paths


def _surface_scan_text(relative_path: str, content: str) -> str:
    """Return human-readable instruction prose for weak-term scanning."""
    if not relative_path.startswith("agents/") or not relative_path.endswith(".toml"):
        return content
    try:
        payload = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return content
    fragments: list[str] = []
    for key in ("description", "developer_instructions"):
        value = payload.get(key)
        if isinstance(value, str):
            fragments.append(value)
    archive_role = payload.get("archive_role")
    if isinstance(archive_role, dict):
        for key in ("title", "mission"):
            value = archive_role.get(key)
            if isinstance(value, str):
                fragments.append(value)
    archive_instructions = payload.get("archive_developer_instructions")
    if isinstance(archive_instructions, dict):
        priority = archive_instructions.get("priority")
        if isinstance(priority, list):
            fragments.extend(item for item in priority if isinstance(item, str))
    conflict = payload.get("conflict")
    if isinstance(conflict, dict):
        for key in ("default", "meaning"):
            value = conflict.get(key)
            if isinstance(value, str):
                fragments.append(value)
    return "\n".join(fragments) if fragments else content


def _instruction_surface_inventory(grammar: dict[str, Any]) -> list[dict[str, Any]]:
    plugin_root = _plugin_root()
    surfaces: list[dict[str, Any]] = []
    for path in _instruction_surface_paths(plugin_root):
        relative_path = path.relative_to(plugin_root).as_posix()
        text, warning = exporter.read_text(path)
        content = text or ""
        scan_content = _surface_scan_text(relative_path, content)
        lowered = scan_content.lower()
        weak_terms = [
            term for term in grammar["weak_terms"] if _term_found(term, lowered)
        ]
        policy_modes = [
            mode for mode in grammar["policy_modes"] if _term_found(mode, scan_content)
        ]
        canonical_actions = [
            action for action in grammar["canonical_actions"] if _term_found(action, lowered)
        ]
        surfaces.append(
            {
                "path": relative_path,
                "kind": _surface_kind(relative_path),
                "bytes": len(content.encode("utf-8")),
                "lines": count_lines(content),
                "weak_terms_found": weak_terms,
                "weak_term_count": sum(
                    len(
                        re.findall(
                            rf"(?<![A-Za-z0-9_-]){re.escape(term)}(?![A-Za-z0-9_-])",
                            lowered,
                        )
                    )
                    for term in weak_terms
                ),
                "policy_modes_found": policy_modes,
                "canonical_actions_found": canonical_actions,
                "warning": warning,
            }
        )
    surfaces.sort(
        key=lambda item: (
            -int(item.get("weak_term_count", 0)),
            item.get("kind", ""),
            item.get("path", ""),
        )
    )
    return surfaces


def _instruction_surface_summary(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    weak_by_kind: dict[str, int] = {}
    for surface in surfaces:
        kind = str(surface.get("kind", "unknown"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
        weak_by_kind[kind] = weak_by_kind.get(kind, 0) + int(
            surface.get("weak_term_count", 0)
        )
    return {
        "surface_count": len(surfaces),
        "by_kind": dict(sorted(by_kind.items())),
        "weak_terms_by_kind": dict(sorted(weak_by_kind.items())),
        "top_friction_paths": [
            {
                "path": surface.get("path"),
                "kind": surface.get("kind"),
                "weak_term_count": surface.get("weak_term_count"),
                "weak_terms_found": surface.get("weak_terms_found", []),
            }
            for surface in surfaces[:20]
        ],
    }


def count_lines(text: str | None) -> int:
    if text is None or text == "":
        return 0
    return len(text.splitlines())


def build_zones(
    *,
    root: str | Path | None = None,
    codex_config: str | Path | None = None,
    personal_agents: str | Path | None = None,
    include_untracked_level4: bool = False,
) -> dict[str, Any]:
    """Return normalized instruction zones without transport or cache metadata."""
    resolved_root = (
        root.expanduser() if isinstance(root, Path) else _resolve_path(root, default_root)
    ).resolve()
    resolved_codex_config = (
        codex_config.expanduser()
        if isinstance(codex_config, Path)
        else _resolve_path(codex_config, default_codex_config)
    )
    resolved_personal_agents = (
        personal_agents.expanduser()
        if isinstance(personal_agents, Path)
        else _resolve_path(personal_agents, default_personal_agents)
    )
    developer_instructions, _config_warnings = exporter.parse_model_instructions_file(
        resolved_codex_config
    )
    targets, _discovery_warnings = exporter.discover_agents(
        resolved_root,
        include_untracked_level4=include_untracked_level4,
    )
    normalized = exporter.build_normalized_export(
        root=resolved_root,
        targets=targets,
        personal_agents=resolved_personal_agents,
        developer_instructions=developer_instructions,
        codex_root=resolved_codex_config.parent.resolve(),
    )
    docs = normalized.get("docs", [])
    graphs = normalized.get("graphs", [])
    return {"docs": docs, "graphs": graphs}


def _doc_text(doc: dict[str, Any]) -> str:
    parts: list[str] = []
    title = doc.get("title")
    if isinstance(title, str):
        parts.append(title)
    for section in doc.get("sections", []):
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        if isinstance(heading, str):
            parts.append(heading)
        for block in section.get("blocks", []):
            if not isinstance(block, dict):
                continue
            for key in ("rules", "lines"):
                values = block.get(key, [])
                if isinstance(values, list):
                    parts.extend(item for item in values if isinstance(item, str))
    return "\n".join(parts)


def _matching_lines(text: str, terms: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in terms):
            lines.append(line.strip())
    return lines


def _graph_doc_ids(graph: dict[str, Any]) -> list[int]:
    doc_ids: set[int] = set()
    target = graph.get("target")
    if isinstance(target, int):
        doc_ids.add(target)
    for value in graph.get("chain", []):
        if isinstance(value, int):
            doc_ids.add(value)
    for dependency in graph.get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        for key in ("from", "to"):
            value = dependency.get(key)
            if isinstance(value, int):
                doc_ids.add(value)
    return sorted(doc_ids)


def _graph_doc_paths(graph_doc_ids: list[int], docs_by_id: dict[int, dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for doc_id in graph_doc_ids:
        normalized = _normalize_plugin_path(docs_by_id.get(doc_id, {}).get("path"))
        if normalized:
            paths.add(normalized)
    return paths


def _accepted_record_matches_graph(
    record: dict[str, Any],
    graph_paths: set[str],
    scope_ids: set[str],
) -> bool:
    if record.get("status") != "accepted":
        return False
    if record.get("contradictions") or record.get("unresolved_inputs"):
        return False
    if scope_ids and record.get("scope_id") not in scope_ids:
        return False
    affected_paths = {
        normalized
        for path in record.get("affected_paths", [])
        if (normalized := _normalize_plugin_path(path))
    }
    return bool(graph_paths.intersection(affected_paths))


def _matching_decision_records(
    graph_paths: set[str],
    scope_ids: set[str],
    decision_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        record
        for record in decision_ledger.get("records", [])
        if _accepted_record_matches_graph(record, graph_paths, scope_ids)
    ]


def _dependency_decision_refs(
    graph: dict[str, Any],
    docs_by_id: dict[int, dict[str, Any]],
    doc_texts: dict[int, str],
    decision_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for dependency in graph.get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        source_id = dependency.get("from")
        target_id = dependency.get("to")
        if not isinstance(source_id, int) or not isinstance(target_id, int):
            continue
        source_doc = docs_by_id.get(source_id, {})
        target_doc = docs_by_id.get(target_id, {})
        source_decision = _decision_for_graph_with_ledger(
            [source_id],
            doc_texts,
            _graph_doc_paths([source_id], docs_by_id),
            decision_ledger,
            set(),
        )
        target_decision = _decision_for_graph_with_ledger(
            [target_id],
            doc_texts,
            _graph_doc_paths([target_id], docs_by_id),
            decision_ledger,
            set(),
        )
        source_text = doc_texts.get(source_id, "")
        target_text = doc_texts.get(target_id, "")
        combined_text = f"{source_doc.get('path', '')}\n{target_doc.get('path', '')}\n{source_text}\n{target_text}".lower()
        escalation_signal_terms = [
            term for term in ESCALATION_SIGNAL_TERMS if term in combined_text
        ]
        refs.append(
            {
                "from_doc_id": source_id,
                "to_doc_id": target_id,
                "type": dependency.get("type", "unknown"),
                "from_path": source_doc.get("path"),
                "to_path": target_doc.get("path"),
                "from_decision_status": source_decision["status"],
                "to_decision_status": target_decision["status"],
                "escalation_signal": bool(escalation_signal_terms),
                "escalation_signal_terms": escalation_signal_terms,
            }
        )
    return refs


def _escalation_candidate(dependency_refs: list[dict[str, Any]]) -> dict[str, Any]:
    signaled_refs = [
        ref
        for ref in dependency_refs
        if ref.get("escalation_signal") or ref.get("to_decision_status") == "contradicted"
    ]
    if signaled_refs:
        status = "required"
        reason = "dependency_requires_higher_level_owner_review"
    else:
        status = "not_required"
        reason = "no_dependency_escalation_signal_found"
    return {
        "status": status,
        "reason": reason,
        "owner_review": "higher_level_instruction_owner" if signaled_refs else None,
        "evidence_dependency_refs": [
            {"from_doc_id": ref["from_doc_id"], "to_doc_id": ref["to_doc_id"]}
            for ref in signaled_refs
        ],
    }


def _decision_for_graph(graph_doc_ids: list[int], doc_texts: dict[int, str]) -> dict[str, Any]:
    return _decision_for_graph_with_ledger(graph_doc_ids, doc_texts, set(), {"records": []})


def _decision_for_graph_with_ledger(
    graph_doc_ids: list[int],
    doc_texts: dict[int, str],
    graph_paths: set[str],
    decision_ledger: dict[str, Any],
    scope_ids: set[str] | None = None,
) -> dict[str, Any]:
    mention_doc_ids: list[int] = []
    refutable_doc_ids: list[int] = []
    summaries: list[str] = []

    for doc_id in graph_doc_ids:
        text = doc_texts.get(doc_id, "")
        decision_lines = _matching_lines(text, OPERATOR_DECISION_MENTION_TERMS)
        contradiction_lines = _matching_lines(text, OPERATOR_CONTRADICTION_TERMS)
        if decision_lines:
            mention_doc_ids.append(doc_id)
            summaries.extend(decision_lines)
        if contradiction_lines:
            refutable_doc_ids.append(doc_id)
            summaries.extend(contradiction_lines)

    notes = ["operator_decision_not_found"]
    if mention_doc_ids:
        notes.append("scanned_operator_decision_mentions_are_evidence_only")
    if refutable_doc_ids:
        notes.append("operator_decision_conflict_signal_found")

    matching_records = _matching_decision_records(
        graph_paths,
        scope_ids or set(),
        decision_ledger,
    )
    ledger_warnings = list(decision_ledger.get("warnings", []))
    if len(matching_records) == 1 and not refutable_doc_ids:
        record = matching_records[0]
        affected_paths = [
            normalized
            for path in record.get("affected_paths", [])
            if (normalized := _normalize_plugin_path(path))
        ]
        return {
            "status": "present",
            "decision_id": record.get("decision_id"),
            "source": "decision_ledger",
            "priority": "operator_highest",
            "summary": record.get("decision"),
            "owner_role": record.get("owner_role"),
            "allowed_authoritative_sources": list(EXPLICIT_OPERATOR_DECISION_SOURCE_KINDS),
            "evidence_doc_ids": [],
            "evidence_only_doc_ids": mention_doc_ids,
            "mention_doc_ids": mention_doc_ids,
            "refutable_doc_ids": refutable_doc_ids,
            "decision_ledger_refs": [record.get("decision_id")],
            "decision_ledger_paths": sorted(set(affected_paths).intersection(graph_paths)),
            "notes": ["operator_decision_found_in_decision_ledger"],
        }

    if len(matching_records) > 1:
        notes.append("multiple_decision_ledger_records_match_graph")
        ledger_warnings.append("decision_ledger_match_not_unique")

    return {
        "status": "missing",
        "decision_id": None,
        "source": None,
        "priority": "operator_highest",
        "summary": summaries[0] if summaries else None,
        "owner_role": "operator",
        "allowed_authoritative_sources": list(EXPLICIT_OPERATOR_DECISION_SOURCE_KINDS),
        "evidence_doc_ids": [],
        "evidence_only_doc_ids": mention_doc_ids,
        "mention_doc_ids": mention_doc_ids,
        "refutable_doc_ids": refutable_doc_ids,
        "decision_ledger_refs": [
            record.get("decision_id") for record in matching_records if record.get("decision_id")
        ],
        "decision_ledger_paths": [],
        "warnings": ledger_warnings,
        "notes": notes,
    }


def _live_confirmation_for_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return _live_confirmation_for_decision_with_graph(decision, set(), {"records": []})


def _live_confirmation_for_decision_with_graph(
    decision: dict[str, Any],
    graph_paths: set[str],
    decision_ledger: dict[str, Any],
) -> dict[str, Any]:
    refutable_doc_ids = decision.get("refutable_doc_ids", [])
    status = "refuted" if refutable_doc_ids else "missing"
    warnings = ["operator_decision_missing"]
    if decision.get("mention_doc_ids"):
        warnings.append("scanned_operator_decision_mentions_are_evidence_only")
    if refutable_doc_ids:
        warnings.append("operator_decision_conflict_signal_found")
    confirmable_paths: list[str] = []
    ledger_refs = decision.get("decision_ledger_refs", [])
    if decision.get("status") == "present" and ledger_refs:
        for record in decision_ledger.get("records", []):
            if record.get("decision_id") not in ledger_refs:
                continue
            live_confirmation = record.get("live_confirmation")
            if not isinstance(live_confirmation, dict):
                warnings.append("decision_ledger_live_confirmation_missing")
                continue
            evidence_paths = [
                normalized
                for path in live_confirmation.get("evidence_paths", [])
                if (normalized := _normalize_plugin_path(path))
            ]
            matched_paths = sorted(set(evidence_paths).intersection(graph_paths))
            if live_confirmation.get("status") == "confirmed" and matched_paths:
                status = "confirmed"
                confirmable_paths.extend(matched_paths)
            elif live_confirmation.get("status") == "refuted":
                status = "refuted"
                warnings.append("decision_ledger_live_confirmation_refuted")
            else:
                warnings.append("decision_ledger_live_confirmation_not_confirmed")
    if status == "confirmed":
        warnings = [
            warning
            for warning in warnings
            if warning not in {"operator_decision_missing", "decision_ledger_live_confirmation_not_confirmed"}
        ]
    return {
        "status": status,
        "confirmable_doc_ids": [],
        "confirmable_paths": sorted(set(confirmable_paths)),
        "evidence_only_doc_ids": decision.get("evidence_only_doc_ids", []),
        "refutable_doc_ids": refutable_doc_ids,
        "checked_fields": [
            "docs[].path",
            "docs[].sections",
            "graphs[].target",
            "graphs[].chain",
            "graphs[].dependencies",
            "decision-ledger.records[].live_confirmation",
        ],
        "warnings": warnings,
    }


def _term_found(term: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(term)}(?![A-Za-z0-9_-])", text) is not None


def _standardization_for_graph(
    graph_doc_ids: list[int],
    doc_texts: dict[int, str],
    grammar: dict[str, Any],
) -> dict[str, Any]:
    text = "\n".join(doc_texts.get(doc_id, "") for doc_id in graph_doc_ids)
    policy_modes = [mode for mode in grammar["policy_modes"] if _term_found(mode, text)]
    lowered = text.lower()
    canonical_actions = [
        action for action in grammar["canonical_actions"] if _term_found(action, lowered)
    ]
    weak_terms = [term for term in grammar["weak_terms"] if _term_found(term, lowered)]
    if policy_modes and not weak_terms:
        status = "aligned"
    elif policy_modes or canonical_actions or weak_terms:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "policy_modes_found": policy_modes,
        "canonical_actions_found": canonical_actions,
        "weak_terms_found": weak_terms,
        "skill_refs": [
            {
                "path": INSTRUCTION_HARDENING_SKILL_PATH,
                "fields": ["policy_modes", "canonical_actions", "avoid_terms"],
            },
            {
                "path": INSTRUCTION_HARDENING_ROLE_PATH,
                "fields": ["archive_developer_instructions"],
                "source": grammar["source"],
            },
        ],
    }


def _enrich_graphs_for_instruction_hardening(
    docs: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    doc_texts = {
        doc["id"]: _doc_text(doc)
        for doc in docs
        if isinstance(doc, dict) and isinstance(doc.get("id"), int)
    }
    docs_by_id = {
        doc["id"]: doc
        for doc in docs
        if isinstance(doc, dict) and isinstance(doc.get("id"), int)
    }
    grammar = _instruction_hardening_grammar()
    decision_ledger = _decision_ledger()
    enriched_graphs: list[dict[str, Any]] = []
    for graph in graphs:
        if not isinstance(graph, dict):
            continue
        graph_doc_ids = _graph_doc_ids(graph)
        graph_paths = _graph_doc_paths(graph_doc_ids, docs_by_id)
        decision = _decision_for_graph_with_ledger(
            graph_doc_ids,
            doc_texts,
            graph_paths,
            decision_ledger,
            {INSTRUCTION_HARDENING_DECISION_SCOPE_ID},
        )
        enriched = dict(graph)
        enriched["decision"] = decision
        enriched["live_confirmation"] = _live_confirmation_for_decision_with_graph(
            decision,
            graph_paths,
            decision_ledger,
        )
        enriched["standardization"] = _standardization_for_graph(
            graph_doc_ids,
            doc_texts,
            grammar,
        )
        dependency_refs = _dependency_decision_refs(
            graph,
            docs_by_id,
            doc_texts,
            decision_ledger,
        )
        enriched["dependency_decision_refs"] = dependency_refs
        enriched["escalation_candidate"] = _escalation_candidate(dependency_refs)
        enriched_graphs.append(enriched)
    return enriched_graphs


def build_instruction_hardening_graphs(
    *,
    root: str | Path | None = None,
    codex_config: str | Path | None = None,
    personal_agents: str | Path | None = None,
    include_untracked_level4: bool = False,
) -> dict[str, Any]:
    """Return MCP-scanned instruction graphs enriched for hardening decisions."""
    payload = build_zones(
        root=root,
        codex_config=codex_config,
        personal_agents=personal_agents,
        include_untracked_level4=include_untracked_level4,
    )
    docs = list(payload.get("docs", []))
    graphs = list(payload.get("graphs", []))
    grammar = _instruction_hardening_grammar()
    instruction_surfaces = _instruction_surface_inventory(grammar)
    return {
        "schema": INSTRUCTION_HARDENING_SCHEMA,
        "source": {
            "scanner": "instruction_artifacts",
            "skill": "instruction-hardening",
            "operator_decision_priority": "highest",
            "instructions_source_of_truth": False,
            "decision_source": "decision_ledger",
        },
        "counts": {
            "docs": len(docs),
            "graphs": len(graphs),
            "instruction_surfaces": len(instruction_surfaces),
        },
        "surface_summary": _instruction_surface_summary(instruction_surfaces),
        "docs": docs,
        "graphs": _enrich_graphs_for_instruction_hardening(docs, graphs),
        "instruction_surfaces": instruction_surfaces,
    }


def build_zones_startup(
    *,
    root: str | Path | None = None,
    codex_config: str | Path | None = None,
    personal_agents: str | Path | None = None,
    include_untracked_level4: bool = False,
    response_line_budget: int = DEFAULT_RESPONSE_LINE_BUDGET,
) -> dict[str, Any]:
    """Return a bounded startup packet for Codex MCP initialization."""
    budget = _bounded_budget(response_line_budget)
    payload = build_zones(
        root=root,
        codex_config=codex_config,
        personal_agents=personal_agents,
        include_untracked_level4=include_untracked_level4,
    )
    docs = list(payload.get("docs", []))
    graphs = list(payload.get("graphs", []))
    docs_budget = min(len(docs), budget // 2)
    graphs_budget = min(len(graphs), budget - docs_budget)
    response_lines = docs_budget + graphs_budget
    truncated = docs_budget < len(docs) or graphs_budget < len(graphs)
    return {
        "schema": "bears.instruction_zones.startup.v1",
        "response_line_budget": budget,
        "response_lines": response_lines,
        "truncated": truncated,
        "truncation_reason": "response_line_budget" if truncated else None,
        "counts": {
            "docs": len(docs),
            "graphs": len(graphs),
            "returned_docs": docs_budget,
            "returned_graphs": graphs_budget,
        },
        "next_calls": [
            {
                "tool": "zones",
                "reason": "Fetch the full normalized docs and graphs payload when explicitly needed.",
            }
        ]
        if truncated
        else [],
        "docs": docs[:docs_budget],
        "graphs": graphs[:graphs_budget],
    }


def build_instruction_hardening_startup(
    *,
    root: str | Path | None = None,
    codex_config: str | Path | None = None,
    personal_agents: str | Path | None = None,
    include_untracked_level4: bool = False,
    response_line_budget: int = DEFAULT_RESPONSE_LINE_BUDGET,
) -> dict[str, Any]:
    """Return a bounded startup packet for instruction hardening."""
    budget = _bounded_budget(response_line_budget)
    payload = build_instruction_hardening_graphs(
        root=root,
        codex_config=codex_config,
        personal_agents=personal_agents,
        include_untracked_level4=include_untracked_level4,
    )
    docs = list(payload.get("docs", []))
    graphs = list(payload.get("graphs", []))
    surfaces = list(payload.get("instruction_surfaces", []))
    docs_budget = min(len(docs), budget // 3)
    graphs_budget = min(len(graphs), budget // 3)
    surfaces_budget = min(len(surfaces), budget - docs_budget - graphs_budget)
    response_lines = docs_budget + graphs_budget + surfaces_budget
    truncated = (
        docs_budget < len(docs)
        or graphs_budget < len(graphs)
        or surfaces_budget < len(surfaces)
    )
    return {
        "schema": INSTRUCTION_HARDENING_STARTUP_SCHEMA,
        "source": payload["source"],
        "response_line_budget": budget,
        "response_lines": response_lines,
        "truncated": truncated,
        "truncation_reason": "response_line_budget" if truncated else None,
        "counts": {
            "docs": len(docs),
            "graphs": len(graphs),
            "instruction_surfaces": len(surfaces),
            "returned_docs": docs_budget,
            "returned_graphs": graphs_budget,
            "returned_instruction_surfaces": surfaces_budget,
        },
        "surface_summary": payload.get("surface_summary", {}),
        "next_calls": [
            {
                "tool": "instruction_hardening_graphs",
                "reason": (
                    "Fetch the full MCP-scanned hardening packet when exact "
                    "graph or instruction-surface evidence is needed."
                ),
            }
        ]
        if truncated
        else [],
        "docs": docs[:docs_budget],
        "graphs": graphs[:graphs_budget],
        "instruction_surfaces": surfaces[:surfaces_budget],
    }
