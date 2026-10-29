"""Rise of Ix's Imperium cards (``ImperiumArchetypes.RiseOfIx`` and the promo
``ImperiumArchetypes.Promo.BoundlessAmbition``): their ability classes.

Ports of the 46 app classes the Ix Imperium cards use and no other module
ports yet, read from the P6 Ix decompilation (assets ``ghidra/p6ix/<addr>.c``,
index ``ghidra/p6ix/targets-named.tsv``) and confirmed in the annotated
disassembly (``dump/asm/worm-canis.dll/<class>.asm``); ``docs/app-ai-plan.md``
§13.4 slice 6. Already ported elsewhere and reused as they are:
``FreighterAgentAbility`` / ``FreighterRevealAbility`` (``abilities/ix_board``),
``AcquireTechAgentAbility`` (``abilities/tech``), ``ImperialBasharRevealAbility``,
``InTheShadowsRevealAbility`` and ``CapturedMentatAgentAbility``
(``abilities/imperium_a``), ``ThufirHawatRevealAbility``,
``PowerPlayAgentAbility``, ``RevealGainIntrigueAbility``,
``TrashAgentAbility`` (``abilities/generic`` and the Uprising modules) and
``ControlTheSpiceAbility`` (Epic).

App class chains (``dump/worm-canis.dll.cs``) of the new classes:

- ``ActivatedAbilities.DeferredAbility`` <- ``Promo.BoundlessAmbitionRevealAbility``,
  ``RiseOfIx.AppropriateAbility``, ``BountyHunterAbility``,
  ``CourtIntrigueAbility``, ``DesertAmbushAbility``,
  ``BaseSet.EmbeddedAgentAbility``, ``EsmarTuekAbility``,
  ``GuildChiefAdministratorAbility``, ``ImperialBasharAgentAbility``,
  ``InTheShadowsAgentAbility``, ``IxGuildCompactAgentAbility``,
  ``IxianEngineerAbility``, ``LocalFenceAbility``,
  ``NegotiatedWithdrawalAbility``, ``SatelliteBanAbility``,
  ``SayyadinaAbility``, ``ShaiHuludAbility``, ``SpiceTraderAbility``,
  ``TreacheryTrashSelfAbility``, ``TruthsayerAbility``,
  ``WebOfPowerEmperorAbility``, ``WebOfPowerFremenAbility``,
  ``WeirdingWayAbility``;
- ``ActivatedAbilities.OptionalRetreatAbility`` <-
  ``BaseSet.SatelliteBanRevealAbility``; ``ActivatedAbilities.DrawAbility`` <-
  ``RiseOfIx.WebOfPowerSpacingGuildAbility``;
  ``ActivatedAbilities.GainAnyInfluenceAbility`` <-
  ``RiseOfIx.WebOfPowerRevealAbility``; ``ActivatedAbilities.AcquireAbility``
  <- ``RiseOfIx.ShaiHuludAcquireAbility``;
- ``PlayAbilities.RevealAbility`` <- ``RiseOfIx.FullScaleAssaultRevealAbility``,
  ``ImperialShockTrooperAbility``, ``InTheShadowsRevealPreviewAbility``,
  ``IxGuildCompactRevealAbility``, ``SayyadinaRevealAbility``,
  ``ShaiHuludRevealAbility``, ``TreacheryRevealAbility``;
- ``TriggeredAbilities.TriggeredAbility`` <- ``Promo.BoundlessAmbitionUnloadAbility``,
  ``Promo.BoundlessAmbitionUnloadOppAbility``, ``RiseOfIx.UnloadAbility``
  (CHOAM Delegate, Esmar Tuek, Ix-Guild Compact, Treachery, Water Peddler),
  ``FreighterFleetOppTrackPositive``, ``FreighterFleetOppTrackZero``,
  ``FreighterFleetUnloadAbility``, ``FullScaleAssaultAbility``,
  ``GuildAccordUnloadAbility``, ``InTheShadowsUnloadAbility``;
  ``TriggeredAbilities.AllianceAbility`` <- ``RiseOfIx.GuildAccordAllianceAbility``;
  ``TriggeredAbilities.BondAbility`` <- ``RiseOfIx.SayyadinaBondAbility``,
  ``ShaiHuludBondAbility``.

Request / answer encoding (``abilities/base``, as in ``generic.py`` and
``original_imperium.py``): the candidates of a prompt are ``request.infos[i]``
in the order the app's ``Targets`` yields its target infos (``entities`` for
entity targets, ``options`` for custom choices). ``Answer.response is None``
= nothing stored (the app's untouched choice, value 0); ``()`` = "use this
ability" with no sub-target; ``((ref, ...), ...)`` = the chosen refs / option
indices per target info. Units in the Conflict (Desert Ambush, Negotiated
Withdrawal) have no entity kind of ours: the window passes them to the
ability's constructor as ``ConflictUnit`` rows, and a target info names them
by ``ConflictUnit.ref`` (an entity ref or an option index). Each class
docstring says what its ``evaluate`` response encodes.

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    ability_for,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AcquireAbility,
    BondAbility,
    DeferredAbility,
    DrawAbility,
    GainAnyInfluenceAbility,
    RevealAbility,
    TriggeredAbility,
    _has_drawable_card,
    _targets,
    bg_played_pile_value,
    collect_first,
)
from dune_imperium.agents.app_ai.abilities.immortality import _all_imperium_cards
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    _Choice,
    _dmax,
    _has_faction,
    _in_play,
)
from dune_imperium.agents.app_ai.abilities.leaders import _has_trashable_card
from dune_imperium.agents.app_ai.abilities.original_imperium import (
    AllianceAbility,
    OptionalRetreatAbility,
    _in_alliance,
    _other_own_card_with,
)
from dune_imperium.agents.app_ai.abilities.tech import is_tech_tile
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    conflict_entity,
    is_board_space,
    space_entity,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.player import PlayerState

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "worm.canis.abilities.ActivatedAbilities.RiseOfIx."
_PA = "worm.canis.abilities.PlayAbilities.RiseOfIx."
_TA = "worm.canis.abilities.TriggeredAbilities.RiseOfIx."
_AA_BASE = "worm.canis.abilities.ActivatedAbilities.BaseSet."
_AA_PROMO = "worm.canis.abilities.ActivatedAbilities.Promo."
_TA_PROMO = "worm.canis.abilities.TriggeredAbilities.Promo."

#: The playmat custom ability Boundless Ambition's Reveal reads
#: (``PlayAbilities.Promo.BoundlessAmbitionCustomAbility``, ported below).
BOUNDLESS_AMBITION_CUSTOM: Final = (
    "worm.canis.abilities.PlayAbilities.Promo.BoundlessAmbitionCustomAbility"
)
#: The playmat (owner of the custom abilities ``SetupPhase`` adds), as the
#: windows spell it.
_PLAYMAT: Final = Entity(Kind.LEADER, "playmat")

# ``Factions`` enum: None 0, Emperor 1, SpacingGuild 2, BeneGesserit 3,
# Fremen 4; ours are the faction ids.
_EMPEROR = "emperor"
_SPACING_GUILD = "spacing_guild"
_BENE_GESSERIT = "bene_gesserit"
_FREMEN = "fremen"

#: ``AppropriateAbility::Evaluate``'s ``IntTargetResponse(0)``: the payment
#: option ``GetCustomChoiceFilter`` @0x4d99ff0 offers when the tile's
#: ``SpiceCost`` is at most the Solari (+ negotiators); 1 is the spice payment.
APPROPRIATE_PAY_SOLARI: Final = 0
APPROPRIATE_PAY_SPICE: Final = 1
#: ``ImperialBasharAgentAbility``'s "AOrB" options: 0 the troop, 1 the trash.
IMPERIAL_BASHAR_TROOP: Final = 0
IMPERIAL_BASHAR_TRASH: Final = 1
#: ``LocalFenceAbility``'s options: 0 = 2 spice for 5 Solari, 1 = 5 Solari for
#: 4 spice.
LOCAL_FENCE_SPICE_TO_SOLARI: Final = 0
LOCAL_FENCE_SOLARI_TO_SPICE: Final = 1


# ---------------------------------------------------------------------------
# Honest reads (AppContext rules) and small app helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConflictUnit:
    """One ``WormUnit`` target in the Conflict (a troop or a dreadnought).

    ``ref`` is how the window's target info names it (entity ref or option
    index), ``seat`` its ``OwningPlayer`` and ``strength`` its ``get_Strength``
    (vslot 35: a troop 2, a dreadnought 3).
    """

    ref: str | int
    seat: int
    strength: int


def _unit_targets(
    info: TargetInfo, units: Mapping[str | int, ConflictUnit]
) -> list[ConflictUnit]:
    """``ValidEntities<WormUnit>(info)``: the info's items that are units, in
    the info's order (entity refs first, then options)."""

    items: tuple[str | int, ...] = (*(e.ref for e in info.entities), *info.options)
    return [units[item] for item in items if item in units]


def _conflict_units(player: PlayerState) -> int:
    """``WormPlayer::get_ConflictUnits @0x4843c40`` /
    ``GetPlayerDeployed(P).children.Count``: every unit in the Conflict, Rise
    of Ix dreadnoughts included (``PlayerState.units_in_conflict``, as in
    ``profile/combat._conflict_units``)."""

    return player.units_in_conflict


def _garrison_units(player: PlayerState) -> int:
    """``WormPlayer::get_GarrisonUnits @0x4843dc0``: every garrison unit,
    dreadnoughts included (as ``profile/combat._garrison_units``)."""

    return (
        player.troops_garrison
        + player.commanders_garrison
        + player.dreadnoughts_garrison
    )


def _conflict_dreadnoughts(player: PlayerState) -> int:
    """``GetPlayerDeployed(P).children.OfType<WormDreadnought>().Count()`` /
    ``WormPlayer::get_ConflictDreadnoughts``."""

    return player.dreadnoughts_conflict


def _hand_count(p: Profile) -> int:
    """``WormPlayer::get_HandCount``."""

    return len(p.ctx.hand)


def _tech_tile_count(p: Profile) -> int:
    """``WormPlayer::get_TechTileCount`` @0x4844320: the seat's Tech tiles."""

    return len(p.ctx.me.tech_ids)


def _influence(p: Profile, faction: str) -> int:
    """``WormPlayer::GetFactionInfluence(F)`` for the seat itself."""

    return int(getattr(p.ctx.me.influence, faction))


def _current_conflict_vp(p: Profile) -> int:
    """``CurrentConflict(M)?.VictoryPoints() ?? 0``."""

    conflict_id = p.ctx.current_conflict_id
    if conflict_id is None:
        return 0
    return conflict_entity(conflict_id, p.ctx.choam).int_attr("VictoryPoints")


def _linq_max(values: Sequence[float]) -> float:
    """``Enumerable.Max<double>``: leading NaNs are skipped, the largest wins."""

    result = math.nan
    for value in values:
        if math.isnan(result) or value > result:
            result = value
    return result


