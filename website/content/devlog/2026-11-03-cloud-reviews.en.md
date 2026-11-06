+++
title = "Four independent reviews: engine, rule tests, hidden information, server security"
description = "We ruled on and fixed the findings of four reviews handed to cloud sessions. There was one gap that leaked hidden information and a connection problem that could stop the server."
date = 2026-11-03T18:00:00+09:00
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
[params]
work_start = "2026-11-02"
retrospective = true
source_ref = "81ca9468"
sources = ["docs/reviews/2026-11-cloud-engine-review.md", "docs/reviews/2026-11-cloud-rule-test-gaps.md", "docs/reviews/2026-11-cloud-hidden-info-audit.md", "docs/reviews/2026-11-cloud-server-security.md", "docs/worklog/2026-11.md"]
+++

## Background

On November 2 the user chose four jobs to run separately from the Mac mini using the remaining cloud usage: an independent engine review, engine speed, test and code cleanup, and documentation cleanup. A rule-test gap survey, a hidden-information audit and a play-server security review were added. The review sessions did not fix the engine directly and left reports; the fixing was done by the coordinating session on the Mac mini after rulings. The speed work is [written up separately]({{< relref path="devlog/2026-11-03-engine-speed.md" lang="en" >}}).

## Engine review: two rulings, one document, one server fix

The review re-read the engine merges from October 29 to November 2 (P7, P8, P8-1, Scouts Collect, the recall floor) and ran 1,000 games. It found no engine defect that contradicts a rule sentence and no hidden-information leak, and left seven low-grade findings. The first four were handled in the November 3 merge (`ac420918`, codec v164).

1. Units that a Scouts mission puts straight into the Conflict were not counted as "units deployed this turn". OQ-077 was extended to count them (designer ruling "a moment in time when there are 3 units in the conflict that were deployed to the conflict this turn"). The user also made Baron's Masterstroke and Rise of Ix's Desert Ambush count them.
2. The engine was correct that a sandworm does not double a victory share such as Strategic Push. The doubling applies only to the reward of a Conflict card `[Main p. 14]`. Only documentation and a test were added.
3. Whether a Sardaukar Commander in the garrison can take part in missions that send troops (Send for Aid, Genetic Research) is answered by neither the official documents nor the app, so it was allowed under the new ruling OQ-166 (a project convention; the user chose option (a)).
4. In Fremen Exchange, the window where one's own troops are lost was being classified by the server as another seat's response; this was fixed.

The remaining three (an outdated comment, a source line, unused code) were handled in the November 3 code cleanup. Before the merge, 200 Uprising games and 160 expansion games were compared step by step against the engine before the change, and the 6 games that differed were all games in which a seat chose the new option of sending a Sardaukar Commander.

## Rule-test gaps: 0 defects

About 740 sourced rule behaviors were compared with the tests, and 28 new test functions were added for those without tests. All passed on the current engine, so there were no defect candidates.

## Hidden-information audit: one gap

37 games (38,864 steps, 1,248 undos) were compared at each decision in two ways, and everything the server sends to seats and spectators was checked.

- **Gap (low to medium).** In Scouts games, the display of the row where Ilesa Ecaz sets cards aside revealed, before the Scouts phase, whether another seat's secret choice was due to be resolved this round. It was closed by always placing the same single pause between the setting-aside and the Scouts phase (OQ-103 6).
- **Latent defect.** A finished game still had an undo window (unreachable at the time). A finished game now undoes nothing (OQ-010).
- That a host can see hands through a replica loaded from a save was only recorded, as trust by design.

The fix merge (`94592486`, codec v165) confirmed in a 1,200-game Ilesa + Scouts soak that one pause occurs per round (11,757 times), and the 12 matching records replayed through the existing pause bridge.

## Server security review: connections could stop the server

In a review assuming friends using Tailscale, the access-check logic had no gaps, and ten findings were reproduced against a real server. The largest was that holding connections open after sending only half a header could use up file descriptors and stop every game. The November 3 merge (`c3c19157`) fixed six of them and the Host check.

- A request must arrive in full within 10 seconds, with limits on the number of connections and on connections per address. Bodies are accepted up to 64 KiB.
- The admin key must be at least 16 characters of letters, digits, `-` and `_`, and the key is not printed to logs that are not a terminal. The admin link can be wrong five times per minute. The admin cookie is a 30-day session signed with the key, not the key itself, so after the update the host opens the admin link once again.
- A remote server does not open the API documentation page, does not cache game responses, and rejects unknown Host names.

Before the fix, while 300 attacking connections were reopened for 20 seconds, 0 of 20 honest requests were answered and the log grew by 6,615 lines. After the fix all were answered and the log had 30–40 lines. A request declaring 64 MiB was rejected in 0.01 seconds. A read-only review by another tool (Codex) found four more, such as closing connections that pass the time limit, and all were fixed.

## Cleanup work

- Test and code cleanup (`af7c5cd1`): 83 Ruff errors in `scripts/` were fixed without changing behavior. On 4 cloud cores the full test run went from 870 seconds to 450 seconds. The effect on the Mac mini is to be measured again.
- Documentation cleanup (`7392ec56`): numbers in 22 documents, the status of finished plans and broken links were aligned with the code. Rule sentences were not changed.

## What is left

- Of the server security findings, two where replay review and undo of finished games use server CPU for a long time were deferred until after the server session code work.
- Opening the server port only to invited accounts through the Tailscale access policy was left as the host's task.
- The audit found what it found in the chosen games and scenarios. Not finding something is not proof that there are no defects.

## References

- Engine review fix merge ·
  Rule test and hidden-information audit merge ·
  Hidden-information fix merge ·
  Server security hardening merge
- Test and code cleanup ·
  Documentation cleanup
- Reports: engine ·
  rule tests ·
  hidden information ·
  server security
