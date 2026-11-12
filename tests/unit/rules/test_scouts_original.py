"""Arrakeen Scouts on the original game: the items that reuse the module's
mechanisms (stage P8b-1).

The original game plays the app's own schedule pools (docs/rules/
arrakeen-scouts.md 9a, plan 20): its subcommittees, events, auctions and
sale are records of their own, whose lines the module's executors already
know. The items checked here: the subcommittees Appropriations, Intelligence,
Oversight (the original wording), Joint Forces, Development and Political
Affairs; the events Assassination, Secrets for Sale, Change of Plans, Gift of
Water, Test of Loyalty, Guild Negotiation, Political Equilibrium, The
Emperor's Tax, Water for Spice Smugglers and Bene Gesserit Treachery; the
Treachery auctions and Soo-Soo Sook! Water Peddlers.

The rules the tests quote:

- "각자 선택"인 이벤트는 First Player부터 차례로 한 가지를 고른다; "또는
  패스"가 있으면 선택하지 않아도 된다; 패스가 없으면 반드시 하나를 해야
  하며, 할 수 없는 쪽은 고를 수 없다 (docs/rules/arrakeen-scouts.md 6, OQ-071).
- Sealed auctions: "이긴 좌석만 입찰액을 낸다 ... 1위가 동점이면 모두 1위
  보상을 받고 2위 보상은 없다" (8.1, OQ-073).
- Influence 얻기: "하나·둘·잃기 — 둘은 한 진영" [DI p. 16]
  (docs/rules/imperium-base.md 11).
"""

from collections import Counter
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.arrakeen_scouts import (
    SUBCOMMITTEES_BY_ID,
    ScoutsPool,
    scouts_pool,
    subcommittees_for,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_effects import (
    SCOUTS_COLLECT,
    SCOUTS_NO_INFLUENCE,
    SCOUTS_NO_OPTION,
)

# Seated as named, so no Leader changes a cost and no Leader draft is dealt.
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
ORIGINAL = RulesetConfig(
    base_game=BaseGame.IMPERIUM, arrakeen_scouts=True, first_player_seat_zero=True
)
ORIGINAL_IMMORTALITY = replace(ORIGINAL, immortality=True)
ORIGINAL_BLOODLINES = replace(ORIGINAL, bloodlines=True)
UPRISING_ONLY_SUBCOMMITTEES = frozenset(
    {
        "appropriations",
        "intelligence",
        "oversight",
        "choam_coordination",
        "forecasting",
        "choam_management",
        "contingencies",
        "leverage",
    }
)


def _start(config: RulesetConfig, seed: int = 3) -> GameState:
    """Round 1, seat 0's first turn (the Scouts step's subcommittees drawn)."""

    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _seats(state: GameState, seat_fields: dict[str, dict[str, Any]]) -> GameState:
    rich = Resources(solari=5, spice=5, water=2)
    return replace(
        state,
        players=tuple(
            replace(
                player,
                **{"resources": rich, **seat_fields.get(str(player.player_id), {})},
            )
            for player in state.players
        ),
    )


def _base(
    config: RulesetConfig = ORIGINAL,
    round_number: int = 4,
    seats: dict[str, dict[str, Any]] | None = None,
) -> GameState:
    """``round_number``'s Scouts step about to draw its event; seat 0 is First
    Player. ``seats`` sets fields of a seat by its number. The mid auction is
    round 5 (round 6 when the event is round 5's)."""

    state = _seats(_start(config), seats or {})
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        decision_stack=(),
        scouts_opening=True,
        scouts_mid_auction_round=6 if round_number == 5 else 5,
        scouts_late_auction_round=9,
    )


def _draw_decision(state: GameState) -> ChanceDecision:
    advanced = _advance_automatic(RuleResult(state=state)).state
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    assert isinstance(frame.decision, ChanceDecision)
    return frame.decision


def _reveal(state: GameState, item_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    decision = advanced.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    ticket = next(o for o in decision.options if o.split("#")[0] == item_id)
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(ticket,))
    ).state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _offered(state: GameState) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
    return [
        (a.action_id, a.arguments) for a in ENGINE.whole_actions(state, _owner(state))
    ]


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = (*ENGINE.legal_actions(state, seat), *ENGINE.whole_actions(state, seat))
    assert action in legal, (action, legal)
    return apply_whole(ENGINE, state, action).state


def _on_turn(state: GameState) -> bool:
    return state.decision_stack[-1].kind == FrameKind.TURN


def _takes_nothing(state: GameState, seat: int) -> GameState:
    """A seat with no line it can take is asked too; at an item that prints
    no pass its one row takes nothing (OQ-071, user ruling 2026-09-30,
    cleanup-2a)."""

    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == seat
    assert _offered(state) == [(SCOUTS_NO_OPTION, ())]
    return _act(state, SCOUTS_NO_OPTION)


def _passes_with_nothing(state: GameState, seat: int) -> GameState:
    """A seat with no line it can take, at an item that prints a pass, gets
    that pass and the wording every seat gets, so the table cannot tell it
    from a seat that chose to pass (OQ-071, user decision 2026-11-11 "(가)";
    hidden-information sweep finding 1)."""

    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_CHOICE
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == seat
    assert frame.decision.prompt == "Choose an Arrakeen Scouts option or pass"
    assert _offered(state) == [("scouts_pass", ())]
    after = _act(state, "scouts_pass")
    new = after.event_log[len(state.event_log) :]
    assert [
        dict(e.payload)["player"] for e in new if e.kind == "scouts_choice_passed"
    ] == [seat]
    assert not any(e.kind == "scouts_choice_skipped" for e in new)
    return after


