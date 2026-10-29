"""Rise of Ix's four board spaces (stage P4c-4).

Rules: docs/rules/rise-of-ix.md 8 ("새 보드 칸", ``[Rise of Ix p. 12]``) and its
sections 4-6 (``[Rise of Ix pp. 4-6]``), docs/base-game-and-ix-plan.md 17.10
item 4. Setup takes ``rise_of_ix`` on the original game since stage P4c-5, but
these tests build their states by hand: the original game's round one at seat
0's first turn with its config switched to ``rise_of_ix=True`` and the Ix
stacks, dreadnoughts and tiles laid on the seats by ``dataclasses.replace``.
Each space is visited through the engine's own Agent placement and its icons
are answered as the whole actions the engine offers.
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rise_of_ix.board import IX_SPACE_IDS
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.core.observation import known_card_seats
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements, legal_agent_actions
from dune_imperium.rules.board_table import board_spaces_on_table
from dune_imperium.rules.frames import FrameKind
from dune_imperium.simulation.invariants import check_observation_privacy

LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
# Guild Bankers' Agent icons are Emperor, Spacing Guild and Landsraad; Scout's
# are City and Spice Trade. Neither card has an Agent box.
LANDSRAAD_CARD = "guild_bankers"
SPICE_TRADE_CARD = "scout"
# Costs: Detonation Devices 3, Artillery 1, Chaumurky 4 | Holtzman Engine 6,
# Invasion Ships 5, Memocorders 2 | Restricted Ordnance 4, Minimic Film 2,
# Flagship 8. The tops are Detonation Devices, Holtzman Engine and Restricted
# Ordnance.
STACKS = (
    ("detonation_devices", "artillery", "chaumurky"),
    ("holtzman_engine", "invasion_ships", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)


def _start(*, rise_of_ix: bool = True) -> GameState:
    """Round 1 of an original game at seat 0's first turn, with or without
    Rise of Ix switched on, the Ix stacks laid."""

    state = ENGINE.reset(ORIGINAL, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    state = replace(state, config=replace(state.config, rise_of_ix=rise_of_ix))
    return replace(state, tech_stacks=STACKS) if rise_of_ix else state


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _holding(card: str, **changes: Any) -> GameState:
    """Seat 0 holding ``card`` alone, two dreadnoughts in its supply and the
    Solari and spice its turn may spend."""

    resources = changes.pop("resources", Resources(solari=5, spice=3, water=2))
    return _seat(
        _start(),
        hand=(f"imperium:{card}:0",),
        resources=resources,
        dreadnoughts_supply=changes.pop("dreadnoughts_supply", 2),
        **changes,
    )


def _placements(state: GameState, space: str, card: str | None = None) -> list[Any]:
    return [
        placement
        for placement in executable_placements(state, 0, card)
        if dict(placement.arguments)["space_id"] == space
    ]


def _visit(space: str, card: str, **changes: Any) -> GameState:
    """Seat 0's Agent turn at ``space`` with its printed icons pending."""

    state = _holding(card, **changes)
    (placement,) = _placements(state, space)
    return apply_placement(ENGINE, state, placement).state


def _wholes(state: GameState) -> list[str]:
    return [whole.action_id for whole in ENGINE.whole_actions(state, 0)]


def _take(state: GameState, action_id: str, **arguments: Any) -> GameState:
    """Seat 0 answers with the whole action ``action_id``."""

    whole = DomainAction(action_id, 0, tuple(sorted(arguments.items())))
    assert whole in ENGINE.whole_actions(state, 0), (action_id, _wholes(state))
    return apply_whole(ENGINE, state, whole).state


def _kinds(state: GameState) -> list[str]:
    return [frame.kind for frame in state.decision_stack]


def _pressed(state: GameState) -> tuple[GameState, list[str]]:
    """The turn's end pressed: the state and the events it logged."""

    result = apply_whole(ENGINE, state, DomainAction("finish_agent_turn", 0))
    return result.state, [event.kind for event in result.events]


def _offered_tiles(state: GameState) -> list[str]:
    """The tiles the open Acquire Tech window offers seat 0."""

    return [
        str(dict(whole.arguments)["tech_id"])
        for whole in ENGINE.whole_actions(state, 0)
        if whole.action_id == "acquire_tech"
    ]


