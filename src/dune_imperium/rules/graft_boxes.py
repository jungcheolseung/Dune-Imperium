"""The two Agent boxes of a grafted Agent turn [Immortality pp. 10-11].

"You gain the effects on both cards, in addition to the board space
effects, in any order you choose." [Immortality pp. 10-11]. Box 0 is the
placed card (the ``agent_turn``'s ``card_id``) and box 1 the graft partner
(``choose_graft_partner``); the numbering never changes during the turn
(docs/graft-boxes-plan.md 4.1).

The Agent-box machinery (every provider and apply of ``agent_effects``,
the Leader Signet stages, the frames a box pushes) reads one box: the one
whose card sits in ``card_id``. The effect frame keeps the other box in the
twin keys of ``BOX_KEY_PAIRS``. ``swap_boxes`` exchanges the two, every
box-scoped key at once, so whichever box is in ``card_id`` resolves through
that machinery and "the other grafted card" (``graft_card_id``) is always
the other box's card. ``ACTIVE_BOX_KEY`` records which box sits in
``card_id`` (absent: box 0, every single-card turn).

Every key of the frame is either one box's (``BOX_KEY_PAIRS``), bound to a
card whichever box resolves it (``CARD_KEYS``), or the turn's
(``TURN_KEYS``); ``swap_boxes`` refuses a key that is none of these, so a
new key cannot ride along unclassified.
"""

from collections.abc import Mapping
from copy import replace
from typing import Final

from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind, with_context

# Which box sits in ``card_id`` (0 the placed card, 1 the partner); absent
# until the partner joins, and on every single-card turn.
ACTIVE_BOX_KEY: Final = "graft_active_box"

# The box resolving now and its twin for the other box. The first five
# pairs predate box 1's own rows; the rest held one box's progress without a
# twin, so a second box of the same kind read the first one's (Ghola +
# Stitched Horror paid the first box's picks again, OQ-057 (12)).
BOX_KEY_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("card_id", "graft_card_id"),
    ("pending_agent_effect", "graft_pending_effect"),
    # The box's queued icons: its printed ones (OQ-027) or an arrow's
    # rewards once its cost is paid (Piter, Branching Path, Captured
    # Mentat, Guild Spy, Elite Forces, Pivotal Gambit).
    ("pending_agent_icons", "graft_pending_icons"),
    # The card left play by its own printed effect (OQ-022).
    ("agent_card_self_trashed", "graft_card_self_trashed"),
    # "Choose two": Long Reach's Factions, Stitched Horror's rewards
    # (OQ-057 (4)).
    ("influence_chosen", "graft_influence_chosen"),
    ("rewards_chosen", "graft_rewards_chosen"),
    # Ruthless Leadership's and The Beast's Spoils' trashes still owed.
    ("trashes_remaining", "graft_trashes_remaining"),
    # Corrinth City's first discard before the second.
    ("corrinth_first_card_id", "graft_corrinth_first_card_id"),
    # Arrakis Observer's Spy after its discard.
    ("agent_card_spy_pending", "graft_agent_card_spy_pending"),
    ("agent_card_spy_recalled", "graft_agent_card_spy_recalled"),
    # The Signet Ring's box: its Leader ability's stages.
    ("feyd_track_stage", "graft_feyd_track_stage"),
    ("feyd_spy_recalled", "graft_feyd_spy_recalled"),
    ("leader_spy_recalled", "graft_leader_spy_recalled"),
    ("staban_bonus_post", "graft_staban_bonus_post"),
    ("listeners_paid", "graft_listeners_paid"),
    ("signet_rewards", "graft_signet_rewards"),
)

# Bound to a card, not to the box resolving it.
CARD_KEYS: Final = frozenset(
    {
        # Urgent Shigawire's added draws name their cards themselves
        # (``effects.BOOST_DRAW_KEY``): the placed card or a Bene Gesserit
        # partner that took the boost, and a Ghola grafted to it (OQ-107).
        "boost_draw_card_ids",
        # The cards that took the boost this turn: each has all Agent icons
        # (``effects.BOOSTED_CARDS_KEY``, Slig Farmer's count, OQ-055).
        "boosted_card_ids",
        # The cards whose Scientific Breakthrough box did its Research: a
        # Ghola copying it researches once more (``agent_effects``).
        "research_resolved_card_ids",
    }
)