def _pass_the_rest(state: GameState) -> GameState:
    while not _on_turn(state):
        assert ("scouts_pass", ()) in _offered(state)
        state = _act(state, "scouts_pass")
    return state


def _hand(**fields: Any) -> dict[str, Any]:
    return fields


# --- The draw ------------------------------------------------------------------------


@pytest.mark.parametrize("config", [ORIGINAL, ORIGINAL_IMMORTALITY])
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_the_original_games_subcommittees_come_from_its_own_pool(
    config: RulesetConfig, seed: int
) -> None:
    """Round 1 shows five subcommittees of the pool the base game and
    Immortality pick (``scouts_pool``): none of the Uprising pools' own, one
    of each tier among them [Scouts schedule] (docs/rules/arrakeen-scouts.md
    2.2, 9a)."""

    state = _start(config, seed)
    assert state.round_number == 1
    assert scouts_pool(config) in (ScoutsPool.IMPERIUM, ScoutsPool.IMPERIUM_IMMORTALITY)
    drawn = state.scouts_subcommittees
    assert len(drawn) == len(set(drawn)) == 5
    pool = {
        entry.subcommittee_id
        for entry in subcommittees_for(scouts_pool(config), choam=False)
    }
    assert set(drawn) <= pool
    assert not set(drawn) & UPRISING_ONLY_SUBCOMMITTEES
    assert {SUBCOMMITTEES_BY_ID[item].tier for item in drawn} == {0, 1, 2}


def test_no_uprising_only_subcommittee_is_offered_to_the_round_one_draw() -> None:
    """Every chance option of the three tier draws is an original-pool id."""

    state = _seats(_start(ORIGINAL), {})
    state = replace(
        state,
        round_number=1,
        decision_stack=(),
        scouts_opening=True,
        scouts_subcommittees=(),
    )
    seen: set[str] = set()
    while len(state.scouts_subcommittees) < 5:
        decision = _draw_decision(state)
        seen.update(decision.options)
        state = ENGINE.apply(
            _advance_automatic(RuleResult(state=state)).state,
            ChanceOutcome(
                decision_id=decision.decision_id,
                values=decision.options[: decision.count],
            ),
        ).state
    assert seen
    assert not seen & UPRISING_ONLY_SUBCOMMITTEES
    original_pool = {
        entry.subcommittee_id
        for entry in subcommittees_for(ScoutsPool.IMPERIUM, choam=False)
    }
    assert seen == original_pool


def _tickets(state: GameState) -> Counter[str]:
    return Counter(option.split("#")[0] for option in _draw_decision(state).options)


def test_an_original_event_draw_offers_the_app_tickets() -> None:
    """The draw counts the app's baseWeight x subWeight in twentieths
    (docs/rules/arrakeen-scouts.md 2.3, 9a): a single event 20 tickets, a
    Spice Gain or Intrigue Bonus variant 10, an Influence Gain variant 15,
    Political Equilibrium 24 and every other Influence Reduction 9. Round 4
    holds the first ten (No Coming Back, a single event, only here);
    Political Equilibrium and the reductions begin in round 5, Assassination
    and the original Rotating Doors in round 6."""

    assert _tickets(_base(round_number=4)) == {
        "imperium_secrets_for_sale": 10,
        "change_of_plans": 20,
        "imperium_gift_of_water": 20,
        "test_of_loyalty": 15,
        "imperium_guild_negotiation": 15,
        # Stage P8c-1.
        "imperium_covert_operation": 20,
        # Stage P8c-2.
        "tap_into_spice_reserves": 10,
        "no_coming_back": 20,
        "intriguing_gift": 15,
        "desert_gift": 15,
    }
    five = _tickets(_base(round_number=5))
    assert five["imperium_political_equilibrium"] == 24
    assert (
        five["emperors_tax"]
        == five["imperium_water_for_spice_smugglers"]
        == five["imperium_bene_gesserit_treachery"]
        == five["fremen_exchange"]
        == 9
    )
    assert "assassination" not in five and "imperium_rotating_doors" not in five
    assert "no_coming_back" not in five
    six = _tickets(_base(round_number=6))
    assert six == {
        "assassination": 10,
        "imperium_secrets_for_sale": 10,
        "change_of_plans": 20,
        "imperium_gift_of_water": 20,
        "test_of_loyalty": 15,
        "imperium_guild_negotiation": 15,
        "imperium_political_equilibrium": 24,
        "emperors_tax": 9,
        "imperium_water_for_spice_smugglers": 9,
        "imperium_bene_gesserit_treachery": 9,
        # Stage P8c-1.
        "fremen_exchange": 9,
        "imperium_covert_operation": 20,
        # Stage P8c-2.
        "tap_into_spice_reserves": 10,
        "imperium_rotating_doors": 10,
        "intriguing_gift": 15,
        "desert_gift": 15,
    }
    assert _tickets(_base(round_number=7)) == six


def test_the_immortality_events_are_twenty_tickets_in_the_original_pool() -> None:
    """The five Immortality events (weight 1) are 20 tickets here, 10 in the
    Uprising pools (``ScoutsEvent.tickets``)."""

    tickets = _tickets(_base(ORIGINAL_IMMORTALITY, round_number=4))
    for event_id in (
        "ingratiate",
        "betrayal",
        "new_innovations",
        "termination_request",
        "offworld_operation",
    ):
        assert tickets[event_id] == 20
    assert tickets["test_of_loyalty"] == 15


