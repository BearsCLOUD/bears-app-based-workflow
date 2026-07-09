---
name: app-analyze
description: Analyze Bears app workflow artifacts, implementation state, and plugin instruction quality. Use when Codex must compare constitution, research, plan, functional graph, task ledger, implementation, or every plugin file, then return pass or the exact broken link, drift, or reuse-quality concern.
---

# App Analyze

## Purpose

Compare constitution truth, research explanations, plan microtasks, graph lineage, ledger state, implementation state, and plugin-file reuse quality.

## Inputs

Read only the target wave artifacts and target files needed for the requested mode:

- `docs/app-constitution.md`
- `waves/<wave-id>/research.md`
- `waves/<wave-id>/plan.md`
- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- implementation target files when checking dev convergence
- plugin files when file-audit mode is requested

Do not read wider paths unless one required input points to a missing link.

## Output

Write `waves/<wave-id>/analysis.md` or return `analysis-audit.packet.v1` with one status:

- `schema: analysis-audit.packet.v1`
- `wave_id`
- `target_files`
- `quality_dimensions`
- `file_results`
- `cross_file_findings`
- `broken_links`
- `status`
- `next_skill`

`waves/<wave-id>/analysis.md` must contain the same values in the sections below.

- `pass`: constitution, research, plan, graph, ledger, code state, and requested file-audit checks agree.
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
- File reuse audit when plugin files or skills are the target.
- Broken links.
- Status.
- Next skill.

## File audit mode

For each target file, score these dimensions as `pass` or `concern` and cite exact file lines for every concern:

- usefulness: the file has a clear consumer.
- consistency: the file agrees with the workflow order and packet contracts.
- brevity: the file avoids duplicated or stale instructions.
- unambiguity: the file names one owner, one next route, and observable outputs.
- instruction coverage: the file covers required inputs, outputs, forbidden actions, and drift routes.
- portability: the file does not require a host-specific instruction file, role inventory, runtime, hook, or MCP server.
- degradation resistance: the file prevents skipped lineage, hidden authority, broad scope, and recursive loops.
- continuous-development readiness: the file tells the next agent what to read, write, update, and close.
- no-test-tooling risk: the file does not ask agents to create validation software or testing tools just to prove this workflow.

## Rules

- Do not fix implementation during analysis.
- Do not create tests, validators, scripts, cache tools, plugin validators, or workflow-testing software.
- Check graph node lineage in this order: constitution refs, research refs, plan task refs, graph backlinks, implementation state.
- Send functional drift to `app-constitution`.
- Send missing research explanation to `app-research`.
- Send missing or wrong microtasks to `app-plan`.
- Send missing or broken graph lineage to `app-functional-graph`.
- Send ready graph-backed work to `app-dev`.
- Report execution-constraint drift separately from functional drift.
- Use `blocked` only for access, credentials, unavailable source, or explicit stop signal.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
