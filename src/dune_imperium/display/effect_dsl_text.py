"""English text for the Intrigue effect DSL primitives.

Wording follows the shared display contract: short imperative fragments, no
trailing period, resources lowercase, game terms capitalized as printed.
Every per-primitive renderer is an exhaustive ``match`` over its DSL union so
``mypy`` fails the moment a new primitive is added without matching text
support.
"""

from typing import assert_never

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    CompletedContractsAtLeast,
    Condition,
    Cost,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FlipBattleCard,
    GainCombatStrength,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    HasHighCouncil,
    InfluenceAtLeast,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    OnRevealAcquisitionThisRound,
    OnUnitsDeployedInTurn,
    OpponentAllianceInfluenceAtLeast,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RetreatTroops,
    Reward,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TakeContract,
    TrashPersonalCard,
    Trigger,
)
from dune_imperium.content.uprising.intrigue import IntrigueCardEntry
from dune_imperium.content.uprising.types import BattleIcon

_FACTION_NAMES: dict[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "Spacing Guild",
    Faction.BENE_GESSERIT: "Bene Gesserit",
    Faction.FREMEN: "Fremen",
}

_BATTLE_ICON_NAMES: dict[BattleIcon, str] = {
    BattleIcon.CRYSKNIFE: "Crysknife",
    BattleIcon.DESERT_MOUSE: "Desert Mouse",
    BattleIcon.ORNITHOPTER: "Ornithopter",
    BattleIcon.WILD: "Wild",
}

_TIMING_LABELS: dict[IntrigueTiming, str] = {
    IntrigueTiming.PLOT: "Plot",
    IntrigueTiming.COMBAT: "Combat",
    IntrigueTiming.ENDGAME: "Endgame",
}


def _faction_name(faction: Faction) -> str:
    return _FACTION_NAMES[faction]


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _retreat_troops_text(troops: RetreatTroops) -> str:
    if troops.maximum is None:
        if troops.minimum == 1:
            return "Retreat any number of troops"
        return f"Retreat any number of troops (at least {troops.minimum})"
    if troops.minimum == troops.maximum:
        return f"Retreat {troops.minimum} {_plural(troops.minimum, 'troop')}"
    return f"Retreat {troops.minimum}-{troops.maximum} troops"


def _gain_influence_text(gain: GainInfluence) -> str:
    if gain.factions is not None and len(gain.factions) == 1:
        return f"Gain {gain.times} {_faction_name(gain.factions[0])} Influence"
    if gain.factions is None:
        choice = "any Faction"
    else:
        choice = " or ".join(_faction_name(faction) for faction in gain.factions)
    if gain.times == 1:
        return f"Gain 1 Influence (choose {choice})"
    suffix = ", distinct" if gain.distinct else ""
    return f"Gain {gain.times} Influence (choose {choice} each time{suffix})"


def _place_spy_text(spy: PlaceSpy) -> str:
    if spy.shared_post:
        return "Place a Spy (sharing another player's Spy's post)"
    if spy.factions is not None:
        names = " or ".join(_faction_name(faction) for faction in spy.factions)
        return f"Place a Spy ({names} Observation Post)"
    return "Place a Spy"


def condition_text(condition: Condition) -> str:
    """Render one Intrigue condition as a clause that follows "If "."""

    match condition:
        case InfluenceAtLeast(faction=faction, amount=amount):
            return f"you have {amount} or more {_faction_name(faction)} Influence"
        case HasHighCouncil():
            return "you hold a High Council seat"
        case SpiesPlacedAtLeast(count=count):
            return f"you have {count} or more Spies on Observation Posts"
        case CompletedContractsAtLeast(count=count):
            return f"you have completed {count} or more Contracts"
        case SandwormsInConflictAtLeast(count=1):
            return "there is a sandworm in the Conflict"
        case SandwormsInConflictAtLeast(count=count):
            return f"there are {count} or more sandworms in the Conflict"
        case GainedSpiceThisTurn(amount=amount):
            return f"you have gained {amount} or more spice this turn"
        case SpiceMustFlowCardsAtLeast(count=count):
            return f"you own {count} or more copies of The Spice Must Flow"
        case OpponentAllianceInfluenceAtLeast(amount=amount):
            return (
                f"you have {amount} or more Influence on a Faction track whose "
                "Alliance token an opponent holds"
            )
        case _:
            assert_never(condition)


