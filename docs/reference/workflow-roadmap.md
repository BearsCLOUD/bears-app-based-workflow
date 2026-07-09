# Workflow roadmap graph

## Scope

`assets/catalog/workflow-roadmap.v1.json` is the executable roadmap for @Bears issue work.

A node is one work item with a state, owner role, inputs, outputs, dependency links, and evidence paths.
A leaf node is a node with no `decomposes_to` children.

## States

`idea`, `researched`, `contracted`, `decomposed`, `queued`, `running`, `validated`, `closed`, `blocked`, `manual_review`.

## Node types

`research`, `contract`, `implementation`, `validator`, `migration`, `cleanup`, `closeout`.

## Required node fields

Each node must include `node_id`, `issue`, `node_type`, `state`, `owner_role`, `source_of_truth`, `inputs`, `outputs`, `depends_on`, `decomposes_to`, `blocked_by`, `autostart_policy`, and `evidence_paths`.

## Role authority

- `roadmap_researcher`: adds finding-backed candidate nodes only.
- `roadmap_curator`: normalizes nodes and rejects duplicate `node_id` values.
- `roadmap_decomposer`: adds child nodes and preserves parent `decomposes_to` links.
- `roadmap_executor`: receives only eligible leaf nodes from `next --json`.
- `roadmap_reconciler`: updates node state from GitHub or local evidence paths.

## Commands

```bash
scripts/workflow_roadmap.py validate
scripts/workflow_roadmap.py add-node --packet <path>
scripts/workflow_roadmap.py decompose --node <id>
scripts/workflow_roadmap.py next --json
scripts/workflow_roadmap.py reconcile --json
```

## Autostart rule

Autostart reads `scripts/workflow_roadmap.py next --json` when the roadmap exists.
The `nodes` list contains only queued, eligible, unblocked leaf nodes with ready dependencies.
No prose file grants roadmap authority.

## Reconcile rule

`reconcile --json` does not promote a node to `validated` only because `evidence_paths[]` files exist.
Validation promotion requires `bears-roadmap-state-transition-authority-transition.v1` evidence.
`manual_review`, `disabled`, and hazard-marked nodes stay unchanged and are reported in `blocked_transitions[]`.

### Resource-conflict gate

Evidence-backed nodes need `resource_conflict_status.status == "allow"` before `reconcile --json` can promote them or `next --json` can expose them as executable-ready. Stale, blocked, missing, or exclusive-active resource status keeps the node out of executable flow.
