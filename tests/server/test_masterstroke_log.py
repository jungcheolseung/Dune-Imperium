"""The Baron's Masterstroke Factions stay his alone in the server's log.

The original game's Baron Harkonnen chooses two Factions in secret before
the first round and reveals them when his own turn's deployment stands four
troops in the Conflict (docs/rules/imperium-base.md 14, OQ-115). The live
log seals each pick (``SEALED_ACTION_IDS``): another seat sees that he chose
and ``(비공개)`` for which, the Baron his own Faction, and a finished game's
review everything (OQ-010 ruling 4). ``known_card_seats`` lists the unrevealed
pair under ``masterstroke_id``, so a pick can be taken back but the step
that reveals it cannot.
"""

from dataclasses import replace
from typing import Any

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.core import ChanceDecision, ChanceResolver, DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import known_card_seats, masterstroke_id
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.masterstroke import reveal_masterstroke
from dune_imperium.server.session_log import (
    SEALED_ACTION_IDS,
    LoggedStep,
    log_step,
    reveals_hidden_information,
)
from dune_imperium.server.sessions import _log_entry_json

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
BARON = "baron_vladimir_harkonnen"
SEATS = (BARON, "paul_atreides", "duke_leto_atreides", "glossu_rabban")


def _pick(faction: str) -> DomainAction:
    return DomainAction("choose_masterstroke_faction", 0, (("faction", faction),))


def _picked(
    engine: UprisingRulesEngine, state: GameState, faction: str
) -> tuple[GameState, LoggedStep]:
    action = _pick(faction)
    result = engine.apply(state, action)
    return result.state, log_step(state, result.state, action, result.events)


def test_another_seat_s_log_hides_each_masterstroke_pick() -> None:
    assert "choose_masterstroke_faction" in SEALED_ACTION_IDS
    engine = UprisingRulesEngine(leader_ids=SEATS)
    state = engine.reset(CONFIG, 3)
    assert state.phase is GamePhase.SETUP
    for count, faction in enumerate(("emperor", "fremen"), start=1):
        state, entry = _picked(engine, state, faction)
        assert entry.sealed
        own: Any = _log_entry_json(0, entry, 0, finished=False)
        assert own["arguments"] == {"faction": faction}
        assert {
            "kind": "masterstroke_faction_identity",
            "payload": {"faction": faction, "player": 0},
        } in own["events"]
        for seat in (1, 2, 3):
            other: Any = _log_entry_json(0, entry, seat, finished=False)
            assert other["action_id"] == "choose_masterstroke_faction"
            assert other["arguments"] == {"faction": "(비공개)"}
            # That he chose is public; the Faction's own event is his alone.
            kinds = [event["kind"] for event in other["events"]]
            assert "masterstroke_faction_identity" not in kinds
            assert {
                "kind": "masterstroke_faction_chosen",
                "payload": {"count": count, "player": 0},
            } in other["events"]
            assert faction not in str(other)
        review: Any = _log_entry_json(0, entry, 1, finished=True)
        assert review["arguments"] == {"faction": faction}


def test_a_pick_can_be_taken_back_but_the_reveal_cannot() -> None:
    engine = UprisingRulesEngine(leader_ids=SEATS)
    state = engine.reset(CONFIG, 3)
    state, first = _picked(engine, state, "emperor")
    assert known_card_seats(state)[masterstroke_id(0)] == frozenset({0})
    # The Baron's own secret, chosen by him: nothing any seat learned. (The
    # second pick opens the first round, whose Conflict and hands are.)
    assert not first.reveals
    state, _ = _picked(engine, state, "fremen")
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    assert known_card_seats(state)[masterstroke_id(0)] == frozenset({0})

    baron = replace(state.players[0], units_deployed_turn=4, units_deployed_peak=4)
    due = replace(state, players=(baron, *state.players[1:]))
    revealed = reveal_masterstroke(RuleResult(state=due)).state
    assert revealed.players[0].masterstroke_revealed
    assert masterstroke_id(0) not in known_card_seats(revealed)
    # The rules reveal the pair, not the Baron, so even his own step that
    # falls into it is a reveal: an undo past it would let the table un-see it.
    assert reveals_hidden_information(due, revealed, 0)
