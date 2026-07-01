#!/usr/bin/env python3
"""Render and validate the local operator TDLib auth command.

This helper is an operator interface only. It does not contact Telegram and it
must not print Infisical secret values. The generated shell command performs the
live local login in the operator terminal after explicit operator execution.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

DEFAULT_INFISICAL_ENV = "dev"
DEFAULT_INFISICAL_PATH = "/kubernetes/bears-platform-telegram/tdlib"
DEFAULT_SESSION_ROOT = "/srv/bears/.secrets/telegram-sessions"
DEFAULT_SESSION_NAME = "operator"
DEFAULT_VENV = "/tmp/bears-tglib-auth-venv"
REQUIRED_INFISICAL_KEYS = (
    ("api-id", "TELEGRAM_API_ID", "TGLIB_API_ID"),
    ("api-hash", "TELEGRAM_API_HASH", "TGLIB_API_HASH"),
)
INLINE_AUTH_PY = r'''
import asyncio
import getpass
import json
import os
import stat
from pathlib import Path

from tglib import TelegramClient
from tglib.errors import SessionPasswordNeededError


def secret_value(payload, aliases):
    for alias in aliases:
        value = payload.get(alias)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def tail(value, keep=4):
    if value is None:
        return None
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return "***" + text[-keep:]


def prepare_session_stem():
    session_root = Path(os.environ["BEARS_TGLIB_SESSION_ROOT"]).expanduser().resolve()
    session_name = os.environ["BEARS_TGLIB_SESSION_NAME"]
    if not session_name or "/" in session_name or ".." in session_name:
        raise SystemExit("invalid session name")
    session_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(session_root, 0o700)
    return session_root / session_name


async def authorize(api_id, api_hash, session_stem):
    phone = input("Telegram phone, international format: ").strip()
    if not phone.startswith("+") or len(phone) < 8:
        raise SystemExit("phone must use international format")

    client = TelegramClient(
        str(session_stem),
        int(api_id),
        api_hash,
        device_model="bears-local-auth",
        system_version="local-python",
        app_version="1.0",
    )
    await client.connect()
    try:
        already_authorized = await client.is_user_authorized()
        if not already_authorized:
            sent = await client.send_code_request(phone)
            code = getpass.getpass("Telegram login code, input hidden: ").strip()
            if not code:
                raise SystemExit("Telegram login code is required")
            try:
                await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
            except SessionPasswordNeededError:
                password = getpass.getpass("Telegram 2FA password, input hidden: ")
                if not password:
                    raise SystemExit("Telegram 2FA password is required")
                await client.sign_in(password=password)
        me = await client.get_me()
        return {"authorized": True, "user_id_tail": tail(getattr(me, "id", None))}
    finally:
        await client.disconnect()


with os.fdopen(3) as secret_stream:
    payload = json.load(secret_stream)
api_id = secret_value(payload, ("api-id", "TELEGRAM_API_ID", "TGLIB_API_ID"))
api_hash = secret_value(payload, ("api-hash", "TELEGRAM_API_HASH", "TGLIB_API_HASH"))
print("[3/5] secret presence", {"api_id": bool(api_id), "api_hash": bool(api_hash)})
if not api_id or not api_hash:
    raise SystemExit("missing api-id/api-hash in Infisical path")

print("[4/5] starting Telegram login; enter phone/code/2FA only in this terminal")
session_stem = prepare_session_stem()
old_umask = os.umask(0o077)
try:
    result = asyncio.run(authorize(api_id, api_hash, session_stem))
    session_file = Path(f"{session_stem}.session")
    if session_file.exists():
        os.chmod(session_file, stat.S_IRUSR | stat.S_IWUSR)
    print(json.dumps({
        "ok": True,
        "session_file": str(session_file),
        "session_file_mode": "0600",
        **result,
    }, sort_keys=True))
finally:
    os.umask(old_umask)
'''


class OperatorAuthError(RuntimeError):
    """Raised when the operator command cannot be rendered or validated."""


@dataclass(frozen=True)
class OperatorAuthConfig:
    """Configuration for the operator-facing TDLib auth command."""

    infisical_env: str = DEFAULT_INFISICAL_ENV
    infisical_path: str = DEFAULT_INFISICAL_PATH
    session_root: str = DEFAULT_SESSION_ROOT
    session_name: str = DEFAULT_SESSION_NAME
    venv_path: str = DEFAULT_VENV
    project_id_env: str = "INFISICAL_PROJECT_ID"

    @property
    def python_bin(self) -> str:
        """Return the Python binary inside the operator venv."""
        return str(Path(self.venv_path) / "bin" / "python")


@dataclass(frozen=True)
class DoctorResult:
    """Non-secret dependency status for the operator interface."""

    infisical_cli: bool
    python3_cli: bool
    session_name_valid: bool

    @property
    def ok(self) -> bool:
        """Return true when all local non-secret checks passed."""
        return all((self.infisical_cli, self.python3_cli, self.session_name_valid))

    def to_dict(self) -> dict[str, bool]:
        """Return a compact JSON-ready result."""
        return {
            "infisical_cli": self.infisical_cli,
            "python3_cli": self.python3_cli,
            "session_name_valid": self.session_name_valid,
            "ok": self.ok,
        }


def validate_session_name(session_name: str) -> bool:
    """Return whether the session name is a single safe path segment."""
    return bool(session_name) and "/" not in session_name and ".." not in session_name


def find_secret(data: dict[str, Any], aliases: Sequence[str]) -> str | None:
    """Return the first non-empty secret value for one alias group."""
    for alias in aliases:
        value = data.get(alias)
        if value is not None and str(value).strip():
            return str(value)
    return None


def secret_presence_from_json(raw_json: str) -> dict[str, bool]:
    """Check required Infisical keys from JSON without returning their values."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise OperatorAuthError("Infisical export did not return valid JSON.") from exc
    if not isinstance(data, dict):
        raise OperatorAuthError("Infisical export JSON must be an object.")
    api_id = find_secret(data, REQUIRED_INFISICAL_KEYS[0])
    api_hash = find_secret(data, REQUIRED_INFISICAL_KEYS[1])
    return {"api_id": api_id is not None, "api_hash": api_hash is not None}


