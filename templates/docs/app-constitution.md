# App Constitution

## Functional summary

- App target: `<app-id-or-path>`
- Source-of-truth rule: this file owns functional capabilities, gaps, decisions, constraints, and evidence needs for the workflow.

## Core capabilities

| ID | Capability | Owner | Evidence need | State |
| --- | --- | --- | --- | --- |
| `capability-id` | `<behavior>` | `<role-or-owner>` | `<doc/source/evidence>` | `accepted|gap|blocked` |

## Actors and runtime surfaces

- `<actor>` uses `<surface>` for `<goal>`.

## Constraints and evidence

- `<constraint-id>`: `<constraint>`; evidence: `<evidence-ref>`.

## Functional gaps

| ID | Gap | Impact | Evidence | Route |
| --- | --- | --- | --- | --- |
| `gap-id` | `<missing-or-drifted-functionality>` | `<impact>` | `<source>` | `app-research|app-plan` |

## Open decisions

| ID | Decision | Blocks | Owner |
| --- | --- | --- | --- |
| `decision-id` | `<question>` | `<capability-or-gap>` | `<owner>` |

## Host policy notes

- `<optional live-session constraint; not functional truth>`

## Next skill

- `<app-research|app-plan>`
