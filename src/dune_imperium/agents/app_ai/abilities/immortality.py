"""Ports of the app's Immortality ability classes (spec/immortality.md §3-§7).

Research and Tleilaxu-track gains, the playmat abilities, graft
(``GraftCardEvaluator`` and ``GraftAgentAbility``), the 25 Imperium cards,
Experimentation, the Tleilaxu cards and the 11 Intrigue cards.

Spec: ``analysis/ai/spec/immortality.md`` (assets checkout; the Errata at the
end of the file override its body). Addresses are build
dad97e2021144d45b5b4f022e07bd3b3. Each port subclasses the port of its app
base class (``worm-canis.dll.cs``) and registers itself with
``@port("<full app class name>")``. Engine-side members as in
``generic.py``: ``timing`` (the ``.ctor``'s ``AbilityTiming``),
``selection_mode(p)``, ``always_run_immediately`` /
``can_run_immediately(p)``, ``contextually_deferred``, ``meets_cost(p)`` where
an AI hook calls ``MeetsCost`` (elsewhere it documents the app's ``Cost`` for
the decision windows; the engine owns legality).

Request / answer encoding (``abilities/base``; as in ``generic.py`` and
``intrigue.py``): ``request.infos[i]`` is the app's target information ``i``.
Answers follow ``WormAIChoiceSelectionWithTargets`` (``intrigue._Choice``):
``Answer.response is None`` = nothing stored (value 0); ``()`` = "use" with
an empty response list (``UpdateSelectionTargets(v, src, null)``);
``((),)`` = an empty entity list (``Array.Empty``, which makes later updates
need a strictly greater value); ``((ref, ...),)`` = chosen refs / option
indices per target info. Per class:

- Research (``GainResearchAbility``, Industrial Espionage, Breakthrough):
  ``infos[0].entities`` = the reachable research spaces (``Kind.SPACE``; ref
  ``c<col>r<row>`` or ``research:c<col>r<row>``, the profile's research space
  entity); the response names the chosen entity's ref.
- Faction choices (For Humanity reveal, Interstellar Conspiracy, Long Reach,
  Disguised Bureaucrat): ``infos[0].entities`` = faction tracks
  (``Kind.TRACK``, ref our faction id).
- Unit choices (Return Specimen, Counterattack Plot): ``infos[0].options`` one
  index per unit, the response the first ``n`` indices. Tleilaxu Surgeon's
  reveal and Piter: ``infos[0].options`` one zone code per target troop in the
  app's order (``0`` garrison, ``1`` deployed; ``GetTroopTargets`` lists the
  garrison troops first); the response names the chosen zone codes.
- Custom choices (Family Atomics ``(1,)`` = confirm, High Priority Travel
  ``0`` draw / ``1`` deploy, Reclaimed Forces ``0`` troops / ``1`` Tleilaxu,
  Stitched Horror ``0`` water / ``1`` troop / ``2`` trash / ``3`` Tleilaxu,
  Tleilaxu Master's destination ``0`` / ``1`` to hand): ``((option, ...),)``.
  Stitched Horror's trash option carries its dependent card list in
  ``infos[1].entities``; Tleilaxu Master's destination picker (when offered)
  is ``infos[1].options``.
- Cards (Beguiling Pheromones, Replacement Eyes, Harvest Cells, the graft
  partner, Imperium Ceremony's kept Intrigue, Trash Intrigue): ``Kind.CARD``
  / ``Kind.INTRIGUE`` entities of ``infos[0]``.

Graft (§4): ``GraftAgentAbility.evaluate`` values each legal space with the
best partner (``best_partners`` exposes the partner per space for the
decision windows); ``graft_card_evaluate`` is ``GraftCardEvaluator::Evaluate``
(the app's state-50 partner question); ``graft_cards_value`` is
``GraftCardEvaluator::GraftCardsValue``. ``convert_specimen_evaluate`` is
``ConvertSpecimenEvaluator`` (§8).
"""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, ClassVar, Final

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
from dune_imperium.agents.app_ai.abilities.intrigue import (
    COMBAT_RESOLUTION_TIMING,
    COMBAT_TIMING,
    IntrigueAbility,
    StrengthIntrigueAbility,
    _Choice,
    _dsum,
    _EndgameIntrigueAbility,
    _in_player_turn,
    _intrigue_hand_count,
    _persuasion,
)
from dune_imperium.agents.app_ai.catalog import FACTION_NAMES, card_entity
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.rules.agent_turn import _placements_for_card

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA: Final = "worm.canis.abilities.ActivatedAbilities."
_PA: Final = "worm.canis.abilities.PlayAbilities."
_TA: Final = "worm.canis.abilities.TriggeredAbilities."

#: ``PlayerTurnTypes`` (intrigue.py keeps the same values).
_UNDETERMINED: Final = 0
_REVEAL_TURN: Final = 2

_APP_TO_FACTION: Final = {app: ours for ours, app in FACTION_NAMES.items()}

# App archetypes the Immortality code tests by ``ArchID`` / ``IsArchetype``.
_GHOLA: Final = "TleilaxuArchetypes.Immortality.Ghola"
_SHOW_OF_STRENGTH: Final = "ImperiumArchetypes.Immortality.ShowofStrength"
_RESEARCH_STATION_IMMORTALITY: Final = (
    "SpaceArchetypes.Immortality.ResearchStationImmortality"
)
_INTERSTELLAR_SHIPPING: Final = "SpaceArchetypes.RiseOfIx.InterstellarShipping"
_SMUGGLING: Final = "SpaceArchetypes.RiseOfIx.Smuggling"

#: ``GholaAgentAbility`` ``.ctor`` @0x4c6ae50: the three penalty lists.
_GHOLA_MINUS_ONE: Final = frozenset(
    {
        "ImperiumArchetypes.RiseOfIx.Sayyadina",
        "ImperiumArchetypes.Immortality.TleilaxuSurgeon",
        "ImperiumArchetypes.RiseOfIx.IxGuildCompact",
        "ImperiumArchetypes.Immortality.DissectingKit",
        "ImperiumArchetypes.RiseOfIx.Appropriate",
        "ImperiumArchetypes.RiseOfIx.WeirdingWay",
    }
)
_GHOLA_MINUS_THREE: Final = frozenset(
    {
        "ImperiumArchetypes.BaseSet.FoldspaceImperium",
        "ImperiumArchetypes.BaseSet.ImperialSpy",
        "ImperiumArchetypes.BaseSet.KwisatzHaderach",
        "ImperiumArchetypes.Immortality.Occupation",
    }
)
_GHOLA_MINUS_FIVE: Final = frozenset(
    {
        "ImperiumArchetypes.BaseSet.PowerPlay",
        "ImperiumArchetypes.BaseSet.SeekAllies",
        "TleilaxuArchetypes.Immortality.BeguilingPheromones",
        "TleilaxuArchetypes.Immortality.TwistedMentat",
        "TleilaxuArchetypes.Immortality.Usurp",
        "ImperiumArchetypes.RiseOfIx.Treachery",
        "ImperiumArchetypes.Uprising.SubversiveAdvisor",
        "ImperiumArchetypes.Uprising.Overthrow",
        "ImperiumArchetypes.Uprising.SardaukarCoordination",
        "ImperiumArchetypes.Uprising.TreacherousManeuver",
        "ImperiumArchetypes.Uprising.DoubleAgent",
        "ImperiumArchetypes.Uprising.UndercoverAsset",
    }
)
_SMUGGLERS_HAVEN: Final = "ImperiumArchetypes.Uprising.SmugglersHaven"
_STEERSMAN: Final = "ImperiumArchetypes.Uprising.Steersman"
_JUNCTION_HEADQUARTERS: Final = "ImperiumArchetypes.Uprising.JunctionHeadquarters"
_LONG_LIVE_THE_FIGHTERS: Final = "ImperiumArchetypes.Uprising.LongLivetheFighters"
_PRICE_IS_NO_OBJECT: Final = "ImperiumArchetypes.Uprising.PriceisNoObject"
_CARGO_RUNNER: Final = "ImperiumArchetypes.Uprising.CargoRunner"


# ---------------------------------------------------------------------------
# Honest reads (AppContext rules) and small app helpers
# ---------------------------------------------------------------------------


def _targets(request: Request, kind: Kind, index: int = 0) -> list[Entity]:
    """``choice.GetTargets(...).OfType<T>()``: one target info's entities."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is kind]


def _options(request: Request, index: int = 0) -> tuple[int, ...]:
    """The option ints / unit indices of target information ``index``."""

    if len(request.infos) <= index:
        return ()
    return request.infos[index].options


def _hand(p: Profile) -> list[Entity]:
    """``P.Hand.children.OfType<WormImperiumPlayable>()`` (hand order)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.hand]


def _in_play(p: Profile) -> list[Entity]:
    """``P.AllCardsInPlay`` (our ``in_play``: PlayArea and ActiveAgentArea)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.me.in_play]


def _row_cards(p: Profile) -> list[Entity]:
    """``WormMatchExtensions::ImperiumRowCards`` (row order, public)."""

    return [card_entity(i) for i in p.ctx.imperium_row]


def _all_imperium_cards(p: Profile) -> list[Entity]:
    """``WormPlayer::get_AllImperiumCards @0x4835810``.

    Deck ++ Hand ++ Discard ++ PlayArea ++ ActiveAgentArea; the own deck is
    read as a multiset only (sorted card ids). Callers only count.
    """

    me = p.ctx.me
    deck = sorted(p.ctx.deck_multiset.elements())
    return [
        *(card_entity(c, p.ctx.seat) for c in deck),
        *(card_entity(i, p.ctx.seat) for i in (*me.hand, *me.discard_pile)),
        *_in_play(p),
    ]


def _has_tag(card: Entity, tag: str) -> bool:
    """``WormEntityExtensions::Tags(c).Contains(tag)``."""

    return tag in card.list_attr("Tags")


def _has_faction(card: Entity, faction: str) -> bool:
    """``WormEntityExtensions::FactionsList(c).Contains(f)`` (app name).

    ``FactionsList @0x482ddd0`` reads ``FactionList`` (cards only); a space
    archetype has only ``Faction``, so a space never matches (Errata §5.8).
    """

    return faction in g.card_factions(card)


def _with_graft(with_entities: Sequence[Entity]) -> bool:
    """ "with-graft" (spec §0): ``with.OfType<WormImperiumPlayable>().Any()``.

    True only inside ``GraftCardsValue`` (``with = [partner, space]``); plain
    ``AgentAbility::Evaluate`` passes ``[space]``.
    """

    return any(e.kind is Kind.CARD for e in with_entities)


def _partner(with_entities: Sequence[Entity]) -> Entity | None:
    """``with.OfType<WormImperiumPlayable>().FirstOrDefault()``."""

    for entity in with_entities:
        if entity.kind is Kind.CARD:
            return entity
    return None


def _markers(p: Profile) -> int:
    """``P.GeneticMarkers`` (``WormPlayer::get_GeneticMarkers @0x48358f0``)."""

    return p.ctx.genetic_markers()


def _tleilaxu(p: Profile) -> int:
    """``P.GetTleilaxuInfluence() @0x48446a0``: Tleilaxu rank 0..7."""

    return p.ctx.tleilaxu_influence()


def _can_gain_tleilaxu(p: Profile) -> bool:
    """``CanGainTleilaxuInfluence @0x4a77ca0``: rank below 7."""

    return _tleilaxu(p) < 7


def _has_grafted(p: Profile, card_ref: str) -> bool:
    """``HasGrafted`` (``CanBePaid @0x4a79c60``): the ability's own card
    carries a ``GraftedTo`` id (``!= EntityID.Empty``).

    Ours: ``card_ref`` is one of this Agent turn's grafted pair (own frame).
    Another turn's or another card's graft does not count.
    """

    return _grafted_partner_of(p, card_ref) is not None


def _grafted_partner_of(p: Profile, card_ref: str) -> Entity | None:
    """``owner.GetGraftedCard()``: the other card of this turn's pair.

    Judgement: ours is whichever of the frame's ``card_id`` / graft partner
    is not ``card_ref`` (the engine swaps them as the boxes resolve); None
    when ``card_ref`` is not one of the pair.
    """

    pair = p.ctx.graft_cards()
    if pair is None or card_ref not in pair:
        return None
    first, second = pair
    other = second if first == card_ref else first
    if other == card_ref:
        return None
    return card_entity(other, p.ctx.seat)


def _in_alliance(p: Profile, faction: str) -> bool:
    """``WormPlayer::InAlliance(f)`` (our faction id)."""

    return faction in p.ctx.me.alliance_faction_ids


def _research_id(space: Entity) -> str:
    """Our research space id of a research ``WormSpace`` target."""

    prefix = "research:"
    return space.ref[len(prefix) :] if space.ref.startswith(prefix) else space.ref


def _dmax(a: float, b: float) -> float:
    """``System.Math.Max(double, double)``: NaN wins, else the larger."""

    if a != a:
        return a
    if b != b:
        return b
    return a if a > b else b


def _ieee_div(numerator: float, denominator: float) -> float:
    """C# ``double`` division: ``x / 0`` is +-Infinity or NaN, never an error."""

    if denominator == 0.0:
        if numerator == 0.0 or numerator != numerator:
            return float("nan")
        sign = 1.0 if (numerator > 0) == (denominator >= 0) else -1.0
        return sign * float("inf")
    return numerator / denominator


def _is_bad_intrigue(p: Profile, card: Entity) -> bool:
    """``WormIntriguePlayable::IsBadIntrigue(match, P)`` @0x4836d70.

    ``Abilities.OfType<IntrigueAbility>().Any(a => a.IsBadIntrigue(M, P))``
    (vslot 87; intrigues.md §4.5).
    """

    return any(
        isinstance(a, IntrigueAbility) and a.is_bad_intrigue(p)
        for a in abilities_of(card)
    )


