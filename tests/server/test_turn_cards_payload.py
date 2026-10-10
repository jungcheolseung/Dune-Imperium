"""The view's ``turn_card_ids`` and ``pending_box_card_ids``.

User feedback 2026-10-11: with two Experimentation cards in play, the page
could not tell the one played this Agent turn (grafted, its Agent box still
waiting) from the one played on an earlier turn, and an optional trash took
this turn's copy. The engine was right: "you can't receive or activate an
effect from a card that is already trashed" (OQ-022, designer ruling;
``expire_trashed_card_effects``), so that copy's box was lost. The view now
names the cards the open Agent turn played (the played card and its graft
partner) and those whose box still waits, for the page to mark.

Display only: both lists are read off the Agent turn's effect frame
(``server.turn_cards``), every seat sees the same public values, and
``PlayerView``, the AI observation, the codec and the engine stay as they
were.
"""

from __future__ import annotations

import random
from dataclasses import fields
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.observation import (
    PlayerView,
    PrivatePlayerView,
    PublicPlayerView,
)
from dune_imperium.rules.agent_turn import legal_agent_actions
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import legal_graft_partner_actions
from dune_imperium.server.sessions import (
    GameSessionManager,
    _serialize_view,
    _state_after,
)
from dune_imperium.server.turn_cards import turn_cards

