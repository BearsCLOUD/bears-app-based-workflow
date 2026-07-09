# Role Catalog

## Purpose

Provide self-contained role names for app-dev handoff packets. This catalog avoids dependency on an external role inventory.

## Default roles

| Role | Use for | Critic pair |
| --- | --- | --- |
| `implementation-owner` | bounded code or doc implementation | `reviewer` |
| `documentation-engineer` | workflow docs, contracts, templates, README, SPEC | `reviewer` |
| `instruction-reviewer` | skill prose, prompts, dispatch packets, hardening output | `reviewer` |
| `security-reviewer` | secrets, auth, permission, network, or deploy-sensitive work | `implementation-owner` |
| `evidence-reader` | reading existing generated evidence and closeout notes | `reviewer` |
| `reviewer` | correctness, consistency, risk, and regression review | none |

## Rules

- Use the narrowest role that matches target paths and proof requirements.
- Use `role_gap` when no listed role fits.
- Do not fetch or require an external role inventory.
- Do not create a new role unless the constitution records the capability or gap that needs it.