def _first_agent_ability(card: Entity) -> g.AgentAbility | None:
    """``card.Abilities.OfType<AgentAbility>().FirstOrDefault()``."""

    for ability in abilities_of(card):
        if isinstance(ability, g.AgentAbility):
            return ability
    return None


def _first_reveal_ability(card: Entity) -> g.RevealAbility | None:
    """``card.Abilities.OfType<RevealAbility>().FirstOrDefault()``."""

    for ability in abilities_of(card):
        if isinstance(ability, g.RevealAbility):
            return ability
    return None


def _troop_choice(p: Profile, zones: Sequence[int], take: int) -> tuple[int, ...]:
    """The troop pick of Tleilaxu Surgeon's reveal and Piter (zone codes).

    ``troops.Count != 2`` -> ``OrderByDescending(t => t.Parent.IsNamed(
    sortEntity)).Take(take)``, ``sortEntity`` = Garrison when
    ``EstimatedConflictRank(0)`` has a value, else Deployed (stable sort;
    ``true`` before ``false``). Exactly two targets are kept as they are.
    """

    if len(zones) == 2:
        return tuple(zones)
    sort_zone = 0 if p.estimated_conflict_rank(0) is not None else 1
    ordered = sorted(zones, key=lambda zone: 0 if zone == sort_zone else 1)
    return tuple(ordered[:take])


# ===========================================================================
# §3.1 GainResearchAbility family
# ===========================================================================


@port(_AA + "Immortality.GainResearchAbility")
class GainResearchAbility(g.DeferredAbility):
    """``Immortality.GainResearchAbility`` (abstract; spec §3.1).

    Never auto-run (``AlwaysRunImmediately`` not overridden) and Explicit:
    every Research icon waits in the post-action / post-reveal prompt and
    forces it.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GainResearchAbility::SelectionMode @0x4e03230``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4e03240``: ``GeneticMarkers > 1 ? HasDrawableCard :
        NoCost`` (with both markers Research draws a card)."""

        if _markers(p) > 1:
            return g._has_drawable_card(p)
        return True

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainResearchAbility::ValueForPlayer @0x4e035e0``: the base V
        (empty) merged with ``ResearchValue()`` (no cost check)."""

        v = Summer()
        v.merge(p.research_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainResearchAbility::Evaluate @0x4e03720`` (spec §3.1, Errata).

        ``Upd(1.0, src, Array.Empty)`` (the "no space" answer; it stores an
        empty entity list, so a space needs strictly more than 1.0), then
        each next research space (``NextIndices`` order, lower index first)
        at ``SpaceValue + 1.0`` ("Value floor for Gain Research").
        """

        choice = _Choice()
        choice.update_targets(1.0, ())
        for space in _targets(request, Kind.SPACE):
            s = p.research_space_value(_research_id(space))
            s.add("Value floor for Gain Research", 1.0)
            choice.update_targets(s.sum, (space.ref,))
        return choice.answer("Gain Research")


@port(_AA + "Immortality.GainResearchAgentAbility")
class GainResearchAgentAbility(GainResearchAbility):
    """``GainResearchAgentAbility`` (``.ctor @0x4e05770``: timing Agent;
    Experimentation, Bene Tleilax Researcher, Scientific Breakthrough, the
    Immortality Research Station)."""

    timing: ClassVar[Timing] = Timing.AGENT


@port(_AA + "Immortality.GainResearchRevealAbility")
class GainResearchRevealAbility(GainResearchAbility):
    """``GainResearchRevealAbility`` (``.ctor @0x4e05970``: timing Reveal;
    Tleilaxu Master x2)."""

    timing: ClassVar[Timing] = Timing.REVEAL


@port(_AA + "Immortality.GainResearchCustomAbility")
class GainResearchCustomAbility(GainResearchAbility):
    """``GainResearchCustomAbility`` (playmat; research-space bonus).

    ``Cost @0x4e05230`` adds ``HasCustomAbility`` (the research space's
    grant, held while our research bonus is pending); ``IsUnexhausted
    @0x4e052c0`` = true; timing None. AI hooks inherited (§3.4).
    """


# ===========================================================================
# §3.2 GainTleilaxuInfluenceAbility family
# ===========================================================================


@port(_AA + "Immortality.GainTleilaxuInfluenceAbility")
class GainTleilaxuInfluenceAbility(g.DeferredAbility):
    """``Immortality.GainTleilaxuInfluenceAbility`` (abstract; spec §3.2).

    E is not overridden: ``DeferredAbility::Evaluate`` = ``DeferValue ?? 1``.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SelectionMode @0x4e05be0``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4e05b90`` = ``CanGainTleilaxuInfluence`` (rank < 7)."""

        return _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainTleilaxuInfluenceAbility::ValueForPlayer @0x4e05da0``: base V
        merged with ``TleilaxuValue(1)``."""

        v = Summer()
        v.merge(p.tleilaxu_value(1))
        return v


@port(_AA + "Immortality.GainTleilaxuInfluenceAgentAbility")
class GainTleilaxuInfluenceAgentAbility(GainTleilaxuInfluenceAbility):
    """``GainTleilaxuInfluenceAgentAbility`` (``.ctor @0x4e06c20``: timing
    Agent; Contaminator). Not auto-run: waits as an Explicit key."""

    timing: ClassVar[Timing] = Timing.AGENT


@port(_AA + "Immortality.GainTleilaxuInfluenceCustomAbility")
class GainTleilaxuInfluenceCustomAbility(GainTleilaxuInfluenceAbility):
    """``GainTleilaxuInfluenceCustomAbility`` (playmat; research bonus).

    ``get_AlwaysRunImmediately @0x4e06f40`` = true (runs at once after the
    research step); ``Cost @0x4e06f50`` = ``CanGainTleilaxu`` then
    ``HasCustomAbility``; ``IsUnexhausted`` true; timing None.
    """

    always_run_immediately: ClassVar[bool] = True


# ===========================================================================
# §3.4 The playmat abilities
# ===========================================================================


@port(_AA + "RiseOfIx.GainAnyFactionInfluenceCustomAbility")
class GainAnyFactionInfluenceCustomAbility(g.GainAnyInfluenceCustomAbility):
    """``RiseOfIx.GainAnyFactionInfluenceCustomAbility`` (research space 15).

    Overrides only logging members (``MakeGameLogBuilder``,
    ``get_LoggingMode``): E/V are ``GainAnyInfluenceAbility``'s
    (generic-abilities §9).
    """


@port(_AA + "Immortality.TrashIntrigueForDrawAndIntrigue")
class TrashIntrigueForDrawAndIntrigue(g.DeferredAbility):
    """``Immortality.TrashIntrigueForDrawAndIntrigue`` (research space 17).

    ``SelectionMode @0x4e2a2e0`` = Optional; ``Cost @0x4e2a2f0`` =
    ``HasCustomAbility`` then ``HasIntrigueCard``; ``IsUnexhausted`` true;
    timing None. Targets: the held Intrigue cards (``Kind.INTRIGUE``).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TrashIntrigueForDrawAndIntrigue::ValueForPlayer @0x4e2a570``.

        With a junk Intrigue in hand (``IsBadIntrigue``): a card draw, its
        buy gains and an Intrigue; else the flat
        ``ResearchTrackSpace17NoBadIntrigueMod``.
        """

        v = Summer()
        if any(_is_bad_intrigue(p, card) for card in g._intrigue_hand(p)):
            v.add("Draw Card", p.card_draw_value())
            v.add("Buy Gains", p.buy_gains(p.possible_persuasion_gain()))
            v.add("Draw Intrigue", p.intrigue_value())
        else:
            v.add("No Bad Intrigue", p.C.ResearchTrackSpace17NoBadIntrigueMod)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TrashIntrigueForDrawAndIntrigue::Evaluate @0x4e2a820``.

        Shuffles the Intrigue targets (``ListUtil.Shuffle`` @0x4e2a955, the
        profile's RNG) and answers the first junk card at the literal 5.0;
        without a junk card nothing is stored and the key is never chosen.
        """

        choice = _Choice()
        cards = list(_targets(request, Kind.INTRIGUE))
        p.rng.shuffle(cards)
        for card in cards:
            if _is_bad_intrigue(p, card):
                choice.update_targets(5.0, (card.ref,))
        return choice.answer("Trash Intrigue For Draw And Intrigue")


@port(_AA + "Immortality.PaySolariForTleilaxuInfluence")
class PaySolariForTleilaxuInfluence(g.DeferredAbility):
    """``Immortality.PaySolariForTleilaxuInfluence`` (research space 21).

    ``SelectionMode @0x4e14750`` = Optional; ``Cost @0x4e14760`` =
    ``HasCustomAbility`` then ``Solari >= 7`` then ``CanGainTleilaxu``;
    ``IsUnexhausted`` true; timing None.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PaySolariForTleilaxuInfluence::ValueForPlayer @0x4e14980``.

        With 7 Solari and a rank other than 3 and at most 5 (literals): the
        two next steps, plus ``ResearchTrackSpace21ThirdSpaceMod`` of the
        third step's increment. The 7 Solari paid are not priced.
        """

        v = Summer()
        rank = _tleilaxu(p)
        if p.ctx.me.resources.solari >= 7 and rank != 3 and rank <= 5:
            two = p.tleilaxu_value(2)
            three = p.tleilaxu_value(3)
            v.add("Next Two spaces", two.sum)
            v.add(
                "Third space",
                p.C.ResearchTrackSpace21ThirdSpaceMod * (three.sum - two.sum),
            )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PaySolariForTleilaxuInfluence::Evaluate @0x4e14b30``:
        ``Upd(V(P, Array.Empty).Sum, src, null)``."""

        choice = _Choice()
        choice.update_targets(self.value_for_player(p, ()).sum, None)
        return choice.answer("Pay Solari For Tleilaxu Influence")


@port(_AA + "Immortality.ReturnSpecimenAbility")
class ReturnSpecimenAbility(g.DeferredAbility):
    """``Immortality.ReturnSpecimenAbility`` (playmat).

    ``SelectionMode @0x4e1a420`` = Optional; ``Cost @0x4e1a430`` =
    ``HasSpecimens.Any``; ``IsUnexhausted`` true; timing None. Targets: one
    option index per specimen.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.specimens() > 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ReturnSpecimenAbility::Evaluate @0x4e1a610`` (spec §3.4).

        ``n = UngainedTroops + UnaddedTechNegotiators`` (Rise of Ix tech
        negotiators: none in our engine, 0); ``n <= 0`` -> no answer (never
        returns specimens voluntarily); else the first ``n`` specimens at
        1.0.
        """

        choice = _Choice()
        n = p.ctx.ungained_troops() + 0
        if n <= 0:
            return choice.answer("Return Specimen | none")
        specimens = _options(request)
        choice.update_targets(1.0, tuple(specimens[:n]))
        return choice.answer(f"Return Specimen | {n}")


@port(_AA + "Immortality.FamilyAtomicsAbility")
class FamilyAtomicsAbility(g.DeferredAbility):
    """``Immortality.FamilyAtomicsAbility`` (playmat).

    ``SelectionMode @0x4dfd3f0`` = Optional; ``Cost @0x4dfd2c0`` = the
    player during its own turn with the token unused; ``IsUnexhausted``
    true; timing None. ``<Targets>d__5 @0x4dff910``: CustomConfirmOrDeny
    ``[decline, confirm]`` (Errata: 1 = confirm).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.family_atomics()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FamilyAtomicsAbility::Evaluate @0x4dfd5f0`` (spec §3.4).

        Only in this seat's Reveal turn with 4-8 Persuasion (literals,
        inclusive): 100, or 0 when the predicted buys are worth more than 1
        acquire value per Persuasion (``1.0 >= ratio`` keeps 100;
        ``ucomisd; jae``, so a NaN ratio gives 0). ``UpdR(v, [Int(1)])``.
        """

        choice = _Choice()
        if not _in_player_turn(p, _REVEAL_TURN):
            return choice.answer("Family Atomics | not Reveal")
        persuasion = _persuasion(p)
        if persuasion < 4 or persuasion > 8:
            return choice.answer("Family Atomics | persuasion")
        buys = p.predict_card_buys(persuasion)
        v = 100
        if buys:
            values = _dsum([p.acquire_value(card).sum for card in buys])
            costs = sum(card.int_attr("PersuasionCost") for card in buys)
            ratio = _ieee_div(values, float(costs))
            if not 1.0 >= ratio:
                v = 0
        choice.update_responses(float(v), ((1,),))
        return choice.answer(f"Family Atomics | {v}")


@port(_AA + "UsurpTrashAbility")
class UsurpTrashAbility(g.DeferredAbility):
    """``ActivatedAbilities.UsurpTrashAbility`` (playmat; trashes the Usurp
    partner at the end of the turn). ``.ctor @0x4ce1050``: timing Agent;
    ``SelectionMode @0x4ce11a0`` = Implicit; always run; no AI hook."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.IMPLICIT


@port(_TA + "Immortality.ChairdogReturnAbility")
class ChairdogReturnAbility(g.TriggeredAbility):
    """``TriggeredAbilities.Immortality.ChairdogReturnAbility`` (playmat;
    start of the Reveal turn, ``IsValidFor @0x4b0ebd0``). No AI hook."""

    should_exhaust: ClassVar[bool] = False  # @0x4b0ec70


# ===========================================================================
# §3.6 Reclaimed Forces and the Tleilaxu lines of AcquireAbility (generic.py)
# ===========================================================================


