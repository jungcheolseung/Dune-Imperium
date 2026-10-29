"""Archduke Armand Ecaz, a Rise of Ix Leader (stage P4e).

docs/rules/rise-of-ix.md 10: "Archduke Armand Ecaz (2) | Coordination: Reveal
turn에 Landsraad·City·Spice Trade 칸에 Agent 둘 이상이면 in play 카드 하나를 trash할
수 있다 | Conscript: 비용 3 이하 카드 하나를 얻을 수 있다 | `[FAQ p. 1]`; Mentat도
그의 Agent로 센다(디자이너 판정)"; 9.2: "Archduke Armand Ecaz | 1 | Coordination:
세 아이콘 칸 어디든 Agent 둘 이상(같은 아이콘일 필요 없음)". Played through
``UprisingRulesEngine`` in an original game with Rise of Ix, Armand at seat 0;
every offered row round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.leader_abilities import coordination_agents

ARMAND = "archduke_armand_ecaz"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (ARMAND, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


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


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
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


def test_armand_is_offered_with_rise_of_ix() -> None:
    """He joins the original game's Leaders only with Rise of Ix [Rise of Ix
    p. 3]."""

    assert ARMAND in {leader.leader_id for leader in content_for(CONFIG).leaders}
    plain = RulesetConfig(base_game=BaseGame.IMPERIUM)
    assert ARMAND not in {leader.leader_id for leader in content_for(plain).leaders}


# --- Coordination ---------------------------------------------------------------


def _revealing(*spaces: str) -> tuple[_Engine, GameState]:
    """Armand's Reveal turn with his Agents on ``spaces``, the cards that
    sent them in play."""

    engine, state = _start()
    owner = state.players[0]
    played = owner.hand[: len(spaces)]
    state = _seat(
        state,
        hand=owner.hand[len(spaces) :],
        in_play=(*owner.in_play, *played),
        agent_locations=spaces,
        agents_available=2 - len(spaces),
    )
    return engine, _do(engine, state, "reveal_turn")


def _coordination(engine: _Engine, state: GameState) -> set[str]:
    return {
        str(dict(row.arguments)["card_id"])
        for row in _rows(engine, state)
        if row.action_id == "trash_leader_reveal_card"
    }


def test_coordination_trashes_a_card_in_play_with_two_agents_on_its_icons() -> None:
    """ "Reveal turn에 Landsraad·City·Spice Trade 칸에 Agent 둘 이상이면 in play
    카드 하나를 trash할 수 있다" (rise-of-ix.md 10): any of the three icons,
    not the same one [FAQ p. 1] -- here the Landsraad's Tech Negotiation and
    the City's Arrakeen. Any card in play may go, once a Reveal turn."""

    engine, revealed = _revealing("tech_negotiation", "arrakeen")
    owner = revealed.players[0]
    assert coordination_agents(owner) == 2
    offered = _coordination(engine, revealed)
    assert offered == set(owner.in_play)
    card = sorted(offered)[0]
    trashed = _do(engine, revealed, "trash_leader_reveal_card", card_id=card)
    assert card not in trashed.players[0].in_play
    assert card in trashed.players[0].trashed
    assert _coordination(engine, trashed) == set()


def test_coordination_needs_two_agents_on_those_spaces() -> None:
    """One Agent on a Landsraad, City or Spice Trade space, or two with one of
    them on a Faction space, offers nothing (rise-of-ix.md 10)."""

    engine, revealed = _revealing("arrakeen", "wealth")
    assert coordination_agents(revealed.players[0]) == 1
    assert _coordination(engine, revealed) == set()
    engine, single = _revealing("imperial_basin")
    assert _coordination(engine, single) == set()


def test_coordination_counts_the_mentat_as_one_of_his_agents() -> None:
    """ "Mentat도 그의 Agent로 센다(디자이너 판정)" (rise-of-ix.md 10): the Mentat
    stands on its space like his own Agents, so a third Agent placed on a
    Spice Trade space completes the two."""

    _, state = _start()
    owner = replace(
        state.players[0],
        mentat=True,
        agent_locations=("wealth", "mentat", "smuggling"),
        agents_available=0,
    )
    # The Mentat space itself prints the Landsraad icon [DI p. 17].
    assert coordination_agents(owner) == 2


# --- Conscript --------------------------------------------------------------------


def _signet(engine: _Engine, state: GameState) -> GameState:
    """Seat 0 sends the Signet Ring to Arrakeen."""

    engine.legal_actions(state, 0)
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == "arrakeen"
        and ":signet_ring:" in str(dict(placement.arguments)["card_id"])
    )
    placed = apply_placement(engine, state, placement).state
    engine.legal_actions(placed, 0)
    return placed


def _conscript(engine: _Engine, state: GameState) -> set[tuple[str, str, bool]]:
    return {
        (
            row.action_id,
            str(
                dict(row.arguments).get(
                    "instance_id", dict(row.arguments).get("card_id")
                )
            ),
            dict(row.arguments).get("to_deck_top") is True,
        )
        for row in _rows(engine, state)
        if row.action_id in ("acquire_leader_imperium", "acquire_leader_reserve")
    }


def test_conscript_acquires_a_card_of_cost_three_or_less_to_the_discard() -> None:
    """ "Conscript: 비용 3 이하 카드 하나를 얻을 수 있다" (rise-of-ix.md 10): the
    Row's and the Reserve's -- Arrakis Liaison, never Foldspace (OQ-125) --
    to the discard pile [DI p. 11]."""

    engine, state = _start()
    placed = _signet(engine, state)
    cheap = {
        instance
        for instance in placed.imperium_row
        if (imperium_card_for_instance(instance).acquisition_cost or 99) <= 3
    }
    assert cheap
    assert _conscript(engine, placed) == {
        *(("acquire_leader_imperium", instance, False) for instance in cheap),
        ("acquire_leader_reserve", "arrakis_liaison", False),
    }
    card = sorted(cheap)[0]
    acquired = _do(engine, placed, "acquire_leader_imperium", instance_id=card)
    assert card in acquired.players[0].discard_pile
    assert card not in acquired.imperium_row
    assert _conscript(engine, acquired) == set()


def test_conscript_puts_the_card_on_the_deck_with_spaceport() -> None:
    """Spaceport: "얻는 카드를 덱 위에 놓을 수 있다" (rise-of-ix.md 4); 9.3:
    "Spaceport의 획득 효과는 바로(Armand의 Signet으로 덱 위에 놓은 뒤 뽑기
    불가)" -- so Conscript's card may go on top of his deck."""

    engine, state = _start()
    stacks = tuple(
        tuple(tile for tile in stack if tile != "spaceport")
        for stack in state.tech_stacks
    )
    state = _seat(replace(state, tech_stacks=stacks), tech_ids=("spaceport",))
    placed = _signet(engine, state)
    offered = _conscript(engine, placed)
    assert ("acquire_leader_reserve", "arrakis_liaison", True) in offered
    topped = _do(
        engine,
        placed,
        "acquire_leader_reserve",
        card_id="arrakis_liaison",
        to_deck_top=True,
    )
    assert "arrakis_liaison" in topped.players[0].deck[0]
