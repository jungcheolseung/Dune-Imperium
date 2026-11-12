"""A row's ``forfeit``: what the step would make its own seat lose.

User request 2026-10-31, after a real game: seat 2 grafted Show of Strength
to Dissecting Kit at Arrakeen and took Dissecting Kit's "trash the other
grafted card" first. "You can't receive or activate an effect from a card
that is already trashed" (OQ-022, designer ruling), so Show of Strength's
unused draw was lost; a small suffix on the row said so without naming the
card, and the player never read it. Each served row now carries, from its
own dry run (``server.forfeits``), the cards whose unused effects it loses
and what those effects are, and the page prints it as its own line.

A card that leaves play by its own printed effect keeps what is left
(OQ-022: "카드가 자기 효과로 자신을 trash하는 경우 인쇄된 이득은 정상
지급"), so no row that does that carries a forfeit. These cases were
``box_losing_trash``'s (``test_turn_cards_payload``) before the row-level
check replaced it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from tests.server.test_turn_cards_payload import (
    DISSECTING_KIT,
    EARLIER,
    ENGINE,
    FACE_DANCER,
    FOUR_HUMANS,
    ONE_HUMAN,
    PHEROMONES,
    STARTERS,
    THIS_TURN,
    _apply,
    _graft,
    _obj,
    _place,
    _signet_trash,
    _state,
    _twin_trash,
    _walk,
)

from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.core import DomainAction, GameState, PlayerState, Resources
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.agent_turn import legal_agent_actions
from dune_imperium.rules.optional_trash import optional_trash_frame, trash_printer
from dune_imperium.server.forfeits import forfeited_effects, lapsed_effects
from dune_imperium.server.sessions import GameSessionManager
from dune_imperium.server.turn_cards import turn_cards

SHOW_OF_STRENGTH = "imperium:show_of_strength:0"
GHOLA = "tleilaxu:ghola:0"

type Row = tuple[str, tuple[tuple[str, Any], ...]]


def _forfeits(state: GameState, seat: int = 0) -> dict[Row, list[Any]]:
    """Every whole action of ``seat`` that forfeits something, with what."""

    found: dict[Row, list[Any]] = {}
    for action in ENGINE.whole_actions(state, seat):
        result = apply_whole(ENGINE, state, action)
        lost = forfeited_effects(
            state, seat, RuleResult(state=result.state, events=result.events)
        )
        if lost:
            found[(action.action_id, action.arguments)] = lost
    return found


def _lost(state: GameState, seat: int = 0) -> dict[Row, list[str]]:
    """``_forfeits`` with each forfeit's cards only."""

    return {
        row: [entry["card_id"] for entry in lost]
        for row, lost in _forfeits(state, seat).items()
    }


def _served(manager: GameSessionManager, game_id: str, seat: int) -> list[Any]:
    listed = manager.legal_actions(game_id, seat)["actions"]
    assert isinstance(listed, list)
    return [_obj(row) for row in listed]


def test_the_users_graft_names_the_partners_lost_draw() -> None:
    """The user's position (round 8 of the 2026-10-31 game, rebuilt):
    Dissecting Kit placed at Arrakeen and grafted to Show of Strength. Its
    trash row, as the play server serves it, names Show of Strength and its
    unused "Draw 2 cards"; no other row forfeits anything. Taking Show of
    Strength's draw first leaves nothing to lose."""

    grafted = _graft(
        _state((DISSECTING_KIT, SHOW_OF_STRENGTH)),
        DISSECTING_KIT,
        "arrakeen",
        SHOW_OF_STRENGTH,
    )
    manager = GameSessionManager()
    game_id = str(
        manager.create_game(
            FOUR_HUMANS, immortality=True, promo_cards=True, game_seed=1
        )["game_id"]
    )
    manager._get(game_id).state = grafted
    rows = _served(manager, game_id, 0)
    forfeiting = [row for row in rows if "forfeit" in row]
    assert [row["action_id"] for row in forfeiting] == [
        "trash_grafted_card_for_specimen"
    ]
    assert forfeiting[0]["forfeit"] == [
        {
            "card_id": SHOW_OF_STRENGTH,
            "kind": "agent",
            "name": "Show of Strength",
            "name_ko": "세력 과시",
            "effects": ["Draw 2 cards"],
            "effects_ko": ["{draw:2}"],
        }
    ]
    # Only the deciding seat is served rows at all.
    for seat in (1, 2, 3):
        assert manager.legal_actions(game_id, seat)["actions"] == []

    drawn = _apply(grafted, "resolve_agent_card_effect", box=1)
    assert "trash_grafted_card_for_specimen" in {
        action.action_id for action in ENGINE.whole_actions(drawn, 0)
    }
    assert _forfeits(drawn) == {}


