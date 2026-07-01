"""Tests for the operator TDLib auth interface."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operator_tglib_auth.py"
)
SPEC = importlib.util.spec_from_file_location("operator_tglib_auth", MODULE_PATH)
assert SPEC and SPEC.loader
operator_tglib_auth = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = operator_tglib_auth
SPEC.loader.exec_module(operator_tglib_auth)


def test_secret_presence_accepts_infisical_names() -> None:
    """Infisical hyphenated keys are accepted without exposing values."""
    result = operator_tglib_auth.secret_presence_from_json(
        '{"api-id":"12345","api-hash":"abcdef"}'
    )

    assert result == {"api_id": True, "api_hash": True}


def test_secret_presence_accepts_env_aliases() -> None:
    """Uppercase runtime aliases are accepted for local wrappers."""
    result = operator_tglib_auth.secret_presence_from_json(
        '{"TELEGRAM_API_ID":"12345","TELEGRAM_API_HASH":"abcdef"}'
    )

    assert result == {"api_id": True, "api_hash": True}


def test_rendered_shell_has_visible_stages_and_no_sample_secrets() -> None:
    """Rendered operator script is staged and does not include secret values."""
    config = operator_tglib_auth.OperatorAuthConfig()
    shell = operator_tglib_auth.build_operator_shell(config)

    assert "[1/5] prepare local python env" in shell
    assert "[5/5] helper finished" in shell
    assert "/srv/bears/.tmp/tglib-telegram-auth" not in shell
    assert "api-id" in shell
    assert "exec 3< <(infisical export" in shell
    assert "3<&3" in shell
    assert "abcdef" not in shell
    assert "12345" not in shell


def test_invalid_session_name_is_rejected() -> None:
    """Session names cannot escape the private session directory."""
    config = operator_tglib_auth.OperatorAuthConfig(session_name="../bad")

    try:
        operator_tglib_auth.build_operator_shell(config)
    except operator_tglib_auth.OperatorAuthError as exc:
        assert "session name" in str(exc)
    else:  # pragma: no cover - clearer failure than pytest.raises import need.
        raise AssertionError("invalid session name was accepted")


def test_doctor_reports_tools_without_secret_access(tmp_path: Path) -> None:
    """Doctor checks local tools only and never needs Infisical values."""
    config = operator_tglib_auth.OperatorAuthConfig(venv_path=str(tmp_path / "venv"))

    result = operator_tglib_auth.doctor(config).to_dict()

    assert "python3_cli" in result
    assert result["session_name_valid"] is True


def test_run_uses_bash_without_printing_generated_body(monkeypatch) -> None:
    """Run delegates to bash so operators use one short command."""
    calls = []

    class FakeCompleted:
        """Small subprocess.CompletedProcess stand-in."""

        returncode = 17

    def fake_run(cmd, check=False):  # noqa: ANN001 - subprocess stub.
        calls.append({"cmd": cmd, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(operator_tglib_auth.subprocess, "run", fake_run)

    result = operator_tglib_auth.run_operator_auth(
        operator_tglib_auth.OperatorAuthConfig()
    )

    assert result == 17
    assert calls[0]["cmd"][:2] == ["bash", "-lc"]
    assert "infisical export" in calls[0]["cmd"][2]
    assert calls[0]["check"] is False
