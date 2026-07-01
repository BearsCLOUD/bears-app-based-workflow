# Role Gate Methodology

Bears plugin owns the universal role gate for platform, product, runtime, deploy, migration, and integration writes.

## Main rule

The orchestrator MUST stop with `ROLE_COVERAGE_BLOCKER` unless the requested concrete part has exactly one valid primary specialist or helper role at the same granularity as the requested write scope.

## Canonical methodology

1. **Concrete part** — define the concrete part as the smallest explicit plugin-owned surface that fully contains the requested write scope through exact aliases or declared write roots.
2. **Valid primary role** — require a plugin-owned TOML artifact with `role_kind=specialist` or `role_kind=helper`, `primary_eligible=true`, bounded write scope, trust boundary, validations, model, reasoning effort, sandbox mode, and developer instructions.
3. **Parent/project-group role is insufficient** — parent, group, controller, or umbrella coverage is classification-only and cannot authorize a narrower child or mixed-scope write.
4. **Broad role is invalid** — if a role is broad, mixed-scope, controller/reviewer-only, or reachable only through parent/group matching, return `invalid_broad_role` and require decomposition.
5. **Choose exactly one primary role** — resolve candidates from exact aliases and declared write roots only, prefer the longest exact concrete match, reject group-only matches, and return `ambiguous_owner` on ties.
6. **Add supporting/security/QA roles only after primary selection** — supporting roles are reviewer-only sidecars for explicit risk flags and can never replace the primary role.
7. **Emit the exact blocker packet** — use the exact `ROLE_COVERAGE_BLOCKER` packet when coverage is unknown, unmapped, parent-only, missing, broad, or ambiguous.
8. **Run mandatory validators/tests** — prove one-primary-role routing, blocker behavior, reviewer-only attachments, and implementation-handoff blocking before edits continue.
9. **Keep forward tests fail-closed** — child-under-group, alias/path drift, catalog growth, and broad fallback regressions must keep blocking.
10. **Record independent control audit evidence** — preserve the audit command, blocker proofs, validation results, and confirmation that no product/runtime/deploy edits happened before coverage closed.
11. **Run source freshness preflight** — before blocker closeout, record current plugin checkout SHA, root gitlink SHA, and root origin/main plugin gitlink SHA.

## Concrete part

A concrete part is the smallest explicit service, path, workflow, runtime contract, role-governance surface, or integration area that fully contains the requested write scope and has an exact plugin-owned catalog mapping.

Parent/project-group coverage is classification only. It cannot authorize child implementation because it is broader than the requested write scope.

## Valid primary role

A valid primary role is plugin-owned, has a TOML artifact, is `role_kind=specialist`, is `primary_eligible=true`, and defines bounded scope, write boundary, trust boundary, validations, model, reasoning effort, sandbox mode, and developer instructions.

Reviewer/security/QA roles can attach after the primary role is selected. They do not replace it.

## Allowed before coverage

Only role TOML/artifact creation or refinement, exact catalog mapping, governance docs, validators/tests, and forward-test evidence are allowed.

Product code, platform implementation, runtime, deploy, migration, and integration behavior edits remain forbidden.

## Blocker packet

Use the exact packet defined in `assets/catalog/role-gate-methodology.v1.json` and emitted by `scripts/platform_roles.py route <target>`.

```yaml
status: ROLE_COVERAGE_BLOCKER
missing_part: <path/service/area>
why_blocked: <unknown|unmapped|parent_only|missing_role|invalid_broad_role|ambiguous_owner>
evidence_checked:
  - <catalog/docs/agents paths>
blocked_edits:
  - product implementation
  - platform implementation
  - runtime/deploy/migration/integration edits
allowed_next_actions:
  - create/refine primary role artifact
  - add exact catalog mapping
  - add/update validators
  - add forward-test evidence
required_role_shape:
  name: <specialist-role-name>
  concrete_scope: <exact part>
  allowed_write_boundary: <paths/surfaces>
  trust_boundary: <data/secrets/external/prod impact>
  required_validations:
    - <checks>
decomposition_required: true|false
```

`governance docs` remain allowed before coverage closes, but the blocker packet keeps `allowed_next_actions` minimal and exact for machine checks.

## Source freshness preflight

Before reporting `ROLE_COVERAGE_BLOCKER`, record:

- `current_plugin_checkout_sha`
- `root_gitlink_sha`
- `root_origin_main_plugin_gitlink_sha`

If the requested mapping exists only in newer merged plugin state, report:

```yaml
status: STALE_ROLE_GATE_SOURCE
requested_target: <path/service/area>
current_plugin_checkout_sha: <sha>
root_gitlink_sha: <sha>
root_origin_main_plugin_gitlink_sha: <sha>
requested_mapping_exists_in_newer_merged_plugin_state: true
safe_next_action: sync plugin checkout | switch to a clean root-sync worktree
exact_role_policy: Exact-role policy remains active; generic role substitution is forbidden.
```

Do not authorize generic role substitution.

## Validation

Local commit validation owns these checks:

- `python3 scripts/role_gate_methodology.py validate`; manual execution requires operator approval.
- `python3 scripts/platform_roles.py validate`; manual execution requires operator approval.
- `python3 -m unittest tests/test_role_gate_methodology.py tests/test_platform_roles.py`; manual execution requires operator approval.

Independent audit is complete only when the control reviewer confirms every criterion listed in `independent_control_audit.must_confirm` and the evidence document named by `control_audit_evidence.required_document` is current for the implementation slice.
