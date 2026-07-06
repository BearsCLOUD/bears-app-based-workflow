# Instruction Artifacts MCP + Instruction Hardening Plan

## Objective
Build the first minimal plugin-owned path that connects the `instruction_artifacts` MCP scanner with the `instruction-hardening` skill so agents can start refactoring instruction surfaces from MCP evidence, not from instructions-as-truth assumptions.

## Target layer
- target_layer: plugin
- repo: canonical `@Bears` plugin checkout
- owner role: `bears-instruction-hardening-engineer`
- MCP source: `src/bears_workflow/instruction_artifacts/`
- skill source: `skills/instruction-hardening/`

## Operator decision
- Decision: Add a minimal MCP packet that treats operator decisions as the highest-priority decision source for instruction graph work.
- Rationale: The operator requested decision-first graphs and MCP-mediated docs/contracts work.
- Live confirmation: MCP packet must expose whether decision coverage is present, missing, or contradicted by scanned artifacts.

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
12. If no operator decision is found in scanned docs, each graph still gets `decision.status="missing"` and must not promote AGENTS, skills, contracts, docs, or catalogs to operator decision.
13. If scanned evidence conflicts with an operator decision, use `decision.status="contradicted"` and `live_confirmation.status="refuted"` with refutable evidence refs.

## Minimal schema
- `decision.status`: `present`, `missing`, or `contradicted`.
- `live_confirmation.status`: `confirmed`, `missing`, `refuted`, or `partial`.
- `standardization.status`: `aligned`, `partial`, or `missing`.

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
- Use critic confirmation before plan changes and before final completion claim.
- Use automatic validation evidence after commit; do not run route/audit/test suites manually before commit.

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
- draft_plan_created: true
- critic_review: changes_required_applied
- artifact_registry_plan_change_review: approved
- implementation: complete
- validation: pending
- commit_push: pending
