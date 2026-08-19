"""Concrete dispatcher for the currently implemented Uprising rules slice."""

from dataclasses import replace

from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, DynamicCost
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
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
    apply_imperium_acquisition,
    apply_reserve_acquisition,
    legal_imperium_acquisitions,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_trash,
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    apply_espionage_action,
    apply_maker_space_action,
    apply_sietch_tabr_action,
    board_effects_for,
    legal_espionage_actions,
    legal_maker_space_actions,
    legal_sietch_tabr_actions,
    resolve_board_effect,
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
from dune_imperium.rules.combat_deployment import (
    apply_combat_deployment,
    legal_combat_deployments,
)
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.endgame import (
    apply_endgame_wild_action,
    begin_endgame_wild_choice,
    can_finish_endgame_automatically,
    finish_endgame_without_pending_effects,
    legal_endgame_wild_actions,
    unambiguous_endgame_wild_match,
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
    begin_reveal_turn,
    current_reveal_context,
    finish_reveal_turn,
    legal_finish_reveal_actions,
    legal_reveal_actions,
)
from dune_imperium.rules.setup import create_initial_state
from dune_imperium.rules.spies import (
    apply_gather_intelligence_action,
    legal_gather_intelligence_actions,
)

DEFAULT_LEADER_IDS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


class UprisingRulesEngine(RulesEngine):
    """Connect implemented rule modules into one playable round state machine.

    The dispatcher deliberately omits actions whose immediate downstream effect
    is not implemented yet. This keeps every advertised legal action executable
    within the current M3 vertical slice.
    """

    def __init__(self, leader_ids: tuple[str, ...] = DEFAULT_LEADER_IDS) -> None:
        self._leader_ids = leader_ids

    def _initial_state(self, config: RulesetConfig, seed: int) -> GameState:
        setup = create_initial_state(config, seed, self._leader_ids)
        started = prepare_round_start(setup.state)
        return replace(started.state, event_log=started.events)

    def _apply_chance(
        self,
        state: GameState,
        outcome: ChanceOutcome,
    ) -> RuleResult:
        result = (
            apply_personal_draw_reshuffle(state, outcome)
            if personal_draw_is_pending(state)
            else apply_round_start_reshuffle(state, outcome)
        )
        return _advance_automatic(result)

    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        """Return all currently supported actions for the decision owner."""

        try:
            current_agent_effect_context(state)
        except ValueError:
            pass
        else:
            gather_intelligence_actions = legal_gather_intelligence_actions(
                state, player
            )
            if gather_intelligence_actions:
                return gather_intelligence_actions
            return (
                *self._agent_effect_actions(state, player),
                *legal_espionage_actions(state, player),
                *legal_sietch_tabr_actions(state, player),
                *legal_maker_space_actions(state, player),
                *legal_combat_deployments(state, player),
            )

        try:
            current_reveal_context(state)
        except ValueError:
            pass
        else:
            return (
                *legal_reserve_acquisitions(state, player),
                *self._supported_imperium_acquisitions(state, player),
                *legal_finish_reveal_actions(state, player),
            )

        actions: list[DomainAction] = []
        actions.extend(legal_endgame_wild_actions(state, player))
        actions.extend(legal_control_defense_actions(state, player))
        actions.extend(self._supported_agent_actions(state, player))
        actions.extend(legal_reveal_actions(state, player))
        actions.extend(legal_combat_intrigue_actions(state, player))
        actions.extend(legal_combat_reward_optional_payment_actions(state, player))
        actions.extend(legal_combat_reward_spy_recall_actions(state, player))
        actions.extend(legal_combat_reward_trash_actions(state, player))
        actions.extend(legal_combat_reward_spy_actions(state, player))
        actions.extend(legal_combat_reward_influence_actions(state, player))
        actions.extend(legal_distinct_combat_reward_influence_actions(state, player))
        return tuple(actions)

    def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
        handlers = {
            "decline_control_defense": apply_control_defense_action,
            "decline_agent_card_trash": apply_agent_card_trash,
            "decline_endgame_wild_match": apply_endgame_wild_action,
            "decline_gather_intelligence": apply_gather_intelligence_action,
            "deploy_control_defense": apply_control_defense_action,
            "agent_turn": apply_agent_action,
            "reveal_turn": begin_reveal_turn,
            "resolve_agent_card_effect": _apply_agent_card_effect,
            "resolve_board_effect": _apply_board_effect,
            "resolve_faction_influence": _apply_faction_influence,
            "recall_spy_for_espionage": apply_espionage_action,
            "resolve_espionage_place_spy": apply_espionage_action,
            "resolve_espionage_without_spy": apply_espionage_action,
            "take_sietch_tabr_supplies": apply_sietch_tabr_action,
            "take_sietch_tabr_water": apply_sietch_tabr_action,
            "take_sietch_tabr_water_and_destroy_wall": apply_sietch_tabr_action,
            "harvest_maker_spice": apply_maker_space_action,
            "match_endgame_wild_icon": apply_endgame_wild_action,
            "summon_maker_sandworms": apply_maker_space_action,
            "deploy_troops": apply_combat_deployment,
            "acquire_reserve": apply_reserve_acquisition,
            "acquire_imperium": apply_imperium_acquisition,
            "finish_reveal": finish_reveal_turn,
            "gather_intelligence": apply_gather_intelligence_action,
            "pass_combat_intrigue": apply_combat_intrigue_pass,
            "decline_combat_reward": _apply_decline_combat_reward,
            "pay_combat_reward": apply_combat_reward_optional_payment,
            "recall_spies_for_combat_reward": apply_combat_reward_spy_recall,
            "decline_combat_reward_trash": apply_combat_reward_trash,
            "trash_combat_reward_card": apply_combat_reward_trash,
            "trash_agent_card": apply_agent_card_trash,
            "place_combat_reward_spy": apply_combat_reward_spy,
            "choose_combat_reward_influence": apply_combat_reward_influence,
            "choose_distinct_combat_reward_influence": (
                apply_distinct_combat_reward_influence
            ),
        }
        result = handlers[action.action_id](state, action)
        return _advance_automatic(result)

    def observe(self, state: GameState, player: int) -> PlayerView:
        return observe_state(state, player)

    def _supported_agent_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        return tuple(
            action
            for action in legal_agent_actions(state, player)
            if _agent_action_is_supported(state, action)
        )

    def _supported_imperium_acquisitions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        return tuple(
            action
            for action in legal_imperium_acquisitions(state, player)
            if not imperium_card_for_instance(
                str(dict(action.arguments)["instance_id"])
            ).has_acquisition_bonus
        )

    def _agent_effect_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        try:
            frame, context = current_agent_effect_context(state)
        except ValueError:
            return ()
        if (
            not isinstance(frame.decision, PlayerDecision)
            or frame.decision.owner != player
        ):
            return ()
        actions: list[DomainAction] = []
        if context["pending_agent_effect"] is True:
            trash_actions = legal_agent_card_trash_actions(state, player)
            if trash_actions:
                actions.extend(trash_actions)
            else:
                actions.append(
                    DomainAction(action_id="resolve_agent_card_effect", actor=player)
                )
        if context["pending_board_effect"] is True and context["space_id"] not in (
            "espionage",
            "sietch_tabr",
            "deep_desert",
            "hagga_basin",
            "imperial_basin",
        ):
            actions.append(DomainAction(action_id="resolve_board_effect", actor=player))
        if context["pending_faction_influence"] is True:
            actions.append(
                DomainAction(action_id="resolve_faction_influence", actor=player)
            )
        return tuple(actions)


