"""Interpreter for the composable effect DSL.

Conditions are pure predicates, costs are checked before anything changes, and
rewards are applied in printed order. Primitives that need a player choice
(``LoseInfluence``, ``DiscardFromHand``, multi-Faction ``GainInfluence``) are
exposed as ordered *choice slots* that the owning rule module resolves one
decision at a time; everything else is applied automatically.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireReserveCard,
    AcquireTech,
    AcquireTleilaxuCard,
    AdvanceTleilaxu,
    AllConditions,
    CommanderDiscountThisTurn,
    CommandersInConflictAtLeast,
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
    FlipFaceUpConflictCard,
    GainCombatStrength,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerUnitType,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    GiveIntrigueToOpponent,
    GrantAgentIconsThisTurn,
    GrantAgentIconThisTurn,
    GrantCombatDeployment,
    HasAlliance,
    HasHighCouncil,
    IgnoreInfluenceRequirementsThisTurn,
    InfluenceAtLeast,
    InNavigationSlot,
    IntrigueOption,
    LoseInfluence,
    LoseTroops,
    OpponentAllianceInfluenceAtLeast,
    OpponentPlayedCombatIntrigue,
    PassTurn,
    PayResources,
    PeekTopCard,
    PermanentRevealPersuasion,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RedirectSpiesOnTurnSpace,
    Research,
    RetreatTroops,
    RevealContractsTakeOne,
    RevealPersuasionThisRound,
    Reward,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    SolariAtLeast,
    SpiceAtLeast,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TakeContract,
    TechTilesAtLeast,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
    TriggeredByFaction,
    UnitsDeployedThisTurnAtLeast,
    WaterAtLeast,
)
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.contract_tiles import contract_reveal_is_possible
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    agent_turn_space_id,
    recruit_shortfall_events,
    recruit_troops,
)
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.immortality import advance_research, advance_tleilaxu
from dune_imperium.rules.influence import gain_faction_influence, influence_amount
from dune_imperium.rules.intrigue_deck import draw_intrigue_cards
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.ornithopter import has_ornithopter_fleet
from dune_imperium.rules.planetologist import replaces_sandworms
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.specimens import generate_specimens
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_agent_icons,
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
    | TrashDiscardPileCard
    | FlipFaceUpConflictCard
    | LoseTroops
    | GiveIntrigueToOpponent
    | TrashIntrigueCard
    | PeekTopCard
    | AcquireTleilaxuCard
)


def _battle_card_icon(card_id: str) -> BattleIcon | None:
    """The card's printed icon; ``None`` when it prints none (OQ-094)."""

    if card_id in OBJECTIVES_BY_ID:
        return OBJECTIVES_BY_ID[card_id].battle_icon
    return CONFLICTS_BY_ID[card_id].battle_icon


def face_up_conflict_card_ids(player: PlayerState) -> tuple[str, ...]:
    """Return the player's face-up Objective and won Conflict cards (any icon).

    Each Objective reads "This counts as a Conflict card you've already won."
    [Objective card], so every effect on won Conflict cards takes it too
    (OQ-005, user ruling 2026-10-04). Grasp Arrakis flips "face-up Conflict
    cards", not battle icons, so a card with no printed icon (Economic
    Supremacy) counts too (OQ-094 (e)).
    """

    face_down = set(player.face_down_battle_card_ids)
    return tuple(
        card_id
        for card_id in (*player.objective_ids, *player.won_conflict_ids)
        if card_id not in face_down
    )


