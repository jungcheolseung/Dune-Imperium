"""Decision-frame kinds and shared frame/context helpers for rule modules."""

from copy import replace
from enum import StrEnum

from dune_imperium.content.uprising.effect_dsl import OnSpiceGainedInTurnAtLeast
from dune_imperium.content.uprising.leader_abilities import leader_triggers
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState

type FrameContext = dict[str, ActionValue]


class FrameKind(StrEnum):
    """Every decision frame the Uprising rules currently push."""

    TURN = "turn"
    AGENT_EFFECTS = "agent_effects"
    OPPONENT_CARD_DISCARD = "opponent_card_discard"
    ACQUISITION_SPY = "acquisition_spy"
    REVEAL = "reveal"
    REVEAL_CHOICE = "reveal_choice"
    CONTRACT_MARKET = "contract_market"
    CONTRACT_REWARD_SPY = "contract_reward_spy"
    CONTRACT_REWARD_RECALL = "contract_reward_recall"
    CONTRACT_INTRIGUE_TRASH = "contract_intrigue_trash"
    CONTROL_DEFENSE = "control_defense"
    COMBAT_INTRIGUE = "combat_intrigue"
    COMBAT_REWARD_INFLUENCE = "combat_reward_influence"
    COMBAT_REWARD_DISTINCT_INFLUENCE = "combat_reward_distinct_influence"
    COMBAT_REWARD_OPTIONAL = "combat_reward_optional"
    COMBAT_REWARD_SPY_RECALL = "combat_reward_spy_recall"
    COMBAT_REWARD_TRASH = "combat_reward_trash"
    CONFLICT_END_TRIGGER = "conflict_end_trigger"
    COMBAT_REWARD_SPY = "combat_reward_spy"
    ENDGAME_INTRIGUE = "endgame_intrigue"
    ROUND_START_RESHUFFLE = "round_start_reshuffle"
    PERSONAL_DRAW_RESHUFFLE = "personal_draw_reshuffle"
    INTRIGUE_RESHUFFLE = "intrigue_reshuffle"
    INTRIGUE_CHOICE = "intrigue_choice"
    INTRIGUE_EFFECTS = "intrigue_effects"
    # No longer opened: Distraction was a face-up trigger until codec v129
    # (OQ-016). Kept so every later kind keeps its observation index.
    INTRIGUE_TRIGGER_SPY = "intrigue_trigger_spy"
    LEADER_DRAFT = "leader_draft"
    SECRETS_STEAL = "secrets_steal"
    # Sardaukar Standard's Skill choice for the Commander it acquires.
    SKILL_CHOICE = "skill_choice"
    # Bloodlines opponent decisions: a Spy forced off a post (Holy War,
    # False Orders) and a unit lost from a chosen zone (Holy War).
    OPPONENT_SPY_MOVE = "opponent_spy_move"
    OPPONENT_UNIT_LOSS = "opponent_unit_loss"
    # False Orders: the owner's Spy placement on the turn's board space.
    SPY_PLACEMENT = "spy_placement"
    # Coercive Negotiation: three Contracts revealed from the bank.
    INTRIGUE_TRIGGER_CONTRACT = "intrigue_trigger_contract"
    # An optional "[trash] icon" reward (Liet Kynes' sandworm replacement).
    OPTIONAL_TRASH = "optional_trash"
    # Steersman Y'rkoon: choosing the four Navigation slots at setup, and
    # choosing how to play the next Navigation card.
    NAVIGATION_SETUP = "navigation_setup"
    NAVIGATION_CHOICE = "navigation_choice"
    # Tech Module: a card-granted Acquire Tech (with its discount) and Kota
    # Odax's Secret Project pick.
    TECH_ACQUISITION = "tech_acquisition"
    TECH_SECRET_PROJECT = "tech_secret_project"
    # Immortality: the research token's direction choice and the optional
    # or chosen bonuses of a research space [Immortality p. 6].
    RESEARCH_ADVANCE = "research_advance"
    RESEARCH_BONUS = "research_bonus"
    # Immortality Graft: choosing the second card of a two-card play.
    GRAFT_PARTNER = "graft_partner"
    # Imperium Ceremony: keep one of the Intrigue deck's top two cards.
    INTRIGUE_PEEK = "intrigue_peek"
    # Long Live the Fighters: the atomic draw-then-discard pick over the top
    # three personal cards. It owns a frame rather than a flag on the Agent
    # effect frame so the exclusivity is structural: while the pick is open no
    # other Agent-turn effect is offered, because the effect frame is not on
    # top of the stack.
    LONG_LIVE_FIGHTERS = "long_live_fighters"
    # Servo-Receivers' acquire effect: the Leader's Signet Ring ability used
    # without the Signet Ring card, so outside its Agent box (appended last:
    # the observation encodes the frame kind by its index).
    LEADER_SIGNET = "leader_signet"
    # Arrakeen Scouts: a chance draw of the round's schedule (appended last,
    # like every kind: the observation encodes the kind by its index).
    SCOUTS_DRAW = "scouts_draw"
    # Friends Everywhere: which Faction's Influence 4 bonus to take.
    SCOUTS_FOUR_BONUS = "scouts_four_bonus"
    # One seat's cost -> reward line of a Scouts item, and the list of
    # subcommittees a new High Council seat opens with choose_subcommittee.
    SCOUTS_EFFECT = "scouts_effect"
    SCOUTS_SUBCOMMITTEE = "scouts_subcommittee"
    # One seat's turn-order pick among an event's or sale's lines.
    SCOUTS_CHOICE = "scouts_choice"
    # A seat's answer to a mission: take part or pass.
    SCOUTS_MISSION = "scouts_mission"
    # A seat's secret pick of a Covert or Offworld Operation line.
    SCOUTS_SECRET = "scouts_secret"
    # Auctions: a sealed bid (pick, then confirm), Mercenaries' retreat, an
    # open call in Critical Moment and its winner's purchase.
    SCOUTS_BID = "scouts_bid"
    SCOUTS_RETREAT = "scouts_retreat"
    SCOUTS_CALL = "scouts_call"
    SCOUTS_MARKET = "scouts_market"
    # A pause before a reveal that follows a seat's choices outside the
    # turns (rules/pauses.py): a chance decision with one fixed outcome.
    # Appended last, like every kind. It is never on top at a player
    # decision, so no observation shows it.
    PAUSE = "pause"
    # A Conflict reward recipient's window over its reward's icons, one row
    # each in any order (stage B2, OQ-112; ``rules/combat.py``).
    COMBAT_REWARD_ICONS = "combat_reward_icons"
    # A completed Contract's reward icons, one row each in any order (stage
    # B2, OQ-112; ``rules/contracts.py``).
    CONTRACT_REWARD_ICONS = "contract_reward_icons"
    # The original game's Baron Harkonnen chooses his two Masterstroke
    # Factions in secret before the first round (``rules/masterstroke.py``).
    MASTERSTROKE_SETUP = "masterstroke_setup"
    # Rise of Ix (observation v39, stage P4a; docs/rules/rise-of-ix.md 14):
    # reserved for the decisions of stages P4b to P4e that no frame above
    # holds, appended last so every older kind keeps its observation index.
    # No engine path opens them yet (``LEGAL_ACTION_PROVIDERS`` names none,
    # so a pushed one fails loudly).
    # A Freighter icon resolved where it is no row of its owner's turn (a
    # Conflict reward's, Skirmish or Trade Monopoly [FAQ p. 3]): move up one
    # space, recall, or neither [Rise of Ix p. 5] -- an icon whose answer
    # is a choice opens a window of its own there, as ``choose_influence``
    # or an optional payment do (``rules/combat.py``).
    FREIGHTER_MOVE = "freighter_move"
    # A Shipping track recall's rewards outside its owner's turn, one row
    # each in any order [Rise of Ix p. 5], as a Contract's reward has its
    # window outside its owner's turn (``CONTRACT_REWARD_ICONS``).
    SHIPPING_REWARD_ICONS = "shipping_reward_icons"
    # The Conflict winner's dreadnought: the Control space without a
    # dreadnought it must take [Rise of Ix p. 6], or Detonation Devices'
    # VP instead (OQ-121), answering that row of the winner's window.
    DREADNOUGHT_CONTROL_CHOICE = "dreadnought_control_choice"
    # Ilesa Ecaz's One Step Ahead: the hand card set aside face down at
    # Round Start, after the draw (OQ-122) [Ilesa Ecaz card]; no Round
    # Start frame picks a hand card, and a discard goes face up.
    ROUND_START_SET_ASIDE = "round_start_set_aside"
    # An Unload card's Reveal box gained outside its owner's turn, when an
    # opponent's effect discards it [Rise of Ix p. 7] or a Combat reward
    # trashes it (OQ-127): one row each in any order, its choices and costs
    # with them, as ``CONTRACT_REWARD_ICONS`` holds a reward box.
    UNLOAD_ICONS = "unload_icons"
    # An optional "[discard] ->" cost outside its owner's turn: a hand card
    # (no Intrigue) or none [Rise of Ix p. 7] -- Tessia Vernius' first
    # Snooper reward, "discard -> 1 spice" [Tessia Vernius card], reached
    # through an Influence gained in Combat. The discard counterpart of
    # ``OPTIONAL_TRASH``, whose window also serves only outside the turn.
    OPTIONAL_DISCARD = "optional_discard"
    # Sonic Snoopers: "Put any number of your Intrigue cards on the bottom of
    # the Intrigue deck, then draw that many" [Sonic Snoopers Tech tile] --
    # one card at a time in the order chosen (the seat knows that order,
    # plan 17.8 review item 6) until it stops, then the draw; a pick of
    # its own, as ``LONG_LIVE_FIGHTERS``, so no other effect interleaves.
    # Court Intrigue's single card is a row with one target, no window.
    INTRIGUE_BOTTOM_PICK = "intrigue_bottom_pick"


