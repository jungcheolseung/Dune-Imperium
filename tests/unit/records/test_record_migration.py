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
- the pause after Ilesa Ecaz's set-aside before the Scouts step (OQ-103 6)
  comes back through ``pause`` on both boards;
- ``walk`` yields the state before each migrated step;
- the one bridge from the previous codec, ``scouts_payout`` (OQ-164),
  clicks the Scouts collect windows an older engine never opened;
- ``owed_draw_row`` (codec v166) rewrites an immediate draw an older engine
  recorded as its whole action on a frame without steps as its step row;
- the Slig Farmer bridges (codec v168) put an older engine's one answer to
  its box -- ``resolve`` (the Solari, the payment declined) or ``pay`` (the
  Solari, then the payment) -- in this engine's two steps.

The bridges of codecs v135-v155 and their older-engine records were removed
when every kept record was converted to v156 (2026-10-29).
"""

from collections.abc import Sequence
from dataclasses import replace
from functools import cache

import pytest
from tests.support.records import FULL, pause_indices, played_steps

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.rulesets import content_for
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.records import migration
from dune_imperium.records.migration import (
    CONTROL_THE_SPICE_TROOP_BRIDGE,
    FEYD_LAST_TROOP_BRIDGE,
    FINAL_DELIVERY_LEADER,
    FINAL_DELIVERY_PAYMENT_BRIDGE,
    FINAL_DELIVERY_REWARDS_BRIDGE,
    FORBIDDEN_WEAPONS_KEEP_BRIDGE,
    OWED_DRAW_ROW_BRIDGE,
    OWED_DRAW_ROW_CODEC,
    RULES_AUDIT_CODEC,
    SCOUTS_NO_LINE_PASS_BRIDGE,
    SCOUTS_NO_LINE_PASS_CODEC,
    SCOUTS_PAYOUT_BRIDGE,
    SCOUTS_PAYOUT_CODEC,
    SLIG_FARMER_CODEC,
    SLIG_FARMER_LINE_BRIDGE,
    SLIG_FARMER_PAY_BRIDGE,
    SLIG_FARMER_PAY_LINE_BRIDGE,
    SPICE_AGONY_REWARDS_BRIDGE,
    THRONE_ROOM_TROOP_BRIDGE,
    Bridge,
    migrate_record,
    replayed,
    rewrite_step,
    walk,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import (
    EFFECT_STEP_FRAMES,
    TARGET_STEP_FRAMES,
    completed_whole,
    path_of,
    without_pick,
)
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, FrameKind
from dune_imperium.rules.one_step_ahead import ILESA
from dune_imperium.rules.scouts_effects import SCOUTS_COLLECT, SCOUTS_NO_OPTION
from dune_imperium.simulation.runner import run_policy_game

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


# The helpers below replay the module's one game; GameReplay and GameState
# are frozen, so each is worked out once per test process (``cache``) instead
# of once per call: the tests called them 9, 5 and 2 times, a whole replay
# each.


@cache
def _states(replay: GameReplay) -> tuple[GameState, ...]:
    """The state before every recorded step."""

    states = [ENGINE.reset(replay.ruleset, replay.seed)]
    for step in replay.steps:
        states.append(ENGINE.apply(states[-1], step).state)
    return tuple(states[:-1])


@cache
def _pauses(replay: GameReplay) -> tuple[int, ...]:
    """The steps of ``replay`` (the module's game) that answer a pause."""

    return tuple(pause_indices(SEED, replay.steps))


@cache
def _declines(replay: GameReplay) -> tuple[int, ...]:
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
    return tuple(found)


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
    pauses = _pauses(game)
    assert len(pauses) >= 10
    # ``pause`` answers a record of any codec, the current one too.
    for codec in (OLDER, ACTION_CODEC_VERSION):
        record = migrate_record(_without(game, pauses, codec))

        assert record.complete
        assert record.bridge_counts() == {"pause": len(pauses)}
        assert _steps(record) == list(game.steps)
        assert canonical_state_hash(record.state) == game.expected_state_hash
        assert not record.exact  # bridged, though to the recorded state


@pytest.mark.parametrize("base_game", [BaseGame.UPRISING, BaseGame.IMPERIUM])
def test_the_pause_after_ilesas_set_aside_is_answered_for_an_older_record(
    base_game: BaseGame,
) -> None:
    """OQ-103 6 (2026-11-03): an engine before it ran Ilesa Ecaz's set-aside
    straight into the Arrakeen Scouts step. Its records, without the
    ``round:N:scouts_step:pause`` steps, come back step for step through
    ``pause`` to the recorded state: no bridge of its own is needed."""

    config = RulesetConfig(base_game=base_game, rise_of_ix=True, arrakeen_scouts=True)
    leaders = tuple(
        leader.leader_id
        for leader in content_for(config).leaders
        if leader.leader_id != ILESA
    )[:3]
    engine = UprisingRulesEngine(leader_ids=(leaders[0], ILESA, *leaders[1:]))
    agents = [make_agent("heuristic", SEED * 10 + seat) for seat in range(4)]
    game = run_policy_game(engine, config, SEED, agents).replay
    state = engine.reset(config, SEED)
    added = []
    for index, step in enumerate(game.steps):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision) and decision.decision_id.endswith(
            ":scouts_step:pause"
        ):
            added.append(index)
        state = engine.apply(state, step).state
    # One a round: her hand is never empty at Round Start's end.
    assert len(added) == state.round_number

    record = migrate_record(_without(game, added), engine)

    assert record.complete
    assert record.bridge_counts() == {"pause": len(added)}
    assert _steps(record) == list(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash


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
    record = migrate_record(_without(game, _pauses(game)))
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


def _collects(replay: GameReplay) -> list[int]:
    """The Scouts collect clicks (OQ-164): what an engine before the click
    has no step for."""

    return [
        index
        for index, step in enumerate(replay.steps)
        if isinstance(step, DomainAction) and step.action_id == SCOUTS_COLLECT
    ]


def _payout_clicks(replay: GameReplay) -> list[int]:
    """The collect clicks of a Scouts payout's window (OQ-164 (a), (b)):
    what an engine of codec v161 has no step for."""

    from dune_imperium.rules.scouts_effects import is_payout

    return [
        index
        for index, (state, step) in enumerate(
            zip(_states(replay), replay.steps, strict=True)
        )
        if isinstance(step, DomainAction)
        and step.action_id == SCOUTS_COLLECT
        and (
            is_payout(state.decision_stack[-1])
            or dict(state.decision_stack[-1].context).get("item")
            == "tap_into_spice_reserves"
        )
    ]


# The module's game (seed 3) pays no Scouts payout since Throne Room
# Politics' and Control the Spice's icons became steps of their own (the
# printed-effects audit P-2, P-3, 2026-11-09): its heuristic walk moved. Of
# FULL seeds 0-11, seeds 0, 2, 4, 9 and 10 pay one; this test takes seed 4
# (three payout clicks).
PAYOUT_SEED = 4


@pytest.fixture(scope="module")
def payout_game() -> GameReplay:
    steps = played_steps(PAYOUT_SEED)
    state = ENGINE.reset(FULL, PAYOUT_SEED)
    for step in steps:
        state = ENGINE.apply(state, step).state
    return GameReplay(
        FULL,
        PAYOUT_SEED,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )


def test_scouts_payout_answers_the_clicks_an_older_engine_never_asked(
    payout_game: GameReplay,
) -> None:
    """User decisions 2026-11-01 (OQ-164 (a), (b)): every Scouts payout
    waits for its seat's click; an engine of codec v161 paid it unasked. The
    bridge clicks it before the recorded step it holds back, which reaches
    the recorded game step for step; a record of the click's own codec gets
    no bridge. The same bridge answers the line clicks an engine before
    v161 never asked (``_collects``)."""

    game = payout_game
    payouts = _payout_clicks(game)
    assert payouts
    older = migrate_record(_without(game, payouts, SCOUTS_PAYOUT_CODEC - 1))

    assert older.complete
    assert older.bridge_counts() == {SCOUTS_PAYOUT_BRIDGE: len(payouts)}
    assert _steps(older) == list(game.steps)
    assert canonical_state_hash(older.state) == game.expected_state_hash

    collects = _collects(game)
    oldest = migrate_record(_without(game, collects, SCOUTS_PAYOUT_CODEC - 2))
    assert oldest.complete
    assert oldest.bridge_counts() == {SCOUTS_PAYOUT_BRIDGE: len(collects)}
    assert canonical_state_hash(oldest.state) == game.expected_state_hash

    newer = migrate_record(_without(game, payouts, SCOUTS_PAYOUT_CODEC))
    assert newer.divergence is not None
    assert newer.divergence.recorded_index == payouts[0]
    assert not newer.bridge_counts()


# An app AI game of the original board with Rise of Ix that recalls a
# Freighter into the Bene Gesserit bonus (the 2026-11-07 scan's seed).
OWED_DRAW_SEED = 10429
ORIGINAL_IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, leader_draft=True
)


