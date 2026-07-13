---
name: role-profile-maintenance
description: Evaluate a concrete semantic role-profile create, merge, split, or delete operation directly requested by the current user.
---

# Role Profile Maintenance

## Boundary

This skill supplies the comparison method and packet template only when the current user directly requests one concrete semantic role-profile `create`, `merge`, `split`, or `delete` operation. The invoking `role-profile-architect` owns the operation decision, permission decision, profile content, acceptance decision, edits, and delivered result. `subagents` owns deterministic selection and `dispatch-packet.v2` dispatch.

The direct current-user request is mandatory evidence, not a predetermined decision. While evaluating it, the invoking role chooses exactly one result from `reuse`, `refactor`, `merge`, `split`, `create`, `reject`, or `delete`. `reuse`, `refactor`, and `reject` are outcomes, not skill triggers. A `create` result is permitted only when the current user expressly requested creation of a concrete role profile.

Do not invoke this skill for generic profile assessment, lookup, inferred need, prose or rule refactoring, formatting-only edits, prose cleanup, file layout normalization, cachebuster changes, or non-semantic metadata rewrites. Route bounded read-only assessment to `explorer` and ordinary bounded edits to `worker` through the ordered `subagents` rules.

## Request template

```yaml
schema: role-profile-request.v1
task_id: <stable task id>
current_user_request_ref: <sanitized direct request ref>
requested_operation: create|merge|split|delete
deliverable: <one objectively observable result>
task_examples: [<concrete accepted task>]
target_profiles: [<exact role definition JSON path or none>]
authority_refs: [<ordered instruction refs>]
required_capabilities: [<known required capability or none>]
proposed_permissions: # optional caller constraints; omit when unknown
  allowed: [<action and object>]
  forbidden: [<action and object>]
  ask: [<action requiring confirmation>]
  escalate: [<decision and target>]
```

Require `current_user_request_ref`, `requested_operation`, `deliverable`, `task_examples`, `target_profiles`, and `authority_refs`. Reject a request ref that is agent-authored, inferred, or does not show the current user's concrete operation. Treat `required_capabilities` and `proposed_permissions` as optional evidence, never as granted capability or the selected result.

## Method

1. Confirm from `current_user_request_ref` that the current user directly requested the declared concrete `create`, `merge`, `split`, or `delete` operation. Otherwise do not invoke this skill. Require one deliverable and concrete task examples; reject a title or technology label without an objectively observable result.
2. Read the declared profiles and every exact reference to their names.
3. Derive the minimum sandbox, capabilities, and permissions from the deliverable and task examples. Do not add capability for completeness. Apply narrower caller constraints; reject broader proposed permissions without evidence.
4. Compare deliverable, allowed actions, forbidden actions, sandbox, external effects, required capabilities, acceptance criteria, and result fields.
5. Evaluate the direct request and choose one result using these criteria: `reuse` when an existing profile already owns the deliverable and permission boundary; `refactor` when the requested operation instead requires an in-place semantic correction; `merge` when duplicate profiles have the same deliverable and permission boundary; `split` when one profile contains multiple deliverables or permission boundaries; `create` only for an express current-user creation request when no existing profile owns the deliverable; `reject` when the request has no objective deliverable, conflicts with authority, or cannot have a safe permission boundary; `delete` when a profile has no remaining deliverable or its ownership moved to an accepted profile.
6. Return `RESEARCH_REQUIRED` only when a current framework API, profile format, capability, permission behavior, or production implementation can change the decision. The caller may create a separate read-only `primary-source-researcher` assignment through `subagents`, then start a new role-maintenance assignment with the evidence ref. Keep research facts separate from design choices.
7. Apply `instruction-hardening` as the method for converting approved semantic meaning into compact role rules. Do not copy its procedure into a role profile.
8. Let the invoking role build one profile per deliverable and produce accept, reject, and boundary cases. Put structured identity, capabilities, runtime controls, and behavior in the authoritative JSON definition; use the fixed renderer to produce TOML and never accept raw TOML input.
9. When the user requested changes, apply reversible in-scope local edits and exact reference updates without another approval gate. Require confirmation only for external writes, destructive actions without a declared recovery path, purchases, or material scope expansion. A version-controlled in-scope local edit or deletion is reversible.

## Naming and capability constraints

- Build a role name from its deliverable.
- Exclude organization names, usernames, hostnames, IP addresses, ports, absolute paths, internal endpoints, environment names, deployment contours, and local responsibility labels.
- Keep a public product or protocol name only when it defines the deliverable.
- Do not create aliases for removed names.
- Reuse an existing skill before proposing another skill.
- Require a plugin, tool, or MCP server only when a task example cannot produce the deliverable without it.
- Separate roles when network, external write, secret access, install, commit, push, or sandbox permissions differ.

## Result template

The invoking role owns and emits the result instance:

```yaml
schema: role-profile-result.v1
task_id: <same task id>
decision: reuse|refactor|merge|split|create|reject|delete
profiles_changed: [<exact path or none>]
profiles_removed: [<exact path or none>]
references_changed: [<exact path and old/new name or none>]
skill_refs: [<required skill or none>]
plugin_refs: [<required plugin or none>]
permissions:
  allowed: [<derived minimum action and object>]
  forbidden: [<action and object>]
  ask: [<action requiring confirmation>]
  escalate: [<decision and target>]
evidence_refs: [<primary source or none>]
accept_cases: [<task that must select the profile>]
reject_cases: [<task that must not select the profile>]
boundary_cases: [<task requiring another profile or decision>]
confirmation_required: true|false
reload_required: true|false
```

Read `references/pilot-evals.csv` only when evaluating changes to this skill or `instruction-hardening`. Expected fields are grader inputs and must not be shown to the evaluated model.
