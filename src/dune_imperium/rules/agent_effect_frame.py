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
    agent_card_effect_is_unavailable,
    graft_boxes_are_stalled,
    legal_agent_card_contract_completion_actions,
    legal_agent_card_discard_actions,
    legal_agent_card_icon_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_intrigue_payment_actions,
    legal_agent_card_opponent_retreat_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_recall_actions,
    legal_agent_card_spy_actions,
    legal_agent_card_trash_actions,
    legal_corrinth_city_payment_actions,
)
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    legal_desert_tactics_actions,
    legal_espionage_actions,
    legal_imperial_privilege_actions,
    legal_maker_space_actions,
    legal_shipping_actions,
    legal_sietch_tabr_actions,
    legal_tuek_sietch_actions,
)
from dune_imperium.rules.combat_deployment import (
    legal_agent_turn_finish_actions,
    legal_combat_deployments,
    legal_commander_deployments,
    legal_commander_withdrawals,
    legal_troop_withdrawals,
)
from dune_imperium.rules.contracts import legal_contract_completion_actions
from dune_imperium.rules.effects import (
    current_agent_effect_context,
    pending_agent_icons,
)
from dune_imperium.rules.graft import legal_graft_switch_actions
from dune_imperium.rules.immortality import (
    legal_family_atomics_actions,
    legal_specimen_return_actions,
)
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.leader_abilities import (
    legal_feyd_track_actions,
    legal_leader_board_repeat_actions,
    legal_leader_placement_ability_actions,
    legal_leader_signet_actions,
)
from dune_imperium.rules.sardaukar import (
    legal_commander_recruit_actions,
    legal_sardaukar_commander_actions,
)
from dune_imperium.rules.spies import legal_gather_intelligence_actions
from dune_imperium.rules.tech import (
    legal_tech_acquisition_actions,
    legal_tech_flip_actions,
)

# Serial Agent-card choices. When any of these offers an action, the generic
# ``resolve_agent_card_effect`` action is withheld until the choice is made.
_AGENT_CARD_CHOICE_PROVIDERS = (
    legal_agent_card_trash_actions,
    legal_agent_card_contract_completion_actions,
    legal_agent_card_opponent_retreat_actions,
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

    pending_groups = _pending_group_actions(state, player, context)

    gather_intelligence_actions = legal_gather_intelligence_actions(state, player)
    if gather_intelligence_actions:
        return gather_intelligence_actions

    return (
        *pending_groups,
        *_graft_switch_actions(state, player),
        *legal_leader_placement_ability_actions(state, player),
        *legal_leader_board_repeat_actions(state, player),
        *legal_contract_completion_actions(state, player),
        *legal_espionage_actions(state, player),
        *legal_sietch_tabr_actions(state, player),
        *legal_tuek_sietch_actions(state, player),
        *legal_shipping_actions(state, player),
        *legal_desert_tactics_actions(state, player),
        *legal_imperial_privilege_actions(state, player),
        *legal_maker_space_actions(state, player),
        *legal_sardaukar_commander_actions(state, player),
        *legal_tech_acquisition_actions(state, player),
        *legal_tech_flip_actions(state, player),
        *legal_commander_recruit_actions(state, player),
        *legal_combat_deployments(state, player),
        *legal_commander_deployments(state, player),
        *legal_intrigue_play_actions(state, player),
        *legal_specimen_return_actions(state, player),
        *legal_family_atomics_actions(state, player),
        *legal_agent_turn_finish_actions(state, player),
        # Withdrawals last (OQ-029): a "first legal action" walk deploys up
        # to the limit and finishes instead of cycling deploy/withdraw.
        *legal_troop_withdrawals(state, player),
        *legal_commander_withdrawals(state, player),
    )


def _graft_switch_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the graft switch unless both boxes could only fizzle (OQ-057).

    With the active box stalled the owner may still switch to a live partner
    box; when the partner's box would fizzle too, only the turn end remains
    (otherwise a policy could switch back and forth forever).
    """

    actions = legal_graft_switch_actions(state, player)
    if not actions or not graft_boxes_are_stalled(state):
        return actions
    return ()


def _pending_group_actions(
    state: GameState,
    player: int,
    context: dict[str, bool | int | str],
) -> tuple[DomainAction, ...]:
    actions: list[DomainAction] = []
    if context["pending_agent_effect"] is True and pending_agent_icons(context):
        # A multi-icon Agent box: every pending icon is offered at once, the
        # automatic ones through their keyed resolution and the choice icons
        # (Steersman's recall, Dangerous Rhetoric's Faction) through their
        # own providers (OQ-027).
        actions.extend(legal_agent_card_icon_actions(state, player))
        actions.extend(legal_agent_card_recall_actions(state, player))
        actions.extend(legal_agent_card_influence_actions(state, player))
    elif context["pending_agent_effect"] is True:
        choice_actions = tuple(
            action
            for provider in _AGENT_CARD_CHOICE_PROVIDERS
            for action in provider(state, player)
        )
        if choice_actions:
            actions.extend(choice_actions)
        elif not agent_card_effect_is_unavailable(state):
            # A mandatory box whose condition is false waits for the turn's
            # end instead of fizzling now (OQ-057); ``finish_agent_turn``
            # resolves it then.
            actions.append(
                DomainAction(action_id="resolve_agent_card_effect", actor=player)
            )
    # One action per pending automatic icon of the visited space; its
    # choice icons are offered by the dedicated providers below (OQ-027).
    actions.extend(legal_board_effect_actions(state, player))
    if context["pending_faction_influence"] is True:
        actions.append(
            DomainAction(action_id="resolve_faction_influence", actor=player)
        )
    return tuple(actions)
