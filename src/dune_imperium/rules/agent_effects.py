"""Resolution of starting-card and Faction Agent-turn effects.

An Agent box that prints several independent icons (for example Hidden
Missive's troop and card draw) resolves them one action each in the owner's
order [Main p. 9] (OQ-027): ``resolve_agent_card_effect`` carries the icon's
``effect`` key, while icons that need a choice (Steersman's recall, Dangerous
Rhetoric's Faction) keep their dedicated actions. Arrow boxes pay their cost
first and then queue the reward icons the same way.
"""

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Final

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import (
    BattleIcon,
    PersonalCardAgentEffect,
    PersonalCardTrashEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.agent_icons import effective_agent_icons
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.combat import face_up_battle_icons
from dune_imperium.rules.combat_deployment import (
    grant_combat_icon,
    reconcile_deployment_after_retreat,
)
from dune_imperium.rules.contracts import (
    begin_contract_gain,
    complete_contract_by_effect,
)
from dune_imperium.rules.effects import (
    active_agent_card,
    advance_after_effect,
    arm_agent_icons,
    current_agent_effect_context,
    finish_agent_icon,
    is_grafted,
    other_grafted_card_id,
    pending_agent_icons,
    recruit_shortfall_events,
    recruit_troops,
)
from dune_imperium.rules.frames import FrameKind, context_int, replace_player
from dune_imperium.rules.immortality import advance_research, advance_tleilaxu
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.intrigue_peek import begin_intrigue_peek
from dune_imperium.rules.leader_abilities import (
    resolve_leader_signet,
    units_deployment_blocked,
)
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.planetologist import replace_sandworms, replaces_sandworms
from dune_imperium.rules.shield_wall import (
    current_conflict_is_shield_wall_protected,
    destroy_shield_wall,
)
from dune_imperium.rules.specimens import generate_specimens, spend_specimens
from dune_imperium.rules.spy_moves import turn_space_spy_frames
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_factions,
    place_spy,
    recall_spy,
)
from dune_imperium.rules.unit_loss import lose_unit, opponent_unit_loss_frames
from dune_imperium.rules.units import retreat_units

# Immortality boxes whose enum names do not fit a comparison line.
_DRAW_ONE_OR_COMBAT_ICON = (
    PersonalCardAgentEffect.DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO
)
_SPICE_AND_GRAFTED_INFLUENCE = (
    PersonalCardAgentEffect
    .GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD
)
_DRAW_RESEARCH_SPECIMEN = (
    PersonalCardAgentEffect.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED
)
_RESEARCH_AND_TRASH_FOR_VP = (
    PersonalCardAgentEffect.RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS
)
_GUILD_INFLUENCE_IF_SPICE = (
    PersonalCardAgentEffect.GAIN_SPACING_GUILD_INFLUENCE_IF_GAINED_SPICE_THIS_TURN
)
_SOLARI_PER_PARTNER_ICON = (
    PersonalCardAgentEffect
    .GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU
)
_CHOOSE_TWO_REWARDS = PersonalCardAgentEffect.CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU
_TRASH_GRAFTED_FOR_INFLUENCE = (
    PersonalCardAgentEffect.MAY_TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE
)
_LOSE_TROOP_FOR_CARDS = PersonalCardAgentEffect.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH
# Stitched Horror's four printed rewards, in card order.
STITCHED_HORROR_REWARDS: Final = ("water", "troop", "trash", "tleilaxu")
SLIG_FARMER_PRICE: Final = 5

# Agent-box icon keys resolved by ``resolve_agent_card_effect`` with
# ``effect=<key>``. Kept sorted: the action codec enumerates them.
AGENT_ICON_CARDS: Final = "cards"
AGENT_ICON_INTRIGUE: Final = "intrigue"
AGENT_ICON_PLEDGE: Final = "pledge"  # Pivotal Gambit's first-place Influence
AGENT_ICON_SOLARI: Final = "solari"
AGENT_ICON_SPICE: Final = "spice"
AGENT_ICON_TRASH_SELF: Final = "trash_self"
_TRASH_TO_DRAW_IF_BOND: Final = (
    PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND
)
AGENT_ICON_TROOPS: Final = "troops"
AGENT_ICON_WATER: Final = "water"
AUTOMATIC_AGENT_ICONS: Final = (
    AGENT_ICON_CARDS,
    AGENT_ICON_INTRIGUE,
    AGENT_ICON_PLEDGE,
    AGENT_ICON_SOLARI,
    AGENT_ICON_SPICE,
    AGENT_ICON_TRASH_SELF,
    AGENT_ICON_TROOPS,
    AGENT_ICON_WATER,
)
# Icon keys resolved through a card's dedicated choice actions.
AGENT_ICON_INFLUENCE: Final = "influence"  # Dangerous Rhetoric: chosen Faction
AGENT_ICON_RECALL: Final = "recall"  # Steersman: one Agent to recall

# Agent boxes whose printed icons are all queued when the card is played,
# in printed order. Arrow boxes queue their reward icons after the cost.
_BOX = PersonalCardAgentEffect
_PLACEMENT_ICONS: Final[Mapping[PersonalCardAgentEffect, tuple[str, ...]]] = (
    MappingProxyType(
        {
            # Hidden Missive: troop and card draw at two Bene Gesserit Influence.
            _BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: (
                AGENT_ICON_TROOPS,
                AGENT_ICON_CARDS,
            ),
            # Steersman: card draw and an Agent recall.
            _BOX.DRAW_ONE_AND_RECALL_AGENT: (AGENT_ICON_CARDS, AGENT_ICON_RECALL),
            # Maker Keeper: water at two Bene Gesserit, spice at two Fremen.
            _BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO: (
                AGENT_ICON_WATER,
                AGENT_ICON_SPICE,
            ),
            # Wheels Within Wheels: two Solari at two Emperor, spice at two Guild.
            _BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO: (
                AGENT_ICON_SOLARI,
                AGENT_ICON_SPICE,
            ),
            # Dangerous Rhetoric: a chosen Faction's Influence and "Trash this card."
            _BOX.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE: (
                AGENT_ICON_INFLUENCE,
                AGENT_ICON_TRASH_SELF,
            ),
            # Fremen War Name (Bloodlines): troop and card draw once two spice
            # were gained this turn.
            _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: (
                AGENT_ICON_TROOPS,
                AGENT_ICON_CARDS,
            ),
            # Tleilaxu Infiltrator (Immortality): card draw and, at two
            # genetic markers, an Intrigue card.
            _BOX.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS: (
                AGENT_ICON_CARDS,
                AGENT_ICON_INTRIGUE,
            ),
            # Twisted Mentat (Immortality): an optional recall of the Agent
            # sent this turn.
            _BOX.MAY_RECALL_AGENT_SENT_THIS_TURN: (AGENT_ICON_RECALL,),
            # Sardaukar Quartermaster (Immortality): "If grafted: troop, draw
            # a card".
            _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED: (
                AGENT_ICON_TROOPS,
                AGENT_ICON_CARDS,
            ),
        }
    )
)

_LONG_LIVE_SELECTION_STARTED = "long_live_fighters_selection_started"
_LONG_LIVE_DRAW_CARD_ID = "long_live_fighters_draw_card_id"
_LONG_LIVE_DRAW_ACTION_ID = "select_long_live_fighters_draw"
_LONG_LIVE_DISCARD_ACTION_ID = "select_long_live_fighters_discard"


def legal_agent_card_discard_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional hand-discard choices for the current Agent card."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    if pending_agent_icons(context):
        # The arrow cost is paid; only the queued reward icons remain.
        return ()
    if context.get("agent_card_spy_pending") is True:
        # Arrakis Observer's discard is paid; the Spy placement remains.
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    effect = source_card.agent_effect
    if effect not in (
        PersonalCardAgentEffect.MAY_DISCARD_FOR_DEEP_COVER_SPY,
        PersonalCardAgentEffect.MAY_DISCARD_FOR_WATER,
        PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD,
        PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT,
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE,
    ):
        return ()
    may_pay = (
        effect
        is not PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
        or bool(state.intrigue_deck)
    )
    return (
        *(
            (DomainAction(action_id="decline_agent_card_discard", actor=player),)
            if effect
            in (
                PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD,
                PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD,
                PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD,
                PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT,
                PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE,
                PersonalCardAgentEffect.MAY_DISCARD_FOR_DEEP_COVER_SPY,
                PersonalCardAgentEffect.MAY_DISCARD_FOR_WATER,
            )
            else ()
        ),
        *(
            DomainAction(
                action_id="discard_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in state.players[player].hand
            if may_pay
            and not (
                effect
                is (
                    PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD
                )
                and Faction.SPACING_GUILD
                in personal_card_for_instance(card_id).factions
                and not state.intrigue_deck
            )
        ),
    )


def apply_agent_card_discard(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or discard one hand card, then resolve its conditional draw."""

    if action not in legal_agent_card_discard_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card discard choice")
    _, context = current_agent_effect_context(state)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_card_discard"
    if action.action_id == "decline_agent_card_discard":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_discard_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card discard choice has invalid card ID")
    discarded_card = personal_card_for_instance(card_id)
    discarded = discard_personal_card_from_hand(
        state,
        action.actor,
        card_id,
        source=source,
    )
    prepared = advance_after_effect(
        discarded.state,
        context,
        discarded.state.players,
    )
    source_card = personal_card_for_instance(_effect_subject(context)[1])
    if source_card.agent_effect in (
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD,
    ):
        # The cost is paid; the printed reward icons (Intrigue draw, card
        # draw) are independent effects queued for their own actions in the
        # owner's order (OQ-027).
        guild_discard = Faction.SPACING_GUILD in discarded_card.factions
        rewards = (
            (AGENT_ICON_INTRIGUE, AGENT_ICON_CARDS)
            if source_card.agent_effect
            is PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
            else (AGENT_ICON_CARDS, *((AGENT_ICON_INTRIGUE,) if guild_discard else ()))
        )
        arm_agent_icons(context, rewards)
        armed = advance_after_effect(
            discarded.state,
            context,
            discarded.state.players,
        )
        return RuleResult(state=armed, events=discarded.events)
    if source_card.agent_effect is PersonalCardAgentEffect.MAY_DISCARD_FOR_WATER:
        # Engineered Miracle: the discard pays one water.
        owner = discarded.state.players[action.actor]
        watered = replace(
            owner, resources=replace(owner.resources, water=owner.resources.water + 1)
        )
        return RuleResult(
            state=advance_after_effect(
                discarded.state,
                context,
                replace_player(discarded.state.players, watered),
            ),
            events=discarded.events,
        )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_FOR_DEEP_COVER_SPY
    ):
        # Arrakis Observer: two spice for a Spacing Guild discard, then the
        # Spy with Deep Cover placement stays pending for its own choice.
        owner = discarded.state.players[action.actor]
        events = list(discarded.events)
        if Faction.SPACING_GUILD in discarded_card.factions:
            owner = replace(
                owner,
                resources=replace(owner.resources, spice=owner.resources.spice + 2),
            )
            events.append(
                GameEvent(
                    event_id=f"{source}:{card_id}:spice",
                    kind="agent_card_effect_resolved",
                    payload=(("player", action.actor), ("spice", 2)),
                )
            )
        context["pending_agent_effect"] = True
        context["agent_card_spy_pending"] = True
        return RuleResult(
            state=advance_after_effect(
                discarded.state,
                context,
                replace_player(discarded.state.players, owner),
            ),
            events=tuple(events),
        )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT
    ):
        contracts = begin_contract_gain(
            prepared,
            action.actor,
            1,
            source=f"{source}:contract_reward",
        )
        return RuleResult(
            state=contracts.state,
            events=(*discarded.events, *contracts.events),
        )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD
    ):
        draw_count = 2 if Faction.SPACING_GUILD in discarded_card.factions else 0
    elif source_card.agent_effect is PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE:
        # I Believe (Bloodlines): "[discard a card] -> draw a card".
        draw_count = 1
    else:
        draw_count = 2 if Faction.SPACING_GUILD in discarded_card.factions else 1
    if draw_count == 0:
        return RuleResult(state=prepared, events=discarded.events)
    drawn = draw_or_request_personal_cards(
        prepared,
        action.actor,
        draw_count,
        source=f"{source}:{card_id}:draw",
    )
    return RuleResult(
        state=drawn.state,
        events=(*discarded.events, *drawn.events),
    )


def legal_agent_card_long_live_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Long Live the Fighters' two private top-card choices.

    The first choice is exposed only after the Agent effect has explicitly
    started resolving. This preserves the free ordering of the board,
    Faction, and card effect groups while still checking the three-card
    requirement at the point of resolution.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    if source_card.agent_effect is not PersonalCardAgentEffect.LOOK_AT_TOP_THREE:
        return ()
    if context.get(_LONG_LIVE_SELECTION_STARTED) is not True:
        return ()

    top_cards = state.players[player].deck[:3]
    if len(top_cards) < 3:
        raise RuntimeError(
            "Long Live the Fighters selection requires three cards in the deck"
        )
    draw_card_id = context.get(_LONG_LIVE_DRAW_CARD_ID)
    if draw_card_id is None:
        return tuple(
            DomainAction(
                action_id=_LONG_LIVE_DRAW_ACTION_ID,
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in top_cards
        )
    if not isinstance(draw_card_id, str) or draw_card_id not in top_cards:
        raise RuntimeError("Long Live the Fighters frame has an invalid draw card")
    return tuple(
        DomainAction(
            action_id=_LONG_LIVE_DISCARD_ACTION_ID,
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in top_cards
        if card_id != draw_card_id
    )


def apply_agent_card_long_live_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one Long Live the Fighters choice.

    The selected cards remain in the deck after the first action. The second
    action commits draw, discard, and trash together, so no unrelated decision
    can be interleaved with this one card effect.
    """

    if action not in legal_agent_card_long_live_actions(state, action.actor):
        raise ValueError("action is not a legal Long Live the Fighters choice")
    _, context = current_agent_effect_context(state)
    player, source_card_id, _ = _effect_subject(context)
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Long Live the Fighters choice has invalid card ID")

    source = (
        f"round:{state.round_number}:player:{player}:"
        f"agent_card:{source_card_id}:long_live_fighters"
    )
    if action.action_id == _LONG_LIVE_DRAW_ACTION_ID:
        context[_LONG_LIVE_DRAW_CARD_ID] = card_id
        frame = state.decision_stack[-1]
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:selection_started",
                    kind="long_live_fighters_selection_started",
                    payload=(("player", player),),
                ),
            ),
        )

    draw_card_id = context.get(_LONG_LIVE_DRAW_CARD_ID)
    if not isinstance(draw_card_id, str):
        raise RuntimeError("Long Live the Fighters frame is missing its draw card")
    top_cards = state.players[player].deck[:3]
    if len(top_cards) < 3 or draw_card_id not in top_cards or card_id not in top_cards:
        raise RuntimeError("Long Live the Fighters frame has invalid top cards")
    if card_id == draw_card_id:
        raise RuntimeError("Long Live the Fighters cannot draw and discard one card")
    trash_card_id = next(
        candidate
        for candidate in top_cards
        if candidate not in (draw_card_id, card_id)
    )

    # Stage the printed draw and discard moves first. The remaining card stays
    # in the deck for the shared trash transition, so a future trash trigger
    # observes the same zones as the completed printed order.
    owner = state.players[player]
    staged_owner = replace(
        owner,
        deck=tuple(
            candidate
            for candidate in owner.deck
            if candidate not in (draw_card_id, card_id)
        ),
        hand=(*owner.hand, draw_card_id),
        discard_pile=(*owner.discard_pile, card_id),
    )
    staged_state = replace(
        state,
        players=replace_player(state.players, staged_owner),
    )
    trashed = trash_personal_card(
        staged_state,
        player,
        trash_card_id,
        source=source,
        allow_deck=True,
    )
    next_owner = trashed.state.players[player]
    context["pending_agent_effect"] = False
    context.pop(_LONG_LIVE_SELECTION_STARTED, None)
    context.pop(_LONG_LIVE_DRAW_CARD_ID, None)
    next_state = advance_after_effect(
        trashed.state,
        context,
        replace_player(trashed.state.players, next_owner),
    )
    discard_event = GameEvent(
        event_id=f"{source}:discard:{card_id}",
        kind="card_discarded",
        payload=(("card_id", card_id), ("player", player)),
    )
    resolved_event = GameEvent(
        event_id=f"{source}:resolved",
        kind="agent_card_effect_resolved",
        payload=(("card_id", source_card_id), ("player", player)),
    )
    return RuleResult(
        state=next_state,
        events=(discard_event, *trashed.events, resolved_event),
    )


