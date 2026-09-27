#!/usr/bin/env bash
set -euo pipefail
# A separate checkout contains data only; never execute files from this branch.
root="$(git rev-parse --show-toplevel)"
target="$root/data/remote-state"
mkdir -p "$target" "$root/data/state"
git init -q "$target"
git -C "$target" remote add origin "$(git remote get-url origin)"
# checkout@v4 stores a scoped extraheader in the trusted checkout's local config.
# Copy it without printing it; do not put credentials in the remote URL.
auth_header="$(git config --get http.https://github.com/.extraheader || true)"
if [ -n "$auth_header" ]; then
  git -C "$target" config http.https://github.com/.extraheader "$auth_header"
fi
unset auth_header
git -C "$target" config user.name 'github-actions[bot]'
git -C "$target" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
remote_ref="$(git -C "$target" ls-remote --heads origin data-state)"
if [ -n "$remote_ref" ]; then
  git -C "$target" fetch -q --depth=1 origin data-state
  git -C "$target" checkout -q -B data-state FETCH_HEAD
  find "$target" -maxdepth 1 -name '*.json' -exec cp '{}' "$root/data/state/" \;
else
  git -C "$target" checkout -q --orphan data-state
fi
