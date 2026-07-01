# Security and Secret Audit — 2026-06-07

## Scope

Adversarial audit of the current `/srv/bears/plugins/bears` worktree, including unstaged and untracked files, with focus on trust boundaries, secret handling, write-only Infisical creation, refusal and provider handoff, output redaction, git secret-path handling, and abuse paths.

## Trust boundary summary

- **Primary surface:** `secret_factory_governance`
- **Primary actor:** `bears-secret-factory-engineer`
- **Supporting reviewer:** `bears-platform-security-reviewer`
- **Permission:** local generation of allowed secret values and write-only POST to Infisical
- **Secret/data class:** newly generated secret values, Infisical bearer token, project/environment metadata
- **External exposure:** outbound HTTP request to Infisical API v4 create-secret endpoint
- **Audit trail:** repo-local catalog, role route/audit packets, validator output, unit tests, git-discipline inspection
- **Failure path:** secret exfiltration through misrouted endpoint, value-bearing request-file ingestion, or out-of-scope documentation writes
- **Rollback/control owner:** plugin-local governance artifacts and role gate inside `/srv/bears/plugins/bears`

## Evidence commands

- `sed -n '1,220p' /srv/bears/AGENTS.md`
- `sed -n '1,260p' /srv/bears/plugins/bears/AGENTS.md`
- `sed -n '1,220p' /srv/bears/plugins/bears/SPEC.md`
- `sed -n '1,220p' /srv/bears/plugins/bears/requirements.md`
- `sed -n '1,220p' /home/ai1/.codex/plugins/cache/bears-local-marketplace/bears/0.1.0/skills/platform-role-governance/SKILL.md`
- `git status --short --untracked-files=all`
- `git diff --stat`
- `git diff -- .codex-plugin/plugin.json README.md SPEC.md requirements.md assets/catalog/git-discipline.v1.json scripts/git_discipline.py tests/test_git_discipline.py agents/README.md assets/catalog/plugin-skill-catalog.v1.json tests/test_platform_roles.py`
- `nl -ba agents/bears-secret-factory-engineer.toml`
- `nl -ba assets/catalog/secret-factory.v1.json`
- `nl -ba docs/reference/secret-factory.md`
- `nl -ba skills/secret-factory/SKILL.md`
- `nl -ba scripts/secret_factory.py`
- `nl -ba tests/test_secret_factory.py`
- `nl -ba assets/catalog/platform-role-catalog.v1.json | sed -n '240,310p;930,952p;1036,1088p;4448,4488p'`
- `python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/secret_factory.py validate`
- `python3 -m unittest tests.test_secret_factory tests.test_platform_roles tests.test_git_discipline`
- `python3 scripts/secret_factory.py create <allowed.json> --dry-run`
- `python3 scripts/secret_factory.py plan <provider.json>`
- `python3 scripts/secret_factory.py create <forbidden.json> --dry-run`
- Safe local proof snippet with mocked opener showed `INFISICAL_API_URL=http://collector.invalid` is accepted and a POST is prepared to that host.
- Safe local proof snippet with `_load_request()` showed an unexpected extra field `note` is accepted.
- `python3 scripts/platform_roles.py route /srv/bears/plugins/bears/docs/audits/max-plugin-audit-2026-06-07/security-trust-audit.md`

## Files inspected

- `AGENTS.md`
- `SPEC.md`
- `requirements.md`
- `.codex-plugin/plugin.json`
- `README.md`
- `agents/README.md`
- `agents/bears-platform-security-reviewer.toml`
- `agents/bears-secret-factory-engineer.toml`
- `assets/catalog/platform-role-catalog.v1.json`
- `assets/catalog/role-gate-methodology.v1.json`
- `assets/catalog/git-discipline.v1.json`
- `assets/catalog/plugin-skill-catalog.v1.json`
- `assets/catalog/secret-factory.v1.json`
- `docs/reference/secret-factory.md`
- `skills/platform-role-governance/SKILL.md`
- `skills/secret-factory/SKILL.md`
- `scripts/git_discipline.py`
- `scripts/secret_factory.py`
- `tests/test_git_discipline.py`
- `tests/test_platform_roles.py`
- `tests/test_secret_factory.py`

## Findings

