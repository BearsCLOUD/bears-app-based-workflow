---
name: projectdevsubagents
description: "Use for Bears development orchestration from GitHub Projects and Issues where the parent controls only L2 orchestrators, L2 orchestrators control only Project/Issue state and L3 assignments, and all implementation is executed by @Bears L3 subagents with gpt-5.4-mini high."
---

# Project Dev Subagents

Use this skill for **development orchestration from GitHub Project work items**.

This skill does not define GitHub Project administration. Project administration means creating Projects, choosing fields, designing views, building roadmap structure, and setting long-lived planning policy. That belongs to `$app-docs2project-bears` or the owning repo/workstream governance. This skill starts after a Project or issue set exists, `$bears-project-analyze` has returned `pass` or an operator-approved advisory handoff, and the parent provides ready Project/Issue state for orchestration.

## Boundary

In scope:

- consume GitHub Project items, linked Issues, sub-issues, PR metadata, Actions metadata, Release metadata, and route/audit results;
- split Project work into L3 assignment packets;
- coordinate L2 orchestrators and L3 workers;
- update Project/Issue state only from evidence;
- request gitflow closeout;
- report exact Project/Issue execution status.

Out of scope:

- creating a new Project unless an explicit operator packet says so;
- deciding the organization's Project field model;
- replacing roadmap governance;
- replacing issue-type policy;
- replacing repo-local specs, acceptance criteria, or product ownership;
- doing implementation in the parent or L2 lane.

## Apps repo boundary

For `BearsCLOUD/apps`, `apps` is the repository name and `/srv/bears/dev/app` is the local repo root. Do not create or route `/srv/bears/dev/app/apps`.

Project-management policy may choose one canonical Project for `BearsCLOUD/apps` or another approved structure. This skill consumes that Project/Issue state and treats app directories or legacy source repos as work items, Issues, or sub-issues according to that policy.

## Required upstream artifacts

Before execution, the parent must provide one of these:

- `app-docs2project-bears.project-task-packet` plus `bears-project.analysis-packet` with `execution_handoff=ready`;
- existing GitHub Project/Issue state plus explicit operator approval that replaces those packets.

The plan must define owner repo, target paths, route-selected roles, dependencies, validation, and closeout fields for every item.

## Required topology

```text
Parent agent
  -> L2 GitHub/project orchestrator subagents
      -> L3 @Bears implementation/review subagents
      -> L3 role-improvement subagent when role gaps appear
  -> one persistent gitflow closeout subagent
```

## Parent control lane

The parent agent is orchestration-only. Parent allowed actions:

- select the existing Project, repository set, issue query, L2 lanes, and ready analysis packet;
- start or reuse L2 orchestrators;
- pass Project item ids, Issue ids, PR ids, Actions metadata ids, Release ids, and route/audit targets;
- wait for L2 evidence packets;
- integrate L2 closeout packets;
- request commit/push closeout through `bears-git-workflow-helper`;
- report exact Project/Issue status.

Parent forbidden actions:

- file writes;
- implementation commands;
- direct Project administration; pass explicit operator-authorized metadata requests to L2 instead;
- `git add`, `git commit`, `git push`, merge, or force push;
- direct PR mutation; pass explicit operator-authorized metadata requests to L2 instead;
- runtime, deploy, provider, secret, repository settings, branch protection, or production mutation.

## L2 orchestrator lane

Each L2 orchestrator must run the `bears-github-project-issues-orchestrator` role. L2 is not a developer. L2 turns Project work into bounded L3 tasks.

## Runtime fallback and deadline rules

