"""Rise of Ix windows (docs/app-ai-plan.md §13): the Freighter and the
Shipping track's recall rewards.

- ``freighter_move``: a Freighter icon outside its owner's turn (a Conflict
  reward's, ``rules.shipping_track.freighter_move_frame``): the app's
  ``FreighterCustomAbility`` prompt, ``FreighterAbility::Evaluate`` --
  ``GetFreighterSelections(-1).Item1`` (1 recall, 0 advance) at
  ``FreighterValue`` (spec/rix-tech.md §4.6-4.7, §6.6). Explicit, so the app
  always answers; ``decline_freighter`` is never the app's answer.
- ``shipping_reward_icons``: a recall's rewards outside the owner's turn, one
  row each in any order (``resolve_shipping_reward``). The app's three
  Explicit sources: ``ShippingTrackAbility1`` (space 1: Dividends or spice by
  ``Item2`` of ``GetFreighterSelections(LastShippingRecallSpace)``, 100),
  ``ShippingTrackAbility2`` (space 2: ``GainAnyInfluenceAbility``, its
  Influence pick; our engine asks its recruit and its Influence as two rows,
  OQ-148, both this one answer) and ``ShippingTrackAbility3`` (space 3, 100),
  ranked by ``make_choice``.

``freighter_sources`` and ``shipping_sources`` are shared with the turn
window (``agent_effects``), where the same rows wait on the owner's turn.
"""

from collections.abc import Sequence

from dune_imperium.agents.app_ai.abilities.base import (
    Request,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.ix_board import (
    DREADNOUGHT_DETONATE,
    FREIGHTER_RECALL,
    SHIPPING_SOLARI,
    DreadnoughtControlAbility,
    FreighterAbility,
    FreighterCustomAbility,
    ShippingTrackAbility1,
    ShippingTrackAbility2,
    ShippingTrackAbility3,
)
from dune_imperium.agents.app_ai.abilities.ix_leaders import OneStepAheadRoundAbility
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    leader_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    decide,
    str_arg,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.dreadnoughts import space_controller

ADVANCE = "advance_freighter"
RECALL = "recall_freighter"
DECLINE = "decline_freighter"
REWARD = "resolve_shipping_reward"
_FREIGHTER_IDS = frozenset({ADVANCE, RECALL, DECLINE})
_REWARD_IDS = frozenset({REWARD})

#: The Shipping track space of each reward effect (``rules.shipping_track``):
#: space 1's choice, space 2's recruit and Influence, space 3's Tech.
_SPACE_OF_EFFECT = {"dividends": 1, "spice": 1, "recruit": 2, "influence": 2, "tech": 3}


def _track_owner(seat: int) -> Entity:
    """The entity a Shipping-track ability hangs off (no hook reads it)."""

    return Entity(Kind.SPACE, "shipping_track", None, seat)


def freighter_sources(
    run: DecisionRun,
    label: str,
    ability: FreighterAbility,
    advance: Sequence[DomainAction],
    recall: Sequence[DomainAction],
) -> list[Source]:
    """One PROMPT source for a Freighter icon: the app's answer realised by
    its advance or recall action (None when that move is not offered)."""

    actions = (*advance, *recall)
    if not actions:
        return []

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, Request())
        item = answer.response[0][0] if answer.response else None
        chosen = recall if item == FREIGHTER_RECALL else advance
        return answer.value, (chosen[0] if chosen else None)

    return [Source(label, Stage.PROMPT, actions, evaluate)]