@cache
def _owed_draw_game() -> GameReplay:
    agents = tuple(
        make_agent("app_ai", 900000 + OWED_DRAW_SEED + seat, ORIGINAL_IX)
        for seat in range(4)
    )
    return run_policy_game(ENGINE, ORIGINAL_IX, OWED_DRAW_SEED, agents).replay


def test_owed_draw_row_rewrites_the_whole_an_older_engine_offered() -> None:
    """Codec v166: an immediate draw is shown by its step row on every frame
    (``effect_steps.presents_steps``). An older engine offered it as its
    whole action on a frame without steps (the Shipping rewards window, the
    Unload hold); such a recorded whole comes back as the row, step for
    step, and only for a record older than the bridge's codec."""

    game = _owed_draw_game()
    states = _states(game)
    rows = [
        index
        for index, (state, step) in enumerate(zip(states, game.steps, strict=True))
        if isinstance(step, DomainAction)
        and step.action_id == "draw"
        and state.decision_stack[-1].kind not in EFFECT_STEP_FRAMES
        and state.decision_stack[-1].kind not in TARGET_STEP_FRAMES
    ]
    assert rows
    wholes = {}
    for index in rows:
        state, row = states[index], game.steps[index]
        assert isinstance(row, DomainAction)
        whole = completed_whole(state, row, ENGINE.whole_actions(state, row.actor))
        assert whole is not None
        wholes[index] = whole
    assert {whole.action_id for whole in wholes.values()} == {"draw_owed_intrigue"}
    steps = tuple(wholes.get(index, step) for index, step in enumerate(game.steps))

    older = migrate_record(
        replace(game, steps=steps, action_codec_version=OWED_DRAW_ROW_CODEC - 1)
    )
    assert older.complete
    assert _steps(older) == list(game.steps)
    assert older.bridge_counts() == {OWED_DRAW_ROW_BRIDGE: len(rows)}
    assert canonical_state_hash(older.state) == game.expected_state_hash

    newer = migrate_record(
        replace(game, steps=steps, action_codec_version=OWED_DRAW_ROW_CODEC)
    )
    assert newer.divergence is not None
    assert newer.divergence.recorded_index == rows[0]


