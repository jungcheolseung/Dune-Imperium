"""Card-specific abilities of Uprising Imperium, reserve and starter cards M–Z.

Spec: spec/imperium-b.md (with ``17-card-followups.md`` and ``09`` §3 and
their Errata). Addresses are build dad97e2021144d45b5b4f022e07bd3b3.

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``), so the app's
class chain (``worm-canis.dll.cs``) is the Python MRO. Classes shared with an
A–L card are ported in ``imperium_a.py`` (Southern Elders' bond and reveal,
shared with Chani, Clever Tactician; Delivery Agreement's reveal, imported
here as the base of Priority Contracts' reveal); the generic bases are in
``generic.py``.

Request / answer encoding (``abilities/base``, as in ``generic.py``): the
candidates of a prompt are ``request.infos[0]`` (entities, or custom-choice
``options``); ``Answer.response is None`` is the app's untouched choice
(value 0), ``()`` "use this ability" with no sub-targets, ``((ref, ...),)``
the chosen refs / option indices of the first target info.

Settled while porting (the spec marks them UNTRACED):

- ``ListUtil.MaxByOrElse @0x1254c20`` (Price Is No Object V): the first
  element always sticks, a later one replaces it only when strictly greater
  (``ucomisd; setbe`` with a "found" flag): the first maximum wins.
- ``AIValueSummer<double>.CompareTo @0x2f771c0`` (Shishakli E's
  ``OrderBy(AcquireValue)``): ``Sum.CompareTo(other.Sum)``.

The app never deals Pivotal Gambit and The Beast's Spoils (its Imperium deck
takes ``ImperiumType == Main``; they are ``Promo``). Our ``promo_cards``
option deals them, and ``catalog`` maps them to those app archetypes, so
these ports run in promo games (spec/epic-goto11-promo-draft.md §4).
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    SelectionMode,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    DeliveryAgreementRevealAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    board_space_ids,
    card_entity,
    is_board_space,
    space_entity,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.rules.ornithopter import face_up_battle_card_ids

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# ---------------------------------------------------------------------------
# Helpers (the app's extension methods, read through AppContext)
# ---------------------------------------------------------------------------

_APP_TO_FACTION = {app: ours for ours, app in FACTION_NAMES.items()}
_POST_SPACES: dict[str, tuple[str, ...]] = {
    post.post_id: tuple(post.connected_space_ids) for post in OBSERVATION_POSTS
}
_GAIN_INFLUENCE_SPACE_ABILITY = (
    "worm.canis.abilities.SpaceAbilities.GainInfluenceAbility"
)
#: Our battle icons -> the app's ``BattleIcons`` names (``BattleIconList``).
_APP_BATTLE_ICONS: Mapping[str, str] = {
    "crysknife": "Crysknife",
    "desert_mouse": "DesertMouse",
    "ornithopter": "Ornithopter",
    "wild": "Wildcard",
}


def _targets(request: Request, kind: Kind) -> list[Entity]:
    """``choice.GetTargets(this).OfType<T>()``: the first target info's entities."""

    if not request.infos:
        return []
    return [e for e in request.infos[0].entities if e.kind is kind]


def _hand(p: Profile) -> list[Entity]:
    """``P.Hand.children`` / ``P.HandCards()`` (own hand, in hand order)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.hand]


def _in_play(p: Profile) -> list[Entity]:
    """``P.AllCardsInPlay`` (our ``in_play``: play area and agent area)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.me.in_play]


def _has_faction(card: Entity, faction: str) -> bool:
    """``WormEntityExtensions::FactionsList(c).Contains(f)`` (app name)."""

    return faction in g.card_factions(card)


def _other_of_faction(p: Profile, owner: Entity, faction: str) -> bool:
    """Pattern OTHER(f) (spec §0.5): ``(hand ⧺ inPlay).Any(e != Owner && f)``."""

    return any(
        e.ref != owner.ref and _has_faction(e, faction)
        for e in (*_hand(p), *_in_play(p))
    )


def _in_play_other_of_faction(p: Profile, owner: Entity, faction: str) -> bool:
    """Pattern INPLAY(f): ``inPlay.Except(Only(Owner)).Any(f)``."""

    return any(e.ref != owner.ref and _has_faction(e, faction) for e in _in_play(p))


def _fremen_deck_synergy(p: Profile, pile: Pile, card: Entity) -> Summer:
    """Pattern FDP (spec §0.5): +``SynergyFremenWithBondInDeck`` for a Fremen
    candidate while valuing a purchase (Deck pile), not in the climax."""

    s = Summer()
    if pile is Pile.DECK and _has_faction(card, "Fremen") and not p.is_climax():
        s.add("Fremen in Deck", p.C.SynergyFremenWithBondInDeck)
    return s


def _faction_influence(space: Entity) -> list[tuple[str, int]]:
    """``space.GetAttributeValue<Dictionary<Factions,int>>(FactionInfluence)
    ?? new Dictionary()`` as (our faction id, amount) pairs."""

    raw = space.attr("FactionInfluence")
    if not isinstance(raw, Mapping):
        return []
    return [(_APP_TO_FACTION[str(f)], int(n)) for f, n in raw.items()]


def _bonus_influence(p: Profile, space: Entity) -> float:
    """``Σ GetGainInfluenceValue(f, n + 1) − Σ GetGainInfluenceValue(f, n)``
    over the space's printed ``FactionInfluence`` (the two ``Sum`` lambdas of
    Power Play / Treacherous Maneuver, each summed left to right)."""

    influence = _faction_influence(space)
    normal = 0.0
    for faction, n in influence:
        normal += p.gain_influence_value(faction, n, -1, False).sum
    bonus = 0.0
    for faction, n in influence:
        bonus += p.gain_influence_value(faction, n + 1, -1, False).sum
    return bonus - normal


def _recalled_spy_this_turn(p: Profile) -> bool:
    """``P.GetAttributeValue<bool>(HasRecalledSpyThisTurn)`` (R5 §4.5)."""

    return p.ctx.me.spies_recalled_turn > 0


def _active_space(p: Profile) -> Entity | None:
    """``P.ActiveSpace.FirstOrDefault()``: the space of this Agent turn.

    Ours: the ``space_id`` of the seat's own open ``agent_effects`` frame.
    """

    context = p.ctx.own_frame_context("agent_effects")
    if context is None:
        return None
    space_id = context.get("space_id")
    if not isinstance(space_id, str) or not is_board_space(space_id):
        return None
    return space_entity(space_id, p.ctx.board)


def _board_spaces(p: Profile) -> list[Entity]:
    """``BoardSpaces(match)``: every board space of this game (catalog order)."""

    board = p.ctx.board
    return [space_entity(space_id, board) for space_id in board_space_ids(board)]


def _is_maker_space(space: Entity) -> bool:
    """``WormEntityExtensions::IsMakerSpace @0x482c820``:
    ``GetAttributeValue<int?>(BonusSpice).HasValue`` (read in the binary)."""

    return space.has("BonusSpice")


def _has_observing_spy(p: Profile, space: Entity) -> bool:
    """``WormSpace::HasObservingSpy(P) @0x49c1030``:
    ``GetObservingSpies(P).Any()`` — P's spies on the space's posts."""

    return any(
        space.ref in _POST_SPACES.get(post, ()) for post in p.ctx.me.spy_post_ids
    )


def _battle_icons(p: Profile) -> list[str]:
    """``P.BattleIconList``: the app icon names of the face-up battle cards."""

    icons: list[str] = []
    for battle_card in face_up_battle_card_ids(p.ctx.me):
        objective = OBJECTIVES_BY_ID.get(battle_card)
        icon = (
            objective.battle_icon
            if objective is not None
            else CONFLICTS_BY_ID[battle_card].battle_icon
        )
        if icon is not None:
            icons.append(_APP_BATTLE_ICONS[str(icon)])
    return icons


