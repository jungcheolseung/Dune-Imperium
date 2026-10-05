"""Economy — spec/profile-economy.md.

The port of the ``WormAIProfile`` economy methods: game arc and climax,
resource values, card draws, the Buy Gains knapsack, ``AcquireValue`` and its
modifiers (icons, consolidation, synergy, friendship, acquire effects),
trashing, discarding and the turn-order helpers.

Faithfulness notes that apply to the whole module:

- ``AIProfileAbsUtils::Multiply`` appends ``m*Sum - Sum`` to the summer
  (spec §0.2, "NOT m*Sum"); ``_mul`` replays that exactly, like
  ``Summer.multiply``.
- .NET ``Enumerable.Sum`` over doubles adds left to right from 0.0; Python's
  ``sum`` compensates float error, so ``_dsum`` loops instead.
- Every number the app takes from an attribute is read from the app
  archetype (``Entity.attr``), never from our card data: Desert Power's
  ``Persuasion`` is 0 there, ours 2.
- Only the Uprising set (4) is on (``SetOn(4)``); the Rise of Ix (2) and
  Immortality (3) branches are dead in a 4-player Uprising game and are
  noted, not ported. BaseSet leaders/intrigues are compared by archetype name
  so their branches exist but can never be met with our content.
- Honesty: the own deck is read only as a multiset (iterated in sorted
  instance-id order), opponents only through public fields.
"""

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from dune_imperium.agents.app_ai.catalog import (
    CONTRACT_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    card_entity,
    conflict_entity,
    conflict_reward_entities,
    contract_entity,
    intrigue_entity,
)
from dune_imperium.agents.app_ai.context import card_id
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import Summer, app_round
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.ornithopter import face_up_battle_card_ids

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.abilities.base import Ability
    from dune_imperium.agents.app_ai.profile import Profile

# -- app archetype names the economy methods compare against ----------------------

_TSMF = frozenset(
    {
        "ImperiumArchetypes.BaseSet.TheSpiceMustFlow",
        "ImperiumArchetypes.Uprising.TheSpiceMustFlowUP",
    }
)  # IsTheSpiceMustFlowImperium
_CONVINCING_ARGUMENT = "ImperiumArchetypes.BaseSet.ConvincingArgument"
_GUILD_SPY = "ImperiumArchetypes.Uprising.GuildSpy"
_CONTRACT_BASE_20 = "ContractArchetypes.Uprising.ContractBase_20"
_SELL_MELANGE = "SpaceArchetypes.BaseSet.SellMelange"

# Intrigue archetypes (HasIntrigueCard).
_CHOAM_SHARES = "IntrigueArchetypes.BaseSet.CHOAMShares"
_SLEEPER_MUST_AWAKEN = "IntrigueArchetypes.BaseSet.TheSleeperMustAwaken"
_PRIVATE_ARMY = "IntrigueArchetypes.BaseSet.PrivateArmy"
_RAPID_MOBILIZATION = "IntrigueArchetypes.BaseSet.RapidMobilization"
_STAGED_INCIDENT = "IntrigueArchetypes.BaseSet.StagedIncident"
_CORNER_THE_MARKET = "IntrigueArchetypes.BaseSet.CornertheMarket"
_CALCULATED_HIRE = "IntrigueArchetypes.BaseSet.CalculatedHire"
_URGENT_MISSION = "IntrigueArchetypes.BaseSet.UrgentMission"
_PLANS_WITHIN_PLANS = "IntrigueArchetypes.BaseSet.PlansWithinPlans"
_BUY_ACCESS = "IntrigueArchetypes.Uprising.BuyAccess"
_MARKET_OPPORTUNITY = "IntrigueArchetypes.Uprising.MarketOpportunity"
_MERCENARIES = "IntrigueArchetypes.Uprising.Mercenaries"
_STRATEGIC_STOCKPILING = "IntrigueArchetypes.Uprising.StrategicStockpiling"
_UNEXPECTED_ALLIES = "IntrigueArchetypes.Uprising.UnexpectedAllies"
_DETONATION = "IntrigueArchetypes.Uprising.Detonation"
_DEVOUR = "IntrigueArchetypes.Uprising.Devour"
_INSPIRE_AWE = "IntrigueArchetypes.Uprising.InspireAwe"
_SPECIAL_MISSION = "IntrigueArchetypes.Uprising.SpecialMission"
_SECURE_SPICE_TRADE = "IntrigueArchetypes.Uprising.SecureSpiceTrade"

# Leader archetypes (P.Leader == X).
_GLOSSU_RABBAN = "LeaderArchetypes.BaseSet.GlossuTheBeastRabban"
_DUKE_LETO = "LeaderArchetypes.BaseSet.DukeLetoAtreides"
_EARL_MEMNON = "LeaderArchetypes.BaseSet.EarlMemnonThorvald"
_COUNTESS_ARIANA = "LeaderArchetypes.BaseSet.CountessArianaThorvald"
_MUAD_DIB = "LeaderArchetypes.Uprising.MuadDib"
_STABAN_TUEK = "LeaderArchetypes.Uprising.StabanTuek"
_WANT_SPY_LEADERS = frozenset(
    {
        "LeaderArchetypes.Uprising.FeydRauthaHarkonnen",
        "LeaderArchetypes.Uprising.LadyMargotFenring",
    }
)

# Ability classes (full app names) whose class derives from
# ``PlayAbilities.RevealAbility`` / ``PlayAbilities.AgentAbility``, for every
# personal card of a 4-player Uprising game (worked out from the type
# listing ``dump/worm-canis.dll.cs``). Each such card has exactly one of each.
_PLAY = "worm.canis.abilities.PlayAbilities."
_REVEAL_BASE = _PLAY + "RevealAbility"
_DESERT_POWER_REVEAL = _PLAY + "Uprising.DesertPowerRevealAbility"
_BG_OPERATIVE_REVEAL = _PLAY + "Uprising.BeneGesseritOperativeRevealAbility"
_CALCULUS_REVEAL = _PLAY + "Uprising.CalculusofPowerRevealAbility"
_INTERSTELLAR_REVEAL = _PLAY + "Uprising.InterstellarTradeRevealAbility"
_PARACOMPASS_REVEAL = _PLAY + "Uprising.ParacompassRevealAbility"
_SARDAUKAR_COORD_REVEAL = _PLAY + "Uprising.SardaukarCoordinationRevealAbility"
_SOUTHERN_ELDERS_REVEAL = _PLAY + "Uprising.SouthernEldersRevealAbility"
_LIET_KYNES_REVEAL = _PLAY + "BaseSet.LietKynesRevealAbility"
_THUFIR_REVEAL = _PLAY + "BaseSet.ThufirHawatRevealAbility"
_IN_HIGH_PLACES_REVEAL = _PLAY + "BaseSet.InHighPlacesRevealAbility"
_UNDERCOVER_REVEAL = _PLAY + "BaseSet.UndercoverAssetRevealAbility"
_REVEAL_CLASSES = frozenset(
    {
        _REVEAL_BASE,
        _DESERT_POWER_REVEAL,
        _BG_OPERATIVE_REVEAL,
        _CALCULUS_REVEAL,
        _INTERSTELLAR_REVEAL,
        _PARACOMPASS_REVEAL,
        _SARDAUKAR_COORD_REVEAL,
        _SOUTHERN_ELDERS_REVEAL,
        _LIET_KYNES_REVEAL,
        _THUFIR_REVEAL,
        _IN_HIGH_PLACES_REVEAL,
        _UNDERCOVER_REVEAL,
    }
)
_AGENT_CLASSES = frozenset(
    {
        _PLAY + "AgentAbility",
        _PLAY + "BaseSet.PowerPlayAgentAbility",
        _PLAY + "BaseSet.SeekAlliesAgentAbility",
        _PLAY + "Uprising.WeirdingWomanAgentAbility",
    }
)

# Conflict-card ``DeferredAbility`` classes overriding ``GetPossibleConflictVP``
# (board.md §2.4.2 / §2.4.6): (SpiceCost, SolariCost) of a Pay-X-to-gain-1-VP
# ability, or None for Recall2SpiesVPAbility.
_CONFLICT_VP_ABILITIES: Mapping[str, tuple[int, int] | None] = {
    "worm.canis.abilities.ConflictAbilities.Uprising.Pay3SpiceToGain1VPAbility": (
        3,
        0,
    ),
    "worm.canis.abilities.ConflictAbilities.Uprising.Pay4SpiceToGain1VPAbility": (
        4,
        0,
    ),
    "worm.canis.abilities.ConflictAbilities.Uprising.Pay6SolariToGain1VPAbility": (
        0,
        6,
    ),
    "worm.canis.abilities.ActivatedAbilities.Uprising.Recall2SpiesVPAbility": None,
}