def test_an_uprising_scouts_game_keeps_its_subcommittee_and_event_draws() -> None:
    """Regression: the original game's items never reach an Uprising draw.
    Round 4 with the CHOAM Module holds 170 tickets, 30 for each Influence
    family (docs/rules/arrakeen-scouts.md 6, tickets summed in tenths), and
    every subcommittee the Uprising game draws is an Uprising-pool one."""

    uprising = RulesetConfig(arrakeen_scouts=True, choam_module=True)
    engine = UprisingRulesEngine()  # the Uprising Leaders, dealt by chance
    state = engine.reset(uprising, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(engine.current_decision(state), ChanceDecision):
        decision = engine.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = engine.apply(state, resolver.resolve(decision)).state
    original_only = {
        entry.subcommittee_id
        for entry in subcommittees_for(ScoutsPool.IMPERIUM, choam=False)
    } - {
        entry.subcommittee_id
        for entry in subcommittees_for(ScoutsPool.UPRISING, choam=True)
    }
    assert original_only  # the six new ones, joint_forces, development, ...
    assert not set(state.scouts_subcommittees) & original_only
    ready = replace(
        state,
        round_number=4,
        first_player=0,
        decision_stack=(),
        scouts_opening=True,
    )
    options = _draw_decision(ready).options
    assert len(options) == 170
    by_event = Counter(option.split("#")[0] for option in options)
    assert by_event["guild_negotiation"] == by_event["royal_delegation"] == 6
    assert not set(by_event) & {
        "assassination",
        "imperium_secrets_for_sale",
        "change_of_plans",
        "imperium_gift_of_water",
        "test_of_loyalty",
        "imperium_guild_negotiation",
        "imperium_political_equilibrium",
        "emperors_tax",
        "imperium_water_for_spice_smugglers",
        "imperium_bene_gesserit_treachery",
    }
    assert (
        sum(
            count
            for event_id, count in by_event.items()
            if event_id
            in (
                "royal_delegation",
                "guild_negotiation",
                "covert_assistance",
                "gift_of_water",
                "share_intelligence",
            )
        )
        == 30
    )


def test_an_uprising_round_one_draw_keeps_its_tier_options() -> None:
    """Regression: an Uprising Scouts game's three tier draws still offer the
    same subcommittees, in catalog order, as before the original game's pools
    (docs/rules/arrakeen-scouts.md 2.2, 4): the original wording and the new
    Joint Forces, Development and Political Affairs are never among them."""

    engine = UprisingRulesEngine()
    uprising = RulesetConfig(arrakeen_scouts=True)
    state = engine.reset(uprising, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(engine.current_decision(state), ChanceDecision):
        decision = engine.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = engine.apply(state, resolver.resolve(decision)).state
    tiers = (
        ("appropriations", "intelligence", "readiness"),
        ("oversight", "investigations", "forecasting"),
        ("relations", "contingencies", "leverage"),
    )
    cleared = replace(
        state,
        round_number=1,
        first_player=0,
        decision_stack=(),
        scouts_opening=True,
        scouts_subcommittees=(),
    )
    for tier, expected in enumerate(tiers):
        drawn = cleared.scouts_subcommittees
        assert len(drawn) == tier
        decision = _draw_decision(cleared)
        assert decision.options == expected
        cleared = engine.apply(
            _advance_automatic(RuleResult(state=cleared)).state,
            ChanceOutcome(
                decision_id=decision.decision_id, values=(decision.options[0],)
            ),
        ).state
    # Two more from what is left of the whole pool.
    rest = _draw_decision(cleared)
    assert rest.count == 2
    assert rest.options == (
        "intelligence",
        "readiness",
        "investigations",
        "forecasting",
        "contingencies",
        "leverage",
    )


# --- Subcommittees (joined at the High Council) -----------------------------------


def _seated(**subcommittees: Any) -> GameState:
    """Seat 0 has sent an Agent to the original High Council and taken the
    seat [DI p. 17] (5 Solari, paid), and may now open the subcommittee list
    (docs/rules/arrakeen-scouts.md 4). It holds 5 Solari, 6 spice and 2 water
    after the visit, enough for every line below; the display is the original
    pool's Appropriations, Intelligence, Oversight, Joint Forces and
    Development unless ``subcommittees["display"]`` names five others."""

    display = subcommittees.get(
        "display",
        (
            "imperium_appropriations",
            "imperium_intelligence",
            "imperium_oversight",
            "joint_forces",
            "development",
        ),
    )
    state = _start(ORIGINAL)
    state = replace(state, scouts_subcommittees=display)
    state = _seats(state, {"0": {"resources": Resources(solari=10, spice=6, water=2)}})
    placements = [
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == "imperium_high_council"
    ]
    assert placements
    state = apply_placement(ENGINE, state, placements[0]).state
    board = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "resolve_board_effect"
        and dict(action.arguments)["effect"] == "high_council"
    )
    state = apply_whole(ENGINE, state, board).state
    assert state.players[0].high_council
    return state


def _join(state: GameState, subcommittee_id: str) -> GameState:
    state = _act(state, "choose_subcommittee")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_SUBCOMMITTEE
    return _act(state, "join_subcommittee", subcommittee_id=subcommittee_id)


def _joinable(state: GameState) -> set[str]:
    """The subcommittees the open list offers seat 0."""

    return {
        str(dict(args)["subcommittee_id"])
        for action_id, args in _offered(_act(state, "choose_subcommittee"))
        if action_id == "join_subcommittee"
    }


def test_the_original_high_council_opens_the_subcommittee_list() -> None:
    """The original board's High Council (``imperium_high_council``) queues
    the join like Uprising's, and the list offers each displayed subcommittee
    the seat can pay for."""

    assert _joinable(_seated()) == {
        "imperium_appropriations",
        "imperium_intelligence",
        "imperium_oversight",
        "joint_forces",
        "development",
    }


def test_original_appropriations_gives_a_spice_for_no_cost() -> None:
    before = _seated()
    state = _join(before, "imperium_appropriations")
    assert state.scouts_subcommittee_members == (("imperium_appropriations", 0),)
    resources = before.players[0].resources
    assert state.players[0].resources == replace(resources, spice=resources.spice + 1)
    assert state.players[0].hand == before.players[0].hand


def test_original_intelligence_draws_a_card() -> None:
    before = _seated().players[0]
    state = _join(_seated(), "imperium_intelligence")
    seat = state.players[0]
    assert seat.hand == (*before.hand, before.deck[0])
    assert seat.resources == before.resources
    assert state.scouts_subcommittee_members == (("imperium_intelligence", 0),)


def test_original_oversight_pays_a_solari_and_trashes_a_chosen_card() -> None:
    """Solari 1 -> trash a card: the trash icon is optional, so the seat
    chooses the card (or none), as the Uprising Oversight's does [Main p. 20]."""

    before = _seated().players[0]
    state = _join(_seated(), "imperium_oversight")
    assert state.players[0].resources.solari == before.resources.solari - 1
    assert state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    offered = {action for action, _ in _offered(state)}
    assert {"trash_optional_card", "decline_optional_trash"} <= offered
    card = before.hand[0]
    state = _act(state, "trash_optional_card", card_id=card)
    seat = state.players[0]
    assert card in seat.trashed and card not in seat.hand
    # No spice, unlike the Uprising Oversight (docs/rules/arrakeen-scouts.md 9a).
    assert seat.resources.spice == before.resources.spice


def test_original_oversight_may_decline_the_trash_but_still_pays() -> None:
    before = _seated().players[0]
    state = _act(_join(_seated(), "imperium_oversight"), "decline_optional_trash")
    assert state.players[0].hand == before.hand
    assert state.players[0].trashed == before.trashed
    assert state.players[0].resources.solari == before.resources.solari - 1


def test_joint_forces_pays_two_solari_for_three_troops() -> None:
    before = _seated().players[0]
    state = _join(_seated(), "joint_forces")
    seat = state.players[0]
    assert seat.resources.solari == before.resources.solari - 2
    assert seat.troops_garrison == before.troops_garrison + 3
    assert seat.troops_supply == before.troops_supply - 3
    assert state.scouts_subcommittee_members == (("joint_forces", 0),)


def test_development_pays_three_spice_for_three_cards() -> None:
    before = _seated().players[0]
    state = _join(_seated(), "development")
    seat = state.players[0]
    assert seat.resources.spice == before.resources.spice - 3
    assert seat.hand == (*before.hand, *before.deck[:3])


def test_political_affairs_gives_two_influence_to_one_chosen_faction() -> None:
    """Spice 4 -> two Influence with one Faction: "Influence 얻기(하나·둘·잃기
    — 둘은 한 진영)" [DI p. 16] (docs/rules/imperium-base.md 11); the seat picks
    the Faction once and gains both there."""

    display = ("imperium_appropriations", "imperium_intelligence", "joint_forces")
    before = _seated(display=(*display, "development", "political_affairs"))
    state = _join(before, "political_affairs")
    assert state.players[0].resources.spice == before.players[0].resources.spice - 4
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    factions = {
        dict(args)["faction"]
        for action_id, args in _offered(state)
        if action_id == "scouts_choose_faction"
    }
    assert factions == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    gained = state.players[0].influence
    state = _act(state, "scouts_choose_faction", faction="spacing_guild")
    after = state.players[0].influence
    assert after.spacing_guild == gained.spacing_guild + 2
    assert (after.emperor, after.bene_gesserit, after.fremen) == (
        gained.emperor,
        gained.bene_gesserit,
        gained.fremen,
    )
    assert state.scouts_subcommittee_members == (("political_affairs", 0),)


def test_a_new_subcommittee_the_seat_cannot_pay_is_not_offered() -> None:
    """A cost that cannot be paid keeps the line from being offered (OQ-071):
    Political Affairs needs 4 spice, Development 3, Joint Forces 2 Solari and
    Oversight 1 Solari; Appropriations costs nothing."""

    state = _seated(
        display=(
            "imperium_oversight",
            "joint_forces",
            "development",
            "political_affairs",
            "imperium_appropriations",
        )
    )
    seat = replace(state.players[0], resources=Resources(solari=1, spice=3, water=0))
    state = replace(state, players=(seat, *state.players[1:]))
    assert _joinable(state) == {
        "imperium_oversight",
        "development",
        "imperium_appropriations",
    }


# --- Events ----------------------------------------------------------------------


def test_assassination_trashes_a_hand_card_for_two_spice() -> None:
    """Optional: trash a card from your hand -> 2 spice (docs/rules/
    arrakeen-scouts.md 9a); a seat with an empty hand takes nothing."""

    state = _base(round_number=6, seats={"1": _hand(hand=())})
    state = _reveal(state, "assassination")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    held = state.players[0].hand
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    assert {dict(a.arguments)["card_id"] for a in ENGINE.whole_actions(state, 0)} == (
        set(held)
    )
    state = _act(state, "scouts_trash_card", card_id=held[0])
    assert held[0] in state.players[0].trashed
    assert held[0] not in state.players[0].hand
    assert state.players[0].resources.spice == spice + 2
    state = _passes_with_nothing(state, 1)
    state = _pass_the_rest(state)
    assert _on_turn(state)


def test_secrets_for_sale_pays_solari_or_spice_for_an_intrigue_card() -> None:
    state = _reveal(_base(), "imperium_secrets_for_sale")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
    ]
    intrigue = len(state.players[0].intrigue_cards)
    solari = state.players[0].resources.solari
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.solari == solari - 1
    assert state.players[0].resources.spice == spice
    assert len(state.players[0].intrigue_cards) == intrigue + 1
    # Seat 1 has no Solari: its spice line is the one it can take.
    state = replace(
        state,
        players=(
            state.players[0],
            replace(state.players[1], resources=Resources(solari=0, spice=2)),
            *state.players[2:],
        ),
    )
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 1),)),
    ]
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[1].resources.spice == 1
    assert len(state.players[1].intrigue_cards) == 1
    # Seat 2 can pay for neither.
    state = replace(
        state,
        players=(
            *state.players[:2],
            replace(state.players[2], resources=Resources(solari=0, spice=0)),
            state.players[3],
        ),
    )
    state = _passes_with_nothing(state, 2)
    state = _pass_the_rest(state)


