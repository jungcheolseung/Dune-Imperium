"""Replay a game recorded by an older engine on this one.

A save records each step by meaning -- an action's id, actor and arguments,
a chance decision's id and drawn values -- not by catalog row, so a new
action codec alone never makes a record unreadable. What breaks one is a
change in the engine's *flow*: a later engine asks a question the recording
engine never asked (a pause before a reveal, OQ-103; a window that now opens
on public facts), so the next recorded step meets a decision it was not
made for. The play server refuses such a save outright
(``parse_save_document`` checks the versions exactly); this module serves
the uses that need only the game itself: reading human decisions as
training or diagnosis data, the human problem suites, the record corpus
check, and converting kept records to the current codec
(``records.convert``, docs/human-records.md).

``migrate_record`` replays the recorded steps in order. When the engine
refuses one, the first bridge in ``BRIDGES`` that applies answers the
pending decision the way the recording engine did by not asking it -- a
pause with its one outcome, a window that engine never opened declined --
and the recorded step is tried again; a ``rewrites`` bridge puts the
recorded step in this engine's terms instead. Where this engine splits off
part of what one recorded step did, a ``follows`` bridge adds that part
right after the recorded step, at the moment the recording engine did it;
several such parts can follow one step, so the ``follows`` bridges are asked
again until none answers. A bridge never answers a decision the recorded
step itself was made for (``_made_for``), so a recorded choice that a rule
change made illegal ends the migration there as a ``Divergence`` instead of
being skipped past; every step before it still stands.

Keep at most one bridge besides ``pause`` (user decision 2026-10-28): every
kept record is converted to the current codec at each codec bump
(``records.convert``), so a bridge only needs to reach back one codec, from
the previous version to the current one. Adding it: when an engine change
makes a recorded game stop, compare the record with the engine's pending
decision (``dune-imperium-records check`` names both). If the new engine
merely asks something the old one answered implicitly, add a bridge gated
on the new codec (``before_codec``), built like ``_decline_in`` and guarded
by ``_made_for``, protect it with a record of the previous engine, convert
every kept record with it, and remove it at the following bump. If a
recorded choice is simply no longer legal, the divergence is the right
answer. The bridges of codecs v135-v155 were removed when every kept record
was converted to v156 (2026-10-29); docs/human-records.md section 8 says
where their history is.
"""

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from dune_imperium.agents.agent_turn_steps import apply_whole, steps_after
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step, presents_steps
from dune_imperium.rules.frames import FrameKind

# A round's end can need a handful of bridges in a row before the next
# recorded step fits (each reward recipient's pause, the Round Start
# pause); this many means the record and the engine have lost each other.
MAX_BRIDGES_PER_STEP = 64
# What ``follows`` bridges add after one recorded step: a few split-off
# parts at most. More than this means two bridges keep answering each other.
MAX_FOLLOWS_PER_STEP = 32

type BridgeAnswer = Callable[
    [UprisingRulesEngine, GameState, Decision, ReplayStep], ReplayStep | None
]


@dataclass(frozen=True, slots=True)
class Bridge:
    """One way an older record meets a decision this engine adds.

    ``answer`` returns the step to apply, or ``None`` when the bridge does
    not apply. With ``rewrites`` the answer is the recorded step itself in
    this engine's terms and takes its place; otherwise it is a step the
    recording engine never asked for, applied before the recorded one.
    ``before_codec`` limits a bridge to records stamped with an older
    action codec; ``None`` applies it to every record.

    With ``follows`` the bridge runs after every recorded step that applied
    (never on a refusal), with that step as ``step`` and the decision the
    engine waits for after it: it adds a part of the recorded step that this
    engine splits off into a step of its own, at the moment the recording
    engine did it. Waiting for a refusal would be too late there: the
    recorded steps in between already saw that part done. After each answer
    the ``follows`` bridges are asked again from the first (``_follow``), so
    a bridge must return ``None`` once its part is done, and ``BRIDGES``
    lists them in the order the recording engine did those parts.
    """

    name: str
    answer: BridgeAnswer
    before_codec: int | None = None
    rewrites: bool = False
    follows: bool = False


