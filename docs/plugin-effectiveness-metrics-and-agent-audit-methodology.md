# Plugin Effectiveness Metrics and Agent Audit Methodology

## Status and purpose

This document defines how to measure the effectiveness of
`bears-app-based-workflow` and how a read-only agent should audit the plugin.
It is an analytical and operational reference, not an instruction authority,
workflow source, acceptance receipt, or replacement for machine-readable
contracts. It is intentionally not linked from `AGENTS.md`.
The source manifest hash-tracks this file as a non-semantic documentation
artifact; that tracking does not make it a workflow or functional-map source.

The methodology evaluates whether the plugin produces deterministic,
traceable, correctly routed, bounded, and efficiently converging app work. It
does not redefine `audited` as product acceptance. `audited` means only that
the structured semantics and recorded process agree for one exact snapshot;
product acceptance remains independently owned by autoCI or another explicitly
authorized acceptance producer.

## Definitions

- **Eligible run**: one native workflow run bound to an exact plugin version,
  repository, wave, task set, source snapshot, and journal digest. A run stopped
  solely by an access, credential, or explicit operator stop may be excluded
  from an outcome denominator, but it remains in the blocker metric.
- **Evidence-qualified**: supported by exact-revision, non-stale,
  non-truncated, provenance-bound evidence. Authored examples and unexecuted
  test scenarios are not evidence-qualified outcomes.
- **Converged run**: an eligible run that legitimately reaches `audited` with
  complete convergence and terminal process evidence, zero routable findings,
  and zero open remediation tasks.
- **First-pass convergence**: convergence without a remediation run after the
  first immutable review.
- **Agent audit**: an independent, read-only evaluation of exact plugin
  artifacts and evidence. Executable tests, validators, schemas, lints, cache
  checks, plugin validation, and executable audit suites remain owned by CI.
- **Hard gate**: a condition that cannot be compensated by a high numeric
  score. Integrity, authority, safety, evidence, or acceptance-honesty failures
  are hard-gate failures.
- **Metric record**: one versioned measurement with a frozen definition,
  numerator, denominator, cohort, evidence references, and verdict.

## Evaluation boundary

The plugin has six distinct evaluation surfaces:

1. **Workflow semantics**: stages, routes, ownership, handoffs, finding routes,
   and the meaning of `audited`.
2. **Graph integrity**: source manifest, deterministic compiler, indexes,
   receipts, digests, dependency and trace edges, and pagination.
3. **Process integrity**: immutable events, causal links, task lifecycle,
   review, remediation, journal ownership, and terminal candidates.
4. **Agent governance**: execution mode, typed role selection, packet identity,
   session lifecycle, target bounds, mutation ownership, and critic separation.
5. **Runtime and delivery**: MCP lifecycle, bounded requests and responses,
   installer, role rendering, marketplace metadata, promotion, rollback, and
   exact-revision deployment.
6. **Resource efficiency**: elapsed time, model turns, tool calls, retries,
   token cost, and throughput per evidence-qualified outcome.

The first five surfaces measure whether the plugin performs its own contract.
The sixth measures the cost of that performance. Product behavior, business
impact, and user satisfaction are paired external outcomes and must not be
inferred from graph consistency alone.

## Current repository baseline

The following snapshot was inspected on 2026-07-13 at Git commit
`468d503278c007ae3381f6777973ba8a2b9efc2c`.

| Parameter | Observed value |
| --- | ---: |
| Plugin version | `0.4.2` |
| Canonical workflow stages | 7 |
| Plugin skills | 15 |
| Agent profiles and role definitions | 11 each |
| MCP tools | 8 read-only + 2 maintainer |
| JSON contracts | 21 |
| Explicit manifest tracked paths | 103 |
| Current compiled sources | 148 |
| Current compiled entities / edges | 63 / 92 |
| Current journal events / runs | 42 / 2 |
| Event schemas | 41 v1, 1 v2 |
| Event automation evidence | 42 `not_run` |
| Authored test scenarios | 87, not executed in this audit |
| Current graph build | `BUILD-BCBF9FEA9EF4EDC84AE2AB6B` |
| Graph reconciliation | exact current build, compiler `no_op=true` |

This snapshot is sufficient for structural analysis but not for an empirical
claim that the plugin is effective or efficient:

- the two runs are not a representative production cohort;
- the journal mixes legacy and native schemas;
- every recorded automation status is `not_run`;
- the repository declares no plugin CI pipeline;
- canonical event and handoff contracts contain no event time, duration,
  token, turn, tool-call, retry, or cost fields;
