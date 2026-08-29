# Endgame implementation audit

This checklist records the currently executable Endgame boundary. The official
summaries in `docs/rules/` remain the source of truth. Battle-icon specifics
live in [objectives.md](objectives.md); the six Endgame Intrigue cards are
transcribed in [intrigue.md](intrigue.md). Refreshed on 2026-08-30 for the
OQ-001 window implementation.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Entry | Recall enters Endgame after a round when any player has at least 10 VP or the Conflict deck is empty. | Agents are not recalled and the First Player marker is not rotated. |
| Reveal recency | Each round records the order in which players finish Reveal turns. | The order resets only when the next Round Start begins, so it remains available during Endgame. |
| Intrigue window | Clockwise from the First Player, each player gets one window to play any number of Endgame Intrigue cards and match wild battle icons in any order; passing closes that player's window for good (OQ-001 convention). | Only Endgame-timed Intrigue options are offered inside the window; plays use the shared Intrigue play provider on the same frame. |
| Wild battle icon | Every (face-up wild, face-up printed) pair the window owner holds is offered as a separate `match_endgame_wild_icon` action, Objectives included. Matching flips both cards face down and gains 1 VP, and the offers are recomputed after each action. | Which candidate to flip is the owner's free choice; see the OQ-005 resolution in [objectives.md](objectives.md). |
| Safe automatic finish | If no player holds any Intrigue card and no face-up wild pair exists, Endgame finishes immediately and emits the winner; otherwise the windows run and the last pass finishes the game. | Holding any Intrigue card opens the windows even when none of them has an Endgame half: the gate reads only the publicly countable hand of Intrigue cards, never their private timings [Main p. 7]. |
| Final ranking | Players compare VP, spice, Solari, water, garrison troops, then most-recent Reveal in that order. | Reveal recency supplies the FAQ tiebreak after every printed resource tiebreak remains equal. |

## Explicitly blocked or deferred

- The window participation order, the single non-reopening pass, and the free
  ordering of plays and wild matches inside one window are the OQ-001
  project convention, not an official ruling.
- Reveal-turn Plots that would put cards into the hand during Endgame remain
  outside this phase; OQ-015(c) governs their Reveal-time handling.

## Action and replay compatibility

The window adds `pass_endgame_intrigue` and the 19 `match_endgame_wild_icon`
pair templates (Propaganda against every printed-icon Conflict and
four-player Objective) to the fixed catalog since codec version 69; Endgame
Intrigue plays reuse the shared `play_intrigue` templates. The
pre-window decline path and its codec v5/v6 template accounting are
superseded.
