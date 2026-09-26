"""Tests for the one-press turn-end convention (2026-09-23).

The server holds every turn end of a human seat until that seat presses
"턴 종료" exactly once (project convention, not a rule; see the module
docstring of ``dune_imperium.server.turn_end``). Which steps end a turn is a
reading of the engine's own decision stack, so these tests exercise the
session layer (``turn_end.py`` + ``sessions.py``), not any card or Main-rules
behaviour -- the cards used to reach a scenario (Covert Operation, Holy War)
are exercised for their card text elsewhere (``tests/unit/rules/
test_agent_effects.py``, ``tests/unit/rules/test_bloodlines_cards.py``); here
they are only a vehicle to reach a decision-stack shape.

Every seed below was found by a scratch search over seeds, not guessed.
"""

import random
from dataclasses import dataclass

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.persistence import SaveError
from dune_imperium.server.session_log import live_steps
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SessionError,
)
from dune_imperium.server.turn_end import (
    EXPLICIT_TURN_ENDS,
    TURN_TAKING_EVENTS,
    answers_another_unit,
    at_turn_start,
    turn_start_seat,
    unit_seat,
)

# The AI seats play the rubric-priced 2026-09-10 table pinned in the registry,
# not ``heuristic`` (see tests/server/test_undo.py): the scripted seeds below
# follow that table's moves, and ``heuristic`` is retuned as the baseline
# improves.
HUMAN_FIRST = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
TWO_HUMANS = ("human", "human", "heuristic_uprising_table", "heuristic_uprising_table")
HUMAN_VS_RANDOM_AI = ("human", "random", "random", "random")


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _play_until(
    manager: GameSessionManager,
    game_id: str,
    summary: JsonObject,
    predicate: object,
) -> JsonObject:
    """Advance by the decision owner's first legal action, confirming any
    hold at once, until ``predicate(summary)`` holds. Used to walk a game
    forward to a scripted point with a deterministic, index-0 policy."""

    while not predicate(summary):  # type: ignore[operator]
        if summary["finished"]:
            raise AssertionError("the game finished before the condition was met")
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)
    return summary


def _play_until_seat0_offers(
    manager: GameSessionManager, game_id: str, summary: JsonObject, action_id: str
) -> tuple[JsonObject, int]:
    """Advance like ``_play_until``, stopping right before seat 0 would take
    its default (index-0) action, whenever ``action_id`` is one of its
    options. Returns the summary and that option's index."""

    while True:
        if summary["finished"]:
            raise AssertionError(f"the game finished before {action_id} was offered")
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        if owner == 0:
            for entry in actions:
                if entry["action_id"] == action_id:
                    return summary, _int(entry["index"])
        summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)


# ------------------------------------------------------------- leader draft


def test_the_last_leader_pick_holds_for_its_own_next_turn() -> None:
    # Seed 0: seat 0 (human) is the First Player, so it picks last (OQ-007,
    # draft_pick_order). The pick crosses straight from Leader-draft setup
    # into seat 0's own round-1 turn -- a phase/round change, and per
    # ``_unit_ended_locked`` that alone ends the unit even though the next
    # decision is again seat 0's own.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    assert summary["first_player"] == 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    pick = actions[0]
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(pick["index"])
    )

    assert summary["confirmation"] == 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["kind"] == "turn"
    assert manager.legal_actions(game_id, 0)["actions"] == []
    assert manager.snapshot(game_id, 0)["actions"] is None
    with pytest.raises(SessionError, match="has not confirmed"):
        manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    confirmed = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert confirmed["confirmation"] is None
    assert _rows(manager.legal_actions(game_id, 0)["actions"])


def test_a_non_last_leader_pick_holds_before_the_next_picker() -> None:
    # Seed 1: seat 0 is not the First Player (first_player == 3), so at
    # least one seat still picks after it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = str(summary["game_id"])
    assert summary["first_player"] != 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    pick = actions[0]
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(pick["index"])
    )

    assert summary["confirmation"] == 0
    decision = _obj(summary["decision"])
    assert decision["kind"] == "leader_draft"
    assert decision["owner"] != 0
    assert manager.legal_actions(game_id, 0)["actions"] == []

    confirmed = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert confirmed["confirmation"] is None
    # Seat 0 is the only human seat, so every remaining pick belongs to an
    # AI seat: the confirmation's own auto-advance runs the whole rest of
    # the draft and opens straight onto seat 0's first round-1 turn.
    assert _obj(confirmed["decision"])["kind"] == "turn"
    assert _obj(confirmed["decision"])["owner"] == 0


