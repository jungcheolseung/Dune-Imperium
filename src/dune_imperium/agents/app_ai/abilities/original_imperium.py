"""The original game's Imperium cards and the base-game promos: their ability classes.

Ports of the original game's card classes (base set and promos) the Uprising deck does
not use; each follows the app's AI for that class, and the detailed notes are kept
privately (``docs/app-ai-plan.md`` §12).

App class chains of the new classes:

- ``PlayAbilities.AgentAbility`` <- ``CarryAllAgentAbility``,
  ``GunThopterAgentAbility``, ``GeneManipulationAbility``,
  ``KwisatzHaderachAbility``, ``ReverendMotherMohiamAbility``,
  ``TestOfHumanityAbility``;
- ``PlayAbilities.RevealAbility`` <- ``BeneGesseritSisterRevealAbility``,
  ``FedaykinDeathCommandoRevealAbility``, ``FirmGripRevealAbility``,
  ``GuildBankersAbility`` (the Guild Bankers' only Reveal box),
  ``SietchReverendMotherRevealAbility``, ``WormRidersRevealAbility``;
- ``TriggeredAbilities.BondAbility`` <- ``FedaykinDeathCommandoAbility``,
  ``SietchReverendMotherAbility``, ``SpiceHunterAbility``;
  ``TriggeredAbilities.AllianceAbility`` <- ``FirmGripAbility2``,
  ``WormRidersAllianceAbility``; ``TriggeredAbilities.TriggeredAbility`` <-
  ``AssassinationMissionAbility``, ``WormRidersInfluenceAbility``;
- ``ActivatedAbilities.OptionalRetreatAbility`` <- ``ScoutAbility``,
  ``ChaniRevealAbility``, ``Promo.DuncanLoyalBladeRetreatAbility``;
  ``ActivatedAbilities.DeployUnitsAbility`` <-
  ``Promo.DuncanLoyalBladeDeployAbility``;
  ``ActivatedAbilities.AcquireAbility`` <- ``ChoamDirectorshipAcquireAbility``,
  ``LadyJessicaAcquireAbility``; ``ActivatedAbilities.GainAnyInfluenceAbility``
  <- ``MissionariaProtectivaAbility``; the rest derive from
  ``ActivatedAbilities.DeferredAbility`` directly.

Request / answer encoding (``abilities/base``, as in ``generic.py``): the
candidates of a prompt are ``request.infos[i]`` in the order the app's
``Targets`` yields its target infos (``entities`` for entity targets,
``options`` for custom choices and for troops, one index per troop).
``Answer.response is None`` = nothing stored (the app's untouched choice,
value 0); ``()`` = "use this ability" with no sub-targets
(``UpdateSelectionTargets(v, src, null)`` or an empty response array);
``((ref, ...), ...)`` = the chosen refs / option indices per target info.
Each class docstring says what its ``evaluate`` response encodes.

"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AcquireAbility,
    AgentAbility,
    BondAbility,
    DeferredAbility,
    DeployUnitsAbility,
    GainAnyInfluenceAbility,
    RevealAbility,
    SpaceAbility,
    TriggeredAbility,
    _targets,
    bg_played_pile_value,
    card_factions,
    collect_first,
    find_space,
    gain_any_influence_value,
)
from dune_imperium.agents.app_ai.abilities.immortality import (
    SpaceCache,
    valid_space_ids,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    _Choice,
    _conflict_units,
    _dmax,
    _hand,
    _has_faction,
    _in_play,
)
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    card_entity,
    conflict_entity,
    is_board_space,
    space_entity,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.leader_abilities import units_deployment_blocked

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_PA = "ability.play.original."
_AA = "ability.activated.original."
_TA = "ability.triggered.original."
_PROMO = "ability.activated.promo."

# ``Factions`` enum: None 0, Emperor 1, SpacingGuild 2, BeneGesserit 3, Fremen 4.
# ``GetGainInfluenceValue`` and ``InAlliance`` take our faction ids.
_EMPEROR = "emperor"
_SPACING_GUILD = "spacing_guild"
_BENE_GESSERIT = "bene_gesserit"
_FREMEN = "fremen"
_APP_TO_FACTION = {app: ours for ours, app in FACTION_NAMES.items()}


# ---------------------------------------------------------------------------
# Honest reads (AppContext rules) and small app helpers
# ---------------------------------------------------------------------------


def _in_alliance(p: Profile, faction: str) -> bool:
    """``Player.InAlliance(faction)``: the seat holds that
    faction's Alliance token."""

    return faction in p.ctx.me.alliance_faction_ids


def _other_own_card_with(p: Profile, owner: Entity, faction: str) -> bool:
    """The shared test of the Fremen bond classes (``ValueForPlayer``
    of ``FedaykinDeathCommandoAbility``,
    ``SietchReverendMotherAbility``, ``SpiceHunterAbility``
): another card of the player's hand or play area (the ``Concat``
    of ``AllCardsInPlay`` and the hand) whose ``FactionsList`` holds ``faction`` (app
    name); the card itself is skipped."""

    others = (*_hand(p), *_in_play(p))
    return any(c.ref != owner.ref and _has_faction(c, faction) for c in others)


def _deployed_units(p: Profile) -> int:
    """``GetPlayerDeployed(P).children.Count``: every unit P has in the
    Conflict (``P.ConflictUnits``)."""

    return _conflict_units(p)


def _retreat_pressure(p: Profile) -> int:
    """The test shared by Chani's Reveal and Duncan's Loyal Blade (``Chani``
    ``ValueForPlayer``, ``DuncanLoyalBlade``): with at least 3 units in the Conflict and
    more than half of the opponents estimated no stronger than P (``OpponentRatio(o =>
    EstOpponentStrength(o).Sum <= estStrength) > 0.5``, f64 0.5, strict), the number of
    units in the Conflict; else 0 (a ``double``)."""

    n = _deployed_units(p)
    if n < 3:
        return 0
    strength = p.est_strength().sum  # the closure's ``estStrength``
    ratio = p.opponent_ratio(
        lambda o: p.est_opponent_strength(o.player_id).sum <= strength
    )
    return n if ratio > 0.5 else 0


def _troop_slots(info: TargetInfo) -> tuple[str | int, ...]:
    """The troop prompt of ``OptionalRetreatAbility.Targets``: one slot per
    troop P has in the Conflict. Our troops are anonymous, so the window
    offers them as ``options`` (one index per troop, as for
    ``DeployUnitsAbility``); entity refs are accepted as well."""

    return info.options or tuple(e.ref for e in info.entities)


# ---------------------------------------------------------------------------
# Optional retreat: Scout, Chani, Duncan Idaho Loyal Blade
# ---------------------------------------------------------------------------


@port("ability.activated.optional_retreat")
class OptionalRetreatAbility(DeferredAbility):
    """``ActivatedAbilities.OptionalRetreatAbility``: retreat troops from the
    Conflict (Scout, Chani's Reveal, Duncan's retreat).

    ``evaluate`` responds ``((slot, ...),)``: the first ``n`` troop slots of
    ``request.infos[0]`` (``options``: one index per troop P has in the
    Conflict), ``n = GetTroopsToRetreat(NumberToSelect)``.
    """

    #: ``MaxRetreat``: abstract; -1 = every troop.
    MAX_RETREAT: ClassVar[int] = -1

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``OptionalRetreatAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``OptionalRetreatAbility.Cost``:
        ``HasUnitsDeployed<Troop>.Any``: a troop in the Conflict."""

        return p.conflict_troop_count() > 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OptionalRetreatAbility.Evaluate``.

        The first target info is the troop prompt (``Targets``:
        the troops P has in the Conflict; ``NumberToSelect`` = ``MaxRetreat``
        when positive, else the number of those troops). ``n =
        GetTroopsToRetreat(NumberToSelect)``; with ``n > 0`` the first ``n``
        entities at value 1.0 (f64 literal), else the untouched choice.
        """

        if not request.infos:
            return Answer(0.0, None, f"{type(self).__name__} no target info")
        slots = _troop_slots(request.infos[0])
        number = self.MAX_RETREAT if self.MAX_RETREAT > 0 else p.conflict_troop_count()
        n = p.troops_to_retreat(number)
        if n <= 0:
            return Answer(0.0, None, f"{type(self).__name__} keep troops")
        return Answer(
            1.0, (tuple(slots[:n]),), f"{type(self).__name__} | retreat {n} | 1.0"
        )


@port(_AA + "scout")
class ScoutAbility(OptionalRetreatAbility):
    """``ability.activated.original.scout`` (Scout's Reveal: retreat up
    to 2 troops). constructor: timing Reveal; ``MaxRetreat``
 = 2. ``evaluate``: ``OptionalRetreatAbility``'s."""

    timing: ClassVar[Timing] = Timing.REVEAL
    MAX_RETREAT: ClassVar[int] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ScoutAbility.ValueForPlayer``.

        ``Math.Min(units in the Conflict * 0.5, 1.0)`` (f64 literals) as
        "Scout Troop Retreat Bonus": no test of the situation.
        """

        v = Summer()
        v.add("Scout Troop Retreat Bonus", min(_deployed_units(p) * 0.5, 1.0))
        return v


@port(_AA + "chani_reveal")
class ChaniRevealAbility(OptionalRetreatAbility):
    """``ability.activated.original.chani_reveal`` (Chani's Reveal:
    retreat any number of troops). constructor: timing Reveal;
    ``MaxRetreat`` = -1. ``evaluate``:
    ``OptionalRetreatAbility``'s."""

    timing: ClassVar[Timing] = Timing.REVEAL
    MAX_RETREAT: ClassVar[int] = -1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ChaniRevealAbility.ValueForPlayer``: the units in
        the Conflict as "Chani Troop Retreat Bonus" under
        ``_retreat_pressure``'s test (3+ units, most opponents no stronger)."""

        v = Summer()
        bonus = _retreat_pressure(p)
        if bonus > 0:
            v.add("Chani Troop Retreat Bonus", float(bonus))
        return v


