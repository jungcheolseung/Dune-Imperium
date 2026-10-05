"""The Immortality decision windows, and the one optional-trash window.

``graft_partner``, ``research_advance``, ``research_bonus``,
``optional_trash`` (every source), ``intrigue_peek`` and
``conflict_end_trigger`` (Harvest Cells gained as a Conflict reward).

``HANDLERS`` maps each decision kind this module answers to its handler; a
handler returning None makes the agent answer at random
(``DefaultRandomChoice``) and count a fallback.

App side: ``analysis/ai/spec/immortality.md`` (its Errata override the body)
§3-§4, §7.5 and §8, ``spec/epic-goto11-promo-draft.md`` §2.3 and §6,
``15-combat-phase.md`` §3.1 and §3.4. Our windows: scratchpad map R7 §2.2
(b) (d) (e) (f) (g) (j), §4.2. Addresses are build
dad97e2021144d45b5b4f022e07bd3b3.

- ``graft_partner`` (``choose_graft_partner``, mandatory). The app asks the
  partner once, at ``AgentTurnPhase`` state 50, with ``GraftCardEvaluator``
  (``abilities.immortality.graft_card_evaluate``): before the placement,
  forced. The ``turn`` window evaluates it on the turn-time state and leaves
  the partner in ``Memory.intents[("graft_partner", round, placed card)]``;
  this window takes it when it is legal (and drops it). Without one (the
  placement was not app_ai's turn answer) the evaluator runs here, on the
  current state, over our legal partners (hand order, then the Imperium Row
  for Usurp). A forced prompt answered with nothing or with a value of 0 or
  less is ``DefaultRandomChoice``: a plain (non-Graft) placed card never
  takes a partner in the app's evaluator, so its partner is random, as in
  the app's ``missingSpace`` case.
- ``research_advance`` (``choose_research_space``, mandatory). The app asks
  the direction inside the ability that grants the Research. When that
  answer is already known (a Breakthrough play's, a Reveal research key's:
  ``windows.intrigue.research_intent``) its space is taken. Otherwise
  ``GainResearchAbility::Evaluate @0x4e03720`` over the next research spaces
  in the app's ``NextIndices`` order: "no space" at 1.0 (an empty entity
  list, Errata), then each space at ``SpaceValue + 1.0``; first strictly
  best.
- ``research_bonus``: the research-space custom abilities the app adds to
  the playmat (spec §3.3-§3.4). ``choose_research_influence`` (c6r6):
  ``GainAnyFactionInfluenceCustomAbility`` = ``GainAnyInfluenceAbility``'s
  Evaluate over every faction track (``GetFactionTrackTargets(_ => true)``,
  Explicit: forced). ``trash_intrigue_for_research_bonus`` (c7r3):
  ``TrashIntrigueForDrawAndIntrigue::Evaluate @0x4e2a820`` (shuffled Intrigue
  targets, the first junk card at 5.0; no junk card -> no answer -> decline;
  Optional). ``pay_research_bonus`` (c8r6): ``PaySolariForTleilaxuInfluence``
  (Optional; ``Evaluate @0x4e14b30`` = its V) is a key only while its
  ``Cost`` holds (7 Solari, Tleilaxu rank below 7); value > 0 -> pay, else
  decline. So the app never pays to advance past rank 7 (R7 §2.4), and its V
  is 0 from rank 6 up anyway.
- ``optional_trash`` (``trash_optional_card`` / ``decline_optional_trash``):
  one handler for every source. Control the Spice
  (``spec/epic-goto11-promo-draft.md`` §2.3) and Stitched Horror (spec
  §6.11): the app answers the payment (the picks) and the trashed card in one
  Evaluate (``ControlTheSpiceAbility``, ``StitchedHorrorAbility``); the
  ``agent_effects`` window stores the card it names
  (``CONTROL_THE_SPICE_TRASH_INTENT`` keyed by the paying card,
  ``STITCHED_HORROR_TRASH_INTENT`` by the Stitched Horror card), and this
  window trashes that card when it is legal, else declines. Every other
  source (the research hexes c3r3 / c7r5 ``TrashCustomAbility``, Throne Room
  Politics ``TrashAgentAbility``, Liet Kynes' sandworm replacement, tech and
  Scouts trash icons) and a Control the Spice or Stitched Horror trash
  without a stored answer: ``TrashAbility::Evaluate @0x4ce98a0`` =
  ``GetCardToTrash(targets, 1.0)``: the card, or "trash nothing" -> decline
  (the same pick those two Evaluates make, ``minTrashValue`` 1.0).
- ``intrigue_peek`` (``keep_peeked_intrigue``, mandatory): the
  ``KeepIntrigueCard`` picker, ``ImperiumCeremonyAbility::EvaluateIntrigue
  @0x4e0b6f0`` (shuffle, junk 1 / other 50, first strictly best).
- ``conflict_end_trigger`` (``play_conflict_end_intrigue`` /
  ``decline_conflict_end_intrigue``): Harvest Cells gained as a Conflict
  reward. The app offers CombatResolution-timing Intrigue in each reward
  entry's resolution prompt (``<PlayCombatResolutionIntrigueCards>d__21``,
  15 §3.4 step 3; non-forced for this key); the key is
  ``HarvestCellsAbility::Evaluate @0x4c75550`` (two specimens, or a Tleilaxu
  card's ``AcquireValue`` + two specimens). Value > 0 -> play, else decline.
  A card whose app ability cannot run (``Cost`` = 3 troops in the Conflict)
  is no key. The answer is stored like every Intrigue play
  (``windows.intrigue``: ``("intrigue", card)`` and the play's event index)
  for the later ``acquire_intrigue_tleilaxu`` step.

Judgements (no exact app twin):

- ``research_advance`` when the app answers "no space" (no space worth more
  than 0: e.g. c8r4 and c8r6 at Tleilaxu rank 7): the app's ``GainResearch``
  then draws a card instead of moving (spec §3.1), which our mandatory
  window cannot do. We take the space the evaluator itself ranks first
  (first strictly best ``SpaceValue``), the move the app values most.
  Industrial Espionage's and Breakthrough's research Evaluates differ only
  in their thresholds (``SpaceValue`` against 1.0, resp. against nothing), so
  the space this rule picks is the one they would name; so a Research step
  without a stored answer (agent and space boxes, Industrial Espionage,
  research-space chains, acquire boxes) is answered with
  ``GainResearchAbility``'s Evaluate.
- ``research_bonus``: the app's custom ability stays on the playmat until
  used, so an unused c7r3 / c8r6 bonus could still be taken in a later
  prompt; our engine asks once, and the app's answer at that prompt is
  final.
- ``graft_partner`` without a stored answer is evaluated on the placed state
  (the Agent already sent, the space's cost already paid), not the app's
  state 50.
- ``conflict_end_trigger``: ``GetHarvestCellsTargets`` and
  ``GetSpecimensAvailable`` are UNTRACED (spec §12 #6). The request is the
  one ``windows.intrigue.intrigue_request`` builds for every play of the
  card (its judgement: the dealt Tleilaxu Row cards the seat can pay for
  with the two harvested specimens). The play is valued when our engine
  asks, after the rewards and before the troops return; the app's
  resolution prompt comes right after the seat's own reward entry.
- An owner entity the Evaluate never reads (the research or trash custom
  ability's playmat, Imperium Ceremony) is a stand-in.
- A target with no app archetype (an expansion card a later stage maps), a
  Conflict-end card with no Combat-turn app ability, a research space off
  the app's track, or a ``research_bonus`` id this module does not know
  makes the handler return None, so the census shows the gap (never a
  silent decline).
"""

