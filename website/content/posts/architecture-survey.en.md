+++
title = "Checking the model structure against other game AIs"
description = "On October 21, 2026 we surveyed public work on board game, card game and large game AIs to judge whether the current model structure is reasonable and what to change first."
date = 2026-10-21
lastmod = 2026-10-21
draft = false
categories = ["AI 학습 실험"]
tags = ["정책·가치", "탐색"]
[params]
source_ref = "7fe69ac6"
sources = ["docs/entity-network-plan.md", "docs/rl-environment.md", "docs/evaluation/m10-2026-09-22.md", "docs/evaluation/exit-v2-2026-10-08.md", "docs/development-handoff.md"]
+++

The two models described in [Inside the AI model]({{< relref path="posts/model-architecture.md" lang="en" >}}) were equally strong when trained the same way,
and numbers such as the 512-wide body and 64-value entity vectors were not chosen by measurement. So on October 21, 2026 we surveyed public work
on other game AIs that face similar decisions. This article summarizes what we found, our judgment of the current structure, and what to try next.

The survey had five strands: TabletopGames (TAG) and board games; digital card games; imperfect-information games such as poker, Mahjong and Diplomacy;
large game agents (StarCraft II, Dota 2) and research on large action spaces; and studies of whether structure or training method mattered more.
We preferred papers, official repositories and developer write-ups. We found no public neural AI for a 4-player deck-building and worker-placement game like ours,
so parts of the judgment below carry results over from other genres and are inferences.

## Summary

- Both models sit inside designs the field commonly uses. The MLP is the "fixed action list + legal-action mask" family; the entity model is the
  "pooled entity summary + dot product of state and action vectors" family. They are reasonable choices, but there is no evidence that they are optimal.
- Three things that large systems share are missing from the entity model: self-attention between entities, target selection conditioned on the chosen verb,
  and a value model separate from the policy.
- In published comparisons, structural differences on the training distribution moved win rates only a little. Large gains came from search at play time,
  followed by training method and optimization. Our own measurements have the same shape.
- So the next steps are not a structure swap: first the parts of search AI, then distillation and value learning, then small changes to the structure.
  None of them has been run yet.

## How other AIs read positions and score actions

Position encodings fell into three groups.

- **Flattened counts or one-hots per card type:** PyTAG's per-game encodings, DouZero's card matrices and Suphx's tile planes. Our MLP's observation belongs here.
- **Card embeddings pooled per zone:** Gerigk & Engels pooled 16-dimensional card embeddings per pile with DeepSets in Dominion, and ByteRL averaged
  zone card embeddings in Hearthstone. Our entity model's "count × entity vector" sum is the simplest member of this group.
- **Entities as tokens with self-attention:** Catan PPO (two attention blocks over tiles), ygo-agent for Yu-Gi-Oh (a 2-layer transformer over cards),
  AlphaStar (a transformer over units), Cicero in Diplomacy, and ZeusAI in 7 Wonders Duel (12 layers).

Action scoring fell into four groups.

| Method | Examples | Our models |
| --- | --- | --- |
| One output row per action + legal mask | PyTAG, Big 2, Mahjong Mortal, the LOCM environment | MLP |
| Dot product of a state query and action vectors (pointer) | OpenAI Five, Honor of Kings, ByteRL (source → target in two steps), Stratego Ataraxos | Entity |
| Action fed as input, one score out | DouZero, Cardsformer, PerfectDou | None |
| Decomposing the action inside the network | AlphaStar (action type → units → target), Catan PPO, Diplomacy order decoder | The engine splits steps |

Every system splits multi-step turns into a chain of single decisions and tells the model which decision it is in.
Our engine already splits the Agent turn into card+space → effect → target steps. Playing the teacher model's per-step distribution directly
was as strong as the teacher (57.5% against 56.8%), so the split loses nothing.

One point is worth noting. A head with one output row per action is also a dot product: each action's row is a freely learned action vector.
So the real difference between our two models is not expressive power but whether action vectors are kept per action or computed from shared parts.
Sharing lets rare actions and new cards borrow statistics from similar ones.

## What moved win rates

| Change | Other systems | Our measurements |
| --- | --- | --- |
| Search at play time | LoCM: the same model without search 26.8% → with search 51.35% (+24.6 points). Catan: root search 47/100 (baseline 25%) | Search AI 81.8% (codec v147, 2026-10-15) versus the same model alone 54.7% (codec v149, 2026-10-21). Engine and seeds differ, so the gap of about 27 points is approximate |
| Training method and optimization | Most of the PPO–TRPO difference came from code-level choices, not the algorithm. In multi-agent self-play, reusing the same games is harmful | Learning rate 1e-4 → 1e-5 explained the whole +7.9-point structure difference first seen. PPO collapsed once |
| Structure, same data | MTG drafting: card representation barely changed accuracy on cards seen in training. LoCM: a larger model gave no clear gain | MLP vs entity +0.1 points ([−4.7, +5.1]). Doubling the entity width left distillation agreement at 95.0% |
| New information or out-of-distribution tests | MTG: representations differed a lot on unseen cards. Diplomacy DORA: a transformer beat graph convolution with fewer parameters. KataGo: global pooling and auxiliary targets each about 1.6× efficiency | No measurement on unseen cards |