def test_graft_trashes_name_the_partner_and_never_the_active_card() -> None:
    """Beguiling Pheromones may trash Face Dancer, the other grafted card
    (its unused box is lost), or itself (its own cost, nothing lost)."""

    grafted = _graft(
        _state((FACE_DANCER, PHEROMONES)), FACE_DANCER, "dutiful_service", PHEROMONES
    )
    assert _lost(grafted) == {
        (
            "trash_grafted_card_for_influence",
            (("box", 1), ("card_id", FACE_DANCER)),
        ): [FACE_DANCER]
    }
    (lost,) = _forfeits(grafted).values()
    assert lost[0]["effects"] == ["Draw 1 card"]
    assert _forfeits(grafted, 2) == {}

    kit = _graft(
        _state((DISSECTING_KIT, FACE_DANCER)), DISSECTING_KIT, "arrakeen", FACE_DANCER
    )
    # The row names no card: it always trashes the partner.
    assert _lost(kit) == {("trash_grafted_card_for_specimen", ()): [FACE_DANCER]}


def test_a_ghola_names_the_box_it_copied() -> None:
    """Ghola grafted to Dissecting Kit copies its box [Immortality p. 14].
    Dissecting Kit's trash of the other grafted card loses Ghola's copy of
    that box, worded as the copied box; Ghola's copy trashing Dissecting
    Kit loses Dissecting Kit's own."""

    grafted = _graft(
        _state((DISSECTING_KIT, GHOLA)), DISSECTING_KIT, "arrakeen", GHOLA
    )
    found = _forfeits(grafted)
    assert len(found) == 2
    by_card = {lost[0]["card_id"]: lost[0] for lost in found.values()}
    assert set(by_card) == {DISSECTING_KIT, GHOLA}
    assert by_card[GHOLA]["name"] == "Ghola"
    assert by_card[GHOLA]["effects"] == by_card[DISSECTING_KIT]["effects"] == [
        "You may trash the other grafted card → Generate 1 specimen"
    ]


def test_trashing_this_turns_copy_is_named_and_the_earlier_one_is_not() -> None:
    """Seed 314 (four human seats, Immortality, Leader draft off, seeded
    random play; the walk of ``test_turn_cards_payload``): an optional trash
    offers this turn's Prepare the Way, its box still pending, beside an
    earlier copy in play. Only the row trashing this turn's copy forfeits
    its box, and the row says so without touching the session. (Seed 4,
    the Research Station's trash bonus, until the server passed Combat
    Intrigue for a seat with no Intrigue card, user request 2026-11-09,
    which moves the walk; of 0-399, seed 314 is the first to reach it.)"""

    manager, game_id, owner, (card, earlier) = _walk(
        FOUR_HUMANS, 314, _twin_trash, random_play=True, immortality=True
    )
    assert (card, earlier) == ("reserve:prepare_the_way:2", "reserve:prepare_the_way:3")
    session = manager._get(game_id)
    before = (session.state, tuple(session.log), tuple(session.steps))
    rows = _served(manager, game_id, owner)
    named = {
        row["arguments"]["card_id"]: row.get("forfeit")
        for row in rows
        if row["action_id"] == "trash_optional_card"
    }
    assert named[earlier] is None
    assert named[card] is not None
    assert [entry["card_id"] for entry in named[card]] == [card]
    assert named[card][0]["effects"] == [
        "If you have 2 or more Bene Gesserit Influence: Draw 1 card"
    ]
    assert (session.state, tuple(session.log), tuple(session.steps)) == before
    assert session.state is before[0]


def test_planetologists_trash_names_the_box_its_frame_will_expire() -> None:
    """Arrakis Planetologist's frame also holds its Intrigue card as a step
    of its own (OQ-106): trashing this turn's card first leaves that frame
    on top, and the engine expires the box only once the frame closes. The
    row names the box all the same."""

    start = _state((THIS_TURN,), in_play=(EARLIER,))
    placed = _place(start, THIS_TURN, "accept_contract")
    placed = replace(
        placed,
        players=(
            replace(placed.players[0], leader_id="liet_kynes"),
            *placed.players[1:],
        ),
    )
    for intrigue in (True, False):
        state = replace(
            placed,
            decision_stack=(
                *placed.decision_stack,
                optional_trash_frame(
                    0,
                    "round:1:player:0:planetologist",
                    printer=trash_printer(Source.LEADER, "liet_kynes"),
                    intrigue=intrigue,
                ),
            ),
        )
        assert _lost(state) == {
            ("trash_optional_card", (("card_id", THIS_TURN),)): [THIS_TURN]
        }
        assert _forfeits(state, 1) == {}


