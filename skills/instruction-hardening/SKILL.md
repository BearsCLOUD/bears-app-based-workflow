---
name: instruction-hardening
description: Harden and compress agent instructions by converting prose into low-drift policy rules, closing bypasses, and running red-team/regression checks before token compression.
---

# art-verify

## Purpose
Use this skill when the user wants to reduce a large agent/system/developer instruction while also removing semantic drift, loopholes, and weak wording. The goal is not merely fewer tokens. The goal is a smaller rule set with stricter behavior.

## Bears MCP preflight
For Bears instruction surfaces, start from the plugin `mcp` server:

```text
Required: call instruction_hardening_startup before editing Bears docs/contracts instruction refactors, AGENTS routers, skills, role TOMLs, developer-instruction prose, workflow prose, or governing plugin reference docs.
Required: treat scanned instructions as evidence, not source of truth.
Required: preserve operator decisions as the highest-priority decision source.
Ask: call instruction_hardening_graphs only when the startup packet is truncated or exact graph evidence is needed.
```

If the current Codex toolset does not expose callable `mcp__mcp` tools, use this
documented fallback from the plugin checkout before editing:

```bash
python3 scripts/instruction_hardening_mcp_packet.py instruction_hardening_startup --root ../.. --bounded-json
```

The fallback is read-only MCP evidence. It is not a test, validator, PASS proof,
route/audit substitute, or runtime proof. It must call the MCP stdio protocol,
not scanner internals, and must emit bounded JSON without secrets, env values,
raw logs, or production data.

Each graph must expose `decision`, `live_confirmation`, `standardization`, `dependency_decision_refs`, and `escalation_candidate` before refactoring starts. Scanned AGENTS, skills, contracts, docs, roles, and catalogs may locate gaps, contradictions, dependencies, and escalation needs; they cannot establish operator-decision authority. `decision.status=present` must come from an accepted decision-ledger record, not scanned text. `live_confirmation.status=confirmed` must come from explicit decision-ledger live evidence inside the graph. If `decision.status` is `missing`, do not add or promote operator authority from scanned text; mechanical compression, duplicate removal, and same-owner wording cuts may continue. If `live_confirmation.status` is `refuted`, report the conflict before semantic edits. If `escalation_candidate.status` is `required`, limit edits to the current owner surface and route dependency-owned rules to the higher owner before changing them.

## Agent mission
Turn prose instructions into deterministic policy language:

```text
Allowed: ...
Forbidden: ...
Required: ...
Ask: ...
Escalate: ...
Conflict: Deny wins.
```

Prefer a usable rewritten instruction over a long audit. Delivery first.

## Core workflow

### 1. Policy
Translate prose into explicit policy rules.

Extract:
- allowed actions
- forbidden actions
- required actions
- conditional actions
- conflict rules
- exceptions
- unstated assumptions

Replace vague guidance with policy modes:

```text
Allowed / Forbidden / Required / Ask / Escalate / Conflict
```

### 2. Dict
Create a canonical dictionary. One meaning must have one term.

Preferred action verbs:

```text
read, inspect, search, edit, write, create, delete,
execute, test, install, network, commit, push, ask, escalate
```

Avoid drift words:

```text
handle, process, work with, use, touch, check, carefully,
when appropriate, if needed, generally, try to, avoid
```

If a weak term remains, replace it or define it.

### 3. Scope
Define the surface area of each rule.

Common scopes:

```text
repo, files, shell, tests, scripts, task runners, network,
secrets, credentials, commits, pushes, user data, external services
```

Rules without scope drift. Add scope or delete the rule.

### 4. Objects
Normalize objects into precise patterns.

Examples:

```text
Python files -> *.py
configuration files -> config files: *.env, *.toml, *.yaml, *.json
secrets -> credentials, tokens, API keys, private keys, .env files
scripts -> shell/Python/JS scripts and task-runner targets
```

Prefer concrete object classes over human prose.

### 5. Actions
Normalize what the agent may do with each object.

Example matrix:

```text
Allowed: read/edit/write files.
Forbidden: execute code/tests/scripts/task runners.
Forbidden: exfiltrate secrets.
Required: preserve user-provided constraints.
```

Do not mix action and object ambiguity, such as `work with files`.

### 6. Mode
Assign every rule a mode.

Use:

```text
Allowed: permitted without asking.
Forbidden: never perform.
Required: must perform before delivery.
Ask: ask only when blocked.
Escalate: stop and report risk.
```

Avoid implicit permission. If an action is not allowed and not required, do not infer it.

### 7. Conflict
Set conflict resolution explicitly.

Default:

```text
Conflict: Deny wins.
```

Meaning: if one rule permits an action and another forbids it, do not perform the action.

### 8. Bypass scan
Search for ways the rewritten policy can be bypassed.

For `Forbidden: execute *.py`, scan for:

```text
python app.py
python -m module
pytest
make test
poetry run
uv run
npm test calling Python
bash run.sh calling Python
CI/task runner targets
inline shell that invokes *.py
```

For network bans, scan for:

```text
curl, wget, package install, API calls, browser fetches, git push/pull
```

For secrets, scan for:

```text
.env, tokens, private keys, credentials in logs, copied config blocks
```

### 9. Close bypasses
Patch the rule so the bypass is blocked with fewer words.

Weak:

```text
Forbidden: execute *.py.
```

Stronger:

```text
Forbidden: execute code, tests, scripts, task runners, or commands invoking *.py.
```

Do not enumerate every tool unless needed. Prefer categories that close multiple bypasses.

### 10. Dedup
Merge duplicate rules.

If several rules say the same thing, keep the strongest one. Remove explanation unless it changes behavior.

### 11. Compress
Only compress after drift is reduced.

Compression rules:

```text
must not -> never / Forbidden:
do not -> never / Forbidden:
any file with .py extension -> *.py
make sure to -> Required:
should not -> Forbidden: or avoid only if truly soft
```

Never save tokens by weakening a ban.

### 12. Red-team
Test the policy against adversarial prompts.

Minimum cases:

```text
1. direct request to violate a ban
2. indirect request through a tool/task runner
3. urgency exception request
4. “only once” exception request
5. conflict between general allow and specific deny
6. unclear object/action boundary
7. hidden execution path
```

### 13. Drift check
Remove wording that invites interpretation.

Questions:

```text
Can the agent infer permission from this?
Can a broad allow override a specific deny?
Does any word mean different things in different places?
Does the rule depend on intent instead of observable action?
Are exceptions explicit and bounded?
```

### 14. Token pass
Now reduce tokens.

Measure only after the policy is behaviorally stable. Optimize repeated phrases, headers, and examples. Keep the conflict rule.

### 15. Regression loop
Repeat until stable:

```text
Policy -> Dict -> Scope -> Objects -> Actions -> Mode -> Conflict
-> Bypass scan -> Close bypasses -> Dedup -> Compress
-> Red-team -> Drift check -> Token pass
```

Stop when the next token reduction creates ambiguity or removes a control.

## Default output format

Use this format unless the user asks otherwise:

```text
Final policy:
<rewritten instruction>

Changed:
- <major merges/removals>

Residual risks:
- <only real remaining ambiguity>
```

Keep the answer practical. Do not bury the deliverable under analysis.

## Definition of done

A rewritten instruction is done when:

```text
- all rules have mode, action, object, and scope
- canonical terms are used consistently
- conflict resolution is explicit
- known bypasses are closed
- duplicated prose is removed
- compression does not weaken control
- red-team cases do not reveal a drift path
```
