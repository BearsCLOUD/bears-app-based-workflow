# Role start packet

Use this packet shape when a role or subagent starts governed work:

```json
{
  "target": "<exact path or repo>",
  "owner_role": "<@Bears role>",
  "action_path": ["<ordered action>"],
  "evidence_required": ["<file, command output, GitHub, Kubernetes, runtime, or issue ref>"],
  "handoff": "<next owner or closeout lane>"
}
```
