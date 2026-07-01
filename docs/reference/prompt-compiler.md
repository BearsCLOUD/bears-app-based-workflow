# Prompt compiler

## Scope

The prompt compiler builds zero-context executor prompts from machine-checked Bears inputs only.

Owned files:

- `assets/catalog/prompt-compiler.v1.json`
- `assets/schemas/prompt-compile-request.v1.schema.json`
- `assets/schemas/context-pack.v1.schema.json`
- `assets/schemas/prompt-compile-result.v1.schema.json`
- `scripts/context_pack.py`
- `scripts/prompt_compiler.py`

## Source rules

Allowed prompt inputs:

- accepted semantic facts from the decision graph;
- accepted decision proofs referenced by decision graph nodes;
- accepted inference proofs from the compile request;
- fresh file-context records from `assets/file-context/index.v1.json`;
- role profiles from `assets/catalog/opencode-agent-profiles.v1.json`;
- unlocked and blocked gates from the decision graph;
- task text and required outputs from the compile request.

Blocked prompt inputs:

- chat history;
- arbitrary Markdown reads;
- issue body excerpts as primary authority;
- stale file-context records;
- full file content without accepted L4 proof.

## Context levels

| Level | Content |
| --- | --- |
| L0 | Task and required output only. |
| L1 | Accepted semantic facts, accepted proofs, accepted inference proofs, and gates. |
| L2 | Fresh file-context summaries. |
| L3 | Fresh selected symbols, public interfaces, and contracts. |
| L4 | Full file content only when `allow_full_file_read=true` and an accepted full-file inference proof matches the context. |

## Fail-closed checks

Compilation returns `status=blocked` when:

- request JSON does not match `prompt-compile-request.v1`;
- decision graph is missing or invalid;
- a decision node proof is missing or not accepted;
- a semantic fact is not accepted;
- a selected context is missing or stale;
- the context pack exceeds `max_tokens`;
- prompt text exceeds `max_tokens`;
- L4 is requested without accepted full-file proof;
- role profile is missing.

## Commands

- `python3 scripts/context_pack.py validate`
- `python3 scripts/context_pack.py build --request <path> --json`
- `python3 scripts/prompt_compiler.py compile --request <path> --json`
- `python3 scripts/prompt_compiler.py diff --base <path> --head <path> --json`
- `python3 scripts/prompt_compiler.py doctor --json`

All commands emit JSON. `build` and `compile` exit non-zero for blocked packets.

## Determinism

Packets use sorted keys, sorted context lists, sorted proof identifiers, and SHA-256 hashes over canonical JSON. Network access and live runtime reads are not part of prompt compilation.

## Executor output contract

Every successful compile result includes `required_output_schema`. The executor must return one JSON object with:

- `schema`
- `status`
- `changed_files`
- `validation_commands`
- `blockers`