- If the exact L2 agent type `bears-github-project-issues-orchestrator` is unavailable, use the approved runtime proxy `bears-development-workflow-orchestrator` with explicit `role=bears-github-project-issues-orchestrator`; if that proxy is unavailable or unauthorized, return `FAST_BLOCKER` before dispatch.
- The runtime proxy must enforce the same L2 deadline rules in its role profile and the GitHub Project subagents catalog/script guard before any fallback implementation pool is used.
- After any five-minute miss, the next attempt must be one-file/one-issue or issue-strengthening only; no grouped implementation retry is allowed.
- When the parent supplies an exact Issue plus route/audit evidence, L2 must skip broad Project scans and read only metadata required for that Issue.
- L2 must set an internal child cutoff before 240 seconds, close descendants before that cutoff, and return `FAST_BLOCKER` with no WIP when completion is not proven.
- The parent must reject any L2 result with elapsed time greater than 300 seconds, even when the final text says `PASS`.
- No WIP may remain after timeout; cleanup is mandatory before any retry.
- Current drift issue #25: `BearsCLOUD/bears_plugin#25`.

## Issue #26 capacity and timeout slicing rules

- Current drift issue #26: `BearsCLOUD/bears_plugin#26`.
- `parent capacity preflight`: before parallel L2 fan-out, the parent must prove available L2 agent slots, each lane's L3 spawn capacity, exact Issue scope, route/audit target, target file or contract, validation path, and 240s/270s cutoff. If capacity is unknown, at thread limit, or unavailable, the parent may start only one smaller L2 lane or must return a parent-visible `FAST_BLOCKER`.
- `first-minute visible state`: every L2 must return exactly one parent-visible `READY`, `WIP`, or `FAST_BLOCKER` packet inside 60 seconds. `READY` requires verified capacity and a bounded execution path. `WIP` is allowed only for metadata/decomposition work already in progress with no L3 spawn yet, exact next action, and cutoff. Missing first-minute packet is timeout drift.
- `L3 capacity failure`: if L3 spawn fails, runner capacity is unavailable, or a thread limit blocks child launch, L2 must stop silently waiting, close or interrupt descendants it owns, create or update a smaller Issue or issue comment with exact evidence, and return `FAST_BLOCKER`; it must not continue as if L3 were running.
- `parent wait max 300s`: the parent wait ceiling is 300 seconds from L2 assignment receipt. Any L2 packet returned after 300 seconds is SLA drift and cannot be accepted as `PASS`, `READY`, `ADOPTED_WITH_GITFLOW_PACKET`, or normal completion.
- `L2 execution lane 240s target`: every L2 execution lane must plan for validated completion, gitflow-ready evidence or blocker evidence, and task-owned cleanup inside 240 seconds. The lane must hard-stop before 270 seconds, stop descendants, and return `FAST_BLOCKER`, `CLEANED_NO_WIP`, or `DRIFT_CLEANED` before the parent ceiling.
- `no PASS after 300s`: L2 must not claim PASS after the parent ceiling. Evidence that arrives after 300 seconds may be used only for recovery triage, adopt-or-clean validation, issue comments, or a later smaller lane; it must not update Project/Issue completion state as normal success.
- `prep-only after timeout`: after any grouped-lane, atomic-lane, execution-lane, metadata-lane, or cleanup-lane timeout, the next L2 assignment must be prep-only until it proves one ready child Issue, Project item placement, exact target path, route/audit target, execution mechanism, validation path, and cutoff. Prep-only lanes must not dispatch L3 or perform implementation.
- `one issue one target one L3 max`: each post-timeout execution lane may cover exactly one Issue, one repo boundary, one target file or target path, one route/audit target, one validation path, and at most one L3 worker. If more work is required, return `DECOMPOSED_ONLY`, `PARTIAL_DECOMPOSED_ONLY`, or `FAST_BLOCKER`.
- `WIP proof before cutoff`: before the 270-second hard stop, L2 must either remove only task-owned uncommitted edits or report exact task-owned WIP paths with `git status --short -- <target>` evidence. Missing WIP proof before cutoff is workflow drift.
- `close-before-240`: when final PASS evidence is not already present by 240 seconds, L2 must close, interrupt, or explicitly orphan as blocked every owned L3 before returning `FAST_BLOCKER`; waiting for late child output after 240 seconds is workflow drift.
- `post-close bounded WIP proof`: after closing an execution or cleanup lane, L2 must run bounded path proof before claiming clean or absent: `git status --short -- <target>` for tracked paths and `test ! -e <target>` for expected-new-file paths. A clean/absent claim without post-close proof is invalid.
- `Project item placement before L3`: L2 must verify the selected Issue is placed in the required GitHub Project item and dependency-ready before any L3 dispatch. Missing Project item placement returns `MISSING_EVIDENCE`, `DECOMPOSED_ONLY`, or `FAST_BLOCKER`; it is not execution-ready.
- `EXECUTION_HOLD before L3`: before any L3 dispatch, L2 must prove a first-minute progress path: child Issue or approved template, Project item placement, route/audit target, exact write scope, authorized L3 or patch-template mechanism, validation command, cleanup path, and enough remaining budget for runner startup plus validation. If any proof is missing, set `EXECUTION_HOLD`, perform only the necessary Issue/Project comment or metadata narrowing, and return `METADATA_ONLY` or `FAST_BLOCKER`; the held item is not `READY`, execution `PASS`, or closeout evidence.
- `metadata closeout separate`: metadata closeout may be a separate L2 assignment after execution evidence or gitflow evidence exists. Under SLA pressure a metadata-only lane must perform one operation only, such as add-to-project, set status, comment, or close issue.
- `repeated timeout decomposition`: every repeated timeout must cite `BearsCLOUD/bears_plugin#26` evidence in the next packet and decompose smaller than the missed lane before retry; widening scope after timeout is forbidden.
- `repeated timeout issue update`: when the same target misses the L2 deadline again, the next packet must update `BearsCLOUD/bears_plugin#26` with the lane id, elapsed seconds, target, WIP proof command result, and next smaller metadata-only action before any implementation retry.
- `metadata reinforcement before retry`: after timeout on a reinforced child slice, prefer metadata-only Issue/comment repair that narrows authorization, target path, validation, and missing prerequisite proof before spawning another L3. A second immediate L3 retry needs exact parent authorization and first-minute `READY`.
- `grouped-lane timeout`: when a grouped L2 lane misses the five-minute parent gate or the parent rejects an over-300-second result, the next attempt must be issue-strengthening only or one-file/one-issue L2 slicing; grouped implementation retry is forbidden.
- `atomic-lane timeout`: when an atomic one-issue L2 lane misses the five-minute parent gate, times out during a child-only attempt, or returns time-based `FAST_BLOCKER`, the next attempt must stay atomic and either use one-file L2 slicing or improve the Issue packet; widening back to grouped execution is forbidden.
- `one-file L2 slicing`: after any grouped-lane timeout or atomic-lane timeout, the L2 packet must name exactly one repo boundary, one Issue, one target file, one route/audit target, one allowed write scope, and one validation path. If the required fix touches more than one file, L2 must return `DECOMPOSED_ONLY` or `FAST_BLOCKER` and defer extra files to later child Issues.
- `180s FAST_BLOCKER`: for timeout-recovery lanes, L2 must set a wall-clock cutoff at or before 180 seconds after assignment receipt. If validated completion plus cleanup proof is not already guaranteed before that cutoff, L2 must stop, run no further implementation steps, and return `FAST_BLOCKER`.
- `no-WIP cleanup`: before returning `FAST_BLOCKER`, `DRIFT_CLEANED`, or any timeout packet, L2/L3 must stop descendants, reject late `READY` or `PASS`, remove only task-owned uncommitted edits, and report target-file `git status` evidence. If no-WIP cleanup cannot be proven, the result is workflow drift, not PASS.
- `post-cutoff untracked drift`: any task-owned or target-adjacent untracked file found after the 270-second L2 hard stop or 300-second parent cutoff is hard workflow drift. L2 must stop further dispatch, remove or quarantine only authorized task-owned files, then prove cleanup with `git status --short -- <target>` and `test ! -e <expected-new-file>` before any retry; no post-cutoff untracked file may be adopted as `PASS`.
- `cleanup lane timeout`: if a cleanup lane misses its own cutoff, record it as new workflow drift in `BearsCLOUD/bears_plugin#26`; do not let that lane claim `CLEANED_NO_WIP` until a later bounded proof packet verifies the path state.

