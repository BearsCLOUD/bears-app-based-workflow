#!/usr/bin/env bash
# Install only the immutable local materializer; do not provision or read a DSN.

set -euo pipefail
umask 027

readonly TARGET=/usr/local/sbin/materialize-bears-app-workflow-sentry-dsn

die() { printf 'install-sentry-materializer: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "requires a separately authorized root operator step"
[[ ${SUDO_USER:-} == ai1 ]] || die "the authorized operator must be ai1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source_file="$script_dir/materialize_sentry_dsn.py"
[[ -f "$source_file" && ! -L "$source_file" ]] || die "materializer source is unsafe"

/usr/bin/install -o root -g root -m 0755 "$source_file" "$TARGET"
[[ "$(/usr/bin/stat -c '%U:%G:%a' "$TARGET")" == root:root:755 ]] || \
  die "installed materializer boundary is unsafe"
