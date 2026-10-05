"""The ``reveal``, ``reveal_choice`` and ``acquisition_spy`` windows.

The app's Reveal turn (spec ``engine-order.md`` §5, ``12-turn-structure.md``
§4) asks the AI one thing: the post-reveal prompt of
``PlayerTurnPhase/<ResolveDeferredAbilities>d__15::MoveNext @0x4a1f490`` with
``turnType = Reveal``. Before it, ``RevealTurnPhase`` reveals the whole hand,
runs every card's plain ``RevealAbility`` in active-card order (state 300,
``<ResolveRevealAbilities>d__14 @0x4a29360``: no question) and the deferred
abilities that ``CanRunImmediately`` (state 400,
``<ResolveImmediateDeferredAbilities>d__15 @0x4a28ec0``). The prompt then
lists, from ``WormPlaymat::GetUsableDeferredAbilities @0x49ae890``: the
Optional/Explicit Reveal-or-None deferred abilities of the revealed cards
(the card choices), Plots, leader abilities with Reveal timing, the custom
abilities (the Emperor-track Spy) and the ``AcquireAbility`` of every
affordable Imperium Row / Reserve / set-aside card. ``MakeChoice`` answers the
best key worth more than 0; every answer re-issues the prompt; the empty
answer (End Turn) exists only while no Explicit ability is pending, and a
forced prompt with nothing positive goes to ``DefaultRandomChoice`` over the
whole list.

Our engine splits the same turn (scratchpad R2): one ``reveal_choice`` frame
per card choice is pushed above the ``reveal`` frame, the automatic gains wait
on the ``reveal`` frame as owner actions, and the turn ends with an explicit
``finish_reveal``. This adapter rebuilds the app's order:

1. **``reveal_choice``: defer first.** An initial (deferrable) choice frame is
   always answered with ``defer_reveal_choice``: in the app no card choice is
   asked before the automatic gains have run and every choice competes by
   value with the buys in the post-reveal prompt. Exceptions: a choice whose
   ability ``CanRunImmediately`` (Corrinth City when already seated) is
   answered at once, like the app's state-400 run; a frame that cannot be
   deferred (resumed, or a Spy already recalled for it) is answered.
2. **``reveal``: automatic gains first** (``Stage.REVEAL_AUTO``):
   ``recruit_reveal_troops``, ``draw_reveal_intrigue``,
   ``gain_reveal_resources`` (and a non-Shishakli
   ``gain_reveal_faction_influence``) are taken in the app's order: state 300
   printed reveal gains before state 400 immediates (Treacherous Maneuver's
   ``RevealGainIntrigueAbility``, ``SmugglersHavenRevealAbility``), each by
   its source card's reveal position. No AI decision depends on this order.
3. **``reveal``: the post-reveal prompt** over PROMPT sources: one per buyable
   card (its ``AcquireAbility.Evaluate`` = ``AcquireValue``, zeroed below
   ``MinimumAcquireValue``; the economy port's ``reserve:<card_id>`` refs are
   our ``acquire_reserve(card_id)``), one per Plot (``intrigue_play_sources``),
   one per deferred choice kind (``resume_reveal_choice(effect)``, valued by
   that card's choice ability), Shishakli's Fremen Influence
   (``CrysknifeAbility``: Explicit, DeferValue 2), Feyd's Devious Strength and
   Amber's Desert Scouts (only while their app ``Cost`` holds) and the
   Emperor-track Spy (``place_track_spy``: ``PlaceSpyCustomAbility``, Explicit,
   ``SpyValue``). The skip is ``finish_reveal``. When it is not legal and no
   Explicit key blocks it, the app would end the turn: the adapter resumes the
   first Optional blocker to decline it (intent ``"decline"``) and marks the
   End Turn in ``run.memory.data`` (``_END_TURN``); the next Reveal decisions
   decline the other Optional blockers and take ``finish_reveal`` without
   evaluating or shuffling again (the app's single empty answer, 12 §4.3).
   When an Explicit key blocks it, the prompt is forced (``decide``'s random
   fallback).
4. **Intents.** A resumed choice comes back on top of the stack; the answer
   computed for its key is stored in ``run.memory.intents`` under
   ``("reveal_choice", round, effect)`` and consumed at that frame (an
   ``Answer``, ``"decline"`` or ``"random"`` for the forced random pick). A
   resumed frame with a single legal action never reaches the handler, so the
   Reveal window drops any such intent left behind. A resumed frame without
   an intent is answered as ``MakeChoice`` would: its value > 0 uses it, else
   an Optional choice declines and an Explicit one (forced) is random.
5. **``acquisition_spy``**: ``spy_answer`` (best post; with an empty supply
   recall the worst-post Spy first; never decline).
6. **Immortality** (``spec/immortality.md`` §3.4-§3.6, §5, §8):
   ``generate_reveal_specimens`` is a state-300 gain, and state 300 runs the
   cards with a printed specimen first (``OrderByDescending(Specimens)``);
   Bene Tleilax Lab's spice is a state-400 immediate. Tleilaxu Master's
   Research icons (``GainResearchRevealAbility`` x2), Dissecting Kit's
   Tleilaxu step (``DissectingKitRevealAbility``) and Throne Room Politics'
   Bene Gesserit Influence (``InTheShadowsRevealAbility``) are Explicit
   prompt keys (one per icon) that force the prompt; a research key's
   answer names the space (``intrigue.RESEARCH_INTENT`` for the
   ``research_advance`` window). New keys: each affordable Tleilaxu Row card
   (``AcquireAbility``, with the ``ChooseAcquireTleilaxuLocation`` picker
   once P has a genetic marker: option 0, our ``to_deck_top`` variant),
   Reclaimed Forces (``ReclaimedForcesAcquireAbility``: 0 two troops, 1 a
   Tleilaxu step), Family Atomics and Return Specimen (playmat; one Return
   Specimen answer returns the whole troop shortfall, which our engine takes
   one ``return_specimen`` at a time: ``_RETURN_BATCH``). The Reveal
   choices of For Humanity, Shadout Mapes and Tleilaxu Surgeon are deferred
   and valued like the Uprising ones.

Judgements (our engine vs the app):

- A card whose archetype lacks the app ability class its key or choice
  effect maps to (``_card_ability``: a catalog gap) is not mirrored: both
  windows answer None rather than value it as another card's ability.
- Two deferred copies of one choice kind are one ``resume_reveal_choice``
  action (the engine resumes the oldest openable entry); its value is that
  entry's card ability (Delivery Agreement and Priority Contracts share a
  kind).
- Corrinth City option 1 for a seated owner and Desert Power's worm option
  when our engine blocks it (the gates differ) are not realisable: the
  option-0 action is taken.
- In the forced random path a leader key's random target is approximated by
  its first legal action; a resumed choice picks a random non-decline option
  at its frame.
- The Guild Spy / The Spice Must Flow timing difference (R2 §8) is accepted:
  buys and Spy placements follow the app's value order.
- A Research / Tleilaxu / In The Shadows gain whose app ``Cost`` fails (no
  drawable card with two markers, the Tleilaxu track ended, Bene Gesserit
  Influence at 6) is no app key, but our engine still owes it: it is taken
  as an automatic gain. Reclaimed Forces at Tleilaxu rank 7 takes the
  troops (the app drops the Tleilaxu option there; we never pay to advance
  past rank 7).
- For Humanity's targets are the tracks with at least two Influence (the
  engine's legal losses; the app's ``Targets`` were not decoded); several
  Alliance recipients take the first offered. Tleilaxu Surgeon's troop zone
  codes map to our ``zones`` pair (garrison first).
"""

