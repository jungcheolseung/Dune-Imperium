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
from typing import Final

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
)
from dune_imperium.content.uprising.agent_abilities import agent_box_ability
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, BoardSpace, Faction
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AllConditions,
    AtMakerSpace,
    BoostNextBeneGesseritCard,
    CommandersInConflictAtLeast,
    CompleteContract,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    DiscardedCardHasFaction,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    GraftedWithFaction,
    GrantCombatDeployment,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    LoseTroops,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecruitTroops,
    Research,
    ReturnThisCardToHand,
    Reward,
    SandwormsInConflictAtLeast,
    SpendSpecimens,
    SpyRecalledThisTurn,
    TakeContract,
    TrashCard,
    TrashedCardHasFaction,
    TrashIntrigueCard,
    TrashPersonalCard,
    TrashThisCard,
    UnitsInConflictAtLeast,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.ability_executor import piece_rows
from dune_imperium.rules.acquisition import agent_box_acquisition
from dune_imperium.rules.action_shapes import Source, Verb, template_id
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import keep_trash_recruits, trash_personal_card
from dune_imperium.rules.combat_deployment import reconcile_deployment_after_retreat
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    advance_after_effect,
    agent_card_source,
    arm_agent_icons,
    current_agent_effect_context,
    finish_agent_icon,
    is_grafted,
    other_grafted_card_id,
    recruit_shortfall_events,
    recruit_troops,
    short_of,
    spice_gained_this_turn,
)
from dune_imperium.rules.frames import context_int, replace_player
from dune_imperium.rules.immortality import (
    advance_research,
    advance_tleilaxu,
    tleilaxu_track_finished,
)
from dune_imperium.rules.influence import gain_faction_influence, influence_amount
from dune_imperium.rules.intrigue_deck import (
    draw_or_queue_intrigue_cards,
    with_trashed_intrigue,
)
from dune_imperium.rules.intrigue_peek import begin_intrigue_peek
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.specimens import generate_specimens, spend_specimens
from dune_imperium.rules.spies import gather_intelligence_draw_available
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_factions,
    solo_occupied_post_ids,
)
from dune_imperium.rules.unit_loss import lose_unit

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
        case GraftedWithFaction(factions=factions):
            # The other grafted card's printed Factions; a Ghola copy's
            # partner is the card it copies.
            partner = other_grafted_card_id(context)
            return bool(partner) and any(
                faction in personal_card_for_instance(partner).factions
                for faction in factions
            )
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
        or (
            len(ability.sections) != 1
            and not trash_box(ability)
            and not discard_box(ability)
            and not lose_box(ability)
            and not either_box(ability)
        )
    ):
        raise ValueError("the active Agent box is not resolved as one recorded action")
    line = ability.sections[0]
    owner = state.players[player]
    source = agent_card_source(state.round_number, player, card_id)
    if lose_box(ability):
        # Piter: an optional arrow resolves through its rows; reached by the
        # dry run only, which keeps its old answer -- the box unavailable
        # (its provider offered nothing).
        available = False
    elif agent_box_acquisition(ability) is not None:
        # Tleilaxu Master: an optional acquisition resolves through its rows;
        # reached by the dry run only, which keeps its old answer -- the box
        # unavailable (its provider offered nothing).
        available = False
    elif trash_box(ability):
        # Ruthless Leadership: reached by the dry run only (the press lapses
        # the optional box first; ``optional_arrow`` keeps the unconditioned
        # trash boxes out); its Commander condition is judged now (OQ-028),
        # and without it the box resolves without effect.
        if _trash_conditions_hold(owner, ability):
            raise RuntimeError("Agent-card trash effect requires a player choice")
        available = False
    elif discard_box(ability) and context.get("agent_card_spy_pending") is True:
        # Arrakis Observer's Deep Cover Spy after its paid discard: placing
        # is mandatory only with a Spy in supply (the erratum to [Main
        # p. 11], OQ-057 (14)); the recall-first and its pass-up are the
        # owner's choice [Main pp. 11, 20], so the box fizzles here only
        # when neither is possible, and then waits for the turn's end
        # (OQ-057 (1)).
        spy = discard_spy(ability)
        if spy is not None and agent_spy_rows(state, player, spy, context):
            raise RuntimeError("place-Spy Agent effect requires a player choice")
        context.pop("agent_card_spy_pending", None)
        context.pop("agent_card_spy_recalled", None)
        available = False
    elif discard_box(ability):
        # Guild Envoy's mandatory discard resolves through its rows; with an
        # empty hand the box waits and fizzles (OQ-057 (1), OQ-028).
        if discard_rows(state, player, ability):
            raise RuntimeError("Agent-card discard effect requires a player choice")
        available = False
    else:
        available = _line_holds(line, owner, context)
    if (piece := target_piece(ability)) is not None:
        # A target choice resolves through its rows; reached with one to make
        # is a caller's error, and with none the box waits and fizzles
        # (OQ-057 (1)) -- a Spy box dropping its recall-first marks.
        if target_rows(state, player, ability):
            raise target_choice_error(ability)
        if isinstance(piece, PlaceSpy):
            context.pop("agent_card_spy_pending", None)
            context.pop("agent_card_spy_recalled", None)
        available = False

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

    base = state
    next_owner: PlayerState = owner
    shortfall: tuple[GameEvent, ...] = ()
    if any(isinstance(reward, TrashThisCard) for reward in line.rewards):
        # Dangerous Rhetoric's "Trash this card.": the card trashes itself by
        # its own printed icon, so any icon still queued keeps paying out
        # (OQ-022); gone from play already, the icon does nothing.
        if available and card_id in owner.in_play:
            context["agent_card_self_trashed"] = True
            trashed = trash_personal_card(state, player, card_id, source=source)
            keep_trash_recruits(context, trashed)
            base = trashed.state
            next_owner = base.players[player]
            shortfall = trashed.events
        else:
            available = False
    elif available:
        next_owner, shortfall = _owner_gains(
            owner, line, context, card_id, f"{source}:{key}", player
        )
    effect_state = replace(base, players=replace_player(base.players, next_owner))
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
# The rewards ``apply_payment`` gives; a record with any other is no payment
# box (it keeps its own code until a stage moves it).
_PAYMENT_REWARDS = (
    GainResources,
    GainVictoryPoints,
    DrawPersonalCards,
    AdvanceTleilaxu,
)


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
    (section,) = ability.sections
    if len(section.costs) != 1 or not all(
        isinstance(reward, _PAYMENT_REWARDS) for reward in section.rewards
    ):
        return False
    try:
        _paid_resource(section.costs[0])
    except ValueError:
        return False
    return True


