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
    DeployFromGarrison,
    DestroyShieldWall,
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
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    Reward,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TrashPersonalCard,
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
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_factions,
)

type ChoiceSlot = (
    LoseInfluence
    | DiscardFromHand
    | RecallSpy
    | GainInfluence
    | DestroyShieldWall
    | DeployFromGarrison
    | TrashPersonalCard
    | PlaceSpy
)


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
    *,
    shield_wall_present: bool = True,
) -> tuple[EffectSection, ...]:
    """Return the sections whose conditions currently hold.

    A section that only offers the Shield Wall detonation icon has nothing to
    do once the token is gone, so it is not applicable then.
    """

    return tuple(
        section
        for section in option.sections
        if (section.condition is None or condition_holds(player, section.condition))
        and (
            shield_wall_present
            or not all(
                isinstance(reward, DestroyShieldWall) for reward in section.rewards
            )
        )
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


def choice_slots(
    sections: tuple[EffectSection, ...],
    *,
    shield_wall_present: bool = True,
) -> tuple[ChoiceSlot, ...]:
    """Return the ordered player choices the sections require.

    Cost choices across every section come first, then reward choices in
    printed order, each repeated once per step (``count`` or ``times``).
    """

    slots: list[ChoiceSlot] = []
    for section in sections:
        for cost in section.costs:
            if isinstance(cost, LoseInfluence | DiscardFromHand | RecallSpy):
                slots.extend([cost] * cost.count)
    for section in sections:
        for reward in section.rewards:
            match reward:
                case GainInfluence() if reward.requires_choice:
                    slots.extend([reward] * reward.times)
                case DestroyShieldWall() if shield_wall_present:
                    slots.append(reward)
                case DeployFromGarrison() | TrashPersonalCard() | PlaceSpy():
                    slots.append(reward)
                case _:
                    pass
    return tuple(slots)


def _choice_costs_feasible(
    player: PlayerState,
    sections: tuple[EffectSection, ...],
) -> bool:
    influence_needed = 0
    discards_needed = 0
    recalls_needed = 0
    for section in sections:
        for cost in section.costs:
            match cost:
                case LoseInfluence(count=count):
                    influence_needed += count
                case DiscardFromHand(count=count):
                    discards_needed += count
                case RecallSpy(count=count):
                    recalls_needed += count
                case _:
                    pass
    total_influence = sum(
        influence_amount(player.influence, faction) for faction in Faction
    )
    return (
        total_influence >= influence_needed
        and len(player.hand) >= discards_needed
        and len(player.spy_post_ids) >= recalls_needed
    )


def spy_placement_targets(
    state: GameState,
    player: int,
    reward: PlaceSpy,
) -> tuple[str, ...]:
    """Return the empty posts this placement may use."""

    allowed = (
        observation_post_ids_for_factions(reward.factions)
        if reward.factions is not None
        else None
    )
    return empty_observation_post_ids(state, allowed)


def spy_placement_possible(state: GameState, player: int, reward: PlaceSpy) -> bool:
    """A placement is possible now or after recalling one of the owner's Spies."""

    owner = state.players[player]
    if spy_placement_targets(state, player, reward):
        return owner.spies_supply > 0 or bool(owner.spy_post_ids)
    if owner.spies_supply > 0:
        return False
    allowed = (
        observation_post_ids_for_factions(reward.factions)
        if reward.factions is not None
        else None
    )
    # Recalling one of the owner's own Spies from an allowed post frees it.
    return any(allowed is None or post_id in allowed for post_id in owner.spy_post_ids)


def _choice_rewards_feasible(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
) -> bool:
    owner = state.players[player]
    for section in sections:
        for reward in section.rewards:
            match reward:
                case DeployFromGarrison() if owner.troops_garrison < 1:
                    return False
                case PlaceSpy() if not spy_placement_possible(state, player, reward):
                    return False
                case _:
                    pass
    return True


def option_is_playable(
    state: GameState,
    player: int,
    option: IntrigueOption,
) -> bool:
    """An option is playable when a section applies and every cost is payable."""

    owner = state.players[player]
    sections = applicable_sections(
        owner, option, shield_wall_present=state.shield_wall_present
    )
    return (
        bool(sections)
        and can_afford(owner, resource_cost(sections))
        and _choice_costs_feasible(owner, sections)
        and _choice_rewards_feasible(state, player, sections)
    )


@dataclass(frozen=True, slots=True)
class RewardOutcome:
    """Result of applying rewards plus data the caller may need to record."""

    result: RuleResult
    troops_recruited: int = 0
    sandworms_deployed: int = 0


def automatic_rewards(sections: tuple[EffectSection, ...]) -> tuple[Reward, ...]:
    """Return the rewards that resolve without a player choice."""

    return tuple(
        reward
        for section in sections
        for reward in section.rewards
        if not (isinstance(reward, GainInfluence) and reward.requires_choice)
        and not isinstance(
            reward,
            DestroyShieldWall | DeployFromGarrison | TrashPersonalCard | PlaceSpy,
        )
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
    sandworms_deployed = 0
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
            case SummonSandworm(count=count, requires_maker_hooks=needs_hooks):
                if (
                    (needs_hooks and not owner.maker_hooks)
                    or not state.current_conflict_ids
                    or current_conflict_is_shield_wall_protected(state)
                ):
                    # No effect against a Shield Wall-protected Conflict
                    # [Main p. 20] or without the required Maker Hooks.
                    events.append(
                        GameEvent(
                            event_id=f"{source}:sandworm_unavailable",
                            kind="sandworm_summon_unavailable",
                            payload=(("player", player),),
                        )
                    )
                else:
                    owner = replace(
                        owner, sandworms_conflict=owner.sandworms_conflict + count
                    )
                    sandworms_deployed += count
                    events.append(
                        GameEvent(
                            event_id=f"{source}:sandworm",
                            kind="sandworm_deployed",
                            payload=(("count", count), ("player", player)),
                        )
                    )
            case GainCombatStrength(amount=amount):
                # Combat Intrigue strength changes update the marker at once
                # [Main p. 14]; the caller only offers Combat options while
                # the player has units in the Conflict.
                owner = replace(owner, combat_strength=owner.combat_strength + amount)
                events.append(
                    GameEvent(
                        event_id=f"{source}:combat_strength",
                        kind="combat_strength_gained",
                        payload=(("amount", amount), ("player", player)),
                    )
                )
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
        # Resolved before the Intrigue card itself is discarded, so the deck
        # reshuffle (if any) never includes the card being played.
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
        sandworms_deployed=sandworms_deployed,
    )
