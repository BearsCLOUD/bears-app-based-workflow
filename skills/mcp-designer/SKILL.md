---
name: mcp-designer
description: "Design, review, or safely change MCP server surfaces and contracts. Use when Codex plans, reviews, or edits an MCP server, adapter, integration surface, MCP contract/docs, tool/resource/prompt schema, response budget, full-export authorization, linked-MCP workflow, or MCP Inspector validation. Also use for implementation patches when the user explicitly asks to change/fix an MCP. Do not scaffold or deploy a new MCP server unless the user separately asks for implementation."
---

# MCP Designer

## Overview

Use this skill to produce a compact, implementation-ready design for an MCP server surface. Keep the design independent of any specific framework unless the target project already chose one.

## Activation

Use this skill whenever the task mentions or touches:

- MCP server code, MCP tools/resources/prompts, adapters, Inspector checks, or MCP runtime registration.
- MCP contracts, `mcpmap.md`, `AGENTS.md` routing for MCP projects, response-size budgets, full exports, authorization, cache/read paths, or linked MCP evidence.
- Bears MCP projects under `/srv/bears/mcp/*`, especially `workspace-map`, `infra`, `codex-telegram`, and `controller`.
- Agent startup/context packets, edit-scope packets, relation-aware code analysis, or cross-MCP links such as `workspace-map://...` and `infra://...`.

If the user asks only for design, do not edit implementation files. If the user
asks to fix/change an MCP, use this skill as the governing review/checklist while
making the bounded implementation patch.

## Bears contract sources

When working in `/srv/bears`, load the current project `AGENTS.md` first, then use
the narrow contract set relevant to the MCP being changed:

- `/srv/bears/contracts/mcp_interaction_methodology.md` — shared MCP startup,
  escalation, response-budget, full-export, and linked-evidence rules.
- `/srv/bears/contracts/infra_map_contract.md` — `mcp/infra` startup, read-only
  checks, code-link packet, and safety rules.
- `/srv/bears/contracts/network_map_contract.md` — required before domain,
  routing, ports, Docker networks, VPN traffic, host placement, or Proxmox work.
- `/srv/bears/mcp/workspace-map/mcpmap.md` — `workspace-map` tool/resource/prompt,
  context graph, linked MCP, and safety surface contract.
- `/srv/bears/mcp/workspace-map/AGENTS.md` and `/srv/bears/mcp/infra/AGENTS.md`
  — project-local runtime and safety boundaries.
- `/srv/bears/contracts/testing_methodologies_skillset.md` and the local
  testing-methodologies plugin — result-record and deterministic testing controls
  when MCP behavior is changed.

Do not duplicate these contracts in chat; apply them, update them when the MCP
surface changes, and validate them with the available contract/test commands.

## Workflow

1. Identify the real source of truth before naming MCP features.
   - Source of truth means the canonical system, database, API, files, or runtime state that owns the data or action.
   - MCP should expose validated access to that source; it must not become a parallel authority, hidden cache, or business-rule fork.
2. Choose the smallest MCP surface that covers the user goal.
   - Use tools for actions, computations, mutations, or live checks.
   - Use resources for read-only contextual data addressed by URI.
   - Use prompts for reusable interaction templates or guided workflows.
   - Prefer fewer, composable features over many narrow aliases.
   - For context-router MCPs, separate one startup packet from deeper evidence readers.
3. Define schemas before implementation details.
   - Specify required and optional fields, enums, defaults, and validation rules.
   - Make outputs structured and predictable; include provenance fields when data comes from external state.
   - Separate user-facing summaries from machine-readable result fields.
   - Add response-budget metadata (`max_lines`, `truncated`, `continuation_token`) for startup surfaces.
4. Add deterministic checks.
   - Include schema validation, static checks, unit tests for adapter logic, and golden examples for representative tool/resource/prompt responses.
   - Add live smoke checks only where the source of truth is available and safe to query.
   - Make failure modes explicit: auth missing, source unavailable, stale data, unsupported input, and partial results.
   - Define startup success evidence, including one bounded startup packet and successful escalation path.
