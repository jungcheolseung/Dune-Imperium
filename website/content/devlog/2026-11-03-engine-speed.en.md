+++
title = "Speeding up the engine without changing results: three rounds"
description = "We tuned the engine three times while checking that the same games end with the same results. Self-play collection became much faster and playing one game a little faster."
date = 2026-11-03T12:00:00+09:00
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
[params]
work_start = "2026-11-02"
retrospective = true
source_ref = "81ca9468"
sources = ["docs/evaluation/2026-11-engine-speed.md", "docs/worklog/2026-11.md", "docs/worklog/2026-10.md"]
+++

## Background

A faster engine shortens collection time for self-play training, and it also shortens the roughly 2.3 seconds a search AI spends on one decision on the play server PC (a Celeron mini PC). There was one condition: **change nothing** about what is shown on screen or about game results. Saves, records and trained models keep working only if the action list, observations and rule behavior stay the same. All three rounds were worked on by cloud sessions, and the coordinating session on the Mac mini ran the engine gate and then merged. (On October 21 we also cut the time of the same games by 6–18% by running state checks only on changed fields.)

## How sameness was checked

- The 360 games recorded on master (200 standard Uprising games, 160 expansion games including the original game and Rise of Ix) were replayed step by step on the new engine, checking that probabilistic decisions, the deciding seat and the order of legal actions, the four seats' observations, events and their visibility, and state summary values were all identical.
- We compared the hash of the 1,440 action-list configurations and the bytes of the observation encoding (in the third round, 1,514,500 of them against master).
- For every timed pair we also checked that the result fingerprint was the same.
- Mac mini gate: full tests, soak, 2,000 recorded games, human saves and the problem set, browser E2E.

## What changed in the three rounds

| Round | Merge | Change |
| --- | --- | --- |
| 1 | November 2 `fc501d97` | Writing state copies straight to slots, remembering the last answer in four functions that repeat the same question within one decision, a fast path for the state hash |
| 2 | November 3 `f68b0dc` | Remembering answers per live state (so concurrently running self-play games do not push each other's memory out), skipping the auto-advance check on a state that has already stopped |
| 3 | November 3 `28695ad8` | The encoder writing the observation array's bytes directly, building observations straight into slots |

## Measured results

The cloud container (4 cores) fluctuates ±20% between measurement pairs, so we measured six alternating pairs of baseline and candidate and report the median of the within-pair ratio. On the Mac mini we measured four pairs during a quiet time. Brackets give the minimum–maximum of the pairs, and above 1 means faster.

| Measurement | Round 1 (Mac mini) | Rounds 2 and 3 together (cloud, against master) |
| --- | --- | --- |
| Heuristic-net self-play collection | ×1.115 [1.108–1.116] | ×1.487 [1.409–1.546] |
| App AI self-play collection | Not measured | ×1.214 |
| Playing one game with the heuristic net | ×1.235 [1.221–1.248] | ×1.038 [0.966–1.117] |
| Playing one original game + Rise of Ix game | ×1.207 [1.178–1.223] | ×1.078 |
| One legal action list (elapsed time) | 0.908 times | 1.032 times (slightly slower) |

After round 1, measuring the play server's search AI seat on the same games on the Mac mini showed time per decision down 10%, from 376 ms to 339 ms.

Two points should be stated honestly. Rounds 2 and 3 cut self-play collection a lot, but playing one game improved only 4–8%, and since only four of six pairs got faster it is hard to say it clearly got faster. Measured alone, the legal action list got slightly slower because of the cost of managing per-state memory in round 2. Round 2's first attempt (remembering only the last 64) gave 1.35–1.40 times for collection but game play stayed at 0.98–1.04 times and the list became 1.10–1.13 times slower, so we changed it.

## Cleanup of unused code

With round 3 we deleted about ten unused rule functions and tables found by the engine review (13 files, 97 lines). Those registered by name or called by a framework, and those in risky files such as server start and stop, were kept. The gate showed all 360 games identical with no declared differences.

## What is left

- The effect of rounds 2 and 3 was not measured on the Mac mini or the play server PC. The Mac mini measurement is to be done after the other game that was running finishes.
- The remaining big costs are walking the choice providers in an Agent effect frame, the check chain of auto-advance, and creating observation objects.
- This time only speed that does not change results was addressed. Search speedups that can change games need a separate gate verdict.

## References

- Round 1 merge ·
  Round 2 merge ·
  Round 3 and code cleanup merge
- Engine speed measurement record ·
  Work log, November
