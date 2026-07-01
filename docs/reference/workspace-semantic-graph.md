# Workspace semantic graph

The workspace semantic graph is the JSON authority layer for repo, file, issue, decision, changelog, context, symbol, and workflow relations.

Authority rules:
- `assets/catalog/workspace-semantic-graph.v1.json` declares node types, edge types, commands, and integration points.
- `assets/catalog/workspace-dictionary.v1.json` owns canonical terms and forbidden aliases.
- `assets/catalog/metadata-store-policy.v1.json` keeps validated JSON in git as the only phase-1 source of truth.
- External stores are cache-only until a separate issue promotes them and exports back to validated JSON.

Commands:
- `python3 scripts/workspace_semantic_graph.py validate`
- `python3 scripts/workspace_semantic_graph.py extract --paths scripts/file_context_index.py --json`
- `python3 scripts/workspace_semantic_graph.py build --json`
- `python3 scripts/workspace_semantic_graph.py query --selector scripts/file_context_index.py --json`
- `python3 scripts/workspace_semantic_graph.py diff --base HEAD^ --head HEAD --json`
- `python3 scripts/workspace_dictionary.py canonicalize --term CPG --json`
- `python3 scripts/metadata_store.py doctor --json`

Selectors return bounded JSON and include file-context ids when available, so agents can avoid full-file reads before write-scoped work.
