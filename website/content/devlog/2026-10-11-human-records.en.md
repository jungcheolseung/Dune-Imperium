+++
title = "Human-played games as records and a problem set"
description = "Replaying old saved games on the current engine after it changed, a first diagnosis comparing human moves with the AI's choices, the problem set that pins the result, and a record corpus per engine version."
date = 2026-10-12T01:01:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-10"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/human-records.md", "docs/evaluation/human-games-2026-10-10.md", "docs/worklog/2026-10.md"]
+++

## How can games played by people be used?

The question was whether records of human play could be turned into data for training. After the options were laid out, two pieces of work were chosen. One was a diagnosis comparing human moves with the AI's choices. The other was making old saved games survive engine changes. Two things are deliberately not recorded: who played, because it is hard to judge who plays well, and undo history, because a player sometimes undoes a move and then plays the same move again.

## Why old saves break, and migrating records

A saved game writes moves by meaning. An action records its `action_id` and arguments, a chance records its decision id and the drawn value, and the codec row number is not written. So a rise in the codec number does not by itself break a save. What breaks it is a change in the engine's flow. When the new engine asks something the old engine did not, the next recorded move meets the wrong decision. At the start of this work, two of the four local saves (v135 and v139) stalled at the shuffle in round 2, because v140's pause before a reveal had put a chance decision in front of it.

`records.migration` plays the recorded moves in order, and when the engine refuses one it inserts a "bridge", which answers the decision the engine is waiting on the way the old engine answered by not asking. There are bridges per codec threshold: one that answers the pause before a reveal with its outcome, one that declines the Conflict-end window for versions before v141, one that passes in combat Intrigue for versions before v139, and one that names argument-less card-effect actions the way v137 and later do. Two principles hold.

- **A bridge never intervenes on a move that was the answer to the decision.** If a rule change has made such a move illegal, it is not patched over; the replay stops at that point as a `Divergence`.
- **The server's loading stays strict.** An old save cannot be used to continue a game; only the game itself is read. The one thing added to the reading side is an option that turns the version check off.

`dune-imperium-records check` reads and replays one save per game. The result is replayed as is (exact), migrated (with the bridges used and how many times), diverged, or engine error (failed). In the first run, two of the four local games replayed exactly and two were migrated. Whether the migration could be trusted was checked by replaying the same records with old engine sources (v135, v139, v140) and comparing the public state move by move. Apart from the middle of a Conflict reward payout in v135, everything matched. An independent review found two real defects. The first general argument rewriting changed moves in which the missing argument was itself a choice (grafts, discounts), and the safety valve was bypassed when every action of that kind had disappeared. Both were fixed. The record migration merged in the early morning of October 10.

## The first diagnosis: where do people and the AI differ?

The subject was two finished games from October 9, each with two humans and two search AI seats, which the humans won. Of 1,030 human decisions that had more than one option, 796 differed from the first choice of the trained network X. A difference was not treated as the right answer; it was judged by search, by two searches: X's search (32 imagined states) and Y's search (64).

