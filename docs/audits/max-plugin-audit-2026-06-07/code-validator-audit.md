# Code Validator Audit — 2026-06-07

## Scope

Audit target: current unstaged and untracked code-health surfaces tied to Python scripts, validators, CLI behavior, deterministic JSON contracts, unit tests, and implementation correctness in `/srv/bears/plugins/bears`.

Changed surfaces reviewed:

- `scripts/secret_factory.py`
- `tests/test_secret_factory.py`
- `assets/catalog/secret-factory.v1.json`
- `agents/bears-secret-factory-engineer.toml`
- `skills/secret-factory/SKILL.md`
- `docs/reference/secret-factory.md`
- `scripts/git_discipline.py`
- `tests/test_git_discipline.py`
- `assets/catalog/git-discipline.v1.json`
- `assets/catalog/platform-role-catalog.v1.json`
- `tests/test_subagents_roles.py`
- sync surfaces required by the new governance lane: `.codex-plugin/plugin.json`, `README.md`, `SPEC.md`, `requirements.md`, `agents/README.md`, `assets/catalog/plugin-skill-catalog.v1.json`, `docs/generated/README.skill-inventory.md`, `docs/generated/SPEC.skill-inventory.md`

Excluded from scope: unrelated audit artifacts already present in the worktree.

## Evidence commands

Repository state and diff:

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- targeted `git diff -- ...` on changed code, catalog, test, and sync files

Validators and tests executed:

- `python3 scripts/secret_factory.py validate`
- `python3 scripts/subagents_roles.py validate`
- `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/git_discipline.py validate`
- `python3 scripts/skill_catalog.py validate && python3 scripts/skill_catalog.py generate --check`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`
- `python3 -m unittest tests.test_secret_factory tests.test_git_discipline tests.test_subagents_roles`
- direct CLI normal/failure probes for `scripts/secret_factory.py create --dry-run` and `plan`
- direct negative probes:
  - request file containing camelCase `secretValue`
  - in-memory catalog mutation with `random_hex.default_bytes = 8`

Files inspected with line references:

- `scripts/secret_factory.py`
- `tests/test_secret_factory.py`
- `docs/reference/secret-factory.md`
- `assets/catalog/secret-factory.v1.json`
- `scripts/git_discipline.py`
- `tests/test_git_discipline.py`
- `assets/catalog/git-discipline.v1.json`
- `assets/catalog/platform-role-catalog.v1.json`
- `tests/test_subagents_roles.py`
- `assets/catalog/plugin-skill-catalog.v1.json`
- `docs/generated/README.skill-inventory.md`
- `docs/generated/SPEC.skill-inventory.md`
- `README.md`
- `.codex-plugin/plugin.json`

## Findings

| Severity | Exact path and line | Impact | Required fix | Missing tests |
| --- | --- | --- | --- | --- |
| P1 | `scripts/secret_factory.py:333-351`, `docs/reference/secret-factory.md:19-29`, `tests/test_secret_factory.py:58-79` | The request-file filter only rejects exact field names in `FORBIDDEN_REQUEST_FIELDS`. A probe request containing camelCase `secretValue` was accepted by `python3 scripts/secret_factory.py plan ...` and returned `ALLOWED`. Because `_load_request()` parses the whole JSON before rejecting keys, value-bearing payloads under `secretValue`, `apiToken`, `clientSecret`, or similar variants can be read into process memory even though this lane claims a write-only and no-read contract. | Normalize keys before acceptance and reject value-bearing name variants by policy, not exact spelling only. At minimum, block snake_case, camelCase, hyphenated, and suffix/prefix forms for secret/value/token/credential/private-key fields before any request is treated as valid input. | Add CLI and unit coverage for camelCase, mixed-case, hyphenated, and nested variants such as `secretValue`, `apiToken`, `client_secret`, and nested provider payloads. |
| P2 | `scripts/secret_factory.py:91-105`, `scripts/secret_factory.py:176-200`, `assets/catalog/secret-factory.v1.json:32-54`, `tests/test_secret_factory.py:35-37` | `validate_catalog()` checks min/max bounds but never validates that `default_bytes` or `default_length` are present, typed correctly, and inside those bounds. An in-memory probe that changed `random_hex.default_bytes` from `32` to `8` still returned `[]` from `validate_catalog()`. That means a future catalog drift can pass validation while default-only requests generate under-strength values or hit runtime conversion errors. | Extend `validate_catalog()` to verify `default_bytes` and `default_length` for presence, integer type, and `min <= default <= max`. Apply the same rule to every allowed generator branch. | Add regression tests for invalid `default_bytes`, invalid `default_length`, and non-integer defaults so validator failures are enforced before runtime use. |

## PASS items with exact evidence

1. **Secret Factory role routing is wired correctly and independently auditable.**
   - Catalog entry: `assets/catalog/platform-role-catalog.v1.json:1039-1082`
   - Route tests: `tests/test_subagents_roles.py:322-338`
   - Runtime evidence:
     - `python3 scripts/subagents_roles.py validate` → PASS
     - `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json` → `status: matched`, `primary_role: bears-secret-factory-engineer`
     - `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json` → `implementation_handoff_allowed: true`

2. **The git-discipline exception logic does not over-whitelist adjacent files.**
   - Implementation: `scripts/git_discipline.py:252-296`
   - Tests: `tests/test_git_discipline.py:94-135`
   - Validation evidence:
     - `python3 scripts/git_discipline.py validate` → PASS
     - `python3 -m unittest tests.test_secret_factory tests.test_git_discipline tests.test_subagents_roles` → PASS (`Ran 98 tests in 7.235s`)
   - The added test proves `skills/secret-factory/SKILL.md` is exempt while `skills/secret-factory/notes.txt` still triggers operator review.

3. **Skill discovery and sync surfaces were updated consistently for the new lane.**
   - Catalog and generated inventory:
     - `assets/catalog/plugin-skill-catalog.v1.json:54-56`
     - `docs/generated/README.skill-inventory.md:19`
     - `docs/generated/SPEC.skill-inventory.md:6`
   - Manifest and README sync:
     - `.codex-plugin/plugin.json:33,69`
     - `README.md:128,174`
   - Validation evidence:
     - `python3 scripts/skill_catalog.py validate && python3 scripts/skill_catalog.py generate --check` → PASS
     - `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills` → PASS

## Validation summary

- Normal path validated: `scripts/secret_factory.py create <request.json> --dry-run` returned `DRY_RUN_ALLOWED` with presence-only output.
- Failure path validated: `scripts/secret_factory.py plan <provider-owned request.json>` returned exit code `2` and `HANDOFF_REQUIRED` without value material.
- Integration edge validated: route and audit commands for `/srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json` both matched `secret_factory_governance` and selected exactly one primary role.

## Residual risk

- `scripts/secret_factory.py` is already 417 lines, `scripts/git_discipline.py` is 402 lines, and `tests/test_subagents_roles.py` is 1378 lines. No immediate defect was proven from size alone, but these files are above the 400-line review threshold from the active Python codeflow guidance and will become harder to audit if more behavior is added without splitting.