def flippable_battle_card_ids(
    player: PlayerState,
    icon: BattleIcon,
) -> tuple[str, ...]:
    """Return the player's face-up won Conflict cards bearing ``icon`` or wild.

    An Objective counts as a Conflict card the player has already won
    [Objective card], so it is a target too (OQ-005, user ruling 2026-10-04).
    A card with no printed icon (Economic Supremacy) is never a target,
    Ornithopter Fleet or not (OQ-094 (b), (c)).
    """

    face_up = face_up_conflict_card_ids(player)
    if has_ornithopter_fleet(player):
        # Ornithopter Fleet: every icon is an Ornithopter, so "the Crysknife
        # and Desert Mouse Intrigue cards can't be used to gain a Victory
        # Point" [Bloodlines p. 12] while any Ornithopter flip may pick any
        # face-up card that has an icon to treat as one.
        if icon is not BattleIcon.ORNITHOPTER:
            return ()
        return tuple(
            card_id for card_id in face_up if _battle_card_icon(card_id) is not None
        )
    # A no-icon card's ``None`` is never ``icon`` or wild, so it never matches.
    return tuple(
        card_id
        for card_id in face_up
        if _battle_card_icon(card_id) in (icon, BattleIcon.WILD)
    )


def trashable_discard_pile_ids(
    player: PlayerState, minimum_cost: int
) -> tuple[str, ...]:
    """Return discard-pile cards printed with a cost of ``minimum_cost`` or more."""

    from dune_imperium.content.uprising.personal_cards import (
        personal_card_for_instance,
    )

    candidates: list[str] = []
    for card_id in player.discard_pile:
        cost = getattr(personal_card_for_instance(card_id), "acquisition_cost", None)
        if isinstance(cost, int) and cost >= minimum_cost:
            candidates.append(card_id)
    return tuple(candidates)


def condition_holds(state: GameState, player: int, condition: Condition) -> bool:
    """Evaluate one DSL condition against the public game state."""

    owner = state.players[player]
    match condition:
        case WaterAtLeast(amount=amount):
            return owner.resources.water >= amount
        case CommandersInConflictAtLeast(count=count):
            return owner.commanders_conflict >= count
        case TechTilesAtLeast(count=count):
            return len(owner.tech_ids) >= count
        case GeneticMarkersAtLeast(count=count):
            return bool(owner.research_space) and (
                genetic_markers_reached(owner.research_space) >= count
            )
        case SolariAtLeast(amount=amount):
            return owner.resources.solari >= amount
        case SpiceAtLeast(amount=amount):
            return owner.resources.spice >= amount
        case OpponentPlayedCombatIntrigue():
            return any(
                seat != player for seat in state.combat_intrigue_players
            )
        case AllConditions(conditions=conditions):
            return all(condition_holds(state, player, item) for item in conditions)
        case InfluenceAtLeast(faction=faction, amount=amount):
            return influence_amount(owner.influence, faction) >= amount
        case HasHighCouncil():
            return owner.high_council
        case HasAlliance():
            return bool(owner.alliance_faction_ids)
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
            return (
                max(owner.units_deployed_turn, owner.units_deployed_peak) >= count
            )
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
            if isinstance(
                cost, LoseInfluence | DiscardFromHand | RecallSpy | LoseTroops
            ):
                slots.extend([cost] * cost.count)
            elif isinstance(cost, GiveIntrigueToOpponent | TrashIntrigueCard):
                slots.append(cost)
            elif isinstance(
                cost, RetreatTroops | FlipBattleCard | TrashDiscardPileCard
            ):
                slots.append(cost)
            elif isinstance(cost, FlipFaceUpConflictCard):
                slots.extend([cost] * cost.count)
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
                    | PeekTopCard()
                    | AcquireTleilaxuCard()
                ):
                    slots.append(reward)
                case _:
                    pass
    return tuple(slots)


