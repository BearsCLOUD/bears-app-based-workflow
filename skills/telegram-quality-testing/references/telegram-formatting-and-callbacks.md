# Telegram Formatting and Callback Rules

## Rendering policy

- Use one parse mode per renderer module unless a project has a documented reason.
- HTML is the default for readable bot messages when supported by the existing project.
- MarkdownV2 requires strict escaping; test every dynamic segment.
- `MessageEntity` is preferred when exact spans matter or escaping becomes fragile.
- Do not concatenate untrusted text into formatted messages without escaping or entity isolation.

## Inline keyboard policy

- Button text must describe the action, not the implementation.
- Callback data must be compact, typed, versioned, and namespaced as `<domain>:<version>:<action>[:<opaque>]`.
- Each callback family must declare: namespace, privilege class, actor binding, integrity mode, expiry rule, replay protection, idempotency key, and audit event.
- Integrity is mandatory: use a signed payload or an equivalent server-side state-bound handle; if neither is possible, record a documented exception before release.
- Sensitive actions require auth checks in the handler, not only in button visibility.
- Actor binding must verify that the caller is the allowed actor, tenant, or operator role for the referenced object.
- Expiry and replay protection are mandatory for privileged or long-lived callbacks; reject stale or replayed tokens deterministically.
- Destructive, financial, approval, or operator-control callbacks must use a stable idempotency key tied to the business action.
- Privileged callbacks must emit an audit event with actor, object reference, privilege class, and outcome.
- Handlers must handle stale callbacks and duplicate clicks idempotently.
- Acknowledge callbacks quickly; long work should report progress separately.

## Approval loops

- Telegram approvals may approve bounded actions only after the same preflight, audit, and rollback rules used by non-Telegram control paths.
- Approval callbacks must resolve to a tracked status model such as `pending`, `approved`, `rejected`, `expired`, or `cancelled`.
- Approval owner and rollback/control owner must be explicit in the governing packet before a privileged callback is shipped.
- Never send secrets, raw credentials, or private production payloads through Telegram.
- Use Telegram for status, choices, and approval metadata; use Infisical or approved runtime secret channels for secrets.