# Slig Farmer (codec v168, 2026-11-08): "Gain 1 solari per Agent icon on the
# other grafted card, You may pay 5 solari -> Advance the Tleilaxu track", two
# steps here (OQ-027) where an older engine offered ``resolve`` (the Solari,
# the payment declined) or ``pay`` (the Solari, then the payment). A heuristic
# game of this engine where seat boxes take the line alone twice and the line
# then the payment once.
# Seed 13's game pays an arrow before its line, which no older engine did.
# (Seed 12's did until Spice Agony's rewards became steps after its payment,
# printed-effects audit F-2, 2026-11-09, which moves the heuristic games; of
# 0-39, seeds 13, 18, 37 and 39 now do.)
SLIG_SEED = 3
SLIG_PAY_FIRST_SEED = 13
SLIG_CONFIG = RulesetConfig(immortality=True, promo_cards=True)


@cache
def _slig_game(seed: int = SLIG_SEED) -> GameReplay:
    steps = played_steps(seed, config=SLIG_CONFIG)
    state = ENGINE.reset(SLIG_CONFIG, seed)
    for step in steps:
        state = ENGINE.apply(state, step).state
    return GameReplay(
        SLIG_CONFIG,
        seed,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )


def _slig_row(step: ReplayStep, verb: str, icon: str) -> bool:
    return (
        isinstance(step, DomainAction)
        and step.action_id == verb
        and dict(step.arguments).get("printed") == "slig_farmer"
        and dict(step.arguments).get("icon") == icon
    )


def _older_slig_steps(game: GameReplay) -> tuple[tuple[ReplayStep, ...], int, int]:
    """The game's Slig Farmer steps as the older engine recorded them: a
    Solari line the payment follows at once is one ``pay``, any other line a
    ``resolve``; the older rows named no icon. Also how many of each."""

    older: list[ReplayStep] = []
    resolves = pays = 0
    steps = game.steps
    index = 0
    while index < len(steps):
        step = steps[index]
        assert not _slig_row(step, "pay", "tleilaxu"), "a payment before its line"
        if not _slig_row(step, "gain", "solari"):
            older.append(step)
            index += 1
            continue
        assert isinstance(step, DomainAction)
        plain = tuple((k, v) for k, v in step.arguments if k != "icon")
        following = steps[index + 1] if index + 1 < len(steps) else None
        if following is not None and _slig_row(following, "pay", "tleilaxu"):
            older.append(DomainAction("pay", step.actor, plain))
            pays += 1
            index += 2
        else:
            older.append(DomainAction("resolve", step.actor, plain))
            resolves += 1
            index += 1
    return tuple(older), resolves, pays


def test_slig_farmer_bridges_split_an_older_engine_s_answer_into_two_steps() -> None:
    """An older ``resolve`` comes back as the Solari line, its arrow left to
    lapse at the turn's end as that engine dropped it; an older ``pay`` as
    the line, then the payment, in that engine's order. The game comes back
    step for step to this engine's state, and only for a record older than
    the bridges' codec."""

    game = _slig_game()
    older, resolves, pays = _older_slig_steps(game)
    assert (resolves, pays) == (2, 1)

    migrated = migrate_record(
        replace(game, steps=older, action_codec_version=SLIG_FARMER_CODEC - 1)
    )
    assert migrated.complete
    assert _steps(migrated) == list(game.steps)
    assert migrated.bridge_counts() == {
        SLIG_FARMER_LINE_BRIDGE: resolves,
        SLIG_FARMER_PAY_LINE_BRIDGE: pays,
        SLIG_FARMER_PAY_BRIDGE: pays,
    }
    assert canonical_state_hash(migrated.state) == game.expected_state_hash

    newer = migrate_record(
        replace(game, steps=older, action_codec_version=SLIG_FARMER_CODEC)
    )
    assert newer.divergence is not None
    first = next(
        index
        for index, step in enumerate(older)
        if isinstance(step, DomainAction)
        and dict(step.arguments).get("printed") == "slig_farmer"
        and step.action_id in ("resolve", "pay")
    )
    assert newer.divergence.recorded_index == first


