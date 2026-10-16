"""Resolution of starting-card and Faction Agent-turn effects.

An Agent box that prints several independent icons (for example Hidden
Missive's troop and card draw) resolves them one action each in the owner's
order [Main p. 9] (OQ-027): ``resolve_agent_card_effect`` carries the icon's
``effect`` key, while icons that need a choice (Steersman's recall, Dangerous
Rhetoric's Faction) keep their dedicated actions. Arrow boxes pay their cost
first and then queue the reward icons the same way.
"""

from collections.abc import Callable, Mapping
from copy import replace
from types import MappingProxyType
from typing import Final

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.uprising.abilities import Ability, AbilityMark
from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.effect_dsl import (
    CompleteContract,
    ForceEnemyRetreat,
    GainInfluence,
    GrantCombatDeployment,
    PlaceSpy,
)
from dune_imperium.content.uprising.personal_cards import (
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import (
    BattleIcon,
    PersonalCardAgentEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.agent_box_abilities import (
    NOT_PRINTED_BLOCK,
    AgentIconBlock,
    AgentIconCondition,
    AgentPaymentBlock,
    agent_spy_rows,
    apply_chosen_influence,
    apply_discard,
    apply_either_influence,
    apply_intrigue_payment,
    apply_lose,
    apply_payment,
    apply_trash,
    box_ability,
    box_icon_block,
    discard_box,
    discard_cost_block,
    discard_rows,
    discard_spy,
    either_box,
    either_choice,
    either_rows,
    intrigue_box,
    intrigue_cost_block,
    intrigue_rows,
    lose_box,
    lose_cost_block,
    lose_rows,
    optional_arrow,
    payment_box,
    payment_cost_block,
    payment_reward_block,
    payment_rows,
    resolve_box,
    resolve_box_icon,
    target_blocked,
    target_piece,
    target_rows,
    trash_block,
    trash_box,
    trash_rows,
    trashes_remaining,
)
from dune_imperium.rules.agent_icons import effective_agent_icons
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.card_discard import (
    discard_personal_card_from_hand,
    resolve_personal_card_discard_trigger,
)
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import keep_trash_recruits as _keep_trash_recruits
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.combat import face_up_battle_icons
from dune_imperium.rules.combat_deployment import (
    grant_combat_icon,
)
from dune_imperium.rules.contracts import (
    complete_contract_by_effect,
)
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    advance_after_effect,
    agent_card_source,
    borrowed_agent_card,
    current_agent_effect_context,
    drop_boost_draw,
    finish_agent_icon,
    is_grafted,
    other_grafted_card_id,
    pending_agent_icons,
    pending_boost_draws,
    recall_conflict_agent,
    recallable_conflict_agents,
    recruit_shortfall_events,
    recruit_troops,
    short_of,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    with_context,
)
from dune_imperium.rules.graft_boxes import (
    active_box,
    box_card_id,
    box_is_pending,
    is_grafted_turn,
    row_box,
    state_with_active_box,
    tagged,
)
from dune_imperium.rules.immortality import (
    advance_research,
    advance_tleilaxu,
    tleilaxu_track_finished,
)
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    gain_faction_influence,
    influence_amount,
    influence_can_rise,
)
from dune_imperium.rules.intrigue_deck import (
    draw_or_queue_intrigue_cards,
)
from dune_imperium.rules.leader_abilities import (
    apply_kota_signet_action,
    legal_leader_signet_actions,
    resolve_leader_signet,
    units_deployment_blocked,
)
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.planetologist import replace_sandworms, replaces_sandworms
from dune_imperium.rules.shield_wall import (
    current_conflict_is_shield_wall_protected,
    destroy_shield_wall,
)
from dune_imperium.rules.specimens import generate_specimens
from dune_imperium.rules.spy_moves import spy_placement_frame
from dune_imperium.rules.spy_placement import (
    place_spy,
    recall_spy,
)
from dune_imperium.rules.units import retreat_units

# Immortality boxes whose enum names do not fit a comparison line.
_RESEARCH_AND_TRASH_FOR_VP = (
    PersonalCardAgentEffect.RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS
)
# The card instances whose Scientific Breakthrough box already did its
# Research this turn. Keyed by card, not by the frame, because a Ghola
# grafted to it copies the box and each box researches once.
_RESEARCHED_BOXES: Final = "research_resolved_card_ids"
# Set once a box's "gain two Influence instead of one" has replaced the
# visited space's own Influence (Subversive Advisor, Treacherous Maneuver):
# the space's 1 never comes back after that (``_release_space_influence``).
_SPACE_INFLUENCE_REPLACED: Final = "space_influence_replaced"
_SOLARI_PER_PARTNER_ICON = (
    PersonalCardAgentEffect
    .GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU
)
_CHOOSE_TWO_REWARDS = PersonalCardAgentEffect.CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU
_TRASH_GRAFTED_FOR_INFLUENCE = (
    PersonalCardAgentEffect.TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE
)
_LOSE_TROOP_FOR_CARDS = PersonalCardAgentEffect.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH
# Control the Spice (Epic Game Mode starting card): "[1 spice] -> [trash a
# card] [troop]" [card face] [Rise of Ix p. 10]; its record names the hook.
CONTROL_THE_SPICE_PRICE: Final = 1
# Branching Path (Uprising card face, re-read 2026-09-19): the Agent box's
# arrow cost trashes an Intrigue card from hand, not a personal card.
_BRANCHING_PATH = (
    PersonalCardAgentEffect
    .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
)
# Stitched Horror's four printed rewards, in card order.
STITCHED_HORROR_REWARDS: Final = ("water", "troop", "trash", "tleilaxu")
SLIG_FARMER_PRICE: Final = 5

# Agent-box icon keys resolved by ``resolve_agent_card_effect`` with
# ``effect=<key>``. Kept sorted: the action codec enumerates them.
AGENT_ICON_CARDS: Final = "cards"
# A box's second, separately conditioned card-draw line (Cargo Runner's
# "If you have completed four or more contracts: [draw 1]").
AGENT_ICON_CARDS_SECOND: Final = "cards_second"
AGENT_ICON_INTRIGUE: Final = "intrigue"
AGENT_ICON_PLEDGE: Final = "pledge"  # Pivotal Gambit's first-place Influence
# Industrial Espionage's "If grafted: [Research] [specimen]" line.
AGENT_ICON_RESEARCH: Final = "research"
# Stillsuit Manufacturer's "[Fremen] Alliance: Return this card from play to
# your hand."
AGENT_ICON_RETURN_SELF: Final = "return_self"
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
    AGENT_ICON_CARDS_SECOND,
    AGENT_ICON_INTRIGUE,
    AGENT_ICON_PLEDGE,
    AGENT_ICON_RESEARCH,
    AGENT_ICON_RETURN_SELF,
    AGENT_ICON_SOLARI,
    AGENT_ICON_SPICE,
    AGENT_ICON_TRASH_SELF,
    AGENT_ICON_TROOPS,
    AGENT_ICON_WATER,
)
# Icon keys resolved through a card's dedicated choice actions.
AGENT_ICON_INFLUENCE: Final = "influence"  # Dangerous Rhetoric: chosen Faction
AGENT_ICON_RECALL: Final = "recall"  # Steersman: one Agent to recall
# Tread in Darkness: its optional black trash icon (``trash_agent_card`` or
# ``decline_agent_card_trash``).
AGENT_ICON_TRASH: Final = "trash"

# Leaders whose Signet Ring ability prints several independent icons: the
# Signet Ring card's box (or a Ghola copying it) queues them like a card's
# box (OQ-027). A Servo-Receivers use of the ability has no Agent box and
# keeps resolving at once (``leader_abilities._resolve_leader_signet``).
_FILL_COFFERS_LEADER: Final = "lady_amber_metulli"
_SIGNET_ICONS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        # Fill Coffers: "[1 Solari] —AND— If you have an Alliance: [1 spice]"
        # [Lady Amber Metulli card]; the spice waits for an Alliance formed
        # later in the turn (OQ-028, OQ-057 (1)).
        _FILL_COFFERS_LEADER: (AGENT_ICON_SOLARI, AGENT_ICON_SPICE),
    }
)

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
    recorded = box_ability(effect)
    if recorded is not None and discard_box(recorded):
        # A discard arrow, from its record (composed A3d).
        return discard_rows(state, player, recorded)
    return ()


