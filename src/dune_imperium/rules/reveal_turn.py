"""Start and score the basic portion of an Uprising Reveal turn.

Reveal effects resolve in any order the owner likes, with Persuasion usable
before, between and after them [Main p. 12]. Every choice effect of a
revealed card -- at the Reveal's start in hand order, a late arrival's after
it -- waits as a pending entry on the Reveal frame (OQ-095 (7) addition, user
ruling 2026-10-14). The Reveal frame offers each entry whose printed
condition holds now with the actions its ``REVEAL_CHOICE`` frame offers,
beside the purchases, gains and Plots (``legal_pending_reveal_choice_actions``);
taking one takes the entry off the list and runs it on its own
``REVEAL_CHOICE`` frame (``open_pending_reveal_choice``), which closes when
the choice is done. Only a step that must be followed at once keeps that
frame on top (a Spy recalled for its placement). An optional choice ("may",
an arrow cost, a black trash icon [FAQ p. 3]) offers no refusal and lapses
at ``finish_reveal``; a mandatory one holds ``finish_reveal`` while it offers
something (its record is marked optional,
``content.uprising.reveal_choice_abilities``). An entry
whose condition fails now (too few Spies, not enough Spice, Command (6+) not
reached) waits, because a later Reveal choice can still open it, and lapses
at the end if it never does (``reveal_choice_lapsed``).
"""

