---
name: mcp-designer
description: Design and refine MCP server surfaces, tools, schemas, packets, and response budgets. Use when Bears workflow work needs an MCP interface, tool inventory, permission boundary, or machine-readable contract.
---

# MCP Designer

## Purpose

Design MCP surfaces that are small, typed, and safe to call from Codex.

## Design packet

Include:

- Server name.
- Tool names.
- Tool purpose.
- Input schema fields.
- Output packet fields.
- Permission boundary.
- Read/write classification.
- Error shape.
- Response budget.
- Cross-tool links.

## Rules

- Prefer few tools with exact verbs over broad catch-all tools.
- Keep read and write tools separate.
- Make every mutation idempotent or explicitly one-shot.
- Return compact machine-readable packets before prose.
- Do not expose credentials or production data.
- Link each tool to the workflow stage that consumes it.
