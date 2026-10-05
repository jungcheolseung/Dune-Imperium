"""Influence, spies, contracts, battle icons, hooks, Shield Wall, agent recall.

Spec: ``spec/profile-influence-uprising.md`` (with ``06-influence.md``,
``08-uprising-systems.md``, ``16-leader-followups.md`` and their Errata; the
contract acquisition terms from ``spec/board.md`` §3.4). Section numbers in
the docstrings below refer to ``profile-influence-uprising.md`` unless they
name another file.

Each method replays the app's Add/Multiply order with ``Summer``. Game state
is read only through ``self.ctx`` (``AppContext``): the seat's own zones,
other seats' public fields. Methods owned by the economy and combat areas are
reached through their ``ProfileCore`` declarations.

Conventions of this port:

- Factions are our ids (``emperor``, ``spacing_guild``, ``bene_gesserit``,
  ``fremen``); ``NO_FACTION`` stands for the app's ``Factions.None`` ("any
  faction") in ``gain_influence_value``. ``FactionList(match)`` is our
  ``FACTIONS`` order (Emperor, Spacing Guild, Bene Gesserit, Fremen: the
  app's enum order; the board's track order is assumed to be the same).
- Agent icons and battle icons are compared by the app's enum names
  (``Emperor``, ``Pentagon``, ``Circle``, ``Triangle``, ...; ``Crysknife``,
  ``DesertMouse``, ``Ornithopter``, ``Wildcard``), which is how the archetype
  attributes store them; ``deck_agent_icons()`` is read with those keys.
- ``ListUtil.Shuffle`` (thread-local ``System.Random`` in the app) is
  replayed with ``self.rng`` on a copy of the list, at the same point.
"""

import sys
from collections.abc import Iterable, Sequence
from functools import cache
from typing import TYPE_CHECKING, Final, cast