# The kinds observation v39 reserved for Rise of Ix (stage P4a), in order.
IX_FRAME_KINDS: tuple[FrameKind, ...] = (
    FrameKind.FREIGHTER_MOVE,
    FrameKind.SHIPPING_REWARD_ICONS,
    FrameKind.DREADNOUGHT_CONTROL_CHOICE,
    FrameKind.ROUND_START_SET_ASIDE,
    FrameKind.UNLOAD_ICONS,
    FrameKind.OPTIONAL_DISCARD,
    FrameKind.INTRIGUE_BOTTOM_PICK,
)


def top_frame(state: GameState) -> DecisionFrame | None:
    """Return the current decision frame, if any."""

    return state.decision_stack[-1] if state.decision_stack else None


def top_frame_of_kind(state: GameState, kind: FrameKind) -> DecisionFrame | None:
    """Return the current frame only when it has ``kind``."""

    frame = top_frame(state)
    return frame if frame is not None and frame.kind == kind else None


def owned_top_frame(
    state: GameState,
    kind: FrameKind,
    player: int,
) -> DecisionFrame | None:
    """Return the current frame when ``player`` owns a ``kind`` player decision."""

    if not 0 <= player < state.config.players:
        return None
    frame = top_frame_of_kind(state, kind)
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return None
    return frame


