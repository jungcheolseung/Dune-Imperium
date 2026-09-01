"""Concrete dispatcher for the implemented Uprising rules.

Dispatch is table-driven. ``LEGAL_ACTION_PROVIDERS`` maps the kind of the top
decision frame to the ordered rule functions that may offer actions in that
frame, and ``ACTION_HANDLERS`` maps every ``action_id`` to the function that
resolves it. Adding a rule boundary means adding a frame kind and one table
entry per side rather than editing dispatcher logic.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Final

from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, DynamicCost
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
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
    legal_acquisition_spy_actions,
    legal_imperium_acquisitions,
    legal_manipulated_acquisitions,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.agent_effect_frame import legal_agent_effect_frame_actions
from dune_imperium.rules.agent_effects import (
    apply_agent_card_discard,
    apply_agent_card_influence,
    apply_agent_card_intrigue_payment,
    apply_agent_card_long_live_action,
    apply_agent_card_payment,
    apply_agent_card_recall,
    apply_agent_card_spy_action,
    apply_agent_card_trash,
    apply_corrinth_city_payment,
    apply_opponent_card_discard,
    legal_opponent_card_discard_actions,
    resolve_agent_card_effect,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    apply_desert_tactics_action,
    apply_espionage_action,
    apply_imperial_privilege_action,
    apply_maker_space_action,
    apply_secrets_steal,
    apply_shipping_action,
    apply_sietch_tabr_action,
    board_effect_is_implemented,
    resolve_board_effect,
    secrets_steal_is_pending,
)
from dune_imperium.rules.card_draw import (
    apply_personal_draw_reshuffle,
    personal_draw_is_pending,
)
from dune_imperium.rules.combat import (
    apply_combat_intrigue_pass,
    apply_combat_reward_influence,
    apply_combat_reward_optional_payment,
    apply_combat_reward_spy,
    apply_combat_reward_spy_recall,
    apply_combat_reward_trash,
    apply_distinct_combat_reward_influence,
    begin_combat_intrigue,
    finish_combat,
    legal_combat_intrigue_actions,
    legal_combat_reward_influence_actions,
    legal_combat_reward_optional_payment_actions,
    legal_combat_reward_spy_actions,
    legal_combat_reward_spy_recall_actions,
    legal_combat_reward_trash_actions,
    legal_distinct_combat_reward_influence_actions,
    resolve_combat_rewards,
)
from dune_imperium.rules.combat_deployment import apply_combat_deployment
from dune_imperium.rules.contracts import (
    apply_contract_action,
    apply_contract_completion,
    apply_contract_recall_action,
    apply_contract_spy_action,
    exhausted_contract_choice_is_pending,
    legal_contract_actions,
    legal_contract_recall_actions,
    legal_contract_spy_actions,
    resolve_exhausted_contract_choice,
)
from dune_imperium.rules.endgame import (
    apply_endgame_intrigue_action,
    begin_endgame_intrigue,
    can_finish_endgame_automatically,
    finish_endgame_without_pending_effects,
    legal_endgame_intrigue_actions,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue import (
    apply_intrigue_choice,
    apply_intrigue_play,
    legal_intrigue_choice_actions,
    legal_intrigue_play_actions,
)
from dune_imperium.rules.intrigue_deck import (
    apply_intrigue_reshuffle,
    intrigue_draw_is_queued,
    intrigue_reshuffle_is_pending,
    resolve_pending_intrigue_draw,
)
from dune_imperium.rules.intrigue_triggers import (
    apply_trigger_spy_action,
    legal_trigger_spy_actions,
    offer_deployment_triggers,
)
from dune_imperium.rules.leader_abilities import (
    apply_feyd_track_action,
    apply_leader_board_repeat,
    apply_leader_card_trash,
    apply_leader_placement_ability,
    apply_leader_reveal_action,
    apply_leader_signet_acquire,
    apply_leader_signet_payment,
    apply_leader_spy_action,
    apply_shaddam_signet_choice,
    grant_leader_reveal_passives,
    leader_signet_is_implemented,
    legal_leader_reveal_actions,
)
from dune_imperium.rules.leader_draft import (
    apply_leader_draft_pick,
    legal_leader_draft_actions,
)
from dune_imperium.rules.phases import (
    apply_control_defense_action,
    apply_round_start_reshuffle,
    legal_control_defense_actions,
    prepare_round_start,
    resolve_makers,
    resolve_recall_or_endgame,
)
from dune_imperium.rules.reveal_turn import (
    apply_contract_reveal_choice,
    apply_corrinth_city_reveal,
    apply_reveal_card_trash,
    apply_reveal_influence_exchange,
    apply_reveal_sandworm_action,
    apply_reveal_spice_influence,
    apply_reveal_spy_action,
    apply_reveal_troop_retreat,
    begin_reveal_turn,
    finish_reveal_turn,
    legal_contract_reveal_choice_actions,
    legal_corrinth_city_reveal_actions,
    legal_finish_reveal_actions,
    legal_reveal_actions,
    legal_reveal_card_trash_actions,
    legal_reveal_influence_exchange_actions,
    legal_reveal_sandworm_actions,
    legal_reveal_spice_influence_actions,
    legal_reveal_spy_actions,
    legal_reveal_troop_retreat_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.rules.spies import apply_gather_intelligence_action

type LegalActionProvider = Callable[[GameState, int], tuple[DomainAction, ...]]
type ActionHandler = Callable[[GameState, DomainAction], RuleResult]

DEFAULT_LEADER_IDS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


def _apply_agent_card_effect(state: GameState, action: DomainAction) -> RuleResult:
    del action
    return resolve_agent_card_effect(state)


def _apply_board_effect(state: GameState, action: DomainAction) -> RuleResult:
    del action
    return resolve_board_effect(state)


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


def _executable_agent_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Withhold Agent placements whose board effect is not implemented yet."""

    return tuple(
        action
        for action in legal_agent_actions(state, player)
        if _agent_action_is_executable(state, action)
    )


