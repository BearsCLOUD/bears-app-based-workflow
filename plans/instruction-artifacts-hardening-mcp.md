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

Status: pending final re-audit after stale-plan fix commit.

Run a no-fork `gpt-5.5` high L3 critic after this plan-status fix is committed and pushed. Previous final critic `019f39c2-2805-7e22-8c3c-f8bbd3d8a3fe` passed requirements 1-10 and 12, then blocked only this stale plan status. The next critic may close the goal without another plan mutation if current files and checks still pass.

## Current status

- phase_1_minimal_mcp_connection: complete
- phase_2_decision_dependencies_escalation: complete
- phase_3_full_plugin_instruction_refactor: complete
- phase_4_final_consistency_critic: pending_final_reaudit_after_plan_status_fix
- current_mcp_tool_gap: current Codex toolset exposes MCP registration through `codex mcp get mcp` but no callable `instruction_hardening_startup` namespace in this turn; use the documented stdio MCP helper as evidence.
- full_goal_complete: pending_final_critic_pass
