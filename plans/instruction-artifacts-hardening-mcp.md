# Instruction Artifacts MCP + Instruction Hardening Plan

## Objective
Build the plugin-owned path that connects the `instruction_artifacts` MCP scanner with the `instruction-hardening` skill so agents refactor instruction surfaces from MCP evidence, not from instructions-as-truth assumptions.

Phase 1 delivered the minimal MCP connection. The broader goal remains open until dependency-aware decision links, escalation candidates, bounded instruction refactors, and final critic confirmation are complete.

## Target layer
- target_layer: plugin
- repo: canonical `@Bears` plugin checkout
- owner role: `bears-instruction-hardening-engineer`
- MCP source: `src/bears_workflow/instruction_artifacts/`
- skill source: `skills/instruction-hardening/`

## Operator decision
- Decision: Add a minimal MCP packet that treats operator decisions as the highest-priority authoritative source for instruction graph work.
- Rationale: The operator requested decision-first graphs and MCP-mediated docs/contracts work.
- Live confirmation: MCP packet must expose whether authoritative decision coverage is missing or refuted by scanned artifacts.

## Requirements
1. Every instruction graph returned by the new MCP surface has one explicit `decision` object.
2. Operator decisions have higher priority than docs, contracts, AGENTS, skills, roles, and catalogs.
3. The MCP must not declare instructions to be source of truth; it may only expose scanned evidence and gaps.
4. Each graph has `live_confirmation` that an agent can confirm or refute from current file evidence.
5. Instruction standardization evidence is explicit and tied to `instruction-hardening` policy grammar.
6. Startup packet remains bounded and keeps deterministic truncation metadata.
7. Full graph payload remains available only through explicit MCP call.
8. No product/runtime/deploy/Kubernetes mutation.
9. Keep plugin source portable: no source-embedded server absolute paths except examples with placeholders.
10. Update docs/tests/catalog entries needed for the new surface.
11. Commit task-owned changes first; then inspect local commit validation evidence for that commit before any push.
12. If no explicit non-instruction operator decision is attached, each graph still gets `decision.status="missing"` and must not promote AGENTS, skills, contracts, docs, or catalogs to operator decision.
13. If scanned evidence conflicts with an explicit non-instruction operator decision, keep `decision.status="missing"` and use `live_confirmation.status="refuted"` with refutable evidence refs.
14. Each graph exposes decision dependency links for scanned instruction dependencies that can affect each other.
15. Each graph exposes an `escalation_candidate` object. If a dependency points at Kubernetes, deploy, runtime, secret, CD, `local_cd`, Dagger proof, workflow policy, role policy, or cross-owner governance evidence, the graph must require higher-level owner review before refactor.
16. Use `app-functional-graph` as workflow reference for exact refs, dependency edges, status fields, and evidence refs only. Do not treat app graph files as plugin authority.
17. Full instruction-surface refactor starts only after Phase 2 MCP fields are present and critic-approved.

## Minimal schema
- `decision.status`: `missing` unless an explicit non-instruction operator-decision source is attached.
- `live_confirmation.status`: `missing` or `refuted` for scanned-only packets.
- `standardization.status`: `aligned`, `partial`, or `missing`.
- `dependency_decision_refs[]`: dependency edge, source/target decision status, source/target doc path, and whether the edge carries escalation signal.
- `escalation_candidate.status`: `required` or `not_required`.

## Minimal implementation
- Add an application helper that enriches normalized `graphs[]` with:
  - `decision`: decision id, source, priority, status, summary, owner role, evidence doc ids, and missing/contradiction notes.
  - `live_confirmation`: status, confirmable evidence refs, refutable evidence refs, checked fields, and warnings.
  - `standardization`: status, policy modes found, canonical action coverage, weak terms found, and skill refs.
