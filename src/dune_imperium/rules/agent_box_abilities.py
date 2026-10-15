"""Agent boxes resolved from their ability records (composed effects, stage A2).

docs/composed-effects-plan.md 5 (A2). A personal card whose Agent box has a
record in ``content.uprising.agent_abilities`` is resolved here instead of
by its own branch of ``agent_effects``. Nothing a seat is offered, sees or
is told changes: the Agent-turn effect frame keeps its keys
(``pending_agent_effect``, ``pending_agent_icons``), the rows stay
``resolve_agent_card_effect`` and ``resolve_agent_card_effect(effect=…)``,
and the events keep their names, ids, payloads and order.

The events follow two conventions, one per way a box resolves:

- **One action** (``resolve_box``): the owner's gains (resources, troops,
  the Bene Gesserit boost, the card back to hand), a fixed Faction's
  Influence (prefix ``<box>:influence:<faction>``) and an Intrigue draw
  (source ``<box>:intrigue_draw``) are applied before the frame is written
  back; then the box's event ``<box>`` (``agent_card_effect_resolved``, or
  ``agent_card_effect_unavailable`` when a printed condition fails); then the
  follow-ups that may push a frame above it, named ``<box>`` -- a Contract,
  Research, the Tleilaxu track, specimens, the Intrigue peek, the optional
  trash frame -- and a personal draw named after the card's *definition*
  (``round:R:player:P:agent_card:<card>``). The event list is the box's event,
  the draws' and follow-ups' events, then any recruit shortfall.
- **Icon by icon** (``resolve_box_icon``, OQ-027): the icon's gains, a recruit
  shortfall named ``<box>:<icon>``, and an Intrigue draw named ``<box>:<icon>``
  before the write-back; specimens (``<box>:specimen``) then Research
  (``<box>:research``) and a personal draw (``<box>:<icon>``) after it; the
  icon's event ``<box>:<icon>:resolved`` comes last.

``<box>`` is ``effects.agent_card_source``. A printed condition is judged
when the box resolves (OQ-028); while it fails the single row is withheld
(``agent_effects.agent_card_effect_is_unavailable`` reads the resolution's
``agent_card_effect_unavailable``) or the icon is not offered
(``box_icon_block``, which ``agent_effects.agent_icon_block`` -- read by the
page too -- answers with), and the turn's end fizzles it (OQ-057 (1)). A
record's ``requirement`` is judged when the card is played
(``opens_at_placement``).
"""

from collections.abc import Mapping
from copy import replace
from dataclasses import dataclass
from enum import StrEnum

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.abilities import Ability, AbilityMark
from dune_imperium.content.uprising.agent_abilities import agent_box_ability
from dune_imperium.content.uprising.board import BoardSpace, Faction
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AllConditions,
    AtMakerSpace,
    BoostNextBeneGesseritCard,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EffectSection,
    FactionBond,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    PayResources,
    RecruitTroops,
    Research,
    ReturnThisCardToHand,
    SandwormsInConflictAtLeast,
    SpendSpecimens,
    SpyRecalledThisTurn,
    TakeContract,
    TrashPersonalCard,
    UnitsInConflictAtLeast,
)
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.action_shapes import Source, Verb, template_id
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    advance_after_effect,
    agent_card_source,
    current_agent_effect_context,
    finish_agent_icon,
    is_grafted,
    recruit_shortfall_events,
    recruit_troops,
    short_of,
    spice_gained_this_turn,
)
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.immortality import (
    advance_research,
    advance_tleilaxu,
    tleilaxu_track_finished,
)
from dune_imperium.rules.influence import gain_faction_influence, influence_amount
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.intrigue_peek import begin_intrigue_peek
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.specimens import generate_specimens, spend_specimens
from dune_imperium.rules.spies import gather_intelligence_draw_available

_RESOLVED = "agent_card_effect_resolved"
_UNAVAILABLE = "agent_card_effect_unavailable"


class AgentIconCondition(StrEnum):
    """What a conditioned Agent-box icon waits for (``box_icon_block``)."""

    INFLUENCE = "influence"
    SPICE_GAINED = "spice_gained"
    GRAFTED = "grafted"
    GENETIC_MARKERS = "genetic_markers"
    CONTRACTS_COMPLETED = "contracts_completed"
    # Another card of ``faction`` in play; it can only be lost in a turn.
    BOND = "bond"
    # The Alliance of ``faction`` (any Alliance when None).
    ALLIANCE = "alliance"
    # The box's own card is not in play: a Row card borrowed with Usurp
    # (OQ-054) never is.
    NOT_IN_PLAY = "not_in_play"
    # The icon belongs to no box that prints it; no card queues one.
    NOT_PRINTED = "not_printed"


