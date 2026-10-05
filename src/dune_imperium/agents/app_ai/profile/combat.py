"""Conflict and combat — spec/profile-combat.md.

Implements the matching methods declared in ``profile/core.py`` (same
names and signatures). Port each app method from the spec in the assets
checkout, replaying the binary's Add/Multiply order with ``Summer``.

Unit counts follow the app's ``WormPlayer`` getters, mapped to our fields
(``R5`` §4.5): ``ConflictUnits`` = ``troops_conflict + sandworms_conflict``
(a sandworm is one unit), ``GarrisonUnits`` = ``GarrisonTroops`` =
``troops_garrison`` (an Uprising garrison holds troops only),
``Strength`` = ``combat_strength``, ``RemainingAgents.Count()`` =
``agents_available`` (like the app, it is not cleared by revealing).
Bloodlines (docs/app-ai/bloodlines-systems.md §1.1, D1): Sardaukar Commanders
count as troops and units, Duncan's Into the Fray Agent as a Conflict unit;
both are 0 without the option.

Comparisons keep the binary's direction and strictness, so a NaN conflict
interest (no current Conflict: ``RelativeConflictValue`` divides by an empty
average) falls through the same branches as in the app.
"""

import math
from collections import Counter
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, cast

from dune_imperium.agents.app_ai import catalog
from dune_imperium.agents.app_ai.abilities import UnportedAbility, abilities_of
from dune_imperium.agents.app_ai.abilities.base import Ability
from dune_imperium.agents.app_ai.context import card_id
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import IntSummer, Summer, app_round
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.leader_abilities import units_deployment_blocked

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# ``GetGainInfluenceValue``'s ``Factions.None`` ("any faction": the best gain);
# the same value as ``influence.NO_FACTION``.
ANY_FACTION = "none"

# ``ResourceActions.ResourceNames`` key order (``ResourceActions::.cctor
# @0x49630b0``), read by ``RelativeConflictValue``. ``PossibleStrength`` and
# ``RevealStrength`` have no ``Attr``: no Uprising reward archetype carries
# them (checked by the tests), so their sum is always 0 and never priced.
_RESOURCE_NAMES: tuple[tuple[str, Attr | None], ...] = (
    ("Water", Attr.WATER),
    ("Spice", Attr.SPICE),
    ("Solari", Attr.SOLARI),
    ("Strength", Attr.STRENGTH),
    ("PossibleStrength", None),
    ("Persuasion", Attr.PERSUASION),
    ("RevealStrength", None),
)

# Custom reward ability IDs counted by ``RelativeConflictValue``
# (``b__112_8`` .. ``b__112_17``): ``<Class>.AbilityID`` is the class's full
# name, as the reward archetypes' ``CustomAbilityIDs`` show.
_GAIN_ANY_INFLUENCE = (
    "worm.canis.abilities.ActivatedAbilities.GainAnyInfluenceConflictAbility"
)
_GAIN_ANY_TWO_INFLUENCE = (
    "worm.canis.abilities.ConflictAbilities.Uprising.GainAnyTwoInfluenceConflictAbility"
)
_TAKE_CONTROL = (
    "worm.canis.abilities.ConflictAbilities.Uprising.TakeControlConflictAbility"
)
_PLACE_SPY_CUSTOM = (
    "worm.canis.abilities.ActivatedAbilities.Uprising.PlaceSpyCustomAbility"
)
# ``TrashCustomAbility.AbilityID``, not ``TrashConflictCustomAbility``'s (the
# app's own mismatch, spec §14.4; moot: Trade Dispute is never in the pool).
_TRASH_CUSTOM = "worm.canis.abilities.ActivatedAbilities.TrashCustomAbility"

# ``ConflictPlace`` of a conflict card's abilities (set by
# ``GenericConflictAbility::.ctor @0x4b70df0``). The card-level extras
# (``Recall2SpiesVPAbility``, ``Pay*ToGain1VPAbility``) come after the three
# generic abilities, so a ``FirstOrDefault(place == n)`` always lands on a
# generic one; they are given place 0 here.
_CONFLICT_PLACES: dict[str, int] = {
    "worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictFirstAbility": 1,
    "worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictSecondAbility": 2,
    "worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictThirdAbility": 3,
    # Epic's Economic Supremacy (spec/epic-goto11-promo-draft.md §2.4): the
    # place ctors 0x4b78db0 / 0x4b7a920 / 0x4b7c980; its Solari and Spice
    # charges have no ConflictPlace attribute (0).
    "worm.canis.abilities.ConflictAbilities.RiseOfIx.EconomicSupremacyFirstAbility": 1,
    "worm.canis.abilities.ConflictAbilities.RiseOfIx.EconomicSupremacySecondAbility": 2,
    "worm.canis.abilities.ConflictAbilities.RiseOfIx.EconomicSupremacyThirdAbility": 3,
}

# Direct subclasses of ``PlayAbilities.StrengthIntrigueAbility`` dealt in an
# Uprising game, with Immortality's two (type listing in
# ``worm-canis.dll.cs``; none has a subclass): the abilities
# ``OfType<StrengthIntrigueAbility>()`` keeps.
_STRENGTH_INTRIGUE_ABILITIES: frozenset[str] = frozenset(
    {
        "worm.canis.abilities.PlayAbilities.Immortality.CounterattackCombatAbility",
        "worm.canis.abilities.PlayAbilities.Immortality.ViciousTalentsAbility",
        "worm.canis.abilities.PlayAbilities.BaseSet.BackedbyCHOAMCombatAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.ContingencyPlanCombatAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.DevourAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.FindWeaknessAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.GoToGroundAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.ImpressAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.QuestionableMethodsAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.ReachAgreementAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.SpiceIsPowerAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.SpringTheTrapAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.TacticalOptionAbility",
        "worm.canis.abilities.PlayAbilities.Uprising.WeirdingCombatAbility",
    }
) | frozenset(
    # App-style Bloodlines subclasses of StrengthIntrigueAbility
    # (docs/app-ai/bloodlines-cards.md §4.1, §5: "Combat cards derive from
    # StrengthIntrigueAbility"), so ``OfType<StrengthIntrigueAbility>()``
    # keeps them. Only the Bloodlines synthetic archetypes list these names.
    "worm.canis.abilities.AppStyle.Bloodlines." + name
    for name in (
        "BattlefieldResearchCombatAbility",
        "DesertSupportAbility",
        "GraspArrakisCombatAbility",
        "ReturnTheFavorAbility",
        "RipplesInTheSandAbility",
        "TenuousBondCombatAbility",
        "TheStrongSurviveAbility",
        "WithdrawalAgreementAbility",
        "TwistedControlledCombatAbility",
        "TwistedShrewdAbility",
        "TwistedSinisterAbility",
    )
)

