+++
title = "Measuring and reducing collection overhead"
description = "Compute legal action rows and balance games across workers, with state-copy improvements measured separately."
date = 2026-10-12
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-12"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-10.md", "docs/evaluation/engine-throughput-2026-10-12.md"]
+++
## Measure first

In the retraining configuration at the time, collection dominated each iteration. There were usually only a few legal actions, but computing and sampling a policy head with tens of thousands of rows was expensive.

Sampled policy inference was changed to compute the union of legal rows in a batch. Games with app AI were also distributed more evenly across workers. Reduced and full computations were checked for matching action distributions within tolerance.

## Collection under matched conditions

Three alternating measurements of 32 games with four workers reduced collection time from about 19–21 seconds to 9–10 seconds. This was specific to that machine, model, and concurrent load; it is not a promise of the same speedup for all training or environments.

Random-number consumption and game allocation changed, so the same seed no longer produced the same games across the old/new code. That limitation was recorded for comparisons.

## Engine follow-up

State copying reduced field-passing overhead while retaining invariant checks. App AI reused static card lookups. These changes were measured separately from the collection improvement above, with a comparison tool checking equivalent execution results before timing.

## References

- [October 2026 work log](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/worklog/2026-10.md)
- [engine-throughput-2026-10-12.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/engine-throughput-2026-10-12.md)