@dataclass(frozen=True, slots=True)
class AgentIconBlock:
    """Why a conditioned Agent-box icon is not offered now: the printed
    threshold ``needed`` against what the owner has (``held``), and the
    Faction of an Influence threshold."""

    condition: AgentIconCondition
    needed: int = 0
    held: int = 0
    faction: Faction | None = None


NOT_PRINTED_BLOCK = AgentIconBlock(AgentIconCondition.NOT_PRINTED)


class AgentPaymentBlock(StrEnum):
    """Why an Agent box's arrow is withheld because its reward does nothing.

    "비용이 있는 줄은 보상 중 하나라도 무언가를 바꿀 수 있을 때만
    제시한다" (OQ-071, user decision 2026-09-29, generalised from OQ-075;
    precedent OQ-046): a cost that would buy nothing is not offered.
    ``legal_agent_card_payment_actions`` withholds the payment exactly when
    ``agent_card_payment_block`` is not None, and the page's greyed-out row
    reads the same block (``display.unavailable``).
    """

    # Ecological Testing Station's draw: deck and discard pile both empty,
    # so the 2 water would buy nothing (OQ-071). Gather Intelligence is not
    # gated this way: its recall is offered with both piles empty (OQ-099).
    NO_CARD_TO_DRAW = "no_card_to_draw"
    # Tleilaxu Surgeon's and Slig Farmer's advance: the token is on the
    # track's last space, where it does nothing (OQ-048).
    TLEILAXU_TRACK_END = "tleilaxu_track_end"


def box_ability(effect: PersonalCardAgentEffect | None) -> Ability | None:
    """The ability record resolving ``effect``'s Agent box, if it has one."""

    return agent_box_ability(effect)


# --- Conditions ----------------------------------------------------------------


def _requirement_holds(
    condition: Condition, owner: PlayerState, space: BoardSpace, card_id: str
) -> bool:
    """A condition fixed by the placement, judged as the card is played."""

    match condition:
        case AtMakerSpace():
            return space.maker
        case FactionBond(faction=faction):
            # A Row card borrowed with Usurp is not "in play" (OQ-054,
            # ``counted_in_play``), so it never gives another card its Bond.
            return has_faction_bond(
                (*counted_in_play(owner), card_id), card_id, faction
            )
        case AllConditions(conditions=conditions):
            return all(
                _requirement_holds(item, owner, space, card_id) for item in conditions
            )
    raise TypeError(f"{condition!r} is not fixed by the placement")


def opens_at_placement(
    ability: Ability, owner: PlayerState, space: BoardSpace, card_id: str
) -> bool:
    """Whether the box is pending once ``card_id`` is played on ``space``."""

    if ability.requirement is None:
        return True
    return _requirement_holds(ability.requirement, owner, space, card_id)


def condition_block(
    condition: Condition, owner: PlayerState, context: Mapping[str, ActionValue]
) -> AgentIconBlock | None:
    """Why a box's printed condition fails now, or None when it holds."""

    match condition:
        case InfluenceAtLeast(faction=faction, amount=amount):
            held = influence_amount(owner.influence, faction)
            if held >= amount:
                return None
            return AgentIconBlock(
                AgentIconCondition.INFLUENCE, amount, held, faction=faction
            )
        case GainedSpiceThisTurn(amount=amount):
            gained = spice_gained_this_turn(owner)
            if gained >= amount:
                return None
            return AgentIconBlock(AgentIconCondition.SPICE_GAINED, amount, gained)
        case GeneticMarkersAtLeast(count=count):
            markers = genetic_markers_reached(owner.research_space)
            if markers >= count:
                return None
            return AgentIconBlock(AgentIconCondition.GENETIC_MARKERS, count, markers)
        case CompletedContractsAtLeast(count=count):
            completed = len(owner.completed_contract_ids)
            if completed >= count:
                return None
            return AgentIconBlock(
                AgentIconCondition.CONTRACTS_COMPLETED, count, completed
            )
        case FactionBond(faction=faction):
            card_id = context.get("card_id")
            source_id = card_id if isinstance(card_id, str) else ""
            if has_faction_bond(counted_in_play(owner), source_id, faction):
                return None
            return AgentIconBlock(AgentIconCondition.BOND, faction=faction)
        case Grafted():
            if is_grafted(context):
                return None
            return AgentIconBlock(AgentIconCondition.GRAFTED)
        case HasAlliance(faction=faction):
            held_alliance = (
                bool(owner.alliance_faction_ids)
                if faction is None
                else faction.value in owner.alliance_faction_ids
            )
            if held_alliance:
                return None
            return AgentIconBlock(AgentIconCondition.ALLIANCE, faction=faction)
    raise TypeError(f"{condition!r} has no icon block")


