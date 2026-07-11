#!/usr/bin/env bash
# Install the pinned isolated runner and its root-owned deployment gateway.

set -euo pipefail
umask 027

readonly RUNNER_VERSION="2.335.1"
readonly RUNNER_SHA256="4ef2f25285f0ae4477f1fe1e346db76d2f3ebf03824e2ddd1973a2819bf6c8cf"
readonly RUNNER_USER="bears-plugin-runner"
readonly RUNNER_GROUP="bears-plugin-runner"
readonly RUNNER_HOME="/var/lib/bears-plugin-runner"
readonly RUNNER_DIR="/opt/bears-plugin-runner"
readonly RUNNER_LABEL="bears-plugin-cd"
readonly REPOSITORY="BearsCLOUD/bears-app-based-workflow"
readonly REPOSITORY_URL="https://github.com/${REPOSITORY}"
readonly ARCHIVE="/var/cache/bears-plugin-runner/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
readonly ARCHIVE_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
readonly DEPLOY_COMMAND="/usr/local/sbin/deploy-bears-app-based-workflow"
readonly DEPLOY_STATE_ROOT="/var/lib/bears-plugin-deploy"
readonly DEPLOY_STATE_DIR="$DEPLOY_STATE_ROOT/ai1"
readonly LEGACY_DEPLOY_STATE_DIR="/srv/bears/codex/ai1/.local/state/bears-plugin-deploy"
readonly SUDOERS_FILE="/etc/sudoers.d/bears-plugin-runner-deploy"
readonly SERVICE_NAME="bears-plugin-runner.service"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"

stage=""
archive_tmp=""
sudoers_tmp=""
unit_tmp=""

die() { printf 'install-runner: %s\n' "$*" >&2; exit 1; }
cleanup() {
  /usr/bin/rm -rf -- "${stage:-}"
  /usr/bin/rm -f -- "${archive_tmp:-}" "${sudoers_tmp:-}" "${unit_tmp:-}"
}
trap cleanup EXIT

[[ $EUID -eq 0 ]] || die "run as ai1 with sudo"
[[ ${SUDO_USER:-} == ai1 ]] || die "the interactive sudo caller must be ai1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
[[ -f "$script_dir/deploy_plugin.py" && ! -L "$script_dir/deploy_plugin.py" ]] || \
  die "deploy_plugin.py must be a regular file beside the installer"

if ! /usr/bin/getent group "$RUNNER_GROUP" >/dev/null; then
  /usr/sbin/groupadd --system "$RUNNER_GROUP"
fi
IFS=: read -r group_name _ runner_gid _ < <(/usr/bin/getent group "$RUNNER_GROUP")
[[ "$group_name" == "$RUNNER_GROUP" && "$runner_gid" =~ ^[0-9]+$ && "$runner_gid" != 0 ]] || \
  die "$RUNNER_GROUP is not a safe dedicated group"
while IFS=: read -r candidate _ candidate_gid _; do
  [[ "$candidate_gid" != "$runner_gid" || "$candidate" == "$RUNNER_GROUP" ]] || \
    die "group id $runner_gid is shared with $candidate"
done < <(/usr/bin/getent group)
while IFS=: read -r candidate _ _ candidate_gid _; do
  [[ "$candidate_gid" != "$runner_gid" || "$candidate" == "$RUNNER_USER" ]] || \
    die "$RUNNER_GROUP is a primary group for $candidate"
done < <(/usr/bin/getent passwd)
if ! /usr/bin/getent passwd "$RUNNER_USER" >/dev/null; then
  /usr/sbin/useradd --system --create-home --home-dir "$RUNNER_HOME" \
    --shell /usr/sbin/nologin --no-user-group --gid "$RUNNER_GROUP" "$RUNNER_USER"
fi
IFS=: read -r _ _ _ _ _ actual_home actual_shell < <(/usr/bin/getent passwd "$RUNNER_USER")
[[ "$actual_home" == "$RUNNER_HOME" && "$actual_shell" == /usr/sbin/nologin ]] || \
  die "$RUNNER_USER must keep the fixed home and no-login shell"