- Both searches judged the human move better in 59 places (24 of them Agent turns, 18 outside X's top five candidates).
- Both judged the network's move better in 53 places.
- Of 442 places that differed only in effect order, 90% showed no difference.

There are places where the human is better and places where the network is better. The diagnosis did not assume the human move to be correct, and it does not prove an overall strength ranking.

## Pinned as a problem set

The 112 places where both searches pointed the same way were pinned as a problem set: 59 `human_right` places where the human is correct, and, as a control, 53 `network_right` places where the network is correct. A mined problem set is re-mined from seeds when the engine changes, but human games cannot be re-mined, so the file holds the two games' records and migrates them to the current engine to revive each position. A position whose record diverges before it, or where one of the two moves has become illegal, is dropped from scoring with a stated reason. The file stays local, because human-played games are not put in the public repository. Defects found by the design review were fixed too: the comparison of the state at judgement time looked only at hand and deck sizes and was widened to all seat fields (83), and four other problems were fixed, such as the pinning stopping after a rewritten move.

The first scoring (codec v141, all 112 revived) is the share of times the correct move was chosen.

| Agent | human_right | network_right |
| --- | ---: | ---: |
| Network X (no search) | 0% | 100% |
| Network Y (no search) | 5% | 79% |
| Search X | 46% | 70% |
| Search Y | 42% | 68% |
| App AI Hard | 37% | 25% |
| Heuristic | 19% | 28% |

The app AI is a rule-based AI ported from the computer opponent of the official digital edition (Steam). The 0% and 100% for network X follow from how the set was built, since "the network's move" was X's first choice. The first judge was X's search, so part of search X's score is circular. The table is the baseline for measuring new checkpoints and is not a training target. A wrong answer is something to investigate.

The problem set changed with rule changes and new games. On the evening of October 10, v142 made the Navigation Chamber discount mandatory, so two `human_right` places where the losing network move paid the list price became illegal, leaving 110. On October 11, the third game, played with friends, added 89 places for 199 (`human_right` 111, `network_right` 88), and the fourth game that night added 86 for 285 (`human_right` 155, `network_right` 130), all revived under v142. The newly added places are scored in full the next time a checkpoint is measured.

## A record corpus per engine version

The trouble was that every time a bridge was fixed, reviewing it meant playing thousands of new games with an old engine. One such review nearly filled the disk. So a record corpus is made once per engine version and picked by index. Index keys are things such as the decision frame, the action offered, and the draws and events, and the state fingerprint is four bytes per field. There is a generator that runs the old engine with it on the PYTHONPATH, and `dune-imperium-records corpus check`, which walks the corpus's records on the current engine.

The v141 corpus is 2,000 games over 6 module combinations × AI combinations, 0 failures, 35 MB, made in about 20 minutes on 3 cores. The point is that it was made before v142 entered master. A sample of 20 games replayed on master with no fingerprint difference over 19,005 moves, and all 2,000 games of the v141 corpus were exact on the v141 engine. `corpus check` sorts outcomes into exact (all equal with no bridge), equal (bridges fired and all equal), transient (differs in the middle and equal again by the end), persistent (the final state differs), diverged (a recorded step was refused that no bridge reached), and failed. Held against the v142 changes (the Imperial Privilege split and others), the 2,000 games gave 6 exact, 639 equal, 1,046 transient, 0 persistent, 309 diverged, and 0 failed, and every diverged game came from a move the new rules made illegal (Navigation Chamber list-price payments in 298 games, for example). Zero persistent means that no game ended in a different state. A v142 corpus of the same plan, 2,000 games, was also made and was all exact on the engine that made it.

The reviews of the two tools found 12 defects (a missed draw in a Reveal turn, games with different seats on the same seed being merged into one, and others) and 13 (classification hiding a defect, a truncated summary, and others), and all were fixed. The checks were 7,074 pytest tests and 54 browser E2E scripts.

## What remains

- The server does not support continuing a game from an old save. Doing so would also require migrating the undo history and the AI's random-number reproduction.
- The guarantee is only that every recorded move is legal on the current engine. When a rule fix changes the outcome of a card, the state after it may differ a little from what the human saw. Only running `check` and the corpus comparison on every flow-changing codec change tells.
- Making training labels from human-game positions with search was postponed while the rules kept changing.
- The same days' feedback fixes to the play screen are in the [launcher, effects and feedback entry]({{< relref path="devlog/2026-10-11-launcher-feedback.md" lang="en" >}}).

## References

- [Record migration design and bridge list](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/human-records.md)
- [Diagnosis of the human games and problem-set scoring](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/human-games-2026-10-10.md)
- [Record migration and first diagnosis merge](https://github.com/jungcheolseung/Dune-Imperium/commit/54d57be7)
- [Human problem set merge](https://github.com/jungcheolseung/Dune-Imperium/commit/f4869e15)
- [Fix to the problem set's state comparison](https://github.com/jungcheolseung/Dune-Imperium/commit/22c9d5c4)
- [Record corpus generation merge](https://github.com/jungcheolseung/Dune-Imperium/commit/a61acb7e)
- [Record corpus check merge](https://github.com/jungcheolseung/Dune-Imperium/commit/062fec1f)
- [v142 record bridges merge](https://github.com/jungcheolseung/Dune-Imperium/commit/64c25384)
- [Dropping the two problems that became void](https://github.com/jungcheolseung/Dune-Imperium/commit/c29f79d1)
