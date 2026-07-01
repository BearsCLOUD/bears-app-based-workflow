# Role Gate Control Audit Evidence - 2026-06-03

## Scope

This evidence packet covers only the plugin-governance implementation slice under `/srv/bears/plugins/bears`.

## Independent worker

Independent control audit worker:

- worker id: `019e8e1c-3871-7843-9ce4-c0246ab0401e`
- role: `bears-platform-role-governor`
- write policy: read-only audit, no file edits requested

## Implementation-slice boundaries

Allowed writes in this slice:

- role TOML/artifact creation or refinement inside `/srv/bears/plugins/bears/agents/`
- exact role catalog mappings inside `/srv/bears/plugins/bears/assets/catalog/`
- governance docs inside `/srv/bears/plugins/bears/docs/`, `AGENTS.md`, `README.md`, `SPEC.md`, and `requirements.md`
- validators and tests inside `/srv/bears/plugins/bears/scripts/` and `/srv/bears/plugins/bears/tests/`
- workflow-governance metadata inside `/srv/bears/plugins/bears/workflows/`

Forbidden writes in this slice:

- product code edits
- platform implementation edits outside the plugin governance boundary
- runtime edits
- deploy execution or production mutation
- migration edits
- integration behavior edits
- secrets or production data access

## Canonical methodology checkpoints

1. Concrete part is explicit and exact for the requested write boundary.
2. The selected primary role is a valid plugin-owned specialist role.
3. Parent/project-group coverage is treated as classification-only.
4. Broad/controller/reviewer roles are rejected for primary ownership and require decomposition.
5. Exactly one primary role remains after exact-alias and write-root matching.
6. Supporting/security/QA roles are reviewer-only sidecars added only after primary selection.
7. The emitted blocker packet keeps the exact machine-checked shape.
8. Deterministic validators/tests run before implementation handoff.
9. Forward tests prove new child/group drift cannot silently widen coverage.
10. This packet records that no product/runtime/deploy edits happened before role coverage closed.

## Role coverage before implementation handoff

The role-gate methodology itself routes to exactly one primary specialist role:

```bash
python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/role-gate-methodology.v1.json
```

Expected result:

- `status: matched`
- `concrete_part: role_gate_methodology`
- `primary_role: bears-platform-role-governor`
- `implementation_handoff_allowed: true`
- `independent_control_audit.auditor_role: bears-platform-role-governor`

The session-worker runtime routes to exactly one primary specialist role:

```bash
python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/session-workers-runtime.v1.json
```

Expected result:

- `status: matched`
- `concrete_part: session_workers_runtime`
- `primary_role: bears-session-worker-runtime-engineer`

The deploy core workflow artifact routes to exactly one primary specialist role:

```bash
python3 scripts/platform_roles.py route /srv/bears/plugins/bears/workflows/auth-gateway-deploy-core/workflow.yml
```

Expected result:

- `status: matched`
- `concrete_part: auth_gateway_deploy_core`
- `primary_role: bears-deploy-platform-engineer`

## Negative controls

Parent/group-only coverage must block:

```bash
python3 scripts/platform_roles.py route /srv/bears/projects/seller/apps
python3 scripts/platform_roles.py route /srv/bears/plugins/bears
```

Both must return:

- `status: ROLE_COVERAGE_BLOCKER`
- `why_blocked: parent_only`

Alias/path drift must not widen coverage:

```bash
python3 scripts/platform_roles.py route /srv/bears/plugins/bears-shadow
```

Expected result:

- `status: ROLE_COVERAGE_BLOCKER`
- `why_blocked: unmapped`

Unknown concrete part must block:

```bash
python3 scripts/platform_roles.py route totally-unknown-platform-surface
```

Expected result:

- `status: ROLE_COVERAGE_BLOCKER`
- `why_blocked: unknown`

Broad/plugin-root scope must decompose before implementation:

```bash
python3 scripts/platform_roles.py route /srv/bears/plugins/bears
```

Expected result:

- `status: ROLE_COVERAGE_BLOCKER`
- `why_blocked: parent_only`
- `decomposition_required: true`

## Historical validation evidence

The command block below is a 2026-06-03 evidence record. It is not a current local run instruction. Current local agents may run only the checks allowed by the active operator packet and repo policy.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/role_gate_methodology.py validate
PYTHONDONTWRITEBYTECODE=1 python3 scripts/platform_roles.py validate
PYTHONDONTWRITEBYTECODE=1 python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/role-gate-methodology.v1.json
# historical unittest evidence only; do not run locally without operator approval
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_role_gate_methodology.py tests/test_platform_roles.py
# historical unittest evidence only; do not run locally without operator approval
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Historical implementation-slice result:

- deterministic validators for role-gate methodology and platform-role catalog passed
- `platform_roles.py audit ...role-gate-methodology.v1.json`: matched, handoff allowed
- targeted `unittest`: pass
- historical full `python3 -m unittest discover -s tests` evidence: pass (`Ran 92 tests`, `OK`)

## Product/runtime/deploy edit check

This evidence packet does not claim the entire workspace is clean. The workspace has pre-existing unrelated dirty files outside `/srv/bears/plugins/bears`.

For this implementation slice, the changed files under `/srv/bears/plugins/bears` are governance-only plugin artifacts: role catalog, methodology catalog, session worker runtime catalog, validators, tests, docs, skills, agent TOMLs, schemas, and workflow metadata.

No product code, production runtime, deploy execution, migration, integration behavior, secrets, or production data edits were part of this plugin-governance slice.
