# Endgame implementation audit

This checklist records the currently executable Endgame boundary. The official
summaries in `docs/rules/` remain the source of truth.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Entry | Recall enters Endgame after a round when any player has at least 10 VP or the Conflict deck is empty. | Agents are not recalled and the First Player marker is not rotated. |
| Reveal recency | Each round records the order in which players finish Reveal turns. | The order resets only when the next Round Start begins, so it remains available during Endgame. |
| Final ranking | Players compare VP, spice, Solari, water, garrison troops, then most-recent Reveal in that order. | Reveal recency supplies the FAQ tiebreak after every printed resource tiebreak remains equal. |
| Safe automatic finish | If no player holds any Intrigue card and no face-up wild battle icon can match another face-up icon, Endgame immediately enters `FINISHED` and emits the winner. | A possible Propaganda wild match blocks finalization even when nobody holds Intrigue. |
| Wild battle icon | With no held Intrigue and exactly one possible face-up pair, Propaganda's owner chooses whether to match it. Matching turns both cards face-down and gains 1 VP; declining is recorded without changing either card. | Two or more possible pairs remain blocked under OQ-005. |

## Explicitly blocked

- Any held Intrigue card conservatively blocks automatic finalization until
  Intrigue timing/type/effect metadata is transcribed. This includes cards that
  will later be known not to have an Endgame effect.
- Endgame Intrigue priority, pass behavior, and its ordering relative to wild
  battle-icon matching remain governed by OQ-001.
- Endgame wild battle-icon matching with multiple possible pairs remains
  deferred under OQ-005.

## Action and replay compatibility

The decline action and every valid Propaganda-to-printed-icon pair add 20
templates. The fixed catalog changes from 534 entries in codec version 5 to 554
entries in version 6. Later personal-card content advances the current replay
default to codec version 10 without changing these Endgame templates.
