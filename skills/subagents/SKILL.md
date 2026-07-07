---
name: subagents
description: "Independent Bears subagent skill for selecting, starting, constraining, reviewing, and closing helper, L2, L3, critic, and gitflow subagents. Apply directly for subagent policy and from app-dev for L2 helper rules."
---

# Subagents

Required: activate this skill when a Bears workflow must delegate bounded work to subagents.

## Core rules

- Subagent prompts start with `/goal` and include explicit completion criteria.
- Parent context is not inherited unless the task explicitly requires it.
- Each subagent receives one role, one repo/path target, one allowed action set, one forbidden action set, and one closeout format.
- Do not pass secrets, raw logs, raw chats, `.env` values, kubeconfigs, private keys, or production data.
- Reuse long-lived lanes when the nearest `AGENTS.md` requires them.
- Close unused completed agents.

## App-dev helper mode

When `$app-dev` invokes this skill:

- L2 may spawn helpers for metadata lookup, decomposition support, packet drafting, or bounded evidence gathering.
- L2 helpers do not implement product changes.
- L2 helpers do not update GitHub Project or Issue state unless the L2 packet names the exact allowed mutation.
- L2 helpers must return evidence to L2; L2 owns Project/Issue updates and L3 assignment.
- L3 workers implement one task only.
- L3 critics review one task only and never edit files.

## Packet minimum

```json
{
  "schema": "subagents.assignment-packet",
  "version": "1",
  "role": "<subagent role>",
  "level": "L2|L2-helper|L3-worker|L3-critic|gitflow",
  "repo": "<repo path>",
  "target": "<exact paths or issue urls>",
  "allowed_actions": ["<verbs>"],
  "forbidden_actions": ["<verbs>"],
  "completion_criteria": "<exact done condition>",
  "closeout": "<required evidence shape>"
}
```
