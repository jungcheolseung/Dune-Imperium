"""The Arrakeen Scouts decision windows (app-style extension).

``scouts_choice``, ``scouts_effect``, ``scouts_subcommittee``,
``scouts_mission``, ``scouts_secret``, ``scouts_bid``, ``scouts_retreat``,
``scouts_call``, ``scouts_market``, ``scouts_four_bonus``; plus
``scouts_trash_source``, which the ``optional_trash`` window
(``windows/immortality.py``) asks for the Scouts trash icon (Oversight,
Water Discipline).

The app has no Arrakeen Scouts, so every answer here is the app-style
extension of docs/app-ai-plan.md §11 (§11.4 decision rules, §11.5 "Arrakeen
Scouts", §11.7, §11.8) as docs/app-ai/scouts.md §3 applies it. Each window
calls the evaluator or line ability the ability stage ported
(``abilities/scouts.py``; values from ``profile/scouts.py`` and the existing
profile prices) and maps its answer to one of our legal actions. Every
evaluator draws its randomness from the profile RNG, which is the agent's
seeded RNG (``run.rng``).

``HANDLERS`` maps each decision kind this module answers to its handler; a
handler returning None makes the agent answer at random
(``DefaultRandomChoice``) and count a fallback. A Scouts item, line, card or
Intrigue card this module has no archetype for, a step it does not know, or
a legal action id outside a window's own ids returns None (never a silent
default).

- ``scouts_choice`` (§3.1): ``ScoutsChoiceEvaluator`` over the offered lines
  (``scouts_choose_option``). Passable (a ``scouts_pass`` is legal: every
  sale, the passable events, Rebuild Infrastructure, a revealed secret pick's
  only line): ``mc``, the empty answer passes. Mandatory: ``mc``; no
  positive line -> least loss for the Influence Reduction family, else
  ``DefaultRandomChoice``. Rebuild Infrastructure is priced by its line
  (``Spi(-1) - BWV``), so the seat always passes (computed, not hard-coded).
- ``scouts_effect`` (§3.2): the current step of the line being resolved
  (frame context ``item``, ``option``, ``step``) is answered by the
  ``Evaluate`` of the line ability that owns it, looked up on the line's
  archetype (``catalog.scouts_line_entity``): discard ->
  ``DiscardCostAbility``, mandatory hand trash -> ``TrashFromHandCostAbility``,
  Intrigue trash -> ``TrashIntrigueCostAbility``, Spy recall ->
  ``RecallSpyCostAbility``, any Faction -> ``GainAnyInfluenceAgentAbility``,
  lowest Faction tie -> ``GainLowestInfluenceAbility``, other Agent ->
  ``RecallAgentAbility``, highest-track tie -> ``LoseHighestInfluenceAbility``
  (least loss); a named Faction's loss (``LoseFactionInfluence``) asks only
  the Alliance recipient. A loss split by Alliance recipient takes the
  **first** offered action of the chosen Faction (plan §11.5, D17). A
  recruit with a short supply (Immortality) returns the largest offered
  specimen count (``line_top_up_answer``, D39). No value threshold: the line
  was taken already, so the step's answer is used whatever its sign.
- ``scouts_subcommittee`` (§3.3): the subcommittee the turn-frame prompt
  chose (``Memory.intents[(SUBCOMMITTEE_INTENT, round, seat)]``, written by
  the ``agent_effects`` / ``reveal`` windows that answer
  ``choose_subcommittee``; dropped once read) when it is still joinable;
  otherwise ``SubcommitteeEvaluator`` over the joinable subcommittees
  (``mc``), the empty answer declines. Not forced.
- ``scouts_mission`` (§3.4): ``MissionJoinEvaluator`` over the join targets,
  with the specimen top-up way when one is offered (its largest count). The
  top-up and the join are one app answer that our engine asks in two steps,
  so a top-up leaves the troop target in
  ``Memory.intents[(MISSION_JOIN_INTENT, round, mission, seat)]`` and the
  next ``scouts_mission`` decision joins with it (plan §4 rule 6). The empty
  answer declines.
- ``scouts_secret`` (§3.6): ``SecretPickEvaluator`` (forced).
- ``scouts_bid`` (§3.7): ``SealedBidEvaluator`` (``MercenariesBidEvaluator``
  for Mercenaries) at both steps: own bid == ``b*`` -> confirm, else
  ``scouts_bid(b*)``. The evaluator is deterministic (its prices do not
  depend on the RNG), so the two decisions agree without an intent.
- ``scouts_retreat`` (§3.8): ``MercenariesRetreatEvaluator``
  (``GetTroopsToRetreat`` over the largest legal count).
- ``scouts_call`` (§3.9): ``CriticalMomentCallEvaluator`` (0 = pass).
- ``scouts_market`` (§3.10): ``CriticalMomentTakeEvaluator``; the second
  place's empty answer declines.
- ``scouts_four_bonus`` (§3.11): ``FourBonusEvaluator`` (forced).
- Section 3.12's automatic items leave their choices in these windows
  (Political Equilibrium's ties in ``scouts_effect``, Rebuild Infrastructure
  in ``scouts_choice``, a revealed secret pick's cost line in
  ``scouts_choice``, Mercenaries' retreat in ``scouts_retreat``, a recruit's
  top-up in ``scouts_effect`` / ``scouts_mission``); section 3.13's existing
  windows (``spy_placement``, ``contract_market``, ``research_advance``,
  ``acquisition_spy``, ``optional_trash``) keep their own handlers, reached
  by decision kind whatever opened them.

Judgements (no exact precedent in the spec):

- ``scouts_effect``'s ``LoseFactionInfluence`` step needs no Evaluate: the
  Faction is printed and only the Alliance recipient is asked, answered with
  the first offered action (D17).
- ``scouts_mission``'s top-up intent: the spec says only that "after a
  top-up the frame asks again and the join is legal"; the intent makes the
  second decision the first one's answer instead of a fresh ``mc`` (whose
  shuffle could pick another target among equal values).
- ``scouts_trash_source``: the line's own ``TrashCustomAbility`` answers the
  Scouts trash icon; its ``Evaluate`` is the generic ``TrashAbility`` one, so
  the pick equals the generic optional-trash answer.
"""