def legal_opponent_card_discard_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return hand cards the current Covert Operation target may discard."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "covert_operation_card_id" not in context
        or "covert_operation_owner" not in context
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="discard_opponent_card",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in state.players[player].hand
    )


def apply_opponent_card_discard(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Discard one target-owned card and expose the next opponent decision."""

    if action not in legal_opponent_card_discard_actions(state, action.actor):
        raise ValueError("action is not a legal opponent-card discard")
    context = dict(state.decision_stack[-1].context)
    source_card_id = context["covert_operation_card_id"]
    source_owner = context["covert_operation_owner"]
    card_id = dict(action.arguments).get("card_id")
    if (
        not isinstance(source_card_id, str)
        or isinstance(source_owner, bool)
        or not isinstance(source_owner, int)
        or not isinstance(card_id, str)
    ):
        raise RuntimeError("Covert Operation frame has invalid context")
    discarded = discard_personal_card_from_hand(
        state,
        action.actor,
        card_id,
        source=(
            f"round:{state.round_number}:player:{source_owner}:"
            f"agent_card:{source_card_id}:opponent:{action.actor}"
        ),
    )
    popped = replace(
        discarded.state,
        decision_stack=discarded.state.decision_stack[:-1],
    )
    base_frame = popped.decision_stack[-1] if popped.decision_stack else None
    if base_frame is not None and base_frame.kind == FrameKind.AGENT_EFFECTS:
        # The last opponent finished. Return to the owner's effect frame, or
        # open the next turn when no group in that frame is still pending.
        popped = advance_after_effect(popped, dict(base_frame.context))
    return RuleResult(state=popped, events=discarded.events)


def _partner_icon_count(state: GameState, context: Mapping[str, ActionValue]) -> int:
    """Slig Farmer: the Agent icons the other grafted card has right now.

    Borrowed and conditional icons count too — Blank Slate's grafted Faction
    icons, Servo-Receivers' Signet icons, a met Long Reach condition — since
    the card carries them (OQ-055, user ruling 2026-09-08).
    """

    partner = other_grafted_card_id(context)
    if not partner:
        return 0
    player = context.get("turn_owner")
    if isinstance(player, bool) or not isinstance(player, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    owner = state.players[player]
    opponents = tuple(seat for seat in state.players if seat.player_id != player)
    partner_card = personal_card_for_instance(partner)
    return len(
        effective_agent_icons(partner_card, owner, grafted=True, opponents=opponents)
    )


def _chosen_rewards(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    value = context.get("rewards_chosen", "")
    return tuple(str(value).split(",")) if value else ()


def _apply_stitched_horror_reward(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
    source: str,
) -> RuleResult:
    """Record one of Stitched Horror's picks; both pay out after the second.

    "Choose two" names both rewards before either resolves (designer ruling,
    OQ-057), so the second pick cannot depend on what the first produced.
    """

    player = action.actor
    reward = str(dict(action.arguments)["reward"])
    chosen = (*_chosen_rewards(context), reward)
    context["rewards_chosen"] = ",".join(chosen)
    context["pending_agent_effect"] = len(chosen) < 2
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:reward:{reward}",
            kind="agent_card_reward_chosen",
            payload=(("player", player), ("reward", reward)),
        )
    ]
    frame = state.decision_stack[-1]
    if context["pending_agent_effect"] is True:
        # The first pick: the box stays open for the second.
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
    players = state.players
    for pick in chosen:
        owner = players[player]
        if pick == "water":
            players = replace_player(
                players,
                replace(
                    owner,
                    resources=replace(owner.resources, water=owner.resources.water + 1),
                ),
            )
        elif pick == "troop":
            recruited_owner, recruited = recruit_troops(owner, 1)
            context["troops_recruited"] = (
                context_int(
                    context, "troops_recruited", owner="Agent-turn effect frame"
                )
                + recruited
            )
            players = replace_player(players, recruited_owner)
            events.extend(recruit_shortfall_events(source, player, 1, recruited))
    next_state = advance_after_effect(state, context, players)
    for index, pick in enumerate(chosen):
        if pick == "tleilaxu":
            advanced = advance_tleilaxu(
                next_state, player, 1, source=f"{source}:tleilaxu"
            )
            next_state = advanced.state
            events.extend(advanced.events)
        elif pick == "trash":
            next_state = next_state.push_decision(
                optional_trash_frame(player, f"{source}:{index + 1}")
            )
    return RuleResult(state=next_state, events=tuple(events))


def legal_agent_card_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Faction choices for the current Agent-card effect."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    effect = source_card.agent_effect
    if effect is PersonalCardAgentEffect.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND:
        # Southern Faith: the draw is always there; the Influence needs
        # another Bene Gesserit card in play, judged now (OQ-028).
        owner = state.players[player]
        if not has_faction_bond(owner.in_play, source_card_id, Faction.BENE_GESSERIT):
            return ()
        return (
            DomainAction(action_id="resolve_agent_card_effect", actor=player),
            DomainAction(
                action_id="choose_agent_card_influence",
                actor=player,
                arguments=(("faction", Faction.BENE_GESSERIT.value),),
            ),
        )
    if (
        effect
        is PersonalCardAgentEffect.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND
    ):
        # Possible Futures: without the Bond it is a choice between the
        # Influence and the two troops; with it the Influence choice pays
        # both.
        owner = state.players[player]
        bond = has_faction_bond(owner.in_play, source_card_id, Faction.BENE_GESSERIT)
        return (
            *(
                ()
                if bond
                else (
                    DomainAction(action_id="resolve_agent_card_effect", actor=player),
                )
            ),
            *(
                DomainAction(
                    action_id="choose_agent_card_influence",
                    actor=player,
                    arguments=(("faction", faction.value),),
                )
                for faction in Faction
            ),
        )
    if effect is PersonalCardAgentEffect.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE:
        # Long Reach: "Choose two" of the four Factions, one pick at a time.
        chosen_value = context.get("influence_chosen", "")
        chosen = str(chosen_value).split(",") if chosen_value else []
        return tuple(
            DomainAction(
                action_id="choose_agent_card_influence",
                actor=player,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
            if faction.value not in chosen
        )
    if (
        effect
        is _SPICE_AND_GRAFTED_INFLUENCE
    ):
        # Interstellar Conspiracy: the Influence needs an Emperor or Guild
        # partner; otherwise the plain resolution pays the spice alone.
        if not _grafted_with_factions(
            context, (Faction.EMPEROR, Faction.SPACING_GUILD)
        ):
            return ()
        return tuple(
            DomainAction(
                action_id="choose_agent_card_influence",
                actor=player,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    if effect not in (
        PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE,
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN,
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE,
    ):
        return ()
    if (
        effect
        is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN
        and context.get("spy_recalled_this_turn") is not True
    ):
        return ()
    if (
        effect is PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE
        and AGENT_ICON_INFLUENCE not in pending_agent_icons(context)
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="choose_agent_card_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )


def _grafted_with_factions(
    context: Mapping[str, ActionValue],
    factions: tuple[Faction, ...],
) -> bool:
    """Return whether the other grafted card carries one of ``factions``."""

    partner = other_grafted_card_id(context)
    if not partner:
        return False
    return any(
        faction in personal_card_for_instance(partner).factions
        for faction in factions
    )


def apply_agent_card_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve the current Agent card's selected Faction Influence."""

    if action not in legal_agent_card_influence_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Influence choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Agent-card Influence choice has invalid Faction")
    faction = Faction(faction_value)
    source_card = active_agent_card(context)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE
    ):
        # Long Reach: "Choose two" names both Factions before either
        # Influence moves (designer ruling, OQ-057); the box stays pending
        # until the second, different Faction is chosen.
        chosen_value = context.get("influence_chosen", "")
        chosen = [
            *(str(chosen_value).split(",") if chosen_value else []),
            faction.value,
        ]
        context["influence_chosen"] = ",".join(chosen)
        context["pending_agent_effect"] = len(chosen) < 2
        if len(chosen) < 2:
            gained = RuleResult(
                state=state,
                events=(
                    GameEvent(
                        event_id=f"{source}:influence:{faction.value}:chosen",
                        kind="agent_card_influence_chosen",
                        payload=(("faction", faction.value), ("player", action.actor)),
                    ),
                ),
            )
        else:
            working = state
            picked_events: list[GameEvent] = []
            for pick in chosen:
                step = gain_faction_influence(
                    working,
                    action.actor,
                    Faction(pick),
                    1,
                    event_prefix=f"{source}:influence:{pick}",
                )
                working = step.state
                picked_events.extend(step.events)
            gained = RuleResult(state=working, events=tuple(picked_events))
    else:
        gained = gain_faction_influence(
            state,
            action.actor,
            faction,
            1,
            event_prefix=f"{source}:influence:{faction.value}",
        )
        if (
            source_card.agent_effect
            is PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE
        ):
            # "Trash this card." is the box's other printed icon, resolved by
            # its own action in the owner's order (OQ-027).
            finish_agent_icon(context, AGENT_ICON_INFLUENCE)
        else:
            context["pending_agent_effect"] = False
    events: tuple[GameEvent, ...] = gained.events
    players = gained.state.players
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND
    ):
        # With the Bond the Influence choice also pays the two troops.
        owner = players[action.actor]
        if has_faction_bond(owner.in_play, source_card_id, Faction.BENE_GESSERIT):
            recruited_owner, recruited = recruit_troops(owner, 2)
            previous = context_int(
                context, "troops_recruited", owner="Agent-turn effect frame"
            )
            context["troops_recruited"] = previous + recruited
            players = replace_player(players, recruited_owner)
            events = (
                *events,
                *recruit_shortfall_events(
                    f"{source}:troops", action.actor, 2, recruited
                ),
            )
    if (
        source_card.agent_effect
        is _SPICE_AND_GRAFTED_INFLUENCE
    ):
        # Interstellar Conspiracy: the spice comes with the Influence.
        spiced = players[action.actor]
        players = replace_player(
            players,
            replace(
                spiced,
                resources=replace(spiced.resources, spice=spiced.resources.spice + 1),
            ),
        )
    next_state = advance_after_effect(
        replace(gained.state, players=players),
        context,
        players,
    )
    return RuleResult(state=next_state, events=events)


def legal_agent_card_contract_completion_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """CHOAM Demands: "Complete one of your contracts" (any active one)."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    if source_card.agent_effect is not PersonalCardAgentEffect.COMPLETE_ONE_CONTRACT:
        return ()
    return tuple(
        DomainAction(
            action_id="complete_contract_by_card",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in state.players[player].active_contract_ids
    )


def apply_agent_card_contract_completion(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Complete the chosen Contract regardless of its printed condition."""

    if action not in legal_agent_card_contract_completion_actions(
        state, action.actor
    ):
        raise ValueError("action is not a legal Agent-card Contract completion")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    instance_id = str(dict(action.arguments)["instance_id"])
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}:contract:{instance_id}"
    )
    garrison_before = state.players[action.actor].troops_garrison
    completed = complete_contract_by_effect(
        state, action.actor, instance_id, source=source
    )
    recruited = completed.state.players[action.actor].troops_garrison - garrison_before
    if recruited:
        previous = context_int(
            context, "troops_recruited", owner="Agent-turn effect frame"
        )
        context["troops_recruited"] = previous + recruited
    context["pending_agent_effect"] = False
    # The reward's own choices (a Spy placement, a recall) were pushed by
    # the completion above this frame; keep them on top of the advanced turn.
    depth = len(state.decision_stack)
    follow_up = completed.state.decision_stack[depth:]
    base = replace(
        completed.state, decision_stack=completed.state.decision_stack[:depth]
    )
    advanced = advance_after_effect(base, context, base.players)
    next_state = replace(
        advanced, decision_stack=(*advanced.decision_stack, *follow_up)
    )
    return RuleResult(state=next_state, events=completed.events)


