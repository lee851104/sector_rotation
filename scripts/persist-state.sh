#!/usr/bin/env bash
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
target="$root/data/remote-state"
test -d "$target/.git"
# Do not copy secrets, staging files or arbitrary source files into the data branch.
for name in budget batch status universe smoke dashboard deployment project; do
  if [ -f "$root/data/state/$name.json" ]; then
    cp "$root/data/state/$name.json" "$target/$name.json"
  fi
done
git -C "$target" add -- '*.json'
if ! git -C "$target" diff --cached --quiet; then
  git -C "$target" commit -qm 'data: checkpoint daily update'
  git -C "$target" push -q origin HEAD:data-state
fi
