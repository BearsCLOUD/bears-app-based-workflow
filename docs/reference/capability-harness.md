# Capability Harness

## Scope

`scripts/capability_harness.py` measures deterministic @Bears workflow capability from L1 to L7 with local fixtures and read-only facts.

## Single level run

Run one fixture level with an exact task id:

```bash
python3 scripts/capability_harness.py run-level \
  --level L7 \
  --task l7_coordinate_subagents \
  --mode bootstrap_plus_subagents \
  --policy fixture \
  --json
```

Expected success output:

- `status: pass` means the deterministic harness scenario passed.
- `validation_status: pending_local_commit_validation` means closeout is still blocked until local validation evidence exists.
- `closeout_allowed: false` prevents the harness from treating fixture quality as production acceptance.

## Full L1-L7 matrix

Run every fixture level deterministically:

```bash
python3 scripts/capability_harness.py run-matrix \
  --mode bootstrap_plus_subagents \
  --policy fixture \
  --json
```

`validate-matrix` is an alias with the same arguments:

```bash
python3 scripts/capability_harness.py validate-matrix \
  --mode bootstrap_plus_subagents \
  --policy fixture \
  --json
```

The matrix command fails with a non-zero exit code when catalog validation, a level run, report writing, or report schema validation fails.

## Stub compatibility

The harness also supports the L0-L3 stub fixture for issue #451:

```bash
python3 scripts/capability_harness.py run \
  --scenario l2_doc_only_stub_patch_auto_close \
  --executor stub \
  --json
```

```bash
python3 scripts/capability_harness.py run-matrix \
  --levels L0,L1,L2,L3 \
  --executor stub \
  --json
```

`report --latest --json` reads the latest saved report for either path.

## Usage ledger

`usage_ledger.v1.jsonl` has one JSON row per run in single-level mode and one row per level in matrix mode.

Key fields:

- `run_id` — deterministic run identifier for the report set.
- `issue_task_id` — task or fixture id used for measurement.
- `level` — capability level from `L1` to `L7`.
- `model_executor` — executor profile that produced the row.
- `input_estimated_tokens` and `output_estimated_tokens` — local token estimates.
- `wall_time_ms` — measured local duration; fixture matrix uses `0` for stable output.
- `files_read` and `files_changed` — bounded file evidence for the task.
- `tools_called` — deterministic tool labels used by the harness.
- `external_facts_count` — sourced facts attached to the run.
- `failure_class` — `none` or the blocking class.
- `result_quality_score` — deterministic estimate, not production proof.
- `validation_status`, `closeout_allowed`, `quality_score_basis` — guard fields that prevent false closeout.

## Cost quality summary

`cost_quality_summary.v1.json` aggregates the ledger rows:

- `total_input_estimated_tokens` — sum of input estimates.
- `total_output_estimated_tokens` — sum of output estimates.
- `total_estimated_tokens` — total estimated usage.
- `average_quality_score` — mean deterministic quality score.
- `run_count` — number of ledger rows.
- `best_mode` — highest scoring mode in the report set.

Use this file for cost-vs-quality comparison only. It is not release or closeout proof.

## Report paths

Each run writes under:

```text
runtime/capability-harness/<run_id>/
```

Required report files:

- `capability_progress.v1.json`
- `usage_ledger.v1.jsonl`
- `cost_quality_summary.v1.json`
- `capability_report.v1.json`
- `matrix_report.v1.json` for matrix runs