# ------------------------------------------------------- explicit turn ends


def test_finish_agent_turn_is_the_press_itself() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "finish_agent_turn"
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "finish_agent_turn")
    assert entry["undoable"] is False

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert _int(summary["revision"]) > before_revision
    # No second step: this seed's finish_agent_turn hands over through the
    # other seats' turns and straight back to seat 0's own next turn,
    # already open -- never blocked behind a fresh hold.
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert manager.legal_actions(game_id, 0)["actions"] != []


def test_finish_reveal_is_the_press_itself() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "finish_reveal"
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "finish_reveal")
    assert entry["undoable"] is False
    # This scenario's seat 0 already holds an open (undoable) window from
    # earlier this turn: the seal below is a real one, not a no-op on an
    # already-empty window.
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] != []

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert _int(summary["revision"]) > before_revision


def test_pass_combat_intrigue_is_the_press_itself() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "pass_combat_intrigue"
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "pass_combat_intrigue")
    assert entry["undoable"] is False

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert _int(summary["revision"]) > before_revision


def test_an_explicit_end_handing_straight_to_a_human_still_seals_the_turn() -> None:
    # Seed 0, two human seats: seat 0's finish_agent_turn hands straight to
    # human seat 1 with nothing else logged in between (no chance outcome,
    # no other seat's step). The log alone only closes a seat's undo window
    # at the next chance outcome or other seat's step -- there is none here
    # before seat 1 must act -- so the explicit-end branch of
    # ``_settle_locked`` has to seal it itself
    # (``session.undo_floor = len(session.steps)``), same as ``confirm_turn``
    # does for a held turn (test_undo.py::
    # test_a_confirmed_turn_end_stays_handed_over_to_the_next_human).
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "finish_agent_turn"
    )
    steps_before = len(session.steps)

    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), index)

    # Exactly the one explicit-end step -- no chance outcome interposed.
    assert len(session.steps) == steps_before + 1
    decision = _obj(summary["decision"])
    assert decision["owner"] == 1
    assert decision["owner_is_human"] is True
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="at most 0 step"):
        manager.undo(game_id, 0, _int(summary["revision"]))


# ------------------------------------------------------------- interrupts


def test_a_human_answering_an_opponent_interrupt_is_not_held() -> None:
    # Seed 7 (bloodlines, three "random" AI opponents): a Holy War-like
    # effect from an AI seat forces seat 0 to lose one unit while that AI's
    # own turn is still open. Answering it is not a turn end of seat 0's.
    # (Re-searched 2026-09-26: the card-transcription audit's rules fixes
    # moved the old seed 12 off this shape; seeds 7 and 16 of 0-16 reach it.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_VS_RANDOM_AI, game_seed=7, bloodlines=True)
    game_id = str(summary["game_id"])
    summary = _play_until(
        manager,
        game_id,
        summary,
        lambda s: _obj(s["decision"])["kind"] == "opponent_unit_loss"
        and _obj(s["decision"])["owner"] == 0,
    )
    assert summary["confirmation"] is None
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert actions

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, 0)
    assert summary["confirmation"] is None


def _covert_operation_instance(card_id: str) -> str:
    return next(i for i in imperium_deck_instance_ids(False) if f":{card_id}:" in i)


def _starter_instance(card_id: str) -> str:
    return next(i for i in starting_deck_instance_ids(0) if f":{card_id}:" in i)