def legal_agent_card_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return placement or recall choices for an Agent-box Spy icon."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    deep_cover = (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_FOR_DEEP_COVER_SPY
        and context.get("agent_card_spy_pending") is True
    )
    if not deep_cover and source_card.agent_effect not in (
        PersonalCardAgentEffect.PLACE_SPY,
        PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE,
    ):
        return ()

    owner = state.players[player]
    allowed_post_ids = (
        observation_post_ids_for_factions(source_card.agent_spy_factions)
        if source_card.agent_spy_factions
        else None
    )
    placements = empty_observation_post_ids(state, allowed_post_ids)
    if deep_cover:
        # Spy with Deep Cover: opponents' Spies may be ignored, never one's
        # own [Bloodlines pp. 5, 12].
        placements = tuple(
            post.post_id
            for post in OBSERVATION_POSTS
            if post.post_id not in owner.spy_post_ids
        )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE
        and _owner_is_spying_on_visited_space(state, player, context)
    ):
        opponent_posts = {
            post_id
            for candidate in state.players
            if candidate.player_id != player
            for post_id in candidate.spy_post_ids
        }
        placements = tuple(
            post.post_id
            for post in OBSERVATION_POSTS
            if post.post_id not in owner.spy_post_ids
            and (
                post.post_id in opponent_posts
                or post.post_id in placements
            )
        )
    # Placement needs a Spy in supply right now [Main pp. 11, 20]; a recall
    # made earlier this turn may already have been consumed by another effect
    # (e.g. the Espionage board space), in which case another recall is offered.
    if owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_agent_card_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in placements
        )
    recall_post_ids = owner.spy_post_ids
    if not placements and allowed_post_ids is not None:
        recall_post_ids = tuple(
            post_id for post_id in owner.spy_post_ids if post_id in allowed_post_ids
        )
    return tuple(
        DomainAction(
            action_id="recall_spy_for_agent_card",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in recall_post_ids
    )


def apply_agent_card_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve a card's place-Spy effect, recalling first when necessary."""

    if action not in legal_agent_card_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Spy choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    post_id = dict(action.arguments).get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("Agent-card Spy choice has invalid post ID")
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:agent_card:{source_card_id}"
    )

    if action.action_id == "recall_spy_for_agent_card":
        next_owner = recall_spy(owner, post_id)
        context["agent_card_spy_recalled"] = True
        next_state = advance_after_effect(
            state,
            context,
            replace_player(state.players, next_owner),
        )
        event = GameEvent(
            event_id=f"{source}:spy_recalled:{post_id}",
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", source_card_id),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = place_spy(owner, post_id)
    context["pending_agent_effect"] = False
    context.pop("agent_card_spy_pending", None)
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
    )
    event = GameEvent(
        event_id=f"{source}:spy_placed:{post_id}",
        kind="spy_placed",
        payload=(
            ("card_id", source_card_id),
            ("player", action.actor),
            ("post_id", post_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_agent_card_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Agent locations that Steersman may recall."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    if AGENT_ICON_RECALL not in pending_agent_icons(context):
        return ()
    _, source_card_id, turn_space_id = _effect_subject(context)
    if (
        active_agent_card(context).agent_effect
        is PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN
    ):
        # Twisted Mentat: "You may recall the Agent you sent this turn."
        locations = tuple(
            space_id
            for space_id in state.players[player].agent_locations
            if space_id == turn_space_id
        )
        return (
            DomainAction(action_id="decline_agent_card_recall", actor=player),
            *(
                DomainAction(
                    action_id="recall_agent_for_agent_card",
                    actor=player,
                    arguments=(("space_id", space_id),),
                )
                for space_id in locations
            ),
        )
    return tuple(
        DomainAction(
            action_id="recall_agent_for_agent_card",
            actor=player,
            arguments=(("space_id", space_id),),
        )
        for space_id in state.players[player].agent_locations
    )


def apply_agent_card_recall(state: GameState, action: DomainAction) -> RuleResult:
    """Recall one Agent for Steersman's recall icon."""

    if action not in legal_agent_card_recall_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card recall choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    if action.action_id == "decline_agent_card_recall":
        finish_agent_icon(context, AGENT_ICON_RECALL)
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:player:{action.actor}:"
                        f"agent_card:{source_card_id}:recall_declined"
                    ),
                    kind="agent_card_effect_declined",
                    payload=(("card_id", source_card_id), ("player", action.actor)),
                ),
            ),
        )
    space_id = dict(action.arguments).get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Agent-card recall choice has invalid space ID")
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        agents_available=owner.agents_available + 1,
        agent_locations=tuple(
            location for location in owner.agent_locations if location != space_id
        ),
    )
    # The printed card draw is the box's other icon, resolved by its own
    # action in the owner's order (OQ-027).
    finish_agent_icon(context, AGENT_ICON_RECALL)
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
    )
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:agent_recalled:{space_id}",
                kind="agent_recalled",
                payload=(
                    ("card_id", source_card_id),
                    ("player", action.actor),
                    ("space_id", space_id),
                ),
            ),
        ),
    )


def legal_agent_card_opponent_retreat_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Disruption Tactics' targets: one enemy unit to retreat.

    "Force an enemy troop to retreat" (card face); a Sardaukar Commander is
    a troop [Bloodlines p. 4]. OQ-034 project convention: the acting player
    picks the opponent and, where both kinds are in the Conflict, which
    kind retreats. With no enemy unit in the Conflict the box resolves
    without effect through ``resolve_agent_card_effect``.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True or pending_agent_icons(context):
        return ()
    _, source_card_id, _ = _effect_subject(context)
    if (
        active_agent_card(context).agent_effect
        is not PersonalCardAgentEffect.FORCE_OPPONENT_TROOP_RETREAT
    ):
        return ()
    actions: list[DomainAction] = []
    for seat in state.players:
        if seat.player_id == player:
            continue
        if seat.troops_conflict > 0:
            actions.append(
                DomainAction(
                    action_id="retreat_opponent_troop",
                    actor=player,
                    arguments=(("player", seat.player_id),),
                )
            )
        if seat.commanders_conflict > 0:
            actions.append(
                DomainAction(
                    action_id="retreat_opponent_troop",
                    actor=player,
                    arguments=(("commanders", 1), ("player", seat.player_id)),
                )
            )
    return tuple(actions)


def apply_agent_card_opponent_retreat(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Retreat one unit of the chosen opponent to their garrison."""

    if action not in legal_agent_card_opponent_retreat_actions(state, action.actor):
        raise ValueError("action is not a legal enemy retreat choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    arguments = dict(action.arguments)
    target = arguments["player"]
    commanders = arguments.get("commanders", 0)
    if isinstance(target, bool) or not isinstance(target, int):
        raise RuntimeError("enemy retreat has an invalid target")
    if isinstance(commanders, bool) or not isinstance(commanders, int):
        raise RuntimeError("enemy retreat has an invalid unit kind")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}:opponent:{target}"
    )
    retreated = retreat_units(
        state, target, source, troops=1 - commanders, commanders=commanders
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        retreated.state, context, retreated.state.players
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:agent_card:{source_card_id}",
        kind="agent_card_effect_resolved",
        payload=(("card_id", source_card_id), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event, *retreated.events))


def legal_agent_card_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional personal-card trash choices for the current Agent card."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    if pending_agent_icons(context):
        # The arrow cost is paid; only the queued reward icons remain.
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    if source_card.agent_effect not in (
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE,
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND,
        PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE,
        PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE,
        PersonalCardAgentEffect.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE,
        PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON,
        PersonalCardAgentEffect.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS,
        PersonalCardAgentEffect.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT,
    ):
        return ()
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON
        and _trashes_remaining(context) == 0
    ):
        # The Beast's Spoils resolves its automatic rewards first; only the
        # Crysknife trashes it counted are then offered one at a time.
        return ()
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT
        and state.players[player].commanders_conflict < 1
    ):
        # Ruthless Leadership: "If you have one or more Sardaukar Commanders
        # in the Conflict" is judged when the box resolves (OQ-028); without
        # one, neither trash icon is offered and the box resolves without
        # effect.
        return ()

    owner = state.players[player]
    eligible = (*owner.hand, *owner.discard_pile, *owner.in_play)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS
    ):
        # Elite Forces: "a card from your hand".
        eligible = owner.hand
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE
    ):
        # "Trash this card" is the arrow cost (OQ-022: a card already trashed
        # by another effect expired before this choice was offered).
        eligible = (source_card_id,) if source_card_id in owner.in_play else ()
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
    ):
        # "Gain 1 additional Influence with the Faction you visited": an
        # Agent infiltrated onto a space without a Faction [Main p. 11]
        # has no Influence to gain, so the arrow cost is not offered
        # (OQ-046).
        space_id = context.get("space_id")
        visited_faction = (
            BOARD_SPACES_BY_ID[space_id].faction if isinstance(space_id, str) else None
        )
        eligible = (
            tuple(
                card_id
                for card_id in owner.hand
                if card_id != source_card_id
                and Faction.EMPEROR in personal_card_for_instance(card_id).factions
            )
            if visited_faction is not None
            else ()
        )
    if (
        source_card.agent_effect
        is (
            PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
        )
    ):
        eligible = tuple(
            card_id
            for card_id in eligible
            if len(state.intrigue_deck)
            >= 1
            + int(
                getattr(personal_card_for_instance(card_id), "trash_effect", None)
                is PersonalCardTrashEffect.DRAW_INTRIGUE_CARD
            )
        )
        if Faction.BENE_GESSERIT.value not in owner.alliance_faction_ids:
            # The Alliance is judged when the payment resolves [Main pp. 9,
            # 20]; a Faction step of this turn may still grant it, so only
            # declining is offered until then (OQ-028).
            eligible = ()
    return (
        DomainAction(action_id="decline_agent_card_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in eligible
        ),
    )


def apply_agent_card_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve or decline an Agent-box personal-card trash choice."""

    if action not in legal_agent_card_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card trash choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_card"
    if action.action_id == "decline_agent_card_trash":
        context.pop("trashes_remaining", None)
        next_state = advance_after_effect(state, context)
        event = GameEvent(
            event_id=f"{source}:trash_declined",
            kind="agent_card_trash_declined",
            payload=(("player", action.actor),),
        )
        if source_card.agent_effect is _TRASH_TO_DRAW_IF_BOND:
            # Tread in Darkness prints two icons, not an arrow: the trash is
            # optional [Main p. 20] and the draw still happens (user ruling
            # 2026-09-09, OQ-058).
            drawn = draw_or_request_personal_cards(
                next_state, action.actor, 1, source=f"{source}:trash_draw"
            )
            return RuleResult(state=drawn.state, events=(event, *drawn.events))
        return RuleResult(state=next_state, events=(event,))

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card trash choice has invalid card ID")
    trashed = trash_personal_card(
        state,
        action.actor,
        card_id,
        source=source,
    )
    if source_card.agent_effect in (
        PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON,
        PersonalCardAgentEffect.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT,
    ):
        remaining = (
            _trashes_remaining(context, default=_pending_trash_icons(source_card)) - 1
        )
        if remaining > 0:
            # More trash icons: keep the box pending for the next trash.
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
        next_state = advance_after_effect(
            trashed.state,
            context,
            trashed.state.players,
        )
        return RuleResult(state=next_state, events=trashed.events)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS
    ):
        # Elite Forces: an Emperor card trashed from hand pays an Intrigue
        # draw and a troop (queued icons, OQ-027) and the Combat icon: this
        # turn deploys as though at a Combat space, never more than two
        # units from the garrison [Bloodlines p. 5].
        if Faction.EMPEROR in personal_card_for_instance(card_id).factions:
            arm_agent_icons(context, (AGENT_ICON_INTRIGUE, AGENT_ICON_TROOPS))
            if context.get("units_deploy_blocked") is not True:
                context["pending_combat_deployment"] = True
                limit = context_int(
                    context,
                    "existing_troop_deployment_limit",
                    owner="Agent-turn effect frame",
                )
                context["existing_troop_deployment_limit"] = max(limit, 2)
        next_state = advance_after_effect(
            trashed.state, context, trashed.state.players
        )
        return RuleResult(state=next_state, events=trashed.events)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE
    ):
        # Pivotal Gambit: the trashed card is the arrow cost; its troop and
        # the "gain 1 Influence of your choice" pledge for this Conflict's
        # first-place reward (OQ-025) are independent reward icons queued
        # for their own actions (OQ-027). The card trashed itself as its
        # own cost, so its rewards still pay out (OQ-022).
        context["agent_card_self_trashed"] = True
        arm_agent_icons(context, (AGENT_ICON_TROOPS, AGENT_ICON_PLEDGE))
        next_state = advance_after_effect(
            trashed.state, context, trashed.state.players
        )
        return RuleResult(state=next_state, events=trashed.events)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
    ):
        # A card trashed by a freely ordered effect expires before this
        # choice is offered (OQ-022), so the source is still in play here
        # and trashes itself as part of its own effect.
        source_trashed = trash_personal_card(
            trashed.state,
            action.actor,
            source_card_id,
            source=source,
        )
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("Treacherous Maneuver requires a Faction space")
        gained = gain_faction_influence(
            source_trashed.state,
            action.actor,
            faction,
            1,
            event_prefix=f"{source}:extra_influence:{faction.value}",
        )
        next_state = advance_after_effect(
            gained.state,
            context,
            gained.state.players,
        )
        return RuleResult(
            state=next_state,
            events=(*trashed.events, *source_trashed.events, *gained.events),
        )
    if (
        source_card.agent_effect
        is (
            PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
        )
    ):
        if not trashed.state.intrigue_deck:
            raise RuntimeError("Branching Path trash has no Intrigue reward")
        # The trash is the arrow cost; the Intrigue draw and the two troops
        # are independent reward icons queued for their own actions
        # (OQ-027). Trashing Branching Path itself as that cost keeps its
        # rewards (OQ-022: a card's own effect still pays out).
        if card_id == source_card_id:
            context["agent_card_self_trashed"] = True
        arm_agent_icons(context, (AGENT_ICON_INTRIGUE, AGENT_ICON_TROOPS))
        next_state = advance_after_effect(
            trashed.state, context, trashed.state.players
        )
        return RuleResult(state=next_state, events=trashed.events)
    next_state = advance_after_effect(
        trashed.state,
        context,
        trashed.state.players,
    )
    if (
        source_card.agent_effect
        in (
            PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE,
            PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND,
        )
    ):
        drawn = draw_or_request_personal_cards(
            next_state,
            action.actor,
            1,
            source=f"{source}:trash_draw",
        )
        return RuleResult(
            state=drawn.state,
            events=(*trashed.events, *drawn.events),
        )
    return RuleResult(state=next_state, events=trashed.events)