def _round_trips(state: GameState, seat: int = 0) -> None:
    """Every row seat ``seat`` is offered survives the codec."""

    codec = ActionCodec(state.config)
    for action in ENGINE.legal_actions(state, seat):
        assert codec.decode(codec.encode(action), action.actor) == action, action


# --- The spaces are Rise of Ix's own -----------------------------------------


def test_the_four_spaces_are_on_the_board_only_with_rise_of_ix() -> None:
    """ "새 보드 칸" (rise-of-ix.md 8, ``[Rise of Ix p. 12]``): Dreadnought, Tech
    Negotiation, Interstellar Shipping and Smuggling stand on the overlay."""

    on = {space.space_id for space in board_spaces_on_table(_start())}
    off = {space.space_id for space in board_spaces_on_table(_start(rise_of_ix=False))}
    assert set(IX_SPACE_IDS) <= on
    assert not set(IX_SPACE_IDS) & off


# --- Dreadnought --------------------------------------------------------------


def test_dreadnought_costs_three_solari_and_offers_both_icons() -> None:
    """ "Dreadnought | Landsraad | 3 Solari | dreadnought commission 그리고/또는
    Acquire Tech" (rise-of-ix.md 8, ``[Rise of Ix p. 12]``): the Agent pays 3
    Solari and both icons wait."""

    state = _visit("dreadnought", LANDSRAAD_CARD)
    assert state.players[0].resources.solari == 2
    assert _wholes(state) == [
        "commission_board_dreadnought",
        "acquire_board_tech",
        "finish_agent_turn",
    ]
    _round_trips(state)


def test_dreadnought_icons_resolve_in_either_order() -> None:
    """ "그리고/또는": the two icons are the owner's to order [Main p. 9]; the
    Acquire Tech is at Tech Discount 0 (rise-of-ix.md 8), so a 3-spice tile
    costs its 3 spice."""

    commission_first = _take(
        _visit("dreadnought", LANDSRAAD_CARD), "commission_board_dreadnought"
    )
    assert commission_first.players[0].dreadnoughts_garrison == 1
    assert commission_first.players[0].dreadnoughts_supply == 1
    assert _wholes(commission_first) == ["acquire_board_tech", "finish_agent_turn"]
    opened = _take(commission_first, "acquire_board_tech")
    assert opened.decision_stack[-1].kind == FrameKind.TECH_ACQUISITION
    assert dict(opened.decision_stack[-1].context)["discount"] == 0
    assert _offered_tiles(opened) == ["detonation_devices"]  # 3 spice, no more
    _round_trips(opened)
    bought = _take(opened, "acquire_tech", tech_id="detonation_devices")
    assert "detonation_devices" in bought.players[0].tech_ids
    assert bought.players[0].resources.spice == 0
    assert _wholes(bought) == ["finish_agent_turn"]

    tech_first = _take(_visit("dreadnought", LANDSRAAD_CARD), "acquire_board_tech")
    bought_first = _take(tech_first, "acquire_tech", tech_id="detonation_devices")
    assert _wholes(bought_first) == [
        "commission_board_dreadnought",
        "finish_agent_turn",
    ]
    both = _take(bought_first, "commission_board_dreadnought")
    assert both.players[0].dreadnoughts_garrison == 1
    assert "detonation_devices" in both.players[0].tech_ids
    assert _wholes(both) == ["finish_agent_turn"]


def test_dreadnought_acquire_tech_may_be_declined_and_is_spent() -> None:
    """The Acquire Tech icon is a "may" ([Rise of Ix p. 4]): its window offers
    the refusal, and the icon is spent either way."""

    opened = _take(_visit("dreadnought", LANDSRAAD_CARD), "acquire_board_tech")
    assert "decline_tech" in _wholes(opened)
    declined = _take(opened, "decline_tech")
    assert declined.decision_stack[-1].kind != FrameKind.TECH_ACQUISITION
    assert declined.players[0].tech_ids == ()
    assert _wholes(declined) == ["commission_board_dreadnought", "finish_agent_turn"]
    _round_trips(opened)


