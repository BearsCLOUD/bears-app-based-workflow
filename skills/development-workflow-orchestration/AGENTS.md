# Development Workflow Orchestration Router

- Scope: broad Bears development workflow packets, domain orchestration profiles, validators, fixtures, and workflow map links only.
- Parent plugin map: `/srv/bears/plugins/bears/AGENTS.md#functional-map`.
- Owned daemon surfaces: `scripts/orchestrator_issue_daemon.py`, `scripts/orchestrator_issue_daemon_eligibility.py`, `assets/catalog/orchestrator-issue-daemon.v1.json`, `docs/reference/orchestrator-issue-daemon.md`, and `docs/runbooks/orchestrator-issue-daemon-*`.
- Owned Codex exec coordination surfaces: `scripts/goal_orchestrator.py`, `scripts/issue_autostart.py`, `scripts/sequential_codex_exec.py`, `assets/catalog/codex-exec-*.v1.json`, and `docs/reference/sequential-codex-exec.md`.
- Parent agent remains orchestration-only and must not implement broad work directly.
- Domain orchestrators coordinate one domain only and must use smart reusable worker selection before worker spawn.
- Subagent prompt packets must start with `/goal` on the first line and must include explicit completion criteria.
- Reviewers are read-only unless a separate implementation-fix role is assigned.
- Merge decisions require `REVIEW_PASS`, unchanged head evidence, exact route/audit, and validation evidence.
- Deployment planning must route Bears software to Kubernetes desired state plus `local_cd` only; local/manual deploy instructions are forbidden.
- Forbidden: product behavior changes, runtime mutation, provider mutation, kubernetes_deployment mutation, local_cd mutation, secrets, raw logs, raw chat, raw VPN configs, credential material, and production data.
- Validate with `python3 scripts/development_workflow_validate.py validate`.
