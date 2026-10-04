"""Arrakeen Scouts: one seat's cost -> reward line, and the subcommittees.

``push_scouts_effect`` opens a ``scouts_effect`` frame that resolves one
``ScoutsOption`` for one seat: its costs in order, then its rewards in
order (docs/rules/arrakeen-scouts.md). Each step is either automatic (paid
or gained at once, possibly opening another module's frame: a Spy
placement, a Contract pick, a reshuffle) or a choice this frame offers (a
card to discard or trash, a Spy to recall, a Faction, an Agent). The frame
stays on the stack under any frame a step opens and moves its cursor before
opening it, so it resumes by itself once that frame pops; the engine's
automatic advance runs the automatic steps. The same frame serves inside a
turn (a subcommittee joined at the High Council) and in the Scouts step.

Subcommittees [Scouts help] (docs/rules/arrakeen-scouts.md 4): taking a
High Council seat lets the seat choose a subcommittee any time in that turn
(OQ-076 alternative C); the choice lists the unclaimed subcommittees whose
cost the seat can pay and whose reward can do something (OQ-071), and
joining one opens its line.
"""

from collections.abc import Mapping
from dataclasses import replace
from typing import Final, cast

from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    SALES_BY_ID,
    SUBCOMMITTEES_BY_ID,
    AutomaticEffect,
    EventKind,
    ScoutsOption,
)
from dune_imperium.content.arrakeen_scouts.types import (
    AcquireReserveCardToHand,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    LoseHighestInfluence,
    PaySpecimens,
    RecallOtherAgent,
    RecruitToConflict,
    ScoutsCost,
    ScoutsReward,
)
from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.effect_dsl import (
    DiscardFromHand,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainInfluence,
    GiveIntrigueToOpponent,
    LoseInfluence,
    LoseTroops,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RetreatTroops,
    Reward,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import acquire_reserve_for_intrigue
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effect_interpreter import apply_rewards
from dune_imperium.rules.effects import (
    advance_after_effect,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
    recall_conflict_agent,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    turn_owner_of,
    update_turn_recruits,
)
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import with_trashed_intrigue
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.reveal_turn import add_reveal_strength
from dune_imperium.rules.scouts_offers import (
    BOARD_ICON_SUBCOMMITTEE,
    CONFLICT_AGENT,
    drop_reveal_subcommittee_offer,
    open_subcommittees,
    reveal_subcommittee_offer,
)
from dune_imperium.rules.specimens import return_specimens
from dune_imperium.rules.spy_moves import spy_placement_frame
from dune_imperium.rules.strength import reveal_in_progress

_EFFECT_FRAME: Final = "Scouts effect frame"
_OFFER_FRAME: Final = "Subcommittee offer frame"
_ALL_POSTS: Final = tuple(post.post_id for post in OBSERVATION_POSTS)
_CHOICE_FRAME: Final = "Scouts choice frame"
# Political Equilibrium, per seat: one Influence off the highest track.
_EQUILIBRIUM: Final = ScoutsOption(costs=(LoseHighestInfluence(),))

type ScoutsStep = ScoutsCost | ScoutsReward
# Steps ``apply_rewards`` cannot take; the ones this module handles itself
# never reach it, the rest arrive with later slices.
_NOT_DSL_REWARDS: Final = (
    LoseInfluence,
    LoseTroops,
    GiveIntrigueToOpponent,
    RetreatTroops,
    FlipBattleCard,
    TrashDiscardPileCard,
    FlipFaceUpConflictCard,
)


# --- Which option -------------------------------------------------------------------


def scouts_option(item: str, index: int) -> ScoutsOption:
    """Return option ``index`` of a Scouts item (a subcommittee has one)."""

    if item in SUBCOMMITTEES_BY_ID:
        return SUBCOMMITTEES_BY_ID[item].option
    if item in EVENTS_BY_ID:
        event = EVENTS_BY_ID[item]
        if event.automatic is AutomaticEffect.POLITICAL_EQUILIBRIUM:
            return _EQUILIBRIUM
        if event.secret_choices:
            return event.secret_choices[index].option
        return event.options[index]
    if item in SALES_BY_ID:
        return SALES_BY_ID[item].options[index]
    if item in AUCTIONS_BY_ID:
        return ScoutsOption(rewards=AUCTIONS_BY_ID[item].rank_rewards[index])
    raise ValueError(f"unknown Scouts item: {item!r}")


def option_steps(option: ScoutsOption) -> tuple[ScoutsStep, ...]:
    """Costs in printed order, then rewards (costs are paid in full first)."""

    return (*option.costs, *option.rewards)


def option_is_affordable(state: GameState, player: int, option: ScoutsOption) -> bool:
    """Whether ``player`` can pay every cost of ``option`` now."""

    owner = state.players[player]
    solari = spice = water = 0
    for cost in option.costs:
        match cost:
            case PayResources():
                solari += cost.solari
                spice += cost.spice
                water += cost.water
            case DiscardFromHand(count=count):
                if len(owner.hand) < count:
                    return False
            case RecallSpy(count=count):
                if len(owner.spy_post_ids) < count:
                    return False
            case TrashIntrigueCard():
                if not owner.intrigue_cards:
                    return False
            case TrashPersonalCard(hand_only=hand_only):
                zones = (
                    owner.hand
                    if hand_only
                    else (*owner.hand, *owner.discard_pile, *owner.in_play)
                )
                if not zones:
                    return False
            case LoseGarrisonTroops(count=count):
                if owner.troops_garrison < count:
                    return False
            case PaySpecimens(count=count):
                if owner.specimens < count:
                    return False
            case LoseFactionInfluence(faction=faction, count=count):
                if influence_amount(owner.influence, faction) < count:
                    return False
            case LoseHighestInfluence():
                pass
            case _:
                # Influence losses are the only other costs; slice 5 adds them.
                raise NotImplementedError(f"Scouts cost not supported yet: {cost!r}")
    resources = owner.resources
    return (
        resources.solari >= solari
        and resources.spice >= spice
        and (resources.water >= water)
    )


def reward_has_effect(
    state: GameState,
    player: int,
    reward: ScoutsReward,
    *,
    exclude_space: str = "",
) -> bool:
    """Whether ``reward`` can change anything for ``player`` now.

    Checked are the rewards that can come to nothing: a Reserve card whose
    stack is empty, an Agent recall with no other Agent out, an Influence
    gain whose every track is at the top (lost, OQ-060), and a recruit with
    no troop in the supply (nor a specimen to return, Immortality).
    """

    owner = state.players[player]
    match reward:
        case AcquireReserveCardToHand(card_id=card_id):
            return dict(state.reserve_stacks).get(card_id, 0) > 0
        case RecallOtherAgent():
            return bool(_recallable_spaces(owner, exclude_space))
        case GainInfluence():
            return bool(_gainable_factions(owner, reward))
        case RecruitTroops() | RecruitToConflict():
            return owner.troops_supply > 0 or (
                state.config.immortality and owner.specimens > 0
            )
    return True


def line_is_offered(
    state: GameState,
    player: int,
    option: ScoutsOption,
    *,
    exclude_space: str = "",
) -> bool:
    """Whether a seat may take ``option`` now.

    Its costs must be payable, and a line with a cost must be able to give
    something: "If you don't pay the cost, you don't get the effect"
    [Main p. 20], and a cost that buys nothing is not offered (OQ-046, the
    user's rulings of 2026-09-29 on Moment of Revelation and on arrow
    costs, OQ-071).
    """

    if not option_is_affordable(state, player, option):
        return False
    if not option.costs or not option.rewards:
        return True  # nothing bought, or a pure loss (Crackdown): no check
    return any(
        reward_has_effect(state, player, reward, exclude_space=exclude_space)
        for reward in option.rewards
    )


def line_unavailable_reason(
    state: GameState,
    player: int,
    option: ScoutsOption,
    *,
    exclude_space: str = "",
) -> ScoutsStep | None:
    """The step that keeps ``option`` from being offered now; None if offered.

    The first cost the seat cannot pay, or else the reward that cannot
    happen (``line_is_offered``). For the display only, which shows a line
    the seat cannot take beside the reason; it reads the same checks, so the
    two never disagree.
    """

    if line_is_offered(state, player, option, exclude_space=exclude_space):
        return None
    if not option_is_affordable(state, player, option):
        return _first_unpaid_cost(state, player, option)
    # Payable but not offered: every reward is one that cannot happen.
    return next(
        (
            reward
            for reward in option.rewards
            if not reward_has_effect(state, player, reward, exclude_space=exclude_space)
        ),
        option.rewards[0],
    )


def _first_unpaid_cost(
    state: GameState, player: int, option: ScoutsOption
) -> ScoutsCost:
    """The first cost, in printed order, that ``option_is_affordable`` fails on."""

    resources = state.players[player].resources
    solari = spice = water = 0
    for cost in option.costs:
        if isinstance(cost, PayResources):
            solari += cost.solari
            spice += cost.spice
            water += cost.water
            if (
                solari > resources.solari
                or spice > resources.spice
                or water > resources.water
            ):
                return cost
        elif not option_is_affordable(state, player, ScoutsOption(costs=(cost,))):
            return cost
    return option.costs[0]  # not reached while the option is unaffordable


# --- The effect frame --------------------------------------------------------------


def push_scouts_effect(
    state: GameState,
    player: int,
    item: str,
    option: int,
    *,
    source: str,
    exclude_space: str = "",
) -> GameState:
    """Open the frame that resolves one seat's line of a Scouts item.

    ``exclude_space`` is the space of the Agent that just took the High
    Council seat (Contingencies recalls another, OQ-075).
    """

    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_EFFECT,
        frame_id=f"{source}:effect",
        decision=PlayerDecision(
            owner=player, prompt="Resolve the Arrakeen Scouts effect"
        ),
        context=(
            ("exclude_space", exclude_space),
            ("item", item),
            ("option", option),
            ("picked", 0),
            ("player", player),
            ("source", source),
            ("step", 0),
        ),
    )
    return state.push_decision(frame)


