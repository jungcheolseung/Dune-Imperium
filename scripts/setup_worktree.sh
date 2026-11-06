#!/usr/bin/env bash
# Make a new worktree of this repository ready to work in (AGENTS.md "Worktrees"):
# the git-ignored `assets` link to the private assets checkout, then the Python
# environment with every extra. Orca runs it from orca.yaml in the new worktree;
# any tool may run it from a worktree's root. Running it again is harmless.
set -euo pipefail

cd "${ORCA_WORKTREE_PATH:-$PWD}"
# A GUI app's environment may lack the user's shell PATH.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

main="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"

# The main checkout links assets relatively (../Dune-Imperium-assets), which
# does not resolve from a nested worktree, so link the resolved absolute path.
if [ "$PWD" != "$main" ] && [ ! -e assets ] && [ ! -L assets ]; then
  if target="$(cd "$main/assets" 2>/dev/null && pwd -P)"; then
    ln -s "$target" assets
    echo "assets -> $target"
  else
    echo "no assets checkout behind $main/assets; tests that need it will skip" >&2
  fi
fi

uv sync --extra rl --extra ui --extra train
