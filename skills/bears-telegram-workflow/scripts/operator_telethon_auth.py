#!/usr/bin/env python3
"""Run local operator Telegram QR auth with Infisical-provided API keys.

The parent command installs isolated operator dependencies and starts a child
process. The child reads Telegram API id/hash from Infisical, renders a QR code
only in the local terminal, and writes a private local Telethon session file.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import shlex
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

DEFAULT_INFISICAL_ENV = "dev"
DEFAULT_INFISICAL_PATH = "/kubernetes/bears-platform-telegram/tdlib"
DEFAULT_SESSION_ROOT = "/srv/bears/.secrets/telegram-sessions"
DEFAULT_SESSION_NAME = "operator-telethon"
DEFAULT_VENV = "/tmp/bears-telethon-auth-venv"
DEFAULT_ENV_FILE = "/srv/bears/tg.env"
DEPENDENCIES = ("Telethon>=1.44,<2", "qrcode>=8,<9")
REQUIRED_INFISICAL_KEYS = (
    ("api-id", "TELEGRAM_API_ID", "TGLIB_API_ID"),
    ("api-hash", "TELEGRAM_API_HASH", "TGLIB_API_HASH"),
)


class OperatorAuthError(RuntimeError):
    """Raised when local operator auth cannot continue safely."""


@dataclass(frozen=True)
class OperatorAuthConfig:
    """Configuration for the operator QR auth command."""

    infisical_env: str = DEFAULT_INFISICAL_ENV
    infisical_path: str = DEFAULT_INFISICAL_PATH
    session_root: str = DEFAULT_SESSION_ROOT
    session_name: str = DEFAULT_SESSION_NAME
    venv_path: str = DEFAULT_VENV
    env_file: str = DEFAULT_ENV_FILE
    project_id_env: str = "INFISICAL_PROJECT_ID"

    @property
    def python_bin(self) -> str:
        """Return the Python binary inside the operator venv."""
        return str(Path(self.venv_path) / "bin" / "python")


@dataclass(frozen=True)
class DoctorResult:
    """Non-secret local dependency status."""

    infisical_cli: bool
    python3_cli: bool
    session_name_valid: bool

    @property
    def ok(self) -> bool:
        """Return true when local checks passed."""
        return all((self.infisical_cli, self.python3_cli, self.session_name_valid))

    def to_dict(self) -> dict[str, bool]:
        """Return JSON-ready status."""
        return {
            "infisical_cli": self.infisical_cli,
            "python3_cli": self.python3_cli,
            "session_name_valid": self.session_name_valid,
            "ok": self.ok,
        }


def validate_session_name(session_name: str) -> bool:
    """Return whether the session name is one safe path segment."""
    return bool(session_name) and "/" not in session_name and ".." not in session_name


def find_secret(data: dict[str, Any], aliases: Sequence[str]) -> str | None:
    """Return the first non-empty value for one alias group."""
    for alias in aliases:
        value = data.get(alias)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def secret_presence_from_json(raw_json: str) -> dict[str, bool]:
    """Check required Infisical keys without returning values."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise OperatorAuthError("Infisical export did not return valid JSON.") from exc
    if not isinstance(data, dict):
        raise OperatorAuthError("Infisical export JSON must be an object.")
    api_id = find_secret(data, REQUIRED_INFISICAL_KEYS[0])
    api_hash = find_secret(data, REQUIRED_INFISICAL_KEYS[1])
    return {"api_id": api_id is not None, "api_hash": api_hash is not None}