def _effect_frame(state: GameState) -> DecisionFrame | None:
    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    return frame if frame.kind == FrameKind.SCOUTS_EFFECT else None


def _cursor(frame: DecisionFrame) -> tuple[int, str, ScoutsOption, int, int]:
    context = dict(frame.context)
    player = context_int(context, "player", owner=_EFFECT_FRAME)
    item = context_str(context, "item", owner=_EFFECT_FRAME)
    option = scouts_option(item, context_int(context, "option", owner=_EFFECT_FRAME))
    step = context_int(context, "step", owner=_EFFECT_FRAME)
    picked = context_int(context, "picked", owner=_EFFECT_FRAME)
    return player, item, option, step, picked


def _current_step(state: GameState, frame: DecisionFrame) -> ScoutsStep | None:
    player, _, option, step, _ = _cursor(frame)
    steps = option_steps(option)
    if step >= len(steps):
        return None
    current = steps[step]
    return current if _is_choice(state, player, frame, current) else None


def _is_choice(
    state: GameState, player: int, frame: DecisionFrame, step: ScoutsStep
) -> bool:
    """Whether ``step`` waits on this frame's own choice actions now."""

    owner = state.players[player]
    match step:
        case RecruitTroops(count=count) | RecruitToConflict(count=count):
            return _specimen_top_up(state, owner, count, frame) > 0
        case DiscardFromHand():
            return bool(owner.hand)
        case RecallSpy():
            return bool(owner.spy_post_ids)
        case TrashIntrigueCard():
            return bool(owner.intrigue_cards)
        case TrashPersonalCard(mandatory=True, hand_only=hand_only):
            return bool(
                owner.hand
                if hand_only
                else (*owner.hand, *owner.discard_pile, *owner.in_play)
            )
        case GainInfluence() if step.requires_choice:
            return len(_gainable_factions(owner, step)) > 1
        case GainLowestInfluence():
            return len(_lowest_factions(owner)) > 1
        case RecallOtherAgent():
            return len(_frame_recallable(owner, frame)) > 0
        case LoseFactionInfluence(faction=faction):
            return len(_loss_actions(state, player, (faction,))) > 1
        case LoseHighestInfluence():
            return len(_loss_actions(state, player, highest_factions(owner))) > 1
    return False


