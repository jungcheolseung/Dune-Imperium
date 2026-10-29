"""Rise of Ix Imperium batch C: Reveal conditions and an OR of two arrows.

Steam app attribute table, per-card UI pieces and English localization
(4.1.2.1808, dad97e20); rules: imperium-base.md 2 ("strength 단위 | troop 2,
sword 1; Conflict에 troop이 하나도 없으면 0" [DI p. 11]; "Recall | Mentat을 제
칸으로 돌린 뒤 Agent recall" [DI p. 13]), player-turns.md [Main p. 9]
[FAQ p. 3]. Every offered row round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
)
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
SHOCK_TROOPER = "imperium:imperial_shock_trooper:0"


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


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    owner = players[seat]
    if "agent_locations" in changes:
        locations = changes["agent_locations"]
        assert isinstance(locations, tuple)
        changes["agents_available"] = 2 - len(locations)
    if "troops_conflict" in changes:
        conflict = changes["troops_conflict"]
        assert isinstance(conflict, int)
        changes["troops_supply"] = 12 - owner.troops_garrison - conflict
    players[seat] = replace(owner, **changes)  # type: ignore[arg-type]
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


# --- Imperial Shock Trooper ----------------------------------------------------


def test_shock_trooper_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "If you have an Agent on an [Emperor] board space," [+3 swords].

    App table: cost 3, one copy, Emperor, no Agent icon, Reveal 1 Persuasion
    and 2 swords; the conditional swords are its Reveal record's line.
    """
    entry = IMPERIUM_CARDS_BY_ID["imperial_shock_trooper"]
    assert (entry.copies, entry.acquisition_cost) == (1, 3)
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == ()
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 2)
    assert entry.play_data_complete
    assert SHOCK_TROOPER in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert SHOCK_TROOPER not in content_for(config).imperium_deck_instance_ids


def test_shock_trooper_card_text_names_the_emperor_space() -> None:
    """ "If you have an Agent on an [Emperor] board space," [+3 swords]."""
    entry = IMPERIUM_CARDS_BY_ID["imperial_shock_trooper"]
    assert (
        "Reveal: If you have an Agent on an Emperor board space: +3 swords"
        in personal_card_text(entry)
    )
    assert (
        "공개 칸: 황제 게임판 장소에 {agent}가 있다면: +{sword:3}"
        in personal_card_text_ko(entry)
    )


@pytest.mark.parametrize(
    ("locations", "swords"),
    [
        ((), 2),
        (("wealth",), 5),
        (("conspire",), 5),
        (("foldspace",), 2),
        (("secrets", "wealth"), 5),
        (("arrakeen",), 2),
    ],
)
def test_shock_trooper_reads_agents_sent_earlier_this_round(
    locations: tuple[str, ...], swords: int
) -> None:
    """ "If you have an Agent on an [Emperor] board space," [+3 swords]; an
    Agent stays on its space until the Recall ("Recall | ... Agent recall"
    [DI p. 13]), and a sword counts with a troop in the Conflict ("troop 2,
    sword 1; Conflict에 troop이 하나도 없으면 0" [DI p. 11])."""
    engine, state = _start()
    state = _seat(
        state, hand=(SHOCK_TROOPER,), agent_locations=locations, troops_conflict=1
    )
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == swords
    assert revealed.players[0].combat_strength == 2 + swords


def test_shock_trooper_ignores_an_opponents_agent_on_an_emperor_space() -> None:
    """ "If **you** have an Agent on an [Emperor] board space," [+3 swords]."""
    engine, state = _start()
    state = _seat(state, hand=(SHOCK_TROOPER,), troops_conflict=1)
    state = _seat(state, 1, agent_locations=("wealth",))
    revealed = _do(engine, state, "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["sword_strength"] == 2


def test_shock_trooper_swords_need_a_unit_in_the_conflict() -> None:
    """ "Conflict에 troop이 하나도 없으면 0" [DI p. 11]: the printed and the
    conditional swords wait for a unit."""
    engine, state = _start()
    state = _seat(
        state, hand=(SHOCK_TROOPER,), agent_locations=("wealth",), troops_conflict=0
    )
    revealed = _do(engine, state, "reveal_turn")
    assert revealed.players[0].combat_strength == 0
