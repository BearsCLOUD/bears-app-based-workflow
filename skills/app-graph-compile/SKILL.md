---
name: app-graph-compile
description: Compile opted-in structured app graph sources and immutable process events into deterministic build-bound indexes.
---

# App Graph Compile

This is a lower-level operation, not a workflow stage. Call `app-graph-maintainer.graph_compile` with the repository root and current `expected_build_ref`. Require an opted-in v1 source manifest. The compiler reads only the fixed workflow, functional map, task ledger, and event journal; it never derives semantics from Markdown.

Treat `DUPLICATE_REF`, `DANGLING_REF`, `EDGE_KIND_UNKNOWN`, `JOURNAL_CORRUPT`, `PATH_ESCAPE`, `SOURCE_LIMIT`, and `CAS_MISMATCH` as fail-closed results. A current result is a no-op. A built result must bind byte-identical deterministic indexes, one `build_ref`, source snapshot digest, journal digest, and build receipt. Do not record a process event for compilation.
