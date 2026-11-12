"""Arrakeen Scouts on the original game: its last five events and its last sale
(stage P8c-2).

The app's original pools hold Tap into Spice Reserves, No Coming Back,
Rotating Doors (the original wording), Intriguing Gift and Desert Gift, and
the sale Fremen Mercenaries (docs/rules/arrakeen-scouts.md 9a). They use three
things the module had no cost for: a hand card chosen among starter cards, an
Intrigue card discarded rather than trashed, and a sale line per count of
water.

The rules the tests quote:

- Tap into Spice Reserves: "모두 spice 1을 얻는다(자동)" (9a); since the user's
  decision of 2026-11-01 (OQ-164 (a)) each seat takes it by its own click.
- No Coming Back: "각자 원하면 손의 시작 카드 1장을 trash한다. Seek Allies면
  원하는 진영 Influence 1, Diplomacy면 한 진영 Influence 2. 다른 시작 카드는
  보상 없이 trash할 수 있다(문장대로)" (9a); "When gaining two Influence, you
  can't choose two different Factions" [DI p. 16]. A starter card is a card of
  the ruleset's starting deck (Experimentation with Immortality, Control the
  Spice in Epic Game Mode).
- Rotating Doors and Intriguing Gift: "Intrigue 1장 버리기" (9a); Intrigue
  cards have no trash pile, so a discarded card joins the shared Intrigue
  discard, and a Twisted card in it is never reshuffled (OQ-061, OQ-097).
- Desert Gift: "시작 카드가 아닌 카드 1장 버리기 → Fremen +1" (9a).
- Fremen Mercenaries: "각자 원하는 만큼 물을 내고 물마다 troop 2를 recruit해
  곧바로 Conflict에 배치한다(supply가 모자라면 8.2절 Mercenaries처럼 OQ-074)"
  (9a); with Immortality a seat short of the supply may first return specimens
  [Immortality p. 8] (docs/rules/arrakeen-scouts.md 10, OQ-074).
- A line a seat cannot pay is not offered, and a seat with none takes nothing
  (OQ-071, 6).
"""

from dataclasses import replace

import pytest
from tests.unit.rules.test_scouts_original import (
    ENGINE,
    ORIGINAL,
    ORIGINAL_BLOODLINES,
    ORIGINAL_IMMORTALITY,
    _act,
    _late_sale,
    _offered,
    _owner,
    _pass_the_rest,
    _passes_with_nothing,
    _reveal,
    _reveal_sale,
)
from tests.unit.rules.test_scouts_original import (
    _base as _plain_base,
)
from tests.unit.rules.test_scouts_original import (
    _hand as _fields,
)

from dune_imperium import RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.content.arrakeen_scouts import EVENTS_BY_ID
from dune_imperium.content.registry.intrigue import twisted_intrigue_instance_ids
from dune_imperium.content.rulesets import content_for
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.engine import Transition
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.display.scouts import scouts_choice_lines
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue_deck import shufflable_intrigue_discard
from dune_imperium.rules.scouts_effects import starter_card_ids
from dune_imperium.simulation.sweep import run_checked_game

ORIGINAL_EPIC = replace(ORIGINAL, rise_of_ix=True, epic_game=True)
ORIGINAL_EPIC_IMMORTALITY = replace(ORIGINAL_EPIC, immortality=True)

SEEK_ALLIES = "player:0:starter:seek_allies:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
DAGGER = "player:0:starter:dagger:0"
ARGUMENT = "player:0:starter:convincing_argument:0"
DUNE = "player:0:starter:dune_the_desert_planet:0"
EXPERIMENTATION = "player:0:starter:experimentation:0"
CONTROL_THE_SPICE = "player:0:starter:control_the_spice:0"


def _intrigue(config: RulesetConfig = ORIGINAL, *, count: int = 3) -> tuple[str, ...]:
    """Some of the original game's Intrigue cards, as hand cards."""

    return content_for(config).intrigue_deck_instance_ids[:count]