def _agent_action_is_supported(state: GameState, action: DomainAction) -> bool:
    arguments = dict(action.arguments)
    card_id = arguments["card_id"]
    space_id = arguments["space_id"]
    if not isinstance(card_id, str) or not isinstance(space_id, str):
        return False
    card = personal_card_for_instance(card_id)
    if card.agent_effect not in (
        None,
        PersonalCardAgentEffect.TRASH_SELF,
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
    ):
        return False
    if space_id in (
        "espionage",
        "sietch_tabr",
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
    ):
        return True
    space = BOARD_SPACES_BY_ID[space_id]
    requested_option = arguments.get("cost_option")
    if isinstance(requested_option, int) and not isinstance(requested_option, bool):
        cost_option = requested_option
    elif space.dynamic_cost is DynamicCost.SWORDMASTER:
        cost_option = int(any(player.swordmaster_acquired for player in state.players))
    else:
        cost_option = 0
    try:
        board_effects_for(state, space_id, cost_option)
    except NotImplementedError:
        return False
    return True


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
    frame_id = state.decision_stack[-1].frame_id
    if ":combat_reward_optional:" in frame_id:
        return apply_combat_reward_optional_payment(state, action)
    return apply_combat_reward_spy_recall(state, action)


def _advance_automatic(result: RuleResult) -> RuleResult:
    state = result.state
    events: list[GameEvent] = list(result.events)
    while not state.decision_stack:
        if state.phase is GamePhase.COMBAT:
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
            elif (
                not any(player.intrigue_cards for player in state.players)
                and unambiguous_endgame_wild_match(state) is not None
            ):
                automatic = begin_endgame_wild_choice(state)
            else:
                break
        else:
            break
        state = automatic.state
        events.extend(automatic.events)
    return RuleResult(state=state, events=tuple(events))
