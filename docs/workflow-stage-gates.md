# Sequential Workflow Stage Gates

## Rule summary

The workflow is strictly sequential: `app-constitution -> app-research -> app-plan -> app-functional-graph -> app-dev -> app-analyze`.

`app-specify` is a clarification helper inside the research stage. It does not become a main gate unless a research question cannot be answered from existing sources.

The plugin is self-contained. Host policy notes may constrain a live session, but workflow artifacts do not depend on a specific host instruction file or workspace layout.

## Drift routing

- Functional drift: compare against `docs/app-constitution.md` first. Update or route to constitution before changing research, plan, graph, or dev packets.
- Research drift: compare the wave explanation against constitution ids and sources, then update the wave or route to constitution.
- Plan drift: map the microtask back to its research section and constitution id before editing ledger state.
- Graph drift: map the graph node back to a plan microtask, research section, and constitution id before changing graph ids.
- Host-policy drift: record as a separate execution constraint. It must not rewrite constitution truth unless the user explicitly changes functional intent.

## Gates

| Stage | Required reads | Allowed writes | Forbidden writes | Exit gate | Drift route |
| --- | --- | --- | --- | --- | --- |
| `app-constitution` | User intent, product docs, existing workflow artifacts, host policy notes when supplied | `docs/app-constitution.md` | plan tasks, graph nodes, dev packets | Every capability has stable id, owner, evidence need, and known state or gap | Functional drift stays here |
| `app-research` | Constitution, sources, existing waves, host policy notes when supplied | `waves/index.md`, `waves/<wave-id>/research.md`, response packet | plan microtasks, graph nodes, dev packets | Every wave maps to constitution ids and records sources, decisions, unknowns, and next route | New functional truth returns to constitution |
| `app-specify` helper | Research questions, sources, user answers | Clarification notes folded into research | standalone plan, graph, or dev artifacts | Missing actor, data, error, or acceptance detail is resolved or recorded as a blocking question | Unresolved choices return to research or constitution |
| `app-plan` | Constitution, research wave, current ledger, code observations when present, host policy notes when supplied | `waves/<wave-id>/plan.md`, `docs/app-task-ledger.v1.json` | graph node creation, dev dispatch | Every microtask has constitution refs, research refs, order, target paths, definition of done, proof, and status | Missing explanation returns to research; missing truth returns to constitution |
| `app-functional-graph` | Constitution, research, approved plan, ledger | `docs/app-functional-graph.v1.json`, ledger graph backlinks | new product decisions, new microtask scope | Every graph node has constitution refs, research refs, plan task refs, dev model kind, dependencies, and evidence refs | Missing plan route returns to plan |
| `subagents-roles` | Graph-backed tasks, target paths, proof needs | role packet | functional decisions, graph ids | Every ready task has owner/critic/helper role or role gap | Role gap routes to role owner |
| `bears-agents` | Role packet, role inventory | role coverage packet | task scope changes | Every ready task has coverage status | Missing role remains a role gap |
| `subagents` | Role coverage, graph-backed tasks, exact target paths | Sequential dispatch packets | product decisions, task creation | Each packet has bounded scope and completion criteria | Missing graph lineage returns to graph |
| `instruction-hardening` | Plan, dispatch packets, host policy notes when supplied | compressed text, removed-content summary, drift note | decisions, tasks, graph ids, scripts | Text is stricter and behavior-equivalent | Functional conflict routes to constitution |
| `app-dev` | Graph nodes with complete lineage, ledger, role coverage, hardened packets | task status, code changes in assigned paths, closeout notes | tasks outside ledger or graph | Assigned work is closed or blocked with evidence | Missing lineage returns to graph |
| `app-analyze` | Constitution, research, plan, graph, ledger, implementation state | `waves/<wave-id>/analysis.md` | implementation fixes | Broken link is named or wave passes | Route by broken link type |
