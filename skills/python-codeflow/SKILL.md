---
name: python-codeflow
description: Guide bounded Python code changes for Bears workflow tasks. Use when an app-dev L3 packet targets Python files and needs clear module boundaries, import hygiene, data contracts, and closeout notes.
---

# Python Codeflow

## Process

1. Identify the owning package, module, and caller path.
2. Keep one responsibility per module.
3. Put reusable domain logic outside CLI, UI, and transport glue.
4. Preserve public imports or update every caller in the same task.
5. Keep data shapes explicit with typed dictionaries, dataclasses, Pydantic models, or documented JSON fields.
6. Return changed files, behavior change, and unresolved risks.

## File rules

- Do not create parallel duplicate packages.
- Do not hide side effects in import time.
- Keep command-line entry points thin.
- Keep exceptions actionable and domain-specific.
- Keep generated files out of hand-written source trees unless the task names them.
