"""A game in which one seat holds several set-aside Imperium cards.

Observation v43 widened each seat's ``imperium_set_aside`` from two slots to
five after mixed-rules training raised on a third (seed 2000231, the ruleset
below, round 8). The observation and entity network tests build the state
here.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    GamePhase,
    PlayerDecision,
)
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine

# The ruleset of the training game that raised: the original board with Rise
# of Ix, Bloodlines (no Tech Module) and Immortality, where Helena Richese's
# Signet Ring card, Ghola's copy of it and Boundless Ambition set three
# cards aside in one round.
SET_ASIDE_RULESET = RulesetConfig.from_identifier(
    "imperium-4p-base+promo+ix+bloodlines+immortality+epic+scouts"
)
# The seat that holds them.
SET_ASIDE_SEAT = 1


def set_aside_state(count: int, config: RulesetConfig = SET_ASIDE_RULESET) -> GameState:
    """The first Agent turn of a ``config`` game, with ``count`` cards off the
    Imperium deck set aside for ``SET_ASIDE_SEAT``."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, 7)
    chance = ChanceResolver(seed=7)
    while state.phase is not GamePhase.PLAYER_TURNS:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        action = engine.legal_actions(state, decision.owner)[0]
        state = engine.apply(state, action).state
    taken = state.imperium_deck[:count]
    assert len(taken) == count
    players = list(state.players)
    players[SET_ASIDE_SEAT] = replace(
        players[SET_ASIDE_SEAT], imperium_set_aside=taken
    )
    return replace(
        state, players=tuple(players), imperium_deck=state.imperium_deck[count:]
    )