import re
from collections.abc import Callable, Sequence
from typing import Final

from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.epic_promo import ControlTheSpiceAbility
from dune_imperium.agents.app_ai.abilities.generic import TrashCustomAbility
from dune_imperium.agents.app_ai.abilities.immortality import (
    GainAnyFactionInfluenceCustomAbility,
    GainResearchAbility,
    ImperiumCeremonyAbility,
    PaySolariForTleilaxuInfluence,
    TrashIntrigueForDrawAndIntrigue,
    graft_card_evaluate,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    IntrigueAbility,
    ability_for_prompt,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    card_entity,
    intrigue_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.choice import first_strictly_best
from dune_imperium.agents.app_ai.context import (
    FACTIONS,
    RESEARCH_SPACE_IDS,
    card_id,
)
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
from dune_imperium.agents.app_ai.windows.agent_effects import (
    CONTROL_THE_SPICE_TRASH_INTENT,
    STITCHED_HORROR_TRASH_INTENT,
)
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    decide,
    str_arg,
    with_arg,
)
from dune_imperium.agents.app_ai.windows.intrigue import (
    INTENT,
    INTENT_AT,
    intrigue_request,
    research_intent,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.agents.app_ai.windows.scouts import scouts_trash_source
from dune_imperium.agents.app_ai.windows.turn import GRAFT_PARTNER_INTENT
from dune_imperium.core.actions import DomainAction

# ``Memory.intents`` keys this module reads (their writers own the names):
# ``(GRAFT_PARTNER_INTENT, round, placed card) -> partner`` (``turn``);
# ``(CONTROL_THE_SPICE_TRASH_INTENT, round, paying card) -> card | None`` and
# ``(STITCHED_HORROR_TRASH_INTENT, round, Stitched Horror card) -> card``
# (``agent_effects``).

#: The optional-trash source of an Agent-box payment: Control the Spice's
#: ends with the paying card (``round:<r>:player:<p>:agent_card_payment:
#: <card ref>``), Stitched Horror's with its pick number (``...:<n>``)
#: (``rules/agent_effects.py``).
_PAYMENT_SOURCE: Final = ":agent_card_payment:"
_STITCHED_HORROR_SOURCE: Final = re.compile(r":agent_card_payment:\d+$")
#: ``CanGainTleilaxuInfluence @0x4a77ca0``: rank below 7.
_TLEILAXU_TOP: Final = 7
#: ``PaySolariForTleilaxuInfluence::Cost``: ``HasResources.AtLeast(Solari, 7)``.
_PAY_SOLARI: Final = 7


def _known_card(ref: str) -> bool:
    return card_id(ref) in CARD_ARCHETYPES


def _known_intrigue(ref: str) -> bool:
    return card_id(ref) in INTRIGUE_ARCHETYPES


def _refs(actions: Sequence[DomainAction], name: str) -> list[str]:
    return [ref for a in actions if (ref := str_arg(a, name)) is not None]


def _first_ref(answer: Answer) -> str | None:
    """The first entity ref of the answer's first response item, if any."""

    if not answer.response or not answer.response[0]:
        return None
    ref = answer.response[0][0]
    return ref if isinstance(ref, str) else None


def _playmat_owner(run: DecisionRun) -> Entity:
    """A stand-in owner for a playmat custom ability (never read by E)."""

    return research_space_entity(run.ctx.research_space_id() or RESEARCH_SPACE_IDS[0])


def _frame_source(run: DecisionRun) -> str:
    """The ``source`` the open frame records (what granted it), or ``""``."""

    source = run.ctx.top_frame_context.get("source")
    return source if isinstance(source, str) else ""


# ---------------------------------------------------------------------------
# graft_partner — GraftCardEvaluator (AgentTurnPhase state 50)
# ---------------------------------------------------------------------------


def _intended_partner(value: object) -> str | None:
    """The partner ref a stored graft answer names (a ref or an Answer)."""

    if isinstance(value, str):
        return value
    if isinstance(value, Answer):
        return _first_ref(value)
    return None


def graft_partner(run: DecisionRun) -> DomainAction | None:
    """``GraftCardEvaluator``: the second card of the graft."""

    actions = run.by_id("choose_graft_partner")
    context = run.ctx.top_frame_context
    placed = context.get("card_id")
    space_id = context.get("space_id")
    if not actions or not isinstance(placed, str) or not isinstance(space_id, str):
        return None
    key = (GRAFT_PARTNER_INTENT, run.ctx.round_number, placed)
    intended = _intended_partner(run.memory.intents.pop(key, None))
    if intended is not None:
        action = with_arg(actions, "card_id", intended)
        if action is not None:
            return action
    refs = _refs(actions, "card_id")
    if not _known_card(placed) or not all(_known_card(ref) for ref in refs):
        return None
    seat = run.ctx.seat
    hand = set(run.ctx.hand)
    played = card_entity(placed, seat)
    space = space_entity(space_id, run.ctx.board)
    candidates = tuple(card_entity(ref, seat if ref in hand else None) for ref in refs)
    request = Request((TargetInfo(candidates, (), 1, 1, True),), forced=True)

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = graft_card_evaluate(run.profile, request, played, space)
        ref = _first_ref(answer)
        return answer.value, None if ref is None else with_arg(actions, "card_id", ref)

    source = Source("GraftCardEvaluator", Stage.PROMPT, actions, evaluate)
    return decide(run, [source], skip=None, forced=True)


# ---------------------------------------------------------------------------
# research_advance — GainResearchAbility::Evaluate
# ---------------------------------------------------------------------------


def research_advance(run: DecisionRun) -> DomainAction | None:
    """The research token's direction (``GainResearchAbility`` E).

    A Breakthrough play's or a Reveal research key's answer already names
    the space (``windows.intrigue.research_intent``); that space is taken.
    """

    actions = run.by_id("choose_research_space")
    intended = research_intent(run)
    if intended is not None:
        return with_arg(actions, "space_id", intended)
    offered = set(_refs(actions, "space_id"))
    if not offered or not offered <= set(RESEARCH_SPACE_IDS):
        return None  # no space, or one the app's track does not have
    # ``NextIndices`` order: lower app index first.
    spaces = sorted(offered, key=RESEARCH_SPACE_IDS.index)
    p = run.profile
    entities = tuple(research_space_entity(s) for s in spaces)
    request = Request((TargetInfo(entities, (), 1, 1, True),), forced=True)
    answer = GainResearchAbility(_playmat_owner(run)).evaluate(p, request)
    ref = _first_ref(answer)
    if ref is None:
        # "No space": the app draws a card instead (judgement, module doc).
        best = first_strictly_best([(s, p.research_space_value(s).sum) for s in spaces])
        assert best is not None
        ref = best[0]
    space_id = ref.removeprefix("research:")
    return with_arg(actions, "space_id", space_id)


# ---------------------------------------------------------------------------
# research_bonus — the research-space custom abilities
# ---------------------------------------------------------------------------


def _research_influence(
    run: DecisionRun, actions: Sequence[DomainAction]
) -> DomainAction | None:
    """c6r6: ``GainAnyFactionInfluenceCustomAbility`` (Explicit, forced)."""

    offered = set(_refs(actions, "faction"))
    tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
    ability = GainAnyFactionInfluenceCustomAbility(_playmat_owner(run))
    request = Request((TargetInfo(tracks),), forced=True)

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, request)
        ref = _first_ref(answer)
        return answer.value, None if ref is None else with_arg(actions, "faction", ref)

    source = Source(ability.APP_CLASS, Stage.PROMPT, tuple(actions), evaluate)
    return decide(run, [source], skip=None, forced=True)