def _imperium_card(config: RulesetConfig = ORIGINAL) -> str:
    """One of the original game's Imperium cards, as a hand card."""

    return content_for(config).imperium_deck_instance_ids[0]


def _spice(state: GameState) -> list[int]:
    return [player.resources.spice for player in state.players]


def _hand(**fields: object) -> dict[str, object]:
    """Seat fields; a ``hand`` is the whole of the seat's cards (so no card is
    in two zones)."""

    if "hand" in fields:
        fields = {**fields, "deck": (), "discard_pile": (), "in_play": ()}
    return _fields(**fields)


def _base(
    config: RulesetConfig = ORIGINAL,
    round_number: int = 4,
    seats: dict[str, dict[str, object]] | None = None,
) -> GameState:
    """The Scouts step of ``round_number``; an Imperium card a seat holds is
    out of the Row and the deck."""

    state = _plain_base(config, round_number, seats)
    held = {card for player in state.players for card in player.hand}
    intrigue = {card for player in state.players for card in player.intrigue_cards}
    return replace(
        state,
        imperium_row=tuple(c for c in state.imperium_row if c not in held),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in held),
        intrigue_deck=tuple(c for c in state.intrigue_deck if c not in intrigue),
    )


# --- Tap into Spice Reserves ---------------------------------------------------------


def _collect_taps(state: GameState) -> tuple[GameState, list[int]]:
    """Each seat takes its Tap into Spice Reserves spice by its own click,
    the one action of its window, in turn order (user decision 2026-11-01,
    OQ-164 (a): "둘 다 클릭으로")."""

    from dune_imperium.rules.scouts_effects import SCOUTS_COLLECT

    seats: list[int] = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT:
        seat = _owner(state)
        collect = DomainAction(action_id=SCOUTS_COLLECT, actor=seat)
        assert ENGINE.legal_actions(state, seat) == (collect,)
        before = _spice(state)
        state = ENGINE.apply(state, collect).state
        assert _spice(state)[seat] == before[seat] + 1
        seats.append(seat)
    return state, seats


def test_tap_into_spice_reserves_gives_every_seat_one_spice() -> None:
    """Every seat gains 1 spice (9a), each by its own click (OQ-164 (a))."""

    state = _base(round_number=5, seats={"2": _hand(resources=Resources(spice=0))})
    before = _spice(state)
    state = _reveal(state, "tap_into_spice_reserves")
    # Nothing is received before the clicks.
    assert _spice(state) == before
    state, seats = _collect_taps(state)
    assert seats == [0, 1, 2, 3]
    assert state.decision_stack[-1].kind == FrameKind.TURN
    assert _spice(state) == [spice + 1 for spice in before]
    gains = [
        dict(event.payload)
        for event in state.event_log
        if event.kind == "resources_gained"
        and "tap_into_spice_reserves" in str(dict(event.payload)["source"])
    ]
    assert [gain["player"] for gain in gains] == [0, 1, 2, 3]
    assert all(gain["spice"] == 1 for gain in gains)


def test_tap_into_spice_reserves_pays_in_turn_order_from_the_first_player() -> None:
    state = replace(_base(round_number=5), first_player=2)
    state = _reveal(state, "tap_into_spice_reserves")
    state, clicked = _collect_taps(state)
    assert clicked == [2, 3, 0, 1]
    seats = [
        dict(event.payload)["player"]
        for event in state.event_log
        if event.kind == "resources_gained"
        and "tap_into_spice_reserves" in str(dict(event.payload)["source"])
    ]
    assert seats == [2, 3, 0, 1]


# --- No Coming Back ------------------------------------------------------------------

_STARTER_HAND = (SEEK_ALLIES, DIPLOMACY, DAGGER, ARGUMENT, DUNE)
_STARTERS = _hand(hand=_STARTER_HAND, influence=Influence())


