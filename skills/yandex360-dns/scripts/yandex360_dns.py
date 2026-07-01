#!/usr/bin/env python3
"""Read-only helper for bears.ru DNS records managed by Yandex 360."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_API_BASE = "https://api360.yandex.net"
ALLOWED_API_HOSTS = {"api360.yandex.net"}
DEFAULT_SCOPE = "directory:read_organization directory:manage_dns"
LOCAL_ENV_DISABLED_MESSAGE = (
    "Local env file loading is disabled for Yandex 360 DNS. "
    "Use Infisical/runtime injection only."
)
CREDENTIAL_PERSISTENCE_DISABLED_MESSAGE = (
    "Local credential persistence is disabled for Yandex 360 DNS. "
    "Store values directly in Infisical or an operator-approved secret manager."
)
LIVE_MUTATION_DISABLED_MESSAGE = (
    "Live DNS mutation apply is disabled in this helper. "
    "Use dry-run output as the operator review packet."
)
SENSITIVE_KEYS = {
    "YANDEX360_DNS_CLIENT_SECRET",
    "YANDEX360_DNS_OAUTH_TOKEN",
    "YANDEX360_DNS_ACCESS_TOKEN",
    "YANDEX360_DNS_REFRESH_TOKEN",
}


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block redirects so OAuth tokens never follow a host change."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def validate_env_path(path: pathlib.Path | None) -> None:
    """Reject every local env file path without echoing the path."""
    if path is not None:
        raise SystemExit(LOCAL_ENV_DISABLED_MESSAGE)


def load_env(path: pathlib.Path | None = None) -> dict[str, str]:
    """Load only runtime-injected Yandex DNS environment keys."""
    validate_env_path(path)
    return {k: v for k, v in os.environ.items() if k.startswith("YANDEX360_DNS_")}


def save_env_values(_path: pathlib.Path | None, _updates: dict[str, str]) -> None:
    """Hard-disabled compatibility shim for older callers."""
    raise SystemExit(CREDENTIAL_PERSISTENCE_DISABLED_MESSAGE)


def urlopen_no_proxy(req: urllib.request.Request, timeout: int = 30):
    redirect_handler = NoRedirectHandler()
    if os.environ.get("YANDEX360_DNS_USE_PROXY") == "1":
        opener = urllib.request.build_opener(redirect_handler)
        return opener.open(req, timeout=timeout)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), redirect_handler)
    return opener.open(req, timeout=timeout)


def require(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value:
        raise SystemExit(f"Missing required env key: {key}")
    return value


def token(env: dict[str, str]) -> str:
    return env.get("YANDEX360_DNS_OAUTH_TOKEN") or env.get("YANDEX360_DNS_ACCESS_TOKEN") or ""


def validate_api_base(raw_base: str) -> str:
    parsed = urllib.parse.urlsplit(raw_base)
    if parsed.scheme != "https":
        raise SystemExit("YANDEX360_DNS_API_BASE must use https")
    if not parsed.hostname:
        raise SystemExit("YANDEX360_DNS_API_BASE must include an allowed host")
    if parsed.username or parsed.password:
        raise SystemExit("YANDEX360_DNS_API_BASE must not include credentials")
    if parsed.hostname.casefold() not in ALLOWED_API_HOSTS:
        raise SystemExit("YANDEX360_DNS_API_BASE host is not allowed")
    if parsed.port is not None:
        raise SystemExit("YANDEX360_DNS_API_BASE must not include a port")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SystemExit("YANDEX360_DNS_API_BASE must not include path, query, or fragment")
    return urllib.parse.urlunsplit(("https", parsed.hostname.casefold(), "", "", ""))


def api_base(env: dict[str, str]) -> str:
    return validate_api_base(env.get("YANDEX360_DNS_API_BASE") or DEFAULT_API_BASE)


def validate_token_request_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname is None or parsed.hostname.casefold() not in ALLOWED_API_HOSTS:
        raise SystemExit("Yandex 360 token request URL host is not allowed")
    if parsed.username or parsed.password:
        raise SystemExit("Yandex 360 token request URL must not include credentials")


def classify_http_status(status: int) -> str:
    if status == 400:
        return "bad_request"
    if status == 401:
        return "unauthorized"
    if status == 403:
        return "forbidden"
    if status == 404:
        return "not_found"
    if status == 409:
        return "conflict"
    if status == 429:
        return "rate_limited"
    if 500 <= status <= 599:
        return "upstream_server_error"
    return "upstream_http_error"


def http_error_payload(
    exc: urllib.error.HTTPError,
    category: str,
    operation: str | None = None,
    *,
    saved: bool | None = None,
) -> dict[str, Any]:
    """Return stable HTTP error metadata without upstream body content."""
    reason = str(exc.reason) if exc.reason is not None else "HTTPError"
    payload: dict[str, Any] = {
        "category": category,
        "error_class": classify_http_status(exc.code),
        "http_status": exc.code,
        "ok": False,
        "reason": reason,
    }
    if operation is not None:
        payload["operation"] = operation
    if saved is not None:
        payload["saved"] = saved
    return payload


def request_json(method: str, url: str, oauth_token: str, body: dict[str, Any] | None = None) -> Any:
    validate_token_request_url(url)
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": f"OAuth {oauth_token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen_no_proxy(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        print_json(http_error_payload(exc, "dns_api_http_error", f"{method} {url}"), stream=sys.stderr)
        raise SystemExit(1) from exc


def dns_url(env: dict[str, str], allow_placeholder: bool = False) -> str:
    org_id = env.get("YANDEX360_DNS_ORG_ID", "")
    if not org_id:
        if allow_placeholder:
            org_id = "{orgId}"
        else:
            raise SystemExit("Missing required env key: YANDEX360_DNS_ORG_ID")
    domain = env.get("YANDEX360_DNS_DOMAIN") or "bears.ru"
    return (
        f'{api_base(env).rstrip("/")}/directory/v1/org/'
        f"{urllib.parse.quote(org_id)}/domains/{urllib.parse.quote(domain)}/dns"
    )


def print_json(payload: Any, stream=None) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=stream)


def parse_field(items: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--field must be key=value, got: {item}")
        key, value = item.split("=", 1)
        value = value.strip()
        if value.lower() == "true":
            parsed: Any = True
        elif value.lower() == "false":
            parsed = False
        else:
            try:
                parsed = int(value)
            except ValueError:
                parsed = value
        out[key.strip()] = parsed
    return out


def build_record(args: argparse.Namespace) -> dict[str, Any]:
    if args.data_json:
        payload = json.loads(args.data_json)
    else:
        payload: dict[str, Any] = {"type": args.type.upper(), "name": args.name}
        optional = [
            "ttl",
            "address",
            "text",
            "exchange",
            "preference",
            "target",
            "priority",
            "weight",
            "port",
            "flag",
            "tag",
            "value",
        ]
        for key in optional:
            value = getattr(args, key, None)
            if value is not None:
                payload[key] = value
        payload.update(parse_field(args.field))
    return payload


def cmd_env_check(args: argparse.Namespace) -> None:
    env = load_env(args.env)
    keys = [
        "YANDEX360_DNS_CLIENT_ID",
        "YANDEX360_DNS_CLIENT_SECRET",
        "YANDEX360_DNS_DOMAIN",
        "YANDEX360_DNS_ORG_ID",
        "YANDEX360_DNS_OAUTH_TOKEN",
        "YANDEX360_DNS_API_BASE",
        "YANDEX360_DNS_SCOPE",
    ]
    rows = []
    for key in keys:
        value = token(env) if key == "YANDEX360_DNS_OAUTH_TOKEN" else env.get(key, "")
        rows.append({"key": key, "present": bool(value), "secret": key in SENSITIVE_KEYS})
    print_json({"env": "runtime", "keys": rows, "local_env_file_loading": "disabled"})


def cmd_auth_url(args: argparse.Namespace) -> None:
    env = load_env(args.env)
    client_id = require(env, "YANDEX360_DNS_CLIENT_ID")
    scope = args.scope or env.get("YANDEX360_DNS_SCOPE") or DEFAULT_SCOPE
    params = {
        "response_type": args.response_type,
        "client_id": client_id,
        "scope": scope,
    }
    if args.redirect_uri:
        params["redirect_uri"] = args.redirect_uri
    if args.force_confirm:
        params["force_confirm"] = "yes"
    print("https://oauth.yandex.ru/authorize?" + urllib.parse.urlencode(params))


def cmd_save_org_id(_args: argparse.Namespace) -> None:
    raise SystemExit(CREDENTIAL_PERSISTENCE_DISABLED_MESSAGE)


def cmd_orgs(args: argparse.Namespace) -> None:
    env = load_env(args.env)
    oauth_token = token(env)
    if not oauth_token:
        raise SystemExit("Missing required env key: YANDEX360_DNS_OAUTH_TOKEN")
    url = f'{api_base(env).rstrip("/")}/directory/v1/org'
    params = {"pageSize": str(args.page_size)}
    print_json(request_json("GET", url + "?" + urllib.parse.urlencode(params), oauth_token))


def cmd_list(args: argparse.Namespace) -> None:
    env = load_env(args.env)
    oauth_token = token(env)
    if not oauth_token:
        raise SystemExit("Missing required env key: YANDEX360_DNS_OAUTH_TOKEN")
    print_json(request_json("GET", dns_url(env), oauth_token))


def cmd_create(args: argparse.Namespace) -> None:
    env = load_env(args.env)
    payload = build_record(args)
    print_json(
        {
            "apply_disabled": True,
            "blocked_method": "POST",
            "dry_run": True,
            "payload": payload,
            "reason": LIVE_MUTATION_DISABLED_MESSAGE,
            "url": dns_url(env, allow_placeholder=True),
        }
    )


def cmd_delete(args: argparse.Namespace) -> None:
    env = load_env(args.env)
    url = f'{dns_url(env, allow_placeholder=True)}/{urllib.parse.quote(str(args.record_id))}'
    print_json(
        {
            "apply_disabled": True,
            "blocked_method": "DELETE",
            "dry_run": True,
            "reason": LIVE_MUTATION_DISABLED_MESSAGE,
            "url": url,
        }
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env", type=pathlib.Path, default=None, help=argparse.SUPPRESS)
    sub = p.add_subparsers(required=True)

    sp = sub.add_parser("env-check", help="show required key presence without values")
    sp.set_defaults(func=cmd_env_check)

    sp = sub.add_parser("auth-url", help="print Yandex OAuth authorize URL")
    sp.add_argument("--response-type", choices=["token"], default="token")
    sp.add_argument("--scope", default=None)
    sp.add_argument("--redirect-uri", default="https://oauth.yandex.ru/verification_code")
    sp.add_argument("--force-confirm", action="store_true")
    sp.set_defaults(func=cmd_auth_url)

    sp = sub.add_parser("save-org-id", help="disabled; store organization id in Infisical")
    sp.add_argument("org_id")
    sp.set_defaults(func=cmd_save_org_id)

    sp = sub.add_parser("orgs", help="list Yandex 360 organizations visible to the token")
    sp.add_argument("--page-size", type=int, default=100)
    sp.set_defaults(func=cmd_orgs)

    sp = sub.add_parser("list", help="list DNS records")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("create", help="build a DNS record dry-run packet; live apply disabled")
    sp.add_argument("--data-json", default="", help="exact JSON payload; overrides shortcut flags")
    sp.add_argument("--type", default="TXT")
    sp.add_argument("--name", default="")
    sp.add_argument("--ttl", type=int)
    sp.add_argument("--address")
    sp.add_argument("--text")
    sp.add_argument("--exchange")
    sp.add_argument("--preference", type=int)
    sp.add_argument("--target")
    sp.add_argument("--priority", type=int)
    sp.add_argument("--weight", type=int)
    sp.add_argument("--port", type=int)
    sp.add_argument("--flag", type=int)
    sp.add_argument("--tag")
    sp.add_argument("--value")
    sp.add_argument("--field", action="append")
    sp.add_argument("--dry-run", action="store_true", help="accepted no-op; this command is always dry-run")
    sp.set_defaults(func=cmd_create)

    sp = sub.add_parser("delete", help="build a DNS delete dry-run packet; live apply disabled")
    sp.add_argument("--record-id", required=True)
    sp.add_argument("--dry-run", action="store_true", help="accepted no-op; this command is always dry-run")
    sp.set_defaults(func=cmd_delete)

    return p


def main() -> None:
    args = parser().parse_args()
    validate_env_path(args.env)
    args.func(args)


if __name__ == "__main__":
    main()