# The turn's own bookkeeping, whichever box resolves.
TURN_KEYS: Final = frozenset(
    {
        ACTIVE_BOX_KEY,
        "board_icons",
        "combat_commanders_deployed",
        "combat_commanders_withdrawable",
        "combat_troops_deployed",
        "combat_troops_withdrawable",
        "commanders_recruited",
        "cost_option",
        "espionage_spy_recalled",
        "existing_troop_deployment_limit",
        "finish_deployment_window",
        "finish_recruited_units",
        "finishing",
        "pending_board_effect",
        "pending_board_icons",
        "pending_combat_deployment",
        "pending_contract_ids",
        "pending_faction_influence",
        "pending_gather_intelligence",
        "pending_leader_ability",
        "pending_leader_board_repeat",
        "pending_tech_acquire_effects",
        # Effects waiting on the turn as rows (cleanup-2b, ``turn_rows``).
        "pending_turn_rows",
        # The rows picked toward one waiting effect (stage B3,
        # ``effect_steps``), whichever box's effect it is.
        "effect_pick",
        "space_id",
        # The space's own Influence was replaced by a box's "two instead
        # of one" for good (Subversive Advisor, Treacherous Maneuver).
        "space_influence_replaced",
        "troops_recruited",
        # The turn's Agent was recalled (Twisted Mentat): a second box
        # finds it gone.
        "turn_agent_recalled",
        "turn_owner",
        "undeployable_troops",
        # A Harkonnen Advisor troop still in the shortfall (OQ-038).
        "undeployable_troops_ungained",
        "units_deploy_blocked",
    }
)

BOX_KEYS: Final = frozenset(key for pair in BOX_KEY_PAIRS for key in pair)