def legal_agent_card_intrigue_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional Intrigue-and-Spice payment choices for an Agent card."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    effect = active_agent_card(context).agent_effect
    if (
        effect
        is not (
            PersonalCardAgentEffect.MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
        )
    ):
        return ()
    owner = state.players[player]
    if (
        Faction.SPACING_GUILD.value not in owner.alliance_faction_ids
        or owner.resources.spice < 2
        or not owner.intrigue_cards
    ):
        # The Alliance condition and the full arrow cost are judged again when
        # the player resolves the pending payment in their chosen effect order
        # [Main pp. 9, 20]; once they no longer hold, only skipping remains.
        return (
            DomainAction(
                action_id="decline_agent_card_intrigue_payment", actor=player
            ),
        )
    return (
        DomainAction(action_id="decline_agent_card_intrigue_payment", actor=player),
        *(
            DomainAction(
                action_id="pay_agent_card_intrigue_and_spice",
                actor=player,
                arguments=(("intrigue_card_id", card_id),),
            )
            for card_id in owner.intrigue_cards
        ),
    )


def apply_agent_card_intrigue_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or trash one Intrigue and pay two Spice for one VP."""

    if action not in legal_agent_card_intrigue_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Intrigue payment")
    _, context = current_agent_effect_context(state)
    # Paying or skipping spends the card's one arrow choice for this turn
    # [Main p. 9] [FAQ p. 3], so the pending effect is discharged either way.
    context["pending_agent_effect"] = False
    _, source_card_id, _ = _effect_subject(context)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}:intrigue_payment"
    )
    if action.action_id == "decline_agent_card_intrigue_payment":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_payment_declined",
                    payload=(("card_id", source_card_id), ("player", action.actor)),
                ),
            ),
        )

    intrigue_card_id = dict(action.arguments).get("intrigue_card_id")
    if not isinstance(intrigue_card_id, str):
        raise RuntimeError("Agent-card Intrigue payment has invalid card ID")
    owner = state.players[action.actor]
    previous_spent = context.get("spice_spent_after_placement", 0)
    if isinstance(previous_spent, bool) or not isinstance(previous_spent, int):
        raise RuntimeError("Agent-turn effect frame has invalid Spice spending")
    context["spice_spent_after_placement"] = previous_spent + 2
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            spice=owner.resources.spice - 2,
        ),
        spice_spent_turn=owner.spice_spent_turn + 2,
        victory_points=owner.victory_points + 1,
        intrigue_cards=tuple(
            card_id
            for card_id in owner.intrigue_cards
            if card_id != intrigue_card_id
        ),
    )
    next_state = advance_after_effect(
        replace(
            state,
            intrigue_trash=(*state.intrigue_trash, intrigue_card_id),
        ),
        context,
        replace_player(state.players, next_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:intrigue_trashed:{intrigue_card_id}",
                kind="intrigue_card_trashed",
                payload=(
                    ("card_id", intrigue_card_id),
                    ("player", action.actor),
                ),
            ),
            GameEvent(
                event_id=f"{source}:paid",
                kind="agent_card_payment_resolved",
                payload=(
                    ("card_id", source_card_id),
                    ("player", action.actor),
                    ("resource", "spice"),
                    ("spent", 2),
                ),
            ),
        ),
    )


def legal_agent_card_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional resource payments for the current Agent card."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect
        .MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS
    ):
        return _arrakis_revolt_payment_actions(state, player)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI
    ):
        # Organ Merchants: "specimen -> 4 Solari" [card face].
        decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
        if state.players[player].specimens < 1:
            return (decline,)
        return (
            decline,
            DomainAction(action_id="pay_agent_card_specimen", actor=player),
        )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU
    ):
        # Tleilaxu Surgeon: "2 specimens -> Tleilaxu Tleilaxu" [card face].
        decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
        if state.players[player].specimens < 2:
            return (decline,)
        return (
            decline,
            DomainAction(action_id="pay_agent_card_two_specimens", actor=player),
        )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN
    ):
        # Dissecting Kit: "Trash the other grafted card -> a specimen"
        # [card face]; without a partner still in play the box does nothing.
        partner = other_grafted_card_id(context)
        if not partner or partner not in state.players[player].in_play:
            return ()
        return (
            DomainAction(action_id="decline_agent_card_payment", actor=player),
            DomainAction(action_id="trash_grafted_card_for_specimen", actor=player),
        )
    if (
        source_card.agent_effect
        is _DRAW_ONE_OR_COMBAT_ICON
    ):
        # High Priority Travel: "[Guild] 2 Influence: draw a card —OR—
        # Combat" [card face]; the draw is the box's plain resolution.
        if state.players[player].influence.spacing_guild < 2:
            return ()
        return (
            DomainAction(action_id="resolve_agent_card_effect", actor=player),
            DomainAction(action_id="take_agent_card_combat_icon", actor=player),
        )
    owner = state.players[player]
    if source_card.agent_effect is _RESEARCH_AND_TRASH_FOR_VP:
        # Scientific Breakthrough: at two genetic markers the research may
        # come with "trash this card -> 1 Victory Point" [card face].
        if genetic_markers_reached(owner.research_space) < 2:
            return ()
        return (
            DomainAction(action_id="resolve_agent_card_effect", actor=player),
            DomainAction(action_id="trash_agent_card_self_for_vp", actor=player),
        )
    if source_card.agent_effect is _SOLARI_PER_PARTNER_ICON:
        # Slig Farmer: the Solari land first, so they may pay the five.
        if (
            owner.resources.solari + _partner_icon_count(state, context)
            < SLIG_FARMER_PRICE
        ):
            return ()
        return (
            DomainAction(action_id="resolve_agent_card_effect", actor=player),
            DomainAction(
                action_id="pay_agent_card_five_solari_for_tleilaxu", actor=player
            ),
        )
    if source_card.agent_effect is _TRASH_GRAFTED_FOR_INFLUENCE:
        # Beguiling Pheromones: a Faction space visited this turn and a
        # grafted card (either one) still in play [card face] [FAQ p. 1].
        _, _, space_id = _effect_subject(context)
        if BOARD_SPACES_BY_ID[space_id].faction is None or not is_grafted(context):
            return ()
        return (
            DomainAction(action_id="decline_agent_card_payment", actor=player),
            *(
                DomainAction(
                    action_id="trash_grafted_card_for_influence",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in (source_card_id, other_grafted_card_id(context))
                if card_id in owner.in_play
            ),
        )
    if source_card.agent_effect is _LOSE_TROOP_FOR_CARDS:
        # Piter, Genius Advisor: "Lose a troop -> draw two cards and
        # Research"; the owner picks the zone like an Intrigue loss (OQ-038).
        return (
            DomainAction(action_id="decline_agent_card_payment", actor=player),
            *(
                DomainAction(
                    action_id="lose_agent_card_troop",
                    actor=player,
                    arguments=(("zone", zone),),
                )
                for zone in ("garrison", "conflict")
                if getattr(owner, f"troops_{zone}") >= 1
            ),
        )
    if source_card.agent_effect is _CHOOSE_TWO_REWARDS:
        # Stitched Horror: "Choose two" of the four rewards, one at a time.
        chosen = _chosen_rewards(context)
        return tuple(
            DomainAction(
                action_id="choose_agent_card_reward",
                actor=player,
                arguments=(("reward", reward),),
            )
            for reward in STITCHED_HORROR_REWARDS
            if reward not in chosen
        )
    if source_card.agent_effect not in (
        PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO,
        PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP,
    ):
        return ()
    owner = state.players[player]
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
        and owner.resources.water < 2
    ) or (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP
        and owner.resources.spice < 4
    ):
        # The arrow cost is judged again when the player resolves the pending
        # payment in their chosen effect order [Main pp. 9, 20]; once it is
        # unaffordable, only skipping remains.
        return (DomainAction(action_id="decline_agent_card_payment", actor=player),)
    return (
        DomainAction(action_id="decline_agent_card_payment", actor=player),
        DomainAction(
            action_id=(
                "pay_agent_card_water"
                if source_card.agent_effect
                is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
                else "pay_agent_card_spice"
            ),
            actor=player,
        ),
    )


def legal_corrinth_city_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Corrinth City's optional, atomic two-card payment choices."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    if (
        source_card.agent_effect
        is not PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP
    ):
        return ()
    owner = state.players[player]
    if owner.resources.solari < 5 or len(owner.hand) < 2:
        # The full cost must still be payable when the player resolves the
        # pending payment in their chosen effect order [Main pp. 9, 20]; once
        # it is unaffordable, only skipping remains.
        return (
            DomainAction(action_id="decline_corrinth_city_payment", actor=player),
        )
    first_card_id = context.get("corrinth_first_card_id")
    if first_card_id is not None and not isinstance(first_card_id, str):
        raise RuntimeError("pending Corrinth City payment has invalid first card")
    if first_card_id is not None and first_card_id not in owner.hand:
        # A freely ordered effect (for example an Intrigue discard cost) can
        # consume the stored first selection before the payment completes;
        # the atomic cost then restarts from no selection [Main pp. 9, 20].
        first_card_id = None
    return (
        DomainAction(action_id="decline_corrinth_city_payment", actor=player),
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


def apply_corrinth_city_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or pay Corrinth City's complete cost before resolving discards."""

    if action not in legal_corrinth_city_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Corrinth City payment choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    if action.action_id == "decline_corrinth_city_payment":
        context["pending_agent_effect"] = False
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="corrinth_city_payment_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Corrinth City payment has invalid card ID")
    if action.action_id == "select_corrinth_city_discard":
        context["corrinth_first_card_id"] = card_id
        frame = state.decision_stack[-1]
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:first_discard_selected",
                    kind="corrinth_city_payment_started",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    first_card_id = context.get("corrinth_first_card_id")
    if not isinstance(first_card_id, str):
        raise RuntimeError("Corrinth City payment is missing its first card")
    context["pending_agent_effect"] = False
    owner = state.players[action.actor]
    if owner.resources.solari < 5:
        raise RuntimeError("Corrinth City payment requires five Solari")
    paid_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari - 5),
    )
    paid_state = replace(state, players=replace_player(state.players, paid_owner))
    first_discard = discard_personal_card_from_hand(
        paid_state,
        action.actor,
        first_card_id,
        source=source,
    )
    second_discard = discard_personal_card_from_hand(
        first_discard.state,
        action.actor,
        card_id,
        source=source,
    )
    resolved_owner = second_discard.state.players[action.actor]
    resolved_owner = replace(
        resolved_owner,
        victory_points=resolved_owner.victory_points + 1,
    )
    next_state = advance_after_effect(
        second_discard.state,
        context,
        replace_player(second_discard.state.players, resolved_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            *first_discard.events,
            *second_discard.events,
            GameEvent(
                event_id=f"{source}:resolved",
                kind="corrinth_city_payment_resolved",
                payload=(
                    ("player", action.actor),
                    ("solari", 5),
                    ("victory_points", 1),
                ),
            ),
        ),
    )