/usr/sbin/usermod --gid "$RUNNER_GROUP" --groups '' "$RUNNER_USER"
IFS=: read -r _ _ _ group_members < <(/usr/bin/getent group "$RUNNER_GROUP")
[[ -z "$group_members" ]] || die "$RUNNER_GROUP must not contain supplementary members"
[[ "$(/usr/bin/id -gn "$RUNNER_USER")" == "$RUNNER_GROUP" ]] || \
  die "$RUNNER_USER primary group must be $RUNNER_GROUP"
[[ "$(/usr/bin/id -G "$RUNNER_USER")" == "$runner_gid" ]] || \
  die "$RUNNER_USER must not have supplementary groups"

# Stop every previously managed service before touching runner or gateway state.
if /usr/bin/systemctl is-active --quiet "$SERVICE_NAME"; then
  /usr/bin/systemctl stop "$SERVICE_NAME"
fi
/usr/bin/systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
if [[ -e "$RUNNER_DIR/.service" || -L "$RUNNER_DIR/.service" ]]; then
  [[ -f "$RUNNER_DIR/.service" && ! -L "$RUNNER_DIR/.service" ]] || \
    die "legacy service marker is unsafe"
  legacy_service="$(<"$RUNNER_DIR/.service")"
  [[ "$legacy_service" =~ ^actions\.runner\.[A-Za-z0-9_.@-]+\.service$ ]] || \
    die "legacy service name is unsafe"
  if /usr/bin/systemctl is-active --quiet "$legacy_service"; then
    /usr/bin/systemctl stop "$legacy_service"
  fi
  /usr/bin/systemctl disable "$legacy_service" >/dev/null 2>&1 || true
  /usr/bin/rm -f -- "/etc/systemd/system/$legacy_service"
fi
if /usr/bin/pgrep -u "$RUNNER_USER" >/dev/null; then
  /usr/bin/pkill -KILL -u "$RUNNER_USER" || true
fi
/usr/bin/pgrep -u "$RUNNER_USER" >/dev/null && die "$RUNNER_USER still has running processes"

# Provision the gateway-owned state boundary and import only the old deployment receipt.
IFS=: read -r _ _ ai1_uid ai1_gid _ _ _ < <(/usr/bin/getent passwd ai1)
[[ "$ai1_uid" =~ ^[0-9]+$ && "$ai1_uid" != 0 && "$ai1_gid" =~ ^[0-9]+$ ]] || \
  die "ai1 must have a fixed non-root uid and numeric gid"
/usr/bin/python3 - \
  "$ai1_uid" "$ai1_gid" "$DEPLOY_STATE_ROOT" "$DEPLOY_STATE_DIR" \
  "$LEGACY_DEPLOY_STATE_DIR" <<'PY'
import ctypes
import errno
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import sys

AI1_UID = int(sys.argv[1])
AI1_GID = int(sys.argv[2])
STATE_ROOT = sys.argv[3]
STATE_DIR = sys.argv[4]
LEGACY_STATE_DIR = sys.argv[5]
PLUGIN = "bears-app-based-workflow"
RECEIPT = f"{PLUGIN}.json"
INTENT = f"{PLUGIN}.promotion-intent.json"
LOCK = f"{PLUGIN}.lock"
IMPORT_TOMBSTONE = f"{PLUGIN}.legacy-state-imported.json"
IMPORT_TOMBSTONE_SCHEMA = "bears-plugin-deploy-state-import.v1"
LEGACY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v1"
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v2"
REPOSITORY = "https://github.com/BearsCLOUD/bears-app-based-workflow.git"
LEGACY_RECEIPT_PATH = f"{LEGACY_STATE_DIR}/{RECEIPT}"
MAXIMUM = 64 * 1024
FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
RENAME_NOREPLACE = 1
RECEIPT_FIELDS = {
    "schema",
    "repository",
    "marketplace",
    "plugin",
    "sha",
    "version",
    "payload_fingerprint",
}
ROLE_RECEIPT_FIELDS = {
    "role_generation",
    "role_count",
    "role_catalog_sha256",
    "role_receipt_sha256",
    "role_source_blobs",
    "role_profiles",
}
ROLE_NAMES = (
    "app-worker",
    "diagnostic-command-runner",
    "domain-lane-orchestrator",
    "explorer",
    "primary-source-researcher",
    "role-profile-architect",
    "runtime-evidence-reader",
    "security-analysis-critic",
    "wave-change-critic",
    "worker",
    "workflow-orchestrator",
)