def _specimen_top_up(
    state: GameState, owner: PlayerState, needed: int, frame: DecisionFrame
) -> int:
    """How many specimens the seat may return before a recruit (0: none).

    "You may return any of your specimens to your supply at any time"
    [Immortality p. 8]; a Scouts line recruiting more troops than the supply
    holds offers it first, once (user ruling 2026-09-29, OQ-050, OQ-074).
    """

    if not state.config.immortality or dict(frame.context).get("picked", 0):
        return 0
    short = needed - owner.troops_supply
    return min(short, owner.specimens) if short > 0 else 0


def scouts_effect_can_advance(state: GameState) -> bool:
    """Whether the top Scouts effect frame waits on an automatic step."""

    frame = _effect_frame(state)
    return frame is not None and _current_step(state, frame) is None


def _moved(state: GameState, frame: DecisionFrame, *, step: int) -> GameState:
    """Replace the top frame's cursor (fresh step: no pick made yet)."""

    context = dict(frame.context)
    context["step"] = step
    context["picked"] = 0
    moved = replace(frame, context=tuple(sorted(context.items())))
    return replace(state, decision_stack=(*state.decision_stack[:-1], moved))


def advance_scouts_effect(state: GameState) -> RuleResult:
    """Run the top frame's automatic step, or close the frame when done."""

    frame = _effect_frame(state)
    if frame is None:
        raise ValueError("there is no Scouts effect frame")
    player, item, option, step, _ = _cursor(frame)
    context = dict(frame.context)
    source = context_str(context, "source", owner=_EFFECT_FRAME)
    steps = option_steps(option)
    if step >= len(steps):
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{source}:resolved",
                    kind="scouts_effect_resolved",
                    payload=(("item_id", item), ("player", player)),
                ),
            ),
        )
    moved = _moved(state, frame, step=step + 1)
    return _apply_automatic(moved, player, steps[step], source=f"{source}:{step}")


def _credit_turn(
    state: GameState,
    player: int,
    *,
    troops: int = 0,
    spice_spent: int = 0,
) -> GameState:
    """Count recruits and spice spent toward ``player``'s own open turn only."""

    if turn_owner_of(state) != player or not (troops or spice_spent):
        return state
    return update_turn_recruits(state, troops_recruited=troops, spice_spent=spice_spent)


def _apply_automatic(
    state: GameState,
    player: int,
    step: ScoutsStep,
    *,
    source: str,
) -> RuleResult:
    owner = state.players[player]
    match step:
        case PayResources(solari=solari, spice=spice, water=water):
            # Every spend adds to ``spice_spent_turn``, so a line's cost inside
            # the seat's open turn is not read as lost gains by Hungry for
            # Spice or "gained spice this turn" (OQ-063, OQ-095 (3)).
            paid = replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari - solari,
                    spice=owner.resources.spice - spice,
                    water=owner.resources.water - water,
                ),
                spice_spent_turn=owner.spice_spent_turn + spice,
            )
            next_state = replace(state, players=replace_player(state.players, paid))
            next_state = _credit_turn(next_state, player, spice_spent=spice)
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=f"{source}:paid",
                        kind="scouts_cost_paid",
                        payload=(
                            ("player", player),
                            ("solari", solari),
                            ("spice", spice),
                            ("water", water),
                        ),
                    ),
                ),
            )
        case LoseGarrisonTroops(count=count):
            lost = min(count, owner.troops_garrison)
            next_owner = replace(
                owner,
                troops_garrison=owner.troops_garrison - lost,
                troops_supply=owner.troops_supply + lost,
            )
            return _owner_event(
                state,
                next_owner,
                GameEvent(
                    event_id=f"{source}:scouts_troops_lost",
                    kind="scouts_troops_lost",
                    payload=(("count", lost), ("player", player)),
                ),
            )
        case PaySpecimens(count=count):
            paid_count = min(count, owner.specimens)
            next_owner = replace(
                owner,
                specimens=owner.specimens - paid_count,
                troops_supply=owner.troops_supply + paid_count,
            )
            return _owner_event(
                state,
                next_owner,
                GameEvent(
                    event_id=f"{source}:scouts_specimens_paid",
                    kind="scouts_specimens_paid",
                    payload=(("count", paid_count), ("player", player)),
                ),
            )
        case RecruitToConflict(count=count):
            deployed = min(count, owner.troops_supply)
            next_owner = replace(
                owner,
                troops_supply=owner.troops_supply - deployed,
                troops_conflict=owner.troops_conflict + deployed,
            )
            return _owner_event(
                state,
                next_owner,
                GameEvent(
                    event_id=f"{source}:scouts_troops_to_conflict",
                    kind="scouts_troops_to_conflict",
                    payload=(("count", deployed), ("player", player)),
                ),
            )
        case PlaceSpy():
            return RuleResult(
                state=spy_placement_frame(
                    state,
                    player,
                    _ALL_POSTS,
                    source=source,
                )
            )
        case TrashPersonalCard():
            # The trash icon: optional [Main p. 20].
            return RuleResult(
                state=state.push_decision(
                    optional_trash_frame(player, source)
                )
            )
        case AcquireReserveCardToHand(card_id=card_id):
            if dict(state.reserve_stacks).get(card_id, 0) < 1:
                return RuleResult(state=state)
            acquired = acquire_reserve_for_intrigue(
                state,
                player,
                card_id,
                to_hand=True,
                source=source,
            )
            return acquired.result
        case GainInfluence() if step.requires_choice:
            factions = _gainable_factions(owner, step)
            if not factions:
                return RuleResult(state=state)  # every track is at the top
            return gain_faction_influence(
                state, player, factions[0], step.times, event_prefix=source
            )
        case GainLowestInfluence():
            (faction,) = _lowest_factions(owner)
            return gain_faction_influence(
                state, player, faction, 1, event_prefix=source
            )
        case RecallOtherAgent():
            return RuleResult(state=state)  # no other Agent is out (OQ-075)
        case GainSpiceWithHelixBonus(spice=spice, helix_spice=helix_spice):
            # Offworld Operation: more once the seat's research token has
            # reached the Helix, the first genetic marker (OQ-089 (b)).
            helix = state.config.immortality and (
                genetic_markers_reached(owner.research_space) >= 1
            )
            gained = helix_spice if helix else spice
            return _owner_event(
                state,
                replace(
                    owner,
                    resources=replace(
                        owner.resources, spice=owner.resources.spice + gained
                    ),
                ),
                GameEvent(
                    event_id=f"{source}:helix_spice",
                    kind="scouts_helix_spice",
                    payload=(("helix", helix), ("player", player), ("spice", gained)),
                ),
            )
        case DiscardFromHand() | RecallSpy() | TrashIntrigueCard():
            # A choice with nothing left to choose (checked before paying a
            # cost; a delayed reward's may run dry): nothing happens.
            return RuleResult(state=state)
        case LoseFactionInfluence(faction=faction, count=count):
            return lose_faction_influence(
                state, player, faction, count, event_prefix=source
            )
        case LoseHighestInfluence():
            factions = highest_factions(owner)
            if not factions:
                return RuleResult(state=state)  # no Influence to lose
            (faction,) = factions
            return lose_faction_influence(
                state, player, faction, 1, event_prefix=source
            )
    if isinstance(step, _NOT_DSL_REWARDS):
        raise NotImplementedError(f"Scouts step not supported yet: {step!r}")
    outcome = apply_rewards(state, player, (cast(Reward, step),), source=source)
    next_state = _credit_turn(
        outcome.result.state, player, troops=outcome.troops_recruited
    )
    return RuleResult(state=next_state, events=outcome.result.events)