def apply_agent_card_discard(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or discard one hand card, then resolve its conditional draw."""

    if action not in legal_agent_card_discard_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card discard choice")
    _, context = current_agent_effect_context(state)
    recorded = box_ability(active_agent_card(context).agent_effect)
    if recorded is not None and discard_box(recorded):
        return apply_discard(state, action, recorded)
    raise RuntimeError(
        f"Agent-card discard has no handler: {active_agent_card(context).agent_effect}"
    )


def long_live_fighters_frame(
    player: int,
    source: str,
    source_card_id: str,
) -> DecisionFrame:
    """Return the frame holding Long Live the Fighters' two-step pick.

    The pick is one atomic card effect, so it gets its own frame: while it is
    open the Agent effect frame is not on top of the stack and therefore
    offers nothing, which is what keeps the two choices from being split by
    another freely ordered effect.
    """

    return DecisionFrame(
        kind=FrameKind.LONG_LIVE_FIGHTERS,
        frame_id=f"{source}:pick",
        decision=PlayerDecision(
            owner=player, prompt="Choose the card to draw, then the one to discard"
        ),
        context=(
            ("player", player),
            ("source", source),
            ("source_card_id", source_card_id),
        ),
    )


def legal_agent_card_long_live_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Long Live the Fighters' two private top-card choices.

    The frame is pushed only once the Agent effect has explicitly started
    resolving, so the free ordering of the board, Faction, and card effect
    groups is preserved and the three-card requirement is checked at the
    point of resolution.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    frame = owned_top_frame(state, FrameKind.LONG_LIVE_FIGHTERS, player)
    if frame is None:
        return ()
    context = dict(frame.context)

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
    player = action.actor
    frame = state.decision_stack[-1]
    frame_context = dict(frame.context)
    source = context_str(
        frame_context, "source", owner="Long Live the Fighters frame"
    )
    source_card_id = context_str(
        frame_context, "source_card_id", owner="Long Live the Fighters frame"
    )
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Long Live the Fighters choice has invalid card ID")

    if action.action_id == _LONG_LIVE_DRAW_ACTION_ID:
        frame_context[_LONG_LIVE_DRAW_CARD_ID] = card_id
        return RuleResult(
            state=replace(
                state,
                decision_stack=(
                    *state.decision_stack[:-1],
                    with_context(frame, frame_context),
                ),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:selection_started",
                    kind="long_live_fighters_selection_started",
                    payload=(("player", player),),
                ),
            ),
        )

    draw_card_id = frame_context.get(_LONG_LIVE_DRAW_CARD_ID)
    if not isinstance(draw_card_id, str):
        raise RuntimeError("Long Live the Fighters frame is missing its draw card")
    # The pick is done: close its frame so the Agent effect frame is on top
    # again for the shared trash transition and the effect advance.
    state = replace(state, decision_stack=state.decision_stack[:-1])
    _, context = current_agent_effect_context(state)
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

    # Stage the printed draw and discard moves first, then resolve the
    # discarded card's own discard trigger. A deck discard triggers it as a
    # project convention (OQ-013, user ruling 2026-10-04), although the
    # official text reads "Only discarding it from your hand triggers the
    # ability." [Main p. 17]. The trigger opens no decision, so the whole
    # printed sentence stays one atomic effect. The remaining card stays in
    # the deck for the shared trash transition, so a trash trigger observes
    # the same zones as the completed printed order.
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
    discard_triggered = resolve_personal_card_discard_trigger(
        staged_state, player, card_id, source=source
    )
    trashed = trash_personal_card(
        discard_triggered.state,
        player,
        trash_card_id,
        source=source,
        allow_deck=True,
    )
    _keep_trash_recruits(context, trashed)
    next_owner = trashed.state.players[player]
    context["pending_agent_effect"] = False
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
        events=(
            discard_event,
            *discard_triggered.events,
            *trashed.events,
            resolved_event,
        ),
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
    # Long Reach in play does not count as its own "another Bene Gesserit
    # card in play" [Long Reach card].
    return len(
        effective_agent_icons(
            partner_card,
            owner,
            grafted=True,
            opponents=opponents,
            card_instance_id=partner,
        )
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
    # A gain on a cube at the top of its track is lost (OQ-060), so no
    # picker below offers such a Faction. With none left the box's plain
    # resolution pays the rest (Southern Faith's draw, Possible Futures'
    # troops, Interstellar Conspiracy's spice), or else the box waits for
    # the turn's end (``resolve_agent_card_effect``, OQ-057 (1)).
    recorded = box_ability(effect)
    if isinstance(target_piece(recorded), GainInfluence):
        # A chosen Faction's Influence, from its record (composed A3c).
        assert recorded is not None
        return target_rows(state, player, recorded)
    if (
        recorded is not None
        and either_box(recorded)
        and isinstance(either_choice(recorded), GainInfluence)
    ):
        # Southern Faith, Interstellar Conspiracy (composed A3f).
        return either_rows(state, player, recorded)
    rising = tuple(
        faction
        for faction in Faction
        if influence_can_rise(state.players[player], faction)
    )
    if _is_possible_futures(recorded):
        # Possible Futures: without the Bond it is a choice between the
        # Influence and the two troops; with it the Influence choice pays
        # both.
        owner = state.players[player]
        bond = has_faction_bond(
            counted_in_play(owner), source_card_id, Faction.BENE_GESSERIT
        )
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
                for faction in rising
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
            for faction in rising
            if faction.value not in chosen
        )
    if effect is not PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE:
        return ()
    if AGENT_ICON_INFLUENCE not in pending_agent_icons(context):
        return ()
    return tuple(
        DomainAction(
            action_id="choose_agent_card_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in rising
    )


def agent_box_influence_blocked(state: GameState, player: int) -> bool:
    """Whether the pending Agent box's "choose a Faction" has no cube to raise.

    Interstellar Trade's and For Humanity's Influence, Public Spectacle's
    once a Spy was recalled, and Long Reach's next pick: every Faction they
    may raise is at the top, where a gain is lost (OQ-060), so the box
    waits for the turn's end (OQ-057 (1)). The page names this reason for
    the waiting box (``display.unavailable``).
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if context.get("pending_agent_effect") is not True:
        return False
    effect = active_agent_card(context).agent_effect
    recorded = box_ability(effect)
    if recorded is not None and isinstance(target_piece(recorded), GainInfluence):
        # Interstellar Trade, For Humanity, Public Spectacle: their records.
        return target_blocked(state, player, recorded)
    if effect is PersonalCardAgentEffect.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE:
        return not legal_agent_card_influence_actions(state, player)
    return False


def apply_agent_card_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve the current Agent card's selected Faction Influence."""

    if action not in legal_agent_card_influence_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Influence choice")
    _, context = current_agent_effect_context(state)
    recorded = box_ability(active_agent_card(context).agent_effect)
    if isinstance(target_piece(recorded), GainInfluence):
        return apply_chosen_influence(state, action)
    if recorded is not None and either_box(recorded):
        return apply_either_influence(state, action, recorded)
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
        # until the second, different Faction is chosen. When no second
        # Faction can rise any more (every other cube at the top, OQ-060),
        # the one named is paid at once and the second is lost, so the owner
        # can use the gain in the rest of the turn (user ruling 2026-10-08,
        # "앱처럼 즉시"; the Steam app gives that one track its +1 as soon as
        # the ability is used -- secondary evidence, not an official rule).
        chosen_value = context.get("influence_chosen", "")
        chosen = [
            *(str(chosen_value).split(",") if chosen_value else []),
            faction.value,
        ]
        owner_now = state.players[action.actor]
        second_possible = any(
            influence_can_rise(owner_now, other) and other.value not in chosen
            for other in Faction
        )
        waiting = len(chosen) < 2 and second_possible
        # The picks belong to this box; they move with it when the other
        # grafted box is made active (``graft_boxes.swap_boxes``), so a
        # second Long Reach box of the turn (Ghola copying it, OQ-057 (12))
        # names its own two Factions.
        context["influence_chosen"] = ",".join(chosen)
        context["pending_agent_effect"] = waiting
        if waiting:
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
    if _is_possible_futures(recorded):
        # With the Bond the Influence choice also pays the two troops.
        owner = players[action.actor]
        if has_faction_bond(
            counted_in_play(owner), source_card_id, Faction.BENE_GESSERIT
        ):
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
    recorded = box_ability(active_agent_card(context).agent_effect)
    if recorded is None or not isinstance(target_piece(recorded), CompleteContract):
        return ()
    return target_rows(state, player, recorded)


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
    # A Recall Agent reward may not take back the Agent this turn sent
    # [Main p. 20], as for a Contract completed by its own space, whether it
    # is still on the board or Into the Fray moved it to the Conflict
    # (OQ-068).
    turn_space_id = context.get("space_id")
    reward_turn_agent_in_conflict = isinstance(
        turn_space_id, str
    ) and turn_agent_in_conflict(
        state.players[action.actor], context, turn_space_id
    )
    completed = complete_contract_by_effect(
        state,
        action.actor,
        instance_id,
        source=source,
        excluded_space_id=turn_space_id if isinstance(turn_space_id, str) else "",
        turn_agent_in_conflict=reward_turn_agent_in_conflict,
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
    """Return placement, recall, or decline choices for an Agent-box Spy icon.

    The rows and their rules are ``agent_box_abilities.agent_spy_rows``'s:
    a placement while a Spy is in the supply, else the recall-first and its
    pass-up [Main pp. 11, 20], OQ-057 (14).
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
    source_card = active_agent_card(context)
    recorded = box_ability(source_card.agent_effect)
    if recorded is not None and isinstance(target_piece(recorded), PlaceSpy):
        # Bene Gesserit Operative, Reliable Informant, Double Agent: from
        # their records (composed A3c).
        return target_rows(state, player, recorded)
    if (
        recorded is not None
        and discard_box(recorded)
        and context.get("agent_card_spy_pending") is True
        and (spy := discard_spy(recorded)) is not None
    ):
        # Arrakis Observer's Spy with Deep Cover after its paid discard:
        # opponents' Spies may be ignored, never one's own [Bloodlines
        # pp. 5, 12].
        return agent_spy_rows(state, player, spy, context)
    return ()


def apply_agent_card_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve a card's place-Spy effect, recalling first or passing it up."""

    if action not in legal_agent_card_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Spy choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:agent_card:{source_card_id}"
    )

    if action.action_id == "decline_agent_card_spy":
        # No Spy in supply and the recall-first passed up [Main pp. 11, 20]:
        # the box resolves without a Spy and the Agent turn goes on.
        context["pending_agent_effect"] = False
        context.pop("agent_card_spy_pending", None)
        return RuleResult(
            state=advance_after_effect(state, context, state.players),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_unavailable",
                    kind="spy_placement_unavailable",
                    payload=(("card_id", source_card_id), ("player", action.actor)),
                ),
            ),
        )

    post_id = dict(action.arguments).get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("Agent-card Spy choice has invalid post ID")

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
    # A second Spy box this turn (a graft partner, Ghola's copy) starts
    # without a recall-first of its own.
    context.pop("agent_card_spy_recalled", None)
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


