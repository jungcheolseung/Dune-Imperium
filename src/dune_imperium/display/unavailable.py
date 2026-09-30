"""What a seat cannot take right now, shown greyed out with the reason.

User request 2026-09-29: an option that cannot be taken right now is shown
but not selectable, with the reason, and it becomes selectable as soon as it
can be taken (and the reverse), for the whole game. Arrakeen Scouts choices
already do this (``display.scouts.scouts_choice_lines``); this module does it
for the Reveal shop, Intrigue plays and effects waiting on their condition
(a new High Council seat's subcommittee choice among them).

Display only, under four rules:

- Legality comes only from the engine's legal list. A candidate is dropped
  whenever its action is in that list, and a table ref whenever a legal
  action names it, so a disagreement could only hide a greyed-out row, never
  grey out something the seat may do.
- A reason is worked out only for a candidate that is not legal, from the
  block predicate the legal provider itself uses (``AcquireBlock``,
  ``option_unplayable_reason``, ``intrigue_play_block``,
  ``waiting_deferred_choices``, ``agent_box_is_waiting``,
  ``joinable_subcommittees``), so the two cannot drift.
- No candidate is dry-run: it is described from its arguments alone
  (``shadow_action``). The one dry run is the provider's own:
  ``agent_box_is_waiting`` asks ``agent_card_effect_is_unavailable``, which
  dry-runs the seat's own pending Agent box, cached by state identity (the
  legal list has already asked it for the same state).
- Only the deciding seat's own decision is read, and every reason reads only
  public state and that seat's own zones (a determinized state gives the same
  rows, ``tests/unit/display/test_unavailable_consistency.py``).

Reasons are (English, Korean with ``{term}`` icon tokens, code) triples. The
generic ``NOT_NOW`` and the two text fallbacks ("Cannot pay: ...", "Nothing
to do now: ...") carry ``NOT_NOW_CODE``: no reason here should ever reach
one, and the tests fail on that code.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Final

from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    Cost,
    DeployFromGarrison,
    DiscardFromHand,
    EffectSection,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainInfluence,
    GiveIntrigueToOpponent,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    PayResources,
    PeekTopCard,
    PlaceSpy,
    RecallSpy,
    RedirectSpiesOnTurnSpace,
    RetreatTroops,
    RevealContractsTakeOne,
    Reward,
    SetAsideImperiumRowCard,
    TakeContract,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.display.effect_dsl_text import (
    condition_text,
    cost_text,
    reward_text,
)
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    cost_text_ko,
    reward_text_ko,
)
from dune_imperium.rules.acquisition import (
    AcquireBlock,
    imperium_acquisition_block,
    manipulated_acquisition_block,
    manipulated_cost,
    reserve_acquisition_block,
    reserve_cost,
    revealer_persuasion,
)
from dune_imperium.rules.agent_effect_frame import agent_box_is_waiting
from dune_imperium.rules.combat_deployment import undeployable_troops_this_turn
from dune_imperium.rules.effect_interpreter import (
    OptionBlock,
    OptionUnplayable,
    applicable_sections,
    condition_holds,
    face_up_conflict_card_ids,
    resource_cost,
)
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.influence import influence_amount
from dune_imperium.rules.intrigue import (
    IntriguePlayBlock,
    intrigue_play_block,
    intrigue_window,
)
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.reveal_turn import waiting_deferred_choices
from dune_imperium.rules.spies import legal_gather_intelligence_actions
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    reclaimed_forces_block,
    tleilaxu_acquisition_block,
    tleilaxu_shop_is_open,
)

# --- Reasons: English, Korean (icons as tokens), a code ---------------------

type Reason = tuple[str, str, str]

NOT_NOW_CODE: Final = "unavailable"
NOT_NOW: Final[Reason] = ("Not available now", "지금은 고를 수 없음", NOT_NOW_CODE)


def plural_s(count: int) -> str:
    return "s" if count != 1 else ""


def held_text(held: int) -> tuple[str, str]:
    """The " (you have N)" tail of a reason, in both languages."""

    return f" (you have {held})", f" (보유 {held})"


def resource_reason(resource: str, needed: int, held: int) -> Reason:
    """Short of a resource: 'Needs 3 spice (you have 2)'."""

    en, ko = held_text(held)
    return f"Needs {needed} {resource}{en}", f"{{{resource}:{needed}}} 필요{ko}", "cost"


def troops_reason(where: str, needed: int, held: int) -> Reason:
    """Troops short in the supply or the garrison, or specimens short."""

    en, ko = held_text(held)
    if where == "specimens":
        return (
            f"Needs {needed} specimen{plural_s(needed)}{en}",
            f"{{specimen:{needed}}} 필요{ko}",
            where,
        )
    return (
        f"Needs {needed} troop{plural_s(needed)} in your {where}{en}",
        f"{{{where}}}에 {{troop:{needed}}} 필요{ko}",
        where,
    )


def _persuasion_reason(needed: int, held: int) -> Reason:
    en, ko = held_text(held)
    return (
        f"Needs {needed} Persuasion{en}",
        f"{{persuasion:{needed}}} 필요{ko}",
        "cost",
    )


def _specimen_cost_reason(needed: int, held: int) -> Reason:
    english, korean, _ = troops_reason("specimens", needed, held)
    return english, korean, "cost"


_EMPTY_STACK: Final[Reason] = (
    "The Reserve stack is empty",
    "{reserve} 더미가 비었음",
    "empty",
)
_NO_COST: Final[Reason] = (
    "It has no cost to acquire it with",
    "획득 비용이 없는 카드",
    "no_cost",
)
_BONUS_NOT_IMPLEMENTED: Final[Reason] = (
    "Its acquire bonus is not implemented yet",
    "획득 보너스가 아직 구현되지 않음",
    "not_implemented",
)
_WAITING: Final[Reason] = (
    "Condition not met yet; it lapses if still unmet when the turn ends",
    "아직 조건을 채우지 못함 — 차례가 끝날 때까지 못 채우면 사라짐",
    "waiting",
)
_NO_LINE: Final[Reason] = (
    "None of its lines can be used now",
    "지금 쓸 수 있는 줄이 없음",
    "no_line",
)
_TIMING: Final[Mapping[IntrigueTiming, Reason]] = {
    IntrigueTiming.PLOT: (
        "Plot Intrigue: played during your own turn",
        "음모 책략 카드: 자기 차례에 사용",
        "timing",
    ),
    IntrigueTiming.COMBAT: (
        "Combat Intrigue: played during combat",
        "전투 책략 카드: 전투 중에 사용",
        "timing",
    ),
    IntrigueTiming.ENDGAME: (
        "Endgame Intrigue: played at the end of the game",
        "종료 단계 책략 카드: 게임이 끝날 때 사용",
        "timing",
    ),
}
_TURN_START: Final[Reason] = (
    "Only at the start of your turn",
    "차례를 시작할 때만 사용",
    "timing",
)


def _acquire_reason(block: AcquireBlock, needed: int | None, held: int) -> Reason:
    match block:
        case AcquireBlock.EMPTY:
            return _EMPTY_STACK
        case AcquireBlock.NO_COST:
            return _NO_COST
        case AcquireBlock.PERSUASION if needed is not None:
            return _persuasion_reason(needed, held)
        case AcquireBlock.SPECIMENS if needed is not None:
            return _specimen_cost_reason(needed, held)
        case AcquireBlock.NOT_IMPLEMENTED:
            return _BONUS_NOT_IMPLEMENTED
    return NOT_NOW


# --- Intrigue reasons ---


def _counted[T](sections: tuple[EffectSection, ...], kind: type[T]) -> list[T]:
    return [
        cost for section in sections for cost in section.costs if isinstance(cost, kind)
    ]


def _units(owner: PlayerState) -> tuple[int, int]:
    """(units anywhere, units in the Conflict), as the interpreter counts them."""

    in_conflict = owner.troops_conflict + owner.commanders_conflict
    return owner.troops_garrison + owner.commanders_garrison + in_conflict, in_conflict


def _in_conflict_reason(needed: int, held: int) -> Reason:
    en, ko = held_text(held)
    return (
        f"Needs {needed} unit{plural_s(needed)} in the Conflict{en}",
        f"{{conflict}}에 유닛 {needed}개 필요{ko}",
        "cost",
    )


def _choice_cost_reason(
    owner: PlayerState, sections: tuple[EffectSection, ...], cost: Cost
) -> Reason:
    """Why a player-choice cost (``_choice_cost_block``) cannot be paid."""

    match cost:
        case LoseInfluence():
            needed = sum(item.count for item in _counted(sections, LoseInfluence))
            held = sum(
                influence_amount(owner.influence, faction) for faction in Faction
            )
            en, ko = held_text(held)
            return (
                f"Needs {needed} Influence to lose{en}",
                f"잃을 {{influence_any}} {needed} 필요{ko}",
                "cost",
            )
        case DiscardFromHand():
            needed = sum(item.count for item in _counted(sections, DiscardFromHand))
            en, ko = held_text(len(owner.hand))
            return (
                f"Needs {needed} card{plural_s(needed)} in hand{en}",
                f"{{hand}}에 카드 {needed}장 필요{ko}",
                "cost",
            )
        case RecallSpy():
            needed = sum(item.count for item in _counted(sections, RecallSpy))
            en, ko = held_text(len(owner.spy_post_ids))
            spies = "Spy" if needed == 1 else "Spies"
            return (
                f"Needs {needed} {spies} on the board{en}",
                f"보드에 {{spy:{needed}}} 필요{ko}",
                "cost",
            )
        case LoseTroops():
            losses = _counted(sections, LoseTroops)
            units, in_conflict = _units(owner)
            needed = sum(item.count for item in losses)
            if units >= needed:
                conflict = sum(item.count for item in losses if item.from_conflict)
                return _in_conflict_reason(conflict, in_conflict)
            en, ko = held_text(units)
            return (
                f"Needs {needed} unit{plural_s(needed)}{en}",
                f"유닛 {needed}개 필요{ko}",
                "cost",
            )
        case GiveIntrigueToOpponent() | TrashIntrigueCard():
            return (
                "Needs another Intrigue card in hand",
                "다른 {intrigue} 필요",
                "cost",
            )
        case RetreatTroops():
            needed = sum(item.minimum for item in _counted(sections, RetreatTroops))
            return _in_conflict_reason(needed, _units(owner)[1])
        case FlipBattleCard():
            return (
                "No face-up won Conflict card with that icon",
                "그 아이콘의 앞면 {conflict} 카드 없음",
                "cost",
            )
        case FlipFaceUpConflictCard(count=count):
            en, ko = held_text(len(face_up_conflict_card_ids(owner)))
            return (
                f"Needs {count} face-up won Conflict card{plural_s(count)}{en}",
                f"앞면 {{conflict}} 카드 {count}장 필요{ko}",
                "cost",
            )
        case TrashDiscardPileCard(minimum_cost=minimum_cost):
            return (
                f"No card costing {minimum_cost} or more in your discard pile",
                f"{{discard_pile}}에 비용 {minimum_cost} 이상인 카드 없음",
                "cost",
            )
    return (
        f"Cannot pay: {cost_text(cost)}",
        f"낼 수 없음: {cost_text_ko(cost)}",
        NOT_NOW_CODE,  # a fallback: no specific reason for this cost yet
    )


def _choice_reward_reason(state: GameState, seat: int, reward: Reward) -> Reason:
    """Why a player-choice reward (``_choice_reward_block``) has no target."""

    match reward:
        case DeployFromGarrison() if units_deployment_blocked(state, seat):
            return (
                "Your units cannot be deployed now",
                "지금은 유닛을 배치할 수 없음",
                "reward",
            )
        case DeployFromGarrison():
            owner = state.players[seat]
            if owner.troops_garrison + owner.commanders_garrison == 0:
                return (
                    "No unit in your garrison to deploy",
                    "{garrison}에 배치할 유닛 없음",
                    "reward",
                )
            # Units in the garrison, none of them deployable: Harkonnen
            # Advisor's troop ("You can't deploy this troop to the Conflict
            # this turn." [Piter De Vries card], OQ-038), which
            # ``_choice_reward_block`` subtracts through this same helper.
            troops = min(
                undeployable_troops_this_turn(state, seat), owner.troops_garrison
            )
            return (
                f"Your garrison troop{plural_s(troops)} cannot be deployed this turn",
                "{garrison}의 {troop}은 이번 차례에 {conflict}에 배치할 수 없음",
                "reward",
            )
        case PlaceSpy():
            return (
                "No observation post for a Spy",
                "{spy}를 놓을 {observation_post} 없음",
                "reward",
            )
        case RetreatTroops(minimum=minimum):
            return _in_conflict_reason(minimum, _units(state.players[seat])[1])
        case TakeContract():
            return "No Contracts in this game", "이 게임에는 {contract} 없음", "reward"
        case SetAsideImperiumRowCard():
            return "The Imperium Row is empty", "{imperium_row}이 비었음", "reward"
        case PeekTopCard():
            return "Your deck is empty", "{deck}이 비었음", "reward"
        case TrashPersonalCard():
            return "No card in hand to trash", "{hand}에 {trash}할 카드 없음", "reward"
        case GainInfluence(where_opponent_leads=True):
            return (
                "No Faction where an opponent has more Influence",
                "상대가 더 높은 {faction} 없음",
                "reward",
            )
        case GainInfluence():
            return (
                "No Faction you may gain Influence with",
                "{influence_any}을 얻을 수 있는 {faction} 없음",
                "reward",
            )
        case RedirectSpiesOnTurnSpace():
            return (
                "Only after you send an Agent this turn",
                "이번 차례에 {agent}를 보낸 뒤에만",
                "reward",
            )
    return (
        f"Nothing to do now: {reward_text(reward)}",
        f"지금은 효과 없음: {reward_text_ko(reward)}",
        NOT_NOW_CODE,  # a fallback: no specific reason for this reward yet
    )


def _condition_reason(state: GameState, seat: int, option: IntrigueOption) -> Reason:
    """No printed section applies: its first failing condition, or else the
    Shield Wall its only section needs is gone (``applicable_sections``)."""

    for section in option.sections:
        condition = section.condition
        if condition is not None and not condition_holds(state, seat, condition):
            return (
                f"Only if {condition_text(condition)}",
                f"{condition_text_ko(condition)} 사용 가능",
                "condition",
            )
    return (
        "The Shield Wall is already destroyed",
        "{shield_wall}이 이미 파괴됨",
        "condition",
    )


def _resource_short_reason(owner: PlayerState, cost: PayResources | None) -> Reason:
    if cost is not None:
        for resource in ("solari", "spice", "water"):
            needed = getattr(cost, resource)
            held = getattr(owner.resources, resource)
            if needed > held:
                return resource_reason(resource, needed, held)
        return (
            f"Cannot pay: {cost_text(cost)}",
            f"낼 수 없음: {cost_text_ko(cost)}",
            NOT_NOW_CODE,  # a fallback: no resource is short
        )
    return NOT_NOW


def _contract_bank_reason(state: GameState, option: IntrigueOption) -> Reason:
    if not state.config.choam_module:
        return (
            "No Contracts in this game",
            "이 게임에는 {contract} 없음",
            "contract_bank",
        )
    needed = max(
        (
            reward.count
            for section in option.sections
            for reward in section.rewards
            if isinstance(reward, RevealContractsTakeOne)
        ),
        default=0,
    )
    held = len(state.contract_bank)
    return (
        f"Needs {needed} Contracts in the bank (there are {held})",
        f"{{contract}} 더미에 {needed}장 필요 (남은 {held}장)",
        "contract_bank",
    )


def intrigue_option_reason(
    state: GameState, seat: int, option: IntrigueOption, block: OptionUnplayable
) -> Reason:
    """Word ``option_unplayable_reason``'s answer with what the seat holds."""

    owner = state.players[seat]
    match block:
        case OptionBlock.CONDITION:
            return _condition_reason(state, seat, option)
        case OptionBlock.NO_LINE:
            return _NO_LINE
        case OptionBlock.CONTRACT_BANK:
            return _contract_bank_reason(state, option)
        case OptionBlock.COST:
            sections = applicable_sections(
                state, seat, option, shield_wall_present=state.shield_wall_present
            )
            return _resource_short_reason(owner, resource_cost(sections))
    # A player-choice cost or reward: the very object of the option's
    # applicable sections that ``option_unplayable_reason`` returned.
    sections = applicable_sections(
        state, seat, option, shield_wall_present=state.shield_wall_present
    )
    for section in sections:
        for cost in section.costs:
            if cost is block:
                return _choice_cost_reason(owner, sections, cost)
        for reward in section.rewards:
            if reward is block:
                return _choice_reward_reason(state, seat, reward)
    return NOT_NOW


