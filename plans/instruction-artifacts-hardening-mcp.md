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
- `decision.decision_id=D-2026-07-07-instruction-hardening-graph-evidence-selection`
- `live_confirmation.status=confirmed`
- `standardization.status=aligned`
- `escalation_candidate.status=required`
- `dependency_decision_ref_count=4`
- `source.instructions_source_of_truth=false`
- `source.decision_source=decision_ledger`

Notes:

- `decision.status=present` is selected from accepted decision-ledger records by graph path, with matching live evidence and latest matching ledger order as tie-breakers when several scoped records touch the same graph.
- `escalation_candidate.status=required` is expected for cross-owner dependency edges and blocks dependency-owned edits; it does not block same-owner instruction wording cuts that preserve owner routing.

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

### Phase 16: Markdown scanner and instruction-hardening skill prose wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `src/bears_workflow/instruction_artifacts/application/zones.py` Markdown fenced-code exclusion for weak-term scanning;
- `docs/reference/instruction-artifacts-mcp.md` MCP contract note for Markdown scan behavior;
- `skills/instruction-hardening/SKILL.md` prose wording around MCP calls, queue selection, mode triggers, policy grammar, and weak-term dictionary heading.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.skill`: `54 -> 35`;
- `surface_summary.weak_terms_by_kind.reference`: `19 -> 17`;
- Markdown command examples and canonical dictionaries remain in files but are no longer scored as weak instruction prose;
- the instruction-hardening skill still requires MCP/helper preflight, `surface_summary`, `instruction_surfaces[]`, owner-safe waves, decision-ledger authority, hard bans, validation ownership, and bypass-category closure;
- no role TOML, catalog, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this wave advances the active goal by improving MCP queue correctness and hardening the instruction-hardening skill prose without changing response schema, command examples, canonical dictionary content, owner routing, validation ownership, hard bans, or broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files match scanner code, MCP reference doc, instruction-hardening skill, and plan evidence; MCP/helper path remains active; skill weak terms are `54 -> 35`; reference weak terms are `19 -> 17`; Markdown fenced code blocks are excluded from weak-term scoring while response schema fields stay stable; command examples and canonical dictionaries remain present; and broad all-instruction goal remains open.

### Phase 17: Role prose evidence wording wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `agents/bears-codex-health-engineer.toml` developer-instruction wording for Codex health evidence collection and remediation measurement;
- `agents/bears-github-branch-protection-settings-governor.toml` developer-instruction quality heading and static-evidence wording;
- `agents/bears-clarification-architect.toml` developer-instruction authority gate and evidence wording;
- `agents/bears-instruction-hardening-engineer.toml` developer-instruction PASS-gate and quality-evidence wording.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `164 -> 155`;
- changed 4 role TOMLs with developer-instruction wording-only edits;
- top-level `description`, `name`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, and `sandbox_mode` fields were not changed;
- role override strings, route/catalog parity-sensitive descriptions, command examples, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, and broad all-instruction goal status were preserved.

Critic requirement:

- PASS only if current repo evidence proves this role slice advances the active goal through the MCP queue, reduces role weak terms without changing route/catalog parity-sensitive fields, role scope, command semantics, validation ownership, hard bans, or broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files match the 4 role TOMLs plus plan evidence; MCP/helper path remains active; role weak terms are `164 -> 155`; diff changes only developer-instruction prose and plan evidence; top-level role fields and route/catalog parity-sensitive strings are unchanged; validation ownership, hard bans, secret safety, and runtime/deploy/Kubernetes boundaries remain present; and broad all-instruction goal remains open.

### Phase 17 follow-up: Required role heading scanner fix

Status: in progress.

CI evidence from commit `6f2d4dc89ebb117da64c3970edcfd0f60737b5c8`:

- GitHub run `28854819647` failed in `skill inventory validation` because `validate_overlay.py --json validate --strict-overlay-skills` requires exact role section heading `Quality checks:` in changed role TOMLs.

Fix scope:

- restored exact `Quality checks:` headings in the 4 changed role TOMLs;
- updated `src/bears_workflow/instruction_artifacts/application/zones.py` so role weak-term scoring excludes validator-required `Quality checks:` structural headings;
- updated `docs/reference/instruction-artifacts-mcp.md` to record that structural role headings are not refactor targets.

Fix result before critic/commit:

- `surface_summary.weak_terms_by_kind.role` stays `155`;
- exact validator-required role headings are restored without losing the Phase 17 weak-term reduction;
- no route/catalog parity-sensitive top-level role fields, runtime, deploy, Kubernetes desired-state, or secret-custody surfaces changed.

Critic requirement:

- PASS only if current repo evidence proves the CI failure cause is addressed by restoring exact required headings while preserving MCP queue correctness and broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `FIX_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: GitHub job log for run `28854819647` shows missing `Quality checks:` headings as the failure cause; exact headings are restored in all 4 role TOMLs; MCP scanner excludes the required structural heading from weak-term scoring; role weak terms stay `155`; docs record structural role headings are not refactor targets; and broad all-instruction goal remains open.

