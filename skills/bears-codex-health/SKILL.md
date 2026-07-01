---
name: bears-codex-health
description: "Use for Bears Codex health diagnostics: Codex desktop/app-server freezes, MCP fan-out, session JSONL growth, token/context pressure, local Codex logs, and evidence-first remediation planning."
---

# Bears Codex Health

Use this skill when the operator asks about Codex freezes, Codex slowness, app-server CPU/RSS growth, MCP process fan-out, session JSONL growth, stream retries, timeout bursts, or safe Codex runtime cleanup planning.

This skill is evidence-first. It does not restart Codex, kill processes, delete/archive sessions, disable MCP servers, edit Codex config, or mutate runtime state unless the operator explicitly approves that exact action in the active turn.

## Workflow

1. Read the nearest `AGENTS.md`, `/srv/bears/plugins/bears/AGENTS.md`, and `agents/bears-codex-health-engineer.toml` when the plugin checkout is the target.
2. Classify the turn as one of:
   - `diagnostics-readonly`
   - `plugin-health-guidance-update`
   - `approved-runtime-remediation`
3. For diagnostics, collect bounded redacted evidence before giving a cause:
   - active Codex app-server PIDs, parent/child relation, CPU, RSS, thread count, and elapsed time;
   - 3 to 5 app-server CPU/RSS/thread samples with timestamps;
   - direct and recursive MCP child process counts grouped by command family;
   - `/home/ai1/.codex/sessions` total size, largest session files, newest session files, and short growth delta;
   - bounded pattern counts for `stream disconnected`, `retrying`, `timeout`, `timed out`, `input_tokens`, `cached_input_tokens`, `compact`, `MCP`, `failed`, `panic`, and `error`;
   - system load average to separate host load from Codex-local load.
4. Mask secret-like strings in all command output: `token`, `key`, `secret`, `password`, `bearer`, private keys, `.env` values, VPN config material, and credential-like arguments.
5. Do not print raw session JSONL bodies, raw logs, encrypted reasoning, raw chat, tool output bodies, shell history, or production data.
6. Do not run `codex doctor` during freeze triage unless the operator asks for that exact command.
7. Decide the strongest current cause from evidence only. Use measured values, not generic claims.
8. If remediation is requested, capture a before baseline, perform only the approved exact action, then repeat the same checks as after baseline.
9. Return a concise packet with status, evidence table, strongest cause, next safe check, and required approval for any mutation.

## Read-only evidence commands

Use these patterns as bounded examples. Adjust PIDs and file paths from live evidence.

```bash
ps -eo pid,ppid,etime,pcpu,pmem,rss,args --sort=-pcpu | \
  awk 'NR==1 || /codex|app-server|mcp|infisical|sentry|openaidocs|context7/ {print}' | \
  sed -E 's/(token|key|secret|password|bearer)[^ ]*/\1=[REDACTED]/Ig'

du -sh /home/ai1/.codex/sessions /home/ai1/.codex/log /home/ai1/.codex/logs 2>/dev/null || true

find /home/ai1/.codex/sessions -type f -printf '%s %TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | \
  sort -nr | head -n 20 | awk '{printf "%.1f MB %s %s %s\n", $1/1048576, $2, $3, $4}'
```

Prefer Python counters for session and log pattern counts when raw lines may expose private content.

## Remediation gate

Before mutation, ask for or confirm the exact approved action. Valid action labels are:

- `restart-codex-app-server`
- `stop-stale-diagnostic-process`
- `archive-old-session-jsonl`
- `disable-named-mcp-server`
- `edit-named-codex-config`

Each approved action must include:

- target PID, file, MCP name, or config path;
- before metrics;
- rollback or recovery path;
- after metrics;
- explicit statement that secrets and raw logs were not exposed.

## Report shape

Return this structure:

```json
{
  "schema": "bears-workflow-overlay.codex-health-evidence",
  "version": "1",
  "status": "review",
  "mode": "diagnostics-readonly",
  "evidence": [
    {
      "id": "app-server-cpu",
      "status": "observed",
      "value": "PID 123 CPU 76 percent RSS 580 MB over 5 samples"
    }
  ],
  "strongest_cause": "hot codex app-server with MCP child fan-out",
  "mutation_performed": false,
  "next_safe_check": "repeat process and MCP child counts after idle window"
}
```

Use `status: pass` only after the requested check or remediation has been revalidated. Use `status: review` for diagnosis. Use `status: blocked` only for missing access, permissions, credentials, role coverage, explicit stop, or linked-contract stop.
