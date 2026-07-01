---
name: python-codeflow
description: Use when Codex develops, reviews, or refactors Python code, Python packages, Python services, or repository Python standards. Enforce a short hard codeflow covering PEP 8 style, PEP 257 docstrings, PyPA packaging, src-layout, Clean/Hexagonal Architecture boundaries, runtime module splitting, flake8 validation, repository AGENTS.md methodology, documentation updates, tests, gitflow hygiene, and file-structure standards.
---

# Python Codeflow

## Trigger rules

- If any task edits or reviews Python files (`*.py`) beyond a trivial one-line
  change, load this skill even when another domain skill also applies.
- Use this skill together with MCP, UI, infra, Android, or documentation skills
  when Python is the implementation or review layer.
- If a changed Python file exceeds 400 lines, explicitly call it out as a long
  file and either split it in the current scope or record/refine a module-split
  plan with validation evidence.
- Split any runtime module (entrypoint, daemon, worker, server, or bot runner)
  that exceeds 400 LOC or carries 3+ responsibilities into the owning domain
  package in the current scope; leave only runtime wiring in the runtime file.
- Keep 200 lines as the target norm for focused Python modules; files above that
  should have a clear boundary reason, documented split path, or active
  follow-up.

## Hard codeflow

1. Start from the nearest `AGENTS.md`; if it is missing for a repository or active subproject, create a short router before broad edits.
2. Identify the Python change zone: package root, `pyproject.toml`, `src/`, tests, docs, and known callers.
3. Keep changes small and cohesive; do not mix feature work, refactoring, formatting, and unrelated cleanup unless the task requires it.
4. Preserve public interfaces by default; if an interface changes, update callers, tests, docs, and migration notes in the same change.
5. Prefer `src/` layout for packages; do not add importable package code at repository root.
6. Keep Clean/Hexagonal boundaries: domain has business rules only, application orchestrates use cases, adapters handle I/O/frameworks, entrypoints wire dependencies.
7. Split any runtime module over 400 LOC or with 3+ responsibilities before closeout: move business rules to `domain/`, use cases to `application/`, I/O to `adapters/`, and keep startup/config wiring in `entrypoints/` or the project-defined runtime package.
8. Follow PEP 8 and project style; use `flake8` or the repository's declared lint command before closeout.
9. Follow PEP 257: every public module, class, method, and function needs a useful docstring that states purpose and boundaries, not obvious mechanics.
10. Follow PyPA packaging: keep `pyproject.toml` authoritative for build system, project metadata, dependencies, optional dev tools, and package discovery.
11. Document changed code paths in the nearest durable docs: module README/manifest, API docs, architecture notes, or `AGENTS.md` router.
12. Add or update tests for behavior changes; for refactors, run equivalence tests or add characterization tests before moving logic.
13. Treat gitflow as both branch hygiene and file-layout hygiene: keep files in their canonical layer/package/docs/test location, avoid duplicate parallel trees, and move/rename with callers, imports, manifests, and docs updated in the same change.
14. Finish with gitflow hygiene: inspect status/diff, avoid secret output, keep commits scoped, and do not leave accidental generated files or dirty unrelated work.

## Repository `AGENTS.md` methodology

Read `references/agents-methodology.md` when creating or updating repository `AGENTS.md` files.

Minimum router shape:

```markdown
# <Project> Agent Instructions

## Scope
- State the directory/repository this file governs.

## Read first
- Link the project contract, module manifest, architecture notes, and validation commands.

## Rules
- Keep short, enforceable rules only.
- Move durable details into linked docs/contracts.

## Validation
- List exact lint/test/build commands for Python work.
```

## File-structure standard

- `src/<package>/domain/` contains entities, value objects, domain services, and business rules only.
- `src/<package>/application/` contains use cases, ports/interfaces, orchestration, and transaction boundaries.
- `src/<package>/adapters/` contains database, HTTP, CLI, framework, filesystem, queue, and third-party integrations.
- `src/<package>/entrypoints/` or project-defined runtime modules wire adapters to application use cases. Runtime modules over 400 LOC or with 3+ responsibilities must be split into the owning domain package in the same change.
- `tests/` mirrors behavior boundaries; keep unit tests near domain/application behavior and integration tests near adapters/runtime seams.
- `docs/`, module manifests, and `AGENTS.md` describe ownership, validation, and boundaries; do not hide durable methodology in code comments.
- `pyproject.toml` is the package/tooling source of truth; avoid split configuration unless the repository already uses it.
- Deprecated files move to the repository's documented archive/deprecated area or are deleted in the same scoped change; never leave shadow copies.

## Python validation ladder

Run the narrowest available checks first, then broaden only as needed:

```bash
python -m py_compile <changed_files_or_package>
python -m pytest <targeted_tests>  # local-commit-owned or operator-approved
python -m flake8 <changed_package_or_repo>
python -m pytest  # local-commit-owned or operator-approved
```

If the repository uses `uv`, `tox`, `nox`, `hatch`, `poetry`, `ruff`, or a Make target, use the repository-declared command instead of inventing a parallel workflow. If `flake8` is required by the task or contract but unavailable, add/configure it or record a concrete follow-up only when adding it is out of scope.

## Review checklist

- PEP 8 style and flake8 path are covered.
- PEP 257 docstrings exist for changed public symbols.
- PyPA metadata is current for packaging/dependency changes.
- `src/` layout is preserved or planned.
- Domain/application/adapters boundaries are not crossed.
- Runtime modules over 400 LOC or with 3+ responsibilities are split into the owning domain package, with only wiring left in runtime files.
- File placement matches the canonical layer/package/docs/test structure.
- Tests prove behavior, not only import success.
- Docs and nearest `AGENTS.md` still route future agents correctly.
- Git diff contains only intentional changes.
