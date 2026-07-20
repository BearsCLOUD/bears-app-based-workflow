# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A seven-phase app workflow plugin that ships to two runtimes (Claude Code and Codex) from one repository. Canonical workflow state lives in a registered per-project SQLite database exposed through two stdio MCP servers, both started from the same single-file runtime:

- `app-workflow` - 12 read-only tools (`serve --mode reader`)
- `app-workflow-maintainer` - 13 registration/mutation tools (`serve --mode maintainer`)

The runtime is stdlib-only Python 3.10+; `git` must be on PATH for project registration. README.md is the authoritative spec for tool surfaces, limits, and phase semantics; contracts/ holds the DB schema and MCP tool contract.

## Commands

```bash
# The wave gate (stdlib unittest) - drives a full wave and lets the plugin judge itself
python3 -m unittest discover -s tests
python3 tests/test_wave_gate.py WaveGate.test_a_complete_wave_validates_and_audits

# Run an MCP server by hand
python3 scripts/app_workflow.py serve --mode reader      # app-workflow
python3 scripts/app_workflow.py serve --mode maintainer  # app-workflow-maintainer

# Read-only workflow validation
python3 scripts/app_workflow.py validate --project-ref <ref> --wave-id <id>
python3 skills/app-analyze/scripts/validate_workflow.py --project-ref <ref> --wave-id <id>

```

There is one test gate: `tests/test_wave_gate.py`. It drives a complete seven-phase wave through the real maintainer backends against a throwaway git project, then asserts only the plugin's own verdict via `workflow_validate` - a clean wave audits, an incomplete one is rejected, and on-disk file drift breaks the audit. Run it with unittest, never pytest (a stray `.pytest_cache/` is noise in the working tree). This gate deliberately does not check repository-artifact properties the runtime cannot see - the 80-file / 1 MiB budget, ASCII purity, manifest version sync, and the role allowlists (the L3-never-reaches-maintainer boundary) are no longer test-enforced; changing roles or manifests needs manual care.

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
| Roles       | claude/agents/*.md (generated)                  | agents/*.toml (generated)                           |
| Extras      | claude/hooks.json, claude/commands/, claude/workflows/ | -                                            |

skills/ (eight skills: one per phase plus subagents) is shared by both runtimes; skills/*/agents/openai.yaml files are Codex UI metadata only.

Roles are generated, not hand-written: `roles/roles.json` is the single typed source and `scripts/render_roles.py` renders both `claude/agents/*.md` and `agents/*.toml` (`--check` detects drift). Edit the IR, never the artifacts, and re-run the renderer. Three roles remain - app-worker (no MCP), app-reviewer and app-analyst (disjoint read-only subsets); the Codex-only repo-orchestrator and workflow-orchestrator lanes were retired in 0.7.0. `scripts/render_roles.py --check` detects drift between the IR and the artifacts, but nothing test-enforces the allowlists themselves - the maintainer-access boundary now rests on review, not CI.

Ownership: one orchestrator per repository - the main session owns the wave and both servers, and is the only writer. A second repository is a separate session with its own wave, not a delegated lane. `claude/workflows/app-wave.js` ships as a file and is invoked by path; plugin manifests have no `workflows` key, so it is deliberately unregistered.

### Releases and CD

- The version (currently 0.7.0) appears in scripts/app_workflow.py (`VERSION`, served as MCP serverInfo.version), .codex-plugin/plugin.json, .claude-plugin/plugin.json, and both marketplace.json files, and is asserted by tests - bump all of them together.
- The Codex installer (`install`), the self-hosted CD runner (`.github/runner`, `.github/workflows/plugin-marketplace-cd.yml`), and the committed `dist/` bundle were retired in 0.7.0: Claude Code installs plugins natively, and the runner was pinned to an operator Codex home that no longer exists. There is currently no CD.

## Repository rules (from AGENTS.md)

- All plugin instructions and documentation are English-only; README.md, CHANGELOG.md, THIRD_PARTY_NOTICES, and every skills/*/SKILL.md must be pure ASCII (test-enforced).
- Budgets are test-enforced: at most 80 working-tree files, 1 MiB total, 30 KiB per skill directory.
- Procedures belong in skills/, unique role behavior in agents/; workspace-level rules stay outside this repository.
