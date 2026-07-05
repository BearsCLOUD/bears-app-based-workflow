# QA Validation Audit — current unstaged and untracked work

## Scope

- Repo: `/srv/bears/plugins/bears`
- Audit date: `2026-06-07`
- Change boundary analyzed:
  - New Secret Factory governance surface:
    - `agents/bears-secret-factory-engineer.toml`
    - `assets/catalog/secret-factory.v1.json`
    - `docs/reference/secret-factory.md`
    - `scripts/secret_factory.py`
    - `skills/secret-factory/SKILL.md`
    - `tests/test_secret_factory.py`
  - Supporting route, inventory, and Git closeout changes:
    - `.codex-plugin/plugin.json`
    - `README.md`
    - `SPEC.md`
    - `agents/README.md`
    - `assets/catalog/git-discipline.v1.json`
    - `assets/catalog/platform-role-catalog.v1.json`
    - `assets/catalog/plugin-skill-catalog.v1.json`
    - `docs/generated/README.skill-inventory.md`
    - `docs/generated/SPEC.skill-inventory.md`
    - `requirements.md`
    - `scripts/git_discipline.py`
    - `tests/test_git_discipline.py`
    - `tests/test_subagents_roles.py`
- Read-only audit only. No implementation files were modified.
- No live secret creation was attempted. No live Infisical write was attempted.

## Evidence commands

### Diff and boundary

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- `git ls-files --others --exclude-standard`
- `git diff --check`
- `python3 scripts/git_discipline.py inspect --repo . --json`

### Validators and route/audit gates