- eight historical `audited` events are events inside a run, not eight
  independent evidence-qualified runs.

Consequently, the current empirical effectiveness verdict is
`inconclusive`, not failed and not passed.

## Measurement rules

### Freeze before measuring

Every evaluation contract must freeze the following before evidence is read:

- plugin Git commit and manifest version;
- installed plugin receipt or installed payload digest when runtime behavior is
  in scope;
- repository, wave, run, and task-set identities;
- current build ref, source snapshot digest, and journal digest;
- baseline version and comparison version;
- metric direction, target, minimum material effect, and negative tolerance;
- sample unit, sampling method, measurement window, and exclusions;
- evidence producer and exact evidence roots;
- statistical mode: deterministic, descriptive, paired comparison, or
  controlled stochastic comparison.

A plugin, objective, metric definition, cohort, or evidence-producer change
invalidates direct comparison unless an explicit rebaseline is recorded.

### Use stable units and denominators

Use these canonical units:

| Question | Unit |
| --- | --- |
| Workflow outcome | eligible native run |
| Stage quality | validated handoff |
| Planning and implementation | canonical task |
| Review quality | immutable repo-wave review |
| Graph quality | active requirement or active trace branch |
| MCP reliability | tool call stratified by tool and dataset size |
| Delivery reliability | install, promotion, rollback, or recovery attempt |
| Agent efficiency | evidence-qualified run or completed canonical task |

Never use raw event count as a proxy for completed work. Always publish the
numerator, denominator, excluded count, exclusion reasons, and sample size next
to a percentage.

### Stratify before aggregating

At minimum, stratify outcome data by:

- plugin version and exact commit;
- DIRECT versus DELEGATED execution;
- repository and wave;
- implementation versus remediation task;
- event schema and event origin;
- complete versus incomplete automation evidence;
- normal, negative, recovery, and capacity scenarios.

Do not merge legacy imports with native v2 runs for stochastic or efficiency
claims. Legacy data may be reported separately as migration evidence.

### Missing evidence is not zero

Missing, stale, truncated, incompatible, unauthenticated, or wrong-revision
evidence produces `inconclusive`. It must not be converted to a zero, silently
removed from a denominator, or treated as a successful no-finding result.

### Keep telemetry bounded and sanitized

Metric evidence may store numeric counts, durations, sizes, stable refs, error
codes, and digests. It must not store raw prompts, secrets, credentials,
production payloads, unrestricted logs, or full agent conversations.

## Metric record parameters

Each metric result should contain these fields, even before a machine-readable
metric contract exists:

| Field | Meaning |
| --- | --- |
| `metric_id` | Stable identifier from the catalog below |
| `definition_version` | Version of the metric formula and inclusion rules |
| `question` | Exact decision the metric supports |
| `direction` | `higher`, `lower`, or `zero-only` |
| `formula` | Numerator, denominator, aggregation, and units |
| `target` | Frozen desired value |
| `minimum_material_effect` | Smallest change considered operationally useful |
| `negative_tolerance` | Regression boundary |
| `hard_guardrail` | Whether failure invalidates the total verdict |
| `sample_unit` | Run, handoff, task, branch, tool call, or delivery attempt |
| `cohort` | Included versions, repositories, modes, and scenario classes |
| `window` | Time or fixed sample boundary |
| `baseline_ref` | Immutable baseline record or version |
| `evidence_producer` | autoCI, runtime collector, compiler, journal, or operator |
| `evidence_refs` | Exact commit-, build-, snapshot-, and digest-bound references |
| `exclusions` | Count and declared reasons |
| `value` | Raw measured result |
| `confidence` | Deterministic, descriptive, confidence interval, or insufficient |
| `status` | `improved`, `neutral`, `regressed`, or `inconclusive` |

## Metric catalog

### A. Outcome and convergence

