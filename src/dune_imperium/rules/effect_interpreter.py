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
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.contracts import contract_for_instance
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
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    OnRevealAcquisitionThisRound,
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
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_INSTANCE,
    is_twisted_intrigue,
)
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.combat_deployment import undeployable_troops_this_turn
from dune_imperium.rules.contract_tiles import contract_reveal_is_possible
from dune_imperium.rules.contracts import (
    begin_contract_gain,
    contract_gain_opens_market,
    market_contract_ids,
)
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    agent_turn_space_id,
    board_icon_is_pending,
    recruit_shortfall_events,
    recruit_troops,
)
from dune_imperium.rules.frames import FrameKind, replace_player
from dune_imperium.rules.immortality import (
    advance_research,
    advance_tleilaxu,
    tleilaxu_track_finished,
)
from dune_imperium.rules.influence import (
    gain_faction_influence,
    influence_amount,
    influence_can_rise,
)
from dune_imperium.rules.intrigue_deck import (
    draw_intrigue_cards,
    shufflable_intrigue_discard,
)
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.ornithopter import has_ornithopter_fleet
from dune_imperium.rules.planetologist import replaces_sandworms
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.specimens import generate_specimens
from dune_imperium.rules.spies import gather_intelligence_draw_available
from dune_imperium.rules.spy_moves import connected_post_ids
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
    """A placement is possible now or after recalling one of the owner's Spies.

    With an empty supply and no free allowed post, the recall must free a
    post the owner's Spy holds alone. Once a Spy was already recalled this
    turn, recalling it and placing it back on the same post changes nothing,
    so that placement is not possible (OQ-101 (b): before any recall this
    turn the counter's 0 -> 1 is the change and the play stays offered;
    "To play an Intrigue card, you must meet its conditions and pay its
    costs." [FAQ p. 2] with the user's ruling of 2026-10-06 that an
    Intrigue option needs an effect that can change something).
    """

    owner = state.players[player]
    if spy_placement_targets(state, player, reward):
        return owner.spies_supply > 0 or bool(owner.spy_post_ids)
    if owner.spies_supply > 0:
        return False
    allowed = spy_placement_allowed_post_ids(reward)
    # With an empty supply, one preparatory recall may free an allowed post,
    # but only when the owner's Spy is its sole occupant; a post shared with
    # another player's Spy stays occupied [Main pp. 11, 20].
    return (
        bool(solo_occupied_post_ids(state, player, allowed))
        and owner.spies_recalled_turn == 0
    )


def deployable_garrison_units(state: GameState, player: int) -> tuple[int, int]:
    """(troops, Commanders) a "deploy from your garrison" effect may move now.

    A Sardaukar Commander in the garrison is a troop for this purpose
    [Bloodlines p. 4]. Harkonnen Advisor's troop is not available this turn
    (OQ-038), and Emperor of the Known Universe blocks every unit for the
    turn [Main p. 17]. The Intrigue deploy slot offers exactly these counts
    (``rules.intrigue``), and the play gate reads the same pair, so the two
    cannot drift.
    """

    if units_deployment_blocked(state, player):
        return 0, 0
    owner = state.players[player]
    return (
        max(owner.troops_garrison - undeployable_troops_this_turn(state, player), 0),
        owner.commanders_garrison,
    )


