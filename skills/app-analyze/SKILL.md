---
name: app-analyze
description: "Analyze app workflow artifacts for drift before app-dev: App Target Gate, constitution, research, specification, GitHub Project plan, Issues, lanes, roles, proof requirements, dependencies, and handoff."
---

# App Analyze

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked Issues and metadata fields. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

## App Target Gate

Every app-* skill starts with this gate:

- Name one exact app directory or app docs path.
- Classify each target as exactly one layer: `app`, `platform`, or `infra`.
- `app` layer belongs to `BearsCLOUD/apps` and one app directory under `/srv/bears/dev/app`.
- `platform` layer belongs to `/srv/bears/dev/platform`.
- `infra` layer belongs to `/srv/bears/kubernetes`.
- Legacy child repos and `/srv/bears/projects` are evidence only.
- Broad workspace scans are forbidden when target packets name paths.
- If a request crosses layers, keep the layers separate and pass them to `$app-plan` as separate lanes.

Use this skill to prove an app plan is internally consistent before `$app-dev` starts.

Analysis means a current-state check across artifacts. It does not fix files unless the operator asks for fixes after the report.

## Boundary

Allowed:

- Read nearest `AGENTS.md`, app constitution, app-research packet, spec, docs, `app-plan.project-task-packet`, GitHub Project/Issue metadata, route evidence, and closeout rules.
- Report contradictions, gaps, stale references, dependency mistakes, role mismatches, proof gaps, and execution blockers.
- Recommend exact artifact fixes or Project/Issue updates.

Forbidden:

- Implementation edits.
- Runtime, Kubernetes desired-state, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Broad workspace scans when packet targets are known.
- Calling a risk a blocker unless access, permission, missing route coverage, explicit stop, or required owner proof prevents safe execution.

## Workflow

1. Run the App Target Gate against every target in the packet.
2. Verify artifact chain: constitution, risk-gated research, spec, docs, Project items, Issues, lane map, dependencies, route-selected roles, proof requirements, and `$app-dev` handoff.
3. Verify cross-layer work is split into `app`, `platform`, and `infra` lanes before execution.
4. Verify optional sub-lanes are disjoint and have explicit dependencies.
5. Verify every task has one repo boundary, one target set, one owning role, one lane, and one proof requirement.
6. Classify each finding as `blocker`, `fix_required`, `advisory`, or `pass`.
7. Emit `app-analysis.packet`.
8. Execution may start only when status is `pass`, or when the operator explicitly approves scoped execution with listed advisory items.

## Packet

```json
{
  "schema": "app-analysis.packet",
  "version": "1",
  "status": "pass|review|fail|blocked",
  "target": "<target/repo/path>",
  "app_directory": "<app directory or none>",
  "artifacts_checked": ["<paths or urls>"],
  "target_gate": "pass|fail|blocked",
  "lane_map": "pass|fail|blocked",
  "requirements_coverage": [
    {"id": "<requirement id>", "status": "covered|missing|contradicted", "evidence": "<path/url>"}
  ],
  "findings": [
    {"severity": "blocker|fix_required|advisory", "artifact": "<path/url>", "issue": "<concrete issue>", "fix": "<exact fix>"}
  ],
  "route_roles": [
    {"target": "<path>", "role": "<@Bears role>", "status": "matched|missing"}
  ],
  "execution_handoff": "ready|needs-fix|blocked",
  "execution_skill": "app-dev",
  "recommendation": "<next action>"
}
```

Use `fail` when artifacts contradict each other or coverage is missing. Use `blocked` only for access, permission, missing required route coverage, explicit operator stop, or missing owner proof.
