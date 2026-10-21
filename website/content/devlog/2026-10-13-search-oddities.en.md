+++
title = "Tracing the search AI's puzzling moves"
description = "Questions about four odd moves by the search AI were re-scored on saved games to find causes. Rules were added for Family Atomics and for strength-only combat Intrigue while alone in first; an attempt to have training learn the Family Atomics timing failed."
date = 2026-10-13T10:58:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-12"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/search-atomics-2026-10-12.md", "docs/worklog/2026-10.md"]
+++

## A question that came up during play

After several games against the search AI, a few of its moves made no sense, and the question was whether such things could be reflected in training. How the search AI picks a move is described in [another article]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}): it keeps five candidates by policy score, plays each out to the end of the round in eight possible worlds, and averages the evaluations. This entry follows the odd moves it made, one by one.

Four saved games were migrated to the current engine to find the scenes, and in each scene the search of the play network of the time (X) re-valued every candidate over 32 possible worlds. Values are on the value head's scale: a win is 1, a loss −1/3.

## Causes of the four scenes

- **A cost-paying combat Intrigue while in first.** In round 7 of a remote game, the search seat was alone in first with 12 points (the others had 6, 2, and 0) and played Spice is Power, paying 3 spice for 6 strength. Re-scoring gave −0.200 for playing and −0.196 for not playing: the search could not tell them apart, so the network's prior preference (0.63 for playing) decided. The value head barely sees what 3 spice is worth, and the combat Intrigue phase ends only when everyone passes in a row (`[Main p. 14]`), so a player alone in first loses nothing by waiting, a fact the search cannot use.
- **Family Atomics in round 1.** This appeared in all six search seats across the four games. The cause is not the search itself but the decision that orders effects within an Agent turn. The search seat does not search that decision and leaves it to the network, and since the only candidates are "use now" and "use a little later in this turn", searching gives nearly identical values. "Hold it" is not a candidate. The network had a habit of using this token in round 1 regardless of the situation.
- **A seemingly pointless Intrigue.** The Emperor's Invitation followed by Assembly Hall turned out to be a normal line: the Intrigue was a one-card draw, not an Emperor icon, and Assembly Hall set up a Dagger for the next turn. Two real cases of the same kind did appear: playing Insider Information to ignore the Influence requirement and then going to a space with no requirement. The search values an Intrigue as "the network's next move after playing it" (+0.336 against +0.259 for going straight to the Agent turn), and re-searches the next decision, which chose a different space.
- **A retreat from a combat with rewards.** Two candidate scenes were found. In one, the retreat led to a contract with values of +0.245 against +0.222 (±0.017); in the other the values were equal. I read both as eight-world luck deciding between moves of nearly equal value, and left them as candidates awaiting confirmation. The Go to Ground retreat on round 5 of the same game was a good move: it protected third place and left two Commanders in the garrison to return to supply after combat (`[Bloodlines p. 4]`).

## Handing Family Atomics to the app AI's rule

The plan was to try a rule first, with the final goal being a network that learns the best timing itself. First the timing was counted on games with all modules and leader draft enabled (seeds 9,000–9,039, 40 games, four seats of the same kind).

| Kind | Seats that used the token | Timing |
| --- | ---: | --- |
| Network X (greedy) | 160/160 | all on the first Agent turn of round 1 |
| App AI, hard | 131/160 (29 never used it) | all on their own Reveal turn, spread across rounds |

The app AI's rule looks at the token only on its own Reveal turn with 4–8 persuasion, and uses it only if the predicted purchases' total value divided by total cost is at most 1 or there is nothing to buy. The search seat and every seat in its playouts now use the token by this rule (0.05 ms per call). With the rule, the search seat used it in 6 of 8 games, in rounds 2 through 9 on its own Reveal turn, and held it to the end in 2.

The measurement was 1 search seat against 3 hard app AI seats, standard rules, 100 seeds (400 games per cell). The merge criteria were written before the results: do not merge if win rate or average rank is clearly worse; if the point estimate is below −2 points, add 100 seeds; otherwise merge.

