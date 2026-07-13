# Machine-Owned Runner Surfaces

These files belong to the repository-owned CI/CD boundary and are not plugin agent instructions or installed plugin payload.

## Module map

- `deploy_plugin.py` is the stable executable facade. It selects the repository-local package for authored autoCI coverage or the fixed root-owned `/usr/local/lib/bears-plugin-deploy` package in production, preserves the legacy import surface, and delegates to `bears_deploy.cli.main`.
- `promote_gateway.py` is the fixed privileged bridge. For one exact SHA reachable from the authoritative `main`, it rebuilds the hash-locked gateway from Git blobs, atomically activates it, runs promotion as non-root `ai1`, and restores the prior gateway on failure or interrupted activation.
- `bears_deploy/constants.py` owns fixed identities, paths, schemas, and size limits.
- `bears_deploy/models.py` owns shared errors and transaction context models.
- `bears_deploy/graph_instructions.py` owns fail-closed transactional reconciliation of the receipted graph-behavior block in `$CODEX_HOME/AGENTS.md`.
- `bears_deploy/telemetry.py` owns sanitized official-SDK Sentry delivery through `report_sentry`. It retains real tracebacks while stripping locals, request/user data, and PII, and never changes the CD result.
- `bears_deploy/process.py` owns bounded subprocess, Git, and GitHub credential operations.
- `bears_deploy/marketplace.py` owns manifest, marketplace, cache, and pinned Git-blob verification.
- `bears_deploy/role_profiles.py` owns exact role bundle materialization and desired config rendering.
- `bears_deploy/role_io.py` owns locked config and receipt reads, snapshots, validation, and receipt construction.
- `bears_deploy/publication.py` owns compare-and-swap publication, rollback, and journaled file replacement.
- `bears_deploy/standalone_roles.py` owns receipt-bounded standalone custom-agent publication under `$CODEX_HOME/agents`.
- `bears_deploy/journal.py` owns bounded binary encoding for durable journal fields.
- `bears_deploy/state_io.py` owns the private state directory, migration tombstone, and deploy receipt reads.
- `bears_deploy/intent_schema.py` owns strict promotion-intent schema and binding validation.
- `bears_deploy/intent_io.py` owns durable promotion-intent and role-transaction writes.
- `bears_deploy/receipts.py` owns deployment receipt writes and receipted installation verification.
- `bears_deploy/role_deploy.py` owns role installation and v1 registration migration transactions.
- `bears_deploy/role_recovery.py` owns role rollback and managed-registration removal.
- `bears_deploy/promotion.py` owns exact-SHA convergence, recovery, and promotion orchestration.
- `bears_deploy/cli.py` owns the `main` identity, argument, credential, and state-lock boundary.
- `sentry-requirements.lock` pins the official `sentry-sdk`, `urllib3`, and `certifi` wheels with SHA-256 hashes. The installer places them inside the atomically replaced root-owned gateway tree.
- `test_deploy_plugin_sentry.py` authors stub-only SDK, stack, release, production environment, trace, sanitization, single-send, and telemetry-failure scenarios. It never opens a live Sentry connection or creates a synthetic live event.
- `test_promote_gateway.py` authors requirement allowlist plus interrupted activation/commit recovery scenarios for the privileged bridge.
- `materialize_sentry_dsn.py` is a root-only atomic writer. It accepts one DSN only on inherited file descriptor 3, writes the fixed target, emits no value, and starts no child process.
- `install-sentry-materializer.sh` installs only that writer as immutable root-owned code. It does not create an identity, obtain a DSN, or execute the writer.
- `install-runner.sh` owns the isolated GitHub runner, the initial root-owned gateway/promoter installation, and the sole SHA-bounded runner-to-root sudo authorization. The runner has no general root shell, no materializer sudo grant, and cannot traverse `/home/ai1`.