def unclassified_keys(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    """The keys of an effect-frame context that no class above names."""

    return tuple(
        sorted(
            key
            for key in context
            if key not in BOX_KEYS and key not in CARD_KEYS and key not in TURN_KEYS
        )
    )


def swap_boxes(context: dict[str, ActionValue]) -> None:
    """Put the other box in ``card_id`` and its keys: every pair at once."""

    unknown = unclassified_keys(context)
    if unknown:
        raise RuntimeError(
            "the Agent-turn effect frame holds keys no graft box class names: "
            + ", ".join(unknown)
        )
    held = {name: context.pop(name) for name in BOX_KEYS if name in context}
    for key, twin in BOX_KEY_PAIRS:
        if key in held:
            context[twin] = held[key]
        if twin in held:
            context[key] = held[twin]
    context[ACTIVE_BOX_KEY] = 1 - active_box(context)


def active_box(context: Mapping[str, ActionValue]) -> int:
    """The box whose card sits in ``card_id``: 0 the placed card, 1 the partner."""

    value = context.get(ACTIVE_BOX_KEY, 0)
    if isinstance(value, bool) or value not in (0, 1):
        raise RuntimeError("Agent-turn effect frame has an invalid active box")
    return int(value)


def is_grafted_turn(context: Mapping[str, ActionValue]) -> bool:
    """Whether the turn plays two grafted cards (box 1 exists)."""

    partner = context.get("graft_card_id", "")
    return isinstance(partner, str) and bool(partner)


def box_card_id(context: Mapping[str, ActionValue], box: int) -> str:
    """Box ``box``'s card ("" when the turn has no such box)."""

    key = "card_id" if box == active_box(context) else "graft_card_id"
    value = context.get(key, "")
    return value if isinstance(value, str) else ""


def box_is_pending(context: Mapping[str, ActionValue], box: int) -> bool:
    """Whether box ``box`` still waits to be resolved."""

    key = (
        "pending_agent_effect" if box == active_box(context) else "graft_pending_effect"
    )
    return context.get(key) is True


# The argument that names box 1 on an Agent-box row (codec v143). A row
# without it is box 0's, or no box's: the turn's other effects, Urgent
# Shigawire's draw added to the placed card (a partner's carries ``box=1``,
# OQ-107), a Servo-Receivers Signet frame's rows.
BOX_ARGUMENT: Final = "box"

# Every action an Agent box offers (``agent_effect_frame._active_box_actions``:
# its icons, its serial choices and its plain resolution, the Signet Ring's
# Leader ability included). The codec holds a ``box=1`` twin of each of
# their templates in a catalog with Immortality; the effect frame refuses a
# box 1 row outside this set, so a new box action cannot go uncoded.
BOX_ACTION_IDS: Final = frozenset(
    {
        # Plain resolution and keyed icons (OQ-027).
        "resolve_agent_card_effect",
        # Trash, discard, Contract, retreat, recall, Spy, Influence.
        "trash_agent_card",
        "decline_agent_card_trash",
        "discard_agent_card",
        "decline_agent_card_discard",
        "complete_contract_by_card",
        "retreat_opponent_troop",
        "recall_agent_for_agent_card",
        "recall_conflict_agent_for_agent_card",
        "decline_agent_card_recall",
        "place_agent_card_spy",
        "recall_spy_for_agent_card",
        "decline_agent_card_spy",
        "choose_agent_card_influence",
        # Payments.
        "pay_agent_card_water",
        "pay_agent_card_spice",
        "pay_agent_card_spice_for_sandworm",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
        "pay_agent_card_specimen",
        "pay_agent_card_two_specimens",
        "pay_agent_card_five_solari_for_tleilaxu",
        "trash_grafted_card_for_specimen",
        "trash_grafted_card_for_influence",
        "trash_agent_card_self_for_vp",
        "take_agent_card_combat_icon",
        "lose_agent_card_troop",
        "lose_agent_card_influence",
        "take_agent_card_from_discard",
        "choose_agent_card_reward",
        "decline_agent_card_payment",
        "pay_corrinth_city",
        "select_corrinth_city_discard",
        "decline_corrinth_city_payment",
        "pay_agent_card_intrigue_and_spice",
        "trash_intrigue_for_agent_card",
        "decline_agent_card_intrigue_payment",
        # Acquisitions.
        "acquire_imperium_with_solari",
        "acquire_reserve_with_solari",
        "acquire_imperium_by_card",
        "acquire_reserve_by_card",
        "decline_agent_card_acquisition",
        # The Signet Ring's box: its Leader ability.
        "advance_feyd_track",
        "trash_leader_card",
        "decline_leader_card_trash",
        "place_leader_spy",
        "recall_spy_for_leader_placement",
        "decline_leader_spy_placement",
        "pay_leader_signet_water",
        "pay_leader_signet_spice",
        "pay_leader_signet_solari",
        "decline_leader_signet_payment",
        "resolve_leader_signet_without_option",
        "gain_leader_signet_troop",
        "choose_leader_signet_influence",
        "acquire_leader_imperium",
        "acquire_leader_reserve",
        "retreat_leader_troops",
        "place_leader_bonus_spice",
        "take_leader_bonus_spice",
        "deploy_leader_agent",
        "gain_leader_signet_spice",
        "trash_leader_tech",
    }
)


def row_box(action: DomainAction) -> int:
    """1 for a row tagged with box 1, else 0."""

    return 1 if dict(action.arguments).get(BOX_ARGUMENT) == 1 else 0


def tagged(action: DomainAction, box: int) -> DomainAction:
    """``action`` as box ``box``'s row: box 1 adds ``box=1``, box 0 none."""

    plain = untagged(action)
    if box == 0:
        return plain
    return replace(
        plain, arguments=tuple(sorted((*plain.arguments, (BOX_ARGUMENT, 1))))
    )


def untagged(action: DomainAction) -> DomainAction:
    """``action`` without its box argument."""

    if all(key != BOX_ARGUMENT for key, _ in action.arguments):
        return action
    return replace(
        action,
        arguments=tuple(
            (key, value) for key, value in action.arguments if key != BOX_ARGUMENT
        ),
    )


def _top_effect_frame_context(state: GameState) -> dict[str, ActionValue] | None:
    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        return None
    return dict(frame.context)


# The last few states with their other box made active, by identity: the
# legal-action providers ask for the same one several times per step, and a
# cached dry run (``agent_effects.agent_card_effect_is_unavailable``) only
# hits for the very same state object.
_SWAPPED_CACHE: list[tuple[GameState, GameState]] = []
_SWAPPED_CACHE_SIZE: Final = 8


def state_with_active_box(state: GameState, box: int) -> GameState:
    """``state`` with box ``box`` of the effect frame on top in ``card_id``.

    ``state`` itself when that box is active already, or when the top frame
    is not an Agent-turn effect frame with a grafted partner.
    """

    context = _top_effect_frame_context(state)
    if context is None or not is_grafted_turn(context) or active_box(context) == box:
        return state
    for cached, swapped in _SWAPPED_CACHE:
        if cached is state:
            return swapped
    swap_boxes(context)
    frame = state.decision_stack[-1]
    swapped = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
    )
    _SWAPPED_CACHE.append((state, swapped))
    if len(_SWAPPED_CACHE) > _SWAPPED_CACHE_SIZE:
        del _SWAPPED_CACHE[0]
    return swapped


def other_box_state(state: GameState) -> GameState:
    """``state`` with the effect frame's other box made active."""

    context = _top_effect_frame_context(state)
    if context is None or not is_grafted_turn(context):
        return state
    return state_with_active_box(state, 1 - active_box(context))
