+++
title = "Inside the AI model: from reading a position to scoring moves"
description = "How the policy/value model used by search AI reads an observation and produces move scores and a win estimate, explained for the current play MLP and the entity model chosen for the next training lineage."
date = 2026-10-21
lastmod = 2026-10-21
draft = false
categories = ["AI 학습 실험"]
tags = ["정책·가치", "대조 실험"]
[params]
source_ref = "7fe69ac6"
sources = ["src/dune_imperium/training/network.py", "src/dune_imperium/training/entity_network.py", "src/dune_imperium/training/entity_features.py", "src/dune_imperium/training/learner.py", "src/dune_imperium/adapters/observation_encoding.py", "docs/rl-environment.md", "docs/entity-network-plan.md", "docs/development-handoff.md"]
+++

Search AI uses one trained model to pick candidate moves and to judge the positions it plays out
([How search AI chooses a move]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}})).
This article looks inside that model. There are two structures: the **MLP** the play server uses today, and the
**entity model** chosen on October 18, 2026 for the next training lineage. Sizes and numbers follow the code of October 21, 2026
(action codec v151, observation v33).

## The overall shape

The model turns the position into numbers, builds a **position summary**, and two outputs read that summary side by side.

```text
Observation (5,732 integers)
  └─ Body → position summary h (512 numbers)
       ├─ Policy head → a score per legal action → probabilities
       └─ Value head → one estimate of the expected result
```

The policy head answers "what should I play?" and the value head answers "am I likely to win from here?".
The two heads are not chained; they branch from the same summary.

## The observation: what the model sees

The observation is a single row of 5,732 integers split into 127 named segments. The function that builds it takes only
the seat's own view (`PlayerView`), so hidden information such as opponents' hands or deck order cannot enter it.

| Segment group | Values | Contents |
| --- | ---: | --- |
| Shared board | 485 | Imperium Row, current Conflict, contracts, Intrigue discard, Tech and Skills |
| Four seats | 828 × 4 | Each seat's resources, VP, influence, alliances, spies, public card zones, contracts |
| My private view | 463 | My hand and Intrigue cards, peeked cards |
| Modules and progress | 277 | Arrakeen Scouts, Epic, pending obligations |
| Deck contents | 556 | Each seat's cards not yet visible |
| Current choice | 639 | The card just played, and the verb, source and target of the effect being answered |

Numbers are written in three ways.

- **Slots:** "what is here" for the five Imperium Row slots, the current Conflict or Agent locations is the card number plus one (0 means empty).
- **Counts:** unordered zones such as a hand or a discard pile hold a count for each card type. There are 139 personal card types, so one such zone is 139 values.
- **State:** alliances, control and spy posts are on/off; resources, VP and influence are plain numbers.

Seats are always counted from the player to move: whoever plays is seat 0 and opponents are seats 1–3, so one model can play all four seats.
The "current choice" segments appeared when the Agent turn was split into card+space → effect → target steps (codec v150).
When a card has been played and its effect's target is being chosen, the verb, card and target kind go here.

## The MLP: today's play model

**Body.** Some observation values are 0 or 1 and others are as large as a card number of 120. Fed as they are, large values would dominate,
so each value is first compressed with log(1+x) (0 → 0, 1 → 0.69, 10 → 2.4, 120 → 4.8). Two layers follow: one mixes the 5,732 values into 512,
the next mixes those 512 into 512 again. Each layer multiplies by weights, adds, and cuts negative values to zero (ReLU).
The result is the position summary h.

**Policy head.** Every action in the action list has its own row of 512 weights. Its score is that row multiplied with h and summed,
plus the row's offset. Actions that cannot be played now get a score of −1 billion, so their probability after softmax is exactly zero.
With three legal actions scored 2.1, 0.3 and −0.5, the probabilities are 0.81, 0.13 and 0.06. Data collection samples from these probabilities,
a model-only seat plays the top one, and search AI takes the top five as candidates.

**Value head.** One number: the 512 values of h multiplied by weights and summed.

