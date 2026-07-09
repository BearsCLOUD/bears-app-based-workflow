# Functional Graph and Task Ledger Contract

## Ownership

- `docs/app-constitution.md` owns functional truth.
- `waves/<wave-id>/research.md` owns source-backed explanation of constitution ids.
- `waves/<wave-id>/plan.md` and `docs/app-task-ledger.v1.json` own ordered microtasks.
- `docs/app-functional-graph.v1.json` owns the dev-stage model built from approved microtasks.
- Execution constraints, when present, constrain execution but do not own functional truth.

## Graph node requirements

Every graph node must include:

- `node_id`: stable id inside one functionality.
- `functionality_id`: stable function record id; graph refs use `<functionality_id>:<node_id>`.
- `kind`: `ui`, `api`, `state`, `job`, `integration`, `data`, `error`, `instruction`, or `workflow`.
- `dev_model_kind`: `implementation`, `review`, `integration`, `evidence`, `handoff`, or `analysis`.
- `constitution_refs`: one or more ids from `docs/app-constitution.md`.
- `research_refs`: one or more `waves/<wave-id>/research.md#section` refs.
- `plan_task_refs`: one or more ledger task ids.
- `depends_on`: graph node refs formatted as `<functionality_id>:<node_id>`.
- `evidence_refs`: concrete docs, source files, anchors, code observations, or generated evidence refs; directory-only refs and wildcard refs are not sufficient.

A graph node without all three lineage arrays is not ready for `app-dev`.

## Function requirements

Every function record must include:

- `functionality_id`: stable id from the constitution capability or gap.
- `wave_id`: owning wave id.
- `title`: user-visible or operator-visible behavior.
- `constitution_refs`: constitution ids covered by the function.
- `research_refs`: wave refs explaining the function.
- `nodes`: graph nodes with complete lineage.
- `edges`: source and target graph refs plus relationship kind.
- `evidence_refs`: artifact or source refs supporting the model.
- `status`: `planned`, `modeled`, `ready_for_dev`, `in_dev`, `done`, `superseded`, or `blocked`.

## Ledger microtask requirements

Every ledger microtask must include:

- `task_id`
- `wave_id`
- `order`
- `title`
- `constitution_refs`
- `research_refs`
- `target_paths`
- `definition_of_done`
- `proof_requirement`
- `status`
- `graph_node_refs`
- `depends_on`
- `owner_role`
- `critic_role`

Allowed `status` values: `proposed`, `blocked_by_decision`, `blocked_by_research`, `ready_for_graph`, `graph_modeled`, `ready_for_dev`, `in_progress`, `in_review`, `done`, `superseded`, `blocked`.

`app-plan` creates approved microtasks with empty `graph_node_refs` or existing backlinks. `app-functional-graph` fills graph backlinks after it creates graph nodes from approved microtasks.

## Backlink rules

- `app-plan` may reference existing graph nodes only when a task is being revised after graph modeling.
- `app-plan` must not create graph node ids for new scope.
- `app-functional-graph` creates graph node refs and writes them back to matching ledger tasks.
- Existing graph ids referenced by ledger tasks must not be deleted. Supersede them and add replacement ids when contracts, skills, templates, or manifest entries change behavior.

## Readiness rules

- `ready_for_graph`: microtask has constitution refs, research refs, target paths, dependencies, owner role, critic role, definition of done, and proof requirement.
- `graph_modeled`: microtask has matching graph node refs with complete lineage.
- `ready_for_dev`: graph node dependencies are modeled and role coverage exists.
