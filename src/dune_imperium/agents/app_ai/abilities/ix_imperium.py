"""Rise of Ix's Imperium cards and the promo ``imperium.promo.boundless_ambition``):
their ability classes.

Ports of the 46 app classes the Ix Imperium cards use and no other module ports yet;
each follows the app's AI for that class, and the detailed notes are kept privately
(``docs/app-ai-plan.md`` §13.4 slice 6). Already ported elsewhere and reused as they
are: ``FreighterAgentAbility`` / ``FreighterRevealAbility`` (``abilities/ix_board``),
``AcquireTechAgentAbility`` (``abilities/tech``), ``ImperialBasharRevealAbility``,
``InTheShadowsRevealAbility`` and ``CapturedMentatAgentAbility``
(``abilities/imperium_a``), ``ThufirHawatRevealAbility``, ``PowerPlayAgentAbility``,
``RevealGainIntrigueAbility``, ``TrashAgentAbility`` (``abilities/generic`` and the
Uprising modules) and ``ControlTheSpiceAbility`` (Epic).

App class chains of the new classes:

- ``ActivatedAbilities.DeferredAbility`` <- ``Promo.BoundlessAmbitionRevealAbility``,
  ``RiseOfIx.AppropriateAbility``, ``BountyHunterAbility``, ``CourtIntrigueAbility``,
  ``DesertAmbushAbility``, ``EmbeddedAgentAbility``, ``EsmarTuekAbility``,
  ``GuildChiefAdministratorAbility``, ``ImperialBasharAgentAbility``,
  ``InTheShadowsAgentAbility``, ``IxGuildCompactAgentAbility``,
  ``IxianEngineerAbility``, ``LocalFenceAbility``, ``NegotiatedWithdrawalAbility``,
  ``SatelliteBanAbility``, ``SayyadinaAbility``, ``ShaiHuludAbility``,
  ``SpiceTraderAbility``, ``TreacheryTrashSelfAbility``, ``TruthsayerAbility``,
  ``WebOfPowerEmperorAbility``, ``WebOfPowerFremenAbility``, ``WeirdingWayAbility``;
- ``ActivatedAbilities.OptionalRetreatAbility`` <-
  ``SatelliteBanRevealAbility``; ``ActivatedAbilities.DrawAbility`` <-
  ``RiseOfIx.WebOfPowerSpacingGuildAbility``;
  ``ActivatedAbilities.GainAnyInfluenceAbility`` <-
  ``RiseOfIx.WebOfPowerRevealAbility``; ``ActivatedAbilities.AcquireAbility`` <-
  ``RiseOfIx.ShaiHuludAcquireAbility``;
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
from dune_imperium.agents.app_ai.abilities.intrigue import (
    _can_gain_faction_influence,
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
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.player import PlayerState

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "ability.activated.ix."
_PA = "ability.play.ix."
_TA = "ability.triggered.ix."
_AA_BASE = "ability.activated.original."
_AA_PROMO = "ability.activated.promo."
_TA_PROMO = "ability.triggered.promo."

#: The playmat custom ability Boundless Ambition's Reveal reads
#: (``ability.play.promo.boundless_ambition_custom``, ported below).
BOUNDLESS_AMBITION_CUSTOM: Final = (
    "ability.play.promo.boundless_ambition_custom"
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

#: ``AppropriateAbility.Evaluate``'s ``IntTargetResponse(0)``: the payment
#: option ``GetCustomChoiceFilter`` offers when the tile's
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
    """One ``Unit`` target in the Conflict (a troop or a dreadnought).

    ``ref`` is how the window's target info names it (entity ref or option index),
    ``seat`` its ``OwningPlayer`` and ``strength`` its ``Strength`` (a troop 2, a
    dreadnought 3).
    """

    ref: str | int
    seat: int
    strength: int


def _unit_targets(
    info: TargetInfo, units: Mapping[str | int, ConflictUnit]
) -> list[ConflictUnit]:
    """``ValidEntities<Unit>(info)``: the info's items that are units, in
    the info's order (entity refs first, then options)."""

    items: tuple[str | int, ...] = (*(e.ref for e in info.entities), *info.options)
    return [units[item] for item in items if item in units]


def _conflict_units(player: PlayerState) -> int:
    """``Player.ConflictUnits`` /
    ``GetPlayerDeployed(P).children.Count``: every unit in the Conflict, Rise
    of Ix dreadnoughts included (``PlayerState.units_in_conflict``, as in
    ``profile/combat._conflict_units``)."""

    return player.units_in_conflict


def _garrison_units(player: PlayerState) -> int:
    """``Player.GarrisonUnits``: every garrison unit,
    dreadnoughts included (as ``profile/combat._garrison_units``)."""

    return (
        player.troops_garrison
        + player.commanders_garrison
        + player.dreadnoughts_garrison
    )


def _conflict_dreadnoughts(player: PlayerState) -> int:
    """``GetPlayerDeployed(P).children.OfType<Dreadnought>().Count()`` /
    ``Player.ConflictDreadnoughts``."""

    return player.dreadnoughts_conflict


def _hand_count(p: Profile) -> int:
    """``Player.HandCount``."""

    return len(p.ctx.hand)


def _tech_tile_count(p: Profile) -> int:
    """``Player.TechTileCount``: the seat's Tech tiles."""

    return len(p.ctx.me.tech_ids)


def _influence(p: Profile, faction: str) -> int:
    """``Player.GetFactionInfluence(F)`` for the seat itself."""

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
    """``System.Double.CompareTo`` (``AIValueSummer.CompareTo`` = ``Sum``):
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
    """``GetTargets(...).OfType<ImperiumPlayable>()`` of one target info."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is Kind.CARD]


def _tracks(request: Request, index: int) -> list[Entity]:
    """``ValidEntities<FactionTrack>(info)``."""

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


@port(_TA_PROMO + "boundless_ambition_unload")
class BoundlessAmbitionUnloadAbility(TriggeredAbility):
    """``ability.triggered.promo.boundless_ambition_unload`` (Boundless
    Ambition's Unload box). constructor stores no timing;
    ``ShouldExhaust`` = false; ``IsValidFor``, ``Cost``
    (NoCostAction) and ``BeginExecution`` are engine-side: no AI
    hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA_PROMO + "boundless_ambition_unload_opp")
class BoundlessAmbitionUnloadOppAbility(TriggeredAbility):
    """``ability.triggered.promo.boundless_ambition_unload_opp``
    (Boundless Ambition's Unload, the opponent's side). constructor
    stores no timing; ``ShouldExhaust`` = false; ``Cost``
    (NoCostAction): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "unload")
