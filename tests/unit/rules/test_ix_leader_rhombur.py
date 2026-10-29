"""Prince Rhombur Vernius, a Rise of Ix Leader (stage P4e).

docs/rules/rise-of-ix.md 10: "Prince Rhombur Vernius (1) | Heavy Lasgun
Cannons: dreadnought strength 4 | Ixian Technology: Acquire Tech -OR- Tech
Negotiation | 오른쪽 아이콘이 Tech Negotiation인 근거: Rival 문장 "Acquire Tech if
he can. If not, he will use the Tech Negotiation icon" `[Rise of Ix p. 8]`".
Played through ``UprisingRulesEngine`` in an original game with Rise of Ix,
Rhombur at seat 0; every offered row round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rise_of_ix.tech import IX_TECH_TILES_BY_ID
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import AcquireTech, PlaceNegotiator
from dune_imperium.content.uprising.leader_abilities import SIGNET_ABILITIES
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerState,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.strength import dreadnought_strength, units_strength

RHOMBUR = "prince_rhombur_vernius"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (RHOMBUR, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


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


def _with_card(state: GameState, card_id: str) -> GameState:
    owner = state.players[0]
    if any(f":{card_id}:" in card for card in owner.hand):
        return state
    instance = next(card for card in owner.deck if f":{card_id}:" in card)
    return _seat(
        state,
        hand=(*owner.hand, instance),
        deck=tuple(card for card in owner.deck if card != instance),
    )


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


def _signet(engine: _Engine, state: GameState, **changes: object) -> GameState:
    """Seat 0 sends the Signet Ring to Arrakeen."""

    state = _seat(_with_card(state, "signet_ring"), **changes)
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


_HALVES = {"acquire_leader_tech", "place_leader_negotiator"}


def _offered(engine: _Engine, state: GameState) -> set[str]:
    return {row.action_id for row in _rows(engine, state)} & _HALVES


def test_rhombur_is_offered_with_rise_of_ix_and_prints_his_signet() -> None:
    """He joins the original game's Leaders only with Rise of Ix [Rise of Ix
    p. 3]; his Signet prints the Negotiator and the Acquire Tech (no Tech
    Discount) as the two halves of an "-OR-" (rise-of-ix.md 10)."""

    assert RHOMBUR in {leader.leader_id for leader in content_for(CONFIG).leaders}
    plain = RulesetConfig(base_game=BaseGame.IMPERIUM)
    assert RHOMBUR not in {leader.leader_id for leader in content_for(plain).leaders}
    record = SIGNET_ABILITIES[RHOMBUR]
    assert [line.rewards for line in record.sections] == [
        (PlaceNegotiator(),),
        (AcquireTech(discount=0),),
    ]


# --- Heavy Lasgun Cannons ------------------------------------------------------


def test_heavy_lasgun_cannons_make_his_dreadnoughts_four_strong() -> None:
    """ "Heavy Lasgun Cannons: dreadnought strength 4" (rise-of-ix.md 10; 6:
    "Conflict의 dreadnought 하나는 strength 3(Prince Rhombur Vernius는 4)"
    [Rise of Ix p. 6]); everyone else's stays 3."""

    _, state = _start()

    def fighting(seat: int) -> PlayerState:
        player = state.players[seat]
        return replace(
            player,
            dreadnoughts_supply=0,
            dreadnoughts_conflict=2,
            troops_supply=player.troops_supply - 1,
            troops_conflict=1,
        )

    rhombur, other = fighting(0), fighting(1)
    assert dreadnought_strength(rhombur) == 4
    assert dreadnought_strength(other) == 3
    assert units_strength(rhombur) == 2 * 4 + 2
    assert units_strength(other) == 2 * 3 + 2
    # A dreadnought alone is a unit: 4 strength with no troop [FAQ p. 2].
    alone = replace(
        rhombur,
        dreadnoughts_supply=1,
        dreadnoughts_conflict=1,
        troops_supply=rhombur.troops_supply + 1,
        troops_conflict=0,
    )
    assert units_strength(alone) == 4


# --- Ixian Technology -----------------------------------------------------------


def test_ixian_technology_offers_both_halves_when_both_can_be_taken() -> None:
    """ "Ixian Technology: Acquire Tech -OR- Tech Negotiation" (rise-of-ix.md
    10): each half a "may" (rise-of-ix.md 4), one of them per play."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(spice=10))
    assert _offered(engine, placed) == _HALVES


def test_ixian_technology_s_negotiator_sends_a_supply_troop_to_the_ix_board() -> None:
    """ "Tech Negotiation(협상가): 아이콘마다 supply의 troop 하나를 Ix board에
    Negotiator로 놓을 수 있다" (rise-of-ix.md 4); the other half is then gone."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(spice=10))
    owner = placed.players[0]
    after = _do(engine, placed, "place_leader_negotiator")
    assert after.players[0].negotiators == owner.negotiators + 1
    assert after.players[0].troops_supply == owner.troops_supply - 1
    assert _offered(engine, after) == set()


def test_ixian_technology_s_acquire_tech_buys_a_tile_at_its_full_cost() -> None:
    """ "아이콘마다 Ix board의 세 더미 맨 위 앞면 타일 하나를 얻을 수 있다("may").
    spice 비용을 내고" (rise-of-ix.md 4): the Signet's Acquire Tech prints no
    Tech Discount, so a tile costs its printed spice; the window offers its
    refusal ("may")."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(spice=10))
    opened = _do(engine, placed, "acquire_leader_tech")
    assert opened.decision_stack[-1].kind == FrameKind.TECH_ACQUISITION
    rows = _rows(engine, opened)
    assert DomainAction("decline_tech", 0) in rows
    buy = next(
        row
        for row in rows
        if row.action_id == "acquire_tech" and "negotiators" not in dict(row.arguments)
    )
    tech_id = str(dict(buy.arguments)["tech_id"])
    bought = apply_whole(engine, opened, buy).state
    cost = IX_TECH_TILES_BY_ID[tech_id].cost
    assert tech_id in bought.players[0].tech_ids
    assert bought.players[0].resources.spice == 10 - cost
    assert _offered(engine, bought) == set()


def test_ixian_technology_offers_only_what_can_be_taken() -> None:
    """With no tile within reach only the Negotiator is offered; with no
    troop in the supply only the Acquire Tech ("supply가 비면 아무 일도
    없다", rise-of-ix.md 4)."""

    engine, state = _start()
    broke = _signet(engine, state, resources=Resources(spice=0))
    assert _offered(engine, broke) == {"place_leader_negotiator"}
    owner = state.players[0]
    emptied = _signet(
        engine,
        state,
        resources=Resources(spice=10),
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    assert _offered(engine, emptied) == {"acquire_leader_tech"}
