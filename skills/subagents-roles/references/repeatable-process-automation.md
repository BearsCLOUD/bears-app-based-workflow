# Repeatable process automation

Repeated gates, checks, refactors, reviews, metrics, issue flows, and sync steps use an executable owner.

Owner types:
- autoCI: automatic verification line.
- autoCD: automatic install, update, or deploy line.
- hook: Codex hook with a fixed command surface.
- script: repo-local deterministic command.
- workflow: GitHub or plugin workflow definition.
- `@Bears` role, skill, or subagent flow for AI-context work.