def _no_coming_back(config: RulesetConfig = ORIGINAL, **seat_zero: object) -> GameState:
    seats = {"0": {**_STARTERS, **seat_zero}}
    return _reveal(_base(config, round_number=4, seats=seats), "no_coming_back")


def _trash_rows(state: GameState) -> set[str]:
    return {
        str(dict(action.arguments)["card_id"])
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "scouts_trash_card"
    }


def test_no_coming_back_offers_its_three_lines_and_a_pass() -> None:
    state = _no_coming_back()
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
        ("scouts_choose_option", (("option", 2),)),
    ]
    event = EVENTS_BY_ID["no_coming_back"]
    assert event.rounds == (4, 4) and event.passable


def test_trashing_seek_allies_gives_one_influence_with_any_faction() -> None:
    state = _act(_no_coming_back(), "scouts_choose_option", option=0)
    assert _trash_rows(state) == {SEEK_ALLIES}
    state = _act(state, "scouts_trash_card", card_id=SEEK_ALLIES)
    assert SEEK_ALLIES in state.players[0].trashed
    assert SEEK_ALLIES not in state.players[0].hand
    # Any Faction is the seat's pick.
    factions = {
        dict(action.arguments)["faction"]
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "scouts_choose_faction"
    }
    assert factions == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    state = _act(state, "scouts_choose_faction", faction="fremen")
    assert state.players[0].influence == Influence(fremen=1)


def test_trashing_diplomacy_gives_two_influence_with_one_faction() -> None:
    """ "When gaining two Influence, you can't choose two different Factions"
    [DI p. 16]: one pick of a Faction takes both."""

    state = _act(_no_coming_back(), "scouts_choose_option", option=1)
    assert _trash_rows(state) == {DIPLOMACY}
    state = _act(state, "scouts_trash_card", card_id=DIPLOMACY)
    assert DIPLOMACY in state.players[0].trashed
    state = _act(state, "scouts_choose_faction", faction="bene_gesserit")
    assert state.players[0].influence == Influence(bene_gesserit=2)
    # The line is over: seat 1 is asked next.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == 1


def test_another_starter_card_is_trashed_for_nothing() -> None:
    """The line offers the other starter cards of the hand, not Seek Allies
    and Diplomacy (which have their own lines), and no card that is not a
    starter card; the trash earns nothing."""

    imperium = _imperium_card()
    state = _no_coming_back(hand=(*_STARTER_HAND, imperium))
    state = _act(state, "scouts_choose_option", option=2)
    assert _trash_rows(state) == {DAGGER, ARGUMENT, DUNE}
    before = state.players[0]
    state = _act(state, "scouts_trash_card", card_id=DAGGER)
    seat = state.players[0]
    assert DAGGER in seat.trashed and DAGGER not in seat.hand
    assert seat.influence == before.influence
    assert seat.resources == before.resources
    assert imperium in seat.hand
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == 1


def test_only_starter_cards_in_hand_are_offered() -> None:
    """A hand of Imperium cards holds no line: the seat is asked with its
    greyed lines and the pass every seat has (OQ-071, user decision
    2026-11-11)."""

    imperium = _imperium_card()
    state = _no_coming_back(hand=(imperium,))
    assert _owner(state) == 0
    assert _offered(state) == [("scouts_pass", ())]
    shown = scouts_choice_lines(state, 0, ENGINE.whole_actions(state, 0))
    assert shown is not None
    lines = shown["lines"]
    assert isinstance(lines, list) and len(lines) == 3
    assert not any(line["enabled"] for line in lines)
    assert all(
        "starter" in str(line["reason"])
        or "Seek" in str(line["reason"])
        or "Diplomacy" in str(line["reason"])
        for line in lines
    )
    state = _passes_with_nothing(state, 0)
    assert state.players[0].hand == (imperium,)


