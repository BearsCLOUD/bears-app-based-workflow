# Graph Workflow v4 implementation wave

- Repository: `BearsCLOUD/bears-app-based-workflow`
- Run: `RUN-GRAPH-WORKFLOW-V4-001`
- Tasks: `TASK-GRAPH-PROCESS-004`, `TASK-SENTRY-GATEWAY-004`, `TASK-RELEASE-004`
- Historical journal: `docs/app-process-events/v1` is read-only.
- Native journal: new records use `app-process-event.v2` under `docs/app-process-events/v2`.
- Acceptance: plugin CI is absent; `automation_status=not_run`.
- Sentry: live trace evidence is `needs-evidence` until operator bootstrap and the first real actionable autoCD failure. No synthetic live error is authorized.