def box_condition_holds(
    condition: Condition, owner: PlayerState, context: Mapping[str, ActionValue]
) -> bool:
    """Whether a box's printed condition holds now (judged when it resolves).

    The conditions with no icon block (none sits on an icon line; the
    record table test keeps it so) are judged here, the rest through
    ``condition_block``.
    """

    match condition:
        case SpyRecalledThisTurn():
            # Every recall counts [Main pp. 11, 20].
            return owner.spies_recalled_turn > 0
        case UnitsInConflictAtLeast(count=count):
            # Troops, sandworms, Commanders and an Agent in the Conflict.
            return owner.units_in_conflict >= count
        case ContractCompletedThisTurn():
            return owner.contracts_completed_turn >= 1
        case SandwormsInConflictAtLeast(count=count):
            return owner.sandworms_conflict >= count
        case AllConditions(conditions=conditions):
            return all(
                box_condition_holds(item, owner, context) for item in conditions
            )
    return condition_block(condition, owner, context) is None


def _line_block(
    line: EffectSection, owner: PlayerState, context: Mapping[str, ActionValue]
) -> AgentIconBlock | None:
    """Why an icon's line cannot resolve now: its card left play before a
    return to hand, then its printed condition."""

    if any(isinstance(reward, ReturnThisCardToHand) for reward in line.rewards):
        card_id = context.get("card_id")
        if card_id not in counted_in_play(owner):
            # A Row card borrowed by Usurp is not "in play" and cannot
            # return to a hand (designer ruling, OQ-054); it is trashed
            # when the turn closes.
            return AgentIconBlock(AgentIconCondition.NOT_IN_PLAY)
    if line.condition is None:
        return None
    return condition_block(line.condition, owner, context)


def _line_holds(
    line: EffectSection, owner: PlayerState, context: Mapping[str, ActionValue]
) -> bool:
    if any(isinstance(reward, ReturnThisCardToHand) for reward in line.rewards):
        if context.get("card_id") not in counted_in_play(owner):
            return False
    return line.condition is None or box_condition_holds(
        line.condition, owner, context
    )


def box_icon_block(
    owner: PlayerState, context: Mapping[str, ActionValue], ability: Ability, key: str
) -> AgentIconBlock | None:
    """Why the box's icon ``key`` is not offered now, or None when it is."""

    if key not in ability.icons:
        return NOT_PRINTED_BLOCK
    return _line_block(ability.sections[ability.icons.index(key)], owner, context)


# --- Resolution --------------------------------------------------------------------


def _subject(context: dict[str, ActionValue]) -> tuple[int, str]:
    player = context["turn_owner"]
    card_id = context["card_id"]
    if isinstance(player, bool) or not isinstance(player, int) or not isinstance(
        card_id, str
    ):
        raise RuntimeError("Agent-turn effect frame has invalid subject")
    return player, card_id


def _returned_to_hand(owner: PlayerState, card_id: str) -> PlayerState:
    """The card back from play to the hand, face up so far, so everyone keeps
    knowing it is there (OQ-010). It leaves play by its own effect, so an
    icon still queued pays out (OQ-022)."""

    return replace(
        owner,
        hand=(*owner.hand, card_id),
        hand_public=(*owner.hand_public, card_id),
        in_play=tuple(candidate for candidate in owner.in_play if candidate != card_id),
    )


def _gain(owner: PlayerState, reward: GainResources) -> PlayerState:
    return replace(
        owner,
        resources=replace(
            owner.resources,
            solari=owner.resources.solari + reward.solari,
            spice=owner.resources.spice + reward.spice,
            water=owner.resources.water + reward.water,
        ),
    )


