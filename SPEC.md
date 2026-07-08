# Bears plugin spec

## Package rule
`@Bears` stores one automatic CD executor and two contract-shape JSON files.

## Retained files
- `.codex-plugin/plugin.json`
- `.agents/plugins/marketplace.json`
- `scripts/bears_auto_cd.py`
- `assets/catalog/git-deploy-contract.v1.json`
- `assets/catalog/cd-kube-deploy-contract.v1.json`

## Excluded files
The plugin must not contain active or archived skill docs, role prompts, hooks, workflows, issue templates, or generated inventories.
