"""Rise of Ix Imperium batch D: Satellite Ban, Spice Trader and Imperial Bashar.

Steam app attribute table, per-card UI pieces and English localization
(4.1.2.1808, dad97e20); rules: rise-of-ix.md 7 ("Discard 아이콘. 손의 카드
하나(Intrigue 아님)를 discard pile로. 대개 비용이고, 내지 않으면 효과도 없다."
[Rise of Ix p. 7]), imperium-base.md 2 ("Conflict에 troop이 하나도 없으면 0"
[DI p. 11]), player-turns.md [Main p. 9] [FAQ p. 3]. Every offered row
round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.agent_abilities import AGENT_BOX_ABILITIES
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    Resources,
)
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_box_abilities import either_trash_block
from dune_imperium.rules.agent_effects import agent_card_cost_block
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.effects import OptionalBlockKind, OptionalEffectBlock

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
_BOX = PersonalCardAgentEffect
_REVEAL = PersonalCardRevealChoiceEffect


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_whole."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _start() -> tuple[_Engine, GameState]:
    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _clean(state: GameState, named: set[str]) -> GameState:
    """``state`` without the named cards in any seat's zones, the Imperium deck
    and Row (seeded decks may hold the card a test then puts in a hand)."""

    return replace(
        state,
        players=tuple(
            replace(
                player,
                deck=tuple(c for c in player.deck if c not in named),
                hand=tuple(c for c in player.hand if c not in named),
                discard_pile=tuple(c for c in player.discard_pile if c not in named),
                in_play=tuple(c for c in player.in_play if c not in named),
            )
            for player in state.players
        ),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    hand = changes.get("hand")
    if isinstance(hand, tuple):
        named = {card for card in hand if card not in state.players[seat].hand}
        state = _clean(state, named)
    players = list(state.players)
    owner = players[seat]
    if "agent_locations" in changes:
        locations = changes["agent_locations"]
        assert isinstance(locations, tuple)
        changes["agents_available"] = 2 - len(locations)
    if "troops_conflict" in changes or "troops_garrison" in changes:
        # The supply makes up the 12 troops a seat always accounts for.
        garrison = changes.get("troops_garrison", owner.troops_garrison)
        conflict = changes.get("troops_conflict", owner.troops_conflict)
        assert isinstance(garrison, int) and isinstance(conflict, int)
        changes["troops_supply"] = (
            12
            - garrison
            - conflict
            - owner.memories
            - owner.specimens
            - owner.troops_parked
            - owner.negotiators
        )
    if "dreadnoughts_conflict" in changes:
        # The two dreadnoughts a seat always accounts for.
        conflict = changes["dreadnoughts_conflict"]
        assert isinstance(conflict, int)
        changes["dreadnoughts_supply"] = 2 - conflict - owner.dreadnoughts_garrison
    players[seat] = replace(owner, **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _rows(engine: _Engine, state: GameState) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, 0)
    return engine.whole_actions(state, 0)


def _ids(engine: _Engine, state: GameState) -> list[str]:
    return [row.action_id for row in _rows(engine, state)]


def _counts(engine: _Engine, state: GameState, action_id: str) -> set[object]:
    return {
        dict(row.arguments).get("count")
        for row in _rows(engine, state)
        if row.action_id == action_id
    }


def _do(engine: _Engine, state: GameState, action_id: str, **args: object) -> GameState:
    row = next(
        row
        for row in _rows(engine, state)
        if row.action_id == action_id
        and all(dict(row.arguments).get(key) == value for key, value in args.items())
    )
    result = apply_whole(engine, state, row).state
    engine.legal_actions(result, 0)
    return result


def _send(engine: _Engine, state: GameState, card_id: str, space_id: str) -> GameState:
    """``card_id`` (already in hand) sent to ``space_id``, its box pending."""

    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == card_id
        and dict(row.arguments)["space_id"] == space_id
    )
    result = apply_placement(engine, state, placement).state
    engine.legal_actions(result, 0)
    return result


def _finish(engine: _Engine, state: GameState) -> GameState:
    """The Agent turn closed with every board effect settled and no arrow
    paid (an unpaid optional arrow lapses at the turn's end, OQ-095 (2))."""

    while True:
        ids = _ids(engine, state)
        step = next(
            (
                action_id
                for action_id in ("resolve_board_effect", "resolve_faction_influence")
                if action_id in ids
            ),
            None,
        )
        if step is None:
            return _do(engine, state, "finish_agent_turn")
        state = _do(engine, state, step)


# --- Satellite Ban --------------------------------------------------------------

SATELLITE_BAN = "imperium:satellite_ban:0"
_DISCARD_BAN = _BOX.MAY_DISCARD_FOR_ONE_SPICE_AND_ONE_WATER


def _ban(engine: _Engine, state: GameState, hand: tuple[str, ...]) -> GameState:
    """Satellite Ban sent to Stillsuits (its Fremen icon) with ``hand`` besides
    it, its box pending."""

    state = _seat(state, hand=(SATELLITE_BAN, *hand))
    return _send(engine, state, SATELLITE_BAN, "stillsuits")


def _discards(engine: _Engine, state: GameState) -> set[str]:
    return {
        str(dict(row.arguments)["card_id"])
        for row in _rows(engine, state)
        if row.action_id == "discard_agent_card"
    }


def test_satellite_ban_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "[Discard] -> [1 spice] [1 water]" / "Retreat up to two of your troops."

    App table: cost 5, one copy, Spacing Guild and Fremen with their two Agent
    icons, Reveal 1 Persuasion and no fixed swords.
    """
    entry = IMPERIUM_CARDS_BY_ID["satellite_ban"]
    assert (entry.copies, entry.acquisition_cost) == (1, 5)
    assert entry.factions == (Faction.SPACING_GUILD, Faction.FREMEN)
    assert entry.agent_icons == (AgentIcon.SPACING_GUILD, AgentIcon.FREMEN)
    assert entry.infiltration_icons == ()
    assert entry.agent_effect is _DISCARD_BAN
    assert entry.reveal_choice_effects == (_REVEAL.MAY_RETREAT_UP_TO_TWO_TROOPS,)
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert SATELLITE_BAN in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert SATELLITE_BAN not in content_for(config).imperium_deck_instance_ids


def test_satellite_ban_card_text_prints_the_arrow_and_the_retreat() -> None:
    """ "[Discard] -> [1 spice] [1 water]" and "Retreat up to two of your
    troops." [Steam app screen pieces and text]."""
    entry = IMPERIUM_CARDS_BY_ID["satellite_ban"]
    assert personal_card_text(entry) == [
        "Agent: You may discard a card → Gain 1 spice, Gain 1 water",
        "Reveal: You may retreat up to 2 troops",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 카드 1장 {discard} 가능 {arrow_right} {spice:1}, {water:1}",
        "공개 칸: {troop:2}까지 {retreat} 가능",
    ]


def test_satellite_ban_goes_to_its_two_icons_only() -> None:
    """The Spacing Guild and Fremen Agent icons (app attribute table)."""
    engine, state = _start()
    state = _seat(state, hand=(SATELLITE_BAN,))
    spaces = {
        str(dict(row.arguments)["space_id"])
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == SATELLITE_BAN
    }
    assert {"stillsuits", "foldspace"} <= spaces
    assert not spaces & {"arrakeen", "wealth", "secrets", "hall_of_oratory"}


def test_satellite_ban_discards_a_chosen_card_for_spice_and_water() -> None:
    """ "[Discard] -> [1 spice] [1 water]": one hand card is the cost
    ("손의 카드 하나(Intrigue 아님)를 discard pile로" [Rise of Ix p. 7]); both
    gains come at once (log text: "Discarded ... to gain [spice] and
    [water]")."""
    engine, state = _start()
    paid, kept = state.players[0].hand[:2]
    placed = _ban(engine, state, (paid, kept))
    assert _discards(engine, placed) == {paid, kept}
    before = placed.players[0]
    paid_state = _do(engine, placed, "discard_agent_card", card_id=paid)
    after = paid_state.players[0]
    assert after.resources.spice == before.resources.spice + 1
    assert after.resources.water == before.resources.water + 1
    assert after.hand == (kept,)
    assert after.discard_pile[-1] == paid
    assert SATELLITE_BAN in after.in_play
    assert "discard_agent_card" not in _ids(engine, paid_state)


def test_satellite_ban_pays_once_per_turn() -> None:
    """ "하나의 화살표 비용과 효과는 한 턴에 한 번만" (player-turns.md [Main p. 9]
    [FAQ p. 3]): the arrow is gone after it is paid."""
    engine, state = _start()
    paid, kept, third = state.players[0].hand[:3]
    placed = _ban(engine, state, (paid, kept, third))
    after = _do(engine, placed, "discard_agent_card", card_id=paid)
    assert not _discards(engine, after)
    assert after.players[0].hand == (kept, third)


def test_satellite_ban_can_leave_the_arrow_unpaid() -> None:
    """ "비용을 지불하지 않으면 효과를 얻지 못하며" (player-turns.md [Main p. 9]
    [FAQ p. 3]): the arrow is optional and offers no refusal row (OQ-095 (2));
    ending the turn without paying keeps the hand and gives nothing."""
    engine, state = _start()
    paid, kept = state.players[0].hand[:2]
    placed = _ban(engine, state, (paid, kept))
    assert "decline_agent_card_discard" not in _ids(engine, placed)
    owner = _finish(engine, placed).players[0]
    assert {paid, kept} <= set(owner.hand)
    assert paid not in owner.discard_pile and kept not in owner.discard_pile
    # Only the space's own gain, as with no card to pay.
    bare = _finish(engine, _ban(engine, state, ())).players[0]
    assert owner.resources == bare.resources
    assert paid not in owner.discard_pile and kept not in owner.discard_pile


def test_satellite_ban_offers_no_discard_with_an_empty_hand() -> None:
    """ "내지 않으면 효과도 없다" [Rise of Ix p. 7]: the played Satellite Ban
    cannot pay itself, so with no other hand card nothing can be paid and the
    block says a card in hand is needed."""
    engine, state = _start()
    placed = _ban(engine, state, ())
    assert placed.players[0].hand == ()
    assert not _discards(engine, placed)
    assert agent_card_cost_block(placed, 0) == OptionalEffectBlock(
        OptionalBlockKind.HAND, 1, 0
    )


def test_satellite_ban_discarding_an_unload_card_settles_its_box_first() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한
    뒤 오른쪽으로 간다" (rise-of-ix.md 7): CHOAM Delegate's "[Unload] [3
    Solari]" is paid, then the spice and water."""
    engine, state = _start()
    delegate = "imperium:choam_delegate:0"
    state = _seat(state, resources=Resources())
    placed = _ban(engine, state, (delegate,))
    after = _do(engine, placed, "discard_agent_card", card_id=delegate).players[0]
    assert (after.resources.solari, after.resources.spice, after.resources.water) == (
        3,
        1,
        placed.players[0].resources.water + 1,
    )


def test_satellite_ban_reveals_one_persuasion() -> None:
    """App table: Reveal 1 Persuasion; its arrow is Agent-box only."""
    engine, state = _start()
    state = _seat(state, hand=(SATELLITE_BAN,), troops_conflict=0)
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == 0
    assert "discard_agent_card" not in _ids(engine, revealed)


def test_satellite_ban_retreats_up_to_two_troops_to_the_garrison() -> None:
    """ "Retreat up to two of your troops." (Scout's sentence): the troops go
    from the Conflict to the garrison [DI p. 16], and a player left without
    a unit has no strength ("Conflict에 troop이 하나도 없으면 0" [DI p. 11])."""
    engine, state = _start()
    state = _seat(state, hand=(SATELLITE_BAN,), troops_garrison=0, troops_conflict=3)
    revealed = _do(engine, state, "reveal_turn")
    assert revealed.players[0].combat_strength == 6
    assert _counts(engine, revealed, "retreat_reveal_card_troops") == {1, 2}
    retreated = _do(engine, revealed, "retreat_reveal_card_troops", count=2)
    after = retreated.players[0]
    assert (after.troops_garrison, after.troops_conflict) == (2, 1)
    assert after.combat_strength == 2
    assert "retreat_reveal_card_troops" not in _ids(engine, retreated)


def test_satellite_ban_may_retreat_none_and_only_offers_what_it_can() -> None:
    """ "Up to" allows none ([FAQ p. 3], Scout's record): no refusal row, the
    troops stay, and one troop in the Conflict offers only a count of one."""
    engine, state = _start()
    three = _seat(state, hand=(SATELLITE_BAN,), troops_garrison=0, troops_conflict=3)
    revealed = _do(engine, three, "reveal_turn")
    assert not {a for a in _ids(engine, revealed) if a.startswith("decline_")}
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].troops_conflict == 3
    one = _seat(state, hand=(SATELLITE_BAN,), troops_garrison=2, troops_conflict=1)
    assert _counts(
        engine, _do(engine, one, "reveal_turn"), "retreat_reveal_card_troops"
    ) == {1}
    none = _seat(state, hand=(SATELLITE_BAN,), troops_garrison=3, troops_conflict=0)
    assert not _counts(
        engine, _do(engine, none, "reveal_turn"), "retreat_reveal_card_troops"
    )