def _research_intrigue_trash(
    run: DecisionRun,
    actions: Sequence[DomainAction],
    decline: DomainAction | None,
) -> DomainAction | None:
    """c7r3: ``TrashIntrigueForDrawAndIntrigue`` (Optional)."""

    refs = _refs(actions, "card_id")
    if not all(_known_intrigue(ref) for ref in refs):
        return None
    cards = tuple(intrigue_entity(ref, run.ctx.seat) for ref in refs)
    ability = TrashIntrigueForDrawAndIntrigue(_playmat_owner(run))
    request = Request((TargetInfo(cards),))

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, request)
        ref = _first_ref(answer)
        return answer.value, None if ref is None else with_arg(actions, "card_id", ref)

    source = Source(ability.APP_CLASS, Stage.PROMPT, tuple(actions), evaluate)
    return decide(run, [source], skip=decline, forced=False)


def _research_payment(
    run: DecisionRun, pay: DomainAction, decline: DomainAction | None
) -> DomainAction | None:
    """c8r6: ``PaySolariForTleilaxuInfluence`` (Optional; a key only while
    its ``Cost`` holds)."""

    me = run.ctx.me
    if (
        me.resources.solari < _PAY_SOLARI
        or run.ctx.tleilaxu_influence() >= _TLEILAXU_TOP
    ):
        return decline
    ability = PaySolariForTleilaxuInfluence(_playmat_owner(run))

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, Request())
        return answer.value, None if answer.response is None else pay

    source = Source(ability.APP_CLASS, Stage.PROMPT, (pay,), evaluate)
    return decide(run, [source], skip=decline, forced=False)