def _recall_icon_context(
    state: GameState, player: int
) -> dict[str, ActionValue] | None:
    """``player``'s own Agent-effect context while its recall icon is pending."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if context.get("pending_agent_effect") is not True:
        return None
    if AGENT_ICON_RECALL not in pending_agent_icons(context):
        return None
    return context


def agent_card_recall_targets(state: GameState, player: int) -> tuple[str, ...] | None:
    """Where ``player``'s pending Recall Agent icon (Steersman) may take an Agent.

    None unless that icon is pending on the seat's own Agent-effect frame
    (Twisted Mentat's optional recall of the Agent sent this turn has its
    own answer). The targets are the seat's other board spaces ("Return one
    of your other Agents on the board to your Leader (not the Agent you sent
    during this turn)." [Main p. 20]) and "conflict" for an earlier turn's
    Into the Fray Agent (OQ-037 (d), OQ-068). The provider offers one recall
    per target. With none the icon offers nothing and fizzles at the turn's
    end (OQ-057 (1)); the page greys it out with this same answer while the
    turn is open (user ruling 2026-10-02, L2-Q3 (3): "③은 회색 줄만").
    """

    context = _recall_icon_context(state, player)
    if (
        context is None
        or active_agent_card(context).agent_effect
        is PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN
    ):
        return None
    _, _, turn_space_id = _effect_subject(context)
    owner = state.players[player]
    return (
        *(
            space_id
            for space_id in owner.agent_locations
            if space_id != turn_space_id
        ),
        *(
            ("conflict",)
            if recallable_conflict_agents(
                owner,
                sent_this_turn=turn_agent_in_conflict(owner, context, turn_space_id),
            )
            > 0
            else ()
        ),
    )


def legal_agent_card_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Agent locations that Steersman may recall."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    context = _recall_icon_context(state, player)
    if context is None:
        return ()
    _, source_card_id, turn_space_id = _effect_subject(context)
    owner = state.players[player]
    if (
        active_agent_card(context).agent_effect
        is PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN
    ):
        # Twisted Mentat: "You may recall the Agent you sent this turn."
        # [Twisted Mentat card]; Into the Fray may have already moved that
        # very Agent into the Conflict, where it is still "the Agent you
        # sent this turn" (2026-09-26 user ruling, OQ-068).
        locations = tuple(
            space_id
            for space_id in owner.agent_locations
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
            *(
                (
                    DomainAction(
                        action_id="recall_conflict_agent_for_agent_card",
                        actor=player,
                    ),
                )
                if turn_agent_in_conflict(owner, context, turn_space_id)
                and owner.agent_in_conflict > 0
                else ()
            ),
        )
    # The Recall Agent icon: "Return one of your other Agents on the board to
    # your Leader (not the Agent you sent during this turn)." [Main p. 20].
    # An earlier turn's Into the Fray Agent in the Conflict is one of the
    # "other" Agents too (OQ-037 (d)), extended to every Recall Agent effect
    # by the 2026-09-26 user ruling (OQ-068). With nothing recallable the
    # icon offers nothing; the box then waits for the turn's end and fizzles
    # there (OQ-057 (1)), shown greyed out meanwhile (no window: user ruling
    # 2026-10-02, L2-Q3 (3)).
    return tuple(
        DomainAction(action_id="recall_conflict_agent_for_agent_card", actor=player)
        if target == "conflict"
        else DomainAction(
            action_id="recall_agent_for_agent_card",
            actor=player,
            arguments=(("space_id", target),),
        )
        for target in agent_card_recall_targets(state, player) or ()
    )


def apply_agent_card_recall(state: GameState, action: DomainAction) -> RuleResult:
    """Recall one Agent for Steersman's recall icon."""

    if action not in legal_agent_card_recall_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card recall choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, turn_space_id = _effect_subject(context)
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
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    if action.action_id == "recall_conflict_agent_for_agent_card":
        owner = state.players[action.actor]
        next_owner, recall_event = recall_conflict_agent(
            owner,
            player=action.actor,
            source=source_card_id,
            event_id=f"{source}:agent_recalled:conflict",
            # Match the board branch's payload shape below, keyed by
            # ``card_id`` rather than ``source`` (review round 2 finding).
            source_key="card_id",
        )
        finish_agent_icon(context, AGENT_ICON_RECALL)
        if (
            active_agent_card(context).agent_effect
            is PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN
        ):
            # Twisted Mentat recalled "the Agent you sent this turn"
            # [Twisted Mentat card] straight from the Conflict (OQ-068);
            # every Agent left there is an earlier turn's and one of
            # Imperial Privilege's "other Agents" [Board Guide p. 2]
            # (OQ-037 (d)); board_effects reads this mark.
            context["turn_agent_recalled"] = True
        next_state = advance_after_effect(
            state,
            context,
            replace_player(state.players, next_owner),
        )
        return RuleResult(state=next_state, events=(recall_event,))
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
    if space_id == turn_space_id:
        # Twisted Mentat: "You may recall the Agent you sent this turn."
        # [Twisted Mentat card]. This turn's Agent is home, not Into the
        # Fray, so every Agent left in the Conflict is an earlier turn's and
        # one of Imperial Privilege's "other Agents" [Board Guide p. 2]
        # (OQ-037 (d)); board_effects reads this mark.
        context["turn_agent_recalled"] = True
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
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
    recorded = box_ability(active_agent_card(context).agent_effect)
    if recorded is None or not isinstance(target_piece(recorded), ForceEnemyRetreat):
        return ()
    return target_rows(state, player, recorded)


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
    icons = pending_agent_icons(context)
    if icons and AGENT_ICON_TRASH not in icons:
        # The arrow cost is paid, or Tread in Darkness's trash icon is
        # resolved; only the queued reward icons remain.
        return ()
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    if source_card.agent_effect is _TRASH_TO_DRAW_IF_BOND and not (
        agent_icon_condition_holds(
            state.players[player], context, _TRASH_TO_DRAW_IF_BOND, AGENT_ICON_TRASH
        )
    ):
        # Tread in Darkness's trash icon without the Bond, judged now
        # (OQ-028): it waits like any conditioned icon (OQ-057 (1)).
        return ()
    recorded = box_ability(source_card.agent_effect)
    if recorded is not None and trash_box(recorded):
        # A trash box, from its record (composed A3e).
        return trash_rows(state, player, recorded)
    if source_card.agent_effect not in (
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND,
        PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE,
        PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON,
    ):
        return ()
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON
        and trashes_remaining(context) == 0
    ):
        # The Beast's Spoils resolves its automatic rewards first; only the
        # Crysknife trashes it counted are then offered one at a time.
        return ()
    return (
        DomainAction(action_id="decline_agent_card_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in _agent_card_trash_targets(state, player, context)
        ),
    )


# The Agent boxes whose optional trash ``legal_agent_card_trash_actions``
# offers card by card (Tread in Darkness's trash icon is a choice icon of
# its own, ``agent_icon_block``).
_TRASH_BOXES: Final = frozenset(
    {
        PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE,
        PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON,
    }
)
_TREACHEROUS_MANEUVER = (
    PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
)


def _treacherous_maneuver_block(
    owner: PlayerState, context: Mapping[str, ActionValue]
) -> OptionalEffectBlock | None:
    """Treacherous Maneuver's arrow without the Influence it would replace.

    "Gain two Influence instead of one" [Treacherous Maneuver card]
    replaces the visited space's own single gain, "기본 1 대신 총 2"
    [Main p. 9] (docs/rules/player-turns.md). The arrow is offered only
    while that gain is still pending: an Agent infiltrated onto a space
    without a Faction [Main p. 11] has no Influence to gain (OQ-046), and
    once the space's 1 is gained there is nothing left to replace. With the
    visited Faction at 5 or 6 the track's top (``MAX_INFLUENCE``) makes two
    instead of one end where the 1 would, so the two trashed cards would
    buy nothing: "비용이 있는 줄은 보상 중 하나라도 무언가를 바꿀 수 있을
    때만 제시한다" (OQ-071, user decision 2026-09-29).
    """

    space_id = context.get("space_id")
    visited_faction = (
        BOARD_SPACES_BY_ID[space_id].faction if isinstance(space_id, str) else None
    )
    if context.get("pending_faction_influence") is not True or visited_faction is None:
        return OptionalEffectBlock(OptionalBlockKind.NO_FACTION_GAIN)
    held = influence_amount(owner.influence, visited_faction)
    if held > MAX_INFLUENCE - 2:
        return OptionalEffectBlock(
            OptionalBlockKind.FACTION_NEAR_TOP, held=held, faction=visited_faction.value
        )
    return None


def _agent_card_trash_targets(
    state: GameState, player: int, context: dict[str, ActionValue]
) -> tuple[str, ...]:
    """The cards the active Agent box's trash may take now."""

    owner = state.players[player]
    effect = active_agent_card(context).agent_effect
    if effect is _TREACHEROUS_MANEUVER:
        if _treacherous_maneuver_block(owner, context) is not None:
            return ()
        _, source_card_id, _ = _effect_subject(context)
        return tuple(
            card_id
            for card_id in owner.hand
            if card_id != source_card_id
            and Faction.EMPEROR in personal_card_for_instance(card_id).factions
        )
    # A Row card borrowed with Usurp is not "in play" ("A grafted card in
    # the Imperium Row isn't considered to be 'in play.'" [Immortality
    # p. 14]), so it is no trash target (OQ-054, user ruling 2026-10-04).
    return (*owner.hand, *owner.discard_pile, *counted_in_play(owner))


def agent_card_trash_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why the active Agent box's optional trash offers no card now, or None.

    ``legal_agent_card_trash_actions`` offers Ruthless Leadership's trashes
    only with a Sardaukar Commander in the Conflict, and every box's trash
    for exactly the cards ``_agent_card_trash_targets`` names: none for
    Elite Forces with an empty hand, Pivotal Gambit once it left play, or
    Treacherous Maneuver without the Influence it replaces
    (``_treacherous_maneuver_block``) or another Emperor card in hand. None
    for a box with no such trash. The page greys an optional box that
    offers nothing out with it (``display.unavailable``, OQ-095 (2)).
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    effect = active_agent_card(context).agent_effect
    recorded = box_ability(effect)
    if recorded is not None and trash_box(recorded):
        return trash_block(state, player, recorded, context)
    if effect not in _TRASH_BOXES:
        return None
    owner = state.players[player]
    kind = OptionalBlockKind
    if effect is _TREACHEROUS_MANEUVER:
        block = _treacherous_maneuver_block(owner, context)
        if block is not None:
            return block
    if _agent_card_trash_targets(state, player, context):
        return None
    if effect is _TREACHEROUS_MANEUVER:
        return OptionalEffectBlock(kind.NO_EMPEROR_CARD)
    return OptionalEffectBlock(kind.NO_CARD_TO_TRASH)


def apply_agent_card_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve or decline an Agent-box personal-card trash choice."""

    if action not in legal_agent_card_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card trash choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    source_card = active_agent_card(context)
    source = f"round:{state.round_number}:player:{action.actor}:agent_card"
    if AGENT_ICON_TRASH in pending_agent_icons(context):
        return _resolve_trash_icon(state, action, context, source_card_id, source)
    recorded = box_ability(source_card.agent_effect)
    if recorded is not None and trash_box(recorded):
        return apply_trash(state, action, recorded)
    context["pending_agent_effect"] = False
    if action.action_id == "decline_agent_card_trash":
        context.pop("trashes_remaining", None)
        next_state = advance_after_effect(state, context)
        event = GameEvent(
            event_id=f"{source}:trash_declined",
            kind="agent_card_trash_declined",
            payload=(("player", action.actor),),
        )
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
    _keep_trash_recruits(context, trashed)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON
    ):
        remaining = trashes_remaining(context) - 1
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
        # The self-trash's own troops (none on a shipped card yet) survive
        # the write-back below, like the paid card's above.
        _keep_trash_recruits(context, source_trashed)
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("Treacherous Maneuver requires a Faction space")
        # One gain of 2 replaces the space's pending 1, so its thresholds
        # and Alliance resolve as for any two-step gain and the space's own
        # ``resolve_faction_influence`` step is used up.
        context["pending_faction_influence"] = False
        context[_SPACE_INFLUENCE_REPLACED] = True
        gained = gain_faction_influence(
            source_trashed.state,
            action.actor,
            faction,
            2,
            event_prefix=f"{source}:influence:{faction.value}",
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
    next_state = advance_after_effect(
        trashed.state,
        context,
        trashed.state.players,
    )
    return RuleResult(state=next_state, events=trashed.events)


def _resolve_trash_icon(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
    source_card_id: str,
    source: str,
) -> RuleResult:
    """Resolve or decline Tread in Darkness's trash icon on its own.

    "If you have another Bene Gesserit card in play: [trash] [draw 1]"
    [Tread in Darkness card] prints two icons and no arrow, so each is its
    own effect in the owner's order [Main p. 9] (OQ-027): the draw may come
    first and the card drawn may then be trashed. "검은색 trash 아이콘에 의한
    trash는 선택이지만, 비용으로 trash하거나 카드가 자기 자신을 trash하라고
    지시하면 선택이 아니다." [Main p. 20] (uprising-systems.md), so the trash
    may be declined and the draw still happens (OQ-058).
    """

    finish_agent_icon(context, AGENT_ICON_TRASH)
    if action.action_id == "decline_agent_card_trash":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:trash_declined",
                    kind="agent_card_trash_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card trash choice has invalid card ID")
    if card_id == source_card_id:
        # The card left play by its own printed icon, so its draw icon
        # still pays out (OQ-022, OQ-027).
        context["agent_card_self_trashed"] = True
    trashed = trash_personal_card(state, action.actor, card_id, source=source)
    _keep_trash_recruits(context, trashed)
    return RuleResult(
        state=advance_after_effect(trashed.state, context, trashed.state.players),
        events=trashed.events,
    )


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
    if pending_agent_icons(context):
        # Branching Path's arrow cost is paid; only its queued reward icons
        # remain (Junction Headquarters never reaches this: it always fully
        # resolves in one action).
        return ()
    _, source_card_id, _ = _effect_subject(context)
    recorded = box_ability(active_agent_card(context).agent_effect)
    if recorded is None or not intrigue_box(recorded):
        return ()
    # From its record (composed A3d): Branching Path, Junction Headquarters.
    return intrigue_rows(state, player, recorded)


def apply_agent_card_intrigue_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline, trash an Intrigue card, or pay two Spice and trash one for a VP.

    Branching Path trashes the Intrigue card alone as its arrow cost, then
    queues its own reward icons; Junction Headquarters pairs the trash with
    two Spice for one Victory Point instead.
    """

    if action not in legal_agent_card_intrigue_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Intrigue payment")
    _, context = current_agent_effect_context(state)
    recorded = box_ability(active_agent_card(context).agent_effect)
    assert recorded is not None and intrigue_box(recorded)
    return apply_intrigue_payment(state, action, recorded)


