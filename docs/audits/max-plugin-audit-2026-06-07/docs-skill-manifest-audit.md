# Max Plugin Audit — 2026-06-07

## Scope
Unstaged and untracked workspace in `/srv/bears/plugins/bears` at date `2026-06-07`: manifest and skill-surface changes for Secret Factory onboarding.

Assessed surfaces:
- `README.md`, `SPEC.md`, `requirements.md`
- `assets/catalog/*.v1.json`
- `agents/README.md`, new `agents/bears-secret-factory-engineer.toml`
- `scripts/git_discipline.py`, `scripts/secret_factory.py`
- `tests/test_git_discipline.py`, `tests/test_subagents_roles.py`, `tests/test_secret_factory.py`
- `docs/generated/README.skill-inventory.md`, `docs/generated/SPEC.skill-inventory.md`, `docs/reference/secret-factory.md`
- `skills/secret-factory/SKILL.md`

## Evidence (exact commands and files inspected)
Commands:
- `git status --short`
- `git diff -- .codex-plugin/plugin.json README.md SPEC.md agents/README.md assets/catalog/git-discipline.v1.json assets/catalog/platform-role-catalog.v1.json assets/catalog/plugin-skill-catalog.v1.json docs/generated/README.skill-inventory.md docs/generated/SPEC.skill-inventory.md requirements.md scripts/git_discipline.py tests/test_git_discipline.py tests/test_subagents_roles.py`
- `python3 scripts/secret_factory.py validate`
- `python3 scripts/subagents_roles.py validate`
- `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/subagents_roles.py route secret-factory`
- `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/docs/reference/secret-factory.md`
- `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/tests/test_secret_factory.py`
- `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 -m unittest tests/test_secret_factory.py tests/test_subagents_roles.py tests/test_git_discipline.py`
- `python3 scripts/skill_catalog.py validate`
- `python3 scripts/skill_catalog.py generate --check`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`
- `python3 scripts/role_gate_methodology.py validate`
- `python3 scripts/git_discipline.py validate`

Files inspected (line references in table below): all above plus:
`assets/catalog/secret-factory.v1.json`, `scripts/secret_factory.py`, `skills/secret-factory/SKILL.md`, `agents/bears-secret-factory-engineer.toml`, `requirements.md`, `git_discipline.py`, `tests/test_git_discipline.py`, `tests/test_secret_factory.py`.

## Findings

| Status | Severity | Exact path and line | Impact | Required fix | Validation gap |
| --- | --- | --- | --- | --- | --- |
| PASS | PASS | `assets/catalog/platform-role-catalog.v1.json:273-305` | Secret Factory now has a dedicated specialist role with bounded write zones and forbidden actions; this is required for role coverage and non-ambiguous concrete ownership. | No fix required; keep role mapping aligned with any future edits. | Keep route/audit evidence run on future catalog changes. |
| PASS | PASS | `assets/catalog/platform-role-catalog.v1.json:4452-4485` and `scripts/subagents_roles.py route secret-factory` output | Route and audit packets now resolve Secret Factory targets (catalog file, script, skill, docs, test, agent toml, alias) to `secret_factory_governance` + `bears-secret-factory-engineer`. | No fix required. | Keep additional route aliases synced with manifest if new entry points are added. |
| PASS | PASS | `assets/catalog/plugin-skill-catalog.v1.json:54-57`, `docs/generated/README.skill-inventory.md:19`, `docs/generated/SPEC.skill-inventory.md:6` | Skill discovery inventory includes new `secret-factory` active skill; generated inventories match catalog declarations (`skill_catalog.py generate --check` passed). | No fix required. | Re-run `skill_catalog.py generate --check` after any skill catalog updates. |
| PASS | PASS | `README.md:126-129`, `SPEC.md:177-185`, `requirements.md:46`, `docs/reference/secret-factory.md:1-47`, `skills/secret-factory/SKILL.md:8-45` | Plugin documentation covers scope, write-only control, provider handoff, validation commands, and allowed kinds across README/SPEC/docs/reference/skill. | No fix required. | Run docs validation in closeout (`python3 scripts/subagents_roles.py validate`, `python3 scripts/secret_factory.py validate`, `python3 -m unittest tests/test_secret_factory.py`). |
| PASS | PASS | `scripts/secret_factory.py:65-139`, `scripts/secret_factory.py:219-255`, `scripts/secret_factory.py:265-331`, `tests/test_secret_factory.py:35-57`, `tests/test_secret_factory.py:81-120`, `tests/test_secret_factory.py:126-133` | Write-only contract is enforced in code and tests: no secret-bearing fields in request input, no value in CLI/output packets, POST-only Infisical endpoint, refusal packet for provider-owned kinds. | No fix required at this audit point. | No end-to-end Infisical call executed due environment dependency; only fake/monkey-patched transport tested. |
| PASS | PASS | `scripts/git_discipline.py:252-260`, `assets/catalog/git-discipline.v1.json:89-98`, `tests/test_git_discipline.py:94-136` | Secret factory paths are exempt from secret-like path review, so governance files no longer force operator-review due naming-only heuristics. | No fix required. | Confirm exception coverage when adding new Secret Factory write artifacts. |
| P3 | P3 | `tests/test_secret_factory.py:47-57` and `assets/catalog/secret-factory.v1.json:56-87` | Refusal-path coverage is incomplete: catalog defines five non-allowed refusal classes, but tests only exercise one (`provider_issued_api_key`). | Add unit tests for every `refusal_classes` kind (`oauth_client_secret`, `ssh_private_key`, `tls_private_key`, `payment_credential`, `wallet_private_key`) and assert handoff packet shape/fields/no value leakage for each. | Missing direct regression checks for refusal classes except one kind. |
| P3 | P3 | `tests/test_git_discipline.py:94-136` and `assets/catalog/git-discipline.v1.json:89-98` | Exception-root policy is only unit-tested for `SKILL.md` plus one nested-file negative case. It does not assert all exception roots (`assets/catalog/secret-factory.v1.json`, `scripts/secret_factory.py`, `docs/reference/secret-factory.md`, `tests/test_secret_factory.py`, `agents/bears-secret-factory-engineer.toml`). | Add one test per root in `secret_path_exception_roots` and assert no operator-review for changes restricted to each path. | Coverage gap is partial evidence against path exception policy. |

## Finding counts
- PASS: 6
- P3: 2
- P2/P1/P0: 0