def test_satellite_ban_retreats_troops_and_not_dreadnoughts() -> None:
    """ "원판 카드의 'troop'은 유닛을 뜻하지 않아 dreadnought에 작용하지 않는다"
    (rise-of-ix.md 6, [Rise of Ix p. 6]): with one troop and one dreadnought in
    the Conflict only a single troop can retreat, and the dreadnought stays."""
    engine, state = _start()
    state = _seat(
        state,
        hand=(SATELLITE_BAN,),
        troops_garrison=0,
        troops_conflict=1,
        dreadnoughts_conflict=1,
    )
    revealed = _do(engine, state, "reveal_turn")
    assert _counts(engine, revealed, "retreat_reveal_card_troops") == {1}
    after = _do(engine, revealed, "retreat_reveal_card_troops", count=1).players[0]
    assert (after.troops_conflict, after.dreadnoughts_conflict) == (0, 1)
    assert after.troops_garrison == 1


# --- Spice Trader ---------------------------------------------------------------

SPICE_TRADER = "imperium:spice_trader:0"
_DISCARD_TRADER = _BOX.MAY_DISCARD_FOR_TWO_SPICE_IF_FREMEN_INFLUENCE_TWO


def _trader(
    engine: _Engine,
    state: GameState,
    hand: tuple[str, ...],
    space: str = "arrakeen",
    **changes: object,
) -> GameState:
    """Spice Trader sent to ``space`` (Arrakeen, its City icon) with ``hand``
    besides it, its box pending."""

    state = _seat(state, 0, hand=(SPICE_TRADER, *hand), **changes)
    return _send(engine, state, SPICE_TRADER, space)


