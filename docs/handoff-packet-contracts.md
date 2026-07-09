# Handoff Packet Contracts

## Purpose

Define reusable packet fields passed between workflow skills. Packets are documentation contracts, not validation software.

## Shared fields

Each packet includes the shared fields that exist at that stage. If a field is not created yet, the packet contract below must mark it not applicable instead of letting a downstream skill infer it.

- `schema`
- `wave_id`
- `constitution_refs`
- `research_refs`
- `plan_task_refs` when a plan task exists
- `graph_node_refs` when graph nodes exist
- `target_paths`
- `owner_skill`
- `next_skill`
- `completion_criteria`
- `drift_notes`

## `wave-research.packet.v1`

Required fields:

- `schema: wave-research.packet.v1`
- `wave_id`
- `scope`
- `constitution_refs`
- `source_refs`
- `decisions`
- `unknowns`
- `clarifications_needed`
- `plan_inputs`
- `next_skill`

## `clarification.packet.v1`

Required fields:

- `schema: clarification.packet.v1`
- `wave_id`
- `research_refs`
- `constitution_refs`
- `closed_questions`
- `actors`
- `flows`
- `data_contracts`
- `error_states`
- `acceptance_criteria`
- `remaining_questions`
- `next_skill`

## `role-packet.v1`

Required fields:

- `schema: role-packet.v1`
- `wave_id`
- `task_id`
- `constitution_refs`
- `research_refs`
- `plan_task_refs`
- `graph_node_refs`
- `target_paths`
- `depends_on`
- `owner_role`
- `critic_role`
- `helper_roles`
- `role_gap`
- `sequential_ready`
- `next_skill`

## `dispatch-packet.v1`

Required fields:

- `schema: dispatch-packet.v1`
- `role`
- `scope`
- `handoff_order`
- `wave_id`
- `task_id`
- `constitution_refs`
- `research_refs`
- `plan_task_refs`
- `graph_node_refs`
- `target_paths`
- `allowed_paths`
- `forbidden_paths`
- `owner_role`
- `critic_role`
- `dependencies`
- `inputs_to_read`
- `expected_edits_or_read_only_output`
- `completion_criteria`
- `definition_of_done`
- `proof_requirement`
- `automation_evidence_policy`
- `ledger_update_contract`
- `closeout_format`
- `drift_notes`
- `next_skill`

`automation_evidence_policy` must name existing generated evidence locations or say `none-required`. It must not request new validation tooling unless a constitution capability explicitly requires that product behavior.

## `hardening-output.v1`

Required fields:

- `schema: hardening-output.v1`
- `wave_id`
- `input_refs`
- `compressed_text`
- `removed_content_summary`
- `behavior_equivalence_statement`
- `drift_notes`
- `next_skill`

## `analysis-audit.packet.v1`

Required fields:

- `schema: analysis-audit.packet.v1`
- `wave_id`
- `target_files`
- `quality_dimensions`
- `file_results`
- `cross_file_findings`
- `broken_links`
- `status`
- `next_skill`

Quality dimensions are usefulness, consistency, brevity, unambiguity, instruction coverage, portability, degradation resistance, continuous-development readiness, and no-test-tooling risk.
