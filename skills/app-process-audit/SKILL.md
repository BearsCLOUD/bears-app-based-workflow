---
name: app-process-audit
description: Run a read-only semantic audit of process causality, transitions, ownership, app-dev lifecycle, and terminal candidates.
---

# App Process Audit

This is a lower-level read-only operation, not a workflow stage or product acceptance. Continue pagination until `next_cursor` is absent; any truncated result is incomplete. Run the handoff profile before every handoff and the terminal profile in `app-analyze`.

Route missing source to `needs-research`; product or decision conflict to `needs-spec`; semantic ref or causal-cycle gaps to `needs-graph`; task, implementation, evidence, review, or remediation gaps to `needs-plan`; and credential, access, or operator stop to `blocked`. Only an exact build with complete process and convergence audits, no routable findings, and no open remediation task may produce `audited`.
