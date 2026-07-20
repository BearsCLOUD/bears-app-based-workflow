# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A seven-phase app workflow plugin that ships to two runtimes (Claude Code and Codex) from one repository. Canonical workflow state lives in a registered per-project SQLite database exposed through two stdio MCP servers, both started from the same single-file runtime:

- `app-workflow` - 12 read-only tools (`serve --mode reader`)
- `app-workflow-maintainer` - 13 registration/mutation tools (`serve --mode maintainer`)

The runtime is stdlib-only Python 3.10+; `git` must be on PATH for project registration. README.md is the authoritative spec for tool surfaces, limits, and phase semantics; contracts/ holds the DB schema and MCP tool contract.

## Commands

```bash
# Full test suite (36 tests, stdlib unittest, ~10s)
python3 -m unittest discover -s tests

# One file / one test
python3 tests/test_app_workflow.py
python3 tests/test_app_workflow.py StateDirEnvTests.test_state_dir_override_ignores_codex_home

# Run an MCP server by hand
python3 scripts/app_workflow.py serve --mode reader      # app-workflow
python3 scripts/app_workflow.py serve --mode maintainer  # app-workflow-maintainer

# Read-only workflow validation
python3 scripts/app_workflow.py validate --project-ref <ref> --wave-id <id>
python3 skills/app-analyze/scripts/validate_workflow.py --project-ref <ref> --wave-id <id>

# Codex-side installer (writes a managed [agents.*] block into $CODEX_HOME/config.toml)
./install --codex-home /tmp/bears-app-workflow-codex --dry-run

# CD runner regression check (what the CD workflow runs)
python3 -B .github/runner/test_graph_instruction_retirement.py --verbose
```

Run tests with unittest, not pytest: `test_repository_limits_and_artifact_language` in tests/test_plugin_shape.py counts every working-tree file (gitignored ones included) against an 80-file / 1 MiB budget, and a stray `.pytest_cache/` directory is enough to fail it locally.

## Architecture

### Single-file runtime: scripts/app_workflow.py (~2.2k lines)

Layered top to bottom: validation/hashing/path helpers -> registry and project SQLite access -> mutation backends -> read/validation/migration backends -> MCP tool schemas and reader/maintainer dispatch -> JSON-RPC-over-stdio loop and CLI. The project DB schema is not embedded in the script: it is loaded at runtime from contracts/app-workflow-db-v1.sql. The MCP tool contract mirror is contracts/app-workflow-mcp-tools.v1.json.

### State model

- `registry.sqlite3` maps stable `project_ref` values to absolute git roots. It lives in `$BEARS_APP_WORKFLOW_STATE_DIR`, otherwise `$CODEX_HOME/state/bears-app-based-workflow/`.
- Per-project state is `<project>/.bears/app-workflow.sqlite3`; it never stores the absolute project path. Markdown phase artifacts live under `waves/<wave_id>/` in the target project.
- JSON workflow-state fallbacks are forbidden; `project_migrate_json` imports the two legacy JSON formats only into an empty database.

### Integrity invariants (do not weaken)

- Every mutation is CAS-guarded: unique `request_id` plus expected revision plus expected logical digest; batch graph/plan changes commit or roll back atomically. A `request_id` replay is idempotent only for an identical payload digest.
- Logical digest = SHA-256 over sorted canonical rows, excluding `request_log`, `audit_attestations`, and the metadata revision.
- `workflow_mark_audited` revalidates at the same revision inside its own transaction; any later mutation stales the attestation.
- SQLite discipline: foreign keys ON, DELETE journal (WAL is rejected), FULL synchronous, 5s busy timeout.
- Graph records are never physically deleted: lifecycle is active/retired with optional replacement refs, and the relation set is closed.
- Response limits: pages default 50 / max 200, traversal depth default 4 / max 16, requests 1 MiB, responses 512 KiB.

### Dual-runtime packaging

|             | Claude Code                                    | Codex                                              |
|-------------|------------------------------------------------|----------------------------------------------------|
| Manifest    | .claude-plugin/plugin.json (+ marketplace.json) | .codex-plugin/plugin.json (+ .agents/plugins/marketplace.json) |
| MCP wiring  | claude/mcp.json via ${CLAUDE_PLUGIN_ROOT}       | .mcp.json (cwd-relative)                            |
| Roles       | claude/agents/*.md (three L3 agents)            | agents/*.toml (five profiles) installed by ./install |

skills/ (eight skills: one per phase plus subagents) is shared by both runtimes; skills/*/agents/openai.yaml files are Codex UI metadata only. The five Codex profiles: app-worker (no MCP), app-reviewer and app-analyst (read-only tool subsets), repo-orchestrator (both servers, owns a delegated repository lane), workflow-orchestrator (no MCP, opens lanes). claude/agents/*.md mirror the three L3 profiles with Claude tool names - keep the allowlists in sync; tests/test_plugin_shape.py and tests/test_claude_plugin_shape.py enforce both sides.

Ownership: the DIRECT primary (main session) or one persistent repo-orchestrator owns a wave and both servers; only the wave owner records mutations. Delegated orchestrator lanes are Codex-only; in Claude Code the main session is the DIRECT primary, one session per repository.

### Releases and CD

- The version (currently 0.6.0) appears in .codex-plugin/plugin.json, .claude-plugin/plugin.json, both marketplace.json files, and the dist/ filenames, and is asserted by tests - bump all of them together.
- dist/ holds a committed, pre-built release bundle; a test verifies the archive SHA-256 against the .bundle.json manifest, so changing either means regenerating both. CD does not build dist/.
- Pushing to main triggers .github/workflows/plugin-marketplace-cd.yml on a self-hosted runner: a recovery check, then a root-owned exact-SHA promotion gateway updates the Codex marketplace checkout and installs roles, writing receipts. Keep exact-SHA ancestry, monotonic SemVer, and the receipt/transaction invariants in .github/runner/bears_deploy/ intact.

## Repository rules (from AGENTS.md)

- All plugin instructions and documentation are English-only; README.md, CHANGELOG.md, THIRD_PARTY_NOTICES, and every skills/*/SKILL.md must be pure ASCII (test-enforced).
- Budgets are test-enforced: at most 80 working-tree files, 1 MiB total, 30 KiB per skill directory.
- Procedures belong in skills/, unique role behavior in agents/; workspace-level rules stay outside this repository.