5. Plan MCP Inspector validation.
   - List the server startup command or connection URL only if already known from the project.
   - Verify `initialize`, feature listing, example calls/reads, error responses, and cancellation/timeout behavior where relevant.
   - Record expected Inspector evidence without requiring service mutation.

6. Include deterministic startup limits.
   - For every router/startup surface in this repository, set explicit response budgets (default `<=200` JSON lines).
   - Add deterministic truncation metadata (`response_line_budget`, `response_lines`, `truncated`, `truncation_reason`, `next_calls`).
   - Return compact summaries first, then explicit scoped actions (e.g., `get_*`, `run_*`) for deep dives.
   - Treat full exports as operator-authorized export surfaces, not agent startup surfaces.
   - For agent-facing tools, require hard size controls: documented line/row budget, stable truncation, and continuation calls; if a payload can exceed the budget, split the surface or gate it behind authorization.

7. Prefer stable evidence sources.
   - For infra or map MCPs, define cache-first read paths and explicit allowlist checks for any explicit live operations.
   - Make stale cache fallback transparent with provenance fields (`ok`, `status`, `warnings`, `warning_sources`).

8. Align with live/modern best practices.
   - Use project-provided contracts as sources of truth for operational constraints.
   - Keep stack-role inference deterministic (for example: FastAPI/queue hints by command/image tokens, no regex-only heuristics without fallback).
   - Require explicit backtest/check entry points in every MCP that performs periodic scanning.

9. Require relation-aware agent packets for context-router MCPs.
   - If an MCP helps agents choose code to edit, add a bounded tool that returns `analysis_model`, `source`, `request_time_file_reads`, `target_blocks`, `validation`, `explicit_links`, and `next_calls`.
   - The packet must be deterministic: score from cached entities, declared relationships, exact path/name tokens, and task-type rules; do not rely on LLM-only guesses.
   - Every target block must include stable links such as MCP resource URIs and file references (`path:start-end`).
   - If runtime/infra facts affect code, include cross-MCP links in both directions (for example `workspace-map://project/.../edit-scope` and `infra://code-links`).
   - Add tests that prove the packet is bounded, cache-first, link-bearing, and useful for a realistic edit task.

## Design Output

Return a design with these sections:

- Summary: target users, source of truth, and main MCP purpose.
- Surface: table of tools, resources, and prompts with names, intent, safety level, and source-of-truth dependency.
- Schemas: input and output shapes for each proposed tool plus URI shape and payload shape for resources.
- Boundaries: what MCP owns, what it delegates to the source of truth, and what is explicitly out of scope.
- Checks: deterministic local checks and MCP Inspector scenarios.
- Startup contract: startup packet fields, response budget, truncation metadata, and linked evidence flow.
- Agent packet contract: deterministic edit/runtime scope tool, target-block schema, explicit links, next calls, and tests proving bounded link-bearing output.
- Open Questions: only decisions that cannot be answered from the repository or existing docs.

## Design Rules

- Do not scaffold, edit, or deploy an MCP server when the user asked only for design.
- Do not add dependencies or choose a framework unless the project already constrains it.
- Do not expose raw internal state when a narrower schema can express the user need.
- Do not make prompts perform actions that belong in tools.
- Do not make resources depend on hidden mutations.
- Prefer explicit names with stable verbs and nouns: `list_*`, `get_*`, `create_*`, `verify_*`, `resource://domain/entity/id`.
- Treat writes, external calls, credentials, and operator actions as higher-safety surfaces that need stricter schemas and checks.
- Keep startup/context responses bounded (default ≤200 lines for startup packets) and return continuation/truncation metadata.

## Inspector Checklist

When MCP Inspector is part of the task, include:

- Connection mode: stdio command or HTTP/SSE URL, if already known.
- Discovery checks: tools/list, resources/list, prompts/list.
- Positive examples: one valid call/read/render per important feature.
- Negative examples: invalid input, missing auth, source unavailable, and permission-denied cases.
- Evidence to capture: request, response, status/error shape, and source-of-truth provenance.
