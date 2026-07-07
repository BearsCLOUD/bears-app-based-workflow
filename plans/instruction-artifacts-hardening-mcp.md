# Instruction Artifacts MCP + Instruction Hardening Plan

## Objective

Connect the plugin-owned `instruction_artifacts` MCP scanner to the `instruction-hardening` skill so Bears instruction refactors start from bounded MCP evidence, not from instructions as source of truth.

## Target

- target_layer: plugin
- owner role: `bears-instruction-hardening-engineer`
- owner surface: `central_plugin_config`
- repo: canonical `@Bears` checkout
- MCP source: `src/bears_workflow/instruction_artifacts/`
- skill source: `skills/instruction-hardening/`

## Required invariants

1. Every hardening graph has `decision`, `live_confirmation`, `standardization`, `dependency_decision_refs`, and `escalation_candidate`.
2. Operator decision priority is highest.
3. Instructions are scanned evidence only: `source.instructions_source_of_truth=false`.
4. `decision.status=present` comes only from accepted `decision_ledger` records that match graph paths.
5. `live_confirmation.status=confirmed` comes only from decision-ledger live evidence inside the graph.
6. Dependency-owned Kubernetes, deploy, runtime, secret, CD, Dagger, workflow, and role-policy changes escalate to the higher owner.
7. `app-functional-graph` is a workflow pattern only: exact refs, dependency edges, status fields, evidence refs. It is not a plugin authority or validator.
8. Tests, validators, schemas, lint, route/audit, and static checks are safety evidence only, not instruction completion proof.
9. Every Git-tracked change ends with local commit in the owning repo; inspect autoCI/local commit validation for known errors before push.
10. Broad all-instruction refactors use MCP `surface_summary` and `instruction_surfaces[]` for the surface queue instead of shell-only inventories.

## Current MCP evidence

Command:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Current result:

- `decision.status=present`
- `decision.source=decision_ledger`
- `decision.decision_id=D-2026-07-06-instruction-hardening-mcp-evidence-plumbing`
- `live_confirmation.status=confirmed`
- `standardization.status=partial`
- `escalation_candidate.status=required`
- `source.instructions_source_of_truth=false`
- `source.decision_source=decision_ledger`

## Completed phases

### Phase 1: MCP connection

Status: complete.

Evidence:

- `instruction_hardening_startup` and `instruction_hardening_graphs` exist.
- Every enriched graph has `decision`, `live_confirmation`, and `standardization`.
- Skill and prompt catalog route instruction refactors through the hardening MCP.

### Phase 2: Decision dependencies and escalation

Status: complete.

Evidence:

- Graphs include `dependency_decision_refs[]`.
- Graphs include `escalation_candidate`.
- Escalation terms cover Kubernetes, deploy, runtime, secret, CD, `local_cd`, Dagger proof, workflow policy, role policy, and cross-owner instruction evidence.

### Phase 3: Full plugin-owned instruction refactor

Status: complete.

Approved by no-fork `gpt-5.5` high critic `019f39b7-8bea-7c13-9750-f47348ddcb6d` with required edits recorded here.

Friction audit source: no-fork `gpt-5.5` medium auditor `019f39b5-5141-7622-b47f-5dce14ac5f7f`, verdict `CUT_REQUIRED`.

Allowed same-owner files:

- `plans/instruction-artifacts-hardening-mcp.md`
- `skills/instruction-hardening/SKILL.md`
- `docs/reference/instruction-artifacts-mcp.md`
- `agents/bears-instruction-hardening-engineer.toml`
- `AGENTS.md`
- `skills/app-functional-graph/SKILL.md`
- `skills/app-dev/SKILL.md`
- `skills/app-dev/references/github-project-issue-flow.md`
- `skills/app-plan/SKILL.md`

Allowed cuts:

- duplicate workflow prose;
- manual validation/test/PASS wording;
- route/audit command wording where computed owner and expected autoCI status are enough;
- role/SKILL archive duplication that does not feed scanner standardization;
- app-* ceremony that does not own live/deploy proof.

