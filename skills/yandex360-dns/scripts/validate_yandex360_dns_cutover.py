#!/usr/bin/env python3
"""Validate the Yandex 360 DNS Infisical cutover path without reading secret values."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
DNS_SCRIPT = SKILL_ROOT / "scripts" / "yandex360_dns.py"
SETUP_SCRIPT = SKILL_ROOT / "scripts" / "infisical_yandex360_setup.py"
CACHE_DNS_SCRIPT = Path(
    "/home/ai1/.codex/plugins/cache/bears-local-marketplace/bears/0.1.0/"
    "skills/yandex360-dns/scripts/yandex360_dns.py"
)
FORBIDDEN_ENV = "/srv/bears/.env"
SECRET_MARKER = "validator-secret-marker-not-real"


def run_cmd(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a local command and capture output for redacted validation."""
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def json_loads(text: str) -> Any:
    """Parse a helper JSON packet and keep parse errors value-free."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"expected JSON output: {exc}") from exc


def env_check() -> dict[str, Any]:
    """Run the DNS helper presence check without exposing values."""
    result = run_cmd([sys.executable, str(DNS_SCRIPT), "env-check"])
    check: dict[str, Any] = {
        "name": "env_check_presence_only",
        "status": "ok" if result.returncode == 0 else "fail",
    }
    if result.returncode != 0:
        check["error"] = "env-check command failed without printing captured stderr"
        return check
    payload = json_loads(result.stdout)
    rows = payload.get("keys", [])
    present = [row["key"] for row in rows if row.get("present")]
    missing = [row["key"] for row in rows if not row.get("present")]
    check.update(
        {
            "env": payload.get("env"),
            "present_keys": present,
            "missing_keys": missing,
            "secret_values_printed": False,
        }
    )
    return check


def helper_dry_run() -> dict[str, Any]:
    """Run setup dry-run and report only key names and target path."""
    result = run_cmd([sys.executable, str(SETUP_SCRIPT), "--dry-run"])
    check: dict[str, Any] = {
        "name": "helper_dry_run",
        "status": "ok" if result.returncode == 0 else "fail",
    }
    if result.returncode != 0:
        check["error"] = "setup helper dry-run failed with stable category only"
        return check
    payload = json_loads(result.stdout)
    check.update(
        {
            "environment": payload.get("environment"),
            "secret_path": payload.get("secret_path"),
            "would_update_keys": payload.get("would_update_keys", []),
            "secret_values_printed": payload.get("secret_values_printed") is not False,
            "write_mode": payload.get("write_mode"),
        }
    )
    if check["secret_values_printed"]:
        check["status"] = "fail"
    return check


def root_env_refusal(script: Path, name: str) -> dict[str, Any]:
    """Verify a helper refuses the legacy root env path without echoing a marker."""
    if not script.is_file():
        return {"name": name, "status": "skip", "reason": "script_absent"}
    env = {"PYTHONDONTWRITEBYTECODE": "1", "YANDEX360_DNS_OAUTH_TOKEN": SECRET_MARKER}
    result = run_cmd([sys.executable, str(script), "--env", FORBIDDEN_ENV, "env-check"], env=env)
    combined = result.stdout + result.stderr
    ok = (
        result.returncode != 0
        and ("Local env file loading is disabled" in combined or "Refusing" in combined)
        and SECRET_MARKER not in combined
        and FORBIDDEN_ENV not in combined
    )
    check: dict[str, Any] = {
        "name": name,
        "status": "ok" if ok else "fail",
        "secret_values_printed": False,
    }
    if not ok:
        check["error"] = "script did not safely refuse the forbidden root env path"
    return check


def infisical_presence() -> list[dict[str, Any]]:
    """Check Infisical CLI/session readiness without printing CLI output."""
    checks: list[dict[str, Any]] = []
    infisical_env_keys = [
        "INFISICAL_PROJECT_ID",
        "INFISICAL_API_URL",
        "INFISICAL_HOST_URL",
    ]
    cli = shutil.which("infisical")
    checks.append({"name": "infisical_cli", "status": "present" if cli else "absent"})
    checks.append(
        {
            "name": "infisical_env_presence",
            "status": "ok",
            "present_keys": [key for key in infisical_env_keys if os.environ.get(key)],
            "missing_keys": [key for key in ["INFISICAL_PROJECT_ID"] if not os.environ.get(key)],
        }
    )
    if not cli:
        checks.append(
            {
                "name": "infisical_whoami",
                "status": "operator_required",
                "reason": "cli_absent",
            }
        )
        return checks
    result = run_cmd([cli, "whoami"])
    checks.append(
        {
            "name": "infisical_whoami",
            "status": "ok" if result.returncode == 0 else "operator_required",
            "secret_values_printed": False,
        }
    )
    return checks


def main() -> None:
    """Print the cutover validation packet and fail only on guardrail failures."""
    checks = [
        env_check(),
        helper_dry_run(),
        root_env_refusal(DNS_SCRIPT, "plugin_root_env_refusal"),
        root_env_refusal(CACHE_DNS_SCRIPT, "cache_root_env_refusal"),
        *infisical_presence(),
    ]
    failed = [check for check in checks if check.get("status") == "fail"]
    operator_required = [
        check["name"]
        for check in checks
        if check.get("status") in {"operator_required", "absent"}
    ]
    print(
        json.dumps(
            {
                "ok": not failed,
                "failed_checks": [check["name"] for check in failed],
                "operator_required": operator_required,
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
