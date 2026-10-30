"""Ports of the app's Rise of Ix tech-tile machinery (spec/rix-tech.md).

The app has no Bloodlines tiles; these ports are the faithful base the
app-style Bloodlines tiles build on (docs/app-ai-plan.md §11.3):
``AcquireTechAbility`` and the tile abilities whose effects Bloodlines tiles
share. Section numbers are those of ``spec/rix-tech.md`` (its Errata override
the body); addresses are build dad97e2021144d45b5b4f022e07bd3b3; the class
chains are ``dump/worm-canis.dll.cs``.

Ported (spec §6, §8):

- the acquisition sources: ``AcquireTechAbility`` with the subclasses
  ``AcquireTechAbilityDiscount1`` (the forced acquire after a Tech Discount),
  ``AcquireTechAbilityShippingTrack2`` (the Shipping-track reward; its grant
  never exists in our games) and ``AcquireTechAgentAbility`` (an Agent box),
  and the negotiate-or-buy
  sources ``TechNegotiationDeferredAbility`` (space) and
  ``IxianTechnologyAbility`` (Rhombur's signet);
- ``TechTileAcquiredAbility`` and the acquire abilities Bloodlines tiles share
  (spec §1.2): ``DrawImperiumAcquiredAbility`` (Spaceport; Delivery Bay's
  draw), ``MemocordersAcquiredAbility`` (Glowglobes, Navigation Chamber),
  ``DisposalFacilityAcquiredAbility`` (Planetary Array), plus
  ``ShuttleFleetAcquiredAbility`` and ``GainIntrigueAcquiredAbility`` (the
  other two acquire classes, small and self-contained);
- ``ChaumurkyAbility`` (its ``SpecificAcquireValue`` pays for Chaumurky's
  two-Intrigue acquire, which Self-Destroying Messages shares) and
  ``MinimicFilmAbility`` (Self-Destroying Messages' Reveal Persuasion; no AI
  hook). Flagship's acquire effect (``AcquireEffectList [VP]``, Sardaukar High
  Command) has no class: ``GetAcquireEffectsValue`` values it.

All tile classes in spec §8 are ported, including the original Ix tiles'
activations, endgame abilities and trigger-only classes.

Not ported here: the Freighter (``FreighterAbility``, spec §4.6-4.7, §6.6).

Request / answer encoding (on top of ``abilities/generic.py``'s):

- tiles are the ``request.infos[0]`` entities whose archetype is a tech tile
  (``is_tech_tile``), in stack order; the answer is ``((tile.ref,),)``;
- the negotiate target of the negotiate-or-buy sources is the ref
  ``TECH_NEGOTIATION_AREA`` (the app's ``Board.TechNegotiationArea``);
- ``()`` is the app's empty target list (decline the acquire, or "use" with
  no sub-target), as in ``generic``; ``None`` the untouched choice (value 0).
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    SelectionMode,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AgentAbility,
    ConflictAbility,
    DeferredAbility,
    RevealAbility,
    TriggeredAbility,
    gain_any_influence_value,
)
from dune_imperium.agents.app_ai.abilities.leaders import SignetAbility
from dune_imperium.agents.app_ai.catalog import card_entity, is_high_council_space
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.bloodlines.tech import HIGH_COUNCIL_TECH_DISCOUNT

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "worm.canis.abilities.ActivatedAbilities."
_RIX = _AA + "RiseOfIx."
_ACQUIRED = _RIX + "TechTileAcquiredAbilities."
_CONFLICT_BASE = "worm.canis.abilities.ConflictAbilities.BaseSet."
_TRIGGERED_RIX = "worm.canis.abilities.TriggeredAbilities.RiseOfIx."

#: ``EntityType`` of the archetypes the app builds as ``WormTechTilePlayable``.
TECH_TILE_ENTITY_TYPE: Final = "TechTile"

#: Our ref for the app's ``Board.TechNegotiationArea`` (the "negotiate" target).
TECH_NEGOTIATION_AREA: Final = "tech_negotiation_area"

#: Our High Council space id (``catalog.TECH_SPACES``): the Landsraad space
#: whose first visit grants the Tech discount seat (bloodlines-systems.md §3.1).
HIGH_COUNCIL_SPACE: Final = "high_council"


def is_tech_tile(entity: Entity) -> bool:
    """``OfType<WormTechTilePlayable>()``: the archetype is a tech tile."""

    return entity.attr("EntityType") == TECH_TILE_ENTITY_TYPE


def _tiles(request: Request) -> list[Entity]:
    """``choice.GetTargets(this).OfType<WormTechTilePlayable>()``."""

    if not request.infos:
        return []
    return [e for e in request.infos[0].entities if is_tech_tile(e)]


def _of_kind(request: Request, kind: Kind) -> list[Entity]:
    """``choice.GetTargets(this).OfType<T>()`` for a plain entity kind."""

    if not request.infos:
        return []
    return [e for e in request.infos[0].entities if e.kind is kind]


class _Choice:
    """``WormAIChoiceSelectionWithTargets`` (value 0, nothing stored).

    ``UpdateSelectionTargets @0x4932c00`` replaces the stored answer iff the
    value is strictly greater (``ucomisd v,value; ja``) or the response list
    is still empty (``ListUtil.IsEmpty``): the first call always sticks, later
    ties keep the earlier target. Every caller here passes an id array (an
    empty one stores one empty entity list, so the list is no longer empty);
    a ``null`` array, which would leave it empty, is not modelled.
    """

    def __init__(self) -> None:
        self.value = 0.0
        self.response: tuple[tuple[str | int, ...], ...] | None = None
        self.label = ""

    def update(self, value: float, refs: Sequence[str], label: str) -> None:
        if self.response is None or value > self.value:
            self.value = value
            self.response = () if not refs else (tuple(refs),)
            self.label = label

    def answer(self, default_label: str) -> Answer:
        return Answer(self.value, self.response, self.label or default_label)


def _negotiate_or_buy(p: Profile, request: Request, name: str) -> Answer:
    """The shared ``Evaluate`` of the negotiate-or-buy sources (spec §6.2-6.3).

    ``UpdateSelectionTargets(1.0, src, [TechNegotiationArea])`` first (f64
    literal 1.0), then every tile target at ``AcquireValue(P).Sum``: a tile
    is bought only when it is worth strictly more than 1.0.
    """

    choice = _Choice()
    choice.update(1.0, (TECH_NEGOTIATION_AREA,), f"{name} | negotiate")
    for tile in _tiles(request):
        value = p.tech_tile_acquire_value(tile).sum
        choice.update(value, (tile.ref,), f"{name} Acquire Tech | acquire {tile.ref}")
    return choice.answer(name)


# ---------------------------------------------------------------------------
# §6.1 AcquireTechAbility and its subclasses
# ---------------------------------------------------------------------------


@port(_RIX + "AcquireTechAbility")
class AcquireTechAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.AcquireTechAbility`` (spec §6.1).

    Used as-is by the Dreadnought space. ``Cost @0x4d97140`` =
    ``CanAcquireTechTile(TechDiscount, M, canUseSolari=false)`` (spec §7.3);
    ``CanRunImmediately`` is inherited (false): the prompt waits in the
    post-action list and forces it.
    """

    #: ``get_TechDiscount`` @0x4d97040 (vslot 89).
    tech_discount: ClassVar[int] = 0
    #: ``get_IsCustomAbility`` @0x4d97050 (vslot 90).
    is_custom_ability: ClassVar[bool] = False

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``AcquireTechAbility::SelectionMode`` @0x4d971c0: Explicit."""

        return SelectionMode.EXPLICIT

    def _discount(self, p: Profile) -> int:
        """``TechDiscount``, with the High Council seat assumed on a first
        visit (app-style, Bloodlines Tech Module only).

        bloodlines-systems.md §3.1 row 2 (D12), plan §11.8: the first High
        Council visit grants the seat before the Landsraad tile is bought
        (``[Bloodlines p. 7]`` example), so its placement is valued with the
        seat's −1 (``HIGH_COUNCIL_TECH_DISCOUNT``). The seat only lowers
        ``tech_cost``, so one more discount is the same affordability; every
        other owner, game and seat keeps ``TechDiscount``.
        """

        if (
            p.ctx.tech_module
            and self.owner.kind is Kind.SPACE
            and is_high_council_space(self.owner)
            and not p.ctx.me.high_council
        ):
            return self.tech_discount + HIGH_COUNCIL_TECH_DISCOUNT
        return self.tech_discount

    def meets_cost(self, p: Profile) -> bool:
        """``CanAcquireTechTile::CanBePaid @0x4a75f40``: a face-up tile is
        affordable with ``TechDiscount``, spice only (spec §7.3); the High
        Council seat assumed on a first visit (``_discount``)."""

        return bool(p.tech_acquire_targets(self._discount(p), False))

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``AcquireTechAbility::ValueForPlayer`` @0x4d97350.

        The base (empty) summer plus ``BuyTechValue(TechDiscount, false)``;
        the High Council seat assumed on a first visit (``_discount``).
        """

        v = Summer()
        v.add("Acquire Tech Value", p.buy_tech_value(self._discount(p), False))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AcquireTechAbility::Evaluate`` @0x4d974c0.

        Each tile target in order at ``AcquireValue(P).Sum`` (first strictly
        best); then ``if !(0.0 < value)`` (``ucomisd 0.0,[choice+0x38]; jb``)
        the empty target list at 0.5 (f64 literal), which replaces a stored
        tile worth 0 or less. The app's engine handling of that empty
        Explicit answer is UNTRACED (spec §11); read as "acquire nothing".
        """

        choice = _Choice()
        for tile in _tiles(request):
            value = p.tech_tile_acquire_value(tile).sum
            choice.update(value, (tile.ref,), f"Acquire Tech | acquire {tile.ref}")
        if not (0.0 < choice.value):
            choice.update(0.5, (), "Acquire Tech | no tile")
        return choice.answer("Acquire Tech")


@port(_RIX + "AcquireTechAbilityDiscount1")
class AcquireTechAbilityDiscount1(AcquireTechAbility):
    """``RiseOfIx.AcquireTechAbilityDiscount1``: created at run time (no
    archetype lists it); ``get_TechDiscount`` @0x4d99500 = 1."""

    tech_discount: ClassVar[int] = 1


@port(_RIX + "AcquireTechAbilityShippingTrack2")
class AcquireTechAbilityShippingTrack2(AcquireTechAbility):
    """``RiseOfIx.AcquireTechAbilityShippingTrack2`` (spec §6.1): the
    Shipping-track reward (``WormShippingTrack`` grants it at run time as a
    custom ability; no archetype lists it).

    ``get_TechDiscount`` @0x4d99850 = 2, ``get_IsCustomAbility`` @0x4d99860
    = true, ``IsUnexhausted`` @0x4d99870 = true; the ``.ctor @0x4d996f0``
    sets no timing. ``ValueForPlayer`` and ``Evaluate`` are inherited: V is
    ``BuyTechValue(2, false)`` and is not gated on the cost.
    """

    tech_discount: ClassVar[int] = 2
    is_custom_ability: ClassVar[bool] = True
    is_unexhausted: ClassVar[bool] = True

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: the Shipping-track grant is pending.

        Judgement (unreachable): our games have no Shipping track (Rise of
        Ix), so nothing grants it; never held, like
        ``GainIntrigueCustomAbility.has_custom_ability``.
        """

        return False

    def meets_cost(self, p: Profile) -> bool:
        """``AcquireTechAbilityShippingTrack2::Cost`` @0x4d99880:
        ``HasCustomAbility(this).Then(CanAcquireTechTile(TechDiscount, M,
        false))``."""

        return self.has_custom_ability(p) and super().meets_cost(p)