def _payment_cost(ability: Ability) -> PayResources | SpendSpecimens:
    cost = ability.sections[0].costs[0]
    assert isinstance(cost, PayResources | SpendSpecimens)
    return cost


def _paid_resource(cost: object) -> tuple[str, int]:
    """The resource the payment event names, and how much was spent; a cost
    no payment row pays raises ``ValueError``."""

    match cost:
        case SpendSpecimens(count=count) if count in (1, 2):
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


# --- A choice of target (stage A3c) --------------------------------------------
#
# A mandatory box whose line is one target choice -- a chosen Faction's
# Influence, a Spy's post, an enemy unit to retreat, a Contract to complete:
# its rows are offered while its condition holds; with none to choose it
# offers no confirmation and waits, and the turn's end fizzles it with the
# box's unavailable event (OQ-057 (1), OQ-060). The rows keep the Agent-box
# rules, which differ from the A1 executor's for a Spy (the recall-first and
# its pass-up below). The chosen Influence is answered here (its events are
# the gain's alone); a Spy, a retreat and a Contract keep their handlers in
# ``agent_effects``, named after their own actions.

type TargetPiece = GainInfluence | PlaceSpy | ForceEnemyRetreat | CompleteContract

_TARGET_CHOICE_ERRORS: Final[Mapping[type, tuple[type[Exception], str]]] = {
    GainInfluence: (
        RuntimeError,
        "Agent-card Influence effect requires a player choice",
    ),
    PlaceSpy: (RuntimeError, "place-Spy Agent effect requires a player choice"),
    ForceEnemyRetreat: (RuntimeError, "enemy retreat requires a player choice"),
    CompleteContract: (
        ValueError,
        "CHOAM Demands resolves through complete_contract_by_card",
    ),
}


def target_piece(ability: Ability | None) -> TargetPiece | None:
    """The one target ``ability``'s mandatory line chooses, if it is one."""

    if (
        ability is None
        or ability.mark is not AbilityMark.MANDATORY
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
        or ability.sections[0].costs
        or len(ability.sections[0].rewards) != 1
    ):
        return None
    (piece,) = ability.sections[0].rewards
    match piece:
        case GainInfluence(requires_choice=True, times=1):
            return piece
        case PlaceSpy(agent_icons=None):
            return piece
        case ForceEnemyRetreat() | CompleteContract():
            return piece
    return None