def agent_card_payment_block(
    state: GameState,
    player: int,
    effect: PersonalCardAgentEffect | None,
) -> AgentPaymentBlock | None:
    """Why ``effect``'s arrow would buy nothing for ``player`` now, or None.

    Judged when the box resolves, like the cost itself (OQ-028): a freely
    ordered effect of the same turn (a discard filling the discard pile)
    can still make the reward live.
    """

    ability = box_ability(effect)
    if payment_box(ability):
        assert ability is not None
        return payment_reward_block(state, player, ability)
    if effect is _SOLARI_PER_PARTNER_ICON and tleilaxu_track_finished(
        state.players[player]
    ):
        return AgentPaymentBlock.TLEILAXU_TRACK_END
    return None


_ARRAKIS_REVOLT = (
    PersonalCardAgentEffect
    .MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS
)


def _arrakis_revolt_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Arrakis Revolt's gate: Maker Hooks, the two spice, a Conflict, and a
    paid option left (``_arrakis_revolt_options``)."""

    owner = state.players[player]
    if not owner.maker_hooks:
        return OptionalEffectBlock(OptionalBlockKind.MAKER_HOOKS)
    spice = short_of(OptionalBlockKind.SPICE, 2, owner.resources.spice)
    if spice is not None:
        return spice
    if not state.current_conflict_ids:
        return OptionalEffectBlock(OptionalBlockKind.NO_CONFLICT)
    if not _arrakis_revolt_options(state, player):
        # No Shield Wall to remove, and no sandworm may deploy.
        return OptionalEffectBlock(OptionalBlockKind.DEPLOYMENT_BARRED)
    return None


def agent_card_cost_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why the active Agent box's optional cost cannot be paid now, or None.

    The gate the box's own provider applies before it offers the payment
    (``legal_agent_card_payment_actions``, ``legal_corrinth_city_payment_actions``,
    ``legal_agent_card_intrigue_payment_actions``,
    ``legal_agent_card_discard_actions``): each offers the payment exactly
    when this is None. Judged now, in the owner's chosen order (OQ-028): a
    freely ordered effect of the same turn may still pay it. None for a box
    with no such gate. The page greys an optional box that offers nothing
    out with it (``display.unavailable``, OQ-095 (2)).
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    owner = state.players[player]
    resources = owner.resources
    effect = active_agent_card(context).agent_effect
    kind = OptionalBlockKind
    if effect is _ARRAKIS_REVOLT:
        return _arrakis_revolt_block(state, player)
    ability = box_ability(effect)
    if payment_box(ability):
        assert ability is not None
        return payment_cost_block(owner, ability)
    if ability is not None and discard_box(ability):
        return discard_cost_block(owner, ability)
    if ability is not None and intrigue_box(ability):
        return intrigue_cost_block(owner, ability)
    if effect is PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN:
        partner = other_grafted_card_id(context)
        if not partner or partner not in owner.in_play:
            return OptionalEffectBlock(kind.NO_PARTNER)
        return None
    if effect is _RESEARCH_AND_TRASH_FOR_VP:
        return short_of(
            kind.GENETIC_MARKERS, 2, genetic_markers_reached(owner.research_space)
        )
    if ability is not None and lose_box(ability):
        return lose_cost_block(owner)
    if _is_control_the_spice(ability):
        return short_of(kind.SPICE, CONTROL_THE_SPICE_PRICE, resources.spice)
    if effect is PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP:
        return short_of(kind.SOLARI, 5, resources.solari) or short_of(
            kind.HAND, 2, len(owner.hand)
        )
    return None


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
    recorded = box_ability(source_card.agent_effect)
    if payment_box(recorded):
        # An optional arrow with no target, from its record (composed A3b).
        assert recorded is not None
        return payment_rows(state, player, recorded)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect
        .MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS
    ):
        return _arrakis_revolt_payment_actions(state, player)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN
    ):
        # Dissecting Kit: "Trash the other grafted card -> a specimen"
        # [card face]; without a partner still in play the box does nothing.
        if agent_card_cost_block(state, player) is not None:
            return ()
        return (
            DomainAction(action_id="decline_agent_card_payment", actor=player),
            DomainAction(action_id="trash_grafted_card_for_specimen", actor=player),
        )
    if (
        recorded is not None
        and either_box(recorded)
        and isinstance(either_choice(recorded), GrantCombatDeployment)
    ):
        # High Priority Travel: "[Guild] 2 Influence: draw a card —OR—
        # Combat" [card face], from its record (composed A3f).
        return either_rows(state, player, recorded)
    owner = state.players[player]
    if source_card.agent_effect is _RESEARCH_AND_TRASH_FOR_VP:
        # Scientific Breakthrough prints the Research icon and, on its own
        # line, "[2 genetic markers]: Trash this card -> 1 VP" [card face].
        # The line is judged when it resolves (OQ-028), so the card's own
        # Research, resolved first, may reach the second marker [Main p. 9].
        # Before the Research, the plain resolution is the Research; after
        # it, the line is an arrow cost the owner may decline.
        if agent_card_cost_block(state, player) is not None:
            return ()
        return (
            DomainAction(
                action_id=(
                    "decline_agent_card_payment"
                    if _box_researched(context, source_card_id)
                    else "resolve_agent_card_effect"
                ),
                actor=player,
            ),
            DomainAction(action_id="trash_agent_card_self_for_vp", actor=player),
        )
    if source_card.agent_effect is _SOLARI_PER_PARTNER_ICON:
        # Slig Farmer: the Solari land first, so they may pay the five; the
        # five are not offered once the advance would do nothing (OQ-071).
        if (
            owner.resources.solari + _partner_icon_count(state, context)
            < SLIG_FARMER_PRICE
            or agent_card_payment_block(state, player, source_card.agent_effect)
            is not None
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
        # "trash one of the grafted cards and gain an additional Influence"
        # has no "may", arrow or black-X icon, so it is mandatory [FAQ p. 3]:
        # the owner picks which card, never whether.
        _, _, space_id = _effect_subject(context)
        if BOARD_SPACES_BY_ID[space_id].faction is None or not is_grafted(context):
            return ()
        return tuple(
            DomainAction(
                action_id="trash_grafted_card_for_influence",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in (source_card_id, other_grafted_card_id(context))
            if card_id in owner.in_play
        )
    if recorded is not None and lose_box(recorded):
        # Piter, Genius Advisor, from its record (composed A3f).
        return lose_rows(state, player)
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
    if _is_control_the_spice(recorded):
        # Control the Spice: the arrow cost may be left unpaid and is chosen
        # once [Main p. 9] [FAQ p. 3]; like Smuggler's Haven's below it is
        # judged when the owner resolves the box in their chosen order
        # (OQ-028), so a spice gained first (Imperial Basin) pays it.
        decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
        if agent_card_cost_block(state, player) is not None:
            return (decline,)
        return (
            decline,
            DomainAction(action_id="pay_agent_card_spice", actor=player),
        )
    return ()


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
    if agent_card_cost_block(state, player) is not None:
        # The full cost (5 Solari, two cards in hand) must still be payable
        # when the player resolves the pending payment in their chosen
        # effect order [Main pp. 9, 20]; once it is unaffordable, only
        # skipping remains.
        return (DomainAction(action_id="decline_corrinth_city_payment", actor=player),)
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
    recorded = box_ability(active_agent_card(context).agent_effect)
    if payment_box(recorded):
        # An optional arrow with no target, from its record (composed A3b).
        assert recorded is not None
        return apply_payment(state, action.actor, recorded, context)
    if recorded is not None and lose_box(recorded):
        # Piter, Genius Advisor (composed A3f).
        return apply_lose(state, action, recorded, context, source)

    owner = state.players[action.actor]
    if action.action_id == "trash_grafted_card_for_specimen":
        # Dissecting Kit: the other grafted card leaves play; its
        # un-activated box expires with it (OQ-022 designer ruling).
        partner = other_grafted_card_id(context)
        held = _waiting_box_holds_space_influence(context)
        context["graft_pending_effect"] = False
        context["graft_pending_icons"] = ""
        _release_space_influence(context, held=held)
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
        # so its research still pays out (OQ-022) unless it already did;
        # the direction choice opens above the settled turn.
        card_instance_id = _effect_subject(context)[1]
        research_owed = not _box_researched(context, card_instance_id)
        context["agent_card_self_trashed"] = True
        trashed = trash_personal_card(
            state, action.actor, card_instance_id, source=f"{source}:trash"
        )
        _keep_trash_recruits(context, trashed)
        trashed_owner = trashed.state.players[action.actor]
        rewarded = replace(
            trashed_owner, victory_points=trashed_owner.victory_points + 1
        )
        next_state = advance_after_effect(
            trashed.state, context, replace_player(trashed.state.players, rewarded)
        )
        researched = (
            advance_research(
                next_state, action.actor, source=f"{source}:research"
            )
            if research_owed
            else RuleResult(state=next_state, events=())
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
            held = _waiting_box_holds_space_influence(context)
            context["graft_pending_effect"] = False
            context["graft_pending_icons"] = ""
            _release_space_influence(context, held=held)
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
    if action.action_id == "choose_agent_card_reward":
        return _apply_stitched_horror_reward(state, action, context, source)
    # The same borrowed box `[Immortality p. 14]`. The provider checks the
    # arrow's cost against the borrowed effect's own resource, so reading the
    # printed card here sent a Ghola down the other branch: it charged four
    # spice and a Victory Point for a box that asks two water and draws two
    # cards, and crashed outright when the seat could not pay in the resource
    # it was never asked for.
    if _is_control_the_spice(recorded):
        return _apply_control_the_spice_payment(state, action, context, source)
    raise RuntimeError(f"no Agent-card payment handles {action.action_id}")


_ARRAKIS_REVOLT_ACTION_IDS = frozenset(
    {
        "pay_agent_card_spice_for_sandworm",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
    }
)


def _arrakis_revolt_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Arrakis Revolt's arrow payment: 2 spice for the wall and a worm.

    "You may remove the Shield Wall" and the sandworm are the two icons after
    the arrow [Main p. 20]. The removal is optional, so paying while keeping
    the wall is offered only when the worm can still do something (the
    Conflict is not Shield Wall-protected); a summon that "does nothing"
    against a protected Conflict is not worth two spice (OQ-026). Arrakis
    Planetologist's replacement still pays behind the wall -- "(Even when
    the Conflict is protected by the Shield Wall.)" [Liet Kynes card] -- so
    Liet may pay and keep the wall there too. Under Emperor of the Known
    Universe ("Units can't be deployed to the Conflict this turn" [Shaddam
    Corrino IV card] [Main p. 17]) neither the worm nor Liet's replacement
    comes, so keeping the wall would buy nothing and is not offered either
    (OQ-026, project convention 2026-09-03: "2 spice로 아무것도 얻지 못하는
    선택은 규칙상 가능하더라도 행동 공간에서 뺀다"); removing the wall still
    does something and stays.
    """

    decline = DomainAction(action_id="decline_agent_card_payment", actor=player)
    if agent_card_cost_block(state, player) is not None:
        return (decline,)
    return (decline, *_arrakis_revolt_options(state, player))


