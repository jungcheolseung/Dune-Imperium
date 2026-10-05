"""Rise of Ix tech — spec/rix-tech.md §3-§4: the ``WormAIProfile`` tech methods.

Tile values (``WormTechTilePlayable::AcquireValue``), ``TechTileToAcquire``,
``TechOptionsMod``, ``BuyTechValue`` and ``NegotiateTechValue``: the faithful
base of the app-style Bloodlines Tech Module (docs/app-ai-plan.md §11.3).
Sections below are those of ``spec/rix-tech.md`` (its Errata override the
body); addresses are build dad97e2021144d45b5b4f022e07bd3b3.

The app has only the 18 Rise of Ix tiles (``TechTileArchetypes.RiseOfIx.*``,
all in ``data/archetypes.py``); none is dealt in our games. A tile is any
entity whose archetype has ``EntityType == "TechTile"`` (the archetypes the
app instantiates as ``WormTechTilePlayable``; ``abilities.tech.is_tech_tile``),
whatever its ``Kind``.

State the app reads directly, one overridable method each (tests stub one
method; ``acquire_tech_tile_targets`` takes the tiles as arguments): the
face-up tile of each tech stack (``tech_face_up_tiles``: the Bloodlines Tech
Module's stack tops when the option is on), the seat's tech negotiators
(``tech_negotiator_count``) and the dreadnoughts in its supply
(``tech_dreadnoughts_in_supply``), both 0 in every game we play.

The Bloodlines Tech Module buys tiles differently (docs/app-ai/
bloodlines-systems.md §3.1, the "adaptation" table): ``tech_acquire_targets``
then offers the face-up tops in stack order and the seat's own Secret Project,
each affordable by our ``tech_cost`` (the High Council seat's −1 standing for
the negotiators, the Secret Project's −1 per tile, no Solari; Advanced Data
Analysis only with an own Spy on the board). The valuation methods below are
untouched.

Not ported (spec §5, all ``HasTech``/``SetOn(2)``-gated on Rise of Ix tiles our
games never hold): the tech terms inside ``GetResourceValue``,
``get_IntrigueValue``, ``TrashMod``/``GetCardToTrash``, ``WormImperiumPlayable::
AcquireValue``, ``GetGainInfluenceValue``, ``GetRevealPreview``,
``RelativeConflictValue``, ``AgentAbility::ValueForPlayer`` and
``HighCouncilSpaceAbility::ValueForPlayer``; and the Freighter methods
(``get_FreighterValue``, ``GetFreighterSelections``, spec §4.6-4.7: no shipping
track in our games).
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, cast

from dune_imperium.agents.app_ai.abilities.tech import is_tech_tile
from dune_imperium.agents.app_ai.catalog import INTRIGUE_ARCHETYPES, tech_entity
from dune_imperium.agents.app_ai.catalog import archetype as catalog_archetype
from dune_imperium.agents.app_ai.context import AppContext, card_id
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID
from dune_imperium.rules.tech import tech_cost

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# -- app archetype names the tech methods compare against --------------------------

_TILE = "TechTileArchetypes.RiseOfIx."
INVASION_SHIPS: Final = _TILE + "InvasionShips"
DETONATION_DEVICES: Final = _TILE + "DetonationDevices"
MACHINE_CULTURE: Final = "IntrigueArchetypes.RiseOfIx.MachineCulture"

#: The ``Kind`` tile entities are built with (the catalog's ``tech_entity``
#: uses the same); nothing here reads the kind, tiles are recognised by
#: ``is_tech_tile``.
TECH_TILE_KIND: Final = Kind.TECH


# ---------------------------------------------------------------------------
# Tile entities and the static helpers the app keeps outside WormAIProfile
# ---------------------------------------------------------------------------


def tech_tile_entity(
    archetype: str | Archetype, ref: str | None = None, owner: int | None = None
) -> Entity:
    """A tile entity for an app (or app-style) tile archetype.

    ``archetype`` is a short name (``catalog.archetype``: the app's, else the
    synthetic Bloodlines archetypes of docs/app-ai-plan.md §11.3) or an
    ``Archetype``; ``ref`` defaults to the archetype's short name.
    """

    arch = catalog_archetype(archetype) if isinstance(archetype, str) else archetype
    return Entity(TECH_TILE_KIND, arch.short if ref is None else ref, arch, owner)


def spice_cost(tile: Entity) -> int:
    """``WormEntityExtensions::SpiceCost @0x482e1d0``: the printed cost."""

    return tile.int_attr("SpiceCost", 0)


def acquire_tech_tile_targets(
    face_up_tiles: Sequence[Entity],
    *,
    spice: int,
    solari: int,
    negotiators: int,
    discount: int,
    allow_solari: bool,
) -> list[Entity]:
    """``AcquireTechAbility::GetAcquireTechTileTargets @0x4d96d10`` (spec §4.1).

    The app's static helper, given the face-up tile of each stack in stack
    order (``TechTileStacks.children.OfType<WormTechTileStack>().SelectMany(
    st => st.TechTileTop.children).OfType<WormTechTilePlayable>()``) and the
    player's spice, Solari and tech negotiators (``GetPlayerNegotiators(p).
    children.Count``). ``resourceCount = Math.Max(Spice, allowSolari ?
    Solari : 0)`` (the larger, not the sum); a tile qualifies when ``SpiceCost
    <= discount + resourceCount + negotiators`` (lambda ``b__1 @0x4d97df0``:
    ``setle``).
    """

    resource_count = max(spice, solari if allow_solari else 0)  # Math.Max(int, int)
    budget = discount + resource_count + negotiators
    return [
        tile
        for tile in face_up_tiles
        if is_tech_tile(tile) and spice_cost(tile) <= budget
    ]


def has_intrigue_card(ctx: AppContext, archetype: str) -> bool:
    """``WormPlayer::HasIntrigueCard @0x4835970`` for this seat's hand."""

    return any(
        INTRIGUE_ARCHETYPES.get(card_id(instance)) == archetype
        for instance in ctx.intrigue_cards
    )