def frame_context(frame: DecisionFrame) -> FrameContext:
    """Return a mutable copy of the frame's context."""

    return dict(frame.context)


def with_context(frame: DecisionFrame, context: FrameContext) -> DecisionFrame:
    """Return ``frame`` carrying ``context`` in canonical sorted order."""

    return replace(frame, context=tuple(sorted(context.items())))


def replace_top_frame(state: GameState, frame: DecisionFrame) -> GameState:
    """Return a state whose top frame is replaced by ``frame``."""

    if not state.decision_stack:
        raise IndexError("cannot replace the top of an empty decision stack")
    return replace(state, decision_stack=(*state.decision_stack[:-1], frame))


def context_int(context: FrameContext, key: str, *, owner: str = "frame") -> int:
    """Read a required non-bool integer from a frame context."""

    value = context.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{owner} has invalid {key}")
    return value


COMMANDERS_RECRUITED_KEY = "commanders_recruited"
"""Sardaukar Commanders recruited this turn, kept apart from the troops on
the Agent-turn effect frame and on the turn frame before the placement
(absent means none): each reserves a deploy slot for a Commander (OQ-070)."""

REVEAL_COMMANDERS_RECRUITED_KEY = "reveal_commanders_recruited"
"""The Reveal frame's Commanders recruited this turn (absent means none)."""