- Add MCP tool `instruction_hardening_startup` for bounded graph packets.
- Add MCP tool `instruction_hardening_graphs` for explicit full packet retrieval.
- Keep existing `zones_startup` and `zones` behavior stable.
- Document that docs/contracts refactoring should start from `instruction_hardening_startup`, then escalate to `instruction_hardening_graphs` only when needed.
- Extend existing instruction artifact tests with mocked normalized graphs.
- Standardization evidence uses the policy modes, canonical actions, and weak terms from `skills/instruction-hardening/SKILL.md` or the matching machine-readable role fields in `agents/bears-instruction-hardening-engineer.toml`.
- Update the `instruction-hardening` skill and plugin prompt/catalog description so the MCP preflight is visible at invocation time.
- Move artifact-registry missing tracked path detection into `scripts/artifact_registry.py`; JSON cleanup alone is not enough.
- Add a regression test that fails a `git_tracked=true` exact registry path with no tracked-file match.

## Workflow shape borrowed from app-* skills
- Treat this as `target_layer=plugin`.
- Use one lane: `plugin/instruction-artifacts`.
- Use exact target files only.
- Use critic confirmation before scope, owner, acceptance, or final completion
  changes. Evidence-only status notes and blocker wording cuts may proceed from
  parent read-only evidence, then the final critic reviews the full result.
- Use automatic validation evidence after commit; do not run route/audit/test suites manually before commit.
- Borrow from `app-functional-graph`: exact graph refs, dependency edges, status fields, and evidence refs. Do not store plugin work in app graph artifacts.

## Phases

### Phase 1: Minimal MCP connection
- Status: complete.
- Evidence:
  - `instruction_hardening_startup` and `instruction_hardening_graphs` exist.
  - Every enriched graph has `decision`, `live_confirmation`, and `standardization`.
  - `source.instructions_source_of_truth=false`.
  - Skill and plugin prompt route instruction refactors through the hardening MCP preflight.
  - Commit/local-validation/push completed at `63c91c8`.

### Phase 2: Decision dependencies and escalation candidates
- Status: complete.
- Add `dependency_decision_refs[]` to every enriched graph.
- Add `escalation_candidate` to every enriched graph.
- Escalation signals include Kubernetes, deploy, runtime, secret, CD, local_cd, Dagger proof, workflow policy, role policy, and cross-owner instruction evidence.
- Add mocked graph tests for dependency decision refs and escalation status.
- Update MCP reference docs and skill preflight text.

### Phase 3: Bounded instruction-surface refactors
- Status: unblocking_same_owner_wording_cuts.
- Phase 3 completion is per wave only. The full goal stays open until Phase 4 critic approval.
- Each wave must cite current `instruction_hardening_startup` or `instruction_hardening_graphs` evidence. If the current Codex toolset cannot call the MCP, record `tool_gap` and stop before any Phase 3 completion claim.
- Current tool gap unblock: add `scripts/instruction_hardening_mcp_packet.py` as a read-only stdio MCP client fallback. Allowed command:
  `python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root ../.. --bounded-json`.
- The helper is MCP evidence only: not a test, validator, route/audit substitute, PASS proof, or objective runtime proof. It must call the MCP stdio protocol, not `application.zones` internals, and emit bounded JSON without secrets, env values, raw logs, or production data.
- Decision drift fix: scanned AGENTS, skills, docs, contracts, roles, and catalogs
  must never set `decision.status=present`; they may only produce evidence-only
  mentions, refutable signals, dependency links, and escalation candidates until
  an explicit non-instruction operator-decision source is attached.
- Before Wave 3A refactors, cite one current helper-produced MCP packet and
  check `decision.status` and `escalation_candidate.status`.
- Current plugin-root helper evidence command:
  `python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root . --bounded-json`.
- Current plugin-root helper result is MCP evidence only, not final proof:
  `docs=6`, `graphs=1`, `decision.status=missing`,
  `live_confirmation.status=missing`, `standardization.status=partial`,
  `escalation_candidate.status=required`.
- `decision.status=missing` blocks adding or promoting operator authority from
  scanned text. It does not block mechanical compression, duplicate removal, or
  same-owner wording cuts.
- `escalation_candidate.status=required` blocks dependency-owned edits. It does
  not block edits inside the current owner surface that keep the dependency rule
  routed to its owner.
- Wave 3A: plugin-owned instruction hardening surfaces only:
  - `plans/instruction-artifacts-hardening-mcp.md`
  - `docs/reference/instruction-artifacts-mcp.md`
  - `skills/instruction-hardening/SKILL.md`
  - `agents/bears-instruction-hardening-engineer.toml` only if needed.
