"""Legal-action composition for the Agent-turn effect frame.

The Agent-turn effect frame carries several pending groups at once (card
effect, board effect, Faction Influence, Contract completion, deployment). This
module decides which of those groups may currently offer actions and in which
order, so the dispatcher does not have to know the frame's internal flags.
"""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import legal_agent_card_acquisitions
from dune_imperium.rules.agent_effects import (
    legal_agent_card_discard_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_intrigue_payment_actions,
    legal_agent_card_long_live_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_recall_actions,
    legal_agent_card_spy_actions,
    legal_agent_card_trash_actions,
    legal_corrinth_city_payment_actions,
)
from dune_imperium.rules.board_effects import (
    CHOICE_DRIVEN_SPACE_IDS,
    legal_espionage_actions,
    legal_maker_space_actions,
    legal_sietch_tabr_actions,
)
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.contracts import legal_contract_completion_actions
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.leader_abilities import (
    legal_feyd_track_actions,
    legal_leader_board_repeat_actions,
    legal_leader_placement_ability_actions,
    legal_leader_signet_actions,
)
from dune_imperium.rules.spies import legal_gather_intelligence_actions

# Serial Agent-card choices. When any of these offers an action, the generic
# ``resolve_agent_card_effect`` action is withheld until the choice is made.
_AGENT_CARD_CHOICE_PROVIDERS = (
    legal_agent_card_trash_actions,
    legal_agent_card_discard_actions,
    legal_agent_card_payment_actions,
    legal_corrinth_city_payment_actions,
    legal_agent_card_intrigue_payment_actions,
    legal_agent_card_recall_actions,
    legal_agent_card_spy_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_acquisitions,
    legal_feyd_track_actions,
    legal_leader_signet_actions,
)


def legal_agent_effect_frame_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every action the effect-frame owner may take right now."""

    frame, context = current_agent_effect_context(state)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()

    if context.get("long_live_fighters_selection_started") is True:
        # Long Live the Fighters is one atomic card effect. Once its private
        # selection starts, no board/Faction/combat choice may be interleaved
        # before the second card selection commits.
        return legal_agent_card_long_live_actions(state, player)
    pending_groups = _pending_group_actions(state, player, context)

    gather_intelligence_actions = legal_gather_intelligence_actions(state, player)
    if gather_intelligence_actions:
        return gather_intelligence_actions

    return (
        *pending_groups,
        *legal_leader_placement_ability_actions(state, player),
        *legal_leader_board_repeat_actions(state, player),
        *legal_contract_completion_actions(state, player),
        *legal_espionage_actions(state, player),
        *legal_sietch_tabr_actions(state, player),
        *legal_maker_space_actions(state, player),
        *legal_combat_deployments(state, player),
        *legal_intrigue_play_actions(state, player),
    )


def _pending_group_actions(
    state: GameState,
    player: int,
    context: dict[str, bool | int | str],
) -> tuple[DomainAction, ...]:
    actions: list[DomainAction] = []
    if context["pending_agent_effect"] is True:
        choice_actions = tuple(
            action
            for provider in _AGENT_CARD_CHOICE_PROVIDERS
            for action in provider(state, player)
        )
        if choice_actions:
            actions.extend(choice_actions)
        else:
            actions.append(
                DomainAction(action_id="resolve_agent_card_effect", actor=player)
            )
    if (
        context["pending_board_effect"] is True
        and context["space_id"] not in CHOICE_DRIVEN_SPACE_IDS
    ):
        actions.append(DomainAction(action_id="resolve_board_effect", actor=player))
    if context["pending_faction_influence"] is True:
        actions.append(
            DomainAction(action_id="resolve_faction_influence", actor=player)
        )
    return tuple(actions)
