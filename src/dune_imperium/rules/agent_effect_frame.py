"""Legal-action composition for the Agent-turn effect frame.

The Agent-turn effect frame carries several pending groups at once (card
effect, board effect, Faction Influence, Contract completion, deployment). This
module decides which of those groups may currently offer actions and in which
order, so the dispatcher does not have to know the frame's internal flags.
``agent_box_is_waiting`` exposes the one test that withholds a single-effect
Agent box (OQ-057), for the page's greyed-out row (``display.unavailable``).

A grafted turn has two Agent boxes, offered together from the start (user
decision 2026-10-12, docs/graft-boxes-plan.md): "You gain the effects on
both cards, in addition to the board space effects, in any order you
choose." [Immortality pp. 10-11]. Box 0 is the placed card, box 1 the
partner; box 1's rows carry ``box=1`` (``graft_boxes.tagged``). Each box's
rows are what the box machinery offers with that box active
(``graft_boxes.state_with_active_box``), and ``route_box_action`` makes a
chosen row's box active before its handler runs. While one box is part way
through a bundled selection (``agent_effects.box_in_progress``) the other
box's rows wait.
"""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import legal_agent_card_acquisitions
from dune_imperium.rules.agent_effects import (
    agent_card_effect_is_unavailable,
    box_has_optional_icon,
    box_in_progress,
    box_is_optional,
    box_refusal_needed,
    legal_agent_card_boost_actions,
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
    resolves_boost_draw,
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
    agent_turn_is_finishing,
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
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import (
    BOX_ACTION_IDS,
    active_box,
    is_grafted_turn,
    row_box,
    state_with_active_box,
    tagged,
    untagged,
)
from dune_imperium.rules.immortality import (
    legal_family_atomics_actions,
    legal_research_bonus_actions,
    legal_specimen_return_actions,
)
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.leader_abilities import (
    legal_feyd_track_actions,
    legal_leader_board_repeat_actions,
    legal_leader_placement_ability_actions,
    legal_leader_signet_actions,
)
from dune_imperium.rules.optional_trash import legal_optional_trash_actions
from dune_imperium.rules.owed_draws import legal_owed_draw_actions
from dune_imperium.rules.sardaukar import (
    legal_commander_recruit_actions,
    legal_sardaukar_commander_actions,
)
from dune_imperium.rules.scouts_effects import legal_subcommittee_choice_actions
from dune_imperium.rules.scouts_missions import legal_mission_collect_actions
from dune_imperium.rules.spies import legal_gather_intelligence_actions
from dune_imperium.rules.spy_moves import legal_track_spy_actions
from dune_imperium.rules.tech import (
    legal_tech_acquire_effect_actions,
    legal_tech_acquisition_actions,
    legal_tech_flip_actions,
)

_RESOLVE_BOX = "resolve_agent_card_effect"

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
    if agent_turn_is_finishing(context):
        # The end was pressed; the engine closes or reopens the turn as soon
        # as the Usurp trash's follow-ups are done (OQ-095 (4)-(5)).
        return ()

    pending_groups = _pending_group_actions(state, player, context)

    gather_intelligence_actions = legal_gather_intelligence_actions(state, player)
    if gather_intelligence_actions:
        return gather_intelligence_actions

    return (
        *pending_groups,
        # The Emperor track's Influence 4 Spy waits in the turn and is
        # placed in any order before its end (user ruling 2026-10-04).
        *legal_track_spy_actions(state, player),
        # So does a draw a trigger earned in it, taken as its own step
        # (user ruling 2026-10-10, OQ-106).
        *legal_owed_draw_actions(state, player),
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
        *legal_mission_collect_actions(state, player),
        # Arrakeen Scouts: the new High Council seat's subcommittee, one
        # more effect of the visit in any order (OQ-076 alternative C).
        *legal_subcommittee_choice_actions(state, player),
        *legal_tech_acquisition_actions(state, player),
        *legal_tech_flip_actions(state, player),
        *legal_tech_acquire_effect_actions(state, player),
        # A research bonus or trash icon raised in the turn waits on it as
        # rows, with no refusal (user decision 2026-10-17, cleanup-2b).
        *legal_research_bonus_actions(state, player),
        *legal_optional_trash_actions(state, player),
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


def agent_box_is_waiting(
    state: GameState, player: int, box: int | None = None
) -> bool:
    """Whether ``player``'s pending single-effect Agent box ``box`` is withheld.

    The box is pending as one effect (not a multi-icon box, OQ-027), none
    of its serial choices is offered, and it would resolve without effect
    now (``agent_card_effect_is_unavailable``, a cached dry run of the
    owner's own box): a mandatory box whose condition is false waits for
    the turn's end instead of fizzling now (OQ-057), so
    ``resolve_agent_card_effect`` is not offered. The legal list offers the
    box through the same ``_single_box_actions``, and the page greys the
    waiting box out with this predicate (``display.unavailable``, user
    request 2026-09-29), so the two cannot drift. ``box`` names a grafted
    turn's box 0 or 1, judged with that box active; ``None`` (the default)
    is the box in ``card_id``.
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return False
    if box is None:
        box = active_box(context)
    if box == 1 and not is_grafted_turn(context):
        return False
    view = state_with_active_box(state, box)
    _, context = current_agent_effect_context(view)
    if context["pending_agent_effect"] is not True or pending_agent_icons(context):
        return False
    return not _single_box_actions(view, player)


# A box choice that answers the box without its effect: an optional
# arrow's or "may" effect's refusal ("You do not have to pay such a cost on
# a card" [Main p. 20], OQ-058).
_REFUSALS = frozenset(
    action_id for action_id in BOX_ACTION_IDS if action_id.startswith("decline_")
)


def _box_choice_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """The serial choices the Agent box in ``card_id`` offers now."""

    return tuple(
        action
        for provider in _AGENT_CARD_CHOICE_PROVIDERS
        for action in provider(state, player)
    )


def agent_box_can_resolve_by_choice(state: GameState, player: int) -> bool:
    """Whether the Agent box in ``card_id`` offers a choice that gives its effect.

    A box resolved by a choice -- Stitched Horror's "Choose two", Beguiling
    Pheromones' trash, an optional arrow whose cost can be paid, Tleilaxu
    Master's acquisition -- does not take the generic resolution, so its
    dry run reads "unavailable" whatever it offers. While it offers such a
    choice it can still resolve, and the turn end waits for it (OQ-057
    (1), OQ-095 2; ``agent_effects.agent_card_effect_is_unavailable``). A
    box that offers only its refusal (an arrow whose cost cannot be paid)
    cannot: the end fizzles it, as the refusal would.
    """

    return any(
        action.action_id not in _REFUSALS
        for action in _box_choice_actions(state, player)
    )


def _single_box_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """What a pending single-effect Agent box offers now; () while it waits.

    Its serial choices when any is offered (the generic resolution is
    withheld until the choice is made); otherwise ``resolve_agent_card_effect``,
    unless the box would resolve without effect now: a mandatory box whose
    condition is false waits for the turn's end instead of fizzling now
    (OQ-057); ``finish_agent_turn`` resolves it then.
    """

    choice_actions = _box_choice_actions(state, player)
    if choice_actions or box_is_optional(state):
        # An optional box resolves only through its choices; with none
        # offered now it waits, unused, and lapses at the turn's end.
        return choice_actions
    if agent_card_effect_is_unavailable(state):
        return ()
    return (DomainAction(action_id="resolve_agent_card_effect", actor=player),)


def _active_box_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """The rows of the Agent box whose card sits in ``card_id``, untagged."""

    _, context = current_agent_effect_context(state)
    if context["pending_agent_effect"] is not True:
        return ()
    if pending_agent_icons(context):
        # A multi-icon Agent box: every pending icon is offered at once, the
        # automatic ones through their keyed resolution and the choice icons
        # (Steersman's recall, Dangerous Rhetoric's Faction, Tread in
        # Darkness's trash) through their own providers (OQ-027).
        rows = (
            *legal_agent_card_icon_actions(state, player),
            *legal_agent_card_recall_actions(state, player),
            *legal_agent_card_influence_actions(state, player),
            *legal_agent_card_trash_actions(state, player),
        )
    else:
        # Nothing while the box waits (``agent_box_is_waiting``, OQ-057).
        rows = _single_box_actions(state, player)
    return _without_refusal(state, rows)


def _without_refusal(
    state: GameState, rows: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """``rows`` without the refusal of a box that is optional now.

    An unused optional effect needs no refusal: the turn's end lapses it
    (OQ-095 (2), user ruling 2026-10-14). The refusal stays where it is
    still needed (``agent_effects.box_refusal_needed``) and for mandatory
    boxes, such as a Spy placement passed up with an empty supply (OQ-057
    (14)).
    """

    if not rows or box_refusal_needed(state):
        return rows
    # A box resolved icon by icon offers refusals only for its optional
    # icons (Tread in Darkness's trash beside its draw), so they go even
    # while a mandatory icon remains.
    if not box_is_optional(state) and not box_has_optional_icon(state):
        return rows
    return tuple(row for row in rows if row.action_id not in _REFUSALS)


def active_box_can_act(state: GameState, player: int) -> bool:
    """Whether the Agent box whose card sits in ``card_id`` offers a row now.

    A bundled selection holds the other grafted box's rows back only while
    it can go on (``agent_effects.box_in_progress``); one that offers
    nothing waits for the turn's end (OQ-057 (1)).
    """

    return bool(_active_box_actions(state, player))


def box_actions(
    state: GameState, player: int, box: int
) -> tuple[DomainAction, ...]:
    """Box ``box``'s rows with that box active, untagged.

    What the box's machinery offers, whether or not the other box's
    bundled selection holds it back now (``agent_box_rows`` applies that):
    a record before codec v143 reads a recorded step as a box's row by
    this (``records.migration``).
    """

    return _active_box_actions(state_with_active_box(state, box), player)


def agent_box_rows(
    state: GameState, player: int
) -> tuple[tuple[DomainAction, ...], tuple[DomainAction, ...]]:
    """Box 0's and box 1's rows as offered now, both untagged.

    Each box's rows are its machinery's with that box active. While the
    active box is part way through a bundled selection
    (``box_in_progress``), the other box offers none (user decision
    2026-10-12, docs/graft-boxes-plan.md 4.3). A single-card turn has box
    0 only.
    """

    _, context = current_agent_effect_context(state)
    own = _active_box_actions(state, player)
    if not is_grafted_turn(context):
        return own, ()
    current = active_box(context)
    other: tuple[DomainAction, ...] = ()
    if not box_in_progress(state):
        other = _active_box_actions(state_with_active_box(state, 1 - current), player)
    return (own, other) if current == 0 else (other, own)


def route_box_action(
    state: GameState, action: DomainAction
) -> tuple[GameState, DomainAction, int | None]:
    """The state to apply a legal row on, the row untagged, and its box.

    A ``box=1`` row is box 1's; an untagged row is box 0's when box 0
    offers it, and otherwise no box's (the turn's other effects). Urgent
    Shigawire's added draw is no box's either, whichever box it was added
    to (untagged for box 0, ``box=1`` for a Bene Gesserit partner, OQ-107):
    it is bound to its card (``effects.BOOST_DRAW_KEY``) and kept as it is,
    so no box is made active for it -- not even while the other box is part
    way through a bundled selection. A box's row is applied with that box
    active, so the ordinary Agent-box handlers read it; any other row is
    applied as it is (box ``None``).
    """

    if not state.decision_stack:
        return state, action, None
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        return state, action, None
    if action.action_id == _RESOLVE_BOX and resolves_boost_draw(state, action):
        return state, action, None
    context = dict(frame.context)
    if row_box(action) == 1:
        return state_with_active_box(state, 1), untagged(action), 1
    if not is_grafted_turn(context):
        return state, action, None
    zero = state_with_active_box(state, 0)
    if box_in_progress(state) and active_box(context) == 1:
        return state, action, None
    if action in _active_box_actions(zero, action.actor):
        return zero, action, 0
    return state, action, None


def _pending_group_actions(
    state: GameState,
    player: int,
    context: dict[str, bool | int | str],
) -> tuple[DomainAction, ...]:
    box_zero, box_one = agent_box_rows(state, player)
    uncoded = sorted(
        {action.action_id for action in box_one} - BOX_ACTION_IDS
    )
    if uncoded:
        raise RuntimeError(
            "a grafted box offers actions with no box=1 template: "
            + ", ".join(uncoded)
        )
    actions: list[DomainAction] = [
        *box_zero,
        *(tagged(action, 1) for action in box_one),
    ]
    # Urgent Shigawire's draw added to the boosted card's box, its own step
    # whatever the box is (user ruling 2026-10-10, OQ-106); ``box=1`` when
    # the boosted card is the graft partner (OQ-107).
    actions.extend(legal_agent_card_boost_actions(state, player))
    # One action per pending automatic icon of the visited space; its
    # choice icons are offered by the dedicated providers below (OQ-027).
    actions.extend(legal_board_effect_actions(state, player))
    if context["pending_faction_influence"] is True:
        actions.append(
            DomainAction(action_id="resolve_faction_influence", actor=player)
        )
    return tuple(actions)
