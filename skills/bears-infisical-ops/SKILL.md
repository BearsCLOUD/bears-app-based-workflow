---
name: bears-infisical-ops
description: "Use for Bears Infisical work: locating project/env/path metadata, checking secret-name readiness, preparing name-only live proof, ExternalSecret/ClusterSecretStore provider handoff, External Secrets readiness, and Telegram/API session custody without reading, printing, logging, committing, or exposing secret values. Trigger for Infisical CLI, ExternalSecret, ClusterSecretStore, Secret Factory handoff, injected env-name proof, TELEGRAM_SESSION_STRING, TELEGRAM_SESSION_PATH exception, or secret-safe runtime validation."
---

# Bears Infisical Ops

Use this skill for Infisical-backed access checks and live-readiness handoffs in Bears repositories.

## Hard rules

- Never read, print, log, commit, copy, or summarize secret values.
- Never ask the user to paste a secret value.
- Never write `.env`, session, token, kubeconfig, private chat, or production-data files.
- Prefer names-only proof: project name/id, environment name, secret path, env var names, and secret key names.
- Treat `TELEGRAM_SESSION_STRING` as preferred session custody.
- Allow `TELEGRAM_SESSION_PATH` only when an operator explicitly sets `TGINTEL_ALLOW_LOCAL_SESSION_PATH=1` for that dev or emergency one-run; never use it as final live PASS evidence.
- Fail closed if Infisical project, environment, path, or required env names are missing.
- Treat Infisical as secret custody and environment injection only; it is not a software deployment path.
- Local `infisical run` proof is preflight only. Final live PASS for software must come from Kubernetes desired state, `local_cd`, workload evidence, secret-reference readiness, and runtime health proof.
- Treat `/srv/bears/control-plane/infisical` as bootstrap or preflight support only; it does not own Kubernetes runtime desired state.
- For generated local values, use `$secret-factory`; do not implement a second write path.

## Required startup

1. Read the nearest `AGENTS.md` files.
2. If editing plugin governance, read `/srv/bears/plugins/bears/AGENTS.md`.
3. Classify the task:
   - `metadata-only`: names, paths, project links, env names.
   - `write-only-generation`: generated value must be created and stored.
   - `live-proof`: app command must run with Infisical-injected env.
4. For `write-only-generation`, switch to `$secret-factory` and follow its catalog.

## Safe local checks

Run from the target checkout. These commands do not print values:

```bash
command -v infisical
infisical --version
infisical --help | sed -n '1,80p'
infisical run --help | sed -n '1,120p'
find . -maxdepth 4 \( -name '.infisical*' -o -name 'infisical*.json' -o -name '*infisical*' \) -print | sort
env | cut -d= -f1 | sort
```

Filter env names to the task-specific allowlist. Example for Telegram one-chat work:

```bash
env | cut -d= -f1 \
  | grep -E '^(TELEGRAM_API_ID|TELEGRAM_API_HASH|TELEGRAM_PHONE|TELEGRAM_SESSION_STRING|TELEGRAM_SESSION_PATH|TGINTEL_ALLOW_LOCAL_SESSION_PATH|TGINTEL_CHAT_ID|DATABASE_URL|LLM_API_KEY|LLM_BASE_URL|LLM_MODEL)$' \
  | sort
```

## Operator-only name proof

Use only with explicit operator approval because `infisical run` injects values into the child process before filtering:

```bash
infisical run -- printenv \
  | cut -d= -f1 \
  | grep -E '^(TELEGRAM_API_ID|TELEGRAM_API_HASH|TELEGRAM_PHONE|TELEGRAM_SESSION_STRING|TELEGRAM_SESSION_PATH|TGINTEL_ALLOW_LOCAL_SESSION_PATH|TGINTEL_CHAT_ID|DATABASE_URL|LLM_API_KEY|LLM_BASE_URL|LLM_MODEL)$' \
  | sort
```

Passes only when every required name is present and no values are printed.

## Infisical metadata packet

Return this packet when a live proof cannot run yet:

```text
infisical_project=<name-or-id-or-missing>
infisical_env=<env-or-missing>
infisical_secret_path=<path-or-missing>
required_env_names=<comma-separated-names>
session_custody=<TELEGRAM_SESSION_STRING|TELEGRAM_SESSION_PATH gated|missing>
operator_approval_needed=<yes|no>
blocked_step=<exact dependent command>
```

## Kubernetes-backed Infisical refs

When Infisical is reached through External Secrets Operator:

1. Use `$bears-kubernetes-ops` for Kubernetes metadata commands.
2. Inspect only `ClusterSecretStore`, `SecretStore`, `ExternalSecret`, workload
   env names, and secret key names.
3. Include `secretRefs=0` when a provider readiness issue means no safe target
   key references were confirmed.
4. Treat `ClusterSecretStore Ready=False`, `InvalidProviderConfig`,
   `ExternalSecret Ready=False`, or `SecretSyncedError` as blockers only for the
   dependent live proof.
5. Do not decode Kubernetes `Secret` values to compensate for a broken provider.
6. Do not fix `ClusterSecretStore` provider drift from a product app lane; return
   a provider handoff instead.
7. Return names-only provider handoff with store name, namespace if namespaced,
   owning infra repo or `missing`, and the blocked proof step.
8. Do not claim a product app is configured just because a generic platform
   Telegram `ExternalSecret` exists; require the target app name or exact env-name
   contract.
9. For deployed Bears software, Infisical wiring must be represented through
   Kubernetes desired state, preferably `ExternalSecret`; local `.env`, pasted
   values, or manual secret injection are not deployment paths.
10. Do not store provider auth payloads, Universal Auth credentials, service
    tokens, kubeconfigs, Infisical values, or decoded Kubernetes Secret data in
    Git, chat, logs, issues, or closeout.

Runtime handoff chain:

```text
Infisical path/key name -> ExternalSecret -> Kubernetes Secret key name -> workload env name -> runtime health proof
```

Every step is names-only. A missing step blocks only the dependent live proof and must be routed to the owner named by `subagents_roles.py route <exact-path>`.

## Dev platform data-service names

For `bears-platform-stateful-backend-dev`, use names-only readiness packets for:

- Redis password reference: `/kubernetes/bears-platform-stateful-backend-dev/redis/password`.
- Taskiq broker/result URL references:
  `/kubernetes/bears-platform-stateful-backend-dev/taskiq/broker-url` and
  `/kubernetes/bears-platform-stateful-backend-dev/taskiq/result-backend-url`.
- ClickHouse password and URL references:
  `/kubernetes/bears-platform-stateful-backend-dev/clickhouse/password` and
  `/kubernetes/bears-platform-stateful-backend-dev/clickhouse/url`.
- PostgreSQL password and database URL references:
  `/kubernetes/bears-platform-stateful-backend-dev/postgresql/password` and
  `/kubernetes/bears-platform-stateful-backend-dev/postgresql/database-url`.

Allowed output is the path name and expected key name only. Do not run readback
commands that print secret values. If a value is missing, return the missing path
and the dependent Kubernetes workload name.

## Telegram session gate

For Telegram user-account collectors:

1. Require `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`, and `TELEGRAM_SESSION_STRING` by name.
2. If `TELEGRAM_SESSION_STRING` is absent, require both `TELEGRAM_SESSION_PATH` and `TGINTEL_ALLOW_LOCAL_SESSION_PATH=1` by name, and mark the proof dev/emergency-only.
3. Keep `TGINTEL_DISABLE_TELEGRAM_SEND=1` for proof runs unless the owning runbook explicitly allows sending.
4. Do not run multi-chat commands to prove a one-chat feature.
5. Do not print chat contents, private messages, session data, or raw logs.

## Closeout language

Report only:

- commands run;
- exit codes and sanitized summaries;
- names of projects, environments, paths, and env vars;
- exact missing inputs.

Do not claim live Infisical readiness from local dry/mock tests.
