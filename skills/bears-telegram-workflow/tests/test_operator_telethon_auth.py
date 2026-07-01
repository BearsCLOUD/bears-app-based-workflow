"""Tests for the terminal QR Telethon operator interface."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operator_telethon_auth.py"
)
SPEC = importlib.util.spec_from_file_location("operator_telethon_auth", MODULE_PATH)
assert SPEC and SPEC.loader
operator_telethon_auth = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = operator_telethon_auth
SPEC.loader.exec_module(operator_telethon_auth)


def test_secret_presence_accepts_infisical_names() -> None:
    """Infisical hyphenated keys are accepted without exposing values."""
    result = operator_telethon_auth.secret_presence_from_json(
        '{"api-id":"12345","api-hash":"abcdef"}'
    )

    assert result == {"api_id": True, "api_hash": True}


def test_invalid_session_name_is_rejected(tmp_path: Path) -> None:
    """Session names cannot escape the private session directory."""
    config = operator_telethon_auth.OperatorAuthConfig(
        session_root=str(tmp_path),
        session_name="../bad",
    )

    try:
        operator_telethon_auth.prepare_session_stem(config)
    except operator_telethon_auth.OperatorAuthError as exc:
        assert "session name" in str(exc)
    else:  # pragma: no cover - clearer failure than pytest.raises import need.
        raise AssertionError("invalid session name was accepted")


def test_doctor_reports_tools_without_secret_access(tmp_path: Path) -> None:
    """Doctor checks local tools only and never needs Infisical values."""
    config = operator_telethon_auth.OperatorAuthConfig(venv_path=str(tmp_path / "venv"))

    result = operator_telethon_auth.doctor(config).to_dict()

    assert "python3_cli" in result
    assert result["session_name_valid"] is True


def test_parent_uses_child_process_without_secret_values(monkeypatch, tmp_path: Path) -> None:
    """Parent installs dependencies and delegates QR auth to the child command."""
    calls = []

    class FakeCompleted:
        """Small subprocess.CompletedProcess stand-in."""

        returncode = 0

    def fake_run(cmd, check=False, env=None):  # noqa: ANN001 - subprocess stub.
        calls.append({"cmd": cmd, "check": check, "env": env})
        return FakeCompleted()

    monkeypatch.setattr(operator_telethon_auth.subprocess, "run", fake_run)
    monkeypatch.setattr(
        operator_telethon_auth,
        "preflight",
        lambda config: {"ok": True},
    )
    config = operator_telethon_auth.OperatorAuthConfig(
        venv_path=str(tmp_path / "venv"),
        session_root=str(tmp_path / "sessions"),
    )

    result = operator_telethon_auth.run_parent(config)

    assert result == 0
    assert calls[0]["cmd"][:3] == ["python3", "-m", "venv"]
    assert "Telethon>=1.44,<2" in calls[1]["cmd"]
    assert calls[2]["cmd"][-1] == "child-qr"
    assert "--env-file" in calls[2]["cmd"]
    assert "/srv/bears/tg.env" in calls[2]["cmd"]
    assert calls[2]["env"]["BEARS_TELETHON_AUTH_CHILD"] == "1"


def test_env_file_accepts_login_but_ignores_password(tmp_path: Path, capsys) -> None:
    """Local env file may hold login but never uses Telegram 2FA password."""
    env_file = tmp_path / "tg.env"
    env_file.write_text(
        "TG_LOGIN=+10000000000\nTG_PASS=secret\n",
        encoding="utf-8",
    )

    result = operator_telethon_auth.parse_env_file(env_file)

    assert result == {"TG_LOGIN": "+10000000000"}
    assert "secret" not in capsys.readouterr().out


def test_infisical_project_id_from_tg_env_is_used(monkeypatch, tmp_path: Path) -> None:
    """Infisical project id may come from tg.env without printing secrets."""
    env_file = tmp_path / "tg.env"
    env_file.write_text("INFISICAL_PROJECT_ID=project-local\n", encoding="utf-8")
    calls = []

    class FakeCompleted:
        """Small subprocess.CompletedProcess stand-in."""

        stdout = '{"api-id":"12345","api-hash":"abcdef"}'
        stderr = ""

    def fake_run(cmd, check=False, text=False, capture_output=False):  # noqa: ANN001
        calls.append({
            "cmd": cmd,
            "check": check,
            "text": text,
            "capture_output": capture_output,
        })
        return FakeCompleted()

    monkeypatch.setattr(operator_telethon_auth.subprocess, "run", fake_run)

    api_id, api_hash = operator_telethon_auth.load_api_credentials(
        operator_telethon_auth.OperatorAuthConfig(env_file=str(env_file))
    )

    assert api_id == 12345
    assert api_hash == "abcdef"
    assert "--projectId=project-local" in calls[0]["cmd"]
    assert calls[0]["capture_output"] is True


def test_infisical_error_reports_stderr_without_command(monkeypatch) -> None:
    """Infisical failures return actionable stderr instead of raw command text."""

    def fake_run(cmd, check=False, text=False, capture_output=False):  # noqa: ANN001
        raise operator_telethon_auth.subprocess.CalledProcessError(
            1,
            cmd,
            stderr="missing project id\nsecond line\nthird line",
        )

    monkeypatch.setattr(operator_telethon_auth.subprocess, "run", fake_run)

    try:
        operator_telethon_auth.load_api_credentials(
            operator_telethon_auth.OperatorAuthConfig()
        )
    except operator_telethon_auth.OperatorAuthError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError("Infisical failure was accepted")

    assert "missing project id" in message
    assert "third line" not in message
    assert "api-hash" not in message


def test_preflight_reports_missing_project_id_without_secret_values(monkeypatch, tmp_path: Path) -> None:
    """Preflight reports Infisical readiness without exposing secret values."""
    env_file = tmp_path / "tg.env"
    env_file.write_text("TG_LOGIN=+10000000000\nTG_PASS=secret\n", encoding="utf-8")

    def fake_load_api_credentials(config):  # noqa: ANN001
        raise operator_telethon_auth.OperatorAuthError("missing project id")

    monkeypatch.setattr(
        operator_telethon_auth,
        "load_api_credentials",
        fake_load_api_credentials,
    )

    result = operator_telethon_auth.preflight(
        operator_telethon_auth.OperatorAuthConfig(env_file=str(env_file))
    )

    assert result["ok"] is False
    assert result["env_file_exists"] is True
    assert result["infisical_project_id_present"] is False
    assert result["tg_pass_present"] is True
    assert "secret" not in str(result)


def test_run_parent_stops_before_venv_when_preflight_fails(monkeypatch) -> None:
    """Run does not install dependencies when Infisical preflight fails."""

    def fake_preflight(config):  # noqa: ANN001
        return {"ok": False, "error": "missing project id"}

    def fake_run(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("subprocess must not run before preflight passes")

    monkeypatch.setattr(operator_telethon_auth, "preflight", fake_preflight)
    monkeypatch.setattr(operator_telethon_auth.subprocess, "run", fake_run)

    result = operator_telethon_auth.run_parent(
        operator_telethon_auth.OperatorAuthConfig()
    )

    assert result == 1
