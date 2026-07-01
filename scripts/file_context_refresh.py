#!/usr/bin/env python3
"""Refresh or garbage-collect the tracked Bears file-context index."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts import file_context_index


def print_packet(packet: dict) -> int:
    """Print a refresh packet and return the matching process status."""
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet.get("status") == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    """Run refresh and gc commands for the file-context index."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    refresh = sub.add_parser("refresh")
    refresh.add_argument("--path", required=True)
    refresh.add_argument("--json", action="store_true")
    gc = sub.add_parser("gc")
    gc.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "refresh":
        return print_packet(file_context_index.refresh_path(args.path))
    if args.command == "gc":
        return print_packet(file_context_index.gc_index())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