# Our battle icons -> the app's ``BattleIcons`` names.
_APP_BATTLE_ICONS: Mapping[str, str] = {
    "crysknife": "Crysknife",
    "desert_mouse": "DesertMouse",
    "ornithopter": "Ornithopter",
    "wild": "Wildcard",
}
# GetFriendshipMod jump table @0x490e2b4 (tags 11..19): (kind, faction).
_FRIENDSHIP_TAGS: Mapping[str, tuple[str, str]] = {
    "FremenInfluence": ("influence", "fremen"),
    "FremenAlliance": ("alliance", "fremen"),
    "SpacingGuildAlliance": ("alliance", "spacing_guild"),
    "EmperorAlliance": ("alliance", "emperor"),
    "SpacingGuildInfluence": ("influence", "spacing_guild"),
    "EmperorInfluence": ("influence", "emperor"),
    "BeneGesseritInfluence": ("influence", "bene_gesserit"),
    "BeneGesseritAlliance": ("alliance", "bene_gesserit"),
}
# GetAcquireEffectsValue jump table @0x490ea24: AcquireEffects -> faction id
# of the GetGainInfluenceValue(F, 1, -1, false) term.
_RANK_EFFECTS: Mapping[str, str] = {
    "RankE": "emperor",
    "RankSG": "spacing_guild",
    "RankBG": "bene_gesserit",
    "RankF": "fremen",
}
# The app's ``Factions.None`` ("best faction") as ``gain_influence_value``
# spells it (``influence.NO_FACTION``). No Uprising card has ``AnyRank`` in its
# AcquireEffectList, so the branch is dead in our games.
_ANY_FACTION = "none"

# Synergy: GetSynergyMod reads intrigue/contract abilities among the cards'
# *direct* children, where none live (spec §7.1, [I] structural), so they add
# nothing. Kept as a switch in case the inference is refuted.
SYNERGY_READS_HELD_CARD_ABILITIES = False

# The Uprising reserve in ``Decks::UprisingReserveDeck`` order after
# ``Distinct()`` (Foldspace, absent here, is excluded by the buy helpers).
_RESERVE_ORDER = ("prepare_the_way", "the_spice_must_flow")


def _mul(s: Summer, factor: float, reason: str) -> None:
    """``AIProfileAbsUtils::Multiply @0x9cd920``: ``s.Add(m*Sum - Sum)``.

    Spec §0.2: the new sum is ``Sum + (m*Sum - Sum)``, not ``m*Sum``.
    """

    s.add(reason, factor * s.sum - s.sum)


def _dsum(values: Sequence[float]) -> float:
    """``Enumerable.Sum<double>``: left to right from 0.0, uncompensated."""

    total = 0.0
    for value in values:
        total += value
    return total


def _to_decimal(value: float) -> Decimal:
    """``Convert.ToDecimal(double)``: rounded to 15 significant digits."""

    return Decimal(format(value, ".15g"))


def _knapsack(
    items: Sequence[tuple[Entity, int, float]], max_weight: int
) -> list[tuple[Entity, float]]:
    """``AIAlgorithmUtil.KnapsackSolver`` (``<KnapsackSolver>d__3::MoveNext``
    @0x2ac1610), spec §5.4: a 0/1 knapsack over decimal values.

    Returns the chosen items in yield order (descending item index) with
    their double value. Ties keep the lowest item indices.
    """

    if max_weight < 0:  # "maxWeight cannot be negative": yields nothing
        return []
    count = len(items)
    values = [_to_decimal(value) for _, _, value in items]
    zero = Decimal(0)
    table = [[zero] * (max_weight + 1)]
    for i in range(1, count + 1):
        weight = items[i - 1][1]
        value = values[i - 1]
        previous = table[i - 1]
        row = [zero] * (max_weight + 1)
        for w in range(1, max_weight + 1):
            if weight > w:  # strict >
                row[w] = previous[w]
            else:
                row[w] = max(previous[w], previous[w - weight] + value)
        table.append(row)
    chosen: list[tuple[Entity, float]] = []
    current_value = table[count][max_weight]
    current_weight = max_weight
    i = count
    while i > 0 and current_value > zero:
        if current_value == table[i - 1][current_weight]:
            i -= 1
            continue
        current_value -= values[i - 1]
        current_weight -= items[i - 1][1]
        chosen.append((items[i - 1][0], items[i - 1][2]))
        i -= 1
    return chosen


def _battle_icon_list(player: PlayerState) -> list[str]:
    """``WormPlayer.BattleIconList``: icons of the face-up battle cards.

    R5 §4.5: the Objective and won Conflict cards still face up (paired ones
    are flipped down), in app ``BattleIcons`` names.
    """

    icons: list[str] = []
    for battle_card in face_up_battle_card_ids(player):
        objective = OBJECTIVES_BY_ID.get(battle_card)
        icon = (
            objective.battle_icon
            if objective is not None
            else CONFLICTS_BY_ID[battle_card].battle_icon
        )
        if icon is not None:
            icons.append(_APP_BATTLE_ICONS[str(icon)])
    return icons