from collections.abc import Callable, Mapping
from copy import replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from dune_imperium.content.bloodlines.sardaukar import (
    SkillDefinition,
    skill_for_instance,
)
from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.abilities import Ability, AbilityStructure
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    CompletedContractsAtLeast,
    Condition,
    DrawIntrigueCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GrantCombatDeployment,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RevealPersuasion,
    RevealSwords,
    Reward,
    SpiesPlacedAtLeast,
    TakeContract,
    TakeHighCouncilSeat,
    TechTilesAtLeast,
    TrashCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.reveal_choice_abilities import (
    reveal_choice_ability,
    reveal_choice_is_optional,
)
from dune_imperium.content.uprising.types import (
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.card_trash import credit_trash_recruits, trash_personal_card
from dune_imperium.rules.combat_deployment import (
    deployment_rooms,
    grant_combat_icon,
    reconcile_deployment_after_retreat,
    undeployable_troops,
)
from dune_imperium.rules.effects import recruit_shortfall_events, recruit_troops
from dune_imperium.rules.frames import (
    COMMANDERS_RECRUITED_KEY,
    REVEAL_COMMANDERS_RECRUITED_KEY,
    TECH_ACQUIRE_PENDING_KEY,
    FrameKind,
    context_int,
    context_str,
    frame_context,
    owes_held_draw,
    owes_track_spy,
    owned_top_frame,
    recruited_commander_count,
    replace_player,
    replace_top_frame,
    reset_turn_counters,
    reveal_is_open_for,
    with_context,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    influence_can_rise,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import (
    credit_suspensor_suits,
    draw_or_queue_intrigue_cards,
)
from dune_imperium.rules.intrigue_triggers import expire_reveal_faceup_intrigue
from dune_imperium.rules.planetologist import replace_sandworms, replaces_sandworms
from dune_imperium.rules.scouts_offers import (
    queue_reveal_subcommittee_offer,
    reveal_subcommittee_offer,
)
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.specimens import generate_specimens
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    is_spying_on_maker_space,
    place_spy,
    recall_spy,
    spied_factions,
)
from dune_imperium.rules.strength import units_strength
from dune_imperium.rules.tactics import advance_tactics_token
from dune_imperium.rules.unit_loss import lose_unit
from dune_imperium.rules.units import retreat_units

# Immortality Reveal choices whose enum names do not fit a comparison line.
_LOSE_INFLUENCE_FOR_VP = (
    PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE
)
_LOSE_TROOPS_FOR_SPECIMENS = (
    PersonalCardRevealChoiceEffect.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS
)
# Tleilaxu Surgeon's two troops: (zones argument, garrison needed, Conflict
# needed).
SURGEON_ZONE_PAIRS = (
    ("garrison,garrison", 2, 0),
    ("garrison,conflict", 1, 1),
    ("conflict,conflict", 0, 2),
)

# What each Reveal choice effect's frame can offer (the ``REVEAL_CHOICE``
# providers below and ``acquisition.legal_reveal_command_acquisition_actions``),
# by action id. The Reveal frame offers them for its pending entries (codec
# v147), and taking one opens that entry's own frame
# (``open_pending_reveal_choice``). ``tests/unit/rules/test_reveal_choices.py``
# checks the providers against it.
_SPY_ICON_ACTIONS: Final = frozenset(
    {"place_reveal_spy", "recall_spy_for_reveal_placement", "decline_reveal_spy_recall"}
)
_TRASH_ACTIONS: Final = frozenset({"trash_reveal_card"})
_RETREAT_ACTIONS: Final = frozenset({"retreat_two_troops_for_reveal"})
_TROOP_MOVE_ACTIONS: Final = frozenset(
    {"deploy_reveal_card_troop", "retreat_reveal_card_troop"}
)
_INFLUENCE_GAIN_ACTIONS: Final = frozenset({"gain_reveal_influence"})
_Choice = PersonalCardRevealChoiceEffect
REVEAL_CHOICE_EFFECT_ACTIONS: Final[Mapping[_Choice, frozenset[str]]] = {
    _Choice.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED: frozenset(
        {"recall_spy_for_reveal"}
    ),
    _Choice.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION: frozenset(
        {"recall_spies_for_reveal"}
    ),
    _Choice.MAY_RECALL_SPY_FOR_THREE_STRENGTH: frozenset({"recall_spy_for_reveal"}),
    _Choice.PLACE_SPY: _SPY_ICON_ACTIONS,
    _Choice.PLACE_TWO_SPIES: _SPY_ICON_ACTIONS,
    _Choice.COMMAND_PLACE_SPY: _SPY_ICON_ACTIONS,
    _Choice.PLACE_SPY_OR_GAIN_TWO_STRENGTH: frozenset(
        {
            "gain_two_reveal_strength",
            "place_reveal_spy",
            "recall_spy_for_reveal_placement",
        }
    ),
    _Choice.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE: frozenset(
        {"exchange_reveal_influence"}
    ),
    _Choice.MAY_PAY_THREE_SPICE_FOR_INFLUENCE: frozenset(
        {"pay_reveal_spice_influence"}
    ),
    _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH: _TRASH_ACTIONS,
    _Choice.COMMAND_MAY_TRASH_CARD: _TRASH_ACTIONS,
    _Choice.MAY_TRASH_SELF_FOR_COMBAT_ICON: _TRASH_ACTIONS,
    _Choice.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS: _TRASH_ACTIONS,
    _Choice.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH: _RETREAT_ACTIONS,
    _Choice.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION: _RETREAT_ACTIONS,
    _Choice.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL: frozenset(
        {"gain_five_reveal_solari", "take_high_council_from_reveal"}
    ),
    _Choice.MAY_PAY_WATER_FOR_SANDWORM: frozenset(
        {"decline_reveal_sandworm", "pay_reveal_water_for_sandworm"}
    ),
    _Choice.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS: frozenset(
        {"keep_contract_reveal_spice", "trash_contract_reveal_for_vp"}
    ),
    _Choice.PERSUASION_OR_CONTRACT: frozenset(
        {"gain_reveal_persuasion", "take_reveal_contract"}
    ),
    _Choice.COMMAND_GAIN_CHOSEN_INFLUENCE: _INFLUENCE_GAIN_ACTIONS,
    _Choice.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH: _INFLUENCE_GAIN_ACTIONS,
    _Choice.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD: frozenset(
        {"command_acquire_row_card"}
    ),
    _Choice.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE: frozenset(
        {"lose_reveal_influence_for_vp"}
    ),
    _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP: _TROOP_MOVE_ACTIONS,
    _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND: _TROOP_MOVE_ACTIONS,
    _Choice.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS: frozenset(
        {"lose_reveal_troops_for_specimens"}
    ),
}
REVEAL_CHOICE_ACTION_IDS: Final = frozenset().union(
    *REVEAL_CHOICE_EFFECT_ACTIONS.values()
)

# The argument naming the revealed card (its definition id; copies of one
# card are interchangeable) whose choice an action resolves. With every
# pending choice offered at once (codec v147), these ids are produced by
# different cards: Calculus of Power's, Shrouded Counsel's, Disruption
# Tactics' and CHOAM Demands' trash; Spy Network's and Arrakis Observer's
# recall; Chani's and Command Center's retreat; a plain Spy icon's and
# Undercover Asset's placement (and recall-first); Priority Contracts' 2
# spice and Delivery Agreement's 1; Pointing the Way's and Ixian
# Ambassador's Influence; Shadout Mapes' and Unswerving Loyalty's troop
# move (the latter needs a Fremen Bond); and the plain Spy icons' pass of
# their empty-supply recall-first. Whichever entry takes the row is used up
# and the event names its card, so every id more than one card produces
# always carries it.
SOURCE_ARGUMENT: Final = "source"
SOURCED_REVEAL_ACTION_IDS: Final = frozenset(
    {
        "trash_reveal_card",
        "recall_spy_for_reveal",
        "retreat_two_troops_for_reveal",
        "place_reveal_spy",
        "recall_spy_for_reveal_placement",
        "keep_contract_reveal_spice",
        "trash_contract_reveal_for_vp",
        "gain_reveal_influence",
        "deploy_reveal_card_troop",
        "retreat_reveal_card_troop",
        "decline_reveal_spy_recall",
    }
)


def reveal_card_identity(card_id: str) -> str:
    """The definition id of a revealed card instance (``source``'s value)."""

    return personal_card_for_instance(card_id).card.card_id


def _sourced(
    action_id: str,
    player: int,
    card_id: str,
    arguments: tuple[tuple[str, ActionValue], ...] = (),
) -> DomainAction:
    """``action_id`` of the Reveal choice of ``card_id``, naming its card."""

    return DomainAction(
        action_id=action_id,
        actor=player,
        arguments=tuple(
            sorted((*arguments, (SOURCE_ARGUMENT, reveal_card_identity(card_id))))
        ),
    )


# --- "Target -> reward" Reveal choices from their records (composed A4d) ------
#
# Spy Network, Arrakis Observer (recall a Spy), Calculus of Power, Disruption
# Tactics, CHOAM Demands (trash a card), Shrouded Counsel (trash a card as the
# reward), Pointing the Way and Ixian Ambassador (a chosen Faction): one row
# per target, named by the card (``source``), resolved in one step. The
# record's line says which target, which reward and its printed condition;
# the events keep their roots under ``round:R:player:P:reveal_card:<card>``:
# the recall or trash first (with the trashed card's own trigger and its
# recruits credited), then the reward -- the Reveal swords
# (``<root>:strength``, counted only with a unit in the Conflict and kept
# for Leadership), the Intrigue card drawn in the same step
# (``<root>:intrigue_draw``, queued with an empty deck), the Combat icon, or
# one Influence with each Faction (``<root>:influence:<f>``).


def target_reward_choice(ability: Ability | None) -> bool:
    """Whether a Reveal choice record resolves by the "target -> reward"
    shape: one line paying one target -- a recalled Spy, a card trashed, or a
    chosen Faction -- for its reward."""

    if (
        ability is None
        or ability.hook is not None
        or ability.structure is not AbilityStructure.SEQUENCE
        or len(ability.sections) != 1
    ):
        return False
    (line,) = ability.sections
    match line.costs:
        case (RecallSpy(count=1),) | (TrashCard(hand_only=False),):
            return all(
                isinstance(
                    reward,
                    (
                        RevealSwords,
                        DrawIntrigueCards,
                        GrantCombatDeployment,
                        GainInfluence,
                    ),
                )
                and not (isinstance(reward, GainInfluence) and reward.requires_choice)
                for reward in line.rewards
            )
        case ():
            return line.rewards in ((GainInfluence(),), (TrashPersonalCard(),))
    return False


def _target_reward_line(effect: PersonalCardRevealChoiceEffect) -> EffectSection:
    ability = reveal_choice_ability(effect)
    if not target_reward_choice(ability):
        raise ValueError(f"{effect} is not a target -> reward Reveal choice")
    return ability.sections[0]


def _target_condition_holds(
    condition: Condition | None, owner: PlayerState, persuasion: int | None
) -> bool:
    """A "target -> reward" line's printed condition, judged now (OQ-028):
    Command on the Persuasion generated this Reveal turn [Bloodlines pp. 5,
    12]."""

    match condition:
        case None:
            return True
        case CommandReached():
            return persuasion is not None and persuasion >= COMMAND_PERSUASION
        case SpiesPlacedAtLeast(count=count):
            return len(owner.spy_post_ids) >= count
        case TechTilesAtLeast(count=count):
            return len(owner.tech_ids) >= count
        case CompletedContractsAtLeast(count=count):
            return len(owner.completed_contract_ids) >= count
    raise TypeError(f"{condition!r} is not a Reveal choice condition")


def _target_reward_targets(
    owner: PlayerState,
    card_id: str,
    line: EffectSection,
    others_in_play: tuple[str, ...],
) -> tuple[str, ...]:
    """What a "target -> reward" line may be paid with, in offer order: own
    Spies in board order; this card while in play; another card of a
    Faction counted in play; any card in hand, discard pile or counted in
    play (Shrouded Counsel's black trash icon [Main p. 20]); a Faction whose
    cube can still rise (OQ-060). ``others_in_play`` are the cards another
    card's trash may take: the rows read the owner's, the gate its caller's
    snapshot, as before."""

    match line.costs:
        case (RecallSpy(),):
            occupied = frozenset(owner.spy_post_ids)
            return tuple(
                post.post_id for post in OBSERVATION_POSTS if post.post_id in occupied
            )
        case (TrashCard(this_card=True),):
            return (card_id,) if card_id in owner.in_play else ()
        case (TrashCard(other_in_play=faction),) if faction is not None:
            return tuple(
                candidate
                for candidate in others_in_play
                if candidate != card_id
                and faction in personal_card_for_instance(candidate).factions
            )
    if line.rewards == (TrashPersonalCard(),):
        return (*owner.hand, *owner.discard_pile, *counted_in_play(owner))
    return tuple(
        faction.value for faction in Faction if influence_can_rise(owner, faction)
    )


def target_reward_is_available(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    effect: PersonalCardRevealChoiceEffect,
    persuasion: int | None,
) -> bool:
    """The gate of a "target -> reward" choice: its printed condition holds
    and it has something to pay with -- for a self-trash, the card counted in
    play; Disruption Tactics' trash needs no condition, so its gate holds
    and its row waits for the card in play."""

    line = _target_reward_line(effect)
    if not _target_condition_holds(line.condition, owner, persuasion):
        return False
    match line.costs:
        case (TrashCard(this_card=True),):
            return line.condition is None or card_id in cards_in_play
    return bool(_target_reward_targets(owner, card_id, line, cards_in_play))


def _target_reward_action_id(line: EffectSection) -> tuple[str, str]:
    match line.costs:
        case (RecallSpy(),):
            return "recall_spy_for_reveal", "post_id"
        case (TrashCard(),):
            return "trash_reveal_card", "card_id"
    if line.rewards == (TrashPersonalCard(),):
        return "trash_reveal_card", "card_id"
    return "gain_reveal_influence", "faction"


def target_reward_rows(
    state: GameState, player: int, card_id: str, effect: PersonalCardRevealChoiceEffect
) -> tuple[DomainAction, ...]:
    """A "target -> reward" choice's rows on its own frame: one per target,
    named by the card; an owner-readable condition (Spies placed) is judged
    again here, as a freely ordered recall can drop it."""

    line = _target_reward_line(effect)
    owner = state.players[player]
    if isinstance(line.condition, SpiesPlacedAtLeast) and not _target_condition_holds(
        line.condition, owner, None
    ):
        return ()
    action_id, argument = _target_reward_action_id(line)
    return tuple(
        _sourced(action_id, player, card_id, ((argument, target),))
        for target in _target_reward_targets(
            owner, card_id, line, counted_in_play(owner)
        )
    )


def _choice_frame_effect(
    state: GameState, player: int
) -> tuple[str, PersonalCardRevealChoiceEffect] | None:
    """The card and choice of ``player``'s ``REVEAL_CHOICE`` frame on top."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    context = dict(frame.context)
    effect_value = context.get("reveal_choice_effect")
    card_id = context.get("reveal_card_id")
    if not isinstance(effect_value, str) or not isinstance(card_id, str):
        return None
    return card_id, PersonalCardRevealChoiceEffect(effect_value)


def resolve_target_reward(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve an opened "target -> reward" choice (see the section note)."""

    opened = _choice_frame_effect(state, action.actor)
    if opened is None:
        raise RuntimeError("Reveal choice frame has invalid context")
    card_id, effect = opened
    line = _target_reward_line(effect)
    player = action.actor
    source = f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
    _, argument = _target_reward_action_id(line)
    target = dict(action.arguments).get(argument)
    if not isinstance(target, str):
        raise RuntimeError("Reveal choice has invalid target")
    if line.rewards == (GainInfluence(),):
        # A chosen Faction's Influence; the choice's frame closes after it.
        gained = gain_faction_influence(
            state,
            player,
            Faction(target),
            1,
            event_prefix=f"{source}:influence:{target}",
        )
        return RuleResult(
            state=replace(
                gained.state, decision_stack=gained.state.decision_stack[:-1]
            ),
            events=gained.events,
        )
    events: list[GameEvent] = []
    working = state
    if isinstance(line.costs[0] if line.costs else None, RecallSpy):
        working = replace(
            working,
            players=replace_player(
                working.players, recall_spy(working.players[player], target)
            ),
        )
        events.append(_spy_recalled_event(state, player, card_id, target))
    else:
        trashed = trash_personal_card(working, player, target, source=source)
        # The frame on top here is this Reveal choice's own, not an
        # AGENT_EFFECTS frame, so ``trash_personal_card`` never credited a
        # troop-on-trash trigger (Eliminate Allies) anywhere: "그 turn에
        # 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수 있다"
        # [Main p. 10] [FAQ p. 4], and the Combat 아이콘 deploys "이번
        # turn에 recruit한 유닛 전부" [Bloodlines pp. 5, 12].
        trashed = credit_trash_recruits(trashed, player)
        working = trashed.state
        events.extend(trashed.events)
    working = replace(working, decision_stack=working.decision_stack[:-1])
    for reward in line.rewards:
        match reward:
            case RevealSwords(amount=amount):
                # Like Devious Strength: the swords count only while units
                # are in the Conflict [Main pp. 12-13].
                owner = working.players[player]
                counted = amount if owner.units_in_conflict else 0
                remaining = add_reveal_optional_sword_strength(
                    working.decision_stack, amount, card_id=card_id
                )
                if counted:
                    remaining = add_reveal_strength(remaining, counted)
                working = replace(
                    working,
                    players=replace_player(
                        working.players,
                        replace(owner, combat_strength=owner.combat_strength + counted),
                    ),
                    decision_stack=remaining,
                )
                events.append(
                    GameEvent(
                        event_id=f"{source}:strength",
                        kind="reveal_strength_gained",
                        payload=(
                            ("amount", amount),
                            ("card_id", card_id),
                            ("player", player),
                        ),
                    )
                )
            case DrawIntrigueCards(count=1):
                # Spy Network's card is drawn with its recall, in the same
                # step: its arrow cost pays for it.
                owner = working.players[player]
                if working.intrigue_deck:
                    owner = credit_suspensor_suits(
                        state,
                        replace(
                            owner,
                            intrigue_cards=(
                                *owner.intrigue_cards,
                                working.intrigue_deck[0],
                            ),
                        ),
                        1,
                    )
                    working = replace(
                        working,
                        players=replace_player(working.players, owner),
                        intrigue_deck=working.intrigue_deck[1:],
                    )
                    events.append(
                        GameEvent(
                            event_id=f"{source}:intrigue_draw",
                            kind="intrigue_card_drawn",
                            payload=(("count", 1), ("player", player)),
                        )
                    )
                else:
                    working = replace(
                        working,
                        pending_intrigue_draws=(
                            *working.pending_intrigue_draws,
                            (player, 1, f"{source}:intrigue_draw"),
                        ),
                    )
            case GrantCombatDeployment():
                # The Combat icon opens this Reveal's deployment window
                # [Bloodlines p. 5].
                working = grant_combat_icon(working, player)
            case GainInfluence(factions=(faction,)):
                gained = gain_faction_influence(
                    working,
                    player,
                    faction,
                    1,
                    event_prefix=f"{source}:influence:{faction.value}",
                )
                working = gained.state
                events.extend(gained.events)
            case TrashPersonalCard():
                pass  # Shrouded Counsel: the trash is the whole reward.
            case _:
                raise TypeError(f"{reward!r} is not a target -> reward reward")
    return RuleResult(state=working, events=tuple(events))


# --- Spy icons and printed "-OR-"s from their records (composed A4e, A4f) ---


def spy_icon_choice(ability: Ability | None) -> bool:
    """Whether a Reveal choice record is a Spy icon (Public Spectacle, Wheels
    within Wheels, Covert Operation's two, Intelligence Training's Command
    one) or Undercover Asset's "Place a Spy -OR- +2 swords"."""

    if ability is None or ability.hook is not None or not ability.sections:
        return False
    spy_lines = [line for line in ability.sections if line.rewards == (PlaceSpy(),)]
    if ability.structure is AbilityStructure.ONE_OF:
        return len(spy_lines) == 1 and _spy_alternative(ability) is not None
    return len(spy_lines) == len(ability.sections)


def _spy_alternative(ability: Ability) -> RevealSwords | None:
    """Undercover Asset's printed alternative to its Spy icon."""

    if ability.structure is not AbilityStructure.ONE_OF:
        return None
    for line in ability.sections:
        match line.rewards:
            case (RevealSwords() as swords,):
                return swords
    return None


def _spy_icons(ability: Ability) -> int:
    return sum(1 for line in ability.sections if line.rewards == (PlaceSpy(),))


# The printed "-OR-" lines whose row each is (Corrinth City, Delivery
# Logistics), by the line's reward.
_EITHER_LINE_ACTIONS: Final[Mapping[Reward, str]] = MappingProxyType(
    {
        GainResources(solari=5): "gain_five_reveal_solari",
        TakeHighCouncilSeat(): "take_high_council_from_reveal",
        RevealPersuasion(1): "gain_reveal_persuasion",
        TakeContract(1): "take_reveal_contract",
    }
)


def either_choice(ability: Ability | None) -> bool:
    """Whether a Reveal choice record is a printed "-OR-" whose every line is
    its own row (Corrinth City, Delivery Logistics)."""

    return (
        ability is not None
        and ability.hook is None
        and ability.structure is AbilityStructure.ONE_OF
        and all(
            len(line.rewards) == 1 and line.rewards[0] in _EITHER_LINE_ACTIONS
            for line in ability.sections
        )
    )


def _either_line_open(owner: PlayerState, line: EffectSection) -> bool:
    """Whether a "-OR-" line can be chosen now: the seat taken only by a
    seat-less owner who can pay for it."""

    if line.rewards == (TakeHighCouncilSeat(),):
        if owner.high_council:
            return False
    for cost in line.costs:
        match cost:
            case PayResources(solari=solari, spice=spice, water=water):
                if (
                    owner.resources.solari < solari
                    or owner.resources.spice < spice
                    or owner.resources.water < water
                ):
                    return False
    return True


def either_is_available(state: GameState, ability: Ability) -> bool:
    """The gate of a printed "-OR-": always open -- one line needs nothing --
    except that a Contract line is a CHOAM card's (Delivery Logistics), open
    only with the CHOAM module."""

    return state.config.choam_module or not any(
        line.rewards == (TakeContract(1),) for line in ability.sections
    )


def either_rows(
    state: GameState, player: int, effect: PersonalCardRevealChoiceEffect
) -> tuple[DomainAction, ...]:
    """A printed "-OR-"'s rows, one per line it can take now, printed order."""

    ability = reveal_choice_ability(effect)
    owner = state.players[player]
    return tuple(
        DomainAction(action_id=_EITHER_LINE_ACTIONS[line.rewards[0]], actor=player)
        for line in ability.sections
        if _either_line_open(owner, line)
    )


def resolve_either(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve the opened "-OR-" line ``action`` takes: Corrinth City's 5
    Solari (``<root>:solari``) or its seat (``<root>:high_council``, +2
    Persuasion this Reveal), Delivery Logistics' Persuasion
    (``<root>:persuasion``) or its Contract (the market, ``<root>:contract``)."""

    opened = _choice_frame_effect(state, action.actor)
    if opened is None:
        raise RuntimeError("Reveal choice frame has invalid context")
    card_id, effect = opened
    ability = reveal_choice_ability(effect)
    (line,) = (
        line
        for line in ability.sections
        if _EITHER_LINE_ACTIONS[line.rewards[0]] == action.action_id
    )
    player = action.actor
    source = f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
    owner = state.players[player]
    remaining = state.decision_stack[:-1]
    match line.rewards[0]:
        case GainResources(solari=solari):
            next_owner = replace(
                owner,
                resources=replace(
                    owner.resources, solari=owner.resources.solari + solari
                ),
            )
            event = GameEvent(
                event_id=f"{source}:solari",
                kind="reveal_solari_gained",
                payload=(("amount", solari), ("card_id", card_id), ("player", player)),
            )
        case TakeHighCouncilSeat():
            (price,) = line.costs
            assert isinstance(price, PayResources)
            if not _either_line_open(owner, line):
                raise RuntimeError("Corrinth City High Council choice is unavailable")
            next_owner = replace(
                owner,
                high_council=True,
                resources=replace(
                    owner.resources, solari=owner.resources.solari - price.solari
                ),
            )
            remaining = add_reveal_persuasion(remaining, 2)
            event = GameEvent(
                event_id=f"{source}:high_council",
                kind="high_council_acquired",
                payload=(
                    ("card_id", card_id),
                    ("player", player),
                    ("solari", price.solari),
                ),
            )
            # Arrakeen Scouts: the new seat lets the seat join a subcommittee
            # any time in the rest of this Reveal turn (OQ-076 alternative C,
            # user ruling 2026-09-30); no Agent took it, so Contingencies may
            # recall any other Agent (OQ-075). With every subcommittee taken
            # the offer is still armed and only its decline is offered (user
            # ruling 2026-09-30; unreachable with four players, OQ-076 (c)).
            state = queue_reveal_subcommittee_offer(
                state, player, source=f"{source}:high_council"
            )
        case RevealPersuasion(amount=amount):
            return RuleResult(
                state=replace(
                    state, decision_stack=add_reveal_persuasion(remaining, amount)
                ),
                events=(
                    GameEvent(
                        event_id=f"{source}:persuasion",
                        kind="reveal_persuasion_gained",
                        payload=(
                            ("amount", amount),
                            ("card_id", card_id),
                            ("player", player),
                        ),
                    ),
                ),
            )
        case TakeContract(count=count):
            from dune_imperium.rules.contracts import begin_contract_gain

            return begin_contract_gain(
                replace(state, decision_stack=remaining),
                player,
                count,
                source=f"{source}:contract",
            )
        case reward:
            raise TypeError(f"{reward!r} is not a printed -OR- line")
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(event,),
    )


def legal_reveal_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Spy choices for the current serial Reveal effect."""

    pending = pending_choice_rows(state, player, legal_reveal_spy_actions)
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    effect_value = context.get("reveal_choice_effect")
    if not isinstance(effect_value, str):
        return ()
    effect = _resolved_choice_effect(effect_value)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal Spy frame has invalid card ID")
    owner = state.players[player]
    icon = reveal_choice_ability(PersonalCardRevealChoiceEffect(effect_value))
    if spy_icon_choice(icon):
        # A Spy icon, or Undercover Asset's "-OR-": its record (composed A4e).
        recalled = context.get("reveal_spy_recalled") is True
        plain_spy = _spy_alternative(icon) is None
        strength_choice = (
            ()
            if recalled or plain_spy
            else (
                DomainAction(
                    action_id="gain_two_reveal_strength",
                    actor=player,
                ),
            )
        )
        if owner.spies_supply > 0:
            return (
                *strength_choice,
                *(
                    _sourced(
                        "place_reveal_spy", player, card_id, (("post_id", post_id),)
                    )
                    for post_id in empty_observation_post_ids(state)
                ),
            )
        # With an empty supply the Spy icon allows "you may first recall one
        # of your Spies for no effect" [Main pp. 11, 20]: the recall stays
        # optional, so the plain icon may pass without a placement (OQ-057
        # (14)). Once a Spy was recalled it is in the supply, and the
        # placement is mandatory again. "Spy -OR- 2 swords" keeps its printed
        # alternative instead.
        decline = (
            (_sourced("decline_reveal_spy_recall", player, card_id),)
            if plain_spy and not recalled
            else ()
        )
        return (
            *strength_choice,
            *decline,
            *(
                _sourced(
                    "recall_spy_for_reveal_placement",
                    player,
                    card_id,
                    (("post_id", post_id),),
                )
                for post_id in owner.spy_post_ids
            ),
        )
    ability = reveal_choice_ability(effect)
    if target_reward_choice(ability) and ability.sections[0].costs == (RecallSpy(),):
        # Spy Network, Arrakis Observer: recall arrows, no refusal (OQ-095
        # (7) addition); their record (composed A4d).
        return target_reward_rows(state, player, card_id, effect)
    occupied = frozenset(state.players[player].spy_post_ids)
    post_ids = tuple(
        post.post_id for post in OBSERVATION_POSTS if post.post_id in occupied
    )
    # In High Places' two recalls are an arrow cost, and "You do not have to
    # pay such a cost on a card" [Main p. 20] [FAQ p. 3]: no refusal; unused,
    # it lapses when the Reveal ends (OQ-095 (7) addition, user ruling
    # 2026-10-14).
    if (
        effect
        is PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION
    ):
        return tuple(
            DomainAction(
                action_id="recall_spies_for_reveal",
                actor=player,
                arguments=(
                    ("first_post_id", first_post_id),
                    ("second_post_id", second_post_id),
                ),
            )
            for index, first_post_id in enumerate(post_ids)
            for second_post_id in post_ids[index + 1 :]
        )
    return ()


def legal_reveal_influence_exchange_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional Influence cost-and-reward choices for a Reveal card.

    An arrow cost: no refusal is offered, and the choice lapses at
    ``finish_reveal`` when it is left unused (OQ-095 (7) addition).
    """

    pending = pending_choice_rows(
        state, player, legal_reveal_influence_exchange_actions
    )
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE.value
    ):
        return ()
    actions: list[DomainAction] = []
    owner = state.players[player]
    for lost_faction in Faction:
        if influence_amount(owner.influence, lost_faction) == 0:
            continue
        recipients = alliance_recipients_after_influence_loss(
            state,
            player,
            lost_faction,
        )
        recipient_options: tuple[int | None, ...] = (
            tuple(recipients) if len(recipients) > 1 else (None,)
        )
        for gained_faction in Faction:
            # Never a cube already at the top (OQ-060); the one just lowered
            # is below it again.
            if gained_faction is not lost_faction and not influence_can_rise(
                owner, gained_faction
            ):
                continue
            for recipient in recipient_options:
                arguments: tuple[tuple[str, ActionValue], ...] = (
                    ("gained_faction", gained_faction.value),
                    ("lost_faction", lost_faction.value),
                )
                if recipient is not None:
                    arguments = (
                        ("alliance_recipient", recipient),
                        *arguments,
                    )
                actions.append(
                    DomainAction(
                        action_id="exchange_reveal_influence",
                        actor=player,
                        arguments=arguments,
                    )
                )
    return tuple(actions)


# Persuasion generated in this Reveal turn, which only gains raise; the
# frame's "persuasion" is what is left to spend after acquisitions.
GENERATED_PERSUASION_KEY = "persuasion_generated"

# The Commander share of ``reveal_units_deployed`` (absent means none): the
# Combat-icon deployment keeps its recruited slots per kind (OQ-070).
REVEAL_COMMANDERS_DEPLOYED_KEY = "reveal_commanders_deployed"


def _reveal_commanders_deployed(context: Mapping[str, ActionValue]) -> int:
    value = context.get(REVEAL_COMMANDERS_DEPLOYED_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("Reveal frame has an invalid Commander deployment count")
    return value


def _generated_persuasion(context: Mapping[str, ActionValue]) -> int | None:
    """Return the Persuasion a Reveal frame's turn has generated so far.

    "Command (6+)" is judged on the Persuasion the Reveal turn generates
    [Bloodlines pp. 5, 12], so Persuasion already spent on acquisitions
    still counts. A frame built without the counter falls back to its
    spendable total.
    """

    value = context.get(GENERATED_PERSUASION_KEY, context.get("persuasion"))
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("Reveal frame has invalid generated Persuasion")
    return value


def _frame_generated_persuasion(frames: tuple[DecisionFrame, ...]) -> int | None:
    """Return the open Reveal frame's generated Persuasion, if a Reveal is open."""

    for frame in reversed(frames):
        if frame.kind == FrameKind.REVEAL:
            return _generated_persuasion(dict(frame.context))
    return None


def legal_reveal_persuasion_or_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Delivery Logistics: "1 Persuasion OR a contract"."""

    pending = pending_choice_rows(
        state, player, legal_reveal_persuasion_or_contract_actions
    )
    if pending is not None:
        return pending
    opened = _choice_frame_effect(state, player)
    if (
        opened is None
        or opened[1] is not PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT
    ):
        return ()
    # Its record's lines (composed A4f).
    return either_rows(state, player, opened[1])


def apply_reveal_persuasion_or_contract(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Add one Persuasion to the Reveal, or open the Contract market."""

    state = _open_pending(state, action, legal_reveal_persuasion_or_contract_actions)
    if action not in legal_reveal_persuasion_or_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Persuasion-or-Contract choice")
    return resolve_either(state, action)


def legal_reveal_influence_gain_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the Faction choices of a "gain 1 Influence of your choice" Reveal."""

    pending = pending_choice_rows(state, player, legal_reveal_influence_gain_actions)
    if pending is not None:
        return pending
    opened = _choice_frame_effect(state, player)
    if opened is None or opened[1] not in (
        PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE,
        PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH,
    ):
        return ()
    # Pointing the Way, Ixian Ambassador: never a cube already at the top
    # (OQ-060); their record (composed A4d).
    return target_reward_rows(state, player, *opened)


def apply_reveal_influence_gain(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain one Influence with the chosen Faction (Pointing the Way's Command)."""

    state = _open_pending(state, action, legal_reveal_influence_gain_actions)
    if action not in legal_reveal_influence_gain_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Influence choice")
    return resolve_target_reward(state, action)


def legal_reveal_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the Combat-icon deployment during the owner's Reveal turn.

    "You may deploy any units you recruit this turn and up to two more from
    your garrison", never more than two from the garrison however many
    icons [Bloodlines p. 5]; a Sardaukar Commander is a "troop"
    [Bloodlines p. 4]. The garrison two are shared by troops and
    Commanders, but each unit recruited this turn keeps its slot for its
    own kind: a recruited Commander's slot is a Commander's (user ruling
    OQ-070, ``combat_deployment.deployment_rooms``).
    """

    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    if context.get("combat_deployment") is not True:
        return ()
    recruited = context_int(context, "reveal_troops_recruited", owner="Reveal frame")
    deployed = context_int(context, "reveal_units_deployed", owner="Reveal frame")
    commanders_deployed = _reveal_commanders_deployed(context)
    troop_room, commander_room = deployment_rooms(
        troops_recruited=recruited,
        commanders_recruited=recruited_commander_count(
            context, REVEAL_COMMANDERS_RECRUITED_KEY
        ),
        existing_limit=2,
        troops_deployed=max(0, deployed - commanders_deployed),
        commanders_deployed=commanders_deployed,
    )
    owner = state.players[player]
    actions: list[DomainAction] = []
    for action_id, garrison, room in (
        # Harkonnen Advisor's troop stays undeployable (OQ-038, OQ-062).
        (
            "deploy_troops",
            max(0, owner.troops_garrison - undeployable_troops(context)),
            troop_room,
        ),
        ("deploy_commanders", owner.commanders_garrison, commander_room),
    ):
        actions.extend(
            DomainAction(
                action_id=action_id, actor=player, arguments=(("count", count),)
            )
            for count in range(1, min(garrison, room) + 1)
        )
    return tuple(actions)


def apply_reveal_deployment(state: GameState, action: DomainAction) -> RuleResult:
    """Deploy garrison units during the Reveal turn (Combat icon)."""

    if action not in legal_reveal_deployments(state, action.actor):
        raise ValueError("action is not a legal Reveal deployment")
    count = dict(action.arguments)["count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise RuntimeError("Reveal deployment has an invalid count")
    commanders = count if action.action_id == "deploy_commanders" else 0
    troops = count - commanders
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["reveal_units_deployed"] = (
        context_int(context, "reveal_units_deployed", owner="Reveal frame") + count
    )
    if commanders:
        # The Commander share of the deployment, kept apart so the
        # recruited slots stay per kind (OQ-070).
        context[REVEAL_COMMANDERS_DEPLOYED_KEY] = (
            _reveal_commanders_deployed(context) + commanders
        )
    prepared = replace_top_frame(state, with_context(frame, context))
    counted = add_units_to_reveal(
        prepared, action.actor, troops=troops, commanders=commanders
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:reveal_deploy:"
            f"{context['reveal_units_deployed']}"
        ),
        kind="commanders_deployed" if commanders else "troops_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=counted.state, events=(event, *counted.events))


def legal_reveal_spice_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional three-Spice payments for Reveal Influence.

    An arrow cost: no refusal is offered (OQ-095 (7) addition).
    """

    pending = pending_choice_rows(state, player, legal_reveal_spice_influence_actions)
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE.value
    ):
        return ()
    owner = state.players[player]
    if owner.resources.spice < 3:
        return ()
    # Three spice for Influence no cube can take is not offered (OQ-060,
    # OQ-071).
    return tuple(
        DomainAction(
            action_id="pay_reveal_spice_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
        if influence_can_rise(owner, faction)
    )


def legal_reveal_sandworm_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Desert Power's mutually exclusive Reveal choices."""

    pending = pending_choice_rows(state, player, legal_reveal_sandworm_actions)
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM.value
    ):
        return ()
    actions: list[DomainAction] = [
        DomainAction(action_id="decline_reveal_sandworm", actor=player),
    ]
    if reveal_sandworm_block(state, player) is None:
        actions.append(
            DomainAction(
                action_id="pay_reveal_water_for_sandworm",
                actor=player,
            )
        )
    return tuple(actions)


def apply_reveal_sandworm_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Desert Power's Persuasion-or-sandworm Reveal choice."""

    state = _open_pending(state, action, legal_reveal_sandworm_actions)
    if action not in legal_reveal_sandworm_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal sandworm choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal sandworm frame has invalid card ID")
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"
    if action.action_id == "decline_reveal_sandworm":
        # "[2 Persuasion] -OR- [water] -> [sandworm]" [Desert Power card]
        # [Main pp. 10, 20]: choosing the Persuasion branch is what gains the
        # 2 Persuasion, so Command (6+) and every other total only count them
        # from here (user ruling 2026-09-26), for a seat without Maker Hooks
        # too (option (B), user ruling 2026-09-30).
        remaining = add_reveal_persuasion(state.decision_stack[:-1], 2)
        return RuleResult(
            state=replace(state, decision_stack=remaining),
            events=(
                GameEvent(
                    event_id=f"{source}:sandworm_declined",
                    kind="reveal_sandworm_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
                GameEvent(
                    event_id=f"{source}:persuasion",
                    kind="reveal_persuasion_gained",
                    payload=(
                        ("amount", 2),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )

    if reveal_sandworm_block(state, action.actor) is not None:
        raise RuntimeError("Desert Power sandworm choice is unavailable")
    owner = state.players[action.actor]
    if replaces_sandworms(owner):
        # Arrakis Planetologist: the water still buys the choice, the
        # sandworm becomes its replacement [Liet Kynes card].
        paid = replace(
            owner, resources=replace(owner.resources, water=owner.resources.water - 1)
        )
        popped = replace(
            state,
            players=replace_player(state.players, paid),
            decision_stack=state.decision_stack[:-1],
        )
        return replace_sandworms(popped, action.actor, 1, source=source)
    previous_units = owner.units_in_conflict
    reveal_context = _reveal_frame_context(state.decision_stack[:-1])
    current_strength = reveal_context.get("strength")
    sword_strength = reveal_context.get("sword_strength", 0)
    optional_sword_strength = reveal_context.get("optional_sword_strength", 0)
    if (
        isinstance(current_strength, bool)
        or not isinstance(current_strength, int)
        or isinstance(sword_strength, bool)
        or not isinstance(sword_strength, int)
        or isinstance(optional_sword_strength, bool)
        or not isinstance(optional_sword_strength, int)
    ):
        raise RuntimeError("Reveal sandworm frame has invalid strength")
    strength_delta = (
        3
        if previous_units
        else 3 + sword_strength + optional_sword_strength - current_strength
    )
    next_owner = replace(
        owner,
        resources=replace(owner.resources, water=owner.resources.water - 1),
        sandworms_conflict=owner.sandworms_conflict + 1,
        combat_strength=owner.combat_strength + strength_delta,
        units_deployed_turn=owner.units_deployed_turn + 1,
    )
    remaining = add_reveal_strength(state.decision_stack[:-1], strength_delta)
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(
            GameEvent(
                event_id=f"{source}:sandworm",
                kind="reveal_sandworm_deployed",
                payload=(
                    ("amount", 1),
                    ("card_id", card_id),
                    ("player", action.actor),
                    ("water", 1),
                ),
            ),
            GameEvent(
                event_id=f"{source}:strength",
                kind="reveal_strength_gained",
                payload=(
                    ("amount", strength_delta),
                    ("card_id", card_id),
                    ("player", action.actor),
                ),
            ),
        ),
    )


def legal_reveal_card_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the optional trash choices of the current Reveal card.

    Calculus of Power's other Emperor card, Shrouded Counsel's Command
    trash, Disruption Tactics' and CHOAM Demands' self-trash: arrows or a
    black trash icon, so no refusal is offered (OQ-095 (7) addition), and
    ``source`` names the card whose choice the trash pays.
    """

    pending = pending_choice_rows(state, player, legal_reveal_card_trash_actions)
    if pending is not None:
        return pending
    opened = _choice_frame_effect(state, player)
    if opened is None or opened[1] not in (
        PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH,
        PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS,
    ):
        return ()
    # Their records (composed A4d).
    return target_reward_rows(state, player, *opened)


def legal_reveal_troop_retreat_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the optional two-troop Reveal retreat payment.

    Chani's and Command Center's arrow: no refusal is offered (OQ-095 (7)
    addition), and ``source`` names the card the retreat pays for.
    """

    pending = pending_choice_rows(state, player, legal_reveal_troop_retreat_actions)
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("reveal_choice_effect") not in (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH.value,
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION.value,
    ):
        return ()
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal troop-retreat frame has invalid card ID")
    owner = state.players[player]
    # Sardaukar Commanders are troops for the retreat [Bloodlines p. 4];
    # ``commanders`` names their share of the two.
    return tuple(
        _sourced(
            "retreat_two_troops_for_reveal",
            player,
            card_id,
            () if commanders == 0 else (("commanders", commanders),),
        )
        for commanders in range(3)
        if owner.troops_conflict >= 2 - commanders
        and owner.commanders_conflict >= commanders
    )


def legal_corrinth_city_reveal_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Corrinth City's mutually exclusive Reveal choices."""

    pending = pending_choice_rows(state, player, legal_corrinth_city_reveal_actions)
    if pending is not None:
        return pending
    opened = _choice_frame_effect(state, player)
    if (
        opened is None
        or opened[1]
        is not PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL
    ):
        return ()
    # Its record's lines (composed A4f).
    return either_rows(state, player, opened[1])


def apply_corrinth_city_reveal(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain five Solari or pay five for a High Council seat."""

    state = _open_pending(state, action, legal_corrinth_city_reveal_actions)
    if action not in legal_corrinth_city_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Corrinth City Reveal choice")
    return resolve_either(state, action)


def legal_contract_reveal_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the CHOAM choice between Spice and a self-trash VP.

    ``source`` names the card: Priority Contracts' spice is 2, Delivery
    Agreement's 1.
    """

    pending = pending_choice_rows(state, player, legal_contract_reveal_choice_actions)
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or context.get("reveal_choice_effect")
        != (
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS.value
        )
    ):
        return ()
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Contract-count Reveal choice has invalid card ID")
    actions = [_sourced("keep_contract_reveal_spice", player, card_id)]
    # The self-trash is the cost of the Victory Point, so it is adjudicated
    # at resolution time [Main pp. 9, 20]: a card another effect already
    # trashed while this choice was pending can no longer pay it.
    if (
        len(state.players[player].completed_contract_ids) >= 4
        and card_id in state.players[player].in_play
    ):
        actions.append(_sourced("trash_contract_reveal_for_vp", player, card_id))
    return tuple(actions)


def apply_contract_reveal_choice(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain printed Spice or trash the card for one VP."""

    state = _open_pending(state, action, legal_contract_reveal_choice_actions)
    if action not in legal_contract_reveal_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Contract-count Reveal choice")
    context = dict(state.decision_stack[-1].context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Contract-count Reveal choice has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}:contract_count_choice"
    )
    if action.action_id == "keep_contract_reveal_spice":
        card = personal_card_for_instance(card_id)
        spice = sum(effect.spice for effect in card.reveal_effects)
        owner = state.players[action.actor]
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + spice,
            ),
        )
        return RuleResult(
            state=replace(
                state.pop_decision(),
                players=replace_player(state.players, next_owner),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:spice",
                    kind="contract_reveal_spice_gained",
                    payload=(
                        ("amount", spice),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )

    prepared = state.pop_decision()
    trashed = trash_personal_card(
        prepared,
        action.actor,
        card_id,
        source=source,
    )
    # A trashed card's own troop-on-trash trigger (Eliminate Allies) is not
    # credited by ``trash_personal_card`` here: the frame on top is this
    # Reveal choice's own, not an AGENT_EFFECTS frame. A troop recruited
    # during the owner's own turn "from any source" may be deployed
    # [Main p. 10] [FAQ p. 4]; the Reveal's Combat icon deploys it
    # [Bloodlines pp. 5, 12].
    trashed = credit_trash_recruits(trashed, action.actor)
    owner = trashed.state.players[action.actor]
    next_owner = replace(owner, victory_points=owner.victory_points + 1)
    next_state = replace(
        trashed.state,
        players=replace_player(trashed.state.players, next_owner),
    )
    event = GameEvent(
        event_id=f"{source}:victory_point",
        kind="contract_reveal_card_trashed_for_vp",
        payload=(
            ("card_id", card_id),
            ("player", action.actor),
            ("victory_points", 1),
        ),
    )
    return RuleResult(state=next_state, events=(*trashed.events, event))


def apply_reveal_troop_retreat(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Retreat two troops for four swords or two Persuasion."""

    state = _open_pending(state, action, legal_reveal_troop_retreat_actions)
    if action not in legal_reveal_troop_retreat_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal troop-retreat choice")
    context = dict(state.decision_stack[-1].context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal troop-retreat frame has invalid card ID")
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"
    owner = state.players[action.actor]
    commanders = dict(action.arguments).get("commanders", 0)
    if isinstance(commanders, bool) or not isinstance(commanders, int):
        raise RuntimeError("Reveal troop-retreat has an invalid Commander count")
    troops = 2 - commanders
    if owner.troops_conflict < troops or owner.commanders_conflict < commanders:
        raise RuntimeError("Reveal troop-retreat payment requires two troops")
    remaining_units = owner.units_in_conflict - 2
    persuasion_choice = context.get("reveal_choice_effect") == (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION.value
    )
    if not remaining_units:
        # No unit left, no strength, swords or not [Main p. 12].
        next_strength = 0
    elif persuasion_choice:
        # Command Center pays Persuasion, not swords: each retreated troop or
        # Commander takes its 2 strength along [Main pp. 12, 14]
        # [Bloodlines p. 4].
        next_strength = max(owner.combat_strength - 2 * 2, 0)
    else:
        # Chani, Clever Tactician: the 4 troop strength becomes 4 swords.
        next_strength = owner.combat_strength
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison + troops,
        troops_conflict=owner.troops_conflict - troops,
        commanders_garrison=owner.commanders_garrison + commanders,
        commanders_conflict=owner.commanders_conflict - commanders,
        combat_strength=next_strength,
    )
    # Tactician: "Whenever you retreat or lose any number of troops from the
    # Conflict, advance your Tactics token that many spaces" [Chani card];
    # Commanders are troops [Bloodlines p. 4], and this one source moves the
    # token once [FAQ p. 1].
    next_owner, tactics_events = advance_tactics_token(next_owner, 2, source=source)
    remaining = state.decision_stack[:-1]
    strength_delta = next_strength - owner.combat_strength
    if strength_delta:
        remaining = add_reveal_strength(remaining, strength_delta)
    if persuasion_choice:
        # Command Center (Bloodlines): "Retreat two troops -> +2 Persuasion".
        remaining = add_reveal_persuasion(remaining, 2)
        reward_event = GameEvent(
            event_id=f"{source}:persuasion",
            kind="reveal_persuasion_gained",
            payload=(("amount", 2), ("card_id", card_id), ("player", action.actor)),
        )
    else:
        remaining = add_reveal_optional_sword_strength(remaining, 4, card_id=card_id)
        reward_event = GameEvent(
            event_id=f"{source}:strength",
            kind="reveal_strength_gained",
            payload=(("amount", 4), ("card_id", card_id), ("player", action.actor)),
        )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(
            GameEvent(
                event_id=f"{source}:troops_retreated",
                kind="troops_retreated",
                payload=(("count", 2), ("player", action.actor)),
            ),
            *tactics_events,
            reward_event,
        ),
    )


_FREMEN_BOND_TROOP_MOVE = (
    PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND
)
# Choices whose actions are exactly another choice's: each of Covert
# Operation's two Spy icons is the plain Reveal Spy icon, and Unswerving
# Loyalty's Fremen Bond line is Shadout Mapes' troop move. Only when (and how
# often) the choice opens differs.
_RESOLVES_AS: Mapping[
    PersonalCardRevealChoiceEffect, PersonalCardRevealChoiceEffect
] = {
    PersonalCardRevealChoiceEffect.PLACE_TWO_SPIES: (
        PersonalCardRevealChoiceEffect.PLACE_SPY
    ),
    _FREMEN_BOND_TROOP_MOVE: (
        PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP
    ),
}


def _resolved_choice_effect(effect_value: str) -> PersonalCardRevealChoiceEffect:
    """Return the choice whose actions resolve the frame's ``effect_value``."""

    effect = PersonalCardRevealChoiceEffect(effect_value)
    return _RESOLVES_AS.get(effect, effect)


def _reveal_choice_frame_context(
    state: GameState,
    player: int,
    effect: PersonalCardRevealChoiceEffect,
) -> dict[str, ActionValue] | None:
    """Return the top REVEAL_CHOICE context if it resolves as ``player``'s ``effect``.

    ``_RESOLVES_AS`` lets a choice share another choice's actions.
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    context = dict(frame.context)
    effect_value = context.get("reveal_choice_effect")
    if not isinstance(effect_value, str):
        return None
    if _resolved_choice_effect(effect_value) is not effect:
        return None
    return context


def _reveal_choice_card_source(
    state: GameState,
    player: int,
    context: dict[str, ActionValue],
    suffix: str,
) -> tuple[str, str]:
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal choice frame has invalid card ID")
    return (
        card_id,
        f"round:{state.round_number}:player:{player}:reveal_card:{card_id}:{suffix}",
    )


# For Humanity's arrow cost: a "?" Influence diamond with two red chevrons,
# two Influence with one chosen Faction [For Humanity card]; like gaining two,
# the two steps cannot be split between Factions [Main p. 20].
_FOR_HUMANITY_INFLUENCE_COST = 2


def _stepwise_alliance_recipients(
    state: GameState,
    player: int,
    faction: Faction,
    steps: int,
) -> tuple[int, ...]:
    """Return the Alliance recipients to pick from while losing ``steps``.

    The steps are lost one space at a time [FAQ p. 1]; only the holder can
    lose the token, so at most one step can move it, and the choice (if any)
    belongs to that step.
    """

    working = state
    for step in range(steps):
        recipients = alliance_recipients_after_influence_loss(working, player, faction)
        if len(recipients) > 1:
            return recipients
        working = lose_faction_influence(
            working, player, faction, 1, event_prefix=f"probe:{step}"
        ).state
    return ()


def _lose_influence_stepwise(
    state: GameState,
    player: int,
    faction: Faction,
    steps: int,
    *,
    event_prefix: str,
    alliance_recipient: int | None,
) -> RuleResult:
    """Lose ``steps`` Influence one space at a time [FAQ p. 1].

    ``alliance_recipient`` is the owner's pick for the one step whose
    Alliance token has several possible recipients.
    """

    working = state
    events: list[GameEvent] = []
    for step in range(steps):
        recipients = alliance_recipients_after_influence_loss(working, player, faction)
        lost = lose_faction_influence(
            working,
            player,
            faction,
            1,
            event_prefix=f"{event_prefix}:{step}",
            alliance_recipient=alliance_recipient if len(recipients) > 1 else None,
        )
        working = lost.state
        events.extend(lost.events)
    return RuleResult(state=working, events=tuple(events))


def legal_reveal_influence_loss_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """For Humanity: "Bene Gesserit Alliance: lose two Influence -> 1 VP".

    The arrow cost is paid in full or not at all [Main p. 20], so only a
    Faction with two or more Influence can pay it; it offers no refusal
    (OQ-095 (7) addition).
    """

    pending = pending_choice_rows(state, player, legal_reveal_influence_loss_actions)
    if pending is not None:
        return pending
    context = _reveal_choice_frame_context(state, player, _LOSE_INFLUENCE_FOR_VP)
    if context is None:
        return ()
    actions: list[DomainAction] = []
    owner = state.players[player]
    for faction in Faction:
        if influence_amount(owner.influence, faction) < _FOR_HUMANITY_INFLUENCE_COST:
            continue
        recipients = _stepwise_alliance_recipients(
            state, player, faction, _FOR_HUMANITY_INFLUENCE_COST
        )
        recipient_options: tuple[int | None, ...] = (
            tuple(recipients) if len(recipients) > 1 else (None,)
        )
        for recipient in recipient_options:
            arguments: tuple[tuple[str, ActionValue], ...] = (
                ("faction", faction.value),
            )
            if recipient is not None:
                arguments = (("alliance_recipient", recipient), *arguments)
            actions.append(
                DomainAction(
                    action_id="lose_reveal_influence_for_vp",
                    actor=player,
                    arguments=arguments,
                )
            )
    return tuple(actions)


def apply_reveal_influence_loss(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Lose two Influence with one Faction for a Victory Point."""

    state = _open_pending(state, action, legal_reveal_influence_loss_actions)
    if action not in legal_reveal_influence_loss_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Influence loss")
    context = dict(state.decision_stack[-1].context)
    card_id, source = _reveal_choice_card_source(
        state, action.actor, context, "influence_loss"
    )
    popped = state.pop_decision()
    arguments = dict(action.arguments)
    faction_value = arguments.get("faction")
    recipient = arguments.get("alliance_recipient")
    if not isinstance(faction_value, str):
        raise RuntimeError("Reveal Influence loss has invalid Faction")
    if recipient is not None and (
        isinstance(recipient, bool) or not isinstance(recipient, int)
    ):
        raise RuntimeError("Reveal Influence loss has invalid recipient")
    lost = _lose_influence_stepwise(
        popped,
        action.actor,
        Faction(faction_value),
        _FOR_HUMANITY_INFLUENCE_COST,
        event_prefix=f"{source}:lost:{faction_value}",
        alliance_recipient=recipient,
    )
    owner = lost.state.players[action.actor]
    next_owner = replace(owner, victory_points=owner.victory_points + 1)
    return RuleResult(
        state=replace(
            lost.state, players=replace_player(lost.state.players, next_owner)
        ),
        events=(
            *lost.events,
            GameEvent(
                event_id=f"{source}:victory_point",
                kind="reveal_victory_point_gained",
                payload=(
                    ("card_id", card_id),
                    ("player", action.actor),
                    ("victory_points", 1),
                ),
            ),
        ),
    )


def legal_reveal_troop_move_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Shadout Mapes: "You may deploy or retreat one of your troops".

    A Sardaukar Commander "is a 'troop' that's worth 2 strength in the
    Conflict" [Bloodlines p. 4], so a garrison or Conflict Commander is a
    legal unit too; ``commanders`` 1 names it, as the other troop retreats do.
    "May": no refusal is offered (OQ-095 (7) addition).
    """

    pending = pending_choice_rows(state, player, legal_reveal_troop_move_actions)
    if pending is not None:
        return pending
    context = _reveal_choice_frame_context(
        state, player, PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP
    )
    if context is None:
        return ()
    card_id, _ = _reveal_choice_card_source(state, player, context, "troop_move")
    owner = state.players[player]
    return tuple(
        _sourced(
            action_id,
            player,
            card_id,
            (("commanders", 1),) if commander else (),
        )
        for action_id, troops, commanders in (
            (
                "deploy_reveal_card_troop",
                owner.troops_garrison,
                owner.commanders_garrison,
            ),
            (
                "retreat_reveal_card_troop",
                owner.troops_conflict,
                owner.commanders_conflict,
            ),
        )
        for commander, available in ((False, troops), (True, commanders))
        if available >= 1
    )


def apply_reveal_troop_move(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Deploy one garrison unit, or retreat one Conflict unit."""

    state = _open_pending(state, action, legal_reveal_troop_move_actions)
    if action not in legal_reveal_troop_move_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal troop move")
    context = dict(state.decision_stack[-1].context)
    _, source = _reveal_choice_card_source(state, action.actor, context, "troop_move")
    popped = state.pop_decision()
    commanders = 1 if dict(action.arguments).get("commanders") == 1 else 0
    if action.action_id == "deploy_reveal_card_troop":
        counted = add_units_to_reveal(
            popped, action.actor, troops=1 - commanders, commanders=commanders
        )
        return RuleResult(
            state=counted.state,
            events=(
                GameEvent(
                    event_id=f"{source}:deployed",
                    kind="commanders_deployed" if commanders else "troops_deployed",
                    payload=(("count", 1), ("player", action.actor)),
                ),
                *counted.events,
            ),
        )
    before = popped.players[action.actor].combat_strength
    retreated = retreat_units(
        popped, action.actor, source, troops=1 - commanders, commanders=commanders
    )
    delta = retreated.state.players[action.actor].combat_strength - before
    # A retreated unit no longer counts among the turn's deployed units, as
    # on an Agent turn: "deploy, retreat, and deploy that troop again" does
    # not reach three (Message from designer; OQ-016).
    next_state = reconcile_deployment_after_retreat(
        retreated.state, action.actor, troops=1 - commanders, commanders=commanders
    )
    if delta:
        next_state = replace(
            next_state,
            decision_stack=add_reveal_strength(next_state.decision_stack, delta),
        )
    return RuleResult(state=next_state, events=retreated.events)


def legal_reveal_troop_sacrifice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Tleilaxu Surgeon: "Lose two troops -> two specimens" (OQ-053).

    The owner picks the zone of each troop: both from the garrison, both
    from the Conflict, or one from each. An arrow cost: no refusal is
    offered (OQ-095 (7) addition).
    """

    pending = pending_choice_rows(state, player, legal_reveal_troop_sacrifice_actions)
    if pending is not None:
        return pending
    context = _reveal_choice_frame_context(state, player, _LOSE_TROOPS_FOR_SPECIMENS)
    if context is None:
        return ()
    owner = state.players[player]
    return tuple(
        DomainAction(
            action_id="lose_reveal_troops_for_specimens",
            actor=player,
            arguments=(("zones", zones),),
        )
        for zones, garrison, conflict in SURGEON_ZONE_PAIRS
        if owner.troops_garrison >= garrison and owner.troops_conflict >= conflict
    )


def apply_reveal_troop_sacrifice(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Return two troops of one zone to the supply for two specimens."""

    state = _open_pending(state, action, legal_reveal_troop_sacrifice_actions)
    if action not in legal_reveal_troop_sacrifice_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal troop sacrifice")
    context = dict(state.decision_stack[-1].context)
    _, source = _reveal_choice_card_source(
        state, action.actor, context, "troop_sacrifice"
    )
    popped = state.pop_decision()
    zones = str(dict(action.arguments)["zones"]).split(",")
    before = popped.players[action.actor].combat_strength
    working = popped
    events: list[GameEvent] = []
    for index, zone in enumerate(zones):
        lost = lose_unit(
            working,
            action.actor,
            zone,
            source=f"{source}:{index}",
            advance_tactics=False,
        )
        working = lost.state
        events.extend(lost.events)
    # Tactician: "Each different source of retreating or losing troops is
    # handled separately" [FAQ p. 1], so the two troops advance the token
    # once, and a pass past the end still only resets it [Bloodlines p. 12].
    tactician, tactics_events = advance_tactics_token(
        working.players[action.actor], zones.count("conflict"), source=source
    )
    working = replace(working, players=replace_player(working.players, tactician))
    if zones.count("conflict"):
        # Troops lost from the Conflict leave the turn's deployed count, as a
        # retreat does (OQ-016).
        working = reconcile_deployment_after_retreat(
            working, action.actor, troops=zones.count("conflict")
        )
    events.extend(tactics_events)
    delta = working.players[action.actor].combat_strength - before
    if delta:
        working = replace(
            working, decision_stack=add_reveal_strength(working.decision_stack, delta)
        )
    generated = generate_specimens(working, action.actor, 2, source=source)
    return RuleResult(state=generated.state, events=(*events, *generated.events))


def apply_reveal_card_trash(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Trash the chosen card for the Reveal card's reward.

    Calculus of Power's three swords, Shrouded Counsel's trash alone,
    Disruption Tactics' Combat icon or CHOAM Demands' four Influence.
    """

    state = _open_pending(state, action, legal_reveal_card_trash_actions)
    if action not in legal_reveal_card_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal card trash choice")
    return resolve_target_reward(state, action)


def apply_reveal_spice_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Pay three Spice and gain one chosen Faction Influence."""

    state = _open_pending(state, action, legal_reveal_spice_influence_actions)
    if action not in legal_reveal_spice_influence_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Spice payment")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal Spice-payment frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}:spice_influence"
    )
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Reveal Spice payment has invalid Faction")
    owner = state.players[action.actor]
    if owner.resources.spice < 3:
        raise RuntimeError("Reveal Influence payment requires three Spice")
    owner = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice - 3),
        spice_spent_turn=owner.spice_spent_turn + 3,
    )
    paid = replace(state, players=replace_player(state.players, owner))
    gained = gain_faction_influence(
        paid,
        action.actor,
        Faction(faction_value),
        1,
        event_prefix=f"{source}:gained:{faction_value}",
    )
    payment_event = GameEvent(
        event_id=f"{source}:paid",
        kind="reveal_spice_paid",
        payload=(
            ("amount", 3),
            ("card_id", card_id),
            ("player", action.actor),
        ),
    )
    return RuleResult(
        state=replace(
            gained.state,
            decision_stack=gained.state.decision_stack[:-1],
        ),
        events=(payment_event, *gained.events),
    )


def apply_reveal_influence_exchange(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Atomically pay and resolve a Reveal Influence exchange."""

    state = _open_pending(state, action, legal_reveal_influence_exchange_actions)
    if action not in legal_reveal_influence_exchange_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Influence exchange")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal Influence frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}:influence_exchange"
    )
    arguments = dict(action.arguments)
    lost_value = arguments.get("lost_faction")
    gained_value = arguments.get("gained_faction")
    recipient = arguments.get("alliance_recipient")
    if not isinstance(lost_value, str) or not isinstance(gained_value, str):
        raise RuntimeError("Reveal Influence exchange has invalid Factions")
    if recipient is not None and (
        isinstance(recipient, bool) or not isinstance(recipient, int)
    ):
        raise RuntimeError("Reveal Influence exchange has invalid recipient")
    lost = lose_faction_influence(
        state,
        action.actor,
        Faction(lost_value),
        1,
        event_prefix=f"{source}:lost:{lost_value}",
        alliance_recipient=recipient,
    )
    gained = gain_faction_influence(
        lost.state,
        action.actor,
        Faction(gained_value),
        1,
        event_prefix=f"{source}:gained:{gained_value}",
    )
    return RuleResult(
        state=replace(
            gained.state,
            decision_stack=gained.state.decision_stack[:-1],
        ),
        events=(*lost.events, *gained.events),
    )


def apply_reveal_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve the current Reveal effect's Spy placement or recall choice."""

    state = _open_pending(state, action, legal_reveal_spy_actions)
    if action not in legal_reveal_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Spy choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    effect_value = context.get("reveal_choice_effect")
    if not isinstance(card_id, str) or not isinstance(effect_value, str):
        raise RuntimeError("Reveal Spy frame has invalid context")
    effect = PersonalCardRevealChoiceEffect(effect_value)
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"

    arguments = dict(action.arguments)
    if action.action_id == "gain_two_reveal_strength":
        # Undercover Asset's "+2 swords" line, counted only with a unit in
        # the Conflict: its record (composed A4e).
        alternative = _spy_alternative(reveal_choice_ability(effect))
        if alternative is None:
            raise RuntimeError("Reveal Spy choice has no swords line")
        amount = alternative.amount
        owner = state.players[action.actor]
        counted_strength = amount if owner.units_in_conflict else 0
        next_owner = replace(
            owner,
            combat_strength=owner.combat_strength + counted_strength,
        )
        remaining = state.decision_stack[:-1]
        remaining = add_reveal_optional_sword_strength(
            remaining, amount, card_id=card_id
        )
        if counted_strength:
            remaining = add_reveal_strength(remaining, counted_strength)
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=remaining,
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:strength",
                    kind="reveal_strength_gained",
                    payload=(
                        ("amount", amount),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )
    if action.action_id == "recall_spy_for_reveal_placement":
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        next_owner = recall_spy(state.players[action.actor], post_id)
        context["reveal_spy_recalled"] = True
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(_spy_recalled_event(state, action.actor, card_id, post_id),),
        )

    if action.action_id == "place_reveal_spy":
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        next_owner = place_spy(state.players[action.actor], post_id)
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=_after_reveal_spy_icon(state, action.actor, effect),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_placed:{post_id}",
                    kind="spy_placed",
                    payload=(
                        ("card_id", card_id),
                        ("player", action.actor),
                        ("post_id", post_id),
                    ),
                ),
            ),
        )

    if action.action_id == "decline_reveal_spy_recall":
        return RuleResult(
            state=replace(
                state,
                decision_stack=_after_reveal_spy_icon(state, action.actor, effect),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_recall_declined",
                    kind="reveal_spy_recall_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )

    if action.action_id == "recall_spy_for_reveal":
        # Spy Network, Arrakis Observer: their records (composed A4d).
        return resolve_target_reward(state, action)
    # In High Places: "[recall Spy] [recall Spy] -> +3 Persuasion" [In High
    # Places card].
    first_post_id = arguments.get("first_post_id")
    second_post_id = arguments.get("second_post_id")
    if not isinstance(first_post_id, str) or not isinstance(second_post_id, str):
        raise RuntimeError("Reveal Spy choice has invalid post IDs")
    owner = state.players[action.actor]
    next_owner = recall_spy(recall_spy(owner, first_post_id), second_post_id)
    events = (
        _spy_recalled_event(state, action.actor, card_id, first_post_id),
        _spy_recalled_event(state, action.actor, card_id, second_post_id),
        GameEvent(
            event_id=f"{source}:persuasion",
            kind="reveal_persuasion_gained",
            payload=(
                ("amount", 3),
                ("card_id", card_id),
                ("player", action.actor),
            ),
        ),
    )
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=add_reveal_persuasion(state.decision_stack[:-1], 3),
    )
    return RuleResult(state=next_state, events=events)


def _after_reveal_spy_icon(
    state: GameState,
    player: int,
    effect: PersonalCardRevealChoiceEffect,
) -> tuple[DecisionFrame, ...]:
    """Close a resolved Reveal Spy frame; Covert Operation queues its second icon.

    Covert Operation prints two Spy icons [Covert Operation card]. Its frame
    resolves the first like any plain Spy icon [Main pp. 11, 20]; the second
    then waits as a plain ``PLACE_SPY`` entry of the same card on the Reveal
    frame's pending list, offered with the other Reveal choices in any
    order [Main p. 12] (OQ-095 (7) addition).
    """

    del player
    remaining = state.decision_stack[:-1]
    if _spy_icons(reveal_choice_ability(effect)) < 2:
        return remaining
    card_id = context_str(
        frame_context(state.decision_stack[-1]), "reveal_card_id", owner=_CHOICE_FRAME
    )
    return _queue_pending_choices(
        remaining, ((card_id, PersonalCardRevealChoiceEffect.PLACE_SPY.value),)
    )


def _spy_recalled_event(
    state: GameState,
    player: int,
    card_id: str,
    post_id: str,
) -> GameEvent:
    return GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:"
            f"reveal_card:{card_id}:spy_recalled:{post_id}"
        ),
        kind="spy_recalled",
        payload=(
            ("player", player),
            ("post_id", post_id),
            ("source", card_id),
        ),
    )