from dune_imperium.agents.app_ai.catalog import (
    BLOODLINES_SPACE_ARCHETYPES,
    FACTION_NAMES,
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    POST_INDEX,
    SPACE_ARCHETYPES,
    board_space_ids,
    card_entity,
    intrigue_entity,
    is_board_space,
    post_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext, Board, card_id
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.ornithopter import face_up_battle_card_ids

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# The app's ``Factions.None``: "any faction" for ``GetGainInfluenceValue``.
NO_FACTION: Final = "none"

# ``IsSetEnabled`` for the sets this port can meet: the target is the
# 4-player Uprising game (with or without CHOAM), never Rise of Ix.
_UPRISING_ENABLED: Final = True
_RISE_OF_IX_ENABLED: Final = False

_APP_FACTION: Final = {app: ours for ours, app in FACTION_NAMES.items()}

# Leaders (our ids; ``Leader.ArchID`` tests of the Uprising leaders).
_MARGOT: Final = "lady_margot_fenring"
_AMBER: Final = "lady_amber_metulli"
_IRULAN: Final = "princess_irulan"
_MUAD_DIB: Final = "muad_dib"
_STABAN: Final = "staban_tuek"
_JESSICA: Final = "lady_jessica"
_JESSICA_FLIPPED_FACE: Final = "reverend_mother_jessica"
_YRKOON: Final = "steersman_y_rkoon"  # Bloodlines (app-style)
# Base/Rise of Ix leader archetypes the app also tests (never dealt here).
_GLOSSU_ARCH: Final = "LeaderArchetypes.BaseSet.GlossuTheBeastRabban"
_TESSIA_ARCH: Final = "LeaderArchetypes.RiseOfIx.TessiaVernius"

# Intrigue archetypes tested by ``HasIntrigueCard``.
_PLANS_WITHIN_PLANS: Final = "IntrigueArchetypes.BaseSet.PlansWithinPlans"
_GRAND_CONSPIRACY: Final = "IntrigueArchetypes.RiseOfIx.GrandConspiracy"
_DEPART_FOR_ARRAKIS: Final = "IntrigueArchetypes.Uprising.DepartforArrakis"
_SHADDAMS_FAVOR: Final = "IntrigueArchetypes.Uprising.ShaddamsFavor"
_SHADOW_ALLIANCE: Final = "IntrigueArchetypes.Uprising.ShadowAlliance"
_STRATEGIC_STOCKPILING: Final = "IntrigueArchetypes.Uprising.StrategicStockpiling"
_WEIRDING_COMBAT: Final = "IntrigueArchetypes.Uprising.WeirdingCombat"
_SPRING_THE_TRAP: Final = "IntrigueArchetypes.Uprising.SpringtheTrap"
_CRYSKNIFE: Final = "IntrigueArchetypes.Uprising.CrysknifeIntrigue"
_DESERT_MOUSE: Final = "IntrigueArchetypes.Uprising.DesertMouse"
_ORNITHOPTER: Final = "IntrigueArchetypes.Uprising.Ornithopter"
_DETONATION: Final = "IntrigueArchetypes.Uprising.Detonation"
_DEVOUR: Final = "IntrigueArchetypes.Uprising.Devour"
_INSPIRE_AWE: Final = "IntrigueArchetypes.Uprising.InspireAwe"
_SPECIAL_MISSION: Final = "IntrigueArchetypes.Uprising.SpecialMission"
_UNEXPECTED_ALLIES: Final = "IntrigueArchetypes.Uprising.UnexpectedAllies"

# Space archetypes (``ArchID`` tests).
_SWORDMASTER_SPACES: Final = frozenset(
    {"SpaceArchetypes.BaseSet.Swordmaster", "SpaceArchetypes.Uprising.SwordmasterUP"}
)
_INTERSTELLAR_SHIPPING: Final = "SpaceArchetypes.RiseOfIx.InterstellarShipping"
_HAGGA_BASIN: Final = "SpaceArchetypes.Uprising.HaggaBasinUP"
_DEEP_DESERT: Final = "SpaceArchetypes.Uprising.DeepDesert"
_SIETCH_TABR: Final = "SpaceArchetypes.Uprising.SietchTabrUP"
_HALL_OF_ORATORY: Final = "SpaceArchetypes.BaseSet.HallofOratory"
_SPICE_TRADE_SPACES: Final = frozenset(  # ResourceMod b__25_0
    {"SpaceArchetypes.Uprising.Sardaukar", "SpaceArchetypes.Uprising.HeighlinerUP"}
)
_HIGH_COUNCIL_SPACES: Final = frozenset(  # WormArchetypeExtensions::IsHighCouncilSpace
    {"SpaceArchetypes.BaseSet.HighCouncil", "SpaceArchetypes.Uprising.HighCouncilUP"}
)
_RESEARCH_STATION_SPACES: Final = frozenset(  # ::IsResearchStationSpace
    {
        "SpaceArchetypes.BaseSet.ResearchStation",
        "SpaceArchetypes.Uprising.ResearchStationUP",
        "SpaceArchetypes.Immortality.ResearchStationImmortality",
    }
)
_REFINERY_SPACES: Final = frozenset(  # ResourceMod b__25_3
    {
        "SpaceArchetypes.Uprising.SpiceRefinery",
        "SpaceArchetypes.RiseOfIx.DreadnoughtSpace",
    }
)

# ``a is SpaceAbilities.Uprising.DesertSpaceDeferredAbility`` (IntrigueBlowWall
# b__160_0): its two concrete subclasses.
_DESERT_DEFERRED_ABILITIES: Final = frozenset(
    {
        "worm.canis.abilities.SpaceAbilities.Uprising.DeepDesertDeferredAbility",
        "worm.canis.abilities.SpaceAbilities.Uprising.HaggaBasinUprisingDeferredAbility",
    }
)
# ``GainInfluenceIntrigueAbility`` subclasses and the faction each grants
# (all BaseSet intrigues: the "+1 influence intrigue" bump is dead here).
_GAIN_INFLUENCE_INTRIGUE_ABILITIES: Final = {
    "worm.canis.abilities.PlayAbilities.BaseSet.FavoredSubjectAbility": "emperor",
    "worm.canis.abilities.PlayAbilities.BaseSet.GuildAuthorizationAbility": (
        "spacing_guild"
    ),
    "worm.canis.abilities.PlayAbilities.BaseSet.KnowTheirWaysAbility": "fremen",
    "worm.canis.abilities.PlayAbilities.BaseSet.SecretOfTheSisterhoodAbility": (
        "bene_gesserit"
    ),
}
# ``AllianceAbility`` subclasses on Imperium cards and their faction (BaseSet
# and Rise of Ix only: the "Abilities Bonus" is dead here).
_ALLIANCE_ABILITIES: Final = {
    "worm.canis.abilities.PlayAbilities.BaseSet.FirmGripAbility2": "emperor",
    "worm.canis.abilities.PlayAbilities.BaseSet.WormRidersAllianceAbility": "fremen",
    "worm.canis.abilities.TriggeredAbilities.RiseOfIx.GuildAccordAllianceAbility": (
        "spacing_guild"
    ),
}

# Contract ability classes (``WormContractPlayable::AcquireValue`` takes the
# first ``ContractAbility`` of the contract).
_CONTRACT_NS: Final = (
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities."
)
_CONTRACT_ABILITY: Final = _CONTRACT_NS + "ContractAbility"
_DRAW2_CONTRACT: Final = _CONTRACT_NS + "Draw2ContractAbility"
_PLACE_SPY_CONTRACT: Final = _CONTRACT_NS + "PlaceSpyContractAbility"
_RECALL_AGENT_CONTRACT: Final = _CONTRACT_NS + "RecallAgentContractAbility"
_BG_CONTRACT: Final = _CONTRACT_NS + "BeneGesseritContractAbility"
_TSMF_CONTRACT: Final = _CONTRACT_NS + "TSMFContractAbility"
# App-style Bloodlines contract tokens (docs/app-ai/bloodlines-cards.md §7);
# only their synthetic archetypes list these classes. The terms live in
# ``abilities/bloodlines_cards`` (``appstyle_contract_terms``,
# ``earn_alliance_acquire_value``).
_APPSTYLE_CONTRACT_ABILITIES: Final = frozenset(
    {
        "worm.canis.abilities.AppStyle.Bloodlines.Draw1ContractAbility",
        "worm.canis.abilities.AppStyle.Bloodlines.EarnAllianceContractAbility",
        "worm.canis.abilities.AppStyle.Bloodlines.Harvest3SpyContractAbility",
        "worm.canis.abilities.AppStyle.Bloodlines.Harvest4SpyContractAbility",
        "worm.canis.abilities.AppStyle.Bloodlines.ImmediateTrashIntrigueContractAbility",
    }
)
_CONTRACT_ABILITIES: Final = _APPSTYLE_CONTRACT_ABILITIES | frozenset(
    {
        _CONTRACT_ABILITY,
        _CONTRACT_NS + "Harvest3ContractAbility",
        _CONTRACT_NS + "Harvest4ContractAbility",
        _DRAW2_CONTRACT,
        _PLACE_SPY_CONTRACT,
        _RECALL_AGENT_CONTRACT,
        _BG_CONTRACT,
        _TSMF_CONTRACT,
    }
)

# Our battle icons -> the app's ``BattleIcons`` names.
_BATTLE_ICONS: Final = {
    "crysknife": "Crysknife",
    "desert_mouse": "DesertMouse",
    "ornithopter": "Ornithopter",
    "wild": "Wildcard",
}

# The 6-step influence track (literal ``Math.Min(amount + cur, 6)``).
_TRACK_TOP: Final = 6


# =============================================================================
# Honest reads (AppContext rules: own zones, other seats' public fields)
# =============================================================================


def _influence(player: PlayerState, faction: str) -> int:
    """``GetFactionInfluence(F)`` (public)."""

    return int(getattr(player.influence, faction))


def _highest_opponent_rank(ctx: AppContext, faction: str) -> int:
    """``WormFactionTrack::HighestOpponentRank(Player)``: max over the others."""

    return max(_influence(p, faction) for p in ctx.opponents)


def _alliance_holder(ctx: AppContext, faction: str) -> PlayerState | None:
    """The seat holding ``faction``'s Alliance token (None: still on the track)."""

    for player in ctx.players:
        if faction in player.alliance_faction_ids:
            return player
    return None


def _own_card_ids(ctx: AppContext) -> list[str]:
    """``Player.AllImperiumCards`` as bare card ids (own deck as a multiset)."""

    me = ctx.me
    ids = list(ctx.deck_multiset.elements())
    ids.extend(card_id(i) for i in (*me.hand, *me.discard_pile, *me.in_play))
    return ids


def _intrigue_archetypes(ctx: AppContext) -> list[str]:
    """Own held Intrigue as app archetype short names."""

    return [INTRIGUE_ARCHETYPES[card_id(i)] for i in ctx.intrigue_cards]


def _has_intrigue(ctx: AppContext, archetype: str) -> bool:
    """``Player.HasIntrigueCard(archetype)``."""

    return archetype in _intrigue_archetypes(ctx)


def _count_card_tags(ctx: AppContext, tags: frozenset[str]) -> int:
    """``WormPlayerExtensions::CountCardTags(player, tags) @ 0x49a8e90``.

    Owned Imperium cards (every zone) plus held Intrigue cards carrying any
    of ``tags``.
    """

    count = 0
    for cid in _own_card_ids(ctx):
        if tags.intersection(card_entity(cid).list_attr("Tags")):
            count += 1
    for iid in ctx.intrigue_cards:
        if tags.intersection(intrigue_entity(iid).list_attr("Tags")):
            count += 1
    return count


def _intrigue_grants_influence(instance_id: str, faction: str) -> bool:
    """``GetGainInfluenceValue`` b__0 @ 0x492afa0.

    The card's first ``GainInfluenceIntrigueAbility`` names ``faction``. Its
    subclasses are BaseSet intrigues, so this is never true in Uprising.
    """

    for ability in intrigue_entity(instance_id).ability_ids:
        if ability in _GAIN_INFLUENCE_INTRIGUE_ABILITIES:
            return _GAIN_INFLUENCE_INTRIGUE_ABILITIES[ability] == faction
    return False


def _leader_archetype(ctx: AppContext) -> str | None:
    leader = ctx.me.leader_id
    return None if leader is None else LEADER_ARCHETYPES.get(leader)


def _in_agent_turn(ctx: AppContext) -> bool:
    """``Player.IsInPlayerTurn(PlayerTurnTypes.AgentTurn = 1)``.

    The app sets ``AgentTurn`` once the Agent card is played and keeps it to
    End Turn; ours is the seat's own open ``agent_effects`` frame.
    """

    return ctx.own_frame_context("agent_effects") is not None


def _active_space_id(ctx: AppContext) -> str | None:
    """``Player.ActiveSpace.FirstOrDefault()``: this Agent turn's space."""

    frame = ctx.own_frame_context("agent_effects")
    if frame is None:
        return None
    space = frame.get("space_id")
    return space if isinstance(space, str) and space else None


def _has_tech_tile(ctx: AppContext, tile: str) -> bool:
    """``Player.HasTechTile(RiseOfIx.<tile>)``: no Rise of Ix tech here."""

    return False


# -- board spaces and observation posts ---------------------------------------


@cache
def _board_spaces(board: Board) -> tuple[Entity, ...]:
    """``BoardSpaces(match)`` of the target game (our board order)."""

    return tuple(space_entity(space_id, board) for space_id in board_space_ids(board))


def _board_space(board: Board, archetype: str) -> Entity | None:
    """``BoardSpaces.FirstOrDefault(s => s.ArchID == archetype)``."""

    for space in _board_spaces(board):
        if space.short == archetype:
            return space
    return None


def _post_indices(space: Entity) -> tuple[int, ...]:
    value = space.attr("ObservationPosts", ())
    if not isinstance(value, tuple):
        return ()
    return tuple(int(i) for i in value)


@cache
def _observed_spaces(index: int, board: Board) -> tuple[Entity, ...]:
    """``WormObservationPost::get_ObservedSpaces @ 0x4837ca0``."""

    return tuple(s for s in _board_spaces(board) if index in _post_indices(s))


def _has_observing_spy(player: PlayerState, space: Entity) -> bool:
    """``WormSpace::HasObservingSpy(player)``: a Spy on a connected post."""

    watched = {POST_INDEX[post_id] for post_id in player.spy_post_ids}
    return any(index in watched for index in _post_indices(space))


def _space_faction(space: Entity) -> str | None:
    """The space's ``Faction`` (our id), None for ``Factions.None``."""

    faction = space.attr("Faction")
    return _APP_FACTION.get(faction) if isinstance(faction, str) else None


def _has_bonus_spice_attr(space: Entity) -> bool:
    """``s.BonusSpice.HasValue`` / ``IsMakerSpace``: the attribute exists."""

    return space.has("BonusSpice")


def _distinct[T](items: Iterable[T]) -> list[T]:
    """``Distinct().ToList()``: first occurrence order."""

    out: list[T] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _battle_icon_list(player: PlayerState) -> list[str]:
    """``Player.BattleIconList``: icons of the face-up battle cards (app names)."""

    icons: list[str] = []
    for cid in face_up_battle_card_ids(player):
        if cid in OBJECTIVES_BY_ID:
            icon = OBJECTIVES_BY_ID[cid].battle_icon
        else:
            conflict_icon = CONFLICTS_BY_ID[cid].battle_icon
            if conflict_icon is None:
                continue
            icon = conflict_icon
        icons.append(_BATTLE_ICONS[str(icon)])
    return icons


def _app_battle_icon(icon: str) -> str:
    """Our battle icon id or an app ``BattleIcons`` name -> the app name."""

    if not icon:
        return "None"
    return _BATTLE_ICONS.get(icon, icon)


def _arc[T](profile: ProfileCore, early: T, mid: T, late: T) -> T:
    """``new double[] {early, mid, late}[GetGameArc()]``."""

    return (early, mid, late)[profile.game_arc()]


# =============================================================================
# Contracts: ``ContractAbility`` hooks the profile needs (spec/board.md §3.4)
# =============================================================================


def contract_ability_class(contract: Entity) -> str | None:
    """The first ``ContractAbility`` of a contract (``AcquireValue``'s b__8_0)."""

    for ability in contract.ability_ids:
        if ability in _CONTRACT_ABILITIES:
            return ability
    return None


def contract_spaces(p: ProfileCore, contract: Entity) -> list[Entity]:
    """``WormContractPlayable.ContractSpaces @ 0x482a7a0``.

    ``BoardSpaces.Where(ReferencedArchetypeIDs.Contains(ArchID))``.
    """

    referenced = contract.list_attr("ReferencedArchetypeIDs")
    return [s for s in _board_spaces(p.ctx.board) if s.short in referenced]


def contract_resource_value(p: ProfileCore, contract: Entity) -> Summer:
    """``ContractAbility::GetResourceValue`` (vslot 91) and its overrides.

    Base ``@ 0x4d546f0``; ``Draw2ContractAbility @ 0x4d59300``,
    ``PlaceSpyContractAbility @ 0x4d5a270``, ``RecallAgentContractAbility @
    0x4d5c0b0``, ``BeneGesseritContractAbility @ 0x4d54640``,
    ``TSMFContractAbility @ 0x4d5d110`` (spec §3.5, board.md §3.4). Harvest
    contracts inherit the base.
    """

    s = Summer()
    s.add("Contract Water", p.water_value(contract.int_attr("Water")))
    s.add("Contract Solari", p.solari_value(contract.int_attr("Solari")))
    s.add("Contract Troops", p.troop_value(contract.int_attr("Troops"), False))
    # NegotiateTechValue * (TechNegotiator ?? 0): no Uprising contract has the
    # Rise of Ix negotiator attribute, so the term is 0.
    s.add("Contract Negotiatiors", 0.0)
    if p.ctx.has_tech("choam_transports"):
        # Bloodlines CHOAM Transports: a draw per completed contract
        # (bloodlines-systems.md §9, D57; Draw2ContractAbility's draw term).
        s.add("CHOAM Transports", p.card_draw_value_with_buy_gains())
    ability = contract_ability_class(contract)
    if ability == _DRAW2_CONTRACT:
        s.add("Draw 2", 2 * p.card_draw_value())  # literal 2
        # ``lea esi, [rax + rax]`` @0x4d593ac: the gain is doubled for 2 draws.
        s.add("Buy Gains Bonus", p.buy_gains(2 * p.possible_persuasion_gain()))
    elif ability == _PLACE_SPY_CONTRACT:
        s.add("Place Spy", p.spy_value().sum)
    elif ability == _RECALL_AGENT_CONTRACT:
        s.add("Recall Agent", p.recall_agent_value())
    elif ability == _BG_CONTRACT:
        s.add("BG Influence", p.gain_influence_value("bene_gesserit", 1, -1, False).sum)
    elif ability == _TSMF_CONTRACT:
        s.add("SG Influence", p.gain_influence_value("spacing_guild", 1, -1, False).sum)
        # The printed 3 Solari is counted again (app quirk, board.md §3.4).
        s.add("Contract Solari", p.solari_value(3))
    elif ability in _APPSTYLE_CONTRACT_ABILITIES:  # Bloodlines tokens only
        from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
            appstyle_contract_terms,
        )

        s.merge(appstyle_contract_terms(ability, contract, cast("Profile", p)))
    return s


