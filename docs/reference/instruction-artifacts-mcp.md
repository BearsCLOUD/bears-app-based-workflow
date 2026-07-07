# Instruction Artifacts MCP

## Ownership

- Owner surface: central plugin config in the `@Bears` plugin.
- MCP server key: `mcp`.
- Runtime entrypoint: `scripts/mcp.py`.
- Source package: `src/bears_workflow/instruction_artifacts/`.
- Local registration stores host paths in Codex config, never in plugin source.

## Public tools

- `zones_startup`: bounded normalized instruction packet.
- `zones`: full normalized instruction graph JSON.
- `instruction_hardening_startup`: bounded packet for `$instruction-hardening` with decision, live confirmation, standardization, dependency, and escalation evidence.
- `instruction_hardening_graphs`: full enriched hardening packet after explicit need.

## Hardening packet contract

Top-level `source`:

- `operator_decision_priority="highest"`
- `instructions_source_of_truth=false`
- `decision_source="decision_ledger"`

Every `graphs[]` item includes:

- `decision`: status, accepted source kinds, decision-ledger refs, evidence-only scanned mentions, and refutable scanned docs.
- `live_confirmation`: status, checked fields, confirmable paths, warnings, and refutable docs.
- `standardization`: status plus policy modes, canonical actions, weak terms, and skill refs.
- `dependency_decision_refs[]`: dependency edges with source/target docs, dependency type, decision status, and escalation terms.
- `escalation_candidate`: `required` or `not_required` with owner-review reason.

Instruction-surface inventory fields:

- `surface_summary`: counts by kind, weak-term counts by kind, and top friction paths.
- `instruction_surfaces[]`: bounded or full tracked plugin instruction surfaces from `AGENTS.md`, `skills/*/SKILL.md`, `agents/*.toml`, `docs/reference/*.md`, `docs/runbooks/*`, `assets/catalog/*.v1.json`, and `workflows/*/workflow.yml`.
- Each surface item: `path`, `kind`, `lines`, `bytes`, `weak_terms_found`, `weak_term_count`, `policy_modes_found`, `canonical_actions_found`, and `warning`.
- For Markdown surfaces, weak-term scoring excludes fenced code blocks and inline code spans because command examples, identifiers, and canonical dictionaries are evidence, not instruction prose. The plugin router and roadmap reference keep stable validator/compatibility phrasing fragments out of scoring because downstream wording compatibility matters more than lexical cleanup there.
- For workflow YAML surfaces, weak-term scoring excludes `command:` executable identifiers because those strings are machine action names, not human policy prose.
- For catalog JSON surfaces, weak-term scoring parses JSON and reads only selected human-policy string fields such as `description`, `rule`, `enforcement`, `decision`, `rationale`, `scope`, `trust_boundary`, `allowed_write_boundary`, and `required_precision`. If a catalog has no selected human-policy string fields, it contributes no weak-term scan text. Evidence-only catalogs such as `assets/catalog/decision-ledger.v1.json` and `assets/catalog/release-notes.v1.json` are not scored because they preserve accepted decisions or historical delivery records, not current mutable instruction prose. JSON keys, identifiers, paths, commands, required-validation entries, and other machine metadata are not scored as instruction prose. Catalog-parity phrases such as `required check list` are structural markers, not refactor targets.
- For `agents/*.toml`, weak-term scanning reads human instruction fields only: `description`, `developer_instructions`, `archive_role.title`, `archive_role.mission`, `archive_developer_instructions.priority`, and `conflict` prose. Technical arrays such as `avoid_terms`, `canonical_actions`, and `policy_modes` are metadata, not refactor targets. Validator-required section headings such as `Quality checks:` and catalog-parity phrases such as `required check list` are structural markers, not refactor targets.

Authority rules:

- Scanned AGENTS, skills, contracts, docs, roles, and catalogs are evidence only.
- `decision.status="present"` requires exactly one accepted `assets/catalog/decision-ledger.v1.json` record matching a graph path and no unresolved contradiction.
- `live_confirmation.status="confirmed"` requires matched decision-ledger live evidence inside the graph.
- `escalation_candidate.status="required"` blocks dependency-owned edits, not same-owner wording cuts that preserve owner routing.
- MCP evidence never grants PASS status and never replaces automatic CI/local commit validation.

## Runtime defaults

- `BEARS_INSTRUCTION_ROOT`: workspace root.
- `BEARS_CODEX_CONFIG`: Codex config with `model_instructions_file`.
- `BEARS_PERSONAL_AGENTS`: personal `AGENTS.md`.
- `CODEX_HOME`: fallback Codex home.
- If unset, the server defaults to the server working directory and current user's Codex home.

## Registration

Required plugin environment command:

```bash
bin/bears-plugin install
bin/bears-plugin update
```

Raw command shape:

```bash
codex mcp add mcp \
  --env BEARS_INSTRUCTION_ROOT=<workspace-root> \
  --env BEARS_CODEX_CONFIG=<codex-config> \
  --env BEARS_PERSONAL_AGENTS=<personal-agents> \
  -- python3 <plugin-checkout>/scripts/mcp.py
```

Inspect registration with `codex mcp get mcp`. Do not print token-bearing config values.

## Fallback evidence helper

Allowed only when callable `mcp__mcp` tools are unavailable:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

The helper is read-only MCP evidence. It calls stdio MCP, emits bounded JSON, and must not print secrets, env values, raw logs, or production data.

## Startup budget

- Default hardening startup: `instruction_hardening_startup`.
- Default budget: `200` JSON item lines.
- Maximum budget: `1000` JSON item lines.
- Metadata: `schema`, `response_line_budget`, `response_lines`, `truncated`, `truncation_reason`, `counts`, `next_calls`.
- If truncated, call `instruction_hardening_graphs` only after explicit need for full enriched graph or full instruction-surface evidence.

## Compatibility

- Existing `zones_startup` and `zones` behavior stays stable.
- Root/app compatibility scripts delegate to the plugin package.
- Query, document lookup, edit-scope packets, and refresh behavior are outside MCP v1.