def test_a_humans_own_covert_operation_does_not_hold_it_mid_turn() -> None:
    # The Covert Operation mechanic (each opponent with cards in hand
    # discards one) is already exercised for its card text in
    # tests/unit/rules/test_agent_effects.py::
    # test_covert_operation_makes_opponents_with_cards_discard_clockwise,
    # whose fixture is reused here to reach the decision-stack shape
    # directly (an organic search across 250+ seeds never got the card
    # acquired, cycled back into hand, and played before the opponents'
    # hands emptied in the same game -- see the report).
    covert_operation = _covert_operation_instance("covert_operation")
    first_discard = _starter_instance("dagger").replace("player:0:", "player:1:")
    second_discard = _covert_operation_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(covert_operation,),
        resources=Resources(solari=10, spice=10, water=10),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            PlayerState(player_id=1, hand=(first_discard,)),
            PlayerState(player_id=2, hand=(second_discard,)),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    session.state = state

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    agent_turn = next(
        a
        for a in actions
        if a["action_id"] == "agent_turn"
        and _obj(a["arguments"])["space_id"] == "assembly_hall"
    )
    summary = manager.apply_action(game_id, 0, 0, _int(agent_turn["index"]))
    assert summary["confirmation"] is None

    # Assembly Hall's own Gather Intelligence choice comes first and must be
    # cleared before the personal-card effect is offered.
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    decline = next(
        a for a in actions if a["action_id"] == "decline_gather_intelligence"
    )
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(decline["index"])
    )
    assert summary["confirmation"] is None

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    resolve = next(a for a in actions if a["action_id"] == "resolve_agent_card_effect")
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(resolve["index"])
    )

    # The AI seats' discards happened inside this one call; the decision is
    # back with seat 0's own still-open turn, never held.
    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["kind"] == "agent_effects"
    session = manager._get(game_id)
    assert session.state.players[1].discard_pile == (first_discard,)
    assert session.state.players[2].discard_pile == (second_discard,)


def test_a_humans_own_effect_that_closes_its_turn_holds_for_that_human() -> None:
    # The other half of the same clause: when Covert Operation is the human
    # seat's LAST pending effect (nothing else of the turn still open), the
    # step that closes the human's unit is an AI seat's own discard, not a
    # step of the human's at all -- and the hold still falls on the human
    # (every implicit turn end holds for its owner, whoever's step ended
    # it), with the pending decision moving on to the next seat, never back
    # to the human. Built like
    # test_a_humans_own_covert_operation_does_not_hold_it_mid_turn, but the
    # board's own Intrigue-draw icon is resolved BEFORE the personal card
    # effect so nothing is left pending once the last opponent discards
    # (probe: scratchpad/probe2.py, 2026-09-24 session).
    covert_operation = _covert_operation_instance("covert_operation")
    first_discard = _starter_instance("dagger").replace("player:0:", "player:1:")
    second_discard = _covert_operation_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(covert_operation,),
        resources=Resources(solari=10, spice=10, water=10),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            PlayerState(player_id=1, hand=(first_discard,)),
            PlayerState(player_id=2, hand=(second_discard,)),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    session.state = state

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    agent_turn = next(
        a
        for a in actions
        if a["action_id"] == "agent_turn"
        and _obj(a["arguments"])["space_id"] == "assembly_hall"
    )
    summary = manager.apply_action(game_id, 0, 0, _int(agent_turn["index"]))
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    decline = next(
        a for a in actions if a["action_id"] == "decline_gather_intelligence"
    )
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(decline["index"])
    )

    # Resolve the space's own Intrigue-draw icon first: once this is done,
    # Covert Operation is the human's only still-pending effect.
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    board = next(a for a in actions if a["action_id"] == "resolve_board_effect")
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(board["index"])
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [a["action_id"] for a in actions] == ["resolve_agent_card_effect"]

    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(actions[0]["index"])
    )

    # Both AI opponents discarded inside this one call; the hold falls on
    # the human (the actor of neither closing step), and the decision has
    # already moved on to the next seat.
    assert summary["confirmation"] == 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 1
    assert manager.legal_actions(game_id, 0)["actions"] == []
    assert session.state.players[1].discard_pile == (first_discard,)
    assert session.state.players[2].discard_pile == (second_discard,)


# ------------------------------------------------------- hand-over listener


