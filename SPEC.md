# Bears plugin spec

## Package rule
`@Bears` stores one automatic CD executor, two contract-shape JSON files, and one MCP design skill.

## Retained files
- `.codex-plugin/plugin.json`
- `.agents/plugins/marketplace.json`
- `scripts/bears_auto_cd.py`
- `assets/catalog/git-deploy-contract.v1.json`
- `assets/catalog/cd-kube-deploy-contract.v1.json`
- `skills/mcp-designer/**`

## Skill rule
`skills/mcp-designer/` is an active Codex skill for MCP surface design and review. It is not workspace instruction authority and does not override `AGENTS.md` or non-plugin contracts.

## Excluded files
The plugin must not contain role prompts, hooks, workflows, issue templates, or generated inventories.