DREADNOUGHTS_COMMISSIONED_KEY = "dreadnoughts_commissioned"
"""Rise of Ix dreadnoughts commissioned this Agent turn, kept on the Agent-turn
effect frame and on the turn frame before the placement (absent means none),
apart from the troops and the Commanders: "If you commissioned the dreadnought
while sending an Agent to a Combat space, you may deploy it to the Conflict"
[Rise of Ix p. 6], and each reserves a deploy slot for a dreadnought outside
the garrison share of two (docs/base-game-and-ix-plan.md 17.6 item 2). A Reveal
turn has no such window, so nothing is kept there."""


SHIPPING_TROOPS_KEY = "shipping_troops_recruited"
"""Troops a Shipping track recruit brought in with Troop Transports in this
Agent turn, kept on the Agent-turn effect frame and on the turn frame before
the placement (absent means none), apart from the other recruits: "You may
deploy any of them to the Conflict" lets every one deploy even where the Agent
went to no Combat space (docs/rules/rise-of-ix.md 15), each with a slot of its
own and none of the garrison share of two (``combat_deployment``). In a
Combat-space turn they are plain recruits of the turn, and a Reveal turn keeps
them as ``combat_deployment.RECRUITS_DEPLOYABLE_KEY``."""

UNGAINED_SHIPPING_TROOPS_KEY = "shipping_troops_ungained"
"""The part of the owner's recruit shortfall (``PlayerState.ungained_troops``,
OQ-030) that a Shipping track recruit with Troop Transports could not get from
the supply, kept on the turn's own frame (absent means none). A refill gives
them as the turn's recruits, so each one joins ``SHIPPING_TROOPS_KEY``'s
allowance as the refill pays it (``combat_deployment.refill_shipping_troops``),
and the frame carries the count over the placement and into the Reveal as it
does ``combat_deployment.UNGAINED_UNDEPLOYABLE_KEY`` (OQ-038)."""


def recruited_commander_count(context: FrameContext, key: str) -> int:
    """Return the Commander recruit count kept under ``key`` (0 when absent)."""

    value = context.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"turn frame has invalid {key}")
    return value


def commissioned_dreadnought_count(context: FrameContext) -> int:
    """Return the dreadnoughts commissioned this Agent turn (0 when absent)."""

    value = context.get(DREADNOUGHTS_COMMISSIONED_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"turn frame has invalid {DREADNOUGHTS_COMMISSIONED_KEY}")
    return value


def shipping_troop_count(context: FrameContext) -> int:
    """Return the Troop Transports troops recruited this Agent turn (0 when
    absent)."""

    value = context.get(SHIPPING_TROOPS_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"turn frame has invalid {SHIPPING_TROOPS_KEY}")
    return value


def ungained_shipping_troop_count(context: FrameContext) -> int:
    """Return the Troop Transports troops still waiting in the shortfall (0
    when absent)."""

    value = context.get(UNGAINED_SHIPPING_TROOPS_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"turn frame has invalid {UNGAINED_SHIPPING_TROOPS_KEY}")
    return value


def frame_context_int(frame: DecisionFrame, key: str) -> int | None:
    """Read an optional non-bool integer from a frame's context."""

    value = dict(frame.context).get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def context_str(context: FrameContext, key: str, *, owner: str = "frame") -> str:
    """Read a required string from a frame context."""

    value = context.get(key)
    if not isinstance(value, str):
        raise RuntimeError(f"{owner} has invalid {key}")
    return value