def apply_agent_card_payment(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve or decline an Agent-box resource payment."""

    if action not in legal_agent_card_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card payment choice")
    _, context = current_agent_effect_context(state)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_card_payment"
    if action.action_id == "decline_agent_card_payment":
        next_state = advance_after_effect(state, context)
        event = GameEvent(
            event_id=f"{source}:declined",
            kind="agent_card_payment_declined",
            payload=(("player", action.actor),),
        )
        return RuleResult(state=next_state, events=(event,))

    if action.action_id in _ARRAKIS_REVOLT_ACTION_IDS:
        return _apply_arrakis_revolt_payment(state, action, context, source)

    owner = state.players[action.actor]
    if action.action_id == "pay_agent_card_two_specimens":
        # Tleilaxu Surgeon: two specimens return to the supply as they are
        # spent [Immortality p. 8]; the token advances twice.
        paid_owner = spend_specimens(owner, 2)
        next_state = advance_after_effect(
            state, context, replace_player(state.players, paid_owner)
        )
        advanced = advance_tleilaxu(
            next_state, action.actor, 2, source=f"{source}:tleilaxu"
        )
        return RuleResult(
            state=advanced.state,
            events=(
                GameEvent(
                    event_id=f"{source}:paid",
                    kind="agent_card_payment_resolved",
                    payload=(
                        ("player", action.actor),
                        ("resource", "specimen"),
                        ("spent", 2),
                    ),
                ),
                *advanced.events,
            ),
        )
    if action.action_id == "trash_grafted_card_for_specimen":
        # Dissecting Kit: the other grafted card leaves play; its
        # un-activated box expires with it (OQ-022 designer ruling).
        partner = other_grafted_card_id(context)
        context["graft_pending_effect"] = False
        context["graft_pending_icons"] = ""
        next_state = advance_after_effect(state, context)
        trashed = trash_personal_card(
            next_state, action.actor, partner, source=f"{source}:trash"
        )
        generated = generate_specimens(
            trashed.state, action.actor, 1, source=f"{source}:specimen"
        )
        return RuleResult(
            state=generated.state,
            events=(
                GameEvent(
                    event_id=f"{source}:paid",
                    kind="agent_card_payment_resolved",
                    payload=(
                        ("card_id", partner),
                        ("player", action.actor),
                        ("resource", "card"),
                        ("spent", 1),
                    ),
                ),
                *trashed.events,
                *generated.events,
            ),
        )
    if action.action_id == "take_agent_card_combat_icon":
        # High Priority Travel's Combat half; the grant writes the frame, so
        # the context is re-read before the box closes.
        with_icon = grant_combat_icon(state, action.actor)
        _, granted = current_agent_effect_context(with_icon)
        granted["pending_agent_effect"] = False
        next_state = advance_after_effect(with_icon, granted, with_icon.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:combat_icon",
                    kind="agent_card_effect_resolved",
                    payload=(
                        ("card_id", _effect_subject(context)[1]),
                        ("player", action.actor),
                    ),
                ),
            ),
        )
    if action.action_id == "trash_agent_card_self_for_vp":
        # Scientific Breakthrough: the card trashes itself as its own cost,
        # so its research still pays out (OQ-022); the direction choice
        # opens above the settled turn.
        card_instance_id = _effect_subject(context)[1]
        context["agent_card_self_trashed"] = True
        trashed = trash_personal_card(
            state, action.actor, card_instance_id, source=f"{source}:trash"
        )
        trashed_owner = trashed.state.players[action.actor]
        rewarded = replace(
            trashed_owner, victory_points=trashed_owner.victory_points + 1
        )
        next_state = advance_after_effect(
            trashed.state, context, replace_player(trashed.state.players, rewarded)
        )
        researched = advance_research(
            next_state, action.actor, source=f"{source}:research"
        )
        return RuleResult(
            state=researched.state,
            events=(
                GameEvent(
                    event_id=f"{source}:victory_point",
                    kind="agent_card_trashed_for_vp",
                    payload=(
                        ("card_id", card_instance_id),
                        ("player", action.actor),
                        ("victory_points", 1),
                    ),
                ),
                *trashed.events,
                *researched.events,
            ),
        )
    if action.action_id == "pay_agent_card_five_solari_for_tleilaxu":
        # Slig Farmer: the per-icon Solari land, then five pay the track.
        icon_solari = _partner_icon_count(state, context)
        paid_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + icon_solari - SLIG_FARMER_PRICE,
            ),
        )
        next_state = advance_after_effect(
            state, context, replace_player(state.players, paid_owner)
        )
        advanced = advance_tleilaxu(
            next_state, action.actor, 1, source=f"{source}:tleilaxu"
        )
        return RuleResult(
            state=advanced.state,
            events=(
                GameEvent(
                    event_id=f"{source}:paid",
                    kind="agent_card_payment_resolved",
                    payload=(
                        ("gained", icon_solari),
                        ("player", action.actor),
                        ("resource", "solari"),
                        ("spent", SLIG_FARMER_PRICE),
                    ),
                ),
                *advanced.events,
            ),
        )
    if action.action_id == "trash_grafted_card_for_influence":
        # Beguiling Pheromones: trashing the other grafted card expires its
        # un-activated box (OQ-022, FAQ p. 1); trashing itself keeps the
        # Influence (its own cost).
        _, active_id, space_id = _effect_subject(context)
        trashed_id = str(dict(action.arguments)["card_id"])
        if trashed_id == active_id:
            context["agent_card_self_trashed"] = True
        else:
            context["graft_pending_effect"] = False
            context["graft_pending_icons"] = ""
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("Beguiling Pheromones needs a Faction space")
        next_state = advance_after_effect(state, context)
        trashed = trash_personal_card(
            next_state, action.actor, trashed_id, source=f"{source}:trash"
        )
        gained = gain_faction_influence(
            trashed.state,
            action.actor,
            faction,
            1,
            event_prefix=f"{source}:influence:{faction.value}",
        )
        return RuleResult(
            state=gained.state, events=(*trashed.events, *gained.events)
        )
    if action.action_id == "lose_agent_card_troop":
        # Piter, Genius Advisor: the troop is the cost; the two cards and
        # the research follow once the box has settled.
        zone = str(dict(action.arguments)["zone"])
        lost = lose_unit(state, action.actor, zone, source=f"{source}:troop")
        lost_state = lost.state
        if zone == "conflict":
            lost_state = reconcile_deployment_after_retreat(
                lost_state, action.actor, troops=1
            )
        next_state = advance_after_effect(lost_state, context, lost_state.players)
        researched = advance_research(
            next_state, action.actor, source=f"{source}:research"
        )
        drawn = draw_or_request_personal_cards(
            researched.state, action.actor, 2, source=f"{source}:draw"
        )
        return RuleResult(
            state=drawn.state,
            events=(*lost.events, *researched.events, *drawn.events),
        )
    if action.action_id == "choose_agent_card_reward":
        return _apply_stitched_horror_reward(state, action, context, source)
    if action.action_id == "pay_agent_card_specimen":
        # Organ Merchants: the specimen returns to the supply as it is spent
        # [Immortality p. 8].
        paid_owner = spend_specimens(owner, 1)
        paid_owner = replace(
            paid_owner,
            resources=replace(
                paid_owner.resources, solari=paid_owner.resources.solari + 4
            ),
        )
        next_state = advance_after_effect(
            state, context, replace_player(state.players, paid_owner)
        )
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:paid",
                    kind="agent_card_payment_resolved",
                    payload=(
                        ("player", action.actor),
                        ("resource", "specimen"),
                        ("spent", 1),
                    ),
                ),
            ),
        )
    source_card = personal_card_for_instance(_effect_subject(context)[1])
    pays_water = (
        source_card.agent_effect
        is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
    )
    resource = "water" if pays_water else "spice"
    spent = 2 if pays_water else 4
    if not pays_water:
        previous_spent = context.get("spice_spent_after_placement", 0)
        if isinstance(previous_spent, bool) or not isinstance(previous_spent, int):
            raise RuntimeError("Agent-turn effect frame has invalid Spice spending")
        context["spice_spent_after_placement"] = previous_spent + spent
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            water=owner.resources.water - (spent if pays_water else 0),
            spice=owner.resources.spice - (0 if pays_water else spent),
        ),
        spice_spent_turn=owner.spice_spent_turn + (0 if pays_water else spent),
        victory_points=owner.victory_points + (0 if pays_water else 1),
    )
    players = replace_player(state.players, next_owner)
    paid_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=f"{source}:paid",
        kind="agent_card_payment_resolved",
        payload=(
            ("player", action.actor),
            ("resource", resource),
            ("spent", spent),
        ),
    )
    if not pays_water:
        return RuleResult(state=paid_state, events=(event,))
    draw = draw_or_request_personal_cards(
        paid_state,
        action.actor,
        2,
        source=source,
    )
    return RuleResult(state=draw.state, events=(event, *draw.events))


_ARRAKIS_REVOLT_ACTION_IDS = frozenset(
    {
        "pay_agent_card_spice_for_sandworm",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
    }
)


def _trashes_remaining(context: dict[str, ActionValue], default: int = 0) -> int:
    """Return how many optional trash icons of the current box are still open.

    The Beast's Spoils sets the counter to its Crysknife count when its
    automatic rewards resolve; Ruthless Leadership's two printed icons start
    from ``default`` on the first offer.
    """

    remaining = context.get("trashes_remaining", default)
    if isinstance(remaining, bool) or not isinstance(remaining, int):
        raise RuntimeError("Agent-turn effect frame has invalid trash count")
    return remaining


def _pending_trash_icons(card: PersonalCardDefinition) -> int:
    """Return the printed optional trash icons a box offers before any counter."""

    if (
        getattr(card, "agent_effect", None)
        is PersonalCardAgentEffect.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT
    ):
        return 2
    return 0


def _arrakis_revolt_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Arrakis Revolt's arrow payment: 2 spice for the wall and a worm.

    "You may remove the Shield Wall" and the sandworm are the two icons after
    the arrow [Main p. 20]. The removal is optional, so paying while keeping
    the wall is offered only when the worm can still do something (the
    Conflict is not Shield Wall-protected); a summon that "does nothing"
    against a protected Conflict is not worth two spice (OQ-026).
    """

    decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
    owner = state.players[player]
    if (
        not owner.maker_hooks
        or owner.resources.spice < 2
        or not state.current_conflict_ids
    ):
        return (decline,)
    actions = [decline]
    if state.shield_wall_present:
        actions.append(
            DomainAction(
                action_id="pay_agent_card_spice_for_sandworm_and_shield_wall",
                actor=player,
            )
        )
    if not current_conflict_is_shield_wall_protected(state):
        actions.append(
            DomainAction(action_id="pay_agent_card_spice_for_sandworm", actor=player)
        )
    return tuple(actions)


def _apply_arrakis_revolt_payment(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
    source: str,
) -> RuleResult:
    owner = state.players[action.actor]
    previous_spent = context.get("spice_spent_after_placement", 0)
    if isinstance(previous_spent, bool) or not isinstance(previous_spent, int):
        raise RuntimeError("Agent-turn effect frame has invalid Spice spending")
    context["spice_spent_after_placement"] = previous_spent + 2
    next_owner = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice - 2),
        spice_spent_turn=owner.spice_spent_turn + 2,
    )
    paid = replace(state, players=replace_player(state.players, next_owner))
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:paid",
            kind="agent_card_payment_resolved",
            payload=(("player", action.actor), ("resource", "spice"), ("spent", 2)),
        )
    ]
    if action.action_id == "pay_agent_card_spice_for_sandworm_and_shield_wall":
        destroyed = destroy_shield_wall(
            paid,
            event_id=f"{source}:shield_wall",
            source=f"player:{action.actor}:arrakis_revolt",
        )
        paid = destroyed.state
        events.extend(destroyed.events)
    owner = paid.players[action.actor]
    replaced = 0
    if replaces_sandworms(owner) and not units_deployment_blocked(paid, action.actor):
        # Arrakis Planetologist, even under the Shield Wall [Liet Kynes card].
        replaced = 1
    elif current_conflict_is_shield_wall_protected(paid) or units_deployment_blocked(
        paid, action.actor
    ):
        # No effect against a Shield Wall-protected Conflict [Main p. 20] or
        # while Emperor of the Known Universe blocks deployment [Main p. 17].
        events.append(
            GameEvent(
                event_id=f"{source}:sandworm_unavailable",
                kind="sandworm_summon_unavailable",
                payload=(("player", action.actor),),
            )
        )
    else:
        owner = replace(
            owner,
            sandworms_conflict=owner.sandworms_conflict + 1,
            units_deployed_turn=owner.units_deployed_turn + 1,
        )
        paid = replace(paid, players=replace_player(paid.players, owner))
        events.append(
            GameEvent(
                event_id=f"{source}:sandworm",
                kind="sandworm_deployed",
                payload=(("count", 1), ("player", action.actor)),
            )
        )
    next_state = advance_after_effect(paid, context, paid.players)
    if replaced:
        replacement = replace_sandworms(
            next_state, action.actor, replaced, source=source
        )
        return RuleResult(
            state=replacement.state, events=(*events, *replacement.events)
        )
    return RuleResult(state=next_state, events=tuple(events))


def _still_owned(owner: PlayerState, card_instance_id: str) -> bool:
    """Return whether the card still sits in a trash-eligible owned zone."""

    return card_instance_id in (*owner.hand, *owner.discard_pile, *owner.in_play)


def expire_trashed_card_effects(result: RuleResult) -> RuleResult:
    """Expire a pending Agent box whose played card already left play.

    You can't receive or activate an effect from a card that is already
    trashed (OQ-022 designer ruling), so when a freely ordered effect
    trashes the played card before its Agent box is activated, the whole
    un-activated box expires instead of resolving.
    """

    state = result.state
    if not state.decision_stack:
        return result
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        return result
    context = dict(frame.context)
    player, card_instance_id, _ = _effect_subject(context)
    owner = state.players[player]
    expired: list[str] = []
    if (
        context.get("pending_agent_effect") is True
        # The card left play through its own printed cost or icon; its
        # remaining printed rewards still pay out (OQ-022 designer ruling).
        and context.get("agent_card_self_trashed") is not True
        and not _still_owned(owner, card_instance_id)
    ):
        context["pending_agent_effect"] = False
        context["pending_agent_icons"] = ""
        expired.append(card_instance_id)
    graft_card_id = other_grafted_card_id(context)
    if (
        context.get("graft_pending_effect") is True
        and graft_card_id
        and not _still_owned(owner, graft_card_id)
    ):
        # The grafted partner's un-activated box expires the same way
        # (Beguiling Pheromones trashing it, FAQ p. 1).
        context["graft_pending_effect"] = False
        context["graft_pending_icons"] = ""
        expired.append(graft_card_id)
    if not expired:
        return result
    next_state = advance_after_effect(state, context)
    events = tuple(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{expired_id}:effect_expired"
            ),
            kind="agent_card_effect_expired",
            payload=(("card_id", expired_id), ("player", player)),
        )
        for expired_id in expired
    )
    return RuleResult(state=next_state, events=(*result.events, *events))


