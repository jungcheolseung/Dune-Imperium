"""Triggered draws held as the owner's own step (OQ-106, ``rules.owed_draws``).

User ruling 2026-10-10 (project convention): "그 외에는 전부 나누자. 특히
카드 드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를 폐기하고 싶을 수
있잖아." A draw that another printed effect triggers waits, inside the seat's
own turn, as its own step taken in any order with the turn's other effects
("You may carry out all these effects in any order." [Main p. 9]) and before
the turn ends; anywhere else it is drawn at once. The ones an adopted
community ruling says come at once (user decision 2026-10-10, "가 로 가자")
are the owner's very next step instead (``frames.draw_is_immediate``).
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import (
    ChanceDecision,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import Influence
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import OWED_INTRIGUE, hold_draw
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.owed_draws import (
    legal_owed_draw_actions,
    pay_stale_owed_draws,
)
from dune_imperium.simulation import InvariantViolation, check_owed_draws

ENGINE = UprisingRulesEngine()
DRAW = DomainAction(action_id="draw_owed_intrigue", actor=0)
FINISH = DomainAction(action_id="finish_agent_turn", actor=0)


def _first_turn() -> GameState:
    """Seed 0: seat 0's first turn, a Sardaukar Soldier in its discard pile."""

    state = ENGINE.reset(RulesetConfig(), 0)
    assert ENGINE.current_decision(state).owner == 0  # type: ignore[union-attr]
    soldier = next(c for c in state.imperium_deck if ":sardaukar_soldier:" in c)
    owner = state.players[0]
    return replace(
        state,
        imperium_deck=tuple(c for c in state.imperium_deck if c != soldier),
        players=(replace(owner, discard_pile=(soldier,)), *state.players[1:]),
    )


def _soldier(state: GameState) -> str:
    return state.players[0].discard_pile[0]


def _at_desert_tactics(state: GameState) -> GameState:
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == "desert_tactics"
    )
    return apply_placement(ENGINE, state, placement).state


def _trash_soldier(state: GameState, soldier: str) -> GameState:
    trash = DomainAction(
        action_id="trash_card_for_desert_tactics",
        actor=0,
        arguments=(("card_id", soldier),),
    )
    assert trash in ENGINE.legal_actions(state, 0)
    return ENGINE.apply(state, trash).state


def test_a_trash_trigger_draw_waits_and_holds_the_turn_end() -> None:
    state = _first_turn()
    soldier = _soldier(state)
    placed = _at_desert_tactics(state)
    intrigue_before = placed.players[0].intrigue_cards
    trashed = _trash_soldier(placed, soldier)

    assert trashed.players[0].intrigue_cards == intrigue_before
    assert [entry[:2] for entry in trashed.players[0].owed_draws] == [
        (OWED_INTRIGUE, f"card:{soldier}")
    ]
    offered = ENGINE.legal_actions(trashed, 0)
    assert offered.count(DRAW) == 1

    # Resolve everything else first: the turn end still waits for the draw.
    while steps := [
        action
        for action in ENGINE.legal_actions(trashed, 0)
        if action.action_id in ("resolve_board_effect", "resolve_faction_influence")
    ]:
        trashed = ENGINE.apply(trashed, steps[0]).state
    offered = ENGINE.legal_actions(trashed, 0)
    assert FINISH not in offered
    assert DRAW in offered

    drawn = ENGINE.apply(trashed, DRAW).state
    assert len(drawn.players[0].intrigue_cards) == len(intrigue_before) + 1
    assert drawn.players[0].owed_draws == ()
    offered = ENGINE.legal_actions(drawn, 0)
    assert DRAW not in offered
    assert FINISH in offered


def test_the_waiting_draw_and_the_other_effects_resolve_in_either_order() -> None:
    state = _first_turn()
    soldier = _soldier(state)
    trashed = _trash_soldier(_at_desert_tactics(state), soldier)

    def others_then_draw(working: GameState) -> GameState:
        while steps := [
            a
            for a in ENGINE.legal_actions(working, 0)
            if a.action_id in ("resolve_board_effect", "resolve_faction_influence")
        ]:
            working = ENGINE.apply(working, steps[0]).state
        return ENGINE.apply(working, DRAW).state

    def draw_then_others(working: GameState) -> GameState:
        working = ENGINE.apply(working, DRAW).state
        while steps := [
            a
            for a in ENGINE.legal_actions(working, 0)
            if a.action_id in ("resolve_board_effect", "resolve_faction_influence")
        ]:
            working = ENGINE.apply(working, steps[0]).state
        return working

    late = others_then_draw(trashed).players[0]
    early = draw_then_others(trashed).players[0]
    assert late.intrigue_cards == early.intrigue_cards
    assert late.influence == early.influence
    assert late.troops_garrison == early.troops_garrison
    assert late.owed_draws == early.owed_draws == ()