def target_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The box's choices now: none while its condition fails."""

    piece = target_piece(ability)
    if piece is None:
        raise ValueError("the Agent box chooses no recorded target")
    _, context = current_agent_effect_context(state)
    (line,) = ability.sections
    if not _line_holds(line, state.players[player], context):
        return ()
    match piece:
        case GainInfluence():
            return piece_rows(
                state,
                player,
                piece,
                Source.AGENT_CARD,
                refusals=False,
                empty_confirm=False,
            )
        case PlaceSpy():
            return agent_spy_rows(state, player, piece, context)
        case ForceEnemyRetreat():
            return _enemy_retreat_rows(state, player)
        case CompleteContract():
            return tuple(
                DomainAction(
                    action_id="complete_contract_by_card",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in state.players[player].active_contract_ids
            )


def _enemy_retreat_rows(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """One row per opponent with troops in the Conflict, then one per opponent
    with Commanders there, in seat order (OQ-034)."""

    rows: list[DomainAction] = []
    for seat in state.players:
        if seat.player_id == player:
            continue
        if seat.troops_conflict > 0:
            rows.append(
                DomainAction(
                    action_id="retreat_opponent_troop",
                    actor=player,
                    arguments=(("player", seat.player_id),),
                )
            )
        if seat.commanders_conflict > 0:
            rows.append(
                DomainAction(
                    action_id="retreat_opponent_troop",
                    actor=player,
                    arguments=(("commanders", 1), ("player", seat.player_id)),
                )
            )
    return tuple(rows)


def agent_spy_rows(
    state: GameState,
    player: int,
    piece: PlaceSpy,
    context: Mapping[str, ActionValue],
) -> tuple[DomainAction, ...]:
    """An Agent box's Spy rows: placement, recall-first, or its pass-up.

    Placing is mandatory while a Spy is in the supply (the erratum to
    [Main p. 11], OQ-057 (14)). Without one, "If you have no Spies in your
    supply when you need to place one, you may first recall one of your
    Spies for no effect" [Main pp. 11, 20]: the owner may pass the icon up
    (``decline_agent_card_spy``) when the box resolves -- the Agent box and
    the space's effects resolve in any order [Main p. 9] -- and once the
    recall is made the Spy has to be placed. An unlimited piece takes the
    card's printed Faction marks (``agent_spy_factions``, which a Ghola copy
    keeps from its partner).
    """

    owner = state.players[player]
    card = active_agent_card(context)
    allowed_post_ids: frozenset[str] | None = None
    if piece.visited_space:
        # Double Agent: "[Spy] spying on the board space you sent an Agent to
        # this turn" -- a placement limit in the "[Spy] on [icon]" sense ("the
        # observation post must connect to a ... board space" [Main p. 20]).
        visited_space_id = context.get("space_id")
        allowed_post_ids = frozenset(
            post.post_id
            for post in OBSERVATION_POSTS
            if visited_space_id in post.connected_space_ids
        )
    elif piece.factions is not None:
        allowed_post_ids = observation_post_ids_for_factions(piece.factions)
    elif not piece.shared_post and card.agent_spy_factions:
        # A shared-post Spy (Deep Cover) never reads the marks: only a
        # place-Spy card prints them (the card tables refuse them elsewhere).
        allowed_post_ids = observation_post_ids_for_factions(card.agent_spy_factions)
    if piece.shared_post:
        # Another player's Spy may share the post, never the owner's own
        # [Bloodlines pp. 5, 12; Double Agent card].
        placements = tuple(
            post.post_id
            for post in OBSERVATION_POSTS
            if (allowed_post_ids is None or post.post_id in allowed_post_ids)
            and post.post_id not in owner.spy_post_ids
        )
    else:
        placements = empty_observation_post_ids(state, allowed_post_ids)
    # Placement needs a Spy in supply right now [Main pp. 11, 20]; a recall
    # made earlier this turn may already have been consumed by another effect
    # (e.g. the Espionage board space), in which case another recall is offered.
    if owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_agent_card_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in placements
        )
    recall_post_ids = owner.spy_post_ids
    if not placements and piece.shared_post:
        recall_post_ids = tuple(
            post_id
            for post_id in owner.spy_post_ids
            if allowed_post_ids is None or post_id in allowed_post_ids
        )
    elif not placements:
        # Only a recall that leaves its post empty opens a placement: a post
        # shared with another player's Spy (Deep Cover) stays occupied
        # [Main pp. 11, 20] (``solo_occupied_post_ids``).
        recall_post_ids = solo_occupied_post_ids(state, player, allowed_post_ids)
    recalls = tuple(
        DomainAction(
            action_id="recall_spy_for_agent_card",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in recall_post_ids
    )
    if not recalls or context.get("agent_card_spy_recalled") is True:
        # With nothing to recall the box waits for the turn's end like any
        # box that can only fizzle (OQ-057 (1)); after a recall-first the
        # placement is mandatory, even if another freely ordered effect
        # (Espionage) spent that Spy meanwhile.
        return recalls
    return (DomainAction(action_id="decline_agent_card_spy", actor=player), *recalls)


def target_blocked(state: GameState, player: int, ability: Ability) -> bool:
    """Whether the box's condition holds yet it has nothing to choose: every
    Faction it may raise at the top (OQ-060), so it waits for the turn's
    end (OQ-057 (1)); the page names this reason (``display.unavailable``)."""

    _, context = current_agent_effect_context(state)
    (line,) = ability.sections
    return _line_holds(line, state.players[player], context) and not target_rows(
        state, player, ability
    )


def target_choice_error(ability: Ability) -> Exception:
    """What resolving the box as one action raises while it has a choice."""

    piece = target_piece(ability)
    if piece is None:
        raise ValueError("the Agent box chooses no recorded target")
    kind, message = _TARGET_CHOICE_ERRORS[type(piece)]
    return kind(message)


def apply_chosen_influence(state: GameState, action: DomainAction) -> RuleResult:
    """Gain the chosen Faction's Influence and close the box."""

    _, context = current_agent_effect_context(state)
    player, card_id = _subject(context)
    faction = Faction(str(dict(action.arguments)["faction"]))
    source = agent_card_source(state.round_number, player, card_id)
    gained = gain_faction_influence(
        state, player, faction, 1, event_prefix=f"{source}:influence:{faction.value}"
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    return RuleResult(state=next_state, events=gained.events)


# --- Discard arrows (stage A3d) -------------------------------------------------
#
# "[You may] discard a card -> reward": the refusal of an optional arrow,
# then one row per hand card; with an empty hand an optional arrow offers
# only its refusal (``discard_cost_block``) and the mandatory one waits and
# fizzles (OQ-057 (1)). The answer discards with source
# ``round:R:player:P:agent_card_discard`` (no card id) and pays the lines
# whose condition the discarded card meets: resources with the write-back,
# then a Contract named ``<that>:contract_reward``, then one draw named
# ``<that>:<discarded card>:draw`` (Space-time Folding's second card, Guild
# Envoy's two). A gain that depends on the discarded card announces itself
# (``<that>:<discarded card>:<resource>``, Arrakis Observer's 2 spice), and a
# Spy line leaves the box pending on its Spy step (``agent_card_spy_pending``,
# the rows ``agent_spy_rows``; a Spy placement is mandatory, OQ-057 (14)).
# The events are the discard's, then the follow-ups'. An arrow
# whose rewards are armed (``Ability.armed_icons``: Captured Mentat, Guild
# Spy) pays nothing at once: the keys of the lines the discarded card meets
# are queued in printed order (``effects.arm_agent_icons``), each resolved
# on its own by the icon path (OQ-027), and the box is then mandatory.

_DISCARD_SOURCE: Final = "agent_card_discard"
_DISCARD_REWARDS = (GainResources, TakeContract, DrawPersonalCards, PlaceSpy)
# The reward each armed key resolves (``agent_effects.resolve_agent_card_icon``).
# That path offers and pays a key per effect (Branching Path's 2 spice), so
# the record table test keeps each key to the boxes it serves.
_ARMED_REWARDS: Final[Mapping[str, tuple[Reward, ...]]] = {
    "intrigue": (DrawIntrigueCards(1),),
    # Piter's ``cards`` draws two.
    "cards": (DrawPersonalCards(1), DrawPersonalCards(2)),
    "spice": (GainResources(spice=2),),
    "troops": (RecruitTroops(1),),
    "pledge": (PledgeFirstPlaceInfluence(),),
    "research": (Research(),),
}


def _armed_line(key: str, line: EffectSection) -> bool:
    """Whether ``line`` is the one reward the icon path pays for ``key``."""

    return len(line.rewards) == 1 and line.rewards[0] in _ARMED_REWARDS.get(key, ())


def discard_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is a discard arrow (one hand card pays it)."""

    if (
        ability is None
        or ability.icons
        or ability.hook is not None
        or ability.mark is AbilityMark.AUTOMATIC
        or not ability.sections
    ):
        return False
    first, *rest = ability.sections
    if first.costs != (DiscardFromHand(),) or any(line.costs for line in rest):
        return False
    if any(
        line.condition is not None
        and not isinstance(line.condition, DiscardedCardHasFaction)
        for line in ability.sections
    ):
        return False
    if ability.armed_icons:
        # Every line armed: a trailing line paid at once is not this shape.
        return len(ability.armed_icons) == len(ability.sections) and all(
            _armed_line(key, line)
            for key, line in zip(ability.armed_icons, ability.sections, strict=False)
        )
    return all(
        isinstance(reward, _DISCARD_REWARDS)
        for line in ability.sections
        for reward in line.rewards
    )


def discard_spy(ability: Ability) -> PlaceSpy | None:
    """The Spy a discard arrow places once paid (Arrakis Observer's Deep Cover)."""

    for line in ability.sections:
        for reward in line.rewards:
            if isinstance(reward, PlaceSpy):
                return reward
    return None


def optional_arrow(ability: Ability | None) -> bool:
    """An optional arrow, resolved only through its rows: the generic
    resolution keeps the dry-run answer it had before the record (not
    implemented, read as available) -- the payment, Intrigue, unconditioned
    trash and optional discard boxes, and Price is No Object's acquisition
    (the acquisition shape is ``rules.acquisition.agent_box_acquisition``,
    kept there because this module imports the executor, which imports
    acquisitions). Ruthless Leadership's trash icons and Tleilaxu Master's
    conditioned acquisition are not one: their old answer is the
    unavailable event."""

    if ability is None:
        return False
    acquisition = agent_box_acquisition(ability)
    return (
        payment_box(ability)
        or intrigue_box(ability)
        or (acquisition is not None and acquisition[1] is None)
        or (trash_box(ability) and not _trash_conditions(ability))
        or (discard_box(ability) and ability.mark is AbilityMark.OPTIONAL)
    )


def discard_cost_block(
    owner: PlayerState, ability: Ability
) -> OptionalEffectBlock | None:
    """An optional discard with no card in hand; None for the mandatory one."""

    if ability.mark is not AbilityMark.OPTIONAL:
        return None
    return short_of(OptionalBlockKind.HAND, 1, len(owner.hand))


def discard_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The refusal of an optional arrow, then one discard per hand card."""

    owner = state.players[player]
    decline = (
        (DomainAction(action_id="decline_agent_card_discard", actor=player),)
        if ability.mark is AbilityMark.OPTIONAL
        else ()
    )
    if discard_cost_block(owner, ability) is not None:
        return decline
    return (
        *decline,
        *(
            DomainAction(
                action_id="discard_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in owner.hand
        ),
    )


def apply_discard(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Refuse the arrow, or discard the chosen card and pay its lines."""

    _, context = current_agent_effect_context(state)
    context["pending_agent_effect"] = False
    player = action.actor
    source = f"round:{state.round_number}:player:{player}:{_DISCARD_SOURCE}"
    if action.action_id == "decline_agent_card_discard":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_discard_declined",
                    payload=(("player", player),),
                ),
            ),
        )
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card discard choice has invalid card ID")
    factions = personal_card_for_instance(card_id).factions
    discarded = discard_personal_card_from_hand(state, player, card_id, source=source)
    met = tuple(
        not isinstance(line.condition, DiscardedCardHasFaction)
        or line.condition.faction in factions
        for line in ability.sections
    )
    if ability.armed_icons:
        arm_agent_icons(
            context,
            tuple(key for key, ok in zip(ability.armed_icons, met, strict=True) if ok),
        )
        return RuleResult(
            state=advance_after_effect(
                discarded.state, context, discarded.state.players
            ),
            events=discarded.events,
        )
    rewards = tuple(
        reward
        for line, ok in zip(ability.sections, met, strict=True)
        if ok
        for reward in line.rewards
    )
    owner = discarded.state.players[player]
    events = list(discarded.events)
    for line, ok in zip(ability.sections, met, strict=True):
        for reward in line.rewards if ok else ():
            if not isinstance(reward, GainResources):
                continue
            owner = _gain(owner, reward)
            if isinstance(line.condition, DiscardedCardHasFaction):
                events.extend(
                    GameEvent(
                        event_id=f"{source}:{card_id}:{resource}",
                        kind=_RESOLVED,
                        payload=(("player", player), (resource, amount)),
                    )
                    for resource, amount in (
                        ("solari", reward.solari),
                        ("spice", reward.spice),
                        ("water", reward.water),
                    )
                    if amount
                )
    if any(isinstance(reward, PlaceSpy) for reward in rewards):
        context["pending_agent_effect"] = True
        context["agent_card_spy_pending"] = True
    next_state = advance_after_effect(
        discarded.state, context, replace_player(discarded.state.players, owner)
    )
    for reward in rewards:
        if isinstance(reward, TakeContract):
            contracts = begin_contract_gain(
                next_state, player, reward.count, source=f"{source}:contract_reward"
            )
            next_state = contracts.state
            events.extend(contracts.events)
    if draws := sum(
        reward.count for reward in rewards if isinstance(reward, DrawPersonalCards)
    ):
        drawn = draw_or_request_personal_cards(
            next_state, player, draws, source=f"{source}:{card_id}:draw"
        )
        next_state = drawn.state
        events.extend(drawn.events)
    return RuleResult(state=next_state, events=tuple(events))


# --- Intrigue arrows (stage A3d) ------------------------------------------------
#
# "If <Faction> Alliance: You may trash an Intrigue card [and pay N spice] ->
# reward" (Branching Path, Junction Headquarters): the refusal, then one row
# per Intrigue card in hand -- ``trash_intrigue_for_agent_card``, or
# ``pay_agent_card_intrigue_and_spice`` when spice is paid too -- while the
# Alliance, the spice and an Intrigue card are there (judged when the cost is
# paid, OQ-028: ``intrigue_cost_block``), else the refusal alone. The trashed
# card joins the Intrigue discard (OQ-061). Events are named
# ``<box>:intrigue_payment``: the trash, then the spice paid; armed rewards
# (Branching Path's Intrigue draw and 2 spice) wait as icons (OQ-027), other
# rewards (Junction's VP, with no event of its own) are paid at once.

_INTRIGUE_TRASH: Final = TrashIntrigueCard()


def intrigue_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional arrow paid by trashing an Intrigue card."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or not ability.sections
    ):
        return False
    first, *rest = ability.sections
    if _INTRIGUE_TRASH not in first.costs or any(line.costs for line in rest):
        return False
    if any(
        cost != _INTRIGUE_TRASH and _intrigue_spice(cost) is None
        for cost in first.costs
    ):
        return False
    if first.condition is not None and not (
        isinstance(first.condition, HasAlliance) and first.condition.faction is not None
    ):
        # A named Faction's Alliance, judged by ``intrigue_cost_block``.
        return False
    if any(line.condition is not None for line in rest):
        return False
    if ability.armed_icons:
        # Every line armed: a trailing line paid at once is not this shape.
        return len(ability.armed_icons) == len(ability.sections) and all(
            _armed_line(key, line)
            for key, line in zip(ability.armed_icons, ability.sections, strict=False)
        )
    return not rest and all(
        isinstance(reward, (GainVictoryPoints, GainResources))
        for reward in first.rewards
    )