Search contributed a lot in every genre. In PyTAG, PPO models trained for one million steps won only 5% in 4-player Sushi Go! and 1% in 4-player Love Letter
against untuned MCTS. In Expert Iteration, network-guided MCTS beat plain MCTS 97% of the time, while doubling plain MCTS iterations gave only 56%.
In Hex, 10× training compute was worth about 15× search compute at play time. Matching search AI's contribution with the model alone would take
several times more training than one Mac mini can provide.

Simply making models larger was often harmful or useless in reinforcement learning. Distillation studies also report that widening the student barely changes
agreement with the teacher, and that the cause lies in optimization rather than capacity — the same shape as our widening experiment.

## Weaknesses of our two models

**MLP.** The 512 × 2 body is a default with no recorded reason, but it matches defaults in the literature (Hex, Hanabi, DouZero). Evidence that width is
the bottleneck is weak. The weakness is the lack of sharing: the action rows, 87% of the weights, share nothing, so rare card actions learn slowly,
and every change to the action list needs surgery to move rows. OpenAI Five did more than 20 such surgeries and reported that retraining from scratch
was stronger with about 20% of the compute.

**Entity model.** The action vector passes the sum of its parts through one ReLU and linear layer, so interactions between parts are limited to that one layer.
In the October 13 breakdown the action scoring lost about 2 points, which a learned per-action vector closed. Four more weaknesses:

- **Zone sums replace the raw counts.** Squeezing a zone with more than 100 card types into a 64-value sum can lose exact count information.
  Sum pooling is lossless only when the latent width is at least the set size (Wagstaff et al.). We have not measured how much our model loses.
- **No interaction between entities.** Relations such as card combinations or competition for spaces must be inferred by the body from the sums.
  Large systems use self-attention, but the gain on the training distribution was small (Hide-and-Seek: 9% fewer samples, 10% slower wall-clock).
- **Action vectors do not depend on the state.** The state enters only through the query. For the ranking of legal actions to change with the state,
  one 128-value query must carry the whole difference.
- **Sharing forced a lower learning rate, and the model is about 1.6× slower per decision in search AI.**

**Both models: the value head and distillation.** The value head is one number sharing the body with the policy, and trained on game outcomes it memorized games.
The literature recommends a separate value model (the large-scale study by Andrychowicz et al., DORA, AlphaStar). But in a September 22, 2026 experiment,
fitting the value head more closely to game outcomes made search AI's mean rank 0.13 worse. Predicting outcomes well is a different skill from separating
similar positions, so value changes must be judged with search AI.

The retraining distillation data came from games the teacher played itself, not positions the student will actually meet. One study found that labeling
student-generated positions with the teacher's answers recovered the teacher's strength about 3× faster (Czarnecki et al.), and another found that adding a
teacher-difference term to the RL loss and decaying its weight let the student surpass the teacher (kickstarting). Our retraining used plain REINFORCE after distillation
and ended 7.0 points weaker than the teacher.

## How the search AI looks

Search AI belongs to the PIMC family: it plays out candidates in sampled worlds. Classic PIMC solves each world with perfect information, so it can
act as if it could choose differently in each world — strategy fusion. In our search every seat plays the playout with the model from its own observation,
so this problem is essentially absent. It is closer to a one-step improvement over the model's policy, as in SPARTA for Hanabi or Ataraxos for Stratego.

Three sources of error remain.

- **Worlds are sampled without regard to opponents' past moves.** Skat and DouDizhu AIs gained by weighting worlds with the probability of the moves opponents actually made.
- **App AI opponents are assumed to play like our model.**
- **The best average over 8 worlds can be noise.** In the September 2026 records, search overturned the model's top choice in 44% of decisions,
  but the average difference was below 0.005 in 41% of decisions, and splitting the worlds into two halves changed the choice in 25%.

There is also a record of model-only gains not carrying into search AI. Model M was 13.1 points stronger model-to-model, but the difference vanished inside search AI
([Does mixing opponents improve training?]({{< relref path="posts/learning-with-opponents.md" lang="en" >}})). We read this as a sign that search is capped more by its own parts —
world sampling, value evaluation, candidate selection — than by the model (an inference).

## What to try next

These are plans, none run yet; expected effects are estimates.

1. **A flip threshold or a prior anchor:** keep the model's top choice when the average difference is small. SPARTA leaves its blueprint only when an action is more than 0.05 better,
   and Ataraxos's search became worse than the model alone when its anchor to the model policy was removed. A few dozen lines of code and one or two 400-game cells.
