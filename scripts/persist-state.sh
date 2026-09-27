#!/usr/bin/env bash
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
target="$root/data/remote-state"
test -d "$target/.git"
# Do not copy secrets, staging files or arbitrary source files into the data branch.
files=()
for name in budget batch status universe smoke dashboard deployment project; do
  if [ -f "$root/data/state/$name.json" ]; then
    cp "$root/data/state/$name.json" "$target/$name.json"
    files+=("$name.json")
  fi
done
if [ "${#files[@]}" -eq 0 ]; then exit 0; fi
git -C "$target" add -- "${files[@]}"
if ! git -C "$target" diff --cached --quiet; then
  git -C "$target" commit -qm 'data: checkpoint daily update'
  git -C "$target" push -q origin HEAD:data-state
fi