| ID | Metric and formula | Evidence | Target policy |
| --- | --- | --- | --- |
| `EFF-01` | **Evidence-qualified convergence rate (EQCR)** = converged eligible runs / all eligible started runs | v2 run-start and terminal events, complete audit receipts, exact build refs | Primary plugin outcome. Provisional target `>= 0.90` only after at least 20 eligible native runs; before that report descriptively. |
| `EFF-02` | **Accepted convergence rate** = converged runs with exact-revision `automation_status=passed` / eligible runs | `EFF-01` evidence plus authentic autoCI evidence | External paired outcome. Never substitute `audited` for acceptance. |
| `EFF-03` | **First-pass convergence rate** = converged runs with no remediation run / converged runs | review and remediation events, `remediates_run_ref` | Higher is better. Provisional target `>= 0.70`; calibrate after a native baseline. |
| `EFF-04` | **Late reroute rate** = runs routed from `app-dev` or `app-analyze` back to research, spec, graph, or plan / runs reaching either late stage | validated handoffs and finding routes | Lower is better. Report by target stage; provisional guardrail `<= 0.10`. |
| `EFF-05` | **Blocker rate** = runs ending in canonical `blocked` / eligible started runs | process events and operator reason refs | Lower is better, but always publish access, credential, and operator-stop categories separately. |
| `EFF-06` | **Remediation load** = remediation runs and remediation tasks / implemented runs | process index and task ledger | Report median, p90, and maximum. Initial target: median `<= 1`; no unresolved remediation at `audited`. |
| `EFF-07` | **Decision escape rate** = late-stage `needs-spec` findings / runs reaching graph, plan, development, or analysis | finding records and handoffs | Lower is better; it measures decisions discovered after their intended stage. |
| `EFF-08` | **Finding escape rate** = valid severe findings first discovered after an earlier audit profile claimed complete / earlier complete audits | immutable audit receipts and later findings | Zero-only for integrity and authority findings; lower is better for other classes. |

### B. Traceability and planning quality

| ID | Metric and formula | Evidence | Target policy |
| --- | --- | --- | --- |
| `TRC-01` | **Seven-dimension coverage** = active requirement dimensions validly mapped or explicitly not applicable / all required dimensions | functional map v3 and semantic audit evidence | Exactly 100%; each active requirement has behavior, dependency, state, API, data, integration, and error dimensions. |
| `TRC-02` | **End-to-end trace completeness** = active trace branches with `spec -> decision -> requirement -> functionality/behavior -> task -> code -> test -> evidence` / all active branches | traceability index and complete profile results | 100% at convergence; incomplete pagination is not success. |
| `TRC-03` | **Task readiness validity** = tasks admitted to execution with closed decisions, complete refs, valid targets, and satisfied dependencies / admitted tasks | task ledger, topological plan, dispatch packets | 100%. |
| `TRC-04` | **Graph defect density** = dangling refs + unknown edges + forbidden cycles + orphan active nodes per 100 active entities | compiler errors, diagnostics, exact build | Zero for a publishable build. Report raw counts as well as density. |
| `TRC-05` | **Impact-query accuracy** = correct returned affected refs / expected refs on golden change fixtures, with recall reported separately | controlled golden fixtures | Precision and recall must both be 100% for deterministic fixtures. |

### C. Process and governance correctness

| ID | Metric and formula | Evidence | Target policy |
| --- | --- | --- | --- |
| `PRC-01` | **Valid handoff rate** = handoffs with a canonical status/target pair, exact digests, complete process evidence, and required trace evidence / all handoffs | handoff records, workflow definition, audit receipts | 100%. |
| `PRC-02` | **Finding route accuracy** = findings routed exactly through the workflow registry / all findings | finding records and `finding_routes` | 100%; no unregistered route may be emitted. |
| `PRC-03` | **Lifecycle integrity** = tasks and sessions following permitted state transitions / all tasks and sessions | ledger, process journal, dispatch/result packets | 100%; failed tasks are never reopened and closed sessions are never reused. |
| `PRC-04` | **Journal immutability and idempotency** = identical replays accepted as no-op plus conflicting same-key payloads rejected / all replay scenarios | controlled journal scenarios | 100%; any overwrite or ambiguous result is a hard failure. |
| `PRC-05` | **Journal ownership validity** = events written by DIRECT primary or repo-L2 / all journal writes | process events and authority refs | 100%; L3 journal writes are a hard failure. |
| `PRC-06` | **Review independence** = repo-wave reviews performed read-only against pinned commit ranges by the correct critic / all reviews | review packets and immutable refs | 100%; review of live worktree state or critic mutation is a hard failure. |
| `PRC-07` | **Mutation atomicity** = write assignments retaining zero or one task-scoped commit and no unrelated changes / all write assignments | result packets and Git evidence | 100%. |

### D. Determinism, MCP, install, and delivery

