#!/usr/bin/env python3
"""Prepare operator-only Yandex 360 DNS secret setup instructions."""
from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_ENV_SLUG = "prod"
DEFAULT_SECRET_PATH = "/global/dns/yandex360/bears-ru"
DEFAULT_DNS_DOMAIN = "bears.ru"
DEFAULT_YANDEX_API_BASE = "https://api360.yandex.net"
DEFAULT_SCOPE = "directory:read_organization directory:manage_dns"
NO_SAFE_TRANSPORT_CATEGORY = "operator_manual_secret_entry_required"
UPSTREAM_FAILURE_CATEGORY = "infisical_upstream_failure"

REQUIRED_OPERATOR_KEYS = [
    "YANDEX360_DNS_CLIENT_ID",
    "YANDEX360_DNS_CLIENT_SECRET",
    "YANDEX360_DNS_ORG_ID",
    "YANDEX360_DNS_OAUTH_TOKEN",
]

DEFAULTED_KEYS = {
    "YANDEX360_DNS_DOMAIN": DEFAULT_DNS_DOMAIN,
    "YANDEX360_DNS_API_BASE": DEFAULT_YANDEX_API_BASE,
    "YANDEX360_DNS_SCOPE": DEFAULT_SCOPE,
}


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def normalize_infisical_domain(value: str | None) -> str:
    raw = (
        value
        or os.environ.get("INFISICAL_API_URL")
        or os.environ.get("INFISICAL_HOST_URL")
        or "https://app.infisical.com"
    ).rstrip("/")
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


def planned_keys() -> list[str]:
    return sorted([*REQUIRED_OPERATOR_KEYS, *DEFAULTED_KEYS])


def runtime_presence() -> dict[str, list[str]]:
    keys = planned_keys()
    return {
        "present_keys": [key for key in keys if os.environ.get(key)],
        "missing_keys": [key for key in keys if not os.environ.get(key)],
    }


def upstream_failure_packet(exit_code: int) -> dict[str, object]:
    """Return stable failure metadata without upstream stdout or stderr."""
    return {
        "category": UPSTREAM_FAILURE_CATEGORY,
        "exit_code": exit_code,
        "secret_values_printed": False,
        "stored": False,
    }


def operator_instruction_packet(args: argparse.Namespace) -> dict[str, object]:
    payload: dict[str, object] = {
        "category": NO_SAFE_TRANSPORT_CATEGORY,
        "environment": args.env_slug,
        "infisical_api": normalize_infisical_domain(args.infisical_domain),
        "required_action": (
            "Enter the listed keys directly in Infisical or another operator-approved "
            "secret manager. Do not paste values into chat, shell history, or files."
        ),
        "secret_path": args.secret_path,
        "secret_values_printed": False,
        "stored": False,
        "would_update_keys": planned_keys(),
        "write_mode": "disabled_no_file_secret_transport",
    }
    if args.from_runtime_env:
        payload.update(runtime_presence())
    return payload


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-slug", default=DEFAULT_ENV_SLUG, help="Infisical environment slug")
    p.add_argument("--secret-path", default=DEFAULT_SECRET_PATH, help="Infisical folder path")
    p.add_argument("--project-id", default="", help="accepted for operator context only; value is not printed")
    p.add_argument("--infisical-domain", default="", help="Infisical API URL; defaults to INFISICAL_API_URL or INFISICAL_HOST_URL")
    p.add_argument("--from-runtime-env", action="store_true", help="report YANDEX360_DNS_* key presence only")
    p.add_argument("--dry-run", action="store_true", help="show target path and key names only; do not store values")
    return p


def main() -> None:
    args = parser().parse_args()
    packet = operator_instruction_packet(args)
    if args.dry_run:
        packet["dry_run"] = True
        print_json(packet)
        return
    print_json(packet)
    raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Interrupted")
