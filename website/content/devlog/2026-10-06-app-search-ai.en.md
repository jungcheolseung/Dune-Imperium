+++
title = "App-style AI and search AI as play seats"
description = "Add rule-based opponents and browser seats that compare model-guided simulations."
date = 2026-10-06
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-05"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/app-ai-2026-10-05.md", "docs/evaluation/m10-2026-10-06.md"]
+++
## A play and evaluation opponent

App-style rule-based AI was implemented and exposed in the seat selector. It covered Uprising and supported expansion decisions, and served as a training/evaluation opponent. App AI here means this project's implementation.

## Search in the interface

Search selects policy candidates and compares them across plausible hidden states. Server startup accepted a model file, the browser offered search seats, and the interface showed which seat was thinking.

Training was adapted to the play interface's expansion configuration and leader draft, with app AI in some games. That run improved over the earlier model, but could not separate rule adaptation from opponent mixing.

## The next experiment

A self-play-only control was needed to isolate opponent mixing, and was run the next day. The [technical article]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}) explains search separately.

## References

- [app-ai-2026-10-05.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/app-ai-2026-10-05.md)
- [Seat the server's own search AI by the kind "search"](https://github.com/jungcheolseung/Dune-Imperium/commit/83a381b6)
- [m10-2026-10-06.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-10-06.md)