**Size and weaknesses.** Most of the model's weight is in the policy head. The current play model file holds the 36,379 action rows of codec v147,
which are 87% of its roughly 21.5 million weights. When the action list changes, rows are moved by action identity and new actions start at zero.
Codec v150 split the Agent turn into steps and created almost all rows anew, so of v151's 4,311 rows this model has trained only 84.
The MLP also reads slot card numbers as magnitudes: cards 57 and 58 are almost the same number after compression, so it hardly tells them apart
(value-sensitivity measurement, September 27, 2026).

## The entity model: reading cards by their content

The entity model takes the same observation and answers the same three calls (body, action scores, value) that search AI, training and
checkpoints use. What changes is how it reads.

**Entity vectors.** Each card, board space, Conflict and so on becomes 64 numbers. The input is content features read from the card definitions:
cost, faction, Agent icons, and the printed ability records (the conditions, costs and rewards of Agent boxes and Reveal lines, with their amounts).
Personal cards have 329 feature columns and board spaces 152. Names and ids are left out, so two cards that print the same thing get the same features.
A linear layer with tanh maps the features to 64 values, and a separate 64-value vector per entity, starting at zero, is added.
Training fills that vector with whatever the features cannot tell apart.

| Entities | Count | Entities | Count |
| --- | ---: | --- | ---: |
| Personal cards | 139 | Conflicts | 19 |
| Intrigue cards | 90 | Leaders | 18 |
| Contracts | 28 | Tech tiles | 18 |
| Battle cards | 24 | Spy posts | 13 |
| Board spaces | 23 | Skills | 7 |
| Research spaces | 22 | Factions | 4 |

**Three ways of reading.**

- **Numbers:** resources, VP and influence enter through log(1+x), as in the MLP.
- **Zones:** a hand, discard pile or set of held contracts becomes the sum of "count × entity vector", 64 values. Two copies of A and one of B in a discard pile give 2A + B.
- **Slots:** the slot's learned vector plus the vector of the entity in it. Cards 57 and 58 have different vectors, so they are told apart.

**Encoders and body.** The four seats share one encoder. Me and the three opponents are read with the same weights, so what is learned about one seat applies to all.

```text
Seat encoder (shared by four)  49 numbers + 13 zones × 64 + 8 slots × 64  → 256 per seat
Board encoder                  315 numbers + 8 zones × 64 + 16 slots × 64 → 256
Private encoder                69 numbers + 13 zones × 64 + 5 slots × 64  → 256
  └─ concatenated: board + private + 4 seats = 1,536 → 512 → 512 → position summary h
```

**Actions are assembled from parts.** The MLP keeps a separate 512-value row per action. The entity model takes parts from the action shape table
and builds a 128-value vector. For `trash_reveal_card(card X)` it adds the vectors of the verb `trash`, the source `reveal_card` and the target
`personal_card`, plus card X's entity vector transformed for the role "card to trash". That sum goes through one ReLU and linear layer to become the action vector.
`trash_agent_card(card X)` differs only in its source, so what is learned for one carries to the other.
The score is the dot product of a 128-value query computed from h with the action vector, plus a per-action offset.
When a rule change adds an action built from known parts, it gets a sensible score from the start.

Scoring from parts alone is weaker on rare decisions, so distilled students add a separately learned 128-value vector per action (`own_actions`).
Actions built from exactly the same parts differ only by that vector and their offset.

| | MLP (current play model) | Entity |
| --- | --- | --- |
| Reading the observation | Mixes all 5,732 values at once | Summarizes seats, board and private view separately |
| Cards | Numbers (slots) and counts (zones) | Content features + own vector |
| Action score | Each action's 512-value row · h | Assembled 128-value vector · query |
| When a new action appears | Starts at zero | Scored from its parts at once |
| Weights | About 21.5 million (v147 file) | About 3.31 million (4,311 rows, own vectors included) |

## How the two heads are trained

Reward comes only at the end of a game: +1 for first place, −1/3 for each other seat. Training is REINFORCE with a value baseline.
After a game each move gets "actual reward − value prediction for that position" (the advantage): moves from games that ended better than predicted
become more likely, and moves from games that ended worse become less likely. The loss is the policy term + 0.5 × value error − 0.01 × entropy,
and each collected batch is used once. The recent recipe collects 32 games at a time, 16 of them with two learning seats facing the app AI,
at a learning rate of 1e-5. The entity model collapsed after about 90 iterations at 1e-4: thousands of actions share each part,
so one step moves many scores at once.

