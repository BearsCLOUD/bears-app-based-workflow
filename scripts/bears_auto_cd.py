#!/usr/bin/env python3
"""Validate and run Bears machine-readable Git/CD contracts.

This program is intended for GitHub Actions. It is not a Codex agent runner:
it owns the fixed Kubernetes CD mechanics, reads app desired state from the
Bears infra repo, and rejects branch policy or CD step descriptions outside
the executable.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from contextlib import nullcontext
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GIT_CONTRACT = PLUGIN_ROOT / "assets" / "catalog" / "git-deploy-contract.v1.json"
DEFAULT_CD_CONTRACT = PLUGIN_ROOT / "assets" / "catalog" / "cd-kube-deploy-contract.v1.json"
DEFAULT_APP_DESCRIPTOR_DIR = Path("local_cd") / "applications"
FORBIDDEN_CD_KEYS = {
    "development_branch",
    "deployment_branch",
    "merge_request_required",
    "pull_request",
    "operator_approval",
    "approval_gate",
    "manual_gate",
}
DIGEST_RE = re.compile(r"@sha256:([0-9a-f]{64})(?:\b|$)")
APPS_MONOREPO_REPOSITORY = "BearsCLOUD/apps"
APPS_MONOREPO_ARCHIVE_SOURCE_REPOS = {
    "BearsCLOUD/codex-telegram-mcp": "codex-telegram",
    "BearsCLOUD/tgsearch": "tgsearch",
}
APPS_MONOREPO_ARCHIVE_SCAN_SURFACES = {
    "cd_contracts",
    "workflows",
    "kubernetes_runbooks",
    "manifests_readme",
    "secret_custody_docs",
}
FORBIDDEN_DESCRIPTOR_KEYS = {
    "ordered_steps",
    "local_image_build",
    "build_local_image",
    "load_local_image_to_k3d",
    "load_to_k3d_nodes",
    "kubectl_apply",
    "kubectl",
    "context_path",
    "dockerfile",
    "clear_proxy_build_args",
    "toolchain",
    "operator_approval",
    "approval_gate",
    "manual_gate",
}
EXECUTOR_LOCAL_BUILD_DEFAULTS: dict[str, dict[str, Any]] = {
    "codex-telegram-mcp": {
        "context_path": ".codex-telegram-source",
        "dockerfile": "Dockerfile",
        "source_subpath": "codex-telegram",
        "clear_proxy_build_args": False,
    },
    "tgsearch-live-gate": {
        "context_path": ".tgsearch-source",
        "dockerfile": "Dockerfile",
        "source_subpath": "tgsearch",
        "clear_proxy_build_args": False,
    },
    "callsaver-starter": {
        "context_path": ".callsaver-source",
        "dockerfile": "Dockerfile",
        "source_subpath": "callsaver",
        "clear_proxy_build_args": True,
    },
    "codex-web": {
        "context_path": "images/codex-web",
        "dockerfile": "Dockerfile",
        "clear_proxy_build_args": False,
    },
    "egress-gateway": {
        "context_path": "images/egress-gateway",
        "dockerfile": "Dockerfile",
        "clear_proxy_build_args": False,
    },
}
SOURCE_SYNC_EXCLUDES = {
    ".git",
    ".env",
    ".sessions",
    "runtime",
    "reports",
    "__pycache__",
    ".pytest_cache",
}


class ContractError(ValueError):
    """Raised when a Git/CD contract is unsafe or inconsistent."""


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from *path*."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"missing JSON contract: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"contract root must be an object: {path}")
    return value


def walk_keys(value: Any, prefix: str = "") -> list[str]:
    """Return dotted key paths for every object key in a JSON value."""
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(walk_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(walk_keys(child, f"{prefix}[{index}]"))
    return paths


def validate_git_contract(contract: dict[str, Any]) -> list[str]:
    """Validate the Git branch-to-target contract."""
    errors: list[str] = []
    if contract.get("schema") != "bears.git-deploy-contract.v1":
        errors.append("git contract schema mismatch")
    repos = contract.get("repositories")
    if not isinstance(repos, list) or not repos:
        errors.append("git contract repositories must be a non-empty list")
        return errors
    for index, repo in enumerate(repos):
        if not isinstance(repo, dict):
            errors.append(f"repositories[{index}] must be an object")
            continue
        if not repo.get("repository"):
            errors.append(f"repositories[{index}].repository missing")
        if repo.get("development_branch") == repo.get("deployment_branch"):
            errors.append(f"repositories[{index}] dev and deployment branches must differ")
        if repo.get("merge_request_required") is not True:
            errors.append(f"repositories[{index}].merge_request_required must be true")
        targets = repo.get("deployment_targets")
        if not isinstance(targets, list) or not targets:
            errors.append(f"repositories[{index}].deployment_targets must be non-empty")
            continue
        for target_index, target in enumerate(targets):
            if not isinstance(target, dict):
                errors.append(f"repositories[{index}].deployment_targets[{target_index}] must be object")
                continue
            if target.get("branch") != repo.get("deployment_branch"):
                errors.append(f"deployment target branch must equal deployment_branch for {repo.get('repository')}")
            if target.get("automatic_cd") is not True:
                errors.append(f"deployment target automatic_cd must be true for {repo.get('repository')}")
            for required in ("target_id", "server_alias", "environment"):
                if not target.get(required):
                    errors.append(f"deployment target missing {required}")
    return errors


def resolve_target(git_contract: dict[str, Any], repository: str, branch: str) -> dict[str, Any]:
    """Resolve a repository branch to its automatic CD target."""
    for repo in git_contract.get("repositories", []):
        if not isinstance(repo, dict) or repo.get("repository") != repository:
            continue
        if branch != repo.get("deployment_branch"):
            raise ContractError(f"branch {branch!r} is not deployment branch for {repository}")
        for target in repo.get("deployment_targets", []):
            if isinstance(target, dict) and target.get("branch") == branch and target.get("automatic_cd") is True:
                return target
    raise ContractError(f"no automatic CD target for {repository}@{branch}")



def validate_cd_root_contract(contract: dict[str, Any]) -> list[str]:
    """Validate global CD authority fields before selecting an app descriptor."""
    errors: list[str] = []
    if contract.get("schema") != "bears.cd-kube-deploy-contract.v1":
        errors.append("cd contract schema mismatch")
    for path in walk_keys(contract):
        key = path.rsplit(".", 1)[-1]
        if key in FORBIDDEN_CD_KEYS:
            errors.append(f"cd contract contains forbidden Git/manual gate field: {path}")
        if key in FORBIDDEN_DESCRIPTOR_KEYS:
            errors.append(f"cd root contract contains executor-owned field: {path}")
    if contract.get("repository") != "BearsCLOUD/bears-infra":
        errors.append("cd contract repository must be BearsCLOUD/bears-infra")
    if contract.get("target_id") != "fyuriserv-prod":
        errors.append("cd contract target_id must be fyuriserv-prod")
    if not contract.get("application_descriptor_directory"):
        errors.append("cd contract application_descriptor_directory missing")
    return errors

def validate_cd_contract(contract: dict[str, Any], git_contract: dict[str, Any]) -> list[str]:
    """Validate the selected CD contract and reject policy/mechanics drift."""
    errors: list[str] = []
    if contract.get("schema") != "bears.cd-kube-deploy-contract.v1":
        errors.append("cd contract schema mismatch")
    key_paths = walk_keys(contract)
    for path in key_paths:
        key = path.rsplit(".", 1)[-1]
        if key in FORBIDDEN_CD_KEYS:
            errors.append(f"cd contract contains forbidden Git/manual gate field: {path}")
        if key in FORBIDDEN_DESCRIPTOR_KEYS:
            errors.append(f"cd application descriptor contains executor-owned field: {path}")
    if contract.get("source", {}).get("branch_source") != "git_contract":
        errors.append("cd contract branch_source must be git_contract")
    manifest_path = contract.get("source", {}).get("manifest_path")
    if not isinstance(manifest_path, str) or not manifest_path:
        errors.append("cd contract source.manifest_path missing")
    if contract.get("target_id") != "fyuriserv-prod":
        errors.append("cd contract target_id must be fyuriserv-prod")
    try:
        target = resolve_target(git_contract, str(contract.get("repository")), "main")
    except ContractError as exc:
        errors.append(str(exc))
    else:
        if contract.get("target_id") != target.get("target_id"):
            errors.append("cd contract target_id does not match Git contract target")
        kube = contract.get("kubernetes", {})
        if kube.get("server_alias") != target.get("server_alias") or kube.get("environment") != target.get("environment"):
            errors.append("cd contract Kubernetes target does not match Git contract")
    errors.extend(validate_apps_monorepo_archive_gate(contract))
    return errors


def validate_apps_monorepo_archive_gate(contract: dict[str, Any]) -> list[str]:
    """Validate apps-monorepo source and archive-readiness metadata."""
    errors: list[str] = []
    gate = contract.get("apps_monorepo_archive_gate")
    if not isinstance(gate, dict):
        errors.append("apps_monorepo_archive_gate missing")
        return errors
    if gate.get("canonical_repository") != APPS_MONOREPO_REPOSITORY:
        errors.append("apps_monorepo_archive_gate.canonical_repository must be BearsCLOUD/apps")
    if gate.get("archive_allowed_default") is not False:
        errors.append("apps_monorepo_archive_gate.archive_allowed_default must be false")
    required_before_archive = gate.get("required_before_archive")
    required_tokens = ("umbrella issue", "source migration issue", "canonical", "Project", "infra/local_cd", "platform boundary")
    if not isinstance(required_before_archive, list) or not all(
        any(token in str(item) for item in required_before_archive) for token in required_tokens
    ):
        errors.append(
            "apps_monorepo_archive_gate.required_before_archive must require issue membership in the "
            "canonical Apps planning Project, infra/local_cd, and platform-boundary proof"
        )
    planning_project = gate.get("canonical_planning_project")
    required_fields = {
        "source_repo/app_module",
        "migration_stage",
        "infra_local_cd_status",
        "platform_boundary_status",
        "archive_readiness",
        "owner_role",
        "blocker_status",
    }
    if not isinstance(planning_project, dict):
        errors.append("apps_monorepo_archive_gate.canonical_planning_project missing")
    else:
        if planning_project.get("owner_repository") != APPS_MONOREPO_REPOSITORY:
            errors.append("apps_monorepo_archive_gate.canonical_planning_project.owner_repository must be BearsCLOUD/apps")
        if planning_project.get("name") != "Apps Migration & Planning":
            errors.append("apps_monorepo_archive_gate.canonical_planning_project.name must be Apps Migration & Planning")
        fields = {item for item in planning_project.get("required_issue_fields", []) if isinstance(item, str)}
        missing_fields = sorted(required_fields - fields)
        if missing_fields:
            errors.append(
                "apps_monorepo_archive_gate.canonical_planning_project.required_issue_fields "
                f"missing {missing_fields}"
            )
        scope = planning_project.get("scope")
        if not isinstance(scope, str) or not all(token in scope for token in ("per-source Projects", "legacy evidence", "must not be required", "used for PASS")):
            errors.append(
                "apps_monorepo_archive_gate.canonical_planning_project.scope must allow per-source Projects only as legacy evidence, not as required/PASS evidence"
            )
        if planning_project.get("api_proof_required_for_archive_pass") is not True:
            errors.append("apps_monorepo_archive_gate.canonical_planning_project.api_proof_required_for_archive_pass must be true")
    scan_surfaces = gate.get("scan_surfaces")
    if not isinstance(scan_surfaces, list):
        errors.append("apps_monorepo_archive_gate.scan_surfaces must be a list")
    else:
        actual = {item.get("surface") for item in scan_surfaces if isinstance(item, dict)}
        missing = sorted(APPS_MONOREPO_ARCHIVE_SCAN_SURFACES - actual)
        if missing:
            errors.append(f"apps_monorepo_archive_gate.scan_surfaces missing {missing}")

    source = contract.get("source", {})
    if not isinstance(source, dict):
        errors.append("source must be an object")
        return errors
    path = "source"
    archive_source = source.get("archive_source_repo")
    if archive_source in APPS_MONOREPO_ARCHIVE_SOURCE_REPOS:
        source_repository = source.get("source_repository")
        if source_repository in APPS_MONOREPO_ARCHIVE_SOURCE_REPOS:
            errors.append(f"{path}.source_repository must be BearsCLOUD/apps, not {source_repository}")
        expected_subpath = APPS_MONOREPO_ARCHIVE_SOURCE_REPOS[archive_source]
        if source_repository != APPS_MONOREPO_REPOSITORY:
            errors.append(f"{path}.source_repository must be BearsCLOUD/apps for archived source {archive_source}")
        if source.get("source_subpath") != expected_subpath:
            errors.append(f"{path}.source_subpath must be {expected_subpath}")
        if source.get("archive_allowed") is not False:
            errors.append(f"{path}.archive_allowed must stay false until infra/local_cd archive checks pass")
        archive_blocker = source.get("archive_blocker")
        if not isinstance(archive_blocker, str) or not all(
            token in archive_blocker for token in ("infra/local_cd", "workflows", "Kubernetes", "secret-custody")
        ):
            errors.append(f"{path}.archive_blocker must name infra/local_cd, workflows, Kubernetes docs, and secret-custody scans")
        planning_project = source.get("canonical_planning_project_invariant")
        if not isinstance(planning_project, str) or not all(
            token in planning_project for token in ("Apps Migration & Planning", "canonical", "Project", "required migration fields", "API proof")
        ):
            errors.append(f"{path}.canonical_planning_project_invariant must require the canonical Apps planning Project with populated fields")
        if "Migrate " in planning_project and " into apps" in planning_project:
            errors.append(f"{path}.canonical_planning_project_invariant must not require a separate per-source Project")
        if source.get("per_source_projects_policy") != "legacy_evidence_only_not_required_not_created_not_pass":
            errors.append(f"{path}.per_source_projects_policy must mark per-source Projects as legacy evidence only")
    return errors


def descriptor_path(repo_root: Path, contract: dict[str, Any], application: str) -> Path:
    """Return the repo-local descriptor path for *application*."""
    descriptor_dir = Path(str(contract.get("application_descriptor_directory", DEFAULT_APP_DESCRIPTOR_DIR)))
    if descriptor_dir.is_absolute() or ".." in descriptor_dir.parts:
        raise ContractError("application_descriptor_directory must stay relative to repo root")
    for item in contract.get("applications", []):
        if isinstance(item, dict) and item.get("application") == application:
            raw_descriptor = item.get("descriptor", descriptor_dir / f"{application}.v1.json")
            rel = Path(str(raw_descriptor))
            if rel.is_absolute() or ".." in rel.parts:
                raise ContractError("application descriptor path must stay relative to repo root")
            return repo_root / rel
    return repo_root / descriptor_dir / f"{application}.v1.json"


def application_contract(contract: dict[str, Any], application: str | None, repo_root: Path) -> dict[str, Any]:
    """Return the selected application CD contract.

    App desired state lives in the bears-infra repo under local_cd/applications.
    The plugin catalog supplies only global authority metadata.
    """
    if not application:
        raise ContractError("--application is required; app desired state is descriptor-owned")
    selected = load_json(descriptor_path(repo_root, contract, application))
    if selected.get("schema") != "bears.local-cd-application.v1":
        raise ContractError("application descriptor schema mismatch")
    if selected.get("application") != application:
        raise ContractError("application descriptor name mismatch")
    for path in walk_keys(selected):
        key = path.rsplit(".", 1)[-1]
        if key in FORBIDDEN_DESCRIPTOR_KEYS or key == "kubeconfig_source":
            raise ContractError(f"application descriptor contains executor-owned field: {path}")
    selected["schema"] = contract.get("schema")
    selected.setdefault("version", contract.get("version"))
    selected.setdefault("owner_plugin", contract.get("owner_plugin"))
    selected.setdefault("git_contract_ref", contract.get("git_contract_ref"))
    selected.setdefault("repository", contract.get("repository"))
    selected.setdefault("target_id", contract.get("target_id"))
    selected.setdefault("evidence", contract.get("evidence"))
    selected.setdefault("rollback", contract.get("rollback"))
    selected.setdefault("apps_monorepo_archive_gate", contract.get("apps_monorepo_archive_gate"))
    selected.setdefault("forbidden_manifest_literals", [])
    selected.setdefault("required_manifest_literals", [])
    source = selected.setdefault("source", {})
    if isinstance(source, dict):
        source.setdefault("branch_source", "git_contract")
    kube = selected.setdefault("kubernetes", {})
    if isinstance(kube, dict):
        kube.setdefault("server_alias", "fyuriserv")
        kube.setdefault("environment", "prod")
        kube.setdefault("kubeconfig_source", "runner_environment")
    return selected


def manifest_text(repo_root: Path, contract: dict[str, Any]) -> tuple[Path, str]:
    """Return the manifest directory and concatenated YAML text."""
    rel = Path(str(contract.get("source", {}).get("manifest_path", "")))
    if rel.is_absolute() or ".." in rel.parts:
        raise ContractError("manifest_path must stay relative to repo root")
    manifest_dir = (repo_root / rel).resolve()
    repo_resolved = repo_root.resolve()
    if repo_resolved not in (manifest_dir, *manifest_dir.parents):
        raise ContractError("manifest_path escapes repo root")
    files = sorted(manifest_dir.glob("*.yaml"))
    if not files:
        raise ContractError(f"no YAML manifests found in {manifest_dir}")
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    return manifest_dir, text


def validate_manifest_safety(repo_root: Path, contract: dict[str, Any]) -> list[str]:
    """Validate manifest safety literals and immutable image digest policy."""
    errors: list[str] = []
    try:
        _manifest_dir, text = manifest_text(repo_root, contract)
    except ContractError as exc:
        return [str(exc)]
    for token in contract.get("forbidden_manifest_literals", []):
        if token in text:
            errors.append(f"forbidden manifest literal present: {token}")
    for token in contract.get("required_manifest_literals", []):
        if token not in text:
            errors.append(f"required manifest literal missing: {token}")
    image_repository = contract.get("source", {}).get("image_repository")
    if image_repository and image_repository not in text:
        errors.append("configured image repository missing from manifests")
    digests = DIGEST_RE.findall(text)
    local_ref = str(contract.get("source", {}).get("image_ref", ""))
    local_build = local_image_build_enabled(contract)
    if local_build and local_ref and local_ref not in text:
        errors.append("configured local image ref missing from manifests")
    digest_required = contract.get("source", {}).get("image_digest_required") is not False
    if digest_required and not digests and not local_build:
        errors.append("immutable sha256 image digest missing")
    if any(digest == "0" * 64 for digest in digests):
        errors.append("placeholder all-zero image digest is forbidden")
    if str(contract.get("kubernetes", {}).get("namespace")) not in text:
        errors.append("configured namespace missing from manifests")
    return errors


def validate_all(git_path: Path, cd_path: Path, repo_root: Path, application: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate all contracts and manifests or raise ContractError."""
    git_contract = load_json(git_path)
    cd_root = load_json(cd_path)
    cd_contract = application_contract(cd_root, application, repo_root)
    errors = []
    errors.extend(validate_git_contract(git_contract))
    errors.extend(validate_cd_root_contract(cd_root))
    errors.extend(validate_cd_contract(cd_contract, git_contract))
    errors.extend(validate_manifest_safety(repo_root, cd_contract))
    if errors:
        raise ContractError("\n".join(errors))
    return git_contract, cd_contract


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    """Run one fixed external command with inherited stdout/stderr."""
    subprocess.run(command, check=True, env=env)



