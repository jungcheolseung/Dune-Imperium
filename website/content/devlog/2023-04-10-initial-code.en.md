+++
title = "The 2023 early attempt and the pause"
description = "State classes, starting cards, and a Poetry setup written in March and April 2023. This code is a separate early attempt, not the base of the 2026 engine."
date = 2023-04-10T01:54:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2023-03-24"
retrospective = true
source_ref = "c8f61677"
sources = ["dune/status.py", "dune/cards.py", "pyproject.toml", "docs/implementation-plan.md"]
+++

## The first code that survives

The first commits date from March 24, 2023. Within a day the repository got a `.gitignore` and `status.py` (111 lines), which defines data classes for game state. On April 1 the `PlayerState` and `GameState` classes were split out inside that same file, and `cards.py` (59 lines) with the starting cards was added. The split was between classes in one file, not into two files.

On April 10 both files moved into a `dune` package, with a Poetry configuration and an empty `tests` folder. That `pyproject.toml` named Python ^3.11 and mypy, pycodestyle, and pylint as development tools. There are five commits in total, and this day is the last one.

## It is not the starting point of the 2026 engine

This code was a separate early attempt, not the origin of the current project. Work stopped after that day for more than three years, until August 12, 2026. When it restarted, the implementation plan said:

- The old `dune/` code is kept only as reference, with no requirement to stay compatible with the new structure.
- The distribution package is renamed from the collision-prone `dune` to `dune_imperium`.
- The old `dune/status.py` and `dune/cards.py` are not imported by new code.

Nothing in `src`, `tests`, or `scripts` imports the `dune` package today. The only use is `cards.py` inside the `dune` folder importing `dune.status`. The folder is still in the repository, but the 2026 engine started over in a new package, `src/dune_imperium`. The first commit of August 12 also moved the toolchain from Poetry to Python 3.14 and uv.

## What this stage could do

These commits could not run a game or check any rule. They only sketched the shape of the state and the starting cards, and there were no tests. The real Uprising implementation begins with [the first August 2026 entry]({{< relref path="devlog/2026-08-14-engine-foundation.md" lang="en" >}}).

## References

- [Add PlayerState and GameState](https://github.com/jungcheolseung/Dune-Imperium/commit/252b866c)
- [Add starting cards](https://github.com/jungcheolseung/Dune-Imperium/commit/e4c55ebc)
- [Initialize the Python package and Poetry](https://github.com/jungcheolseung/Dune-Imperium/commit/2df8c995)
- [Migrate to Python 3.14 and uv](https://github.com/jungcheolseung/Dune-Imperium/commit/e2d7f9b4)
- [Implementation plan for the new engine (M0 covers how `dune/` is treated)](https://github.com/jungcheolseung/Dune-Imperium/blob/a6f1449a/docs/implementation-plan.md)
