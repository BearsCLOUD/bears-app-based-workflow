# Telegram Test Matrix

## Required checks by change type

| Change type | Minimum checks |
| --- | --- |
| Message copy or formatting | normalized text/snapshot, dynamic escaping, no secret text |
| Inline keyboard | button count/order, text, callback data schema, stale callback |
| Callback handler | success, denied user, stale state, duplicate click, callback acknowledgement |
| FSM flow | start, valid transition, invalid input, cancel/back, timeout/stale state |
| Command menu | command list, help text, permission visibility |
| Webhook runtime | import/startup, secret-token config path, reverse-proxy assumptions |
| Polling runtime | import/startup, graceful shutdown, no production token in tests |
| Approval loop | preflight result, explicit approval, audit record, rollback or compensation path |

## Test data rules

- Use fake bot tokens and synthetic chat IDs.
- Do not store copied production updates, raw private messages, or real callback payloads.
- Redact logs before using them as fixtures.
- Prefer deterministic builders for Telegram updates over broad golden blobs.

## Evidence closeout

A Telegram change closeout must include commands run, test result, known gaps, and whether any live action was performed. If live action was skipped, say why.
