"""Rise of Ix Imperium batch A: cards supported by existing play pieces.

Steam app attribute table, per-card UI pieces and English localization
(4.1.2.1808, dad97e20); rules: imperium-base.md 5, 11 [DI pp. 9, 16],
player-turns.md [FAQ p. 3], uprising-systems.md [Main p. 20].
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
SAYYADINA = "imperium:sayyadina:0"


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_placement and apply_whole."""

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


def _seat(state: GameState, **changes: object) -> GameState:
    players = list(state.players)
    players[0] = replace(players[0], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _rows(engine: _Engine, state: GameState) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, 0)
    return engine.whole_actions(state, 0)


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


def _place(engine: _Engine, state: GameState, space: str) -> GameState:
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == SAYYADINA
        and dict(row.arguments)["space_id"] == space
    )
    result = apply_placement(engine, state, placement).state
    engine.legal_actions(result, 0)
    return result


# --- Sayyadina ---------------------------------------------------------------


def test_sayyadina_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "[3 water] -> [1 Victory Point]"; "Fremen Bond: [3 Persuasion]".

    App table: cost 3, one copy, Bene Gesserit/Fremen affiliations and icons;
    the conditional Persuasion is not a fixed Reveal value.
    """
    entry = IMPERIUM_CARDS_BY_ID["sayyadina"]
    assert (entry.copies, entry.acquisition_cost) == (1, 3)
    assert entry.factions == (Faction.BENE_GESSERIT, Faction.FREMEN)
    assert entry.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN)
    assert entry.agent_effect is PersonalCardAgentEffect.MAY_PAY_THREE_WATER_FOR_VP
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.play_data_complete
    assert SAYYADINA in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert SAYYADINA not in content_for(config).imperium_deck_instance_ids


@pytest.mark.parametrize("water", (0, 2, 3, 6))
def test_sayyadina_pays_exactly_three_water_once(water: int) -> None:
    """ "[3 water] -> [1 Victory Point]". "하나의 화살표 비용과 효과는 한 턴에
    한 번만 선택할 수 있다" (player-turns.md [Main p. 9] [FAQ p. 3])."""
    engine, state = _start()
    state = _seat(state, hand=(SAYYADINA,), resources=Resources(water=water))
    placed = _place(engine, state, "secrets")
    before = placed.players[0]
    ids = {row.action_id for row in _rows(engine, placed)}
    if water < 3:
        assert "pay_agent_card_water" not in ids
        assert placed.players[0].resources.water == water
        return
    assert "pay_agent_card_water" in ids
    paid = _do(engine, placed, "pay_agent_card_water")
    assert paid.players[0].resources == replace(before.resources, water=water - 3)
    assert paid.players[0].victory_points == before.victory_points + 1
    assert "pay_agent_card_water" not in {row.action_id for row in _rows(engine, paid)}


def test_sayyadina_can_skip_the_arrow_and_finish_her_agent_turn() -> None:
    """ "[3 water] -> [1 Victory Point]"; "화살표 비용을 지불하지 않거나 ...
    그 효과를 생략할 수 있다" (player-turns.md [FAQ p. 3])."""
    engine, state = _start()
    state = _seat(state, hand=(SAYYADINA,), resources=Resources(water=3))
    placed = _place(engine, state, "secrets")
    resolved = _do(engine, placed, "resolve_board_effect", effect="intrigue")
    resolved = _do(engine, resolved, "resolve_faction_influence")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].resources.water == 3
    assert finished.players[0].victory_points == placed.players[0].victory_points


def test_sayyadina_can_use_the_water_gained_from_stillsuits() -> None:
    """ "[3 water] -> [1 Victory Point]". "칸 효과, Agent box, Faction 칸의
    Influence 1은 원하는 순서로 처리한다" (imperium-base.md [DI p. 9])."""
    engine, state = _start()
    state = _seat(state, hand=(SAYYADINA,), resources=Resources(water=2))
    placed = _place(engine, state, "stillsuits")
    assert "pay_agent_card_water" not in {
        row.action_id for row in _rows(engine, placed)
    }
    watered = _do(engine, placed, "resolve_board_effect", effect="resources")
    paid = _do(engine, watered, "pay_agent_card_water")
    assert paid.players[0].resources.water == 0
    assert paid.players[0].victory_points == placed.players[0].victory_points + 1


def test_sayyadina_board_cost_is_paid_before_the_arrow() -> None:
    """ "[3 water] -> [1 Victory Point]". "칸의 비용은 어떤 효과보다 먼저
    낸다" (imperium-base.md 5 [DI p. 9]); Hardy Warriors costs one water."""
    engine, state = _start()
    state = _seat(state, hand=(SAYYADINA,), resources=Resources(water=3))
    placed = _place(engine, state, "hardy_warriors")
    assert placed.players[0].resources.water == 2
    assert "pay_agent_card_water" not in {
        row.action_id for row in _rows(engine, placed)
    }


@pytest.mark.parametrize("bond_zone", ("none", "revealed", "agent", "discard"))
def test_sayyadina_reveal_needs_another_fremen_in_play(bond_zone: str) -> None:
    """ "Fremen Bond: [3 Persuasion]"; "Fremen Bond 효과는 다른 Fremen card가
    하나 이상 in play일 때 사용할 수 있다" (uprising-systems.md [Main p. 20];
    imperium-base.md 11 [DI p. 16])."""
    engine, state = _start()
    other = "imperium:crysknife_card:0"
    hand = (SAYYADINA, other) if bond_zone == "revealed" else (SAYYADINA,)
    state = _seat(
        state,
        hand=hand,
        in_play=(other,) if bond_zone == "agent" else (),
        discard_pile=(other,) if bond_zone == "discard" else (),
        resources=Resources(water=3),
    )
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == (3 if bond_zone in ("revealed", "agent") else 0)
    assert context["sword_strength"] == (1 if bond_zone == "revealed" else 0)
    assert "pay_agent_card_water" not in {
        row.action_id for row in _rows(engine, revealed)
    }


def test_sayyadina_can_be_acquired_from_the_imperium_row() -> None:
    """ "Fremen Bond: [3 Persuasion]". "획득한 카드는 discard pile로 간다"
    (imperium-base.md 5 [DI p. 11] [FAQ p. 2]); Sayyadina costs 3."""
    engine, state = _start()
    state = _seat(
        state, hand=("imperium:sietch_reverend_mother:0", "imperium:spice_hunter:0")
    )
    state = replace(state, imperium_row=(SAYYADINA, *state.imperium_row[1:]))
    revealed = _do(engine, state, "reveal_turn")
    acquired = _do(engine, revealed, "acquire_imperium", instance_id=SAYYADINA)
    assert SAYYADINA in acquired.players[0].discard_pile
    assert SAYYADINA not in acquired.imperium_row
    assert dict(acquired.decision_stack[-1].context)["persuasion"] == 1