def _arrakis_revolt_options(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Arrakis Revolt's paid options: none without the Shield Wall while
    Emperor of the Known Universe bars deployment (``_arrakis_revolt_block``)."""

    owner = state.players[player]
    actions: list[DomainAction] = []
    if state.shield_wall_present:
        actions.append(
            DomainAction(
                action_id="pay_agent_card_spice_for_sandworm_and_shield_wall",
                actor=player,
            )
        )
    if not units_deployment_blocked(state, player) and (
        replaces_sandworms(owner)
        or not current_conflict_is_shield_wall_protected(state)
    ):
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


def _apply_control_the_spice_payment(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
    source: str,
) -> RuleResult:
    """Pay Control the Spice's spice, recruit its troop, then offer its trash.

    "[1 spice] -> [trash a card] [troop]" [card face]. The black trash icon
    stays optional once the cost is paid ("검은색 카드 폐기 아이콘을 사용하지
    않는 경우에는 그 효과를 생략할 수 있다" [FAQ p. 3]) and "hand, discard
    pile, in play 가운데 카드 1장을 대상으로 한다" [Main p. 20], this card
    included. The two rewards are independent, so the box follows Throne Room
    Politics: the troop now, then the generic optional-trash frame. The
    troop is one recruited this turn, which a Combat space lets the owner
    deploy ("그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에
    deploy할 수 있다" [Main p. 10] [FAQ p. 4]).
    """

    player = action.actor
    _, card_instance_id, _ = _effect_subject(context)
    owner = state.players[player]
    paid_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            spice=owner.resources.spice - CONTROL_THE_SPICE_PRICE,
        ),
        spice_spent_turn=owner.spice_spent_turn + CONTROL_THE_SPICE_PRICE,
    )
    # "supply에 troop이 없으면 recruit할 수 없다" [Main p. 10].
    recruited_owner, recruited = recruit_troops(paid_owner, 1)
    context["troops_recruited"] = (
        context_int(context, "troops_recruited", owner="Agent-turn effect frame")
        + recruited
    )
    next_state = advance_after_effect(
        state, context, replace_player(state.players, recruited_owner)
    )
    box_source = f"{source}:{card_instance_id}"
    return RuleResult(
        state=next_state.push_decision(
            optional_trash_frame(player, box_source)
        ),
        events=(
            GameEvent(
                event_id=f"{box_source}:paid",
                kind="agent_card_payment_resolved",
                payload=(
                    ("player", player),
                    ("resource", "spice"),
                    ("spent", CONTROL_THE_SPICE_PRICE),
                    ("troops", recruited),
                ),
            ),
            *recruit_shortfall_events(box_source, player, 1, recruited),
        ),
    )


def _still_owned(owner: PlayerState, card_instance_id: str) -> bool:
    """Return whether the card still sits in a trash-eligible owned zone."""

    return card_instance_id in (*owner.hand, *owner.discard_pile, *owner.in_play)


def _left_play_by_own_effect(
    context: Mapping[str, ActionValue], card_instance_id: str
) -> bool:
    """Whether the played card left play through its own printed cost or
    icon, so its remaining printed rewards still pay out (OQ-022)."""

    if card_instance_id == context.get("card_id"):
        return context.get("agent_card_self_trashed") is True
    if card_instance_id == other_grafted_card_id(context):
        return context.get("graft_card_self_trashed") is True
    return False


def holds_space_influence(effect: PersonalCardAgentEffect | None) -> bool:
    """Return whether a waiting box of this effect holds the space's Influence.

    Subversive Advisor's "gain two Influence instead of one" [Subversive
    Advisor card] replaces the visited Faction space's own gain, so while
    its box waits the space's ``resolve_faction_influence`` step is not
    offered: the two never add up to 3 [Main pp. 9, 11, 20].
    """

    return (
        effect
        is PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF
    )


def _waiting_box_holds_space_influence(context: dict[str, ActionValue]) -> bool:
    """Return whether a still-pending box of the frame holds the space's gain."""

    graft_card_id = other_grafted_card_id(context)
    return (
        context.get("pending_agent_effect") is True
        and holds_space_influence(active_agent_card(context).agent_effect)
    ) or (
        context.get("graft_pending_effect") is True
        and bool(graft_card_id)
        and holds_space_influence(
            borrowed_agent_card(
                personal_card_for_instance(graft_card_id),
                context_str(context, "card_id", owner="Agent-turn effect frame"),
            ).agent_effect
        )
    )


def _release_space_influence(context: dict[str, ActionValue], *, held: bool) -> None:
    """Offer the space's Influence again once no waiting box holds it.

    ``held`` says whether a box held it before the change. When that box
    expires unresolved (OQ-022), only the card's "instead" lapses: "Faction
    space라면 그 Faction Influence도 1 얻는다." [Main p. 7] [Main p. 9], so
    the space's ordinary ``resolve_faction_influence`` step comes back.
    Once another box already gained two instead of one, the space's 1 was
    replaced and stays gone: "일반 Faction Influence를 별도로 더해 총 3을
    얻지 않는다" [Subversive Advisor card] [Main pp. 9, 11, 20]
    (docs/rules/player-turns.md).
    """

    if context.get(_SPACE_INFLUENCE_REPLACED) is True:
        return
    if held and not _waiting_box_holds_space_influence(context):
        context["pending_faction_influence"] = True


def expire_trashed_card_effects(result: RuleResult) -> RuleResult:
    """Expire a pending Agent box whose played card already left play.

    You can't receive or activate an effect from a card that is already
    trashed (OQ-022 designer ruling), so when a freely ordered effect
    trashes the played card before its Agent box is activated, the whole
    un-activated box expires instead of resolving.

    Only the card's own effect lapses: when the expired box held the
    space's Influence (Subversive Advisor), the space's own gain is offered
    again (``_release_space_influence``).
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
        # The partner's box was left after its card trashed itself by its
        # own icon (``graft_boxes.swap_boxes`` moves the flag with the box);
        # its remaining icons still pay out (OQ-022).
        and context.get("graft_card_self_trashed") is not True
        and not _still_owned(owner, graft_card_id)
    ):
        # The grafted partner's un-activated box expires the same way
        # (Beguiling Pheromones trashing it, FAQ p. 1).
        context["graft_pending_effect"] = False
        context["graft_pending_icons"] = ""
        expired.append(graft_card_id)
    for boost_card_id in pending_boost_draws(context):
        if _still_owned(owner, boost_card_id) or _left_play_by_own_effect(
            context, boost_card_id
        ):
            continue
        # Urgent Shigawire's draw was "added to its Agent box" [Urgent
        # Shigawire card], so it is that card's effect and lapses with its
        # box (OQ-022; user ruling 2026-10-10, OQ-106) -- a Ghola's copy of
        # it with the Ghola (OQ-107).
        drop_boost_draw(context, boost_card_id)
        if boost_card_id not in expired:
            expired.append(boost_card_id)
    if not expired:
        return result
    _release_space_influence(
        context, held=_waiting_box_holds_space_influence(dict(frame.context))
    )
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
    leader_id: str | None = None,
) -> tuple[str, ...]:
    """Return the icon keys an Agent box queues when its card is played.

    Empty for single-effect boxes and for arrow boxes, whose reward icons
    are queued once the cost is paid. The Signet Ring's box is its owner's
    Leader ability, so ``leader_id`` picks its icons (``_SIGNET_ICONS``).
    """

    if effect is None:
        return ()
    if effect is PersonalCardAgentEffect.LEADER_SIGNET:
        return _SIGNET_ICONS.get(leader_id or "", ())
    ability = box_ability(effect)
    # A box's printed icons come from its record; an arrow's are armed after
    # its cost.
    return ability.icons if ability is not None else ()


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
    owner = state.players[player]
    effect = active_agent_card(context).agent_effect
    return tuple(
        DomainAction(
            action_id="resolve_agent_card_effect",
            actor=player,
            arguments=(("effect", key),),
        )
        for key in pending_agent_icons(context)
        if key in AUTOMATIC_AGENT_ICONS
        and agent_icon_condition_holds(owner, context, effect, key)
    )


_BOOST_DRAW_ACTION_ARGUMENTS: Final = (("effect", AGENT_ICON_CARDS),)


def boost_draw_box(context: Mapping[str, ActionValue], card_instance_id: str) -> int:
    """The grafted box the added draw of ``card_instance_id`` belongs to.

    Box 1 when that card is the graft partner -- a Bene Gesserit partner
    that took the boost (user ruling 2026-10-12, OQ-107), or a Ghola
    grafted to the boosted placed card -- else box 0: the placed card, or a
    single-card turn.
    """

    if is_grafted_turn(context) and card_instance_id == box_card_id(context, 1):
        return 1
    return 0


def boost_draw_card(context: Mapping[str, ActionValue], box: int) -> str:
    """The card whose added draw waits in box ``box`` ("" if none)."""

    return next(
        (
            card
            for card in pending_boost_draws(context)
            if boost_draw_box(context, card) == box
        ),
        "",
    )


def legal_agent_card_boost_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer Urgent Shigawire's added draws, each as its own step.

    "The next Bene Gesserit card you play this round has all Agent icons
    and, added to its Agent box: draw a card." [Urgent Shigawire card]. The
    added draw is one more card-draw icon of the boosted card's box,
    resolved by ``resolve_agent_card_effect(effect=cards)`` in any order
    with the turn's other effects [Main p. 9]; whatever the box itself is
    (no box, one effect, an arrow, its own icons) it is unconditional. "그
    외에는 전부 나누자. 특히 카드 드로우는 나눠야하는게, 드로우 하기 전에
    버림더미 카드를 폐기하고 싶을 수 있잖아." (user ruling 2026-10-10,
    OQ-106): the placement no longer draws, so it stays undoable.

    Each row is its card's box's: untagged for box 0 (the placed card),
    ``box=1`` for the graft partner (OQ-107, ``boost_draw_box``). A Ghola
    grafted to the boosted card copies its box with the added draw ("Ghola
    copies the entire Agent box of the card it's grafted to" [Immortality
    p. 14]; user ruling 2026-10-12), so both boxes may hold one. While a
    box's own card-draw icon is offered too, its one row resolves the box's
    icon first (``resolve_agent_card_icon``); this provider offers the row
    only when the box does not, so it is never listed twice -- also while
    the box's rows wait for the other box to finish a bundled selection
    (``box_in_progress``), when the row is this added draw.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    draw = DomainAction(
        action_id="resolve_agent_card_effect",
        actor=player,
        arguments=_BOOST_DRAW_ACTION_ARGUMENTS,
    )
    rows: list[DomainAction] = []
    boxes = sorted(
        {boost_draw_box(context, card) for card in pending_boost_draws(context)}
    )
    for box in boxes:
        box_waits = (
            is_grafted_turn(context)
            and active_box(context) != box
            and box_in_progress(state)
        )
        if not box_waits and draw in legal_agent_card_icon_actions(
            state_with_active_box(state, box), player
        ):
            continue
        rows.append(tagged(draw, box))
    return tuple(rows)


def resolves_boost_draw(state: GameState, action: DomainAction) -> bool:
    """Whether ``action`` resolves one of Urgent Shigawire's added draws now.

    True for a ``resolve_agent_card_effect(effect=cards)`` that
    ``legal_agent_card_boost_actions`` offers: the box's own card-draw
    icon, when also offered, is resolved first by the same action.
    """

    return action in legal_agent_card_boost_actions(state, action.actor)


def _resolve_boost_draw(state: GameState, action: DomainAction) -> RuleResult:
    """Draw Urgent Shigawire's added card for the row's box."""

    _, context = current_agent_effect_context(state)
    player = action.actor
    card_instance_id = boost_draw_card(context, row_box(action))
    drop_boost_draw(context, card_instance_id)
    source = (
        f"round:{state.round_number}:player:{player}:shigawire:{card_instance_id}"
    )
    drawn = draw_or_request_personal_cards(
        advance_after_effect(state, context), player, 1, source=f"{source}:cards"
    )
    return RuleResult(
        state=drawn.state,
        events=(
            *drawn.events,
            GameEvent(
                event_id=f"{source}:cards:resolved",
                kind="agent_card_effect_resolved",
                payload=(
                    ("card_id", card_instance_id),
                    ("effect", AGENT_ICON_CARDS),
                    ("player", player),
                ),
            ),
        ),
    )


_NOT_PRINTED: Final = NOT_PRINTED_BLOCK


def agent_icon_block(
    owner: PlayerState,
    context: Mapping[str, ActionValue],
    effect: PersonalCardAgentEffect | None,
    key: str,
) -> AgentIconBlock | None:
    """Why an Agent-box icon's printed condition fails right now, or None.

    Hidden Missive (two Bene Gesserit Influence), Fremen War Name ("If you
    gained [2 spice] or more this turn:" [Fremen War Name card]), Sardaukar
    Quartermaster (grafted), Tleilaxu Infiltrator (two genetic markers),
    Maker Keeper and Wheels Within Wheels (Influence thresholds), Cargo
    Runner (two and four completed contracts, one line each), Tread in
    Darkness (another Bene Gesserit card in play, on its draw and on its
    optional trash), Industrial Espionage (grafted, on its Research and
    specimen line), Stillsuit Manufacturer (the Fremen Alliance, on its
    return) and Lady Amber Metulli's Fill Coffers (any Alliance, on its
    spice) print a condition on their icons. The condition is judged
    when the icon resolves (OQ-028), and while it is false the icon is not
    offered: a mandatory effect cannot be fired to fizzle, it waits for the
    turn's end and fizzles there (OQ-057 (1)). A later effect of the turn that
    meets the condition makes it resolvable, and then mandatory, again. The
    provider offers an icon exactly when this is None
    (``agent_icon_condition_holds``), and the page greys the others out with
    it while the turn is open (user ruling 2026-10-02, L2-Q3 (3)).
    """

    ability = box_ability(effect)
    if ability is not None and key in ability.icons:
        # A recorded box judges its printed icons from its record; a key it
        # does not print keeps the generic answer below.
        return box_icon_block(owner, context, ability, key)
    if key in (AGENT_ICON_CARDS_SECOND, AGENT_ICON_RETURN_SELF, AGENT_ICON_WATER):
        return _NOT_PRINTED
    if key == AGENT_ICON_RESEARCH:
        # Piter, Genius Advisor's reward, armed once its cost is paid.
        return None if effect is _LOSE_TROOP_FOR_CARDS else _NOT_PRINTED
    fill_coffers = (
        effect is PersonalCardAgentEffect.LEADER_SIGNET
        and owner.leader_id == _FILL_COFFERS_LEADER
    )
    if key == AGENT_ICON_SOLARI:
        return None if fill_coffers else _NOT_PRINTED
    if key == AGENT_ICON_SPICE:
        if effect is _BRANCHING_PATH:
            return None
        if fill_coffers:
            if owner.alliance_faction_ids:
                return None
            return AgentIconBlock(AgentIconCondition.ALLIANCE)
        return _NOT_PRINTED
    return None


def agent_icon_condition_holds(
    owner: PlayerState,
    context: Mapping[str, ActionValue],
    effect: PersonalCardAgentEffect | None,
    key: str,
) -> bool:
    """Return whether an Agent-box icon's printed condition holds right now
    (``agent_icon_block`` is None)."""

    return agent_icon_block(owner, context, effect, key) is None


def resolve_agent_card_icon(
    state: GameState, action: DomainAction, *, boost: bool = True
) -> RuleResult:
    """Resolve one printed icon of the played card's Agent box.

    A box written as an ability record resolves its printed icons in
    ``agent_box_abilities.resolve_box_icon``; this resolves the others'
    (Fill Coffers' gains, and an arrow box's armed rewards).
    An icon is offered only while its condition holds
    (``agent_icon_condition_holds``), judged when it resolves in the owner's
    order [Main pp. 7, 9]. Urgent
    Shigawire's added draw is bound to its card, not to a box's machinery:
    the engine routes it as no box's row (``agent_effect_frame.
    route_box_action``) and resolves it here; a row routed to box 1 is box
    1's own icon (``boost=False``).
    """

    if boost and resolves_boost_draw(state, action):
        return _resolve_boost_draw(state, action)
    if action in legal_leader_signet_actions(state, action.actor):
        # Reverse Engineering's reward icons after its Tech-tile cost, in
        # the Signet Ring's box or a Servo-Receivers frame (OQ-106).
        return apply_kota_signet_action(state, action)
    if action not in legal_agent_card_icon_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card icon resolution")
    _, context = current_agent_effect_context(state)
    player, card_instance_id, _ = _effect_subject(context)
    card = active_agent_card(context)
    effect = card.agent_effect
    recorded = box_ability(effect)
    if recorded is not None and recorded.icons:
        return resolve_box_icon(state, action)
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

    next_owner = owner
    effect_state = state
    # Only an icon whose printed condition holds is offered (see
    # ``agent_icon_condition_holds``); the check stays as a safety net.
    available = agent_icon_condition_holds(owner, context, effect, key)
    personal_draw_count = 0
    intrigue_draw_count = 0
    match key:
        case "cards":
            if available:
                # Piter, Genius Advisor's reward draws two cards.
                personal_draw_count = 2 if effect is _LOSE_TROOP_FOR_CARDS else 1
        case "intrigue":
            if available:
                intrigue_draw_count = 1
        case "troops":
            if available:
                next_owner = recruit(1)
        case "solari":
            if available:
                # Fill Coffers' 1 Solari (the Signet Ring's box).
                next_owner = gain(solari=1)
        case "spice":
            if available:
                # Branching Path's "[Intrigue card] [2 spice]" [Main p. 20];
                # Fill Coffers pays 1 spice.
                next_owner = gain(spice=2 if effect is _BRANCHING_PATH else 1)
        case "research":
            # Piter's Research follows the frame write-back below: it may
            # open its direction choice and bonus frames above the turn.
            pass
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
    research_events: tuple[GameEvent, ...] = ()
    if key == AGENT_ICON_RESEARCH and available and effect is _LOSE_TROOP_FOR_CARDS:
        # Piter, Genius Advisor's reward Research, after its cost (OQ-106).
        researched = advance_research(next_state, player, source=f"{source}:research")
        next_state = researched.state
        research_events = researched.events
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
        events=(
            *extra_events,
            *intrigue_events,
            *research_events,
            *draw_events,
            event,
        ),
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
    from dune_imperium.rules.agent_effect_frame import agent_box_can_resolve_by_choice

    if agent_box_can_resolve_by_choice(state, context_int(context, "turn_owner")):
        # A box resolved by a choice it still offers can resolve, so it is
        # not one that only fizzles and the turn end waits for it (OQ-057
        # (1), OQ-095 2). The generic resolution below is not its path and
        # would report it unavailable: Stitched Horror's "Choose two"
        # (OQ-057 (4)), Beguiling Pheromones' trash, the optional arrows of
        # Piter, Tleilaxu Surgeon and Dissecting Kit and Tleilaxu Master's
        # acquisition while they can be taken (OQ-058), and Ghola's copies.
        return False
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

    A multi-icon box resolves icon by icon through exactly four providers
    (OQ-027; the trash one for Tread in Darkness's trash icon), so when all
    four are empty the icons cannot be resolved at all. Ghola copying
    Steersman's "draw a card, recall an Agent" box reaches this: the first
    box already recalled the seat's last Agent, so the copy's recall icon
    has no target. Like any other mandatory box whose condition is false it
    now waits for the turn's end instead of stalling it (OQ-057), and a
    later effect that gives the icon a target makes it resolvable again.
    """

    player = context_int(context, "turn_owner")
    return not (
        legal_agent_card_icon_actions(state, player)
        or legal_agent_card_recall_actions(state, player)
        or legal_agent_card_influence_actions(state, player)
        or legal_agent_card_trash_actions(state, player)
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
    """Return whether every pending Agent box of the turn could only fizzle.

    With a graft each of the two boxes is judged with itself active
    (``graft_boxes.state_with_active_box``); the turn is stalled only when
    each box still pending would fizzle now (OQ-057 (1)), and not at all
    when no box is pending.
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    pending = tuple(box for box in (0, 1) if box_is_pending(context, box))
    return bool(pending) and all(
        agent_card_effect_is_unavailable(state_with_active_box(state, box))
        for box in pending
    )


# Agent boxes printed as an optional effect -- "you may", an arrow cost or a
# black trash icon [FAQ p. 3] (docs/rules/official-rulings-index.md
# "optional effects"). Until the owner uses one it offers no refusal: the
# turn's end is offered once every mandatory effect is done (OQ-095 (2)),
# and the press lapses an optional box left unused (user ruling 2026-10-14,
# "선택행동의 경우 거절 버튼이 왜 따로 있는거야 그럼?"). Once its cost is paid,
# an arrow's queued rewards are mandatory like any printed effect.
OPTIONAL_AGENT_BOXES: Final = frozenset(
    {
        PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE,
        PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP,
        PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS,
        PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN,
    }
)
# The optional icons of boxes resolved icon by icon (OQ-027): Tread in
# Darkness's black trash icon beside its mandatory draw, and Twisted Mentat's
# "You may recall the Agent you sent this turn".
OPTIONAL_AGENT_ICONS: Final[Mapping[PersonalCardAgentEffect, frozenset[str]]] = (
    MappingProxyType(
        {
            _TRASH_TO_DRAW_IF_BOND: frozenset({AGENT_ICON_TRASH}),
            PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN: frozenset(
                {AGENT_ICON_RECALL}
            ),
        }
    )
)
# Progress an optional box drops when it lapses.
_OPTIONAL_PROGRESS_KEYS: Final = (
    "trashes_remaining",
    "corrinth_first_card_id",
    "feyd_track_stage",
    "staban_bonus_post",
    "listeners_paid",
    "leader_spy_recalled",
)
# Signet Ring abilities that are optional as a whole: Spice Agony and Water
# of Life ("1 Spice ->", an arrow) [Lady Jessica card] [Reverend Mother
# Jessica card], Chronicler's Insight ("acquire … or trash …, or neither")
# [Princess Irulan card], Fedaykin Maneuver ("Retreat any number" -- zero
# included [FAQ p. 3] -- or water -> two cards) [Chani card] and Into the
# Fray ("may") [Duncan Idaho card].
_OPTIONAL_SIGNETS: Final = frozenset(
    {"lady_jessica", "princess_irulan", "chani", "duncan_idaho"}
)


def box_is_optional(state: GameState) -> bool:
    """Whether the active pending Agent box holds only optional effects now.

    An untouched optional box (``OPTIONAL_AGENT_BOXES``, or a record marked
    optional), a box whose
    remaining icons are all optional (``OPTIONAL_AGENT_ICONS``), the optional
    trashes Ruthless Leadership and The Beast's Spoils still owe, and
    Scientific Breakthrough's "Trash this card -> 1 VP" line once its
    Research is done. Not once an arrow's cost is paid (its rewards are
    queued as mandatory icons) nor while Arrakis Observer owes the Spy its
    paid discard bought (a Spy placement is mandatory, OQ-057 (14)).
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if context.get("pending_agent_effect") is not True:
        return False
    effect = active_agent_card(context).agent_effect
    icons = pending_agent_icons(context)
    if icons:
        optional_icons = (
            frozenset()
            if effect is None
            else OPTIONAL_AGENT_ICONS.get(effect, frozenset())
        )
        return set(icons) <= optional_icons
    if context.get("agent_card_spy_pending") is True:
        return False
    if "trashes_remaining" in context:
        return True
    if effect is _RESEARCH_AND_TRASH_FOR_VP:
        _, card_instance_id, _ = _effect_subject(context)
        return _box_researched(context, card_instance_id)
    if effect is PersonalCardAgentEffect.LEADER_SIGNET:
        return _signet_is_optional(state, context)
    if effect in OPTIONAL_AGENT_BOXES:
        return True
    # A recorded box says so itself (composed effects, A3b).
    recorded = box_ability(effect)
    return recorded is not None and recorded.mark is AbilityMark.OPTIONAL


def _signet_is_optional(state: GameState, context: dict[str, ActionValue]) -> bool:
    """Whether the Signet Ring box's Leader ability is optional at this stage.

    ``_OPTIONAL_SIGNETS`` throughout; Staban Tuek's paid follow-up once its
    Spy is placed (an arrow) [Staban Tuek card]; Count Hasimir Fenring's and
    Gaius Helen Mohiam's "— OR —" until a Spy is recalled for the Spy half
    (a Spy is then owed, OQ-057 (14)) -- their refusal was offered before
    and stays the reading; Feyd-Rautha's trash stages (a black trash icon,
    and "1 Solari -> trash") [Feyd-Rautha Harkonnen card]. The Spy stages,
    Esmar Tuek's choose-one and the other Leaders' abilities are mandatory.
    """

    from dune_imperium.content.uprising.leaders import (
        FEYD_TRACK_BY_ID,
        FeydTrackReward,
    )

    leader_id = state.players[context_int(context, "turn_owner")].leader_id
    if leader_id in _OPTIONAL_SIGNETS:
        return True
    if leader_id == "staban_tuek":
        return isinstance(context.get("staban_bonus_post"), str)
    if leader_id in ("count_hasimir_fenring", "gaius_helen_mohiam"):
        return (
            context.get("leader_spy_recalled") is not True
            and context.get("listeners_paid") is not True
        )
    stage_id = context.get("feyd_track_stage")
    return isinstance(stage_id, str) and FEYD_TRACK_BY_ID[stage_id].reward in (
        FeydTrackReward.PAY_SOLARI_TO_TRASH,
        FeydTrackReward.OPTIONAL_TRASH,
    )


def box_has_optional_icon(state: GameState) -> bool:
    """Whether the active box still queues an optional icon (Tread in
    Darkness's trash, Twisted Mentat's recall) beside any mandatory one."""

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if context.get("pending_agent_effect") is not True:
        return False
    effect = active_agent_card(context).agent_effect
    if effect is None:
        return False
    optional_icons = OPTIONAL_AGENT_ICONS.get(effect, frozenset())
    return any(key in optional_icons for key in pending_agent_icons(context))


def box_refusal_needed(state: GameState) -> bool:
    """Whether the active optional box keeps its refusal row.

    Only part way through a bundled selection -- Corrinth City between its
    discards, Ruthless Leadership's second trash, The Beast's Spoils' owed
    Crysknife trashes -- while the other grafted box waits for it
    (``box_in_progress``, docs/graft-boxes-plan.md 4.3): the refusal is then
    how the owner turns to the other card. Anywhere else an unused optional
    box simply lapses when the turn ends.
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if not is_grafted_turn(context) or not box_is_pending(
        context, 1 - active_box(context)
    ):
        return False
    return _box_selection_under_way(state, context)


def pending_boxes_hold_the_end(state: GameState) -> bool:
    """Whether a pending Agent box of the turn still holds its end back.

    A box holds it unless it is optional now (``box_is_optional``) or a
    mandatory box that can only fizzle (OQ-057 (1)); with a graft each box
    is judged with itself active.
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    for box in (0, 1):
        if not box_is_pending(context, box):
            continue
        view = state_with_active_box(state, box)
        if not box_is_optional(view) and not agent_card_effect_is_unavailable(view):
            return True
    return False


def lapse_optional_boxes(state: GameState) -> RuleResult:
    """Lapse every Agent box of the turn that is optional now (the turn end).

    The owner's press of the turn's end is their answer to every optional
    effect still unused (user ruling 2026-10-14); a box with only optional
    icons left retires them. Each lapsed box is logged.
    """

    working = state
    events: list[GameEvent] = []
    for box in (0, 1):
        _, context = current_agent_effect_context(working)
        if not box_is_pending(context, box):
            continue
        view = state_with_active_box(working, box)
        if not box_is_optional(view):
            continue
        _, context = current_agent_effect_context(view)
        player, card_instance_id, _ = _effect_subject(context)
        for key in pending_agent_icons(context):
            finish_agent_icon(context, key)
        context["pending_agent_effect"] = False
        for key in _OPTIONAL_PROGRESS_KEYS:
            context.pop(key, None)
        working = advance_after_effect(view, context)
        events.append(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:"
                    f"agent_card:{card_instance_id}:lapsed"
                ),
                kind="agent_card_effect_lapsed",
                payload=(("card_id", card_instance_id), ("player", player)),
            )
        )
    return RuleResult(state=working, events=tuple(events))