Forbidden cuts:

- secret/raw-log/raw-chat/production-data bans;
- no-manual-tests/validators/route-audit bans;
- Git closeout rules;
- `kubernetes_deployment`, `local_cd`, Dagger ObjectiveRuntimeProof, Infisical custody, and dependency-owner escalation;
- any wording that makes `app-functional-graph` a plugin validator or authority.

`escalation_candidate.status=required` allows app-* skill edits only when they preserve deploy/runtime/secret/CD/Dagger ownership and only cut duplicate or manual-validation wording.

### Phase 4: Final consistency confirmation

Status: complete.

Final no-fork critic `019f39c5-af4b-7d23-b188-819be4d03122` confirmed the implemented MCP scanner/skill/role goal from current repo evidence, not from operator claims.

### Phase 5: All-instruction refactor queue

Status: in progress.

Current change extends the hardening packet with:

- `surface_summary`;
- `instruction_surfaces[]`;
- counts for total and returned instruction surfaces;
- bounded startup truncation across docs, graphs, and instruction surfaces.

Use this MCP-backed queue for the active broad objective: refactor all Bears instruction surfaces in owner-safe waves. Do not treat the queue as authority; it is evidence for picking the next same-owner edit wave.

### Phase 6: Skill instruction wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_graphs --root . --bounded-json --max-output-bytes 500000
```

Wave scope:

- `skills/*/SKILL.md` activation lines;
- app workflow plugin-target lines;
- selected deploy, Kubernetes, Infisical, Secret Factory, Codex health, and role-governance wording lines.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.skill`: `176 -> 82`;
- critic `019f3b88-c177-71a0-83db-a4cc0b406670` re-audit verdict: `PASS`, `required_fix_before_commit=no`;
- no catalog, role TOML, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations;
- remaining high counts include intentional grammar/list terms inside `skills/instruction-hardening/SKILL.md` and metadata/contract keys that may need a later schema-aware wave.

## Current status

- phase_1_minimal_mcp_connection: complete
- phase_2_decision_dependencies_escalation: complete
- phase_3_full_plugin_instruction_refactor: complete
- phase_4_final_consistency_critic: complete
- phase_5_all_instruction_refactor_queue: in_progress
- phase_6_skill_instruction_wording_wave: complete
- current_mcp_tool_gap: current Codex toolset exposes MCP registration through `codex mcp get mcp` but no callable `instruction_hardening_startup` namespace in this turn; use the documented stdio MCP helper as evidence.
- full_goal_complete: not_complete_for_all_instruction_refactor

### Phase 7: Role profile wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `agents/*.toml` developer-instruction prose only;
- stale manual route/audit command wording;
- stale `Use nearest AGENTS` / `touching files` wording;
- stale closeout fields that asked for route/audit or safety-check commands instead of expected CI/LCV status names and safety evidence refs.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `289 -> 176`;
- eliminated the scanned stale patterns: `Role override: Use for`, `Use nearest AGENTS`, `before touching files`, `route/audit commands`, `Use BLOCKED only`, manual route/audit command instructions, and `route/audit result` closeout wording;
- preserved role TOML metadata keys, model fields, sandbox fields, and role section headings;
- no catalog, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic result:

- Re-audit critic `019f3b92-de27-7440-bffe-d673b0f98bc5` verdict: `PASS`, `required fixes before commit: none`.
- PASS was based on current repo evidence: MCP queue exists, role wave uses that queue, stale manual command wording is removed from changed role instructions, duplicate route/audit status wording is fixed, and broad all-instruction refactor remains open.

### Phase 8: Reference documentation wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- selected `docs/reference/*.md` prose lines surfaced by `instruction_surfaces[]`;
- weak action words in human-readable governance docs;
- stale manual validation/test wording in `docs/reference/git-discipline.md`.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.reference`: `67 -> 24`;
- changed 22 reference docs with prose-only wording cuts;
- command names and script examples were preserved unless surrounding prose was stale;
- Git closeout prose now states autoCI and local commit validation own validator, test, lint, schema, and route/audit execution, with manual suites forbidden unless the operator names one exact command;
- no catalog, role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves the reference-doc slice advances the active goal through the MCP queue, removes weak/stale wording without changing command semantics, preserves closeout/secret/deploy/runtime safety, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `PASS`, blockers: none.
- PASS was based on current repo evidence: MCP/helper path remains active, 22 changed reference docs were counted, stale manual validator/test/route-audit wording was removed from the changed files, and the slice did not mutate executable/product/runtime/deploy/Kubernetes/secret-custody files.

### Phase 9: Skill portability and wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- selected `skills/*/SKILL.md` files surfaced by `instruction_surfaces[]`;
- portable command/path wording in skill instructions;
- weak action words in skill activation, command, and report rules.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.skill`: `82 -> 54`;
- changed 6 skill files with instruction-only wording cuts;
- removed server-specific absolute plugin paths from the changed skill instructions;
- converted helper command examples to relative plugin-root or skill-directory commands;
- preserved secret safety, dry-run DNS behavior, app graph validation ownership, GitHub Project boundary, and plugin update CI/local-commit ownership;
- no catalog, role TOML, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this skill slice advances the active goal through the MCP queue, improves portability/wording without changing command semantics, leaves manual validator/test execution under exact operator-named command or automatic CI/local commit validation, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` initial verdict: `FAIL` for an ungated Yandex360 local guardrail validator command.
- Fix applied: `skills/yandex360-dns/SKILL.md` now gates `python3 scripts/validate_yandex360_dns_cutover.py` behind an exact operator-named command or automatic CI/local commit validation ownership.
- Re-audit verdict: `PASS`, blockers: none.

### Phase 10: Workflow wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `workflows/bears-sdd/workflow.yml` gate messages and input prompt text;
- `workflows/auth-gateway-deploy-core/workflow.yml` comments only;
- command ids, command names, route targets, validator fields, and workflow structure were preserved.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.workflow`: `7 -> 2`;
- changed 2 workflow files with wording-only edits;
- remaining workflow weak terms are command/id tokens such as `bears.governance.check`, `speckit.checklist`, and `governance-check`, not prose instructions;
- no catalog, role TOML, skill, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this workflow slice advances the active goal through the MCP queue, reduces prose weak terms without changing workflow command semantics, preserves validation ownership, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `PASS`, blockers: none.
- PASS was based on current repo evidence: MCP/helper path is recorded, workflow weak terms are `7 -> 2`, diff changes only prompt/message/comment text, workflow command semantics and validation ownership are preserved, and the broad all-instruction goal remains open.