def test_change_of_plans_discards_a_card_to_draw_a_card() -> None:
    state = _reveal(_base(seats={"1": _hand(hand=())}), "change_of_plans")
    hand = state.players[0].hand
    deck = state.players[0].deck
    state = _act(state, "scouts_choose_option", option=0)
    state = _act(state, "scouts_discard", card_id=hand[0])
    seat = state.players[0]
    assert hand[0] in seat.discard_pile
    assert len(seat.hand) == len(hand)  # one out, one in
    assert deck[0] in seat.hand
    # Seat 1 has no card to discard.
    state = _passes_with_nothing(state, 1)
    state = _pass_the_rest(state)


def test_gift_of_water_takes_an_arrakis_liaison_from_the_original_reserve() -> None:
    """Water 1 -> Arrakis Liaison from the Reserve, into the hand: the
    original game's own Reserve card (``content/imperium/reserve.py``), taken
    as Moment of Revelation takes Uprising's Prepare the Way."""

    state = _reveal(_base(), "imperium_gift_of_water")
    stacks = dict(state.reserve_stacks)
    assert stacks["arrakis_liaison"] > 0
    assert "prepare_the_way" not in stacks
    water = state.players[0].resources.water
    state = _act(state, "scouts_choose_option", option=0)
    seat = state.players[0]
    assert seat.resources.water == water - 1
    assert any(card.startswith("reserve:arrakis_liaison") for card in seat.hand)
    assert (
        dict(state.reserve_stacks)["arrakis_liaison"] == stacks["arrakis_liaison"] - 1
    )
    state = _pass_the_rest(state)