class UnloadAbility(TriggeredAbility):
    """``ability.triggered.ix.unload`` (the Unload box of CHOAM
    Delegate, Esmar Tuek, Ix-Guild Compact, Treachery and Water Peddler).
    constructor stores no timing; ``ShouldExhaust`` =
    false; ``IsValidFor``, ``Cost`` (NoCostAction), ``BeginExecution``
    and ``Undo`` are engine-side: no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "freighter_fleet_opp_track_positive")
class FreighterFleetOppTrackPositive(TriggeredAbility):
    """``ability.triggered.ix.freighter_fleet_opp_track_positive`` (Freighter
    Fleet). constructor stores no timing; ``ShouldExhaust``
 = false; ``Cost`` (NoCostAction): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "freighter_fleet_opp_track_zero")
class FreighterFleetOppTrackZero(TriggeredAbility):
    """``ability.triggered.ix.freighter_fleet_opp_track_zero`` (Freighter
    Fleet). constructor stores no timing; ``ShouldExhaust``
 = false; ``Cost`` (NoCostAction): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "freighter_fleet_unload")
class FreighterFleetUnloadAbility(TriggeredAbility):
    """``ability.triggered.ix.freighter_fleet_unload`` (Freighter
    Fleet's Unload box). constructor stores no timing;
    ``ShouldExhaust`` = false; ``Cost`` (NoCostAction
): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "guild_accord_unload")
class GuildAccordUnloadAbility(TriggeredAbility):
    """``ability.triggered.ix.guild_accord_unload`` (Guild Accord's
    Unload box). constructor stores no timing; ``ShouldExhaust``
 = false; ``Cost`` (NoCostAction): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "in_the_shadows_unload")
class InTheShadowsUnloadAbility(TriggeredAbility):
    """``ability.triggered.ix.in_the_shadows_unload`` (In the
    Shadows' Unload box). constructor stores no timing;
    ``ShouldExhaust`` = false; ``Cost`` (NoCostAction
): no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "full_scale_assault")
class FullScaleAssaultAbility(TriggeredAbility):
    """``ability.triggered.ix.full_scale_assault`` (Full-Scale
    Assault's dreadnought trigger). constructor: timing Reveal;
    ``ShouldExhaust`` = false; ``GetDeployedDreadnoughts``
, ``IsValidFor`` and ``Cost`` (NoCostAction) are
    engine-side: no AI hook (its Reveal value is
    ``FullScaleAssaultRevealAbility``'s)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Triggered abilities with a value: Guild Accord, Sayyadina, Shai-Hulud
# ---------------------------------------------------------------------------


@port(_TA + "guild_accord_alliance")
class GuildAccordAllianceAbility(AllianceAbility):
    """``ability.triggered.ix.guild_accord_alliance`` (Guild
    Accord's Spacing Guild Alliance). constructor: timing Reveal;
    ``AllianceFaction`` = SpacingGuild (2); ``Cost`` =
    NoCostAction."""

    timing: ClassVar[Timing] = Timing.REVEAL
    alliance_faction: ClassVar[str | None] = _SPACING_GUILD

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildAccordAllianceAbility.ValueForPlayer``: in the
        ``AllianceFaction`` Alliance (``InAlliance``),
        ``GetSpiceValue(1) * 3.0`` (f64 literal) as "Guild Accord Alliance
        Bonus"."""

        v = Summer()
        if _in_alliance(p, _SPACING_GUILD):
            v.add("Guild Accord Alliance Bonus", p.spice_value(1) * 3.0)
        return v


@port(_TA + "sayyadina_bond")
class SayyadinaBondAbility(BondAbility):
    """``ability.triggered.ix.sayyadina_bond`` (Sayyadina's Fremen
    bond). constructor: timing Reveal; ``BondFaction``
 = Fremen (4); ``Cost`` = NoCostAction. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SayyadinaBondAbility.ValueForPlayer``.

        Another Fremen card of the hand or play area (``Hand.Concat(
        AllCardsInPlay)``, ``ValueForPlayer`` skips the
        owner) -> ``GetPersuasionValue(3)`` as "Sayyadina Resources".
        """

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add("Sayyadina Resources", p.persuasion_value(3))
        return v


@port(_TA + "shai_hulud_bond")
class ShaiHuludBondAbility(BondAbility):
    """``ability.triggered.ix.shai_hulud_bond`` (Shai-Hulud's
    Fremen bond). constructor: timing Reveal; ``BondFaction``
 = Fremen (4); ``Cost`` = NoCostAction. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShaiHuludBondAbility.ValueForPlayer``: another Fremen card in hand or in
        play -> ``GetStrengthValue(1, false) * 5.0`` (f64 literal) as "Shai-Hulud
        Resources"."""

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add("Shai-Hulud Resources", p.strength_value(1, False) * 5.0)
        return v


# ---------------------------------------------------------------------------
# Reveal boxes
# ---------------------------------------------------------------------------


@port(_PA + "full_scale_assault_reveal")
class FullScaleAssaultRevealAbility(RevealAbility):
    """``ability.play.ix.full_scale_assault_reveal`` (Full-Scale
    Assault's Reveal box). constructor: timing Reveal;
    ``GetRevealPreviewValue`` answers ``{Persuasion: 2, Strength:
    3 * dreadnoughts in the Conflict}``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FullScaleAssaultRevealAbility.ValueForPlayer``.

        ``RevealAbility.ValueForPlayer``, then ``GetStrengthValue(1, false) * (3 * n)``
        as "Full Scale Assault Reveal", ``n`` the seat's dreadnoughts in the Conflict
        (``GetPlayerDeployed(P).children.OfType<Dreadnought>().Count()``).
        """

        v = super().value_for_player(p, with_entities)
        n = _conflict_dreadnoughts(p.ctx.me)
        v.add("Full Scale Assault Reveal", p.strength_value(1, False) * float(3 * n))
        return v


def _has_agent_on_emperor_space(p: Profile) -> bool:
    """``ImperialShockTrooperAbility.hasAgentOnEmperorSpace``.

    ``Board.Descendents.OfType<Agent>().Where(a.OwningPlayer == P)`` ``.Any(a.parent is
    Space && ActionIcon == 4)`` (``AgentIcons.Emperor`` = 4): one of the seat's
    Agents stands on an Emperor-icon board space.
    """

    for space_id in p.ctx.me.agent_locations:
        if not is_board_space(space_id):
            continue
        if space_entity(space_id, p.ctx.board).attr("AgentIcon") == "Emperor":
            return True
    return False


@port(_PA + "imperial_shock_trooper")
class ImperialShockTrooperAbility(RevealAbility):
    """``ability.play.ix.imperial_shock_trooper`` (Imperial Shock
    Trooper's Reveal box; the card has no generic ``RevealAbility``).
    constructor (the ``RevealAbility`` constructor: timing Reveal);
    ``GetRevealPreviewValue`` answers ``{Persuasion: 1, Strength:
    2 + 3 with an Agent on an Emperor space}``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialShockTrooperAbility.ValueForPlayer``.

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


@port(_PA + "in_the_shadows_reveal_preview")
class InTheShadowsRevealPreviewAbility(RevealAbility):
    """``ability.play.ix.in_the_shadows_reveal_preview`` (In the
    Shadows' Reveal box). constructor: timing Reveal;
    ``GetRevealPreviewValue`` answers only ``{WillClearUndo: Bene
    Gesserit influence == 3}``. The AI value is the generic ``RevealAbility``
    one (its "Reveal Deferred" holds ``InTheShadowsRevealAbility``)."""


@port(_PA + "ix_guild_compact_reveal")
class IxGuildCompactRevealAbility(RevealAbility):
    """``ability.play.ix.ix_guild_compact_reveal`` (Ix-Guild
    Compact's Reveal box; the card has no generic ``RevealAbility``).
    constructor (the ``RevealAbility`` constructor: timing Reveal)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxGuildCompactRevealAbility.ValueForPlayer``:
        ``RevealAbility.ValueForPlayer``, then ``NegotiateTechValue`` added to itself as
        "Ix Guild Compact 2 Negotiate Tech"."""

        v = super().value_for_player(p, with_entities)
        negotiate = p.negotiate_tech_value()
        v.add("Ix Guild Compact 2 Negotiate Tech", negotiate + negotiate)
        return v


@port(_PA + "sayyadina_reveal")
class SayyadinaRevealAbility(RevealAbility):
    """``ability.play.ix.sayyadina_reveal`` (Sayyadina's Reveal
    box). constructor: timing Reveal; ``GetRevealPreviewValue``
 answers ``{Persuasion: 3 with another own Fremen card in play
    or in hand, else 0}``. The AI value is the generic ``RevealAbility`` one."""


@port(_PA + "shai_hulud_reveal")
class ShaiHuludRevealAbility(RevealAbility):
    """``ability.play.ix.shai_hulud_reveal`` (Shai-Hulud's Reveal
    box). constructor: timing Reveal; ``GetRevealPreviewValue``
 answers ``{Strength: 5 with another own Fremen card in play or
    in hand, else 0}``. The AI value is the generic ``RevealAbility`` one."""


@port(_PA + "treachery_reveal")
class TreacheryRevealAbility(RevealAbility):
    """``ability.play.ix.treachery_reveal`` (Treachery's Reveal
    box). constructor (the ``RevealAbility`` constructor: timing Reveal);
    ``BeginExecution`` / ``Undo`` are engine-side."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TreacheryRevealAbility.ValueForPlayer``:
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


@port(_AA_PROMO + "boundless_ambition_reveal")
class BoundlessAmbitionRevealAbility(DeferredAbility):
    """``ability.activated.promo.boundless_ambition_reveal`` (Boundless
    Ambition's Reveal box). constructor: timing Reveal;
    ``SelectionMode``: Explicit; ``AlwaysRunImmediately``
 = true; ``Cost`` = NoCostAction.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BoundlessAmbitionRevealAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BoundlessAmbitionRevealAbility.ValueForPlayer``.

        The base (empty) summer plus the ``ValueForPlayer`` of the playmat's
        ``BoundlessAmbitionCustomAbility`` (``Playmat.Abilities.FirstOrDefault(...)``:
        ``is BoundlessAmbitionCustomAbility``), added as a sub-summer. ``SetupPhase``
        gives the playmat that ability in every Rise of Ix game (``IsSetEnabled(2)``),
        so it is always found (``BoundlessAmbitionCustomAbility`` below).
        """

        v = Summer()
        custom = ability_for(BOUNDLESS_AMBITION_CUSTOM, _PLAYMAT)
        v.merge(custom.value_for_player(p, with_entities))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BoundlessAmbitionRevealAbility.Evaluate``:
        ``UpdateSelectionTargets(100.0, src, null)`` (f64 literal; log
        "Boundless Ambition reveal | always play")."""

        return Answer(100.0, (), "Boundless Ambition reveal | always play")


# ---------------------------------------------------------------------------
# Agent boxes: Appropriate, Bounty Hunter, Court Intrigue
# ---------------------------------------------------------------------------


@port(_AA + "appropriate")
class AppropriateAbility(DeferredAbility):
    """``ability.activated.ix.appropriate`` (Appropriate's Agent
    box: acquire a Tech tile, paying Solari instead of spice). constructor
: timing Agent; ``TechDiscount`` = 0;
    ``IsCustomAbility`` = false.

    ``evaluate`` responds ``((tile,), (APPROPRIATE_PAY_SOLARI,))``: the tile
    entity of ``request.infos[0]`` and the payment option of the second
    target info."""

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``TechDiscount``.
    tech_discount: ClassVar[int] = 0

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``AppropriateAbility.SelectionMode``: Optional (0) when
        the owner's ``OwningPlayer`` is an AI (``IsAI``), else Explicit
        (3). The deciding seat is an AI seat."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``CanAcquireTechTile(TechDiscount, M,
        canUseSolari=true)`` then ``HasFactionInfluence.AtLeast(Emperor, 2)``."""

        return (
            bool(p.tech_acquire_targets(self.tech_discount, True))
            and _influence(p, _EMPEROR) >= 2
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``AppropriateAbility.ValueForPlayer``: with Emperor influence at 2 or more,
        ``BuyTechValue(0, true)`` as "Appropriate Buy Tech"."""

        v = Summer()
        if _influence(p, _EMPEROR) >= 2:
            v.add("Appropriate Buy Tech", p.buy_tech_value(0, True))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AppropriateAbility.Evaluate``.

        For each tile of ``GetTargets().OfType<TechTilePlayable>()`` in order,
        ``UpdateSelectionResponses(tile.AcquireValue(P).Sum, src,
        [EntityListTargetResponse([tile]), IntTargetResponse(0)])`` (the int is the
        constant 0): the first tile sticks, a later one only when strictly better.
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
    """``BountyHunterAbility.SpaceHasEnemyAgent``.

    ``Board.FindSpace(archID).children.OfType<Agent>() .Where(!IsDisabled)``
    ``.Any(a.OwningPlayer != P)``. Judgement (as ``SpaceAbility``'s infiltrate line in
    ``generic.py``): no Agent of a four-player game is disabled.
    """

    return any(seat != p.ctx.seat for seat in p.ctx.space_occupants(space.ref))


@port(_AA + "bounty_hunter")
class BountyHunterAbility(DeferredAbility):
    """``ability.activated.ix.bounty_hunter`` (Bounty Hunter's Agent
    box: 2 Solari at a space with an opponent's Agent). constructor:
    timing Agent; ``SelectionMode``: Explicit;
    ``AlwaysRunImmediately`` = true. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``, no sub-target)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BountyHunterAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BountyHunterAbility.ValueForPlayer``: the space among
        ``with_entities`` (``OfType<Space>().FirstOrDefault()``) holding an
        opponent's Agent (``_space_has_enemy_agent``) -> ``GetSolariValue(2)``
        as "Bounty Hunter Solari"."""

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and _space_has_enemy_agent(p, space):
            v.add("Bounty Hunter Solari", p.solari_value(2))
        return v


@port(_AA + "court_intrigue")
class CourtIntrigueAbility(DeferredAbility):
    """``ability.activated.ix.court_intrigue`` (Court Intrigue's
    Agent box: discard an Intrigue card to draw one). constructor:
    timing Agent; ``SelectionMode``: Optional; ``Cost``:
    ``HasIntrigueCard``; ``Targets``: "DiscardIntrigueCard", the
    held Intrigue cards.

    ``evaluate`` responds ``((intrigue,),)``: the chosen held Intrigue card."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CourtIntrigueAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasIntrigueCard``: an Intrigue card held."""

        return bool(p.ctx.intrigue_cards)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CourtIntrigueAbility.ValueForPlayer``: a bad Intrigue
        card held (``GetBadIntrigueCardsInHand.Any()``) -> ``CourtIntrigueValue``
 as "Court Intrigue with Bad Intrigue"."""

        v = Summer()
        if p.bad_intrigue_cards_in_hand():
            v.add("Court Intrigue with Bad Intrigue", p.C.CourtIntrigueValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CourtIntrigueAbility.Evaluate``.

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


@port(_AA + "desert_ambush")
class DesertAmbushAbility(DeferredAbility):
    """``ability.activated.ix.desert_ambush`` (Desert Ambush's
    Agent box: opponents' units in the Conflict retreat, one per troop
    deployed this turn). constructor: timing Agent; ``SelectionMode``
: Optional; ``IsUnexhausted`` = true; ``Cost``
: ``GetRemainingAmbushCount > 0`` (: the player's
    ``TroopsDeployedThisTurn``, doubled for a Ghola graft, minus the
    ``DesertAmbushUnitCount`` already used) then an opponent's troop or
    dreadnought in the Conflict (not modelled: our state has no
    ``TroopsDeployedThisTurn``; the engine owns legality).

    ``units`` are the valid ``Unit`` targets the window offers (the
    opponents' units in the Conflict); ``evaluate`` responds ``((ref, ...),)``:
    the refs of the units chosen in the first target info, at 0.5."""

    timing: ClassVar[Timing] = Timing.AGENT

    def __init__(self, owner: Entity, units: Sequence[ConflictUnit] = ()) -> None:
        super().__init__(owner)
        self.units: dict[str | int, ConflictUnit] = {u.ref: u for u in units}

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertAmbushAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DesertAmbushAbility.ValueForPlayer``.

        With 2 or more garrison units (``GarrisonUnits``) and the lower
        ``ConflictPostureBounds`` at or above ``CurrentConflictInterest().Sum`` (taken
        when ``lower >= interest``, NaN skips), ``DesertAmbushValue`` as "Desert Ambush
        Value"; then, when the opponents hold no unit in the Conflict
        (``Opponents.Sum(ConflictUnits)``,, skips), ``DesertAmbushNoOppositionPenalty``
        as "No Opposition".
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
        """``DesertAmbushAbility.Evaluate``.

        ``n = NumberToSelect`` of the first target info, ``targets`` its valid units.
        ``order = GetExpectedCombatOrderWithStrength()``; the seat's own entry gives
        ``estStrength`` (0 if missing) and is removed. ``trigger =
        Playmat.EndgameTriggerScore`` (default 10), ``conflictVP =
        CurrentConflict.VictoryPoints`` (0 without one). With ``opp =
        order.FirstOrDefault()``, while ``n > 0`` and ``opp`` is set:

        - when ``VP(opp) + conflictVP < trigger``, or ``>= trigger`` but
          ``VP(opp) + conflictVP < VP(P)`` (keeps "Expected First"), ``opp`` becomes the
          first entry of ``order`` that the first test accepts ("Can reduce opponent
          strength below current": ``estStrength > strength - Sum(its n strongest target
          units)``), else the first entry the second test accepts ("Can retreat all
          opponent units": no Agent left and ``ConflictUnits <= n``), else it stays
          ("Highest ExpectedStrength");
        - the ``n`` strongest target units of ``opp`` (``OrderByDescending(
          Strength)``, stable; ``Take(n)``) join the retreat list and ``n -=
          retreat.Count`` (the whole list's count); ``opp`` leaves ``order`` and the
          next first entry follows.

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

        def can_reduce(entry: tuple[int, int]) -> bool:
            removed = sum(u.strength for u in strongest(entry[0], n))
            return est_strength > entry[1] - removed

        def can_retreat_all(entry: tuple[int, int]) -> bool:
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


@port(_AA_BASE + "embedded_agent")
class EmbeddedAgentAbility(DeferredAbility):
    """``ability.activated.original.embedded_agent`` (Embedded Agent's
    Agent box: a Freighter step with another Bene Gesserit card in play).
    constructor: timing Agent; ``SelectionMode``:
    Explicit; ``AlwaysRunImmediately`` = true.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``EmbeddedAgentAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasPlayedFactionCard(BeneGesserit, owner)``:
        another Bene Gesserit card in play (read as in
        ``BeneGesseritDrawAbility.meets_cost``)."""

        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        return any(_has_faction(c, "BeneGesserit") for c in others)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EmbeddedAgentAbility.ValueForPlayer``: another Bene Gesserit card in play
        (``AllCardsInPlay.Except([owner]).Any(...)``) -> ``FreighterValue`` added to
        itself as "Embedded Agent 2 Freighter"."""

        v = Summer()
        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        if any(_has_faction(c, "BeneGesserit") for c in others):
            freighter = p.freighter_value()
            v.add("Embedded Agent 2 Freighter", freighter + freighter)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``EmbeddedAgentAbility.ValueInPileForOtherPlay``.

        The Bene Gesserit "played" pattern (``bg_played_pile_value``; no Bene Gesserit
        card in the play area,, and 2 or more Agents left) with ``FreighterValue * 1.5``
        (f64 literal) as "Bene Gesserit Played".
        """

        def played() -> float:
            return p.freighter_value() * 1.5

        return bg_played_pile_value(p, pile, card, played, "Bene Gesserit Played")

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``EmbeddedAgentAbility.Evaluate``: 100.0 (f64 literal),
        no sub-target."""

        return Answer(100.0, (), "Embedded Agent | 100")


@port(_AA + "esmar_tuek")
class EsmarTuekAbility(DeferredAbility):
    """``ability.activated.ix.esmar_tuek`` (Esmar Tuek's Agent box:
    pay 1 spice for a Spacing Guild influence and a card). constructor
: timing Agent; ``SelectionMode``: Optional;
    ``Cost``: ``HasResources.AtLeast(Spice, 1)``.

    ``evaluate`` responds ``()`` ("pay") at the summed value."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``EsmarTuekAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: at least 1 spice."""

        return p.ctx.me.resources.spice >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EsmarTuekAbility.ValueForPlayer``.

        Space among ``with_entities`` (``CollectFirst<Space>``): when
        ``CanAgentAbilityBePlayedWithSpace(space, Spice, 1)`` is false only a 0.0 term.
        Else "Esmar Tuek -1 Spice" = ``-GetSpiceValue(1)`` (the sign bit flipped),
        "Esmar Tuek SG Influence" = ``GetGainInfluenceValue(SpacingGuild, 1, -1,
        false).Sum``, "Esmar Tuek Draw" = ``CardDrawValue`` and "Buy Gains Bonus" =
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
        """``EsmarTuekAbility.Evaluate``: ``GetSpiceValue(-1)``
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


@port(_AA + "guild_chief_administrator")
class GuildChiefAdministratorAbility(DeferredAbility):
    """``ability.activated.ix.guild_chief_administrator`` (Guild
    Chief Administrator's Agent box: discard a card to trash a card).
    constructor: timing Agent; ``SelectionMode``:
    Optional; ``Cost``: ``HasImperiumCardInHand.Any``.

    ``evaluate`` responds ``((card,),)``: the card to discard among
    ``request.infos[0]``; ``evaluate_trash`` answers the trash prompt that
    follows (``((card,),)`` or ``((),)``)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildChiefAdministratorAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: an Imperium card in hand."""

        return bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildChiefAdministratorAbility.ValueForPlayer``: with 2 or more cards in
        hand, "Guild Chief Administrator Discard" = ``DiscardValue``, "Guild Chief
        Administrator Trash" = ``TrashCardValue`` and "Trash Card Bonus" =
        ``TrashMod``."""

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Guild Chief Administrator Discard", p.discard_value())
            v.add("Guild Chief Administrator Trash", p.trash_card_value())
            v.add("Trash Card Bonus", p.trash_mod())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildChiefAdministratorAbility.Evaluate``.

        ``discard = GetDiscardOrder(P, targets, false).FirstOrDefault()``; the
        trash pool is ``Hand.Concat(AllCardsInPlay).Concat(Discard)``
        (``Player`` +0xe8, +0xf8) and ``GetCardToTrash(pool, 1.0)``. With
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
        """``GuildChiefAdministratorAbility.EvaluateTrash`` (the
        trash prompt of ``BeginExecution``).

        ``GetCardToTrash(targets.OfType<ImperiumPlayable>(), 1.0)``: the card
        at its trash value (``UpdateTargets``), else the empty target list at
        1.0 (f64 literal).
        """

        card, value = p.card_to_trash(_cards(request), 1.0)
        if card is not None:
            return Answer(value, ((card.ref,),), f"GCA trash | {card.ref}")
        return Answer(1.0, ((),), "GCA trash | nothing")


@port(_AA + "in_the_shadows_agent")
class InTheShadowsAgentAbility(DeferredAbility):
    """``ability.activated.ix.in_the_shadows_agent`` (In the Shadows'
    Agent box: with 2 Bene Gesserit influence, discard a card for an influence
    with another faction). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost``:
    ``HasFactionInfluence.AtLeast(BeneGesserit, 2)``, then a card in hand,
    then ``CanGainInfluence([SpacingGuild, Emperor, Fremen])``.

    ``evaluate`` responds ``((card,), (track,))``: the card of
    ``request.infos[0]`` and the faction track of ``request.infos[1]``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``InTheShadowsAgentAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InTheShadowsAgentAbility.ValueForPlayer``.

        With Bene Gesserit influence at 2 or more and 2 or more cards in hand (both):
        "In The Shadows Discard" = ``DiscardValue`` and "In The Shadows Influence" =
        ``[Fremen, Emperor, SpacingGuild] .Max(GetGainInfluenceValue(F, 1, -1,
        false).Sum)`` (``Enumerable.Max``).
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
        """``InTheShadowsAgentAbility.Evaluate``.

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


@port(_AA + "ix_guild_compact_agent")
class IxGuildCompactAgentAbility(DeferredAbility):
    """``ability.activated.ix.ix_guild_compact_agent`` (Ix-Guild
    Compact's Agent box: discard 2 cards to commission a dreadnought).
    constructor: timing Agent; ``SelectionMode``:
    Optional; ``Cost``: ``HasImperiumCardInHand.AtLeast(2)`` then a
    dreadnought in the supply.

    ``evaluate`` responds ``((card, card),)``: the two cards to discard among
    ``request.infos[0]`` (fewer when fewer are offered)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``IxGuildCompactAgentAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: 2 cards in hand, then
        ``HasUnitsInSupply<Dreadnought>.Any``."""

        return _hand_count(p) >= 2 and p.ctx.me.dreadnoughts_supply > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxGuildCompactAgentAbility.ValueForPlayer``.

        ``d = DiscardValue``, ``n = GetDreadnoughtValue(1, false)``; with 3 or more
        cards in hand and ``d + d + n > 0.0`` (skips), "Ix Guild Compact 2 Discard" =
        ``d + d`` and "Ix Guild Compact Dreadnought" = ``n``.
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
        """``IxGuildCompactAgentAbility.Evaluate``.

        In the Late arc (``GetGameArc() > 1``) the untouched choice. Else "Discard 2" =
        ``DiscardValue * 2`` + "Dreadnought" = ``GetDreadnoughtValue(1, false)``,
        answered with the first two cards of ``GetDiscardOrder(P, targets, false)``
        (``Take(2)``).
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


@port(_AA + "satellite_ban")
class SatelliteBanAbility(DeferredAbility):
    """``ability.activated.ix.satellite_ban`` (Satellite Ban's Agent
    box: discard a card for a spice and a water). constructor: timing
    Agent; ``SelectionMode``: Optional; ``Cost``:
    ``HasImperiumCardInHand.Any``.

    ``evaluate`` responds ``((card,),)``: the card to discard."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SatelliteBanAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: an Imperium card in hand."""

        return bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SatelliteBanAbility.ValueForPlayer``: with 2 or more
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
        """``SatelliteBanAbility.Evaluate``: "Discard" =
        ``DiscardValue`` + "Spice" = ``GetSpiceValue(1)`` + "Water" =
        ``GetWaterValue(1)`` (``_discard_for``)."""

        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("Spice", p.spice_value(1))
        v.add("Water", p.water_value(1))
        return _discard_for(p, request, v, "Satellite Ban (Agent)")


@port(_AA + "spice_trader")
class SpiceTraderAbility(DeferredAbility):
    """``ability.activated.ix.spice_trader`` (Spice Trader's Agent
    box: with 2 Fremen influence, discard a card for 2 spice). constructor
: timing Agent; ``SelectionMode``: Optional; ``Cost``
: ``HasFactionInfluence.AtLeast(Fremen, 2)`` then a card in hand.

    ``evaluate`` responds ``((card,),)``: the card to discard."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SpiceTraderAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Fremen influence 2, then a card in hand."""

        return _influence(p, _FREMEN) >= 2 and bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceTraderAbility.ValueForPlayer``: with Fremen influence at 2 or more and
        2 or more cards in hand, "Spice Trader Discard" = ``DiscardValue`` and "Spice
        Trader 2 Spice" = ``GetSpiceValue(1)`` added to itself."""

        v = Summer()
        if _influence(p, _FREMEN) >= 2 and _hand_count(p) >= 2:
            v.add("Spice Trader Discard", p.discard_value())
            spice = p.spice_value(1)
            v.add("Spice Trader 2 Spice", spice + spice)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpiceTraderAbility.Evaluate``: "Discard" =
        ``DiscardValue`` + "2 Spice" = ``GetSpiceValue(2)``
        (``_discard_for``)."""

        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("2 Spice", p.spice_value(2))
        return _discard_for(p, request, v, "Spice Trader")


@port(_AA + "truthsayer")
class TruthsayerAbility(DeferredAbility):
    """``ability.activated.ix.truthsayer`` (Truthsayer's Agent
    box: discard a card to draw a card). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost``:
    ``HasImperiumCardInHand.Any``.

    ``evaluate`` responds ``((card,),)``: the card to discard."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TruthsayerAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: an Imperium card in hand."""

        return bool(p.ctx.hand)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TruthsayerAbility.ValueForPlayer``: with 2 or more
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
        """``TruthsayerAbility.Evaluate``: "Discard" =
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


@port(_AA + "imperial_bashar_agent")
class ImperialBasharAgentAbility(DeferredAbility):
    """``ability.activated.ix.imperial_bashar_agent`` (Imperial
    Bashar's Agent box: a troop OR trash a card, the "AOrB" prompt).
    constructor: timing Agent; ``SelectionMode``:
    Explicit; ``Cost``: ``HasTrashableCard`` or a troop in the
    supply.

    ``request.infos[0]`` is the choose-one prompt (options 0 troop, 1 trash),
    ``request.infos[1]`` the cards option 1 offers (the
    ``CustomChoiceResultTargetInformation`` result of choice 1).
    ``evaluate`` responds ``((0,),)``, ``((1,), (card,))`` or ``((1,),)``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ImperialBasharAgentAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasTrashableCard`` or
        ``HasUnitsInSupply<Troop>.Any`` (``CostAction.Or``)."""

        return _has_trashable_card(p) or p.ctx.me.troops_supply > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialBasharAgentAbility.ValueForPlayer``:
        ``Math.Max(GetTroopValue(1, false), TrashCardValue + TrashMod)`` as
        "Imperial Bashar: Troop or Trash"."""

        v = Summer()
        troop = p.troop_value(1, False)
        trash = p.trash_card_value() + p.trash_mod()
        v.add("Imperial Bashar: Troop or Trash", _dmax(troop, trash))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``ImperialBasharAgentAbility.SpecificAcquireValue``: the cards of
        ``AllImperiumCards`` with ``Strength > 0`` times ``ImperialBasharSwordValue``
 as "Imperial Bashar"."""

        v = Summer()
        swords = sum(1 for c in _all_imperium_cards(p) if c.int_attr("Strength") > 0)
        v.add("Imperial Bashar", p.C.ImperialBasharSwordValue * float(swords))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperialBasharAgentAbility.Evaluate``.

        Option 0 at ``GetTroopValue(1, false)`` first (``UpdateSelectionResponses``).
        Then, when the choose-one info carries the option-1 result (it finds the
        ``CustomChoiceResultTargetInformation``, its result map not empty),
        ``GetCardToTrash(cards, 1.0)``; a found card is answered ``[1], [card]`` at its
        trash value + ``TrashCardValue`` (strictly greater replaces). Last, while the
        stored value is not above 0.0 (skips), option 1 alone at 0.5 (f64 literal).
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


@port(_AA + "ixian_engineer")
class IxianEngineerAbility(DeferredAbility):
    """``ability.activated.ix.ixian_engineer`` (Ixian Engineer's
    Reveal box: with 3 Tech tiles, trash this card for a victory point).
    constructor: timing Reveal; ``SelectionMode``:
    Optional; ``Cost``: ``HasTechTiles.AtLeast(3)``.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``IxianEngineerAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: 3 Tech tiles."""

        return _tech_tile_count(p) >= 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``IxianEngineerAbility.ValueForPlayer``: with 3 or more Tech tiles,
        ``GetVictoryPointValue(1)`` as "Ixian Engineer VP"."""

        v = Summer()
        if _tech_tile_count(p) >= 3:
            v.add("Ixian Engineer VP", p.victory_point_value(1))
        return v

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``IxianEngineerAbility.SpecificAcquireValue``: with 2 or more Tech tiles,
        ``IxianEngineerValue`` as "Ixian Engineer"."""

        v = Summer()
        if _tech_tile_count(p) >= 2:
            v.add("Ixian Engineer", p.C.IxianEngineerValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IxianEngineerAbility.Evaluate``: 100.0 (f64 literal),
        no sub-target."""

        return Answer(100.0, (), "Ixian Engineer | 100")


@port(_AA + "local_fence")
class LocalFenceAbility(DeferredAbility):
    """``ability.activated.ix.local_fence`` (Local Fence's Agent
    box: 2 spice for 5 Solari OR 5 Solari for 4 spice). constructor
: timing Agent; ``SelectionMode``: Optional;
    ``Cost``: at least 2 spice or at least 5 Solari.

    ``evaluate`` responds ``((LOCAL_FENCE_SPICE_TO_SOLARI,),)`` or
    ``((LOCAL_FENCE_SOLARI_TO_SPICE,),)`` (``IntTargetResponse``)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``LocalFenceAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``AtLeast(Spice, 2).Or(AtLeast(Solari, 5))``."""

        me = p.ctx.me
        return me.resources.spice >= 2 or me.resources.solari >= 5

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LocalFenceAbility.ValueForPlayer``.

        ``s = GetSpiceValue(1)``; the spice trade is open with 2 spice, the Solari trade
        with 5 Solari. With a space among ``with_entities``, each trade whose cost the
        space leaves unpayable (``CanAgentAbilityBePlayedWithSpace(space, Spice, 2)`` /
        ``(space, Solari, 5)``) adds a 0.0 term and closes. With neither open, nothing
        more. Else ``a = GetSolariValue(5) - (s + s)`` for the open spice trade, ``b = s
        * 4.0 + GetSolariValue(-5)`` (f64 literal) for the open Solari trade (0.0
        otherwise), and ``Math.Max(0.0, Math.Max(a, b))`` as "Local Fence Resource".
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
        """``LocalFenceAbility.Evaluate``.

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


@port(_AA + "negotiated_withdrawal")
class NegotiatedWithdrawalAbility(DeferredAbility):
    """``ability.activated.ix.negotiated_withdrawal`` (Negotiated
    Withdrawal's Reveal box: retreat 3 units for an influence). constructor
: timing Reveal; ``SelectionMode``: Optional;
    ``Cost``: ``ConflictTroops + ConflictDreadnoughts >= 3`` then ``CanGainInfluence``;
    ``Targets`` (``Targets``
..) yields the faction prompt
    (``MakeGainAnyFactionInfluenceTargeting``) first, then the retreat prompt
    (the deployed troops and units, ``NumberToSelect`` 3).

    ``units`` are the seat's units the window knows (``ConflictUnit`` rows).
    ``evaluate`` responds ``((track,), (ref, ...))``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def __init__(self, owner: Entity, units: Sequence[ConflictUnit] = ()) -> None:
        super().__init__(owner)
        self.units: dict[str | int, ConflictUnit] = {u.ref: u for u in units}

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``NegotiatedWithdrawalAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``ConflictTroops + ConflictDreadnoughts > 2``
        (``BoolAction(2 < troops + dreadnoughts)``), then ``CanGainInfluence``
        (a Faction the seat can still rise on). A Bloodlines Commander is a
        troop [Bloodlines p. 4]."""

        me = p.ctx.me
        units = me.troops_conflict + me.commanders_conflict + me.dreadnoughts_conflict
        return units > 2 and any(_can_gain_faction_influence(me, f) for f in FACTIONS)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``NegotiatedWithdrawalAbility.ValueForPlayer``: with ``GarrisonUnits +
        ConflictUnits >= 2``, ``NegotiatedWithdrawalRetreatValue`` as "Negotiated
        Withdrawal Retreat"."""

        v = Summer()
        me = p.ctx.me
        if _garrison_units(me) + _conflict_units(me) >= 2:
            v.add("Negotiated Withdrawal Retreat", p.C.NegotiatedWithdrawalRetreatValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``NegotiatedWithdrawalAbility.Evaluate``.

        Needs two entity-list target infos (``Count < 2``: untouched). Both the units
        and the faction tracks are read from the **first** info (``List.Item(0)``
        twice): ``units = ValidEntities<Unit>(infos[0]) .OrderBy(Strength)`` (stable),
        ``retreat = units.Take(3)`` and ``s = retreat.Sum(Strength)``. ``r0 =
        EstimatedConflictRank(0)``, ``r1 = EstimatedConflictRank(-s)`` (4 when
        unranked); ``r0 <= 2`` with ``r0 != r1`` leaves the choice untouched. Then for
        each track of ``ValidEntities<FactionTrack>(infos[0])``,
        ``GetGainInfluenceValue(F, 1, -1, false).Sum`` answered ``[track], [retreat
        ids]`` (first sticks, then strictly greater). With the app's own target order
        (factions first) the retreat list is always empty.
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


@port(_AA_BASE + "satellite_ban_reveal")
class SatelliteBanRevealAbility(OptionalRetreatAbility):
    """``ability.activated.original.satellite_ban_reveal`` (Satellite Ban's
    Reveal: retreat up to 2 troops). constructor: timing Reveal;
    ``MaxRetreat`` = 2. ``evaluate``:
    ``OptionalRetreatAbility``'s."""

    timing: ClassVar[Timing] = Timing.REVEAL
    MAX_RETREAT: ClassVar[int] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SatelliteBanRevealAbility.ValueForPlayer``:
        ``Math.Min(units in the Conflict * 0.5, 1.0)`` (f64 literals;
        ``GetPlayerDeployed(P).children.Count``) as "Satellite Ban Troop
        Retreat Bonus"."""

        v = Summer()
        units = _conflict_units(p.ctx.me)
        v.add("Satellite Ban Troop Retreat Bonus", min(units * 0.5, 1.0))
        return v


@port(_AA + "sayyadina")
class SayyadinaAbility(DeferredAbility):
    """``ability.activated.ix.sayyadina`` (Sayyadina's Agent box:
    pay 3 water for a victory point). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost``:
    ``HasResources.AtLeast(Water, 3)``.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SayyadinaAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: at least 3 water."""

        return p.ctx.me.resources.water >= 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SayyadinaAbility.ValueForPlayer``.

        With 3 or more water (``EntityExtensions.Water(P)``): "Sayyadina -3 Water" =
        ``GetWaterValue(1) * 3.0`` (f64 literal; added as compiled, positive, despite
        its label) and "Sayyadina VP" = ``GetVictoryPointValue(1)``.
        """

        v = Summer()
        if p.ctx.me.resources.water >= 3:
            v.add("Sayyadina -3 Water", p.water_value(1) * 3.0)
            v.add("Sayyadina VP", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SayyadinaAbility.Evaluate``: 100.0 (f64 literal), no
        sub-target."""

        return Answer(100.0, (), "Sayyadina | 100")


@port(_AA + "shai_hulud")
class ShaiHuludAbility(DeferredAbility):
    """``ability.activated.ix.shai_hulud`` (Shai-Hulud's Agent box:
    trash a card for 2 troops). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost``:
    ``HasTrashableCard``; ``GetUnusualSelections`` (2 supply
    troops) is interface plumbing.

    ``evaluate`` responds ``((card,),)``: the card to trash among
    ``request.infos[0]``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ShaiHuludAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShaiHuludAbility.ValueForPlayer``: "Shai-Hulud Trash" = ``TrashCardValue``,
        "Trash Card Bonus" = ``TrashMod`` and "Shai-Hulud 2 Troops" = ``GetTroopValue(1,
        false)`` added to itself."""

        v = Summer()
        v.add("Shai-Hulud Trash", p.trash_card_value())
        v.add("Trash Card Bonus", p.trash_mod())
        troop = p.troop_value(1, False)
        v.add("Shai-Hulud 2 Troops", troop + troop)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShaiHuludAbility.Evaluate``.

        ``(card, t) = GetCardToTrash(targets, 1.0)``; "Trash Value" = ``t``. Without a
        card the least valuable target is taken instead (``OrderBy(c =>
        c.AcquireValue(P)).First()``; ``AIValueSummer.CompareTo`` = ``Sum``, stable).
        The answer names that card at ``t`` (``UpdateSelectionTargets``); with no target
        at all the app's ``First()`` would throw, ours leaves the choice untouched.
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


@port(_AA + "shai_hulud_acquire")
class ShaiHuludAcquireAbility(AcquireAbility):
    """``ability.activated.ix.shai_hulud_acquire`` (Shai-Hulud's
    acquire effect: trash a card; ``AcquireEffectList [Trash]``, valued by
    ``GetAcquireEffectsValue``). ``GetSourceEntityID``;
    ``Targets`` = ``AcquireAbility.Targets`` then the trash prompt.

    Note: the card also lists the plain ``AcquireAbility``, after this one;
    code that takes a card's first ``AcquireAbility`` port gets this one.

    ``evaluate`` responds ``((card,),)``: the card to trash."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShaiHuludAcquireAbility.Evaluate`` (replaces
        ``AcquireAbility``'s): ``GetCardToTrash(targets.OfType<
        ImperiumPlayable>(), 1.0)``; a found card at its trash value
        (``UpdateSelectionTargets``), else the untouched choice."""

        card, value = p.card_to_trash(_cards(request), 1.0)
        if card is None:
            return Answer(0.0, None, "Shai-Hulud acquire | nothing to trash")
        return Answer(value, ((card.ref,),), f"Shai-Hulud acquire | trash {card.ref}")


# ---------------------------------------------------------------------------
# Treachery's self-trash
# ---------------------------------------------------------------------------


@port(_AA + "treachery_trash_self")
class TreacheryTrashSelfAbility(DeferredAbility):
    """``ability.activated.ix.treachery_trash_self`` (Treachery's
    "trash this card" box). constructor: timing Agent;
    ``SelectionMode``: Explicit; ``Cost`` = NoCostAction
; ``GetUnusualSelections`` (the Baron's Masterstroke
    confirmation) is interface plumbing. ``evaluate`` is ``DeferredAbility``'s
    (its ``DeferValue``, no sub-target)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TreacheryTrashSelfAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT


# ---------------------------------------------------------------------------
# Web of Power
# ---------------------------------------------------------------------------


@port(_AA + "web_of_power_emperor")
class WebOfPowerEmperorAbility(DeferredAbility):
    """``ability.activated.ix.web_of_power_emperor`` (Web of Power's
    Emperor line: 2 Solari with Emperor influence 2). constructor:
    timing Agent (``HideInvalidDeferred``); ``SelectionMode``:
    Explicit; ``AlwaysRunImmediately`` = true; ``Cost``
: ``HasFactionInfluence.AtLeast(Emperor, 2)``. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WebOfPowerEmperorAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Emperor influence 2."""

        return _influence(p, _EMPEROR) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WebOfPowerEmperorAbility.ValueForPlayer``: with Emperor
        influence at 2 or more, ``GetSolariValue(2)`` as "Web Of Power Emperor
        Solari"."""

        v = Summer()
        if _influence(p, _EMPEROR) >= 2:
            v.add("Web Of Power Emperor Solari", p.solari_value(2))
        return v


@port(_AA + "web_of_power_spacing_guild")
class WebOfPowerSpacingGuildAbility(DrawAbility):
    """``ability.activated.ix.web_of_power_spacing_guild`` (Web of
    Power's Spacing Guild line: draw a card with Spacing Guild influence 2).
    constructor (the ``DrawAbility`` constructor); only ``Cost`` is overridden:
    V/E are ``DrawAbility``'s (V gated on this cost)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasFactionInfluence.AtLeast(SpacingGuild,
        2)`` then ``HasDrawableCard``."""

        return _influence(p, _SPACING_GUILD) >= 2 and _has_drawable_card(p)


@port(_AA + "web_of_power_fremen")
class WebOfPowerFremenAbility(DeferredAbility):
    """``ability.activated.ix.web_of_power_fremen`` (Web of Power's
    Fremen line: a water with Fremen influence 2). constructor:
    timing Agent (``HideInvalidDeferred``); ``SelectionMode``:
    Explicit; ``AlwaysRunImmediately`` = true; ``Cost``
: ``HasFactionInfluence.AtLeast(Fremen, 2)``. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WebOfPowerFremenAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Fremen influence 2."""

        return _influence(p, _FREMEN) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WebOfPowerFremenAbility.ValueForPlayer``: with Fremen
        influence at 2 or more, ``GetWaterValue(1)`` as "Web Of Power Fremen
        Water"."""

        v = Summer()
        if _influence(p, _FREMEN) >= 2:
            v.add("Web Of Power Fremen Water", p.water_value(1))
        return v


@port(_AA + "web_of_power_reveal")
class WebOfPowerRevealAbility(GainAnyInfluenceAbility):
    """``ability.activated.ix.web_of_power_reveal`` (Web of Power's
    Reveal: an influence on any track). constructor: timing Reveal;
    ``LoggingMode`` is logging only: V/E and
    ``SelectionMode`` are ``GainAnyInfluenceAbility``'s (Explicit; the best
    faction track, response ``((track,),)``)."""

    timing: ClassVar[Timing] = Timing.REVEAL


# ---------------------------------------------------------------------------
# Weirding Way
# ---------------------------------------------------------------------------


@port(_AA + "weirding_way")
class WeirdingWayAbility(DeferredAbility):
    """``ability.activated.ix.weirding_way`` (Weirding Way's Agent
    box: a choose-one prompt). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost`` = NoCostAction
.

    ``evaluate`` responds ``((0,),)`` or ``((1,),)`` (``IntTargetResponse``)
    at 1.0."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WeirdingWayAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WeirdingWayAbility.ValueForPlayer``: with the lower
        ``ConflictPostureBounds`` at or above ``CurrentConflictInterest().Sum`` (skips;
        NaN skips), ``WeirdingWayValue`` as "Weirding Way"."""

        v = Summer()
        interest = p.current_conflict_interest().sum
        lower, _upper = p.conflict_posture_bounds()
        if lower >= interest:
            v.add("Weirding Way", p.C.WeirdingWayValue)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WeirdingWayAbility.Evaluate``: option 1 when the lower
        ``ConflictPostureBounds`` is at or above the conflict interest, else option 0
        (NaN: 0); value 1.0 (f64 literal)."""

        interest = p.current_conflict_interest().sum
        lower, _upper = p.conflict_posture_bounds()
        option = 1 if lower >= interest else 0
        return Answer(1.0, ((option,),), f"Weirding Way | {option}")


@port(BOUNDLESS_AMBITION_CUSTOM)
class BoundlessAmbitionCustomAbility(DeferredAbility):
    """``ability.play.promo.boundless_ambition_custom``: the "acquire a
    card that costs 5 or less" that Boundless Ambition's Reveal
    (``BoundlessAmbitionRevealAbility.BeginExecution``:
    ``GainCustomAbility``) and its Unload
    (``BoundlessAmbitionUnloadAbility.BeginExecution``:
    ``AddCustomAbility``) grant the player.

    ``Targets``: ``MakeAcquireImperiumRowCardTargeting(maxCost 5,
    includeReserved, includeCanTopOfDeck)``: ``request.infos[0]`` the Row
    then Reserve cards, ``infos[1]`` the destination picker.
    ``evaluate`` responds ``((card,), (0,))``."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SelectionMode``: Optional (``return 0``)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasImperiumRowCardWithPersuasionCostLessThan
        (6)`` and ``HasCustomAbility``: a Row card (never the Reserve) of cost
        5 or less."""

        return any(
            card_entity(ref).int_attr("PersuasionCost", 0) < 6
            for ref in p.ctx.imperium_row
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: the base summer plus, for the row card
        ``MaxByOrElse(AcquireValue(P).Sum)`` among
        ``ImperiumRowCards.OfType<ImperiumPlayable>().Where(...)`` (``PersuasionCost <
        6``), its ``AcquireValue`` ("Boundless Ambition Acquire <card>"); none, nothing.
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
        """``Evaluate``: each card target
        (``GetTargets().OfType<ImperiumPlayable>()``) at
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
