# Workflow inference

Issue #438 adds deterministic Datalog-style inference for Bears workflow facts.

## Authority

`assets/catalog/workflow-inference-rules.v1.json` is the source of truth for facts, rule groups, and closed-world predicates.

## Safety rules

- Accepted facts can derive execution permissions.
- Candidate facts can derive only `research_required`, `planning_required`, or `manual_review_required`.
- Rejected facts are never materialized as truth.
- Negation requires an explicit closed-world predicate in the catalog.
- Each derived fact includes `proof_trace` with the source fact ids.

## Commands

```bash
python3 scripts/workflow_inference.py validate --json
python3 scripts/workflow_inference.py materialize --input tests/fixtures/workflow_inference/good/accepted-can-write.json --json
python3 scripts/workflow_inference.py query --predicate can_write --args '["bears-machine-first-execution-kernel-engineer","scripts/workflow_inference.py"]' --json
python3 scripts/workflow_inference.py explain --fact derived-can_write-bears-machine-first-execution-kernel-engineer-scripts_workflow_inference.py --json
python3 scripts/workflow_inference.py doctor --json
```
