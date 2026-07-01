from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bears_auto_cd.py"
GIT_CONTRACT = ROOT / "assets" / "catalog" / "git-deploy-contract.v1.json"
CD_CONTRACT = ROOT / "assets" / "catalog" / "cd-kube-deploy-contract.v1.json"
KUBE_ROOT = ROOT.parents[1] / "kubernetes"


def run_cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_codex_telegram_manifest(path: Path, image: str | None = None, digest: str | None = None) -> None:
    image = image or f"registry.local/bears/codex-telegram-mcp@sha256:{digest or '1' * 64}"
    path.write_text(
        "\n".join([
            "apiVersion: apps/v1",
            "kind: Deployment",
            "metadata:",
            "  name: codex-telegram-mcp",
            "  namespace: codex-telegram-prod",
            "spec:",
            "  template:",
            "    spec:",
            "      containers:",
            "        - name: codex-telegram-mcp",
            f"          image: {image}",
            "          args: ['codex_telegram_mcp.http_server']",
            "          readinessProbe:",
            "            httpGet:",
            "              path: /readyz",
            "              port: http",
            "          livenessProbe:",
            "            httpGet:",
            "              path: /healthz",
            "              port: http",
            "          envFrom:",
            "            - secretRef:",
            "                name: codex-telegram-mcp-runtime",
            "          securityContext:",
            "            readOnlyRootFilesystem: true",
            "            allowPrivilegeEscalation: false",
            "",
        ]),
        encoding="utf-8",
    )


def test_contracts_reject_placeholder_digest_fixture(tmp_path: Path) -> None:
    fixture_root = tmp_path / "repo"
    fixture_manifest = fixture_root / "manifests" / "codex-telegram-prod"
    fixture_manifest.mkdir(parents=True)
    write_codex_telegram_manifest(fixture_manifest / "deployment.yaml", digest="0" * 64)
    cd_contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    cd_contract["source"].pop("image_ref", None)
    cd_contract["source"].pop("local_image_build", None)
    cd_contract["source"]["image_digest_required"] = True
    cd_path = tmp_path / "cd.json"
    write_json(cd_path, cd_contract)
    result = run_cli("validate", "--cd-contract", str(cd_path), "--repo-root", str(fixture_root))
    assert result.returncode == 1
    assert "placeholder all-zero image digest is forbidden" in result.stderr


def test_cd_contract_rejects_git_policy_fields(tmp_path: Path) -> None:
    cd_contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    cd_contract["deployment_branch"] = "main"
    cd_path = tmp_path / "cd.json"
    write_json(cd_path, cd_contract)
    result = run_cli("validate", "--cd-contract", str(cd_path), "--repo-root", str(KUBE_ROOT))
    assert result.returncode == 1
    assert "forbidden Git/manual gate field" in result.stderr