def test_a_slig_farmer_record_of_this_engine_paying_first_replays_exactly() -> None:
    """This engine may pay Slig Farmer's arrow before its Solari line; its
    row names the icon, so no older-engine bridge reads it, whatever the
    record's codec stamp."""

    game = _slig_game(SLIG_PAY_FIRST_SEED)
    rows = [
        index
        for index, step in enumerate(game.steps)
        if _slig_row(step, "pay", "tleilaxu")
        and not _slig_row(game.steps[index - 1], "gain", "solari")
    ]
    assert rows  # an arrow paid before its line
    record = migrate_record(replace(game, action_codec_version=SLIG_FARMER_CODEC - 1))
    assert record.exact


# The printed-effects audit (codec v170, user 2026-11-09). Forbidden Weapons'
# optional Shield Wall icon is, in its owner's own turn, its detonation row
# alone, and the turn-end press lapses it unused (OQ-095 (2)): an older
# engine's in-turn keep of the wall is dropped. Spice Agony pays its spice as
# one step and leaves its memory and Intrigue card as steps (OQ-106): an
# older engine did both inside the payment, the memory first. Heuristic games
# with Bloodlines and the Tech Module: seed 1 buys Forbidden Weapons and
# keeps the wall, seed 4 pays Spice Agony once, then takes its memory before
# its draw (the older engine's order).
AUDIT_CONFIG = RulesetConfig(bloodlines=True, tech_module=True)
FORBIDDEN_WEAPONS_KEEP_SEED = 1
SPICE_AGONY_SEED = 4


@cache
def _audit_game(seed: int) -> GameReplay:
    steps = played_steps(seed, config=AUDIT_CONFIG)
    state = ENGINE.reset(AUDIT_CONFIG, seed)
    for step in steps:
        state = ENGINE.apply(state, step).state
    return GameReplay(
        AUDIT_CONFIG,
        seed,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )


def _spice_agony_row(step: ReplayStep, verb: str, icon: str) -> bool:
    return (
        isinstance(step, DomainAction)
        and step.action_id == verb
        and dict(step.arguments).get("printed") == "lady_jessica"
        and dict(step.arguments).get("option" if verb == "pay" else "icon") == icon
    )


