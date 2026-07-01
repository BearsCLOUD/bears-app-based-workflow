#!/usr/bin/env python3
"""Serve short-lived web QR auth using Telegram API keys from Kubernetes."""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import secrets
import socket
import stat
import subprocess
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Sequence

from operator_telethon_auth import OperatorAuthError, chmod_session_file, tail
from operator_telethon_kube_auth import (
    DEFAULT_NAMESPACE,
    DEFAULT_QR_PNG_PATH,
    DEFAULT_SECRET_NAME,
    DEFAULT_SESSION_NAME,
    DEFAULT_SESSION_ROOT,
    DEFAULT_VENV,
    KUBE_DEPENDENCIES,
    KubeAuthConfig,
    effective_proxy_url,
    kube_preflight,
    load_kube_api_credentials,
    prepare_session_stem,
    telethon_proxy,
)

DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8765
DEFAULT_AUTH_WINDOW_SECONDS = 900
DEFAULT_QR_REFRESH_SECONDS = 120


@dataclass(frozen=True)
class WebAuthConfig:
    """Configuration for web-served Kubernetes Telegram QR auth."""

    kube: KubeAuthConfig
    web_host: str = DEFAULT_WEB_HOST
    web_port: int = DEFAULT_WEB_PORT
    web_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    public_base_url: str | None = None
    auth_window_seconds: int = DEFAULT_AUTH_WINDOW_SECONDS
    qr_refresh_seconds: int = DEFAULT_QR_REFRESH_SECONDS

    @property
    def web_url(self) -> str:
        """Return the browser URL for the QR page."""
        base = self.public_base_url or f"http://{display_host(self.web_host)}:{self.web_port}"
        return f"{base.rstrip('/')}/{self.web_token}/"


def display_host(host: str) -> str:
    """Return a browser-usable host for bind addresses."""
    if host in {"0.0.0.0", "::"}:
        return local_lan_ip() or "127.0.0.1"
    return host