def test_git_contract_rejects_unknown_deploy_branch() -> None:
    git_contract = json.loads(GIT_CONTRACT.read_text(encoding="utf-8"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("bears_auto_cd", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.resolve_target(git_contract, "BearsCLOUD/bears-infra", "dev")
    except Exception as exc:  # noqa: BLE001 - test checks any resolver refusal.
        assert "not deployment branch" in str(exc)
    else:
        raise AssertionError("dev branch unexpectedly resolved to prod target")


def test_manifest_validator_accepts_nonzero_digest_fixture(tmp_path: Path) -> None:
    fixture_root = tmp_path / "repo"
    fixture_manifest = fixture_root / "manifests" / "codex-telegram-prod"
    fixture_manifest.mkdir(parents=True)
    contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    write_codex_telegram_manifest(
        fixture_manifest / "deployment.yaml",
        image=contract["source"]["image_ref"],
    )
    result = run_cli("validate", "--repo-root", str(fixture_root))
    assert result.returncode == 0, result.stderr
    assert "Bears automatic CD contracts ok" in result.stdout


def test_build_manifests_falls_back_to_kubectl_kustomize() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "shutil.which(\"kustomize\")" in text
    assert "[\"kubectl\", \"kustomize\"" in text


def test_cd_contract_uses_runner_kubeconfig_source() -> None:
    contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    assert contract["kubernetes"]["kubeconfig_source"] == "runner_environment"
    assert "use_runner_kubeconfig" in contract["ordered_steps"]
    assert "kubeconfig_b64_env" not in contract["kubernetes"]


def test_cd_contract_declares_kube_preflight_before_apply() -> None:
    contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    steps = contract["ordered_steps"]
    assert steps.index("bootstrap_infisical_runtime_secret") < steps.index("kubectl_apply")
    assert steps.index("build_local_image") < steps.index("load_local_image_to_k3d")
    assert steps.index("load_local_image_to_k3d") < steps.index("kubectl_apply")
    assert "check_remote_registry_pull_access" not in steps
    assert steps.index("preflight_kube_truth") < steps.index("kubectl_apply")
    assert steps.index("kubectl_apply") < steps.index("rollout_restart_after_apply")
    assert steps.index("rollout_restart_after_apply") < steps.index("rollout_status")
    assert "bootstrap_infisical_cluster_secret_store" not in steps
    assert contract["kubernetes"]["restart_after_apply"] is True
    api_names = {item["name"] for item in contract["preflight"]["api_resources"]}
    assert api_names == {"ingressroutes.traefik.io"}
    assert contract["preflight"]["cluster_resources"] == []
    assert "remote_registry_pull" not in contract["preflight"]
    assert contract["source"]["image_digest_required"] is False
    assert contract["source"]["image_ref"] == "codex-telegram-mcp:local-2eb8efbcfebd"
    local_build = contract["source"]["local_image_build"]
    assert local_build["enabled"] is True
    assert local_build["source_repository"] == "BearsCLOUD/codex-telegram-mcp"
    assert local_build["source_ref"] == "2eb8efbcfebde61b509bd3b975ec71ab0f7fe41d"
    assert local_build["context_path"] == ".codex-telegram-source"
    assert local_build["load_to_k3d_nodes"] is True
    runtime_secret = contract["bootstrap"]["infisical_runtime_secret"]
    assert runtime_secret["secret_name"] == "codex-telegram-mcp-runtime"
    assert runtime_secret["secret_path"] == "/prod/codex-telegram"
    assert runtime_secret["docker_fallback"] is True
    assert "selfhost_infisical" in runtime_secret["docker_network_name_patterns"]
    assert {item["env_key"] for item in runtime_secret["mappings"]} == {
        "CODEX_TELEGRAM_MCP_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ALLOWED_CHAT_IDS",
    }
    assert sorted(contract["bootstrap"]) == ["infisical_runtime_secret"]



def test_auto_cd_reads_infisical_runtime_secrets_without_store_manifest() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "def bootstrap_infisical_runtime_secret" in text
    assert "/v1/auth/universal-auth/login" in text
    assert "/v4/secrets/" in text
    assert "Infisical API URL must be http or https" in text
    assert "ProxyHandler({})" in text
    assert "def resolve_infisical_runner_docker_api_url" in text

def test_auto_cd_writes_started_failed_and_succeeded_evidence() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'write_evidence(args.evidence_dir, cd_contract, args.repository, args.branch, args.sha, "started")' in text
    assert '"failed", _sanitized_failure(exc)' in text
    assert '"succeeded"' in text


def test_cd_contract_declares_external_secrets_operator_app() -> None:
    contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    apps = {item["application"]: item for item in contract["applications"]}
    app = apps["external-secrets-operator"]
    assert app["source"]["manifest_path"] == "manifests/external-secrets-prod"
    assert app["kubernetes"]["apply_mode"] == "server_side"
    assert app["kubernetes"]["kubeconfig_source"] == "runner_environment"
    assert app["kubernetes"]["rollout_timeout_seconds"] == 600
    assert app["kubernetes"]["deployments"] == [
        "external-secrets-cert-controller",
        "external-secrets-webhook",
        "external-secrets",
    ]
    assert "kind: Secret" not in app["forbidden_manifest_literals"]


def test_cd_contract_declares_opencode_browser_auth_runtime() -> None:
    contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    apps = {item["application"]: item for item in contract["applications"]}
    app = apps["opencode-server"]
    assert app["kubernetes"]["restart_after_apply"] is True
    assert "bootstrap" not in app
    assert "ExternalSecret" not in app["required_manifest_literals"]
    assert "OPENAI_API_KEY" not in app["required_manifest_literals"]
    assert "opencode-server-runtime" not in app["required_manifest_literals"]


def test_cd_contract_declares_tgsearch_live_gate_app() -> None:
    contract = json.loads(CD_CONTRACT.read_text(encoding="utf-8"))
    apps = {item["application"]: item for item in contract["applications"]}
    app = apps["tgsearch-live-gate"]
    assert app["source"]["manifest_path"] == "manifests/tgsearch"
    assert app["source"]["image_repository"] == "tgintel"
    assert app["source"]["image_digest_required"] is False
    assert app["source"]["reject_latest_tag"] is True
    assert app["source"]["reject_placeholder_digest"] is True
    assert app["source"]["local_image_build"]["enabled"] is True
    assert app["source"]["local_image_build"]["context_path"] == ".tgsearch-source"
    assert app["kubernetes"]["namespace"] == "tgsearch-dev"
    assert app["kubernetes"]["job"] == "tgsearch-tgintel-live-gate"
    assert app["kubernetes"]["kubeconfig_source"] == "runner_environment"
    assert app["kubernetes"]["apply_mode"] == "server_side"
    assert "remote_registry_pull" not in app["preflight"]
    assert "tgintel:0.1.0" in app["required_manifest_literals"]
    assert "kind: Secret" in app["forbidden_manifest_literals"]
    assert "stringData:" in app["forbidden_manifest_literals"]


def test_auto_cd_supports_job_completion_waits() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "def job_wait_targets" in text
    assert "def wait_for_declared_workloads" in text
    assert '"--for=condition=complete"' in text
    assert "job/{job}" in text
    assert "kubernetes.jobs entries must be non-empty strings" in text


def test_auto_cd_supports_server_side_apply_mode() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'def kubectl_apply_command' in text
    assert '"--server-side"' in text
    assert 'unsupported kubernetes.apply_mode' in text


def test_auto_cd_supports_declared_rollout_targets() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'def rollout_targets' in text
    assert '"kubernetes.deployments must be a non-empty list"' in text
    assert 'for deployment in deployments' in text


def test_auto_cd_restarts_deployments_after_apply_when_declared() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "def rollout_restart_after_apply" in text
    assert '"rollout", "restart"' in text
    assert "rollout_restart_after_apply(cd_contract, env)" in text


def test_auto_cd_rejects_remote_registry_pull_preflight() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "def check_remote_registry_pull_access" in text
    assert "remote registry pull preflight is disabled" in text
    assert "source.local_image_build" in text
    assert "check_remote_registry_pull_access(cd_contract, manifest, env)" in text


def test_auto_cd_supports_local_image_build_and_k3d_load() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "def build_local_image" in text
    assert '"docker", "build", "--pull"' in text
    assert "def load_local_image_to_k3d" in text
    assert '"ctr", "-n", "k8s.io", "images", "import", "-"' in text
    assert "load_local_image_to_k3d(cd_contract, local_image_ref, env)" in text
