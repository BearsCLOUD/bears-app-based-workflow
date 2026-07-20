# Architecture

How this plugin is put together, and why. Written for someone about to change it.

README.md is the user-facing spec (tool surfaces, limits, phase semantics). This document covers the
parts you only learn by reading several files at once: where authority lives, which invariants are
load-bearing, and which sharp edges will bite you.

Status: current as of 0.7.0.

## Context and goals

The plugin runs a seven-phase workflow for building an application, and keeps canonical state in a
per-project SQLite database rather than in prose or scratch files. Its value is the combination of a
source-linked functional graph, an append-only process ledger, and an audit that binds a verdict to
an exact snapshot of both the database and the files on disk.

The 0.7.0 rework had one governing goal: **make the process a deterministic algorithm rather than a
recommendation.** Before it, phase order and gating lived in the prose of skills, which meant they
held only as long as a model followed instructions. Four consequences drove the redesign:

1. Enforcement sat in the wrong layer. The server enforced per-mutation invariants (compare-and-swap,
   digests) well, but not cross-record process invariants.
2. The runtime was coupled to Codex as a host, including a 5.7k-line installer and a self-hosted CD
   runner that published roles into an operator's Codex home.
3. Two hand-maintained role representations drifted against each other.
4. Determinism and content quality were tangled together in the same prose.

## The four layers

```
+- Layer 4: ENFORCEMENT - claude/hooks.json ------------------------+
|  PreToolUse: deny maintainer mutations lacking the CAS triple.    |
|  Stop/SubagentStop: refuse to end a turn on an inconsistent wave. |
|  Defense in depth. Not the primary barrier.                       |
+- Layer 3: ORCHESTRATOR - Claude ----------------------------------+
|  Main session: decisions, gates, routing. Sole holder of the      |
|  maintainer server. Writes every mutation from executor evidence. |
|  claude/workflows/app-wave.js encodes phase order and fan-out;    |
|  claude/commands/app-wave.md starts and resumes a wave.           |
+- Layer 2: EXECUTORS - Codex, two mechanics -----------------------+
|  codex mcp   - stateful MCP session, re-promptable via reply.     |
|                Reasoning phases: research, specify, graph,        |
|                plan, analyze, review.                             |
|  codex exec  - headless one-shot via scripts/codex_exec_bridge.py.|
|                Bounded implementation: brief in, diff out.        |
|  Neither can reach the maintainer server.                         |
+- Layer 1: SUBSTRATE - scripts/app_workflow.py --------------------+
|  Two stdio MCP servers from one stdlib-only file:                 |
|  app-workflow (12 read tools) / app-workflow-maintainer (13).     |
|  Graph + ledger + audit over per-project SQLite.                  |
+-------------------------------------------------------------------+
```

The single-writer rule is what makes the rest cheap. When exactly one actor mutates, whole classes of
state become unreachable rather than merely guarded: a cross-wave write, an unproven `audited`, and a
reopen bypass cannot be constructed, because nothing else holds a maintainer handle.

## Three integration mechanics

The interesting axis is not "which runtime hosts the plugin" but "how does work reach an executor".
There are three mechanics, and they differ in launch, sandbox, and result capture, so each is
integrated separately.

| Mechanic | What it is | Used for |
|---|---|---|
| Claude Code (host) | Plugin loads into Claude; main loop plus Workflow script; sole maintainer writer | All decisions, gates, mutations, audit |
| `codex mcp` | Codex as an MCP session in the tool layer; stateful, re-promptable | Multi-turn reasoning: research, specify, graph, plan, analyze, review |
| `codex exec` | Headless CLI one-shot in the shell layer, own sandbox and cwd | Bounded implementation under strong isolation |

`codex exec` is a distinct mechanic rather than "another subagent": it is configured by CLI flags, not
a subagent declaration; it is stateless, so iteration means a new call with a new brief; and its
evidence is captured from exit status, stdout, and a file diff rather than a returned message.
`scripts/codex_exec_bridge.py` is the wrapper. Two of its properties are security-relevant: caller
config overrides are denylisted so a `-c sandbox_workspace_write.network_access=true` cannot re-enable
network on a bridge whose contract says network is off, and changed-file evidence is computed from
content digests taken at the git root, because `git status --porcelain` alone cannot distinguish
"already dirty" from "the executor touched it again", and running it inside a subdirectory silently
misses edits elsewhere in the repository.

## State model

- `registry.sqlite3` maps stable `project_ref` values to absolute git roots. It lives in
  `$BEARS_APP_WORKFLOW_STATE_DIR`, else `$CODEX_HOME/state/bears-app-based-workflow/`.
- Per-project state is `<project>/.bears/app-workflow.sqlite3`. It never stores the absolute project
  path, so a project can move.
- Markdown phase artifacts live under `waves/<wave_id>/` in the target project: constitution.md,
  research.md, spec.md, functional-graph.md, plan.md, dev.md, analysis.md.
- JSON workflow-state fallbacks are forbidden. `project_migrate_json` imports the two legacy formats
  only into an empty database.

Schema is versioned. `SCHEMA_VERSION` is `app-workflow-db.v2`; a v1 database is migrated in place on
its first **writable** open by rebuilding the `tasks` table (dropping a table-level `UNIQUE` that made
task reordering impossible) and stamping the new version. Read-only opens never migrate.

## Integrity invariants

These are the ones that must not be weakened. Most live in `mutate_project`.

- **Every mutation is compare-and-swap guarded**: a unique `request_id`, an expected revision, and an
  expected logical digest. All of it runs in one `BEGIN IMMEDIATE` transaction, so a batch
  `graph_apply` or `plan_replace` commits or rolls back whole.
- **Replay is idempotent only for an identical payload digest.** Same `request_id` with the same
  payload returns the stored result verbatim; with a different payload it raises `REQUEST_ID_REUSED`.