def _credit_recruits(context: dict[str, ActionValue], recruited: int) -> None:
    previous = context.get("troops_recruited")
    if isinstance(previous, bool) or not isinstance(previous, int):
        raise RuntimeError("Agent-turn effect frame has invalid recruit count")
    context["troops_recruited"] = previous + recruited


def _owner_gains(
    owner: PlayerState,
    line: EffectSection,
    context: dict[str, ActionValue],
    card_id: str,
    shortfall_source: str,
    player: int,
) -> tuple[PlayerState, tuple[GameEvent, ...]]:
    """The line's gains on the owner, and any recruit shortfall."""

    shortfall: tuple[GameEvent, ...] = ()
    for reward in line.rewards:
        match reward:
            case GainResources():
                owner = _gain(owner, reward)
            case RecruitTroops(count=count):
                owner, recruited = recruit_troops(owner, count)
                _credit_recruits(context, recruited)
                shortfall = (
                    *shortfall,
                    *recruit_shortfall_events(
                        shortfall_source, player, count, recruited
                    ),
                )
            case BoostNextBeneGesseritCard():
                owner = replace(owner, bene_gesserit_boost_pending=True)
            case ReturnThisCardToHand():
                owner = _returned_to_hand(owner, card_id)
    return owner, shortfall


def _intrigue_draws(line: EffectSection) -> int:
    return sum(
        reward.count for reward in line.rewards if isinstance(reward, DrawIntrigueCards)
    )


def _personal_draws(line: EffectSection, owner: PlayerState) -> int:
    count = 0
    for reward in line.rewards:
        if isinstance(reward, DrawPersonalCards):
            count += reward.count
        elif isinstance(reward, DrawPerSandwormInConflict):
            count += owner.sandworms_conflict
    return count


def resolve_box(state: GameState) -> RuleResult:
    """Resolve the active Agent box as one action (see the module doc)."""

    _, context = current_agent_effect_context(state)
    player, card_id = _subject(context)
    card = active_agent_card(context)
    ability = box_ability(card.agent_effect)
    if (
        ability is None
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
    ):
        raise ValueError("the active Agent box is not resolved as one recorded action")
    (line,) = ability.sections
    owner = state.players[player]
    source = agent_card_source(state.round_number, player, card_id)
    available = _line_holds(line, owner, context)

    next_owner: PlayerState = owner
    shortfall: tuple[GameEvent, ...] = ()
    if available:
        next_owner, shortfall = _owner_gains(
            owner, line, context, card_id, source, player
        )
    working = replace(state, players=replace_player(state.players, next_owner))
    influence_events: tuple[GameEvent, ...] = ()
    for reward in line.rewards if available else ():
        if isinstance(reward, GainInfluence):
            # A fixed Faction's Influence, prefix ``<box>:influence:<f>``.
            assert reward.factions is not None and not reward.requires_choice
            faction = reward.factions[0]
            gained = gain_faction_influence(
                working,
                player,
                faction,
                reward.times,
                event_prefix=f"{source}:influence:{faction.value}",
            )
            working = gained.state
            influence_events = (*influence_events, *gained.events)
    intrigue_events: tuple[GameEvent, ...] = ()
    if available and (intrigue := _intrigue_draws(line)):
        drawn = draw_or_queue_intrigue_cards(
            working, player, intrigue, source=f"{source}:intrigue_draw"
        )
        working, intrigue_events = drawn.state, drawn.events
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(working, context)
    event = GameEvent(
        event_id=source,
        kind=_RESOLVED if available else _UNAVAILABLE,
        payload=(("card_id", card_id), ("player", player)),
    )
    if not available:
        return RuleResult(state=next_state, events=(event,))

    follow_ups: list[GameEvent] = []
    for reward in line.rewards:
        step: RuleResult | None = None
        match reward:
            case TakeContract(count=count):
                step = begin_contract_gain(next_state, player, count, source=source)
            case Research():
                step = advance_research(next_state, player, source=source)
            case AdvanceTleilaxu(count=count):
                step = advance_tleilaxu(next_state, player, count, source=source)
            case GenerateSpecimens(count=count):
                step = generate_specimens(next_state, player, count, source=source)
            case LookAtIntrigueKeepOne():
                step = begin_intrigue_peek(next_state, player, source=source)
            case TrashPersonalCard():
                # The black trash icon on a frame of its own, named after the
                # box so a self-trash keeps its card's effects (OQ-022).
                next_state = next_state.push_decision(
                    optional_trash_frame(player, source)
                )
        if step is not None:
            next_state = step.state
            follow_ups.extend(step.events)
    if draws := _personal_draws(line, owner):
        drawn_cards = draw_or_request_personal_cards(
            next_state,
            player,
            draws,
            source=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card.card.card_id}"
            ),
        )
        next_state = drawn_cards.state
        follow_ups.extend(drawn_cards.events)
    return RuleResult(
        state=next_state,
        events=(event, *influence_events, *intrigue_events, *follow_ups, *shortfall),
    )


