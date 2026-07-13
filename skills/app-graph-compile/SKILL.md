---
name: app-graph-compile
description: Compile opted-in structured app sources and native process events into deterministic build-bound indexes.
---

# App Graph Compile

## Boundary

Treat this skill as a lower-level deterministic operation rather than a workflow stage.

Call `app-graph-maintainer.graph_compile` with the repository root and current `expected_build_ref` only when the exact v1 manifest enables the maintainer.

Read only workflow v3, functional-map v4, task-ledger v3, artifact-catalog v2, and native event v3 sources declared by the manifest.

Never derive semantic meaning from Markdown and never record a process event for compilation.

## Result

Reject `DUPLICATE_REF`, `DANGLING_REF`, `EDGE_KIND_UNKNOWN`, `JOURNAL_CORRUPT`, `PATH_ESCAPE`, `SOURCE_LIMIT`, and `CAS_MISMATCH` without publishing a partial receipt.

Return a no-op only when the current sources and journal are byte-identical to the receipted build.

Bind every built result to one `build_ref`, source snapshot digest, journal digest, traceability index v4, process index v4, and immutable build receipt.
