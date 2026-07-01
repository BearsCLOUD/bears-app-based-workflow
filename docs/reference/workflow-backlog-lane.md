# Bears Workflow Backlog Lane

Snapshot date: 2026-06-18.
Source: GitHub open issues in `BearsCLOUD/bears_plugin`.
Scope: Bears workflow plugin planning, validators, catalogs, docs, and issue routing only.

## Current issue state

| Metric | Count |
| --- | ---: |
| Open issues | 99 |
| Unlabeled open issues | 0 |
| `type:develop-ready` | 30 |
| `type:bugfix` | 60 |
| `type:idea` | 5 |
| `bug` | 4 |

## Workflow area classification

| Area | Count | Primary action |
| --- | ---: | --- |
| `parallelization_preflight` | 22 | Drive through #173 slices. |
| `merge_handoff_gate` | 20 | Drive through #132 slices. |
| `git_branch_repo_hygiene` | 12 | Drive through #133, #88, #144, and #128. |
| `role_gate_coverage` | 7 | Drive through #73 and #80 coverage slices. |
| `github_issue_dev_cd` | 6 | Drive through GitHub issue-type and agent pickup policy. |
| `validation_overlay` | 9 | Drive through validator evidence slices. |
| `secret_factory` | 3 | Keep separate from branch cleanup and runtime work. |
| `uncategorized` | 20 | Label triage complete; content classification still needs future narrowing. |

## Develop-ready execution order

| Order | Issue lane | Slice | Changed surface | Validators |
| ---: | --- | --- | --- | --- |
| 1 | #173, #103, #154, #153, #142, #138, #158, #157 | Goal parallelization preflight first slice. | `assets/catalog/subagent-orchestration-policy.v1.json`, `scripts/subagent_orchestration_policy.py`, tests. | local-commit-owned subagent orchestration validator and unit coverage; local execution requires operator approval. |
| 2 | #133, #88, #144, #128, #132, #120 | Branch hygiene and cleanup evidence slice. | `assets/catalog/git-discipline.v1.json`, `scripts/git_discipline.py`, `docs/reference/git-discipline.md`, tests. | local-commit-owned Git discipline validator and unit coverage; local execution requires operator approval. |
| 3 | #132, #119, #116, #115, #105, #90 | Merge handoff gate slice. | Agent GitHub dev CD catalog, validator, tests. | local-commit-owned Agent GitHub dev CD validator and unit coverage; local execution requires operator approval. |
| 4 | #128, #133 | Gitlink sync audit/helper slice. | Git discipline catalog, helper command, tests, README inventory. | local-commit-owned Git discipline and overlay validator coverage; local execution requires operator approval. |
| 5 | #73, #80, #85 | Role coverage and source freshness preflight slice. | Platform role catalog, route validator, tests. | Agent-local route checks for exact targets; local-commit-owned catalog validator and unit coverage; local validator or test execution requires operator approval. |
| 6 | Remaining broad issues | Content triage slice. | GitHub issue bodies and labels only. | GitHub issue list diff: no unlabeled open issues; no product/runtime changes. |

## Duplicate and overlap decisions

| Issues | Decision |
| --- | --- |
| #103 and #173 | Not duplicates. #103 is the no-eligible-task classifier inside #173. |
| #132, #119, #116, #115, #105, #90, #120 | Not duplicates. They are merge handoff sub-gates under #132. |
| #128 and #133 | Overlap only at closeout. #128 owns gitlink target audit; #133 owns clean worktree and closeout guard. |
| #88 and #144 | Not duplicates. #88 owns branch base proof; #144 owns branch prefix governance. |
| #73, #80, #85 | Not duplicates. They share role-gate preflight but cover different source and target surfaces. |

## Missing issue assignments now covered

| Gap | Assigned issue |
| --- | --- |
| Branch cleanup inventory before deletion | #133 |
| Branch base proof before worker branches | #88 |
| `codex/` branch prefix governance | #144 |
| Gitlink target object sync audit | #128 |
| Merge authority and handoff gate | #132 |
| Durable PASS evidence before merge handoff | #120 |
| Central goal parallelization preflight | #173 |
| No eligible subagent task is not a blocker | #103 |

## First PR slice for #173

PR #177 is the first bounded implementation slice.

It adds:

- `goal_parallelization_preflight.issue_mapping` with #173 as the central lane.
- read-only local branch inventory under Git discipline.
- branch cleanup issue mapping for branch/repo hygiene issues.
- unit coverage and validator checks for the new mappings.

PR #177 does not close #173. PR #179 adds remote branch inventory. PR #181 guards symbolic remote HEAD refs. The remaining #173 work is merge handoff enforcement, reusable worker state reconciliation, and content triage for broad issues.

## Label triage result

All 99 open issues now have at least one type label. Current unlabeled count: 0.

## Remote branch cleanup evidence

`branch-inventory` now emits `remote_branches` with `remote_delete_eligible`. Remote branch deletion still requires explicit operator approval and must not run from validator code. Current post-cleanup inventory found 3 remote refs and 0 remote cleanup candidates.