def _first_reveal_value(p: Profile, card: Entity) -> float:
    """``TypedOwner.Abilities.OfType<RevealAbility>().FirstOrDefault()
    ?.ValueForPlayer(P, []).Sum ?? 0`` (vslot 64)."""

    for ability in abilities_of(card):
        if isinstance(ability, g.RevealAbility):
            return ability.value_for_player(p, ()).sum
    return 0.0


# ---------------------------------------------------------------------------
# Maker Keeper (spec §2 "Maker Keeper")
# ---------------------------------------------------------------------------


class _InfluenceRiderAbility(g.DeferredAbility):
    """Shared shape of Maker Keeper's and Wheels Within Wheels' two riders
    (not an app class: each app class derives from ``DeferredAbility``).

    Explicit, auto-run (``AlwaysRunImmediately`` true), timing Agent; Cost
    ``HasFactionInfluence.AtLeast(faction, 2)``. E is the inherited
    ``DeferredAbility::Evaluate`` (DeferValue; auto-run, no targets). V adds
    the gain when the current influence is at least 2 (``cmp eax,2; jl``);
    the influence the candidate space would give is not anticipated.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True
    FACTION: ClassVar[str] = ""  # our faction id
    LABEL: ClassVar[str] = ""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def gain_value(self, p: Profile) -> float:
        raise NotImplementedError

    def meets_cost(self, p: Profile) -> bool:
        return int(getattr(p.ctx.me.influence, self.FACTION)) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if int(getattr(p.ctx.me.influence, self.FACTION)) >= 2:
            v.add(self.LABEL, self.gain_value(p))
        return v


@port("worm.canis.abilities.ActivatedAbilities.Uprising.MakerKeeperBeneGesseritAbility")
class MakerKeeperBeneGesseritAbility(_InfluenceRiderAbility):
    """``Uprising.MakerKeeperBeneGesseritAbility`` (ctor @0x4d24e50, Cost
    @0x4d24fa0, SelectionMode @0x4d24fc0, AlwaysRunImmediately @0x4d24fd0).

    V ``@0x4d25080``: Bene Gesserit influence >= 2 -> ``GetWaterValue(1)``
    "Maker Keeper Bene Gesserit Water".
    """

    FACTION: ClassVar[str] = "bene_gesserit"
    LABEL: ClassVar[str] = "Maker Keeper Bene Gesserit Water"

    def gain_value(self, p: Profile) -> float:
        return p.water_value(1)


@port("worm.canis.abilities.ActivatedAbilities.Uprising.MakerKeeperFremenAbility")
class MakerKeeperFremenAbility(_InfluenceRiderAbility):
    """``Uprising.MakerKeeperFremenAbility`` (ctor @0x4d255a0, Cost @0x4d256f0,
    SelectionMode @0x4d25710, AlwaysRunImmediately @0x4d25720).

    V ``@0x4d25800``: Fremen influence >= 2 -> ``GetSpiceValue(1)`` "Maker
    Keeper Fremen Spice".
    """

    FACTION: ClassVar[str] = "fremen"
    LABEL: ClassVar[str] = "Maker Keeper Fremen Spice"

    def gain_value(self, p: Profile) -> float:
        return p.spice_value(1)


# ---------------------------------------------------------------------------
# Northern Watermaster
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.TriggeredAbilities.Uprising.NorthernWatermasterBondAbility")
class NorthernWatermasterBondAbility(g.BondAbility):
    """``Uprising.NorthernWatermasterBondAbility`` (ctor @0x4a974f0: timing
    Reveal; ``get_BondFaction`` @0x4a975e0 = Fremen; Cost @0x4a975f0 =
    NoCost). P is the inherited ``BondAbility`` FDP; no E (triggered)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``NorthernWatermasterBondAbility::ValueForPlayer`` @0x4a97760.

        OTHER(Fremen) (``b__10_0 @0x4a97a10``) -> ``GetSpiceValue(2)``
        "Northern Watermaster spice". Reached as "Reveal Triggered".
        """

        v = Summer()
        if _other_of_faction(p, self.owner, "Fremen"):
            v.add("Northern Watermaster spice", p.spice_value(2))
        return v


# ---------------------------------------------------------------------------
# Paracompass
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.Uprising.ParacompassRevealAbility")
class ParacompassRevealAbility(g.RevealAbility):
    """``Uprising.ParacompassRevealAbility``: overrides only
    ``GetRevealPreviewValue @0x4c48880`` (UI; the Persuasion forecast reads it
    by class name in ``economy._reveal_preview_value``). AI value = the
    generic ``RevealAbility`` V (no printed reveal resources) + the triggered
    V below."""


@port("worm.canis.abilities.TriggeredAbilities.Uprising.ParacompassTriggeredAbility")
class ParacompassTriggeredAbility(g.TriggeredAbility):
    """``Uprising.ParacompassTriggeredAbility`` (ctor @0x4a99bd0: timing
    Reveal; Cost @0x4a99cd0 = ``HasHighCouncilSeat``; ``get_ShouldExhaust``
    @0x4a99de0 = false)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ParacompassTriggeredAbility::ValueForPlayer`` @0x4a99ef0.

        With a High Council seat: ``GetPersuasionValue(2 | Swordmaster)``
        (``movzx ebx,al; or ebx,2``: 2 or 3) "Paracompass Persuasion n".
        """

        v = Summer()
        me = p.ctx.me
        if me.high_council:
            n = 2 | (1 if me.swordmaster_acquired else 0)
            v.add(f"Paracompass Persuasion {n}", p.persuasion_value(n))
        return v


# ---------------------------------------------------------------------------
# Pivotal Gambit (promo; not in a normal game)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Promo.PivotalGambitAbility")
class PivotalGambitAbility(g.DeferredAbility):
    """``Promo.PivotalGambitAbility`` (ctor @0x4d93660: timing Agent;
    SelectionMode @0x4d93750 = Optional; Cost @0x4d93760 = NoCost; not
    auto-run). Not dealt in a 4-player Uprising game (spec §0.6)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PivotalGambitAbility::Evaluate`` @0x4d93af0: ``Upd(100.0, null)``."""

        return Answer(100.0, (), "Pivotal Gambit | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PivotalGambitAbility::ValueForPlayer`` @0x4d93950.

        A copy of Smuggler's Haven's V without the affordability test (app
        bug kept): ``GetSpiceValue(-4)`` + ``GetVictoryPointValue(1)``.
        """

        v = Summer()
        v.add("Smuggler's Haven Spice Cost", p.spice_value(-4))
        v.add("Smuggler's Haven VP", p.victory_point_value(1))
        return v