| | Win rate | Average rank | Victory point (VP) margin |
| --- | ---: | ---: | ---: |
| Chosen by the network | 71.8% [67.2, 76.0] | 1.415 | +3.62 |
| App rule | 76.2% [71.8, 80.5] | 1.337 | +3.99 |
| Difference | +4.5 points [−1.3, +10.2] | −0.077 [−0.175, +0.018] | +0.38 [+0.03, +0.72] |

Win rate and rank improved within noise; only the VP margin's interval excluded 0. There were no failures or illegal actions, and time per decision was the same (703 ms against 712 ms). It was merged by the stated rule.

## Holding strength-only Intrigue while alone in first

The first scene had a separate fix. Since the combat Intrigue phase ends only when everyone passes in a row (`[Main p. 14]`), a player alone in first still gets a turn to respond without playing first. The search seat and every seat in its playouts now drop combat Intrigue options whose rewards are all strength (16 options, such as Spice is Power's 3 spice for 6 strength) from the candidates when alone in first. When tied or behind, or for cards with other rewards mixed in, nothing changes. The app AI holds in the same situation.

Under the same conditions (100 seeds from 7,300,000, 400 games per cell), win rate went from 75.5% to 77.2% (+1.8 points [−2.5, +6.0]), rank difference 0.000, VP difference −0.05. All within noise and not worse, so it was merged by the rule. There is no basis to say this change helped; the finding is only that it costs nothing under the rules.

## Trying to have training learn the timing

Two stages were tried.

**First, the token's actual value.** In 9,000 games among four app AIs, the way a single seat used the token was varied. Against the app rule, "never use" gave win rate −1.15 points [−2.20, −0.05], and the network's habit of "use at the first chance" gave −1.38 points [−2.53, −0.27]. A token used by the rule is worth about 1.2 points of win rate, and using it at once in round 1 is no better than never using it.

**Training stage 1.** In training self-play, the network seats' token was left to the app rule (`--family-atomics app`) for 800 iterations, on the hypothesis that the value head would then see positions where the token was still held. Against the original network (Y) in 1,400 games, the result was −1.4 points [−6.4, +3.6], within noise. Contrary to expectation, the value change from setting only one's own token to "used" in the same observations was +0.0012 for the trained network and +0.0094 for the original. The value head does not seem able to separate differences this small.

**Training stage 2.** The token was returned to the policy and training continued for 800 iterations. Counting timing over 10 checkpoints, all 160 seats used it in round 1. The probability of using it at the first offer in round 1 swung between 0.24 and 0.44 without a steady decline, and the comparison against stage 1 was +1.0 points [−4.0, +6.0], within noise. Under the pre-declared rule (if 90% or more of the last checkpoint's uses are in round 1, the timing was not learned), training stopped. The signal from a token used once per game is about 1.2 points of win rate, and the value head sees a tenth of that, so the current reinforcement learning setup (REINFORCE) does not move in 800 iterations.

The search seat therefore keeps using the app AI's rule. Remaining paths to a network that decides for itself are teaching it to imitate the app rule, or teaching it answers obtained by searching "use now" against "hold" to the end of the game; the latter is an expensive research task.

## What remains

- The two rules here apply only to the search AI and its playouts. Seats that use the trained network alone are unchanged.
- Saved games in which a search seat used Family Atomics before this change cannot be reopened by the server, because replay re-verifies the AI's answers.
- Left as candidates from this topic: evaluating a "this turn" Intrigue together with the Agent turn that uses it, and adding worlds when the top two candidates are within noise, as for the retreat scenes. This entry did not touch them. Afterwards the choice was to change the network's input structure rather than fix scenes one by one with hand-written rules ([next entry]({{< relref path="devlog/2026-10-14-entity-experiment.md" lang="en" >}})).

## References

- [Evaluation document: the odd scenes and the Family Atomics rule](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/search-atomics-2026-10-12.md)
- [Search seat Family Atomics rule merge](https://github.com/jungcheolseung/Dune-Imperium/commit/c4e110da)
- [Self-play Family Atomics option merge](https://github.com/jungcheolseung/Dune-Imperium/commit/4dbd31eb)
- [Hold combat Intrigue while alone in first merge](https://github.com/jungcheolseung/Dune-Imperium/commit/00c00f5c)