@dataclass(frozen=True, slots=True)
class MigratedStep:
    """One step of the migrated game, and where it came from."""

    step: ReplayStep
    # The step's index in the record; ``None`` for a bridged step.
    recorded_index: int | None
    # The bridge that answered or rewrote it; ``None`` for a recorded step
    # that applied as recorded.
    bridge: str | None = None


@dataclass(slots=True)
class _Taken:
    """The migrated steps so far, each with the state it was taken from.

    ``migrate_record`` hands the states to its record, so ``walk`` yields
    them instead of replaying the whole record a second time (2026-10-21:
    the second replay was about two fifths of a corpus check)."""

    steps: list[MigratedStep] = field(default_factory=list)
    states: list[GameState] = field(default_factory=list)

    def add(self, step: MigratedStep, before: GameState) -> None:
        self.steps.append(step)
        self.states.append(before)

    def __len__(self) -> int:
        return len(self.steps)

    def cut(self, mark: int) -> None:
        del self.steps[mark:]
        del self.states[mark:]


def _apply_answer(
    engine: UprisingRulesEngine,
    state: GameState,
    answer: ReplayStep,
    bridge: str,
    migrated: _Taken,
) -> GameState:
    """Apply a bridge's answer, recorded as ``bridge``'s steps.

    A bridge may answer with a whole action where this engine offers its
    effect first (``rules.effect_steps``); it is taken as the steps that
    stand for it, each recorded under the bridge, so a converted record
    holds only steps this engine offers."""

    while (
        isinstance(answer, DomainAction)
        and presents_steps(state)
        and answer not in engine.legal_actions(state, answer.actor)
        and answer in engine.whole_actions(state, answer.actor)
    ):
        left = steps_after(state, answer)
        row = first_step(state, answer)
        before = state
        state = engine.apply(state, row).state
        migrated.add(MigratedStep(row, None, bridge), before)
        if left == 0:
            return state
    before = state
    state = engine.apply(state, answer).state
    migrated.add(MigratedStep(answer, None, bridge), before)
    return state


@dataclass(frozen=True, slots=True)
class Divergence:
    """The first recorded step this engine refused and no bridge reached."""

    recorded_index: int
    step: ReplayStep
    reason: str
    # The decision the engine was waiting for instead.
    pending: Decision | None


@dataclass(frozen=True, slots=True)
class MigratedRecord:
    """A record replayed on this engine, as far as it goes."""

    replay: GameReplay
    steps: tuple[MigratedStep, ...]
    state: GameState
    divergence: Divergence | None
    # The steps tuple and the state each of them was taken from, as
    # ``migrate_record`` replayed them (``_Taken``): ``walk`` yields these
    # while ``steps`` is still that very tuple, and replays the record when
    # a migration module rebuilt the record with other steps. Left out of
    # comparisons: the same steps from the same reset give the same states.
    walked: tuple[tuple[MigratedStep, ...], tuple[GameState, ...]] | None = field(
        default=None, compare=False, repr=False
    )

    @property
    def complete(self) -> bool:
        """Whether every recorded step applied."""

        return self.divergence is None

    @property
    def exact(self) -> bool:
        """Whether the record replays on this engine as it was recorded."""

        return (
            self.complete
            and not self.bridge_counts()
            and canonical_state_hash(self.state) == self.replay.expected_state_hash
        )

    def bridge_counts(self) -> Counter[str]:
        """How many steps each bridge answered or rewrote."""

        return Counter(step.bridge for step in self.steps if step.bridge is not None)