def test_an_explicit_end_into_the_same_seats_next_turn_still_hands_over() -> None:
    # ``apply_action``'s ``passed = ended or _turn_passed(...)`` only ever
    # disagrees with ``_turn_passed`` alone for an explicit end
    # (EXPLICIT_TURN_ENDS) whose very next decision, with nothing else
    # logged, is the SAME seat's own fresh turn again -- every other seat
    # already revealed this round. ``_turn_passed`` alone reads that as
    # "still my turn" and would never announce the hand-over a human
    # server's autosave relies on (``add_hand_over_listener``); ``ended``
    # is exactly what still fires it. Seed 18, three random AI opponents,
    # found by a scratch random walk (rng seed 18 * 9973 + 1); see
    # scratchpad/verify_item4.py (2026-09-24 session).
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_VS_RANDOM_AI, game_seed=18)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    calls: list[str] = []
    manager.add_hand_over_listener(calls.append)
    rng = random.Random(18 * 9973 + 1)

    found = False
    for _ in range(6000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        choice = rng.choice(actions)
        steps_before = len(session.steps)
        calls_before = len(calls)
        summary = manager.apply_action(
            game_id, owner, _int(summary["revision"]), _int(choice["index"])
        )
        if owner == 0 and choice["action_id"] in EXPLICIT_TURN_ENDS:
            decision = _obj(summary["decision"])
            if (
                decision["owner"] == 0
                and decision["kind"] == "turn"
                and len(session.steps) == steps_before + 1
            ):
                found = True
                assert len(calls) == calls_before + 1, (
                    "the explicit end into the same seat's fresh turn must "
                    "still announce a hand-over"
                )
                break
    assert found, "the same-seat, zero-step hand-over was not reached"


# ------------------------------------------------------------- own turns


def test_a_seat_taking_consecutive_turns_is_held_between_them() -> None:
    # Seed 11 (re-searched 2026-09-26: the s1-card-data icon fixes -- Maker
    # Keeper's single City icon, Calculus of Power's City icon, Chani's
    # Fremen icon, and Undercover Asset losing its Spy icon [card faces] --
    # shift this index-0 policy's path, so the old seed 4 no longer reaches
    # this shape before the game finishes): at some point seat 0 is the only
    # seat left unrevealed this round, so its next "turn" decision is its own
    # again with no other seat's turn in between -- the engine cannot tell
    # this from a Plot Intrigue return (test_i below) by the frame alone, so
    # the hold uses the session's own log-based ``_fresh_turn`` check.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=11)
    game_id = str(summary["game_id"])
    summary = _play_until(
        manager,
        game_id,
        summary,
        lambda s: s["confirmation"] == 0
        and _obj(s["decision"])["kind"] == "turn"
        and _obj(s["decision"])["owner"] == 0,
    )
    assert summary["confirmation"] == 0
    assert manager.legal_actions(game_id, 0)["actions"] == []

    confirmed = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert confirmed["confirmation"] is None
    assert _rows(manager.legal_actions(game_id, 0)["actions"])


def test_a_plot_intrigue_at_turn_start_returns_without_a_hold() -> None:
    # Seed 0: seat 0 draws Imperium Politics (a Plot-timed Intrigue card) and
    # can play it right from the "turn" frame, before choosing an Agent or
    # Reveal turn. Playing it, and resolving its own choice, returns to the
    # very same turn start -- not a fresh turn, so no hold.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "play_intrigue"
    )
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn"
    assert decision["owner"] == 0

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)
    assert summary["confirmation"] is None

    while _obj(summary["decision"])["kind"] != "turn":
        assert summary["confirmation"] is None
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert _int(summary["revision"]) > before_revision


def test_undoing_back_to_the_turn_start_closes_the_unit() -> None:
    # An open unit belongs to the steps that opened it: take every one of
    # them back and the seat is left with nothing pending, exactly as if
    # its turn had never started (``undo``'s own "a unit whose opening step
    # was taken back is not open any more"). A different Agent turn played
    # afterwards then holds exactly once, like any other fresh turn.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    turn_start_revision = _int(summary["revision"])

    summary = manager.apply_action(game_id, 0, turn_start_revision, 0)
    assert session.open_units.get(0) == 0
    window = next(row for row in _rows(summary["undo"]) if row["seat"] == 0)

    summary = manager.undo(
        game_id, 0, _int(summary["revision"]), _int(window["steps"])
    )

    assert 0 not in session.open_units
    assert _int(summary["revision"]) == turn_start_revision
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn" and decision["owner"] == 0

    # A different board space (index 1, not index 0) played to its natural
    # end holds exactly once.
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 1)
    holds = 0
    for _ in range(60):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            holds += 1
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            break
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    assert holds == 1


