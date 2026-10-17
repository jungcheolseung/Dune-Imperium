"""When a human seat's turn is over, read off the engine's decision stack.

Every turn end of a human seat is exactly one press (project convention,
not a rule; ``docs/rules/player-turns.md``). An Agent turn ends only through
its owner's ``finish_agent_turn`` (user ruling OQ-095), a Reveal turn
through ``finish_reveal``, and a turn-passing card is that press itself; the
server holds the remaining unit ends (a Leader pick, Conflict rewards, a
Control defense, an Arrakeen Scouts line) until the seat presses "턴 종료",
as long as the seat still has a step of the unit to take back; a step that
reveals something itself cannot be taken back and is instead held by the
browser and sent with "확정 ▶" (``sent_by_turn_end``, see below).
The last Leader pick has its own explicit ``finish_leader_draft`` so setup
cannot reveal hidden cards before that press (OQ-007).
Which steps end a turn is a reading of the decision stack the engine
already keeps, so the server needs no rule logic of its own; this module is
that reading and nothing else.

A seat's *unit* is its own run of decisions: an Agent or Reveal turn in
Player Turns, or its share of a phase outside them (a Leader pick, a Combat
or Endgame Intrigue go, its Conflict rewards, a Control defense). Another
seat's decision inside a unit is an answer, not a unit of its own: the
engine stacks it above the running unit and returns there once it is
answered. That is every other seat's frame above a started Agent or Reveal
turn, and the three opponent-decision frames anywhere.

The press is the seat's confirmation, and until it the seat may take its
unit's steps back. So a held unit end comes before the chance outcomes that
follow the unit (the next Arrakeen Scouts card, a reshuffle, and the
engine's pauses before a reveal: before each Conflict reward recipient
after the first, before every Round Start after the first, after a Control
defense, before each Arrakeen Scouts auction winner's reward after the
first, rules/pauses.py): those reveal hidden information or stand right
before it, the reveal closes the undo window (OQ-010), and a press after
it would confirm nothing ("전투 보상으로 받은 스파이 둘 위치를 골랐다가 …
확정 전에 다른 곳에 두고 싶을 수 있잖아", user, 2026-10-08). A chance
outcome inside the unit (a reshuffle in the middle of an Agent turn, whose
frame waits below it) resolves at once, as the effect that drew the card.
"""

from typing import Final

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.combat_deployment import (
    FINISHING_KEY,
    legal_agent_turn_finish_actions,
)
from dune_imperium.rules.effects import agent_turn_has_other_pending_effects
from dune_imperium.rules.frames import (
    FrameKind,
    owes_held_draw,
    owes_track_spy,
)

# Engine actions whose whole meaning is "I am done": pressing one is the
# seat's turn end itself, so no second press follows it.
EXPLICIT_TURN_ENDS: Final = frozenset(
    {
        "finish_agent_turn",
        "finish_leader_draft",
        "finish_reveal",
        "pass_combat_intrigue",
        "pass_endgame_intrigue",
        # The Conflict-end Intrigue window opens on public facts, often
        # with nothing to play (OQ-103, user decision 2026-10-09): "쓰지
        # 않음" ends the seat's part with one press, like a pass.
        "decline_conflict_end_intrigue",
        # Its end once a card was played in the window (user decision
        # 2026-10-18: "끝내기"): the window stays open after a play while
        # the seat holds Intrigue (OQ-103), and this one press closes it.
        "finish_conflict_end_intrigue",
        # Arrakeen Scouts: confirming a sealed bid is the seat's turn end;
        # until then it may change the bid (D5, docs/arrakeen-scouts-design.md).
        "confirm_scouts_bid",
        # A Scouts choice with no line the seat can take asks it anyway
        # (cleanup-2a, OQ-071); its one confirm says the seat takes nothing,
        # like a pass, so one press ends the seat's part.
        "resolve_scouts_choice_without_option",
        # Critical Moment's open call (0 a pass) is one action per amount, so
        # the browser sends it with the turn-end press after the stepper set
        # the amount ("경매 ... 턴 종료를 눌러야 확정되게 해줘", user,
        # 2026-10-05); no second press follows it.
        "scouts_call",
    }
)

# Frames an opponent answers in the middle of another seat's unit
# (Covert Operation's discard, Holy War and False Orders' Spy moves, Holy
# War's unit loss). Since every Agent turn ends only through its owner's
# press (OQ-095), they always sit above the card player's still-open Agent
# turn: an answer belongs to that seat's unit, never opens one of the
# answering seat's own, and the owner's turn end is not offered until
# every opponent has answered (``agent_turn_end_ready``). They are
# recognised by kind, so an answer is read as one wherever it sits.
INTERRUPT_KINDS: Final = frozenset(
    {
        FrameKind.OPPONENT_CARD_DISCARD,
        FrameKind.OPPONENT_SPY_MOVE,
        FrameKind.OPPONENT_UNIT_LOSS,
    }
)