def test_gift_of_water_is_skipped_with_an_empty_liaison_stack() -> None:
    """A cost that buys nothing is not offered (OQ-071, OQ-022): with no
    Arrakis Liaison left every seat takes nothing and nobody pays water."""

    base = _base()
    empty = tuple(
        (card_id, 0) if card_id == "arrakis_liaison" else (card_id, count)
        for card_id, count in base.reserve_stacks
    )
    water = [player.resources.water for player in base.players]
    state = _reveal(replace(base, reserve_stacks=empty), "imperium_gift_of_water")
    for seat in range(4):
        state = _passes_with_nothing(state, seat)
    assert _on_turn(state)
    assert [player.resources.water for player in state.players] == water


def test_test_of_loyalty_loses_a_garrison_troop_for_emperor_influence() -> None:
    state = _base(
        seats={
            "0": _hand(troops_garrison=2, troops_supply=10),
            "1": _hand(troops_garrison=0, troops_supply=12),
        }
    )
    state = _reveal(state, "test_of_loyalty")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    state = _act(state, "scouts_choose_option", option=0)
    seat = state.players[0]
    assert (seat.troops_garrison, seat.troops_supply) == (1, 11)
    assert seat.influence.emperor == 1
    # Seat 1 has no garrison troop to lose.
    state = _passes_with_nothing(state, 1)
    assert state.players[1].influence.emperor == 0
    state = _pass_the_rest(state)


def test_test_of_loyalty_is_paid_by_a_garrison_commander_alone() -> None:
    """Bloodlines: "Commander는 Conflict에서 strength 2인 "troop"이다. troop을
    대상으로 하는 효과 ... 는 Commander에도 적용된다" [Bloodlines p. 4]
    (docs/rules/bloodlines.md 3, OQ-105): a garrison Commander pays the troop
    line when it is the only unit there."""

    state = _base(
        ORIGINAL_BLOODLINES,
        seats={
            "0": _hand(
                troops_garrison=0,
                troops_supply=12,
                commanders_garrison=1,
                commanders_supply=0,
            ),
            "1": _hand(troops_garrison=0, troops_supply=12, commanders_garrison=0),
        },
    )
    state = _reveal(state, "test_of_loyalty")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    state = _act(state, "scouts_choose_option", option=0)
    seat = state.players[0]
    assert (seat.commanders_garrison, seat.commanders_supply) == (0, 1)
    assert seat.troops_garrison == 0
    assert seat.influence.emperor == 1
    assert _owner(state) == 1
    state = _passes_with_nothing(state, 1)


def test_test_of_loyalty_asks_troop_or_commander_when_both_are_there() -> None:
    state = _base(
        ORIGINAL_BLOODLINES,
        seats={
            "0": _hand(
                troops_garrison=2,
                troops_supply=10,
                commanders_garrison=1,
                commanders_supply=0,
            )
        },
    )
    state = _reveal(state, "test_of_loyalty")
    state = _act(state, "scouts_choose_option", option=0)
    assert _offered(state) == [
        ("scouts_lose_garrison_unit", ()),
        ("scouts_lose_garrison_unit", (("commanders", 1),)),
    ]
    state = _act(state, "scouts_lose_garrison_unit", commanders=1)
    seat = state.players[0]
    assert (seat.troops_garrison, seat.commanders_garrison) == (2, 0)
    assert seat.influence.emperor == 1


