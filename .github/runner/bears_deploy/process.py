"""Bounded subprocess, Git, and GitHub credential operations for the fixed gateway."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import subprocess
from typing import Any

from .constants import (
    CODEX,
    ENV,
    GIT,
    GITHUB_TOKEN_MAX_BYTES,
    GITHUB_TOKEN_RE,
    MAIN_REF,
    MIRROR,
    REPOSITORY,
)
from .models import DeployError
from .telemetry import command_label, normalized_diagnostic


def run(
    argv: list[str],
    *,
    ok: tuple[int, ...] = (0,),
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if not argv or argv[0] not in {GIT, CODEX}:
        raise DeployError("only the fixed git and codex binaries may be invoked")
    try:
        result = subprocess.run(
            argv,
            env=ENV if env is None else env,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise DeployError(
            f"{command_label(argv)} invocation failed: {normalized_diagnostic(str(exc))}"
        ) from exc
    if result.returncode not in ok:
        detail = normalized_diagnostic(result.stderr or result.stdout)
        raise DeployError(
            f"{command_label(argv)} command failed with exit {result.returncode}: {detail}"
        )
    return result


def run_json(
    argv: list[str], *, env: dict[str, str] | None = None
) -> dict[str, Any]:
    try:
        value = json.loads(run(argv, env=env).stdout)
    except json.JSONDecodeError as exc:
        raise DeployError(f"invalid JSON from {command_label(argv)}") from exc
    if not isinstance(value, dict):
        raise DeployError(f"unexpected JSON shape from {command_label(argv)}")
    return value


def git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    return run(
        [
            GIT,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.file.allow=never",
            "-C",
            str(repo),
            *args,
        ],
        ok=ok,
    )


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def exact_remote(repo: Path) -> None:
    urls = git_text(repo, "remote", "get-url", "--all", "origin").splitlines()
    if urls != [REPOSITORY]:
        raise DeployError(f"repository origin is not fixed to {REPOSITORY}")


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    result = git(repo, "merge-base", "--is-ancestor", older, newer, ok=(0, 1))
    return result.returncode == 0


def read_github_token(stream: io.BufferedIOBase) -> str:
    """Read one bounded ephemeral GitHub job token from the gateway pipe."""
    raw = stream.read(GITHUB_TOKEN_MAX_BYTES + 1)
    if (
        len(raw) > GITHUB_TOKEN_MAX_BYTES
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
    ):
        raise DeployError("missing or invalid GitHub job credential")
    token = raw[:-1]
    if (
        not 20 <= len(token) <= GITHUB_TOKEN_MAX_BYTES
        or GITHUB_TOKEN_RE.fullmatch(token) is None
    ):
        raise DeployError("missing or invalid GitHub job credential")
    return token.decode("ascii")


def github_authenticated_env(github_token: str) -> dict[str, str]:
    """Build URL-scoped Git auth without exposing the token through argv."""
    authorization = base64.b64encode(
        f"x-access-token:{github_token}".encode("ascii")
    ).decode("ascii")
    return {
        **ENV,
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "http.https://github.com/.extraHeader",
        "GIT_CONFIG_VALUE_1": f"Authorization: Basic {authorization}",
    }


def fetch_main(repo: Path, github_token: str) -> None:
    """Fetch fixed GitHub main with a token kept out of argv and diagnostics."""
    authenticated_env = github_authenticated_env(github_token)
    run(
        [
            GIT,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.file.allow=never",
            "-C",
            str(repo),
            "fetch",
            "--force",
            "--no-tags",
            "origin",
            "+refs/heads/main:" + MAIN_REF,
        ],
        env=authenticated_env,
    )


def prepare_mirror(requested: str, github_token: str) -> str:
    if MIRROR.is_symlink():
        raise DeployError("mirror path must not be a symlink")
    if not MIRROR.exists():
        run([GIT, "init", "--bare", str(MIRROR)])
        git(MIRROR, "remote", "add", "origin", REPOSITORY)
    exact_remote(MIRROR)
    fetch_main(MIRROR, github_token)
    main_sha = git_text(MIRROR, "rev-parse", MAIN_REF)
    if not is_ancestor(MIRROR, requested, main_sha):
        raise DeployError("requested SHA is not reachable from the fixed repository main branch")
    return main_sha
