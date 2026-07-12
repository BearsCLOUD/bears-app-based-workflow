# Machine-Owned Runner Surfaces

These files belong to the repository-owned CI/CD boundary and are not plugin agent instructions or installed plugin payload.

## Module map

- `deploy_plugin.py` is the state-mutating marketplace CD gateway invoked on every `main` push. Its `main` entry point fetches the exact pushed revision, upgrades the fixed marketplace, reinstalls the plugin, reconciles roles, verifies exact SHA/version state, and advances the durable receipt. Runtime risks are partial marketplace mutation, receipt corruption, and unavailable telemetry.
- `test_deploy_plugin_sentry.py` provides local, stub-only event and transport coverage inside autoCI. It never opens a live Sentry connection and never creates a synthetic live event.
- `materialize_sentry_dsn.py` is a root-only atomic writer. It accepts one DSN only on inherited file descriptor 3, writes the fixed target, emits no value, and starts no child process.
- `install-sentry-materializer.sh` installs only that writer as immutable root-owned code. It does not create an identity, obtain a DSN, or execute the writer.
- `install-runner.sh` owns the isolated GitHub runner and the sole runner-to-deploy sudo boundary. The runner has no materializer sudo grant and cannot traverse `/home/ai1`.

## Durable promotion recovery

The gateway atomically persists and syncs a promotion-intent journal before activation, then clears it only after the requested revision, the previous receipted revision, or the disabled state is verified. A later invocation recovers an interrupted promotion before ordinary receipt handling by converging to those outcomes in that order.

The operator-visible risk is an interrupted or partially mutated marketplace. Recovery fails closed: if convergence cannot be proven, promotion stops with a recovery failure rather than advancing the receipt or enabling an unverified plugin, and operator repair is required before another promotion can safely proceed.

## Sentry failure boundary

The gateway reads `/home/ai1/.config/bears-app-based-workflow/credentials/sentry-dsn` only in memory and only after an actionable failure. The file must be a non-linked regular file owned by `ai1` with mode `0600`. The DSN is never copied into a child environment, argument, log, event, or receipt.

Eligible event codes are limited to unhandled exception, receipt corruption, mutation failure after start, post-mutation failure, recovery activation, and recovery failure. Normal success, no-op, dry-run, invalid input, expected policy or authorization refusal, and a missing or unusable DSN produce no event. Delivery failure is swallowed and cannot change deployment status.

Events contain only normalized `error_code`, `service`, `component`, `operation`, repository shorthand, plugin, full Git SHA, plugin version, workflow run, and receipt schema. Their fingerprint is `service + component + error_code`. Raw exceptions, process output, URLs, request bodies, secrets, personal data, and local variables are excluded.

## Operator-gated materialization contract

No Infisical identity, secret coordinate, or credential is defined in this repository. Inventing any of them would cross the observability ownership boundary. The observability owner must first provision one identity limited to read exactly the DSN secret and provide the fixed secret coordinate through the separately authorized operator packet.

The operator-owned bootstrap must supply the Infisical identity credential from a protected file or inherited descriptor. It must not use arguments, standard output, a GitHub job environment, or the runner account. The Infisical client may stream only the single DSN value into file descriptor 3 of the installed materializer. The materializer then atomically replaces the target with owner `ai1:ai1`, directory mode `0700`, and file mode `0600`. No runner access is retained.

Installing the materializer and performing the first materialization are separate operator-authorized actions. This repository performs neither action automatically and defines no manual fallback for CI/CD or telemetry delivery.

## CD and acceptance boundary

`plugin-marketplace-cd.yml` runs no repository checkout or agent-controlled installer. It passes the exact pushed SHA and ephemeral GitHub job credential to the fixed root-owned gateway through the runner's existing command-restricted sudo rule. The gateway owns marketplace refresh, plugin installation, durable recovery, and sanitized deployment output.

No autoCI workflow is active and CD emits no acceptance status. Existing historical evidence remains immutable but never applies to a newer commit; acceptance projects as `not_run` until exact external evidence is supplied.
