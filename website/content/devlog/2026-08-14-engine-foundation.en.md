+++
title = "Rules specification, a one-round engine, and the first action codec"
description = "Official rules were written up as documents and a replayable engine kernel was built. In three days one round ran end to end, and a fixed action codec and a PettingZoo adapter were connected."
date = 2026-08-14T15:42:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-08-12"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/implementation-plan.md", "docs/rules/README.md", "docs/rules/sources.md", "docs/rules/information-visibility.md", "scripts/official-rule-sources.json"]
+++

## Fixing the target first

This was a fresh start unrelated to [the 2023 early attempt]({{< relref path="devlog/2023-04-10-initial-code.md" lang="en" >}}). On August 12 the toolchain moved to Python 3.14 and uv, and the rules documents and the implementation plan were committed before any engine code. The first documentation commit is 16 files and 2,163 lines: 13 rules documents, the implementation plan (377 lines), a README, and the repository instructions.

- **Target:** the four-player Uprising game. The first complete scope is the base game with the CHOAM module off. Contracts are an optional mini-expansion, so they were to be added afterwards as a rules option.
- **Rule-source policy:** rulings rest only on the official Main rulebook, the board space guide, and the FAQ (January 13, 2025 edition), and every item in the documents carries a page citation such as `[Main p. N]`. Orders and defaults the official documents do not settle are not decided silently in code; they go into `open-questions.md` first. The card site is used only as a reference for identifying cards.
- **Reproducible official sources:** the official PDF addresses and SHA-256 values are pinned in a list, and a tool produces page-indexed text from them. The rulebook PDFs themselves are not kept in the repository.
- **Milestones:** from the rules specification (R0) and the development skeleton (M0) through one round (M3), the learning interface (M4), base content, full-game verification, CHOAM, evaluation, training, and the human-facing screen, the plan lists the order and the completion conditions. One condition says engine implementation does not start until every item of the rules specification has been classified.

## The engine kernel

These structural decisions from the plan have held ever since.

- **State and observation are separate:** `GameState` holds everything, and `PlayerView` holds only what one player may see. The point is that private information (opponents' hands, deck order, opponents' Intrigue cards) cannot leak into an observation (August 12, "Add redacted player observations").
- **Decision stack:** the card, space, payment, and target of an Agent turn are not combined into one action. They are split into small choices and stacked as `DecisionFrame`s.
- **Recorded chance:** every random event passes through one place. Not only the seed but the actual outcomes are recorded and injected on replay, so a game can be replayed even if the random-number implementation changes. The completion condition of this stage (M1) was that replaying the same input yields the same state hash.
- **Reward design stays outside the core:** reward shaping for training was kept out of the rules core.

On August 12 and 13 the four-player board (22 spaces), the official starting components, seeded randomization of setup, and the shared deck lists went onto this structure. The observation boundary has its own rules document, `information-visibility.md`.

## The one-round vertical slice

On August 13 and 14 the following were implemented one by one and joined into a round: Round Start, Agent placement, Reveal turns, Imperium Row and Reserve acquisition, combat ranking, Conflict tier 1, 2, and 3 rewards (including optional payments, card trashing, and Spy placement), Makers and Recall, the Intrigue priority loop during combat, influence and alliances, and the Shield Wall. August 13 alone has 30 commits. While reviewing Conflict rewards that day, an error in trashing Reserve cards was found and fixed.

Two kinds of checks were made. A seeded random-round runner and a debug CLI were built, and three rulebook examples (an Agent turn, a Reveal turn, and round end; `[Main pp. 11, 13, 15]`) were turned into fixed scenarios and passed. The one-round stage was marked complete at 14:17 on August 14.

## The learning interface and the next rules, the same day

Marking one round complete was not the end of that day. Also on August 14:

- **Fixed action codec (M4):** a list giving every single choice a fixed integer ID, separate from the engine's structural actions, and a legal-action mask of the same width. At the time the plan was updated the codec was v6 with 554 actions.
- **PettingZoo adapter:** an AEC-style environment as an optional install (`rl`), passing PettingZoo's `api_test` and `seed_test`. The observation and `info` do not expose the full `GameState`. An episode was still one round.
- **First systems of the next stage (M5):** High Council and Swordmaster, critical-location control bonuses, Spy Infiltrate and Gather Intelligence, the Reveal order within a round, final standings with the official tiebreaks, automatic finish for an Endgame without Intrigue cards, and reshuffling the personal deck when it runs short, handled as replayable chance.

The plan calls this stage "early validation of the RL interface". Its completion condition was to run one round in an AEC loop, before card content grew, and to confirm that the full state does not leak into what the policy observes.

## What remained

The state at the end of the scope of this entry, the afternoon of August 14, is "R0 and M0 through M4 complete, M5 in progress". One round worked, but not a full game. Most card effects were not yet transcribed, and Endgame Intrigue and the wild battle icon choice were deferred until open question OQ-001 and card transcription. Card transcription and the full game continue in [the next entry]({{< relref path="devlog/2026-08-30-full-game.md" lang="en" >}}).

## References

- [Official rules and implementation plan](https://github.com/jungcheolseung/Dune-Imperium/commit/fe29f63b)
- [Official rules preparation tool](https://github.com/jungcheolseung/Dune-Imperium/commit/2c3ec01c)
- [Recording chance outcomes for replay](https://github.com/jungcheolseung/Dune-Imperium/commit/4f41ed91)
- [Observations that hide private information](https://github.com/jungcheolseung/Dune-Imperium/commit/9e79499c)
- [One-round completion mark](https://github.com/jungcheolseung/Dune-Imperium/commit/f1941ea0)
- [Fixed action codec](https://github.com/jungcheolseung/Dune-Imperium/commit/69140dc1) and [PettingZoo adapter](https://github.com/jungcheolseung/Dune-Imperium/commit/a0ae35ce)
- [Implementation plan at the end of August 14](https://github.com/jungcheolseung/Dune-Imperium/blob/a6f1449a/docs/implementation-plan.md)
- [Rules specification overview](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/README.md) and [information visibility](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/information-visibility.md)