def _intrigue_spice(cost: object) -> int | None:
    match cost:
        case PayResources(solari=0, spice=spice, water=0) if spice:
            return spice
    return None


def _spice_cost(ability: Ability) -> int:
    return sum(
        spice
        for cost in ability.sections[0].costs
        if (spice := _intrigue_spice(cost)) is not None
    )


def intrigue_cost_block(
    owner: PlayerState, ability: Ability
) -> OptionalEffectBlock | None:
    """The Alliance, then the spice, then an Intrigue card to trash."""

    condition = ability.sections[0].condition
    if (
        isinstance(condition, HasAlliance)
        and condition.faction is not None
        and condition.faction.value not in owner.alliance_faction_ids
    ):
        return OptionalEffectBlock(
            OptionalBlockKind.ALLIANCE, faction=condition.faction.value
        )
    if spice := _spice_cost(ability):
        block = short_of(OptionalBlockKind.SPICE, spice, owner.resources.spice)
        if block is not None:
            return block
    if not owner.intrigue_cards:
        return OptionalEffectBlock(OptionalBlockKind.INTRIGUE)
    return None


def intrigue_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The refusal, then one row per Intrigue card while the cost is payable."""

    owner = state.players[player]
    decline = DomainAction(
        action_id="decline_agent_card_intrigue_payment", actor=player
    )
    if intrigue_cost_block(owner, ability) is not None:
        return (decline,)
    action_id = (
        "pay_agent_card_intrigue_and_spice"
        if _spice_cost(ability)
        else "trash_intrigue_for_agent_card"
    )
    return (
        decline,
        *(
            DomainAction(
                action_id=action_id,
                actor=player,
                arguments=(("intrigue_card_id", card_id),),
            )
            for card_id in owner.intrigue_cards
        ),
    )


def apply_intrigue_payment(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Refuse the arrow, or trash the Intrigue card, pay and take the rewards."""

    _, context = current_agent_effect_context(state)
    # Paying or skipping spends the card's one arrow choice for this turn
    # [Main p. 9] [FAQ p. 3].
    context["pending_agent_effect"] = False
    player, card_id = _subject(context)
    box = agent_card_source(state.round_number, player, card_id)
    source = f"{box}:intrigue_payment"
    if action.action_id == "decline_agent_card_intrigue_payment":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_payment_declined",
                    payload=(("card_id", card_id), ("player", player)),
                ),
            ),
        )
    intrigue_card_id = dict(action.arguments).get("intrigue_card_id")
    if not isinstance(intrigue_card_id, str):
        raise RuntimeError("Agent-card Intrigue payment has invalid card ID")
    owner = state.players[player]
    owner = replace(
        owner,
        intrigue_cards=tuple(
            held for held in owner.intrigue_cards if held != intrigue_card_id
        ),
    )
    events = [
        GameEvent(
            event_id=f"{source}:intrigue_trashed:{intrigue_card_id}",
            kind="intrigue_card_trashed",
            payload=(("card_id", intrigue_card_id), ("player", player)),
        )
    ]
    if ability.armed_icons:
        # Every key: the Alliance printed over the whole arrow gated the cost
        # line's rows (``intrigue_cost_block``), and no later line has a
        # condition of its own (``intrigue_box``).
        arm_agent_icons(context, ability.armed_icons)
    else:
        if spice := _spice_cost(ability):
            owner = replace(
                owner,
                resources=replace(
                    owner.resources, spice=owner.resources.spice - spice
                ),
                spice_spent_turn=owner.spice_spent_turn + spice,
            )
            events.append(
                GameEvent(
                    event_id=f"{source}:paid",
                    kind="agent_card_payment_resolved",
                    payload=(
                        ("card_id", card_id),
                        ("player", player),
                        ("resource", "spice"),
                        ("spent", spice),
                    ),
                )
            )
        for reward in ability.sections[0].rewards:
            match reward:
                case GainVictoryPoints(amount=amount):
                    owner = replace(owner, victory_points=owner.victory_points + amount)
                case GainResources():
                    owner = _gain(owner, reward)
    next_state = advance_after_effect(
        with_trashed_intrigue(state, intrigue_card_id),
        context,
        replace_player(state.players, owner),
    )
    return RuleResult(state=next_state, events=tuple(events))