# ------------------------------------------------- turn_end.py decision stacks


def _frame(kind: FrameKind, owner: int, frame_id: str) -> DecisionFrame:
    return DecisionFrame(
        kind=kind, frame_id=frame_id, decision=PlayerDecision(owner=owner, prompt="x")
    )


def _stack_state(*frames: DecisionFrame) -> GameState:
    return GameState(config=RulesetConfig(), seed=1, decision_stack=frames)


def test_unit_seat_reads_a_holy_war_shaped_stack() -> None:
    # [turn(C), opponent_unit_loss(X), opponent_unit_loss(C)]: C's own turn
    # is still the running unit even though the top of the stack is C's own
    # answer to X's Holy War (module docstring: "Holy War can stack [an
    # interrupt] above the next seat's turn before that turn has started").
    state = _stack_state(
        _frame(FrameKind.TURN, 2, "turn:2"),
        _frame(FrameKind.OPPONENT_UNIT_LOSS, 1, "loss:1"),
        _frame(FrameKind.OPPONENT_UNIT_LOSS, 2, "loss:2"),
    )
    assert unit_seat(state) == 2
    assert answers_another_unit(state, 2) is True
    assert at_turn_start(state, 2) is True


def test_unit_seat_reads_an_agent_effects_stack_with_a_foreign_trigger() -> None:
    # [agent_effects(3), intrigue_trigger_spy(0)]: seat 0 answers a leftover
    # Intrigue trigger offered inside seat 3's still-running Agent turn.
    state = _stack_state(
        _frame(FrameKind.AGENT_EFFECTS, 3, "agent_effects:3"),
        _frame(FrameKind.INTRIGUE_TRIGGER_SPY, 0, "trigger:0"),
    )
    assert unit_seat(state) == 3
    assert answers_another_unit(state, 0) is True


def test_unit_seat_reads_a_trailing_leftover_above_a_fresh_turn_start() -> None:
    # [turn(1), contract_market(0)]: seat 1's turn has started but a
    # leftover Contract pick from seat 0's previous turn is offered first.
    state = _stack_state(
        _frame(FrameKind.TURN, 1, "turn:1"),
        _frame(FrameKind.CONTRACT_MARKET, 0, "market:0"),
    )
    assert unit_seat(state) == 0
    assert at_turn_start(state, 0) is False
    assert at_turn_start(state, 1) is True


def test_turn_start_seat_reads_a_plain_turn_frame() -> None:
    state = _stack_state(_frame(FrameKind.TURN, 2, "turn:2"))
    assert turn_start_seat(state) == 2


# ------------------------------------------------------------------- saves


def test_a_hold_with_an_empty_undo_window_survives_save_and_restore() -> None:
    # Same scenario as test_undo.py's
    # test_a_turn_ending_in_a_reveal_still_waits_for_its_press (seed 21):
    # the reveal closes the undo window to nothing, but the hold and its
    # empty window both round-trip through save/restore.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = str(summary["game_id"])
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    assert summary["confirmation"] == 0
    assert summary["undo"] == []

    document = manager.save_game(game_id)
    assert document["confirmation"] == 0
    assert document["sealed_steps"] == 0
    restored = manager.restore_game(document)
    assert restored["confirmation"] == 0
    assert restored["undo"] == []
    assert restored["revision"] == summary["revision"]


