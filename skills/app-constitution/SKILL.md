---
name: app-constitution
description: Create or update the first-stage app constitution as a short functional baseline and app-local AGENTS alignment pass. Use when Codex needs a compact app functionality summary, important functional gaps, stable app rules, or a baseline before app research, specification, graph planning, analysis, or implementation.
---

# App Constitution

## Output

Maintain one app-local `docs/app-constitution.md` file. Keep it at 100 physical lines or fewer. Link waves, specs, graphs, ledgers, and source files instead of copying detail.

Also inspect the nearest `AGENTS.md` chain. Create or update the app-local `AGENTS.md` only for stable app-specific instruction rules.

## Required constitution sections

1. `Functional summary`
2. `Core capabilities`
3. `Actors and runtime surfaces`
4. `Constraints and evidence`
5. `Functional gaps`
6. `Open decisions`
7. `AGENTS alignment note`
8. `Next skill`

## Functional gap format

Write every gap as a compact record:

- `gap`: missing, partial, or drifted functionality.
- `impact`: user, runtime, data, or delivery impact.
- `evidence`: exact source, doc, wave, graph, ledger, code observation, or AGENTS rule.
- `route`: next owner skill such as `app-research`, `app-specify`, `app-functional-graph`, or `app-plan`.

## Gap discovery pass

Compare all available functional sources before routing the next skill:

- User intent and product decisions.
- Existing docs, wave files, specs, functional graph, and task ledger.
- Code observations and runtime-surface notes.
- Nearest parent and app-local `AGENTS.md` rules.
- Known constraints, evidence requirements, data ownership, and secret boundaries.

Record missing, partial, and drifted functionality in `Functional gaps`. Keep uncertain choices in `Open decisions`.

## AGENTS alignment

- `AGENTS.md` is instruction authority for its subtree; the constitution is a functional baseline, not authority.
- If constitution content conflicts with `AGENTS.md`, follow `AGENTS.md`, add a drift note to `AGENTS alignment note`, and route a fix to the owning `AGENTS.md` or contract.
- If app-local `AGENTS.md` is missing and stable app-specific rules exist, create a short router with: app path, parent rule narrowed, `docs/app-constitution.md` link, stable app rules, and evidence/source boundaries.
- If app-local `AGENTS.md` exists but misses or misstates a stable app-specific rule, update that file with the narrow rule.
- Do not write workspace-wide rules. Do not override parent `AGENTS.md` files or contracts.
- Temporary, disputed, or functional details belong in `Open decisions` or `Functional gaps`, not in `AGENTS.md`.

## Rules

- Keep `docs/app-constitution.md` app-local and no longer than 100 lines.
- Record concrete decisions only. Put uncertain items under `Open decisions`.
- Use role-matched subagents for bounded constitution slices when sources, rules, or runtime surfaces are independent.
- Do not create implementation tasks here.
- Send missing product choices to `app-specify`.
- Send missing source or domain knowledge to `app-research`.
- Send graph or ledger drift to `app-functional-graph` or `app-plan`.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