def add_reveal_persuasion(
    frames: tuple[DecisionFrame, ...],
    amount: int,
) -> tuple[DecisionFrame, ...]:
    """Add Persuasion to the Reveal frame below serial choice frames."""

    for index in range(len(frames) - 1, -1, -1):
        context = dict(frames[index].context)
        persuasion = context.get("persuasion")
        if persuasion is None:
            continue
        if isinstance(persuasion, bool) or not isinstance(persuasion, int):
            raise RuntimeError("Reveal frame has invalid Persuasion")
        generated = _generated_persuasion(context)
        context["persuasion"] = persuasion + amount
        if generated is not None:
            # Gains are generated Persuasion [Bloodlines p. 5]. Desert
            # Power's "2 Persuasion -OR- sandworm" waits out of both totals
            # until the owner picks the Persuasion branch (user ruling
            # 2026-09-26), so this is never called with a negative amount.
            # Acquisition costs do not come through here.
            context[GENERATED_PERSUASION_KEY] = generated + amount
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("Reveal Spy choice is missing its Reveal frame")


def add_reveal_strength(
    frames: tuple[DecisionFrame, ...],
    amount: int,
) -> tuple[DecisionFrame, ...]:
    """Add counted strength to the Reveal frame below serial choices."""

    for index in range(len(frames) - 1, -1, -1):
        context = dict(frames[index].context)
        strength = context.get("strength")
        if strength is None:
            continue
        if isinstance(strength, bool) or not isinstance(strength, int):
            raise RuntimeError("Reveal frame has invalid strength")
        context["strength"] = strength + amount
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("Reveal trash choice is missing its Reveal frame")