def parse_env_file(path: Path) -> dict[str, str]:
    """Read allowed local env values and ignore 2FA password keys."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    forbidden_keys = {"TG_PASS", "TELEGRAM_PASSWORD", "TWO_FA_PASSWORD"}
    with path.open(encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            if key in forbidden_keys:
                print(f"warning: {key} ignored; enter 2FA only in hidden prompt")
                continue
            value = shlex.split(raw_value, comments=False, posix=True)
            values[key] = value[0] if value else ""
    return values


def load_operator_env(config: OperatorAuthConfig) -> dict[str, str]:
    """Load allowed local operator env values."""
    values = parse_env_file(Path(config.env_file))
    if "TG_LOGIN" in os.environ:
        values["TG_LOGIN"] = os.environ["TG_LOGIN"]
    return values


def env_file_key_presence(path: Path) -> dict[str, bool]:
    """Return selected env-file key presence without exposing values."""
    keys: set[str] = set()
    if path.is_file():
        with path.open(encoding="utf-8", errors="replace") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" in line:
                    keys.add(line.split("=", 1)[0].strip())
    return {
        "env_file_exists": path.is_file(),
        "infisical_project_id_present": "INFISICAL_PROJECT_ID" in keys,
        "tg_login_present": "TG_LOGIN" in keys,
        "tg_pass_present": "TG_PASS" in keys,
    }


def preflight(config: OperatorAuthConfig) -> dict[str, bool | str]:
    """Run non-secret operator readiness checks, including Infisical access."""
    env_path = Path(config.env_file)
    presence: dict[str, bool | str] = {
        "env_file": str(env_path),
        **env_file_key_presence(env_path),
    }
    try:
        api_id, api_hash = load_api_credentials(config)
    except OperatorAuthError as exc:
        return {**presence, "ok": False, "error": str(exc)}
    return {
        **presence,
        "api_id_present": bool(api_id),
        "api_hash_present": bool(api_hash),
        "ok": True,
    }


def load_api_credentials(config: OperatorAuthConfig) -> tuple[int, str]:
    """Read Telegram API credentials from Infisical without printing values."""
    operator_env = load_operator_env(config)
    cmd = [
        "infisical",
        "export",
        "--silent",
        f"--env={config.infisical_env}",
        f"--path={config.infisical_path}",
        "--format=json",
    ]
    project_id = operator_env.get(config.project_id_env) or os.environ.get(
        config.project_id_env
    )
    if project_id:
        cmd.append(f"--projectId={project_id}")
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip().splitlines()[:2]
        message = "; ".join(stderr) or "infisical export failed"
        raise OperatorAuthError(message) from exc
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise OperatorAuthError("Infisical export JSON must be an object.")
    api_id = find_secret(data, REQUIRED_INFISICAL_KEYS[0])
    api_hash = find_secret(data, REQUIRED_INFISICAL_KEYS[1])
    if not api_id or not api_hash:
        raise OperatorAuthError("missing api-id/api-hash in Infisical path")
    try:
        return int(api_id), api_hash
    except ValueError as exc:
        raise OperatorAuthError("api-id must be an integer") from exc


def prepare_session_stem(config: OperatorAuthConfig) -> Path:
    """Create private session directory and return the session stem."""
    if not validate_session_name(config.session_name):
        raise OperatorAuthError("session name must be one local path segment")
    session_dir = Path(config.session_root).expanduser().resolve()
    session_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(session_dir, 0o700)
    return session_dir / config.session_name


def chmod_session_file(session_file: Path) -> None:
    """Restrict a session file to the local owner when it exists."""
    if session_file.exists():
        os.chmod(session_file, stat.S_IRUSR | stat.S_IWUSR)


def tail(value: object, keep: int = 4) -> str | None:
    """Return only a redacted identifier tail."""
    if value is None:
        return None
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return f"***{text[-keep:]}"


def print_terminal_qr(url: str) -> None:
    """Render a Telegram login URL as terminal-only ASCII QR."""
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


async def run_qr_login(config: OperatorAuthConfig) -> dict[str, Any]:
    """Run Telethon QR login and return redacted status."""
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError

    api_id, api_hash = load_api_credentials(config)
    session_stem = prepare_session_stem(config)
    session_file = Path(f"{session_stem}.session")
    client = TelegramClient(str(session_stem), api_id, api_hash)
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            chmod_session_file(session_file)
            return {
                "ok": True,
                "already_authorized": True,
                "session_file": str(session_file),
                "session_file_mode": "0600",
                "user_id_tail": tail(getattr(me, "id", None)),
            }
        qr_login = await client.qr_login()
        print("[3/5] scan this QR in Telegram mobile app")
        print_terminal_qr(qr_login.url)
        print("[4/5] waiting for scan; enter 2FA only here if requested")
        try:
            await qr_login.wait(timeout=180)
        except SessionPasswordNeededError:
            password = getpass.getpass("Telegram 2FA password, input hidden: ")
            if not password:
                raise OperatorAuthError("Telegram 2FA password is required")
            await client.sign_in(password=password)
        me = await client.get_me()
        chmod_session_file(session_file)
        return {
            "ok": True,
            "already_authorized": False,
            "session_file": str(session_file),
            "session_file_mode": "0600",
            "user_id_tail": tail(getattr(me, "id", None)),
        }
    finally:
        await client.disconnect()


def doctor(config: OperatorAuthConfig) -> DoctorResult:
    """Run local non-secret checks."""
    return DoctorResult(
        infisical_cli=shutil.which("infisical") is not None,
        python3_cli=shutil.which("python3") is not None,
        session_name_valid=validate_session_name(config.session_name),
    )


def run_secret_probe(config: OperatorAuthConfig) -> dict[str, bool]:
    """Fetch Infisical JSON and return only key presence flags."""
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


def run_parent(config: OperatorAuthConfig) -> int:
    """Prepare an isolated venv and launch the child QR auth process."""
    if not validate_session_name(config.session_name):
        raise OperatorAuthError("session name must be one local path segment")
    preflight_result = preflight(config)
    print(json.dumps(preflight_result, sort_keys=True))
    if not preflight_result.get("ok"):
        return 1
    print("[1/5] prepare local python env")
    subprocess.run(["python3", "-m", "venv", config.venv_path], check=True)
    subprocess.run(
        [config.python_bin, "-m", "pip", "install", "-q", *DEPENDENCIES],
        check=True,
    )
    print("[2/5] loading api-id/api-hash from Infisical")
    env = os.environ.copy()
    env["BEARS_TELETHON_AUTH_CHILD"] = "1"
    cmd = [
        config.python_bin,
        str(Path(__file__).resolve()),
        "--env",
        config.infisical_env,
        "--path",
        config.infisical_path,
        "--session-root",
        config.session_root,
        "--session-name",
        config.session_name,
        "--env-file",
        config.env_file,
        "child-qr",
    ]
    result = subprocess.run(cmd, check=False, env=env)
    if result.returncode == 0:
        print("[5/5] helper finished")
    return int(result.returncode)


def run_child_qr(config: OperatorAuthConfig) -> int:
    """Run the child QR auth flow after dependency setup."""
    old_umask = os.umask(0o077)
    try:
        result = asyncio.run(run_qr_login(config))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OperatorAuthError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    finally:
        os.umask(old_umask)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    parser = argparse.ArgumentParser(
        description="Operator interface for local Telegram QR auth via Infisical."
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
    parser.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        help="Optional local env file; TG_PASS is rejected.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Run non-secret local checks.")
    subparsers.add_parser("preflight", help="Check tg.env and Infisical readiness.")
    subparsers.add_parser("run-qr", help="Run terminal-only QR auth.")
    subparsers.add_parser("child-qr", help=argparse.SUPPRESS)
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
        env_file=args.env_file,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the operator CLI and print only redacted output."""
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    try:
        if args.command == "doctor":
            result = doctor(config)
            print(json.dumps(result.to_dict(), sort_keys=True))
            return 0 if result.ok else 2
        if args.command == "preflight":
            result = preflight(config)
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("ok") else 2
        if args.command == "run-qr":
            return run_parent(config)
        if args.command == "child-qr":
            return run_child_qr(config)
        if args.command == "probe-secrets":
            print(json.dumps(run_secret_probe(config), sort_keys=True))
            return 0
    except (OperatorAuthError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
