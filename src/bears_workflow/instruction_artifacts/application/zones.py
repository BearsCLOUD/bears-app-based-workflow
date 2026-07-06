"""Build normalized instruction zones for callers that do not need metadata."""

from __future__ import annotations

import re
import tomllib
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
OPERATOR_DECISION_TERMS = (
    "operator decision",
    "operator-approved",
    "operator approved",
    "operator requested",
    "operator request",
)
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


def _dependency_decision_refs(
    graph: dict[str, Any],
    docs_by_id: dict[int, dict[str, Any]],
    doc_texts: dict[int, str],
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
        source_decision = _decision_for_graph([source_id], doc_texts)
        target_decision = _decision_for_graph([target_id], doc_texts)
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
    decision_evidence: list[int] = []
    contradiction_evidence: list[int] = []
    summaries: list[str] = []

    for doc_id in graph_doc_ids:
        text = doc_texts.get(doc_id, "")
        decision_lines = _matching_lines(text, OPERATOR_DECISION_TERMS)
        contradiction_lines = _matching_lines(text, OPERATOR_CONTRADICTION_TERMS)
        if decision_lines:
            decision_evidence.append(doc_id)
            summaries.extend(decision_lines)
        if contradiction_lines:
            contradiction_evidence.append(doc_id)
            summaries.extend(contradiction_lines)

    if decision_evidence and contradiction_evidence:
        status = "contradicted"
        notes = ["operator_decision_conflict_signal_found"]
    elif decision_evidence:
        status = "present"
        notes = []
    else:
        status = "missing"
        notes = ["operator_decision_not_found"]

    return {
        "status": status,
        "decision_id": f"operator-scanned-{decision_evidence[0]}" if decision_evidence else None,
        "source": "scanned_operator_decision_text" if decision_evidence else None,
        "priority": "operator_highest",
        "summary": summaries[0] if summaries else None,
        "owner_role": "operator",
        "evidence_doc_ids": decision_evidence,
        "refutable_doc_ids": contradiction_evidence,
        "notes": notes,
    }


def _live_confirmation_for_decision(decision: dict[str, Any]) -> dict[str, Any]:
    decision_status = decision["status"]
    if decision_status == "contradicted":
        status = "refuted"
    elif decision_status == "present":
        status = "confirmed"
    else:
        status = "missing"
    return {
        "status": status,
        "confirmable_doc_ids": decision.get("evidence_doc_ids", []),
        "refutable_doc_ids": decision.get("refutable_doc_ids", []),
        "checked_fields": [
            "docs[].path",
            "docs[].sections",
            "graphs[].target",
            "graphs[].chain",
            "graphs[].dependencies",
        ],
        "warnings": [] if status != "missing" else ["operator_decision_missing"],
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
    enriched_graphs: list[dict[str, Any]] = []
    for graph in graphs:
        if not isinstance(graph, dict):
            continue
        graph_doc_ids = _graph_doc_ids(graph)
        decision = _decision_for_graph(graph_doc_ids, doc_texts)
        enriched = dict(graph)
        enriched["decision"] = decision
        enriched["live_confirmation"] = _live_confirmation_for_decision(decision)
        enriched["standardization"] = _standardization_for_graph(
            graph_doc_ids,
            doc_texts,
            grammar,
        )
        dependency_refs = _dependency_decision_refs(graph, docs_by_id, doc_texts)
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
    return {
        "schema": INSTRUCTION_HARDENING_SCHEMA,
        "source": {
            "scanner": "instruction_artifacts",
            "skill": "instruction-hardening",
            "operator_decision_priority": "highest",
            "instructions_source_of_truth": False,
        },
        "counts": {"docs": len(docs), "graphs": len(graphs)},
        "docs": docs,
        "graphs": _enrich_graphs_for_instruction_hardening(docs, graphs),
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
    docs_budget = min(len(docs), budget // 2)
    graphs_budget = min(len(graphs), budget - docs_budget)
    response_lines = docs_budget + graphs_budget
    truncated = docs_budget < len(docs) or graphs_budget < len(graphs)
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
            "returned_docs": docs_budget,
            "returned_graphs": graphs_budget,
        },
        "next_calls": [
            {
                "tool": "instruction_hardening_graphs",
                "reason": (
                    "Fetch the full MCP-scanned hardening packet when exact "
                    "graph decision evidence is needed."
                ),
            }
        ]
        if truncated
        else [],
        "docs": docs[:docs_budget],
        "graphs": graphs[:graphs_budget],
    }
