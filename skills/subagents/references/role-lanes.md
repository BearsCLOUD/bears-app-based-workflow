# Subagent role lanes

Use exact @Bears role TOMLs from `the @Bears plugin checkout/agents`.

## L2 orchestration lanes

- `bears-development-workflow-orchestrator`: broad development split and assignment packets only.
- `bears-github-project-issues-orchestrator`: GitHub Projects, Issues, PR metadata, Actions metadata, Releases metadata, labels, milestones, discussions, and planning state only.
- `l2-platform-domain-orchestrator`: platform domain assignment review.
- `l2-gitops-domain-orchestrator`: GitOps domain assignment review.
- `l2-infra-domain-orchestrator`: infrastructure domain assignment review.
- `l2-product-infra-domain-orchestrator`: product-infra domain assignment review.

L2 orchestrators may create L3 assignments and role-gap blocker packets. They must not implement code, edit repo payload, commit, push, deploy, or read restricted data.

## L3 execution lanes

Pick the exact primary role returned by `subagents_roles.py route` and `audit`. L3 workers use `gpt-5.4-mini` with `high` reasoning unless the operator explicitly names another model. Keep each L3 slice to one repo, one issue/project item set, one measurable output, and one validation path.

## GitHub planning lanes

Use GitHub Projects for cross-repo planning views and fields. Use Issues for tracked implementation units. Use Pull Requests for code-review state. Use Actions for status metadata. Use Releases for versioned delivery state. Use Discussions only for non-actionable transparent conversation.