def test_dreadnought_space_is_usable_with_both_dreadnoughts_out() -> None:
    """ "Dreadnought 칸은 둘이 이미 있어도 갈 수 있고 그 아이콘만 불발한다"
    (rise-of-ix.md 6, ``[Rise of Ix p. 6]``): with no dreadnought in the supply
    the space is still offered and paid for, its commission icon offers no row
    and lapses at the turn's end, and the Acquire Tech still works."""

    state = _holding(LANDSRAAD_CARD, dreadnoughts_supply=0, dreadnoughts_garrison=2)
    assert _placements(state, "dreadnought")
    visited = _visit(
        "dreadnought",
        LANDSRAAD_CARD,
        dreadnoughts_supply=0,
        dreadnoughts_garrison=2,
    )
    assert visited.players[0].resources.solari == 2
    assert _wholes(visited) == ["acquire_board_tech", "finish_agent_turn"]
    _, kinds = _pressed(visited)
    assert kinds.count("board_effect_lapsed") == 2  # the commission, the tech
    after = _take(visited, "acquire_board_tech")
    assert _offered_tiles(after) == ["detonation_devices"]
    assert visited.players[0].dreadnoughts_garrison == 2


def test_dukes_landsraad_discount_reaches_the_dreadnought_space() -> None:
    """ "Duke Leto의 Landsraad 할인은 Dreadnought 칸에도 든다(3 → 2)"
    (rise-of-ix.md 8): Landsraad Popularity takes 1 Solari off a Landsraad
    space's cost, never optional."""

    paid = _visit("dreadnought", LANDSRAAD_CARD, leader_id="duke_leto_atreides")
    assert paid.players[0].resources.solari == 3  # 5 - 2
    plain = _visit("dreadnought", LANDSRAAD_CARD)
    assert plain.players[0].resources.solari == 2  # 5 - 3
    short = _holding(
        LANDSRAAD_CARD,
        leader_id="duke_leto_atreides",
        resources=Resources(solari=2),
    )
    assert _placements(short, "dreadnought")
    unpaid = _holding(LANDSRAAD_CARD, resources=Resources(solari=2))
    assert not _placements(unpaid, "dreadnought")


# --- Tech Negotiation ---------------------------------------------------------


def test_tech_negotiation_offers_the_two_halves_of_its_or_box() -> None:
    """ "고르기: Tech Discount 1로 Acquire Tech -OR- Negotiator 하나"
    (rise-of-ix.md 8, ``[Rise of Ix pp. 4, 12]``): both halves are rows of one
    icon; the Acquire Tech opens at Tech Discount 1 (a 6-spice tile costs 5)."""

    state = _visit("tech_negotiation", LANDSRAAD_CARD, resources=Resources(spice=2))
    assert state.players[0].resources.solari == 0  # no Solari cost
    assert _wholes(state) == [
        "acquire_negotiation_tech",
        "place_board_negotiator",
        "finish_agent_turn",
    ]
    _round_trips(state)
    opened = _take(state, "acquire_negotiation_tech")
    assert dict(opened.decision_stack[-1].context)["discount"] == 1
    assert _offered_tiles(opened) == ["detonation_devices"]  # 3 - 1 = 2 spice
    bought = _take(opened, "acquire_tech", tech_id="detonation_devices")
    assert bought.players[0].resources.spice == 0
    # The icon is spent by the half taken: the Negotiator no longer offered.
    assert _wholes(bought) == ["finish_agent_turn"]


def test_tech_negotiation_negotiator_half_spends_the_icon() -> None:
    """The Negotiator half: one troop from the supply to the Ix board
    (rise-of-ix.md 4), and the Acquire Tech half is gone with it."""

    state = _visit("tech_negotiation", LANDSRAAD_CARD)
    troops = state.players[0].troops_supply
    placed = _take(state, "place_board_negotiator")
    owner = placed.players[0]
    assert (owner.negotiators, owner.troops_supply) == (1, troops - 1)
    assert _wholes(placed) == ["finish_agent_turn"]
    _round_trips(placed)


def test_tech_negotiation_halves_that_cannot_work_offer_no_row() -> None:
    """Each half is a "may" that offers no row it cannot use (OQ-095 (2)): with
    no spice for any tile and no troop in the supply the icon only lapses."""

    state = _visit(
        "tech_negotiation",
        LANDSRAAD_CARD,
        resources=Resources(spice=0),
        troops_supply=0,
        troops_garrison=_start().players[0].troops_garrison
        + _start().players[0].troops_supply,
    )
    assert _wholes(state) == ["finish_agent_turn"]
    _, kinds = _pressed(state)
    assert kinds.count("board_effect_lapsed") == 1


def _reveal_persuasion(state: GameState) -> object:
    revealed = apply_whole(ENGINE, state, DomainAction("reveal_turn", 0)).state
    return dict(revealed.decision_stack[-1].context)["persuasion"]