### Phase 11: Small catalog wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `assets/catalog/github-project-subagents.v1.json` value text only;
- `assets/catalog/session-workers-runtime.v1.json` value text only;
- JSON keys, ids, command names, schema names, roles, lane names, status names, and file paths were preserved.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `147 -> 139`;
- changed 2 catalog files with value-only wording edits;
- preserved L2 reuse/attach semantics, runtime-proxy guard, parent gitflow handoff requirement, session lane ownership, capacity fallback evidence requirements, and GitHub metadata mutation boundary;
- no role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this catalog slice advances the active goal through the MCP queue, reduces catalog prose weak terms without mutating schema/key/command semantics, preserves validation and GitHub metadata boundaries, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `PASS`, blockers: none.
- PASS was based on current repo evidence: MCP/helper path is recorded, catalog weak terms are `147 -> 139`, diff changes only JSON string values, key/id/command/schema/role/lane/status/path semantics are preserved, and the broad all-instruction goal remains open.

### Phase 12: Plugin router wording wave

Status: complete.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `AGENTS.md` prose-only wording in entity terms, functional map, runtime boundary, role activation, and entity-term rules;
- exact required fragments and policy boundaries were preserved.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.agents_router`: `8 -> 2`;
- changed only the plugin router file plus this plan evidence;
- remaining grep hits are entity words or exact required phrases such as `checkout`, `tool use`, `checks`, and `must use English only`;
- no catalog, role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this router slice advances the active goal through the MCP queue, reduces router weak terms without moving policy out of owner surfaces, preserves exact language/closeout/deploy/secret boundaries, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `PASS`, blockers: none.
- PASS was based on current repo evidence: MCP/helper path is recorded, router weak terms are `8 -> 2`, diff changes only plugin router prose plus plan evidence, owner routing and closeout/deploy/secret/runtime/validation boundaries are preserved, and the broad all-instruction goal remains open.

### Phase 13: Reference residual wording wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `docs/reference/agent-registration-sync.md` prose labels around drift packet wording;
- `docs/reference/github-project-subagents.md` lane wording and autoCI evidence label;
- `docs/reference/secret-factory.md` Infisical writer wording;
- command names, command examples, GitHub Check terms, validator ownership, secret-custody rules, and provider routing were preserved.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.reference`: `26 -> 24`;
- changed 3 reference files with wording-only edits;
- remaining reference weak terms include command names, GitHub Check terms, exact CI-required fragments, or technical phrases such as process memory;
- no role TOML, skill, catalog, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this reference slice advances the active goal through the MCP queue, reduces reference weak terms without changing command semantics, GitHub Check terminology, validation ownership, secret custody, provider routing, or broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files match the 3 reference docs plus plan evidence, MCP/helper path is active, reference weak terms are `26 -> 24`, diff is wording-only, command examples/GitHub Check terminology/validation ownership/secret custody/provider routing are preserved, and broad all-instruction goal remains open.