# The Leader Signet stages a Signet Ring's box holds while its ability is
# under way (``leader_abilities``).
_SIGNET_STAGE_KEYS: Final = (
    "feyd_track_stage",
    "feyd_spy_recalled",
    "leader_spy_recalled",
    "staban_bonus_post",
    "listeners_paid",
    "signet_rewards",
)


def box_in_progress(state: GameState) -> bool:
    """Whether the active Agent box is part way through one bundled selection.

    While it is, the other grafted box's rows wait until it is done (user
    decision 2026-10-12, docs/graft-boxes-plan.md 4.3): a "Choose two"
    after its first pick (Long Reach, Stitched Horror -- both are named
    before either resolves, OQ-057 (4)), Corrinth City between its two
    discards, Arrakis Observer's Spy after its discard, Ruthless
    Leadership's and The Beast's Spoils' trashes still owed, a Leader
    Signet ability between its stages, and an arrow's reward icons once its
    cost is paid (Piter, Branching Path, Captured Mentat, Guild Spy, Elite
    Forces, Pivotal Gambit). Only the active box holds the other one's rows
    back, and only while it can go on: a selection that can no longer
    continue this moment -- Long Reach's second Faction after the visited
    space raised the last other cube to the top -- offers no rows and waits
    for the turn's end like any box that can only fizzle (OQ-057 (1)), so
    the other box is offered again and the turn can still end.
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if not _box_selection_under_way(state, context):
        return False
    from dune_imperium.rules.agent_effect_frame import active_box_can_act

    return active_box_can_act(state, context_int(context, "turn_owner"))


def _box_selection_under_way(
    state: GameState, context: dict[str, ActionValue]
) -> bool:
    """Whether the active Agent box is part way through a bundled selection."""

    if context.get("pending_agent_effect") is not True:
        return False
    if context.get("influence_chosen") or _chosen_rewards(context):
        return True
    player = context_int(context, "turn_owner")
    owner = state.players[player]
    first = context.get("corrinth_first_card_id")
    if isinstance(first, str) and first in owner.hand:
        return True
    if context.get("agent_card_spy_pending") is True:
        return True
    if "trashes_remaining" in context:
        return True
    if any(key in context for key in _SIGNET_STAGE_KEYS):
        return True
    if pending_agent_icons(context):
        # Icons the box did not print at placement are an arrow's rewards.
        printed = agent_card_icons_at_placement(
            active_agent_card(context).agent_effect, owner.leader_id
        )
        return not printed
    return False


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
    event_source = agent_card_source(state.round_number, player, card_instance_id)
    recruit_shortfall: tuple[GameEvent, ...] = ()
    if effect is PersonalCardAgentEffect.LEADER_SIGNET:
        return resolve_leader_signet(state)
    ability = box_ability(effect)
    if ability is not None and ability.hook is not None:
        # A special flow kept as code (composed effects, A3).
        return _BOX_HOOKS[ability.hook](state)
    if ability is not None and (
        not optional_arrow(ability)
        or (
            context.get("agent_card_spy_pending") is True
            and discard_box(ability)
            and discard_spy(ability) is not None
        )
    ):
        # A box written as an ability record (composed effects, stage A2),
        # or an optional arrow on the mandatory step its cost opened
        # (Arrakis Observer's Spy, A3f).
        return resolve_box(state)
    # An optional arrow resolves only through its payment or discard row;
    # the generic resolution below is reached only by the dry run, which
    # keeps the answers it had before the record (Tleilaxu Surgeon:
    # unavailable; the others: not implemented, read as available).
    if effect is PersonalCardAgentEffect.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE:
        # Long Reach with no further Faction to name. A first pick made with
        # no second possible is paid at once (``apply_agent_card_influence``,
        # user ruling 2026-10-08), so this is reached only when the second
        # became impossible after the first pick -- a later effect of the
        # turn raised the last other cube to the top -- or with no Faction
        # named at all. The box then waits for the turn's end (this
        # resolution reports itself unavailable, OQ-057 (1)), and the Faction
        # already named is paid and the rest is lost, as a Conflict reward's
        # "Choose two" pays its first Faction (OQ-060).
        if legal_agent_card_influence_actions(state, player):
            raise RuntimeError("Agent-card Influence effect requires a player choice")
        chosen_value = context.get("influence_chosen", "")
        working = state
        named_events: list[GameEvent] = []
        for pick in (Faction(value) for value in str(chosen_value).split(",") if value):
            step = gain_faction_influence(
                working,
                player,
                pick,
                1,
                event_prefix=f"{event_source}:influence:{pick.value}",
            )
            working = step.state
            named_events.extend(step.events)
        context["pending_agent_effect"] = False
        return RuleResult(
            state=advance_after_effect(working, context, working.players),
            events=(
                GameEvent(
                    event_id=event_source,
                    kind="agent_card_effect_unavailable",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
                *named_events,
            ),
        )
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
        # The 2 replaced the space's 1 for good: a partner box that held it
        # too and expires later does not bring the 1 back (never 2 + 1).
        context[_SPACE_INFLUENCE_REPLACED] = True
        trashed = trash_personal_card(
            gained.state,
            player,
            card_instance_id,
            source=source,
        )
        _keep_trash_recruits(context, trashed)
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
        if len(owner.deck) < 3:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}:long_live_fighters"
            )
            return RuleResult(
                state=replace(
                    state,
                    decision_stack=(
                        *state.decision_stack,
                        long_live_fighters_frame(player, source, card_instance_id),
                    ),
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
    elif effect in (
        PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN,
        PersonalCardAgentEffect.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU,
        _TRASH_GRAFTED_FOR_INFLUENCE,
        _CHOOSE_TWO_REWARDS,
    ):
        # Reached only when the box's choice provider offered nothing: no
        # grafted partner, no genetic marker, no Faction space.
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is _RESEARCH_AND_TRASH_FOR_VP:
        if _box_researched(context, card_instance_id):
            # Scientific Breakthrough's trash line after its Research: an
            # arrow choice once two markers are reached, else it waits for
            # the turn's end and lapses there (OQ-057 (1)).
            if genetic_markers_reached(owner.research_space) >= 2:
                raise ValueError("choose whether to trash Scientific Breakthrough")
            context["pending_agent_effect"] = False
            return RuleResult(
                state=advance_after_effect(state, context),
                events=(
                    GameEvent(
                        event_id=f"{event_source}:trash_line",
                        kind="agent_card_effect_unavailable",
                        payload=(("card_id", card_instance_id), ("player", player)),
                    ),
                ),
            )
        # Scientific Breakthrough's Research first: the trash line stays
        # open behind it and is judged once the Research has settled
        # ("[2 genetic markers]: Trash this card -> 1 VP" [card face];
        # OQ-028), so a Research that reaches the second marker unlocks it.
        context[_RESEARCHED_BOXES] = ",".join(
            (*_researched_boxes(context), card_instance_id)
        )
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
    else:
        raise NotImplementedError(
            f"personal-card Agent effect is not implemented: {card.card.card_id}"
        )
    players = replace_player(state.players, next_owner)
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:"
            f"agent_card:{card_instance_id}"
        ),
        kind=event_kind,
        payload=(("card_id", card_instance_id), ("player", player)),
    )
    return RuleResult(state=next_state, events=(event, *recruit_shortfall))


# --- Special flows of recorded Agent boxes (``agent_abilities``'s hooks) -----


def _box_subject(
    state: GameState,
) -> tuple[dict[str, ActionValue], int, str, PlayerState, str]:
    """The active box's context, owner seat, card, owner and event source."""

    _, context = current_agent_effect_context(state)
    player, card_instance_id, _ = _effect_subject(context)
    owner = state.players[player]
    source = agent_card_source(state.round_number, player, card_instance_id)
    return context, player, card_instance_id, owner, source