def test_a_confirmed_hand_over_to_a_human_stays_unheld_after_restore() -> None:
    # Seed 7, two human seats: confirming a hold that hands straight to the
    # other human (nothing else gets logged in between) used to re-hold on
    # restore, since the log alone could not tell the window was sealed. The
    # found hand-over must itself still carry an open undo window right
    # before the press, or this would not exercise the sealing at all: an
    # already-empty window (closed by the log alone) looks the same whether
    # or not ``sealed_steps`` is restored correctly (m3: restoring
    # ``session.undo_floor = 0`` instead of the saved value).
    manager = GameSessionManager()
    seats = ("human", "human", *HUMAN_FIRST[1:3])
    summary = manager.create_game(seats, game_seed=7)
    game_id = str(summary["game_id"])

    found = False
    held_seat = -1
    for _ in range(400):
        held = summary["confirmation"]
        if not isinstance(held, int):
            owner = _int(_obj(summary["decision"])["owner"])
            summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)
            continue
        revision = _int(summary["revision"])
        before = [row for row in _rows(summary["undo"]) if row["seat"] == held]
        summary = manager.confirm_turn(game_id, held, revision)
        if not before:
            # The log alone already closed the window; this confirmation
            # would pass even under a broken restore (m3), so it does not
            # count as the scenario this test needs.
            continue
        successor = _int(_obj(summary["decision"])["owner"])
        if seats[successor] == "human" and _int(summary["revision"]) == revision:
            found = True
            held_seat = held
            break
    assert found, (
        "no direct human-to-human hand-over with an open undo window was reached"
    )
    assert summary["confirmation"] is None

    document = manager.save_game(game_id)
    assert document["confirmation"] is None
    restored = manager.restore_game(document)
    assert restored["confirmation"] is None
    held_seat_undo = [
        row for row in _rows(restored["undo"]) if row["seat"] == held_seat
    ]
    assert held_seat_undo == []


def test_a_document_without_the_new_fields_restores_by_the_old_rule() -> None:
    # Reuses test_undo.py's own known hold: seed 14, revision 12, seat 0
    # ends its turn with an undoable window while the next decision belongs
    # to another seat -- a hold under both the old rule and the new one, so
    # stripping the new fields and restoring must still reproduce it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    while _int(summary["revision"]) < 12:
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    influence = next(
        _int(entry["index"])
        for entry in _rows(manager.legal_actions(game_id, 0)["actions"])
        if entry["action_id"] == "resolve_faction_influence"
    )
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), influence)
    assert summary["confirmation"] == 0
    assert summary["undo"] != []

    document = manager.save_game(game_id)
    legacy = {
        key: value
        for key, value in document.items()
        if key not in ("confirmation", "sealed_steps")
    }
    restored = manager.restore_game(legacy)
    assert restored["confirmation"] == 0
    assert restored["revision"] == summary["revision"]


def test_a_legacy_document_saved_mid_turn_restores_with_an_open_unit() -> None:
    # A save written before the turn-end state was recorded (no
    # "confirmation"/"sealed_steps"/"open_units" at all) taken well before
    # any hold, mid-turn: the old rule's own live-log scan
    # (``_restore_legacy_hand_over_locked``) has to reopen the seat's unit
    # itself, or the turn's eventual end would never hold at all. It must
    # hold exactly once, not zero times and not twice.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["kind"] == "agent_effects" and decision["owner"] == 0

    document = manager.save_game(game_id)
    legacy = {
        key: value
        for key, value in document.items()
        if key not in ("confirmation", "sealed_steps", "open_units")
    }
    restored = manager.restore_game(legacy)
    restored_id = str(restored["game_id"])
    rsession = manager._get(restored_id)
    assert restored["confirmation"] is None
    assert rsession.open_units.get(0) == 0

    holds = 0
    for _ in range(200):
        if restored["finished"]:
            break
        held: object = restored["confirmation"]
        if isinstance(held, int):
            holds += 1
            assert held == 0
            restored = manager.confirm_turn(restored_id, 0, _int(restored["revision"]))
            assert restored["confirmation"] is None
            break
        owner = _int(_obj(restored["decision"])["owner"])
        restored = manager.apply_action(
            restored_id, owner, _int(restored["revision"]), 0
        )
    assert holds == 1


