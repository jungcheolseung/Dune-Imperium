"""The running combat strength kept current between steps.

The printed rule sets the Combat marker during the Reveal turn and updates
it on every later change [Main p. 12]; the engine keeps one running
``combat_strength`` instead (user decision 2026-09-06) so a seat that
deploys or withdraws units in its Agent turn sees its strength move at
once. This module has no rules imports so both ``combat`` and
``reveal_turn`` can use the one formula.

With the Bloodlines option the same value also folds in the Sardaukar
Commander Skills that give strength "when resolving combat" while a
Commander is in the Conflict [Bloodlines p. 4]: ``skill_strength`` is the
condition-dependent part and ``skill_strength_applied`` on the player
records how much of it the running total currently contains, so a later
change of a condition (an opponent's sandworm, a lost Influence) adjusts
the total by the difference only.
"""

from dataclasses import replace

from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_STRENGTH,
    skill_for_instance,
)
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind


def units_strength(player: PlayerState) -> int:
    """Return the strength the units in the Conflict provide on their own.

    A troop is worth 2 and a sandworm 3 [Main p. 12], a Sardaukar Commander
    2 [Bloodlines p. 4], and without a unit there is no strength at all,
    swords or not [Main p. 12].
    """

    if player.units_in_conflict <= 0:
        return 0
    return (
        player.troops_conflict * 2
        + player.sandworms_conflict * 3
        + player.commanders_conflict * COMMANDER_STRENGTH
    )


def skill_strength(players: tuple[PlayerState, ...], player: int) -> int:
    """Return the Combat strength the seat's Skills currently grant.

    Every Skill is active only while the seat has at least one Commander in
    the Conflict, and each works once per round however many Commanders
    are there [Bloodlines p. 4]. Conditions come from the tile faces: Canny
    needs an Agent on a Landsraad board space, Fierce adds one more sword
    while any opponent has a sandworm in the Conflict, Loyal needs Emperor
    Influence 3 [Skill tile faces].
    """

    owner = players[player]
    if owner.commanders_conflict <= 0 or not owner.skill_ids:
        return 0
    landsraad_agent = any(
        BOARD_SPACES_BY_ID[space_id].agent_icon is AgentIcon.LANDSRAAD
        for space_id in owner.agent_locations
        if space_id in BOARD_SPACES_BY_ID
    )
    opponent_sandworm = any(
        candidate.sandworms_conflict > 0
        for candidate in players
        if candidate.player_id != player
    )
    total = 0
    for instance_id in owner.skill_ids:
        skill = skill_for_instance(instance_id)
        total += skill.strength
        if landsraad_agent:
            total += skill.strength_if_landsraad_agent
        if opponent_sandworm:
            total += skill.strength_if_opponent_sandworm
        if (
            skill.emperor_influence_required
            and owner.influence.emperor >= skill.emperor_influence_required
        ):
            total += skill.strength_if_emperor_influence
    return total


def with_skill_strength(players: tuple[PlayerState, ...], player: int) -> PlayerState:
    """Return the seat with its Skill strength folded into the running total.

    A seat without units keeps strength 0 whatever its Skills say (no
    Commander in the Conflict means no active Skill), so the applied amount
    is simply reset there.
    """

    owner = players[player]
    if owner.units_in_conflict <= 0:
        if owner.skill_strength_applied == 0:
            return owner
        return replace(owner, skill_strength_applied=0)
    target = skill_strength(players, player)
    if target == owner.skill_strength_applied:
        return owner
    return replace(
        owner,
        combat_strength=owner.combat_strength - owner.skill_strength_applied + target,
        skill_strength_applied=target,
    )


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
    units provide (``units_strength``) plus its active Skills; from
    ``begin_reveal_turn`` on the Reveal adds the revealed swords to it and
    every later effect adjusts it incrementally, so this pass leaves
    revealing and revealed seats alone except for re-deriving their Skill
    share. Outcomes never change: at Reveal the total is the same sum the
    rule describes.
    """

    state = result.state
    if state.phase not in (
        GamePhase.ROUND_START,
        GamePhase.PLAYER_TURNS,
        GamePhase.COMBAT,
    ):
        return result
    players = list(state.players)
    for player in state.players:
        seat = player.player_id
        if (
            state.phase is not GamePhase.COMBAT
            and not player.has_revealed
            and not reveal_in_progress(state, seat)
        ):
            base = units_strength(player)
            if player.combat_strength != base or player.skill_strength_applied:
                players[seat] = replace(
                    player, combat_strength=base, skill_strength_applied=0
                )
        if not state.config.bloodlines:
            continue
        players[seat] = with_skill_strength(tuple(players), seat)
    next_players = tuple(players)
    if next_players == state.players:
        return result
    return replace(result, state=replace(state, players=next_players))
