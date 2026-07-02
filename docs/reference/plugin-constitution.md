# Plugin Constitution

## Purpose

The plugin constitution evaluates every Bears plugin change against agent simplification, token economy, deterministic validation, and future reuse before research starts.

## Technical terms

- Constitution: top-level rule set for judging whether plugin work is useful.
- Token cost: context and output consumed by the model.
- Bounded packet: short structured data that replaces broad file reads.
- Reusable evidence: file-backed proof a future agent can rely on.
- Deterministic validator: script or schema check with stable pass/fail output.
- Constitution gate: the policy check after route gate and before research gate.
- Change-check packet: JSON data that records changed surfaces, agent impact, context plan, validation, operator boundary, cost, and status.
- Restricted data: secrets, credentials, private keys, `.env` values, production data, raw logs, shell history, and raw VPN configs.

## Gate files

- Catalog: `assets/catalog/plugin-constitution.v1.json`.
- Validator: `scripts/plugin_constitution.py`.
- Tests: `tests/test_plugin_constitution.py`.
- Manifest: `.codex-plugin/plugin.json`.

## Principles

- `agent_simplification`: the change makes future agent work simpler.
- `token_economy`: the change reduces repeated context load or justifies added token cost.
- `bounded_context`: the change names the narrow context needed by the next worker.
- `deterministic_validation`: the change adds or updates a deterministic validation path.
- `future_reuse`: the change names where future agents reuse the rule.
- `operator_boundary`: the change states operator-owned decisions and agent-owned checks.
- `mode_explicitness`: the change states when normal, no-subagent, subagent, audit, or validation mode applies.
- `agent_handoff_compaction`: the change supports compact handoff with status, scope, validation, and unresolved decisions.
- `no_process_weight_without_payoff`: the change adds no gate, document, role, or checklist without explicit payoff.

## Required constitution check

A change-check packet must use schema `bears-plugin-constitution-change-check.v1` and contain these fields:

- `schema`
- `change_id`
- `changed_surfaces`
- `agent_simplification_impact`
- `token_budget_impact`
- `bounded_context_plan`
- `future_reuse_path`
- `deterministic_validation_added`
- `deterministic_validation_evidence`
- `operator_decision_boundary`
- `cost_justification_if_any`
- `status`

`status` must be `pass`, `fail`, or `needs-redesign`. Missing fields or any other status fail closed.

For `status` `pass`, `deterministic_validation_evidence` must be a non-empty object with `command`, `target_surface`, `expected_status`, `actual_status`, `validator_path`, and either `result_summary` or `evidence_path`. The command must be a repo-only validation command. The target, validator, and evidence paths must stay inside the plugin repository.

The packet must also include either `route_target` with `/srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json` or route/audit evidence from `platform_roles.py`. `changed_surfaces` must stay inside the exact plugin constitution governance path set. `lifecycle_position_proof` must be `after route_gate and before research_gate`.

Trust-boundary text fails when it claims product app, connector, MCP server, runtime service, product behavior, local_cd expansion, kubernetes_deployment expansion, standalone Bears governance, upstream Spec Kit vendoring, generic deploy wording, illustrative policy sections, or restricted-data access.

## Allowed outcomes

- `pass`: the packet proves a simpler route, lower or justified token cost, bounded context, reusable evidence, deterministic validation, and a clear operator boundary.
- `needs-redesign`: the packet shows added process weight, unclear mode, broad context, or missing reuse path that can be fixed before implementation.
- `fail`: the packet violates the plugin boundary, lacks payoff, lacks deterministic validation, or relies on chat memory instead of repository evidence.

## Blocked outcomes

- A second Bears governance plugin or standalone Bears governance layer.
- Product app, connector, MCP server, runtime service, product behavior, or production mutation behavior in this plugin.
- Upstream Spec Kit skill vendoring in this plugin.
- Generic deploy wording for `local_cd` or `kubernetes_deployment` entities.
- Sample, example, or illustrative policy sections in governed policy surfaces.
- Restricted-data reads, output, storage, commits, docs, tests, or packets.

## Token/context cost rule

A change that increases token cost must state the payoff in `cost_justification_if_any`. Added gates, documents, roles, branches, or handoffs without payoff fail closed.

## Agent simplification rule

A change must reduce future agent ambiguity, repeated file reads, repeated human explanation, workflow mode inference, or handoff size. If it cannot, the packet status must be `needs-redesign` or `fail`.

## Reusable evidence rule

A change must leave a repository path, validator, catalog rule, bounded packet, or documented next-action path that future agents can use without chat context.

## Memory citation relevance rule

Final-report packets that use memory must bind each memory citation to one current report claim. Each citation must carry source, line range, note, cited text, and claim. The note must match the cited text. The cited text must directly support the claim. If memory was read and discarded, the packet must state the discard reason instead of adding a citation.

## Human approval boundary rule

Human approval belongs only at real decision boundaries. Routine mechanical checks must be handled by validators, catalogs, packets, or role routes.

## Pass/fail decision outcomes

- Pass when a repeated manual decision becomes a validator, catalog rule, bounded packet, or reusable evidence path.
- Needs redesign when a new gate, role, branch shape, or handoff adds process weight without machine-readable enforcement.
- Fail when token cost rises without justification, the mode is inferred from chat, or the change duplicates an existing rule.

## Boundary checks

- Keep one Bears workflow governance plugin at `/srv/bears/plugins/bears`.
- Keep apps, connectors, MCP servers, runtime services, product behavior, and production mutation paths out of this plugin.
- Keep upstream Spec Kit external to this plugin.
- Start implementation only after exact role coverage exists for the child target.
- Use English artifact text with strict concise entity-bound wording.
- Use `local_cd` or `kubernetes_deployment` when those exact entities are meant.
- Keep restricted data out of reads, output, commits, docs, tests, and packets.
- Sync catalog, validator, README inventory, manifest, docs, and tests when governance claims change.

## Constitution checklist

- Agent work simplified:
- Token/context cost reduced or justified:
- Repeated file reads reduced:
- Future validator/catalog/rule added:
- Reusable evidence path:
- Human decision boundary:
- Failure mode if this is skipped:

## Validator usage

Run `python3 scripts/plugin_constitution.py validate` to check catalog, doc, README, AGENTS, SPEC, manifest, and tests coverage.

Run `python3 scripts/plugin_constitution.py inspect-change --packet <path>` to check a constitution change-check packet. The command prints JSON and exits non-zero when required fields are missing, required fields are empty, deterministic validation evidence is missing for a passing packet, added process weight lacks cost justification, or `status` is not `pass`, `fail`, or `needs-redesign`.

Run `python3 scripts/plugin_constitution.py inspect-final-report --packet <path>` to check memory-citation relevance in a final-report packet. The command prints JSON and exits non-zero when a memory citation lacks a matching claim, when cited text does not support the claim, or when accessed memory was discarded without a discard reason.
