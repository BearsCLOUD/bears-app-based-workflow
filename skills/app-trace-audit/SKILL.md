---
name: app-trace-audit
description: Run a read-only semantic, planning, or convergence audit over exact structured graph refs and digests.
---

# App Trace Audit

This is a lower-level read-only operation, not a workflow stage or product acceptance. `semantic` is owned by `app-functional-graph`, `planning` by `app-plan`, and `convergence` by `app-analyze`. Require every active requirement to have an exact-digest chain `spec -> decision -> requirement -> functionality or behavior -> task -> code -> test -> evidence` at the applicable profile boundary.

Continue opaque-cursor pagination until no cursor remains. A truncated or incomplete result never authorizes `audited`. Route findings through the workflow definition; never execute tests or reinterpret autoCI evidence.
