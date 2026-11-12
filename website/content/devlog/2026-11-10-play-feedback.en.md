+++
title = "Feedback from friends' games: choice wording, automatic passes, specimen returns, Slig Farmer"
description = "We fixed the friction from games played with friends in three rounds. Choice rows now show the card's wording, the server passes Intrigue questions that leave nothing to choose, and the windows where specimens can be returned just before recruiting were widened."
date = 2026-11-10T09:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-08"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/worklog/2026-11.md", "docs/rules/open-questions.md", "docs/rules/immortality.md", "docs/rules/combat-and-round-end.md"]
+++

## Background

On the night of November 8 the user played a remote game with friends and passed on several complaints. One was wrong rule behavior; the rest were screens that made it hard to tell what was being chosen, or questions asked when there was nothing to choose. They were fixed on three branches, and each batch passed the engine gate before merging.

## Slig Farmer: both effects must be usable (merge `f57830d4`, codec v168)

The user: "The Slig Farmer card — shouldn't I be able to both get money for each Agent icon on the grafted card and pay 5 Solari for Tleilaxu? I did one and the other option disappeared." The engine offered two branches for this box, "take the Solari and drop the payment" and "take it, then pay 5", so taking the Solari first made the payment vanish. It came from an earlier engine cleanup, not from a user decision.

All the effects of a card's Agent box may be carried out in any order `[Main p. 9]`, an arrow cost is optional `[FAQ p. 3]`, and resources gained from the first effect can pay the second's cost (OQ-058). So the box was split into two icons. The Solari line is mandatory; paying 5 Solari for Tleilaxu is optional, usable before or after the line, and lapses at turn end if unused. A full survey found no other Agent box of the same shape. The user's game (1,011 moves) replayed through a record bridge to the same end.

## Five pieces of feedback and their neighbors (merge `e8ffbe69`, codec v169)

1. **Intrigue line wording.** The choice rows of Intrigue cards whose lines are used separately read "Use effect line — section: 1". Now the line's card text appears, and the log line shows the text too. A sweep of every row the server sends confirmed these were the only rows that showed only a number.
2. **Research space display.** The engine was right. Every research step in nine of the user's saves matched, and "what is shown differs from what you get" was the rule's chain: from a research icon space you go straight on to the next space `[Immortality p. 6]`. So the row now shows the arrival space ("Research track 3-1 (research) → research track 4-2 (Tleilaxu)"). A hint from the user led to the real cause as well: the research-space icon row repeated the icon description ("specimen, specimen") and did not say which space it was.
3. **Zero amounts.** A card that gains 1 spice on Reveal was also drawn with "Solari 0"; now only what is gained is drawn.
4. **Automatic Combat Intrigue pass.** A seat with units in the Conflict may play Combat Intrigue cards or pass `[Main p. 14]`. If it holds zero Intrigue cards, has played none at this opportunity and is offered only the pass, the server passes for it. The engine still asks and records the pass, so the codec, observations, records and AI are unchanged. A step the server passed is not counted as the seat's own action in the "new since" highlight.
5. **Card info popover.** A card with a picture shows only its title and picture, keeping the ruling notes. Without a picture, the text is shown.

As neighboring cases, the rows now note the draw after passing the second gene marker on the research track and "no effect" at the end of the Tleilaxu track. We also checked whether returning specimens during combat matters for a seat with zero cards that holds specimens. It does when troops are recruited in the reward window (OQ-030: an out-of-turn recruit's shortfall is not made up later), so following the user's choice "return in the reward window too + pass", the seat's own Conflict reward window offers the specimen return (OQ-050 re-ruled).

## Follow-up: Endgame and winner-window passes, specimen returns out of turn (merge `a95ab1b2`, codec v171)

- **Endgame Intrigue.** If a human seat has no Endgame Intrigue to play and no Objective pair, the server passes for it `[Main p. 15]`.
- **The winner's window.** In the original game and Ix, if the sole winner has zero winning Intrigue cards and only the close button is left, the server presses it `[FAQ p. 4]` (OQ-121). If the reward drew cards, it asks, because a drawn card can be played at once. What used to take two presses is now one turn-end press.
- **Specimen returns.** The rules say specimens can be returned to the supply at any time, which helps when there are no troops left in the supply `[Immortality p. 8]`. The user chose to widen it ("contract + (a) + (b)"), so the return is offered in 18 kinds of out-of-turn windows where recruiting can happen (Contract rewards, Tech acquisition, Shipping rewards, the original game's Emperor space bonus, Combat Intrigue and others). Arrakeen Scouts missions and bids keep only the existing top-up (OQ-074). In a survey of 900 Immortality games, no seat holding specimens recruited without returning them and lost troops.
- An independent review found that specimens must not count toward recruiting until they are back in the supply, or the AI could pay a cost trusting its specimens and lose troops. This was fixed.

## Verification and what is left

- Each batch passed the engine gate (pytest, identity of 360 games with declared differences, soak, 2,000 recorded games, saves and problem sets, 85 E2E scripts), and the AI seats played the same moves as master on the same seeds. Human saves were converted to each new codec and all replayed.
- Another tool (Codex) and an independent Claude review ran for each batch, and every finding was applied.
- A seat that played its last card at this opportunity still presses its own pass (because of confirming and undoing that card).

## References

- Slig Farmer ·
  Five pieces of feedback ·
  Follow-up
- [Open questions](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/open-questions.md) ·
  [Immortality rules](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/immortality.md) ·
  [Combat and round-end rules](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/combat-and-round-end.md) ·
  Work log, November
