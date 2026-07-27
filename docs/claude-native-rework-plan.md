# App-workflow -> Claude-native rework plan (end-to-end)

Status: working plan (v1.2). Architecture on triple-mechanism model (Section 3.1); roles section enriched from repo history. English per the repo's AGENTS.md docs rule.
Date: 2026-07-20. Source: `/srv/bears/plugins/bears-app-based-workflow` + five subsystem audits + repo-history mining.

---

## 1. Goal and principles

Rework the seven-phase workflow plugin so the **process becomes a deterministic algorithm rather than a recommendation**, while preserving the plugin's unique value (functional graph + canonical SQLite state + exact-snapshot audit).

Governing invariants (every decision below follows from these):

1. **Claude is the sole orchestrator and sole writer.** Only the main Claude session calls maintainer-MCP, chooses routes, gates, and attests audit.
2. **Codex are the executors, through two distinct mechanics.** Almost all generative work (research, spec, graph population, implementation, analysis) runs through Codex, initiated by Claude. This is not one path but two, and both must be integrated (Section 3.1): `codex mcp` (MCP session with follow-up) and `codex exec` (headless CLI one-shot with its own sandbox). Executors have no maintainer-MCP access.
3. **Determinism lives in control-flow.** Phase order and gates are encoded in a Workflow script, not in the prose of skills. Content quality stays with the executing model - a deliberate boundary.
4. **Enforcement is at the harness layer** (hooks + tool allowlists), not only inside a passive server.
5. **Reuse the substrate, do not rewrite it** - but first fix four blocking defects (Tier A).

---

## 2. Why rework, not patches (audit summary)

Five audits (server core, installer, contracts/tests, process layer, CD) converged: **the deepest defects are a structural consequence of "advisory process + passive server"**, not point bugs.

Cross-cutting themes:

- **A. Enforcement in the wrong layer.** The server enforces per-mutation local invariants (CAS, digest) well, but not cross-record/process invariants (wave membership, phase order, "audit before done"). Hence the plan deadlocks, the audit bypass via empty `analysis_record`, and the cross-wave write. -> Removed by Workflow + hooks + single writer.
- **B. Atomicity breaks at resource boundaries.** A single DB is clean; the links registry-DB <-> project-DB <-> filesystem and SQLite <-> file hashes are not.
- **C. Over-engineering reduces safety** (the 5.7k-line installer creates its own crash states; the CAS/owner ceremony).
- **D. Test blind spots** exactly where prod degradation is invisible (concurrency, DB corruption, protocol).

Detailed findings in Sections 6-7. Conclusion: the substrate (server + graph + audit) is valuable and reusable; everything around it (installer, L1/L2/L3 hierarchy, CAS ceremony, prose-as-algorithm) is replaced.

---

## 3. Target architecture (4 layers)

```
+- Layer 4: ENFORCEMENT (hooks.json) --------------------------+
|  PreToolUse: maintainer mutations only from the orchestrator,|
|  with a valid request_id; Stop/SubagentStop: no phase left   |
|  in an inconsistent state.                                    |
+- Layer 2: ORCHESTRATOR = Claude -----------------------------+
|  main loop (decisions, gates) + Workflow script (7-phase     |
|  skeleton, dev-task fan-out, resume from SQLite). Sole holder |
|  of maintainer-MCP. Writes mutations from executor evidence. |
+- Layer 3: EXECUTORS = Codex, TWO mechanics ------------------+
|  (2) codex mcp / codex-reply - MCP session, follow-up        |
|      (research/specify/graph/analyze/review)                 |
|  (3) codex exec - headless CLI one-shot, own sandbox         |
|      (dev; workspace-write, network off)                     |
|  No maintainer access. Full standalone brief + graph slice.  |
+- Layer 1: SUBSTRATE = thin SQLite-MCP -----------------------+
|  graph + ledger + audit. Reader (12) / maintainer (13).      |
|  Cleaned of Codex coupling and Tier-A bugs; CAS ceremony     |
|  reduced to a cheap revision integrity check.                |
+--------------------------------------------------------------+
```

