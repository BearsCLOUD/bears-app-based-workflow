# Development Workflow Orchestration Reference

Canonical files:

- `assets/catalog/agent-workflow-map.v1.json`
- `scripts/development_workflow_validate.py`
- `scripts/agent_workflow_map.py`
- `skills/development-workflow-orchestration/contracts/*.schema.json`

Packet order:

`user-agreement -> workspace-bootstrap -> architecture-packet -> task-graph -> domain-orchestrator-assignment -> worker-assignment -> worker-closeout -> review-result -> merge-decision -> stage-boundary-audit`.