def _owner_event(state: GameState, owner: PlayerState, event: GameEvent) -> RuleResult:
    return RuleResult(
        state=replace(state, players=replace_player(state.players, owner)),
        events=(event,),
    )


def _gainable_factions(owner: PlayerState, step: GainInfluence) -> tuple[Faction, ...]:
    allowed = step.factions if step.factions is not None else tuple(Faction)
    return tuple(
        faction
        for faction in allowed
        if influence_amount(owner.influence, faction) < MAX_INFLUENCE
    )


def _lowest_factions(owner: PlayerState) -> tuple[Faction, ...]:
    lowest = min(influence_amount(owner.influence, faction) for faction in Faction)
    return tuple(
        faction
        for faction in Faction
        if influence_amount(owner.influence, faction) == lowest
    )


def highest_factions(owner: PlayerState) -> tuple[Faction, ...]:
    """The seat's highest Influence tracks (none when every track is at 0)."""

    highest = max(influence_amount(owner.influence, faction) for faction in Faction)
    if highest == 0:
        return ()
    return tuple(
        faction
        for faction in Faction
        if influence_amount(owner.influence, faction) == highest
    )


def _loss_actions(
    state: GameState, player: int, factions: tuple[Faction, ...]
) -> tuple[DomainAction, ...]:
    """One loss per Faction, split by Alliance recipient when several tie."""

    actions: list[DomainAction] = []
    for faction in factions:
        recipients = alliance_recipients_after_influence_loss(state, player, faction)
        if len(recipients) > 1:
            actions.extend(
                DomainAction(
                    action_id="scouts_lose_influence_to",
                    actor=player,
                    arguments=(
                        ("alliance_recipient", recipient),
                        ("faction", faction.value),
                    ),
                )
                for recipient in recipients
            )
        else:
            actions.append(
                DomainAction(
                    action_id="scouts_lose_influence",
                    actor=player,
                    arguments=(("faction", faction.value),),
                )
            )
    return tuple(actions)




def _recallable_spaces(owner: PlayerState, excluded: str) -> tuple[str, ...]:
    """The seat's other Agents: on the board but the one that took the seat
    (``excluded``), and one sent into the Conflict by Into the Fray (every
    Recall Agent effect may bring that one back, OQ-068, OQ-075 (D)).

    The Conflict one is offered during the seat's own Reveal turn too
    (Contingencies joined through Corrinth City's seat): the seat may pick
    any of its other Agents, the Into the Fray one included, and its
    strength is recomputed (user ruling 2026-09-29, OQ-075); "Reveal turn
    중 효과가 unit 수나 strength를 바꾸면 Combat marker도 그에 맞게
    갱신한다." [Main p. 13].
    """

    locations = list(owner.agent_locations)
    if excluded in locations:
        locations.remove(excluded)  # only the one Agent that took the seat
    # The seat-taking Agent may itself have gone into the Conflict by Into
    # the Fray this turn: "not the Agent you sent during this turn"
    # [Main p. 20], as for every other Recall Agent effect (OQ-068).
    sent_there = 1 if excluded == CONFLICT_AGENT else 0
    if owner.agent_in_conflict - sent_there > 0:
        locations.append(CONFLICT_AGENT)
    return tuple(dict.fromkeys(locations))


def _frame_recallable(owner: PlayerState, frame: DecisionFrame) -> tuple[str, ...]:
    excluded = context_str(dict(frame.context), "exclude_space", owner=_EFFECT_FRAME)
    return _recallable_spaces(owner, excluded)