def resolve_box_icon(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one printed icon of the active Agent box (see the module doc).

    The caller checks that ``action`` is offered (its condition holds) and
    has already sent Urgent Shigawire's added draw elsewhere.
    """

    _, context = current_agent_effect_context(state)
    player, card_id = _subject(context)
    card = active_agent_card(context)
    ability = box_ability(card.agent_effect)
    key = dict(action.arguments).get("effect")
    if ability is None or not isinstance(key, str) or key not in ability.icons:
        raise ValueError("the action names no recorded icon of the active Agent box")
    line = ability.sections[ability.icons.index(key)]
    owner = state.players[player]
    source = agent_card_source(state.round_number, player, card_id)
    finish_agent_icon(context, key)
    available = _line_holds(line, owner, context)

    next_owner: PlayerState = owner
    shortfall: tuple[GameEvent, ...] = ()
    if available:
        next_owner, shortfall = _owner_gains(
            owner, line, context, card_id, f"{source}:{key}", player
        )
    effect_state = replace(state, players=replace_player(state.players, next_owner))
    intrigue_events: tuple[GameEvent, ...] = ()
    if available and (intrigue := _intrigue_draws(line)):
        drawn = draw_or_queue_intrigue_cards(
            effect_state, player, intrigue, source=f"{source}:{key}"
        )
        effect_state, intrigue_events = drawn.state, drawn.events
    next_state = advance_after_effect(effect_state, context)
    track_events: tuple[GameEvent, ...] = ()
    if available:
        # Industrial Espionage's grafted line: the specimen, then the
        # Research step, as one icon [Immortality pp. 6, 8].
        for reward in line.rewards:
            if isinstance(reward, GenerateSpecimens):
                generated = generate_specimens(
                    next_state, player, reward.count, source=f"{source}:specimen"
                )
                next_state = generated.state
                track_events = (*track_events, *generated.events)
        for reward in line.rewards:
            if isinstance(reward, Research):
                researched = advance_research(
                    next_state, player, source=f"{source}:research"
                )
                next_state = researched.state
                track_events = (*track_events, *researched.events)
    draw_events: tuple[GameEvent, ...] = ()
    if available and (draws := _personal_draws(line, owner)):
        drawn_cards = draw_or_request_personal_cards(
            next_state, player, draws, source=f"{source}:{key}"
        )
        next_state, draw_events = drawn_cards.state, drawn_cards.events
    event = GameEvent(
        event_id=f"{source}:{key}:resolved",
        kind=_RESOLVED if available else _UNAVAILABLE,
        payload=(("card_id", card_id), ("effect", key), ("player", player)),
    )
    return RuleResult(
        state=next_state,
        events=(*shortfall, *intrigue_events, *track_events, *draw_events, event),
    )


# --- Optional arrows with no target (stage A3b) ----------------------------------
#
# "You may pay X -> Y" with nothing to pick: one row naming the cost
# (``pay_agent_card_<variant>``) beside the refusal the provider keeps for the
# box's raw rows (the turn drops it, ``agent_effect_frame._without_refusal``).
# The answer pays, gains, writes the frame back, names its event
# ``round:R:player:P:agent_card_payment:paid`` (no card id) with the resource
# and the amount spent, then runs the follow-ups that may push a frame: a
# draw named ``…:agent_card_payment``, a Tleilaxu advance named
# ``…:agent_card_payment:tleilaxu``.

_PAYMENT_SOURCE = "round:{round}:player:{player}:agent_card_payment"


def payment_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional arrow paid with no target to pick."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
    ):
        return False
    costs = ability.sections[0].costs
    return len(costs) == 1 and isinstance(costs[0], PayResources | SpendSpecimens)


def _payment_cost(ability: Ability) -> PayResources | SpendSpecimens:
    cost = ability.sections[0].costs[0]
    assert isinstance(cost, PayResources | SpendSpecimens)
    return cost


def _paid_resource(cost: PayResources | SpendSpecimens) -> tuple[str, int]:
    """The resource the payment event names, and how much was spent."""

    match cost:
        case SpendSpecimens(count=count):
            return "specimen", count
        case PayResources(solari=0, spice=0, water=water) if water:
            return "water", water
        case PayResources(solari=0, spice=spice, water=0) if spice:
            return "spice", spice
    raise ValueError(f"no payment row pays {cost!r}")


def _payment_template(cost: PayResources | SpendSpecimens) -> str:
    resource, spent = _paid_resource(cost)
    variant = "two_specimens" if resource == "specimen" and spent == 2 else resource
    return template_id(Verb.PAY, Source.AGENT_CARD, variant=variant)


def payment_cost_block(
    owner: PlayerState, ability: Ability
) -> OptionalEffectBlock | None:
    """Why the arrow's cost cannot be paid now, or None."""

    match _payment_cost(ability):
        case SpendSpecimens(count=count):
            return short_of(OptionalBlockKind.SPECIMENS, count, owner.specimens)
        case PayResources(solari=solari, spice=spice, water=water):
            return (
                short_of(OptionalBlockKind.SOLARI, solari, owner.resources.solari)
                if solari
                else None
            ) or (
                short_of(OptionalBlockKind.SPICE, spice, owner.resources.spice)
                if spice
                else None
            ) or (
                short_of(OptionalBlockKind.WATER, water, owner.resources.water)
                if water
                else None
            )
    return None


def payment_reward_block(
    state: GameState, player: int, ability: Ability
) -> AgentPaymentBlock | None:
    """Why the arrow would buy nothing now (OQ-071), or None."""

    for reward in ability.sections[0].rewards:
        if isinstance(reward, DrawPersonalCards) and not (
            gather_intelligence_draw_available(state, player)
        ):
            return AgentPaymentBlock.NO_CARD_TO_DRAW
        if isinstance(reward, AdvanceTleilaxu) and tleilaxu_track_finished(
            state.players[player]
        ):
            return AgentPaymentBlock.TLEILAXU_TRACK_END
    return None


def payment_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The box's raw rows: its refusal, then its payment while it can buy
    something; the arrow cost is judged again whenever the box resolves, in
    the owner's order [Main pp. 9, 20] (OQ-028)."""

    decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
    if (
        payment_cost_block(state.players[player], ability) is not None
        or payment_reward_block(state, player, ability) is not None
    ):
        return (decline,)
    return (
        decline,
        DomainAction(action_id=_payment_template(_payment_cost(ability)), actor=player),
    )


def apply_payment(
    state: GameState, player: int, ability: Ability, context: dict[str, ActionValue]
) -> RuleResult:
    """Pay the arrow and take what it buys (``context`` has its pending flag
    already cleared by the caller)."""

    source = _PAYMENT_SOURCE.format(round=state.round_number, player=player)
    cost = _payment_cost(ability)
    owner = state.players[player]
    match cost:
        case SpendSpecimens(count=count):
            # The specimens return to the supply as they are spent
            # [Immortality p. 8].
            owner = spend_specimens(owner, count)
        case PayResources(solari=solari, spice=spice, water=water):
            owner = replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari - solari,
                    spice=owner.resources.spice - spice,
                    water=owner.resources.water - water,
                ),
                spice_spent_turn=owner.spice_spent_turn + spice,
            )
    for reward in ability.sections[0].rewards:
        match reward:
            case GainResources():
                owner = _gain(owner, reward)
            case GainVictoryPoints(amount=amount):
                owner = replace(owner, victory_points=owner.victory_points + amount)
    next_state = advance_after_effect(
        state, context, replace_player(state.players, owner)
    )
    resource, spent = _paid_resource(cost)
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:paid",
            kind="agent_card_payment_resolved",
            payload=(("player", player), ("resource", resource), ("spent", spent)),
        )
    ]
    for reward in ability.sections[0].rewards:
        step: RuleResult | None = None
        match reward:
            case AdvanceTleilaxu(count=count):
                step = advance_tleilaxu(
                    next_state, player, count, source=f"{source}:tleilaxu"
                )
            case DrawPersonalCards(count=count):
                step = draw_or_request_personal_cards(
                    next_state, player, count, source=source
                )
        if step is not None:
            next_state = step.state
            events.extend(step.events)
    return RuleResult(state=next_state, events=tuple(events))