## First-minute parent gate

Immediately after assignment receipt, before route/audit, issue enrichment, Project field reads beyond the assigned item, environment/profile loading, local file reads beyond the fixed proof path below, execution planning, or L3 dispatch, L2 must answer the parent inside 60 seconds with exactly one of these packets:

- `FAST_BLOCKER`: no writes, no metadata mutation, no L3 dispatch. Use this when deterministic completion inside the parent wait gate is not already proven, or when the active L2 controller profile cannot launch L3 and cannot write or apply a preapproved patch-template.
- `READY`: deterministic proof that the child-only execution path can finish inside the parent wait gate, including the preexisting child Issue or approved issue template, exact repo/path boundary, route target, role target, write scope, validation path, authorized execution mechanism, closeout path, and remaining time budget.
- `WIP`: parent-visible metadata or decomposition progress only. It must name one current action, one smaller Issue/comment update if needed, no L3 spawn yet, no implementation WIP, and the cutoff for returning `READY`, `DECOMPOSED_ONLY`, or `FAST_BLOCKER`.

The first packet uses this fixed checklist in this hard order:

1. Read only the assigned Issue identifier, title, and body with one assigned-Issue read. If this cannot finish inside 15 seconds, return `FAST_BLOCKER`.
2. Verify only the named controller proof for `github-project-issues-product-app-l3-delegation-controller` in `assets/catalog/subagent-orchestration-policy.v1.json` with one 10-second grep/read command or one 40-line file slice around the controller entry: exact controller id, role `bears-github-project-issues-orchestrator`, and allowed child role `bears-product-app-zone-engineer`.
3. Return `FAST_BLOCKER`, `WIP`, or `READY` immediately. Do not run route/audit, spawn L3, plan execution, enrich GitHub Project fields, read broad local files, or load role/profile trees before this packet.