def add_reveal_optional_sword_strength(
    frames: tuple[DecisionFrame, ...],
    amount: int,
    *,
    card_id: str | None = None,
) -> tuple[DecisionFrame, ...]:
    """Record a chosen sword bonus even when no unit currently counts it.

    ``card_id`` names the revealed card whose Reveal choice provided the
    swords, so Leadership can count it as a card that "provides one or more
    [sword] this turn" [Leadership card].
    """

    for index in range(len(frames) - 1, -1, -1):
        context = dict(frames[index].context)
        if "strength" not in context or "persuasion" not in context:
            continue
        optional_strength = context.get("optional_sword_strength", 0)
        if isinstance(optional_strength, bool) or not isinstance(
            optional_strength, int
        ):
            raise RuntimeError("Reveal frame has invalid optional sword strength")
        context["optional_sword_strength"] = optional_strength + amount
        if card_id is not None and amount > 0:
            context[_CHOICE_SWORD_CARDS_KEY] = ",".join(
                dict.fromkeys((*_choice_sword_card_ids(context), card_id))
            )
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("Reveal choice is missing its Reveal frame")


class RevealSandwormBlock(StrEnum):
    """Why Desert Power's sandworm branch cannot be taken right now.

    "[2 Persuasion] -OR- [water] -> [sandworm]" [Desert Power card]
    [Main pp. 10, 20], with Maker Hooks needed to summon a sandworm
    [Main p. 20]. ``legal_reveal_sandworm_actions`` offers
    ``pay_reveal_water_for_sandworm`` exactly when ``reveal_sandworm_block``
    is None, and the page's greyed-out row reads the same block
    (``display.unavailable``), so the reason shown can never disagree with
    the legal list.
    """

    MAKER_HOOKS = "maker_hooks"  # the seat has no Maker Hooks
    WATER = "water"  # no Water to pay
    NO_CONFLICT = "no_conflict"  # no Conflict this round to deploy into
    SHIELD_WALL = "shield_wall"  # the Shield Wall protects this Conflict


def reveal_sandworm_block(state: GameState, player: int) -> RevealSandwormBlock | None:
    """Return why Desert Power cannot deploy its sandworm now, or None.

    Checked in this order: Maker Hooks, Water, a current Conflict, the
    Shield Wall. Arrakis Planetologist's replacement ignores the Shield Wall
    [Liet Kynes card]. Every input is public. The 2 Persuasion are not
    counted (and so cannot be "spent") before the owner picks a branch
    (user ruling 2026-09-26), so this only gates the sandworm branch's own
    requirements.
    """

    owner = state.players[player]
    if not owner.maker_hooks:
        return RevealSandwormBlock.MAKER_HOOKS
    if owner.resources.water < 1:
        return RevealSandwormBlock.WATER
    if not state.current_conflict_ids:
        return RevealSandwormBlock.NO_CONFLICT
    if not replaces_sandworms(owner) and current_conflict_is_shield_wall_protected(
        state
    ):
        return RevealSandwormBlock.SHIELD_WALL
    return None


def _desert_power_persuasion_pending(card: PersonalCardDefinition) -> bool:
    """Return whether a revealed card's Persuasion waits for a Reveal choice.

    "[2 Persuasion] -OR- [water] -> [sandworm]" [Desert Power card]
    [Main pp. 10, 20]: the 2 Persuasion are not generated -- and cannot
    fund Command (6+) -- until the owner picks the Persuasion branch
    (``decline_reveal_sandworm``) (user ruling 2026-09-26). This holds for
    every seat: one without Maker Hooks also gets the choice window, with
    only the Persuasion branch to pick (option (B), user ruling 2026-09-30:
    "REVEAL_CHOICE 창을 열어 '설득 2'만 고르게, 모래벌레 줄은 '메이커 작살
    없음' 회색").
    """

    return (
        PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
        in card.reveal_choice_effects
    )


def _card_reveal_persuasion(card: PersonalCardDefinition) -> int:
    """Return a revealed card's own Persuasion, deferring Desert Power's."""

    return 0 if _desert_power_persuasion_pending(card) else card.reveal_persuasion


def _reveal_frame_context(
    frames: tuple[DecisionFrame, ...],
) -> dict[str, ActionValue]:
    """Find the active Reveal frame below any serial choice frames."""

    for frame in reversed(frames):
        if frame.kind == FrameKind.REVEAL:
            return dict(frame.context)
    raise RuntimeError("Reveal choice is missing its Reveal frame")


def _update_reveal_frame(
    frames: tuple[DecisionFrame, ...],
    updates: dict[str, ActionValue],
) -> tuple[DecisionFrame, ...]:
    """Write ``updates`` into the Reveal frame below any serial choice frames."""

    for index in range(len(frames) - 1, -1, -1):
        if frames[index].kind == FrameKind.REVEAL:
            context = dict(frames[index].context)
            context.update(updates)
            return (
                *frames[:index],
                replace(frames[index], context=tuple(sorted(context.items()))),
                *frames[index + 1 :],
            )
    raise RuntimeError("Reveal update is missing its Reveal frame")


SPICE_MUST_FLOW_ACQUIRED_KEY = "spice_must_flow_acquired"
GUILD_SPY_FIRED_KEY = "guild_spy_fired"
_GUILD_SPY_EFFECT = (
    PersonalCardRevealAcquisitionEffect.GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
)


def fire_guild_spy_on_spice_must_flow(
    state: GameState,
    player: int,
    *,
    acquired: bool,
) -> RuleResult:
    """Guild Spy's Reveal box on The Spice Must Flow, once per copy per Reveal.

    Designer ruling (OQ-057): buying two copies bumps once per Guild Spy,
    a Guild Spy revealed later in the Reveal still reacts to a purchase made
    earlier in it, and only the Spies on the board at that moment count.
    With ``acquired`` the card was just bought: the Reveal remembers it and
    every revealed, unfired Guild Spy fires; without it a Guild Spy that
    just arrived fires if the purchase already happened this Reveal. The
    box is a Reveal effect, so nothing fires outside the owner's Reveal.
    """

    if not reveal_is_open_for(state, player):
        return RuleResult(state=state)
    context = _reveal_frame_context(state.decision_stack)
    bought = acquired or context.get(SPICE_MUST_FLOW_ACQUIRED_KEY) is True
    fired = {
        card_id
        for card_id in str(context.get(GUILD_SPY_FIRED_KEY, "")).split(",")
        if card_id
    }
    frames = state.decision_stack
    if acquired:
        frames = _update_reveal_frame(frames, {SPICE_MUST_FLOW_ACQUIRED_KEY: True})
    working = replace(state, decision_stack=frames)
    events: list[GameEvent] = []
    if not bought:
        return RuleResult(state=working)
    for card_id in working.players[player].in_play:
        if card_id in fired or (
            personal_card_for_instance(card_id).reveal_acquisition_effect
            is not _GUILD_SPY_EFFECT
        ):
            continue
        for faction in spied_factions(working.players[player]):
            gained = gain_faction_influence(
                working,
                player,
                faction,
                1,
                event_prefix=(
                    f"round:{state.round_number}:player:{player}:"
                    f"reveal_card:{card_id}:spice_must_flow:{faction.value}"
                ),
            )
            working = gained.state
            events.extend(gained.events)
        fired.add(card_id)
    working = replace(
        working,
        decision_stack=_update_reveal_frame(
            working.decision_stack, {GUILD_SPY_FIRED_KEY: ",".join(sorted(fired))}
        ),
    )
    return RuleResult(state=working, events=tuple(events))


COMMAND_PERSUASION = 6
"""Persuasion a Reveal turn must generate for "Command (6+)" [Bloodlines p. 5]."""

# Tech tiles with a "Reveal Turn: Command (6+)" line, and the Reveal-frame
# key recording which have paid this Reveal.
_COMMAND_TECH = (
    ("delivery_bay", TechAbility.COMMAND_TWO_SOLARI),
    ("training_depot", TechAbility.COMMAND_TWO_STRENGTH),
)
_TECH_GRANTED_KEY = "tech_granted"
# Skills whose Reveal-turn bonus this Reveal already paid ("Each one works
# only once each round" [Bloodlines p. 4]).
_SKILL_GRANTED_KEY = "skill_reveal_granted"
# Reveal-turn tile effects the owner still has to take, in any order the
# owner likes [Main p. 12] (OQ-044): Forbidden Weapons' mandatory choice and
# Panopticon's Spy placement.
TECH_PENDING_KEY = "tech_reveal_pending"


