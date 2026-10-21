+++
title = "An entity-based neural network and a learning-rate control"
description = "A network that reads cards, spaces, and actions through shared features was built and tried. Its first win was corrected to a learning-rate effect; what really helped was the training method, so the play model was switched to an MLP trained that way."
date = 2026-10-14T11:16:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-13"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/entity-network-plan.md", "docs/worklog/2026-10.md", "docs/evaluation/search-atomics-2026-10-12.md"]
+++

## Is fixing scenes one at a time the right way?

While following the search AI's odd moves one by one and adding rules, as in the [previous entry]({{< relref path="devlog/2026-10-13-search-oddities.md" lang="en" >}}), the question arose whether picking things out and training on them one at a time was the right direction. Looking at the input structure, we concluded the root was in the structure of the trained network, and decided to plan a fundamental improvement.

The network of the time (X) works like this: it turns the state into 4,537 integers, passes them through 512 × 512 layers, and outputs one score for each of 35,972 action rows. Measured on 501 observations from games with the app AI:

- On average 235 of 4,537 input columns were nonzero per observation, 5.2%.
- 87.6% of the 21.04 million parameters (18.45 million) were the action score table. Each action row is an independent score line, so the fact that similar actions are similar is learned separately for every row. The middle layer, where the state is actually mixed, held 1.2%.
- The five Imperium Row slots, this round's Conflict, and the leader enter as a single number (index plus 1), so cards 87 and 88 are merely "similar in size" and the network cannot tell what card is there.
- The value is one number learned from a single win/loss bit.

The plan was an `entity` network (2.62 million parameters) that reads cards, spaces, and actions through features of their kind and arguments, while the observation, action codec, data collection, trainer, and search seat stay unchanged. The condition was that play with the existing network must remain possible whatever the new structure. To keep causes from mixing, one thing would change at a time, evaluation tools would be built first, and the judging rules would be written before results.

## Evaluation tools first

- **AI mistake problems.** Three problems where the recorded AI's move was wrong and a hand-picked move was better: Spice is Power while alone in first, and two "this turn" Insider Information cases.
- **Network probes.** On 2,025 positions from 20 games with the app AI, they measure value sensitivity (changing spice, Solari, water, troops, or VP and watching the value), swapping the Imperium Row, and the timing of Family Atomics.

The baseline findings shared by four networks (X, Y, and the two networks from the Family Atomics experiment): changing the Imperium Row moves the policy by only 0.3%, so the row is effectively unread. They treat 1 VP (+0.03) the same as 3 spice (+0.03), and value Family Atomics at under a quarter of its real value (about −0.016). All use it in round 1 (80 of 80 seats).

## Building it and imitation (P1, P2)

P1 built the network. Collection cost 0.199 ms per decision (existing) against 0.220 ms (1.1 times), within budget, and search-seat decisions were about 1.6 times slower. Tests caught all five deliberate breakages, and the network can sit in one game alongside existing network files. Building it also fixed a defect where two action arguments were read as a different card of the same name.

P2 teaches the network to imitate the 1.97 million decisions of the head of the training lineage (Y), against a control MLP student of the existing structure.

- The first try's agreement with Y was 93.6% for the entity student against 96.8% for the MLP, and 9.4 points lower on moves Y rarely chose. It failed criteria (a) and (b) of the judging rule.
- Adding a per-action vector that starts at zero raised it to 95.0% and removed the gap on rare moves.
- Value heads trained on game outcomes all memorised the games (error 0.46 on unseen games; always predicting 0 gives 0.33). Switching the target to Y's value also improved the policy (entity 96.5%, MLP 97.8%).

We judged imitating an MLP teacher to favour a student of the same structure, and it was decided to go past the rule and measure directly in reinforcement learning.

## First reinforcement-learning result and its correction (P3)

Both students were trained for 800 iterations each with the same settings. At the MLP's learning rate of 1e-4 the entity network collapsed within about 90 iterations, so 3e-5 and 1e-5 were compared for 150 iterations each and 1e-5 was continued. The MLP stayed at 1e-4.

