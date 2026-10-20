+++
title = "Browser play, saves, replay, and undo"
description = "Build the human interface and add tools for continuing games and reviewing earlier choices."
date = 2026-09-03
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-08-30"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-08.md", "docs/worklog/2026-09.md"]
+++
## A human-playable interface

Heuristic AI and leader draft were connected to a FastAPI session server and an HTML/CSS/JavaScript interface. The first full browser games used text cards and action buttons. The browser displayed the server's view and choices rather than adjudicating rules itself.

## Saving and review

Saving/loading and finished-game review arrived on August 31. Tests compared continuation after loading with an uninterrupted game. Since records may contain private deck orders, raw save files were not simply sent to the browser.

Early September brought action logs, undo, and a more board-centered display. Information boundaries were reviewed alongside undo, so newly revealed information could not be freely reversed.

## Verification

An actual server and Chromium covered game creation, completion, intermediate saving/loading, and finished-game navigation. Combining engine tests with browser checks became a continuing workflow.

## References

- [Play a full game in the browser with text cards](https://github.com/jungcheolseung/Dune-Imperium/commit/42be8833)
- [Save, load, and review games in the browser](https://github.com/jungcheolseung/Dune-Imperium/commit/e44900ae)
- [Add undo buttons and a live action log to the browser UI](https://github.com/jungcheolseung/Dune-Imperium/commit/993bf11d)