def test_feyds_signet_ring_trashed_by_its_own_box_forfeits_nothing() -> None:
    """Seed 1, base game, Leader draft off, seat 0 Feyd-Rautha playing its
    first legal action: the Signet Ring's box offers Personal Training's
    paid trash with the Signet Ring itself among the cards. Trashing it
    there is the box's own step and completes it (OQ-022, own effect)."""

    manager, game_id, owner, signet = _walk(
        ONE_HUMAN, 1, _signet_trash, random_play=False
    )
    assert owner == 0 and signet == "player:0:starter:signet_ring:0"
    rows = _served(manager, game_id, 0)
    assert any(
        row["action_id"] == "trash_leader_card"
        and row["arguments"]["card_id"] == signet
        for row in rows
    )
    assert [row for row in rows if "forfeit" in row] == []


def test_a_research_trash_of_a_pending_signet_ring_is_named() -> None:
    """Feyd-Rautha plays the Signet Ring at Research Station with its box
    still pending; the Research to c3r3 offers an optional trash with the
    Signet Ring among the cards. That trash is not the box's own step, so it
    loses the box (``leader_signet_expired``), and the row names it."""

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
        state = apply_whole(ENGINE, state, action).state
    icon = (("printed", "c3r3"), ("source", "research"))
    row = ("trash_optional_card", tuple(sorted((("card_id", signet), *icon))))
    found = _forfeits(state)
    assert list(found) == [row]
    assert found[row][0]["card_id"] == signet
    assert found[row][0]["effects"] == ["Your Leader's Signet Ring ability"]


def test_a_waiting_optional_trash_is_part_of_what_is_lost() -> None:
    """Control the Spice's paid arrow leaves its trash waiting on the turn
    (cleanup-2b), outside the box; Dissecting Kit's trash of its partner
    expires that trash too (OQ-022; engine audit 2026-10-22, P1), and the
    row names it. That waiting trash is Control the Spice's own: trashing
    Control the Spice with it forfeits nothing, trashing Dissecting Kit
    with it loses Dissecting Kit's still pending box."""

    from tests.unit.rules import test_control_the_spice as cts

    paid = cts._grafted_and_paid(cts.KIT)
    found = _forfeits(paid)
    lost = found[("trash_grafted_card_for_specimen", (("box", 1),))]
    assert [entry["card_id"] for entry in lost] == [cts.CONTROL]
    assert lost[0]["effects"] == ["Trash"]
    assert lost[0]["effects_ko"] == ["{trash}"]
    icon = (("printed", "control_the_spice"), ("source", "agent_card"))
    assert {
        dict(arguments)["card_id"]: [entry["card_id"] for entry in lost]
        for (action_id, arguments), lost in found.items()
        if action_id == "trash_optional_card"
        and set(icon) <= set(arguments)
    } == {cts.KIT: [cts.KIT]}


def test_a_usurped_row_card_is_never_named() -> None:
    """A Row card borrowed with Usurp is not "in play" for any trash choice
    (OQ-054) and is trashed when the turn ends, so no row forfeits it."""

    from tests.unit.rules import test_usurp_not_in_play as usurp

    owner = usurp._owner((usurp.USURP, usurp.DAGGER))
    state = usurp._usurp(
        usurp._state(owner, usurp.REPLACEMENT_EYES), "arrakeen", usurp.REPLACEMENT_EYES
    )
    for position in (state, usurp._switch(state)):
        played, _ = turn_cards(position)
        assert usurp.REPLACEMENT_EYES in played
        assert all(
            usurp.REPLACEMENT_EYES not in cards
            for cards in _lost(position).values()
        )