def test_guild_negotiation_pays_two_solari_for_spacing_guild_influence() -> None:
    state = _base(seats={"1": _hand(resources=Resources(solari=1, spice=5, water=2))})
    state = _reveal(state, "imperium_guild_negotiation")
    solari = state.players[0].resources.solari
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.solari == solari - 2
    assert state.players[0].influence.spacing_guild == 1
    state = _passes_with_nothing(state, 1)
    assert state.players[1].influence.spacing_guild == 0
    state = _pass_the_rest(state)


def test_the_original_political_equilibrium_takes_one_from_each_highest_track() -> None:
    """Automatic: everyone loses 1 Influence on their highest Faction, a tie
    chosen, every seat asked (docs/rules/arrakeen-scouts.md 6, 9a)."""

    state = _base(
        round_number=6,
        seats={
            "0": _hand(influence=Influence(fremen=3, emperor=1)),
            "1": _hand(influence=Influence(spacing_guild=2, bene_gesserit=2)),
            "2": _hand(influence=Influence()),
            "3": _hand(influence=Influence(fremen=1)),
        },
    )
    state = _reveal(state, "imperium_political_equilibrium")
    assert _offered(state) == [("scouts_lose_influence", (("faction", "fremen"),))]
    state = _act(state, "scouts_lose_influence", faction="fremen")
    assert state.players[0].influence == Influence(fremen=2, emperor=1)
    assert {dict(args)["faction"] for _, args in _offered(state)} == {
        "spacing_guild",
        "bene_gesserit",
    }
    state = _act(state, "scouts_lose_influence", faction="bene_gesserit")
    assert _offered(state) == [(SCOUTS_NO_INFLUENCE, ())]
    state = _act(state, SCOUTS_NO_INFLUENCE)
    state = _act(state, "scouts_lose_influence", faction="fremen")
    assert state.players[3].influence == Influence()
    assert _on_turn(state)


def test_the_emperors_tax_is_a_mandatory_choice_of_spice_or_emperor() -> None:
    """Mandatory: pay 1 spice or lose 1 Emperor Influence; no pass (docs/rules/
    arrakeen-scouts.md 6, OQ-071). A seat that can take one line only is asked
    with that line; a seat that can take neither takes nothing."""

    state = _base(
        round_number=6,
        seats={
            "0": _hand(influence=Influence(emperor=2)),
            "1": _hand(
                influence=Influence(emperor=2),
                resources=Resources(solari=5, spice=0, water=2),
            ),
            "2": _hand(influence=Influence(), resources=Resources(spice=1)),
            "3": _hand(influence=Influence(), resources=Resources(spice=0)),
        },
    )
    state = _reveal(state, "emperors_tax")
    assert _offered(state) == [
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
    ]
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.spice == spice - 1
    assert state.players[0].influence.emperor == 2
    # Seat 1 has no spice: only the Emperor line.
    assert _offered(state) == [("scouts_choose_option", (("option", 1),))]
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[1].influence.emperor == 1
    # Seat 2 has no Emperor Influence: only the spice line.
    assert _offered(state) == [("scouts_choose_option", (("option", 0),))]
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[2].resources.spice == 0
    state = _takes_nothing(state, 3)
    assert _on_turn(state)


def test_water_for_spice_smugglers_is_water_or_spacing_guild() -> None:
    state = _base(
        round_number=6,
        seats={
            "0": _hand(influence=Influence(spacing_guild=1)),
            "1": _hand(
                influence=Influence(spacing_guild=1),
                resources=Resources(solari=5, spice=5, water=0),
            ),
            "2": _hand(influence=Influence(), resources=Resources(water=0)),
        },
    )
    state = _reveal(state, "imperium_water_for_spice_smugglers")
    assert [a for a, _ in _offered(state)] == ["scouts_choose_option"] * 2
    water = state.players[0].resources.water
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.water == water - 1
    assert _offered(state) == [("scouts_choose_option", (("option", 1),))]
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[1].influence.spacing_guild == 0
    state = _takes_nothing(state, 2)
    # Seat 3 holds water and no Influence: the water line.
    assert _offered(state) == [("scouts_choose_option", (("option", 0),))]


def test_bene_gesserit_treachery_discards_a_card_or_loses_bene_gesserit() -> None:
    """Mandatory: discard a card or Bene Gesserit -1 (the original wording; the
    Uprising event loses a garrison troop instead)."""

    state = _base(
        round_number=6,
        seats={
            "0": _hand(influence=Influence(bene_gesserit=2)),
            "1": _hand(influence=Influence(bene_gesserit=1), hand=()),
            "2": _hand(influence=Influence(), hand=()),
        },
    )
    state = _reveal(state, "imperium_bene_gesserit_treachery")
    assert [a for a, _ in _offered(state)] == ["scouts_choose_option"] * 2
    hand = state.players[0].hand
    state = _act(state, "scouts_choose_option", option=0)
    state = _act(state, "scouts_discard", card_id=hand[0])
    assert hand[0] in state.players[0].discard_pile
    assert state.players[0].influence.bene_gesserit == 2
    # Seat 1 has no card to discard: the Influence line only.
    assert _offered(state) == [("scouts_choose_option", (("option", 1),))]
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[1].influence.bene_gesserit == 0
    state = _takes_nothing(state, 2)


# --- Treachery (sealed bids in spice) ------------------------------------------------


def _auction_base(
    round_number: int = 5, seats: dict[str, dict[str, Any]] | None = None
) -> GameState:
    """Round ``round_number``'s Scouts step about to draw its auction."""

    return _auction_base_for(ORIGINAL, round_number, seats)