def test_a_control_defense_restore_gives_the_same_confirmation_as_live() -> None:
    # Base game: seat 0 eventually faces its own Control-defense decision
    # (it controls a critical location with troops in supply). Save+restore
    # right there and take the same choice in both sessions: both must hold
    # for seat 0. Found the way scratchpad/restore_control_defense.py found
    # its own seed -- an rng.Random(seed).choice policy that reaches a
    # seat-0 control_defense decision -- but at seed 0, round 7: that
    # reviewer script used the bare "heuristic" agent, which is retuned as
    # the baseline improves (see HUMAN_FIRST's own comment above), so its
    # seed 10 does not reproduce against this suite's pinned
    # "heuristic_uprising_table" table. Re-searched 2026-09-26 with this same
    # rng.Random(seed).choice policy: the s1-card-data icon fixes (Maker
    # Keeper, Calculus of Power, Chani, Undercover Asset [card faces]) moved
    # this path enough that the old seed 0 no longer reaches a seat-0
    # control_defense decision; seed 13 does.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(13)

    found = False
    choice: dict[str, object] = {}
    for _ in range(40_000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        choice = rng.choice(actions)
        top = session.state.decision_stack[-1] if session.state.decision_stack else None
        if top is not None and str(top.kind) == "control_defense" and owner == 0:
            found = True
            break
        summary = manager.apply_action(
            game_id, owner, _int(summary["revision"]), _int(choice["index"])
        )
    assert found, "no seat-0 control_defense decision was reached"

    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["decision"] == summary["decision"]

    live = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(choice["index"])
    )
    twin = manager.apply_action(
        restored_id, 0, _int(restored["revision"]), _int(choice["index"])
    )
    assert live["confirmation"] == 0
    assert twin["confirmation"] == 0


def test_bad_hand_over_fields_are_rejected_on_restore() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    document = manager.save_game(game_id)

    with pytest.raises(SaveError, match="sealed_steps"):
        manager.restore_game({**document, "sealed_steps": -1})
    with pytest.raises(SaveError, match="sealed_steps"):
        manager.restore_game({**document, "sealed_steps": "3"})
    with pytest.raises(SaveError, match="confirmation"):
        manager.restore_game({**document, "confirmation": "x"})
    # "confirmation" present without "sealed_steps" at all (not merely a bad
    # value) must still be rejected, not read as a legacy document.
    without_sealed_steps = {
        key: value for key, value in document.items() if key != "sealed_steps"
    }
    assert "confirmation" in without_sealed_steps
    with pytest.raises(SaveError, match="sealed_steps"):
        manager.restore_game(without_sealed_steps)


def test_open_units_fields_are_rejected_on_restore() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    document = manager.save_game(game_id)
    step_count = len(_rows(document["steps"]))
    assert step_count > 0

    with pytest.raises(SaveError, match="open_units"):
        manager.restore_game({**document, "open_units": "not-a-list"})
    with pytest.raises(SaveError, match="open_units"):
        manager.restore_game({**document, "open_units": [[0]]})
    with pytest.raises(SaveError, match="open_units"):
        manager.restore_game({**document, "open_units": [[0, 1, 2]]})
    # Seat 1 is an AI seat in HUMAN_FIRST: it can never hold an open unit.
    with pytest.raises(SaveError, match="seat 1"):
        manager.restore_game({**document, "open_units": [[1, 0]]})
    # A step index past every recorded step cannot have opened anything.
    with pytest.raises(SaveError, match="seat 0"):
        manager.restore_game({**document, "open_units": [[0, step_count]]})


# -------------------------------------------------------------------- remote


def test_a_remote_hold_with_an_empty_window_still_blocks_the_next_seat() -> None:
    # Seed 6, two claimed human seats: the same empty-undo-window hold as
    # the save/restore test above, checked here for the REMOTE-only block
    # on the next seat's own client (open servers let it act regardless,
    # unchanged: test_access.py::
    # test_an_open_server_still_lets_the_next_seat_act_without_the_confirmation).
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="key")
    admin = Credentials(admin_key="key")
    summary = manager.create_game(TWO_HUMANS, game_seed=6, credentials=admin)
    game_id = str(summary["game_id"])
    creds = {
        seat: Credentials(
            seat_tokens=frozenset({manager.claim_seat(game_id, seat, f"P{seat}").token})
        )
        for seat in (0, 1)
    }

    held = None
    owner = None
    for _ in range(200):
        held = summary["confirmation"]
        decision = _obj(summary["decision"])
        owner = _int(decision["owner"])
        if isinstance(held, int) and owner != held and owner in creds:
            undo_rows = [row for row in _rows(summary["undo"]) if row["seat"] == held]
            if not undo_rows:
                break
        if isinstance(held, int):
            summary = manager.confirm_turn(
                game_id, held, _int(summary["revision"]), credentials=creds[held]
            )
        else:
            summary = manager.apply_action(
                game_id, owner, _int(summary["revision"]), 0, credentials=creds[owner]
            )
    else:
        raise AssertionError("no empty-window hold blocking a human seat was reached")

    assert held is not None and owner is not None
    blocked = manager.snapshot(game_id, owner, credentials=creds[owner])
    assert blocked["actions"] is None
    with pytest.raises(SessionError, match="has not confirmed"):
        manager.apply_action(
            game_id, owner, _int(summary["revision"]), 0, credentials=creds[owner]
        )

    confirmed = manager.confirm_turn(
        game_id, held, _int(summary["revision"]), credentials=creds[held]
    )
    assert confirmed["confirmation"] is None
    released = manager.snapshot(game_id, owner, credentials=creds[owner])
    assert released["actions"] is not None


