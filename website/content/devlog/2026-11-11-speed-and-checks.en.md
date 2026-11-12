+++
title = "A faster search AI, and faster checks without weakening them"
description = "Search playouts now read the model in batches, and a fourth engine round cut the time per search decision a good deal. The same tests now run the full pytest 21% faster, and browser checks that broke under load wait for real end conditions."
date = 2026-11-11T23:30:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-10"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/search-ai.md", "docs/evaluation/2026-11-engine-speed.md", "scripts/e2e/README.md", "docs/worklog/2026-11.md"]
+++

## Background

On the play server PC (a Celeron mini PC) the search AI's turns are long, and longer since Agent turns got 16 worlds. Saved time can do the same search sooner, or look further in the same time. Meanwhile the full pytest and the browser E2E that run at every engine gate and merge were long, and under load a few E2E scripts timed out and had to be rerun every time.

## Batched model reads in playouts (merge `2067caab`, November 10)

For each decision the search plays dozens of playouts (worlds × candidates) and read the model once per playout step. Now the playouts of one stage advance side by side, one step at a time, and at each step the model is read once for all of them in a batch (the same observation only once).

- **Do moves change.** With batching off, every move and search result is bit-for-bit the same as master. Comparing on and off at the same decisions, 0 of 1,093 search decisions chose differently, and playout values differed by at most 2e-6. Since decisions did not change, only speed was measured, as the rule says, and by the user's decision no strength match was played.
- **Time.** On a quiet machine with 4 threads, a search decision went from 1.28 to 0.88 seconds (ratio 0.684 [0.675, 0.690]) and an Agent turn from 3.02 to 2.02 seconds. Restricted to efficiency cores to imitate a slow host, 6.50 to 3.74 seconds (0.575). The model's share of the time fell from 38% to 14%, so most of what is left is the engine.
- The user: "Isn't including this simply better? Then shouldn't it just go in as the default?" So it is on by default, and `::batch=off` takes the old path. The play servers change at their next code sync.

## Engine round 4 (merge `a47fd570`, November 11)

Measuring a game with one E3 search seat and three app AIs showed the engine taking 71–72% of the seat's time, spread out rather than concentrated in one place. Under the same condition as [the earlier three rounds]({{< relref path="devlog/2026-11-03-engine-speed.md" lang="en" >}}) — change nothing that can be seen — four engine stages (remembering answers to repeated questions, checking only changed fields, ending idle hooks early, building the public seat view) and the search seat's memo keys were changed.

| Measurement (quiet window, three ABBA pairs) | Before → after | Ratio |
| --- | --- | --- |
| Per search decision, Uprising | 0.818 → 0.702 s | ×0.859 [0.854–0.862] |
| Per search decision, original game | 0.651 → 0.568 s | ×0.872 [0.871–0.873] |
| Legal action list | | standard ×0.862, expansions ×0.871 |
| App AI games | | ×0.96–0.97 |

The full engine gate ran at every stage: identity of 360 games, encodings, catalogs, soak, 2,000 recorded games and saves were all the same, and on 9 games the chosen moves and search values matched master. The findings from six review rounds by another tool (Codex) were all inputs that can arise only inside the process, and they were fixed. This work used five gates (about 6 CPU hours), after which the user changed the gate rules: a sub-stage whose results stay the same needs only the quick gate (pytest, ruff, mypy, identity, encodings), the full gate runs once on the merge candidate, and if engine events, legal lists, the server and the screen are unchanged, E2E runs once at the merge.

## The full pytest faster without weakening it (merge `4cc6b2c6`)

The cause was collection. This development environment sets a variable on every command that turns off bytecode writing, so pytest's assertion-rewrite cache never got written. Each of the eight `-n 8` workers therefore rewrote all 443 test modules on every run (about 14 seconds per worker).

- The controller rewrites them once per run, in parallel, writes them where pytest looks, and deletes them when the run ends. No cache is left behind, so no stale-cache problem arises.
- Creating a new worktree compiles the installed packages to bytecode (about 2 seconds).
- Three places that replayed the same seeded game for every test now play it once.

`-n 8` went from 170.5 to 134.4 seconds (−21%), `-n 4` from 211.0 to 179.8 seconds, and collection alone from 33.9 to 9.7 seconds. The test IDs are the same as master (only 2 new tests added), and the tests that use the caches caught all three deliberately broken pieces of code. Dropping heavy tests from the default run would be faster still, but the quick gate would lose those checks, so the user decided against it.

## Four E2E scripts that broke under load (merge `6816ef72`)

With `pytest -n 8` running alongside, each unfixed script was run five times to reproduce the failures.

- `vp_ledger`: the log line's highlight switches off after 2.5 seconds, and under load the picture responses arrived later than that, so the check looked after it had switched off. It now stops the page clock and waits until "every requested picture has answered".
- `table_motion`: a real screen defect. Under load a cube's box was measured 0 wide and the slide was skipped. It now slides from the old level's printed spot on the board.
- `spectate`, `scouts_stage`: fixed waits became waits until movement stops.

After the fix, under the same conditions, table_motion went from 3/5 to 5/5 and vp_ledger from 4/5 to 5/5, and E2E passed 87/87 on the tree that merged the three branches.

## What is left

- The effect of batching and engine round 4 has not been measured on the Celeron PC yet (an estimate for batching alone is 0.6–0.75 times).
- Spending the saved time on more worlds (for example 24 worlds on Agent turns) changes moves, so it needs its own measurement.
- On a slow real connection, if pictures arrive later than 2.5 seconds the log line is pushed out of view (kept as product behavior).

## References

- Batched playouts ·
  Engine round 4 ·
  pytest speed ·
  E2E stability
- Search AI description ·
  Engine speed measurement record ·
  [E2E guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/scripts/e2e/README.md) ·
  Work log, November