@port(_RIX + "AcquireTechAgentAbility")
class AcquireTechAgentAbility(AcquireTechAbility):
    """``RiseOfIx.AcquireTechAgentAbility`` (Ixian Engineer's Agent box):
    ``.ctor @0x4d990d0`` sets ``AbilityTiming = Agent``; nothing else."""

    timing: ClassVar[Timing] = Timing.AGENT


# ---------------------------------------------------------------------------
# §6.2-6.3 The negotiate-or-buy sources
# ---------------------------------------------------------------------------


@port(_RIX + "TechNegotiationDeferredAbility")
class TechNegotiationDeferredAbility(DeferredAbility):
    """``RiseOfIx.TechNegotiationDeferredAbility`` (the Tech Negotiation space,
    spec §6.2): ``.ctor @0x4de7fb0`` ``AbilityTiming = Agent``,
    ``WillClearUndo``; ``Cost @0x4de8120`` = ``NoCostAction``. Its targets
    are the negotiation area then ``GetAcquireTechTileTargets(M, P, 1,
    false)``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TechNegotiationDeferredAbility::SelectionMode`` @0x4de8110: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TechNegotiationDeferredAbility::ValueForPlayer`` @0x4de83d0.

        ``Math.Max(NegotiateTechValue, BuyTechValue(1, false))``.
        """

        v = Summer()
        v.add(
            "Tech Negotiation: Negotiate Tech or Buy Tech",
            max(p.negotiate_tech_value(), p.buy_tech_value(1, False)),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TechNegotiationDeferredAbility::Evaluate`` @0x4de8590."""

        return _negotiate_or_buy(p, request, "Tech Negotiation")


@port(_RIX + "IxianTechnologyAbility")
class IxianTechnologyAbility(SignetAbility):
    """``RiseOfIx.IxianTechnologyAbility`` (Prince Rhombur Vernius' signet,
    spec §6.3)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxianTechnologyAbility::ValueForPlayer`` @0x4dd1b60.

        ``Math.Max(NegotiateTechValue, BuyTechValue(0, false))``.
        """

        v = Summer()
        v.add(
            "Ixian Technology: Negotiate Tech or Buy Tech",
            max(p.negotiate_tech_value(), p.buy_tech_value(0, False)),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IxianTechnologyAbility::Evaluate`` @0x4dd1d20 (same as §6.2)."""

        return _negotiate_or_buy(p, request, "Ixian Technology")


# ---------------------------------------------------------------------------
# §7.4, §8 Acquire abilities (TechTileAcquiredAbility and its subclasses)
# ---------------------------------------------------------------------------


@port(_ACQUIRED + "TechTileAcquiredAbility")
class TechTileAcquiredAbility(DeferredAbility):
    """``RiseOfIx.TechTileAcquiredAbilities.TechTileAcquiredAbility``.

    A tile's acquire effect, run at once and forced right after the purchase
    (spec §7.2, §7.4). ``Cost @0x4df62b0`` = ``HasCustomAbility(this)`` (not
    read by any AI hook); ``ValueForPlayer @0x4df64e0`` = the empty base.
    """

    #: ``get_AlwaysRunImmediately`` @0x4df6320.
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TechTileAcquiredAbility::SelectionMode`` @0x4df6310: Explicit."""

        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TechTileAcquiredAbility::Evaluate`` @0x4df65c0: an empty choice
        (value 0, nothing stored), not ``DeferredAbility``'s DeferValue."""

        return Answer(0.0, None, f"{type(self).__name__} default")


@port(_CONFLICT_BASE + "DrawImperiumAcquiredAbility")
class DrawImperiumAcquiredAbility(TechTileAcquiredAbility):
    """``ConflictAbilities.BaseSet.DrawImperiumAcquiredAbility`` (Spaceport's
    two draws; spec §8.12). ``Cost @0x4b83670`` = ``HasDrawableCard`` then
    ``HasCustomAbility``; E = the base (nothing to choose)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DrawImperiumAcquiredAbility::ValueForPlayer`` @0x4b83800 (not
        gated on the cost, unlike ``DrawAbility``)."""

        v = super().value_for_player(p, ())
        v.add("Draw Value", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


@port(_CONFLICT_BASE + "GainIntrigueAcquiredAbility")
class GainIntrigueAcquiredAbility(TechTileAcquiredAbility):
    """``ConflictAbilities.BaseSet.GainIntrigueAcquiredAbility`` (Sonic
    Snoopers' acquire; spec §8.11); E = the base."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainIntrigueAcquiredAbility::ValueForPlayer`` @0x4b841f0."""

        v = super().value_for_player(p, ())
        v.add("Gain Intrigue", p.intrigue_value())
        return v


@port(_CONFLICT_BASE + "MemocordersAcquiredAbility")
class MemocordersAcquiredAbility(TechTileAcquiredAbility):
    """``ConflictAbilities.BaseSet.MemocordersAcquiredAbility`` (+1 influence
    with any faction; spec §8.8). ``Cost @0x4b84860`` = the base, then
    ``CanGainInfluence``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``MemocordersAcquiredAbility::ValueForPlayer`` @0x4b84a80.

        Conflict-reward code copied by the app, labels included:
        ``GetSpiceValue(1)`` plus ``GetGainInfluenceValue(None, 1, -1,
        false).Sum``. No AI caller values a purchase with it (the tile's
        ``AcquireValue`` reads ``GetAcquireEffectsValue``).
        """

        v = super().value_for_player(p, ())
        v.add("Conflict SkirmishC First Spice", p.spice_value(1))
        v.add(
            "Conflict SkirmishC First Influence",
            gain_any_influence_value(p, 1).sum,
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MemocordersAcquiredAbility::Evaluate`` @0x4b84c40.

        Every faction-track target in order at ``GetGainInfluenceValue(
        track.Faction, 1, -1, false).Sum + 100.0`` (f64 literal): the first
        strictly best faction. The House Hagal branch (``HagalMode == 1``)
        is unreachable in a 4-player game.
        """

        choice = _Choice()
        for track in _of_kind(request, Kind.TRACK):
            value = p.gain_influence_value(track.ref, 1, -1, False).sum + 100.0
            choice.update(value, (track.ref,), f"Memocorders Acquire | {track.ref}")
        return choice.answer("Memocorders Acquire")


@port(_CONFLICT_BASE + "ShuttleFleetAcquiredAbility")
class ShuttleFleetAcquiredAbility(TechTileAcquiredAbility):
    """``ConflictAbilities.BaseSet.ShuttleFleetAcquiredAbility`` (+1 influence
    with two different factions; spec §8.10)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShuttleFleetAcquiredAbility::ValueForPlayer`` @0x4b85a50.

        ``GetGainInfluenceValue(f, 1, -1, false).Sum`` for every faction of
        ``M.FactionList``, ``OrderByDescending(x => x).Take(2).Sum()``
        (left to right from 0.0).
        """

        v = super().value_for_player(p, ())
        values = [p.gain_influence_value(f, 1, -1, False).sum for f in FACTIONS]
        top_two = sorted(values, reverse=True)[:2]  # stable OrderByDescending
        total = 0.0
        for value in top_two:  # Enumerable.Sum<double>
            total += value
        v.add("Conflict Machinations First Influence", total)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShuttleFleetAcquiredAbility::Evaluate`` @0x4b85f40.

        The faction-track targets (``ToList``) are shuffled
        (``ListUtil.Shuffle``, here ``p.rng``), each one's
        ``GetGainInfluenceValue(track.Faction, 1, -1, false)`` summer added
        as the key of a ``Dictionary<AIValueSummer, WormFactionTrack>``
        (``TryAdd``; ``AIValueSummer`` overrides no ``Equals``, so every
        fresh summer is a new key and ``Keys`` keep insertion order),
        ``Keys.OrderByDescending(Sum).Take(2)``
        (stable: ties keep the shuffled order), value ``Math.Max(0.5, Σ Sum)``
        (f64 literal 0.5), answered with those (up to) two tracks. The House
        Hagal branch is unreachable.
        """

        tracks = list(_of_kind(request, Kind.TRACK))
        p.rng.shuffle(tracks)
        scores = [(p.gain_influence_value(t.ref, 1, -1, False).sum, t) for t in tracks]
        top_two = sorted(scores, key=lambda item: item[0], reverse=True)[:2]
        total = 0.0
        for value, _ in top_two:  # Enumerable.Sum(c => c.Sum)
            total += value
        value = max(0.5, total)  # Math.Max(0.5, sum)
        choice = _Choice()
        choice.update(
            value,
            tuple(track.ref for _, track in top_two),
            "Machinations First | " + ", ".join(track.ref for _, track in top_two),
        )
        return choice.answer("Machinations First")


@port(_AA + "DisposalFacilityAcquiredAbility")
class DisposalFacilityAcquiredAbility(TechTileAcquiredAbility):
    """``ActivatedAbilities.DisposalFacilityAcquiredAbility`` (optional trash
    on acquire; spec §8.3). ``Cost @0x4ce7d20`` = ``HasTrashableCard`` then
    ``HasCustomAbility``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DisposalFacilityAcquiredAbility::ValueForPlayer`` @0x4ce7eb0."""

        v = super().value_for_player(p, ())
        v.add("Trash Card", p.trash_card_value())
        v.add("Trash Card Bonus", p.trash_mod())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DisposalFacilityAcquiredAbility::Evaluate`` @0x4ce8040.

        ``(card, v) = GetCardToTrash(targets.OfType<WormImperiumPlayable>(),
        1.0)``; a card is answered at ``v + 10.0``, no card with the empty
        target list at 10.0 (f64 literals): the prompt always answers, and
        the empty answer declines the optional trash.
        """

        card, value = p.card_to_trash(_of_kind(request, Kind.CARD), 1.0)
        choice = _Choice()
        if card is not None:
            choice.update(value + 10.0, (card.ref,), f"Disposal Facility | {card.ref}")
        else:
            choice.update(10.0, (), "Disposal Facility | no card")
        return choice.answer("Disposal Facility")


# ---------------------------------------------------------------------------
# §8 Tile abilities
# ---------------------------------------------------------------------------


@port(_AA + "ChaumurkyAbility")
class ChaumurkyAbility(DeferredAbility):
    """``ActivatedAbilities.ChaumurkyAbility`` (endgame tiebreaker; spec §8.2).

    ``Cost @0x4ce4280`` = ``NoCostAction``. ``.ctor @0x4ce4190`` sets
    ``AbilityTiming = 4`` (Endgame); the endgame phase runs it without asking
    the AI.
    """

    timing: ClassVar[Timing] = Timing.ENDGAME  # ``.ctor @0x4ce4190``

    #: ``get_AlwaysRunImmediately`` @0x4ce42e0.
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ChaumurkyAbility::SelectionMode`` @0x4ce42d0: Explicit."""

        return SelectionMode.EXPLICIT

    def is_endgame_playable(self, p: Profile) -> bool:
        """``ChaumurkyAbility::IsEndgamePlayable`` @0x4ce43f0: always."""

        return True

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``ChaumurkyAbility::SpecificAcquireValue`` @0x4ce4400.

        ``IntrigueValue + IntrigueValue`` (``addsd xmm0,xmm0``): the only
        additive tile ``SpecificAcquireValue``; it pays for the two Intrigue
        cards of the acquire, which ``GetAcquireEffectsValue`` values at 0.
        """

        s = Summer()
        value = p.intrigue_value()
        s.add("Chaumurky", value + value)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChaumurkyAbility::Evaluate`` @0x4ce4490: 100.0 (f64 literal),
        no target ("Chaumurky | always play"). The ids are ``null``
        (``xor edx,edx`` @0x4ce4538; the spec writes ``[]``), which
        ``generic``'s encoding also spells ``()``."""

        return Answer(100.0, (), "Chaumurky | always play")


@port(_TRIGGERED_RIX + "MinimicFilmAbility")
class MinimicFilmAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.MinimicFilmAbility`` (Reveal: +1
    Persuasion; spec §8.9). No AI hook: the Reveal phase tests
    ``HasTech(MinimicFilm)`` itself and ``GetRevealPreview`` adds the
    Persuasion (spec §5.2). Every member the AI reads is the
    ``WormAbilityDefinition`` default."""


@port(_TRIGGERED_RIX + "ArtilleryAbility")
class ArtilleryAbility(TriggeredAbility):
    """Artillery (spec §8.1): VIP @0x4ad2e70, SAV @0x4ad2f70.

    Both modifiers multiply an empty summer. The live reveal penalty is in
    ``AgentAbility.value_for_player`` (spec §5.2).
    """

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        s = Summer()
        if pile is Pile.DECK and card.int_attr("Strength") > 0:
            s.multiply("Artillery Mod", p.C.ArtilleryAcquireMod)
        return s

    def specific_acquire_value(self, p: Profile) -> Summer:
        n = sum(c.int_attr("Strength") > 0 for c in p._all_imperium_cards())
        s = Summer()
        s.multiply(f"Artillery with {n} cards", math.pow(p.C.ArtilleryValueMod, n))
        return s


@port(_RIX + "DisposalFacilityAbility")
class DisposalFacilityAbility(DeferredAbility):
    """Reveal trash (spec §8.3); E @0x4dad550, minimum trash value 1.0."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        card, value = p.card_to_trash(_of_kind(request, Kind.CARD), 1.0)
        if card is None:
            return Answer(0.0, None, "Disposal Facility | no card")
        return Answer(value, ((card.ref,),), f"Disposal Facility | {card.ref}")


@port(_RIX + "DisposalFacilityTriggeredAbility")
class DisposalFacilityTriggeredAbility(TriggeredAbility):
    """Disposal Facility's trigger (spec §8.3): no AI hook, no exhaustion."""


def _active_combat_space(p: Profile) -> bool:
    """``P.ActiveSpace?.IsCombatSpace`` (spec §8.4, §8.14)."""

    from dune_imperium.agents.app_ai.catalog import space_entity

    frame = p.ctx.own_frame_context("agent_effects")
    space_id = frame.get("space_id") if frame else None
    return isinstance(space_id, str) and bool(
        space_entity(space_id, p.ctx.board).attr("CombatSpace", False)
    )


@port(_RIX + "FlagshipAbility")
class FlagshipAbility(DeferredAbility):
    """Flagship (spec §8.4): SAV @0x4db6220, E @0x4db6390."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def specific_acquire_value(self, p: Profile) -> Summer:
        me = p.ctx.me
        solari = me.resources.solari
        s = Summer()
        if p.is_final_round() or (
            me.swordmaster_acquired
            and (solari > 6 or (solari >= 5 and me.high_council))
        ):
            s.multiply("Flagship", p.C.FlagshipValueMod)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _REVEAL_TURN,
            _in_player_turn,
        )

        if p.ctx.me.troops_supply >= 2:
            if _active_combat_space(p) and p.units_to_deploy(2, -1) > 0:
                return Answer(100.0, (), "Flagship | 100")
            if _in_player_turn(p, _REVEAL_TURN) and p.ctx.me.resources.solari >= 6:
                return Answer(100.0, (), "Flagship | 100")
        return Answer(0.0, None, "Flagship")


def _first_reveal_value(p: Profile, card: Entity) -> float:
    """Holoprojectors' b__0/b__1 @0x4dc0c40/@0x4dc0db0 (spec §8.5).

    First RevealAbility only, valued with []; absent -> 0.0 (``xorps``
    @0x4dc0d52 and @0x4dc0ec2), resolving the spec's UNTRACED default.
    """

    for ability in abilities_of(card):
        if isinstance(ability, RevealAbility):
            return ability.value_for_player(p, ()).sum
    return 0.0


@port(_RIX + "HoloprojectorsAbility")
class HoloprojectorsAbility(DeferredAbility):
    """Holoprojectors (spec §8.5): VIP @0x4dbfe20, SAV @0x4dbffa0,
    E @0x4dc0210; first discard target, once any hand card is below average.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        s = Summer()
        if pile is Pile.DECK and "IncentiveDiscard" in card.list_attr("Tags"):
            s.multiply("Holoprojectors", p.C.HoloprojectorsAcquireMod)
        return s

    def specific_acquire_value(self, p: Profile) -> Summer:
        n = sum(
            "IncentiveDiscard" in card.list_attr("Tags")
            for card in p._all_imperium_cards()
        )
        s = Summer()
        s.multiply("Holoprojectors", math.pow(p.C.HoloprojectorsValueMod, n))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _UNDETERMINED,
            _in_player_turn,
        )

        if not _in_player_turn(p, _UNDETERMINED) or p.buy_value() > 6.0:
            return Answer(0.0, None, "Holoprojectors")
        me = p.ctx.me
        # Own deck is a multiset; its hidden order is never read.
        cards = p._own_cards(me.deck) or p._own_cards(me.discard_pile)
        total = 0.0
        for card in cards:
            total += _first_reveal_value(p, card)
        average = total / len(cards) if cards else 0.0
        if any(
            average > _first_reveal_value(p, card_entity(ref, p.ctx.seat))
            for ref in p.ctx.hand
        ):
            order = p.discard_order(_of_kind(request, Kind.CARD), False)
            if order:
                return Answer(100.0, ((order[0].ref,),), "Holoprojectors | 100")
        return Answer(0.0, None, "Holoprojectors")


@port(_TRIGGERED_RIX + "HoltzmanEngineAbility")
class HoltzmanEngineAbility(TriggeredAbility):
    """Holtzman Engine (spec §8.6): VIP @0x4afa720, SAV @0x4afa920.
    Both hooks multiply an empty summer, independently of its draw trigger.
    """

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        from dune_imperium.agents.app_ai.abilities.intrigue import _TSMF_ARCHETYPES

        s = Summer()
        if pile is Pile.DECK:
            if card.short in _TSMF_ARCHETYPES:
                s.multiply("Holtzman Engine TSMF", p.C.HoltzmanEngineAcquireTSMFMod)
            elif (
                card.short == "ImperiumArchetypes.BaseSet.LietKynes"
                or card.int_attr("Persuasion") >= 2
            ):
                s.multiply(
                    "Holtzman Engine Persuasion 2",
                    p.C.HoltzmanEngineAcquirePersuasion2Mod,
                )
            elif card.int_attr("Persuasion") == 0:
                s.multiply(
                    "Holtzman Engine Persuasion 0",
                    p.C.HoltzmanEngineAcquirePersuasion0Mod,
                )
        return s

    def specific_acquire_value(self, p: Profile) -> Summer:
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _count_the_spice_must_flow,
        )

        s = Summer()
        s.multiply(
            "Holtzman Engine",
            p.C.HoltzmanEngineValueTSMFMod * min(2, _count_the_spice_must_flow(p)),
        )
        return s


@port(_RIX + "HoltzmanEngineEndgameAbility")
class HoltzmanEngineEndgameAbility(DeferredAbility):
    """Holtzman endgame (spec §8.6): explicit/immediate, V/E empty."""

    timing: ClassVar[Timing] = Timing.ENDGAME  # spec §7.4
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def is_endgame_playable(self, p: Profile) -> bool:
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _count_the_spice_must_flow,
        )

        return _count_the_spice_must_flow(p) >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(0.0, None, "Holtzman Engine endgame")


