"""What a seat cannot take right now, shown greyed out with the reason.

User request 2026-09-29: an option that cannot be taken right now is shown
but not selectable, with the reason, and it becomes selectable as soon as it
can be taken (and the reverse), for the whole game. Arrakeen Scouts choices
already do this (``display.scouts.scouts_choice_lines``); this module does it
for the Reveal shop, Intrigue plays and effects waiting on their condition
(a new High Council seat's subcommittee choice, an Agent-box icon below
its printed threshold and held Contract icons among them), and for the
branch of an open choice that cannot be taken ("choice": Desert Power's
sandworm, a recall with no Agent to recall, a research bonus whose cost
cannot be paid, a Conflict reward's Faction already at the top, a Holy War
unit the seat does not have, a Skill the seat already holds, a Navigation
card's option it cannot play, an Acquire Tech with every stack empty, an
Agent-box icon that cannot come back before the turn's end, a Contract the
seat has no Intrigue card to trash for, Litany Against Fear once the seat
already acted in its turn, a separate-lines Intrigue card's finish before
one of its lines is used).

Display only, under four rules:

- Legality comes only from the engine's legal list. A candidate is dropped
  whenever its action is in that list, and a table ref whenever a legal
  action names it, so a disagreement could only hide a greyed-out row, never
  grey out something the seat may do.
- A reason is worked out only for a candidate that is not legal, from the
  block predicate the legal provider itself uses (``AcquireBlock``,
  ``option_unplayable_reason``, ``intrigue_play_block``,
  ``waiting_deferred_choices``, ``agent_box_is_waiting``,
  ``joinable_subcommittees``, ``reveal_sandworm_block``,
  ``imperial_privilege_recall_targets``, ``contract_recall_targets``,
  ``research_bonus_block``, ``combat_reward_influence_block``,
  ``unit_loss_block``, ``skill_choice_block``, ``tech_candidates``,
  ``agent_icon_block``, ``agent_card_recall_targets``,
  ``contract_take_block``, ``turn_start_is_open``,
  ``intrigue_effects_finish_is_open``), so the two cannot drift.
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

from dune_imperium.content.immortality.board import ResearchBonus
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
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_INSTANCE,
    intrigue_card_for_instance,
)
from dune_imperium.content.uprising.types import PersonalCardRevealChoiceEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
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
from dune_imperium.rules.agent_effects import (
    AUTOMATIC_AGENT_ICONS,
    AgentIconBlock,
    AgentIconCondition,
    agent_card_recall_targets,
    agent_icon_block,
)
from dune_imperium.rules.agent_turn import turn_start_cards
from dune_imperium.rules.board_effects import imperial_privilege_recall_targets
from dune_imperium.rules.combat import (
    CombatInfluenceBlock,
    combat_reward_influence_block,
)
from dune_imperium.rules.combat_deployment import undeployable_troops_this_turn
from dune_imperium.rules.contracts import (
    ContractTakeBlock,
    contract_recall_targets,
    contract_take_block,
    held_contract_icons_can_open,
    market_contract_ids,
)
from dune_imperium.rules.effect_interpreter import (
    OptionBlock,
    OptionUnplayable,
    applicable_sections,
    condition_holds,
    face_up_conflict_card_ids,
    option_unplayable_reason,
    resource_cost,
)
from dune_imperium.rules.effects import (
    active_agent_card,
    current_agent_effect_context,
    pending_agent_icons,
)
from dune_imperium.rules.frames import FrameKind, turn_owner_of, turn_start_is_open
from dune_imperium.rules.immortality import (
    SEVEN_SOLARI_COST,
    ResearchBonusBlock,
    research_bonus_block,
)
from dune_imperium.rules.influence import influence_amount
from dune_imperium.rules.intrigue import (
    IntriguePlayBlock,
    intrigue_effects_finish_is_open,
    intrigue_play_block,
    intrigue_window,
)
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.reveal_turn import (
    RevealSandwormBlock,
    reveal_sandworm_block,
    waiting_deferred_choices,
)
from dune_imperium.rules.sardaukar import (
    face_up_skill_identities,
    skill_choice_block,
)
from dune_imperium.rules.spies import (
    gather_intelligence_draw_available,
    legal_gather_intelligence_actions,
)
from dune_imperium.rules.spy_moves import connected_post_ids
from dune_imperium.rules.tech import tech_candidates
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    reclaimed_forces_block,
    tleilaxu_acquisition_block,
    tleilaxu_shop_is_open,
)
from dune_imperium.rules.unit_loss import (
    UNIT_LOSS_CANDIDATES,
    UnitLossBlock,
    unit_loss_block,
    unit_loss_options,
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
_LINE_FIRST: Final[Reason] = (
    "Use at least one of its lines first",
    "먼저 줄을 하나 이상 써야 함",
    "line_first",
)
_NO_MAKER_HOOKS: Final[Reason] = (
    "No Maker Hooks",
    "{maker_hooks} 없음",
    "maker_hooks",
)
_NO_CONFLICT: Final[Reason] = (
    "No Conflict this round",
    "이번 라운드에 교전 없음",
    "no_conflict",
)
_SHIELD_WALL: Final[Reason] = (
    "The Shield Wall protects this Conflict",
    "{shield_wall}이 이번 교전을 보호함",
    "shield_wall",
)
_NO_OTHER_AGENT: Final[Reason] = (
    "No other Agent of yours to recall (not the one sent this turn)",
    "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외)",
    "no_target",
)
_NO_INTRIGUE_TO_TRASH: Final[Reason] = (
    "No Intrigue card to trash",
    "{trash}할 {intrigue} 없음",
    "cost",
)
_AT_THE_TOP: Final[Reason] = ("Already at the top", "이미 최고치", "top")
_NAMED_FOR_THIS_REWARD: Final[Reason] = (
    "Already named for this reward",
    "이 보상에서 이미 고른 진영",
    "named",
)
_NO_UNIT_TO_LOSE: Final[Reason] = ("No unit to lose", "잃을 유닛 없음", "no_unit")
_LAPSES_EN: Final = "; it lapses if still unmet when the turn ends"
_LAPSES_KO: Final = " — 차례가 끝날 때까지 못 채우면 사라짐"
_NO_RECALL_TARGET: Final[Reason] = (
    "No other Agent of yours to recall (not the one sent this turn);"
    " it lapses when the turn ends",
    "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외) — 차례가 끝날 때 사라짐",
    "no_target",
)
_TECH_STACKS_EMPTY: Final[Reason] = (
    "Every Tech stack is empty",
    "{tech_tile} 더미가 모두 비었음",
    "empty",
)
_SKILL_HELD: Final[Reason] = (
    "You already have this Skill",
    "이미 가진 {commander_skill}",
    "held",
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
# "At the start of your turn" (Withdrawn, Litany Against Fear) on the turn
# frame once the seat already acted in the turn (OQ-095 (6), user ruling
# 2026-10-04, ``frames.turn_start_is_open``).
_TURN_STARTED: Final[Reason] = (
    "Only at the start of your turn: you already acted this turn",
    "차례를 시작할 때만 사용 — 이번 차례에 이미 다른 행동을 했음",
    "turn_started",
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
            # The gate asks for one unit even of a zero-minimum retreat
            # (``_choice_reward_block``).
            return _in_conflict_reason(
                max(minimum, 1), _units(state.players[seat])[1]
            )
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
                _TURN_STARTED
                if block is IntriguePlayBlock.TURN_STARTED
                else intrigue_option_reason(state, seat, option, block),
                dim=card_id,
            )
        if other_window is not None:
            found.refs.setdefault(card_id, other_window)


def _turn_start_card(state: GameState, seat: int, found: _Found) -> None:
    """Litany Against Fear in hand once the start of the seat's turn is over.

    "At the start of your turn: Put this card into play -> Draw a card and
    pass your turn." [Litany Against Fear card]: only the turn's first
    action (OQ-095 (6), user ruling 2026-10-04). A branch of the turn
    frame's choice, beside the Agent and Reveal turns; the row names the
    card rather than dimming it in the hand, which it leaves only this way
    or with the Reveal.
    """

    if turn_start_is_open(state, seat):
        return
    for card_id in turn_start_cards(state.players[seat]):
        found.row(
            "choice",
            card_id,
            DomainAction(
                action_id="play_turn_start_card",
                actor=seat,
                arguments=(("card_id", card_id),),
            ),
            _TURN_STARTED,
            card_id=card_id,
        )


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


def _sandworm_reason(state: GameState, seat: int, block: RevealSandwormBlock) -> Reason:
    match block:
        case RevealSandwormBlock.MAKER_HOOKS:
            return _NO_MAKER_HOOKS
        case RevealSandwormBlock.WATER:
            return resource_reason("water", 1, state.players[seat].resources.water)
        case RevealSandwormBlock.NO_CONFLICT:
            return _NO_CONFLICT
        case RevealSandwormBlock.SHIELD_WALL:
            return _SHIELD_WALL
    return NOT_NOW


def _reveal_choice(state: GameState, seat: int, found: _Found) -> None:
    """Desert Power's sandworm branch while it cannot be taken.

    The choice opens for every seat, which may always take the Persuasion
    branch (option (B), user ruling 2026-09-30: "REVEAL_CHOICE 창을 열어
    '설득 2'만 고르게, 모래벌레 줄은 '메이커 작살 없음' 회색"); the sandworm
    branch is offered exactly when ``reveal_sandworm_block`` is None, and
    otherwise shows greyed out with that block.
    """

    context = dict(state.decision_stack[-1].context)
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM.value
    ):
        return
    block = reveal_sandworm_block(state, seat)
    if block is None:
        return
    card_id = context.get("reveal_card_id")
    found.row(
        "choice",
        "pay_reveal_water_for_sandworm",
        DomainAction(action_id="pay_reveal_water_for_sandworm", actor=seat),
        _sandworm_reason(state, seat, block),
        card_id=card_id if isinstance(card_id, str) else None,
    )


def _imperial_privilege_recall(state: GameState, seat: int, found: _Found) -> None:
    """Imperial Privilege's recall when no other Agent can be recalled.

    The provider then offers only ``resolve_imperial_privilege_without_recall``
    (the recall is skipped and the card still drawn, OQ-023), exactly when
    ``imperial_privilege_recall_targets`` is empty; the recall shows greyed
    out beside it with the reason. Targets never grow within one Agent turn,
    so the row cannot light up again.
    """

    if imperial_privilege_recall_targets(state, seat) != ():
        return
    found.row(
        "choice",
        "imperial_privilege_recall",
        DomainAction(action_id="recall_agent_for_imperial_privilege", actor=seat),
        _NO_OTHER_AGENT,
    )


def _contract_recall(state: GameState, seat: int, found: _Found) -> None:
    """A Contract's Recall Agent reward (Sardaukar II, the Bloodlines High
    Council token) with no Agent to recall: the provider offers only
    ``resolve_contract_without_recall`` exactly when
    ``contract_recall_targets`` is empty, and the recall shows greyed out."""

    if contract_recall_targets(state, seat) != ():
        return
    found.row(
        "choice",
        "contract_recall",
        DomainAction(action_id="recall_agent_for_contract", actor=seat),
        _NO_OTHER_AGENT,
    )


def _contract_take_reason(block: ContractTakeBlock) -> Reason:
    match block:
        case ContractTakeBlock.NEEDS_INTRIGUE:
            return _NO_INTRIGUE_TO_TRASH
    return NOT_NOW


def _blocked_contracts(
    state: GameState, seat: int
) -> list[tuple[str, ContractTakeBlock]]:
    return [
        (instance_id, block)
        for instance_id in market_contract_ids(state, seat)
        if (block := contract_take_block(state, seat, instance_id)) is not None
    ]


def _contract_market(state: GameState, seat: int, found: _Found) -> None:
    """A Contract icon's market: every token the seat cannot take now.

    "You can't take the new Immediate contract unless you have an Intrigue
    card to trash." `[Bloodlines p. 2]`. The provider offers a token exactly
    when ``contract_take_block`` is None (``takeable_contract_ids``); the
    others show greyed out with the block, and their market token dims.
    With nothing in a non-empty market takeable the window still opens (user
    ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
    연다") with only ``hold_contract_icons`` (OQ-059).
    """

    for instance_id, block in _blocked_contracts(state, seat):
        found.row(
            "choice",
            f"take_contract:{instance_id}",
            DomainAction(
                action_id="take_contract",
                actor=seat,
                arguments=(("instance_id", instance_id),),
            ),
            _contract_take_reason(block),
            dim=instance_id,
        )


def _held_contracts(state: GameState, seat: int, found: _Found) -> None:
    """The seat's held Contract icons, under "waiting", in any of its
    decisions but the market itself (which greys the token out).

    Held when nothing in a non-empty market could be taken (OQ-059); the
    market reopens by itself once ``held_contract_icons_can_open`` (a token
    the seat can take, by ``contract_take_block``). The icons fizzle at the
    turn-end press, or, held from a Conflict reward, at the end of the
    seat's Conflict rewards (user ruling 2026-10-02, L2-Q2).

    The row promises the reopening and the lapse where the engine does
    both (``engine._held_contract_owner``): in the seat's own turn, in the
    Combat phase, and during the Arrakeen Scouts step, whose held icons
    fizzle as the step ends (user ruling 2026-10-02, "Scouts 단계 안에서
    보류 후 불발"). Anywhere else the row only says they are held.
    """

    held = state.players[seat].held_contract_icons
    if not held or held_contract_icons_can_open(state, seat):
        return
    if state.decision_stack[-1].kind == FrameKind.CONTRACT_MARKET:
        return
    icons_en = f"{held} Contract icon{plural_s(held)} held"
    icons_ko = f"{{contract}} 아이콘 {held}개 보류"
    take_en = "taken once you have an Intrigue card to trash"
    take_ko = "{trash}할 {intrigue}가 생기면 가져감"
    reason: Reason
    if state.phase is GamePhase.COMBAT:
        reason = (
            f"{icons_en}: {take_en}, lost when your Conflict rewards end",
            f"{icons_ko} — {take_ko}, 교전 보상을 다 받으면 사라짐",
            "waiting",
        )
    elif turn_owner_of(state) == seat:
        reason = (
            f"{icons_en}: {take_en}, lost when the turn ends",
            f"{icons_ko} — {take_ko}, 차례가 끝나면 사라짐",
            "waiting",
        )
    elif state.scouts_opening and turn_owner_of(state) is None:
        reason = (
            f"{icons_en}: {take_en}, lost when the Arrakeen Scouts step ends",
            f"{icons_ko} — {take_ko}, 아라킨 스카웃 단계가 끝나면 사라짐",
            "waiting",
        )
    else:
        reason = (
            f"{icons_en}: no Contract you can take now",
            f"{icons_ko} — 지금 가져갈 수 있는 {{contract}} 없음",
            "waiting",
        )
    # The tokens it waits for; with none left in the market, an id-less
    # take that is never legal.
    waits_for = [instance_id for instance_id, _ in _blocked_contracts(state, seat)]
    for instance_id in waits_for or [""]:
        found.row(
            "waiting",
            f"held_contracts:{instance_id}",
            DomainAction(
                action_id="take_contract",
                actor=seat,
                arguments=(("instance_id", instance_id),) if instance_id else (),
            ),
            reason,
        )


def _research_bonus(state: GameState, seat: int, found: _Found) -> None:
    """A research space's arrow whose cost cannot be paid (Immortality).

    The window opens anyway and then offers only ``decline_research_bonus``
    (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정
    창을 연다"), exactly when ``research_bonus_block`` is not None; the
    payment shows greyed out beside it with the reason. The trash row names
    no card: with no Intrigue card in hand there is none to name.
    """

    bonus = dict(state.decision_stack[-1].context).get("bonus")
    if not isinstance(bonus, str):
        return
    owner = state.players[seat]
    match research_bonus_block(owner, ResearchBonus(bonus)):
        case ResearchBonusBlock.NO_INTRIGUE:
            found.row(
                "choice",
                "research_bonus_trash",
                DomainAction(action_id="trash_intrigue_for_research_bonus", actor=seat),
                _NO_INTRIGUE_TO_TRASH,
            )
        case ResearchBonusBlock.SOLARI:
            found.row(
                "choice",
                "research_bonus_pay",
                DomainAction(action_id="pay_research_bonus", actor=seat),
                resource_reason("solari", SEVEN_SOLARI_COST, owner.resources.solari),
            )
        case None:
            pass


def _combat_reward_influence(state: GameState, seat: int, found: _Found) -> None:
    """A Conflict reward's "choose a Faction" Influence: every Faction it
    cannot take now, with ``combat_reward_influence_block``'s reason.

    The providers offer a Faction exactly when that block is None. With
    every eligible Faction blocked the window still opens (user ruling
    2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
    연다") and offers only ``resolve_combat_influence_without_faction``
    (OQ-060); the Factions show greyed out beside it. A track at the top
    can come down again later (an Influence loss), so the rows are shown in
    any such window, not only the empty one.
    """

    frame = state.decision_stack[-1]
    action_id = (
        "choose_combat_reward_influence"
        if frame.kind is FrameKind.COMBAT_REWARD_INFLUENCE
        else "choose_distinct_combat_reward_influence"
    )
    owner = state.players[seat]
    for faction in Faction:
        block = combat_reward_influence_block(frame, owner, faction)
        if block is None:
            continue
        found.row(
            "choice",
            f"combat_reward_influence:{faction.value}",
            DomainAction(
                action_id=action_id,
                actor=seat,
                arguments=(("faction", faction.value),),
            ),
            _AT_THE_TOP
            if block is CombatInfluenceBlock.TOP
            else _NAMED_FOR_THIS_REWARD,
        )


def _unit_loss_reason(zone: str, block: UnitLossBlock) -> Reason:
    where = "your garrison" if zone == "garrison" else "the Conflict"
    if block is UnitLossBlock.NO_COMMANDER:
        return (
            f"No Sardaukar Commander in {where}",
            f"{{{zone}}}에 {{commander}} 없음",
            "no_unit",
        )
    return f"No troop in {where}", f"{{{zone}}}에 {{troop}} 없음", "no_unit"


def _unit_loss(state: GameState, seat: int, found: _Found) -> None:
    """Holy War's unit loss: every (zone, unit) the seat cannot lose now.

    Every opponent is asked, even with one option or none (user ruling
    2026-09-30, OQ-036 (a)). The provider offers ``lose_unit`` exactly when
    ``unit_loss_block`` is None; an empty zone shows greyed out with its
    reason, a Sardaukar Commander row only for a seat that owns one. With
    no unit at all only ``resolve_unit_loss_without_unit`` is offered, and
    every row reads "No unit to lose" beside it.
    """

    owner = state.players[seat]
    nothing = not unit_loss_options(state, seat)
    for zone, commander in UNIT_LOSS_CANDIDATES:
        if commander and owner.commanders_total == 0:
            continue
        block = unit_loss_block(owner, zone, commander=commander)
        if block is None:
            continue
        found.row(
            "choice",
            f"lose_unit:{zone}:{int(commander)}",
            DomainAction(
                action_id="lose_unit",
                actor=seat,
                arguments=(
                    *((("commanders", 1),) if commander else ()),
                    ("zone", zone),
                ),
            ),
            _NO_UNIT_TO_LOSE if nothing else _unit_loss_reason(zone, block),
        )


def _navigation(state: GameState, seat: int, found: _Found) -> None:
    """A Navigation card's options that cannot be played now (Steersman
    Y'rkoon's Plot Course, OQ-039).

    The provider offers ``play_navigation`` for an option exactly when
    ``option_unplayable_reason`` is None (``option_is_playable``); the others
    show greyed out with that block, worded as an Intrigue card's
    (``intrigue_option_reason``). With none playable the window still opens
    (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정
    창을 연다") with only ``decline_navigation``, which spends the card
    without effect (OQ-039 (b)). The rows name no card: the page names the
    Navigation card a ``play_navigation`` row plays by itself.
    """

    card_id = dict(state.decision_stack[-1].context).get("card_id")
    if not isinstance(card_id, str):
        return
    for index, option in enumerate(intrigue_card_for_instance(card_id).options):
        block = option_unplayable_reason(state, seat, option)
        if block is None:
            continue
        found.row(
            "choice",
            f"play_navigation:{index}",
            DomainAction(
                action_id="play_navigation",
                actor=seat,
                arguments=(("option", index),),
            ),
            intrigue_option_reason(state, seat, option, block),
        )


def _intrigue_effects(state: GameState, seat: int, found: _Found) -> None:
    """Finishing a separate-lines Intrigue card before any line is used.

    At least one line must be used (OQ-058, user ruling 2026-10-04): the
    provider offers ``finish_intrigue_effects`` exactly when
    ``intrigue_effects_finish_is_open``, so until a line is used the
    finish shows greyed out beside the lines the seat can use.
    """

    if intrigue_effects_finish_is_open(state, seat):
        return
    found.row(
        "choice",
        "finish_intrigue_effects",
        DomainAction(action_id="finish_intrigue_effects", actor=seat),
        _LINE_FIRST,
    )


def _tech(state: GameState, seat: int, found: _Found) -> None:
    """A card's Acquire Tech with no tile left to take (Battlefield
    Research, Rapid Engineering).

    The window opens anyway (user ruling 2026-09-30, "결정 창 없이 자동으로
    넘어가는 곳도 모두 결정 창을 연다") and offers only ``decline_tech``
    exactly when ``tech_candidates`` is empty (OQ-057 (9) "살 수 없으면
    거절만"); the acquisition shows greyed out beside it. The row names no
    tile, so it is never a legal action (those always name one).
    """

    if tech_candidates(state, state.players[seat]):
        return
    found.row(
        "choice",
        "acquire_tech",
        DomainAction(action_id="acquire_tech", actor=seat),
        _TECH_STACKS_EMPTY,
    )


def _skill_choice(state: GameState, seat: int, found: _Found) -> None:
    """A Skill choice's face-up Skills the seat already holds.

    "You cannot choose a copy of a Sardaukar Commander Skill already in your
    supply" [Bloodlines p. 4]: the provider offers a face-up Skill exactly
    when ``skill_choice_block`` is None, and the others show greyed out.
    With none choosable the window still opens (user ruling 2026-10-02,
    L2-Q3 (1)) with only ``resolve_commander_without_skill`` (a bank
    Commander) or ``decline_skill`` (Plasteel Blades), and every face-up
    Skill reads "You already have this Skill" beside it.
    """

    owner = state.players[seat]
    for skill_id in face_up_skill_identities(state):
        if skill_choice_block(owner, skill_id) is None:
            continue
        found.row(
            "choice",
            f"choose_skill:{skill_id}",
            DomainAction(
                action_id="choose_skill",
                actor=seat,
                arguments=(("skill_id", skill_id),),
            ),
            _SKILL_HELD,
        )


def _agent_icon_reason(block: AgentIconBlock) -> Reason:
    """Word ``agent_icon_block``'s answer with what the seat has."""

    needed, held = block.needed, block.held
    match block.condition:
        case AgentIconCondition.INFLUENCE if block.faction is not None:
            name = block.faction.value.replace("_", " ").title()
            return (
                f"Needs {needed} {name} Influence (you have {held}){_LAPSES_EN}",
                f"{{influence_{block.faction.value}}} {needed} 필요 (보유 {held})"
                f"{_LAPSES_KO}",
                "condition",
            )
        case AgentIconCondition.SPICE_GAINED:
            return (
                f"Needs {needed} spice gained this turn (you gained {held})"
                f"{_LAPSES_EN}",
                f"이번 차례에 얻은 {{spice}} {needed} 필요 (얻은 {held}){_LAPSES_KO}",
                "condition",
            )
        case AgentIconCondition.GENETIC_MARKERS:
            return (
                f"Needs {needed} genetic markers (you have {held}){_LAPSES_EN}",
                f"유전자 마커 {needed}개 필요 (보유 {held}){_LAPSES_KO}",
                "condition",
            )
        case AgentIconCondition.GRAFTED:
            return (
                "Only when the card is grafted; it lapses when the turn ends",
                "{graft}한 카드일 때만 — 차례가 끝날 때 사라짐",
                "condition",
            )
        case AgentIconCondition.NOT_PRINTED:
            return ("Not printed on this card", "이 카드에 없는 아이콘", "condition")
    return NOT_NOW


# Conditions a later effect of the same turn can still meet (Influence
# gained, spice gained, a marker reached): such an icon sits with the
# Agent boxes waiting on theirs (``_agent_box``), under "waiting". A card
# grafted or not stays so all turn, and an unprinted icon never comes.
_ICON_CAN_STILL_BE_MET: Final = frozenset(
    {
        AgentIconCondition.INFLUENCE,
        AgentIconCondition.SPICE_GAINED,
        AgentIconCondition.GENETIC_MARKERS,
    }
)


def _agent_icons(state: GameState, seat: int, found: _Found) -> None:
    """A multi-icon Agent box's icons withheld while their condition fails.

    Such an icon is not offered and fizzles when the owner presses the
    turn's end (OQ-057 (1)); no window opens for it, it shows greyed out
    while the turn is open (user ruling 2026-10-02, L2-Q3: "③은 회색 줄만"
    -- Steersman Y'rkoon's Recall Agent icon with no target, and the other
    conditioned icons). The reasons come from the providers' own answers:
    ``agent_icon_block`` (an automatic icon is offered exactly when it is
    None) and ``agent_card_recall_targets`` (the recall is offered once per
    target). An icon whose condition a later effect of the turn can still
    meet (Influence, spice gained, genetic markers) sits under "waiting",
    like a single Agent box withheld by the same rule (``_agent_box``); one
    that cannot come back this turn (an ungrafted card, a recall with no
    target -- targets never grow within one Agent turn) under "choice".
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != seat:
        return
    if context.get("pending_agent_effect") is not True:
        return
    card_id = context.get("card_id")
    card = card_id if isinstance(card_id, str) else None
    owner = state.players[seat]
    effect = active_agent_card(context).agent_effect
    for key in pending_agent_icons(context):
        if key not in AUTOMATIC_AGENT_ICONS:
            continue
        block = agent_icon_block(owner, context, effect, key)
        if block is None:
            continue
        found.row(
            "waiting" if block.condition in _ICON_CAN_STILL_BE_MET else "choice",
            f"agent_icon:{key}",
            DomainAction(
                action_id="resolve_agent_card_effect",
                actor=seat,
                arguments=(("effect", key),),
            ),
            _agent_icon_reason(block),
            card_id=card,
        )
    if agent_card_recall_targets(state, seat) == ():
        found.row(
            "choice",
            "agent_icon:recall",
            DomainAction(action_id="recall_agent_for_agent_card", actor=seat),
            _NO_RECALL_TARGET,
            card_id=card,
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
    test) says why, and the row lights up once one can. With every
    subcommittee already taken it never can: the offer still opens (user
    ruling 2026-09-30, OQ-076 (c); unreachable with four players) with only
    its decline, and the row sits among the choices that cannot be taken
    rather than the waiting ones.
    """

    # Imported here: display.scouts imports this module for its reasons.
    from dune_imperium.display.scouts import (
        SUBCOMMITTEES_CLAIMED,
        choose_subcommittee_reason,
    )

    reason = choose_subcommittee_reason(state, seat)
    if reason is None:
        return
    found.row(
        "choice" if reason == SUBCOMMITTEES_CLAIMED else "waiting",
        "choose_subcommittee",
        DomainAction(action_id="choose_subcommittee", actor=seat),
        reason,
    )


_BY_FRAME: Final[Mapping[str, tuple[Callable[[GameState, int, _Found], None], ...]]] = {
    FrameKind.REVEAL: (_shop, _deferred, _subcommittee_choice, _intrigue),
    FrameKind.REVEAL_CHOICE: (_reveal_choice,),
    FrameKind.AGENT_EFFECTS: (
        _agent_box,
        _agent_icons,
        _imperial_privilege_recall,
        _subcommittee_choice,
        _intrigue,
    ),
    FrameKind.CONTRACT_MARKET: (_contract_market,),
    FrameKind.CONTRACT_REWARD_RECALL: (_contract_recall,),
    FrameKind.RESEARCH_BONUS: (_research_bonus,),
    FrameKind.COMBAT_REWARD_INFLUENCE: (_combat_reward_influence,),
    FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE: (_combat_reward_influence,),
    FrameKind.OPPONENT_UNIT_LOSS: (_unit_loss,),
    FrameKind.SKILL_CHOICE: (_skill_choice,),
    FrameKind.NAVIGATION_CHOICE: (_navigation,),
    FrameKind.INTRIGUE_EFFECTS: (_intrigue_effects,),
    FrameKind.TECH_ACQUISITION: (_tech,),
    FrameKind.TURN: (_turn_start_card, _intrigue),
    FrameKind.COMBAT_INTRIGUE: (_intrigue,),
    FrameKind.ENDGAME_INTRIGUE: (_intrigue,),
}


# Collected in every decision of the seat, after its frame's own.
_EVERY_FRAME: Final[tuple[Callable[[GameState, int, _Found], None], ...]] = (
    _held_contracts,
)


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


def _gather_intelligence(state: GameState, seat: int, found: _Found) -> None:
    """Explain the existing empty-piles block in the immediate Spy window."""

    if gather_intelligence_draw_available(state, seat):
        return
    _, context = current_agent_effect_context(state)
    space_id = context.get("space_id")
    if not isinstance(space_id, str):
        return
    posts = connected_post_ids(space_id)
    for post_id in state.players[seat].spy_post_ids:
        if post_id not in posts:
            continue
        found.row(
            "choice",
            f"gather_intelligence:{post_id}",
            DomainAction(
                action_id="gather_intelligence",
                actor=seat,
                arguments=(("post_id", post_id),),
            ),
            (
                "No card to draw: your deck and discard pile are both empty",
                "뽑을 카드 없음: 덱과 버린 카드 더미가 모두 비었음",
                "empty",
            ),
        )


def unavailable_choices(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> dict[str, object] | None:
    """What ``seat``'s own decision offers that it cannot take now, and why.

    ``rows`` are the greyed-out panel rows: ``surface`` ("acquire",
    "intrigue", "waiting", or "choice" for a branch of an open choice that
    cannot be taken now) says which list a row sits in, ``action`` is the
    candidate described like a legal row (``shadow_action``), ``refs`` the
    table objects it names, with ``reason``, ``reason_ko`` and ``code``.
    ``refs`` maps a card on the table (an Imperium Row, Reserve, Tleilaxu,
    set-aside or Intrigue card) to the reason it is dimmed. ``legal`` is the
    list the page numbers: a candidate in it, or a ref one of its actions
    names, is left out. None when nothing is greyed out, for any decision
    that is not ``seat``'s. Gather Intelligence hides the waiting Agent
    effects but still explains its own unavailable draw.
    """

    frame = state.decision_stack[-1] if state.decision_stack else None
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != seat
    ):
        return None
    collectors = (*_BY_FRAME.get(frame.kind, ()), *_EVERY_FRAME)
    if legal_gather_intelligence_actions(state, seat):
        # Gather Intelligence replaces the Agent-effect frame's whole list
        # while it is pending (``legal_agent_effect_frame_actions``): the
        # waiting Agent box and the Intrigue cards come back after it.
        collectors = (_gather_intelligence,)
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