def run_capture(command: list[str], *, env: dict[str, str] | None = None) -> str:
    """Run a fixed command and return stdout with stderr suppressed from evidence."""
    result = subprocess.run(
        command,
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.stdout


def run_apply_yaml(document: str, *, env: dict[str, str]) -> None:
    """Apply a generated Kubernetes document through stdin without printing it."""
    subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=document,
        check=True,
        env=env,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def yaml_scalar(value: str) -> str:
    """Return a conservative single-quoted YAML scalar."""
    return "'" + value.replace("'", "''") + "'"


def docker_networks() -> list[str]:
    """Return Docker network names visible to the runner."""
    if not shutil.which("docker"):
        return []
    try:
        output = run_capture(["docker", "network", "ls", "--format", "{{.Name}}"])
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def container_network_ip(container: str, network: str) -> str | None:
    """Return a Docker container IP on a network, if attached."""
    if not shutil.which("docker"):
        return None
    try:
        output = run_capture(["docker", "inspect", container, "--format", f"{{{{with index .NetworkSettings.Networks {json.dumps(network)}}}}}{{{{.IPAddress}}}}{{{{end}}}}"])
    except subprocess.CalledProcessError:
        return None
    value = output.strip()
    return value or None


def resolve_infisical_host_api(config: dict[str, Any]) -> str:
    """Resolve the Infisical API endpoint reachable from the Kubernetes cluster."""
    env_name = config.get("host_api_env", "INFISICAL_HOST_API")
    if isinstance(env_name, str):
        value = os.environ.get(env_name)
        if value:
            return value
    container = str(config.get("docker_container", ""))
    port = int(config.get("container_port", 8080))
    patterns = [str(item) for item in config.get("docker_network_name_patterns", []) if str(item)]
    networks = docker_networks()
    preferred = [network for network in networks if any(pattern in network for pattern in patterns)] or networks
    for network in preferred:
        ip = container_network_ip(container, network)
        if not ip and shutil.which("docker"):
            try:
                subprocess.run(["docker", "network", "connect", network, container], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                pass
            ip = container_network_ip(container, network)
        if ip:
            return f"http://{ip}:{port}/api"
    raise ContractError("unable to resolve Infisical hostAPI from env or Docker network")


def require_env(env: dict[str, str], name: str) -> str:
    """Return a required environment variable value without logging it."""
    value = env.get(name)
    if not value:
        raise ContractError(f"required env ref is unset: {name}")
    return value


def bootstrap_infisical_cluster_secret_store(contract: dict[str, Any], env: dict[str, str]) -> None:
    """Create or refresh the shared Infisical ClusterSecretStore credentials and store."""
    config = contract.get("bootstrap", {}).get("infisical_cluster_secret_store", {})
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return
    namespace = str(config.get("credentials_namespace", "external-secrets"))
    secret_name = str(config.get("credentials_secret_name", "infisical-universal-auth-credentials"))
    client_id_key = str(config.get("client_id_key", "clientId"))
    client_secret_key = str(config.get("client_secret_key", "clientSecret"))
    client_id = require_env(env, str(config.get("client_id_env", "INFISICAL_UNIVERSAL_AUTH_CLIENT_ID")))
    client_secret = require_env(env, str(config.get("client_secret_env", "INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET")))
    host_api = resolve_infisical_host_api(config)
    run_apply_yaml(
        "\n".join([
            "apiVersion: v1",
            "kind: Namespace",
            "metadata:",
            f"  name: {namespace}",
            "",
        ]),
        env=env,
    )
    run_apply_yaml(
        "\n".join([
            "apiVersion: v1",
            "kind: Secret",
            "metadata:",
            f"  name: {secret_name}",
            f"  namespace: {namespace}",
            "type: Opaque",
            "stringData:",
            f"  {client_id_key}: {yaml_scalar(client_id)}",
            f"  {client_secret_key}: {yaml_scalar(client_secret)}",
            "",
        ]),
        env=env,
    )
    store_name = str(config.get("store_name", "infisical-bears"))
    store_yaml = "\n".join([
        "apiVersion: external-secrets.io/v1",
        "kind: ClusterSecretStore",
        "metadata:",
        f"  name: {store_name}",
        "spec:",
        "  provider:",
        "    infisical:",
        f"      hostAPI: {yaml_scalar(host_api)}",
        "      auth:",
        "        universalAuthCredentials:",
        "          clientId:",
        f"            name: {secret_name}",
        f"            namespace: {namespace}",
        f"            key: {client_id_key}",
        "          clientSecret:",
        f"            name: {secret_name}",
        f"            namespace: {namespace}",
        f"            key: {client_secret_key}",
        "      secretsScope:",
        f"        projectSlug: {yaml_scalar(str(config.get('project_slug', 'bears-workspace')))}",
        f"        environmentSlug: {yaml_scalar(str(config.get('environment_slug', 'prod')))}",
        f"        secretsPath: {yaml_scalar(str(config.get('secrets_path', '/')))}",
        f"        recursive: {str(config.get('recursive', True)).lower()}",
        f"        expandSecretReferences: {str(config.get('expand_secret_references', True)).lower()}",
        "",
    ])
    run_apply_yaml(store_yaml, env=env)


def infisical_api_request(method: str, api_base: str, path: str, *, token: str | None = None, body: dict[str, Any] | None = None, params: dict[str, str] | None = None) -> dict[str, Any]:
    """Call Infisical without logging request or response bodies."""
    base = api_base.rstrip("/")
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw.decode() or "{}")
    except urllib.error.HTTPError as exc:
        exc.read()
        raise ContractError(f"Infisical {method} {path} failed with HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise ContractError(f"Infisical {method} {path} failed: {exc.reason}") from None


def resolve_infisical_runner_docker_api_url(config: dict[str, Any]) -> str | None:
    """Resolve Infisical through Docker for the self-hosted CI runner."""
    container = str(config.get("docker_container", "bears-infisical-backend"))
    port = int(config.get("container_port", 8080))
    patterns = [str(item) for item in config.get("docker_network_name_patterns", []) if str(item)]
    networks = docker_networks()
    ordered: list[str] = []
    for pattern in patterns:
        ordered.extend(network for network in networks if pattern in network and network not in ordered)
    ordered.extend(network for network in networks if network not in ordered)
    for network in ordered:
        ip = container_network_ip(container, network)
        if ip:
            return f"http://{ip}:{port}/api"
    return None


def resolve_infisical_api_url(config: dict[str, Any]) -> str:
    """Resolve the Infisical API URL used by the CI runner, not by Kubernetes pods."""
    env_name = str(config.get("api_url_env", config.get("host_api_env", "INFISICAL_HOST_API")))
    value = os.environ.get(env_name)
    if not value and config.get("docker_fallback", True) is not False:
        value = resolve_infisical_runner_docker_api_url(config)
    if not value:
        value = str(config.get("default_api_url", "http://127.0.0.1:58080/api"))
    if not (value.startswith("http://") or value.startswith("https://")):
        raise ContractError("Infisical API URL must be http or https")
    return value.rstrip("/")


def infisical_login(api_url: str, client_id: str, client_secret: str) -> str:
    """Return a Universal Auth access token without exposing it."""
    payload = infisical_api_request(
        "POST",
        api_url,
        "/v1/auth/universal-auth/login",
        body={"clientId": client_id, "clientSecret": client_secret},
    )
    token = payload.get("accessToken") or payload.get("token")
    if not token:
        raise ContractError("Infisical Universal Auth login returned no access token")
    return str(token)


def infisical_get_secret_value(api_url: str, access_token: str, *, project_id: str, environment: str, secret_path: str, secret_name: str) -> str:
    """Read one required secret value for immediate Kubernetes Secret bootstrap."""
    payload = infisical_api_request(
        "GET",
        api_url,
        f"/v4/secrets/{urllib.parse.quote(secret_name, safe='')}",
        token=access_token,
        params={
            "projectId": project_id,
            "environment": environment,
            "secretPath": secret_path,
            "type": "shared",
            "viewSecretValue": "true",
            "expandSecretReferences": "false",
            "includeImports": "false",
        },
    )
    value = (payload.get("secret") or {}).get("secretValue")
    if not isinstance(value, str) or not value:
        raise ContractError(f"Infisical secret is missing or empty: {secret_path}/{secret_name}")
    return value


def contract_image_reference(manifest: Path, contract: dict[str, Any]) -> str:
    """Return the first built image reference matching source.image_repository."""
    image_repository = str(contract.get("source", {}).get("image_repository", ""))
    if not image_repository:
        raise ContractError("source.image_repository missing")
    text = manifest.read_text(encoding="utf-8")
    for match in re.finditer(r"^\s*image:\s*['\"]?([^'\"\s]+)", text, flags=re.MULTILINE):
        image_ref = match.group(1)
        if image_ref == image_repository or image_ref.startswith(f"{image_repository}:") or image_ref.startswith(f"{image_repository}@"):
            return image_ref
    raise ContractError("configured image reference missing from built manifests")


def local_image_build_config(contract: dict[str, Any]) -> dict[str, Any]:
    """Return executor-owned local image build settings for the app."""
    application = str(contract.get("application", ""))
    defaults = EXECUTOR_LOCAL_BUILD_DEFAULTS.get(application, {})
    if not defaults:
        return {}
    source = contract.get("source", {})
    if not isinstance(source, dict):
        raise ContractError("source must be an object")
    config = dict(defaults)
    for key in ("source_repository", "source_ref", "source_subpath"):
        if key in source:
            config[key] = source[key]
    return config


def local_image_build_enabled(contract: dict[str, Any]) -> bool:
    """Return true when the executable owns a local build for this app."""
    return bool(local_image_build_config(contract))


def source_image_ref(contract: dict[str, Any], manifest: Path | None = None) -> str:
    """Return the image reference declared by source.image_ref or built manifest."""
    image_ref = str(contract.get("source", {}).get("image_ref", ""))
    if image_ref:
        return image_ref
    if manifest is None:
        raise ContractError("source.image_ref missing")
    return contract_image_reference(manifest, contract)


def safe_repo_relative_path(repo_root: Path, raw_path: str, field_name: str) -> Path:
    """Resolve a repo-relative path and reject path escape."""
    rel = Path(raw_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ContractError(f"{field_name} must stay relative to repo root")
    resolved = (repo_root / rel).resolve()
    repo_resolved = repo_root.resolve()
    if repo_resolved not in (resolved, *resolved.parents):
        raise ContractError(f"{field_name} escapes repo root")
    return resolved


def prepare_local_source(repo_root: Path, contract: dict[str, Any]) -> None:
    """Stage app source into the executor-owned build context when needed."""
    if not local_image_build_enabled(contract):
        return
    config = local_image_build_config(contract)
    source_repository = str(config.get("source_repository", ""))
    source_subpath = str(config.get("source_subpath", ""))
    if source_repository != APPS_MONOREPO_REPOSITORY or not source_subpath:
        return
    source_root = Path("/srv/bears/dev/app") / source_subpath
    if not source_root.is_dir():
        raise ContractError(f"local source directory missing: {source_subpath}")
    context_path = safe_repo_relative_path(repo_root, str(config.get("context_path", "")), "executor.context_path")
    if context_path.exists():
        shutil.rmtree(context_path)
    ignore = shutil.ignore_patterns(*sorted(SOURCE_SYNC_EXCLUDES))
    shutil.copytree(source_root, context_path, ignore=ignore)


def build_local_image(repo_root: Path, contract: dict[str, Any]) -> str:
    """Build the executable-declared image locally on the GitHub Actions runner."""
    if not local_image_build_enabled(contract):
        return ""
    if not shutil.which("docker"):
        raise ContractError("docker is required for local image build")
    config = local_image_build_config(contract)
    image_ref = source_image_ref(contract)
    if not image_ref or image_ref.endswith(":latest"):
        raise ContractError("source.image_ref must be a non-latest image tag for local build")
    context_path = safe_repo_relative_path(repo_root, str(config.get("context_path", "")), "executor.context_path")
    if not context_path.is_dir():
        raise ContractError("local image build context path is missing")
    command = ["docker", "build", "--pull", "-t", image_ref]
    if config.get("clear_proxy_build_args") is True:
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            command.extend(["--build-arg", f"{name}="])
    dockerfile = str(config.get("dockerfile", ""))
    if dockerfile:
        dockerfile_path = safe_repo_relative_path(context_path, dockerfile, "executor.dockerfile")
        command.extend(["-f", str(dockerfile_path)])
    command.append(str(context_path))
    run(command)
    return image_ref


def kubectl_node_names(env: dict[str, str]) -> list[str]:
    """Return Kubernetes node names for local image loading."""
    output = run_capture(["kubectl", "get", "nodes", "-o", "jsonpath={range .items[*]}{.metadata.name}{'\\n'}{end}"], env=env)
    return [line.strip() for line in output.splitlines() if line.strip()]


def import_image_to_k3d_node(image_ref: str, node: str) -> None:
    """Import a local Docker image archive into one k3d node's k8s containerd namespace."""
    if not shutil.which("docker"):
        raise ContractError("docker is required for k3d local image load")
    if subprocess.run(["docker", "inspect", node], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        raise ContractError(f"k3d node container not found: {node}")
    save = subprocess.Popen(["docker", "save", image_ref], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert save.stdout is not None
    load = subprocess.Popen(
        ["docker", "exec", "-i", node, "ctr", "-n", "k8s.io", "images", "import", "-"],
        stdin=save.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    save.stdout.close()
    load_return = load.wait()
    save_return = save.wait()
    if save_return != 0 or load_return != 0:
        raise ContractError(f"failed to import local image into k3d node: {node}")


def load_local_image_to_k3d(contract: dict[str, Any], image_ref: str, env: dict[str, str]) -> None:
    """Load the locally built image into all Kubernetes nodes."""
    if not local_image_build_enabled(contract):
        return
    nodes = kubectl_node_names(env)
    if not nodes:
        raise ContractError("no Kubernetes nodes found for local image load")
    for node in nodes:
        import_image_to_k3d_node(image_ref, node)


def check_remote_registry_pull_access(contract: dict[str, Any], manifest: Path, _env: dict[str, str]) -> None:
    """Reject remote registry pull preflight; Bears CD uses local image handoff."""
    if local_image_build_enabled(contract):
        return
    preflight = contract.get("preflight", {})
    if not isinstance(preflight, dict):
        return
    if preflight.get("remote_registry_pull") is True:
        image_ref = contract_image_reference(manifest, contract)
        raise ContractError(
            f"remote registry pull preflight is disabled for {image_ref}; "
            "use an executor-owned local image handoff or source.image_ref"
        )


def bootstrap_infisical_runtime_secret(contract: dict[str, Any], env: dict[str, str]) -> None:
    """Create or refresh the app runtime Kubernetes Secret from Infisical."""
    config = contract.get("bootstrap", {}).get("infisical_runtime_secret", {})
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return
    namespace = str(config.get("namespace") or contract.get("kubernetes", {}).get("namespace"))
    secret_name = str(config.get("secret_name", "codex-telegram-mcp-runtime"))
    api_url = resolve_infisical_api_url(config)
    client_id = require_env(env, str(config.get("client_id_env", "INFISICAL_UNIVERSAL_AUTH_CLIENT_ID")))
    client_secret = require_env(env, str(config.get("client_secret_env", "INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET")))
    project_id = str(config.get("project_id", ""))
    environment = str(config.get("environment_slug", "prod"))
    secret_path = str(config.get("secret_path", "/prod/codex-telegram"))
    mappings = config.get("mappings", [])
    if not project_id:
        raise ContractError("infisical_runtime_secret.project_id is required")
    if not isinstance(mappings, list) or not mappings:
        raise ContractError("infisical_runtime_secret.mappings must be non-empty")
    access_token = infisical_login(api_url, client_id, client_secret)
    data_lines: list[str] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ContractError("infisical_runtime_secret mapping must be an object")
        env_key = str(mapping.get("env_key", ""))
        remote_key = str(mapping.get("remote_key", ""))
        if not env_key or not remote_key:
            raise ContractError("infisical_runtime_secret mapping requires env_key and remote_key")
        required = mapping.get("required", True) is not False
        try:
            value = infisical_get_secret_value(
                api_url,
                access_token,
                project_id=project_id,
                environment=environment,
                secret_path=secret_path,
                secret_name=remote_key,
            )
        except ContractError:
            if required:
                raise
            continue
        data_lines.append(f"  {env_key}: {yaml_scalar(value)}")
    run_apply_yaml(
        "\n".join([
            "apiVersion: v1",
            "kind: Namespace",
            "metadata:",
            f"  name: {namespace}",
            "",
        ]),
        env=env,
    )
    run_apply_yaml(
        "\n".join([
            "apiVersion: v1",
            "kind: Secret",
            "metadata:",
            f"  name: {secret_name}",
            f"  namespace: {namespace}",
            "type: Opaque",
            "stringData:",
            *data_lines,
            "",
        ]),
        env=env,
    )

def kubectl_apply_command(contract: dict[str, Any], manifest: Path) -> list[str]:
    """Return the contract-declared kubectl apply command."""
    mode = contract.get("kubernetes", {}).get("apply_mode", "client")
    if mode == "client":
        return ["kubectl", "apply", "-f", str(manifest)]
    if mode == "server_side":
        return ["kubectl", "apply", "--server-side", "-f", str(manifest)]
    raise ContractError(f"unsupported kubernetes.apply_mode: {mode}")


def _timeout_arg(contract: dict[str, Any]) -> str:
    """Return the kubectl timeout argument from Kubernetes contract settings."""
    kube = contract.get("kubernetes", {})
    timeout_seconds = kube.get("rollout_timeout_seconds", 180)
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ContractError("kubernetes.rollout_timeout_seconds must be a positive integer")
    return f"--timeout={timeout_seconds}s"


def _named_targets(contract: dict[str, Any], singular: str, plural: str) -> list[str]:
    """Return one or many Kubernetes workload names from the contract."""
    kube = contract.get("kubernetes", {})
    many = kube.get(plural)
    if many is None:
        one = kube.get(singular)
        if one is None:
            return []
        if not isinstance(one, str) or not one:
            raise ContractError(f"kubernetes.{singular} must be a non-empty string")
        return [one]
    if not isinstance(many, list) or not many:
        raise ContractError(f"kubernetes.{plural} must be a non-empty list")
    names: list[str] = []
    for item in many:
        if not isinstance(item, str) or not item:
            raise ContractError(f"kubernetes.{plural} entries must be non-empty strings")
        names.append(item)
    return names


def rollout_targets(contract: dict[str, Any]) -> tuple[list[str], str]:
    """Return deployment names and timeout for the contract rollout wait."""
    deployments = _named_targets(contract, "deployment", "deployments")
    if not deployments:
        raise ContractError("kubernetes.deployment missing")
    return deployments, _timeout_arg(contract)


def daemonset_rollout_targets(contract: dict[str, Any]) -> tuple[list[str], str]:
    """Return DaemonSet names and timeout for the contract rollout wait."""
    return _named_targets(contract, "daemonset", "daemonsets"), _timeout_arg(contract)


def job_wait_targets(contract: dict[str, Any]) -> tuple[list[str], str]:
    """Return job names and timeout for completion waits."""
    return _named_targets(contract, "job", "jobs"), _timeout_arg(contract)


def wait_for_declared_workloads(contract: dict[str, Any], env: dict[str, str]) -> None:
    """Wait for declared Deployment rollout and Job completion targets."""
    namespace = str(contract["kubernetes"]["namespace"])
    if contract.get("kubernetes", {}).get("deployment") or contract.get("kubernetes", {}).get("deployments"):
        deployments, timeout = rollout_targets(contract)
        for deployment in deployments:
            run(["kubectl", "-n", namespace, "rollout", "status", f"deployment/{deployment}", timeout], env=env)
    daemonsets, timeout = daemonset_rollout_targets(contract)
    for daemonset in daemonsets:
        run(["kubectl", "-n", namespace, "rollout", "status", f"daemonset/{daemonset}", timeout], env=env)
    jobs, timeout = job_wait_targets(contract)
    for job in jobs:
        run(["kubectl", "-n", namespace, "wait", "--for=condition=complete", f"job/{job}", timeout], env=env)


def rollout_restart_after_apply(contract: dict[str, Any], env: dict[str, str]) -> None:
    """Restart declared deployments after mutable runtime bootstrap resources change."""
    kube = contract.get("kubernetes", {})
    if kube.get("restart_after_apply") is not True:
        return
    namespace = str(kube.get("namespace", ""))
    if not namespace:
        raise ContractError("kubernetes.namespace missing")
    if kube.get("deployment") or kube.get("deployments"):
        deployments, _timeout = rollout_targets(contract)
        for deployment in deployments:
            run(["kubectl", "-n", namespace, "rollout", "restart", f"deployment/{deployment}"], env=env)
    daemonsets, _timeout = daemonset_rollout_targets(contract)
    for daemonset in daemonsets:
        run(["kubectl", "-n", namespace, "rollout", "restart", f"daemonset/{daemonset}"], env=env)


def build_manifests(repo_root: Path, contract: dict[str, Any]) -> Path:
    """Build Kubernetes manifests with kustomize or kubectl's bundled kustomize."""
    manifest_dir, _text = manifest_text(repo_root, contract)
    output = Path(tempfile.mkdtemp(prefix="bears-cd-")) / "manifest.yaml"
    if shutil.which("kustomize"):
        command = ["kustomize", "build", str(manifest_dir)]
    else:
        command = ["kubectl", "kustomize", str(manifest_dir)]
    with output.open("w", encoding="utf-8") as handle:
        subprocess.run(command, check=True, stdout=handle)
    return output


def configure_kubeconfig(contract: dict[str, Any]) -> tuple[dict[str, str], Any]:
    """Configure Kubernetes credentials from the contract-declared source."""
    kube = contract.get("kubernetes", {})
    source = kube.get("kubeconfig_source", "env_b64")
    if source == "runner_environment":
        return dict(os.environ), nullcontext()
    if source != "env_b64":
        raise ContractError(f"unsupported kubernetes.kubeconfig_source: {source}")
    env_name = kube.get("kubeconfig_b64_env")
    if not isinstance(env_name, str) or not env_name:
        raise ContractError("kubernetes.kubeconfig_b64_env missing")
    encoded = os.environ.get(env_name)
    if not encoded:
        raise ContractError(f"required kubeconfig env ref is unset: {env_name}")
    tempdir = tempfile.TemporaryDirectory(prefix="bears-kubeconfig-")
    kubeconfig = Path(tempdir.name) / "kubeconfig"
    try:
        kubeconfig.write_bytes(base64.b64decode(encoded, validate=True))
    except Exception as exc:  # noqa: BLE001 - base64 raises several concrete errors.
        tempdir.cleanup()
        raise ContractError(f"invalid base64 kubeconfig env ref: {env_name}") from exc
    kubeconfig.chmod(0o600)
    env = dict(os.environ)
    env["KUBECONFIG"] = str(kubeconfig)
    return env, tempdir


def _sanitized_failure(exc: BaseException) -> str:
    """Return a compact failure reason without paths, tokens, or raw command output."""
    if isinstance(exc, ContractError):
        return str(exc).splitlines()[0][:180]
    if isinstance(exc, subprocess.CalledProcessError):
        command = " ".join(str(part) for part in exc.cmd[:3]) if isinstance(exc.cmd, list) else str(exc.cmd)
        return f"{command} failed with exit code {exc.returncode}"[:180]
    return exc.__class__.__name__


def check_kube_prerequisites(contract: dict[str, Any], env: dict[str, str]) -> None:
    """Check declared Kubernetes prerequisites before mutating application state."""
    preflight = contract.get("preflight", {})
    if not isinstance(preflight, dict):
        return
    api_resources = preflight.get("api_resources", [])
    cluster_resources = preflight.get("cluster_resources", [])
    if api_resources:
        result = subprocess.run(
            ["kubectl", "api-resources", "-o", "name"],
            check=True,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        available = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        for item in api_resources:
            if not isinstance(item, dict):
                raise ContractError("preflight.api_resources entries must be objects")
            name = item.get("name")
            if not isinstance(name, str) or not name:
                raise ContractError("preflight.api_resources[].name missing")
            if name not in available:
                raise ContractError(f"required Kubernetes API resource missing: {name}")
    for item in cluster_resources:
        if not isinstance(item, dict):
            raise ContractError("preflight.cluster_resources entries must be objects")
        kind = item.get("kind")
        name = item.get("name")
        if not isinstance(kind, str) or not kind or not isinstance(name, str) or not name:
            raise ContractError("preflight.cluster_resources entries require kind and name")
        subprocess.run(
            ["kubectl", "get", kind, name],
            check=True,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def write_evidence(evidence_dir: Path, contract: dict[str, Any], repository: str, branch: str, sha: str, status: str, failure: str | None = None) -> Path:
    """Write sanitized CD evidence without kubeconfig, tokens, logs, or secrets."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    application = str(contract.get("application", "unknown-application"))
    path = evidence_dir / f"{application}-cd.txt"
    lines = [
        "schema=bears.sanitized-cd-evidence.v1",
        f"status={status}",
        f"repository={repository}",
        f"branch={branch}",
        f"sha={sha}",
        f"application={contract.get('application')}",
        f"target_id={contract.get('target_id')}",
        f"namespace={contract.get('kubernetes', {}).get('namespace')}",
        f"deployment={contract.get('kubernetes', {}).get('deployment')}",
        f"daemonset={contract.get('kubernetes', {}).get('daemonset')}",
        f"job={contract.get('kubernetes', {}).get('job')}",
        f"manifest_path={contract.get('source', {}).get('manifest_path')}",
    ]
    if failure:
        lines.append(f"failure={failure}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def deploy(args: argparse.Namespace) -> None:
    """Run the fixed automatic CD sequence."""
    git_contract, cd_contract = validate_all(args.git_contract, args.cd_contract, args.repo_root, args.application)
    resolve_target(git_contract, args.repository, args.branch)
    manifest = build_manifests(args.repo_root, cd_contract)
    env, kubeconfig_context = configure_kubeconfig(cd_contract)
    evidence = write_evidence(args.evidence_dir, cd_contract, args.repository, args.branch, args.sha, "started")
    with kubeconfig_context:
        try:
            prepare_local_source(args.repo_root, cd_contract)
            local_image_ref = build_local_image(args.repo_root, cd_contract)
            if local_image_ref:
                load_local_image_to_k3d(cd_contract, local_image_ref, env)
            bootstrap_infisical_cluster_secret_store(cd_contract, env)
            bootstrap_infisical_runtime_secret(cd_contract, env)
            check_kube_prerequisites(cd_contract, env)
            check_remote_registry_pull_access(cd_contract, manifest, env)
            run(kubectl_apply_command(cd_contract, manifest), env=env)
            rollout_restart_after_apply(cd_contract, env)
            wait_for_declared_workloads(cd_contract, env)
        except (ContractError, subprocess.CalledProcessError) as exc:
            write_evidence(args.evidence_dir, cd_contract, args.repository, args.branch, args.sha, "failed", _sanitized_failure(exc))
            raise
    evidence = write_evidence(args.evidence_dir, cd_contract, args.repository, args.branch, args.sha, "succeeded")
    print(f"automatic CD complete; sanitized evidence: {evidence}")


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command_parsers: dict[str, argparse.ArgumentParser] = {}
    for name in ("validate", "deploy"):
        command_parser = sub.add_parser(name)
        command_parser.add_argument("--git-contract", type=Path, default=DEFAULT_GIT_CONTRACT)
        command_parser.add_argument("--cd-contract", type=Path, default=DEFAULT_CD_CONTRACT)
        command_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
        command_parser.add_argument("--application")
        command_parsers[name] = command_parser
    command_parsers["deploy"].add_argument("--repository", required=True)
    command_parsers["deploy"].add_argument("--branch", required=True)
    command_parsers["deploy"].add_argument("--sha", required=True)
    command_parsers["deploy"].add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate_all(args.git_contract, args.cd_contract, args.repo_root, args.application)
            print("Bears automatic CD contracts ok")
        elif args.command == "deploy":
            deploy(args)
    except (ContractError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
