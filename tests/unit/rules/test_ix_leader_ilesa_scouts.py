"""Ilesa Ecaz's set-aside in an Arrakeen Scouts game (P8-1 branch).

OQ-122 (user ruling 2026-10-23): "… → Ilesa Ecaz의 따로 두기 (Holtzman Engine으로
뽑은 카드까지 든 손에서 고른다) → Scouts 또는 First Player의 첫 turn"; the Scouts
step runs after the whole Round Start and before the first turn (OQ-072,
docs/rules/arrakeen-scouts.md). So with Scouts her One Step Ahead choice comes
first, and the round's Scouts step waits for it. Until this branch the engine
skipped the choice in every Scouts game (``phases.begin_round`` left it to a
first turn the Scouts step opened without it), so she never set a card aside.

Covered on both base games, with all of Rise of Ix and with its Leaders and
Tech tiles beside the Tech Module (``ix_leaders``, OQ-165); every offered row
round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.chance import is_fixed_outcome
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.one_step_ahead import SET_ASIDE_ACTION
from dune_imperium.simulation.invariants import check_observation_privacy

ILESA = "ilesa_ecaz"
SCOUTS = RulesetConfig(arrakeen_scouts=True, first_player_seat_zero=True)
CONFIGS = {
    "uprising-all": replace(SCOUTS, rise_of_ix=True),
    "uprising-leaders": replace(
        SCOUTS, bloodlines=True, tech_module=True, ix_tech_tiles=True, ix_leaders=True
    ),
    "original-all": replace(SCOUTS, base_game=BaseGame.IMPERIUM, rise_of_ix=True),
    "original-leaders": replace(
        SCOUTS,
        base_game=BaseGame.IMPERIUM,
        bloodlines=True,
        tech_module=True,
        ix_tech_tiles=True,
        ix_leaders=True,
    ),
}
# Leaders with no setup pick of their own, on each board (Ilesa at seat 0).
OTHERS = {
    BaseGame.UPRISING: ("gurney_halleck", "lady_amber_metulli", "lady_jessica"),
    BaseGame.IMPERIUM: ("glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald"),
}


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Round-trip every offered row through the game's codec."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _round_one(config: RulesetConfig) -> tuple[_Engine, GameState]:
    """The game up to its first player decision (chance first)."""

    engine = _Engine(leader_ids=(ILESA, *OTHERS[config.base_game]))
    state = engine.reset(config, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return engine, state


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_ilesa_sets_a_card_aside_before_the_scouts_step(name: str) -> None:
    config = CONFIGS[name]
    engine, state = _round_one(config)
    # Round Start is over and the Scouts step has not begun: the set-aside is
    # the only frame, with no turn frame under it.
    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 1
    assert state.scouts_opening
    assert [frame.kind for frame in state.decision_stack] == [
        FrameKind.ROUND_START_SET_ASIDE
    ]
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision) and decision.owner == 0
    rows = engine.legal_actions(state, 0)
    assert rows and all(row.action_id == SET_ASIDE_ACTION for row in rows)
    for seat in range(1, config.players):
        assert engine.legal_actions(state, seat) == ()
    card = str(dict(rows[0].arguments)["card_id"])
    hand = len(state.players[0].hand)

    after = engine.apply(state, rows[0]).state
    ilesa = after.players[0]
    assert ilesa.set_aside_card_id == card
    assert len(ilesa.hand) == hand - 1
    # The set-aside card is hers alone (docs/rules/rise-of-ix.md 13).
    check_observation_privacy(after)
    # Then the engine pauses before the Scouts step, whose first work may
    # reveal the secret picks due this round (OQ-103 6, hidden-information
    # audit 2026-11-02 finding 1): a one-outcome chance, in round 1 too.
    assert after.scouts_opening
    assert [frame.kind for frame in after.decision_stack] == [FrameKind.PAUSE]
    pause = engine.current_decision(after)
    assert isinstance(pause, ChanceDecision) and is_fixed_outcome(pause)
    assert pause.decision_id == "round:1:scouts_step:pause"
    # Its answer begins the step: its first unit, the round's draw, waited for
    # the choice (it runs only on an empty stack); no second set-aside is
    # asked for this round.
    after = engine.apply(after, ChanceResolver(seed=0).resolve(pause)).state
    assert after.scouts_opening
    assert [frame.kind for frame in after.decision_stack] == [FrameKind.SCOUTS_DRAW]
