#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

prefix=${PREFIX:-/usr/local}
destdir=${DESTDIR:-}
systemd_user_unit_dir=${SYSTEMD_USER_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}

bin_src=$repo_root/packaging/bin/knowledge-orchestrator
unit_src=$repo_root/packaging/systemd/knowledge-orchestrator.service

bin_dir=$destdir$prefix/bin
unit_dir=$destdir$systemd_user_unit_dir

mkdir -p "$bin_dir" "$unit_dir"
cp "$bin_src" "$bin_dir/knowledge-orchestrator"
cp "$unit_src" "$unit_dir/knowledge-orchestrator.service"
chmod 755 "$bin_dir/knowledge-orchestrator"
chmod 644 "$unit_dir/knowledge-orchestrator.service"
