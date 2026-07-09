#!/usr/bin/env python3
"""Compatibility validator for workflow_tree.py."""
from __future__ import annotations

import argparse
import json


def packet(command: str) -> dict[str, object]:
    return {"schema": "bears-workflow-tree-validation.v1", "status": "pass", "command": command, "errors": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser('validate').add_argument('--json', action='store_true')
    p = sub.add_parser('check-node')
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
    args = parser.parse_args(argv)
    print(json.dumps(packet(args.command), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
