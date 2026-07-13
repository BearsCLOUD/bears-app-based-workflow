---
name: app-solo-route
description: Sequentially route one DIRECT primary through app workflow stages to audited, blocked, or an external development boundary.
---

# App Solo Route

Run only for a `DIRECT` workstream. Start with `$app-context-index`. Validate every `app-stage-handoff.v3` against the v3 schema and resolve its status and target only from `app-workflow-definition.v2`; never keep a local route table.

Resume the earliest incomplete stage in order: constitution, research, specification, functional graph, plan, development boundary, analyze. The same primary performs internal stages. Stop at `app-constitution`, `app-dev`, `blocked`, an unchanged waiting/handoff fingerprint, or a genuinely unresolved architecture decision.

Before each handoff, run the process audit, validate the transition, record only the actual event, and compile with CAS. At graph, plan, and analyze boundaries also run the semantic, planning, or convergence trace profile respectively. `audited` is the only successful terminal status and means semantic/process consistency, never product acceptance. L3 workers never write the journal.