def local_lan_ip() -> str | None:
    """Best-effort local LAN address without network requests."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def make_qr_png(url: str) -> bytes:
    """Render the Telegram QR login URL as PNG bytes."""
    import qrcode

    buffer = io.BytesIO()
    image = qrcode.make(url)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def write_private_qr_png(path: str | None, data: bytes) -> str | None:
    """Write QR PNG bytes to a private local path."""
    if not path:
        return None
    qr_path = Path(path).expanduser().resolve()
    qr_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(qr_path.parent, 0o700)
    qr_path.write_bytes(data)
    os.chmod(qr_path, stat.S_IRUSR | stat.S_IWUSR)
    return str(qr_path)


class WebQrState:
    """Thread-safe state exposed by the temporary auth web page."""

    def __init__(self) -> None:
        """Create empty QR state."""
        self._lock = threading.Lock()
        self.status = "starting"
        self.qr_png: bytes | None = None
        self.message = "QR is not ready yet."
        self.result: dict[str, Any] | None = None

    def update_qr(self, png: bytes) -> None:
        """Publish a fresh QR image."""
        with self._lock:
            self.status = "scan"
            self.qr_png = png
            self.message = "Scan this QR in Telegram mobile app."

    def mark_waiting(self) -> None:
        """Mark that the helper waits for scan or 2FA."""
        with self._lock:
            self.status = "waiting"
            self.message = "Waiting for scan; enter 2FA in terminal if requested."

    def finish(self, result: dict[str, Any]) -> None:
        """Publish final authorization result."""
        with self._lock:
            self.status = "done" if result.get("ok") else "error"
            self.result = result
            self.message = "Authorized." if result.get("ok") else str(result.get("error"))

    def snapshot(self) -> dict[str, Any]:
        """Return a non-secret snapshot for JSON responses."""
        with self._lock:
            return {
                "status": self.status,
                "message": self.message,
                "qr_ready": self.qr_png is not None,
                "result": self.result,
            }

    def png(self) -> bytes | None:
        """Return QR PNG bytes if ready."""
        with self._lock:
            return self.qr_png


def html_page(config: WebAuthConfig) -> bytes:
    """Return minimal QR auth HTML."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="cache-control" content="no-store">
  <title>Telegram Operator Auth</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #101418; color: #f3f6f8; margin: 0; }}
    main {{ max-width: 520px; margin: 40px auto; padding: 24px; text-align: center; }}
    img {{ width: min(82vw, 420px); height: auto; background: white; padding: 12px; border-radius: 16px; }}
    code {{ color: #9ee493; }}
  </style>
</head>
<body>
  <main>
    <h1>Telegram Operator Auth</h1>
    <p id="status">Loading QR...</p>
    <img id="qr" alt="Telegram login QR" src="qr.png?ts={secrets.token_hex(4)}">
    <p>Telegram mobile app → Settings → Devices → Link Desktop Device.</p>
    <p>Session: <code>{config.kube.session_name}</code></p>
  </main>
  <script>
    async function tick() {{
      const status = await fetch('status.json', {{cache: 'no-store'}}).then(r => r.json());
      document.getElementById('status').textContent = status.message || status.status;
      if (status.status === 'done') {{ document.getElementById('qr').style.display = 'none'; return; }}
      if (status.status === 'error') {{ document.getElementById('qr').style.display = 'none'; return; }}
      document.getElementById('qr').src = 'qr.png?ts=' + Date.now();
      setTimeout(tick, 3000);
    }}
    tick();
  </script>
</body>
</html>
""".encode("utf-8")


def build_handler(config: WebAuthConfig, state: WebQrState) -> type[BaseHTTPRequestHandler]:
    """Build a token-gated HTTP handler for QR auth."""

    token_prefix = f"/{config.web_token}/"

    class Handler(BaseHTTPRequestHandler):
        """Serve the temporary QR auth page."""

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Suppress request logs to avoid leaking the token path."""
            return

        def send_no_store(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            """Send a no-store response body."""
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            """Handle token-gated GET requests."""
            path = self.path.split("?", 1)[0]
            if not path.startswith(token_prefix):
                self.send_no_store(HTTPStatus.NOT_FOUND, "text/plain", b"not found")
                return
            relative = path[len(token_prefix):]
            if relative in {"", "index.html"}:
                self.send_no_store(HTTPStatus.OK, "text/html; charset=utf-8", html_page(config))
                return
            if relative == "status.json":
                body = json.dumps(state.snapshot(), sort_keys=True).encode("utf-8")
                self.send_no_store(HTTPStatus.OK, "application/json", body)
                return
            if relative == "qr.png":
                png = state.png()
                if not png:
                    self.send_no_store(HTTPStatus.ACCEPTED, "text/plain", b"qr not ready")
                    return
                self.send_no_store(HTTPStatus.OK, "image/png", png)
                return
            self.send_no_store(HTTPStatus.NOT_FOUND, "text/plain", b"not found")

    return Handler


def start_server(config: WebAuthConfig, state: WebQrState) -> ThreadingHTTPServer:
    """Start the temporary token-gated HTTP server."""
    server = ThreadingHTTPServer((config.web_host, config.web_port), build_handler(config, state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def run_web_login(config: WebAuthConfig, state: WebQrState) -> dict[str, Any]:
    """Run Telegram QR login while serving QR over HTTP."""
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    import getpass

    api_id, api_hash = load_kube_api_credentials(config.kube)
    session_stem = prepare_session_stem(config.kube)
    session_file = Path(f"{session_stem}.session")
    proxy = telethon_proxy(effective_proxy_url(config.kube))
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
        loop = asyncio.get_running_loop()
        deadline = loop.time() + config.auth_window_seconds
        printed_url = False
        while True:
            png = make_qr_png(qr_login.url)
            write_private_qr_png(config.kube.qr_png_path, png)
            state.update_qr(png)
            if not printed_url:
                print(json.dumps({"ok": True, "web_url": config.web_url}, sort_keys=True))
                printed_url = True
            state.mark_waiting()
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise OperatorAuthError("auth expired")
            try:
                await qr_login.wait(timeout=min(config.qr_refresh_seconds, remaining))
                break
            except asyncio.TimeoutError:
                if deadline - loop.time() <= 0:
                    raise OperatorAuthError("auth expired") from None
                refreshed = await qr_login.recreate()
                if refreshed is not None:
                    qr_login = refreshed
            except SessionPasswordNeededError:
                password = getpass.getpass("Telegram 2FA password, input hidden: ")
                if not password:
                    raise OperatorAuthError("Telegram 2FA password is required")
                await client.sign_in(password=password)
                break
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


def run_parent(config: WebAuthConfig) -> int:
    """Prepare dependencies and launch web QR child."""
    preflight = kube_preflight(config.kube)
    print(json.dumps(preflight, sort_keys=True))
    if not preflight.get("ok"):
        return 1
    subprocess.run(["python3", "-m", "venv", config.kube.venv_path], check=True)
    subprocess.run(
        [config.kube.python_bin, "-m", "pip", "install", "-q", *KUBE_DEPENDENCIES],
        check=True,
    )
    cmd = [
        config.kube.python_bin,
        str(Path(__file__).resolve()),
        "--namespace",
        config.kube.namespace,
        "--secret-name",
        config.kube.secret_name,
        "--session-root",
        config.kube.session_root,
        "--session-name",
        config.kube.session_name,
        "--venv",
        config.kube.venv_path,
        "--web-host",
        config.web_host,
        "--web-port",
        str(config.web_port),
        "--web-token",
        config.web_token,
        "--timeout",
        str(config.auth_window_seconds),
        "--qr-refresh",
        str(config.qr_refresh_seconds),
    ]
    if config.public_base_url:
        cmd.extend(["--public-base-url", config.public_base_url])
    if config.kube.kube_context:
        cmd.extend(["--context", config.kube.kube_context])
    if config.kube.proxy_url:
        cmd.extend(["--proxy-url", config.kube.proxy_url])
    if config.kube.qr_png_path:
        cmd.extend(["--qr-png-path", config.kube.qr_png_path])
    cmd.append("child-web")
    return int(subprocess.run(cmd, check=False).returncode)


def run_child(config: WebAuthConfig) -> int:
    """Run child web server and Telegram QR login."""
    old_umask = os.umask(0o077)
    state = WebQrState()
    server = start_server(config, state)
    try:
        print(json.dumps({"ok": True, "web_url": config.web_url, "server_started": True}, sort_keys=True))
        result = asyncio.run(run_web_login(config, state))
        state.finish(result)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OperatorAuthError, OSError, subprocess.CalledProcessError) as exc:
        result = {"ok": False, "error": str(exc)}
        state.finish(result)
        print(json.dumps(result, sort_keys=True))
        return 1
    finally:
        server.shutdown()
        os.umask(old_umask)


def build_parser() -> argparse.ArgumentParser:
    """Build the web auth CLI parser."""
    parser = argparse.ArgumentParser(description="Serve Telegram QR auth over a temporary web page.")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--session-root", default=DEFAULT_SESSION_ROOT)
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument("--venv", default=DEFAULT_VENV)
    parser.add_argument("--context", default=None, dest="kube_context")
    parser.add_argument("--proxy-url", default=None)
    parser.add_argument("--qr-png-path", default=DEFAULT_QR_PNG_PATH)
    parser.add_argument("--web-host", default=DEFAULT_WEB_HOST)
    parser.add_argument("--web-port", default=DEFAULT_WEB_PORT, type=int)
    parser.add_argument("--web-token", default=None)
    parser.add_argument("--public-base-url", default=None)
    parser.add_argument("--timeout", default=DEFAULT_AUTH_WINDOW_SECONDS, type=int)
    parser.add_argument("--qr-refresh", default=DEFAULT_QR_REFRESH_SECONDS, type=int)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-web-kube", help="Run token-gated web QR auth.")
    subparsers.add_parser("child-web", help=argparse.SUPPRESS)
    return parser


def config_from_args(args: argparse.Namespace) -> WebAuthConfig:
    """Create config from command-line args."""
    kube = KubeAuthConfig(
        namespace=args.namespace,
        secret_name=args.secret_name,
        session_root=args.session_root,
        session_name=args.session_name,
        venv_path=args.venv,
        kube_context=args.kube_context,
        proxy_url=args.proxy_url,
        qr_png_path=args.qr_png_path,
    )
    return WebAuthConfig(
        kube=kube,
        web_host=args.web_host,
        web_port=args.web_port,
        web_token=args.web_token or secrets.token_urlsafe(24),
        public_base_url=args.public_base_url,
        auth_window_seconds=args.timeout,
        qr_refresh_seconds=args.qr_refresh,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the web QR auth CLI."""
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    if args.command == "run-web-kube":
        return run_parent(config)
    if args.command == "child-web":
        return run_child(config)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