| ID | Metric and formula | Evidence | Target policy |
| --- | --- | --- | --- |
| `DET-01` | **Build reproducibility** = repeated compiles of byte-identical sources producing identical build ref and index bytes / deterministic compile scenarios | build receipts and artifact digests | 100%. |
| `DET-02` | **Drift rejection** = stale CAS, stale cursor, source drift, path escape, and unsafe source scenarios rejected with the expected code / all negative scenarios | CI scenario evidence | 100%. |
| `OPS-01` | **Unexpected MCP error rate** = unexpected errors / valid tool calls | sanitized runtime call records | Provisional target `<= 1%`; expected negative-test rejections are excluded and reported separately. |
| `OPS-02` | **Tool latency** = p50, p95, and maximum duration by tool, dataset stratum, page size, and depth | bounded runtime telemetry | Freeze a hardware/runtime profile. Target no p95 regression greater than 10% unless an approved SLO changes. |
| `OPS-03` | **Wire-budget compliance** = requests and responses within 64 KiB and 16 KiB budgets / all calls | MCP envelope telemetry | 100%; oversized valid responses must fail with the declared bounded error. |
| `OPS-04` | **Pagination completeness** = paginated queries followed to no cursor with a stable snapshot / all queries used for decisions | query result refs and cursor chain | 100%; stale or truncated decision evidence is a hard failure. |
| `OPS-05` | **Surface isolation** = read-only server calls without mutation capability and maintainer server exposing only its two declared tools / all capability checks | MCP `tools/list`, tool annotations, mutation evidence | 100%; arbitrary path, shell, network, Git, credential, source, or ledger mutation exposure is a hard failure. |
| `OPS-06` | **Recovery convergence** = interrupted install, role publication, promotion, and rollback scenarios returning to one valid receipted state / all recovery scenarios | exact-revision CI and deployment receipts | 100%. |
| `OPS-07` | **Registry consistency** = plugin manifest, marketplace version, role definitions, generated TOML, installer discovery, and deployed receipt agreeing / all audited revisions | manifests, rendered profiles, receipts | 100%. |

### E. Delegation and role selection

| ID | Metric and formula | Evidence | Target policy |
| --- | --- | --- | --- |
| `AGT-01` | **Execution-mode accuracy** = workstreams correctly kept DIRECT or admitted through a valid delegation gate / all workstreams | authority refs and routing records | 100%; inferred delegation authority is a hard failure. |
| `AGT-02` | **Role-selection accuracy** = golden assignments selecting the exact deterministic profile / all golden assignments | assignment facts and selected profile identity | 100%. |
| `AGT-03` | **Packet identity preservation** = dispatch/result pairs preserving all authority, role, repo, trust, and session identities byte-for-byte / all pairs | packet records | 100%. |
| `AGT-04` | **Parent boundary compliance** = DELEGATED parent/L1/L2 actions limited to permitted orchestration / all delegated actions | bounded action records | 100%; target access or parent execution fallback is a hard failure. |
| `AGT-05` | **Session reuse validity** = continuations reusing only the permitted open app-worker or critic session / all continuations | dispatch lifecycle records | 100%. |
| `AGT-06` | **Scope adherence** = changed and inspected targets inside the authorized assignment bounds / all assignments | result packets, sanitized file refs, Git evidence | 100%. |

### F. Resource efficiency and throughput

These metrics are essential to evaluate efficiency, but the current canonical
event and handoff schemas do not provide their inputs.

| ID | Metric and formula | Required evidence | Target policy |
| --- | --- | --- | --- |
| `CST-01` | **Time to convergence** = terminal audit time - run-start time | monotonic or UTC timestamps bound to run refs | Report median, p90, and p95 by mode and task stratum. |
| `CST-02` | **Stage latency** = next valid handoff time - stage-entry time | stage entry/exit timestamps | Identify bottlenecks; do not aggregate different stages into one mean. |
| `CST-03` | **Agent effort per converged run** = model turns, tool calls, and tokens / converged runs | sanitized per-run counters | Lower is better only while outcome and guardrail metrics do not regress. |
| `CST-04` | **Retry and no-progress ratio** = repeated equivalent attempts or unchanged waits / all attempts | attempt ids and normalized outcome fingerprints | Target zero repeated unchanged waits; other retries require a frozen tolerance. |
| `CST-05` | **Evidence-qualified throughput** = converged runs or completed canonical tasks / fixed wall-clock period | timestamps and exact outcome evidence | Report with work-mix stratification; never optimize throughput alone. |
| `CST-06` | **Cost per accepted outcome** = model/API cost / `EFF-02` accepted runs | sanitized cost counters and exact autoCI evidence | External paired metric; unavailable when acceptance is `not_run`. |

## Hard gates

A numeric effectiveness score is invalid if any of these gates fails:

| Gate | Pass condition |
| --- | --- |
| `G1 Snapshot integrity` | Current pointer, receipt, indexes, source digest, journal digest, and evidence all bind the same exact build. |
| `G2 Determinism` | Byte-identical sources reproduce byte-identical build artifacts; drift and stale CAS fail closed. |
| `G3 Journal integrity` | Events are immutable, idempotent, causally valid, and written only by authorized owners. |
| `G4 Authority and safety` | No inferred delegation, identity drift, parent fallback, unauthorized mutation, unsafe path, secret exposure, or trust-boundary breach. |
| `G5 Route consistency` | Every status, target, finding route, and ownership rule comes from a canonical registered vocabulary. |
| `G6 Evidence completeness` | No truncated, stale, wrong-revision, unauthenticated, authored-only, or missing evidence is treated as complete. |
| `G7 Acceptance honesty` | `audited` is never represented as product acceptance; `automation_status` remains explicit. |
| `G8 Delivery safety` | Install, publication, recovery, rollback, and removal converge to one valid receipted state without unmanaged-byte loss. |

One hard-gate failure produces `nonconformant`. Insufficient evidence to decide a
gate produces `inconclusive`.

## Threshold and statistical policy

### Deterministic metrics

Contract, route, schema, digest, safety, authority, idempotency, golden-query,
and recovery checks are deterministic. Their target is 100% success or zero
violations. A statistical average must not soften a deterministic failure.

### Observational workflow metrics

Use a rolling cohort of at least 20 eligible native runs for provisional trend
claims. Also show the last 30 and 90 calendar days when timestamps become
available. If fewer than 20 eligible runs exist, publish raw values and mark the
trend `inconclusive`.

The initial `EFF-01`, `EFF-03`, `EFF-04`, `EFF-06`, and `OPS-01` targets in this
document are calibration defaults, not immutable policy. Freeze them in the
audit charter before measurement and revise them only through an explicit new
definition version.

### Stochastic agent comparisons

For model- or prompt-sensitive comparisons:

1. predeclare control and treatment revisions;
2. use the same immutable scenario fixtures and acceptance criteria;
3. randomize or alternate execution order;
4. run a small pilot to estimate variance;
5. choose sample size through a predeclared power or precision requirement;
6. report effect size and uncertainty, not only a p-value;
7. classify insufficient samples as `inconclusive`;
8. never mix results from different models, reasoning efforts, sandboxes, or
   plugin commits without explicit stratification.

### Improvement verdict

For a compatible baseline and comparison:

- `improved`: the minimum material effect is reached, progress versus the
  immutable baseline remains positive, and every hard guardrail passes;
- `neutral`: no material improvement and no regression beyond tolerance;
- `regressed`: the primary metric exceeds its negative tolerance or any hard
  guardrail fails;
- `inconclusive`: evidence is missing, stale, incompatible, or insufficient.

## Optional composite index

A single score is secondary to the metric vector and hard gates. If a compact
version-comparison number is required, calculate it only when every hard gate
is decided and passed and each domain has at least 80% evidence coverage:

```text
Plugin Effectiveness Index =
  100 * (0.30 * C + 0.20 * T + 0.25 * P + 0.15 * O + 0.10 * R)
```

Where every component is normalized to `0..1`:

- `C`: convergence outcomes (`EFF-*`);
- `T`: traceability and planning (`TRC-*`);
- `P`: process, governance, and agent correctness (`PRC-*`, `AGT-*`);
- `O`: MCP, determinism, installation, and delivery (`DET-*`, `OPS-*`);
- `R`: resource efficiency (`CST-*`).

Do not calculate the index when resource telemetry is absent; publish the
domain vector instead. Product acceptance is not a hidden component of this
index and remains visible as `EFF-02`.

## Telemetry required to close current gaps

The safest design is a separate append-only metric evidence stream bound to
existing run, task, build, and commit refs. Do not silently add operational
telemetry to the semantic journal without an approved contract revision.

Minimum fields are:

- `metric_event_ref`, `plugin_version`, and exact plugin commit;
- `repo_ref`, `wave_ref`, `run_ref`, optional `task_ref`, and stage;
- source snapshot, journal, build, and commit refs;
- event or attempt start and end timestamps, plus monotonic duration;
- execution mode, profile, model family, reasoning effort, and sandbox class;
- attempt number and normalized outcome fingerprint;
- tool name, success or stable error code, duration, input bytes, output bytes,
  page size, and depth;
- model turns, input tokens, output tokens, cached tokens, and cost when
  available without exposing content;
