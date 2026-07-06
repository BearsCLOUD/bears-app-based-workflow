---
name: instruction-hardening
description: "Use to harden human-readable agent instructions, AGENTS routers, skill docs, role TOMLs, and governance prose by preserving semantics, closing bypasses, reducing drift, and scoring diffs with a weighted rubric."
---

# Instruction Hardening

Use this skill when the task is to rewrite, compress, audit, or compare human-readable instructions that govern agent behavior. Human-readable instructions include `AGENTS.md`, `skills/*/SKILL.md`, `agents/*.toml`, role prompts, developer-instruction prose, workflow prose, and directly governing plugin reference docs.

This skill adapts the archived `art-verify` method for Bears governance surfaces.

## Scope

Include only the assigned instruction surfaces:

- `AGENTS.md` routers and nearest path routers;
- active `skills/*/SKILL.md` files;
- `agents/*.toml` role profiles;
- directly governing plugin reference docs named by the assignment.

Exclude unless the operator explicitly expands scope:

- secrets, credentials, `.env` values, raw logs, raw chats, session bodies, production data, and caches;
- runtime, deploy, product, Kubernetes, provider, and network surfaces;
- ordinary README/reference prose that does not govern agent behavior.

## Workflow

1. Load the nearest `AGENTS.md`, this plugin router, the active route packet, and this skill.
2. Identify the exact target files and owner role before edits. Stop on `ROLE_COVERAGE_BLOCKER` unless the assignment is role-coverage remediation.
3. Extract every governing rule as: `mode`, `action`, `object`, `scope`, `condition`, `exception`, and `conflict rule`.
4. Build a canonical term table. One behavior gets one term. Replace weak words or define them in-place.
5. Convert prose into observable rules using these modes only: `Allowed`, `Forbidden`, `Required`, `Ask`, `Escalate`, `Conflict`.
6. Add `Conflict: Deny wins.` unless a stricter local conflict rule already exists.
7. Scan for bypasses before compression:
   - shell wrappers, task runners, test commands, package scripts, CI targets, and indirect commands;
   - broad allow rules overriding narrow denies;
   - hidden secret exposure through logs, env, copied config, or tool output;
   - runtime/deploy/product authority leaking into instruction-only work;
   - vague exceptions such as urgency, one-time use, or user convenience.
8. Close bypasses with compact categories before enumerating tools.
9. Deduplicate repeated policy only after the bypass scan.
10. Compress text only when the shorter wording preserves all required controls.
11. Run the red-team prompts from `references/evaluation-rubric.md` against the proposed policy.
12. Return a diff candidate plus the weighted rubric score.

## Codex exec live-run isolation

Required for every `codex exec` row in an instruction-hardening comparison:

- Startup context is exactly the assigned prompt file plus the selected role file. Only deterministic source delimiters may be added.
- Run from an empty control cwd, not from the target checkout. Add the target isolated worktree with `--add-dir`.
- Use `--ignore-user-config`, `--ignore-rules`, `--ephemeral`, and `--skip-git-repo-check`.
- Record the runner flags, control cwd, target worktree, startup context source paths, and token usage in the result packet.
- Forbidden startup context: inherited user config, project rules, auto-loaded `AGENTS.md`, skill catalog, plugin context, MCP/app context, runtime logs, session history, or copied full files.
- If the local sandbox cannot start, retry only in the same isolated worktree with the explicit sandbox override recorded in the result packet.

Use `scripts/instruction_hardening_exec.py` for governed exec rows. Do not invoke `codex exec` directly for matrix results unless the script is missing or broken and the result packet records the manual command and reason.

## Hard rules

- Delivery first: provide a usable rewritten instruction or diff candidate when the user asked for a rewrite.
- Never reduce tokens by weakening a prohibition, deleting a route owner, or hiding an exception.
- Never let a broad allow override a specific deny.
- Never invent product, runtime, deployment, provider, or secret policy.
- Keep Bears artifacts in English.
- Keep user-facing reports concise and in Russian unless the user asks otherwise.

## Default output

```text
Status: pass | review | blocked
Target files:
- <path>

Diff candidate:
<patch or exact replacement>

Rubric:
- safety_and_bears_compliance: <0-25>
- semantic_preservation: <0-20>
- bypass_closure: <0-20>
- compression_dedup: <0-15>
- scope_coverage: <0-10>
- diff_usability: <0-5>
- efficiency: <0-5>
- total: <0-100>

Changed:
- <semantic merges/removals>

Residual risks:
- <only real remaining ambiguity or none>
```

Use `blocked` only for missing access, missing role coverage, explicit operator stop, forbidden-path risk, secret exposure risk, or an instruction conflict that cannot be resolved within the assigned scope.

## References

- `references/evaluation-rubric.md`
