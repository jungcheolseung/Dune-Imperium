+++
title = "Investigating a plateau and correcting evaluation"
description = "Use a control run to reassess rank rewards and fix training-time evaluation reading the opponent’s results."
date = 2026-09-22
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-18"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md", "docs/evaluation/m10-2026-09-22.md"]
+++
## Separating causes

A perceived learning plateau prompted changes to learning rates and rewards. A rank-reward run improved over its start, but a control trained for the same duration improved similarly. The direct win-rate comparison did not establish a clear benefit from rank rewards.

A ladder of checkpoints then showed gains concentrated early. Adaptation to changed rules was a plausible interpretation, but its causal role was not isolated. Earlier claims of continued growth or a complete plateau were revised.

## Evaluation itself had a bug

Training-time evaluation read the first checkpoint row in name order, which could belong to the opponent. Reproducing the same inputs through the tournament CLI revealed the mismatch. Evaluation was changed to select the exact tested model.

Separate post-training tournaments and paired comparisons were unaffected. This work reinforced the distinction between progress displays and final evidence, and the need for control runs and multiple time points.

## References

- [Refute the rank reward with its control arm](https://github.com/jungcheolseung/Dune-Imperium/commit/6b96e510)
- [September 2026 work log](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/worklog/2026-09.md)
- [m10-2026-09-22.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-09-22.md)
