"""The log names a printed line that an event gives only by its index in
the line's words (user report 2026-11-09: a Conflict reward's "-OR-" line
read "N번째 줄" and a Reveal line paid late "효과 번호: 1").

The server reads the words off the position when it logs the step
(``session_log.event_line_words``) and adds them to the event's payload in
the log it serves (``sessions._log_entry_json``); the engine's events stay
as they are, so saves and records are untouched.
"""

from __future__ import annotations

import random

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.config import BaseGame
from dune_imperium.core import (
    ChanceDecision,
    GameEvent,
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.replay import ReplayStep
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.server.session_log import LoggedStep, event_line_words
from dune_imperium.server.sessions import _log_entry_json

ENGINE = UprisingRulesEngine()


def test_a_reveal_line_paid_late_is_named_in_its_words() -> None:
    """Interstellar Trade's one Reveal line, index 0 -- which the log's zero
    filter used to drop, leaving no line named at all."""

    state = ENGINE.reset(RulesetConfig(choam_module=True), 0)
    event = GameEvent(
        event_id="late",
        kind="reveal_line_granted_late",
        payload=(
            ("card_id", "imperium:interstellar_trade:0"),
            ("line_index", 0),
            ("persuasion", 1),
            ("player", 0),
        ),
    )
    assert event_line_words(state, (event,)) == (
        (
            "late",
            "+1 Persuasion per completed Contract",
            "+{persuasion:1} (완수한 {contract}마다)",
        ),
    )
    # Any other event, or a line the card does not print, has none.
    assert event_line_words(state, (GameEvent(event_id="x", kind="other"),)) == ()
    beyond = GameEvent(
        event_id="late",
        kind="reveal_line_granted_late",
        payload=(("card_id", "imperium:interstellar_trade:0"), ("line_index", 5)),
    )
    assert event_line_words(state, (beyond,)) == ()


def _first_reward_line_choice() -> tuple[GameState, GameEvent, LoggedStep]:
    """Rise of Ix on the original board, seed 1: the first time a Conflict
    reward's "-OR-" row has a line chosen (round 3, third place)."""

    state = ENGINE.reset(RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True), 1)
    resolver = ChanceResolver(seed=1)
    rng = random.Random(1)
    while state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        step: ReplayStep
        if isinstance(decision, ChanceDecision):
            step = resolver.resolve(decision)
        else:
            assert isinstance(decision, PlayerDecision)
            step = rng.choice(ENGINE.whole_actions(state, decision.owner))
        result = apply_whole(ENGINE, state, step)
        for event in result.events:
            if event.kind == "combat_reward_line_chosen":
                entry = LoggedStep(
                    step=step,
                    events=(event,),
                    reveals=False,
                    hidden_arguments=frozenset(),
                    event_words=event_line_words(state, (event,)),
                )
                return state, event, entry
        state = result.state
    raise AssertionError("no reward line was chosen")


def test_a_conflict_reward_line_is_logged_in_its_rows_words() -> None:
    state, event, entry = _first_reward_line_choice()
    payload = dict(event.payload)
    assert payload == {"line": 0, "player": 0, "rank": 3}
    assert entry.event_words == (
        (event.event_id, "Draw 1 Intrigue card", "{intrigue:1}"),
    )
    # Every seat's log carries the words beside the index, which stays.
    for seat in range(4):
        served = _log_entry_json(0, entry, seat, False)
        events = served["events"]
        assert isinstance(events, list)
        (logged,) = events
        assert isinstance(logged, dict)
        assert logged["payload"] == {
            **payload,
            "line_words": "Draw 1 Intrigue card",
            "line_words_ko": "{intrigue:1}",
        }
    assert state.phase is GamePhase.COMBAT
