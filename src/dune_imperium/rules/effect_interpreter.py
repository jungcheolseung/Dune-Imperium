"""Interpreter for the composable effect DSL.

Conditions are pure predicates, costs are checked before anything changes, and
rewards are applied in printed order. Primitives that need a player choice
(``LoseInfluence``, ``DiscardFromHand``, multi-Faction ``GainInfluence``) are
exposed as ordered *choice slots* that the owning rule module resolves one
decision at a time; everything else is applied automatically.
"""

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    CompletedContractsAtLeast,
    Condition,
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
    LoseInfluence,
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
)
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import (
    acquirable_imperium_instance_ids,
    acquirable_reserve_card_ids,
)
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.influence import gain_faction_influence, influence_amount
from dune_imperium.rules.intrigue_deck import draw_intrigue_cards
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_factions,
    solo_occupied_post_ids,
)

type ChoiceSlot = (
    LoseInfluence
    | DiscardFromHand
    | RecallSpy
    | RetreatTroops
    | GainInfluence
    | DestroyShieldWall
    | DeployFromGarrison
    | TrashPersonalCard
    | PlaceSpy
    | AcquireCardUpTo
    | FlipBattleCard
    | SetAsideImperiumRowCard
)


def flippable_battle_card_ids(
    player: PlayerState,
    icon: BattleIcon,
    wild_icon_conflict_ids: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return the player's face-up won Conflict cards bearing ``icon`` or wild.

    Objective cards are not valid targets for a printed flip effect. A won
    Conflict that carries Pivotal Gambit's pledged wild icon
    (``wild_icon_conflict_ids``) bears a wild icon as well (OQ-025).
    """

    face_down = set(player.face_down_battle_card_ids)
    return tuple(
        card_id
        for card_id in player.won_conflict_ids
        if card_id not in face_down
        and (
            CONFLICTS_BY_ID[card_id].battle_icon in (icon, BattleIcon.WILD)
            or card_id in wild_icon_conflict_ids
        )
    )


def condition_holds(state: GameState, player: int, condition: Condition) -> bool:
    """Evaluate one DSL condition against the public game state."""

    owner = state.players[player]
    match condition:
        case InfluenceAtLeast(faction=faction, amount=amount):
            return influence_amount(owner.influence, faction) >= amount
        case HasHighCouncil():
            return owner.high_council
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
        case SpiceMustFlowCardsAtLeast(count=count):
            prefix = "reserve:the_spice_must_flow:"
            copies = sum(
                1
                for zone in (owner.deck, owner.hand, owner.discard_pile, owner.in_play)
                for instance_id in zone
                if instance_id.startswith(prefix)
            )
            return copies >= count
        case OpponentAllianceInfluenceAtLeast(amount=amount):
            return any(
                influence_amount(owner.influence, faction) >= amount
                and any(
                    faction.value in candidate.alliance_faction_ids
                    for candidate in state.players
                    if candidate.player_id != player
                )
                for faction in Faction
            )
    raise TypeError(f"unsupported condition: {condition!r}")


def applicable_sections(
    state: GameState,
    player: int,
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
        if (
            section.condition is None
            or condition_holds(state, player, section.condition)
        )
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
        spice_spent_turn=player.spice_spent_turn + cost.spice,
    )


def cost_slots(sections: tuple[EffectSection, ...]) -> tuple[ChoiceSlot, ...]:
    """Return the player-choice cost payments across every section."""

    slots: list[ChoiceSlot] = []
    for section in sections:
        for cost in section.costs:
            if isinstance(cost, LoseInfluence | DiscardFromHand | RecallSpy):
                slots.extend([cost] * cost.count)
            elif isinstance(cost, RetreatTroops | FlipBattleCard):
                slots.append(cost)
    return tuple(slots)


def choice_slots(
    sections: tuple[EffectSection, ...],
    *,
    shield_wall_present: bool = True,
) -> tuple[ChoiceSlot, ...]:
    """Return the ordered player choices the sections require.

    Cost choices across every section come first, then reward choices in
    printed order, each repeated once per step (``count`` or ``times``).
    """

    slots: list[ChoiceSlot] = list(cost_slots(sections))
    for section in sections:
        for reward in section.rewards:
            match reward:
                case GainInfluence() if reward.requires_choice:
                    slots.extend([reward] * reward.times)
                case DestroyShieldWall() if shield_wall_present:
                    slots.append(reward)
                case (
                    DeployFromGarrison()
                    | TrashPersonalCard()
                    | PlaceSpy()
                    | RetreatTroops()
                    | AcquireCardUpTo()
                    | SetAsideImperiumRowCard()
                ):
                    slots.append(reward)
                case _:
                    pass
    return tuple(slots)


def _choice_costs_feasible(
    player: PlayerState,
    sections: tuple[EffectSection, ...],
    wild_icon_conflict_ids: tuple[str, ...] = (),
) -> bool:
    influence_needed = 0
    discards_needed = 0
    recalls_needed = 0
    retreats_needed = 0
    for section in sections:
        for cost in section.costs:
            match cost:
                case LoseInfluence(count=count):
                    influence_needed += count
                case DiscardFromHand(count=count):
                    discards_needed += count
                case RecallSpy(count=count):
                    recalls_needed += count
                case RetreatTroops(minimum=minimum):
                    retreats_needed += minimum
                case FlipBattleCard(icon=icon) if not flippable_battle_card_ids(
                    player, icon, wild_icon_conflict_ids
                ):
                    return False
                case _:
                    pass
    total_influence = sum(
        influence_amount(player.influence, faction) for faction in Faction
    )
    return (
        total_influence >= influence_needed
        and len(player.hand) >= discards_needed
        and len(player.spy_post_ids) >= recalls_needed
        and player.troops_conflict >= retreats_needed
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
    # With an empty supply, one preparatory recall may free an allowed post,
    # but only when the owner's Spy is its sole occupant; a post shared with
    # another player's Spy stays occupied [Main pp. 11, 20].
    return bool(solo_occupied_post_ids(state, player, allowed))


def _choice_rewards_feasible(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
) -> bool:
    owner = state.players[player]
    for section in sections:
        for reward in section.rewards:
            match reward:
                case DeployFromGarrison() if (
                    owner.troops_garrison < 1
                    or units_deployment_blocked(state, player)
                ):
                    return False
                case PlaceSpy() if not spy_placement_possible(state, player, reward):
                    return False
                case RetreatTroops(minimum=minimum) if owner.troops_conflict < minimum:
                    return False
                case TakeContract() if not state.config.choam_module:
                    return False
                case AcquireCardUpTo(max_cost=max_cost) if not (
                    acquirable_reserve_card_ids(state, max_cost)
                    or acquirable_imperium_instance_ids(state, max_cost)
                ):
                    return False
                case SetAsideImperiumRowCard() if not state.imperium_row:
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
        state, player, option, shield_wall_present=state.shield_wall_present
    )
    if option.trigger is not None:
        # Playing only sets the card waiting face up; its rewards resolve
        # when the trigger fires, so present feasibility does not gate it.
        return bool(sections)
    return (
        bool(sections)
        and can_afford(owner, resource_cost(sections))
        and _choice_costs_feasible(owner, sections, state.wild_icon_conflict_ids)
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
            DestroyShieldWall
            | DeployFromGarrison
            | TrashPersonalCard
            | PlaceSpy
            | RetreatTroops
            | AcquireCardUpTo
            | SetAsideImperiumRowCard,
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
    contracts = 0
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
                    or units_deployment_blocked(state, player)
                ):
                    # No effect against a Shield Wall-protected Conflict
                    # [Main p. 20], without the required Maker Hooks, or
                    # while Emperor of the Known Universe blocks deployment
                    # for this turn [Main p. 17].
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
            case TakeContract(count=count):
                contracts += count
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
    if contracts:
        taken = begin_contract_gain(
            next_state, player, contracts, source=f"{source}:contract"
        )
        next_state = taken.state
        events.extend(taken.events)
    return RewardOutcome(
        result=RuleResult(state=next_state, events=tuple(events)),
        troops_recruited=troops_recruited,
        sandworms_deployed=sandworms_deployed,
    )