from collections.abc import Sequence
from typing import Final

from dune_imperium.agents.app_ai.abilities import abilities_of
from dune_imperium.agents.app_ai.abilities import scouts as sc
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    TargetInfo,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    GainAnyInfluenceAbility,
    RecallAgentAbility,
    TrashCustomAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    SCOUTS_LINE_ARCHETYPES,
    agent_entity,
    card_entity,
    intrigue_entity,
    scouts_line_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import card_id
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.windows.common import int_arg, str_arg, with_arg
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    SUBCOMMITTEES_BY_ID,
    AuctionKind,
    MissionKind,
)
from dune_imperium.content.arrakeen_scouts.types import (
    GainLowestInfluence,
    LoseFactionInfluence,
    LoseHighestInfluence,
    RecallOtherAgent,
    RecruitToConflict,
)
from dune_imperium.content.uprising.effect_dsl import (
    DiscardFromHand,
    GainInfluence,
    RecallSpy,
    RecruitTroops,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.scouts_effects import option_steps, scouts_option

#: ``Memory.intents`` keys. ``(SUBCOMMITTEE_INTENT, round, seat) ->
#: subcommittee id`` (or the ``Answer`` naming it) is written by the windows
#: that answer ``choose_subcommittee`` (scouts.md §3.3) and read here;
#: ``(MISSION_JOIN_INTENT, round, mission id, seat) -> join target`` is
#: written and read here.
SUBCOMMITTEE_INTENT: Final = "subcommittee"
MISSION_JOIN_INTENT: Final = "scouts_mission_join"

_CHOICE_IDS: Final = frozenset({"scouts_choose_option", "scouts_pass"})
_SUBCOMMITTEE_IDS: Final = frozenset({"join_subcommittee", "decline_subcommittee"})
_MISSION_IDS: Final = frozenset(
    {"scouts_join_mission", "scouts_decline_mission", "scouts_return_specimens"}
)
_BID_IDS: Final = frozenset({"scouts_bid", "confirm_scouts_bid"})
_MARKET_IDS: Final = frozenset({"scouts_take_card", "scouts_decline_card"})
_LOSS_IDS: Final = frozenset({"scouts_lose_influence", "scouts_lose_influence_to"})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _only(run: DecisionRun, ids: frozenset[str]) -> bool:
    """Whether every legal action is one of the window's own ids."""

    return all(action.action_id in ids for action in run.legal)


def _first_ref(answer: Answer) -> str | int | None:
    """The one target an answer names (``((ref,),)``), if any."""

    if not answer.response or not answer.response[0]:
        return None
    return answer.response[0][0]


def _context_str(run: DecisionRun, name: str) -> str | None:
    value = run.ctx.top_frame_context.get(name)
    return value if isinstance(value, str) else None


def _context_int(run: DecisionRun, name: str) -> int | None:
    value = run.ctx.top_frame_context.get(name)
    return value if type(value) is int else None


def _has_line(item_id: str, line: int) -> bool:
    return f"{item_id}:{line}" in SCOUTS_LINE_ARCHETYPES


def _ints(actions: Sequence[DomainAction], name: str) -> list[int]:
    return [value for a in actions if (value := int_arg(a, name)) is not None]


def _strs(actions: Sequence[DomainAction], name: str) -> list[str]:
    return [value for a in actions if (value := str_arg(a, name)) is not None]


def _request(entities: Sequence[Entity]) -> Request:
    """A forced one-of-N prompt over ``entities`` (one target info)."""

    info = TargetInfo(entities=tuple(entities), min_select=1, max_select=1, forced=True)
    return Request(infos=(info,), forced=True)


def _line_ability[A: Ability](line: Entity, cls: type[A]) -> A | None:
    """The first ability of class ``cls`` on the line (archetype order)."""

    for ability in abilities_of(line):
        if isinstance(ability, cls):
            return ability
    return None


def _answer_action(
    answer: Answer, actions: Sequence[DomainAction], name: str
) -> DomainAction | None:
    """The action whose argument ``name`` is the target the answer names."""

    ref = _first_ref(answer)
    return None if ref is None else with_arg(actions, name, ref)


# ---------------------------------------------------------------------------
# scouts_choice — ScoutsChoiceEvaluator (§3.1)
# ---------------------------------------------------------------------------


def scouts_choice(run: DecisionRun) -> DomainAction | None:
    """An event's or sale's lines, Rebuild Infrastructure or a revealed
    secret pick's only line: ``ScoutsChoiceEvaluator``."""

    if not _only(run, _CHOICE_IDS):
        return None
    item = _context_str(run, "item")
    chooses = run.by_id("scouts_choose_option")
    lines = _ints(chooses, "option")
    if item is None or len(lines) != len(chooses):
        return None
    if not all(_has_line(item, line) for line in lines):
        return None
    passed = run.first("scouts_pass")
    answer = sc.ScoutsChoiceEvaluator.evaluate(
        run.profile, item, lines, passable=passed is not None
    )
    if answer.response is None:
        return passed
    return _answer_action(answer, chooses, "option")


# ---------------------------------------------------------------------------
# scouts_effect — the line ability that owns the step (§3.2)
# ---------------------------------------------------------------------------


def _current_step(run: DecisionRun) -> tuple[Entity, object] | None:
    """The line being resolved (its entity) and its current step."""

    item = _context_str(run, "item")
    option = _context_int(run, "option")
    step = _context_int(run, "step")
    if item is None or option is None or step is None:
        return None
    if not _has_line(item, option):
        return None
    try:
        steps = option_steps(scouts_option(item, option))
    except KeyError, IndexError, ValueError:
        return None
    if not 0 <= step < len(steps):
        return None
    return scouts_line_entity(item, option, run.ctx.seat), steps[step]


def _pick(
    run: DecisionRun,
    line: Entity,
    cls: type[Ability],
    action_id: str,
    name: str,
    entities: Sequence[Entity],
) -> DomainAction | None:
    """The step's actions answered by the line ability ``cls``'s Evaluate
    over ``entities`` (the offered targets, in legal order)."""

    actions = run.by_id(action_id)
    if len(actions) != len(run.legal):
        return None
    ability = _line_ability(line, cls)
    if ability is None:
        return None
    answer = ability.evaluate(run.profile, _request(entities))
    return _answer_action(answer, actions, name)


def _loss(run: DecisionRun, faction: str | None) -> DomainAction | None:
    """The first offered loss of ``faction`` (the Alliance recipient tie:
    plan §11.5, D17)."""

    if faction is None:
        return None
    for action in run.legal:
        if str_arg(action, "faction") == faction:
            return action
    return None


def scouts_effect(run: DecisionRun) -> DomainAction | None:
    """One choice step of a taken line, answered by its line ability."""

    current = _current_step(run)
    if current is None:
        return None
    line, step = current
    seat = run.ctx.seat
    match step:
        case DiscardFromHand():
            refs = _strs(run.by_id("scouts_discard"), "card_id")
            if not all(card_id(ref) in CARD_ARCHETYPES for ref in refs):
                return None
            cards = [card_entity(ref, seat) for ref in refs]
            return _pick(
                run, line, sc.DiscardCostAbility, "scouts_discard", "card_id", cards
            )
        case TrashPersonalCard(mandatory=True):
            refs = _strs(run.by_id("scouts_trash_card"), "card_id")
            if not all(card_id(ref) in CARD_ARCHETYPES for ref in refs):
                return None
            cards = [card_entity(ref, seat) for ref in refs]
            return _pick(
                run,
                line,
                sc.TrashFromHandCostAbility,
                "scouts_trash_card",
                "card_id",
                cards,
            )
        case TrashIntrigueCard():
            refs = _strs(run.by_id("scouts_trash_intrigue"), "card_id")
            if not all(card_id(ref) in INTRIGUE_ARCHETYPES for ref in refs):
                return None
            intrigues = [intrigue_entity(ref, seat) for ref in refs]
            return _pick(
                run,
                line,
                sc.TrashIntrigueCostAbility,
                "scouts_trash_intrigue",
                "card_id",
                intrigues,
            )
        case RecallSpy():
            posts = _strs(run.by_id("scouts_recall_spy"), "post_id")
            spies = [spy_entity(post, seat) for post in posts]
            return _pick(
                run,
                line,
                sc.RecallSpyCostAbility,
                "scouts_recall_spy",
                "post_id",
                spies,
            )
        case GainInfluence():
            factions = _strs(run.by_id("scouts_choose_faction"), "faction")
            tracks = [track_entity(f) for f in factions]
            return _pick(
                run,
                line,
                GainAnyInfluenceAbility,
                "scouts_choose_faction",
                "faction",
                tracks,
            )
        case GainLowestInfluence():
            factions = _strs(run.by_id("scouts_choose_faction"), "faction")
            tracks = [track_entity(f) for f in factions]
            return _pick(
                run,
                line,
                sc.GainLowestInfluenceAbility,
                "scouts_choose_faction",
                "faction",
                tracks,
            )
        case RecallOtherAgent():
            spaces = _strs(run.by_id("scouts_recall_agent"), "space_id")
            agents = [agent_entity(space, seat) for space in spaces]
            return _pick(
                run,
                line,
                RecallAgentAbility,
                "scouts_recall_agent",
                "space_id",
                agents,
            )
        case LoseFactionInfluence(faction=faction):
            if not _only(run, _LOSS_IDS):
                return None
            return _loss(run, faction.value)
        case LoseHighestInfluence():
            if not _only(run, _LOSS_IDS):
                return None
            if _line_ability(line, sc.LoseHighestInfluenceAbility) is None:
                return None
            factions = list(dict.fromkeys(_strs(run.legal, "faction")))
            answer = sc.lose_influence_answer(run.profile, factions)
            ref = _first_ref(answer)
            return _loss(run, ref if isinstance(ref, str) else None)
        case RecruitTroops() | RecruitToConflict():
            top_ups = run.by_id("scouts_return_specimens")
            if len(top_ups) != len(run.legal):
                return None
            answer = sc.line_top_up_answer(_ints(top_ups, "count"))
            return _answer_action(answer, top_ups, "count")
    return None


# ---------------------------------------------------------------------------
# scouts_subcommittee — the turn prompt's pick, else SubcommitteeEvaluator (§3.3)
# ---------------------------------------------------------------------------


def _intended_subcommittee(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Answer):
        ref = _first_ref(value)
        return ref if isinstance(ref, str) else None
    return None


def scouts_subcommittee(run: DecisionRun) -> DomainAction | None:
    """Join one joinable subcommittee or decline."""

    if not _only(run, _SUBCOMMITTEE_IDS):
        return None
    joins = run.by_id("join_subcommittee")
    joinable = _strs(joins, "subcommittee_id")
    if len(joinable) != len(joins):
        return None
    if not all(s in SUBCOMMITTEES_BY_ID and _has_line(s, 0) for s in joinable):
        return None
    decline = run.first("decline_subcommittee")
    key = (SUBCOMMITTEE_INTENT, run.ctx.round_number, run.ctx.seat)
    intended = _intended_subcommittee(run.memory.intents.pop(key, None))
    if intended is not None:
        stored = with_arg(joins, "subcommittee_id", intended)
        if stored is not None:
            return stored
    answer = sc.SubcommitteeEvaluator.evaluate(run.profile, joinable)
    if answer.response is None:
        return decline
    return _answer_action(answer, joins, "subcommittee_id")


# ---------------------------------------------------------------------------
# scouts_mission — MissionJoinEvaluator (§3.4)
# ---------------------------------------------------------------------------


def _troop_target(mission_id: str) -> str:
    """The join target of the troop way a specimen top-up supplies."""

    if MISSIONS_BY_ID[mission_id].kind is MissionKind.CHOAM_ESCORT:
        return "recruit"
    return ""


def scouts_mission(run: DecisionRun) -> DomainAction | None:
    """Take part in a mission (or top up specimens first), or decline."""

    if not _only(run, _MISSION_IDS):
        return None
    mission_id = _context_str(run, "mission_id")
    if mission_id is None or mission_id not in MISSIONS_BY_ID:
        return None
    joins = run.by_id("scouts_join_mission")
    top_ups = run.by_id("scouts_return_specimens")
    targets = _strs(joins, "target")
    counts = _ints(top_ups, "count")
    if len(targets) != len(joins) or len(counts) != len(top_ups):
        return None
    lines = {sc.mission_join_line(mission_id, t) for t in targets}
    if counts:
        lines.add(sc.mission_join_line(mission_id, _troop_target(mission_id)))
    if not all(_has_line(mission_id, line) for line in lines):
        return None
    key = (MISSION_JOIN_INTENT, run.ctx.round_number, mission_id, run.ctx.seat)
    intended = run.memory.intents.pop(key, None)
    if isinstance(intended, str):
        stored = with_arg(joins, "target", intended)
        if stored is not None:
            return stored
    answer = sc.MissionJoinEvaluator.evaluate(
        run.profile, mission_id, targets, max(counts, default=0)
    )
    if answer.response is None:
        return run.first("scouts_decline_mission")
    action_id, value = answer.response[0][0], answer.response[0][1]
    if action_id == "scouts_join_mission":
        return with_arg(joins, "target", value)
    if action_id == "scouts_return_specimens":
        chosen = with_arg(top_ups, "count", value)
        if chosen is not None:
            run.memory.intents[key] = _troop_target(mission_id)
        return chosen
    return None


# ---------------------------------------------------------------------------
# scouts_secret — SecretPickEvaluator (§3.6)
# ---------------------------------------------------------------------------


def scouts_secret(run: DecisionRun) -> DomainAction | None:
    """Covert / Offworld Operation's secret pick (forced)."""

    picks_actions = run.by_id("scouts_secret_pick")
    if len(picks_actions) != len(run.legal):
        return None
    event_id = _context_str(run, "event_id")
    picks = _ints(picks_actions, "pick")
    if event_id is None or event_id not in EVENTS_BY_ID:
        return None
    choices = EVENTS_BY_ID[event_id].secret_choices
    if not all(0 <= p < len(choices) and _has_line(event_id, p) for p in picks):
        return None
    answer = sc.SecretPickEvaluator.evaluate(run.profile, event_id, picks)
    return _answer_action(answer, picks_actions, "pick")


# ---------------------------------------------------------------------------
# scouts_bid — SealedBidEvaluator / MercenariesBidEvaluator (§3.7)
# ---------------------------------------------------------------------------


def scouts_bid(run: DecisionRun) -> DomainAction | None:
    """The two-step sealed bid: bid ``b*``, then confirm it."""

    if not _only(run, _BID_IDS):
        return None
    auction_id = _context_str(run, "auction_id")
    if auction_id is None or auction_id not in AUCTIONS_BY_ID:
        return None
    bids = run.by_id("scouts_bid")
    counts = _ints(bids, "count")
    if len(counts) != len(bids):
        return None
    cap = max(counts, default=0)
    kind = AUCTIONS_BY_ID[auction_id].kind
    if kind is AuctionKind.MERCENARIES:
        answer = sc.MercenariesBidEvaluator.evaluate(run.profile, cap)
    elif kind is AuctionKind.SEALED and _has_line(auction_id, 0):
        answer = sc.SealedBidEvaluator.evaluate(run.profile, auction_id, cap)
    else:
        return None
    if answer.response is None:
        return None
    item = answer.response[0]
    if item[0] == "confirm_scouts_bid":
        return run.first("confirm_scouts_bid")
    if item[0] == "scouts_bid" and len(item) > 1:
        return with_arg(bids, "count", item[1])
    return None


# ---------------------------------------------------------------------------
# scouts_retreat, scouts_call, scouts_market, scouts_four_bonus (§3.8-3.11)
# ---------------------------------------------------------------------------


def scouts_retreat(run: DecisionRun) -> DomainAction | None:
    """Mercenaries' lowest bidder: ``MercenariesRetreatEvaluator``."""

    actions = run.by_id("scouts_retreat")
    counts = _ints(actions, "count")
    if len(actions) != len(run.legal) or len(counts) != len(actions):
        return None
    answer = sc.MercenariesRetreatEvaluator.evaluate(run.profile, max(counts))
    return _answer_action(answer, actions, "count")


def _market_known(run: DecisionRun) -> bool:
    """Every revealed Critical Moment card has an archetype."""

    return all(card_id(c) in CARD_ARCHETYPES for c in run.ctx.scouts_market_cards)


def scouts_call(run: DecisionRun) -> DomainAction | None:
    """Critical Moment's open call: ``CriticalMomentCallEvaluator``."""

    actions = run.by_id("scouts_call")
    amounts = _ints(actions, "count")
    if len(actions) != len(run.legal) or len(amounts) != len(actions):
        return None
    if not _market_known(run):
        return None
    answer = sc.CriticalMomentCallEvaluator.evaluate(run.profile, amounts)
    return _answer_action(answer, actions, "count")


def scouts_market(run: DecisionRun) -> DomainAction | None:
    """Critical Moment's winner (forced) or second place (may decline):
    ``CriticalMomentTakeEvaluator``."""

    if not _only(run, _MARKET_IDS):
        return None
    amount = _context_int(run, "amount")
    place = _context_int(run, "place")
    takes = run.by_id("scouts_take_card")
    slots = _ints(takes, "slot")
    if amount is None or place is None or len(slots) != len(takes):
        return None
    market = run.ctx.scouts_market_cards
    if not _market_known(run) or not all(0 <= s < len(market) for s in slots):
        return None
    answer = sc.CriticalMomentTakeEvaluator.evaluate(run.profile, slots, amount, place)
    if answer.response is None:
        return run.first("scouts_decline_card")
    return _answer_action(answer, takes, "slot")


def scouts_four_bonus(run: DecisionRun) -> DomainAction | None:
    """Friends Everywhere: ``FourBonusEvaluator`` (forced)."""

    actions = run.by_id("choose_four_bonus")
    factions = _strs(actions, "faction")
    if len(actions) != len(run.legal) or len(factions) != len(actions):
        return None
    answer = sc.FourBonusEvaluator.evaluate(run.profile, factions)
    return _answer_action(answer, actions, "faction")


# ---------------------------------------------------------------------------
# The Scouts trash icon (optional_trash; scouts.md §3.13, O2)
# ---------------------------------------------------------------------------


def scouts_trash_source(
    run: DecisionRun, source: str
) -> tuple[bool, TrashCustomAbility | None]:
    """Whether the ``optional_trash`` frame granted by ``source`` is a Scouts
    line's trash icon (Oversight, Water Discipline), and that line's
    ``TrashCustomAbility``.

    The icon is the step just passed of this seat's open ``scouts_effect``
    frame: the engine opens it with ``source = "<line source>:<step>"``
    (``rules/scouts_effects.py`` ``advance_scouts_effect``). ``(True,
    None)``: a Scouts line opened it but the line has no such ability (the
    caller falls back). ``(False, None)``: another source; always so without
    the ``arrakeen_scouts`` option.
    """

    if not run.ctx.scouts:
        return False, None
    effect = run.ctx.own_frame_context("scouts_effect")
    if effect is None:
        return False, None
    effect_source = effect.get("source")
    item = effect.get("item")
    option = effect.get("option")
    step = effect.get("step")
    if not (
        isinstance(effect_source, str)
        and isinstance(item, str)
        and type(option) is int
        and type(step) is int
    ):
        return False, None
    if source != f"{effect_source}:{step - 1}":
        return False, None
    if not _has_line(item, option):
        return True, None
    try:
        steps = option_steps(scouts_option(item, option))
    except KeyError, IndexError, ValueError:
        return True, None
    if not 0 <= step - 1 < len(steps):
        return True, None
    trash_step = steps[step - 1]
    if not isinstance(trash_step, TrashPersonalCard) or trash_step.mandatory:
        return True, None
    line = scouts_line_entity(item, option, run.ctx.seat)
    return True, _line_ability(line, TrashCustomAbility)


HANDLERS: dict[str, Handler] = {
    "scouts_choice": scouts_choice,
    "scouts_effect": scouts_effect,
    "scouts_subcommittee": scouts_subcommittee,
    "scouts_mission": scouts_mission,
    "scouts_secret": scouts_secret,
    "scouts_bid": scouts_bid,
    "scouts_retreat": scouts_retreat,
    "scouts_call": scouts_call,
    "scouts_market": scouts_market,
    "scouts_four_bonus": scouts_four_bonus,
}
