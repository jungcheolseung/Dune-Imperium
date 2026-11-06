"""Arrakeen Scouts events and sales that had no effect test (2026-11 audit).

docs/rules/arrakeen-scouts.md lists each Uprising-pool event and sale with
its lines (`[Scouts event: <name>]`, `[Scouts sale: <name>]`). These ids
were only named in the pool and schedule tests; their payouts were not
pinned. Each case quotes its table row.
"""

from dataclasses import dataclass

import pytest
from tests.unit.rules.test_scouts_choices import (
    _act,
    _base,
    _late,
    _offered,
    _on_turn,
    _owner,
    _reveal,
    _reveal_sale,
)

from dune_imperium.core import GameState, Influence, PlayerState
from dune_imperium.rules.frames import FrameKind

POST = "arrakis-deep-desert"
HELD = "intrigue:held"
SEAT0 = {
    "spies_supply": 2,
    "spy_post_ids": (POST,),
    "intrigue_cards": (HELD,),
}


def _answer_seat_zero(state: GameState, option: int) -> GameState:
    """Seat 0 takes ``option`` and answers its follow-ups with the first row
    offered; the other seats pass where they may."""

    assert _owner(state) == 0
    state = _act(state, "scouts_choose_option", option=option)
    while not _on_turn(state) and _owner(state) == 0:
        if state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE:
            break
        action_id, arguments = _offered(state)[0]
        state = _act(state, action_id, **dict(arguments))
    while not _on_turn(state) and state.decision_stack[-1].kind in (
        FrameKind.SCOUTS_CHOICE,
    ):
        assert _owner(state) != 0
        offered = _offered(state)
        if ("scouts_pass", ()) in offered:
            state = _act(state, "scouts_pass")
        else:
            action_id, arguments = offered[0]
            state = _act(state, action_id, **dict(arguments))
    return state


def _influence_total(player: PlayerState) -> int:
    influence = player.influence
    return (
        influence.emperor
        + influence.spacing_guild
        + influence.bene_gesserit
        + influence.fremen
    )


@dataclass(frozen=True)
class _Case:
    item_id: str
    option: int
    row: str
    solari: int = 0
    spice: int = 0
    water: int = 0
    spies_on_board: int = 0
    intrigue: int = 0
    hand: int = 0
    emperor: int = 0
    spacing_guild: int = 0
    bene_gesserit: int = 0
    fremen: int = 0
    any_influence: int = 0
    sale: bool = False


_CASES = (
    _Case(
        "market_research",
        0,
        "각자 선택: Spy 1 회수 → spice 2, 또는 패스 [Scouts event: Market Research]",
        spice=2,
        spies_on_board=-1,
    ),
    _Case(
        "smoke_and_mirrors",
        0,
        "각자 선택: Spy 1 배치, 또는 Solari 1 → Intrigue 1장"
        " [Scouts event: Smoke and Mirrors]",
        spies_on_board=1,
    ),
    _Case(
        "smoke_and_mirrors",
        1,
        "각자 선택: Spy 1 배치, 또는 Solari 1 → Intrigue 1장"
        " [Scouts event: Smoke and Mirrors]",
        solari=-1,
        intrigue=1,
    ),
    _Case(
        "guild_negotiation",
        0,
        "각자 선택: spice 1 + 손의 카드 1장 버리기 → Spacing Guild +1, 또는 패스"
        " [Scouts event: Guild Negotiation]",
        spice=-1,
        hand=-1,
        spacing_guild=1,
    ),
    _Case(
        "covert_assistance",
        0,
        "각자 선택: Spy 1 회수 → Bene Gesserit +1, 또는 패스"
        " [Scouts event: Covert Assistance]",
        spies_on_board=-1,
        bene_gesserit=1,
    ),
    _Case(
        "gift_of_water",
        0,
        "각자 선택: 물 1 → Fremen +1, 또는 패스 [Scouts event: Gift of Water]",
        water=-1,
        fremen=1,
    ),
    _Case(
        "share_intelligence",
        0,
        "각자 선택: Intrigue 1장 trash + Solari 1 → 원하는 Faction +1, 또는 패스"
        " [Scouts event: Share Intelligence]",
        solari=-1,
        intrigue=-1,
        any_influence=1,
    ),
    _Case(
        "water_for_spice_smugglers",
        0,
        "각자 선택: 물 1 잃기, 또는 Spacing Guild −1"
        " [Scouts event: Water for Spice Smugglers]",
        water=-1,
    ),
    _Case(
        "unravel_the_future",
        0,
        "spice 1 → 카드 1장 draw, 또는 spice 3 → 카드 2장 draw"
        " [Scouts sale: Unravel the Future]",
        spice=-1,
        hand=1,
        sale=True,
    ),
    _Case(
        "unravel_the_future",
        1,
        "spice 1 → 카드 1장 draw, 또는 spice 3 → 카드 2장 draw"
        " [Scouts sale: Unravel the Future]",
        spice=-3,
        hand=2,
        sale=True,
    ),
    _Case(
        "imperium_connections",
        0,
        "Solari 2 → Spy 1 배치, 또는 Solari 2 → 물 1"
        " [Scouts sale: Imperium Connections]",
        solari=-2,
        spies_on_board=1,
        sale=True,
    ),
    _Case(
        "imperium_connections",
        1,
        "Solari 2 → Spy 1 배치, 또는 Solari 2 → 물 1"
        " [Scouts sale: Imperium Connections]",
        solari=-2,
        water=1,
        sale=True,
    ),
)


