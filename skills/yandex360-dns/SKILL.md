---
name: yandex360-dns
description: Prepare Yandex 360 DNS review and change packets without exposing secrets. Use when Bears workflow work needs DNS records, domain verification, mail routing records, or operator-ready DNS handoff notes.
---

# Yandex 360 DNS

## Purpose

Prepare DNS record review or change packets for Yandex 360-managed domains.

## Packet fields

- Domain.
- Record name.
- Record type.
- Desired value class, without raw secrets.
- TTL.
- Reason.
- Source request.
- Operator action.
- Rollback note.

## Rules

- Never print tokens, private keys, session data, or secret values.
- Separate read-only review from requested mutation.
- Use placeholder labels for secret-backed values.
- Ask for operator approval before any live DNS mutation.
- Return exact records and rationale; do not return broad provider tutorials.