def _agent_action_is_executable(state: GameState, action: DomainAction) -> bool:
    arguments = dict(action.arguments)
    card_id = arguments["card_id"]
    space_id = arguments["space_id"]
    if not isinstance(card_id, str) or not isinstance(space_id, str):
        return False
    if personal_card_for_instance(
        card_id
    ).agent_effect is PersonalCardAgentEffect.LEADER_SIGNET and not (
        leader_signet_is_implemented(state.players[action.actor].leader_id)
    ):
        return False
    requested_option = arguments.get("cost_option")
    if isinstance(requested_option, int) and not isinstance(requested_option, bool):
        cost_option = requested_option
    elif BOARD_SPACES_BY_ID[space_id].dynamic_cost is DynamicCost.SWORDMASTER:
        cost_option = int(any(player.swordmaster_acquired for player in state.players))
    else:
        cost_option = 0
    return board_effect_is_implemented(state, space_id, cost_option)


LEGAL_ACTION_PROVIDERS: Final[Mapping[str, tuple[LegalActionProvider, ...]]] = {
    FrameKind.TURN: (
        _executable_agent_actions,
        legal_reveal_actions,
        legal_intrigue_play_actions,
    ),
    FrameKind.AGENT_EFFECTS: (legal_agent_effect_frame_actions,),
    FrameKind.OPPONENT_CARD_DISCARD: (legal_opponent_card_discard_actions,),
    FrameKind.ACQUISITION_SPY: (legal_acquisition_spy_actions,),
    FrameKind.REVEAL: (
        legal_reserve_acquisitions,
        legal_imperium_acquisitions,
        legal_manipulated_acquisitions,
        legal_leader_reveal_actions,
        legal_finish_reveal_actions,
        legal_intrigue_play_actions,
    ),
    FrameKind.REVEAL_CHOICE: (
        legal_corrinth_city_reveal_actions,
        legal_contract_reveal_choice_actions,
        legal_reveal_card_trash_actions,
        legal_reveal_spy_actions,
        legal_reveal_influence_exchange_actions,
        legal_reveal_sandworm_actions,
        legal_reveal_spice_influence_actions,
        legal_reveal_troop_retreat_actions,
    ),
    FrameKind.CONTRACT_MARKET: (legal_contract_actions,),
    FrameKind.CONTRACT_REWARD_SPY: (legal_contract_spy_actions,),
    FrameKind.CONTRACT_REWARD_RECALL: (legal_contract_recall_actions,),
    FrameKind.CONTROL_DEFENSE: (legal_control_defense_actions,),
    FrameKind.COMBAT_INTRIGUE: (
        legal_combat_intrigue_actions,
        legal_intrigue_play_actions,
    ),
    FrameKind.COMBAT_REWARD_OPTIONAL: (legal_combat_reward_optional_payment_actions,),
    FrameKind.COMBAT_REWARD_SPY_RECALL: (legal_combat_reward_spy_recall_actions,),
    FrameKind.COMBAT_REWARD_TRASH: (legal_combat_reward_trash_actions,),
    FrameKind.COMBAT_REWARD_SPY: (legal_combat_reward_spy_actions,),
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
    FrameKind.INTRIGUE_TRIGGER_SPY: (legal_trigger_spy_actions,),
    FrameKind.LEADER_DRAFT: (legal_leader_draft_actions,),
}