# --- Choices -------------------------------------------------------------------------


def legal_scouts_effect_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Offer the current choice step's options."""

    frame = owned_top_frame(state, FrameKind.SCOUTS_EFFECT, player)
    if frame is None:
        return ()
    step = _current_step(state, frame)
    owner = state.players[player]

    def offer(
        action_id: str, name: str, values: tuple[str, ...]
    ) -> tuple[DomainAction, ...]:
        return tuple(
            DomainAction(action_id=action_id, actor=player, arguments=((name, value),))
            for value in dict.fromkeys(values)
        )

    match step:
        case RecruitTroops(count=count) | RecruitToConflict(count=count):
            top_up = _specimen_top_up(state, owner, count, frame)
            return tuple(
                DomainAction(
                    action_id="scouts_return_specimens",
                    actor=player,
                    arguments=(("count", returned),),
                )
                for returned in range(top_up + 1)
            )
        case DiscardFromHand():
            return offer("scouts_discard", "card_id", owner.hand)
        case TrashPersonalCard(hand_only=hand_only):
            zones = (
                owner.hand
                if hand_only
                else (*owner.hand, *owner.discard_pile, *owner.in_play)
            )
            return offer("scouts_trash_card", "card_id", zones)
        case TrashIntrigueCard():
            return offer("scouts_trash_intrigue", "card_id", owner.intrigue_cards)
        case RecallSpy():
            return offer("scouts_recall_spy", "post_id", owner.spy_post_ids)
        case GainInfluence():
            factions = _gainable_factions(owner, step)
            return offer(
                "scouts_choose_faction", "faction", tuple(f.value for f in factions)
            )
        case GainLowestInfluence():
            factions = _lowest_factions(owner)
            return offer(
                "scouts_choose_faction", "faction", tuple(f.value for f in factions)
            )
        case RecallOtherAgent():
            return offer(
                "scouts_recall_agent",
                "space_id",
                _frame_recallable(owner, frame),
            )
        case LoseFactionInfluence(faction=faction):
            return _loss_actions(state, player, (faction,))
        case LoseHighestInfluence():
            return _loss_actions(state, player, highest_factions(owner))
    return ()