def test_a_seat_with_only_seek_allies_has_that_line_alone() -> None:
    state = _no_coming_back(hand=(SEEK_ALLIES, _imperium_card()))
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]


def test_a_seek_allies_line_needs_an_influence_track_below_the_top() -> None:
    """A line that cannot do anything is not offered (OQ-071): with every
    track at the top the Influence cannot be gained."""

    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _no_coming_back(hand=(SEEK_ALLIES, DAGGER), influence=top)
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 2),)),
    ]


def test_a_seat_may_pass_no_coming_back() -> None:
    state = _act(_no_coming_back(), "scouts_pass")
    assert state.players[0].hand == _STARTER_HAND
    assert _owner(state) == 1


@pytest.mark.parametrize(
    ("config", "starter", "not_starter"),
    [
        (ORIGINAL, DUNE, EXPERIMENTATION),
        (ORIGINAL_IMMORTALITY, EXPERIMENTATION, DUNE),
        (ORIGINAL_EPIC, CONTROL_THE_SPICE, EXPERIMENTATION),
    ],
)
def test_the_rulesets_starter_cards_are_those_of_its_starting_deck(
    config: RulesetConfig, starter: str, not_starter: str
) -> None:
    """With Immortality Experimentation replaces the Dune cards, in Epic Game
    Mode Control the Spice is among the starting cards."""

    ids = starter_card_ids(config)
    assert starter.split(":")[3] in ids
    assert not_starter.split(":")[3] not in ids
    state = _no_coming_back(config, hand=(starter, not_starter, SEEK_ALLIES))
    state = _act(state, "scouts_choose_option", option=2)
    assert _trash_rows(state) == {starter}


def test_control_the_spice_that_starts_in_the_discard_is_a_starter_card() -> None:
    """Epic Game Mode with Immortality starts Control the Spice in the discard
    pile [Immortality p. 12]; it is still one of the cards a player starts
    with, so a starter card (docs/rules/arrakeen-scouts.md 9a)."""

    ids = starter_card_ids(ORIGINAL_EPIC_IMMORTALITY)
    assert "control_the_spice" in ids and "experimentation" in ids


# --- Rotating Doors and Intriguing Gift ----------------------------------------------

CARD_A, CARD_B, CARD_C = _intrigue(count=3)


def _with_intrigue(*cards: str) -> dict[str, object]:
    return _hand(intrigue_cards=cards)


def _discarded(state: GameState) -> list[dict[str, object]]:
    return [
        dict(event.payload)
        for event in state.event_log
        if event.kind == "intrigue_card_discarded"
    ]


def test_rotating_doors_discards_an_intrigue_card_to_draw_one() -> None:
    state = _base(round_number=6, seats={"0": _with_intrigue(CARD_A)})
    state = _reveal(state, "imperium_rotating_doors")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    deck = state.intrigue_deck
    state = _act(state, "scouts_choose_option", option=0)
    offered = ENGINE.whole_actions(state, 0)
    assert [(a.action_id, dict(a.arguments)["card_id"]) for a in offered] == [
        ("scouts_discard_intrigue", CARD_A)
    ]
    state = _act(state, "scouts_discard_intrigue", card_id=CARD_A)
    seat = state.players[0]
    # The card joined the shared discard (Intrigue cards have no trash pile,
    # OQ-061), is announced as a discard, and the top of the deck replaced it.
    assert state.intrigue_discard[-1] == CARD_A
    assert _discarded(state) == [{"card_id": CARD_A, "player": 0}]
    assert not [e for e in state.event_log if e.kind == "intrigue_card_trashed"]
    assert seat.intrigue_cards == (deck[0],)
    assert state.intrigue_deck == deck[1:]