If the controller proof cannot be read and verified within that one command or one 40-line file slice, return `FAST_BLOCKER` immediately.

`READY` is forbidden until L2 has verified an actual authorized execution mechanism available in the active lane. For product-app L3 lanes, valid proof is only the named controller proof above. Other valid proof is only one of these:

- named L3 dispatch capability allowed by the active L2 role/profile for this lane; or
- concrete preapproved patch-template path for a one-file slice with exact write scope, validation, and rollback instructions.

A nominal `worker_path` string, planned worker name, assumed runner availability, environment load, or planned route/audit is not proof. The first-minute packet must name the exact capability proof checked, the source policy path or template path, and the action it authorizes. For product-app L3 lanes it must cite `assets/catalog/subagent-orchestration-policy.v1.json` and `github-project-issues-product-app-l3-delegation-controller`. A later `PASS`, `READY`, closeout, or `DRIFT` caused by missing worker authority after `READY` is workflow drift, not success.

For tiny child-only slices, L2 may dispatch L3 or use a patch-template only when the first-minute packet cites one of these precomputed paths:

- a precomputed child-Issue template that already defines repo, target files, role, allowed writes, validation, closeout fields, and the named L3 dispatch capability allowed by the active L2 role/profile; or
- a deterministic preapproved patch-template path for a one-file slice with exact validation and rollback instructions.

If neither authorized mechanism exists, L2 must return `FAST_BLOCKER` or decompose to a smaller child-only Issue instead of attempting implementation.

Before L3 dispatch, apply `EXECUTION_HOLD` when the first-minute packet lacks a proven progress path or the proof became stale after route/audit, metadata checks, or budget checks. An `EXECUTION_HOLD` lane may post one narrowing comment or metadata update and must return `METADATA_ONLY` or `FAST_BLOCKER`; it must not spawn L3, claim execution `PASS`, or mark the Issue complete.

Repeated first-minute gate misses after issue #17, issue #18, or issue #19 are active workflow drift. Before retrying the product child, open or fix a new drift issue in the owning repository and link the missed run evidence.

L2 allowed actions:

