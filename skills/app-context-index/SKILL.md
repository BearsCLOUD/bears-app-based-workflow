---
name: app-context-index
description: Reconcile an opted-in app repository and return its current deterministic build-bound context.
---

# App Context Index

## Boundary

Treat this skill as a cross-cutting protocol facade rather than a workflow stage.

Keep `docs/app-graph-source-manifest.v1.json` authoritative for opted-in sources, the native v3 journal root, and generated paths.

Invoke `$app-graph-compile` for deterministic derivation and never construct indexes manually or infer structured meaning from Markdown.

Never append, rewrite, or synthesize a journal event in this skill.

## Procedure

1. Read the fixed manifest and require exact workflow v3, functional-map v4, task-ledger v3, artifact-catalog v2, native event v3, trace-index v4, process-index v4, and build-receipt paths.
2. Load the current build receipt when present.
3. Compare the tracked source snapshot and journal digest to the current receipt.
4. Invoke `graph_compile` with the current `expected_build_ref` compare-and-swap pin when either digest drifted.
5. Reuse a byte-identical current build when the compiler reports `no_op=true`.
6. Return `app-context-index-result.v2` with exact build, source snapshot, journal, trace index, process index, and build receipt refs.

## Authority

Permit the maintainer only when `maintainer_enabled=true` in the exact repository manifest.

Deny the maintainer shell, network, Git, credential, symlink, arbitrary-path, semantic-source, ledger, and Markdown write authority.

Publish no partial receipt after a compiler failure.

Require the stage owner to validate its candidate transition, append only the event that occurred, invoke this skill again, and bind the resulting refs to `app-stage-handoff.v4`.