def test_a_seat_without_an_intrigue_card_cannot_take_rotating_doors() -> None:
    """Seat 1 holds a card and may take it; seat 0 holds none and is asked
    with its one row to take nothing (OQ-071)."""

    state = _base(round_number=6, seats={"1": _with_intrigue(CARD_A)})
    state = _reveal(state, "imperium_rotating_doors")
    state = _passes_with_nothing(state, 0)
    assert _owner(state) == 1
    assert ("scouts_choose_option", (("option", 0),)) in _offered(state)
    assert not _discarded(state)


def test_intriguing_gift_discards_an_intrigue_card_for_bene_gesserit() -> None:
    state = _base(seats={"0": _hand(intrigue_cards=(CARD_A, CARD_B))})
    state = _reveal(state, "intriguing_gift")
    # The first seat can pay; the three gifts of the event are one line.
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    state = _act(state, "scouts_choose_option", option=0)
    assert {a.action_id for a in ENGINE.whole_actions(state, 0)} == {
        "scouts_discard_intrigue"
    }
    state = _act(state, "scouts_discard_intrigue", card_id=CARD_B)
    seat = state.players[0]
    assert seat.influence.bene_gesserit == 1
    assert seat.intrigue_cards == (CARD_A,)
    assert state.intrigue_discard[-1] == CARD_B
    assert _discarded(state) == [{"card_id": CARD_B, "player": 0}]
    assert not [e for e in state.event_log if e.kind == "intrigue_card_trashed"]


def test_a_seat_without_an_intrigue_card_passes_intriguing_gift() -> None:
    state = _reveal(_base(), "intriguing_gift")
    state = _passes_with_nothing(state, 0)


def test_intriguing_gift_needs_bene_gesserit_below_the_top() -> None:
    """A line that could not give its Influence is not offered (OQ-071)."""

    top = _hand(
        intrigue_cards=(CARD_A,),
        influence=Influence(bene_gesserit=6),
    )
    state = _reveal(_base(seats={"0": top}), "intriguing_gift")
    state = _passes_with_nothing(state, 0)


def test_a_discarded_twisted_card_joins_the_discard_but_is_never_reshuffled() -> None:
    """Piter De Vries' Twisted cards go to the shared Intrigue discard like
    any Intrigue card, and stay in it when the discard is shuffled (OQ-097)."""

    twisted = twisted_intrigue_instance_ids()[0]
    state = _base(
        ORIGINAL_BLOODLINES,
        round_number=6,
        seats={"0": _with_intrigue(twisted, CARD_A)},
    )
    state = _reveal(state, "imperium_rotating_doors")
    state = _act(state, "scouts_choose_option", option=0)
    state = _act(state, "scouts_discard_intrigue", card_id=twisted)
    assert state.intrigue_discard[-1] == twisted
    assert twisted not in shufflable_intrigue_discard(state)
    assert twisted not in state.players[0].intrigue_cards


# --- Desert Gift ---------------------------------------------------------------------


def _discard_rows(state: GameState) -> set[str]:
    return {
        str(dict(action.arguments)["card_id"])
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "scouts_discard"
    }


def test_desert_gift_discards_a_card_that_is_not_a_starter_card() -> None:
    imperium = _imperium_card()
    state = _base(seats={"0": _hand(hand=(DAGGER, ARGUMENT, imperium))})
    state = _reveal(state, "desert_gift")
    state = _act(state, "scouts_choose_option", option=0)
    # A starter card is refused: only the Imperium card is offered.
    assert _discard_rows(state) == {imperium}
    state = _act(state, "scouts_discard", card_id=imperium)
    seat = state.players[0]
    assert imperium in seat.discard_pile and imperium not in seat.hand
    assert seat.influence.fremen == 1
    assert seat.hand == (DAGGER, ARGUMENT)