@port(_RIX + "InvasionShipsAbility")
class InvasionShipsAbility(DeferredAbility):
    """Invasion Ships (spec §8.7), E @0x4dcaec0.

    Resolved b__17_0 @0x4dcc420: no Kwisatz Haderach in hand. Space filter
    b__1 @0x4dcc910 excludes ValidSpaces, requires an enemy Agent, matching
    printed icon and HasResourceCost. b__2/@0x4dcc710 and b__4/@0x4dcc810
    value card AgentAbilities and space abilities with [] (not [space/card]).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        # Spec §8.7: multiply-only VIP (no additive base call).
        s = Summer()
        if pile is Pile.DECK and "IncentiveDiscard" in card.list_attr("Tags"):
            s.multiply("Invasion Ships Mod", p.C.InvasionShipsAcquireMod)
        return s

    def specific_acquire_value(self, p: Profile) -> Summer:
        # b__16_0 @0x4dcc380: Tags.Contains(IncentiveDiscard = 0x14).
        n = sum(
            "IncentiveDiscard" in c.list_attr("Tags")
            for c in p._all_imperium_cards()
        )
        s = Summer()
        s.multiply("Invasion Ships", math.pow(p.C.InvasionShipsValueMod, n))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        from dune_imperium.agents.app_ai.abilities.immortality import (
            SpaceCache,
            valid_space_ids,
        )
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _UNDETERMINED,
            _in_player_turn,
        )
        from dune_imperium.agents.app_ai.abilities.original_intrigue import (
            _board_spaces,
            _can_pay_space,
            _hand_entities,
            _space_value,
        )

        choice = _Choice()
        order = p.discard_order(_of_kind(request, Kind.CARD), False)
        if not order or p.ctx.me.agents_available <= 0:
            return choice.answer("Invasion Ships")
        if not _in_player_turn(p, _UNDETERMINED):
            return choice.answer("Invasion Ships")
        hand = _hand_entities(p)
        if any(c.short == "ImperiumArchetypes.BaseSet.KwisatzHaderach" for c in hand):
            return choice.answer("Invasion Ships")
        cache: SpaceCache = {}
        for card in hand:
            valid = valid_space_ids(p, card.ref, cache)
            for space in _board_spaces(p):
                occupants = p.ctx.space_occupants(space.ref)
                if (
                    space.ref in valid
                    or not occupants
                    or p.ctx.seat in occupants
                    or space.attr("AgentIcon") not in card.list_attr("IconList")
                    or not _can_pay_space(p, space)
                ):
                    continue
                agent_value = Summer()
                for ability in abilities_of(card):
                    if isinstance(ability, AgentAbility):
                        agent_value.merge(ability.value_for_player(p, ()))
                value = _space_value(p, space, ()) + agent_value.sum + -0.1
                value += p.discard_value()
                choice.update(value, (order[0].ref,), "Invasion Ships")
        return choice.answer("Invasion Ships")


@port(_AA + "MemocordersAbility")
class MemocordersAbility(DeferredAbility):
    """Memocorders endgame (spec §8.8), SAV @0x4ce5710, E @0x4ce5b90.

    SAV's UNTRACED conditions resolved @0x4ce587c and @0x4ce5a65:
    per-faction 2/>=3, then influence >=3.75 or >=3.0 in the final round.
    Every modifier still acts on an empty summer.
    """

    timing: ClassVar[Timing] = Timing.ENDGAME  # spec §7.4
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def is_endgame_playable(self, p: Profile) -> bool:
        return all(p._influence(p.ctx.me, f) >= 3 for f in FACTIONS)

    def specific_acquire_value(self, p: Profile) -> Summer:
        s = Summer()
        for faction in FACTIONS:
            rank = p._influence(p.ctx.me, faction)
            if rank >= 3:
                s.multiply(
                    f"Memocorders: {faction} >= 3 influence",
                    p.C.MemocordersValue3Mod,
                )
            elif rank == 2:
                s.multiply(
                    f"Memocorders: {faction} == 2 influence",
                    p.C.MemocordersValue2Mod,
                )
        value = gain_any_influence_value(p, 1).sum
        if value >= 3.75 or (value >= 3.0 and p.is_final_round()):
            s.multiply(
                "Memocorders: High influence value",
                p.C.MemocordersValueConditionalMod,
            )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), "Memocorders | always play")


@port(_TRIGGERED_RIX + "RestrictedOrdnanceAbility")
class RestrictedOrdnanceAbility(TriggeredAbility):
    """Restricted Ordnance (spec §8.9), SAV @0x4b05200.

    The unresolved SAV condition is HighCouncilSeat (@0x4b05272-0x4b0528f).
    No V/E override; the strength and High Council terms live elsewhere.
    """

    def specific_acquire_value(self, p: Profile) -> Summer:
        s = Summer()
        if p.ctx.me.high_council:
            s.multiply("Restricted Ordnance", p.C.RestrictedOrdnanceValueMod)
        return s


@port(_TRIGGERED_RIX + "ShuttleFleetAbility")
class ShuttleFleetAbility(TriggeredAbility):
    """Shuttle Fleet's round-start trigger (spec §8.9): no AI hook."""