def _double_compare(a: float, b: float) -> int:
    """``System.Double::CompareTo`` (``AIValueSummer.CompareTo`` = ``Sum``):
    NaN sorts below every number."""

    if a < b:
        return -1
    if a > b:
        return 1
    if a == b:
        return 0
    if math.isnan(a):
        return 0 if math.isnan(b) else -1
    return 1


def _cards(request: Request, index: int = 0) -> list[Entity]:
    """``GetTargets(...).OfType<WormImperiumPlayable>()`` of one target info."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is Kind.CARD]


def _tracks(request: Request, index: int) -> list[Entity]:
    """``ValidEntities<WormFactionTrack>(info)``."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is Kind.TRACK]


def _first_discard(p: Profile, request: Request) -> Entity | None:
    """``ChooseDiscardEvaluator.GetDiscardOrder(P, targets, false)
    .FirstOrDefault()`` over the first target info's cards."""

    order = p.discard_order(_cards(request), False)
    return order[0] if order else None


def _space_cost_blocked(
    p: Profile, v: Summer, space: Entity | None, attr: Attr, amount: int, name: str
) -> bool:
    """The shared "cost on top of the space's cost" test of the agent boxes:
    with a space among ``with_entities`` and ``CanAgentAbilityBePlayedWithSpace(
    space, attr, amount)`` false, a 0.0 term with the app's debug label."""

    if space is not None and not p.can_agent_ability_be_played_with_space(
        space, attr, amount
    ):
        v.add(f"{name} cost cannot be paid in addition to {space.ref} cost", 0.0)
        return True
    return False


# ---------------------------------------------------------------------------
# Triggered abilities without an AI hook (Unload, Freighter Fleet, Full-Scale
# Assault)
# ---------------------------------------------------------------------------


@port(_TA_PROMO + "BoundlessAmbitionUnloadAbility")
class BoundlessAmbitionUnloadAbility(TriggeredAbility):
    """``TriggeredAbilities.Promo.BoundlessAmbitionUnloadAbility`` (Boundless
    Ambition's Unload box). ``.ctor`` @0x4b0b1d0 stores no timing;
    ``get_ShouldExhaust`` @0x4b0b2f0 = false; ``IsValidFor``, ``Cost``
    (NoCostAction @0x4b0b300) and ``BeginExecution`` are engine-side: no AI
    hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA_PROMO + "BoundlessAmbitionUnloadOppAbility")
class BoundlessAmbitionUnloadOppAbility(TriggeredAbility):
    """``TriggeredAbilities.Promo.BoundlessAmbitionUnloadOppAbility``
    (Boundless Ambition's Unload, the opponent's side). ``.ctor`` @0x4b0c0c0
    stores no timing; ``get_ShouldExhaust`` @0x4b0c1e0 = false; ``Cost``
    (NoCostAction @0x4b0c1f0): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "UnloadAbility")
class UnloadAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.UnloadAbility`` (the Unload box of CHOAM
    Delegate, Esmar Tuek, Ix-Guild Compact, Treachery and Water Peddler).
    ``.ctor`` @0x4b09a40 stores no timing; ``get_ShouldExhaust`` @0x4b09b60 =
    false; ``IsValidFor``, ``Cost`` (NoCostAction @0x4b09b70), ``BeginExecution``
    and ``Undo`` are engine-side: no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "FreighterFleetOppTrackPositive")
class FreighterFleetOppTrackPositive(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.FreighterFleetOppTrackPositive`` (Freighter
    Fleet). ``.ctor`` @0x4ad4c50 stores no timing; ``get_ShouldExhaust``
    @0x4ad4d70 = false; ``Cost`` (NoCostAction @0x4ad4d80): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "FreighterFleetOppTrackZero")
class FreighterFleetOppTrackZero(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.FreighterFleetOppTrackZero`` (Freighter
    Fleet). ``.ctor`` @0x4ad5c20 stores no timing; ``get_ShouldExhaust``
    @0x4ad5d40 = false; ``Cost`` (NoCostAction @0x4ad5d50): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "FreighterFleetUnloadAbility")
class FreighterFleetUnloadAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.FreighterFleetUnloadAbility`` (Freighter
    Fleet's Unload box). ``.ctor`` @0x4ad6780 stores no timing;
    ``get_ShouldExhaust`` @0x4ad68a0 = false; ``Cost`` (NoCostAction
    @0x4ad68b0): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "GuildAccordUnloadAbility")
class GuildAccordUnloadAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.GuildAccordUnloadAbility`` (Guild Accord's
    Unload box). ``.ctor`` @0x4ad9030 stores no timing; ``get_ShouldExhaust``
    @0x4ad9150 = false; ``Cost`` (NoCostAction @0x4ad9160): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "InTheShadowsUnloadAbility")
class InTheShadowsUnloadAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.InTheShadowsUnloadAbility`` (In the
    Shadows' Unload box). ``.ctor`` @0x4afc9c0 stores no timing;
    ``get_ShouldExhaust`` @0x4afcae0 = false; ``Cost`` (NoCostAction
    @0x4afcaf0): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "FullScaleAssaultAbility")
class FullScaleAssaultAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.FullScaleAssaultAbility`` (Full-Scale
    Assault's dreadnought trigger). ``.ctor`` @0x4ad7670: timing Reveal;
    ``get_ShouldExhaust`` @0x4ad79a0 = false; ``GetDeployedDreadnoughts``
    @0x4ad7760, ``IsValidFor`` and ``Cost`` (NoCostAction @0x4ad79b0) are
    engine-side: no AI hook (its Reveal value is
    ``FullScaleAssaultRevealAbility``'s)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Triggered abilities with a value: Guild Accord, Sayyadina, Shai-Hulud
# ---------------------------------------------------------------------------


@port(_TA + "GuildAccordAllianceAbility")
class GuildAccordAllianceAbility(AllianceAbility):
    """``TriggeredAbilities.RiseOfIx.GuildAccordAllianceAbility`` (Guild
    Accord's Spacing Guild Alliance). ``.ctor`` @0x4ad84c0: timing Reveal;
    ``get_AllianceFaction`` @0x4ad85b0 = SpacingGuild (2); ``Cost`` =
    NoCostAction @0x4ad85c0."""

    timing: ClassVar[Timing] = Timing.REVEAL
    alliance_faction: ClassVar[str | None] = _SPACING_GUILD

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildAccordAllianceAbility::ValueForPlayer`` @0x4ad8710: in the
        ``AllianceFaction`` Alliance (vslot 88, ``InAlliance``),
        ``GetSpiceValue(1) * 3.0`` (f64 literal) as "Guild Accord Alliance
        Bonus"."""

        v = Summer()
        if _in_alliance(p, _SPACING_GUILD):
            v.add("Guild Accord Alliance Bonus", p.spice_value(1) * 3.0)
        return v


@port(_TA + "SayyadinaBondAbility")
class SayyadinaBondAbility(BondAbility):
    """``TriggeredAbilities.RiseOfIx.SayyadinaBondAbility`` (Sayyadina's Fremen
    bond). ``.ctor`` @0x4b05f60: timing Reveal; ``get_BondFaction``
    @0x4b06050 = Fremen (4); ``Cost`` = NoCostAction @0x4b06060. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SayyadinaBondAbility::ValueForPlayer`` @0x4b061d0.

        Another Fremen card of the hand or play area (``Hand.Concat(
        AllCardsInPlay)``, ``<ValueForPlayer>b__10_0`` @0x4b06480 skips the
        owner) -> ``GetPersuasionValue(3)`` as "Sayyadina Resources".
        """

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add("Sayyadina Resources", p.persuasion_value(3))
        return v


@port(_TA + "ShaiHuludBondAbility")
class ShaiHuludBondAbility(BondAbility):
    """``TriggeredAbilities.RiseOfIx.ShaiHuludBondAbility`` (Shai-Hulud's
    Fremen bond). ``.ctor`` @0x4b06e30: timing Reveal; ``get_BondFaction``
    @0x4b06f20 = Fremen (4); ``Cost`` = NoCostAction @0x4b06f30. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShaiHuludBondAbility::ValueForPlayer`` @0x4b070a0: another Fremen
        card in hand or in play (``b__10_0`` @0x4b07360) ->
        ``GetStrengthValue(1, false) * 5.0`` (f64 literal) as "Shai-Hulud
        Resources"."""

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add("Shai-Hulud Resources", p.strength_value(1, False) * 5.0)
        return v


# ---------------------------------------------------------------------------
# Reveal boxes
# ---------------------------------------------------------------------------


@port(_PA + "FullScaleAssaultRevealAbility")
class FullScaleAssaultRevealAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.FullScaleAssaultRevealAbility`` (Full-Scale
    Assault's Reveal box). ``.ctor`` @0x4be9e90: timing Reveal;
    ``GetRevealPreviewValue`` @0x4bea100 answers ``{Persuasion: 2, Strength:
    3 * dreadnoughts in the Conflict}``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FullScaleAssaultRevealAbility::ValueForPlayer`` @0x4bea270.

        ``RevealAbility.ValueForPlayer``, then ``GetStrengthValue(1, false) *
        (3 * n)`` (``lea eax,[r14+r14*2]``; ``mulsd``) as "Full Scale Assault
        Reveal", ``n`` the seat's dreadnoughts in the Conflict
        (``GetPlayerDeployed(P).children.OfType<WormDreadnought>().Count()``).
        """

        v = super().value_for_player(p, with_entities)
        n = _conflict_dreadnoughts(p.ctx.me)
        v.add("Full Scale Assault Reveal", p.strength_value(1, False) * float(3 * n))
        return v


def _has_agent_on_emperor_space(p: Profile) -> bool:
    """``ImperialShockTrooperAbility::hasAgentOnEmperorSpace`` @0x4bedd10.

    ``Board.Descendents.OfType<WormAgent>().Where(a.OwningPlayer == P)``
    (``b__0`` @0x4bee420) ``.Any(a.parent is WormSpace && ActionIcon == 4)``
    (``b__5_1`` @0x4bee3a0; ``AgentIcons.Emperor`` = 4): one of the seat's
    Agents stands on an Emperor-icon board space.
    """

    for space_id in p.ctx.me.agent_locations:
        if not is_board_space(space_id):
            continue
        if space_entity(space_id, p.ctx.board).attr("AgentIcon") == "Emperor":
            return True
    return False


@port(_PA + "ImperialShockTrooperAbility")
class ImperialShockTrooperAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.ImperialShockTrooperAbility`` (Imperial Shock
    Trooper's Reveal box; the card has no generic ``RevealAbility``).
    ``.ctor`` @0x4bedc30 (``RevealAbility.ctor``: timing Reveal);
    ``GetRevealPreviewValue`` @0x4bee1a0 answers ``{Persuasion: 1, Strength:
    2 + 3 with an Agent on an Emperor space}``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialShockTrooperAbility::ValueForPlayer`` @0x4bee030.

        ``RevealAbility.ValueForPlayer``, then with an Agent on an Emperor
        space (``_has_agent_on_emperor_space``) ``GetStrengthValue(1, false) *
        3.0`` (f64 literal) as "Imperial Shock Trooper Emperor Space Strength".
        """

        v = super().value_for_player(p, with_entities)
        if _has_agent_on_emperor_space(p):
            v.add(
                "Imperial Shock Trooper Emperor Space Strength",
                p.strength_value(1, False) * 3.0,
            )
        return v


@port(_PA + "InTheShadowsRevealPreviewAbility")
class InTheShadowsRevealPreviewAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.InTheShadowsRevealPreviewAbility`` (In the
    Shadows' Reveal box). ``.ctor`` @0x4beec60: timing Reveal;
    ``GetRevealPreviewValue`` @0x4beedd0 answers only ``{WillClearUndo: Bene
    Gesserit influence == 3}``. The AI value is the generic ``RevealAbility``
    one (its "Reveal Deferred" holds ``InTheShadowsRevealAbility``)."""


@port(_PA + "IxGuildCompactRevealAbility")
class IxGuildCompactRevealAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.IxGuildCompactRevealAbility`` (Ix-Guild
    Compact's Reveal box; the card has no generic ``RevealAbility``).
    ``.ctor`` @0x4beef70 (``RevealAbility.ctor``: timing Reveal)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxGuildCompactRevealAbility::ValueForPlayer`` @0x4bef150:
        ``RevealAbility.ValueForPlayer``, then ``NegotiateTechValue`` added to
        itself (``addsd xmm0, xmm0``) as "Ix Guild Compact 2 Negotiate
        Tech"."""

        v = super().value_for_player(p, with_entities)
        negotiate = p.negotiate_tech_value()
        v.add("Ix Guild Compact 2 Negotiate Tech", negotiate + negotiate)
        return v


@port(_PA + "SayyadinaRevealAbility")
class SayyadinaRevealAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.SayyadinaRevealAbility`` (Sayyadina's Reveal
    box). ``.ctor`` @0x4bf69b0: timing Reveal; ``GetRevealPreviewValue``
    @0x4bf6b20 answers ``{Persuasion: 3 with another own Fremen card in play
    or in hand, else 0}``. The AI value is the generic ``RevealAbility`` one."""


@port(_PA + "ShaiHuludRevealAbility")
class ShaiHuludRevealAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.ShaiHuludRevealAbility`` (Shai-Hulud's Reveal
    box). ``.ctor`` @0x4bf9110: timing Reveal; ``GetRevealPreviewValue``
    @0x4bf9280 answers ``{Strength: 5 with another own Fremen card in play or
    in hand, else 0}``. The AI value is the generic ``RevealAbility`` one."""


@port(_PA + "TreacheryRevealAbility")
class TreacheryRevealAbility(RevealAbility):
    """``PlayAbilities.RiseOfIx.TreacheryRevealAbility`` (Treachery's Reveal
    box). ``.ctor`` @0x4bfbc90 (``RevealAbility.ctor``: timing Reveal);
    ``BeginExecution`` / ``Undo`` are engine-side."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TreacheryRevealAbility::ValueForPlayer`` @0x4bfbe70:
        ``RevealAbility.ValueForPlayer``, then "Treachery 2 Troops" =
        ``GetTroopValue(2, false)`` and "Treachery Deploy" =
        ``DeployValue(owner)``."""

        v = super().value_for_player(p, with_entities)
        v.add("Treachery 2 Troops", p.troop_value(2, False))
        v.add("Treachery Deploy", p.deploy_value(self.owner))
        return v


# ---------------------------------------------------------------------------
# Boundless Ambition
# ---------------------------------------------------------------------------


@port(_AA_PROMO + "BoundlessAmbitionRevealAbility")
class BoundlessAmbitionRevealAbility(DeferredAbility):
    """``ActivatedAbilities.Promo.BoundlessAmbitionRevealAbility`` (Boundless
    Ambition's Reveal box). ``.ctor`` @0x4d8d6b0: timing Reveal;
    ``SelectionMode`` @0x4d8d7f0: Explicit; ``get_AlwaysRunImmediately``
    @0x4d8d800 = true; ``Cost`` = NoCostAction @0x4d8d7a0.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BoundlessAmbitionRevealAbility::SelectionMode`` @0x4d8d7f0:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BoundlessAmbitionRevealAbility::ValueForPlayer`` @0x4d8d8d0.

        The base (empty) summer plus the ``ValueForPlayer`` (vslot 64) of the
        playmat's ``BoundlessAmbitionCustomAbility``
        (``Playmat.Abilities.FirstOrDefault(b__11_0)``, ``b__11_0`` @0x4d8dd10:
        ``is BoundlessAmbitionCustomAbility``), added as a sub-summer.
        ``SetupPhase`` gives the playmat that ability in every Rise of Ix game
        (``IsSetEnabled(2)`` @0x4a42f96 .. 0x4a43225), so it is always found
        (``BoundlessAmbitionCustomAbility`` below).
        """

        v = Summer()
        custom = ability_for(BOUNDLESS_AMBITION_CUSTOM, _PLAYMAT)
        v.merge(custom.value_for_player(p, with_entities))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BoundlessAmbitionRevealAbility::Evaluate`` @0x4d8db40:
        ``UpdateSelectionTargets(100.0, src, null)`` (f64 literal; log
        "Boundless Ambition reveal | always play")."""

        return Answer(100.0, (), "Boundless Ambition reveal | always play")


# ---------------------------------------------------------------------------
# Agent boxes: Appropriate, Bounty Hunter, Court Intrigue
# ---------------------------------------------------------------------------


@port(_AA + "AppropriateAbility")
class AppropriateAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.AppropriateAbility`` (Appropriate's Agent
    box: acquire a Tech tile, paying Solari instead of spice). ``.ctor``
    @0x4d99b30: timing Agent; ``get_TechDiscount`` @0x4d99c30 = 0;
    ``get_IsCustomAbility`` @0x4d99c40 = false.

    ``evaluate`` responds ``((tile,), (APPROPRIATE_PAY_SOLARI,))``: the tile
    entity of ``request.infos[0]`` and the payment option of the second
    target info."""

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``get_TechDiscount`` @0x4d99c30 (vslot 89).
    tech_discount: ClassVar[int] = 0

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``AppropriateAbility::SelectionMode`` @0x4d99de0: Optional (0) when
        the owner's ``OwningPlayer`` is an AI (``get_IsAI``), else Explicit
        (3). The deciding seat is an AI seat."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d99d30: ``CanAcquireTechTile(TechDiscount, M,
        canUseSolari=true)`` then ``HasFactionInfluence.AtLeast(Emperor, 2)``."""

        return (
            bool(p.tech_acquire_targets(self.tech_discount, True))
            and _influence(p, _EMPEROR) >= 2
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``AppropriateAbility::ValueForPlayer`` @0x4d9a6d0: with Emperor
        influence at 2 or more (``cmp eax, 2; jl``), ``BuyTechValue(0, true)``
        as "Appropriate Buy Tech"."""

        v = Summer()
        if _influence(p, _EMPEROR) >= 2:
            v.add("Appropriate Buy Tech", p.buy_tech_value(0, True))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AppropriateAbility::Evaluate`` @0x4d9a840.

        For each tile of ``GetTargets().OfType<WormTechTilePlayable>()`` in
        order, ``UpdateSelectionResponses(tile.AcquireValue(P).Sum, src,
        [EntityListTargetResponse([tile]), IntTargetResponse(0)])`` (the int
        is the constant 0, ``xor esi, esi`` @0x4d9acf4): the first tile sticks,
        a later one only when strictly better.
        """

        choice = _Choice()
        for tile in request.infos[0].entities if request.infos else ():
            if not is_tech_tile(tile):
                continue
            value = p.tech_tile_acquire_value(tile).sum
            choice.update(
                value,
                ((tile.ref,), (APPROPRIATE_PAY_SOLARI,)),
                f"Appropriate Acquire Tech | acquire {tile.ref}",
            )
        return choice.answer("Appropriate Acquire Tech")


def _space_has_enemy_agent(p: Profile, space: Entity) -> bool:
    """``BountyHunterAbility::SpaceHasEnemyAgent`` @0x4d9cff0.

    ``Board.FindSpace(archID).children.OfType<WormAgent>()
    .Where(!IsDisabled)`` (``b__10_0`` @0x4d9d650) ``.Any(a.OwningPlayer !=
    P)`` (``b__1`` @0x4d9d670). Judgement (as ``SpaceAbility``'s infiltrate
    line in ``generic.py``): no Agent of a four-player game is disabled.
    """

    return any(seat != p.ctx.seat for seat in p.ctx.space_occupants(space.ref))


@port(_AA + "BountyHunterAbility")
class BountyHunterAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.BountyHunterAbility`` (Bounty Hunter's Agent
    box: 2 Solari at a space with an opponent's Agent). ``.ctor`` @0x4d9cd20:
    timing Agent; ``SelectionMode`` @0x4d9ce80: Explicit;
    ``get_AlwaysRunImmediately`` @0x4d9ce90 = true. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``, no sub-target)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BountyHunterAbility::SelectionMode`` @0x4d9ce80: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BountyHunterAbility::ValueForPlayer`` @0x4d9d380: the space among
        ``with_entities`` (``OfType<WormSpace>().FirstOrDefault()``) holding an
        opponent's Agent (``_space_has_enemy_agent``) -> ``GetSolariValue(2)``
        as "Bounty Hunter Solari"."""

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and _space_has_enemy_agent(p, space):
            v.add("Bounty Hunter Solari", p.solari_value(2))
        return v


@port(_AA + "CourtIntrigueAbility")
class CourtIntrigueAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.CourtIntrigueAbility`` (Court Intrigue's
    Agent box: discard an Intrigue card to draw one). ``.ctor`` @0x4da79d0:
    timing Agent; ``SelectionMode`` @0x4da7b70: Optional; ``Cost`` @0x4da7c60:
    ``HasIntrigueCard``; ``Targets`` @0x4da7ba0: "DiscardIntrigueCard", the
    held Intrigue cards.

    ``evaluate`` responds ``((intrigue,),)``: the chosen held Intrigue card."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CourtIntrigueAbility::SelectionMode`` @0x4da7b70: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4da7c60: ``HasIntrigueCard``: an Intrigue card held."""

        return bool(p.ctx.intrigue_cards)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CourtIntrigueAbility::ValueForPlayer`` @0x4da7da0: a bad Intrigue
        card held (``GetBadIntrigueCardsInHand.Any()``) -> ``CourtIntrigueValue``
        (vslot 262) as "Court Intrigue with Bad Intrigue"."""

        v = Summer()
        if p.bad_intrigue_cards_in_hand():
            v.add("Court Intrigue with Bad Intrigue", p.C.CourtIntrigueValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CourtIntrigueAbility::Evaluate`` @0x4da7f50.

        With a bad Intrigue card held, the list ``GetBadIntrigueCardsInHand`` is
        shuffled (``ListUtil.Shuffle``, the seat's RNG here) and its first card
        answered at ``CourtIntrigueValue`` (``UpdateSelectionTargets``); else
        the untouched choice.
        """

        bad = list(p.bad_intrigue_cards_in_hand())
        if not bad:
            return Answer(0.0, None, "Court Intrigue | no bad intrigue")
        p.rng.shuffle(bad)
        intrigue = bad[0]
        value = p.C.CourtIntrigueValue
        return Answer(value, ((intrigue.ref,),), f"Court Intrigue | {intrigue.ref}")


# ---------------------------------------------------------------------------
# Desert Ambush
# ---------------------------------------------------------------------------


@port(_AA + "DesertAmbushAbility")
class DesertAmbushAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.DesertAmbushAbility`` (Desert Ambush's
    Agent box: opponents' units in the Conflict retreat, one per troop
    deployed this turn). ``.ctor`` @0x4da9240: timing Agent; ``SelectionMode``
    @0x4da96e0: Optional; ``IsUnexhausted`` @0x4da96f0 = true; ``Cost``
    @0x4da9570: ``GetRemainingAmbushCount > 0`` (@0x4da93f0: the player's
    ``TroopsDeployedThisTurn``, doubled for a Ghola graft, minus the
    ``DesertAmbushUnitCount`` already used) then an opponent's troop or
    dreadnought in the Conflict (not modelled: our state has no
    ``TroopsDeployedThisTurn``; the engine owns legality).

    ``units`` are the valid ``WormUnit`` targets the window offers (the
    opponents' units in the Conflict); ``evaluate`` responds ``((ref, ...),)``:
    the refs of the units chosen in the first target info, at 0.5."""

    timing: ClassVar[Timing] = Timing.AGENT

    def __init__(self, owner: Entity, units: Sequence[ConflictUnit] = ()) -> None:
        super().__init__(owner)
        self.units: dict[str | int, ConflictUnit] = {u.ref: u for u in units}

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertAmbushAbility::SelectionMode`` @0x4da96e0: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DesertAmbushAbility::ValueForPlayer`` @0x4da9900.

        With 2 or more garrison units (``GarrisonUnits``, ``cmp eax, 2; jl``)
        and the lower ``ConflictPostureBounds`` at or above
        ``CurrentConflictInterest().Sum`` (``ucomisd lower, interest; jb``
        skips: taken when ``lower >= interest``, NaN skips),
        ``DesertAmbushValue`` (vslot 271) as "Desert Ambush Value"; then, when
        the opponents hold no unit in the Conflict
        (``Opponents.Sum(ConflictUnits)``, ``b__15_0`` @0x4daabb0, ``test eax,
        eax; jg`` skips), ``DesertAmbushNoOppositionPenalty`` (vslot 272) as
        "No Opposition".
        """

        v = Summer()
        if _garrison_units(p.ctx.me) >= 2:
            interest = p.current_conflict_interest().sum
            lower, _upper = p.conflict_posture_bounds()
            if lower >= interest:
                v.add("Desert Ambush Value", p.C.DesertAmbushValue)
        if sum(_conflict_units(o) for o in p.ctx.opponents) <= 0:
            v.add("No Opposition", p.C.DesertAmbushNoOppositionPenalty)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DesertAmbushAbility::Evaluate`` @0x4da9c40.

        ``n = NumberToSelect`` of the first target info, ``targets`` its valid
        units. ``order = GetExpectedCombatOrderWithStrength()``; the seat's own
        entry (``b__0`` @0x4daad80) gives ``estStrength`` (0 if missing) and is
        removed. ``trigger = Playmat.EndgameTriggerScore`` (default 10),
        ``conflictVP = CurrentConflict.VictoryPoints`` (0 without one). With
        ``opp = order.FirstOrDefault()``, while ``n > 0`` and ``opp`` is set:

        - when ``VP(opp) + conflictVP < trigger``, or ``>= trigger`` but
          ``VP(opp) + conflictVP < VP(P)`` (``jge`` @0x4daa269 keeps
          "Expected First"), ``opp`` becomes the first entry of ``order`` that
          ``b__4`` @0x4daadd0 accepts ("Can reduce opponent strength below
          current": ``estStrength > strength - Sum(its n strongest target
          units)``, ``setg``), else the first ``b__8`` @0x4dab0c0 accepts
          ("Can retreat all opponent units": no Agent left and ``ConflictUnits
          <= n``, ``setle``), else it stays ("Highest ExpectedStrength");
        - the ``n`` strongest target units of ``opp`` (``OrderByDescending(
          Strength)``, stable; ``Take(n)``) join the retreat list and ``n -=
          retreat.Count`` (the whole list's count, ``sub [r12+0x20], eax``
          @0x4daa4f6); ``opp`` leaves ``order`` and the next first entry
          follows.

        An empty retreat list leaves the choice untouched; else
        ``UpdateSelectionTargets(0.5, src, retreat ids)`` (f64 literal 0.5).
        """

        if not request.infos:
            return Answer(0.0, None, "Desert Ambush | no target info")
        info = request.infos[0]
        targets = _unit_targets(info, self.units)
        n = info.max_select
        order = list(p.expected_combat_order_with_strength())
        mine = next((entry for entry in order if entry[0] == p.ctx.seat), None)
        est_strength = 0
        if mine is not None:
            est_strength = mine[1]
            order.remove(mine)
        trigger = p.ctx.endgame_trigger_score
        conflict_vp = _current_conflict_vp(p)
        my_vp = p.ctx.vp(p.ctx.me)

        def strongest(seat: int, count: int) -> list[ConflictUnit]:
            own = [u for u in targets if u.seat == seat]
            own.sort(key=lambda u: u.strength, reverse=True)  # stable
            return own[: max(count, 0)]

        def can_reduce(entry: tuple[int, int]) -> bool:  # b__4
            removed = sum(u.strength for u in strongest(entry[0], n))
            return est_strength > entry[1] - removed

        def can_retreat_all(entry: tuple[int, int]) -> bool:  # b__8
            opponent = p.ctx.player(entry[0])
            return opponent.agents_available == 0 and _conflict_units(opponent) <= n

        retreat: list[ConflictUnit] = []
        paths: list[str] = []
        opp = order[0] if order else None
        while n > 0 and opp is not None:
            reason = "Highest ExpectedStrength"
            reach = p.ctx.vp(p.ctx.player(opp[0])) + conflict_vp
            if reach >= trigger and reach >= my_vp:
                reason = "Expected First"
            else:
                reducing = next((e for e in order if can_reduce(e)), None)
                if reducing is not None:
                    opp = reducing
                    reason = "Can reduce opponent strength below current"
                else:
                    clearing = next((e for e in order if can_retreat_all(e)), None)
                    if clearing is not None:
                        opp = clearing
                        reason = "Can retreat all opponent units"
            retreat.extend(strongest(opp[0], n))
            n -= len(retreat)
            paths.append(f"{opp[0]}: {reason} - selected ({len(retreat)}) units")
            order.remove(opp)
            opp = order[0] if order else None
        if not retreat:
            return Answer(0.0, None, "Desert Ambush | nothing to retreat")
        refs = tuple(u.ref for u in retreat)
        return Answer(
            0.5, (refs,), f"Desert Ambush | 0.5 | Retreating {refs} | {paths}"
        )


# ---------------------------------------------------------------------------
# Embedded Agent, Esmar Tuek
# ---------------------------------------------------------------------------


@port(_AA_BASE + "EmbeddedAgentAbility")
class EmbeddedAgentAbility(DeferredAbility):
    """``ActivatedAbilities.BaseSet.EmbeddedAgentAbility`` (Embedded Agent's
    Agent box: a Freighter step with another Bene Gesserit card in play).
    ``.ctor`` @0x4e67c60: timing Agent; ``SelectionMode`` @0x4e67dc0:
    Explicit; ``get_AlwaysRunImmediately`` @0x4e67dd0 = true.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``EmbeddedAgentAbility::SelectionMode`` @0x4e67dc0: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4e67de0: ``HasPlayedFactionCard(BeneGesserit, owner)``:
        another Bene Gesserit card in play (read as in
        ``BeneGesseritDrawAbility.meets_cost``)."""

        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        return any(_has_faction(c, "BeneGesserit") for c in others)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EmbeddedAgentAbility::ValueForPlayer`` @0x4e67f30: another Bene
        Gesserit card in play (``AllCardsInPlay.Except([owner]).Any(b__10_0)``,
        @0x4e68700) -> ``FreighterValue`` added to itself (``addsd xmm0,
        xmm0``) as "Embedded Agent 2 Freighter"."""

        v = Summer()
        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        if any(_has_faction(c, "BeneGesserit") for c in others):
            freighter = p.freighter_value()
            v.add("Embedded Agent 2 Freighter", freighter + freighter)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``EmbeddedAgentAbility::ValueInPileForOtherPlay`` @0x4e68200.

        The Bene Gesserit "played" pattern (``bg_played_pile_value``; no Bene
        Gesserit card in the play area, ``b__11_0`` @0x4e68760, and 2 or more
        Agents left, ``cmp eax, 2; jge``) with ``FreighterValue * 1.5`` (f64
        literal) as "Bene Gesserit Played".
        """

        def played() -> float:
            return p.freighter_value() * 1.5

        return bg_played_pile_value(p, pile, card, played, "Bene Gesserit Played")

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``EmbeddedAgentAbility::Evaluate`` @0x4e68570: 100.0 (f64 literal),
        no sub-target."""

        return Answer(100.0, (), "Embedded Agent | 100")


@port(_AA + "EsmarTuekAbility")
class EsmarTuekAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.EsmarTuekAbility`` (Esmar Tuek's Agent box:
    pay 1 spice for a Spacing Guild influence and a card). ``.ctor``
    @0x4db2de0: timing Agent; ``SelectionMode`` @0x4db2f40: Optional;
    ``Cost`` @0x4db2f50: ``HasResources.AtLeast(Spice, 1)``.

    ``evaluate`` responds ``()`` ("pay") at the summed value."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``EsmarTuekAbility::SelectionMode`` @0x4db2f40: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4db2f50: at least 1 spice."""

        return p.ctx.me.resources.spice >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EsmarTuekAbility::ValueForPlayer`` @0x4db30b0.

        Space among ``with_entities`` (``CollectFirst<WormSpace>``): when
        ``CanAgentAbilityBePlayedWithSpace(space, Spice, 1)`` is false only a
        0.0 term. Else "Esmar Tuek -1 Spice" = ``-GetSpiceValue(1)`` (the sign
        bit flipped, ``xorps``), "Esmar Tuek SG Influence" =
        ``GetGainInfluenceValue(SpacingGuild, 1, -1, false).Sum``, "Esmar Tuek
        Draw" = ``CardDrawValue`` and "Buy Gains Bonus" =
        ``GetBuyGains(PossiblePersuasionGain())``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if _space_cost_blocked(p, v, space, Attr.SPICE, 1, "Esmar Tuek Ability"):
            return v
        v.add("Esmar Tuek -1 Spice", -p.spice_value(1))
        v.add(
            "Esmar Tuek SG Influence",
            p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum,
        )
        v.add("Esmar Tuek Draw", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``EsmarTuekAbility::Evaluate`` @0x4db3490: ``GetSpiceValue(-1)``
        ("Pay 1 Spice") + the Spacing Guild influence ("SG Influence") +
        ``CardDrawValue`` ("Card Draw") + ``GetBuyGains(
        PossiblePersuasionGain())`` ("Buy Gains Bonus"); no sub-target."""

        v = Summer()
        v.add("Pay 1 Spice", p.spice_value(-1))
        v.add("SG Influence", p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum)
        v.add("Card Draw", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return Answer(v.sum, (), f"Esmar Tuek (Agent) | {v.sum}")


# ---------------------------------------------------------------------------
# Discard-for-something agent boxes: Guild Chief Administrator, In the
# Shadows, Ix-Guild Compact, Satellite Ban, Spice Trader, Truthsayer
# ---------------------------------------------------------------------------


@port(_AA + "GuildChiefAdministratorAbility")
class GuildChiefAdministratorAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.GuildChiefAdministratorAbility`` (Guild
    Chief Administrator's Agent box: discard a card to trash a card).
    ``.ctor`` @0x4dbc020: timing Agent; ``SelectionMode`` @0x4dbc110:
    Optional; ``Cost`` @0x4dbc1e0: ``HasImperiumCardInHand.Any``.

    ``evaluate`` responds ``((card,),)``: the card to discard among
    ``request.infos[0]``; ``evaluate_trash`` answers the trash prompt that
    follows (``((card,),)`` or ``((),)``)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildChiefAdministratorAbility::SelectionMode`` @0x4dbc110:
        Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dbc1e0: an Imperium card in hand."""

        return bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildChiefAdministratorAbility::ValueForPlayer`` @0x4dbc2e0: with 2
        or more cards in hand (``cmp eax, 2; jl``), "Guild Chief Administrator
        Discard" = ``DiscardValue``, "Guild Chief Administrator Trash" =
        ``TrashCardValue`` and "Trash Card Bonus" = ``TrashMod``."""

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Guild Chief Administrator Discard", p.discard_value())
            v.add("Guild Chief Administrator Trash", p.trash_card_value())
            v.add("Trash Card Bonus", p.trash_mod())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildChiefAdministratorAbility::Evaluate`` @0x4dbc4c0.

        ``discard = GetDiscardOrder(P, targets, false).FirstOrDefault()``; the
        trash pool is ``Hand.Concat(AllCardsInPlay).Concat(Discard)``
        (``WormPlayer`` +0xe8, +0xf8) and ``GetCardToTrash(pool, 1.0)``. With
        both found, "Discard" = ``DiscardValue`` + "Trash" = ``TrashCardValue``
        answered with the discard card; else the untouched choice.
        """

        discard = _first_discard(p, request)
        if discard is None:
            return Answer(0.0, None, "Guild Chief Administrator | nothing to discard")
        me = p.ctx.me
        pool = [
            card_entity(i, p.ctx.seat)
            for i in (*p.ctx.hand, *me.in_play, *me.discard_pile)
        ]
        trash, _value = p.card_to_trash(pool, 1.0)
        if trash is None:
            return Answer(0.0, None, "Guild Chief Administrator | nothing to trash")
        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("Trash", p.trash_card_value())
        return Answer(
            v.sum,
            ((discard.ref,),),
            f"Guild Chief Administrator | {v.sum} | discarding: {discard.ref} | "
            f"trashing: {trash.ref}",
        )

    def evaluate_trash(self, p: Profile, request: Request) -> Answer:
        """``GuildChiefAdministratorAbility::EvaluateTrash`` @0x4dbc950 (the
        trash prompt of ``BeginExecution``).

        ``GetCardToTrash(targets.OfType<WormImperiumPlayable>(), 1.0)``: the card
        at its trash value (``UpdateTargets``), else the empty target list at
        1.0 (f64 literal).
        """

        card, value = p.card_to_trash(_cards(request), 1.0)
        if card is not None:
            return Answer(value, ((card.ref,),), f"GCA trash | {card.ref}")
        return Answer(1.0, ((),), "GCA trash | nothing")


@port(_AA + "InTheShadowsAgentAbility")
class InTheShadowsAgentAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.InTheShadowsAgentAbility`` (In the Shadows'
    Agent box: with 2 Bene Gesserit influence, discard a card for an influence
    with another faction). ``.ctor`` @0x4dc64d0: timing Agent;
    ``SelectionMode`` @0x4dc6610: Optional; ``Cost`` @0x4dc6700:
    ``HasFactionInfluence.AtLeast(BeneGesserit, 2)``, then a card in hand,
    then ``CanGainInfluence([SpacingGuild, Emperor, Fremen])``.

    ``evaluate`` responds ``((card,), (track,))``: the card of
    ``request.infos[0]`` and the faction track of ``request.infos[1]``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``InTheShadowsAgentAbility::SelectionMode`` @0x4dc6610: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InTheShadowsAgentAbility::ValueForPlayer`` @0x4dc69f0.

        With Bene Gesserit influence at 2 or more and 2 or more cards in hand
        (both ``cmp eax, 2; jl``): "In The Shadows Discard" = ``DiscardValue``
        and "In The Shadows Influence" = ``[Fremen, Emperor, SpacingGuild]
        .Max(GetGainInfluenceValue(F, 1, -1, false).Sum)`` (``b__0``
        @0x4dc7920; ``Enumerable.Max``).
        """

        v = Summer()
        if _influence(p, _BENE_GESSERIT) >= 2 and _hand_count(p) >= 2:
            v.add("In The Shadows Discard", p.discard_value())
            values = [
                p.gain_influence_value(f, 1, -1, False).sum
                for f in (_FREMEN, _EMPEROR, _SPACING_GUILD)
            ]
            v.add("In The Shadows Influence", _linq_max(values))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``InTheShadowsAgentAbility::Evaluate`` @0x4dc6dc0.

        Needs two entity-list target infos (``Count < 2`` leaves the choice
        untouched). ``discard = GetDiscardOrder(P, cards of infos[0],
        false).FirstOrDefault()`` (none: untouched); then for each track of
        ``infos[1]`` "Discard" = ``DiscardValue`` + "Influence" =
        ``GetGainInfluenceValue(F, 1, -1, false).Sum``, answered ``[discard],
        [track]`` (``UpdateSelectionResponses``: the first sticks, a later one
        only when strictly better).
        """

        if len(request.infos) < 2:
            return Answer(0.0, None, "In The Shadows (Agent) | no target infos")
        discard = _first_discard(p, request)
        if discard is None:
            return Answer(0.0, None, "In The Shadows (Agent) | nothing to discard")
        discard_value = p.discard_value()
        choice = _Choice()
        for track in _tracks(request, 1):
            v = Summer()
            v.add("Discard", discard_value)
            v.add("Influence", p.gain_influence_value(track.ref, 1, -1, False).sum)
            choice.update(
                v.sum,
                ((discard.ref,), (track.ref,)),
                f"In The Shadows (Agent) | {track.ref} | {v.sum}",
            )
        return choice.answer("In The Shadows (Agent)")


@port(_AA + "IxGuildCompactAgentAbility")
class IxGuildCompactAgentAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.IxGuildCompactAgentAbility`` (Ix-Guild
    Compact's Agent box: discard 2 cards to commission a dreadnought).
    ``.ctor`` @0x4dcef00: timing Agent; ``SelectionMode`` @0x4dceff0:
    Optional; ``Cost`` @0x4dcf0e0: ``HasImperiumCardInHand.AtLeast(2)`` then a
    dreadnought in the supply.

    ``evaluate`` responds ``((card, card),)``: the two cards to discard among
    ``request.infos[0]`` (fewer when fewer are offered)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``IxGuildCompactAgentAbility::SelectionMode`` @0x4dceff0: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dcf0e0: 2 cards in hand, then
        ``HasUnitsInSupply<WormDreadnought>.Any``."""

        return _hand_count(p) >= 2 and p.ctx.me.dreadnoughts_supply > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxGuildCompactAgentAbility::ValueForPlayer`` @0x4dcf250.

        ``d = DiscardValue``, ``n = GetDreadnoughtValue(1, false)``; with 3 or
        more cards in hand (``cmp eax, 3; jl``) and ``d + d + n > 0.0``
        (``ucomisd; jbe`` skips), "Ix Guild Compact 2 Discard" = ``d + d`` and
        "Ix Guild Compact Dreadnought" = ``n``.
        """

        v = Summer()
        discard = p.discard_value()
        dreadnought = p.dreadnought_value(1, False)
        if _hand_count(p) >= 3:
            two = discard + discard
            if two + dreadnought > 0.0:
                v.add("Ix Guild Compact 2 Discard", two)
                v.add("Ix Guild Compact Dreadnought", dreadnought)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IxGuildCompactAgentAbility::Evaluate`` @0x4dcf430.

        In the Late arc (``GetGameArc() > 1``) the untouched choice. Else
        "Discard 2" = ``DiscardValue * 2`` (``addsd``) + "Dreadnought" =
        ``GetDreadnoughtValue(1, false)``, answered with the first two cards of
        ``GetDiscardOrder(P, targets, false)`` (``Take(2)``).
        """

        if p.game_arc() > 1:
            return Answer(0.0, None, "Ix Guild Compact | late")
        v = Summer()
        discard = p.discard_value()
        v.add("Discard 2", discard + discard)
        v.add("Dreadnought", p.dreadnought_value(1, False))
        chosen = p.discard_order(_cards(request), False)[:2]
        refs = tuple(c.ref for c in chosen)
        return Answer(
            v.sum, (refs,), f"Ix Guild Compact | {v.sum} | discarding: {refs}"
        )


def _discard_for(p: Profile, request: Request, v: Summer, name: str) -> Answer:
    """The shared ``Evaluate`` of Satellite Ban, Spice Trader and Truthsayer:
    ``GetDiscardOrder(P, targets, false).FirstOrDefault()`` answered at
    ``v.Sum`` (``UpdateSelectionTargets``), else the untouched choice."""

    discard = _first_discard(p, request)
    if discard is None:
        return Answer(0.0, None, f"{name} | nothing to discard")
    return Answer(
        v.sum, ((discard.ref,),), f"{name} | {v.sum} | discarding: {discard.ref}"
    )


@port(_AA + "SatelliteBanAbility")
class SatelliteBanAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.SatelliteBanAbility`` (Satellite Ban's Agent
    box: discard a card for a spice and a water). ``.ctor`` @0x4dd9000: timing
    Agent; ``SelectionMode`` @0x4dd90f0: Optional; ``Cost`` @0x4dd91c0:
    ``HasImperiumCardInHand.Any``.

    ``evaluate`` responds ``((card,),)``: the card to discard."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SatelliteBanAbility::SelectionMode`` @0x4dd90f0: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dd91c0: an Imperium card in hand."""

        return bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SatelliteBanAbility::ValueForPlayer`` @0x4dd92c0: with 2 or more
        cards in hand, "Satellite Ban Discard" = ``DiscardValue``, "Satellite
        Ban Spice" = ``GetSpiceValue(1)`` and "Satellite Ban Water" =
        ``GetWaterValue(1)``."""

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Satellite Ban Discard", p.discard_value())
            v.add("Satellite Ban Spice", p.spice_value(1))
            v.add("Satellite Ban Water", p.water_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SatelliteBanAbility::Evaluate`` @0x4dd94b0: "Discard" =
        ``DiscardValue`` + "Spice" = ``GetSpiceValue(1)`` + "Water" =
        ``GetWaterValue(1)`` (``_discard_for``)."""

        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("Spice", p.spice_value(1))
        v.add("Water", p.water_value(1))
        return _discard_for(p, request, v, "Satellite Ban (Agent)")


@port(_AA + "SpiceTraderAbility")
class SpiceTraderAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.SpiceTraderAbility`` (Spice Trader's Agent
    box: with 2 Fremen influence, discard a card for 2 spice). ``.ctor``
    @0x4de4080: timing Agent; ``SelectionMode`` @0x4de4170: Optional; ``Cost``
    @0x4de4240: ``HasFactionInfluence.AtLeast(Fremen, 2)`` then a card in hand.

    ``evaluate`` responds ``((card,),)``: the card to discard."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SpiceTraderAbility::SelectionMode`` @0x4de4170: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4de4240: Fremen influence 2, then a card in hand."""

        return _influence(p, _FREMEN) >= 2 and bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceTraderAbility::ValueForPlayer`` @0x4de4390: with Fremen
        influence at 2 or more and 2 or more cards in hand, "Spice Trader
        Discard" = ``DiscardValue`` and "Spice Trader 2 Spice" =
        ``GetSpiceValue(1)`` added to itself (``addsd``)."""

        v = Summer()
        if _influence(p, _FREMEN) >= 2 and _hand_count(p) >= 2:
            v.add("Spice Trader Discard", p.discard_value())
            spice = p.spice_value(1)
            v.add("Spice Trader 2 Spice", spice + spice)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpiceTraderAbility::Evaluate`` @0x4de4550: "Discard" =
        ``DiscardValue`` + "2 Spice" = ``GetSpiceValue(2)``
        (``_discard_for``)."""

        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("2 Spice", p.spice_value(2))
        return _discard_for(p, request, v, "Spice Trader")


@port(_AA + "TruthsayerAbility")
class TruthsayerAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.TruthsayerAbility`` (Truthsayer's Agent
    box: discard a card to draw a card). ``.ctor`` @0x4def7b0: timing Agent;
    ``SelectionMode`` @0x4def910: Optional; ``Cost`` @0x4def9e0:
    ``HasImperiumCardInHand.Any``.

    ``evaluate`` responds ``((card,),)``: the card to discard."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TruthsayerAbility::SelectionMode`` @0x4def910: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4def9e0: an Imperium card in hand."""

        return bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TruthsayerAbility::ValueForPlayer`` @0x4defae0: with 2 or more
        cards in hand, "Truthsayer Discard" = ``DiscardValue``, "Truthsayer
        Draw" = ``CardDrawValue`` and "Buy Gains Bonus" =
        ``GetBuyGains(PossiblePersuasionGain())``."""

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Truthsayer Discard", p.discard_value())
            v.add("Truthsayer Draw", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TruthsayerAbility::Evaluate`` @0x4defcd0: "Discard" =
        ``DiscardValue`` + "Draw" = ``CardDrawValue`` + "Buy Gains Bonus"
        (``_discard_for``)."""

        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("Draw", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return _discard_for(p, request, v, "Truthsayer")


# ---------------------------------------------------------------------------
# Imperial Bashar's Agent box
# ---------------------------------------------------------------------------


@port(_AA + "ImperialBasharAgentAbility")
class ImperialBasharAgentAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.ImperialBasharAgentAbility`` (Imperial
    Bashar's Agent box: a troop OR trash a card, the "AOrB" prompt).
    ``.ctor`` @0x4dc3a60: timing Agent; ``SelectionMode`` @0x4dc3ba0:
    Explicit; ``Cost`` @0x4dc3c70: ``HasTrashableCard`` or a troop in the
    supply.

    ``request.infos[0]`` is the choose-one prompt (options 0 troop, 1 trash),
    ``request.infos[1]`` the cards option 1 offers (the
    ``CustomChoiceResultTargetInformation`` result of choice 1).
    ``evaluate`` responds ``((0,),)``, ``((1,), (card,))`` or ``((1,),)``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ImperialBasharAgentAbility::SelectionMode`` @0x4dc3ba0: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dc3c70: ``HasTrashableCard`` or
        ``HasUnitsInSupply<WormTroop>.Any`` (``CostAction::Or``)."""

        return _has_trashable_card(p) or p.ctx.me.troops_supply > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialBasharAgentAbility::ValueForPlayer`` @0x4dc3e00:
        ``Math.Max(GetTroopValue(1, false), TrashCardValue + TrashMod)`` as
        "Imperial Bashar: Troop or Trash"."""

        v = Summer()
        troop = p.troop_value(1, False)
        trash = p.trash_card_value() + p.trash_mod()
        v.add("Imperial Bashar: Troop or Trash", _dmax(troop, trash))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``ImperialBasharAgentAbility::SpecificAcquireValue`` @0x4dc3fe0: the
        cards of ``AllImperiumCards`` with ``Strength > 0`` (``b__12_0``
        @0x4dc4d00, ``test eax, eax; setg``) times ``ImperialBasharSwordValue``
        (vslot 273) as "Imperial Bashar"."""

        v = Summer()
        swords = sum(1 for c in _all_imperium_cards(p) if c.int_attr("Strength") > 0)
        v.add("Imperial Bashar", p.C.ImperialBasharSwordValue * float(swords))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperialBasharAgentAbility::Evaluate`` @0x4dc41a0.

        Option 0 at ``GetTroopValue(1, false)`` first
        (``UpdateSelectionResponses``). Then, when the choose-one info carries
        the option-1 result (``b__13_0`` @0x4dc4da0 finds the
        ``CustomChoiceResultTargetInformation``, its result map not empty),
        ``GetCardToTrash(cards, 1.0)``; a found card is answered ``[1],
        [card]`` at its trash value + ``TrashCardValue`` (strictly greater
        replaces). Last, while the stored value is not above 0.0 (``ucomisd
        0.0, value; jb`` skips), option 1 alone at 0.5 (f64 literal).
        """

        choice = _Choice()
        troop = p.troop_value(1, False)
        choice.update(
            troop, ((IMPERIAL_BASHAR_TROOP,),), f"Imperial Bashar | Troop | {troop}"
        )
        if len(request.infos) < 2:
            return choice.answer("Imperial Bashar")
        card, value = p.card_to_trash(_cards(request, 1), 1.0)
        trash_value = p.trash_card_value()
        if card is not None:
            total = value + trash_value
            choice.update(
                total,
                ((IMPERIAL_BASHAR_TRASH,), (card.ref,)),
                f"Imperial Bashar | {total} | trashing: {card.ref}",
            )
        if choice.value <= 0.0:  # not above 0.0 and not NaN
            choice.update(0.5, ((IMPERIAL_BASHAR_TRASH,),), "Imperial Bashar | 0.5")
        return choice.answer("Imperial Bashar")


# ---------------------------------------------------------------------------
# Ixian Engineer, Local Fence
# ---------------------------------------------------------------------------


@port(_AA + "IxianEngineerAbility")
class IxianEngineerAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.IxianEngineerAbility`` (Ixian Engineer's
    Reveal box: with 3 Tech tiles, trash this card for a victory point).
    ``.ctor`` @0x4dd0a00: timing Reveal; ``SelectionMode`` @0x4dd0af0:
    Optional; ``Cost`` @0x4dd0b00: ``HasTechTiles.AtLeast(3)``.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``IxianEngineerAbility::SelectionMode`` @0x4dd0af0: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dd0b00: 3 Tech tiles."""

        return _tech_tile_count(p) >= 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxianEngineerAbility::ValueForPlayer`` @0x4dd0c10: with 3 or more
        Tech tiles (``cmp eax, 3; jl``), ``GetVictoryPointValue(1)`` as
        "Ixian Engineer VP"."""

        v = Summer()
        if _tech_tile_count(p) >= 3:
            v.add("Ixian Engineer VP", p.victory_point_value(1))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``IxianEngineerAbility::SpecificAcquireValue`` @0x4dd0d80: with 2 or
        more Tech tiles (``cmp eax, 2; jl``), ``IxianEngineerValue`` (vslot
        274) as "Ixian Engineer"."""

        v = Summer()
        if _tech_tile_count(p) >= 2:
            v.add("Ixian Engineer", p.C.IxianEngineerValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IxianEngineerAbility::Evaluate`` @0x4dd0e30: 100.0 (f64 literal),
        no sub-target."""

        return Answer(100.0, (), "Ixian Engineer | 100")


@port(_AA + "LocalFenceAbility")
class LocalFenceAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.LocalFenceAbility`` (Local Fence's Agent
    box: 2 spice for 5 Solari OR 5 Solari for 4 spice). ``.ctor``
    @0x4dd3cd0: timing Agent; ``SelectionMode`` @0x4dd3e10: Optional;
    ``Cost`` @0x4dd3e20: at least 2 spice or at least 5 Solari.

    ``evaluate`` responds ``((LOCAL_FENCE_SPICE_TO_SOLARI,),)`` or
    ``((LOCAL_FENCE_SOLARI_TO_SPICE,),)`` (``IntTargetResponse``)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``LocalFenceAbility::SelectionMode`` @0x4dd3e10: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dd3e20: ``AtLeast(Spice, 2).Or(AtLeast(Solari, 5))``."""

        me = p.ctx.me
        return me.resources.spice >= 2 or me.resources.solari >= 5

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LocalFenceAbility::ValueForPlayer`` @0x4dd40a0.

        ``s = GetSpiceValue(1)``; the spice trade is open with 2 spice, the
        Solari trade with 5 Solari (``setge``). With a space among
        ``with_entities``, each trade whose cost the space leaves unpayable
        (``CanAgentAbilityBePlayedWithSpace(space, Spice, 2)`` /
        ``(space, Solari, 5)``) adds a 0.0 term and closes. With neither open,
        nothing more. Else ``a = GetSolariValue(5) - (s + s)`` for the open
        spice trade, ``b = s * 4.0 + GetSolariValue(-5)`` (f64 literal) for
        the open Solari trade (0.0 otherwise), and ``Math.Max(0.0,
        Math.Max(a, b))`` as "Local Fence Resource".
        """

        v = Summer()
        me = p.ctx.me
        spice_one = p.spice_value(1)
        spice_open = me.resources.spice >= 2
        solari_open = me.resources.solari >= 5
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None:
            if _space_cost_blocked(
                p, v, space, Attr.SPICE, 2, "Local Fence Spice Ability"
            ):
                spice_open = False
            if _space_cost_blocked(
                p, v, space, Attr.SOLARI, 5, "Local Fence Solari Ability"
            ):
                solari_open = False
        if not (spice_open or solari_open):
            return v
        a = 0.0
        b = 0.0
        if spice_open:
            a = p.solari_value(5) - (spice_one + spice_one)
        if solari_open:
            b = spice_one * 4.0 + p.solari_value(-5)
        v.add("Local Fence Resource", _dmax(0.0, _dmax(a, b)))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LocalFenceAbility::Evaluate`` @0x4dd4590.

        Option 0 at "Pay 2 Spice" = ``GetSpiceValue(-2)`` + "Gain 5 Solari" =
        ``GetSolariValue(5)``, then option 1 at "Pay 5 Solari" =
        ``GetSolariValue(-5)`` + "Gain 4 Spice" = ``GetSpiceValue(4)``
        (``UpdateSelectionResponses``: option 1 replaces only when strictly
        better). Neither option is checked against the seat's resources.
        """

        choice = _Choice()
        first = Summer()
        first.add("Pay 2 Spice", p.spice_value(-2))
        first.add("Gain 5 Solari", p.solari_value(5))
        choice.update(
            first.sum,
            ((LOCAL_FENCE_SPICE_TO_SOLARI,),),
            f"Local Fence | 2 spice -> 5 solari | {first.sum}",
        )
        second = Summer()
        second.add("Pay 5 Solari", p.solari_value(-5))
        second.add("Gain 4 Spice", p.spice_value(4))
        choice.update(
            second.sum,
            ((LOCAL_FENCE_SOLARI_TO_SPICE,),),
            f"Local Fence | 5 solari -> 4 spice | {second.sum}",
        )
        return choice.answer("Local Fence")


# ---------------------------------------------------------------------------
# Negotiated Withdrawal
# ---------------------------------------------------------------------------


@port(_AA + "NegotiatedWithdrawalAbility")
class NegotiatedWithdrawalAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.NegotiatedWithdrawalAbility`` (Negotiated
    Withdrawal's Reveal box: retreat 3 units for an influence). ``.ctor``
    @0x4dd6450: timing Reveal; ``SelectionMode`` @0x4dd67b0: Optional;
    ``Cost`` @0x4dd6620: ``ConflictTroops + ConflictDreadnoughts >= 3``
    (``setge``) then ``CanGainInfluence``; ``Targets`` (``<Targets>d__6``
    @0x4dd8651..) yields the faction prompt
    (``MakeGainAnyFactionInfluenceTargeting``) first, then the retreat prompt
    (the deployed troops and units, ``NumberToSelect`` 3).

    ``units`` are the seat's units the window knows (``ConflictUnit`` rows).
    ``evaluate`` responds ``((track,), (ref, ...))``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def __init__(self, owner: Entity, units: Sequence[ConflictUnit] = ()) -> None:
        super().__init__(owner)
        self.units: dict[str | int, ConflictUnit] = {u.ref: u for u in units}

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``NegotiatedWithdrawalAbility::SelectionMode`` @0x4dd67b0: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``NegotiatedWithdrawalAbility::ValueForPlayer`` @0x4dd68c0: with
        ``GarrisonUnits + ConflictUnits >= 2`` (``cmp eax, 2; jl``),
        ``NegotiatedWithdrawalRetreatValue`` (vslot 269) as "Negotiated
        Withdrawal Retreat"."""

        v = Summer()
        me = p.ctx.me
        if _garrison_units(me) + _conflict_units(me) >= 2:
            v.add("Negotiated Withdrawal Retreat", p.C.NegotiatedWithdrawalRetreatValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``NegotiatedWithdrawalAbility::Evaluate`` @0x4dd6a50.

        Needs two entity-list target infos (``Count < 2``: untouched). Both
        the units and the faction tracks are read from the **first** info
        (``List.get_Item(0)`` twice, ``xor esi, esi`` @0x4dd6cce and
        @0x4dd6fff): ``units = ValidEntities<WormUnit>(infos[0])
        .OrderBy(Strength)`` (``b__12_0``, stable), ``retreat = units.Take(3)``
        and ``s = retreat.Sum(Strength)`` (``b__12_1``). ``r0 =
        EstimatedConflictRank(0)``, ``r1 = EstimatedConflictRank(-s)`` (4 when
        unranked); ``r0 <= 2`` with ``r0 != r1`` leaves the choice untouched
        (``jg`` / ``jne`` @0x4dd6fea). Then for each track of
        ``ValidEntities<WormFactionTrack>(infos[0])``,
        ``GetGainInfluenceValue(F, 1, -1, false).Sum`` answered ``[track],
        [retreat ids]`` (first sticks, then strictly greater). With the app's
        own target order (factions first) the retreat list is always empty.
        """

        if len(request.infos) < 2:
            return Answer(0.0, None, "Negotiated Withdrawal | no target infos")
        first = request.infos[0]
        units = _unit_targets(first, self.units)
        units.sort(key=lambda u: u.strength)  # stable OrderBy
        retreat = units[:3]
        strength = sum(u.strength for u in retreat)
        rank_now = p.estimated_conflict_rank(0)
        rank_after = p.estimated_conflict_rank(-strength)
        r0 = 4 if rank_now is None else rank_now
        r1 = 4 if rank_after is None else rank_after
        if r0 <= 2 and r0 != r1:
            return Answer(0.0, None, "Negotiated Withdrawal | keep the rank")
        refs = tuple(u.ref for u in retreat)
        choice = _Choice()
        for track in _tracks(request, 0):
            value = p.gain_influence_value(track.ref, 1, -1, False).sum
            choice.update(
                value,
                ((track.ref,), refs),
                f"Negotiated Withdrawal | {refs} | {track.ref}",
            )
        return choice.answer("Negotiated Withdrawal")


# ---------------------------------------------------------------------------
# Satellite Ban's Reveal, Sayyadina, Shai-Hulud
# ---------------------------------------------------------------------------


@port(_AA_BASE + "SatelliteBanRevealAbility")
class SatelliteBanRevealAbility(OptionalRetreatAbility):
    """``ActivatedAbilities.BaseSet.SatelliteBanRevealAbility`` (Satellite Ban's
    Reveal: retreat up to 2 troops). ``.ctor`` @0x4e68c80: timing Reveal;
    ``get_MaxRetreat`` @0x4e68d90 = 2. ``evaluate``:
    ``OptionalRetreatAbility``'s."""

    timing: ClassVar[Timing] = Timing.REVEAL
    MAX_RETREAT: ClassVar[int] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SatelliteBanRevealAbility::ValueForPlayer`` @0x4e68da0:
        ``Math.Min(units in the Conflict * 0.5, 1.0)`` (f64 literals;
        ``GetPlayerDeployed(P).children.Count``) as "Satellite Ban Troop
        Retreat Bonus"."""

        v = Summer()
        units = _conflict_units(p.ctx.me)
        v.add("Satellite Ban Troop Retreat Bonus", min(units * 0.5, 1.0))
        return v


@port(_AA + "SayyadinaAbility")
class SayyadinaAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.SayyadinaAbility`` (Sayyadina's Agent box:
    pay 3 water for a victory point). ``.ctor`` @0x4dda8d0: timing Agent;
    ``SelectionMode`` @0x4dda9c0: Optional; ``Cost`` @0x4dda9d0:
    ``HasResources.AtLeast(Water, 3)``.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SayyadinaAbility::SelectionMode`` @0x4dda9c0: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dda9d0: at least 3 water."""

        return p.ctx.me.resources.water >= 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SayyadinaAbility::ValueForPlayer`` @0x4ddab30.

        With 3 or more water (``WormEntityExtensions.Water(P)``, ``cmp eax, 3;
        jl``): "Sayyadina -3 Water" = ``GetWaterValue(1) * 3.0`` (f64 literal;
        added as compiled, positive, despite its label) and "Sayyadina VP" =
        ``GetVictoryPointValue(1)``.
        """

        v = Summer()
        if p.ctx.me.resources.water >= 3:
            v.add("Sayyadina -3 Water", p.water_value(1) * 3.0)
            v.add("Sayyadina VP", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SayyadinaAbility::Evaluate`` @0x4ddacf0: 100.0 (f64 literal), no
        sub-target."""

        return Answer(100.0, (), "Sayyadina | 100")


@port(_AA + "ShaiHuludAbility")
class ShaiHuludAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.ShaiHuludAbility`` (Shai-Hulud's Agent box:
    trash a card for 2 troops). ``.ctor`` @0x4ddbd50: timing Agent;
    ``SelectionMode`` @0x4ddbe40: Optional; ``Cost`` @0x4ddbee0:
    ``HasTrashableCard``; ``GetUnusualSelections`` @0x4ddbfe0 (2 supply
    troops) is interface plumbing.

    ``evaluate`` responds ``((card,),)``: the card to trash among
    ``request.infos[0]``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ShaiHuludAbility::SelectionMode`` @0x4ddbe40: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShaiHuludAbility::ValueForPlayer`` @0x4ddc1b0: "Shai-Hulud Trash" =
        ``TrashCardValue``, "Trash Card Bonus" = ``TrashMod`` and "Shai-Hulud 2
        Troops" = ``GetTroopValue(1, false)`` added to itself (``addsd``)."""

        v = Summer()
        v.add("Shai-Hulud Trash", p.trash_card_value())
        v.add("Trash Card Bonus", p.trash_mod())
        troop = p.troop_value(1, False)
        v.add("Shai-Hulud 2 Troops", troop + troop)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShaiHuludAbility::Evaluate`` @0x4ddc380.

        ``(card, t) = GetCardToTrash(targets, 1.0)``; "Trash Value" = ``t``.
        Without a card the least valuable target is taken instead
        (``OrderBy(c => c.AcquireValue(P)).First()``, ``b__0`` @0x4ddc750;
        ``AIValueSummer.CompareTo`` = ``Sum``, stable). The answer names that
        card at ``t`` (``UpdateSelectionTargets``); with no target at all the
        app's ``First()`` would throw, ours leaves the choice untouched.
        """

        cards = _cards(request)
        card, trash_value = p.card_to_trash(cards, 1.0)
        v = Summer()
        v.add("Trash Value", trash_value)
        if card is None:
            least: Entity | None = None
            least_value = 0.0
            for candidate in cards:
                value = p.acquire_value(candidate).sum
                if least is None or _double_compare(value, least_value) < 0:
                    least, least_value = candidate, value
            card = least
        if card is None:
            return Answer(0.0, None, "Shai-Hulud | no card")
        return Answer(v.sum, ((card.ref,),), f"Shai-Hulud | trash {card.ref}")


@port(_AA + "ShaiHuludAcquireAbility")
class ShaiHuludAcquireAbility(AcquireAbility):
    """``ActivatedAbilities.RiseOfIx.ShaiHuludAcquireAbility`` (Shai-Hulud's
    acquire effect: trash a card; ``AcquireEffectList [Trash]``, valued by
    ``GetAcquireEffectsValue``). ``GetSourceEntityID`` @0x4ddd490;
    ``Targets`` @0x4ddd590 = ``AcquireAbility.Targets`` then the trash prompt.

    Note: the card also lists the plain ``AcquireAbility``, after this one;
    code that takes a card's first ``AcquireAbility`` port gets this one.

    ``evaluate`` responds ``((card,),)``: the card to trash."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShaiHuludAcquireAbility::Evaluate`` @0x4ddd770 (replaces
        ``AcquireAbility``'s): ``GetCardToTrash(targets.OfType<
        WormImperiumPlayable>(), 1.0)``; a found card at its trash value
        (``UpdateSelectionTargets``), else the untouched choice."""

        card, value = p.card_to_trash(_cards(request), 1.0)
        if card is None:
            return Answer(0.0, None, "Shai-Hulud acquire | nothing to trash")
        return Answer(value, ((card.ref,),), f"Shai-Hulud acquire | trash {card.ref}")


# ---------------------------------------------------------------------------
# Treachery's self-trash
# ---------------------------------------------------------------------------


@port(_AA + "TreacheryTrashSelfAbility")
class TreacheryTrashSelfAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.TreacheryTrashSelfAbility`` (Treachery's
    "trash this card" box). ``.ctor`` @0x4dec3b0: timing Agent;
    ``SelectionMode`` @0x4dec4c0: Explicit; ``Cost`` = NoCostAction
    @0x4dec4d0; ``GetUnusualSelections`` @0x4dec620 (the Baron's Masterstroke
    confirmation) is interface plumbing. ``evaluate`` is ``DeferredAbility``'s
    (its ``DeferValue``, no sub-target)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TreacheryTrashSelfAbility::SelectionMode`` @0x4dec4c0: Explicit."""

        return SelectionMode.EXPLICIT


# ---------------------------------------------------------------------------
# Web of Power
# ---------------------------------------------------------------------------


@port(_AA + "WebOfPowerEmperorAbility")
class WebOfPowerEmperorAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.WebOfPowerEmperorAbility`` (Web of Power's
    Emperor line: 2 Solari with Emperor influence 2). ``.ctor`` @0x4df13d0:
    timing Agent (``HideInvalidDeferred``); ``SelectionMode`` @0x4df1550:
    Explicit; ``get_AlwaysRunImmediately`` @0x4df1560 = true; ``Cost``
    @0x4df1530: ``HasFactionInfluence.AtLeast(Emperor, 2)``. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WebOfPowerEmperorAbility::SelectionMode`` @0x4df1550: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4df1530: Emperor influence 2."""

        return _influence(p, _EMPEROR) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WebOfPowerEmperorAbility::ValueForPlayer`` @0x4df1640: with Emperor
        influence at 2 or more, ``GetSolariValue(2)`` as "Web Of Power Emperor
        Solari"."""

        v = Summer()
        if _influence(p, _EMPEROR) >= 2:
            v.add("Web Of Power Emperor Solari", p.solari_value(2))
        return v


@port(_AA + "WebOfPowerSpacingGuildAbility")
class WebOfPowerSpacingGuildAbility(DrawAbility):
    """``ActivatedAbilities.RiseOfIx.WebOfPowerSpacingGuildAbility`` (Web of
    Power's Spacing Guild line: draw a card with Spacing Guild influence 2).
    ``.ctor`` @0x4df2670 (``DrawAbility.ctor``); only ``Cost`` is overridden:
    V/E are ``DrawAbility``'s (V gated on this cost)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4df2750: ``HasFactionInfluence.AtLeast(SpacingGuild,
        2)`` then ``HasDrawableCard``."""

        return _influence(p, _SPACING_GUILD) >= 2 and _has_drawable_card(p)


@port(_AA + "WebOfPowerFremenAbility")
class WebOfPowerFremenAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.WebOfPowerFremenAbility`` (Web of Power's
    Fremen line: a water with Fremen influence 2). ``.ctor`` @0x4df1b80:
    timing Agent (``HideInvalidDeferred``); ``SelectionMode`` @0x4df1d00:
    Explicit; ``get_AlwaysRunImmediately`` @0x4df1d10 = true; ``Cost``
    @0x4df1ce0: ``HasFactionInfluence.AtLeast(Fremen, 2)``. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WebOfPowerFremenAbility::SelectionMode`` @0x4df1d00: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4df1ce0: Fremen influence 2."""

        return _influence(p, _FREMEN) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WebOfPowerFremenAbility::ValueForPlayer`` @0x4df1df0: with Fremen
        influence at 2 or more, ``GetWaterValue(1)`` as "Web Of Power Fremen
        Water"."""

        v = Summer()
        if _influence(p, _FREMEN) >= 2:
            v.add("Web Of Power Fremen Water", p.water_value(1))
        return v


@port(_AA + "WebOfPowerRevealAbility")
class WebOfPowerRevealAbility(GainAnyInfluenceAbility):
    """``ActivatedAbilities.RiseOfIx.WebOfPowerRevealAbility`` (Web of Power's
    Reveal: an influence on any track). ``.ctor`` @0x4df2470: timing Reveal;
    ``get_LoggingMode`` @0x4df2580 is logging only: V/E and
    ``SelectionMode`` are ``GainAnyInfluenceAbility``'s (Explicit; the best
    faction track, response ``((track,),)``)."""

    timing: ClassVar[Timing] = Timing.REVEAL


# ---------------------------------------------------------------------------
# Weirding Way
# ---------------------------------------------------------------------------


@port(_AA + "WeirdingWayAbility")
class WeirdingWayAbility(DeferredAbility):
    """``ActivatedAbilities.RiseOfIx.WeirdingWayAbility`` (Weirding Way's Agent
    box: a choose-one prompt). ``.ctor`` @0x4df29c0: timing Agent;
    ``SelectionMode`` @0x4df2bc0: Optional; ``Cost`` = NoCostAction
    @0x4df2b70.

    ``evaluate`` responds ``((0,),)`` or ``((1,),)`` (``IntTargetResponse``)
    at 1.0."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WeirdingWayAbility::SelectionMode`` @0x4df2bc0: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WeirdingWayAbility::ValueForPlayer`` @0x4df2db0: with the lower
        ``ConflictPostureBounds`` at or above ``CurrentConflictInterest().Sum``
        (``ucomisd lower, interest; jb`` skips; NaN skips),
        ``WeirdingWayValue`` (vslot 260) as "Weirding Way"."""

        v = Summer()
        interest = p.current_conflict_interest().sum
        lower, _upper = p.conflict_posture_bounds()
        if lower >= interest:
            v.add("Weirding Way", p.C.WeirdingWayValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WeirdingWayAbility::Evaluate`` @0x4df2f80: option 1 when the lower
        ``ConflictPostureBounds`` is at or above the conflict interest
        (``ucomisd lower, interest; jae``), else option 0 (NaN: 0); value 1.0
        (f64 literal)."""

        interest = p.current_conflict_interest().sum
        lower, _upper = p.conflict_posture_bounds()
        option = 1 if lower >= interest else 0
        return Answer(1.0, ((option,),), f"Weirding Way | {option}")


@port(BOUNDLESS_AMBITION_CUSTOM)
class BoundlessAmbitionCustomAbility(DeferredAbility):
    """``PlayAbilities.Promo.BoundlessAmbitionCustomAbility``: the "acquire a
    card that costs 5 or less" that Boundless Ambition's Reveal
    (``BoundlessAmbitionRevealAbility/<BeginExecution>d__9`` @0x4d8dd90:
    ``GainCustomAbility``) and its Unload
    (``BoundlessAmbitionUnloadAbility/<BeginExecution>d__9`` @0x4b0b5b0:
    ``AddCustomAbility``) grant the player.

    ``Targets`` @0x4c5cff0: ``MakeAcquireImperiumRowCardTargeting(maxCost 5,
    includeReserved, includeCanTopOfDeck)``: ``request.infos[0]`` the Row
    then Reserve cards, ``infos[1]`` the destination picker.
    ``evaluate`` responds ``((card,), (0,))``."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SelectionMode`` @0x4c5d1b0: Optional (``return 0``)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4c5d100: ``HasImperiumRowCardWithPersuasionCostLessThan
        (6)`` and ``HasCustomAbility``: a Row card (never the Reserve) of cost
        5 or less."""

        return any(
            card_entity(ref).int_attr("PersuasionCost", 0) < 6
            for ref in p.ctx.imperium_row
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4c5d360: the base summer plus, for the row
        card ``MaxByOrElse(AcquireValue(P).Sum)`` among
        ``ImperiumRowCards.OfType<WormImperiumPlayable>().Where(b__14_0)``
        (``b__14_0`` @0x4c5e070: ``PersuasionCost < 6``), its
        ``AcquireValue`` ("Boundless Ambition Acquire <card>"); none, nothing.
        """

        v = Summer()
        best: tuple[Entity, float] | None = None
        for ref in p.ctx.imperium_row:
            card = card_entity(ref)
            if card.int_attr("PersuasionCost", 0) >= 6:
                continue
            value = p.acquire_value(card).sum
            if best is None or value > best[1]:
                best = (card, value)
        if best is not None:
            v.add(f"Boundless Ambition Acquire {best[0].ref}", best[1])
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``Evaluate`` @0x4c5d750: each card target
        (``GetTargets().OfType<WormImperiumPlayable>()``) at
        ``AcquireValue(P).Sum``, answered ``[EntityListTargetResponse([card]),
        IntTargetResponse(0)]`` -- the card, then option 0 of the destination
        picker -- and kept only when strictly better
        (``UpdateSelectionResponses``)."""

        best: Answer | None = None
        for card in _targets(request, Kind.CARD):
            value = p.acquire_value(card).sum
            if best is None or value > best.value:
                best = Answer(
                    value, ((card.ref,), (0,)), f"Boundless Ambition | {card.ref}"
                )
        return best if best is not None else Answer(0.0, None, "Boundless Ambition")