# --- Collecting the candidates ---


@dataclass(slots=True)
class _Found:
    """The candidates of one decision, before the legality filter."""

    rows: list[tuple[DomainAction, dict[str, object]]] = field(default_factory=list)
    # A table object (card instance, Reserve stack) dimmed with a reason,
    # in the order met; a row's own card comes first.
    refs: dict[str, Reason] = field(default_factory=dict)

    def row(
        self,
        surface: str,
        key: str,
        action: DomainAction,
        reason: Reason,
        *,
        card_id: str | None = None,
        dim: str | None = None,
    ) -> None:
        english, korean, code = reason
        row: dict[str, object] = {
            "key": f"{surface}:{key}",
            "surface": surface,
            "action": action,
            "refs": [card_id or dim] if (card_id or dim) else [],
            "reason": english,
            "reason_ko": korean,
            "code": code,
        }
        if card_id is not None:
            row["card_id"] = card_id
        if dim is not None:
            row["dim"] = dim
        self.rows.append((action, row))


def _shop(state: GameState, seat: int, found: _Found) -> None:
    """The Reveal shop: Imperium Row, Reserve, set-aside and Tleilaxu cards."""

    owner = state.players[seat]
    persuasion = revealer_persuasion(state, seat)
    if persuasion is not None:
        for instance_id in state.imperium_row:
            block = imperium_acquisition_block(instance_id, persuasion)
            if block is not None:
                cost = imperium_card_for_instance(instance_id).acquisition_cost
                found.row(
                    "acquire",
                    instance_id,
                    DomainAction(
                        action_id="acquire_imperium",
                        actor=seat,
                        arguments=(("instance_id", instance_id),),
                    ),
                    _acquire_reason(block, cost, persuasion),
                    dim=instance_id,
                )
        for card_id, count in state.reserve_stacks:
            block = reserve_acquisition_block(state, card_id, count, persuasion)
            if block is not None:
                found.row(
                    "acquire",
                    card_id,
                    DomainAction(
                        action_id="acquire_reserve",
                        actor=seat,
                        arguments=(("card_id", card_id),),
                    ),
                    _acquire_reason(block, reserve_cost(state, card_id), persuasion),
                    dim=card_id,
                )
        for instance_id in owner.imperium_set_aside:
            block = manipulated_acquisition_block(instance_id, persuasion)
            if block is not None:
                found.row(
                    "acquire",
                    instance_id,
                    DomainAction(
                        action_id="acquire_manipulated_imperium",
                        actor=seat,
                        arguments=(("instance_id", instance_id),),
                    ),
                    _acquire_reason(block, manipulated_cost(instance_id), persuasion),
                    dim=instance_id,
                )
    if not tleilaxu_shop_is_open(state, seat):
        return
    for instance_id in state.tleilaxu_row:
        block = tleilaxu_acquisition_block(owner, instance_id)
        if block is not None:
            found.row(
                "acquire",
                instance_id,
                DomainAction(
                    action_id="acquire_tleilaxu",
                    actor=seat,
                    arguments=(("instance_id", instance_id),),
                ),
                _acquire_reason(
                    block,
                    tleilaxu_card_for_instance(instance_id).specimen_cost,
                    owner.specimens,
                ),
                dim=instance_id,
            )
    block = reclaimed_forces_block(owner)
    if block is not None:
        reason = _acquire_reason(block, RECLAIMED_FORCES.specimen_cost, owner.specimens)
        for choice in RECLAIMED_FORCES_CHOICES:
            found.row(
                "acquire",
                f"reclaimed_forces:{choice}",
                DomainAction(
                    action_id="acquire_reclaimed_forces",
                    actor=seat,
                    arguments=(("choice", choice),),
                ),
                reason,
                dim="reclaimed_forces",
            )