# ``DeployValue``'s "nothing to deploy from" spaces (base-game list; in
# Uprising only Spice Refinery and Imperial Basin match).
_EMPTY_GARRISON_SPACES: frozenset[str] = frozenset(
    {
        "SpaceArchetypes.BaseSet.Stillsuits",
        "SpaceArchetypes.BaseSet.ResearchStation",
        "SpaceArchetypes.BaseSet.TheGreatFlat",
        "SpaceArchetypes.BaseSet.HaggaBasin",
        "SpaceArchetypes.Uprising.SpiceRefinery",
        "SpaceArchetypes.BaseSet.ImperialBasin",
    }
)
# ``WormArchetypeExtensions::IsHeighlinerSpace @0x4eaca60``.
_HEIGHLINER_SPACES: frozenset[str] = frozenset(
    {"SpaceArchetypes.BaseSet.Heighliner", "SpaceArchetypes.Uprising.HeighlinerUP"}
)
_GURNEY = "LeaderArchetypes.Uprising.GurneyHalleckLeader"
_CHANI_CLEVER_TACTICIAN = "chani_clever_tactician"
_GO_TO_GROUND = "go_to_ground"
_ECONOMIC_POSITIONING = "economic_positioning"  # our Intrigue card id
# Our ids of the board spaces the potentials look up
# (``BoardSpaces.FirstOrDefault(IsHeighlinerSpace)`` / ``ArchID ==
# Uprising.HaggaBasinUP`` / ``Uprising.DeepDesert``): always on our board.
_HEIGHLINER = "heighliner"
_HAGGA_BASIN = "hagga_basin"
_DEEP_DESERT = "deep_desert"
# ``WormUnit`` vslot 35 ``get_Strength``: a troop is worth 2.
_TROOP_STRENGTH = 2

_APP_FACTION_TO_OURS: dict[str, str] = {
    app: ours for ours, app in catalog.FACTION_NAMES.items()
}

_UPRISING_CONFLICTS: list[Archetype] = []


def _ieee_div(numerator: float, denominator: float) -> float:
    """C# ``double`` division: ``x / 0`` is ±Infinity or NaN, never an error."""

    if denominator == 0.0:
        if numerator == 0.0 or math.isnan(numerator):
            return math.nan
        return math.copysign(math.inf, numerator) * math.copysign(1.0, denominator)
    return numerator / denominator


def _multiply(summer: Summer, reason: str, mod: float) -> None:
    """``AIProfileAbsUtils::Multiply @0x9cd920`` (label overload ``@0x9cd7b0``).

    The binary reads ``Sum``, then ``mulsd``/``subsd`` and
    ``AIValueSummer<double>::Add``: the new sum is ``Sum + (mod*Sum - Sum)``,
    which can differ from ``mod*Sum`` in the last bit (spec
    profile-combat.md, header "Summer arithmetic": "reproduce for
    bit-exactness"). ``Summer.multiply`` now does the same; this helper keeps
    the app's debug label. The reason mirrors the app's debug-only
    ``$"{reason} (*{mod:f2})"`` label.
    """

    total = summer.sum
    summer.add(f"{reason} (*{mod:.2f})", mod * total - total)


