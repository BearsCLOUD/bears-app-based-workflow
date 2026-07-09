# Open Issues Subagent Packets for `BearsCLOUD/bears_plugin`

Use the workstreams from `open-issues-workstreams.md`.
Rule: if a fix would break existing behavior, do not land code first; leave a comment on the issue with the breakage and reason.

## Packet 1: Roadmap and autostart control

**Controller:** `bears-development-workflow-orchestrator`
**Live controller agent:** `Dalton` / `019f0aa3-676e-7870-97cb-0e33c1d92e4a`
**Mini-model workers:** `bears-explorer, bears-worker`
**Issues:** #413, #422, #423, #467, #468, #481, #504, #505, #514, #515, #516, #518
**Allowed writes:** roadmap catalogs, roadmap scripts, roadmap tests, docs reference.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Packet 2: Agent runtime, subagents, runners, locks, and policy

**Controller:** `bears-subagent-orchestration-engineer`
**Live controller agent:** `Bacon` / `019f0aa3-a57c-7851-b716-ffb2bb973129`
**Mini-model workers:** `bears-worker, bears-runtime-verifier, bears-docs-maintainer`
**Issues:** #1, #370, #372, #373, #374, #375, #376, #381, #404, #406, #407, #408, #409, #414, #416, #417, #418, #419, #421, #426, #430, #431, #441, #442, #447, #451, #452, #453, #454, #455, #456, #457, #458, #459, #462, #474, #488, #489, #490
**Allowed writes:** subagent policy, runner scripts, lock scripts, tests, docs.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Packet 3: Issue daemon service loop and closeout pipeline

**Controller:** `bears-development-workflow-orchestrator`
**Live controller agent:** `Gibbs` / `019f0aa3-ddec-7150-8794-e403442c0061`
**Mini-model workers:** `bears-worker, bears-runtime-verifier`
**Issues:** #470, #477, #478, #487, #491, #492, #493, #494, #495, #496
**Allowed writes:** issue daemon scripts, service templates, closeout ledger scripts, tests, docs.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Packet 4: Knowledge Orchestrator control plane

**Controller:** `bears-development-workflow-orchestrator`
**Live controller agent:** `Arendt` / `019f0aa4-b8bc-70d2-bc97-4b3bd6d5205e`
**Mini-model workers:** `bears-worker, bears-runtime-verifier`
**Issues:** #499, #500, #501, #502, #503, #506, #507, #509, #511, #512, #513
**Allowed writes:** Knowledge Orchestrator runtime scripts, unit templates, state contracts, tests, docs.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Packet 5: CD, Kubernetes, and deployment custody

**Controller:** `bears-deploy-platform-engineer`
**Live controller agent:** `Hegel` / `019f0aa5-95ae-7021-a7d1-84ca523cfe2b`
**Mini-model workers:** `bears-worker, bears-runtime-verifier, bears-docs-maintainer`
**Issues:** #379, #380, #410, #461, #464, #465, #466, #469, #471, #472, #473, #475, #476, #479, #480, #482, #483, #484, #485, #486, #497, #498
**Allowed writes:** CD policy catalogs, Kubernetes safety validators, delivery docs, tests.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Packet 6: Seller route and cutover safety

**Controller:** `bears-product-app-zone-engineer`
**Live controller agent:** `Helmholtz` / `019f0aa7-670a-7d90-ab28-13c0b14cefac`
**Mini-model workers:** `bears-worker, bears-runtime-verifier`
**Issues:** #424, #427, #449, #508, #510
**Allowed writes:** seller route contracts, alias normalization, cutover docs/tests.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Packet 7: Planning, graph, and audit surfaces

**Controller:** `bears-docs-maintainer`
**Live controller agent:** `Ramanujan` / `019f0aa8-3d0f-72b1-90ad-81211434a56b`
**Mini-model workers:** `bears-explorer, bears-worker`
**Issues:** #425, #433, #436, #440, #443, #444, #445, #448, #460, #463
**Allowed writes:** planning docs, graph/audit contracts, docs reference, tests.
**Stop when:** controller returns safe-to-close, code-needed, and comment-only sets with exact evidence.

## Umbrella issues that are comment-first

- #422 roadmap-first execution
- #424 global seller migration planning graph
- #426 goal-state orchestrator
- #463 Temporal evaluation only after executable gates exist
