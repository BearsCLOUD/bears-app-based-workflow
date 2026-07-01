# Goal Prompt Best Practices

This file separates sourced facts from Bears-specific inference so the goal-prompt role stays honest about what comes from current Codex guidance and what comes from local governance policy.

## Purpose

Use this reference when the `/goal` generator needs a stronger quality bar, clearer anti-patterns, or trigger-specific overlays. Keep official Codex guidance primary, OpenAI GitHub examples secondary, and local Bears policy explicit.

## Official Codex facts

Current Codex docs support these stable rules:

- `/goal` is for long-running work where Codex should keep pursuing one durable objective across turns.
- A good goal is bigger than one prompt but smaller than an open-ended backlog.
- Good goals define what Codex should achieve, what it should not change, how it should validate progress, and when it should stop.
- If the goal is hard to define up front, start with `/plan` first and let Codex refine the goal.
- Goal objectives must be non-empty and at most 4,000 characters; longer detail should live in a file that the goal points to.

These facts support a generator that insists on one concrete objective, explicit completion criteria, explicit non-goals, and validators that can actually be run.

## OpenAI GitHub reinforcement

The OpenAI `define-goal` skill adds practical heuristics that help a generator role:

- confirm that goal definition is actually needed instead of forcing goal mode onto normal implementation work;
- restate the goal in concrete terms: outcome, target surface, verification method, in-scope surface, out-of-scope surface, and stop condition;
- repair vague goals before setting them;
- reject pure activity goals such as `make progress`, `keep investigating`, or `improve things` unless sharpened into a verifiable outcome.

These heuristics justify asking one concise clarification question when scope, truth, or validation is missing.

## Community heuristics

Community `/goal` guides are non-authoritative, but they consistently reinforce a compact contract shape:

- objective with a crisp definition of done;
- ordered truth sources;
- bounded scope and explicit non-goals;
- exact validation steps;
- short status and closeout expectations.

Community guidance also warns that `/goal` is not a safety boundary and should not replace sandbox, approval, role-gate, or repo-readiness discipline.

## Bears-local policy overlay

The generator should add Bears policy only as local governance inference, not as official Codex fact:

- Generated goal prompts are control contracts, not memory or truth. The truth layer must point to authoritative files, docs, issues, commands, or runtime checks.
- Add role coverage whenever work touches shared platform surfaces.
- Treat missing role coverage as `ROLE_COVERAGE_BLOCKER`.
- Preserve shared spine order `auth_core -> bears_gateway -> cd_deploy_stage` unless the operator explicitly narrows scope.
- Add no-secret, no-raw-log, no-production-data, and no-production-mutation constraints to every Bears-generated `/goal`.
- Never claim marketplace/plugin state is already clean unless the truth layer proves it; require checking exact local marketplace entry count and names.


## Anti-patterns

Reject or rewrite prompts that:

- ask Codex to `improve`, `continue`, or `investigate` without a finish line;
- bundle unrelated work into one backlog-shaped goal;
- invent truth-layer facts instead of naming sources;
- blur truth sources with execution-control policy;
- omit exact validators, independent audit, or completion evidence;
- omit forbidden scope, non-goals, or blockers;
- ask Codex to decide product, architecture, or approval questions silently during the run;
- exceed the goal-length budget when a referenced file would be safer;

## Forward-test scenarios

Use this stable scenario set when comparing prompt variants.

### General normal case

Input:

- "Turn the auth package from Pydantic v1 to v2, keep current public imports working, and prove it with the existing auth test suite."

Expected behavior:

- generate a `/goal` prompt directly;
- name the exact target package and tests;
- include truth layer, stop conditions, validation, and independent audit;
- no clarification needed.

### General edge case

Input:

- "Do the whole auth + gateway + deploy core migration and make it production-ready."

Expected behavior:

- refuse a single broad `/goal` as-is;
- either narrow to one spine stage, split explicit worker lanes with dependencies, or recommend `/plan` first;
- keep production mutation out of scope unless explicitly approved.

### General failure case

Input:

- "Improve Bears platform quality."

Expected behavior:

- mark it as not goal-ready;
- ask one concise question about the missing validator, target surface, or truth source, or recommend direct `/plan` first;
- do not fabricate scope or acceptance criteria.


## Sources

Official:

- Codex follow-goals use case: https://developers.openai.com/codex/use-cases/follow-goals
- Codex CLI slash commands: https://developers.openai.com/codex/cli/slash-commands#set-or-view-a-task-goal-with-goal

OpenAI GitHub:

- `define-goal` skill: https://github.com/openai/skills/blob/main/skills/.curated/define-goal/SKILL.md

Community heuristics:

- Community guide with concrete `/goal` contract examples: https://raw.githubusercontent.com/davidondrej/jailbreak-autoresearch/main/docs-slash-goal.md
