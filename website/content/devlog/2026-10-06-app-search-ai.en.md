+++
title = "Adding the app AI and the search AI as play seats"
description = "A rule-based AI ported from the computer opponent of the official digital edition now answers every decision as a comparison opponent and play seat, and the search AI on top of the trained network became a browser seat."
date = 2026-10-06T08:50:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-05"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/app-ai-2026-10-05.md", "docs/evaluation/app-ai-expansions-2026-10-05.md", "docs/evaluation/m10-2026-10-06.md", "docs/worklog/2026-10.md"]
+++

## A stronger opponent was needed

Until then the comparison opponents were a heuristic AI that scores each kind of action with fixed points, and the trained network. Measuring training results needed a stronger opponent that plays differently, and people playing against an AI in the browser needed a better one too. So a rule-based AI ported from the computer opponent of the official digital edition (Steam) was implemented. This entry calls it the app AI. Every number here measures this project's own implementation.

## Extending the app AI to every option (October 5)

An AI that mixes in heuristic decisions was not something worth playing against anyway, so the app AI was extended to play every option without any heuristic. Besides the leader draft, Immortality, Go to 11, Epic, and the promo cards, it also answers Bloodlines, the Tech module, and Arrakeen Scouts. A decision with no corresponding judgement is answered with a random legal action, and those are counted separately. There are three levels: Hard, Medium, and Easy.

The check was 12 games for each of 16 option combinations, with all four seats being the app AI. Every combination had 0 errors, 0 random substitutions, and 0 unconnected abilities. With the expansions off, the plain game's action sequences on the same 40 seeds were identical before and after the work.

### A/B against the heuristic AI

These are 2:2 mirror matches, and the random expectation per seat is 25%. Leaders rotated per seed and games ran with and without CHOAM. The 95% intervals come from a bootstrap that resamples seed groups.

| Cell | Games | Win rate per seat (app AI / opponent) |
| --- | ---: | --- |
| Hard vs heuristic, seeds 0–499 | 2,000 | 46.5% / 3.5% |
| Same cell, seeds 500–999 | 2,000 | 46.2% / 3.8% |
| Hard vs Medium | 2,000 | 28.4% / 21.6% |
| Hard vs Easy | 2,000 | 36.7% / 13.3% |

With each option switched on in turn (250 seeds, with and without CHOAM, 1,000 games per cell), Hard against the heuristic was 45.8–47.5% to 2.5–4.2% per seat. Bloodlines plus Tech gave 46.7% to 3.3%, Scouts 46.5% to 3.5%, and everything on 47.2% to 2.8%. With everything on, Hard against Easy was 34.0% to 15.9%. The tournament tool with the leader draft on (1,000 games) gave 46.6% to 3.4% (win-rate difference +86.6 points, 95% interval [+83.6, +89.4]). The levels ordered as Hard, Medium, Easy, and the heuristic AI was much weaker.

In the same comparison the trained network lost to Hard when playing without search (the baseline of the time, 7081, 13.5% against 36.5% per seat over 1,000 2:2 games). That network had been trained on the rules from before the End turn change and the later rule corrections, so part of that loss comes from rules that no longer apply. The same network with search on top won 48.5% per seat alone against three Hard seats (400 games).

### Seats in the play screen

The new-game screen now lists app AI Hard, Medium, and Easy. The local server's default AI seat changed from the heuristic to app AI Hard, while remote rooms still seat four humans. If an app AI window throws or picks an illegal action, the game does not stall: it answers with a random legal action and records that. Two pieces of module-level state that could mix between concurrent games were removed. There is a limit: if the app AI's code or data changes, a save with an app AI seat may not replay as recorded and may fail to open.

## The search AI as a browser seat (October 6)

The search AI takes the candidates the trained network picks and plays each one out in several possible hidden states to compare them (the method is in the [technical article]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}})). When the server starts with a network file, the browser's seat list offers the search AI. If the file or torch is missing, the server starts without that seat and says so in one line.

