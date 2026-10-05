"""Board spaces, conflict cards and rewards, CHOAM contracts — spec/board.md.

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``). The generic
classes these build on (``SpaceAbility``, ``DeferredAbility``,
``ContractAbility``, ``ConflictAbility``, ``TriggeredAbility``, the draw,
influence, intrigue, deploy, trash, spy, recall-agent and contract-gain
abilities and the generic conflict rewards) are in ``abilities/generic.py``;
this module holds the space-, conflict- and contract-specific subclasses and
the two playmat spy abilities the Agent turn asks about. Which abilities a
Conflict reward grants (``granted_reward_abilities``) is read here for every
card, including Economic Supremacy, whose rewards live on the card's own
abilities (``abilities/epic_promo.py``) instead of reward archetypes.

App class chains (``dump/worm-canis.dll.cs``):

- ``SpaceAbilities.SpaceAbility`` <- ``BaseSet.HighCouncilSpaceAbility``,
  ``Uprising.HighCouncilUprisingSpaceAbility``,
  ``Uprising.SwordmasterUprisingSpaceAbility``,
  ``BaseSet.HeighlinerSpaceAbility``, ``BaseSet.SecretsSpaceAbility``,
  ``Uprising.EspionageSpaceAbility``, ``Uprising.AssemblyHallSpaceAbility``,
  ``Uprising.GatherSupportAbility``, ``Uprising.SpiceRefineryAbility``;
- ``ActivatedAbilities.DeferredAbility`` <-
  ``Uprising.SietchTabrUprisingDeferredSpaceAbility``,
  ``Uprising.DesertSpaceDeferredAbility`` (abstract) <- ``DeepDesert…`` /
  ``HaggaBasinUprising…``, ``Uprising.ImperialPrivilegeAbility``,
  ``Uprising.RecallSpyInfiltrateAbility``,
  ``Uprising.RecallSpyIntelligenceAbility``;
- ``ContractAbilities.ContractAbility`` <- ``Harvest3/4ContractAbility``,
  ``RecallAgentContractAbility``, ``TSMFContractAbility``,
  ``BeneGesseritContractAbility``;
- ``ConflictAbilities.ConflictAbility`` <-
  ``Uprising.GainAnyTwoInfluenceConflictAbility``;
- ``TriggeredAbilities.TriggeredAbility`` <- ``BaseSet.HighCouncilAbility2``,
  ``Uprising.AssemblyHallAbility``,
  ``Uprising.ActivateTSMFContractTriggeredAbility``.

Request / answer encoding (``abilities/generic.py``): candidates are the first
target info's ``entities`` or custom-choice ``options``; ``Answer.response``
holds one item per target info (refs or option indices), ``()`` = "use with no
sub-target" (the app's ``UpdateSelectionTargets(v, src, null)`` or an empty
id array), ``None`` = nothing stored (value 0). The app's ``IntTargetResponse
(k)`` / ``IntListTargetResponse(k)`` answers are option ``k``.

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.epic_promo import (
    EconomicSupremacyFirstAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    ConflictAbility,
    ContractAbility,
    DeferredAbility,
    GenericConflictAbility,
    HighCouncilGainIntrigueAbility,
    SpaceAbility,
    TriggeredAbility,
    _deployed_spies,
    _leader_arch_id,
    _no_current_player,
    _space_bonus_spice,
    _targets,
    collect_first,
    conflict_reward,
    contract_spaces,
    deferred_threshold_reached,
    gain_any_influence_value,
)
from dune_imperium.agents.app_ai.catalog import INTRIGUE_ARCHETYPES, conflict_entity
from dune_imperium.agents.app_ai.context import FACTIONS, card_id
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# ---------------------------------------------------------------------------
# Archetype ids the board abilities test (``ArchID`` / ``HasIntrigueCard``)
# ---------------------------------------------------------------------------

_MUAD_DIB = "LeaderArchetypes.Uprising.MuadDib"
# Base-game leader tested by HighCouncilSpaceAbility; never dealt in Uprising.
_EARL_MEMNON = "LeaderArchetypes.BaseSet.EarlMemnonThorvald"
_COUNCILORS_AMBITION = "IntrigueArchetypes.Uprising.CouncilorsAmbition"
# Non-Uprising intrigues and tech tile the High Council value also tests; no
# 4-player Uprising deck holds them, so their terms never fire here.
_COUNCILORS_DISPENSATION = "IntrigueArchetypes.BaseSet.CouncilorsDispensation"
_SECRET_FORCES = "IntrigueArchetypes.RiseOfIx.SecretForces"
_GRAND_CONSPIRACY = "IntrigueArchetypes.RiseOfIx.GrandConspiracy"
_TLEILAXU_PUPPET = "IntrigueArchetypes.Immortality.TleilaxuPuppet"
_RESTRICTED_ORDNANCE = "TechTileArchetypes.RiseOfIx.RestrictedOrdnance"


# ---------------------------------------------------------------------------
# Honest reads (AppContext rules: own zones, other seats' public fields)
# ---------------------------------------------------------------------------


def _has_intrigue_card(p: Profile, archetype: str) -> bool:
    """``WormPlayer::HasIntrigueCard(archID)`` @0x4835970 (own Intrigue hand)."""

    return any(
        INTRIGUE_ARCHETYPES.get(card_id(i)) == archetype for i in p.ctx.intrigue_cards
    )


def _has_tech_tile(p: Profile, archetype: str) -> bool:
    """``WormPlayer::HasTechTile`` @0x4835a60: Rise of Ix only, never held."""

    return False


def _current_conflict(p: Profile) -> Entity | None:
    """``WormMatchExtensions::CurrentConflict`` @0x480f5b0 (face-up card)."""

    conflict_id = p.ctx.current_conflict_id
    if conflict_id is None:
        return None
    return conflict_entity(conflict_id, p.ctx.choam)


def _conflict_level(conflict: Entity) -> int:
    """``GetAttributeValue<int>(ConflictLevel)`` with the default 1."""

    return conflict.int_attr("ConflictLevel", 1)


def _can_deploy_sandworms(p: Profile) -> bool:
    """``WormPlayer::get_CanDeploySandworms`` @0x483dc40.

    ``CanDeploy`` (@0x483db50: the conflict area's ``Deployable`` flag, which
    only Shaddam's signet clears for its turn; ours ``units_deployment_
    blocked`` on the seat's own turn frame) and not ``Board.
    CurrentConflictBehindShieldWall`` (ours ``current_conflict_is_shield_
    wall_protected``, public board state).
    """

    state = p.ctx.state
    if units_deployment_blocked(state, p.ctx.seat):
        return False
    return not current_conflict_is_shield_wall_protected(state)


def _dsum(values: Sequence[float]) -> float:
    """``Enumerable.Sum`` over doubles: left to right from 0.0 (no
    compensation, unlike Python's ``sum`` of floats)."""

    total = 0.0
    for value in values:
        total += value
    return total


def _math_max(a: float, b: float) -> float:
    """``System.Math.Max(double, double)``: NaN if either is NaN."""

    if a != a or b != b:
        return float("nan")
    return a if a >= b else b


# ===========================================================================
# 1. Board spaces (board.md §1.4)
# ===========================================================================

# -- High Council (§1.4.10) -------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.BaseSet.HighCouncilSpaceAbility")
class HighCouncilSpaceAbility(SpaceAbility):
    """``SpaceAbilities.BaseSet.HighCouncilSpaceAbility``: taking the seat."""

    def meets_cost(self, p: Profile) -> bool:
        """``HighCouncilSpaceAbility::Cost`` @0x4bc76d0 as ``MeetsCost`` reads it.

        ``SpaceAbility.Cost.Then(BoolAction(P.CanTakeHighCouncilSeat()))``
        with ``WormPlayer::CanTakeHighCouncilSeat`` @0x48457c0 = the player's
        ``CanTakeHighCouncilSeat`` attribute (never cleared in Uprising) and
        not ``HighCouncilSeat``. Judgement: the ``SpaceAbility.Cost`` part
        (Solari cost, ``CanPlaceAgent``, matching icon) is taken as met —
        ``ValueForPlayer`` is reached for legal spaces only (agent placement)
        or not at all (``GetRecallAgent`` scores the High Council in its
        100 tier without the space value).
        """

        return not p.ctx.me.high_council

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HighCouncilSpaceAbility::ValueForPlayer`` @0x4bc7b60 (board §1.4.10).

        The generic space value (``Array.Empty`` instead of the card), then,
        when the seat can be taken: ``HighCouncilValue`` and the leader /
        intrigue / tech terms in the binary's order. Only Councilor's
        Ambition is live in Uprising.
        """

        v = super().value_for_player(p, ())
        if not self.meets_cost(p):
            return v
        c = p.C
        v.add("Space High Council", p.high_council_value())
        if _leader_arch_id(p) == _EARL_MEMNON:  # base leader
            v.add(
                "Earl Memnon Thorvald High Council Bonus",
                gain_any_influence_value(p, 1).sum,
            )
        if _has_intrigue_card(p, _COUNCILORS_DISPENSATION):  # BaseSet
            v.add("Councilors Dispensation Bonus", p.spice_value(2))
        if _has_intrigue_card(p, _SECRET_FORCES):  # Rise of Ix
            v.add("Secret Forces Bonus", p.troop_value(1, False) * c.SecretForcesMod)
        if _has_intrigue_card(p, _GRAND_CONSPIRACY):  # Rise of Ix
            v.multiply("Grand Conspiracy Bonus", c.GrandConspiracyHighCouncilMod)
        if _has_tech_tile(p, _RESTRICTED_ORDNANCE):  # Rise of Ix
            v.multiply("Restricted Ordnance Bonus", c.RestrictedOrdnanceHighCouncilMod)
        if _has_intrigue_card(p, _TLEILAXU_PUPPET):  # Immortality
            v.multiply("Tleilaxu Puppet Mod", c.TleilaxuPuppetHighCouncilMod)
        if _has_intrigue_card(p, _COUNCILORS_AMBITION):
            v.add("Councilor's Ambition Mod", c.CouncilorsAmbitionMod)
        return v


@port("worm.canis.abilities.SpaceAbilities.Uprising.HighCouncilUprisingSpaceAbility")
class HighCouncilUprisingSpaceAbility(SpaceAbility):
    """``SpaceAbilities.Uprising.HighCouncilUprisingSpaceAbility``: the repeat
    visit (2 spice, 3 troops; the intrigue is ``HighCouncilGainIntrigue
    Ability``)."""

    def meets_cost(self, p: Profile) -> bool:
        """``HighCouncilUprisingSpaceAbility::Cost`` @0x4bbce00 =
        ``SpaceAbility.Cost.Then(MakeRepeatedVisitCost)`` (@0x4bbcce0).

        ``MakeRepeatedVisitCost`` is also ``HighCouncilGainIntrigueAbility::
        Cost`` (@0x4d1a1b0); its port (generic) is reused so both read the
        repeat visit the same way (``IsRepeatHighCouncilUse`` agent branch
        UNTRACED, board §6). The ``SpaceAbility.Cost`` part is taken as met,
        as in ``HighCouncilSpaceAbility.meets_cost``.
        """

        return HighCouncilGainIntrigueAbility(self.owner).meets_cost(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HighCouncilUprisingSpaceAbility::ValueForPlayer`` @0x4bbcfa0.

        Calls the generic space value again (quirk kept: the High Council's
        Solari cost, contract and spy terms count twice, board §5).
        """

        v = super().value_for_player(p, ())
        if self.meets_cost(p):
            v.add("High Council UP Spice", p.spice_value(2))  # literal 2
            v.add("High Council UP Troops", p.troop_value(3, False))  # literal 3
        return v


@port("worm.canis.abilities.TriggeredAbilities.BaseSet.HighCouncilAbility2")
class HighCouncilAbility2(TriggeredAbility):
    """``TriggeredAbilities.BaseSet.HighCouncilAbility2``: +2 Persuasion at
    each Reveal for the seat holder. No AI hook (V = 0)."""

    should_exhaust: ClassVar[bool] = False  # @0x4b58970


# -- Swordmaster (§1.4.11) --------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.Uprising.SwordmasterUprisingSpaceAbility")
class SwordmasterUprisingSpaceAbility(SpaceAbility):
    """``SpaceAbilities.Uprising.SwordmasterUprisingSpaceAbility``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SwordmasterUprisingSpaceAbility::ValueForPlayer`` @0x4bc29d0.

        The generic value (its Solari cost is the runtime 8 or 6,
        ``generic.space_solari_cost``) plus ``SwordmasterValue``.
        """

        v = super().value_for_player(p, ())
        v.add("Space Swordmaster", p.swordmaster_value())
        return v


# -- Heighliner (§1.4.12) ---------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.BaseSet.HeighlinerSpaceAbility")
class HeighlinerSpaceAbility(SpaceAbility):
    """``SpaceAbilities.BaseSet.HeighlinerSpaceAbility`` (``HeighlinerUP``)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HeighlinerSpaceAbility::ValueForPlayer`` @0x4bc68f0 (board §1.4.12).

        Reads ``ConflictPostureBounds`` before ``CurrentConflictInterest``,
        as the binary does. Supply = troops in the player's supply
        (``troops_supply``); ``RemainingAgents`` = ``agents_available``.
        """

        v = super().value_for_player(p, ())
        c = p.C
        me = p.ctx.me
        lower, upper = p.conflict_posture_bounds()
        interest = p.current_conflict_interest().sum
        supply = me.troops_supply
        bonus = False
        if supply >= 3:
            if interest > upper:
                bonus = True
            elif interest > lower:
                conflict = _current_conflict(p)
                bonus = conflict is not None and _conflict_level(conflict) == 3
        if bonus:
            v.add("Space Heighliner", c.HeighlinerSpaceBonus)
        elif supply <= 1:  # supply >= 3 with a failed bonus test lands here too
            conflict = _current_conflict(p)
            if conflict is None or _conflict_level(conflict) <= 2:
                v.add("Low Troop Supply", c.HeighlinerSpaceLowSupplyPenalty)
        spice_cost = self.owner.int_attr("SpiceCost")
        # b__8_0 @0x4bc6e60: op.Spice <= Owner.SpiceCost - 1 (nobody else can pay).
        if (
            all(o.resources.spice <= spice_cost - 1 for o in p.ctx.opponents)
            and me.agents_available >= 2
        ):
            v.add(
                "Early In Round",
                c.HeighlinerSpaceEarlyInRoundPenalty * float(me.agents_available - 1),
            )
        return v


# -- Secrets, Espionage (§1.4.13-14) -----------------------------------------------


def _lady_jessica_memories(p: Profile, v: Summer) -> None:
    """The shared "Lady Jessica Memories" term of Secrets and Espionage.

    ``LadyJessicaReturnMemories`` then ``LadyJessicaOtherMemoriesMod x
    (P.Memories()?.children.Count ?? 0)`` (ours ``memories``).
    """

    if p.lady_jessica_return_memories():
        v.add(
            "Lady Jessica Memories",
            p.C.LadyJessicaOtherMemoriesMod * float(p.ctx.me.memories),
        )


@port("worm.canis.abilities.SpaceAbilities.BaseSet.SecretsSpaceAbility")
class SecretsSpaceAbility(SpaceAbility):
    """``SpaceAbilities.BaseSet.SecretsSpaceAbility``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SecretsSpaceAbility::ValueForPlayer`` @0x4bcb760 (board §1.4.13).

        ``n`` = other seats holding 4 or more Intrigue cards (b__0
        @0x4bcbd60; the public hand count); the steal term is added even at
        ``n = 0``.
        """

        v = super().value_for_player(p, ())
        n = sum(
            1
            for pv in p.ctx.view.players
            if pv.player != p.ctx.seat and pv.intrigue_card_count >= 4
        )
        v.add("Space Secrets", (p.C.IntrigueStealBonus + p.intrigue_value()) * float(n))
        _lady_jessica_memories(p, v)
        return v


@port("worm.canis.abilities.SpaceAbilities.Uprising.EspionageSpaceAbility")
class EspionageSpaceAbility(SpaceAbility):
    """``SpaceAbilities.Uprising.EspionageSpaceAbility``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EspionageSpaceAbility::ValueForPlayer`` @0x4bb9c70 (board §1.4.14)."""

        v = super().value_for_player(p, ())
        _lady_jessica_memories(p, v)
        return v


# -- Assembly Hall (§1.4.15) -------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.Uprising.AssemblyHallSpaceAbility")
class AssemblyHallSpaceAbility(SpaceAbility):
    """``SpaceAbilities.Uprising.AssemblyHallSpaceAbility``: no AI override
    (the generic space value: spy and contract terms only)."""


@port("worm.canis.abilities.TriggeredAbilities.Uprising.AssemblyHallAbility")
class AssemblyHallAbility(TriggeredAbility):
    """``TriggeredAbilities.Uprising.AssemblyHallAbility``: +1 Persuasion on
    the Reveal turn while the Agent stands here."""

    should_exhaust: ClassVar[bool] = False  # @0x4a90ca0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``AssemblyHallAbility::ValueForPlayer`` @0x4a90ea0."""

        v = Summer()
        v.add("Assembly Hall Persuasion", p.persuasion_value(1))  # literal 1
        return v


# -- Gather Support (§1.4.16) ------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.Uprising.GatherSupportAbility")
class GatherSupportAbility(SpaceAbility):
    """``SpaceAbilities.Uprising.GatherSupportAbility`` (2 troops; may pay 2
    Solari for 1 water)."""

    def find_solari_cost(self) -> int:
        """``GatherSupportAbility::FindSolariCost`` @0x4bba100:
        ``PossibleSolariCost`` (default 2) + ``SolariDiscount`` (default 0)."""

        return self.owner.int_attr("PossibleSolariCost", 2) + self.owner.int_attr(
            "SolariDiscount", 0
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GatherSupportAbility::ValueForPlayer`` @0x4bba460 (board §1.4.16).

        The water trade is counted whenever it is worth more than its cost,
        without checking that the AI holds the Solari (quirk kept).
        """

        cost = self.find_solari_cost()
        v = super().value_for_player(p, ())
        trade = p.solari_value(-cost) + p.water_value(1)
        if trade > 0:
            v.add(f"{cost} Solari -> Water", trade)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GatherSupportAbility::Evaluate`` @0x4bba660 (the pay prompt).

        Option 0 = do not pay, option 1 = pay (the app's ``IntListTarget
        Response`` values; the button mapping is UNTRACED, board §6). Without
        the Solari nothing is stored (value 0).
        """

        cost = self.find_solari_cost()
        if p.ctx.me.resources.solari < cost:
            return Answer(0.0, None, "GatherSupport | cannot pay")
        s = Summer()
        s.add("Water", p.water_value(1))
        s.add("Solari Cost", p.solari_value(-cost))
        if 0.0 >= s.sum:
            return Answer(1.0, ((0,),), "GatherSupport | keep Solari")
        return Answer(_math_max(s.sum, 1.0), ((1,),), f"GatherSupport | spend {cost}")


# -- Spice Refinery (§1.4.19) ------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.Uprising.SpiceRefineryAbility")
class SpiceRefineryAbility(SpaceAbility):
    """``SpaceAbilities.Uprising.SpiceRefineryAbility`` (2 Solari, or pay 1
    spice for 4)."""

    @staticmethod
    def solari_amount(spice: int) -> int:
        """``SpiceRefineryAbility::SolariAmount`` @0x4bbf550: ``2n + 2``."""

        return 2 * spice + 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceRefineryAbility::ValueForPlayer`` @0x4bbf890 (board §1.4.19).

        The optional trade is counted without checking that the AI holds
        spice (quirk kept).
        """

        v = super().value_for_player(p, ())
        s2 = p.solari_value(2)  # literal 2
        s1 = p.spice_value(1)  # literal 1
        v.add("2 * SolariValue", s2)
        if s2 > s1:
            v.add("2 SolariValue > SpiceValue", s2)
            v.add("- SpiceValue", -s1)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpiceRefineryAbility::Evaluate`` @0x4bbfb90 (the "SellMelange"
        int prompt: how much spice to pay).

        ``GetSpiceForSpiceRefinery`` decides (sell 1 whenever one Solari is
        worth at least the threshold and the AI holds spice); the value is
        only floored at 1.0 ("Ensure positive value"). The answer is option
        ``n`` (the spice paid).
        """

        n = p.spice_for_spice_refinery()
        if n < 0:
            return Answer(0.0, None, "SpiceRefinery | no answer")
        s = Summer()
        s.add("Solari", p.solari_value(self.solari_amount(n)))
        s.add("Spice Cost", p.spice_value(-n))
        if 0.0 >= s.sum:
            s.multiply("Reset", 0.0)
            s.add("Ensure positive value", 1.0)
        return Answer(s.sum, ((n,),), f"SpiceRefinery | sell {n}")


# -- Sietch Tabr (§1.4.17) ---------------------------------------------------------


@port(
    "worm.canis.abilities.SpaceAbilities.Uprising.SietchTabrUprisingDeferredSpaceAbility"
)
class SietchTabrUprisingDeferredSpaceAbility(DeferredAbility):
    """``SpaceAbilities.Uprising.SietchTabrUprisingDeferredSpaceAbility``:
    option 0 = maker hooks + 1 water + 1 troop, option 1 = 1 water and the
    Shield Wall grant (``BlowWallCustomAbility``). Timing None (no timing in
    the ctor); ``Cost`` = ``NoCostAction``."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SietchTabrUprisingDeferredSpaceAbility::SelectionMode`` @0x4bbdb40:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SietchTabrUprisingDeferredSpaceAbility::ValueForPlayer`` @0x4bbdd70.

        No generic space value (the space's ``SpaceAbility`` carries it).
        ``(hooks + water) + troop`` against ``wall + water``; a tie goes to
        "Blow Wall" (quirk). ``BlowWallValue`` ignores whether the wall still
        stands.
        """

        v = Summer()
        water = p.water_value(1)
        hooks = p.maker_hooks_value()
        troop = p.troop_value(1, False)
        wall = p.blow_wall_value().sum
        hooks_side = hooks + water + troop
        wall_side = wall + water
        if hooks_side > wall_side:
            v.add("Maker Hooks + Troop", hooks_side)
        else:
            v.add("Blow Wall", wall_side)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SietchTabrUprisingDeferredSpaceAbility::Evaluate`` @0x4bbdf80.

        Option 0 is stored first; option 1 replaces it only when strictly
        greater, so a tie keeps the hooks (unlike V).
        """

        hooks = Summer()
        hooks.add("Water", p.water_value(1))
        hooks.add("Troop", p.troop_value(1, False))
        hooks.add("Maker Hooks", p.maker_hooks_value())
        stored = Answer(hooks.sum, ((0,),), "Sietch Tabr Maker Hooks")
        wall = Summer()
        wall.add("Water", p.water_value(1))
        wall.merge(p.blow_wall_value())
        if wall.sum > stored.value:
            stored = Answer(wall.sum, ((1,),), "Sietch Tabr Blow Wall")
        return stored


# -- Maker spaces (§1.4.18) --------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.Uprising.DesertSpaceDeferredAbility")
class DesertSpaceDeferredAbility(DeferredAbility):
    """``SpaceAbilities.Uprising.DesertSpaceDeferredAbility`` (abstract):
    option 0 = spice, option 1 = sandworms. Timing None; ``Cost`` @0x4bb7a90
    = ``NoCostAction``."""

    #: ``get_GetSpiceAmount`` (vslot 90) / ``get_GetSandwormAmount`` (vslot 91).
    spice_amount: ClassVar[int] = 0
    sandworm_amount: ClassVar[int] = 0

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertSpaceDeferredAbility::SelectionMode`` @0x4bb81d0: Explicit."""

        return SelectionMode.EXPLICIT

    def _spice_value(self, p: Profile) -> float:
        """``GetSpiceValue(GetSpiceAmount + Owner.SpiceGainReduction)``."""

        return p.spice_value(
            self.spice_amount + self.owner.int_attr("SpiceGainReduction", 0)
        )

    def _sandworm_value(self, p: Profile) -> float:
        """The worm option's value (only reached with hooks and deployable
        worms).

        Muad'Dib at a two-worm space while ``CurrentConflictInterest`` is
        strictly above the **lower** posture bound loses ``IntrigueValue``
        (``cmp eax, 2``; interest is read before the bounds, as in the
        binary).
        """

        worms = p.sandworm_value(self.sandworm_amount, False)
        if self.sandworm_amount == 2 and _leader_arch_id(p) == _MUAD_DIB:
            interest = p.current_conflict_interest().sum
            lower, _upper = p.conflict_posture_bounds()
            if interest > lower:
                worms = worms - p.intrigue_value()
        return worms

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DesertSpaceDeferredAbility::ValueForPlayer`` @0x4bb7e50.

        No generic space value (the separate ``SpaceAbility`` carries the
        bonus spice and the water cost). A tie goes to the worms (quirk).
        """

        v = Summer()
        spice = self._spice_value(p)
        worms = 0.0
        if p.ctx.me.maker_hooks and _can_deploy_sandworms(p):
            worms = self._sandworm_value(p)
        if spice > worms:
            v.add("Desert Space Spice", spice)
        else:
            v.add("Desert Space Sandworm", worms)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DesertSpaceDeferredAbility::Evaluate`` @0x4bb81e0.

        Spice is stored first; the worms replace it only when strictly
        greater (a tie keeps the spice, unlike V).
        """

        stored = Answer(self._spice_value(p), ((0,),), "Desert Space Spice")
        if p.ctx.me.maker_hooks and _can_deploy_sandworms(p):
            worms = self._sandworm_value(p)
            if worms > stored.value:
                stored = Answer(worms, ((1,),), "Desert Space SandWorms")
        return stored


@port("worm.canis.abilities.SpaceAbilities.Uprising.DeepDesertDeferredAbility")
class DeepDesertDeferredAbility(DesertSpaceDeferredAbility):
    """``DeepDesertDeferredAbility``: 4 spice or 2 sandworms (@0x4bb78b0,
    @0x4bb78c0)."""

    spice_amount: ClassVar[int] = 4
    sandworm_amount: ClassVar[int] = 2


@port("worm.canis.abilities.SpaceAbilities.Uprising.HaggaBasinUprisingDeferredAbility")
class HaggaBasinUprisingDeferredAbility(DesertSpaceDeferredAbility):
    """``HaggaBasinUprisingDeferredAbility``: 2 spice or 1 sandworm
    (@0x4bbc9d0, @0x4bbc9e0)."""

    spice_amount: ClassVar[int] = 2
    sandworm_amount: ClassVar[int] = 1


# -- Imperial Privilege (§1.4.9) ---------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.Uprising.ImperialPrivilegeAbility")
class ImperialPrivilegeAbility(DeferredAbility):
    """``Uprising.ImperialPrivilegeAbility``: may trash an Intrigue card to
    draw one (the space's ``DrawAbility``/``RecallAgentAbility`` are generic)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4d1aaa0 stores 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ImperialPrivilegeAbility::SelectionMode`` @0x4d1ab90: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d1ac40: ``HasIntrigueCardWith(CanBeTrashed)``.

        Judgement: no Uprising Intrigue card is Permanent, so any held
        Intrigue card can be trashed.
        """

        return bool(p.ctx.intrigue_cards)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialPrivilegeAbility::ValueForPlayer`` @0x4d1aee0.

        ``IntrigueValue`` when any held Intrigue card ``IsBadIntrigue``
        (b__0 @0x4d1b510), read through ``bad_intrigue_cards_in_hand``.
        """

        v = Summer()
        if p.bad_intrigue_cards_in_hand():
            v.add("Imperial Privilege Intrigue Value", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperialPrivilegeAbility::Evaluate`` @0x4d1b150 (board §1.4.9).

        The INTRIGUE targets are shuffled (``ListUtil.Shuffle``, here
        ``p.rng`` on a copy); every bad one is offered at ``IntrigueValue``
        (computed once, after the shuffle), so the first bad card in shuffled
        order sticks. No bad card: nothing stored, nothing trashed.
        """

        cards = list(_targets(request, Kind.INTRIGUE))
        p.rng.shuffle(cards)
        value = p.intrigue_value()
        bad = [c.ref for c in p.bad_intrigue_cards_in_hand()]
        stored: Answer | None = None
        for card in cards:
            if card.ref in bad and (stored is None or value > stored.value):
                stored = Answer(value, ((card.ref,),), f"Imperial Privilege {card.ref}")
        if stored is None:
            return Answer(0.0, None, "Imperial Privilege no bad intrigue")
        return stored


# ===========================================================================
# Playmat spy abilities of the Agent turn (engine-order §3.4)
# ===========================================================================


@port("worm.canis.abilities.ActivatedAbilities.Uprising.RecallSpyInfiltrateAbility")
class RecallSpyInfiltrateAbility(DeferredAbility):
    """``Uprising.RecallSpyInfiltrateAbility`` (Agent-turn state 240: which
    Spy to recall to infiltrate an occupied space). A playmat ability: the
    owner is whatever entity the window adapter attaches (never read)."""

    always_run_immediately: ClassVar[bool] = True  # @0x4d31b30

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``RecallSpyInfiltrateAbility::SelectionMode`` @0x4d31b20: Explicit."""

        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RecallSpyInfiltrateAbility::Evaluate`` @0x4d31d00.

        Always 100. With SPY targets: ``GetRecallSpy(spies) ?? spies[0]``.
        The "Intrigue Value" / "Remove spy" summer is only logged and is not
        computed here.
        """

        spies = _targets(request, Kind.SPY)
        if not spies:
            return Answer(100.0, (), "Infiltrate | 100")
        spy, _ = p.recall_spy(spies)
        if spy is None:
            spy = spies[0]
        return Answer(100.0, ((spy.ref,),), "Infiltrate | 100")


@port("worm.canis.abilities.ActivatedAbilities.Uprising.RecallSpyIntelligenceAbility")
class RecallSpyIntelligenceAbility(DeferredAbility):
    """``Uprising.RecallSpyIntelligenceAbility`` (Agent-turn state 260: recall
    an observing Spy to draw a card). Option 1 = recall, 0 = no; the optional
    second target info lists the Spies (its dependent targets)."""

    always_run_immediately: ClassVar[bool] = True  # @0x4d332e0

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``RecallSpyIntelligenceAbility::SelectionMode`` @0x4d332d0: Explicit."""

        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RecallSpyIntelligenceAbility::Evaluate`` @0x4d33400.

        ``CardDrawValueWithBuyGains - SpyValue`` (+100 with 3 or more Spies
        deployed). Positive: option 1 at that value, with ``GetRecallSpy``'s
        Spy (``?? spies[0]``) when there are 2+ target infos; else option 0
        at 1.0, so the forced prompt never falls back to random.
        """

        s = Summer()
        s.add("Card Draw + Buy Gains", p.card_draw_value_with_buy_gains())
        s.add("-Spy Value", -p.spy_value().sum)
        if _deployed_spies(p) >= 3:
            s.add(">= 3 Spies deployed", 100.0)
        if not s.sum > 0.0:
            return Answer(1.0, ((0,),), "Gather Intelligence | no")
        if len(request.infos) >= 2:
            # GetDependentTargets<WormSpy>(1): the second target info.
            spies = [e for e in request.infos[1].entities if e.kind is Kind.SPY]
            spy, _ = p.recall_spy(spies)
            if spy is None:
                spy = spies[0]  # the app indexes [0] too (throws when empty)
            return Answer(s.sum, ((1,), (spy.ref,)), "Gather Intelligence | yes")
        return Answer(s.sum, ((1,),), "Gather Intelligence | yes")


# ===========================================================================
# 2. Conflict rewards (board.md §2.4)
# ===========================================================================


@port(
    "worm.canis.abilities.ConflictAbilities.Uprising.GainAnyTwoInfluenceConflictAbility"
)
class GainAnyTwoInfluenceConflictAbility(ConflictAbility):
    """``ConflictAbilities.Uprising.GainAnyTwoInfluenceConflictAbility``
    (Propaganda 1st: +1 influence with two different factions)."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION  # ctor stores 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainAnyTwoInfluenceConflictAbility::ValueForPlayer`` @0x4b6ef00.

        ``FactionList`` values of ``GetGainInfluenceValue(f, 1)``, ordered
        descending, the top two summed (``Enumerable.Sum``: left to right).
        """

        values = [p.gain_influence_value(f, 1, -1, False).sum for f in FACTIONS]
        top = sorted(values, reverse=True)[:2]  # OrderByDescending.Take(2)
        v = Summer()
        v.add("GainAnyTwoInfluenceConflict", _dsum(top))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainAnyTwoInfluenceConflictAbility::Evaluate`` @0x4b6f3f0.

        TRACK targets shuffled (``p.rng``), each with its own summer
        (``Dictionary.TryAdd`` keeps insertion order), the two best by a
        stable descending sort, value ``Math.Max(0.5, sum)``. The House
        Hagal branch is unreachable.
        """

        tracks = list(_targets(request, Kind.TRACK))
        p.rng.shuffle(tracks)
        scored = [(p.gain_influence_value(t.ref, 1, -1, False), t) for t in tracks]
        top = sorted(scored, key=lambda st: st[0].sum, reverse=True)[:2]
        value = _math_max(0.5, _dsum([s.sum for s, _ in top]))
        refs = tuple(t.ref for _, t in top)
        return Answer(value, (refs,), "GainAnyTwoInfluenceConflict")


def place_reward_ability(conflict: Entity, place: int) -> ConflictAbility | None:
    """``conflict.Abilities.OfType<ConflictAbility>().FirstOrDefault(
    ConflictPlace == place)`` (``WormConflictPlayable::AbilityForPlacement``
    @0x4829c40; an ability without the attribute reads 0): the reward
    ``CombatPhase/<DetermineRewards>d__19`` runs for that place."""

    for ability in abilities_of(conflict):
        if isinstance(ability, ConflictAbility) and (ability.place or 0) == place:
            return ability
    return None


def granted_reward_abilities(conflict: Entity, place: int) -> tuple[Ability, ...]:
    """The custom abilities the ``place`` reward of ``conflict`` grants.

    What the place's ``ConflictAbility.BeginExecution`` hands its taker, in
    grant order:

    - ``GenericConflictAbility`` (every Uprising card): the reward
      archetype's ``CustomAbilityIDs`` (``<BeginExecution>d__3``), the same
      abilities ``catalog.conflict_reward_entities`` reaches;
    - ``EconomicSupremacyFirstAbility`` (Epic's Conflict III, no reward
      archetypes): the card's own ``EconomicSupremacySolariAbility`` and
      ``…SpiceAbility`` (spec/epic-goto11-promo-draft.md §2.4);
    - anything else (ES 2nd/3rd: plain gains): nothing.

    Static content only: the ``GainAnyInfluenceConflictAbility`` charge a
    played Pivotal Gambit appends at run time to the
    ``GenericConflictFirstAbility``'s own ``CustomAbilityIDs``
    (``epic_promo.pivotal_gambit_reward_ability``) is not listed.
    """

    reward = place_reward_ability(conflict, place)
    if isinstance(reward, GenericConflictAbility):
        return abilities_of(conflict_reward(conflict, place))
    if isinstance(reward, EconomicSupremacyFirstAbility):
        return reward.granted_abilities()
    return ()


# ===========================================================================
# 3. CHOAM contracts (board.md §3)
# ===========================================================================


class _HarvestContractAbility(ContractAbility):
    """Shared body of the two harvest contracts (not an app class: both app
    classes derive from ``ContractAbility`` directly).

    ``Cost`` (@0x4d59850 / @0x4d59b90) prepends ``HasGainedSpiceThisTurn.
    AtLeast(n)``; the engine owns that legality.
    """

    THRESHOLD: ClassVar[int] = 0  # literal of each ValueForPlayer and Cost

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``Harvest3ContractAbility::ValueForPlayer`` @0x4d598b0 /
        ``Harvest4ContractAbility::ValueForPlayer`` @0x4d59bf0.

        At a contract space whose ``Spice + BonusSpice`` (runtime) reaches
        the threshold: the base ``GetResourceValue`` (non-virtual call).
        Hagga Basin and Deep Desert have ``Spice`` 0, so only their bonus
        spice counts (quirk kept, board §5).
        """

        space = collect_first(with_entities, Kind.SPACE)
        if (
            space is not None
            and any(s.ref == space.ref for s in contract_spaces(p, self.owner))
            and space.int_attr("Spice") + _space_bonus_spice(p, space) >= self.THRESHOLD
        ):
            return ContractAbility.resource_value(self, p)
        return Summer()


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.Harvest3ContractAbility"
)
class Harvest3ContractAbility(_HarvestContractAbility):
    """``ContractAbilities.Harvest3ContractAbility`` (ContractBase_1)."""

    THRESHOLD: ClassVar[int] = 3


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.Harvest4ContractAbility"
)
class Harvest4ContractAbility(_HarvestContractAbility):
    """``ContractAbilities.Harvest4ContractAbility`` (ContractBase_3)."""

    THRESHOLD: ClassVar[int] = 4


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.RecallAgentContractAbility"
)
class RecallAgentContractAbility(ContractAbility):
    """``ContractAbilities.RecallAgentContractAbility`` (ContractBase_13):
    never runs by itself; waits in the post-action prompt."""

    always_run_immediately: ClassVar[bool] = False  # @0x4d5bdd0

    def resource_value(self, p: Profile) -> Summer:
        """``RecallAgentContractAbility::GetResourceValue`` @0x4d5c0b0."""

        v = super().resource_value(p)
        v.add("Recall Agent", p.recall_agent_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RecallAgentContractAbility::Evaluate`` @0x4d5c140.

        AGENT targets (``GetTargets`` filter b__0 UNTRACED: the request lists
        what the engine offers): ``GetRecallAgent(agents) ?? agents[0]`` at
        ``RecallAgentValue + 1.0``; no agent: "use" at 1.0 with nothing.
        """

        agents = _targets(request, Kind.AGENT)
        if agents:
            agent = p.recall_agent(list(agents))
            if agent is None:
                agent = agents[0]
            return Answer(
                p.recall_agent_value() + 1.0,  # literal 1.0
                ((agent.ref,),),
                f"Recall Agent Contract {agent.ref}",
            )
        return Answer(1.0, (), "Recall Agent Contract | nothing")  # literal 1.0


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.TSMFContractAbility"
)
class TSMFContractAbility(ContractAbility):
    """``ContractAbilities.TSMFContractAbility`` (ContractBase_20, completed
    by acquiring The Spice Must Flow)."""

    always_run_immediately: ClassVar[bool] = False  # @0x4d5d020

    def can_run_immediately(self, p: Profile) -> bool:
        """``TSMFContractAbility::CanRunImmediately`` @0x4d5cff0:
        ``cp == null or !cp.DeferredThresholdReached()``."""

        if _no_current_player(p):
            return True
        return not deferred_threshold_reached(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TSMFContractAbility::ValueForPlayer`` @0x4d5d0f0: the (virtual)
        ``GetResourceValue``, unconditionally."""

        return self.resource_value(p)

    def resource_value(self, p: Profile) -> Summer:
        """``TSMFContractAbility::GetResourceValue`` @0x4d5d110.

        The base already holds the archetype's ``Solari 3``; the literal 3
        Solari is added again (quirk kept, board §3.4).
        """

        v = super().resource_value(p)
        v.add("SG Influence", p.gain_influence_value("spacing_guild", 1, -1, False).sum)
        v.add("Contract Solari", p.solari_value(3))  # literal 3
        return v


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.BeneGesseritContractAbility"
)
class BeneGesseritContractAbility(ContractAbility):
    """``ContractAbilities.BeneGesseritContractAbility`` (ContractBase_10)."""

    always_run_immediately: ClassVar[bool] = False  # @0x4d54540

    def will_clear_undo(self, p: Profile) -> bool:
        """``BeneGesseritContractAbility::WillClearUndo`` @0x4d54610: the
        player's Bene Gesserit influence is exactly 3 (the +1 reaches the
        4-step VP)."""

        return p.ctx.me.influence.bene_gesserit == 3

    def can_run_immediately(self, p: Profile) -> bool:
        """``BeneGesseritContractAbility::CanRunImmediately`` @0x4d544d0:
        ``cp == null or cp.WillClearUndo or !cp.DeferredThresholdReached()``
        (the spec verifier's reading; the current player is the deciding
        seat)."""

        if _no_current_player(p):
            return True
        if self.will_clear_undo(p):
            return True
        return not deferred_threshold_reached(p)

    def resource_value(self, p: Profile) -> Summer:
        """``BeneGesseritContractAbility::GetResourceValue`` @0x4d54640."""

        v = super().resource_value(p)
        v.add("BG Influence", p.gain_influence_value("bene_gesserit", 1, -1, False).sum)
        return v


@port(
    "worm.canis.abilities.TriggeredAbilities.Uprising.ActivateTSMFContractTriggeredAbility"
)
class ActivateTSMFContractTriggeredAbility(TriggeredAbility):
    """``TriggeredAbilities.Uprising.ActivateTSMFContractTriggeredAbility``:
    makes the TSMF contract claimable on an ``AcquireImperium`` of The Spice
    Must Flow. No AI hook (it derives from ``TriggeredAbility`` directly, not
    from ``ActivateContractTriggeredAbility``)."""

    should_exhaust: ClassVar[bool] = False  # @0x4a8f350