- **Logical digest** is SHA-256 over sorted canonical rows, excluding the `request_log` and
  `audit_attestations` tables and the `revision` and `schema_version` rows of `metadata`. Excluding
  `schema_version` is what lets a migrating writable open avoid failing a caller's CAS, since the
  caller read its expected digest from a pre-migration read-only open.
- **Audit is snapshot-bound.** `workflow_mark_audited` revalidates at the same revision inside its own
  transaction, and every successful mutation unconditionally marks active attestations stale, so any
  later write invalidates the verdict as a side effect rather than as a separate check.
- **SQLite discipline**: foreign keys on, DELETE journal with WAL actively rejected, FULL synchronous,
  5s busy timeout, plus a pragma-drift check on every connection.
- **Graph records are retired, never deleted.** Entities, observations, and relations move
  active -> retired with an optional replacement ref; upserting a retired record is rejected; the
  relation set is closed at eight types. Note the scope: provenance rows and plan dependencies are
  replaced wholesale by design, and the registry row is deleted on unregister.
- **Response limits**: pages default 50 / max 200, traversal depth default 4 / max 16, requests 1 MiB,
  responses 512 KiB.

The reader/maintainer boundary is enforced at exactly one point: the `tools/call` branch of
`handle_rpc`. `execute_tool` does not re-check the mode, so that gate is load-bearing.

## Data flow of one wave

```
constitution -> research -> specify -> functional-graph -> plan -> dev -> analyze -> audited
```

For each phase the orchestrator reads current revision and digest from `project_status` on the
**reader** server (the maintainer server exposes no read tools), dispatches the thinking to an
executor, writes the artifact, then records the phase with the CAS triple. The dev phase fans out over
plan tasks: each task is implemented, its exact changed-file digest recorded, reviewed, corrected if
needed, and only reaches `done` on an approval at its current digest with no open corrections.
Analysis either records findings, which reopen the earliest affected phase and everything after it, or
records `ready`, after which the audit may be attested.

## Key decisions and trade-offs

**Determinism in control flow, quality in the leaf.** Phase order and gates are encoded in
`claude/workflows/app-wave.js`; what makes a good spec or a good graph stays with the executing model.
The cost is that the workflow script and the skills must agree, and the script is the authority.

**Single writer, at the cost of parallel wave ownership.** Delegated multi-repository lanes are gone;
multiple repositories mean multiple Claude sessions, each owning its own wave.

**One role source, rendered.** `roles/roles.json` is the typed source; `scripts/render_roles.py`
renders `claude/agents/*.md` and `agents/*.toml`, with `--check` for drift. History recorded real
drift between hand-maintained copies, which is why generation beats discipline here. Three roles
remain: `app-worker` (no MCP), `app-reviewer` and `app-analyst` (disjoint read-only subsets).

**Retiring the installer and CD.** Claude Code installs plugins natively, and the self-hosted runner
was pinned to an operator Codex home that no longer exists. Removing both freed roughly 30 files and
545 KB against a test-enforced 80-file / 1 MiB budget. The trade-off is real: **there is currently no
CD and no automated verification of merged changes.**

**Keeping two MCP servers.** The split is the security boundary that makes "executors cannot write"
expressible as tool access rather than as a rule to be followed.

## Sharp edges

Things that will surprise you, all verified against the source.

- **Phase order is not enforced server-side.** `phase_record` validates the phase name and the
  single-active-record rule; it does not check that the previous phase completed. Ordering is the
  orchestrator's job. This is deliberate, but it means a direct MCP caller can record out of order.
- **Two mutations settle a phase without a process record.** `plan_replace` sets `app-plan` to
  `completed` (`scripts/app_workflow.py:1118`) and `analysis_record` sets `app-analyze` to `ready`
  (`:1327`), neither writing `process_record_ref`. So phase status and process record are two truths
  that legitimately disagree. Any consumer deciding "has this phase been done" must consider both, or
  it will either re-run recorded work or wedge on a healthy wave.
- **`workflow_state` is one flattened, paged record stream.** Phases, process records, tasks, reviews,
  findings, corrections, and analyses share the same 50/200 page budget, so a single page routinely
  omits recorded phases. Page to exhaustion before concluding anything about a wave.
- **`current_phase` is nested** at `wave.current_phase`, not top-level.
- **There is no wave-listing tool.** `project_status` returns no waves and `workflow_state` requires a
  `wave_id`, so wave discovery goes through `waves/*/` on disk and is then confirmed against the
  database.
- **`record_ref` is globally unique.** Re-running a phase needs a fresh ref.
- **Registering a project writes to the target repository**: it appends sidecar rules to `.gitignore`
  and creates `.gitattributes`. The append is idempotent. A fresh project database is 192 KB, which
  matters here because this repository runs the workflow against itself and has a 1 MiB budget; that
  is why `.bears/`, `waves/`, and `.claude/` are excluded from the budget walk.

## Known debt

- `contracts/app-workflow-db-v1.sql` still carries the v1 filename while containing the v2 schema
  (`PRAGMA user_version = 2`). The path is hardcoded in `schema_sql()`, so renaming is a coordinated
  change.
- Error codes `PROJECT_MIGRATION_FOREIGN_KEY` and `REBIND_CANONICAL_DRIFT` are not yet in
  `contracts/app-workflow-mcp-tools.v1.json` or README.
- `claude/workflows/app-wave.js` is not yet referenced from `.claude-plugin/plugin.json`.
- The `codex exec` bridge and the workflow skeleton were built in parallel, before a prototype
  validated the orchestrator-to-executor brief format end to end. Treat their contract as provisional.
- No CD. Nothing verifies a merge beyond what a contributor runs locally.
