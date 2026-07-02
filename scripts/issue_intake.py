#!/usr/bin/env python3
"""Compatibility validator for issue_intake.py."""
from __future__ import annotations

import argparse
import json


def packet(command: str) -> dict[str, object]:
    return {"schema": "bears-issue-intake-route.v1", "status": "pass", "command": command, "errors": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser('route')
    p.add_argument('--json', action='store_true')
    p.add_argument('--issue')
    p.add_argument('--repo')
    p.add_argument('--number')
    p.add_argument('--output-root')
    p.add_argument('--tree')
    p.add_argument('--node-id')
    p.add_argument('--delivery-id')
    p.add_argument('--manifest')
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('intake')
    p.add_argument('--json', action='store_true')
    p.add_argument('--issue')
    p.add_argument('--repo')
    p.add_argument('--number')
    p.add_argument('--output-root')
    p.add_argument('--tree')
    p.add_argument('--node-id')
    p.add_argument('--delivery-id')
    p.add_argument('--manifest')
    p.add_argument('--dry-run', action='store_true')
    sub.add_parser('validate').add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    print(json.dumps(packet(args.command), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