def _choice_cost_block(
    player: PlayerState,
    sections: tuple[EffectSection, ...],
) -> Cost | None:
    """Return a player-choice cost the owner cannot pay in full, or None.

    Costs of one kind add up across the sections; the one returned is the
    first printed cost of the first kind that falls short.
    """

    influence_needed = 0
    discards_needed = 0
    recalls_needed = 0
    retreats_needed = 0
    losses_needed = 0
    conflict_losses_needed = 0
    intrigue_needed = 0
    influence_cost: Cost | None = None
    discard_cost: Cost | None = None
    recall_cost: Cost | None = None
    retreat_cost: Cost | None = None
    loss_cost: Cost | None = None
    conflict_loss_cost: Cost | None = None
    intrigue_cost: Cost | None = None
    for section in sections:
        for cost in section.costs:
            match cost:
                case LoseInfluence(count=count):
                    influence_needed += count
                    if influence_cost is None:
                        influence_cost = cost
                case DiscardFromHand(count=count):
                    discards_needed += count
                    if discard_cost is None:
                        discard_cost = cost
                case LoseTroops(count=count, from_conflict=from_conflict):
                    losses_needed += count
                    if loss_cost is None:
                        loss_cost = cost
                    if from_conflict:
                        conflict_losses_needed += count
                        if conflict_loss_cost is None:
                            conflict_loss_cost = cost
                case GiveIntrigueToOpponent() | TrashIntrigueCard():
                    # The played card itself is still held while it resolves.
                    intrigue_needed += 1
                    if intrigue_cost is None:
                        intrigue_cost = cost
                case RecallSpy(count=count):
                    recalls_needed += count
                    if recall_cost is None:
                        recall_cost = cost
                case RetreatTroops(minimum=minimum):
                    retreats_needed += minimum
                    if retreat_cost is None:
                        retreat_cost = cost
                case FlipBattleCard(icon=icon) if not flippable_battle_card_ids(
                    player, icon
                ):
                    return cost
                case FlipFaceUpConflictCard(count=count) if (
                    len(face_up_conflict_card_ids(player)) < count
                ):
                    return cost
                case TrashDiscardPileCard(minimum_cost=minimum_cost) if (
                    not trashable_discard_pile_ids(player, minimum_cost)
                ):
                    return cost
                case _:
                    pass
    total_influence = sum(
        influence_amount(player.influence, faction) for faction in Faction
    )
    units = (
        player.troops_garrison
        + player.commanders_garrison
        + player.troops_conflict
        + player.commanders_conflict
    )
    in_conflict = player.troops_conflict + player.commanders_conflict
    if total_influence < influence_needed:
        return influence_cost
    if len(player.hand) < discards_needed:
        return discard_cost
    if len(player.spy_post_ids) < recalls_needed:
        return recall_cost
    if in_conflict < retreats_needed:
        return retreat_cost
    if units < losses_needed:
        return loss_cost
    if in_conflict < conflict_losses_needed:
        return conflict_loss_cost
    # The played card itself is still held while it resolves (a Navigation
    # card is not held at all, so it needs no allowance).
    if intrigue_needed and len(player.intrigue_cards) < intrigue_needed + 1:
        return intrigue_cost
    return None


def spy_placement_targets(
    state: GameState,
    player: int,
    reward: PlaceSpy,
) -> tuple[str, ...]:
    """Return the posts this placement may use: empty ones, by default.

    ``shared_post`` (Distraction): "You may place this Spy on the same
    observation post as another player's Spy" [Distraction card], so a post
    held only by opponents is allowed too -- the Spy with Deep Cover set:
    "you also have the option to ignore any opponents' Spies ... (You can't
    place the Spy where you already have a Spy of your own.)"
    [Bloodlines p. 5].
    """

    if reward.shared_post:
        own = set(state.players[player].spy_post_ids)
        return tuple(
            post.post_id for post in OBSERVATION_POSTS if post.post_id not in own
        )
    return empty_observation_post_ids(state, spy_placement_allowed_post_ids(reward))


def spy_placement_allowed_post_ids(reward: PlaceSpy) -> frozenset[str] | None:
    """Return the posts a limited placement may use; None when unlimited.

    "Some effects limit placement. For example: '[Spy] on [City]' means the
    observation post must connect to a [City] board space." [Main p. 20]
    """

    if reward.factions is not None:
        return observation_post_ids_for_factions(reward.factions)
    if reward.agent_icons is not None:
        return observation_post_ids_for_agent_icons(reward.agent_icons)
    return None


def spy_placement_possible(state: GameState, player: int, reward: PlaceSpy) -> bool:
    """A placement is possible now or after recalling one of the owner's Spies."""

    owner = state.players[player]
    if spy_placement_targets(state, player, reward):
        return owner.spies_supply > 0 or bool(owner.spy_post_ids)
    if owner.spies_supply > 0:
        return False
    allowed = spy_placement_allowed_post_ids(reward)
    # With an empty supply, one preparatory recall may free an allowed post,
    # but only when the owner's Spy is its sole occupant; a post shared with
    # another player's Spy stays occupied [Main pp. 11, 20].
    return bool(solo_occupied_post_ids(state, player, allowed))


