+++
title = "Finding hidden bugs with 10,000-game random completion checks"
description = "A sweep that checks card conservation, deadlocks, observation leaks, and replay at every transition found 46 failures in 20,000 random games and fixed them, and it found more bugs with a heuristic AI and leader-draft games that random play could not reach."
date = 2026-08-30T20:09:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-08-30"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-08.md", "docs/implementation-plan.md", "docs/rules/open-questions.md", "docs/rules/player-turns.md", "src/dune_imperium/simulation/sweep.py", "src/dune_imperium/simulation/invariants.py"]
+++

## What per-card tests miss

While cards were implemented one by one, each got its own tests ([previous entry]({{< relref path="devlog/2026-08-30-full-game.md" lang="en" >}})), but how cards interact is tested only as far as someone thought of it in advance. The sharpest source of trouble in this project is the rule that effects within a turn may be resolved in any order the player chooses (`[Main p. 9]`). After resolving one effect of card A, the condition of card B may have changed, so the more effect combinations there are, the more unexpected states appear. For this, the M7 stage of the implementation plan set as its completion condition that random legal play finishes without deadlock and satisfies the state invariants after every action.

## What was checked

On August 30 `dune-imperium-sweep` was built. It plays a seeded game to the end, checks the following, and reports the game as a failure if anything is off. Games are spread over several processes.

- **Card conservation:** after every transition, personal cards, Reserve (the stack plus live copies), Intrigue, Conflict, contract, and objective cards must each be in exactly one place.
- **Deadlock:** at every point where a player must decide there must be at least one legal action, and the game must end within a step limit.
- **Observation leaks:** at sampled decision points a state is built by shuffling only the deck order, opponents' hand cards, opponents' held Intrigue (`[Main p. 7]`), and the face-down contract bank (`[Main p. 16]`), and every player's observation is compared with the original. A test also pins that the shuffle really changes the state, so the check cannot pass by doing nothing.
- **Replay:** when a game ends, its record is replayed and must give the same state hash.

The first version ran 500 games over the two rulesets (base and CHOAM) at about 49 games per second.

## First run: 46 of 20,000 games

The first run of 10,000 random games per ruleset, 20,000 in all, failed in 46 games (0.23%). The causes fell into five families.

1. **Spy Network deadlock.** The choice this card queues at Reveal offered one recall per placed Spy. If In High Places, resolved first in free order, recalled all the remaining Spies, the mandatory choice had no legal action and the game stopped.
2. **Conditions changing between queueing and resolution.** For Maker Keeper, Wheels Within Wheels, and three cards using a Bene Gesserit Bond (In High Places, Southern Elders, Weirding Woman), paying an Intrigue cost could lower Influence so the queued condition no longer held, and the game died on a "conditional effect is not available" exception.
3. **Self-trash of a card that was already gone.** Cards whose effect trashes themselves (Seek Allies, Subversive Advisor) died on the same exception when an Intrigue trash slot had trashed them first.
4. **Corrinth City selection lost.** If an Intrigue discard cost used up the first discard chosen as the cost, the game tried to discard a card that had already left the hand.
5. **Price is No Object stalling on an acquisition Spy.** Buying a card that places a Spy during an Agent turn left no pending decision to return to after the placement, and the game stopped.

Prepare the Way, fixed in the same shape a day earlier while implementing leaders (a condition changing between placement and resolution, so an action presented as legal failed when applied), had been the first case of this family.

## The principle behind the fixes: judge at resolution time

All five came from trusting the state at queueing time while resolving effects in free order. The official rules let a turn's effects be resolved in a chosen order and say that the order can change a condition's outcome (`[Main pp. 9, 20]`), and Reveal effects are likewise ordered by the player (`[Main p. 12]`). So conditions, self-trashes, and costs are now judged again at resolution time, and if they no longer hold the effect is treated as unavailable instead of raising. A case the rules documents do not cover, a played card being trashed before its effect resolves, was recorded as OQ-022.

OQ-022's ruling on August 30 was "resolve the remaining mandatory effects and count the self-trash instruction as already satisfied". On September 1 that ruling changed. A designer's public answer states that a card already trashed cannot give or activate an effect, so the engine was changed to expire the whole not-yet-activated Agent box. That answer is not in the official rulebook or FAQ, so the entry stays a decided project ruling. The problem the sweep pointed at, a game dying while handling a card that is gone, is still prevented; only the handling changed.