def research_bonus(run: DecisionRun) -> DomainAction | None:
    """A research space's printed choice (c6r6, c7r3, c8r6)."""

    decline = run.first("decline_research_bonus")
    influence = run.by_id("choose_research_influence")
    if influence:
        return _research_influence(run, influence)
    trash = run.by_id("trash_intrigue_for_research_bonus")
    if trash:
        return _research_intrigue_trash(run, trash, decline)
    pay = run.first("pay_research_bonus")
    if pay is not None:
        return _research_payment(run, pay, decline)
    if any(a.action_id != "decline_research_bonus" for a in run.legal):
        return None  # a bonus choice this window does not know: a gap
    # The arrow's cost cannot be paid: the lapse is the only choice.
    return decline


# ---------------------------------------------------------------------------
# optional_trash — Control the Spice's stored answer, else TrashAbility E
# ---------------------------------------------------------------------------

#: A stored answer that is missing (not "trash nothing").
_MISSING: Final = object()


def _stored_trash(run: DecisionRun, source: str) -> object:
    """The trash an Agent-box answer already named for this frame, if any.

    Control the Spice: the key names the paying card the source ends with.
    Stitched Horror: the source ends with the pick number; the key names the
    card whose box resolves (the own Agent-effect frame's active card).
    Popped once read; ``_MISSING`` when the frame is neither or nothing was
    stored.
    """

    if _PAYMENT_SOURCE not in source:
        return _MISSING
    intents = run.memory.intents
    round_number = run.ctx.round_number
    if _STITCHED_HORROR_SOURCE.search(source):
        effects = run.ctx.own_frame_context("agent_effects")
        card_ref = None if effects is None else effects.get("card_id")
        if not isinstance(card_ref, str):
            return _MISSING
        return intents.pop(
            (STITCHED_HORROR_TRASH_INTENT, round_number, card_ref), _MISSING
        )
    card_ref = source.split(_PAYMENT_SOURCE, 1)[1]
    return intents.pop(
        (CONTROL_THE_SPICE_TRASH_INTENT, round_number, card_ref), _MISSING
    )