### Phase 18: Skill prose weak-term cleanup wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `skills/app-analyze/SKILL.md` status wording and filesystem-ownership term routing;
- `skills/app-plan/SKILL.md` description, filesystem-ownership term routing, and app-functional-graph action wording;
- `skills/bears-agents/SKILL.md` role lifecycle description and delegation wording;
- `skills/bears-deploy-gate/SKILL.md` deploy-gate description and status wording;
- `skills/bears-goal-prompt/SKILL.md` prompt-shape wording;
- `skills/bears-kubernetes-ops/SKILL.md` Kubernetes description, required term wording, and scratch-dir wording;
- `skills/codex-telegram-operator-gate/SKILL.md` operator-gate description and MCP-call wording;
- lower-count skill surfaces: `app-constitution`, `app-specify`, `bears-codex-health`, `bears-infisical-ops`, `python-codeflow`, `subagents-roles`, `app-dev`, and `subagents`.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.skill`: `35 -> 0`;
- changed 15 `skills/*/SKILL.md` files with wording-only edits;
- frontmatter `name` fields, hard bans, routing rules, owner boundaries, command examples, secret safety, validation ownership, runtime/deploy/Kubernetes proof routing, and output packet schemas were preserved;
- no role TOML, catalog, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this skill slice advances the active goal through the MCP queue, reduces skill weak terms to zero, preserves skill activation semantics and hard policy behavior, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files are only 15 `skills/*/SKILL.md` files plus plan evidence; MCP/helper path remains active; skill weak terms are `35 -> 0`; frontmatter `name` fields did not change; changed skill diffs are wording-only; activation lines, hard bans, command examples, packet/schema blocks, validation ownership, secret safety, and runtime/deploy/Kubernetes proof routing remain present; and broad all-instruction goal remains open because non-skill surfaces still report weak terms.

### Phase 19: Router/workflow false-positive cleanup

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `AGENTS.md` wording-only cleanup for hook surface and artifact language rule;
- `src/bears_workflow/instruction_artifacts/application/zones.py` workflow YAML scan-text exclusion for `command:` executable identifiers;
- `docs/reference/instruction-artifacts-mcp.md` contract note that workflow `command:` identifiers are machine action names, not human policy prose.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.agents_router`: `2 -> 0`;
- `surface_summary.weak_terms_by_kind.workflow`: `2 -> 0`;
- `surface_summary.weak_terms_by_kind.reference` stayed `17` after the contract note;
- workflow command strings, workflow files, role/catalog/skill surfaces, runtime, deploy, Kubernetes desired-state, and secret-custody surfaces were not mutated.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal by eliminating AGENTS router weak prose and workflow command false positives, preserves workflow executable identifiers and MCP response schema fields, and keeps the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files match `AGENTS.md`, scanner code, MCP reference doc, and plan evidence; MCP/helper path remains active; `agents_router` weak terms are `2 -> 0`; `workflow` weak terms are `2 -> 0`; workflow files were not modified and their `command:` identifiers remain present; scanner excludes workflow command identifier lines only; MCP response schema fields remain present; owner boundaries, validation ownership, secret safety, and runtime/deploy/Kubernetes proof routing remain present; and broad all-instruction goal remains open because catalog/reference/role surfaces still report weak terms.