## After the fixes: 0 failures in 20,000 games

After the fixes the same scale (10,000 games per ruleset, 20,000 in all) was run again with every check and replay verification on, and had 0 failures. It took 400 seconds, about 50 games per second, about 8.79 million transitions, with a median of 10 rounds per game. With this the M7 stage of the implementation plan was marked complete.

## Where random play could not reach

Random play does not buy enough cards, so some situations are out of its reach. The same day a heuristic AI was built (a rule-based AI that scores legal actions in the order direct victory points, permanent upgrades, acquisitions scaled by cost, and full deployment), and 1,000 games per ruleset found things the 10,000 random games had not.

- **Special Mission deadlock (CHOAM seeds 97 and 901).** In the Spy placement slot, recalling one's own Spy was assumed to free the post, but a post shared with another player's Spy is not freed by that. The slot kept offering unhelpful recalls until no action remained. The official rules make both placing a Spy and the single preparatory recall when the supply is empty optional (`[Main pp. 11, 20]`), so a decline action was added to every branch and a recall is offered only if it can lead to a placement.
- **Imperium deck exhaustion (6 of 1,000 base games).** The heuristic bought so many cards that the shared deck actually ran out, and the implementation threw an exception for that case. The official documents only say the Row refills from the top of the deck and do not say what happens when it is empty (`[Main p. 13]`), so the only physically forced continuation, leaving the vacated spot empty and continuing with fewer cards, was recorded as a project ruling in OQ-004.

After the fixes, 1,000 heuristic games per ruleset (2,000 in all) and 300 random games per ruleset had 0 failures, and the two deadlock seeds stayed as regression tests with the invariant checks on. Tests went from 770 to 796.

Next came a run with the leader draft, in which six leaders are revealed and picked one at a time in turn order (project ruling OQ-007, not an official rule). In the soak of 500 heuristic and 500 random games per ruleset, CHOAM seed 198 produced a new error. After Treacherous Maneuver was played, an Intrigue trash slot trashed that card, and resolving the choice then tried to trash a card that was already gone. It was the same OQ-022 family; after applying the ruling of the time to this path, the draft soak of 2,000 games had 0 failures. There were 813 tests. During the draft some leaders legitimately remove starting cards, so the reference list for the conservation check was fixed at the end of setup.

## What remained

- The check only walks the paths that random play and a simple heuristic take. On September 1 it gained `--soundness-interval` (actually apply every legal action offered at a decision point and also round-trip it through the action codec), `--coverage-json` (content coverage), and `--rotate-leaders` (leader rotation), and the cross-check run then (7,000 games in all) also had 0 failures.
- A check shows only that errors exist, not that the rules are right. Whether the rules are right has to be settled against the official sentences.

## References

- [Introduction of the M7 sweep](https://github.com/jungcheolseung/Dune-Imperium/commit/3bafc67e)
- [Spy Network deadlock fix](https://github.com/jungcheolseung/Dune-Imperium/commit/f148c14d)
- [Judging drifting conditions and self-trashes at resolution](https://github.com/jungcheolseung/Dune-Imperium/commit/83aa4f5f)
- [Advancing the Agent turn after an acquisition Spy placement](https://github.com/jungcheolseung/Dune-Imperium/commit/24b13e73)
- [Heuristic baseline AI](https://github.com/jungcheolseung/Dune-Imperium/commit/1a449f4f)
- [Special Mission Spy placement fix](https://github.com/jungcheolseung/Dune-Imperium/commit/7a53c8f9) and [Imperium deck exhaustion handling](https://github.com/jungcheolseung/Dune-Imperium/commit/ac4d6d4f)
- [Treacherous Maneuver fix from the leader-draft soak](https://github.com/jungcheolseung/Dune-Imperium/commit/d70b353f)
- [Change of the OQ-022 ruling](https://github.com/jungcheolseung/Dune-Imperium/commit/76dbbf7a)
- [Open questions and rulings](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
- [Agent-turn rules document](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/player-turns.md)
