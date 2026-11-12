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
from typing import Final

from dune_imperium.agents.agent_turn_steps import apply_whole, steps_after
from dune_imperium.content.registry.card_abilities import card_agent_box
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import (
    first_step,
    path_of,
    presents_steps,
    printed_from_state,
    without_pick,
)
from dune_imperium.rules.effects import (
    active_agent_card,
    current_agent_effect_context,
    pending_agent_icons,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import (
    box_is_pending,
    is_grafted_turn,
    state_with_active_box,
    tagged,
)
from dune_imperium.rules.leader_abilities import (
    SIGNET_NO_OPTION,
    legal_leader_signet_actions,
)
from dune_imperium.rules.scouts_effects import SCOUTS_COLLECT, SCOUTS_NO_OPTION

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
    # A recorded step this engine has no counterpart for, consumed with no
    # move: the bridge answers with any step when it applies, and the step
    # is listed in ``MigratedRecord.dropped`` under the bridge's name.
    drops: bool = False
    # For an older form only the record as a whole shows (a step this engine
    # always records, missing): ``older(replay)`` says whether the record is
    # of that form; the bridge is left out of a record it says no to, as
    # ``before_codec`` leaves it out of a newer stamp.
    older: Callable[[GameReplay], bool] | None = None


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
    # The recorded steps a ``drops`` bridge consumed with no move, as
    # (recorded index, bridge name) (``records.convert.dropped_steps``).
    dropped: tuple[tuple[int, str], ...] = ()

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
        """How many steps each bridge answered, rewrote or dropped."""

        counts = Counter(
            step.bridge for step in self.steps if step.bridge is not None
        )
        counts.update(name for _, name in self.dropped)
        return counts


def migrate_record(
    replay: GameReplay, engine: UprisingRulesEngine | None = None
) -> MigratedRecord:
    """Replay ``replay`` on this engine through ``BRIDGES``."""

    engine = engine or UprisingRulesEngine()
    bridges = tuple(
        bridge
        for bridge in BRIDGES
        if (
            bridge.before_codec is None
            or replay.action_codec_version < bridge.before_codec
        )
        and (bridge.older is None or bridge.older(replay))
    )
    state = engine.reset(replay.ruleset, replay.seed)
    migrated = _Taken()
    dropped: list[tuple[int, str]] = []

    def ended(divergence: Divergence | None, at: GameState) -> MigratedRecord:
        steps = tuple(migrated.steps)
        return MigratedRecord(
            replay,
            steps,
            at,
            divergence,
            walked=(steps, tuple(migrated.states)),
            dropped=tuple(dropped),
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
                if bridge.drops:
                    dropped.append((index, bridge.name))
                    break
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


# The codec at which every Arrakeen Scouts payout waits for its seat's
# ``scouts_collect_reward`` click (user decisions 2026-11-01, OQ-164 (a) and
# (b): Tap into Spice Reserves and the five mission payouts -- CHOAM Escort,
# Tleilaxu Offering, Valued Informants, Sponsored Research, Back Room Deal --
# each in a window that opens at once). An older engine paid them unasked,
# so its records never click: the window, its one action, is answered
# before the recorded step it holds back, which gives the older engine's
# state, since the window lets nothing else happen first. The same bridge
# answers the click on a line received later (codec v161), which every
# record kept since that bump already holds. The codec is raised in
# the merge commit; this is that version.
SCOUTS_PAYOUT_CODEC: Final = 162
SCOUTS_PAYOUT_BRIDGE: Final = "scouts_payout"

# The codec at which an immediate triggered draw (OQ-106) is offered by its
# step on every frame (``effect_steps.presents_steps``, 2026-11-07). An older
# engine offered it as its whole action, ``draw_owed_intrigue`` or
# ``draw_owed_card``, on a frame that does not present steps: Rise of Ix's
# Shipping rewards window and the Unload hold under it, where the window's
# Influence reaches a Bene Gesserit bonus. The bridge rewrites such a recorded
# whole as its one step row, the same press. The codec is raised in the merge
# commit; this is that version.
OWED_DRAW_ROW_CODEC: Final = 166
OWED_DRAW_ROW_BRIDGE: Final = "owed_draw_row"
_OWED_DRAW_IDS: Final = frozenset({"draw_owed_intrigue", "draw_owed_card"})


def _owed_draw_row(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """A recorded owed-draw whole in this engine's terms: its step row,
    when that row is what this engine offers for it (``OWED_DRAW_ROW_CODEC``)."""

    del decision
    if (
        not isinstance(step, DomainAction)
        or step.action_id not in _OWED_DRAW_IDS
        or not presents_steps(state)
        or step not in engine.whole_actions(state, step.actor)
        or steps_after(state, step) != 0
    ):
        return None
    row = first_step(state, step)
    return row if row in engine.legal_actions(state, step.actor) else None


# The codec at which Slig Farmer's two printed effects are two steps
# (2026-11-08, OQ-027's card Agent box extension 4): "Gain 1 solari per Agent
# icon on the other grafted card" an icon of its own
# (``resolve_agent_card_effect(effect=solari)``) and "You may pay 5 solari ->
# Advance the Tleilaxu track" another, optional, whose payment row names its
# icon (``pay(icon=tleilaxu)``). An older engine offered two alternatives:
# ``resolve`` -- the Solari, the payment declined -- and ``pay`` -- the
# Solari, then the payment. The bridges put such a recorded step in this
# engine's terms, in the older engine's order: ``resolve`` becomes the Solari
# line (its arrow left to lapse at the turn's end, as that engine dropped it);
# ``pay`` becomes the Solari line, answered before it, and then the payment
# row. Every older ``pay`` is refused here (its row names no icon), so a
# record of this engine, whose payment may come before its line, never meets
# them. The codec is raised in the merge commit; this is that version.
SLIG_FARMER_CODEC: Final = 168
SLIG_FARMER_LINE_BRIDGE: Final = "slig_farmer_line"
SLIG_FARMER_PAY_LINE_BRIDGE: Final = "slig_farmer_pay_line"
SLIG_FARMER_PAY_BRIDGE: Final = "slig_farmer_pay"
_SLIG_FARMER_BOX: Final = (
    "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu"
)
_SLIG_FARMER_LINE: Final = "solari"
_SLIG_FARMER_ARROW: Final = "tleilaxu"
_SLIG_FARMER_PAY_ID: Final = "pay_agent_card_five_solari_for_tleilaxu"
# The older engine's two answers: the step's verb and its whole action.
_OLDER_SLIG_FARMER_STEPS: Final = (
    ("resolve", "resolve_agent_card_effect"),
    ("pay", _SLIG_FARMER_PAY_ID),
)


def _slig_farmer_icons(state: GameState, box: int) -> tuple[str, ...] | None:
    """The waiting icons of the deciding Agent turn's box ``box`` when it is
    a Slig Farmer box (a Ghola's copy included); None otherwise."""

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if (box == 1 and not is_grafted_turn(context)) or not box_is_pending(
        context, box
    ):
        return None
    _, active = current_agent_effect_context(state_with_active_box(state, box))
    if card_agent_box(active_agent_card(active)) != _SLIG_FARMER_BOX:
        return None
    return pending_agent_icons(active)


def _older_slig_farmer_step(
    state: GameState, step: ReplayStep
) -> tuple[str, int, tuple[str, ...]] | None:
    """An older engine's answer to a Slig Farmer box: ``resolve`` or
    ``pay``, its box and the box's waiting icons here; None for any other
    step. Its step row named the box's card (``printed``) and no icon."""

    if not isinstance(step, DomainAction):
        return None
    arguments = dict(step.arguments)
    box = arguments.pop("box", 0)
    if box not in (0, 1) or isinstance(box, bool):
        return None
    for verb, whole_id in _OLDER_SLIG_FARMER_STEPS:
        whole = tagged(DomainAction(whole_id, step.actor), box)
        if step != whole and step.action_id != verb:
            continue
        icons = _slig_farmer_icons(state, box)
        if icons is None:
            return None
        if step == whole:
            return verb, box, icons
        try:
            printed = printed_from_state(state, whole)
        except ValueError:
            return None
        if printed is None:
            return None
        source, entity = printed
        if arguments == {"printed": entity, "source": source.value}:
            return verb, box, icons
        return None
    return None


def _slig_farmer_row(
    engine: UprisingRulesEngine, state: GameState, whole: DomainAction
) -> ReplayStep | None:
    """The row this engine offers now for ``whole``, if it offers one."""

    try:
        row = first_step(state, whole) if presents_steps(state) else whole
    except ValueError:
        return None
    return row if row in engine.legal_actions(state, whole.actor) else None


def _slig_farmer_line_row(
    engine: UprisingRulesEngine, state: GameState, actor: int, box: int
) -> ReplayStep | None:
    line = DomainAction(
        "resolve_agent_card_effect", actor, (("effect", _SLIG_FARMER_LINE),)
    )
    return _slig_farmer_row(engine, state, tagged(line, box))


def _slig_farmer_line(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """An older ``resolve`` of a Slig Farmer box as its Solari line's row."""

    del decision
    older = _older_slig_farmer_step(state, step)
    if older is None or older[0] != "resolve" or _SLIG_FARMER_LINE not in older[2]:
        return None
    assert isinstance(step, DomainAction)
    return _slig_farmer_line_row(engine, state, step.actor, older[1])


def _slig_farmer_pay_line(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Before an older ``pay`` of a Slig Farmer box, its Solari line: the
    older engine paid the line first, then the arrow out of it."""

    del decision
    older = _older_slig_farmer_step(state, step)
    if older is None or older[0] != "pay" or _SLIG_FARMER_LINE not in older[2]:
        return None
    assert isinstance(step, DomainAction)
    return _slig_farmer_line_row(engine, state, step.actor, older[1])


def _slig_farmer_pay(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """An older ``pay`` of a Slig Farmer box, its line taken, as its arrow's
    payment row."""

    del decision
    older = _older_slig_farmer_step(state, step)
    if (
        older is None
        or older[0] != "pay"
        or _SLIG_FARMER_LINE in older[2]
        or _SLIG_FARMER_ARROW not in older[2]
    ):
        return None
    assert isinstance(step, DomainAction)
    pay = DomainAction(_SLIG_FARMER_PAY_ID, step.actor)
    return _slig_farmer_row(engine, state, tagged(pay, older[1]))


# The printed-effects audit (user 2026-11-09). Forbidden Weapons' optional
# Shield Wall icon ("Shield Wall detonation icon으로 Shield Wall을 제거하는
# 것은 선택 사항이며 ... [Main p. 10] [FAQ p. 4]", docs/rules/player-turns.md)
# is in its owner's own turn its detonation row alone, with no refusal; left
# unused, the turn-end press lapses it (OQ-095 (2), (7)). An older engine also
# offered the wall's keeping there, as a row the owner had to press; such a
# recorded keep has no counterpart and is dropped (the turn's end then lapses
# the icon, leaving the wall as the keep did). Combat's acquire frame still
# offers the keep, so a keep recorded there applies as it was. Spice Agony
# ("1 Spice → Intrigue 1 draw, 그리고 supply의 troop 1개를 board의 Bene
# Gesserit 구역으로(이제 memory)", docs/implementation-audits/leaders.md) pays
# its spice as one step and leaves its two rewards as steps of their own
# (OQ-106); an older engine did both inside the payment, the memory first,
# then the draw. The box then offers only those two rows (OQ-167), so an
# older record's next step is refused and the bridge answers them first, in
# that order (a row the lock lets through, such as an owed Tech icon recorded
# right after the payment, still applies as recorded before them). Final
# Delivery (OQ-148 (가)) pays its 7 Solari as one step and leaves its
# Influence, troop and spice as steps; an older engine chose the Faction in
# the payment's own row (``gain_influence``, then its Faction) and gave all
# three at once: ``final_delivery_payment`` pays before that recorded row,
# which then answers the Influence, and ``final_delivery_rewards`` gives the
# spice and the troop (and confirms an Influence lost at the top) where the
# record goes on. Personal Training's last space (OQ-027) leaves its troop
# as a step beside its Spy; an older engine recruited it on arrival, so
# ``feyd_last_troop`` gives it right after the recorded arrival. Throne Room
# Politics (OQ-027 card Agent box extension 3) offers its troop and its
# trash icon from the placement; an older engine's ``resolve`` was the troop,
# which ``throne_room_troop`` rewrites to the troops icon's row (its trash
# rows read the same on both engines). Control the Spice (OQ-148) arms its
# troop at the payment where an older engine recruited it;
# ``control_the_spice_troop`` gives it right after the recorded payment.
# Both troops are ``follows`` bridges: the steps an older record goes on
# with (the Spy, the card's trash) stay legal here, so a refusal would come
# only later, and every position in between would hold the troop in the
# supply where the recording engine had it in the garrison (two human
# problems judged right after Control the Spice's payment no longer matched,
# rules-audit-s3 gate 2026-11-09). The codec is raised in the merge
# commit; this is that version (codec v169 went to the play-labels merge
# first, 2026-11-09).
RULES_AUDIT_CODEC: Final = 170
FORBIDDEN_WEAPONS_KEEP_BRIDGE: Final = "forbidden_weapons_keep"
SPICE_AGONY_REWARDS_BRIDGE: Final = "spice_agony_rewards"
FINAL_DELIVERY_PAYMENT_BRIDGE: Final = "final_delivery_payment"
FINAL_DELIVERY_REWARDS_BRIDGE: Final = "final_delivery_rewards"
FEYD_LAST_TROOP_BRIDGE: Final = "feyd_last_troop"
THRONE_ROOM_TROOP_BRIDGE: Final = "throne_room_troop"
CONTROL_THE_SPICE_TROOP_BRIDGE: Final = "control_the_spice_troop"
_THRONE_ROOM_BOX: Final = "recruit_one_and_may_trash"
_CONTROL_THE_SPICE_BOX: Final = "may_pay_spice_to_trash_and_recruit"
_SPICE_AGONY_ORDER: Final = ("memory", "intrigue")
FINAL_DELIVERY_LEADER: Final = "princess_yuna_moritani"
# The older engine's order: spice and troop with the payment, then the
# Influence; one lost with every Faction at the top is confirmed here.
_FINAL_DELIVERY_ORDER: Final = ("spice", "troops", "confirm")


def _forbidden_weapons_keep(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """An older in-turn keep of a Tech tile's Shield Wall icon, to drop."""

    from dune_imperium.rules.tech import pending_tech_acquire_effects

    del engine
    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
    ):
        return None
    arguments = dict(step.arguments)
    if arguments.get("destroy_shield_wall") is not None:
        return None
    if step.action_id == "destroy_shield_wall":
        if arguments.get("icon") != "shield_wall" or arguments.get("source") != "tech":
            return None
        tech_id = arguments.get("printed")
    elif step.action_id == "resolve_tech_acquire_effect":
        if arguments.get("effect") != "shield_wall":
            return None
        tech_id = arguments.get("tech_id")
    else:
        return None
    frame = state.decision_stack[-1] if state.decision_stack else None
    if frame is None or frame.kind not in (
        FrameKind.TURN,
        FrameKind.AGENT_EFFECTS,
        FrameKind.REVEAL,
    ):
        return None
    if f"{tech_id}:shield_wall" not in pending_tech_acquire_effects(frame):
        return None
    return step


def _armed_signet_reward(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    leader_id: str,
    order: tuple[str, ...],
) -> ReplayStep | None:
    """The first of ``order``'s Signet rewards the deciding seat owes now:
    a ``resolve_agent_card_effect`` icon, or ``SIGNET_NO_OPTION`` (the key
    ``"confirm"``) for an Influence lost with every Faction at the top."""

    if not isinstance(decision, PlayerDecision):
        return None
    owner = decision.owner
    if state.players[owner].leader_id != leader_id:
        return None
    armed = legal_leader_signet_actions(state, owner)
    offered = engine.whole_actions(state, owner)
    for key in order:
        reward = (
            DomainAction(SIGNET_NO_OPTION, owner)
            if key == "confirm"
            else DomainAction(
                "resolve_agent_card_effect", owner, (("effect", key),)
            )
        )
        if reward not in armed:
            continue
        for box in (0, 1):
            if tagged(reward, box) in offered:
                return tagged(reward, box)
    return None


def _spice_agony_rewards(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Spice Agony's memory, then its draw, right after an older payment.

    An older engine did both inside the payment, the memory first. A
    ``follows`` bridge gives them at that moment, before the record goes
    on: OQ-167 lets an owed effect through the part-way box, so a refusal
    would come too late when the record's next step is such an effect (a
    Tech tile's troop taking the supply's last troop before the memory, as
    the older engine never let it; Codex review 2026-11-09). A record of
    this engine has its memory steps (``_records_no_memory``) and never
    meets this bridge, whatever its codec stamp."""

    del step
    return _armed_signet_reward(
        engine, state, decision, "lady_jessica", _SPICE_AGONY_ORDER
    )


def _records_no_memory(replay: GameReplay) -> bool:
    """Whether ``replay`` takes no Spice Agony memory as a step of its own,
    which this engine always records after the payment (the ``memory``
    icon is Spice Agony's alone)."""

    return not any(
        isinstance(step, DomainAction)
        and step.action_id == "take"
        and dict(step.arguments).get("icon") == "memory"
        for step in replay.steps
    )


def _final_delivery_payment(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Before an older Final Delivery Influence row, its 7 Solari, in the
    box that row names: with a Signet Ring grafted to Ghola both boxes offer
    the payment, and the row's ``box`` (none for box 0) says which one the
    older record played (Codex review 2026-11-09)."""

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and state.players[decision.owner].leader_id == FINAL_DELIVERY_LEADER
    ):
        return None
    arguments = dict(step.arguments)
    box = arguments.pop("box", None)
    older = step.action_id == "choose_leader_signet_influence" or (
        step.action_id == "gain_influence"
        and arguments == {"printed": FINAL_DELIVERY_LEADER, "source": "leader"}
    )
    if not older:
        return None
    if box is None:
        box = 0  # box 0's rows carry no ``box`` (graft_boxes.tagged)
    if not isinstance(box, int):
        return None
    pay = tagged(DomainAction("pay_leader_signet_solari", decision.owner), box)
    return pay if pay in engine.whole_actions(state, decision.owner) else None


def _final_delivery_rewards(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Final Delivery's spice, troop and lost Influence, where an older
    record goes on after its payment (that engine's order)."""

    del step
    return _armed_signet_reward(
        engine, state, decision, FINAL_DELIVERY_LEADER, _FINAL_DELIVERY_ORDER
    )


def _feyd_last_troop(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Personal Training's last-space troop, right after an older arrival
    (that engine recruited it on arrival). A record of this engine records
    the troop in the arrival's turn (``_records_no_feyd_troop``)."""

    del step
    return _armed_signet_reward(
        engine, state, decision, "feyd_rautha_harkonnen", ("troops",)
    )


_TURN_ENDS: Final = frozenset({"finish_agent_turn", "finish_reveal"})


def _is_troop_row(step: ReplayStep, printed: frozenset[str]) -> bool:
    return (
        isinstance(step, DomainAction)
        and step.action_id == "recruit"
        and dict(step.arguments).get("icon") == "troops"
        and dict(step.arguments).get("printed") in printed
    )


def _records_no_feyd_troop(replay: GameReplay) -> bool:
    """Whether no Personal Training last-space arrival in ``replay`` is
    followed, in its own turn, by its troop as a step of its own, which this
    engine always records there: Feyd's row, or a Ghola copy's (``ghola``,
    which other copied Signet rewards also print, hence the turn)."""

    arrived: int | None = None
    for step in replay.steps:
        if not isinstance(step, DomainAction):
            continue
        if (
            step.action_id == "choose_track_space"
            and dict(step.arguments).get("space_id") == "final"
        ):
            arrived = step.actor
        elif arrived == step.actor and step.action_id in _TURN_ENDS:
            arrived = None
        elif arrived == step.actor and _is_troop_row(
            step, frozenset({"feyd_rautha_harkonnen", "ghola"})
        ):
            return False
    return True


def _box_waits_on(state: GameState, box: int, effect: str, icon: str) -> bool:
    """Whether the deciding Agent turn's box ``box`` is ``effect``'s (a Ghola's
    copy included) with ``icon`` still waiting."""

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if (box == 1 and not is_grafted_turn(context)) or not box_is_pending(
        context, box
    ):
        return False
    _, active = current_agent_effect_context(state_with_active_box(state, box))
    return (
        card_agent_box(active_agent_card(active)) == effect
        and icon in pending_agent_icons(active)
    )


def _troops_row(
    engine: UprisingRulesEngine, state: GameState, actor: int, box: int
) -> ReplayStep | None:
    troops = DomainAction(
        "resolve_agent_card_effect", actor, (("effect", "troops"),)
    )
    return _slig_farmer_row(engine, state, tagged(troops, box))


def _throne_room_troop(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """An older ``resolve`` of a Throne Room Politics box as its troops
    icon's row."""

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and step.action_id in ("resolve", "resolve_agent_card_effect")
    ):
        return None
    arguments = dict(step.arguments)
    box = arguments.pop("box", 0)
    if not isinstance(box, int) or isinstance(box, bool) or "effect" in arguments:
        return None
    if step.action_id == "resolve" and (
        arguments.get("source") != "agent_card" or "icon" in arguments
    ):
        return None
    if not _box_waits_on(state, box, _THRONE_ROOM_BOX, "troops"):
        return None
    return _troops_row(engine, state, step.actor, box)


def _control_the_spice_troop(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Control the Spice's troop, right after an older payment (that engine
    recruited it with the payment). A record of this engine records the
    troop as a step (``_records_no_control_the_spice_troop``)."""

    del step
    if not isinstance(decision, PlayerDecision):
        return None
    for box in (0, 1):
        if _box_waits_on(state, box, _CONTROL_THE_SPICE_BOX, "troops"):
            return _troops_row(engine, state, decision.owner, box)
    return None


def _records_no_control_the_spice_troop(replay: GameReplay) -> bool:
    """Whether ``replay`` recruits no Control the Spice troop as a step of
    its own, which this engine always records after the payment (a card's
    box keeps its own ``printed``, a graft's too)."""

    return not any(
        _is_troop_row(step, frozenset({"control_the_spice"}))
        for step in replay.steps
    )


# The codec at which a seat with no Arrakeen Scouts line it can take, at a
# choice with a pass (an event's "or Pass", a sale, Rebuild Infrastructure, a
# revealed secret pick's costed line), answers with that pass (user decisions
# 2026-11-11 "(가)" and "새로 나온 수정 범위는 모두 권고대로ㄱㄱ", OQ-071;
# hidden-information sweep finding 1, docs/reviews/2026-11-hidden-info-sweep.md).
# An older engine
# offered such a seat only ``resolve_scouts_choice_without_option``; the
# bridge rewrites that recorded confirm as the pass, the same press with the
# same outcome (the seat takes nothing), where the pass is offered and no
# line is. Only the step's event changes kind (``scouts_choice_passed``
# instead of ``scouts_choice_skipped``). The codec is raised in the
# merge commit; this is that version.
SCOUTS_NO_LINE_PASS_CODEC: Final = 172
SCOUTS_NO_LINE_PASS_BRIDGE: Final = "scouts_no_line_pass"


def _scouts_no_line_pass(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """A recorded ``SCOUTS_NO_OPTION`` (or its step row) as this engine's
    pass, where the seat's Scouts choice offers the pass and no line
    (``SCOUTS_NO_LINE_PASS_CODEC``); a specimen return may stand beside it
    (OQ-050)."""

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    ):
        return None
    # The confirm as a whole action, or as the step row a save records for it
    # (``rules.effect_steps``: ``confirm_empty`` naming the item).
    confirm = DomainAction(action_id=SCOUTS_NO_OPTION, actor=decision.owner)
    if step != confirm and path_of(without_pick(state), confirm) != (step,):
        return None
    passed = DomainAction(action_id="scouts_pass", actor=decision.owner)
    actions = engine.whole_actions(state, decision.owner)
    if passed not in actions or any(
        action.action_id == "scouts_choose_option" for action in actions
    ):
        return None
    return passed


# ``pause`` answers every record; a bridge from the previous codec, when the
# current one changed the engine's flow, goes after it (module docstring).
BRIDGES: tuple[Bridge, ...] = (
    Bridge("pause", _pause),
    Bridge(
        SCOUTS_PAYOUT_BRIDGE,
        _decline_in(
            FrameKind.SCOUTS_EFFECT, SCOUTS_COLLECT, frozenset({SCOUTS_COLLECT})
        ),
        before_codec=SCOUTS_PAYOUT_CODEC,
    ),
    Bridge(
        OWED_DRAW_ROW_BRIDGE,
        _owed_draw_row,
        before_codec=OWED_DRAW_ROW_CODEC,
        rewrites=True,
    ),
    Bridge(
        SLIG_FARMER_LINE_BRIDGE,
        _slig_farmer_line,
        before_codec=SLIG_FARMER_CODEC,
        rewrites=True,
    ),
    Bridge(
        SLIG_FARMER_PAY_LINE_BRIDGE,
        _slig_farmer_pay_line,
        before_codec=SLIG_FARMER_CODEC,
    ),
    Bridge(
        SLIG_FARMER_PAY_BRIDGE,
        _slig_farmer_pay,
        before_codec=SLIG_FARMER_CODEC,
        rewrites=True,
    ),
    Bridge(
        SPICE_AGONY_REWARDS_BRIDGE,
        _spice_agony_rewards,
        before_codec=RULES_AUDIT_CODEC,
        follows=True,
        older=_records_no_memory,
    ),
    Bridge(
        FINAL_DELIVERY_PAYMENT_BRIDGE,
        _final_delivery_payment,
        before_codec=RULES_AUDIT_CODEC,
    ),
    Bridge(
        FINAL_DELIVERY_REWARDS_BRIDGE,
        _final_delivery_rewards,
        before_codec=RULES_AUDIT_CODEC,
    ),
    Bridge(
        FEYD_LAST_TROOP_BRIDGE,
        _feyd_last_troop,
        before_codec=RULES_AUDIT_CODEC,
        follows=True,
        older=_records_no_feyd_troop,
    ),
    Bridge(
        THRONE_ROOM_TROOP_BRIDGE,
        _throne_room_troop,
        before_codec=RULES_AUDIT_CODEC,
        rewrites=True,
    ),
    Bridge(
        CONTROL_THE_SPICE_TROOP_BRIDGE,
        _control_the_spice_troop,
        before_codec=RULES_AUDIT_CODEC,
        follows=True,
        older=_records_no_control_the_spice_troop,
    ),
    Bridge(
        FORBIDDEN_WEAPONS_KEEP_BRIDGE,
        _forbidden_weapons_keep,
        before_codec=RULES_AUDIT_CODEC,
        drops=True,
    ),
    Bridge(
        SCOUTS_NO_LINE_PASS_BRIDGE,
        _scouts_no_line_pass,
        before_codec=SCOUTS_NO_LINE_PASS_CODEC,
        rewrites=True,
    ),
)
