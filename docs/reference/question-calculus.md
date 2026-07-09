# Question Calculus

The question calculus is the JSON authority for material Bears workflow decisions.

## Canonical files

- Operator schema: `assets/schemas/question-operator.v1.schema.json`.
- Answer proof schema: `assets/schemas/question-answer-proof.v1.schema.json`.
- Decision graph schema: `assets/schemas/decision-graph.v1.schema.json`.
- Operator catalog: `assets/catalog/question-calculus.v1.json`.
- Question bank: `assets/catalog/question-bank.v1.json`.
- Operator CLI: `scripts/question_calculus.py`.
- Decision graph CLI: `scripts/decision_graph.py`.
- Tests: `tests/test_question_calculus.py`.

## Rule set

- No material execution without a decision graph.
- No gate unlock without an accepted answer proof.
- Operators are deterministic and versioned.
- Ambiguous answers return `manual_review` or `research_required`.
- Decision graphs must reference accepted #435 semantic facts.
- LLM text is not evidence until converted into a bounded validated packet.

## Commands

```text
python3 scripts/question_calculus.py validate --json
python3 scripts/question_calculus.py ask --operator <id> --input <path> --json
python3 scripts/question_calculus.py prove-answer --packet <path> --json
python3 scripts/decision_graph.py build --goal-id <id> --json
python3 scripts/decision_graph.py check-gate --goal-id <id> --gate <id> --json
python3 scripts/decision_graph.py doctor --json
```

## Gate behavior

An accepted proof can unlock only the gates listed in its operator record. A candidate, rejected, invalid, `manual_review`, or `research_required` answer blocks material execution.