def shipping_sources(run: DecisionRun, rows: Sequence[DomainAction]) -> list[Source]:
    """The Shipping track's three app sources over our reward rows."""

    seat = run.ctx.seat
    owner = _track_owner(seat)
    by_effect: dict[str, list[DomainAction]] = {}
    for row in rows:
        by_effect.setdefault(str_arg(row, "effect") or "", []).append(row)
    # ``LastShippingRecallSpace``: the highest space still owed. The app's
    # space 1 source ties its 100 with space 3's and comes first, so the
    # choice is made while every reward of the recall is owed.
    recalled = max((_SPACE_OF_EFFECT.get(e, 0) for e in by_effect), default=-1)
    sources: list[Source] = []
    choice_rows = (*by_effect.get("dividends", ()), *by_effect.get("spice", ()))
    if choice_rows:
        first = ShippingTrackAbility1(owner, recalled)

        def evaluate_first() -> tuple[float, DomainAction | None]:
            answer = first.evaluate(run.profile, Request())
            item = answer.response[0][0] if answer.response else None
            effect = "dividends" if item == SHIPPING_SOLARI else "spice"
            chosen = by_effect.get(effect)
            return answer.value, (chosen[0] if chosen else None)

        sources.append(
            Source("Shipping Track 1", Stage.PROMPT, choice_rows, evaluate_first)
        )
    recruit = by_effect.get("recruit", [])
    influence = by_effect.get("influence", [])
    if recruit or influence:
        second = ShippingTrackAbility2(owner)
        offered = {str_arg(row, "faction") for row in influence}
        tracks = tuple(track_entity(f) for f in FACTIONS if f in offered) or tuple(
            track_entity(f) for f in FACTIONS
        )

        def evaluate_second() -> tuple[float, DomainAction | None]:
            answer = second.evaluate(
                run.profile, Request(infos=(TargetInfo(entities=tracks),))
            )
            if recruit:  # the recruit row first: the same answer's first part
                return answer.value, recruit[0]
            faction = answer.response[0][0] if answer.response else None
            chosen = [row for row in influence if str_arg(row, "faction") == faction]
            return answer.value, (chosen[0] if chosen else None)

        sources.append(
            Source(
                "Shipping Track 2",
                Stage.PROMPT,
                (*recruit, *influence),
                evaluate_second,
            )
        )
    tech = by_effect.get("tech", [])
    if tech:
        third = ShippingTrackAbility3(owner)

        def evaluate_third() -> tuple[float, DomainAction | None]:
            return third.evaluate(run.profile, Request()).value, tech[0]

        sources.append(
            Source("Shipping Track 3", Stage.PROMPT, tuple(tech), evaluate_third)
        )
    return sources


def freighter_move(run: DecisionRun) -> DomainAction | None:
    """``freighter_move``: the Conflict reward's Freighter (see the module
    docstring)."""

    if any(a.action_id not in _FREIGHTER_IDS for a in run.legal):
        return None
    ability = FreighterCustomAbility(_track_owner(run.ctx.seat))
    sources = freighter_sources(
        run, "Freighter", ability, run.by_id(ADVANCE), run.by_id(RECALL)
    )
    return decide(run, sources, skip=run.first(DECLINE), forced=True)


def shipping_reward_icons(run: DecisionRun) -> DomainAction | None:
    """``shipping_reward_icons``: a recall's rewards outside the turn."""

    if any(a.action_id not in _REWARD_IDS for a in run.legal):
        return None
    return decide(run, shipping_sources(run, run.legal), skip=None, forced=True)


_PLACE_DREADNOUGHT = "place_combat_reward_dreadnought"
_DETONATE_DREADNOUGHT = "detonate_combat_reward_dreadnought"


def dreadnought_control_choice(run: DecisionRun) -> DomainAction | None:
    """``dreadnought_control_choice``: the app's ``DreadnoughtControlAbility``
    prompt (Explicit) over the offered Control spaces, and Detonation
    Devices' VP when offered (``abilities/ix_board.py``)."""

    ids = {_PLACE_DREADNOUGHT, _DETONATE_DREADNOUGHT}
    if any(a.action_id not in ids for a in run.legal):
        return None
    places = run.by_id(_PLACE_DREADNOUGHT)
    detonate = run.first(_DETONATE_DREADNOUGHT)
    state = run.ctx.state
    spaces = [str_arg(a, "space_id") for a in places]
    entities = tuple(space_entity(s, run.ctx.board) for s in spaces if s is not None)
    ability = DreadnoughtControlAbility(
        _track_owner(run.ctx.seat),
        {e.ref: space_controller(state, e.ref) for e in entities},
    )

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(
            run.profile, Request(infos=(TargetInfo(entities=entities),))
        )
        if not answer.response:
            return answer.value, None
        if answer.response[0][0] == DREADNOUGHT_DETONATE:
            return answer.value, detonate
        ref = answer.response[1][0] if len(answer.response) > 1 else None
        chosen = [a for a in places if str_arg(a, "space_id") == ref]
        return answer.value, (chosen[0] if chosen else None)

    source = Source("Dreadnought Control", Stage.PROMPT, tuple(run.legal), evaluate)
    return decide(run, [source], skip=None, forced=True)


