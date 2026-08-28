"""Interpreter for the composable effect DSL.

Conditions are pure predicates, costs are checked before anything changes, and
rewards are applied in printed order. Primitives that need a player choice
(``LoseInfluence``, ``DiscardFromHand``, multi-Faction ``GainInfluence``) are
exposed as ordered *choice slots* that the owning rule module resolves one
decision at a time; everything else is applied automatically.
"""

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    CompletedContractsAtLeast,
    Condition,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    HasHighCouncil,
    InfluenceAtLeast,
    IntrigueOption,
    LoseInfluence,
    PayResources,
    RecruitTroops,
    Reward,
    SpiesPlacedAtLeast,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.influence import gain_faction_influence, influence_amount
from dune_imperium.rules.intrigue_deck import draw_intrigue_cards

type ChoiceSlot = LoseInfluence | DiscardFromHand | GainInfluence


def condition_holds(player: PlayerState, condition: Condition) -> bool:
    """Evaluate one DSL condition against a player's public state."""

    match condition:
        case InfluenceAtLeast(faction=faction, amount=amount):
            return influence_amount(player.influence, faction) >= amount
        case HasHighCouncil():
            return player.high_council
        case SpiesPlacedAtLeast(count=count):
            return len(player.spy_post_ids) >= count
        case CompletedContractsAtLeast(count=count):
            return len(player.completed_contract_ids) >= count
    raise TypeError(f"unsupported condition: {condition!r}")


def applicable_sections(
    player: PlayerState,
    option: IntrigueOption,
) -> tuple[EffectSection, ...]:
    """Return the sections whose conditions currently hold."""

    return tuple(
        section
        for section in option.sections
        if section.condition is None or condition_holds(player, section.condition)
    )


def resource_cost(sections: tuple[EffectSection, ...]) -> PayResources | None:
    """Sum every automatic resource cost across ``sections``."""

    total: PayResources | None = None
    for section in sections:
        for cost in section.costs:
            if isinstance(cost, PayResources):
                total = cost if total is None else total + cost
    return total


def can_afford(player: PlayerState, cost: PayResources | None) -> bool:
    """Return whether the player can pay a resource ``cost`` right now."""

    if cost is None:
        return True
    resources = player.resources
    return (
        resources.solari >= cost.solari
        and resources.spice >= cost.spice
        and resources.water >= cost.water
    )


def pay_cost(player: PlayerState, cost: PayResources | None) -> PlayerState:
    """Return the player after paying ``cost``; raises if unaffordable."""

    if cost is None:
        return player
    if not can_afford(player, cost):
        raise ValueError("player cannot afford the required cost")
    resources = player.resources
    return replace(
        player,
        resources=replace(
            resources,
            solari=resources.solari - cost.solari,
            spice=resources.spice - cost.spice,
            water=resources.water - cost.water,
        ),
    )


def choice_slots(sections: tuple[EffectSection, ...]) -> tuple[ChoiceSlot, ...]:
    """Return the ordered player choices the sections require.

    Cost choices across every section come first, then reward choices, each
    repeated once per step (``count`` or ``times``).
    """

    slots: list[ChoiceSlot] = []
    for section in sections:
        for cost in section.costs:
            if isinstance(cost, LoseInfluence | DiscardFromHand):
                slots.extend([cost] * cost.count)
    for section in sections:
        for reward in section.rewards:
            if isinstance(reward, GainInfluence) and reward.requires_choice:
                slots.extend([reward] * reward.times)
    return tuple(slots)


def _choice_costs_feasible(
    player: PlayerState,
    sections: tuple[EffectSection, ...],
) -> bool:
    influence_needed = 0
    discards_needed = 0
    for section in sections:
        for cost in section.costs:
            match cost:
                case LoseInfluence(count=count):
                    influence_needed += count
                case DiscardFromHand(count=count):
                    discards_needed += count
                case _:
                    pass
    total_influence = sum(
        influence_amount(player.influence, faction) for faction in Faction
    )
    return total_influence >= influence_needed and len(player.hand) >= discards_needed


def option_is_playable(player: PlayerState, option: IntrigueOption) -> bool:
    """An option is playable when a section applies and every cost is payable."""

    sections = applicable_sections(player, option)
    return (
        bool(sections)
        and can_afford(player, resource_cost(sections))
        and _choice_costs_feasible(player, sections)
    )


@dataclass(frozen=True, slots=True)
class RewardOutcome:
    """Result of applying rewards plus data the caller may need to record."""

    result: RuleResult
    troops_recruited: int = 0


def automatic_rewards(sections: tuple[EffectSection, ...]) -> tuple[Reward, ...]:
    """Return the rewards that resolve without a player choice."""

    return tuple(
        reward
        for section in sections
        for reward in section.rewards
        if not (isinstance(reward, GainInfluence) and reward.requires_choice)
    )


def apply_rewards(
    state: GameState,
    player: int,
    rewards: tuple[Reward, ...],
    *,
    source: str,
) -> RewardOutcome:
    """Apply automatic ``rewards`` for ``player`` in printed order.

    Immediate gains resolve on the player first; personal and Intrigue draws
    are requested afterwards so any reshuffle chance frame sits on top.
    """

    owner = state.players[player]
    events: list[GameEvent] = []
    troops_recruited = 0
    personal_draws = 0
    intrigue_draws = 0
    fixed_influence: list[GainInfluence] = []
    for reward in rewards:
        match reward:
            case GainResources(solari=solari, spice=spice, water=water):
                owner = replace(
                    owner,
                    resources=replace(
                        owner.resources,
                        solari=owner.resources.solari + solari,
                        spice=owner.resources.spice + spice,
                        water=owner.resources.water + water,
                    ),
                )
            case GainVictoryPoints(amount=amount):
                owner = replace(owner, victory_points=owner.victory_points + amount)
                events.append(
                    GameEvent(
                        event_id=f"{source}:victory_points",
                        kind="victory_points_gained",
                        payload=(("amount", amount), ("player", player)),
                    )
                )
            case RecruitTroops(count=count):
                owner, recruited = recruit_troops(owner, count)
                troops_recruited += recruited
            case DrawPersonalCards(count=count):
                personal_draws += count
            case DrawIntrigueCards(count=count):
                intrigue_draws += count
            case GainInfluence() if not reward.requires_choice:
                fixed_influence.append(reward)
            case GainInfluence():
                raise ValueError("Influence choices must be resolved as choice slots")
            case GainCombatStrength():
                raise NotImplementedError("Combat strength rewards need Combat play")
            case _:
                raise TypeError(f"unsupported reward: {reward!r}")

    next_state = replace(state, players=replace_player(state.players, owner))
    for index, gain in enumerate(fixed_influence):
        assert gain.factions is not None
        faction = gain.factions[0]
        gained = gain_faction_influence(
            next_state,
            player,
            faction,
            gain.times,
            event_prefix=f"{source}:influence:{index}:{faction.value}",
        )
        next_state = gained.state
        events.extend(gained.events)
    if intrigue_draws:
        drawn = draw_intrigue_cards(
            next_state, player, intrigue_draws, source=f"{source}:intrigue"
        )
        next_state = drawn.state
        events.extend(drawn.events)
    if personal_draws:
        drawn = draw_or_request_personal_cards(
            next_state, player, personal_draws, source=f"{source}:draw"
        )
        next_state = drawn.state
        events.extend(drawn.events)
    return RewardOutcome(
        result=RuleResult(state=next_state, events=tuple(events)),
        troops_recruited=troops_recruited,
    )