All gateway modules share the same runtime risks: partial marketplace mutation, receipt corruption, unsafe filesystem state, and unavailable telemetry. No plugin CI pipeline is active; `automation_status=not_run` is mandatory until exact external evidence is supplied.

## Durable promotion recovery

The gateway atomically persists and syncs a promotion-intent journal before activation, then clears it only after the requested revision, the previous receipted revision, or the disabled state is verified. Role reconciliation also publishes one private standalone TOML file per receipted role under `$CODEX_HOME/agents`; retries converge partial per-file publication, updates remove only stale receipt-owned names, and removal preserves unrelated files. A later invocation recovers an interrupted promotion before ordinary receipt handling by converging to those outcomes in that order.

The operator-visible risk is an interrupted or partially mutated marketplace. Recovery fails closed: if convergence cannot be proven, promotion stops with a recovery failure rather than advancing the receipt or enabling an unverified plugin, and operator repair is required before another promotion can safely proceed.

## Sentry failure boundary

The gateway reads `/home/ai1/.config/bears-app-based-workflow/credentials/sentry-dsn` only in memory and only after an actionable failure. The file must be a non-linked regular file owned by `ai1` with mode `0600`. Infisical is used only when that materialized secret is absent or explicitly rotated. Live trace evidence waits for a real autoCD after operator bootstrap; the stack path remains `needs-evidence` until the first real actionable failure.

Eligible event codes are limited to unhandled exception, receipt corruption, mutation failure after start, post-mutation failure, recovery activation, and recovery failure. Normal success, no-op, dry-run, invalid input, expected policy or authorization refusal, and a missing or unusable DSN produce no event. Delivery failure is swallowed and cannot change deployment status.

Events contain only normalized `error_code`, `service`, `component`, `operation`, repository shorthand, plugin, full Git SHA, plugin version, workflow run, and receipt schema. Their fingerprint is `service + component + error_code`. Raw exceptions, process output, URLs, request bodies, secrets, personal data, and local variables are excluded.

## Operator-gated materialization contract

No Infisical identity, secret coordinate, or credential is defined in this repository. Inventing any of them would cross the observability ownership boundary. The observability owner must first provision one identity limited to read exactly the DSN secret and provide the fixed secret coordinate through the separately authorized operator packet.

The operator-owned bootstrap must supply the Infisical identity credential from a protected file or inherited descriptor. It must not use arguments, standard output, a GitHub job environment, or the runner account. The Infisical client may stream only the single DSN value into file descriptor 3 of the installed materializer. The materializer then atomically replaces the target with owner `ai1:ai1`, directory mode `0700`, and file mode `0600`. No runner access is retained.

Installing the materializer and performing the first materialization are separate operator-authorized actions. This repository performs neither action automatically and defines no manual fallback for CI/CD or telemetry delivery.

## CD and acceptance boundary

`plugin-marketplace-cd.yml` runs no repository checkout or general-purpose installer. It passes the exact pushed SHA and ephemeral GitHub job credential to the fixed root-owned promoter through the runner's command-restricted sudo rule. The promoter accepts only revisions reachable from the authoritative `main`, reads gateway sources as bounded Git blobs, installs only the three hash-locked allowlisted Python distributions, and never executes the fetched gateway code as root. It runs the newly activated gateway as non-root `ai1`; gateway or activation failure restores the previous root-owned gateway before CD fails.

Gateway source and its hash-locked dependency versions therefore update automatically with each successful `main` promotion. The privileged promoter itself remains a small operator-installed trust anchor: changing that root-executed bridge or its sudo authorization requires one explicit bootstrap, while ordinary gateway edits do not.

The gateway accepts timestamp-suffixed versions and their historical payload-fingerprint scope only while migrating an existing receipt. Once a plain SemVer receipt exists, each later pushed revision must strictly increase that version and cannot return to the legacy format or fingerprint scope.

No autoCI workflow is active and CD emits no acceptance status. Existing historical evidence remains immutable but never applies to a newer commit; acceptance projects as `not_run` until exact external evidence is supplied.
