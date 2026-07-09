---
name: app-analyze
description: Analyze Bears app workflow artifacts against implemented code state. Use when Codex must compare constitution, research, plan, functional graph, task ledger, and implementation, then return pass or the exact broken link.
---

# App Analyze

## Purpose

Compare constitution truth, research explanations, plan microtasks, graph lineage, ledger state, and implemented code state.

## Output

Write `waves/<wave-id>/analysis.md` with one status:

- `pass`: constitution, research, plan, graph, ledger, and code state agree.
- `needs-constitution`: functional truth is missing, partial, or drifted.
- `needs-research`: constitution truth lacks source-backed explanation.
- `needs-plan`: research explanation lacks a microtask or the microtask is wrong.
- `needs-graph`: a graph node or graph backlink is missing or has broken lineage.
- `needs-dev`: graph-backed task is ready but not implemented.
- `blocked`: progress requires access, credentials, unavailable source, or an explicit stop signal.

## Analysis sections

- Wave and target.
- Inputs reviewed.
- Lineage check.
- Implementation comparison.
- Broken links.
- Status.
- Next skill.

## Rules

- Do not fix implementation during analysis.
- Check graph node lineage in this order: constitution refs, research refs, plan task refs, graph backlinks, implementation state.
- Send functional drift to `app-constitution`.
- Send missing research explanation to `app-research`.
- Send missing or wrong microtasks to `app-plan`.
- Send missing or broken graph lineage to `app-functional-graph`.
- Send ready graph-backed work to `app-dev`.
- Report host-policy drift separately from functional drift.
- Use `blocked` only for access, credentials, unavailable source, or explicit stop signal.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
