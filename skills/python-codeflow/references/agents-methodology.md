# Repository AGENTS.md methodology

Use this reference only when creating, reviewing, or updating repository `AGENTS.md` files during Python development.

## Purpose

`AGENTS.md` is a router for future agents, not a full handbook. Keep it short. Put durable standards in linked docs, contracts, manifests, or runbooks.

## Required content

- Scope: exact directory or repository governed by the file.
- Project intent: one or two bullets describing the runtime/package purpose.
- Read-first links: architecture notes, module manifest/README, API contracts, plans, and validation docs.
- Python code rules: concise references to PEP 8, PEP 257, PyPA, `src/`, Clean/Hexagonal boundaries, canonical file layout, tests, and linting.
- Validation commands: exact repository commands, not generic guesses.
- Safety rules: secrets, production data, migrations, destructive operations, and environment boundaries.

## Hard rules

- Do not duplicate long standards already present in linked docs.
- Do not place secrets, `.env` values, raw configs, or production data in `AGENTS.md`.
- Do not make `AGENTS.md` depend on chat history.
- Do not claim a command is canonical unless it exists or is documented in the repository.
- When missing information blocks safe work, add a narrow TODO to `plans.md` or the repository's planning surface.

## Update triggers

Update or create `AGENTS.md` when:

- A new Python repository, package, service, or active subproject is created.
- Architecture boundaries, package layout, file-placement rules, validation commands, or runtime entrypoints change.
- A refactor moves files across domain/application/adapters/entrypoint boundaries.
- Repeated agent mistakes show the router is incomplete.

## Template

```markdown
# <Name> Agent Instructions

## Scope
- Applies to `<path>`.

## Project intent
- <short purpose>.

## Read first
- `<doc>` — <why it matters>.

## Python rules
- Keep package code under `src/`.
- Preserve domain/application/adapters boundaries.
- Put new files in canonical package, docs, and tests locations.
- Keep public docstrings useful and current.
- Update docs/manifests with code moves.

## Validation
- `<exact lint command>`
- `<exact targeted test command>`
- `<exact full test command>`

## Safety
- Never read or print secrets.
- <project-specific operational boundary>.
```