- read assigned Project items and linked Issues, sub-issues, PR metadata, Actions metadata, Releases, labels, milestones, blockers, and dependency notes;
- verify repo/path ownership through route/audit;
- classify each item by repo boundary, @Bears role, write scope, validation path, and blocker state;
- create or update Issues, sub-issues, links, labels, milestones, assignees, and Project fields only when the parent packet authorizes metadata mutation;
- split work into L3 `/goal` packets;
- spawn L3 workers with route-selected @Bears role names;
- spawn one role-improvement L3 worker when route/audit exposes role drift;
- integrate L3 closeout into Project and Issue state from evidence.

L2 forbidden actions:

- implementation file writes;
- shell implementation commands;
- commit, push, merge, or force push;
- deploy or runtime mutation;
- repository settings, branch protection, secret, variable, webhook, GitHub App, billing, or environment mutation;
- reading secrets, raw logs, raw chats, raw VPN configs, credentials, or production data.

## Decomposition and retry rules

- Parent talks to L2 only; L2 talks to L3 only.
- The first-minute parent gate is mandatory before all decomposition, route/audit, metadata enrichment, file reads, or L3 dispatch.
- Grouped L2 goals are allowed only for Project/Issue metadata batches, decomposition batches, closeout batches, or selecting exactly one dependency-ready implementation child for the current five-minute wave.
- L2 may self-select from an authorized GitHub Project query, but it must return a batch packet before the five-minute parent wait expires: `METADATA_BATCH`, `DECOMPOSED_ONLY`, `PARTIAL_DECOMPOSED_ONLY`, `CLOSEOUT_BATCH`, `ONE_CHILD_READY`, `FAST_BLOCKER`, or `DRIFT_CLEANED`.
- If self-selection finds implementation work, L2 must choose one dependency-ready child, execute only that child through the verified mechanism, and stop after a validated patch/gitflow-ready packet or blocker packet.
- Multi-child implementation batches are forbidden unless the parent packet names explicit precomputed child templates and a shorter per-child gate for each child.
- When decomposition is needed, L2 must create and link child Issues, add each child to the GitHub Project, and then return `DECOMPOSED_ONLY`.
- `DECOMPOSED_ONLY` means no L3 dispatch in the same five-minute wave.
- One decomposition wave may create at most two child Issues unless a precomputed child-Issue template has explicit operator approval.
- If more than two child Issues are needed, L2 creates the first two, records dependency/order links, sets only required status/linkage metadata, and returns `PARTIAL_DECOMPOSED_ONLY` before the five-minute parent wait expires.
- `PARTIAL_DECOMPOSED_ONLY` means remaining child Issues and optional Project field fills are deferred to later parent assignments; no L3 dispatch in that wave.
- During decomposition, postpone optional Project field fills and avoid broad Project field work in the same wave.
- Returning `DECOMPOSED_ONLY` or `PARTIAL_DECOMPOSED_ONLY` before timeout has priority over complete metadata cleanup.
- If required child metadata already exists before assignment, L2 may proceed child-by-child after verifying each child is visible and dependency-ready.
- For a tiny child-only slice, check named L3 dispatch capability allowed by the active L2 role/profile, precomputed child-Issue template, and deterministic preapproved patch-template availability within the first minute; if no authorized mechanism is confirmed, return `FAST_BLOCKER` immediately and do not start a slow implementation attempt.
- If named L3 dispatch capability is available in the active L2 role/profile, use it for the tiny child-only slice; do not wrap that launch in nested codex exec.
- If L3 dispatch is unavailable but the preapproved patch-template fallback is confirmed, use that one-file slice path; do not invent a new edit flow.
- If the active controller profile forbids direct L3 launch and also forbids writing or applying templates, return `FAST_BLOCKER`; do not return `READY` from a nominal `worker_path`.
- Before any L3 spawn, compare remaining budget against runner startup plus edit validation; if the budget cannot cover both, stop and return a blocker instead of starting L3.
- These decomposition limits do not widen metadata mutation authority; parent/operator authorization is still required.
- The first child execution is a separate parent assignment after the child Issue and Project metadata are visible.
- Do not combine decomposition and first L3 execution in one five-minute wave.
- After a tiny-slice timeout, retry only that child slice with a child-only packet; skip broad discovery.
- Keep issue #65's codex exec 60s timeout before edits and issue #59's parent >5min cleanup rule; these guardrails do not widen authority. If issue #65 timeout repeats after issue #16, treat it as repeated timeout drift and return `FAST_BLOCKER` instead of starting a slow implementation attempt.
- `RESET` and `CLEANUP` packets are terminal; do not continue or start L3 after either packet.
- When the parent sends timeout `RESET` or `CLEANUP`, L2 must stop waiting on L3 at once, ignore any late L3 `READY` or `PASS`, and return `DRIFT_CLEANED` within the cleanup wait.
- If L2 cannot return `DRIFT_CLEANED` within the cleanup wait, the parent records stronger workflow drift, links the active drift issue, and future grouped batches must split smaller than the missed batch before retry. Current drift issue: `BearsCLOUD/bears_plugin#24`.
- After timeout `RESET` or `CLEANUP`, post-timeout evidence must be comments only; do not change Project fields, issue state, or closeout state from late output.
- A timeout `READY` result is rejected; close uncommitted work and do not commit or push.
- Late `READY` or `PASS` after timeout `RESET` or `CLEANUP` is rejected, even if the child work finished.
- Parallel L2 fan-out is allowed only for dependency-ready disjoint scopes.
- Parent timeout after combined decomposition + execution is workflow drift, even when no files changed.
- If the same timeout, first-minute drift, or missing worker-authority drift repeats after issue #17, issue #18, or issue #19, open a new active drift issue, link it to the original evidence, and do not retry the product child until that drift is fixed.
- Regression example: `BearsCLOUD/apps#38` -> `#45` and `#46`; L2 started L3 `019f2437-d47a-7590-b8fe-37c02d7a49d5`; parent wait exceeded five minutes; the worker was interrupted; no files changed in `/srv/bears/dev/app/callsaver`.