def replace_player(
    players: tuple[PlayerState, ...],
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    """Return ``players`` with the seat matching ``player.player_id`` replaced."""

    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in players
    )


def hungry_for_spice_is_due(seat: PlayerState) -> bool:
    """Return whether Hungry for Spice has earned this turn's draw.

    "Whenever you gain 3 or more spice in a single turn: draw a card"
    [Steersman Y'rkoon card]; once per turn, against the spice held when
    the seat's turn opened plus the spice spent since (OQ-063).
    """

    hungry = leader_triggers(
        seat.leader_face_id or seat.leader_id, OnSpiceGainedInTurnAtLeast
    )
    return (
        bool(hungry)
        and not seat.hungry_for_spice_granted_turn
        and seat.resources.spice - seat.spice_at_turn_start + seat.spice_spent_turn
        >= hungry[0][0].amount
    )


def reset_turn_counters(
    players: tuple[PlayerState, ...],
    player: int,
    *,
    closing: int | None = None,
) -> tuple[PlayerState, ...]:
    """Restart one player's per-turn bookkeeping as their turn opens.

    Deployment counters return to zero and the Spice-gained tracking takes a
    fresh snapshot of the player's current Spice. ``closing`` is the seat
    whose turn just closed. When it is the same seat (every other seat has
    revealed), the snapshot would erase the closed turn's spice before
    Hungry for Spice judges it in the closing transition, so a draw that
    turn earned is kept as owed (OQ-063).
    """

    owner = players[player]
    owed = owner.hungry_for_spice_owed or (
        closing == player and hungry_for_spice_is_due(owner)
    )
    # A recruit, specimen or Suspensor Suits shortfall never outlives the turn
    # it waits in, whoever's seat it is (OQ-030, OQ-049, OQ-042): every
    # seat's clears here.
    players = tuple(
        replace(
            seat, ungained_troops=0, ungained_specimens=0, ungained_conflict_troops=0
        )
        if seat.ungained_troops
        or seat.ungained_specimens
        or seat.ungained_conflict_troops
        else seat
        for seat in players
    )
    # Infiltrate lasts for the turn it was played in (an Agent turn's
    # placement spends it earlier; a Reveal turn's play never can): whichever
    # seat's turn opens, none carries it over.
    players = tuple(
        replace(seat, enemy_agents_ignored_turn=False)
        if seat.enemy_agents_ignored_turn
        else seat
        for seat in players
    )
    owner = players[player]
    return replace_player(
        players,
        replace(
            owner,
            units_deployed_turn=0,
            track_troops_recruited_turn=0,
            units_deployed_peak=0,
            units_deployed_committed=0,
            spice_at_turn_start=owner.resources.spice,
            spice_spent_turn=0,
            commander_recruited_turn=False,
            contracts_completed_turn=0,
            # A held Contract icon never outlives the turn it was gained on
            # (OQ-059), a Conflict reward's the seat's Conflict rewards (user
            # ruling 2026-10-02, L2-Q2), nor an Arrakeen Scouts step's the
            # step (same day); each fizzles there with an event and this is
            # the belt-and-braces reset.
            held_contract_icons=0,
            commander_discount_turn=0,
            ignores_influence_requirements_turn=False,
            granted_agent_icon_turn="",
            combat_icon_turn=False,
            hungry_for_spice_granted_turn=False,
            hungry_for_spice_owed=owed,
            spies_recalled_turn=0,
            suspensor_owed=0,
        ),
    )


def turn_owner_of(state: GameState) -> int | None:
    """Return whose Agent or Reveal turn is in progress, if any.

    The turn's own frame (turn, Agent effects or Reveal) sits lowest on the
    stack during Player Turns; frames above it belong to that turn's
    effects, whoever decides them.
    """

    if state.phase is not GamePhase.PLAYER_TURNS:
        return None
    for frame in state.decision_stack:
        if frame.kind in (
            FrameKind.TURN,
            FrameKind.AGENT_EFFECTS,
            FrameKind.REVEAL,
        ) and isinstance(frame.decision, PlayerDecision):
            return frame.decision.owner
    return None