ACTION_HANDLERS: Final[Mapping[str, ActionHandler]] = {
    # Setup Leader draft (OQ-007 convention)
    "pick_leader": apply_leader_draft_pick,
    # Turn choice and Plot Intrigue
    "agent_turn": apply_agent_action,
    "reveal_turn": begin_reveal_turn,
    "play_intrigue": apply_intrigue_play,
    "choose_intrigue_faction": apply_intrigue_choice,
    "choose_intrigue_discard": apply_intrigue_choice,
    "detonate_shield_wall": apply_intrigue_choice,
    "keep_shield_wall": apply_intrigue_choice,
    "deploy_intrigue_troops": apply_intrigue_choice,
    "trash_intrigue_card": apply_intrigue_choice,
    "decline_intrigue_trash": apply_intrigue_choice,
    "decline_intrigue_spy": apply_intrigue_choice,
    "place_intrigue_spy": apply_intrigue_choice,
    "recall_spy_for_intrigue": apply_intrigue_choice,
    "retreat_intrigue_troops": apply_intrigue_choice,
    "acquire_intrigue_imperium": apply_intrigue_choice,
    "acquire_intrigue_reserve": apply_intrigue_choice,
    "flip_battle_card": apply_intrigue_choice,
    "manipulate_imperium_row": apply_intrigue_choice,
    "acquire_manipulated_imperium": apply_manipulated_acquisition,
    "place_trigger_spy": apply_trigger_spy_action,
    "recall_spy_for_trigger": apply_trigger_spy_action,
    "decline_intrigue_trigger": apply_trigger_spy_action,
    # Agent-turn effect frame
    "resolve_agent_card_effect": _apply_agent_card_effect,
    "resolve_board_effect": _apply_board_effect,
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
    "harvest_maker_spice": apply_maker_space_action,
    "summon_maker_sandworms": apply_maker_space_action,
    "choose_shipping_influence": apply_shipping_action,
    "resolve_desert_tactics_without_trash": apply_desert_tactics_action,
    "trash_card_for_desert_tactics": apply_desert_tactics_action,
    "decline_imperial_privilege_intrigue": apply_imperial_privilege_action,
    "discard_intrigue_for_imperial_privilege": apply_imperial_privilege_action,
    "recall_agent_for_imperial_privilege": apply_imperial_privilege_action,
    "deploy_troops": apply_combat_deployment,
    # Agent-card serial choices
    "trash_agent_card": apply_agent_card_trash,
    "decline_agent_card_trash": apply_agent_card_trash,
    "discard_agent_card": apply_agent_card_discard,
    "decline_agent_card_discard": apply_agent_card_discard,
    "pay_agent_card_water": apply_agent_card_payment,
    "pay_agent_card_spice": apply_agent_card_payment,
    "decline_agent_card_payment": apply_agent_card_payment,
    "pay_corrinth_city": apply_corrinth_city_payment,
    "select_corrinth_city_discard": apply_corrinth_city_payment,
    "decline_corrinth_city_payment": apply_corrinth_city_payment,
    "pay_agent_card_intrigue_and_spice": apply_agent_card_intrigue_payment,
    "decline_agent_card_intrigue_payment": apply_agent_card_intrigue_payment,
    "recall_agent_for_agent_card": apply_agent_card_recall,
    "place_agent_card_spy": apply_agent_card_spy_action,
    "recall_spy_for_agent_card": apply_agent_card_spy_action,
    "choose_agent_card_influence": apply_agent_card_influence,
    "acquire_imperium_with_solari": apply_agent_card_acquisition,
    "acquire_reserve_with_solari": apply_agent_card_acquisition,
    "decline_agent_card_acquisition": apply_agent_card_acquisition,
    "select_long_live_fighters_draw": apply_agent_card_long_live_action,
    "select_long_live_fighters_discard": apply_agent_card_long_live_action,
    "discard_opponent_card": apply_opponent_card_discard,
    # Leader Signet Ring and placement-triggered Leader abilities
    "advance_feyd_track": apply_feyd_track_action,
    "trash_leader_card": apply_leader_card_trash,
    "decline_leader_card_trash": apply_feyd_track_action,
    "place_leader_spy": apply_leader_spy_action,
    "recall_spy_for_leader_placement": apply_leader_spy_action,
    "pay_leader_signet_spice": apply_leader_signet_payment,
    "pay_leader_signet_solari": apply_leader_signet_payment,
    "decline_leader_signet_payment": apply_leader_signet_payment,
    "acquire_leader_imperium": apply_leader_signet_acquire,
    "acquire_leader_reserve": apply_leader_signet_acquire,
    "gain_leader_signet_troop": apply_shaddam_signet_choice,
    "choose_leader_signet_influence": apply_shaddam_signet_choice,
    "use_other_memories": apply_leader_placement_ability,
    "decline_other_memories": apply_leader_placement_ability,
    "pay_leader_board_repeat": apply_leader_board_repeat,
    "decline_leader_board_repeat": apply_leader_board_repeat,
    # Reveal turn
    "acquire_reserve": apply_reserve_acquisition,
    "acquire_imperium": apply_imperium_acquisition,
    "retreat_leader_troop": apply_leader_reveal_action,
    "recall_spy_for_leader": apply_leader_reveal_action,
    "finish_reveal": finish_reveal_turn,
    "place_acquisition_spy": apply_acquisition_spy_action,
    "recall_spy_for_acquisition": apply_acquisition_spy_action,
    # Reveal serial choices
    "gain_five_reveal_solari": apply_corrinth_city_reveal,
    "take_high_council_from_reveal": apply_corrinth_city_reveal,
    "keep_contract_reveal_spice": apply_contract_reveal_choice,
    "trash_contract_reveal_for_vp": apply_contract_reveal_choice,
    "trash_reveal_card": apply_reveal_card_trash,
    "decline_reveal_card_trash": apply_reveal_card_trash,
    "place_reveal_spy": apply_reveal_spy_action,
    "recall_spy_for_reveal": apply_reveal_spy_action,
    "recall_spy_for_reveal_placement": apply_reveal_spy_action,
    "recall_spies_for_reveal": apply_reveal_spy_action,
    "gain_two_reveal_strength": apply_reveal_spy_action,
    "decline_reveal_spy_recall": apply_reveal_spy_action,
    "exchange_reveal_influence": apply_reveal_influence_exchange,
    "decline_reveal_influence_exchange": apply_reveal_influence_exchange,
    "pay_reveal_water_for_sandworm": apply_reveal_sandworm_action,
    "decline_reveal_sandworm": apply_reveal_sandworm_action,
    "pay_reveal_spice_influence": apply_reveal_spice_influence,
    "decline_reveal_spice_influence": apply_reveal_spice_influence,
    "retreat_two_troops_for_reveal": apply_reveal_troop_retreat,
    "decline_reveal_troop_retreat": apply_reveal_troop_retreat,
    # Contracts
    "take_contract": apply_contract_action,
    "place_contract_spy": apply_contract_spy_action,
    "recall_spy_for_contract": apply_contract_spy_action,
    "recall_agent_for_contract": apply_contract_recall_action,
    # Round start and Combat
    "deploy_control_defense": apply_control_defense_action,
    "decline_control_defense": apply_control_defense_action,
    "pass_combat_intrigue": apply_combat_intrigue_pass,
    "pay_combat_reward": apply_combat_reward_optional_payment,
    "recall_spies_for_combat_reward": apply_combat_reward_spy_recall,
    "decline_combat_reward": _apply_decline_combat_reward,
    "trash_combat_reward_card": apply_combat_reward_trash,
    "decline_combat_reward_trash": apply_combat_reward_trash,
    "place_combat_reward_spy": apply_combat_reward_spy,
    "choose_combat_reward_influence": apply_combat_reward_influence,
    "choose_distinct_combat_reward_influence": (
        apply_distinct_combat_reward_influence
    ),
    # Endgame
    "match_endgame_wild_icon": apply_endgame_intrigue_action,
    "pass_endgame_intrigue": apply_endgame_intrigue_action,
}


