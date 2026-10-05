"""Immortality — spec/immortality.md §2: the ``WormAIProfile`` parts.

Research and Tleilaxu-track values, the research-space value of
``WormResearchTrack`` and the Tleilaxu Row the other readers iterate. The
Immortality terms of the methods that live elsewhere are in those methods:
``GetResourceValue`` (Specimen row bonus, Economic Positioning),
``AcquireValue`` (the Tleilaxu branch), ``GetSynergyMod`` (Helix),
``GetAcquireEffectsValue`` (Research, Shadow), ``GetCardToTrash``
(Replacement Eyes) and ``GetRevealPreview`` in ``economy.py``;
``DeployValue`` (Economic Positioning), ``IntrigueHandStrengthValue``
(Counterattack, Vicious Talents) and the "Intrigue Troop Value" of
``EstStrength``/``PotentialStrength`` in ``combat.py``.

Nothing here is gated by ``IsSetEnabled(Immortality)``: the app reads the
tracks unconditionally (they always exist, ``WormBoard::.ctor @0x48267c0``)
and they stay at their start without the expansion (``AppContext``'s
Immortality block). Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

from typing import TYPE_CHECKING, NamedTuple, cast

from dune_imperium.agents.app_ai.catalog import card_entity, intrigue_entity
from dune_imperium.agents.app_ai.context import RESEARCH_SPACE_IDS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# -- the research-space bonus abilities (``AbilityID`` = full class name) ---------

_ACTIVATED = "worm.canis.abilities.ActivatedAbilities."
GAIN_TLEILAXU_CUSTOM = _ACTIVATED + "Immortality.GainTleilaxuInfluenceCustomAbility"
GAIN_RESEARCH_CUSTOM = _ACTIVATED + "Immortality.GainResearchCustomAbility"
TRASH_CUSTOM = _ACTIVATED + "TrashCustomAbility"
GAIN_ANY_FACTION_INFLUENCE_CUSTOM = (
    _ACTIVATED + "RiseOfIx.GainAnyFactionInfluenceCustomAbility"
)
TRASH_INTRIGUE_FOR_DRAW_AND_INTRIGUE = (
    _ACTIVATED + "Immortality.TrashIntrigueForDrawAndIntrigue"
)
PAY_SOLARI_FOR_TLEILAXU = _ACTIVATED + "Immortality.PaySolariForTleilaxuInfluence"


class ResearchSpaceDef(NamedTuple):
    """One entry of ``WormResearchTrack::get_SpaceDefs @0x49b4e40``.

    The resources the space grants on arrival and the ``AbilityIDs`` it adds
    as custom abilities (``ChangeRankBonuses @0x49bb510``). ``next`` is the
    app's ``NextIndices`` (kept for the cross-check with our board).
    """

    specimens: int = 0
    spice: int = 0
    solari: int = 0
    troops: int = 0
    abilities: tuple[str, ...] = ()
    next: tuple[int, ...] = ()


#: The 22 research spaces by app index (spec immortality.md §1.5, re-read in
#: ``get_SpaceDefs``): literal data of the app's code, in the order of our
#: ``RESEARCH_SPACES`` (``AppContext.research_rank``). No space grants troops.
RESEARCH_SPACE_DEFS: tuple[ResearchSpaceDef, ...] = (
    ResearchSpaceDef(next=(1,)),  # 0 c0r3 start
    ResearchSpaceDef(specimens=1, next=(2, 3)),  # 1 c1r3
    ResearchSpaceDef(specimens=1, next=(4, 5)),  # 2 c2r2
    ResearchSpaceDef(abilities=(GAIN_TLEILAXU_CUSTOM,), next=(5, 6)),  # 3 c2r4
    ResearchSpaceDef(abilities=(GAIN_RESEARCH_CUSTOM,), next=(7,)),  # 4 c3r1
    ResearchSpaceDef(specimens=1, abilities=(TRASH_CUSTOM,), next=(7, 8)),  # 5 c3r3
    ResearchSpaceDef(  # 6 c3r5
        specimens=1, abilities=(GAIN_TLEILAXU_CUSTOM,), next=(8, 9)
    ),
    ResearchSpaceDef(abilities=(GAIN_TLEILAXU_CUSTOM,), next=(10, 11)),  # 7 c4r2
    ResearchSpaceDef(specimens=1, next=(11, 12)),  # 8 c4r4
    ResearchSpaceDef(abilities=(GAIN_RESEARCH_CUSTOM,), next=(12,)),  # 9 c4r6
    ResearchSpaceDef(abilities=(GAIN_RESEARCH_CUSTOM,), next=(13,)),  # 10 c5r1
    ResearchSpaceDef(specimens=1, next=(13, 14)),  # 11 c5r3
    ResearchSpaceDef(solari=1, next=(14, 15)),  # 12 c5r5
    ResearchSpaceDef(spice=1, next=(16, 17)),  # 13 c6r2
    ResearchSpaceDef(abilities=(GAIN_TLEILAXU_CUSTOM,), next=(17, 18)),  # 14 c6r4
    ResearchSpaceDef(abilities=(GAIN_ANY_FACTION_INFLUENCE_CUSTOM,), next=(18,)),  # 15
    ResearchSpaceDef(abilities=(GAIN_TLEILAXU_CUSTOM,), next=(19,)),  # 16 c7r1
    ResearchSpaceDef(  # 17 c7r3
        abilities=(TRASH_INTRIGUE_FOR_DRAW_AND_INTRIGUE,), next=(19, 20)
    ),
    ResearchSpaceDef(specimens=1, abilities=(TRASH_CUSTOM,), next=(20, 21)),  # 18
    ResearchSpaceDef(spice=2),  # 19 c8r2 (marker 2)
    ResearchSpaceDef(abilities=(GAIN_TLEILAXU_CUSTOM,)),  # 20 c8r4 (marker 2)
    ResearchSpaceDef(abilities=(PAY_SOLARI_FOR_TLEILAXU,)),  # 21 c8r6 (marker 2)
)


def research_space_entity(space_id: str) -> Entity:
    """The app's research ``WormSpace`` for our research space ``space_id``.

    The owner of the space's bonus-ability prototypes in
    ``research_space_value``. The app has no archetype for it (the
    attributes are built in ``get_SpaceDefs``); ``ref`` is
    ``research:<space id>``.
    """

    return Entity(Kind.SPACE, f"research:{space_id}", None)


class ImmortalityMixin(ProfileCore):
    """The Immortality ``WormAIProfile`` methods."""

    def _profile(self) -> Profile:
        """``self`` as the full ``Profile`` the ability hooks expect."""

        return cast("Profile", self)

    def _helix_count(self, tag: str) -> int:
        """``AllImperiumCards.Count(tag) + IntrigueHand.children.Count(tag)``.

        ``<ResearchValue>b__141_0..3``; the app adds the Intrigue count to
        the Imperium count (``add r12d, [rbp-0x2c]``).
        """

        seat = self.ctx.seat
        held = sum(
            1
            for instance in self.ctx.intrigue_cards
            if tag in intrigue_entity(instance, seat).list_attr("Tags")
        )
        return held + self._profile()._owned_with_tag(tag)

    # ===========================================================================
    # §2.1 ResearchValue
    # ===========================================================================

    def research_value(self) -> Summer:
        """``WormAIProfile::ResearchValue @0x490ea70`` (spec §2.1).

        Base 2.25 per arc; after the first genetic marker the Double Helix
        cards (Imperium cards anywhere plus held Intrigue) add 1.0 each,
        before it the Helix cards 0.75 each; with both markers the track is
        done and Research is a card draw (``get_CardDrawValue``, no buy
        gains). The counts are ``double(n) * K`` (``cvtsi2sd; mulsd``).
        """

        c = self.C
        s = Summer()
        s.add(
            "Base Research Value",
            (c.ResearchValueEarly, c.ResearchValueMid, c.ResearchValueLate)[
                self.game_arc()
            ],
        )
        markers = self.ctx.genetic_markers()
        if markers > 0:
            if markers > 1:
                s.multiply("End of Track", 0.0)
                s.add("Draw Card", self.card_draw_value())
                return s
            n = self._helix_count("DoubleHelix")
            s.add("Mid Step Mod", float(n) * c.ResearchStepValueDoubleHelixMod)
        else:
            n = self._helix_count("Helix")
            s.add("Early Step Mod", float(n) * c.ResearchStepValueSingleHelixMod)
        return s

    # ===========================================================================
    # §2.2 TleilaxuValue
    # ===========================================================================

    def tleilaxu_value(self, amount: int) -> Summer:
        """``WormAIProfile::TleilaxuValue(int amount) @0x490f130`` (spec §2.2).

        2.25 per step; at rank 7 the value is multiplied away. Crossing rank
        2 or 6 adds the intrigue bonus once, crossing 4 or 7 the flat VP
        bonus (4.0, not ``GetVictoryPointValue``) once; a single Late-arc
        step from rank 0, 2 or 4 (onto a space without a bonus) is cut to a
        quarter. The ranks 2, 4, 6, 7 and the bitmask ``0x15`` are literals
        of the app's code. The first-arrival 2 spice at rank 4 is not valued.
        """

        c = self.C
        s = Summer()
        base = (c.TleilaxuValueEarly, c.TleilaxuValueMid, c.TleilaxuValueLate)[
            self.game_arc()
        ]
        s.add("Tleilaxu Influence", base * float(amount))
        current = self.ctx.tleilaxu_influence()
        if current == 7:  # cmp eax, 7
            s.multiply("End of Track", 0.0)
            return s
        new = current + amount
        if (current < 2 and new >= 2) or (current < 6 and new >= 6):
            s.add("Gain Intrigue Card", c.TleilaxuTrackIntrigue)
        if (current < 4 and new >= 4) or (current < 7 and new >= 7):
            s.add("Gain VP", c.TleilaxuTrackVP)
        # amount == 1, arc >= 2 (second GetGameArc call), cur <= 4 and bit cur
        # of 0x15 (``bt``): cur in {0, 2, 4}.
        if amount == 1 and self.game_arc() >= 2 and current in (0, 2, 4):
            s.multiply("Late Game No Bonus", c.TleilaxuTrackLateGameMod)
        if self.ctx.scouts:  # app-style Arrakeen Scouts (scouts.md §4.6, D37)
            offered = self._profile().tleilaxu_offering_specimens(amount)
            if offered > 0:
                s.add("Tleilaxu Offering", self.specimen_value(offered))
        return s

    # ===========================================================================
    # §2.10 WormResearchTrack::SpaceValue
    # ===========================================================================

    def research_space_value(self, space_id: str) -> Summer:
        """``WormResearchTrack::SpaceValue(space, forPlayer) @0x49b9900``.

        Spec §2.10: the space's resources (specimens, spice, Solari, troops,
        each only when > 0, in that order) plus the ``ValueForPlayer(P, [])``
        of every bonus-ability prototype of the space, merged in definition
        order. The genetic marker a space carries is not valued here.
        """

        definition = RESEARCH_SPACE_DEFS[RESEARCH_SPACE_IDS.index(space_id)]
        s = Summer()
        if definition.specimens > 0:
            s.add("Specimens", self.specimen_value(definition.specimens))
        if definition.spice > 0:
            s.add("Spice", self.spice_value(definition.spice))
        if definition.solari > 0:
            s.add("Solari", self.solari_value(definition.solari))
        if definition.troops > 0:
            s.add("Troops", self.troop_value(definition.troops, False))
        if definition.abilities:
            from dune_imperium.agents.app_ai.abilities import ability_for

            owner = research_space_entity(space_id)
            profile = self._profile()
            for ability_class in definition.abilities:
                ability = ability_for(ability_class, owner)
                s.merge(ability.value_for_player(profile, ()))
        if self.ctx.scouts:  # app-style Arrakeen Scouts: Sponsored Research
            s.merge(self._profile().sponsored_research_value(space_id))
        return s

    # ===========================================================================
    # The Tleilaxu Row
    # ===========================================================================

    def tleilaxu_row_cards(self) -> list[Entity]:
        """``Playmat.TleilaxuRow.children.OfType<WormImperiumPlayable>()``.

        Reclaimed Forces first, then the two face-up cards in row order
        (``AppContext.tleilaxu_row``); empty without Immortality.
        """

        return [card_entity(instance) for instance in self.ctx.tleilaxu_row]