- exact autoCI evidence ref and automation status;
- collector version, evidence digest, and sanitization status.

Store no raw prompt, completion, secret, credential, production payload, or
unbounded log. Retention and access rules must be declared before collection.

## Agent audit methodology

### Audit roles and authority

The audit starts as DIRECT unless the operator explicitly requests delegation
or a trusted task-scoped state artifact requires it. Complexity, available
agents, or the value of independent review does not create delegation
authority.

If delegation is authorized, use current installed profiles only:

| Audit need | Current role boundary |
| --- | --- |
| Bounded static repository inspection | `explorer` |
| Sanitized runtime, MCP, service, or exact CI evidence | `graph-evidence-reader` |
| One explicitly bounded local diagnostic command | `diagnostic-command-runner` |
| Pinned `base_commit..wave_head` change review | `wave-change-critic` |
| Separate security assessment with a named satisfied trigger | `security-analysis-critic` |
| Tests, validators, schemas, lints, cache checks, plugin validation, and executable audits | CI only |

Every delegated assignment requires an exact immutable authority, explicit
profile, `fork_turns=none`, read-only or mutation mode, bounded targets, and a
typed result. Audit agents do not mutate plugin files, the journal, or evidence.

### Phase 1: Charter

Create an immutable audit charter containing:

- audit objective and requested decisions;
- exact repository and plugin commit;
- installed revision when runtime or deployment is in scope;
- comparison baseline;
- included surfaces and explicit exclusions;
- selected metrics and hard gates;
- cohort, fixtures, sample plan, and statistical mode;
- evidence authorities and allowed tools;
- audit roles and delegation authority when applicable;
- stop conditions and output paths.

Do not start evidence collection until definitions and denominators are frozen.

### Phase 2: Snapshot and provenance preflight

Establish one exact evaluation snapshot:

1. identify authoritative remote `main` and `dev` topology;
2. record Git commit, plugin version, marketplace version, and working-tree
   state;
3. read the opted-in source manifest;
4. resolve the current build pointer and immutable receipt;
5. compare build, trace index, process index, source snapshot, and journal
   digests;
6. confirm whether compiler reconciliation is current or drifted;
7. reject stale handoffs, wrong-revision evidence, or mixed installed/source
   revisions.

The preflight output is a compact evidence manifest. If the snapshot cannot be
made exact, stop with `inconclusive` rather than continuing on approximate data.

### Phase 3: Static consistency audit

Review exact files and compare machine authorities rather than prose alone.

#### Workflow and contracts

- workflow stages equal the skill stage set;
- every handoff status has exactly one registered target;
- finding kinds route only to canonical statuses;
- stage owners, journal writers, and L3 prohibitions agree;
- `audited` gates and acceptance boundaries agree across workflow, schemas,
  skills, runtime, and README;
- historical schemas are read-only and new writes use current schemas;
- schema references and versions resolve to existing files.

#### Graph and process runtime

- compiler semantics come only from registered structured sources;
- tracked code contributes digests but not inferred meaning;
- limits agree between manifest, runtime, schemas, and documentation;
- every edge kind has one canonical family, transitivity, impact, and cycle
  policy;
- current pointer, build receipt, indexes, and query cache reject drift;
- process events are append-only, idempotent, causally scoped, and repo-wave
  bound;
- pagination cursors are opaque, query-bound, and snapshot-bound.

#### MCP surface

- `app-graph` exposes only the eight declared read-only tools;
- `app-graph-maintainer` exposes only `graph_compile` and
  `process_record_event`;
- tool schemas reject extra or malformed fields;
- lifecycle behavior supports only declared MCP protocol versions;
- request, response, page, depth, source, entity, edge, event, and link limits
  agree;
- no maintainer capability provides shell, network, Git, credential, arbitrary
  path, source, ledger, or Markdown mutation.

#### Agents and delegation

- authoritative JSON role definitions and generated TOML profiles match;
- each profile declares model, reasoning effort, sandbox, and exact identity;
- role selection rules are deterministic and ordered;
- packet schemas preserve authority and session identity;
- parent, L1, L2, worker, reviewer, and security boundaries do not overlap;
- app-worker reuse and critic reuse obey the permitted lifecycle;
- one task produces at most one retained task-scoped commit;
- no hidden helper, duplicate critic, L4, or parent fallback is introduced.

#### Install and delivery