@port(_AA + "Immortality.ReclaimedForcesAcquireAbility")
class ReclaimedForcesAcquireAbility(g.AcquireAbility):
    """``Immortality.ReclaimedForcesAcquireAbility`` (spec §3.6).

    ``Cost @0x4e15820``, ``Targets @0x4e15790``; ``IsUnexhausted`` true (the
    card stays in the Tleilaxu Row). Targets: ``infos[0].options`` = the
    ``0`` two troops / ``1`` Tleilaxu choice.
    """

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ReclaimedForcesAcquireAbility::ValueForPlayer @0x4e16070``.

        Read in the binary (the spec says "base V only"): the base V, then
        the literal 0.5 in the Late arc (else 0.0) "Reclaimed Forces late
        game" and a literal 0.0 "Reclaimed Forces tleilaxu influence".
        """

        v = Summer()
        v.add("Reclaimed Forces late game", 0.5 if p.game_arc() >= 2 else 0.0)
        v.add("Reclaimed Forces tleilaxu influence", 0.0)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ReclaimedForcesAcquireAbility::Evaluate @0x4e16200`` (spec §3.6).

        ``AcquireValue(P)`` (Tleilaxu branch: 3 + S); outside the Reveal turn
        a value ``<= 0`` (or NaN) becomes 1.0 (``cmpnlesd``); option 1
        (Tleilaxu) when ``GetTroopValue(2, false) <= TleilaxuValue(1).Sum``
        (``setbe``: NaN picks Tleilaxu too), else 0 (two troops). None of
        ``AcquireAbility``'s Tleilaxu lines run (the override does not call
        the base).
        """

        v = p.acquire_value(self.owner).sum
        if p.ctx.scouts:  # app-style Arrakeen Scouts: Back Room Deal (D36)
            v += p.back_room_deal_value()
        troops = p.troop_value(2, False)
        tleilaxu = p.tleilaxu_value(1).sum
        option = 0 if troops > tleilaxu else 1
        if not _in_player_turn(p, _REVEAL_TURN):
            v = v if v > 0.0 or v != v else 1.0
        choice = _Choice()
        choice.update_responses(v, ((option,),))
        return choice.answer(f"Reclaimed Forces | option {option}")

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``ReclaimedForcesAcquireAbility::SpecificAcquireValue @0x4e165e0``.

        Late arc ``TleilaxuReclaimForcesLateGameBonus``, else
        ``TleilaxuReclaimForcesNotLateGameMod``; at Tleilaxu rank 3 or 6 (the
        step reaches a VP space) ``TleilaxuReclaimForcesVPBonus``.
        """

        c = p.C
        v = Summer()
        if p.game_arc() >= 2:
            v.add("Late Game Bonus", c.TleilaxuReclaimForcesLateGameBonus)
        else:
            v.add("Not Late Game Mod", c.TleilaxuReclaimForcesNotLateGameMod)
        if _tleilaxu(p) in (6, 3):
            v.add("Tleilaxu Track Bonus", c.TleilaxuReclaimForcesVPBonus)
        return v


# ===========================================================================
# §4 Graft
# ===========================================================================


type SpaceCache = dict[str, frozenset[str]]


def valid_space_ids(p: Profile, card_ref: str, cache: SpaceCache) -> frozenset[str]:
    """``WormBoard::ValidSpaces(card, P, null) @0x4828890`` for a hand card.

    The spaces the card could take on its own (no graft partner), with
    infiltration and costs as the engine judges them. Judgement: AppContext
    has no read for it yet, so it asks the engine's per-card placement
    enumeration (own hand and public board only); ``cache`` keeps one answer
    per card for one evaluation.
    """

    cached = cache.get(card_ref)
    if cached is not None:
        return cached
    state = p.ctx.state
    owner = state.players[p.ctx.seat]
    actions = _placements_for_card(
        state,
        p.ctx.seat,
        owner,
        card_ref,
        personal_card_for_instance(card_ref),
        False,
    )
    spaces = frozenset(
        str(value)
        for action in actions
        for key, value in action.arguments
        if key == "space_id"
    )
    cache[card_ref] = spaces
    return spaces


def graft_cards_value(
    p: Profile,
    first: Entity,
    second: Entity,
    space: Entity,
    cache: SpaceCache | None = None,
) -> Summer:
    """``GraftCardEvaluator::GraftCardsValue(wm, P, A, B, space)`` @0x492fd20.

    Spec §4.3: 100 + both cards' agent boxes valued in the with-graft
    context (``A`` with ``[B, space]``, ``B`` with ``[A, space]``). With at
    least two Agents left: -4 when the other hand cards reach at most one
    space between them, -1.5 when both are Graft cards, else -3 when the
    Graft card has no Agent icon the other card lacks. ``B`` may be an
    Imperium Row card (Usurp).
    """

    c = p.C
    cache = {} if cache is None else cache
    agents = p.ctx.me.agents_available  # P.RemainingAgents.Count()
    graft_b = _has_tag(second, "Graft")
    s = Summer()
    s.add("Base value", 100.0)
    a = _first_agent_ability(first)
    if a is not None:
        s.merge(a.value_for_player(p, (second, space)))
    b = _first_agent_ability(second)
    if b is not None:
        s.merge(b.value_for_player(p, (first, space)))
    rest = [
        ref for ref in p.ctx.hand if ref not in (first.ref, second.ref)
    ]  # hand.Except([A, B])
    reachable: set[str] = set()
    for ref in rest:
        reachable |= valid_space_ids(p, ref, cache)
    if agents >= 2:
        if len(reachable) <= 1:
            s.add("Not Enough Valid Spaces", c.GraftFewRemainingSpaceTargetsPenalty)
        if graft_b and _has_tag(first, "Graft"):
            s.add("Both Cards Have Graft", c.GraftBothCardsHaveGraftPenalty)
        else:
            graft_icons, other_icons = (
                (second.list_attr("IconList"), first.list_attr("IconList"))
                if graft_b
                else (first.list_attr("IconList"), second.list_attr("IconList"))
            )
            if not graft_icons or all(i in other_icons for i in graft_icons):
                s.add(
                    "graft card has 0 Agent Icons which the non-graft card doesn't",
                    c.GraftAgentIconsPenalty,
                )
    return s


def graft_card_evaluate(
    p: Profile, request: Request, played: Entity, space: Entity
) -> Answer:
    """``GraftCardEvaluator::Evaluate @0x49305a0`` (spec §4.2; state 50).

    ``GraftID`` = the played card, ``SpaceID`` = the chosen space; the
    candidates are ``request.infos[0]`` cards (hand cards, and Imperium Row
    cards for Usurp). A played card without the Graft tag never takes an
    optional partner (no answer). Each candidate ``c`` is valued as
    ``GraftCardsValue(A = c, B = played)``; ``UpdateTargets`` keeps the
    first strictly best.
    """

    choice = _Choice()
    if not _has_tag(played, "Graft"):
        return choice.answer("Graft partner | not a Graft card")
    cache: SpaceCache = {}
    for candidate in _targets(request, Kind.CARD):
        v = graft_cards_value(p, candidate, played, space, cache)
        choice.update_targets(v.sum, (candidate.ref,))
    return choice.answer("Graft partner")


def convert_specimen_evaluate(request: Request) -> Answer:
    """``ConvertSpecimenEvaluator @0x492fa60`` (spec §8): ``UpdateTargets(100,
    every specimen offered)`` (``infos[0].options``, one per specimen)."""

    choice = _Choice()
    choice.update_targets(100.0, tuple(_options(request)))
    return choice.answer("Convert Specimen | 100")


@port(_PA + "Immortality.GraftAgentAbility")
class GraftAgentAbility(g.AgentAbility):
    """``Immortality.GraftAgentAbility`` (spec §4.4): the agent box of every
    Graft card. Overrides ``Evaluate`` (no single-card fallback) and adds
    ``GraftTargets`` (vslot 85); V is ``AgentAbility``'s. ``Cost
    @0x4c72920`` (UNTRACED formula) is the engine's."""

    def graft_targets(self, p: Profile) -> list[Entity]:
        """``GraftAgentAbility::GraftTargets @0x4c72c50``: the hand cards
        other than this one (``b__6_0``), hand order."""

        return [c for c in _hand(p) if c.ref != self.owner.ref]

    def best_partners(
        self, p: Profile, request: Request
    ) -> list[tuple[Entity, Entity, float]]:
        """``(space, best partner, total)`` for every space ``Evaluate``
        values, in target order (the decision windows read the partner).

        Per space: the first partner (``GraftTargets`` order) whose
        ``GraftCardsValue`` is strictly above the best so far, starting from
        an empty summer (0.0): a pair worth 0 or less is never kept, and a
        space without one gets no value. A space none of whose
        ``SpaceAbility`` can run is skipped (``b__1 @0x4c73bf0`` tests every
        pair; judgement: ``can_be_run`` does not depend on the partner, as in
        ``AgentAbility.evaluate``). Total = the space's abilities valued with
        ``Array.Empty`` (``b__0 @0x4c73b00``) + the pair.
        """

        out: list[tuple[Entity, Entity, float]] = []
        partners = self.graft_targets(p)
        cache: SpaceCache = {}
        for space in _targets(request, Kind.SPACE):
            space_abilities = abilities_of(space)
            runnable = [a for a in space_abilities if isinstance(a, g.SpaceAbility)]
            if all(not a.can_be_run(p) for a in runnable):
                continue
            best_sum = 0.0
            best_card: Entity | None = None
            for partner in partners:
                v = graft_cards_value(p, self.owner, partner, space, cache)
                if v.sum > best_sum:
                    best_sum, best_card = v.sum, partner
            if best_card is None:
                continue
            space_v = Summer()
            for ability in space_abilities:
                space_v.merge(ability.value_for_player(p, ()))
            out.append((space, best_card, space_v.sum + best_sum))
        return out

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GraftAgentAbility::Evaluate @0x4c72d40`` (spec §4.4):
        ``Upd(spaceV + best pair, src, [space])`` per space, first strictly
        best kept (``UpdateSelectionTargets``)."""

        choice = _Choice()
        for space, _partner_card, total in self.best_partners(p, request):
            choice.update_targets(total, (space.ref,))
        return choice.answer(f"GraftAgentAbility | {self.owner.ref}")


@port(_PA + "Immortality.ChairdogAgentAbility")
class ChairdogAgentAbility(GraftAgentAbility):
    """``Immortality.ChairdogAgentAbility`` (spec §4.4)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ChairdogAgentAbility::ValueForPlayer @0x4c65250``.

        With a partner (with-graft context): the partner's first reveal box
        ``ValueForPlayer(P, [])`` scaled by ``ChairdogGraftRevealMod`` (the
        partner returns to the hand and can be revealed).
        """

        v = super().value_for_player(p, with_entities)
        partner = _partner(with_entities)
        if partner is not None:
            reveal = _first_reveal_ability(partner)
            if reveal is not None:
                t = reveal.value_for_player(p, ())
                t.multiply("Chairdog Grafted Reveal", p.C.ChairdogGraftRevealMod)
                v.merge(t)
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``ChairdogAgentAbility::SpecificAcquireValue @0x4c654a0``:
        ``TleilaxuHighCostCardsSynergyMod`` per owned card costing 5 or more
        (literal; ``b__8_0 @0x4c65780``)."""

        return _high_cost_cards_bonus(p)


def _high_cost_cards_bonus(p: Profile) -> Summer:
    """Chairdog / Ghola ``SpecificAcquireValue``: ``count(AllImperiumCards
    where PersuasionCost >= 5) * TleilaxuHighCostCardsSynergyMod``."""

    v = Summer()
    n = sum(
        1 for card in _all_imperium_cards(p) if card.int_attr("PersuasionCost") >= 5
    )
    if n > 0:
        v.add("Good Cards Bonus", p.C.TleilaxuHighCostCardsSynergyMod * float(n))
    return v


@port(_PA + "Immortality.GholaAgentAbility")
class GholaAgentAbility(GraftAgentAbility):
    """``Immortality.GholaAgentAbility`` (spec §4.4)."""

    def ghola_graft_penalty(
        self, p: Profile, arch: str | None, space: Entity | None
    ) -> int:
        """``GholaAgentAbility::GetGholaGraftPenalty @0x4c6d4c0``.

        The three lists of the ``.ctor`` (-1 / -3 / -5), then -5 for the
        Uprising cards Ghola would copy uselessly now (literals of the
        method). ``space`` adds what the visit itself brings.
        """

        if arch in _GHOLA_MINUS_ONE:
            return -1
        if arch in _GHOLA_MINUS_THREE:
            return -3
        if arch in _GHOLA_MINUS_FIVE:
            return -5
        me = p.ctx.me
        if arch == _SMUGGLERS_HAVEN and me.resources.spice < 8:
            return -5
        if arch == _STEERSMAN and len(me.agent_locations) < 2:
            return -5  # GetDeployedAgents().Count
        if arch == _JUNCTION_HEADQUARTERS:
            if not _in_alliance(p, "spacing_guild"):
                return -5
            k = len(p.ctx.intrigue_cards)
            if space is not None:
                k += sum(
                    1
                    for a in abilities_of(space)
                    if isinstance(a, g.GainIntrigueAbility)
                )
            if k < 2:
                return -5
            spice = me.resources.spice
            if space is not None:
                spice += space.int_attr("Spice") + g._space_bonus_spice(p, space)
            if spice < 4:
                return -5
        if arch == _LONG_LIVE_THE_FIGHTERS and p.ctx.deck_size < 6:
            return -5
        if arch == _PRICE_IS_NO_OBJECT and me.resources.solari < 6:
            return -5
        if arch == _CARGO_RUNNER:
            completed = len(me.completed_contract_ids)
            if space is not None:
                completed += sum(
                    1
                    for a in abilities_of(space)
                    if isinstance(a, g.GainContractAbility)
                )
            if completed < 2:
                return -5
        return 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GholaAgentAbility::ValueForPlayer @0x4c6da30`` (spec §4.4).

        With a partner other than a Ghola: a non-zero copy penalty is added
        and the method returns (``test eax, eax; je 0x4c6dc9e`` ... ``jmp
        0x4c6de60``: the spec's pseudo-code, which also merges the copy, is
        wrong); only a penalty of 0 merges the partner's first agent box
        valued as grafted with Ghola (``[this card, space]``). A partner
        without an agent box adds nothing (``Merge(null)`` @0x2f76b20 is a
        no-op).
        """

        v = super().value_for_player(p, with_entities)
        partner = _partner(with_entities)
        if partner is None or partner.short == _GHOLA:
            return v
        space = g.collect_first(with_entities, Kind.SPACE)
        penalty = self.ghola_graft_penalty(p, partner.short, space)
        if penalty != 0:
            v.add(f"Ghola {penalty} Copy Penalty", float(penalty))
            return v  # the copied box is not valued (@0x4c6dc99)
        copied = _first_agent_ability(partner)
        if copied is not None:
            with_copy: tuple[Entity, ...] = (self.owner,)
            if space is not None:
                with_copy = (self.owner, space)
            v.merge(copied.value_for_player(p, with_copy))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``GholaAgentAbility::SpecificAcquireValue @0x4c6de90``: as
        Chairdog's."""

        return _high_cost_cards_bonus(p)