def test_desert_gift_refuses_a_seat_holding_only_starter_cards() -> None:
    state = _base(seats={"0": _hand(hand=(DAGGER, SEEK_ALLIES, DUNE))})
    state = _reveal(state, "desert_gift")
    assert _offered(state) == [("scouts_pass", ())]
    shown = scouts_choice_lines(state, 0, ENGINE.whole_actions(state, 0))
    assert shown is not None
    lines = shown["lines"]
    assert isinstance(lines, list) and len(lines) == 1
    assert not lines[0]["enabled"] and "starter" in str(lines[0]["reason"])
    state = _passes_with_nothing(state, 0)
    assert state.players[0].hand == (DAGGER, SEEK_ALLIES, DUNE)


def test_experimentation_counts_as_a_starter_card_with_immortality() -> None:
    """With Immortality the two Dune cards are Experimentation, so the
    Experimentation is refused and a (here impossible) Dune card would not
    be."""

    imperium = _imperium_card(ORIGINAL_IMMORTALITY)
    state = _base(
        ORIGINAL_IMMORTALITY,
        seats={"0": _hand(hand=(EXPERIMENTATION, imperium))},
    )
    state = _reveal(state, "desert_gift")
    state = _act(state, "scouts_choose_option", option=0)
    assert _discard_rows(state) == {imperium}


def test_desert_gift_needs_fremen_below_the_top() -> None:
    top = _hand(hand=(_imperium_card(),), influence=Influence(fremen=6))
    state = _reveal(_base(seats={"0": top}), "desert_gift")
    state = _passes_with_nothing(state, 0)


# --- Fremen Mercenaries --------------------------------------------------------------


def _water(water: int) -> dict[str, object]:
    """A seat holding ``water`` water (and some Solari and spice)."""

    return {"resources": Resources(solari=5, spice=5, water=water)}


def _sale(
    seat: dict[str, object] | None = None, config: RulesetConfig = ORIGINAL
) -> GameState:
    """The late sale Fremen Mercenaries, seat 0 as ``seat`` sets it."""

    base = _late_sale(_base(config, seats={"0": _hand(**(seat or {}))}))
    return _reveal_sale(base, "fremen_mercenaries")


def _seat_with_supply(
    config: RulesetConfig, supply: int, specimens: int = 0, water: int = 6
) -> dict[str, object]:
    """Seat 0 with ``supply`` supply troops and ``specimens`` specimens (the
    rest of its twelve in the garrison)."""

    state = _base(config)
    held = state.players[0]
    outside = held.troops_garrison + held.troops_supply
    return {
        "troops_supply": supply,
        "specimens": specimens,
        "troops_garrison": outside - supply - specimens,
        "resources": Resources(solari=5, spice=5, water=water),
    }


def test_fremen_mercenaries_offers_a_line_per_water_the_seat_holds() -> None:
    state = _sale(_water(3))
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
        ("scouts_choose_option", (("option", 2),)),
    ]
    rich = _sale(_water(12))
    assert len(_offered(rich)) == 1 + 6  # a pass and six counts of water


def test_one_water_buys_two_troops_straight_into_the_conflict() -> None:
    state = _sale()
    seat = state.players[0]
    supply, water, conflict = (
        seat.troops_supply,
        seat.resources.water,
        seat.troops_conflict,
    )
    state = _act(state, "scouts_choose_option", option=0)
    seat = state.players[0]
    assert seat.resources.water == water - 1
    assert seat.troops_supply == supply - 2
    assert seat.troops_conflict == conflict + 2
    assert seat.troops_garrison == state.players[0].troops_garrison
    deployed = [
        dict(event.payload)
        for event in state.event_log
        if event.kind == "scouts_troops_to_conflict"
    ]
    assert deployed[-1] == {"count": 2, "player": 0}


def test_several_water_buy_two_troops_each() -> None:
    state = _sale(_water(6))
    seat = state.players[0]
    supply, conflict = seat.troops_supply, seat.troops_conflict
    state = _act(state, "scouts_choose_option", option=2)  # three water
    seat = state.players[0]
    assert seat.resources.water == 3
    assert seat.troops_supply == supply - 6
    assert seat.troops_conflict == conflict + 6


