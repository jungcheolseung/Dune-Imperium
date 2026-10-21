+++
title = "How search AI chooses a move"
description = "Default AI, trained policies, and search use different ways to choose the next legal action."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
categories = ["AI 학습 실험"]
tags = ["정책·가치", "탐색", "숨은 정보"]
[params]
source_ref = "c8f61677"
sources = ["docs/search-ai.md", "src/dune_imperium/agents/network_search_agent.py", "docs/evaluation/m10-2026-09-22.md", "docs/evaluation/m10-2026-10-06.md", "docs/evaluation/m10-2026-10-07.md", "docs/evaluation/search-atomics-2026-10-12.md", "docs/development-handoff.md"]
+++
AI seats share the same interface but can choose moves differently. Some score immediate gains, some use a learned judgment, and search compares simulated continuations.

## Three decision methods

**Default app AI** compares the immediate value of each choice with a fixed evaluation and does not look ahead. It has hard, medium, and easy levels and needs no trained model.

**Checkpoint AI** scores every action from the trained model's view of the position and plays the highest-scoring legal action. When only actions the model never learned remain, the heuristic AI answers instead.

**Search AI** uses the model to pick promising candidates, then simulates what follows. It can overrule the model's first preference.

## Two model outputs

A policy-value model produces:

- **Policy:** preference among legal actions.
- **Value:** estimated favorability of the current position.

The policy narrows candidates; the value evaluates unfinished positions. Selecting good actions and evaluating future positions are separate abilities that both need checking.

## One search decision

The defaults are five candidates, eight possible worlds, and search to the end of the current round.

1. **Choose candidates.** Keep the five legal actions with the highest policy scores.
2. **Create possible worlds.** Reassign unknown information consistently with what the seat knows, making eight worlds.
3. **Play them out.** Apply each candidate in each world, then let the model play all four seats to the end of the round.
4. **Compare outcomes.** Score the end-of-round position with the value, or use the actual result if the game ended.
5. **Decide.** Play the candidate with the highest average over the eight worlds.

All five candidates are compared in the same worlds with the same random outcomes, such as card draws. Separate samples per candidate could favor a lucky draw; shared samples make the difference come from the candidates themselves.

```text
Current position
  └─ five candidates from the model
       └─ play each one to the end of the round in eight possible worlds
            └─ compare averaged outcomes and values → choose one action
```

One decision plays 5 × 8 = 40 continuations. In the measurement recorded in the documentation, searched decisions took 1.4 seconds on average and about 3.3 seconds for slow ones under the default rules. The server lets a search seat think in the background and shows **Thinking…** meanwhile.

Decisions with only one legal action, with only one candidate left, or that order effects within an Agent turn are answered by the model without search. Searching effect order rarely changed the result but cost much of the time. That was measured before the action units changed (codec v150) and has not been re-measured since.

## Defaults chosen by measurement

The first defaults were three candidates and four worlds. On September 24–25, 2026, candidate count, world count, and depth were varied one at a time. Against three seats of the strongest model at the time, five candidates × eight worlds won 76.1% of 1,000 games, while three × four won 62.0% of the same games (25% for an even result): a difference of +14.1 points, 95% interval [+10.5, +17.7].

Eight candidates were no better than five. Searching two rounds ahead took 3.4 times as long with a lower point estimate and was stopped at 200 games. Sixteen worlds gained +2.2 points ([−1.6, +5.8]) over eight on 1,000 new games, below the pre-declared threshold, at twice the time, so eight remained the default.

## Thinking without hidden information

The server knows the full state, but search must not use actual hidden hands or deck order. It reassigns unknown information into possible states, a process called determinization.

What is reassigned includes opponents' hands, deck order, and Intrigue cards. The Conflict deck keeps its I, II, and III tier positions, and each tier is reshuffled together with the cards of that tier returned to the box unused, because nobody knows which cards went to the box (`[Main p. 4]`, since October 8, 2026). That search does not leak hidden information was checked separately.

A sampled world is not the hidden answer. With few samples, close candidates can be ranked by chance.

## Rules decided outside the model

Not every search decision comes from training. The following three rules were set separately, and the four seats inside each playout follow them too.

- **No repetition.** An action already played at the same position in the same round is removed from the candidates. Without this, some games looped forever switching a grafted card.
- **Family Atomics (Immortality).** The model used this token on the first Agent turn of round 1 in every game, so the app AI's rule decides instead: use it on one's own Reveal turn with 4–8 persuasion when the cards available cost at least one persuasion per point of value. Against three hard app AIs on the same 400 seeds, win rates were 76.2% vs. 71.8% (within noise), with a clearer VP margin gain of +0.38 (October 12, 2026).
- **Holding combat Intrigue when alone in first.** The combat Intrigue step ends only after everyone passes in succession (`[Main p. 14]`), so a sole leader who plays a strength-only card first spends the card and its cost for nothing. Sixteen such cards are held in that situation. The same comparison showed 77.2% vs. 75.5%, no weaker (October 13, 2026).

## How strong was it?

Measured with the model of October 6, 2026, using every expansion, Arrakeen Scouts, and leader draft on seeds not used in training:

| Comparison | Games | Result |
| --- | ---: | --- |
| Model alone, two seats, vs. two hard app AIs | 1,400 | 29.5% vs. 20.6% wins per seat |
| One search seat vs. three hard app AIs | 200 | Search won 72% (25% for an even result) |

After the play server's model changed on October 8, the search seat won about 78% in each of three seed blocks of the same comparison.

## Model strength and search strength are measured separately

A model's standalone win rate and the win rate of search using it can move differently. Model M from the [opponent-mixing experiment]({{< relref path="posts/learning-with-opponents.md" lang="en" >}}) beat its starting model by +13.1 points (95% interval [+8.0, +18.1]) when the models played each other. Put inside search against three hard app AIs, the difference over 150 seeds was −0.5 points ([−5.8, +4.7]). The first 50 seeds had shown −10.5 points, a reversal that did not reproduce on new seeds. Play-model changes are therefore measured with search seats; the October 8 change was decided by a search-seat comparison (+11.3 points over 100 seeds, [+5.3, +17.3]).

## Limits and current state

After the current round, search trusts the value. If that estimate is wrong, search can be wrong. Simulations also assume opponents play like the model, which may not match a human.

A model is tied to the action list it learned. Since the action units changed on October 20, 2026 (codec v150), the current play model, trained on an earlier version, knows only 84 of the 4,311 new action rows. Other decisions fall back to the heuristic, so search AI on the v150 engine is weaker than the numbers above. The [first attempt]({{< relref path="devlog/2026-10-21-retrain-teacher.md" lang="en" >}}) to retrain for the new action units did not surpass the existing model, and the play model has not been replaced yet.

See the [search AI documentation](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/search-ai.md) and the [implementation at this article's reference commit](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/src/dune_imperium/agents/network_search_agent.py). The documentation's strength figures refer to the October 6 model. Play requirements are in [choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}}).
