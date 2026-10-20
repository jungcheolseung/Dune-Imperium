+++
title = "A launcher and feedback from real games"
description = "Add server controls, game presentation and clocks, then use friends’ games and human records to guide improvements."
date = 2026-10-11
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-08"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/server-launcher-plan.md", "docs/evaluation/human-games-2026-10-10.md", "docs/worklog/2026-10.md"]
+++
## Starting the server from a window

A launcher combined settings, start/stop, addresses, and logs. It displayed room links and kept the host PC awake during play, reducing repeated terminal setup.

## Playing and revising

AI turns and combat results became clearer, with adjustable pacing, sounds, and game/seat clocks. Games with friends led to changes in choice displays, turn ending, card viewing, and autosave.

Human saves were also migrated for analysis with the current engine. Two games were compared with AI choices, and 112 positions with agreement between two evaluations were fixed as a problem set.

## What the records mean

Human moves were not all treated as correct. Some positions favored the human choice and others favored the model. This is a regression set from limited records and search-based evaluation, not evidence of an overall human/AI strength ranking.

## References

- [Open the launcher window: settings, start and stop, links, server log](https://github.com/jungcheolseung/Dune-Imperium/commit/4f70c976)
- [human-games-2026-10-10.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/human-games-2026-10-10.md)
- [October 2026 work log](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/worklog/2026-10.md)
