---
name: role-profile-maintenance
description: Apply a repeatable comparison and least-privilege method when a role may need reuse, refactoring, merging, splitting, creation, rejection, or deletion.
---

# Role Profile Maintenance

## Boundary

This skill supplies the comparison method and packet templates. The invoking role owns the operation decision, permission decision, profile content, acceptance decision, edits, and delivered result. `subagents` owns role selection and dispatch.

The invoking role chooses exactly one operation: `reuse`, `refactor`, `merge`, `split`, `create`, `reject`, or `delete`. A caller may request an outcome, but that request is evidence, not the operation decision.

## Request template

```yaml
schema: role-profile-request.v1
task_id: <stable task id>
deliverable: <one objectively checkable result>
task_examples: [<concrete accepted task>]
target_profiles: [<exact role TOML path or none>]
authority_refs: [<ordered instruction refs>]
required_capabilities: [<known required capability or none>]
proposed_permissions: # optional caller constraints; omit when unknown
  allowed: [<action and object>]
  forbidden: [<action and object>]
  ask: [<action requiring confirmation>]
  escalate: [<decision and target>]
```

Require `deliverable`, `task_examples`, `target_profiles`, and `authority_refs`. Do not accept `operation` as an input field. Treat `required_capabilities` and `proposed_permissions` as optional evidence, never as granted capability or a selected decision.

## Method

1. Obtain one deliverable and concrete task examples. Reject a title or technology label without an objectively checkable result.
2. Read the declared profiles and every exact reference to their names.
3. Derive the minimum sandbox, capabilities, and permissions from the deliverable and task examples. Do not add capability for completeness. Apply narrower caller constraints; reject broader proposed permissions without evidence.
4. Compare deliverable, allowed actions, forbidden actions, sandbox, external effects, required capabilities, acceptance criteria, and result fields.
5. Let the invoking role choose one operation using these criteria: `reuse` when an existing profile already owns the deliverable and permission boundary; `refactor` when that owner needs an in-place correction; `merge` when duplicate profiles have the same deliverable and permission boundary; `split` when one profile contains multiple deliverables or permission boundaries; `create` when no existing profile owns the deliverable; `reject` when the request has no objective deliverable, conflicts with authority, or cannot have a safe permission boundary; `delete` when a profile has no remaining deliverable or its ownership moved to an accepted profile.
6. Route one evidence-packet assignment to `primary-source-researcher` only when a current framework API, profile format, capability, permission behavior, or production implementation can change the decision. Keep research read-only and separate facts from design choices.
7. Apply `instruction-hardening` to approved role meaning as a method. Do not copy its procedure into a role profile.
8. Let the invoking role build one profile per deliverable and produce accept, reject, and boundary cases. Put the trigger and specialist identity in `description`; put dependencies, permissions, acceptance criteria, result format, and one declarative example in `developer_instructions`.
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

Read `references/pilot-evals.csv` only when evaluating changes to this skill, `instruction-hardening`, or `instruction-editor`. Expected fields are grader inputs and must not be shown to the evaluated model.
