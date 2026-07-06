# Instruction Artifacts MCP

## Ownership
- Owner surface: central plugin config in the `@Bears` plugin.
- MCP server key: `mcp`.
- Runtime entrypoint: `scripts/mcp.py`.
- Source package: `src/bears_workflow/instruction_artifacts/`.

## Public surface
- Tool `zones` returns normalized instruction graph JSON with top-level `docs` and `graphs`.
- The response has no top-level metadata.
- `docs[].kind` is `instruction` or `markdown_reference`.
- `graphs[].target`, `graphs[].chain[]`, `dependencies[].from`, and `dependencies[].to` reference existing `docs[].id` values.

## Compatibility
- Root and app compatibility scripts delegate to the plugin package.
- Full export, query, document lookup, edit-scope packets, and refresh behavior are not exposed through MCP v1.