@port(_PA + "Immortality.UsurpAgentAbility")
class UsurpAgentAbility(GraftAgentAbility):
    """``Immortality.UsurpAgentAbility`` (spec §4.4 and Errata)."""

    def graft_targets(self, p: Profile) -> list[Entity]:
        """``UsurpAgentAbility::GraftTargets @0x4c7eae0`` (Errata): the base
        list concatenated with the Imperium Row cards."""

        return [*super().graft_targets(p), *_row_cards(p)]

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``UsurpAgentAbility::ValueForPlayer @0x4c7e9f0``: + the literal 4.0
        "Usurp Imperium Card" when a ``with`` entity sits in the Imperium Row
        (``b__8_0 @0x4c7ec20``)."""

        v = super().value_for_player(p, with_entities)
        row = set(p.ctx.imperium_row)
        if any(e.kind is Kind.CARD and e.ref in row for e in with_entities):
            v.add("Usurp Imperium Card", 4.0)
        return v


@port(_PA + "Immortality.SpecimenAgentAbility")
class SpecimenAgentAbility(g.AgentAbility):
    """``Immortality.SpecimenAgentAbility`` (Bene Tleilax Lab): an
    ``AgentAbility`` whose ``SpecimensToGain`` (``AgentSpecimens``) the
    engine grants at Agent-turn state 210 (spec §4.5). No AI override: the
    agent specimen is not valued (``AgentAttributes`` stay Water, Spice,
    Solari)."""


@port(_PA + "Immortality.SpecimenGraftedAgentAbility")
class SpecimenGraftedAgentAbility(SpecimenAgentAbility):
    """``Immortality.SpecimenGraftedAgentAbility`` (Industrial Espionage):
    overrides only ``SpecimensToGain @0x4c7af90``."""


# ===========================================================================
# §5 Immortality Imperium cards
# ===========================================================================


@port(_AA + "Immortality.BeneTleilaxLabAbility")
class BeneTleilaxLabAbility(g.DeferredAbility):
    """``Immortality.BeneTleilaxLabAbility`` (§5.1). ``.ctor @0x4df9120``:
    timing Reveal; Explicit; ``get_AlwaysRunImmediately`` true; ``Cost`` =
    ``HasAtLeastGeneticMarkers(1)``."""

    timing: ClassVar[Timing] = Timing.REVEAL
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeneTleilaxLabAbility::ValueForPlayer @0x4df9410``: + 1 spice
        with a genetic marker."""

        v = Summer()
        if _markers(p) > 0:
            v.add("BeneTleilaxLab Spice", p.spice_value(1))
        return v


@port(_PA + "Immortality.BeneTleilaxResearcherRevealAbility")
class BeneTleilaxResearcherRevealAbility(g.RevealAbility):
    """``Immortality.BeneTleilaxResearcherRevealAbility`` (§5.2): overrides
    only ``GetRevealPreviewValue @0x4c637e0`` (``Persuasion: GM + 1``, read
    by the profile's reveal preview)."""


class _BeneTleilaxResearcherHelixBase(g.TriggeredAbility):
    """Shared body of the two Bene Tleilax Researcher persuasion triggers (not
    an app class: both derive from ``TriggeredAbility``; timing Reveal,
    ``get_ShouldExhaust`` false)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False
    MARKERS: ClassVar[int] = 1
    LABEL: ClassVar[str] = ""

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= self.MARKERS

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if _markers(p) >= self.MARKERS:
            v.add(self.LABEL, p.persuasion_value(1))
        return v


@port(_TA + "Immortality.BeneTleilaxResearcherRevealHelixAbility")
class BeneTleilaxResearcherRevealHelixAbility(_BeneTleilaxResearcherHelixBase):
    """``BeneTleilaxResearcherRevealHelixAbility`` (§5.2; ``.ctor
    @0x4b0ddf0``). ``V @0x4b0e120``: ``GM > 0`` -> ``GetPersuasionValue(1)``."""

    MARKERS: ClassVar[int] = 1
    LABEL: ClassVar[str] = "BeneTleilaxResearcher Persuasion 1"


@port(_TA + "Immortality.BeneTleilaxResearcherRevealDoubleHelixAbility")
class BeneTleilaxResearcherRevealDoubleHelixAbility(_BeneTleilaxResearcherHelixBase):
    """``BeneTleilaxResearcherRevealDoubleHelixAbility`` (§5.2; ``.ctor
    @0x4b0d070``). ``V @0x4b0d3a0``: ``GM >= 2`` -> ``GetPersuasionValue(1)``."""

    MARKERS: ClassVar[int] = 2
    LABEL: ClassVar[str] = "BeneTleilaxResearcher Persuasion 2"


@port(_AA + "Immortality.CorruptSmugglerAbility")
class CorruptSmugglerAbility(g.DeferredAbility):
    """``Immortality.CorruptSmugglerAbility`` (§5.3). ``.ctor @0x4dfa7a0``:
    timing Agent; Explicit; always run; ``Cost`` = ``HasGrafted``."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _has_grafted(p, self.owner.ref)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CorruptSmugglerAbility::ValueForPlayer @0x4dfaa40``: with-graft
        -> ``GetSpiceValue(2)``."""

        v = Summer()
        if _with_graft(with_entities):
            v.add("Corrupt Smuggler Graft", p.spice_value(2))
        return v


@port(_AA + "Immortality.DissectingKitAgentAbility")
class DissectingKitAgentAbility(g.DeferredAbility):
    """``Immortality.DissectingKitAgentAbility`` (§5.4). ``.ctor
    @0x4dfb020``: timing Agent; ``SelectionMode @0x4dfb2d0`` = Optional;
    ``Cost @0x4dfb160`` = the grafted card in the ActiveAgentArea."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return _grafted_partner_of(p, self.owner.ref) is not None

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DissectingKitAgentAbility::ValueForPlayer @0x4dfb7c0``.

        With a partner: a partner without ``TrashValue`` (``<= 0``) costs
        ``DissectingKitCardCostMod`` x its Persuasion cost (or the literal
        1.5 x its specimen cost for a Tleilaxu card); then its
        ``TrashValue`` and one specimen.
        """

        v = Summer()
        partner = _partner(with_entities)
        if partner is None:
            return v
        trash_value = partner.float_attr("TrashValue", 0.0)
        if trash_value <= 0:
            if partner.has("PersuasionCost"):
                cost = float(partner.int_attr("PersuasionCost"))
            else:
                cost = 1.5 * float(partner.int_attr("SpecimenCost"))
            v.add("Dissecting Kit Avoid Good Card", cost * p.C.DissectingKitCardCostMod)
        v.add(f"Dissecting Kit Trash {partner.ref}", trash_value)
        v.add("Dissecting Kit Gain Specimen", p.specimen_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DissectingKitAgentAbility::Evaluate @0x4dfbb90``:
        ``Upd(100.0, src, null)`` (always trash the partner)."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Dissecting Kit | 100")


@port(_AA + "Immortality.DissectingKitRevealAbility")
class DissectingKitRevealAbility(g.DeferredAbility):
    """``Immortality.DissectingKitRevealAbility`` (§5.4). ``.ctor
    @0x4dfc6c0``: timing Reveal; Explicit; ``Cost`` = one genetic marker
    then ``CanGainTleilaxu``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 1 and _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DissectingKitRevealAbility::ValueForPlayer @0x4dfc9a0``:
        ``GM > 0`` -> merge ``TleilaxuValue(1)``."""

        v = Summer()
        if _markers(p) > 0:
            v.merge(p.tleilaxu_value(1))
        return v


@port(_AA + "Immortality.ForHumanityAgentAbility")
class ForHumanityAgentAbility(g.GainAnyInfluenceAbility):
    """``Immortality.ForHumanityAgentAbility`` (§5.5): a
    ``GainAnyInfluenceAbility`` with timing Agent (``.ctor @0x4dfffc0``)."""

    timing: ClassVar[Timing] = Timing.AGENT


@port(_AA + "Immortality.ForHumanityRevealAbility")
class ForHumanityRevealAbility(g.DeferredAbility):
    """``Immortality.ForHumanityRevealAbility`` (§5.5). ``.ctor
    @0x4e00290``: timing Reveal; ``SelectionMode @0x4e003f0`` = Optional;
    ``Cost @0x4e00400`` = ``HasFactionAlliance(BeneGesserit)``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return _in_alliance(p, "bene_gesserit")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ForHumanityRevealAbility::ValueForPlayer @0x4e00620``: with the
        Bene Gesserit alliance, the cheapest loss of 2 influence
        (``GetGainInfluenceValue(None, -2)``) and 1 VP."""

        v = Summer()
        if _in_alliance(p, "bene_gesserit"):
            v.add(
                "For Humanity Reveal Lose Influence",
                g.gain_any_influence_value(p, -2).sum,
            )
            v.add("For Humanity Reveal Gain VP", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ForHumanityRevealAbility::Evaluate @0x4e007f0``: per faction
        track, 1 VP + losing 2 influence there; first strictly best."""

        choice = _Choice()
        vp = p.victory_point_value(1)
        for track in _targets(request, Kind.TRACK):
            s = Summer()
            s.add("Victory Point Gained", vp)
            s.add(
                "Lose Faction Value",
                p.gain_influence_value(track.ref, -2, -1, False).sum,
            )
            choice.update_targets(s.sum, (track.ref,))
        return choice.answer("For Humanity")


@port(_AA + "Immortality.HighPriorityTravelAbility")
class HighPriorityTravelAbility(g.DeferredAbility):
    """``Immortality.HighPriorityTravelAbility`` (§5.6). ``.ctor
    @0x4e074c0``: timing Agent; Explicit; ``Cost @0x4e07610`` = Guild
    influence 2 then a drawable card or a garrisoned unit. Options: 0 draw,
    1 deploy (``<Targets>d__8 @0x4e09980``, [I] by order)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        me = p.ctx.me
        return me.influence.spacing_guild >= 2 and (
            g._has_drawable_card(p) or me.troops_garrison > 0
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HighPriorityTravelAbility::ValueForPlayer @0x4e07990``: with Guild
        2, the better of a card draw (with buy gains) and the combat
        positioning, plus ``HighPriorityTravelAgentMod``."""

        v = Summer()
        if p.ctx.me.influence.spacing_guild >= 2:
            v.add(
                "High Priority Travel Draw with Buy Gains",
                _dmax(p.card_draw_value_with_buy_gains(), p.combat_positioning()),
            )
            v.add("High Priority Travel Mod", p.C.HighPriorityTravelAgentMod)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``HighPriorityTravelAbility::Evaluate @0x4e07bb0`` (§5.6).

        Not at a combat space, 2+ garrisoned units and a conflict interest
        strictly above the posture's lower bound (the log says "> Lower
        Bound"; ``Item1``) -> deploy at 1.0; else draw at
        ``CardDrawValueWithBuyGains``.
        """

        choice = _Choice()
        _cards, spaces = g._this_turn_agent(p)
        not_combat = all(not s.attr("CombatSpace", False) for s in spaces)
        if not_combat and p.ctx.me.troops_garrison >= 2:
            lower, _upper = p.conflict_posture_bounds()
            if p.current_conflict_interest().sum > lower:
                choice.update_responses(1.0, ((1,),))
                return choice.answer("High Priority Travel | deploy")
        choice.update_responses(p.card_draw_value_with_buy_gains(), ((0,),))
        return choice.answer("High Priority Travel | draw")


@port(_AA + "HighPriorityTravelDeployUnitsCustomAbility")
class HighPriorityTravelDeployUnitsCustomAbility(g.DeployUnitsAbility):
    """``ActivatedAbilities.HighPriorityTravelDeployUnitsCustomAbility``
    (§5.6): ``Cost @0x4cd9c00`` = a garrisoned unit then the custom grant;
    ``IsUnexhausted`` true; E/V = ``DeployUnitsAbility``."""


@port(_AA + "Immortality.ImperiumCeremonyAbility")
class ImperiumCeremonyAbility(g.DeferredAbility):
    """``Immortality.ImperiumCeremonyAbility`` (§5.7 and Errata). ``.ctor
    @0x4e0b000``: timing Agent; Explicit; ``Cost`` NoCost."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperiumCeremonyAbility::ValueForPlayer @0x4e0b330``:
        ``IntrigueValue x ImperiumCeremonyMod``."""

        v = Summer()
        v.add(
            "Imperium Ceremony Intrigue value",
            p.intrigue_value() * p.C.ImperiumCeremonyMod,
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperiumCeremonyAbility::Evaluate @0x4e0b4d0``:
        ``Upd(V(P, Array.Empty).Sum, src, null)``."""

        choice = _Choice()
        choice.update_targets(self.value_for_player(p, ()).sum, None)
        return choice.answer("Imperium Ceremony")

    def evaluate_intrigue(self, p: Profile, request: Request) -> Answer:
        """``ImperiumCeremonyAbility::EvaluateIntrigue @0x4e0b6f0`` (Errata):
        the ``KeepIntrigueCard`` picker.

        Shuffles the Intrigue targets (``ListUtil.Shuffle`` @0x4e0b9cf) and
        scores each 1 when one of its Intrigue abilities is junk
        (``IsBadIntrigue``), else 50 (literals); first strictly best: a random
        non-junk card is kept.
        """

        choice = _Choice()
        cards = list(_targets(request, Kind.INTRIGUE))
        p.rng.shuffle(cards)
        for card in cards:
            value = 1.0 if _is_bad_intrigue(p, card) else 50.0
            choice.update_targets(value, (card.ref,))
        return choice.answer("Imperium Ceremony | keep Intrigue")