def _auction_base_for(
    config: RulesetConfig,
    round_number: int = 5,
    seats: dict[str, dict[str, Any]] | None = None,
) -> GameState:
    state = _seats(_start(config), seats or {})
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        decision_stack=(),
        scouts_opening=True,
        scouts_secrets_round=round_number,
        scouts_mid_auction_round=round_number if round_number < 8 else 5,
        scouts_late_auction_round=round_number if round_number >= 8 else 9,
    )


def _auction(state: GameState, item_id: str) -> GameState:
    """Answer Scouts draws until ``item_id`` is revealed."""

    while True:
        state = _advance_automatic(RuleResult(state=state)).state
        frame = state.decision_stack[-1]
        if frame.kind != FrameKind.SCOUTS_DRAW:
            return state
        decision = frame.decision
        assert isinstance(decision, ChanceDecision)
        wanted = [o for o in decision.options if o.split("#")[0] == item_id]
        state = ENGINE.apply(
            state,
            ChanceOutcome(
                decision_id=decision.decision_id,
                values=(wanted[0] if wanted else decision.options[0],),
            ),
        ).state
        if wanted:
            return state


def _bid_all(state: GameState, bids: dict[int, int]) -> GameState:
    order = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_BID:
        seat = _owner(state)
        order.append(seat)
        state = _act(state, "scouts_bid", count=bids[seat])
        state = _act(state, "confirm_scouts_bid")
    assert order == [0, 1, 2, 3]
    return state


def _collect(state: GameState, seat: int) -> GameState:
    """Collect a winner's line: it waits for its seat's own click, the one
    action offered (user decision 2026-11-01, OQ-164)."""

    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    assert _owner(state) == seat
    collect = DomainAction(action_id=SCOUTS_COLLECT, actor=seat)
    assert ENGINE.legal_actions(state, seat) == (collect,)
    return ENGINE.apply(state, collect).state


def _resume(state: GameState) -> GameState:
    """Answer the pause before the next winner's reward (rules/pauses.py)."""

    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.PAUSE
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    return ENGINE.apply(
        state, ChanceOutcome(decision_id=decision.decision_id, values=decision.options)
    ).state


def _intrigue(state: GameState) -> list[int]:
    return [len(player.intrigue_cards) for player in state.players]


def _spice(state: GameState) -> list[int]:
    return [player.resources.spice for player in state.players]


def test_treachery_is_a_sealed_auction_bid_in_spice() -> None:
    state = _auction(_auction_base(), "treachery_mid")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_BID
    bids = [
        dict(a.arguments)["count"]
        for a in ENGINE.whole_actions(state, 0)
        if a.action_id == "scouts_bid"
    ]
    # 0..5 spice: the seat holds 5 spice (the bid's currency).
    assert bids == list(range(6))
    poor = _auction(
        _auction_base(
            seats={"0": _hand(resources=Resources(solari=9, spice=2, water=0))}
        ),
        "treachery_mid",
    )
    assert [
        dict(a.arguments)["count"]
        for a in ENGINE.whole_actions(poor, 0)
        if a.action_id == "scouts_bid"
    ] == [0, 1, 2]


def test_treachery_mid_the_winner_pays_spice_and_draws_an_intrigue_card() -> None:
    state = _auction(_auction_base(), "treachery_mid")
    spice, intrigue = _spice(state), _intrigue(state)
    solari = [player.resources.solari for player in state.players]
    state = _bid_all(state, {0: 2, 1: 4, 2: 1, 3: 0})
    # Seat 1 won; the losers (2 and 1 spice bid, 0 bid) paid nothing.
    assert _spice(state) == [spice[0], spice[1] - 4, spice[2], spice[3]]
    # Its card waits for its click (OQ-164).
    assert _intrigue(state) == intrigue
    state = _collect(state, 1)
    assert _intrigue(state) == [intrigue[0], intrigue[1] + 1, intrigue[2], intrigue[3]]
    assert [player.resources.solari for player in state.players] == solari
    assert state.scouts_bids == ()
    # The round's event is drawn next, after the mid auction (2.1).
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW


def test_treachery_mid_a_tie_for_first_pays_and_rewards_each_tied_seat() -> None:
    state = _auction(_auction_base(), "treachery_mid")
    spice, intrigue = _spice(state), _intrigue(state)
    state = _bid_all(state, {0: 3, 1: 3, 2: 1, 3: 0})
    # Both tied first places win and pay; the second winner's reward waits
    # behind a pause (OQ-103); each line waits for its seat's click (OQ-164).
    state = _collect(state, 0)
    state = _resume(state)
    state = _collect(state, 1)
    assert _spice(state) == [spice[0] - 3, spice[1] - 3, spice[2], spice[3]]
    assert _intrigue(state) == [
        intrigue[0] + 1,
        intrigue[1] + 1,
        intrigue[2],
        intrigue[3],
    ]


def test_treachery_mid_nobody_pays_when_nobody_bids() -> None:
    state = _auction(_auction_base(), "treachery_mid")
    spice, intrigue = _spice(state), _intrigue(state)
    state = _bid_all(state, {0: 0, 1: 0, 2: 0, 3: 0})
    assert _spice(state) == spice
    assert _intrigue(state) == intrigue


