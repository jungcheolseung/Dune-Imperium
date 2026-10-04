"""When a human seat's turn is over, read off the engine's decision stack.

Every turn end of a human seat is exactly one press (project convention,
not a rule; ``docs/rules/player-turns.md``). An Agent turn ends only through
its owner's ``finish_agent_turn`` (user ruling OQ-095), a Reveal turn
through ``finish_reveal``, and a turn-passing card is that press itself; the
server holds the remaining unit ends (a Leader pick, Conflict rewards, a
Control defense, an Arrakeen Scouts line) until the seat presses "턴 종료".
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
"""

from typing import Final

from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.combat_deployment import FINISHING_KEY
from dune_imperium.rules.effects import agent_turn_has_other_pending_effects
from dune_imperium.rules.frames import FrameKind, owes_track_spy

# Engine actions whose whole meaning is "I am done": pressing one is the
# seat's turn end itself, so no second press follows it.
EXPLICIT_TURN_ENDS: Final = frozenset(
    {
        "finish_agent_turn",
        "finish_reveal",
        "pass_combat_intrigue",
        "pass_endgame_intrigue",
        # Arrakeen Scouts: confirming a sealed bid is the seat's turn end;
        # until then it may change the bid (D5, docs/arrakeen-scouts-design.md).
        "confirm_scouts_bid",
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


def finishing_seat(state: GameState) -> int | None:
    """Return the seat whose pressed Agent-turn end is still resolving.

    Only Usurp's trash at the turn's end leaves follow-ups (a Skill choice, a
    reshuffle) after the press; the engine then closes the turn, or reopens
    it for what the trash produced (OQ-095 (4)-(5)). The flagged frame sits
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


def agent_turn_end_ready(state: GameState) -> int | None:
    """Return the seat whose open Agent turn has nothing mandatory left.

    The seat may still take optional steps (a Plot Intrigue, a deployment,
    a specimen return) before its one press. Read from public facts only --
    the effect frame's pending flags, the Contracts it must complete and an
    Emperor track Spy still owed (placed before the turn ends, user ruling
    2026-10-04) -- so every seat may be told; a stalled Agent box (OQ-057),
    whose judgment can depend on the owner's hand, counts as not ready here.
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
    if agent_turn_has_other_pending_effects(context, state.players):
        return None
    if owes_track_spy(state, top.decision.owner):
        return None
    return top.decision.owner