def apply_scouts_effect_action(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one pick of the current choice step."""

    if action not in legal_scouts_effect_actions(state, action.actor):
        raise ValueError("action is not a legal Arrakeen Scouts choice")
    frame = state.decision_stack[-1]
    player, _, option, step, picked = _cursor(frame)
    context = dict(frame.context)
    source = f"{context_str(context, 'source', owner=_EFFECT_FRAME)}:{step}"
    current = option_steps(option)[step]
    if action.action_id == "scouts_return_specimens":
        # The recruit step itself stays next; it is automatic from here on.
        returned = dict(action.arguments)["count"]
        assert isinstance(returned, int)
        context["picked"] = 1
        topped = replace(
            state,
            decision_stack=(
                *state.decision_stack[:-1],
                replace(frame, context=tuple(sorted(context.items()))),
            ),
        )
        return return_specimens(topped, player, returned, source=source)
    value = str(dict(action.arguments)[action.arguments[0][0]])
    count = getattr(current, "count", 1)
    done = picked + 1 >= count or action.action_id in (
        "scouts_choose_faction",
        "scouts_recall_agent",
        "scouts_trash_card",
        "scouts_trash_intrigue",
        "scouts_lose_influence",
        "scouts_lose_influence_to",
    )
    if done:
        cursor_state = _moved(state, frame, step=step + 1)
    else:
        context["picked"] = picked + 1
        cursor_state = replace(
            state,
            decision_stack=(
                *state.decision_stack[:-1],
                replace(frame, context=tuple(sorted(context.items()))),
            ),
        )
    owner = cursor_state.players[player]
    pick_source = f"{source}:{picked}"
    match action.action_id:
        case "scouts_discard":
            return discard_personal_card_from_hand(
                cursor_state, player, value, source=pick_source
            )
        case "scouts_trash_card":
            return trash_personal_card(
                cursor_state, player, value, source=pick_source
            )
        case "scouts_trash_intrigue":
            next_owner = replace(
                owner,
                intrigue_cards=tuple(c for c in owner.intrigue_cards if c != value),
            )
            # The trashed card joins the shared Intrigue discard (OQ-061,
            # user ruling 2026-10-04).
            return RuleResult(
                state=with_trashed_intrigue(
                    replace(
                        cursor_state,
                        players=replace_player(cursor_state.players, next_owner),
                    ),
                    value,
                ),
                events=(
                    GameEvent(
                        event_id=f"{pick_source}:intrigue_trashed",
                        kind="intrigue_card_trashed",
                        payload=(("card_id", value), ("player", player)),
                    ),
                ),
            )
        case "scouts_recall_spy":
            recalled = replace(
                owner,
                spies_supply=owner.spies_supply + 1,
                spies_recalled_turn=owner.spies_recalled_turn + 1,
                spy_post_ids=tuple(p for p in owner.spy_post_ids if p != value),
            )
            return RuleResult(
                state=replace(
                    cursor_state,
                    players=replace_player(cursor_state.players, recalled),
                ),
                events=(
                    GameEvent(
                        event_id=f"{pick_source}:recalled:{value}",
                        kind="spy_recalled",
                        payload=(("player", player), ("post_id", value)),
                    ),
                ),
            )
        case "scouts_choose_faction":
            times = current.times if isinstance(current, GainInfluence) else 1
            return gain_faction_influence(
                cursor_state, player, Faction(value), times, event_prefix=pick_source
            )
        case "scouts_recall_agent" if value == CONFLICT_AGENT:
            back, recall_event = recall_conflict_agent(
                owner,
                player=player,
                source=pick_source,
                event_id=f"{pick_source}:agent_recalled",
            )
            stack = cursor_state.decision_stack
            delta = back.combat_strength - owner.combat_strength
            if delta and reveal_in_progress(cursor_state, player):
                # Corrinth City's seat, in the seat's Reveal turn (OQ-075):
                # the Reveal frame's own tally follows the running total
                # [Main p. 13], as for any unit removed during the Reveal.
                stack = add_reveal_strength(stack, delta)
            return RuleResult(
                state=replace(
                    cursor_state,
                    players=replace_player(cursor_state.players, back),
                    decision_stack=stack,
                ),
                events=(recall_event,),
            )
        case "scouts_recall_agent":
            locations = list(owner.agent_locations)
            locations.remove(value)
            recalled_agent = replace(
                owner,
                agents_available=owner.agents_available + 1,
                agent_locations=tuple(locations),
            )
            return RuleResult(
                state=replace(
                    cursor_state,
                    players=replace_player(cursor_state.players, recalled_agent),
                ),
                events=(
                    GameEvent(
                        event_id=f"{pick_source}:agent_recalled",
                        kind="agent_recalled",
                        payload=(("player", player), ("space_id", value)),
                    ),
                ),
            )
        case "scouts_lose_influence" | "scouts_lose_influence_to":
            arguments = dict(action.arguments)
            recipient = arguments.get("alliance_recipient")
            return lose_faction_influence(
                cursor_state,
                player,
                Faction(str(arguments["faction"])),
                1,
                event_prefix=pick_source,
                alliance_recipient=recipient if isinstance(recipient, int) else None,
            )
    raise RuntimeError(f"unknown Scouts choice: {action.action_id}")


# --- One seat's turn-order choice ---------------------------------------------------


def _choice_options(item: str) -> tuple[ScoutsOption, ...]:
    if item in SALES_BY_ID:
        return SALES_BY_ID[item].options
    return EVENTS_BY_ID[item].options


def _is_passable(item: str) -> bool:
    """A sale and Rebuild Infrastructure may always be passed; an event only
    when it offers "or Pass" [Scouts event: <name>] [Scouts sale: <name>]."""

    if item in SALES_BY_ID:
        return True
    event = EVENTS_BY_ID[item]
    return event.passable or event.kind is EventKind.SHARED


def _affordable(state: GameState, player: int, item: str) -> tuple[int, ...]:
    return tuple(
        index
        for index, option in enumerate(_choice_options(item))
        if line_is_offered(state, player, option)
    )


def offer_scouts_choice(
    state: GameState,
    player: int,
    item: str,
    *,
    source: str,
    volunteer: int = -1,
) -> RuleResult:
    """Open one seat's turn-order choice of an event or sale (OQ-071).

    Only lines the seat can pay for, and whose cost buys something, are
    offered (``line_is_offered``). A seat that must choose and can do one
    line only still gets the choice, with the other line shown but not
    selectable (``display.scouts.scouts_choice_lines``); one that can do
    none is skipped without a choice (OQ-071, user ruling 2026-09-29)
    [Scouts help]. ``volunteer`` is Rebuild Infrastructure's first seat
    that agreed to pay (OQ-084).
    """

    affordable = _affordable(state, player, item)
    if not affordable:
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"{source}:skipped",
                    kind="scouts_choice_skipped",
                    payload=(("item_id", item), ("player", player)),
                ),
            ),
        )
    passable = _is_passable(item)
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_CHOICE,
        frame_id=f"{source}:choice",
        decision=PlayerDecision(
            owner=player,
            prompt=(
                "Choose an Arrakeen Scouts option or pass"
                if passable
                else "Choose an Arrakeen Scouts option"
            ),
        ),
        context=(
            ("item", item),
            ("player", player),
            ("source", source),
            ("volunteer", volunteer),
        ),
    )
    return RuleResult(state=state.push_decision(frame))


def offer_only_line(
    state: GameState,
    player: int,
    item: str,
    index: int,
    *,
    source: str,
    exclude_space: str = "",
) -> RuleResult:
    """Resolve the one line a seat is owed: at once, or as its choice.

    A line without a cost just resolves. A line with a white-arrow cost is
    the seat's to take or leave: "You do not have to pay such a cost. If you
    don't pay the cost, you don't get the effect." [Main p. 20]; it is not
    offered at all when the seat cannot pay it or when paying would buy
    nothing (``line_is_offered``). Used by a revealed secret pick (OQ-085
    (c), ``offer_secret_reward``); a joined subcommittee opens its line
    directly, its cost already checked by ``joinable_subcommittees``.
    """

    option = scouts_option(item, index)
    if not option.costs:
        return RuleResult(
            state=push_scouts_effect(
                state,
                player,
                item,
                index,
                source=source,
                exclude_space=exclude_space,
            )
        )
    if not line_is_offered(state, player, option, exclude_space=exclude_space):
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"{source}:skipped",
                    kind="scouts_choice_skipped",
                    payload=(("item_id", item), ("player", player)),
                ),
            ),
        )
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_CHOICE,
        frame_id=f"{source}:choice",
        decision=PlayerDecision(
            owner=player, prompt="Choose an Arrakeen Scouts option or pass"
        ),
        context=(
            ("exclude_space", exclude_space),
            ("item", item),
            ("only_option", index),
            ("player", player),
            ("source", source),
            ("volunteer", -1),
        ),
    )
    return RuleResult(state=state.push_decision(frame))


def offer_secret_reward(
    state: GameState, player: int, event_id: str, pick: int, *, source: str
) -> RuleResult:
    """Resolve a revealed secret pick's line for its seat (OQ-085 (c))."""

    return offer_only_line(state, player, event_id, pick, source=source)


def _line_exclude_space(context: Mapping[str, object]) -> str:
    """An only-line frame's ``exclude_space``."""

    excluded = context.get("exclude_space", "")
    return excluded if isinstance(excluded, str) else ""


def legal_scouts_choice_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """The seat's payable lines, and a pass where the item allows one."""

    frame = owned_top_frame(state, FrameKind.SCOUTS_CHOICE, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    item = context_str(context, "item", owner=_CHOICE_FRAME)
    only = context.get("only_option")
    if type(only) is int:
        # The one line a seat is owed, with a cost: take it or leave it.
        excluded = _line_exclude_space(context)
        passable = True
        indices: tuple[int, ...] = (
            (only,)
            if line_is_offered(
                state, player, scouts_option(item, only), exclude_space=excluded
            )
            else ()
        )
    else:
        passable = _is_passable(item)
        indices = _affordable(state, player, item)
    passes = (DomainAction(action_id="scouts_pass", actor=player),) if passable else ()
    return (
        *passes,
        *(
            DomainAction(
                action_id="scouts_choose_option",
                actor=player,
                arguments=(("option", index),),
            )
            for index in indices
        ),
    )


def apply_scouts_choice_action(state: GameState, action: DomainAction) -> RuleResult:
    """Pass, or take a line (Rebuild Infrastructure: agree to pay)."""

    if action not in legal_scouts_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Arrakeen Scouts option")
    context = dict(state.decision_stack[-1].context)
    item = context_str(context, "item", owner=_CHOICE_FRAME)
    source = context_str(context, "source", owner=_CHOICE_FRAME)
    popped = state.pop_decision()
    if action.action_id == "scouts_pass":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:passed",
                    kind="scouts_choice_passed",
                    payload=(("item_id", item), ("player", action.actor)),
                ),
            ),
        )
    index = dict(action.arguments)["option"]
    assert isinstance(index, int)
    event = EVENTS_BY_ID.get(item)
    if event is not None and event.kind is EventKind.SHARED:
        volunteer = context_int(context, "volunteer", owner=_CHOICE_FRAME)
        return _rebuild(popped, action.actor, volunteer, source=source)
    excluded = _line_exclude_space(context)
    return RuleResult(
        state=push_scouts_effect(
            popped,
            action.actor,
            item,
            index,
            source=source,
            exclude_space=excluded,
        ),
        events=(
            GameEvent(
                event_id=f"{source}:chosen",
                kind="scouts_option_chosen",
                payload=(
                    ("item_id", item),
                    ("option", index),
                    ("player", action.actor),
                ),
            ),
        ),
    )