# -------------------------------------------------------------- property sweep


@dataclass
class _SweepConfig:
    seats: tuple[str, ...]
    leader_draft: bool
    game_seeds: tuple[int, ...]


_SWEEP_CONFIGS = (
    _SweepConfig(HUMAN_FIRST, False, (0, 1)),
    _SweepConfig(HUMAN_FIRST, True, (0,)),
)


def _run_property_sweep_game(
    manager: GameSessionManager,
    seats: tuple[str, ...],
    leader_draft: bool,
    game_seed: int,
) -> None:
    summary = manager.create_game(
        seats, leader_draft=leader_draft, game_seed=game_seed
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(game_seed * 7 + 1)
    humans = [seat for seat, kind in enumerate(seats) if kind == "human"]
    since_press = dict.fromkeys(humans, 0)
    # A hold for seat S requires a non-answer step of S since S's last
    # press (a step whose pre-step state has
    # ``not answers_another_unit(state, S)``): that is exactly what opens
    # ``session.open_units[S]`` in the first place, so nothing else could
    # ever make S's unit "over" for ``_unit_ended_locked`` to hold on.
    has_unit_step = dict.fromkeys(humans, False)
    last_logged = len(live_steps(session.log))

    for _ in range(4000):
        if summary["finished"]:
            break
        live = live_steps(session.log)
        for entry in live[last_logged:]:
            actor = entry.actor
            step_id = getattr(entry.step, "action_id", None)
            if step_id in ("reveal_turn", "pick_leader") and actor in humans:
                since_press[actor] += 1
                assert since_press[actor] <= 1, (
                    f"seat {actor} took two turns without a press "
                    f"(step {step_id!r})"
                )
            for event in entry.events:
                if event.kind in TURN_TAKING_EVENTS:
                    player = dict(event.payload).get("player")
                    if player in humans:
                        since_press[player] += 1
                        assert since_press[player] <= 1, (
                            f"seat {player} took two turns without a press "
                            f"({event.kind})"
                        )
        last_logged = len(live)

        held = summary["confirmation"]
        if isinstance(held, int):
            assert manager.legal_actions(game_id, held)["actions"] == []
            assert has_unit_step[held], (
                f"seat {held} held without a non-answer step since its last press"
            )
            summary = manager.confirm_turn(
                game_id,
                held,
                _int(summary["revision"]),
                undo_count=_int(summary["undo_count"]),
            )
            since_press[held] = 0
            has_unit_step[held] = False
            continue
        decision = _obj(summary["decision"])
        owner = _int(decision["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        choice = rng.choice(actions)
        before = session.state
        summary = manager.apply_action(
            game_id,
            owner,
            _int(summary["revision"]),
            _int(choice["index"]),
            undo_count=_int(summary["undo_count"]),
        )
        if owner in has_unit_step and not answers_another_unit(before, owner):
            has_unit_step[owner] = True
        if choice["action_id"] in EXPLICIT_TURN_ENDS:
            since_press[owner] = 0
            has_unit_step[owner] = False
            assert summary["confirmation"] != owner, (
                "an explicit turn end must never leave its own seat held"
            )
    else:
        raise AssertionError(f"seed {game_seed} did not finish within the step budget")


def test_property_sweep_a_human_seat_is_always_pressed_between_turns() -> None:
    manager = GameSessionManager()
    for config in _SWEEP_CONFIGS:
        for seed in config.game_seeds:
            _run_property_sweep_game(
                manager, config.seats, config.leader_draft, seed
            )