def test_treachery_late_first_draws_two_second_one_losers_pay_nothing() -> None:
    state = _auction(_auction_base(8), "treachery_late")
    spice, intrigue = _spice(state), _intrigue(state)
    state = _bid_all(state, {0: 2, 1: 5, 2: 3, 3: 0})
    # 1st place (seat 1, 5 spice) draws 2; the second winner's reward waits
    # behind a pause; 2nd place (seat 2, 3 spice) draws 1; seat 0 (2 spice,
    # third) and seat 3 (0) neither pay nor draw. Each winner collects its
    # line by its own click (OQ-164).
    state = _collect(state, 1)
    state = _resume(state)
    state = _collect(state, 2)
    assert _spice(state) == [spice[0], spice[1] - 5, spice[2] - 3, spice[3]]
    assert _intrigue(state) == [
        intrigue[0],
        intrigue[1] + 2,
        intrigue[2] + 1,
        intrigue[3],
    ]


def test_treachery_late_a_tie_for_first_gives_no_second_place() -> None:
    state = _auction(_auction_base(9), "treachery_late")
    spice, intrigue = _spice(state), _intrigue(state)
    state = _bid_all(state, {0: 4, 1: 4, 2: 2, 3: 1})
    state = _collect(state, 0)
    state = _resume(state)
    state = _collect(state, 1)
    # Both tied seats take first place's two cards and pay 4; the next
    # highest bid (2) is third place, so it neither pays nor draws (8.1).
    assert _spice(state) == [spice[0] - 4, spice[1] - 4, spice[2], spice[3]]
    assert _intrigue(state) == [
        intrigue[0] + 2,
        intrigue[1] + 2,
        intrigue[2],
        intrigue[3],
    ]
    assert _on_turn(state)


def test_treachery_late_a_tie_for_second_rewards_each_tied_seat() -> None:
    state = _auction(_auction_base(8), "treachery_late")
    spice, intrigue = _spice(state), _intrigue(state)
    state = _bid_all(state, {0: 5, 1: 2, 2: 2, 3: 0})
    state = _collect(state, 0)
    state = _resume(state)
    state = _collect(state, 1)
    state = _resume(state)
    state = _collect(state, 2)
    assert _spice(state) == [spice[0] - 5, spice[1] - 2, spice[2] - 2, spice[3]]
    assert _intrigue(state) == [
        intrigue[0] + 2,
        intrigue[1] + 1,
        intrigue[2] + 1,
        intrigue[3],
    ]


# --- Soo-Soo Sook! Water Peddlers -----------------------------------------------------


def _late_sale(state: GameState) -> GameState:
    """Round 9 with the late auction in round 8: the sale is drawn now."""

    return replace(
        state,
        round_number=9,
        scouts_mid_auction_round=5,
        scouts_late_auction_round=8,
    )


def _reveal_sale(state: GameState, sale_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    decision = advanced.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert sale_id in decision.options
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(sale_id,))
    ).state


def test_water_peddlers_sells_one_water_for_two_solari() -> None:
    state = _reveal_sale(_late_sale(_base()), "water_peddlers")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
    ]
    solari, water = state.players[0].resources.solari, state.players[0].resources.water
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.solari == solari - 2
    assert state.players[0].resources.water == water + 1


def test_water_peddlers_sells_two_water_for_four_solari() -> None:
    state = _reveal_sale(_late_sale(_base()), "water_peddlers")
    solari, water = state.players[0].resources.solari, state.players[0].resources.water
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[0].resources.solari == solari - 4
    assert state.players[0].resources.water == water + 2


def test_water_peddlers_offers_each_seat_the_lines_it_can_pay() -> None:
    state = _late_sale(
        _base(
            seats={
                "0": _hand(resources=Resources(solari=3, spice=0, water=0)),
                "1": _hand(resources=Resources(solari=1, spice=0, water=0)),
            }
        )
    )
    state = _reveal_sale(state, "water_peddlers")
    # Seat 0 holds 3 Solari: the 2-Solari line only.
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    state = _act(state, "scouts_pass")
    # Seat 1 holds 1 Solari: neither line.
    state = _passes_with_nothing(state, 1)
    state = _pass_the_rest(state)
    assert [p.resources.solari for p in state.players][:2] == [3, 1]


# --- The expansions ride along --------------------------------------------------------

EXPANSIONS = [
    pytest.param(ORIGINAL_IMMORTALITY, id="immortality"),
    pytest.param(ORIGINAL_BLOODLINES, id="bloodlines"),
    pytest.param(
        replace(ORIGINAL, immortality=True, bloodlines=True, rise_of_ix=True),
        id="immortality-bloodlines-ix",
    ),
]


@pytest.mark.parametrize("config", EXPANSIONS)
def test_the_items_play_the_same_with_every_expansion(config: RulesetConfig) -> None:
    """Immortality, Bloodlines and Rise of Ix change which pool or missions
    play, never an item's lines (docs/rules/arrakeen-scouts.md 2, 9a): an
    event, a Treachery auction and the Water Peddlers sale resolve as they do
    on the plain original game."""

    state = _reveal(_base(config), "imperium_guild_negotiation")
    solari = state.players[0].resources.solari
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.solari == solari - 2
    assert state.players[0].influence.spacing_guild == 1
    assert _pass_the_rest(state).decision_stack[-1].kind == FrameKind.TURN

    auction = _auction(_auction_base_for(config), "treachery_mid")
    spice, intrigue = _spice(auction), _intrigue(auction)
    auction = _bid_all(auction, {0: 1, 1: 3, 2: 0, 3: 0})
    assert _spice(auction) == [spice[0], spice[1] - 3, spice[2], spice[3]]
    auction = _collect(auction, 1)
    assert _intrigue(auction)[1] == intrigue[1] + 1

    sale = _reveal_sale(_late_sale(_base(config)), "water_peddlers")
    water = sale.players[0].resources.water
    sale = _act(sale, "scouts_choose_option", option=1)
    assert sale.players[0].resources.water == water + 2