def tech_reveal_pending(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    """Return the tile ids whose Reveal-turn effect is still pending."""

    value = context.get(TECH_PENDING_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid pending tile effects")
    return tuple(key for key in value.split(",") if key)


def _reveal_effect_is_eligible(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
    effect: PersonalCardRevealEffect,
    *,
    persuasion: int | None = None,
) -> bool:
    """Return whether one revealed card's automatic Reveal effect applies.

    Mirrors every gate ``begin_reveal_turn`` checks so the late-reveal path
    [FAQ p. 3] can re-adjudicate eligibility at arrival under the same
    rules. ``persuasion`` is the Reveal turn's current total for the
    Bloodlines "Command (6+)" gate; ``None`` (unknown yet) never satisfies
    it.
    """

    return (
        (not effect.requires_high_council or owner.high_council)
        and (
            not effect.requires_commander_in_conflict or owner.commanders_conflict >= 1
        )
        # Immortality: "[genetic marker]: ..." lines need the research token
        # in the marker's column [Immortality pp. 6, 16].
        and (
            effect.minimum_genetic_markers == 0
            or (
                bool(owner.research_space)
                and genetic_markers_reached(owner.research_space)
                >= effect.minimum_genetic_markers
            )
        )
        and (
            owner.troops_garrison + owner.commanders_garrison
            >= effect.minimum_garrisoned_units
        )
        and (
            not effect.requires_command
            or (persuasion is not None and persuasion >= COMMAND_PERSUASION)
        )
        and (not effect.requires_swordmaster or owner.swordmaster_acquired)
        and len(owner.spy_post_ids) >= effect.minimum_spies_placed
        and (
            effect.required_faction_bond is None
            or has_faction_bond(
                cards_in_play,
                card_id,
                Faction(effect.required_faction_bond.value),
            )
        )
        and (
            not effect.requires_spying_on_maker_space or is_spying_on_maker_space(owner)
        )
        # Priority Contracts / Delivery Agreement: "[spice] -OR- If you have
        # completed four or more contracts: Trash this card -> [1 VP]" [card
        # faces]. The spice is one branch of that choice, paid only by it,
        # so a fourth Contract completed later this Reveal (OQ-028 (b)) can
        # never add the Victory Point on top of spice already paid.
        and not (
            effect.spice > 0
            and (
                PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
                in card.reveal_choice_effects
            )
        )
    )


def _eligible_reveal_effects(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
    *,
    persuasion: int | None = None,
) -> tuple[PersonalCardRevealEffect, ...]:
    """Return ``card``'s Reveal effects that currently apply."""

    return tuple(
        effect
        for effect in card.reveal_effects
        if _reveal_effect_is_eligible(
            owner, cards_in_play, card_id, card, effect, persuasion=persuasion
        )
    )


_GRANTED_EFFECTS_KEY = "granted_reveal_effects"


def _granted_reveal_effects(
    context: dict[str, ActionValue],
) -> dict[str, int | None]:
    """Decode which automatic Reveal effects already paid out this Reveal.

    Keys are ``card#index`` over ``card.reveal_effects``; the value is the
    completed-Contract count a per-Contract Persuasion effect was last paid
    for, the sword cards Leadership has counted, or None for every other
    effect.
    """

    value = context.get(_GRANTED_EFFECTS_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid granted effects")
    granted: dict[str, int | None] = {}
    for item in value.split(","):
        if not item:
            continue
        key, separator, count = item.partition("=")
        granted[key] = int(count) if separator else None
    return granted


def _encode_granted(granted: dict[str, int | None]) -> str:
    return ",".join(
        key if count is None else f"{key}={count}" for key, count in granted.items()
    )


# Revealed cards whose Reveal choice provided swords this turn (Chani, Clever
# Tactician's retreat, Calculus of Power, Undercover Asset, Arrakis Observer).
_CHOICE_SWORD_CARDS_KEY = "choice_sword_card_ids"


def _choice_sword_card_ids(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    value = context.get(_CHOICE_SWORD_CARDS_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid choice sword cards")
    return tuple(card_id for card_id in value.split(",") if card_id)


def _count_leadership_swords(state: GameState, player: int) -> RuleResult:
    """Pay Leadership's swords for sword cards it has not counted yet.

    "+[sword] for each other revealed card that provides one or more
    [sword] this turn" [Leadership card]: a card counts through its printed
    or automatic Reveal swords, or through swords its Reveal choice
    provided (Undercover Asset's "-OR- 2 swords"). Leadership "counts at one
    moment and a trashed card cannot be counted" (designer ruling, OQ-057;
    designer-rulings-audit.md), and the owner orders the Reveal effects
    [Main p. 12], so the owner may count at the moment with the most sword
    cards in play. The granted-effect record keeps the count already paid
    (from ``begin_reveal_turn``); this pass tops it up to the current count
    and never takes swords back (OQ-022), which pays exactly the best single
    moment.
    """

    frames = state.decision_stack
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    granted = _granted_reveal_effects(context)
    owner = state.players[player]
    revealed_ids = tuple(
        context_str(context, f"revealed_card_{index:03d}", owner="Reveal frame")
        for index in range(
            context_int(context, "revealed_card_count", owner="Reveal frame")
        )
    )
    revealed_cards = tuple(
        personal_card_for_instance(card_id) for card_id in revealed_ids
    )
    choice_swords = set(_choice_sword_card_ids(context))
    sword_cards = {
        card_id
        for card_id, card in zip(revealed_ids, revealed_cards, strict=True)
        if card_id in owner.in_play
        and (
            card_id in choice_swords
            or card.reveal_strength
            + sum(
                _reveal_effect_strength(effect, revealed_cards)
                for index, effect in enumerate(card.reveal_effects)
                if f"{card_id}#{index}" in granted
            )
            > 0
        )
    }
    updates: dict[str, int | None] = {}
    swords = 0
    for card_id, card in zip(revealed_ids, revealed_cards, strict=True):
        if card_id not in owner.in_play:
            continue
        for index, effect in enumerate(card.reveal_effects):
            counted = granted.get(f"{card_id}#{index}")
            if not effect.strength_per_other_sword_card or counted is None:
                continue
            now = len(sword_cards - {card_id})
            if now > counted:
                swords += effect.strength_per_other_sword_card * (now - counted)
                updates[f"{card_id}#{index}"] = now
    if not swords:
        return RuleResult(state=state)
    units = owner.units_in_conflict
    frames = _add_reveal_sword(
        _record_granted_effects(frames, updates),
        swords,
        counts_toward_combat=units > 0,
    )
    next_owner = replace(
        owner, combat_strength=owner.combat_strength + (swords if units else 0)
    )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=frames,
        ),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:reveal:"
                    f"leadership:{','.join(f'{key}={n}' for key, n in updates.items())}"
                ),
                kind="reveal_strength_gained",
                payload=(("amount", swords), ("player", player)),
            ),
        ),
    )


def _granted_entries(
    card_ids: tuple[str, ...],
    cards: tuple[PersonalCardDefinition, ...],
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    completed_contracts: int,
    *,
    persuasion: int | None = None,
) -> dict[str, int | None]:
    """Return the granted-effect entries for the cards' currently eligible effects."""

    entries: dict[str, int | None] = {}
    for card_id, card in zip(card_ids, cards, strict=True):
        for index, effect in enumerate(card.reveal_effects):
            if _reveal_effect_is_eligible(
                owner, cards_in_play, card_id, card, effect, persuasion=persuasion
            ):
                # Leadership keeps the number of sword cards it has counted
                # (``_count_leadership_swords``); a new entry has counted none.
                entries[f"{card_id}#{index}"] = (
                    completed_contracts
                    if effect.persuasion_per_completed_contract
                    else 0
                    if effect.strength_per_other_sword_card
                    else None
                )
    return entries


# Reveal gains the owner resolves as their own actions, in any order
# [Main p. 12] (OQ-045): troop recruits, Intrigue draws and resource gains.
# Their timing matters — the supply may fill (a troop lost to a Twisted
# Intrigue cost), a tile may arrive (Suspensor Suits through Rapid
# Engineering), or spice may be spent before Forbidden Weapons' trash — so
# they wait on the Reveal frame as ``kind|payload|source`` entries: the
# payload is a count for troops and Intrigue and ``solari/spice/water`` for
# resources.
REVEAL_GAINS_KEY = "reveal_pending_gains"
RevealGain = tuple[str, str, str]


def reveal_pending_gains(
    context: Mapping[str, ActionValue],
) -> tuple[RevealGain, ...]:
    """Return the (kind, payload, source) gains still waiting in this Reveal."""

    value = context.get(REVEAL_GAINS_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid pending gains")
    entries: list[RevealGain] = []
    for item in value.split(","):
        if not item:
            continue
        kind, payload, source = item.split("|", 2)
        entries.append((kind, payload, source))
    return tuple(entries)


def _encode_gains(entries: tuple[RevealGain, ...]) -> str:
    return ",".join(f"{kind}|{payload}|{source}" for kind, payload, source in entries)


def resource_gain_entry(
    source: str, *, solari: int = 0, spice: int = 0, water: int = 0
) -> RevealGain | None:
    """Return a pending resource gain, or None when nothing is gained."""

    if not (solari or spice or water):
        return None
    return ("resources", f"{solari}/{spice}/{water}", source)


def influence_gain_entry(
    source: str, effect: PersonalCardRevealEffect
) -> RevealGain | None:
    """Return a pending fixed-Faction Influence gain, or None without one."""

    if effect.influence_faction is None or effect.influence <= 0:
        return None
    return ("influence", f"{effect.influence_faction.value}/{effect.influence}", source)


def _resource_payload(payload: str) -> tuple[int, int, int]:
    solari, spice, water = (int(part) for part in payload.split("/"))
    return solari, spice, water


def _append_reveal_gains(
    frames: tuple[DecisionFrame, ...],
    entries: tuple[RevealGain, ...],
) -> tuple[DecisionFrame, ...]:
    """Queue more troop or Intrigue gains on the Reveal frame, wherever it sits."""

    if not entries:
        return frames
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    context[REVEAL_GAINS_KEY] = _encode_gains(
        (*reveal_pending_gains(context), *entries)
    )
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def _append_reveal_gains_state(
    state: GameState, entries: tuple[RevealGain, ...]
) -> GameState:
    return replace(
        state, decision_stack=_append_reveal_gains(state.decision_stack, entries)
    )


def queue_reveal_intrigue_draw(state: GameState, count: int, source: str) -> GameState:
    """Queue an Intrigue draw on the open Reveal frame's pending gains.

    The owner takes it with ``draw_reveal_intrigue`` in any order before the
    Reveal ends (OQ-045); a Reveal passive's draw waits there too rather
    than being drawn by the step that met its condition (user ruling
    2026-10-10, OQ-106).
    """

    return _append_reveal_gains_state(state, (("intrigue", str(count), source),))


def legal_reveal_gain_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the pending troop recruit and Intrigue draw of the owner's Reveal.

    Each resolves the oldest pending entry of its kind; entries of one kind
    are interchangeable (the same supply, the same deck), so no argument is
    needed. Both must be taken before the Reveal ends.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    pending = reveal_pending_gains(dict(frame.context))
    kinds = {kind for kind, _, _ in pending}
    actions: list[DomainAction] = []
    if "troops" in kinds:
        actions.append(DomainAction(action_id="recruit_reveal_troops", actor=player))
    if "intrigue" in kinds:
        actions.append(DomainAction(action_id="draw_reveal_intrigue", actor=player))
    if "specimens" in kinds:
        actions.append(
            DomainAction(action_id="generate_reveal_specimens", actor=player)
        )
    if "tleilaxu" in kinds:
        actions.append(DomainAction(action_id="advance_reveal_tleilaxu", actor=player))
    if "research" in kinds:
        actions.append(DomainAction(action_id="advance_reveal_research", actor=player))
    # Resource gains differ in what they give, so each distinct bundle is
    # its own choice; equal bundles are interchangeable.
    for payload in dict.fromkeys(
        payload for kind, payload, _ in pending if kind == "resources"
    ):
        solari, spice, water = _resource_payload(payload)
        actions.append(
            DomainAction(
                action_id="gain_reveal_resources",
                actor=player,
                arguments=(("solari", solari), ("spice", spice), ("water", water)),
            )
        )
    # Fixed-Faction Influence gains: one choice per Faction still pending.
    for faction in dict.fromkeys(
        payload.split("/")[0] for kind, payload, _ in pending if kind == "influence"
    ):
        actions.append(
            DomainAction(
                action_id="gain_reveal_faction_influence",
                actor=player,
                arguments=(("faction", faction),),
            )
        )
    return tuple(actions)


def apply_reveal_gain(state: GameState, action: DomainAction) -> RuleResult:
    """Recruit the next pending troops or draw the next pending Intrigue."""

    if action not in legal_reveal_gain_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal gain")
    player = action.actor
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    pending = reveal_pending_gains(context)
    arguments = dict(action.arguments)
    if action.action_id == "gain_reveal_resources":
        wanted_payload = "/".join(
            str(arguments.get(name, 0)) for name in ("solari", "spice", "water")
        )
        index = next(
            i
            for i, (kind, payload, _) in enumerate(pending)
            if kind == "resources" and payload == wanted_payload
        )
    elif action.action_id == "gain_reveal_faction_influence":
        wanted_faction = str(arguments["faction"])
        index = next(
            i
            for i, (kind, payload, _) in enumerate(pending)
            if kind == "influence" and payload.split("/")[0] == wanted_faction
        )
    else:
        wanted = {
            "recruit_reveal_troops": "troops",
            "draw_reveal_intrigue": "intrigue",
            "generate_reveal_specimens": "specimens",
            "advance_reveal_tleilaxu": "tleilaxu",
            "advance_reveal_research": "research",
        }[action.action_id]
        index = next(i for i, (kind, _, _) in enumerate(pending) if kind == wanted)
    kind, payload, source = pending[index]
    context[REVEAL_GAINS_KEY] = _encode_gains((*pending[:index], *pending[index + 1 :]))
    event_id = f"round:{state.round_number}:player:{player}:reveal_gain:{source}"
    owner = state.players[player]
    if kind == "influence":
        faction_value, amount_text = payload.split("/")
        settled = replace(
            state,
            decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
        )
        return gain_faction_influence(
            settled,
            player,
            Faction(faction_value),
            int(amount_text),
            event_prefix=f"{event_id}:influence:{faction_value}",
        )
    if kind == "resources":
        solari, spice, water = _resource_payload(payload)
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + solari,
                spice=owner.resources.spice + spice,
                water=owner.resources.water + water,
            ),
        )
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=(
                    *state.decision_stack[:-1],
                    with_context(frame, context),
                ),
            ),
            events=(
                GameEvent(
                    event_id=event_id,
                    kind="reveal_resources_gained",
                    payload=(
                        ("player", player),
                        ("solari", solari),
                        ("source", source),
                        ("spice", spice),
                        ("water", water),
                    ),
                ),
            ),
        )
    count = int(payload)
    if kind in ("specimens", "tleilaxu", "research"):
        # Imported here: the research module imports the card draw, which
        # imports this module.
        from dune_imperium.rules.immortality import (
            advance_research,
            advance_tleilaxu,
        )

        settled = replace(
            state,
            decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
        )
        if kind == "specimens":
            return generate_specimens(settled, player, count, source=event_id)
        if kind == "tleilaxu":
            return advance_tleilaxu(settled, player, count, source=event_id)
        # A Reveal-box Research icon (Tleilaxu Master): each action advances
        # once, so the two icons may be resolved apart with other Reveal
        # effects between them (designer ruling, OQ-057); the advance may
        # open a direction choice above the Reveal frame.
        researched = advance_research(settled, player, source=f"{event_id}:{count}")
        remaining = count - 1
        if remaining:
            researched = RuleResult(
                state=_append_reveal_gains_state(
                    researched.state, (("research", str(remaining), source),)
                ),
                events=researched.events,
            )
        return researched
    if kind == "troops":
        next_owner, recruited = recruit_troops(owner, count)
        context["reveal_troops_recruited"] = (
            context_int(context, "reveal_troops_recruited", owner="Reveal frame")
            + recruited
        )
        next_state = replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
        )
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=event_id,
                    kind="reveal_troops_recruited",
                    payload=(
                        ("player", player),
                        ("source", source),
                        ("troops", recruited),
                    ),
                ),
                *recruit_shortfall_events(event_id, player, count, recruited),
            ),
        )
    queued = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
    )
    drawn = draw_or_queue_intrigue_cards(queued, player, count, source=event_id)
    return RuleResult(state=drawn.state, events=drawn.events)


def _record_granted_effects(
    frames: tuple[DecisionFrame, ...],
    entries: dict[str, int | None],
) -> tuple[DecisionFrame, ...]:
    """Merge granted-effect entries into the Reveal frame, wherever it sits."""

    if not entries:
        return frames
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    granted = _granted_reveal_effects(context)
    granted.update(entries)
    context[_GRANTED_EFFECTS_KEY] = _encode_granted(granted)
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def _add_reveal_sword(
    frames: tuple[DecisionFrame, ...],
    amount: int,
    *,
    counts_toward_combat: bool,
) -> tuple[DecisionFrame, ...]:
    """Add sword strength to the Reveal frame (counted only with a unit)."""

    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    context["sword_strength"] = (
        context_int(context, "sword_strength", owner="Reveal frame") + amount
    )
    if counts_toward_combat:
        context["strength"] = (
            context_int(context, "strength", owner="Reveal frame") + amount
        )
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def _granted_skill_ids(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    value = context.get(_SKILL_GRANTED_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid granted Skills")
    return tuple(skill_id for skill_id in value.split(",") if skill_id)


def _late_skill_bonuses(
    context: Mapping[str, ActionValue], owner: PlayerState
) -> tuple[SkillDefinition, ...]:
    """Return the owner's Reveal-bonus Skills that became active this Reveal.

    A frame without the record (built before it existed) pays none.
    """

    if owner.commanders_conflict < 1 or _SKILL_GRANTED_KEY not in context:
        return ()
    granted = set(_granted_skill_ids(context))
    return tuple(
        skill
        for skill in (skill_for_instance(instance) for instance in owner.skill_ids)
        if skill.skill_id not in granted
        and (skill.reveal_persuasion or skill.reveal_spice or skill.reveal_troops)
    )


def grant_late_reveal_effects(result: RuleResult) -> RuleResult:
    """Pay out revealed cards' automatic effects whose condition came true later.

    Automatic Reveal effects are applied when the Reveal begins. A printed
    condition that fails at that moment — two Spies placed, a High Council
    seat, a Faction Bond, spying on a Maker space, completed Contracts — can
    still be met by the owner's later choices in the same Reveal: a Spy
    placed by another card's Reveal effect, a seat bought through Corrinth
    City, a Fremen card arriving late, an Acquire Contract completed by a
    purchase. Reveal effects resolve in any order the owner likes
    [Main p. 12], so each such effect pays out the first time its condition
    holds during the Reveal and is recorded on the Reveal frame so it never
    repeats. Interstellar Trade's "[1 Persuasion] for each contract you have
    completed" [card face] records the count it was paid for and pays +1 for
    each Contract completed later in the Reveal, whatever completed it (OQ-028
    (c), user ruling 2026-10-04). Only a card still in play pays: "you can't
    receive or activate an effect from a card that is already trashed"
    (designer ruling, OQ-022), and what was paid stays paid. The cards are
    swept until nothing new pays, so Persuasion paid late by one card opens
    a "Command (6+)" line on another whatever their order in the hand.
    """

    state = result.state
    position = next(
        (
            index
            for index in range(len(state.decision_stack) - 1, -1, -1)
            if state.decision_stack[index].kind == FrameKind.REVEAL
        ),
        None,
    )
    if position is None:
        return result
    frame = state.decision_stack[position]
    if not isinstance(frame.decision, PlayerDecision):
        return result
    player = frame.decision.owner
    context = frame_context(frame)
    granted = _granted_reveal_effects(context)
    owner = state.players[player]
    revealed_ids = tuple(
        context_str(context, f"revealed_card_{index:03d}", owner="Reveal frame")
        for index in range(
            context_int(context, "revealed_card_count", owner="Reveal frame")
        )
    )
    revealed_cards = tuple(
        personal_card_for_instance(card_id) for card_id in revealed_ids
    )
    completed = len(owner.completed_contract_ids)
    units = owner.units_in_conflict
    frames = state.decision_stack
    next_owner = owner
    events: list[GameEvent] = list(result.events)
    late_gains: list[RevealGain] = []
    pending_trashes: list[tuple[str, str]] = []
    pending_combat_icons = 0
    newly_granted: dict[str, int | None] = {}
    # Skills switch on while any Commander is in the Conflict [Bloodlines
    # p. 4]; one that arrives there during the Reveal (a Combat icon
    # deployment) pays its Reveal-turn bonus then, once (OQ-028 (c)). Paid
    # first, so Charismatic's Persuasion counts toward Command (6+) below.
    late_skills = _late_skill_bonuses(context, owner)
    for skill in late_skills:
        if skill.reveal_persuasion:
            frames = add_reveal_persuasion(frames, skill.reveal_persuasion)
        skill_resources = resource_gain_entry(
            f"skill:{skill.skill_id}", spice=skill.reveal_spice
        )
        if skill_resources is not None:
            late_gains.append(skill_resources)
        if skill.reveal_troops:
            # Hardy: "Reveal Turn: [troop]" [Hardy Skill tile], waiting for
            # the owner's order like the Reveal-start recruit (OQ-045).
            late_gains.append(
                ("troops", str(skill.reveal_troops), f"skill:{skill.skill_id}")
            )
        events.append(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:reveal:"
                    f"skill:{skill.skill_id}:late"
                ),
                kind="skill_reveal_bonus",
                payload=(
                    ("persuasion", skill.reveal_persuasion),
                    ("player", player),
                    ("skill_id", skill.skill_id),
                    ("spice", skill.reveal_spice),
                    ("troops", skill.reveal_troops),
                ),
            )
        )
    if late_skills:
        frames = _update_reveal_frame(
            frames,
            {
                _SKILL_GRANTED_KEY: ",".join(
                    (
                        *_granted_skill_ids(context),
                        *(skill.skill_id for skill in late_skills),
                    )
                )
            },
        )
    # What has paid so far: the record from the Reveal frame plus this pass's
    # grants, so a repeated sweep never pays an effect or a Contract twice.
    paid = dict(granted)
    # "You may resolve Reveal effects in any order you like" [Main p. 12],
    # and a "Command (6+)" line is used once the Reveal turn has generated 6
    # or more Persuasion [Bloodlines pp. 5, 12]: Persuasion paid late by a
    # card visited after a Command card (Interstellar Trade's +1, Southern
    # Elders' Fremen Bond, Bene Gesserit Operative's two Spies) still opens
    # it. The sweep repeats until it grants nothing new, so the result never
    # depends on the hand's order. Nothing in the sweep removes a card from
    # play or completes a Contract; self-trashes and Combat icons wait until
    # it has settled.
    sweeping = True
    while sweeping:
        sweeping = False
        for card_id, card in zip(revealed_ids, revealed_cards, strict=True):
            if card_id not in next_owner.in_play:
                # A card trashed earlier in the Reveal pays nothing more: "you
                # can't receive or activate an effect from a card that is
                # already trashed" (designer ruling, OQ-022).
                continue
            for index, effect in enumerate(card.reveal_effects):
                key = f"{card_id}#{index}"
                source = (
                    f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
                )
                counted_contracts = paid.get(key)
                if effect.persuasion_per_completed_contract and (
                    counted_contracts is not None
                ):
                    # Interstellar Trade pays +1 for each Contract completed
                    # later in this Reveal (OQ-028 (c), user ruling
                    # 2026-10-04, which overturns the designer ruling that it
                    # triggers once, adopted as OQ-057 (2)).
                    if completed > counted_contracts:
                        delta = effect.persuasion_per_completed_contract * (
                            completed - counted_contracts
                        )
                        frames = add_reveal_persuasion(frames, delta)
                        newly_granted[key] = paid[key] = completed
                        sweeping = True
                        events.append(
                            GameEvent(
                                event_id=(
                                    f"{source}:{index}:late_contracts:{completed}"
                                ),
                                kind="reveal_effect_granted_late",
                                payload=(
                                    ("card_id", card_id),
                                    ("effect_index", index),
                                    ("persuasion", delta),
                                    ("player", player),
                                ),
                            )
                        )
                    continue
                if key in paid:
                    continue
                if not _reveal_effect_is_eligible(
                    next_owner,
                    counted_in_play(next_owner),
                    card_id,
                    card,
                    effect,
                    persuasion=_frame_generated_persuasion(frames),
                ):
                    continue
                persuasion = _reveal_effect_persuasion(
                    effect, revealed_cards, completed, _in_play_cards(next_owner)
                )
                sword = _reveal_effect_strength(effect, revealed_cards)
                if persuasion:
                    frames = add_reveal_persuasion(frames, persuasion)
                if sword:
                    frames = _add_reveal_sword(
                        frames, sword, counts_toward_combat=units > 0
                    )
                next_owner = replace(
                    next_owner,
                    combat_strength=next_owner.combat_strength
                    + (sword if units else 0),
                )
                if effect.recruit_troops:
                    late_gains.append(("troops", str(effect.recruit_troops), card_id))
                if effect.draw_intrigue:
                    late_gains.append(("intrigue", str(effect.draw_intrigue), card_id))
                if effect.specimens:
                    late_gains.append(("specimens", str(effect.specimens), card_id))
                if effect.tleilaxu:
                    late_gains.append(("tleilaxu", str(effect.tleilaxu), card_id))
                if effect.research:
                    late_gains.append(("research", str(effect.research), card_id))
                resources = resource_gain_entry(
                    card_id,
                    solari=effect.solari,
                    spice=effect.spice,
                    water=effect.water,
                )
                if resources is not None:
                    late_gains.append(resources)
                influence = influence_gain_entry(card_id, effect)
                if influence is not None:
                    late_gains.append(influence)
                if effect.trashes_self:
                    pending_trashes.append((f"{source}:{index}:late", card_id))
                if effect.grants_combat_icon:
                    pending_combat_icons += 1
                # Defensive: no per-Contract effect is gated today (Interstellar
                # Trade always applies and is recorded with its count when it is
                # revealed, so it takes the branch above). A gated one would
                # keep the count it was paid for here, and later Contracts would
                # add their increment above.
                newly_granted[key] = paid[key] = (
                    completed if effect.persuasion_per_completed_contract else None
                )
                sweeping = True
                events.append(
                    GameEvent(
                        event_id=f"{source}:{index}:late",
                        kind="reveal_effect_granted_late",
                        payload=(
                            ("card_id", card_id),
                            ("effect_index", index),
                            ("persuasion", persuasion),
                            ("player", player),
                            ("solari", effect.solari),
                            ("spice", effect.spice),
                            ("strength", sword),
                            ("troops", effect.recruit_troops),
                            ("water", effect.water),
                        ),
                    )
                )
    # Tech tiles whose Command (6+) line opens late pay the same way, on the
    # Persuasion generated so far, spent or not [Bloodlines p. 5].
    late_persuasion = _frame_generated_persuasion(frames)
    reveal_context = frame_context(frames[_reveal_frame_position(frames)])
    tech_granted = tuple(
        key
        for key in str(reveal_context.get(_TECH_GRANTED_KEY, "")).split(",")
        if key
    )
    late_tech = tuple(
        tech_id
        for tech_id, ability in _COMMAND_TECH
        if late_persuasion is not None
        and late_persuasion >= COMMAND_PERSUASION
        and tech_id not in tech_granted
        and has_tech(next_owner.tech_ids, ability)
    )
    for tech_id in late_tech:
        solari = 2 if tech_id == "delivery_bay" else 0
        sword = 2 if tech_id == "training_depot" else 0
        if sword:
            frames = _add_reveal_sword(frames, sword, counts_toward_combat=units > 0)
        next_owner = replace(
            next_owner,
            combat_strength=next_owner.combat_strength + (sword if units else 0),
        )
        tile_resources = resource_gain_entry(f"tech:{tech_id}", solari=solari)
        if tile_resources is not None:
            late_gains.append(tile_resources)
        events.append(
            GameEvent(
                event_id=f"round:{state.round_number}:player:{player}:tech:{tech_id}:late",
                kind="tech_reveal_bonus",
                payload=(
                    ("player", player),
                    ("solari", solari),
                    ("strength", sword),
                    ("tech_id", tech_id),
                ),
            )
        )
    if late_tech:
        position = _reveal_frame_position(frames)
        reveal_context = frame_context(frames[position])
        reveal_context[_TECH_GRANTED_KEY] = ",".join((*tech_granted, *late_tech))
        frames = (
            *frames[:position],
            with_context(frames[position], reveal_context),
            *frames[position + 1 :],
        )
    frames = _record_granted_effects(frames, newly_granted)
    frames = _append_reveal_gains(frames, tuple(late_gains))
    # Leadership may count every sword card provided so far, a late-met
    # effect's or a Reveal choice's included, before a late self-trash.
    counted = _count_leadership_swords(
        replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=frames,
        ),
        player,
    )
    if not newly_granted and not late_tech and not late_skills and not counted.events:
        return result
    working = counted.state
    events.extend(counted.events)
    for trash_source, trashed_card_id in pending_trashes:
        if trashed_card_id in working.players[player].in_play:
            trashed = trash_personal_card(
                working, player, trashed_card_id, source=trash_source
            )
            # No AGENT_EFFECTS frame is on top in a Reveal, so the trash's
            # own troops (none on a shipped card yet) are credited here.
            trashed = credit_trash_recruits(trashed, player)
            working = trashed.state
            events.extend(trashed.events)
    if pending_combat_icons:
        working = grant_combat_icon(working, player)
    return RuleResult(state=working, events=tuple(events))