import functools
from collections.abc import Callable, Mapping, Sequence

from dune_imperium.agents.app_ai.abilities import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AcquireAbility,
    DeferredAbility,
    PlaceSpyCustomAbility,
    PlaceSpyRevealAbility,
    card_factions,
)
from dune_imperium.agents.app_ai.abilities.immortality import (
    DissectingKitRevealAbility,
    FamilyAtomicsAbility,
    ForHumanityRevealAbility,
    GainResearchRevealAbility,
    InTheShadowsRevealAbility,
    ReclaimedForcesAcquireAbility,
    ReturnSpecimenAbility,
    TleilaxuSurgeonRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    CalculusofPowerEmperorAbility,
    CapturedMentatRevealAbility,
    ChaniCleverTacticianRevealAbility,
    CorrinthCityRevealAbility,
    DeliveryAgreementRevealAbility,
    DesertPowerDeferredAbility,
    InHighPlacesPersuasionAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_b import (
    CrysknifeAbility,
    ShadoutMapesAbility,
    SpacingGuildsFavorRevealAbility,
    SpyNetworkAbility,
    UndercoverAssetAbility,
    UnswervingLoyaltyAbility,
)
from dune_imperium.agents.app_ai.abilities.leaders import (
    DesertScoutsAbility,
    DeviousStrengthAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    LEADER_ARCHETYPES,
    card_entity,
    leader_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.choice import default_random_choice
from dune_imperium.agents.app_ai.context import (
    FACTIONS,
    RECLAIMED_FORCES_REF,
    card_id,
)
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    decide,
    int_arg,
    spy_answer,
    str_arg,
    with_arg,
)
from dune_imperium.agents.app_ai.windows.intrigue import (
    RESEARCH_INTENT,
    TLEILAXU_TRACK_END,
    intrigue_play_sources,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler, arg
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.reveal_turn import (
    reveal_pending_gains,
    waiting_deferred_choices,
)

# ---------------------------------------------------------------------------
# Choice effects -> app abilities
# ---------------------------------------------------------------------------

#: ``reveal_choice_effect`` -> the port class of the card's app ability
#: (spec engine-order.md §4.3 "Reveal (2)" row; R2 §5.0.1). Covert Operation's
#: two Spy icons are two ``PlaceSpyRevealAbility`` keys in the app, as our
#: engine's ``place_two_spies`` then ``place_spy`` frames.
_CHOICE_ABILITIES: Mapping[str, type[DeferredAbility]] = {
    "place_spy": PlaceSpyRevealAbility,
    "place_two_spies": PlaceSpyRevealAbility,
    "place_spy_or_gain_two_strength": UndercoverAssetAbility,
    "recall_spy_to_draw_intrigue_if_two_placed": SpyNetworkAbility,
    "may_recall_two_spies_for_three_persuasion": InHighPlacesPersuasionAbility,
    "may_lose_influence_to_gain_influence": CapturedMentatRevealAbility,
    "may_pay_three_spice_for_influence": SpacingGuildsFavorRevealAbility,
    "may_trash_other_emperor_for_three_strength": CalculusofPowerEmperorAbility,
    "may_retreat_two_troops_for_four_strength": ChaniCleverTacticianRevealAbility,
    "gain_five_solari_or_take_high_council": CorrinthCityRevealAbility,
    "may_pay_water_for_sandworm": DesertPowerDeferredAbility,
    "keep_spice_or_trash_self_for_vp_if_four_contracts": (
        DeliveryAgreementRevealAbility  # Priority Contracts' class subclasses it
    ),
    "may_deploy_or_retreat_one_troop_if_fremen_bond": UnswervingLoyaltyAbility,
    # Immortality (spec immortality.md §5.5, §5.15, §5.20).
    "may_lose_influence_for_vp_if_bene_gesserit_alliance": ForHumanityRevealAbility,
    "may_deploy_or_retreat_one_troop": ShadoutMapesAbility,
    "may_lose_two_troops_for_two_specimens": TleilaxuSurgeonRevealAbility,
}

#: The decline action of each choice whose app ability is Optional (and of the
#: plain Spy icon, whose decline only passes an empty supply's recall).
_DECLINES: Mapping[str, str] = {
    "may_lose_influence_for_vp_if_bene_gesserit_alliance": (
        "decline_reveal_influence_loss"
    ),
    "may_deploy_or_retreat_one_troop": "decline_reveal_troop_move",
    "may_lose_two_troops_for_two_specimens": "decline_reveal_troop_sacrifice",
    "place_spy": "decline_reveal_spy_recall",
    "place_two_spies": "decline_reveal_spy_recall",
    "recall_spy_to_draw_intrigue_if_two_placed": "decline_reveal_spy_recall",
    "may_recall_two_spies_for_three_persuasion": "decline_reveal_spy_recall",
    "may_lose_influence_to_gain_influence": "decline_reveal_influence_exchange",
    "may_pay_three_spice_for_influence": "decline_reveal_spice_influence",
    "may_trash_other_emperor_for_three_strength": "decline_reveal_card_trash",
    "may_retreat_two_troops_for_four_strength": "decline_reveal_troop_retreat",
    "may_deploy_or_retreat_one_troop_if_fremen_bond": "decline_reveal_troop_move",
}

_SPY_EFFECTS = frozenset({"place_spy", "place_two_spies"})

#: Our REVEAL-window action ids this adapter mirrors (core Uprising ± CHOAM).
_REVEAL_ACTIONS = frozenset(
    {
        "acquire_imperium",
        "acquire_reserve",
        "acquire_manipulated_imperium",
        "recruit_reveal_troops",
        "draw_reveal_intrigue",
        "gain_reveal_resources",
        "gain_reveal_faction_influence",
        "retreat_leader_troop",
        "recall_spy_for_leader",
        "resume_reveal_choice",
        "place_track_spy",
        "finish_reveal",
        "play_intrigue",
        # Immortality
        "acquire_tleilaxu",
        "acquire_reclaimed_forces",
        "generate_reveal_specimens",
        "advance_reveal_tleilaxu",
        "advance_reveal_research",
        "return_specimen",
        "use_family_atomics",
    }
)

#: Cards whose pending Reveal gain the app pays from an ``AlwaysRunImmediately``
#: deferred ability (state 400) rather than the plain ``RevealAbility`` (state
#: 300): ``SmugglersHavenRevealAbility`` (imperium-b) and Bene Tleilax Lab's
#: ``BeneTleilaxLabAbility`` (immortality §5.1). Treacherous Maneuver's and
#: Long Reach's Intrigue (``RevealGainIntrigueAbility``) are recognised by
#: their kind.
_IMMEDIATE_GAIN_CARDS = frozenset({"smuggler_s_haven", "bene_tleilax_lab"})

#: The pending-gain kind each argument-free gain action resolves (the engine
#: takes the oldest entry of that kind).
_GAIN_KINDS: Mapping[str, str] = {
    "recruit_reveal_troops": "troops",
    "draw_reveal_intrigue": "intrigue",
    "generate_reveal_specimens": "specimens",
    "advance_reveal_tleilaxu": "tleilaxu",
    "advance_reveal_research": "research",
}

#: Pending gains the app does not run on its own: an Explicit, never auto-run
#: Reveal ability of the source card is a key of the post-reveal prompt, one
#: per icon (immortality.md §3.1, §5.4): Tleilaxu Master's
#: ``GainResearchRevealAbility`` x2 and Dissecting Kit's
#: ``DissectingKitRevealAbility``. A gain of these kinds from a card without
#: that class is not mirrored.
_PROMPT_GAINS: Mapping[str, type[DeferredAbility]] = {
    "research": GainResearchRevealAbility,
    "tleilaxu": DissectingKitRevealAbility,
}

#: Owner of the playmat abilities (Return Specimen, Family Atomics): the app
#: builds them on the player's playmat; no hook here reads its owner.
_PLAYMAT = Entity(Kind.LEADER, "playmat")

#: ``run.memory.intents`` key of a Return Specimen answer still being paid:
#: ``(_RETURN_BATCH, round, seat)`` -> specimens left to return.
_RETURN_BATCH = "reveal_return_specimen"

_SHISHAKLI = "shishakli"

type Intent = Answer | str


def _intent_key(run: DecisionRun, effect: str) -> tuple[object, ...]:
    """``run.memory.intents`` key of a resumed choice's app answer."""

    return ("reveal_choice", run.ctx.round_number, effect)


#: ``run.memory.data`` key: the post-reveal prompt gave its empty answer (End
#: Turn) in this seat's Reveal; its value is ``_end_turn_mark``.
_END_TURN = "reveal_end_turn"


def _end_turn_mark(run: DecisionRun) -> tuple[int, int]:
    """Identifies one Reveal turn: (round, seat)."""

    return (run.ctx.round_number, run.ctx.seat)


# ---------------------------------------------------------------------------
# Honest reads (own frames, own zones)
# ---------------------------------------------------------------------------


def _reveal_context(run: DecisionRun) -> Mapping[str, ActionValue]:
    """The seat's own open Reveal frame context (empty if none)."""

    return run.ctx.own_frame_context("reveal") or {}


def _revealed_cards(context: Mapping[str, ActionValue]) -> list[str]:
    """``revealed_card_NNN``: the revealed cards in reveal (active-card) order."""

    count = context.get("revealed_card_count")
    if not isinstance(count, int) or isinstance(count, bool):
        return []
    cards: list[str] = []
    for index in range(count):
        value = context.get(f"revealed_card_{index:03d}")
        if isinstance(value, str):
            cards.append(value)
    return cards


def _deferred_entries(context: Mapping[str, ActionValue]) -> list[tuple[str, str]]:
    """The Reveal frame's deferred ``(card, effect)`` queue, oldest first."""

    value = context.get("deferred_reveal_choices", "")
    if not isinstance(value, str):
        return []
    entries: list[tuple[str, str]] = []
    for item in value.split(","):
        if item:
            card, _, effect = item.partition("|")
            entries.append((card, effect))
    return entries


def _resumed_card(run: DecisionRun, effect: str) -> str | None:
    """The card ``resume_reveal_choice(effect)`` would bring back.

    The engine resumes the oldest entry of that kind whose condition holds
    now: the queue minus ``waiting_deferred_choices``.
    """

    waiting = set(waiting_deferred_choices(run.ctx.state, run.ctx.seat))
    for card, kind in _deferred_entries(_reveal_context(run)):
        if kind == effect and (card, kind) not in waiting:
            return card
    return None


def _own_spies(run: DecisionRun) -> tuple[Entity, ...]:
    """The seat's spies in board-post order (the engine's recall order).

    UNTRACED: the app's ``GetDeployedSpies`` order; ``GetPostSelection``
    shuffles before ranking, so the order only moves the RNG draws.
    """

    occupied = frozenset(run.ctx.me.spy_post_ids)
    return tuple(
        spy_entity(post.post_id, run.ctx.seat)
        for post in OBSERVATION_POSTS
        if post.post_id in occupied
    )


def _leader_ability[A: Ability](run: DecisionRun, cls: type[A]) -> A | None:
    """The seat's leader ability of port class ``cls`` (current face)."""

    me = run.ctx.me
    if me.leader_id is None or me.leader_id not in LEADER_ARCHETYPES:
        return None
    for ability in abilities_of(leader_entity(me.leader_id, me.leader_face_id)):
        if isinstance(ability, cls):
            return ability
    return None


class _Unmirrored(Exception):
    """A card whose archetype lacks the app ability class its effect or key
    maps to (a catalog gap, e.g. an expansion card sharing one of our effect
    ids). The window answers None (a counted fallback) instead of valuing
    the card with another card's ability."""


def _none_when_unmirrored(handler: Handler) -> Handler:
    """``handler``, answering None when it meets an ``_Unmirrored`` card."""

    @functools.wraps(handler)
    def wrapped(run: DecisionRun) -> DomainAction | None:
        try:
            return handler(run)
        except _Unmirrored:
            return None

    return wrapped


def _card_ability[A: Ability](card: Entity, cls: type[A]) -> A:
    """The card's first ability of port class ``cls``.

    Raises ``_Unmirrored`` when the card's archetype has no such ability:
    attaching the class to a card that does not carry it would silently
    value the card as another card (the window falls back instead).
    """

    for ability in abilities_of(card):
        if isinstance(ability, cls):
            return ability
    raise _Unmirrored(f"{card.ref} has no {cls.__name__}")


# ---------------------------------------------------------------------------
# Choice abilities: requests and answers
# ---------------------------------------------------------------------------


def _choice_ability(run: DecisionRun, effect: str, card_ref: str) -> DeferredAbility:
    """The app ability behind one of our Reveal choice effects."""

    return _card_ability(card_entity(card_ref, run.ctx.seat), _CHOICE_ABILITIES[effect])


def _choice_request(run: DecisionRun, effect: str, card_ref: str) -> Request:
    """The ability's target infos, built from the state (R2 §5).

    Built the same way at the Reveal frame (to value a ``resume`` key) and at
    the choice frame, so both see one candidate list:

    - Spy Network / In High Places: the own spies (``Targets``: P's spies);
    - Captured Mentat: the "lose" tracks (influence > 0) then all tracks;
    - Spacing Guild's Favor: the four tracks (``FACTIONS`` order; the app's
      track order is UNTRACED);
    - Calculus of Power: the other Emperor cards in play
      (``counted_in_play``, as the engine's trash candidates);
    - Unswerving Loyalty, Shadout Mapes: the ``ChooseOne`` indices (deploy,
      then retreat);
    - Corrinth City: option 0, and 1 when Solari >= 5; the rest read none;
    - For Humanity: the tracks P can lose two influence on (influence >= 2;
      judgement: the app's ``Targets`` were not decoded, these are the
      engine's legal losses), ``FACTIONS`` order;
    - Tleilaxu Surgeon: one zone code per troop, garrison troops (0) first,
      then deployed ones (1) (``GetTroopTargets``).
    """

    me = run.ctx.me
    if effect in (
        "recall_spy_to_draw_intrigue_if_two_placed",
        "may_recall_two_spies_for_three_persuasion",
    ):
        return Request((TargetInfo(entities=_own_spies(run)),))
    if effect == "may_lose_influence_for_vp_if_bene_gesserit_alliance":
        tracks = tuple(
            track_entity(f) for f in FACTIONS if getattr(me.influence, f) >= 2
        )
        return Request((TargetInfo(entities=tracks),))
    if effect == "may_lose_two_troops_for_two_specimens":
        zones = (0,) * me.troops_garrison + (1,) * me.troops_conflict
        return Request((TargetInfo(options=zones, min_select=2, max_select=2),))
    if effect == "may_deploy_or_retreat_one_troop":
        options = _unswerving_options(run)
        return Request((TargetInfo(options=tuple(range(len(options)))),))
    if effect == "may_lose_influence_to_gain_influence":
        lose = tuple(track_entity(f) for f in FACTIONS if getattr(me.influence, f) > 0)
        gain = tuple(track_entity(f) for f in FACTIONS)
        return Request((TargetInfo(entities=lose), TargetInfo(entities=gain)))
    if effect == "may_pay_three_spice_for_influence":
        # UNTRACED: the app's faction-track target order; ours (= the engine's).
        tracks = tuple(track_entity(f) for f in FACTIONS)
        return Request((TargetInfo(entities=tracks),))
    if effect == "may_trash_other_emperor_for_three_strength":
        cards = tuple(
            entity
            for entity in (
                card_entity(instance, run.ctx.seat)
                for instance in counted_in_play(me)
                if instance != card_ref
            )
            if "Emperor" in card_factions(entity)
        )
        return Request((TargetInfo(entities=cards, forced=True),))
    if effect == "may_deploy_or_retreat_one_troop_if_fremen_bond":
        options = _unswerving_options(run)
        return Request((TargetInfo(options=tuple(range(len(options)))),))
    if effect == "gain_five_solari_or_take_high_council":
        offered = (0, 1) if me.resources.solari >= 5 else (0,)
        return Request((TargetInfo(options=offered),))
    if effect == "may_pay_water_for_sandworm":
        return Request((TargetInfo(options=(0, 1)),))
    if effect in (
        "keep_spice_or_trash_self_for_vp_if_four_contracts",
        "place_spy_or_gain_two_strength",
    ):
        return Request((TargetInfo(options=(0, 1)),))
    return Request()


def _unswerving_options(run: DecisionRun) -> list[str]:
    """``ShadoutMapesAbility`` ``<Targets>d__6 @0x4e1f0b0`` option order.

    Deploy when a troop is in the garrison (``P.CanDeploy`` is always true in
    a 4-player Uprising game), then retreat when a troop is deployed.
    """

    me = run.ctx.me
    options: list[str] = []
    if me.troops_garrison >= 1:
        options.append("deploy_reveal_card_troop")
    if me.troops_conflict >= 1:
        options.append("retreat_reveal_card_troop")
    return options


def _option(answer: Answer, index: int = 0) -> ActionValue | None:
    """The first ref / option of response item ``index``."""

    if answer.response is None or len(answer.response) <= index:
        return None
    item = answer.response[index]
    return item[0] if item else None


def _plain(run: DecisionRun, action_id: str) -> DomainAction | None:
    """The first legal ``action_id`` without arguments (no Commander form)."""

    for action in run.by_id(action_id):
        if not action.arguments:
            return action
    return run.first(action_id)


def _spy_placement(run: DecisionRun, *, may_decline: bool) -> DomainAction | None:
    """A Reveal Spy icon as the app's ``PlaceSpy`` prompt answers it."""

    decline = run.first("decline_reveal_spy_recall") if may_decline else None
    return spy_answer(
        run,
        run.by_id("place_reveal_spy"),
        run.by_id("recall_spy_for_reveal_placement"),
        decline,
    )


def _realise(run: DecisionRun, effect: str, answer: Answer) -> DomainAction | None:
    """Our legal action that carries the app's ``answer`` to a choice.

    A response the frame cannot realise falls back to the decline of an
    Optional choice, or to option 0 of an Explicit one (judgement).
    """

    if effect in _SPY_EFFECTS:
        return _spy_placement(run, may_decline=True)
    if effect == "place_spy_or_gain_two_strength":
        if _option(answer) == 1:
            strength = run.first("gain_two_reveal_strength")
            if strength is not None:
                return strength
        return _spy_placement(run, may_decline=False)
    if effect == "gain_five_solari_or_take_high_council":
        if _option(answer) == 1:
            seat = run.first("take_high_council_from_reveal")
            if seat is not None:
                return seat
        return run.first("gain_five_reveal_solari")
    if effect == "may_pay_water_for_sandworm":
        if _option(answer) == 1:
            worm = run.first("pay_reveal_water_for_sandworm")
            if worm is not None:
                return worm
        return run.first("decline_reveal_sandworm")
    if effect == "keep_spice_or_trash_self_for_vp_if_four_contracts":
        if _option(answer) == 1:
            trash = run.first("trash_contract_reveal_for_vp")
            if trash is not None:
                return trash
        return run.first("keep_contract_reveal_spice")
    decline = run.first(_DECLINES[effect])
    action: DomainAction | None = None
    chosen = _option(answer)
    if effect == "recall_spy_to_draw_intrigue_if_two_placed":
        if chosen is not None:
            action = with_arg(run.by_id("recall_spy_for_reveal"), "post_id", chosen)
    elif effect == "may_recall_two_spies_for_three_persuasion":
        pair = answer.response[0] if answer.response else ()
        for candidate in run.by_id("recall_spies_for_reveal"):
            posts = {
                str_arg(candidate, "first_post_id"),
                str_arg(candidate, "second_post_id"),
            }
            if len(pair) == 2 and posts == set(pair):
                action = candidate
                break
    elif effect == "may_lose_influence_to_gain_influence":
        lost, gained = _option(answer, 0), _option(answer, 1)
        for candidate in run.by_id("exchange_reveal_influence"):
            if (
                str_arg(candidate, "lost_faction") == lost
                and str_arg(candidate, "gained_faction") == gained
            ):
                action = candidate
                break
    elif effect == "may_pay_three_spice_for_influence":
        if chosen is not None:
            action = with_arg(
                run.by_id("pay_reveal_spice_influence"), "faction", chosen
            )
    elif effect == "may_trash_other_emperor_for_three_strength":
        if chosen is not None:
            action = with_arg(run.by_id("trash_reveal_card"), "card_id", chosen)
    elif effect == "may_retreat_two_troops_for_four_strength":
        action = _plain(run, "retreat_two_troops_for_reveal")
    elif effect in (
        "may_deploy_or_retreat_one_troop_if_fremen_bond",
        "may_deploy_or_retreat_one_troop",
    ):
        options = _unswerving_options(run)
        if isinstance(chosen, int) and 0 <= chosen < len(options):
            action = _plain(run, options[chosen])
    elif effect == "may_lose_influence_for_vp_if_bene_gesserit_alliance":
        if chosen is not None:
            # Several Alliance recipients: the first offered (UNTRACED in the
            # app, as ``windows.intrigue._faction_action``).
            action = with_arg(
                run.by_id("lose_reveal_influence_for_vp"), "faction", chosen
            )
    elif effect == "may_lose_two_troops_for_two_specimens":
        codes = answer.response[0] if answer.response else ()
        if len(codes) == 2:
            zones = ",".join(
                "garrison" if code == 0 else "conflict"
                for code in sorted(c for c in codes if isinstance(c, int))
            )
            action = with_arg(
                run.by_id("lose_reveal_troops_for_specimens"), "zones", zones
            )
    return action if action is not None else decline


def _random_option(run: DecisionRun, effect: str) -> DomainAction | None:
    """``DefaultRandomChoice`` on a choice: a random key with random targets.

    The ability runs (an Optional one is not declined), so the decline and
    the defer are left out unless nothing else is legal.
    """

    if effect in _SPY_EFFECTS:
        return _spy_placement(run, may_decline=False)
    skip = {"defer_reveal_choice", _DECLINES.get(effect)}
    pool = [a for a in run.legal if a.action_id not in skip]
    if not pool:
        pool = [a for a in run.legal if a.action_id != "defer_reveal_choice"]
    return default_random_choice(pool, run.rng) if pool else None


# ---------------------------------------------------------------------------
# reveal_choice
# ---------------------------------------------------------------------------


@_none_when_unmirrored
def reveal_choice_window(run: DecisionRun) -> DomainAction | None:
    """One card choice of our Reveal (FrameKind.REVEAL_CHOICE).

    The app never asks it on its own: the choice is a key of the post-reveal
    prompt (``<ResolveDeferredAbilities>d__15 @0x4a1f490``), so a deferrable
    frame is deferred and valued there (module rule 1), unless the ability
    ``CanRunImmediately`` (``RevealTurnPhase/<ResolveImmediateDeferred
    Abilities>d__15 @0x4a28ec0``, a forced single-key prompt). A frame that
    comes back answers with the stored intent, or with the ability's
    ``Evaluate`` as ``MakeChoice`` answers it (spec engine-order.md §0,
    generic-abilities §0.2): a value > 0 with a response is used; otherwise
    an Optional ability is declined (the empty answer) and an Explicit one,
    whose prompt is forced, goes to ``DefaultRandomChoice``.
    """

    context = run.ctx.top_frame_context
    effect = context.get("reveal_choice_effect")
    card_ref = context.get("reveal_card_id")
    if not isinstance(effect, str) or effect not in _CHOICE_ABILITIES:
        return None  # a non-core choice: not mirrored
    if not isinstance(card_ref, str):
        return None
    if context.get("reveal_spy_recalled") is True:
        # The recall of the app's ``PlaceSpy`` is done; the move is mandatory.
        return _spy_placement(run, may_decline=False)
    p = run.profile
    ability = _choice_ability(run, effect, card_ref)
    defer = run.first("defer_reveal_choice")
    if defer is not None and not ability.can_run_immediately(p):
        return defer
    intent = run.memory.intents.pop(_intent_key(run, effect), None)
    if intent == "decline":
        decline = run.first(_DECLINES.get(effect, ""))
        if decline is not None:
            return decline
        intent = None
    if intent == "random":
        return _random_option(run, effect)
    if isinstance(intent, Answer):
        return _realise(run, effect, intent)
    answer = ability.evaluate(p, _choice_request(run, effect, card_ref))
    if answer.value > 0.0 and answer.response is not None:
        return _realise(run, effect, answer)
    if ability.selection_mode(p) == SelectionMode.EXPLICIT:
        # Forced prompt, nothing > 0 (or no response):
        # ``PlayerEntity::DefaultRandomChoice`` (engine-order.md §0, 12 §3.3).
        return _random_option(run, effect)
    return run.first(_DECLINES[effect])


# ---------------------------------------------------------------------------
# reveal (the post-reveal prompt)
# ---------------------------------------------------------------------------


def _source_card(source: str) -> Entity | None:
    """The card a pending gain's ``source`` names, if it is a personal card
    with an app archetype (not a Tech tile or a Skill)."""

    if source.split(":", 1)[0] not in ("imperium", "reserve", "tleilaxu", "player"):
        return None
    if card_id(source) not in CARD_ARCHETYPES:
        return None
    return card_entity(source)


def _auto_rank(kind: str, source: str, revealed: Sequence[str]) -> int:
    """App order of an automatic Reveal gain: state 300 printed reveal
    abilities before state 400 immediates, then the source card's reveal
    position. State 300 runs ``OrderByDescending(ab => ab.Owner.Specimens)``
    (stable): the cards with a printed specimen (Experimentation, Spiritual
    Fervor, Twisted Mentat, Usurp; immortality.md §8) before the others, a
    no-op without Immortality (engine-order.md §7)."""

    # UNTRACED: when the Bond ``TriggeredAbility`` gains (Southern Elders,
    # Ecological Testing Station, Northern Watermaster, Stillsuit
    # Manufacturer) fire (state 200 or 500); taken with the state-300 gains
    # by card position.
    immediate = kind == "intrigue" or card_id(source) in _IMMEDIATE_GAIN_CARDS
    index = revealed.index(source) if source in revealed else len(revealed)
    later = 1
    if not immediate:
        card = _source_card(source)
        if card is not None and card.int_attr("Specimen") > 0:
            later = 0
    return (400 if immediate else 300) * 10_000 + later * 1_000 + index


def _prompt_gain_sources(
    run: DecisionRun,
    action: DomainAction,
    kind: str,
    entries: Sequence[tuple[str, str, str]],
    answers: dict[str, Answer],
) -> list[Source] | None:
    """The post-reveal keys of the pending ``kind`` gains (``_PROMPT_GAINS``).

    One Explicit, blocking key per icon of every pending entry, all realised
    by ``action`` (the engine resolves the oldest entry). Research is valued
    by ``GainResearchAbility::Evaluate`` over the next research spaces (its
    answer is kept in ``answers["research"]``), Dissecting Kit's Tleilaxu
    step by the inherited ``DeferredAbility::Evaluate`` (no ``DeferValue``:
    1). Empty when the ability's ``Cost`` fails (the app never offers the
    key; our engine still owes the gain, so it runs automatically:
    judgement); None when the source card has no such ability.
    """

    cls = _PROMPT_GAINS[kind]
    p = run.profile
    sources: list[Source] = []
    for _kind, payload, source in entries:
        card = _source_card(source)
        if card is None:
            return None
        ability = next((a for a in abilities_of(card) if isinstance(a, cls)), None)
        if ability is None:
            return None
        if not ability.meets_cost(p):
            return []
        explicit = ability.selection_mode(p) == SelectionMode.EXPLICIT
        for copy in range(max(1, int(payload))):
            sources.append(
                Source(
                    f"{cls.__name__} {source} {copy}",
                    Stage.PROMPT,
                    (action,),
                    _gain_evaluate(run, action, kind, ability, answers),
                    extra={"blocking": True, "explicit": explicit},
                )
            )
    return sources


def _gain_evaluate(
    run: DecisionRun,
    action: DomainAction,
    kind: str,
    ability: DeferredAbility,
    answers: dict[str, Answer],
) -> Callable[[], tuple[float, DomainAction | None]]:
    def evaluate() -> tuple[float, DomainAction | None]:
        request = Request()
        if kind == "research":
            spaces = run.ctx.research_next_space_ids()
            request = Request(
                (TargetInfo(entities=tuple(research_space_entity(s) for s in spaces)),)
            )
        answer = ability.evaluate(run.profile, request)
        answers[kind] = answer
        return answer.value, action

    return evaluate


def _in_the_shadows_source(
    run: DecisionRun, action: DomainAction, source: str
) -> Source | None:
    """Throne Room Politics' "+1 Bene Gesserit Influence" on Reveal:
    ``RiseOfIx.InTheShadowsRevealAbility`` (Explicit, not auto-run, E 100,
    ``Cost`` = ``CanGainInfluence(BeneGesserit)``): a blocking prompt key.
    None for another source, or when the cost fails (the app offers no key;
    our engine still owes the gain: automatic, judgement)."""

    card = _source_card(source)
    if card is None:
        return None
    ability = next(
        (a for a in abilities_of(card) if isinstance(a, InTheShadowsRevealAbility)),
        None,
    )
    if ability is None or not ability.meets_cost(run.profile):
        return None

    def evaluate() -> tuple[float, DomainAction | None]:
        return ability.evaluate(run.profile, Request()).value, action

    explicit = ability.selection_mode(run.profile) == SelectionMode.EXPLICIT
    return Source(
        f"In The Shadows {source}",
        Stage.PROMPT,
        (action,),
        evaluate,
        extra={"blocking": True, "explicit": explicit},
    )


def _gain_sources(
    run: DecisionRun, answers: dict[str, Answer] | None = None
) -> list[Source] | None:
    """The pending Reveal gains: app automatic runs, except the prompt keys.

    Shishakli's "+1 Fremen Influence" is ``CrysknifeAbility`` (Explicit, not
    auto-run): a PROMPT key valued by the inherited ``DeferredAbility::
    Evaluate`` (DeferValue 2) that blocks End Turn. So are Throne Room
    Politics' influence (``_in_the_shadows_source``) and the Research /
    Tleilaxu icons of ``_PROMPT_GAINS``. The printed specimens of a revealed
    card (``generate_reveal_specimens``) are state-300 gains. None when a
    gain's source is not mirrored.
    """

    if answers is None:
        answers = {}
    context = _reveal_context(run)
    pending = reveal_pending_gains(context)
    revealed = _revealed_cards(context)
    sources: list[Source] = []
    for action in run.legal:
        entry: tuple[str, str, str] | None = None
        gain_kind = _GAIN_KINDS.get(action.action_id)
        if gain_kind is not None:
            entries = [e for e in pending if e[0] == gain_kind]
            if gain_kind in _PROMPT_GAINS:
                keys = _prompt_gain_sources(run, action, gain_kind, entries, answers)
                if keys is None:
                    return None
                if keys:
                    sources.extend(keys)
                    continue
            entry = entries[0] if entries else None
        elif action.action_id == "gain_reveal_resources":
            payload = "/".join(
                str(int_arg(action, name) or 0) for name in ("solari", "spice", "water")
            )
            entry = next(
                (e for e in pending if e[0] == "resources" and e[1] == payload), None
            )
        elif action.action_id == "gain_reveal_faction_influence":
            faction = str_arg(action, "faction")
            entry = next(
                (
                    e
                    for e in pending
                    if e[0] == "influence" and e[1].split("/")[0] == faction
                ),
                None,
            )
            if entry is not None and card_id(entry[2]) == _SHISHAKLI:
                sources.append(_crysknife_source(run, action, entry[2]))
                continue
            if entry is not None:
                shadows = _in_the_shadows_source(run, action, entry[2])
                if shadows is not None:
                    sources.append(shadows)
                    continue
        else:
            continue
        if entry is None:
            return None  # a gain action without its pending entry: no fit
        kind, source = entry[0], entry[2]
        sources.append(
            Source(
                action.action_id,
                Stage.REVEAL_AUTO,
                (action,),
                order=_auto_rank(kind, source, revealed),
            )
        )
    return sources


def _crysknife_source(run: DecisionRun, action: DomainAction, card_ref: str) -> Source:
    """Shishakli's Fremen Influence: ``CrysknifeAbility`` (Explicit key)."""

    ability = _card_ability(card_entity(card_ref, run.ctx.seat), CrysknifeAbility)

    def evaluate() -> tuple[float, DomainAction | None]:
        return ability.evaluate(run.profile, Request()).value, action

    explicit = ability.selection_mode(run.profile) == SelectionMode.EXPLICIT
    return Source(
        f"Crysknife {card_ref}",
        Stage.PROMPT,
        (action,),
        evaluate,
        extra={"blocking": True, "explicit": explicit},
    )


def _acquire_sources(run: DecisionRun) -> list[Source]:
    """``AcquireAbility`` keys of the affordable Row / Reserve / set-aside
    cards (``GetUsableDeferredAbilities`` Reveal-only row, b__96_10).

    ``AcquireAbility::Evaluate @0x4cd3c50`` = ``AcquireValue`` (no
    destination picker in Uprising, so the request has no target info).
    """

    sources: list[Source] = []
    for action in run.legal:
        if action.action_id in ("acquire_imperium", "acquire_manipulated_imperium"):
            instance = str_arg(action, "instance_id")
            if instance is None:
                continue
            entity = card_entity(instance)
        elif action.action_id == "acquire_reserve":
            reserve_id = str_arg(action, "card_id")
            if reserve_id is None:
                continue
            entity = card_entity(f"reserve:{reserve_id}")
        else:
            continue
        sources.append(_acquire_source(run, action, entity))
    return sources


def _acquire_source(run: DecisionRun, action: DomainAction, card: Entity) -> Source:
    ability = _card_ability(card, AcquireAbility)

    def evaluate() -> tuple[float, DomainAction | None]:
        return ability.evaluate(run.profile, Request()).value, action

    return Source(f"Acquire {card.ref}", Stage.PROMPT, (action,), evaluate)


def _tleilaxu_sources(run: DecisionRun) -> list[Source]:
    """``AcquireAbility`` keys of the affordable Tleilaxu Row cards
    (immortality.md §3.5, §8: the post-reveal prompt's Tleilaxu buys).

    ``AcquireAbility::Evaluate @0x4cd3c50`` with its Tleilaxu lines. Once P
    has a genetic marker, ``GetAcquireArchIDAndPickerKind`` adds the
    ``ChooseAcquireTleilaxuLocation`` picker (our ``to_deck_top`` variant is
    offered exactly then) and the AI answers option 0, "Top of Deck"
    (12-turn-structure.md §5.2); option 1 (only for The Spice Must Flow) is
    the plain variant.
    """

    by_card: dict[str, list[DomainAction]] = {}
    for action in run.by_id("acquire_tleilaxu"):
        instance = str_arg(action, "instance_id")
        if instance is not None:
            by_card.setdefault(instance, []).append(action)
    return [
        _tleilaxu_source(run, instance, actions)
        for instance, actions in by_card.items()
    ]


def _tleilaxu_source(
    run: DecisionRun, instance: str, actions: Sequence[DomainAction]
) -> Source:
    card = card_entity(instance)
    ability = _card_ability(card, AcquireAbility)
    plain = next((a for a in actions if arg(a, "to_deck_top") is not True), None)
    deck_top = next((a for a in actions if arg(a, "to_deck_top") is True), None)

    def evaluate() -> tuple[float, DomainAction | None]:
        if deck_top is None:
            return ability.evaluate(run.profile, Request()).value, plain
        picker = Request((TargetInfo(options=(0, 1)),))
        answer = ability.evaluate(run.profile, picker)
        return answer.value, deck_top if _option(answer) == 0 else plain

    return Source(f"Acquire {instance}", Stage.PROMPT, tuple(actions), evaluate)


def _reclaimed_forces_source(run: DecisionRun) -> list[Source]:
    """``ReclaimedForcesAcquireAbility`` (immortality.md §3.6): option 0 two
    troops, 1 one Tleilaxu step. At the end of the Tleilaxu track the app
    drops option 1 (R7 §2.4), so the troops are taken there; our engine
    still offers ``choice=tleilaxu`` (OQ-048 adjacent)."""

    actions = run.by_id("acquire_reclaimed_forces")
    if not actions:
        return []
    ability = _card_ability(
        card_entity(RECLAIMED_FORCES_REF), ReclaimedForcesAcquireAbility
    )

    def evaluate() -> tuple[float, DomainAction | None]:
        at_end = run.ctx.tleilaxu_influence() >= TLEILAXU_TRACK_END
        options = (0,) if at_end else (0, 1)
        answer = ability.evaluate(run.profile, Request((TargetInfo(options=options),)))
        choice = "tleilaxu" if _option(answer) == 1 and not at_end else "troops"
        return answer.value, with_arg(actions, "choice", choice)

    return [Source("Reclaimed Forces", Stage.PROMPT, actions, evaluate)]


def _family_atomics_source(run: DecisionRun) -> list[Source]:
    """``FamilyAtomicsAbility`` (playmat, Optional; immortality.md §3.4): in
    the Reveal turn with 4-8 Persuasion, 100 unless the predicted buys are
    worth more than 1 per Persuasion; response ``Int(1)`` = confirm."""

    action = run.first("use_family_atomics")
    if action is None:
        return []
    ability = FamilyAtomicsAbility(_PLAYMAT)

    def evaluate() -> tuple[float, DomainAction | None]:
        request = Request((TargetInfo(options=(0, 1)),))
        answer = ability.evaluate(run.profile, request)
        return answer.value, action if _option(answer) == 1 else None

    return [Source("Family Atomics", Stage.PROMPT, (action,), evaluate)]


def _return_specimen_source(
    run: DecisionRun, answers: dict[str, Answer]
) -> list[Source]:
    """``ReturnSpecimenAbility`` (playmat, Optional; immortality.md §3.4):
    exactly the troop shortfall (``UngainedTroops``) at 1.0, else no answer
    (never a voluntary return). The answer is kept in
    ``answers["return_specimen"]``: one app answer returns them all, our
    engine one per action (``_RETURN_BATCH``)."""

    action = run.first("return_specimen")
    if action is None:
        return []
    ability = ReturnSpecimenAbility(_PLAYMAT)

    def evaluate() -> tuple[float, DomainAction | None]:
        specimens = tuple(range(run.ctx.specimens()))
        answer = ability.evaluate(
            run.profile, Request((TargetInfo(options=specimens),))
        )
        answers["return_specimen"] = answer
        if not answer.response or not answer.response[0]:
            return answer.value, None
        return answer.value, action

    return [Source("Return Specimen", Stage.PROMPT, (action,), evaluate)]


def _return_batch(run: DecisionRun) -> DomainAction | None:
    """The rest of a Return Specimen answer (``_RETURN_BATCH``): one more
    ``return_specimen`` while the shortfall it covers is still there, with
    no new evaluation; the intent is dropped otherwise."""

    key = (_RETURN_BATCH, run.ctx.round_number, run.ctx.seat)
    left = run.memory.intents.pop(key, None)
    action = run.first("return_specimen")
    if not isinstance(left, int) or left <= 0 or action is None:
        return None
    if run.ctx.ungained_troops() <= 0:
        return None
    if left > 1:
        run.memory.intents[key] = left - 1
    return action


def _leader_sources(run: DecisionRun) -> list[Source]:
    """Leader abilities with Reveal timing (``GetUsableDeferredAbilities`` row
    3: ``HasMatchingTiming && CanBeRun``): Amber's Desert Scouts and Feyd's
    Devious Strength. A key whose app ``Cost`` fails is not in the list."""

    p = run.profile
    sources: list[Source] = []
    scouts_actions = run.by_id("retreat_leader_troop")
    scouts = _leader_ability(run, DesertScoutsAbility)
    if scouts_actions and scouts is not None and scouts.meets_cost(p):
        sources.append(
            Source(
                "Desert Scouts",
                Stage.PROMPT,
                scouts_actions,
                _leader_evaluate(run, scouts, scouts_actions, None),
            )
        )
    recall_actions = run.by_id("recall_spy_for_leader")
    devious = _leader_ability(run, DeviousStrengthAbility)
    if recall_actions and devious is not None and devious.meets_cost(p):
        sources.append(
            Source(
                "Devious Strength",
                Stage.PROMPT,
                recall_actions,
                _leader_evaluate(run, devious, recall_actions, "post_id"),
            )
        )
    return sources


def _leader_evaluate(
    run: DecisionRun,
    ability: DeferredAbility,
    actions: tuple[DomainAction, ...],
    post_arg: str | None,
) -> Callable[[], tuple[float, DomainAction | None]]:
    """A leader key's value and the action of its answer.

    Devious Strength's target info is the own spies (``post_arg`` names the
    recall action's post). A value-0 answer stores no spy: the key's first
    target stands in for the forced random pick (module judgement).
    """

    def evaluate() -> tuple[float, DomainAction | None]:
        if post_arg is None:
            return ability.evaluate(run.profile, Request()).value, actions[0]
        spies = tuple(
            spy_entity(post, run.ctx.seat)
            for post in (str_arg(a, post_arg) for a in actions)
            if post is not None
        )
        answer = ability.evaluate(run.profile, Request((TargetInfo(entities=spies),)))
        post = _option(answer)
        chosen = None if post is None else with_arg(actions, post_arg, post)
        return answer.value, chosen if chosen is not None else actions[0]

    return evaluate


def _resume_sources(
    run: DecisionRun, answers: dict[str, Answer]
) -> list[Source] | None:
    """One key per deferred choice kind that can open now; None when a kind
    is not mirrored. Each evaluate stores its answer in ``answers``."""

    p = run.profile
    sources: list[Source] = []
    for action in run.by_id("resume_reveal_choice"):
        effect = str_arg(action, "effect")
        if effect is None or effect not in _CHOICE_ABILITIES:
            return None
        card_ref = _resumed_card(run, effect)
        if card_ref is None:
            return None
        ability = _choice_ability(run, effect, card_ref)
        sources.append(
            Source(
                f"Resume {effect}",
                Stage.PROMPT,
                (action,),
                _resume_evaluate(run, action, effect, card_ref, ability, answers),
                extra={
                    "blocking": True,
                    "explicit": ability.selection_mode(p) == SelectionMode.EXPLICIT,
                    "effect": effect,
                },
            )
        )
    return sources


def _resume_evaluate(
    run: DecisionRun,
    action: DomainAction,
    effect: str,
    card_ref: str,
    ability: DeferredAbility,
    answers: dict[str, Answer],
) -> Callable[[], tuple[float, DomainAction | None]]:
    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, _choice_request(run, effect, card_ref))
        answers[effect] = answer
        return answer.value, action

    return evaluate


def _track_spy_source(run: DecisionRun) -> list[Source]:
    """The Emperor-track Spy: ``WormFactionTrack::FactionTrackBonusAction``
    grants ``PlaceSpyCustomAbility`` (Explicit; ``CanRunImmediately`` only in
    Combat) — a post-reveal key valued ``PlaceSpyAbility::Evaluate
    @0x4d2a870`` = ``SpyValue`` (R6 §6.2)."""

    action = run.first("place_track_spy")
    if action is None:
        return []
    ability = PlaceSpyCustomAbility(track_entity("emperor"))

    def evaluate() -> tuple[float, DomainAction | None]:
        return ability.evaluate(run.profile, Request()).value, action

    explicit = ability.selection_mode(run.profile) == SelectionMode.EXPLICIT
    return [
        Source(
            "Emperor track Spy",
            Stage.PROMPT,
            (action,),
            evaluate,
            extra={"blocking": True, "explicit": explicit},
        )
    ]


def _end_turn(run: DecisionRun, finish: DomainAction | None) -> DomainAction | None:
    """The rest of an End Turn the post-reveal prompt already answered.

    ``12-turn-structure.md`` §4.3: ``elif !forced: empty answer ->
    SkipRunPlayerTurnSelection(false)``: one ``MakeChoice``, then the turn
    ends and every Optional ability left pending is simply not used. Our
    engine needs each such choice declined before ``finish_reveal``, so the
    next Optional blocker is resumed with a ``"decline"`` intent, without
    evaluating or shuffling again. None when the state no longer fits (an
    Explicit or unmirrored blocker): the caller evaluates as usual.
    """

    if finish is not None:
        return finish
    blockers: list[tuple[DomainAction, str]] = []
    for action in run.by_id("resume_reveal_choice"):
        effect = str_arg(action, "effect")
        if effect is None or effect not in _DECLINES:
            return None
        card_ref = _resumed_card(run, effect)
        if card_ref is None:
            return None
        ability = _choice_ability(run, effect, card_ref)
        if ability.selection_mode(run.profile) == SelectionMode.EXPLICIT:
            return None
        blockers.append((action, effect))
    if not blockers:
        return None
    action, effect = blockers[0]
    run.memory.intents[_intent_key(run, effect)] = "decline"
    return action


def _note_answer(
    run: DecisionRun, choice: DomainAction, answers: dict[str, Answer]
) -> None:
    """Keep what the chosen key's app answer says beyond our action.

    A Return Specimen answer names every specimen to return
    (``_RETURN_BATCH``: the rest follow without a new prompt); a research
    key's answer names the research space (``intrigue.RESEARCH_INTENT``, for
    the ``research_advance`` window).
    """

    round_number, seat = run.ctx.round_number, run.ctx.seat
    if choice.action_id == "return_specimen":
        answer = answers.get("return_specimen")
        count = len(answer.response[0]) if answer and answer.response else 0
        if count > 1:
            run.memory.intents[(_RETURN_BATCH, round_number, seat)] = count - 1
    elif choice.action_id == "advance_reveal_research":
        research = answers.get("research")
        space = None if research is None else _option(research)
        key = (RESEARCH_INTENT, round_number, seat)
        # Only a step with two spaces opens our ``research_advance`` frame.
        opens = len(run.ctx.research_next_space_ids()) > 1
        if isinstance(space, str) and opens:
            run.memory.intents[key] = space.removeprefix("research:")
        else:
            run.memory.intents.pop(key, None)


@_none_when_unmirrored
def reveal_window(run: DecisionRun) -> DomainAction | None:
    """Our REVEAL frame: automatic gains, then the app's post-reveal prompt.

    ``PlayerTurnPhase/<ResolveDeferredAbilities>d__15::MoveNext @0x4a1f490``
    with ``turnType = Reveal`` (spec engine-order.md §5.4, 12 §4.2-4.3):
    ``forced = sel.Any(DeferredAbility && SelectionMode == Explicit)``
    (b__5 @0x4a0fe10); ``MakeChoice``; empty answer = End Turn
    (``finish_reveal``).
    """

    if any(a.action_id not in _REVEAL_ACTIONS for a in run.legal):
        return None  # a Reveal action of another expansion: not mirrored
    # A resumed choice frame has been answered by now; an intent left behind
    # (the frame had a single legal action, so no handler ran) is stale.
    for key in [k for k in run.memory.intents if k[:1] == ("reveal_choice",)]:
        del run.memory.intents[key]
    batch = _return_batch(run)
    if batch is not None:
        return batch
    finish = run.first("finish_reveal")
    gain_answers: dict[str, Answer] = {}
    gains = _gain_sources(run, gain_answers)
    if gains is None:
        return None
    if any(s.stage < Stage.PROMPT for s in gains):
        # States 300/400 run before the prompt is built: nothing is valued.
        return decide(run, gains, skip=finish)
    if run.memory.data.get(_END_TURN) == _end_turn_mark(run):
        ending = _end_turn(run, finish)
        if ending is not None:
            if ending is finish:
                del run.memory.data[_END_TURN]
            return ending
    run.memory.data.pop(_END_TURN, None)  # stale, or the state moved on
    answers: dict[str, Answer] = {}
    resumes = _resume_sources(run, answers)
    if resumes is None:
        return None
    sources: list[Source] = [
        *gains,
        *_acquire_sources(run),
        *_tleilaxu_sources(run),
        *_reclaimed_forces_source(run),
        *_leader_sources(run),
        *resumes,
        *_track_spy_source(run),
        *_family_atomics_source(run),
        *_return_specimen_source(run, gain_answers),
    ]
    plots = run.by_id("play_intrigue")
    if plots:
        sources.extend(intrigue_play_sources(run, plots, combat=False))
    blocking = [s for s in sources if s.extra.get("blocking")]
    skip: DomainAction | None
    if finish is not None:
        skip, forced = finish, False
    elif any(s.extra.get("explicit") for s in blocking):
        skip, forced = None, True
    else:
        optional = [s for s in blocking if "effect" in s.extra]
        if not optional:
            return None  # finish blocked by something the app has no key for
        # The app would End Turn: our engine needs the Optional choice
        # declined first (resumed, then answered ``"decline"``).
        skip, forced = optional[0].actions[0], False
    choice = decide(run, sources, skip=skip, forced=forced)
    if choice is not None:
        _note_answer(run, choice, gain_answers)
    if choice is not None and choice.action_id == "resume_reveal_choice":
        effect = str_arg(choice, "effect")
        if effect is not None:
            stored = answers.get(effect)
            intent: Intent
            if stored is not None and stored.value > 0.0:
                intent = stored  # ``MakeChoice`` picked this key
            elif not forced:
                # The empty answer (End Turn) stand-in: the app asks nothing
                # more, so the other Optional blockers follow via _end_turn.
                intent = "decline"
                run.memory.data[_END_TURN] = _end_turn_mark(run)
            else:
                intent = "random"  # ``DefaultRandomChoice`` picked it
            run.memory.intents[_intent_key(run, effect)] = intent
    return choice


# ---------------------------------------------------------------------------
# acquisition_spy
# ---------------------------------------------------------------------------


def acquisition_spy_window(run: DecisionRun) -> DomainAction | None:
    """A card's acquire-box Spy (``AcquireEffectList PlaceSpy``).

    The app's ``PlaceSpy`` prompt: ``PlaceSpyEvaluator`` (best post) or, with
    an empty supply, ``RecallSpyEvaluator`` first (worst post); it never
    declines (``common.spy_answer``).
    """

    return spy_answer(
        run,
        run.by_id("place_acquisition_spy"),
        run.by_id("recall_spy_for_acquisition"),
        run.first("decline_acquisition_spy"),
    )


HANDLERS: dict[str, Handler] = {
    "reveal": reveal_window,
    "reveal_choice": reveal_choice_window,
    "acquisition_spy": acquisition_spy_window,
}
"""Decision-window adapters: our engine's questions -> the app AI's answers."""