def migrate_record(
    replay: GameReplay, engine: UprisingRulesEngine | None = None
) -> MigratedRecord:
    """Replay ``replay`` on this engine through ``BRIDGES``."""

    engine = engine or UprisingRulesEngine()
    bridges = tuple(
        bridge
        for bridge in BRIDGES
        if bridge.before_codec is None
        or replay.action_codec_version < bridge.before_codec
    )
    state = engine.reset(replay.ruleset, replay.seed)
    migrated = _Taken()

    def ended(divergence: Divergence | None, at: GameState) -> MigratedRecord:
        steps = tuple(migrated.steps)
        return MigratedRecord(
            replay, steps, at, divergence, walked=(steps, tuple(migrated.states))
        )

    for index, recorded in enumerate(replay.steps):
        step, rewritten_by = recorded, None
        for _ in range(MAX_BRIDGES_PER_STEP):
            try:
                after = engine.apply(state, step).state
            except IllegalActionError as error:
                bridged = _bridge(engine, state, step, bridges)
                if bridged is None:
                    divergence = Divergence(
                        recorded_index=index,
                        step=recorded,
                        reason=str(error),
                        pending=engine.current_decision(state),
                    )
                    return ended(divergence, state)
                bridge, answer = bridged
                if bridge.rewrites:
                    step, rewritten_by = answer, bridge.name
                    continue
                state = _apply_answer(engine, state, answer, bridge.name, migrated)
                continue
            before, mark = state, len(migrated)
            migrated.add(MigratedStep(step, index, rewritten_by), before)
            followed = _follow(engine, after, step, bridges, migrated)
            if followed is None:
                migrated.cut(mark)
                divergence = Divergence(
                    recorded_index=index,
                    step=recorded,
                    reason=(
                        f"{MAX_FOLLOWS_PER_STEP} follows bridges after the step "
                        "did not settle"
                    ),
                    pending=engine.current_decision(before),
                )
                return ended(divergence, before)
            state = followed
            break
        else:
            divergence = Divergence(
                recorded_index=index,
                step=recorded,
                reason=f"{MAX_BRIDGES_PER_STEP} bridges did not reach the step",
                pending=engine.current_decision(state),
            )
            return ended(divergence, state)
    return ended(None, state)


def walk(
    record: MigratedRecord, engine: UprisingRulesEngine | None = None
) -> Iterator[tuple[GameState, MigratedStep]]:
    """Yield the state before every migrated step, with that step.

    The states ``migrate_record`` took the steps from, while the record
    still holds its own steps (``MigratedRecord.walked``); otherwise the
    record replayed from its reset (``replayed``)."""

    walked = record.walked
    if walked is not None and walked[0] is record.steps:
        yield from zip(walked[1], record.steps, strict=True)
        return
    yield from replayed(record, engine)


def replayed(
    record: MigratedRecord, engine: UprisingRulesEngine | None = None
) -> Iterator[tuple[GameState, MigratedStep]]:
    """``walk`` by replaying the record's steps from its reset."""

    engine = engine or UprisingRulesEngine()
    state = engine.reset(record.replay.ruleset, record.replay.seed)
    for migrated in record.steps:
        yield state, migrated
        state = apply_whole(engine, state, migrated.step).state


def rewrite_step(
    engine: UprisingRulesEngine,
    state: GameState,
    step: ReplayStep,
    codec: int,
) -> ReplayStep | None:
    """``step`` in this engine's terms by a rewrite bridge open to ``codec``.

    For a move that was never recorded but was judged in an older engine's
    terms (``records.problems``: the play network's candidate); ``None``
    when no rewrite bridge applies to it at ``state``.
    """

    decision = engine.current_decision(state)
    if decision is None:
        return None
    for bridge in BRIDGES:
        if bridge.rewrites and (
            bridge.before_codec is None or codec < bridge.before_codec
        ):
            answer = bridge.answer(engine, state, decision, step)
            if answer is not None:
                return answer
    return None


