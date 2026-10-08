"""The engine's pauses before a reveal that follows a seat's choices.

A project convention for the play server's undo, not a rule (OQ-103,
rules/pauses.py): a one-outcome chance decision before each Conflict reward
recipient after the first (tests/unit/rules/test_combat.py), after a Control
defense (tests/unit/rules/test_phases.py) and before every Round Start after
the first (here). A pause draws nothing from the random stream, so a seeded
game's outcomes and every agent's answers stay what they were.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceResolver,
    GamePhase,
    PlayerDecision,
)
from dune_imperium.core.chance import FIXED_OUTCOME_SUFFIX, is_fixed_outcome
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules.engine import UprisingRulesEngine, _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.pauses import CONTINUE, ROUND_START, push_pause
from dune_imperium.rules.setup import create_initial_state
from dune_imperium.simulation import run_random_round

SELECTED_LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "staban_tuek",
)


def test_the_resolver_answers_a_pause_without_drawing() -> None:
    shuffle = ChanceDecision(
        decision_id="round:2:player:0:discard_shuffle",
        prompt="Shuffle",
        options=("a", "b", "c", "d", "e"),
        count=5,
    )
    plain = ChanceResolver(seed=7)
    paused = ChanceResolver(seed=7)
    state = create_initial_state(RulesetConfig(), seed=7, leader_ids=SELECTED_LEADERS)
    pause = push_pause(state.state, ROUND_START, "round:2").state.decision_stack[-1]
    assert isinstance(pause.decision, ChanceDecision)
    assert is_fixed_outcome(pause.decision)
    assert pause.decision.decision_id == f"round:2:{ROUND_START}{FIXED_OUTCOME_SUFFIX}"

    answered = paused.resolve(pause.decision)

    assert answered == ChanceOutcome(pause.decision.decision_id, (CONTINUE,))
    assert paused.resolve(shuffle) == plain.resolve(shuffle)


def test_a_reshuffle_of_one_card_still_draws() -> None:
    # Only a pause is a fixed outcome: a one-card shuffle keeps drawing, as
    # every seeded game recorded before the pauses did.
    one = ChanceDecision(
        decision_id="round:2:player:0:discard_shuffle", prompt="x", options=("a",)
    )
    assert not is_fixed_outcome(one)


def test_every_round_start_after_the_first_pauses_before_the_reveal() -> None:
    engine = UprisingRulesEngine()
    finished = run_random_round(engine, RulesetConfig(), 0, 1000)
    pauses = [
        step.decision_id
        for step in finished.replay.steps
        if isinstance(step, ChanceOutcome)
        and step.decision_id.endswith(FIXED_OUTCOME_SUFFIX)
    ]
    # Round 1 opens with the setup; the pause stands before round 2's
    # reshuffles and reveal (and before reward recipients after the first).
    assert f"round:2:{ROUND_START}{FIXED_OUTCOME_SUFFIX}" in pauses


def test_the_round_start_pause_holds_back_the_reveal_and_the_draw() -> None:
    setup = create_initial_state(
        RulesetConfig(), seed=71, leader_ids=SELECTED_LEADERS
    ).state
    after_round = replace(
        setup, round_number=1, phase=GamePhase.ROUND_START, decision_stack=()
    )

    paused = _advance_automatic(RuleResult(state=after_round)).state

    top = paused.decision_stack[-1]
    assert top.kind == FrameKind.PAUSE
    assert isinstance(top.decision, ChanceDecision)
    assert paused.conflict_deck == after_round.conflict_deck
    assert paused.current_conflict_ids == after_round.current_conflict_ids
    assert [player.hand for player in paused.players] == [
        player.hand for player in after_round.players
    ]
    # Nobody has an action while the pause waits.
    engine = UprisingRulesEngine()
    assert all(engine.legal_actions(paused, seat) == () for seat in range(4))

    revealed = engine.apply(
        paused, ChanceOutcome(top.decision.decision_id, (CONTINUE,))
    ).state

    assert revealed.round_number == 2
    assert revealed.current_conflict_ids == (
        *after_round.current_conflict_ids,
        after_round.conflict_deck[0],
    )
    assert revealed.phase is GamePhase.PLAYER_TURNS
    top = revealed.decision_stack[-1]
    assert isinstance(top.decision, PlayerDecision)


def test_the_first_round_start_does_not_pause() -> None:
    setup = create_initial_state(
        RulesetConfig(), seed=71, leader_ids=SELECTED_LEADERS
    ).state
    before = replace(
        setup, round_number=0, phase=GamePhase.ROUND_START, decision_stack=()
    )

    started = _advance_automatic(RuleResult(state=before)).state

    assert started.round_number == 1
    assert all(frame.kind != FrameKind.PAUSE for frame in started.decision_stack)
