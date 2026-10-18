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
and the recorded step is tried again. Where this engine splits off part of
what one recorded step did (Imperial Privilege's draw, the OQ-106 draws), a
``follows`` bridge adds that part right after the recorded step, at the
moment the recording engine did it; several such parts can follow one step,
so the ``follows`` bridges are asked again until none answers. A bridge
never answers a decision the recorded step itself was made for
(``_made_for``), so a recorded choice that a rule change made illegal ends
the migration there as a ``Divergence`` instead of being skipped past;
every step before it still stands.

A record before codec v143 also had ``switch_graft_card``: a grafted Agent
turn resolved one box at a time and the switch made the other one active.
This engine offers both boxes at once, box 1's rows tagged ``box=1``
(docs/graft-boxes-plan.md), so ``migrate_record`` follows the recording
engine's active box through the turn (``_GraftSlot``): it drops each
switch and tags the steps the partner's box took. A dropped switch is
counted as ``graft_switch``, a tagged step as ``graft_box``.

A record before codec v147 resolved its Reveal choices on stacked
``REVEAL_CHOICE`` frames, which ``defer_reveal_choice`` and
``resume_reveal_choice`` reordered, and refused an optional one with its own
``decline_*``. This engine offers every pending choice on the Reveal frame at
once and lapses an unused optional one at ``finish_reveal`` (OQ-095 (7)
addition), and eleven ids name their card with ``source``. ``migrate_record``
follows the recording engine's choice frames through the Reveal
(``_RevealSlot``): it drops each defer and resume (``reveal_choice_defer``,
``reveal_choice_resume``) and each refusal of an optional choice
(``reveal_optional_refusal``; ``reveal_optional_refusal_by_order`` for an
optional recall's ``decline_reveal_spy_recall`` this engine would read as a
plain Spy icon's), and gives a step of a sourced id the one card that offers
it (``reveal_source``) or, when several do, the card of the top frame
(``reveal_source_by_order``).

Adding a bridge: when an engine change makes a recorded game stop, compare
the record with the engine's pending decision (``dune-imperium-records
check`` names both). If the new engine merely asks something the old one
answered implicitly, add a bridge gated on the codec version that changed
the flow and protect it with an old-engine record in
``tests/unit/records/data``. If a recorded choice is simply no longer legal,
the divergence is the right answer.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.personal_cards import (
    card_is_ghola,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import (
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import (
    FIXED_OUTCOME_SUFFIX,
    ChanceOutcome,
    is_fixed_outcome,
)
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.agent_effect_frame import (
    agent_box_can_resolve_by_choice,
    box_actions,
    route_box_action,
)
from dune_imperium.rules.agent_effects import boost_draw_card, resolves_boost_draw
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.effects import (
    active_agent_card,
    current_agent_effect_context,
    pending_agent_icons,
)
from dune_imperium.rules.frames import (
    OWED_CARD,
    OWED_INTRIGUE,
    FrameKind,
    own_turn_frame_index,
    replace_player,
)
from dune_imperium.rules.graft_boxes import (
    BOX_ACTION_IDS,
    active_box,
    is_grafted_turn,
    row_box,
    state_with_active_box,
    tagged,
    untagged,
)
from dune_imperium.rules.immortality import OWED_ORIGIN_RESEARCH, RESEARCH_ICON_ORDER
from dune_imperium.rules.influence import influence_can_rise
from dune_imperium.rules.intrigue import current_intrigue_choice_slot
from dune_imperium.rules.leader_abilities import legal_leader_signet_actions
from dune_imperium.rules.optional_trash import INTRIGUE_PENDING_KEY
from dune_imperium.rules.owed_draws import next_owed_draw
from dune_imperium.rules.pauses import SCOUTS_REWARD
from dune_imperium.rules.reveal_turn import (
    GENERATED_PERSUASION_KEY,
    REVEAL_CHOICE_EFFECT_ACTIONS,
    SOURCE_ARGUMENT,
    SOURCED_REVEAL_ACTION_IDS,
    reveal_card_identity,
    reveal_choice_effect_is_available,
    reveal_pending_gains,
)
from dune_imperium.rules.scouts_effects import SCOUTS_NO_OPTION, reward_was_chosen

# A round's end can need a handful of bridges in a row before the next
# recorded step fits (each reward recipient's pause, every seat's
# Conflict-end window, the Round Start pause); this many means the record
# and the engine have lost each other.
MAX_BRIDGES_PER_STEP = 64
# What ``follows`` bridges add after one recorded step: a few held draws
# (Piter's two rewards, a Tleilaxu Intrigue behind them, Hungry for Spice's
# card), up to three Scouts reward pauses with the rewards they hold. More
# than this means two bridges keep answering each other.
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
    # For a record before codec v143, the grafted box the recording engine
    # had active when the step was taken (``_GraftSlot``); 0 otherwise.
    graft_box: int = 0
    # For a record before codec v147, the card (definition id) of the Reveal
    # choice frame the recording engine had on top when the step was taken
    # (``_RevealSlot``); None otherwise.
    reveal_source: str | None = None


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
    # Recorded steps this engine has no counterpart for, by record index
    # and the reason's name: ``graft_switch`` (codec v143 offers both
    # grafted boxes at once, so ``switch_graft_card`` is dropped).
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
        """How many steps each bridge answered or rewrote, or dropped."""

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
        if bridge.before_codec is None
        or replay.action_codec_version < bridge.before_codec
    )
    state = engine.reset(replay.ruleset, replay.seed)
    migrated: list[MigratedStep] = []
    dropped: list[tuple[int, str]] = []
    graft = (
        _GraftSlot() if replay.action_codec_version < GRAFT_BOXES_CODEC else None
    )
    drops_refusals = replay.action_codec_version < OPTIONAL_REFUSALS_CODEC
    drops_turn_row_refusals = replay.action_codec_version < TURN_ROW_REFUSALS_CODEC
    reveal = (
        _RevealSlot() if replay.action_codec_version < REVEAL_CHOICES_CODEC else None
    )

    def ended(divergence: Divergence | None, at: GameState) -> MigratedRecord:
        return MigratedRecord(
            replay, tuple(migrated), at, divergence, tuple(dropped)
        )

    # Recorded steps of an in-turn window this engine keeps as turn rows,
    # held until the owner's turn frame offers them (``_waits_on_the_turn``).
    waiting_steps: list[tuple[int, DomainAction]] = []
    # Later recorded steps this engine asked for earlier and already applied
    # (``_asked_earlier``).
    consumed: set[int] = set()
    # Seats whose recorded Harvest Cells plays may still owe, in the record,
    # their "resolve the rewards" steps at the recording engine's cleanup,
    # where the step has no counterpart here (a copy whose acquisition was
    # answered first owes none, so a count may be left; the next Round
    # Start clears it). Such a step is dropped only while no Intrigue choice
    # of the seat is on top, where a rewards step of another card stands.
    harvest_due: Counter[int] = Counter()

    def harvest_rewards_due(index: int, recorded: ReplayStep, at: GameState) -> bool:
        """Drop the recorded Harvest Cells rewards step a recording engine
        asked at its cleanup, if this is it."""

        if (
            not isinstance(recorded, DomainAction)
            or recorded.action_id != "resolve_intrigue_rewards"
            or harvest_due[recorded.actor] <= 0
            or _intrigue_choice_on_top(at, recorded.actor)
        ):
            return False
        harvest_due[recorded.actor] -= 1
        dropped.append((index, HARVEST_CELLS_REWARDS_DROPPED))
        return True

    def apply_waiting(at: GameState) -> GameState | None:
        """Apply the held steps this engine now offers, oldest first, each
        with what the ``follows`` bridges add after it; None when those do
        not settle."""

        while waiting_steps:
            held_index, held_step = waiting_steps[0]
            try:
                after = engine.apply(at, held_step).state
            except IllegalActionError:
                return at
            waiting_steps.pop(0)
            migrated.append(MigratedStep(held_step, held_index, TURN_ROW_HELD))
            followed = _follow(engine, after, held_step, bridges, migrated)
            if followed is None:
                return None
            at = followed
        return at

    for index, recorded in enumerate(replay.steps):
        if index in consumed:
            continue
        if isinstance(recorded, ChanceOutcome) and ":round_start:" in (
            recorded.decision_id
        ):
            # The recording engine's cleanup is over.
            harvest_due.clear()
        if waiting_steps:
            settled = apply_waiting(state)
            if settled is None:
                return ended(
                    Divergence(
                        recorded_index=index,
                        step=recorded,
                        reason="a held turn-row step's follows did not settle",
                        pending=engine.current_decision(state),
                    ),
                    state,
                )
            state = settled
        if graft is not None and graft.drops(recorded):
            dropped.append((index, GRAFT_SWITCH_DROPPED))
            continue
        if harvest_rewards_due(index, recorded, state):
            # Before any bridge: a pause bridge would otherwise answer the
            # Round Start pause this step stood in front of in the record.
            continue
        if reveal is not None:
            reveal.sync(state)
            refused = reveal.refuses_optional_recall(engine, state, recorded)
            if refused is not None:
                dropped.append((index, refused))
                continue
        step, rewritten_by = recorded, None
        box = 0 if graft is None else graft.box
        reveal_source = None if reveal is None else reveal.top_source(recorded)
        for _ in range(MAX_BRIDGES_PER_STEP):
            if reveal is not None and rewritten_by in (None, *REVEAL_SOURCE_NAMES):
                named = reveal.named(engine, state, recorded)
                step, rewritten_by = named if named is not None else (recorded, None)
            if graft is not None and rewritten_by in (None, GRAFT_BOX_TAGGED):
                boxed = graft.boxed(engine, state, recorded)
                step, rewritten_by = (
                    (boxed, GRAFT_BOX_TAGGED) if boxed is not None else (recorded, None)
                )
                held = (
                    graft_box_held(engine, state, recorded, graft.box)
                    if boxed is None
                    else None
                )
                if held is not None:
                    divergence = Divergence(
                        recorded_index=index,
                        step=recorded,
                        reason=held,
                        pending=engine.current_decision(state),
                    )
                    return ended(divergence, state)
            try:
                after = engine.apply(state, step).state
            except IllegalActionError as error:
                # While box 1 was active, a rewrite bridge reads the step as
                # box 1's (``agent_card_effect_named``).
                asked = (
                    tagged(step, 1)
                    if box == 1 and isinstance(step, DomainAction)
                    else step
                )
                bridged = _bridge(engine, state, asked, bridges)
                if (
                    bridged is None
                    and drops_refusals
                    and isinstance(recorded, DomainAction)
                    and recorded.action_id in _OPTIONAL_REFUSALS
                ):
                    dropped.append((index, OPTIONAL_REFUSAL_DROPPED))
                    break
                if (
                    bridged is None
                    and drops_turn_row_refusals
                    and isinstance(recorded, DomainAction)
                    and recorded.action_id in _TURN_ROW_REFUSALS
                ):
                    dropped.append((index, TURN_ROW_REFUSAL_DROPPED))
                    break
                if (
                    bridged is None
                    and drops_turn_row_refusals
                    and _influence_at_the_top(state, recorded)
                ):
                    dropped.append((index, INFLUENCE_AT_TOP_DROPPED))
                    break
                if bridged is None and drops_turn_row_refusals:
                    earlier = _asked_earlier(
                        engine, state, replay.steps, index, consumed
                    )
                    if earlier is not None:
                        asked_index, asked_step = earlier
                        consumed.add(asked_index)
                        migrated.append(
                            MigratedStep(
                                asked_step,
                                asked_index,
                                _asked_earlier_bridge(
                                    asked_step, replay.steps[asked_index]
                                ),
                            )
                        )
                        followed = _follow(
                            engine,
                            engine.apply(state, asked_step).state,
                            asked_step,
                            bridges,
                            migrated,
                        )
                        if followed is None:
                            return ended(
                                Divergence(
                                    recorded_index=asked_index,
                                    step=asked_step,
                                    reason=(
                                        f"{MAX_FOLLOWS_PER_STEP} follows bridges "
                                        "after the step did not settle"
                                    ),
                                    pending=engine.current_decision(state),
                                ),
                                state,
                            )
                        state = followed
                        if asked_index == index or harvest_rewards_due(
                            index, recorded, state
                        ):
                            # The recorded step itself, taken under this
                            # engine's decision; or the rewards step it
                            # stood before, which has no counterpart here.
                            break
                        continue
                if (
                    bridged is None
                    and drops_turn_row_refusals
                    and _waits_on_the_turn(state, recorded)
                ):
                    assert isinstance(recorded, DomainAction)
                    waiting_steps.append((index, recorded))
                    break
                if (
                    bridged is None
                    and drops_refusals
                    and isinstance(recorded, DomainAction)
                    and recorded.action_id == _REPEATED_MISSION_COLLECTION
                ):
                    dropped.append((index, REPEATED_MISSION_DROPPED))
                    break
                if bridged is None and reveal is not None:
                    gone = reveal.without_counterpart(state, recorded)
                    if gone is not None:
                        dropped.append((index, gone))
                        break
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
                state = engine.apply(state, answer).state
                migrated.append(MigratedStep(answer, None, bridge.name))
                continue
            before, mark = state, len(migrated)
            migrated.append(
                MigratedStep(step, index, rewritten_by, box, reveal_source)
            )
            if graft is not None:
                graft.applied(after, step)
            if drops_turn_row_refusals and _plays_harvest_cells(recorded):
                assert isinstance(recorded, DomainAction)
                harvest_due[recorded.actor] += 1
            if reveal is not None:
                reveal.applied(before, after, recorded)
            followed = _follow(engine, after, step, bridges, migrated)
            if followed is None:
                del migrated[mark:]
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
    if waiting_steps:
        first_index, first_step = waiting_steps[0]
        settled = apply_waiting(state)
        if settled is None or waiting_steps:
            return ended(
                Divergence(
                    recorded_index=first_index,
                    step=first_step,
                    reason="a held turn-row step was never offered",
                    pending=engine.current_decision(state),
                ),
                state,
            )
        state = settled
    return ended(None, state)


# Codec v143 (docs/graft-boxes-plan.md 4.10): a grafted Agent turn offers
# both boxes from the start, box 1's rows tagged ``box=1``, and
# ``switch_graft_card`` is gone.
GRAFT_BOXES_CODEC: Final = 143
GRAFT_SWITCH: Final = "switch_graft_card"
GRAFT_SWITCH_DROPPED: Final = "graft_switch"
GRAFT_BOX_TAGGED: Final = "graft_box"

# Codec v146 (user ruling 2026-10-14, OQ-095 (2)): an optional effect of the
# Agent turn ("may", an arrow cost, a black trash icon [FAQ p. 3]) offers no
# refusal and lapses when the turn ends. A recording engine's refusal of one
# has no counterpart: this engine keeps the effect pending and the recorded
# ``finish_agent_turn`` lapses it, which leaves the same game state. Such a
# step is dropped once the engine refuses it and no bridge answers instead
# (a refusal this engine still offers -- a bundled selection part way
# through while the other grafted box waits -- is applied as recorded).
OPTIONAL_REFUSALS_CODEC: Final = 146
OPTIONAL_REFUSAL_DROPPED: Final = "optional_refusal"
_OPTIONAL_REFUSALS: Final = frozenset(
    {
        "decline_agent_card_acquisition",
        "decline_agent_card_discard",
        "decline_agent_card_intrigue_payment",
        "decline_agent_card_payment",
        "decline_agent_card_recall",
        "decline_agent_card_trash",
        "decline_corrinth_city_payment",
        "decline_imperial_privilege_intrigue",
        "decline_leader_board_repeat",
        "decline_leader_card_trash",
        "decline_leader_signet_payment",
        "decline_other_memories",
        "decline_sardaukar_commander",
        "decline_subcommittee",
        "decline_tech",
        "resolve_desert_tactics_without_trash",
    }
)
# Codec v149 (cleanup-2b, user decision 2026-10-17, OQ-095 (2)): a research
# bonus or an optional trash raised in its owner's own turn waits on the turn
# as rows with no refusal, and the turn's end lapses it, so a recording
# engine's in-turn ``decline_research_bonus`` or ``decline_optional_trash``
# has no counterpart and leaves the same state;
# it is dropped once this engine refuses it (outside the turn the window and
# its decline remain, and the step is applied as recorded).
TURN_ROW_REFUSALS_CODEC: Final = 149
TURN_ROW_REFUSAL_DROPPED: Final = "turn_row_refusal"
_TURN_ROW_REFUSALS: Final = frozenset(
    {"decline_optional_trash", "decline_research_bonus"}
)
# Also from v149 (cleanup-2b, rule decision 1, OQ-060): Shipping's and a Tech
# tile's acquire "Influence with any Faction" no longer offer a Faction at
# the top. A recording engine's pick of one gained nothing; this engine's
# icon waits instead and the recorded turn end lapses it (with every
# Faction at the top), so the step is dropped; in Combat, where no turn end
# lapses it, ``tech_influence_confirm`` names the confirm instead. A known
# divergence: a pick at the top beside a Faction that could still rise (the
# older engine offered all four for a Tech tile) leaves this engine's icon
# holding the turn end, so the record stops at its press; no step of the
# record says which Faction the seat would have raised.
INFLUENCE_AT_TOP_DROPPED: Final = "influence_at_top"
# Also from v149: such an effect raised above another frame of the owner's
# (an Intrigue card's choice still open, say) is offered once the turn frame
# is back on top, where a recording engine opened its window at once and the
# record answered it there. That step is held (``_waits_on_the_turn``) and
# applied as soon as this engine offers it, before the next recorded step.
TURN_ROW_HELD: Final = "turn_row_held"
# Also from v149 (user decision 2026-10-18): the Conflict's troops go back to
# the supply before the Conflict-end windows, and Harvest Cells resolves as
# it is played -- its specimens at once, its "You may also acquire a
# Tleilaxu card" asked right then. A recording engine fired it at the
# cleanup, after every window: its acquisition answer, recorded there, is
# taken as soon as this engine asks (``HARVEST_CELLS_AT_ONCE``), and its
# "resolve the rewards" step has no counterpart (``HARVEST_CELLS_REWARDS_
# DROPPED``). The window's press after a play is the finish
# (``conflict_end_finish``).
HARVEST_CELLS_AT_ONCE: Final = "harvest_cells_at_once"
# Also from v149 (user decision 2026-10-18, OQ-108): the winner takes the
# Conflict card, and Planetary Array's card, before the troops go back; a
# recorded reshuffle of that draw is taken as this engine asks
# (``_tech_draw_earlier``).
TECH_DRAW_AT_THE_WIN: Final = "tech_draw_at_the_win"
# ... and a seat's reshuffle of the same cards the recording engine did
# later under another decision (``_reshuffle_earlier``).
RESHUFFLE_MOVED: Final = "reshuffle_moved"


def _asked_earlier_bridge(asked: ReplayStep, recorded: ReplayStep) -> str:
    """The bridge name of a later ``recorded`` step taken earlier as
    ``asked``."""

    if not isinstance(asked, ChanceOutcome):
        return HARVEST_CELLS_AT_ONCE
    same = isinstance(recorded, ChanceOutcome) and (
        recorded.decision_id == asked.decision_id
    )
    return TECH_DRAW_AT_THE_WIN if same else RESHUFFLE_MOVED
HARVEST_CELLS_REWARDS_DROPPED: Final = "harvest_cells_rewards"
_HARVEST_CELLS_PREFIX: Final = "intrigue:harvest_cells:"
_HARVEST_CELLS_CHOICES: Final = frozenset(
    {
        "acquire_intrigue_reclaimed_forces",
        "acquire_intrigue_tleilaxu",
        "decline_intrigue_tleilaxu",
    }
)


def _harvest_cells_choice(state: GameState) -> int | None:
    """The owner of an open Harvest Cells acquisition asked as it was played
    in its Conflict-end window, if one is on top."""

    if not state.decision_stack:
        return None
    top = state.decision_stack[-1]
    source = dict(top.context).get("source")
    if (
        top.kind != FrameKind.INTRIGUE_CHOICE
        or not isinstance(top.decision, PlayerDecision)
        or not isinstance(source, str)
        or ":conflict_end:" not in source
    ):
        return None
    return top.decision.owner


def _asked_earlier(
    engine: UprisingRulesEngine,
    state: GameState,
    steps: tuple[ReplayStep, ...],
    index: int,
    consumed: set[int],
) -> tuple[int, ReplayStep] | None:
    """The owner's later recorded answer to the Harvest Cells acquisition
    this engine asks now, if it is legal here; or the later recorded
    reshuffle of the Planetary Array card this engine draws as the Conflict
    is won (``_tech_draw_earlier``), or of the same cards under another
    decision (``_reshuffle_earlier``)."""

    owner = _harvest_cells_choice(state)
    if owner is None:
        return _tech_draw_earlier(
            engine, state, steps, index, consumed
        ) or _reshuffle_earlier(engine, state, steps, index, consumed)
    for ahead in range(index, len(steps)):
        step = steps[ahead]
        if (
            ahead in consumed
            or not isinstance(step, DomainAction)
            or step.actor != owner
            or step.action_id not in _HARVEST_CELLS_CHOICES
        ):
            continue
        return (ahead, step) if step in engine.legal_actions(state, owner) else None
    return None


def _intrigue_choice_on_top(state: GameState, player: int) -> bool:
    if not state.decision_stack:
        return False
    top = state.decision_stack[-1]
    return (
        top.kind == FrameKind.INTRIGUE_CHOICE
        and isinstance(top.decision, PlayerDecision)
        and top.decision.owner == player
    )


def _tech_draw_earlier(
    engine: UprisingRulesEngine,
    state: GameState,
    steps: tuple[ReplayStep, ...],
    index: int,
    consumed: set[int],
) -> tuple[int, ReplayStep] | None:
    """The winner takes the Conflict card before the troops go back (codec
    v149, OQ-108), so Planetary Array's card is drawn there; a recording
    engine whose cleanup also fired a Harvest Cells drew it at that cleanup.
    Its reshuffle, recorded there under the same decision, is taken as this
    engine asks (none is looked for past the recording's next pause)."""

    decision = engine.current_decision(state)
    if (
        not isinstance(decision, ChanceDecision)
        or state.phase is not GamePhase.COMBAT
        or not state.combat_end_triggers_offered
        or ":tech_draw:" not in decision.decision_id
    ):
        return None
    for ahead in range(index, len(steps)):
        step = steps[ahead]
        if ahead in consumed or not isinstance(step, ChanceOutcome):
            continue
        if step.decision_id == decision.decision_id:
            if sorted(step.values) != sorted(decision.options):
                return None
            return ahead, step
        if step.decision_id.endswith(FIXED_OUTCOME_SUFFIX):
            return None
    return None


_PERSONAL_SHUFFLE: Final = re.compile(
    r"^round:\d+:player:(\d+):(?:.+:)?discard_shuffle$"
)
_PLANETARY_ARRAY: Final = "planetary_array"
_TECH_DRAW_SHUFFLE: Final = ":tech_draw:discard_shuffle"
# How far ahead a moved reshuffle is looked for: the recording engine drew
# Planetary Array's card after the next round's hand at the latest.
_RESHUFFLE_LOOKAHEAD: Final = 200


def _reshuffle_earlier(
    engine: UprisingRulesEngine,
    state: GameState,
    steps: tuple[ReplayStep, ...],
    index: int,
    consumed: set[int],
) -> tuple[int, ReplayStep] | None:
    """A seat's discard reshuffle this engine asks before the recording did:
    Planetary Array's card, drawn as the Conflict is won (OQ-108), takes the
    deck's top card a round earlier, so this engine shuffles the seat's
    discard at the win or at the next Round Start where the recording
    engine shuffled the same cards for that card after the next round's
    hand. The recorded permutation of those same cards is taken now, under
    this engine's decision; the game is then the recording's."""

    decision = engine.current_decision(state)
    if not isinstance(decision, ChanceDecision):
        return None
    asked = _PERSONAL_SHUFFLE.match(decision.decision_id)
    if asked is None or _PLANETARY_ARRAY not in (
        state.players[int(asked.group(1))].tech_ids
    ):
        return None
    cards = sorted(decision.options)
    for ahead in range(index, min(len(steps), index + _RESHUFFLE_LOOKAHEAD)):
        step = steps[ahead]
        if ahead in consumed or not isinstance(step, ChanceOutcome):
            continue
        recorded = _PERSONAL_SHUFFLE.match(step.decision_id)
        if (
            recorded is not None
            and recorded.group(1) == asked.group(1)
            # One side is that card's draw (``...:tech_draw:discard_shuffle``).
            and _TECH_DRAW_SHUFFLE in f"{decision.decision_id} {step.decision_id}"
            and sorted(step.values) == cards
        ):
            return ahead, ChanceOutcome(decision.decision_id, step.values)
    return None


def _conflict_end_reopened(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """The window's finish where a recording engine had closed it: a seat
    whose hand the play emptied may hold an Intrigue card again once the
    card's acquisition drew one (a Tleilaxu track Intrigue space), and the
    window, judged when it comes back on top, stays open (codec v149, user
    decision 2026-10-18, OQ-109). A recording engine drew that card at its
    cleanup, after every window, so its record goes on to another step."""

    if not isinstance(decision, PlayerDecision) or not state.decision_stack:
        return None
    top = state.decision_stack[-1]
    if (
        top.kind != FrameKind.CONFLICT_END_TRIGGER
        or dict(top.context).get("played") is not True
    ):
        return None
    if (
        isinstance(step, DomainAction)
        and step.actor == decision.owner
        and step.action_id in _CONFLICT_END_WINDOW_STEPS
    ):
        return None
    finish = DomainAction(
        action_id="finish_conflict_end_intrigue", actor=decision.owner
    )
    return finish if finish in engine.legal_actions(state, decision.owner) else None


_CONFLICT_END_WINDOW_STEPS: Final = frozenset(
    {
        "decline_conflict_end_intrigue",
        "finish_conflict_end_intrigue",
        "play_conflict_end_intrigue",
    }
)


def _plays_harvest_cells(recorded: ReplayStep) -> bool:
    """Whether a recorded step plays Harvest Cells in its Conflict-end
    window (the only window that plays it; no other card's rewards step
    can come between it and the cleanup)."""

    if (
        not isinstance(recorded, DomainAction)
        or recorded.action_id != "play_conflict_end_intrigue"
    ):
        return False
    card_id = dict(recorded.arguments).get("card_id")
    return isinstance(card_id, str) and card_id.startswith(_HARVEST_CELLS_PREFIX)


def _conflict_end_finish(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """The window's press after a play: ``finish_conflict_end_intrigue``
    where a recording engine offered its decline again (codec v149, user
    decision 2026-10-18)."""

    if (
        not isinstance(decision, PlayerDecision)
        or not isinstance(step, DomainAction)
        or step.action_id != "decline_conflict_end_intrigue"
        # Another seat's decline is its own window's: the window on top is
        # one this engine keeps open (``conflict_end_reopened``).
        or step.actor != decision.owner
    ):
        return None
    finish = DomainAction(
        action_id="finish_conflict_end_intrigue", actor=decision.owner
    )
    return finish if finish in engine.legal_actions(state, decision.owner) else None
_TURN_ROW_STEPS: Final = frozenset(
    {
        "choose_research_influence",
        "draw_planetologist_intrigue",
        "pay_research_bonus",
        "trash_intrigue_for_research_bonus",
        "trash_optional_card",
    }
)


def _waits_on_the_turn(state: GameState, step: ReplayStep) -> bool:
    """Whether ``step`` answers an effect waiting on its actor's own turn
    frame while another frame sits above it."""

    if not isinstance(step, DomainAction) or step.action_id not in _TURN_ROW_STEPS:
        return False
    index = own_turn_frame_index(state, step.actor)
    if index is None or index == len(state.decision_stack) - 1:
        return False
    return bool(turn_rows.pending(state.decision_stack[index]))


def _influence_at_the_top(state: GameState, step: ReplayStep) -> bool:
    """Whether ``step`` picks a Faction at the top for Shipping's or a Tech
    acquire icon's Influence."""

    if not isinstance(step, DomainAction):
        return False
    arguments = dict(step.arguments)
    if step.action_id != "choose_shipping_influence" and not (
        step.action_id == "resolve_tech_acquire_effect"
        and arguments.get("effect") == "influence"
    ):
        return False
    faction = arguments.get("faction")
    return isinstance(faction, str) and not influence_can_rise(
        state.players[step.actor], Faction(faction)
    )
# Also from v146 (user ruling 2026-10-14, OQ-019): Reverend Mother's repeat
# no longer queues the Arrakeen Scouts mission collection again, an effect
# of the visit not printed on the space. The pieces were all collected
# before the repeat, so a recording engine's second collection took nothing;
# it is dropped once this engine refuses it.
REPEATED_MISSION_DROPPED: Final = "repeated_mission_collection"
_REPEATED_MISSION_COLLECTION: Final = "scouts_collect_mission"


@dataclass
class _GraftSlot:
    """The grafted box a recording engine before codec v143 had active.

    That engine's effect frame resolved one grafted box at a time: the
    placed card's first (box 0), the partner's (box 1) after a
    ``switch_graft_card``, and back after another. Its turn end switched to
    a partner box still pending as this engine's does, so a reopened turn
    goes on with the box the press left active. This engine offers both
    boxes at once: a switch is dropped, and while box 1 was active each of
    its steps is that box's tagged row. A step of the turn's other effects
    keeps its form: its tagged twin is not a legal row. While box 1 was
    active the shared ``resolve_agent_card_effect(effect=cards)`` was box
    1's own icon whenever box 1 offered one, as that engine resolved it
    (Urgent Shigawire's added draw only otherwise), which the tagged row is.
    A step of the active box that this engine holds back behind the other
    box's bundled selection ends the migration (``graft_box_held``).
    """

    box: int = 0

    def drops(self, step: ReplayStep) -> bool:
        if isinstance(step, DomainAction) and step.action_id == GRAFT_SWITCH:
            self.box = 1 - self.box
            return True
        return False

    def boxed(
        self, engine: UprisingRulesEngine, state: GameState, step: ReplayStep
    ) -> DomainAction | None:
        """``step`` as box 1's row while box 1 was active, if that is legal."""

        if self.box == 0 or not isinstance(step, DomainAction):
            return None
        if not state.decision_stack or (
            state.decision_stack[-1].kind != FrameKind.AGENT_EFFECTS
        ):
            return None
        candidate = tagged(step, 1)
        if candidate in engine.legal_actions(state, step.actor):
            return candidate
        return None

    def applied(self, state: GameState, step: ReplayStep) -> None:
        if not isinstance(step, DomainAction):
            return
        if step.action_id in ("agent_turn", "choose_graft_partner"):
            self.box = 0
        elif step.action_id == "finish_agent_turn":
            frame = state.decision_stack[-1] if state.decision_stack else None
            self.box = (
                active_box(dict(frame.context))
                if frame is not None
                and frame.kind == FrameKind.AGENT_EFFECTS
                and isinstance(frame.decision, PlayerDecision)
                and frame.decision.owner == step.actor
                else 0
            )


def graft_box_held(
    engine: UprisingRulesEngine, state: GameState, step: ReplayStep, box: int
) -> str | None:
    """Why ``step``, box ``box``'s step in a record before codec v143, is not
    that box's row here; None when it is, or when it is no box's step.

    The recording engine resolved the box it had active (``_GraftSlot``)
    and let a switch leave the other box part way through a bundled
    selection; this engine holds the other box's rows until that selection
    is done (docs/graft-boxes-plan.md 4.3). Such a step would be read here
    as the other box's row or as none (Urgent Shigawire's added draw), and
    play on as a different move, so the record diverges there instead. A
    step the box's machinery does not offer (``agent_effect_frame.
    box_actions``) is the turn's other effects' and keeps its form.
    """

    if not isinstance(step, DomainAction) or step.action_id not in BOX_ACTION_IDS:
        return None
    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        return None
    if not is_grafted_turn(dict(frame.context)):
        return None
    if step not in box_actions(state, step.actor, box):
        return None
    legal = engine.legal_actions(state, step.actor)
    if box == 1:
        if tagged(step, 1) in legal:
            return None
    elif step in legal and route_box_action(state, step)[2] == 0:
        return None
    return (
        f"box {box}'s {step.action_id} waits here until the other box's "
        "selection is done (codec v143)"
    )


# Codec v147 (user ruling 2026-10-14, OQ-095 (7) addition): a Reveal choice no
# longer opens its own frame. Every choice of a revealed card waits on the
# Reveal frame and is offered there in any order; an optional one offers no
# refusal and lapses at ``finish_reveal``. A recording engine before v147
# stacked the choices as ``REVEAL_CHOICE`` frames and let the owner put the
# top one off (``defer_reveal_choice``) and bring a deferred one back
# (``resume_reveal_choice``); neither has a counterpart here, nor has its
# refusal of an optional choice: this engine keeps that choice pending and
# the recorded ``finish_reveal`` lapses it, which leaves the same game state.
# Eleven ids name their card with ``source`` here (``SOURCED_REVEAL_ACTION_IDS``):
# a recorded one is given the card the recording engine had on top.
REVEAL_CHOICES_CODEC: Final = 147
REVEAL_DEFER_DROPPED: Final = "reveal_choice_defer"
REVEAL_RESUME_DROPPED: Final = "reveal_choice_resume"
REVEAL_REFUSAL_DROPPED: Final = "reveal_optional_refusal"
# An optional recall's refusal (``decline_reveal_spy_recall``) this engine
# would read as a plain Spy icon's empty-supply refusal: dropped by the
# recording engine's frame order.
REVEAL_REFUSAL_BY_ORDER: Final = "reveal_optional_refusal_by_order"
# A recorded step given its ``source``: the one card that offers it, or, when
# several do, the card of the recording engine's top frame.
REVEAL_SOURCE_NAMED: Final = "reveal_source"
REVEAL_SOURCE_BY_ORDER: Final = "reveal_source_by_order"
REVEAL_SOURCE_NAMES: Final = (REVEAL_SOURCE_NAMED, REVEAL_SOURCE_BY_ORDER)

_DEFER: Final = "defer_reveal_choice"
_RESUME: Final = "resume_reveal_choice"
_RECALL_REFUSAL: Final = "decline_reveal_spy_recall"
# The refusals each optional choice offered before v147, by the refused id.
_Choice = PersonalCardRevealChoiceEffect
_OPTIONAL_REVEAL_REFUSALS: Final[dict[str, frozenset[_Choice]]] = {
    _RECALL_REFUSAL: frozenset(
        {
            _Choice.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
            _Choice.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION,
            _Choice.MAY_RECALL_SPY_FOR_THREE_STRENGTH,
        }
    ),
    "decline_reveal_influence_exchange": frozenset(
        {_Choice.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE}
    ),
    "decline_reveal_spice_influence": frozenset(
        {_Choice.MAY_PAY_THREE_SPICE_FOR_INFLUENCE}
    ),
    "decline_reveal_card_trash": frozenset(
        {
            _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH,
            _Choice.COMMAND_MAY_TRASH_CARD,
            _Choice.MAY_TRASH_SELF_FOR_COMBAT_ICON,
            _Choice.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS,
        }
    ),
    "decline_reveal_troop_retreat": frozenset(
        {
            _Choice.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH,
            _Choice.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION,
        }
    ),
    "decline_command_acquisition": frozenset(
        {_Choice.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD}
    ),
    "decline_reveal_influence_loss": frozenset(
        {_Choice.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE}
    ),
    "decline_reveal_troop_move": frozenset(
        {
            _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP,
            _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND,
        }
    ),
    "decline_reveal_troop_sacrifice": frozenset(
        {_Choice.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS}
    ),
}
# Covert Operation's first icon gave way to a plain Spy frame of the same card.
_SECOND_SPY_STEPS: Final = frozenset({"place_reveal_spy", _RECALL_REFUSAL})

type _Entry = tuple[str, str]


def _answers(effect: str, action_id: str) -> bool:
    """Whether a recording engine's ``effect`` frame offered ``action_id``."""

    choice = PersonalCardRevealChoiceEffect(effect)
    return action_id in REVEAL_CHOICE_EFFECT_ACTIONS[choice] or choice in (
        _OPTIONAL_REVEAL_REFUSALS.get(action_id, frozenset())
    )


@dataclass
class _RevealSlot:
    """The Reveal choice frames a recording engine before codec v147 had.

    That engine pushed one ``REVEAL_CHOICE`` frame per choice whose
    condition held at the Reveal's start, in hand order with the first on
    top, and queued the others; a late arrival's frames went directly above
    the Reveal frame, its unavailable ones to the queue's end. A recorded
    ``defer_reveal_choice`` moved the top frame to the queue's end, a
    ``resume_reveal_choice`` brought the oldest queued entry of that kind
    whose condition held back on top, and Covert Operation's first icon gave
    way to a plain Spy frame of the same card. Each recorded choice answered
    the top frame. This engine offers every pending choice at once, so a
    recorded id several cards offer here takes the top frame's card as its
    ``source``, and a refusal is dropped or applied by the frame it answered.
    A frame stays while this engine keeps the choice on top (a Spy recalled
    for its placement). Conditions are judged on this engine's state, which
    the trace keeps equal to the recording engine's; a late arrival's on the
    state before the next recorded step.
    """

    player: int | None = None
    # Bottom to top, above the Reveal frame.
    frames: list[_Entry] = field(default_factory=list)
    queue: list[_Entry] = field(default_factory=list)
    # How much of the event log the slot has read.
    seen: int = 0

    def sync(self, state: GameState) -> None:
        """Read the late arrivals since the last step."""

        for event in state.event_log[self.seen :]:
            payload = dict(event.payload)
            if self.player is None or payload.get("player") != self.player:
                continue
            if event.kind == "personal_card_late_revealed":
                card_id = payload.get("card_id")
                if isinstance(card_id, str):
                    self._arrive(state, card_id)
        self.seen = len(state.event_log)

    def _arrive(self, state: GameState, card_id: str) -> None:
        assert self.player is not None
        owner = state.players[self.player]
        persuasion = _reveal_generated(state, self.player)
        framed: list[_Entry] = []
        for effect in personal_card_for_instance(card_id).reveal_choice_effects:
            entry = (card_id, effect.value)
            if reveal_choice_effect_is_available(
                state,
                self.player,
                owner,
                counted_in_play(owner),
                card_id,
                effect,
                persuasion=persuasion,
            ):
                framed.append(entry)
            else:
                self.queue.append(entry)
        self.frames[0:0] = reversed(framed)

    def _frame_for(self, action_id: str) -> int | None:
        """The topmost frame that offered ``action_id`` (normally the top)."""

        for index in range(len(self.frames) - 1, -1, -1):
            if _answers(self.frames[index][1], action_id):
                return index
        return None

    def top_source(self, step: ReplayStep) -> str | None:
        """The card of the frame a recorded choice ``step`` answered."""

        if not isinstance(step, DomainAction) or step.actor != self.player:
            return None
        index = self._frame_for(step.action_id)
        return None if index is None else reveal_card_identity(self.frames[index][0])

    def refuses_optional_recall(
        self, engine: UprisingRulesEngine, state: GameState, step: ReplayStep
    ) -> str | None:
        """Drop a recorded optional recall's refusal this engine would apply.

        ``decline_reveal_spy_recall`` also passes up a plain Spy icon's
        recall-first with an empty supply, which this engine still offers:
        the frame it answered tells the two apart.
        """

        if not (
            isinstance(step, DomainAction)
            and step.action_id == _RECALL_REFUSAL
            and step.actor == self.player
        ):
            return None
        index = self._frame_for(_RECALL_REFUSAL)
        if index is None or PersonalCardRevealChoiceEffect(
            self.frames[index][1]
        ) not in (_OPTIONAL_REVEAL_REFUSALS[_RECALL_REFUSAL]):
            return None
        del self.frames[index]
        return (
            REVEAL_REFUSAL_BY_ORDER
            if _offered(engine, state, step)
            else REVEAL_REFUSAL_DROPPED
        )

    def without_counterpart(self, state: GameState, step: ReplayStep) -> str | None:
        """Drop a refused recorded step this engine has no counterpart for.

        A defer or a resume, or an optional choice's refusal: the slot moves
        the frames as the recording engine did.
        """

        if not isinstance(step, DomainAction) or step.actor != self.player:
            return None
        if step.action_id == _DEFER:
            if self.frames:
                self.queue.append(self.frames.pop())
            return REVEAL_DEFER_DROPPED
        if step.action_id == _RESUME:
            self._resume(state, str(dict(step.arguments).get("effect")))
            return REVEAL_RESUME_DROPPED
        if step.action_id in _OPTIONAL_REVEAL_REFUSALS:
            index = self._frame_for(step.action_id)
            if index is not None:
                del self.frames[index]
            return REVEAL_REFUSAL_DROPPED
        return None

    def _resume(self, state: GameState, effect: str) -> None:
        assert self.player is not None
        owner = state.players[self.player]
        persuasion = _reveal_generated(state, self.player)
        for position, (card_id, queued) in enumerate(self.queue):
            if queued == effect and reveal_choice_effect_is_available(
                state,
                self.player,
                owner,
                counted_in_play(owner),
                card_id,
                PersonalCardRevealChoiceEffect(queued),
                persuasion=persuasion,
            ):
                self.frames.append(self.queue.pop(position))
                return

    def named(
        self, engine: UprisingRulesEngine, state: GameState, step: ReplayStep
    ) -> tuple[DomainAction, str] | None:
        """A recorded ``step`` of a sourced id with the card that took it."""

        if not (
            isinstance(step, DomainAction)
            and step.action_id in SOURCED_REVEAL_ACTION_IDS
            and all(key != SOURCE_ARGUMENT for key, _ in step.arguments)
        ):
            return None
        return _with_source(engine, state, step, self.top_source(step))

    def applied(self, before: GameState, after: GameState, step: ReplayStep) -> None:
        """Follow the recording engine's frames through an applied step."""

        if not isinstance(step, DomainAction):
            return
        if step.action_id == "reveal_turn":
            self._begin(before, after, step.actor)
            return
        if step.actor != self.player:
            return
        if step.action_id == "finish_reveal":
            self.player, self.frames, self.queue = None, [], []
            return
        index = self._frame_for(step.action_id)
        if index is None:
            return
        top = after.decision_stack[-1] if after.decision_stack else None
        if (
            top is not None
            and top.kind == FrameKind.REVEAL_CHOICE
            and isinstance(top.decision, PlayerDecision)
            and top.decision.owner == step.actor
        ):
            # A step that must be followed at once keeps its frame on top.
            return
        card_id, effect = self.frames.pop(index)
        if (
            effect == PersonalCardRevealChoiceEffect.PLACE_TWO_SPIES.value
            and step.action_id in _SECOND_SPY_STEPS
        ):
            self.frames.insert(
                index, (card_id, PersonalCardRevealChoiceEffect.PLACE_SPY.value)
            )

    def _begin(self, before: GameState, after: GameState, player: int) -> None:
        """The frames the recording engine opened when ``player`` revealed."""

        frame = next(
            (
                frame
                for frame in reversed(after.decision_stack)
                if frame.kind == FrameKind.REVEAL
            ),
            None,
        )
        self.player, self.frames, self.queue = player, [], []
        self.seen = len(after.event_log)
        if frame is None:
            return
        context = dict(frame.context)
        count = context.get("revealed_card_count")
        persuasion = context.get(GENERATED_PERSUASION_KEY)
        if not isinstance(count, int) or not isinstance(persuasion, int):
            return
        revealed = tuple(
            str(context[f"revealed_card_{index:03d}"]) for index in range(count)
        )
        # The hand as that engine judged it: Chairdog's returned card is in
        # it, the revealed cards are not yet in play.
        owner = replace(
            before.players[player],
            hand=revealed,
            in_play=tuple(
                card_id
                for card_id in before.players[player].in_play
                if card_id not in revealed
            ),
        )
        judged = replace(before, players=replace_player(before.players, owner))
        cards_in_play = (*counted_in_play(owner), *revealed)
        framed: list[_Entry] = []
        for card_id in revealed:
            for effect in personal_card_for_instance(card_id).reveal_choice_effects:
                entry = (card_id, effect.value)
                if reveal_choice_effect_is_available(
                    judged,
                    player,
                    owner,
                    cards_in_play,
                    card_id,
                    effect,
                    persuasion=persuasion,
                ):
                    framed.append(entry)
                else:
                    self.queue.append(entry)
        self.frames = list(reversed(framed))


def _reveal_generated(state: GameState, player: int) -> int | None:
    """The Persuasion ``player``'s open Reveal has generated, if one is open."""

    for frame in reversed(state.decision_stack):
        if (
            frame.kind == FrameKind.REVEAL
            and isinstance(frame.decision, PlayerDecision)
            and frame.decision.owner == player
        ):
            value = dict(frame.context).get(GENERATED_PERSUASION_KEY)
            return value if isinstance(value, int) else None
    return None


def _offered(
    engine: UprisingRulesEngine, state: GameState, step: DomainAction
) -> list[DomainAction]:
    """This engine's legal actions that are ``step`` with or without a ``source``."""

    decision = engine.current_decision(state)
    if not isinstance(decision, PlayerDecision) or decision.owner != step.actor:
        return []
    return [
        action
        for action in engine.legal_actions(state, step.actor)
        if action.action_id == step.action_id
        and tuple(
            (key, value) for key, value in action.arguments if key != SOURCE_ARGUMENT
        )
        == step.arguments
    ]


def _with_source(
    engine: UprisingRulesEngine,
    state: GameState,
    step: DomainAction,
    hint: str | None,
) -> tuple[DomainAction, str] | None:
    """``step`` with the ``source`` this engine offers it with (codec v147).

    The one card that offers it, or the ``hint`` (the card of the recording
    engine's top frame) among several; None when none does, or several do
    and the hint is not one of them.
    """

    offered = _offered(engine, state, step)
    if len(offered) == 1:
        return offered[0], REVEAL_SOURCE_NAMED
    chosen = [
        action
        for action in offered
        if dict(action.arguments).get(SOURCE_ARGUMENT) == hint
    ]
    if hint is not None and len(chosen) == 1:
        return chosen[0], REVEAL_SOURCE_BY_ORDER
    return None


def walk(
    record: MigratedRecord, engine: UprisingRulesEngine | None = None
) -> Iterator[tuple[GameState, MigratedStep]]:
    """Yield the state before every migrated step, with that step."""

    engine = engine or UprisingRulesEngine()
    state = engine.reset(record.replay.ruleset, record.replay.seed)
    for migrated in record.steps:
        yield state, migrated
        state = engine.apply(state, migrated.step).state


def rewrite_step(
    engine: UprisingRulesEngine,
    state: GameState,
    step: ReplayStep,
    codec: int,
    graft_box: int = 0,
    reveal_source: str | None = None,
) -> ReplayStep | None:
    """``step`` in this engine's terms by a rewrite bridge open to ``codec``.

    For a move that was never recorded but was judged in an older engine's
    terms (``records.problems``: the play network's candidate); ``None``
    when no rewrite bridge applies to it at ``state``. ``graft_box`` is the
    grafted box that engine had active there (``MigratedStep.graft_box``):
    box 1's step is its tagged row (``_GraftSlot``). A
    ``switch_graft_card`` has no counterpart (codec v143), nor has a box's
    step this engine holds back behind the other box's bundled selection
    (``graft_box_held``). Before codec v147 a Reveal choice id that names
    its card here takes the one card that offers it, or ``reveal_source``
    (``MigratedStep.reveal_source``, the card of that engine's top choice
    frame) among several; a defer, a resume and an optional choice's refusal
    have no counterpart.
    """

    decision = engine.current_decision(state)
    if decision is None:
        return None
    if codec < REVEAL_CHOICES_CODEC and isinstance(step, DomainAction):
        sourced = step.action_id in SOURCED_REVEAL_ACTION_IDS and all(
            key != SOURCE_ARGUMENT for key, _ in step.arguments
        )
        if step.action_id in (_DEFER, _RESUME) or (
            step.action_id in _OPTIONAL_REVEAL_REFUSALS
            and not sourced
            and step not in engine.legal_actions(state, step.actor)
        ):
            return None
        if sourced:
            named = _with_source(engine, state, step, reveal_source)
            if (
                named is not None
                and step.action_id == _RECALL_REFUSAL
                and reveal_source is not None
                and dict(named[0].arguments).get(SOURCE_ARGUMENT) != reveal_source
            ):
                # The recording engine's top frame was an optional recall,
                # whose refusal has no counterpart here; a plain Spy icon's
                # pass of its recall-first is another card's choice.
                return None
            return None if named is None else named[0]
    if codec < GRAFT_BOXES_CODEC:
        if isinstance(step, DomainAction) and step.action_id == GRAFT_SWITCH:
            return None
        boxed = _GraftSlot(graft_box).boxed(engine, state, step)
        if boxed is not None:
            return boxed
        if graft_box_held(engine, state, step, graft_box) is not None:
            return None
        if graft_box == 1:
            step = (
                tagged(step, 1) if isinstance(step, DomainAction) else step
            )
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
    migrated: list[MigratedStep],
) -> GameState | None:
    """Apply what the ``follows`` bridges add right after the applied ``step``.

    A fixpoint: each pass asks the ``follows`` bridges in ``BRIDGES`` order
    and applies the first answer, and the passes repeat until one answers
    nothing. One recorded step can leave several held parts, some behind
    another: Piter's two rewards, a Bene Gesserit 4 card owed behind a Scouts
    line's held draw, up to three Scouts reward pauses in a row. Starting
    each pass from the first bridge keeps the recording engine's order (the
    step's own draws before the hooks that ran after it). ``None`` when
    ``MAX_FOLLOWS_PER_STEP`` answers did not settle.
    """

    follows = tuple(bridge for bridge in bridges if bridge.follows)
    firings = 0
    while (found := _next_follow(engine, state, step, follows)) is not None:
        if firings == MAX_FOLLOWS_PER_STEP:
            return None
        bridge, answer = found
        state = engine.apply(state, answer).state
        migrated.append(MigratedStep(answer, None, bridge.name))
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


_SCOUTS_CHOICE_ANSWERS: Final = frozenset(
    {"scouts_choose_option", "scouts_pass", SCOUTS_NO_OPTION}
)


def _scouts_no_option(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Answer a Scouts choice that offers only the confirm of taking nothing.

    Codec v149 (cleanup-2a) asks a seat with no line it can take; an older
    engine skipped it, so no recorded step answers the window. A recorded
    choice of that seat's was made for a window of its own, and the refusal
    of it then means a rule changed, which no bridge may hide
    (``_made_for``).
    """

    if (
        not isinstance(decision, PlayerDecision)
        or state.decision_stack[-1].kind != FrameKind.SCOUTS_CHOICE
        or _made_for(engine, state, decision, step, _SCOUTS_CHOICE_ANSWERS)
    ):
        return None
    confirm = DomainAction(action_id=SCOUTS_NO_OPTION, actor=decision.owner)
    if engine.legal_actions(state, decision.owner) != (confirm,):
        return None
    return confirm


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
        and not untagged(step).arguments
    ):
        return None
    # The icons of the box that resolved: box 1's carry ``box=1`` (codec
    # v143), and a record's step is box 1's while that box was active.
    box = row_box(step)
    named = [
        action
        for action in engine.legal_actions(state, decision.owner)
        if action.action_id == _CARD_EFFECT
        and row_box(action) == box
        and tuple(key for key, _ in untagged(action).arguments) == ("effect",)
    ]
    return named[0] if len(named) == 1 else None


_PRIVILEGE_RECALLS = frozenset(
    {
        "recall_agent_for_imperial_privilege",
        "recall_conflict_agent_for_imperial_privilege",
        "resolve_imperial_privilege_without_recall",
    }
)


def _privilege_draw(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw Imperial Privilege's card right after a recorded recall.

    Before codec v142 (4c7150d3) each of the three recall answers also drew
    the card, as the last thing its step did; this engine holds the draw as
    the board icon ``cards``. Resolving it at once draws the same card from
    the same deck with the same source, so a reshuffle meets the recorded
    chance outcome, and later recorded steps see the card in hand, as they
    did (one trashes it with Insider Information).
    """

    if not (
        isinstance(step, DomainAction)
        and step.action_id in _PRIVILEGE_RECALLS
        and isinstance(decision, PlayerDecision)
        and decision.owner == step.actor
        and state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
        and dict(state.decision_stack[-1].context).get("space_id")
        == "imperial_privilege"
    ):
        return None
    draw = DomainAction(
        action_id="resolve_board_effect",
        actor=step.actor,
        arguments=(("effect", "cards"),),
    )
    return draw if draw in engine.legal_actions(state, step.actor) else None


def _troop_from_garrison(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Pay Bene Gesserit Treachery's lost unit with a troop.

    Before codec v142 (0ef97fa1, OQ-105) the garrison cost was paid in
    troops without a question; this engine asks which unit when the
    garrison holds a troop and a Sardaukar Commander. The troop is what the
    recording engine took.
    """

    if (
        not isinstance(decision, PlayerDecision)
        or state.decision_stack[-1].kind != FrameKind.SCOUTS_EFFECT
        or _made_for(
            engine, state, decision, step, frozenset({"scouts_lose_garrison_unit"})
        )
    ):
        return None
    troop = DomainAction(action_id="scouts_lose_garrison_unit", actor=decision.owner)
    return troop if troop in engine.legal_actions(state, decision.owner) else None


def _prison_planet_commanders_only(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Decline Prison Planet for a seat whose garrison holds only Commanders.

    Before codec v142 (0ef97fa1, OQ-105) only a garrison troop could join
    Prison Planet, so such a seat was never asked; this engine offers the
    Commander. Declining changes nothing, as the skip did.
    """

    if (
        not isinstance(decision, PlayerDecision)
        or state.decision_stack[-1].kind != FrameKind.SCOUTS_MISSION
        or _made_for(
            engine,
            state,
            decision,
            step,
            frozenset(
                {
                    "scouts_decline_mission",
                    "scouts_join_mission",
                    "scouts_return_specimens",
                }
            ),
        )
    ):
        return None
    # The frame check above and the commander target below are defensive:
    # on this engine a Prison Planet decision with no troop target always
    # offers the commander, and the join actions exist only in this frame.
    # The troop target is what tells a seat the old engine asked (it has its
    # recorded answer) from one it skipped.
    legal = engine.legal_actions(state, decision.owner)
    owner = decision.owner

    def join(target: str) -> DomainAction:
        return DomainAction(
            action_id="scouts_join_mission",
            actor=owner,
            arguments=(("target", target),),
        )

    if join("") in legal or join("commander") not in legal:
        return None
    decline = DomainAction(action_id="scouts_decline_mission", actor=owner)
    return decline if decline in legal else None


# --- Codec v142 (OQ-106, user ruling 2026-10-10): a public choice and a
# hidden draw are never one step. Each bridge below adds a draw (or a pause)
# that v141 made inside a recorded step, right after that step.


def _shigawire_draw(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw Urgent Shigawire's added card as soon as it is its own step.

    Before codec v142 (6947f446) the boosted Bene Gesserit card's placement
    (``agent_turn``) drew the added card as the last thing it did, before
    the graft partner, the Gather Intelligence answer and the box's own
    icons; this engine holds it in the Agent box for
    ``resolve_agent_card_effect(effect=cards)``. It is taken the first time
    that action draws the added card itself: right after the placement, or
    right after the graft partner or Gather Intelligence answer this engine
    asks first (that one recorded step sees the hand a card short).

    While the box's own ``cards`` icon is offered (Tread in Darkness,
    Hidden Missive), the shared action would resolve that icon first. That
    icon is not taken in advance -- the record may never resolve it (a trash
    can lapse it) -- so the added card follows the record's own draw of the
    box icon, one to seven steps late; the two cards are the same. When
    v141 recorded a reshuffle right after the placement, this engine has no
    draw pending there if the box icon, the graft partner or the Gather
    Intelligence answer comes first, and the record stops on that chance.
    """

    del step
    if not isinstance(decision, PlayerDecision):
        return None
    draw = DomainAction(
        action_id=_CARD_EFFECT,
        actor=decision.owner,
        arguments=(("effect", "cards"),),
    )
    if state.decision_stack[-1].kind != FrameKind.AGENT_EFFECTS or not (
        resolves_boost_draw(state, draw)
        and draw in engine.legal_actions(state, decision.owner)
    ):
        return None
    if _ghola_draw(state, 0):
        # Codec v145's copy in a placed Ghola's box: an older engine had no
        # such draw at all, so it waits for the recorded turn end
        # (``_boost_draw_at_turn_end``) instead of shifting the turn's
        # later draws by a card.
        return None
    return draw


def _ghola_draw(state: GameState, box: int) -> bool:
    """Whether box ``box``'s waiting added draw is a Ghola's copy (v145)."""

    _, context = current_agent_effect_context(state)
    card_id = boost_draw_card(context, box)
    return bool(card_id) and card_is_ghola(personal_card_for_instance(card_id))


def _research_icon_order(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Resolve a research space's paired icons and c7r3's rewards right
    after the recorded step that raised them.

    Before codec v149 (cleanup-2b, rule decision 5) the specimen, the
    Tleilaxu advance and c7r3's Intrigue card and card came inside the step
    that moved the token or paid the cost, in the order
    ``RESEARCH_ICON_ORDER`` keeps; this engine offers each as its own step
    (a turn row, an owed draw, or a window outside the turn). A pair's
    optional trash stays the owner's own step, answered by the record.
    """

    del step
    if not isinstance(decision, PlayerDecision):
        return None
    legal = engine.legal_actions(state, decision.owner)
    icons = {
        dict(action.arguments)["effect"]: action
        for action in legal
        if action.action_id == "resolve_research_icon"
    }
    for icon in RESEARCH_ICON_ORDER:
        if icon in icons:
            return icons[icon]
    owner = state.players[decision.owner]
    for deck, action_id in (
        (OWED_INTRIGUE, "draw_owed_intrigue"),
        (OWED_CARD, "draw_owed_card"),
    ):
        # A press takes its deck's next waiting draw (``next_owed_draw``):
        # only when that is c7r3's is it the one the older engine drew here;
        # an older one is the record's own later step.
        index = next_owed_draw(owner, deck)
        if index is not None and owner.owed_draws[index][1] == OWED_ORIGIN_RESEARCH:
            draw = DomainAction(action_id=action_id, actor=decision.owner)
            return draw if draw in legal else None
    return None


def _tech_influence_confirm(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Confirm a Combat Tech acquire Influence an older engine spent at the
    top (codec v149, cleanup-2b): ``resolve_tech_influence_without_faction``
    in place of the recorded pick, when this engine offers it."""

    if not isinstance(decision, PlayerDecision) or not _influence_at_the_top(
        state, step
    ):
        return None
    confirm = DomainAction(
        action_id="resolve_tech_influence_without_faction", actor=decision.owner
    )
    return confirm if confirm in engine.legal_actions(state, decision.owner) else None


def _planetologist_intrigue(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw Arrakis Planetologist's Intrigue card for each replaced sandworm.

    Before codec v142 (9e9fbd71) ``replace_sandworms`` drew every
    replacement's Intrigue card inside the summoning step, then pushed one
    optional trash per replacement; this engine holds each card in its trash
    frame for ``draw_planetologist_intrigue``. It is taken when its frame
    comes to the top: after the summon, and for a second replacement
    (Deep Desert) after the recorded answer to the first frame, so that one
    answer sees the hand an Intrigue card short. Since codec v149
    (cleanup-2b) a replacement in its owner's own turn waits on the turn as
    rows instead: every card is taken right after the summon.
    """

    del step
    if not isinstance(decision, PlayerDecision):
        return None
    top = state.decision_stack[-1]
    if (
        top.kind == FrameKind.OPTIONAL_TRASH
        and dict(top.context).get(INTRIGUE_PENDING_KEY) is not True
    ):
        return None
    draw = DomainAction(action_id="draw_planetologist_intrigue", actor=decision.owner)
    return draw if draw in engine.legal_actions(state, decision.owner) else None


def _intrigue_held_rewards(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw Cunning's or Insider Information's card after the recorded trash.

    Before codec v142 (21069cbd) the trash slot's answer
    (``trash_intrigue_card`` or ``decline_intrigue_trash``) also gave the
    line's draw and finished the card; this engine keeps the Intrigue choice
    open with ``resolve_intrigue_rewards`` as its only action. A recorded
    reshuffle of that draw keeps its old id and is renamed by
    ``reshuffle_renamed``.

    A trashed Sardaukar Standard queues a Skill choice, which this engine
    opens above the held frame: the draw then follows the recorded
    ``choose_skill``, one step late, and if the draw reshuffles, the
    recorded reshuffle (v141 drew before opening the Skill choice) meets the
    Skill choice and the record stops there.
    """

    del step
    if not (
        isinstance(decision, PlayerDecision)
        and state.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
        and current_intrigue_choice_slot(state, decision.owner) is None
    ):
        return None
    held = DomainAction(action_id="resolve_intrigue_rewards", actor=decision.owner)
    return held if engine.legal_actions(state, decision.owner) == (held,) else None


_PITER = PersonalCardAgentEffect.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH
_PITER_REWARDS = frozenset({"cards", "research"})


def _reward_icon(player: int, key: str, box: int = 0) -> DomainAction:
    """A reward icon of the Agent box ``box`` (box 1's tagged, codec v143)."""

    icon = DomainAction(
        action_id=_CARD_EFFECT, actor=player, arguments=(("effect", key),)
    )
    return tagged(icon, box)


def _top_box(state: GameState) -> int:
    """The grafted box active in the Agent-turn effect frame on top (0 if none)."""

    frame = state.decision_stack[-1] if state.decision_stack else None
    if frame is None or frame.kind != FrameKind.AGENT_EFFECTS:
        return 0
    return active_box(dict(frame.context))


def _piter_rewards_waiting(state: GameState, player: int) -> tuple[str, ...]:
    """Piter's reward icons still armed in ``player``'s Agent box on top."""

    frame = state.decision_stack[-1]
    if (
        frame.kind != FrameKind.AGENT_EFFECTS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    context = dict(frame.context)
    if active_agent_card(context).agent_effect is not _PITER:
        return ()
    return tuple(key for key in pending_agent_icons(context) if key in _PITER_REWARDS)


def _piter_reward(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Take Piter, Genius Advisor's rewards right after the recorded troop loss.

    Before codec v142 (2f76372b) ``lose_agent_card_troop`` lost the troop,
    Researched, then drew two cards, all in its step; this engine arms
    ``cards`` and ``research`` as icons of the Agent box. A Research that
    settles at once (one way forward, or a card past the second genetic
    marker) goes first, as it did, so a reshuffle meets the recorded chance
    at the same point. A Research that asks something (the direction, a
    trash) went on after the two cards were drawn, so the cards go first
    and the Research then opens its frame for the recorded answer. When the
    first reward needs a reshuffle, the second follows the recorded
    (renamed) reshuffle. A one-way Research onto a trash space with a short
    deck leaves one step that sees the token a space behind.
    """

    if not isinstance(decision, PlayerDecision):
        return None
    player = decision.owner
    waiting = _piter_rewards_waiting(state, player)
    if not waiting:
        return None
    if isinstance(step, DomainAction):
        if step.action_id != "lose_agent_card_troop" or step.actor != player:
            return None
    elif len(waiting) != 1:
        return None
    legal = engine.legal_actions(state, player)
    key = waiting[0]
    # Piter's box is the active one: box 1's rewards are its tagged rows.
    box = _top_box(state)
    if len(waiting) == 2 and _reward_icon(player, "research", box) in legal:
        trial = engine.apply(
            state, _reward_icon(player, "research", box), legal_actions=legal
        ).state
        top = trial.decision_stack[-1]
        settles = isinstance(top.decision, ChanceDecision) or (
            top.kind == FrameKind.AGENT_EFFECTS
            and isinstance(top.decision, PlayerDecision)
            and top.decision.owner == player
        )
        key = "research" if settles else "cards"
    action = _reward_icon(player, key, box)
    return action if action in legal else None


_REVERSE_ENGINEERING_ORDER = ("intrigue", "cards")


def _reverse_engineering_reward(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw Reverse Engineering's rewards right after the recorded tile trash.

    Before codec v142 (2f76372b) Kota Odax's ``trash_leader_tech`` trashed
    the tile and drew the Intrigue card, then the card, in its step (in the
    Signet Ring's box or a Servo-Receivers frame); this engine keeps them as
    ``resolve_agent_card_effect(effect=intrigue|cards)``. With the Intrigue
    deck empty v141 queued that draw behind the card's, so the card goes
    first then (reasoned from v141's code; no record has it, and its
    Intrigue reshuffle, named after the new source, would stop the record).
    When the first reward needs a reshuffle, the second follows the
    recorded (renamed) reshuffle.
    """

    if not isinstance(decision, PlayerDecision):
        return None
    player = decision.owner
    if isinstance(step, DomainAction):
        if step.action_id != "trash_leader_tech" or step.actor != player:
            return None
    elif not isinstance(step, ChanceOutcome):
        return None
    rewards = [
        action
        for action in legal_leader_signet_actions(state, player)
        if action.action_id == _CARD_EFFECT
    ]
    if not rewards or (isinstance(step, ChanceOutcome) and len(rewards) != 1):
        return None
    order = (
        _REVERSE_ENGINEERING_ORDER
        if state.intrigue_deck
        else _REVERSE_ENGINEERING_ORDER[::-1]
    )
    legal = engine.legal_actions(state, player)
    # In the Signet Ring's box the rewards are that box's rows: box 1's
    # tagged (codec v143). A Servo-Receivers frame is no box.
    box = _top_box(state)
    return next(
        (
            _reward_icon(player, key, box)
            for key in order
            if _reward_icon(player, key) in rewards
            and _reward_icon(player, key, box) in legal
        ),
        None,
    )


_SCOUTS_HELD_DRAW = "scouts_rewards_first"


def _scouts_held_draw(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Take an Arrakeen Scouts line's draw right after its reward choice.

    Before codec v142 (2626df03) the step that settled one of a line's
    reward choices -- Water Discipline's trash, Leverage's Faction, Spies for
    Hire's Spy post, CHOAM Negotiations' Contract, or a later step that
    closed the frame the reward opened -- also drew the card printed after
    it; this engine holds that draw as the line's ``scouts_rewards_first``,
    then its only action. A reshuffle it needs keeps its recorded id.
    """

    del step
    if (
        not isinstance(decision, PlayerDecision)
        or state.decision_stack[-1].kind != FrameKind.SCOUTS_EFFECT
        or not reward_was_chosen(state.decision_stack[-1])
    ):
        return None
    held = DomainAction(action_id=_SCOUTS_HELD_DRAW, actor=decision.owner)
    return held if engine.legal_actions(state, decision.owner) == (held,) else None


_SCOUTS_REWARD_PAUSE = f":{SCOUTS_REWARD}{FIXED_OUTCOME_SUFFIX}"


def _scouts_reward_pause(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Pass the pause before a later Scouts auction winner's reward at once.

    Before codec v142 (aa600ee0) each later winner's reward ran inside the
    step that finished the one before it; this engine pauses before it. The
    ``pause`` bridge would answer it when the next recorded step is refused,
    but a record that ends right after that step must end with the rewards
    paid, as it did.
    """

    del engine, state, step
    if (
        isinstance(decision, ChanceDecision)
        and is_fixed_outcome(decision)
        and decision.decision_id.endswith(_SCOUTS_REWARD_PAUSE)
    ):
        return ChanceOutcome(decision.decision_id, decision.options)
    return None


_OWED_DRAW_ACTIONS = {
    OWED_INTRIGUE: "draw_owed_intrigue",
    OWED_CARD: "draw_owed_card",
}


def _owed_draw(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Take a triggered draw right after the recorded step that earned it.

    Codec v142 (6ec211d8, 43fa4fa7, fb-immediate) holds a draw that another
    printed effect triggers in the seat's own turn -- the Bene Gesserit
    Influence 4 bonus, Imperial Birthright, a Tleilaxu track Intrigue space,
    Sardaukar Soldier's trash, Overthrow's acquire box, Hungry for Spice,
    CHOAM Transports on a Contract completed in the seat's own turn -- as the
    seat's own ``draw_owed_*`` step; an older engine drew it inside the
    triggering step (Hungry for Spice's at its end, CHOAM Transports' in the
    completing step's hook). Four of them (Bene Gesserit 4, Imperial
    Birthright, Overthrow, CHOAM Transports) are immediate: right after the
    trigger the draw is the owner's only legal action
    (``frames.draw_is_immediate``), which this bridge takes at once anyway.
    The oldest waiting draw is taken as
    soon as it is offered: right after the step, or after the recorded step
    that closes the frame it waits behind (an Intrigue effect, a Reveal,
    Skill or Scouts choice; one to three steps see the hand a card short).
    A Scouts line's own held draw comes first (``scouts_held_draw``), as
    v141 drew a Leverage Faction's bonus card and then the line's; the two
    cards land in the same hand. A draw the turn-end press earned reopens
    the turn (``refinish_agent_turn``). Untested by any record: a Bene
    Gesserit 4 card held with the Intrigue deck empty reshuffles under a
    new id (``...:track_bonus:<n>:intrigue``) and would stop the record.
    """

    del step
    if not isinstance(decision, PlayerDecision):
        return None
    owed = state.players[decision.owner].owed_draws
    if not owed:
        return None
    draw = DomainAction(action_id=_OWED_DRAW_ACTIONS[owed[0][0]], actor=decision.owner)
    return draw if draw in engine.legal_actions(state, decision.owner) else None


_FOE_SOURCE = "leader_reveal:unpredictable_foe"


def _unpredictable_foe_draw(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw Muad'Dib's Unpredictable Foe card right after the step that met it.

    Before codec v142 (f8f7e080) the Reveal passives' hook drew it inside
    the step that first put a sandworm in Muad'Dib's Conflict during his
    Reveal; this engine queues it on the Reveal frame for
    ``draw_reveal_intrigue``, which takes the oldest waiting Intrigue entry.
    So it is drawn once per grant -- while no Reveal-gain Intrigue draw of
    his has been logged since the grant -- the first time his Reveal frame
    is on top again: at once, or one to three recorded steps late behind a
    Reveal choice (a choice that needs the card then stops the record).
    """

    del step
    if not isinstance(decision, PlayerDecision):
        return None
    frame = state.decision_stack[-1]
    player = decision.owner
    if frame.kind != FrameKind.REVEAL or not any(
        kind == "intrigue" and source == _FOE_SOURCE
        for kind, _, source in reveal_pending_gains(dict(frame.context))
    ):
        return None
    grant = f"round:{state.round_number}:player:{player}:leader_reveal:intrigue"
    gains = f"round:{state.round_number}:player:{player}:reveal_gain:"
    for event in reversed(state.event_log):
        if event.event_id == grant and event.kind == "leader_ability_resolved":
            break
        if event.event_id.startswith(gains) and event.kind in (
            "intrigue_card_drawn",
            "intrigue_draw_short",
        ):
            return None
    else:
        return None
    draw = DomainAction(action_id="draw_reveal_intrigue", actor=player)
    return draw if draw in engine.legal_actions(state, player) else None


_DISCARD_SHUFFLE = ":discard_shuffle"


def _reshuffle_renamed(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Give a recorded discard reshuffle the id of the one this engine asks.

    Codec v142's OQ-106 splits draw some cards under new sources: Piter's
    (``agent_card_payment`` became ``agent_card:<card>:cards`` and
    ``...:research``, with everything its Research draws), Reverse
    Engineering's (``leader_signet:cards``), Urgent Shigawire's added card
    (``shigawire:<card>:cards``), Cunning's held draw (``...:rewards:draw``),
    and a held draw can swap places with another draw of the seat. A
    reshuffle a short draw asks for is named after its source, so the
    recorded one is refused. It is the same seat's same discard pile when
    both are personal reshuffles of that seat in this round and the recorded
    values are exactly the pile; the recorded order is kept. An Intrigue
    reshuffle is never renamed.
    """

    del engine
    if not (
        isinstance(step, ChanceOutcome)
        and isinstance(decision, ChanceDecision)
        and state.decision_stack[-1].kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
        and step.decision_id != decision.decision_id
    ):
        return None
    player = dict(state.decision_stack[-1].context).get("player")
    prefix = f"round:{state.round_number}:player:{player}:"
    if not all(
        decision_id.startswith(prefix) and decision_id.endswith(_DISCARD_SHUFFLE)
        for decision_id in (step.decision_id, decision.decision_id)
    ) or Counter(step.values) != Counter(decision.options):
        return None
    return ChanceOutcome(decision.decision_id, step.values)


def _renamed_draw_reshuffle(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Give a recorded discard or Intrigue reshuffle the name of the draw
    that asks it.

    Codec v149 (cleanup-2c) renames draws by the event grammar: an Agent
    box's after the box (``round:R:player:P:agent_card:<card>``, where an
    older engine named some after the card's definition,
    ``agent_card_discard``, ``agent_card_payment`` or ``shigawire:<card>``),
    a Leader ability's after the Leader (Hungry for Spice, Esmar Tuek's
    Tuek's Sietch draw), what a research or Tleilaxu track space gives
    after the seat's track space, a Research draw and an Intrigue line's or
    a Signet payment's draw after their source without the caller's extra
    word. The reshuffle a short draw asks for carries that name. Renamed
    only when the recorded name is the older one of exactly such a rename
    (``_cleanup2c_renamed``), the same kind of reshuffle in this round, the
    recorded values exactly the pile.
    """

    del engine
    suffix = _RENAMED_RESHUFFLES.get(state.decision_stack[-1].kind)
    if not (
        suffix is not None
        and isinstance(step, ChanceOutcome)
        and isinstance(decision, ChanceDecision)
        and step.decision_id != decision.decision_id
        and _cleanup2c_renamed(step.decision_id, decision.decision_id, suffix)
    ):
        return None
    prefix = f"round:{state.round_number}:"
    if not all(
        decision_id.startswith(prefix) and decision_id.endswith(suffix)
        for decision_id in (step.decision_id, decision.decision_id)
    ) or Counter(step.values) != Counter(decision.options):
        return None
    return ChanceOutcome(decision.decision_id, step.values)


_INTRIGUE_SHUFFLE = ":intrigue_shuffle"
# The reshuffles a renamed draw asks for, and the word ending their names.
_RENAMED_RESHUFFLES: dict[str, str] = {
    FrameKind.PERSONAL_DRAW_RESHUFFLE: _DISCARD_SHUFFLE,
    FrameKind.INTRIGUE_RESHUFFLE: _INTRIGUE_SHUFFLE,
}


_OLD_BOX_DRAW = re.compile(
    r"^round:\d+:player:\d+:(?:agent_card(?:_discard|_payment)?|shigawire):"
)
_NEW_BOX_DRAW = re.compile(r"^round:\d+:player:\d+:agent_card:")
_NEW_TRACK_DRAW = re.compile(
    r"^round:\d+:player:\d+(:(?:research:c\d+r\d+|tleilaxu:\d+):.*)$"
)
# Esmar Tuek's draw for a visit to Tuek's Sietch: named after the visitor,
# now after Esmar (cleanup-2c-4); the seat changes.
_OLD_ESMAR_DRAW = re.compile(r"^(round:\d+):player:\d+:tuek_sietch_visit:")
_NEW_ESMAR_DRAW = re.compile(r"^(round:\d+):player:\d+:leader:esmar_tuek:")
# The words a caller added to a draw's source, which cleanup-2c dropped.
_DROPPED_DRAW_WORDS = (":draw", ":research_draw", ":intrigue", ":intrigue_draw")


def _cleanup2c_renamed(old: str, new: str, suffix: str = _DISCARD_SHUFFLE) -> bool:
    """Whether reshuffle ``new`` is ``old`` under a cleanup-2c draw name
    (both ending with ``suffix``): a box's draw named after the box, Hungry
    for Spice's after the Leader, Esmar Tuek's after Esmar, what a research
    or Tleilaxu track space gives after the seat's track space, a caller's
    extra word dropped -- and the seat unchanged but for Esmar's."""

    esmar = _OLD_ESMAR_DRAW.match(old), _NEW_ESMAR_DRAW.match(new)
    if esmar[0] is not None and esmar[1] is not None:
        return esmar[0].group(1) == esmar[1].group(1)
    seat = re.compile(r"^round:\d+:player:(\d+):")
    old_seat, new_seat = seat.match(old), seat.match(new)
    if old_seat is not None and new_seat is not None:
        if old_seat.group(1) != new_seat.group(1):
            return False
    elif new_seat is not None:
        # A seatless opener (an Arrakeen Scouts reward's research) moved a
        # seat's track token: the space's draw is that seat's now.
        return _track_renamed(old, new, suffix)
    elif old_seat is not None:
        return False
    for extra in _DROPPED_DRAW_WORDS:
        if old.replace(f"{extra}{suffix}", suffix) == new != old:
            return True
    if new.replace(":leader:steersman_y_rkoon:", ":hungry_for_spice:") == old:
        return True
    if _OLD_BOX_DRAW.match(old) and _NEW_BOX_DRAW.match(new):
        return True
    return _track_renamed(old, new, suffix)


def _track_renamed(old: str, new: str, suffix: str) -> bool:
    """Whether ``new`` names after the seat's research or Tleilaxu track
    space the draw ``old`` named after what moved the token (with an icon's
    extra ``:card`` or ``:intrigue``)."""

    track = _NEW_TRACK_DRAW.match(new)
    return track is not None and any(
        old.replace(f"{extra}{suffix}", suffix).endswith(track.group(1))
        for extra in ("", ":card", ":intrigue")
    )


_FINISH_AGENT_TURN = "finish_agent_turn"


def _refinish_agent_turn(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """End again an Agent turn this engine reopened for its held draws.

    A draw earned while the Agent turn is finishing -- in the recorded
    ``finish_agent_turn`` press itself (a Usurped card's trash moving the
    Tleilaxu token onto Intrigue or spice, Hungry for Spice) or in a step
    answered on top of the finishing frame -- was drawn inside that step by
    an older engine, and the turn closed. Codec v142 (6ec211d8, 43fa4fa7)
    holds it, so the turn reopens (``agent_turn_reopened``); ``owed_draw``
    takes it right after the step, and the turn then waits for a second
    press the record never made. When the next recorded step shows the turn
    was over (it is refused and was not this decision's answer), the turn is
    ended again -- only after a reopen, with no draw left waiting and
    nothing that would reopen it once more. Where v141 reopened the turn
    too (units to deploy, a Contract), its record goes on with the seat's
    own steps, which this engine accepts, so this never answers there. No
    record of the 1,563-game corpus reaches this; a built state pins it.
    """

    if not isinstance(decision, PlayerDecision):
        return None
    player = decision.owner
    frame = state.decision_stack[-1]
    press = DomainAction(action_id=_FINISH_AGENT_TURN, actor=player)
    if (
        frame.kind != FrameKind.AGENT_EFFECTS
        or state.players[player].owed_draws
        or _made_for(engine, state, decision, step, frozenset({_FINISH_AGENT_TURN}))
        or not _reopened_since_press(state, player)
        or press not in engine.legal_actions(state, player)
    ):
        return None
    pressed = engine.apply(state, press)
    if any(event.kind == "agent_turn_reopened" for event in pressed.events):
        return None
    return press


def _shigawire_partner_draw(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw a Bene Gesserit graft partner's Urgent Shigawire card before the
    recorded turn end.

    Codec v144 (user ruling 2026-10-12, OQ-107: "1. 짝도 받음"): a Bene
    Gesserit graft partner played while the boost is pending takes it, and
    the draw added to its box waits as box 1's
    ``resolve_agent_card_effect(effect=cards)``; the turn cannot end over
    it. An older engine gave the partner nothing, so its record never took
    that draw and pressed ``finish_agent_turn`` with it waiting. The draw is
    taken as late as it may be, right before that press, so every recorded
    step of the turn sees the hand the recording engine showed. The boost
    the older engine kept pending is spent here: a later Bene Gesserit card
    of the round that leaned on it diverges (the rule change).
    """

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and step.action_id == _FINISH_AGENT_TURN
        and state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    ):
        return None
    draw = _reward_icon(decision.owner, "cards", 1)
    if not (
        resolves_boost_draw(state, draw)
        and draw in engine.legal_actions(state, decision.owner)
    ):
        return None
    if _ghola_draw(state, 1):
        # A Ghola partner's copy of the placed card's draw is codec v145's
        # (``_boost_draw_at_turn_end``), not a boosted partner's.
        return None
    return draw


def _boost_draw_at_turn_end(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Draw an Urgent Shigawire card an older engine never had before the
    recorded turn end.

    Codec v145 leaves two added draws waiting where an older engine had
    none (user ruling 2026-10-12, OQ-107; OQ-022):
    - Ghola "copies the entire Agent box of the card it's grafted to"
      [Immortality p. 14], and the boosted card's draw was "added to its
      Agent box" [Urgent Shigawire card], so Ghola's box draws a card too;
    - a card that trashes itself with its own trash icon (Throne Room
      Politics' optional trash) leaves play by its own effect, so its added
      draw stays; an older engine lapsed it.
    Either draw holds the turn end, so the record pressed
    ``finish_agent_turn`` with it waiting. It is taken as late as it may
    be, right before that press, so every recorded step of the turn sees
    the hand the recording engine showed. Only these two are answered: a
    Ghola's draw, or the draw of a card no longer in play; any other added
    draw waiting at the press is a record of a flow that held it otherwise
    (a v141 placement drew it at once: ``_shigawire_draw``).
    """

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and step.action_id == _FINISH_AGENT_TURN
        and state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    ):
        return None
    _, context = current_agent_effect_context(state)
    in_play = state.players[decision.owner].in_play
    legal = engine.legal_actions(state, decision.owner)
    for box in (0, 1):
        card_id = boost_draw_card(context, box)
        draw = _reward_icon(decision.owner, "cards", box)
        if (
            card_id
            and (_ghola_draw(state, box) or card_id not in in_play)
            and resolves_boost_draw(state, draw)
            and draw in legal
        ):
            return draw
    return None


# Codec v144 (OQ-057 (1)): the optional boxes whose choice an older
# engine's turn end skipped -- its dry run read them as boxes that can only
# fizzle -- with the refusal that answers each.
_REFUSED_AT_TURN_END: Final = {
    PersonalCardAgentEffect.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH: (
        "decline_agent_card_payment"
    ),
    PersonalCardAgentEffect.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU: (
        "decline_agent_card_payment"
    ),
    PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN: (
        "decline_agent_card_payment"
    ),
    PersonalCardAgentEffect.MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER: (
        "decline_agent_card_acquisition"
    ),
}


def _box_refused_at_turn_end(
    engine: UprisingRulesEngine,
    state: GameState,
    decision: Decision,
    step: ReplayStep,
) -> ReplayStep | None:
    """Refuse an optional Agent box before the recorded turn end.

    Codec v144 (user instruction 2026-10-12 "2. 고치자", OQ-057 (1)): a box
    that still offers a choice giving its effect holds the turn end. An
    older engine's turn end was offered beside Piter's, Tleilaxu Surgeon's
    and Dissecting Kit's payable arrows and Tleilaxu Master's acquisition
    (a dry run misread them), and its press fizzled the box: the result of
    the refusal ("You do not have to pay such a cost on a card" [Main p.
    20], OQ-058). So right before that recorded press the box is refused,
    box 1's tagged. A mandatory box the press skipped (Stitched Horror's
    "Choose two", Beguiling Pheromones' trash) has no refusal, and the
    record diverges there: the rule fix.
    """

    if not (
        isinstance(decision, PlayerDecision)
        and isinstance(step, DomainAction)
        and step.actor == decision.owner
        and step.action_id == _FINISH_AGENT_TURN
        and state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    ):
        return None
    context = dict(state.decision_stack[-1].context)
    legal = engine.legal_actions(state, decision.owner)
    for box in (0, 1) if is_grafted_turn(context) else (0,):
        view = state_with_active_box(state, box)
        effect = active_agent_card(dict(view.decision_stack[-1].context)).agent_effect
        refusal_id = None if effect is None else _REFUSED_AT_TURN_END.get(effect)
        if refusal_id is None:
            continue
        refusal = tagged(DomainAction(refusal_id, decision.owner), box)
        # Only a box that holds the end: one offering just its refusal (the
        # cost cannot be paid) still lets the press fizzle it.
        if refusal in legal and agent_box_can_resolve_by_choice(view, decision.owner):
            return refusal
    return None


def _reopened_since_press(state: GameState, player: int) -> bool:
    """Whether ``player``'s Agent turn was reopened after its last press."""

    turn = f"round:{state.round_number}:player:{player}:"
    for event in reversed(state.event_log):
        if event.event_id == f"{turn}agent_turn_reopened":
            return True
        if event.event_id == f"{turn}{_FINISH_AGENT_TURN}":
            return False
    return False


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
    # Codec v142 (4c7150d3) holds Imperial Privilege's draw as its own board
    # icon; older recalls drew at once.
    Bridge("imperial_privilege_draw", _privilege_draw, before_codec=142, follows=True),
    # Codec v142 (0ef97fa1, OQ-105) lets a Sardaukar Commander pay a seat's
    # own troop costs, so it asks where an older engine paid with a troop or
    # skipped a seat that had only Commanders.
    Bridge("garrison_unit_troop", _troop_from_garrison, before_codec=142),
    Bridge(
        "prison_planet_commanders_only",
        _prison_planet_commanders_only,
        before_codec=142,
    ),
    # Codec v142 (OQ-106) holds each hidden draw that a public choice or a
    # trigger used to make in its step as a step of its own. The follows
    # bridges below take them in the order an older engine drew them: the
    # recorded step's own draws first, then the triggered draws its hooks
    # made after it (Hungry for Spice, then the Reveal passives').
    Bridge("shigawire_draw", _shigawire_draw, before_codec=142, follows=True),
    Bridge(
        "planetologist_intrigue",
        _planetologist_intrigue,
        before_codec=142,
        follows=True,
    ),
    Bridge(
        "intrigue_held_rewards",
        _intrigue_held_rewards,
        before_codec=142,
        follows=True,
    ),
    Bridge("piter_reward", _piter_reward, before_codec=142, follows=True),
    Bridge(
        "reverse_engineering_reward",
        _reverse_engineering_reward,
        before_codec=142,
        follows=True,
    ),
    # A Scouts line's draw comes before a Bene Gesserit 4 or Imperial
    # Birthright card its Faction choice owes, which is offered only once
    # the line closes.
    Bridge("scouts_held_draw", _scouts_held_draw, before_codec=142, follows=True),
    Bridge(
        "scouts_reward_pause",
        _scouts_reward_pause,
        before_codec=142,
        follows=True,
    ),
    Bridge("owed_draw", _owed_draw, before_codec=142, follows=True),
    Bridge(
        "unpredictable_foe_draw",
        _unpredictable_foe_draw,
        before_codec=142,
        follows=True,
    ),
    Bridge("reshuffle_renamed", _reshuffle_renamed, before_codec=142, rewrites=True),
    Bridge("refinish_agent_turn", _refinish_agent_turn, before_codec=142),
    # Codec v144 (OQ-107) gives a Bene Gesserit graft partner a pending
    # Urgent Shigawire boost; its added draw holds the turn end.
    Bridge(
        "shigawire_partner_draw", _shigawire_partner_draw, before_codec=144
    ),
    # Codec v144 (OQ-057 (1)) holds the turn end for an optional box whose
    # choice is still open; an older engine's press fizzled it.
    Bridge(
        "box_refused_at_turn_end", _box_refused_at_turn_end, before_codec=144
    ),
    # Codec v145 gives a Ghola grafted to the boosted card a copy of its
    # added draw (OQ-107) and keeps the draw of a card that trashed itself
    # with its own trash icon (OQ-022); either holds the turn end.
    Bridge(
        "boost_draw_at_turn_end", _boost_draw_at_turn_end, before_codec=145
    ),
    # Codec v149 (cleanup-2a) asks a Scouts seat with no line it can take,
    # which an older engine skipped.
    Bridge("scouts_no_option_window", _scouts_no_option, before_codec=149),
    # Codec v149 (cleanup-2b) resolves a research space's paired icons and
    # c7r3's rewards each as its own step; an older engine resolved them
    # inside the step that raised them.
    Bridge(
        "research_icon_order",
        _research_icon_order,
        before_codec=149,
        follows=True,
    ),
    # Codec v149 (user decision 2026-10-18) finishes the Conflict-end window
    # after a play, where an older engine offered its decline again.
    Bridge(
        "conflict_end_finish",
        _conflict_end_finish,
        before_codec=149,
        rewrites=True,
    ),
    # Codec v149 (user decision 2026-10-18, OQ-109) keeps a Conflict-end
    # window open after a play while its seat holds an Intrigue card, judged
    # when it comes back on top; an older engine had closed it at the play.
    Bridge(
        "conflict_end_reopened",
        _conflict_end_reopened,
        before_codec=149,
    ),
    # Codec v149 (cleanup-2b) confirms a Tech acquire Influence with every
    # Faction at the top in Combat, where an older engine let it pick one.
    Bridge(
        "tech_influence_confirm",
        _tech_influence_confirm,
        before_codec=149,
        rewrites=True,
    ),
    # Codec v149 (cleanup-2c) renames draws by the event grammar, and the
    # reshuffles they ask for with them.
    Bridge(
        "draw_reshuffle_renamed",
        _renamed_draw_reshuffle,
        before_codec=149,
        rewrites=True,
    ),
)