## New-file implementation preflight

- Before any implementation L3 may create a new file, L2 must require a no-write preflight/plan packet naming the Issue, repo, exact new file path, route/audit evidence, owning role, validation command, and parent-visible WIP heartbeat text.
- The preflight must include exact new-file authorization from the Issue body, sub-issue, or parent packet. An implied target, inferred test name, or broad "add tests" request is not authorization to spawn an L3 that creates a file.
- L2 must send the WIP heartbeat to the parent before file creation starts; no child may write the new file while the preflight is missing.
- If the no-write preflight is not ready inside the first 60 seconds, L2 must return `FAST_BLOCKER`, then create or update a smaller Issue or issue comment with the missing proof instead of spawning write work.
- Timed-out L2 or L3 WIP must be stopped and removed before the parent cap; timed-out WIP is not `PASS`, `READY`, or closeout evidence.

## L2 execution loop

For each assigned Project item or Issue:

1. Read only the assigned item identifier, issue title/body, and the fixed named controller proof path required by the first-minute gate, then return `FAST_BLOCKER`, `WIP`, or `READY` to the parent inside 60 seconds.
2. If `WIP` was returned, continue only the named metadata/decomposition action and return `READY`, `DECOMPOSED_ONLY`, or `FAST_BLOCKER` before the declared cutoff; do not spawn L3 from `WIP`.
3. If `READY` was returned, load only the ready plan/analysis packet, current Project item, linked Issue, sub-issues, linked PRs, Actions/check metadata, and existing field values required by that pass proof; if the named capability proof is later absent or unauthorized, stop and report workflow drift.
4. Identify the canonical owner repo, local path, target paths, issue type, acceptance criteria, and blocker notes.
5. Run route/audit for the target path.
6. If route/audit returns `ROLE_COVERAGE_BLOCKER`, create a role-improvement L3 packet and keep the implementation item blocked.
7. Split work when repo boundary, @Bears role, write scope, validation path, or deploy/runtime boundary differs.
8. If decomposition is needed, create and link at most two child Issues per wave, add only required Project status/linkage metadata, and return `DECOMPOSED_ONLY` or `PARTIAL_DECOMPOSED_ONLY`; do not dispatch L3 in the same wave.
9. Build one L3 packet per split only after the child metadata is visible, dependency-ready, and either preexisted or came from a prior parent assignment.
10. Validate every materialized L3 packet only through local-commit-owned or operator-approved `python3 scripts/github_project_subagents.py validate-assignment <packet.json>` evidence.
11. Dispatch L3 workers or use the patch-template only when the first-minute proof remains true after route/audit and required metadata checks, including the exact authorized execution mechanism named in the first-minute packet.
12. Collect L3 closeout packets.
13. Update Project/Issue state only from L3 evidence, validation proof, commit SHA, PR metadata, Release metadata, or blocker proof.
14. Request gitflow closeout when files changed.
15. Report item status to the parent.