def test_tech_negotiation_gives_persuasion_only_while_the_agent_is_there() -> None:
    """ "여기 Agent가 있으면 자기 Reveal turn에 Persuasion 1" (rise-of-ix.md 8,
    ``[Rise of Ix pp. 4, 12]``): an Arrakis Recruiter's 1 Persuasion becomes 2
    with an Agent on the space, and 1 again once it is recalled."""

    base = _seat(_start(), hand=("imperium:arrakis_recruiter:0",))
    assert _reveal_persuasion(base) == 1
    there = _seat(base, agent_locations=("tech_negotiation",), agents_available=1)
    assert _reveal_persuasion(there) == 2
    elsewhere = _seat(base, agent_locations=("smuggling",), agents_available=1)
    assert _reveal_persuasion(elsewhere) == 1


# --- Interstellar Shipping ----------------------------------------------------


def _guild(influence: int) -> dict[str, Any]:
    owner = _start().players[0]
    return {"influence": replace(owner.influence, spacing_guild=influence)}


def test_interstellar_shipping_needs_spacing_guild_influence_two() -> None:
    """ "Interstellar Shipping | Spice Trade | Spacing Guild Influence 2 이상"
    (rise-of-ix.md 8, ``[Rise of Ix pp. 5, 12]``): refused with 1, offered
    with 2."""

    assert not _placements(
        _holding(SPICE_TRADE_CARD, **_guild(1)), "interstellar_shipping"
    )
    assert _placements(_holding(SPICE_TRADE_CARD, **_guild(2)), "interstellar_shipping")
    # Another Spice Trade space has no such requirement.
    assert _placements(_holding(SPICE_TRADE_CARD, **_guild(0)), "smuggling")


def test_kwisatz_haderach_cannot_pass_the_influence_requirement() -> None:
    """ "Kwisatz Haderach는 Interstellar Shipping의 Influence 요구를 넘지
    못한다(디자이너 판정)" (rise-of-ix.md 8): his Agent goes to any space, even
    an occupied one, but "the Influence requirements still stop it"
    (imperium-base.md 13.1, ``[DI p. 13]``)."""

    def kwisatz_at(influence: int) -> set[str]:
        state = _holding("kwisatz_haderach", **_guild(influence))
        return {
            str(dict(action.arguments)["space_id"])
            for action in legal_agent_actions(state, 0)
        }

    low = kwisatz_at(1)
    assert "smuggling" in low and "dreadnought" in low  # any space ...
    assert "interstellar_shipping" not in low  # ... but the requirement
    assert "interstellar_shipping" in kwisatz_at(2)


def test_interstellar_shipping_has_two_freighter_icons() -> None:
    """ "Freighter 두 번" (rise-of-ix.md 8): two icons, each its own move; from
    the bottom only a move up is offered, and with both used the visit is done."""

    state = _visit("interstellar_shipping", SPICE_TRADE_CARD, **_guild(2))
    assert state.players[0].resources.solari == 5  # no cost
    assert _wholes(state) == ["advance_board_freighter", "finish_agent_turn"]
    once = _take(state, "advance_board_freighter")
    assert once.players[0].freighter_space == 1
    assert _wholes(once) == [
        "advance_board_freighter",
        "recall_board_freighter",
        "finish_agent_turn",
    ]
    _round_trips(once)
    twice = _take(once, "advance_board_freighter")
    assert twice.players[0].freighter_space == 2
    assert _wholes(twice) == ["finish_agent_turn"]


def test_interstellar_shipping_second_icon_may_recall_the_first_move() -> None:
    """One icon up and the other a recall: the recall owes the rewards of the
    space it left (space 1: Dividends or spice 2, ``[Rise of Ix p. 5]``)."""

    state = _visit("interstellar_shipping", SPICE_TRADE_CARD, **_guild(2))
    recalled = _take(_take(state, "advance_board_freighter"), "recall_board_freighter")
    assert recalled.players[0].freighter_space == 0
    owed = [whole for whole in ENGINE.whole_actions(recalled, 0)]
    assert {
        dict(whole.arguments)["effect"]
        for whole in owed
        if whole.action_id == "resolve_shipping_reward"
    } == {"dividends", "spice"}
    paid = _take(recalled, "resolve_shipping_reward", effect="spice")
    assert paid.players[0].resources.spice == 3 + 2
    assert _wholes(paid) == ["finish_agent_turn"]


