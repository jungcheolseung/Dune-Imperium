"""Records made by older engines replay on this one (records.migration).

Two kinds of evidence. Records made on *this* engine and then stripped of
what an older engine never recorded (its pauses, the Conflict-end windows
it never opened, the Combat Intrigue pass it never asked for) must come
back step for step through the bridges, while the codec gates keep each
bridge away from records that did meet the decision. And two records made
by the older engines themselves (``data/``, written by
``scripts/records/old_engine_record.py`` at master 37727846, codec v135,
5a2dfc19, codec v139, and 6b033158, codec v140) must replay to their end.

When an engine change makes a ``data/`` record stop, read the module
docstring of ``records.migration`` and docs/human-records.md before
touching this test: a new question the old engine never asked needs a
bridge; a recorded choice a rule change made illegal is a real divergence.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.records.migration import migrate_record, walk
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.persistence import parse_save_document
from dune_imperium.simulation.runner import run_policy_game

DATA = Path(__file__).parent / "data"
FULL = RulesetConfig(
    players=4,
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)
ENGINE = UprisingRulesEngine()


@pytest.fixture(scope="module")
def game() -> GameReplay:
    """A whole heuristic game on this engine with every module on."""

    agents = [make_agent("heuristic", 10 + seat) for seat in range(4)]
    return run_policy_game(ENGINE, FULL, 1, agents).replay


def _states(replay: GameReplay) -> list[GameState]:
    """The state before every recorded step."""

    states = [ENGINE.reset(replay.ruleset, replay.seed)]
    for step in replay.steps:
        states.append(ENGINE.apply(states[-1], step).state)
    return states[:-1]


def _older(replay: GameReplay, codec: int, drop: set[int] | None = None) -> GameReplay:
    """``replay`` as an engine of ``codec`` would have recorded it."""

    steps = tuple(
        step for index, step in enumerate(replay.steps) if index not in (drop or ())
    )
    return replace(replay, steps=steps, action_codec_version=codec)


def _pause_indices(replay: GameReplay) -> set[int]:
    return {
        index
        for index, (state, step) in enumerate(
            zip(_states(replay), replay.steps, strict=True)
        )
        if isinstance(step, ChanceOutcome)
        and isinstance(decision := ENGINE.current_decision(state), ChanceDecision)
        and is_fixed_outcome(decision)
    }


def _only_choice_in(replay: GameReplay, frame: FrameKind, action_id: str) -> set[int]:
    """Steps answering ``frame`` with ``action_id`` where nothing else was legal."""

    found = set()
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if (
            isinstance(step, DomainAction)
            and step.action_id == action_id
            and state.decision_stack[-1].kind == frame
            and ENGINE.legal_actions(state, step.actor) == (step,)
        ):
            found.add(index)
    return found


def _actor(replay: GameReplay, index: int) -> int:
    step = replay.steps[index]
    assert isinstance(step, DomainAction)
    return step.actor


def _steps(record_steps: tuple[ReplayStep, ...]) -> list[ReplayStep]:
    return list(record_steps)


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
    pauses = _pause_indices(game)
    assert len(pauses) >= 10

    record = migrate_record(_older(game, 139, pauses))

    assert record.complete
    assert record.bridge_counts() == {"pause": len(pauses)}
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash


def test_conflict_end_windows_are_declined_only_for_records_before_v141(
    game: GameReplay,
) -> None:
    declines = _only_choice_in(
        game, FrameKind.CONFLICT_END_TRIGGER, "decline_conflict_end_intrigue"
    )
    assert declines
    drop = _pause_indices(game) | declines

    before = migrate_record(_older(game, 140, drop))
    assert before.complete
    assert before.bridge_counts()["conflict_end_window"] == len(declines)
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    # A v141 record met the window, so a missing decline is not a bridge's.
    after = migrate_record(_older(game, 141, drop))
    assert after.divergence is not None
    first = min(declines)
    assert after.divergence.recorded_index == first - sum(
        1 for index in drop if index < first
    )


def test_a_combat_intrigue_pass_is_answered_only_for_records_before_v139(
    game: GameReplay,
) -> None:
    # A pass followed by another seat's step: dropping it leaves that seat's
    # Combat Intrigue question unanswered in the record.
    passes = sorted(
        index
        for index, step in enumerate(game.steps[:-1])
        if isinstance(step, DomainAction)
        and step.action_id == "pass_combat_intrigue"
        and getattr(game.steps[index + 1], "actor", None) != step.actor
    )
    dropped = passes[0]

    before = migrate_record(_older(game, 138, {dropped}))
    assert before.complete
    assert before.bridge_counts() == {"combat_intrigue_pass": 1}
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    after = migrate_record(_older(game, 139, {dropped}))
    assert after.divergence is not None
    assert after.divergence.recorded_index == dropped


def test_a_bridge_never_answers_the_decision_the_recorded_step_was_for(
    game: GameReplay,
) -> None:
    # The seat passed here; its recorded answer now carries an argument no
    # pass takes. The pass bridge is open for a v138 record, but the step
    # was this decision's own answer, so the migration must stop on it.
    index = next(
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction) and step.action_id == "pass_combat_intrigue"
    )
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    broken = DomainAction(
        action_id="pass_combat_intrigue",
        actor=recorded.actor,
        arguments=(("card_id", "intrigue:not_a_card:0"),),
    )
    steps = list(game.steps)
    steps[index] = broken
    record = migrate_record(replace(game, steps=tuple(steps), action_codec_version=138))

    assert record.divergence is not None
    assert record.divergence.recorded_index == index
    assert record.divergence.step == broken
    assert isinstance(record.divergence.pending, PlayerDecision)
    assert len(record.steps) == index
    before = _states(game)[index]
    assert canonical_state_hash(record.state) == canonical_state_hash(before)


@pytest.mark.parametrize(
    ("frame", "answer", "codec"),
    [
        (FrameKind.COMBAT_INTRIGUE, "pass_combat_intrigue", 138),
        (FrameKind.CONFLICT_END_TRIGGER, "decline_conflict_end_intrigue", 140),
    ],
)
def test_a_bridge_never_answers_a_decision_whose_answer_a_rule_change_removed(
    game: GameReplay, frame: FrameKind, answer: str, codec: int
) -> None:
    # The seat could only decline here; its recorded answer becomes a card
    # play the decision does not offer at all (as if a rule change had taken
    # every such play away). The decline bridge is open for this codec, but
    # the step was this decision's own answer.
    play = {
        FrameKind.COMBAT_INTRIGUE: "play_intrigue",
        FrameKind.CONFLICT_END_TRIGGER: "play_conflict_end_intrigue",
    }[frame]
    states = _states(game)
    index = next(
        index
        for index in sorted(_only_choice_in(game, frame, answer))
        if not any(
            action.action_id == play
            for action in ENGINE.legal_actions(states[index], _actor(game, index))
        )
    )
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    broken = DomainAction(
        action_id=play,
        actor=recorded.actor,
        arguments=(("card_id", "intrigue:not_a_card:0"),),
    )
    steps = list(game.steps)
    steps[index] = broken
    record = migrate_record(
        replace(game, steps=tuple(steps), action_codec_version=codec)
    )

    assert record.divergence is not None
    assert record.divergence.recorded_index == index
    assert len(record.steps) == index
    pending = record.divergence.pending
    assert isinstance(pending, PlayerDecision)
    assert pending.owner == recorded.actor
    assert record.state.decision_stack[-1].kind == frame


def _card_effect_steps(game: GameReplay) -> list[int]:
    """Steps naming an icon where it was the only icon offered."""

    states = _states(game)
    return [
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and step.action_id == "resolve_agent_card_effect"
        and step.arguments
        and [
            action
            for action in ENGINE.legal_actions(states[index], step.actor)
            if action.action_id == "resolve_agent_card_effect"
        ]
        == [step]
    ]


def test_a_card_effect_recorded_before_v137_named_its_icon_is_rewritten(
    game: GameReplay,
) -> None:
    index = _card_effect_steps(game)[0]
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    steps = list(game.steps)
    steps[index] = DomainAction(action_id=recorded.action_id, actor=recorded.actor)

    before = migrate_record(replace(game, steps=tuple(steps), action_codec_version=136))
    assert before.complete
    assert before.bridge_counts() == {"agent_card_effect_named": 1}
    assert before.steps[index].step == recorded
    assert before.steps[index].recorded_index == index
    assert canonical_state_hash(before.state) == game.expected_state_hash

    after = migrate_record(replace(game, steps=tuple(steps), action_codec_version=137))
    assert after.divergence is not None
    assert after.divergence.recorded_index == index


def test_a_missing_argument_elsewhere_is_a_choice_not_a_gap(
    game: GameReplay,
) -> None:
    # No ``discount`` means the seat did not use one; the record must stop
    # there rather than be rewritten into the discounted play.
    states = _states(game)
    index, recorded = next(
        (index, step)
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and dict(step.arguments).get("discount") is not None
        and DomainAction(
            action_id=step.action_id,
            actor=step.actor,
            arguments=tuple(pair for pair in step.arguments if pair[0] != "discount"),
        )
        not in ENGINE.legal_actions(states[index], step.actor)
    )
    plain = DomainAction(
        action_id=recorded.action_id,
        actor=recorded.actor,
        arguments=tuple(pair for pair in recorded.arguments if pair[0] != "discount"),
    )
    steps = list(game.steps)
    steps[index] = plain

    record = migrate_record(replace(game, steps=tuple(steps), action_codec_version=130))

    assert record.divergence is not None
    assert record.divergence.recorded_index == index
    assert not record.bridge_counts()


def test_walk_yields_the_state_before_each_migrated_step(game: GameReplay) -> None:
    record = migrate_record(_older(game, 139, _pause_indices(game)))
    walked = list(walk(record))

    assert [migrated for _, migrated in walked] == list(record.steps)
    expected = ENGINE.reset(game.ruleset, game.seed)
    for state, migrated in walked[:200]:
        assert canonical_state_hash(state) == canonical_state_hash(expected)
        expected = ENGINE.apply(expected, migrated.step).state


@pytest.mark.parametrize(
    ("name", "codec", "bridges"),
    [
        (
            "v135-app_ai-3",
            135,
            {
                "pause",
                "conflict_end_window",
                "combat_intrigue_pass",
                "agent_card_effect_named",
            },
        ),
        ("v139-heuristic-1", 139, {"pause", "conflict_end_window"}),
        ("v140-heuristic-1", 140, {"conflict_end_window"}),
    ],
)
def test_records_of_older_engines_replay_to_their_end(
    name: str, codec: int, bridges: set[str]
) -> None:
    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    replay = parse_save_document(document, check_versions=False).replay
    assert replay.action_codec_version == codec < ACTION_CODEC_VERSION

    record = migrate_record(replay)

    assert record.complete, record.divergence
    assert bridges <= set(record.bridge_counts())
    recorded = [m.recorded_index for m in record.steps if m.recorded_index is not None]
    assert recorded == list(range(len(replay.steps)))
