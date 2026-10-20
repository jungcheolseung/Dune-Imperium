+++
title = "Choosing an AI"
description = "The default AI needs no model file; checkpoint and search AI require a compatible trained model."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 50
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/search-ai.md", "docs/remote-play-host-guide.md", "src/dune_imperium/cli/server.py", "src/dune_imperium/launcher/command.py"]
+++
Start with **app AI** at hard, normal, or easy difficulty. No trained model file is required. The local server defaults to hard app AI.

## Types and requirements

| Type | Decision method | Trained model |
| --- | --- | --- |
| App AI | Fixed evaluation of the immediate choice | Not required |
| Heuristic / random | Rule-based score or random choice | Not required |
| Rollout | Simulates candidates and compares a fixed evaluation | Not required |
| Checkpoint AI | Uses the trained model's action scores | Required |
| Search AI | Uses the model to select candidates, then compares simulated outcomes | Required |

The same AI name can behave differently with different rules and models. Historic experiment win rates do not describe current strength in every configuration.

## Using search AI

The host needs a **compatible model file** and extra dependencies. With a model available, run:

```bash
uv sync --locked --extra ui --extra rl --extra train
```

This does not download the model. No public model download is currently offered; use default AI unless you have prepared one separately.

Select the model in the launcher or use `checkpoints/play/search.pt`. In a terminal you can specify the file:

```bash
uv run dune-imperium-server --autosave --search-checkpoint checkpoints/play/search.pt
```

Search AI appears when the server can use the required model and packages. Guests do not need copies; the host runs the AI.

## Thinking time

Search compares candidates and may take longer than default AI. Timing depends on the host PC and game state. Check the thinking indicator.

Read [how search AI chooses a move]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}) for the method, or [troubleshooting]({{< relref path="help/_index.md" lang="en" >}}) if the model is unavailable.