def _rebuild(
    state: GameState, player: int, volunteer: int, *, source: str
) -> RuleResult:
    """Rebuild Infrastructure (OQ-084): the first two seats that agree each
    pay 1 spice and the Shield Wall returns; one seat alone pays nothing."""

    if volunteer < 0:
        tasks = tuple(
            task.replace("|-1", f"|{player}") if task.startswith("rebuild:") else task
            for task in state.scouts_tasks
        )
        return RuleResult(
            state=replace(state, scouts_tasks=tasks),
            events=(
                GameEvent(
                    event_id=f"{source}:volunteered",
                    kind="scouts_rebuild_offered",
                    payload=(("player", player),),
                ),
            ),
        )
    players = state.players
    for payer in (volunteer, player):
        owner = players[payer]
        players = replace_player(
            players,
            replace(
                owner,
                resources=replace(owner.resources, spice=owner.resources.spice - 1),
            ),
        )
    return RuleResult(
        state=replace(
            state,
            players=players,
            shield_wall_present=True,
            scouts_tasks=tuple(
                task for task in state.scouts_tasks if not task.startswith("rebuild:")
            ),
        ),
        events=(
            GameEvent(
                event_id=f"{source}:rebuilt",
                kind="scouts_shield_wall_rebuilt",
                payload=(("players", f"{volunteer},{player}"),),
            ),
        ),
    )


# --- Subcommittees --------------------------------------------------------------------
#
# A new High Council seat may join one still-empty subcommittee any time in
# the turn it was taken (OQ-076 alternative C, user ruling 2026-09-30, a
# project convention widening the app's "when you take a council seat"):
# "You may carry out all these effects in any order." [Main p. 9]. Two
# levels: the turn's own frame (the Agent-turn effect frame while
# ``BOARD_ICON_SUBCOMMITTEE`` is pending, or the Reveal frame while
# Corrinth City's offer is open) offers ``choose_subcommittee`` and
# ``decline_subcommittee``; choosing opens the ``scouts_subcommittee`` frame
# listing ``join_subcommittee`` per joinable subcommittee and the decline.


def joinable_subcommittees(
    state: GameState, player: int, *, exclude_space: str = ""
) -> tuple[str, ...]:
    """Unclaimed subcommittees of the display that ``player`` may join now.

    Taking a council seat lets the seat join one subcommittee nobody has
    chosen yet, and joining one with a cost means paying that cost
    (docs/rules/arrakeen-scouts.md 4; the app's help and subcommittee
    instructions, OQ-075, OQ-076). A white-arrow line whose effect cannot
    happen cannot be paid for (user principle 2026-09-29, OQ-071), so the
    line must be offered (``line_is_offered``): Contingencies with no other
    Agent to recall is not joinable. ``exclude_space`` is the space of the
    Agent that took the seat (``CONFLICT_AGENT`` when Into the Fray moved it
    into the Conflict this turn; "" for Corrinth City's Reveal-turn seat,
    OQ-075).
    """

    return tuple(
        subcommittee_id
        for subcommittee_id in open_subcommittees(state, player)
        if line_is_offered(
            state,
            player,
            SUBCOMMITTEES_BY_ID[subcommittee_id].option,
            exclude_space=exclude_space,
        )
    )


