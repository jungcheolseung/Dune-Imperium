"""The running combat strength kept current between steps.

The printed rule sets the Combat marker during the Reveal turn and updates
it on every later change [Main p. 12]; the engine keeps one running
``combat_strength`` instead (user decision 2026-09-06) so a seat that
deploys or withdraws units in its Agent turn sees its strength move at
once. This module has no rules imports so both ``combat`` and
``reveal_turn`` can use the one formula.
"""

from dataclasses import replace

from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind


def units_strength(player: PlayerState) -> int:
    """Return the strength the units in the Conflict provide on their own.

    A troop is worth 2 and a sandworm 3, and without a unit there is no
    strength at all, swords or not [Main p. 12].
    """

    if player.troops_conflict + player.sandworms_conflict <= 0:
        return 0
    return player.troops_conflict * 2 + player.sandworms_conflict * 3


def reveal_in_progress(state: GameState, player: int) -> bool:
    """Return whether ``player``'s Reveal turn has begun and not finished."""

    return any(
        frame.kind == FrameKind.REVEAL
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == player
        for frame in state.decision_stack
    )


def refresh_pre_reveal_strength(result: RuleResult) -> RuleResult:
    """Keep ``combat_strength`` current before each seat's Reveal turn.

    The printed rule sets the Combat marker during the Reveal turn and
    updates it on every later change [Main p. 12]; the engine keeps one
    running value instead (user decision 2026-09-06), so a seat that
    deploys or withdraws units in its Agent turn sees its strength move at
    once. Until the seat's Reveal begins the value is exactly what its
    units provide (``units_strength``); from ``begin_reveal_turn`` on the
    Reveal adds the revealed swords to it and every later effect adjusts
    it incrementally, so this pass leaves revealing and revealed seats
    alone. Outcomes never change: at Reveal the total is the same sum the
    rule describes.
    """

    state = result.state
    # Once Combat begins every seat has revealed and the marker is live
    # (Combat Intrigue adjusts it, clean-up zeroes it), so only the turn
    # phases are refreshed.
    if state.phase not in (GamePhase.ROUND_START, GamePhase.PLAYER_TURNS):
        return result
    players = tuple(
        replace(player, combat_strength=units_strength(player))
        if not player.has_revealed
        and not reveal_in_progress(state, player.player_id)
        and player.combat_strength != units_strength(player)
        else player
        for player in state.players
    )
    if players == state.players:
        return result
    return replace(result, state=replace(state, players=players))

