"""The record migration's mechanism (records.migration).

Every kept record is converted to the current codec at each codec bump
(records.convert, docs/human-records.md), so the migration keeps at most one
bridge from the previous codec besides ``pause``, which answers every
record. These tests hold the mechanism such a bridge plugs into, on games of
this engine with what an older engine never recorded taken out, and with
bridges made up for the test where the module has none:

- a record of this engine replays exactly, and one without its pauses comes
  back step for step through ``pause``;
- a bridge answers only records older than its codec, and never the
  decision a recorded step was made for (``_made_for``), even where a rule
  change took every action of that id away;
- a rewrite bridge puts a recorded step in this engine's terms, a follows
  bridge adds a step right after one, and follows that never settle end the
  record at their step;
- ``walk`` yields the state before each migrated step.

The bridges of codecs v135-v155 and their older-engine records were removed
when every kept record was converted to v156 (2026-10-29).
"""

from collections.abc import Sequence
from dataclasses import replace

import pytest
from tests.support.records import FULL, pause_indices, played_steps

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import Decision, PlayerDecision
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.records import migration
from dune_imperium.records.migration import (
    Bridge,
    migrate_record,
    replayed,
    rewrite_step,
    walk,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind

ENGINE = UprisingRulesEngine()
SEED = 3
OLDER = ACTION_CODEC_VERSION - 1
DECLINE = "decline_conflict_end_intrigue"
PLAY = "play_conflict_end_intrigue"
# A made-up bridge of the shape most bridges had: the Conflict-end window,
# which an engine before codec v141 never opened for a seat with no card to
# play (``_decline_in``), as if the current codec had added it.
WINDOW = Bridge(
    "test_window",
    migration._decline_in(
        FrameKind.CONFLICT_END_TRIGGER, DECLINE, frozenset({DECLINE, PLAY})
    ),
    before_codec=ACTION_CODEC_VERSION,
)


@pytest.fixture(scope="module")
def game() -> GameReplay:
    """A whole heuristic game on this engine with every module on, stamped
    as its saves are."""

    steps = played_steps(SEED)
    state = ENGINE.reset(FULL, SEED)
    for step in steps:
        state = ENGINE.apply(state, step).state
    return GameReplay(
        FULL,
        SEED,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )


def _states(replay: GameReplay) -> list[GameState]:
    """The state before every recorded step."""

    states = [ENGINE.reset(replay.ruleset, replay.seed)]
    for step in replay.steps:
        states.append(ENGINE.apply(states[-1], step).state)
    return states[:-1]


def _declines(replay: GameReplay) -> list[int]:
    """The Conflict-end window's declines where nothing else was offered:
    what an engine that never opened the window has no step for."""

    found = []
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if (
            isinstance(step, DomainAction)
            and state.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
            and ENGINE.legal_actions(state, step.actor) == (step,)
            and ENGINE.whole_actions(state, step.actor)
            == (DomainAction(DECLINE, step.actor),)
        ):
            found.append(index)
    return found


def _without(
    replay: GameReplay, dropped: Sequence[int], codec: int = OLDER
) -> GameReplay:
    """``replay`` without the steps ``dropped``, stamped ``codec``."""

    gone = set(dropped)
    steps = tuple(step for index, step in enumerate(replay.steps) if index not in gone)
    return replace(replay, steps=steps, action_codec_version=codec)


def _position(dropped: Sequence[int], index: int) -> int:
    """Where step ``index`` sits once the steps ``dropped`` are taken out."""

    return index - sum(1 for gone in dropped if gone < index)


def _steps(record: migration.MigratedRecord) -> list[ReplayStep]:
    return [migrated.step for migrated in record.steps]


def test_a_record_of_this_engine_replays_exactly(game: GameReplay) -> None:
    record = migrate_record(game)

    assert record.exact
    assert not record.bridge_counts()
    assert [migrated.recorded_index for migrated in record.steps] == list(
        range(len(game.steps))
    )


def test_pauses_an_older_engine_never_recorded_are_answered(
    game: GameReplay,
) -> None:
    pauses = pause_indices(SEED, game.steps)
    assert len(pauses) >= 10
    # ``pause`` answers a record of any codec, the current one too.
    for codec in (OLDER, ACTION_CODEC_VERSION):
        record = migrate_record(_without(game, pauses, codec))

        assert record.complete
        assert record.bridge_counts() == {"pause": len(pauses)}
        assert _steps(record) == list(game.steps)
        assert canonical_state_hash(record.state) == game.expected_state_hash
        assert not record.exact  # bridged, though to the recorded state


def test_a_bridge_answers_only_records_older_than_its_codec(
    game: GameReplay, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(migration, "BRIDGES", (*migration.BRIDGES, WINDOW))
    declines = _declines(game)
    assert len(declines) >= 4

    before = migrate_record(_without(game, declines))

    assert before.complete
    assert before.bridge_counts() == {"test_window": len(declines)}
    assert _steps(before) == list(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    # A record of the current codec met the window: a missing decline is not
    # the bridge's to answer.
    after = migrate_record(_without(game, declines, ACTION_CODEC_VERSION))
    assert after.divergence is not None
    assert after.divergence.recorded_index == declines[0]
    assert not after.bridge_counts()


@pytest.mark.parametrize("taken_away", [False, True])
def test_a_bridge_never_answers_the_decision_the_recorded_step_was_for(
    game: GameReplay, monkeypatch: pytest.MonkeyPatch, taken_away: bool
) -> None:
    # The seat could only decline here; its recorded answer becomes one the
    # window does not take: a decline with an argument no decline has, or,
    # as if a rule change had taken every such play away, a card play the
    # window offers none of. The window's bridge is open for the record's
    # codec, but the step was this decision's own answer, so the migration
    # stops on it.
    monkeypatch.setattr(migration, "BRIDGES", (*migration.BRIDGES, WINDOW))
    states = _states(game)
    index = _declines(game)[0]
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    broken = DomainAction(
        action_id=PLAY if taken_away else DECLINE,
        actor=recorded.actor,
        arguments=(("card_id", "intrigue:not_a_card:0"),),
    )
    assert not any(
        action.action_id == PLAY
        for action in ENGINE.whole_actions(states[index], recorded.actor)
    )
    steps = list(game.steps)
    steps[index] = broken
    older = replace(game, steps=tuple(steps), action_codec_version=OLDER)

    record = migrate_record(older)

    assert record.divergence is not None
    assert record.divergence.recorded_index == index
    assert record.divergence.step == broken
    pending = record.divergence.pending
    assert isinstance(pending, PlayerDecision) and pending.owner == recorded.actor
    assert record.state.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert _steps(record) == list(game.steps[:index])
    assert canonical_state_hash(record.state) == canonical_state_hash(states[index])


def _renamed(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """A made-up rewrite: an older engine's ``old_<id>`` is ``<id>`` here."""

    del engine, state, decision
    if isinstance(step, DomainAction) and step.action_id.startswith("old_"):
        return replace(step, action_id=step.action_id.removeprefix("old_"))
    return None


def test_a_rewrite_bridge_takes_the_recorded_step_s_place(
    game: GameReplay, monkeypatch: pytest.MonkeyPatch
) -> None:
    rename = Bridge(
        "test_rename", _renamed, before_codec=ACTION_CODEC_VERSION, rewrites=True
    )
    monkeypatch.setattr(migration, "BRIDGES", (*migration.BRIDGES, rename))
    passes = [
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction) and step.action_id == "pass_combat_intrigue"
    ]
    assert len(passes) >= 4
    steps = [
        replace(step, action_id=f"old_{step.action_id}")
        if index in passes and isinstance(step, DomainAction)
        else step
        for index, step in enumerate(game.steps)
    ]
    older = replace(game, steps=tuple(steps), action_codec_version=OLDER)

    record = migrate_record(older)

    assert record.complete
    assert _steps(record) == list(game.steps)
    assert record.bridge_counts() == {"test_rename": len(passes)}
    assert [m.recorded_index for m in record.steps if m.bridge] == passes
    # A move judged in the older engine's terms goes through the same bridge
    # (records.problems: the network's move), only for an older codec.
    state = _states(game)[passes[0]]
    old = steps[passes[0]]
    assert rewrite_step(ENGINE, state, old, OLDER) == game.steps[passes[0]]
    assert rewrite_step(ENGINE, state, old, ACTION_CODEC_VERSION) is None
    # Without the bridge the older record stops at its first renamed step.
    monkeypatch.setattr(migration, "BRIDGES", (migration.BRIDGES[0],))
    stopped = migrate_record(older)
    assert stopped.divergence is not None
    assert stopped.divergence.recorded_index == passes[0]


def _window_follows(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """A made-up ``follows`` bridge: the Conflict-end window an older engine
    never opened (the seat could only decline) is declined right after the
    step before it."""

    del step
    if not isinstance(decision, PlayerDecision) or engine.whole_actions(
        state, decision.owner
    ) != (DomainAction(DECLINE, decision.owner),):
        return None
    return WINDOW.answer(engine, state, decision, DomainAction("none", 0))


def test_a_follows_bridge_adds_its_step_right_after_the_recorded_one(
    game: GameReplay, monkeypatch: pytest.MonkeyPatch
) -> None:
    follow = Bridge(
        "test_follow", _window_follows, before_codec=ACTION_CODEC_VERSION, follows=True
    )
    monkeypatch.setattr(migration, "BRIDGES", (*migration.BRIDGES, follow))
    declines = _declines(game)

    record = migrate_record(_without(game, declines))

    assert record.complete
    assert _steps(record) == list(game.steps)
    assert record.bridge_counts() == {"test_follow": len(declines)}
    # The decline comes right after the recorded step before it, not when
    # the next recorded step is refused: a record that ends on that step
    # ends with the decline too.
    older = _without(game, declines)
    end = _position(declines, declines[0])
    cut = migrate_record(replace(older, steps=older.steps[:end]))
    assert cut.complete
    last = max(i for i, m in enumerate(cut.steps) if m.recorded_index is not None)
    assert cut.steps[last].recorded_index == end - 1
    tail = cut.steps[last + 1 :]
    assert tail and all(migrated.bridge == "test_follow" for migrated in tail)


def test_follows_that_never_settle_end_the_record_at_their_step(
    game: GameReplay, monkeypatch: pytest.MonkeyPatch
) -> None:
    follow = Bridge(
        "test_follow", _window_follows, before_codec=ACTION_CODEC_VERSION, follows=True
    )
    monkeypatch.setattr(migration, "BRIDGES", (*migration.BRIDGES, follow))
    declines = _declines(game)
    # A step after which two declines follow at once, as when two seats
    # without a card meet the window in a row.
    first = next(
        index
        for index, (a, b) in enumerate(zip(declines, declines[1:], strict=False))
        if b == a + 1
    )
    after = declines[first] - 1
    older = _without(game, declines)
    position = _position(declines, after)
    complete = migrate_record(older)
    before = next(
        state
        for state, migrated in walk(complete)
        if migrated.recorded_index == position
    )
    monkeypatch.setattr(migration, "MAX_FOLLOWS_PER_STEP", 1)

    record = migrate_record(older)

    assert record.divergence is not None
    assert record.divergence.recorded_index == position
    assert "did not settle" in record.divergence.reason
    assert record.steps[-1].recorded_index == position - 1
    assert canonical_state_hash(record.state) == canonical_state_hash(before)


def test_walk_yields_the_state_before_each_migrated_step(game: GameReplay) -> None:
    record = migrate_record(_without(game, pause_indices(SEED, game.steps)))
    walked = list(walk(record))

    assert record.walked is not None and record.walked[0] is record.steps
    assert [migrated for _, migrated in walked] == list(record.steps)
    expected = ENGINE.reset(game.ruleset, game.seed)
    for state, migrated in walked[:200]:
        assert canonical_state_hash(state) == canonical_state_hash(expected)
        expected = ENGINE.apply(expected, migrated.step).state
    # The kept states are the ones a replay from the reset reaches (they
    # compare equal field by field, stricter than the hash).
    again = list(replayed(record, ENGINE))
    assert all(a == b for (a, _), (b, _) in zip(walked, again, strict=True))


def test_walk_replays_a_record_rebuilt_with_other_steps(game: GameReplay) -> None:
    # A migration module may rebuild the record with steps of its own
    # (tests/unit/records/test_corpus_check.py); the kept states belong to
    # the steps they were taken for, so ``walk`` replays the new ones.
    record = migrate_record(game)
    shorter = replace(record, steps=record.steps[:200])

    walked = list(walk(shorter, ENGINE))

    assert shorter.walked is record.walked
    assert [m for _, m in walked] == list(shorter.steps)
    assert all(
        a == b for (a, _), (b, _) in zip(walked, replayed(shorter, ENGINE), strict=True)
    )
    assert walked[0][0] == ENGINE.reset(game.ruleset, game.seed)
