+++
title = "Removing Reveal, Conflict, and contract total copies, and repairing the problem-suite check"
description = "Card text, the action list, and contract checks now read ability records directly, finishing the composed-effects switch through stage B; the problem-suite check stopped at v150 was fixed."
date = 2026-10-21T10:10:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-21"
source_ref = "c8f61677"
sources = ["docs/worklog/2026-10.md", "docs/development-handoff.md"]
+++
## The same information in two forms

After [stage B]({{< relref path="devlog/2026-10-20-action-units.md" lang="en" >}}), reward payout read the ability records. Card text, the action list (codec), contract completion checks, the problem-suite detectors, and the app-AI data scripts still read total copies built from those records: Reveal gains, Conflict rewards, and contract conditions and rewards. Keeping one effect in two forms allows one side to be changed without the other.

## Changes

- **Reveal:** card text and the action list read a card's Reveal record lines. The totals type and its field in the card definitions were removed. The checks done when building totals (unknown conditions or rewards, the same gain twice on one line, and so on) now run on all 51 Reveal records at import. Previously only records that were built into totals were checked.
- **Conflict and contracts:** definitions hold the record itself, and rule questions (the required space, harvested spice, alliance gain, immediate completion, and so on) are answered from the record. Five totals types and two converters were removed.

Because this cleanup must not change behavior, it was accepted only if these outputs were byte-identical to the starting commit: English and Korean text for 140 cards, the full browser card tables, the action list for 144 option combinations, the AI input feature digest, and the app-AI data script outputs.

## Verification

Both batches ran the full engine sub-stage checks: 8,198 pytest tests with ruff and mypy, the same 200 games on the old and new engines, 200 heuristic and app-AI games replayed, 900 random and heuristic games (no failures), 2,000 v150 records replayed (all identical), 8 human save files (no divergence), problem-suite re-mining (111 positions identical), and 68 browser E2E scripts. Only the way display text and the action list read their data changed, so the diff was reviewed directly instead of by an independent review agent.

## Problem-suite check repair

A problem suite collects positions from human or AI games where two moves are compared. The check rebuilds each position on the current engine and confirms both moves are legal. During the checks above this command was found to stop at codec v150. It did the same on the starting commit, so the cause was stage B, not this cleanup. There were two causes.

- When one move expanded into several steps and the other was an Agent placement, the problem was asked at the position of the last step, where choosing a card was not possible. It is now asked before the first step where the two moves part.
- When the answer was a decline action removed in v149, the move could not be expanded into steps and raised an exception. Such moves are now asked unexpanded and reported, as in v149, as "the answer is not legal".

After the repair, 279 of 285 human-game problems (the same set as v149) and all 3 AI-mistake problems can be asked. The remaining 6 have a decline as the answer with no counterpart in the current engine, and could not be asked in v149 either. Only the records tooling changed; the engine, codec, and save format did not.

## Remaining points

The composed-effects plan is finished through stage B. Its remaining stage C adds Rise of Ix, base-game Imperium, and Conspiracy cards as ability records. Retraining for the new action units did not replace the play model in its [first attempt]({{< relref path="devlog/2026-10-21-retrain-teacher.md" lang="en" >}}).

## References

- [Merge reveal-totals: read a card's Reveal gains from its record everywhere](https://github.com/jungcheolseung/Dune-Imperium/commit/0425224a)
- [Merge problem-checks: the problem-suite checks run again at codec v150](https://github.com/jungcheolseung/Dune-Imperium/commit/c9a087a7)
- [Merge reward-totals: Conflict rewards and Contract terms read from their records](https://github.com/jungcheolseung/Dune-Imperium/commit/c8f61677)
- [docs/worklog/2026-10.md](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/worklog/2026-10.md)
- [development-handoff.md](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/development-handoff.md)
