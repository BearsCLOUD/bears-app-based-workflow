#!/usr/bin/env python3
"""Locate and run the platform Dagger ObjectiveRuntimeProof entrypoint."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PLUGIN_ROOT.parents[1]
PLATFORM_ROOT = WORKSPACE_ROOT / "dev/platform"
APPS_ROOT = WORKSPACE_ROOT / "dev/app"
CATALOG = PLUGIN_ROOT / "assets/catalog/objective-runtime-proof.v1.json"
TIMEOUT_SECONDS = 900


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def packet(**items: Any) -> dict[str, Any]:
    base = {"schema": "bears-objective-runtime-proof-wrapper.v1"}
    base.update(items)
    return base


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def dagger_path() -> str | None:
    return shutil.which("dagger")


def locate(app: str) -> dict[str, Any]:
    catalog = load_catalog()
    app_name = safe_app(app)
    return packet(
        status="located",
        app=app_name,
        platform_dagger_module=catalog["platform_dagger_module"],
        platform_dagger_manifest=catalog["platform_dagger_manifest"],
        source_input=str(APPS_ROOT / app_name),
        artifact_root=f"{catalog['artifact_root']}/{app_name}/<run-id>.json",
        final_live_owner=catalog["final_live_owner"],
        required_entrypoint=f"dagger call objective-runtime-proof --source {APPS_ROOT} --app {app_name} --scenario <scenario>",
        forbidden_pass_evidence=catalog["forbidden_pass_evidence"],
    )


def run(app: str, scenario: str, source: str) -> dict[str, Any]:
    app_name = safe_app(app)
    binary = dagger_path()
    if not binary:
        return packet(status="tool_missing", app=app_name, missing_tool="dagger", next_action="Install Dagger CLI in the runtime dependency layer before requesting proof.")
    command = [
        binary,
        "call",
        "objective-runtime-proof",
        "--source",
        source,
        "--app",
        app_name,
        "--scenario",
        scenario,
    ]
    proc = subprocess.run(
        command,
        cwd=PLATFORM_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    return packet(
        status="pass" if proc.returncode == 0 else "failed",
        app=app_name,
        command=" ".join(command),
        cwd=str(PLATFORM_ROOT),
        exit_code=proc.returncode,
        stdout_excerpt=proc.stdout[-4000:],
        stderr_excerpt=proc.stderr[-2000:],
    )


def migrate(target: str) -> dict[str, Any]:
    clean = target.strip() or "<unspecified>"
    return packet(
        status="migration_required",
        target=clean,
        required_action="Replace test/contract/validation-layer acceptance with platform Dagger ObjectiveRuntimeProof or remove the obsolete reference.",
        replacement="python3 scripts/objective_runtime_proof.py run --app <app> --scenario <scenario> --json",
        forbidden_closeout="Do not close with tests, contracts, validators, schemas, lint, or static checks as PASS evidence.",
    )


def safe_app(value: str) -> str:
    clean = value.strip()
    if not clean or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in clean):
        raise SystemExit("app must be a safe app directory name")
    return clean


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    locate_p = sub.add_parser("locate")
    locate_p.add_argument("--app", required=True)
    locate_p.add_argument("--json", action="store_true")
    run_p = sub.add_parser("run")
    run_p.add_argument("--app", required=True)
    run_p.add_argument("--scenario", default="default")
    run_p.add_argument("--source", default=str(APPS_ROOT))
    run_p.add_argument("--json", action="store_true")
    migrate_p = sub.add_parser("migrate")
    migrate_p.add_argument("target")
    migrate_p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "locate":
        result = locate(args.app)
    elif args.command == "run":
        result = run(args.app, args.scenario, args.source)
    else:
        result = migrate(args.target)
    if getattr(args, "json", False):
        print_json(result)
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0 if result.get("status") in {"located", "pass", "tool_missing", "migration_required"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
