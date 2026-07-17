# Machine-Owned Deployment Runner

These files form the repository-owned deployment boundary. They are not plugin agent instructions, installed skill payload, or workflow-stage authority.

## Module map

- deploy_plugin.py is the stable gateway facade and delegates to bears_deploy.cli.main.
- promote_gateway.py is the fixed privileged bridge for one exact revision reachable from authoritative main.
- bears_deploy/constants.py owns fixed identities, paths, schemas, and size limits.
- bears_deploy/models.py owns shared errors and transaction context models.
- bears_deploy/graph_instructions.py only retires an exact receipted legacy block; ordinary promotion and repair never access $CODEX_HOME/AGENTS.md.
- bears_deploy/telemetry.py sends bounded sanitized Sentry events without changing the deployment result.
- bears_deploy/process.py owns bounded subprocess, Git, and GitHub credential operations.
- bears_deploy/marketplace.py owns manifest, marketplace, cache, and pinned Git-blob verification.
- bears_deploy/role_profiles.py validates and materializes the authoritative TOML role bundle.
- bears_deploy/role_io.py owns locked role state reads, snapshots, validation, and receipt construction.
- bears_deploy/publication.py owns compare-and-swap publication, rollback, and journaled file replacement.
- bears_deploy/standalone_roles.py owns receipt-bounded standalone profile publication under $CODEX_HOME/agents.
- bears_deploy/journal.py owns bounded binary encoding for durable journal fields.
- bears_deploy/state_io.py owns private deployment state and receipt reads.
- bears_deploy/intent_schema.py and bears_deploy/intent_io.py own promotion intent binding and durable writes.
- bears_deploy/receipts.py owns deployment receipt writes and receipted installation verification.
- bears_deploy/role_deploy.py and bears_deploy/role_recovery.py own role publication, migration, and rollback.
- bears_deploy/promotion.py owns exact-revision convergence, recovery, and promotion orchestration.
- bears_deploy/cli.py owns identity, argument, credential, and state-lock boundaries.
- sentry-requirements.lock pins the official Sentry transport dependencies by SHA-256.
- materialize_sentry_dsn.py is the root-owned atomic writer for one inherited DSN value.
- install-sentry-materializer.sh installs only that writer.
- install-runner.sh installs the isolated GitHub runner and the narrow SHA-bound runner-to-root authorization.

## Promotion and recovery

The privileged bridge reads bounded Git blobs, installs only hash-locked allowlisted dependencies, and never executes fetched gateway code as root. It activates the gateway atomically, invokes it as non-root ai1, and restores the prior gateway when the requested revision cannot converge.

CD runs the deployment recovery regression suite against the exact pushed revision before invoking the privileged bridge. Receipt v5 rollout is gated on an exact installed copy of `promote_gateway.py`, so the operator must bootstrap that root-owned file with `install-runner.sh` before publication. A fixed bounded timeout supervisor inherits the update-lock lease while the fetched gateway runs as non-root `ai1`; recovery cannot overlap a surviving old child after the outer promoter exits. Once v5 becomes durable, the bridge retains the v5-capable gateway across child failure, signal termination, or interrupted root commit while still propagating a failed child result to CI.

The gateway persists a promotion intent before mutation and clears it only after the requested revision, the previous receipted revision, or local plugin removal is verified. Role recovery converges partial publication while preserving unrelated files.

An unsafe marketplace state, corrupt receipt, or unresolved recovery stops promotion without advancing the receipt.

## Large-module boundary

- `promote_gateway.py` stays standalone so the root-owned updater has one auditable installation unit; before adding another gateway feature, extract receipt and source-binding validation into an installer-owned module.
- `bears_deploy/graph_instructions.py` stays cohesive only for the bounded v3/v4 retirement window; remove the module and tombstone asset after legacy receipts are no longer supported.
- `test_graph_instruction_retirement.py` stays one standard-library CI entrypoint for the v5 rollout; before adding another scenario, split legacy-transaction and privileged-gateway cases into separate test modules.

## Sentry boundary

The gateway reads /home/ai1/.config/bears-app-based-workflow/credentials/sentry-dsn only in memory and only after an actionable deployment failure. The file must be a non-linked regular file owned by ai1 with mode 0600.

Eligible events are limited to unhandled exceptions, receipt corruption, mutation failure, recovery activation, and recovery failure. Events contain normalized operational identifiers and exclude secrets, personal data, process output, request bodies, raw local variables, and credential material.

The observability owner provisions the Infisical identity and exact secret coordinate outside this repository. The operator supplies the identity credential through a protected file or inherited descriptor, and the materializer receives only the DSN on inherited file descriptor 3.

## Workflow separation

The runner publishes one repository revision and its managed role payload. It does not own app-* stages, select workflow routes, append repository process records, or emit audited.
