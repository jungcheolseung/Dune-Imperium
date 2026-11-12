+++
title = "A search AI for the original game: two defects found while retraining, and the verdict"
description = "While retraining the search AI for 800 iterations on the original game + Rise of Ix, we found and fixed two engine defects. Judged again, the search AI won 54.0% against three app AI Hard seats, and the original game got a search AI seat."
date = 2026-11-08T21:30:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-07"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/worklog/2026-11.md", "docs/rules/open-questions.md", "docs/search-ai.md", "docs/development-handoff.md"]
+++

## Background

[The November 2 entry]({{< relref path="devlog/2026-11-02-original-game-and-ix.md" lang="en" >}}) added the original Dune: Imperium and Rise of Ix to the engine, but the search AI's model had learned only from Uprising games. Seated in an original game, the Uprising model (E3) knew only 132 of the 1,707 action templates and finished last against three app AI Hard seats. On November 7 the user chose the overnight training run: "original-game readapt / 800 iterations / original + Ix only" — start from E3 and train again on original game + Rise of Ix games with the leader draft.

## Two defects found where training stopped

**1. An immediate draw offered as a whole action (merge `0bf65b7f`, codec v166).** Training stopped at iteration 32 on a move the codec did not have. In Rise of Ix's Shipping reward window, when Influence reaches the Bene Gesserit bonus space an immediate Intrigue draw arises (OQ-106), but that window is not a step window, so the draw came out as a whole action that no catalog contains. Five of 2,000 original + Ix app AI games hit it. Now a window with an immediate draw waiting is also treated as a step window, so the draw is a step row everywhere. The rule is unchanged; only the shape of the action changed. Old records are moved by a bridge. The tournament and training commands also gained `--base-game imperium` and `--rise-of-ix` (merge `228e1f24`).

**2. Another effect slipping into an Agent box part way (merge `933b347d`, codec v167).** The restarted training died at iterations 276 and 567. After Tessia Vernius's Duplicity had lost Influence but before gaining it, a Plot Intrigue took the last Snooper token, so no Faction was left to gain. In Uprising, too, another effect could be slipped in while a box was part way. The user set the scope to "every intermediate step" (OQ-167), and a designer's answer on BGG that the user brought the same day ("You can't mix the ability's effects with other effects on that turn.") points the same way. Now, while an Agent box is part way, only that box's rows and effects already waiting are offered. A Duplicity whose reward target has vanished ends with a confirmation row. Card effects can still be slipped in between the icons of a board space (the user did not widen the ruling).

Because this changes recorded moves, 16 of 24 saves replayed as they were, and 8 (five unfinished games) were cut just before the move that played another effect while a box was part way. The originals were kept.

## Retraining and the verdict

Training finished its 800 iterations (the deaths at iterations 614 and 742 in between were the same Duplicity defect, and the supervisor script resumed the run). The decision rules were written before the run: one search AI against three app AI Hard seats, four configurations × 200 games. The first verdict stopped on the same defect, and after the fix the whole verdict was run again from the start on the Windows PC (WSL).

| Seat | Before training | After training |
| --- | --- | --- |
| Search AI | 0/200 | **54.0% [47.0, 60.5]** (108/200) |
| Model alone (no search) | 0/200 | 18.5% [12.5, 25.0] |

Equal strength would be 25%. The search AI is stronger than app AI Hard. The learning curve was still rising at iteration 800.

## A search AI seat in original games (merge `08ebf7fb`)

The user decided: "the whole original game, without a measurement", "the original game gets the search AI too".

- Original games also offer a search AI seat. The server looks for the original-game model separately and never seats the Uprising model in an original game. On a server without the original-game model, original games offer no search AI.
- Letting the AI play a person's seat in an original game uses this model too. The setup screen offers the search AI row only when the chosen board has a model.
- A review by another tool (Codex) found that switching boards left a search AI seat on a board without a model; this was fixed.

## Training machine

The same day the Windows PC (WSL) also got a training environment. With the original-game readapt recipe an iteration takes about 18 seconds on the CPU, and about 11 seconds with the training update on that PC's AMD GPU (12.7 seconds on the Mac). It was installed without administrator rights, and the GPU's first-iteration loss matched the CPU to six decimal places.

## What is left

- Which hosts get the original-game model, and whether to train further, are the user's decisions.
- Strength in original games against people was not measured.
- The other immediate-draw path (Irulan) was not tested with a hand-built state.

## References

- Immediate draw as a step row ·
  Original-game training tools ·
  Agent box lock (OQ-167) ·
  Original-game search AI seat
- [Open questions](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/open-questions.md) ·
  Search AI description ·
  Work log, November