def test_interstellar_shipping_recalls_first_from_a_high_freighter() -> None:
    """A Freighter already on space 2 recalls with the first icon and moves up
    with the second."""

    state = _visit(
        "interstellar_shipping", SPICE_TRADE_CARD, freighter_space=2, **_guild(2)
    )
    assert _wholes(state) == [
        "advance_board_freighter",
        "recall_board_freighter",
        "finish_agent_turn",
    ]
    recalled = _take(state, "recall_board_freighter")
    assert recalled.players[0].freighter_space == 0
    # Spaces 1 and 2 owe their rewards, which wait on the turn.
    assert _wholes(recalled).count("resolve_shipping_reward") > 0
    moved = _take(recalled, "advance_board_freighter")
    assert moved.players[0].freighter_space == 1


# --- Smuggling ----------------------------------------------------------------


def test_smuggling_gives_a_solari_and_a_freighter_icon_in_either_order() -> None:
    """ "Smuggling | Spice Trade | 1 Solari, Freighter 한 번" (rise-of-ix.md 8,
    ``[Rise of Ix p. 12]``): the two icons are the owner's to order
    [Main p. 9]."""

    state = _visit("smuggling", SPICE_TRADE_CARD)
    # The Solari is automatic, so it holds the turn's end back.
    assert _wholes(state) == ["resolve_board_effect", "advance_board_freighter"]
    _round_trips(state)
    solari_first = _take(state, "resolve_board_effect", effect="resources")
    assert solari_first.players[0].resources.solari == 6
    assert _wholes(solari_first) == ["advance_board_freighter", "finish_agent_turn"]
    done = _take(solari_first, "advance_board_freighter")
    assert done.players[0].freighter_space == 1

    freighter_first = _take(state, "advance_board_freighter")
    assert _wholes(freighter_first) == ["resolve_board_effect"]
    both = _take(freighter_first, "resolve_board_effect", effect="resources")
    assert both.players[0].resources.solari == 6
    assert both.players[0].freighter_space == 1


def test_smuggling_freighter_icon_lapses_unused() -> None:
    """The Freighter icon is a "may" ([Rise of Ix p. 5]); pressing the turn's
    end with it unused lapses it (OQ-095 (2))."""

    state = _take(
        _visit("smuggling", SPICE_TRADE_CARD),
        "resolve_board_effect",
        effect="resources",
    )
    _, kinds = _pressed(state)
    assert kinds.count("board_effect_lapsed") == 1


# --- Spaceport and the Foldspace space ----------------------------------------


def _foldspace_visit(**changes: Any) -> GameState:
    return _visit("foldspace", LANDSRAAD_CARD, **changes)


def test_spaceport_puts_the_foldspace_card_on_top_of_the_deck_publicly() -> None:
    """ "Spaceport: 얻는 카드를 덱 위에 놓을 수 있다" (rise-of-ix.md 4,
    ``[Rise of Ix p. 4]``): the Foldspace card the Foldspace space acquires may
    go on top of its owner's deck, and a card there is known to every seat until
    it is drawn (OQ-145)."""

    state = _foldspace_visit(tech_ids=("spaceport",))
    assert _wholes(state).count("resolve_board_effect") == 1
    assert "acquire_foldspace_to_deck_top" in _wholes(state)
    _round_trips(state)
    before = state.players[0]
    stack = dict(state.reserve_stacks)["foldspace_card"]
    taken = _take(state, "acquire_foldspace_to_deck_top")
    owner = taken.players[0]
    card = owner.deck[0]
    assert card.startswith("reserve:foldspace_card:")
    assert owner.deck_public_top == (card,)
    assert owner.discard_pile == before.discard_pile
    assert dict(taken.reserve_stacks)["foldspace_card"] == stack - 1
    assert card not in known_card_seats(taken)  # public: every seat knows it
    check_observation_privacy(taken)
    assert "acquire_foldspace_to_deck_top" not in _wholes(taken)
    assert "resolve_board_effect" not in _wholes(taken)  # the icon is spent


def test_spaceport_leaves_the_plain_foldspace_row_in_the_discard_pile() -> None:
    """The deck top is a choice ("놓을 수 있다"): the plain row still puts the
    Foldspace card in the discard pile."""

    state = _foldspace_visit(tech_ids=("spaceport",))
    plain = _take(state, "resolve_board_effect", effect="foldspace")
    owner = plain.players[0]
    assert owner.discard_pile[-1].startswith("reserve:foldspace_card:")
    assert owner.deck_public_top == ()
    assert "acquire_foldspace_to_deck_top" not in _wholes(plain)