def fail(message: str) -> None:
    raise SystemExit(f"install-runner: {message}")


if (
    STATE_ROOT != "/var/lib/bears-plugin-deploy"
    or STATE_DIR != f"{STATE_ROOT}/ai1"
    or LEGACY_STATE_DIR
    != "/srv/bears/codex/ai1/.local/state/bears-plugin-deploy"
):
    fail("deployment state path contract drifted")


def validate_directory(
    descriptor: int,
    label: str,
    *,
    uid: int,
    gid: int | None,
    exact_mode: int | None,
    allow_group_write: bool = False,
) -> None:
    value = os.fstat(descriptor)
    mode = stat.S_IMODE(value.st_mode)
    if (
        not stat.S_ISDIR(value.st_mode)
        or value.st_uid != uid
        or (gid is not None and value.st_gid != gid)
        or (exact_mode is not None and mode != exact_mode)
        or (exact_mode is None and (mode & (0o002 if allow_group_write else 0o022)))
    ):
        fail(f"unsafe directory in deployment state path: {label}")


def open_child(parent: int, name: str, label: str) -> int:
    try:
        return os.open(name, FLAGS, dir_fd=parent)
    except OSError as exc:
        fail(f"missing or unsafe directory in deployment state path: {label}: {exc.errno}")


root = os.open("/", FLAGS)
validate_directory(root, "/", uid=0, gid=0, exact_mode=None)
var = open_child(root, "var", "/var")
validate_directory(var, "/var", uid=0, gid=0, exact_mode=None)
var_lib = open_child(var, "lib", "/var/lib")
validate_directory(var_lib, "/var/lib", uid=0, gid=0, exact_mode=None)
try:
    state_root = os.open("bears-plugin-deploy", FLAGS, dir_fd=var_lib)
except FileNotFoundError:
    os.mkdir("bears-plugin-deploy", 0o755, dir_fd=var_lib)
    state_root = os.open("bears-plugin-deploy", FLAGS, dir_fd=var_lib)
    os.fchown(state_root, 0, 0)
    os.fchmod(state_root, 0o755)
    os.fsync(state_root)
    os.fsync(var_lib)
except OSError as exc:
    fail(f"unsafe deployment state root: {exc.errno}")
validate_directory(
    state_root,
    "/var/lib/bears-plugin-deploy",
    uid=0,
    gid=0,
    exact_mode=0o755,
)
try:
    state = os.open("ai1", FLAGS, dir_fd=state_root)
except FileNotFoundError:
    os.mkdir("ai1", 0o700, dir_fd=state_root)
    state = os.open("ai1", FLAGS, dir_fd=state_root)
    os.fchown(state, AI1_UID, AI1_GID)
    os.fchmod(state, 0o700)
    os.fsync(state)
    os.fsync(state_root)
except OSError as exc:
    fail(f"unsafe ai1 deployment state leaf: {exc.errno}")
validate_directory(
    state,
    "/var/lib/bears-plugin-deploy/ai1",
    uid=AI1_UID,
    gid=AI1_GID,
    exact_mode=0o700,
)