def _choice_reward_block(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
) -> Reward | None:
    """Return the first reward that has nothing to act on now, or None."""

    owner = state.players[player]
    for section in sections:
        for reward in section.rewards:
            # DeployFromGarrison is never blocked: every card prints "Deploy
            # up to N troops", so zero is a legal choice, and "Intrigue 카드를
            # 플레이하려면 카드의 모든 조건을 충족하고 모든 비용을 지불해야
            # 한다. [FAQ p. 2]" (docs/rules/player-turns.md) makes no target
            # a play condition (OQ-057 (6)). The deployment limits still
            # shape the counts offered (``rules.intrigue``).
            match reward:
                case PlaceSpy() if not spy_placement_possible(state, player, reward):
                    return reward
                case RetreatTroops(minimum=minimum) if (
                    # An "any number" retreat may choose zero [Main p. 20]
                    # [FAQ p. 3], but stays playable only with a unit in the
                    # Conflict, as before (the Steam app offers Tactical
                    # Option's retreat the same way).
                    owner.troops_conflict + owner.commanders_conflict
                    < max(minimum, 1)
                ):
                    return reward
                case TakeContract() if not state.config.choam_module:
                    return reward
                case SetAsideImperiumRowCard() if not state.imperium_row:
                    return reward
                case PeekTopCard() if not owner.deck:
                    return reward
                case TrashPersonalCard(mandatory=True, hand_only=True) if (
                    not owner.hand
                ):
                    return reward
                case GainInfluence(where_opponent_leads=True) if not (
                    factions_where_opponent_leads(state, player)
                ):
                    return reward
                case GainInfluence() as gain if (
                    gain.different_from_trigger or gain.minimum_own
                ) and not influence_gain_candidates(state, player, gain):
                    return reward
                case RedirectSpiesOnTurnSpace() if (
                    agent_turn_space_id(state, player) is None
                ):
                    # "the board space where you sent an Agent this turn":
                    # only after this turn's placement.
                    return reward
                case _:
                    pass
    return None


def influence_gain_candidates(
    state: GameState,
    player: int,
    gain: GainInfluence,
) -> tuple[Faction, ...]:
    """Factions a GainInfluence choice may pick, after its printed limits."""

    owner = state.players[player]
    candidates = gain.factions if gain.factions is not None else tuple(Faction)
    if gain.where_opponent_leads:
        leading = factions_where_opponent_leads(state, player)
        candidates = tuple(f for f in candidates if f in leading)
    if gain.different_from_trigger:
        candidates = tuple(
            f for f in candidates if f.value != owner.navigation_trigger_faction
        )
    if gain.minimum_own:
        candidates = tuple(
            f
            for f in candidates
            if influence_amount(owner.influence, f) >= gain.minimum_own
        )
    return candidates


def factions_where_opponent_leads(
    state: GameState,
    player: int,
) -> tuple[Faction, ...]:
    """Factions where some opponent has more Influence than ``player``."""

    own = state.players[player].influence
    return tuple(
        faction
        for faction in Faction
        if any(
            influence_amount(seat.influence, faction) > influence_amount(own, faction)
            for seat in state.players
            if seat.player_id != player
        )
    )


def section_is_usable(
    state: GameState,
    player: int,
    section: EffectSection,
) -> bool:
    """A separate printed line is usable when it applies and its cost is payable now."""

    owner = state.players[player]
    if section.condition is not None and not condition_holds(
        state, player, section.condition
    ):
        return False
    if not state.shield_wall_present and all(
        isinstance(reward, DestroyShieldWall) for reward in section.rewards
    ):
        return False
    sections = (section,)
    return (
        can_afford(owner, resource_cost(sections))
        and _choice_cost_block(owner, sections) is None
        and _choice_reward_block(state, player, sections) is None
    )