def _intrigue(state: GameState, seat: int, found: _Found) -> None:
    """The seat's own Intrigue cards in an open Intrigue window.

    An option failing on its cost or condition is a row; one printed for
    another window is not (it would be noise every turn), only its card's
    dim (``intrigue_play_block``'s timing blocks).
    """

    timing = intrigue_window(state, seat)
    if timing is None:
        return
    frame_kind = state.decision_stack[-1].kind
    for card_id in state.players[seat].intrigue_cards:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None or not entry.play_data_complete:
            continue  # the page marks an unimplemented card by itself
        other_window: Reason | None = None
        for index, option in enumerate(entry.options):
            block = intrigue_play_block(state, seat, frame_kind, timing, option)
            if block is None:
                continue
            if block is IntriguePlayBlock.TURN_START:
                other_window = other_window or _TURN_START
                continue
            if block is IntriguePlayBlock.TIMING:
                other_window = other_window or _TIMING[option.timing]
                continue
            found.row(
                "intrigue",
                f"{card_id}:{index}",
                DomainAction(
                    action_id="play_intrigue",
                    actor=seat,
                    arguments=(("card_id", card_id), ("option", index)),
                ),
                intrigue_option_reason(state, seat, option, block),
                dim=card_id,
            )
        if other_window is not None:
            found.refs.setdefault(card_id, other_window)