| Severity | Path and line | Finding | Impact | Required fix | Validation gap | Remaining attack scenario |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | `scripts/secret_factory.py:276-299`, `assets/catalog/secret-factory.v1.json:15-19`, `docs/reference/secret-factory.md:41` | `INFISICAL_API_URL` is accepted from environment without scheme or host allowlist enforcement. Safe proof with mocked opener produced `http://collector.invalid/api/v4/secrets/APP_RANDOM_HEX` and included an Authorization header. | A mis-set or attacker-controlled environment can redirect both the generated secret value and the Infisical bearer token to an arbitrary host. This breaks the write-only trust boundary and expands blast radius from one secret to the Infisical project token. | Enforce `https` only, pin or allowlist approved Infisical base URLs in code and catalog, reject redirects or foreign-host changes, and add explicit unit tests for hostile URL values. | `scripts/secret_factory.py validate` does not check URL trust rules. `tests/test_secret_factory.py` does not reject non-HTTPS or foreign-host endpoints. | A wrapper shell, CI job, or local runtime injects `INFISICAL_API_URL` to an attacker host; the next `create` call exfiltrates the generated value and bearer token. |
| P2 | `scripts/secret_factory.py:333-351`, `docs/reference/secret-factory.md:21-29`, `skills/secret-factory/SKILL.md:15-16`, `tests/test_secret_factory.py:58-79` | Request-file validation blocks only known value-bearing key names and does not enforce a strict allowlist for request fields. Safe proof showed `_load_request()` accepted an unexpected `note` field. | The tool can ingest arbitrary extra JSON fields from disk. If automation or a human places secret material under an innocuous key, the agent reads that material even though the workflow promises write-only local generation and no secret readback. | Reject unknown request keys, allow only `secret_name`, `kind`, `secret_path`, `bytes`, and `length`, and add recursive tests that fail on any extra field. | Current tests cover `secret_value` and nested `Token` keys only. No validator or unit test enforces an exact request schema. | A helper script writes a request file with secret material under `note`, `metadata`, or another non-blocked key; the Secret Factory reads the file and silently violates the no-read invariant. |
| P3 | `assets/catalog/platform-role-catalog.v1.json:938-947`; route evidence: `python3 scripts/platform_roles.py route /srv/bears/plugins/bears/docs/audits/max-plugin-audit-2026-06-07/security-trust-audit.md` returned `ROLE_COVERAGE_BLOCKER` with `why_blocked: parent_only` | The requested audit artifact path does not have an exact concrete role mapping and falls back to the broad plugin parent, which is decomposition-only. | Security-review documentation can be written outside an exact governed write lane, weakening ownership, traceability, and reviewer-scope enforcement for future audits. | Add an exact `docs/audits` concrete part with one primary owner, or require audit artifacts to live only under an already routed documentation surface and add route tests for that path. | No route expectation or validator covers `docs/audits/**` paths. | A generic controller or reviewer can land authoritative-looking audit files under `docs/audits/` without a concrete ownership packet. |

## PASS items tied to exact evidence

| Item | Evidence | Result |
| --- | --- | --- |
| Exact role route exists for Secret Factory governance. | `python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`; `python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`; `assets/catalog/platform-role-catalog.v1.json:1039-1085`; `tests/test_platform_roles.py` Secret Factory route coverage. | PASS — one primary role (`bears-secret-factory-engineer`) plus reviewer sidecar (`bears-platform-security-reviewer`) matched and the independent control audit allowed implementation handoff for the concrete Secret Factory surface. |
| Dry-run success path is presence-only. | `python3 scripts/secret_factory.py create <allowed.json> --dry-run` returned `{"generator_kind":"random_base64url","provider_handoff":null,"secret_name":"APP_SESSION_SECRET","secret_path":"/","status":"DRY_RUN_ALLOWED"}`; `scripts/secret_factory.py:315-317`; `tests/test_secret_factory.py:38-45`. | PASS — no secret value field was emitted in the success packet. |
| Provider-owned requests are refused without value material, and HTTP error redaction avoids upstream body echo. | `python3 scripts/secret_factory.py plan <provider.json>` returned `HANDOFF_REQUIRED` with no value fields; `tests/test_secret_factory.py:47-57` and `126-152`. | PASS — provider handoff output stayed metadata-only and the tested error path suppressed both generated value text and upstream response body text. |
| Git-discipline coverage includes untracked files and keeps Secret Factory exceptions exact-path only. | `scripts/git_discipline.py:272,288-300`; `assets/catalog/git-discipline.v1.json:91-100`; `tests/test_git_discipline.py:94-135`; worktree inspection used `git status --short --untracked-files=all`. | PASS — current inspection includes untracked files, and a nested file under `skills/secret-factory/` still triggers operator review instead of being silently exempted. |

## Finding counts

- P0: 0
- P1: 1
- P2: 1
- P3: 1
- PASS items: 4
