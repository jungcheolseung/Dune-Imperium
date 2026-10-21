+++
title = "Splitting actions into card, space, effect, and target steps"
description = "Agent turns and pending effects became smaller choices and rewards are paid icon by icon, raising the action codec to v150."
date = 2026-10-20T23:40:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-19"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/stage-b-plan.md", "docs/composed-effects-plan.md", "docs/worklog/2026-10.md"]
+++
## One action carried too much

The previous stage moved card effects into ability records, but the names and units of the actions exchanged by the AI, the browser, and save files stayed the same. A single Agent-turn action combined the card, space, graft, infiltrated post, discount, and cost choice, and made up 72% of the 36,385-row action list with every option enabled.

Conflict rewards and completed contracts were paid at once as per-resource totals. Actions doing the same job also had different names per source (20 trash variants, 41 declines, 15 empty confirmations, and so on).

## Changes

- **Agent turn:** two steps, choosing the card and then the space.
- **Reward payout:** Conflict rewards and completed contracts are paid one printed icon at a time, in the order the receiving player chooses.
- **Pending effects:** the player first chooses which effect to use, then its target. Declines and "nothing to choose" confirmations share one name regardless of source. Research icons, deferred card draws, and Reveal gains are one effect per printed item.
- **Hidden information:** a choice in progress is visible only to that player (observation v33).

The all-options action list shrank from 36,385 to 4,311 rows, and the action codec became v150. Two points the official documents leave open, who sees and can undo a half-made choice and the order of icons within one reward line, were settled as project conventions and recorded with their reasoning as open questions (OQ-111, OQ-112).

During the work, research icons and deferred draws had at one point been merged per space or source. That went beyond the decision agreed in advance, so they were split per printed item and the case was added to the lessons document.

## Verification

Every sub-stage ran the full check set: unit tests and static checks, 900 random and heuristic games (including an action-list round trip), the same 200 games played on the old and new engines (intended differences listed), replay of 2,000 old records, problem-suite re-mining, and 68 browser E2E scripts. Higher-risk steps such as hidden information and engine events also had an independent review.

The heuristic AI and app AI were kept choosing in the old engine's order, and each sub-stage played the same games as the previous commit on the same seeds.

Migrating the 2,000 old records to the new action units and replaying them: 1,568 match at every compared point, 431 differ for a while and end in the same state, and 1 diverges. In that game, paying rewards icon by icon in order let another effect send the last troop in supply to the Conflict before the contract reward, changing the Conflict ranking.

## Remaining points

- Save files from earlier codec versions cannot be loaded from v150 on.
- The play network had learned only 84 of the 4,311 new action rows. Decisions on unlearned rows fall back to the heuristic, so search AI seats are weaker on the v150 engine until retraining. The first retraining attempt is covered in the [next entry]({{< relref path="devlog/2026-10-21-retrain-teacher.md" lang="en" >}}).

Merged into master on October 20 and pushed to the remote repository on October 21.

## References

- [stage-b-plan.md: design, sub-stage implementation, and measurements](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/stage-b-plan.md)
- [Merge stage-b: the action-shape stage B, codec v150](https://github.com/jungcheolseung/Dune-Imperium/commit/c133be07)
- [open-questions.md (OQ-111, OQ-112)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
- [docs/worklog/2026-10.md](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/worklog/2026-10.md)
