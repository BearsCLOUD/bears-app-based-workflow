# Well-specified agent artifacts

Agent instructions and agent-created artifacts state the target, owner, action path, evidence, and handoff in positive action language.

Required fields:
- Target: exact path, repo, role, skill, script, hook, workflow, or catalog entry.
- Owner: one role profile or executable owner.
- Action path: ordered actions the owner performs.
- Evidence: file path, route/audit packet, ledger output, GitHub evidence, Kubernetes/runtime evidence, or issue URL.
- Handoff: next role, skill, script, autoCI, autoCD, hook, workflow, or issue owner.