def _hook_seek_allies(state: GameState) -> RuleResult:
    """"Trash this card." (Seek Allies) is mandatory [Main p. 20]; the trash's
    events alone. A card trashed by a freely ordered effect expires before
    this resolution is offered (OQ-022), so the card is still in play here."""

    context, player, card_instance_id, _, _ = _box_subject(state)
    trashed = trash_personal_card(
        state,
        player,
        card_instance_id,
        source=f"round:{state.round_number}:player:{player}:agent_card",
    )
    _keep_trash_recruits(context, trashed)
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(trashed.state, context, trashed.state.players)
    return RuleResult(state=next_state, events=trashed.events)


def _hook_clandestine_meeting(state: GameState) -> RuleResult:
    """Clandestine Meeting: Bene Gesserit Influence and an Intrigue card, the
    draw named ``<box>:intrigue``; the box's event comes first."""

    context, player, card_instance_id, _, event_source = _box_subject(state)
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


def _hook_lisan_al_gaib(state: GameState) -> RuleResult:
    """Lisan al Gaib: the Bond is judged when the effect resolves
    [Main pp. 9, 20] (a grafted partner may provide it); the Influence's
    events alone."""

    context, player, card_instance_id, owner, event_source = _box_subject(state)
    context["pending_agent_effect"] = False
    if not has_faction_bond(
        counted_in_play(owner), card_instance_id, Faction.BENE_GESSERIT
    ):
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


