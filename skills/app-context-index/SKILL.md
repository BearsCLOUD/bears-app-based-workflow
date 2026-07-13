---
name: app-context-index
description: Reconcile an opted-in app repository through the deterministic graph compiler and return the current build-bound context.
---

# App Context Index

## Boundary

This is a cross-cutting facade, not a workflow stage. It owns `docs/app-graph-source-manifest.v1.json` and invokes `$app-graph-compile`; it never constructs indexes manually or infers meaning from Markdown. Structured sources remain authoritative and derived indexes remain disposable.

## Procedure

1. Read the fixed v1 manifest and require its exact workflow, functional-map, ledger, event-root, and generated paths.
2. Load the current build receipt when present. If any structured source or journal digest drifted, invoke `graph_compile` with its `expected_build_ref` compare-and-swap pin.
3. Reuse a byte-identical current build when the compiler returns `no_op=true`.
4. Return `app-context-index-result.v1` with build, snapshot, journal, trace index, process index, and build receipt refs.

The maintainer is permitted only when `maintainer_enabled=true`. It has no shell, network, Git, credential, symlink, arbitrary-path, source, ledger, or Markdown write authority. A compiler error publishes no receipted partial build.

Before every stage handoff, validate the candidate transition, record only the event that actually occurred, compile the resulting build, and place its refs and digests in `app-stage-handoff.v3`. Compiler rebuilds never create events.
