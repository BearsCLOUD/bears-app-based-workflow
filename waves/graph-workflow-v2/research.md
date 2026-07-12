# Graph Workflow v2 Research

## Observed state

- The functional graph contract was prose-only and also owned the inter-stage handoff definition.
- Route semantics were duplicated in `app-solo-route`, README prose, and an executable route check.
- Graph nodes and edges had no typed registry for transitivity, impact direction, cycle policy, reachability, or ordering.
- Product semantics and actual app-dev process events were mixed or absent, so run behavior could not be reconstructed deterministically.
- Plugin packaging already admitted `scripts` and `.mcp.json`, but no graph runtime was bundled.

## Decision

Use a normative workflow contract plus two derived indexes. Add `app-context-index` as a cross-cutting digest gate rather than a new sequential stage. Bundle an MCP server that performs read-only queries over tracked indexes and never writes or accepts results.

## Sources

- `docs/app-constitution.md`
- existing `skills/app-*/SKILL.md`
- `.codex-plugin/plugin.json`
- `.github/runner/deploy_plugin.py`