@port(_PROMO + "duncan_loyal_blade_retreat")
class DuncanLoyalBladeRetreatAbility(OptionalRetreatAbility):
    """``ability.activated.promo.duncan_loyal_blade_retreat``: the retreat
    half of Duncan Idaho, Loyal Blade (run by ``DuncanLoyalBladeAbility``).
    constructor: timing Reveal; ``MaxRetreat`` = -1;
    ``Cost`` is the constant ``(false, match)``: never payable on
    its own."""

    timing: ClassVar[Timing] = Timing.REVEAL
    MAX_RETREAT: ClassVar[int] = -1

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``ValueTuple<bool, Match>(false, match)``."""

        return False


@port(_PROMO + "duncan_loyal_blade_deploy")
class DuncanLoyalBladeDeployAbility(DeployUnitsAbility):
    """``ability.activated.promo.duncan_loyal_blade_deploy``: the deploy
    half of Duncan Idaho, Loyal Blade. constructor: timing Reveal;
    ``Cost`` is the constant ``(false, match)``: never payable on
    its own; ``Targets`` only builds the deploy prompt."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``ValueTuple<bool, Match>(false, match)``."""

        return False


@port(_PROMO + "duncan_loyal_blade")
class DuncanLoyalBladeAbility(DeferredAbility):
    """``ability.activated.promo.duncan_loyal_blade`` (Duncan Idaho,
    Loyal Blade's Reveal: deploy OR retreat; the "AOrB" prompt).
    constructor: timing Reveal; ``SelectionMode``:
    Optional; ``Cost``: a garrisoned or a deployed troop.

    ``evaluate`` responds ``((0,),)`` to deploy, ``((1,),)`` to retreat (the
    ``IntTargetResponse`` of the choose-one prompt), ``()`` to decline at value
    0 and ``None`` never.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DuncanLoyalBladeAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasUnitsGarrisoned<Troop>.Any`` or
        ``HasUnitsDeployed<Troop>.Any``."""

        return p.garrison_troop_count() > 0 or p.conflict_troop_count() > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DuncanLoyalBladeAbility.ValueForPlayer``.

        ``Math.Max(DeployValue(owner), retreat)`` as "Duncan Loyal Blade
        value", ``retreat`` = the units in the Conflict under
        ``_retreat_pressure``'s test (the Chani condition), else 0.0.
        """

        v = Summer()
        v.add(
            "Duncan Loyal Blade value",
            _dmax(p.deploy_value(self.owner), float(_retreat_pressure(p))),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DuncanLoyalBladeAbility.Evaluate``.

        Deploy (option 0, value 100.0) when P has a garrison troop and
        ``CanDeploy`` and ``GetUnitsToDeploy(GetNextGarrisonTroops(12), -1)``
        is not empty; else retreat (option 1, value 100.0) when a troop is in
        the Conflict and ``GetTroopsToRetreat(those troops) > 0``; else an
        empty response at 0.0.
        """

        garrison = p.garrison_troop_count()
        if (
            garrison > 0
            and not units_deployment_blocked(p.ctx.state, p.ctx.seat)  # CanDeploy
            and p.units_to_deploy(min(12, garrison), -1) > 0
        ):
            return Answer(100.0, ((0,),), "Duncan Loyal Blade | Deploy | 100")
        deployed = p.conflict_troop_count()
        if deployed > 0 and p.troops_to_retreat(deployed) > 0:
            return Answer(100.0, ((1,),), "Duncan Loyal Blade| Retreat | 100")
        return Answer(0.0, (), "Duncan Loyal Blade | nothing")


# ---------------------------------------------------------------------------
# Triggered abilities: Alliance base, Worm Riders, Assassination Mission
# ---------------------------------------------------------------------------


@port("ability.triggered.alliance")
class AllianceAbility(TriggeredAbility):
    """``TriggeredAbilities.AllianceAbility`` (abstract; Firm Grip, Worm
    Riders): fires on the Alliance holder's Reveal.

    Subclasses set ``alliance_faction`` (``AllianceFaction``;
    app faction) and their own V. ``IsValidFor`` is engine-side;
    ``ValueInPileForOtherPlay`` is not overridden (the default tag synergy).
    """

    alliance_faction: ClassVar[str | None] = None  # abstract in the app
    should_exhaust: ClassVar[bool] = False


@port(_PA + "firm_grip_ability2")
class FirmGripAbility2(AllianceAbility):
    """``ability.play.original.firm_grip_ability2`` (Firm Grip's Emperor
    Alliance). constructor: timing Reveal; ``AllianceFaction``
 = Emperor; ``Cost`` = NoCostAction."""

    timing: ClassVar[Timing] = Timing.REVEAL
    alliance_faction: ClassVar[str | None] = _EMPEROR

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FirmGripAbility2.ValueForPlayer``: in the Emperor
        Alliance, ``GetPersuasionValue(4)`` as "Firm Grip Persuasion"."""

        v = Summer()
        if _in_alliance(p, _EMPEROR):
            v.add("Firm Grip Persuasion", p.persuasion_value(4))
        return v


@port(_PA + "worm_riders_alliance")
class WormRidersAllianceAbility(AllianceAbility):
    """``ability.play.original.worm_riders_alliance`` (Worm Riders'
    Fremen Alliance). constructor: timing Reveal;
    ``AllianceFaction`` = Fremen; ``Cost`` = NoCostAction."""

    timing: ClassVar[Timing] = Timing.REVEAL
    alliance_faction: ClassVar[str | None] = _FREMEN

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WormRidersAllianceAbility.ValueForPlayer``: in the
        Fremen Alliance, ``WormRidersAllianceRevealBonus`` as "Worm Riders
        Alliance Bonus"."""

        v = Summer()
        if _in_alliance(p, _FREMEN):
            v.add("Worm Riders Alliance Bonus", p.C.WormRidersAllianceRevealBonus)
        return v


@port(_TA + "worm_riders_influence")
class WormRidersInfluenceAbility(TriggeredAbility):
    """``ability.triggered.original.worm_riders_influence`` (Worm Riders'
    Fremen influence line). constructor: timing Reveal;
    ``ShouldExhaust`` = false; ``IsValidFor`` and
    ``Cost`` (NoCostAction) are engine-side."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WormRidersInfluenceAbility.ValueForPlayer``: with Fremen influence at 2 or
        more, ``WormRidersInfluenceRevealBonus`` as "Worm Riders Influence Bonus"."""

        v = Summer()
        if p.ctx.me.influence.fremen >= 2:
            v.add("Worm Riders Influence Bonus", p.C.WormRidersInfluenceRevealBonus)
        return v


@port(_TA + "assassination_mission")
class AssassinationMissionAbility(TriggeredAbility):
    """``ability.triggered.original.assassination_mission`` (Assassination
    Mission: the trash trigger). constructor stores no timing;
    ``ShouldExhaust`` = false; ``IsValidFor``, ``Cost``
    (NoCostAction) and ``BeginExecution`` are engine-side: no AI hook."""

    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Reveal boxes that only change the Reveal preview (Persuasion forecast)
# ---------------------------------------------------------------------------


@port(_PA + "bene_gesserit_sister_reveal")
class BeneGesseritSisterRevealAbility(RevealAbility):
    """``ability.play.original.bene_gesserit_sister_reveal`` (Bene Gesserit
    Sister's Reveal box). constructor: timing Reveal;
    ``GetRevealPreviewValue`` answers ``{OptionalPersuasion: 2,
    OptionalStrength: 2}`` (no ``Persuasion`` key: 0 in the forecast, see
    ``profile/economy._reveal_preview_value``). The AI value is the generic
    ``RevealAbility`` one."""


@port(_PA + "firm_grip_reveal")
class FirmGripRevealAbility(RevealAbility):
    """``ability.play.original.firm_grip_reveal`` (Firm Grip's Reveal box).
    constructor: timing Reveal; ``GetRevealPreviewValue``
    answers ``{Persuasion: 4 in the Emperor Alliance, else 0}`` (read by
    ``profile/economy._reveal_preview_value``). The AI value is the generic
    ``RevealAbility`` one."""


@port(_PA + "worm_riders_reveal")
class WormRidersRevealAbility(RevealAbility):
    """``ability.play.original.worm_riders_reveal`` (Worm Riders' Reveal
    box). constructor: timing Reveal; ``GetRevealPreviewValue``
 answers only ``{Strength: ...}`` (no ``Persuasion`` key: 0 in
    the forecast). The AI value is the generic ``RevealAbility`` one."""


@port(_PA + "fedaykin_death_commando_reveal")
class FedaykinDeathCommandoRevealAbility(RevealAbility):
    """``ability.play.original.fedaykin_death_commando_reveal``
    (Fedaykin Death Commando's Reveal box). constructor: timing
    Reveal; ``GetRevealPreviewValue`` answers ``{Persuasion: 1,
    Strength: 3 with another own Fremen card}`` (the forecast reads the literal
    1). The AI value is the generic ``RevealAbility`` one."""


@port(_PA + "sietch_reverend_mother_reveal")
class SietchReverendMotherRevealAbility(RevealAbility):
    """``ability.play.original.sietch_reverend_mother_reveal`` (Sietch
    Reverend Mother's Reveal box). constructor: timing Reveal;
    ``GetRevealPreviewValue`` answers ``{Persuasion: 3 with another
    own Fremen card, else 0}`` (read by ``profile/economy``). The AI value is
    the generic ``RevealAbility`` one."""


