---
name: bears-plugin-update
description: "Use for @Bears plugin updates: route policy ownership, use skill-local config, keep target facts in target surfaces, and rely on CI/local-commit checks for validation."
---

# Bears Plugin Update

This skill governs shared `@Bears` plugin update work. Skill-local config lives in `plugin-update.config.v1.json`; its schema lives in `plugin-update.config.v1.schema.json`.

## Plugin Update Gate

Classify every changed fact into one owner surface from `plugin-update.config.v1.json`:

- `central_plugin_config` for shared plugin policy, catalogs, role profiles, hooks, scripts, generated inventory, governance schemas, contracts, prompts, capabilities, tests, and skill workflow rules.
- `target_agents_md` for one target repo or path rule: ownership, forbidden paths, source-of-truth pointers, workflow entrypoints, repo responsibility, path responsibility, or app-directory responsibility.
- `target_codex` for materialized Codex runtime behavior scoped to one target: repo-local agents, skill wrappers, prompts, config, or local Codex behavior.

Proceed with this skill only for `central_plugin_config` facts. Route `target_agents_md` facts to the target `AGENTS.md`. Route `target_codex` facts to the target `.codex/` surface.

## Workflow

1. Load `plugin-update.config.v1.json`.
2. Classify each changed fact into exactly one owner surface.
3. Record expected route/audit ownership for each exact changed path from
   catalog and current-file evidence. Do not run route/audit manually unless
   the operator names the exact command in the current turn.
4. When a configured trigger path changes and no configured exemption matches, perform sequential audit-review before implementation edits.
5. Build the audit manifest from git-tracked files plus untracked-unignored files under the plugin root, sorted by path.
6. Classify manifest entries as `text_file`, `generated_file`, `directory`, or `binary_or_non_text`.
7. Review text files line by line against the current subagents roles and this skill.
8. Record directory child inventory and generated-file generator source.
9. Add only implementation tasks found by the audit-review; keep existing tasks unchanged.
10. Sync generated plugin inventory when the skill catalog changes.
11. Use CI/local-commit validation as blocking check evidence. Route/audit output is ownership evidence only.

## JSON Packet

Sequential audit-review returns one JSON packet:

```json
{
  "schema": "bears-plugin-update.audit-packet.v1",
  "changed_targets": [],
  "reviewed_files": [
    {
      "path": "relative/path",
      "kind": "text_file",
      "reviewed_line_ranges": [{"start": 1, "end": 1}],
      "constitution_alignment": "aligned",
      "update_skill_alignment": "aligned",
      "owner_surface": "central_plugin_config",
      "drift_items": []
    }
  ],
  "reviewed_line_ranges": [],
  "drift_items": [],
  "planned_tasks_added": []
}
```

Packet field requirements are defined in `plugin-update.config.v1.json`.

## Report

Report changed files, owner-surface classification, route/audit result, CI/local-commit validation source, and carried unrelated dirty paths.
