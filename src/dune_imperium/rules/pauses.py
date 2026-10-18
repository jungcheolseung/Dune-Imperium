"""Pauses before a reveal that follows a seat's choices outside the turns.

A seat's choices outside the player turns (its Conflict reward choices, a
Conflict-end Intrigue window, a Control defense) often run, in the same
engine step, into something hidden being revealed: the next reward
recipient's Intrigue draw, the next round's Conflict and hands, the Round
Start draw. Only a chance decision used to stop that run (a discard
reshuffle), so whether a seat could still take its last choice back
depended on whether a deck happened to need shuffling, and the play server
showed the same choice two ways ("턴 종료 ▶" with undo, or "확정 ▶").

A pause is a chance decision with one fixed outcome, pushed at a fixed
point whatever the seats hold, and answered by ``resume_pause``, which runs
the step it held back. The play server already holds a seat's turn end
before a chance outcome that follows its unit (``server/turn_end.py``
``unit_over``), so the seat may take its last choice back until it presses
"턴 종료"; everywhere else (AI seats, training, simulations) the chance
resolver answers it at once without drawing from the random stream
(``core/chance.py`` ``FIXED_OUTCOME_SUFFIX``). This is a project convention
for the play server's undo, not a rule: the official rules have no point at
which such a choice becomes final (OQ-103).

The points are fixed by public facts only, so where a pause stands tells no
seat anything:
- ``REWARDS`` before each Conflict reward recipient after the first is paid
  (``rules/combat.py``);
- ``CONFLICT_END`` once a Combat's rewards are paid, before the Conflict card
  is awarded (with Planetary Array's card, OQ-108) and the Conflict-end
  Intrigue windows are offered (``rules/engine.py``). The windows open on
  public facts and tell nothing of a hand (OQ-103, user decision
  2026-10-09); the pause keeps the last recipient's choice open to undo
  before them, like the earlier recipients' choices, in the last round
  too, which has no Round Start;
- ``ROUND_START`` before every round's reshuffles and reveal after the first
  round (``rules/engine.py``), after any Conflict-end Intrigue window;
- ``ROUND_DRAW`` after a Control defense, before the round's draw
  (``rules/phases.py``);
- ``SCOUTS_REWARD`` before each Arrakeen Scouts auction winner's reward
  after the first (``rules/scouts_auctions.py``), like the Conflict's
  recipients: Competitive Study's second place may research past the second
  genetic marker, which draws its card, or move on a single path onto a
  Tleilaxu track Intrigue space, so the first place's Research direction
  stood right before another seat's hidden card (user ruling 2026-10-10,
  OQ-106: "그 외에는 전부 나누자"). The order of the winners is public once
  the bids are revealed.

Every step a pause holds back runs as it did, in the same order. The one
hook the engine runs at the end of a step on that step's own events, Earn
Any Alliance's completion, runs at the end of the step that took the
Alliance, also when that step stopped at a pause (``rules/engine.py``
``_complete_alliance_contracts``). In Combat every reward step ends at a
pause or a choice before the cleanup, so the Contract always completes
before the Conflict's troops go back to the supply, and its troops come
only from the supply, a shortfall dropped like any Conflict reward's
(OQ-056, user decision 2026-10-09).
"""

from typing import Final

from dune_imperium.core.chance import FIXED_OUTCOME_SUFFIX
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind

REWARDS: Final = "rewards"
CONFLICT_END: Final = "conflict_end"
ROUND_START: Final = "round_start"
ROUND_DRAW: Final = "round_draw"
SCOUTS_REWARD: Final = "scouts_reward"
PAUSE_POINTS: Final = frozenset(
    {REWARDS, CONFLICT_END, ROUND_START, ROUND_DRAW, SCOUTS_REWARD}
)
CONTINUE: Final = "continue"


def push_pause(state: GameState, point: str, where: str) -> RuleResult:
    """Stop before ``point``'s step; ``where`` keeps the decision id unique."""

    if point not in PAUSE_POINTS:
        raise ValueError(f"unknown pause point: {point}")
    decision_id = f"{where}:{point}{FIXED_OUTCOME_SUFFIX}"
    frame = DecisionFrame(
        kind=FrameKind.PAUSE,
        frame_id=decision_id,
        decision=ChanceDecision(
            decision_id=decision_id,
            prompt="Continue",
            options=(CONTINUE,),
        ),
        context=(("point", point),),
    )
    return RuleResult(state=state.push_decision(frame))


def pause_is_pending(state: GameState) -> bool:
    return bool(state.decision_stack) and state.decision_stack[-1].kind == (
        FrameKind.PAUSE
    )


def pending_pause_point(state: GameState) -> str:
    """The point of the pause on top of the stack, which the caller resumes."""

    if not pause_is_pending(state):
        raise ValueError("there is no pending pause")
    point = dict(state.decision_stack[-1].context).get("point")
    if not isinstance(point, str) or point not in PAUSE_POINTS:
        raise RuntimeError("a pause frame names no known point")
    return point
