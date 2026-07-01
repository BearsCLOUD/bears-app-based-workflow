# Dagger delivery pipeline

`scripts/dagger_delivery.py` is the delivery wrapper for the local and CI gate order.

## Commands

```bash
python3 scripts/dagger_delivery.py validate
python3 scripts/dagger_delivery.py run --delivery-id <id> --json
```

## Gate order

1. Pipeline catalog validation.
2. #425 external review audit.
3. #460 policy invariant closeout gate.
4. #459 impacted runner when `scripts/local_commit_validation.py` exists.
5. `bears_doctor validate-closeout`.

## Result packet

The run command emits compact `bears-dagger-delivery-result.v1` JSON with:

- `status`
- `failed_gates`
- `artifacts`
- `next_actions`

Missing `dagger` reports `tool_missing` with `manual_setup_required`; it is not a pass.

## Safety

- No deploy mutation.
- No GitHub mutation.
- No branch mutation.
- No secret reads.