Key consequence of the single writer: **cross-wave leak, unproven `audited`, and the reopen bypass become unreachable states**, not "fixed" ones - nothing can construct them.

### 3.1. Three integration mechanics (triple, not dual)

The earlier open question ("dual-runtime: Codex-host + Claude-host, or Claude-only") was the wrong axis. The correct model is **three integration mechanics, each integrated separately**, because they differ in launch, sandbox, and result capture:

| # | Mechanic | What it is | Role in the workflow |
|---|---|---|---|
| 1 | **Claude Code - orchestrator/host** | plugin loads into Claude; main loop + Workflow script; sole maintainer-MCP writer | makes all decisions, gates, writes mutations, attests audit |
| 2 | **codex mcp** (`mcp__codex__codex` / `codex-reply`) | Codex as an MCP session in the tool layer; stateful, re-promptable via reply; Codex uses its own tools | reasoning phases: research, specify, functional-graph, plan, analyze, review |
| 3 | **codex exec** | headless CLI one-shot via shell-out; stateless; own sandbox/flags/auth; result parsed from stdout | bounded implementation (dev): "task in -> diff out" under strong isolation |

**Why codex exec is a distinct mechanic, not "another subagent":**
- lives in the shell layer (Bash `codex exec ...`), not the tool/MCP layer; configured by CLI flags (`--sandbox`, `--cd`, model, effort, network), not a subagent declaration;
- stateless one-shot: no session, no `reply`; re-iterate with a new call and a new brief;
- own sandbox and working directory (isolated from Claude's cwd and state); own evidence capture (stdout + changed files), own timeout/error handling;
- needs a thin orchestrator-side wrapper (see Section 9, "codex exec bridge").

**When to use which:** `codex exec` when you need strong sandbox isolation and a clean "task->diff" (dev workers, mechanical edits to an exact brief); `codex mcp` when you need multi-turn reasoning, clarification via `codex-reply`, or the executor to use tools interactively (research/analyze/review with a second pass).

**Legacy axis (separate):** the original plugin still loads under Codex CLI as host. That is now a secondary legacy path; its fate (keep advisory skills as a cheap Codex-host fallback vs retire) is a smaller decision, deferred to Section 13. The "triple" above is the go-forward, Claude-orchestrated architecture.

---

## 4. Roles and executor dispatch

**Central lesson from repo history** (three role eras: a governance plugin of ~59 profiles with a deterministic router -> static TOML 52->9->11 -> rendered-JSON roles -> the final 5 static TOML): **roles were never generated per task.** The working recipe, carried over:

- **Role definition** - stable: "who and what may" (specialization + authority_kind + sandbox + tools + MCP + output shape).
- **Assignment packet** - dynamic: "what exactly to do now" (target paths, snapshot, allowed/forbidden actions, completion criteria, expected result).
- **Launcher / binding** - technically links the two and PROVES the chosen profile holds exactly that authority (packet.role/kind matches the profile identity line; instruction_refs include the exact installed profile; PACKET_REJECTED on mismatch; fork with no inherited chat).

Reusability = **one static role launched many times with different typed packets**, not cloning/re-rendering a role. The earliest era is the exemplar: `roles[]` (50 stable roles) x `platform_parts[]` (215 concrete areas, each with its own write_roots/trust_boundary/validations) - one worker served many parts. Auto-spawning "bonus" experts was explicitly forbidden; extra work = a new bounded assignment.

**Four entities, carried over separately (rec. C1):** Role definition / Assignment class (work type, target patterns, risks, required evidence) / Runtime assignment (concrete target) / Launch profile (Codex sandbox/MCP/tools/network/output-schema).

**Authority derives from role_kind, not specialization and not level.** role_kind matrix: `orchestrator` (here: Claude), `mutation-worker` (workspace-write, only assigned targets, one committed result), `primary-critic` (judge an immutable scope, no mutations), `helper`/`reader`/`researcher` (one read-only fact/slice). Calling a helper a "security expert" grants no rights.

**Base Claude-native roles (a small set of role KINDS, not micro-profiles):**
- `app-worker` - mutation-worker: Edit/Write/Bash, no MCP -> codex exec.
- `app-reviewer` - primary-critic: read-only + reader MCP, bound to `change_digest` -> codex mcp.
- `app-analyst` - reader: read-only + reader MCP, bound to revision/digest -> codex mcp.
- Specialization comes through the assignment, not through new role files.

**Security - lesson of `c9864b1`:** the dedicated security-critic was removed not because security is unneeded, but because it was folded into a SINGLE primary-critic mandated to cover trust/secret/identity/authorization/ingress/promotion boundaries. Rule: never keep two critics over one acceptance surface. -> In Claude: security/perf are mandatory sections of the `app-reviewer` checklist, not separate roles; add a separate role only when a genuinely independent acceptance surface appears.

**Dynamic dispatch (role-selector, rec. C3):** Claude *proposes* a role semantically, but the launcher *independently* verifies: normalize the task into a packet -> filter roles by hard authority/capability constraints -> pick the narrowest match -> 0 = `ROLE_GAP`, several equal = `ROLE_SELECTION_CONFLICT` -> bind the ID to the exact profile/digest -> hand off a bounded packet with no inherited chat. Claude picks from an ENUM; it cannot turn a generic worker into a specialist via prose. (Ports the early `route_target()` logic: exact-match, `parent_only`/`ambiguous_owner`, `broad_fallback=false`.)

**Coverage gate (rec. C4):** before launching, build a coverage matrix over ALL plan assignments: each atomic assignment has exactly one primary; a reviewer does not replace a primary; a mutation does not start on gap/conflict; role-ID matches profile-digest. On a gap, return a packet (missing_work_type, target_scope, required_role_shape, blocked/allowed actions) - do not auto-create a role.

**Claude<->Codex sync (rec. C2) - directly relevant to us:** `claude/agents/*.md` are currently hand-authored separately from `agents/*.toml`. History explicitly warns that maintaining two representations by hand drifts (a real case: a JSON profile said `gpt-5.4-mini` while its TOML said `gpt-5.5`). Solution - a **single typed source (IR) + build-time rendering of both artifacts** (revive the `role_renderer.py` idea), not two hand-maintained copies. Render at build time, not per task. Interim: `tests/test_claude_plugin_shape.py` cross-checks the allowlists - keep it until the renderer exists.

**Fallback (rec. C5):** availability-fallback only if authority DECREASES (no generic fallback for security/deploy/credential/production/mutation - only `ROLE_GAP`); separately, quality-degradation (invalid-output/timeout/scope-violation -> fresh-session/smaller-assignment/reduced-context/manual-review; never auto-escalate permissions).

**Do not port:** 50+ technology micro-profiles; runtime role creation; `task_name` as a selector; mixing identity and scope; implicit inherited context; duplicate critics; the heavy `$CODEX_HOME` receipt/CAS layer (roles live inside one Claude plugin); `role-profile-architect` as an auto-launched role on `ROLE_GAP`.

History reference commits: `d3e4282` (governance init), `7389ea2` (teardown -> rebuild), `36941b2`/`4052af4`/`8eda10e` (52->9 + nine-profile dispatch), `8693f2a` (JSON-rendered), `bd86941` (profile-bound dispatch), `53dccd4` (role-kind authority), `c9864b1` (security-critic removal), `b8dfabc` (-> 5 static TOML). Best single example of a full rendered profile: `git show b8dfabc^:agents/app-worker.toml`.

---

## 5. Phase map (who / mechanic / tier)

| Phase | Who | Mechanic | Codex tier |
|---|---|---|---|
| constitution | Claude | registration + decision (maintainer-MCP) | - |
| research | Codex | codex mcp | terra |
| specify | Codex | codex mcp | terra/sol |
| functional-graph | Codex proposes delta -> Claude applies | codex mcp -> maintainer | sol |
| plan | Codex -> Claude applies `plan_replace` | codex mcp -> maintainer | terra |
| dev (per task) | Codex | codex exec (sandbox, network off) | terra; sol for subtle |
| review of a task | Codex or Claude (cross-family) | codex-review / Claude gate | terra |
| analyze | Codex -> Claude records + attests | codex mcp deep -> maintainer | sol |
| record / gate / audit | Claude | maintainer-MCP | - |

Linear early phases run in Claude's main loop; the dev-heavy fan-out runs in a Workflow script (`pipeline()` over independent tasks, each: codex exec -> review -> return evidence -> orchestrator records). Do not force everything into one mechanism.

---

## 6. Substrate: keep / fix (Tier A) / simplify

**Keep as-is (valuable, no Claude equivalent):** the functional graph (source-linked entities/relations, impact/dependency/trace), SQLite as the single source of truth (enables cross-session resume), exact-snapshot audit, split read/maintainer.

**Fix before reuse (Tier A - blocking, all confirmed by reading code):**

| # | Defect | Location | Fix |
|---|---|---|---|
| 1 | `plan_replace` cannot replan/reorder (full `UNIQUE(wave_id,sequence)`, retire keeps sequence) | `app_workflow.py:965-984`, schema `:107` | partial index `WHERE record_status='active'`; two-phase reorder (temporary negative sequence) |
| 2 | `audited` not atomic with files; survives drift | `:1210-1359`, `:1388-1429`, `:1680-1682` | bind audit to a git tree/commit or open fds; exclude the project DB by inode; re-verify the snapshot when reporting `audited` |
| 3 | Cross-wave write via a foreign `task_ref` | guard `:575-599` vs backends `~:1017/1049/1103` | verify `record.wave_id == args.wave_id` in the task/review/correction backends |
| 4 | `rebind` rolls state back; register/rebind not cross-DB atomic | `:644-693`, `:362-423` | require an existing binding + compare the current canonical DB's CAS; saga verifying the actual binding on replay (or a single transaction via `ATTACH`) |

**Simplify (consequence of the single writer):**

- Drop the owner_session/CAS ceremony - with one writer, optimistic concurrency is unnecessary; keep a cheap revision integrity check.
- Enforce the declared inputSchema server-side (`:2166-2181`, before backend) - `maxItems` and types are unchecked today, and extra fields leak into the idempotency digest so an identical request counts as new (a real correctness bug).
- Reader reads a single snapshot: an explicit `BEGIN` per reader (`:151/154` is autocommit today) - needed for "read at revision" in the phases.
- Untrusted-input robustness (process crash on `AttributeError`/`RecursionError` `:2203-2206`, forgeable cursor `:1436`, response doubling `:2117-2123`, non-progressing cursor `:1460-1465`, unbounded read `:2194-2197`) - lower severity now that the client is Claude, but cheap to fix alongside.

**Env:** keep `BEARS_APP_WORKFLOW_STATE_DIR` (done) as the primary registry path; `CODEX_HOME` is the dual-runtime fallback.

---

## 7. What to remove

- **`install` (5.7k lines, 202 KiB)** - not needed in Claude at all (native marketplace). Its critical bug (config.toml loss on `kill -9`) and all its over-engineering go with it.
- **The L1/L2/L3 hierarchy** (`workflow-orchestrator`, `repo-orchestrator`) - replaced by native subagents and Workflow orchestration; multi-repo delegated mode = separate Claude sessions.
- **Prose-as-algorithm** - skills demote to an "entry point" and "how to think about the phase"; sequencing authority moves into the Workflow script.
- **CD `.github/runner/bears_deploy/*` (~250 KiB)** - defer (Section 12); porting = 2 Large (marketplace adapter, role/config publication) + 2 Medium (provisioning, verification) workstreams.

Process-layer deadlocks/bypasses (dependency-vs-sequence, reopen-vs-immutable, audit bypass) must NOT be fixed in skills - they vanish under the deterministic engine.

Removing `install` and the CD runner frees the bulk of the repository budget (see Section 13), which the Claude-native components then reuse.

---

## 8. Enforcement (hooks)

The Claude plugin can ship `hooks.json` (plugin agents cannot carry hooks, but the plugin can):

- **PreToolUse on `mcp__...maintainer__*`** - defense-in-depth: reject a mutation without a valid `request_id`/expected shape. (The primary single-writer barrier is that subagents are simply not granted the maintainer tool; the hook is a second line. Wave-membership stays server-side, Tier A #3.)
- **Stop / SubagentStop** - do not end the turn if the Workflow left a phase inconsistent (no process record at `current_phase`, open corrections at audit time).
- **PostToolUse (optional)** - after `task done`, verify the review gate passed.

---

## 9. Work plan by phase (end-to-end)

**Phase 0 - Prototype (vertical slice).** register -> one dev task -> audit. Validates at once: the Claude->Codex brief contract, the single-writer invariant, the cost/latency of one `codex exec` cycle, and **builds a minimal codex exec bridge**. Also touches Tier-A #2 (audit atomicity) and #4 (register cross-DB). Avoids `plan_replace` (no replan). *Acceptance:* the full cycle passes, `codex exec` returns evidence, Claude records and attests, cost measured.

**Phase 1 - Substrate hardening.** The four Tier-A fixes + the Section 6 simplifications + tests for the blind spots (Section 11). *Acceptance:* `plan_replace` reorders and reuses a sequence; `audited` invalidates on file drift; cross-wave writes are rejected; new tests green.

**Phase 2 - The two executor mechanics (Section 3.1).** Bring both legs to production: (2) **codex mcp** dispatch (Task/Agent with type codex, structured-output schemas, `codex-reply` for a second pass); (3) **codex exec bridge** - orchestrator-side wrapper: sandbox flags (`--sandbox`, `--cd`, network off), brief passing (argv/stdin), changed-file + exit capture, timeouts, isolation from Claude's cwd/state, per-assignment `base-instructions` rendering. *Acceptance:* both mechanics run a bounded assignment and return structured evidence; codex exec is isolated (no maintainer-MCP, does not touch Claude state).

**Phase 3 - Orchestrator + Workflow skeleton.** Seven phases as deterministic stages; dev fan-out via the codex exec bridge (Phase 2); resume from `workflow_state`. *Acceptance:* a full seven-phase run on a toy git repo; `audited` only after a real `workflow_validate`.

**Phase 4 - Role library + dynamic dispatch.** A typed role IR + build-time renderer (one source -> `claude/agents/*.md` + Codex profiles, ending hand-maintained drift, rec. C2); base mechanism-agnostic roles; the briefer; the role-selector (enum + independent verification, rec. C3); the coverage gate (rec. C4). *Acceptance:* one base role reused across >=2 assignments with different scope via both mechanics; least-privilege verified empirically (as already done for `app-reviewer`); the renderer emits both runtime artifacts from one source and a drift check passes.

**Phase 5 - Enforcement hooks.** `hooks.json` + the Section 8 checks. *Acceptance:* an injected violation (maintainer mutation from the wrong context / without request_id) is blocked.

**Phase 6 - Interface.** A `/app-wave` skill/command (start/resume, reads state from SQLite). *Acceptance:* `kill` mid-wave -> `/app-wave` continues from the same phase.

**Phase 7 - Docs, versions, migration.** Bump the version (Section 12), close Unreleased, migrate from 0.6.0 via the existing `project_migrate_json`. *Acceptance:* a 0.6.0 DB opens and requires a re-audit.

**Deferred - CD port** to the Claude marketplace (provider layer, Section 7).

Critical path: Phase 0 -> 1 -> 2 -> 3. Phases 4-6 partly parallelize after Phase 3.

---

## 10. Prototype (Phase 0) - detail

1. Claude registers a wave on a test git repo (`project_register` + `wave_initialize`, maintainer-MCP).
2. Claude sets one bounded dev task and forms a full brief (target files, expected result, graph slice - minimal graph for the prototype).
3. `codex exec` in a sandbox (workspace-write, network off) implements it and returns exact changed paths + evidence.
4. Claude reviews at the gate (cross-family) and records `task_record_change` + `review_record` to maintainer-MCP.
5. The PreToolUse hook confirms: the write came only from the orchestrator context with a valid request_id.
6. Claude runs `workflow_validate` -> `workflow_mark_audited`.

Measure: tokens/latency of the full `codex exec` cycle, brief completeness (how many clarifications were needed), whether Tier-A #2/#4 bite on a live task.

---

## 11. Test strategy (close the audit blind spots)

Priority (from the contracts/tests audit): concurrent mutations (two writers), a corrupted DB (`integrity_check`), invalid JSON-RPC (parse error / unknown method / bad cursor / deep nesting), the `MAX_RESPONSE_BYTES` boundary, `limit`/`max_depth` bounds, CAS for each of the 13 maintainer tools, `plan_replace` rollback, migration into a non-empty DB, cross-wave rejection. All stdlib unittest, in the style of `tests/test_app_workflow.py`. Delegating to Codex: use `base-instructions` (works around the testing prohibition).

---

## 12. Versioning and migration

- Claude artifacts are currently tagged `0.6.0` but sit in CHANGELOG under Unreleased, while the released `dist/` bundle 0.6.0 does not contain them. **Decision:** bump to `0.7.0` and include `claude/` + `.claude-plugin/` in the release; close Unreleased. Per CLAUDE.md, the version appears in both plugin.json files, both marketplace.json files, and the dist/ filenames, and is test-asserted - bump all together and regenerate dist/.
- State migration: `project_migrate_json` already imports the v5 map and v1 state into an empty DB with a parity check -> reuse it; a re-audit is required after migration.
- Metadata nits: align `category` casing, `keywords`, and descriptions across manifests.

---

## 13. Constraints, risks, open questions

- **Repository budget (test-enforced).** `test_repository_limits_and_artifact_language` caps the working tree at 80 files / 1 MiB and requires ASCII for README/CHANGELOG/THIRD_PARTY_NOTICES/`skills/*/SKILL.md`. The repo is at 79/80 files and ~953 KiB - one file from failure. The rework adds files (hooks.json, codex exec bridge, role IR + renderer, Workflow script, tests). But the budget is dominated by Codex machinery the rework removes: `install` (202 KiB), `.github/runner` CD (~250 KiB), `dist/` (162 KiB). **Plan:** raise the cap deliberately (it is the plugin's own test) and/or split the Codex-only installer/CD out as they retire; net, Claude-native frees budget. This doc is English to satisfy the same rule.
- **Cost/latency of two executor mechanics** at scale, and a double integration surface (codex exec bridge + codex mcp). Mitigation: a shared mechanism-agnostic role-render layer (Section 4) so only transport differs; parallelize independent tasks (`pipeline()`); use sol only for subtle work; Claude does trivia itself.
- **Fate of the legacy Codex-host.** The triple (Section 3.1) closes the go-forward question: Claude orchestrator + codex mcp + codex exec. The smaller remaining decision - keep the original Codex-host plugin as a cheap advisory fallback or retire it. Recommendation: keep until the Claude path stabilizes. Needs confirmation.
- **Graph auto-population vs quality** - risk of a noisy graph; needs a graph critic in the analyze phase.
- **Brief completeness** - a burden on the orchestrator (Codex sees no Claude context); validated in Phase 0.
- **Determinism boundary** - control-flow only; leaf quality stays with Codex.
- **Specialist critics** (security/perf) - do not reintroduce as separate roles by default; history folded them into one primary-critic (Section 4). Add one only for an independent acceptance surface.

---

## 14. Recorded decisions

- **Triple, not dual (Section 3.1):** three integration mechanics - Claude orchestrator + `codex mcp` + `codex exec` - each integrated separately; `codex exec` is its own mechanic (own sandbox/launch/capture), not "another subagent". The legacy Codex-host is a separate, secondary axis.
- **Roles = stable authority profiles x dynamic assignment packets; no per-task role generation.** Reuse via many typed packets against one static role; a single typed source + build-time rendering keeps Claude and Codex representations in sync.
- All plugin-related material lives inside the plugin repository (this plan is in the plugin's `docs/`), English per the repo rule.
- Claude = sole orchestrator and sole writer; Codex = executors through two mechanics.
- Drop the L1/L2 hierarchy in Claude; delegated multi-repo = separate sessions.
- Two MCP servers are retained (topology parity, security boundary).
- The substrate is reused after the Tier-A fixes; the installer and CD runner are removed/deferred.