def _tri(level: int) -> float:
    """ResourceMod's abundance mapping: Poor -3, above +3, no thresholds 0."""

    if level == 0:
        return -3.0
    return 3.0 if level > 0 else 0.0


def contract_specific_acquire_value(p: ProfileCore, contract: Entity) -> Summer:
    """``ContractAbility::SpecificAcquireValue @ 0x4d55450`` (board.md §3.4).

    With its helpers ``RewardValueMod @ 0x4d558e0``, ``AgentIconsMod @
    0x4d55b00``, ``ResourceMod @ 0x4d55f10``, ``SpyMod @ 0x4d56800``,
    ``BonusSpiceMod @ 0x4d56960`` and ``RoundMod @ 0x4d56b90``.
    """

    ctx = p.ctx
    constants = p.C
    s = Summer()
    kind = contract.attr("ContractType")
    if kind == "Immediate":
        s.add("Immediate RewardValue", contract_resource_value(p, contract).sum)
        return s
    if kind == "Alliance":  # Bloodlines Earn Any Alliance (bloodlines-cards.md §7)
        from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
            earn_alliance_acquire_value,
        )

        resource = contract_resource_value(p, contract).sum
        s.merge(earn_alliance_acquire_value(cast("Profile", p), resource))
        return s
    if kind not in ("Space", "Harvest", "Acquire"):
        return s
    spaces = contract_spaces(p, contract)

    def reward_value_mod() -> float:
        if kind == "Acquire":
            ratio = constants.AcquireContractRewardValueModRatio
        elif kind == "Harvest":
            ratio = constants.HarvestContractRewardValueModRatio
        else:
            ratio = constants.SpaceContractRewardValueModRatio
        reward = contract_resource_value(p, contract).sum
        # literals 9.0, 0.125, 0.25 (RewardValueMod)
        factor = max((9.0 - ctx.round_number) * 0.125, 0.25)
        return factor * (ratio * reward)

    def agent_icons_mod() -> float:
        icons = [
            str(sp.attr("AgentIcon")) for sp in spaces if _space_faction(sp) is not None
        ]
        if not icons:
            return 0.0
        deck = p.deck_agent_icons()
        n = sum(deck.get(icon, 0) for icon in icons)
        # literals +2 / 0 / -2 / -5 (AgentIconsMod)
        if n > 2:
            f = 2.0
        elif n == 1:
            f = -2.0
        elif n == 0:
            f = -5.0
        else:
            f = 0.0
        return f * constants.SpaceContractAgentIconsModRatio

    def resource_mod() -> float:
        if kind == "Space":
            ratio = constants.SpaceContractResourceModRatio
        elif kind == "Harvest":
            ratio = constants.HarvestContractResourceModRatio
        else:
            ratio = 0.0
        r = 0.0
        if any(sp.short in _SPICE_TRADE_SPACES for sp in spaces):
            r = _tri(p.abundance_level(Attr.SPICE))
        if any(sp.short in _HIGH_COUNCIL_SPACES for sp in spaces):
            r += _tri(p.abundance_level(Attr.SOLARI))
        if any(sp.short in _RESEARCH_STATION_SPACES for sp in spaces):
            r += _tri(p.abundance_level(Attr.WATER))
        if any(sp.short in _REFINERY_SPACES for sp in spaces):
            s1 = p.solari_value(1)
            r += -3.0 if 0.5 > s1 else (3.0 if s1 >= 0.9 else 0.0)  # literals
        if any(_has_bonus_spice_attr(sp) for sp in spaces):
            s1 = p.solari_value(1)
            r += -3.0 if 1.25 > s1 else (3.0 if s1 >= 1.8 else 0.0)  # literals
        return ratio * r

    def spy_mod() -> float:
        if any(_has_observing_spy(ctx.me, sp) for sp in spaces):
            return 2.0 * constants.SpaceContractSpyModRatio  # literal 2.0
        return 0.0

    def bonus_spice_mod() -> float:
        bonus = dict(ctx.state.maker_bonus_spice)
        total = sum(bonus.get(sp.ref, 0) for sp in spaces)
        # literal 0.33 (BonusSpiceMod)
        return constants.HarvestContractBonusSpiceModRatio * 0.33 * total

    def round_mod() -> float:
        arc = p.game_arc()
        f = 3.0 if arc == 2 else (-3.0 if arc == 0 else 0.0)  # literals
        return f * constants.AcquireContractRoundModRatio

    if kind == "Space":
        s.add("RewardValueMod", reward_value_mod())
        s.add("AgentIconsMod", agent_icons_mod())
        s.add("ResourceMod", resource_mod())
        s.add("SpyMod", spy_mod())
    elif kind == "Harvest":
        s.add("RewardValueMod", reward_value_mod())
        s.add("ResourceMod", resource_mod())
        s.add("BonusSpiceMod", bonus_spice_mod())
    else:  # Acquire
        s.add("RewardValueMod", reward_value_mod())
        seat = 3.0 if ctx.me.high_council else -3.0  # literals
        s.add("HighCouncilMod", seat * constants.AcquireContractHighCouncilModRatio)
        s.add("RoundMod", round_mod())
    return s