- plugin and marketplace versions agree;
- installer discovery matches the current profile catalog;
- retired profiles remain one-way migration inputs, not aliases;
- generated managed blocks preserve unmanaged bytes;
- symlink, path, ownership, lock, race, and crash boundaries fail closed;
- promotion and rollback remain exact-revision, transactional, and receipted;
- runtime state never claims acceptance from authored scenarios alone.

### Phase 4: Executable evidence plan

The read-only audit agent designs and reviews the scenario matrix. CI executes
the scenarios and returns evidence for the exact full commit. At minimum the
matrix covers:

1. every forward route and every canonical remediation route;
2. `audited` as the only successful terminal status;
3. exact seven-dimension requirement mapping;
4. full trace branches and missing segment routing;
5. dependency ordering, superseded tasks, and forbidden cycles;
6. deterministic rebuild and current-build no-op;
7. stale CAS, source drift, stale cursor, wrong query cursor, and all resource
   limits;
8. identical event replay and conflicting same-key event rejection;
9. task success, failure, blocked result, immutable review, remediation, and
   rereview;
10. DIRECT entry, valid DELEGATED entry, invalid authority, fresh-task gate,
    packet identity drift, session closure, and unavailable typed role;
11. overlapping versus independent repo and target scheduling;
12. read-only and maintainer MCP separation, malformed protocol input,
    notification behavior, and response budgets;
13. role rendering, manifest consistency, install, uninstall, recovery, and
    legacy migration;
14. promotion crash boundaries, rollback, receipt races, managed-block drift,
    and unsafe filesystem objects;
15. missing, stale, failed, and passed automation evidence without false
    acceptance claims.

Each scenario has a stable id, immutable fixture digest, expected result or
error code, hard-gate mapping, exact producer, and evidence ref. A scenario
name without executed exact-revision evidence has status `not_run`.

### Phase 5: Runtime measurement

On fixed hardware and runtime versions, CI or an authorized runtime collector:

- measures every MCP tool by dataset strata, page sizes, and traversal depths;
- records p50, p95, maximum latency, success, stable error code, and wire sizes;
- distinguishes expected negative-test errors from unexpected failures;
- repeats deterministic operations to prove reproducibility;
- exercises install and delivery recovery at declared interruption points;
- publishes only sanitized numeric evidence and exact refs.

The audit agent checks provenance and calculates `DET-*` and `OPS-*`; it does
not reinterpret missing runtime evidence as success.

### Phase 6: Historical workflow measurement

From native exact-revision events only:

1. group events into repo-wave runs;
2. verify one valid run-start and exact task scope;
3. resolve immutable reviews, remediation runs, handoffs, and terminal evidence;
4. follow every audit cursor to completion in the evidence producer;
5. calculate `EFF-*`, `TRC-*`, `PRC-*`, and `AGT-*` by stratum;
6. join time and cost evidence only through stable refs;
7. publish missing-field and excluded-run counts;
8. compare only compatible metric-definition and plugin versions.

If time or resource telemetry is absent, report `CST-*` as unavailable. Do not
approximate agent duration from Git commit timestamps or file mtimes.

### Phase 7: Adversarial review

Challenge the evidence and metric design for:

- a denominator that excludes failures;
- duplicated events counted as independent outcomes;
- legacy and native run mixing;
- incomplete cursor chains;
- stale build, installed revision, or automation evidence;
- a good aggregate hiding a failed repository, mode, stage, or tool;
- a high composite score masking a hard-gate failure;
- `audited` presented as accepted;
- throughput improved by skipping required stages or evidence;
- raw prompt, secret, or production-data leakage through telemetry;
- a metric change presented as product improvement without rebaseline.

Any unresolved challenge becomes a finding or makes the affected metric
`inconclusive`.

### Phase 8: Findings, routing, and verdict

Each finding records:

- stable finding id and audit ref;
- severity and confidence;
- observed behavior and exact expected authority;
- exact file, build, event, packet, scenario, or receipt evidence refs;
- affected metrics and hard gates;
- canonical route;
- owner and remediation requirement;
- status and superseding finding ref when applicable.

Use both severity and workflow route:

| Severity | Meaning |
| --- | --- |
| `P0 critical` | Corruption, unsafe mutation, secret exposure, authority bypass, or false product-acceptance claim |
| `P1 high` | Deterministic route, lifecycle, digest, audit, or recovery failure that can invalidate outcomes |
| `P2 medium` | Material coverage, reliability, performance, or rework problem without immediate integrity loss |
| `P3 low` | Local clarity, maintenance, or observability weakness with bounded impact |

