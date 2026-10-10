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

from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import (
    FIXED_OUTCOME_SUFFIX,
    ChanceOutcome,
    is_fixed_outcome,
)
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_effects import resolves_boost_draw
from dune_imperium.rules.effects import active_agent_card, pending_agent_icons
from dune_imperium.rules.frames import OWED_CARD, OWED_INTRIGUE, FrameKind
from dune_imperium.rules.intrigue import current_intrigue_choice_slot
from dune_imperium.rules.leader_abilities import legal_leader_signet_actions
from dune_imperium.rules.optional_trash import INTRIGUE_PENDING_KEY
from dune_imperium.rules.pauses import SCOUTS_REWARD
from dune_imperium.rules.reveal_turn import reveal_pending_gains
from dune_imperium.rules.scouts_effects import reward_was_chosen

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
                    return MigratedRecord(replay, tuple(migrated), state, divergence)
                bridge, answer = bridged
                if bridge.rewrites:
                    step, rewritten_by = answer, bridge.name
                    continue
                state = engine.apply(state, answer).state
                migrated.append(MigratedStep(answer, None, bridge.name))
                continue
            before, mark = state, len(migrated)
            migrated.append(MigratedStep(step, index, rewritten_by))
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
                return MigratedRecord(replay, tuple(migrated), before, divergence)
            state = followed
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


def rewrite_step(
    engine: UprisingRulesEngine, state: GameState, step: ReplayStep, codec: int
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
    return draw


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
    answer sees the hand an Intrigue card short.
    """

    del step
    if (
        not isinstance(decision, PlayerDecision)
        or state.decision_stack[-1].kind != FrameKind.OPTIONAL_TRASH
        or dict(state.decision_stack[-1].context).get(INTRIGUE_PENDING_KEY) is not True
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


def _reward_icon(player: int, key: str) -> DomainAction:
    return DomainAction(
        action_id=_CARD_EFFECT, actor=player, arguments=(("effect", key),)
    )


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
    if len(waiting) == 2 and _reward_icon(player, "research") in legal:
        trial = engine.apply(
            state, _reward_icon(player, "research"), legal_actions=legal
        ).state
        top = trial.decision_stack[-1]
        settles = isinstance(top.decision, ChanceDecision) or (
            top.kind == FrameKind.AGENT_EFFECTS
            and isinstance(top.decision, PlayerDecision)
            and top.decision.owner == player
        )
        key = "research" if settles else "cards"
    action = _reward_icon(player, key)
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
    return next(
        (
            _reward_icon(player, key)
            for key in order
            if _reward_icon(player, key) in rewards
            and _reward_icon(player, key) in legal
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
)
