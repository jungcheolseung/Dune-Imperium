+++
title = "How search AI chooses a move"
description = "Default AI, trained policies, and search use different ways to choose the next legal action."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
categories = ["AI 학습 실험"]
tags = ["정책·가치", "탐색", "숨은 정보"]
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/search-ai.md", "src/dune_imperium/agents/network_search_agent.py", "docs/rl-environment.md"]
+++
AI seats share the same interface but can choose moves differently. Some score immediate gains, some use a learned judgment, and search compares simulated continuations.

## Three decision methods

**Default app AI** compares the immediate choice using a fixed evaluation. It requires no trained model file.

**Checkpoint AI** takes the current position and produces action scores, then chooses a preferred move directly. Its judgment comes from repeated games.

**Search AI** uses the model to select promising candidates and simulates their continuations. It can choose differently from the model's initial preference.

## Policy and value

The model has two outputs:

- **Policy:** preferences among available actions.
- **Value:** an estimate of how favorable the position is for winning.

Policy narrows the candidate set. Value evaluates positions that are not played to the end. Direct move selection and position evaluation need separate checks.

## A search decision

The implementation described here defaults to five candidates, eight possible worlds, and simulations to the end of the current round. It skips search for a sole legal choice and some effect-order decisions.

1. **Choose candidates.** Take highly ranked legal actions from the policy.
2. **Build possible worlds.** Rearrange unknown information consistently with what this seat knows.
3. **Simulate.** Play each candidate in each world, with the model playing all four seats.
4. **Evaluate.** Use value at the round boundary, or the actual result if the game has ended.
5. **Choose.** Average across worlds and select one action.

Candidates use the same worlds, reducing the chance that one wins simply because it received a luckier sample.

```text
Current position
  └─ Policy candidates
       └─ Simulate each in possible worlds
            └─ Compare outcomes and values → Choose an action
```

## Reasoning without hidden information

The server's complete state must not let the AI play with knowledge of actual opposing hands or deck order. Search rebuilds the unknown parts as plausible scenarios, a process called determinization.

A sampled world is a possibility, not the discovered truth. With few worlds, chance can affect the ordering of similar candidates.

## Limits

Beyond the current round, search relies on learned value. A bad value estimate can mislead it. Simulations also assume model-driven opponents, who may play differently from people.

Some decisions use separate safeguards against repetition or resource-use conventions. Not every search decision comes only from learning.

A model's improved standalone win rate therefore does not establish stronger search. [The opponent-mixing experiment]({{< relref path="posts/learning-with-opponents.md" lang="en" >}}) produced different outcomes under those two evaluations.

See the [search documentation](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/search-ai.md) and [implementation at this article's reference commit](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/src/dune_imperium/agents/network_search_agent.py). Play requirements are in [choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}}).