def test_a_track_bonus_reached_outside_the_seats_turn_is_drawn_at_once() -> None:
    state = _first_turn()
    owner = replace(
        state.players[1], influence=replace(state.players[1].influence, bene_gesserit=3)
    )
    # Another seat's gain in seat 0's turn: not that seat's own turn.
    others = gain_faction_influence(
        replace(state, players=(state.players[0], owner, *state.players[2:])),
        1,
        Faction.BENE_GESSERIT,
        1,
        event_prefix="test",
    ).state
    assert len(others.players[1].intrigue_cards) == 1
    assert others.players[1].owed_draws == ()
    # A Conflict reward: no turn is open at all.
    combat = gain_faction_influence(
        replace(
            state,
            phase=GamePhase.COMBAT,
            decision_stack=(),
            players=(state.players[0], owner, *state.players[2:]),
        ),
        1,
        Faction.BENE_GESSERIT,
        1,
        event_prefix="test",
    ).state
    assert len(combat.players[1].intrigue_cards) == 1
    assert combat.players[1].owed_draws == ()


def test_a_draw_left_waiting_outside_its_seats_turn_is_paid_and_flagged() -> None:
    state = _first_turn()
    stray = replace(
        state,
        players=(
            state.players[0],
            hold_draw(state.players[1], OWED_INTRIGUE, "bene_gesserit_4", "test"),
            *state.players[2:],
        ),
    )
    assert legal_owed_draw_actions(stray, 1) == ()
    with pytest.raises(InvariantViolation, match="outside their turn"):
        check_owed_draws(stray)
    paid = pay_stale_owed_draws(RuleResult(state=stray)).state
    assert len(paid.players[1].intrigue_cards) == 1
    assert paid.players[1].owed_draws == ()
    check_owed_draws(paid)
    # The seat's own waiting draw is not paid by the hook.
    own = replace(
        state,
        players=(
            hold_draw(state.players[0], OWED_INTRIGUE, "bene_gesserit_4", "test"),
            *state.players[1:],
        ),
    )
    assert pay_stale_owed_draws(RuleResult(state=own)).state == own


def _hungry_turn() -> tuple[GameState, int, str, str]:
    """Steersman Y'rkoon's first Agent turn at Desert Tactics, deck empty.

    The seat to act first (seed 0 with Bloodlines) is made Y'rkoon holding
    three spice gained this turn, so "Whenever you gain 3 or more spice in a
    single turn: draw a card" [Steersman Y'rkoon card] is earned by the
    placement's step and waits as his own step (OQ-106). Two starter cards
    lie in his discard pile; returns the state, the seat and those cards.
    """

    state = ENGINE.reset(RulesetConfig(bloodlines=True), 0)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    owner = state.players[seat]
    cards = (*owner.hand, *owner.deck)
    seek_allies = next(card for card in cards if ":seek_allies:" in card)
    weak, kept = [card for card in cards if card != seek_allies][:2]
    steersman = replace(
        owner,
        leader_id="steersman_y_rkoon",
        leader_face_id="steersman_y_rkoon",
        hand=(seek_allies,),
        deck=(),
        discard_pile=(weak, kept),
        resources=replace(owner.resources, spice=3),
        spice_at_turn_start=0,
    )
    players = list(state.players)
    players[seat] = steersman
    state = replace(state, players=tuple(players))
    placement = next(
        action
        for action in executable_placements(state, seat)
        if dict(action.arguments)["space_id"] == "desert_tactics"
    )
    return apply_placement(ENGINE, state, placement).state, seat, weak, kept


