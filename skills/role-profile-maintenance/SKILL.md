---
name: role-profile-maintenance
description: Evaluate one concrete semantic role-profile create, merge, split, or delete operation requested by the current user.
---

# Role Profile Maintenance

## Boundary

Invoke this skill only when the current user directly requests one concrete semantic role-profile `create`, `merge`, `split`, or `delete` operation.

Keep the operation decision, permission decision, profile content, edits, and delivered result with the invoking `role-profile-architect`.

Require the repo-L2 to supply each prerequisite L3 result before invoking this skill.

Do not invoke this skill for generic assessment, lookup, inferred need, prose cleanup, formatting, file layout, metadata, or cachebuster work.

## Request

Require one `role-profile-request.v1` with a stable task id, sanitized direct-user request ref, requested operation, observable deliverable, concrete task examples, exact target profile refs, ordered authority refs, and known capability constraints.

Reject an agent-authored or inferred request ref.

Treat proposed permissions as evidence rather than granted authority.

## Method

1. Confirm that the current user directly requested the declared concrete operation.
2. Read the declared profiles and every exact reference to their names.
3. Derive the minimum sandbox, capabilities, and permissions from the deliverable and examples.
4. Compare deliverable, allowed actions, forbidden actions, sandbox, external effects, capabilities, completion conditions, and result fields.
5. Select `reuse` when one profile already owns the deliverable and permission boundary.
6. Select `refactor` when the request requires an in-place semantic correction.
7. Select `merge` only when profiles duplicate both deliverable and permission boundary.
8. Select `split` when one profile contains multiple deliverables or permission boundaries.
9. Select `create` only for an explicit creation request when no profile owns the deliverable.
10. Select `delete` only when no deliverable remains or ownership moved to a retained profile.
11. Select `reject` when the request lacks an observable deliverable, conflicts with authority, or cannot have a bounded permission surface.
12. Return `RESEARCH_REQUIRED` only when a current external fact can change the decision.
13. Keep supplied public-source facts separate from design choices.
14. Apply `$instruction-hardening` after semantic meaning and permissions are decided.
15. Keep structured identity, capabilities, runtime controls, and behavior in the authoritative JSON definition.
16. Use the fixed renderer for derived TOML and never consume raw TOML as authoritative input.
17. Apply reversible in-scope local changes without another permission gate when the user requested them.
18. Ask before an external write, an unrecoverable destructive action, a purchase, or material scope expansion.

## Constraints

- Derive a role name from its deliverable.
- Exclude organization names, usernames, hostnames, addresses, ports, absolute paths, internal endpoints, environment names, and local responsibility labels.
- Keep a public product or protocol name only when it defines the deliverable.
- Never create aliases for removed names.
- Reuse an existing skill before proposing another skill.
- Require a plugin, tool, or MCP server only when an example cannot produce the deliverable without it.
- Separate roles when network, external write, secret access, install, commit, push, or sandbox permissions differ.

## Result

Emit one `role-profile-result.v1` with the task id, decision, changed and removed profile refs, changed reference refs, required skill and plugin refs, minimum permissions, evidence refs, selection cases, rejection cases, boundary cases, confirmation state, and reload state.

Read `references/pilot-evals.csv` only when evaluating this skill or `$instruction-hardening` and never expose its grader fields to the evaluated model.
