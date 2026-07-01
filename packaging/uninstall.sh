#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

prefix=${PREFIX:-/usr/local}
destdir=${DESTDIR:-}
systemd_user_unit_dir=${SYSTEMD_USER_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}

bin_path=$destdir$prefix/bin/knowledge-orchestrator
unit_path=$destdir$systemd_user_unit_dir/knowledge-orchestrator.service

rm -f -- "$bin_path" "$unit_path"
