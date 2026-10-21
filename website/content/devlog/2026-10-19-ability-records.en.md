+++
title = "Moving card effects and AI inputs onto shared ability records"
description = "Stages A0 to A8 and a cleanup stage moved card, board, and expansion effects onto ability records and a shared executor, with a before-and-after engine comparison at every stage; the action codec became v149."
date = 2026-10-19T11:59:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-14"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/composed-effects-plan.md", "docs/entity-network-plan.md", "docs/worklog/2026-10.md"]
+++

## Different handling code for every card

Card effects were scattered across per-card handler functions. Even similar effects took different paths, so fixing one rule widened the places to change and check, and the input given to the AI carried nothing about what an effect meant beyond the card's number. As the [entity-network experiment]({{< relref path="devlog/2026-10-14-entity-experiment.md" lang="en" >}}) shows, the network also received no meaning of cards and actions as input, and this work leads into taking those features from the effect records (A8).

There were two conditions: before changing the engine, put the strongest current model into play, and keep the game playable while the engine is being changed. So the play model was replaced first on 14 October, and the whole work was split into stages that change neither actions, observations, nor events but only how effects are represented and executed (A0 to A8), followed by a cleanup stage. Each stage was merged and verified before the next.

## What changed

Effects are written as data, as ability records, and a shared executor reads pending abilities and resolves them.

| Stage | Content | Scale |
| --- | --- | --- |
| A0 | Ability records, action shape table, executor core (not yet connected to the engine) | 124 Intrigue and Navigation options round-trip through records. The action shape table has 279 kinds (45 verbs, 20 sources, 25 targets) |
| A1 | Intrigue choices through the executor; action codec v148 | `rules/intrigue.py` from 2,402 to 1,169 lines; the executor from 633 to 1,658 lines |
| A2, A3 | Agent boxes of personal cards | 44 in A2 (754 lines of handling code removed). A3 extended it to choice payments, required targets, discards, trashes, and chosen acquisitions: all 103 recorded. Per-box flows are named hooks, 20 of them |
| A4 | Acquire, trash, and discard effects; 51 cards with automatic Reveal gains; 26 Reveal choices | Every personal-card effect is a record |
| A5 | 28 contracts, 57 reward lines on 19 Conflict cards, board spaces | |
| A6 | 18 Tech tiles, 18 Signet rings, 21 leader spaces | |
| A7 | 7 Sardaukar Tech tiles, 21 research spaces, Immortality rule changes, 77 Arrakeen Scouts items | Moving to records is complete |

Arrakeen Scouts has no rulebook; the source is the mode of the official companion app. Parts that would be harder to read as data (samples, graft, the shop, track movement, the Scouts schedule and auction machinery) stayed as engine rules.

A cleanup stage followed A7. Cleanup 1 merged duplicate Scouts pieces, and cleanup 2 unified inherited differences. It put event names in one grammar (for example a resource-gain event), removed five declines that were never offered, made copied duplicates read the records directly, and settled six rule judgments. It also made three Agent spaces resolve icon by icon. Hooks outside Scouts went from 62 to 30. The standard for these judgments was this: when settling a rule or an order, go by principle, not by compatibility or sameness of result.

## The check at every stage

The safeguard was a before-and-after engine comparison.

- **Equivalence check.** 200 games are recorded on the old engine and replayed move by move on the new engine, comparing at every step chance decisions, the order of legal actions, the four seats' views, events, and the decision stack minus its identifiers. The 200 games (191,836 steps, 241 kinds of action) were identical at every stage. Also checked: re-recording the same games by the agents gives identical moves down to the last one, and a 2,000-game investigative probe gives byte-identical results. The tool itself was tested: it passes the same engine and catches deliberately mutated legal-action order or event content.
- **Old records.** At each stage, the 2,000-game record bundles of the previous codecs (v148 and v147) replayed on the new engine were all exact.
- **Others.** Unit tests rose from 7,733 (A0) to 8,096 (cleanup-2 merge, excluding two tests that fail only in a separately made copy), and browser E2E scenarios from 67 to 68. The automated soak had 0 failures over 720 or more games, and a speed gate required fixing anything that slowed legal-action computation by more than 10% per call before merging. High-risk stages got an independent review, including a differential probe walking the old and new engines (no blocking findings; low findings were addressed).
- **Speed.** In A1, legal-action computation for Intrigue frames was at first 2.3 times slower, because the executor scanned the 279-row shape table for every line. After caching the lookups, replaying 100 recorded games measured 48.3–48.9 µs per call at the start and 48.5 µs after.

