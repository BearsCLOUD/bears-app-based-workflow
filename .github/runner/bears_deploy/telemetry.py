"""Official-SDK deployment telemetry; failures never alter the CD result."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
from typing import Any

import sentry_sdk

from .constants import (
    ACTIONABLE_ERROR_CODES, DEPLOY_RECEIPT_SCHEMA, GIT, PLUGIN,
    REPOSITORY_SHORTHAND, SENTRY_COMPONENT, SENTRY_DSN_FILE,
    SENTRY_SERVICE, SENTRY_TIMEOUT_SECONDS, SHA_RE,
    SUBPROCESS_DIAGNOSTIC_LIMIT, VERSION_RE,
)
from .models import DeployContext


def read_sentry_dsn() -> str | None:
    """Read the already-materialized DSN from the fixed protected file."""
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try: descriptor = os.open(SENTRY_DSN_FILE, flags)
    except OSError: return None
    try:
        metadata = os.fstat(descriptor); raw = os.read(descriptor, 4097)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600: return None
    finally: os.close(descriptor)
    try: value = raw.decode().strip()
    except UnicodeError: return None
    return value if 0 < len(value) <= 4096 else None


def gateway_digest() -> str:
    """Hash the immutable installed package without including paths or contents."""
    root = Path(__file__).resolve().parent; digest = hashlib.sha256()
    for path in sorted(root.glob("*.py")):
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode): raise RuntimeError("unsafe gateway module")
        digest.update(path.name.encode()); digest.update(b"\0"); digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _fields(error_code: str, context: DeployContext) -> dict[str, str]:
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    return {
        "error_code": error_code, "service": SENTRY_SERVICE,
        "component": SENTRY_COMPONENT, "operation": "promote",
        "repository": REPOSITORY_SHORTHAND, "plugin": PLUGIN,
        "target_sha": context.sha if SHA_RE.fullmatch(context.sha) else "unknown",
        "plugin_version": context.version if VERSION_RE.fullmatch(context.version) else "unknown",
        "workflow_run": f"{run_id}:{attempt}" if run_id.isdigit() and attempt.isdigit() else "unknown",
        "receipt_schema": DEPLOY_RECEIPT_SCHEMA, "gateway_digest": gateway_digest(),
    }


def _scrub_event(event: dict[str, Any], hint: dict[str, Any], error_code: str) -> dict[str, Any] | None:
    """Retain traceback frames while removing values, locals, PII, and request data."""
    event.pop("request", None); event.pop("user", None); event.pop("breadcrumbs", None); event.pop("modules", None)
    event["message"] = f"actionable deployment failure: {error_code}"
    values = event.get("exception", {}).get("values", [])
    for value in values:
        value["value"] = error_code
        for frame in value.get("stacktrace", {}).get("frames", []): frame.pop("vars", None)
    event["contexts"] = {key: value for key, value in event.get("contexts", {}).items() if key in {"trace", "deployment"}}
    return event


def report_sentry(error_code: str, context: DeployContext, exception: BaseException | None = None) -> str | None:
    """Capture one real actionable failure through the official SDK, best effort."""
    if error_code not in ACTIONABLE_ERROR_CODES or exception is None: return None
    try:
        dsn = read_sentry_dsn()
        if dsn is None: return None
        fields = _fields(error_code, context); release = f"{PLUGIN}@{fields['plugin_version']}+{fields['target_sha']}"
        sentry_sdk.init(
            dsn=dsn, release=release, environment="production",
            traces_sample_rate=1.0, send_default_pii=False,
            include_local_variables=False, max_breadcrumbs=0,
            integrations=[], default_integrations=False,
            shutdown_timeout=SENTRY_TIMEOUT_SECONDS,
            before_send=lambda event, hint: _scrub_event(event, hint, error_code),
        )
        with sentry_sdk.start_transaction(name="plugin-auto-cd", op="cd.promote"):
            with sentry_sdk.push_scope() as scope:
                for key, value in fields.items(): scope.set_tag(key, value)
                scope.set_context("deployment", fields)
                event_id = sentry_sdk.capture_exception(exception)
        sentry_sdk.flush(timeout=SENTRY_TIMEOUT_SECONDS)
        return f"sentry-event:{event_id}" if event_id else None
    except Exception: return None


def normalized_diagnostic(value: str) -> str:
    normalized = " ".join("".join(ch if ch.isascii() and ch.isprintable() else " " for ch in value).split())
    if not normalized: return "no diagnostic output"
    return normalized[: SUBPROCESS_DIAGNOSTIC_LIMIT - 3] + "..." if len(normalized) > SUBPROCESS_DIAGNOSTIC_LIMIT else normalized


def command_label(argv: list[str]) -> str: return "git" if argv[0] == GIT else "codex"