## L3 worker lane

- Use the exact @Bears role returned by route/audit.
- Use `model=gpt-5.4-mini` and `reasoning=high`.
- One L3 assignment covers one issue or Project item slice, one repo boundary, one allowed write scope, and one validation path.
- L3 must return changed files, validation evidence, blockers, issue/project item ids, requested Project field updates, and forbidden surfaces untouched.
- L3 must not directly mutate Project fields unless the L2 packet explicitly asks for a closeout comment or metadata update.

## L3 assignment packet

```text
/goal
lane=l3
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
github_project_item=<item id/url>
github_issue=<owner/repo#number>
repo=<local path and owner/repo>
target=<exact files/paths>
route_audit_evidence=<route/audit command result or packet id>
metadata_mutation_authorized=<true|false>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<issue checklist or Project item requirement>
validation=<exact commands or metadata checks>
completion_criteria=<closeout proof required by L2>
closeout_updates=<Project fields and Issue comment requested from L2>
```

## Done rule

L2 may mark the work done only when the closeout packet contains:

- L3 result for every split;
- validation PASS or explicit blocker issue;
- commit SHA and push proof when files changed;
- linked PR, Release, or deployment metadata when required by the item;
- Issue closeout comment text;
- Project/Issue state updates derived from evidence.

## GitHub surface coverage

Before L3 dispatch, L2 must inspect and reconcile only the metadata needed for the assigned item:

- Project item ids, linked content ids, field values, status, and blockers;
- Issues, issue types, sub-issues, labels, milestones, assignees, linked branches, linked PRs, and dependencies;
- Pull requests, review state, mergeability metadata, check suite status, and linked issues;
- Actions status metadata without raw log reads;
- Releases, tags, packages, and deployment notes when delivery is in scope;
- Discussions only when the work needs a non-actionable decision record;
- Wiki and Pages metadata only for public knowledge or docs pointers;
- Code scanning, secret scanning alert metadata, Dependabot alerts, and security advisories only through a security-review route;
- Deployments and Environments metadata only for planning; runtime or environment mutation requires the exact deploy route;
- Repository collaboration metadata, including branches, commits, compare output, CODEOWNERS, repository topics, rules metadata, and teams metadata, as read-only planning evidence.

## Required gates

Agent-local route gates before L2 or L3 dispatch:

```bash
python3 scripts/platform_roles.py route <target-path>
python3 scripts/platform_roles.py audit <target-path>
```

CI/local-commit-owned or operator-approved validator before closeout after changes to this skill, the GitHub orchestrator role, or the GitHub Project subagent catalog:

```bash
python3 scripts/github_project_subagents.py validate  # local-commit-owned
```

CI/local-commit-owned or operator-approved assignment-packet validator before L2 or L3 dispatch when packet files are materialized:

```bash
python3 scripts/github_project_subagents.py validate-assignment <packet.json>  # local-commit-owned
```

See `references/github-project-issue-flow.md` and `../../docs/reference/github-project-subagents.md` for the exact orchestration sequence and surface matrix.