# ---------------------------------------------------------------------------
# Price Is No Object
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PriceIsNoObjectAbility")
class PriceIsNoObjectAbility(g.DeferredAbility):
    """``Uprising.PriceIsNoObjectAbility`` (ctor @0x4d2cbb0: timing Agent;
    SelectionMode @0x4d2cdb0 = Optional; not auto-run; the archetype
    DeferValue 1 is unused, own E).

    Targets @0x4d2cca0: ``MakeAcquireImperiumRowCardTargeting(maxCost =
    P.Solari)``; ``request.infos[0]`` holds the offered CARD entities in the
    app's target order (UNTRACED whether the reserve is included — the
    adapter decides what it offers).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d2cdc0: some Imperium Row or Reserve card (not
        Foldspace) with ``PersuasionCost <= P.Solari`` (``cmp; setle``)."""

        solari = p.ctx.me.resources.solari
        cards = [card_entity(i) for i in p.ctx.imperium_row]
        cards += [
            card_entity(f"reserve:{reserve_id}")
            for reserve_id, count in p.ctx.reserve_stacks
            if count > 0
        ]
        return any(c.int_attr("PersuasionCost") <= solari for c in cards)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PriceIsNoObjectAbility::Evaluate`` @0x4d2d590.

        For each target card, no shuffle: ``GetSolariValue(-cost) +
        AcquireValue(P).Sum``; the first candidate sticks, a later one wins
        only when strictly greater. Used by MakeChoice only if > 0.
        """

        stored: Answer | None = None
        for card in _targets(request, Kind.CARD):
            acquired = p.acquire_value(card)
            value = p.solari_value(-card.int_attr("PersuasionCost")) + acquired.sum
            if stored is None or value > stored.value:
                stored = Answer(value, ((card.ref,),), f"Price Is No Object {card.ref}")
        if stored is None:
            return Answer(0.0, None, "Price Is No Object no target")
        return stored

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PriceIsNoObjectAbility::ValueForPlayer`` @0x4d2d080.

        Imperium Row only (no reserve): the affordable card with the highest
        ``AcquireValue`` (``MaxByOrElse``: first maximum, read at
        @0x1254c20) after paying the candidate space's Solari cost; its value
        and its Solari price are added even when the net is negative.
        """

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        remaining = p.ctx.me.resources.solari - (
            g.space_solari_cost(p, space) if space is not None else 0
        )
        best: Entity | None = None
        best_value = 0.0
        for card in (card_entity(i) for i in p.ctx.imperium_row):
            if card.int_attr("PersuasionCost") > remaining:  # b__0: cmp; setle
                continue
            value = p.acquire_value(card).sum  # b__1
            if best is None or value > best_value:
                best, best_value = card, value
        if best is not None:
            cost = best.int_attr("PersuasionCost")
            v.add(f"Price Is No Object Acquire {best.ref}", p.acquire_value(best).sum)
            v.add(f"Price Is No Object {cost} Solari", p.solari_value(-cost))
        return v


# ---------------------------------------------------------------------------
# Priority Contracts (CHOAM; the agent box is generic.GainContractAbility)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PriorityContractsRevealAbility")
class PriorityContractsRevealAbility(DeliveryAgreementRevealAbility):
    """``Uprising.PriorityContractsRevealAbility`` (ctor @0x4d2eb20: timing
    Reveal) : ``DeliveryAgreementRevealAbility`` (``imperium_a.py``).

    Overrides only ``get_SpiceAmount`` @0x4d2ecd0 = 2 (Delivery Agreement's
    @0x4d02a10 = 1), ``get_ButtonTexts`` and ``MakeGameLogBuilder``.
    Inherited: Explicit, NoCost, not auto-run; E @0x4d02de0 (with 4+
    completed contracts option 1 = trash -> ``GetVictoryPointValue(1)``
    first, then option 0 = ``GetSpiceValue(SpiceAmount)`` if strictly
    greater); V @0x4d02c00 = ``max(spice, VP)``. Losing the card is never
    priced.
    """

    spice_amount: ClassVar[int] = 2


# ---------------------------------------------------------------------------
# Public Spectacle
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PublicSpectacleAbility")
class PublicSpectacleAbility(g.GainAnyInfluenceAbility):
    """``Uprising.PublicSpectacleAbility`` (ctor @0x4d2edc0: timing Agent).

    Only ``Cost`` @0x4d2ef10 is overridden (``HasRecalledSpy`` then
    ``CanGainInfluence``: an engine gate). E and V are the inherited
    ``GainAnyInfluenceAbility`` ones (Explicit; E = influence + 100 "Static
    Boost"; V = best +1 influence). V is **not** gated by the spy recall (app
    behaviour kept).
    """

    timing: ClassVar[Timing] = Timing.AGENT


# ---------------------------------------------------------------------------
# Rebel Supplier / Strike Fleet
# ---------------------------------------------------------------------------


class _RecalledSpyTroopsAbility(g.DeferredAbility):
    """Shared shape of Rebel Supplier and Strike Fleet (not an app class).

    Explicit, auto-run, timing Agent; Cost ``HasRecalledSpy``; E =
    ``Upd(100.0, null)``; V = the troops when a spy was already recalled
    this turn (the recall the placement itself may cause is not
    anticipated).
    """

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True
    TROOPS: ClassVar[int] = 0
    LABEL: ClassVar[str] = ""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _recalled_spy_this_turn(p)

    def costed_troops(self, p: Profile) -> int:
        """``GetCostedTroops``: ``HasRecalledSpyThisTurn ? n : 0``.

        UNTRACED: no caller found (spec §5 item 5); kept for completeness.
        """

        return self.TROOPS if _recalled_spy_this_turn(p) else 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), f"{type(self).__name__} | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if _recalled_spy_this_turn(p):
            v.add(self.LABEL, p.troop_value(self.TROOPS, False))
        return v


@port("worm.canis.abilities.ActivatedAbilities.Uprising.RebelSupplierAbility")
class RebelSupplierAbility(_RecalledSpyTroopsAbility):
    """``Uprising.RebelSupplierAbility`` (ctor @0x4d2f090, SelectionMode
    @0x4d2f1f0, AlwaysRunImmediately @0x4d2f200, Cost @0x4d2f210,
    GetCostedTroops @0x4d2f6d0 ``movzx; add eax,eax``; E @0x4d2f780 = 100;
    V @0x4d2f510 = ``GetTroopValue(2, false)`` "Rebel Supplier Troops")."""

    TROOPS: ClassVar[int] = 2
    LABEL: ClassVar[str] = "Rebel Supplier Troops"


@port("worm.canis.abilities.ActivatedAbilities.Uprising.StrikeFleetAbility")
class StrikeFleetAbility(_RecalledSpyTroopsAbility):
    """``Uprising.StrikeFleetAbility`` (ctor @0x4d44330, SelectionMode
    @0x4d44490, AlwaysRunImmediately @0x4d444a0, Cost @0x4d444b0,
    GetCostedTroops @0x4d44970 ``lea eax,[rax+rax*2]``; E @0x4d44a20 = 100;
    V @0x4d447b0 = ``GetTroopValue(3, false)`` "Strike Fleet Troops")."""

    TROOPS: ClassVar[int] = 3
    LABEL: ClassVar[str] = "Strike Fleet Troops"


# ---------------------------------------------------------------------------
# Reliable Informant
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.ReliableInformantAbility")
class ReliableInformantAbility(g.PlaceSpyAbility):
    """``Uprising.ReliableInformantAbility`` (ctor @0x4d34af0: timing Agent;
    ``get_PostFilter`` @0x4d34d20 = ``IsEmperorBeneGesseritOrFremen``).

    E and SelectionMode (Explicit) are the inherited ``PlaceSpyAbility``
    ones. ``Cost`` @0x4d34be0 (valid posts / ``SpyRemainingCount``; exact
    boolean UNTRACED) is an engine gate and not modelled.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``factionList`` of ``IsValidObservationPost`` (app faction names).
    POST_FACTIONS: ClassVar[tuple[str, ...]] = ("Emperor", "BeneGesserit", "Fremen")

    def is_valid_observation_post(self, p: Profile, post_id: str) -> bool:
        """``ReliableInformantAbility::IsValidObservationPost`` @0x4d34d30.

        ``BoardSpaces.Where(factionList.Contains(s.Faction))`` (b__0
        @0x4d35270) ``.Any(s => s.GetObservationPosts.Contains(post))`` (b__1
        @0x4d352d0). Occupancy is not tested.
        """

        connected = _POST_SPACES.get(post_id, ())
        return any(
            space.attr("Faction") in self.POST_FACTIONS and space.ref in connected
            for space in _board_spaces(p)
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ReliableInformantAbility::ValueForPlayer`` @0x4d34fd0.

        ``PlaceSpyAbility`` V (``SpyValue``), then ``Multiply`` by
        ``ReliableInformantMod`` when some observation post is valid (always
        on the Uprising board), else by 0.0.
        """

        v = super().value_for_player(p, with_entities)
        if any(
            self.is_valid_observation_post(p, post.post_id)
            for post in OBSERVATION_POSTS
        ):
            v.multiply("Reliable Informant Spy", p.C.ReliableInformantMod)
        else:
            v.multiply("Reliable Informant No Posts", 0.0)
        return v