def test_an_older_spice_agony_payment_takes_its_memory_then_its_draw() -> None:
    game = _audit_game(SPICE_AGONY_SEED)
    pays = [
        index
        for index, step in enumerate(game.steps)
        if _spice_agony_row(step, "pay", "spice")
    ]
    assert pays
    for index in pays:
        assert _spice_agony_row(game.steps[index + 1], "take", "memory")
        assert _spice_agony_row(game.steps[index + 2], "draw", "intrigue")
    rewards = {index + 1 for index in pays} | {index + 2 for index in pays}
    older = tuple(
        step for index, step in enumerate(game.steps) if index not in rewards
    )
    record = migrate_record(
        replace(game, steps=older, action_codec_version=RULES_AUDIT_CODEC - 1)
    )
    assert record.complete
    assert record.bridge_counts() == {SPICE_AGONY_REWARDS_BRIDGE: 2 * len(pays)}
    assert _steps(record) == list(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash
    # A record of this engine takes its rewards as recorded, whatever its
    # codec stamp.
    assert migrate_record(
        replace(game, action_codec_version=RULES_AUDIT_CODEC - 1)
    ).exact


def test_the_spice_agony_bridge_answers_right_after_an_older_payment() -> None:
    # Codex review 2026-11-09: OQ-167 lets an owed effect through the part-way
    # box, so a bridge waiting for a refusal would answer too late where an
    # older record's next step is such an effect (a Tech tile's troop taking
    # the supply's last troop before the memory, which the older engine,
    # doing the memory inside the payment, never let happen). The bridge
    # follows the payment, and it is left out of a record that takes its
    # memory as a step (every record of this engine).
    from dune_imperium.agents.agent_turn_steps import apply_whole

    bridge = next(b for b in migration.BRIDGES if b.name == SPICE_AGONY_REWARDS_BRIDGE)
    assert bridge.follows
    assert bridge.older is not None
    game = _audit_game(SPICE_AGONY_SEED)
    pay = next(
        index
        for index, step in enumerate(game.steps)
        if _spice_agony_row(step, "pay", "spice")
    )
    rewards = {pay + 1, pay + 2}
    older = replace(
        game,
        steps=tuple(s for i, s in enumerate(game.steps) if i not in rewards),
        action_codec_version=RULES_AUDIT_CODEC - 1,
    )
    assert bridge.older(older)
    assert not bridge.older(game)
    state = ENGINE.reset(game.ruleset, game.seed)
    for step in game.steps[: pay + 1]:
        state = ENGINE.apply(state, step).state
    decision = ENGINE.current_decision(state)
    assert decision is not None
    answers = []
    for _ in range(3):
        answer = bridge.answer(ENGINE, state, decision, game.steps[pay])
        if answer is None:
            break
        answers.append(answer)
        state = apply_whole(ENGINE, state, answer).state
        decision = ENGINE.current_decision(state)
        assert decision is not None
    assert [dict(a.arguments)["effect"] for a in answers] == ["memory", "intrigue"]  # type: ignore[union-attr]


def test_an_older_in_turn_keep_of_the_shield_wall_is_dropped() -> None:
    game = _audit_game(FORBIDDEN_WEAPONS_KEEP_SEED)
    state = ENGINE.reset(game.ruleset, game.seed)
    finish = None
    for index, step in enumerate(game.steps):
        frame = state.decision_stack[-1] if state.decision_stack else None
        pending = "" if frame is None else dict(frame.context).get(
            TECH_ACQUIRE_PENDING_KEY, ""
        )
        if (
            isinstance(step, DomainAction)
            and step.action_id in ("finish_agent_turn", "finish_reveal")
            and "forbidden_weapons:shield_wall" in str(pending).split(",")
        ):
            finish = index
            break
        state = ENGINE.apply(state, step).state
    assert finish is not None  # the wall kept: the press lapses the icon
    actor = game.steps[finish].actor  # type: ignore[union-attr]
    keep = DomainAction(
        "destroy_shield_wall",
        actor,
        (
            ("icon", "shield_wall"),
            ("printed", "forbidden_weapons"),
            ("source", "tech"),
        ),
    )
    older = (*game.steps[:finish], keep, *game.steps[finish:])
    record = migrate_record(
        replace(game, steps=older, action_codec_version=RULES_AUDIT_CODEC - 1)
    )
    assert record.complete
    assert record.dropped == ((finish, FORBIDDEN_WEAPONS_KEEP_BRIDGE),)
    assert record.bridge_counts() == {FORBIDDEN_WEAPONS_KEEP_BRIDGE: 1}
    assert _steps(record) == list(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash
    # Stamped with this engine's codec, a keep is a choice no longer legal.
    newer = migrate_record(
        replace(game, steps=older, action_codec_version=RULES_AUDIT_CODEC)
    )
    assert newer.divergence is not None
    assert newer.divergence.recorded_index == finish


# Final Delivery (OQ-148 (가)) pays its 7 Solari as one step and leaves its
# Influence, troop and spice as steps; an older engine chose the Faction in
# the payment's own row (``gain_influence`` then ``choose_faction``) and gave
# all three at once. Personal Training's last space (OQ-027) leaves its troop
# beside its Spy; an older engine recruited it on arrival. Seed 15 of an
# original game with Yuna seated (heuristic): she pays Final Delivery once,
# then takes the troop, the spice and the Influence. Seed 26 of the default
# Uprising game: Feyd reaches his last space, places the Spy, then recruits.
YUNA_LEADERS = (
    "princess_yuna_moritani",
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
)
YUNA_CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
FINAL_DELIVERY_SEED = 15
FEYD_LAST_SPACE_SEED = 26


def _without_log(state: GameState) -> str:
    return canonical_state_hash(replace(state, event_log=()))


def test_an_older_final_delivery_pays_before_its_influence_row() -> None:
    engine = UprisingRulesEngine(leader_ids=YUNA_LEADERS)
    agents = [make_agent("heuristic", FINAL_DELIVERY_SEED * 10 + s) for s in range(4)]
    game = run_policy_game(engine, YUNA_CONFIG, FINAL_DELIVERY_SEED, agents).replay
    pay = next(
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and step.action_id == "pay"
        and dict(step.arguments).get("printed") == FINAL_DELIVERY_LEADER
    )
    rewards = game.steps[pay + 1 : pay + 6]
    assert [step.action_id for step in rewards] == [  # type: ignore[union-attr]
        "recruit",
        "gain",
        "gain_influence",
        "choose_faction",
        "deploy_troops",
    ]
    # The older engine: the Influence row and its Faction were the payment.
    older = (*game.steps[:pay], rewards[2], rewards[3], *game.steps[pay + 5 :])
    record = migrate_record(
        replace(game, steps=older, action_codec_version=RULES_AUDIT_CODEC - 1),
        engine,
    )
    assert record.complete
    assert record.bridge_counts() == {
        FINAL_DELIVERY_PAYMENT_BRIDGE: 1,
        FINAL_DELIVERY_REWARDS_BRIDGE: 2,
    }
    newer = migrate_record(game, engine)
    assert newer.exact
    # The same game; only the reward events' order differs (the older
    # engine's spice and troop came with the payment).
    assert _without_log(record.state) == _without_log(newer.state)


def test_an_older_feyd_last_space_takes_its_troop_on_arrival() -> None:
    # The older engine recruited the troop on arrival, and the Spy steps the
    # record goes on with stay legal here, so the bridge follows the arrival
    # (a refusal would leave every position before the troop with it in the
    # supply; rules-audit-s3 gate 2026-11-09). This engine offers the troop
    # and the Spy in either order (OQ-027), so the migrated record takes the
    # troop first and ends in the same game.
    bridge = _bridge(FEYD_LAST_TROOP_BRIDGE)
    assert bridge.follows
    assert bridge.older is not None
    steps = played_steps(FEYD_LAST_SPACE_SEED, config=RulesetConfig())
    final = next(
        index
        for index, step in enumerate(steps)
        if isinstance(step, DomainAction)
        and dict(step.arguments).get("space_id") == "final"
    )
    troop = final + 3
    assert dict(steps[troop].arguments) == {  # type: ignore[union-attr]
        "icon": "troops",
        "printed": "feyd_rautha_harkonnen",
        "source": "leader",
    }
    state = ENGINE.reset(RulesetConfig(), FEYD_LAST_SPACE_SEED)
    for step in steps:
        state = ENGINE.apply(state, step).state
    game = GameReplay(
        RulesetConfig(),
        FEYD_LAST_SPACE_SEED,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )
    older = (*steps[:troop], *steps[troop + 1 :])
    record = migrate_record(
        replace(game, steps=older, action_codec_version=RULES_AUDIT_CODEC - 1)
    )
    on_arrival = (
        *steps[: final + 1],
        steps[troop],
        *steps[final + 1 : troop],
        *steps[troop + 1 :],
    )
    assert record.complete
    assert record.bridge_counts() == {FEYD_LAST_TROOP_BRIDGE: 1}
    assert _steps(record) == list(on_arrival)
    assert canonical_state_hash(record.state) == _replay_to(
        RulesetConfig(), FEYD_LAST_SPACE_SEED, on_arrival
    )
    assert _without_log(record.state) == _without_log(state)
    assert bridge.older(record.replay)
    assert not bridge.older(game)


# Throne Room Politics (OQ-027 card Agent box extension 3) offers its troop
# and its trash icon from the placement; an older engine resolved the troop
# with ``resolve`` and its trash rows read the same. Control the Spice
# (OQ-148) arms its troop at the payment; an older engine recruited it with
# the payment. Heuristic games: Immortality seed 0 plays Throne Room
# Politics and takes the troop first; Epic seed 1 pays Control the Spice,
# takes the troop and then deploys.
THRONE_ROOM_SEED = 0
CONTROL_THE_SPICE_SEED = 1


def _replay_of(config: RulesetConfig, seed: int) -> GameReplay:
    steps = played_steps(seed, config=config)
    state = ENGINE.reset(config, seed)
    for step in steps:
        state = ENGINE.apply(state, step).state
    return GameReplay(
        config,
        seed,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )


def _card_troop(step: ReplayStep, card: str) -> bool:
    return (
        isinstance(step, DomainAction)
        and step.action_id == "recruit"
        and dict(step.arguments).get("printed") == card
        and dict(step.arguments).get("icon") == "troops"
    )


def test_an_older_throne_room_resolve_is_its_troops_icon() -> None:
    game = _replay_of(RulesetConfig(immortality=True), THRONE_ROOM_SEED)
    troops = [
        index
        for index, step in enumerate(game.steps)
        if _card_troop(step, "throne_room_politics")
    ]
    assert troops

    def older(step: ReplayStep) -> ReplayStep:
        assert isinstance(step, DomainAction)
        arguments = {**dict(step.arguments)}
        del arguments["icon"]
        return DomainAction("resolve", step.actor, tuple(sorted(arguments.items())))

    steps = tuple(
        older(step) if index in troops else step
        for index, step in enumerate(game.steps)
    )
    record = migrate_record(
        replace(game, steps=steps, action_codec_version=RULES_AUDIT_CODEC - 1)
    )
    assert record.complete
    assert record.bridge_counts() == {THRONE_ROOM_TROOP_BRIDGE: len(troops)}
    assert _steps(record) == list(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash


def test_an_older_control_the_spice_payment_takes_its_troop_right_after_it() -> (
    None
):
    # The heuristic takes each of its three troops right after the payment
    # (the first before a deployment, the others before the card's trash);
    # an older record has none of them.
    game = _replay_of(RulesetConfig(epic_game=True), CONTROL_THE_SPICE_SEED)
    troops = [
        index
        for index, step in enumerate(game.steps)
        if _card_troop(step, "control_the_spice")
    ]
    assert len(troops) == 3
    assert all(game.steps[i - 1].action_id == "pay" for i in troops)  # type: ignore[union-attr]
    steps = tuple(step for i, step in enumerate(game.steps) if i not in troops)
    record = migrate_record(
        replace(game, steps=steps, action_codec_version=RULES_AUDIT_CODEC - 1)
    )
    assert record.complete
    assert record.bridge_counts() == {CONTROL_THE_SPICE_TROOP_BRIDGE: 3}
    assert _steps(record) == list(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash


def _bridge(name: str) -> migration.Bridge:
    return next(bridge for bridge in migration.BRIDGES if bridge.name == name)


def _replay_to(config: RulesetConfig, seed: int, steps: Sequence[ReplayStep]) -> str:
    state = ENGINE.reset(config, seed)
    for step in steps:
        state = ENGINE.apply(state, step).state
    return canonical_state_hash(state)


def test_an_older_control_the_spice_trash_first_finds_its_troop_taken() -> None:
    # rules-audit-s3 gate 2026-11-09: the card's trash stays legal right
    # after the payment, so a bridge waiting for a refusal gave the troop
    # only later, and two human problems judged at the trash's pick (the
    # older engine's troop already in the garrison) no longer matched. The
    # bridge follows the payment; a record that takes the troop as a step
    # (every record of this engine) is left out of it.
    bridge = _bridge(CONTROL_THE_SPICE_TROOP_BRIDGE)
    assert bridge.follows
    assert bridge.older is not None
    config = RulesetConfig(epic_game=True)
    game = _replay_of(config, CONTROL_THE_SPICE_SEED)
    troop = next(
        index
        for index, step in enumerate(game.steps)
        if _card_troop(step, "control_the_spice")
    )
    state = ENGINE.reset(config, CONTROL_THE_SPICE_SEED)
    for step in game.steps[:troop]:
        state = ENGINE.apply(state, step).state
    actor = game.steps[troop].actor  # type: ignore[union-attr]
    trash = DomainAction(
        "trash", actor, (("printed", "control_the_spice"), ("source", "agent_card"))
    )
    assert trash in ENGINE.legal_actions(state, actor)
    after = ENGINE.apply(ENGINE.apply(state, game.steps[troop]).state, trash).state
    pick = next(
        action
        for action in ENGINE.legal_actions(after, actor)
        if action.action_id == "choose_personal_card"
    )
    newer = (*game.steps[: troop + 1], trash, pick)
    older = (*game.steps[:troop], trash, pick)
    record = migrate_record(
        GameReplay(
            config,
            CONTROL_THE_SPICE_SEED,
            older,
            _replay_to(config, CONTROL_THE_SPICE_SEED, newer),
            action_codec_version=RULES_AUDIT_CODEC - 1,
        )
    )
    assert record.complete
    assert record.bridge_counts() == {CONTROL_THE_SPICE_TROOP_BRIDGE: 1}
    assert _steps(record) == list(newer)
    assert canonical_state_hash(record.state) == record.replay.expected_state_hash
    assert bridge.older(record.replay)
    assert not bridge.older(game)


def test_the_feyd_troop_record_test_reads_the_arrival_turn_only() -> None:
    # A Ghola's copy of the Signet Ring prints its rewards ``ghola``, as other
    # copied Signet rewards do, so only a troop row in the arrival's own turn
    # makes a record this engine's.
    older = _bridge(FEYD_LAST_TROOP_BRIDGE).older
    assert older is not None

    def replay(*steps: DomainAction) -> GameReplay:
        return GameReplay(
            RulesetConfig(), 0, steps, "-", action_codec_version=RULES_AUDIT_CODEC - 1
        )

    arrive = DomainAction("choose_track_space", 1, (("space_id", "final"),))
    finish = DomainAction("finish_agent_turn", 1)

    def troop(printed: str, actor: int = 1) -> DomainAction:
        source = "leader" if printed == "feyd_rautha_harkonnen" else "agent_card"
        return DomainAction(
            "recruit",
            actor,
            (("icon", "troops"), ("printed", printed), ("source", source)),
        )

    assert not older(replay(arrive, troop("feyd_rautha_harkonnen"), finish))
    assert not older(replay(arrive, troop("ghola"), finish))
    assert older(replay(arrive, finish))
    assert older(replay(arrive, finish, troop("ghola")))
    assert older(replay(troop("ghola"), arrive, finish))
    assert older(replay(arrive, troop("ghola", actor=2), finish))


# Codec v172 (user decision 2026-11-11 "(가)", OQ-071; hidden-information
# sweep finding 1): a seat with no Scouts line it can take, at an item that
# prints a pass, passes. A heuristic game of the original board with Scouts
# and Immortality where two seats pass Desert Gift holding only starter
# cards, one of them beside a specimen return (OQ-050).
NO_LINE_PASS_SEED = 3
ORIGINAL_SCOUTS = RulesetConfig(
    base_game=BaseGame.IMPERIUM, arrakeen_scouts=True, immortality=True
)


def _owner_of(frame: object) -> int:
    decision = getattr(frame, "decision", None)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _no_line_passes(game: GameReplay, states: Sequence[GameState]) -> list[int]:
    """The steps where a seat passes a Scouts choice that offers it no line."""

    return [
        index
        for index, (state, step) in enumerate(zip(states, game.steps, strict=True))
        if isinstance(step, DomainAction)
        and step.action_id == "scouts_pass"
        and not any(
            action.action_id == "scouts_choose_option"
            for action in ENGINE.whole_actions(state, step.actor)
        )
    ]


def _check_no_line_pass_bridge(
    game: GameReplay, states: Sequence[GameState], passes: list[int], form: str
) -> None:
    """Older forms of ``game``, its no-line passes recorded as the confirm
    (``form``: the whole action, or the step row a record holds), come back
    as the pass, step for step, and only for a record older than the
    bridge's codec."""

    def confirm(index: int) -> ReplayStep:
        whole = DomainAction(
            action_id=SCOUTS_NO_OPTION,
            actor=_owner_of(states[index].decision_stack[-1]),
        )
        if form == "whole":
            return whole
        row = path_of(without_pick(states[index]), whole)
        assert row is not None and len(row) == 1
        assert row[0].action_id == "confirm_empty"
        item = dict(states[index].decision_stack[-1].context)["item"]
        assert dict(row[0].arguments)["printed"] == item
        return row[0]

    steps = tuple(
        confirm(index) if index in passes else step
        for index, step in enumerate(game.steps)
    )

    older = migrate_record(
        replace(game, steps=steps, action_codec_version=SCOUTS_NO_LINE_PASS_CODEC - 1)
    )
    assert older.complete
    assert _steps(older) == list(game.steps)
    assert older.bridge_counts() == {SCOUTS_NO_LINE_PASS_BRIDGE: len(passes)}
    assert canonical_state_hash(older.state) == game.expected_state_hash

    newer = migrate_record(
        replace(game, steps=steps, action_codec_version=SCOUTS_NO_LINE_PASS_CODEC)
    )
    assert newer.divergence is not None
    assert newer.divergence.recorded_index == passes[0]


@pytest.mark.parametrize("form", ["whole", "row"])
def test_an_older_confirm_of_taking_nothing_is_the_printed_pass(form: str) -> None:
    """An older engine offered such a seat only the confirm that it takes
    nothing (``resolve_scouts_choice_without_option``); a recorded confirm
    comes back as the pass. A record holds the confirm as its step row
    (``confirm_empty`` naming the item, ``rules.effect_steps``); the bridge
    takes the whole action too."""

    game = _replay_of(ORIGINAL_SCOUTS, NO_LINE_PASS_SEED)
    states = _states(game)
    passes = _no_line_passes(game, states)
    items = {
        str(dict(states[index].decision_stack[-1].context)["item"]) for index in passes
    }
    assert items == {"desert_gift"} and len(passes) == 2
    # One of them beside a specimen return (OQ-050).
    assert any(
        action.action_id == "return_specimen"
        for index in passes
        for action in ENGINE.whole_actions(
            states[index], _owner_of(states[index].decision_stack[-1])
        )
    )
    _check_no_line_pass_bridge(game, states, passes, form)


# A random game on Uprising's board with Scouts where a revealed Covert
# Operation pick's costed line falls due that its seat cannot pay (OQ-085
# (c); user decision 2026-11-11 "새로 나온 수정 범위는 모두 권고대로ㄱㄱ").
SECRET_LINE_PASS_SEED = 35
UPRISING_SCOUTS = RulesetConfig(arrakeen_scouts=True)


@pytest.mark.parametrize("form", ["whole", "row"])
def test_an_older_confirm_of_a_secret_pick_s_line_is_its_pass(form: str) -> None:
    steps = played_steps(
        SECRET_LINE_PASS_SEED, config=UPRISING_SCOUTS, agents=("random",) * 4
    )
    state = ENGINE.reset(UPRISING_SCOUTS, SECRET_LINE_PASS_SEED)
    for step in steps:
        state = ENGINE.apply(state, step).state
    game = GameReplay(
        UPRISING_SCOUTS,
        SECRET_LINE_PASS_SEED,
        steps,
        canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )
    states = _states(game)
    passes = [
        index
        for index in _no_line_passes(game, states)
        if "only_option" in dict(states[index].decision_stack[-1].context)
    ]
    assert passes
    assert {
        dict(states[index].decision_stack[-1].context)["item"] for index in passes
    } == {"covert_operation"}
    others = [i for i in _no_line_passes(game, states) if i not in passes]
    _check_no_line_pass_bridge(game, states, sorted((*passes, *others)), form)