def agent_card_icons_at_placement(
    effect: PersonalCardAgentEffect | None,
) -> tuple[str, ...]:
    """Return the icon keys an Agent box queues when its card is played.

    Empty for single-effect boxes and for arrow boxes, whose reward icons
    are queued once the cost is paid.
    """

    if effect is None:
        return ()
    return _PLACEMENT_ICONS.get(effect, ())


def legal_agent_card_icon_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return one ``resolve_agent_card_effect`` action per pending automatic icon."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    return tuple(
        DomainAction(
            action_id="resolve_agent_card_effect",
            actor=player,
            arguments=(("effect", key),),
        )
        for key in pending_agent_icons(context)
        if key in AUTOMATIC_AGENT_ICONS
    )


def resolve_agent_card_icon(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one printed icon of the played card's Agent box.

    Conditions printed on the box (Hidden Missive's, Maker Keeper's and
    Wheels Within Wheels' Influence thresholds) are judged when the icon
    resolves in the owner's order [Main pp. 7, 9]; an unmet condition
    consumes the icon without effect.
    """

    if action not in legal_agent_card_icon_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card icon resolution")
    _, context = current_agent_effect_context(state)
    player, card_instance_id, _ = _effect_subject(context)
    card = active_agent_card(context)
    effect = card.agent_effect
    key = str(dict(action.arguments)["effect"])
    owner = state.players[player]
    source = (
        f"round:{state.round_number}:player:{player}:agent_card:{card_instance_id}"
    )
    finish_agent_icon(context, key)

    extra_events: tuple[GameEvent, ...] = ()

    def recruit(amount: int) -> PlayerState:
        nonlocal extra_events
        recruited_owner, recruited = recruit_troops(owner, amount)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        extra_events = (
            *extra_events,
            *recruit_shortfall_events(f"{source}:{key}", player, amount, recruited),
        )
        return recruited_owner

    def gain(*, solari: int = 0, spice: int = 0, water: int = 0) -> PlayerState:
        return replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + solari,
                spice=owner.resources.spice + spice,
                water=owner.resources.water + water,
            ),
        )

    hidden_missive = (
        effect
        is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    )
    # Fremen War Name: both icons need two spice gained this turn, judged
    # when each icon resolves (OQ-028).
    war_name_blocked = (
        effect
        is (
            PersonalCardAgentEffect
            .RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN
        )
        and spice_gained_this_turn(owner) < 2
    )
    # Sardaukar Quartermaster: both icons need the card to be grafted.
    quartermaster_blocked = (
        effect is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED
        and not is_grafted(context)
    )
    missive_blocked = (
        hidden_missive and owner.influence.bene_gesserit < 2
    ) or quartermaster_blocked
    maker_keeper = (
        effect is PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
    )
    wheels = (
        effect
        is PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
    )
    next_owner = owner
    effect_state = state
    available = True
    personal_draw_count = 0
    intrigue_draw_count = 0
    match key:
        case "cards":
            if missive_blocked or war_name_blocked:
                available = False
            else:
                personal_draw_count = 1
        case "intrigue":
            if (
                effect is PersonalCardAgentEffect.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS
                and genetic_markers_reached(owner.research_space) < 2
            ):
                # Tleilaxu Infiltrator: the Intrigue needs both genetic
                # markers, judged when the icon resolves (OQ-028).
                available = False
            else:
                intrigue_draw_count = 1
        case "troops":
            if missive_blocked or war_name_blocked:
                available = False
            else:
                next_owner = recruit(
                    2
                    if effect
                    is (
                        PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
                    )
                    else 1
                )
        case "solari":
            if wheels and owner.influence.emperor >= 2:
                next_owner = gain(solari=2)
            else:
                available = False
        case "spice":
            if (maker_keeper and owner.influence.fremen >= 2) or (
                wheels and owner.influence.spacing_guild >= 2
            ):
                next_owner = gain(spice=1)
            else:
                available = False
        case "water":
            if maker_keeper and owner.influence.bene_gesserit >= 2:
                next_owner = gain(water=1)
            else:
                available = False
        case "trash_self":
            if card_instance_id in owner.in_play:
                # The card trashes itself by its own printed icon, so any
                # icon still queued keeps paying out (OQ-022).
                context["agent_card_self_trashed"] = True
                trashed = trash_personal_card(
                    state, player, card_instance_id, source=source
                )
                effect_state = trashed.state
                next_owner = effect_state.players[player]
                extra_events = trashed.events
            else:
                available = False
        case "pledge":
            effect_state = replace(
                state,
                conflict_first_place_influence_bonus=(
                    state.conflict_first_place_influence_bonus + 1
                ),
            )
            extra_events = (
                GameEvent(
                    event_id=f"{source}:{key}",
                    kind="first_place_influence_pledged",
                    payload=(
                        ("conflict_id", state.current_conflict_ids[-1]),
                        ("player", player),
                    ),
                ),
            )
        case _:
            raise RuntimeError(f"unknown Agent-card icon: {key}")

    effect_state = replace(
        effect_state, players=replace_player(effect_state.players, next_owner)
    )
    intrigue_events: tuple[GameEvent, ...] = ()
    if intrigue_draw_count:
        intrigue_draw = draw_or_queue_intrigue_cards(
            effect_state, player, intrigue_draw_count, source=f"{source}:{key}"
        )
        effect_state = intrigue_draw.state
        intrigue_events = intrigue_draw.events
    next_state = advance_after_effect(effect_state, context)
    draw_events: tuple[GameEvent, ...] = ()
    if personal_draw_count:
        draw = draw_or_request_personal_cards(
            next_state, player, personal_draw_count, source=f"{source}:{key}"
        )
        next_state = draw.state
        draw_events = draw.events
    event = GameEvent(
        event_id=f"{source}:{key}:resolved",
        kind=(
            "agent_card_effect_resolved"
            if available
            else "agent_card_effect_unavailable"
        ),
        payload=(("card_id", card_instance_id), ("effect", key), ("player", player)),
    )
    return RuleResult(
        state=next_state,
        events=(*extra_events, *intrigue_events, *draw_events, event),
    )


_UNAVAILABLE_CACHE: list[tuple[GameState, bool]] = []
_UNAVAILABLE_CACHE_SIZE: Final = 8


def agent_card_effect_is_unavailable(state: GameState) -> bool:
    """Return whether the pending Agent box would resolve without effect now.

    A mandatory box whose printed condition is false cannot be "fired to
    fizzle" while the turn goes on (designer ruling, OQ-057): a later effect
    of the same turn may still meet it (Guild Envoy's discard after a draw),
    so the box waits and fizzles only when the owner ends the turn. The
    check dry-runs the resolution on the immutable state; the last few
    answers are kept by state identity because the legal-action providers
    ask several times per step.
    """

    for cached_state, cached in _UNAVAILABLE_CACHE:
        if cached_state is state:
            return cached
    answer = _dry_run_effect_is_unavailable(state)
    _UNAVAILABLE_CACHE.append((state, answer))
    if len(_UNAVAILABLE_CACHE) > _UNAVAILABLE_CACHE_SIZE:
        del _UNAVAILABLE_CACHE[0]
    return answer


def _dry_run_effect_is_unavailable(state: GameState) -> bool:
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if context.get("pending_agent_effect") is not True:
        return False
    if pending_agent_icons(context):
        return _pending_icons_offer_nothing(state, context)
    try:
        dry_run = resolve_agent_card_effect(state)
    except (NotImplementedError, RuntimeError, ValueError):
        return False
    return bool(dry_run.events) and (
        dry_run.events[0].kind == "agent_card_effect_unavailable"
    )


def _pending_icons_offer_nothing(
    state: GameState,
    context: dict[str, ActionValue],
) -> bool:
    """Return whether a multi-icon box has icons nothing can resolve.

    A multi-icon box resolves icon by icon through exactly three providers
    (OQ-027), so when all three are empty the icons cannot be resolved at
    all. Ghola copying Steersman's "draw a card, recall an Agent" box
    reaches this: the first box already recalled the seat's last Agent, so
    the copy's recall icon has no target. Like any other mandatory box
    whose condition is false it now waits for the turn's end instead of
    stalling it (OQ-057), and a later effect that gives the icon a target
    makes it resolvable again.
    """

    player = context_int(context, "turn_owner")
    return not (
        legal_agent_card_icon_actions(state, player)
        or legal_agent_card_recall_actions(state, player)
        or legal_agent_card_influence_actions(state, player)
    )


def fizzle_pending_agent_icons(state: GameState) -> RuleResult:
    """Retire a multi-icon Agent box whose icons nothing can resolve.

    The counterpart of ``resolve_agent_card_effect``'s unavailable branch
    for boxes that resolve icon by icon; ``finish_agent_turn`` calls it so
    the turn's end fizzles the box (OQ-057).
    """

    _, context = current_agent_effect_context(state)
    keys = pending_agent_icons(context)
    if context.get("pending_agent_effect") is not True or not keys:
        raise ValueError("the pending Agent box has no icons to retire")
    player, card_instance_id, _ = _effect_subject(context)
    source = f"round:{state.round_number}:player:{player}:agent_card:{card_instance_id}"
    for key in keys:
        finish_agent_icon(context, key)
    return RuleResult(
        state=advance_after_effect(state, context),
        events=tuple(
            GameEvent(
                event_id=f"{source}:{key}:resolved",
                kind="agent_card_effect_unavailable",
                payload=(
                    ("card_id", card_instance_id),
                    ("effect", key),
                    ("player", player),
                ),
            )
            for key in keys
        ),
    )


def graft_boxes_are_stalled(state: GameState) -> bool:
    """Return whether the pending box, and the grafted partner's if any, only fizzle.

    With a graft the owner may switch to the other card's box; the turn is
    stalled only when that box would fizzle as well (or has none).
    """

    if not agent_card_effect_is_unavailable(state):
        return False
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if context.get("graft_pending_effect") is not True:
        return True
    from dune_imperium.rules.graft import apply_graft_switch, legal_graft_switch_actions

    switches = legal_graft_switch_actions(state, context_int(context, "turn_owner"))
    if not switches:
        return True
    switched = apply_graft_switch(state, switches[0]).state
    return agent_card_effect_is_unavailable(switched)


def resolve_agent_card_effect(state: GameState) -> RuleResult:
    """Resolve the supported Agent box in the current effect frame."""

    _, context = current_agent_effect_context(state)
    if context["pending_agent_effect"] is not True:
        raise ValueError("the current Agent turn has no pending card effect")
    if pending_agent_icons(context):
        raise ValueError("this Agent box resolves icon by icon")
    player, card_instance_id, _ = _effect_subject(context)
    card = active_agent_card(context)
    effect = card.agent_effect

    owner = state.players[player]
    event_source = (
        f"round:{state.round_number}:player:{player}:agent_card:{card_instance_id}"
    )
    recruit_shortfall: tuple[GameEvent, ...] = ()
    if effect is PersonalCardAgentEffect.LEADER_SIGNET:
        return resolve_leader_signet(state)
    if effect is PersonalCardAgentEffect.TRASH_SELF:
        # "Trash this card." (Seek Allies) is mandatory [Main p. 20]. A card
        # trashed by a freely ordered effect expires before this resolution
        # is offered (OQ-022), so the card is still in play here.
        trashed = trash_personal_card(
            state,
            player,
            card_instance_id,
            source=f"round:{state.round_number}:player:{player}:agent_card",
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            trashed.state,
            context,
            trashed.state.players,
        )
        return RuleResult(state=next_state, events=trashed.events)
    if (
        effect
        is PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF
    ):
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("card effect requires a visited Faction space")
        source = (
            f"round:{state.round_number}:player:{player}:"
            f"agent_card:{card_instance_id}"
        )
        gained = gain_faction_influence(
            state,
            player,
            faction,
            2,
            event_prefix=f"{source}:influence:{faction.value}",
        )
        trashed = trash_personal_card(
            gained.state,
            player,
            card_instance_id,
            source=source,
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            trashed.state,
            context,
            trashed.state.players,
        )
        return RuleResult(
            state=next_state,
            events=(*gained.events, *trashed.events),
        )
    elif effect is PersonalCardAgentEffect.LOOK_AT_TOP_THREE:
        if context.get(_LONG_LIVE_SELECTION_STARTED) is True:
            raise RuntimeError(
                "Long Live the Fighters selection is already in progress"
            )
        if len(owner.deck) < 3:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            context[_LONG_LIVE_SELECTION_STARTED] = True
            frame = state.decision_stack[-1]
            next_frame = replace(frame, context=tuple(sorted(context.items())))
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}:long_live_fighters"
            )
            return RuleResult(
                state=replace(
                    state,
                    decision_stack=(*state.decision_stack[:-1], next_frame),
                ),
                events=(
                    GameEvent(
                        event_id=f"{source}:ready",
                        kind="agent_card_effect_ready",
                        payload=(
                            ("card_id", card_instance_id),
                            ("player", player),
                        ),
                    ),
                ),
            )
    elif effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD:
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif (
        effect
        is PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO
    ):
        next_owner = owner
        event_kind = (
            "agent_card_effect_resolved"
            if len(owner.completed_contract_ids) >= 2
            else "agent_card_effect_unavailable"
        )
    elif effect is PersonalCardAgentEffect.FORCE_OPPONENT_TROOP_RETREAT:
        if any(
            seat.player_id != player and seat.troops_conflict + seat.commanders_conflict
            for seat in state.players
        ):
            raise RuntimeError("enemy retreat requires a player choice")
        # No enemy unit in the Conflict: nothing to retreat (OQ-028).
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.RECRUIT_ONE_IF_EMPEROR_INFLUENCE_TWO:
        # Command Center (Bloodlines): "Emperor 2 Influence: troop", judged
        # when the box resolves (OQ-028).
        if owner.influence.emperor >= 2:
            next_owner, recruited = recruit_troops(owner, 1)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            recruit_shortfall = recruit_shortfall_events(
                event_source, player, 1, recruited
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN:
        # Sandwalk (Bloodlines): "If you gained 2 spice or more this turn:
        # draw a card"; the draw follows the generic path below.
        next_owner = owner
        event_kind = (
            "agent_card_effect_resolved"
            if spice_gained_this_turn(owner) >= 2
            else "agent_card_effect_unavailable"
        )
    elif effect in (
        PersonalCardAgentEffect.DRAW_INTRIGUE_CARD,
        PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT,
        PersonalCardAgentEffect.DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN,
    ):
        # Imperial Throneship / Shrouded Counsel: an Intrigue draw; Pointing
        # the Way: "If you have one or more sandworms in the Conflict:
        # Intrigue"; Mercantile Affairs: "If you completed a contract this
        # turn: Intrigue" (Bloodlines card faces).
        met = (
            owner.sandworms_conflict >= 1
            if effect is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT
            else owner.contracts_completed_turn >= 1
            if effect
            is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN
            else True
        )
        if not met:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            intrigue_draw = draw_or_queue_intrigue_cards(
                state, player, 1, source=f"{event_source}:intrigue_draw"
            )
            context["pending_agent_effect"] = False
            next_state = advance_after_effect(intrigue_draw.state, context)
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=event_source,
                        kind="agent_card_effect_resolved",
                        payload=(("card_id", card_instance_id), ("player", player)),
                    ),
                    *intrigue_draw.events,
                ),
            )
    elif effect is PersonalCardAgentEffect.TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN:
        # Corrupt Bureaucrat (Bloodlines): "If you recalled a Spy this turn:
        # contract" (2 Solari without the CHOAM Module [Main p. 20]).
        if context.get("spy_recalled_this_turn") is not True:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            context["pending_agent_effect"] = False
            resumed = advance_after_effect(state, context)
            contracts = begin_contract_gain(
                resumed, player, 1, source=event_source
            )
            return RuleResult(
                state=contracts.state,
                events=(
                    GameEvent(
                        event_id=event_source,
                        kind="agent_card_effect_resolved",
                        payload=(("card_id", card_instance_id), ("player", player)),
                    ),
                    *contracts.events,
                ),
            )
    elif effect is PersonalCardAgentEffect.TAKE_CONTRACT:
        context["pending_agent_effect"] = False
        resumed = advance_after_effect(state, context)
        contracts = begin_contract_gain(
            resumed,
            player,
            1,
            source=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            ),
        )
        event = GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            ),
            kind="agent_card_effect_resolved",
            payload=(("card_id", card_instance_id), ("player", player)),
        )
        return RuleResult(
            state=contracts.state,
            events=(event, *contracts.events),
        )
    elif effect is PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_PERSONAL_CARD:
        context["pending_agent_effect"] = False
        base_frame = replace(
            state.decision_stack[-1],
            context=tuple(sorted(context.items())),
        )
        targets = tuple(
            (player + offset) % state.config.players
            for offset in range(1, state.config.players)
            if state.players[(player + offset) % state.config.players].hand
        )
        frames = tuple(
            DecisionFrame(
                kind=FrameKind.OPPONENT_CARD_DISCARD,
                frame_id=(
                    f"round:{state.round_number}:player:{player}:"
                    f"agent_card:{card_instance_id}:opponent:{target}"
                ),
                decision=PlayerDecision(
                    owner=target,
                    prompt="Choose a card to discard for Covert Operation",
                ),
                context=(
                    ("covert_operation_card_id", card_instance_id),
                    ("covert_operation_owner", player),
                ),
            )
            for target in reversed(targets)
        )
        base_state = replace(
            state,
            decision_stack=(*state.decision_stack[:-1], base_frame, *frames),
        )
        next_state = (
            base_state
            if targets
            else advance_after_effect(base_state, context, base_state.players)
        )
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:player:{player}:"
                        f"agent_card:{card_instance_id}"
                    ),
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
            ),
        )
    elif effect is PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT:
        # Judged when the effect resolves [Main pp. 7, 9]: a sandworm summoned
        # earlier in this turn at a Maker space counts; with none it draws
        # nothing (OQ-028).
        next_owner = owner
        event_kind = (
            "agent_card_effect_resolved"
            if owner.sandworms_conflict
            else "agent_card_effect_unavailable"
        )
    elif effect is PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO:
        # The Influence condition is judged when the effect resolves in the
        # player's chosen order, which can differ from the placement-time
        # check [Main pp. 7, 9]; below two Bene Gesserit Influence the
        # conditional draw simply does nothing.
        next_owner = owner
        event_kind = (
            "agent_card_effect_resolved"
            if owner.influence.bene_gesserit >= 2
            else "agent_card_effect_unavailable"
        )
    elif (
        effect
        is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    ):
        if owner.influence.bene_gesserit >= 2:
            next_owner, recruited = recruit_troops(owner, 1)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            recruit_shortfall = recruit_shortfall_events(
                event_source, player, 1, recruited
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str) or not BOARD_SPACES_BY_ID[space_id].maker:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + 1,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_MAKER_SPACE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str) or not BOARD_SPACES_BY_ID[space_id].maker:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + 2,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str) or not BOARD_SPACES_BY_ID[space_id].maker:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner, recruited = recruit_troops(owner, 1)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        recruit_shortfall = recruit_shortfall_events(event_source, player, 1, recruited)
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.BOOST_NEXT_BENE_GESSERIT_CARD_THIS_ROUND:
        # Urgent Shigawire arms the seat; the boost is spent by the next
        # Bene Gesserit card played this round (``agent_turn``).
        next_owner = replace(owner, bene_gesserit_boost_pending=True)
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY:
        # Holy War: the opponents' decisions are pushed once this frame has
        # advanced (below).
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.COMPLETE_ONE_CONTRACT:
        # CHOAM Demands resolves through its own Contract choice; with no
        # active Contract the box does nothing.
        if owner.active_contract_ids:
            raise ValueError("CHOAM Demands resolves through complete_contract_by_card")
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND:
        # Southern Faith's draw half; the draw follows the generic path.
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif effect in (
        PersonalCardAgentEffect.RECRUIT_TWO_TROOPS,
        PersonalCardAgentEffect.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND,
    ):
        # Possible Futures' two-troop half (the Bond case pays both through
        # the Influence choice instead).
        next_owner, recruited = recruit_troops(owner, 2)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        recruit_shortfall = recruit_shortfall_events(event_source, player, 2, recruited)
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_WATER:
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                water=owner.resources.water + 1,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_TWO_SOLARI:
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 2,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_ONE_SPICE:
        # Ixian Ambassador: "1 spice" [card face].
        next_owner = replace(
            owner,
            resources=replace(owner.resources, spice=owner.resources.spice + 1),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.DRAW_TWO_IF_ONE_MARKER:
        # Unnatural Reflexes: "[one genetic marker]: draw two cards".
        if genetic_markers_reached(owner.research_space) >= 1:
            next_owner = owner
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect in (
        PersonalCardAgentEffect.ADVANCE_TLEILAXU,
        PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_ONE_MARKER,
        PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_GRAFTED,
    ):
        # Contaminator's Tleilaxu icon; Subject X-137 needs the first genetic
        # marker, judged now (OQ-028) [Immortality pp. 6-7, 16].
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context)
        if (
            effect is PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_ONE_MARKER
            and genetic_markers_reached(owner.research_space) < 1
        ) or (
            # Corrino Genes: "If grafted: Tleilaxu" [Immortality p. 11].
            effect is PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_GRAFTED
            and not is_grafted(context)
        ):
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=event_source,
                        kind="agent_card_effect_unavailable",
                        payload=(("card_id", card_instance_id), ("player", player)),
                    ),
                ),
            )
        advanced = advance_tleilaxu(next_state, player, 1, source=event_source)
        return RuleResult(
            state=advanced.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *advanced.events,
            ),
        )
    elif effect is PersonalCardAgentEffect.PEEK_TWO_INTRIGUE_KEEP_ONE:
        # Imperium Ceremony: the keep-one choice opens once the box has
        # resolved (OQ-052 for a short deck).
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context)
        peek = begin_intrigue_peek(next_state, player, source=event_source)
        return RuleResult(
            state=peek.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *peek.events,
            ),
        )
    elif (
        effect
        is _DRAW_ONE_OR_COMBAT_ICON
    ):
        # High Priority Travel's draw half; the Influence is judged now
        # (OQ-028).
        next_owner = owner
        event_kind = (
            "agent_card_effect_resolved"
            if owner.influence.spacing_guild >= 2
            else "agent_card_effect_unavailable"
        )
    elif (
        effect
        is _SPICE_AND_GRAFTED_INFLUENCE
    ):
        # Interstellar Conspiracy without an Emperor or Guild partner: the
        # spice alone (the Influence choice pays both otherwise).
        next_owner = replace(
            owner,
            resources=replace(owner.resources, spice=owner.resources.spice + 1),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect in (
        PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN,
        PersonalCardAgentEffect.MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER,
        PersonalCardAgentEffect.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU,
        _TRASH_GRAFTED_FOR_INFLUENCE,
        _CHOOSE_TWO_REWARDS,
        _LOSE_TROOP_FOR_CARDS,
    ):
        # Reached only when the box's choice provider offered nothing: no
        # grafted partner, no genetic marker, no Faction space.
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is (
        PersonalCardAgentEffect.RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START
    ):
        # Chairdog: the return is scheduled for the owner's Reveal turn
        # (``begin_reveal_turn``); without a partner in play nothing is.
        partner = other_grafted_card_id(context)
        if partner and partner in owner.in_play:
            next_owner = replace(
                owner,
                chairdog_return_card_ids=(*owner.chairdog_return_card_ids, partner),
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is _DRAW_RESEARCH_SPECIMEN:
        # Industrial Espionage: the draw always; grafted, a specimen and a
        # research step whose direction choice opens above the turn.
        context["pending_agent_effect"] = False
        grafted = is_grafted(context)
        next_state = advance_after_effect(state, context)
        extra: list[GameEvent] = []
        if grafted:
            generated = generate_specimens(
                next_state, player, 1, source=f"{event_source}:specimen"
            )
            researched = advance_research(
                generated.state, player, source=f"{event_source}:research"
            )
            next_state = researched.state
            extra.extend((*generated.events, *researched.events))
        drawn = draw_or_request_personal_cards(
            next_state, player, 1, source=f"{event_source}:draw"
        )
        return RuleResult(
            state=drawn.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *extra,
                *drawn.events,
            ),
        )
    elif effect is _RESEARCH_AND_TRASH_FOR_VP:
        # Scientific Breakthrough without (or declining) the trash: research.
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context)
        researched = advance_research(
            next_state, player, source=f"{event_source}:research"
        )
        return RuleResult(
            state=researched.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *researched.events,
            ),
        )
    elif effect is _GUILD_INFLUENCE_IF_SPICE:
        # Guild Impersonator: judged when the box resolves (OQ-028), so a
        # spice space resolved first counts.
        context["pending_agent_effect"] = False
        if spice_gained_this_turn(owner) < 1:
            return RuleResult(
                state=advance_after_effect(state, context),
                events=(
                    GameEvent(
                        event_id=event_source,
                        kind="agent_card_effect_unavailable",
                        payload=(("card_id", card_instance_id), ("player", player)),
                    ),
                ),
            )
        gained = gain_faction_influence(
            state,
            player,
            Faction.SPACING_GUILD,
            1,
            event_prefix=f"{event_source}:influence:spacing_guild",
        )
        next_state = advance_after_effect(gained.state, context, gained.state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *gained.events,
            ),
        )
    elif effect is _SOLARI_PER_PARTNER_ICON:
        # Slig Farmer without the payment: the per-icon Solari alone.
        gained_solari = _partner_icon_count(state, context)
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources, solari=owner.resources.solari + gained_solari
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GENERATE_SPECIMEN:
        # Bene Tleilax Lab: a specimen [Immortality p. 8].
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context)
        generated = generate_specimens(next_state, player, 1, source=event_source)
        return RuleResult(
            state=generated.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *generated.events,
            ),
        )
    elif effect is PersonalCardAgentEffect.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE:
        # Clandestine Meeting: Bene Gesserit Influence and an Intrigue card.
        gained = gain_faction_influence(
            state,
            player,
            Faction.BENE_GESSERIT,
            1,
            event_prefix=f"{event_source}:influence:bene_gesserit",
        )
        drawn = draw_or_queue_intrigue_cards(
            gained.state, player, 1, source=f"{event_source}:intrigue"
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(drawn.state, context, drawn.state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *gained.events,
                *drawn.events,
            ),
        )
    elif effect in (
        PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_GRAFTED,
        PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO,
    ):
        # Corrupt Smuggler ("If grafted") and Keys to Power ("[Emperor] 2
        # Influence"), judged when the box resolves (OQ-028).
        met = (
            is_grafted(context)
            if effect is PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_GRAFTED
            else owner.influence.emperor >= 2
        )
        if met:
            next_owner = replace(
                owner,
                resources=replace(owner.resources, spice=owner.resources.spice + 2),
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND:
        # Lisan al Gaib: the Bond is judged when the effect resolves
        # [Main pp. 9, 20] (a grafted partner may provide it).
        context["pending_agent_effect"] = False
        if not has_faction_bond(owner.in_play, card_instance_id, Faction.BENE_GESSERIT):
            return RuleResult(
                state=advance_after_effect(state, context),
                events=(
                    GameEvent(
                        event_id=event_source,
                        kind="agent_card_effect_unavailable",
                        payload=(("card_id", card_instance_id), ("player", player)),
                    ),
                ),
            )
        gained = gain_faction_influence(
            state,
            player,
            Faction.FREMEN,
            1,
            event_prefix=f"{event_source}:influence:fremen",
        )
        next_state = advance_after_effect(gained.state, context, gained.state.players)
        return RuleResult(state=next_state, events=gained.events)
    elif effect is PersonalCardAgentEffect.DRAW_ONE_AND_COMBAT_ICON:
        # Occupation: draw a card and the Combat icon [Immortality p. 16].
        # The grant writes the frame, so the context is re-read before the
        # box closes.
        with_icon = grant_combat_icon(state, player)
        _, granted = current_agent_effect_context(with_icon)
        granted["pending_agent_effect"] = False
        next_state = advance_after_effect(with_icon, granted, with_icon.players)
        drawn = draw_or_request_personal_cards(
            next_state, player, 1, source=f"{event_source}:draw"
        )
        return RuleResult(
            state=drawn.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *drawn.events,
            ),
        )
    elif effect is PersonalCardAgentEffect.DRAW_TWO_CARDS:
        # Show of Strength: draw two cards.
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE
    ):
        # Stillsuit Manufacturer: water, and with the Fremen Alliance the
        # card returns from play to the hand (judged now, OQ-028).
        next_owner = replace(
            owner, resources=replace(owner.resources, water=owner.resources.water + 1)
        )
        if (
            Faction.FREMEN.value in owner.alliance_faction_ids
            and card_instance_id in owner.in_play
            # A Row card borrowed by Usurp is not "in play" and cannot
            # return to a hand (designer ruling, OQ-054); it is trashed
            # when the turn closes.
            and card_instance_id != owner.usurped_row_card_id
        ):
            # Face up in play, so everyone keeps knowing it (OQ-010).
            next_owner = replace(
                next_owner,
                hand=(*next_owner.hand, card_instance_id),
                hand_public=(*next_owner.hand_public, card_instance_id),
                in_play=tuple(
                    candidate
                    for candidate in next_owner.in_play
                    if candidate != card_instance_id
                ),
            )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.RECRUIT_ONE_AND_MAY_TRASH:
        # Throne Room Politics: a troop and a black trash icon (optional
        # [Main p. 20]); the trash opens after the recruit.
        next_owner, recruited = recruit_troops(owner, 1)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        recruit_shortfall = recruit_shortfall_events(event_source, player, 1, recruited)
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            state, context, replace_player(state.players, next_owner)
        )
        return RuleResult(
            state=next_state.push_decision(optional_trash_frame(player, event_source)),
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *recruit_shortfall,
            ),
        )
    elif effect is PersonalCardAgentEffect.RESEARCH:
        # Experimentation: the Research icon [Immortality pp. 6, 16]. The
        # advance (and its direction choice) follows the frame bookkeeping.
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context)
        advanced = advance_research(next_state, player, source=event_source)
        return RuleResult(
            state=advanced.state,
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *advanced.events,
            ),
        )
    elif effect is PersonalCardAgentEffect.GAIN_VISITED_FACTION_INFLUENCE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("card effect requires a visited Faction space")
        gained = gain_faction_influence(
            state,
            player,
            faction,
            1,
            event_prefix=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}:influence:{faction.value}"
            ),
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            gained.state,
            context,
            gained.state.players,
        )
        return RuleResult(state=next_state, events=gained.events)
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
    ):
        # Both Influence conditions are judged when the effect resolves in the
        # player's chosen order [Main pp. 7, 9]; a mid-frame Influence loss
        # (for example an Intrigue cost) can leave the effect with nothing.
        gains_water = owner.influence.bene_gesserit >= 2
        gains_spice = owner.influence.fremen >= 2
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + int(gains_spice),
                water=owner.resources.water + int(gains_water),
            ),
        )
        event_kind = (
            "agent_card_effect_resolved"
            if gains_water or gains_spice
            else "agent_card_effect_unavailable"
        )
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
    ):
        # Judged at resolution time like Maker Keeper's pair of conditions
        # [Main pp. 7, 9]; with neither Influence the effect does nothing.
        gains_solari = owner.influence.emperor >= 2
        gains_spice = owner.influence.spacing_guild >= 2
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 2 * int(gains_solari),
                spice=owner.resources.spice + int(gains_spice),
            ),
        )
        event_kind = (
            "agent_card_effect_resolved"
            if gains_solari or gains_spice
            else "agent_card_effect_unavailable"
        )
    elif effect is PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND:
        # The Bond is judged when the effect resolves in the player's chosen
        # order [Main pp. 9, 20]; trashing the bonded card mid-frame (for
        # example through an Intrigue slot) forfeits the conditional gain.
        if has_faction_bond(owner.in_play, card_instance_id, Faction.BENE_GESSERIT):
            next_owner, recruited = recruit_troops(owner, 2)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            recruit_shortfall = recruit_shortfall_events(
                event_source, player, 2, recruited
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND:
        # The Bond is judged when the effect resolves [Main pp. 9, 20]; a
        # trashed card expires before this resolution is offered (OQ-022).
        if has_faction_bond(
            owner.in_play,
            card_instance_id,
            Faction.BENE_GESSERIT,
        ):
            # The card was face up in play, so everyone keeps knowing it sits
            # in the hand (OQ-010).
            next_owner = replace(
                owner,
                hand=(*owner.hand, card_instance_id),
                hand_public=(*owner.hand_public, card_instance_id),
                in_play=tuple(
                    candidate
                    for candidate in owner.in_play
                    if candidate != card_instance_id
                ),
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.GAIN_WATER_IF_BENE_GESSERIT_BOND:
        # The Bond is judged when the effect resolves [Main pp. 9, 20].
        if has_faction_bond(owner.in_play, card_instance_id, Faction.BENE_GESSERIT):
            next_owner = replace(
                owner,
                resources=replace(
                    owner.resources,
                    water=owner.resources.water + 1,
                ),
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect in (
        PersonalCardAgentEffect.PLACE_SPY,
        PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE,
    ):
        if legal_agent_card_spy_actions(state, player):
            raise RuntimeError("place-Spy Agent effect requires a player choice")
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN:
        if context.get("spy_recalled_this_turn") is True:
            next_owner, recruited = recruit_troops(owner, 3)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            recruit_shortfall = recruit_shortfall_events(
                event_source, player, 3, recruited
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN:
        if context.get("spy_recalled_this_turn") is True:
            next_owner, recruited = recruit_troops(owner, 2)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            recruit_shortfall = recruit_shortfall_events(
                event_source, player, 2, recruited
            )
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN:
        if context.get("spy_recalled_this_turn") is not True:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            )
            intrigue_draw = draw_or_queue_intrigue_cards(
                state, player, 1, source=f"{source}:intrigue_draw"
            )
            context["pending_agent_effect"] = False
            next_state = advance_after_effect(intrigue_draw.state, context)
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=source,
                        kind="agent_card_effect_resolved",
                        payload=(
                            ("card_id", card_instance_id),
                            ("player", player),
                        ),
                    ),
                    *intrigue_draw.events,
                ),
            )
    elif effect is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT:
        if owner.units_in_conflict < 3:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            )
            intrigue_draw = draw_or_queue_intrigue_cards(
                state, player, 1, source=f"{source}:intrigue_draw"
            )
            context["pending_agent_effect"] = False
            next_state = advance_after_effect(intrigue_draw.state, context)
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=source,
                        kind="agent_card_effect_resolved",
                        payload=(
                            ("card_id", card_instance_id),
                            ("player", player),
                        ),
                    ),
                    *intrigue_draw.events,
                ),
            )
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN
    ):
        if context.get("spy_recalled_this_turn") is True:
            raise RuntimeError("Agent-card Influence effect requires a player choice")
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON:
        # The Beast's Spoils: one reward per printed battle icon kind that is
        # face up in the owner's supply — immediate matching keeps at most
        # one face-up card per icon [Main p. 14] (OQ-024). Spice and the
        # troop resolve here; the Crysknife's optional trash is then offered.
        icons = face_up_battle_icons(owner)
        spice = int(BattleIcon.DESERT_MOUSE in icons)
        next_owner, recruited = recruit_troops(
            owner, int(BattleIcon.ORNITHOPTER in icons)
        )
        next_owner = replace(
            next_owner,
            resources=replace(
                next_owner.resources,
                spice=next_owner.resources.spice + spice,
            ),
        )
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        recruit_shortfall = recruit_shortfall_events(
            event_source, player, int(BattleIcon.ORNITHOPTER in icons), recruited
        )
        crysknives = int(BattleIcon.CRYSKNIFE in icons)
        event_kind = (
            "agent_card_effect_resolved"
            if spice or recruited or crysknives
            else "agent_card_effect_unavailable"
        )
        if crysknives:
            context["trashes_remaining"] = crysknives
            frame = state.decision_stack[-1]
            next_frame = replace(frame, context=tuple(sorted(context.items())))
            return RuleResult(
                state=replace(
                    state,
                    players=replace_player(state.players, next_owner),
                    decision_stack=(*state.decision_stack[:-1], next_frame),
                ),
                events=(
                    GameEvent(
                        event_id=(
                            f"round:{state.round_number}:player:{player}:"
                            f"agent_card:{card_instance_id}"
                        ),
                        kind=event_kind,
                        payload=(
                            ("card_id", card_instance_id),
                            ("crysknife", crysknives),
                            ("player", player),
                            ("spice", spice),
                            ("troops", recruited),
                        ),
                    ),
                    *recruit_shortfall,
                ),
            )
    elif effect is PersonalCardAgentEffect.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT:
        if owner.commanders_conflict >= 1:
            raise RuntimeError("Agent-card trash effect requires a player choice")
        # Ruthless Leadership without a Sardaukar Commander in the Conflict,
        # judged now (OQ-028): the box resolves without effect.
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE:
        raise RuntimeError("Agent-card Influence effect requires a player choice")
    elif effect is PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD:
        if owner.hand:
            raise RuntimeError("Agent-card discard effect requires a player choice")
        # Guild Envoy's mandatory discard has no card to take when it
        # resolves: the effect completes without a choice (OQ-028).
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    else:
        raise NotImplementedError(
            f"personal-card Agent effect is not implemented: {card.card.card_id}"
        )
    players = replace_player(state.players, next_owner)
    context["pending_agent_effect"] = False
    space_id_value = context.get("space_id")
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:"
            f"agent_card:{card_instance_id}"
        ),
        kind=event_kind,
        payload=(("card_id", card_instance_id), ("player", player)),
    )
    if effect is PersonalCardAgentEffect.EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY:
        if not isinstance(space_id_value, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        losses = opponent_unit_loss_frames(next_state, player, source=event_source)
        moves = turn_space_spy_frames(
            losses.state, player, space_id_value, source=event_source
        )
        return RuleResult(
            state=moves.state, events=(event, *losses.events, *moves.events)
        )
    if effect in (
        PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT,
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
        PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO,
        PersonalCardAgentEffect.DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN,
        PersonalCardAgentEffect.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND,
        PersonalCardAgentEffect.DRAW_TWO_IF_ONE_MARKER,
        PersonalCardAgentEffect.DRAW_TWO_CARDS,
        PersonalCardAgentEffect.DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO,
    ):
        if effect is PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT:
            draw_count = owner.sandworms_conflict
        elif effect in (
            PersonalCardAgentEffect.DRAW_TWO_IF_ONE_MARKER,
            PersonalCardAgentEffect.DRAW_TWO_CARDS,
        ):
            draw_count = 2
        elif (
            effect
            is PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO
        ):
            draw_count = min(len(owner.completed_contract_ids) // 2, 2)
        else:
            draw_count = 1
        if draw_count == 0 or event_kind == "agent_card_effect_unavailable":
            return RuleResult(state=next_state, events=(event, *recruit_shortfall))
        draw = draw_or_request_personal_cards(
            next_state,
            player,
            draw_count,
            source=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card.card.card_id}"
            ),
        )
        return RuleResult(
            state=draw.state, events=(event, *draw.events, *recruit_shortfall)
        )
    return RuleResult(state=next_state, events=(event, *recruit_shortfall))


def resolve_faction_influence(state: GameState) -> RuleResult:
    """Gain the visited Faction's Influence and resolve crossed boundaries."""

    _, context = current_agent_effect_context(state)
    if context["pending_faction_influence"] is not True:
        raise ValueError("the current Agent turn has no pending Faction Influence")
    player, _, space_id = _effect_subject(context)
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is None:
        raise RuntimeError("pending Faction Influence requires a Faction space")

    gained = gain_faction_influence(
        state,
        player,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:player:{player}:influence:{faction.value}"
        ),
    )
    context["pending_faction_influence"] = False
    next_state = advance_after_effect(
        gained.state,
        context,
        gained.state.players,
    )
    return RuleResult(state=next_state, events=gained.events)


def spice_gained_this_turn(owner: PlayerState) -> int:
    """Return the spice the seat gained since its turn opened, before spending.

    ``spice_at_turn_start`` is snapshotted when the turn frame opens and
    every spend adds to ``spice_spent_turn``, so gains from any source count
    (the same reading the Intrigue DSL uses for "gained N spice this turn").
    """

    return owner.resources.spice - owner.spice_at_turn_start + owner.spice_spent_turn


def _effect_subject(context: dict[str, bool | int | str]) -> tuple[int, str, str]:
    player = context["turn_owner"]
    card_id = context["card_id"]
    space_id = context["space_id"]
    if (
        isinstance(player, bool)
        or not isinstance(player, int)
        or not isinstance(card_id, str)
        or not isinstance(space_id, str)
    ):
        raise RuntimeError("Agent-turn effect frame has invalid subject")
    return player, card_id, space_id



def _owner_is_spying_on_visited_space(
    state: GameState,
    player: int,
    context: dict[str, ActionValue],
) -> bool:
    space_id = context.get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Agent-turn effect frame has invalid space")
    occupied = frozenset(state.players[player].spy_post_ids)
    return any(
        space_id in post.connected_space_ids and post.post_id in occupied
        for post in OBSERVATION_POSTS
    )