def optional_trash(run: DecisionRun) -> DomainAction | None:
    """One optional trash, whatever granted it."""

    decline = run.first("decline_optional_trash")
    trashes = run.by_id("trash_optional_card")
    granted_by = _frame_source(run)
    stored = _stored_trash(run, granted_by)
    if stored is not _MISSING:
        ref = (
            ControlTheSpiceAbility.trash_target(stored)
            if isinstance(stored, Answer)
            else stored
        )
        action = with_arg(trashes, "card_id", ref) if isinstance(ref, str) else None
        return decline if action is None else action
    refs = _refs(trashes, "card_id")
    if not all(_known_card(ref) for ref in refs):
        return None
    seat = run.ctx.seat
    cards = tuple(card_entity(ref, seat) for ref in refs)
    # The Scouts trash icon (Oversight, Water Discipline): the line's own
    # ``TrashCustomAbility`` (scouts.md §3.13); a Scouts line without one
    # is not mirrored.
    from_scouts, line_trash = scouts_trash_source(run, granted_by)
    if from_scouts and line_trash is None:
        return None
    ability = line_trash or TrashCustomAbility(
        Entity(Kind.CARD, granted_by, None, seat)
    )
    request = Request((TargetInfo(cards, (), 0, 1),))

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, request)
        if answer.response is None:
            return answer.value, None
        ref = _first_ref(answer)
        if ref is None:  # "trash nothing"
            return answer.value, decline
        return answer.value, with_arg(trashes, "card_id", ref)

    actions = (*trashes, *(() if decline is None else (decline,)))
    source = Source(ability.APP_CLASS, Stage.PROMPT, actions, evaluate)
    return decide(run, [source], skip=decline, forced=False)