def own_turn_frame_index(state: GameState, player: int) -> int | None:
    """Return the stack index of ``player``'s own open turn frame, if any.

    The turn frame before the Agent is placed, the Agent-turn effect frame
    and the Reveal frame each carry the bookkeeping of that one turn.
    ``None`` when the open turn is another seat's or no turn is open (the
    Combat, Makers and Recall phases are not turns [Main p. 8]).
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if frame.kind not in (
            FrameKind.TURN,
            FrameKind.AGENT_EFFECTS,
            FrameKind.REVEAL,
        ):
            continue
        if isinstance(frame.decision, PlayerDecision) and (
            frame.decision.owner == player
        ):
            return index
        return None
    return None


def credit_commissioned_dreadnoughts(
    state: GameState, player: int, count: int
) -> GameState:
    """Count ``count`` dreadnoughts commissioned in ``player``'s own Agent turn.

    Credited on the owner's turn frame -- the one before the Agent is placed
    (the placement carries the count over) or the Agent-turn effect frame --
    the way a recruited Commander is (``update_turn_recruits``), and only in
    the owner's own turn: nothing is kept outside it, and nothing in a Reveal
    turn, which has no deployment of a dreadnought ("If you commissioned the
    dreadnought while sending an Agent to a Combat space, you may deploy it to
    the Conflict" [Rise of Ix p. 6]).
    """

    index = own_turn_frame_index(state, player)
    if index is None or count < 1:
        return state
    frame = state.decision_stack[index]
    if frame.kind not in (FrameKind.TURN, FrameKind.AGENT_EFFECTS):
        return state
    context = frame_context(frame)
    context[DREADNOUGHTS_COMMISSIONED_KEY] = (
        commissioned_dreadnought_count(context) + count
    )
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:index],
            with_context(frame, context),
            *state.decision_stack[index + 1 :],
        ),
    )


TECH_ACQUIRE_PENDING_KEY = "pending_tech_acquire_effects"
"""One-time Tech rewards waiting for free ordering in this turn (OQ-098)."""


TURN_START_OVER_KEY = "turn_start_over"
"""Set on the owner's turn frame once the owner has acted in that turn.

"At the start of your turn: Put this card into play -> Draw a card and pass
your turn." [Litany Against Fear card]; "At the start of your turn: Pass
your turn." [Withdrawn card]. Either is only the turn's first action: any
other action of the turn's owner -- a Plot Intrigue and its choices, a
specimen return, Family Atomics, an Emperor track Spy -- ends the start of
the turn (OQ-095 (6), user ruling 2026-10-04: "턴 시작 후 이 카드를 사용하는
것 말고 다른 행동을 했으면 이제 턴 시작이 끝났으니 이 카드를 사용할 수 없게
되는게 맞다고 봐"). Absent means the start is still open. The Agent-turn
effect and Reveal frames that replace the turn frame never carry it: the
two cards are not offered there at all."""


def turn_start_is_open(state: GameState, player: int) -> bool:
    """Whether ``player``'s own turn is open and the seat has not acted yet.

    True while the seat's own open turn frame is the turn frame (no Agent
    sent, no Reveal) without ``TURN_START_OVER_KEY``, whatever is stacked
    above it (a Plot's choice, another seat's answer).
    """

    index = own_turn_frame_index(state, player)
    if index is None:
        return False
    frame = state.decision_stack[index]
    return (
        frame.kind == FrameKind.TURN
        and dict(frame.context).get(TURN_START_OVER_KEY) is not True
    )


def end_turn_start(state: GameState, player: int) -> GameState:
    """Mark the start of ``player``'s open turn as over (``TURN_START_OVER_KEY``).

    Unchanged when the seat's own open turn frame is not a turn frame whose
    start is still open.
    """

    index = own_turn_frame_index(state, player)
    if index is None or not turn_start_is_open(state, player):
        return state
    frame = state.decision_stack[index]
    context = frame_context(frame)
    context[TURN_START_OVER_KEY] = True
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:index],
            with_context(frame, context),
            *state.decision_stack[index + 1 :],
        ),
    )


def owes_track_spy(state: GameState, seat: int) -> bool:
    """Whether ``seat`` still has an Emperor track Influence 4 Spy to place.

    "When you reach 4 Influence, you earn the bonus shown on that space of
    the track" [Main p. 7]; the Emperor strip prints the Spy icon. Each
    reach queues one entry in ``GameState.pending_track_spies``.
    """

    return any(entry[0] == seat for entry in state.pending_track_spies)


def track_spy_waits(state: GameState, seat: int) -> bool:
    """Whether an Emperor track Spy owed by ``seat`` waits inside its turn.

    During the seat's own Agent or Reveal turn the placement is a mandatory
    action of that turn, taken in any order with its other actions and
    before the turn ends ("엄연히 agent턴 내에 순서를 정해서 할 수 있는 의무
    행동", user ruling 2026-10-04 following the Steam app, which overrides
    the designer's "before you move on to other player initiated actions",
    OQ-057 (15)). Anywhere else -- another seat's turn, Combat, Round Start,
    the Arrakeen Scouts step, the Endgame -- it opens at once.
    """

    return turn_owner_of(state) == seat


OWED_INTRIGUE = "intrigue"
"""An owed draw from the Intrigue deck (``PlayerState.owed_draws``)."""

OWED_CARD = "card"
"""An owed draw from the seat's own deck (``PlayerState.owed_draws``)."""

OWED_ORIGIN_BENE_GESSERIT_4 = "bene_gesserit_4"
"""The Bene Gesserit track's Influence 4 Intrigue card [Main p. 7]."""

OWED_ORIGIN_IMPERIAL_BIRTHRIGHT = "imperial_birthright"
"""Princess Irulan's Intrigue card for reaching Emperor 2."""

OWED_ORIGIN_CHOAM_TRANSPORTS = "choam_transports"
"""CHOAM Transports' card for a completed Contract [Tech tile]."""

OWED_ORIGIN_ACQUIRE = "acquire:"
"""Prefix of an acquired card's own acquire box (``acquire:<instance>``)."""

_IMMEDIATE_DRAW_ORIGINS = frozenset(
    {
        OWED_ORIGIN_BENE_GESSERIT_4,
        OWED_ORIGIN_IMPERIAL_BIRTHRIGHT,
        OWED_ORIGIN_CHOAM_TRANSPORTS,
    }
)


def draw_waits_for_owner(state: GameState, seat: int) -> bool:
    """Whether a draw a trigger earns ``seat`` now waits as its own step.

    User ruling 2026-10-10 (OQ-106, project convention): "그 외에는 전부
    나누자. 특히 카드 드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를
    폐기하고 싶을 수 있잖아." A draw triggered by another printed effect (a
    track bonus, a Leader ability, a "when trashed" or acquire box, a Tech
    tile) is not drawn inside the step that triggered it: during the seat's
    own Agent or Reveal turn it waits for the owner's own step, so the
    public choice that triggered it stays undoable (OQ-010). Most such
    draws are taken in any order with the turn's other effects ("You may
    carry out all these effects in any order." [Main p. 9], OQ-027) and
    before the turn ends; the ones an adopted community ruling says come at
    once are the owner's very next step instead (``draw_is_immediate``).
    Like the Emperor track's Spy (``track_spy_waits``, user ruling
    2026-10-04), anywhere else -- another seat's turn, Combat, the Arrakeen
    Scouts step, the Endgame -- the draw happens at once, where every
    choice is already held to its seat's confirm press (OQ-103).
    """

    return turn_owner_of(state) == seat


def draw_is_immediate(origin: str) -> bool:
    """Whether a held draw from ``origin`` must be the owner's next step.

    User decision 2026-10-10 (OQ-106, "가 로 가자"): three triggered draws
    whose adopted community rulings (OQ-057) say they come at once are
    still their own step -- the trigger stays undoable -- but the step
    right after it, with nothing of the owner's in between (no other
    effect, Plot, free-timing action or turn end):

    - CHOAM Transports' card, "When you complete a contract: draw a card"
      [Tech tile]: "The card draw from CHOAM Transports is triggered as soon
      as the contract is completed and can't be deferred." (Message from
      designer);
    - the Bene Gesserit Influence 4 Intrigue card [Main p. 7] and Princess
      Irulan's Imperial Birthright: "faction bonuses (such as drawing an
      Intrigue on the BG track) may interrupt this flow" (Message from
      designer);
    - an acquire box's draw (Overthrow, OQ-042): "Acquire Effects must be
      taken immediately upon acquiring the Card or Tech." (Direwolf
      Discord).

    Every other held draw stays in free order (OQ-106).
    """

    return origin in _IMMEDIATE_DRAW_ORIGINS or origin.startswith(OWED_ORIGIN_ACQUIRE)


def hold_draw(owner: PlayerState, deck: str, origin: str, source: str) -> PlayerState:
    """Return ``owner`` with one more draw waiting as its own step (OQ-106).

    ``deck`` is ``OWED_INTRIGUE`` or ``OWED_CARD``; ``origin`` names the
    printed effect that earned it (shown with the step) and ``source`` is the
    event source the draw is logged under when it is taken.
    """

    return replace(owner, owed_draws=(*owner.owed_draws, (deck, origin, source)))


def owes_held_draw(state: GameState, seat: int) -> bool:
    """Whether ``seat`` still has a triggered draw waiting (OQ-106).

    Like an owed Emperor track Spy, a waiting draw holds the turn's end back:
    it must be taken before the turn ends, so no draw is ever lost.
    """

    return bool(state.players[seat].owed_draws)


def reveal_is_open_for(state: GameState, player: int) -> bool:
    """Return whether ``player``'s Reveal frame is on the decision stack."""

    return any(
        frame.kind == FrameKind.REVEAL
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == player
        for frame in state.decision_stack
    )


def update_turn_recruits(
    state: GameState,
    *,
    troops_recruited: int = 0,
    commanders_recruited: int = 0,
) -> GameState:
    """Keep the turn owner's bookkeeping in step with a mid-turn effect.

    Troops recruited during the owner's turn join that turn's deployment
    allowance whether the effect resolved before or after placing the Agent
    (a Reveal turn's recruits feed its Combat-icon deployment
    [Bloodlines p. 5]). Sardaukar Commanders are counted apart from the
    troops (``COMMANDERS_RECRUITED_KEY``): each reserves a deploy slot for a
    Commander (OQ-070). Spice spent is counted on the seat
    (``PlayerState.spice_spent_turn``), not here.
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if frame.kind == FrameKind.REVEAL:
            context = frame_context(frame)
            recruited = context.get("reveal_troops_recruited", 0)
            if isinstance(recruited, bool) or not isinstance(recruited, int):
                raise RuntimeError("Reveal frame has an invalid recruit count")
            context["reveal_troops_recruited"] = recruited + troops_recruited
            if commanders_recruited:
                context[REVEAL_COMMANDERS_RECRUITED_KEY] = (
                    recruited_commander_count(context, REVEAL_COMMANDERS_RECRUITED_KEY)
                    + commanders_recruited
                )
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    with_context(frame, context),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind not in (FrameKind.AGENT_EFFECTS, FrameKind.TURN):
            continue
        context = frame_context(frame)
        previous = context.get("troops_recruited", 0)
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("turn frame has an invalid recruit count")
        context["troops_recruited"] = previous + troops_recruited
        if commanders_recruited:
            context[COMMANDERS_RECRUITED_KEY] = (
                recruited_commander_count(context, COMMANDERS_RECRUITED_KEY)
                + commanders_recruited
            )
        updated = with_context(frame, context)
        return replace(
            state,
            decision_stack=(
                *state.decision_stack[:index],
                updated,
                *state.decision_stack[index + 1 :],
            ),
        )
    return state
