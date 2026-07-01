# Governance and Role Audit — 2026-06-07

## Scope

Audit target: `/srv/bears/plugins/bears` current worktree, including modified, unstaged, and untracked files.

Focus areas:
- governance and role routing
- role catalog and lifecycle gates
- subagent and plugin-root boundaries
- Spec Kit packet alignment
- plugin manifest/catalog sync
- route/audit validator coverage

Changed files inspected: 19
- Modified: `.codex-plugin/plugin.json`, `README.md`, `SPEC.md`, `agents/README.md`, `assets/catalog/git-discipline.v1.json`, `assets/catalog/platform-role-catalog.v1.json`, `assets/catalog/plugin-skill-catalog.v1.json`, `docs/generated/README.skill-inventory.md`, `docs/generated/SPEC.skill-inventory.md`, `requirements.md`, `scripts/git_discipline.py`, `tests/test_git_discipline.py`, `tests/test_platform_roles.py`
- Untracked: `agents/bears-secret-factory-engineer.toml`, `assets/catalog/secret-factory.v1.json`, `docs/reference/secret-factory.md`, `scripts/secret_factory.py`, `skills/secret-factory/SKILL.md`, `tests/test_secret_factory.py`

Finding counts:
- P0: 0
- P1: 2
- P2: 1
- P3: 0

## Evidence commands

