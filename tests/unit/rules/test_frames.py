"""Unit tests for shared decision-frame helpers in ``rules/frames.py``."""

from dune_imperium import RulesetConfig
from dune_imperium.core import DecisionFrame, GamePhase, GameState, PlayerDecision
from dune_imperium.rules.frames import FrameKind, turn_closing_player


def _state(*frames: DecisionFrame) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        decision_stack=frames,
    )


def _frame(kind: str, owner: int, frame_id: str = "f") -> DecisionFrame:
    return DecisionFrame(
        kind=kind,
        frame_id=frame_id,
        decision=PlayerDecision(owner=owner, prompt="p"),
    )


def test_turn_closing_player_reports_an_agent_effects_frame_that_became_a_turn() -> (
    None
):
    # "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수
    # 있다. 이미 garrison에 있던 troop을 다시 recruit한 것으로 취급해 두 개
    # 제한을 우회할 수는 없다" [Main p. 10] [FAQ p. 4]
    # (docs/rules/player-turns.md:137). This is the shape ``4e29e27``'s
    # ``turn_closed`` checks and ``complete_alliance_contracts``'s
    # ``closing_player`` guard against: an owner's own AGENT_EFFECTS frame
    # closed and reopened as a fresh "turn" frame for the same owner.
    before = _state(_frame(FrameKind.AGENT_EFFECTS, 0))
    after = _state(_frame(FrameKind.TURN, 0))

    assert turn_closing_player(before, after) == 0


def test_turn_closing_player_reports_a_reveal_frame_that_became_a_turn() -> None:
    before = _state(_frame(FrameKind.REVEAL, 0))
    after = _state(_frame(FrameKind.TURN, 0))

    assert turn_closing_player(before, after) == 0


def test_turn_closing_player_ignores_a_bare_turn_frame_that_stays_a_turn_frame() -> (
    None
):
    # OQ-062's Servo-Receivers-before-placement false positive (review round
    # 2, ``leader_abilities.apply_leader_signet_acquire``): the owner's own
    # frame is already a bare "turn" frame *before* the step (the Agent has
    # not been placed yet), and ``_close_servo_signet`` merges back into
    # that very same, still-open frame. Nothing closed, so this must not be
    # mistaken for the AGENT_EFFECTS/REVEAL -> TURN transition above.
    before = _state(_frame(FrameKind.TURN, 0))
    after = _state(_frame(FrameKind.TURN, 0))

    assert turn_closing_player(before, after) is None


def test_turn_closing_player_ignores_a_turn_that_reopens_for_another_seat() -> None:
    # The ordinary case: seat 0's turn closes and seat 1's opens next. Seat
    # 0 recruited nothing in the turn that is only just starting for seat 1.
    before = _state(_frame(FrameKind.AGENT_EFFECTS, 0))
    after = _state(_frame(FrameKind.TURN, 1))

    assert turn_closing_player(before, after) is None


def test_turn_closing_player_ignores_a_frame_that_is_still_open() -> None:
    # The turn has not closed at all: still AGENT_EFFECTS after the step.
    before = _state(_frame(FrameKind.AGENT_EFFECTS, 0))
    after = _state(_frame(FrameKind.AGENT_EFFECTS, 0))

    assert turn_closing_player(before, after) is None
