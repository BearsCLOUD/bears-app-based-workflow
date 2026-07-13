#!/usr/bin/env bash
# Install the pinned isolated runner and its root-owned deployment gateway.

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
readonly DEPLOY_PACKAGE_ROOT="/usr/local/lib/bears-plugin-deploy"
readonly DEPLOY_STATE_ROOT="/var/lib/bears-plugin-deploy"
readonly DEPLOY_STATE_DIR="$DEPLOY_STATE_ROOT/ai1"
readonly LEGACY_DEPLOY_STATE_DIR="/srv/bears/codex/ai1/.local/state/bears-plugin-deploy"
readonly SUDOERS_FILE="/etc/sudoers.d/bears-plugin-runner-deploy"
readonly SERVICE_NAME="bears-plugin-runner.service"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"

_install_runner_die() { printf 'install-runner: %s\n' "$*" >&2; exit 1; }

_install_runner_cleanup() {
  /usr/bin/rm -rf -- "${_install_runner_stage:-}"
  /usr/bin/rm -rf -- "${_install_runner_gateway_tmp:-}"
  /usr/bin/rm -f -- "${_install_runner_archive_tmp:-}" "${_install_runner_sudoers_tmp:-}" "${_install_runner_unit_tmp:-}"
}

_install_runner_service_cgroup() {
  local unit="$1" value
  value="$(/usr/bin/systemctl show --property=ControlGroup --value "$unit" 2>/dev/null || true)"
  [[ -z "$value" ]] && return 0
  [[ "$value" == /* && "$value" != / && "$value" != *..* && "$value" != *$'\n'* ]] || \
    _install_runner_die "$unit has an unsafe service cgroup"
  printf '%s\n' "$value"
}

_install_runner_service_cgroup_empty() {
  local unit="$1" cgroup="$2" cgroup_root="$3" directory events
  [[ -z "$cgroup" ]] && return 0
  [[ "$cgroup" == /* && "$cgroup" != / && "$cgroup" != *..* && "$cgroup" != *$'\n'* ]] || \
    _install_runner_die "$unit has an unsafe service cgroup"
  [[ "$cgroup_root" == /* && "$cgroup_root" != *..* && "$cgroup_root" != *$'\n'* ]] || \
    _install_runner_die "$unit has an unsafe cgroup root"
  directory="${cgroup_root%/}${cgroup}"
  [[ ! -e "$directory" && ! -L "$directory" ]] && return 0
  [[ -d "$directory" && ! -L "$directory" ]] || _install_runner_die "$unit service cgroup is unsafe"
  events="$directory/cgroup.events"
  [[ -f "$events" && ! -L "$events" ]] || _install_runner_die "$unit service cgroup events are unsafe"
  /usr/bin/grep -qx 'populated 0' "$events"
}

_install_runner_quiesce_managed_service() {
  local unit="$1" cgroup_root="$2" cgroup kill_file attempt
  cgroup="$(_install_runner_service_cgroup "$unit")"
  if /usr/bin/systemctl is-active --quiet "$unit"; then
    [[ -n "$cgroup" ]] || _install_runner_die "$unit active service cgroup is missing"
    /usr/bin/systemctl stop "$unit"
  fi
  if ! _install_runner_service_cgroup_empty "$unit" "$cgroup" "$cgroup_root"; then
    kill_file="${cgroup_root%/}${cgroup}/cgroup.kill"
    [[ -f "$kill_file" && ! -L "$kill_file" ]] || \
      _install_runner_die "$unit service cgroup cannot be terminated safely"
    printf '1\n' >"$kill_file"
    for attempt in {1..50}; do
      _install_runner_service_cgroup_empty "$unit" "$cgroup" "$cgroup_root" && break
      /usr/bin/sleep 0.1
    done
  fi
  _install_runner_service_cgroup_empty "$unit" "$cgroup" "$cgroup_root" || \
    _install_runner_die "$unit service cgroup still has running processes"
}

_install_runner_import_deployment_state() {
  local ai1_uid="$1" ai1_gid="$2" state_root="$3" state_dir="$4"
  local legacy_state_dir="$5" path_profile="$6" test_root="$7" crash_point="$8"
  /usr/bin/python3 - \
    "$ai1_uid" "$ai1_gid" "$state_root" "$state_dir" "$legacy_state_dir" \
    "$path_profile" "$test_root" "$crash_point" <<'PY'
import ctypes
import errno
import fcntl
import hashlib
import hmac
import json
import os
import re
import stat
import sys

AI1_UID = int(sys.argv[1])
AI1_GID = int(sys.argv[2])
STATE_ROOT = sys.argv[3]
STATE_DIR = sys.argv[4]
LEGACY_STATE_DIR = sys.argv[5]
PATH_PROFILE = sys.argv[6]
TEST_ROOT = sys.argv[7]
CRASH_POINT = sys.argv[8]
PLUGIN = "bears-app-based-workflow"
RECEIPT = f"{PLUGIN}.json"
INTENT = f"{PLUGIN}.promotion-intent.json"
LOCK = f"{PLUGIN}.lock"
IMPORT_STAGE = f".{PLUGIN}.legacy-state-import.stage"
IMPORT_TOMBSTONE = f"{PLUGIN}.legacy-state-imported.json"
IMPORT_TOMBSTONE_SCHEMA = "bears-plugin-deploy-state-import.v1"
LEGACY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v1"
PRIOR_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v2"
GRAPH_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v3"
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v4"
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
GRAPH_RECEIPT_FIELDS = {
    "graph_template_sha256",
    "graph_block_sha256",
    "graph_separator_added",
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


if PATH_PROFILE == "live":
    if (
        STATE_ROOT != "/var/lib/bears-plugin-deploy"
        or STATE_DIR != f"{STATE_ROOT}/ai1"
        or LEGACY_STATE_DIR
        != "/srv/bears/codex/ai1/.local/state/bears-plugin-deploy"
        or TEST_ROOT
        or CRASH_POINT
    ):
        fail("deployment state path contract drifted")
elif PATH_PROFILE == "test":
    if (
        not TEST_ROOT.startswith("/")
        or TEST_ROOT == "/"
        or ".." in TEST_ROOT.split("/")
        or "\n" in TEST_ROOT
        or STATE_ROOT != f"{TEST_ROOT}/state"
        or STATE_DIR != f"{STATE_ROOT}/ai1"
        or LEGACY_STATE_DIR != f"{TEST_ROOT}/legacy"
        or CRASH_POINT not in {
            "",
            "after-stage-write-before-receipt",
            "after-receipt-before-tombstone",
        }
    ):
        fail("test deployment state path contract drifted")
else:
    fail("unknown deployment state path profile")


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


def create_or_open_directory(
    parent: int,
    name: str,
    label: str,
    *,
    uid: int,
    gid: int,
    mode: int,
) -> int:
    try:
        descriptor = os.open(name, FLAGS, dir_fd=parent)
    except FileNotFoundError:
        os.mkdir(name, mode, dir_fd=parent)
        descriptor = os.open(name, FLAGS, dir_fd=parent)
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        os.fsync(parent)
    except OSError as exc:
        fail(f"unsafe deployment state directory {label}: {exc.errno}")
    validate_directory(descriptor, label, uid=uid, gid=gid, exact_mode=mode)
    return descriptor


var = None
var_lib = None
if PATH_PROFILE == "live":
    root = os.open("/", FLAGS)
    validate_directory(root, "/", uid=0, gid=0, exact_mode=None)
    var = open_child(root, "var", "/var")
    validate_directory(var, "/var", uid=0, gid=0, exact_mode=None)
    var_lib = open_child(var, "lib", "/var/lib")
    validate_directory(var_lib, "/var/lib", uid=0, gid=0, exact_mode=None)
    state_root = create_or_open_directory(
        var_lib,
        "bears-plugin-deploy",
        STATE_ROOT,
        uid=0,
        gid=0,
        mode=0o755,
    )
else:
    try:
        root = os.open(TEST_ROOT, FLAGS)
    except OSError as exc:
        fail(f"missing or unsafe test deployment state root: {exc.errno}")
    validate_directory(
        root,
        TEST_ROOT,
        uid=AI1_UID,
        gid=AI1_GID,
        exact_mode=0o700,
    )
    state_root = create_or_open_directory(
        root,
        "state",
        STATE_ROOT,
        uid=AI1_UID,
        gid=AI1_GID,
        mode=0o700,
    )
state = create_or_open_directory(
    state_root,
    "ai1",
    STATE_DIR,
    uid=AI1_UID,
    gid=AI1_GID,
    mode=0o700,
)


def optional_old_state() -> int | None:
    if PATH_PROFILE == "test":
        try:
            descriptor = os.open("legacy", FLAGS, dir_fd=root)
        except FileNotFoundError:
            return None
        except OSError as exc:
            fail(f"unsafe legacy deployment state path: {exc.errno}")
        validate_directory(
            descriptor,
            LEGACY_STATE_DIR,
            uid=AI1_UID,
            gid=AI1_GID,
            exact_mode=0o700,
        )
        return descriptor
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
            LEGACY_STATE_DIR,
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


def validate_private_file(descriptor: int, label: str) -> os.stat_result:
    value = os.fstat(descriptor)
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_uid != AI1_UID
        or value.st_gid != AI1_GID
        or stat.S_IMODE(value.st_mode) != 0o600
        or value.st_nlink != 1
    ):
        fail(f"{label} is not a private ai1 regular file")
    return value


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
        value = validate_private_file(descriptor, label)
        if value.st_size > MAXIMUM:
            fail(f"{label} is oversized")
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


def open_private_lock(
    directory: int, name: str, label: str, *, create: bool
) -> int:
    flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
    created = False
    if create:
        try:
            descriptor = os.open(
                name,
                flags | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory,
            )
            created = True
        except FileExistsError:
            descriptor = os.open(name, flags, dir_fd=directory)
    else:
        try:
            descriptor = os.open(name, flags, dir_fd=directory)
        except OSError as exc:
            fail(f"missing or unsafe {label}: {exc.errno}")
    try:
        if created:
            os.fchown(descriptor, AI1_UID, AI1_GID)
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
            os.fsync(directory)
        validate_private_file(descriptor, label)
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def acquire_private_lock(descriptor: int, label: str) -> None:
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            fail(f"{label} is busy")
        fail(f"{label} acquisition failed: {exc.errno}")


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
            r"(?:(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)|\d+\.\d+\.\d+\+codex\.\d{14})",
            value["version"],
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
    if schema not in {PRIOR_RECEIPT_SCHEMA, GRAPH_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA}:
        fail("new deployment receipt schema or shape is invalid")

    expected_fields = RECEIPT_FIELDS | ROLE_RECEIPT_FIELDS
    if schema in {GRAPH_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA}:
        expected_fields |= GRAPH_RECEIPT_FIELDS
    if set(receipt) != expected_fields:
        fail("new deployment receipt schema or shape is invalid")
    if schema in {GRAPH_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA} and (
        not isinstance(receipt.get("graph_template_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", receipt["graph_template_sha256"])
        or not isinstance(receipt.get("graph_block_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", receipt["graph_block_sha256"])
        or not isinstance(receipt.get("graph_separator_added"), bool)
    ):
        fail("new deployment receipt graph identity is invalid")

    generation = receipt.get("role_generation")
    blobs = receipt.get("role_source_blobs")
    profiles = receipt.get("role_profiles")
    profile_names = tuple(
        record.get("name")
        for record in profiles
        if isinstance(record, dict) and isinstance(record.get("name"), str)
    ) if isinstance(profiles, list) else ()
    expected_sources = {
        ".codex-plugin/plugin.json",
        "agents/README.md",
        *(f"agents/{name}.toml" for name in profile_names),
    }
    legacy_jsonless = receipt.get("version") == "0.3.0" or bool(
        isinstance(receipt.get("version"), str)
        and re.fullmatch(r"\d+\.\d+\.\d+\+codex\.\d{14}", receipt["version"])
    )
    has_definition_sources = isinstance(blobs, dict) and any(
        path.startswith("role-definitions/") for path in blobs
    )
    if schema == DEPLOY_RECEIPT_SCHEMA and (has_definition_sources or not legacy_jsonless):
        expected_sources.update(
            {
                "role-definitions/capability-catalog.v1.json",
                *(f"role-definitions/{name}.json" for name in profile_names),
            }
        )
    if (
        not isinstance(generation, str)
        or not re.fullmatch(r"[0-9a-f]{64}", generation)
        or not isinstance(receipt.get("role_count"), int)
        or isinstance(receipt.get("role_count"), bool)
        or not 1 <= receipt["role_count"] <= 64
        or receipt.get("role_catalog_sha256") != generation
        or not isinstance(receipt.get("role_receipt_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", receipt["role_receipt_sha256"])
        or not isinstance(blobs, dict)
        or set(blobs) != expected_sources
        or not isinstance(profiles, list)
        or len(profiles) != receipt["role_count"]
        or profile_names != tuple(sorted(set(profile_names)))
    ):
        fail("new deployment receipt role identity is invalid")
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
    for name, record in zip(profile_names, profiles, strict=True):
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
    source_path: str, source_sha256: str, source_identity: dict[str, object]
) -> bytes:
    value = {
        "schema": IMPORT_TOMBSTONE_SCHEMA,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "source_receipt": source_identity,
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def validate_import_tombstone(
    payload: bytes,
    source_path: str,
    source: bytes,
    source_identity: dict[str, object],
) -> None:
    label = "legacy state import tombstone"
    value = strict_json(payload, label)
    expected_fields = {"schema", "source_path", "source_sha256", "source_receipt"}
    if (
        not isinstance(value, dict)
        or set(value) != expected_fields
        or value.get("schema") != IMPORT_TOMBSTONE_SCHEMA
        or value.get("source_path") != source_path
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


def reconcile_import_stage(
    directory: int,
    stage_name: str,
    expected: bytes,
    label: str,
    *,
    partial_recoverable: bool,
) -> None:
    if not entry_exists(directory, stage_name):
        return
    staged = read_private(directory, stage_name, "legacy state import staging file")
    staged_sha256 = hashlib.sha256(staged).digest()
    expected_sha256 = hashlib.sha256(expected).digest()
    if len(staged) == len(expected) and hmac.compare_digest(
        staged_sha256, expected_sha256
    ) and hmac.compare_digest(staged, expected):
        return
    if partial_recoverable and len(staged) < len(expected) and hmac.compare_digest(
        staged, expected[: len(staged)]
    ):
        os.unlink(stage_name, dir_fd=directory)
        os.fsync(directory)
        return
    fail(f"{label} staging file drifted from the expected first-import state")


def write_import_stage(
    directory: int, stage_name: str, payload: bytes, label: str
) -> None:
    reconcile_import_stage(
        directory, stage_name, payload, label, partial_recoverable=True
    )
    if entry_exists(directory, stage_name):
        return
    target_fd = os.open(
        stage_name,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory,
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
    os.fsync(directory)
    reconcile_import_stage(
        directory, stage_name, payload, label, partial_recoverable=False
    )


def publish_private_no_replace(
    directory: int,
    stage_name: str,
    name: str,
    payload: bytes,
    label: str,
    *,
    crash_after_stage: bool = False,
) -> None:
    write_import_stage(directory, stage_name, payload, label)
    if crash_after_stage and CRASH_POINT == "after-stage-write-before-receipt":
        fail("injected crash after import stage write before receipt publication")
    if renameat2(
        directory,
        os.fsencode(stage_name),
        directory,
        os.fsencode(name),
        RENAME_NOREPLACE,
    ) != 0:
        number = ctypes.get_errno()
        if number != errno.EEXIST:
            fail(f"{label} publication failed: {number}")
        current = read_private(directory, name, label)
        if not hmac.compare_digest(current, payload):
            fail(f"{label} publication raced")
        reconcile_import_stage(
            directory, stage_name, payload, label, partial_recoverable=False
        )
        os.unlink(stage_name, dir_fd=directory)
    os.fsync(directory)
    durable = read_private(directory, name, label)
    if not hmac.compare_digest(durable, payload):
        fail(f"{label} is not durable")


gateway_lock_fd = open_private_lock(
    state, LOCK, "gateway deployment state lock", create=True
)
acquire_private_lock(gateway_lock_fd, "gateway deployment state lock")
import_tombstone_present = entry_exists(state, IMPORT_TOMBSTONE)
legacy = optional_old_state()
if legacy is None:
    if any(
        entry_exists(state, name)
        for name in (RECEIPT, IMPORT_STAGE, IMPORT_TOMBSTONE)
    ):
        fail("legacy deployment receipt source is missing after import")
else:
    legacy_lock_fd = open_private_lock(
        legacy, LOCK, "legacy deployment state lock", create=False
    )
    acquire_private_lock(legacy_lock_fd, "legacy deployment state lock")
    if entry_exists(legacy, INTENT):
        fail("legacy deployment state has an active promotion intent")
    if not entry_exists(legacy, RECEIPT):
        if any(
            entry_exists(state, name)
            for name in (RECEIPT, IMPORT_STAGE, IMPORT_TOMBSTONE)
        ):
            fail("legacy deployment receipt source disappeared after import")
    else:
        source = read_private(legacy, RECEIPT, "legacy deployment receipt")
        source_identity = validate_legacy_receipt(source)
        source_sha256 = hashlib.sha256(source).hexdigest()
        expected_tombstone = import_tombstone_bytes(
            LEGACY_RECEIPT_PATH, source_sha256, source_identity
        )
        destination_present = entry_exists(state, RECEIPT)
        import_tombstone_present = entry_exists(state, IMPORT_TOMBSTONE)
        if import_tombstone_present:
            reconcile_import_stage(
                state,
                IMPORT_STAGE,
                expected_tombstone,
                "legacy state import tombstone",
                partial_recoverable=False,
            )
            if entry_exists(state, IMPORT_STAGE):
                publish_private_no_replace(
                    state,
                    IMPORT_STAGE,
                    IMPORT_TOMBSTONE,
                    expected_tombstone,
                    "legacy state import tombstone",
                )
            tombstone = read_private(
                state, IMPORT_TOMBSTONE, "legacy state import tombstone"
            )
            validate_import_tombstone(
                tombstone, LEGACY_RECEIPT_PATH, source, source_identity
            )
            if not destination_present:
                fail("new deployment receipt is missing after legacy state import")
            destination = read_private(state, RECEIPT, "new deployment receipt")
            validate_destination_receipt(destination)
        else:
            expected_stage = expected_tombstone if destination_present else source
            reconcile_import_stage(
                state,
                IMPORT_STAGE,
                expected_stage,
                "legacy state import",
                partial_recoverable=True,
            )
            allowed_entries = {LOCK, IMPORT_STAGE}
            if destination_present:
                allowed_entries.add(RECEIPT)
            if set(os.listdir(state)) - allowed_entries:
                fail("new deployment state is non-empty before one-time receipt import")
            if destination_present:
                destination = read_private(state, RECEIPT, "new deployment receipt")
                if not hmac.compare_digest(source, destination):
                    fail(
                        "new deployment state conflicts with the legacy receipt "
                        "without an import tombstone"
                    )
            else:
                publish_private_no_replace(
                    state,
                    IMPORT_STAGE,
                    RECEIPT,
                    source,
                    "legacy deployment receipt import",
                    crash_after_stage=True,
                )
            imported = read_private(state, RECEIPT, "imported deployment receipt")
            if not hmac.compare_digest(source, imported):
                fail("imported deployment receipt changed before tombstone publication")
            if CRASH_POINT == "after-receipt-before-tombstone":
                fail("injected crash after receipt publication before tombstone")
            publish_private_no_replace(
                state,
                IMPORT_STAGE,
                IMPORT_TOMBSTONE,
                expected_tombstone,
                "legacy state import tombstone",
            )
            validate_import_tombstone(
                read_private(
                    state, IMPORT_TOMBSTONE, "legacy state import tombstone"
                ),
                LEGACY_RECEIPT_PATH,
                source,
                source_identity,
            )
    os.close(legacy_lock_fd)
    os.close(legacy)
os.fsync(state)
os.close(gateway_lock_fd)
os.close(state)
os.close(state_root)
if var_lib is not None:
    os.close(var_lib)
if var is not None:
    os.close(var)
os.close(root)
PY
}

_install_runner_main() {
set -euo pipefail
umask 027
_install_runner_stage=""
_install_runner_archive_tmp=""
_install_runner_gateway_tmp=""
_install_runner_sudoers_tmp=""
_install_runner_unit_tmp=""
local -a gateway_modules=(
  __init__.py
  cli.py
  constants.py
  graph_instructions.py
  intent_io.py
  intent_schema.py
  journal.py
  marketplace.py
  models.py
  process.py
  promotion.py
  publication.py
  receipts.py
  role_deploy.py
  role_io.py
  role_profiles.py
  role_renderer.py
  role_recovery.py
  standalone_roles.py
  state_io.py
  telemetry.py
)
trap _install_runner_cleanup EXIT

[[ $EUID -eq 0 ]] || _install_runner_die "run as ai1 with sudo"
[[ ${SUDO_USER:-} == ai1 ]] || _install_runner_die "the interactive sudo caller must be ai1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
[[ -f "$script_dir/deploy_plugin.py" && ! -L "$script_dir/deploy_plugin.py" ]] || \
  _install_runner_die "deploy_plugin.py must be a regular file beside the installer"
[[ -d "$script_dir/bears_deploy" && ! -L "$script_dir/bears_deploy" ]] || \
  _install_runner_die "bears_deploy must be a regular directory beside the installer"
for module in "${gateway_modules[@]}"; do
  [[ -f "$script_dir/bears_deploy/$module" && ! -L "$script_dir/bears_deploy/$module" ]] || \
    _install_runner_die "gateway module is missing or unsafe: $module"
done

if ! /usr/bin/getent group "$RUNNER_GROUP" >/dev/null; then
  /usr/sbin/groupadd --system "$RUNNER_GROUP"
fi
IFS=: read -r group_name _ runner_gid _ < <(/usr/bin/getent group "$RUNNER_GROUP")
[[ "$group_name" == "$RUNNER_GROUP" && "$runner_gid" =~ ^[0-9]+$ && "$runner_gid" != 0 ]] || \
  _install_runner_die "$RUNNER_GROUP is not a safe dedicated group"
while IFS=: read -r candidate _ candidate_gid _; do
  [[ "$candidate_gid" != "$runner_gid" || "$candidate" == "$RUNNER_GROUP" ]] || \
    _install_runner_die "group id $runner_gid is shared with $candidate"
done < <(/usr/bin/getent group)
while IFS=: read -r candidate _ _ candidate_gid _; do
  [[ "$candidate_gid" != "$runner_gid" || "$candidate" == "$RUNNER_USER" ]] || \
    _install_runner_die "$RUNNER_GROUP is a primary group for $candidate"
done < <(/usr/bin/getent passwd)
if ! /usr/bin/getent passwd "$RUNNER_USER" >/dev/null; then
  /usr/sbin/useradd --system --create-home --home-dir "$RUNNER_HOME" \
    --shell /usr/sbin/nologin --no-user-group --gid "$RUNNER_GROUP" "$RUNNER_USER"
fi
IFS=: read -r _ _ _ _ _ actual_home actual_shell < <(/usr/bin/getent passwd "$RUNNER_USER")
[[ "$actual_home" == "$RUNNER_HOME" && "$actual_shell" == /usr/sbin/nologin ]] || \
  _install_runner_die "$RUNNER_USER must keep the fixed home and no-login shell"
/usr/sbin/usermod --gid "$RUNNER_GROUP" --groups '' "$RUNNER_USER"
IFS=: read -r _ _ _ group_members < <(/usr/bin/getent group "$RUNNER_GROUP")
[[ -z "$group_members" ]] || _install_runner_die "$RUNNER_GROUP must not contain supplementary members"
[[ "$(/usr/bin/id -gn "$RUNNER_USER")" == "$RUNNER_GROUP" ]] || \
  _install_runner_die "$RUNNER_USER primary group must be $RUNNER_GROUP"
[[ "$(/usr/bin/id -G "$RUNNER_USER")" == "$runner_gid" ]] || \
  _install_runner_die "$RUNNER_USER must not have supplementary groups"

# Stop every previously managed service before touching runner or gateway state.
_install_runner_quiesce_managed_service "$SERVICE_NAME" "/sys/fs/cgroup"
/usr/bin/systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
if [[ -e "$RUNNER_DIR/.service" || -L "$RUNNER_DIR/.service" ]]; then
  [[ -f "$RUNNER_DIR/.service" && ! -L "$RUNNER_DIR/.service" ]] || \
    _install_runner_die "legacy service marker is unsafe"
  legacy_service="$(<"$RUNNER_DIR/.service")"
  [[ "$legacy_service" =~ ^actions\.runner\.[A-Za-z0-9_.@-]+\.service$ ]] || \
    _install_runner_die "legacy service name is unsafe"
  _install_runner_quiesce_managed_service "$legacy_service" "/sys/fs/cgroup"
  /usr/bin/systemctl disable "$legacy_service" >/dev/null 2>&1 || true
  /usr/bin/rm -f -- "/etc/systemd/system/$legacy_service"
fi
if /usr/bin/pgrep -u "$RUNNER_USER" >/dev/null; then
  /usr/bin/pkill -KILL -u "$RUNNER_USER" || true
fi
/usr/bin/pgrep -u "$RUNNER_USER" >/dev/null && _install_runner_die "$RUNNER_USER still has running processes"

# Provision the gateway-owned state boundary and import only the old deployment receipt.
IFS=: read -r _ _ ai1_uid ai1_gid _ _ _ < <(/usr/bin/getent passwd ai1)
[[ "$ai1_uid" =~ ^[0-9]+$ && "$ai1_uid" != 0 && "$ai1_gid" =~ ^[0-9]+$ ]] || \
  _install_runner_die "ai1 must have a fixed non-root uid and numeric gid"
_install_runner_import_deployment_state \
  "$ai1_uid" "$ai1_gid" "$DEPLOY_STATE_ROOT" "$DEPLOY_STATE_DIR" \
  "$LEGACY_DEPLOY_STATE_DIR" live "" ""

/usr/bin/install -d -o root -g root -m 0755 "$(dirname "$ARCHIVE")"
if [[ -f "$ARCHIVE" ]] && ! printf '%s  %s\n' "$RUNNER_SHA256" "$ARCHIVE" | /usr/bin/sha256sum --check --status; then
  /usr/bin/rm -f "$ARCHIVE"
fi
if [[ ! -f "$ARCHIVE" ]]; then
  _install_runner_archive_tmp="$(/usr/bin/mktemp "${ARCHIVE}.XXXXXX")"
  /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 --output "$_install_runner_archive_tmp" "$ARCHIVE_URL"
  printf '%s  %s\n' "$RUNNER_SHA256" "$_install_runner_archive_tmp" | /usr/bin/sha256sum --check --status || \
    _install_runner_die "runner archive checksum mismatch"
  /usr/bin/install -o root -g root -m 0644 "$_install_runner_archive_tmp" "$ARCHIVE"
  /usr/bin/rm -f "$_install_runner_archive_tmp"
  _install_runner_archive_tmp=""
fi
printf '%s  %s\n' "$RUNNER_SHA256" "$ARCHIVE" | /usr/bin/sha256sum --check --status || \
  _install_runner_die "cached runner archive checksum mismatch"

# Configure only in a disposable runner-owned stage; root never executes its files.
_install_runner_stage="$(/usr/bin/mktemp -d /var/tmp/bears-plugin-runner.XXXXXX)"
/usr/bin/tar --extract --gzip --file "$ARCHIVE" --directory "$_install_runner_stage" --no-same-owner
/usr/bin/chown -R "$RUNNER_USER:$RUNNER_GROUP" "$_install_runner_stage"
token="$(/usr/sbin/runuser -u ai1 -- env HOME=/home/ai1 GH_PROMPT_DISABLED=1 \
  /home/ai1/.local/bin/gh api --method POST "repos/${REPOSITORY}/actions/runners/registration-token" --jq .token)"
[[ -n "$token" ]] || _install_runner_die "GitHub did not return a repository registration token"
runner_name="bears-plugin-cd-$(/usr/bin/hostname --short | /usr/bin/tr -cd 'A-Za-z0-9._-')"
/usr/sbin/runuser -u "$RUNNER_USER" -- env HOME="$RUNNER_HOME" \
  "$_install_runner_stage/config.sh" --unattended --replace --disableupdate \
  --url "$REPOSITORY_URL" --token "$token" --name "$runner_name" \
  --labels "$RUNNER_LABEL" --work _work
unset token
/usr/bin/chown -R root:root "$_install_runner_stage"
for credential in .runner .credentials .credentials_rsaparams; do
  [[ -f "$_install_runner_stage/$credential" && ! -L "$_install_runner_stage/$credential" ]] || \
    _install_runner_die "runner configuration did not create safe $credential"
done

# Re-extract verified code into the final root-owned tree; copy only data files.
/usr/bin/rm -rf "$RUNNER_DIR"
/usr/bin/install -d -o root -g root -m 0755 "$RUNNER_DIR"
/usr/bin/tar --extract --gzip --file "$ARCHIVE" --directory "$RUNNER_DIR" --no-same-owner
/usr/bin/chown -R root:root "$RUNNER_DIR"
/usr/bin/chmod -R go-w "$RUNNER_DIR"
[[ -f "$RUNNER_DIR/bin/runsvc.sh" && ! -L "$RUNNER_DIR/bin/runsvc.sh" && \
  -x "$RUNNER_DIR/bin/runsvc.sh" ]] || _install_runner_die "runner service wrapper is unsafe"
[[ "$(/usr/bin/stat -c '%U:%G' "$RUNNER_DIR/bin/runsvc.sh")" == root:root ]] || \
  _install_runner_die "runner service wrapper is not root-owned"
/usr/bin/install -o root -g root -m 0755 \
  "$RUNNER_DIR/bin/runsvc.sh" "$RUNNER_DIR/runsvc.sh"
/usr/bin/install -o root -g root -m 0644 "$_install_runner_stage/.runner" "$RUNNER_DIR/.runner"
/usr/bin/install -o "$RUNNER_USER" -g "$RUNNER_GROUP" -m 0600 \
  "$_install_runner_stage/.credentials" "$RUNNER_DIR/.credentials"
/usr/bin/install -o "$RUNNER_USER" -g "$RUNNER_GROUP" -m 0600 \
  "$_install_runner_stage/.credentials_rsaparams" "$RUNNER_DIR/.credentials_rsaparams"
/usr/bin/install -d -o "$RUNNER_USER" -g "$RUNNER_GROUP" -m 0700 \
  "$RUNNER_DIR/_work" "$RUNNER_DIR/_diag"
printf '%s\n' "$RUNNER_VERSION" >"$RUNNER_DIR/.bears-version"
/usr/bin/chown root:root "$RUNNER_DIR/.bears-version"
/usr/bin/chmod 0644 "$RUNNER_DIR/.bears-version"
/usr/bin/install -d -o root -g "$RUNNER_GROUP" -m 0750 "$RUNNER_HOME"

# Install and validate the root-owned gateway package and sole sudo authorization.
_install_runner_gateway_tmp="$(/usr/bin/mktemp -d "${DEPLOY_PACKAGE_ROOT}.XXXXXX")"
/usr/bin/chown root:root "$_install_runner_gateway_tmp"
/usr/bin/chmod 0755 "$_install_runner_gateway_tmp"
/usr/bin/install -d -o root -g root -m 0755 "$_install_runner_gateway_tmp/bears_deploy"
for module in "${gateway_modules[@]}"; do
  /usr/bin/install -o root -g root -m 0644 \
    "$script_dir/bears_deploy/$module" "$_install_runner_gateway_tmp/bears_deploy/$module"
done
/usr/bin/rm -rf -- "$DEPLOY_PACKAGE_ROOT"
/usr/bin/mv -- "$_install_runner_gateway_tmp" "$DEPLOY_PACKAGE_ROOT"
_install_runner_gateway_tmp=""
[[ "$(/usr/bin/stat -c '%U:%G:%a' "$DEPLOY_PACKAGE_ROOT")" == root:root:755 ]] || \
  _install_runner_die "deployment package root is not immutable"
for module in "${gateway_modules[@]}"; do
  [[ "$(/usr/bin/stat -c '%U:%G:%a' "$DEPLOY_PACKAGE_ROOT/bears_deploy/$module")" == root:root:644 ]] || \
    _install_runner_die "deployment package module is not immutable: $module"
done
/usr/bin/install -o root -g root -m 0755 "$script_dir/deploy_plugin.py" "$DEPLOY_COMMAND"
[[ "$(/usr/bin/stat -c '%U:%G:%a' "$DEPLOY_COMMAND")" == root:root:755 ]] || \
  _install_runner_die "deployment gateway ownership is not immutable"
_install_runner_sudoers_tmp="$(/usr/bin/mktemp /etc/sudoers.d/bears-plugin-runner-deploy.XXXXXX)"
printf '%s ALL=(ai1) NOPASSWD: %s ^[0-9a-f]{40}$\n' "$RUNNER_USER" "$DEPLOY_COMMAND" >"$_install_runner_sudoers_tmp"
/usr/bin/chmod 0440 "$_install_runner_sudoers_tmp"
/usr/sbin/visudo -cf "$_install_runner_sudoers_tmp" >/dev/null
/usr/bin/install -o root -g root -m 0440 "$_install_runner_sudoers_tmp" "$SUDOERS_FILE"
/usr/bin/rm -f "$_install_runner_sudoers_tmp"
_install_runner_sudoers_tmp=""

# The runner must not inherit operator groups or read operator credential state.
for protected_root in /home/ai1 /srv/bears/codex/ai1; do
  [[ -d "$protected_root" ]] || _install_runner_die "protected operator path is missing: $protected_root"
  for access_mode in -r -x; do
    if /usr/sbin/runuser -u "$RUNNER_USER" -- /usr/bin/test "$access_mode" "$protected_root"; then
      _install_runner_die "$RUNNER_USER can read or traverse protected operator path: $protected_root"
    fi
  done
done
for sensitive in \
  /home/ai1/.config/gh/hosts.yml \
  /srv/bears/codex/ai1/auth.json \
  /srv/bears/codex/ai1/config.toml; do
  if /usr/sbin/runuser -u "$RUNNER_USER" -- /usr/bin/test -r "$sensitive"; then
    _install_runner_die "$RUNNER_USER can read sensitive operator state: $sensitive"
  fi
done

# Use a fixed root-owned unit; the service executes official code only as the runner.
_install_runner_unit_tmp="$(/usr/bin/mktemp /etc/systemd/system/bears-plugin-runner.XXXXXX)"
cat >"$_install_runner_unit_tmp" <<EOF
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
KillMode=control-group
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
/usr/bin/install -o root -g root -m 0644 "$_install_runner_unit_tmp" "$SERVICE_FILE"
/usr/bin/rm -f "$_install_runner_unit_tmp"
_install_runner_unit_tmp=""
/usr/bin/systemctl daemon-reload

# Activation is deliberately the final step; every prerequisite is already complete.
_install_runner_cleanup
trap - EXIT
exec /usr/bin/systemctl enable --now "$SERVICE_NAME"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  _install_runner_main "$@"
fi