def cost_text(cost: Cost) -> str:
    """Render one Intrigue cost."""

    match cost:
        case PayResources(solari=solari, spice=spice, water=water):
            parts = []
            if solari:
                parts.append(f"{solari} solari")
            if spice:
                parts.append(f"{spice} spice")
            if water:
                parts.append(f"{water} water")
            return "Pay " + ", ".join(parts)
        case LoseInfluence(count=count):
            return f"Lose {count} Influence"
        case DiscardFromHand(count=1):
            return "Discard a card"
        case DiscardFromHand(count=count):
            return f"Discard {count} cards"
        case RecallSpy(count=1):
            return "Recall a Spy"
        case RecallSpy(count=count):
            return f"Recall {count} Spies"
        case RetreatTroops() as troops:
            return _retreat_troops_text(troops)
        case FlipBattleCard(icon=icon):
            icon_name = _BATTLE_ICON_NAMES[icon]
            return f"Flip a won Conflict card ({icon_name} icon) face down"
        case _:
            assert_never(cost)


def reward_text(reward: Reward) -> str:
    """Render one Intrigue reward."""

    match reward:
        case GainResources(solari=solari, spice=spice, water=water):
            parts = []
            if solari:
                parts.append(f"{solari} solari")
            if spice:
                parts.append(f"{spice} spice")
            if water:
                parts.append(f"{water} water")
            return "Gain " + ", ".join(parts)
        case GainVictoryPoints(amount=amount):
            return f"Gain {amount} VP"
        case RecruitTroops(count=count):
            return f"Recruit {count} {_plural(count, 'troop')}"
        case DrawPersonalCards(count=count):
            return f"Draw {count} {_plural(count, 'card')}"
        case DrawIntrigueCards(count=count):
            return f"Draw {count} Intrigue {_plural(count, 'card')}"
        case GainCombatStrength(amount=amount):
            return f"Gain {amount} {_plural(amount, 'sword')}"
        case GainInfluence() as gain:
            return _gain_influence_text(gain)
        case DestroyShieldWall():
            return "Destroy the Shield Wall"
        case SummonSandworm(count=count, requires_maker_hooks=requires_maker_hooks):
            text = f"Summon {count} {_plural(count, 'sandworm')}"
            if requires_maker_hooks:
                text += " (Maker Hooks required)"
            return text
        case DeployFromGarrison(up_to=up_to):
            return f"Deploy {up_to} {_plural(up_to, 'troop')}"
        case TrashPersonalCard():
            return "Trash a card"
        case PlaceSpy() as spy:
            return _place_spy_text(spy)
        case RetreatTroops() as troops:
            return _retreat_troops_text(troops)
        case TakeContract(count=count):
            return f"Take {count} {_plural(count, 'Contract')}"
        case AcquireCardUpTo(max_cost=max_cost, to_hand_if=to_hand_if):
            if to_hand_if is None:
                return f"Acquire a card costing {max_cost} or less"
            return (
                f"Acquire a card costing {max_cost} or less "
                f"(to hand if {condition_text(to_hand_if)})"
            )
        case SetAsideImperiumRowCard(discount=discount):
            return (
                "Set aside an Imperium Row card "
                f"({discount} Persuasion off for you this round)"
            )
        case _:
            assert_never(reward)


def trigger_text(trigger: Trigger) -> str:
    """Render one Intrigue trigger as a clause introducing the option line."""

    match trigger:
        case OnRevealAcquisitionThisRound():
            return "Whenever you acquire a card during your Reveal turn this round"
        case OnUnitsDeployedInTurn(minimum=minimum):
            return f"When you deploy {minimum} or more units in a turn"
        case _:
            assert_never(trigger)


def section_text(section: EffectSection) -> str:
    """Render one printed Intrigue line: an optional condition, costs, rewards."""

    rewards = ", ".join(reward_text(reward) for reward in section.rewards)
    if section.costs:
        costs = ", ".join(cost_text(cost) for cost in section.costs)
        body = f"{costs} → {rewards}"
    else:
        body = rewards
    if section.condition is not None:
        return f"If {condition_text(section.condition)}: {body}"
    return body


def option_text(option: IntrigueOption) -> str:
    """Render one Intrigue option, prefixed by its timing.

    A triggered option (``option.trigger`` set) never resolves when played;
    its trigger clause introduces the sections that fire later instead.
    """

    prefix = f"{_TIMING_LABELS[option.timing]} — "
    body = "; ".join(section_text(section) for section in option.sections)
    if option.trigger is not None:
        return f"{prefix}{trigger_text(option.trigger)}: {body}"
    return f"{prefix}{body}"


def intrigue_card_text(entry: IntrigueCardEntry) -> list[str]:
    """Render one line of English text per printed Intrigue option."""

    return [option_text(option) for option in entry.options]