@port(_AA + "Immortality.InterstellarConspiracyAbility")
class InterstellarConspiracyAbility(g.GainAnyInfluenceAbility):
    """``Immortality.InterstellarConspiracyAbility`` (§5.8 and Errata).
    ``.ctor @0x4e0e260``: timing Agent; ``Cost @0x4e0e3b0`` = the grafted
    card holds the Emperor or Spacing Guild faction, then
    ``CanGainInfluence``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def meets_cost(self, p: Profile) -> bool:
        partner = _grafted_partner_of(p, self.owner.ref)
        return partner is not None and (
            _has_faction(partner, "Emperor") or _has_faction(partner, "SpacingGuild")
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InterstellarConspiracyAbility::ValueForPlayer @0x4e0e500``.

        ``GainAnyInfluenceAbility``'s V, 1 spice, and the best influence when
        a ``with`` entity has the Emperor or Spacing Guild faction
        (``b__6_0``). Errata: only a grafted partner card can (spaces have
        no ``FactionList``).
        """

        v = super().value_for_player(p, with_entities)
        v.add("Interstellar Conspiracy Spice", p.spice_value(1))
        if any(
            _has_faction(e, "Emperor") or _has_faction(e, "SpacingGuild")
            for e in with_entities
        ):
            v.add(
                "Interstellar Conspiracy Influence",
                g.gain_any_influence_value(p, 1).sum,
            )
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``InterstellarConspiracyAbility::ValueInPileForOtherPlay
        @0x4e0e7c0``.

        Always 1 spice. The "Interstellar Conspiracy Played" term tests
        ``pile.IsNamed(EntityNames.Hand)``, a pile the AI never passes (it
        calls with the PlayArea and the Deck): dead in the app, kept dead
        here. Deck: an Emperor or Guild candidate outside the climax adds
        ``SynergyBeneGesseritWithBondInDeck``.
        """

        v = Summer()
        v.add("Interstellar Conspiracy Spice", p.spice_value(1))
        if (
            pile is Pile.DECK
            and (_has_faction(card, "Emperor") or _has_faction(card, "SpacingGuild"))
            and not p.is_climax()
        ):
            v.add(
                "Emperor or SpacingGuild in Deck",
                p.C.SynergyBeneGesseritWithBondInDeck,
            )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``InterstellarConspiracyAbility::Evaluate @0x4e0ebb0``: each
        track's ``GetGainInfluenceValue(f, 1)``; if the stored value is not
        positive, ``Upd(0.5, src, null)``."""

        choice = _Choice()
        for track in _targets(request, Kind.TRACK):
            choice.update_targets(
                p.gain_influence_value(track.ref, 1, -1, False).sum, (track.ref,)
            )
        if choice.value <= 0:
            choice.update_targets(0.5, None)
        return choice.answer("Interstellar Conspiracy")


@port(_AA + "Immortality.KeysToPowerAbility")
class KeysToPowerAbility(g.DeferredAbility):
    """``Immortality.KeysToPowerAbility`` (§5.9). ``.ctor @0x4e0f3a0``:
    timing Agent; Explicit; ``Cost`` = Emperor influence 2."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.influence.emperor >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``KeysToPowerAbility::ValueForPlayer @0x4e0f5c0``: Emperor 2 ->
        ``GetSpiceValue(2)``."""

        v = Summer()
        if p.ctx.me.influence.emperor >= 2:
            v.add("Keys To Power Spice", p.spice_value(2))
        return v


def _bg_played(
    p: Profile, pile: Pile, card: Entity, played: Callable[[], float]
) -> Summer:
    """The Lisan al Gaib / Long Reach P (spec §5.10, §5.11; pattern BGP).

    PlayArea: no Bene Gesserit card in play, a BG candidate and 2+ Agents
    left -> ``played()`` "Bene Gesserit Played"; Deck: a BG candidate outside
    the climax -> ``SynergyBeneGesseritWithBondInDeck``.
    """

    return g.bg_played_pile_value(p, pile, card, played, "Bene Gesserit Played")


@port(_PA + "Immortality.LisanAlGaibAgentAbility")
class LisanAlGaibAgentAbility(g.DeferredAbility):
    """``Immortality.LisanAlGaibAgentAbility`` (§5.10). ``.ctor
    @0x4c776f0``: timing Agent; Explicit; ``Cost`` = a Bene Gesserit card
    played (other than this) then ``CanGainInfluence``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LisanAlGaibAgentAbility::ValueForPlayer @0x4c77ae0``: another BG
        card in play -> ``Inf(Fremen, 1)``."""

        v = Summer()
        if any(
            c.ref != self.owner.ref and _has_faction(c, "BeneGesserit")
            for c in _in_play(p)
        ):
            v.add(
                "Lisan Al Gaib Fremen Influence",
                p.gain_influence_value("fremen", 1, -1, False).sum,
            )
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``LisanAlGaibAgentAbility::ValueInPileForOtherPlay @0x4c77de0``:
        "Bene Gesserit Played" = 0.75 (literal) x the best +1 influence."""

        return _bg_played(
            p, pile, card, lambda: 0.75 * g.gain_any_influence_value(p, 1).sum
        )


@port(_TA + "Immortality.LisanAlGaibRevealAbility")
class LisanAlGaibRevealAbility(g.BondAbility):
    """``Immortality.LisanAlGaibRevealAbility`` (§5.10): a Fremen bond
    (``get_BondFaction @0x4b106f0``), timing Reveal."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LisanAlGaibRevealAbility::ValueForPlayer @0x4b10870``: another
        own Fremen card in hand or in play -> ``GetStrengthValue(2)``."""

        v = Summer()
        if any(
            c.ref != self.owner.ref and _has_faction(c, "Fremen")
            for c in (*_hand(p), *_in_play(p))
        ):
            v.add("Lisan Al Gaib Strength", p.strength_value(2))
        return v


@port(_PA + "Immortality.LisanAlGaibRevealPreviewAbility")
class LisanAlGaibRevealPreviewAbility(g.RevealAbility):
    """``Immortality.LisanAlGaibRevealPreviewAbility`` (§5.10): overrides only
    ``GetRevealPreviewValue @0x4c790e0`` (read by the profile)."""


@port(_AA + "Immortality.LongReachAgentAbility")
class LongReachAgentAbility(g.DeferredAbility):
    """``Immortality.LongReachAgentAbility`` (§5.11). ``.ctor @0x4e0fdc0``:
    timing Agent; Explicit; ``Cost`` = ``CanGainInfluence``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def _two_best(self, p: Profile) -> list[Summer]:
        """``Match.FactionList`` -> ``GetGainInfluenceValue(f, 1)`` ordered by
        ``Sum`` descending (stable: track order on ties)."""

        values = [p.gain_influence_value(f, 1, -1, False) for f in _FACTIONS]
        values.sort(key=lambda s: s.sum, reverse=True)
        return values[:2]

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LongReachAgentAbility::ValueForPlayer @0x4e100d0``: the two best
        +1 influences (each added as one entry)."""

        v = Summer()
        for best in self._two_best(p):
            v.add("Long Reach Influence", best.sum)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``LongReachAgentAbility::ValueInPileForOtherPlay @0x4e106b0``:
        "Bene Gesserit Played" = 0.75 x the sum of the two best +1
        influences (``OrderByDescending.Take(2).Sum``)."""

        def played() -> float:
            return 0.75 * _dsum([s.sum for s in self._two_best(p)])

        return _bg_played(p, pile, card, played)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LongReachAgentAbility::Evaluate @0x4e10c00`` (§5.11).

        No track: ``Upd(0.5, src, null)``. Else shuffle the tracks
        (``ListUtil.Shuffle`` @0x4e10f6b), key each by its
        ``GetGainInfluenceValue(f, 1)`` summer (``TryAdd``: distinct summer
        objects, so every track is kept), take the two best (stable after
        the shuffle) and answer ``max(0.5, their sum)`` with both tracks.
        The House Hagal branch is unreachable.
        """

        choice = _Choice()
        tracks = list(_targets(request, Kind.TRACK))
        if not tracks:
            choice.update_targets(0.5, None)
            return choice.answer("Long Reach | no track")
        p.rng.shuffle(tracks)
        valued = [(p.gain_influence_value(t.ref, 1, -1, False), t) for t in tracks]
        valued.sort(key=lambda item: item[0].sum, reverse=True)
        top = valued[:2]
        total = _dsum([s.sum for s, _ in top])
        choice.update_targets(_dmax(0.5, total), tuple(t.ref for _, t in top))
        return choice.answer("Long Reach")


#: ``WormMatchExtensions::FactionList``: the four faction tracks.
_FACTIONS: Final = ("emperor", "spacing_guild", "bene_gesserit", "fremen")


@port(_AA + "Immortality.OrganMerchantsAbility")
class OrganMerchantsAbility(g.DeferredAbility):
    """``Immortality.OrganMerchantsAbility`` (§5.12). ``.ctor @0x4e13250``:
    timing Agent; ``SelectionMode @0x4e13340`` = Optional; ``Cost`` = one
    specimen."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.specimens() >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``OrganMerchantsAbility::ValueForPlayer @0x4e13460``: when the
        specimen can be paid with the space (``CanAgentAbilityBePlayedWith
        Space(space, Specimen, 1)``, always true for a specimen): one
        specimen paid, 4 Solari gained."""

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        if p.can_agent_ability_be_played_with_space(space, Attr.SPECIMEN, 1):
            v.add("Organ merchants Specimen Cost", p.specimen_value(-1))
            v.add("Organ merchants Solari", p.solari_value(4))
        else:
            v.add("Organ merchants cost cannot be paid", 0.0)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OrganMerchantsAbility::Evaluate @0x4e13780``."""

        s = Summer()
        s.add("Specimen Cost", p.specimen_value(-1))
        s.add("Solari", p.solari_value(4))
        choice = _Choice()
        choice.update_targets(s.sum, None)
        return choice.answer("Organ Merchants")


