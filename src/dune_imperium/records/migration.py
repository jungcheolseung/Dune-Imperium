"""Replay a game recorded by an older engine on this one.

A save records each step by meaning -- an action's id, actor and arguments,
a chance decision's id and drawn values -- not by catalog row, so a new
action codec alone never makes a record unreadable. What breaks one is a
change in the engine's *flow*: a later engine asks a question the recording
engine never asked (a pause before a reveal, OQ-103; a Conflict-end window
that now opens on public facts), so the next recorded step meets a decision
it was not made for. The play server refuses such a save outright
(``parse_save_document`` checks the versions exactly); this module serves
the uses that need only the game itself, such as reading human decisions as
training or diagnosis data (docs/human-records.md).

``migrate_record`` replays the recorded steps in order. When the engine
refuses one, the first bridge in ``BRIDGES`` that applies answers the
pending decision the way the recording engine did by not asking it -- a
pause with its one outcome, a window that engine never opened declined --
and the recorded step is tried again. A bridge never answers a decision the
recorded step itself was made for (``_made_for``), so a recorded choice that
a rule change made illegal ends the migration there as a ``Divergence``
instead of being skipped past; every step before it still stands.

Adding a bridge: when an engine change makes a recorded game stop, compare
the record with the engine's pending decision (``dune-imperium-records
check`` names both). If the new engine merely asks something the old one
answered implicitly, add a bridge gated on the codec version that changed
the flow and protect it with an old-engine record in
``tests/unit/records/data``. If a recorded choice is simply no longer legal,
the divergence is the right answer.
"""

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind

# A round's end can need a handful of bridges in a row before the next
# recorded step fits (each reward recipient's pause, every seat's
# Conflict-end window, the Round Start pause); this many means the record
# and the engine have lost each other.
MAX_BRIDGES_PER_STEP = 64

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
    """

    name: str
    answer: BridgeAnswer
    before_codec: int | None = None
    rewrites: bool = False


@dataclass(frozen=True, slots=True)
class MigratedStep:
    """One step of the migrated game, and where it came from."""

    step: ReplayStep
    # The step's index in the record; ``None`` for a bridged step.
    recorded_index: int | None
    # The bridge that answered or rewrote it; ``None`` for a recorded step
    # that applied as recorded.
    bridge: str | None = None


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
    migrated: list[MigratedStep] = []
    for index, recorded in enumerate(replay.steps):
        step, rewritten_by = recorded, None
        for _ in range(MAX_BRIDGES_PER_STEP):
            try:
                state = engine.apply(state, step).state
            except IllegalActionError as error:
                bridged = _bridge(engine, state, step, bridges)
                if bridged is None:
                    divergence = Divergence(
                        recorded_index=index,
                        step=recorded,
                        reason=str(error),
                        pending=engine.current_decision(state),
                    )
                    return MigratedRecord(replay, tuple(migrated), state, divergence)
                bridge, answer = bridged
                if bridge.rewrites:
                    step, rewritten_by = answer, bridge.name
                    continue
                state = engine.apply(state, answer).state
                migrated.append(MigratedStep(answer, None, bridge.name))
                continue
            migrated.append(MigratedStep(step, index, rewritten_by))
            break
        else:
            divergence = Divergence(
                recorded_index=index,
                step=recorded,
                reason=f"{MAX_BRIDGES_PER_STEP} bridges did not reach the step",
                pending=engine.current_decision(state),
            )
            return MigratedRecord(replay, tuple(migrated), state, divergence)
    return MigratedRecord(replay, tuple(migrated), state, None)


def walk(
    record: MigratedRecord, engine: UprisingRulesEngine | None = None
) -> Iterator[tuple[GameState, MigratedStep]]:
    """Yield the state before every migrated step, with that step."""

    engine = engine or UprisingRulesEngine()
    state = engine.reset(record.replay.ruleset, record.replay.seed)
    for migrated in record.steps:
        yield state, migrated
        state = engine.apply(state, migrated.step).state


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
        for action in engine.legal_actions(state, decision.owner)
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

    ``answers`` are the action ids that answer a ``frame`` decision; a
    recorded step of the deciding seat with one of them was made for it.
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
        if decline not in engine.legal_actions(state, decision.owner):
            return None
        return decline

    return answer


_CARD_EFFECT = "resolve_agent_card_effect"


def _named_card_effect(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Name the icon of an argument-less ``resolve_agent_card_effect``.

    Codec v137 (752c39fe, the Steam app card comparison) split some Agent
    boxes that used to resolve as one ``resolve_agent_card_effect`` (Stillsuit
    Manufacturer's water) into icons that name themselves with ``effect``.
    The recorded action is the one such icon offered now -- if exactly one
    is; with two or more the record no longer says which, and the migration
    stops there. Only this action and only an added ``effect``: elsewhere an
    absent argument is itself a choice (no ``graft``, no ``discount``).
    """

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and step.action_id == _CARD_EFFECT
        and not step.arguments
    ):
        return None
    named = [
        action
        for action in engine.legal_actions(state, decision.owner)
        if action.action_id == _CARD_EFFECT
        and tuple(key for key, _ in action.arguments) == ("effect",)
    ]
    return named[0] if len(named) == 1 else None


BRIDGES: tuple[Bridge, ...] = (
    Bridge("pause", _pause),
    # Codec v141 (e7eef001) opens the Conflict-end Intrigue window on public
    # facts, so it now asks seats an older engine skipped because they held
    # no card for it; such a seat could only decline.
    Bridge(
        "conflict_end_window",
        _decline_in(
            FrameKind.CONFLICT_END_TRIGGER,
            "decline_conflict_end_intrigue",
            frozenset({"decline_conflict_end_intrigue", "play_conflict_end_intrigue"}),
        ),
        before_codec=141,
    ),
    # Codec v139 (5654d7f8) no longer counts a pass made right after a play
    # towards closing Combat Intrigue, so it asks again where an older
    # engine had already closed the window.
    Bridge(
        "combat_intrigue_pass",
        _decline_in(
            FrameKind.COMBAT_INTRIGUE,
            "pass_combat_intrigue",
            frozenset({"pass_combat_intrigue", "play_intrigue"}),
        ),
        before_codec=139,
    ),
    Bridge(
        "agent_card_effect_named",
        _named_card_effect,
        before_codec=137,
        rewrites=True,
    ),
)
