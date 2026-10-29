"""The Tech Module's Acquire Tech decision (``docs/rules/bloodlines.md`` §5).

"The Acquire Tech icon is the only way to acquire a Tech tile"
[Bloodlines p. 7]. Two decision points open it:

- A Landsraad visit: "during a turn in which you send an Agent to a
  Landsraad board space, you may acquire one Tech tile" [Bloodlines p. 7].
  The offer is one more freely ordered effect of the visit
  (``BOARD_ICON_TECH`` on the Agent-turn effect frame).
- A card's Tech Discount icon (Battlefield Research, Rapid Engineering): a
  ``TECH_ACQUISITION`` frame carrying the discount [Bloodlines pp. 7, 12].

Either way the owner chooses ``acquire_tech(tech_id, ...)`` for a face-up
tile on top of a stack (or Kota Odax's Secret Project tile), pays its spice
cost less the discounts (never below zero), puts it in the supply and turns
the stack's next tile face up. The tile's acquire effect pays once
[Bloodlines p. 7]; OQ-098 queues its icons for the owner to order freely
within the current turn. ``decline_tech`` refuses the offer.
"""

from collections.abc import Mapping
from copy import replace
from typing import Final

from dune_imperium.content.bloodlines.tech import (
    HIGH_COUNCIL_TECH_DISCOUNT,
    IX_FLIP_ABILITIES,
    TECH_TILES,
    TECH_TILES_BY_ID,
    TechAbility,
    TechTile,
    has_tech,
)
from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ABILITIES,
    TRASH_SPY_TO_ACQUIRE,
)
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.effect_dsl import (
    CompletedContractsAtLeast,
    DrawIntrigueCards,
    DrawPersonalCards,
    DuringAgentTurn,
    EffectSection,
    GainInfluenceWhereAtMost,
    GainResources,
    GainVictoryPoints,
    GrantCombatDeployment,
    OnConflictWon,
    OnContractCompleted,
    SpyRecalledThisTurn,
    TrashPersonalCard,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import TECH_DISCOUNT_KEY, TECH_PAYMENT_KEY
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.action_shapes import PRINTER_KEY, Source, printer_value
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import credit_trash_recruits, trash_personal_card
from dune_imperium.rules.combat import add_late_windtraps_row
from dune_imperium.rules.combat_deployment import grant_combat_icon
from dune_imperium.rules.conditions import spice_must_flow_copies
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    BOARD_ICON_TECH,
    OptionalBlockKind,
    OptionalEffectBlock,
    advance_after_effect,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
    recruit_shortfall_events,
    recruit_troops,
)
from dune_imperium.rules.frames import (
    TECH_ACQUIRE_PENDING_KEY,
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    reveal_is_open_for,
    update_turn_recruits,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event, resources_paid_event
from dune_imperium.rules.immortality import troop_can_join
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    influence_can_rise,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_bottom import (
    begin_intrigue_bottom_pick,
    puttable_intrigue,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.leader_abilities import (
    units_deployment_blocked,
    use_leader_signet_for_tech,
)
from dune_imperium.rules.optional_trash import open_optional_trash, trash_printer
from dune_imperium.rules.ornithopter import (
    has_ornithopter_fleet,
    match_all_battle_icons,
)
from dune_imperium.rules.reveal_turn import (
    TECH_PENDING_KEY,
    add_reveal_optional_sword_strength,
    add_reveal_strength,
    add_units_to_reveal,
    reveal_generated_persuasion,
    tech_reveal_pending,
)
from dune_imperium.rules.shield_wall import destroy_shield_wall
from dune_imperium.rules.spy_moves import spy_placement_frame
from dune_imperium.rules.turn_rows import tech_influence_blocked, tech_influence_lapsed

# Disposal Facility: "[Persuasion 6] or more" (OQ-126).
DISPOSAL_FACILITY_PERSUASION: Final = 6
# Rise of Ix's Flip tiles: Flagship "4 Solari -> troop 3", Training Drones
# "troop 1" (docs/rules/rise-of-ix.md 4).
FLAGSHIP_SOLARI: Final = 4
FLAGSHIP_TROOPS: Final = 3
TRAINING_DRONES_TROOPS: Final = 1
# Rise of Ix's Endgame lines (docs/rules/rise-of-ix.md 4): each is 1 VP
# (Spy Satellites: for each Faction where the owner has 1 or less Influence;
# Holtzman Engine: with at least two The Spice Must Flow, OQ-123; Memocorders:
# with 3 or more Influence on every track).
ENDGAME_TILE_VP: Final = 1
HOLTZMAN_ENGINE_SPICE_MUST_FLOW: Final = 2
MEMOCORDERS_INFLUENCE: Final = 3
SPY_SATELLITES_INFLUENCE: Final = 1
# Rise of Ix's two tiles used by trashing them in their owner's turn
# (docs/rules/rise-of-ix.md 4, ``legal_tech_trash_actions``): Spy Satellites
# "spice 3 + 이 타일 trash -> 1 VP", Sonic Snoopers' Intrigue cycle
# (``rules.intrigue_bottom``).
SPY_SATELLITES_SPICE: Final = 3
SPY_SATELLITES_TRASH_VP: Final = 1
TRASH_ABILITIES: Final = frozenset(
    {TechAbility.SPY_SATELLITES, TechAbility.TRASH_CYCLE_INTRIGUE}
)
_FRAME_LABEL = "Agent-turn effect frame"
_ACQUISITION_LABEL = "Tech acquisition frame"
# Kota Odax's Secret Project: "Whenever you could acquire a Tech tile, you
# may choose this one. It costs 1 less" [Kota Odax of Ix card].
SECRET_PROJECT_DISCOUNT = 1
ALL_POST_IDS = tuple(post.post_id for post in OBSERVATION_POSTS)
_ACQUIRE_TURN_KINDS = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)


def tech_acquire_effect_arguments(
    tile: TechTile, effect: str
) -> tuple[tuple[tuple[str, ActionValue], ...], ...]:
    """All legal argument variants for one acquire icon."""

    base: tuple[tuple[str, ActionValue], ...] = (
        ("effect", effect),
        ("tech_id", tile.tech_id),
    )
    if effect == "influence":
        return tuple(
            tuple(sorted((*base, ("faction", faction.value)))) for faction in Faction
        )
    if effect == "distinct_influence":
        # Shuttle Fleet's "Choose two:" (OQ-114): two different Factions
        # named before either Influence is paid, one action naming both
        # (every ordered pair, so the seat picks them in either order), or
        # the one Faction that can still rise when the other three are at the
        # top (OQ-060).
        return (
            *(
                tuple(
                    sorted(
                        (
                            *base,
                            ("faction", first.value),
                            ("second_faction", second.value),
                        )
                    )
                )
                for first in Faction
                for second in Faction
                if first is not second
            ),
            *(
                tuple(sorted((*base, ("faction", faction.value))))
                for faction in Faction
            ),
        )
    if effect == "intrigue_or_card":
        choices = ("card", "intrigue")
        return tuple(
            tuple(sorted((*base, ("choice", choice)))) for choice in choices
        )
    if effect == "shield_wall":
        return (base, tuple(sorted((*base, ("destroy_shield_wall", True)))))
    return (base,)


def pending_tech_acquire_effects(frame: DecisionFrame) -> tuple[str, ...]:
    """Acquire icons still owed on this turn or Combat acquisition frame."""

    value = dict(frame.context).get(TECH_ACQUIRE_PENDING_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Tech acquire effects must be a string")
    return tuple(key for key in value.split(",") if key)


def _acquire_effect_host(state: GameState, player: int) -> DecisionFrame | None:
    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if frame.kind in _ACQUIRE_TURN_KINDS or (
        frame.kind == FrameKind.TECH_ACQUISITION
        and dict(frame.context).get("acquire_effects_only") is True
    ):
        return frame
    return None


def _queue_acquire_effects(state: GameState, player: int, tile: TechTile) -> GameState:
    if not tile.acquire_effect_keys:
        return state
    frame = _acquire_effect_host(state, player)
    if frame is None:
        # Battlefield Research is played in Combat, outside a player's turn.
        # Reuse the acquisition frame for its purchase's remaining rewards.
        frame = DecisionFrame(
            kind=FrameKind.TECH_ACQUISITION,
            frame_id=f"round:{state.round_number}:player:{player}:tech:{tile.tech_id}:effects",
            decision=PlayerDecision(
                owner=player, prompt="Resolve Tech acquire effects"
            ),
            context=(("acquire_effects_only", True),),
        )
        state = state.push_decision(frame)
    pending = (
        *pending_tech_acquire_effects(frame),
        *(f"{tile.tech_id}:{effect}" for effect in tile.acquire_effect_keys),
    )
    context = dict(frame.context)
    context[TECH_ACQUIRE_PENDING_KEY] = ",".join(pending)
    return replace(
        state, decision_stack=(*state.decision_stack[:-1], with_context(frame, context))
    )


def legal_tech_acquire_effect_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Resolve any owed acquire icon in the owner's chosen order (OQ-098)."""

    frame = _acquire_effect_host(state, player)
    if frame is None:
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = []
    blocked = False
    for key in pending_tech_acquire_effects(frame):
        tech_id, effect = key.split(":")
        tile = TECH_TILES_BY_ID[tech_id]
        blocked = blocked or tech_influence_blocked(key, owner)
        for arguments in tech_acquire_effect_arguments(tile, effect):
            values = dict(arguments)
            if values.get("destroy_shield_wall") and not state.shield_wall_present:
                continue
            # A "choose a Faction" never offers a Faction at the top (OQ-060;
            # user decision 2026-10-17, composed-effects plan 5, rule
            # decision 1, which removes the old exception for these icons).
            if "faction" in values and not influence_can_rise(
                owner, Faction(str(values["faction"]))
            ):
                continue
            if effect == "distinct_influence" and not _names_distinct_pair(
                owner, values
            ):
                continue
            actions.append(
                DomainAction(
                    action_id="resolve_tech_acquire_effect",
                    actor=player,
                    arguments=arguments,
                )
            )
    if blocked and dict(frame.context).get("acquire_effects_only") is True:
        # Outside a turn (Battlefield Research in Combat) no press lapses a
        # blocked Influence: its owner confirms it, as a Conflict reward's
        # (OQ-060, ``resolve_combat_influence_without_faction``).
        actions.append(
            DomainAction(
                action_id="resolve_tech_influence_without_faction", actor=player
            )
        )
    return tuple(actions)


def _names_distinct_pair(owner: PlayerState, values: Mapping[str, ActionValue]) -> bool:
    """Whether a Shuttle Fleet row names the two different Factions "Choose
    two:" takes (OQ-114): both able to rise (OQ-060), or the only one that
    can when the other three sit at the top of their tracks."""

    named = tuple(
        Faction(str(values[key]))
        for key in ("faction", "second_faction")
        if key in values
    )
    rising = tuple(
        faction for faction in Faction if influence_can_rise(owner, faction)
    )
    return len(named) == min(2, len(rising)) and all(
        faction in rising for faction in named
    )


def apply_tech_influence_without_faction(
    state: GameState, action: DomainAction
) -> RuleResult:
    """Confirm the acquire Influences with every Faction at the top: each
    lapses with an event (``turn_rows.tech_influence_lapsed``)."""

    if action not in legal_tech_acquire_effect_actions(state, action.actor):
        raise ValueError("action is not a legal Tech acquire effect")
    player = action.actor
    owner = state.players[player]
    frame = state.decision_stack[-1]
    keys = pending_tech_acquire_effects(frame)
    lapsed = tuple(key for key in keys if tech_influence_blocked(key, owner))
    pending = tuple(key for key in keys if key not in lapsed)
    context = dict(frame.context)
    if pending:
        context[TECH_ACQUIRE_PENDING_KEY] = ",".join(pending)
    else:
        context.pop(TECH_ACQUIRE_PENDING_KEY, None)
    working = replace(
        state, decision_stack=(*state.decision_stack[:-1], with_context(frame, context))
    )
    if not pending:
        working = working.pop_decision()
    return RuleResult(
        state=working,
        events=tuple(
            tech_influence_lapsed(player, state.round_number, key) for key in lapsed
        ),
    )


def tech_cost(
    owner: PlayerState,
    tile: TechTile,
    *,
    discount: int = 0,
    secret_project: bool = False,
    high_council_discount: bool = True,
) -> int:
    """Return the spice the tile costs the owner now.

    The Ixian Embassy takes one off with a High Council seat, a card's Tech
    Discount icon one more, and Kota Odax's Secret Project tile one more;
    "the cost can never be less than 0" [Bloodlines p. 7]. A Rise of Ix tile
    has no Ixian Embassy: ``high_council_discount=False``, and its
    Negotiators returned count in ``discount`` ("비용은 0보다 낮아지지
    않는다", docs/rules/rise-of-ix.md 4, [Rise of Ix p. 4]).
    """

    cost = tile.cost - discount
    if owner.high_council and high_council_discount:
        cost -= HIGH_COUNCIL_TECH_DISCOUNT
    if secret_project:
        cost -= SECRET_PROJECT_DISCOUNT
    return max(cost, 0)


def face_up_tech_ids(state: GameState) -> tuple[str, ...]:
    """Return the face-up tile on top of each non-empty stack, in stack order."""

    return tuple(stack[0] for stack in state.tech_stacks if stack)


def tech_acquisition_frame(
    player: int,
    *,
    discount: int,
    source: str,
    printer: str,
    extra: tuple[tuple[str, ActionValue], ...] = (),
) -> DecisionFrame:
    """Return the frame of a card-granted Acquire Tech with ``discount``;
    ``printer`` is the card that grants it (``action_shapes.printer_value``),
    its refusal's entity (stage B3d-3). ``extra`` is the context a Rise of Ix
    game adds (``ix_acquisition_context``)."""

    return DecisionFrame(
        kind=FrameKind.TECH_ACQUISITION,
        frame_id=f"{source}:tech_acquisition",
        decision=PlayerDecision(owner=player, prompt="Acquire a Tech tile or decline"),
        context=tuple(
            sorted(
                (
                    ("discount", discount),
                    ("player", player),
                    (PRINTER_KEY, printer),
                    ("source", source),
                    *extra,
                )
            )
        ),
    )


def push_tech_acquisition(
    state: GameState,
    player: int,
    *,
    discount: int,
    source: str,
    printer: str,
) -> RuleResult:
    """Open a card-granted Acquire Tech.

    It opens even with no tile left to take (every stack empty and no Secret
    Project): the owner then confirms with ``decline_tech``, the only action
    offered (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도
    모두 결정 창을 연다"; OQ-057 (9) "살 수 없으면 거절만").
    """

    if not (state.config.tech_module or state.config.rise_of_ix):
        raise ValueError("Acquire Tech requires the Tech Module or Rise of Ix")
    extra = ix_acquisition_context(discount) if state.config.rise_of_ix else ()
    return RuleResult(
        state=state.push_decision(
            tech_acquisition_frame(
                player, discount=discount, source=source, printer=printer, extra=extra
            )
        )
    )


def _pending_board_context(
    state: GameState, player: int
) -> dict[str, ActionValue] | None:
    """Return the owner's effect-frame context while its Tech offer is pending.

    Only the Tech Module's Landsraad visit offers one; a Rise of Ix game
    without the module has no such icon on its board (stage P4c-1)."""

    if not state.config.tech_module:
        return None
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if not board_icon_is_pending(context, BOARD_ICON_TECH):
        return None
    return context


def _offer(state: GameState, player: int) -> tuple[int, str] | None:
    """Return (discount, source) of the open Acquire Tech offer, if any."""

    context = _pending_board_context(state, player)
    if context is not None:
        space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
        return 0, f"round:{state.round_number}:player:{player}:board:{space_id}:tech"
    frame = owned_top_frame(state, FrameKind.TECH_ACQUISITION, player)
    if frame is None:
        return None
    frame_context = dict(frame.context)
    if frame_context.get("acquire_effects_only") is True:
        return None
    return (
        context_int(frame_context, "discount", owner=_ACQUISITION_LABEL),
        context_str(frame_context, "source", owner=_ACQUISITION_LABEL),
    )


def tech_candidates(
    state: GameState, owner: PlayerState
) -> tuple[tuple[TechTile, bool], ...]:
    """Return the tiles the owner may choose from: stack tops, then the secret one.

    Each with whether it is the owner's Secret Project. Empty when every
    stack is empty and the owner keeps no Secret Project: an Acquire Tech
    then offers only its refusal, and the page says why
    (``display.unavailable``).
    """

    candidates = [
        (TECH_TILES_BY_ID[tech_id], False) for tech_id in face_up_tech_ids(state)
    ]
    if owner.secret_project_tech_id:
        candidates.append((TECH_TILES_BY_ID[owner.secret_project_tech_id], True))
    return tuple(candidates)


def _acquisition_variants(
    state: GameState,
    owner: PlayerState,
    tile: TechTile,
) -> tuple[tuple[tuple[str, ActionValue], ...], ...]:
    """Return the argument tuples of the tile's acquire choices (beyond ``tech_id``)."""

    if tile.acquire_requires_spy_trash:
        # "You must trash one of your Spies from the board".
        return tuple((("post_id", post_id),) for post_id in owner.spy_post_ids)
    return ((),)


def _affordable_acquisitions(
    state: GameState,
    owner: PlayerState,
    discount: int,
) -> tuple[tuple[TechTile, tuple[tuple[str, ActionValue], ...]], ...]:
    """Return each (tile, extra arguments) the owner can buy now at ``discount``.

    A tile the owner cannot pay for is left out, and so is Advanced Data
    Analysis while no Spy of the owner's is on the board to trash.
    """

    return tuple(
        (tile, variant)
        for tile, secret in tech_candidates(state, owner)
        if owner.resources.spice
        >= tech_cost(owner, tile, discount=discount, secret_project=secret)
        for variant in _acquisition_variants(state, owner, tile)
    )


def tech_acquisition_possible(
    state: GameState,
    owner: PlayerState,
    discount: int,
) -> bool:
    """Whether a card's Acquire Tech at ``discount`` could buy a tile now.

    The play gate of Battlefield Research and Rapid Engineering reads it
    (``effect_interpreter``), with the owner after the card's own cost; the
    Acquire Tech frame offers exactly these tiles
    (``legal_tech_acquisition_actions``).
    """

    if state.config.rise_of_ix:
        return bool(ix_tech_acquisitions(state, owner, discount))
    return state.config.tech_module and bool(
        _affordable_acquisitions(state, owner, discount)
    )


# --- Rise of Ix's Tech tiles (stage P4c-1) ---------------------------------
#
# "Acquire Tech 아이콘이 유일한 길이다. 아이콘마다 Ix board의 세 더미 맨 위
# 앞면 타일 하나를 얻을 수 있다("may"). spice 비용을 내고 supply에 공개로 두고,
# 그 더미의 다음 타일을 앞면으로 뒤집는다. 더미가 비면 고를 것이 줄 뿐이다.
# 개수 제한 없음." (docs/rules/rise-of-ix.md 4, [Rise of Ix p. 4]). The framework
# is the Tech Module's: ``tech_stacks`` (here Ix's three stacks of six, the top
# face up), the acquisition frame, ``_take_tile`` and the acquire effects. A
# Rise of Ix game differs in three ways: the acquisition is a "may" (its
# refusal is always offered), Negotiators returned lower the cost, and there is
# no Ixian Embassy (no High Council discount) and no Secret Project.


def ix_tech_cost(
    owner: PlayerState, tile: TechTile, *, discount: int, negotiators: int
) -> int:
    """The spice an Ix tile costs the owner at a Tech Discount of ``discount``
    with ``negotiators`` of its Negotiators returned.

    "비용은 0보다 낮아지지 않는다. Tech Discount: −1·−2가 붙은 Acquire Tech
    아이콘은 그 한 번의 구매를 깎는다. ... Negotiator를 supply로 돌려 하나에
    spice 1씩 깎는다. Tech Discount와 합칠 수 있다." (docs/rules/rise-of-ix.md
    4, [Rise of Ix p. 4]).
    """

    return tech_cost(
        owner,
        tile,
        discount=discount + negotiators,
        high_council_discount=False,
    )


def _ix_tops(state: GameState) -> tuple[TechTile, ...]:
    return tuple(TECH_TILES_BY_ID[tech_id] for tech_id in face_up_tech_ids(state))


def ix_tech_acquisitions(
    state: GameState, owner: PlayerState, discount: int
) -> tuple[tuple[TechTile, int], ...]:
    """Each (tile, Negotiators returned) the owner can pay for now.

    The face-up top of every non-empty stack; the owner picks the tile and
    how many Negotiators to return, from none up to the most that still
    lowers its cost ("원하는 만큼"; the most over every tile on offer is
    ``core.observation.ix_negotiators_returnable``), and the rest of the price
    is spice it holds.
    """

    return tuple(
        (tile, returned)
        for tile in _ix_tops(state)
        for returned in range(
            min(owner.negotiators, max(tile.cost - discount, 0)) + 1
        )
        if owner.resources.spice
        >= ix_tech_cost(owner, tile, discount=discount, negotiators=returned)
    )


def ix_acquisition_context(discount: int) -> tuple[tuple[str, ActionValue], ...]:
    """The open Acquire Tech's state the seat's own view shows
    (``core.observation.ix_pending_of``): its Tech Discount and its payment
    (spice; Appropriate's Solari is stage P4c's later slice). The Negotiators
    the seat may still return are not kept: the view counts them from the state
    each time (``core.observation.ix_negotiators_returnable``), as an
    acquisition stacked under another must not show the count it opened with."""

    return (
        (TECH_DISCOUNT_KEY, discount),
        (TECH_PAYMENT_KEY, "spice"),
    )


def landsraad_tech_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why a Landsraad visit's pending Acquire Tech offers no tile, or None.

    ``legal_tech_acquisition_actions`` offers exactly the tiles
    ``_affordable_acquisitions`` names (the visit's offer has no refusal,
    OQ-095 (2)); with none, every stack is empty and no Secret Project is
    kept, or Advanced Data Analysis is the only tile the spice reaches and
    no Spy of the owner's is on the board to trash, or no tile is
    affordable (``needed``: the cheapest one's cost now). None when no
    visit's offer is pending for ``player``. The page greys the offer out
    with this (``display.unavailable``).
    """

    if not state.config.tech_module or _pending_board_context(state, player) is None:
        return None
    owner = state.players[player]
    if _affordable_acquisitions(state, owner, 0):
        return None
    candidates = tech_candidates(state, owner)
    if not candidates:
        return OptionalEffectBlock(OptionalBlockKind.TECH_STACKS_EMPTY)
    costs = [
        tech_cost(owner, tile, secret_project=secret) for tile, secret in candidates
    ]
    if any(cost <= owner.resources.spice for cost in costs):
        # Only tiles that need a Spy to trash are in reach.
        return OptionalEffectBlock(OptionalBlockKind.TECH_NEEDS_SPY)
    return OptionalEffectBlock(
        OptionalBlockKind.TECH_UNAFFORDABLE,
        needed=min(costs),
        held=owner.resources.spice,
    )


def legal_tech_acquisition_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every affordable face-up tile (and the Secret Project).

    A card's Tech Discount frame offers its refusal only when no tile is
    affordable; a Landsraad visit's offer never does (it lapses at the turn
    end when left unused).
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not (state.config.tech_module or state.config.rise_of_ix):
        return ()
    offer = _offer(state, player)
    if offer is None:
        return ()
    discount, _ = offer
    owner = state.players[player]
    actions = [DomainAction(action_id="decline_tech", actor=player)]
    if state.config.rise_of_ix:
        # "아이콘마다 ... 하나를 얻을 수 있다("may")" [Rise of Ix p. 4]: the
        # refusal is always there, beside each tile at each number of
        # Negotiators returned that the owner can pay for. A returned count
        # of none is the Tech Module's row, ``negotiators`` is named only
        # for one or more.
        actions.extend(
            DomainAction(
                action_id="acquire_tech",
                actor=player,
                arguments=tuple(
                    sorted(
                        (
                            ("tech_id", tile.tech_id),
                            *((("negotiators", returned),) if returned else ()),
                        )
                    )
                ),
            )
            for tile, returned in ix_tech_acquisitions(state, owner, discount)
        )
        return tuple(actions)
    actions.extend(
        DomainAction(
            action_id="acquire_tech",
            actor=player,
            arguments=tuple(sorted((("tech_id", tile.tech_id), *variant))),
        )
        for tile, variant in _affordable_acquisitions(state, owner, discount)
    )
    if _pending_board_context(state, player) is not None:
        # The Landsraad visit's "may acquire" [Bloodlines p. 7] is an
        # optional effect of the visit: it needs no refusal, and left unused
        # it lapses when the turn ends (OQ-095 (2), user ruling 2026-10-14).
        actions = actions[1:]
    elif len(actions) > 1:
        # A card's Tech Discount icon (Battlefield Research, Rapid
        # Engineering) must be used once the card is played and a tile is
        # affordable (designer ruling, OQ-057); its own frame keeps the
        # refusal only when no tile is affordable.
        actions = actions[1:]
    return tuple(actions)


def _take_tile(
    state: GameState,
    owner: PlayerState,
    tech_id: str,
    *,
    source: str,
) -> tuple[GameState, PlayerState, tuple[GameEvent, ...], bool]:
    """Move the tile from its stack (revealing the next) or the Secret Project."""

    if owner.secret_project_tech_id == tech_id:
        return (
            state,
            replace(
                owner, secret_project_tech_id="", tech_ids=(*owner.tech_ids, tech_id)
            ),
            (),
            True,
        )
    stacks = list(state.tech_stacks)
    events: list[GameEvent] = []
    for index, stack in enumerate(stacks):
        if stack and stack[0] == tech_id:
            stacks[index] = stack[1:]
            if stacks[index]:
                events.append(
                    GameEvent(
                        event_id=f"{source}:{tech_id}:revealed:{stacks[index][0]}",
                        kind="tech_revealed",
                        payload=(("stack", index), ("tech_id", stacks[index][0])),
                    )
                )
            break
    else:
        raise RuntimeError("Tech tile is not on top of a stack")
    return (
        replace(state, tech_stacks=tuple(stacks)),
        replace(owner, tech_ids=(*owner.tech_ids, tech_id)),
        tuple(events),
        False,
    )


def apply_tech_acquisition(state: GameState, action: DomainAction) -> RuleResult:
    """Buy the tile and queue its acquire icons, or decline (OQ-098)."""

    if action not in legal_tech_acquisition_actions(state, action.actor):
        raise ValueError("action is not a legal Tech acquisition choice")
    player = action.actor
    context = _pending_board_context(state, player)
    offer = _offer(state, player)
    if offer is None:
        raise RuntimeError("Tech acquisition lost its offer")
    discount, source = offer

    if action.action_id == "decline_tech":
        event = GameEvent(
            event_id=f"{source}:declined",
            kind="tech_declined",
            payload=(("player", player),),
        )
        if context is not None:
            finish_board_icon(context, BOARD_ICON_TECH)
            return RuleResult(
                state=advance_after_effect(state, context), events=(event,)
            )
        return RuleResult(state=state.pop_decision(), events=(event,))

    arguments = dict(action.arguments)
    tech_id = str(arguments["tech_id"])
    tile = TECH_TILES_BY_ID[tech_id]
    owner = state.players[player]
    secret = owner.secret_project_tech_id == tech_id
    ix = state.config.rise_of_ix
    # Rise of Ix: the Negotiators returned to the supply, one spice off each
    # [Rise of Ix p. 4] (``ix_tech_cost``).
    returned = int(arguments.get("negotiators", 0)) if ix else 0
    cost = (
        ix_tech_cost(owner, tile, discount=discount, negotiators=returned)
        if ix
        else tech_cost(owner, tile, discount=discount, secret_project=secret)
    )
    payload: list[tuple[str, ActionValue]] = [
        ("player", player),
        ("secret_project", secret),
        ("spice", cost),
        ("tech_id", tech_id),
    ]
    if ix:
        payload.append(("negotiators", returned))
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:{tech_id}",
            kind="tech_acquired",
            payload=tuple(sorted(payload)),
        )
    ]
    working, next_owner, reveal_events, _ = _take_tile(
        state, owner, tech_id, source=source
    )
    events.extend(reveal_events)
    if returned:
        next_owner = replace(
            next_owner,
            negotiators=next_owner.negotiators - returned,
            troops_supply=next_owner.troops_supply + returned,
        )
    # The price is Spice spent, not Spice never gained: "If you gained spice
    # this turn" (Leverage) and Harvest Contracts count every gain of the
    # turn [Main p. 16], so the spend is recorded like any other payment.
    next_owner = replace(
        next_owner,
        resources=replace(
            next_owner.resources, spice=next_owner.resources.spice - cost
        ),
        spice_spent_turn=next_owner.spice_spent_turn + cost,
    )

    # --- purchase prerequisite on the owner ---------------------------
    if tile.acquire_requires_spy_trash:
        post_id = str(arguments["post_id"])
        next_owner = replace(
            next_owner,
            spy_post_ids=tuple(
                candidate
                for candidate in next_owner.spy_post_ids
                if candidate != post_id
            ),
            spies_boxed=next_owner.spies_boxed + 1,
        )
        events.append(
            GameEvent(
                event_id=f"{source}:{tech_id}:spy_trashed:{post_id}",
                kind="spy_trashed",
                payload=(("player", player), ("post_id", post_id)),
            )
        )
    if has_ornithopter_fleet(next_owner):
        # Acquiring the Fleet (or any tile while holding it) matches at once
        # [Bloodlines p. 12].
        next_owner, match_events = match_all_battle_icons(
            next_owner, source=f"{source}:{tech_id}"
        )
        events.extend(match_events)
    players = replace_player(working.players, next_owner)
    working = replace(working, players=players)

    # --- frame bookkeeping ------------------------------------------------
    if context is not None:
        finish_board_icon(context, BOARD_ICON_TECH)
        working = advance_after_effect(working, context, players)
    else:
        # A card-granted Acquire Tech (a Plot) returns to the turn it was
        # played in, before or after the placement or in a Reveal: its troops
        # join that turn's recruits, since "그 turn에 어떤 출처에서 recruit했든
        # 새 troop은 Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4].
        working = working.pop_decision()

    working = _queue_acquire_effects(working, player, tile)
    if has_tech((tech_id,), TechAbility.CONFLICT_WIN_WATER):
        # Windtraps taken in the winner's own Conflict reward (a Freighter's
        # Acquire Tech) still pays this win's water (docs/rules/rise-of-ix.md
        # 12).
        working = add_late_windtraps_row(working, player)
    return RuleResult(state=working, events=tuple(events))


def apply_tech_acquire_effect(state: GameState, action: DomainAction) -> RuleResult:
    """Pay exactly one already acquired icon, with its choices made now.

    docs/rules/bloodlines.md: "획득 효과의 각 아이콘은 그 turn 안에서 다른
    효과와 원하는 순서로 해결한다" [Bloodlines p. 7] [Main p. 9], user
    ruling OQ-098. The purchase's prerequisite and passive ability have
    already taken effect; the tile need not still be in the owner's supply.
    """

    if action not in legal_tech_acquire_effect_actions(state, action.actor):
        raise ValueError("action is not a legal Tech acquire effect")
    player = action.actor
    arguments = dict(action.arguments)
    tech_id = str(arguments["tech_id"])
    effect = str(arguments["effect"])
    tile = TECH_TILES_BY_ID[tech_id]
    frame = state.decision_stack[-1]
    key = f"{tech_id}:{effect}"
    pending = tuple(
        entry for entry in pending_tech_acquire_effects(frame) if entry != key
    )
    context = dict(frame.context)
    if pending:
        context[TECH_ACQUIRE_PENDING_KEY] = ",".join(pending)
    else:
        context.pop(TECH_ACQUIRE_PENDING_KEY, None)
    working = replace(
        state, decision_stack=(*state.decision_stack[:-1], with_context(frame, context))
    )
    if not pending and context.get("acquire_effects_only") is True:
        working = working.pop_decision()
    source = (
        f"round:{state.round_number}:player:{player}:tech:{tech_id}:acquire:{effect}"
    )
    # What the icon gained rides on its event (rule decision 4: VP, like any
    # amount gained, is a key of the source event's payload).
    amounts = {
        "solari": tile.acquire_solari if effect == "solari" else 0,
        "water": tile.acquire_water if effect == "water" else 0,
        "victory_points": (
            tile.acquire_victory_points if effect == "victory_points" else 0
        ),
    }
    events: list[GameEvent] = [
        GameEvent(
            event_id=source,
            kind="tech_acquire_effect_resolved",
            payload=tuple(
                sorted(
                    (
                        ("effect", effect),
                        ("player", player),
                        ("tech_id", tech_id),
                        *((key, amount) for key, amount in amounts.items() if amount),
                    )
                )
            ),
        )
    ]
    owner = working.players[player]
    if effect == "solari":
        owner = replace(
            owner,
            resources=replace(
                owner.resources, solari=owner.resources.solari + tile.acquire_solari
            ),
        )
    if effect == "victory_points":
        owner = replace(
            owner, victory_points=owner.victory_points + tile.acquire_victory_points
        )
    if effect == "water":
        # Windtraps: "water 1" on acquiring it [Rise of Ix p. 4].
        owner = replace(
            owner,
            resources=replace(
                owner.resources, water=owner.resources.water + tile.acquire_water
            ),
        )
    if effect == "troops":
        owner, recruited = recruit_troops(owner, tile.acquire_troops)
        events.extend(
            recruit_shortfall_events(source, player, tile.acquire_troops, recruited)
        )
        working = update_turn_recruits(working, troops_recruited=recruited)
    working = replace(working, players=replace_player(working.players, owner))
    if effect == "shield_wall" and arguments.get("destroy_shield_wall") is True:
        destroyed = destroy_shield_wall(
            working, event_id=f"{source}:shield_wall", source=tech_id
        )
        working = destroyed.state
        events.extend(destroyed.events)
    if effect == "influence":
        faction_value = str(arguments["faction"])
        gained = gain_faction_influence(
            working,
            player,
            Faction(faction_value),
            1,
            event_prefix=f"{source}:influence:{faction_value}",
        )
        working = gained.state
        events.extend(gained.events)
    if effect == "distinct_influence":
        # Shuttle Fleet: both Factions were named before either is paid, so
        # the second pick never saw what the first one drew (OQ-114, OQ-057
        # (4)).
        for key in ("faction", "second_faction"):
            if key not in arguments:
                continue
            faction_value = str(arguments[key])
            gained = gain_faction_influence(
                working,
                player,
                Faction(faction_value),
                1,
                event_prefix=f"{source}:influence:{faction_value}",
            )
            working = gained.state
            events.extend(gained.events)
    if effect == "contracts":
        contracts = begin_contract_gain(
            working, player, tile.acquire_contracts, source=source
        )
        working = contracts.state
        events.extend(contracts.events)
    if effect == "trash":
        working = open_optional_trash(
            working, player, source, printer=trash_printer(Source.TECH, tech_id)
        )
    if effect.startswith("spy_"):
        working = spy_placement_frame(
            working,
            player,
            ALL_POST_IDS,
            source=source,
            printer=printer_value(Source.TECH, tech_id),
            deep_cover=True,
        )
    intrigue = tile.acquire_intrigue if effect == "intrigue" else 0
    cards = tile.acquire_cards if effect == "cards" else 0
    if effect == "intrigue_or_card":
        if arguments["choice"] == "intrigue":
            intrigue = 1
        else:
            cards = 1
    if intrigue:
        drawn = draw_or_queue_intrigue_cards(
            working, player, intrigue, source=f"{source}:intrigue"
        )
        working = drawn.state
        events.extend(drawn.events)
    if cards:
        drawn = draw_or_request_personal_cards(
            working, player, cards, source=f"{source}:draw"
        )
        working = drawn.state
        events.extend(drawn.events)
    if effect == "signet":
        signet = use_leader_signet_for_tech(
            working, player, source=source, advance_agent_frame=False
        )
        working = signet.state
        events.extend(signet.events)
    return RuleResult(state=working, events=tuple(events))

# --- abilities ----------------------------------------------------------------

PLASTEEL_BLADES_CARD_ID = "tech:plasteel_blades"
_TURN_FRAME_KINDS = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)


def _owned_turn_frame(state: GameState, player: int) -> DecisionFrame | None:
    """Return the top frame if it is one of the owner's turn frames."""

    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if (
        frame.kind not in _TURN_FRAME_KINDS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return None
    return frame


def legal_tech_flip_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Offer the owner's unflipped Flip tiles during one of their turns.

    "An ability with this icon is used during one of your turns, and can be
    used only once per round" [Bloodlines p. 7]. Rapid Dropships prints
    "Agent Turn", so its Combat icon is offered after the Agent placement
    only; the other two flip from the turn, Agent-effect or Reveal frame.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not (state.config.tech_module or state.config.rise_of_ix):
        return ()
    frame = _owned_turn_frame(state, player)
    if frame is None:
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = []
    for tech_id in owner.tech_ids:
        tile = TECH_TILES_BY_ID[tech_id]
        if not tile.flips or tech_id in owner.tech_flipped:
            continue
        if tile.ability in IX_FLIP_ABILITIES:
            actions.extend(_ix_flip_actions(state, owner, frame, tile))
            continue
        flip = _flip_ability(tech_id)
        if (
            flip.requirement == DuringAgentTurn()
            and frame.kind != FrameKind.AGENT_EFFECTS
        ):
            continue
        if _grants_combat_icon(flip) and (
            not state.current_conflict_ids or units_deployment_blocked(state, player)
        ):
            continue
        actions.append(
            DomainAction(
                action_id="flip_tech", actor=player, arguments=(("tech_id", tech_id),)
            )
        )
    return tuple(actions)


def apply_tech_flip(state: GameState, action: DomainAction) -> RuleResult:
    """Flip the tile face down and resolve its printed ability."""

    if action not in legal_tech_flip_actions(state, action.actor):
        raise ValueError("action is not a legal Tech flip")
    player = action.actor
    tech_id = str(dict(action.arguments)["tech_id"])
    owner = state.players[player]
    source = f"round:{state.round_number}:player:{player}:tech:{tech_id}:flip"
    flipped = replace(owner, tech_flipped=(*owner.tech_flipped, tech_id))
    events: list[GameEvent] = [
        GameEvent(
            event_id=source,
            kind="tech_flipped",
            payload=(("player", player), ("tech_id", tech_id)),
        )
    ]
    working = replace(state, players=replace_player(state.players, flipped))
    if TECH_TILES_BY_ID[tech_id].ability in IX_FLIP_ABILITIES:
        return _apply_ix_flip(working, action, source, events)
    for line in _flip_ability(tech_id).sections:
        # Spy Drones: "and if you recalled a Spy this turn: trash a card"
        # (OQ-101; the trash icon is optional, like every printed trash).
        if line.condition == SpyRecalledThisTurn() and not (
            working.players[player].spies_recalled_turn > 0
        ):
            continue
        for reward in line.rewards:
            match reward:
                case DrawIntrigueCards(count=count):
                    drawn = draw_or_queue_intrigue_cards(
                        working, player, count, source=source
                    )
                    working = drawn.state
                    events.extend(drawn.events)
                case GrantCombatDeployment():
                    working = grant_combat_icon(working, player)
                case GainResources(solari=solari):
                    seat = working.players[player]
                    seat = replace(
                        seat,
                        resources=replace(
                            seat.resources, solari=seat.resources.solari + solari
                        ),
                    )
                    working = replace(
                        working, players=replace_player(working.players, seat)
                    )
                    # Spy Drones' Solari leaves the one resource-gain event
                    # (user decision 2026-10-17, composed-effects plan 5,
                    # rule decision 3; engine audit 2026-10-22, P11).
                    events.append(resources_gained_event(source, player, solari=solari))
                case TrashPersonalCard():
                    working = open_optional_trash(
                        working,
                        player,
                        source,
                        printer=trash_printer(Source.TECH, tech_id),
                    )
    return RuleResult(state=working, events=tuple(events))


def _ix_flip_actions(
    state: GameState, owner: PlayerState, frame: DecisionFrame, tile: TechTile
) -> tuple[DomainAction, ...]:
    """The rows of one of Rise of Ix's unflipped Flip tiles.

    "뒤집기 아이콘이 있는 능력은 자기 turn(Agent·Reveal) 가운데 라운드에 한 번,
    쓰면 뒷면으로 뒤집고 다음 라운드 Round Start에 되돌린다" [Rise of Ix p. 4]
    [FAQ p. 1] (docs/rules/rise-of-ix.md 4). Training Drones' "troop 1" costs
    nothing. Flagship's "4 Solari -> troop 3" is a paid line, offered only
    when the Solari are there and a troop can join (OQ-071: nothing is paid
    for a recruit that changes nothing). A "discard ->" cost is one hand card
    named in the row (an Intrigue card is not a card here); Holoprojectors'
    draw always changes something, the discarded card being shuffled back at
    worst, as Twisted Discerning's. Invasion Ships' "이번 turn 상대 Agent가 내
    Agent를 막지 않는다" can matter only before the turn's Agent is placed, so
    it is offered on the turn frame, not after the placement or in a Reveal.
    A Reveal turn has revealed the whole hand: no card is left to discard.
    """

    player = owner.player_id
    tech_id = tile.tech_id

    def row(*extra: tuple[str, ActionValue]) -> DomainAction:
        return DomainAction(
            action_id="flip_tech",
            actor=player,
            arguments=tuple(sorted((("tech_id", tech_id), *extra))),
        )

    match tile.ability:
        case TechAbility.FLIP_TROOP:
            return (row(),)
        case TechAbility.FLIP_SOLARI_FOR_TROOPS:
            if owner.resources.solari >= FLAGSHIP_SOLARI and troop_can_join(
                state, owner
            ):
                return (row(),)
            return ()
        case TechAbility.FLIP_DISCARD_FOR_CARD:
            return tuple(row(("card_id", card_id)) for card_id in owner.hand)
        case TechAbility.FLIP_DISCARD_IGNORE_BLOCKS:
            if frame.kind != FrameKind.TURN:
                return ()
            return tuple(row(("card_id", card_id)) for card_id in owner.hand)
    raise ValueError(f"{tech_id}: not a Rise of Ix Flip tile")


def _apply_ix_flip(
    working: GameState,
    action: DomainAction,
    source: str,
    events: list[GameEvent],
) -> RuleResult:
    """Resolve a Rise of Ix Flip tile whose tile is already turned face down
    (``apply_tech_flip``): pay its cost, then its effect."""

    player = action.actor
    arguments = dict(action.arguments)
    tech_id = str(arguments["tech_id"])
    match TECH_TILES_BY_ID[tech_id].ability:
        case TechAbility.FLIP_TROOP:
            working, gained = _flip_recruit(
                working, player, TRAINING_DRONES_TROOPS, source
            )
            events.extend(gained)
        case TechAbility.FLIP_SOLARI_FOR_TROOPS:
            owner = working.players[player]
            paid = replace(
                owner,
                resources=replace(
                    owner.resources, solari=owner.resources.solari - FLAGSHIP_SOLARI
                ),
            )
            working = replace(working, players=replace_player(working.players, paid))
            events.append(resources_paid_event(source, player, solari=FLAGSHIP_SOLARI))
            working, gained = _flip_recruit(working, player, FLAGSHIP_TROOPS, source)
            events.extend(gained)
        case TechAbility.FLIP_DISCARD_FOR_CARD:
            discarded = discard_personal_card_from_hand(
                working, player, str(arguments["card_id"]), source=f"{source}:discard"
            )
            events.extend(discarded.events)
            drawn = draw_or_request_personal_cards(
                discarded.state, player, 1, source=f"{source}:draw"
            )
            working = drawn.state
            events.extend(drawn.events)
            events.append(
                GameEvent(
                    event_id=f"{source}:draw",
                    kind="cards_drawn",
                    payload=(("count", 1), ("player", player)),
                )
            )
        case TechAbility.FLIP_DISCARD_IGNORE_BLOCKS:
            discarded = discard_personal_card_from_hand(
                working, player, str(arguments["card_id"]), source=f"{source}:discard"
            )
            events.extend(discarded.events)
            # The Infiltrate mechanism: spent by the turn's Agent placement,
            # gone when any turn opens (``PlayerState.enemy_agents_ignored_turn``).
            owner = discarded.state.players[player]
            working = replace(
                discarded.state,
                players=replace_player(
                    discarded.state.players,
                    replace(owner, enemy_agents_ignored_turn=True),
                ),
            )
    return RuleResult(state=working, events=tuple(events))


def _flip_recruit(
    state: GameState, player: int, count: int, source: str
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """A Flip tile's "troop" icons: recruit to the garrison, the part the
    supply lacks owed as every recruit's (OQ-030)."""

    owner, recruited = recruit_troops(state.players[player], count)
    working = replace(state, players=replace_player(state.players, owner))
    working = update_turn_recruits(working, troops_recruited=recruited)
    return working, recruit_shortfall_events(source, player, count, recruited)


def _flip_ability(tech_id: str) -> Ability:
    """The tile's Flip record (composed A6b)."""

    (flip,) = (
        record
        for record in TECH_ABILITIES[tech_id]
        if record.timing is AbilityTiming.FLIP
    )
    return flip


def legal_tech_trash_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """The owner's Rise of Ix tiles that are used by trashing them, in their
    own turn.

    "Spy Satellites: spice 3 + 이 타일 trash -> 1 VP(자기 turn에)" and "Sonic
    Snoopers: 이 타일 trash -> Intrigue 몇 장이든 덱 맨 아래로, 그만큼 뽑기"
    (docs/rules/rise-of-ix.md 4, [Rise of Ix p. 10]); "때를 적지 않은 능력은
    자기 turn 가운데 쓴다" [FAQ p. 4], so the turn, Agent-effect or Reveal frame
    offers them. The trash is a cost that must buy something (OQ-071): Spy
    Satellites needs its 3 spice, Sonic Snoopers an Intrigue card it may put
    (a Twisted one is never put, OQ-097).
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not state.config.rise_of_ix or _owned_turn_frame(state, player) is None:
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = []
    for tech_id in owner.tech_ids:
        ability = TECH_TILES_BY_ID[tech_id].ability
        if ability not in TRASH_ABILITIES:
            continue
        if ability is TechAbility.SPY_SATELLITES:
            if owner.resources.spice < SPY_SATELLITES_SPICE:
                continue
        elif not puttable_intrigue(state, player):
            continue
        actions.append(
            DomainAction(
                action_id="trash_tech", actor=player, arguments=(("tech_id", tech_id),)
            )
        )
    return tuple(actions)


def apply_tech_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Trash the tile (the cost), then resolve its ability.

    Spy Satellites pays 3 spice for 1 VP; Sonic Snoopers opens its pick of
    Intrigue cards for the deck's bottom (``rules.intrigue_bottom``). The tile
    goes to the Tech trash zone, as every trashed tile does.
    """

    if action not in legal_tech_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Tech trash")
    player = action.actor
    tech_id = str(dict(action.arguments)["tech_id"])
    owner = state.players[player]
    source = f"round:{state.round_number}:player:{player}:tech:{tech_id}:trash"
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:tech_trashed",
            kind="tech_trashed",
            payload=(("player", player), ("tech_id", tech_id)),
        )
    ]
    trashed = replace(
        owner,
        tech_ids=tuple(held for held in owner.tech_ids if held != tech_id),
        tech_flipped=tuple(held for held in owner.tech_flipped if held != tech_id),
    )
    if TECH_TILES_BY_ID[tech_id].ability is TechAbility.SPY_SATELLITES:
        trashed = replace(
            trashed,
            resources=replace(
                trashed.resources, spice=trashed.resources.spice - SPY_SATELLITES_SPICE
            ),
            # Every spend adds to ``spice_spent_turn`` (``effects``).
            spice_spent_turn=trashed.spice_spent_turn + SPY_SATELLITES_SPICE,
            victory_points=trashed.victory_points + SPY_SATELLITES_TRASH_VP,
        )
        events.append(resources_paid_event(source, player, spice=SPY_SATELLITES_SPICE))
        events.append(
            resources_gained_event(
                source, player, victory_points=SPY_SATELLITES_TRASH_VP
            )
        )
    working = replace(
        state,
        players=replace_player(state.players, trashed),
        tech_trash=(*state.tech_trash, tech_id),
    )
    if TECH_TILES_BY_ID[tech_id].ability is TechAbility.TRASH_CYCLE_INTRIGUE:
        working = begin_intrigue_bottom_pick(working, player, source=source)
    return RuleResult(state=working, events=tuple(events))


def optional_trash_tech_ids() -> tuple[str, ...]:
    """The tiles that print an optional trash: an acquire ``trash`` icon or a
    Flip line's (stage B3c-2b, ``optional_trash.trash_printer``)."""

    return tuple(
        tile.tech_id
        for tile in TECH_TILES
        if "trash" in tile.acquire_effect_keys
        or any(
            isinstance(reward, TrashPersonalCard)
            for record in TECH_ABILITIES[tile.tech_id]
            if record.timing is AbilityTiming.FLIP
            for line in record.sections
            for reward in line.rewards
        )
    )


def _grants_combat_icon(flip: Ability) -> bool:
    return any(
        isinstance(reward, GrantCombatDeployment)
        for line in flip.sections
        for reward in line.rewards
    )


def _reveal_top(state: GameState, player: int) -> DecisionFrame | None:
    """Return the owner's Reveal frame while it is the top decision."""

    return owned_top_frame(state, FrameKind.REVEAL, player)


def legal_tech_reveal_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Offer the Reveal-turn tile effects still pending, in the owner's order.

    Reveal effects resolve in any order the owner likes [Main p. 12], so
    Forbidden Weapons' mandatory choice and Panopticon's Spy wait on the
    Reveal frame until the owner takes them (OQ-044). Panopticon's Spy is
    always offered: the shared ``spy_placement`` frame it opens offers only
    its decline when nothing can be placed, so the owner answers even a Spy
    that cannot be placed (user ruling 2026-09-30, "결정 창 없이 자동으로
    넘어가는 곳도 모두 결정 창을 연다"; with four players it never happens,
    since Advanced Data Analysis boxes at most one Spy). The strength option
    "must lose one Influence with a Faction where you have at least one
    Influence (if possible)" [Bloodlines p. 12]: one action per such
    Faction (with the Alliance recipient when the loss hands a token to
    one of several opponents), or a bare action when the owner has no
    Influence at all.
    """

    if not (state.config.tech_module or state.config.rise_of_ix):
        return ()
    frame = _reveal_top(state, player)
    if frame is None:
        return ()
    pending = tech_reveal_pending(dict(frame.context))
    owner = state.players[player]
    actions: list[DomainAction] = []
    if "disposal_facility" in pending:
        # "Reveal turn: ... 얻은 Persuasion 합계(쓴 것 포함)가 6 이상이면 in play
        # 카드 하나를 trash할 수 있다" (OQ-126, [Disposal Facility tile]): the
        # total only grows, so the rows open the moment it reaches 6, even in
        # the Reveal turn's later steps; a "may" lapses at the turn's end.
        generated = reveal_generated_persuasion(dict(frame.context))
        if generated is not None and generated >= DISPOSAL_FACILITY_PERSUASION:
            actions.extend(
                DomainAction(
                    action_id="trash_disposal_facility_card",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in counted_in_play(owner)
            )
    if "forbidden_weapons" in pending:
        strength: list[DomainAction] = []
        for faction in Faction:
            if influence_amount(owner.influence, faction) == 0:
                continue
            recipients = alliance_recipients_after_influence_loss(
                state, player, faction
            )
            recipient_options: tuple[int | None, ...] = (
                tuple(recipients) if len(recipients) > 1 else (None,)
            )
            for recipient in recipient_options:
                arguments: tuple[tuple[str, ActionValue], ...] = (
                    ("faction", faction.value),
                )
                if recipient is not None:
                    arguments = (("alliance_recipient", recipient), *arguments)
                strength.append(
                    DomainAction(
                        action_id="choose_tech_strength",
                        actor=player,
                        arguments=arguments,
                    )
                )
        if not strength:
            strength.append(
                DomainAction(action_id="choose_tech_strength", actor=player)
            )
        actions.extend(strength)
        actions.append(DomainAction(action_id="choose_tech_trash", actor=player))
    if "panopticon" in pending:
        actions.append(DomainAction(action_id="place_tech_spy", actor=player))
    return tuple(actions)


def apply_disposal_facility_trash(
    state: GameState, action: DomainAction
) -> RuleResult:
    """Disposal Facility: trash one of the owner's cards in play.

    "Reveal Turn: If you have [Persuasion 6] or more, you may trash one of
    your cards in play." [Disposal Facility tile]; the Persuasion is the
    turn's generated total, spent or not (OQ-126). The tile's effect is used
    once a Reveal turn.
    """

    if action not in legal_tech_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Disposal Facility trash")
    player = action.actor
    card_id = str(dict(action.arguments)["card_id"])
    source = f"round:{state.round_number}:player:{player}:reveal:disposal_facility"
    settled = _settle_tech_reveal(state, player, "disposal_facility")
    return credit_trash_recruits(
        trash_personal_card(settled, player, card_id, source=source), player
    )


def _settle_tech_reveal(state: GameState, player: int, tech_id: str) -> GameState:
    """Drop ``tech_id`` from the Reveal frame's pending tile effects."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining = tuple(key for key in tech_reveal_pending(context) if key != tech_id)
    context[TECH_PENDING_KEY] = ",".join(remaining)
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def apply_place_tech_spy(state: GameState, action: DomainAction) -> RuleResult:
    """Panopticon: open the Spy placement on any Observation Post."""

    if action not in legal_tech_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Panopticon Spy placement")
    player = action.actor
    source = f"round:{state.round_number}:player:{player}:reveal:panopticon"
    settled = _settle_tech_reveal(state, player, "panopticon")
    return RuleResult(
        state=spy_placement_frame(
            settled,
            player,
            ALL_POST_IDS,
            source=source,
            printer=printer_value(Source.TECH, "panopticon"),
        )
    )


def apply_tech_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve Forbidden Weapons: swords and an Influence loss, or spice and trash."""

    if action not in legal_tech_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Forbidden Weapons choice")
    player = action.actor
    tech_id = "forbidden_weapons"
    source = f"round:{state.round_number}:player:{player}:reveal:{tech_id}"
    owner = state.players[player]
    settled = _settle_tech_reveal(state, player, tech_id)
    if action.action_id == "choose_tech_trash":
        trashed = replace(
            owner,
            resources=replace(owner.resources, spice=0),
            # The spice gained this turn is the spice now, less the turn's
            # start, plus every spice that left the seat since: a loss counts
            # like a spend, or the loss would cancel later gains. Steersman
            # Y'rkoon's Hungry for Spice counts "only the spice gained in his
            # own Agent or Reveal turn" (OQ-063), and the owner orders the
            # Reveal's effects [Main p. 12], so a gain taken after this trash
            # counts as one taken before (engine audit 2026-10-22, R6).
            spice_spent_turn=owner.spice_spent_turn + owner.resources.spice,
            tech_ids=tuple(held for held in owner.tech_ids if held != tech_id),
            tech_flipped=tuple(held for held in owner.tech_flipped if held != tech_id),
        )
        return RuleResult(
            state=replace(
                settled,
                players=replace_player(settled.players, trashed),
                tech_trash=(*settled.tech_trash, tech_id),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:tech_trashed",
                    kind="tech_trashed",
                    payload=(
                        ("player", player),
                        ("spice", owner.resources.spice),
                        ("tech_id", tech_id),
                    ),
                ),
            ),
        )
    swords = 3
    units = owner.units_in_conflict
    frames = add_reveal_optional_sword_strength(settled.decision_stack, swords)
    next_owner = owner
    if units > 0:
        # The swords count at once with a unit in the Conflict [Main p. 12].
        frames = add_reveal_strength(frames, swords)
        next_owner = replace(owner, combat_strength=owner.combat_strength + swords)
    working = replace(
        settled,
        players=replace_player(settled.players, next_owner),
        decision_stack=frames,
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:strength",
            kind="reveal_strength_gained",
            payload=(("amount", swords), ("player", player)),
        )
    ]
    arguments = dict(action.arguments)
    faction_value = arguments.get("faction")
    if isinstance(faction_value, str):
        recipient = arguments.get("alliance_recipient")
        assert recipient is None or isinstance(recipient, int)
        lost = lose_faction_influence(
            working,
            player,
            Faction(faction_value),
            1,
            event_prefix=f"{source}:lost:{faction_value}",
            alliance_recipient=recipient,
        )
        working = lost.state
        events.extend(lost.events)
    return RuleResult(state=working, events=tuple(events))


def deploy_suspensor_troops(result: RuleResult) -> RuleResult:
    """Suspensor Suits: recruit a troop and deploy it per Intrigue card gained.

    "For each Intrigue card you draw or steal during your turn: troop,
    deploy it to the Conflict" [Suspensor Suits Tech tile]: the troop icon is
    a recruit and the deployment follows it. The draw paths record the cards
    gained by the turn owner in ``suspensor_owed``; this hook pays them out
    after the transition (OQ-042, user re-ruling 2026-10-25, "그래 (가)로
    가자"):

    - each troop the supply holds is recruited and deployed to the Conflict
      (``suspensor_troops_to_conflict``);
    - with deployment banned (Emperor of the Known Universe) the recruited
      troop stays in the garrison -- "You still gain the troop, but it just
      goes to your Garrison instead of deploying." (designer, community FAQ);
    - what the supply cannot cover is recorded on the seat and made up if
      troops return to the supply later in the same player turn
      (``rules.shortfall``, like a recruit's shortfall, OQ-030): as troops
      owed to the Conflict (``ungained_conflict_troops``), or as a plain
      recruit shortfall when they could not deploy anyway. It is logged as a
      recruit shortfall, so the play server's dry run warns about it on the
      step that draws (user ruling 2026-10-02, L2-Q4: "로그 + 클릭 전 경고").
    """

    state = result.state
    if not any(seat.suspensor_owed for seat in state.players):
        return result
    events = list(result.events)
    for seat in state.players:
        if seat.suspensor_owed <= 0:
            continue
        owed = seat.suspensor_owed
        player = seat.player_id
        count = min(owed, seat.troops_supply)
        short = owed - count
        if suspensor_can_deploy(state, player):
            cleared = replace(
                seat,
                suspensor_owed=0,
                ungained_conflict_troops=seat.ungained_conflict_troops + short,
            )
        else:
            cleared = replace(
                seat, suspensor_owed=0, ungained_troops=seat.ungained_troops + short
            )
        state = replace(state, players=replace_player(state.players, cleared))
        source = f"round:{state.round_number}:player:{player}:suspensor_suits"
        if count:
            placed = suspensor_troops_to_conflict(state, player, count, source=source)
            state = placed.state
            events.extend(placed.events)
        events.extend(recruit_shortfall_events(source, player, owed, count))
    return RuleResult(state=state, events=tuple(events))


def suspensor_can_deploy(state: GameState, player: int) -> bool:
    """Whether Suspensor Suits' troops can go to the Conflict now.

    Not while Emperor of the Known Universe bans deployment, and not without
    a Conflict (a player turn always has one; kept as the engine's guard).
    """

    return bool(state.current_conflict_ids) and not units_deployment_blocked(
        state, player
    )


def suspensor_troops_to_conflict(
    state: GameState, player: int, count: int, *, source: str, origin: str = "tech"
) -> RuleResult:
    """Recruit ``count`` troops from ``player``'s supply for Suspensor Suits.

    They are deployed to the Conflict (through the Reveal bookkeeping when the
    owner's Reveal is open); with deployment banned they stay in the garrison
    as this turn's recruits and ``suspensor_deployment_unavailable`` says so
    (OQ-042). The caller checks the supply holds ``count`` troops; the
    shortfall refill (``rules.shortfall``) uses this for the troops it makes
    up, and Double Cross's deployment (``deploy_troops_from_supply``, whose
    ``origin`` is "intrigue") for the troops it deploys.
    """

    seat = state.players[player]
    if count < 1 or count > seat.troops_supply:
        raise ValueError("Suspensor Suits recruits only troops in the supply")
    if not suspensor_can_deploy(state, player):
        recruited = replace(
            seat,
            troops_supply=seat.troops_supply - count,
            troops_garrison=seat.troops_garrison + count,
        )
        state = replace(state, players=replace_player(state.players, recruited))
        state = update_turn_recruits(state, troops_recruited=count)
        return RuleResult(
            state=state,
            events=(_suspensor_garrison_event(source, player, count),),
        )
    events: list[GameEvent] = []
    if reveal_is_open_for(state, player):
        staged = replace(
            seat,
            troops_supply=seat.troops_supply - count,
            troops_garrison=seat.troops_garrison + count,
        )
        state = replace(state, players=replace_player(state.players, staged))
        deployed = add_units_to_reveal(state, player, troops=count)
        state = deployed.state
        events.extend(deployed.events)
    else:
        deployed_seat = replace(
            seat,
            troops_supply=seat.troops_supply - count,
            troops_conflict=seat.troops_conflict + count,
            units_deployed_turn=seat.units_deployed_turn + count,
        )
        state = replace(state, players=replace_player(state.players, deployed_seat))
    events.append(
        GameEvent(
            event_id=f"{source}:deployed",
            kind="troops_deployed",
            payload=(("count", count), ("player", player), ("source", origin)),
        )
    )
    return RuleResult(state=state, events=tuple(events))


def deploy_troops_from_supply(
    state: GameState, player: int, count: int, *, source: str
) -> RuleResult:
    """Deploy ``count`` troops from ``player``'s supply to the Conflict.

    "you deploy one troop from your supply to the Conflict" [Double Cross
    card, app text]: a deployment by a card, needing no Combat icon, joined to
    the Reveal bookkeeping in the owner's Reveal turn and counted as a unit
    deployed this turn (``suspensor_troops_to_conflict``). Nothing deploys
    while deployment is banned (Emperor of the Known Universe, [Main p. 17]).
    A supply that holds fewer deploys what it has, and "my supply may be
    empty" [FAQ p. 2] (imperium-base.md 13.2): the rest is recorded as the
    troops owed to the Conflict (``ungained_conflict_troops``), made up if
    troops return to the supply later in the same player turn
    (``rules.shortfall``, OQ-042 ruling (2): "원판·Ix의 Double Cross·Treachery
    (supply에서 Conflict로 배치)도 같은 기록을 쓴다").
    """

    if count < 1:
        raise ValueError("a deployment moves at least one troop")
    if not suspensor_can_deploy(state, player):
        return RuleResult(state=state)
    seat = state.players[player]
    deployed = min(count, seat.troops_supply)
    short = count - deployed
    if short:
        seat = replace(
            seat, ungained_conflict_troops=seat.ungained_conflict_troops + short
        )
        state = replace(state, players=replace_player(state.players, seat))
    if not deployed:
        return RuleResult(state=state)
    return suspensor_troops_to_conflict(
        state, player, deployed, source=source, origin="intrigue"
    )


def _suspensor_garrison_event(source: str, player: int, troops: int) -> GameEvent:
    """The public event for Suspensor Suits troops kept in the garrison."""

    return GameEvent(
        event_id=f"{source}:unavailable",
        kind="suspensor_deployment_unavailable",
        payload=(
            ("deployed", 0),
            ("player", player),
            ("troops", troops),
        ),
    )


def apply_endgame_tech_effects(state: GameState) -> RuleResult:
    """Pay the Endgame lines of CHOAM Transports and Panopticon.

    "Endgame: worth 1 VP if you have completed four or more contracts"
    [CHOAM Transports Tech tile]; "Endgame: gain 1 Influence with each
    Faction where you have 1 or less Influence" [Panopticon Tech tile].
    Resolved as the Endgame opens, before the Endgame Intrigue window
    (project convention, OQ-040).
    """

    events: list[GameEvent] = []
    for seat in state.players:
        player = seat.player_id
        source = f"round:{state.round_number}:player:{player}:endgame_tech"
        for tile, line in _ENDGAME_LINES:
            if not has_tech(seat.tech_ids, tile.ability):
                continue
            match line:
                case EffectSection(
                    rewards=(GainVictoryPoints(amount=amount),),
                    condition=CompletedContractsAtLeast(count=count),
                ):
                    if len(seat.completed_contract_ids) < count:
                        continue
                    scored = replace(seat, victory_points=seat.victory_points + amount)
                    state = replace(
                        state, players=replace_player(state.players, scored)
                    )
                    events.append(
                        resources_gained_event(
                            f"{source}:{tile.tech_id}", player, victory_points=amount
                        )
                    )
                case EffectSection(
                    rewards=(GainInfluenceWhereAtMost(maximum=maximum),),
                    condition=None,
                ):
                    for faction in Faction:
                        if (
                            influence_amount(state.players[player].influence, faction)
                            > maximum
                        ):
                            continue
                        gained = gain_faction_influence(
                            state,
                            player,
                            faction,
                            1,
                            event_prefix=f"{source}:{tile.tech_id}:{faction.value}",
                        )
                        state = gained.state
                        events.extend(gained.events)
        # Rise of Ix's tiles, after the Tech Module's (OQ-040's convention:
        # as the Endgame opens, before the Endgame Intrigue window).
        for tech_id, points in ix_endgame_points(state.players[player]):
            scored = replace(
                state.players[player],
                victory_points=state.players[player].victory_points + points,
            )
            state = replace(state, players=replace_player(state.players, scored))
            events.append(
                resources_gained_event(
                    f"{source}:{tech_id}", player, victory_points=points
                )
            )
    return RuleResult(state=state, events=tuple(events))


def ix_endgame_points(owner: PlayerState) -> tuple[tuple[str, int], ...]:
    """The Victory Points each of Rise of Ix's Endgame tiles the owner holds
    pays now, as (tile, VP) pairs for the ones that pay (docs/rules/
    rise-of-ix.md 4), in the table's order.

    - Holtzman Engine, "Endgame: The Spice Must Flow 2장 이상이면 1 VP": the
      copies counted as OQ-123 rules (deck, hand, discard pile and in play;
      not trashed).
    - Memocorders, "Endgame: 네 track 모두 Influence 3 이상이면 1 VP".
    - Spy Satellites, "Endgame: Influence 1 이하인 진영마다 1 VP".

    Chaumurky's "동률을 이긴다" pays nothing; it is the first tie-break of
    ``rules.endgame``.
    """

    points: list[tuple[str, int]] = []
    if has_tech(owner.tech_ids, TechAbility.HOLTZMAN_ENGINE) and (
        spice_must_flow_copies(owner) >= HOLTZMAN_ENGINE_SPICE_MUST_FLOW
    ):
        points.append(("holtzman_engine", ENDGAME_TILE_VP))
    if has_tech(owner.tech_ids, TechAbility.ENDGAME_INFLUENCE_THREE_VP) and all(
        influence_amount(owner.influence, faction) >= MEMOCORDERS_INFLUENCE
        for faction in Faction
    ):
        points.append(("memocorders", ENDGAME_TILE_VP))
    if has_tech(owner.tech_ids, TechAbility.SPY_SATELLITES):
        low = sum(
            influence_amount(owner.influence, faction) <= SPY_SATELLITES_INFLUENCE
            for faction in Faction
        )
        if low:
            points.append(("spy_satellites", ENDGAME_TILE_VP * low))
    return tuple(points)


# The tiles' Endgame lines in tile order (composed A6b): CHOAM Transports'
# VP before Panopticon's Influence, as the Endgame opens (OQ-040).
_ENDGAME_LINES: Final = tuple(
    (tile, line)
    for tile in TECH_TILES
    for record in TECH_ABILITIES[tile.tech_id]
    if record.timing is AbilityTiming.ENDGAME
    for line in record.sections
)
# The tiles' abilities whose flow stays code (composed A6b): Plasteel
# Blades, Suspensor Suits, Forbidden Weapons and Panopticon's Reveal;
# Advanced Data Analysis' Spy prerequisite (A6a).
TECH_HOOKS: Final = frozenset(
    {
        TRASH_SPY_TO_ACQUIRE,
        "plasteel_blades",
        "suspensor_suits",
        "forbidden_weapons",
        "panopticon_reveal",
    }
)


def _check_tech_records() -> None:
    """Refuse a record the Flip, Endgame and hook code cannot resolve."""

    for tech_id, records in TECH_ABILITIES.items():
        for record in records:
            if record.timing is AbilityTiming.STANDING:
                if record.sections or record.hook is None:
                    raise ValueError(f"{tech_id}: a standing record names its branch")
                continue
            if record.hook is not None:
                if record.hook not in TECH_HOOKS:
                    raise ValueError(f"{tech_id}: unknown hook {record.hook!r}")
                continue
            if record.timing is AbilityTiming.FLIP:
                flips = [r for r in records if r.timing is AbilityTiming.FLIP]
                if (
                    len(flips) > 1
                    or record.mark is not AbilityMark.OPTIONAL
                    or record.structure is not AbilityStructure.SEQUENCE
                ):
                    raise ValueError(f"{tech_id}: one optional Flip, every line")
                if record.requirement not in (None, DuringAgentTurn()):
                    raise ValueError(f"{tech_id}: no such Flip requirement")
                for line in record.sections:
                    if line.costs or line.condition not in (
                        None,
                        SpyRecalledThisTurn(),
                    ):
                        raise ValueError(f"{tech_id}: no such Flip line")
                    for reward in line.rewards:
                        if not (
                            isinstance(
                                reward, (DrawIntrigueCards, GrantCombatDeployment)
                            )
                            or (
                                isinstance(reward, GainResources)
                                and reward.spice == reward.water == 0
                            )
                            or reward == TrashPersonalCard()
                        ):
                            raise ValueError(f"{tech_id}: no such Flip reward")
            elif record.timing is AbilityTiming.ENDGAME:
                if record.requirement is not None or record.trigger is not None:
                    raise ValueError(f"{tech_id}: an Endgame line checks itself")
                for line in record.sections:
                    match line:
                        case EffectSection(
                            rewards=(GainVictoryPoints(),),
                            condition=CompletedContractsAtLeast(),
                            costs=(),
                        ):
                            pass
                        case EffectSection(
                            rewards=(GainInfluenceWhereAtMost(),),
                            condition=None,
                            costs=(),
                        ):
                            pass
                        case _:
                            raise ValueError(f"{tech_id}: no such Endgame line")
            elif record.timing is AbilityTiming.TRIGGERED:
                # CHOAM Transports' and Planetary Array's draws, one card owed
                # or held (``tech_draw_on``, composed A6e).
                if not isinstance(
                    record.trigger, (OnContractCompleted, OnConflictWon)
                ) or record.sections != (
                    EffectSection(rewards=(DrawPersonalCards(1),)),
                ):
                    raise ValueError(f"{tech_id}: no such Tech trigger")
            elif record.timing is not AbilityTiming.REVEAL:
                # The automatic Reveal lines are checked on load
                # (``tech.tech_reveal_line``).
                raise ValueError(
                    f"{tech_id}: no {record.timing} ability without a hook"
                )


_check_tech_records()


def draw_owed_tech_cards(result: RuleResult) -> RuleResult:
    """Draw the cards CHOAM Transports and Planetary Array owe after a step.

    Both tiles pay inside another effect's resolution (a contract
    completion, the Conflict card's award), where a discard reshuffle could not be
    pushed safely; the owing seat records the count and this hook draws
    once the transition has settled. A pending chance frame defers it to
    the next transition, like Hungry for Spice.

    Round Start defers it too. Its order is reveal, then any Control
    defense, then "each player draws five cards from their own deck"
    [Main p. 8] [Main p. 20], and the Round Start reshuffle has already put
    the discard pile beneath the deck for exactly that draw
    (``phases.prepare_round_start``). A card drawn while the defense is
    open would come out of the round's hand and leave the deck short of
    five, which the draw rejects. So the owed card waits for the draw's
    transition and comes after the hand, as it did when the reveal and the
    draw were one transition (OQ-072).
    """

    state = result.state
    if not any(seat.tech_cards_owed for seat in state.players):
        return result
    if state.phase is GamePhase.ROUND_START:
        return result
    if state.decision_stack and isinstance(
        state.decision_stack[-1].decision, ChanceDecision
    ):
        return result
    events = list(result.events)
    for seat in state.players:
        if seat.tech_cards_owed <= 0:
            continue
        owed = seat.tech_cards_owed
        cleared = replace(seat, tech_cards_owed=0)
        state = replace(state, players=replace_player(state.players, cleared))
        drawn = draw_or_request_personal_cards(
            state,
            seat.player_id,
            owed,
            source=f"round:{state.round_number}:player:{seat.player_id}:tech_draw",
        )
        state = drawn.state
        events.extend(drawn.events)
        if state.decision_stack and isinstance(
            state.decision_stack[-1].decision, ChanceDecision
        ):
            # One reshuffle at a time; the next seat waits for the next step.
            break
    return RuleResult(state=state, events=tuple(events))


# --- Kota Odax of Ix: Secret Project ----------------------------------------------


def assign_secret_project(state: GameState) -> GameState:
    """Open Kota Odax's game-start pick of a bottom Tech tile.

    "Game Start: Peek at the bottom Tech tile of each stack. Place one face
    down here" [Kota Odax of Ix card]. The frame pauses the game in SETUP
    (like the Navigation setup) until the owner has chosen.
    """

    if not state.config.tech_module or not any(state.tech_stacks):
        return state
    seat = next(
        (
            candidate
            for candidate in state.players
            if candidate.leader_id == "kota_odax_of_ix"
        ),
        None,
    )
    if seat is None or seat.secret_project_tech_id:
        return state
    candidates = tuple(stack[-1] for stack in state.tech_stacks if stack)
    frame = DecisionFrame(
        kind=FrameKind.TECH_SECRET_PROJECT,
        frame_id=f"setup:secret_project:{seat.player_id}",
        decision=PlayerDecision(
            owner=seat.player_id,
            prompt="Secret Project: place one bottom Tech tile on your Leader",
        ),
        context=(
            ("candidates", ",".join(candidates)),
            ("player", seat.player_id),
            ("resume_phase", state.phase.value),
        ),
    )
    return replace(
        state, phase=GamePhase.SETUP, decision_stack=(*state.decision_stack, frame)
    )


def legal_secret_project_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Offer the bottom tile of each stack (the owner alone sees them)."""

    frame = owned_top_frame(state, FrameKind.TECH_SECRET_PROJECT, player)
    if frame is None:
        return ()
    candidates = context_str(
        dict(frame.context), "candidates", owner="Secret Project frame"
    )
    return tuple(
        DomainAction(
            action_id="choose_secret_project",
            actor=player,
            arguments=(("tech_id", tech_id),),
        )
        for tech_id in candidates.split(",")
        if tech_id
    )


def apply_secret_project(state: GameState, action: DomainAction) -> RuleResult:
    """Move the chosen bottom tile face down onto Kota Odax's Leader card."""

    if action not in legal_secret_project_actions(state, action.actor):
        raise ValueError("action is not a legal Secret Project choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    tech_id = str(dict(action.arguments)["tech_id"])
    stacks = tuple(
        stack[:-1] if stack and stack[-1] == tech_id else stack
        for stack in state.tech_stacks
    )
    owner = state.players[action.actor]
    chosen = replace(owner, secret_project_tech_id=tech_id)
    resume = GamePhase(
        context_str(context, "resume_phase", owner="Secret Project frame")
    )
    return RuleResult(
        state=replace(
            state,
            phase=resume,
            tech_stacks=stacks,
            players=replace_player(state.players, chosen),
            decision_stack=state.decision_stack[:-1],
        ),
        events=(
            # The identity is the owner's; everyone sees that a tile left.
            GameEvent(
                event_id=f"{frame.frame_id}:chosen",
                kind="secret_project_chosen",
                payload=(("player", action.actor),),
            ),
            GameEvent(
                event_id=f"{frame.frame_id}:identity",
                kind="secret_project_identity",
                payload=(("player", action.actor), ("tech_id", tech_id)),
                visible_to=(action.actor,),
            ),
        ),
    )