@port(_RIX + "SonicSnoopersAbility")
class SonicSnoopersAbility(DeferredAbility):
    """Sonic Snoopers (spec §8.11), SAV @0x4de2210, E @0x4de2840."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def specific_acquire_value(self, p: Profile) -> Summer:
        from dune_imperium.agents.app_ai.abilities.intrigue import IntrigueAbility
        from dune_imperium.agents.app_ai.catalog import intrigue_entity

        s = Summer()
        for ref in p.ctx.intrigue_cards:
            card = intrigue_entity(ref, p.ctx.seat)
            bad = any(
                a.is_bad_intrigue(p)
                for a in abilities_of(card)
                if isinstance(a, IntrigueAbility)
            )
            if bad:
                s.multiply(
                    f"Sonic Snoopers Bad Intrigue: {ref}",
                    p.C.SonicSnoopersBadValueMod,
                )
            else:
                s.multiply(
                    f"Sonic Snoopers Good Intrigue: {ref}",
                    p.C.SonicSnoopersGoodValueMod,
                )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        bad = p.bad_intrigue_cards_in_hand()
        if any(
            c.short == "ImperiumArchetypes.RiseOfIx.IxianEngineer"
            for c in p._all_imperium_cards()
        ):
            return Answer(0.0, None, "Sonic Snoopers")
        if len(bad) > 1 or (len(bad) == 1 and p.is_climax()):
            return Answer(1.0, (tuple(c.ref for c in bad),), "Sonic Snoopers | 1")
        return Answer(0.0, None, "Sonic Snoopers")


@port(_RIX + "SpySatellitesAbility")
class SpySatellitesAbility(DeferredAbility):
    """Spy Satellites (spec §8.13), SAV @0x4de5b60, E @0x4de6300.

    SAV's faction filter b__0 @0x4de6950 is rank < 2; one arc multiplier
    per such faction. The final-round multiplier also requires >=7 spice
    (``cmp eax,7; jl`` @0x4de617f-0x4de6182); all multiply an empty summer.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def specific_acquire_value(self, p: Profile) -> Summer:
        s = Summer()
        for faction in FACTIONS:
            if p._influence(p.ctx.me, faction) < 2:
                mod = (
                    p.C.SpySatellitesValueEarlyMod,
                    p.C.SpySatellitesValueMidMod,
                    p.C.SpySatellitesValueLateMod,
                )[p.game_arc()]
                s.multiply(f"Spy Satellites {p.game_arc()}: {faction}", mod)
        if p.is_final_round() and p.ctx.me.resources.spice >= 7:
            s.multiply("Spy Satellites FinalRound", p.C.SpySatellitesValueFinalRoundMod)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _REVEAL_TURN,
            _in_player_turn,
        )

        if (
            all(p._influence(p.ctx.me, f) >= 2 for f in FACTIONS)
            and p.is_climax()
            and _in_player_turn(p, _REVEAL_TURN)
            and (
                all(
                    c.short != "ImperiumArchetypes.RiseOfIx.IxianEngineer"
                    for c in p._all_imperium_cards()
                )
                or p.is_final_round()
            )
        ):
            return Answer(100.0, (), "Spy Satellites | 100 | 3 Spice -> VP")
        return Answer(0.0, None, "Spy Satellites")


