---
name: app-context-index
description: Reconcile authoritative app artifacts into current traceability and process indexes before app workflow stages. Use at run or wave entry, after source digest drift, or for an explicit needs-index refresh.
---

# App Context Index

## Boundary

Run as a cross-cutting preflight, not as an eighth sequential app stage. For `DIRECT`, the primary performs the bounded collection and index update. For `DELEGATED`, follow `$subagents` before data access. The skill owns only derived indexes; it never changes product meaning, source documents, code, tests, ledger tasks, stage status, or acceptance.

Authoritative inputs remain constitution, research, specification, functional map, plans, ledger, code, tests, results, reviews, commits, and existing evidence. The indexes are rebuildable relationship caches and never override those sources.

## Contract

Load only these plugin contracts:

- `contracts/app-workflow-definition.v1.json` for stages, routes, finding routes, and edge semantics;
- `contracts/app-context-index-result.v1.schema.json` for the preflight result;
- `contracts/app-traceability-index.v2.schema.json` and `contracts/app-process-index.v1.schema.json` for owned artifacts;
- `contracts/app-functional-map.v2.schema.json` when semantic mapping exists.

The owned consuming-app artifacts are `docs/app-traceability-index.v2.json` and `docs/app-process-index.v1.json`. Store relative source paths, an optional symbol/API/test anchor, and a SHA-256 content digest; never copy source bodies into an index.

## Refresh procedure

1. Collect the bounded authoritative artifact inventory and calculate one deterministic `source_snapshot_digest` over sorted `(relative path, content digest)` pairs.
2. If both tracked indexes carry the same digest and no explicit `needs-index` exists, return `current` without modifying either file.
3. If only `docs/app-functional-graph.v1.json` exists, normalize it once into v2 entities and typed relations. Preserve every legacy ref through `aliases` or `replacements`; report an unmappable record instead of guessing it. After all current ledger anchors use v2 refs, remove the active v1 file rather than maintaining two live indexes.
4. Rebuild trace entities and edges from exact source refs. Use the edge registry in the workflow definition; undeclared edge kinds are `semantic-map-gap` findings.
5. Append process events for the actual run, handoff, wave, task, review, remediation, and commit refs. Do not synthesize events for work that did not occur.
6. Write both indexes with the same source digest and monotonically increasing revision, then return one `app-context-index-result.v1`.

## Findings and routing

- Missing source knowledge: `incomplete`, target `needs-research`.
- Conflicting accepted decisions or requirements: `conflict`, target `needs-spec`, with both source refs.
- Missing or stale semantic mapping: `incomplete`, target `needs-graph`.
- Missing dependency or task coverage: `incomplete`, target `needs-plan`.
- Access, credential, unavailable source, or explicit operator stop: `incomplete`, target `blocked`.

Do not infer conceptual truth. Record exact conflicting refs and let `app-specify` resolve them. Every subsequent `app-stage-handoff.v2` carries the current index refs, revisions, digest, and `context_index_result_ref`.
