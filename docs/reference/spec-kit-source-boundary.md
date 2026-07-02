# Spec Kit source boundary

This repository owns the Bears workflow-governance overlay at `/srv/bears/plugins/bears` and the policy for ignored generated `.specify` workspace state.

Upstream Spec Kit skills remain external at `/srv/bears/.agents/skills`. This plugin may define how `.specify` scripts, templates, workflow registry, integration metadata, and constitution are generated, but it must not track generated `.specify` files. It must not vendor upstream `speckit-*` skills, create a second Bears governance plugin, or add product app, connector, MCP server, runtime service, product behavior, or production mutation surfaces.

Workspace-level source-boundary contracts may exist outside this source repository. They are advisory references only unless their rule is mirrored in this repo-local README, SPEC, catalog, validator, workflow, or test surface.

## Spec Kit analysis findings

Spec Kit 0.11.5 shows these concrete behavior points:

- `specify init` installs ignored generated project files from the bundled CLI package and records integration state under `.specify/`.
- Core commands read generated `.specify/memory/constitution.md` before producing or updating feature artifacts.
- Core command order is constitution, specify, clarify, plan, tasks, analyze, implement, with pre-command and post-command extension hooks.
- Feature specification stays technology-agnostic and user-outcome focused.
- Planning converts approved requirements into research, data model, contracts, quickstart, and agent-context updates.
- Task generation is user-story ordered, file-path specific, and marks parallel work only for disjoint files.
- Workflow execution records state, supports resume/status JSON, gate detail, `continue_on_error`, and parsed JSON shell output.
- Extensions, presets, bundles, and integrations are catalog-managed and project-installed instead of hardcoded into one command path.
- The `agent-context` extension can update multiple context files; this repo disables it because `AGENTS.md` is a governed router.

## Research decision

Decision:

- Keep Spec Kit as an external upstream command-skill and CLI layer.
- Keep `.specify/` as ignored generated Spec Kit workspace state.
- Keep Bears governance behavior in the plugin functionality layer.

Rationale:

- Spec Kit separates reusable CLI infrastructure from initialized project files.
- Spec Kit commands read project constitution before generating spec, plan, and task artifacts.
- Bears role gates must remain the authority for plugin write scope and implementation handoff.

Alternatives considered:

- Vendor upstream `speckit-*` skills into this plugin. Rejected: it creates a forked upstream layer and widens plugin authority.
- Let `agent-context` update `AGENTS.md`. Rejected: `AGENTS.md` is a governed router and requires explicit role-gated mutation.
- Store Spec Kit analysis only in chat. Rejected: future agents need repo-file evidence.

Risks and constraints:

- Spec Kit upgrades may change extension hook behavior or integration manifests.
- Tracked `.specify/` generated files can widen future agent behavior if ignore rules are removed.
- Broad generated artifacts can mix plugin behavior with project feature state unless source and target layers are named.

Validation implications:

- Run `python3 scripts/platform_roles.py route <target>` and `python3 scripts/platform_roles.py audit <target>` before governed writes.
- Local commit validation owns plugin repo validators and tests after plugin governance changes. GitHub Actions is operator-dispatched diagnostics only.
- `scripts/validate_overlay.py` fails in CI when Git tracks `.specify/**` as plugin source.

Sources inspected:

- Installed CLI: `/home/ai1/.local/bin/specify`, version `0.11.5`.
- CLI package: `/home/ai1/.local/share/uv/tools/specify-cli/lib/python3.11/site-packages/specify_cli/`.
- Core commands: `specify_cli/core_pack/commands/{constitution,specify,clarify,plan,tasks,analyze,implement}.md`.
- Project templates: `specify_cli/core_pack/templates/`.
- Workflow engine: `specify_cli/workflows/`.
- Integration state: `specify_cli/integration_state.py`.
- Extension commands: `specify_cli/extensions/_commands.py`.

## Principles derived from Spec Kit

Functional principles:

- Bundled project infrastructure: the CLI owns reusable templates, scripts, workflow definitions, and integration adapters; a project may generate an ignored `.specify` copy.
- Integration adapter boundary: each coding agent integration maps shared Spec Kit commands into that agent's command or skill format without changing the core workflow contract.
- Catalog composition: extensions, presets, workflows, and bundles extend the project through manifests and catalogs, not through hidden global state.
- Managed-file accountability: integration state and manifests record installed files so upgrades can preserve local settings and report skipped or changed files.
- Hook containment: extension hooks run around explicit Spec Kit events and must stay optional, ordered, and inspectable.

Workflow principles:

- Constitution first: project principles constrain every later spec, plan, task, and implementation artifact.
- Intent before implementation: the spec captures user journeys, acceptance scenarios, measurable outcomes, assumptions, and unclear requirements before technical planning.
- Artifact chain separation: `spec.md` states the user need; `plan.md` states technical context and design; `tasks.md` states ordered file-level work.
- Clarification limit: agents should ask only for decisions that block correctness, safety, scope, or user experience.
- Independent delivery slices: tasks are organized by user story so one story can be implemented and validated without completing all stories.
- Deterministic workflow state: workflow runs, gates, JSON output, and resume/status commands make automation state inspectable.
- Analyze before implement: cross-artifact drift is checked before implementation starts.
- Parallelism by file boundary: parallel tasks are valid only when paths are disjoint and dependencies are clear.

## Bears layer split

Plugin functionality layer:

- Owns Bears role gates, validators, catalogs, workflow policy, skills, schemas, and plugin documentation.
- May adapt Spec Kit templates for Bears governance checks.
- Must not become an upstream Spec Kit fork, product app, connector, MCP server, runtime service, product feature, or production mutation surface.

Generated Spec Kit layer:

- Owns ignored generated `.specify/` scripts, templates, workflow registry, integration metadata, constitution, and generated feature artifacts.
- May record route packets, audit packets, validation commands, operator decisions, and restricted-data boundaries.
- Must not create plugin capabilities or modify `AGENTS.md` through hooks.

Validation entrypoint: `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`.
