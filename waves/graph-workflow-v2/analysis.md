# Graph Workflow v3 self-analysis

Run `RUN-GRAPH-WORKFLOW-V2` continues through imported legacy events, v3 implementation, an initial convergence finding, canonical remediation, and terminal audit.

The active structured artifacts are workflow definition v2, handoff v3, source manifest v1, process event v1, task ledger v2, trace index v3, process index v2, and build receipt v1. Legacy active indexes and route semantics were removed.

The semantic audit profiles verify exact ref/digest chains without executing tests. The terminal process audit verifies the causal DAG, stage ownership, terminal candidate, and open remediation state. The final recorded status is `audited`, meaning semantic/process consistency only. `automation_status` is `not_run`; autoCI acceptance was not executed by this workflow.