def test_a_reveal_trash_names_the_choice_it_leaves_unusable() -> None:
    """Calculus of Power trashes Corrinth City while Corrinth City's choice
    still waits: the choice then offers nothing and lapses at the Reveal's
    end (OQ-022, its 2026-09-07 addition). The row names it; Calculus of
    Power trashing its own twin names the twin's choice, never its own."""

    from tests.unit.rules import test_reveal_choices as rc

    calculus = rc._card("calculus_of_power")
    corrinth = rc._card("corrinth_city")
    owner = PlayerState(
        player_id=0,
        hand=(calculus, corrinth),
        resources=Resources(solari=9),
        troops_supply=8,
        troops_conflict=1,
    )
    revealed = rc._reveal(rc._state(owner))
    found = _forfeits(revealed)
    trash = rc._first(
        revealed, "trash_reveal_card", card_id=corrinth, source="calculus_of_power"
    )
    (lost,) = found[(trash.action_id, trash.arguments)]
    assert lost["card_id"] == corrinth
    assert lost["kind"] == "reveal"
    assert lost["name"] == "Corrinth City"
    assert lost["effects"] and lost["effects_ko"]
    assert all(
        entry["card_id"] != calculus for lost in found.values() for entry in lost
    )


def test_a_box_with_no_icon_is_worded_as_its_own_button() -> None:
    """Seek Allies at Desert Tactics: the space's trash of Seek Allies
    expires its box ("Trash this card", one action with no icon). The note
    words that box exactly as the box's own button does, in both languages:
    English "Trash this card" (the page draws its Trash), Korean the words
    "이 카드 폐기". The {trash} icon means "Trash one card" [Main p. 20], so
    beside "이 카드" it would read as a second effect; one rulebook icon per
    effect (user, 2026-10-11; tests/server/test_label_icons.py) writes the
    trash of this card as a word."""

    seek = next(card for card in STARTERS if ":seek_allies:" in card)
    manager = GameSessionManager()
    game_id = str(
        manager.create_game(
            FOUR_HUMANS, immortality=True, promo_cards=True, game_seed=1
        )["game_id"]
    )
    manager._get(game_id).state = _place(_state((seek,)), seek, "desert_tactics")
    rows = _served(manager, game_id, 0)
    (box,) = [row for row in rows if row["action_id"] == "resolve_agent_card_effect"]
    forfeiting = [row for row in rows if "forfeit" in row]
    assert [row["action_id"] for row in forfeiting] == [
        "trash_card_for_desert_tactics"
    ]
    assert forfeiting[0]["forfeit"] == [
        {
            "card_id": seek,
            "kind": "agent",
            "name": "Seek Allies",
            "name_ko": "동맹 물색",
            "effects": [box["detail"]],
            "effects_ko": [box["detail_ko"]],
        }
    ]
    assert (box["detail"], box["detail_ko"]) == ("Trash this card", "이 카드 폐기")


def test_a_failing_read_drops_the_warning_instead_of_the_listing(
    monkeypatch: Any,
) -> None:
    from dune_imperium.server import forfeits as module

    def broken(*_args: object) -> Any:
        raise RuntimeError("unexpected engine state")

    monkeypatch.setattr(module, "_forfeited_effects", broken)
    state = _state(())
    assert module.forfeited_effects(state, 0, RuleResult(state=state)) is None


# --- what a turn end lapses (``lapses``) --------------------------------------


def test_a_turn_end_row_lists_the_optional_effects_it_lapses() -> None:
    """The user's turn played the other way round: Show of Strength's draw
    and Arrakeen's icons taken, Dissecting Kit's optional trash left. Every
    optional effect still waiting "does not block the turn's end, has no
    refusal, and the press lapses it" (OQ-095 (2)); the turn-end row lists
    it, as the log will, and no other row carries a list."""

    state = _graft(
        _state((DISSECTING_KIT, SHOW_OF_STRENGTH)),
        DISSECTING_KIT,
        "arrakeen",
        SHOW_OF_STRENGTH,
    )
    state = _apply(state, "resolve_agent_card_effect", box=1)
    state = _apply(state, "resolve_board_effect", effect="troops")
    state = _apply(state, "resolve_board_effect", effect="cards")
    manager = GameSessionManager()
    game_id = str(
        manager.create_game(
            FOUR_HUMANS, immortality=True, promo_cards=True, game_seed=1
        )["game_id"]
    )
    manager._get(game_id).state = state
    rows = _served(manager, game_id, 0)
    listing = {row["action_id"]: row.get("lapses") for row in rows}
    assert listing["finish_agent_turn"] == [
        {
            "kind": "agent_card_effect_lapsed",
            "payload": {"card_id": DISSECTING_KIT, "player": 0},
        }
    ]
    assert [
        row
        for row in rows
        if row["action_id"] != "finish_agent_turn" and "lapses" in row
    ] == []
    # The list is what the press logs.
    end = DomainAction("finish_agent_turn", 0)
    logged = apply_whole(ENGINE, state, end).events
    assert [
        (event.kind, dict(event.payload))
        for event in logged
        if event.kind.endswith("_lapsed")
    ] == [("agent_card_effect_lapsed", {"card_id": DISSECTING_KIT, "player": 0})]