# ---------------------------------------------------------------------------
# Sardaukar Coordination
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.Uprising.SardaukarCoordinationRevealAbility")
class SardaukarCoordinationRevealAbility(g.RevealAbility):
    """``Uprising.SardaukarCoordinationRevealAbility`` (replaces the plain
    reveal box; timing Reveal)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SardaukarCoordinationRevealAbility::ValueForPlayer`` @0x4c4c860.

        Generic reveal V, then ``GetStrengthValue(n, false)`` "Sardaukar
        Coordination Strength" (added even for n = 0) with n = the Emperor
        cards currently in **hand** (``<>c::b__7_0 @0x4c4cd10``; this card
        counts while it is in hand).
        """

        v = super().value_for_player(p, with_entities)
        n = sum(1 for e in _hand(p) if _has_faction(e, "Emperor"))
        v.add("Sardaukar Coordination Strength", p.strength_value(n, False))
        return v


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.SardaukarCoordinationAgentAbility"
)
class SardaukarCoordinationAgentAbility(g.DeployUnitsAbility):
    """``Uprising.SardaukarCoordinationAgentAbility`` (timing Agent, inherited
    from ``DeployUnitsAbility``).

    Overrides only ``Cost`` @0x4d376b0 and ``Targets`` @0x4d37be0 (garrison
    units ``Take(P.TroopDeployNumber)``: the request's ``max_select``; the
    min/max/forced flags are UNTRACED). E (``GetUnitsToDeploy`` at 0.5), V
    (``DeployValue(Owner)``) and SelectionMode (Optional) are inherited.
    """