# Events of a turn-passing card: Withdrawn ("pass your turn") and Litany
# Against Fear ("draw a card and pass your turn"). Playing one is the seat's
# turn end itself, like an explicit turn-end action -- "카드 효과로 턴 넘김
# 버튼을 눌렀다면 그건 턴 종료를 누른거랑 같으니까" (user, 2026-10-01,
# OQ-095 (6)) -- so no press follows it.
TURN_PASS_EVENTS: Final = frozenset({"turn_passed", "turn_start_card_played"})

# Events that mean a seat has taken its turn: an Agent went out, or the
# turn was passed. A Reveal turn ends only through ``finish_reveal``, which
# is explicit.
TURN_TAKING_EVENTS: Final = frozenset({"agent_placed", *TURN_PASS_EVENTS})


_TURN_KINDS: Final = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)


def _turn_frame(state: GameState) -> DecisionFrame | None:
    """Return the turn's own frame, lowest on the stack, if a turn is on it."""

    for frame in state.decision_stack:
        if frame.kind in _TURN_KINDS and isinstance(frame.decision, PlayerDecision):
            return frame
    return None


def unit_seat(state: GameState) -> int | None:
    """Return the seat whose unit the pending decision belongs to.

    The owner of a started Agent or Reveal turn, whoever answers above it;
    otherwise the owner of the topmost player decision that is not an
    opponent interrupt. ``None`` when no player decision is on the stack
    (the finished game).
    """

    turn = _turn_frame(state)
    if turn is not None and turn.kind != FrameKind.TURN:
        return _owner(turn)
    for frame in reversed(state.decision_stack):
        if frame.kind in INTERRUPT_KINDS:
            continue
        if isinstance(frame.decision, PlayerDecision):
            return frame.decision.owner
    return None


def answers_another_unit(state: GameState, seat: int) -> bool:
    """Whether ``seat``'s pending decision answers inside another seat's unit."""

    top = state.decision_stack[-1] if state.decision_stack else None
    return (top is not None and top.kind in INTERRUPT_KINDS) or unit_seat(state) != seat


def own_unit_outside_turns(state: GameState, seat: int) -> bool:
    """Whether ``seat``'s pending decision is its own unit outside the turns.

    A Leader pick, a Combat or Endgame Intrigue go, its Conflict rewards, a
    Control defense, an Arrakeen Scouts line: no Agent or Reveal turn (nor
    the start of one) is on the stack, and the decision is no answer inside
    another seat's unit. Read from the stack alone.
    """

    return _turn_frame(state) is None and not answers_another_unit(state, seat)


def at_turn_start(state: GameState, seat: int) -> bool:
    """Whether ``seat``'s turn is open but not yet taken.

    Its ``turn`` frame is the turn's own frame: no Agent sent, no Reveal.
    What the seat does there (a Plot Intrigue, a Tech flip) comes before
    its turn, and so do the leftovers of its previous turn that the engine
    stacks above the new frame (a Contract pick, a reshuffle).
    """

    turn = _turn_frame(state)
    return turn is not None and turn.kind == FrameKind.TURN and _owner(turn) == seat


def _owner(frame: DecisionFrame) -> int:
    if not isinstance(frame.decision, PlayerDecision):
        raise TypeError("a turn frame holds a player decision")
    return frame.decision.owner


def turn_start_seat(state: GameState) -> int | None:
    """Return the seat choosing its Agent or Reveal turn right now, if any.

    That is the pending decision of a ``turn`` frame on top of the stack:
    the start of a turn, before the seat has sent an Agent or revealed.
    """

    if not state.decision_stack:
        return None
    top = state.decision_stack[-1]
    if top.kind == FrameKind.TURN and isinstance(top.decision, PlayerDecision):
        return top.decision.owner
    return None


def unit_over(state: GameState, unit: int) -> bool:
    """Whether ``unit``'s run of decisions is over in ``state``.

    With a player decision pending, the unit is over once that decision
    belongs to another seat's unit, or when the seat stands at the start
    of a turn of its own (its Conflict rewards ran into its next turn, or
    every other seat has revealed and its next turn follows). With a chance
    outcome pending, it is over once no decision of the unit is left on the
    stack below the outcome: the outcome comes after the unit and waits for
    the press. That reading uses only the stack the outcome sits on, never
    the outcome itself, so whether a seat is held tells it nothing about
    the card about to be revealed. Not over when nothing is pending.
    """

    if not state.decision_stack:
        return False
    pending = state.decision_stack[-1].decision
    if isinstance(pending, ChanceDecision):
        return unit_seat(state) != unit
    return unit_seat(state) != unit or turn_start_seat(state) == unit