@port(_PA + "guild_bankers")
class GuildBankersAbility(RevealAbility):
    """``ability.play.original.guild_bankers`` (Guild Bankers' Reveal
    box; the card has no generic ``RevealAbility``). constructor:
    timing Reveal; ``BeginExecution`` / ``Undo`` are engine-side."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildBankersAbility.ValueForPlayer``.

        ``RevealAbility.ValueForPlayer``, then, when a one-step advance on both
        the Spacing Guild and the Emperor track is worth less than the f64
        literal 1.25 (``GetGainInfluenceValue(F, 1, -1, false).Sum``, both
        strict), ``+ 5.0`` as "Guild Bankers Faction Influence".
        """

        v = super().value_for_player(p, with_entities)
        guild = p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum
        emperor = p.gain_influence_value(_EMPEROR, 1, -1, False).sum
        if 1.25 > guild and 1.25 > emperor:
            v.add("Guild Bankers Faction Influence", 5.0)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``GuildBankersAbility.ValueInPileForOtherPlay``: the
        empty ``DefaultValueSummer`` (the default tag synergy is skipped)."""

        return Summer()


# ---------------------------------------------------------------------------
# Fremen bonds: Fedaykin Death Commando, Sietch Reverend Mother, Spice Hunter
# ---------------------------------------------------------------------------


@port(_PA + "fedaykin_death_commando")
class FedaykinDeathCommandoAbility(BondAbility):
    """``ability.play.original.fedaykin_death_commando`` (Fedaykin Death
    Commando's Fremen bond). constructor: timing Reveal;
    ``BondFaction`` = Fremen; ``Cost`` = NoCostAction. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FedaykinDeathCommandoAbility.ValueForPlayer``.

        Another Fremen card in hand or in play -> ``GetStrengthValue(1,
        false) * 3.0`` (f64 literal) as "Fedaykin Death Commando Strength".
        """

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add("Fedaykin Death Commando Strength", p.strength_value(1, False) * 3.0)
        return v


@port(_PA + "sietch_reverend_mother")
class SietchReverendMotherAbility(BondAbility):
    """``ability.play.original.sietch_reverend_mother`` (Sietch Reverend
    Mother's Fremen bond). constructor: timing Reveal;
    ``BondFaction`` = Fremen; ``Cost`` = NoCostAction. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SietchReverendMotherAbility.ValueForPlayer``.

        Another Fremen card in hand or in play -> ``GetPersuasionValue(3) +
        GetSpiceValue(1)`` as "Sietch Reverend Mother Resources".
        """

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add(
                "Sietch Reverend Mother Resources",
                p.persuasion_value(3) + p.spice_value(1),
            )
        return v


@port(_PA + "spice_hunter")
class SpiceHunterAbility(BondAbility):
    """``ability.play.original.spice_hunter`` (Spice Hunter's Fremen
    bond). constructor: timing Reveal; ``BondFaction``
    = Fremen; ``Cost`` = NoCostAction. P is the inherited ``BondAbility``
    synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceHunterAbility.ValueForPlayer``: another Fremen
        card in hand or in play -> ``GetSpiceValue(1)`` as "Spice Hunter
        Resources"."""

        v = Summer()
        if _other_own_card_with(p, self.owner, "Fremen"):
            v.add("Spice Hunter Resources", p.spice_value(1))
        return v


# ---------------------------------------------------------------------------
# Agent boxes: Carryall, Gun Thopter
# ---------------------------------------------------------------------------


@port(_PA + "carry_all_agent")
class CarryAllAgentAbility(AgentAbility):
    """``ability.play.original.carry_all_agent`` (Carryall's Agent box:
    the card has no generic ``AgentAbility``). constructor: timing
    Agent; ``evaluate``: ``AgentAbility``'s (response: the best space)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CarryAllAgentAbility.ValueForPlayer``.

        ``AgentAbility.ValueForPlayer``, then, for a space among
        ``with_entities`` (``OfType<Space>().FirstOrDefault()``), the
        extra spice the card doubles: ``GetSpiceValue(2 * s) -
        GetSpiceValue(s)`` as "Carryall Bonus Spice", ``s`` the space's printed
        ``Spice`` (``EntityExtensions.Spice``, without bonus spice).
        """

        v = super().value_for_player(p, with_entities)
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None:
            spice = space.int_attr("Spice")
            v.add(
                "Carryall Bonus Spice",
                p.spice_value(spice + spice) - p.spice_value(spice),
            )
        return v


@port(_PA + "gun_thopter_agent")
class GunThopterAgentAbility(AgentAbility):
    """``ability.play.original.gun_thopter_agent`` (Gun Thopter's Agent
    box: the opponent's garrison troop it removes). Only ``RunImmediateEffects``
    and ``Undo`` are overridden (engine-side): ``evaluate`` and
    ``value_for_player`` are ``AgentAbility``'s."""


@port(_AA + "gun_thopter_reveal")
class GunThopterRevealAbility(DeferredAbility):
    """``ability.activated.original.gun_thopter_reveal`` (Gun Thopter's
    Reveal: deploy a troop). constructor: timing Reveal;
    ``SelectionMode``: Optional; ``Cost``: a unit can be
    deployed (``CanDeployUnits``) and a troop is garrisoned.

    ``evaluate`` responds ``()`` ("do deploy") at 100.0 or ``None``.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GunThopterRevealAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``CanDeployUnits`` (``P.CanDeploy``) then
        ``HasUnitsGarrisoned<Troop>.Any``."""

        return (
            not units_deployment_blocked(p.ctx.state, p.ctx.seat)
            and p.garrison_troop_count() > 0
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GunThopterRevealAbility.ValueForPlayer``.

        With ``n`` the opponents that have a troop in the Conflict
        (``ConflictTroops > 0``, ``ValueForPlayer``): ``0.0``
        when ``n < 1``, else ``a / n + a / n`` with ``a`` all opponents, as
        "Gun Thopter Reveal Bonus" (the same quotient twice, as compiled); then,
        with a garrisoned troop, ``GunThopterTroopRevealBonus`` as "Gun
        Thopter Troop Reveal Bonus".
        """

        v = Summer()
        opponents = p.ctx.opponents
        n = sum(1 for o in opponents if p.conflict_troop_count(o) > 0)
        if n < 1:
            bonus = 0.0
        else:
            bonus = len(opponents) / n + len(opponents) / n
        v.add("Gun Thopter Reveal Bonus", bonus)
        if p.garrison_troop_count() > 0:
            v.add("Gun Thopter Troop Reveal Bonus", p.C.GunThopterTroopRevealBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GunThopterRevealAbility.Evaluate``.

        ``GetUnitsToDeploy(GetNextTroops(1), -1)`` (one troop of the supply)
        not empty -> 100.0 (f64 literal) with no sub-target; else the untouched
        choice.
        """

        supply = min(1, p.ctx.me.troops_supply)
        if p.units_to_deploy(supply, -1) > 0:
            return Answer(100.0, (), "Gun Thopter (Reveal) | toDeploy | 100")
        return Answer(0.0, None, "Gun Thopter (Reveal) | nothing to deploy")


# ---------------------------------------------------------------------------
# Spice Smugglers
# ---------------------------------------------------------------------------


@port(_AA + "spice_smugglers")
class SpiceSmugglersAbility(DeferredAbility):
    """``ability.activated.original.spice_smugglers`` (Spice Smugglers'
    Agent box: pay 2 spice for a Spacing Guild influence and 3 Solari).
    constructor: timing Agent; ``SelectionMode``:
    Optional; ``Cost``: ``HasResources.AtLeast(Spice, 2)``.

    ``evaluate`` responds ``()`` ("pay") at the summed value."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SpiceSmugglersAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: at least 2 spice."""

        return p.ctx.me.resources.spice >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceSmugglersAbility.ValueForPlayer``.

        Space among ``with_entities``: when ``CanAgentAbilityBePlayedWithSpace(
        space, Spice, 2)`` is false only a 0.0 term (a debug label) and no value.
        Else "Spice Smugglers Spice Cost" = ``GetSpiceValue(1) * -2.0`` (f64
        literal), "Spice Smugglers Influence" = ``GetGainInfluenceValue(
        SpacingGuild, 1, -1, false).Sum`` and "Spice Smugglers Solari" =
        ``GetSolariValue(3)``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 2
        ):
            v.add(
                f"Spice Smugglers Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return v
        v.add("Spice Smugglers Spice Cost", p.spice_value(1) * -2.0)
        v.add(
            "Spice Smugglers Influence",
            p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum,
        )
        v.add("Spice Smugglers Solari", p.solari_value(3))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpiceSmugglersAbility.Evaluate``: ``GetSpiceValue(-2)``
        ("Spice Cost") + the Spacing Guild influence + ``GetSolariValue(3)``,
        the sum as the value; no sub-target."""

        v = Summer()
        v.add("Spice Cost", p.spice_value(-2))
        v.add("Influence", p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum)
        v.add("Solari", p.solari_value(3))
        return Answer(v.sum, (), f"Spice Smugglers | {v.sum}")


# ---------------------------------------------------------------------------
# Bene Gesserit Sister
# ---------------------------------------------------------------------------


@port(_AA + "bene_gesserit_sister")
class BeneGesseritSisterAbility(DeferredAbility):
    """``ability.activated.original.bene_gesserit_sister`` (Bene Gesserit
    Sister's Reveal: 2 Persuasion OR 2 Strength, the "AOrB" prompt).
    constructor: timing Reveal; ``SelectionMode``:
    Explicit; ``Cost`` = NoCostAction.

    ``evaluate`` responds ``((0,),)`` for the Persuasion and ``((1,),)`` for the
    Strength option (``IntListTargetResponse``), always at 50.0.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BeneGesseritSisterAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeneGesseritSisterAbility.ValueForPlayer``:
        ``Math.Max(GetPersuasionValue(2), GetStrengthValue(1, false) * 2)``
        (the strength added to itself) as "Bene Gesserit Sister Resource"."""

        v = Summer()
        strength = p.strength_value(1, False)
        v.add(
            "Bene Gesserit Sister Resource",
            _dmax(p.persuasion_value(2), strength + strength),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BeneGesseritSisterAbility.Evaluate``.

        ``rcv = RelativeConflictValue(false).Sum``; ``diff = EstStrength -
        max(EstOpponentStrength)`` (0 without opponents). Persuasion (0)
        without a unit in the Conflict. Else Strength (1) when ``rcv >= 0.9``,
        ``|diff| <= 3`` and ``GetBuyGains(2) <= 2.5``; else Persuasion when
        ``rcv < 1.2`` or ``|diff| > 5``; else Strength. f64 literals 0.9, 2.5,
        1.2; value 50.0 either way (``UpdateSelectionResponses``; a second
        Persuasion update at the same value never replaces the first).
        """

        option = 0
        if p.conflict_unit_count() > 0:
            rcv = p.relative_conflict_value().sum
            diff = p.est_strength().sum - max(
                (p.est_opponent_strength(o.player_id).sum for o in p.ctx.opponents),
                default=0,
            )
            if rcv >= 0.9 and abs(diff) <= 3 and 2.5 >= p.buy_gains(2):
                option = 1
            elif rcv < 1.2 or abs(diff) > 5:
                option = 0
            else:
                option = 1
        label = "strength" if option else "persuasion"
        return Answer(50.0, ((option,),), f"Bene Gesserit Sister | {label}")


# ---------------------------------------------------------------------------
# Acquire boxes: CHOAM Directorship, Lady Jessica
# ---------------------------------------------------------------------------


@port(_AA + "choam_directorship_acquire")
class ChoamDirectorshipAcquireAbility(AcquireAbility):
    """``ability.activated.original.choam_directorship_acquire`` (CHOAM
    Directorship: the four-faction acquire effect ``AcquireEffectList``
    ``RankE/RankSG/RankBG/RankF`` priced by ``GetAcquireEffectsValue``).
    ``GetSourceEntityID`` (the card) and ``SetAsideWillClearUndo``
 (engine-side) are the only overrides: ``evaluate`` is
    ``AcquireAbility``'s."""


@port(_AA + "lady_jessica_acquire")
class LadyJessicaAcquireAbility(AcquireAbility):
    """``ability.activated.original.lady_jessica_acquire`` (Lady Jessica:
    the "advance on any track" acquire effect, ``AcquireEffectList`` ``AnyRank``).
    ``Targets``: ``AcquireAbility.Targets`` then a "SelectFaction"
    prompt (``MakeGainAnyFactionInfluenceTargeting``).

    ``evaluate`` responds ``((faction,),)`` (the chosen track entity, one
    target info) or ``((1,), (faction,))`` when ``AcquireAbility`` also
    prompted (two target infos): the value of the best faction.
    """

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LadyJessicaAcquireAbility.Evaluate``.

        For each faction track of the "SelectFaction" target info the value
        ``GetGainInfluenceValue(F, 1, -1, false).Sum``; the first track sticks,
        a later one only when strictly better. (The closing ``rank > 0`` test
 reads the choice's ``AIChoice.rank``, which stays 0, so
        ``SetRank(AcquireValue)`` never runs.)
        """

        choice = _Choice()
        faction_info = next(
            (
                info
                for info in request.infos
                if info.entities and all(e.kind is Kind.TRACK for e in info.entities)
            ),
            None,
        )
        if faction_info is not None:
            for track in faction_info.entities:
                value = p.gain_influence_value(track.ref, 1, -1, False).sum
                if len(request.infos) < 2:
                    response: tuple[tuple[str | int, ...], ...] = ((track.ref,),)
                else:
                    response = ((1,), (track.ref,))
                choice.update(
                    value, response, f"Lady Jessica Acquire Influence | {track.ref}"
                )
        return choice.answer("Lady Jessica Acquire Influence")


# ---------------------------------------------------------------------------
# Spice-for-troops and water-for-draw agent boxes: Fremen Camp, Duncan Idaho
# ---------------------------------------------------------------------------


@port(_AA + "fremen_camp")
class FremenCampAbility(DeferredAbility):
    """``ability.activated.original.fremen_camp`` (Fremen Camp's Agent
    box: pay 2 spice for 3 troops). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost``: at least 2
    spice, then a troop in the supply. ``GetUnusualSelections`` is
    interface plumbing.

    ``evaluate`` responds ``()`` ("pay") at the summed value."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FremenCampAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Spice, 2)`` then
        ``HasUnitsInSupply<Troop>.Any``."""

        me = p.ctx.me
        return me.resources.spice >= 2 and me.troops_supply > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FremenCampAbility.ValueForPlayer``.

        Space among ``with_entities``: when ``CanAgentAbilityBePlayedWithSpace(
        space, Spice, 2)`` is false only a 0.0 term. Else "Fremen Camp Spice
        Cost" = ``GetSpiceValue(1) * -2.0`` (f64 literal) and "Fremen Camp
        Troops" = ``GetTroopValue(3, false)``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 2
        ):
            v.add(
                f"Fremen Camp Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return v
        v.add("Fremen Camp Spice Cost", p.spice_value(1) * -2.0)
        v.add("Fremen Camp Troops", p.troop_value(3, False))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FremenCampAbility.Evaluate``: ``GetSpiceValue(-2)``
        ("Spice Cost") + ``GetTroopValue(3, false)`` ("Troops"); no
        sub-target."""

        v = Summer()
        v.add("Spice Cost", p.spice_value(-2))
        v.add("Troops", p.troop_value(3, False))
        return Answer(v.sum, (), f"Fremen Camp (Agent) | {v.sum}")


@port(_AA + "duncan_idaho")
class DuncanIdahoAbility(DeferredAbility):
    """``ability.activated.original.duncan_idaho`` (Duncan Idaho's Agent
    box: pay 1 water for a troop and a card). constructor: timing
    Agent; ``SelectionMode``: Optional; ``Cost``: at
    least 1 water, then a drawable card or a troop in the supply.

    ``evaluate`` responds ``()`` ("pay") at the summed value."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DuncanIdahoAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Water, 1)`` then
        (``HasDrawableCard`` or ``HasUnitsInSupply<Troop>.Any``)."""

        me = p.ctx.me
        drawable = p.ctx.deck_size + len(me.discard_pile) > 0
        return me.resources.water >= 1 and (drawable or me.troops_supply > 0)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DuncanIdahoAbility.ValueForPlayer``.

        Space among ``with_entities``: when ``CanAgentAbilityBePlayedWithSpace(space,
        Water, 1)`` is false only a 0.0 term. Else "Duncan Idaho Water Cost" =
        ``-GetWaterValue(1)`` (the sign bit flipped), "Duncan Idaho Troops" =
        ``GetTroopValue(1, false)``, "Duncan Idaho Draw" = ``CardDrawValue`` and "Buy
        Gains Bonus" = ``GetBuyGains(PossiblePersuasionGain())``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.WATER, 1
        ):
            v.add(
                f"Duncan Idaho Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return v
        v.add("Duncan Idaho Water Cost", -p.water_value(1))
        v.add("Duncan Idaho Troops", p.troop_value(1, False))
        v.add("Duncan Idaho Draw", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DuncanIdahoAbility.Evaluate``: ``GetWaterValue(-1)``
        ("Water Cost") + ``GetTroopValue(1, false)`` ("Troop") +
        ``CardDrawValue`` ("Card") + ``GetBuyGains(PossiblePersuasionGain())``
        ("Buy Gains Bonus"); no sub-target."""

        v = Summer()
        v.add("Water Cost", p.water_value(-1))
        v.add("Troop", p.troop_value(1, False))
        v.add("Card", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return Answer(v.sum, (), f"Duncan Idaho (Agent) | {v.sum}")


# ---------------------------------------------------------------------------
# Firm Grip's Agent box
# ---------------------------------------------------------------------------


@port(_AA + "firm_grip_agent")
class FirmGripAgentAbility(DeferredAbility):
    """``ability.activated.original.firm_grip_agent`` (Firm Grip's Agent
    box: pay 2 Solari for an influence on a track other than the Emperor).
    constructor: timing Agent; ``SelectionMode``: Optional;
    ``Cost``: at least 2 Solari, then ``CanGainInfluence`` on the
    Spacing Guild, Bene Gesserit or Fremen track; ``Targets`` lists
    the tracks with ``NotEmperorFilter`` (``Faction != Emperor``).

    ``evaluate`` responds ``((track,),)``: the chosen faction track entity (ref
    = our faction id) among ``request.infos[0]``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FirmGripAgentAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FirmGripAgentAbility.ValueForPlayer``.

        Space among ``with_entities``: when ``CanAgentAbilityBePlayedWithSpace(
        space, Solari, 2)`` is false only a 0.0 term. Else "Firm Grip Solari
        Cost" = ``GetSolariValue(-2)`` and "Firm Grip Influence" =
        ``GetGainInfluenceValue(Factions.None, 1, -1, false).Sum`` (the best
        faction, the Emperor included).
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SOLARI, 2
        ):
            v.add(
                f"Firm Grip Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return v
        v.add("Firm Grip Solari Cost", p.solari_value(-2))
        v.add("Firm Grip Influence", gain_any_influence_value(p, 1).sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FirmGripAgentAbility.Evaluate``.

        Only when ``CurrentRound > 3`` or the Swordmaster is held: for each faction
        track of the targets, in order, ``GetGainInfluenceValue(F, 1, -1, false)`` +
        "Static Boost" 100.0; the first track sticks, a later one only when strictly
        better.
        """

        if p.ctx.round_number <= 3 and not p.ctx.me.swordmaster_acquired:
            return Answer(0.0, None, "Firm Grip (Agent) | no Swordmaster yet")
        stored: Answer | None = None
        for track in _targets(request, Kind.TRACK):
            s = Summer()
            s.merge(p.gain_influence_value(track.ref, 1, -1, False))
            s.add("Static Boost", 100.0)
            if stored is None or s.sum > stored.value:
                stored = Answer(
                    s.sum, ((track.ref,),), f"Firm Grip (Agent) | {track.ref}"
                )
        if stored is None:
            return Answer(0.0, None, "Firm Grip (Agent) | no track")
        return stored


# ---------------------------------------------------------------------------
# Gene Manipulation
# ---------------------------------------------------------------------------


@port(_PA + "gene_manipulation")
class GeneManipulationAbility(AgentAbility):
    """``ability.play.original.gene_manipulation`` (Gene Manipulation's
    Agent box: the card has no generic ``AgentAbility``). ``RunImmediateEffects``
 is engine-side; ``evaluate``: ``AgentAbility``'s."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GeneManipulationAbility.ValueForPlayer``.

        ``AgentAbility.ValueForPlayer``, then another Bene Gesserit card in play
        (``AllCardsInPlay.Except(owner)``, ``ValueForPlayer``
) -> ``GetSpiceValue(1)`` added to itself as "Gene
        Manipulation Spice".
        """

        v = super().value_for_player(p, with_entities)
        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        if any(_has_faction(c, "BeneGesserit") for c in others):
            v.add("Gene Manipulation Spice", p.spice_value(1) + p.spice_value(1))
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``GeneManipulationAbility.ValueInPileForOtherPlay``.

        The Bene Gesserit "played" pattern (``bg_played_pile_value``) with
        ``(GetSpiceValue(1) + GetSpiceValue(1)) * 0.75`` (f64 literal) as "Bene
        Gesserit in Play".
        """

        def played() -> float:
            return (p.spice_value(1) + p.spice_value(1)) * 0.75

        return bg_played_pile_value(p, pile, card, played, "Bene Gesserit in Play")


# ---------------------------------------------------------------------------
# Guild Ambassador
# ---------------------------------------------------------------------------


@port(_AA + "guild_ambassador_reveal")
class GuildAmbassadorRevealAbility(DeferredAbility):
    """``ability.activated.original.guild_ambassador_reveal`` (Guild
    Ambassador's Reveal box: the Spacing Guild alliance's spice pay-off).
    constructor: timing Reveal; ``SelectionMode``:
    Optional; ``Cost``: the Spacing Guild Alliance, then at least 3
    spice.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildAmbassadorRevealAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasFactionAlliance(SpacingGuild)`` then
        ``HasResources.AtLeast(Spice, 3)``."""

        return _in_alliance(p, _SPACING_GUILD) and p.ctx.me.resources.spice >= 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildAmbassadorRevealAbility.ValueForPlayer``.

        In the Spacing Guild Alliance, with more than 2 spice
        (``EntityExtensions.Spice(P)``) or at least 2 Agents left (skips):
        ``GuildAmbassadorRevealBonus`` as "Guild Ambassador Reveal Bonus".
        """

        v = Summer()
        me = p.ctx.me
        if _in_alliance(p, _SPACING_GUILD) and (
            me.resources.spice > 2 or me.agents_available >= 2
        ):
            v.add("Guild Ambassador Reveal Bonus", p.C.GuildAmbassadorRevealBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildAmbassadorRevealAbility.Evaluate``: 100.0 (f64
        literal), no sub-target."""

        return Answer(100.0, (), "Guild Ambassador (Reveal) | 100")


@port(_AA + "guild_ambassador_agent")
class GuildAmbassadorAgentAbility(DeferredAbility):
    """``ability.activated.original.guild_ambassador_agent`` (Guild
    Ambassador's Agent box: a Spacing Guild influence OR 2 spice, the "AOrB"
    prompt). constructor: timing Agent; ``SelectionMode``:
    Explicit; ``Cost`` = NoCostAction.

    ``evaluate`` responds ``((0,),)`` for the influence and ``((1,),)`` for the
    spice option (``IntListTargetResponse``)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildAmbassadorAgentAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildAmbassadorAgentAbility.ValueForPlayer``:
        ``Math.Max(GetGainInfluenceValue(SpacingGuild, 1, -1, false).Sum,
        GetSpiceValue(1) * 2)`` (the spice value added to itself) as "Guild
        Ambassador Resource"."""

        v = Summer()
        influence = p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum
        spice = p.spice_value(1)
        v.add("Guild Ambassador Resource", _dmax(influence, spice + spice))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildAmbassadorAgentAbility.Evaluate``.

        Option 0 (influence) at ``GetGainInfluenceValue(SpacingGuild, 1, -1,
        false).Sum``, then option 1 (spice) at ``GetSpiceValue(1) * 2``
        replacing it only when strictly greater."""

        choice = _Choice()
        choice.update(
            p.gain_influence_value(_SPACING_GUILD, 1, -1, False).sum,
            ((0,),),
            "Guild Ambassador (Agent) | influence",
        )
        spice = p.spice_value(1)
        choice.update(spice + spice, ((1,),), "Guild Ambassador (Agent) | Spice Value")
        return choice.answer("Guild Ambassador (Agent)")


# ---------------------------------------------------------------------------
# Imperial Spy, Opulence, Smuggler's Thopter, Sardaukar Legion, Missionaria
# ---------------------------------------------------------------------------


@port(_AA + "imperial_spy")
class ImperialSpyAbility(DeferredAbility):
    """``ability.activated.original.imperial_spy`` (Imperial Spy's Agent
    box: an Intrigue card). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost`` = NoCostAction.

    ``evaluate`` responds ``()`` at ``IntrigueValue`` when it takes the card."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ImperialSpyAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialSpyAbility.ValueForPlayer``.

        ``IntrigueValue`` as "Imperial Spy Intrigue" when the game arc is past
        Early and fewer than 3 Intrigue cards are held, or the arc is Late
        (``GetGameArc() >= 2``).
        """

        v = Summer()
        arc = p.game_arc()
        held = len(p.ctx.intrigue_cards)
        if (arc > 0 and held < 3) or arc >= 2:
            v.add("Imperial Spy Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperialSpyAbility.Evaluate``.

        From round 3 with fewer than 3 Intrigue cards held, or from round 8
        (``CurrentRound``), ``IntrigueValue`` with no sub-target; else the
        untouched choice."""

        rounds = p.ctx.round_number
        held = len(p.ctx.intrigue_cards)
        if (rounds >= 3 and held < 3) or rounds >= 8:
            return Answer(p.intrigue_value(), (), "Imperial Spy | intrigue")
        return Answer(0.0, None, "Imperial Spy | keep")


@port(_AA + "opulence")
class OpulenceAbility(DeferredAbility):
    """``ability.activated.original.opulence`` (Opulence's Reveal box:
    pay 6 Solari for a victory point). constructor: timing Reveal;
    ``SelectionMode``: Optional; ``Cost``: at least 6
    Solari.

    ``evaluate`` responds ``()`` at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``OpulenceAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Solari, 6)``."""

        return p.ctx.me.resources.solari >= 6

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``OpulenceAbility.ValueForPlayer``.

        ``OpulenceRevealBonus`` as "Opulence Reveal" with more than 5 Solari
        (``EntityExtensions.Solari(P)``), or with at least 4 and more than 1 Agent left.
        """

        v = Summer()
        me = p.ctx.me
        solari = me.resources.solari
        if solari > 5 or (solari >= 4 and me.agents_available > 1):
            v.add("Opulence Reveal", p.C.OpulenceRevealBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OpulenceAbility.Evaluate``: 100.0 (f64 literal), no
        sub-target."""

        return Answer(100.0, (), "Opulence | 100")


@port(_AA + "smugglers_thopter")
class SmugglersThopterAbility(DeferredAbility):
    """``ability.activated.original.smugglers_thopter`` (Smuggler's
    Thopter's Agent box: draw a card with Spacing Guild influence 2; the card
    lists the class twice). constructor: timing Agent;
    ``SelectionMode``: Explicit; ``Cost``: Spacing Guild
    influence at least 2, then a drawable card. ``evaluate`` is
    ``DeferredAbility``'s (its ``DeferValue``, no sub-target)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SmugglersThopterAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasFactionInfluence.AtLeast(SpacingGuild,
        2)`` then ``HasDrawableCard``."""

        me = p.ctx.me
        drawable = p.ctx.deck_size + len(me.discard_pile) > 0
        return me.influence.spacing_guild >= 2 and drawable

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SmugglersThopterAbility.ValueForPlayer``: with Spacing Guild influence at 2
        or more, ``CardDrawValue`` as "Smugglers Thopter Draw" and
        ``GetBuyGains(PossiblePersuasionGain())`` as "Buy Gains Bonus"."""

        v = Summer()
        if p.ctx.me.influence.spacing_guild >= 2:
            v.add("Smugglers Thopter Draw", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


@port(_AA + "sardaukar_legion")
class SardaukarLegionAbility(DeferredAbility):
    """``ability.activated.original.sardaukar_legion`` (Sardaukar Legion's
    Reveal box: deploy up to 3 garrison troops). constructor: timing
    Reveal; ``SelectionMode``: Optional; ``Cost``:
    ``CanDeployUnits`` then a garrisoned troop; ``Targets``:
    "ChooseDeployedTroops", the first 3 garrison troops.

    ``evaluate`` responds ``((slot, ...),)``: the first ``n`` of
    ``request.infos[0]`` (``options``: one index per offered troop,
    ``max_select`` = ``NumberToSelect``), at 1.0."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SardaukarLegionAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``CanDeployUnits`` (``P.CanDeploy``) then
        ``HasUnitsGarrisoned<Troop>.Any``."""

        return (
            not units_deployment_blocked(p.ctx.state, p.ctx.seat)
            and p.garrison_troop_count() > 0
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SardaukarLegionAbility.ValueForPlayer``.

        ``SardaukarLegionRevealBonus`` as "Sardukar Legion Reveal" when
        ``CurrentConflictInterest().Sum`` is above the lower ``ConflictPostureBounds``
        (strict) and the garrison holds more than ``2 * RemainingAgents + 2`` units.
        """

        v = Summer()
        interest = p.current_conflict_interest().sum
        lower, _upper = p.conflict_posture_bounds()
        if interest > lower:
            garrison = p.garrison_troop_count()
            if garrison > 2 * p.ctx.me.agents_available + 2:
                v.add("Sardukar Legion Reveal", p.C.SardaukarLegionRevealBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SardaukarLegionAbility.Evaluate``.

        ``GetUnitsToDeploy(validEntities(first target info),
        NumberToSelect)``; when it is not empty, the 1.0 (f64 literal) answer
        names those units; else the untouched choice."""

        if not request.infos:
            return Answer(0.0, None, "Sardaukar Legion no target info")
        info = request.infos[0]
        slots = _troop_slots(info)
        count = p.units_to_deploy(len(slots), info.max_select)
        if count <= 0:
            return Answer(0.0, None, "Sardaukar Legion | nothing to deploy")
        return Answer(
            1.0,
            (tuple(slots[:count]),),
            f"Sardaukar Legion | 1 | would deploy {count}",
        )


@port(_AA + "missionaria_protectiva")
class MissionariaProtectivaAbility(GainAnyInfluenceAbility):
    """``ability.activated.original.missionaria_protectiva``
    (Missionaria Protectiva's Agent box: an influence on any track).
    constructor: timing Agent; ``SelectionMode`` and ``evaluate``:
    ``GainAnyInfluenceAbility``'s (Explicit; the best faction track, response
    ``((track,),)``); ``Cost``: another Bene Gesserit card played
    (``HasPlayedFactionCard``), then ``CanGainInfluence``."""

    timing: ClassVar[Timing] = Timing.AGENT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``MissionariaProtectivaAbility.ValueForPlayer``.

        ``GainAnyInfluenceAbility.ValueForPlayer``, then, with another Bene
        Gesserit card in play (``AllCardsInPlay.Except(owner)``,
        ``ValueForPlayer``), ``GetGainInfluenceValue(
        Factions.None, 1, -1, false).Sum`` once more as "Missionaria Protectiva
        Influence".
        """

        v = super().value_for_player(p, with_entities)
        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        if any(_has_faction(c, "BeneGesserit") for c in others):
            v.add(
                "Missionaria Protectiva Influence", gain_any_influence_value(p, 1).sum
            )
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``MissionariaProtectivaAbility.ValueInPileForOtherPlay``.

        The Bene Gesserit "played" pattern (``bg_played_pile_value``) with
        ``GetGainInfluenceValue(Factions.None, 1, -1, false).Sum * 0.75`` as
        "Bene Gesserit Played".
        """

        def played() -> float:
            return gain_any_influence_value(p, 1).sum * 0.75

        return bg_played_pile_value(p, pile, card, played, "Bene Gesserit Played")


# ---------------------------------------------------------------------------
# Gurney Halleck
# ---------------------------------------------------------------------------


def _conflict_level(p: Profile) -> int:
    """``GetAttributeValue<int>(CurrentConflict, ConflictLevel)`` (default 0,
    ``MatchExtensions.CurrentConflict``)."""

    conflict_id = p.ctx.current_conflict_id
    if conflict_id is None:
        return 0
    return conflict_entity(conflict_id, p.ctx.choam).int_attr("ConflictLevel", 0)


@port(_AA + "gurney_halleck")
class GurneyHalleckAbility(DeferredAbility):
    """``ability.activated.original.gurney_halleck`` (Gurney Halleck's
    Reveal box: pay 3 Solari to deploy up to 2 troops, specimens making up the
    count). constructor: timing Reveal; ``SelectionMode``:
    Optional; ``Cost``: at least 3 Solari, then a troop in the supply
    or a specimen; ``Targets``: "ChooseDeployedTroops", the next 2
    troops of the supply and the specimens that fill up the rest.
    ``GetUnusualSelections`` is interface plumbing.

    ``evaluate`` responds ``((slot, ...),)``: the first ``n`` of
    ``request.infos[0]`` (``options``: one index per offered unit,
    ``max_select`` = ``NumberToSelect``), at 100.0."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GurneyHalleckAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GurneyHalleckAbility.ValueForPlayer``: ``GurneyHalleckRevealBonus`` as
        "Gurney Halleck Reveal Bonus" with at least 3 Solari
        (``EntityExtensions.Solari(P)``)."""

        v = Summer()
        if p.ctx.me.resources.solari >= 3:
            v.add("Gurney Halleck Reveal Bonus", p.C.GurneyHalleckRevealBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GurneyHalleckAbility.Evaluate``.

        With the Swordmaster the deployment is taken at once. Without it only
        in a level-3 Conflict (``ConflictLevel != 3`` leaves the choice
        untouched) in which some opponent is close: the strongest estimated
        opponent strength within 4 of ``EstStrength`` (``|top - est| < 5``) or
        the second strongest within 4 (``|second - est| <= 4``). Then
        ``GetUnitsToDeploy(units, NumberToSelect)``: when it is not empty the
        first ``n`` units at 100.0 (f64 literal), else the untouched choice.
        """

        if not request.infos:
            return Answer(0.0, None, "Gurney Halleck no target info")
        info = request.infos[0]
        if not p.ctx.me.swordmaster_acquired:
            if _conflict_level(p) != 3:
                return Answer(0.0, None, "Gurney Halleck | no level 3 Conflict")
            estimate = p.est_strength().sum
            rivals = sorted(
                (p.est_opponent_strength(o.player_id).sum for o in p.ctx.opponents),
                reverse=True,
            )
            top = rivals[0] if rivals else 0  # FirstOrDefault
            second = rivals[1] if len(rivals) > 1 else 0  # Skip(1).FirstOrDefault
            if not (abs(top - estimate) < 5 or abs(second - estimate) <= 4):
                return Answer(0.0, None, "Gurney Halleck | out of reach")
        slots = _troop_slots(info)
        count = p.units_to_deploy(len(slots), info.max_select)
        if count <= 0:
            return Answer(0.0, None, "Gurney Halleck | nothing to deploy")
        return Answer(
            100.0,
            (tuple(slots[:count]),),
            f"Gurney Halleck (Reveal) | toDeploy {count} troops | 100",
        )


# ---------------------------------------------------------------------------
# Shifting Allegiances
# ---------------------------------------------------------------------------


@port(_AA + "shifting_allegiances")
class ShiftingAllegiancesAbility(DeferredAbility):
    """``ability.activated.original.shifting_allegiances`` (Shifting
    Allegiances' Agent box: pay 2 spice, lose 1 influence with one faction and
    gain 2 with another). constructor: timing Agent;
    ``SelectionMode``: Optional; ``Cost``: at least 2
    spice and influence on some track.

    ``Targets`` yields two "SelectFaction" infos: "minusone"
    (tracks with influence, ``InfluenceDelta = -1``) then "plustwo" (the tracks
    that can gain, ``InfluenceDelta = 2``). ``evaluate`` responds
    ``((lose,), (gain))``: one track entity (ref = our faction id) per info.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    #: The ``InfluenceDelta`` Targets puts on each of its two infos (for "plustwo").
    TARGET_INFLUENCE_DELTAS: ClassVar[tuple[int, ...]] = (-1, 2)

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ShiftingAllegiancesAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Spice, 2)`` then
        ``HasFactionInfluence.AtLeast(F, 1)`` for any of the four factions."""

        me = p.ctx.me
        influence = me.influence
        return me.resources.spice >= 2 and (
            influence.emperor >= 1
            or influence.spacing_guild >= 1
            or influence.bene_gesserit >= 1
            or influence.fremen >= 1
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ShiftingAllegiancesAbility.ValueForPlayer``.

        Space among ``with_entities``: when ``CanAgentAbilityBePlayedWithSpace(space,
        Spice, 2)`` is false, or with fewer than 2 spice
        (``EntityExtensions.Spice(P)``), only a 0.0 term. Else ``Math.Max(0.0,
        GetBestInfluenceExchange(-1, 2, false, null, null) - GetSpiceValue(1) * 2)`` as
        "Shifting Allegiances".
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 2
        ):
            v.add(
                f"Shifting Allegiances Ability cost cannot be paid in addition "
                f"to {space.ref} cost",
                0.0,
            )
            return v
        if p.ctx.me.resources.spice < 2:
            v.add("Shifting Allegiances Ability cost cannot be paid", 0.0)
            return v
        _lose, _gain, exchange = p.best_influence_exchange(-1, 2, None, None)
        spice = p.spice_value(1)
        v.add("Shifting Allegiances", _dmax(0.0, exchange - (spice + spice)))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShiftingAllegiancesAbility.Evaluate``.

        The "lose" info (``InfluenceDelta == -1``) and the "gain" info (``== 2``);
        ``GetBestInfluenceExchange(-1, 2, true, loseTracks, gainTracks)``; the value is
        ``GetSpiceValue(-2)`` ("Spice Cost") plus the exchange ("Best Influence Exchange
        Value"). Both tracks of the winning exchange must be among the infos' entities,
        else the untouched choice.
        """

        infos = list(zip(request.infos, self.TARGET_INFLUENCE_DELTAS, strict=False))
        lose = next((info for info, delta in infos if delta == -1), None)
        gain = next((info for info, delta in infos if delta == 2), None)
        if lose is None or gain is None:
            return Answer(0.0, None, "Shifting Allegiances | no faction infos")
        lose_tracks = [e for e in lose.entities if e.kind is Kind.TRACK]
        gain_tracks = [e for e in gain.entities if e.kind is Kind.TRACK]
        lose_faction, gain_faction, exchange = p.best_influence_exchange(
            -1, 2, [t.ref for t in lose_tracks], [t.ref for t in gain_tracks]
        )
        s = Summer()
        s.add("Spice Cost", p.spice_value(-2))
        s.add("Best Influence Exchange Value", exchange)
        lose_track = next((t for t in lose_tracks if t.ref == lose_faction), None)
        gain_track = next((t for t in gain_tracks if t.ref == gain_faction), None)
        if lose_track is None or gain_track is None:
            return Answer(0.0, None, "Shifting Allegiances | no exchange")
        return Answer(
            s.sum,
            ((lose_track.ref,), (gain_track.ref,)),
            f"Shifting Allegiances | {lose_track.ref}->{gain_track.ref}",
        )


# ---------------------------------------------------------------------------
# Reverend Mother Mohiam and Test of Humanity (opponents discard / lose troops)
# ---------------------------------------------------------------------------


def _client_runs_immediately(p: Profile) -> bool:
    """The ``CanRunImmediately`` of ``ReverendMotherMohiamDeferredAbility``
 and ``TestOfHumanityDeferredAbility``.

    ``!(Target is Player && IsAtLeastMinClient(GetClientVersion(
    Target.ClientVersion ?? "0.0.0.0"), [3, ...]))``: a player whose client is
    at least 3.0.0.0 gets the prompt, any other target runs the effect at once.
    Judgement: a computer seat has no ``ClientVersion`` attribute (the app
    creates it without a client), so the literal "0.0.0.0" default applies
    and the effect runs at once; it is never prompted.
    """

    return True


@port(_PA + "reverend_mother_mohiam")
class ReverendMotherMohiamAbility(AgentAbility):
    """``ability.play.original.reverend_mother_mohiam`` (Reverend Mother
    Mohiam's Agent box: the card has no generic ``AgentAbility``).
    constructor: timing Agent; ``RunImmediateEffects`` is
    engine-side: ``evaluate`` and ``value_for_player`` are ``AgentAbility``'s."""


@port(_PA + "reverend_mother_mohiam_deferred")
class ReverendMotherMohiamDeferredAbility(DeferredAbility):
    """``ability.play.original.reverend_mother_mohiam_deferred`` (Reverend
    Mother Mohiam's second Agent box: with another Bene Gesserit card in play
    every opponent discards a card). constructor: timing Agent;
    ``SelectionMode``: Explicit; ``Cost``: another Bene
    Gesserit card played (``HasPlayedFactionCard``).

    No ``Evaluate`` override: ``DeferredAbility``'s (its ``DeferValue``, no
    sub-target)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ReverendMotherMohiamDeferredAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``CanRunImmediately``: see ``_client_runs_immediately``."""

        return _client_runs_immediately(p)

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasPlayedFactionCard(BeneGesserit, owner)``:
        another Bene Gesserit card in play."""

        return any(
            c.ref != self.owner.ref and _has_faction(c, "BeneGesserit")
            for c in _in_play(p)
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ReverendMotherMohiamDeferredAbility.ValueForPlayer``.

        Another Bene Gesserit card in play (``AllCardsInPlay.Except(owner)``,
        ``ValueForPlayer``): ``OpponentRatio(o => o.HandCount > 0)`` times 5.0 (f64
        literal) as "Reverend Mother Discard".
        """

        v = Summer()
        others = [c for c in _in_play(p) if c.ref != self.owner.ref]
        if any(_has_faction(c, "BeneGesserit") for c in others):
            ratio = p.opponent_ratio(lambda o: len(o.hand) > 0)
            v.add("Reverend Mother Discard", ratio * 5.0)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``ReverendMotherMohiamDeferredAbility.ValueInPileForOtherPlay``
.

        The Bene Gesserit "played" pattern (``bg_played_pile_value``) with
        ``OpponentRatio(o => o.HandCount > 0) * 5.0 * 0.75`` (f64 literals) as
        "Bene Gesserit in Play".
        """

        def played() -> float:
            return p.opponent_ratio(lambda o: len(o.hand) > 0) * 5.0 * 0.75

        return bg_played_pile_value(p, pile, card, played, "Bene Gesserit in Play")


@port(_PA + "test_of_humanity")
class TestOfHumanityAbility(AgentAbility):
    """``ability.play.original.test_of_humanity`` (Test of Humanity's Agent
    box: the card has no generic ``AgentAbility``). constructor:
    timing Agent; ``RunImmediateEffects`` is engine-side:
    ``evaluate`` and ``value_for_player`` are ``AgentAbility``'s."""

    __test__ = False  # not a pytest class


@port(_AA + "test_of_humanity_deferred")
class TestOfHumanityDeferredAbility(DeferredAbility):
    """``ability.activated.original.test_of_humanity_deferred`` (Test of
    Humanity's second Agent box: every opponent discards a card or loses a
    troop). constructor: timing Agent; ``SelectionMode``:
    Explicit; ``Cost`` = NoCostAction.

    No ``Evaluate`` override (``DeferredAbility``'s). The opponent's choice is
    ``evaluate_resolution_choice``: ``((0,),)`` makes P discard a card,
    ``((1,),)`` lose a troop."""

    __test__ = False  # not a pytest class
    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TestOfHumanityDeferredAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``CanRunImmediately``: see ``_client_runs_immediately``."""

        return _client_runs_immediately(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TestOfHumanityDeferredAbility.ValueForPlayer``.

        ``OpponentRatio(o => o.HandCount > 0 || o has a unit in the Conflict)`` times
        ``TestOfHumanityRelevantOpponentMod`` as "Test of Humanity Bonus".
        """

        v = Summer()
        ratio = p.opponent_ratio(
            lambda o: len(o.hand) > 0 or p.conflict_unit_count(o) > 0
        )
        v.add("Test of Humanity Bonus", ratio * p.C.TestOfHumanityRelevantOpponentMod)
        return v

    def evaluate_resolution_choice(self, p: Profile) -> Answer:
        """``TestOfHumanityDeferredAbility.EvaluateResolutionChoice``
: how the targeted opponent (P) answers "discard a card or
        lose a troop".

        Discard (0) first at 1.0 (the House Hagal branch ``HagalMode == 1``,
        which would put Troop at 5.0 first, never arises in a four-player game).
        Troop (1) at 5.0 replaces it when the Conflict is worth defending
        (``CurrentConflictInterest().Sum`` below the lower
        ``ConflictPostureBounds`` and more than one unit of P in the Conflict) or
        when the cards of P's hand that carry an Agent icon (``IconList``
        non-empty, ``EvaluateResolutionChoice``) do not
        outnumber its remaining Agents.
        """

        choice = _Choice()
        choice.update(1.0, ((0,),), "Test Of Humanity | Discard")
        lower, _upper = p.conflict_posture_bounds()
        interest = p.current_conflict_interest().sum
        troop = lower > interest and p.conflict_unit_count() > 1
        if not troop:
            with_icons = sum(1 for c in _hand(p) if len(p.icon_list(c)) > 0)
            troop = with_icons <= p.ctx.me.agents_available
        if troop:
            choice.update(5.0, ((1,),), "Test Of Humanity | Troop")
        return choice.answer("Test Of Humanity")


# ---------------------------------------------------------------------------
# Other Memory
# ---------------------------------------------------------------------------

_KWISATZ_HADERACH = "imperium.original.kwisatz_haderach"


@port(_AA + "other_memory")
class OtherMemoryAbility(DeferredAbility):
    """``ability.activated.original.other_memory`` (Other Memory's Agent
    box: take a Bene Gesserit card back). constructor: timing Agent;
    ``SelectionMode``: Explicit; ``Cost``:
    ``HasDrawableCard``; ``Targets``: the "OtherMemory" card prompt
    (the player's Bene Gesserit cards, ``Targets``).

    ``evaluate`` responds ``((card,),)``: one card entity of
    ``request.infos[0]`` (entities, in the prompt's order)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``OtherMemoryAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasDrawableCard``."""

        return p.ctx.deck_size + len(p.ctx.me.discard_pile) > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``OtherMemoryAbility.ValueForPlayer``.

        The highest ``PersuasionCost`` among the Bene Gesserit cards of P's discard pile
        (``Discard.children`` ``Where(...)`` ``Select(...)`` ``OrderByDescending``
        ``FirstOrDefault``; 0 without one) times ``OtherMemoryPlayBonusMod`` as "Other
        Memory Draw".
        """

        v = Summer()
        costs = [
            card.int_attr("PersuasionCost")
            for card in (card_entity(i, p.ctx.seat) for i in p.ctx.me.discard_pile)
            if _has_faction(card, "BeneGesserit")
        ]
        best = max(costs, default=0)
        v.add("Other Memory Draw", p.C.OtherMemoryPlayBonusMod * best)
        return v

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``OtherMemoryAbility.ValueInPileForOtherPlay``: the deck
        half of the Bene Gesserit pattern only (a Bene Gesserit candidate while
        not in the climax: ``SynergyBeneGesseritWithBondInDeck``); nothing for
        the play area."""

        s = Summer()
        if (
            pile is Pile.DECK
            and "BeneGesserit" in card_factions(card)
            and not p.is_climax()
        ):
            s.add("Bene Gesserit in Deck", p.C.SynergyBeneGesseritWithBondInDeck)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OtherMemoryAbility.Evaluate``.

        The first card of the targets at 1.0 (f64 literal; no response without
        one). Then each card in order: the Kwisatz Haderach at 100.0 (f64
        literal); else, while P has an Agent left, the ``ValueForPlayer(P, [])``
        of its first ``AgentAbility`` ("for Agent"), otherwise of its first
        ``RevealAbility`` ("for Reveal") (the empty ``DefaultValueSummer`` when
        it has none). A card replaces the stored one only when strictly better.
        """

        choice = _Choice()
        cards = _targets(request, Kind.CARD)
        if cards:
            choice.update(1.0, ((cards[0].ref,),), "Other Memory | first")
        else:
            choice.update(1.0, (), "Other Memory | no card")
        agents_left = p.ctx.me.agents_available > 0
        for card in cards:
            if card.short == _KWISATZ_HADERACH:
                choice.update(100.0, ((card.ref,),), f"Other Memory | {card.ref} | 100")
                continue
            kind = AgentAbility if agents_left else RevealAbility
            ability = next((a for a in abilities_of(card) if isinstance(a, kind)), None)
            value = Summer() if ability is None else ability.value_for_player(p, ())
            where = "Agent" if agents_left else "Reveal"
            choice.update(
                value.sum,
                ((card.ref,),),
                f"Other Memory | {card.ref} for {where} | {value.sum}",
            )
        return choice.answer("Other Memory")


# ---------------------------------------------------------------------------
# Kwisatz Haderach
# ---------------------------------------------------------------------------


def agent_retrieval_value(p: Profile, agent: Entity) -> float:
    """``KwisatzHaderachAgentRecallEvaluator.AgentRetrievalValue``:
    what retrieving ``agent`` (P's Agent on a space, ``Kind.AGENT``, ref = the
    space id it stands on) is worth to the Kwisatz Haderach's player.

    A combat space is worth 0.0 and a space without a faction 1000.0; a faction
    space 500.0 when the best opponent leads P's rank by 3 or more
    (``HighestOpponentRank - CurrentRank >= 3``), else 0.0. Minus the sum of
    ``ValueForPlayer(P, [])`` of the space's abilities
    (``AgentRetrievalValue``; f64 literals 1000.0, 500.0).
    """

    if not is_board_space(agent.ref):
        # An Agent not on a board space (still in P's area): its parent is no
        # Combat space, has ``Factions.None`` and no abilities.
        return 1000.0
    space = space_entity(agent.ref, p.ctx.board)
    if space.attr("CombatSpace", False) is True:  # IsCombatSpace
        base = 0.0
    else:
        app_faction = space.attr("Faction")
        faction = (
            _APP_TO_FACTION.get(app_faction) if isinstance(app_faction, str) else None
        )
        if faction is None:  # Factions.None
            base = 1000.0
        else:
            me = p.ctx.me
            lead = max(getattr(o.influence, faction) for o in p.ctx.opponents) - int(
                getattr(me.influence, faction)
            )
            base = 500.0 if lead >= 3 else 0.0
    total = 0.0
    for ability in abilities_of(space):
        total += ability.value_for_player(p, ()).sum
    return base - total


@port(_PA + "kwisatz_haderach")
class KwisatzHaderachAbility(AgentAbility):
    """``ability.play.original.kwisatz_haderach`` (Kwisatz Haderach's Agent
    box: any space, and an Agent comes back; the card has no generic
    ``AgentAbility``). constructor: timing Agent; ``Cost`` =
    NoCostAction; ``GetAgentTargets`` (P's Agents, not on the
    Swordmaster space unless P holds it), ``Targets`` and
    ``RunImmediateEffects`` are engine-side.

    ``evaluate`` responds ``((space,), (agent,))``: a space entity of
    ``request.infos[0]`` and an Agent entity of ``request.infos[1]``
    (``Kind.AGENT``, ref = the space the Agent stands on)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``KwisatzHaderachAbility.ValueForPlayer``.

        ``AgentAbility.ValueForPlayer``, then ``KwisatzHaderachDelayPenalty`` ("Agent
        Kwisatz Haderach Delay") while P has an Agent left and some other hand card
        (``ArchID != owner's``, ``ValueForPlayer``) has a valid space
        (``Board.ValidSpaces``): the Kwisatz is not played while something else can be.
        """

        v = super().value_for_player(p, with_entities)
        if p.ctx.me.agents_available > 0:
            cache: SpaceCache = {}
            for card in _hand(p):
                if card.short != self.owner.short and valid_space_ids(
                    p, card.ref, cache
                ):
                    v.add(
                        "Agent Kwisatz Haderach Delay", p.C.KwisatzHaderachDelayPenalty
                    )
                    break
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``KwisatzHaderachAbility.Evaluate``.

        Needs the two entity infos (spaces, then Agents). The card's own
        ``ValueForPlayer(P, [])`` is taken once. Each space of the first info on
        which some ``SpaceAbility`` can run: the sum of the space abilities'
        ``ValueForPlayer(P, [card])`` plus that card value; the first space sticks,
        a later one only when strictly better. Each Agent of the second info:
        ``AgentRetrievalValue``, the first sticks, a later one only when strictly
        better. With both found the answer is the best space's value.
        """

        infos = list(request.infos)
        if len(infos) < 2:
            return Answer(0.0, None, "KwisatzHaderachAbility | no two infos")
        card_value = self.value_for_player(p, ()).sum
        best_space: Entity | None = None
        best_value = 0.0
        for space in infos[0].entities:
            if space.kind is not Kind.SPACE:
                continue
            space_abilities = abilities_of(space)
            runnable = [a for a in space_abilities if isinstance(a, SpaceAbility)]
            if all(not a.can_be_run(p) for a in runnable):
                continue
            space_value = Summer()
            for ability in space_abilities:
                space_value.merge(ability.value_for_player(p, (self.owner,)))
            total = space_value.sum + card_value
            if total > best_value or best_space is None:
                best_space = space
                best_value = total
        best_agent: Entity | None = None
        best_retrieval = 0.0
        for agent in infos[1].entities:
            if agent.kind is not Kind.AGENT:
                continue
            retrieval = agent_retrieval_value(p, agent)
            if retrieval > best_retrieval or best_agent is None:
                best_agent = agent
                best_retrieval = retrieval
        if best_space is None or best_agent is None:
            return Answer(0.0, None, "KwisatzHaderachAbility | nothing to pick")
        return Answer(
            best_value,
            ((best_space.ref,), (best_agent.ref,)),
            f"KwisatzHaderachAbility | {self.owner.ref} -> {best_space.ref} : "
            f"retrieve from {best_agent.ref}",
        )


# ---------------------------------------------------------------------------
# The Voice
# ---------------------------------------------------------------------------

_HEIGHLINER = "space.original.heighliner"
_HARDY_WARRIORS = "space.original.hardy_warriors"


def _last_agent_with_spice(o: PlayerState) -> bool:
    """``ValueForPlayer`` / ``Evaluate``:
    ``RemainingAgents.Count() == 1 && Spice(o) >= 6``."""

    return o.agents_available == 1 and o.resources.spice >= 6


def _last_agent_with_water(o: PlayerState) -> bool:
    """``Evaluate``: ``RemainingAgents.Count() == 1 &&
    Water(o) > 0``."""

    return o.agents_available == 1 and o.resources.water > 0


@port(_AA + "the_voice")
class TheVoiceAbility(DeferredAbility):
    """``ability.activated.original.the_voice`` (The Voice's Agent box:
    block a space). constructor: timing Agent; ``SelectionMode``
: Explicit; ``Cost`` = NoCostAction; ``Targets`` (the
    spaces that are not blocked, ``Targets``) and ``Undo``
    are engine-side.

    ``evaluate`` responds ``((space,),)``: one space entity of the prompt."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TheVoiceAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TheVoiceAbility.ValueForPlayer``.

        ``TheVoiceBlockHeighlinerBonus`` as "The Voice Block Heighliner" while P has
        more than one Agent left, or, with at most one, while the Heighliner space
        (``space.original.heighliner``) holds no Agent and some opponent is down to its
        last Agent holding 6 or more spice (``ValueForPlayer``).
        """

        v = Summer()
        if p.ctx.me.agents_available > 1:
            v.add("The Voice Block Heighliner", p.C.TheVoiceBlockHeighlinerBonus)
            return v
        heighliner = find_space(p, _HEIGHLINER)
        if (
            heighliner is not None
            and not p.ctx.space_occupants(heighliner.ref)
            and any(_last_agent_with_spice(o) for o in p.ctx.opponents)
        ):
            v.add("The Voice Block Heighliner", p.C.TheVoiceBlockHeighlinerBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TheVoiceAbility.Evaluate``.

        ``lower`` = the lower ``ConflictPostureBounds``, ``interest`` =
        ``CurrentConflictInterest().Sum``. Each space of the prompt without an Agent on
        it (``Evaluate``), in order: the merged ``ValueForPlayer(P, [])`` of its
        abilities (``Aggregate`` of ``Merge``). With ``lower < interest`` the Heighliner
        goes at 100.0 when some opponent is down to its last Agent with 6 or more spice,
        and the Hardy Warriors space at 99.0 when one holds water, without looking at
        the value. Otherwise, with an Agent left and the space's first ``SpaceAbility``
        runnable, "Agent Play Option" 50.0 is added, and the space is offered at the
        sum. A space replaces the stored one only when strictly better.
        """

        choice = _Choice()
        interest = p.current_conflict_interest().sum
        lower, _upper = p.conflict_posture_bounds()
        agents_left = p.ctx.me.agents_available > 0
        for space in _targets(request, Kind.SPACE):
            if p.ctx.space_occupants(space.ref):
                continue
            space_abilities = abilities_of(space)
            value = Summer()
            for ability in space_abilities:
                value.merge(ability.value_for_player(p, ()))
            response: tuple[tuple[str | int, ...], ...] = ((space.ref,),)
            if lower < interest:
                if space.short == _HEIGHLINER and any(
                    _last_agent_with_spice(o) for o in p.ctx.opponents
                ):
                    choice.update(100.0, response, f"The Voice | {space.ref} | 100")
                    continue
                if space.short == _HARDY_WARRIORS and any(
                    _last_agent_with_water(o) for o in p.ctx.opponents
                ):
                    choice.update(99.0, response, f"The Voice | {space.ref} | 99")
                    continue
            first = next(
                (a for a in space_abilities if isinstance(a, SpaceAbility)), None
            )
            if agents_left and first is not None and first.can_be_run(p):
                value.add("Agent Play Option", 50.0)
            choice.update(value.sum, response, f"The Voice | {space.ref} | {value.sum}")
        return choice.answer("The Voice")