def _bridge(
    engine: UprisingRulesEngine,
    state: GameState,
    step: ReplayStep,
    bridges: tuple[Bridge, ...],
) -> tuple[Bridge, ReplayStep] | None:
    decision = engine.current_decision(state)
    if decision is None:
        return None
    for bridge in bridges:
        if bridge.follows:
            continue
        answer = bridge.answer(engine, state, decision, step)
        if answer is not None:
            return bridge, answer
    return None


def _follow(
    engine: UprisingRulesEngine,
    state: GameState,
    step: ReplayStep,
    bridges: tuple[Bridge, ...],
    migrated: _Taken,
) -> GameState | None:
    """Apply what the ``follows`` bridges add right after the applied ``step``.

    A fixpoint: each pass asks the ``follows`` bridges in ``BRIDGES`` order
    and applies the first answer, and the passes repeat until one answers
    nothing. One recorded step can leave several split-off parts, some
    behind another; starting each pass from the first bridge keeps the
    recording engine's order. ``None`` when ``MAX_FOLLOWS_PER_STEP`` answers
    did not settle.
    """

    follows = tuple(bridge for bridge in bridges if bridge.follows)
    firings = 0
    while (found := _next_follow(engine, state, step, follows)) is not None:
        if firings == MAX_FOLLOWS_PER_STEP:
            return None
        bridge, answer = found
        state = _apply_answer(engine, state, answer, bridge.name, migrated)
        firings += 1
    return state


def _next_follow(
    engine: UprisingRulesEngine,
    state: GameState,
    step: ReplayStep,
    follows: tuple[Bridge, ...],
) -> tuple[Bridge, ReplayStep] | None:
    """The first ``follows`` bridge that answers now, with its answer."""

    decision = engine.current_decision(state)
    if decision is None:
        return None
    for bridge in follows:
        answer = bridge.answer(engine, state, decision, step)
        if answer is not None:
            return bridge, answer
    return None


def _made_for(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
    answers: frozenset[str],
) -> bool:
    """Whether ``step`` answers ``decision`` (legally or not).

    A recorded action of the deciding seat answered this decision when its
    action id is one the decision's frame answers with (``answers``) or one
    the decision offers now. If the engine refuses it, a rule changed -- it
    may even have taken away every action of that id -- and no bridge may
    answer the decision in its place.
    """

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
    ):
        return False
    return step.action_id in answers or any(
        action.action_id == step.action_id
        for action in engine.whole_actions(state, decision.owner)
    )


def _pause(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Answer a pause (rules/pauses.py) with its one outcome.

    A pause stops the engine at a point fixed by public facts and holds
    back a step that then runs as it did, so its outcome carries no choice
    and no draw; any record may meet one an older engine did not have.
    """

    del engine, state, step
    if isinstance(decision, ChanceDecision) and is_fixed_outcome(decision):
        return ChanceOutcome(decision.decision_id, decision.options)
    return None


def _decline_in(
    frame: FrameKind, decline_id: str, answers: frozenset[str]
) -> BridgeAnswer:
    """Answer an unrecorded ``frame`` decision with ``decline_id``.

    The shape most bridges have had (a window an older engine never opened
    for a seat that could only decline it). ``answers`` are the action ids
    that answer a ``frame`` decision; a recorded step of the deciding seat
    with one of them was made for it (``_made_for``).
    """

    def answer(
        engine: UprisingRulesEngine,
        state: GameState,
        decision: Decision,
        step: ReplayStep,
    ) -> ReplayStep | None:
        if (
            not isinstance(decision, PlayerDecision)
            or state.decision_stack[-1].kind != frame
            or _made_for(engine, state, decision, step, answers)
        ):
            return None
        decline = DomainAction(action_id=decline_id, actor=decision.owner)
        if decline not in engine.whole_actions(state, decision.owner):
            return None
        return decline

    return answer


# ``pause`` answers every record; a bridge from the previous codec, when the
# current one changed the engine's flow, goes after it (module docstring).
BRIDGES: tuple[Bridge, ...] = (Bridge("pause", _pause),)