def _int(archetype: Archetype, name: str) -> int:
    """``GetAttributeValue<int>(name, 0)`` on an archetype."""

    value = archetype.attributes.get(name, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _strings(archetype: Archetype, name: str) -> tuple[str, ...]:
    value = archetype.attributes.get(name, ())
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return ()


def _card_archetype(bare_card_id: str) -> Archetype:
    """A personal card's archetype by bare card id."""

    return catalog.archetype(catalog.CARD_ARCHETYPES[bare_card_id])


def _card_strength(bare_card_id: str) -> int:
    """``WormEntityExtensions::Strength @0x482e770``: the printed swords."""

    return _int(_card_archetype(bare_card_id), "Strength")


def _has_guild_icon(bare_card_id: str) -> bool:
    """``IconList`` contains ``SpacingGuild`` (``b__126_4`` / ``b__126_6``)."""

    return "SpacingGuild" in _strings(_card_archetype(bare_card_id), "IconList")


def _cs_half(value: int) -> int:
    """C# ``int / 2``: truncation toward zero."""

    return int(value / 2)


def _conflict_units(p: PlayerState) -> int:
    """``WormPlayer::get_ConflictUnits @0x4843c40`` (a sandworm is one unit).

    Bloodlines (docs/app-ai/bloodlines-systems.md §1.1, D1): every
    ``WormUnit`` counts, so Sardaukar Commanders and Duncan's Into the Fray
    Agent too (``PlayerState.units_in_conflict``); both are 0 without the
    option.
    """

    return p.units_in_conflict


def _garrison_units(p: PlayerState) -> int:
    """``WormPlayer::get_GarrisonUnits @0x4843dc0`` (troops only in Uprising;
    Bloodlines garrison Commanders too, §1.1)."""

    return p.troops_garrison + p.commanders_garrison


def _garrison_troops(p: PlayerState) -> int:
    """``WormPlayer::get_GarrisonTroops @0x4843ac0``: troops, and Bloodlines
    Commanders ("a 'troop' worth 2 strength", §1.1, D1); never an Agent."""

    return p.troops_garrison + p.commanders_garrison


def _conflict_troops(p: PlayerState) -> int:
    """``GetDeployedTroops`` / ``HasUnitsDeployed<WormTroop>``: troops in the
    Conflict and Bloodlines Commanders (§1.1); never a sandworm or Agent."""

    return p.troops_conflict + p.commanders_conflict


class CombatMixin(ProfileCore):
    """Overrides of the ProfileCore declarations for this area."""

    # -- private reads --

    def _profile(self) -> Profile:
        return cast("Profile", self)

    def _is_four_player(self) -> bool:
        """``Players.Count >= 4`` (the closures' ``isFourPlayer``)."""

        return len(self.ctx.players) >= 4

    def _conflict_rewards_allowed(self) -> int:
        """``WormMatch::get_ConflictRewardsAllowed @0x47fdfa0``: 3 in 4p, else 2."""

        return 3 if len(self.ctx.players) >= 4 else 2

    def _current_conflict(self) -> Entity | None:
        """``WormMatchExtensions::CurrentConflict @0x480f5b0``."""

        conflict_id = self.ctx.current_conflict_id
        if conflict_id is None:
            return None
        return catalog.conflict_entity(conflict_id, self.ctx.choam)

    def _conflict_level(self) -> int:
        """``GetFrom<int>(ConflictLevel, CurrentConflict)`` (default 0)."""

        conflict = self._current_conflict()
        return 0 if conflict is None else conflict.int_attr("ConflictLevel", 0)

    def _conflict_abilities(self, conflict: Entity) -> list[tuple[int, Ability]]:
        """``cc.Abilities`` in order, each with its ``ConflictPlace``."""

        return [
            (_CONFLICT_PLACES.get(ability_id, 0), ability)
            for ability_id, ability in zip(
                conflict.ability_ids, abilities_of(conflict), strict=True
            )
        ]

    def _conflict_ability_for_place(self, place: int) -> Ability | None:
        """``CurrentConflict.Abilities.FirstOrDefault(ConflictPlace == place)``."""

        conflict = self._current_conflict()
        if conflict is None:
            return None
        for ability_place, ability in self._conflict_abilities(conflict):
            if ability_place == place:
                return ability
        return None

    def _conflict_value(self, conflict: Entity) -> Summer:
        """``WormConflictPlayable::ConflictValue(P, isFourPlayer) @0x4829dc0``.

        spec/board.md §2.3: merge ``ValueForPlayer`` of every card ability,
        skipping ``ConflictPlace == 3`` below four players.
        """

        four = self._is_four_player()
        value = Summer()
        for place, ability in self._conflict_abilities(conflict):
            if not four and place == 3:
                continue
            value.merge(ability.value_for_player(self._profile(), ()))
        return value

    def _hand_swords(self) -> int:
        """``me.Hand.children.Sum(entity.Strength)`` (own hand)."""

        return sum(_card_strength(card_id(card)) for card in self.ctx.hand)

    def _holds_intrigue(self, bare_card_id: str) -> bool:
        """``WormPlayer::HasIntrigueCard`` for the AI's own Intrigue hand."""

        return any(card_id(card) == bare_card_id for card in self.ctx.intrigue_cards)

    def _space_has_agent(self, space_id: str) -> bool:
        """``WormSpace.HasAgent``: any seat's Agent stands on the space."""

        return bool(self.ctx.space_occupants(space_id))

    def _observes(self, p: PlayerState, space: Entity) -> bool:
        """``WormSpace.HasObservingSpy(p)``: a Spy of ``p`` on a post seeing it."""

        posts = space.attr("ObservationPosts", ())
        if not isinstance(posts, tuple):
            return False
        return any(catalog.POST_INDEX[post] in posts for post in p.spy_post_ids)

    def _strength_value(self, ability: Ability) -> int:
        """``StrengthIntrigueAbility.StrengthValue(me)`` (vslot 88).

        The Intrigue port supplies it as ``strength_value(profile)``. An
        unported class behaves like ``WormAbilityDefinition`` (worth 0) and is
        counted in ``UNPORTED``.
        """

        method = getattr(ability, "strength_value", None)
        if method is None:
            if isinstance(ability, UnportedAbility):
                return 0
            raise TypeError(f"{ability!r} has no strength_value")
        return int(method(self._profile()))

    def _can_deploy(self) -> bool:
        """``WormPlayer::get_CanDeploy @0x483db50``.

        True unless the conflict area's ``Deployable`` flag is false, which
        only Shaddam's Emperor of the Known Universe sets for its turn
        (spec/leaders.md §11.2): our ``units_deployment_blocked`` reads the
        same restriction from this seat's own turn frame.
        """

        return not units_deployment_blocked(self.ctx.state, self.ctx.seat)

    # -- competitors, posture --

    def _is_competitor(self, op: PlayerState) -> bool:
        """``<get_ConflictCompetitors>b__105_0 @0x491eeb0``."""

        return _conflict_units(op) >= self._conflict_level()

    def deploy_value(self, owner: Entity) -> float:
        """``WormAIProfile::DeployValue @0x4912c50`` — spec §6.

        ``owner`` is the space whose ``DeployUnitsAbility`` is valued. Shaddam's
        signet gate lives in ``DeployUnitsAbility.ValueForPlayer``, not here.
        """

        me = self.ctx.me
        v = (self.C.DeployEarly, self.C.DeployMid, self.C.DeployLate)[self.game_arc()]
        lb, ub = self.conflict_posture_bounds()
        interest = self.current_conflict_interest().sum
        slots = self._conflict_rewards_allowed()
        # b__103_0 / b__103_1: opponents with ConflictUnits > 0 (recounted).
        if lb > interest and slots <= sum(
            1 for op in self.ctx.opponents if _conflict_units(op) > 0
        ):
            v = 0.0
        elif ub > interest and slots > sum(
            1 for op in self.ctx.opponents if _conflict_units(op) > 0
        ):
            v = v * 1.5  # f64 1.5 (DeployValue)
        elif interest >= ub and _garrison_troops(me) > 0:
            v = v + v
        w = v
        if _garrison_units(me) == 0 and owner.kind is Kind.SPACE:
            if owner.short in _EMPTY_GARRISON_SPACES:
                w = 0.0
            elif _conflict_units(me) > 0 and owner.short in _HEIGHLINER_SPACES:
                w = v + -1.0  # f64 -1.0 (DeployValue)
        if (
            _conflict_units(me) == 0
            and _garrison_units(me) > 0
            # b__103_2: ConflictUnits > 0
            and slots > sum(1 for op in self.ctx.opponents if _conflict_units(op) > 0)
            # b__103_3: ConflictUnits == 0 and RemainingAgents.Any()
            and sum(
                1
                for op in self.ctx.opponents
                if _conflict_units(op) == 0 and op.agents_available > 0
            )
            == 0
        ):
            third = self._conflict_ability_for_place(3)  # b__103_6
            if third is not None:
                # f64 1.25 (DeployValue): a guaranteed 3rd place.
                w += 1.25 * third.value_for_player(self._profile(), ()).sum
        # f64 0.33 and 2.0 (DeployValue): pressure from an overfull garrison.
        w += min(max(0.0, (_garrison_troops(me) - 3) * 0.33), 2.0)
        # IsSetEnabled(RiseOfIx) is false: dreadnought, Negotiated Withdrawal
        # and Overpowering Dread terms skipped. Rapid Mobilization and Staged
        # Incident (BaseSet) cannot be held: r = s = 1.0.
        r = 1.0
        s = 1.0
        w = w * (r * s)
        # Economic Positioning (Immortality, spec/immortality.md §2.9): not
        # gated by the set (the card exists only with it).
        if (
            self._holds_intrigue(_ECONOMIC_POSITIONING)
            and self.solari_value(1) >= self.C.EconomicPositioningDeploySolariThreshold
        ):
            w *= self.C.EconomicPositioningDeployMod
        if (
            any(card_id(card) == _CHANI_CLEVER_TACTICIAN for card in me.in_play)
            and 1 <= _conflict_units(me) <= 2  # unsigned ConflictUnits - 1 <= 1
            and _conflict_units(me) + _garrison_units(me) >= 3
            and interest > lb
        ):
            w *= self.C.ChaniCleverTacticianDeployMod
        return w

    def conflict_competitors(self) -> float:
        """``get_ConflictCompetitors @0x4913e30`` — spec §1.2 (no caller)."""

        return self.opponent_ratio(self._is_competitor)

    def conflict_posture_bounds(self) -> tuple[float, float]:
        """``get_ConflictPostureBounds @0x4908390`` — spec §2.

        The ratio is recomputed for each test, as in the binary.
        """

        if 0.0 >= self.opponent_ratio(self._is_competitor):
            return (
                self.C.ConflictPostureNoCompetitorsLowerBound,
                self.C.ConflictPostureNoCompetitorsUpperBound,
            )
        # f64 0.5 (get_ConflictPostureBounds).
        if self.opponent_ratio(self._is_competitor) > 0.0 and 0.5 >= (
            self.opponent_ratio(self._is_competitor)
        ):
            return (
                self.C.ConflictPostureSomeCompetitorsLowerBound,
                self.C.ConflictPostureSomeCompetitorsUpperBound,
            )
        if self.is_climax():
            return (
                self.C.ConflictPostureManyCompetitorsLowerBoundClimax,
                self.C.ConflictPostureManyCompetitorsUpperBoundClimax,
            )
        return (
            self.C.ConflictPostureManyCompetitorsLowerBound,
            self.C.ConflictPostureManyCompetitorsUpperBound,
        )

    def combat_positioning(self) -> float:
        """``GetCombatPositioning @0x4913ea0`` — spec §4.

        Only caller: Immortality's ``HighPriorityTravelAbility``
        (immortality.md §5.6); unused in a plain Uprising game.
        """

        me = self.ctx.me
        # b__108_0: p != me and its agent supply holds at least as many.
        n = sum(
            1
            for p in self.ctx.players
            if p.player_id != self.ctx.seat
            and p.agents_available >= me.agents_available
        )
        interest = self.current_conflict_interest().sum
        lb, ub = self.conflict_posture_bounds()
        if interest > ub:
            return n * 1.5  # f64 1.5 (GetCombatPositioning)
        return float(n) if lb < interest else 0.0

    def combat_posture_mod(self) -> float:
        """``GetCombatPostureMod @0x4908080`` — spec §3.

        Dead in every game: its only caller, ``GetResourceValue``, reaches it
        only with ``includeCombatPostureMod`` true, which no caller passes.
        """

        interest = self.current_conflict_interest().sum
        lb, ub = self.conflict_posture_bounds()
        if interest > ub:
            return self.C.ConflictPostureHighMod
        if interest > lb:
            return self.C.ConflictPostureMidMod
        return 1.0

    # -- conflict interest --

    def uprising_conflicts(self) -> list[Archetype]:
        """``GetUprisingConflicts @0x4913fb0`` — spec §5.1.

        ``AllArchetypes().Where(IsConflictArchetype && IsInSet(Uprising) &&
        !HasAttribute(RemovedFromSetList))``: 14 cards, never CHOAM Security or
        Trade Dispute. Cached for the whole game (``_cachedUprisingConflicts``
        is never cleared), here for the process: it is static content.
        """

        if _UPRISING_CONFLICTS:
            return _UPRISING_CONFLICTS
        _UPRISING_CONFLICTS.extend(
            archetype
            for archetype in ARCHETYPES.values()
            # IsConflictArchetype @0x4eab3a0: EntityType Conflict, level > 0.
            if archetype.attributes.get("EntityType") == "Conflict"
            and _int(archetype, "ConflictLevel") > 0
            and "Uprising" in _strings(archetype, "SetList")
            and "RemovedFromSetList" not in archetype.attributes
        )
        return _UPRISING_CONFLICTS

    def relative_conflict_value(self) -> Summer:
        """``RelativeConflictValue(false) @0x4900490`` — spec §5.2.

        The current card's ``ConflictValue`` divided by the average reward value
        of every Uprising conflict card of its level. With no current Conflict
        the average stays 0 and the result is NaN, as in the app. Epic's
        Economic Supremacy (a Rise of Ix archetype) is never in that pool: as
        the current card it is divided by the four Uprising level-III cards'
        average (spec/epic-goto11-promo-draft.md §2.4).
        """

        four = self._is_four_player()
        avg = Summer()
        res = Summer()
        cc = self._current_conflict()
        if cc is not None:
            conflict_level = cc.int_attr("ConflictLevel", 0)
            # IsSetEnabled(Uprising) is true: the Uprising branch.
            pool = [
                c
                for c in self.uprising_conflicts()
                if _int(c, "ConflictLevel") == conflict_level
            ]
            take = 3 if four else 2  # Take(isFourPlayer | 2)
            rewards = [
                ARCHETYPES[reward_id]
                for c in pool
                for reward_id in _strings(c, "ConflictRewardArchetypes")[:take]
            ]
            for name, attr in _RESOURCE_NAMES:
                n = sum(_int(r, name) for r in rewards)
                if n > 0:
                    if attr is None:
                        raise NotImplementedError(f"no Attr for reward {name}")
                    avg.add(f"{name} * {n}", self.resource_value(attr, n, False))
            vp1 = self.victory_point_value(1)
            n = sum(_int(r, "VictoryPoints") for r in rewards)
            if n > 0:
                avg.add(f"VP * {n}", n * vp1)
            n = sum(_int(r, "IntrigueCard") for r in rewards)
            if n > 0:
                avg.add(f"Intrigue * {n}", self.intrigue_value() * n)
            influence: list[tuple[str, int]] = []
            for r in rewards:
                pairs = r.attributes.get("FactionInfluence")
                if isinstance(pairs, Mapping):
                    influence.extend(
                        (_APP_FACTION_TO_OURS[faction], int(amount))
                        for faction, amount in pairs.items()
                    )
            if influence:
                total = 0.0
                for faction, amount in influence:  # b__19
                    total += self.gain_influence_value(faction, amount, -1, False).sum
                avg.add("Specific Influence", total)
            n = sum(_int(r, "Troops") for r in rewards)
            if n > 0:
                avg.add(f"Troop * {n}", self.resource_value(Attr.TROOPS, n, False))
            # lea eax,[rax+rax*2]: a flat 3 per card, always added.
            avg.add("Battle Icon Value", float(3 * len(pool)))
            ids = [i for r in rewards for i in _strings(r, "CustomAbilityIDs")]
            k = ids.count(_GAIN_ANY_INFLUENCE) + 2 * ids.count(_GAIN_ANY_TWO_INFLUENCE)
            if k > 0:
                avg.add(
                    f"Any Influence * {k}",
                    k * self.gain_influence_value(ANY_FACTION, 1, -1, False).sum,
                )
            ids = [
                i
                for i in ids
                if i not in (_GAIN_ANY_INFLUENCE, _GAIN_ANY_TWO_INFLUENCE)
            ]
            n = ids.count(_TAKE_CONTROL)
            if n > 0:
                control_solari = self.control_solari_value()
                avg.add(
                    f"Take Control * {n}",
                    n
                    * (
                        (control_solari + control_solari + self.control_spice_value())
                        / 3.0
                    ),
                )
                ids = [i for i in ids if i != _TAKE_CONTROL]
            n = ids.count(_PLACE_SPY_CUSTOM)
            if n > 0:
                # The app's log label is the copy-pasted "Take Control * ".
                avg.add(f"Take Control * {n}", n * self.spy_value().sum)
                ids = [i for i in ids if i != _PLACE_SPY_CUSTOM]
            n = ids.count(_TRASH_CUSTOM)
            if n > 0:
                # Valued with SpyValue (the app's copy-paste).
                avg.add(f"Trash * {n}", n * self.spy_value().sum)
                ids = [i for i in ids if i != _TRASH_CUSTOM]
            if ids:
                # f64 0.5 (RelativeConflictValue): pay-X-for-VP style rewards.
                avg.add(f"Costed Ability * {len(ids)}", vp1 * len(ids) * 0.5)
            _multiply(avg, "Avg Conflict Value", _ieee_div(1.0, len(pool)))
        cc = self._current_conflict()
        if cc is not None:
            res.merge(self._conflict_value(cc))  # MergePrependReason "CCV "
        _multiply(res, "Avg Conflict Value", _ieee_div(1.0, avg.sum))
        # Demand Respect, To the Victor (BaseSet), Strategic Push and Windtraps
        # (Rise of Ix) cannot be held in an Uprising game.
        # Bloodlines Planetary Array (bloodlines-systems.md §9, D58; the
        # Windtraps precedent): a draw on a Conflict win. Tech Module only.
        if self.ctx.has_tech("planetary_array"):
            res.add("Planetary Array", self.card_draw_value_with_buy_gains())
        return res

    def current_conflict_interest(self) -> Summer:
        """``CurrentConflictInterest @0x4902f80`` — spec §5.4 (not cached)."""

        me = self.ctx.me
        s = Summer()
        s.merge(self.relative_conflict_value())
        s.add("VAR offset", -1.0)  # f64 -1.0 (CurrentConflictInterest)
        _multiply(s, "VAR offset", 40.0)  # f64 40.0 (CurrentConflictInterest)
        s.add(
            "Garrisoned Units",
            self.C.ConflictInterestGarrisonUnitValue * _garrison_units(me),
        )
        s.add(
            "Opponents with Agents",
            self.C.ConflictInterestOpponentsWithAgentsPenalty
            * sum(1 for op in self.ctx.opponents if op.agents_available > 0),
        )
        s.add(
            "Hand Swords", self.C.ConflictInterestHandSwordValue * self._hand_swords()
        )
        s.add(
            "Intrigue Swords",
            self.C.ConflictInterestIntrigueSwordValue
            * self.intrigue_hand_strength_value(),
        )
        # IsSetEnabled(RiseOfIx) is false: no garrison dreadnought term.
        if self.heighliner_potential_player() == self.ctx.seat:
            s.add("Heighliner Potential", self.C.ConflictInterestHeighlinerPotential)
        if self.has_worm_potential():
            s.add("Worm Potential", self.C.ConflictInterestWormPotential)
        # Reinforcements (BaseSet) cannot be held in an Uprising game.
        return s

    def _intrigue_troop_value(self) -> int:
        """``IntrigueHand.OfType<WormIntriguePlayable>().Sum(b__116_2)``.

        ``b__116_2``: ``card.Abilities.OfType<IntrigueAbility>().Sum(a =>
        a.TroopValue(M, me))`` (vslot 86), over the held Intrigue in hand
        order. The only override in our games is Immortality's
        ``CounterattackPlotAbility::TroopValue @0x4c672f0`` (4), spec
        immortality.md §2.9; the Intrigue port supplies it as
        ``troop_value(profile)`` (``IntrigueAbility`` default 0). An
        unported class is worth 0 (``WormAbilityDefinition``).
        """

        from dune_imperium.agents.app_ai.abilities.intrigue import IntrigueAbility

        profile = self._profile()
        total = 0
        for card in self.ctx.intrigue_cards:
            entity = catalog.intrigue_entity(card, self.ctx.seat)
            for ability in abilities_of(entity):
                if isinstance(ability, IntrigueAbility):
                    total += int(ability.troop_value(profile))
        return total

    def intrigue_hand_strength_value(self) -> int:
        """``IntrigueHandStrengthValue @0x4914170`` — spec §5.3, intrigues §4.4.

        Sum of ``StrengthValue(me)`` over every ``StrengthIntrigueAbility`` of
        the Intrigue cards in hand (hand order, then ability order).
        """

        total = 0
        for card in self.ctx.intrigue_cards:
            entity = catalog.intrigue_entity(card, self.ctx.seat)
            for ability_id, ability in zip(
                entity.ability_ids, abilities_of(entity), strict=True
            ):
                if ability_id in _STRENGTH_INTRIGUE_ABILITIES:
                    total += self._strength_value(ability)
        return total

    # -- strength estimates --

    def est_opponent_strength(self, opponent: int) -> IntSummer:
        """``EstOpponentStrength @0x4914400`` — spec §7.3.

        Reads the opponent's ``Hand ∪ Deck`` only as a multiset average
        (``AppContext.hidden_pool``) and its Intrigue only as a count.
        """

        op = self.ctx.player(opponent)
        s = IntSummer()
        k = (1.0, 1.2)[_conflict_units(op) >= 2]  # double table at 0x52f3bc0
        pool: Counter[str] = self.ctx.hidden_pool(opponent)
        size = sum(pool.values())
        if size > 0:
            # Enumerable.Average<int>: (double)sum / count.
            average = sum(_card_strength(c) * n for c, n in pool.items()) / size
            hand_swords = app_round(len(op.hand) * average * k)
        else:
            hand_swords = 0
        # f64 0.75 (EstOpponentStrength): per held Intrigue card.
        intrigue_swords = app_round(len(op.intrigue_cards) * 0.75 * k)
        current = op.combat_strength
        agents = 0 if op.has_revealed else op.agents_available
        heighliner = self.heighliner_potential_player()  # always evaluated
        is_heighliner = heighliner is not None and heighliner == opponent
        if agents > 0:
            s.add("Current Strength", current)
            s.add("Possible Intrigue Swords", intrigue_swords)
            s.add("Possible Hand Swords", hand_swords)
            s.add("Agents Left", 2 * agents)
            s.add("Garrison Units", min(3 * agents, _garrison_troops(op)))
            # f64 1.0 (EstOpponentStrength); RCV from this AI's point of view.
            if is_heighliner and self.relative_conflict_value().sum >= 1.0:
                s.add("Heighliner Bonus", self.C.ExpectedStrengthHeighlinerPotential)
            if self._worm_potential_a_player() == opponent:
                s.add("WormPotentialA Bonus", self.C.ExpectedStrengthWormPotentialA)
            if self._worm_potential_b_player() == opponent:
                s.add("WormPotentialB Bonus", self.C.ExpectedStrengthWormPotentialB)
        elif _conflict_units(op) > 0:
            s.add("Current Strength", current)
            s.add("Possible Intrigue Swords", intrigue_swords)
            if len(op.hand) > 0:
                s.add("Possible Hand Swords", hand_swords)
        else:
            s.add("Not in Conflict", 0)
        return s

    def est_strength(self) -> IntSummer:
        """``EstStrength @0x4914bd0`` — spec §7.1."""

        me = self.ctx.me
        s = IntSummer()
        interest = self.current_conflict_interest().sum
        lb, _ub = self.conflict_posture_bounds()
        s.add("Hand Swords", self._hand_swords())
        s.add("Misc Strength", me.combat_strength)
        if interest >= lb:
            s.add("Intrigue Swords", self.intrigue_hand_strength_value())
            if _garrison_units(me) > 0:
                s.add("Agents Left Bonus", 3 * me.agents_available)
            s.add("Intrigue Troop Value", _cs_half(self._intrigue_troop_value()))
            if self.heighliner_potential_player() == self.ctx.seat:
                s.add("Heighliner Bonus", self.C.ExpectedStrengthHeighlinerPotential)
            elif self._worm_potential_a_player() == self.ctx.seat:
                s.add("WormPotentialA Bonus", self.C.ExpectedStrengthWormPotentialA)
            elif self._worm_potential_b_player() == self.ctx.seat:
                s.add("WormPotentialB Bonus", self.C.ExpectedStrengthWormPotentialB)
        # Treachery (Rise of Ix) cannot be in hand.
        return s

    def potential_strength(self, max_units: int) -> IntSummer:
        """``PotentialStrength(maxUnits) @0x49152d0`` — spec §7.2 (no posture gate)."""

        me = self.ctx.me
        s = IntSummer()
        s.add("Misc Strength", me.combat_strength)
        s.add("Hand Swords", self._hand_swords())
        s.add("Intrigue Swords", self.intrigue_hand_strength_value())
        agents = me.agents_available
        s.add("Deployable Bonus", 2 * max_units)
        s.add("Undeployable Bonus", min(_garrison_units(me) - max_units, 2 * agents))
        s.add("Agents Left", 2 * agents)
        s.add("Intrigue Troop Value", _cs_half(self._intrigue_troop_value()))
        if self.heighliner_potential_player() == self.ctx.seat:
            s.add("Heighliner Bonus", self.C.PotentialStrengthHeighlinerPotential)
        elif self.has_worm_potential():
            s.add("Worm Potential Bonus", self.C.PotentialStrengthWormPotential)
        # Treachery (Rise of Ix) cannot be in hand.
        return s

    # -- deploy and retreat --

    def units_to_deploy(self, garrison_troops: int, max_units: int) -> int:
        """``GetUnitsToDeploy(units, max) @0x49158f0`` — spec §8.

        ``garrison_troops`` is the number of units the deploy prompt offers
        (all garrison troops, strength 2 each); ``max_units`` its
        ``NumberToSelect``. Returns how many of them to deploy (the app's
        list holds that many troops, strongest first in prompt order).
        """

        me = self.ctx.me
        units = garrison_troops
        max_ = max_units if max_units > 0 else units
        interest = self.current_conflict_interest().sum
        my_exp = self.est_strength().sum
        my_pot = self.potential_strength(max_).sum
        opp = sorted(
            (self.est_opponent_strength(op.player_id).sum for op in self.ctx.opponents),
            reverse=True,
        )
        all_ = sorted([*opp, my_exp], reverse=True)
        req = 0
        sum_strength = units * _TROOP_STRENGTH
        lb, ub = self.conflict_posture_bounds()
        slots = self._conflict_rewards_allowed()
        in_conflict = sum(1 for op in self.ctx.opponents if _conflict_units(op) > 0)
        # me.GarrisonTroops is read here and unused.
        if self.is_climax():
            req = sum_strength  # "Climax"
        elif lb > interest:
            if slots > in_conflict and _conflict_units(me) <= 0:
                req = 1  # "Low Deploy 1"
        else:
            a0 = all_[0] if all_ else 0
            a1 = all_[1] if len(all_) > 1 else 0
            o0 = opp[0] if opp else 0
            o1 = opp[1] if len(opp) > 1 else 0
            if ub > interest:
                gurney = False
                if my_pot > o0:
                    req = a0 - my_exp + 1  # "Mid can win"
                    gurney = True
                elif my_pot > o1:
                    req = a1 - my_exp + 1  # "Mid can get 2nd"
                    gurney = True
                elif _garrison_units(me) >= 6 and any(my_pot >= o for o in opp):
                    req = 2 * _garrison_units(me) - 8  # "Mid Avoid Unit Saturation"
                    gurney = True
                elif slots > in_conflict and _conflict_units(me) == 0:
                    req = 1  # "Mid Deploy 1" (no Gurney adjustment)
                if gurney and self._leader_short() == _GURNEY and (6 - my_exp) > req:
                    req = 6 - my_exp  # " + Gurney 6 Strength" (literal 6)
            elif interest >= ub:
                if my_pot > o0:
                    req = a0 - my_exp + 3  # "High can win"
                elif my_pot > o1:
                    req = a1 - my_exp + 3  # "High can get second"
                elif len(self.ctx.opponents) == 3:
                    a2 = all_[2] if len(all_) > 2 else 0
                    o2 = opp[2] if len(opp) > 2 else 0
                    if my_pot > o2:
                        req = a2 - my_exp + 3  # "High can get third"
                elif _garrison_units(me) >= 6:
                    req = 2 * _garrison_units(me) - 8  # unreachable in 4p
                elif slots > in_conflict and _conflict_units(me) == 0:
                    req = 1  # unreachable in 4p
        # Selection: strongest first; TakeWhile tests the sum before the unit.
        total = 0
        taken = 0
        deploy = 0
        for _ in range(units):
            ok = total < req and taken < max_
            total += _TROOP_STRENGTH
            taken += 1
            if not ok:
                break
            deploy += 1
        # Baron Harkonnen's Masterstroke (BaseSet) and Diversion (Rise of Ix)
        # cannot occur. Go to Ground: keep one troop in to stay playable.
        if (
            self._holds_intrigue(_GO_TO_GROUND)
            and _conflict_troops(me) == 0
            and deploy == 0
            and units - deploy > 0
        ):
            # The app adds sorted.OfType<WormTroop>().FirstOrDefault(); with no
            # unit offered there is no deploy prompt at all.
            deploy += 1
        return deploy

    def _leader_short(self) -> str | None:
        me = self.ctx.me
        if me.leader_id is None:
            return None
        return catalog.leader_entity(me.leader_id, me.leader_face_id).short

    def troops_to_retreat(self, max_troops: int) -> int:
        """``GetTroopsToRetreat(max) @0x4917820`` — spec §10, intrigues §4.3."""

        me = self.ctx.me
        opp_current = sorted(
            (op.combat_strength for op in self.ctx.opponents), reverse=True
        )
        current = me.combat_strength  # the closure's "myEstimatedStrength"

        def estimate(p: PlayerState) -> int:  # b__2
            if p.player_id == self.ctx.seat:
                return self.est_strength().sum
            return self.est_opponent_strength(p.player_id).sum

        top2 = sorted(self.ctx.players, key=estimate, reverse=True)[:2]
        max_vp = max(self.ctx.vp(q) for q in top2)
        trigger = self.ctx.endgame_trigger_score
        conflict = self._current_conflict()
        # The conflict card's own VictoryPoints: 0 for every Uprising card, 4
        # for Epic's Economic Supremacy (its Rise of Ix archetype; spec
        # epic-goto11-promo-draft.md §2.4: the branch fires at max VP >= 8
        # with T = 12).
        conflict_vp = 0 if conflict is None else conflict.int_attr("VictoryPoints", 0)
        slots = self._conflict_rewards_allowed()
        if conflict_vp + max_vp >= trigger:
            if self.is_climax():
                return 0
            ahead = sum(1 for s in opp_current if current < s)  # b__5
            if ahead == slots:
                top = opp_current[0] if opp_current else 0
                return (
                    max_troops
                    if top > self.intrigue_hand_strength_value() + current
                    else 0
                )
            if ahead == slots - 1 and all(
                _conflict_units(op) > 0 or op.agents_available == 0
                for op in self.ctx.opponents
            ):
                return min(max_troops, _conflict_units(me) - 1)
            return 0
        if self.C.TroopRichThreshold <= _garrison_troops(me):
            return 0
        below = next((s for s in opp_current if current >= s), 0)  # b__4
        excess = current - below
        # f64 0.9 (GetTroopsToRetreat).
        if 0.9 >= self.relative_conflict_value().sum:
            return min((excess >> 1) - 2, max_troops) if excess >= 6 else 0
        return min((excess >> 1) - 4, max_troops) if excess >= 8 else 0

    # -- ranks and orders --

    def _conflict_rank(
        self, opponent_strength: Callable[[int], int], bonus_strength: int
    ) -> int | None:
        """``GetConflictRank(oppStrengthFunc, bonusStrength) @0x49180f0`` — §11.4."""

        players = self.ctx.players
        max_rank = (1 if len(players) >= 4 else 0) | 2
        keys = {
            p.player_id: (
                p.combat_strength + bonus_strength
                if p.player_id == self.ctx.seat
                else opponent_strength(p.player_id)
            )
            for p in players
        }
        ordered = sorted(keys, key=lambda seat: keys[seat], reverse=True)
        rank = 1
        index = 0
        while index < len(ordered):
            key = keys[ordered[index]]
            group = [seat for seat in ordered[index:] if keys[seat] == key]
            index += len(group)
            if self.ctx.seat not in group:
                rank += len(group)
                continue
            rank += 1 if len(group) >= 2 else 0
            return rank if rank <= max_rank else None
        return None

    def estimated_conflict_rank(self, bonus_strength: int = 0) -> int | None:
        """``EstimatedConflictRank(bonus) @0x4918070`` — spec §11.4 (1-based)."""

        return self._conflict_rank(
            lambda seat: self.est_opponent_strength(seat).sum, bonus_strength
        )

    def current_conflict_rank(self, bonus_strength: int = 0) -> int | None:
        """``CurrentConflictRank(bonus) @0x4918460`` — spec §11.4 (1-based)."""

        return self._conflict_rank(
            lambda seat: self.ctx.player(seat).combat_strength, bonus_strength
        )

    def current_combat_order(self) -> list[int]:
        """``GetCurrentCombatOrder @0x49040a0`` — spec §11.2.

        Seats by current strength, descending; ties keep seat order.
        """

        players = sorted(
            self.ctx.players, key=lambda p: p.combat_strength, reverse=True
        )
        return [p.player_id for p in players]

    def expected_combat_order(self) -> list[int]:
        """``GetExpectedCombatOrder @0x49185a0`` — spec §11.3 (unused in Uprising)."""

        return [seat for seat, _strength in self.expected_combat_order_with_strength()]

    def expected_combat_order_with_strength(self) -> list[tuple[int, int]]:
        """``GetExpectedCombatOrderWithStrength @0x49186f0`` — spec §11.3.

        Opponents first (seat order), the AI appended last; a stable sort, so
        ties put opponents before the AI.
        """

        entries = [
            (op.player_id, self.est_opponent_strength(op.player_id).sum)
            for op in self.ctx.opponents
        ]
        entries.append((self.ctx.seat, self.est_strength().sum))
        return sorted(entries, key=lambda entry: entry[1], reverse=True)

    # -- Heighliner and worm potentials --

    def heighliner_potential_player(self) -> int | None:
        """``GetHeighlinerPotentialPlayer @0x49189a0`` — spec §9.1.

        The first seat in ``GetOrderedPlayers`` order with the Heighliner's
        spice, the space free (or a Spy observing it), an Agent left and a
        Guild-icon card: in the real hand for the AI, among the cards it owns
        minus those in play and in the discard pile (= ``Hand ∪ Deck``) for an
        opponent.
        """

        ordered = self.ordered_players()
        space = catalog.space_entity(_HEIGHLINER, self.ctx.board)
        spice_cost = space.int_attr("SpiceCost", 0)
        occupied = self._space_has_agent(_HEIGHLINER)
        for seat in ordered:
            p = self.ctx.player(seat)
            is_me = seat == self.ctx.seat
            if p.resources.spice < spice_cost:
                continue
            # p.IsHagal: never in a 4-player game.
            if occupied and not self._observes(p, space):
                # Only the AI could still go there, with Infiltrate (BaseSet),
                # which an Uprising Intrigue hand cannot hold.
                continue
            if p.agents_available > 0:
                if not is_me:
                    if any(_has_guild_icon(c) for c in self.ctx.hidden_pool(seat)):
                        return seat
                    continue
            else:
                # Urgent Mission (BaseSet) cannot be held: the AI is out too.
                continue
            # ME: Dispatch an Envoy (BaseSet) cannot be held.
            if any(_has_guild_icon(card_id(card)) for card in self.ctx.hand):
                return seat
        return None

    def has_highliner_potential(self, seat: int | None = None) -> bool:
        """``HasHighlinerPotential() @0x4914340`` / ``(p) @0x4914b10`` (no caller)."""

        target = self.ctx.seat if seat is None else seat
        return self.heighliner_potential_player() == target

    def worm_potential_player(self, space_id: str) -> int | None:
        """``GetWormPotentialPlayer(space) @0x491e770`` — spec §9.3."""

        for seat in self.ordered_players():
            if self.can_play_to_desert_space_with_hooks(seat, space_id):
                return seat
        return None

    def _worm_potential_a_player(self) -> int | None:
        """``GetWormPotentialAPlayer @0x491e8d0``: Hagga Basin (``HaggaBasinUP``)."""

        return self.worm_potential_player(_HAGGA_BASIN)

    def _worm_potential_b_player(self) -> int | None:
        """``GetWormPotentialBPlayer @0x491ea30``: Deep Desert."""

        return self.worm_potential_player(_DEEP_DESERT)

    def has_worm_potential(self, seat: int | None = None) -> bool:
        """``HasWormPotential() @0x4914380`` / ``(p) @0x491eb90`` — spec §9.4.

        A is tested first; B only when A fails.
        """

        target = self.ctx.seat if seat is None else seat
        return (
            self._worm_potential_a_player() == target
            or self._worm_potential_b_player() == target
        )

    def has_worm_potential_a(self, seat: int | None = None) -> bool:
        """``HasWormPotentialA() @0x4915250`` / ``(p) @0x4914b50`` (no caller)."""

        target = self.ctx.seat if seat is None else seat
        return self._worm_potential_a_player() == target

    def has_worm_potential_b(self, seat: int | None = None) -> bool:
        """``HasWormPotentialB() @0x4915290`` / ``(p) @0x4914b90`` (no caller)."""

        target = self.ctx.seat if seat is None else seat
        return self._worm_potential_b_player() == target

    def can_play_to_desert_space_with_hooks(self, seat: int, space_id: str) -> bool:
        """``CanPlayToDesertSpaceWithHooks(p, s) @0x491ce50`` — spec §9.2.

        No card-icon check, no "already there" check, no ``HasRevealed`` test.
        """

        p = self.ctx.player(seat)
        space = catalog.space_entity(space_id, self.ctx.board)
        return (
            p.maker_hooks
            and p.agents_available > 0
            and p.resources.water >= space.int_attr("WaterCost", 0)
            and (not self._space_has_agent(space_id) or self._observes(p, space))
        )

    # -- intrigue helpers --

    def should_play_retreat_intrigue(
        self,
        card_name: str,
        not_first_extra_strength: int,
        first_extra_strength: int,
        retreat_units: int,
    ) -> int:
        """``ShouldPlayRetreatIntrigue @0x4919820`` — spec/intrigues.md §4.1.

        Returns 0 or 1. ``card_name`` is the app's literal ("Go To Ground",
        "Reach Agreement", "Spice Is Power").
        """

        me = self.ctx.me
        current = me.combat_strength
        opp_current = [op.combat_strength for op in self.ctx.opponents]
        my_exp = self.est_strength().sum
        top = 0
        second = 0
        next_below = 0
        for op in self.ctx.opponents:
            e = self.est_opponent_strength(op.player_id).sum
            if e > top:
                second = top
                top = e
            elif e > second:
                second = e
            s = op.combat_strength
            if s > next_below and s < current:
                next_below = s
        is_go_to_ground = card_name == "Go To Ground"
        units = _conflict_units(me)
        if my_exp >= top:
            # 'In First and (Strength(self) - <firstExtra>) >= (NextOpponentStrength)'
            if (
                all(current > s for s in opp_current)
                and current - first_extra_strength >= next_below
                and units > retreat_units
            ):
                return 1
            return 0
        if any(current <= s for s in opp_current):
            if my_exp < second:
                if is_go_to_ground:
                    return 1 if self.current_conflict_rank(0) is not None else 0
                return 1  # 'Not Expected(Second)'
            if not is_go_to_ground:
                second_place = self._conflict_ability_for_place(2)  # b__129_3
                # A GenericConflictSecondAbility is always a ConflictAbility.
                if (
                    second_place is not None
                    and self.victory_point_value(1)
                    > second_place.value_for_player(self._profile(), ()).sum
                ):
                    return 1
            return 0
        if (
            current - not_first_extra_strength >= next_below + 1
            and units > retreat_units
        ):
            return 1
        return 0

    def should_play_troop_intrigue(
        self,
        card_name: str,
        not_first_extra_strength: int,
        first_extra_strength: int,
        troops: int,
    ) -> int:
        """``ShouldPlayTroopIntrigue @0x491a4c0`` — spec/intrigues.md §4.2.

        Returns 0 or 100 (Mercenaries ``(6, 4, 2)``, Depart for Arrakis
        ``(6, 4, 3)``). ``card_name`` only feeds the app's log.
        """

        if not self._can_deploy():
            return 0
        if self.ctx.me.troops_supply < troops - 1:
            return 0
        lb, ub = self.conflict_posture_bounds()
        interest = self.current_conflict_interest().sum
        if self.is_climax():
            return 100  # 'Climax or High Combat Posture'
        if interest > ub:
            return 100
        if not interest > lb:  # jbe: also taken for a NaN interest
            return 0
        exp = self.est_strength().sum
        # Max over AIValueSummer<int> (compared by Sum).
        max_opp = max(
            (self.est_opponent_strength(op.player_id).sum for op in self.ctx.opponents),
            default=0,
        )
        d = max_opp - exp
        if d > 0:
            # 'Mid CombatPosture, Not Expected(First)'
            return 0 if abs(d) > not_first_extra_strength else 100
        # 'Mid CombatPosture, Expected(First)'
        return 0 if exp > max_opp + first_extra_strength else 100

    def play_intrigue_for_final_round_or_hand_size(self, card: Entity) -> int:
        """``PlayIntrigueForFinalRoundOrHandSize @0x4912b00`` — intrigues §4.6.

        Dead in Uprising (callers are Base-set Windfall and Water Peddlers).
        """

        if self.is_final_round():
            return 100  # '<card> | 100 | Final Round'
        if len(self.ctx.intrigue_cards) < 4:
            return -1
        return 100  # '<card> | 100 | Intrigue hand >= 4'

    def trash_intrigue_value(self) -> float:
        """``TrashIntrigueValue @0x491b610`` — intrigues §4.5.

        0 when any held Intrigue card is junk (``WormIntriguePlayable::
        IsBadIntrigue``, the same predicate as ``GetBadIntrigueCardsInHand``),
        else ``TrashIntrigueValue``.
        """

        if self.bad_intrigue_cards_in_hand():
            return 0.0
        return self.C.TrashIntrigueValue


__all__ = ["ANY_FACTION", "CombatMixin"]
