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
ReadWritePaths=$RUNNER_DIR/_work $RUNNER_DIR/_diag $RUNNER_DIR/.credentials $RUNNER_DIR/.credentials_rsaparams /srv/bears/codex/ai1
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
