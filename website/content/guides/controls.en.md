+++
title = "Controls, saves, and updates"
description = "Choosing cards and spaces, ending turns, undoing actions, saving, and version compatibility."
date = 2026-10-20
lastmod = 2026-11-03
draft = false
weight = 40
[params]
source_ref = "81ca9468"
sources = ["README.md", "src/dune_imperium/server/static/ui_text.js", "src/dune_imperium/server/turn_end.py", "src/dune_imperium/cli/server.py", "docs/remote-play-host-guide.md", "docs/remote-play-player-guide.md", "docs/human-records.md"]
+++
The interface identifies the player who must decide and the available actions. If progress seems stuck, check for remaining choices or an **End turn ▶** or **Confirm ▶** button.

## Taking a turn

On an Agent turn, choose a card from your hand and a board space, then resolve remaining choices. Highlighted cards and spaces indicate available options. `Esc` can cancel a selection.

On a Reveal turn, reveal your cards and choose purchases using the remaining Persuasion. Press **End turn ▶** when finished.

Some selections remain pending until **Confirm ▶** sends them. You may also need to respond outside your own turn; follow the current prompt.

When ending the turn or picking another row would lose an effect you have not used yet, a ⚠ line warns you first: for example a card's remaining Agent effect, troops left in the garrison, the Persuasion left and how many cards it could acquire, or Agents not yet placed.

In games with Arrakeen Scouts, the receiving player presses **Collect** to receive revealed secret choices, auction winnings, and shares from events and missions. A Collect window opens at once, even inside another player's action, and waits for that player. Secret choices show the round number in which their effect comes.

## Undo

Undo is available only within the permitted part of your uninterrupted actions. New random outcomes or newly revealed hidden information can prevent it. **Not every action can be undone before the end of a turn.** Use the interface's undo availability and confirmation controls. A finished game cannot be undone, and this turn's Conflict units that an effect has used (for example the units Seize Production counted) cannot be withdrawn.

## Saving and continuing

| Start method | Autosave |
| --- | --- |
| Launcher, local or remote | Enabled by default; check settings |
| Terminal, remote server | Enabled by default unless explicitly disabled |
| Terminal, local server | Add `--autosave` to enable |

Autosave updates on turn handover. Before stopping, also use **Save** locally or **Save now** in the host panel to reduce the chance of losing pending choices.

The default save folder is **`saves/` inside the project folder on the server PC**. Guests' browsers do not hold the game save files.

Restart the server and load from the save list. Restoring a remote game changes its room link; the host sends the new one and players rejoin their original seats.

## Before updating

Finish ongoing games with the same code and models where possible. A rules or action-version change may stop an old save from loading directly. Games with AI seats may also fail to load after an update that changes AI behaviour, because loading replays the AI's moves and compares them with the record.

Keep the save folder and existing model files when moving or cleaning the project. Do not immediately delete the old model after replacing it; existing saves may depend on it.

Tools can migrate earlier games into records for the current engine, but this does not guarantee resuming every old save in the current play server. See game records.

## More information

The in-game help explains icons, seat displays, and shortcuts. See [joining a room]({{< relref path="guides/joining.md" lang="en" >}}) to return to your seat and [help]({{< relref path="help/_index.md" lang="en" >}}) for startup problems.
