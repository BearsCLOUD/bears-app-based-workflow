# Missing role blocker

Return `ROLE_COVERAGE_BLOCKER` unless the requested concrete part has exactly one valid primary specialist or helper role at the same granularity as the requested write scope.

## Definitions

- **Concrete part** — the smallest explicit cataloged surface that contains the requested write scope through an exact alias or declared write root.
- **Valid primary role** — a catalog role with `role_kind=specialist` or `role_kind=helper`, `primary_eligible=true`, an existing TOML artifact, bounded write scope, trust boundary, and required validations.
- **Parent/group coverage** — classification-only coverage for a root, umbrella, or controller surface; it is insufficient for child implementation.
- **Broad invalid role** — any controller, reviewer, umbrella, or mixed-scope role that is not an exact specialist match for the requested write boundary.

## Mandatory blocker cases

- unknown concrete part
- unmapped concrete part
- parent/group-only coverage
- missing role artifact
- invalid/broad role
- ambiguous ownership

## Blocked edits before coverage closes

- product implementation
- platform implementation
- runtime/deploy/migration/integration edits

## Allowed next actions before coverage closes

- create/refine primary role artifact
- add exact catalog mapping
- add/update validators
- add forward-test evidence

## Exact blocker packet

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
  name: <primary-role-name>
  concrete_scope: <exact part>
  allowed_write_boundary: <paths/surfaces>
  trust_boundary: <data/secrets/external/prod impact>
  required_validations:
    - <checks>
decomposition_required: true|false
```

## Forward-test requirements

- child-under-group requests must block
- alias/path drift must not widen coverage
- one-primary-role invariant must hold
- broad/controller fallback must not reappear
- implementation handoff must stay blocked until validation passes
