"""Concrete dispatcher for the implemented Uprising rules.

Dispatch is table-driven. ``LEGAL_ACTION_PROVIDERS`` maps the kind of the top
decision frame to the ordered rule functions that may offer actions in that
frame, and ``ACTION_HANDLERS`` maps every ``action_id`` to the function that
resolves it. Adding a rule boundary means adding a frame kind and one table
entry per side rather than editing dispatcher logic.
"""

from collections.abc import Callable, Mapping
from copy import replace
from typing import Final

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult, RulesEngine
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import PlayerView, observe_state
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.acquisition import (
    apply_acquisition_spy_action,
    apply_agent_card_acquisition,
    apply_imperium_acquisition,
    apply_manipulated_acquisition,
    apply_reserve_acquisition,
    apply_reveal_command_acquisition,
    legal_acquisition_spy_actions,
    legal_imperium_acquisitions,
    legal_manipulated_acquisitions,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.agent_effect_frame import (
    legal_agent_effect_frame_actions,
    route_box_action,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_contract_completion,
    apply_agent_card_discard,
    apply_agent_card_influence,
    apply_agent_card_intrigue_payment,
    apply_agent_card_long_live_action,
    apply_agent_card_opponent_retreat,
    apply_agent_card_payment,
    apply_agent_card_recall,
    apply_agent_card_spy_action,
    apply_agent_card_trash,
    apply_corrinth_city_payment,
    apply_opponent_card_discard,
    expire_trashed_card_effects,
    legal_agent_card_long_live_actions,
    legal_opponent_card_discard_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_turn import (
    agent_card_pick,
    agent_card_pick_actions,
    agent_space_pick_actions,
    apply_agent_card_pick,
    apply_agent_space_pick,
    apply_turn_start_card,
    executable_placements,
    legal_turn_start_card_actions,
)
from dune_imperium.rules.board_effects import (
    apply_desert_tactics_action,
    apply_espionage_action,
    apply_imperial_privilege_action,
    apply_maker_space_action,
    apply_secrets_steal,
    apply_shipping_action,
    apply_sietch_tabr_action,
    apply_tuek_sietch_action,
    resolve_board_effect,
    secrets_steal_is_pending,
)
from dune_imperium.rules.card_draw import (
    apply_personal_draw_reshuffle,
    personal_draw_is_pending,
)
from dune_imperium.rules.combat import (
    apply_combat_influence_without_faction,
    apply_combat_intrigue_pass,
    apply_combat_reward_icon,
    apply_combat_reward_influence,
    apply_combat_reward_optional_payment,
    apply_combat_reward_spy,
    apply_combat_reward_spy_recall,
    apply_combat_reward_trash,
    apply_conflict_end_trigger,
    apply_distinct_combat_reward_influence,
    begin_combat_intrigue,
    close_spent_conflict_end_window,
    combat_participants_are_stale,
    finish_combat,
    legal_combat_intrigue_actions,
    legal_combat_reward_icon_actions,
    legal_combat_reward_influence_actions,
    legal_combat_reward_optional_payment_actions,
    legal_combat_reward_spy_actions,
    legal_combat_reward_spy_recall_actions,
    legal_combat_reward_trash_actions,
    legal_conflict_end_trigger_actions,
    legal_distinct_combat_reward_influence_actions,
    offer_conflict_end_triggers,
    pay_combat_rewards,
    refresh_combat_participants,
    resolve_combat_rewards,
    spent_conflict_end_window,
)
from dune_imperium.rules.combat_deployment import (
    apply_agent_turn_finish,
    apply_combat_deployment,
    apply_commander_deployment,
    apply_commander_withdrawal,
    apply_troop_withdrawal,
    record_deployment_peak,
    settle_finishing_agent_turn,
)
from dune_imperium.rules.contracts import (
    apply_contract_action,
    apply_contract_completion,
    apply_contract_fizzle,
    apply_contract_hold,
    apply_contract_intrigue_trash,
    apply_contract_recall_action,
    apply_contract_reward_icon,
    apply_contract_spy_action,
    combat_held_contract_owner,
    complete_alliance_contracts,
    exhausted_contract_choice_is_pending,
    fizzle_combat_held_contract_icons,
    held_contract_icons_can_open,
    legal_contract_actions,
    legal_contract_intrigue_trash_actions,
    legal_contract_recall_actions,
    legal_contract_reward_icon_actions,
    legal_contract_spy_actions,
    open_held_contract_icons,
    resolve_exhausted_contract_choice,
)
from dune_imperium.rules.effect_steps import (
    present,
    presents_steps,
    take_step,
    whole_actions,
    without_pick,
)
from dune_imperium.rules.endgame import (
    apply_endgame_intrigue_action,
    begin_endgame_intrigue,
    can_finish_endgame_automatically,
    finish_endgame_without_pending_effects,
    legal_endgame_intrigue_actions,
)
from dune_imperium.rules.frames import (
    FrameKind,
    end_turn_start,
    owned_top_frame,
    turn_owner_of,
    turn_start_is_open,
)
from dune_imperium.rules.graft import (
    apply_graft_partner,
    legal_graft_partner_actions,
)
from dune_imperium.rules.immortality import (
    apply_family_atomics,
    apply_research_advance,
    apply_research_bonus,
    apply_research_icon,
    apply_specimen_return,
    legal_family_atomics_actions,
    legal_research_advance_actions,
    legal_research_bonus_actions,
    legal_specimen_return_actions,
)
from dune_imperium.rules.intrigue import (
    apply_intrigue_choice,
    apply_intrigue_effect,
    apply_intrigue_play,
    apply_intrigue_rewards,
    legal_intrigue_choice_actions,
    legal_intrigue_effect_actions,
    legal_intrigue_play_actions,
    plays_turn_start_option,
)
from dune_imperium.rules.intrigue_deck import (
    apply_intrigue_reshuffle,
    intrigue_draw_is_queued,
    intrigue_reshuffle_is_pending,
    resolve_pending_intrigue_draw,
)
from dune_imperium.rules.intrigue_peek import (
    apply_intrigue_peek,
    legal_intrigue_peek_actions,
)
from dune_imperium.rules.intrigue_triggers import (
    apply_trigger_contract_action,
    deferred_acquisition_trigger_is_due,
    fire_deferred_acquisition_trigger,
    legal_trigger_contract_actions,
)
from dune_imperium.rules.leader_abilities import (
    apply_feyd_track_action,
    apply_kota_signet_action,
    apply_leader_agent_deploy,
    apply_leader_board_repeat,
    apply_leader_bonus_spice,
    apply_leader_card_trash,
    apply_leader_placement_ability,
    apply_leader_reveal_action,
    apply_leader_signet_acquire,
    apply_leader_signet_payment,
    apply_leader_spy_action,
    apply_leader_troop_retreat,
    apply_shaddam_signet_choice,
    grant_hungry_for_spice,
    grant_leader_reveal_passives,
    legal_feyd_track_actions,
    legal_leader_reveal_actions,
    legal_leader_signet_actions,
)
from dune_imperium.rules.leader_draft import (
    apply_leader_draft_pick,
    finish_leader_draft,
    legal_leader_draft_actions,
)
from dune_imperium.rules.navigation import (
    apply_navigation_play,
    apply_navigation_setup_action,
    begin_navigation_play,
    legal_navigation_play_actions,
    legal_navigation_setup_actions,
    navigation_play_is_queued,
)
from dune_imperium.rules.optional_trash import (
    apply_optional_trash,
    legal_optional_trash_actions,
)
from dune_imperium.rules.owed_draws import (
    apply_owed_draw,
    immediate_owed_draw_actions,
    legal_owed_draw_actions,
    pay_stale_owed_draws,
)
from dune_imperium.rules.pauses import (
    CONFLICT_END,
    REWARDS,
    ROUND_START,
    SCOUTS_REWARD,
    pause_is_pending,
    pending_pause_point,
    push_pause,
)
from dune_imperium.rules.phases import (
    apply_control_defense_action,
    apply_round_start_reshuffle,
    draw_round_hands,
    legal_control_defense_actions,
    prepare_round_start,
    resolve_makers,
    resolve_recall_or_endgame,
)
from dune_imperium.rules.reveal_turn import (
    apply_contract_reveal_choice,
    apply_corrinth_city_reveal,
    apply_reveal_card_trash,
    apply_reveal_deployment,
    apply_reveal_gain,
    apply_reveal_influence_exchange,
    apply_reveal_influence_gain,
    apply_reveal_influence_loss,
    apply_reveal_persuasion_or_contract,
    apply_reveal_sandworm_action,
    apply_reveal_spice_influence,
    apply_reveal_spy_action,
    apply_reveal_troop_move,
    apply_reveal_troop_retreat,
    apply_reveal_troop_sacrifice,
    begin_reveal_turn,
    finish_reveal_turn,
    grant_late_reveal_effects,
    legal_finish_reveal_actions,
    legal_pending_reveal_choice_actions,
    legal_reveal_actions,
    legal_reveal_deployments,
    legal_reveal_gain_actions,
    reveal_choice_providers,
)
from dune_imperium.rules.sardaukar import (
    apply_commander_recruit,
    apply_sardaukar_commander_action,
    apply_skill_choice,
    apply_skill_trash,
    begin_skill_choice,
    legal_commander_recruit_actions,
    legal_skill_choice_actions,
    legal_skill_trash_actions,
    skill_choice_is_queued,
)
from dune_imperium.rules.scouts import (
    advance_scouts_step,
    apply_four_bonus_choice,
    apply_scouts_draw,
    apply_scouts_return_specimens,
    begin_four_bonus_choice,
    four_bonus_choice_is_queued,
    legal_four_bonus_actions,
    scouts_draw_is_pending,
    scouts_step_is_pending,
)
from dune_imperium.rules.scouts_auctions import (
    apply_bid_action,
    apply_call,
    apply_retreat,
    apply_take,
    legal_bid_actions,
    legal_call_actions,
    legal_retreat_actions,
    legal_take_actions,
)
from dune_imperium.rules.scouts_effects import (
    advance_scouts_effect,
    apply_scouts_choice_action,
    apply_scouts_effect_action,
    apply_scouts_rewards_first,
    apply_subcommittee_action,
    legal_scouts_choice_actions,
    legal_scouts_effect_actions,
    legal_scouts_rewards_first_actions,
    legal_subcommittee_actions,
    legal_subcommittee_choice_actions,
    scouts_effect_can_advance,
)
from dune_imperium.rules.scouts_missions import (
    apply_mission_collect,
    apply_mission_join,
    claim_due_mission_goods,
    legal_mission_join_actions,
    mission_goods_are_due,
)
from dune_imperium.rules.scouts_secrets import (
    apply_secret_pick,
    legal_secret_pick_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.rules.shortfall import (
    drop_stale_shortfalls,
    refill_shortfall,
    shortfall_is_stale,
    shortfall_refill_seat,
)
from dune_imperium.rules.spies import apply_gather_intelligence_action
from dune_imperium.rules.spy_moves import (
    apply_place_track_spy,
    apply_spy_move,
    apply_spy_placement,
    begin_track_spy_placement,
    legal_spy_move_actions,
    legal_spy_placement_actions,
    legal_track_spy_actions,
    track_spy_is_queued,
)
from dune_imperium.rules.strength import refresh_pre_reveal_strength
from dune_imperium.rules.tech import (
    apply_place_tech_spy,
    apply_secret_project,
    apply_tech_acquire_effect,
    apply_tech_acquisition,
    apply_tech_choice,
    apply_tech_flip,
    apply_tech_influence_without_faction,
    deploy_suspensor_troops,
    draw_owed_tech_cards,
    legal_secret_project_actions,
    legal_tech_acquire_effect_actions,
    legal_tech_acquisition_actions,
    legal_tech_flip_actions,
    legal_tech_reveal_actions,
)
from dune_imperium.rules.tleilaxu_row import (
    apply_tleilaxu_acquisition,
    legal_tleilaxu_acquisitions,
)
from dune_imperium.rules.unit_loss import apply_unit_loss, legal_unit_loss_actions

type LegalActionProvider = Callable[[GameState, int], tuple[DomainAction, ...]]

# The last state whose rules' actions were asked, its player and the actions
# (``UprisingRulesEngine._rules_of``). Read and replaced as one reference.
_LAST_RULES: tuple[GameState, int, tuple[DomainAction, ...]] | None = None
type ActionHandler = Callable[[GameState, DomainAction], RuleResult]

DEFAULT_LEADER_IDS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


def _apply_agent_card_effect(state: GameState, action: DomainAction) -> RuleResult:
    if any(key == "effect" for key, _ in action.arguments):
        return resolve_agent_card_icon(state, action)
    return resolve_agent_card_effect(state)


def _handle(state: GameState, action: DomainAction) -> RuleResult:
    """Run ``action``'s handler; a grafted box's row with its box active.

    Box 1's rows carry ``box=1`` and box 0's none (docs/graft-boxes-plan.md
    4.6): ``route_box_action`` makes the row's box the one the Agent-box
    machinery reads, and drops the tag. Urgent Shigawire's added draw is
    routed as no box's row (it is bound to its card, OQ-106, OQ-107), so a
    ``effect=cards`` routed to box 1 is box 1's own icon.
    """

    state, action, box = route_box_action(state, action)
    if box == 1 and action.action_id == "resolve_agent_card_effect" and any(
        key == "effect" for key, _ in action.arguments
    ):
        return resolve_agent_card_icon(state, action, boost=False)
    return ACTION_HANDLERS[action.action_id](state, action)


def _apply_faction_influence(state: GameState, action: DomainAction) -> RuleResult:
    del action
    return resolve_faction_influence(state)


def _apply_decline_combat_reward(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    if state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_OPTIONAL:
        return apply_combat_reward_optional_payment(state, action)
    return apply_combat_reward_spy_recall(state, action)


def _apply_deployment(state: GameState, action: DomainAction) -> RuleResult:
    """Route a deployment to the Reveal-turn Combat icon or the Agent turn."""

    if owned_top_frame(state, FrameKind.REVEAL, action.actor) is not None:
        return apply_reveal_deployment(state, action)
    if action.action_id == "deploy_commanders":
        return apply_commander_deployment(state, action)
    return apply_combat_deployment(state, action)


def _executable_agent_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """The Agent turn's step (stage B1): a card pick, or the picked card's
    space picks."""

    pick = agent_card_pick(state, player)
    if pick is None:
        return agent_card_pick_actions(player, executable_placements(state, player))
    card, graft = pick
    return agent_space_pick_actions(
        player, executable_placements(state, player, card), card, graft
    )


LEGAL_ACTION_PROVIDERS: Final[Mapping[str, tuple[LegalActionProvider, ...]]] = {
    FrameKind.TURN: (
        _executable_agent_actions,
        legal_turn_start_card_actions,
        legal_reveal_actions,
        legal_intrigue_play_actions,
        legal_tech_flip_actions,
        legal_tech_acquire_effect_actions,
        legal_specimen_return_actions,
        legal_family_atomics_actions,
        # The owner's waiting Emperor track Spy, before the Agent or Reveal
        # too: a Plot is part of the turn (user ruling 2026-10-04).
        legal_track_spy_actions,
        # A draw a Plot's trigger earned, its own step (OQ-106).
        legal_owed_draw_actions,
        # A research bonus or trash icon a Plot raised waits on the turn
        # (cleanup-2b).
        legal_research_bonus_actions,
        legal_optional_trash_actions,
    ),
    FrameKind.AGENT_EFFECTS: (legal_agent_effect_frame_actions,),
    FrameKind.OPPONENT_CARD_DISCARD: (legal_opponent_card_discard_actions,),
    FrameKind.ACQUISITION_SPY: (legal_acquisition_spy_actions,),
    FrameKind.REVEAL: (
        legal_reserve_acquisitions,
        legal_imperium_acquisitions,
        legal_manipulated_acquisitions,
        legal_leader_reveal_actions,
        legal_commander_recruit_actions,
        legal_skill_trash_actions,
        legal_reveal_deployments,
        # Every pending Reveal choice that can be taken now, beside the
        # purchases and gains (OQ-095 (7) addition, codec v147).
        legal_pending_reveal_choice_actions,
        # The owner's waiting Emperor track Spy, placed in any order before
        # the Reveal ends (user ruling 2026-10-04).
        legal_track_spy_actions,
        # A draw a trigger earned in the turn, its own step taken in any
        # order before the Reveal ends (user ruling 2026-10-10, OQ-106).
        legal_owed_draw_actions,
        legal_finish_reveal_actions,
        legal_intrigue_play_actions,
        legal_tech_flip_actions,
        legal_tech_reveal_actions,
        legal_tech_acquire_effect_actions,
        legal_reveal_gain_actions,
        legal_specimen_return_actions,
        legal_family_atomics_actions,
        legal_tleilaxu_acquisitions,
        # Arrakeen Scouts: Corrinth City's seat's subcommittee (OQ-076).
        legal_subcommittee_choice_actions,
        # A research bonus or trash icon raised in the Reveal waits on it
        # (cleanup-2b).
        legal_research_bonus_actions,
        legal_optional_trash_actions,
    ),
    # A Reveal choice opened from the Reveal frame's pending list, on top
    # only while a step must follow at once (a Spy recalled for its
    # placement); the rows of every pending choice are the Reveal frame's.
    FrameKind.REVEAL_CHOICE: reveal_choice_providers(),
    # Each frame a Scouts line's reward may open also offers the line's
    # later automatic rewards first (OQ-100).
    FrameKind.CONTRACT_MARKET: (
        legal_contract_actions,
        legal_scouts_rewards_first_actions,
    ),
    FrameKind.CONTRACT_REWARD_SPY: (legal_contract_spy_actions,),
    FrameKind.CONTRACT_REWARD_ICONS: (legal_contract_reward_icon_actions,),
    FrameKind.CONTRACT_REWARD_RECALL: (legal_contract_recall_actions,),
    FrameKind.CONTRACT_INTRIGUE_TRASH: (legal_contract_intrigue_trash_actions,),
    FrameKind.CONTROL_DEFENSE: (
        legal_control_defense_actions,
        legal_specimen_return_actions,
    ),
    FrameKind.COMBAT_INTRIGUE: (
        legal_combat_intrigue_actions,
        legal_intrigue_play_actions,
        legal_specimen_return_actions,
    ),
    FrameKind.COMBAT_REWARD_OPTIONAL: (legal_combat_reward_optional_payment_actions,),
    FrameKind.COMBAT_REWARD_SPY_RECALL: (legal_combat_reward_spy_recall_actions,),
    FrameKind.COMBAT_REWARD_TRASH: (legal_combat_reward_trash_actions,),
    FrameKind.CONFLICT_END_TRIGGER: (legal_conflict_end_trigger_actions,),
    FrameKind.COMBAT_REWARD_SPY: (legal_combat_reward_spy_actions,),
    FrameKind.COMBAT_REWARD_ICONS: (legal_combat_reward_icon_actions,),
    FrameKind.COMBAT_REWARD_INFLUENCE: (legal_combat_reward_influence_actions,),
    FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE: (
        legal_distinct_combat_reward_influence_actions,
    ),
    FrameKind.ENDGAME_INTRIGUE: (
        legal_endgame_intrigue_actions,
        legal_intrigue_play_actions,
    ),
    # Chance frames never reach this table: legal_actions returns () for any
    # frame whose decision is not a PlayerDecision.
    FrameKind.INTRIGUE_CHOICE: (legal_intrigue_choice_actions,),
    FrameKind.INTRIGUE_EFFECTS: (legal_intrigue_effect_actions,),
    # Retired with Distraction's face-up trigger (codec v129, OQ-016): the
    # kind keeps its place so later kinds keep their observation index.
    FrameKind.INTRIGUE_TRIGGER_SPY: (),
    FrameKind.LEADER_DRAFT: (legal_leader_draft_actions,),
    FrameKind.SKILL_CHOICE: (legal_skill_choice_actions,),
    FrameKind.OPPONENT_SPY_MOVE: (legal_spy_move_actions,),
    FrameKind.OPPONENT_UNIT_LOSS: (legal_unit_loss_actions,),
    FrameKind.SPY_PLACEMENT: (
        legal_spy_placement_actions,
        legal_scouts_rewards_first_actions,
    ),
    FrameKind.INTRIGUE_TRIGGER_CONTRACT: (legal_trigger_contract_actions,),
    FrameKind.OPTIONAL_TRASH: (
        legal_optional_trash_actions,
        legal_scouts_rewards_first_actions,
        # A triggered draw waiting in the owner's turn: drawn before or
        # after the trash, as the owner orders (user ruling 2026-10-10,
        # OQ-106).
        legal_owed_draw_actions,
    ),
    FrameKind.LONG_LIVE_FIGHTERS: (legal_agent_card_long_live_actions,),
    FrameKind.NAVIGATION_SETUP: (legal_navigation_setup_actions,),
    FrameKind.NAVIGATION_CHOICE: (legal_navigation_play_actions,),
    FrameKind.TECH_ACQUISITION: (
        legal_tech_acquisition_actions,
        legal_tech_acquire_effect_actions,
    ),
    FrameKind.TECH_SECRET_PROJECT: (legal_secret_project_actions,),
    FrameKind.RESEARCH_ADVANCE: (
        legal_research_advance_actions,
        legal_scouts_rewards_first_actions,
    ),
    FrameKind.RESEARCH_BONUS: (
        legal_research_bonus_actions,
        legal_scouts_rewards_first_actions,
    ),
    FrameKind.GRAFT_PARTNER: (legal_graft_partner_actions,),
    FrameKind.INTRIGUE_PEEK: (legal_intrigue_peek_actions,),
    # Servo-Receivers: the Leader's Signet Ring ability outside its box.
    FrameKind.LEADER_SIGNET: (legal_feyd_track_actions, legal_leader_signet_actions),
    # Arrakeen Scouts: Friends Everywhere's choice of Influence 4 bonus.
    FrameKind.SCOUTS_FOUR_BONUS: (legal_four_bonus_actions,),
    FrameKind.SCOUTS_EFFECT: (
        legal_scouts_effect_actions,
        legal_scouts_rewards_first_actions,
    ),
    FrameKind.SCOUTS_SUBCOMMITTEE: (legal_subcommittee_actions,),
    FrameKind.SCOUTS_CHOICE: (legal_scouts_choice_actions,),
    FrameKind.SCOUTS_MISSION: (legal_mission_join_actions,),
    FrameKind.SCOUTS_SECRET: (legal_secret_pick_actions,),
    FrameKind.SCOUTS_BID: (legal_bid_actions,),
    FrameKind.SCOUTS_RETREAT: (legal_retreat_actions,),
    FrameKind.SCOUTS_CALL: (legal_call_actions,),
    FrameKind.SCOUTS_MARKET: (legal_take_actions,),
}

ACTION_HANDLERS: Final[Mapping[str, ActionHandler]] = {
    # Setup Leader draft (OQ-007 convention)
    "pick_leader": apply_leader_draft_pick,
    "finish_leader_draft": finish_leader_draft,
    # Arrakeen Scouts (docs/rules/arrakeen-scouts.md)
    "choose_four_bonus": apply_four_bonus_choice,
    "choose_subcommittee": apply_subcommittee_action,
    "join_subcommittee": apply_subcommittee_action,
    "decline_subcommittee": apply_subcommittee_action,
    "scouts_discard": apply_scouts_effect_action,
    "scouts_trash_card": apply_scouts_effect_action,
    "scouts_trash_intrigue": apply_scouts_effect_action,
    "scouts_recall_spy": apply_scouts_effect_action,
    "scouts_choose_faction": apply_scouts_effect_action,
    "scouts_recall_agent": apply_scouts_effect_action,
    "scouts_lose_influence": apply_scouts_effect_action,
    "scouts_lose_influence_to": apply_scouts_effect_action,
    "scouts_lose_garrison_unit": apply_scouts_effect_action,
    "scouts_rewards_first": apply_scouts_rewards_first,
    "scouts_choose_option": apply_scouts_choice_action,
    "scouts_pass": apply_scouts_choice_action,
    "resolve_scouts_choice_without_option": apply_scouts_choice_action,
    "scouts_join_mission": apply_mission_join,
    "scouts_decline_mission": apply_mission_join,
    "scouts_collect_mission": apply_mission_collect,
    "scouts_secret_pick": apply_secret_pick,
    "scouts_bid": apply_bid_action,
    "confirm_scouts_bid": apply_bid_action,
    "scouts_retreat": apply_retreat,
    "scouts_call": apply_call,
    "scouts_take_card": apply_take,
    "scouts_decline_card": apply_take,
    "scouts_return_specimens": apply_scouts_return_specimens,
    # Turn choice and Plot Intrigue
    "choose_agent_card": apply_agent_card_pick,
    "place_agent": apply_agent_space_pick,
    "reveal_turn": begin_reveal_turn,
    "recruit_reveal_troops": apply_reveal_gain,
    "draw_reveal_intrigue": apply_reveal_gain,
    "generate_reveal_specimens": apply_reveal_gain,
    "advance_reveal_tleilaxu": apply_reveal_gain,
    "advance_reveal_research": apply_reveal_gain,
    "pay_agent_card_specimen": apply_agent_card_payment,
    "pay_agent_card_two_specimens": apply_agent_card_payment,
    "trash_grafted_card_for_specimen": apply_agent_card_payment,
    "take_agent_card_combat_icon": apply_agent_card_payment,
    "trash_agent_card_self_for_vp": apply_agent_card_payment,
    "pay_agent_card_five_solari_for_tleilaxu": apply_agent_card_payment,
    "trash_grafted_card_for_influence": apply_agent_card_payment,
    "lose_agent_card_troop": apply_agent_card_payment,
    "choose_agent_card_reward": apply_agent_card_payment,
    "keep_peeked_intrigue": apply_intrigue_peek,
    "gain_reveal_resources": apply_reveal_gain,
    "gain_reveal_faction_influence": apply_reveal_gain,
    "play_intrigue": apply_intrigue_play,
    "choose_intrigue_faction": apply_intrigue_choice,
    "use_intrigue_effect": apply_intrigue_effect,
    "finish_intrigue_effects": apply_intrigue_effect,
    "choose_intrigue_discard": apply_intrigue_choice,
    "detonate_shield_wall": apply_intrigue_choice,
    "keep_shield_wall": apply_intrigue_choice,
    "deploy_intrigue_troops": apply_intrigue_choice,
    "trash_intrigue_card": apply_intrigue_choice,
    "decline_intrigue_trash": apply_intrigue_choice,
    "decline_intrigue_spy": apply_intrigue_choice,
    "place_intrigue_spy": apply_intrigue_choice,
    "lose_intrigue_troop": apply_intrigue_choice,
    "give_intrigue_card": apply_intrigue_choice,
    "trash_intrigue_hand_card": apply_intrigue_choice,
    "put_back_top_card": apply_intrigue_choice,
    "discard_top_card": apply_intrigue_choice,
    "draw_top_card_for_solari": apply_intrigue_choice,
    "recall_spy_for_intrigue": apply_intrigue_choice,
    "retreat_intrigue_troops": apply_intrigue_choice,
    "acquire_intrigue_imperium": apply_intrigue_choice,
    "acquire_intrigue_reserve": apply_intrigue_choice,
    "skip_intrigue_acquisition": apply_intrigue_choice,
    "resolve_intrigue_influence_without_faction": apply_intrigue_choice,
    "acquire_intrigue_tleilaxu": apply_intrigue_choice,
    "acquire_intrigue_reclaimed_forces": apply_intrigue_choice,
    "decline_intrigue_tleilaxu": apply_intrigue_choice,
    "flip_battle_card": apply_intrigue_choice,
    "manipulate_imperium_row": apply_intrigue_choice,
    "resolve_intrigue_rewards": apply_intrigue_rewards,
    "acquire_manipulated_imperium": apply_manipulated_acquisition,
    # Agent-turn effect frame
    "resolve_agent_card_effect": _apply_agent_card_effect,
    "resolve_board_effect": resolve_board_effect,
    "resolve_faction_influence": _apply_faction_influence,
    "gather_intelligence": apply_gather_intelligence_action,
    "decline_gather_intelligence": apply_gather_intelligence_action,
    "complete_contract": apply_contract_completion,
    "recall_spy_for_espionage": apply_espionage_action,
    "resolve_espionage_place_spy": apply_espionage_action,
    "resolve_espionage_without_spy": apply_espionage_action,
    "take_sietch_tabr_supplies": apply_sietch_tabr_action,
    "take_sietch_tabr_water": apply_sietch_tabr_action,
    "take_sietch_tabr_water_and_destroy_wall": apply_sietch_tabr_action,
    "take_tuek_sietch_spice": apply_tuek_sietch_action,
    "take_tuek_sietch_card": apply_tuek_sietch_action,
    "place_leader_bonus_spice": apply_leader_bonus_spice,
    "take_leader_bonus_spice": apply_leader_bonus_spice,
    "harvest_maker_spice": apply_maker_space_action,
    "take_desert_riding_hooks": apply_maker_space_action,
    "summon_maker_sandworms": apply_maker_space_action,
    "choose_shipping_influence": apply_shipping_action,
    "trash_card_for_desert_tactics": apply_desert_tactics_action,
    "trash_intrigue_for_imperial_privilege": apply_imperial_privilege_action,
    "recall_agent_for_imperial_privilege": apply_imperial_privilege_action,
    "recall_conflict_agent_for_imperial_privilege": apply_imperial_privilege_action,
    "resolve_imperial_privilege_without_recall": apply_imperial_privilege_action,
    "deploy_troops": _apply_deployment,
    "withdraw_troops": apply_troop_withdrawal,
    "deploy_commanders": _apply_deployment,
    "withdraw_commanders": apply_commander_withdrawal,
    "finish_agent_turn": apply_agent_turn_finish,
    # Immortality: the Bene Tleilax board and Family Atomics
    "choose_research_space": apply_research_advance,
    "choose_research_influence": apply_research_bonus,
    "trash_intrigue_for_research_bonus": apply_research_bonus,
    "pay_research_bonus": apply_research_bonus,
    "decline_research_bonus": apply_research_bonus,
    "resolve_research_icon": apply_research_icon,
    "return_specimen": apply_specimen_return,
    "use_family_atomics": apply_family_atomics,
    "acquire_tleilaxu": apply_tleilaxu_acquisition,
    "acquire_reclaimed_forces": apply_tleilaxu_acquisition,
    "choose_graft_partner": apply_graft_partner,
    "decline_agent_card_recall": apply_agent_card_recall,
    # Bloodlines Sardaukar Commanders
    "acquire_sardaukar_commander": apply_sardaukar_commander_action,
    "acquire_tech": apply_tech_acquisition,
    "resolve_tech_acquire_effect": apply_tech_acquire_effect,
    "resolve_tech_influence_without_faction": apply_tech_influence_without_faction,
    "decline_tech": apply_tech_acquisition,
    "flip_tech": apply_tech_flip,
    "choose_secret_project": apply_secret_project,
    "gain_leader_signet_spice": apply_kota_signet_action,
    "trash_leader_tech": apply_kota_signet_action,
    "choose_tech_strength": apply_tech_choice,
    "choose_tech_trash": apply_tech_choice,
    "place_tech_spy": apply_place_tech_spy,
    "place_track_spy": apply_place_track_spy,
    # A triggered draw held as the owner's own step (OQ-106).
    "draw_owed_intrigue": apply_owed_draw,
    "draw_owed_card": apply_owed_draw,
    "decline_skill": apply_skill_choice,
    "recruit_sardaukar_commander": apply_commander_recruit,
    "trash_skill_for_strength": apply_skill_trash,
    # Agent-card serial choices
    "trash_agent_card": apply_agent_card_trash,
    "retreat_opponent_troop": apply_agent_card_opponent_retreat,
    "decline_agent_card_trash": apply_agent_card_trash,
    "discard_agent_card": apply_agent_card_discard,
    "decline_agent_card_discard": apply_agent_card_discard,
    "pay_agent_card_water": apply_agent_card_payment,
    "pay_agent_card_spice_for_sandworm": apply_agent_card_payment,
    "pay_agent_card_spice_for_sandworm_and_shield_wall": apply_agent_card_payment,
    "pay_agent_card_spice": apply_agent_card_payment,
    "decline_agent_card_payment": apply_agent_card_payment,
    "pay_corrinth_city": apply_corrinth_city_payment,
    "select_corrinth_city_discard": apply_corrinth_city_payment,
    "decline_corrinth_city_payment": apply_corrinth_city_payment,
    "pay_agent_card_intrigue_and_spice": apply_agent_card_intrigue_payment,
    "trash_intrigue_for_agent_card": apply_agent_card_intrigue_payment,
    "decline_agent_card_intrigue_payment": apply_agent_card_intrigue_payment,
    "recall_agent_for_agent_card": apply_agent_card_recall,
    "recall_conflict_agent_for_agent_card": apply_agent_card_recall,
    "place_agent_card_spy": apply_agent_card_spy_action,
    "recall_spy_for_agent_card": apply_agent_card_spy_action,
    "decline_agent_card_spy": apply_agent_card_spy_action,
    "choose_agent_card_influence": apply_agent_card_influence,
    "acquire_imperium_with_solari": apply_agent_card_acquisition,
    "acquire_reserve_with_solari": apply_agent_card_acquisition,
    "decline_agent_card_acquisition": apply_agent_card_acquisition,
    "acquire_reserve_by_card": apply_agent_card_acquisition,
    "acquire_imperium_by_card": apply_agent_card_acquisition,
    "select_long_live_fighters_draw": apply_agent_card_long_live_action,
    "select_long_live_fighters_discard": apply_agent_card_long_live_action,
    "discard_opponent_card": apply_opponent_card_discard,
    # Leader Signet Ring and placement-triggered Leader abilities
    "advance_feyd_track": apply_feyd_track_action,
    "trash_leader_card": apply_leader_card_trash,
    "retreat_leader_troops": apply_leader_troop_retreat,
    "deploy_leader_agent": apply_leader_agent_deploy,
    "pay_leader_signet_water": apply_leader_signet_payment,
    "trash_optional_card": apply_optional_trash,
    "place_navigation_card": apply_navigation_setup_action,
    "play_navigation": apply_navigation_play,
    "decline_navigation": apply_navigation_play,
    "decline_optional_trash": apply_optional_trash,
    # Arrakis Planetologist's Intrigue card, its own step in the trash
    # frame (user ruling 2026-10-10, OQ-106).
    "draw_planetologist_intrigue": apply_optional_trash,
    "decline_leader_card_trash": apply_feyd_track_action,
    "place_leader_spy": apply_leader_spy_action,
    "recall_spy_for_leader_placement": apply_leader_spy_action,
    "decline_leader_spy_placement": apply_leader_spy_action,
    "pay_leader_signet_spice": apply_leader_signet_payment,
    "pay_leader_signet_solari": apply_leader_signet_payment,
    "decline_leader_signet_payment": apply_leader_signet_payment,
    "resolve_leader_signet_without_option": apply_leader_signet_payment,
    "acquire_leader_imperium": apply_leader_signet_acquire,
    "acquire_leader_reserve": apply_leader_signet_acquire,
    "gain_leader_signet_troop": apply_shaddam_signet_choice,
    "choose_leader_signet_influence": apply_shaddam_signet_choice,
    "use_other_memories": apply_leader_placement_ability,
    "pay_leader_board_repeat": apply_leader_board_repeat,
    # Reveal turn
    "acquire_reserve": apply_reserve_acquisition,
    "acquire_imperium": apply_imperium_acquisition,
    "retreat_leader_troop": apply_leader_reveal_action,
    "retreat_leader_commander": apply_leader_reveal_action,
    "recall_spy_for_leader": apply_leader_reveal_action,
    "finish_reveal": finish_reveal_turn,
    "place_acquisition_spy": apply_acquisition_spy_action,
    "recall_spy_for_acquisition": apply_acquisition_spy_action,
    "decline_acquisition_spy": apply_acquisition_spy_action,
    # Reveal serial choices
    "gain_five_reveal_solari": apply_corrinth_city_reveal,
    "take_high_council_from_reveal": apply_corrinth_city_reveal,
    "keep_contract_reveal_spice": apply_contract_reveal_choice,
    "trash_contract_reveal_for_vp": apply_contract_reveal_choice,
    "trash_reveal_card": apply_reveal_card_trash,
    "place_reveal_spy": apply_reveal_spy_action,
    "recall_spy_for_reveal": apply_reveal_spy_action,
    "recall_spy_for_reveal_placement": apply_reveal_spy_action,
    "recall_spies_for_reveal": apply_reveal_spy_action,
    "gain_two_reveal_strength": apply_reveal_spy_action,
    "decline_reveal_spy_recall": apply_reveal_spy_action,
    "exchange_reveal_influence": apply_reveal_influence_exchange,
    "gain_reveal_influence": apply_reveal_influence_gain,
    "command_acquire_row_card": apply_reveal_command_acquisition,
    "gain_reveal_persuasion": apply_reveal_persuasion_or_contract,
    "take_reveal_contract": apply_reveal_persuasion_or_contract,
    "play_turn_start_card": apply_turn_start_card,
    "complete_contract_by_card": apply_agent_card_contract_completion,
    "choose_skill": apply_skill_choice,
    "resolve_commander_without_skill": apply_skill_choice,
    "move_spy": apply_spy_move,
    "lose_moved_spy": apply_spy_move,
    "place_spy_on_space": apply_spy_placement,
    "recall_spy_for_placement": apply_spy_placement,
    "decline_spy_placement": apply_spy_placement,
    "lose_unit": apply_unit_loss,
    "resolve_unit_loss_without_unit": apply_unit_loss,
    "take_trigger_contract": apply_trigger_contract_action,
    "pay_reveal_water_for_sandworm": apply_reveal_sandworm_action,
    "decline_reveal_sandworm": apply_reveal_sandworm_action,
    "pay_reveal_spice_influence": apply_reveal_spice_influence,
    "retreat_two_troops_for_reveal": apply_reveal_troop_retreat,
    # Immortality Reveal choices (For Humanity, Shadout Mapes, Tleilaxu
    # Surgeon)
    "lose_reveal_influence_for_vp": apply_reveal_influence_loss,
    "deploy_reveal_card_troop": apply_reveal_troop_move,
    "retreat_reveal_card_troop": apply_reveal_troop_move,
    "lose_reveal_troops_for_specimens": apply_reveal_troop_sacrifice,
    # Contracts
    "take_contract": apply_contract_action,
    # Nothing in a non-empty market can be taken: the icons wait (OQ-059).
    "hold_contract_icons": apply_contract_hold,
    "resolve_contract_icons_without_contract": apply_contract_fizzle,
    "resolve_contract_reward_icon": apply_contract_reward_icon,
    "place_contract_spy": apply_contract_spy_action,
    "recall_spy_for_contract": apply_contract_spy_action,
    "decline_contract_spy": apply_contract_spy_action,
    "recall_agent_for_contract": apply_contract_recall_action,
    "recall_conflict_agent_for_contract": apply_contract_recall_action,
    "resolve_contract_without_recall": apply_contract_recall_action,
    "trash_intrigue_for_contract": apply_contract_intrigue_trash,
    # Round start and Combat
    "deploy_control_defense": apply_control_defense_action,
    "decline_control_defense": apply_control_defense_action,
    "pass_combat_intrigue": apply_combat_intrigue_pass,
    "pay_combat_reward": apply_combat_reward_optional_payment,
    "recall_spies_for_combat_reward": apply_combat_reward_spy_recall,
    "decline_combat_reward": _apply_decline_combat_reward,
    "resolve_combat_reward_icon": apply_combat_reward_icon,
    "trash_combat_reward_card": apply_combat_reward_trash,
    "decline_combat_reward_trash": apply_combat_reward_trash,
    "resolve_combat_trash_without_card": apply_combat_reward_trash,
    "play_conflict_end_intrigue": apply_conflict_end_trigger,
    "decline_conflict_end_intrigue": apply_conflict_end_trigger,
    "finish_conflict_end_intrigue": apply_conflict_end_trigger,
    "place_combat_reward_spy": apply_combat_reward_spy,
    "recall_spy_for_combat_reward": apply_combat_reward_spy,
    "decline_combat_reward_spy": apply_combat_reward_spy,
    "choose_combat_reward_influence": apply_combat_reward_influence,
    "choose_distinct_combat_reward_influence": (apply_distinct_combat_reward_influence),
    # Every eligible Faction at the top: the owner confirms the loss (OQ-060).
    "resolve_combat_influence_without_faction": apply_combat_influence_without_faction,
    # Endgame
    "match_endgame_wild_icon": apply_endgame_intrigue_action,
    "pass_endgame_intrigue": apply_endgame_intrigue_action,
}


class UprisingRulesEngine(RulesEngine):
    """Connect the implemented rule modules into one multi-round state machine."""

    # The Combat's final standing (``combat_standing``) is the strengths
    # and reward rows the state already holds, logged for the tables when
    # the rewards begin, and a Reveal's hand (``cards_revealed``) is the
    # cards the state then holds in play. Kept in the state, either would
    # change the hash of every game past it, and no save written before
    # they existed would load (2026-10-08).
    report_only_event_kinds = frozenset({"combat_standing", "cards_revealed"})

    def __init__(self, leader_ids: tuple[str, ...] = DEFAULT_LEADER_IDS) -> None:
        self._leader_ids = leader_ids

    def _initial_state(self, config: RulesetConfig, seed: int) -> GameState:
        if config.leader_draft:
            # The OQ-007 draft pauses in SETUP on the pick frames; the
            # engine's fixed leader_ids only serve the non-draft path.
            return create_draft_initial_state(config, seed).state
        setup = create_initial_state(config, seed, self._leader_ids)
        if setup.state.phase is GamePhase.SETUP:
            # Steersman Y'rkoon's Navigation picks pause the game in SETUP
            # like the draft; Round Start follows once they are made.
            return setup.state
        started = prepare_round_start(setup.state)
        if config.arrakeen_scouts:
            # Round 1 begins inside reset(): its Scouts step (the
            # subcommittee draws) starts here, so the reset state already
            # waits on the first Scouts chance frame.
            started = _advance_automatic(started)
        return replace(started.state, event_log=started.events)

    def _apply_chance(
        self,
        state: GameState,
        outcome: ChanceOutcome,
    ) -> RuleResult:
        if pause_is_pending(state):
            result = _resume_pause(state)
        elif personal_draw_is_pending(state):
            result = apply_personal_draw_reshuffle(state, outcome)
        elif intrigue_reshuffle_is_pending(state):
            result = apply_intrigue_reshuffle(state, outcome)
        elif secrets_steal_is_pending(state):
            result = apply_secrets_steal(state, outcome)
        elif scouts_draw_is_pending(state):
            result = apply_scouts_draw(state, outcome)
        else:
            result = apply_round_start_reshuffle(state, outcome)
        # An Intrigue draw granted by a Reveal passive may queue a reshuffle,
        # so the automatic advance runs again after the passives.
        result = grant_late_reveal_effects(
            grant_leader_reveal_passives(
                grant_hungry_for_spice(_advance_automatic(result), state)
            )
        )
        result = expire_trashed_card_effects(_advance_automatic(result))
        # Suspensor Suits pays the troops owed by this step's Intrigue gains.
        advanced = _advance_automatic(result)
        result = deploy_suspensor_troops(
            pay_stale_owed_draws(
                draw_owed_tech_cards(_complete_alliance_contracts(advanced))
            )
        )
        return refresh_pre_reveal_strength(
            _settle_finishing(record_deployment_peak(_advance_automatic(result)))
        )

    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        """Return the rows the top frame offers to ``player``.

        The rows are the whole actions of ``_rules_actions``, each shown by
        its next step where the frame offers its waiting effects effect
        first (stage B3, ``rules.effect_steps``). While an immediate
        triggered draw waits for ``player`` (CHOAM Transports, the Bene
        Gesserit Influence 4 card, Imperial Birthright, an acquire box; user
        decision 2026-10-10, OQ-106), that draw is all any of its frames
        offers, so nothing of the owner's comes between the trigger and it.
        """

        return present(state, self._rules_of(state, player))

    def whole_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        """The whole actions ``player``'s legal rows stand for (stage B3).

        A frame that offers its waiting effects effect first
        (``rules.effect_steps``) shows each whole action -- an effect and its
        target at once, as the rules resolve it -- by its next step; this is
        the list of the whole actions themselves (during a pick, those its
        rows lead to), for an agent that weighs an effect with its target
        and for the page. Elsewhere it is the legal list.
        """

        return whole_actions(state, self._rules_of(state, player))

    def _rules_of(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        """``_rules_actions`` of ``state`` without its pick, kept for the last
        state asked: one decision asks for them several times (its legal
        rows, the whole actions an agent weighs, the step it takes), and a
        state never changes, so the state object is the key (stage B3)."""

        global _LAST_RULES
        last = _LAST_RULES
        if last is not None and last[0] is state and last[1] == player:
            return last[2]
        actions = self._rules_actions(without_pick(state), player)
        _LAST_RULES = (state, player, actions)
        return actions

    def _rules_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        """The whole actions the top frame's providers offer to ``player``."""

        if not state.decision_stack:
            return ()
        frame = state.decision_stack[-1]
        if not isinstance(frame.decision, PlayerDecision):
            return ()
        immediate = immediate_owed_draw_actions(state, player)
        if immediate:
            return immediate
        if frame.kind == FrameKind.TURN and agent_card_pick(state, player) is not None:
            # A picked Agent card waits for its space and nothing else
            # (stage B1, OQ-111).
            return _executable_agent_actions(state, player)
        providers = LEGAL_ACTION_PROVIDERS.get(frame.kind)
        if providers is None:
            raise RuntimeError(f"unknown decision frame kind: {frame.kind}")
        return tuple(
            action for provider in providers for action in provider(state, player)
        )

    def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
        if presents_steps(state):
            # A step toward a waiting effect only keeps the pick; the path's
            # last step applies its whole action to the rules' own state
            # (stage B3, ``rules.effect_steps``).
            step = take_step(
                state,
                action,
                self._rules_of(state, action.actor),
            )
            if step.whole is None:
                assert step.event is not None
                return RuleResult(state=step.state, events=(step.event,))
            state, action = step.state, step.whole
        handled = _end_turn_start(state, action, _handle(state, action))
        result = _advance_automatic(handled)
        # An Intrigue draw granted by a Reveal passive or a late-met Reveal
        # condition may queue a reshuffle, so the automatic advance runs
        # again after them.
        result = _advance_automatic(
            grant_late_reveal_effects(
                grant_leader_reveal_passives(grant_hungry_for_spice(result, state))
            )
        )
        result = expire_trashed_card_effects(result)
        # Units moved this step: the running strength follows [Main p. 12].
        # Suspensor Suits pays the troops owed by this step's Intrigue gains.
        advanced = _advance_automatic(result)
        result = deploy_suspensor_troops(
            pay_stale_owed_draws(
                draw_owed_tech_cards(_complete_alliance_contracts(advanced))
            )
        )
        return refresh_pre_reveal_strength(
            _settle_finishing(record_deployment_peak(_advance_automatic(result)))
        )

    def observe(self, state: GameState, player: int) -> PlayerView:
        return observe_state(state, player)



def _end_turn_start(
    state: GameState, action: DomainAction, handled: RuleResult
) -> RuleResult:
    """End the start of the actor's turn once it acted in that turn.

    "At the start of your turn" [Litany Against Fear card] [Withdrawn card]:
    any action of the turn's owner taken while its turn frame is open --
    whatever frame it answers, a Plot's own choices included -- ends the
    start of the turn (OQ-095 (6), user ruling 2026-10-04: "턴 시작 후 이
    카드를 사용하는 것 말고 다른 행동을 했으면 이제 턴 시작이 끝났으니 이
    카드를 사용할 수 없게 되는게 맞다고 봐"). Another seat's answer and the
    engine's automatic steps do not, by themselves. Playing one of the two
    cards is the start's own action; it passes the turn, and the next turn
    frame (the seat's own again when every other seat has revealed) opens
    with its start still open. Marked on the handler's result, before the
    automatic steps, so a turn those steps open is a fresh one.
    """

    if not turn_start_is_open(state, action.actor) or (
        action.action_id == "play_turn_start_card" or plays_turn_start_option(action)
    ):
        return handled
    return RuleResult(
        state=end_turn_start(handled.state, action.actor), events=handled.events
    )


def _complete_alliance_contracts(result: RuleResult) -> RuleResult:
    """Complete Earn Any Alliance, then pay what that Contract opens in a Reveal.

    The completion runs after the step's late-Reveal pass, so the pass runs
    once more when a Contract was completed: an Interstellar Trade in play
    pays +1 for it at once rather than a step later, or never when the owner
    finishes the Reveal next (OQ-028 (c), user ruling 2026-10-04).

    It runs at the end of the step that took the Alliance, also when that
    step stopped at a pause (rules/pauses.py): in Combat every reward step
    ends before the cleanup, so the Contract's troops come only from the
    supply, like any Conflict reward's (OQ-056, user decision 2026-10-09).
    """

    completed = complete_alliance_contracts(result)
    if completed.state is result.state:
        return completed
    granted = grant_late_reveal_effects(completed)
    return completed if granted is completed else _advance_automatic(granted)


def _settle_finishing(result: RuleResult) -> RuleResult:
    """Close or reopen an Agent turn whose end is still resolving.

    Only after every hook of the transition has run (Hungry for Spice,
    Suspensor Suits, Alliance Contracts, the deployment peak), so whatever
    the press produced -- a Usurp trash, a box it resolved -- is judged
    inside that turn (OQ-095 (3), (5)); the next seat's turn may then need its
    own automatic steps.
    """

    settled = settle_finishing_agent_turn(result)
    if settled is result:
        return result
    return _advance_automatic(settled)


def _held_contract_owner(state: GameState) -> int | None:
    """Seat whose held Contract icons can reopen the market now.

    The turn's owner, or in the Combat phase the seat whose Conflict reward
    icons wait while it resolves the rest of its rewards (user ruling
    2026-10-02, L2-Q2), or during the Arrakeen Scouts step -- no one's turn
    -- any seat whose icons wait for the rest of the step (user ruling
    2026-10-02, "Scouts 단계 안에서 보류 후 불발").
    """

    if state.phase is GamePhase.COMBAT or (
        state.scouts_opening and turn_owner_of(state) is None
    ):
        return next(
            (
                seat.player_id
                for seat in state.players
                if held_contract_icons_can_open(state, seat.player_id)
            ),
            None,
        )
    player = turn_owner_of(state)
    if player is None or not held_contract_icons_can_open(state, player):
        return None
    return player


def _resume_pause(state: GameState) -> RuleResult:
    """Answer the pause on top: run the step it held back (rules/pauses.py)."""

    point = pending_pause_point(state)
    resumed = state.pop_decision()
    if point == REWARDS:
        return pay_combat_rewards(resumed)
    if point == CONFLICT_END:
        return offer_conflict_end_triggers(resumed)
    if point == ROUND_START:
        return prepare_round_start(resumed)
    if point == SCOUTS_REWARD:
        # The Scouts step's next task is the held-back winner's reward; the
        # automatic advance runs it (rules/scouts.py).
        return RuleResult(state=resumed)
    return draw_round_hands(resumed)


def _advance_automatic(result: RuleResult) -> RuleResult:
    state = result.state
    events: list[GameEvent] = list(result.events)
    while True:
        if deferred_acquisition_trigger_is_due(state):
            # A face-up Call to Arms waited for the decision frames the
            # acquired card's own effects opened (a Research direction, a Spy
            # post, the Contract market); they are answered, so it fires
            # before the queued steps below, as it does inside an acquisition
            # that opened none, and before Reveal choices of cards those
            # effects drew (OQ-012, user ruling 2026-10-04).
            automatic = fire_deferred_acquisition_trigger(state)
        elif mission_goods_are_due(state):
            # Arrakeen Scouts: a Spy on a Valued Informants post or a
            # completed CHOAM Escort Contract, by whatever path it got there.
            automatic = claim_due_mission_goods(state)
        elif (refill_seat := shortfall_refill_seat(state)) is not None:
            # Troops came back to a seat's supply during a player turn: its
            # recruit and specimen shortfall is taken from them at once
            # (OQ-030, OQ-049, user ruling 2026-10-04).
            automatic = refill_shortfall(state, refill_seat)
        elif shortfall_is_stale(state):
            # Outside a player turn nothing makes a shortfall up: a Combat
            # reward's, or the last turn's once it closed, is dropped.
            automatic = drop_stale_shortfalls(state)
        elif intrigue_draw_is_queued(state):
            automatic = resolve_pending_intrigue_draw(state)
        elif exhausted_contract_choice_is_pending(state):
            automatic = resolve_exhausted_contract_choice(state)
        elif (held_owner := _held_contract_owner(state)) is not None:
            # The wait ended inside the same turn, the same seat's Conflict
            # rewards, or the Arrakeen Scouts step -- an Intrigue card
            # arrived, or a token the
            # owner can take was flipped up. Taking is not optional, so the
            # market reopens on its own (OQ-057(1)). Nothing in a non-empty
            # market reachable is no longer held unasked: the owner confirms
            # it with ``hold_contract_icons`` (OQ-059, user ruling
            # 2026-09-30).
            automatic = open_held_contract_icons(state, held_owner)
        elif skill_choice_is_queued(state):
            automatic = begin_skill_choice(state)
        elif four_bonus_choice_is_queued(state):
            # Friends Everywhere: the seat picks the Influence 4 bonus
            # first; an Emperor pick then queues its Spy (Arrakeen Scouts).
            automatic = begin_four_bonus_choice(state)
        elif track_spy_is_queued(state):
            # The Emperor track's Influence 4 Spy [Main p. 7] opens at once
            # outside its seat's own turn; inside it the entry waits for the
            # owner's ``place_track_spy`` (user ruling 2026-10-04, overriding
            # OQ-057 (15)).
            automatic = begin_track_spy_placement(state)
        elif navigation_play_is_queued(state):
            automatic = begin_navigation_play(state)
        elif combat_participants_are_stale(state):
            # A Combat Intrigue card's own window resolved and its play left
            # a participant with no unit: the loop drops them now (OQ-003).
            automatic = refresh_combat_participants(state)
        elif scouts_effect_can_advance(state):
            # Arrakeen Scouts: the next automatic step of a seat's line.
            automatic = advance_scouts_effect(state)
        elif combat_held_contract_owner(state) is not None:
            # A Conflict reward's Contract icons held to the end of that
            # seat's Conflict rewards fizzle there (user ruling 2026-10-02,
            # L2-Q2: "보상 끝까지 보류 후 불발").
            automatic = fizzle_combat_held_contract_icons(state)
        elif spent_conflict_end_window(state):
            # A Conflict-end window a card was played in, back on top with
            # its seat holding no Intrigue card, closes (OQ-103, OQ-109).
            automatic = close_spent_conflict_end_window(state)
        elif state.decision_stack:
            break
        elif scouts_step_is_pending(state):
            # Arrakeen Scouts: the round's Scouts step, one unit at a time,
            # until it opens the First Player's turn.
            automatic = advance_scouts_step(state)
        elif state.phase is GamePhase.COMBAT:
            if not state.combat_intrigue_complete:
                automatic = begin_combat_intrigue(state)
            elif not state.combat_rewards_resolved:
                automatic = resolve_combat_rewards(state)
            elif not state.combat_end_triggers_offered:
                # A pause after the rewards (rules/pauses.py), so the last
                # recipient's choice can be taken back before the
                # Conflict-end windows open, like the earlier recipients';
                # its answer offers the windows.
                automatic = (
                    push_pause(state, CONFLICT_END, f"round:{state.round_number}")
                    if state.combat_rewards_paid > 0
                    else offer_conflict_end_triggers(state)
                )
            elif any(seat.tech_cards_owed for seat in state.players):
                # The card Planetary Array owes for the win is drawn before
                # the cleanup runs on into the next round (OQ-108): with a
                # Conflict-end window open it is drawn as that step settles;
                # with none, here (a reshuffle stops the run).
                automatic = draw_owed_tech_cards(RuleResult(state=state))
            else:
                automatic = finish_combat(state)
        elif state.phase is GamePhase.MAKERS:
            automatic = resolve_makers(state)
        elif state.phase is GamePhase.RECALL_OR_ENDGAME:
            automatic = resolve_recall_or_endgame(state)
        elif state.phase is GamePhase.ROUND_START:
            # After a round, its last choices (a reward recipient's, a
            # Conflict-end Intrigue window's) are held at a pause before the
            # next round's reshuffles and reveal (rules/pauses.py); the
            # pause's answer prepares the round. The first round follows the
            # setup (and its explicit last Leader pick) with no pause.
            automatic = (
                prepare_round_start(state)
                if state.round_number == 0
                else push_pause(state, ROUND_START, f"round:{state.round_number + 1}")
            )
        elif state.phase is GamePhase.ENDGAME:
            if can_finish_endgame_automatically(state):
                automatic = finish_endgame_without_pending_effects(state)
            elif not state.endgame_intrigue_complete:
                automatic = begin_endgame_intrigue(state)
            else:
                break
        else:
            break
        state = automatic.state
        events.extend(automatic.events)
    return RuleResult(state=state, events=tuple(events))