# =============================================================================
# The mixin
# =============================================================================


class InfluenceMixin(ProfileCore):
    """Overrides of the ProfileCore declarations for this area."""

    # -- 1. Influence -------------------------------------------------------------

    def gain_influence_value(
        self,
        faction: str,
        amount: int,
        current_rank: int = -1,
        has_alliance: bool = False,
    ) -> Summer:
        """``WormAIProfile::GetGainInfluenceValue @ 0x490a180`` (§1.1, §1.2).

        ``faction == NO_FACTION`` is the app's ``Factions.None``: the best
        (gain) or worst (loss) faction, dropping ``current_rank`` and
        ``has_alliance``. ``current_rank < 0`` reads the seat's influence and
        alliance; otherwise the given rank and ``has_alliance`` are used.
        """

        if faction == NO_FACTION:
            return self._any_faction_influence_value(amount)
        ctx = self.ctx
        me = ctx.me
        c = self.C
        s = Summer()
        s.add("Base", c.InfluenceValue * amount)  # amount is not clamped

        cur = current_rank
        if current_rank < 0:
            cur = _influence(me, faction)
            has_alliance = faction in me.alliance_faction_ids
            # b__0: a held intrigue whose influence ability names F (dead here).
            if any(
                _intrigue_grants_influence(iid, faction) for iid in ctx.intrigue_cards
            ):
                cur += 1
        new_rank = min(amount + cur, _TRACK_TOP)
        opp_max = _highest_opponent_rank(ctx, faction)

        # (A) one situational multiplier.
        if cur >= _TRACK_TOP and amount > 0:
            s.multiply("No Value", 0.0)
            return s  # nothing below is applied
        if amount > 0:
            self._gain_multiplier(
                s, faction, amount, cur, new_rank, opp_max, has_alliance
            )
        else:
            self._loss_multiplier(s, amount, cur, new_rank, opp_max, has_alliance)

        # (B) "Abilities Bonus": Alliance-keyword Imperium cards (dead here).
        n = sum(
            1
            for cid in _own_card_ids(ctx)
            for ability in card_entity(cid).ability_ids
            if _ALLIANCE_ABILITIES.get(ability) == faction
        )
        if n > 0 and (
            (has_alliance and cur - opp_max < 2)
            or (not has_alliance and opp_max <= 5 and opp_max - cur <= 2)
        ):
            s.multiply("Abilities Bonus", c.GainInfluenceCardAllianceBonusMod * n)

        # (C) track bonus when this change crosses into 4.
        if cur <= 3 and new_rank >= 4:
            if cast("Profile", self).friends_everywhere_active():
                # App-style Arrakeen Scouts (scouts.md §4.7, D29): Friends
                # Everywhere lets the seat take any track's bonus.
                s.add(
                    "Friends Everywhere",
                    cast("Profile", self).any_faction_four_bonus_value(),
                )
            elif faction == "emperor":
                if _UPRISING_ENABLED:
                    s.add("Resource Bonus(Spy)", self.spy_value().sum)
                else:
                    s.add("Resource Bonus (Troops)", 3.0)  # literal
            elif faction == "spacing_guild":
                s.add(
                    "Resource Bonus (Solari)",
                    self.resource_value(Attr.SOLARI, 3, False),
                )
            elif faction == "bene_gesserit":
                s.add("Resource Bonus (Intrigue)", self.intrigue_value())
            elif faction == "fremen":
                s.add(
                    "Resource Bonus (Water)", self.resource_value(Attr.WATER, 1, False)
                )

        # (D) other-set terms (inert in a 4-player Uprising game).
        leader_arch = _leader_archetype(ctx)
        if leader_arch == _GLOSSU_ARCH and not has_alliance:
            s.add("Glossu Bonus", c.GlossuRabbanInfluenceValueBonus)
        if _has_intrigue(ctx, _PLANS_WITHIN_PLANS):
            if cur <= 1:
                s.multiply("Plans Within Plans", c.PlansWithinPlansEarlyInfluenceMod)
            elif cur == 2:
                s.multiply(
                    "Plans Within Plans", c.PlansWithinPlansMeetRequisiteInfluenceMod
                )
        if _RISE_OF_IX_ENABLED:
            if (
                current_rank < 0
                and not self.is_climax()
                and faction == "spacing_guild"
                and cur <= 1
            ):
                s.multiply("Spacing Guild Rise of Ix", c.SpacingGuildRiseOfIxBonus)
            if cur <= 3 and _has_intrigue(ctx, _GRAND_CONSPIRACY) and new_rank >= 4:
                s.multiply("Grand Conspiracy", c.GrandConspiracyInfluenceMod)
            if _has_tech_tile(ctx, "Memocorders") and cur <= 2 and new_rank >= 3:
                s.multiply("Memocorders", c.MemocordersInfluenceMod)
            # Tessia's SnooperFactions: Rise of Ix leader, never dealt here.
            if leader_arch == _TESSIA_ARCH:
                s.multiply("Tessia Vernius", c.TessiaVerniusInfluenceMod)

        # (E) Uprising block.
        if not _UPRISING_ENABLED:
            return s
        leader = me.leader_id
        if leader == _MARGOT and faction == "bene_gesserit" and cur <= 1:
            s.add(
                "Lady Margot Fenring Spice",
                c.LadyMargoFenringBeneGesseritSpiceMod
                * (self.resource_value(Attr.SPICE, 1, False) * amount),
            )
        elif leader == _AMBER and not me.alliance_faction_ids:
            s.add(
                "Lady Amber Metulli Influence Mod",
                c.LadyAmberMetulliInfluenceMod * amount,
            )
        elif leader == _IRULAN and faction == "emperor" and cur <= 1:
            s.add("Princess Irulan Emperor Mod", c.PrincessIrulanEmperorMod * amount)
        elif (
            leader == _MUAD_DIB
            and faction == "fremen"
            and cur <= 1
            and not me.maker_hooks
            and self.opponent_maker_hooks_ratio() <= 0.5  # literal
            and not self.is_climax()
        ):
            s.multiply("Muad'Dib Fremen Mod", c.MuadDibFremenMod)
        elif leader == _YRKOON and cur <= 1:
            # Bloodlines Plot Course (bloodlines-systems.md §9, D43; the
            # Margot / Irulan shape: × amount, cur <= 1).
            s.add(
                "Steersman Y'rkoon Plot Course",
                cast("Profile", self).plot_course_value(faction, amount),
            )
        if (
            _has_intrigue(ctx, _DEPART_FOR_ARRAKIS)
            and faction == "spacing_guild"
            and cur <= 2
        ):
            s.add("Depart For Arrakis Mod", c.DepartForArrakisSGMod * amount)
        if _has_intrigue(ctx, _SHADDAMS_FAVOR) and faction == "emperor":
            s.add("Shaddam's Favor Mod", c.ShaddamsFavorEmperorMod * amount)
        if (
            _has_intrigue(ctx, _SHADOW_ALLIANCE)
            and new_rank >= 4
            and not _has_shadow_alliance(ctx)
        ):
            s.multiply("Shadow Alliance Mod", c.ShadowAllianceMod)
        if (
            _has_intrigue(ctx, _STRATEGIC_STOCKPILING)
            and faction == "fremen"
            and cur <= 2
        ):
            s.add(
                "Strategic Stockpiling Mod", c.StrategicStockpilingInfluenceMod * amount
            )
        if (
            _has_intrigue(ctx, _WEIRDING_COMBAT)
            and faction == "bene_gesserit"
            and cur <= 2
        ):
            s.add("Weirding Combat Mod", c.WeirdingCombatInfluenceMod * amount)
        if (
            faction == "fremen"
            and cur <= 1
            and not me.maker_hooks
            and not self.is_climax()
            and self.opponent_maker_hooks_ratio() <= 0.5  # literal
        ):
            s.multiply("Maker Hooks Fremen Mod", c.MakerHooksFremenMod)
        return s

    def _any_faction_influence_value(self, amount: int) -> Summer:
        """The ``Factions.None`` branch: ``Max``/``Min`` by ``Sum`` (b__2/b__3).

        .NET ``Max``/``Min`` over reference types keep the first extreme
        (strict comparison), in ``FactionList`` order.
        """

        best: Summer | None = None
        for faction in FACTIONS:
            value = self.gain_influence_value(faction, amount, -1, False)
            if best is None:
                best = value
            elif amount > 0 and value.sum > best.sum:
                best = value
            elif amount <= 0 and value.sum < best.sum:
                best = value
        assert best is not None
        return best

    def _gain_multiplier(
        self,
        s: Summer,
        faction: str,
        amount: int,
        cur: int,
        new_rank: int,
        opp_max: int,
        has_alliance: bool,
    ) -> None:
        """Section (A) for gains (``amount > 0``, ``cur < 6``): first match wins."""

        c = self.C
        d = cur - opp_max
        if has_alliance and d < 2:
            if d <= 0:
                s.multiply(
                    "Protect Threatened Alliance",
                    c.GainInfluenceDefendAllianceThreatenedMod,
                )
            else:
                s.multiply(
                    "Protect Threatened Alliance", c.GainInfluenceDefendAllianceMod
                )
        elif cur <= 1 and amount + cur >= 2:  # crosses the 2-influence VP
            if self.game_arc() > 1:
                s.multiply("Victory Point", c.GainInfluenceVictoryPointLateMod)
            else:
                s.multiply("Victory Point", c.GainInfluenceVictoryPointMod)
            if _has_tech_tile(self.ctx, "SpySatellites") and (
                sum(1 for f in FACTIONS if _influence(self.ctx.me, f) < 2) >= 2
            ):
                s.multiply("Spy Satellites", 0.0)
        elif cur <= opp_max and new_rank >= 4 and new_rank > opp_max:
            holder = _alliance_holder(self.ctx, faction)
            if holder is None:  # the token is still on the track
                if opp_max >= 3:
                    s.multiply(
                        "Gain Alliance Threat", c.GainInfluenceThreatenedAllianceMod
                    )
                elif self.game_arc() > 1:
                    s.multiply("Gain Alliance Late", c.GainInfluenceAllianceLateMod)
                else:
                    s.multiply("Gain Alliance", c.GainInfluenceAllianceMod)
            elif self.ctx.vp(holder) >= self.ctx.endgame_trigger_score:
                s.multiply(
                    "Steal Alliance Endgame", c.GainInfluenceStealAllianceEndgameMod
                )
            else:
                s.multiply("Steal Alliance", c.GainInfluenceStealAllianceMod)
        elif opp_max in (4, 5) and cur < opp_max and new_rank == opp_max:
            s.multiply("Threaten Alliance", c.GainInfluenceThreatenAllianceMod)
        elif has_alliance and d >= 2:
            s.multiply("Secure Alliance", c.GainInfluenceSecureAllianceMod)
        elif cur >= 4 and opp_max >= 6:
            s.multiply("Alliance Impossible", c.GainInfluenceAllianceImpossibleMod)
        elif (
            cur == 2
            and opp_max >= 4
            and not _has_intrigue(self.ctx, _PLANS_WITHIN_PLANS)
            and not _has_intrigue(self.ctx, _GRAND_CONSPIRACY)
            and not _has_tech_tile(self.ctx, "Memocorders")
        ):
            s.multiply("Alliance Unlikely", c.GainInfluenceAllianceUnlikelyMod)
        elif self.game_arc() != 0 and new_rank >= opp_max and amount > 0:
            s.multiply("Sieze Opening", c.GainInfluenceSeizeOpeningMod)

    def _loss_multiplier(
        self,
        s: Summer,
        amount: int,
        cur: int,
        new_rank: int,
        opp_max: int,
        has_alliance: bool,
    ) -> None:
        """Section (A) for ``amount <= 0`` (the ``LOSS`` label)."""

        c = self.C
        if has_alliance:
            if new_rank < 4 or new_rank < opp_max:
                s.multiply("Forfeit Alliance", c.LoseInfluenceForfeitAllianceMod)
            elif new_rank == opp_max:
                s.multiply("Forfeit Cushion", c.LoseInfluenceForfeitAllianceCushionMod)
        elif cur >= 2 and new_rank <= 1:
            s.multiply("Forfeit Victory Point", c.LoseInfluenceForfeitVictoryPoint)
        elif opp_max >= 6:
            s.multiply("Alliance Impossible", c.LoseInfluenceAllianceImpossibleMod)
        elif opp_max == 5 and cur == 3 and amount < 0:
            s.multiply("Alliance Unlikely", c.LoseInfluenceAllianceUnlikelyMod)

    def has_or_would_gain_alliance(self, faction: str, amount: int) -> bool:
        """``WormAIProfile::HasOrWouldGainAlliance @ 0x490c260`` (§1.3).

        Optimistic on ties (``>=``); no token check, no intrigue bump.
        """

        me = self.ctx.me
        if faction in me.alliance_faction_ids:
            return True
        if amount <= 0:
            return False
        opp_max = _highest_opponent_rank(self.ctx, faction)
        new_rank = min(_TRACK_TOP, _influence(me, faction) + amount)
        return new_rank >= 4 and new_rank >= opp_max

    def best_influence_exchange(
        self,
        lose_amount: int,
        gain_amount: int,
        lose_factions: Sequence[str] | None = None,
        gain_factions: Sequence[str] | None = None,
    ) -> tuple[str | None, str | None, float]:
        """``WormAIProfile::GetBestInfluenceExchange @ 0x490c380`` (§1.4).

        Shuffles both lists (the app shuffles the caller's lists in place;
        here copies), then keeps the first strictly best ``lose + gain``
        total above 0. ``(None, None, 0.0)`` when no exchange is worth > 0.
        """

        ctx = self.ctx
        me = ctx.me
        if lose_amount > 0:
            lose_amount = -lose_amount
        if lose_factions is None:  # b__0 @ 0x492b250
            lose_list = [f for f in FACTIONS if _influence(me, f) + lose_amount >= 0]
        else:
            lose_list = list(lose_factions)
        gain_list = list(FACTIONS) if gain_factions is None else list(gain_factions)
        self.rng.shuffle(lose_list)
        self.rng.shuffle(gain_list)
        lose_values = {
            f: self.gain_influence_value(f, lose_amount, -1, False) for f in lose_list
        }
        gain_values = {
            f: self.gain_influence_value(f, gain_amount, -1, False) for f in gain_list
        }
        best: tuple[str | None, str | None, float] = (None, None, 0.0)
        for lose in lose_list:
            for gain in gain_list:
                lose_value = lose_values[lose]
                gain_value = gain_values[gain]
                if lose == gain:  # re-evaluate the gain from the post-loss rank
                    rank = _influence(me, lose)
                    after = lose in me.alliance_faction_ids and (
                        rank + lose_amount >= _highest_opponent_rank(ctx, lose)
                    )
                    gain_value = self.gain_influence_value(
                        lose, gain_amount, rank + lose_amount, after
                    )
                total = lose_value.sum + gain_value.sum
                if total > best[2]:  # strict: first in shuffled order wins
                    best = (lose, gain, total)
        return best

    # -- 2. Spies ------------------------------------------------------------------

    def spy_value(self) -> Summer:
        """``WormAIProfile::SpyValue @ 0x490be50`` (§2.1)."""

        c = self.C
        s = Summer()
        s.add(
            "Base Spy Value", _arc(self, c.SpyValueEarly, c.SpyValueMid, c.SpyValueLate)
        )
        want_spy = _count_card_tags(self.ctx, frozenset({"WantSpy"}))
        s.multiply("WantSpy cards", 1.0 + 0.25 * want_spy)  # literals 1.0, 0.25
        deployed = len(self.ctx.me.spy_post_ids)
        s.multiply("SpyCount", 1.0 + -0.33 * deployed)  # literal -0.33
        if _has_intrigue(self.ctx, _SPRING_THE_TRAP):
            s.multiply("Spring the Trap", c.SpringTheTrapSpyMod)
        return s

    def recall_spy_value(self) -> Summer:
        """``WormAIProfile::RecallSpyValue @ 0x491b720`` (§2.2)."""

        me = self.ctx.me
        s = self.spy_value()
        s.multiply("-1 * SpyValue", -1.0)  # literal
        if _in_agent_turn(self.ctx) and not me.spies_recalled_turn > 0:
            n = sum(
                1
                for iid in me.in_play
                if "WantRecall" in card_entity(iid).list_attr("Tags")
            )
            s.add("WantRecall Cards", self.C.SpyRecallMod * n)
        return s

    def post_value(self, post: Entity, unseen_network: bool = False) -> float:
        """``WormObservationPost::PostValue @ 0x4837d80`` (§2.3).

        The Unseen Network terms read ``PostValueUnseenNetwork`` [379], not
        ``StabanTuekUnseenNetworkMod``.
        """

        ctx = self.ctx
        me = ctx.me
        c = self.C
        s = Summer()
        spaces = _observed_spaces(POST_INDEX[post.ref], ctx.board)
        icons = _distinct(str(sp.attr("AgentIcon")) for sp in spaces)
        faction = _distinct(_space_faction(sp) for sp in spaces)[0]
        deck = self.deck_agent_icons()
        n = sum(deck.get(icon, 0) for icon in icons)
        s.add("Matching Agent Icon", c.PostValueMatchingAgentIcon * n)
        staban = me.leader_id == _STABAN
        if faction is not None:
            s.add(f"Connected To {faction} Space", c.PostValueFactionSpace)
            if self.gain_influence_value(faction, 1, -1, False).sum >= 3.0:  # literal
                s.add(f"Value({faction}) >= 3", c.PostValueFactionSpaceHighValue)
            if "guild_spy" in _own_card_ids(ctx):
                s.add("Guild Spy in Deck", c.PostValueFactionSpaceGuildSpy)
            if (
                unseen_network
                and staban
                and me.resources.solari >= 2
                and self.intrigue_value() > self.solari_value(2)
            ):
                s.add("Unseen Network Faction", c.PostValueUnseenNetwork)
        elif (
            unseen_network
            and "Pentagon" in icons
            and staban
            and me.resources.spice > 0
            and self.solari_value(3) > self.spice_value(1)
        ):
            s.add("Unseen Network Pentagon", c.PostValueUnseenNetwork)
        if (
            any(sp.short in _SWORDMASTER_SPACES for sp in spaces)
            and not me.swordmaster_acquired
        ):
            s.add("Swordmaster", c.PostValueSwordmaster)
        if (
            any(sp.short == _INTERSTELLAR_SHIPPING for sp in spaces)
            and _influence(me, "spacing_guild") >= 2
        ):
            s.add("Interstellar Shipping", c.PostValueInterstellarShipping)
        if any(sp.short == _HAGGA_BASIN for sp in spaces) and me.maker_hooks:
            s.add("Hagga Basin", c.PostValueHaggaBasin)
        if (
            any(sp.short == _SIETCH_TABR for sp in spaces)
            and me.maker_hooks
            and _influence(me, "fremen") >= 2
        ):
            s.add("Sietch Tabr", c.PostValueSietchTabr)
        if (
            staban
            and any(_has_bonus_spice_attr(sp) for sp in spaces)
            and not any(
                _has_observing_spy(me, sp)
                for sp in _board_spaces(ctx.board)
                if _has_bonus_spice_attr(sp)
            )
            and not self.is_final_round()
        ):
            s.add("Staban Tuek Maker Post", c.StabanTuekPostMod)
        if ctx.scouts:  # app-style Arrakeen Scouts: Valued Informants (§4.3)
            s.merge(cast("Profile", self).valued_informants_post_value(post.ref))
        return s.sum

    def best_post(
        self, posts: Sequence[Entity], unseen_network: bool = False
    ) -> tuple[Entity | None, float]:
        """``WormAIProfile::GetBestPost @ 0x491d2d0`` (§2.4)."""

        chosen, value = self.post_selection(posts, 1, True, unseen_network)
        return (chosen[0] if chosen else None), value

    def post_selection(
        self,
        posts: Sequence[Entity],
        take: int,
        best: bool,
        unseen_network: bool = False,
    ) -> tuple[list[Entity], float]:
        """``WormAIProfile::GetPostSelection @ 0x491d390`` (§2.4).

        Shuffle, score, stable ``OrderBy(best ? -v : v)``, ``Take(take)``;
        returns the posts and the sum of their values.
        """

        shuffled = list(posts)
        self.rng.shuffle(shuffled)
        scored = [(p, self.post_value(p, unseen_network)) for p in shuffled]
        ordered = sorted(scored, key=(lambda t: -t[1]) if best else (lambda t: t[1]))
        chosen = ordered[:take] if take > 0 else []
        total = 0.0
        for _, value in chosen:  # Enumerable.Sum: sequential addition
            total += value
        return [p for p, _ in chosen], total

    def recall_spy(self, spies: Sequence[Entity]) -> tuple[Entity | None, float]:
        """``WormAIProfile::GetRecallSpy @ 0x491db00`` (§2.4)."""

        chosen, value = self.recall_spies(spies, 1)
        return (chosen[0] if chosen else None), value

    def recall_spies(
        self, spies: Sequence[Entity], take: int
    ) -> tuple[list[Entity], float]:
        """``WormAIProfile::GetRecallSpies @ 0x491dba0`` (§2.4).

        The spies on the ``take`` lowest-valued posts.
        """

        spy_list = list(spies)
        posts = [post_entity(spy.ref, spy.owner) for spy in spy_list]
        chosen, value = self.post_selection(posts, take, False, False)
        return [next(s for s in spy_list if s.ref == p.ref) for p in chosen], value

    # -- 3. CHOAM contracts -----------------------------------------------------------

    def want_contract_count(self) -> int:
        """``WormAIProfile::WantContractCount @ 0x491b990`` (§3.1)."""

        tags = {"WantContractX"}
        completed = len(self.ctx.me.completed_contract_ids)
        if completed <= 1:
            tags |= {"WantContract2", "WantContract4"}
        elif completed <= 3:
            tags |= {"WantContract4"}
        return _count_card_tags(self.ctx, frozenset(tags))

    def gain_contract_value(self) -> Summer:
        """``WormAIProfile::GainContractValue @ 0x491bb20`` (§3.2)."""

        c = self.C
        s = Summer()
        s.add(
            "Base Contract Value",
            _arc(self, c.ContractValueEarly, c.ContractValueMid, c.ContractValueLate),
        )
        s.multiply("Contract Mod", 1.0 + c.ContractMod * self.want_contract_count())
        return s

    def best_contract(
        self, contracts: Sequence[Entity], forced: bool
    ) -> tuple[Entity | None, float]:
        """``WormAIProfile::GetBestContract @ 0x491cf10`` (§3.3).

        Given order, strict keep-best; a forced pick worth <= 0 reports 1.0.
        """

        best_value = -sys.float_info.max if forced else 0.0  # -DBL_MAX literal
        best: Entity | None = None
        for contract in list(contracts):
            value = self.contract_acquire_value(contract).sum
            if value > best_value:
                best_value = value
                best = contract
        if best_value <= 0.0:
            return best, (1.0 if forced else best_value)
        return best, best_value

    def contract_acquire_value(self, contract: Entity) -> Summer:
        """``WormContractPlayable::AcquireValue @ 0x482a880`` (§3.4).

        The first ``ContractAbility``'s ``SpecificAcquireValue`` (board.md
        §3.4), ported here as ``contract_specific_acquire_value``.
        """

        return contract_specific_acquire_value(self, contract)

    # -- 4. Battle icons --------------------------------------------------------------

    def battle_icon_value(self, icon: str) -> Summer:
        """``WormAIProfile::GetBattleIconValue @ 0x491bcf0`` (§4).

        ``icon`` is the app name (``None``, ``Crysknife``, ``DesertMouse``,
        ``Ornithopter``, ``Wildcard``) or our id (``crysknife``, ...,
        ``wild``; ``""`` = none).
        """

        c = self.C
        s = Summer()
        s.add(
            "Base Battle Icon Value",
            _arc(
                self,
                c.BattleIconValueEarly,
                c.BattleIconValueMid,
                c.BattleIconValueLate,
            ),
        )
        app_icon = _app_battle_icon(icon)
        if app_icon == "None":
            return s
        # Bloodlines Ornithopter Fleet: every battle icon of the owner, wild
        # ones and the evaluated one included, is an Ornithopter (engine
        # fact, bloodlines-systems.md §9). Tech Module only.
        fleet = self.ctx.has_tech("ornithopter_fleet")
        if fleet:
            app_icon = "Ornithopter"
        if app_icon == "Wildcard":
            s.multiply("Match Mod Wildcard", c.MatchModWildcard)
            return s
        own = _battle_icon_list(self.ctx.me)
        if fleet:
            own = ["Ornithopter" for _ in own]
        crysknife = _has_intrigue(self.ctx, _CRYSKNIFE)
        desert_mouse = _has_intrigue(self.ctx, _DESERT_MOUSE)
        ornithopter = _has_intrigue(self.ctx, _ORNITHOPTER)
        if (
            app_icon in own
            or (app_icon == "Crysknife" and crysknife)
            or (app_icon == "DesertMouse" and desert_mouse)
            or (app_icon == "Ornithopter" and ornithopter)
        ):
            s.multiply("Match Mod Standard", c.MatchModStandard)
        return s

    # -- 5. Maker hooks ---------------------------------------------------------------

    def maker_hooks_value(self) -> float:
        """``WormAIProfile::MakerHooksValue @ 0x491c0c0`` (§5.1)."""

        ctx = self.ctx
        c = self.C
        if ctx.me.maker_hooks:
            return 0.0
        v = _arc(
            self, c.MakerHooksValueEarly, c.MakerHooksValueMid, c.MakerHooksValueLate
        )
        r = self.opponent_maker_hooks_ratio()
        if r > 0.5:  # literal, strict
            v *= c.HooksModHalfOfOpponents
        if r > 0.99:  # literal, strict
            v *= c.HooksModAllOpponents
        if _has_intrigue(ctx, _DETONATION):
            v *= c.DetonationHooksMod
        if _has_intrigue(ctx, _DEVOUR):
            v *= c.DevourHooksMod
        if _has_intrigue(ctx, _INSPIRE_AWE):
            v *= c.InspireAweHooksMod
        if _has_intrigue(ctx, _SPECIAL_MISSION):
            v *= c.SpecialMissionHooksMod
        if _has_intrigue(ctx, _UNEXPECTED_ALLIES):
            v *= c.UnexpectedAlliesHooksMod
        if ctx.me.leader_id == _MUAD_DIB and r <= 0.5:  # literal
            v *= c.MuadDibMakerHooksMod
        return v

    def opponent_maker_hooks_ratio(self) -> float:
        """``WormAIProfile::GetOpponentMakerHooksRatio @ 0x490c0e0`` (§0)."""

        opponents = self.ctx.opponents
        return sum(1 for o in opponents if o.maker_hooks) / len(opponents)

    # -- 7. Agent recall --------------------------------------------------------------

    def recall_agent_value(self) -> float:
        """``WormAIProfile::RecallAgentValue @ 0x491c600`` (§7.1).

        Bloodlines (bloodlines-systems.md D56, plan §11.7): Duncan's Into the
        Fray Agent in the Conflict counts as a deployed Agent.
        """

        if (
            not self.ctx.me.agent_locations
            and not cast("Profile", self).counts_conflict_agent()
        ):
            return -3.0  # literal
        c = self.C
        return _arc(
            self, c.RecallAgentValueEarly, c.RecallAgentValueMid, c.RecallAgentValueLate
        )

    def recall_agent(self, agents: Sequence[Entity]) -> Entity | None:
        """``WormAIProfile::GetRecallAgent @ 0x4912340`` (§7.2).

        Shuffle; non-combat non-faction space = 100 (last such wins); faction
        space trailing the top opponent by >= 2 = 75; else ``50 - space
        value``. None when nothing scores above 0.
        """

        ctx = self.ctx
        shuffled = list(agents)
        self.rng.shuffle(shuffled)
        best = 0.0
        pick: Entity | None = None
        for agent in shuffled:
            # a.Parent is not a WormSpace (Duncan's Conflict Agent, D55);
            # Esmar's Tuek's Sietch is a space (bloodlines-systems.md §6).
            if (
                agent.ref not in SPACE_ARCHETYPES
                and agent.ref not in BLOODLINES_SPACE_ARCHETYPES
            ):
                continue
            space = space_entity(agent.ref, ctx.board)
            combat = space.attr("CombatSpace", False) is True
            faction = _space_faction(space)
            if not combat and faction is None and space.short != _HALL_OF_ORATORY:
                best = 100.0  # literal; no comparison: the last one wins
                pick = agent
            elif (
                not combat
                and faction is not None
                and _highest_opponent_rank(ctx, faction) - _influence(ctx.me, faction)
                >= 2
            ):
                if 75.0 > best:  # literal, strict
                    best = 75.0
                    pick = agent
            else:
                s = Summer()
                s.add("Offset", 50.0)  # literal
                s.add("Space Abilities", -(self.space_value_for_player(space).sum))
                if s.sum > best:
                    best = s.sum
                    pick = agent
        return pick

    def space_value_for_player(self, space: Entity) -> Summer:
        """``WormSpace::ValueForPlayer @ 0x49c0c40`` (§7.2).

        The merge of every ability's ``ValueForPlayer(player, [])`` on the
        space, in archetype order.
        """

        # Imported here: the ability ports import the profile package.
        from dune_imperium.agents.app_ai.abilities import abilities_of

        profile = cast("Profile", self)
        total = Summer()
        for ability in abilities_of(space):
            total.merge(ability.value_for_player(profile, ()))
        return total

    # -- 6. Shield Wall ---------------------------------------------------------------

    def blow_wall_value(self) -> Summer:
        """``WormAIProfile::BlowWallValue @ 0x491c750`` (§6.1)."""

        ctx = self.ctx
        me = ctx.me
        c = self.C
        s = Summer()
        if not me.maker_hooks:
            s.multiply("No Maker Hooks", 0.0)
            return s
        s.add(
            "Base Contract Value",
            _arc(self, c.BlowWallValueEarly, c.BlowWallValueMid, c.BlowWallValueLate),
        )
        s.add("Water count", c.WallModWaterMod * me.resources.water)
        s.add("Spy count", float(len(me.spy_post_ids)))  # raw count
        hagga = _board_space(ctx.board, _HAGGA_BASIN)
        deep = _board_space(ctx.board, _DEEP_DESERT)
        if (
            me.agents_available >= 2
            and hagga is not None
            and deep is not None
            and (
                self.can_play_to_desert_space_with_hooks(ctx.seat, hagga.ref)
                or self.can_play_to_desert_space_with_hooks(ctx.seat, deep.ref)
            )
        ):
            s.add("Can Play to Desert Space", c.WallModSpaceMod)
        s.add("Has Maker Hooks", c.WallModHooksMod)
        # GarrisonTroops: Commanders count (bloodlines-systems.md §1.1 D1; 0
        # without Bloodlines).
        if (
            _has_intrigue(ctx, _DETONATION)
            and me.troops_garrison + me.commanders_garrison <= 3
        ):
            s.multiply("Detonation", c.DetonationBlowWallMod)
        s.multiply(
            "Opponent Hook Ratio",
            1.0 - self.opponent_ratio(lambda o: o.maker_hooks),  # b__152_2
        )
        return s

    def should_blow_wall(self) -> bool:
        """``WormAIProfile::ShouldBlowWall @ 0x491dfe0`` (§6.2)."""

        ctx = self.ctx
        if not ctx.me.maker_hooks:
            return False
        if not ctx.shield_wall_present:
            return False
        hook_opponents = [o for o in ctx.opponents if o.maker_hooks]
        if not hook_opponents:
            return True
        hagga = _board_space(ctx.board, _HAGGA_BASIN)
        deep = _board_space(ctx.board, _DEEP_DESERT)
        if all(
            hagga is not None
            and not self.can_play_to_desert_space_with_hooks(o.player_id, hagga.ref)
            and deep is not None
            and not self.can_play_to_desert_space_with_hooks(o.player_id, deep.ref)
            for o in hook_opponents
        ):
            return True
        # The app reads CurrentConflictInterest (0x491e45e) before
        # get_ConflictPostureBounds (0x491e475); keep that order.
        interest = self.current_conflict_interest().sum
        lower, _upper = self.conflict_posture_bounds()
        return lower >= interest

    def intrigue_blow_wall(self) -> bool:
        """``WormAIProfile::IntrigueBlowWall @ 0x491e4a0`` (§6.3).

        The last test reads the space's ``SandWorms`` and ``Spice``
        attributes. No Uprising desert space carries either (Hagga Basin and
        Deep Desert have ``PossibleSpice``), and nothing in the app writes
        them at run time, so the comparison is ``0 > 0`` and this returns
        False whenever the earlier gates pass (reproduced as is).
        """

        ctx = self.ctx
        if not ctx.me.maker_hooks:
            return False
        if not ctx.shield_wall_present:
            return False
        space_id = _active_space_id(ctx)
        if space_id is None or not is_board_space(space_id):
            return False
        space = space_entity(space_id, ctx.board)
        if not any(a in _DESERT_DEFERRED_ABILITIES for a in space.ability_ids):
            return False
        # IsExhausted: the spice-or-sandworm choice already resolved this turn.
        frame = ctx.own_frame_context("agent_effects") or {}
        pending = str(frame.get("pending_board_icons", "")).split(",")
        if "maker" not in pending:
            return False
        interest = self.current_conflict_interest().sum
        _lower, upper = self.conflict_posture_bounds()
        if not upper >= interest:
            return False
        spice = space.int_attr("Spice")
        spice_value = self.spice_value(1)
        sandworms = space.int_attr("SandWorms")
        sandworm_value = self.sandworm_value(1, False)
        return sandworms * sandworm_value > spice * spice_value

    # -- 8. Leaders -------------------------------------------------------------------

    def lady_jessica_return_memories(self) -> bool:
        """``WormAIProfile::LadyJessicaReturnMemories @ 0x491de50`` (§8.1)."""

        ctx = self.ctx
        me = ctx.me
        if me.leader_id != _JESSICA:
            return False
        if me.leader_face_id == _JESSICA_FLIPPED_FACE:  # Leader Flipped
            return False
        if len(me.intrigue_cards) > 2:  # literal
            return True
        if me.resources.water > 2:  # literal
            return True
        if me.memories > 1:  # literal
            return True
        return ctx.round_number >= 5  # literal


def _has_shadow_alliance(ctx: AppContext) -> bool:
    """``ShadowAllianceAbility::HasShadowAlliance(player) @ 0x4c4ee60``.

    Some faction whose Alliance another seat holds (b__2 @ 0x4c4f7d0) and on
    which this seat has 4 or more influence (b__1 @ 0x4c4f7a0).
    """

    me = ctx.me
    return any(
        _influence(me, f) >= 4
        for f in FACTIONS
        if any(f in o.alliance_faction_ids for o in ctx.opponents)
    )