def _reveal_effect_persuasion(
    effect: PersonalCardRevealEffect,
    revealed_cards: tuple[PersonalCardDefinition, ...],
    completed_contracts: int,
    in_play_cards: tuple[PersonalCardDefinition, ...],
) -> int:
    """Return one eligible effect's Persuasion over the revealed or in-play set.

    "Revealed" counts this Reveal's cards (Sardaukar Coordination);
    "in play" also counts the cards played on this round's Agent turns
    [Main p. 20 "In Play"] [FAQ p. 2 Liet Kynes] (Stilgar, The Devoted).
    """

    if effect.per_revealed_faction is not None:
        counted = sum(
            Faction(effect.per_revealed_faction.value) in card.factions
            for card in revealed_cards
        )
    elif effect.per_in_play_faction is not None:
        counted = sum(
            Faction(effect.per_in_play_faction.value) in card.factions
            for card in in_play_cards
        )
    else:
        counted = 1
    return (
        effect.persuasion * counted
        + effect.persuasion_per_completed_contract * completed_contracts
    )


def _in_play_cards(owner: PlayerState) -> tuple[PersonalCardDefinition, ...]:
    # Only the cards that count as in play (OQ-054, ``counted_in_play``).
    return tuple(
        personal_card_for_instance(card_id) for card_id in counted_in_play(owner)
    )


def _reveal_effect_strength(
    effect: PersonalCardRevealEffect,
    revealed_cards: tuple[PersonalCardDefinition, ...],
) -> int:
    """Return one eligible effect's own-card strength over the revealed set."""

    return effect.strength * (
        sum(
            Faction(effect.per_revealed_faction.value) in card.factions
            for card in revealed_cards
        )
        if effect.per_revealed_faction is not None
        else 1
    )


def reveal_choice_prompt(effect: PersonalCardRevealChoiceEffect) -> str:
    """Return the REVEAL_CHOICE frame prompt text for one choice effect."""

    effect = _RESOLVES_AS.get(effect, effect)
    return (
        "Bene Gesserit Alliance: you may lose two Influence with one Faction "
        "for a Victory Point"
        if effect
        is _LOSE_INFLUENCE_FOR_VP
        else "You may deploy or retreat one troop"
        if effect is PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP
        else "You may lose two troops for two specimens"
        if effect is _LOSE_TROOPS_FOR_SPECIMENS
        else "You may trash this card for one Influence with each Faction"
        if effect
        is (
            PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS
        )
        else "Choose one Persuasion or a Contract"
        if effect is PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT
        else "You may recall a Spy for three swords"
        if effect is PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH
        else "Command: you may trash this card to acquire an Imperium Row card"
        if effect
        is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD
        else "You may trash this card for the Combat icon"
        if effect is PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON
        else "Command: you may trash a card"
        if effect is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD
        else "Command: choose where to place a Spy"
        if effect is PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY
        else "Command: choose a Faction to gain one Influence with"
        if effect is PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE
        else "Two or more Tech tiles: choose a Faction to gain one Influence with"
        if effect is PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH
        else "You may retreat two troops for two Persuasion"
        if effect
        is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION
        else "You may lose one Influence to gain one Influence"
        if effect is PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
        else "You may pay three Spice for one Influence"
        if effect is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
        else "Choose where to place the Spy you chose over two strength"
        if effect is PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH
        else "Choose where to place a Spy for this Reveal effect"
        if effect is PersonalCardRevealChoiceEffect.PLACE_SPY
        else "You may recall two Spies for three Persuasion"
        if effect
        is (PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION)
        else "You may trash another Emperor card for three swords"
        if effect
        is (PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH)
        else "You may retreat two troops for four strength"
        if effect
        is (PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH)
        else "Gain five Solari or pay five for a High Council seat"
        if effect
        is (PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL)
        else "Gain two Persuasion or pay one Water for a sandworm"
        if effect is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
        else "Gain Spice or trash this card for one Victory Point"
        if effect
        is (
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
        )
        else "You may recall a Spy to draw an Intrigue card"
        if effect
        is PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED
        else "Choose a Spy to recall for this Reveal effect"
    )


_INFLUENCE_GAIN_CHOICES: Final = frozenset(
    {
        PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE,
        PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH,
        PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE,
    }
)


def reveal_influence_choice_blocked(
    owner: PlayerState, effect: PersonalCardRevealChoiceEffect
) -> bool:
    """Whether a "choose a Faction" Reveal gain has no cube that can rise.

    A gain on a cube at the top of its track is lost (OQ-060), so with every
    cube there Pointing the Way's Command, Ixian Ambassador's gain and the
    "3 spice -> Influence" line do not open: the choice waits deferred like
    one whose printed condition fails, opens again if a later effect of the
    Reveal lowers a cube, and lapses at ``finish_reveal`` otherwise [Main
    p. 12] -- the three spice are never offered for nothing (OQ-071). The
    page greys the waiting choice out with this test (``display.unavailable``).
    """

    return effect in _INFLUENCE_GAIN_CHOICES and not any(
        influence_can_rise(owner, faction) for faction in Faction
    )


def _reveal_choice_effect_is_available(
    state: GameState,
    player: int,
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    effect: PersonalCardRevealChoiceEffect,
    *,
    persuasion: int | None = None,
) -> bool:
    """Return whether one revealed card's choice effect currently opens.

    Mirrors every availability gate ``begin_reveal_turn`` checks, evaluated
    against whichever ``owner``/``state`` snapshot the caller passes, so the
    late-reveal path [FAQ p. 3] can push the same choice under the same
    rules at arrival time. ``persuasion`` gates the Bloodlines "Command
    (6+)" choices; a deferred Command choice reopens once the Reveal's
    Persuasion reaches six [Bloodlines p. 5].
    """

    command_open = persuasion is not None and persuasion >= COMMAND_PERSUASION
    ability = reveal_choice_ability(effect)
    if target_reward_choice(ability):
        # Spy Network, Arrakis Observer, Calculus of Power, Shrouded
        # Counsel, Disruption Tactics, CHOAM Demands, Pointing the Way, Ixian
        # Ambassador: from their records (composed A4d).
        return target_reward_is_available(
            owner, cards_in_play, card_id, effect, persuasion
        )
    if spy_icon_choice(ability):
        # A Spy icon always opens (a supply Spy with no free post waits on
        # its rows); Intelligence Training's on Command (composed A4e).
        return _target_condition_holds(ability.sections[0].condition, owner, persuasion)
    if either_choice(ability):
        # Corrinth City, Delivery Logistics (composed A4f).
        return either_is_available(state, ability)
    return (
        (
            # For Humanity: the Alliance and two Influence with one Faction
            # to lose, judged when the choice opens (OQ-028).
            effect
            is _LOSE_INFLUENCE_FOR_VP
            and Faction.BENE_GESSERIT.value in owner.alliance_faction_ids
            and any(
                influence_amount(owner.influence, faction)
                >= _FOR_HUMANITY_INFLUENCE_COST
                for faction in Faction
            )
        )
        or (
            # Shadout Mapes: a Commander is a troop [Bloodlines p. 4].
            effect is PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP
            and owner.troops_garrison
            + owner.commanders_garrison
            + owner.troops_conflict
            + owner.commanders_conflict
            >= 1
        )
        or (
            # Tleilaxu Surgeon: any two troops, from either zone (OQ-053).
            effect is _LOSE_TROOPS_FOR_SPECIMENS
            and owner.troops_garrison + owner.troops_conflict >= 2
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION
            and owner.troops_conflict + owner.commanders_conflict >= 2
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD
            and command_open
            and bool(state.imperium_row)
            and card_id in cards_in_play
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
            and any(
                influence_amount(owner.influence, faction) > 0 for faction in Faction
            )
        )
        or (
            effect is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
            and owner.resources.spice >= 3
            and not reveal_influence_choice_blocked(owner, effect)
        )
        or (
            # Unswerving Loyalty: "Fremen Bond: You may deploy or retreat one
            # of your troops" [Unswerving Loyalty card] -- "one or more other
            # Fremen cards in play" [Main p. 20], judged when the choice opens
            # like the other Reveal conditions (OQ-028); then Shadout Mapes'
            # own condition (a troop to move).
            effect is _FREMEN_BOND_TROOP_MOVE
            and has_faction_bond(cards_in_play, card_id, Faction.FREMEN)
            and _reveal_choice_effect_is_available(
                state,
                player,
                owner,
                cards_in_play,
                card_id,
                PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP,
            )
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH
            # Sardaukar Commanders are troops for the retreat [Bloodlines p. 4].
            and owner.troops_conflict + owner.commanders_conflict >= 2
        )
        # The Persuasion branch is always choosable, so the choice always
        # opens, with or without Maker Hooks (option (B), user ruling
        # 2026-09-30); ``legal_reveal_sandworm_actions`` gates the sandworm
        # branch itself through ``reveal_sandworm_block`` (Maker Hooks, water,
        # a Conflict, the Shield Wall).
        or effect is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION
            and len(owner.spy_post_ids) >= 2
        )
        # The spice branch needs nothing, so this choice always opens; its
        # trash branch is offered only with four completed Contracts at
        # resolution (legal_contract_reveal_choice_actions).
        or effect
        is (
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
        )
    )


def reveal_choice_effect_is_available(
    state: GameState,
    player: int,
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    effect: PersonalCardRevealChoiceEffect,
    *,
    persuasion: int | None = None,
) -> bool:
    """Whether one revealed card's choice effect can be taken on these facts.

    The gate a pending entry is offered by (``_available_pending_choices``,
    which also needs the card still in play, OQ-022), for a caller that
    judges it on another snapshot: ``records.migration`` follows an older
    engine's choice frames, which it opened by this gate alone.
    """

    return _reveal_choice_effect_is_available(
        state, player, owner, cards_in_play, card_id, effect, persuasion=persuasion
    )


def _build_reveal_choice_frame(
    round_number: int,
    player: int,
    card_id: str,
    effect: PersonalCardRevealChoiceEffect,
) -> DecisionFrame:
    """Return the REVEAL_CHOICE frame for one revealed card's choice effect."""

    return DecisionFrame(
        kind=FrameKind.REVEAL_CHOICE,
        frame_id=(
            f"round:{round_number}:player:{player}:reveal_spy:{card_id}:{effect.value}"
        ),
        decision=PlayerDecision(owner=player, prompt=reveal_choice_prompt(effect)),
        context=(
            ("reveal_card_id", card_id),
            ("reveal_choice_effect", effect.value),
            ("turn_owner", player),
        ),
    )


# The Reveal frame's pending choices: one ``card|effect`` entry per choice
# effect of a revealed card, in hand order, with late arrivals and Covert
# Operation's second Spy appended (OQ-095 (7) addition, user ruling
# 2026-10-14; codec v147). The key keeps the name of the queue it replaced,
# which held the deferred choices.
# The Reveal choices whose flow stays code here, named by their records'
# ``hook`` (``content.uprising.reveal_choice_abilities``, composed A4d): one
# action pays a cost with its targets in one row (two Spies, an Influence
# exchange or loss, spice for Influence, two troops retreated or lost, a
# troop deployed or retreated), Engineered Miracle's purchase, or a choice
# reaching outside its entry (Desert Power's held Persuasion, Priority
# Contracts' printed spice).
REVEAL_CHOICE_HOOKS: Final = frozenset(
    {
        "recall_two_spies",
        "influence_exchange",
        "spice_for_influence",
        "retreat_two_troops",
        "command_acquisition",
        "influence_for_vp",
        "deploy_or_retreat_troop",
        "troops_for_specimens",
        "desert_power",
        "priority_contracts",
    }
)

_PENDING_CHOICES_KEY = "deferred_reveal_choices"
_CHOICE_FRAME = "Reveal choice frame"

type PendingChoice = tuple[str, str]
type ChoiceProvider = Callable[[GameState, int], tuple[DomainAction, ...]]


