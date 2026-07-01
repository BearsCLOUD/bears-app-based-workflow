# Aiogram Migration Readiness Packet

Use this packet before migrating a Telegram bot surface.

```yaml
surface: <bot/package/path>
owning_project: <repo/project>
backlog_item: <surface id from telegram-aiogram-migration-backlog.v1.json>
role_gate:
  platform_part: <catalog platform part>
  primary_role: <registered role>
  supporting_roles:
    - <registered role>
  status: matched | ROLE_COVERAGE_BLOCKER
current_framework: aiogram | python-telegram-bot | telebot | telethon | custom | unknown
migration_status: already-aiogram3-core-seed | already-aiogram3-hardening | target-aiogram3-upgrade | target-aiogram3-rewrite | not-applicable-non-bot | deferred-missing-source
artifact_gate:
  status: open | blocked-before-code | not-applicable | deferred-source-required
  missing:
    - <required artifact or evidence>
user_visible_flows:
  - command: </command or trigger>
    expected_result: <behavior>
callbacks:
  - namespace: <domain:version:action>
    data_shape: <payload schema or opaque handle>
    privilege_class: <read | operator-write | admin | financial | destructive>
    integrity: <signed | equivalent-state-bound | exception-recorded>
    actor_binding: <caller-scoped | tenant-scoped | admin-only>
    expiry: <duration or not-applicable>
    replay_protection: <nonce/store/timestamp rule>
    idempotency_key: <business key or callback token>
    audit_event: <event name>
    action: <effect>
fsm_states:
  - state: <state>
    transitions: <allowed transitions>
runtime_entrypoint: webhook | polling | bridge | unknown
side_effects:
  - <database/API/runtime action>
security_controls:
  - auth/RBAC
  - tenant boundary
  - idempotency
  - audit/log redaction
secret_governance:
  secret_source_class: <none | vault-reference | env-runtime | operator-single-use>
  rotation_owner: <team or role>
  webhook_secret_token_owner: <team or role | not-applicable>
  chat_id_classification: <private-user | operator-group | service-chat | test-only | not-applicable>
  chat_id_redaction_rule: <how chat ids are masked in docs/tests/logs>
approval_status: <not-requested | pending | approved | blocked>
security_signoff: <required | not-required | approved>
behavior_baseline:
  tests: <paths or missing>
  snapshots: <paths or missing>
  runtime_evidence: <read-only command or missing>
target_aiogram_shape:
  dispatcher_root: <module>
  routers:
    - <domain router>
  middlewares:
    - <middleware>
  fsm_storage: <dev/prod storage>
  dependency_injection: <services>
validation:
  - <commands>
rollout:
  - <dev/stage/prod promotion gates>
exceptions:
  - <reason and expiry/review date>
```

## Acceptance gate

Do not start a broad rewrite until the backlog item validates, the role gate matches, mandatory project artifacts are present or explicitly blocking, and commands, callbacks, FSM states, side effects, secret governance, and validation are either inventoried or explicitly marked missing with a follow-up task.