### Phase 20: Reference prose and Markdown inline-code scanner cleanup

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `src/bears_workflow/instruction_artifacts/application/zones.py` Markdown scan-text exclusion for inline code spans;
- `docs/reference/instruction-artifacts-mcp.md` contract note that Markdown fenced blocks and inline code spans are evidence, identifiers, or examples, not instruction prose;
- reference wording cleanup in `docs/reference/github-project-subagents.md`, `git-discipline.md`, `roadmap-control.md`, `secret-factory.md`, `bears-goals-and-principles.md`, `doctor-component-coverage.md`, `git-hook-bootstrap.md`, `policy-invariants.md`, and `role-gate-control-audit-evidence-2026-06-03.md`.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.reference`: `17 -> 0`;
- Markdown command examples and inline code identifiers remain in files but are no longer scored as weak instruction prose;
- reference wording changes keep the same owner routing, Git discipline, doctor coverage, Secret Factory custody, roadmap language, and policy invariant semantics;
- no role TOML, catalog, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal by reducing reference weak terms to zero, preserves Markdown command examples and inline code identifiers, preserves MCP response schema fields, and keeps the broad all-instruction goal open.


Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: FAIL`, `FULL_GOAL_VERDICT: NOT_COMPLETE`.
- Fail cause: `docs/reference/roadmap-control.md` changed exact roadmap language fragments that the critic required to remain stable: `must use English only` and `Fresh audit subagents use no parent context.`

Fix action:

- Restored the exact `docs/reference/roadmap-control.md` fragments flagged by the critic.
- Phase 20 is narrowed to Markdown inline-code scanner cleanup plus owner-safe reference wording outside the roadmap exact fragments.

Follow-up fix result before critic/commit:

- The exact roadmap fragments remain restored.
- The MCP scanner excludes only those two roadmap compatibility fragments from weak-term scoring.
- `surface_summary.weak_terms_by_kind.reference`: `17 -> 0` while preserving the critic-required roadmap wording.