- `git status --short --branch`
- `git diff --name-only`
- `git ls-files --others --exclude-standard`
- `git diff --unified=0 -- <changed files>`
- `python3 scripts/platform_roles.py route /srv/bears/plugins/bears`
- `python3 scripts/platform_roles.py audit /srv/bears/plugins/bears`
- `python3 scripts/platform_roles.py route <each changed file>`
- `python3 scripts/platform_roles.py audit <role-catalog|git-discipline|plugin-skill-catalog|secret-factory targets>`
- `python3 scripts/project_registry_gate.py gate /srv/bears/plugins/bears`
- `python3 scripts/platform_roles.py validate`
- `python3 scripts/secret_factory.py validate`
- `python3 scripts/git_discipline.py validate`
- `python3 scripts/skill_catalog.py validate`
- `python3 scripts/skill_catalog.py generate --check`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills --feature-dir /srv/bears/specs/005-telegram-workflow-plugin --require-artifacts`
- `python3 -m unittest tests/test_platform_roles.py tests/test_git_discipline.py tests/test_secret_factory.py`
- `python3 -m unittest tests/test_validate_overlay.py`
- `python3 -m pytest -q tests/test_skill_catalog.py tests/test_validate_overlay.py tests/test_platform_roles.py`
- `if [ -d specs ]; then ...; else echo 'specs_dir=missing'; fi`

## Files inspected

- `/srv/bears/AGENTS.md`
- `/srv/bears/plugins/bears/AGENTS.md`
- `assets/catalog/platform-role-catalog.v1.json`
- `assets/catalog/role-gate-methodology.v1.json`
- `.codex-plugin/plugin.json`
- `README.md`
- `SPEC.md`
- `requirements.md`
- `agents/README.md`
- `agents/bears-secret-factory-engineer.toml`
- `assets/catalog/git-discipline.v1.json`
- `assets/catalog/plugin-skill-catalog.v1.json`
- `assets/catalog/secret-factory.v1.json`
- `docs/generated/README.skill-inventory.md`
- `docs/generated/SPEC.skill-inventory.md`
- `docs/reference/secret-factory.md`
- `scripts/git_discipline.py`
- `scripts/secret_factory.py`
- `skills/secret-factory/SKILL.md`
- `tests/test_git_discipline.py`
- `tests/test_platform_roles.py`
- `tests/test_secret_factory.py`

## Findings

| Severity | Exact path and line | Impact | Required fix | Validation gap |
| --- | --- | --- | --- | --- |
| P1 | `specs/` missing; `git status --short --branch` shows one broad change set across `.codex-plugin/plugin.json`, `assets/catalog/platform-role-catalog.v1.json`, `assets/catalog/plugin-skill-catalog.v1.json`, `scripts/git_discipline.py`, `scripts/secret_factory.py`, `skills/secret-factory/SKILL.md`, docs, and tests; `python3 scripts/platform_roles.py route /srv/bears/plugins/bears` returns `ROLE_COVERAGE_BLOCKER` with `why_blocked: parent_only`. | The worktree spans at least four concrete parts (`workflow_overlay_core_plugin_surface`, `workflow_overlay_skill_inventory`, `platform_role_governance`/`git_discipline`, and `secret_factory_governance`) but there is no active Spec Kit packet or task decomposition that proves the one-primary-role invariant per write scope. Future handoff or closeout cannot prove lifecycle-gate compliance. | Create one active `specs/<feature>/` packet with `spec.md`, `plan.md`, `tasks.md`, and `speckit-analyze` PASS. Split tasks by exact concrete part and primary role before more implementation or handoff. | No `specs/` directory was present (`specs_dir=missing`). No packet was available to tie the current multi-role changes to exact tasks or stage-boundary audit evidence. |
| P1 | `agents/bears-secret-factory-engineer.toml:13-28`; `skills/secret-factory/SKILL.md:12-45`; `docs/reference/secret-factory.md:43-48`; `assets/catalog/secret-factory.v1.json:133-137`; required contract in `assets/catalog/platform-role-catalog.v1.json:1076-1081`. | Future agents can follow the Secret Factory local instructions and still skip mandatory independent control audit and route-regression checks. The worker role, skill, docs, and local catalog do not consistently require `platform_roles.py audit`, `platform_roles.py validate`, or `tests/test_platform_roles.py`, even though the concrete part contract requires them. | Align every Secret Factory instruction surface to the concrete part contract: require `platform_roles.py validate`, `platform_roles.py route`, `platform_roles.py audit`, `scripts/secret_factory.py validate`, and `python3 -m unittest tests/test_secret_factory.py tests/test_platform_roles.py`. Add the audit step to the start workflow, not only to the reference doc. | Current green status came from manual audit-time commands, not from the Secret Factory local instruction chain. A future worker could stop after the shorter local validation list and still claim success. |
| P2 | Catalog declares password alphabet metadata at `assets/catalog/secret-factory.v1.json:48-53`; implementation hardcodes `PASSWORD_ALPHABET` at `scripts/secret_factory.py:24` and uses it at `scripts/secret_factory.py:194-203`; catalog validation at `scripts/secret_factory.py:65-143` does not verify the alphabet field; tests at `tests/test_secret_factory.py:35-153` do not assert alphabet alignment. | The contract says validation must fail on generator drift (`SPEC.md:185`), but the random-password alphabet can drift between catalog and code while all current validators still pass. This weakens the write-only generator contract. | Either consume and validate the catalog `alphabet` field in `secret_factory.py` and add unit tests, or remove the unused field from the catalog and narrow the contract text. | No validator or unit test currently checks that the runtime password alphabet matches the catalog declaration. |

## PASS items tied to exact evidence

| Status | Area | Exact evidence | Result |
| --- | --- | --- | --- |
| PASS | Exact role routing for touched concrete files | Per-file route checks mapped all 19 changed files to one concrete part and one primary role. Summary: `.codex-plugin/plugin.json -> workflow_overlay_core_plugin_surface -> bears-workflow-overlay-platform-engineer`; `assets/catalog/plugin-skill-catalog.v1.json` and `docs/generated/* -> workflow_overlay_skill_inventory -> bears-workflow-overlay-platform-engineer`; `assets/catalog/platform-role-catalog.v1.json`, `assets/catalog/git-discipline.v1.json`, `scripts/git_discipline.py`, `tests/test_git_discipline.py`, `README.md`, `SPEC.md`, `requirements.md`, `agents/README.md`, `tests/test_platform_roles.py -> bears-platform-role-governor`; Secret Factory files -> `secret_factory_governance -> bears-secret-factory-engineer`. | Concrete file routing is deterministic and non-ambiguous. |
| PASS | Manifest, skill catalog, and generated inventory sync | `.codex-plugin/plugin.json:4-69`; `assets/catalog/plugin-skill-catalog.v1.json:53-56`; `docs/generated/README.skill-inventory.md:17-21`; `docs/generated/SPEC.skill-inventory.md:4-6`; commands: `python3 scripts/skill_catalog.py validate`, `python3 scripts/skill_catalog.py generate --check`, `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`, and `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills --feature-dir /srv/bears/specs/005-telegram-workflow-plugin --require-artifacts`. | No manifest/catalog/generated-doc drift was detected for the active `secret-factory` skill addition. |
| PASS | Governance validators and tests executed cleanly | `python3 scripts/platform_roles.py validate`; `python3 scripts/secret_factory.py validate`; `python3 scripts/git_discipline.py validate`; `python3 -m unittest tests/test_platform_roles.py tests/test_git_discipline.py tests/test_secret_factory.py` -> `Ran 98 tests ... OK`; `python3 -m unittest tests/test_validate_overlay.py` -> `Ran 31 tests ... OK`; `python3 -m pytest -q tests/test_skill_catalog.py tests/test_validate_overlay.py tests/test_platform_roles.py` -> `118 passed, 255 subtests passed`. | Current repo state is validator-clean despite the process and contract gaps above. |
| PASS | Untracked-file handling in git discipline | `assets/catalog/git-discipline.v1.json:92-99`; `scripts/git_discipline.py:261-296`; `tests/test_git_discipline.py:94-136`; `git status --short --branch --untracked-files=all` is now used and exact exception-root behavior is covered by tests. | No finding in this area. The new git-discipline logic includes untracked files and keeps the Secret Factory exceptions path-bounded. |

## Checked areas with no finding

- Plugin-root manifest surface: route and audit for `.codex-plugin/plugin.json` matched `workflow_overlay_core_plugin_surface`; exact overlay validators passed.
- Skill inventory discovery surface: route and audit for `assets/catalog/plugin-skill-catalog.v1.json` and generated inventory docs matched `workflow_overlay_skill_inventory`; generated fragments were in sync.
- Role catalog surface: route and audit for `assets/catalog/platform-role-catalog.v1.json` matched `platform_role_governance`; `python3 scripts/platform_roles.py validate` passed.
- Git discipline surface: route and audit for `assets/catalog/git-discipline.v1.json` matched `git_discipline`; validator and unit tests passed.
- Secret Factory route coverage: route and audit for `assets/catalog/secret-factory.v1.json` matched `secret_factory_governance`; validator and local unit tests passed.

