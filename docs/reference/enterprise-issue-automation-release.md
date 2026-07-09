# Enterprise Issue Automation Release

The release manifest is `assets/catalog/enterprise-issue-automation-release.v1.json`.

Canonical identity is not issue-specific. `release_id` and `delivery_id` must both equal `bears-governance-kernel-v1`, the canonical value from `assets/catalog/commit-closeout.v1.json`.

The dependency order is fixed:

`#394 -> #390 -> #384 -> #385 -> #395 -> #396 -> #397 -> #398 -> #399 -> #400 -> #401 -> #403 -> #402`.

Release rules:

- keep one release manifest for this enterprise automation release;
- keep `max_active=1`;
- keep `completed_issues` as a prefix of `issue_order`;
- keep `active_issue` equal to the next issue after `completed_issues`;
- hooks must not solve issues or run issue `codex exec` work;
- services or timers may be templated later, but must not auto-install;
- issue closeout uses the canonical delivery id only.