def test_a_seat_without_water_passes_with_nothing_from_fremen_mercenaries() -> None:
    state = _sale(_water(0))
    state = _passes_with_nothing(state, 0)
    state = _pass_the_rest(state)
    assert state.players[0].troops_conflict == 0


def test_a_seat_may_pass_fremen_mercenaries() -> None:
    state = _act(_sale(), "scouts_pass")
    assert state.players[0].troops_conflict == 0
    assert _owner(state) == 1


def test_a_short_supply_deploys_what_it_holds() -> None:
    """Without Immortality the troops that are not there are not recruited
    (OQ-030, "해결 시점의 supply만큼")."""

    state = _sale(_seat_with_supply(ORIGINAL, 3))
    state = _act(state, "scouts_choose_option", option=1)  # two water, four troops
    seat = state.players[0]
    assert seat.resources.water == 4
    assert (seat.troops_supply, seat.troops_conflict) == (0, 3)


def test_an_empty_supply_is_not_offered_the_sale() -> None:
    """A line that recruits nothing is not offered (OQ-071)."""

    state = _sale(_seat_with_supply(ORIGINAL, 0))
    state = _passes_with_nothing(state, 0)


def test_immortality_may_return_specimens_before_the_recruit() -> None:
    """With Immortality a seat asked for more troops than its supply holds may
    first return specimens (docs/rules/arrakeen-scouts.md 10, OQ-074): four
    troops with a supply of three and two specimens asks for 0 or 1."""

    state = _sale(_seat_with_supply(ORIGINAL_IMMORTALITY, 3, 2), ORIGINAL_IMMORTALITY)
    state = _act(state, "scouts_choose_option", option=1)
    offered = ENGINE.whole_actions(state, 0)
    assert [(a.action_id, dict(a.arguments)["count"]) for a in offered] == [
        ("scouts_return_specimens", 0),
        ("scouts_return_specimens", 1),
    ]
    state = _act(state, "scouts_return_specimens", count=1)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_conflict, seat.specimens) == (0, 4, 1)
    assert seat.resources.water == 4


def test_immortality_without_a_specimen_deploys_the_supply_unasked() -> None:
    state = _sale(_seat_with_supply(ORIGINAL_IMMORTALITY, 3, 0), ORIGINAL_IMMORTALITY)
    state = _act(state, "scouts_choose_option", option=1)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_conflict) == (0, 3)
    assert _owner(state) == 1


def test_a_seat_may_decline_the_specimen_return() -> None:
    state = _sale(_seat_with_supply(ORIGINAL_IMMORTALITY, 3, 2), ORIGINAL_IMMORTALITY)
    state = _act(state, "scouts_choose_option", option=1)
    state = _act(state, "scouts_return_specimens", count=0)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_conflict, seat.specimens) == (0, 3, 2)


# --- The codec -----------------------------------------------------------------------


def _round_trips(window: GameState) -> int:
    """Every legal action of the window's owner encodes and decodes in the
    original game's codec; how many there are."""

    codec = ActionCodec(ORIGINAL)
    seat = _owner(window)
    actions = ENGINE.legal_actions(window, seat)
    for action in actions:
        assert codec.decode(codec.encode(action), seat) == action
    return len(actions)


