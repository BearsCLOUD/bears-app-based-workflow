# Bears App-Based Workflow Router
Work only in /srv/bears/plugins/bears-app-based-workflow

- Keep plugin procedures in skills/, unique role behavior in the role source (roles/roles.json, rendered into agents/ and claude/agents/), and plugin metadata in the manifests.
- Keep one orchestrator per repository: the main session owns the wave and is the sole writer.
- Dispatch L3 assignments as bounded subagent work, and keep each one scoped to the assigned result.
- Let only the orchestrator choose routes and append process records; no L3 role reaches the maintainer server.
- Work a second repository as a separate session with its own wave, not as a delegated lane.
- Make app-analyze compare documentation, graph edges, ledger provenance, reviews, and linked records for logical correspondence.
- Emit audited only when semantic and process consistency is complete on the exact snapshot.
- Keep plugin instructions and documentation in English.
- Keep workspace rules and shared invariants outside this repository.
- Keep agent-executable completion mechanics and parent execution fallback out of plugin documentation.