2. **Candidate selection and playout budget:** instead of a fixed top five, draw candidates the Gumbel way and give the 40 playouts to promising candidates.
   Gumbel AlphaZero guarantees policy improvement even with 2 simulations.
3. **Weighting worlds by opponents' moves:** weight 32 worlds by the probability of what opponents played this round and resample 8. Our model already produces opponent policies,
   so no new model is needed.
4. **Distillation method:** label positions from games the student plays with the teacher's answers, then train with a decaying teacher-difference term. The goal is to shrink the −7.0-point gap to within −2 points.
5. **A separate value model:** compare a value model split from the policy, and a training-only value baseline that sees hidden information (as in PerfectDou).
6. **Entity model changes:** feed the raw zone counts as well, state-dependent action scores (one attention layer over legal actions or verb gating), and 1–2 entity self-attention layers.

Search experiments will also be measured against three play models, not only three app AI Hard seats, because near 81.8% the confidence interval of a 400-game win-rate
difference is about ±5 points and small gains would not show. Rank and score margin are judged too. On hold: another PPO attempt, a wider MLP, an LSTM, and poker-style CFR search.
CFR-style guarantees hold only for two-player zero-sum games, and even Pluribus in 6-player poker was justified by measurement, not guarantees.

## Where evidence is missing

- No public study compares an MLP with entity or attention models at equal compute in a multiplayer deck-building or worker-placement game. Our +0.1-point tie is a rare data point.
- No study directly compares per-action output rows with dot-product scoring under policy gradient on a large action list.
- Almost no study compares PIMC, IS-MCTS and learned-belief search in such games or measures how many worlds are needed (one result: LoCM saturated around 32).
- Scaling-law studies come from two-player perfect-information games and do not transfer directly to four-player imperfect information.
- We found no study measuring which decisions a distilled student loses strength on. Our finding that the loss concentrates where the teacher itself is unsure is new data in itself.

## References

- TabletopGames: [PyTAG (2024)](https://arxiv.org/abs/2405.18123), [TAG (2025)](https://arxiv.org/abs/2503.02686)
- Board games: [Catan PPO](https://settlers-rl.github.io/), [Dominion, Gerigk & Engels (AIIDE 2023)](https://ojs.aaai.org/index.php/AIIDE/article/view/27518), [ZeusAI, 7 Wonders Duel](https://arxiv.org/abs/2406.00741)
- Card games: [ByteRL, Hearthstone](https://arxiv.org/abs/2303.05197), [LoCM search, Rubin (2026)](https://arxiv.org/abs/2609.06816), [ygo-agent](https://github.com/sbl1996/ygo-agent), [MTG card representations, Bertram et al. (CoG 2024)](https://arxiv.org/abs/2407.05879), [DouZero](https://arxiv.org/abs/2106.06135), [PerfectDou](https://arxiv.org/abs/2203.16406)
- Imperfect information: [Suphx](https://arxiv.org/abs/2003.13590), [Pluribus](https://www.science.org/doi/10.1126/science.aay2400), [ReBeL](https://arxiv.org/abs/2007.13544), [SPARTA](https://arxiv.org/abs/1912.02318), [Ataraxos](https://arxiv.org/abs/2511.07312), [DORA](https://arxiv.org/abs/2110.02924), [Kermit policy-based inference](https://arxiv.org/abs/1905.10911), [strategy fusion in PIMC, Long et al. (AAAI 2010)](https://ojs.aaai.org/index.php/AAAI/article/view/7562)
- Large agents: [OpenAI Five](https://arxiv.org/abs/1912.06680), [Honor of Kings](https://arxiv.org/abs/1912.09729), [AlphaStar Unplugged](https://arxiv.org/abs/2308.03526), [Perceiver IO](https://arxiv.org/abs/2107.14795), [Hide-and-Seek](https://arxiv.org/abs/1909.07528)
- Training method: [Engstrom et al. (2020)](https://arxiv.org/abs/2005.12729), [Andrychowicz et al. (2021)](https://arxiv.org/abs/2006.05990), [MAPPO](https://arxiv.org/abs/2103.01955), [Expert Iteration](https://arxiv.org/abs/1705.08439), [Jones, scaling laws in Hex](https://arxiv.org/abs/2104.03113), [Gumbel AlphaZero](https://openreview.net/forum?id=bERaNdoegnO), [KataGo](https://arxiv.org/abs/1902.10565)
- Distillation and set representations: [Czarnecki et al. (2019)](https://arxiv.org/abs/1902.02186), [Kickstarting](https://arxiv.org/abs/1803.03835), [Stanton et al. (2021)](https://arxiv.org/abs/2106.05945), [Wagstaff et al. (2019)](https://arxiv.org/abs/1901.09006)
- This project's records: [entity model plan and progress record](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/docs/entity-network-plan.md),
  [training environment document](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/docs/rl-environment.md),
  [September 2026 evaluation record](https://github.com/jungcheolseung/Dune-Imperium/blob/7fe69ac6/docs/evaluation/m10-2026-09-22.md)