def doctor(config: OperatorAuthConfig) -> DoctorResult:
    """Run local non-secret checks for the operator command."""
    return DoctorResult(
        infisical_cli=shutil.which("infisical") is not None,
        python3_cli=shutil.which("python3") is not None,
        session_name_valid=validate_session_name(config.session_name),
    )


def shell_quote(value: str) -> str:
    """Quote a shell token using a small dependency-free rule."""
    if not value:
        return "''"
    safe = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-"
    if all(char in safe for char in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_operator_shell(config: OperatorAuthConfig) -> str:
    """Build a pasteable shell command with visible operator stages."""
    if not validate_session_name(config.session_name):
        raise OperatorAuthError("session name must be one local path segment")
    inline = INLINE_AUTH_PY.rstrip()
    return f'''cd /srv/bears
set -euo pipefail

echo "[1/5] prepare local python env"
python3 -m venv {shell_quote(config.venv_path)}
{shell_quote(config.python_bin)} -m pip install -q tglib==0.1.4

echo "[2/5] export Infisical secrets into this process only"
INFISICAL_ARGS=(--silent)
INFISICAL_ARGS+=(--env={shell_quote(config.infisical_env)})
INFISICAL_ARGS+=(--path={shell_quote(config.infisical_path)})
INFISICAL_ARGS+=(--format=json)
if [ -n "${{{config.project_id_env}:-}}" ]; then
  INFISICAL_ARGS+=(--projectId="${{{config.project_id_env}}}")
fi
export BEARS_TGLIB_SESSION_ROOT={shell_quote(config.session_root)}
export BEARS_TGLIB_SESSION_NAME={shell_quote(config.session_name)}

exec 3< <(infisical export "${{INFISICAL_ARGS[@]}}")
{shell_quote(config.python_bin)} -c "$(cat <<'PY'
{inline}
PY
)" 3<&3
exec 3<&-

echo "[5/5] helper finished"
'''


def run_operator_auth(config: OperatorAuthConfig) -> int:
    """Run the rendered auth command without exposing its generated body."""
    result = subprocess.run(["bash", "-lc", build_operator_shell(config)], check=False)
    return int(result.returncode)


def run_secret_probe(config: OperatorAuthConfig) -> dict[str, bool]:
    """Fetch Infisical JSON and return only required-key presence flags."""
    cmd = [
        "infisical",
        "export",
        "--silent",
        f"--env={config.infisical_env}",
        f"--path={config.infisical_path}",
        "--format=json",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return secret_presence_from_json(result.stdout)


def build_parser() -> argparse.ArgumentParser:
    """Build the operator interface parser."""
    parser = argparse.ArgumentParser(
        description="Operator interface for local TDLib auth via Infisical."
    )
    parser.add_argument("--env", default=DEFAULT_INFISICAL_ENV, help="Infisical env name.")
    parser.add_argument("--path", default=DEFAULT_INFISICAL_PATH, help="Infisical folder path.")
    parser.add_argument(
        "--session-root",
        default=DEFAULT_SESSION_ROOT,
        help="Private session directory.",
    )
    parser.add_argument(
        "--session-name",
        default=DEFAULT_SESSION_NAME,
        help="Safe local session name.",
    )
    parser.add_argument("--venv", default=DEFAULT_VENV, help="Local operator venv path.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Run non-secret local checks.")
    subparsers.add_parser("run", help="Run local interactive auth via Infisical.")
    subparsers.add_parser("render", help="Render the pasteable live-auth shell command.")
    subparsers.add_parser("probe-secrets", help="Check secret presence without printing values.")
    return parser


def config_from_args(args: argparse.Namespace) -> OperatorAuthConfig:
    """Create typed config from parsed arguments."""
    return OperatorAuthConfig(
        infisical_env=args.env,
        infisical_path=args.path,
        session_root=args.session_root,
        session_name=args.session_name,
        venv_path=args.venv,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the operator CLI and print only non-secret output."""
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    try:
        if args.command == "doctor":
            result = doctor(config)
            print(json.dumps(result.to_dict(), sort_keys=True))
            return 0 if result.ok else 2
        if args.command == "run":
            return run_operator_auth(config)
        if args.command == "render":
            print(build_operator_shell(config))
            return 0
        if args.command == "probe-secrets":
            print(json.dumps(run_secret_probe(config), sort_keys=True))
            return 0
    except (OperatorAuthError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}, sort_keys=True))
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