The same learner also has PPO (clipping, and reusing the same games several times), but it collapsed in a comparison on September 18, 2026 and is not used.
A starting model that won 76.5% against three heuristic seats fell to 43.0% after 100 more iterations of PPO (clip 0.2, each batch used three times),
while REINFORCE under the same conditions held 75.5% (200 games each).
On October 21, 2026 the project corrected its records and documents, which had been calling the later REINFORCE runs "PPO".

The value head is used in two places: as the baseline above during training, and to score end-of-round positions in search AI.
A value head trained on game outcomes tended to memorize games. In the October 13 distillation its error on unseen games was 0.46,
worse than the 0.33 of always answering 0. Using the teacher model's value as the target instead also raised policy agreement from 95.0% to 96.5%.

## How the widths were chosen

| Number | Chosen | Reason | Other values tried |
| --- | --- | --- | --- |
| MLP body 512, 512 | 2026-09-06, first model | No recorded reason | None |
| Entity body 512, 512 | 2026-10-13 | The plan says only "512 × 2, as in the MLP" | None |
| Entity 64, seat 256 | 2026-10-13 | A starting point inside a speed budget: per-decision cost within 1.5× the MLP's | Once (below) |
| Action 128 | 2026-10-13 | No recorded reason | None |

The speed budget exists because most training time goes into collecting games. The first entity model cost 1.1× the MLP per decision in collection,
inside the budget, and about 1.6× in search AI. Search often evaluates one position at a time, and at that batch size the entity model is 3.2× slower.

The width was widened once, on October 13. Two students were distilled from the same data, one with entity 64 and seat 256, one with entity 128 and seat 512.
The wider one grew from 7.2 to 11.0 million weights and from 125 to 211 seconds per epoch, yet both agreed with the teacher on 95.0% of unseen games,
and both were within noise in 400 games against the teacher. The agreement gap at the time came from the action scoring (about 2 points) and the state summary
(about 1 point), not the width; adding a learned vector per action closed the gap on rare decisions.

## Where things stand

- **Play server:** uses the MLP (`readapt-v147-4400`, installed October 15, 2026). At installation one search AI seat won 81.8% (95% interval [78.0, 85.5]%)
  of 400 games against three app AI Hard seats (codec v147). Since codec v150 it knows only 84 rows, so it is weaker on the current engine.
- **The two structures:** trained the same way they were equally strong. On October 14 the entity model's win-rate difference against the MLP over 1,400 games
  was +0.1 points ([−4.7, +5.1]), and in the October 19 retraining comparison +1.3 points ([−3.9, +6.4]). The benefit expected from the entity model
  is less about strength than about not relearning from scratch when rules and cards change.
- **Retraining:** an adapter that lets the old model act on the new action units reproduced its strength (1 vs 3 app AI Hard, 54.7% and 54.8% over
  1,000 games each), but it is not a play server seat. An entity student distilled from that adapter, followed by 800 REINFORCE iterations,
  was 7.0 points weaker than the teacher and was not installed
  ([first retraining attempt]({{< relref path="devlog/2026-10-21-retrain-teacher.md" lang="en" >}})).

How this structure compares with other game AIs is covered in
[Checking the model structure against other game AIs]({{< relref path="posts/architecture-survey.md" lang="en" >}}).

## Records

- [MLP code](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/src/dune_imperium/training/network.py),
  [entity model code](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/src/dune_imperium/training/entity_network.py),
  [entity features](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/src/dune_imperium/training/entity_features.py),
  [learner](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/src/dune_imperium/training/learner.py)
- [Training environment document](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/docs/rl-environment.md) (observation, reward, structures, policy term),
  [entity model plan and progress record](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/docs/entity-network-plan.md)
- [Commit correcting the training method name](https://github.com/jungcheolseung/Dune-Imperium/commit/7fe69ac6)
