---
name: python-codeflow
description: "Independent reusable Bears L3-local Python standard for a bounded worker task that changes Python code; it does not own orchestration, GitHub Project state, app PASS, lanes, or task proof."
---

# Python Codeflow

Required: activate this skill only inside a bounded worker task that changes Python files.

## Ownership boundary

- This skill is an L3-local coding standard.
- It does not choose tasks, lanes, repos, roles, GitHub Project fields, or closeout state.
- It does not replace `$app-dev`, `$subagents`, route gates, app proof, or gitflow closeout.
- Follow the nearest `AGENTS.md` and the task packet first.

## Python rules

- Keep package code in the repo's canonical package root, preferably `src/<package>/` when the repo already uses src layout.
- Keep domain rules in `domain/`, application cases in `application/`, I/O adapters in `adapters/`, and startup/config wiring in `entrypoints/` or the repo-defined runtime package.
- Preserve Clean/Hexagonal boundaries: domain code must not import framework, database, HTTP, queue, filesystem, or provider clients.
- Public modules, classes, methods, and functions need useful docstrings that state purpose and boundary.
- Keep `pyproject.toml` authoritative for build metadata, dependencies, optional tools, and package discovery.
- Do not create duplicate parallel trees or shadow copies.
- Move/rename with callers, imports, manifests, and docs updated in the same bounded change.
- Document changed behavior in the nearest durable docs when the task changes public or operator-visible behavior.
- Keep the diff task-owned and do not stage unrelated files.

## Review checklist

- Python package placement matches the repo layout.
- Domain/application/adapters boundaries stay separated.
- Public docstrings are meaningful.
- Packaging metadata remains current when dependencies or package discovery change.
- Runtime modules are split when they hold multiple unrelated responsibilities.
- Changed docs and imports point at the new paths.
- The final diff contains only task-owned files.