def _deferred(state: GameState, seat: int, found: _Found) -> None:
    """Deferred Reveal choices whose printed condition fails now.

    Known limitation: ``resume_reveal_choice`` is keyed by the effect kind
    alone, so while another card's deferred choice of the same kind is
    offered, a waiting one's action equals that legal action and the
    legality filter drops the waiting row. It only hides a row, never greys
    out a legal one; showing it would need the resume action to name its
    card.
    """

    for card_id, effect in waiting_deferred_choices(state, seat):
        found.row(
            "waiting",
            f"{card_id}:{effect}",
            DomainAction(
                action_id="resume_reveal_choice",
                actor=seat,
                arguments=(("effect", effect),),
            ),
            _WAITING,
            card_id=card_id,
        )


def _agent_box(state: GameState, seat: int, found: _Found) -> None:
    """A mandatory Agent box withheld until its condition holds (OQ-057).

    ``agent_box_is_waiting`` is the very test the legal list makes before
    offering ``resolve_agent_card_effect``.
    """

    if not agent_box_is_waiting(state, seat):
        return
    _, context = current_agent_effect_context(state)
    card_id = context.get("card_id")
    found.row(
        "waiting",
        f"agent_box:{card_id}",
        DomainAction(action_id="resolve_agent_card_effect", actor=seat),
        _WAITING,
        card_id=card_id if isinstance(card_id, str) else None,
    )