def _hook_occupation(state: GameState) -> RuleResult:
    """Occupation: draw a card and the Combat icon [Immortality p. 16]. The
    grant writes the frame, so the context is re-read before the box closes;
    the draw is named ``<box>:draw``."""

    _, player, card_instance_id, _, event_source = _box_subject(state)
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


def _hook_overthrow(state: GameState) -> RuleResult:
    """Overthrow: one more Influence with the visited Faction, the
    Influence's events alone (the placement keeps the box off a space with
    no Faction, ``agent_turn.agent_effect_is_available``)."""

    context, player, _, _, event_source = _box_subject(state)
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
        event_prefix=f"{event_source}:influence:{faction.value}",
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    return RuleResult(state=next_state, events=gained.events)


def _hook_possible_futures(state: GameState) -> RuleResult:
    """Possible Futures' two-troop half, its plain resolution (the Bond case
    pays both through the Influence choice instead): the box's event, then
    the shortfall named ``<box>:recruit_short``."""

    context, player, card_instance_id, owner, event_source = _box_subject(state)
    next_owner, recruited = recruit_troops(owner, 2)
    previous = context.get("troops_recruited")
    if isinstance(previous, bool) or not isinstance(previous, int):
        raise RuntimeError("Agent-turn effect frame has invalid recruit count")
    context["troops_recruited"] = previous + recruited
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        state, context, replace_player(state.players, next_owner)
    )
    event = GameEvent(
        event_id=event_source,
        kind="agent_card_effect_resolved",
        payload=(("card_id", card_instance_id), ("player", player)),
    )
    return RuleResult(
        state=next_state,
        events=(
            event,
            *recruit_shortfall_events(event_source, player, 2, recruited),
        ),
    )


def _is_possible_futures(ability: Ability | None) -> bool:
    """Possible Futures' Bond-shaped choice, named by its record's hook."""

    return ability is not None and ability.hook == "possible_futures"


def _hook_control_the_spice(state: GameState) -> RuleResult:
    """Control the Spice resolves through its payment choice, which always
    offers at least the decline: reached by the dry run only (its old
    answer)."""

    raise RuntimeError("Agent-card payment effect requires a player choice")


def _is_control_the_spice(ability: Ability | None) -> bool:
    """Control the Spice's payment flow, named by its record's hook."""

    return ability is not None and ability.hook == "control_the_spice"


def _hook_in_high_places(state: GameState) -> RuleResult:
    """In High Places: "If you have another Bene Gesserit card in play: [draw
    1 card] [Spy]" [In High Places card], the Bond judged when the effect
    resolves [Main pp. 9, 20]. The box's event comes first; the plain Spy
    icon opens the shared placement frame -- any unoccupied post, mandatory
    with a Spy in supply, and with an empty supply "you may first recall one
    of your Spies" [Main pp. 11, 20] (OQ-057 (14)) -- under the draw, whose
    discard shuffle (if any) resolves first, so the printed order holds."""

    context, player, card_instance_id, owner, event_source = _box_subject(state)
    bonded = has_faction_bond(
        counted_in_play(owner), card_instance_id, Faction.BENE_GESSERIT
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(state, context)
    event = GameEvent(
        event_id=event_source,
        kind=(
            "agent_card_effect_resolved" if bonded else "agent_card_effect_unavailable"
        ),
        payload=(("card_id", card_instance_id), ("player", player)),
    )
    if not bonded:
        return RuleResult(state=next_state, events=(event,))
    with_spy = spy_placement_frame(
        next_state,
        player,
        tuple(post.post_id for post in OBSERVATION_POSTS),
        source=event_source,
    )
    draw = draw_or_request_personal_cards(with_spy, player, 1, source=event_source)
    return RuleResult(state=draw.state, events=(event, *draw.events))


# The hook names ``content.uprising.agent_abilities`` gives its special flows.
_BOX_HOOKS: Final[Mapping[str, Callable[[GameState], RuleResult]]] = (
    MappingProxyType(
        {
            "seek_allies": _hook_seek_allies,
            "clandestine_meeting": _hook_clandestine_meeting,
            "lisan_al_gaib": _hook_lisan_al_gaib,
            "occupation": _hook_occupation,
            "overthrow": _hook_overthrow,
            "in_high_places": _hook_in_high_places,
            "control_the_spice": _hook_control_the_spice,
            "possible_futures": _hook_possible_futures,
        }
    )
)


def box_hook_names() -> frozenset[str]:
    """The special flows a recorded Agent box may name (``Ability.hook``)."""

    return frozenset(_BOX_HOOKS)


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


def spy_recalled_this_turn(owner: PlayerState) -> bool:
    """Return whether the seat recalled one of its Spies during this turn.

    "If you recalled a Spy this turn:" (Imperial Spymaster, Strike Fleet,
    Rebel Supplier, Public Spectacle, Corrupt Bureaucrat) names no way of
    recalling, so every recall counts: Infiltrate and Gather Intelligence
    [Main p. 11], a card's Recall Spy icon or cost [Main pp. 11, 20], and
    the "first recall one of your Spies for no effect" before a placement
    [Main pp. 11, 20]. ``spies_recalled_turn`` counts each of them and
    restarts whenever the seat's turn opens — the same reading as Spy
    Drones (OQ-044 (d)).
    """

    return owner.spies_recalled_turn > 0


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


def _researched_boxes(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    value = context.get(_RESEARCHED_BOXES, "")
    return tuple(value.split(",")) if isinstance(value, str) and value else ()


def _box_researched(context: Mapping[str, ActionValue], card_instance_id: str) -> bool:
    """Return whether this card's Scientific Breakthrough box did its Research."""

    return card_instance_id in _researched_boxes(context)