@port(_AA + "Immortality.ReplacementEyesAgentAbility")
class ReplacementEyesAgentAbility(g.DeferredAbility):
    """``Immortality.ReplacementEyesAgentAbility`` (§5.13). ``.ctor
    @0x4e18780``: timing Agent; ``SelectionMode @0x4e189f0`` = Optional;
    ``Cost`` = ``HasTrashableCard``. Targets: the trashable cards."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ReplacementEyesAgentAbility::ValueForPlayer @0x4e18b00``."""

        v = Summer()
        v.add("Replacement Eyes Trash Card", p.trash_card_value())
        v.add("Replacement Eyes Trash Card Bonus", p.trash_mod())
        v.add("Replacement Eyes Draw Card", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        v.add("Replacement Eyes Mod", p.C.ReplacementEyesAgentMod)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ReplacementEyesAgentAbility::Evaluate @0x4e18d70`` (§5.13).

        ``GetCardToTrash(targets, 1.0)``; without a junk card the card with
        the lowest ``AcquireValue`` (stable ``OrderBy``); value = the trash
        score + a draw + its buy gains.
        """

        choice = _Choice()
        targets = _targets(request, Kind.CARD)
        best, trash_value = p.card_to_trash(targets, 1.0)
        s = Summer()
        s.add("Trash Value", trash_value)
        if best is None and targets:
            best = sorted(targets, key=lambda c: p.acquire_value(c).sum)[0]
        s.add("Draw 1 card", p.card_draw_value())
        s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        if best is None:
            return choice.answer("Replacement Eyes | no target")
        choice.update_targets(s.sum, (best.ref,))
        return choice.answer(f"Replacement Eyes | {best.ref}")


@port(_TA + "Immortality.ReplacementEyesTrashAbility")
class ReplacementEyesTrashAbility(g.TriggeredAbility):
    """``Immortality.ReplacementEyesTrashAbility`` (§5.13): fires when the
    card is trashed (``IsValidFor @0x4b11780``); ``Cost`` NoCost; no AI
    hook."""

    should_exhaust: ClassVar[bool] = False  # @0x4b11840


@port(_AA + "Immortality.SardaukarQuartermasterTroopAbility")
class SardaukarQuartermasterTroopAbility(g.DeferredAbility):
    """``Immortality.SardaukarQuartermasterTroopAbility`` (§5.14). ``.ctor
    @0x4e1b9c0``: timing Agent; Explicit; always run; ``Cost`` =
    ``HasGrafted``."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _has_grafted(p, self.owner.ref)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SardaukarQuartermasterTroopAbility::ValueForPlayer @0x4e1bc60``:
        with-graft -> ``GetTroopValue(1)``."""

        v = Summer()
        if _with_graft(with_entities):
            v.add("Gain Troop", p.troop_value(1, False))
        return v


@port(_AA + "Immortality.SardaukarQuartermasterDrawAbility")
class SardaukarQuartermasterDrawAbility(g.DrawAbility):
    """``Immortality.SardaukarQuartermasterDrawAbility`` (§5.14): a
    ``DrawAbility`` whose ``Cost @0x4e1b840`` is ``HasGrafted`` then
    ``HasDrawableCard``; ``DrawAbility``'s V checks ``MeetsCost``, so it is
    worth a draw only while this turn grafts."""

    def meets_cost(self, p: Profile) -> bool:
        return _has_grafted(p, self.owner.ref) and g._has_drawable_card(p)


@port(_TA + "Immortality.ShowOfStrengthAbility")
class ShowOfStrengthAbility(g.TriggeredAbility):
    """``Immortality.ShowOfStrengthAbility`` (§5.16; ``.ctor @0x4b122e0``:
    timing Agent). ``IsValidFor @0x4b123d0``; ``Cost`` NoCost; no AI hook."""

    timing: ClassVar[Timing] = Timing.AGENT
    should_exhaust: ClassVar[bool] = False  # @0x4b12490


@port(_AA + "Immortality.StillsuitManufacturerAgentAbility")
class StillsuitManufacturerAgentAbility(g.DeferredAbility):
    """``Immortality.StillsuitManufacturerAgentAbility`` (§5.17). ``.ctor
    @0x4e2cb40``: timing Agent; Explicit; ``IsUnexhausted`` true; ``Cost`` =
    the Fremen alliance then the card in play."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _in_alliance(p, "fremen") and self.owner.ref in p.ctx.me.in_play

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``StillsuitManufacturerAgentAbility::ValueForPlayer @0x4e2cfa0``.

        ``HasOrWouldGainAlliance(Fremen, space.Faction == Fremen ? 1 : 0)``
        (read in the binary: the amount is the 0/1 of the space test) -> the
        card's first reveal box (it returns to the hand) and
        ``StillsuitManufacturerMod``.
        """

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        amount = 1 if space is not None and space.attr("Faction") == "Fremen" else 0
        if p.has_or_would_gain_alliance("fremen", amount):
            reveal = _first_reveal_ability(self.owner)
            v.add(
                "Stillsuit Manufacturer Return To Hand",
                reveal.value_for_player(p, ()).sum if reveal is not None else 0.0,
            )
            v.add("Stillsuit Manufacturer Mod", p.C.StillsuitManufacturerMod)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StillsuitManufacturerAgentAbility::Evaluate @0x4e2d280``:
        ``Upd(100.0, src, Array.Empty)``."""

        choice = _Choice()
        choice.update_targets(100.0, ())
        return choice.answer("Stillsuit Manufacturer | 100")


@port(_TA + "Immortality.StillsuitManufacturerRevealAbility")
class StillsuitManufacturerRevealAbility(g.BondAbility):
    """``Immortality.StillsuitManufacturerRevealAbility`` (§5.17): a Fremen
    bond (``get_BondFaction @0x4b133f0``), timing Reveal."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``StillsuitManufacturerRevealAbility::ValueForPlayer @0x4b13570``:
        another own Fremen card in hand or in play -> ``GetSpiceValue(2)``."""

        v = Summer()
        if any(
            c.ref != self.owner.ref and _has_faction(c, "Fremen")
            for c in (*_hand(p), *_in_play(p))
        ):
            v.add("Stillsuit Manufacturer Spice", p.spice_value(2))
        return v


@port(_PA + "Immortality.ThroneRoomPoliticsRevealAbility")
class ThroneRoomPoliticsRevealAbility(g.RevealAbility):
    """``Immortality.ThroneRoomPoliticsRevealAbility`` (§5.18): overrides
    only ``GetRevealPreviewValue @0x4c7c540`` (read by the profile)."""


@port(_AA + "RiseOfIx.InTheShadowsRevealAbility")
class InTheShadowsRevealAbility(g.DeferredAbility):
    """``RiseOfIx.InTheShadowsRevealAbility`` (§5.18; Throne Room Politics).
    ``.ctor @0x4dc9770``: timing Reveal; Explicit; not auto-run; ``Cost`` =
    ``CanGainInfluence(BeneGesserit)``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.influence.bene_gesserit <= 5

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InTheShadowsRevealAbility::ValueForPlayer @0x4dc9ae0``:
        ``Inf(BeneGesserit, 1)``."""

        v = Summer()
        v.add(
            "In The Shadows Reveal Influence",
            p.gain_influence_value("bene_gesserit", 1, -1, False).sum,
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``InTheShadowsRevealAbility::Evaluate @0x4dc9c70``: 100 ("always
        play")."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("In The Shadows Reveal | 100")


@port(_PA + "Immortality.TleilaxuMasterAbility")
class TleilaxuMasterAbility(g.DeferredAbility):
    """``Immortality.TleilaxuMasterAbility`` (§5.19). ``.ctor @0x4c60eb0``:
    timing Agent; ``SelectionMode @0x4c614e0`` = Optional; ``Cost`` = one
    genetic marker then an Imperium Row card costing less than 7.

    Targets: ``infos[0]`` the acquirable Row cards; ``infos[1].options`` the
    destination picker when ``GetAcquireArchIDAndPickerKind`` offers one
    (UNTRACED condition; judgement: present iff the window sends it).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TleilaxuMasterAbility::ValueForPlayer @0x4c616a0``.

        With a marker: the best Row card costing less than 7 by
        ``AcquireValue`` (``MaxByOrElse``: the first maximum), and with two
        markers its first reveal box (it goes to the hand).
        """

        v = Summer()
        if _markers(p) <= 0:
            return v
        best: Entity | None = None
        best_value = 0.0
        for card in _row_cards(p):
            if card.int_attr("PersuasionCost") >= 7:
                continue
            value = p.acquire_value(card).sum
            if best is None or value > best_value:
                best, best_value = card, value
        if best is None:
            return v
        v.add(f"Tleilaxu Master Acquire {best.ref}", p.acquire_value(best).sum)
        if _markers(p) >= 2:
            reveal = _first_reveal_ability(best)
            v.add(
                f"Tleilaxu Master Reveal {best.ref}",
                reveal.value_for_player(p, ()).sum if reveal is not None else 0.0,
            )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TleilaxuMasterAbility::Evaluate @0x4c61c90``: each target card at
        its ``AcquireValue`` with the destination option (1 = hand with two
        markers when the picker is offered, else 0); first strictly best."""

        choice = _Choice()
        picker = bool(_options(request, 1))
        option = (1 if _markers(p) >= 2 else 0) if picker else 0
        for card in _targets(request, Kind.CARD):
            choice.update_responses(p.acquire_value(card).sum, ((card.ref,), (option,)))
        return choice.answer("Tleilaxu Master")


@port(_AA + "Immortality.TleilaxuSurgeonAgentAbility")
class TleilaxuSurgeonAgentAbility(g.DeferredAbility):
    """``Immortality.TleilaxuSurgeonAgentAbility`` (§5.20). ``.ctor
    @0x4e26140``: timing Agent; Optional; ``Cost`` = two specimens then
    ``CanGainTleilaxu``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.specimens() >= 2 and _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TleilaxuSurgeonAgentAbility::ValueForPlayer @0x4e263c0``: when
        payable with the space, two specimens paid and two Tleilaxu steps,
        only if their sum is positive."""

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        if p.can_agent_ability_be_played_with_space(space, Attr.SPECIMEN, 2):
            cost = p.specimen_value(-2)
            steps = p.tleilaxu_value(2)
            if steps.sum + cost > 0:
                v.add("Tleilaxu Surgeon Specimen Cost", cost)
                v.merge(steps)
        else:
            v.add("Tleilaxu Surgeon cost cannot be paid", 0.0)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TleilaxuSurgeonAgentAbility::Evaluate @0x4e26720``."""

        s = Summer()
        s.add("Specimen Cost", p.specimen_value(-2))
        s.merge(p.tleilaxu_value(2))
        choice = _Choice()
        choice.update_targets(s.sum, None)
        return choice.answer("Tleilaxu Surgeon (Agent)")


@port(_AA + "Immortality.TleilaxuSurgeonRevealAbility")
class TleilaxuSurgeonRevealAbility(g.DeferredAbility):
    """``Immortality.TleilaxuSurgeonRevealAbility`` (§5.20). ``.ctor
    @0x4e276a0``: timing Reveal; Optional; ``Cost`` = two troops between
    the garrison and the Conflict. Targets: zone codes (module docstring)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        me = p.ctx.me
        return me.troops_garrison + me.troops_conflict >= 2

    def _trade(self, p: Profile) -> Summer:
        s = Summer()
        s.add("Troop Cost", p.troop_value(-2, False))
        s.add("Specimen", p.specimen_value(2))
        return s

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TleilaxuSurgeonRevealAbility::ValueForPlayer @0x4e27bf0``.

        When the conflict interest is strictly below the posture's lower
        bound (``Item1``) and at most one unit is garrisoned: 0. Else two
        troops for two specimens, only if positive.
        """

        v = Summer()
        lower, _upper = p.conflict_posture_bounds()
        if lower > p.current_conflict_interest().sum and p.ctx.me.troops_garrison <= 1:
            v.add("Tleilaxu Surgeon cost cannot be paid", 0.0)
            return v
        trade = self._trade(p)
        if trade.sum > 0:
            v.merge(trade)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TleilaxuSurgeonRevealAbility::Evaluate @0x4e27f90`` (§5.20):
        two troops chosen garrison-first when the AI expects to place in the
        conflict (``EstimatedConflictRank(0)`` has a value), else
        deployed-first."""

        choice = _Choice()
        trade = self._trade(p)
        if trade.sum <= 0:
            return choice.answer("Tleilaxu Surgeon (Reveal) | 0")
        troops = _troop_choice(p, _options(request), 2)
        choice.update_targets(trade.sum, troops)
        return choice.answer("Tleilaxu Surgeon (Reveal)")


# ===========================================================================
# §6 Tleilaxu cards
# ===========================================================================


@port(_AA + "Immortality.BeguilingPheromonesAbility")
class BeguilingPheromonesAbility(g.DeferredAbility):
    """``Immortality.BeguilingPheromonesAbility`` (§6.1). ``.ctor
    @0x4df7240``: timing Agent; Explicit; ``Cost`` = ``HasGrafted`` then an
    active space with a faction. Targets: the two grafted cards."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeguilingPheromonesAbility::ValueForPlayer @0x4df77c0``."""

        v = Summer()
        v.add("Trash Card", p.trash_card_value())
        v.add("Trash Card Bonus", p.trash_mod())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BeguilingPheromonesAbility::Evaluate @0x4df7950`` (§6.1).

        Itself: 1.0; the partner: its ``GetCardToTrash`` score + 1 when above
        1, else the table ``@0x52f3d40`` ``[6.0, 1.0][PersuasionCost >= 5]``
        (a cheap partner is trashed at 6.0).
        """

        choice = _Choice()
        for card in _targets(request, Kind.CARD):
            if card.ref == self.owner.ref:
                value = 1.0
            else:
                _best, trash_value = p.card_to_trash((card,), 1.0)
                if trash_value > 1.0:
                    value = trash_value + 1.0
                else:
                    value = (6.0, 1.0)[1 if card.int_attr("PersuasionCost") >= 5 else 0]
            choice.update_targets(value, (card.ref,))
        return choice.answer("Beguiling Pheromones")


@port(_AA + "Immortality.CorrinoGenesAbility")
class CorrinoGenesAbility(g.DeferredAbility):
    """``Immortality.CorrinoGenesAbility`` (§6.5). ``.ctor @0x4df9b70``:
    timing Agent; Explicit; ``Cost`` = ``HasGrafted`` then
    ``CanGainTleilaxu``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _has_grafted(p, self.owner.ref) and _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CorrinoGenesAbility::ValueForPlayer @0x4df9ea0``: with-graft ->
        merge ``TleilaxuValue(1)``."""

        v = Summer()
        if _with_graft(with_entities):
            v.merge(p.tleilaxu_value(1))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``CorrinoGenesAbility::SpecificAcquireValue @0x4dfa030``: +
        ``TleilaxuSwordmasterSynergyBonus`` when the player **has** the
        Swordmaster (the app's label says "No Swordmaster")."""

        v = Summer()
        if p.ctx.me.swordmaster_acquired:
            v.add("No Swordmaster", p.C.TleilaxuSwordmasterSynergyBonus)
        return v


@port(_PA + "Immortality.GuildImpersonatorAbility")
class GuildImpersonatorAbility(g.DeferredAbility):
    """``Immortality.GuildImpersonatorAbility`` (§6.6). ``.ctor
    @0x4c5f350``: timing Agent; Explicit; ``Cost`` = spice gained this turn
    then ``CanGainInfluence(SpacingGuild)``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildImpersonatorAbility::ValueForPlayer @0x4c5f5f0``: at a maker
        space (or Rise of Ix Interstellar Shipping, or Smuggling with a
        shipping rank: not on our board) -> ``Inf(SpacingGuild, 1)``."""

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        if space is None:
            return v
        if space.has("BonusSpice") or space.short == _INTERSTELLAR_SHIPPING:
            v.add(
                "Guild Impersonator Spacing Guild Influence",
                p.gain_influence_value("spacing_guild", 1, -1, False).sum,
            )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildImpersonatorAbility::Evaluate @0x4c5f880``: 100."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Guild Impersonator | 100")


@port(_AA + "Immortality.IndustrialEspionageResearchAbility")
class IndustrialEspionageResearchAbility(g.DeferredAbility):
    """``Immortality.IndustrialEspionageResearchAbility`` (§6.7). ``.ctor
    @0x4e0cce0``: timing Agent; Explicit; ``Cost`` = ``HasGrafted``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _has_grafted(p, self.owner.ref)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IndustrialEspionageResearchAbility::ValueForPlayer @0x4e0d0a0``:
        with-graft -> merge ``ResearchValue()``."""

        v = Summer()
        if _with_graft(with_entities):
            v.merge(p.research_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IndustrialEspionageResearchAbility::Evaluate @0x4e0d230``:
        ``Upd(1.0, Array.Empty)`` then each research space at its
        ``SpaceValue`` (no +1.0 floor, unlike ``GainResearchAbility``)."""

        choice = _Choice()
        choice.update_targets(1.0, ())
        for space in _targets(request, Kind.SPACE):
            value = p.research_space_value(_research_id(space)).sum
            choice.update_targets(value, (space.ref,))
        return choice.answer("Industrial Espionage Research")


@port(_AA + "Immortality.ScientificBreakthroughAbility")
class ScientificBreakthroughAbility(g.DeferredAbility):
    """``Immortality.ScientificBreakthroughAbility`` (§6.9). ``.ctor
    @0x4e1c250``: timing Agent; Optional; ``Cost`` = two genetic markers."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ScientificBreakthroughAbility::ValueForPlayer @0x4e1c4d0``:
        research rank above 6, or exactly 6 at the Immortality Research
        Station -> ``GetVictoryPointValue(1)``.

        Read in the binary (the spec's pseudo-code omits it): the space
        ``with.OfType<WormSpace>().FirstOrDefault()`` is taken first and a
        missing space returns the base value at once (``test rax, rax; je
        0x4e1c720`` at 0x4e1c606), before the rank is read. So a call without
        a space (``AgentAbility::ValueForPlayer(P, [])`` from the discard
        order) never prices the Victory Point.
        """

        v = Summer()
        space = g.collect_first(with_entities, Kind.SPACE)
        if space is None:
            return v
        rank = p.ctx.research_rank()
        at_station = space.short == _RESEARCH_STATION_IMMORTALITY
        if rank > 6 or (rank == 6 and at_station):
            v.add("Scientific Breakthrough Victory Point", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ScientificBreakthroughAbility::Evaluate @0x4e1c740``: 100."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Scientific Breakthrough | 100")


@port(_AA + "Immortality.SligFarmerSolariAbility")
class SligFarmerSolariAbility(g.DeferredAbility):
    """``Immortality.SligFarmerSolariAbility`` (§6.10). ``.ctor
    @0x4e1fc20``: timing Agent; Explicit; ``Cost`` = ``HasGrafted``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _has_grafted(p, self.owner.ref)

    def can_run_immediately(self, p: Profile) -> bool:
        """``SligFarmerSolariAbility::CanRunImmediately @0x4e1fda0``: unless
        grafted to Show of Strength (``ArchID ?? Empty``)."""

        partner = _grafted_partner_of(p, self.owner.ref)
        return partner is None or partner.short != _SHOW_OF_STRENGTH

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SligFarmerSolariAbility::ValueForPlayer @0x4e1ff80``: the
        partner's Agent icon count in Solari."""

        v = Summer()
        partner = _partner(with_entities)
        if partner is not None:
            v.add("Solari Gained", p.solari_value(len(partner.list_attr("IconList"))))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``SligFarmerSolariAbility::SpecificAcquireValue @0x4e20140``:
        ``(owned cards with 3+ Agent icons - offset) x mod`` (may be
        negative)."""

        c = p.C
        n = sum(
            1 for card in _all_imperium_cards(p) if len(card.list_attr("IconList")) >= 3
        )
        v = Summer()
        v.add(
            "Agent Icons Benefit",
            (float(n) - c.TleilaxuSligFarmerCardCountOffset)
            * c.TleilaxuSligFarmerCardCountMod,
        )
        return v


@port(_AA + "Immortality.SligFarmerTleilaxuAbility")
class SligFarmerTleilaxuAbility(g.DeferredAbility):
    """``Immortality.SligFarmerTleilaxuAbility`` (§6.10). ``.ctor
    @0x4e20c50``: timing Agent; Optional; ``Cost`` = 5 Solari then
    ``CanGainTleilaxu``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.resources.solari >= 5 and _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SligFarmerTleilaxuAbility::ValueForPlayer @0x4e20f30``: with 5
        Solari, ``-5.0 x GetSolariValue(1)`` (literal) and ``TleilaxuValue(1)``.
        V prices the cost per unit while E prices ``GetSolariValue(-5)``
        (quirk kept)."""

        v = Summer()
        if p.ctx.me.resources.solari >= 5:
            v.add("Solari Cost", -5.0 * p.solari_value(1))
            v.merge(p.tleilaxu_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SligFarmerTleilaxuAbility::Evaluate @0x4e210f0``."""

        s = Summer()
        s.add("Solari Cost", p.solari_value(-5))
        s.add("Tleilaxu Value", p.tleilaxu_value(1).sum)
        choice = _Choice()
        choice.update_targets(s.sum, ())
        return choice.answer("Slig Farmer Tleilaxu")


@port(_AA + "Immortality.StitchedHorrorAbility")
class StitchedHorrorAbility(g.DeferredAbility):
    """``Immortality.StitchedHorrorAbility`` (§6.11 and Errata). ``.ctor
    @0x4e21b80``: timing Agent; Explicit; ``Cost`` = (``CanGainTleilaxu`` or
    a troop in supply) or a trashable card."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``StitchedHorrorAbility::ValueForPlayer @0x4e21f20``: the best of
        water, a troop, ``DiscardValue`` and one Tleilaxu step."""

        best = _dmax(
            _dmax(_dmax(p.water_value(1), p.troop_value(1, False)), p.discard_value()),
            p.tleilaxu_value(1).sum,
        )
        v = Summer()
        v.add("Stitched Horror Best Resource", best)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StitchedHorrorAbility::Evaluate @0x4e22150`` (§6.11, Errata).

        Options ``[(water, 0), (troop, 1), (trash, 2), (Tleilaxu, 3)]``
        sorted by value descending with ``List.Sort`` (a 4-element insertion
        sort: stable, ties keep this order; no RNG); the two best are taken.
        Trash = ``GetCardToTrash(trash targets, 1.0)`` + ``TrashCardValue``
        (0 without a trash target list); the chosen card rides along when
        option 2 is picked.

        Read in the binary: the trash value stays 0.0 when ``GetCardToTrash``
        finds no card (``test rax, rax; je 0x4e2267d`` at 0x4e22637 skips the
        ``tv + TrashCardValue`` store), not ``tv + TrashCardValue``.
        """

        water = p.water_value(1)
        troop = p.troop_value(1, False)
        tleilaxu = p.tleilaxu_value(1).sum
        trash_value = 0.0
        best: Entity | None = None
        if len(request.infos) > 1:
            best, score = p.card_to_trash(_targets(request, Kind.CARD, 1), 1.0)
            if best is not None:
                trash_value = score + p.trash_card_value()
        opts = [(water, 0), (troop, 1), (trash_value, 2), (tleilaxu, 3)]
        opts.sort(key=lambda o: o[0], reverse=True)
        pick = opts[:2]
        total = _dsum([value for value, _ in pick])
        ids = tuple(option for _, option in pick)
        choice = _Choice()
        if best is not None and 2 in ids:
            choice.update_responses(total, (ids, (best.ref,)))
        else:
            choice.update_responses(total, (ids,))
        return choice.answer(f"Stitched Horror | {ids}")


@port(_AA + "Immortality.SubjectX137Ability")
class SubjectX137Ability(g.DeferredAbility):
    """``Immortality.SubjectX137Ability`` (§6.12). ``.ctor @0x4e254d0``:
    timing Agent; Explicit; ``Cost`` = one genetic marker then
    ``CanGainTleilaxu``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 1 and _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SubjectX137Ability::ValueForPlayer @0x4e257b0``: ``GM > 0`` ->
        merge ``TleilaxuValue(1)``."""

        v = Summer()
        if _markers(p) > 0:
            v.merge(p.tleilaxu_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SubjectX137Ability::Evaluate @0x4e25910``: 100."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Subject X-137 | 100")


@port(_PA + "Immortality.TleilaxuInfiltratorAbility")
class TleilaxuInfiltratorAbility(g.DeferredAbility):
    """``Immortality.TleilaxuInfiltratorAbility`` (§6.13). ``.ctor
    @0x4c60380``: timing Agent; Explicit; ``Cost`` = two genetic markers."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TleilaxuInfiltratorAbility::ValueForPlayer @0x4c60660``: ``GM >=
        2`` -> ``IntrigueValue``."""

        v = Summer()
        if _markers(p) >= 2:
            v.add("Tleilaxu Infiltrator Draw Intrigue", p.intrigue_value())
        return v


@port(_AA + "Immortality.TwistedMentatAbility")
class TwistedMentatAbility(g.DeferredAbility):
    """``Immortality.TwistedMentatAbility`` (§6.14). ``.ctor @0x4e2bba0``:
    timing Agent; Optional; ``get_ContextuallyDeferred`` true; ``Cost``
    NoCost."""

    timing: ClassVar[Timing] = Timing.AGENT
    contextually_deferred: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TwistedMentatAbility::ValueForPlayer @0x4e2be30``: 3+ hand cards
        (literal) -> ``TwistedMentatBonus``."""

        v = Summer()
        if len(p.ctx.hand) >= 3:
            v.add("Twisted Mentat Recall", p.C.TwistedMentatBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TwistedMentatAbility::Evaluate @0x4e2bfb0``: 100."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Twisted Mentat | 100")


@port(_AA + "Immortality.UnnaturalReflexesAbility")
class UnnaturalReflexesAbility(g.DrawAbility):
    """``Immortality.UnnaturalReflexesAbility`` (§6.15): a ``DrawAbility``
    with ``Cost @0x4e2c8b0`` = one genetic marker then ``HasDrawableCard``
    (V checks it)."""

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 1 and g._has_drawable_card(p)


@port(_AA + "Promo.PiterGeniusAdvisorAbility")
class PiterGeniusAdvisorAbility(g.DeferredAbility):
    """``Promo.PiterGeniusAdvisorAbility`` (§6.16; a promo the app never
    deals). ``.ctor @0x4d90e10``: timing Agent; Optional; ``Cost`` = a
    garrisoned or deployed troop. Targets: zone codes (module docstring)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        me = p.ctx.me
        return me.troops_garrison + me.troops_conflict >= 1

    def _terms(self, p: Profile) -> Summer:
        s = Summer()
        s.add("Troop Cost", p.troop_value(-1, False))
        s.add("Draw two with Buy Gains", p.card_draw_value_with_buy_gains() * 2.0)
        s.add("Research", p.research_value().sum)
        return s

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PiterGeniusAdvisorAbility::ValueForPlayer @0x4d91240``: when
        ``MeetsCost``: a troop paid, two draws with buy gains (``addsd x,x``)
        and ``ResearchValue`` (added as one entry)."""

        if self.meets_cost(p):
            return self._terms(p)
        return Summer()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PiterGeniusAdvisorAbility::Evaluate @0x4d91450``: if positive,
        the troop as Tleilaxu Surgeon's reveal picks it, ``Take(1)``; with
        exactly two targets both are answered (app quirk kept)."""

        choice = _Choice()
        s = self._terms(p)
        if not s.sum > 0:
            return choice.answer("Piter | 0")
        if not request.infos:
            return choice.answer("Piter | no target")
        troops = _troop_choice(p, _options(request), 1)
        choice.update_targets(s.sum, troops)
        return choice.answer("Piter, Genius Advisor")


# ===========================================================================
# §7 Immortality intrigues
# ===========================================================================


@port(_PA + "Immortality.BreakthroughAbility")
class BreakthroughAbility(IntrigueAbility):
    """``Immortality.BreakthroughAbility`` (§7.1; Plot). ``Cost
    @0x4c63a90``: ``GM > 1 ? HasDrawableCard : NoCost``."""

    def meets_cost(self, p: Profile) -> bool:
        if _markers(p) > 1:
            return g._has_drawable_card(p)
        return True

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BreakthroughAbility::Evaluate @0x4c63d70``: only in the final
        round, with 4+ Intrigue or at turn start; each research space at its
        ``SpaceValue``."""

        choice = _Choice()
        if not (
            p.is_final_round()
            or _intrigue_hand_count(p) > 3
            or _in_player_turn(p, _UNDETERMINED)
        ):
            return choice.answer("Breakthrough | hold")
        for space in _targets(request, Kind.SPACE):
            value = p.research_space_value(_research_id(space)).sum
            choice.update_targets(value, (space.ref,))
        return choice.answer("Breakthrough")


@port(_PA + "Immortality.CounterattackPlotAbility")
class CounterattackPlotAbility(IntrigueAbility):
    """``Immortality.CounterattackPlotAbility`` (§7.2; Plot). ``Cost`` =
    ``CanDeployUnits``. Targets: one option index per garrison unit."""

    def troop_value(self, p: Profile) -> int:
        """``CounterattackPlotAbility::TroopValue @0x4c672f0``: 4 (read by
        ``EstStrength`` / ``PotentialStrength``, halved there)."""

        return 4

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CounterattackPlotAbility::Evaluate @0x4c67640`` (§7.2).

        In the Reveal turn with units to deploy; outside the climax only when
        the conflict interest is strictly above the posture's lower bound,
        the AI is not expected first (rank >= 2) and +4 strength would
        improve its rank. Deploys up to two units at 10.0.
        """

        choice = _Choice()
        units = _options(request)
        if not _in_player_turn(p, _REVEAL_TURN) or not units:
            return choice.answer("Counterattack | hold")
        if not p.is_climax():
            lower, _upper = p.conflict_posture_bounds()
            if not p.current_conflict_interest().sum > lower:
                return choice.answer("Counterattack | interest")
            r0 = p.estimated_conflict_rank(0)
            if r0 is None or r0 < 2:
                return choice.answer("Counterattack | first")
            r4 = p.estimated_conflict_rank(4)
            if r4 is None or not r4 < r0:
                return choice.answer("Counterattack | no gain")
        n = p.units_to_deploy(len(units), min(len(units), 2))
        choice.update_targets(10.0, tuple(units[: max(n, 0)]))
        return choice.answer("Counterattack | 10")


def _opponent_played_combat_intrigue(p: Profile) -> bool:
    """``OpponentPlayedCombatIntrigue``: another seat played a Combat Intrigue
    card in this Conflict (``state.combat_intrigue_players``, public)."""

    return any(seat != p.ctx.seat for seat in p.ctx.state.combat_intrigue_players)


@port(_PA + "Immortality.CounterattackCombatAbility")
class CounterattackCombatAbility(StrengthIntrigueAbility):
    """``Immortality.CounterattackCombatAbility`` (§7.2): a strength intrigue
    whose ``Cost @0x4c66920`` is ``OpponentPlayedCombatIntrigue``; its
    ``StrengthValue`` (base: ``MeetsCost ? Strength : 0``) is 4 or 0."""

    def meets_cost(self, p: Profile) -> bool:
        return _opponent_played_combat_intrigue(p)


@port(_PA + "Immortality.DisguisedBureaucratAbility")
class DisguisedBureaucratAbility(IntrigueAbility):
    """``Immortality.DisguisedBureaucratAbility`` (§7.3; Plot). ``Cost
    @0x4c688f0`` = one genetic marker."""

    def meets_cost(self, p: Profile) -> bool:
        return _markers(p) >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c68a30``: Late arc with research rank below 5."""

        return p.game_arc() >= 2 and p.ctx.research_rank() < 5

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DisguisedBureaucratAbility::Evaluate @0x4c68ac0`` (§7.3).

        Outside the final round, with fewer than two markers and at most 3
        Intrigue: only at turn start with an Agent left, at most 4 spice and
        research rank below 5. One marker: 1.0 (spice); two: the best
        faction track.
        """

        choice = _Choice()
        markers = _markers(p)
        me = p.ctx.me
        if not (p.is_final_round() or markers > 1 or _intrigue_hand_count(p) > 3):
            if (
                not _in_player_turn(p, _UNDETERMINED)
                or me.agents_available == 0
                or me.resources.spice > 4
                or p.ctx.research_rank() >= 5
            ):
                return choice.answer("Disguised Bureaucrat | hold")
        if markers < 2:
            choice.update_targets(1.0, None)
            return choice.answer("Disguised Bureaucrat | 1 | No Faction")
        for track in _targets(request, Kind.TRACK):
            choice.update_targets(
                p.gain_influence_value(track.ref, 1, -1, False).sum, (track.ref,)
            )
        return choice.answer("Disguised Bureaucrat")


class _ConflictTroopsIntrigue(IntrigueAbility):
    """Shared body of Economic Positioning (Combat) and Gruesome Sacrifice
    (not an app class: both derive from ``IntrigueAbility``; ``.ctor``
    timing 5 Combat; ``Cost`` = two deployed troops)."""

    timing: ClassVar[Timing] = Timing.COMBAT
    ability_timing: ClassVar[int] = COMBAT_TIMING
    #: Economic Positioning holds in the Late arc (``arc > 1``).
    LATE_HOLD: ClassVar[bool] = False

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.troops_conflict >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``EconomicPositioningCombatAbility::Evaluate @0x4c69c70`` /
        ``GruesomeSacrificeAbility::Evaluate @0x4c743f0`` (§7.4).

        Not placing now: 1.0. Placing with fewer than 3 units in the
        Conflict: hold. Losing the six strength would not cost a place: 5.0;
        it would, while 1st or 2nd: hold; else 1.0.
        """

        choice = _Choice()
        if self.LATE_HOLD and p.game_arc() > 1:
            return choice.answer(f"{type(self).__name__} | late")
        v = 1.0
        r0 = p.current_conflict_rank(0)
        if r0 is not None:
            me = p.ctx.me
            if me.troops_conflict + me.sandworms_conflict < 3:  # ConflictUnits
                return choice.answer(f"{type(self).__name__} | units")
            r6 = p.current_conflict_rank(-6)
            if r6 is not None and r6 <= r0:
                v = 5.0
            elif r0 < 3:
                return choice.answer(f"{type(self).__name__} | place")
        choice.update_targets(v, None)
        return choice.answer(f"{type(self).__name__} | {v}")


@port(_PA + "Immortality.EconomicPositioningCombatAbility")
class EconomicPositioningCombatAbility(_ConflictTroopsIntrigue):
    """``Immortality.EconomicPositioningCombatAbility`` (§7.4; ``.ctor
    @0x4c69a40``)."""

    LATE_HOLD: ClassVar[bool] = True


@port(_PA + "Immortality.EconomicPositioningEndgameAbility")
class EconomicPositioningEndgameAbility(_EndgameIntrigueAbility):
    """``Immortality.EconomicPositioningEndgameAbility`` (§7, table; ``.ctor
    @0x4c6a400``: timing Endgame). ``Cost`` = 10 Solari."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.resources.solari >= 10

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c6a810``: Late arc with fewer than 7 Solari."""

        return p.game_arc() >= 2 and p.ctx.me.resources.solari < 7


@port(_PA + "Immortality.GruesomeSacrificeAbility")
class GruesomeSacrificeAbility(_ConflictTroopsIntrigue):
    """``Immortality.GruesomeSacrificeAbility`` (§7.4; ``.ctor
    @0x4c73d80``)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c73fa0``: Late arc unless the Tleilaxu rank is
        3 or 6."""

        return p.game_arc() >= 2 and _tleilaxu(p) not in (3, 6)


@port(_PA + "Immortality.HarvestCellsAbility")
class HarvestCellsAbility(IntrigueAbility):
    """``Immortality.HarvestCellsAbility`` (§7.5). ``.ctor @0x4c74ee0``:
    timing 3 (CombatResolution), which ``HasMatchingTiming`` maps to the
    Combat turn. ``Cost @0x4c74fd0`` = ``TroopsDeployedThisConflict >= 3``
    (judgement: our troops in the Conflict). Targets: the Tleilaxu Row
    cards it may acquire (``GetHarvestCellsTargets``, UNTRACED)."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION
    ability_timing: ClassVar[int] = COMBAT_RESOLUTION_TIMING

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.troops_conflict >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c75510``: the Late arc."""

        return p.game_arc() >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``HarvestCellsAbility::Evaluate @0x4c75550``: two specimens ("no
        acquire", stored with an empty list), then each card at its
        ``AcquireValue`` + two specimens (strictly better to replace)."""

        choice = _Choice()
        specimens = p.specimen_value(2)
        choice.update_targets(specimens, ())
        for card in _targets(request, Kind.CARD):
            s = p.acquire_value(card)
            s.add("Harvest Cells Specimens", p.specimen_value(2))
            choice.update_targets(s.sum, (card.ref,))
        return choice.answer("Harvest Cells")


@port(_PA + "Immortality.IllicitDealingsAbility")
class IllicitDealingsAbility(IntrigueAbility):
    """``Immortality.IllicitDealingsAbility`` (§7.6; Plot). ``Cost`` NoCost."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c76dc0``: Late arc unless the Tleilaxu rank is
        1, 3 or 6."""

        return p.game_arc() >= 2 and _tleilaxu(p) not in (1, 3, 6)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IllicitDealingsAbility::Evaluate @0x4c77070``: at Tleilaxu rank
        1, 3 or 6 (bitmask ``0x4a``), in the final round or with 4+ Intrigue:
        ``TleilaxuValue(1)``."""

        choice = _Choice()
        t = p.tleilaxu_value(1)
        if (
            _tleilaxu(p) in (1, 3, 6)
            or p.is_final_round()
            or _intrigue_hand_count(p) >= 4
        ):
            choice.update_targets(t.sum, None)
        return choice.answer("Illicit Dealings")


@port(_PA + "Immortality.ShadowyBargainPlotAbility")
class ShadowyBargainPlotAbility(IntrigueAbility):
    """``Immortality.ShadowyBargainPlotAbility`` (§7.7; Plot). ``Cost``
    NoCost."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShadowyBargainPlotAbility::Evaluate @0x4c7a290``: one specimen
        with 4+ Intrigue, or in the Reveal turn before the Late arc or at
        Tleilaxu rank 2 or less."""

        choice = _Choice()
        v = p.specimen_value(1)
        if _intrigue_hand_count(p) > 3:
            choice.update_targets(v, None)
            return choice.answer("Shadowy Bargain | hand")
        if _in_player_turn(p, _REVEAL_TURN) and (p.game_arc() < 2 or _tleilaxu(p) <= 2):
            choice.update_targets(v, None)
        return choice.answer("Shadowy Bargain")


@port(_PA + "Immortality.ShadowyBargainEndgameAbility")
class ShadowyBargainEndgameAbility(_EndgameIntrigueAbility):
    """``Immortality.ShadowyBargainEndgameAbility`` (``.ctor @0x4c79540``:
    timing Endgame). ``Cost`` NoCost."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c79800``: Late arc unless the Tleilaxu rank is
        3 or 6."""

        return p.game_arc() >= 2 and _tleilaxu(p) not in (3, 6)


@port(_PA + "Immortality.StudyMelangePlotAbility")
class StudyMelangePlotAbility(IntrigueAbility):
    """``Immortality.StudyMelangePlotAbility`` (§7.8; Plot). ``Cost``
    NoCost."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StudyMelangePlotAbility::Evaluate @0x4c7be90`` (§7.8): one spice,
        never past research rank 5; in the final round always; else only at
        turn start below rank 5 with an Agent left and under 6 spice or with
        4+ Intrigue."""

        choice = _Choice()
        v = p.spice_value(1)
        rank = p.ctx.research_rank()
        if rank > 5:
            return choice.answer("Study Melange | rank")
        if p.is_final_round():
            choice.update_targets(v, None)
            return choice.answer("Study Melange | final round")
        me = p.ctx.me
        if (
            not _in_player_turn(p, _UNDETERMINED)
            or rank == 5
            or me.agents_available == 0
        ):
            return choice.answer("Study Melange | hold")
        if me.resources.spice < 6 or _intrigue_hand_count(p) >= 4:
            choice.update_targets(v, None)
        return choice.answer("Study Melange")


@port(_PA + "Immortality.StudyMelangeEndgameAbility")
class StudyMelangeEndgameAbility(_EndgameIntrigueAbility):
    """``Immortality.StudyMelangeEndgameAbility`` (``.ctor @0x4c7b160``:
    timing Endgame). ``Cost`` = 3 spice then two genetic markers."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.resources.spice >= 3 and _markers(p) >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c7b5e0``: Late arc with research rank below 5."""

        return p.game_arc() >= 2 and p.ctx.research_rank() < 5


@port(_PA + "Immortality.TleilaxuPuppetPlotAbility")
class TleilaxuPuppetPlotAbility(IntrigueAbility):
    """``Immortality.TleilaxuPuppetPlotAbility`` (§7.9; Plot). ``Cost``
    NoCost. Holding the card also multiplies the High Council space value
    (``abilities/board.py``)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TleilaxuPuppetPlotAbility::Evaluate @0x4c7d6e0``: never with the
        High Council seat past research rank 5; 10.0 with 4+ Intrigue or in
        the Reveal turn when one more Persuasion buys at least 1.33 (literal)
        more."""

        choice = _Choice()
        rank = p.ctx.research_rank()
        buy_gains = p.buy_gains(1)
        if p.ctx.me.high_council and rank > 5:
            return choice.answer("Tleilaxu Puppet | hold")
        if _intrigue_hand_count(p) > 3 or (
            _in_player_turn(p, _REVEAL_TURN) and buy_gains >= 1.33
        ):
            choice.update_targets(10.0, None)
        return choice.answer("Tleilaxu Puppet")


@port(_PA + "Immortality.TleilaxuPuppetEndgameAbility")
class TleilaxuPuppetEndgameAbility(_EndgameIntrigueAbility):
    """``Immortality.TleilaxuPuppetEndgameAbility`` (``.ctor @0x4c7c7d0``:
    timing Endgame). ``Cost`` = the High Council seat then two genetic
    markers."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.high_council and _markers(p) >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c7cca0``: Late arc, seated, research rank below
        5 (the seat test is as the app has it)."""

        return p.game_arc() >= 2 and p.ctx.me.high_council and p.ctx.research_rank() < 5


@port(_PA + "Immortality.ViciousTalentsAbility")
class ViciousTalentsAbility(StrengthIntrigueAbility):
    """``Immortality.ViciousTalentsAbility`` (§7.10). ``Cost`` NoCost; E is
    ``StrengthIntrigueAbility``'s."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue @0x4c7ffa0``: ``2 * GM + 2`` (no cost check)."""

        return 2 * _markers(p) + 2

    def combat_value(self, p: Profile) -> float:
        """``CombatValue @0x4c7ff40``: ``GM > 1 ? 7.0 : [2.0, 5.25][GM > 0]``
        (table ``@0x52f3d10``)."""

        markers = _markers(p)
        if markers > 1:
            return 7.0
        return (2.0, 5.25)[1 if markers > 0 else 0]
