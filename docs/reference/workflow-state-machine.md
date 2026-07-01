# Workflow state machine

Issue #439 adds a deterministic state machine for Bears goal execution.

## Authority

`assets/catalog/workflow-state-machine.v1.json` defines allowed states, transitions, guards, evidence requirements, and invariants.

## States

The catalog uses the exact #439 state set: intake, questioning, researching, planning, covered, ready_for_execution, running, waiting_validation, remediating, waiting_closeout, closed, blocked, manual_review, cancelled.

## Safety rules

- Unknown transitions fail.
- Missing evidence fails the transition.
- Execution transitions require a decision graph, accepted inference, and file context.
- Closeout transitions require validation pass and no blocking debt.
- Degradation events can force only `manual_review`.

## Commands

```bash
python3 scripts/workflow_state_machine.py validate --json
python3 scripts/workflow_state_machine.py can-transition --packet tests/fixtures/workflow_state_machine/good/run-transition.json --json
python3 scripts/workflow_state_machine.py apply --packet tests/fixtures/workflow_state_machine/good/run-transition.json --json
python3 scripts/workflow_state_machine.py check-invariants --goal-id goal-438 --json
python3 scripts/workflow_state_machine.py doctor --json
```
