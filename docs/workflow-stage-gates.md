# Sequential Workflow Stage Gates

## Rule summary

The main artifact workflow is strictly sequential: `app-constitution -> app-research -> app-plan -> app-functional-graph -> app-dev -> app-analyze`.

`app-specify` is a clarification helper inside research. `subagents-roles`, `subagents`, and `instruction-hardening` are support skills inside `app-dev`; they do not create extra main gates.

The plugin is self-contained. Execution constraints may limit a live session, but workflow artifacts do not depend on a specific host instruction file, role inventory, runtime service, or workspace layout.

## Drift routing

- Functional drift: compare against `docs/app-constitution.md` first. Update or route to constitution before changing research, plan, graph, or dev packets.
- Research drift: compare the wave explanation against constitution ids and sources, then update the wave or route to constitution.
- Plan drift: map the microtask back to its research section and constitution id before editing ledger state.
- Graph drift: map the graph node back to a plan microtask, research section, and constitution id before changing graph ids.
- Dev drift: map the implementation or dispatch issue back to graph node, plan microtask, research section, and constitution id.
- Execution-constraint drift: record as a separate execution constraint. It must not rewrite constitution truth unless the user explicitly changes functional intent.

## Gates

| Stage | Required reads | Allowed writes | Forbidden writes | Exit gate | Drift route |
| --- | --- | --- | --- | --- | --- |
| `app-constitution` | User intent, product docs, existing workflow artifacts, execution constraints when supplied | `docs/app-constitution.md` | plan tasks, graph nodes, dev packets | Every capability has stable id, owner, evidence need, and known state or gap | Functional drift stays here |
| `app-research` | Constitution, sources, existing waves, execution constraints when supplied | `waves/index.md`, `waves/<wave-id>/research.md`, `wave-research.packet.v1` | plan microtasks, graph nodes, dev packets | Every wave maps to constitution ids and records sources, decisions, unknowns, and next route | New functional truth returns to constitution |
| `app-specify` helper | Research questions, sources, user answers | `clarification.packet.v1` folded into research or response | standalone plan, graph, or dev artifacts | Missing actor, data, error, or acceptance detail is resolved or recorded as a blocking question | Unresolved choices return to research or constitution |
| `app-plan` | Constitution, research wave, current ledger, code observations when present, execution constraints when supplied | `waves/<wave-id>/plan.md`, `docs/app-task-ledger.v1.json` | graph node creation, dev dispatch | Every microtask has constitution refs, research refs, order, target paths, dependencies, roles, definition of done, proof, and status | Missing explanation returns to research; missing truth returns to constitution |
| `app-functional-graph` | Constitution, research, approved plan, ledger | `docs/app-functional-graph.v1.json`, ledger graph backlinks | new product decisions, new microtask scope | Every graph node has constitution refs, research refs, plan task refs, dev model kind, dependencies, and evidence refs | Missing plan route returns to plan |
| `app-dev` | Graph nodes with complete lineage, ledger, role catalog, optional support packets | task status, code changes in assigned paths, closeout notes | tasks outside ledger or graph | Assigned work is closed or blocked with evidence | Missing lineage returns to graph |
| `app-analyze` | Constitution, research, plan, graph, ledger, implementation state, target plugin files in file-audit mode | `waves/<wave-id>/analysis.md` | implementation fixes, test tooling | Broken link or file-level concern is named, or wave passes | Route by broken link type |

## Support checks inside `app-dev`

| Support skill | Required reads | Output | Exit gate |
| --- | --- | --- | --- |
| `subagents-roles` | Graph-backed task, ledger, `docs/role-catalog.md` | `role-packet.v1` | Owner, critic, helper roles are confirmed or a role gap is recorded. |
| `subagents` | Role packet, graph-backed task, target paths | `dispatch-packet.v1` | One bounded sequential handoff packet is ready. |
| `instruction-hardening` | Plan or dispatch packet, execution constraints when supplied | `hardening-output.v1` | Text is stricter and behavior-equivalent. |
