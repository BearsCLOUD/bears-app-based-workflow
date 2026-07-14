"""Fixed identities, paths, schemas, and limits for the deployment gateway."""

from __future__ import annotations

from pathlib import Path
import re

PLUGIN = "bears-app-based-workflow"
MARKETPLACE = "bears-app-based-workflow"
REPOSITORY = "https://github.com/BearsCLOUD/bears-app-based-workflow.git"
REPOSITORY_SHORTHAND = "BearsCLOUD/bears-app-based-workflow"
MAIN_REF = "refs/remotes/origin/main"
CODEX_HOME = Path("/srv/bears/codex/ai1")
MARKETPLACE_ROOT = CODEX_HOME / ".tmp/marketplaces" / MARKETPLACE
STATE_ROOT = Path("/var/lib/bears-plugin-deploy")
STATE_DIR = STATE_ROOT / "ai1"
STATE_FILE = STATE_DIR / f"{PLUGIN}.json"
INTENT_FILE = STATE_DIR / f"{PLUGIN}.promotion-intent.json"
LOCK_FILE = STATE_DIR / f"{PLUGIN}.lock"
MIGRATION_TOMBSTONE_FILE = STATE_DIR / f"{PLUGIN}.v1-registration-migrated.json"
ROLE_GENERATIONS_DIR = STATE_DIR / "role-generations"
ROLE_RECEIPT_DIR = CODEX_HOME / "state"
ROLE_RECEIPT_FILE = ROLE_RECEIPT_DIR / f"{PLUGIN}-role-sync.json"
MIRROR = STATE_DIR / "repository.git"
GIT = "/usr/bin/git"
CODEX = "/srv/bears/.codex/packages/standalone/current/bin/codex"
SHA_RE = re.compile(r"[0-9a-f]{40}")
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")
SEMVER_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
LEGACY_VERSION_RE = re.compile(r"\d+\.\d+\.\d+\+codex\.\d{14}")
VERSION_RE = re.compile(rf"(?:{SEMVER_RE.pattern}|{LEGACY_VERSION_RE.pattern})")
LEGACY_DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v1"
PRIOR_DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v2"
GRAPH_DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v3"
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v4"
PROMOTION_INTENT_SCHEMA = "bears-plugin-promotion-intent.v5"
LEGACY_ROLE_RECEIPT_SCHEMA = "bears-role-install-receipt.v1"
ROLE_RECEIPT_SCHEMA = "bears-role-install-receipt.v2"
ROLE_MIGRATION_TOMBSTONE_SCHEMA = "bears-role-registration-migration.v1"
LEGACY_ROLE_VERSION = "0.1.0+codex.20260711074119"
LEGACY_ROLE_NAMES = (
    "diagnostic-command-runner",
    "domain-lane-orchestrator",
    "explorer",
    "primary-source-researcher",
    "role-profile-architect",
    "runtime-evidence-reader",
    "security-analysis-critic",
    "worker",
    "workflow-orchestrator",
)
LEGACY_ROLE_PATHS = {
    "diagnostic-command-runner": "/srv/bears/plugins/bears-app-based-workflow/agents/diagnostic-command-runner.toml",
    "domain-lane-orchestrator": "/srv/bears/plugins/bears-app-based-workflow/agents/domain-lane-orchestrator.toml",
    "explorer": "/srv/bears/plugins/bears-app-based-workflow/agents/explorer.toml",
    "primary-source-researcher": "/srv/bears/plugins/bears-app-based-workflow/agents/primary-source-researcher.toml",
    "role-profile-architect": "/srv/bears/plugins/bears-app-based-workflow/agents/role-profile-architect.toml",
    "runtime-evidence-reader": "/srv/bears/plugins/bears-app-based-workflow/agents/runtime-evidence-reader.toml",
    "security-analysis-critic": "/srv/bears/plugins/bears-app-based-workflow/agents/security-analysis-critic.toml",
    "worker": "/srv/bears/plugins/bears-app-based-workflow/agents/worker.toml",
    "workflow-orchestrator": "/srv/bears/plugins/bears-app-based-workflow/agents/workflow-orchestrator.toml",
}
LEGACY_ROLE_COUNT = 9
LEGACY_ROLE_BLOCK_LENGTH = 1301
LEGACY_ROLE_MANAGED_DIGEST = "72938ba5e0bf98464077941dfbd7465f7528ecb6d8937003603f1239415d2901"
LEGACY_ROLE_RECEIPT_LENGTH = 1445
LEGACY_ROLE_RECEIPT_SHA256 = "a2d80113324e76668e2afc958da14fc2b53ef061676ec28eaf3ff7ac181d25f2"
LEGACY_ARCHIVE_DIRECTORY = (
    "archive/bears-app-based-workflow/0.1.0+codex.20260710051738/"
    "sync-16f8326f934f-001"
)
LEGACY_ARCHIVE_FILES = (
    "bears-analytics-quality-engineer.toml",
    "bears-auth-domain-orchestrator.toml",
    "bears-auth-platform-engineer.toml",
    "bears-deploy-platform-engineer.toml",
    "bears-development-workflow-orchestrator.toml",
    "bears-gateway-domain-orchestrator.toml",
    "bears-gateway-platform-engineer.toml",
    "bears-github-branch-protection-settings-governor.toml",
    "bears-infra-domain-orchestrator.toml",
    "bears-notifications-platform-engineer.toml",
    "bears-orchestrator.toml",
    "bears-payments-domain-orchestrator.toml",
    "bears-payments-platform-engineer.toml",
    "bears-platform-security-reviewer.toml",
    "bears-product-app-zone-engineer.toml",
    "bears-qa-governance-orchestrator.toml",
    "bears-tenant-domain-orchestrator.toml",
    "bears-tenant-registry-platform-engineer.toml",
    "bears-wb-integration-platform-engineer.toml",
)
PROFILE_FIELDS = frozenset(
    {"name", "description", "model", "model_reasoning_effort", "sandbox_mode", "developer_instructions"}
)
BEGIN_ROLE_MARKER = b"# >>> bears-app-based-workflow agent roles (managed by ./install)"
END_ROLE_MARKER = b"# <<< bears-app-based-workflow agent roles (managed by ./install)"
CONFIG_LOCK_NAME = ".config.toml.coordination.lock"
CONFIG_MAX_BYTES = 1024 * 1024
PROFILE_MAX_BYTES = 256 * 1024
ROLE_RECEIPT_MAX_BYTES = 64 * 1024
RECEIPT_MAX_BYTES = 64 * 1024
INTENT_MAX_BYTES = 8 * 1024 * 1024
GRAPH_MAX_BYTES = 1024 * 1024
GRAPH_INSTRUCTIONS_TEMPLATE = "assets/codex-home-graph-instructions.md"
SUBPROCESS_DIAGNOSTIC_LIMIT = 512
GITHUB_TOKEN_MAX_BYTES = 1024
GITHUB_TOKEN_RE = re.compile(rb"[\x21-\x7e]+")
SENTRY_DSN_FILE = Path("/home/ai1/.config/bears-app-based-workflow/credentials/sentry-dsn")
SENTRY_SERVICE = "bears-app-based-workflow"
SENTRY_COMPONENT = "deploy-plugin-gateway"
SENTRY_TIMEOUT_SECONDS = 2
ACTIONABLE_ERROR_CODES = frozenset(
    {
        "unhandled-exception",
        "receipt-corruption",
        "mutation-failure-after-start",
        "post-mutation-failure",
        "recovery-activated",
        "recovery-failure",
    }
)
PAYLOAD_PATHS = (
    ".codex-plugin",
    "agents",
    "contracts",
    "skills",
    "scripts",
    "hooks",
    "assets",
    ".app.json",
    ".mcp.json",
    "install",
)
LEGACY_PAYLOAD_PATHS = (
    ".codex-plugin",
    "agents",
    "skills",
    "scripts",
    "hooks",
    "assets",
    ".app.json",
    ".mcp.json",
    "AGENTS.md",
    "install",
)
ENV = {
    "HOME": "/home/ai1",
    "CODEX_HOME": str(CODEX_HOME),
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "HTTP_PROXY": "http://127.0.0.1:8090",
    "HTTPS_PROXY": "http://127.0.0.1:8090",
    "http_proxy": "http://127.0.0.1:8090",
    "https_proxy": "http://127.0.0.1:8090",
    "NO_PROXY": "localhost,127.0.0.1,::1,.local",
    "no_proxy": "localhost,127.0.0.1,::1,.local",
    "CODEX_PROXY_URL": "http://127.0.0.1:8090",
    "CODEX_PROXY_HTTP_FALLBACK": "http://127.0.0.1:8090",
}
FIXED_MARKETPLACE_SOURCE = {"sourceType": "git", "source": REPOSITORY}
RENAME_NOREPLACE = 1
RENAME_EXCHANGE = 2
SNAPSHOT_METADATA_FIELDS = frozenset(
    {"dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns"}
)
