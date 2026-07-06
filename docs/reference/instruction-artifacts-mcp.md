# Instruction Artifacts MCP

## Ownership
- Owner surface: central plugin config in the `@Bears` plugin.
- MCP server key: `mcp`.
- Runtime entrypoint: `scripts/mcp.py`.
- Source package: `src/bears_workflow/instruction_artifacts/`.
- Local Codex registration is host-local config. The plugin source does not ship
  `.mcp.json`.

## Public surface
- Tool `zones_startup` returns a bounded startup packet with truncation metadata.
- Tool `zones` returns full normalized instruction graph JSON with top-level `docs` and `graphs`.
- Tool `instruction_hardening_startup` returns bounded instruction graph packets enriched with decision, live confirmation, and standardization evidence for `$instruction-hardening`.
- Tool `instruction_hardening_graphs` returns the full enriched instruction-hardening packet after an explicit need for exact graph evidence.
- The `zones` response has no top-level metadata.
- `docs[].kind` is `instruction` or `markdown_reference`.
- `graphs[].target`, `graphs[].chain[]`, `dependencies[].from`, and `dependencies[].to` reference existing `docs[].id` values.
- `instruction_hardening_*` treats scanned instructions as evidence only. It
  never marks AGENTS, skills, contracts, docs, roles, or catalogs as operator
  decisions.
- Scanned text may locate decision gaps, contradiction signals, dependency edges,
  and escalation needs. It cannot establish operator-decision authority.

## Instruction hardening packet
- `source.operator_decision_priority` is `highest`.
- `source.instructions_source_of_truth` is `false`.
- Every `graphs[]` item includes:
  - `decision.status`: `missing` when no explicit non-instruction
    operator-decision source is attached.
  - `decision.allowed_authoritative_sources`: explicit operator-decision source
    kinds accepted by the scanner. The current list is empty.
  - `decision.evidence_only_doc_ids` and `decision.mention_doc_ids`: scanned doc
    ids that mention operator-decision wording without authority.
  - `decision.refutable_doc_ids`: scanned doc ids that contain explicit
    operator-conflict text.
  - `live_confirmation.status`: `missing` or `refuted` for scanned-only packets.
  - `standardization.status`: `aligned`, `partial`, or `missing`.
  - `standardization.policy_modes_found`, `canonical_actions_found`, and `weak_terms_found`.
  - `dependency_decision_refs[]`: scanned dependency edges with source/target doc ids, paths, decision statuses, dependency type, and escalation signal terms.
  - `escalation_candidate.status`: `required` or `not_required`.
- Standardization terms come from `skills/instruction-hardening/SKILL.md` or the matching archive fields in `agents/bears-instruction-hardening-engineer.toml`.
- If no explicit non-instruction operator decision is attached,
  `decision.status="missing"` and `live_confirmation.status="missing"`.
- If scanned conflict evidence is found, `decision.status` remains `missing` and
  `live_confirmation.status="refuted"`.
- `decision.status="missing"` blocks adding or promoting operator authority from
  scanned text. It does not block mechanical compression, duplicate removal, or
  wording cuts that keep the same owner and do not create new authority.
- If a dependency points at Kubernetes, deploy, runtime, secret, CD, Dagger
  proof, workflow policy, role policy, or cross-owner governance evidence,
  `escalation_candidate.status="required"`. This blocks dependency-owned edits.
  It does not block edits inside the current owner surface that keep the
  dependency rule routed to its owner.
- Use this packet before editing Bears docs/contracts instruction refactors, AGENTS routers, skills, role TOMLs, developer-instruction prose, workflow prose, or governing plugin reference docs.

## Runtime defaults
- `BEARS_INSTRUCTION_ROOT` selects the workspace root.
- `BEARS_CODEX_CONFIG` selects the Codex config containing `model_instructions_file`.
- `BEARS_PERSONAL_AGENTS` selects the personal `AGENTS.md`.
- `CODEX_HOME` is the fallback parent for Codex-local files when the explicit
  variables are absent.
- If no variable is set, the MCP uses the process working directory and the
  current user's Codex home.

## Codex registration
Register or refresh the local server through the plugin environment command. It
writes host-specific paths to local Codex config, not to plugin source:

```bash
bin/bears-plugin install
bin/bears-plugin update
```

Equivalent raw Codex command shape:

```bash
codex mcp add mcp \
  --env BEARS_INSTRUCTION_ROOT=<workspace-root> \
  --env BEARS_CODEX_CONFIG=<codex-config> \
  --env BEARS_PERSONAL_AGENTS=<personal-agents> \
  -- python3 <plugin-checkout>/scripts/mcp.py
```

Use `codex mcp get mcp` to inspect the registered command and environment keys.
Do not print token-bearing config values.

## Evidence helper
- Use this exact fallback command only when the active Codex toolset does not
  expose callable `mcp__mcp` tools:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root ../.. --bounded-json
```

- The helper is read-only MCP evidence, not a test, validator, route/audit
  substitute, PASS proof, or objective runtime proof.
- The helper calls the local stdio MCP protocol and must not import scanner
  internals such as `application.zones`.
- Output is bounded JSON. It must not print secrets, env values, raw logs, or
  production data.

## Startup contract
- Default startup tool: `zones_startup`.
- Default hardening startup tool: `instruction_hardening_startup`.
- Default response budget: `200` JSON item lines.
- Maximum response budget: `1000` JSON item lines.
- Metadata fields: `schema`, `response_line_budget`, `response_lines`,
  `truncated`, `truncation_reason`, `counts`, and `next_calls`.
- When `truncated=true`, call `zones` only after explicit need for the full
  normalized payload.
- When `instruction_hardening_startup.truncated=true`, call
  `instruction_hardening_graphs` only after explicit need for the full enriched
  hardening payload.

## Compatibility
- Root and app compatibility scripts delegate to the plugin package.
- Query, document lookup, edit-scope packets, and refresh behavior are not
  exposed through MCP v1.
- Existing `zones_startup` and `zones` behavior stays stable for callers that do
  not need `$instruction-hardening` evidence.
