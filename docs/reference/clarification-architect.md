# Clarification Architect

`clarification_architect` turns an under-specified `/goal` packet into a deterministic clarification question batch before planning or implementation starts.

## Role boundary

The role is read-only. It does not plan, implement, assign workers, edit files, run commands, or select a solution path.

## Runtime contract

Bounded command:

```text
codex exec --sandbox read-only --output-schema assets/schemas/clarification-role-result.v1.schema.json -
```

The compiled prompt may include only:

- goal packet
- current decision graph
- known answers
- allowed question operators
- relevant context pack ids
- role profile

The role returns JSON conforming to `assets/schemas/clarification-role-result.v1.schema.json`.

## Deterministic gate

`/goal` enters this role before planning. The role reads the decision graph and emits only questions that can unlock one declared gate. Each question names:

- `operator_id`: the versioned decision operator from `assets/catalog/question-calculus.v1.json`.
- `gate_id`: the exact gate blocked by the missing answer.
- `answer_type`: the machine answer type.
- `required_evidence_types`: the proof source required before the answer can unlock the gate.
- `question_fingerprint`: the stable duplicate key.
- `priority`: `P0`, `P1`, or `P2`.

## Failure policy

The result fails closed when any of these conditions appear:

- a question has no `gate_id`;
- a question has no `operator_id`;
- a question has no `answer_type`;
- a `freeform_bounded` question has no byte limit;
- two active questions share the same `question_fingerprint`;
- a scope-changing question does not set `scope_change_request` to `true`;
- a `P0` question does not set `blocks_execution` to `true`;
- the result contains planning or implementation instructions.

## Empty batch

When the goal packet, decision graph, and known answers already prove the needed gates, the role returns an empty `questions` array and a non-empty `no_questions_reason`.

## Linked artifacts

- `assets/catalog/clarification-question-methodology.v1.json`
- `assets/catalog/role-profiles/clarification-architect.v1.json`
- `assets/schemas/clarification-question.v1.schema.json`
- `assets/schemas/clarification-question-batch.v1.schema.json`
- `assets/schemas/clarification-role-result.v1.schema.json`
- `prompts/roles/clarification-architect.md`
