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

from copy import replace
from typing import Final

from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_STRENGTH,
    skill_for_instance,
)
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.effect_dsl import (
    AgentOnSpaceWithIcon,
    Condition,
    GainCombatStrength,
    InfluenceAtLeast,
    OpponentSandwormInConflict,
)
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.influence import influence_amount


def conflict_agent_strength(player: PlayerState) -> int:
    """Return the strength one of the seat's Conflict Agents fights with.

    Into the Fray: "You may take the Agent you sent this turn and deploy it
    to the Conflict as a 2 strength unit that can't be retreated. If you
    have your Swordmaster, it has 3 strength instead." [Duncan Idaho card]
    (docs/implementation-audits/leaders.md).
    """

    return 3 if player.swordmaster_acquired else 2


# A dreadnought in the Conflict is worth 3 strength [Rise of Ix p. 6]
# (docs/rules/rise-of-ix.md 6).
DREADNOUGHT_STRENGTH: Final = 3
# Prince Rhombur Vernius' Heavy Lasgun Cannons (Rise of Ix).
RHOMBUR_DREADNOUGHT_STRENGTH: Final = 4


def dreadnought_strength(player: PlayerState) -> int:
    """Return the strength one of the seat's Conflict dreadnoughts fights with.

    "Conflict의 dreadnought 하나는 strength 3(Prince Rhombur Vernius는 4)"
    [Rise of Ix p. 6] (docs/rules/rise-of-ix.md 6); "Heavy Lasgun Cannons:
    dreadnought strength 4" (rise-of-ix.md 10, stage P4e).
    """

    if player.leader_id == "prince_rhombur_vernius":
        return RHOMBUR_DREADNOUGHT_STRENGTH
    return DREADNOUGHT_STRENGTH


def units_strength(player: PlayerState) -> int:
    """Return the strength the units in the Conflict provide on their own.

    A troop is worth 2 and a sandworm 3 [Main p. 12], a Sardaukar Commander
    2 [Bloodlines p. 4], a dreadnought 3 (``dreadnought_strength``)
    [Rise of Ix p. 6], an Into the Fray Agent 2 or 3
    (``conflict_agent_strength``), and without a unit there is no strength
    at all, swords or not [Main p. 12]; a dreadnought is a unit, so one alone
    keeps its seat's strength above 0 [Rise of Ix p. 6] [FAQ p. 2].
    """

    if player.units_in_conflict <= 0:
        return 0
    return (
        player.troops_conflict * 2
        + player.sandworms_conflict * 3
        + player.commanders_conflict * COMMANDER_STRENGTH
        + player.dreadnoughts_conflict * dreadnought_strength(player)
        + player.agent_in_conflict * conflict_agent_strength(player)
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

    def holds(condition: Condition | None) -> bool:
        match condition:
            case None:
                return True
            case AgentOnSpaceWithIcon(icon=icon):
                return any(
                    BOARD_SPACES_BY_ID[space_id].agent_icon is icon
                    for space_id in owner.agent_locations
                    if space_id in BOARD_SPACES_BY_ID
                )
            case OpponentSandwormInConflict():
                return any(
                    candidate.sandworms_conflict > 0
                    for candidate in players
                    if candidate.player_id != player
                )
            case InfluenceAtLeast(faction=faction, amount=amount):
                return influence_amount(owner.influence, faction) >= amount
        raise ValueError(f"no Skill strength checks {condition!r}")

    total = 0
    for instance_id in owner.skill_ids:
        # The tile's strength lines are its record's (cleanup 2e), checked
        # on load (``sardaukar._skill``).
        ability = skill_for_instance(instance_id).ability
        if ability.timing is not AbilityTiming.IN_CONFLICT:
            continue
        for line in ability.sections:
            if holds(line.condition):
                total += sum(
                    reward.amount
                    for reward in line.rewards
                    if isinstance(reward, GainCombatStrength)
                )
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
    if state.phase is GamePhase.COMBAT and state.combat_end_triggers_offered:
        # The troops and Commanders went back to the supply after the
        # rewards (``combat.offer_conflict_end_triggers``); the strengths
        # stand as the rewards found them until the cleanup sets every
        # Combat marker to 0 [Main p. 14]. A sandworm still in the Conflict
        # would otherwise let a Skill's share drop with the Commander's
        # return [Bloodlines p. 4].
        return result
    players = list(state.players)
    stack = state.decision_stack
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
        before = players[seat].combat_strength
        players[seat] = with_skill_strength(tuple(players), seat)
        if players[seat].combat_strength != before:
            stack = _shift_reveal_strength(
                stack, seat, players[seat].combat_strength - before
            )
    next_players = tuple(players)
    if next_players == state.players and stack == state.decision_stack:
        return result
    return replace(
        result, state=replace(state, players=next_players, decision_stack=stack)
    )


def _shift_reveal_strength(
    stack: tuple[DecisionFrame, ...], player: int, amount: int
) -> tuple[DecisionFrame, ...]:
    """Move the seat's open Reveal total along with its Skill share.

    The Reveal frame's ``strength`` mirrors ``combat_strength`` while the
    Reveal runs; units that later enter after the seat had none are
    counted from it (``reveal_turn.add_units_to_reveal``). A Skill share
    that changed only ``combat_strength`` left the frame behind, so units
    leaving and coming back brought an old Canny, Fierce or Loyal share
    with them (engine audit 2026-10-22, R3): "Conflict에 유닛이 하나도 없으면
    sword가 있어도 strength는 0이다." [Main p. 12], and with no Commander in
    the Conflict a Skill gives no strength [Bloodlines p. 4] (OQ-032).
    """

    for index in range(len(stack) - 1, -1, -1):
        frame = stack[index]
        if not (
            frame.kind == FrameKind.REVEAL
            and isinstance(frame.decision, PlayerDecision)
            and frame.decision.owner == player
        ):
            continue
        context = dict(frame.context)
        strength = context.get("strength")
        if isinstance(strength, bool) or not isinstance(strength, int):
            raise RuntimeError("Reveal frame has invalid strength")
        context["strength"] = strength + amount
        return (
            *stack[:index],
            replace(frame, context=tuple(sorted(context.items()))),
            *stack[index + 1 :],
        )
    return stack