# ---------------------------------------------------------------------------
# intrigue_peek — ImperiumCeremonyAbility::EvaluateIntrigue
# ---------------------------------------------------------------------------


def intrigue_peek(run: DecisionRun) -> DomainAction | None:
    """Imperium Ceremony: keep one of the Intrigue deck's top two."""

    actions = run.by_id("keep_peeked_intrigue")
    refs = _refs(actions, "instance_id")
    if not refs or not all(_known_intrigue(ref) for ref in refs):
        return None
    seat = run.ctx.seat
    cards = tuple(intrigue_entity(ref, seat) for ref in refs)
    ability = ImperiumCeremonyAbility(Entity(Kind.CARD, _frame_source(run), None, seat))
    request = Request((TargetInfo(cards, (), 1, 1, True),), forced=True)

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate_intrigue(run.profile, request)
        ref = _first_ref(answer)
        if ref is None:
            return answer.value, None
        return answer.value, with_arg(actions, "instance_id", ref)

    keep = Source("KeepIntrigueCard", Stage.PROMPT, actions, evaluate)
    return decide(run, [keep], skip=None, forced=True)


# ---------------------------------------------------------------------------
# conflict_end_trigger — Harvest Cells in the CombatResolution prompt
# ---------------------------------------------------------------------------


def _harvest_cells_evaluator(
    run: DecisionRun, instance: str, action: DomainAction, ability: IntrigueAbility
) -> Callable[[], tuple[float, DomainAction | None]]:
    def evaluate() -> tuple[float, DomainAction | None]:
        # The Combat-half request every Intrigue play of the card reads
        # (Harvest Cells: the Tleilaxu Row cards it could acquire).
        request = intrigue_request(run.ctx, instance, True)
        answer = ability.evaluate(run.profile, request)
        # As ``windows.intrigue`` records a play: the answer and the index
        # the play's ``intrigue_played`` event will take.
        run.memory.intents[(INTENT, instance)] = answer
        run.memory.intents[(INTENT_AT, instance)] = len(run.ctx.state.event_log)
        return answer.value, action

    return evaluate


def conflict_end_trigger(run: DecisionRun) -> DomainAction | None:
    """Play a Conflict-end Intrigue (Harvest Cells) or decline."""

    decline = run.first("decline_conflict_end_intrigue")
    sources: list[Source] = []
    for action in run.by_id("play_conflict_end_intrigue"):
        instance = str_arg(action, "card_id")
        if instance is None or not _known_intrigue(instance):
            return None
        ability = ability_for_prompt(intrigue_entity(instance, run.ctx.seat), True)
        if ability is None:
            # No Combat-turn ability to evaluate: a gap, not a decline.
            return None
        if not ability.can_be_run(run.profile):
            continue  # the app's ``Cost`` gate: no key
        sources.append(
            Source(
                label=f"intrigue {instance}",
                stage=Stage.PROMPT,
                actions=(action,),
                evaluate=_harvest_cells_evaluator(run, instance, action, ability),
            )
        )
    return decide(run, sources, skip=decline, forced=False)


HANDLERS: dict[str, Handler] = {
    "graft_partner": graft_partner,
    "research_advance": research_advance,
    "research_bonus": research_bonus,
    "optional_trash": optional_trash,
    "intrigue_peek": intrigue_peek,
    "conflict_end_trigger": conflict_end_trigger,
}
