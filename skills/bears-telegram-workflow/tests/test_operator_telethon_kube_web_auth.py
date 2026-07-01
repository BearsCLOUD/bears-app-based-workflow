"""Tests for token-gated web QR operator auth."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.request import urlopen

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operator_telethon_kube_web_auth.py"
)
SCRIPT_DIR = str(MODULE_PATH.parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
SPEC = importlib.util.spec_from_file_location("operator_telethon_kube_web_auth", MODULE_PATH)
assert SPEC and SPEC.loader
operator_telethon_kube_web_auth = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = operator_telethon_kube_web_auth
SPEC.loader.exec_module(operator_telethon_kube_web_auth)


def test_web_url_contains_token_and_no_secret() -> None:
    """The web URL uses a random token path only."""
    config = operator_telethon_kube_web_auth.WebAuthConfig(
        kube=operator_telethon_kube_web_auth.KubeAuthConfig(),
        web_host="127.0.0.1",
        web_port=8765,
        web_token="token-123",
    )

    assert config.web_url == "http://127.0.0.1:8765/token-123/"
    assert "tg://" not in config.web_url


def test_token_gated_server_serves_status_and_qr() -> None:
    """HTTP server only serves the token-gated paths."""
    state = operator_telethon_kube_web_auth.WebQrState()
    state.update_qr(b"png-bytes")
    config = operator_telethon_kube_web_auth.WebAuthConfig(
        kube=operator_telethon_kube_web_auth.KubeAuthConfig(),
        web_host="127.0.0.1",
        web_port=0,
        web_token="token-123",
    )
    server = operator_telethon_kube_web_auth.start_server(config, state)
    try:
        port = server.server_address[1]
        status = urlopen(f"http://127.0.0.1:{port}/token-123/status.json", timeout=2)
        payload = json.loads(status.read().decode("utf-8"))
        assert payload["qr_ready"] is True
        qr = urlopen(f"http://127.0.0.1:{port}/token-123/qr.png", timeout=2)
        assert qr.read() == b"png-bytes"
        try:
            urlopen(f"http://127.0.0.1:{port}/wrong/status.json", timeout=2)
        except Exception as exc:  # noqa: BLE001 - urllib raises HTTPError here.
            assert "404" in str(exc)
        else:  # pragma: no cover - defensive branch.
            raise AssertionError("wrong token must not be served")
    finally:
        server.shutdown()


def test_parent_passes_refresh_and_timeout_to_child(monkeypatch, tmp_path: Path) -> None:
    """Parent command delegates web auth window controls to the child."""
    calls = []

    class FakeCompleted:
        """Small subprocess.CompletedProcess stand-in."""

        returncode = 0

    def fake_run(cmd, check=False):  # noqa: ANN001
        calls.append({"cmd": cmd, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(
        operator_telethon_kube_web_auth,
        "kube_preflight",
        lambda config: {"ok": True},
    )
    monkeypatch.setattr(operator_telethon_kube_web_auth.subprocess, "run", fake_run)
    config = operator_telethon_kube_web_auth.WebAuthConfig(
        kube=operator_telethon_kube_web_auth.KubeAuthConfig(
            venv_path=str(tmp_path / "venv"),
        ),
        web_host="127.0.0.1",
        web_port=8765,
        web_token="token-123",
        auth_window_seconds=900,
        qr_refresh_seconds=60,
    )

    result = operator_telethon_kube_web_auth.run_parent(config)

    assert result == 0
    child_cmd = calls[2]["cmd"]
    assert "--web-token" in child_cmd
    assert "token-123" in child_cmd
    assert "--timeout" in child_cmd
    assert "900" in child_cmd
    assert "--qr-refresh" in child_cmd
    assert "60" in child_cmd
    assert "child-web" == child_cmd[-1]
