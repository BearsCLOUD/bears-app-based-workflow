# Doctor component coverage

`doctor_component_coverage.py` confirms that issue-level validator contracts are represented in `bears_doctor`, test selection, and closeout validation.

## Commands

```bash
python3 scripts/doctor_component_coverage.py validate
python3 scripts/doctor_component_coverage.py scan --repo BearsCLOUD/bears_plugin --json
python3 scripts/doctor_component_coverage.py check-issue --issue 457 --json
python3 scripts/doctor_component_coverage.py diff --base <path> --head <path> --json
python3 scripts/doctor_component_coverage.py doctor --json
```

`scan` reads issue facts through the GitHub CLI or a local fixture. Output is bounded: issue number, title, state, extracted commands/files, coverage status, and gap ids. It does not print raw issue bodies.

## Gap meanings

- `missing_doctor_check`: no required `component_issue` or guard id in `assets/catalog/bears-doctor.v1.json`.
- `missing_validator_command`: a required command is absent from doctor checks.
- `missing_test_selection`: a required file is absent from `assets/catalog/test-selection.v1.json` mappings.
- `closed_issue_still_not_available`: a closed issue still lacks required doctor coverage.
- `unsafe_autostart_without_doctor_gate`: an autostart-safe issue needs doctor coverage before execution.

`not_applicable` is allowed only with explicit catalog evidence.