@pytest.mark.parametrize(
    "case", _CASES, ids=lambda case: f"{case.item_id}-{case.option}"
)
def test_a_scouts_line_pays_its_table_row(case: _Case) -> None:
    """docs/rules/arrakeen-scouts.md: the row quoted in ``case.row``."""

    base = _base(**{"0": SEAT0})
    state = (
        _reveal_sale(_late(base), case.item_id)
        if case.sale
        else _reveal(base, case.item_id)
    )
    before = state.players[0]

    after = _answer_seat_zero(state, case.option).players[0]

    assert after.resources.solari == before.resources.solari + case.solari
    assert after.resources.spice == before.resources.spice + case.spice
    assert after.resources.water == before.resources.water + case.water
    assert len(after.spy_post_ids) == len(before.spy_post_ids) + case.spies_on_board
    assert len(after.intrigue_cards) == len(before.intrigue_cards) + case.intrigue
    assert len(after.hand) == len(before.hand) + case.hand
    if not case.any_influence:
        assert after.influence.emperor == before.influence.emperor + case.emperor
        assert (
            after.influence.spacing_guild
            == before.influence.spacing_guild + case.spacing_guild
        )
        assert (
            after.influence.bene_gesserit
            == before.influence.bene_gesserit + case.bene_gesserit
        )
        assert after.influence.fremen == before.influence.fremen + case.fremen
    assert _influence_total(after) == _influence_total(before) + (
        case.emperor
        + case.spacing_guild
        + case.bene_gesserit
        + case.fremen
        + case.any_influence
    )


def test_water_for_spice_smugglers_may_lose_guild_influence_instead() -> None:
    """docs/rules/arrakeen-scouts.md: "| `water_for_spice_smugglers` | ... | 각자
    선택: 물 1 잃기, 또는 Spacing Guild −1 |" [Scouts event: Water for Spice
    Smugglers]"""

    seat = {**SEAT0, "influence": Influence(spacing_guild=1)}
    state = _reveal(_base(**{"0": seat}), "water_for_spice_smugglers")
    assert _offered(state) == [
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
    ]
    before = state.players[0]

    after = _answer_seat_zero(state, 1).players[0]

    assert after.influence.spacing_guild == 0
    assert after.resources.water == before.resources.water


def test_a_plain_discard_never_offers_an_intrigue_card() -> None:
    """Guild Negotiation's "discard a card" takes a hand card, not Intrigue.

    docs/rules/uprising-systems.md: "별도 위치를 지정하지 않고 `discard a
    card`라고 하면 hand의 카드를 뜻한다. 일반 카드 discard 지시는 Intrigue를
    명시하지 않는 한 Intrigue card를 대상으로 하지 않는다." `[Main p. 20]`
    `[FAQ p. 2]`; arrakeen-scouts.md: "spice 1 + 손의 카드 1장 버리기 →
    Spacing Guild +1" [Scouts event: Guild Negotiation]
    """

    state = _reveal(_base(**{"0": SEAT0}), "guild_negotiation")
    state = _act(state, "scouts_choose_option", option=0)

    discards = {
        dict(arguments)["card_id"]
        for action_id, arguments in _offered(state)
        if action_id == "scouts_discard"
    }

    assert discards == set(state.players[0].hand)
    assert HELD not in discards