- `python3 scripts/secret_factory.py validate`
- `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/subagents_roles.py validate`
- `python3 scripts/git_discipline.py validate`
- `python3 scripts/skill_catalog.py validate`
- `python3 scripts/skill_catalog.py generate --check`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`

### Tests

- `python3 -m unittest tests/test_secret_factory.py tests/test_git_discipline.py tests/test_subagents_roles.py`
- `python3 -m unittest discover -s tests`

### Safe runtime probes

- Safe dry-run with unexpected request field:
  - `python3 scripts/secret_factory.py create <tmp-request.json> --dry-run`
  - request body included `"unexpected": "allowed?"`
- Safe dry-run with path traversal:
  - `python3 scripts/secret_factory.py create <tmp-request.json> --dry-run`
  - request body included `"secret_path": "../bad"`
- In-memory validator probe:
  - imported `scripts/secret_factory.py`
  - removed `payment_credential` and `wallet_private_key` from a catalog copy
  - ran `validate_catalog(...)`

## Files inspected

- `/srv/bears/AGENTS.md`
- `/srv/bears/plugins/bears/AGENTS.md`
- `scripts/secret_factory.py`
- `assets/catalog/secret-factory.v1.json`
- `skills/secret-factory/SKILL.md`
- `README.md`
- `SPEC.md`
- `requirements.md`
- `assets/catalog/platform-role-catalog.v1.json`
- `assets/catalog/plugin-skill-catalog.v1.json`
- `assets/catalog/git-discipline.v1.json`
- `tests/test_secret_factory.py`
- `tests/test_subagents_roles.py`
- `tests/test_git_discipline.py`

## Findings

| Severity | Finding | Exact path and line | Impact | Required fix | Missing validation | Recommended command |
| --- | --- | --- | --- | --- | --- | --- |
| P2 | `validate_catalog()` does not require all catalog-claimed refusal kinds. `payment_credential` and `wallet_private_key` are documented as mandatory provider handoff classes, but the validator only enforces four kinds. An in-memory probe removed both classes and `validate_catalog(...)` still returned `[]`. | `assets/catalog/secret-factory.v1.json:77-85`; `SPEC.md:183-185`; `scripts/secret_factory.py:107-110`; `tests/test_secret_factory.py:47-56` | Validator coverage is weaker than the contract. Future drift can remove refusal coverage for payment or wallet materials without failing the declared Secret Factory validator. Current behavior fails closed for unknown kinds, but it does not preserve the promised handoff classification. | Extend `validate_catalog()` to require every refusal kind that the contract treats as mandatory, including `payment_credential` and `wallet_private_key`. Add negative tests that prove validator failure when any mandatory refusal class is removed. | No negative test proves validator failure for missing `payment_credential` or `wallet_private_key`. No runtime test proves handoff classification for those kinds. | `python3 scripts/secret_factory.py validate && python3 -m unittest tests/test_secret_factory.py` |
| P2 | The skill contract says the request file must contain only `secret_name`, `kind`, and optional generation bounds or `secret_path`, but the runtime accepts extra keys. A safe dry-run request with an additional `unexpected` field returned `DRY_RUN_ALLOWED`. | `skills/secret-factory/SKILL.md:15-16`; `scripts/secret_factory.py:333-351` | Request shape is not deterministic at the documented boundary. Extra fields can silently pass through review, which weakens contract clarity and makes later unsafe extensions easier to miss. | Either enforce a strict request-key allowlist in `_load_request()` and per-generator validation, or narrow the skill wording so it does not claim a stricter contract than the code. | No negative test rejects unknown request keys. The existing tests only reject forbidden value-bearing field names. | `python3 -m unittest tests/test_secret_factory.py` plus a new case for unknown-key rejection |
| P3 | The documented validation envelope is broader than the operator-facing validation commands. `SPEC.md` says validation must fail on role-route, request-shape, output-redaction, skill, docs, and test drift, but `scripts/secret_factory.py validate` checks catalog structure only, and `README.md` plus `requirements.md` omit the independent control audit command from the listed Secret Factory validation path. | `SPEC.md:185`; `README.md:128`; `requirements.md:46`; `scripts/secret_factory.py:354-360` | Proof strength is capped at partial. An operator following the short validation commands can miss route-audit or cross-artifact drift even though the spec claims stronger failure semantics. | Add one composite validation command or script that covers route, independent control audit, catalog validation, and artifact-alignment checks; or narrow the spec and README language to the evidence actually enforced today. | No deterministic validator links the catalog to `skills/secret-factory/SKILL.md` or `docs/reference/secret-factory.md`. The short validation lists do not include `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`. | `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json && python3 scripts/validate_overlay.py --json validate --strict-overlay-skills` |

## PASS evidence

| Area | Exact evidence | Result |
| --- | --- | --- |
| Role routing and independent control audit | `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json` returned `status: matched`, `concrete_part: secret_factory_governance`, `primary_role: bears-secret-factory-engineer`. `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json` returned `implementation_handoff_allowed: true`. Supporting unit test coverage exists at `tests/test_subagents_roles.py:322-338`. | PASS |
| Git discipline path exception coverage | `python3 scripts/git_discipline.py inspect --repo . --json` returned `status: GIT_DISCIPLINE_READY`, `secret_like_paths: []`, `operator_review_required: false` for the current worktree. Regression tests exist at `tests/test_git_discipline.py:94-135` for exact Secret Factory exception roots and nested-path blocking. | PASS |
| Secret Factory validator and repo-wide validators | `python3 scripts/secret_factory.py validate` returned `OK: secret factory catalog valid`. `python3 scripts/subagents_roles.py validate`, `python3 scripts/git_discipline.py validate`, `python3 scripts/skill_catalog.py validate`, `python3 scripts/skill_catalog.py generate --check`, and `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills` all passed. | PASS |
| Unit and integration-style test coverage execution | `python3 -m unittest tests/test_secret_factory.py tests/test_git_discipline.py tests/test_subagents_roles.py` ran `98 tests` and passed. `python3 -m unittest discover -s tests` ran `381 tests` and passed. | PASS |
| Failure-path rejection for unsafe Infisical path | A safe dry-run request with `"secret_path": "../bad"` failed with `ERROR: secret_path must be an absolute Infisical path without parent traversal`, matching `scripts/secret_factory.py:211-215`. | PASS |

## Coverage summary

- Positive path validated:
  - Secret Factory exact role route and independent control audit
  - Catalog validator
  - Repo-wide validator suite
  - Full unit test suite
- Failure path validated:
  - `secret_path` traversal rejection
  - request-file rejection for forbidden value-bearing fields by existing unit tests
  - upstream HTTP error redaction by existing unit tests
- Integration edge validated:
  - Git discipline exception roots for governance file names
  - skill catalog generation/check and overlay validation

## Residual risk

- Confidence in current repo health is good for the executed validators and tests.
- Confidence in Secret Factory proof strength is capped by three gaps:
  1. refusal-class completeness is under-validated,
  2. documented request-shape strictness is not enforced,
  3. cross-artifact validation claims are broader than the short documented validation path.

