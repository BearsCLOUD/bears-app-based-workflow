# Workflow Tree Contract

The workflow tree is the machine-readable root index for a governed `@bears` goal or issue task.

## Authority

- `assets/schemas/workflow-tree.v1.schema.json` defines the root packet.
- `assets/schemas/workflow-node.v1.schema.json` defines reusable node packets.
- `assets/catalog/workflow-tree-contract.v1.json` lists required fields, commands, and validation rules.
- `scripts/workflow_tree.py` is the deterministic validator and packet editor.

Human-readable text explains the contract. JSON packets and validators are authoritative.

## Required node behavior

Each node declares owner role, repo boundary, target paths, allowed write scope, forbidden scope, inputs, outputs, allowed runners, validation commands, evidence outputs, blocker conditions, closeout conditions, and next nodes.

A node fails validation when it has no owner role, no target path, no allowed runner, no validator, target paths outside allowed write scope, forbidden data markers, or missing closeout evidence.

## Graph rules

- One root node is required.
- Edges must reference existing nodes.
- Unreachable nodes fail validation.
- Cycles fail unless the edge is `bounded_loop` with `max_iterations`.
- Closeout must point to a closeout node and required evidence.

## Command surface

- `python3 scripts/workflow_tree.py validate`
- `python3 scripts/workflow_tree.py init --goal-id <id> --issue <issue>`
- `python3 scripts/workflow_tree.py add-node --tree <path> --packet <node.json>`
- `python3 scripts/workflow_tree.py check-node --tree <path> --node-id <id>`
- `python3 scripts/workflow_tree.py check-closeout --tree <path>`
- `python3 scripts/workflow_tree.py emit-report --tree <path> --json`

## Integration state

Artifact registry, decision ledger, and `bears_doctor` integration stay `not_available` until their issue surfaces land. The workflow tree stores those dependencies as required artifacts and decisions without pretending that future validators exist.