def pending_reveal_choices(
    context: Mapping[str, ActionValue],
) -> tuple[PendingChoice, ...]:
    """Decode the Reveal frame's pending (card, effect) choices, oldest first."""

    value = context.get(_PENDING_CHOICES_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid pending choices")
    entries: list[PendingChoice] = []
    for item in value.split(","):
        if not item:
            continue
        card_id, _, effect = item.partition("|")
        entries.append((card_id, effect))
    return tuple(entries)


def _encode_pending(entries: tuple[PendingChoice, ...]) -> str:
    return ",".join(f"{card_id}|{effect}" for card_id, effect in entries)


def _reveal_frame_position(frames: tuple[DecisionFrame, ...]) -> int:
    for index in range(len(frames) - 1, -1, -1):
        if frames[index].kind == FrameKind.REVEAL:
            return index
    raise RuntimeError("Reveal choice is missing its Reveal frame")


def _queue_pending_choices(
    frames: tuple[DecisionFrame, ...],
    entries: tuple[PendingChoice, ...],
) -> tuple[DecisionFrame, ...]:
    """Append (card, effect) entries to the Reveal frame's pending choices."""

    if not entries:
        return frames
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    context[_PENDING_CHOICES_KEY] = _encode_pending(
        (*pending_reveal_choices(context), *entries)
    )
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def _available_pending_choices(
    state: GameState,
    player: int,
    context: Mapping[str, ActionValue],
) -> frozenset[PendingChoice]:
    """Return the pending entries whose card is in play and whose printed
    condition holds right now.

    "You can't receive or activate an effect from a card that is already
    trashed" (designer ruling, OQ-022), which applies to the Reveal's freely
    ordered choices too (its 2026-09-07 addition), as a late Reveal effect
    is paid only while its card is still in play (OQ-028 re-ruling
    2026-10-04): an entry whose card another effect trashed (Calculus of
    Power's or Shrouded Counsel's trash) offers nothing, does not hold
    ``finish_reveal`` and lapses there. A card that trashes itself through
    its own choice uses up that entry when it opens.
    """

    owner = state.players[player]
    # Command (6+) is judged on the Persuasion generated this Reveal turn
    # [Bloodlines pp. 5, 12], so a purchase does not close it again.
    persuasion = _generated_persuasion(context)
    cards_in_play = counted_in_play(owner)
    return frozenset(
        (card_id, effect_value)
        for card_id, effect_value in pending_reveal_choices(context)
        if card_id in owner.in_play
        and _reveal_choice_effect_is_available(
            state,
            player,
            owner,
            cards_in_play,
            card_id,
            PersonalCardRevealChoiceEffect(effect_value),
            persuasion=persuasion,
        )
    )


def reveal_choice_providers() -> tuple[ChoiceProvider, ...]:
    """The providers of a ``REVEAL_CHOICE`` frame's actions, in offer order.

    Engineered Miracle's lives in ``rules.acquisition``, which imports this
    module, so it is read at call time.
    """

    from dune_imperium.rules.acquisition import (
        legal_reveal_command_acquisition_actions,
    )

    return (
        legal_reveal_command_acquisition_actions,
        legal_reveal_persuasion_or_contract_actions,
        legal_corrinth_city_reveal_actions,
        legal_contract_reveal_choice_actions,
        legal_reveal_card_trash_actions,
        legal_reveal_spy_actions,
        legal_reveal_influence_exchange_actions,
        legal_reveal_influence_gain_actions,
        legal_reveal_sandworm_actions,
        legal_reveal_spice_influence_actions,
        legal_reveal_troop_retreat_actions,
        legal_reveal_influence_loss_actions,
        legal_reveal_troop_move_actions,
        legal_reveal_troop_sacrifice_actions,
    )


def _entry_state(state: GameState, player: int, entry: PendingChoice) -> GameState:
    """``state`` with the entry's ``REVEAL_CHOICE`` frame on top of the stack.

    The frame its choice opens on (``_build_reveal_choice_frame``), so the
    frame's own providers say what the entry offers, as
    ``graft_boxes.state_with_active_box`` does for a grafted box.
    """

    card_id, effect = entry
    frame = _build_reveal_choice_frame(
        state.round_number, player, card_id, PersonalCardRevealChoiceEffect(effect)
    )
    return replace(state, decision_stack=(*state.decision_stack, frame))


type EntryRows = tuple[tuple[PendingChoice, tuple[DomainAction, ...]], ...]

# The last few states' pending rows, by identity: the Reveal frame's
# providers, ``finish_reveal`` and the page ask for the same state's rows
# several times in one step.
_ROWS_CACHE: list[tuple[GameState, int, EntryRows]] = []
_ROWS_CACHE_SIZE: Final = 8


def pending_choice_entries(state: GameState, player: int) -> EntryRows | None:
    """Each pending choice of ``player``'s Reveal with the actions it offers now.

    None unless ``player``'s Reveal frame is on top. An entry whose card
    left play (trashed by another effect, OQ-022) or whose printed
    condition fails now (``_reveal_choice_effect_is_available``) offers
    nothing; so does one whose condition holds with nothing to choose (a
    Spy icon with no free post).
    """

    if owned_top_frame(state, FrameKind.REVEAL, player) is None:
        return None
    for cached, seat, rows in _ROWS_CACHE:
        if cached is state and seat == player:
            return rows
    context = frame_context(state.decision_stack[-1])
    entries = pending_reveal_choices(context)
    result: EntryRows = ()
    if entries:
        available = _available_pending_choices(state, player, context)
        providers = reveal_choice_providers()
        found: list[tuple[PendingChoice, tuple[DomainAction, ...]]] = []
        for entry in entries:
            if entry not in available:
                found.append((entry, ()))
                continue
            virtual = _entry_state(state, player, entry)
            found.append(
                (
                    entry,
                    tuple(
                        action
                        for provider in providers
                        for action in provider(virtual, player)
                    ),
                )
            )
        result = tuple(found)
    _ROWS_CACHE.append((state, player, result))
    if len(_ROWS_CACHE) > _ROWS_CACHE_SIZE:
        del _ROWS_CACHE[0]
    return result


def pending_choice_rows(
    state: GameState, player: int, provider: ChoiceProvider
) -> tuple[DomainAction, ...] | None:
    """``provider``'s actions for ``player``'s pending Reveal choices.

    None unless ``player``'s Reveal frame is on top: the provider then reads
    its own ``REVEAL_CHOICE`` frame. With the Reveal frame on top, each
    pending entry that is available now is asked on its own frame
    (``_entry_state``); an action two interchangeable entries offer appears
    once.
    """

    if owned_top_frame(state, FrameKind.REVEAL, player) is None:
        return None
    context = frame_context(state.decision_stack[-1])
    available = _available_pending_choices(state, player, context)
    rows: dict[DomainAction, None] = {}
    for entry in pending_reveal_choices(context):
        if entry in available:
            rows.update(
                dict.fromkeys(provider(_entry_state(state, player, entry), player))
            )
    return tuple(rows)


def legal_pending_reveal_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every pending Reveal choice that can be taken now, on the Reveal frame.

    "You may resolve Reveal effects in any order you like", and Persuasion
    may be used to acquire before, between or after them [Main p. 12]: each
    entry offers what its ``REVEAL_CHOICE`` frame would, beside the
    purchases, gains and Plots, in pending order (OQ-095 (7) addition, user
    ruling 2026-10-14). An optional choice offers no refusal; leaving it
    unused lapses it at ``finish_reveal``. Identical actions of
    interchangeable entries (two copies of one card) appear once.
    """

    by_entry = pending_choice_entries(state, player)
    if not by_entry:
        return ()
    return tuple(dict.fromkeys(action for _, rows in by_entry for action in rows))


def _open_pending(
    state: GameState, action: DomainAction, provider: ChoiceProvider
) -> GameState:
    """``state`` with the pending choice ``action`` takes open on its frame.

    Unchanged unless the actor's Reveal frame is on top. The first pending
    entry (in pending order) whose frame offers ``action`` leaves the list
    and its ``REVEAL_CHOICE`` frame is pushed, so the frame's own handler
    resolves the action and closes it, or keeps it on top for a step that
    must follow at once (a Spy recalled for its placement).
    """

    frame = owned_top_frame(state, FrameKind.REVEAL, action.actor)
    if frame is None or action.action_id not in REVEAL_CHOICE_ACTION_IDS:
        return state
    context = frame_context(frame)
    entries = pending_reveal_choices(context)
    available = _available_pending_choices(state, action.actor, context)
    for index, entry in enumerate(entries):
        if entry not in available:
            continue
        opened = _entry_state(state, action.actor, entry)
        if action not in provider(opened, action.actor):
            continue
        context[_PENDING_CHOICES_KEY] = _encode_pending(
            (*entries[:index], *entries[index + 1 :])
        )
        return replace(
            state,
            decision_stack=(
                *state.decision_stack[:-1],
                with_context(frame, context),
                opened.decision_stack[-1],
            ),
        )
    return state


def _every_choice_action(state: GameState, player: int) -> tuple[DomainAction, ...]:
    return tuple(
        action
        for provider in reveal_choice_providers()
        for action in provider(state, player)
    )


def open_pending_reveal_choice(state: GameState, action: DomainAction) -> GameState:
    """``state`` with the pending Reveal choice ``action`` takes on top.

    The step every Reveal choice handler takes first (``_open_pending``):
    unchanged unless the actor's Reveal frame is on top and a pending entry
    offers ``action``.
    """

    return _open_pending(state, action, _every_choice_action)


def mandatory_choice_is_pending(state: GameState, player: int) -> bool:
    """Whether a mandatory pending Reveal choice offers something now.

    A Spy icon with a Spy in supply (OQ-057 (14)), a printed "-OR-" choice
    (Desert Power before its branch, OQ-069) or an Influence gain must be
    answered before the Reveal ends (its record is marked mandatory,
    ``reveal_choice_abilities``); one
    whose condition fails now, that has nothing to choose, or whose card
    another effect trashed (OQ-022), does not hold the end and lapses with
    it.
    """

    by_entry = pending_choice_entries(state, player) or ()
    return any(
        rows and not reveal_choice_is_optional(PersonalCardRevealChoiceEffect(effect))
        for (_, effect), rows in by_entry
    )


def waiting_deferred_choices(
    state: GameState,
    player: int,
) -> tuple[PendingChoice, ...]:
    """Return ``player``'s pending Reveal choices that offer nothing now.

    Each is a ``(card instance, effect)`` entry of the open Reveal frame's
    pending choices whose printed condition fails now (or that has nothing
    to choose); a later choice of the owner can still open it, and it lapses
    at ``finish_reveal`` if it never does [Main p. 12]. One whose card
    another effect trashed never opens again (OQ-022). The page shows these
    greyed out (``display.unavailable``, user request 2026-09-29). Empty
    unless ``player``'s Reveal is on top.
    """

    by_entry = pending_choice_entries(state, player) or ()
    return tuple(entry for entry, rows in by_entry if not rows)


def waiting_choice_action(player: int, effect: str) -> DomainAction:
    """The row that stands for a waiting pending Reveal choice on the page.

    Never legal: ``resume_reveal_choice`` brought a deferred choice back
    before codec v147, and its catalog row stays as a never-legal one. The
    page greys it out with its prompt (``display.unavailable``).
    """

    return DomainAction(
        action_id="resume_reveal_choice",
        actor=player,
        arguments=(("effect", effect),),
    )


def _apply_late_reveal_frame_update(
    frames: tuple[DecisionFrame, ...],
    card_id: str,
    persuasion_delta: int,
    sword_delta: int,
    *,
    counts_toward_combat: bool,
) -> tuple[DecisionFrame, ...]:
    """Record one late-arriving card on the Reveal frame, wherever it sits.

    A chance or choice frame can be layered above the Reveal frame when a
    card lands in hand mid-Reveal (a Personal-draw reshuffle chance, or the
    Intrigue choice frame an acquisition slot resolves under), so this scans
    for it by kind rather than assuming the stack top, mirroring
    ``replace_top_frame``'s single-frame replacement.
    """

    for index in range(len(frames) - 1, -1, -1):
        if frames[index].kind != FrameKind.REVEAL:
            continue
        context = dict(frames[index].context)
        count = context_int(context, "revealed_card_count", owner="Reveal frame")
        context[f"revealed_card_{count:03d}"] = card_id
        context["revealed_card_count"] = count + 1
        if persuasion_delta:
            generated = _generated_persuasion(context)
            context["persuasion"] = (
                context_int(context, "persuasion", owner="Reveal frame")
                + persuasion_delta
            )
            if generated is not None:
                context[GENERATED_PERSUASION_KEY] = generated + persuasion_delta
        if sword_delta:
            context["sword_strength"] = (
                context_int(context, "sword_strength", owner="Reveal frame")
                + sword_delta
            )
            if counts_toward_combat:
                context["strength"] = (
                    context_int(context, "strength", owner="Reveal frame") + sword_delta
                )
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("late-reveal card is missing its Reveal frame")


def _late_reveal_one_card(
    state: GameState,
    player: int,
    card_id: str,
) -> RuleResult:
    """Immediately reveal one card that just entered ``player``'s hand.

    A card drawn or acquired to hand during a player's own Reveal turn is
    revealed at once and used in that same Reveal turn [FAQ p. 3]: it moves
    to ``in_play``, grants its own Reveal contribution evaluated over the
    now-larger revealed set, adds the increment its arrival causes to other
    already-revealed cards' cross-scaling effects (those still in play), and
    adds its own choice effects to the Reveal's pending choices. Amounts
    already granted to other cards are final and are never recomputed here,
    only added to.
    """

    owner = state.players[player]
    if card_id not in owner.hand:
        raise RuntimeError("late-reveal card is not in the owner's hand")
    card = personal_card_for_instance(card_id)
    context = _reveal_frame_context(state.decision_stack)
    previously_revealed_ids = tuple(
        context_str(context, f"revealed_card_{index:03d}", owner="Reveal frame")
        for index in range(
            context_int(context, "revealed_card_count", owner="Reveal frame")
        )
    )

    next_owner = replace(
        owner,
        hand=tuple(candidate for candidate in owner.hand if candidate != card_id),
        in_play=(*owner.in_play, card_id),
    )
    cards_in_play = counted_in_play(next_owner)
    completed_contracts = len(next_owner.completed_contract_ids)
    revealed_cards = tuple(
        personal_card_for_instance(instance_id)
        for instance_id in (*previously_revealed_ids, card_id)
    )

    frame_persuasion = _frame_generated_persuasion(state.decision_stack)
    # Command (6+) counts the card's own Persuasion [Bloodlines p. 5]; the
    # effects paid here are recorded on the same total below, so
    # grant_late_reveal_effects never pays them a second time. Desert Power's
    # 2 wait for its own Reveal choice like any other card (user rulings
    # 2026-09-26 and 2026-09-30, with or without Maker Hooks), so they are
    # excluded here too.
    card_persuasion = _card_reveal_persuasion(card)
    command_persuasion = (
        None if frame_persuasion is None else frame_persuasion + card_persuasion
    )
    eligible = _eligible_reveal_effects(
        next_owner, cards_in_play, card_id, card, persuasion=command_persuasion
    )
    persuasion_gain = card_persuasion + sum(
        _reveal_effect_persuasion(
            effect, revealed_cards, completed_contracts, _in_play_cards(next_owner)
        )
        for effect in eligible
    )
    own_strength = card.reveal_strength + sum(
        _reveal_effect_strength(effect, revealed_cards) for effect in eligible
    )
    # Leadership's count, for this card and for one revealed earlier, is
    # topped up by _count_leadership_swords once the card is recorded.
    sword_delta = own_strength

    persuasion_increment = 0
    for other_id in previously_revealed_ids:
        if other_id not in next_owner.in_play:
            # A Stilgar, The Devoted trashed earlier in the Reveal gains
            # nothing from a Fremen card arriving after it: "you can't receive
            # or activate an effect from a card that is already trashed"
            # (designer ruling, OQ-022). What it paid before stays paid.
            continue
        other_card = personal_card_for_instance(other_id)
        for effect in other_card.reveal_effects:
            # The arriving card is both revealed and in play, so either
            # count grows by it.
            counted_faction = effect.per_revealed_faction or effect.per_in_play_faction
            if counted_faction is None:
                continue
            if not _reveal_effect_is_eligible(
                next_owner,
                cards_in_play,
                other_id,
                other_card,
                effect,
                persuasion=frame_persuasion,
            ):
                continue
            if Faction(counted_faction.value) in card.factions:
                persuasion_increment += effect.persuasion
                sword_delta += effect.strength
    persuasion_delta = persuasion_gain + persuasion_increment

    # Troop recruits, Intrigue draws and resources join the Reveal's pending
    # gains so the owner keeps choosing their order [Main p. 12] (OQ-045).
    late_gains: tuple[RevealGain, ...] = tuple(
        entry
        for effect in eligible
        for entry in (
            ("troops", str(effect.recruit_troops), card_id)
            if effect.recruit_troops
            else None,
            ("intrigue", str(effect.draw_intrigue), card_id)
            if effect.draw_intrigue
            else None,
            ("specimens", str(effect.specimens), card_id) if effect.specimens else None,
            ("tleilaxu", str(effect.tleilaxu), card_id) if effect.tleilaxu else None,
            ("research", str(effect.research), card_id) if effect.research else None,
            resource_gain_entry(
                card_id, solari=effect.solari, spice=effect.spice, water=effect.water
            ),
            influence_gain_entry(card_id, effect),
        )
        if entry is not None
    )

    units = next_owner.units_in_conflict
    counts_toward_combat = units > 0
    if counts_toward_combat and sword_delta:
        next_owner = replace(
            next_owner, combat_strength=next_owner.combat_strength + sword_delta
        )

    source = f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=_append_reveal_gains(
            _record_granted_effects(
                _apply_late_reveal_frame_update(
                    state.decision_stack,
                    card_id,
                    persuasion_delta,
                    sword_delta,
                    counts_toward_combat=counts_toward_combat,
                ),
                _granted_entries(
                    (card_id,),
                    (card,),
                    next_owner,
                    cards_in_play,
                    completed_contracts,
                    persuasion=command_persuasion,
                ),
            ),
            late_gains,
        ),
    )
    counted = _count_leadership_swords(next_state, player)
    next_state = counted.state
    guild_spy_events: tuple[GameEvent, ...] = ()
    if card.reveal_acquisition_effect is _GUILD_SPY_EFFECT:
        # A Guild Spy revealed late still reacts to The Spice Must Flow
        # bought earlier in this Reveal (designer ruling, OQ-057).
        reacted = fire_guild_spy_on_spice_must_flow(next_state, player, acquired=False)
        next_state = reacted.state
        guild_spy_events = reacted.events
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:late_reveal",
            kind="personal_card_late_revealed",
            payload=(
                ("card_id", card_id),
                ("persuasion", persuasion_delta),
                ("player", player),
                ("strength", sword_delta),
            ),
        )
    ]
    # Its choice effects join the Reveal's pending choices after the ones
    # already there, offered with them whenever their condition holds
    # (OQ-095 (7) addition): no frame opens, so a frame above the Reveal
    # frame (the Intrigue choice that drew the card) stays on top.
    next_state = replace(
        next_state,
        decision_stack=_queue_pending_choices(
            next_state.decision_stack,
            tuple(
                (card_id, choice_effect.value)
                for choice_effect in card.reveal_choice_effects
            ),
        ),
    )
    # The card is used this turn like a card revealed at the start [FAQ p. 3],
    # so its recorded effects also trash it or open the Combat icon, as in
    # begin_reveal_turn (after Leadership has counted it, as in
    # grant_late_reveal_effects).
    self_events: list[GameEvent] = []
    for effect in eligible:
        if effect.trashes_self and card_id in next_state.players[player].in_play:
            # Bombast: "Command (6+): 3 Solari and trash this card".
            trashed = trash_personal_card(
                next_state, player, card_id, source=f"{source}:late_trash"
            )
            trashed = credit_trash_recruits(trashed, player)
            next_state = trashed.state
            self_events.extend(trashed.events)
        if effect.grants_combat_icon:
            # Holy War's Fremen Bond, Ruthless Leadership's Command: deploy
            # as though at a Combat space [Bloodlines p. 5].
            next_state = grant_combat_icon(next_state, player)

    return RuleResult(
        state=next_state,
        events=(*events, *counted.events, *guild_spy_events, *self_events),
    )


def reveal_late_arrivals(
    state: GameState,
    player: int,
    card_ids: tuple[str, ...],
) -> RuleResult:
    """Immediately reveal personal cards that just entered a Reveal hand.

    A card drawn or acquired to hand during the owner's own Reveal turn is
    revealed and used at once [FAQ p. 3] rather than withheld to the next
    round. Cards are processed one at a time in the given (draw) order, so
    a later card's cross-scaling effects see every card revealed before it.
    """

    working = state
    events: list[GameEvent] = []
    for card_id in card_ids:
        step = _late_reveal_one_card(working, player, card_id)
        working = step.state
        events.extend(step.events)
    return RuleResult(state=working, events=tuple(events))


def legal_reveal_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Return the always-available Reveal choice for the current turn owner."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return ()
    if owned_top_frame(state, FrameKind.TURN, player) is None:
        return ()
    return (DomainAction(action_id="reveal_turn", actor=player),)


def begin_reveal_turn(state: GameState, action: DomainAction) -> RuleResult:
    """Reveal the hand and calculate its basic Persuasion and strength."""

    if action not in legal_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal turn")
    returned = _return_chairdog_cards(state, action.actor)
    revealed_turn = _begin_reveal_turn(returned.state, action)
    return RuleResult(
        state=revealed_turn.state, events=(*returned.events, *revealed_turn.events)
    )


def _return_chairdog_cards(state: GameState, player: int) -> RuleResult:
    """Chairdog: "At the start of your Reveal turn, return the other grafted
    card from play to your hand" [card face]; the card is then revealed with
    the hand. A card that already left play is simply forgotten."""

    owner = state.players[player]
    if not owner.chairdog_return_card_ids:
        return RuleResult(state=state)
    returned = tuple(
        card_id
        for card_id in owner.chairdog_return_card_ids
        if card_id in owner.in_play
    )
    next_owner = replace(
        owner,
        in_play=tuple(card_id for card_id in owner.in_play if card_id not in returned),
        hand=(*owner.hand, *returned),
        hand_public=(*owner.hand_public, *returned),
        chairdog_return_card_ids=(),
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=tuple(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:"
                    f"chairdog_return:{card_id}"
                ),
                kind="card_returned_to_hand",
                payload=(("card_id", card_id), ("player", player)),
            )
            for card_id in returned
        ),
    )


def _begin_reveal_turn(state: GameState, action: DomainAction) -> RuleResult:
    owner = state.players[action.actor]
    revealed = owner.hand
    cards = tuple(personal_card_for_instance(card_id) for card_id in revealed)
    # The cards that count as in play: the Row card a Usurp turn borrowed
    # is trashed when that Agent turn ends, so it never reaches a Reveal,
    # and it would not count if it did (OQ-054, ``counted_in_play``).
    cards_in_play = (*counted_in_play(owner), *revealed)
    in_play_cards = (*_in_play_cards(owner), *cards)

    def eligible_effects(
        persuasion: int | None,
    ) -> tuple[tuple[str, PersonalCardRevealEffect], ...]:
        return tuple(
            (card_id, effect)
            for card_id, card in zip(revealed, cards, strict=True)
            for effect in _eligible_reveal_effects(
                owner, cards_in_play, card_id, card, persuasion=persuasion
            )
        )

    # Sardaukar Commander Skills pay their Reveal-turn bonus once while a
    # Commander is in the Conflict [Bloodlines p. 4] [Skill tile faces].
    active_skills = (
        tuple(skill_for_instance(instance_id) for instance_id in owner.skill_ids)
        if owner.commanders_conflict > 0
        else ()
    )

    def total_persuasion(
        effects: tuple[tuple[str, PersonalCardRevealEffect], ...],
    ) -> int:
        total = sum(_card_reveal_persuasion(card) for card in cards) + sum(
            _reveal_effect_persuasion(
                effect, cards, len(owner.completed_contract_ids), in_play_cards
            )
            for _, effect in effects
        )
        if owner.high_council:
            total += 2
        if "assembly_hall" in owner.agent_locations:
            total += 1
        # Persuasion generated in this Reveal turn from outside the cards
        # counts toward "Command (6+)" too [Bloodlines p. 5]: Charismatic,
        # Navigation card 3 from slot 4 ("during each of your Reveal turns,
        # 1 Persuasion") and Self-Destroying Messages ("Reveal Turn: 1
        # Persuasion").
        total += sum(skill.reveal_persuasion for skill in active_skills)
        total += owner.reveal_persuasion_bonus
        # Tleilaxu Puppet: "Gain 1 Persuasion during your Reveal turn this
        # round" [card face].
        total += owner.reveal_persuasion_round_bonus
        if has_tech(owner.tech_ids, TechAbility.REVEAL_PERSUASION):
            total += 1
        return total

    # "Command (6+)" effects open on the Persuasion the other effects
    # generate [Bloodlines p. 5]; they never add Persuasion themselves.
    persuasion = total_persuasion(eligible_effects(None))
    reveal_effects = eligible_effects(persuasion)
    persuasion = total_persuasion(reveal_effects)
    # Tech tiles with "Reveal Turn: Command (6+)" lines pay once the total
    # is known; a later Command opening pays them late [Bloodlines p. 5].
    tech_granted = tuple(
        tech_id
        for tech_id, ability in _COMMAND_TECH
        if persuasion >= COMMAND_PERSUASION and has_tech(owner.tech_ids, ability)
    )
    tech_sword = 2 if "training_depot" in tech_granted else 0

    card_strengths = tuple(
        (
            card_id,
            card.reveal_strength
            + sum(
                _reveal_effect_strength(effect, cards)
                for effect_card_id, effect in reveal_effects
                if effect_card_id == card_id
            ),
        )
        for card_id, card in zip(revealed, cards, strict=True)
    )
    # Leadership counts the other sword cards revealed now; a card that
    # provides swords later (a Reveal choice, a late arrival) is added by
    # _count_leadership_swords, which reads the count recorded here.
    other_sword_cards = {
        card_id: sum(
            strength > 0 for other_id, strength in card_strengths if other_id != card_id
        )
        for card_id in revealed
    }
    sword_strength = (
        sum(strength for _, strength in card_strengths)
        + sum(
            effect.strength_per_other_sword_card * other_sword_cards[effect_card_id]
            for effect_card_id, effect in reveal_effects
        )
        + tech_sword
    )
    # One formula for the units' share (the engine keeps combat_strength
    # equal to it after every step before the Reveal); the Reveal adds the
    # revealed swords, and without a unit there is no strength [Main p. 12].
    units = owner.units_in_conflict
    # The Skill strength already folded into the running value stays.
    strength = (
        units_strength(owner) + sword_strength + owner.skill_strength_applied
        if units > 0
        else 0
    )
    next_owner = owner
    # Panopticon: "Reveal Turn: a Spy and a troop" [Panopticon Tech tile];
    # the Spy placement opens below.
    panopticon = has_tech(owner.tech_ids, TechAbility.PANOPTICON)
    # Troop recruits, Intrigue draws and resource gains wait for the owner's
    # order (OQ-045).
    # A troop recruited earlier this same turn (a Plot Intrigue played before
    # placing an Agent, or an acquire-box troop resolved mid-turn) still
    # joins this Reveal's Combat-icon deployment: "이번 turn에 recruit한
    # 유닛 전부와 garrison에서 최대 두 개 ... Reveal turn에서도 쓸 수
    # 있다" [Bloodlines pp. 5, 12] and "그 turn에 어떤 출처에서
    # recruit했든 새 troop은 Conflict에 deploy할 수 있다" [Main p. 10]
    # [FAQ p. 4] (docs/rules/player-turns.md:137). The turn frame this
    # Reveal is about to replace carries the count in, mirroring
    # ``agent_turn._troops_recruited_before_placement``.
    turn_context = dict(state.decision_stack[-1].context)
    reveal_troops_recruited = turn_context.get("troops_recruited", 0)
    if isinstance(reveal_troops_recruited, bool) or not isinstance(
        reveal_troops_recruited, int
    ):
        raise RuntimeError("turn frame has an invalid recruit count")
    # A Commander recruited before the Reveal keeps its own deploy slot
    # (OQ-070), carried apart from the troops.
    carried_commanders = recruited_commander_count(
        turn_context, COMMANDERS_RECRUITED_KEY
    )
    # A Harkonnen Advisor troop kept undeployable that turn stays so in the
    # Reveal (OQ-038, OQ-062); ``legal_reveal_deployments`` already reads
    # this key off the Reveal frame's context.
    carried_undeployable = undeployable_troops(turn_context)
    resource_gains = (
        *(
            resource_gain_entry(
                card_id, solari=effect.solari, spice=effect.spice, water=effect.water
            )
            for card_id, effect in reveal_effects
        ),
        *(
            resource_gain_entry(f"skill:{skill.skill_id}", spice=skill.reveal_spice)
            for skill in active_skills
        ),
        resource_gain_entry(
            "tech:delivery_bay", solari=2 if "delivery_bay" in tech_granted else 0
        ),
    )
    pending_gains: tuple[RevealGain, ...] = (
        *(
            ("troops", str(effect.recruit_troops), card_id)
            for card_id, effect in reveal_effects
            if effect.recruit_troops
        ),
        *((("troops", "1", "tech:panopticon"),) if panopticon else ()),
        # Hardy: "Reveal Turn: [troop]" [Hardy Skill tile] [Main p. 20].
        *(
            ("troops", str(skill.reveal_troops), f"skill:{skill.skill_id}")
            for skill in active_skills
            if skill.reveal_troops
        ),
        *(
            ("intrigue", str(effect.draw_intrigue), card_id)
            for card_id, effect in reveal_effects
            if effect.draw_intrigue
        ),
        # Specimens come from the supply like troops [Immortality p. 8], so
        # their timing is the owner's too (OQ-045).
        *(
            ("specimens", str(effect.specimens), card_id)
            for card_id, effect in reveal_effects
            if effect.specimens
        ),
        *(
            ("tleilaxu", str(effect.tleilaxu), card_id)
            for card_id, effect in reveal_effects
            if effect.tleilaxu
        ),
        *(
            ("research", str(effect.research), card_id)
            for card_id, effect in reveal_effects
            if effect.research
        ),
        *(entry for entry in resource_gains if entry is not None),
        *(
            entry
            for entry in (
                influence_gain_entry(card_id, effect)
                for card_id, effect in reveal_effects
            )
            if entry is not None
        ),
    )
    next_owner = replace(
        next_owner,
        hand=(),
        in_play=(*owner.in_play, *revealed),
        combat_strength=strength,
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    granted_at_start = _granted_entries(
        revealed,
        cards,
        owner,
        cards_in_play,
        len(owner.completed_contract_ids),
        persuasion=persuasion,
    )
    for card_id, card in zip(revealed, cards, strict=True):
        for index, effect in enumerate(card.reveal_effects):
            key = f"{card_id}#{index}"
            if effect.strength_per_other_sword_card and key in granted_at_start:
                granted_at_start[key] = other_sword_cards[card_id]
    context: list[tuple[str, ActionValue]] = [
        (_GRANTED_EFFECTS_KEY, _encode_granted(granted_at_start)),
        # Combat-icon deployment during the Reveal [Bloodlines p. 5]: open
        # when an icon arrived earlier this turn, counting this Reveal's
        # recruits toward the limit.
        ("combat_deployment", owner.combat_icon_turn),
        ("optional_sword_strength", 0),
        ("persuasion", persuasion),
        (GENERATED_PERSUASION_KEY, persuasion),
        ("reveal_troops_recruited", reveal_troops_recruited),
        (REVEAL_GAINS_KEY, _encode_gains(pending_gains)),
        ("reveal_units_deployed", 0),
        ("revealed_card_count", len(revealed)),
        ("strength", strength),
        ("sword_strength", sword_strength),
        (_TECH_GRANTED_KEY, ",".join(tech_granted)),
        (_SKILL_GRANTED_KEY, ",".join(skill.skill_id for skill in active_skills)),
        ("turn_owner", action.actor),
    ]
    if turn_context.get(TECH_ACQUIRE_PENDING_KEY):
        context.append(
            (TECH_ACQUIRE_PENDING_KEY, turn_context[TECH_ACQUIRE_PENDING_KEY])
        )
    if carried_undeployable:
        context.append(("undeployable_troops", carried_undeployable))
    if carried_commanders:
        context.append((REVEAL_COMMANDERS_RECRUITED_KEY, carried_commanders))
    context.extend(
        (f"revealed_card_{index:03d}", card_id)
        for index, card_id in enumerate(revealed)
    )
    reveal_frame = DecisionFrame(
        kind=FrameKind.REVEAL,
        frame_id=f"round:{state.round_number}:player:{action.actor}:reveal",
        decision=PlayerDecision(
            owner=action.actor,
            prompt="Resolve Reveal effects and acquire cards",
        ),
        context=tuple(sorted(context)),
    )
    # Every choice effect of the revealed cards waits on the Reveal frame in
    # hand order, offered there with the purchases and gains whenever its
    # printed condition holds (OQ-095 (7) addition, user ruling 2026-10-14):
    # Reveal effects resolve in any order the owner likes [Main p. 12], and
    # one whose condition fails now can still open after a later choice.
    reveal_context = frame_context(reveal_frame)
    reveal_context[_PENDING_CHOICES_KEY] = _encode_pending(
        tuple(
            (card_id, choice_effect.value)
            for card_id, card in zip(revealed, cards, strict=True)
            for choice_effect in card.reveal_choice_effects
        )
    )
    reveal_frame = with_context(reveal_frame, reveal_context)
    # Forbidden Weapons' "Reveal Turn: You must choose" and Panopticon's Spy
    # wait on the Reveal frame for the owner's order (OQ-044).
    reveal_context[TECH_PENDING_KEY] = ",".join(
        (
            *(
                ("forbidden_weapons",)
                if has_tech(owner.tech_ids, TechAbility.FORBIDDEN_WEAPONS)
                else ()
            ),
            *(("panopticon",) if panopticon else ()),
        )
    )
    reveal_frame = with_context(reveal_frame, reveal_context)
    next_state = replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], reveal_frame),
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:reveal",
        kind="reveal_started",
        payload=(
            ("cards", len(revealed)),
            ("persuasion", persuasion),
            ("player", action.actor),
            ("strength", strength),
        ),
    )
    # The revealed hand, for the tables to show (report-only: the engine
    # keeps it out of the state, ``UprisingRulesEngine``). Revealed cards
    # are public from here on [Main p. 12]; the view lists them in play.
    shown = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:revealed",
        kind="cards_revealed",
        payload=(("card_ids", ",".join(revealed)), ("player", action.actor)),
    )
    events: list[GameEvent] = [event, shown]
    for card_id, effect in reveal_effects:
        if effect.trashes_self:
            # Bombast: "3 Solari and trash this card" — the card leaves play
            # once its Command effect pays out.
            trashed = trash_personal_card(
                next_state, action.actor, card_id, source=f"{event.event_id}:{card_id}"
            )
            trashed = credit_trash_recruits(trashed, action.actor)
            next_state = trashed.state
            events.extend(trashed.events)
        if effect.grants_combat_icon:
            # Holy War's Fremen Bond: this Reveal may deploy as though at a
            # Combat space [Bloodlines p. 5].
            next_state = grant_combat_icon(next_state, action.actor)
    events.extend(
        GameEvent(
            event_id=f"{event.event_id}:tech:{tech_id}",
            kind="tech_reveal_bonus",
            payload=(
                ("player", action.actor),
                ("solari", 2 if tech_id == "delivery_bay" else 0),
                ("strength", 2 if tech_id == "training_depot" else 0),
                ("tech_id", tech_id),
            ),
        )
        for tech_id in tech_granted
    )
    events.extend(
        GameEvent(
            event_id=f"{event.event_id}:skill:{skill.skill_id}",
            kind="skill_reveal_bonus",
            payload=(
                ("persuasion", skill.reveal_persuasion),
                ("player", action.actor),
                ("skill_id", skill.skill_id),
                ("spice", skill.reveal_spice),
                ("troops", skill.reveal_troops),
            ),
        )
        for skill in active_skills
        if skill.reveal_persuasion or skill.reveal_spice or skill.reveal_troops
    )
    return RuleResult(state=next_state, events=tuple(events))


REVEAL_CONTEXT_KEYS = frozenset(
    {"persuasion", "revealed_card_count", "strength", "turn_owner"}
)


def current_reveal_context(state: GameState) -> dict[str, ActionValue]:
    """Return and validate the current Reveal resolution frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Reveal turn")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.REVEAL or not isinstance(frame.decision, PlayerDecision):
        raise ValueError("the current decision is not a Reveal turn")
    context = dict(frame.context)
    if not REVEAL_CONTEXT_KEYS.issubset(context):
        raise ValueError("the Reveal frame is missing context")
    return context


def legal_finish_reveal_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the explicit action that ends the current Reveal turn."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        context = current_reveal_context(state)
    except ValueError:
        return ()
    owner = context["turn_owner"]
    if isinstance(owner, bool) or not isinstance(owner, int) or owner != player:
        return ()
    if mandatory_choice_is_pending(state, player):
        # A mandatory Reveal choice that offers something now must be
        # answered; an optional one, or one whose condition fails now,
        # lapses when the Reveal ends (OQ-095 (7) addition).
        return ()
    if reveal_pending_gains(context):
        # Every troop recruit and Intrigue draw must be taken (OQ-045).
        return ()
    if reveal_subcommittee_offer(state, player) is not None:
        # Arrakeen Scouts: Corrinth City's seat must join a subcommittee or
        # decline before the Reveal ends, as the High Council board space's
        # choice must be answered before its Agent turn ends; nothing lapses
        # unasked (user rulings 2026-09-30, OQ-076). Declining is always
        # offered, so this never blocks the turn.
        return ()
    pending_tech = tech_reveal_pending(context)
    if "forbidden_weapons" in pending_tech or "panopticon" in pending_tech:
        # Forbidden Weapons must be chosen; Panopticon's Spy must be taken
        # (OQ-044), and its placement window offers only the decline when no
        # Spy can reach a post, so nothing lapses unasked.
        return ()
    if context.get(TECH_ACQUIRE_PENDING_KEY):
        return ()
    if owes_track_spy(state, player):
        # The Emperor track's Influence 4 Spy waits in the turn and must be
        # placed before it ends (user ruling 2026-10-04, overriding OQ-057
        # (15)); its placement window, like Panopticon's, offers only the
        # decline when nothing can be placed.
        return ()
    if owes_held_draw(state, player):
        # A triggered draw waits as its own step and is taken before the
        # Reveal ends (user ruling 2026-10-10, OQ-106).
        return ()
    return (DomainAction(action_id="finish_reveal", actor=player),)


def finish_reveal_turn(state: GameState, action: DomainAction) -> RuleResult:
    """Clean up in-play cards and advance or enter Combat."""

    if owes_track_spy(state, action.actor):
        # Placed in any order, but before the turn ends (user ruling
        # 2026-10-04, overriding OQ-057 (15)).
        raise RuntimeError("a Reveal turn cannot end over an owed track Spy")
    if owes_held_draw(state, action.actor):
        raise RuntimeError("a Reveal turn cannot end over a waiting draw")
    if action not in legal_finish_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal cleanup")
    # Every choice still pending lapses here: an optional one left unused,
    # one whose printed condition never came true (OQ-095 (7) addition, user
    # ruling 2026-10-14).
    lapsed_events = tuple(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"reveal_card:{card_id}:{effect}:lapsed"
            ),
            kind="reveal_choice_lapsed",
            payload=(
                ("card_id", card_id),
                ("effect", effect),
                ("player", action.actor),
            ),
        )
        for card_id, effect in pending_reveal_choices(
            frame_context(state.decision_stack[-1])
        )
    )
    # Face-up Intrigue whose window was this Reveal turn expires with it.
    expired = expire_reveal_faceup_intrigue(state, action.actor)
    working = expired.state
    owner = working.players[action.actor]
    # A set-aside Imperium card not acquired by the end of this Reveal turn
    # leaves the game [FAQ p. 3].
    removed = owner.imperium_set_aside
    removal_events = tuple(
        GameEvent(
            event_id=(
                f"round:{working.round_number}:player:{action.actor}:"
                f"imperium_removed:{instance_id}"
            ),
            kind="imperium_card_removed",
            payload=(("instance_id", instance_id), ("player", action.actor)),
        )
        for instance_id in removed
    )
    if removed:
        working = replace(
            working, imperium_removed=(*working.imperium_removed, *removed)
        )
    # A Contract icon that never found a token it could take lapses with the
    # turn, without the two-Solari conversion (OQ-059).
    held_contracts = owner.held_contract_icons
    if held_contracts:
        lapsed_events = (
            *lapsed_events,
            GameEvent(
                event_id=(
                    f"round:{working.round_number}:player:{action.actor}:"
                    f"finish_reveal:contract_icons_fizzled:{held_contracts}"
                ),
                kind="contract_icons_fizzled",
                payload=(("count", held_contracts), ("player", action.actor)),
            ),
        )
    next_owner = replace(
        owner,
        has_revealed=True,
        discard_pile=(*owner.discard_pile, *owner.in_play),
        in_play=(),
        imperium_set_aside=(),
        held_contract_icons=0,
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in working.players
    )
    next_player = _next_unrevealed_player(players, action.actor)
    if next_player is None:
        phase = GamePhase.COMBAT
        decision_stack = working.decision_stack[:-1]
    else:
        phase = GamePhase.PLAYER_TURNS
        players = reset_turn_counters(players, next_player)
        decision_stack = (
            *working.decision_stack[:-1],
            DecisionFrame(
                kind=FrameKind.TURN,
                frame_id=f"round:{working.round_number}:turn:{next_player}",
                decision=PlayerDecision(
                    owner=next_player,
                    prompt="Choose an Agent turn or Reveal turn",
                ),
                context=(
                    ("round", working.round_number),
                    ("turn_owner", next_player),
                ),
            ),
        )
    next_state = replace(
        working,
        phase=phase,
        players=players,
        reveal_order=(*working.reveal_order, action.actor),
        decision_stack=decision_stack,
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:reveal_finished",
        kind="reveal_finished",
        payload=(("player", action.actor),),
    )
    return RuleResult(
        state=next_state,
        events=(
            *lapsed_events,
            *expired.events,
            *removal_events,
            event,
        ),
    )