class OptionBlock(StrEnum):
    """Why an Intrigue option cannot be played, beyond a named cost or reward.

    ``option_unplayable_reason`` returns one of these, or the printed cost or
    reward that fails; ``option_is_playable`` is its ``is None``, so the
    page's reason for a greyed-out Intrigue card (``display.unavailable``,
    user request 2026-09-29) reads the very check the legal list does.
    """

    CONDITION = "condition"  # no printed section applies now
    COST = "cost"  # the resource cost is more than the owner holds
    NO_LINE = "no_line"  # separate printed lines: none usable now (OQ-058)
    CONTRACT_BANK = "contract_bank"  # too few Contracts to reveal (OQ-064)


type OptionUnplayable = OptionBlock | Cost | Reward


def option_is_playable(
    state: GameState,
    player: int,
    option: IntrigueOption,
) -> bool:
    """An option is playable when a section applies and every cost is payable.

    Separate printed lines (``separate``) make the card playable as soon as
    one line is usable; each line is paid when it is used (OQ-058).
    """

    return option_unplayable_reason(state, player, option) is None


def option_unplayable_reason(
    state: GameState,
    player: int,
    option: IntrigueOption,
) -> OptionUnplayable | None:
    """Why ``option`` cannot be played now, or None when it can.

    The checks, in order: a separate-lines card needs one usable line; a
    triggered card needs an applicable section; any other needs an
    applicable section, the Contracts Coercive Negotiation reveals, its
    resource cost, then each player-choice cost and reward
    (``_choice_cost_block``, ``_choice_reward_block``).
    """

    owner = state.players[player]
    if option.separate and option.trigger is None:
        if any(
            section_is_usable(state, player, section) for section in option.sections
        ):
            return None
        return OptionBlock.NO_LINE
    sections = applicable_sections(
        state, player, option, shield_wall_present=state.shield_wall_present
    )
    if not sections:
        return OptionBlock.CONDITION
    if option.trigger is not None:
        # Playing only sets the card waiting face up; its rewards resolve
        # when the trigger fires, so present feasibility does not gate it.
        return None
    if not all(
        contract_reveal_is_possible(state, reward)
        for section in sections
        for reward in section.rewards
        if isinstance(reward, RevealContractsTakeOne)
    ):
        # Coercive Negotiation's "Reveal three contracts from the bank"
        # [Coercive Negotiation card]: nothing refills the bank, so with
        # fewer than three there the card cannot be used at all, not used
        # for no effect (OQ-064, user ruling 2026-09-26).
        return OptionBlock.CONTRACT_BANK
    if not can_afford(owner, resource_cost(sections)):
        return OptionBlock.COST
    cost = _choice_cost_block(owner, sections)
    if cost is not None:
        return cost
    return _choice_reward_block(state, player, sections)


