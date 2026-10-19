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

A pending box alone does not say a trash loses it: a card trashing itself
by its own effect still pays its printed rewards (OQ-022: "카드가 자기
효과로 자신을 trash하는 경우 인쇄된 이득은 정상 지급"), as Feyd's Signet Ring
does when its own box trashes it. ``box_losing_trash`` dry-runs the decision
owner's trash rows naming a pending card and lists the ones that lose the
box; only that seat's view carries it, beside the rows it describes.
"""

from __future__ import annotations

import random
from dataclasses import fields, replace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.agents.agent_turn_steps import apply_placement
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
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import legal_graft_partner_actions
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.server.sessions import (
    GameSessionManager,
    _serialize_view,
    _state_after,
)
from dune_imperium.server.turn_cards import box_losing_trash, turn_cards

ENGINE = UprisingRulesEngine()
IMMORTALITY = RulesetConfig(immortality=True, promo_cards=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
EARLIER = next(card for card in STARTERS if card.endswith(":experimentation:0"))
THIS_TURN = next(card for card in STARTERS if card.endswith(":experimentation:1"))
FACE_DANCER = "tleilaxu:face_dancer:0"
PHEROMONES = "tleilaxu:beguiling_pheromones:0"
FOUR_HUMANS = ("human", "human", "human", "human")
ALL_AI = ("heuristic", "heuristic", "heuristic", "heuristic")
ONE_HUMAN = ("human", "heuristic", "heuristic", "heuristic")
DISSECTING_KIT = "imperium:dissecting_kit:0"


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
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and (dict(action.arguments).get("graft") is True) == graft
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    return apply_placement(ENGINE, state, action).state


def _graft(state: GameState, card_id: str, space_id: str, partner_id: str) -> GameState:
    placed = _place(state, card_id, space_id, graft=True)
    partner = next(
        action
        for action in legal_graft_partner_actions(placed, 0)
        if dict(action.arguments)["card_id"] == partner_id
    )
    return ENGINE.apply(placed, partner).state


def _apply(state: GameState, action_id: str, **arguments: str | int) -> GameState:
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
    two the frame holds in ``card_id`` (box 1's row makes it that one)."""

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

    partner_done = _apply(face_dancer_done, "resolve_agent_card_effect", box=1)
    _, context = next(
        (frame, dict(frame.context))
        for frame in partner_done.decision_stack
        if frame.kind == FrameKind.AGENT_EFFECTS
    )
    assert context["card_id"] == THIS_TURN
    assert _lists(partner_done) == {(both, ())}

    # Box 1 first: its card leaves the pending list, box 0's stays.
    partner_first = _apply(grafted, "resolve_agent_card_effect", box=1)
    assert _lists(partner_first) == {(both, (FACE_DANCER,))}


def test_a_card_trashed_out_of_play_leaves_both_lists() -> None:
    """Beguiling Pheromones trashes its grafted partner, whose box expires
    (OQ-022, FAQ p. 1): the partner is no longer in play, so neither list
    names it."""

    grafted = _graft(
        _state((FACE_DANCER, PHEROMONES)), FACE_DANCER, "dutiful_service", PHEROMONES
    )
    both = (FACE_DANCER, PHEROMONES)
    assert _lists(grafted) == {(both, both)}

    # Pheromones is box 1: its trash row carries ``box=1``.
    trashed = _apply(
        grafted, "trash_grafted_card_for_influence", box=1, card_id=FACE_DANCER
    )
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
        # A review serves no legal rows, so nothing to mark.
        assert view["box_losing_trash"] == []
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


# --- which trash rows lose a box (``box_losing_trash``) ---------------------


def _rows(view: dict[str, Any]) -> list[tuple[str, str]]:
    rows = view["box_losing_trash"]
    assert isinstance(rows, list)
    return [(str(row["action_id"]), str(row["card_id"])) for row in rows]


def _walk(
    seats: tuple[str, ...],
    seed: int,
    found: Any,
    *,
    random_play: bool,
    immortality: bool = False,
) -> tuple[GameSessionManager, str, int, Any]:
    """Walk a session until ``found(state, owner, actions)`` is truthy: every
    hold confirmed at once, the owner playing ``random.Random(seed)`` over
    its legal actions (or its first one); Leader draft off."""

    manager = GameSessionManager()
    summary = manager.create_game(
        seats, game_seed=seed, immortality=immortality, leader_draft=False
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(seed)
    for _ in range(6000):
        assert not summary["finished"]
        revision = summary["revision"]
        assert isinstance(revision, int)
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, revision)
            continue
        owner = _obj(summary["decision"])["owner"]
        assert isinstance(owner, int)
        actions = ENGINE.legal_actions(session.state, owner)
        hit = found(session.state, owner, actions)
        if hit:
            return manager, game_id, owner, hit
        index = rng.randrange(len(actions)) if random_play else 0
        summary = manager.apply_action(game_id, owner, revision, index)
    raise AssertionError("the walk never reached the position")


def _twin_trash(state: GameState, owner: int, actions: Any) -> Any:
    """This turn's pending card offered by an optional trash beside an
    earlier copy in play (the user's position)."""

    played, pending = turn_cards(state)
    offered = [
        str(dict(action.arguments)["card_id"])
        for action in actions
        if action.action_id == "trash_optional_card"
    ]
    for card in offered:
        if card not in pending:
            continue
        base = card.rsplit(":", 1)[0]
        for other in offered:
            if (
                other != card
                and other.rsplit(":", 1)[0] == base
                and other in state.players[owner].in_play
                and other not in played
            ):
                return card, other
    return None


def test_a_research_trash_of_this_turns_pending_card_loses_its_box() -> None:
    """Seed 185 (four human seats, Immortality, Leader draft off, seeded
    random play): the Research Station's Research offers its trash bonus
    while this turn's Prepare the Way still has its box, beside an earlier
    Prepare the Way in play. Trashing this turn's copy expires its box; only
    the owner's view says so, and working that out leaves the session as it
    was. (v146: optional Agent-turn effects offer no refusal (OQ-095 (2),
    2026-10-14), which moved seed 23's random walk off this position, and
    Other Memories without a refusal (same day) moved its replacement seed
    43 off it again; re-searched, seeds 111 and 223 were the only ones of
    0-299. v147: personal-card Reveal choices are rows on the Reveal frame
    beside the purchases, with no defer/resume and no refusal, so a random
    walk picks from a different list at such a Reveal; neither 111 nor 223
    reached the position any more, and searched on from 112, seed 243 was
    the first that did. Cleanup-2b (user decision 2026-10-17, OQ-095 (2)):
    the Research bonus's trash no longer opens a window; it waits on the
    Agent turn as a row among the turn's others, with no refusal, so the
    random walk moved off seed 243 once more. Searched from 0 for the
    position, seeds 0-758 missed; 759 reached it through an Intrigue card's
    Research (Breakthrough, c7r5) and 763 was the first through the Research
    Station. A research space's two icons are steps of their own too (user
    decision 2026-10-17, composed-effects plan 5, rule decision 5; OQ-027
    [Main p. 9]): the specimen waits as a row beside the trash and the Agent
    turn goes on, which moved the walk off seed 763. Searched from 0 under
    this whole test, seed 538 is the first, through an Agent card's Research
    (Bene Tleilax Researcher, c3r3), and 603 the first through the Research
    Station: seat 2, round 8, Research c3r3, "trash and specimen". Codec v150
    (stage B1, OQ-111): the Agent turn is a card pick and a space pick, so
    every random walk is a different one; searched from 0 for the position
    (walk only), seed 185 is the first, and 227 and 682 of 0-899 reach it
    too.)"""

    manager, game_id, owner, (card, earlier) = _walk(
        FOUR_HUMANS, 185, _twin_trash, random_play=True, immortality=True
    )
    assert (card, earlier) == ("reserve:prepare_the_way:4", "reserve:prepare_the_way:7")
    session = manager._get(game_id)
    before = (
        session.state,
        tuple(session.log),
        tuple(session.steps),
        session.undo_count,
        dict(session.open_units),
    )

    snapshot = _obj(manager.snapshot(game_id, owner)["view"])
    assert snapshot["pending_box_card_ids"] == [card]
    assert _rows(snapshot) == [("trash_optional_card", card)]
    assert _rows(manager.view(game_id, owner)) == [("trash_optional_card", card)]
    for seat in set(range(4)) - {owner}:
        other = _obj(manager.snapshot(game_id, seat)["view"])
        assert other["pending_box_card_ids"] == [card]
        assert _rows(other) == []

    after = (
        session.state,
        tuple(session.log),
        tuple(session.steps),
        session.undo_count,
        dict(session.open_units),
    )
    assert after[0] is before[0]
    assert after == before

    # The flag says what the engine does with the row.
    trash = next(
        action
        for action in ENGINE.legal_actions(session.state, owner)
        if action.action_id == "trash_optional_card"
        and dict(action.arguments)["card_id"] == card
    )
    events = ENGINE.apply(session.state, trash).events
    assert ("agent_card_effect_expired", card) in {
        (event.kind, dict(event.payload).get("card_id")) for event in events
    }


def test_planetologists_trash_loses_the_box_before_its_intrigue_card() -> None:
    """Arrakis Planetologist's frame also holds its Intrigue card as a step
    of its own (OQ-106): trashing this turn's card first leaves that frame
    on top, and the engine expires the box only once the frame closes.
    The row is flagged all the same, and so is the plain optional trash."""

    start = _state((THIS_TURN,), in_play=(EARLIER,))
    placed = _place(start, THIS_TURN, "accept_contract")
    for intrigue in (True, False):
        state = replace(
            placed,
            decision_stack=(
                *placed.decision_stack,
                optional_trash_frame(
                    0, "round:1:player:0:planetologist", intrigue=intrigue
                ),
            ),
        )
        assert box_losing_trash(ENGINE, state, 0) == (
            ("trash_optional_card", THIS_TURN),
        )
        assert box_losing_trash(ENGINE, state, 1) == ()
        trash = DomainAction(
            action_id="trash_optional_card",
            actor=0,
            arguments=(("card_id", THIS_TURN),),
        )
        first = ENGINE.apply(state, trash)
        expired_now = any(
            event.kind == "agent_card_effect_expired" for event in first.events
        )
        assert expired_now is not intrigue
        if intrigue:
            draw = DomainAction(action_id="draw_planetologist_intrigue", actor=0)
            assert "agent_card_effect_expired" in {
                event.kind for event in ENGINE.apply(first.state, draw).events
            }


def _signet_trash(state: GameState, owner: int, actions: Any) -> Any:
    played, _ = turn_cards(state)
    return next(
        (
            str(dict(action.arguments)["card_id"])
            for action in actions
            if action.action_id == "trash_leader_card"
            and dict(action.arguments).get("card_id") in played
        ),
        None,
    )


def test_feyds_signet_ring_trashed_by_its_own_box_keeps_its_rewards() -> None:
    """Seed 1, base game, Leader draft off, seat 0 Feyd-Rautha playing its
    first legal action (the walk of scripts/e2e/trash_zone.py): the Signet
    Ring's box offers Personal Training's paid trash with the Signet Ring
    itself among the cards. Its box is pending, but trashing the Signet Ring
    there is the box's own step and completes it (OQ-022, own effect): the
    row is not flagged."""

    manager, game_id, owner, signet = _walk(
        ONE_HUMAN, 1, _signet_trash, random_play=False
    )
    assert owner == 0 and signet == "player:0:starter:signet_ring:0"
    view = _obj(manager.snapshot(game_id, 0)["view"])
    assert view["turn_card_ids"] == [signet]
    assert view["pending_box_card_ids"] == [signet]
    assert _rows(view) == []

    session = manager._get(game_id)
    trash = next(
        action
        for action in ENGINE.legal_actions(session.state, 0)
        if action.action_id == "trash_leader_card"
        and dict(action.arguments)["card_id"] == signet
    )
    result = ENGINE.apply(session.state, trash)
    kinds = {event.kind for event in result.events}
    assert not kinds & {"agent_card_effect_expired", "leader_signet_expired"}
    _, pending = turn_cards(result.state)
    assert pending == ()


def test_a_research_trash_of_a_pending_signet_ring_is_flagged() -> None:
    """Feyd-Rautha plays the Signet Ring at Research Station with its box
    still pending; the Research to c3r3 offers an optional trash with the
    Signet Ring among the cards. That trash is not the box's own step, so it
    loses the box, which logs ``leader_signet_expired`` (cleanup-2c-4), and
    the row is flagged (2026-10-18 review: only the Agent box's kind was
    read)."""

    signet = next(card for card in STARTERS if ":signet_ring:" in card)
    state = _state((signet,))
    owner = replace(
        state.players[0],
        leader_id="feyd_rautha_harkonnen",
        research_space="c2r2",
        family_atomics=False,
        resources=Resources(solari=6, spice=6, water=3),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = _place(state, signet, "research_station")
    for action in (
        DomainAction("resolve_board_effect", 0, (("effect", "research"),)),
        DomainAction("choose_research_space", 0, (("space_id", "c3r3"),)),
    ):
        assert action in ENGINE.legal_actions(state, 0)
        state = ENGINE.apply(state, action).state
    _, pending = turn_cards(state)
    assert pending == (signet,)
    trash = DomainAction("trash_optional_card", 0, (("card_id", signet),))
    assert box_losing_trash(ENGINE, state, 0) == (("trash_optional_card", signet),)
    result = ENGINE.apply(state, trash)
    assert [
        dict(event.payload)["card_id"]
        for event in result.events
        if event.kind == "leader_signet_expired"
    ] == [signet]


def test_graft_trashes_flag_the_partner_and_never_the_active_card() -> None:
    """Beguiling Pheromones and Dissecting Kit clear the other grafted
    card's box themselves (no expired event): trashing the partner loses
    its box, trashing the active card itself is that card's own cost."""

    grafted = _graft(
        _state((FACE_DANCER, PHEROMONES)), FACE_DANCER, "dutiful_service", PHEROMONES
    )
    _, pending = turn_cards(grafted)
    assert set(pending) == {FACE_DANCER, PHEROMONES}
    # Pheromones' box (box 1) may trash Face Dancer, the other grafted card
    # (its box is lost), or itself (its own cost).
    assert box_losing_trash(ENGINE, grafted, 0) == (
        ("trash_grafted_card_for_influence", FACE_DANCER),
    )
    assert box_losing_trash(ENGINE, grafted, 2) == ()

    kit = _graft(
        _state((DISSECTING_KIT, FACE_DANCER)), DISSECTING_KIT, "arrakeen", FACE_DANCER
    )
    assert "trash_grafted_card_for_specimen" in {
        action.action_id for action in ENGINE.legal_actions(kit, 0)
    }
    # The row names no card: it always trashes the partner.
    assert box_losing_trash(ENGINE, kit, 0) == (
        ("trash_grafted_card_for_specimen", FACE_DANCER),
    )


def test_a_usurped_row_card_is_this_turns_card_but_never_pending() -> None:
    """A Row card borrowed with Usurp is not "in play" for any trash choice
    (OQ-054) and is trashed when the turn ends, so its box is never shown as
    one another effect could lose (2026-10-11 review)."""

    from tests.unit.rules import test_usurp_not_in_play as usurp

    owner = usurp._owner((usurp.USURP, usurp.DAGGER))
    state = usurp._usurp(
        usurp._state(owner, usurp.REPLACEMENT_EYES), "arrakeen", usurp.REPLACEMENT_EYES
    )
    for position in (state, usurp._switch(state)):
        played, pending = turn_cards(position)
        assert usurp.REPLACEMENT_EYES in played
        assert usurp.REPLACEMENT_EYES not in pending
        assert box_losing_trash(UprisingRulesEngine(), position, 0) == ()


def test_a_failing_read_drops_the_marks_instead_of_the_snapshot(
    monkeypatch: Any,
) -> None:
    from dune_imperium.server import turn_cards as module

    def broken(*_args: object) -> Any:
        raise RuntimeError("unexpected engine state")

    monkeypatch.setattr(module, "_turn_cards", broken)
    monkeypatch.setattr(module, "_box_losing_trash", broken)
    state = _state(())
    assert module.turn_cards(state) == ((), ())
    assert module.box_losing_trash(UprisingRulesEngine(), state, 0) == ()
