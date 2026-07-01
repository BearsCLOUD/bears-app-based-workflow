"""Tests for Kubernetes-backed terminal QR operator auth."""

from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operator_telethon_kube_auth.py"
)
SCRIPT_DIR = str(MODULE_PATH.parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
SPEC = importlib.util.spec_from_file_location("operator_telethon_kube_auth", MODULE_PATH)
assert SPEC and SPEC.loader
operator_telethon_kube_auth = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = operator_telethon_kube_auth
SPEC.loader.exec_module(operator_telethon_kube_auth)


def test_preflight_reports_secret_key_presence(monkeypatch) -> None:
    """Preflight checks key names only."""
    monkeypatch.setattr(operator_telethon_kube_auth.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        operator_telethon_kube_auth,
        "secret_key_names",
        lambda config: {"api-id", "api-hash"},
    )

    result = operator_telethon_kube_auth.kube_preflight(
        operator_telethon_kube_auth.KubeAuthConfig()
    )

    assert result["ok"] is True
    assert result["api_id_key_present"] is True
    assert result["api_hash_key_present"] is True
    assert "12345" not in str(result)


def test_loads_credentials_without_printing_values(monkeypatch) -> None:
    """Credential loader decodes Kubernetes Secret values in process only."""
    values = {
        "api-id": base64.b64encode(b"12345").decode(),
        "api-hash": base64.b64encode(b"abcdef").decode(),
    }

    def fake_read(config, key):  # noqa: ANN001 - test stub.
        return base64.b64decode(values[key]).decode()

    monkeypatch.setattr(operator_telethon_kube_auth, "read_secret_key", fake_read)

    api_id, api_hash = operator_telethon_kube_auth.load_kube_api_credentials(
        operator_telethon_kube_auth.KubeAuthConfig()
    )

    assert api_id == 12345
    assert api_hash == "abcdef"


def test_parent_stops_before_venv_when_kube_preflight_fails(monkeypatch) -> None:
    """Run does not install dependencies when kube preflight fails."""
    monkeypatch.setattr(
        operator_telethon_kube_auth,
        "kube_preflight",
        lambda config: {"ok": False, "error": "kubectl_missing"},
    )

    def fake_run(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("subprocess must not run before preflight passes")

    monkeypatch.setattr(operator_telethon_kube_auth.subprocess, "run", fake_run)

    result = operator_telethon_kube_auth.run_parent(
        operator_telethon_kube_auth.KubeAuthConfig()
    )

    assert result == 1


def test_parent_delegates_to_child_after_preflight(monkeypatch, tmp_path: Path) -> None:
    """Parent installs deps and launches child QR command."""
    calls = []

    class FakeCompleted:
        """Small subprocess.CompletedProcess stand-in."""

        returncode = 0

    def fake_run(cmd, check=False):  # noqa: ANN001
        calls.append({"cmd": cmd, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(
        operator_telethon_kube_auth,
        "kube_preflight",
        lambda config: {"ok": True},
    )
    monkeypatch.setattr(operator_telethon_kube_auth.subprocess, "run", fake_run)

    result = operator_telethon_kube_auth.run_parent(
        operator_telethon_kube_auth.KubeAuthConfig(venv_path=str(tmp_path / "venv"))
    )

    assert result == 0
    assert calls[0]["cmd"][:3] == ["python3", "-m", "venv"]
    assert "Telethon>=1.44,<2" in calls[1]["cmd"]
    assert "Pillow>=10,<12" in calls[1]["cmd"]
    assert "python-socks[asyncio]>=2.4,<3" in calls[1]["cmd"]
    assert calls[2]["cmd"][-1] == "child-qr"
    assert "--qr-png-path" in calls[2]["cmd"]


def test_parent_passes_explicit_proxy_to_child(monkeypatch, tmp_path: Path) -> None:
    """Explicit proxy URL is delegated without printing secret values."""
    calls = []

    class FakeCompleted:
        """Small subprocess.CompletedProcess stand-in."""

        returncode = 0

    def fake_run(cmd, check=False):  # noqa: ANN001
        calls.append({"cmd": cmd, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(
        operator_telethon_kube_auth,
        "kube_preflight",
        lambda config: {"ok": True},
    )
    monkeypatch.setattr(operator_telethon_kube_auth.subprocess, "run", fake_run)

    result = operator_telethon_kube_auth.run_parent(
        operator_telethon_kube_auth.KubeAuthConfig(
            venv_path=str(tmp_path / "venv"),
            proxy_url="socks5://127.0.0.1:1080",
        )
    )

    assert result == 0
    assert "--proxy-url" in calls[2]["cmd"]
    assert "socks5://127.0.0.1:1080" in calls[2]["cmd"]


def test_effective_proxy_uses_tg_proxy_env_first(monkeypatch) -> None:
    """TG proxy env overrides generic proxy env."""
    monkeypatch.setenv("TG_PROXY_URL", "socks5://127.0.0.1:1080")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:8888")

    result = operator_telethon_kube_auth.effective_proxy_url(
        operator_telethon_kube_auth.KubeAuthConfig()
    )

    assert result == "socks5://127.0.0.1:1080"