def _subcommittee_choice(state: GameState, seat: int, found: _Found) -> None:
    """A new High Council seat's subcommittee choice that nothing can meet
    now (Arrakeen Scouts, OQ-076 alternative C).

    ``choose_subcommittee`` is offered exactly when a subcommittee can be
    joined now; while the choice stays open and none can,
    ``choose_subcommittee_reason`` (the same ``joinable_subcommittees``
    test) says why, and the row lights up once one can.
    """

    # Imported here: display.scouts imports this module for its reasons.
    from dune_imperium.display.scouts import choose_subcommittee_reason

    reason = choose_subcommittee_reason(state, seat)
    if reason is None:
        return
    found.row(
        "waiting",
        "choose_subcommittee",
        DomainAction(action_id="choose_subcommittee", actor=seat),
        reason,
    )


_BY_FRAME: Final[Mapping[str, tuple[Callable[[GameState, int, _Found], None], ...]]] = {
    FrameKind.REVEAL: (_shop, _deferred, _subcommittee_choice, _intrigue),
    FrameKind.AGENT_EFFECTS: (_agent_box, _subcommittee_choice, _intrigue),
    FrameKind.TURN: (_intrigue,),
    FrameKind.COMBAT_INTRIGUE: (_intrigue,),
    FrameKind.ENDGAME_INTRIGUE: (_intrigue,),
}


