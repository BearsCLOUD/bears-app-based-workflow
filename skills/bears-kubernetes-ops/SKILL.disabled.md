---
name: bears-kubernetes-ops
description: "Govern Bears Kubernetes read-only metadata work, Kubernetes deployment governance, all-software Kubernetes desired-state and local_cd deploy boundaries, local dev-instance kube runtime placement, kube-backed secret-reference discovery, namespace/workload/env-name checks, and safe live-gate proof planning without decoding Secret data, printing secret values, mutating runtime, or bypassing local CD contracts."
---

# Bears Kubernetes Ops

Required: activate this skill for Kubernetes metadata checks and kube-backed live-gate discovery in Bears.

## Hard rules

- Default to read-only metadata.
- Never decode Kubernetes Secret values.
- Never print `.data`, `stringData`, token, kubeconfig, session, private chat, or production-data values.
- Never run mutating commands (`apply`, `patch`, `delete`, `scale`, `rollout restart`, `exec` with writes) unless a higher-priority task explicitly authorizes the exact mutation.
- All Bears live software deploys must be Kubernetes desired-state backed and promoted through `local_cd`; local host runs, `docker run`, local Infisical helpers, and manual `kubectl apply` are not deploy paths.
- The local CD executor owns source staging, image handoff, apply, rollout, and evidence mechanics; descriptors and policy must not define those steps.
- Agents must not hunt for `kubectl`, kubeconfigs, or cluster access to decide a CD path. The fixed `local_cd` executor owns runner toolchain paths.
- Agent-run `kubectl` is read-only metadata proof only after `local_cd` evidence or exact operator-approved runtime inspection; it is not source truth and not a final deploy path.
- Local dev-instance Kubernetes may prove manifest shape, image wiring, and read-only readiness only; it is not final live PASS evidence.
- Operator-approved live mutation may be incident break-glass only; it must not become deployment source of truth.
- Do not treat Kubernetes as a bypass around Infisical or Secret Factory policy.
- Production Kubernetes mutation is Git/CD-owned; follow `$bears-deploy-gate` for deploy impact.
- Say exact terms `kubernetes_deployment` and `local_cd` when those surfaces are changed.

## Required startup

1. Read the nearest `AGENTS.md` files.
2. For plugin work, read `/srv/bears/plugins/bears/AGENTS.md`.
3. Route the surface:
   - manifests under `/srv/bears/kubernetes`: infrastructure desired state;
   - product checkout manifests: target-local evidence only unless routed otherwise;
   - live cluster checks: read-only runtime evidence.
4. If a command can expose secret values, do not run it.

## Safe kubectl metadata commands

Prefer these read-only commands:

```bash
kubectl config current-context
kubectl get ns
kubectl get deploy,statefulset,daemonset,job,cronjob -A
kubectl get svc,ingress,httproute,gateway -A
kubectl get externalsecret,secretstore,clustersecretstore -A 2>/dev/null || true
kubectl get secret -A
```

`kubectl get secret` default table output is allowed because it shows names, types, data counts, and ages, not values. Do not add `-o yaml` or `-o json` for Secret resources.

When exact task evidence names a Bears local kube toolchain, run that exact binary and context for read-only metadata only. If it is absent, do not search the host for `kubectl` or kubeconfigs; report `KUBE_TOOLCHAIN_EVIDENCE_MISSING` for the dependent metadata proof.

Do not commit kubeconfig paths or generated kubeconfig files.

## Local dev-instance runtime

Required: follow this section when the user asks to raise or inspect a Kubernetes node on the
current dev instance.

1. Put persistent local kube runtime under `/srv/bears/runtime/kube/<context>/`.
2. Keep kubeconfigs, certificates, cache, and cluster state out of Git; `/srv/bears/runtime/**` is runtime-only.
3. Write `.tmp` only for disposable scratch that may be deleted between runs.
4. Report local cluster evidence as `dev-instance proof`, not final live PASS.
5. Never convert local `kubectl apply`, local smoke, or local host-process evidence into deployment proof. Final live PASS requires Kubernetes desired state, `local_cd`, workload evidence, secret-reference readiness, CD evidence, and runtime health proof.

## Safe manifest discovery

Required: read repository manifests to find names and references without live values:

```bash
find /srv/bears/kubernetes -maxdepth 5 -type f \
  \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) -print | sort
rg -n 'kind: (Deployment|StatefulSet|Job|CronJob|ExternalSecret|SecretStore|ClusterSecretStore|Secret)|secretKeyRef|envFrom|TELEGRAM_|INFISICAL|DATABASE_URL|TGINTEL_' /srv/bears/kubernetes
```

Do not copy raw Secret manifests into the response. Summarize only resource names, namespaces, key names, and owning manifests.

## Secret-safe workload inspection

