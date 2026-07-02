---
name: bears-project-analyze
description: "Analyze Bears target artifacts for drift before execution: constitution, specification, documentation, GitHub Project plan, Issues, route/audit roles, validation, dependencies, and projectdevsubagents handoff. Use as the Bears-native analogue to speckit-analyze before plan execution or after material target docs change."
---

## Entity terms

`app` means a Bears product application source directory under `/srv/bears/dev/app` or `BearsCLOUD/apps`. `project` means a GitHub Project planning board with linked Issues and metadata fields. Use `target`, `registered target`, `repo`, `path`, `workspace surface`, or `app directory` for filesystem/source ownership.

# Bears Target Analyze

Use this skill to prove a Bears target plan is internally consistent before implementation or `$projectdevsubagents` execution starts.

Analysis means a current-state check across artifacts. It does not fix files unless the operator asks for fixes after the report.

## Boundary

Allowed:

- Read nearest `AGENTS.md`, constitution, spec, docs, GitHub Project plan packet, Project/Issue metadata, route/audit output, validation policy, and closeout rules.
- Report contradictions, gaps, stale references, dependency mistakes, role mismatches, validation gaps, and execution blockers.
- Recommend exact artifact fixes or Project/Issue updates.

Forbidden:

- Implementation edits.
- Runtime, deploy, Kubernetes, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Broad workspace scans when packet targets are known.
- Calling a risk a blocker unless access, permission, missing route coverage, explicit stop, or required owner proof prevents safe execution.

## Workflow

1. Read `/srv/bears/AGENTS.md`, nearest target `AGENTS.md`, and the artifacts named by the packets.
2. Verify artifact chain:
   - constitution exists or explicit approved gap;
   - spec references constitution rules and has acceptance criteria;
   - docs changed match the spec;
   - GitHub Project plan items cover every requirement;
   - Issue dependencies match the plan order;
   - each planned target has route/audit evidence and one exact @Bears role;
   - each item has validation and closeout evidence requirements;
   - `$projectdevsubagents` can consume the plan without parent implementation.
3. Classify every finding:
   - `blocker`: execution cannot start safely;
   - `fix_required`: artifact must be corrected before execution;
   - `advisory`: safe to execute but should be tracked;
   - `pass`: verified.
4. Produce a requirements coverage table, artifact drift table, role/route table, validation table, dependency table, and execution handoff verdict.
5. Emit a `bears-project.analysis-packet`.
6. Execution may start only when status is `pass`, or when the operator explicitly approves a scoped execution with listed `advisory` items.

## Analysis packet

```json
{
  "schema": "bears-project.analysis-packet",
  "version": "1",
  "status": "pass|review|fail|blocked",
  "target": "<target/repo/path>",
  "artifacts_checked": ["<paths or urls>"],
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
  "execution_skill": "projectdevsubagents",
  "recommendation": "<next action>"
}
```

Use `fail` when artifacts contradict each other or coverage is missing. Use `blocked` only for access, permission, missing required route coverage, explicit operator stop, or missing owner proof.
