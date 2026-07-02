---
name: bears-workflow-validate
description: "Use after Bears workflow-overlay skill, README, schema-packet, or workflow edits to validate boundaries; emits workflow-validation JSON and short diagnostics."
---

# Bears Workflow Validate

Use this skill after Bears workflow-overlay edits to validate skill structure, source boundaries, JSON governance packets, and workflow references.

This skill is report-first. It does not add app connector, MCP, production deploy, or runtime behavior.

## Workflow

1. List skill directories and confirm no upstream Spec Kit core skill directories remain inside the plugin overlay.
2. Require local-commit-owned or operator-approved Codex skill-validator evidence for changed skill folders.
3. Require local-commit-owned or operator-approved schema-validation evidence for known governance packets when artifacts are present.
4. For auth/gateway/deploy workflow changes, cite local-commit-owned `scripts/auth_gateway_deploy_readiness.py validate`; manual execution requires operator approval.
5. For subagent closeout or non-product workflow changes, cite local-commit-owned `scripts/subagent_orchestration_policy.py validate`; manual execution requires operator approval.
6. For target artifact or registry-gate changes, cite local-commit-owned `scripts/project_registry_gate.py validate-registry`; manual execution requires operator approval.
7. For Spec Kit-gated feature dirs, validate that `spec.md`, `plan.md`, and `tasks.md` exist, that `tasks.md` links to `role-coverage.json`, and that restricted mutation text has operator approval evidence.
8. For platform-role, dev-core, Kubernetes, Android emulator, Sentry/observability, or The Ants routing changes, run route/audit checks for the changed targets and cite local-commit-owned validation.
9. Check workflow or README references for old plugin names, invalid command names, broadened scope, deprecated projects parent authority, or source-boundary drift.
10. Confirm standalone `bears-speckit` plugin or layer claims stay deprecated; `speckit-bears-flow` must remain an `@bears` workflow skill that calls upstream Spec Kit skills from `/srv/bears/.agents/skills`.
11. Confirm stage-boundary audits replace per-file non-product audits.
12. Emit JSON first using the `bears-workflow-overlay.workflow-validation` shape below.
13. Optionally add a short Markdown diagnostics summary after the JSON.

## Agent-local checks

Run only bounded inspection checks that match the changed files and allowed scope:

```bash
find /srv/bears/plugins/bears/skills -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
find /srv/bears/plugins/bears/skills -mindepth 1 -maxdepth 1 -type d -name 'speckit-*' ! -name 'speckit-bears-*' -printf '%f\n' | sort
grep -RIn 'bears-''speckit' /srv/bears/plugins/bears/README.md /srv/bears/plugins/bears/skills || true
grep -RInE 'standalone .*bears-speckit|bears-speckit .*plugin|bears-speckit .*layer' /srv/bears/plugins/bears/README.md /srv/bears/plugins/bears/SPEC.md /srv/bears/plugins/bears/requirements.md /srv/bears/plugins/bears/skills /srv/bears/plugins/bears/assets/catalog || true
```

Agents may run exact `platform_roles.py route <changed-target>` and `platform_roles.py audit <changed-target>` checks for changed targets only.

## Local-commit-owned checks

- Local commit validation owns `python3 scripts/auth_gateway_deploy_readiness.py validate`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/platform_roles.py validate`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/role_gate_methodology.py validate`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/session_workers_runtime.py validate`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/subagent_orchestration_policy.py validate`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/project_registry_gate.py validate-registry`; manual execution requires operator approval.
- Local commit validation owns `python3 /home/ai1/.codex/skills/.system/skill-creator/scripts/quick_validate.py <changed-skill-dir>`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills --feature-dir /srv/bears/specs/005-telegram-workflow-plugin --require-artifacts`; manual execution requires operator approval.
- Local commit validation owns `python3 -m unittest discover -s tests`; manual execution requires operator approval.

## JSON artifact

Emit this JSON artifact first:

```json
{
  "schema": "bears-workflow-overlay.workflow-validation",
  "version": "1",
  "status": "pass",
  "validator": "bears-workflow-validate",
  "targets": [
    "/srv/bears/plugins/bears/skills",
    "/srv/bears/plugins/bears/README.md"
  ],
  "checks": [
    {
      "id": "skill-boundary",
      "status": "pass",
      "evidence": "No upstream speckit-* skill directories remain except speckit-bears-* overlays."
    },
    {
      "id": "bears-speckit-boundary",
      "status": "pass",
      "evidence": "Standalone bears-speckit plugin/layer claims are deprecated; speckit-bears-flow remains an @bears workflow skill."
    },
    {
      "id": "skill-frontmatter",
      "status": "pass",
      "evidence": "Changed SKILL.md files have local-commit-owned or operator-approved quick_validate.py evidence."
    }
  ],
  "recommendation": "Accept the overlay edit if all checks pass."
}
```

Allowed `status` values for this packet are `pass`, `fail`, and `review`. Use `review` when validation is advisory or incomplete.

## Report rules

- Put the JSON packet before prose.
- Include command names and exit codes when reporting validation to the operator. Do not include raw logs.
- Do not treat `validate_plugin.py` success as proof that runtime discovery has no duplicate upstream Spec Kit skills.
- Do not mutate manifests, app definitions, connectors, MCP servers, secrets, `.env` files, production data, or raw VPN configs.
