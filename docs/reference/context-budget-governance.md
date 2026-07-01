# Context budget governance

This surface closes #418.

## Data rule
Every skill, role, catalog, schema, and reference surface gets a compact context-surface record with estimated tokens, authority class, section count, and split policy.

## Commands
- `scripts/context_budget.py scan --json` scans current plugin surfaces.
- `scripts/context_budget.py validate` validates catalog and required commands.
- `scripts/context_budget.py surface --path <path> --json` emits one surface record.
- `scripts/skill_surface.py split-decision --path <path> --json` decides keep, index, or split.
- `scripts/skill_surface.py doctor --json` validates split governance.

## Rules
Oversized surfaces must have an index or split decision. Mixed-authority surfaces must split. Role prompt generation may use `select-sections` to include bounded sections only.