def optional_old_state() -> int | None:
    descriptor = os.dup(root)
    specifications = (
        ("srv", "/srv", 0, 0, 0o755),
        ("bears", "/srv/bears", 0, AI1_GID, 0o775),
        ("codex", "/srv/bears/codex", AI1_UID, None, 0o2770),
        ("ai1", "/srv/bears/codex/ai1", AI1_UID, AI1_GID, 0o700),
        (".local", "/srv/bears/codex/ai1/.local", AI1_UID, AI1_GID, 0o775),
        ("state", "/srv/bears/codex/ai1/.local/state", AI1_UID, AI1_GID, 0o775),
        (
            "bears-plugin-deploy",
            "/srv/bears/codex/ai1/.local/state/bears-plugin-deploy",
            AI1_UID,
            AI1_GID,
            0o700,
        ),
    )
    for name, label, uid, gid, mode in specifications:
        try:
            child = os.open(name, FLAGS, dir_fd=descriptor)
        except FileNotFoundError:
            os.close(descriptor)
            return None
        except OSError as exc:
            os.close(descriptor)
            fail(f"unsafe legacy deployment state ancestor {label}: {exc.errno}")
        os.close(descriptor)
        descriptor = child
        validate_directory(descriptor, label, uid=uid, gid=gid, exact_mode=mode)
    return descriptor


