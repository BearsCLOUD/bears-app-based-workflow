# Governance Drift Summary

This file lists every current governance drift finding from `docs/reference/capability-governance-rules.md`.

Drift means a checked runtime, repository, cache, CI, hook, connector, or agent surface differs from the stated Bears workflow, plugin constitution, or governance principle.

## Rollup

- Total findings: 207.
- Canonical detail source: `docs/reference/capability-governance-rules.md`.
- This file is an operator-facing index, not a replacement for validator-backed remediation.

## Highest-impact drift groups

1. Plugin does not prove control over all active agents.
   - Unmanaged global and target-local agents remain outside concrete Bears role/principle binding.
2. Constitution role keys do not match active agent names.
   - Scoped principles use abstract L1/L2/L3/reviewer keys that do not bind to concrete agent inventories.
3. L1/L2 lifecycle rule is not fully propagated.
   - Stale target-local hook and agent text can still imply L2 spawn-packet behavior instead of L1 task decomposition and L2 governance review.
4. Active project hooks reference missing plugin scripts.
   - Hook paths name scripts that are not present in the plugin source tree.
5. Hook proof checks presence, not effective execution.
   - Cache delivery can pass without proving active hook execution.
6. Plugin manifest does not prove runtime control surfaces.
   - The manifest does not declare agents, apps, or MCP servers and current plugin discovery evidence is incomplete.
7. Deferred connector tools are outside Bears policy binding.
   - Connector namespaces can be exposed without Bears role, principle, or data-boundary proof.
8. External-account mutation tools are not gated by Bears policy proof.
   - Gmail, Drive, Slack, Calendar, GitHub, and OpenAI Platform flows need a Bears policy packet boundary before mutation.
9. Secret governance is not bound to OpenAI API key setup.
   - OpenAI API key flow is not proven to route through the Bears secret-factory policy.
10. Untrusted-content policy is not centralized in Bears governance.
   - Connector content rules are not one Bears-controlled catalog/validator surface.
11. Decision logs do not require principle or validator evidence.
   - Decision records can omit principle ids, role gate reference, validator evidence, and catalog SHA.
12. Scope matrix owner lineage is too weak.
   - Owner lineage checks do not bind roles to principle scopes.
13. Constitution file coverage omits governance findings.
   - The constitution file-coverage validator does not cover the audit findings file.
14. GitHub diagnostics can skip core governance jobs.
   - Operator-dispatched diagnostics path flags can skip role/workflow, hook policy, and dirty/boundary jobs.
15. Dirty local source prevents exact conformance proof.
   - Unrelated local modifications keep source, main, cache, and CI from being one clean proof surface.
16. Plugin cache sync proves delivery, not governance completeness.
   - Exact SHA delivery does not prove hooks, agents, connectors, logs, or CI-job coverage are governed.

## Full drift index

