#!/usr/bin/env python3
"""Run local Telegram QR auth with API keys sourced from a Kubernetes Secret."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from operator_telethon_auth import (
    DEPENDENCIES,
    OperatorAuthError,
    chmod_session_file,
    print_terminal_qr,
    tail,
)

DEFAULT_NAMESPACE = "bears-platform-telegram-dev"
DEFAULT_SECRET_NAME = "bears-platform-telegram-tdlib-runtime"
DEFAULT_SESSION_ROOT = "/srv/bears/.secrets/telegram-sessions"
DEFAULT_SESSION_NAME = "operator-telethon-kube"
DEFAULT_VENV = "/tmp/bears-telethon-kube-auth-venv"
DEFAULT_QR_PNG_PATH = (
    "/srv/bears/.secrets/telegram-sessions/operator-telethon-kube-qr.png"
)
API_ID_KEY = "api-id"
API_HASH_KEY = "api-hash"
KUBE_DEPENDENCIES = [
    *DEPENDENCIES,
    "Pillow>=10,<12",
    "python-socks[asyncio]>=2.4,<3",
]


@dataclass(frozen=True)
class KubeAuthConfig:
    """Configuration for Kubernetes-backed operator QR auth."""

    namespace: str = DEFAULT_NAMESPACE
    secret_name: str = DEFAULT_SECRET_NAME
    session_root: str = DEFAULT_SESSION_ROOT
    session_name: str = DEFAULT_SESSION_NAME
    venv_path: str = DEFAULT_VENV
    kube_context: str | None = None
    proxy_url: str | None = None
    qr_png_path: str | None = DEFAULT_QR_PNG_PATH

    @property
    def python_bin(self) -> str:
        """Return the Python binary inside the operator venv."""
        return str(Path(self.venv_path) / "bin" / "python")


def validate_session_name(session_name: str) -> bool:
    """Return whether the session name is one safe path segment."""
    return bool(session_name) and "/" not in session_name and ".." not in session_name


def kubectl_base(config: KubeAuthConfig) -> list[str]:
    """Build a kubectl command prefix without secret data."""
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    command.extend(["-n", config.namespace])
    return command


def run_kubectl(config: KubeAuthConfig, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run kubectl and capture output for parsing."""
    return subprocess.run(
        [*kubectl_base(config), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def secret_key_names(config: KubeAuthConfig) -> set[str]:
    """Return Kubernetes Secret data key names without values."""
    template = "{{range $k,$v := .data}}{{println $k}}{{end}}"
    result = run_kubectl(
        config,
        ["get", "secret", config.secret_name, "-o", f"go-template={template}"],
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def kube_preflight(config: KubeAuthConfig) -> dict[str, Any]:
    """Check Kubernetes secret readiness without printing secret values."""
    if shutil.which("kubectl") is None:
        return {"ok": False, "error": "kubectl_missing"}
    try:
        keys = secret_key_names(config)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "kubectl get secret failed").strip()
        return {"ok": False, "error": message}
    return {
        "ok": API_ID_KEY in keys and API_HASH_KEY in keys,
        "namespace": config.namespace,
        "secret_name": config.secret_name,
        "api_id_key_present": API_ID_KEY in keys,
        "api_hash_key_present": API_HASH_KEY in keys,
    }


def read_secret_key(config: KubeAuthConfig, key: str) -> str:
    """Read and decode one Kubernetes Secret key without printing it."""
    result = run_kubectl(
        config,
        ["get", "secret", config.secret_name, "-o", f"jsonpath={{.data.{key}}}"],
    )
    raw = result.stdout.strip()
    if not raw:
        raise OperatorAuthError(f"missing Kubernetes Secret key {key}")
    return base64.b64decode(raw).decode("utf-8").strip()


def load_kube_api_credentials(config: KubeAuthConfig) -> tuple[int, str]:
    """Load Telegram API credentials from Kubernetes Secret values."""
    api_id_raw = read_secret_key(config, API_ID_KEY)
    api_hash = read_secret_key(config, API_HASH_KEY)
    try:
        return int(api_id_raw), api_hash
    except ValueError as exc:
        raise OperatorAuthError("api-id must be an integer") from exc


def prepare_session_stem(config: KubeAuthConfig) -> Path:
    """Create private session directory and return the session stem."""
    if not validate_session_name(config.session_name):
        raise OperatorAuthError("session name must be one local path segment")
    session_dir = Path(config.session_root).expanduser().resolve()
    session_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(session_dir, 0o700)
    return session_dir / config.session_name


def effective_proxy_url(config: KubeAuthConfig) -> str | None:
    """Return the first configured proxy URL without logging it."""
    if config.proxy_url:
        return config.proxy_url
    for env_name in ("TG_PROXY_URL", "ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy"):
        value = os.environ.get(env_name)
        if value:
            return value
    return None


def telethon_proxy(proxy_url: str | None) -> tuple[Any, ...] | None:
    """Convert a proxy URL to a Telethon/PySocks proxy tuple."""
    if not proxy_url:
        return None
    import socks

    parsed = urlparse(proxy_url)
    scheme = parsed.scheme.lower()
    proxy_types = {
        "socks5": socks.SOCKS5,
        "socks5h": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "socks4a": socks.SOCKS4,
        "http": socks.HTTP,
        "https": socks.HTTP,
    }
    proxy_type = proxy_types.get(scheme)
    if proxy_type is None or not parsed.hostname or not parsed.port:
        raise OperatorAuthError("proxy URL must be socks5://host:port or http://host:port")
    rdns = scheme in {"socks5h", "socks4a"}
    username = parsed.username
    password = parsed.password
    return (proxy_type, parsed.hostname, parsed.port, rdns, username, password)


def write_qr_png(url: str, path: str | None) -> str | None:
    """Write a private QR PNG file and return its local path."""
    if not path:
        return None
    import qrcode

    qr_path = Path(path).expanduser().resolve()
    qr_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(qr_path.parent, 0o700)
    image = qrcode.make(url)
    image.save(qr_path)
    os.chmod(qr_path, stat.S_IRUSR | stat.S_IWUSR)
    return str(qr_path)


async def run_qr_login(config: KubeAuthConfig) -> dict[str, Any]:
    """Run Telethon QR login using Kubernetes-sourced API credentials."""
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    import getpass

    api_id, api_hash = load_kube_api_credentials(config)
    session_stem = prepare_session_stem(config)
    session_file = Path(f"{session_stem}.session")
    proxy = telethon_proxy(effective_proxy_url(config))
    client = TelegramClient(str(session_stem), api_id, api_hash, proxy=proxy)
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
        qr_png_path = write_qr_png(qr_login.url, config.qr_png_path)
        print("[3/5] scan this QR in Telegram mobile app")
        if qr_png_path:
            print(f"private_qr_png={qr_png_path}")
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


def run_parent(config: KubeAuthConfig) -> int:
    """Prepare isolated deps and launch Kubernetes-backed QR auth child."""
    preflight = kube_preflight(config)
    print(json.dumps(preflight, sort_keys=True))
    if not preflight.get("ok"):
        return 1
    print("[1/5] prepare local python env")
    subprocess.run(["python3", "-m", "venv", config.venv_path], check=True)
    subprocess.run(
        [config.python_bin, "-m", "pip", "install", "-q", *KUBE_DEPENDENCIES],
        check=True,
    )
    print("[2/5] loading api-id/api-hash from Kubernetes Secret")
    cmd = [
        config.python_bin,
        str(Path(__file__).resolve()),
        "--namespace",
        config.namespace,
        "--secret-name",
        config.secret_name,
        "--session-root",
        config.session_root,
        "--session-name",
        config.session_name,
        "--venv",
        config.venv_path,
    ]
    if config.kube_context:
        cmd.extend(["--context", config.kube_context])
    if config.proxy_url:
        cmd.extend(["--proxy-url", config.proxy_url])
    if config.qr_png_path:
        cmd.extend(["--qr-png-path", config.qr_png_path])
    cmd.append("child-qr")
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print("[5/5] helper finished")
    return int(result.returncode)


def run_child(config: KubeAuthConfig) -> int:
    """Run QR auth child after dependencies are installed."""
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
        description="Operator Telegram QR auth using Kubernetes Secret API keys."
    )
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--session-root", default=DEFAULT_SESSION_ROOT)
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument("--venv", default=DEFAULT_VENV)
    parser.add_argument("--context", default=None, dest="kube_context")
    parser.add_argument(
        "--proxy-url",
        default=None,
        help="Optional proxy URL; TG_PROXY_URL/ALL_PROXY/HTTPS_PROXY are also used.",
    )
    parser.add_argument(
        "--qr-png-path",
        default=DEFAULT_QR_PNG_PATH,
        help="Private local PNG path for the short-lived QR.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight-kube", help="Check Kubernetes Secret readiness.")
    subparsers.add_parser("run-qr-kube", help="Run terminal-only QR auth via kube Secret.")
    subparsers.add_parser("child-qr", help=argparse.SUPPRESS)
    return parser


def config_from_args(args: argparse.Namespace) -> KubeAuthConfig:
    """Create typed config from parsed args."""
    return KubeAuthConfig(
        namespace=args.namespace,
        secret_name=args.secret_name,
        session_root=args.session_root,
        session_name=args.session_name,
        venv_path=args.venv,
        kube_context=args.kube_context,
        proxy_url=args.proxy_url,
        qr_png_path=args.qr_png_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the operator CLI."""
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    if args.command == "preflight-kube":
        result = kube_preflight(config)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("ok") else 2
    if args.command == "run-qr-kube":
        return run_parent(config)
    if args.command == "child-qr":
        return run_child(config)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