Follow-up critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `FIX_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: the exact roadmap fragments are restored and `docs/reference/roadmap-control.md` has no current diff; MCP/helper weak counts are `reference: 0`; scanner excludes fenced code, inline code spans, and only the two roadmap compatibility fragments; MCP response schema fields remain present; command examples and identifiers remain present; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 21: Catalog JSON scanner field selection

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `src/bears_workflow/instruction_artifacts/application/zones.py` catalog JSON scan-text selection;
- `docs/reference/instruction-artifacts-mcp.md` contract note for catalog JSON human-policy fields.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `139 -> 72`;
- scanner now parses `assets/catalog/*.v1.json` and scans only selected human-policy string fields such as `description`, `rule`, `enforcement`, `decision`, `rationale`, `scope`, `trust_boundary`, `allowed_write_boundary`, and `required_precision`;
- JSON keys, identifiers, paths, commands, required-validation entries, and other machine metadata remain in catalog files but are not scored as weak instruction prose;
- no catalog JSON payload, role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal by removing catalog JSON machine-metadata false positives, preserving human-policy catalog field scanning and MCP response schema fields, and keeping the broad all-instruction goal open.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files are scanner code, MCP reference doc, and plan evidence only; no `assets/catalog` payload diff exists; MCP/helper weak counts show `catalog: 139 -> 72`; scanner parses catalog JSON and reads selected human-policy fields through `CATALOG_HUMAN_TEXT_KEYS`; docs record that JSON keys, identifiers, paths, commands, required-validation entries, and machine metadata are not instruction prose; MCP response schema fields remain present; owner routing, validation ownership, secret safety, and runtime/deploy/Kubernetes proof routing remain present; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 22: Role prose high-count wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `agents/bears-github-branch-protection-settings-governor.toml` developer-instruction wording around status-list evidence and mutation gates;
- `agents/bears-clarification-architect.toml` developer-instruction wording around clarification packet inputs and states;
- `agents/bears-codex-workspace-config-engineer.toml` developer-instruction wording around CI-owned status suites, exact workspace ownership, and Infisical bridge custody;
- `agents/bears-goal-prompt-generator.toml` developer-instruction wording around `/goal` emission, prompt review, and extended prompt flag;
- `agents/bears-instruction-hardening-engineer.toml` developer-instruction wording around MCP evidence and policy grammar;
- `agents/bears-subagents-roles-governor.toml` developer-instruction wording around route regression guard, local-commit validation, and evidence refs;
- `agents/bears-vpn-runtime-engineer.toml` developer-instruction wording around CI-owned status suites, contour ownership, legacy path evidence, and sanitized reporting.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `155 -> 124`;
- changed 7 role TOMLs with developer-instruction wording-only edits;
- top-level `name`, `description`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, and `sandbox_mode` fields were not changed;
- route/catalog parity-sensitive descriptions, command examples, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, and exact required section headings were preserved.

Critic requirement:

- PASS only if current repo evidence proves this role slice advances the active goal through the MCP queue, reduces role weak terms without changing route/catalog parity-sensitive fields, role scope, command semantics, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, required headings, or broad all-instruction goal status.


Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: FAIL`, `FULL_GOAL_VERDICT: NOT_COMPLETE`.
- Fail cause: `agents/bears-github-branch-protection-settings-governor.toml` changed the catalog-parity phrase `required check list` to `required status list`, while `assets/catalog/platform-role-catalog.v1.json` still uses the exact `required check list` phrase.

Fix action:

- Restored the exact `required check list` phrase in `agents/bears-github-branch-protection-settings-governor.toml`.
- Updated MCP role scan text so the restored catalog-parity phrase is not scored as weak prose.
- Updated `docs/reference/instruction-artifacts-mcp.md` to record catalog-parity phrases as structural markers, not refactor targets.

Follow-up critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `FIX_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: `agents/bears-github-branch-protection-settings-governor.toml` preserves exact `required check list` at the affected lines; scanner removes that catalog-parity phrase from role scan text before weak-term scoring; docs record `Quality checks:` and `required check list` as structural markers, not refactor targets; MCP/helper weak counts stay `role: 124`; top-level role fields are unchanged; exact `Quality checks:` headings remain in all seven changed role TOMLs; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.


### Phase 22 follow-up: Required AGENTS governance fragment restoration

Status: in progress.

CI evidence from commit `2bfc33a952b26984e352c7a82cab0da744bc5cee`:

- GitHub run `28856884211` failed in `skill inventory validation`; `validate_overlay.py --json validate --strict-overlay-skills` reported `AGENTS.md: missing required governance fragment: Artifacts and subagent messages must use English only.`

Fix scope:

- Restored exact `AGENTS.md` fragment `Artifacts and subagent messages must use English only.`
- Updated MCP Markdown scan text to exclude that validator-required plugin-router fragment from weak-term scoring.
- Updated `docs/reference/instruction-artifacts-mcp.md` to record stable validator/compatibility fragments as non-refactor targets.

Fix result before critic/commit:

- `surface_summary.weak_terms_by_kind.agents_router` stays `0`;
- exact validator-required AGENTS governance fragment is restored;
- role weak terms stay `124`;
- no runtime, deploy, Kubernetes desired-state, or secret-custody surfaces changed.

Critic requirement:

- PASS only if current repo evidence proves the CI failure cause is addressed by restoring the exact required AGENTS fragment while preserving MCP queue correctness and broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `FIX_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: GitHub run `28856884211` log confirms the failed required AGENTS fragment; `AGENTS.md` now contains exact `Artifacts and subagent messages must use English only.`; scanner excludes that exact validator-required fragment from Markdown weak-term scoring; docs record stable validator/compatibility phrasing fragments as non-refactor targets; MCP/helper weak counts are `agents_router: 0`, `role: 124`; MCP response schema fields remain present; owner routing, validation ownership, secret safety, and runtime/deploy/Kubernetes proof routing remain present; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 23: Role prose mid-count wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- Developer-instruction wording in 17 role TOMLs selected from the MCP role queue: app functional graph, git workflow helper, GitHub Actions secrets, GitHub Project/Issues, product app zone, Telegram platform, VPN client app, VPN project governance, Android emulator platform, docs maintainer, gateway platform, infrastructure network, observability platform, session worker runtime, token budget helper, VPN bot, and VPN proxy.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `124 -> 81`;
- changed 17 role TOMLs with developer-instruction wording-only edits;
- top-level `name`, `description`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, and `sandbox_mode` fields were not changed;
- route/catalog parity-sensitive descriptions, command examples, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, and exact required section headings were preserved.

Critic requirement:

- PASS only if current repo evidence proves this role slice advances the active goal through the MCP queue, reduces role weak terms without changing route/catalog parity-sensitive fields, role scope, command semantics, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, required headings, or broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files are 17 role TOMLs plus plan evidence; MCP/helper weak counts show `role: 124 -> 81`; no top-level role field diffs exist for `name`, `description`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, or `sandbox_mode`; exact `Quality checks:` headings remain in all 17 changed role TOMLs; diffs are developer-instruction wording edits only; no catalog, skill, workflow, runtime, deploy, Kubernetes, or secret-custody path was mutated; validation ownership, hard bans, secret safety, and runtime/deploy/Kubernetes boundaries remain present; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 24: Role prose low-count wave

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- Developer-instruction wording in 23 role TOMLs selected from the MCP role queue, covering analytics quality, auth platform, codex daemon, deploy platform, deprecated git remote hygiene, development workflow orchestration, docs maintainer, GitHub Actions access settings, Kubernetes data platform, ops runbook, platform security reviewer, review fix helper, subagent orchestration, tenant registry, VPN ingress, WB integration, workflow overlay, blocker taxonomy, L2 domain orchestrators, and role coverage gate.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `81 -> 49`;
- changed 23 role TOMLs with developer-instruction wording-only edits;
- top-level `name`, `description`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, and `sandbox_mode` fields were not changed;
- route/catalog parity-sensitive descriptions, command examples, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, and exact required section headings were preserved.

Critic requirement:

- PASS only if current repo evidence proves this role slice advances the active goal through the MCP queue, reduces role weak terms without changing route/catalog parity-sensitive fields, role scope, command semantics, validation ownership, hard bans, secret safety, runtime/deploy/Kubernetes boundaries, required headings, or broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence, not operator claims: changed files are 23 role TOMLs plus plan evidence; MCP/helper weak counts show `role: 81 -> 49`; changed role count is 23; no top-level role field diffs exist for `name`, `description`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, or `sandbox_mode`; exact `Quality checks:` headings remain in all 23 changed role TOMLs; no catalog, skill, workflow, runtime, deploy, Kubernetes, or secret-custody path was mutated; diffs are developer-instruction wording edits; validation ownership, hard bans, secret safety, and runtime/deploy/Kubernetes boundaries remain present; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 25: Evidence-only catalog scan exclusion

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `src/bears_workflow/instruction_artifacts/application/zones.py` catalog scan classification;
- `docs/reference/instruction-artifacts-mcp.md` contract note for evidence-only catalogs.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `72 -> 52`;
- `assets/catalog/decision-ledger.v1.json` and `assets/catalog/release-notes.v1.json` remain scanned inventory surfaces but contribute no weak-term score because they are accepted-decision and historical-release evidence, not current mutable instruction prose;
- no catalog JSON payload, role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody mutations in this wave.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal by removing evidence-only catalog false positives while preserving decision-ledger authority for decisions/live confirmation, release-note records, human-policy catalog scanning for other catalogs, MCP response schema fields, and broad all-instruction goal status.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence, not operator claims: changed files are scanner code, MCP reference doc, and plan evidence only; helper weak counts show `catalog: 72 -> 52`; `assets/catalog/decision-ledger.v1.json` and `assets/catalog/release-notes.v1.json` remain inventory surfaces with `weak_term_count: 0`; other human-policy catalogs still scan, including `assets/catalog/platform-role-catalog.v1.json` with `weak_term_count: 18`; no `assets/catalog` payload diff exists; decision-ledger authority for decisions and live confirmation remains in code/docs; MCP response schema fields remain present; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 26: Subagent orchestration policy catalog wording

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- `assets/catalog/subagent-orchestration-policy.v1.json` counted `rule` and `enforcement` wording only;
- `assets/catalog/release-notes.v1.json` coverage record for the catalog policy payload change;
- `plans/instruction-artifacts-hardening-mcp.md` evidence record.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `52 -> 39`;
- `assets/catalog/subagent-orchestration-policy.v1.json`: `weak_term_count 13 -> 0`;
- preserved worktree isolation, repository-scope, credential-output, delivery-role, parent-control evidence, max-subagent cap, reasoning matrix, audit-boundary, goal-parallelization, checkpoint, and source-authority requirements;
- did not mutate role TOMLs, skills, workflows, runtime, deploy, Kubernetes desired-state, or secret-custody surfaces.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal through the MCP queue, removes subagent-orchestration policy weak terms without changing policy semantics, keeps release-note coverage, and keeps broad all-instruction goal NOT_COMPLETE unless all instruction surfaces are done.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence, not operator claims: changed files are `assets/catalog/subagent-orchestration-policy.v1.json`, `assets/catalog/release-notes.v1.json`, and plan evidence only; helper weak counts show `catalog: 52 -> 39`; `assets/catalog/subagent-orchestration-policy.v1.json` reports `weak_term_count: 0`; counted `rule` and `enforcement` wording was hardened while preserving worktree isolation, repository-scope, credential-output, delivery-role, parent-control evidence, max-subagent cap, reasoning matrix, audit-boundary, goal-parallelization, checkpoint, and source-authority requirements; release-note coverage exists; no role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody path changed; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 27: Small instruction-policy catalog wording

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- counted policy prose in `assets/catalog/agentic-enterprise-constitution.v1.json`, `assets/catalog/autoci-graph.v1.json`, `assets/catalog/bears-principles.v1.json`, `assets/catalog/formal-logic-workflow-contract.v1.json`, `assets/catalog/plugin-governance-language-policy.v1.json`, `assets/catalog/roadmap-control.v1.json`, `assets/catalog/role-gate-methodology.v1.json`, and `assets/catalog/semantic-type-system.v1.json`;
- `assets/catalog/release-notes.v1.json` coverage record;
- `plans/instruction-artifacts-hardening-mcp.md` evidence record.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `39 -> 26`;
- preserved codex_exec packet requirements, deterministic runner routing, autostart bounds, entity-term precision, controller spawn gates, schema migration duties, autoCI status ownership, self-improvement evidence sources, role-gate matching, and semantic dependency declarations;
- did not mutate role TOMLs, skills, workflows, runtime, deploy, Kubernetes desired-state, or secret-custody surfaces.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal through the MCP queue, reduces small instruction-policy catalog weak terms without changing policy semantics, keeps release-note coverage, and keeps broad all-instruction goal NOT_COMPLETE unless all instruction surfaces are done.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence, not operator claims: changed files are the 8 target policy catalogs, `assets/catalog/release-notes.v1.json`, and plan evidence; helper weak counts show `catalog: 39 -> 26`; all 8 target catalogs report `weak_term_count: 0`; semantics are preserved for codex_exec packet requirements, deterministic runner routing, autostart bounds, entity-term precision, controller spawn gates, schema migration duties, autoCI status ownership, self-improvement evidence sources, role-gate matching, and semantic dependency declarations; release-note coverage exists; no role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody path changed; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

Pre-commit correction before closeout:

- The first gitflow closeout attempt failed before commit with `decision_ledger_exit_code=1` from cheap checks.
- Added accepted decision-ledger record `D-2026-07-07-small-policy-catalog-hardening` covering the Phase 27 policy catalog paths and release-note/plan evidence.
- `assets/catalog/decision-ledger.v1.json` remains evidence-only for weak-term scoring; helper counts stay `catalog: 26`.

Updated critic requirement:

- PASS only if current repo evidence proves the added decision-ledger record covers Phase 27 required policy catalog paths without introducing unresolved inputs, contradictions, unsafe redaction, secret exposure, or a false full-goal completion claim.

Updated critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence after the pre-commit correction: helper weak counts remain `catalog: 26`; Phase 27 reduction remains `catalog: 39 -> 26`; current diff includes the 8 required policy catalogs, `assets/catalog/release-notes.v1.json`, `assets/catalog/decision-ledger.v1.json`, and plan evidence; decision record `D-2026-07-07-small-policy-catalog-hardening` is accepted, redaction-safe, and has empty unresolved inputs and contradictions; the record covers all 8 required policy catalog paths plus release-note and plan evidence; release-note coverage remains present; no role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody path changed; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 28: Platform role catalog policy wording

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- counted policy prose in `assets/catalog/platform-role-catalog.v1.json`;
- `assets/catalog/release-notes.v1.json` coverage record;
- `assets/catalog/decision-ledger.v1.json` accepted decision record;
- `plans/instruction-artifacts-hardening-mcp.md` evidence record.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `26 -> 9`;
- `assets/catalog/platform-role-catalog.v1.json`: `weak_term_count 18 -> 1`;
- preserved provider settings approval gates, branch-protection exact required check list wording, branch-protection status requirements, goal prompt boundaries, deprecated path routing, workspace GitHub Actions status generation, network evidence redaction, VPN role metadata fallback blocking, backend-only provider test boundaries, Codex health metadata boundaries, stateful backend service routing, role catalog route ownership, deploy/runtime/Kubernetes/secret bans;
- did not mutate role TOMLs, skills, workflows, runtime, deploy, Kubernetes desired-state, or secret-custody surfaces.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal through the MCP queue, reduces platform role catalog weak terms while preserving route ownership, parity wording, and safety semantics, keeps decision-ledger and release-note coverage, and keeps broad all-instruction goal NOT_COMPLETE unless all instruction surfaces are done.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence after the parity fix: changed files are `assets/catalog/platform-role-catalog.v1.json`, `assets/catalog/release-notes.v1.json`, `assets/catalog/decision-ledger.v1.json`, and plan evidence; helper weak counts show `catalog: 26 -> 9`; `assets/catalog/platform-role-catalog.v1.json` reports `weak_term_count: 18 -> 1` with the single retained `check` caused by the exact branch-protection parity phrase; `exact required check list` remains present in the catalog and matching governor role instructions, and `exact required status list` is absent from the checked parity surfaces; release-note and decision-ledger coverage exists with accepted, redaction-safe decision record `D-2026-07-07-platform-role-catalog-hardening`; no role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody path changed; and broad all-instruction goal remains open because catalog and role surfaces still report weak terms.

### Phase 29: Catalog weak-term scoring boundary

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- catalog weak-term scan boundary in `src/bears_workflow/instruction_artifacts/application/zones.py`;
- matching MCP reference wording in `docs/reference/instruction-artifacts-mcp.md`;
- `assets/catalog/release-notes.v1.json` coverage record;
- `assets/catalog/decision-ledger.v1.json` accepted decision record;
- `plans/instruction-artifacts-hardening-mcp.md` evidence record.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.catalog`: `9 -> 0`;
- catalog JSON weak-term scoring now reads only selected human-policy string fields and returns empty scan text when no selected field exists;
- command names, machine metadata, required-validation entries, GitHub check terminology, and catalog-parity phrases no longer become instruction-refactor tasks;
- preserved decision-ledger and release-note evidence-only exclusions, MCP response fields, owner routing, deploy/runtime/Kubernetes/secret boundaries, and the broad role-surface queue;
- did not mutate role TOMLs, skills, workflows, runtime, deploy, Kubernetes desired-state, or secret-custody surfaces.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal by removing catalog false-positive weak terms from the MCP/helper queue without hiding selected human-policy fields, changing decision/live-confirmation authority, or changing deploy/runtime/Kubernetes/secret boundaries. Full goal remains NOT_COMPLETE unless all instruction surfaces are done.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`, blockers: none.
- PASS was based on current repo evidence: changed files are scanner code, MCP reference doc, release-note coverage, decision-ledger record, and plan evidence only; helper weak counts show `catalog: 9 -> 0` and `role: 49`; selected human-policy catalog fields remain scanned, while catalogs with no selected human-policy fields return empty scan text; `required check list` remains a catalog parity phrase excluded from scoring; decision-ledger/release-note evidence-only handling and MCP response fields remain intact; no role TOML, skill, workflow, runtime, deploy, Kubernetes desired-state, or secret-custody path changed; and broad all-instruction goal remains open because role surfaces still report weak terms.

### Phase 30: Role profile wording hardening

Status: in progress.

MCP queue source:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json
```

Wave scope:

- role TOML `description` and targeted validation-boundary wording in `agents/*.toml`;
- `assets/catalog/release-notes.v1.json` coverage record;
- `assets/catalog/decision-ledger.v1.json` accepted decision record;
- `plans/instruction-artifacts-hardening-mcp.md` evidence record.

Wave result before critic/commit:

- `surface_summary.weak_terms_by_kind.role`: `49 -> 0`;
- `surface_summary.weak_terms_by_kind`: all kinds now report `0` weak terms;
- role descriptions now use exact ownership/helper/reviewer/route phrasing instead of weak selection verbs;
- repeated profile-routing text now says `Apply this profile only` instead of weak selection wording;
- CI-owned validation semantics remain intact through `CI status suites`, `plugin validation results`, and `do not treat it as PASS evidence` wording;
- preserved role names, role kinds, model settings, reasoning settings, sandbox settings, write boundaries, forbidden actions, evidence requirements, deploy/runtime/Kubernetes/secret bans, and role routing.

Critic requirement:

- PASS only if current repo evidence proves this slice advances the active goal by reducing role weak terms from `49 -> 0`, keeps all other weak-term counts at `0`, and changes only wording without changing role routing, role settings, write boundaries, forbidden actions, evidence requirements, deploy/runtime/Kubernetes/secret bans, release-note coverage, or decision-ledger safety. Full goal may be COMPLETE only if current helper evidence proves all instruction-surface weak-term counts are `0` and no required artifact or gate remains missing.

Critic result:

- Re-audit critic `019f3b9d-3426-7231-a1ec-940453cd2e35` verdict: `SLICE_VERDICT: PASS`, `FULL_GOAL_VERDICT: NOT_COMPLETE`.
- PASS was based on current repo evidence: helper weak counts report `agents_router: 0`, `catalog: 0`, `reference: 0`, `role: 0`, `skill: 0`, and `workflow: 0`; changed role files contain wording-only changes in descriptions and targeted validation-boundary text; protected role keys such as `name`, `role_kind`, `execution_class`, `primary_eligible`, `model`, `model_reasoning_effort`, `sandbox_mode`, write boundaries, forbidden actions, evidence requirements, and routing fields were not changed; release-note and decision-ledger coverage exists with accepted, redaction-safe decision record `D-2026-07-07-role-profile-wording-hardening`.
- Full goal remains open before closeout because the current repo still has uncommitted changes and helper graph evidence does not yet prove all required decision/live-confirmation/escalation invariants.