- Wave 3A action: compress wording, remove test/validator PASS logic from instruction logic, keep operator decision priority, and keep MCP evidence fields.
- Wave 3B: root/workspace `AGENTS.md` and plugin `AGENTS.md` only when MCP evidence says no escalation is required or the higher-level owner is explicit. Use a separate root commit for root-owned changes.
- Wave 3C: remaining repo-owned `AGENTS.md`, skills, contracts, or role prose use separate owning-repo commits and closeout.
- Tests, validators, schemas, lint, and static checks are safety guardrails only. They are not instruction completion proof.
- `app-functional-graph` is pattern-only for exact refs, dependency edges, status fields, and evidence refs. It is not an executable validator or authority for plugin instruction work.
- Tests, catalogs, `BUILD`, and generated inventory change in Phase 3 only when MCP code or catalog-owned descriptions change.

### Phase 4: Final consistency confirmation
- Status: pending.
- Run an L3 critic with `gpt-5.5` high, no fork context.
- Critic must verify the full objective from current files and read-only evidence, not from parent claims.
- Only after critic approval may the goal be marked complete.

## Planned target files
- `plans/instruction-artifacts-hardening-mcp.md`
- `src/bears_workflow/instruction_artifacts/application/zones.py`
- `src/bears_workflow/instruction_artifacts/entrypoints/mcp.py`
- `docs/reference/instruction-artifacts-mcp.md`
- `tests/test_instruction_artifacts.py`
- `skills/instruction-hardening/SKILL.md`
- `skills/instruction-hardening/agents/openai.yaml`
- `.codex-plugin/plugin.json`
- `README.md`
- `scripts/artifact_registry.py`
- `tests/test_artifact_registry.py`
- `assets/catalog/plugin-skill-catalog.v1.json`
- `assets/catalog/artifact-registry.v1.json`
- `assets/catalog/pants-test-graph.v1.json`
- `assets/catalog/release-notes.v1.json`
- `assets/catalog/test-selection.v1.json`
- `BUILD`
- `docs/generated/README.skill-inventory.md`
- Catalog edits are limited to existing tracked catalogs that enumerate skill descriptions, artifact registry ownership, test selection, Pants file coverage, or release notes.

## Current status
- phase_1_minimal_mcp_connection: complete
- phase_2_decision_dependencies_escalation: complete
- phase_3_bounded_instruction_refactors: unblocking_same_owner_wording_cuts
- phase_4_final_consistency_critic: pending
- latest_plan_change_critic: approved by no-fork `gpt-5.5` high critic `019f3976-7920-7433-a6b4-70eae4653d7e`
- latest_phase_2_critic: approved by no-fork `gpt-5.5` high critic `019f397a-e75d-7192-8cd9-b37cce31419f`
- latest_phase_3_refinement_critic: changes_required by no-fork `gpt-5.5` high critic `019f3980-b0c8-7681-9b71-0b2a63f1db32`
- latest_instruction_friction_audit: cut_required by no-fork `gpt-5.5` medium auditor `019f399a-958a-72f3-b736-c82b78a5c02e`; same-owner wording cuts are allowed while authority claims and dependency-owned edits remain blocked.
- latest_mcp_helper_plan_critic: require_edits by no-fork `gpt-5.5` high critic `019f3987-d46a-7d62-9d03-9ba578ee3609`; required edits applied in plan/docs/skill/helper scope.
- latest_decision_authority_critic: require_edits by no-fork `gpt-5.5` high critic `019f398c-380d-7260-99ba-871f6d058897`; scanned instruction prose must not claim operator decision authority.
- latest_phase_3_status_critic: approve_with_required_edits by no-fork `gpt-5.5` high critic `019f398e-dc37-70b3-a595-947990f1b3de`; required status edits applied before the friction audit narrowed the block to authority claims and dependency-owned edits.
- current_mcp_tool_gap: current Codex toolset exposes MCP registration through `codex mcp get mcp` but no callable `instruction_hardening_startup` tool namespace in this turn.
- full_goal_complete: false