def pending_subcommittee_exclude(state: GameState, player: int) -> str | None:
    """The ``exclude_space`` of ``player``'s open subcommittee choice, or
    None while the seat's own turn frame offers none.

    At the High Council board space it is worked out now, not when the seat
    was taken: the seat-taking Agent's space, or ``CONFLICT_AGENT`` once Into
    the Fray has moved it into the Conflict ("not the Agent you sent during
    this turn" [Main p. 20], OQ-068, OQ-075). Corrinth City's seat has no
    Agent of its own ("", OQ-075).
    """

    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if frame.kind == FrameKind.AGENT_EFFECTS:
        _, context = current_agent_effect_context(state)
        if not board_icon_is_pending(context, BOARD_ICON_SUBCOMMITTEE):
            return None
        space_id = context_str(context, "space_id", owner=_OFFER_FRAME)
        owner = state.players[player]
        return (
            CONFLICT_AGENT
            if turn_agent_in_conflict(owner, context, space_id)
            else space_id
        )
    if frame.kind == FrameKind.REVEAL:
        entry = reveal_subcommittee_offer(state, player)
        return None if entry is None else entry[2]
    return None


def legal_subcommittee_choice_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """The turn frame's subcommittee choice: choose (when one can be joined
    now) or decline; the seat may also leave it for later in the turn."""

    excluded = pending_subcommittee_exclude(state, player)
    if excluded is None:
        return ()
    choose = (
        (DomainAction(action_id="choose_subcommittee", actor=player),)
        if joinable_subcommittees(state, player, exclude_space=excluded)
        else ()
    )
    return (*choose, DomainAction(action_id="decline_subcommittee", actor=player))


def legal_subcommittee_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Join one joinable subcommittee, or decline (the chance is then gone)."""

    frame = owned_top_frame(state, FrameKind.SCOUTS_SUBCOMMITTEE, player)
    if frame is None:
        return ()
    excluded = context_str(dict(frame.context), "exclude_space", owner=_OFFER_FRAME)
    return (
        DomainAction(action_id="decline_subcommittee", actor=player),
        *(
            DomainAction(
                action_id="join_subcommittee",
                actor=player,
                arguments=(("subcommittee_id", subcommittee_id),),
            )
            for subcommittee_id in joinable_subcommittees(
                state, player, exclude_space=excluded
            )
        ),
    )


def _offer_source(state: GameState, player: int) -> str:
    """The event source of the seat's open choice (its turn frame on top)."""

    frame = state.decision_stack[-1]
    if frame.kind == FrameKind.REVEAL:
        entry = reveal_subcommittee_offer(state, player)
        if entry is None:
            raise RuntimeError("the Reveal frame holds no subcommittee offer")
        return entry[1]
    _, context = current_agent_effect_context(state)
    space_id = context_str(context, "space_id", owner=_OFFER_FRAME)
    return f"round:{state.round_number}:player:{player}:board:{space_id}:high_council"


def _close_offer(state: GameState, player: int) -> GameState:
    """Retire the seat's choice on its turn frame, now back on top.

    The Agent-turn effect frame finishes the icon and advances (the turn
    stays open until its owner ends it, OQ-095); the Reveal frame drops the
    offer.
    """

    frame = state.decision_stack[-1]
    if frame.kind == FrameKind.REVEAL:
        return drop_reveal_subcommittee_offer(state, player)
    _, context = current_agent_effect_context(state)
    finish_board_icon(context, BOARD_ICON_SUBCOMMITTEE)
    return advance_after_effect(state, context)


def _declined(source: str, player: int) -> GameEvent:
    return GameEvent(
        event_id=f"{source}:subcommittee_declined",
        kind="scouts_subcommittee_declined",
        payload=(("player", player),),
    )


def apply_subcommittee_action(state: GameState, action: DomainAction) -> RuleResult:
    """Choose, join (then the line) or decline the new seat's subcommittee.

    From the turn frame ``choose_subcommittee`` opens the list and
    ``decline_subcommittee`` gives the chance up; in the list
    ``join_subcommittee`` records the member, retires the choice on the turn
    frame and opens the line (its cost is paid, OQ-075), and
    ``decline_subcommittee`` gives the chance up too.
    """

    player = action.actor
    top = state.decision_stack[-1] if state.decision_stack else None
    if top is not None and top.kind == FrameKind.SCOUTS_SUBCOMMITTEE:
        if action not in legal_subcommittee_actions(state, player):
            raise ValueError("action is not a legal subcommittee choice")
        context = dict(top.context)
        source = context_str(context, "source", owner=_OFFER_FRAME)
        excluded = context_str(context, "exclude_space", owner=_OFFER_FRAME)
        closed = _close_offer(state.pop_decision(), player)
        if action.action_id == "decline_subcommittee":
            return RuleResult(state=closed, events=(_declined(source, player),))
        subcommittee_id = str(dict(action.arguments)["subcommittee_id"])
        joined = replace(
            closed,
            scouts_subcommittee_members=(
                *closed.scouts_subcommittee_members,
                (subcommittee_id, player),
            ),
        )
        opened = push_scouts_effect(
            joined,
            player,
            subcommittee_id,
            0,
            source=f"{source}:{subcommittee_id}",
            exclude_space=excluded,
        )
        return RuleResult(
            state=opened,
            events=(
                GameEvent(
                    event_id=f"{source}:subcommittee_joined",
                    kind="scouts_subcommittee_joined",
                    payload=(
                        ("player", player),
                        ("subcommittee_id", subcommittee_id),
                    ),
                ),
            ),
        )
    if action not in legal_subcommittee_choice_actions(state, player):
        raise ValueError("action is not a legal subcommittee choice")
    excluded_now = pending_subcommittee_exclude(state, player)
    assert excluded_now is not None
    source = _offer_source(state, player)
    if action.action_id == "decline_subcommittee":
        return RuleResult(
            state=_close_offer(state, player), events=(_declined(source, player),)
        )
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_SUBCOMMITTEE,
        frame_id=f"{source}:subcommittee",
        decision=PlayerDecision(owner=player, prompt="Join a subcommittee or decline"),
        context=(
            ("exclude_space", excluded_now),
            ("player", player),
            ("source", source),
        ),
    )
    return RuleResult(state=state.push_decision(frame))