class UprisingRulesEngine(RulesEngine):
    """Connect the implemented rule modules into one multi-round state machine."""

    def __init__(self, leader_ids: tuple[str, ...] = DEFAULT_LEADER_IDS) -> None:
        self._leader_ids = leader_ids

    def _initial_state(self, config: RulesetConfig, seed: int) -> GameState:
        if config.leader_draft:
            # The OQ-007 draft pauses in SETUP on the pick frames; the
            # engine's fixed leader_ids only serve the non-draft path.
            return create_draft_initial_state(config, seed).state
        setup = create_initial_state(config, seed, self._leader_ids)
        started = prepare_round_start(setup.state)
        return replace(started.state, event_log=started.events)

    def _apply_chance(
        self,
        state: GameState,
        outcome: ChanceOutcome,
    ) -> RuleResult:
        if personal_draw_is_pending(state):
            result = apply_personal_draw_reshuffle(state, outcome)
        elif intrigue_reshuffle_is_pending(state):
            result = apply_intrigue_reshuffle(state, outcome)
        elif secrets_steal_is_pending(state):
            result = apply_secrets_steal(state, outcome)
        else:
            result = apply_round_start_reshuffle(state, outcome)
        # An Intrigue draw granted by a Reveal passive may queue a reshuffle,
        # so the automatic advance runs again after the passives.
        result = grant_leader_reveal_passives(_advance_automatic(result))
        return offer_deployment_triggers(_advance_automatic(result))

    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        """Return the actions the top frame's providers offer to ``player``."""

        if not state.decision_stack:
            return ()
        frame = state.decision_stack[-1]
        if not isinstance(frame.decision, PlayerDecision):
            return ()
        providers = LEGAL_ACTION_PROVIDERS.get(frame.kind)
        if providers is None:
            raise RuntimeError(f"unknown decision frame kind: {frame.kind}")
        return tuple(
            action for provider in providers for action in provider(state, player)
        )

    def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
        result = _advance_automatic(ACTION_HANDLERS[action.action_id](state, action))
        # An Intrigue draw granted by a Reveal passive may queue a reshuffle,
        # so the automatic advance runs again after the passives.
        result = _advance_automatic(grant_leader_reveal_passives(result))
        return offer_deployment_triggers(result)

    def observe(self, state: GameState, player: int) -> PlayerView:
        return observe_state(state, player)


def _advance_automatic(result: RuleResult) -> RuleResult:
    state = result.state
    events: list[GameEvent] = list(result.events)
    while True:
        if intrigue_draw_is_queued(state):
            automatic = resolve_pending_intrigue_draw(state)
        elif exhausted_contract_choice_is_pending(state):
            automatic = resolve_exhausted_contract_choice(state)
        elif state.decision_stack:
            break
        elif state.phase is GamePhase.COMBAT:
            if not state.combat_intrigue_complete:
                automatic = begin_combat_intrigue(state)
            elif not state.combat_rewards_resolved:
                automatic = resolve_combat_rewards(state)
            else:
                automatic = finish_combat(state)
        elif state.phase is GamePhase.MAKERS:
            automatic = resolve_makers(state)
        elif state.phase is GamePhase.RECALL_OR_ENDGAME:
            automatic = resolve_recall_or_endgame(state)
        elif state.phase is GamePhase.ROUND_START:
            automatic = prepare_round_start(state)
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
