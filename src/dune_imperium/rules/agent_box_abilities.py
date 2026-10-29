"""Agent boxes resolved from their ability records (composed effects, stage A2).

docs/composed-effects-plan.md 5 (A2). A personal card whose Agent box has a
record in ``content.uprising.agent_abilities`` is resolved here instead of
by its own branch of ``agent_effects``. The Agent-turn effect frame keeps
its keys (``pending_agent_effect``, ``pending_agent_icons``) and the rows
stay ``resolve_agent_card_effect`` and ``resolve_agent_card_effect(effect=…)``;
the events follow the cleanup-2c grammar (docs/composed-effects-plan.md,
"정리-2c 사건 문법").

The events follow two conventions, one per way a box resolves:

- **One action** (``resolve_box``): the owner's gains (resources, troops,
  the Bene Gesserit boost, the card back to hand), a fixed Faction's
  Influence (prefix ``<box>:influence:<faction>``) and an Intrigue draw are
  applied before the frame is written back; then the follow-ups that may
  push a frame above it -- a Contract, Research, the Tleilaxu track,
  specimens, the Intrigue peek, the optional trash frame -- and a personal
  draw; the opponents' decisions last, pushed last-printed first so they are
  answered in printed order (Covert Operation's discards
  ``<box>:opponent:<seat>``, Holy War's losses ``<box>:unit_loss:<seat>``
  before its Spy moves, OQ-036). Everything is named after ``<box>``. The
  event list is the gains' ``resources_gained``, the Influence, draws' and
  follow-ups' events, any recruit shortfall, then the box's event
  ``<box>:resolved`` (``<box>:unavailable`` when a printed condition fails;
  ``rules/box_events.py``, cleanup-2c-2).
- **Icon by icon** (``resolve_box_icon``, OQ-027): the icon's gains, a recruit
  shortfall and an Intrigue draw, all named ``<box>``, before the write-back;
  specimens (``<box>:specimen``) then Research (``<box>:research``) and a
  personal draw (``<box>``) after it; the icon's event
  ``<box>:<icon>:resolved`` comes last.

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
from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    BoardSpace,
    Faction,
)
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AllConditions,
    AtFactionSpace,
    AtMakerSpace,
    BlockChosenSpaceForOpponentsNextAgent,
    BoostNextBeneGesseritCard,
    CommandersInConflictAtLeast,
    CompleteContract,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    DestroyShieldWall,
    DiscardedCardHasFaction,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EachOpponentDiscardsCard,
    EachOpponentDiscardsOrLosesDeployedTroop,
    EachOpponentLosesTroop,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerPartnerAgentIcon,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    GraftedTrash,
    GraftedWithFaction,
    GrantCombatDeployment,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    LoseInfluence,
    LoseTroops,
    OpponentsMoveSpiesFromVisitedSpace,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecruitTroops,
    Research,
    ReturnOtherGraftedCardAtRevealStart,
    ReturnThisCardToHand,
    Reward,
    SandwormsInConflictAtLeast,
    SpendSpecimens,
    SpyRecalledThisTurn,
    SummonSandworm,
    TakeCardFromDiscard,
    TakeContract,
    TrashCard,
    TrashedCardHasFaction,
    TrashIntrigueCard,
    TrashPersonalCard,
    TrashThisCard,
    UnitsInConflictAtLeast,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.ability_executor import piece_rows
from dune_imperium.rules.acquisition import agent_box_acquisition
from dune_imperium.rules.action_shapes import (
    PRINTER_KEY,
    Source,
    Verb,
    printer_value,
    template_id,
)
from dune_imperium.rules.agent_icons import effective_agent_icons
from dune_imperium.rules.board_table import board_spaces_on_table
from dune_imperium.rules.box_events import BoxNeedsRows, BoxOutcome, agent_box_event
from dune_imperium.rules.card_bonds import (
    counted_in_play,
    has_faction_bond,
    trashable_cards,
)
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import keep_trash_recruits, trash_personal_card
from dune_imperium.rules.combat_deployment import (
    open_combat_deployment,
    reconcile_deployment_after_retreat,
)
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    advance_after_effect,
    agent_card_source,
    arm_agent_icons,
    boosted_cards,
    current_agent_effect_context,
    finish_agent_icon,
    is_grafted,
    other_grafted_card_id,
    pending_agent_icons,
    recruit_shortfall_events,
    recruit_troops,
    short_of,
    spice_gained_this_turn,
)
from dune_imperium.rules.frames import FrameKind, replace_player
from dune_imperium.rules.gain_events import resources_gained_event, resources_paid_event
from dune_imperium.rules.graft_boxes import ACTIVE_BOX_KEY
from dune_imperium.rules.immortality import (
    advance_research,
    advance_tleilaxu,
    tleilaxu_track_finished,
    troop_can_join,
)
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    influence_can_rise,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import (
    draw_or_queue_intrigue_cards,
    shufflable_intrigue_discard,
    with_trashed_intrigue,
)
from dune_imperium.rules.intrigue_peek import begin_intrigue_peek
from dune_imperium.rules.optional_trash import open_optional_trash, trash_printer
from dune_imperium.rules.specimens import generate_specimens, spend_specimens
from dune_imperium.rules.spies import gather_intelligence_draw_available
from dune_imperium.rules.spy_moves import turn_space_spy_frames
from dune_imperium.rules.spy_placement import (
    observation_post_ids_for_factions,
    spy_options,
)
from dune_imperium.rules.unit_loss import lose_unit, opponent_unit_loss_frames

_RESOLVED = BoxOutcome.RESOLVED
_UNAVAILABLE = BoxOutcome.UNAVAILABLE


class AgentIconCondition(StrEnum):
    """What a conditioned Agent-box icon waits for (``box_icon_block``)."""

    INFLUENCE = "influence"
    SPICE_GAINED = "spice_gained"
    GRAFTED = "grafted"
    # Grafted with a card of one of ``factions`` (Interstellar Conspiracy);
    # the partner is chosen once, so it stays so all turn.
    GRAFTED_WITH = "grafted_with"
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
    factions: tuple[Faction, ...] = ()


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
    # Firm Grip's chosen Influence: every Faction it may raise is at the top
    # of its track, where a gain is lost (OQ-060), so the 2 Solari would buy
    # nothing ("the cost line is not offered if all three are at 6", OQ-071).
    NO_FACTION_TO_RAISE = "no_faction_to_raise"
    # Fremen Camp's and Duncan Idaho's recruit: no troop in the supply and no
    # specimen to return, so the cost would buy nothing (OQ-071's recruit
    # criterion, user ruling 2026-10-06 "효과 없음"; P3d app comparison).
    NO_TROOP_TO_RECRUIT = "no_troop_to_recruit"


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
        case AtFactionSpace():
            return space.faction is not None
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
    """Whether the box is pending once ``card_id`` is played on ``space``.

    An automatic box has nothing to resolve and never opens: it modifies a
    step another effect takes (Carryall's doubled harvest).
    """

    if ability.mark is AbilityMark.AUTOMATIC:
        return False
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
        case GraftedWithFaction(factions=factions):
            if box_condition_holds(condition, owner, context):
                return None
            return AgentIconBlock(AgentIconCondition.GRAFTED_WITH, factions=factions)
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


def _other_grafted_card_returns(
    line: EffectSection, owner: PlayerState, context: Mapping[str, ActionValue]
) -> bool:
    """Chairdog's return can still happen: the other grafted card is in
    play ("return the other grafted card from play" [Chairdog card])."""

    if not any(
        isinstance(reward, ReturnOtherGraftedCardAtRevealStart)
        for reward in line.rewards
    ):
        return True
    partner = other_grafted_card_id(context)
    return bool(partner) and partner in owner.in_play


def _line_holds(
    line: EffectSection, owner: PlayerState, context: Mapping[str, ActionValue]
) -> bool:
    if any(isinstance(reward, ReturnThisCardToHand) for reward in line.rewards):
        if context.get("card_id") not in counted_in_play(owner):
            return False
    if not _other_grafted_card_returns(line, owner, context):
        return False
    return line.condition is None or box_condition_holds(
        line.condition, owner, context
    )


def box_icon_block(
    owner: PlayerState, context: Mapping[str, ActionValue], ability: Ability, key: str
) -> AgentIconBlock | None:
    """Why the box's icon ``key`` is not offered now, or None when it is."""

    keys = ability.icons or ability.armed_icons
    if key not in keys:
        return NOT_PRINTED_BLOCK
    return _line_block(ability.sections[keys.index(key)], owner, context)


# --- Resolution --------------------------------------------------------------------


def _card_printer(card_id: str) -> str:
    """The Agent card ``card_id`` as the entity that opened an opponent's
    window (``action_shapes.printer_value``; stage B3d-3)."""

    card = personal_card_for_instance(card_id).card.card_id
    return printer_value(Source.AGENT_CARD, card)


def _box_trash_printer(context: Mapping[str, ActionValue]) -> str:
    """The printer an optional trash the active box opens records (stage
    B3c-2b): the box's card by type, box 1 for a grafted turn's second card
    (as ``effect_steps.Printed.BOX_CARD`` names a box's effects)."""

    card_id = context["card_id"]
    assert isinstance(card_id, str)
    return trash_printer(
        Source.AGENT_CARD,
        personal_card_for_instance(card_id).card.card_id,
        1 if context.get(ACTIVE_BOX_KEY) == 1 else 0,
    )


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


# The frame key that says a box's Influence replaced the visited space's own
# 1 for good: a partner box that held it too and expires later does not
# bring the 1 back (never 2 + 1, [Main pp. 9, 11, 20]).
SPACE_INFLUENCE_REPLACED: Final = "space_influence_replaced"


def holds_space_influence(ability: Ability | None) -> bool:
    """Whether a waiting box of ``ability`` holds the visited space's own
    Influence: a mandatory "Gain 2 Influence with the visited Faction" that
    replaces it [Subversive Advisor card], so while the box waits the
    space's ``resolve_faction_influence`` step is not offered and the two
    never add up to 3 [Main pp. 9, 11, 20]."""

    return (
        ability is not None
        and ability.mark is AbilityMark.MANDATORY
        and any(
            isinstance(reward, GainInfluence) and reward.replaces_space
            for line in ability.sections
            for reward in line.rewards
        )
    )


def _replace_space_influence(context: dict[str, ActionValue]) -> None:
    """The box's gain replaces the visited space's 1 [Main p. 9]: the space's
    own step is used up, and a partner box that held it and expires later
    does not bring it back.

    Once one box replaced it, a second "instead of one" box of the same
    placement -- Ghola's copy -- gains nothing more: "If you graft this card
    with Power Play to send an Agent to a faction board space, you gain only
    2 Influence with that faction, the same as if you'd played Power Play
    alone." [Immortality p. 14], which the user ruled holds for every card
    of that text (OQ-128, 2026-10-25: "이와 같은 동작을 하는건 모두 그
    내용을 따라야지"). The callers skip that second gain.
    """

    context["pending_faction_influence"] = False
    context[SPACE_INFLUENCE_REPLACED] = True


def replacing_gain_block(
    owner: PlayerState, gain: GainInfluence, context: Mapping[str, ActionValue]
) -> OptionalEffectBlock | None:
    """Why an optional arrow's "N Influence instead of 1" buys nothing now
    [Treacherous Maneuver card]: it replaces the visited space's own single
    gain, "기본 1 대신 총 2" [Main p. 9] (docs/rules/player-turns.md), so it
    is offered only while that gain is still pending -- an Agent infiltrated
    onto a space without a Faction [Main p. 11] has none (OQ-046), and once
    the space's 1 is gained there is nothing left to replace. Near the
    track's top (``MAX_INFLUENCE``) the N end where the 1 would, so the cost
    would buy nothing: "비용이 있는 줄은 보상 중 하나라도 무언가를 바꿀 수
    있을 때만 제시한다" (OQ-071, user decision 2026-09-29)."""

    space_id = context.get("space_id")
    visited = (
        BOARD_SPACES_BY_ID[space_id].faction if isinstance(space_id, str) else None
    )
    if context.get("pending_faction_influence") is not True or visited is None:
        return OptionalEffectBlock(OptionalBlockKind.NO_FACTION_GAIN)
    held = influence_amount(owner.influence, visited)
    if held > MAX_INFLUENCE - gain.times:
        return OptionalEffectBlock(
            OptionalBlockKind.FACTION_NEAR_TOP, held=held, faction=visited.value
        )
    return None


def _replacing_gain(ability: Ability) -> GainInfluence | None:
    return next(
        (
            reward
            for line in ability.sections
            for reward in line.rewards
            if isinstance(reward, GainInfluence) and reward.replaces_space
        ),
        None,
    )


def _visited_faction(context: Mapping[str, ActionValue]) -> Faction:
    """The Faction of the space the Agent was sent to (the placement judged
    it, ``AtFactionSpace``)."""

    space_id = context.get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Agent-turn effect frame has invalid space")
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is None:
        raise RuntimeError("a visited Faction's gain needs a Faction space")
    return faction


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
            case ReturnOtherGraftedCardAtRevealStart():
                # Noted when the pair was grafted (``graft.apply_graft_partner``);
                # the box notes nothing twice.
                partner = other_grafted_card_id(context)
                if partner not in owner.chairdog_return_card_ids:
                    owner = replace(
                        owner,
                        chairdog_return_card_ids=(
                            *owner.chairdog_return_card_ids,
                            partner,
                        ),
                    )
    return owner, shortfall


def _gains_event(
    rewards: tuple[Reward, ...], source: str, player: int
) -> tuple[GameEvent, ...]:
    """The rewards' resources and Victory Points as one ``resources_gained``
    named ``source`` (rule decisions 3 and 4), or none when it gains
    neither (only paid arrows print Victory Points, ``apply_payment`` and
    the Intrigue payment)."""

    amounts = {"solari": 0, "spice": 0, "water": 0, "victory_points": 0}
    for reward in rewards:
        if isinstance(reward, GainResources):
            amounts["solari"] += reward.solari
            amounts["spice"] += reward.spice
            amounts["water"] += reward.water
        elif isinstance(reward, GainVictoryPoints):
            amounts["victory_points"] += reward.amount
    if not any(amounts.values()):
        return ()
    return (resources_gained_event(source, player, **amounts),)


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
            and not plain_and_paid_box(ability)
            and not choose_two_box(ability)
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
    if (
        lose_box(ability)
        or influence_loss_box(ability)
        or agent_box_acquisition(ability) is not None
    ):
        # Piter's and Shifting Allegiances' optional arrows and Tleilaxu
        # Master's optional acquisition resolve through their rows only; an
        # optional box is never dry-run (cleanup-2c-2) and lapses at the
        # turn's end.
        raise BoxNeedsRows("an optional Agent box resolves through its rows")
    elif trash_box(ability):
        # Ruthless Leadership: its Commander condition is judged now
        # (OQ-028); without it the box resolves without effect.
        if _trash_conditions_hold(owner, ability):
            raise BoxNeedsRows("Agent-card trash effect requires a player choice")
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
            raise BoxNeedsRows("place-Spy Agent effect requires a player choice")
        context.pop("agent_card_spy_pending", None)
        context.pop("agent_card_spy_recalled", None)
        available = False
    elif choose_two_box(ability):
        # "Choose two" resolves through its picks; reached with none to
        # make, the box fizzles (OQ-057 (1)).
        if choose_two_rows(state, player, ability):
            raise BoxNeedsRows("the Agent box resolves through its picks")
        available = False
    elif graft_trash_box(ability):
        # Beguiling Pheromones' mandatory trash resolves through its rows;
        # with none (no graft, no Faction space) the box waits and fizzles
        # (OQ-057 (1)).
        if graft_trash_rows(state, player, ability):
            raise BoxNeedsRows("the grafted card's trash requires a player choice")
        available = False
    elif discard_box(ability):
        # Guild Envoy's mandatory discard resolves through its rows; with an
        # empty hand the box waits and fizzles (OQ-057 (1), OQ-028).
        if discard_rows(state, player, ability):
            raise BoxNeedsRows("Agent-card discard effect requires a player choice")
        available = False
    else:
        available = _line_holds(line, owner, context)
    base = state
    self_trash: tuple[GameEvent, ...] = ()
    if available and any(isinstance(reward, TrashThisCard) for reward in line.rewards):
        # Seek Allies' "Trash this card." [Main p. 20]: the card trashes
        # itself by its own effect (OQ-022), before the frame is written
        # back so a trash trigger's troops count as this turn's recruits.
        if card_id in owner.in_play:
            trashed = trash_personal_card(state, player, card_id, source=source)
            keep_trash_recruits(context, trashed)
            base, self_trash = trashed.state, trashed.events
            owner = base.players[player]
        else:
            available = False
    if (piece := target_piece(ability)) is not None:
        # A target choice resolves through its rows; reached with one to make
        # is a caller's error, and with none the box waits and fizzles
        # (OQ-057 (1)) -- a Spy box dropping its recall-first marks.
        if target_rows(state, player, ability):
            raise BoxNeedsRows("the Agent box resolves through its target choice")
        if isinstance(piece, PlaceSpy):
            context.pop("agent_card_spy_pending", None)
            context.pop("agent_card_spy_recalled", None)
        if isinstance(piece, GainInfluence) and piece.times > 1:
            # Long Reach with no second Faction left after its first pick (a
            # later effect raised the last other cube to the top), or none
            # named: the Faction named is paid and the rest is lost, as a
            # Conflict reward's "Choose two" pays its first (OQ-060); the box
            # fizzles (OQ-057 (1)).
            named = _pay_named_influence(
                base, player, _influence_chosen(context), source
            )
            base, self_trash = named.state, named.events
            owner = base.players[player]
        available = False

    next_owner: PlayerState = owner
    shortfall: tuple[GameEvent, ...] = ()
    gains: tuple[GameEvent, ...] = ()
    if available:
        next_owner, shortfall = _owner_gains(
            owner, line, context, card_id, source, player
        )
        gains = _gains_event(line.rewards, source, player)
        if any(
            isinstance(reward, GainSolariPerPartnerAgentIcon) for reward in line.rewards
        ) and (icon_solari := partner_icon_count(state, context)):
            # Slig Farmer's plain line [Slig Farmer card].
            next_owner = replace(
                next_owner,
                resources=replace(
                    next_owner.resources,
                    solari=next_owner.resources.solari + icon_solari,
                ),
            )
            gains = (resources_gained_event(source, player, solari=icon_solari),)
    working = replace(base, players=replace_player(base.players, next_owner))
    if available and any(
        isinstance(reward, GrantCombatDeployment) for reward in line.rewards
    ):
        # Occupation's Combat icon [Bloodlines p. 5].
        open_combat_deployment(context)
    influence_events: tuple[GameEvent, ...] = ()
    for reward in line.rewards if available else ():
        if isinstance(reward, GainInfluence):
            # A fixed or the visited Faction's Influence, prefix
            # ``<box>:influence:<f>``.
            if reward.visited_space:
                faction = _visited_faction(context)
                if reward.replaces_space:
                    if context.get(SPACE_INFLUENCE_REPLACED) is True:
                        # A second "instead of one" box of the placement (a
                        # Ghola copy) adds nothing (``_replace_space_influence``).
                        continue
                    _replace_space_influence(context)
            else:
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
        drawn = draw_or_queue_intrigue_cards(working, player, intrigue, source=source)
        working, intrigue_events = drawn.state, drawn.events
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(working, context)
    event = agent_box_event(
        source, card_id, player, _RESOLVED if available else _UNAVAILABLE
    )
    if not available:
        # Long Reach's named Faction, paid as it fizzles.
        return RuleResult(state=next_state, events=(*self_trash, event))

    follow_ups: list[GameEvent] = []
    for reward in line.rewards:
        step: RuleResult | None = None
        match reward:
            case TakeContract(count=count):
                step = begin_contract_gain(next_state, player, count, source=source)
            case Research():
                step = advance_research(next_state, player, source=source)
            case AdvanceTleilaxu(count=count):
                step = advance_tleilaxu(next_state, player, count)
            case GenerateSpecimens(count=count):
                step = generate_specimens(next_state, player, count, source=source)
            case LookAtIntrigueKeepOne():
                step = begin_intrigue_peek(next_state, player, source=source)
            case TrashPersonalCard():
                # The black trash icon on a frame of its own, named after the
                # box so a self-trash keeps its card's effects (OQ-022).
                next_state = open_optional_trash(
                    next_state, player, source, printer=_box_trash_printer(context)
                )
        if step is not None:
            next_state = step.state
            follow_ups.extend(step.events)
    if draws := _personal_draws(line, owner):
        drawn_cards = draw_or_request_personal_cards(
            next_state, player, draws, source=source
        )
        next_state = drawn_cards.state
        follow_ups.extend(drawn_cards.events)
    for reward in reversed(line.rewards):
        # The stack is last in, first out: the first printed is pushed last.
        if (opponents := _opponents_decide(next_state, reward, context)) is not None:
            next_state = opponents.state
            follow_ups.extend(opponents.events)
    return RuleResult(
        state=next_state,
        events=(
            *gains,
            *influence_events,
            *intrigue_events,
            *follow_ups,
            *self_trash,
            *shortfall,
            event,
        ),
    )


def _opponents_decide(
    state: GameState, reward: Reward, context: Mapping[str, ActionValue]
) -> RuleResult | None:
    """Push the opponents' decisions a reward asks for, named after the box;
    None for a reward the owner resolves."""

    player, card_id = _subject(dict(context))
    source = agent_card_source(state.round_number, player, card_id)
    match reward:
        case EachOpponentDiscardsCard() | EachOpponentDiscardsOrLosesDeployedTroop():
            count = (
                reward.cards if isinstance(reward, EachOpponentDiscardsCard) else 1
            )
            or_lose = isinstance(reward, EachOpponentDiscardsOrLosesDeployedTroop)
            # Every opponent is asked, the next seat first (OQ-138, user
            # ruling 2026-10-26, as OQ-131 and Holy War's unit loss): a seat
            # with an empty hand gets the window too and confirms that it
            # discards nothing (``resolve_opponent_discard_without_card``).
            # The owner's frame is already written back beneath them; the
            # last answer writes it back again, unchanged
            # (``agent_effects.apply_opponent_card_discard``).
            seats = state.config.players
            targets = tuple((player + offset) % seats for offset in range(1, seats))
            is_covert_operation = ":covert_operation:" in card_id
            frames = tuple(
                DecisionFrame(
                    kind=FrameKind.OPPONENT_CARD_DISCARD,
                    frame_id=f"{source}:opponent:{target}",
                    decision=PlayerDecision(
                        owner=target,
                        prompt=(
                            _test_of_humanity_prompt(state, target)
                            if or_lose
                            else "Choose a card to discard for Covert Operation"
                            if state.players[target].hand and is_covert_operation
                            else "Choose a card to discard for Reverend Mother Mohiam"
                            if state.players[target].hand
                            else "No card to discard"
                        ),
                    ),
                    context=(
                        ("covert_operation_card_id", card_id),
                        ("covert_operation_owner", player),
                        # "Each opponent discards two cards" (Reverend Mother
                        # Mohiam): the picks still owed, as many as the hand
                        # holds (OQ-118); Covert Operation's one needs no key.
                        *(
                            (("opponent_discards_remaining", count),)
                            if count > 1
                            else ()
                        ),
                        # Test of Humanity: the same window also offers the
                        # loss of a deployed troop; no other frame has the key.
                        *((("or_lose_deployed_troop", True),) if or_lose else ()),
                        (PRINTER_KEY, _card_printer(card_id)),
                    ),
                )
                for target in reversed(targets)
            )
            return RuleResult(
                state=replace(
                    state, decision_stack=(*state.decision_stack, *frames)
                ),
                events=(),
            )
        case EachOpponentLosesTroop(garrison_only=garrison_only):
            return opponent_unit_loss_frames(
                state,
                player,
                source=source,
                printer=_card_printer(card_id),
                garrison_only=garrison_only,
            )
        case OpponentsMoveSpiesFromVisitedSpace():
            space_id = context.get("space_id")
            if not isinstance(space_id, str):
                raise RuntimeError("Agent-turn effect frame has invalid space")
            return turn_space_spy_frames(
                state, player, space_id, source=source, printer=_card_printer(card_id)
            )
    return None


def _test_of_humanity_prompt(state: GameState, seat: int) -> str:
    """The prompt of Test of Humanity's window for ``seat``: what it can do,
    a card to discard or a deployed troop to lose (``rules.agent_effects``)."""

    owner = state.players[seat]
    if owner.hand and owner.troops_conflict:
        return "Choose a card to discard or a deployed troop to lose"
    if owner.hand:
        return "Choose a card to discard for Test of Humanity"
    if owner.troops_conflict:
        return "Choose a deployed troop to lose for Test of Humanity"
    return "No card to discard and no deployed troop to lose"


def icon_line[P](
    context: Mapping[str, ActionValue], ability: Ability | None, piece: type[P]
) -> tuple[str, P] | None:
    """The pending icon of an icon-by-icon box whose line prints ``piece``,
    with that piece; None when none waits.

    A choice icon is answered by its own rows (cleanup-2d-5): a Faction's
    Influence by ``choose_agent_card_influence``, the Combat icon by
    ``take_agent_card_combat_icon``, a Spy by the box's Spy rows, the
    recall and the trash by theirs.
    """

    if ability is None:
        return None
    # An arrow's armed icons are looked up like printed ones (Firm Grip's
    # chosen Influence once its 2 Solari are paid); a line after the keyed
    # ones is paid with the cost and has no icon.
    keys = ability.icons or ability.armed_icons
    if not keys:
        return None
    pending = pending_agent_icons(context)
    for key, line in zip(keys, ability.sections, strict=bool(ability.icons)):
        if key in pending:
            for reward in line.rewards:
                if isinstance(reward, piece):
                    return key, reward
    return None


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
        # What an icon does is named after its box; the icon names only its
        # own event (cleanup-2c-3, as a board space's icons).
        next_owner, shortfall = _owner_gains(
            owner, line, context, card_id, source, player
        )
        shortfall = (*_gains_event(line.rewards, source, player), *shortfall)
    effect_state = replace(base, players=replace_player(base.players, next_owner))
    intrigue_events: tuple[GameEvent, ...] = ()
    if available and (intrigue := _intrigue_draws(line)):
        drawn = draw_or_queue_intrigue_cards(
            effect_state, player, intrigue, source=source
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
                    next_state, player, reward.count, source=source
                )
                next_state = generated.state
                track_events = (*track_events, *generated.events)
        for reward in line.rewards:
            if isinstance(reward, Research):
                researched = advance_research(next_state, player, source=source)
                next_state = researched.state
                track_events = (*track_events, *researched.events)
    draw_events: tuple[GameEvent, ...] = ()
    if available and (draws := _personal_draws(line, owner)):
        drawn_cards = draw_or_request_personal_cards(
            next_state, player, draws, source=source
        )
        next_state, draw_events = drawn_cards.state, drawn_cards.events
    event = agent_box_event(
        source, card_id, player, _RESOLVED if available else _UNAVAILABLE, effect=key
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
# ``<box>:paid`` with the resource and the amount spent, the gains'
# ``resources_gained`` ``<box>:resources``, then runs the follow-ups that may
# push a frame: a draw named ``<box>``, a Tleilaxu advance named
# ``<box>:tleilaxu``. The caller adds the box's event. Two such arrows printed
# with "-OR-" (Local Fence, a ``ONE_OF`` record) are one row each beside the
# one refusal, each named by its exchange (``pay_agent_card_<paid>_for_<gained>``,
# as Arrakis Revolt names its two payments), so the steps tell them apart.

# The rewards ``apply_payment`` gives; a record with any other is no payment
# box (it keeps its own code until a stage moves it).
_PAYMENT_REWARDS = (
    GainResources,
    GainVictoryPoints,
    DrawPersonalCards,
    AdvanceTleilaxu,
    RecruitTroops,
    TrashPersonalCard,
    GainInfluence,
)


def _paid_influence(reward: object) -> Faction | None:
    """The one Faction a paid arrow's Influence reward names, or None when
    the reward is not a gain of one fixed Faction's Influence (a choice or the
    visited space's keeps its own code)."""

    if (
        isinstance(reward, GainInfluence)
        and not reward.requires_choice
        and not reward.visited_space
        and reward.factions is not None
    ):
        return reward.factions[0]
    return None


def payment_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional arrow paid with no target to pick."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or not ability.sections
    ):
        return False
    if ability.armed_icons:
        # An arrow whose rewards wait as icons once the cost is paid (Duncan
        # Idaho's troop and draw, OQ-027, OQ-106): every line armed, the
        # cost on the first.
        first, *rest = ability.sections
        if (
            len(first.costs) != 1
            or any(line.costs for line in rest)
            or len(ability.armed_icons) != len(ability.sections)
            or not all(
                _armed_line(key, line)
                for key, line in zip(
                    ability.armed_icons, ability.sections, strict=True
                )
            )
        ):
            return False
        try:
            _paid_resource(first.costs[0])
        except ValueError:
            return False
        return True
    if ability.structure is AbilityStructure.ONE_OF:
        # "[2 spice] -> [5 Solari] -OR- [5 Solari] -> [4 spice]" (Local
        # Fence): each line an arrow of its own, told apart by its row.
        if not all(_payment_line(line) for line in ability.sections):
            return False
        try:
            rows = {_exchange_template(line) for line in ability.sections}
        except LookupError:
            return False
        return len(rows) == len(ability.sections)
    if len(ability.sections) != 1:
        return False
    return _payment_line(ability.sections[0])


def _payment_line(section: EffectSection) -> bool:
    """Whether ``section`` is one paid arrow ``apply_payment`` pays: one cost
    a payment row names, and rewards it gives."""

    if len(section.costs) != 1 or not all(
        isinstance(reward, _PAYMENT_REWARDS)
        and (not isinstance(reward, GainInfluence) or _paid_influence(reward))
        for reward in section.rewards
    ):
        return False
    try:
        _paid_resource(section.costs[0])
    except ValueError:
        return False
    return True


def _line_cost(section: EffectSection) -> PayResources | SpendSpecimens:
    cost = section.costs[0]
    assert isinstance(cost, PayResources | SpendSpecimens)
    return cost


def _paid_lines(ability: Ability) -> tuple[EffectSection, ...]:
    """The lines whose arrow a payment row pays: each of a "-OR-" box's, or
    the one line (an armed arrow's cost is on its first)."""

    if ability.structure is AbilityStructure.ONE_OF:
        return ability.sections
    return ability.sections[:1]


def _payment_cost(ability: Ability) -> PayResources | SpendSpecimens:
    return _line_cost(ability.sections[0])


def _exchange_template(line: EffectSection) -> str:
    """The row of one arrow of a "-OR-" box: what it pays for the one
    resource it gains (``pay_agent_card_spice_for_solari``); ``LookupError``
    when no row names that exchange."""

    gained = [
        name
        for reward in line.rewards
        if isinstance(reward, GainResources)
        for name in ("solari", "spice", "water")
        if getattr(reward, name)
    ]
    if len(line.rewards) != 1 or len(gained) != 1:
        raise LookupError(f"no exchange row pays {line!r}")
    paid, _ = _paid_resource(_line_cost(line))
    return template_id(
        Verb.PAY, Source.AGENT_CARD, variant=f"{paid}_for_{gained[0]}"
    )


def _chosen_line(ability: Ability, action_id: str | None) -> EffectSection:
    """The arrow the payment row ``action_id`` pays (the first line of a box
    with one arrow)."""

    if ability.structure is not AbilityStructure.ONE_OF:
        return ability.sections[0]
    return next(
        line for line in ability.sections if _exchange_template(line) == action_id
    )


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
        case PayResources(solari=solari, spice=0, water=0) if solari:
            # Firm Grip's 2 Solari: an arrow cost, not a board space's printed
            # cost, so no Count Ilban card [FAQ p. 2].
            return "solari", solari
    raise ValueError(f"no payment row pays {cost!r}")


def _payment_template(cost: PayResources | SpendSpecimens) -> str:
    resource, spent = _paid_resource(cost)
    variant = "two_specimens" if resource == "specimen" and spent == 2 else resource
    return template_id(Verb.PAY, Source.AGENT_CARD, variant=variant)


def payment_cost_block(
    owner: PlayerState, ability: Ability
) -> OptionalEffectBlock | None:
    """Why the arrow's cost cannot be paid now, or None: for a "-OR-" box,
    None while either arrow's can, else the first's with the second's
    ``also``."""

    blocks = [_cost_block(owner, _line_cost(line)) for line in _paid_lines(ability)]
    if any(block is None for block in blocks):
        return None
    first, *rest = blocks
    assert first is not None
    return replace(first, also=rest[0]) if rest else first


def _cost_block(
    owner: PlayerState, cost: PayResources | SpendSpecimens
) -> OptionalEffectBlock | None:
    match cost:
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

    if ability.armed_icons:
        # Rewards waiting as icons: the arrow is dead only when none of them
        # can pay. A recruit pays while a troop can join (``troop_can_join``,
        # OQ-071's recruit criterion, user ruling 2026-10-06 "효과 없음"); a
        # Faction's Influence while one of its Factions can rise (OQ-060) --
        # Spice Smugglers' Solari keep its arrow live at the Guild's top.
        blocks = [
            _armed_reward_block(state, player, reward)
            for line in ability.sections
            for reward in line.rewards
        ]
        if any(block is None for block in blocks):
            return None
        return blocks[0]
    blocks = [
        _rewards_block(state, player, line.rewards) for line in _paid_lines(ability)
    ]
    return None if any(block is None for block in blocks) else blocks[0]


def _rewards_block(
    state: GameState, player: int, rewards: tuple[Reward, ...]
) -> AgentPaymentBlock | None:
    """Why one arrow's rewards would change nothing now (OQ-071), or None."""

    if (
        rewards
        and all(isinstance(reward, RecruitTroops) for reward in rewards)
        and not troop_can_join(state, state.players[player])
    ):
        # Fremen Camp's "[2 spice] -> [troop][troop]" with no troop to take
        # (OQ-071's recruit criterion); a line with another live reward
        # beside its recruit (Control the Spice's trash) stays offered.
        return AgentPaymentBlock.NO_TROOP_TO_RECRUIT
    for reward in rewards:
        if isinstance(reward, DrawPersonalCards) and not (
            gather_intelligence_draw_available(state, player)
        ):
            return AgentPaymentBlock.NO_CARD_TO_DRAW
        if isinstance(reward, AdvanceTleilaxu) and tleilaxu_track_finished(
            state.players[player]
        ):
            return AgentPaymentBlock.TLEILAXU_TRACK_END
    return None


def _armed_reward_block(
    state: GameState, player: int, reward: Reward
) -> AgentPaymentBlock | None:
    """Why one of an armed arrow's rewards would change nothing now, or None:
    a draw from an empty deck and discard pile, a recruit with no troop to
    take (Duncan Idaho's "[water] -> [troop][draw]"), a Faction's Influence
    with every track it may raise at the top (OQ-060, OQ-071). Every other
    reward pays."""

    if isinstance(reward, GainInfluence):
        owner = state.players[player]
        return (
            None
            if any(
                influence_can_rise(owner, faction)
                for faction in (reward.factions or tuple(Faction))
            )
            else AgentPaymentBlock.NO_FACTION_TO_RAISE
        )
    if isinstance(reward, DrawPersonalCards) and not (
        gather_intelligence_draw_available(state, player)
    ):
        return AgentPaymentBlock.NO_CARD_TO_DRAW
    if isinstance(reward, RecruitTroops) and not troop_can_join(
        state, state.players[player]
    ):
        return AgentPaymentBlock.NO_TROOP_TO_RECRUIT
    return None


def payment_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The box's raw rows: its refusal, then its payment while it can buy
    something; the arrow cost is judged again whenever the box resolves, in
    the owner's order [Main pp. 9, 20] (OQ-028)."""

    decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
    if ability.structure is AbilityStructure.ONE_OF:
        # One row per arrow its owner can pay for something now; the box
        # holds one refusal (Local Fence).
        owner = state.players[player]
        return (
            decline,
            *(
                DomainAction(action_id=_exchange_template(line), actor=player)
                for line in ability.sections
                if _cost_block(owner, _line_cost(line)) is None
                and _rewards_block(state, player, line.rewards) is None
            ),
        )
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
    state: GameState,
    player: int,
    ability: Ability,
    context: dict[str, ActionValue],
    source: str,
    action_id: str | None = None,
) -> RuleResult:
    """Pay the arrow and take what it buys (``context`` has its pending flag
    already cleared by the caller; ``source`` is the box; ``action_id`` the
    payment row, which names the arrow of a "-OR-" box)."""

    line = _chosen_line(ability, action_id)
    cost = _line_cost(line)
    owner = state.players[player]
    if ability.armed_icons:
        # Only the cost is paid now; the rewards are armed as icons, each
        # its own step in the owner's order (Duncan Idaho: the troop and
        # the hidden draw, OQ-027, OQ-106).
        assert isinstance(cost, PayResources)
        paid_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari - cost.solari,
                spice=owner.resources.spice - cost.spice,
                water=owner.resources.water - cost.water,
            ),
            spice_spent_turn=owner.spice_spent_turn + cost.spice,
        )
        arm_agent_icons(context, ability.armed_icons)
        resource, spent = _paid_resource(cost)
        return RuleResult(
            state=advance_after_effect(
                state, context, replace_player(state.players, paid_owner)
            ),
            events=(resources_paid_event(source, player, **{resource: spent}),),
        )
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
    shortfall: tuple[GameEvent, ...] = ()
    for reward in line.rewards:
        match reward:
            case GainResources():
                owner = _gain(owner, reward)
            case GainVictoryPoints(amount=amount):
                owner = replace(owner, victory_points=owner.victory_points + amount)
            case RecruitTroops(count=count):
                # A troop recruited this turn, which a Combat space lets the
                # owner deploy [Main p. 10] [FAQ p. 4] (Control the Spice).
                owner, recruited = recruit_troops(owner, count)
                _credit_recruits(context, recruited)
                shortfall = recruit_shortfall_events(source, player, count, recruited)
    next_state = advance_after_effect(
        state, context, replace_player(state.players, owner)
    )
    resource, spent = _paid_resource(cost)
    events: list[GameEvent] = [
        resources_paid_event(
            source,
            player,
            **{"specimens" if resource == "specimen" else resource: spent},
        ),
        *_gains_event(line.rewards, source, player),
        *shortfall,
    ]
    for reward in line.rewards:
        step: RuleResult | None = None
        match reward:
            case TrashPersonalCard():
                # The black trash icon stays optional once the cost is paid
                # [FAQ p. 3], on a frame of its own named after the box.
                next_state = open_optional_trash(
                    next_state, player, source, printer=_box_trash_printer(context)
                )
            case AdvanceTleilaxu(count=count):
                step = advance_tleilaxu(next_state, player, count)
            case DrawPersonalCards(count=count):
                step = draw_or_request_personal_cards(
                    next_state, player, count, source=source
                )
            case GainInfluence(times=times) if faction := _paid_influence(reward):
                # A fixed Faction's Influence (Spice Smugglers), prefix
                # ``<box>:influence:<f>`` as the box's other gains name it.
                step = gain_faction_influence(
                    next_state,
                    player,
                    faction,
                    times,
                    event_prefix=f"{source}:influence:{faction.value}",
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

type TargetPiece = (
    GainInfluence
    | PlaceSpy
    | ForceEnemyRetreat
    | CompleteContract
    | BlockChosenSpaceForOpponentsNextAgent
)


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
        case GainInfluence(requires_choice=True, distinct=True):
            # Long Reach's "Choose two Factions" (cleanup-2d).
            return piece
        case PlaceSpy(agent_icons=None):
            return piece
        case (
            ForceEnemyRetreat()
            | CompleteContract()
            | BlockChosenSpaceForOpponentsNextAgent()
        ):
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
        case GainInfluence(times=times) if times > 1:
            # "Choose two" of the Factions, one pick at a time: each a
            # Faction that can rise (OQ-060) and not named yet.
            chosen = _influence_chosen(context)
            return tuple(
                DomainAction(
                    action_id="choose_agent_card_influence",
                    actor=player,
                    arguments=(("faction", faction.value),),
                )
                for faction in Faction
                if influence_can_rise(state.players[player], faction)
                and faction.value not in chosen
            )
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
        case BlockChosenSpaceForOpponentsNextAgent():
            # "Choose any board space" [The Voice card]: every space on the
            # table, occupied or not, the owner's own Agent's included
            # (imperium-base.md 15); a Leader's space only with its Leader.
            return tuple(
                DomainAction(
                    action_id="block_agent_card_space",
                    actor=player,
                    arguments=(("space_id", space.space_id),),
                )
                for space in board_spaces_on_table(state)
            )
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
    # Another player's Spy may share a shared-post Spy's post, never the
    # owner's own [Bloodlines pp. 5, 12; Double Agent card]. The supply is
    # judged now: a recall made earlier this turn may already have been
    # consumed by another effect (Espionage), and then another recall is
    # offered. With nothing to place or recall the box waits for the turn's
    # end like any box that can only fizzle (OQ-057 (1)); after a
    # recall-first the placement is owed.
    options = spy_options(
        state,
        player,
        allowed_post_ids,
        shared_post=piece.shared_post,
        recalled=context.get("agent_card_spy_recalled") is True,
        stuck_passes=False,
    )
    return (
        *(
            (DomainAction(action_id="decline_agent_card_spy", actor=player),)
            if options.pass_up
            else ()
        ),
        *(
            DomainAction(
                action_id="recall_spy_for_agent_card",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.recall
        ),
        *(
            DomainAction(
                action_id="place_agent_card_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.place
        ),
    )


def target_blocked(state: GameState, player: int, ability: Ability) -> bool:
    """Whether the box's condition holds yet it has nothing to choose: every
    Faction it may raise at the top (OQ-060), so it waits for the turn's
    end (OQ-057 (1)); the page names this reason (``display.unavailable``)."""

    _, context = current_agent_effect_context(state)
    (line,) = ability.sections
    return _line_holds(line, state.players[player], context) and not target_rows(
        state, player, ability
    )


def _influence_chosen(context: Mapping[str, ActionValue]) -> list[str]:
    """The Factions this box named so far (they move with the box when the
    other grafted box is made active, ``graft_boxes.swap_boxes``, so a
    second such box of the turn names its own)."""

    value = context.get("influence_chosen", "")
    return str(value).split(",") if value else []


def _pay_named_influence(
    state: GameState, player: int, picks: list[str], source: str
) -> RuleResult:
    working = state
    events: list[GameEvent] = []
    for pick in picks:
        step = gain_faction_influence(
            working, player, Faction(pick), 1, event_prefix=f"{source}:influence:{pick}"
        )
        working = step.state
        events.extend(step.events)
    return RuleResult(state=working, events=tuple(events))


def apply_chosen_influence(state: GameState, action: DomainAction) -> RuleResult:
    """Gain the chosen Faction's Influence and close the box.

    "Choose two" [Long Reach card] names both Factions before either
    Influence moves (designer ruling, OQ-057): the box stays pending until
    the second, different Faction is named. When no second Faction can rise
    any more (every other cube at the top, OQ-060), the one named is paid at
    once and the second is lost, so the owner can use the gain in the rest
    of the turn (user ruling 2026-10-08, "앱처럼 즉시").
    """

    _, context = current_agent_effect_context(state)
    player, card_id = _subject(context)
    faction = Faction(str(dict(action.arguments)["faction"]))
    source = agent_card_source(state.round_number, player, card_id)
    piece = target_piece(box_ability(active_agent_card(context).agent_effect))
    if isinstance(piece, GainInfluence) and piece.times > 1:
        chosen = [*_influence_chosen(context), faction.value]
        second_possible = any(
            influence_can_rise(state.players[player], other)
            and other.value not in chosen
            for other in Faction
        )
        waiting = len(chosen) < piece.times and second_possible
        context["influence_chosen"] = ",".join(chosen)
        context["pending_agent_effect"] = waiting
        if waiting:
            return RuleResult(
                state=advance_after_effect(state, context),
                events=(
                    GameEvent(
                        event_id=f"{source}:influence:{faction.value}:chosen",
                        kind="agent_card_influence_chosen",
                        payload=(("faction", faction.value), ("player", player)),
                    ),
                ),
            )
        paid = _pay_named_influence(state, player, chosen, source)
        return RuleResult(
            state=advance_after_effect(paid.state, context, paid.state.players),
            events=(*paid.events, agent_box_event(source, card_id, player, _RESOLVED)),
        )
    gained = gain_faction_influence(
        state, player, faction, 1, event_prefix=f"{source}:influence:{faction.value}"
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    return RuleResult(
        state=next_state,
        events=(*gained.events, agent_box_event(source, card_id, player, _RESOLVED)),
    )


# --- Discard arrows (stage A3d) -------------------------------------------------
#
# "[You may] discard a card -> reward": the refusal of an optional arrow,
# then one row per hand card; with an empty hand an optional arrow offers
# only its refusal (``discard_cost_block``) and the mandatory one waits and
# fizzles (OQ-057 (1)). The answer discards with the box as its source and
# pays the lines whose condition the discarded card meets: resources with the
# write-back (one ``resources_gained`` ``<box>:resources``, Arrakis
# Observer's 2 spice), then a Contract named ``<box>:contract_reward``, then
# one draw named ``<box>`` (Space-time Folding's second card, Guild Envoy's
# two), and a Spy line leaves the box pending on its Spy step
# (``agent_card_spy_pending``, the rows ``agent_spy_rows``; a Spy placement
# is mandatory, OQ-057 (14)). The events are the discard's, the gain's, the
# follow-ups', then the box's (unless it stays pending). An arrow
# whose rewards are armed (``Ability.armed_icons``: Captured Mentat, Guild
# Spy) pays nothing at once: the keys of the lines the discarded card meets
# are queued in printed order (``effects.arm_agent_icons``), each resolved
# on its own by the icon path (OQ-027), and the box is then mandatory.

_DISCARD_REWARDS = (GainResources, TakeContract, DrawPersonalCards, PlaceSpy)
# The reward each armed key resolves (``agent_effects.resolve_agent_card_icon``).
# That path offers and pays a key per effect (Branching Path's 2 spice), so
# the record table test keeps each key to the boxes it serves.
_ARMED_REWARDS: Final[Mapping[str, tuple[Reward, ...]]] = {
    "intrigue": (DrawIntrigueCards(1),),
    # Piter's ``cards`` draws two.
    "cards": (DrawPersonalCards(1), DrawPersonalCards(2)),
    "spice": (GainResources(spice=2),),
    # Spice Smugglers' 3 Solari (OQ-148).
    "solari": (GainResources(solari=3),),
    "troops": (RecruitTroops(1),),
    "pledge": (PledgeFirstPlaceInfluence(),),
    "research": (Research(),),
}


def _armed_line(key: str, line: EffectSection) -> bool:
    """Whether ``line`` is the one reward the icon path pays for ``key``."""

    if key == "influence":
        # Firm Grip's "choose one: Spacing Guild / Bene Gesserit / Fremen
        # Influence": a chosen Faction's Influence, answered by
        # ``choose_agent_card_influence`` (never a track at the top, OQ-060).
        # Shifting Allegiances' two Influence with one chosen Faction is the
        # same row, one pick for both ([DI p. 16], imperium-base.md 13.3).
        # Spice Smugglers' fixed Spacing Guild Influence is that row with its
        # one Faction (OQ-148), as Clandestine Meeting's printed Faction is.
        if len(line.rewards) != 1 or not isinstance(line.rewards[0], GainInfluence):
            return False
        gain = line.rewards[0]
        if not gain.requires_choice:
            return gain.factions is not None and len(gain.factions) == 1 and (
                gain.times == 1
            )
        return not gain.distinct and (gain.times == 1 or gain.one_faction)
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
    player, box_card_id = _subject(context)
    source = agent_card_source(state.round_number, player, box_card_id)
    if action.action_id == "decline_agent_card_discard":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                agent_box_event(source, box_card_id, player, BoxOutcome.DECLINED),
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
        # With nothing armed the box ends here, with its event (Guild Envoy's
        # discard of a card that is not Spacing Guild).
        done = (
            (agent_box_event(source, box_card_id, player, _RESOLVED),)
            if context["pending_agent_effect"] is not True
            else ()
        )
        return RuleResult(
            state=advance_after_effect(
                discarded.state, context, discarded.state.players
            ),
            events=(*discarded.events, *done),
        )
    rewards = tuple(
        reward
        for line, ok in zip(ability.sections, met, strict=True)
        if ok
        for reward in line.rewards
    )
    owner = discarded.state.players[player]
    events = list(discarded.events)
    for reward in rewards:
        if isinstance(reward, GainResources):
            owner = _gain(owner, reward)
    events.extend(_gains_event(rewards, source, player))
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
        drawn = draw_or_request_personal_cards(next_state, player, draws, source=source)
        next_state = drawn.state
        events.extend(drawn.events)
    if context["pending_agent_effect"] is not True:
        events.append(agent_box_event(source, box_card_id, player, _RESOLVED))
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
    source = agent_card_source(state.round_number, player, card_id)
    if action.action_id == "decline_agent_card_intrigue_payment":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(agent_box_event(source, card_id, player, BoxOutcome.DECLINED),),
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
            events.append(resources_paid_event(source, player, spice=spice))
        for reward in ability.sections[0].rewards:
            match reward:
                case GainVictoryPoints(amount=amount):
                    owner = replace(owner, victory_points=owner.victory_points + amount)
                case GainResources():
                    owner = _gain(owner, reward)
        events.extend(_gains_event(ability.sections[0].rewards, source, player))
        events.append(agent_box_event(source, card_id, player, _RESOLVED))
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
# condition fails. The answer trashes with the box as its source and keeps
# the trash trigger's recruits in the context written back; a box with icons
# left keeps its ``trashes_remaining`` counter on the frame. Shishakli's draw
# is named ``<box>``; the box's event comes last once the box is done.

_TRASH_ICON: Final = TrashPersonalCard()
_THIS_CARD: Final = TrashCard(this_card=True)


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
    costs = tuple(cost for cost in first.costs if isinstance(cost, TrashCard))
    if (
        not 1 <= len(costs) <= 2
        or len(costs) != len(first.costs)
        # "this card and an Emperor card from your hand" [Treacherous
        # Maneuver card]: the pick, then the card itself.
        or (len(costs) == 2 and (costs[1] != _THIS_CARD or costs[0] == _THIS_CARD))
        or costs[0].other_in_play is not None
        or costs[0].grafted is not None
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
        # Shai-Hulud's "[Trash a card] -> [2 troops]" recruits at once.
        isinstance(reward, (DrawPersonalCards, GrantCombatDeployment, RecruitTroops))
        or (isinstance(reward, GainInfluence) and reward.visited_space)
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
    gain = _replacing_gain(ability)
    if gain is not None and replacing_gain_block(owner, gain, context) is not None:
        return ()
    if cost is not None and cost.this_card:
        # "Trash this card" (OQ-022: a card already trashed by another
        # effect expired before this choice was offered).
        card_id = context.get("card_id")
        if isinstance(card_id, str) and card_id in owner.in_play:
            return (card_id,)
        return ()
    if cost is not None and cost.hand_only and cost.faction is not None:
        # "an Emperor card from your hand": another card than the box's own.
        return tuple(
            card_id
            for card_id in owner.hand
            if card_id != context.get("card_id")
            and cost.faction in personal_card_for_instance(card_id).factions
        )
    return trashable_cards(owner, hand_only=cost is not None and cost.hand_only)


def trash_block(
    state: GameState, player: int, ability: Ability, context: Mapping[str, ActionValue]
) -> OptionalEffectBlock | None:
    """Why the box's trash offers no card now: its condition, then no target."""

    owner = state.players[player]
    kind = OptionalBlockKind
    if not _trash_conditions_hold(owner, ability):
        return OptionalEffectBlock(kind.NO_COMMANDER_IN_CONFLICT)
    gain = _replacing_gain(ability)
    if gain is not None and (
        block := replacing_gain_block(owner, gain, context)
    ) is not None:
        return block
    if (dead := _paid_trash_reward_block(state, player, ability)) is not None:
        return dead
    if trash_targets(state, player, ability, context):
        return None
    cost = _trash_cost(ability)
    if cost is not None and cost.this_card:
        return OptionalEffectBlock(kind.NOT_IN_PLAY)
    if cost is not None and cost.faction is Faction.EMPEROR:
        return OptionalEffectBlock(kind.NO_EMPEROR_CARD)
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
    if _paid_trash_reward_block(state, player, ability) is not None:
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


def _paid_trash_reward_block(
    state: GameState, player: int, ability: Ability
) -> OptionalEffectBlock | None:
    """Why a trash paid as the cost of a one-line reward would buy nothing.

    "비용이 있는 줄은 보상 중 하나라도 무언가를 바꿀 수 있을 때만 제시한다"
    (OQ-071, user 2026-09-29), and a cost's side effect -- here the trashed
    card leaving the deck -- never keeps the line alive (OQ-071 extension
    2): Imperial Spy's "Trash this card -> [Intrigue card]" waits while the
    Intrigue deck and its shufflable discard pile are empty (P3d app
    comparison). A draw needs a card to draw, a recruit a troop to take
    (``troop_can_join``); every other reward pays. The first dead reward's
    reason, or None.
    """

    if _trash_cost(ability) is None or len(ability.sections) != 1:
        return None
    blocks = [
        _paid_trash_reward_dead(state, player, reward)
        for reward in ability.sections[0].rewards
    ]
    if not blocks or any(block is None for block in blocks):
        return None
    return blocks[0]


def _paid_trash_reward_dead(
    state: GameState, player: int, reward: Reward
) -> OptionalEffectBlock | None:
    kind = OptionalBlockKind
    match reward:
        case DrawIntrigueCards():
            if not (state.intrigue_deck or shufflable_intrigue_discard(state)):
                return OptionalEffectBlock(kind.NO_INTRIGUE_TO_DRAW)
        case DrawPersonalCards():
            if not gather_intelligence_draw_available(state, player):
                return OptionalEffectBlock(kind.NO_CARD_TO_DRAW)
        case RecruitTroops():
            if not troop_can_join(state, state.players[player]):
                return OptionalEffectBlock(kind.NO_TROOP_TO_RECRUIT)
    return None


def apply_trash(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Refuse the trash, or trash the chosen card and take what it buys."""

    _, context = current_agent_effect_context(state)
    player, box_card_id = _subject(context)
    source = agent_card_source(state.round_number, player, box_card_id)
    context["pending_agent_effect"] = False
    if action.action_id == "decline_agent_card_trash":
        context.pop("trashes_remaining", None)
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                agent_box_event(source, box_card_id, player, BoxOutcome.DECLINED),
            ),
        )
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card trash choice has invalid card ID")
    trashed = trash_personal_card(state, player, card_id, source=source)
    done: tuple[GameEvent, ...] = (
        agent_box_event(source, box_card_id, player, _RESOLVED),
    )
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
            events=(*trashed.events, *done),
        )
    if cost is None:
        # The one black trash icon.
        return RuleResult(
            state=advance_after_effect(trashed.state, context, trashed.state.players),
            events=(*trashed.events, *done),
        )
    if cost.this_card:
        # The card trashed itself as its own cost, so its rewards still pay
        # out (OQ-022).
        context["agent_card_self_trashed"] = True
    if len(ability.sections[0].costs) == 2:
        # "this card and an Emperor card": the card trashes itself after the
        # pick, as part of its own effect (a card trashed by an earlier
        # effect expired before this choice was offered, OQ-022).
        itself = trash_personal_card(trashed.state, player, box_card_id, source=source)
        keep_trash_recruits(context, itself)
        trashed = RuleResult(
            state=itself.state, events=(*trashed.events, *itself.events)
        )
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
    if any(isinstance(reward, GrantCombatDeployment) for reward in paid):
        # The Combat icon [Bloodlines p. 5].
        open_combat_deployment(context)
    if context["pending_agent_effect"] is True:
        # Armed rewards wait as icons; the box is not done.
        done = ()
    for reward in paid:
        if isinstance(reward, RecruitTroops):
            # Shai-Hulud's "[Trash a card] -> [2 troops]": the troops come at
            # once, to the garrison; a troop recruited this turn may be
            # deployed by a Combat space [Main p. 10] [FAQ p. 4].
            recruiting, recruited = recruit_troops(
                trashed.state.players[player], reward.count
            )
            _credit_recruits(context, recruited)
            trashed = RuleResult(
                state=replace(
                    trashed.state,
                    players=replace_player(trashed.state.players, recruiting),
                ),
                events=(
                    *trashed.events,
                    *recruit_shortfall_events(
                        source, player, reward.count, recruited
                    ),
                ),
            )
        if isinstance(reward, GainInfluence) and reward.visited_space:
            faction = _visited_faction(context)
            if reward.replaces_space:
                if context.get(SPACE_INFLUENCE_REPLACED) is True:
                    # A second "instead of one" box adds nothing (see
                    # ``_replace_space_influence``).
                    continue
                _replace_space_influence(context)
            gained = gain_faction_influence(
                trashed.state,
                player,
                faction,
                reward.times,
                event_prefix=f"{source}:influence:{faction.value}",
            )
            trashed = RuleResult(
                state=gained.state, events=(*trashed.events, *gained.events)
            )
    next_state = advance_after_effect(trashed.state, context, trashed.state.players)
    draws = sum(
        reward.count for reward in paid if isinstance(reward, DrawPersonalCards)
    )
    if draws:
        drawn = draw_or_request_personal_cards(next_state, player, draws, source=source)
        return RuleResult(
            state=drawn.state, events=(*trashed.events, *drawn.events, *done)
        )
    return RuleResult(state=next_state, events=(*trashed.events, *done))


# --- A grafted card's trash (cleanup-2d) ------------------------------------------
#
# "You may trash the other grafted card -> Generate 1 specimen" [Dissecting
# Kit card] and "Trash one of the grafted cards, Gain 1 Influence with that
# Faction" [Beguiling Pheromones card]: one row per card the trash may take
# (no card named when only the other one can be), named after the reward
# (``trash_grafted_card_for_specimen`` / ``…_for_influence``), beside the
# refusal for an optional box. The answer is ``agent_effects``' (the other
# grafted card's waiting box expires with it, OQ-022).


def graft_trash_box(ability: Ability | None) -> bool:
    """Whether ``ability`` trashes a grafted card for its reward."""

    if (
        ability is None
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
    ):
        return False
    (line,) = ability.sections
    return (
        len(line.costs) == 1
        and isinstance(line.costs[0], TrashCard)
        and line.costs[0].grafted is not None
        and all(
            isinstance(reward, GenerateSpecimens)
            or (isinstance(reward, GainInfluence) and reward.visited_space)
            for reward in line.rewards
        )
    )


def graft_trash_cost(ability: Ability) -> TrashCard:
    cost = ability.sections[0].costs[0]
    assert isinstance(cost, TrashCard) and cost.grafted is not None
    return cost


def graft_trash_block(
    owner: PlayerState, ability: Ability, context: Mapping[str, ActionValue]
) -> OptionalEffectBlock | None:
    """Why "the other grafted card" cannot be trashed now: it left play."""

    if graft_trash_cost(ability).grafted is GraftedTrash.OTHER:
        partner = other_grafted_card_id(context)
        if not partner or partner not in owner.in_play:
            return OptionalEffectBlock(OptionalBlockKind.NO_PARTNER)
    return None


def graft_trash_targets(
    state: GameState, player: int, ability: Ability, context: Mapping[str, ActionValue]
) -> tuple[str, ...]:
    """The grafted cards the trash may take now: none for the visited
    Faction's gain off a Faction space [Beguiling Pheromones card] or with
    no graft [FAQ p. 1]."""

    owner = state.players[player]
    if graft_trash_block(owner, ability, context) is not None:
        return ()
    visited = any(
        isinstance(reward, GainInfluence) and reward.visited_space
        for reward in ability.sections[0].rewards
    )
    space_id = context.get("space_id")
    if visited and (
        not isinstance(space_id, str) or BOARD_SPACES_BY_ID[space_id].faction is None
    ):
        return ()
    partner = other_grafted_card_id(context)
    if graft_trash_cost(ability).grafted is GraftedTrash.OTHER:
        return (partner,)
    if not is_grafted(context):
        return ()
    return tuple(
        card_id
        for card_id in (context.get("card_id"), partner)
        if isinstance(card_id, str) and card_id in owner.in_play
    )


def graft_trash_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The refusal of an optional box, then one row per card it may take."""

    _, context = current_agent_effect_context(state)
    targets = graft_trash_targets(state, player, ability, context)
    if not targets:
        return ()
    reward = ability.sections[0].rewards[0]
    action_id = (
        "trash_grafted_card_for_specimen"
        if isinstance(reward, GenerateSpecimens)
        else "trash_grafted_card_for_influence"
    )
    names_card = graft_trash_cost(ability).grafted is GraftedTrash.EITHER
    return (
        *(
            (DomainAction(action_id="decline_agent_card_payment", actor=player),)
            if ability.mark is AbilityMark.OPTIONAL
            else ()
        ),
        *(
            DomainAction(
                action_id=action_id,
                actor=player,
                arguments=(("card_id", card_id),) if names_card else (),
            )
            for card_id in targets
        ),
    )


# --- A plain line beside a paid arrow (cleanup-2d) ------------------------------------
#
# "Gain 1 solari per Agent icon on the other grafted card, You may pay 5
# solari -> Advance the Tleilaxu track" [Slig Farmer card]: the plain line
# lands first, so its Solari may pay the arrow. While the arrow can be paid
# and would buy something (OQ-071) the rows are the plain resolution and
# the payment (``pay_agent_card_five_solari_for_tleilaxu``, which pays the
# plain line too); otherwise the plain resolution alone, which
# ``resolve_box`` gives.


def plain_and_paid_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is a plain per-icon gain beside a Solari arrow to
    the Tleilaxu track."""

    if (
        ability is None
        or ability.mark is not AbilityMark.MANDATORY
        or ability.structure is not AbilityStructure.SEQUENCE
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 2
    ):
        return False
    plain, paid = ability.sections
    return (
        not plain.costs
        and plain.condition is None
        and all(
            isinstance(reward, GainSolariPerPartnerAgentIcon)
            for reward in plain.rewards
        )
        and len(paid.costs) == 1
        and isinstance(paid.costs[0], PayResources)
        and paid.costs[0].spice == paid.costs[0].water == 0
        and paid.costs[0].solari > 0
        and paid.condition is None
        and paid.rewards == (AdvanceTleilaxu(1),)
    )


def plain_and_paid_price(ability: Ability) -> int:
    cost = ability.sections[1].costs[0]
    assert isinstance(cost, PayResources)
    return cost.solari


def partner_icon_count(state: GameState, context: Mapping[str, ActionValue]) -> int:
    """The Agent icons the other grafted card has right now
    (``GainSolariPerPartnerAgentIcon``)."""

    partner = other_grafted_card_id(context)
    if not partner:
        return 0
    player = context.get("turn_owner")
    if isinstance(player, bool) or not isinstance(player, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    owner = state.players[player]
    opponents = tuple(seat for seat in state.players if seat.player_id != player)
    # Long Reach in play does not count as its own "another Bene Gesserit
    # card in play" [Long Reach card].
    icons = set(
        effective_agent_icons(
            personal_card_for_instance(partner),
            owner,
            grafted=True,
            opponents=opponents,
            card_instance_id=partner,
        )
    )
    # "그 순간 상대 카드가 가진 Agent 아이콘 전부를 센다" (OQ-055, user ruling
    # "추가된 Agent 아이콘도 세는 게 맞다"): a card that took Urgent
    # Shigawire's boost "has all Agent icons" [Urgent Shigawire card], the
    # eight kinds Spy included [Main p. 9] (docs/rules/player-turns.md), and
    # Emperor's Invitation and Twisted Resourceful give "the card you play
    # this turn" theirs -- both grafted cards are played (OQ-107). User
    # confirmation 2026-10-25 ("P7의 너의 해석이 맞다고 봐. Slig Farmer가
    # 세게 해야지"; engine audit 2026-10-22, P7).
    if partner in boosted_cards(context):
        icons.update(AgentIcon)
    icons.update(
        AgentIcon(value) for value in owner.granted_agent_icon_turn.split(",") if value
    )
    return len(icons)


def plain_and_paid_block(state: GameState, player: int) -> AgentPaymentBlock | None:
    """Why the arrow would buy nothing now: the Tleilaxu token at the track's
    end (OQ-071)."""

    if tleilaxu_track_finished(state.players[player]):
        return AgentPaymentBlock.TLEILAXU_TRACK_END
    return None


def plain_and_paid_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    _, context = current_agent_effect_context(state)
    owner = state.players[player]
    if (
        owner.resources.solari + partner_icon_count(state, context)
        < plain_and_paid_price(ability)
        or plain_and_paid_block(state, player) is not None
    ):
        return ()
    return (
        DomainAction(action_id=_PLAIN_ROW, actor=player),
        DomainAction(action_id="pay_agent_card_five_solari_for_tleilaxu", actor=player),
    )


def apply_plain_and_paid(
    state: GameState,
    player: int,
    ability: Ability,
    context: dict[str, ActionValue],
    source: str,
) -> RuleResult:
    """Pay the plain line, then the arrow out of it (the caller adds the
    box's event)."""

    icon_solari = partner_icon_count(state, context)
    price = plain_and_paid_price(ability)
    owner = state.players[player]
    paid_owner = replace(
        owner,
        resources=replace(
            owner.resources, solari=owner.resources.solari + icon_solari - price
        ),
    )
    next_state = advance_after_effect(
        state, context, replace_player(state.players, paid_owner)
    )
    advanced = advance_tleilaxu(next_state, player, 1)
    return RuleResult(
        state=advanced.state,
        events=(
            *(
                (resources_gained_event(source, player, solari=icon_solari),)
                if icon_solari
                else ()
            ),
            resources_paid_event(source, player, solari=price),
            *advanced.events,
        ),
    )


# --- A paid Shield Wall and sandworm (cleanup-2d) -------------------------------------
#
# "If Maker Hooks: You may pay 2 spice -> You may remove the Shield Wall,
# Summon 1 sandworm" [Arrakis Revolt card]: the removal is optional and
# folded into the payment's rows (OQ-026); ``agent_effects`` offers and pays
# them, reading the spice and the Maker Hooks condition from the record.


def wall_and_worm_box(ability: Ability | None) -> bool:
    """Whether ``ability`` pays spice for an optional Shield Wall removal and
    a sandworm."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
    ):
        return False
    (line,) = ability.sections
    return (
        len(line.costs) == 1
        and isinstance(line.costs[0], PayResources)
        and line.costs[0].solari == line.costs[0].water == 0
        and line.costs[0].spice > 0
        and len(line.rewards) == 2
        and isinstance(line.rewards[0], DestroyShieldWall)
        and isinstance(line.rewards[1], SummonSandworm)
        and line.rewards[1].count == 1
    )


def wall_and_worm_spice(ability: Ability) -> int:
    cost = ability.sections[0].costs[0]
    assert isinstance(cost, PayResources)
    return cost.spice


def wall_and_worm_needs_hooks(ability: Ability) -> bool:
    summon = ability.sections[0].rewards[1]
    assert isinstance(summon, SummonSandworm)
    return summon.requires_maker_hooks


# --- Two discards and a payment (cleanup-2d) ------------------------------------------
#
# "You may discard 2 cards and pay 5 solari -> Gain 1 VP" [Corrinth City
# card]: the whole cost is judged whenever the box resolves, in the owner's
# order [Main pp. 9, 20]; the two cards are picked one by one
# (``select_corrinth_city_discard`` stores the first in
# ``corrinth_first_card_id``, ``pay_corrinth_city`` names the second and
# pays everything at once), beside the refusal
# ``decline_corrinth_city_payment``; the rows keep the card's codec names.


def discard_pay_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional arrow paid by two discards and a
    Solari payment for Victory Points."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
    ):
        return False
    (line,) = ability.sections
    return (
        len(line.costs) == 2
        and line.costs[0] == DiscardFromHand(2)
        and isinstance(line.costs[1], PayResources)
        and line.costs[1].spice == line.costs[1].water == 0
        and line.costs[1].solari > 0
        and all(isinstance(reward, GainVictoryPoints) for reward in line.rewards)
    )


def discard_pay_solari(ability: Ability) -> int:
    cost = ability.sections[0].costs[1]
    assert isinstance(cost, PayResources)
    return cost.solari


def discard_pay_block(
    owner: PlayerState, ability: Ability
) -> OptionalEffectBlock | None:
    """Why the whole cost cannot be paid now: the Solari, then the cards."""

    return short_of(
        OptionalBlockKind.SOLARI, discard_pay_solari(ability), owner.resources.solari
    ) or short_of(OptionalBlockKind.HAND, 2, len(owner.hand))


def discard_pay_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The refusal, then the first pick or the second (paying everything)."""

    _, context = current_agent_effect_context(state)
    owner = state.players[player]
    decline = DomainAction(action_id="decline_corrinth_city_payment", actor=player)
    if discard_pay_block(owner, ability) is not None:
        # Once the cost is unaffordable, only skipping remains.
        return (decline,)
    first_card_id = context.get("corrinth_first_card_id")
    if first_card_id is not None and not isinstance(first_card_id, str):
        raise RuntimeError("pending Corrinth City payment has invalid first card")
    if first_card_id is not None and first_card_id not in owner.hand:
        # A freely ordered effect (an Intrigue discard cost) can consume the
        # stored first pick before the payment completes; the cost then
        # restarts from no pick [Main pp. 9, 20].
        first_card_id = None
    return (
        decline,
        *(
            DomainAction(
                action_id=(
                    "select_corrinth_city_discard"
                    if first_card_id is None
                    else "pay_corrinth_city"
                ),
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in owner.hand
            if card_id != first_card_id
        ),
    )


def apply_discard_pay(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Refuse, store the first pick, or discard both and pay for the gain."""

    _, context = current_agent_effect_context(state)
    player, card_id = _subject(context)
    source = agent_card_source(state.round_number, player, card_id)
    if action.action_id == "decline_corrinth_city_payment":
        context["pending_agent_effect"] = False
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(agent_box_event(source, card_id, player, BoxOutcome.DECLINED),),
        )
    picked = dict(action.arguments).get("card_id")
    if not isinstance(picked, str):
        raise RuntimeError("Corrinth City payment has invalid card ID")
    if action.action_id == "select_corrinth_city_discard":
        context["corrinth_first_card_id"] = picked
        frame = state.decision_stack[-1]
        return RuleResult(
            state=replace(
                state,
                decision_stack=(
                    *state.decision_stack[:-1],
                    replace(frame, context=tuple(sorted(context.items()))),
                ),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:first_discard_selected",
                    kind="corrinth_city_payment_started",
                    payload=(("player", player),),
                ),
            ),
        )
    first_card_id = context.get("corrinth_first_card_id")
    if not isinstance(first_card_id, str):
        raise RuntimeError("Corrinth City payment is missing its first card")
    context["pending_agent_effect"] = False
    solari = discard_pay_solari(ability)
    owner = state.players[player]
    if owner.resources.solari < solari:
        raise RuntimeError("Corrinth City payment requires its Solari")
    paid_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari - solari),
    )
    paid_state = replace(state, players=replace_player(state.players, paid_owner))
    first = discard_personal_card_from_hand(
        paid_state, player, first_card_id, source=source
    )
    second = discard_personal_card_from_hand(first.state, player, picked, source=source)
    gained_owner = second.state.players[player]
    points = sum(
        reward.amount
        for reward in ability.sections[0].rewards
        if isinstance(reward, GainVictoryPoints)
    )
    gained_owner = replace(
        gained_owner, victory_points=gained_owner.victory_points + points
    )
    next_state = advance_after_effect(
        second.state, context, replace_player(second.state.players, gained_owner)
    )
    return RuleResult(
        state=next_state,
        events=(
            *first.events,
            *second.events,
            resources_paid_event(source, player, solari=solari),
            resources_gained_event(source, player, victory_points=points),
            agent_box_event(source, card_id, player, _RESOLVED),
        ),
    )


# --- "Choose two" (cleanup-2d) ------------------------------------------------------
#
# "Choose two: Gain 1 water / Recruit 1 troop / Trash a card / Advance the
# Tleilaxu track" [Stitched Horror card]: both picks are named before either
# is paid (designer ruling, OQ-057), so the second cannot depend on what the
# first produced. Rows ``choose_agent_card_reward(reward=<key>)`` for each
# line not picked yet, in printed order; the first pick keeps the box open
# (``rewards_chosen``), the second pays both: resources and troops with the
# write-back, then the Tleilaxu step and the optional trash frame
# (``<box>:<pick number>``).

# The row key each line's reward is named by.
_CHOSEN_REWARD_KEYS: Final[Mapping[str, Reward]] = {
    "water": GainResources(water=1),
    "troop": RecruitTroops(1),
    "trash": TrashPersonalCard(),
    "tleilaxu": AdvanceTleilaxu(1),
}


def choose_two_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is a "Choose two" of keyed one-reward lines."""

    return (
        ability is not None
        and ability.structure is AbilityStructure.CHOOSE_TWO
        and ability.mark is AbilityMark.MANDATORY
        and ability.hook is None
        and all(
            not line.costs
            and line.condition is None
            and len(line.rewards) == 1
            and line.rewards[0] in _CHOSEN_REWARD_KEYS.values()
            for line in ability.sections
        )
    )


def _reward_key(reward: Reward) -> str:
    return next(key for key, piece in _CHOSEN_REWARD_KEYS.items() if piece == reward)


def chosen_rewards(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    """The keys this box picked so far (they move with the box when the
    other grafted box is made active, ``graft_boxes``)."""

    value = context.get("rewards_chosen", "")
    return tuple(str(value).split(",")) if value else ()


def choose_two_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    _, context = current_agent_effect_context(state)
    chosen = chosen_rewards(context)
    return tuple(
        DomainAction(
            action_id="choose_agent_card_reward",
            actor=player,
            arguments=(("reward", key),),
        )
        for line in ability.sections
        if (key := _reward_key(line.rewards[0])) not in chosen
    )


def apply_chosen_reward(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Record one pick; both pay out after the second (the box's event is
    the caller's)."""

    _, context = current_agent_effect_context(state)
    player, card_id = _subject(context)
    source = agent_card_source(state.round_number, player, card_id)
    key = str(dict(action.arguments)["reward"])
    chosen = (*chosen_rewards(context), key)
    context["rewards_chosen"] = ",".join(chosen)
    context["pending_agent_effect"] = len(chosen) < 2
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:reward:{key}",
            kind="agent_card_reward_chosen",
            payload=(("player", player), ("reward", key)),
        )
    ]
    if context["pending_agent_effect"] is True:
        # The first pick: the box stays open for the second.
        frame = state.decision_stack[-1]
        return RuleResult(
            state=replace(
                state,
                decision_stack=(
                    *state.decision_stack[:-1],
                    replace(frame, context=tuple(sorted(context.items()))),
                ),
            ),
            events=tuple(events),
        )
    picks = tuple(_CHOSEN_REWARD_KEYS[pick] for pick in chosen)
    owner = state.players[player]
    for reward in picks:
        match reward:
            case GainResources():
                owner = _gain(owner, reward)
                events.extend(_gains_event((reward,), source, player))
            case RecruitTroops(count=count):
                owner, recruited = recruit_troops(owner, count)
                _credit_recruits(context, recruited)
                events.extend(
                    recruit_shortfall_events(source, player, count, recruited)
                )
    next_state = advance_after_effect(
        state, context, replace_player(state.players, owner)
    )
    for index, reward in enumerate(picks):
        match reward:
            case AdvanceTleilaxu(count=count):
                advanced = advance_tleilaxu(next_state, player, count)
                next_state = advanced.state
                events.extend(advanced.events)
            case TrashPersonalCard():
                next_state = open_optional_trash(
                    next_state,
                    player,
                    f"{source}:{index + 1}",
                    printer=_box_trash_printer(context),
                )
    return RuleResult(state=next_state, events=tuple(events))


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


# --- Influence-loss arrows (stage P3b) -------------------------------------------
#
# "[lose 1 Influence with a chosen Faction] [2 spice] -> [2 Influence with one
# chosen Faction]" (Shifting Allegiances): an optional arrow paid once [DI p. 9]
# [FAQ p. 3]. The whole cost is judged whenever the box resolves, in the owner's
# order [Main pp. 9, 20] (OQ-028): the spice and a Faction the owner has
# Influence with ("Influence가 없는 진영은 잃을 수 없다", imperium-base.md 13.2). The
# refusal, then one ``lose_agent_card_influence`` row per such Faction -- and
# per recipient where its Alliance token could go to several seats, as every
# Influence loss offers it -- answers the cost: the spice is paid, the Influence
# lost through the common loss path (the Alliance and the Victory Point move as
# the Reveal exchange's do), and the +2 is armed as an "influence" icon, whose
# one Faction the owner picks next (``choose_agent_card_influence``, one pick for
# both: an unbreakable effect, imperium-base.md 13.3). The same Faction may be
# lost and gained again ("같은 진영을 잃고 얻을 수 있다", 13.2, [FAQ p. 4]); as the
# Faction just lowered is below the top, the +2 always has a Faction to raise, so
# no payment buys nothing (OQ-071).


def influence_loss_box(ability: Ability | None) -> bool:
    """Whether ``ability`` is an optional arrow paid by losing one Influence
    and a Resource payment, for one chosen Faction's Influence."""

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
        or ability.armed_icons != ("influence",)
    ):
        return False
    (line,) = ability.sections
    return (
        line.condition is None
        and len(line.costs) == 2
        and line.costs[0] == LoseInfluence(1)
        and isinstance(line.costs[1], PayResources)
        and line.costs[1].solari == line.costs[1].water == 0
        and line.costs[1].spice > 0
        and _armed_line("influence", line)
    )


def influence_loss_spice(ability: Ability) -> int:
    """The spice the arrow's cost pays beside the Influence."""

    cost = ability.sections[0].costs[1]
    assert isinstance(cost, PayResources)
    return cost.spice


def influence_loss_block(
    owner: PlayerState, ability: Ability
) -> OptionalEffectBlock | None:
    """Why the whole cost cannot be paid now: the spice, then an Influence
    to lose."""

    spice = short_of(
        OptionalBlockKind.SPICE, influence_loss_spice(ability), owner.resources.spice
    )
    if spice is not None:
        return spice
    if any(influence_amount(owner.influence, faction) >= 1 for faction in Faction):
        return None
    return OptionalEffectBlock(OptionalBlockKind.NO_INFLUENCE_TO_LOSE)


def influence_loss_rows(
    state: GameState, player: int, ability: Ability
) -> tuple[DomainAction, ...]:
    """The refusal, then each Faction the owner has Influence with to lose,
    and where its Alliance token may go to several seats, each recipient."""

    owner = state.players[player]
    rows = [DomainAction(action_id="decline_agent_card_payment", actor=player)]
    if influence_loss_block(owner, ability) is not None:
        return tuple(rows)
    for faction in Faction:
        if influence_amount(owner.influence, faction) < 1:
            continue
        recipients = alliance_recipients_after_influence_loss(state, player, faction)
        for recipient in tuple(recipients) if len(recipients) > 1 else (None,):
            arguments: tuple[tuple[str, ActionValue], ...] = (
                ("faction", faction.value),
            )
            if recipient is not None:
                arguments = (("alliance_recipient", recipient), *arguments)
            rows.append(
                DomainAction(
                    action_id="lose_agent_card_influence",
                    actor=player,
                    arguments=arguments,
                )
            )
    return tuple(rows)


def apply_influence_loss(
    state: GameState,
    action: DomainAction,
    ability: Ability,
    context: dict[str, ActionValue],
    source: str,
) -> RuleResult:
    """Pay the spice, lose the chosen Faction's Influence and arm the arrow's
    reward (the refusal is the payment handler's). The frame is written back
    first, with the spice paid, so what the loss records there stays."""

    arguments = dict(action.arguments)
    faction = Faction(str(arguments["faction"]))
    recipient = arguments.get("alliance_recipient")
    if recipient is not None and (
        isinstance(recipient, bool) or not isinstance(recipient, int)
    ):
        raise RuntimeError("Influence loss has an invalid Alliance recipient")
    spice = influence_loss_spice(ability)
    owner = state.players[action.actor]
    paid_owner = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice - spice),
        spice_spent_turn=owner.spice_spent_turn + spice,
    )
    arm_agent_icons(context, ability.armed_icons)
    settled = advance_after_effect(
        state, context, replace_player(state.players, paid_owner)
    )
    lost = lose_faction_influence(
        settled,
        action.actor,
        faction,
        1,
        event_prefix=f"{source}:lost:{faction.value}",
        alliance_recipient=recipient,
    )
    return RuleResult(
        state=lost.state,
        events=(resources_paid_event(source, action.actor, spice=spice), *lost.events),
    )


# --- A plain line beside a choice line (stage A3f) --------------------------------
#
# Two printed lines, the second a choice: "Choose one: Draw 1 card / If Bene
# Gesserit Bond: Gain 1 Bene Gesserit Influence" (Southern Faith) and "If 2
# or more Spacing Guild Influence: Choose one: Draw 1 card / Combat" (High
# Priority Travel). The plain line resolves as one action (``resolve_box``,
# the A2 conventions). While the choice line's condition holds and it has a
# target, its rows are offered beside the plain row; otherwise the frame
# offers the plain row alone. The Combat answers through its own handler
# (``take_agent_card_combat_icon``). Interstellar Conspiracy's two lines,
# a sequence whose choice once paid the plain line too, are two icons since
# the engine audit 2026-10-22 (P4; OQ-027 extension 3).

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
    if len(choice.rewards) != 1:
        return False
    if ability.structure is not AbilityStructure.ONE_OF:
        # Two lines both paid resolve icon by icon (OQ-027 extension 3).
        return False
    match choice.rewards[0]:
        case (
            GainInfluence(times=1, distinct=False)
            | GrantCombatDeployment()
            | TakeCardFromDiscard()
        ):
            pass
        case _:
            return False
    return all(
        isinstance(reward, (DrawPersonalCards, GainResources))
        for reward in plain.rewards
    )


def either_choice(
    ability: Ability,
) -> GainInfluence | GrantCombatDeployment | TakeCardFromDiscard:
    """The choice line's one reward."""

    piece = ability.sections[1].rewards[0]
    assert isinstance(
        piece, (GainInfluence, GrantCombatDeployment, TakeCardFromDiscard)
    )
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
    elif isinstance(piece, TakeCardFromDiscard):
        rows = discard_take_rows(state.players[player], piece, player)
    else:
        rows = (DomainAction(action_id="take_agent_card_combat_icon", actor=player),)
    if not rows:
        return ()
    if _line_holds(ability.sections[0], state.players[player], context):
        return (DomainAction(action_id=_PLAIN_ROW, actor=player), *rows)
    return rows


def discard_take_rows(
    owner: PlayerState, piece: TakeCardFromDiscard, player: int
) -> tuple[DomainAction, ...]:
    """One row per card of the owner's discard pile that has the piece's
    Faction ("only if one is there", imperium-base.md 15), in pile order."""

    return tuple(
        DomainAction(
            action_id="take_agent_card_from_discard",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in owner.discard_pile
        if piece.faction in personal_card_for_instance(card_id).factions
    )


def apply_discard_take(state: GameState, action: DomainAction) -> RuleResult:
    """Put the chosen discard-pile card into the owner's hand (the "-OR-"
    line taken, so the draw is gone). The pile is face up, so the card is a
    publicly acquired hand card, known to every seat (imperium-base.md 14,
    OQ-010: ``PlayerState.hand_public``)."""

    _, context = current_agent_effect_context(state)
    _, card_id = _subject(context)
    player = action.actor
    taken = dict(action.arguments)["card_id"]
    if not isinstance(taken, str):
        raise RuntimeError("Agent-card discard take has an invalid card")
    source = agent_card_source(state.round_number, player, card_id)
    owner = state.players[player]
    pile = list(owner.discard_pile)
    pile.remove(taken)
    next_owner = replace(
        owner,
        discard_pile=tuple(pile),
        hand=(*owner.hand, taken),
        hand_public=(*owner.hand_public, taken),
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        state, context, replace_player(state.players, next_owner)
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:discard_pile:{taken}",
                kind="card_returned_to_hand",
                payload=(("card_id", taken), ("player", player)),
            ),
        ),
    )


def apply_either_influence(
    state: GameState, action: DomainAction, ability: Ability
) -> RuleResult:
    """Gain the chosen Faction's Influence (the "Choose one" line taken)."""

    _, context = current_agent_effect_context(state)
    _, card_id = _subject(context)
    player = action.actor
    faction = Faction(str(dict(action.arguments)["faction"]))
    source = agent_card_source(state.round_number, player, card_id)
    gained = gain_faction_influence(
        state, player, faction, 1, event_prefix=f"{source}:influence:{faction.value}"
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    return RuleResult(
        state=next_state,
        events=(
            *gained.events,
            agent_box_event(source, card_id, player, _RESOLVED),
        ),
    )