# --- Trash boxes (stage A3e) ----------------------------------------------------
#
# Black trash icons (Calculus of Power's one, Ruthless Leadership's two under
# its Commander condition) and arrows paid by trashing a card (Shishakli's
# draw, Pivotal Gambit's armed troop and pledge). Rows: the refusal, then one
# per card the trash may take -- hand, discard pile and cards in play (a
# Usurped Row card is not in play, OQ-054), the box's own card while in play
# for "this card", the hand for "from your hand" -- and none while a printed
# condition fails. The answer trashes with source ``round:R:player:P:
# agent_card`` (no card id) and keeps the trash trigger's recruits in the
# context written back; a box with icons left keeps its ``trashes_remaining``
# counter on the frame. Shishakli's draw is named ``<that>:trash_draw``.

_TRASH_SOURCE: Final = "agent_card"
_TRASH_ICON: Final = TrashPersonalCard()


def trash_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional trash box (icons or a trash arrow)."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or not ability.sections
    ):
        return False
    if all(
        line.rewards == (_TRASH_ICON,)
        and not line.costs
        and (
            line.condition is None
            or isinstance(line.condition, CommandersInConflictAtLeast)
        )
        for line in ability.sections
    ):
        return not ability.armed_icons
    first, *rest = ability.sections
    if (
        len(first.costs) != 1
        or not isinstance(first.costs[0], TrashCard)
        or any(line.costs for line in rest)
        or any(
            line.condition is not None
            and not isinstance(line.condition, TrashedCardHasFaction)
            for line in ability.sections
        )
    ):
        return False
    if any(
        not _armed_line(key, line)
        for key, line in zip(ability.armed_icons, ability.sections, strict=False)
    ):
        return False
    return all(
        isinstance(reward, (DrawPersonalCards, GrantCombatDeployment))
        for line in ability.sections[len(ability.armed_icons) :]
        for reward in line.rewards
    )