def finishing_seat(state: GameState) -> int | None:
    """Return the seat whose pressed Agent-turn end is still resolving.

    Every press leaves its turn finishing; one that left nothing is settled
    in the same transition, so only a press with follow-ups is seen here: a
    Usurp trash's, or a box the press itself resolved (Long Reach's payment
    reaching a Faction's bonus) -- a Skill or Navigation choice, a reshuffle,
    a Friends Everywhere pick. The engine then closes the turn, or reopens
    it for what they produced (OQ-095 (3)-(5)). The flagged frame sits
    below those follow-ups, so the whole stack is read.
    """

    for frame in state.decision_stack:
        if (
            frame.kind == FrameKind.AGENT_EFFECTS
            and isinstance(frame.decision, PlayerDecision)
            and dict(frame.context).get(FINISHING_KEY) is True
        ):
            return frame.decision.owner
    return None


def _only_skippable_boxes_wait(
    state: GameState, context: dict[str, ActionValue], owner: int
) -> bool:
    """Whether the only Agent boxes left are boxes the turn end lets go.

    Two kinds, both judged from public facts: a box that is optional now
    (``agent_effects.box_is_optional`` -- the card in play and the box's
    public stage; the press lapses it, user ruling 2026-10-14), and a box
    that resolves icon by icon (OQ-027) keeping only icons whose printed
    condition is false (Lady Amber's Signet spice with no Alliance, Cargo
    Runner's four-contract line, Industrial Espionage's ungrafted Research),
    which offers nothing and waits for the press (OQ-057). Their conditions
    are all public (Influence, Alliances, contracts, Bonds, the graft), and
    so is the engine's verdict on them: ``finish_agent_turn`` is legal
    beside such boxes exactly when nothing else holds the end. A
    single-effect mandatory box is left out -- its stall is a dry run that
    can depend on the owner's hand.
    """

    from dune_imperium.rules.agent_effects import box_is_optional
    from dune_imperium.rules.graft_boxes import box_is_pending, state_with_active_box

    pending = [box for box in (0, 1) if box_is_pending(context, box)]
    if not pending:
        return False
    for box in pending:
        view = state_with_active_box(state, box)
        icons = dict(view.decision_stack[-1].context).get("pending_agent_icons")
        if not box_is_optional(view) and not (isinstance(icons, str) and icons):
            return False
    return bool(legal_agent_turn_finish_actions(state, owner))


def agent_turn_end_ready(state: GameState) -> int | None:
    """Return the seat whose open Agent turn has nothing mandatory left.

    The seat may still take optional steps (a Plot Intrigue, a deployment,
    a specimen return) before its one press. Read from public facts only --
    the effect frame's pending flags, the Contracts it must complete, an
    Emperor track Spy still owed (placed before the turn ends, user ruling
    2026-10-04) and a triggered draw still waiting (taken before the turn
    ends, user ruling 2026-10-10, OQ-106) -- so every seat may be told. A
    box that is optional now, or keeps only icons whose conditions are
    false, is ready too (``_only_skippable_boxes_wait``); a stalled
    single-effect mandatory Agent box
    (OQ-057), whose judgment can depend on the owner's hand, counts as not
    ready here.
    """

    if not state.decision_stack:
        return None
    top = state.decision_stack[-1]
    if top.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        top.decision, PlayerDecision
    ):
        return None
    context = dict(top.context)
    if context.get(FINISHING_KEY) is True:
        return None
    owner = top.decision.owner
    if agent_turn_has_other_pending_effects(
        context, state.players
    ) and not _only_skippable_boxes_wait(state, context, owner):
        return None
    if owes_track_spy(state, owner) or owes_held_draw(state, owner):
        return None
    # A Tech tile's acquire effects still waiting hold the end back too
    # (OQ-098; ``combat_deployment.legal_agent_turn_finish_actions``), but
    # not an Influence with every Faction at the top (cleanup-2b).
    if turn_rows.tech_acquire_effects_hold_the_end(context, state.players[owner]):
        return None
    # So does c6r6's Influence waiting with a Faction it can raise
    # (cleanup-2b; public facts: the frame's context, the seat's Influence).
    if turn_rows.holds_the_end(state, owner):
        return None
    return owner