| Finding class | Canonical route |
| --- | --- |
| Missing source | `needs-research` |
| Product or decision conflict | `needs-spec` |
| Semantic ref, graph, or cycle gap | `needs-graph` |
| Task, implementation, evidence, review, remediation, or audit-plan gap | `needs-plan` |
| Credential, access, or explicit operator stop | `blocked` |

Do not invent an additional handoff status for missing evidence. Under the
current workflow registry, an evidence gap routes to `needs-plan`.

The report verdict is separate from workflow status:

- `conformant`: all hard gates pass and selected metrics meet frozen targets;
- `conformant_with_findings`: hard gates pass, but noncritical improvement
  findings remain;
- `nonconformant`: at least one hard gate fails;
- `inconclusive`: evidence is insufficient to decide required gates or metrics.

Always report `automation_status` independently. A semantic/process verdict is
not product acceptance.

### Phase 9: Remediation and re-audit

Remediation uses new canonical tasks and, when applicable, a new remediation
run. Original task and review records remain immutable. Re-audit the exact
remediated commit with the same metric definition, fixtures, cohort rules, and
hard gates. If any definition changes, create a new baseline lineage rather
than overwriting the prior result.

## Audit output packet

A complete recurring audit should produce these standalone artifacts:

1. `audit-charter`: scope, snapshot, metrics, targets, roles, and evidence
   authorities;
2. `evidence-manifest`: exact source, installed, build, journal, CI, runtime,
   and fixture refs with digests;
3. `metric-results`: one record per metric with numerator, denominator, value,
   exclusions, evidence, and confidence;
4. `findings`: immutable findings with severity, canonical route, and affected
   gates;
5. `audit-report`: concise verdict, hard-gate matrix, metric scorecard,
   limitations, and remediation priorities;
6. optional `next-wave-plan`: proposed work only; it is not authoritative until
   materialized through the normal app workflow.

Recommended summary table:

| Field | Value |
| --- | --- |
| Audit ref | stable id |
| Plugin source commit / version | exact values |
| Installed commit / version | exact values or `not_in_scope` |
| Build / source / journal refs | exact values |
| Baseline ref | exact value |
| Evidence coverage | percent and missing count |
| Hard gates | pass / fail / inconclusive per gate |
| Primary metric | value, target, effect, confidence |
| Product acceptance | explicit automation status |
| Verdict | one report verdict |
| Findings | count by severity and route |
| Re-audit trigger | exact condition |

## Preliminary findings from this research

### `AUD-OBS-01`: route vocabulary drift

`scripts/app_graph_audit.py` can emit `needs-evidence` for a missing terminal
candidate or `automation_status=not_run`. `needs-evidence` is absent from the
canonical workflow route registry and the handoff status schema, while the
workflow maps `evidence-gap` to `needs-plan` and the README lists only the
canonical routes.

Impact: a terminal process audit may return a route that cannot be represented
by the canonical handoff contract. This is a `P1 high` static consistency
finding routed to `needs-plan`. It requires exact CI evidence before a product
fix is accepted.

### `AUD-OBS-02`: efficiency instrumentation gap

The current event, handoff, and build contracts contain no timestamps,
durations, attempt ids, tool counters, token counters, or cost fields.

Impact: `CST-01` through `CST-06` cannot be measured from canonical artifacts.
Git timestamps and file mtimes are not valid substitutes. This is a `P2
medium` observability finding routed to `needs-plan`.

### `AUD-OBS-03`: insufficient outcome cohort

The current index contains two runs and 42 events, with 41 v1 events, one v2
event, and all automation evidence marked `not_run`. Authored scenarios exist,
but the repository explicitly states that they are not acceptance evidence.

Impact: structural strengths can be described, but current convergence,
acceptance, latency, cost, and throughput cannot be claimed. The current
empirical effectiveness verdict remains `inconclusive` with
`automation_status=not_run`.

## Recommended audit cadence

- **Every source release**: all hard gates, deterministic scenarios, manifest
  and role consistency, graph reconciliation, and exact delivery evidence.
- **Every contract, route, MCP, role, installer, or CD change**: the affected
  static checklist plus all mapped regression scenarios.
- **Monthly after telemetry exists**: rolling workflow outcomes, runtime SLOs,
  resource efficiency, and cohort drift.
- **After a P0 or P1 finding**: exact-commit remediation audit before promotion.
- **Quarterly**: metric-definition review, gaming analysis, retention review,
  and explicit rebaseline decision when definitions or objectives changed.

The audit closes only when every required metric and hard gate has an explicit
result, failure, or `inconclusive` reason. Silence is never evidence.