def _trash_cost(ability: Ability) -> TrashCard | None:
    cost = ability.sections[0].costs[0] if ability.sections[0].costs else None
    return cost if isinstance(cost, TrashCard) else None


def _trash_conditions(ability: Ability) -> tuple[CommandersInConflictAtLeast, ...]:
    return tuple(
        line.condition
        for line in ability.sections
        if isinstance(line.condition, CommandersInConflictAtLeast)
    )


def _trash_conditions_hold(owner: PlayerState, ability: Ability) -> bool:
    return all(
        owner.commanders_conflict >= condition.count
        for condition in _trash_conditions(ability)
    )


def trash_targets(
    state: GameState, player: int, ability: Ability, context: Mapping[str, ActionValue]
) -> tuple[str, ...]:
    """The cards the box's trash may take now."""

    owner = state.players[player]
    cost = _trash_cost(ability)
    if cost is not None and cost.this_card:
        # "Trash this card" (OQ-022: a card already trashed by another
        # effect expired before this choice was offered).
        card_id = context.get("card_id")
        if isinstance(card_id, str) and card_id in owner.in_play:
            return (card_id,)
        return ()
    if cost is not None and cost.hand_only:
        return owner.hand
    # A Row card borrowed with Usurp is not "in play" ("A grafted card in
    # the Imperium Row isn't considered to be 'in play.'" [Immortality
    # p. 14]), so it is no trash target (OQ-054, user ruling 2026-10-04).
    return (*owner.hand, *owner.discard_pile, *counted_in_play(owner))


def trash_block(
    state: GameState, player: int, ability: Ability, context: Mapping[str, ActionValue]
) -> OptionalEffectBlock | None:
    """Why the box's trash offers no card now: its condition, then no target."""

    owner = state.players[player]
    kind = OptionalBlockKind
    if not _trash_conditions_hold(owner, ability):
        return OptionalEffectBlock(kind.NO_COMMANDER_IN_CONFLICT)
    if trash_targets(state, player, ability, context):
        return None
    cost = _trash_cost(ability)
    if cost is not None and cost.this_card:
        return OptionalEffectBlock(kind.NOT_IN_PLAY)
    if cost is not None and cost.hand_only:
        return OptionalEffectBlock(kind.HAND, 1, 0)
    return OptionalEffectBlock(kind.NO_CARD_TO_TRASH)


