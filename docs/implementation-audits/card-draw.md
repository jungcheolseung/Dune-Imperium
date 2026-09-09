# Personal card draw implementation audit

This checklist records the implemented personal Imperium-card draw and shuffle
boundary. The general deck-building rules in `docs/rules/uprising-systems.md`
remain authoritative.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Existing deck | A draw takes cards from the top of the personal deck in order. | Cards already in hand are not counted toward a Round Start draw of five. |
| Discard reshuffle | If the deck cannot satisfy a draw, the full discard pile is shuffled and placed beneath cards remaining in the deck. | Existing deck cards are therefore drawn before any shuffled discard card. |
| Chance and replay | Every discard permutation is a `ChanceOutcome` and is consumed by the normal engine transition. | Shuffle order is private to the owner; replay injects the recorded permutation instead of sampling again. |
| Round Start | All players complete any required reshuffles before the Conflict is revealed and cards are drawn. | Multiple required shuffles are requested in seat order only as an engine serialization convention; they do not interact. |
| Agent-turn draw | Gather Intelligence, Espionage, and typed board-space draw effects use the same reshuffle transition. | The chance frame is nested above the already-selected continuation, so no later Agent effect can resolve before the draw completes. |
| Short deck | If deck and discard together contain fewer cards than requested, every available card is drawn. | No card is fabricated and cards already in hand or in play are not recycled. |

## Boundaries

- (2026-09-10) Imperium transcription is complete: all 109 identities carry
  `play_data_complete=True`, so every possible later-round hand can take Agent
  and Reveal turns. `tests/unit/content/test_imperium_play_data.py` pins the
  play data. The earlier "three remaining base identities" note was stale.
- The shared decks do not use the personal deck's reshuffle rule (the discard
  shuffled *beneath* the cards left in the deck). The Intrigue deck shuffles
  its discard into a new deck when it runs out (`rules/intrigue_deck.py`, the
  `INTRIGUE_RESHUFFLE` chance frame) [FAQ p. 2]; the Imperium deck has no
  reshuffle and stops refilling the Row once empty (`take_imperium_row_card`
  in `rules/acquisition.py`).