def _plot_frame(state: GameState, player: int) -> DecisionFrame | None:
    """The owner's own turn frame on top (turn, Agent effects or Reveal).

    None in a Navigation choice, a Combat or Endgame window, or any other
    frame; no reward that reads the turn appears on the cards played there.
    """

    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if (
        frame.kind in (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == player
    ):
        return frame
    return None


def agent_placement_ahead(state: GameState, player: int) -> bool:
    """The owner can still send an Agent this turn: its turn frame is on top
    before the Agent or Reveal choice, with an Agent and a card to play."""

    frame = _plot_frame(state, player)
    owner = state.players[player]
    return (
        frame is not None
        and frame.kind == FrameKind.TURN
        and owner.agents_available > 0
        and bool(owner.hand)
    )


def _troop_can_join(state: GameState, owner: PlayerState) -> bool:
    """Whether a recruit can take a troop for ``owner`` now.

    A troop in the supply, or under Immortality a specimen the owner may
    return to the supply first ("You may return any of your specimens to
    your supply at any time. (This could be useful if you need to recruit
    troops but have no more in your supply.)" [Immortality p. 8]). A
    shortfall the engine records and may fill later in the turn (OQ-030
    re-ruling 2026-10-04) does not count, in a player turn or out of one:
    the user's ruling of 2026-10-06 that an Intrigue option with no effect
    cannot be played ("아무 효과 없이 책략을 쓸 수 없는거지"), read as the
    Arrakeen Scouts recruit already is (``scouts_effects.reward_has_effect``,
    OQ-071).
    """

    return owner.troops_supply >= 1 or (
        state.config.immortality and owner.specimens > 0
    )


def _paid_commander_ahead(state: GameState, player: int, frame: DecisionFrame) -> bool:
    """A Commander may still be bought for Solari in the owner's turn.

    "자신의 turn에 Sardaukar Commander가 있는 board space에 Agent를
    보내면, 2 Solari를 지불해 그 Commander를 acquire하고 즉시 recruit할 수
    있다." and "turn(Agent 또는 Reveal)마다 한 번, 2 Solari를 지불해
    supply의 Commander 하나를 garrison으로 ... recruit할 수 있다."
    [Bloodlines p. 4] (docs/rules/bloodlines.md 3): the once-per-turn recruit
    from the supply, the Commander waiting on the space this Agent visits
    (its icon is queued only while the token is there, ``board_effects``),
    or, before the placement, a Commander token still on some board space
    to visit. With no token left and the paid recruit used or the supply
    empty, no Commander can be bought this turn.
    """

    owner = state.players[player]
    recruit_left = owner.commanders_supply > 0 and not owner.commander_recruited_turn
    if frame.kind == FrameKind.REVEAL:
        return recruit_left
    if frame.kind == FrameKind.AGENT_EFFECTS:
        return recruit_left or board_icon_is_pending(
            dict(frame.context), BOARD_ICON_COMMANDER
        )
    return recruit_left or (
        owner.agents_available > 0 and bool(state.sardaukar_commander_space_ids)
    )


def _commander_purchase_ahead(state: GameState, player: int) -> bool:
    """Honor Guard's discount can still lower a paid Commander this turn."""

    from dune_imperium.rules.sardaukar import commander_cost

    frame = _plot_frame(state, player)
    if frame is None or commander_cost(state.players[player]) <= 0:
        return False
    return _paid_commander_ahead(state, player, frame)


def _combat_deployment_ahead(state: GameState, player: int) -> bool:
    """Adaptive Tactics' Combat icon could still let a unit deploy this turn.

    The icon opens the Agent turn's deployment window (with up to two
    garrison units) or the Reveal turn's, or waits on the seat for the
    placement [Bloodlines p. 5] (``combat_deployment.grant_combat_icon``).
    The icon deploys "이번 turn에 recruit한 유닛 전부와 garrison에서 최대
    두 개" [Bloodlines pp. 5, 12] (docs/rules/bloodlines.md 4), so a
    deployable garrison unit counts, and so does a Commander still to be
    bought this turn (``_paid_commander_ahead``): it is recruited to the
    garrison and joins the window the icon opens.
    """

    if units_deployment_blocked(state, player):
        return False
    frame = _plot_frame(state, player)
    if frame is None:
        return False
    owner = state.players[player]
    unit_ahead = sum(
        deployable_garrison_units(state, player)
    ) >= 1 or _paid_commander_ahead(state, player, frame)
    context = dict(frame.context)
    if frame.kind == FrameKind.AGENT_EFFECTS:
        limit = context.get("existing_troop_deployment_limit", 0)
        already_open = (
            context.get("pending_combat_deployment") is True
            and isinstance(limit, int)
            and limit >= 2
        )
        return not already_open and unit_ahead
    if frame.kind == FrameKind.REVEAL:
        return context.get("combat_deployment") is not True and unit_ahead
    return not owner.combat_icon_turn and (unit_ahead or owner.troops_supply >= 1)


def _unmet_influence_requirement(state: GameState, player: int) -> bool:
    """Some board space on the table bars the owner by an unmet, unwaived
    Influence requirement (``agent_turn.influence_requirement_unmet``)."""

    from dune_imperium.rules.agent_turn import influence_requirement_unmet

    owner = state.players[player]
    return any(
        influence_requirement_unmet(state, owner, space)
        for space in BOARD_SPACES
        # Tuek's Sietch is on the table only with Esmar Tuek.
        if space.required_leader_id is None
        or any(seat.leader_id == space.required_leader_id for seat in state.players)
    )


def _contract_can_be_taken(state: GameState, player: int) -> bool:
    """A Contract icon of ``player`` can change something now (CHOAM on).

    With the market exhausted the icon becomes 2 Solari [Main p. 16]
    (``contracts.begin_contract_gain``). Otherwise a token other than the
    Bloodlines Immediate (Shaddam's set-aside Sardaukar Contracts included)
    can be taken, or the Immediate can, with another Intrigue card to trash:
    "You can't take the new Immediate contract unless you have an Intrigue
    card to trash." [Bloodlines p. 2]. The played Intrigue card is still
    held while this is judged and leaves the hand before the choice, so a
    second card is needed.
    """

    if not contract_gain_opens_market(state, player):
        return True
    if any(
        not contract_for_instance(instance_id).requires_intrigue_trash
        for instance_id in market_contract_ids(state, player)
    ):
        return True
    return len(state.players[player].intrigue_cards) >= 2


def _redirect_has_target(state: GameState, player: int) -> bool:
    """False Orders can move an opponent's Spy or place the owner's own.

    Judged before the moves: an opponent's Spy on a post connected to this
    turn's board space (one that has nowhere to go is lost, which still
    changes something, OQ-065), or an empty connected post for the
    owner's placement.
    """

    space_id = agent_turn_space_id(state, player)
    if space_id is None:
        return False
    posts = frozenset(connected_post_ids(space_id))
    if any(
        post_id in posts
        for seat in state.players
        if seat.player_id != player
        for post_id in seat.spy_post_ids
    ):
        return True
    return bool(empty_observation_post_ids(state, posts))


def reward_can_change_something(
    state: GameState,
    player: int,
    reward: Reward,
    section: EffectSection,
    owner_after: PlayerState,
) -> bool:
    """Whether ``reward`` of ``section`` can change anything for ``player`` now.

    "Intrigue 카드를 플레이하려면 카드의 모든 조건을 충족하고 모든 비용을
    지불해야 한다. [FAQ p. 2]" (docs/rules/player-turns.md), and the user's
    ruling of 2026-10-06 that an Intrigue option needs an effect that can
    change something ("아무 효과 없이 책략을 쓸 수 없는거지"): the Intrigue
    form of the Arrakeen Scouts check (``scouts_effects.reward_has_effect``,
    OQ-071). ``owner_after`` is the owner after the option's resource cost,
    and a cost that feeds a reward of its own section counts (a discarded
    card can be reshuffled and drawn, a trashed Intrigue card shuffled back,
    a lost troop made a specimen, a lowered Faction raised again). Only
    public state, the owner's own zones and the sizes of hidden piles are
    read.
    """

    owner = state.players[player]
    costs = section.costs
    match reward:
        case DrawPersonalCards():
            return gather_intelligence_draw_available(state, player) or any(
                isinstance(cost, DiscardFromHand) for cost in costs
            )
        case Research():
            # Past the second genetic marker Research draws a card instead
            # [Immortality p. 6]; before it the token always has a space to
            # move to.
            past_second_marker = bool(owner.research_space) and (
                genetic_markers_reached(owner.research_space) >= 2
            )
            return not past_second_marker or gather_intelligence_draw_available(
                state, player
            )
        case DrawIntrigueCards():
            # Twisted cards in the discard pile are never shuffled (OQ-097).
            if state.intrigue_deck or shufflable_intrigue_discard(state):
                return True
            # Twisted Unnatural: the trashed card lands on the discard pile
            # and is shufflable unless it is Twisted (Unnatural itself is).
            return any(isinstance(cost, TrashIntrigueCard) for cost in costs) and any(
                not is_twisted_intrigue(held) for held in owner.intrigue_cards
            )
        case RecruitTroops():
            return _troop_can_join(state, owner_after)
        case GenerateSpecimens():
            if owner_after.troops_supply >= 1:
                return True
            # Gruesome Sacrifice: a troop lost to pay the cost returns to the
            # supply before the specimens are made (a Commander does not).
            return any(
                isinstance(cost, LoseTroops)
                and (
                    owner.troops_conflict
                    if cost.from_conflict
                    else owner.troops_garrison + owner.troops_conflict
                )
                >= 1
                for cost in costs
            )
        case AdvanceTleilaxu():
            # "끝까지 가고 나면 뭐 없는 게 맞다" (OQ-048).
            return not tleilaxu_track_finished(owner)
        case GainInfluence() if not reward.requires_choice:
            assert reward.factions is not None
            return influence_can_rise(owner, reward.factions[0])
        case GainInfluence():
            # A line that pays a LoseInfluence first (Change Allegiances,
            # Tenuous Bond) leaves the Faction it lowers free to rise again,
            # so an unrestricted gain after it always changes something; a
            # gain on a cube at the top is lost (OQ-060).
            if reward.factions is None and any(
                isinstance(cost, LoseInfluence) for cost in costs
            ):
                return True
            return bool(influence_gain_candidates(state, player, reward))
        case DestroyShieldWall():
            return state.shield_wall_present
        case SummonSandworm(requires_maker_hooks=needs_hooks):
            # No effect without a Conflict, while Emperor of the Known
            # Universe blocks deployment [Main p. 17], without the Maker
            # Hooks it asks for, or against a Shield Wall-protected Conflict
            # [Main p. 20] unless Arrakis Planetologist replaces the
            # sandworm [Liet Kynes card].
            return (
                bool(state.current_conflict_ids)
                and not units_deployment_blocked(state, player)
                and not (needs_hooks and not owner.maker_hooks)
                and (
                    replaces_sandworms(owner)
                    or not current_conflict_is_shield_wall_protected(state)
                )
            )
        case DeployFromGarrison():
            return sum(deployable_garrison_units(state, player)) >= 1
        case RetreatTroops(minimum=minimum):
            # An "any number" retreat may choose zero once played [Main
            # p. 20] [FAQ p. 3], but needs a unit in the Conflict to play.
            return owner.troops_conflict + owner.commanders_conflict >= max(minimum, 1)
        case TrashPersonalCard(hand_only=hand_only):
            # A Row card borrowed with Usurp is not "in play" (OQ-054); a
            # bonus for the trashed card's cost is not an effect of its own.
            if hand_only:
                return bool(owner.hand)
            return bool(owner.hand or owner.discard_pile or counted_in_play(owner))
        case PlaceSpy():
            return spy_placement_possible(state, player, reward)
        case AcquireCardUpTo(max_cost=max_cost):
            # The slot's own two lists: the owner's own Manipulate set-aside
            # card counts, never an opponent's [FAQ p. 3].
            from dune_imperium.rules.acquisition import (
                acquirable_imperium_instance_ids,
                acquirable_reserve_card_ids,
            )

            return bool(acquirable_reserve_card_ids(state, max_cost)) or bool(
                acquirable_imperium_instance_ids(state, max_cost, player=player)
            )
        case AcquireReserveCard(card_id=card_id):
            return dict(state.reserve_stacks).get(card_id, 0) > 0
        case AcquireTech(discount=discount):
            from dune_imperium.rules.tech import tech_acquisition_possible

            return tech_acquisition_possible(state, owner_after, discount)
        case TakeContract():
            return state.config.choam_module and _contract_can_be_taken(state, player)
        case GainSolariPerUnitType():
            return owner.units_in_conflict > 0
        case PassTurn():
            # With every other seat revealed, the pass hands the turn
            # straight back [Main p. 8] (``effects.next_unrevealed_player``).
            return any(
                not seat.has_revealed
                for seat in state.players
                if seat.player_id != player
            )
        case RedirectSpiesOnTurnSpace():
            return _redirect_has_target(state, player)
        case GrantAgentIconThisTurn() | GrantAgentIconsThisTurn():
            return agent_placement_ahead(state, player)
        case IgnoreInfluenceRequirementsThisTurn():
            return agent_placement_ahead(state, player) and (
                _unmet_influence_requirement(state, player)
            )
        case CommanderDiscountThisTurn():
            return _commander_purchase_ahead(state, player)
        case GrantCombatDeployment():
            return _combat_deployment_ahead(state, player)
        case SetAsideImperiumRowCard():
            return bool(state.imperium_row)
        case PeekTopCard():
            return bool(owner.deck)
    # Resources, Victory Points, swords, persuasion and Contract reveals
    # (the bank check runs first, OQ-064) always change something; Harvest
    # Cells' Tleilaxu card is judged by its Conflict-end window.
    return True


def rewards_with_no_effect(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
) -> tuple[Reward, ...]:
    """Every reward of ``sections``, in printed order, when none of them can
    change anything now; () as soon as one can.

    An option is playable as soon as one of its effects can change
    something; the others fizzle when it is played (user ruling 2026-10-06,
    ``reward_can_change_something``). A detonation is left out once the
    Shield Wall is gone (``choice_slots`` drops it), so the page names only
    rewards that apply.
    """

    owner = state.players[player]
    cost = resource_cost(sections)
    owner_after = pay_cost(owner, cost) if can_afford(owner, cost) else owner
    dead: list[Reward] = []
    for section in sections:
        for reward in section.rewards:
            if isinstance(reward, DestroyShieldWall) and not state.shield_wall_present:
                continue
            if reward_can_change_something(state, player, reward, section, owner_after):
                return ()
            dead.append(reward)
    return tuple(dead)


def _no_effect_block(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
) -> Reward | None:
    """Return the first reward to blame when no reward of ``sections`` can
    change anything now (``rewards_with_no_effect``), or None when one can."""

    dead = rewards_with_no_effect(state, player, sections)
    return dead[0] if dead else None


def _choice_reward_block(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
) -> Reward | None:
    """Return the first reward that blocks the option whatever else it offers.

    These rewards cannot even be resolved now, or are printed as mandatory,
    so the option is not playable however its other rewards stand. Every
    other reward that cannot happen blocks only when no reward can change
    anything (``_no_effect_block``).
    """

    owner = state.players[player]
    for section in sections:
        for reward in section.rewards:
            match reward:
                case TakeContract() if not state.config.choam_module:
                    return reward
                case SetAsideImperiumRowCard() if not state.imperium_row:
                    return reward
                case PeekTopCard() if not owner.deck:
                    # "덱이 비어 있으면 낼 수 없다" (OQ-038).
                    return reward
                case TrashPersonalCard(mandatory=True, hand_only=True) if (
                    not owner.hand
                ):
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
    """Factions a GainInfluence choice may pick, after its printed limits.

    Never a Faction whose cube is already at the top of its track: a gain
    there is lost (OQ-060, user ruling 2026-09-16), so the picker leaves it
    out like the Conflict-reward picker does (``influence_can_rise``).
    """

    owner = state.players[player]
    candidates = gain.factions if gain.factions is not None else tuple(Faction)
    candidates = tuple(f for f in candidates if influence_can_rise(owner, f))
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
    """A separate printed line is usable when it applies, its cost is payable
    now and one of its rewards can change something (user ruling
    2026-10-06, ``_no_effect_block``)."""

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
        and _no_effect_block(state, player, sections) is None
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
    # Call to Arms in its owner's Reveal turn with nothing left to acquire
    # (user ruling 2026-10-06, ``_trigger_option_block``).
    NO_ACQUISITION_AHEAD = "no_acquisition_ahead"


type OptionUnplayable = OptionBlock | Cost | Reward

# Rewards of another Plot Intrigue card that can add an acquisition to the
# Reveal turn it is played in (Inspire Awe, Tleilaxu Puppet).
_REVEAL_ACQUISITION_REWARDS = (
    AcquireCardUpTo,
    AcquireReserveCard,
    RevealPersuasionThisRound,
)


def _reveal_acquisition_ahead(state: GameState, player: int) -> bool:
    """Whether the owner's open Reveal turn may still acquire a card.

    Deliberately generous, so it never blocks a play that could still fire:
    any action the Reveal frame offers besides ending the Reveal and playing
    an Intrigue card counts -- the shop's own offers (Imperium Row, Reserve,
    a set-aside card, the Tleilaxu Row), and every other choice that might
    add Persuasion or change what is on offer (a deferred Reveal choice, a
    Tech tile, a leader ability). So does another held Plot Intrigue option,
    playable now, that acquires a card or adds Persuasion; trigger options
    are skipped, so this never asks itself again.
    """

    # Function-local: the engine's table and the Intrigue play gate import
    # this module.
    from dune_imperium.rules.engine import LEGAL_ACTION_PROVIDERS
    from dune_imperium.rules.intrigue import (
        intrigue_play_block,
        legal_intrigue_play_actions,
    )
    from dune_imperium.rules.reveal_turn import legal_finish_reveal_actions

    for provider in LEGAL_ACTION_PROVIDERS[FrameKind.REVEAL]:
        if provider in (legal_intrigue_play_actions, legal_finish_reveal_actions):
            continue
        if provider(state, player):
            return True
    for card_id in state.players[player].intrigue_cards:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None or not entry.play_data_complete:
            continue
        for other in entry.options:
            if other.trigger is not None or not any(
                isinstance(reward, _REVEAL_ACQUISITION_REWARDS)
                for section in other.sections
                for reward in section.rewards
            ):
                continue
            if (
                intrigue_play_block(
                    state, player, FrameKind.REVEAL, IntrigueTiming.PLOT, other
                )
                is None
            ):
                return True
    return False


def _trigger_option_block(
    state: GameState,
    player: int,
    option: IntrigueOption,
    sections: tuple[EffectSection, ...],
) -> OptionUnplayable | None:
    """Why a triggered option cannot be played now, or None.

    Playing it only sets the card waiting face up, and its rewards resolve
    when the trigger fires, so the check looks ahead to that firing (user
    ruling 2026-10-06, "아무 효과 없이 책략을 쓸 수 없는거지"). Call to Arms
    recruits a troop "whenever you acquire a card" in the owner's Reveal
    turn this round [Call to Arms card]: its troop must be able to join now
    (``_troop_can_join``, as every recruit is judged), and once the
    owner's Reveal turn is open, a card must still be acquirable in it
    (``_reveal_acquisition_ahead``); before the Reveal the whole Reveal
    turn is still ahead. Harvest Cells is judged by its Conflict-end window
    instead (``combat._conflict_end_trigger_cards``), which projects the
    troops the cleanup returns to the supply.
    """

    if not isinstance(option.trigger, OnRevealAcquisitionThisRound):
        return None
    dead = _no_effect_block(state, player, sections)
    if dead is not None:
        return dead
    frame = _plot_frame(state, player)
    if (
        frame is not None
        and frame.kind == FrameKind.REVEAL
        and not _reveal_acquisition_ahead(state, player)
    ):
        return OptionBlock.NO_ACQUISITION_AHEAD
    return None


def option_is_playable(
    state: GameState,
    player: int,
    option: IntrigueOption,
) -> bool:
    """An option is playable when a section applies, every cost is payable
    and one of its effects can change something (user ruling 2026-10-06).

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
    triggered card needs an applicable section and a firing that can change
    something (``_trigger_option_block``); any other needs an
    applicable section, the Contracts Coercive Negotiation reveals, its
    resource cost, then each player-choice cost (``_choice_cost_block``), a
    reward that cannot be resolved at all (``_choice_reward_block``), and
    last an effect that can change something (``_no_effect_block``):
    "Intrigue 카드를 플레이하려면 카드의 모든 조건을 충족하고 모든 비용을
    지불해야 한다. [FAQ p. 2]" (docs/rules/player-turns.md), with the
    user's ruling of 2026-10-06, "아무 효과 없이 책략을 쓸 수 없는거지".
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
        return _trigger_option_block(state, player, option, sections)
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
    hard = _choice_reward_block(state, player, sections)
    if hard is not None:
        return hard
    return _no_effect_block(state, player, sections)


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
