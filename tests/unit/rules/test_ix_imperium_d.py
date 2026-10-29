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

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
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
    Resources,
)
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
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
    assert owner.hand == (paid, kept)
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
