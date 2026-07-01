# Platform and Telegram Subagent Start Packet

Use this packet when delegating Telegram or platform-part work. Platform work must include a plugin-owned registered role.

```markdown
You are working under /srv/bears. Reply in Russian to the operator only if asked; write repository artifacts in English.
Workspace-map is disabled; use local AGENTS/docs and targeted file reads.
Do not read, print, or commit secrets, .env values, raw tokens, private chat payloads, or production data.

Role: <registered plugin role name>
Role file: /srv/bears/plugins/bears/skills/bears-telegram-workflow/agents/<role>.toml
Platform part: <catalog platform part or not-applicable>
Objective: <one concrete outcome>
Owning path: <absolute path>
Allowed writes: <disjoint file list or read-only>
Forbidden writes: <paths, actions, and data classes>
Trust boundary: <same-repo | shared-platform | cross-repo | runtime-adjacent | prod-adjacent>
Data classes: <public-docs | internal-metadata | private-chat-metadata | redacted-runtime-metadata>
Secret classes: <none | vault-reference | env-derived | runtime-injected>
Approval owner: <operator, team, or not-applicable>
Rollback/control owner: <role, team, or service owner>
Approval status: <not-requested | pending | approved | not-applicable>
Use skill: <absolute skill path or $skill-name>
Read first: nearest AGENTS.md, then relevant SPEC/requirements/plans.
Evidence required: <commands, tests, diff checks, read-only probes>
Reviewer signoff: <required | not-required> and owner
Security signoff: <required | not-required>; required for privileged callbacks, secret handling, cross-trust work, or production-adjacent mutation
Final status: <done | blocked | needs_approval>
Closeout: changed files, validation result, final status, approval status, risks/blockers, no broad summary.
```

## Delegation rules

- Do not assign the immediate blocking task to a subagent if the parent is waiting on it.
- Do not spawn implementation subagents for a platform part until `$platform-role-governance` selects a registered role.
- Do not duplicate another active subagent's write scope.
- Ask reviewers to inspect artifacts, not to rewrite them.
- Use nested subagents only when the child task has a smaller write scope, the child part has a registered role, and the parent subagent remains accountable.
- A child packet must inherit or narrow the parent's trust boundary, data classes, secret classes, approval owner, and rollback/control owner.
- If a child discovers an uncovered platform part, it must return `ROLE_COVERAGE_BLOCKER` and stop implementation edits.
- If privileged callbacks, secret ownership, or production-adjacent control are in scope, the child must return reviewer/security signoff state before integration.