def test_a_turn_end_with_nothing_left_lists_nothing() -> None:
    """Both boxes and Arrakeen's icons taken: the press lapses nothing."""

    state = _graft(
        _state((DISSECTING_KIT, SHOW_OF_STRENGTH)),
        DISSECTING_KIT,
        "arrakeen",
        SHOW_OF_STRENGTH,
    )
    for action_id, arguments in (
        ("resolve_agent_card_effect", {"box": 1}),
        ("trash_grafted_card_for_specimen", {}),
        ("resolve_board_effect", {"effect": "troops"}),
        ("resolve_board_effect", {"effect": "cards"}),
    ):
        state = _apply(state, action_id, **arguments)
    end = DomainAction("finish_agent_turn", 0)
    assert end in ENGINE.whole_actions(state, 0)
    result = apply_whole(ENGINE, state, end)
    outcome = RuleResult(state=result.state, events=result.events)
    assert lapsed_effects(0, outcome) is None


def test_lapses_name_only_the_seats_own_public_events() -> None:
    """Another seat's lapse or a hidden event never reaches the list."""

    state = _state(())
    events = (
        GameEvent("a", "board_effect_lapsed", (("effect", "tech"), ("player", 0))),
        GameEvent("b", "board_effect_lapsed", (("effect", "tech"), ("player", 1))),
        GameEvent(
            "c",
            "agent_card_effect_lapsed",
            (("card_id", "x"), ("player", 0)),
            visible_to=(0,),
        ),
        GameEvent("d", "contract_icons_fizzled", (("count", 1), ("player", 0))),
    )
    assert lapsed_effects(0, RuleResult(state=state, events=events)) == [
        {"kind": "board_effect_lapsed", "payload": {"effect": "tech", "player": 0}}
    ]


def test_a_box_left_to_expire_later_names_the_draw_added_to_it() -> None:
    """A boosted Truthtrance at Desert Tactics: its own box is done, Urgent
    Shigawire's draw "added to its Agent box" still waits [Urgent Shigawire
    card]. Trashing it through Arrakis Planetologist's frame, whose Intrigue
    card is still to come, leaves the expiry to the frame's close (OQ-022;
    OQ-106); the row names the draw the engine will expire then (2026-10-31
    review: it named nothing)."""

    from tests.unit.rules import test_bloodlines_cards as bc

    truthtrance = bc._card("truthtrance")
    state = bc._state(
        bc._owner(
            hand=(truthtrance,),
            deck=bc.STARTERS[:2],
            resources=Resources(water=1),
            bene_gesserit_boost_pending=True,
        )
    )
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "desert_tactics"
    )
    placed = apply_placement(ENGINE, state, placement).state
    placed = replace(
        placed,
        players=(
            replace(placed.players[0], leader_id="liet_kynes"),
            *placed.players[1:],
        ),
    )
    framed = replace(
        placed,
        decision_stack=(
            *placed.decision_stack,
            optional_trash_frame(
                0,
                "round:1:player:0:planetologist",
                printer=trash_printer(Source.LEADER, "liet_kynes"),
                intrigue=True,
            ),
        ),
    )
    row = ("trash_optional_card", (("card_id", truthtrance),))
    (lost,) = _forfeits(framed)[row]
    assert (lost["card_id"], lost["effects"], lost["effects_ko"]) == (
        truthtrance,
        ["Draw 1 card"],
        ["{draw:1}"],
    )
    # What the engine expires once the Intrigue card is drawn.
    trashed = apply_whole(ENGINE, framed, DomainAction(row[0], 0, row[1])).state
    draw = DomainAction("draw_planetologist_intrigue", 0)
    expired = [
        dict(event.payload)
        for event in apply_whole(ENGINE, trashed, draw).events
        if event.kind == "agent_card_effect_expired"
    ]
    assert expired == [{"card_id": truthtrance, "effect": "cards", "player": 0}]


# --- what the fields may read (2026-10-31 review) ----------------------------