@port(
    "worm.canis.abilities.PlayAbilities.Uprising.SardaukarCoordinationTriggeredAbility"
)
class SardaukarCoordinationTriggeredAbility(g.TriggeredAbility):
    """``Uprising.SardaukarCoordinationTriggeredAbility`` (ctor @0x4c5bf50:
    timing Reveal; ``get_ShouldExhaust`` @0x4c5c220 = false): applies the
    strength in the engine; no AI hook (V = 0 inside the reveal sum)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Sardaukar Soldier
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.TriggeredAbilities.Uprising.SardaukarSoldierAbility")
class SardaukarSoldierAbility(g.TriggeredAbility):
    """``Uprising.SardaukarSoldierAbility`` (ctor @0x4a9cc00: no timing;
    trigger ``ImperiumTrashed`` ``<IsValidFor>d__6 @0x4a9d300``; Cost
    @0x4a9cd30 = NoCost; ``get_ShouldExhaust`` @0x4a9cd20 = false). No AI
    hook: no trash chooser values the drawn intrigue."""

    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Seek Allies
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.BaseSet.SeekAlliesAgentAbility")
class SeekAlliesAgentAbility(g.AgentAbility):
    """``BaseSet.SeekAlliesAgentAbility`` (only V overridden; E is
    ``AgentAbility::Evaluate``)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SeekAlliesAgentAbility::ValueForPlayer`` @0x4cb4740.

        The generic agent value plus ``SeekAlliesValueMod`` "Losing Seek
        Allies" (positive: trashing the starter is a small bonus).
        """

        v = super().value_for_player(p, with_entities)
        v.add("Losing Seek Allies", p.C.SeekAlliesValueMod)
        return v


# ---------------------------------------------------------------------------
# Shishakli
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.ShishakliAgentAbility")
class ShishakliAgentAbility(g.DeferredAbility):
    """``Uprising.ShishakliAgentAbility`` (ctor @0x4d38270: timing Agent;
    SelectionMode @0x4d384e0 = Optional; Cost @0x4d38490 =
    ``HasTrashableCard``; not auto-run; the archetype DeferValue 2 is
    unused, own E).

    Targets (``<Targets>d__6 @0x4d394f0``): ``hand ⧺ inPlay ⧺ discard`` in
    that order — the request's CARD entities in that order.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShishakliAgentAbility::Evaluate`` @0x4d38800.

        ``(card, tv) = GetCardToTrash(cards, 1.0)`` (literal); "Trash Value"
        ``tv``; without junk, the card with the lowest ``AcquireValue``
        (``OrderBy`` by ``AIValueSummer.CompareTo`` = ``Sum``, stable: the
        first minimum in target order); + ``CardDrawValueWithBuyGains``.
        """

        cards = _targets(request, Kind.CARD)
        card, trash_value = p.card_to_trash(cards, 1.0)
        s = Summer()
        s.add("Trash Value", trash_value)
        if card is None:
            if not cards:  # ``First()`` on an empty list: unreachable (Cost)
                return Answer(0.0, None, "Shishakli no target")
            keyed = [(c, p.acquire_value(c).sum) for c in cards]
            card = min(keyed, key=lambda item: item[1])[0]  # first minimum
        s.add("Draw 1 card with Buy Gains", p.card_draw_value_with_buy_gains())
        return Answer(s.sum, ((card.ref,),), f"Shishakli trash {card.ref}")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShishakliAgentAbility::ValueForPlayer`` @0x4d385f0 (not gated by
        ``HasTrashableCard``)."""

        v = Summer()
        v.add("Shishakli Trash Card", p.trash_card_value())
        v.add("Shishakli Trash Card Bonus", p.trash_mod())
        v.add("Shishakli Draw Card", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


@port("worm.canis.abilities.ActivatedAbilities.BaseSet.CrysknifeAbility")
class CrysknifeAbility(g.DeferredAbility):
    """``BaseSet.CrysknifeAbility`` (Shishakli's "Fremen Bond: +1 Fremen
    Influence"; ctor @0x4e36a80: timing Reveal; SelectionMode @0x4e36ca0 =
    Explicit; AlwaysRunImmediately @0x4e36cb0 = false; Cost @0x4e36bf0 =
    ``HasFremenBond`` then ``CanGainInfluence(Fremen)``). E is the inherited
    ``DeferredAbility::Evaluate`` (archetype DeferValue 2: ordering only)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CrysknifeAbility::ValueForPlayer`` @0x4e36e60.

        OTHER(Fremen) (``b__11_0 @0x4e372b0``) -> ``GetGainInfluenceValue(
        Fremen, 1, -1, false).Sum`` "Crysknife Influence".
        """

        v = Summer()
        if _other_of_faction(p, self.owner, "Fremen"):
            v.add(
                "Crysknife Influence",
                p.gain_influence_value("fremen", 1, -1, False).sum,
            )
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``CrysknifeAbility::ValueInPileForOtherPlay`` @0x4e370a0: FDP."""

        return _fremen_deck_synergy(p, pile, card)


# ---------------------------------------------------------------------------
# Smuggler's Harvester / Smuggler's Haven
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SmugglersHarvesterAbility")
class SmugglersHarvesterAbility(g.DeferredAbility):
    """``Uprising.SmugglersHarvesterAbility`` (ctor @0x4d39b40: timing Agent;
    SelectionMode @0x4d39ce0 = Explicit; AlwaysRunImmediately @0x4d39cf0 =
    true; Cost @0x4d39c90 = ``HasPlayedToMakerSpaceThisTurn``)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SmugglersHarvesterAbility::Evaluate`` @0x4d39f90: 100."""

        return Answer(100.0, (), "Smuggler's Harvester | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SmugglersHarvesterAbility::ValueForPlayer`` @0x4d39dd0.

        Only when the candidate space is a Maker space: ``GetSpiceValue(1)``.
        """

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        if space is not None and _is_maker_space(space):
            v.add("Smuggler's Harvester Spice", p.spice_value(1))
        return v


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SmugglersHavenAgentAbility")
class SmugglersHavenAgentAbility(g.DeferredAbility):
    """``Uprising.SmugglersHavenAgentAbility`` (ctor @0x4d3a430: timing
    Agent; SelectionMode @0x4d3a520 = Optional; Cost @0x4d3a530 =
    ``HasResources.AtLeast(Spice, 4)``; not auto-run)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SmugglersHavenAgentAbility::Evaluate`` @0x4d3a8f0: 100 (always
        pays 4 spice for the VP when offered)."""

        return Answer(100.0, (), "Smuggler's Haven | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SmugglersHavenAgentAbility::ValueForPlayer`` @0x4d3a690.

        Inverted affordability (app bug kept, 17 §16): ``jne`` to the
        epilogue when ``CanAgentAbilityBePlayedWithSpace(space, Spice, 4)``
        is true, so the trade is valued only when the AI **cannot** afford
        it at that space.
        """

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        if space is None:
            return v
        if p.can_agent_ability_be_played_with_space(space, Attr.SPICE, 4):
            return v
        v.add("Smuggler's Haven Spice Cost", p.spice_value(-4))
        v.add("Smuggler's Haven VP", p.victory_point_value(1))
        return v


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SmugglersHavenRevealAbility")
class SmugglersHavenRevealAbility(g.DeferredAbility):
    """``Uprising.SmugglersHavenRevealAbility`` (ctor @0x4d3b680: timing
    Reveal; SelectionMode @0x4d3ba40 = Explicit; AlwaysRunImmediately
    @0x4d3ba50 = true; Cost @0x4d3b950 = ``IsSpyingOnMakerSpace(P)``)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def is_spying_on_maker_space(self, p: Profile) -> bool:
        """``SmugglersHavenRevealAbility::IsSpyingOnMakerSpace`` @0x4d3b770:
        ``BoardSpaces.Where(IsMakerSpace).Any(HasObservingSpy(P))``."""

        return any(
            _is_maker_space(space) and _has_observing_spy(p, space)
            for space in _board_spaces(p)
        )

    def meets_cost(self, p: Profile) -> bool:
        return self.is_spying_on_maker_space(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SmugglersHavenRevealAbility::Evaluate`` @0x4d3bcd0: 100."""

        return Answer(100.0, (), "Smuggler's Haven Reveal | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SmugglersHavenRevealAbility::ValueForPlayer`` @0x4d3bb40."""

        v = Summer()
        if self.is_spying_on_maker_space(p):
            v.add("Smuggler's Haven Spice", p.spice_value(2))
        return v


# ---------------------------------------------------------------------------
# Southern Elders (agent rider; the bond and reveal are in imperium_a.py)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SouthernEldersAgentAbility")
class SouthernEldersAgentAbility(g.DeferredAbility):
    """``Uprising.SouthernEldersAgentAbility`` (ctor @0x4d3c250: timing
    Agent; SelectionMode @0x4d3c3b0 = Explicit; AlwaysRunImmediately
    @0x4d3c3c0 = true; Cost @0x4d3c3d0 = ``HasPlayedFactionCard(BG)``)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def costed_troops(self, p: Profile) -> int:
        """``GetCostedTroops`` @0x4d3cb70: ``INPLAY(BG) ? 2 : 0``.

        UNTRACED: no caller found (spec §5 item 5).
        """

        return 2 if _in_play_other_of_faction(p, self.owner, "BeneGesserit") else 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SouthernEldersAgentAbility::Evaluate`` @0x4d3cd30: 100."""

        return Answer(100.0, (), "Southern Elders | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SouthernEldersAgentAbility::ValueForPlayer`` @0x4d3c540.

        INPLAY(BeneGesserit) (``<>c::b__10_0 @0x4d3cf30``) ->
        ``GetTroopValue(2, false)`` "Southern Elders Troops".
        """

        v = Summer()
        if _in_play_other_of_faction(p, self.owner, "BeneGesserit"):
            v.add("Southern Elders Troops", p.troop_value(2, False))
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``SouthernEldersAgentAbility::ValueInPileForOtherPlay`` @0x4d3c810:
        pattern BGP with ``X = GetTroopValue(2, false)``."""

        return g.bg_played_pile_value(
            p, pile, card, lambda: p.troop_value(2, False), "Bene Gesserit Played"
        )


# ---------------------------------------------------------------------------
# Space-Time Folding
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SpacetimeFoldingAbility")
class SpacetimeFoldingAbility(g.DeferredAbility):
    """``Uprising.SpacetimeFoldingAbility`` (ctor @0x4d3daf0: timing Agent;
    SelectionMode @0x4d3dc50 = Optional; Cost @0x4d3dd20 =
    ``HasImperiumCardInHand``; not auto-run).

    Targets (``<Targets>d__7 @0x4d3fa40``): the hand cards (the AI is always
    asked, even with one card) — the request's CARD entities.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpacetimeFoldingAbility::Evaluate`` @0x4d3e1d0.

        ``DiscardValue + CardDrawValue + GetBuyGains(PossiblePersuasionGain())``;
        the card is ``GetDiscardOrder(P, targets, spacingGuildBonus = true)
        .FirstOrDefault()`` (none -> value 0); a Spacing Guild card adds the
        draw and Buy Gains once more.
        """

        s = Summer()
        s.add("Discard", p.discard_value())
        s.add("Draw", p.card_draw_value())
        s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        order = p.discard_order(_targets(request, Kind.CARD), True)
        if not order:
            return Answer(0.0, None, "Space-time Folding no card")
        card = order[0]
        if _has_faction(card, "SpacingGuild"):
            s.add("Draw", p.card_draw_value())
            s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return Answer(s.sum, ((card.ref,),), f"Space-time Folding discard {card.ref}")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpacetimeFoldingAbility::ValueForPlayer`` @0x4d3de20.

        ``P.HandCount >= 2`` (``cmp eax,2; jl``) -> discard, draw, Buy Gains;
        at placement time (``withEntities.Any()``) the bonus draw is added
        when the first card of ``GetDiscardOrder(hand minus this card, true)``
        (``b__11_0 @0x4d3e6f0``) is a Spacing Guild card.
        """

        v = Summer()
        if len(p.ctx.hand) >= 2:
            v.add("Space-time Folding Discard", p.discard_value())
            v.add("Space-time Folding Draw", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
            if with_entities:
                others = [c for c in _hand(p) if c.ref != self.owner.ref]
                order = p.discard_order(others, True)
                if order and _has_faction(order[0], "SpacingGuild"):
                    v.add("Space-time Folding SG Draw", p.card_draw_value())
                    v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


# ---------------------------------------------------------------------------
# Spacing Guild's Favor
# ---------------------------------------------------------------------------


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.SpacingGuildsFavorRevealAbility"
)
class SpacingGuildsFavorRevealAbility(g.GainAnyInfluenceAbility):
    """``Uprising.SpacingGuildsFavorRevealAbility`` (ctor @0x4d40a00: timing
    Reveal; SelectionMode @0x4d40bc0 = Optional; Cost @0x4d40b00 =
    ``HasResources.AtLeast(Spice, 3)`` then ``CanGainInfluence``)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SpacingGuildsFavorRevealAbility::SelectionMode`` @0x4d40bc0:
        Optional (overrides ``GainAnyInfluenceAbility``'s Explicit)."""

        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpacingGuildsFavorRevealAbility::Evaluate`` @0x4d40e70.

        ``spiceCost = GetSpiceValue(-3)`` once; per faction track in target
        order (no shuffle): ``GetGainInfluenceValue(f, 1) + spiceCost``; the
        first sticks, later ones win only when strictly greater. Used iff
        > 0 (Optional).
        """

        spice_cost = p.spice_value(-3)
        stored: Answer | None = None
        for track in _targets(request, Kind.TRACK):
            s = Summer()
            s.merge(p.gain_influence_value(track.ref, 1, -1, False))
            s.add("3 Spice Cost", spice_cost)
            if stored is None or s.sum > stored.value:
                stored = Answer(
                    s.sum, ((track.ref,),), f"Spacing Guild's Favor {track.ref}"
                )
        if stored is None:
            return Answer(0.0, None, "Spacing Guild's Favor no track")
        return stored

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpacingGuildsFavorRevealAbility::ValueForPlayer`` @0x4d40cb0.

        App bug kept: the best +1 influence is counted twice (the base
        ``GainAnyInfluenceAbility`` V, then again), and nothing tests
        Spice >= 3.
        """

        v = super().value_for_player(p, with_entities)
        v.add("Spacing Guild's Favor 3 Spice Cost", p.spice_value(-3))
        v.add("Spacing Guild's Favor Influence", g.gain_any_influence_value(p, 1).sum)
        return v


@port(
    "worm.canis.abilities.TriggeredAbilities.Uprising.SpacingGuildsFavorDiscardAbility"
)
class SpacingGuildsFavorDiscardAbility(g.TriggeredAbility):
    """``Uprising.SpacingGuildsFavorDiscardAbility`` (ctor @0x4a9f300: no
    timing; trigger ``ImperiumDiscardedForUnload`` ``<IsValidFor>d__6
    @0x4a9fa00``; gains 2 spice; ``get_ShouldExhaust`` @0x4a9f420 = false).
    No AI hook: the interest in discarding the card comes from its
    ``IncentiveDiscard`` tag."""

    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Spy Network
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SpyNetworkAbility")
class SpyNetworkAbility(g.DeferredAbility):
    """``Uprising.SpyNetworkAbility`` (ctor @0x4d428a0: timing Reveal;
    SelectionMode @0x4d42a00 = Optional; Cost @0x4d42a10 =
    ``HasAtLeastSpiesOnBoard(2)``; not auto-run).

    Targets @0x4d42a70: P's spies on the board — the request's SPY entities.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``HasAtLeastSpiesOnBoard(2)``: 2+ of P's spies on the board."""

        return len(p.ctx.me.spy_post_ids) >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpyNetworkAbility::Evaluate`` @0x4d42e10.

        ``IntrigueValue`` + ``RecallSpyValue().Sum`` for the spy of
        ``GetRecallSpy`` (worst post); no spy -> value 0.
        """

        s = Summer()
        s.add("Intrigue Value", p.intrigue_value())
        spy, _ = p.recall_spy(_targets(request, Kind.SPY))
        if spy is None:
            return Answer(0.0, None, "Spy Network no spy")
        s.add(f"Remove spy {spy.ref}", p.recall_spy_value().sum)
        return Answer(s.sum, ((spy.ref,),), f"Spy Network recall {spy.ref}")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpyNetworkAbility::ValueForPlayer`` @0x4d42c50 (``MeetsCost``)."""

        v = Summer()
        if self.meets_cost(p):
            v.add("Recall Spy Value", p.recall_spy_value().sum)
            v.add("Intrigue Value", p.intrigue_value())
        return v


# ---------------------------------------------------------------------------
# Stilgar, The Devoted (Liet Kynes classes)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.BaseSet.LietKynesRevealAbility")
class LietKynesRevealAbility(g.RevealAbility):
    """``BaseSet.LietKynesRevealAbility`` (Stilgar's reveal box)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LietKynesRevealAbility::ValueForPlayer`` @0x4ca4810.

        Generic reveal V, then ``GetPersuasionValue(2 * n)`` "Liet Kynes
        Reveal" (``add eax,eax``; added even for n = 0) with n = the Fremen
        cards of ``hand ⧺ AllCardsInPlay`` (``<>c::b__7_0 @0x4ca4bb0``; this
        card included). ``LietKynesFremenRevealBonus`` is never read.
        """

        v = super().value_for_player(p, with_entities)
        n = sum(1 for e in (*_hand(p), *_in_play(p)) if _has_faction(e, "Fremen"))
        v.add("Liet Kynes Reveal", p.persuasion_value(2 * n))
        return v


@port("worm.canis.abilities.PlayAbilities.BaseSet.LietKynesAbility")
class LietKynesAbility(g.TriggeredAbility):
    """``BaseSet.LietKynesAbility`` (ctor @0x4ccedd0: timing Reveal;
    ``get_ShouldExhaust`` @0x4ccf0d0 = false): engine only, no AI hook."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Subversive Advisor
# ---------------------------------------------------------------------------


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.SubversiveAdvisorTrashSelfAbility"
)
class SubversiveAdvisorTrashSelfAbility(g.TrashSelfAbility):
    """``Uprising.SubversiveAdvisorTrashSelfAbility`` (ctor @0x4d44fa0: timing
    Agent). Inherited Implicit + always auto-run: never asked, no AI hook.
    The placement value is ``PowerPlayAgentAbility``'s (losing the card is
    not priced)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d45110: ``PlayedSpace?.Faction != None`` (``setne``);
        a null ``PlayedSpace`` is true (``je 0x4d45183`` -> ``mov r15b, 1``).
        Ours: no open Agent turn of this seat, or its space has a faction."""

        space = _active_space(p)
        return space is None or space.has("Faction")


# ---------------------------------------------------------------------------
# The Beast's Spoils (promo; not in a normal game)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Promo.TheBeastsSpoilsCrysknifeAbility")
class TheBeastsSpoilsCrysknifeAbility(g.TrashAbility):
    """``Promo.TheBeastsSpoilsCrysknifeAbility`` (ctor @0x4d95350: timing
    Agent; Cost @0x4d954a0 = ``BattleIconList.Contains(Crysknife)`` then the
    ``TrashAbility`` cost). E/V/SelectionMode are ``TrashAbility``'s; V is
    **not** gated by the icon."""

    timing: ClassVar[Timing] = Timing.AGENT

    def meets_cost(self, p: Profile) -> bool:
        return "Crysknife" in _battle_icons(p)


class _BeastsSpoilsIconAbility(g.DeferredAbility):
    """Shared shape of The Beast's Spoils' mouse and thopter riders (not an
    app class): Explicit, auto-run, timing Agent, Cost = the exact battle
    icon (not Wildcard), E = 100, V = the gain if ``MeetsCost``."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True
    ICON: ClassVar[str] = ""
    LABEL: ClassVar[str] = ""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return self.ICON in _battle_icons(p)

    def gain_value(self, p: Profile) -> float:
        raise NotImplementedError

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), f"{type(self).__name__} | 100")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if self.meets_cost(p):
            v.add(self.LABEL, self.gain_value(p))
        return v


@port("worm.canis.abilities.ActivatedAbilities.Promo.TheBeastsSpoilsDesertMouseAbility")
class TheBeastsSpoilsDesertMouseAbility(_BeastsSpoilsIconAbility):
    """``Promo.TheBeastsSpoilsDesertMouseAbility`` (Cost @0x4d95820,
    SelectionMode @0x4d95950, AlwaysRunImmediately @0x4d95960, E @0x4d95bb0,
    V @0x4d95a40 = ``GetSpiceValue(1)`` "The Beast's Spoils Spice")."""

    ICON: ClassVar[str] = "DesertMouse"
    LABEL: ClassVar[str] = "The Beast's Spoils Spice"

    def gain_value(self, p: Profile) -> float:
        return p.spice_value(1)


@port("worm.canis.abilities.ActivatedAbilities.Promo.TheBeastsSpoilsOrnithopterAbility")
class TheBeastsSpoilsOrnithopterAbility(_BeastsSpoilsIconAbility):
    """``Promo.TheBeastsSpoilsOrnithopterAbility`` (Cost @0x4d96110,
    SelectionMode @0x4d96240, AlwaysRunImmediately @0x4d96250, E @0x4d964a0,
    V @0x4d96330 = ``GetTroopValue(1, false)`` "The Beast's Spoils Troop")."""

    ICON: ClassVar[str] = "Ornithopter"
    LABEL: ClassVar[str] = "The Beast's Spoils Troop"

    def gain_value(self, p: Profile) -> float:
        return p.troop_value(1, False)


# ---------------------------------------------------------------------------
# Treacherous Maneuver
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.BaseSet.ThufirHawatRevealAbility")
class ThufirHawatRevealAbility(g.RevealAbility):
    """``BaseSet.ThufirHawatRevealAbility``: overrides only
    ``GetRevealPreviewValue @0x4cb72a0``; AI value = the generic reveal V
    (1 Persuasion) + ``RevealGainIntrigueAbility`` V."""


@port("worm.canis.abilities.ActivatedAbilities.Uprising.TreacherousManeuverAbility")
class TreacherousManeuverAbility(g.DeferredAbility):
    """``Uprising.TreacherousManeuverAbility`` (ctor @0x4d453a0: timing
    Agent; SelectionMode @0x4d45700 = Optional; not auto-run; the archetype
    DeferValue 3 is unused, own E).

    Targets (``<Targets>b__9_0 @0x4d466b0``): Emperor hand cards other than
    this one — the request's CARD entities.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d457d0: an Emperor hand card other than this one
        (``b__0 @0x4d468e0``) and a ``GainInfluenceAbility`` on the visited
        space (``b__1 @0x4d469f0``; "runnable" read as present)."""

        if not any(
            c.ref != self.owner.ref and _has_faction(c, "Emperor") for c in _hand(p)
        ):
            return False
        space = _active_space(p)
        return space is not None and _GAIN_INFLUENCE_SPACE_ABILITY in space.ability_ids

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TreacherousManeuverAbility::Evaluate`` @0x4d46050.

        ``GetCardToTrash(targets, 0.0)`` first (it shuffles; never finds an
        Emperor card in Uprising); no active space -> 0; else the junk card,
        else the first target with ``PersuasionCost < 4`` (``b__15_0
        @0x4d46840``: ``cmp eax,4; setl``), else (climax only) ``targets[0]``;
        answered at the literal 200.0.
        """

        targets = _targets(request, Kind.CARD)
        card, _ = p.card_to_trash(targets, 0.0)
        if _active_space(p) is None:
            return Answer(0.0, None, "Treacherous Maneuver no space")
        if card is None:
            card = next((c for c in targets if c.int_attr("PersuasionCost") < 4), None)
            if card is None:
                if not p.is_climax():
                    return Answer(0.0, None, "Treacherous Maneuver keep")
                if not targets:
                    return Answer(0.0, None, "Treacherous Maneuver no target")
                card = targets[0]
        return Answer(200.0, ((card.ref,),), f"Treacherous Maneuver | 200 | {card.ref}")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TreacherousManeuverAbility::ValueForPlayer`` @0x4d45b90.

        Emperor hand cards other than this one (``b__0 @0x4d46c30``); none ->
        empty. ``GetCardToTrash(emp, 0.0)`` (shuffles) before the space test;
        without junk and without an Emperor card of cost < 4 (``b__14_1
        @0x4d467a0``) only in the climax; then "Treacherous Maneuver Bonus
        Influence" = the space's influence with +1 minus the normal value.
        Neither trashed card is priced.
        """

        v = Summer()
        emperor = [
            c
            for c in _hand(p)
            if _has_faction(c, "Emperor") and c.ref != self.owner.ref
        ]
        if not emperor:
            return v
        card, _ = p.card_to_trash(emperor, 0.0)
        space = g.collect_first(with_entities, Kind.SPACE)
        if space is None:
            return v
        if card is None and not any(c.int_attr("PersuasionCost") < 4 for c in emperor):
            if not p.is_climax():
                return v
        v.add("Treacherous Maneuver Bonus Influence", _bonus_influence(p, space))
        return v


# ---------------------------------------------------------------------------
# Tread in Darkness (the draw class is generic.BeneGesseritDrawAbility)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.BeneGesseritTrashAbility")
class BeneGesseritTrashAbility(g.TrashAbility):
    """``Uprising.BeneGesseritTrashAbility`` (ctor @0x4cede20: timing Agent;
    Cost @0x4cedf70 = ``HasPlayedFactionCard(BG)`` then the ``TrashAbility``
    cost). SelectionMode (Explicit) and E (junk or nothing at 1.0) are
    ``TrashAbility``'s."""

    timing: ClassVar[Timing] = Timing.AGENT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeneGesseritTrashAbility::ValueForPlayer`` @0x4cee030.

        INPLAY(BeneGesserit) (``b__6_0 @0x4cee700``) -> the ``TrashAbility`` V
        (``TrashCardValue + TrashMod()``), else empty.
        """

        if _in_play_other_of_faction(p, self.owner, "BeneGesserit"):
            return super().value_for_player(p, with_entities)
        return Summer()

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``BeneGesseritTrashAbility::ValueInPileForOtherPlay`` @0x4cee2a0:
        pattern BGP with ``X = 0.75 * TrashCardValue`` (f64 literal 0.75)."""

        return g.bg_played_pile_value(
            p, pile, card, lambda: 0.75 * p.trash_card_value(), "Bene Gesserit Played"
        )


# ---------------------------------------------------------------------------
# Undercover Asset
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.BaseSet.UndercoverAssetRevealAbility")
class UndercoverAssetRevealAbility(g.RevealAbility):
    """``BaseSet.UndercoverAssetRevealAbility``: overrides only
    ``GetRevealPreviewValue @0x4cce1c0``; the agent rule (ignore influence
    requirements) is engine legality, no AI hook."""


@port("worm.canis.abilities.ActivatedAbilities.Uprising.UndercoverAssetAbility")
class UndercoverAssetAbility(g.DeferredAbility):
    """``Uprising.UndercoverAssetAbility`` (ctor @0x4d47fc0: timing Reveal,
    PlaceSpyNoUndo; SelectionMode @0x4d48170 = Explicit; Cost @0x4d48180 =
    NoCost; not auto-run).

    Targets (``<Targets>d__9 @0x4d49bc0``): one custom choice, option 0 = Spy,
    option 1 = 2 Strength. The post of the spy is a later ``PlaceSpy`` prompt.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``UndercoverAssetAbility::Evaluate`` @0x4d48570.

        ``Upd(SpyValue().Sum, [0])`` (first: sticks), then
        ``Upd(GetStrengthValue(2, false), [1])`` (strictly greater only: ties
        go to the spy).
        """

        spy = p.spy_value().sum
        answer = Answer(spy, ((0,),), "Undercover Asset Place Spy")
        strength = p.strength_value(2, False)
        if strength > answer.value:
            answer = Answer(strength, ((1,),), "Undercover Asset Strength")
        return answer

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``UndercoverAssetAbility::ValueForPlayer`` @0x4d483a0:
        ``Math.Max(SpyValue().Sum, GetStrengthValue(2, false))``."""

        v = Summer()
        v.add(
            "Undercover Asset Reveal",
            max(p.spy_value().sum, p.strength_value(2, False)),
        )
        return v


# ---------------------------------------------------------------------------
# Unswerving Loyalty (Immortality's Shadout Mapes class)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Immortality.ShadoutMapesAbility")
class ShadoutMapesAbility(g.DeferredAbility):
    """``Immortality.ShadoutMapesAbility`` (ctor @0x4e1d660: timing Reveal;
    SelectionMode @0x4e1d870 = Optional; Cost @0x4e1d880 = a garrisoned or a
    deployed unit; not auto-run). Not on an Uprising archetype itself: the
    base of ``UnswervingLoyaltyAbility``.

    Targets (``<Targets>d__6 @0x4e1f0b0``): one "ChooseOne" custom choice
    built in this order — deploy (when ``P.CanDeploy`` and a garrison troop),
    then retreat (when a troop is deployed). ``request.infos[0].options`` are
    those indices; ``evaluate`` answers the app's raw index.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShadoutMapesAbility::Evaluate`` @0x4e1db80.

        With a garrison troop: ``GetUnitsToDeploy([one troop], -1)`` non-empty
        -> option 0 at 100; the retreat index is 1 whenever the garrison holds
        a troop (even when the targets have no deploy option — app edge case
        kept, the engine's handling is UNTRACED). Else a deployed troop and
        ``GetTroopsToRetreat(1) > 0`` -> retreat at 100. Else
        ``Upd(0.0, [])``.
        """

        me = p.ctx.me
        retreat_index = 0
        if me.troops_garrison > 0:
            units = p.units_to_deploy(1, -1)  # edx = 0xffffffff
            retreat_index = 1
            if units > 0:
                return Answer(100.0, ((0,),), "Shadout Mapes (Reveal) | Deploy | 100")
        if me.troops_conflict > 0 and p.troops_to_retreat(1) > 0:  # jle
            return Answer(
                100.0, ((retreat_index,),), "Shadout Mapes (Reveal) | Retreat | 100"
            )
        return Answer(0.0, (), "Shadout Mapes (Reveal) | 0")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShadoutMapesAbility::ValueForPlayer`` @0x4e1da10: the constant
        ``ShadoutMapesRevealValue`` (not gated by the bond or by units)."""

        v = Summer()
        v.add("Shadout Mapes Reveal Value", p.C.ShadoutMapesRevealValue)
        return v


@port("worm.canis.abilities.ActivatedAbilities.Uprising.UnswervingLoyaltyAbility")
class UnswervingLoyaltyAbility(ShadoutMapesAbility):
    """``Uprising.UnswervingLoyaltyAbility`` (ctor @0x4d4d4c0 ->
    ``ShadoutMapesAbility`` ctor). Overrides ``Cost`` @0x4d4d5a0 (another
    Fremen card in play, then the Shadout Mapes cost: engine gate) and P."""

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``UnswervingLoyaltyAbility::ValueInPileForOtherPlay`` @0x4d4d710:
        FDP."""

        return _fremen_deck_synergy(p, pile, card)


# ---------------------------------------------------------------------------
# Weirding Woman
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.Uprising.WeirdingWomanAgentAbility")
class WeirdingWomanAgentAbility(g.AgentAbility):
    """``Uprising.WeirdingWomanAgentAbility``: overrides
    ``RunImmediateEffects @0x4c5ac90`` and ``Undo`` only (engine); E/V are
    the generic ``AgentAbility`` ones."""


@port("worm.canis.abilities.ActivatedAbilities.Uprising.WeirdingWomanAbility")
class WeirdingWomanAbility(g.DeferredAbility):
    """``Uprising.WeirdingWomanAbility`` (ctor @0x4d4efd0: timing Agent;
    ``IsUnexhausted`` @0x4d4f130 = true; SelectionMode @0x4d4f140 =
    Explicit; Cost @0x4d4f150 = ``HasPlayedFactionCard(BG)`` and this card
    in play; not auto-run)."""

    timing: ClassVar[Timing] = Timing.AGENT
    is_unexhausted: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WeirdingWomanAbility::Evaluate`` @0x4d4fda0: ``Upd(100.0, [])``."""

        return Answer(100.0, (), "Weirding Woman | 100")

    def _played_value(self, p: Profile) -> float:
        """``r``: this card's first ``RevealAbility`` V (0 if none)."""

        return _first_reveal_value(p, self.owner)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WeirdingWomanAbility::ValueForPlayer`` @0x4d4f4a0.

        INPLAY(BeneGesserit) (``<>c::b__12_0 @0x4d50050``) -> this card's
        reveal value "Weirding Woman Return To Hand" + ``WeirdingWomanMod``.
        """

        v = Summer()
        if _in_play_other_of_faction(p, self.owner, "BeneGesserit"):
            v.add("Weirding Woman Return To Hand", self._played_value(p))
            v.add("Weirding Woman Mod", p.C.WeirdingWomanMod)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``WeirdingWomanAbility::ValueInPileForOtherPlay`` @0x4d4f880:
        pattern BGP with ``X = 0.75 * (r + WeirdingWomanMod)`` (f64 0.75)."""

        return g.bg_played_pile_value(
            p,
            pile,
            card,
            lambda: 0.75 * (self._played_value(p) + p.C.WeirdingWomanMod),
            "Bene Gesserit Played",
        )


# ---------------------------------------------------------------------------
# Wheels Within Wheels
# ---------------------------------------------------------------------------


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.WheelsWithinWheelsEmperorAbility"
)
class WheelsWithinWheelsEmperorAbility(_InfluenceRiderAbility):
    """``Uprising.WheelsWithinWheelsEmperorAbility`` (ctor @0x4d51380, Cost
    @0x4d514e0, SelectionMode @0x4d51500, AlwaysRunImmediately @0x4d51510).

    V ``@0x4d515f0``: Emperor influence >= 2 -> ``GetSolariValue(2)``.
    """

    FACTION: ClassVar[str] = "emperor"
    LABEL: ClassVar[str] = "Wheels Within Wheels Emperor Solari"

    def gain_value(self, p: Profile) -> float:
        return p.solari_value(2)


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.WheelsWithinWheelsSpacingGuildAbility"
)
class WheelsWithinWheelsSpacingGuildAbility(_InfluenceRiderAbility):
    """``Uprising.WheelsWithinWheelsSpacingGuildAbility`` (ctor @0x4d51ae0,
    Cost @0x4d51c40, SelectionMode @0x4d51c60, AlwaysRunImmediately
    @0x4d51c70).

    V ``@0x4d51d50``: Spacing Guild influence >= 2 -> ``GetSpiceValue(1)``.
    """

    FACTION: ClassVar[str] = "spacing_guild"
    LABEL: ClassVar[str] = "Wheels Within Wheels Spacing Guild Spice"

    def gain_value(self, p: Profile) -> float:
        return p.spice_value(1)
