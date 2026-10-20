"""Printed conditions that read the seat alone.

One place judges a DSL condition that depends only on the seat's own
public state, so every effect that prints it reads it alike: the effect
interpreter (``effect_interpreter.condition_holds``, an Intrigue card, a
Navigation card, a Tleilaxu card) and, since stage B3e-2 of
docs/stage-b-plan.md, a revealed card's Reveal lines (``reveal_turn``,
read off the card's ability record). A condition that needs more -- the
other seats, the card that prints it (a Faction Bond), the Reveal's
Persuasion (Command) -- is its caller's.
"""

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.effect_dsl import (
    CommandersInConflictAtLeast,
    CompletedContractsAtLeast,
    Condition,
    GainedSpiceThisTurn,
    GarrisonedUnitsAtLeast,
    GeneticMarkersAtLeast,
    HasAlliance,
    HasHighCouncil,
    HasSwordmaster,
    InfluenceAtLeast,
    InNavigationSlot,
    SandwormsInConflictAtLeast,
    SolariAtLeast,
    SpiceAtLeast,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SpyingOnMakerSpace,
    TechTilesAtLeast,
    TriggeredByFaction,
    UnitsDeployedThisTurnAtLeast,
    WaterAtLeast,
)
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.influence import influence_amount
from dune_imperium.rules.spy_placement import is_spying_on_maker_space


def owner_condition_holds(owner: PlayerState, condition: Condition) -> bool | None:
    """Whether ``condition`` holds for ``owner``, or None when it reads more
    than the seat (module docstring)."""

    match condition:
        case WaterAtLeast(amount=amount):
            return owner.resources.water >= amount
        case SolariAtLeast(amount=amount):
            return owner.resources.solari >= amount
        case SpiceAtLeast(amount=amount):
            return owner.resources.spice >= amount
        case CommandersInConflictAtLeast(count=count):
            return owner.commanders_conflict >= count
        case TechTilesAtLeast(count=count):
            return len(owner.tech_ids) >= count
        case GeneticMarkersAtLeast(count=count):
            return bool(owner.research_space) and (
                genetic_markers_reached(owner.research_space) >= count
            )
        case InfluenceAtLeast(faction=faction, amount=amount):
            return influence_amount(owner.influence, faction) >= amount
        case HasHighCouncil():
            return owner.high_council
        case HasAlliance(faction=None):
            return bool(owner.alliance_faction_ids)
        case HasAlliance(faction=faction) if faction is not None:
            return faction.value in owner.alliance_faction_ids
        case InNavigationSlot(slot=slot):
            return owner.navigation_active_slot == slot
        case TriggeredByFaction(faction=faction):
            return owner.navigation_trigger_faction == faction.value
        case SpiesPlacedAtLeast(count=count):
            return len(owner.spy_post_ids) >= count
        case CompletedContractsAtLeast(count=count):
            return len(owner.completed_contract_ids) >= count
        case SandwormsInConflictAtLeast(count=count):
            return owner.sandworms_conflict >= count
        case GainedSpiceThisTurn(amount=amount):
            gained = (
                owner.resources.spice
                - owner.spice_at_turn_start
                + owner.spice_spent_turn
            )
            return gained >= amount
        case UnitsDeployedThisTurnAtLeast(count=count):
            # "a moment in time when there are 3 units in the conflict that
            # were deployed to the conflict this turn, then that requirement
            # becomes true" (Message from designer): the turn's peak, which
            # a retreat leaves standing (OQ-016).
            return max(owner.units_deployed_turn, owner.units_deployed_peak) >= count
        case SpiceMustFlowCardsAtLeast(count=count):
            prefix = "reserve:the_spice_must_flow:"
            copies = sum(
                1
                for zone in (owner.deck, owner.hand, owner.discard_pile, owner.in_play)
                for instance_id in zone
                if instance_id.startswith(prefix)
            )
            return copies >= count
        # Stage B3e-2: a Reveal line's own conditions [card faces].
        case HasSwordmaster():
            return owner.swordmaster_acquired
        case GarrisonedUnitsAtLeast(count=count):
            # Imperial Throneship: "four or more garrisoned units", troops and
            # Commanders [Bloodlines p. 12].
            return owner.troops_garrison + owner.commanders_garrison >= count
        case SpyingOnMakerSpace():
            return is_spying_on_maker_space(owner)
    return None