def _hidden_twin(state: GameState) -> GameState:
    """``state`` with every card the seat cannot see placed otherwise: its
    own deck's order, the other seats' hidden Intrigue cards, the Imperium
    and Intrigue decks' orders."""

    owner = state.players[0]
    others = []
    intrigue = list(reversed(state.intrigue_deck))
    for seat in state.players[1:]:
        dealt = (intrigue.pop(),) if intrigue else ()
        others.append(replace(seat, intrigue_cards=(*seat.intrigue_cards, *dealt)))
    return replace(
        state,
        players=(replace(owner, deck=tuple(reversed(owner.deck))), *others),
        imperium_deck=tuple(reversed(state.imperium_deck)),
        intrigue_deck=tuple(intrigue),
    )


def _fields(state: GameState) -> dict[tuple[str, str], tuple[Any, Any]]:
    """Each served row's ``forfeit`` and ``lapses``, by its action."""

    manager = GameSessionManager()
    game_id = str(
        manager.create_game(
            FOUR_HUMANS, immortality=True, promo_cards=True, game_seed=1
        )["game_id"]
    )
    manager._get(game_id).state = state
    return {
        (row["action_id"], repr(sorted(row["arguments"].items()))): (
            row.get("forfeit"),
            row.get("lapses"),
        )
        for row in _served(manager, game_id, 0)
    }


def test_the_fields_read_nothing_the_seat_cannot_see() -> None:
    """Two positions that differ only in cards the seat cannot see (its own
    deck's order, the other seats' Intrigue cards, the decks' orders) serve
    the same ``forfeit`` and ``lapses`` on every row: the user's graft (a
    forfeit, and a draw row whose dry run takes the deck's top card) and its
    turn end (a lapse)."""

    grafted = _graft(
        _state((DISSECTING_KIT, SHOW_OF_STRENGTH)),
        DISSECTING_KIT,
        "arrakeen",
        SHOW_OF_STRENGTH,
    )
    ended = grafted
    for action_id, arguments in (
        ("resolve_agent_card_effect", {"box": 1}),
        ("resolve_board_effect", {"effect": "troops"}),
        ("resolve_board_effect", {"effect": "cards"}),
    ):
        ended = _apply(ended, action_id, **arguments)
    for position, field in ((grafted, 0), (ended, 1)):
        served = _fields(position)
        assert any(entry[field] for entry in served.values())
        twin = _hidden_twin(position)
        assert twin.players[0].deck != position.players[0].deck
        assert _fields(twin) == served


def test_a_sealed_outcome_carries_neither_field() -> None:
    """A secret choice's own outcome, or one that runs into the reveal of
    due secret choices, previews nothing but whether it can be taken back
    (``sessions.preview_outcome``); neither ``forfeit`` nor ``lapses`` reads
    it either."""

    from dune_imperium.server.session_log import (
        SEALED_ACTION_IDS,
        SEALED_REVEAL_EVENTS,
    )
    from dune_imperium.server.sessions import _dry_run_fields

    grafted = _graft(
        _state((DISSECTING_KIT, SHOW_OF_STRENGTH)),
        DISSECTING_KIT,
        "arrakeen",
        SHOW_OF_STRENGTH,
    )
    ended = grafted
    for action_id, arguments in (
        ("resolve_agent_card_effect", {"box": 1}),
        ("resolve_board_effect", {"effect": "troops"}),
        ("resolve_board_effect", {"effect": "cards"}),
    ):
        ended = _apply(ended, action_id, **arguments)
    manager = GameSessionManager()
    game_id = str(
        manager.create_game(
            FOUR_HUMANS, immortality=True, promo_cards=True, game_seed=1
        )["game_id"]
    )
    session = manager._get(game_id)
    reveal = GameEvent(
        "sealed", sorted(SEALED_REVEAL_EVENTS)[0], (("player", 1),)
    )
    for state, action, field in (
        (grafted, DomainAction("trash_grafted_card_for_specimen", 0), "forfeit"),
        (ended, DomainAction("finish_agent_turn", 0), "lapses"),
    ):
        session.state = state
        result = apply_whole(ENGINE, state, action)
        outcome = RuleResult(state=result.state, events=result.events)
        assert field in _dry_run_fields(session, action, outcome)
        sealed = RuleResult(
            state=result.state, events=(*result.events, reveal)
        )
        assert field not in _dry_run_fields(session, action, sealed)
    session.state = grafted
    result = apply_whole(
        ENGINE, grafted, DomainAction("trash_grafted_card_for_specimen", 0)
    )
    secret = DomainAction(sorted(SEALED_ACTION_IDS)[0], 0)
    outcome = RuleResult(state=result.state, events=result.events)
    assert "forfeit" not in _dry_run_fields(session, secret, outcome)