def test_the_windows_of_the_new_items_round_trip_through_the_codec() -> None:
    """The original game's catalog holds the rows of every new window; the
    Uprising catalogs keep their rows (pinned by digest in
    ``test_arrakeen_scouts_content``)."""

    choose = _base(seats={"0": _with_intrigue(CARD_A, CARD_B)})
    discarding = _act(
        _reveal(choose, "intriguing_gift"), "scouts_choose_option", option=0
    )
    assert _round_trips(discarding) == 2  # one row per Intrigue card held
    # The sale's six lines and its pass: one row each.
    assert _round_trips(_sale(_water(12))) == 7
    assert _round_trips(_no_coming_back()) == 4
    trashing = _act(_no_coming_back(), "scouts_choose_option", option=2)
    assert _round_trips(trashing) == 3  # the three other starter cards
    discarding_a_card = _act(
        _reveal(
            _base(seats={"0": _hand(hand=(DAGGER, _imperium_card()))}), "desert_gift"
        ),
        "scouts_choose_option",
        option=0,
    )
    assert _round_trips(discarding_a_card) == 1
    returning = _act(
        _sale(_seat_with_supply(ORIGINAL_IMMORTALITY, 3, 2), ORIGINAL_IMMORTALITY),
        "scouts_choose_option",
        option=1,
    )
    codec = ActionCodec(ORIGINAL_IMMORTALITY)
    for action in ENGINE.legal_actions(returning, 0):
        assert codec.decode(codec.encode(action), 0) == action


# --- Whole games ---------------------------------------------------------------------

_NEW_ITEMS = frozenset(
    {
        "tap_into_spice_reserves",
        "no_coming_back",
        "imperium_rotating_doors",
        "intriguing_gift",
        "desert_gift",
        "fremen_mercenaries",
    }
)
# The game's seats are drawn, not seated as the other tests name them.
_DRAWN = replace(ORIGINAL, first_player_seat_zero=False)
_ALL_OPTIONS = replace(
    _DRAWN,
    rise_of_ix=True,
    immortality=True,
    bloodlines=True,
    tech_module=True,
    promo_cards=True,
)
# (name, config, game seed, policy): the plain game, Immortality, Rise of Ix,
# Bloodlines and every option at once, each with the random and the heuristic
# seats. The seeds are ones whose schedules draw the new items.
_GAMES = [
    ("plain", _DRAWN, 0, "random"),
    ("plain", _DRAWN, 2, "random"),
    ("immortality", replace(_DRAWN, immortality=True), 1, "random"),
    ("immortality", replace(_DRAWN, immortality=True), 3, "heuristic"),
    ("ix", replace(_DRAWN, rise_of_ix=True), 0, "random"),
    ("ix", replace(_DRAWN, rise_of_ix=True), 2, "random"),
    ("ix", replace(_DRAWN, rise_of_ix=True), 3, "heuristic"),
    ("bloodlines", replace(_DRAWN, bloodlines=True), 1, "random"),
    ("bloodlines", replace(_DRAWN, bloodlines=True), 0, "heuristic"),
    ("everything", _ALL_OPTIONS, 1, "random"),
    ("everything", _ALL_OPTIONS, 3, "heuristic"),
]


class _Watching(UprisingRulesEngine):
    """The engine, noting which items the schedule reveals and picks."""

    def __init__(self) -> None:
        super().__init__()
        self.revealed: set[str] = set()
        self.discarded = 0

    def apply(
        self,
        state: GameState,
        action: DomainAction | ChanceOutcome,
        *,
        legal_actions: tuple[DomainAction, ...] | None = None,
    ) -> Transition:
        result = super().apply(state, action, legal_actions=legal_actions)
        for event in result.events:
            if event.kind == "scouts_item_revealed":
                self.revealed.add(str(dict(event.payload)["item_id"]))
            self.discarded += event.kind == "intrigue_card_discarded"
        return result


def test_original_scouts_games_play_to_the_end_with_the_new_items() -> None:
    """Games on every combination of expansions, each under the sweep's checks
    (state invariants, privacy, replay and codec soundness), finish; between
    them the schedules draw every item this stage adds, and an Intrigue card
    is discarded."""

    engine = _Watching()
    for name, config, seed, policy in _GAMES:
        report = run_checked_game(
            config, seed, seed, policy=policy, soundness_interval=6, engine=engine
        )
        assert report.rounds >= 3, (name, seed, policy)
    assert _NEW_ITEMS <= engine.revealed, _NEW_ITEMS - engine.revealed
    assert engine.discarded > 0