def trash_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The refusal, then one row per target; none while a condition fails."""

    _, context = current_agent_effect_context(state)
    if not _trash_conditions_hold(state.players[player], ability):
        return ()
    return (
        DomainAction(action_id="decline_agent_card_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in trash_targets(state, player, ability, context)
        ),
    )


def apply_trash(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Refuse the trash, or trash the chosen card and take what it buys."""

    _, context = current_agent_effect_context(state)
    player = action.actor
    source = f"round:{state.round_number}:player:{player}:{_TRASH_SOURCE}"
    context["pending_agent_effect"] = False
    if action.action_id == "decline_agent_card_trash":
        context.pop("trashes_remaining", None)
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:trash_declined",
                    kind="agent_card_trash_declined",
                    payload=(("player", player),),
                ),
            ),
        )
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card trash choice has invalid card ID")
    trashed = trash_personal_card(state, player, card_id, source=source)
    keep_trash_recruits(context, trashed)
    cost = _trash_cost(ability)
    if cost is None and len(ability.sections) > 1:
        # Black trash icons: one counter for the ones still open.
        remaining = trashes_remaining(context, len(ability.sections)) - 1
        if remaining > 0:
            context["pending_agent_effect"] = True
            context["trashes_remaining"] = remaining
            frame = trashed.state.decision_stack[-1]
            next_frame = replace(frame, context=tuple(sorted(context.items())))
            return RuleResult(
                state=replace(
                    trashed.state,
                    decision_stack=(*trashed.state.decision_stack[:-1], next_frame),
                ),
                events=trashed.events,
            )
        context.pop("trashes_remaining", None)
        return RuleResult(
            state=advance_after_effect(trashed.state, context, trashed.state.players),
            events=trashed.events,
        )
    if cost is None:
        # The one black trash icon.
        return RuleResult(
            state=advance_after_effect(trashed.state, context, trashed.state.players),
            events=trashed.events,
        )
    if cost.this_card:
        # The card trashed itself as its own cost, so its rewards still pay
        # out (OQ-022).
        context["agent_card_self_trashed"] = True
    factions = personal_card_for_instance(card_id).factions
    met = tuple(
        not isinstance(line.condition, TrashedCardHasFaction)
        or line.condition.faction in factions
        for line in ability.sections
    )
    armed = len(ability.armed_icons)
    if keys := tuple(
        key for key, ok in zip(ability.armed_icons, met, strict=False) if ok
    ):
        arm_agent_icons(context, keys)
    paid = tuple(
        reward
        for line, ok in zip(ability.sections[armed:], met[armed:], strict=True)
        if ok
        for reward in line.rewards
    )
    if any(isinstance(reward, GrantCombatDeployment) for reward in paid) and (
        context.get("units_deploy_blocked") is not True
    ):
        # The Combat icon: this turn deploys as though at a Combat space,
        # never more than two units from the garrison [Bloodlines p. 5].
        context["pending_combat_deployment"] = True
        limit = context_int(
            context, "existing_troop_deployment_limit", owner="Agent-turn effect frame"
        )
        context["existing_troop_deployment_limit"] = max(limit, 2)
    next_state = advance_after_effect(trashed.state, context, trashed.state.players)
    draws = sum(
        reward.count for reward in paid if isinstance(reward, DrawPersonalCards)
    )
    if draws:
        drawn = draw_or_request_personal_cards(
            next_state, player, draws, source=f"{source}:trash_draw"
        )
        return RuleResult(
            state=drawn.state, events=(*trashed.events, *drawn.events)
        )
    return RuleResult(state=next_state, events=trashed.events)


def trashes_remaining(context: Mapping[str, ActionValue], default: int = 0) -> int:
    """How many optional trash icons of the active box are still open.

    The Beast's Spoils sets the counter to its Crysknife count when its
    automatic rewards resolve; Ruthless Leadership's two printed icons start
    from ``default`` on the first trash.
    """

    remaining = context.get("trashes_remaining", default)
    if isinstance(remaining, bool) or not isinstance(remaining, int):
        raise RuntimeError("Agent-turn effect frame has invalid trash count")
    return remaining


# --- Unit-loss arrows (stage A3f) -----------------------------------------------
#
# "You may lose 1 troop -> ..." (Piter, Genius Advisor): the refusal, then for
# the garrison and then the Conflict a troop row and, where one is, a
# Sardaukar Commander row -- a Commander is a troop [Bloodlines p. 4] (OQ-105)
# -- named ``lose_agent_card_troop``; with no unit the refusal alone
# (``lose_cost_block``). The answer arms the record's keys, writes the frame
# back first so what the loss records there stays (OQ-029, OQ-038 (b)), then
# loses the unit under ``round:R:player:P:agent_card_payment:troop`` and
# settles a Conflict loss's deployment. Every line is armed (OQ-027, OQ-106).

_LOSS: Final = LoseTroops()


def lose_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional arrow paid by losing one unit."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or not ability.sections
        or ability.sections[0].costs != (_LOSS,)
        or any(line.costs for line in ability.sections[1:])
        or any(line.condition is not None for line in ability.sections)
    ):
        return False
    return len(ability.armed_icons) == len(ability.sections) and all(
        _armed_line(key, line)
        for key, line in zip(ability.armed_icons, ability.sections, strict=True)
    )


def lose_cost_block(owner: PlayerState) -> OptionalEffectBlock | None:
    """No troop or Commander anywhere to lose."""

    if (
        owner.troops_garrison
        + owner.commanders_garrison
        + owner.troops_conflict
        + owner.commanders_conflict
    ) < 1:
        return OptionalEffectBlock(OptionalBlockKind.NO_UNIT)
    return None