class EconomyMixin(ProfileCore):
    """Overrides of the ProfileCore declarations for this area."""

    # ===========================================================================
    # Honest state reads (AppContext rules) shared by the methods below
    # ===========================================================================

    def _profile(self) -> Profile:
        """``self`` as the full ``Profile`` the ability hooks expect."""

        return cast("Profile", self)

    def _own_reveal_context(self) -> Mapping[str, ActionValue] | None:
        """This seat's open Reveal frame (``IsInPlayerTurn(RevealTurn)``)."""

        return self.ctx.own_frame_context("reveal")

    def _in_reveal_turn(self) -> bool:
        """``WormPlayer::IsInPlayerTurn(RevealTurn = 2)`` for this seat.

        Judgement: our engine has no ``PlayerTurn`` attribute; the seat is in
        its Reveal turn while its own REVEAL frame is open.
        """

        return self._own_reveal_context() is not None

    def _persuasion_pool(self) -> int:
        """``P.GetAttributeValue<int>(Persuasion, 0)``: the live pool.

        Our engine keeps Persuasion only inside the Reveal frame (the
        spendable rest after purchases); outside it the pool is 0.
        """

        context = self._own_reveal_context()
        if context is None:
            return 0
        value = context.get("persuasion")
        if isinstance(value, bool) or not isinstance(value, int):
            return 0
        return value

    def _intrigue_shorts(self) -> list[str]:
        """App archetypes of the held Intrigue (``P.IntrigueHand``)."""

        return [
            INTRIGUE_ARCHETYPES.get(card_id(instance), "")
            for instance in self.ctx.intrigue_cards
        ]

    def _has_intrigue(self, archetype: str) -> bool:
        """``WormPlayer::HasIntrigueCard @0x4835970``."""

        return archetype in self._intrigue_shorts()

    def _leader_short(self) -> str:
        """The app archetype of this seat's Leader (``P.Leader.ArchID``)."""

        return LEADER_ARCHETYPES.get(self.ctx.me.leader_id or "", "")

    def _influence(self, player: PlayerState, faction: str) -> int:
        """``GetFactionInfluence(f)`` (our faction id)."""

        return int(getattr(player.influence, faction))

    def _own_cards(self, *zones: tuple[str, ...]) -> list[Entity]:
        """Own personal cards of ``zones`` as entities, in zone order."""

        seat = self.ctx.seat
        return [card_entity(instance, seat) for zone in zones for instance in zone]

    def _deck_cards(self) -> list[Entity]:
        """The own draw pile as a multiset (sorted instance ids, never order)."""

        return self._own_cards(tuple(sorted(self.ctx.me.deck)))

    def _all_imperium_cards(self) -> list[Entity]:
        """``WormPlayer::get_AllImperiumCards @0x4835810``.

        Deck ++ Hand ++ Discard ++ PlayArea ++ ActiveAgentArea (our ``in_play``
        holds both play areas).
        """

        me = self.ctx.me
        return [
            *self._deck_cards(),
            *self._own_cards(me.hand, me.discard_pile, me.in_play),
        ]

    def _row_cards(self) -> list[Entity]:
        """``ImperiumAndReserveRowCards(M, includeFoldspace=false)`` @0x480f380.

        Imperium Row order, then one entity per non-empty reserve pile
        (``reserve:<card_id>``). Judgement: the app's ``ReserveRow`` holds one
        entity per archetype (``Distinct()``, spec §5.2 [I]); an empty pile is
        left out because nothing can be bought from it.
        """

        cards = [card_entity(instance) for instance in self.ctx.imperium_row]
        remaining = dict(self.ctx.reserve_stacks)
        for reserve_id in _RESERVE_ORDER:
            if remaining.get(reserve_id, 0) > 0:
                cards.append(card_entity(f"reserve:{reserve_id}"))
        return cards

    def _abilities(self, card: Entity) -> tuple[Ability, ...]:
        """``WormPlayable::get_Abilities``: the card's ability ports in order."""

        from dune_imperium.agents.app_ai.abilities import abilities_of

        return abilities_of(card)

    # ===========================================================================
    # §1 Game arc
    # ===========================================================================

    def game_arc(self) -> int:
        """``WormAIProfile::GetGameArc @0x4904790`` (spec §1.1).

        0 Early (rounds 1-3), 1 Mid (4-6), 2 Late (7+ or climax).
        """

        if self.is_climax():
            return 2
        round_number = self.ctx.round_number
        if round_number > 6:  # strict >
            return 2
        return 1 if round_number >= 4 else 0

    def is_climax(self) -> bool:
        """``WormAIProfile::get_IsClimax @0x4903d50`` (spec §1.2).

        Cached in ``_isClimax`` for the decision.
        """

        if self._is_climax is not None:
            return self._is_climax
        trigger = self.ctx.endgame_trigger_score
        players = self.ctx.players
        if any(self.ctx.vp(p) >= trigger - 1 for p in players):  # b__0: >=
            result = True
        elif sum(1 for p in players if self.ctx.vp(p) >= trigger - 2) > 1:
            result = True  # b__1: >= ; count strict > 1
        elif self.ctx.conflict_deck_size < 2:  # strict <
            result = True
        else:
            result = any(  # b__2: >=
                self.possible_end_of_round_score(seat) >= trigger
                for seat in self.current_combat_order()[:2]
            )
        self._is_climax = result
        return result

    def is_final_round(self) -> bool:
        """``WormAIProfile::get_IsFinalRound @0x49043f0`` (spec §1.3).

        Reads ``_isFinalRound`` but never writes it (the app's own quirk), so
        the value is always recomputed.
        """

        if self._is_final_round is not None:
            return self._is_final_round
        trigger = self.ctx.endgame_trigger_score
        if self._is_endgame(trigger):
            return True
        return any(
            self.possible_end_of_round_score(seat) >= trigger
            for seat in self.current_combat_order()[:2]
        )

    def _is_endgame(self, trigger: int) -> bool:
        """``WormMatch::IsEndgame @0x48019c0`` (non-campaign)."""

        if self.ctx.conflict_deck_size == 0:
            return True
        return any(self.ctx.vp(p) >= trigger for p in self.ctx.players)

    def possible_end_of_round_score(self, seat: int) -> int:
        """``WormAIProfile::GetPossibleEndOfRoundScore @0x49045d0`` (spec §1.2)."""

        player = self.ctx.player(seat)
        score = self.ctx.vp(player)
        conflict = self.ctx.current_conflict_id
        if conflict is None:
            return score
        score += self._possible_combat_reward_vp(conflict, player, False)
        # SetOn(4) (Uprising) is on in every game we play.
        if player.sandworms_conflict > 0:  # any(p.ConflictSandworms)
            # The 1st-place reward again, with doubleCost = true.
            score += self._possible_combat_reward_vp(conflict, player, True)
        icon = conflict_entity(conflict, self.ctx.choam).attr("BattleIcon")
        if icon in _battle_icon_list(player):  # List.Contains: +1 once
            score += 1
        return score

    def _possible_combat_reward_vp(
        self, conflict: str, player: PlayerState, double_cost: bool
    ) -> int:
        """``WormConflictPlayable::GetPossibleCombatRewardVP(p, 1, doubleCost)``
        @0x482a460 -> ``GenericConflictAbility::GetPossibleRewardVP`` @0x4b71240.

        The 1st-place reward's ``VictoryPoints`` plus, for each of its custom
        ability ids, ``GetPossibleConflictVP`` of the first ``DeferredAbility``
        of the conflict card with that id (board.md §2.4.2 / §2.4.6).
        """

        card = conflict_entity(conflict, self.ctx.choam)
        rewards = conflict_reward_entities(conflict, self.ctx.choam)
        if not rewards:
            return 0
        reward = rewards[0]  # ConflictPlace ?? 1
        vp = reward.int_attr("VictoryPoints")
        card_abilities = card.ability_ids
        for custom in reward.list_attr("CustomAbilityIDs"):
            if custom not in card_abilities or custom not in _CONFLICT_VP_ABILITIES:
                continue  # no DeferredAbility of the card with that id
            costs = _CONFLICT_VP_ABILITIES[custom]
            if costs is None:
                # Recall2SpiesVPAbility::GetPossibleConflictVP @0x4d52820
                if not double_cost and len(player.spy_post_ids) >= 2:
                    vp += 1
                continue
            # PayAttributeToGainVPAbility::GetPossibleConflictVP @0x4b72d20
            spice_cost, solari_cost = costs
            shift = 1 if double_cost else 0
            if (
                player.resources.spice >= spice_cost << shift
                and player.resources.solari >= solari_cost << shift
            ):
                vp += 1
        return vp

    def select_for_game_arc(self, choices: Sequence[float]) -> float:
        """``WormAIProfile::SelectForGameArc @0x4908c80`` (spec §1.4)."""

        if len(choices) < 3:  # strict <
            return 0.0
        return choices[self.game_arc()]

    # ===========================================================================
    # §2 Tables and abundance
    # ===========================================================================

    def _values_dict(self) -> dict[Attr, tuple[float, float, float]]:
        """``WormAIProfile::get_ValuesDict @0x4904800`` (spec §2.1)."""

        c = self.C
        return {
            Attr.PERSUASION: (
                c.PersuasionValueEarly,
                c.PersuasionValueMid,
                c.PersuasionValueLate,
            ),
            Attr.STRENGTH: (
                c.StrengthValueEarly,
                c.StrengthValueMid,
                c.StrengthValueLate,
            ),
            Attr.SOLARI: (c.SolariValueEarly, c.SolariValueMid, c.SolariValueLate),
            Attr.SPICE: (c.SpiceValueEarly, c.SpiceValueMid, c.SpiceValueLate),
            Attr.WATER: (c.WaterValueEarly, c.WaterValueMid, c.WaterValueLate),
            Attr.TROOPS: (c.TroopValueEarly, c.TroopValueMid, c.TroopValueLate),
            Attr.DREADNOUGHT: (c.DreadnoughtEarly, c.DreadnoughtMid, c.DreadnoughtLate),
            Attr.SPECIMEN: (
                c.SpecimenValueEarly,
                c.SpecimenValueMid,
                c.SpecimenValueLate,
            ),
            Attr.SANDWORMS: (
                c.SandwormValueEarly,
                c.SandwormValueMid,
                c.SandwormValueLate,
            ),
        }

    def _abundance_thresholds(self) -> dict[Attr, tuple[float, float, float]]:
        """``WormAIProfile::get_AbundanceThresholdDict @0x4905120`` (spec §2.2)."""

        c = self.C
        return {
            Attr.SOLARI: (
                c.SolariNormalThreshold,
                c.SolariRichThreshold,
                c.SolariFloodedThreshold,
            ),
            Attr.SPICE: (
                c.SpiceNormalThreshold,
                c.SpiceRichThreshold,
                c.SpiceFloodedThreshold,
            ),
            Attr.WATER: (
                c.WaterNormalThreshold,
                c.WaterRichThreshold,
                c.WaterFloodedThreshold,
            ),
            Attr.TROOPS: (
                c.TroopNormalThreshold,
                c.TroopRichThreshold,
                c.TroopFloodedThreshold,
            ),
            Attr.SPECIMEN: (
                c.SpecimenNormalThreshold,
                c.SpecimenRichThreshold,
                c.SpecimenFloodedThreshold,
            ),
            Attr.INTRIGUE_CARD: (
                c.IntrigueNormalThreshold,
                c.IntrigueRichThreshold,
                c.IntrigueFloodedThreshold,
            ),
        }

    def _stock(self, attr: Attr) -> int:
        """``P.GetAttributeValue<int>(attr, 0)`` for the stocked resources."""

        me = self.ctx.me
        if attr is Attr.SOLARI:
            return me.resources.solari
        if attr is Attr.SPICE:
            return me.resources.spice
        if attr is Attr.WATER:
            return me.resources.water
        if attr is Attr.SPECIMEN:
            return me.specimens
        if attr is Attr.VICTORY_POINTS:
            return self.ctx.vp(me)
        return 0

    def abundance_level(self, attr: Attr) -> int:
        """``WormAIProfile::GetAbundanceLevel @0x4905770`` (spec §2.3).

        0 Poor, 1 Supplied, 2 Rich, 3 Flooded; -1 without thresholds.
        """

        thresholds = self._abundance_thresholds().get(attr)
        if thresholds is None:
            return -1
        if attr is Attr.TROOPS:
            have = self.ctx.me.troops_garrison  # GarrisonTroops
        elif attr is Attr.INTRIGUE_CARD:
            have = len(self.ctx.intrigue_cards)  # IntrigueHandCount
        else:
            have = self._stock(attr)
        for index, threshold in enumerate(thresholds):
            if have < threshold:  # strict <
                return index
        return len(thresholds)

    # ===========================================================================
    # §3 GetResourceValue and its wrappers
    # ===========================================================================

    def resource_value(
        self, attr: Attr, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``WormAIProfile::GetResourceValue @0x4905940`` (spec §3).

        Rise of Ix (Princess Yuna, Advanced Weaponry, War Chest, techs,
        Dreadnought supply), Immortality (Economic Positioning, Specimen
        Tleilaxu bonus) branches: dead (sets 2/3 off).
        """

        s = Summer()
        if amount == 0:
            return 0.0
        me = self.ctx.me
        c = self.C
        values = self._values_dict().get(attr)
        if values is not None:
            if (
                attr is Attr.STRENGTH
                and me.troops_conflict + me.sandworms_conflict == 0  # ConflictUnits
                and me.agents_available <= 1  # RemainingAgents.Count()
            ):
                return s.sum
            s.add("Base Value", values[self.game_arc()])
            not_late_solari = self.game_arc() < 2 or attr is not Attr.SOLARI
            level = self.abundance_level(attr)
            if level == 0:
                _mul(s, c.PoorMod, "Poor")
            elif level == 1:
                _mul(s, 1.0, "Supplied")  # literal
            elif level == 2:
                _mul(s, c.RichMod, "Rich")
                if not not_late_solari:
                    _mul(s, c.RichMod, "Late Game")
            elif level == 3:
                _mul(s, c.FloodedMod, "Flooded")
                if not not_late_solari:
                    _mul(s, c.FloodedMod, "Late Game")

            if attr is Attr.SOLARI:
                if self.game_arc() <= 1:
                    if not me.high_council:
                        _mul(s, c.SolariMissingHighCouncilMod, "Missing High Council")
                    if not me.swordmaster_acquired:
                        _mul(s, c.SolariMissingSwordmasterMod, "Missing Swordmaster")
                if self._has_intrigue(_CHOAM_SHARES):
                    _mul(s, c.ChoamSharesSolariMod, "Choam Shares")
                # SetOn(4):
                if self._has_intrigue(_BUY_ACCESS):
                    _mul(s, c.BuyAccessSolariMod, "Buy Access Mod")
                if self._has_intrigue(_MARKET_OPPORTUNITY):
                    _mul(s, c.MarketOpportunitySolariMod, "Market Opportunity Mod")
                if self._has_intrigue(_MERCENARIES):
                    _mul(s, c.MercenariesSolariMod, "Mercenaries Mod")

            if include_combat_posture_mod and attr in (
                Attr.STRENGTH,
                Attr.TROOPS,
                Attr.DREADNOUGHT,
                Attr.SANDWORMS,
            ):
                # Dead in the app: every caller passes false (spec §3.2).
                _mul(s, self.combat_posture_mod(), "Combat Posture")

            leader = self._leader_short()
            if attr is Attr.TROOPS and leader == _GLOSSU_RABBAN:
                _mul(s, c.GlossuRabbanTroopsValueMod, "Glossu Rabban")

            if attr is Attr.SPICE:
                if leader == _DUKE_LETO:
                    _mul(s, c.DukeLetoAtreidesSpiceValueMod, "Duke Leto")
                if leader == _EARL_MEMNON:
                    _mul(s, c.EarlMemnonThorvaldSpiceValueMod, "Earl Memnon")
                if self._has_intrigue(_SLEEPER_MUST_AWAKEN):
                    _mul(s, c.TheSleeperMustAwakenSpiceMod, "Sleeper Must Awaken")
                if self._has_intrigue(_PRIVATE_ARMY):
                    _mul(s, c.PrivateArmySpiceMod, "Private Army")
                # SetOn(4):
                if self._has_intrigue(_MARKET_OPPORTUNITY):
                    _mul(s, c.MarketOpportunitySpiceMod, "Market Opportunity Mod")
                if self._has_intrigue(_STRATEGIC_STOCKPILING):
                    _mul(
                        s,
                        c.StrategicStockpilingSpiceMod,
                        "Strategic Stockpiling Mod",
                    )

            if attr is Attr.WATER:
                if leader == _COUNTESS_ARIANA:
                    _mul(s, c.CountessArianaThorvaldWaterValueMod, "Countess Ariana")
                # SetOn(4):
                if me.maker_hooks:
                    _mul(s, c.WaterHooksMod, "Water Hooks Mod")
                if (
                    self._has_intrigue(_STRATEGIC_STOCKPILING)
                    and self._influence(me, "fremen") >= 2
                ):
                    _mul(
                        s,
                        c.StrategicStockpilingWaterMod,
                        "Strategic Stockpiling Mod",
                    )
                if self._has_intrigue(_UNEXPECTED_ALLIES):
                    _mul(s, c.UnexpectedAlliesWaterMod, "Unexpected Allies Mod")

            if attr is Attr.TROOPS:
                if self._has_intrigue(_RAPID_MOBILIZATION):
                    _mul(s, c.RapidMobilizationTroopMod, "Rapid Mobilization")
                if (
                    self._has_intrigue(_STAGED_INCIDENT)
                    and c.StagedIncidentDeployedTroopThreshold >= me.troops_conflict
                    and c.StagedIncidentTotalTroopThreshold
                    >= me.troops_conflict + me.troops_garrison
                ):
                    _mul(s, c.StagedIncidentTroopMod, "Staged Incident")
                # Capped at the troops left in the supply (after the mods).
                amount = min(amount, me.troops_supply)

            if attr is Attr.SANDWORMS:  # SetOn(4)
                interest = self.current_conflict_interest().sum  # always computed
                if leader == _MUAD_DIB:
                    s.add("Muad'Dib Intrigue", self.intrigue_value())
                if (
                    self._has_intrigue(_DETONATION)
                    and me.maker_hooks
                    and interest >= self.conflict_posture_bounds()[0]
                ):
                    s.add("Detonation SandWorm Mod", c.DetonationSandWormMod)
                if self._has_intrigue(_DEVOUR):
                    _mul(s, c.DevourSandWormMod, "Devour SandWorm Mod")
                if self._has_intrigue(_INSPIRE_AWE):
                    _mul(s, c.InspireAweSandWormMod, "Devour SandWorm Mod")
                if (
                    self._has_intrigue(_SPECIAL_MISSION)
                    and me.maker_hooks
                    and interest >= self.conflict_posture_bounds()[0]
                ):
                    s.add("Special Mission SandWorm Mod", c.SpecialMissionSandWormMod)

        # AMOUNT:
        _mul(s, float(amount), "Amount")
        if attr is Attr.PERSUASION:
            s.add("Buy Gains", self.buy_gains(amount))
        return s.sum

    def persuasion_value(self, amount: int) -> float:
        """``WormAIProfile::GetPersuasionValue @0x4908890`` (spec §3.1)."""

        return self.resource_value(Attr.PERSUASION, amount, False)

    def solari_value(self, amount: int) -> float:
        """``WormAIProfile::GetSolariValue @0x4908900`` (spec §3.1)."""

        return self.resource_value(Attr.SOLARI, amount, False)

    def spice_value(self, amount: int) -> float:
        """``WormAIProfile::GetSpiceValue @0x4908970`` (spec §3.1)."""

        return self.resource_value(Attr.SPICE, amount, False)

    def water_value(self, amount: int) -> float:
        """``WormAIProfile::GetWaterValue @0x49089e0`` (spec §3.1)."""

        return self.resource_value(Attr.WATER, amount, False)

    def specimen_value(self, amount: int) -> float:
        """``WormAIProfile::GetSpecimenValue @0x4908a50`` (spec §3.1)."""

        return self.resource_value(Attr.SPECIMEN, amount, False)

    def strength_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``WormAIProfile::GetStrengthValue @0x4908ac0`` (spec §3.1)."""

        return self.resource_value(Attr.STRENGTH, amount, include_combat_posture_mod)

    def troop_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``WormAIProfile::GetTroopValue @0x4908b30`` (spec §3.1)."""

        return self.resource_value(Attr.TROOPS, amount, include_combat_posture_mod)

    def dreadnought_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``WormAIProfile::GetDreadnoughtValue @0x4908ba0`` (spec §3.1)."""

        return self.resource_value(Attr.DREADNOUGHT, amount, include_combat_posture_mod)

    def sandworm_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``WormAIProfile::GetSandWormValue @0x4908c10`` (spec §3.1)."""

        return self.resource_value(Attr.SANDWORMS, amount, include_combat_posture_mod)

    # ===========================================================================
    # §4 Victory points, cards and other scalars
    # ===========================================================================

    def victory_point_value(self, amount: int) -> float:
        """``WormAIProfile::GetVictoryPointValue @0x490a030`` (spec §4.1).

        The doubling line is a literal 10 (``cmp eax,0xa``), also in Epic.
        """

        c = self.C
        value = (
            c.VictoryPointValueEarly,
            c.VictoryPointValueMid,
            c.VictoryPointValueLate,
        )[self.game_arc()]
        mult = 1.0 if self.ctx.vp(self.ctx.me) + amount < 10 else 2.0
        return (float(amount) * value) * mult

    def card_draw_value(self) -> float:
        """``WormAIProfile::get_CardDrawValue @0x4908cc0`` (spec §4.2).

        Paul Atreides' deck-top branch (BaseSet leader) never occurs with our
        content, and would read the deck order; it is not ported.
        """

        value = self.C.CardDrawValue
        return value * 1.0

    def card_draw_value_with_buy_gains(self) -> float:
        """``WormAIProfile::CardDrawValueWithBuyGains @0x4908eb0`` (spec §4.2)."""

        draw = self.card_draw_value()
        return self.buy_gains(self.possible_persuasion_gain()) + draw

    def intrigue_value(self) -> float:
        """``WormAIProfile::get_IntrigueValue @0x4908130`` (spec §4.4).

        Plain ``mulsd``, no summer. Sonic Snoopers (Rise of Ix tech): dead.
        """

        c = self.C
        value = (
            c.IntrigueValueEarly,
            c.IntrigueValueMid,
            c.IntrigueValueLate,
        )[self.game_arc()]
        level = self.abundance_level(Attr.INTRIGUE_CARD)
        if level == 3:
            value *= c.FloodedMod
        elif level == 2:
            value *= c.RichMod
        elif level == 0:
            value *= c.PoorMod
        return value

    def trash_card_value(self) -> float:
        """``WormAIProfile::get_TrashCardValue @0x49091d0`` (spec §4.3)."""

        c = self.C
        return (c.TrashCardEarly, c.TrashCardMid, c.TrashCardLate)[self.game_arc()]

    def minimum_acquire_value(self) -> float:
        """``WormAIProfile::get_MinimumAcquireValue @0x49092e0`` (spec §4.3)."""

        c = self.C
        return (
            c.MinimumAcquireValueEarly,
            c.MinimumAcquireValueMid,
            c.MinimumAcquireValueLate,
        )[self.game_arc()]

    def trash_mod(self) -> float:
        """``WormAIProfile::TrashMod @0x49093f0`` (spec §11.1).

        Discard ++ AllCardsInPlay only (hand and draw pile not looked at).
        """

        me = self.ctx.me
        cards = self._own_cards(me.discard_pile, me.in_play)
        if not cards:
            return -1.0
        if self._has_intrigue(_CORNER_THE_MARKET):  # or HasTech(HoltzmanEngine)
            cards = [card for card in cards if card.short not in _TSMF]
        if not cards:
            return -1.0
        best = max(card.float_attr("TrashValue", 0.0) for card in cards)
        if best > 1.5:  # strict >
            return 1.5
        return -1.0 if best <= 0.0 else best

    def swordmaster_value(self) -> float:
        """``WormAIProfile::get_SwordmasterValue @0x4909740`` (spec §4.3)."""

        c = self.C
        return (c.GainSwordmasterEarly, c.GainSwordmasterMid, c.GainSwordmasterLate)[
            self.game_arc()
        ]

    def high_council_value(self) -> float:
        """``WormAIProfile::get_HighCouncilValue @0x4909850`` (spec §4.3)."""

        c = self.C
        return (
            c.GainHighCouncilEarly,
            c.GainHighCouncilMid,
            c.GainHighCouncilLate,
        )[self.game_arc()]

    def foldspace_value(self) -> float:
        """``WormAIProfile::get_FoldspaceValue @0x4909960`` (spec §4.3)."""

        c = self.C
        return (c.GainFoldspaceEarly, c.GainFoldspaceMid, c.GainFoldspaceLate)[
            self.game_arc()
        ]

    def mentat_value(self) -> float:
        """``WormAIProfile::get_MentatValue @0x4909a70`` (spec §4.3)."""

        c = self.C
        base = (c.GainMentatEarly, c.GainMentatMid, c.GainMentatLate)[self.game_arc()]
        m1 = (
            c.CalculatedHireMentatValueMod
            if self._has_intrigue(_CALCULATED_HIRE)
            else 1.0
        )
        m2 = (
            c.UrgentMissionMentatValueMod
            if self._has_intrigue(_URGENT_MISSION)
            else 1.0
        )
        return (base * m1) * m2

    def control_solari_value(self) -> float:
        """``WormAIProfile::get_ControlSolariValue @0x4909cb0`` (spec §4.3)."""

        c = self.C
        return (c.ControlSolariEarly, c.ControlSolariMid, c.ControlSolariLate)[
            self.game_arc()
        ]

    def control_spice_value(self) -> float:
        """``WormAIProfile::get_ControlSpiceValue @0x4909dc0`` (spec §4.3)."""

        c = self.C
        return (c.ControlSpiceEarly, c.ControlSpiceMid, c.ControlSpiceLate)[
            self.game_arc()
        ]

    def control_value_avg(self) -> float:
        """``WormAIProfile::get_ControlValueAvg @0x4909ed0`` (spec §4.3)."""

        spice = self.control_spice_value()
        solari = self.control_solari_value()
        return (spice + (solari + solari)) / 3.0

    def discard_value(self) -> float:
        """``WormAIProfile::get_DiscardValue @0x491aac0`` (spec §4.3)."""

        c = self.C
        return (c.DiscardEarly, c.DiscardMid, c.DiscardLate)[self.game_arc()]

    # ===========================================================================
    # §5 Persuasion forecast and the knapsack
    # ===========================================================================

    def _reveal_preview_value(self, ability_class: str, card: Entity) -> int:
        """``GetRevealPreviewValue(M, P)["Persuasion"]`` of one Reveal ability.

        Base ``RevealAbility @0x4bdbb10`` = the printed ``Persuasion``
        attribute; the overrides read from the disassembly at the addresses
        given. Keys other than ``Persuasion`` (OptionalPersuasion, Strength,
        ...) do not reach the Persuasion forecast.
        """

        me = self.ctx.me
        if ability_class == _DESERT_POWER_REVEAL:  # @0x4c03ff0
            return 0  # only {"OptionalPersuasion": 2}
        if ability_class == _BG_OPERATIVE_REVEAL:  # @0x4c042e0
            # + 2 while fewer than 2 Spies are left in the supply (setl).
            bonus = 2 if me.spies_supply < 2 else 0
            return card.int_attr("Persuasion") + bonus
        if ability_class in (
            _CALCULUS_REVEAL,  # @0x4c06e70 (OptionalStrength aside)
            _SARDAUKAR_COORD_REVEAL,  # @0x4c4c690
            _IN_HIGH_PLACES_REVEAL,  # @0x4cc8aa0 (OptionalPersuasion aside)
        ):
            return 2
        if ability_class == _INTERSTELLAR_REVEAL:  # @0x4c42260
            return len(me.completed_contract_ids)  # GetContractsCompletedCount
        if ability_class == _PARACOMPASS_REVEAL:  # @0x4c48880
            if not me.high_council:
                return 0
            return 2 | (1 if me.swordmaster_acquired else 0)
        if ability_class == _SOUTHERN_ELDERS_REVEAL:  # @0x4c4ff90
            # 2 if another own card in play or in hand is Fremen.
            others = (
                other
                for other in self._own_cards(me.in_play, me.hand)
                if other.ref != card.ref
            )
            return (
                2 if any("Fremen" in o.list_attr("FactionList") for o in others) else 0
            )
        if ability_class == _LIET_KYNES_REVEAL:  # @0x4ca4600 (Stilgar)
            fremen = [
                other
                for other in self._own_cards(me.in_play, me.hand)
                if "Fremen" in other.list_attr("FactionList")
            ]
            return len(fremen) * 2
        if ability_class == _THUFIR_REVEAL:  # @0x4cb72a0
            return 1
        if ability_class == _UNDERCOVER_REVEAL:  # @0x4cce1c0
            return 0  # only {"OptionalStrength": 2}
        return card.int_attr("Persuasion")  # base RevealAbility

    def _reveal_preview_persuasion(self) -> int:
        """``WormPlayer::GetRevealPreview(M, false)["Persuasion"]`` @0x483eb70.

        Spec §5.1. Outside the seat's own Reveal turn: pool + High Council 2 +
        own Agent on Assembly Hall 1 + the Reveal Persuasion of the hand. In
        the Reveal turn the hand is already revealed, so: the pool.
        ``SelectableAbilities(false)`` holds every card's Play/Activated
        abilities (@0x4839ac0), so no hand card is filtered out.
        """

        me = self.ctx.me
        persuasion = self._persuasion_pool()
        if not self._in_reveal_turn():
            if me.high_council:
                persuasion += 2
            if "assembly_hall" in me.agent_locations:
                persuasion += 1
        for card in self._own_cards(self.ctx.hand):
            for ability_class in card.ability_ids:
                if ability_class in _REVEAL_CLASSES:
                    persuasion += self._reveal_preview_value(ability_class, card)
        return persuasion

    def possible_persuasion(self) -> int:
        """``WormAIProfile::get_PossiblePersuasion @0x4903600`` (spec §5.1)."""

        return self._reveal_preview_persuasion()

    def possible_persuasion_gain(self) -> int:
        """``WormAIProfile::PossiblePersuasionGain @0x4908ef0`` (spec §4.2).

        The mean printed ``Persuasion`` (app attribute) of the draw pile, or
        of the discard pile when the draw pile is empty, banker-rounded.
        """

        me = self.ctx.me
        if me.deck:
            source = self._deck_cards()
        elif me.discard_pile:
            source = self._own_cards(me.discard_pile)
        else:
            return app_round(0.0)
        total = 0
        for card in source:
            total += card.int_attr("Persuasion")
        return app_round(total / len(source))

    def _predict_with_values(self, with_persuasion: int) -> list[tuple[Entity, float]]:
        """``PredictCardBuys`` with each yielded card's ``AcquireValue.Sum``."""

        items: list[tuple[Entity, int, float]] = []
        for card in self._row_cards():
            if card.int_attr("PersuasionCost", 99) <= with_persuasion:  # b__0: <=
                items.append(
                    (
                        card,
                        card.int_attr("PersuasionCost", 0),
                        self.acquire_value(card).sum,
                    )
                )
        return _knapsack(items, with_persuasion)

    def predict_card_buys(self, with_persuasion: int) -> list[Entity]:
        """``WormAIProfile::PredictCardBuys @0x4903680`` (spec §5.3-5.4).

        A 0/1 knapsack over the affordable row and reserve cards (weight =
        cost, value = ``AcquireValue``); cards in yield order (descending row
        index).
        """

        return [card for card, _ in self._predict_with_values(with_persuasion)]

    def buy_gains(self, amount: int) -> float:
        """``WormAIProfile::GetBuyGains @0x4908650`` (spec §5.5).

        ``max(0, (Σ AcquireValue(knapsack(P+n)) - Σ AcquireValue(knapsack(P)))
        - n)`` with ``P`` the Reveal-preview Persuasion; cached per ``n`` for
        the decision. The sums are in yield order; the app re-evaluates
        ``AcquireValue`` for them, which gives the same doubles.
        """

        cached = self._cached_buy_gains.get(amount)
        if cached is not None:
            return cached
        preview = self._reveal_preview_persuasion()
        base = self._predict_with_values(preview)
        more = self._predict_with_values(preview + amount)
        gain = max(
            0.0,
            (_dsum([v for _, v in more]) - _dsum([v for _, v in base])) - float(amount),
        )
        self._cached_buy_gains[amount] = gain
        return gain

    def buy_value(self) -> float:
        """``WormAIProfile::GetBuyValue @0x4909f10`` (spec §5.5)."""

        chosen = self._predict_with_values(self._reveal_preview_persuasion())
        return _dsum([value for _, value in chosen])

    def acquire_cards_by_value(self, with_persuasion: int) -> list[Entity]:
        """``WormAIProfile::GetAcquireCardsByValue @0x4903810`` (spec §5.6).

        Affordable row/reserve cards, stable-sorted by ``AcquireValue``
        descending.
        """

        affordable = [
            card
            for card in self._row_cards()
            if card.int_attr("PersuasionCost", 99) <= with_persuasion
        ]
        keyed = [(card, self.acquire_value(card).sum) for card in affordable]
        keyed.sort(key=lambda item: item[1], reverse=True)  # stable
        return [card for card, _ in keyed]

    def deck_agent_icons(self) -> dict[str, int]:
        """``WormAIProfile::get_DeckAgentIcons @0x4903980`` (spec §6.1).

        Icon (app ``IconList`` name) -> count over the draw pile only, one per
        list entry.
        """

        icons: dict[str, int] = {}
        for card in self._deck_cards():
            for icon in card.list_attr("IconList"):
                icons[icon] = icons.get(icon, 0) + 1
        return icons

    # ===========================================================================
    # §6 AcquireValue and its terms
    # ===========================================================================

    def acquire_value(self, card: Entity) -> Summer:
        """``WormImperiumPlayable::AcquireValue @0x4834650`` (spec §6).

        Immortality's ``EntityType == Tleilaxu`` branch is dead here.
        """

        c = self.C
        me = self.ctx.me
        s = Summer()
        s.add("Archetype Value", card.float_attr("AcquireValue", 0.0))

        # (a) new agent icons
        if not self.is_climax():
            deck_icons = self.deck_agent_icons()
            icons = _dsum(
                [
                    0.0
                    if (icon in deck_icons and deck_icons[icon] > 2)  # strict > 2
                    else c.AcquireNewIconsBonus
                    for icon in card.list_attr("IconList")
                ]
            )
            if self._has_intrigue(_PLANS_WITHIN_PLANS):
                icons *= c.PoliticsPayoffMod
            # Grand Conspiracy / Memocorders (Rise of Ix): dead.
            if self._leader_short() == _STABAN_TUEK:
                icons *= c.StabanTuekIconMod
            s.add("New Icons", icons)  # added even when 0

        # (b) consolidation (spend big)
        cost = card.int_attr("PersuasionCost", 0)
        pool = self._persuasion_pool()  # the live pool, not the preview
        if cost > 0 and pool >= cost:  # strict > 0 ; >=
            s.add(
                "Consolidation",
                c.ConsolidationValueMod * ((float(pool) - float(cost)) / float(cost)),
            )

        s.merge(self.synergy_mod(card))
        s.merge(self.friendship_mod(card))
        s.merge(self.acquire_effects_value(card))
        s.merge(self.specific_acquire_bonus(card))
        # player.CallToArms: Call to Arms played and waiting face up.
        if any(card_id(i) == "call_to_arms" for i in me.intrigue_faceup):
            s.add("Call To Arms", c.CallToArmsAcquireMod)
        if (
            "WantSpy" in card.list_attr("Tags")
            and self._leader_short() in _WANT_SPY_LEADERS
        ):
            _mul(s, c.WantSpyImperiumMod, "WantSpy mod")

        mod = (
            card.float_attr("EarlyMod", 1.0),
            1.0,
            card.float_attr("LateMod", 1.0),
        )[self.game_arc()]
        _mul(s, mod, "Game Arc")
        if self.minimum_acquire_value() > s.sum:  # strict >
            _mul(s, 0.0, "Game Arc Min")
        return s

    def synergy_mod(self, card: Entity) -> Summer:
        """``WormAIProfile::GetSynergyMod @0x490d040`` (spec §7.1).

        The deck-pile synergy of every ability of every owned card
        (``ValueInPileForOtherPlay`` with the Deck), plus tag incentives,
        capped at ``SynergyModMaxValue``. Helix/Double Helix (Immortality):
        dead.
        """

        c = self.C
        me = self.ctx.me
        tags = card.list_attr("Tags")
        s = Summer()
        if card.short in _TSMF and self._in_reveal_turn():
            # ActiveCards: in play with an unexhausted Play/Activated ability;
            # judgement: a played Guild Spy always keeps one (AcquireAbility).
            guild_spy = any(
                played.short == _GUILD_SPY for played in self._own_cards(me.in_play)
            )
            contract_open = any(
                CONTRACT_ARCHETYPES.get(card_id(contract)) == _CONTRACT_BASE_20
                for contract in me.active_contract_ids
            )
            if guild_spy or contract_open:
                s.add("TSMF Uprising Mod", c.SynergyTSMFUprisingMod)
        if not self.is_climax():
            from dune_imperium.agents.app_ai.abilities import Pile

            profile = self._profile()
            concat = Summer()
            for owned in self._all_imperium_cards():
                for ability in self._abilities(owned):
                    concat.merge(
                        ability.value_in_pile_for_other_play(profile, Pile.DECK, card)
                    )
            if SYNERGY_READS_HELD_CARD_ABILITIES:
                held = [intrigue_entity(i, self.ctx.seat) for i in me.intrigue_cards]
                held += [
                    contract_entity(i, self.ctx.seat) for i in me.active_contract_ids
                ]
                for owned in held:
                    for ability in self._abilities(owned):
                        concat.merge(
                            ability.value_in_pile_for_other_play(
                                profile, Pile.DECK, card
                            )
                        )
            s.merge(concat)
            if "WantSpy" in tags:
                s.add(
                    "WantSpy Spy count incentive",
                    c.SynergySpyMod * float(len(me.spy_post_ids)),
                )
            if (
                "WantContract2" in tags
                or "WantContract4" in tags
                or "WantContractX" in tags
            ):
                s.add(
                    "Contract Completed incentive",
                    min(
                        c.SynergyContractCompleted * len(me.completed_contract_ids),
                        c.SynergyContractCompletedMax,
                    ),
                )
                s.add(
                    "Contract Open incentive",
                    min(
                        c.SynergyContractOpen * len(me.active_contract_ids),
                        c.SynergyContractOpenMax,
                    ),
                )
            if "WantHooks" in tags:
                if me.maker_hooks:
                    s.add("Has Hooks Incentive", c.SynergyHaveHooksMod)
                elif self._influence(me, "fremen") >= 2:
                    s.add(
                        "No Hooks + 2 Fremen Incentive",
                        c.SynergyHooksFremenInfluenceMod,
                    )
        if s.sum > c.SynergyModMaxValue:  # strict >
            _mul(s, 0.0, "Exceeded Synergy Max")
            s.add("Synergy Max", c.SynergyModMaxValue)
        return s

    def friendship_mod(self, card: Entity) -> Summer:
        """``WormAIProfile::GetFriendshipMod @0x490deb0`` (spec §8).

        Literals 1.5 / 0.5 / 2.5 / 1.0, the same on every level.
        """

        value = 0.0
        for tag in card.list_attr("Tags"):
            entry = _FRIENDSHIP_TAGS.get(tag)
            if entry is None:
                continue  # incl. DiscardEnabler (case 15: nothing)
            kind, faction = entry
            if kind == "influence":
                value += self._influence_check(faction)
            else:
                value += self._alliance_check(faction)
        s = Summer()
        s.add("Friendship Mod", value)
        return s

    def _influence_check(self, faction: str) -> float:
        """``TwoInfluenceCheck @0x490e410`` (also inlined)."""

        influence = self._influence(self.ctx.me, faction)
        if influence > 1:  # strict > 1
            return 1.5
        return 0.5 if influence == 1 else 0.0

    def _alliance_check(self, faction: str) -> float:
        """``AllianceCheck @0x490e2e0``."""

        me = self.ctx.me
        if faction in me.alliance_faction_ids:
            return 2.5
        if self._influence(me, faction) >= 2 and all(
            faction not in o.alliance_faction_ids for o in self.ctx.opponents
        ):
            return 1.0
        return 0.0

    def acquire_effects_value(self, card: Entity) -> Summer:
        """``WormAIProfile::GetAcquireEffectsValue @0x490e470`` (spec §9).

        Invasion Ships (Rise of Ix), Research and Shadow (Immortality): dead.
        Unlisted effects (Intrigue, Contract, PlaceSpy, ...) are worth 0.
        """

        value = 0.0
        for effect in card.list_attr("AcquireEffectList"):
            faction = _RANK_EFFECTS.get(effect)
            if faction is not None:
                value += self.gain_influence_value(faction, 1, -1, False).sum
            elif effect == "AnyRank":
                value += self.gain_influence_value(_ANY_FACTION, 1, -1, False).sum
            elif effect == "VP":
                value += self.victory_point_value(1)
            elif effect == "Water":
                value += self.resource_value(Attr.WATER, 1, False)
            elif effect == "Troop":
                value += self.resource_value(Attr.TROOPS, 1, False)
            elif effect == "Solari":
                value += self.resource_value(Attr.SOLARI, 1, False)
            elif effect == "Spice":
                value += self.resource_value(Attr.SPICE, 1, False)
        s = Summer()
        s.add("Acquire Effects", value)
        return s

    def specific_acquire_bonus(self, card: Entity) -> Summer:
        """``WormAIProfile::GetSpecificAcquireBonus @0x490f430`` (spec §10).

        The ``SpecificAcquireValue`` of each of the card's abilities
        (concatenated). Detonation Devices (Rise of Ix): dead.
        """

        profile = self._profile()
        concat = Summer()
        for ability in self._abilities(card):
            concat.merge(ability.specific_acquire_value(profile))
        s = Summer()
        s.merge(concat)
        return s

    # ===========================================================================
    # §4.6-4.7 Space costs
    # ===========================================================================

    def _spice_for_sell_melange(self) -> int:
        """``WormAIProfile::GetSpiceForSellMelange @0x490f6c0`` (spec §4.6).

        BaseSet space, not on the Uprising board.
        """

        c = self.C
        spice = self.ctx.me.resources.spice
        value = self.resource_value(Attr.SOLARI, 1, False)
        if c.SellMelangeLowSolariValueThreshold > value:  # strict
            return min(2, spice)
        if c.SellMelangeMidSolariValueThreshold > value:
            return min(3, spice)
        n = 4 if c.SellMelangeHighSolariValueThreshold > value else 5
        return min(n, spice)

    def spice_for_spice_refinery(self) -> int:
        """``WormAIProfile::GetSpiceForSpiceRefinery @0x490f850`` (spec §4.6)."""

        spice = self.ctx.me.resources.spice
        value = self.resource_value(Attr.SOLARI, 1, False)
        pay = 1 if self.C.SpiceRefineryLowSolariValueThreshold <= value else 0
        return min(pay, spice)

    def can_agent_ability_be_played_with_space(
        self, space: Entity | None, attr: Attr, amount: int
    ) -> bool:
        """``WormAIProfile::CanAgentAbilityBePlayedWithSpace @0x490f950``.

        Spec §4.7. Judgement: a missing space (a null deref in the app) reads
        as a space with no costs or gains.
        """

        me = self.ctx.me

        def attribute(name: str) -> int:
            return 0 if space is None else space.int_attr(name)

        if attr is Attr.SPICE:
            need = attribute("SpiceCost")
            if space is not None and space.short == _SELL_MELANGE:
                need = self._spice_for_sell_melange()
            bonus = 0
            if space is not None and space.has("BonusSpice"):
                # Runtime BonusSpice: our maker spaces' bonus spice.
                bonus = dict(self.ctx.view.maker_bonus_spice).get(
                    space.ref, space.int_attr("BonusSpice")
                )
            return need + amount <= me.resources.spice + attribute("Spice") + bonus
        if attr is Attr.SOLARI:
            return attribute("SolariCost") + amount + attribute(
                "SolariDiscount"
            ) <= me.resources.solari + attribute("Solari")
        if attr is Attr.WATER:
            return attribute("WaterCost") + amount <= me.resources.water + attribute(
                "Water"
            )
        return True

    # ===========================================================================
    # §11 Trashing
    # ===========================================================================

    def card_to_trash(
        self, targets: Sequence[Entity], min_trash_value: float
    ) -> tuple[Entity | None, float]:
        """``WormAIProfile::GetCardToTrash @0x490fc00`` (spec §11.2).

        Shuffles (ListUtil.Shuffle, here ``self.rng``), then keeps the last
        card whose score is ``>=`` the best so far (starting at
        ``min_trash_value``). Rise of Ix / Immortality card bonuses: dead.
        """

        c = self.C
        me = self.ctx.me
        candidates = list(targets)
        convincing_argument = any(
            card.short == _CONVINCING_ARGUMENT for card in candidates
        )
        self.rng.shuffle(candidates)
        tsmf_owned = sum(
            1 for owned in self._all_imperium_cards() if owned.short in _TSMF
        )
        discard = set(me.discard_pile)
        played = set(me.in_play)
        hand = set(me.hand)
        best: Entity | None = None
        best_value = min_trash_value
        for card in candidates:
            s = Summer()
            trash_value = card.float_attr("TrashValue", 0.0)
            if card.short in _TSMF:
                if self._has_intrigue(_CORNER_THE_MARKET):  # or Holtzman Engine
                    trash_value = 0.0
                # Grand Conspiracy (Rise of Ix): dead.
                elif self._has_intrigue(_SECURE_SPICE_TRADE) and tsmf_owned < 3:
                    trash_value = 0.0
            s.add("Archetype", trash_value)
            if convincing_argument:  # every candidate
                s.add(
                    "Convincing Argument TrashValueMod",
                    c.ConvincingArgumentTrashValueMod,
                )
            if s.sum > 0.0:  # strict >
                if s.sum > 1.0:  # strict >
                    s.add("TrashValue: x > 1", 10.0)
                else:
                    s.add("TrashValue: x > 0", 0.0)
                _mul(s, 10.0, "Value Shift")
            else:
                _mul(s, 0.0, "Avoid Trashing")
                s.add("Ignore", -1.0)
            if card.ref in discard:
                s.add("Is Discarded", 0.2)
            elif card.ref in played:
                s.add("Is Played", 0.1)
            elif card.ref in hand:
                s.add("In Hand", 0.0)
            s.add(
                "Persuasion Cost",
                float(card.int_attr("PersuasionCost", 0)) * -0.01 + 0.09,
            )
            if s.sum >= best_value:  # >= : the later card wins ties
                best, best_value = card, s.sum
        return best, best_value

    # ===========================================================================
    # §3.3, §13 Opponents and turn order
    # ===========================================================================

    def opponent_ratio(self, condition: Callable[[PlayerState], bool]) -> float:
        """``WormAIProfile::OpponentRatio @0x4911080`` (spec §3.3)."""

        opponents = self.ctx.opponents
        matching = sum(1 for opponent in opponents if condition(opponent))
        return float(matching) / float(len(opponents))

    def _active_seat(self) -> int:
        """``M.ActiveAccountID``'s seat: the turn owner, else the decider."""

        view = self.ctx.view
        if view.turn_owner is not None:
            return view.turn_owner
        if view.decision_owner is not None:
            return view.decision_owner
        return self.ctx.seat

    def ordered_players(self) -> list[int]:
        """``WormAIProfile::GetOrderedPlayers @0x4911120`` (spec §13).

        Seat order rotated to the active player; the active player goes last
        unless its ``PlayerTurn`` is Undetermined. Judgement (UNTRACED in the
        spec): Undetermined = the turn-start prompt, our ``turn`` window.
        """

        count = len(self.ctx.players)
        active = self._active_seat()
        order = [(active + k) % count for k in range(count)]
        undetermined = self.ctx.decision_kind == "turn"
        if not undetermined:
            order.append(order.pop(0))
        return order

    def has_turn_before_opponent_next_round(self, opponent: int) -> bool:
        """``WormAIProfile::HasTurnBeforeOpponentNextRound @0x4911e00``.

        Spec §13: ``PlayerTurnOrder`` from the First Player marker.
        """

        first = self.ctx.first_player
        if first is None:
            # No First Player: an empty order, FirstIndexOf -1 < -1 is false.
            return False
        if first == opponent:
            return True
        if first == self.ctx.seat:
            return False
        count = len(self.ctx.players)
        rest = [(first + k) % count for k in range(1, count)]  # Skip(1)
        return rest.index(self.ctx.seat) < rest.index(opponent)  # strict <

    def bad_intrigue_cards_in_hand(self) -> list[Entity]:
        """``WormAIProfile::get_GetBadIntrigueCardsInHand @0x4912250``.

        intrigues.md §4.5: held Intrigue cards with an ``IntrigueAbility``
        whose ``IsBadIntrigue`` holds. Callers are Rise of Ix only. Judgement:
        an ability port answers through an ``is_bad_intrigue(profile)`` hook
        (``IntrigueAbility`` default false); a port without it counts false.
        """

        profile = self._profile()
        bad: list[Entity] = []
        for instance in self.ctx.intrigue_cards:
            card = intrigue_entity(instance, self.ctx.seat)
            for ability in self._abilities(card):
                hook = getattr(ability, "is_bad_intrigue", None)
                if callable(hook) and bool(hook(profile)):
                    bad.append(card)
                    break
        return bad

    # ===========================================================================
    # §12 Discarding
    # ===========================================================================

    def _first_ability_value(self, card: Entity, classes: frozenset[str]) -> float:
        """``c.Abilities.OfType<T>().FirstOrDefault()?.ValueForPlayer(P, [])``."""

        from dune_imperium.agents.app_ai.abilities import ability_for

        for ability_class in card.ability_ids:
            if ability_class in classes:
                ability = ability_for(ability_class, card)
                return ability.value_for_player(self._profile(), ()).sum
        return 0.0

    def discard_order(
        self, cards: Sequence[Entity], spacing_guild_bonus: bool
    ) -> list[Entity]:
        """``ChooseDiscardEvaluator::GetDiscardOrder @0x492de30`` (spec §12.1).

        Ascending, stable. ``WithAgentValue`` while an Agent is left
        (``GetNextAgent``), else ``NoAgentValue``. The evaluator itself
        (``Evaluate @0x492dfe0``) takes the first ``n`` of this order.
        """

        def reveal_value(card: Entity) -> float:  # g__RevealValue|0 @0x492e5a0
            return self._first_ability_value(card, _REVEAL_CLASSES)

        def play_value(card: Entity) -> float:  # g__PlayValue|1 @0x492e700
            return self._first_ability_value(card, _AGENT_CLASSES)

        def incentive_discard(card: Entity) -> bool:  # @0x492e860
            if "IncentiveDiscard" in card.list_attr("Tags"):
                return True
            return (
                spacing_guild_bonus
                and "SpacingGuild" in card.list_attr("FactionList")
                and card.int_attr("PersuasionCost", 0) < 5  # strict < 5
            )

        def no_agent_value(card: Entity) -> float:  # g__NoAgentValue|3 @0x492e9b0
            rv = reveal_value(card)
            inc = (
                play_value(card) - (100000.0 * rv + 1000000.0)
                if incentive_discard(card)
                else 0.0
            )
            return float(card.int_attr("PersuasionCost", 0)) + (
                100.0 * rv + (0.0 + inc)
            )

        def with_agent_value(card: Entity) -> float:  # g__WithAgentValue|4 @0x492eae0
            tv = card.float_attr("TrashValue", 0.0)
            rv = reveal_value(card)
            pv = play_value(card)
            x = (
                (pv - (100000.0 * rv + 1000000.0)) + 0.0
                if incentive_discard(card)
                else 0.0
            )
            y = (tv * -10000.0 + x) if 0.0 < tv else x  # strict 0 < tv
            cost = card.int_attr("PersuasionCost", 0)
            return 1.5 * rv + (pv + (float(100 * cost) + y))

        key = with_agent_value if self.ctx.me.agents_available > 0 else no_agent_value
        return sorted(cards, key=key)