def test_a_card_owed_by_hungry_for_spice_waits_so_a_discard_trash_comes_first() -> (
    None
):
    # "특히 카드 드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를
    # 폐기하고 싶을 수 있잖아." (user ruling 2026-10-10, OQ-106): with the
    # deck empty the draw reshuffles the discard pile [Main p. 10], so a
    # discard-pile card trashed first (Desert Tactics' "trash a card")
    # never comes back; drawn first, the same card may.
    turn, seat, weak, kept = _hungry_turn()
    draw = DomainAction(action_id="draw_owed_card", actor=seat)
    assert [entry[:2] for entry in turn.players[seat].owed_draws] == [
        ("card", "hungry_for_spice")
    ]
    offered = ENGINE.legal_actions(turn, seat)
    assert draw in offered
    assert DomainAction(action_id="finish_agent_turn", actor=seat) not in offered
    trash = DomainAction(
        action_id="trash_card_for_desert_tactics",
        actor=seat,
        arguments=(("card_id", weak),),
    )
    assert trash in offered

    trashed = ENGINE.apply(turn, trash).state
    assert trashed.players[seat].trashed == (weak,)
    drawn = ENGINE.apply(trashed, draw).state
    decision = ENGINE.current_decision(drawn)
    assert isinstance(decision, ChanceDecision)
    assert decision.options == (kept,)  # the reshuffle cannot bring it back
    drawn = ENGINE.apply(drawn, ChanceOutcome(decision.decision_id, (kept,))).state
    assert drawn.players[seat].hand == (kept,)
    assert drawn.players[seat].owed_draws == ()
    assert draw not in ENGINE.legal_actions(drawn, seat)

    # Drawn first, the reshuffle holds both cards.
    early = ENGINE.apply(turn, draw).state
    decision = ENGINE.current_decision(early)
    assert isinstance(decision, ChanceDecision)
    assert set(decision.options) == {weak, kept}


# --- Immediate triggered draws (user decision 2026-10-10, "가 로 가자") ---------
#
# Three draws whose adopted community rulings (OQ-057) say they come at once
# are still their own step after the trigger, but the owner's very next one:
# the Bene Gesserit Influence 4 card and Imperial Birthright ("faction
# bonuses (such as drawing an Intrigue on the BG track) may interrupt this
# flow", Message from designer), CHOAM Transports' card ("can't be
# deferred", Message from designer) and an acquire box's card ("Acquire
# Effects must be taken immediately upon acquiring the Card or Tech.",
# Direwolf Discord).

DRAW_CARD = DomainAction(action_id="draw_owed_card", actor=0)
INFLUENCE = DomainAction(action_id="resolve_faction_influence", actor=0)


def _faction_space_turn(
    space_id: str, leader_id: str, influence: Influence
) -> GameState:
    """Seed 0: seat 0's first turn, Diplomacy placed at ``space_id``.

    Seat 0 is made ``leader_id`` with ``influence`` by hand, so the space's
    Faction icon reaches the track step under test.
    """

    state = ENGINE.reset(RulesetConfig(), 0)
    owner = state.players[0]
    state = replace(
        state,
        players=(
            replace(
                owner,
                leader_id=leader_id,
                leader_face_id=leader_id,
                influence=influence,
            ),
            *state.players[1:],
        ),
    )
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_placement(ENGINE, state, placement).state


@pytest.mark.parametrize(
    ("space_id", "leader_id", "influence", "origin"),
    (
        # "When you reach 4 Influence, you earn the bonus shown on that
        # space of the track" [Main p. 7]: the Bene Gesserit strip's card.
        (
            "secrets",
            "feyd_rautha_harkonnen",
            Influence(bene_gesserit=3),
            "bene_gesserit_4",
        ),
        # "When you reach [Emperor] 2 Influence: [Intrigue 1 draw]."
        # [Princess Irulan card]
        (
            "dutiful_service",
            "princess_irulan",
            Influence(emperor=1),
            "imperial_birthright",
        ),
    ),
)
def test_an_influence_card_is_the_owners_only_step_after_the_influence(
    space_id: str, leader_id: str, influence: Influence, origin: str
) -> None:
    placed = _faction_space_turn(space_id, leader_id, influence)
    intrigue_before = placed.players[0].intrigue_cards
    assert INFLUENCE in ENGINE.legal_actions(placed, 0)

    reached = ENGINE.apply(placed, INFLUENCE).state
    assert reached.players[0].intrigue_cards == intrigue_before  # nothing drawn
    assert [entry[:2] for entry in reached.players[0].owed_draws] == [
        (OWED_INTRIGUE, origin)
    ]
    # The space's own effect, a Plot and the turn end all wait for the draw.
    assert ENGINE.legal_actions(reached, 0) == (DRAW,)

    drawn = ENGINE.apply(reached, DRAW).state
    assert len(drawn.players[0].intrigue_cards) == len(intrigue_before) + 1
    assert drawn.players[0].owed_draws == ()
    offered = ENGINE.legal_actions(drawn, 0)
    assert DRAW not in offered
    assert any(action.action_id == "resolve_board_effect" for action in offered)