# --- The payload ---


def shadow_action(state: GameState, action: DomainAction) -> dict[str, object]:
    """Describe a candidate the seat cannot take, the way a legal row is.

    The id, the arguments and the detail text (``effect_action_text``), with
    no index and no dry run: the engine refuses an action that is not legal.
    """

    # Imported here: display.actions imports display.scouts, which imports
    # this module for its reason helpers.
    from dune_imperium.display.actions import (
        effect_action_text,
        effect_action_text_ko,
    )

    try:
        detail = effect_action_text(state, action)
        detail_ko = effect_action_text_ko(state, action)
    except Exception:  # noqa: BLE001 - written for legal actions; a miss is no detail
        detail = detail_ko = None
    return {
        "action_id": action.action_id,
        "arguments": dict(action.arguments),
        "detail": detail,
        "detail_ko": detail_ko,
    }


def _why(reason: Reason) -> dict[str, object]:
    return {"reason": reason[0], "reason_ko": reason[1], "code": reason[2]}


def unavailable_choices(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> dict[str, object] | None:
    """What ``seat``'s own decision offers that it cannot take now, and why.

    ``rows`` are the greyed-out panel rows: ``surface`` ("acquire",
    "intrigue", "waiting") says which list a row sits in, ``action`` is the
    candidate described like a legal row (``shadow_action``), ``refs`` the
    table objects it names, with ``reason``, ``reason_ko`` and ``code``.
    ``refs`` maps a card on the table (an Imperium Row, Reserve, Tleilaxu,
    set-aside or Intrigue card) to the reason it is dimmed. ``legal`` is the
    list the page numbers: a candidate in it, or a ref one of its actions
    names, is left out. None when nothing is greyed out, for any decision
    that is not ``seat``'s, and while Gather Intelligence is its only choice.
    """

    frame = state.decision_stack[-1] if state.decision_stack else None
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != seat
    ):
        return None
    collectors = _BY_FRAME.get(frame.kind, ())
    if not collectors:
        return None
    if legal_gather_intelligence_actions(state, seat):
        # Gather Intelligence replaces the Agent-effect frame's whole list
        # while it is pending (``legal_agent_effect_frame_actions``): the
        # waiting Agent box and the Intrigue cards come back after it.
        return None
    found = _Found()
    for collect in collectors:
        collect(state, seat, found)
    offered = frozenset(legal)
    named = {
        value
        for action in legal
        for _, value in action.arguments
        if isinstance(value, str)
    }
    rows: list[dict[str, object]] = []
    refs: dict[str, dict[str, object]] = {}
    for action, row in found.rows:
        if action in offered:
            continue
        dim = row.pop("dim", None)
        if isinstance(dim, str) and dim not in named and dim not in refs:
            refs[dim] = _why(
                (str(row["reason"]), str(row["reason_ko"]), str(row["code"]))
            )
        rows.append({**row, "action": shadow_action(state, action)})
    for ref, reason in found.refs.items():
        if ref not in named and ref not in refs:
            refs[ref] = _why(reason)
    if not rows and not refs:
        return None
    return {"frame": str(frame.kind), "rows": rows, "refs": refs}
