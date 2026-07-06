---
name: app-functional-graph
description: "Create, update, and consume app-local functional graph and app task ledger files for Bears apps under /srv/bears/dev/app/*. Use when app-plan creates ledger tasks, when app-dev consumes task scope before L3 dispatch, or when a task must link to functionality refs, graph node refs, async cycles, API calls, state transitions, Project item refs, notification refs, and execution evidence."
---

# App Functional Graph

`functional graph` means the app-local JSON execution map that links app functionality to nodes, edges, async cycles, API calls, state transitions, and evidence. `app task ledger` means the app-local JSON task source for `$app-dev` execution.

## App Target Gate

Run the shared app-* target gate first.

- Use this skill for `target_layer=app` under `/srv/bears/dev/app/<app>`.
- Keep graph and ledger files inside the app directory.
- Use `target_layer=platform`, `infra`, or `plugin` only as a referenced dependency; do not store their execution tasks in an app ledger.

## Files

- Functional graph: `docs/app-functional-graph.v1.json`.
- Task ledger: `docs/app-task-ledger.v1.json`.

## Modes

### Initialize

Create both files when the app has no graph or ledger yet:

```bash
python3 /srv/bears/plugins/bears/scripts/app_functional_graph.py init --app-dir /srv/bears/dev/app/<app>
```

### Plan mode

Use with `$app-plan` before execution task creation.

1. Read app specification, research, nearest `AGENTS.md`, and existing graph and ledger.
2. Create or update one functionality for each executable product behavior.
3. Create ledger tasks with `task_id`, `functionality_refs`, `graph_node_refs`, lane, role, paths, dependencies, `autoci_zones`, `expected_statuses`, Project refs, and evidence fields.
4. Link GitHub Project items through `project_refs` only.
5. Create GitHub Issues only after explicit manual notification authorization; store those URLs in `notification_refs` with a reason.

Hard rule: an execution task with `status=ready`, `in_progress`, `done`, `blocked`, or `needs-review` must have `functionality_refs`, `graph_node_refs`, `autoci_zones`, and `expected_statuses`.

### Dev mode

Use with `$app-dev` before L3 dispatch and after L3 closeout.

1. Consume existing graph and ledger validity evidence.
2. Dispatch only ledger tasks with `status=ready` and valid refs.
3. Pass `task_id`, `functionality_refs`, `graph_node_refs`, `allowed_paths`, `autoci_zones`, `expected_statuses`, and `task_ledger` to L3.
4. Keep L3 edits inside task paths and graph node scope.
5. L3 records claim and closeout status in the ledger through assigned task commands, including commit, status evidence, and proof refs.

Hard rule: no valid ledger task with computed autoCI zones means no L3 dispatch.
Forbidden: manually run graph or ledger validators unless the task packet or operator names the exact command.

## GitHub surfaces

- GitHub Project is a planning/status view over `task_id` and `functionality_ref`.
- GitHub Issues are notification records for blocker, incident, bug, or operator question.
- GitHub Issues are not execution task identity and are not dispatch input.

## Command surface

Use `/srv/bears/plugins/bears/scripts/app_functional_graph.py` only as an assigned app-plan/app-dev operation, exact operator-named command, or local-commit-owned automation.

- `init`: creates graph and ledger files for a registered app directory.
- `validate`: checks graph and ledger JSON, ids, references, API caller nodes, async cycle nodes, and notification refs.
- `summary`: emits graph and ledger counts for status reporting.
- `create-task`: creates a ledger task with functionality refs, graph-node refs, autoCI zones, and expected statuses.
- `claim-task`: lets the assigned L3 worker mark one ready task `in_progress`.
- `mark-task-status`: lets the assigned L3 worker mark one task `done`, `blocked`, or `needs-review` with commit, evidence, and status evidence refs.
- `close-task`: legacy closeout command for commit and evidence refs.
- `link-project-item`: stores GitHub Project metadata refs.
- `record-notification`: stores GitHub Issue notification refs with an allowed reason.

The script is a helper. Its `validate` mode is not agent PASS evidence; it belongs to exact task packets, exact operator commands, or automatic CI/local commit validation.

## Output rules

- Store ids, paths, refs, status, worker id, worker role, timestamps, commit ids, autoCI zones, status names, and evidence refs only.
- Do not store secret values, env values, tokens, raw logs, raw chats, provider payloads, or production data.
- Use positive action wording: target, owner, action path, evidence, and handoff.