**A defect that led to strengthening the tool.** When Reveal choices were moved in A4, the Spy-offering function emitted the same row twice, so a pending choice's row list had duplicates. The combined legal actions were identical, so the 200-game equivalence check passed. A separately run investigative probe caught it, and afterward the equivalence tool also compares on-screen information and the rows of pending Reveal choices; reintroducing the defect was confirmed to be caught. Before the cleanup stage the tool's recording changed from hashes to content (format 2), and two commands were added: `check --differences`, where declared intentional differences report how many times each rule applied and flag undeclared differences, and `compare`, which compares agents' re-recordings.

## Model inputs and retraining

Network input was changed to build card features from the ability records and action vectors from the action shape table. Because retraining would otherwise be needed again whenever something else changed, entity network files were made to store the feature table's names and to move columns by name when the table changes. Entities whose own features are unchanged give exactly the same output.

Retraining distilled the play model as teacher (1.97 million rows, 95.2% agreement with the teacher), then 800 iterations of reinforcement learning (REINFORCE) at learning rate 1e-5. In a preliminary comparison (700 seeds, 1,400 games) the win-rate difference against the play model was +1.3 points, 95% interval [−3.9, +6.4], within noise, as were rank and score margin: a tie. The search-seat gate was skipped by decision, because the action units were about to change again and the model would be retrained. The play server's model stays the MLP. That MLP was migrated to codec v149 with 36,374 rows kept and 11 new rows starting from zero.

## A rule correction in the same period

It was noticed that Navigation Card 3's +1 persuasion, when gained during a Reveal turn by reaching Influence 2, did not count toward that same Reveal. It raised only the seat's value, which was read only at the start of a Reveal. It now adds to the open Reveal even when gained mid-way (OQ-110, a project ruling); the 2,000-game record bundle was all exact, and 281 of the 285 human-game problem positions resolved. The 4 that did not resolve are positions that depended on decline actions, which no longer exist since v146, and they are the same on master regardless of this fix.

## What remains

- The transition is not finished. The problem of one action carrying too much (a single Agent-turn action bundled card, space, graft, and discount) and the payout of Conflict rewards, contracts, and Reveal gains as per-resource totals were left for the next stage (stage B). What followed is in [Splitting actions into card, space, effect, and target steps]({{< relref path="devlog/2026-10-20-action-units.md" lang="en" >}}) and [Removing Reveal, Conflict, and contract total copies]({{< relref path="devlog/2026-10-21-reward-records.md" lang="en" >}}).
- The action codec at this point is v149. Saved games from earlier codecs do not open in the server.
- The retrained model tied, so the play model was not replaced.

## References

- [Composed-effects plan and stage-by-stage record](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/composed-effects-plan.md)
- [Model input switch and retraining](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/entity-network-plan.md)
- [A0 merge: ability records, action shape table, executor](https://github.com/jungcheolseung/Dune-Imperium/commit/1a5debda)
- [A1 merge: Intrigue choices through the executor (codec v148)](https://github.com/jungcheolseung/Dune-Imperium/commit/7ba624ad)
- [A4 merge: through the Reveal choices](https://github.com/jungcheolseung/Dune-Imperium/commit/bdef8c76)
- [A7 merge: moving to records complete](https://github.com/jungcheolseung/Dune-Imperium/commit/4ca56ffd)
- [Equivalence check tooling merge](https://github.com/jungcheolseung/Dune-Imperium/commit/d892cd6c)
- [Cleanup 2 and A8 merge (codec v149)](https://github.com/jungcheolseung/Dune-Imperium/commit/86086c6d)