_PUT_BOTTOM = "put_intrigue_on_bottom"
_FINISH_BOTTOM = "finish_intrigue_bottom"


def intrigue_bottom_pick(run: DecisionRun) -> DomainAction | None:
    """``intrigue_bottom_pick``: Sonic Snoopers' "put any number of your
    Intrigue cards on the bottom, then draw that many", asked one card at a
    time. The app answers at once: ``SonicSnoopersAbility::Evaluate``
    @0x4de2840 names the bad Intrigue cards in hand
    (``bad_intrigue_cards_in_hand``, in that order). So each pick puts the
    next of them still in hand, and the pick ends when none is left (the
    draw comes after, so the hand only shrinks meanwhile)."""

    ids = {_PUT_BOTTOM, _FINISH_BOTTOM}
    if any(a.action_id not in ids for a in run.legal):
        return None
    puts = {str_arg(a, "card_id"): a for a in run.by_id(_PUT_BOTTOM)}
    for card in run.profile.bad_intrigue_cards_in_hand():
        if card.ref in puts:
            return puts[card.ref]
    return run.first(_FINISH_BOTTOM)


UNLOAD = "resolve_unload_icon"


def take_unload(run: DecisionRun) -> DomainAction | None:
    """The first owed Unload icon (``resolve_unload_icon``): the app's
    ``UnloadAbility`` family is Triggered with no AI hook, so the engine
    resolves the box without asking; its icons are taken in order."""

    rows = run.by_id(UNLOAD)
    return rows[0] if rows else None


def unload_icons(run: DecisionRun) -> DomainAction | None:
    """``unload_icons``: an Unload box gained outside its owner's turn."""

    if any(a.action_id != UNLOAD for a in run.legal):
        return None
    return take_unload(run)


_SET_ASIDE = "set_aside_leader_card"


def round_start_set_aside(run: DecisionRun) -> DomainAction | None:
    """Ilesa Ecaz's One Step Ahead at Round Start: the hand card
    ``OneStepAheadRoundAbility::Evaluate`` sets aside (a forced
    ``KeepCard`` prompt over the hand, ``<Targets>d__7`` @0x4b01d90); an
    empty answer is ``DefaultRandomChoice``."""

    actions = run.by_id(_SET_ASIDE)
    me = run.ctx.me
    if not actions or len(actions) != len(run.legal) or me.leader_id is None:
        return None
    ability = next(
        (
            a
            for a in abilities_of(leader_entity(me.leader_id, me.leader_face_id))
            if isinstance(a, OneStepAheadRoundAbility)
        ),
        None,
    )
    if ability is None:
        return None
    seat = run.ctx.seat
    refs = [ref for a in actions if (ref := str_arg(a, "card_id")) is not None]
    hand = tuple(card_entity(ref, seat) for ref in refs)
    request = Request((TargetInfo(entities=hand),), forced=True)

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, request)
        ref = answer.response[0][0] if answer.response and answer.response[0] else None
        chosen = next((a for a in actions if str_arg(a, "card_id") == ref), None)
        return answer.value, chosen

    source = Source("One Step Ahead", Stage.PROMPT, actions, evaluate)
    return decide(run, [source], skip=None, forced=True)


HANDLERS: dict[str, Handler] = {
    "unload_icons": unload_icons,
    "round_start_set_aside": round_start_set_aside,
    "dreadnought_control_choice": dreadnought_control_choice,
    "intrigue_bottom_pick": intrigue_bottom_pick,
    "freighter_move": freighter_move,
    "shipping_reward_icons": shipping_reward_icons,
}