def _double_compare(a: float, b: float) -> int:
    """``System.Double::CompareTo``: NaN sorts below every number."""

    if a < b:
        return -1
    if a > b:
        return 1
    if a == b:
        return 0
    if math.isnan(a):
        return 0 if math.isnan(b) else -1
    return 1


class TechMixin(ProfileCore):
    """The Rise of Ix tech ``WormAIProfile`` methods."""

    # ===========================================================================
    # State the app reads directly (see the module docstring)
    # ===========================================================================

    def tech_face_up_tiles(self) -> list[Entity]:
        """The face-up tile of each tech stack, stacks 1, 2, 3 in order.

        ``M.WormPlaymat.Board.TechTileStacks`` → ``TechTileTop`` (spec §4.1).
        Rise of Ix is never in our games. With the Bloodlines Tech Module the
        stack tops (``AppContext.tech_face_up_ids``, public) as app-style tile
        entities (bloodlines-systems.md §3.1); empty without the option.
        """

        if not self.ctx.tech_module:
            return []
        return [tech_entity(tech_id) for tech_id in self.ctx.tech_face_up_ids]

    def tech_negotiator_count(self) -> int:
        """``Board.TechNegotiationArea.GetPlayerNegotiators(P).children.Count``.

        Rise of Ix only (the Tech Negotiation space): 0 in our games. The
        Bloodlines High Council seat's −1 stands for the negotiators inside
        the Tech Module's affordability (``tech_acquire_targets``), so this
        stays 0 there too (bloodlines-systems.md §3.1, D12).
        """

        return 0

    def tech_dreadnoughts_in_supply(self) -> int:
        """``P.Supply.children.OfType<WormDreadnought>().Count()``.

        Rise of Ix only: no dreadnought exists in our games, Bloodlines
        included.
        """

        return 0

    def _tech_profile(self) -> Profile:
        """``self`` as the full ``Profile`` the ability hooks expect."""

        return cast("Profile", self)

    # ===========================================================================
    # §3 Tile valuation
    # ===========================================================================

    def tech_tile_acquire_value(self, tile: Entity) -> Summer:
        """``WormTechTilePlayable::AcquireValue(forPlayer) @0x4adc3f0`` (spec §3.1).

        Authored ``AcquireValue`` + ``GetSynergyMod`` + ``GetAcquireEffectsValue``
        + ``GetSpecificAcquireBonus``, then ``Multiply`` by ``[EarlyMod, 1.0,
        LateMod][arc]`` (both default 1.0; the 1.0 is a literal). Below
        ``MinimumAcquireValue`` (strict ``>``) the sum is multiplied by 0 and
        the Early test is skipped; otherwise in the Early arc a tile whose
        ``EarlyMod`` (read again with default **0.0**) is ``<= 1.0`` is
        multiplied by 0 ("Not early tech"). Unlike the Imperium
        ``AcquireValue`` there are no icon, consolidation, friendship,
        Call-to-Arms or WantSpy terms.
        """

        s = Summer()
        s.add("Archetype Value", tile.float_attr("AcquireValue", 0.0))
        s.merge(self.synergy_mod(tile))
        s.merge(self.tech_tile_acquire_effects_value(tile))
        s.merge(self.tech_tile_specific_acquire_bonus(tile))
        arc_mods = (
            tile.float_attr("EarlyMod", 1.0),
            1.0,  # literal 0x3ff0000000000000 @0x4adc5f0
            tile.float_attr("LateMod", 1.0),
        )
        s.multiply("Game Arc", arc_mods[self.game_arc()])
        if self.minimum_acquire_value() > s.sum:  # ucomisd min,sum ; jbe -> strict
            s.multiply("Game Arc Min", 0.0)
        elif self.game_arc() == 0:  # the second GetGameArc call
            # ucomisd 1.0,e ; jae: zeroed when 1.0 >= EarlyMod (absent = 0.0)
            if 1.0 >= tile.float_attr("EarlyMod", 0.0):
                s.multiply("Not early tech", 0.0)
        return s

    def tech_tile_acquire_effects_value(self, tile: Entity) -> Summer:
        """``WormAIProfile::GetAcquireEffectsValue @0x490e470`` for a tile (spec §3.3).

        The Invasion Ships branch (``ArchID == RiseOfIx.InvasionShips``:
        ``0.0 + GetResourceValue(Troops, 4, false)``, the list ignored) comes
        first; every other tile takes the shared per-entry jump table
        (``acquire_effects_value``, profile-economy.md §9), where ``Trash``,
        ``Intrigue``, ``Imperium`` and ``AnyTwoDifferentRanks`` are worth 0.
        """

        if tile.short == INVASION_SHIPS:
            s = Summer()
            s.add("Acquire Effects", 0.0 + self.resource_value(Attr.TROOPS, 4, False))
            return s
        return self.acquire_effects_value(tile)

    def tech_tile_specific_acquire_bonus(self, tile: Entity) -> Summer:
        """``WormAIProfile::GetSpecificAcquireBonus @0x490f430`` for a tile (spec §3.4).

        The concatenated ``SpecificAcquireValue`` of the tile's abilities
        (only Chaumurky's adds; the other RoI overrides multiply an empty
        summer, so their unported stand-ins' empty value is exact), then the
        Detonation Devices branch: ``k = 2 - dreadnoughts in P.Supply``
        (literal 2, ``mov r15d,2``); ``k > 0`` multiplies by
        ``Pow(DetonationDevicesValueMod, k)`` (a no-op: Detonation Devices has
        no ability, so the summer is empty), else adds
        ``DetonationDevicesValueNoDreadnoughtMod`` (-2.0, both dreadnoughts
        still in the supply).
        """

        from dune_imperium.agents.app_ai.abilities import abilities_of

        profile = self._tech_profile()
        concat = Summer()
        for ability in abilities_of(tile):
            concat.merge(ability.specific_acquire_value(profile))
        s = Summer()
        s.merge(concat)
        if tile.short == DETONATION_DEVICES:
            k = 2 - self.tech_dreadnoughts_in_supply()
            if k > 0:
                s.multiply(
                    "Detonation Devices",
                    math.pow(self.C.DetonationDevicesValueMod, k),
                )
            else:
                s.add(
                    "Detonation Devices - no dreadnoughts",
                    self.C.DetonationDevicesValueNoDreadnoughtMod,
                )
        return s

    # ===========================================================================
    # §4 The WormAIProfile tech methods
    # ===========================================================================

    def tech_acquire_targets(self, discount: int, allow_solari: bool) -> list[Entity]:
        """``GetAcquireTechTileTargets(M, P, discount, allowSolari)`` for this seat.

        With the Bloodlines Tech Module: ``bloodlines_tech_acquire_targets``
        (bloodlines-systems.md §3.1); otherwise the app's helper.
        """

        if self.ctx.tech_module:
            return self.bloodlines_tech_acquire_targets(discount)
        me = self.ctx.me
        return acquire_tech_tile_targets(
            self.tech_face_up_tiles(),
            spice=me.resources.spice,
            solari=me.resources.solari,
            negotiators=self.tech_negotiator_count(),
            discount=discount,
            allow_solari=allow_solari,
        )

    def bloodlines_tech_acquire_targets(self, discount: int) -> list[Entity]:
        """The Tech Module's acquisition model (bloodlines-systems.md §3.1, D12).

        App-style adaptation of ``GetAcquireTechTileTargets``: the face-up tops
        in stack order (``rules/tech.py`` ``face_up_tech_ids``), then this
        seat's own Secret Project (``tech_candidates``). A tile qualifies when
        ``tech_cost(me, tile, discount, secret)`` (the High Council seat's −1
        for the negotiators, the Secret Project's −1 per tile, floor 0) is at
        most the seat's spice; ``allowSolari`` is always false. Advanced Data
        Analysis also needs an own Spy on the board (its ``acquire_tech``
        variants are one per own Spy, ``_acquisition_variants``).
        """

        me = self.ctx.me
        candidates = [(tile, False) for tile in self.tech_face_up_tiles()]
        secret = self.ctx.secret_project_tech_id
        if secret:
            candidates.append((tech_entity(secret), True))
        targets: list[Entity] = []
        for tile, is_secret in candidates:
            printed = TECH_TILES_BY_ID[tile.ref]
            cost = tech_cost(me, printed, discount=discount, secret_project=is_secret)
            if cost > me.resources.spice:
                continue
            if printed.acquire_requires_spy_trash and not me.spy_post_ids:
                continue
            targets.append(tile)
        return targets

    def tech_tile_to_acquire(self, discount: int, allow_solari: bool) -> Entity | None:
        """``WormAIProfile::TechTileToAcquire @0x491b510`` (spec §4.2).

        ``targets.OrderByDescending(t => t.AcquireValue(P)).FirstOrDefault()``
        (lambda ``b__138_0 @0x491f400``): the stable sort keys on
        ``AIValueSummer.CompareTo`` (``Sum.CompareTo``), so the first tile
        with the highest value in stack order wins. A tile worth 0 (Early
        arc, below the minimum) is still returned when it is the best.
        """

        best: Entity | None = None
        best_value = 0.0
        for tile in self.tech_acquire_targets(discount, allow_solari):
            value = self.tech_tile_acquire_value(tile).sum
            if best is None or _double_compare(value, best_value) > 0:
                best, best_value = tile, value
        return best

    def tech_options_mod(self, discount: int, allow_solari: bool) -> float:
        """``WormAIProfile::TechOptionsMod @0x491b3f0`` (spec §4.3).

        ``Math.Max(2.0, 0.5 * SpiceCost(tile))`` (both literals; the printed
        cost, not the discounted one), times ``MachineCultureTechValueMod``
        (plain ``mulsd``) with Machine Culture in hand; 0.0 with no tile.
        """

        tile = self.tech_tile_to_acquire(discount, allow_solari)
        if tile is None:
            return 0.0
        value = max(2.0, float(spice_cost(tile)) * 0.5)
        if has_intrigue_card(self.ctx, MACHINE_CULTURE):  # Rise of Ix intrigue
            value = value * self.C.MachineCultureTechValueMod
        return value

    def buy_tech_value(self, discount: int, allow_solari: bool) -> float:
        """``WormAIProfile::BuyTechValue @0x491b2b0`` (spec §4.4).

        ``TechOptionsMod(discount, allowSolari) * [BuyTechEarly, Mid,
        Late][arc]`` (plain ``mulsd``): independent of how much the tile
        itself is worth.
        """

        value = self.tech_options_mod(discount, allow_solari)
        c = self.C
        return value * (c.BuyTechEarly, c.BuyTechMid, c.BuyTechLate)[self.game_arc()]

    def negotiate_tech_value(self) -> float:
        """``WormAIProfile::get_NegotiateTechValue @0x491a900`` (spec §4.5).

        ``GetResourceValue(Spice, 1, false) * [NegotiateTechEarlyMod, Mid,
        Late][arc]``.
        """

        value = self.resource_value(Attr.SPICE, 1, False)
        c = self.C
        return (
            value
            * (c.NegotiateTechEarlyMod, c.NegotiateTechMidMod, c.NegotiateTechLateMod)[
                self.game_arc()
            ]
        )