def lose_rows(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """The refusal, then the units the loss may take, troop first per zone."""

    owner = state.players[player]
    rows = [DomainAction(action_id="decline_agent_card_payment", actor=player)]
    if lose_cost_block(owner) is not None:
        return tuple(rows)
    for zone in ("garrison", "conflict"):
        if getattr(owner, f"troops_{zone}") >= 1:
            rows.append(
                DomainAction(
                    action_id="lose_agent_card_troop",
                    actor=player,
                    arguments=(("zone", zone),),
                )
            )
        if getattr(owner, f"commanders_{zone}") >= 1:
            rows.append(
                DomainAction(
                    action_id="lose_agent_card_troop",
                    actor=player,
                    arguments=(("commanders", 1), ("zone", zone)),
                )
            )
    return tuple(rows)


def apply_lose(
    state: GameState,
    action: DomainAction,
    ability: Ability,
    context: dict[str, ActionValue],
    source: str,
) -> RuleResult:
    """Lose the chosen unit and arm the arrow's rewards (the refusal is the
    payment handler's)."""

    arguments = dict(action.arguments)
    zone = str(arguments["zone"])
    commander = arguments.get("commanders") == 1
    arm_agent_icons(context, ability.armed_icons)
    settled = advance_after_effect(state, context)
    lost = lose_unit(
        settled, action.actor, zone, commander=commander, source=f"{source}:troop"
    )
    next_state = lost.state
    if zone == "conflict":
        next_state = reconcile_deployment_after_retreat(
            next_state,
            action.actor,
            troops=int(not commander),
            commanders=int(commander),
        )
    return RuleResult(state=next_state, events=lost.events)


# --- A plain line beside a choice line (stage A3f) --------------------------------
#
# Two printed lines, the second a choice: "Choose one: Draw 1 card / If Bene
# Gesserit Bond: Gain 1 Bene Gesserit Influence" (Southern Faith), "If 2 or
# more Spacing Guild Influence: Choose one: Draw 1 card / Combat" (High
# Priority Travel), and "Gain 1 spice, If grafted with an Emperor or Spacing
# Guild card: Gain 1 Influence with a chosen Faction" (Interstellar
# Conspiracy). The plain line resolves as one action (``resolve_box``, the
# A2 conventions). While the choice line's condition holds and it has a
# target, its rows are offered -- beside the plain row for "Choose one"
# (``ONE_OF``), alone for a sequence, whose choice then pays the plain line
# too (its gains after the choice's events); otherwise the frame offers the
# plain row alone. The Combat answers through its own handler
# (``take_agent_card_combat_icon``).

_PLAIN_ROW: Final = "resolve_agent_card_effect"


def either_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is a plain line beside a choice line (see above)."""

    if (
        ability is None
        or ability.mark is not AbilityMark.MANDATORY
        or ability.icons
        or ability.armed_icons
        or ability.hook is not None
        or ability.structure is AbilityStructure.SEPARATE
        or len(ability.sections) != 2
        or any(line.costs for line in ability.sections)
    ):
        return False
    plain, choice = ability.sections
    if len(choice.rewards) != 1 or choice.condition is None:
        # The choice line is printed under a condition of its own; two plain
        # lines resolve as one action.
        return False
    match choice.rewards[0]:
        case GainInfluence(times=1, distinct=False) as gain:
            # A sequence pays its plain line with a chosen Faction; "Choose
            # one" may offer a fixed Faction beside the plain line.
            if (
                ability.structure is AbilityStructure.SEQUENCE
                and not gain.requires_choice
            ):
                return False
        case GrantCombatDeployment():
            if ability.structure is not AbilityStructure.ONE_OF:
                return False
        case _:
            return False
    return all(
        isinstance(reward, (DrawPersonalCards, GainResources))
        for reward in plain.rewards
    )


def either_choice(ability: Ability) -> GainInfluence | GrantCombatDeployment:
    """The choice line's one reward."""

    piece = ability.sections[1].rewards[0]
    assert isinstance(piece, (GainInfluence, GrantCombatDeployment))
    return piece


def either_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The choice line's rows while it holds -- after the plain row for
    "Choose one" -- or none, leaving the plain row to the frame."""

    _, context = current_agent_effect_context(state)
    choice = ability.sections[1]
    if not _line_holds(choice, state.players[player], context):
        return ()
    piece = either_choice(ability)
    if isinstance(piece, GainInfluence):
        rows = piece_rows(
            state,
            player,
            piece,
            Source.AGENT_CARD,
            refusals=False,
            empty_confirm=False,
        )
    else:
        rows = (DomainAction(action_id="take_agent_card_combat_icon", actor=player),)
    if not rows:
        return ()
    plain = ability.sections[0]
    if ability.structure is AbilityStructure.ONE_OF and _line_holds(
        plain, state.players[player], context
    ):
        return (DomainAction(action_id=_PLAIN_ROW, actor=player), *rows)
    return rows


def apply_either_influence(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Gain the chosen Faction's Influence; a sequence pays its plain line's
    gains after it (Interstellar Conspiracy's spice)."""

    _, context = current_agent_effect_context(state)
    _, card_id = _subject(context)
    player = action.actor
    faction = Faction(str(dict(action.arguments)["faction"]))
    source = agent_card_source(state.round_number, player, card_id)
    gained = gain_faction_influence(
        state, player, faction, 1, event_prefix=f"{source}:influence:{faction.value}"
    )
    context["pending_agent_effect"] = False
    players = gained.state.players
    if ability.structure is AbilityStructure.SEQUENCE:
        owner = players[player]
        for reward in ability.sections[0].rewards:
            if isinstance(reward, GainResources):
                owner = _gain(owner, reward)
        players = replace_player(players, owner)
    next_state = advance_after_effect(
        replace(gained.state, players=players), context, players
    )
    return RuleResult(state=next_state, events=gained.events)