Allowed for workload metadata:

```bash
kubectl -n <namespace> get deploy <name> -o jsonpath='{.metadata.name}{"\n"}{range .spec.template.spec.containers[*]}{.name}{"\n"}{end}'
kubectl -n <namespace> describe deploy <name>
```

When describing workloads, redact values if Kubernetes prints literal env values. Prefer reporting only env var names and referenced Secret/ConfigMap names.

Forbidden:

```bash
kubectl get secret <name> -o yaml
kubectl get secret <name> -o json
kubectl get secret <name> -o jsonpath='{.data.*}'
kubectl exec <pod> -- printenv
kubectl exec <pod> -- cat /var/run/secrets/...
```

## ExternalSecret readiness

For External Secrets Operator resources, read status and names only:

```bash
kubectl get clustersecretstore <name> -o name
kubectl describe clustersecretstore <name>
kubectl -n <namespace> get externalsecret -o custom-columns=NAME:.metadata.name,READY:.status.conditions[0].status,REASON:.status.conditions[0].reason --no-headers
kubectl -n <namespace> describe externalsecret <name>
```

If a `ClusterSecretStore` reports `Ready=False` or `InvalidProviderConfig`, mark
only the dependent live proof blocked. Do not decode the target `Secret` to
debug provider credentials.

## Dev platform data-service checks

Required: follow this section only for the exact Bears dev platform lane:

- Namespace: `bears-platform-stateful-backend-dev`.
- Redis: in-memory data store used here for queue and cache state.
- Taskiq: Python async task worker that consumes jobs through a broker.
- ClickHouse: column-store analytics database.
- PostgreSQL: relational database for platform state.

Allowed name-only checks:

```bash
kubectl -n bears-platform-stateful-backend-dev get statefulset,deploy,svc,externalsecret,networkpolicy
kubectl -n bears-platform-stateful-backend-dev get pvc
kubectl -n bears-platform-stateful-backend-dev get externalsecret -o custom-columns=NAME:.metadata.name,READY:.status.conditions[0].status,REASON:.status.conditions[0].reason --no-headers
```

Report only:

- workload names;
- service names and ports;
- PVC names, phases, and requested sizes;
- ExternalSecret names and key names;
- NetworkPolicy names and allowed service paths;
- image names with digest IDs.

Forbidden without exact operator approval:

- Redis `FLUSH*`, `CONFIG SET`, or raw key reads;
- Taskiq queue purge, retry replay, or worker restart;
- ClickHouse mutation or raw query against user data;
- PostgreSQL migration, DDL/DML, dump, restore, or row reads;
- `kubectl exec`, port-forward, rollout restart, scale, patch, delete, or apply.

Live PASS for these services requires Kubernetes workload evidence, digest image
provenance, ExternalSecret readiness, PVC readiness, network-path evidence, and
runtime health proof through `local_cd`.

## Infisical/Kubernetes live-gate packet

When kube is used to locate missing live inputs, return:

```text
namespace=<namespace-or-missing>
workload=<kind/name-or-missing>
external_secret=<namespace/name-or-missing>
secret_store=<namespace/name-or-missing>
secret_name=<namespace/name-or-missing>
env_names=<comma-separated-env-names>
secret_key_names=<comma-separated-key-names>
infisical_project_ref=<name-or-missing>
infisical_env_ref=<name-or-missing>
infisical_path_ref=<name-or-missing>
approved_chat_ref=<name-or-missing>
secret_refs_count=<integer>
values_read=false
mutation_performed=false
```

## One-chat Telegram proof from kube

For TG One Chat Intelligence or similar one-chat collectors:

1. Find the namespace and workload names.
2. Find env var names and Secret/ExternalSecret key names only.
3. Confirm `TELEGRAM_SESSION_STRING` is present by name, or `TELEGRAM_SESSION_PATH` plus `TGINTEL_ALLOW_LOCAL_SESSION_PATH=1` is present by name.
4. Confirm a single approved chat name exists by name (`TGINTEL_CHAT_ID` or project-specific equivalent).
5. Confirm `TGINTEL_DISABLE_TELEGRAM_SEND=1` is required for proof commands.
6. Do not run `kubectl exec printenv`; run a repo helper or operator-approved Infisical name proof instead.
7. If the only remaining proof requires injected runtime values, return the exact operator command and mark the step blocked on operator approval.
8. Do not treat generic Telegram platform resources as `tgsearch` proof unless
   their names, env names, or manifests explicitly reference `tgsearch`,
   `tgintel`, or the target one-chat app.

## Closeout

Report:

- safe commands run;
- resource names and namespaces;
- env/key names found;
- missing refs;
- whether values were read (`false` unless explicitly authorized and still never printed);
- whether runtime was mutated (`false` unless explicitly authorized).