In 1,400 games the entity network beat the MLP: 53.9% against 46.1%, +7.9 points [+2.7, +13.0], and +5.7 points [+0.7, +10.7] against Y. At first this could be read as a gain from the structure. The note that the learning rates differed was recorded, and the next night the MLP was trained at 1e-5 too and compared.

At the matched learning rate (1,400 games, 14 October) the entity network and the MLP differed by +0.1 points, 95% interval [−4.7, +5.1]. The earlier +7.9 points came from the learning rate, not the structure (1e-4 was too high for the MLP as well). Passing Y was real, though: an MLP trained the same way also beat Y by +4.9 points [−0.3, +9.9], with rank and score margin confirmed. The method is to distil Y's policy and value, use Y's value as the value target, and train with reinforcement learning (REINFORCE) at 1e-5. The record was corrected to say the gain belongs to this training method, not the structure. The training lineage had been running at 1e-4, so retraining the lineage with this method became the follow-up.

## The search seat and replacing the play model (P4)

For a search seat against three hard app AI seats (400 games), the entity network won 81.2% against 77.2% for X, +4.0 points [−1.3, +9.2]. By the rule the win rate was a tie; rank (−0.10) and score margin (+0.72) were confirmed in the entity network's favour. Time per decision was 0.80 s against 0.67 s. Given the control above, that gain more likely belongs to the training method than to the structure.

The policy was to put the strongest model available into play before the engine switch, and to keep the game playable while the engine was being changed. On 14 October the play server's network was changed to the MLP trained with this method (`recipe-mlp-1e5-800`). An MLP stays readable when card data changes; the entity file at that time could not be read after even one card's data was edited, and was 1.6 times slower in the search seat. The previous network X was kept for rollback. The confirming measurement after the decision (search seat against three hard app AI seats) was 82.0% [77.8, 86.0]; against X on the same seeds it was +4.8 points [−1.0, +10.5], within noise, with a confirmed score margin of +0.54. The entity network was not put into play.

## Observation v32: deck and hidden-hand composition

While reviewing the entity network's input, it seemed better to include bought or acquired cards too. The network has no memory, so a bought card disappeared from the observation once it was shuffled into the deck. A ruling was made to publish each seat's combined deck and hidden hand composition (which cards, how many) to all seats (OQ-010 ruling 6). Every path by which cards enter or leave the deck and hand passes through public places, so anyone can count it. Which of deck or hand a card is in, and which copy it is, stay hidden. The AI observation gained 139 columns per seat, going from 4,537 to 5,093 columns (observation v32), and tapping the hand, deck, and discard lines on screen also shows "cards in deck and hand".

The independent review audited every point in the engine where cards move between deck and hand in a table, and compared about 17,000 card movements across 14 games in 7 rule combinations, finding 0 leaks of a hidden source or destination. Entity files now name their inputs and migrate by name, and the migrated network was confirmed to give exactly the same output as the v31 code on v31 observations.

## What remains

- At this point the entity network did not show a structural advantage and was not put into play. Using the new deck-composition columns requires retraining.
- The results should not be read as a ranking of structures. The structure for the next training run is a choice to be made on other grounds: the input (observation v32), search speed, and generalisation to card and rule changes.
- The feature tables and the evaluation and distillation tools were later used to connect model inputs in the [ability-record work]({{< relref path="devlog/2026-10-19-ability-records.md" lang="en" >}}).

## References

- [Experiment plan, evaluation tools, results by stage, and the correction](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/entity-network-plan.md)
- [Evaluation tools merge](https://github.com/jungcheolseung/Dune-Imperium/commit/cfad1fc1)
- [P1 implementation merge](https://github.com/jungcheolseung/Dune-Imperium/commit/fa3054d2)
- [P2/P3 distillation and reinforcement learning merge](https://github.com/jungcheolseung/Dune-Imperium/commit/1b6ed481)
- [Correction of the earlier interpretation](https://github.com/jungcheolseung/Dune-Imperium/commit/4df74232)
- [Observation v32 merge](https://github.com/jungcheolseung/Dune-Imperium/commit/ebe125c7)
