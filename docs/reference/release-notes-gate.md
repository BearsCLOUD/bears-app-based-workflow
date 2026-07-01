# Release Notes Gate

The release notes gate requires a machine-readable release note for plugin changes that alter behavior.

## Authority

- `assets/catalog/release-notes-gate.v1.json` catalogs behavior-changing path patterns.
- `assets/catalog/release-notes.v1.json` stores release notes entries and explicit exemptions.
- `assets/schemas/release-notes.v1.schema.json` defines entry and exemption fields.
- `scripts/release_notes_gate.py` validates the catalog, release notes file, fixtures, and changed-file coverage.

## Required entry fields

Each entry must include:

- `date`
- `issue_ref`
- `impact`
- `validation`
- `affected_surfaces`
- `files`

Each exemption must include `date`, `issue_ref`, `reason`, and `files`.

## Local validation

`local_commit_validation.py` runs `scripts/release_notes_gate.py check` for the commit range. A matched behavior-changing file must be covered by a release note entry or by an explicit exemption.
