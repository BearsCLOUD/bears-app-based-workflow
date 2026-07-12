"""Sanitized deployment telemetry; report_sentry never persists credential material."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import secrets
import stat
from typing import Any
from urllib import parse, request

from .constants import (
    ACTIONABLE_ERROR_CODES,
    DEPLOY_RECEIPT_SCHEMA,
    GIT,
    PLUGIN,
    REPOSITORY_SHORTHAND,
    SENTRY_COMPONENT,
    SENTRY_DSN_FILE,
    SENTRY_SERVICE,
    SENTRY_TIMEOUT_SECONDS,
    SHA_RE,
    SUBPROCESS_DIAGNOSTIC_LIMIT,
    VERSION_RE,
)
from .models import DeployContext


def sentry_event(error_code: str, context: DeployContext) -> dict[str, Any]:
    """Build one normalized event without exception or process payload data."""
    if error_code not in ACTIONABLE_ERROR_CODES:
        raise ValueError("non-actionable event code")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    workflow_run = f"{run_id}:{run_attempt}" if run_id.isdigit() and run_attempt.isdigit() else "unknown"
    fields = {
        "error_code": error_code,
        "service": SENTRY_SERVICE,
        "component": SENTRY_COMPONENT,
        "operation": "promote",
        "repository": REPOSITORY_SHORTHAND,
        "plugin": PLUGIN,
        "git_sha": context.sha if SHA_RE.fullmatch(context.sha) else "unknown",
        "plugin_version": context.version if VERSION_RE.fullmatch(context.version) else "unknown",
        "workflow_run": workflow_run,
        "receipt_schema": DEPLOY_RECEIPT_SCHEMA,
    }
    event_id = secrets.token_hex(16)
    return {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "level": "error",
        "logger": "bears.plugin.deploy",
        "message": "actionable deployment failure",
        "platform": "other",
        "fingerprint": [SENTRY_SERVICE, SENTRY_COMPONENT, error_code],
        "tags": fields,
        "contexts": {"deployment": fields},
    }


def sentry_request(dsn: str, event: dict[str, Any]) -> request.Request:
    """Encode one Sentry envelope; callers retain the DSN only in memory."""
    parsed = parse.urlsplit(dsn)
    path_parts = parsed.path.rstrip("/").rsplit("/", 1)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.username
        or len(path_parts) != 2
        or not path_parts[1].isdigit()
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid DSN")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    endpoint = parse.urlunsplit(
        ("https", host, f"{path_parts[0]}/api/{path_parts[1]}/envelope/", "", "")
    )
    auth = f"Sentry sentry_version=7, sentry_client=bears-plugin-gateway/1, sentry_key={parse.unquote(parsed.username)}"
    if parsed.password:
        auth += f", sentry_secret={parse.unquote(parsed.password)}"
    header = json.dumps({"event_id": event["event_id"]}, separators=(",", ":"))
    item = json.dumps({"type": "event", "content_type": "application/json"}, separators=(",", ":"))
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return request.Request(
        endpoint,
        data=f"{header}\n{item}\n{payload}".encode(),
        headers={"Content-Type": "application/x-sentry-envelope", "X-Sentry-Auth": auth},
        method="POST",
    )


def read_sentry_dsn() -> str | None:
    """Read the fixed protected credential without following links."""
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(SENTRY_DSN_FILE, flags)
    except OSError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            return None
        raw = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    if not raw or len(raw) > 4096:
        return None
    try:
        return raw.decode("utf-8").strip()
    except UnicodeError:
        return None


def report_sentry(error_code: str, context: DeployContext, *, opener: Any = request.urlopen) -> str | None:
    """Deliver best effort without changing the deployment outcome."""
    try:
        dsn = read_sentry_dsn()
        if dsn is None:
            return None
        event = sentry_event(error_code, context)
        with opener(sentry_request(dsn, event), timeout=SENTRY_TIMEOUT_SECONDS) as response:
            response.read(1)
        return f"sentry-event:{event['event_id']}"
    except Exception:
        return None


def normalized_diagnostic(value: str) -> str:
    """Return one bounded ASCII diagnostic without control characters."""
    normalized = " ".join(
        "".join(
            character if character.isascii() and character.isprintable() else " "
            for character in value
        ).split()
    )
    if not normalized:
        return "no diagnostic output"
    if len(normalized) > SUBPROCESS_DIAGNOSTIC_LIMIT:
        return normalized[: SUBPROCESS_DIAGNOSTIC_LIMIT - 3] + "..."
    return normalized


def command_label(argv: list[str]) -> str:
    return "git" if argv[0] == GIT else "codex"