@port(_AA + "SpySatellitesEndgameAbility")
class SpySatellitesEndgameAbility(DeferredAbility):
    """Spy Satellites endgame (spec §8.13 + first Errata), @0x4ce6ab0:
    playable if ANY faction is below 2. V/E empty, explicit/immediate.
    """

    timing: ClassVar[Timing] = Timing.ENDGAME  # spec §7.4
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def is_endgame_playable(self, p: Profile) -> bool:
        return any(p._influence(p.ctx.me, f) < 2 for f in FACTIONS)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(0.0, None, "Spy Satellites endgame")


@port(_RIX + "TrainingDronesAbility")
class TrainingDronesAbility(DeferredAbility):
    """Training Drones (spec §8.14), E @0x4dea760: one supply troop."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        from dune_imperium.agents.app_ai.abilities.intrigue import (
            _REVEAL_TURN,
            _in_player_turn,
        )

        if p.ctx.me.troops_supply > 0:
            if _active_combat_space(p) and p.units_to_deploy(1, -1) > 0:
                return Answer(100.0, (), "Training Drones | 100")
            if _in_player_turn(p, _REVEAL_TURN):
                return Answer(100.0, (), "Training Drones | 100")
        return Answer(0.0, None, "Training Drones")


@port(_RIX + "TroopTransportsAbility")
class TroopTransportsAbility(DeferredAbility):
    """Troop Transports (spec §8.15), SAV @0x4ded480, E @0x4ded520.

    AI selection Optional (@0x4ded1d0). The first info's entities are the
    offered units, max_select is NumberToSelect (``edx=[r13+0x40]``
    @0x4ded842); selected unit refs keep prompt order. Engine owns legality.
    """

    is_unexhausted: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def specific_acquire_value(self, p: Profile) -> Summer:
        s = Summer()
        if p._influence(p.ctx.me, "spacing_guild") >= 2:
            s.multiply(
                "Troop Transports >= 2 Spacing Guild influence",
                p.C.TroopTransportsValueMod,
            )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        if request.infos:
            info = request.infos[0]
            count = p.units_to_deploy(len(info.entities), info.max_select)
            deploy = info.entities[:max(0, count)]
            if deploy:
                return Answer(
                    0.5, (tuple(u.ref for u in deploy),),
                    "Troop Transports | Deploying",
                )
        return Answer(0.0, None, "Troop Transports")


@port("worm.canis.abilities.ConflictAbilities.RiseOfIx.WindtrapsAbility")
class WindtrapsAbility(ConflictAbility):
    """Windtraps (spec §8.9): no AI hook; RelativeConflictValue reads tile."""
