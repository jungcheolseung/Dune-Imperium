"""Ilesa Ecaz's set-aside card and Hundro Moritani's Intelligence peek stay
their own in the server's log.

docs/rules/rise-of-ix.md 13: "Hundro Moritani의 Intelligence | Hundro 좌석이
Intrigue 덱 맨 위 카드 | ... 갖는 카드는 손(숨김)" and "Ilesa Ecaz의 따로 둔 카드 |
Ilesa 좌석 | 둘째 turn에 공개". The live log seals Ilesa's pick
(``SEALED_ACTION_IDS``): another seat sees that she set a card aside and
``(비공개)`` for which, she her card, a finished game's review everything
(OQ-010 ruling 4). ``known_card_seats`` lists her pick under
``set_aside_id`` while the card is aside, so the pick can be taken back but
the step whose rules return the card cannot, her own included. Hundro's kept
card is hidden in his hand, so the log redacts its id as it does Imperium
Ceremony's (``hidden_argument_values``), and the cards he looked at reach no
other seat.
"""

from dataclasses import replace
from typing import Any

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents import HeuristicAgent
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.observation import known_card_seats, set_aside_id
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.server.session_log import (
    SEALED_ACTION_IDS,
    LoggedStep,
    log_step,
    reveals_hidden_information,
    undo_window,
)
from dune_imperium.server.sessions import _log_entry_json

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
OTHERS = ("glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


def _logged_whole(
    engine: UprisingRulesEngine, state: GameState, whole: DomainAction
) -> tuple[GameState, list[LoggedStep]]:
    """Apply ``whole`` step by step, logging each step as the server does."""

    entries: list[LoggedStep] = []
    while True:
        rows = engine.legal_actions(state, whole.actor)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        result = engine.apply(state, row)
        entries.append(log_step(state, result.state, row, result.events))
        state = result.state
        if left == 0:
            return state, entries


def _ilesa() -> tuple[UprisingRulesEngine, GameState]:
    engine = UprisingRulesEngine(leader_ids=("ilesa_ecaz", *OTHERS))
    state = engine.reset(IX, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return engine, state


def _set_aside(
    engine: UprisingRulesEngine, state: GameState, index: int = 0
) -> tuple[GameState, list[LoggedStep], str]:
    rows = [
        row
        for row in engine.whole_actions(state, 0)
        if row.action_id == "set_aside_leader_card"
    ]
    card = str(dict(rows[index].arguments)["card_id"])
    after, entries = _logged_whole(engine, state, rows[index])
    return after, entries, card


def test_another_seat_s_log_hides_ilesa_s_set_aside_card() -> None:
    """Every seat sees that she set a card aside, never which, in the live
    log, an undone entry and its own view; she sees her card."""

    assert "set_aside_leader_card" in SEALED_ACTION_IDS
    engine, state = _ilesa()
    after, entries, card = _set_aside(engine, state)
    (entry,) = entries
    assert entry.sealed
    own: Any = _log_entry_json(0, entry, 0, finished=False)
    assert own["arguments"] == {"card_id": card}
    assert any(event["payload"].get("card_id") == card for event in own["events"])
    for seat in (1, 2, 3):
        for logged in (entry, LoggedStep(**{**_fields(entry), "undone": True})):
            other: Any = _log_entry_json(0, logged, seat, finished=False)
            assert other["action_id"] == "set_aside_leader_card"
            assert other["arguments"] == {"card_id": "(비공개)"}
            assert card not in str(other)
            assert {
                "kind": "leader_ability_resolved",
                "payload": {"leader_id": "ilesa_ecaz", "player": 0},
            } in other["events"]
        view = engine.observe(after, seat)
        assert view.private is not None and not view.private.set_aside_card_id
        assert card not in str(view.players)
    review: Any = _log_entry_json(0, entry, 1, finished=True)
    assert review["arguments"] == {"card_id": card}


def _fields(entry: LoggedStep) -> dict[str, Any]:
    return {name: getattr(entry, name) for name in LoggedStep.__slots__}


def test_a_known_hand_card_set_aside_stays_sealed() -> None:
    """A hand card the table knew (OQ-010) may be the one she sets aside:
    the pick is sealed as a whole, so the log never says which."""

    engine, state = _ilesa()
    hand = state.players[0].hand
    owner = state.players[0]
    known = replace(
        state,
        players=(replace(owner, hand_public=(hand[0],)), *state.players[1:]),
    )
    _, entries, card = _set_aside(engine, known, 0)
    assert card == hand[0]
    other: Any = _log_entry_json(0, entries[0], 1, finished=False)
    assert other["arguments"] == {"card_id": "(비공개)"}
    assert card not in str(other)


def test_the_set_aside_can_be_taken_back_but_its_return_cannot() -> None:
    """The pick is hers to undo (it reveals nothing); the step whose rules
    return the card at her second turn's start is a reveal, whoever took it,
    so no undo reaches past it. The Round Start line that set it aside stays
    "(비공개)" for the other seats after the card returns (OQ-154, user
    decision 2026-10-30 "계속 (비공개)": the return's own line and her public
    hand already show it; an old line is not rewritten)."""

    engine, state = _ilesa()
    after, entries, card = _set_aside(engine, state)
    assert not entries[0].reveals
    assert known_card_seats(after)[set_aside_id(0)] == frozenset({0})
    assert undo_window(list(entries), 0) == 1

    agents = {seat: HeuristicAgent(seed=seat + 1) for seat in range(4)}
    chance = ChanceResolver(seed=7)
    state = after
    for _ in range(600):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            step: Any = chance.resolve(decision)
            actor = None
        else:
            assert isinstance(decision, PlayerDecision)
            actor = decision.owner
            rows = engine.legal_actions(state, actor)
            step = agents[actor].choose_action_with_state(
                state, engine.observe(state, actor), rows
            )
        result = engine.apply(state, step)
        if state.players[0].set_aside_card_id and not (
            result.state.players[0].set_aside_card_id
        ):
            assert card in result.state.players[0].hand_public
            assert set_aside_id(0) not in known_card_seats(result.state)
            assert reveals_hidden_information(state, result.state, actor)
            assert reveals_hidden_information(state, result.state, 0)
            for seat in (1, 2, 3):
                other: Any = _log_entry_json(0, entries[0], seat, finished=False)
                assert other["arguments"] == {"card_id": "(비공개)"}
                assert card not in str(other)
            return
        state = result.state
    raise AssertionError("the set-aside card never returned")


def test_hundro_s_intelligence_shows_no_other_seat_a_card() -> None:
    """The kept card is his hidden Intrigue card and the one put back is his
    alone to know (OQ-149): the log redacts the kept card's id for every
    other seat, as Imperium Ceremony's, and names neither card to them."""

    engine = UprisingRulesEngine(leader_ids=("viscount_hundro_moritani", *OTHERS))
    state = engine.reset(IX, 3)
    assert state.phase is GamePhase.SETUP
    top = state.intrigue_deck[:2]
    keep = next(
        row
        for row in engine.whole_actions(state, 0)
        if row.action_id == "keep_peeked_intrigue"
    )
    kept = str(dict(keep.arguments)["instance_id"])
    after, entries = _logged_whole(engine, state, keep)
    assert kept in after.players[0].intrigue_cards
    # Keeping one opens the first round (its Conflict and hands are public
    # reveals of that step); his two cards stay his alone.
    (returned,) = (card for card in top if card != kept)
    known = known_card_seats(after)
    assert known[kept] == frozenset({0})
    assert known[returned] == frozenset({0})
    for entry in entries:
        own: Any = _log_entry_json(0, entry, 0, finished=False)
        assert kept in str(own)
        for seat in (1, 2, 3):
            other: Any = _log_entry_json(0, entry, seat, finished=False)
            for card in top:
                assert card not in str(other)
    for seat in (1, 2, 3):
        view = engine.observe(after, seat)
        for card in top:
            assert card not in str(view)


def test_a_first_turn_reveal_that_shows_the_set_aside_card_is_a_reveal() -> None:
    """ "라운드 첫 turn에 Reveal을 하면 따로 둔 카드를 공개 카드에 더한다" [Rise of Ix
    p. 10]: the rules put the card among the revealed ones, so her Reveal
    closes the undo window, unlike revealing a hand alone."""

    engine, state = _ilesa()
    after, _, card = _set_aside(engine, state)
    reveal = next(
        row for row in engine.whole_actions(after, 0) if row.action_id == "reveal_turn"
    )
    revealed, entries = _logged_whole(engine, after, reveal)
    assert card in revealed.players[0].in_play
    assert any(entry.reveals for entry in entries)