def test_an_immediate_draw_takes_its_own_entry_and_leaves_a_free_one_free() -> (
    None
):
    # A free-order draw (a Tleilaxu track card, OQ-106 item 6) already waits
    # when the Bene Gesserit card is earned: the forced press takes the
    # immediate one, and the free one is again offered with the rest.
    placed = _faction_space_turn(
        "secrets", "feyd_rautha_harkonnen", Influence(bene_gesserit=3)
    )
    owner = placed.players[0]
    waiting = replace(
        placed,
        players=(
            hold_draw(owner, OWED_INTRIGUE, "tleilaxu_track", "test:free"),
            *placed.players[1:],
        ),
    )
    offered = ENGINE.legal_actions(waiting, 0)
    assert DRAW in offered and INFLUENCE in offered

    reached = ENGINE.apply(waiting, INFLUENCE).state
    assert ENGINE.legal_actions(reached, 0) == (DRAW,)
    drawn = ENGINE.apply(reached, DRAW)
    assert [entry[:2] for entry in drawn.state.players[0].owed_draws] == [
        (OWED_INTRIGUE, "tleilaxu_track")
    ]
    (logged,) = [e for e in drawn.events if e.kind == "intrigue_card_drawn"]
    assert logged.event_id.startswith(
        "round:1:player:0:influence:bene_gesserit:track_bonus:0:intrigue:"
    )
    offered = ENGINE.legal_actions(drawn.state, 0)
    assert DRAW in offered
    assert any(action.action_id == "resolve_board_effect" for action in offered)


def _transports_turn() -> GameState:
    """Seed 1 with CHOAM, Bloodlines and Tech: seat 0's first Agent at Arrakeen.

    Seat 0 is given CHOAM Transports and the Arrakeen I Contract ("Send an
    Agent to Arrakeen" -> 1 water) by hand; Reconnaissance goes to Arrakeen.
    """

    config = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
    state = ENGINE.reset(config, 1)
    assert ENGINE.current_decision(state).owner == 0  # type: ignore[union-attr]
    contract = "contract:arrakeen_i"
    owner = state.players[0]
    state = replace(
        state,
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c != contract
        ),
        contract_bank=tuple(c for c in state.contract_bank if c != contract),
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile != "choam_transports")
            for stack in state.tech_stacks
        ),
        players=(
            replace(
                owner,
                tech_ids=("choam_transports",),
                active_contract_ids=(contract,),
            ),
            *state.players[1:],
        ),
    )
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    return apply_placement(ENGINE, state, placement).state


def test_choam_transports_card_is_the_owners_next_step_after_the_completion() -> (
    None
):
    # "When you complete a contract: draw a card" [CHOAM Transports Tech
    # tile]; "The card draw from CHOAM Transports is triggered as soon as the
    # contract is completed and can't be deferred." (Message from designer)
    placed = _transports_turn()
    hand_before = placed.players[0].hand
    complete = DomainAction(
        action_id="complete_contract",
        actor=0,
        arguments=(("instance_id", "contract:arrakeen_i"),),
    )
    assert complete in ENGINE.legal_actions(placed, 0)

    completed = ENGINE.apply(placed, complete).state
    seat = completed.players[0]
    assert seat.completed_contract_ids == ("contract:arrakeen_i",)
    assert seat.hand == hand_before  # the completion draws nothing
    assert seat.tech_cards_owed == 0
    assert [entry[:2] for entry in seat.owed_draws] == [
        ("card", "choam_transports")
    ]
    assert ENGINE.legal_actions(completed, 0) == (DRAW_CARD,)

    drawn = ENGINE.apply(completed, DRAW_CARD).state
    assert len(drawn.players[0].hand) == len(hand_before) + 1
    assert drawn.players[0].owed_draws == ()
    offered = ENGINE.legal_actions(drawn, 0)
    assert DRAW_CARD not in offered
    assert {"resolve_board_effect", "deploy_troops"} <= {
        action.action_id for action in offered
    }
