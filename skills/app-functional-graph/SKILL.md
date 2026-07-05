---
name: app-functional-graph
description: "Create, update, validate, and consume app-local functional graph and app task ledger files for Bears apps under /srv/bears/dev/app/*. Use when app-plan creates ledger tasks, when app-dev validates task scope before L3 dispatch, or when a task must link to functionality refs, graph node refs, async cycles, API calls, state transitions, Project item refs, notification refs, and execution evidence."
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
3. Create ledger tasks with `task_id`, `functionality_refs`, `graph_node_refs`, lane, role, paths, dependencies, Project refs, and evidence fields.
4. Link GitHub Project items through `project_refs` only.
5. Create GitHub Issues only after explicit manual notification authorization; store those URLs in `notification_refs` with a reason.

Hard rule: an execution task with `status=ready`, `in_progress`, or `done` must have `functionality_refs` and `graph_node_refs`.

### Dev mode

Use with `$app-dev` before L3 dispatch and after L3 closeout.

1. Validate graph and ledger.
2. Dispatch only ledger tasks with `status=ready` and valid refs.
3. Pass `task_id`, `functionality_refs`, `graph_node_refs`, `allowed_paths`, and `task_ledger` to L3.
4. Keep L3 edits inside task paths and graph node scope.
5. Record commit, evidence, and critic result in the ledger after closeout.

Hard rule: no valid ledger task means no L3 dispatch.

## GitHub surfaces

- GitHub Project is a planning/status view over `task_id` and `functionality_ref`.
- GitHub Issues are notification records for blocker, incident, bug, or operator question.
- GitHub Issues are not execution task identity and are not dispatch input.

## Command surface

Use `/srv/bears/plugins/bears/scripts/app_functional_graph.py` only as an assigned app-plan/app-dev operation or as local-commit-owned automation.

- `init`: creates graph and ledger files for a registered app directory.
- `validate`: checks graph and ledger JSON, ids, references, API caller nodes, async cycle nodes, and notification refs.
- `summary`: emits graph and ledger counts for status reporting.
- `create-task`: creates a ledger task with functionality and graph-node refs.
- `close-task`: records task closeout commit and evidence refs.
- `link-project-item`: stores GitHub Project metadata refs.
- `record-notification`: stores GitHub Issue notification refs with an allowed reason.

The script is an executable validator/helper. It becomes `autoCI` only when a test-selection, hook, workflow, or GitHub check invokes it automatically.

## Output rules

- Store ids, paths, refs, status, commit ids, and evidence refs only.
- Do not store secret values, env values, tokens, raw logs, raw chats, provider payloads, or production data.
- Use positive action wording: target, owner, action path, evidence, and handoff.