- **Thinking in the background.** Search is slow, so only the search seats are answered by a per-game worker thread. The request returns at once and the seat shows "thinking…". The answer is applied only if the state is unchanged when the work finishes, and undo is blocked while it thinks. If the search raises an exception, the seat answers with the network's own move and logs a warning; the save of that game then no longer guarantees the same continuation from that step.
- **Not searching again when a save reopens.** Following the recorded answer, only the random numbers and the loop-avoidance record move exactly as the search would, and the code checks only that the answer is among the network's candidates. With the real network and the play screen's default rules, reopening a one-round save went from 10.67 s to 0.33 s, and a three-round save from 17.9 s to 0.49 s. The refactor left ordinary search choices and random numbers unchanged bit for bit, which the review confirmed.
- **Speed.** With the play screen's default rules, one search decision took 1.4 s on average (90th percentile 3.3 s, maximum 7.3 s). In a game with one search seat the AI spent about 134 s in total.

An independent review found five issues, including a failed worker step that stalled the game, and all were fixed. The checks at this stage were 6,472 pytest tests, 46 browser E2E scripts (including 61 checks for search seats and 63 for app AI seats), and 18 server tests.

## Retraining on the full rule set: L3

Network 7081 had learned CHOAM, the promo cards, Bloodlines, Tech, and Immortality with four fixed leaders, and had never seen the leader draft, Epic, Go to 11, or Scouts. It was trained for 1,000 more iterations on the play screen's whole rule set (draft, CHOAM, promo, Bloodlines, Tech, Immortality, Go to 11, Epic, Scouts). Each collection round is 32 games: 16 with two learner seats against two app AI Hard seats, and 16 self-play. The machine was a Mac mini (M4, 16 GB), and training took about 4 h 20 min (4 h 36 min including the time lost to a stopped attempt).

The judging rules were written before the results, and seeds started at 3,000,000 so they did not overlap the training seeds. The "difference" is the difference in the combined win share of the two seats of each side.

| Cell | Games | Result (95% interval) |
| --- | ---: | --- |
| J1 new network (8081) vs 7081, 2:2 | 1,400 | +41.1 points [+36.4, +45.7] |
| J2 8081 alone vs app AI Hard, 2:2 | 1,400 | +17.9 points [+12.3, +23.1] (29.5% vs 20.6% per seat) |
| J2 7081 alone vs Hard, same seeds | 1,400 | −22.4 points [−27.6, −17.4] |
| J3 search (8081), one seat vs three Hard seats | 200 | 72.0% [65.0, 78.5], average rank 1.41 |
| J3 search (7081), same seeds | 200 | 49.0% (search(8081) − search(7081) = +23.0 points [+14.5, +31.5]) |

The reading comes with conditions. In J1, 7081 had never learned part of these rules, so much of the gap is adaptation to the new rules; it is not read as a general strength difference. J2 is the first time a trained network beat app AI Hard without search. But the effect of mixing in app AI games and the effect of adapting to the new rules cannot be separated in this design. That split needs a self-play-only control run, which was done in the [next entry]({{< relref path="devlog/2026-10-09-mixed-training.md" lang="en" >}}). In a cell measured after the judgement with Scouts off (700 games), 8081 also beat Hard 33.0% to 17.0% per seat. Why that margin is larger than in the Scouts games was not measured.

The play server's search seats were installed with 8081's weights. On October 8 that network was replaced by another one.

## A defect that is still unexplained

The first training attempt died at iteration 7205 because of an engine defect: a human decision with no legal action. It appeared about once in 4,000 games, and it did not appear in a 600-game random soak, a 300-game heuristic soak, or 1,296 games that reproduced the training conditions. So a mechanism was added to save the state of such a game to a file and cut only that game short, and training resumed. In about 26,000 games afterward it did not recur, so the cause is still unknown. If it appears again, the plan is to fix it from the saved state.

## References

- [App-style AI implementation and A/B](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/app-ai-2026-10-05.md)
- [A/B after extending the app AI to every option](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/app-ai-expansions-2026-10-05.md)
- [L3 retraining judgement](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-10-06.md)
- [Merge extending the app AI to every option](https://github.com/jungcheolseung/Dune-Imperium/commit/89f57fc5)
- [App AI seats in the play screen](https://github.com/jungcheolseung/Dune-Imperium/commit/e5a2b0d5)
- [Search AI seats](https://github.com/jungcheolseung/Dune-Imperium/commit/9a03ac3e)
- [Leader-draft option in the tournament tool](https://github.com/jungcheolseung/Dune-Imperium/commit/8de02791)
- [L3 retraining merge](https://github.com/jungcheolseung/Dune-Imperium/commit/3e064dd9)
- [Saving the state of a stuck game](https://github.com/jungcheolseung/Dune-Imperium/commit/c42d23d6)