def _next_unrevealed_player(
    players: tuple[PlayerState, ...],
    owner: int,
) -> int | None:
    for offset in range(1, len(players) + 1):
        candidate = (owner + offset) % len(players)
        player = players[candidate]
        if not player.has_revealed:
            return candidate
    return None


def add_units_to_reveal(
    state: GameState,
    player: int,
    *,
    troops: int = 0,
    sandworms: int = 0,
    commanders: int = 0,
) -> RuleResult:
    """Record units that entered the Conflict during ``player``'s Reveal turn.

    Mirrors Desert Power: the first units make the revealed sword strength
    count, later units add their own value only [Main p. 13]. A Sardaukar
    Commander is worth 2 like a troop [Bloodlines p. 4].
    """

    owner = state.players[player]
    value = 2 * troops + 3 * sandworms + 2 * commanders
    if value == 0:
        return RuleResult(state=state)
    previous_units = owner.units_in_conflict
    context = _reveal_frame_context(state.decision_stack)
    current_strength = context.get("strength")
    sword_strength = context.get("sword_strength", 0)
    optional_sword_strength = context.get("optional_sword_strength", 0)
    if (
        isinstance(current_strength, bool)
        or not isinstance(current_strength, int)
        or isinstance(sword_strength, bool)
        or not isinstance(sword_strength, int)
        or isinstance(optional_sword_strength, bool)
        or not isinstance(optional_sword_strength, int)
    ):
        raise RuntimeError("Reveal frame has invalid strength")
    strength_delta = (
        value
        if previous_units
        else value + sword_strength + optional_sword_strength - current_strength
    )
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison - troops,
        troops_conflict=owner.troops_conflict + troops,
        sandworms_conflict=owner.sandworms_conflict + sandworms,
        commanders_garrison=owner.commanders_garrison - commanders,
        commanders_conflict=owner.commanders_conflict + commanders,
        combat_strength=owner.combat_strength + strength_delta,
        units_deployed_turn=(
            owner.units_deployed_turn + troops + sandworms + commanders
        ),
    )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=add_reveal_strength(state.decision_stack, strength_delta),
        ),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:reveal:"
                    f"units:{owner.units_in_conflict}"
                ),
                kind="reveal_strength_gained",
                payload=(("amount", strength_delta), ("player", player)),
            ),
        ),
    )
