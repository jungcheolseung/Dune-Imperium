+++
title = "Mixed-opponent training and learning from search"
description = "Check whether stronger direct play improves search, and stop a later distillation experiment before final evaluation."
date = 2026-10-09
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-07"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/m10-2026-10-07.md", "docs/evaluation/exit-v2-2026-10-08.md"]
+++
## Two runs from the same start

On October 7, mixed app-AI training and self-play-only training each ran 1,000 iterations from the same model, rules, and seeds. Mixed training was stronger in direct policy matches.

The initial 200-game search comparison went the other way, so the play model was not immediately replaced. A follow-up did not establish a clear search difference; the initial result was not treated as a general conclusion. Conditions and numbers are in the [experiment article]({{< relref path="posts/learning-with-opponents.md" lang="en" >}}).

## Search choices as training data

A second expert-iteration experiment prepared to teach the model search's decisions. It separated agreement on training games from unseen games, and separated policy and value during search comparisons.

After a pilot, work stopped on October 9 with 510 collected games. Final student-strength evaluation was not run. There is therefore no result establishing stronger AI from this attempt. Collection/training tools and the stopping point were retained.

## References

- [m10-2026-10-07.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-10-07.md)
- [exit-v2-2026-10-08.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/exit-v2-2026-10-08.md)
