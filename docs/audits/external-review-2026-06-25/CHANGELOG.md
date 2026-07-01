# External Review Package Changelog

## 2026-06-25

### Added

- Added repo-visible external review package under `docs/audits/external-review-2026-06-25/`.
- Added issue-state audit artifact for external review of covered issue closeout.
- Added changelog/release-note audit artifact for behavior-changing delivery records.
- Added decision audit artifact for governance and workflow decision records.
- Added machine-readable audit index at `audit-index.v1.json`.
- Added issue link artifact for #425.

### Review impact

External reviewers can now inspect the audit requirements from committed repository files instead of relying on chat, agent memory, or ignored runtime files.

### Remaining blocker

This package is visible, but validator enforcement is not complete until #425 and related closeout issues are implemented.
