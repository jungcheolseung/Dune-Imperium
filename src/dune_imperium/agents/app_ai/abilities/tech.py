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

Not ported (no Bloodlines tile shares the effect; spec §8): ``Artillery``,
``RiseOfIx.DisposalFacilityAbility`` / ``DisposalFacilityTriggeredAbility``,
``FlagshipAbility``, ``HoloprojectorsAbility``, ``HoltzmanEngineAbility`` /
``HoltzmanEngineEndgameAbility``, ``InvasionShipsAbility``,
``MemocordersAbility`` (endgame), ``RestrictedOrdnanceAbility``,
``ShuttleFleetAbility`` (round start), ``SonicSnoopersAbility``,
``SpySatellitesAbility`` / ``SpySatellitesEndgameAbility``,
``TrainingDronesAbility``, ``TroopTransportsAbility``, ``WindtrapsAbility``;
and the Freighter (``FreighterAbility``, spec §4.6-4.7, §6.6).

Request / answer encoding (on top of ``abilities/generic.py``'s):

- tiles are the ``request.infos[0]`` entities whose archetype is a tech tile
  (``is_tech_tile``), in stack order; the answer is ``((tile.ref,),)``;
- the negotiate target of the negotiate-or-buy sources is the ref
  ``TECH_NEGOTIATION_AREA`` (the app's ``Board.TechNegotiationArea``);
- ``()`` is the app's empty target list (decline the acquire, or "use" with
  no sub-target), as in ``generic``; ``None`` the untouched choice (value 0).
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    SelectionMode,
    Timing,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    TriggeredAbility,
    gain_any_influence_value,
)
from dune_imperium.agents.app_ai.abilities.leaders import SignetAbility
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer

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

    def meets_cost(self, p: Profile) -> bool:
        """``CanAcquireTechTile::CanBePaid @0x4a75f40``: a face-up tile is
        affordable with ``TechDiscount``, spice only (spec §7.3)."""

        return bool(p.tech_acquire_targets(self.tech_discount, False))

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``AcquireTechAbility::ValueForPlayer`` @0x4d97350.

        The base (empty) summer plus ``BuyTechValue(TechDiscount, false)``.
        """

        v = Summer()
        v.add("Acquire Tech Value", p.buy_tech_value(self.tech_discount, False))
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
    Persuasion (spec §5.2, not ported). Every member the AI reads is the
    ``WormAbilityDefinition`` default."""
