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
- The `zones` response has no top-level metadata.
- `docs[].kind` is `instruction` or `markdown_reference`.
- `graphs[].target`, `graphs[].chain[]`, `dependencies[].from`, and `dependencies[].to` reference existing `docs[].id` values.

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

## Startup contract
- Default startup tool: `zones_startup`.
- Default response budget: `200` JSON item lines.
- Maximum response budget: `1000` JSON item lines.
- Metadata fields: `schema`, `response_line_budget`, `response_lines`,
  `truncated`, `truncation_reason`, `counts`, and `next_calls`.
- When `truncated=true`, call `zones` only after explicit need for the full
  normalized payload.

## Compatibility
- Root and app compatibility scripts delegate to the plugin package.
- Query, document lookup, edit-scope packets, and refresh behavior are not
  exposed through MCP v1.
