# Temporal Evaluation

Temporal is not needed for the current `@bears` worker runtime.

## Bottom line

- **Current fit:** local worker/state-file model plus simple queue/lease.
- **Wrapper fit:** Dagger can wrap container runs, but it is wrapper-only.
- **Future fit:** Temporal is a later candidate only if the local model fails.

Temporal adds durable task queues, worker polling, retry history, and recovery. That is useful when the runtime needs cross-process orchestration that local files and explicit leases cannot cover. It is not a closeout-path dependency here.

## Comparison

### Local worker/state-file model

- Best fit now.
- Keeps ownership explicit in repo/runtime files.
- Matches the current closeout and policy-gate flow.

### Dagger wrapper

- Good for containerized task execution.
- Does not replace durable worker state.
- Does not solve queue history or worker recovery by itself.

### Simple queue/lease

- Best fit for bounded dispatch.
- Prevents duplicate starts with explicit leases.
- Keeps recovery and ownership visible in files.

### Temporal

- Strong if the runtime needs durable orchestration, worker polling, and retry history.
- Adds service, worker, and operator overhead.
- Should stay out of the closeout path.

## Adoption preconditions

Temporal can move from candidate to adopt only after all of these pass:

1. Closeout and policy gates are executable without Temporal.
2. The local worker/state-file model and queue/lease still leave a real runtime gap.
3. The runtime needs durable retries, routing, or recovery that files cannot cover.
4. A named owner can run, observe, and retire the Temporal service and worker fleet.

## Command surface

```bash
python3 scripts/temporal_evaluation.py validate
python3 scripts/temporal_evaluation.py report --json
```