def entry_exists(directory: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def read_private(directory: int, name: str, label: str) -> bytes:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory,
        )
    except OSError as exc:
        fail(f"missing or unsafe {label}: {exc.errno}")
    try:
        value = os.fstat(descriptor)
        if (
            not stat.S_ISREG(value.st_mode)
            or value.st_uid != AI1_UID
            or value.st_gid != AI1_GID
            or stat.S_IMODE(value.st_mode) != 0o600
            or value.st_nlink != 1
            or value.st_size > MAXIMUM
        ):
            fail(f"{label} is not a private ai1 regular file")
        payload = bytearray()
        while len(payload) <= MAXIMUM:
            chunk = os.read(descriptor, min(4096, MAXIMUM + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > MAXIMUM:
            fail(f"{label} is oversized")
        return bytes(payload)
    finally:
        os.close(descriptor)


def strict_json(payload: bytes, label: str) -> object:
    def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                fail(f"{label} contains duplicate JSON keys")
            value[key] = item
        return value

    try:
        return json.loads(payload, object_pairs_hook=strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{label} is malformed: {exc}")


def validate_receipt_identity(value: object, label: str) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or value.get("repository") != REPOSITORY
        or value.get("marketplace") != PLUGIN
        or value.get("plugin") != PLUGIN
        or not isinstance(value.get("sha"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", value["sha"])
        or not isinstance(value.get("version"), str)
        or not re.fullmatch(
            r"\d+\.\d+\.\d+\+codex\.\d{14}", value["version"]
        )
        or not isinstance(value.get("payload_fingerprint"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["payload_fingerprint"])
    ):
        fail(f"{label} identity is invalid")
    return value


def validate_legacy_receipt_value(
    value: object, label: str = "legacy deployment receipt"
) -> dict[str, object]:
    receipt = validate_receipt_identity(value, label)
    if set(receipt) != RECEIPT_FIELDS or receipt.get("schema") != LEGACY_RECEIPT_SCHEMA:
        fail(f"{label} shape is invalid")
    return receipt


def validate_legacy_receipt(payload: bytes) -> dict[str, object]:
    return validate_legacy_receipt_value(
        strict_json(payload, "legacy deployment receipt")
    )


def validate_destination_receipt(payload: bytes) -> dict[str, object]:
    label = "new deployment receipt"
    receipt = validate_receipt_identity(strict_json(payload, label), label)
    schema = receipt.get("schema")
    if schema == LEGACY_RECEIPT_SCHEMA:
        if set(receipt) != RECEIPT_FIELDS:
            fail("new v1 deployment receipt shape is invalid")
        return receipt
    if schema != DEPLOY_RECEIPT_SCHEMA or set(receipt) != RECEIPT_FIELDS | ROLE_RECEIPT_FIELDS:
        fail("new deployment receipt schema or shape is invalid")

    generation = receipt.get("role_generation")
    blobs = receipt.get("role_source_blobs")
    profiles = receipt.get("role_profiles")
    expected_sources = {
        ".codex-plugin/plugin.json",
        *(f"agents/{name}.toml" for name in ROLE_NAMES),
    }
    if (
        not isinstance(generation, str)
        or not re.fullmatch(r"[0-9a-f]{64}", generation)
        or receipt.get("role_count") != len(ROLE_NAMES)
        or receipt.get("role_catalog_sha256") != generation
        or not isinstance(receipt.get("role_receipt_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", receipt["role_receipt_sha256"])
        or not isinstance(blobs, dict)
        or set(blobs) != expected_sources
        or not isinstance(profiles, list)
        or len(profiles) != len(ROLE_NAMES)
    ):
        fail("new v2 deployment receipt role identity is invalid")
    for relative, record in blobs.items():
        if (
            not isinstance(record, dict)
            or set(record) != {"git_oid", "sha256"}
            or not isinstance(record.get("git_oid"), str)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", record["git_oid"])
            or not isinstance(record.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
        ):
            fail(f"new v2 deployment receipt role blob is invalid: {relative}")
    for name, record in zip(ROLE_NAMES, profiles, strict=True):
        source_record = blobs[f"agents/{name}.toml"]
        expected_path = f"{STATE_DIR}/role-generations/{generation}/{name}.toml"
        if (
            not isinstance(record, dict)
            or set(record) != {"name", "config_file", "git_oid", "sha256"}
            or record.get("name") != name
            or record.get("config_file") != expected_path
            or record.get("git_oid") != source_record["git_oid"]
            or record.get("sha256") != source_record["sha256"]
        ):
            fail(f"new v2 deployment receipt role profile is invalid: {name}")
    return receipt


def import_tombstone_bytes(
    source_sha256: str, source_identity: dict[str, object]
) -> bytes:
    value = {
        "schema": IMPORT_TOMBSTONE_SCHEMA,
        "source_path": LEGACY_RECEIPT_PATH,
        "source_sha256": source_sha256,
        "source_receipt": source_identity,
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def validate_import_tombstone(
    payload: bytes, source: bytes, source_identity: dict[str, object]
) -> None:
    label = "legacy state import tombstone"
    value = strict_json(payload, label)
    expected_fields = {"schema", "source_path", "source_sha256", "source_receipt"}
    if (
        not isinstance(value, dict)
        or set(value) != expected_fields
        or value.get("schema") != IMPORT_TOMBSTONE_SCHEMA
        or value.get("source_path") != LEGACY_RECEIPT_PATH
        or not isinstance(value.get("source_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["source_sha256"])
    ):
        fail("legacy state import tombstone shape is invalid")
    tombstone_identity = validate_legacy_receipt_value(
        value.get("source_receipt"), "legacy state import tombstone source receipt"
    )
    source_sha256 = hashlib.sha256(source).hexdigest()
    if (
        not hmac.compare_digest(value["source_sha256"], source_sha256)
        or tombstone_identity != source_identity
    ):
        fail("legacy deployment receipt drifted from its import tombstone")


libc = ctypes.CDLL(None, use_errno=True)
renameat2 = libc.renameat2
renameat2.argtypes = [
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_uint,
]
renameat2.restype = ctypes.c_int


def publish_private_no_replace(name: str, payload: bytes, label: str) -> None:
    temporary = f".{PLUGIN}.state-import.{secrets.token_hex(16)}.tmp"
    target_fd = os.open(
        temporary,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | os.O_NOFOLLOW,
        0o600,
        dir_fd=state,
    )
    try:
        os.fchown(target_fd, AI1_UID, AI1_GID)
        os.fchmod(target_fd, 0o600)
        offset = 0
        while offset < len(payload):
            advanced = os.write(target_fd, payload[offset:])
            if advanced <= 0:
                fail(f"{label} write did not advance")
            offset += advanced
        os.fsync(target_fd)
    finally:
        os.close(target_fd)
    if renameat2(
        state,
        os.fsencode(temporary),
        state,
        os.fsencode(name),
        RENAME_NOREPLACE,
    ) != 0:
        number = ctypes.get_errno()
        if number != errno.EEXIST:
            os.unlink(temporary, dir_fd=state)
            fail(f"{label} publication failed: {number}")
        try:
            current = read_private(state, name, label)
            if not hmac.compare_digest(current, payload):
                fail(f"{label} publication raced")
        finally:
            os.unlink(temporary, dir_fd=state)
    os.fsync(state)
    durable = read_private(state, name, label)
    if not hmac.compare_digest(durable, payload):
        fail(f"{label} is not durable")


import_tombstone_present = entry_exists(state, IMPORT_TOMBSTONE)
legacy = optional_old_state()
if legacy is None:
    if import_tombstone_present:
        fail("legacy deployment receipt source is missing after import")
else:
    receipt_present = entry_exists(legacy, RECEIPT)
    intent_present = entry_exists(legacy, INTENT)
    if receipt_present or intent_present or import_tombstone_present:
        if not entry_exists(legacy, LOCK):
            fail("legacy deployment state lock is missing")
        lock_fd = os.open(
            LOCK,
            os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=legacy,
        )
        lock_stat = os.fstat(lock_fd)
        if (
            not stat.S_ISREG(lock_stat.st_mode)
            or lock_stat.st_uid != AI1_UID
            or lock_stat.st_gid != AI1_GID
            or stat.S_IMODE(lock_stat.st_mode) != 0o600
            or lock_stat.st_nlink != 1
        ):
            fail("legacy deployment state lock is unsafe")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if entry_exists(legacy, INTENT):
            fail("legacy deployment state has an active promotion intent")
        if not entry_exists(legacy, RECEIPT):
            if import_tombstone_present:
                fail("legacy deployment receipt source disappeared after import")
        else:
            source = read_private(legacy, RECEIPT, "legacy deployment receipt")
            source_identity = validate_legacy_receipt(source)
            source_sha256 = hashlib.sha256(source).hexdigest()
            destination_present = entry_exists(state, RECEIPT)
            if import_tombstone_present:
                tombstone = read_private(
                    state, IMPORT_TOMBSTONE, "legacy state import tombstone"
                )
                validate_import_tombstone(tombstone, source, source_identity)
                if not destination_present:
                    fail("new deployment receipt is missing after legacy state import")
                destination = read_private(state, RECEIPT, "new deployment receipt")
                validate_destination_receipt(destination)
            else:
                if destination_present:
                    destination = read_private(state, RECEIPT, "new deployment receipt")
                    if not hmac.compare_digest(source, destination):
                        fail(
                            "new deployment state conflicts with the legacy receipt "
                            "without an import tombstone"
                        )
                else:
                    if os.listdir(state):
                        fail("new deployment state is non-empty before one-time receipt import")
                    publish_private_no_replace(
                        RECEIPT, source, "legacy deployment receipt import"
                    )
                imported = read_private(state, RECEIPT, "imported deployment receipt")
                if not hmac.compare_digest(source, imported):
                    fail("imported deployment receipt changed before tombstone publication")
                tombstone = import_tombstone_bytes(source_sha256, source_identity)
                publish_private_no_replace(
                    IMPORT_TOMBSTONE, tombstone, "legacy state import tombstone"
                )
                validate_import_tombstone(
                    read_private(
                        state, IMPORT_TOMBSTONE, "legacy state import tombstone"
                    ),
                    source,
                    source_identity,
                )
        os.close(lock_fd)
    os.close(legacy)
os.close(state)
os.close(state_root)
os.close(var_lib)
os.close(var)
os.close(root)
PY

/usr/bin/install -d -o root -g root -m 0755 "$(dirname "$ARCHIVE")"
if [[ -f "$ARCHIVE" ]] && ! printf '%s  %s\n' "$RUNNER_SHA256" "$ARCHIVE" | /usr/bin/sha256sum --check --status; then
  /usr/bin/rm -f "$ARCHIVE"
fi
if [[ ! -f "$ARCHIVE" ]]; then
  archive_tmp="$(/usr/bin/mktemp "${ARCHIVE}.XXXXXX")"
  /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 --output "$archive_tmp" "$ARCHIVE_URL"
  printf '%s  %s\n' "$RUNNER_SHA256" "$archive_tmp" | /usr/bin/sha256sum --check --status || \
    die "runner archive checksum mismatch"
  /usr/bin/install -o root -g root -m 0644 "$archive_tmp" "$ARCHIVE"
  /usr/bin/rm -f "$archive_tmp"
  archive_tmp=""
fi
printf '%s  %s\n' "$RUNNER_SHA256" "$ARCHIVE" | /usr/bin/sha256sum --check --status || \
  die "cached runner archive checksum mismatch"

# Configure only in a disposable runner-owned stage; root never executes its files.
stage="$(/usr/bin/mktemp -d /var/tmp/bears-plugin-runner.XXXXXX)"
/usr/bin/tar --extract --gzip --file "$ARCHIVE" --directory "$stage" --no-same-owner
/usr/bin/chown -R "$RUNNER_USER:$RUNNER_GROUP" "$stage"
token="$(/usr/sbin/runuser -u ai1 -- env HOME=/home/ai1 GH_PROMPT_DISABLED=1 \
  /home/ai1/.local/bin/gh api --method POST "repos/${REPOSITORY}/actions/runners/registration-token" --jq .token)"
[[ -n "$token" ]] || die "GitHub did not return a repository registration token"
runner_name="bears-plugin-cd-$(/usr/bin/hostname --short | /usr/bin/tr -cd 'A-Za-z0-9._-')"
/usr/sbin/runuser -u "$RUNNER_USER" -- env HOME="$RUNNER_HOME" \
  "$stage/config.sh" --unattended --replace --disableupdate \
  --url "$REPOSITORY_URL" --token "$token" --name "$runner_name" \
  --labels "$RUNNER_LABEL" --work _work
unset token
/usr/bin/chown -R root:root "$stage"
for credential in .runner .credentials .credentials_rsaparams; do
  [[ -f "$stage/$credential" && ! -L "$stage/$credential" ]] || \
    die "runner configuration did not create safe $credential"
done

# Re-extract verified code into the final root-owned tree; copy only data files.
/usr/bin/rm -rf "$RUNNER_DIR"
/usr/bin/install -d -o root -g root -m 0755 "$RUNNER_DIR"
/usr/bin/tar --extract --gzip --file "$ARCHIVE" --directory "$RUNNER_DIR" --no-same-owner
/usr/bin/chown -R root:root "$RUNNER_DIR"
/usr/bin/chmod -R go-w "$RUNNER_DIR"
[[ -f "$RUNNER_DIR/bin/runsvc.sh" && ! -L "$RUNNER_DIR/bin/runsvc.sh" && \
  -x "$RUNNER_DIR/bin/runsvc.sh" ]] || die "runner service wrapper is unsafe"
[[ "$(/usr/bin/stat -c '%U:%G' "$RUNNER_DIR/bin/runsvc.sh")" == root:root ]] || \
  die "runner service wrapper is not root-owned"
/usr/bin/install -o root -g root -m 0755 \
  "$RUNNER_DIR/bin/runsvc.sh" "$RUNNER_DIR/runsvc.sh"
/usr/bin/install -o root -g root -m 0644 "$stage/.runner" "$RUNNER_DIR/.runner"
/usr/bin/install -o "$RUNNER_USER" -g "$RUNNER_GROUP" -m 0600 \
  "$stage/.credentials" "$RUNNER_DIR/.credentials"
/usr/bin/install -o "$RUNNER_USER" -g "$RUNNER_GROUP" -m 0600 \
  "$stage/.credentials_rsaparams" "$RUNNER_DIR/.credentials_rsaparams"
/usr/bin/install -d -o "$RUNNER_USER" -g "$RUNNER_GROUP" -m 0700 \
  "$RUNNER_DIR/_work" "$RUNNER_DIR/_diag"
printf '%s\n' "$RUNNER_VERSION" >"$RUNNER_DIR/.bears-version"
/usr/bin/chown root:root "$RUNNER_DIR/.bears-version"
/usr/bin/chmod 0644 "$RUNNER_DIR/.bears-version"
/usr/bin/install -d -o root -g "$RUNNER_GROUP" -m 0750 "$RUNNER_HOME"

# Install and validate the immutable gateway and its sole sudo authorization.
/usr/bin/install -o root -g root -m 0755 "$script_dir/deploy_plugin.py" "$DEPLOY_COMMAND"
[[ "$(/usr/bin/stat -c '%U:%G:%a' "$DEPLOY_COMMAND")" == root:root:755 ]] || \
  die "deployment gateway ownership is not immutable"
sudoers_tmp="$(/usr/bin/mktemp /etc/sudoers.d/bears-plugin-runner-deploy.XXXXXX)"
printf '%s ALL=(ai1) NOPASSWD: %s ^[0-9a-f]{40}$\n' "$RUNNER_USER" "$DEPLOY_COMMAND" >"$sudoers_tmp"
/usr/bin/chmod 0440 "$sudoers_tmp"
/usr/sbin/visudo -cf "$sudoers_tmp" >/dev/null
/usr/bin/install -o root -g root -m 0440 "$sudoers_tmp" "$SUDOERS_FILE"
/usr/bin/rm -f "$sudoers_tmp"
sudoers_tmp=""

# The runner must not inherit operator groups or read operator credential state.
for protected_root in /home/ai1 /srv/bears/codex/ai1; do
  [[ -d "$protected_root" ]] || die "protected operator path is missing: $protected_root"
  for access_mode in -r -x; do
    if /usr/sbin/runuser -u "$RUNNER_USER" -- /usr/bin/test "$access_mode" "$protected_root"; then
      die "$RUNNER_USER can read or traverse protected operator path: $protected_root"
    fi
  done
done
for sensitive in \
  /home/ai1/.config/gh/hosts.yml \
  /srv/bears/codex/ai1/auth.json \
  /srv/bears/codex/ai1/config.toml; do
  if /usr/sbin/runuser -u "$RUNNER_USER" -- /usr/bin/test -r "$sensitive"; then
    die "$RUNNER_USER can read sensitive operator state: $sensitive"
  fi
done

# Use a fixed root-owned unit; the service executes official code only as the runner.
unit_tmp="$(/usr/bin/mktemp /etc/systemd/system/bears-plugin-runner.XXXXXX)"
cat >"$unit_tmp" <<EOF
[Unit]
Description=GitHub Actions runner for Bears plugin CD
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUNNER_USER
Group=$RUNNER_GROUP
SupplementaryGroups=
WorkingDirectory=$RUNNER_DIR
Environment=HOME=$RUNNER_HOME
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=$RUNNER_DIR/runsvc.sh
Restart=always
RestartSec=5
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$RUNNER_DIR/_work $RUNNER_DIR/_diag $RUNNER_DIR/.credentials $RUNNER_DIR/.credentials_rsaparams /srv/bears/codex/ai1 $DEPLOY_STATE_DIR
UMask=0077

[Install]
WantedBy=multi-user.target
EOF
/usr/bin/install -o root -g root -m 0644 "$unit_tmp" "$SERVICE_FILE"
/usr/bin/rm -f "$unit_tmp"
unit_tmp=""
/usr/bin/systemctl daemon-reload

# Activation is deliberately the final step; every prerequisite is already complete.
cleanup
trap - EXIT
exec /usr/bin/systemctl enable --now "$SERVICE_NAME"