### Phase 14: Reference low-risk prose residual wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `docs/reference/capability-governance-rules.md` weak prose around validators and typed packets;
- `docs/reference/file-context-index.md` AST extraction wording;
- `docs/reference/governance-drift-summary.md` drift-summary weak prose;
- `docs/reference/roadmap-issue-coverage.md` issue metadata gate wording;
- `docs/reference/workspace-hygiene.md` closeout heading wording;
- command examples, command names, issue ids, exact required fragments, validation ownership, and historical drift ids were preserved.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.reference`: `24 -> 19`;
- changed 5 reference files with wording-only edits;
- remaining reference weak terms are command names, GitHub Check terms, exact CI-required fragments, process-memory technical phrases, or historical evidence text;
- no role TOML, skill, catalog, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this reference slice advances the active goal through the MCP queue, reduces reference weak terms without changing command semantics, validation ownership, historical drift identifiers, safety bans, or broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files match the 5 reference docs plus plan evidence, MCP/helper path is active, reference weak terms are `24 -> 19`, diff is wording-only, command names/examples, validation ownership, historical drift identifiers, and safety bans are preserved, and broad all-instruction goal remains open.

### Phase 15: Role scanner metadata exclusion wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `src/bears_workflow/instruction_artifacts/application/zones.py` role TOML scan text selection;
- `docs/reference/instruction-artifacts-mcp.md` MCP contract note for role TOML scan fields;
- scanner now counts human-readable role instruction fields and excludes technical metadata arrays such as `avoid_terms`, `canonical_actions`, and `policy_modes` from weak-term/friction scoring.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `176 -> 164`;
- `surface_summary.weak_terms_by_kind.reference` stayed `19` after the contract note;
- no role TOML, skill, catalog, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave;
- this is MCP queue correctness work, not PASS proof or runtime proof.

Critic requirement:

- PASS only if current repo evidence proves this MCP scanner change advances the active goal by removing technical metadata false positives from role instruction-surface scoring, preserves human-readable role field scanning, preserves response schema fields, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files match scanner code, MCP reference doc, and plan evidence; MCP/helper path remains active; role weak terms are `176 -> 164`; scanner still reads human-readable role fields while excluding technical metadata arrays; response schema fields remain stable; and broad all-instruction goal remains open.