ENGINE = UprisingRulesEngine()
IMMORTALITY = RulesetConfig(immortality=True, promo_cards=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
EARLIER = next(card for card in STARTERS if card.endswith(":experimentation:0"))
THIS_TURN = next(card for card in STARTERS if card.endswith(":experimentation:1"))
FACE_DANCER = "tleilaxu:face_dancer:0"
PHEROMONES = "tleilaxu:beguiling_pheromones:0"
FOUR_HUMANS = ("human", "human", "human", "human")
ALL_AI = ("heuristic", "heuristic", "heuristic", "heuristic")


def _obj(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


def _seat(seat: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": seat,
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(hand: tuple[str, ...], in_play: tuple[str, ...] = ()) -> GameState:
    """Seat 0 at the start of an Agent turn (Immortality), holding ``hand``
    with ``in_play`` already played on an earlier turn of the round."""

    owner = _seat(
        0,
        hand=hand,
        in_play=in_play,
        deck=tuple(card for card in STARTERS if card not in (*hand, *in_play)),
        resources=Resources(solari=4, spice=2, water=2),
    )
    imperium = imperium_deck_instance_ids(False)
    return GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        players=(owner, *(_seat(seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _place(
    state: GameState, card_id: str, space_id: str, *, graft: bool = False
) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and (dict(action.arguments).get("graft") is True) == graft
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    return ENGINE.apply(state, action).state


def _graft(state: GameState, card_id: str, space_id: str, partner_id: str) -> GameState:
    placed = _place(state, card_id, space_id, graft=True)
    partner = next(
        action
        for action in legal_graft_partner_actions(placed, 0)
        if dict(action.arguments)["card_id"] == partner_id
    )
    return ENGINE.apply(placed, partner).state


def _apply(state: GameState, action_id: str, **arguments: str) -> GameState:
    action = DomainAction(
        action_id=action_id, actor=0, arguments=tuple(sorted(arguments.items()))
    )
    assert action in ENGINE.legal_actions(state, 0), action
    return ENGINE.apply(state, action).state


def _lists(state: GameState) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Both lists as every seat's serialized view carries them."""

    seen = set()
    for seat in range(4):
        view = _serialize_view(ENGINE.observe(state, seat), state)
        turn, pending = view["turn_card_ids"], view["pending_box_card_ids"]
        assert isinstance(turn, list) and isinstance(pending, list)
        seen.add((tuple(map(str, turn)), tuple(map(str, pending))))
    return seen


def test_the_card_played_this_turn_is_named_beside_the_earlier_copy() -> None:
    """The user's case without the graft: two Experimentation in play, the
    one played this turn named until its turn ends, and pending until its
    Agent box (Research) resolves."""

    start = _state((THIS_TURN,), in_play=(EARLIER,))
    assert _lists(start) == {((), ())}

    placed = _place(start, THIS_TURN, "accept_contract")
    assert placed.players[0].in_play == (EARLIER, THIS_TURN)
    assert _lists(placed) == {((THIS_TURN,), (THIS_TURN,))}

    researched = _apply(placed, "resolve_agent_card_effect")
    assert _lists(researched) == {((THIS_TURN,), ())}

    # Everything resolved: the turn is still open until its end is pressed
    # (OQ-095), and the card is still this turn's.
    done = _apply(
        _apply(researched, "resolve_board_effect", effect="cards"),
        "resolve_board_effect",
        effect="resources",
    )
    assert any(
        action.action_id == "finish_agent_turn"
        for action in ENGINE.legal_actions(done, 0)
    )
    assert _lists(done) == {((THIS_TURN,), ())}

    ended = _apply(done, "finish_agent_turn")
    assert not any(
        frame.kind == FrameKind.AGENT_EFFECTS for frame in ended.decision_stack
    )
    assert _lists(ended) == {((), ())}


def test_a_graft_names_both_cards_each_with_its_own_box() -> None:
    """The user's case: the placed card and its graft partner are both this
    turn's; each stays pending until its own box resolves, whichever of the
    two is the active one (``switch_graft_card`` swaps them)."""

    grafted = _graft(
        _state((FACE_DANCER, THIS_TURN), in_play=(EARLIER,)),
        FACE_DANCER,
        "dutiful_service",
        THIS_TURN,
    )
    both = (FACE_DANCER, THIS_TURN)
    assert _lists(grafted) == {(both, both)}

    face_dancer_done = _apply(grafted, "resolve_agent_card_effect")
    assert _lists(face_dancer_done) == {(both, (THIS_TURN,))}

    switched = _apply(face_dancer_done, "switch_graft_card")
    _, context = next(
        (frame, dict(frame.context))
        for frame in switched.decision_stack
        if frame.kind == FrameKind.AGENT_EFFECTS
    )
    assert context["card_id"] == THIS_TURN
    assert _lists(switched) == {(both, (THIS_TURN,))}

    partner_done = _apply(switched, "resolve_agent_card_effect")
    assert _lists(partner_done) == {(both, ())}


def test_a_card_trashed_out_of_play_leaves_both_lists() -> None:
    """Beguiling Pheromones trashes its grafted partner, whose box expires
    (OQ-022, FAQ p. 1): the partner is no longer in play, so neither list
    names it."""

    grafted = _graft(
        _state((FACE_DANCER, PHEROMONES)), FACE_DANCER, "dutiful_service", PHEROMONES
    )
    switched = _apply(grafted, "switch_graft_card")
    both = (FACE_DANCER, PHEROMONES)
    assert _lists(switched) == {(both, both)}

    trashed = _apply(switched, "trash_grafted_card_for_influence", card_id=FACE_DANCER)
    assert FACE_DANCER not in trashed.players[0].in_play
    played, pending = turn_cards(trashed)
    assert played == (PHEROMONES,)
    assert FACE_DANCER not in pending


def test_another_seat_answering_inside_the_turn_still_sees_it() -> None:
    """A frame stacked above the open turn (here a Graft partner choice,
    and in the user's game an optional trash) leaves the turn's frame
    below it, and the lists read it there."""

    placed = _place(
        _state((FACE_DANCER, THIS_TURN), in_play=(EARLIER,)),
        FACE_DANCER,
        "dutiful_service",
        graft=True,
    )
    assert placed.decision_stack[-1].kind == FrameKind.GRAFT_PARTNER
    assert _lists(placed) == {((FACE_DANCER,), (FACE_DANCER,))}


def test_a_live_game_serves_the_same_lists_to_every_seat() -> None:
    """Through the session: the snapshot and the plain view of every seat
    carry the frame's lists, the same for all four."""

    manager = GameSessionManager()
    game_id = str(
        manager.create_game(FOUR_HUMANS, immortality=True, game_seed=4)["game_id"]
    )
    session = manager._get(game_id)
    rng = random.Random(4)
    checked = 0
    for _ in range(600):
        played, pending = turn_cards(session.state)
        expected = {"turn": list(played), "pending": list(pending)}
        for seat in range(4):
            for view in (
                _obj(manager.snapshot(game_id, seat)["view"]),
                manager.view(game_id, seat),
            ):
                got = {
                    "turn": view["turn_card_ids"],
                    "pending": view["pending_box_card_ids"],
                }
                assert got == expected
        if played:
            checked += 1
            if checked >= 12 and pending != played:
                break
        summary = manager.summary(game_id)
        revision = summary["revision"]
        assert isinstance(revision, int)
        held = summary["confirmation"]
        if isinstance(held, int):
            manager.confirm_turn(game_id, held, revision)
            continue
        owner = _obj(summary["decision"])["owner"]
        assert isinstance(owner, int)
        actions = manager.legal_actions(game_id, owner)["actions"]
        assert isinstance(actions, list) and actions
        index = _obj(rng.choice(actions))["index"]
        assert isinstance(index, int)
        manager.apply_action(game_id, owner, revision, index)
    assert checked >= 12


def test_a_review_step_carries_the_lists_of_that_step() -> None:
    manager = GameSessionManager()
    game_id = str(manager.create_game(ALL_AI, game_seed=13)["game_id"])
    session = manager._get(game_id)
    assert session.state.phase is GamePhase.FINISHED
    state = ENGINE.reset(session.config, session.game_seed)
    open_step = None
    for index, step in enumerate(session.steps):
        state = ENGINE.apply(state, step).state
        if turn_cards(state)[0]:
            open_step = index + 1
            break
    assert open_step is not None
    expected = turn_cards(_state_after(session, open_step))
    for seat in (0, 2):
        view = _obj(manager.review_state(game_id, seat, open_step)["view"])
        assert (
            tuple(view["turn_card_ids"]),
            tuple(view["pending_box_card_ids"]),
        ) == expected
    final = _obj(manager.review_state(game_id, 1, len(session.steps))["view"])
    assert final["turn_card_ids"] == [] and final["pending_box_card_ids"] == []


def test_the_ai_observation_never_sees_the_lists() -> None:
    """The lists live only in the server's serialization: no observation
    dataclass has such a field, and serializing the views of a state with
    an open Agent turn leaves the AI observation's encoding as it was."""

    for view_type in (PlayerView, PublicPlayerView, PrivatePlayerView):
        names = {field.name for field in fields(view_type)}
        assert not names & {"turn_card_ids", "pending_box_card_ids"}

    grafted = _graft(
        _state((FACE_DANCER, THIS_TURN), in_play=(EARLIER,)),
        FACE_DANCER,
        "dutiful_service",
        THIS_TURN,
    )
    before = [encode_player_view(ENGINE.observe(grafted, seat)) for seat in range(4)]
    both = (FACE_DANCER, THIS_TURN)
    assert _lists(grafted) == {(both, both)}
    after = [encode_player_view(ENGINE.observe(grafted, seat)) for seat in range(4)]
    assert before == after
