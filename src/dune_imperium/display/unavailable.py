"""What a seat cannot take right now, shown greyed out with the reason.

User request 2026-09-29: an option that cannot be taken right now is shown
but not selectable, with the reason, and it becomes selectable as soon as it
can be taken (and the reverse), for the whole game. Arrakeen Scouts choices
already do this (``display.scouts.scouts_choice_lines``); this module does it
for the Reveal shop, Intrigue plays (one none of whose effects could
change anything now among them, user ruling 2026-10-06; Call to Arms in a
Reveal with nothing left to acquire; a Harvest Cells its Conflict-end
window does not offer) and effects waiting on their
condition (a new High Council seat's subcommittee choice, an Agent-box
icon below its printed threshold, held Contract icons and a Leader's Reveal
ability with nothing to act on yet among them), and
for the branch of an open choice that cannot be taken ("choice": Desert Power's
sandworm, a recall with no Agent to recall, a research bonus whose cost
cannot be paid or whose reward would change nothing, an Agent box's arrow
whose reward would change nothing (OQ-071), a Conflict reward's, a research
space's or Shipping's Faction already at the top, a Conflict reward's payment
(resource or Spies) the seat is short of, a Maker space's sandworm or Desert
Riding token it cannot take, Sietch Tabr's detonation once the Shield Wall is
destroyed, a Holy War unit the
seat does not have, a Skill the seat already holds, a Navigation card's
option it cannot play, an Acquire Tech with every stack empty, an
Agent-box icon that cannot come back before the turn's end, a Contract the
seat has no Intrigue card to trash for, Litany Against Fear once the seat
already acted in its turn, a separate-lines Intrigue card's finish before
one of its lines is used). An optional effect of the Agent turn offers no
refusal, and the turn's end lapses it (OQ-095 (2), user ruling
2026-10-14), so one that cannot be used now offers no row at all: it shows
greyed out with its block and says it lapses (Smuggler's Haven short of
spice, a Signet Ring payment, a Sardaukar Commander short of Solari, a
Landsraad visit's Tech with no tile in reach, among them), under
"waiting" while another effect of the turn could still enable it.

Display only, under four rules:

- Legality comes only from the engine's legal list. A candidate is dropped
  whenever its action is in that list, and a table ref whenever a legal
  action names it, so a disagreement could only hide a greyed-out row, never
  grey out something the seat may do.
- A reason is worked out only for a candidate that is not legal, from the
  block predicate the legal provider itself uses (``AcquireBlock``,
  ``option_unplayable_reason``, ``rewards_with_no_effect``,
  ``intrigue_play_block``,
  ``waiting_deferred_choices``, ``reveal_choice_effect_is_available``,
  ``agent_box_is_waiting``,
  ``joinable_subcommittees``, ``reveal_sandworm_block``,
  ``imperial_privilege_recall_targets``, ``contract_recall_targets``,
  ``research_bonus_block``, ``research_influence_factions``,
  ``shipping_influence_factions``, ``combat_reward_influence_block``,
  ``unit_loss_block``, ``conflict_end_trigger_block``,
  ``skill_choice_block``, ``tech_candidates``,
  ``combat_reward_payment_block``, ``combat_reward_spy_recall_block``,
  ``maker_sandworm_block``, ``desert_riding_block``,
  ``sietch_tabr_wall_block``, ``leader_reveal_block``,
  ``agent_icon_block``, ``agent_card_recall_targets``,
  ``agent_card_payment_block``, ``signet_influence_withheld``,
  ``reveal_influence_choice_blocked``,
  ``contract_take_block``, ``turn_start_is_open``,
  ``intrigue_effects_finish_is_open``, and for an optional effect of the
  Agent turn that offers nothing ``agent_card_cost_block``,
  ``agent_card_trash_block``, ``agent_card_acquisition_block``,
  ``signet_optional_block``, ``imperial_privilege_trade_block``,
  ``desert_tactics_block``, ``sardaukar_commander_block``,
  ``landsraad_tech_block`` and ``leader_board_repeat_block``), so the two
  cannot drift.
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
    AcquireCardUpTo,
    AcquireReserveCard,
    AcquireTech,
    AdvanceTleilaxu,
    CommanderDiscountThisTurn,
    Cost,
    DeployFromGarrison,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainInfluence,
    GainSolariPerUnitType,
    GenerateSpecimens,
    GiveIntrigueToOpponent,
    GrantAgentIconsThisTurn,
    GrantAgentIconThisTurn,
    GrantCombatDeployment,
    IgnoreInfluenceRequirementsThisTurn,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    OnTroopsLostAtConflictEnd,
    PassTurn,
    PayResources,
    PeekTopCard,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RedirectSpiesOnTurnSpace,
    Research,
    RetreatTroops,
    RevealContractsTakeOne,
    Reward,
    SetAsideImperiumRowCard,
    SummonSandworm,
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
from dune_imperium.content.uprising.types import (
    OPTIONAL_REVEAL_CHOICES,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
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
from dune_imperium.display.leaders_ko import LEADER_FACE_TEXTS_KO
from dune_imperium.rules.acquisition import (
    AcquireBlock,
    agent_card_acquisition_block,
    imperium_acquisition_block,
    manipulated_acquisition_block,
    manipulated_cost,
    reserve_acquisition_block,
    reserve_cost,
    revealer_persuasion,
)
from dune_imperium.rules.agent_effect_frame import (
    active_box_can_act,
    agent_box_is_waiting,
)
from dune_imperium.rules.agent_effects import (
    AGENT_ICON_TRASH,
    AUTOMATIC_AGENT_ICONS,
    AgentIconBlock,
    AgentIconCondition,
    AgentPaymentBlock,
    agent_box_influence_blocked,
    agent_card_cost_block,
    agent_card_payment_block,
    agent_card_recall_targets,
    agent_card_trash_block,
    agent_icon_block,
    box_in_progress,
    box_is_optional,
)
from dune_imperium.rules.agent_turn import turn_start_cards
from dune_imperium.rules.board_effects import (
    BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
    BOARD_ICON_TRASH,
    MAKER_SANDWORM_SPACE_IDS,
    desert_riding_block,
    desert_riding_offered_at,
    desert_tactics_block,
    imperial_privilege_recall_targets,
    imperial_privilege_trade_block,
    legal_shipping_actions,
    maker_sandworm_block,
    pending_maker_space,
    pending_sietch_tabr,
    shipping_influence_factions,
    sietch_tabr_wall_block,
)
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.combat import (
    CombatInfluenceBlock,
    ConflictEndTriggerBlock,
    combat_reward_influence_block,
    combat_reward_payment_block,
    combat_reward_spy_recall_block,
    conflict_end_trigger_block,
)
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
    agent_placement_ahead,
    applicable_sections,
    condition_holds,
    face_up_conflict_card_ids,
    option_unplayable_reason,
    resource_cost,
    rewards_with_no_effect,
    spy_placement_allowed_post_ids,
    spy_placement_targets,
)
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    BOARD_ICON_TECH,
    OPTIONAL_BOARD_ICONS,
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    agent_turn_space_id,
    current_agent_effect_context,
    eligible_agent_contract_ids,
    pending_agent_icons,
    pending_board_icons,
    pending_boost_draws,
)
from dune_imperium.rules.frames import FrameKind, turn_owner_of, turn_start_is_open
from dune_imperium.rules.graft_boxes import (
    active_box,
    box_is_pending,
    is_grafted_turn,
    state_with_active_box,
    tagged,
)
from dune_imperium.rules.immortality import (
    SEVEN_SOLARI_COST,
    ResearchBonusBlock,
    research_bonus_block,
    research_influence_factions,
)
from dune_imperium.rules.influence import influence_amount, influence_can_rise
from dune_imperium.rules.intrigue import (
    IntriguePlayBlock,
    intrigue_effects_finish_is_open,
    intrigue_play_block,
    intrigue_window,
)
from dune_imperium.rules.leader_abilities import (
    leader_board_repeat_block,
    leader_reveal_block,
    signet_influence_withheld,
    signet_optional_block,
    units_deployment_blocked,
)
from dune_imperium.rules.owed_draws import legal_owed_draw_actions
from dune_imperium.rules.reveal_turn import (
    COMMAND_PERSUASION,
    GENERATED_PERSUASION_KEY,
    RevealSandwormBlock,
    pending_choice_entries,
    reveal_choice_effect_is_available,
    reveal_influence_choice_blocked,
    reveal_sandworm_block,
    waiting_choice_action,
    waiting_deferred_choices,
)
from dune_imperium.rules.sardaukar import (
    face_up_skill_identities,
    sardaukar_commander_block,
    skill_choice_block,
)
from dune_imperium.rules.scouts_effects import legal_subcommittee_choice_actions
from dune_imperium.rules.spies import (
    legal_gather_intelligence_actions,
)
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    solo_occupied_post_ids,
)
from dune_imperium.rules.tech import landsraad_tech_block, tech_candidates
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
# Desert Riding's token is one of the four Maker Hooks, so a seat that holds
# Maker Hooks cannot take it (OQ-079 (b)).
_MAKER_HOOKS_HELD: Final[Reason] = (
    "You already hold Maker Hooks",
    "이미 가진 {maker_hooks}",
    "held",
)
_WALL_DESTROYED: Final[Reason] = (
    "The Shield Wall is already destroyed",
    "{shield_wall}이 이미 파괴됨",
    "condition",
)
_NO_OTHER_AGENT: Final[Reason] = (
    "No other Agent of yours to recall (not the one sent this turn)",
    "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외)",
    "no_target",
)
_NO_INTRIGUE_TO_TRASH: Final[Reason] = (
    "No Intrigue card to trash",
    "폐기할 {intrigue_card} 없음",
    "cost",
)
_AT_THE_TOP: Final[Reason] = ("Already at the top", "이미 최고치", "top")
# A cost for Influence no cube can take is not offered, and a "choose a
# Faction" gain with every cube at the top waits or is lost (OQ-060, OQ-071).
_ALL_AT_THE_TOP: Final[Reason] = (
    "Every Faction it can raise is already at the top (6)",
    "올릴 수 있는 {faction}의 {influence_any}이 모두 이미 최고치(6)",
    "top",
)
_NAMED_FOR_THIS_REWARD: Final[Reason] = (
    "Already named for this reward",
    "이 보상에서 이미 고른 진영",
    "named",
)
_NO_UNIT_TO_LOSE: Final[Reason] = ("No unit to lose", "잃을 유닛 없음", "no_unit")
# A reward that would change nothing keeps its cost line off the list
# (OQ-071): the draw of an empty deck and discard pile (Gather Intelligence,
# OQ-099; Ecological Testing Station) and a Tleilaxu advance from the
# track's last space (OQ-048).
_NO_CARD_TO_DRAW: Final[Reason] = (
    "No card to draw: your deck and discard pile are both empty",
    "뽑을 카드 없음: 덱과 버린 카드 더미가 모두 비었음",
    "empty",
)
_TLEILAXU_TRACK_END: Final[Reason] = (
    "Your Tleilaxu token is already at the end of its track",
    "{tleilaxu} 트랙 끝에 이미 도달함",
    "reward",
)
_LAPSES_EN: Final = "; it lapses if still unmet when the turn ends"
_LAPSES_KO: Final = " — 차례가 끝날 때까지 못 채우면 사라짐"
_ALL_AT_THE_TOP_WAITING: Final[Reason] = (
    _ALL_AT_THE_TOP[0] + _LAPSES_EN,
    _ALL_AT_THE_TOP[1] + _LAPSES_KO,
    "waiting",
)
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


def _conflict_end_reason(option: IntrigueOption) -> Reason:
    """Harvest Cells in any Intrigue window: played only in the window after
    the Conflict's rewards, when its loss holds (user ruling 2026-10-06,
    ``IntriguePlayBlock.CONFLICT_END``)."""

    trigger = option.trigger
    assert isinstance(trigger, OnTroopsLostAtConflictEnd)
    lost = trigger.minimum
    return (
        f"Played after the Conflict resolves, if you lose {lost} or more troops",
        f"{{conflict}}이 끝난 뒤 {{troop}}을 {lost} 이상 잃었을 때 사용",
        "timing",
    )


# Harvest Cells in its own window when one more copy could change nothing
# (``ConflictEndTriggerBlock``): its specimens come from troops back in the
# supply after the cleanup, and lost Sardaukar Commanders go back to their
# own supply and make none (``combat._harvest_cells_has_effect``).
_NO_TROOP_FOR_A_SPECIMEN: Final[Reason] = (
    "No troop in your supply or the Conflict to make a specimen",
    "{specimen}으로 만들 {troop}이 {supply}에도 {conflict}에도 없음",
    "reward",
)
_TROOPS_TAKEN_FOR_SPECIMENS: Final[Reason] = (
    "The copy already played takes every troop left to make a specimen",
    "먼저 쓴 카드가 {specimen}으로 만들 {troop}을 모두 가져감",
    "reward",
)
_COMMANDERS_MAKE_NONE: Final = (
    " (Sardaukar Commanders make none)",
    " ({commander}은 {specimen}이 되지 않음)",
)
_NO_TLEILAXU_CARD_TO_ACQUIRE: Final[Reason] = (
    "No Tleilaxu card your specimens could acquire",
    "{specimen}으로 획득할 수 있는 {tleilaxu} 카드 없음",
    "reward",
)


def _conflict_end_trigger_reason(
    state: GameState,
    seat: int,
    option: IntrigueOption,
    block: ConflictEndTriggerBlock | OptionUnplayable,
) -> Reason:
    """Word ``conflict_end_trigger_block``'s answer for a held Harvest Cells
    the Conflict-end window does not offer."""

    if not isinstance(block, ConflictEndTriggerBlock):
        return intrigue_option_reason(state, seat, option, block)
    owner = state.players[seat]
    if block is ConflictEndTriggerBlock.LOSS:
        english, korean, _ = _conflict_end_reason(option)
        lost = _units(owner)[1]
        return (
            f"{english} (you lose {lost} unit{plural_s(lost)})",
            f"{korean} (잃는 유닛 {lost})",
            "condition",
        )
    english, korean, code = (
        _NO_TROOP_FOR_A_SPECIMEN
        if block is ConflictEndTriggerBlock.NO_TROOP
        else _TROOPS_TAKEN_FOR_SPECIMENS
    )
    if owner.commanders_conflict:
        english += _COMMANDERS_MAKE_NONE[0]
        korean += _COMMANDERS_MAKE_NONE[1]
    # Both of its effects are dead, each explained, as ``_no_effect_reason``
    # joins them.
    return (
        f"{english}; {_NO_TLEILAXU_CARD_TO_ACQUIRE[0]}",
        f"{korean} · {_NO_TLEILAXU_CARD_TO_ACQUIRE[1]}",
        code,
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
        case AcquireBlock.TLEILAXU_TRACK_END:
            return _TLEILAXU_TRACK_END
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
                "다른 {intrigue_card} 필요",
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


_DEPLOYMENT_BARRED: Final[Reason] = (
    "Emperor of the Known Universe bars deploying units this turn",
    f"{LEADER_FACE_TEXTS_KO['shaddam_corrino_iv'].signet_name}: "
    "이번 차례에는 유닛을 배치할 수 없음",
    "reward",
)
_BEFORE_THE_AGENT: Final[Reason] = (
    "Only before you send an Agent this turn",
    "이번 차례에 {agent}를 보내기 전에만",
    "reward",
)
# Call to Arms in the owner's Reveal turn once nothing is left to acquire in
# it (``OptionBlock.NO_ACQUISITION_AHEAD``, user ruling 2026-10-06).
_NO_ACQUISITION_AHEAD: Final[Reason] = (
    "Nothing left to acquire in this Reveal turn",
    "이번 공개 차례에 더 획득할 수 있는 카드 없음",
    "reward",
)


def _deploy_reason(state: GameState, seat: int) -> Reason:
    """Why a "deploy from your garrison" line has nothing it may deploy
    (``effect_interpreter.deployable_garrison_units``)."""

    if units_deployment_blocked(state, seat):
        return _DEPLOYMENT_BARRED
    owner = state.players[seat]
    if owner.troops_garrison + owner.commanders_garrison == 0:
        return troops_reason("garrison", 1, 0)
    # Units in the garrison, none of them deployable: Harkonnen Advisor's
    # troop ("You can't deploy this troop to the Conflict this turn."
    # [Piter De Vries card], OQ-038).
    only = (
        "Your only garrison troop"
        if owner.troops_garrison == 1
        else "Your garrison troops"
    )
    return (
        f"{only} cannot deploy this turn",
        "{garrison}의 {troop}은 이번 차례에 배치할 수 없음",
        "reward",
    )


def _sandworm_reward_reason(
    state: GameState, seat: int, reward: SummonSandworm
) -> Reason:
    """Why a summoned sandworm could not land (in the interpreter's order)."""

    owner = state.players[seat]
    if not state.current_conflict_ids:
        return _NO_CONFLICT
    if units_deployment_blocked(state, seat):
        return _DEPLOYMENT_BARRED
    if reward.requires_maker_hooks and not owner.maker_hooks:
        return _NO_MAKER_HOOKS
    return _SHIELD_WALL


def _tech_reward_reason(state: GameState, seat: int, discount: int) -> Reason:
    """Why a card's Acquire Tech has no tile the owner can buy."""

    owner = state.players[seat]
    candidates = tech_candidates(state, owner)
    if not candidates:
        return _TECH_STACKS_EMPTY
    if not owner.spy_post_ids and all(
        tile.acquire_requires_spy_trash for tile, _ in candidates
    ):
        return (
            "Advanced Data Analysis needs a Spy of yours on the board to trash",
            "고급 데이터 분석은 보드에 있는 내 {spy}를 폐기해야 함",
            "reward",
        )
    return (
        f"No Tech tile you can afford ({discount} spice off)",
        f"살 수 있는 {{tech_tile}} 없음 ({{spice:{discount}}} 할인 포함)",
        "reward",
    )


def _spy_reward_reason(state: GameState, seat: int, reward: PlaceSpy) -> Reason:
    """Why a Spy placement cannot happen (``spy_placement_possible``)."""

    owner = state.players[seat]
    if (
        owner.spies_supply == 0
        and owner.spies_recalled_turn > 0
        and not spy_placement_targets(state, seat, reward)
        and solo_occupied_post_ids(
            state, seat, spy_placement_allowed_post_ids(reward)
        )
    ):
        # OQ-101 (b): the recall-and-replace changes nothing once a Spy was
        # already recalled this turn.
        return (
            "You already recalled a Spy this turn;"
            " recalling and replacing it would change nothing",
            "이번 차례에 이미 {spy}를 회수함 — 회수해 다시 놓아도 바뀌는 것 없음",
            "reward",
        )
    return (
        "No observation post for a Spy",
        "{spy}를 놓을 {observation_post} 없음",
        "reward",
    )


def _choice_reward_reason(state: GameState, seat: int, reward: Reward) -> Reason:
    """Why a reward blocks its option: it cannot be resolved at all
    (``_choice_reward_block``) or it, the first in printed order, cannot
    change anything while no other reward can either (``_no_effect_block``,
    user ruling 2026-10-06)."""

    owner = state.players[seat]
    match reward:
        case DeployFromGarrison():
            return _deploy_reason(state, seat)
        case DrawPersonalCards():
            return _NO_CARD_TO_DRAW
        case Research():
            return (
                "Past the second genetic marker Research draws a card,"
                " and your deck and discard pile are both empty",
                "두 번째 유전자 표지 뒤의 {research}는 카드를 뽑는데"
                " {deck}과 {discard_pile}이 모두 비었음",
                "empty",
            )
        case DrawIntrigueCards():
            return (
                "No Intrigue card to draw: the Intrigue deck is empty"
                " and its discard pile holds nothing to shuffle",
                "뽑을 {intrigue_card} 없음: 책략 카드덱이 비었고"
                " 버린 더미에 섞을 카드 없음",
                "empty",
            )
        case RecruitTroops():
            english, korean, _ = troops_reason("supply", 1, owner.troops_supply)
            return english, korean, "reward"
        case GenerateSpecimens():
            return (
                "No troop in your supply to make a specimen",
                "{specimen}로 만들 {troop}이 {supply}에 없음",
                "reward",
            )
        case AdvanceTleilaxu():
            return _TLEILAXU_TRACK_END
        case AcquireCardUpTo(max_cost=max_cost):
            return (
                f"No card costing {max_cost} or less to acquire",
                f"획득할 수 있는 비용 {max_cost} 이하 카드 없음",
                "reward",
            )
        case AcquireTech(discount=discount):
            return _tech_reward_reason(state, seat, discount)
        case AcquireReserveCard():
            return _EMPTY_STACK
        case SummonSandworm():
            return _sandworm_reward_reason(state, seat, reward)
        case GainSolariPerUnitType():
            return (
                "No unit of yours in the Conflict",
                "{conflict}에 내 유닛 없음",
                "reward",
            )
        case PassTurn():
            return (
                "Every other player has revealed: the turn would come straight"
                " back to you",
                "다른 플레이어가 모두 공개를 마쳐 차례가 바로 돌아옴",
                "reward",
            )
        case GrantAgentIconThisTurn() | GrantAgentIconsThisTurn():
            return _BEFORE_THE_AGENT
        case IgnoreInfluenceRequirementsThisTurn():
            if not agent_placement_ahead(state, seat):
                return _BEFORE_THE_AGENT
            return (
                "No board space's Influence requirement is unmet",
                "못 채운 {influence_any} 조건이 있는 공간 없음",
                "reward",
            )
        case CommanderDiscountThisTurn():
            return (
                "No Sardaukar Commander left to recruit this turn",
                "이번 차례에 고용할 {commander} 없음",
                "reward",
            )
        case GrantCombatDeployment():
            return (
                "Nothing could deploy through it this turn",
                "이번 차례에 이것으로 배치할 유닛 없음",
                "reward",
            )
        case PlaceSpy():
            return _spy_reward_reason(state, seat, reward)
        case RetreatTroops(minimum=minimum):
            # The gate asks for one unit even of a zero-minimum retreat.
            return _in_conflict_reason(max(minimum, 1), _units(owner)[1])
        case TakeContract() if not state.config.choam_module:
            return "No Contracts in this game", "이 게임에는 {contract} 없음", "reward"
        case TakeContract():
            return (
                "No Contract you can take: only the Immediate is left and you"
                " hold no other Intrigue card to trash",
                "가져갈 {contract} 없음: 즉시 {contract}만 남았고"
                " 폐기할 다른 {intrigue_card} 없음",
                "reward",
            )
        case SetAsideImperiumRowCard():
            return "The Imperium Row is empty", "{imperium_row}이 비었음", "reward"
        case PeekTopCard():
            return "Your deck is empty", "{deck}이 비었음", "reward"
        case TrashPersonalCard(hand_only=True):
            return "No card in hand to trash", "{hand}에 {trash}할 카드 없음", "reward"
        case TrashPersonalCard():
            return (
                "No card in hand, discard pile or play to trash",
                "{hand}·{discard_pile}·{in_play}에 {trash}할 카드 없음",
                "reward",
            )
        case GainInfluence(where_opponent_leads=True):
            return (
                "No Faction where an opponent has more Influence",
                "상대가 더 높은 {faction} 없음",
                "reward",
            )
        case GainInfluence(factions=factions) if not any(
            influence_can_rise(owner, faction)
            for faction in (factions or tuple(Faction))
        ):
            return _ALL_AT_THE_TOP
        case GainInfluence():
            return (
                "No Faction you may gain Influence with",
                "{influence_any}을 얻을 수 있는 {faction} 없음",
                "reward",
            )
        case RedirectSpiesOnTurnSpace() if (
            agent_turn_space_id(state, seat) is None
        ):
            return (
                "Only after you send an Agent this turn",
                "이번 차례에 {agent}를 보낸 뒤에만",
                "reward",
            )
        case RedirectSpiesOnTurnSpace():
            return (
                "No opponent Spy and no empty post connected to that space",
                "그 공간에 연결된 상대 {spy}도 빈 {observation_post}도 없음",
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
    return _WALL_DESTROYED


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
        case OptionBlock.NO_ACQUISITION_AHEAD:
            return _NO_ACQUISITION_AHEAD
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
                return _no_effect_reason(state, seat, sections, reward)
    return NOT_NOW


def _no_effect_reason(
    state: GameState, seat: int, sections: tuple[EffectSection, ...], blamed: Reward
) -> Reason:
    """The blamed reward's reason, or, when no reward of the option can
    change anything (``rewards_with_no_effect``), each distinct reward's
    reason joined, so a card with two dead halves explains both (Mercenaries'
    Intrigue draw and recruit, Honor Guard's troop and discount)."""

    dead = rewards_with_no_effect(state, seat, sections)
    if not any(reward is blamed for reward in dead):
        return _choice_reward_reason(state, seat, blamed)
    reasons: list[Reason] = []
    for reward in dead:
        reason = _choice_reward_reason(state, seat, reward)
        if reason not in reasons:
            reasons.append(reason)
    if len(reasons) == 1:
        return reasons[0]
    return (
        "; ".join(english for english, _, _ in reasons),
        " · ".join(korean for _, korean, _ in reasons),
        # A fallback among them keeps its code, so the tests still catch it.
        NOT_NOW_CODE
        if any(code == NOT_NOW_CODE for _, _, code in reasons)
        else "reward",
    )


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
        title_card: str | None = None,
        reveal_choice: str | None = None,
    ) -> None:
        """One candidate row. ``title_card``: a revealed card that leads the
        row's words (its ``detail_title``), for a row whose action names no
        card; ``reveal_choice``: the pending Reveal choice the row belongs
        to (``display.actions.reveal_choice_key``), whose header the page
        sets it under."""

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
        if title_card is not None:
            row["title_card"] = title_card
        if reveal_choice is not None:
            row["reveal_choice"] = reveal_choice
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
    card_block = reclaimed_forces_block(owner)
    for choice in RECLAIMED_FORCES_CHOICES:
        block = reclaimed_forces_block(owner, choice)
        if block is None:
            continue
        found.row(
            "acquire",
            f"reclaimed_forces:{choice}",
            DomainAction(
                action_id="acquire_reclaimed_forces",
                actor=seat,
                arguments=(("choice", choice),),
            ),
            _acquire_reason(block, RECLAIMED_FORCES.specimen_cost, owner.specimens),
            # Only a block of the whole card dims it on the table; one choice
            # withheld (the Tleilaxu advance at the track's end) leaves the
            # other to take.
            dim="reclaimed_forces" if card_block is not None else None,
        )


def _intrigue(state: GameState, seat: int, found: _Found) -> None:
    """The seat's own Intrigue cards in an open Intrigue window.

    An option failing on its cost or condition, or with no effect that
    could change anything now, is a row; one printed for another window is
    not (it would be noise every turn), only its card's dim
    (``intrigue_play_block``'s timing blocks).
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
            if block is IntriguePlayBlock.CONFLICT_END:
                other_window = other_window or _conflict_end_reason(option)
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


def _conflict_end_trigger(state: GameState, seat: int, found: _Found) -> None:
    """A held Harvest Cells the Conflict-end window does not offer.

    The window opens on public facts (OQ-103, user decision 2026-10-09), so
    a seat may sit in it holding a copy it cannot play: the window then
    offers only the decline, or, once a first copy is face up, no second.
    The provider offers ``play_conflict_end_intrigue`` for a hand card
    exactly when ``conflict_end_trigger_block`` is None; any other shows
    greyed out among the Intrigue cards with that block, and dims in the
    hand, as it does in a Combat Intrigue window (``_conflict_end_reason``).
    Only the first such option of a card counts, as for the provider
    (``combat._loss_trigger_option``).
    """

    for card_id in state.players[seat].intrigue_cards:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        option = next(
            (
                option
                for option in (entry.options if entry is not None else ())
                if isinstance(option.trigger, OnTroopsLostAtConflictEnd)
            ),
            None,
        )
        if option is None:
            continue
        block = conflict_end_trigger_block(state, seat, option)
        if block is None:
            continue
        found.row(
            "intrigue",
            card_id,
            DomainAction(
                action_id="play_conflict_end_intrigue",
                actor=seat,
                arguments=(("card_id", card_id),),
            ),
            _conflict_end_trigger_reason(state, seat, option, block),
            dim=card_id,
        )


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


# --- A Reveal's pending choices that offer nothing now -------------------------
#
# Every choice of a revealed card waits on the Reveal frame and is offered
# there while it can be taken (OQ-095 (7) addition, user ruling 2026-10-14,
# codec v147). One that offers nothing now is shown greyed out as that card's
# choice, with what keeps it closed: its printed condition, judged by the
# engine's own gate (``reveal_choice_effect_is_available``) on the facts it
# reads, or nothing to choose. When the Reveal ends every choice still
# pending lapses (``reveal_choice_lapsed``): an optional one ("may", an arrow
# cost or a black trash icon [FAQ p. 3]) unused, a mandatory one unmet.

_Choice = PersonalCardRevealChoiceEffect
_REVEAL_LAPSES_UNUSED: Final = (
    "; it lapses unused when the Reveal turn ends",
    " — {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
)
_REVEAL_LAPSES_UNMET: Final = (
    "; it lapses if still unmet when the Reveal turn ends",
    " — {reveal_turn}를 끝낼 때까지 못 채우면 사라짐",
)
# "Command (6+ Persuasion)" choices, judged on the Persuasion the Reveal
# turn generates [Bloodlines pp. 5, 12].
_COMMAND_CHOICES: Final = frozenset(
    {
        _Choice.COMMAND_PLACE_SPY,
        _Choice.COMMAND_GAIN_CHOSEN_INFLUENCE,
        _Choice.COMMAND_MAY_TRASH_CARD,
        _Choice.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD,
    }
)
_RETREAT_TWO: Final = frozenset(
    {
        _Choice.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH,
        _Choice.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION,
    }
)
_TWO_SPY_RECALLS: Final = frozenset(
    {
        _Choice.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
        _Choice.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION,
    }
)
_SPY_ICONS: Final = frozenset(
    {
        _Choice.PLACE_SPY,
        _Choice.PLACE_TWO_SPIES,
        _Choice.COMMAND_PLACE_SPY,
        _Choice.PLACE_SPY_OR_GAIN_TWO_STRENGTH,
    }
)
# A choice whose card another effect trashed: "you can't receive or
# activate an effect from a card that is already trashed" (designer ruling,
# OQ-022). It never opens again, so it simply lapses when the Reveal ends.
_NOT_IN_PLAY: Final[Reason] = (
    "This card is no longer in play",
    "이 카드가 더는 {in_play}에 없음",
    "waiting",
)
_REVEAL_LAPSES_GONE: Final = (
    "; it lapses when the Reveal turn ends",
    " — {reveal_turn}를 끝내면 사라짐",
)
_NOTHING_TO_CHOOSE: Final[Reason] = (
    "Nothing it could choose now",
    "지금 고를 수 있는 것이 없음",
    "waiting",
)


def _spies_reason(needed: int, held: int, code: str = "waiting") -> Reason:
    en, ko = held_text(held)
    spies = "Spy" if needed == 1 else "Spies"
    return (
        f"Needs {needed} {spies} of yours on the board{en}",
        f"보드에 내 {{spy:{needed}}} 필요{ko}",
        code,
    )


def _reveal_generated_persuasion(state: GameState) -> int:
    """The Persuasion the open Reveal turn has generated so far (Command)."""

    context = dict(state.decision_stack[-1].context)
    value = context.get(GENERATED_PERSUASION_KEY, context.get("persuasion"))
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _reveal_choice_block(
    state: GameState, seat: int, card_id: str, effect: PersonalCardRevealChoiceEffect
) -> Reason:
    """What keeps one pending Reveal choice from offering anything now.

    A card another effect trashed first: its choice never opens again
    (OQ-022). Then in the order its card prints it: Command (6+) first, then
    the line's own condition, the facts ``_reveal_choice_effect_is_available``
    reads. A choice whose condition holds offers nothing only when nothing
    can be chosen (a Spy icon with no empty post).
    """

    owner = state.players[seat]
    if card_id not in owner.in_play:
        return _NOT_IN_PLAY
    in_play = counted_in_play(owner)
    generated = _reveal_generated_persuasion(state)
    if effect in _COMMAND_CHOICES and generated < COMMAND_PERSUASION:
        return (
            f"Command: needs {COMMAND_PERSUASION} Persuasion generated this"
            f" Reveal turn (you have {generated})",
            f"{{command}}: 이번 {{reveal_turn}}에 만든"
            f" {{persuasion:{COMMAND_PERSUASION}}} 필요 (지금 {generated})",
            "waiting",
        )
    open_now = reveal_choice_effect_is_available(
        state, seat, owner, in_play, card_id, effect, persuasion=generated
    )
    if open_now:
        if effect in _SPY_ICONS and not empty_observation_post_ids(state):
            return (
                "No empty observation post for your Spy",
                "{spy}를 놓을 빈 {observation_post} 없음",
                "waiting",
            )
        return _NOTHING_TO_CHOOSE
    units_conflict = owner.troops_conflict + owner.commanders_conflict
    match effect:
        case _Choice.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE:
            if Faction.BENE_GESSERIT.value not in owner.alliance_faction_ids:
                return (
                    "Needs the Bene Gesserit Alliance",
                    "베네 게세리트 {alliance} 필요",
                    "waiting",
                )
            return (
                "Needs 2 Influence with one Faction to lose",
                "한 {faction}에 잃을 {influence_any} 2 필요",
                "waiting",
            )
        case _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND if (
            not has_faction_bond(in_play, card_id, Faction.FREMEN)
        ):
            return (
                "Fremen Bond: needs another Fremen card in play",
                "프레멘의 유대감: {in_play}에 다른 프레멘 카드 필요",
                "waiting",
            )
        case (
            _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP
            | _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND
        ):
            return (
                "No troop of yours in the garrison or the Conflict",
                "{garrison}에도 {conflict}에도 내 {troop} 없음",
                "waiting",
            )
        case _Choice.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS:
            en, ko = held_text(owner.troops_garrison + owner.troops_conflict)
            return (
                f"Needs 2 troops in your garrison or the Conflict{en}",
                f"{{garrison}}·{{conflict}}에 {{troop:2}} 필요{ko}",
                "waiting",
            )
        case _Choice.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH if len(owner.tech_ids) < 2:
            en, ko = held_text(len(owner.tech_ids))
            return (
                f"Needs 2 Tech tiles{en}",
                f"{{tech_tile}} 2개 필요{ko}",
                "waiting",
            )
        case _Choice.MAY_PAY_THREE_SPICE_FOR_INFLUENCE if owner.resources.spice < 3:
            english, korean, _ = resource_reason("spice", 3, owner.resources.spice)
            return english, korean, "waiting"
        case choice if reveal_influence_choice_blocked(owner, choice):
            return _ALL_AT_THE_TOP[0], _ALL_AT_THE_TOP[1], "waiting"
        case choice if choice in _RETREAT_TWO:
            english, korean, _ = _in_conflict_reason(2, units_conflict)
            return english, korean, "waiting"
        case _Choice.MAY_RECALL_SPY_FOR_THREE_STRENGTH:
            return _spies_reason(1, len(owner.spy_post_ids))
        case choice if choice in _TWO_SPY_RECALLS:
            return _spies_reason(2, len(owner.spy_post_ids))
        case _Choice.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS if (
            len(owner.completed_contract_ids) < 4
        ):
            en, ko = held_text(len(owner.completed_contract_ids))
            return (
                f"Needs 4 completed Contracts{en}",
                f"완수한 {{contract}} 4개 필요{ko}",
                "waiting",
            )
        case _Choice.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD if (
            not state.imperium_row
        ):
            return ("The Imperium Row is empty", "{imperium_row}가 비었음", "waiting")
        case _Choice.COMMAND_MAY_TRASH_CARD:
            return (
                "No card in hand, discard pile or play to trash",
                "{hand}·{discard_pile}·{in_play}에 {trash}할 카드 없음",
                "waiting",
            )
        case _Choice.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE:
            return ("No Influence to lose", "잃을 {influence_any} 없음", "waiting")
        case _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH:
            return (
                "No other Emperor card in play to trash",
                "{in_play}에 {trash}할 다른 황제 카드 없음",
                "waiting",
            )
    return _NOTHING_TO_CHOOSE


def _deferred(state: GameState, seat: int, found: _Found) -> None:
    """Pending Reveal choices that offer nothing now (their printed
    condition fails, nothing can be chosen, or their card left play).

    Every choice of a revealed card waits on the Reveal frame and is offered
    there while it can be taken (OQ-095 (7) addition, codec v147); one that
    cannot shows here greyed out, as the never-legal
    ``waiting_choice_action`` row, led by its card and worded as the card's
    choice (``display.actions.reveal_choice_text``), with what keeps it
    closed (``_reveal_choice_block``) and that it lapses when the Reveal
    ends: unused for an optional one, unmet for a mandatory one, and
    without condition for one whose card another effect trashed (OQ-022).
    """

    for card_id, effect in waiting_deferred_choices(state, seat):
        choice = PersonalCardRevealChoiceEffect(effect)
        english, korean, code = _reveal_choice_block(state, seat, card_id, choice)
        tail_en, tail_ko = (
            _REVEAL_LAPSES_GONE
            if card_id not in state.players[seat].in_play
            else _REVEAL_LAPSES_UNUSED
            if choice in OPTIONAL_REVEAL_CHOICES
            else _REVEAL_LAPSES_UNMET
        )
        found.row(
            "waiting",
            f"{card_id}:{effect}",
            waiting_choice_action(seat, effect),
            (english + tail_en, korean + tail_ko, code),
            card_id=card_id,
            title_card=card_id,
            reveal_choice=f"{card_id}:{effect}",
        )


def _leader_reveal(state: GameState, seat: int, found: _Found) -> None:
    """A Leader's Reveal-turn ability that has nothing to act on yet.

    Lady Amber's Desert Scouts (retreat a troop) needs a unit in the Conflict
    and Feyd-Rautha's Devious Strength (recall a Spy for two swords) a Spy on
    the board; ``legal_leader_reveal_actions`` offers the ability exactly
    when ``leader_reveal_block`` is None. Otherwise its actions show greyed
    out under "waiting", with the block: Reveal effects are carried out in
    any order [Main p. 12], so another effect of the Reveal can still meet
    it (a deployment into the Conflict, a Spy placed), and the ability is an
    optional one that lapses unused when the Reveal turn ends, as a card's
    optional Reveal choice does (``_deferred``). Amber's Commander retreat
    shows only for a seat that owns a Sardaukar Commander.
    """

    block = leader_reveal_block(state, seat)
    if block is None:
        return
    english, korean, code = _optional_block_reason(block)
    tail_en, tail_ko = _REVEAL_LAPSES_UNUSED
    owner = state.players[seat]
    if owner.leader_id == "feyd_rautha_harkonnen":
        action_ids = ("recall_spy_for_leader",)
    else:
        action_ids = (
            "retreat_leader_troop",
            *(("retreat_leader_commander",) if owner.commanders_total else ()),
        )
    for action_id in action_ids:
        found.row(
            "waiting",
            f"leader_reveal:{action_id}",
            DomainAction(action_id=action_id, actor=seat),
            (english + tail_en, korean + tail_ko, code),
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

    The choice is offered to every seat, which may always take the
    Persuasion branch (option (B), user ruling 2026-09-30: "REVEAL_CHOICE
    창을 열어 '설득 2'만 고르게, 모래벌레 줄은 '메이커 작살 없음' 회색"); the
    sandworm branch is offered exactly when ``reveal_sandworm_block`` is
    None, and otherwise shows greyed out with that block, beside the pending
    choice's rows on the Reveal frame (codec v147), under its card's header
    (``reveal_choice``: the first copy's choice, which a shared row takes).
    """

    desert_power = PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM.value
    card_ids = tuple(
        card_id
        for (card_id, effect), rows in pending_choice_entries(state, seat) or ()
        if effect == desert_power and rows
    )
    if not card_ids:
        return
    block = reveal_sandworm_block(state, seat)
    if block is None:
        return
    found.row(
        "choice",
        "pay_reveal_water_for_sandworm",
        DomainAction(action_id="pay_reveal_water_for_sandworm", actor=seat),
        _sandworm_reason(state, seat, block),
        card_id=card_ids[0],
        reveal_choice=f"{card_ids[0]}:{desert_power}",
    )


def _maker_space(state: GameState, seat: int, found: _Found) -> None:
    """A Maker space's sandworm and Desert Riding branches while they cannot
    be taken.

    Deep Desert, Hagga Basin and Imperial Basin always offer their spice
    (``harvest_maker_spice``); the sandworm (Deep Desert, Hagga Basin) is
    offered exactly when ``maker_sandworm_block`` is None and Arrakeen
    Scouts' Desert Riding token (Hagga Basin, while it waits on the board)
    exactly when ``desert_riding_block`` is None. Each shows greyed out
    beside the spice with its block, worded as Desert Power's sandworm is
    (``reveal_sandworm_block``). Imperial Basin prints no sandworm and gets
    no row. The Maker icon is the visit's own choice, so a block no other
    effect of the turn lifts (the Hooks, the Conflict, the Shield Wall come
    from outside the turn) sits among the choices, with no lapse wording.
    """

    space_id = pending_maker_space(state, seat)
    if space_id is None:
        return
    if space_id in MAKER_SANDWORM_SPACE_IDS:
        block = maker_sandworm_block(state, seat)
        if block is not None:
            found.row(
                "choice",
                "summon_maker_sandworms",
                DomainAction(
                    action_id="summon_maker_sandworms",
                    actor=seat,
                    arguments=(("space_id", space_id),),
                ),
                _optional_block_reason(block),
            )
    if desert_riding_offered_at(state, space_id):
        block = desert_riding_block(state, seat)
        if block is not None:
            found.row(
                "choice",
                "take_desert_riding_hooks",
                DomainAction(
                    action_id="take_desert_riding_hooks",
                    actor=seat,
                    arguments=(("space_id", space_id),),
                ),
                _optional_block_reason(block),
            )


def _sietch_tabr(state: GameState, seat: int, found: _Found) -> None:
    """Sietch Tabr's "water and destroy the Shield Wall" once the Wall is gone.

    Supplies and plain water stay on offer; the detonation branch is offered
    exactly when ``sietch_tabr_wall_block`` is None, and otherwise shows
    greyed out beside them. A Shield Wall destroyed is gone for good, so
    nothing in the turn lifts the block.
    """

    if not pending_sietch_tabr(state, seat):
        return
    block = sietch_tabr_wall_block(state)
    if block is None:
        return
    found.row(
        "choice",
        "take_sietch_tabr_water_and_destroy_wall",
        DomainAction(action_id="take_sietch_tabr_water_and_destroy_wall", actor=seat),
        _optional_block_reason(block),
    )


def _imperial_privilege_recall(state: GameState, seat: int, found: _Found) -> None:
    """Imperial Privilege's recall when no other Agent can be recalled.

    The provider then offers only ``resolve_imperial_privilege_without_recall``
    (the recall is skipped, OQ-023; the card draw is the space's own
    ``cards`` icon, user ruling 2026-10-10), exactly when
    ``imperial_privilege_recall_targets`` is empty; the recall shows greyed
    out beside it with the reason, its plain label naming the recall alone.
    Targets never grow within one Agent turn, so the row cannot light up
    again.
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
    take_ko = "폐기할 {intrigue_card}가 생기면 가져감"
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

    c6r6's "Influence with any Faction" offers exactly the Factions in
    ``research_influence_factions``; each one at the top shows greyed out,
    as a Conflict reward's does (OQ-060), and with all four there only the
    decline is offered.
    """

    bonus = dict(state.decision_stack[-1].context).get("bonus")
    if not isinstance(bonus, str):
        return
    owner = state.players[seat]
    if ResearchBonus(bonus) is ResearchBonus.INFLUENCE_ANY:
        _influence_at_the_top(
            found,
            seat,
            "research_influence",
            "choose_research_influence",
            research_influence_factions(owner),
        )
        return
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
        case ResearchBonusBlock.TLEILAXU_TRACK_END:
            found.row(
                "choice",
                "research_bonus_pay",
                DomainAction(action_id="pay_research_bonus", actor=seat),
                _TLEILAXU_TRACK_END,
            )
        case None:
            pass


def _influence_at_the_top(
    found: _Found,
    seat: int,
    key: str,
    action_id: str,
    offered: tuple[Faction, ...],
) -> None:
    """Grey out every Faction a "choose a Faction" picker leaves out."""

    for faction in Faction:
        if faction in offered:
            continue
        found.row(
            "choice",
            f"{key}:{faction.value}",
            DomainAction(
                action_id=action_id,
                actor=seat,
                arguments=(("faction", faction.value),),
            ),
            _AT_THE_TOP,
        )


def _shipping_influence(state: GameState, seat: int, found: _Found) -> None:
    """Shipping's "Influence with a chosen Faction": every Faction at the
    top, greyed out beside the ones offered (OQ-060).

    Only while the icon is pending (``legal_shipping_actions`` offers
    something); ``shipping_influence_factions`` is the provider's own list.
    """

    if not legal_shipping_actions(state, seat):
        return
    _influence_at_the_top(
        found,
        seat,
        "shipping_influence",
        "choose_shipping_influence",
        shipping_influence_factions(state.players[seat]),
    )


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


def _combat_reward_payment(state: GameState, seat: int, found: _Found) -> None:
    """An optional Conflict reward's arrow the seat cannot pay now.

    "Each optional cost is its own arrow" [Main p. 9] [FAQ p. 3]: the window
    always offers the refusal, and the payment (a resource, or Arrakeen's two
    Spies recalled from the board) exactly when its block is None
    (``combat_reward_payment_block``, ``combat_reward_spy_recall_block``);
    otherwise it shows greyed out beside the refusal with what the seat is
    short of. The window's terms are fixed, so a shortfall cannot be made up
    inside it and the row sits among the choices that cannot be taken.
    """

    frame = state.decision_stack[-1]
    owner = state.players[seat]
    if frame.kind == FrameKind.COMBAT_REWARD_SPY_RECALL:
        action_id = "recall_spies_for_combat_reward"
        block = combat_reward_spy_recall_block(frame, owner)
    else:
        action_id = "pay_combat_reward"
        block = combat_reward_payment_block(frame, owner)
    if block is None:
        return
    found.row(
        "choice",
        action_id,
        DomainAction(action_id=action_id, actor=seat),
        _optional_block_reason(block),
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
        case AgentIconCondition.CONTRACTS_COMPLETED:
            return (
                f"Needs {needed} completed contracts (you have {held}){_LAPSES_EN}",
                f"완수한 {{contract}} {needed}개 필요 (완수 {held}){_LAPSES_KO}",
                "condition",
            )
        case AgentIconCondition.ALLIANCE if block.faction is Faction.FREMEN:
            # Stillsuit Manufacturer's return; tokens_ko.py's "프레멘 {alliance}".
            return (
                f"Needs the Fremen Alliance{_LAPSES_EN}",
                f"프레멘 {{alliance}} 필요{_LAPSES_KO}",
                "condition",
            )
        case AgentIconCondition.ALLIANCE if block.faction is None:
            return (
                f"Needs an Alliance{_LAPSES_EN}",
                f"{{alliance}} 필요{_LAPSES_KO}",
                "condition",
            )
        case AgentIconCondition.NOT_IN_PLAY:
            return (
                "A card borrowed with Usurp is not in play;"
                " it lapses when the turn ends",
                "찬탈로 빌린 카드는 {in_play}에 있지 않음 — 차례가 끝날 때 사라짐",
                "condition",
            )
        case AgentIconCondition.BOND if block.faction is Faction.BENE_GESSERIT:
            # Tread in Darkness's words [card face], tokens_ko.py's for KO.
            return (
                "Needs another Bene Gesserit card in play;"
                " it lapses when the turn ends",
                "{in_play}에 다른 베네 게세리트 카드 필요 — 차례가 끝날 때 사라짐",
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
# gained, spice gained, a marker reached, a contract completed, an
# Alliance formed): such an
# icon sits with the Agent boxes waiting on theirs (``_agent_box``), under
# "waiting". A card grafted or not stays so all turn, and an unprinted icon
# never comes.
_ICON_CAN_STILL_BE_MET: Final = frozenset(
    {
        AgentIconCondition.INFLUENCE,
        AgentIconCondition.SPICE_GAINED,
        AgentIconCondition.GENETIC_MARKERS,
        AgentIconCondition.CONTRACTS_COMPLETED,
        AgentIconCondition.ALLIANCE,
    }
)


def _agent_icons(state: GameState, seat: int, found: _Found) -> None:
    """A multi-icon Agent box's icons withheld while their condition fails.

    Such an icon is not offered and fizzles when the owner presses the
    turn's end (OQ-057 (1)); no window opens for it, it shows greyed out
    while the turn is open (user ruling 2026-10-02, L2-Q3: "③은 회색 줄만"
    -- Steersman Y'rkoon's Recall Agent icon with no target, and the other
    conditioned icons). The reasons come from the providers' own answers:
    ``agent_icon_block`` (an automatic icon, or Tread in Darkness's trash
    icon, is offered exactly when it is None) and
    ``agent_card_recall_targets`` (the recall is offered once per target).
    An icon whose condition a later effect of the turn can still meet
    (Influence, spice gained, genetic markers) sits under "waiting",
    like a single Agent box withheld by the same rule (``_agent_box``); one
    that cannot come back this turn (an ungrafted card, a lost Bond, a
    recall with no target -- targets never grow within one Agent turn)
    under "choice".
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
        if key not in (*AUTOMATIC_AGENT_ICONS, AGENT_ICON_TRASH):
            continue
        block = agent_icon_block(owner, context, effect, key)
        if block is None:
            continue
        found.row(
            "waiting" if block.condition in _ICON_CAN_STILL_BE_MET else "choice",
            f"agent_icon:{key}",
            # Tread in Darkness's trash icon is offered as its trash choices.
            DomainAction(action_id="trash_agent_card", actor=seat)
            if key == AGENT_ICON_TRASH
            else DomainAction(
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


_PAYMENT_BLOCK_REASONS: Final[Mapping[AgentPaymentBlock, Reason]] = {
    AgentPaymentBlock.NO_CARD_TO_DRAW: _NO_CARD_TO_DRAW,
    AgentPaymentBlock.TLEILAXU_TRACK_END: _TLEILAXU_TRACK_END,
}
# The payment an ``AgentPaymentBlock`` withholds, by the box's effect.
_WITHHELD_PAYMENTS: Final[Mapping[PersonalCardAgentEffect, str]] = {
    PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO: "pay_agent_card_water",
    PersonalCardAgentEffect.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU: (
        "pay_agent_card_two_specimens"
    ),
    (
        PersonalCardAgentEffect
        .GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU
    ): "pay_agent_card_five_solari_for_tleilaxu",
}


def _agent_box_payment(state: GameState, seat: int, found: _Found) -> None:
    """An Agent box's arrow withheld because its reward would do nothing.

    OQ-071: Ecological Testing Station's water with no card left to draw,
    Tleilaxu Surgeon's specimens and Slig Farmer's Solari with the Tleilaxu
    token at the track's end. ``agent_card_payment_block`` is the very test
    ``legal_agent_card_payment_actions`` makes before offering the payment.
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != seat:
        return
    if context.get("pending_agent_effect") is not True or pending_agent_icons(
        context
    ):
        return
    if box_is_optional(state):
        # Its own row says why it offers nothing (``_optional_agent_box``).
        return
    effect = active_agent_card(context).agent_effect
    block = agent_card_payment_block(state, seat, effect)
    if block is None or effect is None:
        return
    action_id = _WITHHELD_PAYMENTS[effect]
    card_id = context.get("card_id")
    found.row(
        "choice",
        f"agent_payment:{action_id}",
        DomainAction(action_id=action_id, actor=seat),
        _PAYMENT_BLOCK_REASONS[block],
        card_id=card_id if isinstance(card_id, str) else None,
    )


def _signet_influence(state: GameState, seat: int, found: _Found) -> None:
    """Emperor of the Known Universe's "3 Solari -> Influence" withheld
    because every cube is at the top (OQ-060, OQ-071).

    ``signet_influence_withheld`` holds exactly when
    ``legal_leader_signet_actions`` drops every Faction for want of a cube
    below the top (``influence_can_rise``, the filter it applies); the
    Solari and troop stay on offer beside the greyed row.
    """

    if not signet_influence_withheld(state, seat):
        return
    found.row(
        "choice",
        "leader_signet_influence",
        DomainAction(action_id="choose_leader_signet_influence", actor=seat),
        _ALL_AT_THE_TOP,
    )


def _agent_box(state: GameState, seat: int, found: _Found) -> None:
    """A mandatory Agent box withheld until its condition holds (OQ-057).

    ``agent_box_is_waiting`` is the very test the legal list makes before
    offering ``resolve_agent_card_effect``. An optional box that offers
    nothing has its own row (``_optional_agent_box``).
    """

    if not agent_box_is_waiting(state, seat) or box_is_optional(state):
        return
    _, context = current_agent_effect_context(state)
    card_id = context.get("card_id")
    found.row(
        "waiting",
        f"agent_box:{card_id}",
        DomainAction(action_id="resolve_agent_card_effect", actor=seat),
        # A "choose a Faction" box with every cube it may raise at the top
        # (OQ-060) waits like one whose condition fails.
        _ALL_AT_THE_TOP_WAITING
        if agent_box_influence_blocked(state, seat)
        else _WAITING,
        card_id=card_id if isinstance(card_id, str) else None,
    )


# --- Optional effects of the Agent turn that offer nothing now ---------------
#
# An optional effect -- "may", an arrow cost or a black trash icon [FAQ p. 3]
# -- offers no refusal in its owner's Agent turn, and the turn's end lapses
# it unused (OQ-095 (2), user ruling 2026-10-14). One that cannot be used
# now therefore offers no row at all; it shows greyed out with the block its
# provider gates it on, and says that it lapses. One that another effect of
# the turn could still enable sits with the waiting ones, in the plan's free
# order wording (docs/unavailable-options-plan.md 1: only whether another
# effect is left is asked, not whether it would help).

_LAPSES_UNUSED: Final = (
    "; it lapses unused when the turn ends",
    " — 차례가 끝나면 쓰지 않은 채 사라짐",
)
_FREE_ORDER: Final = (
    "; another effect of this turn can still meet it, and unused it lapses"
    " when the turn ends",
    " — 이번 차례의 다른 효과로 채우면 가능, 쓰지 않으면 차례가 끝날 때 사라짐",
)
_AFTER_THE_SPACE_LAPSES: Final = (
    "; unused, it lapses when the turn ends",
    " — 쓰지 않으면 차례가 끝날 때 사라짐",
)
# ``scouts_offers.BOARD_ICON_SUBCOMMITTEE`` (``effects.OPTIONAL_BOARD_ICONS``
# spells it the same way).
_SUBCOMMITTEE_ICON: Final = "scouts_subcommittee"
_FACTION_EN: Final[Mapping[str, str]] = {
    faction.value: faction.value.replace("_", " ").title() for faction in Faction
}
# docs/rules/glossary-ko.md "팩션과 영향력" [Main p. 20].
_FACTION_KO: Final[Mapping[str, str]] = {
    Faction.EMPEROR.value: "황제",
    Faction.SPACING_GUILD.value: "우주 항행 길드",
    Faction.BENE_GESSERIT.value: "베네 게세리트",
    Faction.FREMEN.value: "프레멘",
}
# Blocks no other effect of the same turn can lift.
_NEVER_THIS_TURN: Final = frozenset(
    {
        OptionalBlockKind.TLEILAXU_TRACK_END,
        OptionalBlockKind.NO_PARTNER,
        OptionalBlockKind.NOT_IN_PLAY,
        OptionalBlockKind.NO_FACTION_GAIN,
        OptionalBlockKind.FACTION_NEAR_TOP,
        OptionalBlockKind.NO_CONFLICT,
        OptionalBlockKind.DEPLOYMENT_BARRED,
        OptionalBlockKind.AGENT_LEFT,
        OptionalBlockKind.COMMANDER_GONE,
        OptionalBlockKind.TECH_STACKS_EMPTY,
    }
)
_OPTIONAL_REASONS: Final[Mapping[OptionalBlockKind, Reason]] = {
    OptionalBlockKind.INTRIGUE: _NO_INTRIGUE_TO_TRASH,
    OptionalBlockKind.NO_UNIT: _NO_UNIT_TO_LOSE,
    OptionalBlockKind.NO_UNIT_IN_CONFLICT: (
        "No unit of yours in the Conflict to retreat",
        "{conflict}에 후퇴할 내 유닛 없음",
        "no_unit",
    ),
    OptionalBlockKind.NO_COMMANDER_IN_CONFLICT: (
        "Needs a Sardaukar Commander of yours in the Conflict",
        "{conflict}에 내 {commander} 필요",
        "condition",
    ),
    OptionalBlockKind.NO_CARD_TO_TRASH: (
        "No card in hand, discard pile or play to trash",
        "{hand}·{discard_pile}·{in_play}에 {trash}할 카드 없음",
        "empty",
    ),
    OptionalBlockKind.NO_SPY_POST: (
        "No observation post where it could place your Spy",
        "{spy}를 놓을 {observation_post} 없음",
        "no_target",
    ),
    OptionalBlockKind.NO_EMPEROR_CARD: (
        "No other Emperor card in hand to trash",
        "{hand}에 {trash}할 다른 황제 카드 없음",
        "cost",
    ),
    OptionalBlockKind.MAKER_HOOKS: _NO_MAKER_HOOKS,
    OptionalBlockKind.NO_CARD_TO_DRAW: _NO_CARD_TO_DRAW,
    OptionalBlockKind.TECH_NEEDS_SPY: (
        "Advanced Data Analysis needs a Spy of yours on the board to trash",
        "고급 데이터 분석은 보드에 있는 내 {spy}를 폐기해야 함",
        "cost",
    ),
    OptionalBlockKind.TLEILAXU_TRACK_END: _TLEILAXU_TRACK_END,
    OptionalBlockKind.NO_PARTNER: (
        "The other grafted card is no longer in play",
        "{graft}한 다른 카드가 더 이상 {in_play}에 없음",
        "condition",
    ),
    OptionalBlockKind.NOT_IN_PLAY: (
        "This card is no longer in play",
        "이 카드가 더 이상 {in_play}에 없음",
        "condition",
    ),
    OptionalBlockKind.NO_FACTION_GAIN: (
        "No Influence of the visited space left for it to replace",
        "대신할 이 공간의 {influence_any} 획득이 남아 있지 않음",
        "condition",
    ),
    OptionalBlockKind.NO_CONFLICT: _NO_CONFLICT,
    OptionalBlockKind.DEPLOYMENT_BARRED: _DEPLOYMENT_BARRED,
    OptionalBlockKind.SHIELD_WALL: _SHIELD_WALL,
    OptionalBlockKind.NO_SHIELD_WALL: _WALL_DESTROYED,
    OptionalBlockKind.MAKER_HOOKS_HELD: _MAKER_HOOKS_HELD,
    OptionalBlockKind.AGENT_LEFT: (
        "The Agent sent this turn already left its space",
        "이번 차례에 보낸 {agent}가 이미 공간을 떠났음",
        "condition",
    ),
    OptionalBlockKind.COMMANDER_GONE: (
        "No Sardaukar Commander is left on this space",
        "이 공간에 남은 {commander} 없음",
        "empty",
    ),
    OptionalBlockKind.TECH_STACKS_EMPTY: _TECH_STACKS_EMPTY,
    OptionalBlockKind.AFTER_THE_SPACE: (
        "Only after the space's own effects are resolved",
        "이 공간의 효과를 모두 해결한 뒤에만",
        "timing",
    ),
}


def _optional_block_reason(block: OptionalEffectBlock) -> Reason:
    """Word an optional effect's block (``OptionalEffectBlock``), with a
    second block it also has joined as ``_no_effect_reason`` joins two."""

    reason = _one_optional_reason(block)
    if block.also is None:
        return reason
    other = _one_optional_reason(block.also)
    return f"{reason[0]}; {other[0]}", f"{reason[1]} · {other[1]}", reason[2]


def _one_optional_reason(block: OptionalEffectBlock) -> Reason:
    kind, needed, held = block.kind, block.needed, block.held
    match kind:
        case (
            OptionalBlockKind.SPICE
            | OptionalBlockKind.WATER
            | OptionalBlockKind.SOLARI
        ):
            return resource_reason(kind.value, needed, held)
        case OptionalBlockKind.SPECIMENS:
            return _specimen_cost_reason(needed, held)
        case OptionalBlockKind.SPIES_ON_BOARD:
            return _spies_reason(needed, held, "cost")
        case OptionalBlockKind.HAND:
            en, ko = held_text(held)
            return (
                f"Needs {needed} card{plural_s(needed)} in hand{en}",
                f"{{hand}}에 카드 {needed}장 필요{ko}",
                "cost",
            )
        case OptionalBlockKind.ALLIANCE:
            return (
                f"Needs the {_FACTION_EN[block.faction]} Alliance",
                f"{_FACTION_KO[block.faction]} {{alliance}} 필요",
                "condition",
            )
        case OptionalBlockKind.INFLUENCE:
            en, ko = held_text(held)
            return (
                f"Needs {needed} {_FACTION_EN[block.faction]} Influence{en}",
                f"{{influence_{block.faction}}} {needed} 필요{ko}",
                "condition",
            )
        case OptionalBlockKind.GENETIC_MARKERS:
            return (
                f"Needs {needed} genetic marker{plural_s(needed)}"
                f" (you have {held})",
                f"유전자 마커 {needed}개 필요 (보유 {held})",
                "condition",
            )
        case OptionalBlockKind.NOTHING_TO_ACQUIRE if needed:
            return (
                f"No card costing {needed} or less to acquire",
                f"획득할 수 있는 비용 {needed} 이하 카드 없음",
                "reward",
            )
        case OptionalBlockKind.NOTHING_TO_ACQUIRE:
            en, ko = held_text(held)
            return (
                f"No card you can acquire with your Solari{en}",
                f"{{solari}}로 획득할 수 있는 카드 없음{ko}",
                "cost",
            )
        case OptionalBlockKind.TECH_UNAFFORDABLE:
            en, ko = held_text(held)
            return (
                f"No Tech tile you can afford: the cheapest costs {needed}"
                f" spice{en}",
                f"살 수 있는 {{tech_tile}} 없음: 가장 싼 타일 {{spice:{needed}}}{ko}",
                "cost",
            )
        case OptionalBlockKind.FACTION_NEAR_TOP:
            name = _FACTION_EN[block.faction]
            return (
                f"{name} Influence is already {held}: two would end where one"
                " does",
                f"{{influence_{block.faction}}}이 이미 {held} — 2를 얻어도 1을 얻는"
                " 것과 같음",
                "top",
            )
    return _OPTIONAL_REASONS.get(kind, NOT_NOW)


def _board_icon_offered(state: GameState, seat: int, key: str) -> bool:
    """Whether the visit's optional icon ``key`` offers a row now."""

    if key == BOARD_ICON_TRASH:
        return desert_tactics_block(state, seat) is None
    if key == BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE:
        return imperial_privilege_trade_block(state, seat) is None
    if key == BOARD_ICON_COMMANDER:
        return sardaukar_commander_block(state, seat) is None
    if key == BOARD_ICON_TECH:
        return landsraad_tech_block(state, seat) is None
    return bool(legal_subcommittee_choice_actions(state, seat))


def _another_effect_offered(
    state: GameState,
    seat: int,
    *,
    box: int | None = None,
    icon: str | None = None,
    repeat: bool = False,
) -> bool:
    """Whether another effect of the seat's Agent turn offers a row now.

    The other Agent box, the visit's other icons (an optional one only
    while it offers a row), the Faction Influence of the visit, a Leader's
    placement ability, Reverend Mother's repeat, Urgent Shigawire's draw, a
    Contract completed by the visit and a held draw. Every one is public,
    or the seat's own (its held draws).
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    for other in (0, 1) if is_grafted_turn(context) else (0,):
        if other == box or not box_is_pending(context, other):
            continue
        if active_box_can_act(state_with_active_box(state, other), seat):
            return True
    for key in pending_board_icons(context):
        if key == icon:
            continue
        if key not in OPTIONAL_BOARD_ICONS or _board_icon_offered(state, seat, key):
            return True
    if (
        context.get("pending_faction_influence") is True
        or context.get("pending_leader_ability") is True
        or pending_boost_draws(context)
        or eligible_agent_contract_ids(context, state.players)
        or legal_owed_draw_actions(state, seat)
    ):
        return True
    return (
        not repeat
        and context.get("pending_leader_board_repeat") is True
        and leader_board_repeat_block(state, seat) is None
    )


def _optional_row(
    found: _Found,
    state: GameState,
    seat: int,
    key: str,
    action: DomainAction,
    reason: Reason,
    *,
    meetable: bool,
    box: int | None = None,
    icon: str | None = None,
    repeat: bool = False,
    card_id: str | None = None,
) -> None:
    """One optional effect's greyed row: under "waiting", with the free
    order wording, when its block could still be lifted (``meetable``) and
    another effect of the turn offers a row; otherwise under "choice". Both
    say that it lapses unused when the turn ends."""

    english, korean, code = reason
    waiting = meetable and _another_effect_offered(
        state, seat, box=box, icon=icon, repeat=repeat
    )
    tail_en, tail_ko = _FREE_ORDER if waiting else _LAPSES_UNUSED
    found.row(
        "waiting" if waiting else "choice",
        key,
        action,
        (english + tail_en, korean + tail_ko, code),
        card_id=card_id,
    )


def _optional_box_reason(
    state: GameState, seat: int
) -> tuple[Reason, bool] | None:
    """The active optional Agent box's reason, and whether another effect
    of the turn could lift its block, from its provider's own gate."""

    effect = active_agent_card(current_agent_effect_context(state)[1]).agent_effect
    cost = agent_card_cost_block(state, seat)
    payment = agent_card_payment_block(state, seat, effect)
    if cost is None and payment is not None:
        # Ecological Testing Station's draw with empty piles (a discard of
        # the turn refills them), Tleilaxu Surgeon at the track's end.
        return (
            _PAYMENT_BLOCK_REASONS[payment],
            payment is AgentPaymentBlock.NO_CARD_TO_DRAW,
        )
    block = (
        cost
        or agent_card_trash_block(state, seat)
        or agent_card_acquisition_block(state, seat)
        or signet_optional_block(state, seat)
    )
    if block is None:
        return None
    meetable = block.kind not in _NEVER_THIS_TURN and (
        block.also is None or block.also.kind not in _NEVER_THIS_TURN
    )
    return _optional_block_reason(block), meetable


def _optional_agent_box(state: GameState, seat: int, found: _Found) -> None:
    """An optional Agent box that offers nothing now (OQ-095 (2)).

    ``box_is_optional`` says the box holds only optional effects now, and
    ``active_box_can_act`` that it offers no row (the legal list offers the
    box's rows through the same ``agent_effect_frame._active_box_actions``).
    The reason is the gate its provider applies: ``agent_card_cost_block``
    (payments, discards, Corrinth City, the Intrigue payments, Piter,
    Dissecting Kit, Scientific Breakthrough's line, Arrakis Revolt),
    ``agent_card_payment_block`` (OQ-071), ``agent_card_trash_block``,
    ``agent_card_acquisition_block`` (Tleilaxu Master, Price is No Object)
    and ``signet_optional_block``. The row is the box's resolution, led by
    its card like a waiting box's (``agent_box_row_title``). A box resolved
    icon by icon (Tread in Darkness's trash, Twisted Mentat's recall) is
    ``_agent_icons``'.
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != seat:
        return
    if (
        context.get("pending_agent_effect") is not True
        or pending_agent_icons(context)
        or not box_is_optional(state)
        or active_box_can_act(state, seat)
    ):
        return
    answer = _optional_box_reason(state, seat)
    reason, meetable = answer if answer is not None else (NOT_NOW, False)
    card_id = context.get("card_id")
    _optional_row(
        found,
        state,
        seat,
        f"optional_box:{card_id}",
        DomainAction(action_id="resolve_agent_card_effect", actor=seat),
        reason,
        meetable=meetable,
        box=active_box(context),
        card_id=card_id if isinstance(card_id, str) else None,
    )


# The visit's optional effects, each with its provider's block function and
# the candidate it would offer (an argument-less one, never legal).
_OPTIONAL_BOARD_EFFECTS: Final[
    tuple[
        tuple[
            str,
            str,
            Callable[[GameState, int], OptionalEffectBlock | None],
            str,
        ],
        ...,
    ]
] = (
    (
        BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
        "imperial_privilege_intrigue",
        imperial_privilege_trade_block,
        "trash_intrigue_for_imperial_privilege",
    ),
    (
        BOARD_ICON_TRASH,
        "desert_tactics_trash",
        desert_tactics_block,
        "trash_card_for_desert_tactics",
    ),
    (
        BOARD_ICON_COMMANDER,
        "sardaukar_commander",
        sardaukar_commander_block,
        "acquire_sardaukar_commander",
    ),
    (BOARD_ICON_TECH, "landsraad_tech", landsraad_tech_block, "acquire_tech"),
)


def _optional_board_effects(state: GameState, seat: int, found: _Found) -> None:
    """The visit's optional effects that offer nothing now (OQ-095 (2)).

    Imperial Privilege's Intrigue trade with no Intrigue card in hand
    (``imperial_privilege_trade_block``), Desert Tactics' trash with no
    card (``desert_tactics_block``), a Sardaukar Commander gone or short of
    its Solari (``sardaukar_commander_block``), a Landsraad visit's Acquire
    Tech with no tile in reach (``landsraad_tech_block``), and Reverend
    Mother's repeat before the space's effects or without its water
    (``leader_board_repeat_block``): each provider offers its rows exactly
    when its block is None. The subcommittee seat is
    ``_subcommittee_choice``'s.
    """

    for icon, key, block_of, action_id in _OPTIONAL_BOARD_EFFECTS:
        block = block_of(state, seat)
        if block is None:
            continue
        _optional_row(
            found,
            state,
            seat,
            key,
            DomainAction(action_id=action_id, actor=seat),
            _optional_block_reason(block),
            meetable=block.kind not in _NEVER_THIS_TURN,
            icon=icon,
        )
    repeat = leader_board_repeat_block(state, seat)
    if repeat is None:
        return
    action = DomainAction(action_id="pay_leader_board_repeat", actor=seat)
    if repeat.kind is OptionalBlockKind.AFTER_THE_SPACE:
        english, korean, code = _optional_block_reason(repeat)
        found.row(
            "waiting",
            "leader_board_repeat",
            action,
            (
                english + _AFTER_THE_SPACE_LAPSES[0],
                korean + _AFTER_THE_SPACE_LAPSES[1],
                code,
            ),
        )
        return
    _optional_row(
        found,
        state,
        seat,
        "leader_board_repeat",
        action,
        _optional_block_reason(repeat),
        meetable=True,
        repeat=True,
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
    action = DomainAction(action_id="choose_subcommittee", actor=seat)
    if state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS:
        # An optional effect of the visit: left unused it lapses when the
        # turn ends (OQ-095 (2), user ruling 2026-10-14).
        _optional_row(
            found,
            state,
            seat,
            "choose_subcommittee",
            action,
            reason,
            meetable=reason != SUBCOMMITTEES_CLAIMED,
            icon=_SUBCOMMITTEE_ICON,
        )
        return
    found.row(
        "choice" if reason == SUBCOMMITTEES_CLAIMED else "waiting",
        "choose_subcommittee",
        action,
        reason,
    )


def _each_box(
    collect: Callable[[GameState, int, _Found], None],
) -> Callable[[GameState, int, _Found], None]:
    """``collect``, which reads the Agent box in ``card_id``, for each box.

    A grafted turn offers both cards' boxes (codec v143): the collector runs
    once per box on the state with that box active, and box 1's rows carry
    ``box=1`` like its legal rows (and a key of their own). A box whose rows
    wait while the other box is part way through a bundled selection
    (``box_in_progress``) shows none. Every row also names its box in
    ``box`` (0 on a single card's turn), as the legal rows do
    (``display.actions.agent_box_of_rows``), so the page can set it under
    its card's header.
    """

    def run(state: GameState, seat: int, found: _Found) -> None:
        try:
            _, context = current_agent_effect_context(state)
        except ValueError:
            collect(state, seat, found)
            return
        grafted = is_grafted_turn(context)
        current = active_box(context)
        locked = grafted and box_in_progress(state)
        for box in (0, 1) if grafted else (0,):
            if locked and box != current:
                continue
            boxed = _Found()
            collect(state_with_active_box(state, box), seat, boxed)
            for action, row in boxed.rows:
                action = tagged(action, box)
                row["action"] = action
                row["box"] = box
                if box == 1:
                    row["key"] = f"{row['key']}:box1"
                found.rows.append((action, row))
            for ref, reason in boxed.refs.items():
                found.refs.setdefault(ref, reason)

    return run


_BY_FRAME: Final[Mapping[str, tuple[Callable[[GameState, int, _Found], None], ...]]] = {
    FrameKind.REVEAL: (
        _shop,
        _reveal_choice,
        _deferred,
        _leader_reveal,
        _subcommittee_choice,
        _intrigue,
    ),
    FrameKind.AGENT_EFFECTS: (
        _each_box(_agent_box),
        _each_box(_optional_agent_box),
        _each_box(_agent_box_payment),
        _each_box(_signet_influence),
        _shipping_influence,
        _each_box(_agent_icons),
        _imperial_privilege_recall,
        _maker_space,
        _sietch_tabr,
        _optional_board_effects,
        _subcommittee_choice,
        _intrigue,
    ),
    # Servo-Receivers' Signet Ring outside the Agent box (OQ-062 (b)).
    FrameKind.LEADER_SIGNET: (_signet_influence,),
    FrameKind.CONTRACT_MARKET: (_contract_market,),
    FrameKind.CONTRACT_REWARD_RECALL: (_contract_recall,),
    FrameKind.RESEARCH_BONUS: (_research_bonus,),
    FrameKind.COMBAT_REWARD_INFLUENCE: (_combat_reward_influence,),
    FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE: (_combat_reward_influence,),
    FrameKind.COMBAT_REWARD_OPTIONAL: (_combat_reward_payment,),
    FrameKind.COMBAT_REWARD_SPY_RECALL: (_combat_reward_payment,),
    FrameKind.OPPONENT_UNIT_LOSS: (_unit_loss,),
    FrameKind.SKILL_CHOICE: (_skill_choice,),
    FrameKind.NAVIGATION_CHOICE: (_navigation,),
    FrameKind.INTRIGUE_EFFECTS: (_intrigue_effects,),
    FrameKind.TECH_ACQUISITION: (_tech,),
    FrameKind.TURN: (_turn_start_card, _intrigue),
    FrameKind.COMBAT_INTRIGUE: (_intrigue,),
    FrameKind.CONFLICT_END_TRIGGER: (_conflict_end_trigger,),
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
    A waiting Agent box is led by its card, as its legal row would be
    (``agent_box_row_title``).
    """

    # Imported here: display.actions imports display.scouts, which imports
    # this module for its reason helpers.
    from dune_imperium.display.actions import (
        agent_box_row_title,
        effect_action_text,
        effect_action_text_ko,
    )

    try:
        detail = effect_action_text(state, action)
        detail_ko = effect_action_text_ko(state, action)
        title = agent_box_row_title(state, action)
    except Exception:  # noqa: BLE001 - written for legal actions; a miss is no detail
        detail = detail_ko = None
        title = None
    shadow: dict[str, object] = {
        "action_id": action.action_id,
        "arguments": dict(action.arguments),
        "detail": detail,
        "detail_ko": detail_ko,
    }
    if title is not None:
        shadow["detail_title"], shadow["detail_title_ko"] = title
    return shadow


def _why(reason: Reason) -> dict[str, object]:
    return {"reason": reason[0], "reason_ko": reason[1], "code": reason[2]}


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
        # waiting Agent box and the Intrigue cards come back after it. Its
        # recall is offered even with both personal piles empty (OQ-099), so
        # nothing in the window is greyed out.
        collectors = ()
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
        # A box's row is described with its own box active, as it was
        # collected (``_each_box``): box 0's untagged row would otherwise
        # read the card of whichever box acted last.
        box = row.get("box")
        described = state_with_active_box(state, box) if isinstance(box, int) else state
        shadow = shadow_action(described, action)
        title_card = row.pop("title_card", None)
        if isinstance(title_card, str):
            # Imported here, as in ``shadow_action``.
            from dune_imperium.display.actions import reveal_card_names

            shadow["detail_title"], shadow["detail_title_ko"] = reveal_card_names(
                title_card
            )
        rows.append({**row, "action": shadow})
    for ref, reason in found.refs.items():
        if ref not in named and ref not in refs:
            refs[ref] = _why(reason)
    if not rows and not refs:
        return None
    return {"frame": str(frame.kind), "rows": rows, "refs": refs}