def test_foldspace_deck_top_row_needs_spaceport_rise_of_ix_and_a_card() -> None:
    """Without the tile, without Rise of Ix, or with the Foldspace stack empty
    there is no deck-top row."""

    assert "acquire_foldspace_to_deck_top" not in _wholes(_foldspace_visit())
    empty = replace(
        _foldspace_visit(tech_ids=("spaceport",)),
        reserve_stacks=tuple(
            (card, 0 if card == "foldspace_card" else count)
            for card, count in _foldspace_visit().reserve_stacks
        ),
    )
    assert "acquire_foldspace_to_deck_top" not in _wholes(empty)


# --- The codec ----------------------------------------------------------------


def test_the_rows_are_in_the_catalog_only_with_rise_of_ix() -> None:
    """Only an original + Rise of Ix catalog holds the rows of the four spaces'
    icons, the Foldspace deck-top option and the Acquire Tech refusal their
    two Landsraad spaces print."""

    def rows(config: RulesetConfig) -> set[tuple[object, object]]:
        return {
            (dict(t.arguments).get("icon"), dict(t.arguments).get("option"))
            for t in ActionCodec(config).catalog
        }

    def refusals(config: RulesetConfig) -> set[object]:
        return {
            dict(t.arguments).get("printed")
            for t in ActionCodec(config).catalog
            if t.action_id == "decline"
            and dict(t.arguments).get("source") == "board_space"
        }

    ix_config = replace(ORIGINAL, rise_of_ix=True)
    plain, ix = rows(ORIGINAL), rows(ix_config)
    icons = {"commission", "ix_tech", "tech_negotiation", "freighter"}
    assert not icons & {icon for icon, _ in plain}
    assert icons <= {icon for icon, _ in ix}
    assert ("foldspace", "deck_top") in ix and ("foldspace", "deck_top") not in plain
    assert {("tech_negotiation", "tech"), ("tech_negotiation", "negotiator")} <= ix
    printers = {"dreadnought", "tech_negotiation"}
    assert printers <= refusals(ix_config)
    assert not printers & refusals(ORIGINAL)


def test_each_row_names_only_the_space_that_prints_it() -> None:
    """A row of the four spaces' icons, and the Foldspace deck-top option, is
    named by the space or spaces that print it and no other."""

    printers: dict[tuple[object, object], set[object]] = {}
    for t in ActionCodec(replace(ORIGINAL, rise_of_ix=True)).catalog:
        arguments = dict(t.arguments)
        if arguments.get("source") != "board_space":
            continue
        key = (arguments.get("icon"), arguments.get("option"))
        printers.setdefault(key, set()).add(arguments.get("printed"))
    assert printers[("commission", None)] == {"dreadnought"}
    assert printers[("ix_tech", None)] == {"dreadnought"}
    assert printers[("tech_negotiation", "tech")] == {"tech_negotiation"}
    assert printers[("tech_negotiation", "negotiator")] == {"tech_negotiation"}
    assert printers[("freighter", None)] == {"interstellar_shipping", "smuggling"}
    assert printers[("foldspace", "deck_top")] == {"foldspace"}


@pytest.mark.parametrize(
    ("space", "card", "changes"),
    [
        ("dreadnought", LANDSRAAD_CARD, {}),
        ("tech_negotiation", LANDSRAAD_CARD, {}),
        ("interstellar_shipping", SPICE_TRADE_CARD, _guild(2)),
        ("smuggling", SPICE_TRADE_CARD, {}),
        ("foldspace", LANDSRAAD_CARD, {"tech_ids": ("spaceport",)}),
    ],
)
def test_every_offered_row_round_trips_through_the_codec(
    space: str, card: str, changes: dict[str, Any]
) -> None:
    """Every row of the visit and of the windows it opens is in the codec."""

    state = _visit(space, card, **changes)
    _round_trips(state)
    for action in ENGINE.whole_actions(state, 0):
        if action.action_id in ("acquire_board_tech", "acquire_negotiation_tech"):
            _round_trips(_take(state, action.action_id))
        if action.action_id == "recall_board_freighter":
            _round_trips(_take(state, action.action_id))