@dataclass(frozen=True, slots=True)
class RewardOutcome:
    """Result of applying rewards plus data the caller may need to record."""

    result: RuleResult
    troops_recruited: int = 0
    sandworms_deployed: int = 0
    combat_icons: int = 0
    redirects_turn_space_spies: bool = False
    sandworms_replaced: int = 0
    passes_turn: bool = False
    reserve_acquisitions: tuple[str, ...] = ()
    # Acquire Tech icons to open, one discount per icon (Tech Module).
    tech_acquisitions: tuple[int, ...] = ()


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
            | SetAsideImperiumRowCard
            | PeekTopCard
            | AcquireTleilaxuCard
            | RevealContractsTakeOne,
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
    combat_icons = 0
    redirects_turn_space_spies = False
    sandworms_replaced = 0
    passes_turn = False
    reserve_acquisitions: list[str] = []
    tech_acquisitions: list[int] = []
    personal_draws = 0
    intrigue_draws = 0
    contracts = 0
    fixed_influence: list[GainInfluence] = []
    # Immortality: Bene Tleilax board moves resolve on the state after the
    # resource gains (a research advance may open a direction choice).
    specimens = 0
    tleilaxu_advances = 0
    researches = 0
    for reward in rewards:
        match reward:
            case Research():
                researches += 1
            case AdvanceTleilaxu(count=count):
                tleilaxu_advances += count
            case GenerateSpecimens(count=count):
                specimens += count
            case RevealPersuasionThisRound(amount=amount):
                owner = replace(
                    owner,
                    reveal_persuasion_round_bonus=(
                        owner.reveal_persuasion_round_bonus + amount
                    ),
                )
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
                events.extend(
                    recruit_shortfall_events(
                        f"{source}:recruit", player, count, recruited
                    )
                )
            case DrawPersonalCards(count=count):
                personal_draws += count
            case DrawIntrigueCards(count=count):
                intrigue_draws += count
            case GainInfluence() if not reward.requires_choice:
                fixed_influence.append(reward)
            case GainInfluence():
                raise ValueError("Influence choices must be resolved as choice slots")
            case SummonSandworm(count=count, requires_maker_hooks=needs_hooks) if (
                replaces_sandworms(owner)
                and not (needs_hooks and not owner.maker_hooks)
                and state.current_conflict_ids
                and not units_deployment_blocked(state, player)
            ):
                # Arrakis Planetologist: the replacement, even under the
                # Shield Wall [Liet Kynes card]; paid by the caller.
                sandworms_replaced += count
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
            case CommanderDiscountThisTurn(amount=amount):
                # Honor Guard: the discount lasts for the rest of the turn.
                owner = replace(
                    owner,
                    commander_discount_turn=owner.commander_discount_turn + amount,
                )
            case IgnoreInfluenceRequirementsThisTurn():
                owner = replace(owner, ignores_influence_requirements_turn=True)
            case GrantAgentIconThisTurn(icon=icon):
                owner = replace(owner, granted_agent_icon_turn=icon.value)
            case GrantAgentIconsThisTurn(icons=icons):
                # Resourceful: several icons at once, comma-joined.
                granted = [
                    value for value in owner.granted_agent_icon_turn.split(",") if value
                ]
                granted.extend(
                    icon.value for icon in icons if icon.value not in granted
                )
                owner = replace(owner, granted_agent_icon_turn=",".join(granted))
            case GainSolariPerUnitType():
                # Calculating: troops, sandworms, Commanders and a fighting
                # Agent are each a kind of unit.
                kinds = sum(
                    (
                        owner.troops_conflict > 0,
                        owner.sandworms_conflict > 0,
                        owner.commanders_conflict > 0,
                        owner.agent_in_conflict > 0,
                    )
                )
                owner = replace(
                    owner,
                    resources=replace(
                        owner.resources, solari=owner.resources.solari + kinds
                    ),
                )
            case PassTurn():
                passes_turn = True
            case PermanentRevealPersuasion(amount=amount):
                owner = replace(
                    owner,
                    reveal_persuasion_bonus=owner.reveal_persuasion_bonus + amount,
                )
            case AcquireReserveCard(card_id=card_id):
                reserve_acquisitions.append(card_id)
            case AcquireTech(discount=discount):
                tech_acquisitions.append(discount)
            case GrantCombatDeployment():
                combat_icons += 1
            case RedirectSpiesOnTurnSpace():
                redirects_turn_space_spies = True
            case RevealContractsTakeOne():
                raise ValueError(
                    "Contract reveals open their own frame once the card is "
                    "discarded (finish_intrigue_play)"
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
    if specimens:
        generated = generate_specimens(
            next_state, player, specimens, source=f"{source}:specimens"
        )
        next_state = generated.state
        events.extend(generated.events)
    if tleilaxu_advances:
        advanced = advance_tleilaxu(
            next_state, player, tleilaxu_advances, source=f"{source}:tleilaxu"
        )
        next_state = advanced.state
        events.extend(advanced.events)
    for index in range(researches):
        researched = advance_research(
            next_state, player, source=f"{source}:research:{index}"
        )
        next_state = researched.state
        events.extend(researched.events)
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
        combat_icons=combat_icons,
        redirects_turn_space_spies=redirects_turn_space_spies,
        sandworms_replaced=sandworms_replaced,
        passes_turn=passes_turn,
        reserve_acquisitions=tuple(reserve_acquisitions),
        tech_acquisitions=tuple(tech_acquisitions),
    )