def test_spice_trader_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "[Fremen] 2 Influence: [Discard] -> [2 spice]".

    App table: cost 4, one copy, Fremen, the City and Spice Trade icons,
    Reveal 2 Persuasion and 1 sword.
    """
    entry = IMPERIUM_CARDS_BY_ID["spice_trader"]
    assert (entry.copies, entry.acquisition_cost) == (1, 4)
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.infiltration_icons == ()
    assert entry.agent_effect is _DISCARD_TRADER
    assert entry.reveal_choice_effects == ()
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 1)
    assert entry.play_data_complete
    assert SPICE_TRADER in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert SPICE_TRADER not in content_for(config).imperium_deck_instance_ids


def test_spice_trader_card_text_prints_the_influence_and_the_arrow() -> None:
    """ "[Fremen] 2 Influence : [Discard] -> [2 spice]" [Steam app screen
    pieces and text]."""
    entry = IMPERIUM_CARDS_BY_ID["spice_trader"]
    assert personal_card_text(entry) == [
        "Agent: If you have 2 or more Fremen Influence: "
        "You may discard a card → Gain 2 spice"
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {influence_fremen} 2 이상이면: "
        "카드 1장 {discard} 가능 {arrow_right} {spice:2}"
    ]


def test_spice_trader_goes_to_its_two_icons_only() -> None:
    """The City and Spice Trade Agent icons (app attribute table)."""
    engine, state = _start()
    state = _seat(state, hand=(SPICE_TRADER,))
    spaces = {
        str(dict(row.arguments)["space_id"])
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == SPICE_TRADER
    }
    assert {"arrakeen", "carthag", "imperial_basin", "smuggling"} <= spaces
    assert not spaces & {"wealth", "stillsuits", "foldspace", "hall_of_oratory"}


def test_spice_trader_discards_a_chosen_card_for_two_spice() -> None:
    """ "[Fremen] 2 Influence: [Discard] -> [2 spice]": with 2 Fremen
    Influence one hand card is the cost ("손의 카드 하나(Intrigue 아님)를
    discard pile로" [Rise of Ix p. 7]) and 2 spice come at once."""
    engine, state = _start()
    paid, kept = state.players[0].hand[:2]
    placed = _trader(engine, state, (paid, kept), influence=Influence(fremen=2))
    assert _discards(engine, placed) == {paid, kept}
    before = placed.players[0]
    after = _do(engine, placed, "discard_agent_card", card_id=paid).players[0]
    assert after.resources.spice == before.resources.spice + 2
    assert after.resources.water == before.resources.water
    assert after.hand == (kept,)
    assert after.discard_pile[-1] == paid
    assert SPICE_TRADER in after.in_play


@pytest.mark.parametrize(
    "influence",
    [
        Influence(),
        Influence(fremen=1),
        # Another Faction's Influence is no Fremen Influence.
        Influence(emperor=4, spacing_guild=3, bene_gesserit=2, fremen=1),
    ],
)
def test_spice_trader_needs_two_fremen_influence(influence: Influence) -> None:
    """ "[Fremen] 2 Influence:" is a threshold on the Fremen track: below it
    no card can pay, and the block names the Influence it needs."""
    engine, state = _start()
    paid, kept = state.players[0].hand[:2]
    placed = _trader(engine, state, (paid, kept), influence=influence)
    assert not _discards(engine, placed)
    assert agent_card_cost_block(placed, 0) == OptionalEffectBlock(
        OptionalBlockKind.INFLUENCE,
        needed=2,
        held=influence.fremen,
        faction="fremen",
    )
    owner = _finish(engine, placed).players[0]
    assert {paid, kept} <= set(owner.hand)
    assert paid not in owner.discard_pile and kept not in owner.discard_pile


@pytest.mark.parametrize("influence", [Influence(fremen=2), Influence(fremen=3)])
def test_spice_trader_wants_the_influence_and_not_the_alliance(
    influence: Influence,
) -> None:
    """The Faction icon with "2 Influence :" (the words High Priority Travel
    prints for its Spacing Guild threshold) is a count of Influence; the
    Alliance token (4 Influence and the most) is not asked."""
    engine, state = _start()
    paid = state.players[0].hand[0]
    placed = _trader(engine, state, (paid,), influence=influence)
    assert placed.players[0].alliance_faction_ids == ()
    assert _discards(engine, placed) == {paid}
    assert agent_card_cost_block(placed, 0) is None


def test_spice_trader_judges_the_influence_when_the_cost_is_paid() -> None:
    """OQ-028 (a): "Influence 문턱 ... 은 box를 pending으로 두고 해결 시점에
    판정한다. 화살표 지불은 비용이 성립할 때까지" nothing is offered: placed
    with 1 Fremen Influence the arrow offers no card, and once the owner
    reaches 2 later in the same turn it does."""
    engine, state = _start()
    paid, kept = state.players[0].hand[:2]
    placed = _trader(engine, state, (paid, kept), influence=Influence(fremen=1))
    assert not _discards(engine, placed)
    owner = placed.players[0]
    risen = replace(
        placed,
        players=(replace(owner, influence=Influence(fremen=2)), *placed.players[1:]),
    )
    assert _discards(engine, risen) == {paid, kept}
    spice = owner.resources.spice
    assert (
        _do(engine, risen, "discard_agent_card", card_id=kept)
        .players[0]
        .resources.spice
        == spice + 2
    )


def test_spice_trader_pays_once_per_turn_and_can_stay_unpaid() -> None:
    """ "하나의 화살표 비용과 효과는 한 턴에 한 번만" (player-turns.md [Main
    p. 9] [FAQ p. 3]) and no payment means no effect: the arrow is optional
    and offers no refusal row (OQ-095 (2))."""
    engine, state = _start()
    paid, kept, third = state.players[0].hand[:3]
    placed = _trader(engine, state, (paid, kept, third), influence=Influence(fremen=2))
    assert "decline_agent_card_discard" not in _ids(engine, placed)
    unpaid = _finish(engine, placed).players[0]
    assert {paid, kept, third} <= set(unpaid.hand)
    assert not {paid, kept, third} & set(unpaid.discard_pile)
    assert unpaid.resources.spice == placed.players[0].resources.spice
    after = _do(engine, placed, "discard_agent_card", card_id=paid)
    assert not _discards(engine, after)
    assert after.players[0].hand == (kept, third)


def test_spice_trader_offers_no_discard_with_an_empty_hand() -> None:
    """ "내지 않으면 효과도 없다" [Rise of Ix p. 7]: the played Spice Trader
    cannot pay itself; the Influence is held, so the block is the hand."""
    engine, state = _start()
    placed = _trader(engine, state, (), influence=Influence(fremen=2))
    assert not _discards(engine, placed)
    assert agent_card_cost_block(placed, 0) == OptionalEffectBlock(
        OptionalBlockKind.HAND, 1, 0
    )


def test_spice_trader_reveals_two_persuasion_and_a_sword() -> None:
    """App table: Reveal 2 Persuasion and 1 sword; its arrow is Agent-box
    only. A sword counts with a troop in the Conflict ("troop 2, sword 1;
    Conflict에 troop이 하나도 없으면 0" [DI p. 11])."""
    engine, state = _start()
    state = _seat(
        state,
        hand=(SPICE_TRADER,),
        influence=Influence(fremen=2),
        troops_conflict=1,
    )
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (2, 1)
    assert revealed.players[0].combat_strength == 2 + 1
    assert "discard_agent_card" not in _ids(engine, revealed)


# --- Imperial Bashar ------------------------------------------------------------

BASHAR = "imperium:imperial_bashar:0"
JAMIS = "imperium:jamis:0"
SISTER = "imperium:bene_gesserit_sister:0"
FENCE = "imperium:local_fence:0"
_RECRUIT_OR_TRASH = _BOX.RECRUIT_ONE_OR_MAY_TRASH_A_CARD
_BOX_ROWS = {"resolve_agent_card_effect", "trash_agent_card"}


def _bashar(
    engine: _Engine,
    state: GameState,
    hand: tuple[str, ...] = (),
    space: str = "arrakeen",
    **changes: object,
) -> GameState:
    """Imperial Bashar sent to ``space`` (Arrakeen, its City icon) with
    ``hand`` besides it, its box pending."""

    state = _seat(state, 0, hand=(BASHAR, *hand), **changes)
    return _send(engine, state, BASHAR, space)


def _box_rows(engine: _Engine, state: GameState) -> list[DomainAction]:
    return [row for row in _rows(engine, state) if row.action_id in _BOX_ROWS]


def _revealed(engine: _Engine, state: GameState, *hand: str) -> GameState:
    state = _seat(state, 0, hand=hand, troops_conflict=1)
    return _do(engine, state, "reveal_turn")


def test_imperial_bashar_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "[Troop] -OR- [Trash a card]" / "+[sword] for each other revealed card
    that provides one or more [sword] this turn."

    App table: cost 4, one copy, Emperor, the City icon, Reveal 1 Persuasion
    and 2 swords; the per-card swords are its Reveal record's line.
    """
    entry = IMPERIUM_CARDS_BY_ID["imperial_bashar"]
    assert (entry.copies, entry.acquisition_cost) == (1, 4)
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.infiltration_icons == ()
    assert entry.agent_effect is _RECRUIT_OR_TRASH
    assert entry.reveal_choice_effects == ()
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 2)
    assert entry.play_data_complete
    assert BASHAR in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert BASHAR not in content_for(config).imperium_deck_instance_ids


def test_imperial_bashar_card_text_prints_the_or_and_the_sword_count() -> None:
    """ "[Troop] -OR- [Trash a card]" and "+[sword] for each other revealed card
    that provides one or more [sword] this turn" [Steam app screen pieces and
    text]."""
    entry = IMPERIUM_CARDS_BY_ID["imperial_bashar"]
    assert personal_card_text(entry) == [
        "Agent: Choose one: Recruit 1 troop / You may trash a card",
        "Reveal: +1 sword per other revealed sword card",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 하나 선택: {troop:1} / 카드 1장 {trash} 가능",
        "공개 칸: +{sword:1} (공개한 다른 {sword} 카드마다)",
    ]


def test_imperial_bashar_goes_to_its_one_icon_only() -> None:
    """The City Agent icon (app attribute table)."""
    engine, state = _start()
    state = _seat(state, hand=(BASHAR,))
    spaces = {
        str(dict(row.arguments)["space_id"])
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == BASHAR
    }
    assert {"arrakeen", "carthag"} <= spaces
    assert not spaces & {"wealth", "stillsuits", "foldspace", "imperial_basin"}


def test_imperial_bashar_offers_the_recruit_and_a_trash_of_any_card() -> None:
    """ "Trash ... 비용이거나 카드가 자기를 trash하라고 할 때만 의무"
    (docs/rules/imperium-base.md 11, [DI p. 16]): the black Trash icon is
    optional, so the box offers the recruit and a trash of each card in hand,
    discard pile or play (itself included, "Trash a card from your hand,
    discard pile, or in play" [Main p. 20]) and no refusal row."""
    engine, state = _start()
    held, kept = state.players[0].hand[:2]
    discarded = state.players[0].deck[0]
    placed = _bashar(
        engine,
        state,
        (held, kept),
        deck=state.players[0].deck[1:],
        discard_pile=(discarded,),
    )
    rows = _box_rows(engine, placed)
    assert sum(row.action_id == "resolve_agent_card_effect" for row in rows) == 1
    assert {
        dict(row.arguments)["card_id"]
        for row in rows
        if row.action_id == "trash_agent_card"
    } == {held, kept, discarded, BASHAR}
    assert not {
        row.action_id
        for row in _rows(engine, placed)
        if row.action_id.startswith("decline_")
    }


def test_imperial_bashar_recruit_takes_the_or_and_ends_the_box() -> None:
    """ "[Troop] -OR- [Trash a card]": the recruit is one troop to the
    garrison, deployable this turn at a Combat space ([Main p. 10] [FAQ p. 4]),
    and the box is done: the trash rows go with it."""
    engine, state = _start()
    held = state.players[0].hand[0]
    placed = _bashar(engine, state, (held,))
    before = placed.players[0]
    recruited = _do(engine, placed, "resolve_agent_card_effect")
    after = recruited.players[0]
    assert after.troops_garrison == before.troops_garrison + 1
    assert after.troops_supply == before.troops_supply - 1
    assert after.trashed == before.trashed
    assert not _box_rows(engine, recruited)
    assert max(_deploy_counts(engine, recruited)) == (
        max(_deploy_counts(engine, placed)) + 1
    )


def _deploy_counts(engine: _Engine, state: GameState) -> set[int]:
    counts = {
        dict(row.arguments)["count"]
        for row in _rows(engine, state)
        if row.action_id == "deploy_troops"
    }
    assert all(isinstance(count, int) for count in counts)
    return {count for count in counts if isinstance(count, int)}


@pytest.mark.parametrize("zone", ["hand", "discard_pile", "in_play"])
def test_imperial_bashar_trash_takes_the_or_and_ends_the_box(zone: str) -> None:
    """ "[Troop] -OR- [Trash a card]": the trash is the other line, so no troop
    comes, and the trash rows and the recruit go with the box."""
    engine, state = _start()
    held, kept, other = state.players[0].hand[:3]
    owner = state.players[0]
    target = {"hand": held, "discard_pile": other, "in_play": BASHAR}[zone]
    placed = _bashar(
        engine,
        state,
        (held, kept),
        discard_pile=(other,),
    )
    before = placed.players[0]
    trashed = _do(engine, placed, "trash_agent_card", card_id=target)
    after = trashed.players[0]
    assert after.trashed == (*before.trashed, target)
    assert target not in (*after.hand, *after.discard_pile, *after.in_play)
    assert after.troops_garrison == before.troops_garrison
    assert after.troops_supply == before.troops_supply
    assert not _box_rows(engine, trashed)
    assert owner.player_id == 0


def test_imperial_bashar_may_stay_unused_and_lapses_at_the_turns_end() -> None:
    """ "Trash ... 비용이거나 카드가 자기를 trash하라고 할 때만 의무"
    (imperium-base.md 11, [DI p. 16]): taking the trash and declining it is
    doing nothing, so the box is optional -- no refusal row, and pressing the
    turn's end lapses it (OQ-095 (2)) without a recruit or a trash."""
    engine, state = _start()
    held = state.players[0].hand[0]
    placed = _bashar(engine, state, (held,))
    unused = _finish(engine, placed).players[0]
    assert unused.trashed == placed.players[0].trashed
    assert {held, BASHAR} <= {*unused.hand, *unused.in_play, *unused.discard_pile}
    recruited = _finish(
        engine, _do(engine, placed, "resolve_agent_card_effect")
    ).players[0]
    assert unused.troops_supply == recruited.troops_supply + 1


def test_imperial_bashar_offers_no_recruit_without_a_troop_to_join() -> None:
    """A recruit with no troop in the supply buys nothing and is not offered
    (OQ-071, ``troop_can_join``); the trash still is, and the box can be left."""
    engine, state = _start()
    held = state.players[0].hand[0]
    placed = _bashar(engine, state, (held,), troops_garrison=12, troops_conflict=0)
    assert placed.players[0].troops_supply == 0
    rows = _box_rows(engine, placed)
    assert "resolve_agent_card_effect" not in {row.action_id for row in rows}
    assert {dict(row.arguments)["card_id"] for row in rows} >= {held, BASHAR}
    assert _finish(engine, placed).players[0].trashed == ()


def test_imperial_bashar_block_says_what_is_missing() -> None:
    """Greyed out only when neither line can act: no troop can join and no card
    can be trashed (``either_trash_block``, read by the page)."""
    engine, state = _start()
    ability = AGENT_BOX_ABILITIES[_RECRUIT_OR_TRASH]
    bare = _seat(
        state,
        0,
        hand=(),
        discard_pile=(),
        in_play=(),
        troops_garrison=12,
        troops_conflict=0,
    )
    block = either_trash_block(bare, 0, ability, {})
    assert block == OptionalEffectBlock(
        OptionalBlockKind.NO_TROOP_TO_RECRUIT,
        also=OptionalEffectBlock(OptionalBlockKind.NO_CARD_TO_TRASH),
    )
    with_card = _seat(bare, 0, discard_pile=(state.players[0].hand[0],))
    assert either_trash_block(with_card, 0, ability, {}) is None
    with_troop = _seat(bare, 0, troops_garrison=11, troops_supply=1)
    assert either_trash_block(with_troop, 0, ability, {}) is None


def test_imperial_bashar_trashing_an_unload_card_gives_its_box() -> None:
    """The black Trash icon is no cost, and a trashed Unload card gives its
    Reveal box while it is trashed (rise-of-ix.md 7): CHOAM Delegate's "[Unload]
    [3 Solari]" waits as a row of the turn."""
    engine, state = _start()
    delegate = "imperium:choam_delegate:0"
    placed = _bashar(engine, state, (delegate,), resources=Resources())
    solari = placed.players[0].resources.solari
    trashed = _do(engine, placed, "trash_agent_card", card_id=delegate)
    assert trashed.players[0].resources.solari == solari
    taken = _do(
        engine, trashed, "resolve_unload_icon", card_id=delegate, effect="solari"
    )
    assert taken.players[0].resources.solari == solari + 3


def test_imperial_bashar_reveals_one_persuasion_and_two_swords() -> None:
    """App table: Reveal 1 Persuasion and 2 swords; alone it counts no other
    card. A sword counts with a troop in the Conflict ("troop 2, sword 1;
    Conflict에 troop이 하나도 없으면 0" [DI p. 11])."""
    engine, state = _start()
    revealed = _revealed(engine, state, BASHAR)
    context = dict(revealed.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (1, 2)
    assert revealed.players[0].combat_strength == 2 + 2
    assert not _box_rows(engine, revealed)


def test_imperial_bashar_counts_each_other_card_that_gives_swords() -> None:
    """ "+[sword] for each other revealed card that provides one or more [sword]
    this turn": Jamis gives 2 swords, so Bashar's 2 + 1 and Jamis' 2; Local
    Fence gives only Persuasion and adds nothing."""
    engine, state = _start()
    with_jamis = _revealed(engine, state, BASHAR, JAMIS)
    assert dict(with_jamis.decision_stack[-1].context)["sword_strength"] == 2 + 1 + 2
    assert with_jamis.players[0].combat_strength == 2 + 5
    with_fence = _revealed(engine, state, BASHAR, FENCE)
    context = dict(with_fence.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (1 + 2, 2)


def test_imperial_bashar_counts_only_swords_actually_given() -> None:
    """Rise of Ix's clarification: "Imperial Bashar" counts only another card
    that really provided swords, so Bene Gesserit Sister choosing 2 Persuasion
    is not counted ([Rise of Ix p. 10], docs/rules/rise-of-ix.md 9.1); choosing
    her 2 swords instead counts her, once."""
    engine, state = _start()
    revealed = _revealed(engine, state, BASHAR, SISTER)
    assert dict(revealed.decision_stack[-1].context)["sword_strength"] == 2
    persuasion = _do(engine, revealed, "gain_two_reveal_persuasion")
    context = dict(persuasion.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (1 + 2, 2)
    assert persuasion.players[0].combat_strength == 2 + 2
    swords = _do(engine, revealed, "gain_two_reveal_swords")
    assert dict(swords.decision_stack[-1].context)["persuasion"] == 1
    # One troop (2), Bashar's 2 and 1 for the Sister, and the Sister's 2.
    assert swords.players[0].combat_strength == 2 + 2 + 1 + 2
