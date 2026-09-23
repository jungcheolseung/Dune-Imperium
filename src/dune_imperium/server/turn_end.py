"""When a human seat's turn is over, read off the engine's decision stack.

The play server holds every turn end of a human seat until that seat
presses "턴 종료" (project convention, not a rule; ``docs/rules/
player-turns.md``). Which steps end a turn is a reading of the decision
stack the engine already keeps, so the server needs no rule logic of its
own; this module is that reading and nothing else.

A seat's *unit* is its own run of decisions: an Agent or Reveal turn in
Player Turns, or its share of a phase outside them (a Leader pick, a Combat
or Endgame Intrigue go, its Conflict rewards, a Control defense). Another
seat's decision inside a unit is an answer, not a unit of its own: the
engine stacks it above the running unit and returns there once it is
answered. That is every other seat's frame above a started Agent or Reveal
turn (a leftover Intrigue trigger can be offered to its owner then), and
the three opponent-decision frames anywhere.
"""

from typing import Final

from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind

# Engine actions whose whole meaning is "I am done": pressing one is the
# seat's turn end itself, so no second press follows it.
EXPLICIT_TURN_ENDS: Final = frozenset(
    {
        "finish_agent_turn",
        "finish_reveal",
        "pass_combat_intrigue",
        "pass_endgame_intrigue",
    }
)

# Frames an opponent answers in the middle of another seat's unit
# (Covert Operation's discard, Holy War and False Orders' Spy moves and
# unit loss). Holy War can stack them above the next seat's turn before
# that turn has started, so they are recognised by kind, not by position.
INTERRUPT_KINDS: Final = frozenset(
    {
        FrameKind.OPPONENT_CARD_DISCARD,
        FrameKind.OPPONENT_SPY_MOVE,
        FrameKind.OPPONENT_UNIT_LOSS,
    }
)

# Events that mean a seat has taken its turn: an Agent went out, or the
# turn was passed (Withdrawn, Litany Against Fear). A Reveal turn ends only
# through ``finish_reveal``, which is explicit.
TURN_TAKING_EVENTS: Final = frozenset(
    {"agent_placed", "turn_passed", "turn_start_card_played"}
)


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