- W1: installed-cache-drift
- W2: delivery-state-stale-after-successful-ci
- W3: fast-test-selection-low-confidence
- W4: agent-registration-runtime-refresh-required
- W5: non-bears-global-agent-coverage-is-indirect
- W6: hook-policy-source-probes-pass-but-runtime-cache-proof-is-missing
- W7: principles-validate-but-agent-binding-is-not-complete-proof
- W8: new-audit-artifact-path-is-unmapped
- W9: principles-bind-to-layers-not-agent-identities
- W10: plugin-constitution-not-visible-in-most-agent-prompts
- W11: active-agent-inventory-is-not-owned-by-plugin
- W12: marketplace-and-installed-cache-sha-are-stale
- W13: bounded-runtime-evidence-tooling-gap
- W14: unknown-layer-hook-allows-tools
- W15: target-local-codex-hooks-are-unmapped
- W16: target-local-codex-agents-are-separate-from-plugin-agents
- W17: user-codex-config-is-unmapped-and-contains-sensitive-runtime-material
- W18: hook-event-schema-contract-is-not-proven
- W19: parent-workspace-gitlink-lags-plugin-main
- W20: active-model-instructions-do-not-reference-plugin-workflow
- W21: target-local-hooks-reference-missing-plugin-scripts
- W22: plugin-hooks-and-project-hooks-are-different-implementations
- W23: hook-registration-schema-mismatch-risk
- W24: installed-cache-diff-spans-governance-code
- W25: installed-cache-misses-current-audit-evidence
- W26: plugin-manifest-does-not-declare-agent-registration
- W27: cache-state-schema-pass-is-not-delivery-pass
- W28: stale-cache-trash-remains-runtime-visible
- W29: current-all-agent-audit-has-no-dedicated-spec-kit-packet
- W30: role-route-validation-requires-manual-tests-that-local-policy-bans
- W31: matching-hook-wrappers-hide-stale-hook-dependencies
- W32: codex-plugin-list-does-not-report-bears-workflow-plugin
- W33: constitution-validators-do-not-prove-per-agent-principle-binding
- W34: ten-canonical-agent-tomls-are-not-platform-role-backed
- W35: plugin-hook-commands-depend-on-runtime-working-directory
- W36: plugin-hooks-have-no-post-tool-event
- W37: workflow-catalog-claims-installation-prevents-bypass-without-runtime-proof
- W38: canonical-global-agent-prompts-have-partial-plugin-reference-coverage
- W39: agent-registration-sync-passes-despite-filename-aliasing
- W40: agent-tomls-have-runtime-profile-fields-but-no-tool-policy-field
- W41: agent-developer-instructions-do-not-carry-l1-l2-l3-or-principle-markers
- W42: active-skill-docs-still-recommend-manual-unit-tests
- W43: bears-goal-prompt-skill-has-stale-relative-validator-reference
- W44: agent-workflow-runtime-state-is-absent
- W45: scoped-l2-hook-allows-with-missing-default-state
- W46: ci-does-not-update-plugin-cache-sync-state
- W47: docs-only-governance-audit-ci-skips-role-workflow-and-unit-jobs
- W48: active-codex-custom-agent-config-registers-only-one-bears-agent
- W49: l1-l2-l3-workflow-layer-ids-are-not-agent-identities
- W50: disabled-telegram-skill-surfaces-still-have-active-spec-skill-md-references
- W51: installed-cache-still-contains-old-l1-l2-task-split-policy
- W52: fast-hooks-do-not-load-principle-constitution-catalogs
- W53: scoped-l2-l3-hooks-have-no-tool-allowlist
- W54: active-external-plugin-and-mcp-inventory-is-not-validated-by-bears-plugin
- W55: active-custom-orchestrator-agent-has-stale-l2-spawn-packet-language
- W56: target-local-agent-role-coverage-is-partial-and-one-route-is-wrong-scope
- W57: target-local-agent-prompts-mostly-lack-plugin-principle-workflow-markers
- W58: active-project-session-hook-still-instructs-l2-spawn-packets
- W59: plugin-worktree-has-uncommitted-specify-boundary-expansion
- W60: active-project-agent-directory-contains-stale-backup-prompt-material
- W61: global-agent-inventory-is-larger-than-bears-registration-scope
- W62: unmanaged-non-bears-agents-are-invisible-to-registration-extra-check
- W63: non-bears-global-agent-prompts-lack-bears-governance-markers
- W64: principle-catalog-validation-does-not-bind-principles-to-agent-prompts
- W65: agentic-constitution-role-scopes-are-layer-labels-not-agent-identities
- W66: plugin-constitution-gate-does-not-cover-active-environment-agents
- W67: active-bears-skills-do-not-define-all-agent-or-principle-binding
- W68: report-first-skills-are-not-runtime-enforcement
- W69: plugin-manifest-claims-runtime-guard-delivery-without-active-skill-proof
- W70: docs-only-audit-ci-does-not-run-all-agent-or-principle-binding-checks
- W71: hook-policy-ci-validates-hook-manifest-json-not-hook-decisions
- W72: ci-and-test-selection-do-not-inspect-active-environment-agent-directories
- W73: subagent-orchestration-policy-lacks-l1-l2-no-spawn-binding
- W74: agent-workflow-map-lacks-l1-l2-no-spawn-fields
- W75: agent-github-dev-cd-doc-conflicts-with-no-spawn-per-task
- W76: roadmap-control-spawn-gates-do-not-carry-l1-l2-no-spawn-policy
- W77: agent-registration-proof-lacks-main-sha-ci-and-delivery-binding
- W78: user-agent-registration-check-does-not-cover-target-local-agent-root
- W79: agent-registration-check-reports-tool-schema-staleness-but-still-passes
- W80: active-model-instructions-do-not-load-plugin-principles
- W81: active-session-start-hooks-do-not-emit-principle-or-delivery-state
- W82: pre-tool-policy-layer-guard-does-not-load-principle-catalogs
- W83: most-principle-ids-are-absent-from-runtime-facing-surfaces
- W84: hooks-have-zero-principle-id-coverage
- W85: principle-id-coverage-is-strongest-in-scripts-tests-not-agent-prompts
- W86: codex-plugin-list-does-not-show-bears-but-shows-other-enabled-plugins
- W87: non-bears-skill-surface-mostly-lacks-bears-governance-markers
- W88: bears-plugin-manifest-does-not-own-external-plugin-tool-surfaces
- W89: active-mcp-servers-are-configured-outside-bears-manifest-authority
- W90: deferred-tool-surface-includes-mutating-connectors-outside-bears-policy
- W91: bears-governance-skills-explicitly-do-not-cover-mcp-and-connector-behavior
- W92: dirty-governance-worktree-blocks-current-state-proof
- W93: uncommitted-hook-event-migration-is-not-delivered-or-runtime-proven
- W94: untracked-specify-layer-expands-authority-without-delivery-proof
- W95: uncommitted-ci-workflow-expands-validation-without-main-proof
- W96: dirty-readme-and-spec-claim-specify-layer-before-delivery
- W97: dirty-ci-and-hook-docs-create-split-authority-for-hook-events
- W98: l1-l2-fix-has-content-equivalence-but-no-main-ancestry-proof
- W99: deferred-tool-discovery-can-expand-mutating-surface-after-startup
- W100: effective-config-snapshot-defaults-do-not-reflect-active-plugin-and-mcp-inventory
- W101: global-agent-registration-can-be-current-while-installed-plugin-cache-is-stale
- W102: codex-plugin-discovery-omits-bears-while-config-and-cache-reference-it
- W103: dirty-stop-hook-closeout-guard-is-not-delivered
- W104: effective-hook-proof-state-is-stale-and-does-not-prove-runtime-invocation
- W105: dirty-manifest-and-docs-claim-stop-guard-before-delivery
- W106: stop-closeout-guard-detects-only-explicit-payload-or-env-intent
- W107: delivered-spec-kit-and-stop-hook-sync-failed-main-ci
- W108: test-selection-map-does-not-cover-new-specify-surface
- W109: remediated-findings-stay-open-without-resolution-state
- W110: delivery-complete-does-not-prove-hook-invocation
- W111: active-global-agent-prompts-still-lack-governance-markers
- W112: source-plugin-agent-prompts-do-not-carry-principle-ids
- W113: plugin-delivery-closeout-can-be-misread-as-feature-plan-completion
- W114: dirty-specify-ignore-policy-conflicts-with-tracked-head
- W115: corrective-history-restores-specify-but-leaves-audit-noise
- W116: exact-cache-sync-still-not-visible-in-codex-plugin-list
- W117: delivery-state-is-ignored-runtime-artifact
- W118: active-model-instructions-still-do-not-load-bears-plugin-governance
- W119: project-hook-event-schema-still-differs-from-plugin-hook-schema
- W120: hook-validator-still-checks-pretask-while-manifest-uses-userpromptsubmit
- W121: stop-hook-is-outside-agentic-workflow-decision-cli
- W122: pretooluse-allows-l1-when-tool-name-is-missing
- W123: pretooluse-allows-unknown-agent-layer-with-tool-name
- W124: manifest-prompt-required-does-not-require-a-manifest-prompt-field
- W125: constitution-validation-commands-conflict-with-agent-local-test-ban
- W126: target-local-agents-have-no-source-digest-or-principle-binding
- W127: agent-registration-sync-has-no-target-local-target
- W128: no-active-spec-kit-feature-packet-for-plugin-workflow-proof
- W129: staged-specify-deletion-hides-generated-state-behind-ignore-rules
- W130: effective-environment-resolver-is-sanitized-metadata-not-runtime-proof
- W131: effective-config-fixture-claims-runtime-surfaces-with-non-live-counts
- W132: effective-config-runtime-claims-do-not-match-current-plugin-list
- W133: main-can-advance-without-exact-cache-sync-state
- W134: decision-json-required-fields-do-not-match-decision-log-schema
- W135: decision-log-closeout-proof-is-ignored-runtime-only
- W136: plugin-install-command-does-not-match-active-marketplace-resolution
- W137: active-plugin-list-still-omits-bears-workflow-plugin-after-source-cleanup
- W138: user-agent-sync-passes-while-unmanaged-global-agents-remain-outside-governance
- W139: agent-registration-sync-declares-disk-only-proof-without-active-tool-schema-verification
- W140: principle-catalogs-are-not-bound-to-most-agent-prompts
- W141: canonical-agent-source-validation-checks-codex-fields-but-not-principle-binding
- W142: target-local-agent-directory-still-outside-sync-and-principle-policy
- W143: config-enabled-plugin-does-not-match-active-plugin-inventory
- W144: cached-plugin-files-do-not-prove-active-plugin-registration
- W145: active-config-has-no-hook-registration-section
- W146: plugin-hook-commands-depend-on-runtime-plugin-root-env-vars
- W147: target-local-hooks-use-different-event-contract-and-remain-outside-plugin-cache-proof
- W148: managed-global-agents-are-stale-against-canonical-source
- W149: agent-registration-sync-remains-disk-only-runtime-proof
- W150: plugin-spec-kit-feature-packet-is-missing
- W151: manual-validation-command-policy-does-not-cover-all-authoritative-surfaces
- W152: manual-validation-approval-marker-is-line-local-and-too-broad
- W153: active-plugin-inventory-still-omits-bears-workflow-plugin
- W154: plugin-manifest-does-not-deliver-agent-registration
- W155: active-bootstrap-instructions-do-not-load-plugin-principles
- W156: constitution-principles-are-not-bound-across-agent-prompts
- W157: target-local-agent-profiles-are-outside-plugin-principle-coverage
- W158: l1-l2-source-rule-is-not-proven-active-for-target-local-or-stale-managed-agents
- W159: cache-sync-closeout-state-can-pass-while-runtime-governance-remains-unproven
- W160: docs-only-ci-path-skips-runtime-governance-tests-for-audit-findings
- W161: hook-policy-validation-only-checks-json-shape
- W162: effective-hooks-proof-name-overstates-manifest-file-presence
- W163: marketplace-fixture-test-does-not-catch-runtime-plugin-add-failure
- W164: plugin-cache-sync-validation-does-not-require-active-plugin-inventory
- W165: stop-closeout-guard-allows-no-intent-stops-with-dirty-state
- W166: canonical-agent-filenames-diverge-from-agent-type-names
- W167: active-multi-agent-policy-conflicts-with-bears-workflow-delegation
- W168: active-agent-schema-includes-unmanaged-generic-roles
- W169: target-local-bears-agents-are-outside-plugin-sync
- W170: agent-sync-runtime-checkpoint-has-no-active-tool-schema-comparison
- W171: config-agents-section-is-not-the-active-agent-authority
- W172: bootstrap-model-instructions-do-not-bind-plugin-principles
- W173: active-plugin-config-and-plugin-list-disagree
- W174: no-spec-kit-packet-for-current-plugin-governance-work
- W175: canonical-agent-prompts-do-not-bind-agentic-enterprise-catalogs
- W176: pre-tool-hook-allows-empty-event-as-unknown-agent
- W177: default-hook-controller-state-is-missing
- W178: user-prompt-hook-event-name-is-translated-to-pretask
- W179: hook-policy-has-no-input-schema-for-codex-events
- W180: l1-tool-deny-policy-does-not-fire-without-agent-layer
- W181: stop-closeout-guard-has-no-codex-stop-payload-schema
- W182: delivery-complete-does-not-require-clean-worktree
- W183: unmanaged-global-write-agents-have-no-bears-principle-binding
- W184: generic-write-agent-prompts-lack-bears-route-gate-language
- W185: target-local-write-agents-can-delegate-outside-l2-governance-wording
- W186: target-local-l1-profile-is-not-sourced-from-plugin-catalog
- W187: active-plugin-enabled-config-does-not-grant-agent-control
- W188: deferred-tool-discovery-can-add-ungoverned-connector-namespaces
- W189: external-account-mutation-tools-are-active-outside-bears-policy-proof
- W190: connected-account-read-tools-are-active-without-bears-data-boundary-proof
- W191: openai-api-key-flow-is-not-bound-to-bears-secret-factory-policy
- W192: connector-untrusted-content-rules-are-not-centralized-in-bears-policy
- W193: role-scoped-principles-do-not-bind-to-active-agent-names
- W194: scope-matrix-owner-lineage-is-not-cross-checked-against-principle-scopes
- W195: decision-log-records-do-not-carry-principle-or-gate-evidence
- W196: plugin-constitution-change-packet-is-not-required-for-audit-doc-edits
- W197: active-project-hooks-reference-missing-current-plugin-scripts
- W198: active-project-session-hook-still-prompts-l2-spawn-packets
- W199: cache-sync-effective-hooks-proof-does-not-execute-active-hooks
- W200: active-project-hooks-use-a-different-hook-contract-than-plugin-hooks
- W201: workflow-governance-doc-findings-do-not-trigger-workflow-validators
- W202: ci-summary-success-does-not-mean-required-governance-jobs-ran
- W203: plugin-constitution-file-coverage-omits-capability-governance-rules
- W204: ci-requirements-path-policy-explicitly-allows-diagnostics-to-skip-governance-jobs
- W205: local-source-conformance-is-unverifiable-while-governance-files-are-dirty
- W206: dirty-catalog-and-test-edits-can-change-role-coverage-without-cache-proof
- W207: dirty-telegram-governance-files-can-change-workflow-claims-without-closeout-proof

## Required cleanup direction

- Convert every drift item into a validator-backed rule or an explicit documented non-goal.
- Bind active agent inventories to role-scoped principles by concrete agent names.
- Make hook proof execute the active hook path or mark hooks inactive with a hard validator.
- Gate connector and external-account tools through Bears policy packets before mutation.
- Make CI success require the relevant governance jobs for any governance doc, catalog, hook, agent, or manifest change.
- Separate unrelated dirty work before claiming source/cache/CI conformance.
