"""The original game's Intrigue abilities.

Ports of the 34 original-game Intrigue cards' ability classes that the Uprising deck
does not use; each follows the app's AI for that class, and the detailed notes are kept
privately (``docs/app-ai-plan.md`` §12). The classes the Uprising deck shares (Backed by
CHOAM, Call to Arms, Change Allegiances, Contingency Plan, Councilor's Ambition,
Crysknife, Depart for Arrakis, Detonation, Leverage, Market Opportunity, Shaddam's
Favor, Sietch Ritual...) are in ``abilities/intrigue.py``.

App class chains:

- ``PlayAbilities.IntrigueAbility`` <- ``BriberyAbility``,
  ``BinduSuspensionAbility``, ``BypassProtocolAbility``,
  ``CalculatedHireAbility``, ``CharismaAbility``, ``ChoamSharesAbility``,
  ``CornerTheMarketAbility`` (Endgame), ``CouncilorsDispensationAbility``,
  ``DemandRespectAbility`` and ``ToTheVictorAbility`` (CombatResolution),
  ``DispatchAnEnvoyAbility``, ``DoubleCrossAbility``,
  ``InfiltrateAbility``, ``PlansWithinPlansAbility`` (Endgame),
  ``PoisonSnooperAbility``, ``RapidMobilizationAbility``,
  ``RecruitmentMissionAbility``, ``RefocusAbility``,
  ``ReinforcementsAbility``, ``StagedIncidentAbility`` (Combat),
  ``TheSleeperMustAwakenAbility``, ``TiebreakerAbility2`` (Endgame),
  ``UrgentMissionAbility``, ``WaterOfLifeAbility``,
  ``WaterPeddlersUnionAbility``, ``WindfallAbility``;
- ``PlayAbilities.StrengthIntrigueAbility`` <- ``AlliedArmadaAbility``,
  ``AmbushAbility``, ``MasterTacticianAbility``, ``PrivateArmyAbility``,
  ``TiebreakerAbility``;
- ``PlayAbilities.GainInfluenceIntrigueAbility`` (abstract, an
  ``IntrigueAbility``) <- ``FavoredSubjectAbility`` (Emperor),
  ``GuildAuthorizationAbility`` (Spacing Guild), ``KnowTheirWaysAbility`` (Fremen),
  ``SecretOfTheSisterhoodAbility`` (Bene Gesserit).

Request / answer encoding (on top of ``abilities/intrigue.py``'s; what a
window builds and what ``evaluate`` reads). ``request.infos[i]`` is the app's
target information ``i`` of the ability. Per card (only the infos the
ability reads; every other card reads none):

- Bribery: ``infos[0]`` the faction TRACKs of the gain
  (``MakeGainAnyFactionInfluenceTargeting``); the answer is ``((track,),)``.
- Master Tactician: ``infos[0].options`` the ``ChooseOne`` (0 = gain the
  strength, 1 = retreat) and ``infos[1].options`` one index per Conflict troop
  (the retreat option's dependent targets); the answers are ``((0,),)`` and
  ``((1,), (troop indices...))``.
- Demand Respect: ``infos[0]`` the faction TRACKs (the faction of the gained
  Influence) and ``infos[1]`` the ``ChooseOne`` (0 = one Influence, 1 = pay 2
  spice for two); the answer is ``((option,), (track,))``.
- Poison Snooper: ``infos[0]`` the card on top of the draw pile, revealed by
  the Plot (read by ``choose_poison``).

Answers follow ``abilities/intrigue.py`` (``AIChoiceSelectionWithTargets``,
``_Choice``): ``Answer.response is None`` = nothing stored (value 0); ``()`` =
"play it" with no sub-targets (``UpdateSelectionTargets(v, src, null)``).

"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AgentAbility,
    _space_bonus_spice,
    space_solari_cost,
)
from dune_imperium.agents.app_ai.abilities.immortality import (
    SpaceCache,
    valid_space_ids,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    _REVEAL_TURN,
    _TSMF_ARCHETYPES,
    _UNDETERMINED,
    COMBAT_RESOLUTION_TIMING,
    COMBAT_TIMING,
    ENDGAME_TIMING,
    IntrigueAbility,
    StrengthIntrigueAbility,
    _Choice,
    _count_the_spice_must_flow,
    _current_conflict,
    _in_player_turn,
    _influence,
    _intrigue_hand_count,
    _options,
    _space_cost,
    _swordmaster,
    _targets,
    intrigue_deploy_troops,
)
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    SWORDMASTER_SPACE_ARCHETYPES,
    board_space_ids,
    card_entity,
    intrigue_entity,
    is_high_council_space,
    space_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_PA: Final = "ability.play.original."

#: ``intrigue.original.choam_shares`` / ``CornertheMarket`` (tested by
#: ``ArchID``).
_CHOAM_SHARES: Final = "intrigue.original.choam_shares"
_CORNER_THE_MARKET: Final = "intrigue.original.corner_the_market"
#: ``Factions.None`` of ``GetGainInfluenceValue`` (``influence.NO_FACTION``).
_ANY_FACTION: Final = "none"
_APP_TO_FACTION: Final = {app: ours for ours, app in FACTION_NAMES.items()}

# ---------------------------------------------------------------------------
# Shared reads
# ---------------------------------------------------------------------------


def _hand_or_reveal(p: Profile) -> bool:
    """The gate Charisma, Recruitment Mission, Choam Shares and The Sleeper Must Awaken
    share: ``PlayerTurn == Reveal`` or ``IntrigueHand.Count >= 4`` (return when neither
    holds)."""

    return _in_player_turn(p, _REVEAL_TURN) or _intrigue_hand_count(p) >= 4


def _holds_intrigue(p: Profile, archetype: str) -> bool:
    """``P.HasIntrigueCard(archID)``: a held Intrigue card of
    that archetype."""

    return any(
        intrigue_entity(instance, p.ctx.seat).short == archetype
        for instance in p.ctx.intrigue_cards
    )


def _turn_start_with_agent(p: Profile) -> bool:
    """``P.IsInPlayerTurn(Undetermined) && P.GetNextAgent() != null``: the
    turn-start prompt with an Agent left (``GetNextAgent`` is the
    first ``Agent`` of the leader's Agent supply)."""

    return _in_player_turn(p, _UNDETERMINED) and p.ctx.me.agents_available > 0


# ---------------------------------------------------------------------------
# GainInfluenceIntrigueAbility and its four cards
# ---------------------------------------------------------------------------


@port("ability.play.gain_influence_intrigue")
class GainInfluenceIntrigueAbility(IntrigueAbility):
    """``PlayAbilities.GainInfluenceIntrigueAbility`` (abstract): "gain one
    Influence with the card's Faction". ``Cost`` = NoCost; no
    target information (``SpecifiedFaction`` fixes the Faction)."""

    #: ``SpecifiedFaction``: our id of the Faction the card names.
    specified_faction: ClassVar[str] = ""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``GainInfluenceIntrigueAbility.IsBadIntrigue``.

        True when some opponent stands at 6 on the Faction's track
        (``GetFactionInfluence(F) == 6``); else, when the player stands at 4 or 2, true
        when some opponent is 2 or more above the player (``influence - playerInfluence
        >= 2``).
        """

        faction = self.specified_faction
        if any(_influence(o, faction) == 6 for o in p.ctx.opponents):
            return True
        mine = _influence(p.ctx.me, faction)
        if mine not in (4, 2):
            return False
        return any(_influence(o, faction) - mine >= 2 for o in p.ctx.opponents)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainInfluenceIntrigueAbility.Evaluate``.

        ``G(F, +1, -1, false)``; played at the literal 100.0 when its sum reaches
        ``GainInfluenceValueThreshold``, or at the climax, or with four Intrigue cards
        in hand.
        """

        choice = _Choice()
        g = p.gain_influence_value(self.specified_faction, 1, -1, False)
        if (
            g.sum >= p.C.GainInfluenceValueThreshold
            or p.is_climax()
            or _intrigue_hand_count(p) >= 4
        ):
            choice.update_targets(100.0, None)
        return choice.answer(f"{type(self).__name__} | {g.sum}")


@port(_PA + "favored_subject")
class FavoredSubjectAbility(GainInfluenceIntrigueAbility):
    """``FavoredSubjectAbility``: ``SpecifiedFaction`` = Emperor (1)."""

    specified_faction: ClassVar[str] = "emperor"


@port(_PA + "guild_authorization")
class GuildAuthorizationAbility(GainInfluenceIntrigueAbility):
    """``GuildAuthorizationAbility``: ``SpecifiedFaction`` = Spacing Guild (2)."""

    specified_faction: ClassVar[str] = "spacing_guild"


@port(_PA + "know_their_ways")
class KnowTheirWaysAbility(GainInfluenceIntrigueAbility):
    """``KnowTheirWaysAbility``: ``SpecifiedFaction`` = Fremen (4)."""

    specified_faction: ClassVar[str] = "fremen"


@port(_PA + "secret_of_the_sisterhood")
class SecretOfTheSisterhoodAbility(GainInfluenceIntrigueAbility):
    """``SecretOfTheSisterhoodAbility``: ``SpecifiedFaction`` = Bene Gesserit (3);
 ``WillClearUndo`` is the
    engine's (an Influence gain that may rank up)."""

    specified_faction: ClassVar[str] = "bene_gesserit"


# ---------------------------------------------------------------------------
# Plot intrigues
# ---------------------------------------------------------------------------


@port(_PA + "bribery")
class BriberyAbility(IntrigueAbility):
    """``BriberyAbility``: pay 2 Solari for one Influence with a Faction of your choice.
    ``Cost`` = ``Solari >= 2``."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Solari, 2)``."""

        return p.ctx.me.resources.solari >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: ``GetGameArc() == 0``."""

        return p.game_arc() == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BriberyAbility.Evaluate``.

        Away from the climax: ``G(None, +1, -1, false)`` must reach
        ``BriberyInfluenceThreshold`` and the turn must not be the turn start
        (``PlayerTurn == Undetermined`` returns). At the climax neither test runs. Each
        track is then priced ``G(track, +1)``, scaled by the literal 0.1 ("Play Bribery
        Last") away from the climax, and stored (strictly better replaces).
        """

        choice = _Choice()
        climax = p.is_climax()
        if not climax:
            if (
                p.gain_influence_value(_ANY_FACTION, 1, -1, False).sum
                < p.C.BriberyInfluenceThreshold
            ):
                return choice.answer("Bribery")
            if _in_player_turn(p, _UNDETERMINED):
                return choice.answer("Bribery")
        for track in _targets(request, 0, Kind.TRACK):
            g = p.gain_influence_value(track.ref, 1, -1, False)
            if not climax:
                g.multiply("Play Bribery Last", 0.1)
            choice.update_targets(g.sum, (track.ref,))
        return choice.answer("Bribery | gain influence")


@port(_PA + "charisma")
class CharismaAbility(IntrigueAbility):
    """``CharismaAbility``: +2 Persuasion this Reveal turn (``Cost`` = NoCost;
    ``ShowHinting`` = ``IsInPlayerTurn(Reveal)`` is the UI's)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CharismaAbility.Evaluate``: ``GetBuyGains(2)``; outside the Reveal turn
        four held Intrigue cards are needed; a gain below ``CharismaBuyGainsThreshold``
        needs the climax; then the literal 100.0."""

        choice = _Choice()
        gain = p.buy_gains(2)
        if not _hand_or_reveal(p):
            return choice.answer("Charisma")
        if gain < p.C.CharismaBuyGainsThreshold and not p.is_climax():
            return choice.answer("Charisma")
        choice.update_targets(100.0, None)
        return choice.answer("Charisma | 100")


@port(_PA + "recruitment_mission")
class RecruitmentMissionAbility(IntrigueAbility):
    """``RecruitmentMissionAbility``: +1 Persuasion this Reveal turn (``Cost`` =
    NoCost)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RecruitmentMissionAbility.Evaluate``: Charisma's shape with
        ``GetBuyGains(1)`` against ``RecruitmentMissionBuyGainsThreshold`` (the
        threshold test comes first, then the Reveal-or-four-cards gate)."""

        choice = _Choice()
        gain = p.buy_gains(1)
        if gain < p.C.RecruitmentMissionBuyGainsThreshold and not p.is_climax():
            return choice.answer("Recruitment Mission")
        if not _hand_or_reveal(p):
            return choice.answer("Recruitment Mission")
        choice.update_targets(100.0, None)
        return choice.answer("Recruitment Mission | 100")


@port(_PA + "choam_shares")
class ChoamSharesAbility(IntrigueAbility):
    """``ChoamSharesAbility``: pay 7 Solari for 1 VP."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Solari, 7)``."""

        return p.ctx.me.resources.solari >= 7

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: tail call of ``IsSolariShort``."""

        return p.is_solari_short()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChoamSharesAbility.Evaluate``.

        Only at the climax (``IsClimax`` false returns); outside the Reveal
        turn four held Intrigue cards are needed. The value is a fresh
        summer: ``GetSolariValue(-7)`` ("Solari Cost") plus
        ``GetVictoryPointValue(1)`` ("Victory Point")."""

        choice = _Choice()
        if not p.is_climax():
            return choice.answer("Choam Shares")
        if not _hand_or_reveal(p):
            return choice.answer("Choam Shares")
        v = Summer()
        v.add("Solari Cost", p.solari_value(-7))
        v.add("Victory Point", p.victory_point_value(1))
        choice.update_targets(v.sum, None)
        return choice.answer(f"Choam Shares | {v.sum}")


@port(_PA + "the_sleeper_must_awaken")
class TheSleeperMustAwakenAbility(IntrigueAbility):
    """``TheSleeperMustAwakenAbility``: pay 4 spice for 1 VP."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Spice, 4)``."""

        return p.ctx.me.resources.spice >= 4

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TheSleeperMustAwakenAbility.Evaluate``: Choam Shares'
        shape with ``GetSpiceValue(-4)`` ("Spice Cost") plus
        ``GetVictoryPointValue(1)``."""

        choice = _Choice()
        if not p.is_climax():
            return choice.answer("The Sleeper Must Awaken")
        if not _hand_or_reveal(p):
            return choice.answer("The Sleeper Must Awaken")
        v = Summer()
        v.add("Spice Cost", p.spice_value(-4))
        v.add("Victory Point", p.victory_point_value(1))
        choice.update_targets(v.sum, None)
        return choice.answer(f"The Sleeper Must Awaken | {v.sum}")


@port(_PA + "councilors_dispensation")
class CouncilorsDispensationAbility(IntrigueAbility):
    """``CouncilorsDispensationAbility``: with a High Council seat, spice."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasHighCouncilSeat``."""

        return p.ctx.me.high_council

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: ``!HighCouncilSeat`` (``xor al, 1``)."""

        return not p.ctx.me.high_council

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CouncilorsDispensationAbility.Evaluate``.

        Without the seat nothing. With more spice than
        ``CouncilorsDispensationSpiceThreshold`` (skips the test) four held Intrigue
        cards are needed; then the literal 100.0."""

        choice = _Choice()
        me = p.ctx.me
        if not me.high_council:
            return choice.answer("Councilor's Dispensation")
        if (
            p.C.CouncilorsDispensationSpiceThreshold < me.resources.spice
            and _intrigue_hand_count(p) < 4
        ):
            return choice.answer("Councilor's Dispensation")
        choice.update_targets(100.0, None)
        return choice.answer("Councilor's Dispensation | 100")


@port(_PA + "water_peddlers_union")
class WaterPeddlersUnionAbility(IntrigueAbility):
    """``WaterPeddlersUnionAbility`` (``Cost`` = NoCost)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: tail call of ``IsWaterLong``."""

        return p.is_water_long()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WaterPeddlersUnionAbility.Evaluate``.

        ``PlayIntrigueForFinalRoundOrHandSize(card) > 0`` plays at the literal 100.0.
        Otherwise only at the turn start with an Agent left, and with at most
        ``WaterPeddlersUnionWaterThreshold`` water (plays)."""

        choice = _Choice()
        if p.play_intrigue_for_final_round_or_hand_size(self.owner) <= 0:
            if not _turn_start_with_agent(p):
                return choice.answer("Water Peddlers Union")
            if p.C.WaterPeddlersUnionWaterThreshold < p.ctx.me.resources.water:
                return choice.answer("Water Peddlers Union")
        choice.update_targets(100.0, None)
        return choice.answer("Water Peddlers Union | 100")


@port(_PA + "windfall")
class WindfallAbility(IntrigueAbility):
    """``WindfallAbility``: +2 Solari (``Cost`` = NoCost)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: tail call of ``IsSolariLong``."""

        return p.is_solari_long()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WindfallAbility.Evaluate``.

        ``PlayIntrigueForFinalRoundOrHandSize(card) > 0`` plays at the literal
        100.0. Otherwise it needs the turn start with an Agent left; then with
        at most ``WindfallSolariThreshold`` Solari it plays. Above it, a
        player who cannot yet pay the Swordmaster space (Solari at most its
        ``SolariCost``, default 8) and lacks the Swordmaster plays; every
        other case plays only with at most ``WindfallChoamSharesThreshold``
        Solari while holding CHOAM Shares."""

        choice = _Choice()
        me = p.ctx.me
        if p.play_intrigue_for_final_round_or_hand_size(self.owner) <= 0:
            if not _turn_start_with_agent(p):
                return choice.answer("Windfall")
            solari = me.resources.solari
            if p.C.WindfallSolariThreshold < solari:
                short_of_swordmaster = solari <= _space_cost(p, _swordmaster(p))
                if not (short_of_swordmaster and not me.swordmaster_acquired):
                    if p.C.WindfallChoamSharesThreshold < solari:
                        return choice.answer("Windfall")
                    if not _holds_intrigue(p, _CHOAM_SHARES):
                        return choice.answer("Windfall")
        choice.update_targets(100.0, None)
        return choice.answer("Windfall | 100")


@port(_PA + "refocus")
class RefocusAbility(IntrigueAbility):
    """``RefocusAbility``: shuffle the discard pile into the deck and draw a card
    (``Cost`` = NoCost)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: always true."""

        return True

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RefocusAbility.Evaluate``.

        ``list = Deck.children ++ Discard.children`` (``[+0xf0]``, ``[+0xf8]`` of
        ``Player``); empty returns. ``GetBuyGains((int) Average( Persuasion))``
        (truncated). With an Agent left it plays; with none, a gain below the literal
        1.0 needs the climax or four held Intrigue cards; then 100.0."""

        choice = _Choice()
        me = p.ctx.me
        cards = [*sorted(me.deck), *me.discard_pile]
        if not cards:
            return choice.answer("Refocus")
        persuasion = [card_entity(i, p.ctx.seat).int_attr("Persuasion") for i in cards]
        average = sum(persuasion) / len(persuasion)  # Enumerable.Average<int>
        gain = p.buy_gains(int(average))
        if not me.agents_available > 0 and gain < 1.0:
            if not p.is_climax() and _intrigue_hand_count(p) < 4:
                return choice.answer("Refocus")
        choice.update_targets(100.0, None)
        return choice.answer("Refocus | 100")


@port(_PA + "water_of_life")
class WaterOfLifeAbility(IntrigueAbility):
    """``WaterOfLifeAbility``: pay a water and a spice to draw three cards."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Water, 1)`` then
        (``CostAction.Then``) ``AtLeast(Spice, 1)``."""

        me = p.ctx.me
        return me.resources.water >= 1 and me.resources.spice >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: ``GetGameArc() == 0``."""

        return p.game_arc() == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WaterOfLifeAbility.Evaluate``, ungated: a fresh summer of
        ``GetWaterValue(-1)`` ("Water Cost"), ``GetSpiceValue(-1)`` ("Spice Cost") and
        ``CardDrawValueWithBuyGains() * 3.0`` ("Card with Buy Gains")."""

        choice = _Choice()
        v = Summer()
        v.add("Water Cost", p.water_value(-1))
        v.add("Spice Cost", p.spice_value(-1))
        v.add("Card with Buy Gains", p.card_draw_value_with_buy_gains() * 3.0)
        choice.update_targets(v.sum, None)
        return choice.answer(f"Water of Life | {v.sum}")


@port(_PA + "poison_snooper")
class PoisonSnooperAbility(IntrigueAbility):
    """``PoisonSnooperAbility``: reveal the top card of your deck and draw or trash it
    (``Cost`` is the engine's)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: ``GetGameArc() == 1``."""

        return p.game_arc() == 1

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PoisonSnooperAbility.Evaluate``: ungated, the
        literal 100.0 (the choice is made later by ``choose_poison``)."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Poison Snooper | 100")

    def choose_poison(self, p: Profile, top: Entity | None) -> int:
        """``PoisonSnooperAbility.ChoosePoisonEvaluator``: the
        ``AIChoiceCustom`` answer of the draw-or-trash choice, 0 = trash and 1
        = draw. ``top`` is the revealed top card of the draw pile (our
        ``infos[0]``; ``None`` for an empty deck).

        ``v`` is the card's ``TrashValue`` attribute (0.0 for none). While the player
        holds Corner the Market (``IntrigueHand.Any(ArchID == CornertheMarket)``) a
        Spice Must Flow top card is worth 0 (``IsTheSpiceMustFlowImperium``). The card
        is trashed (0) in the Early and Mid arcs when ``v`` reaches the literal 0.5
        (draws); otherwise drawn.
        """

        value = 0.0 if top is None else top.float_attr("TrashValue", 0.0)
        if (
            top is not None
            and _holds_intrigue(p, _CORNER_THE_MARKET)
            and top.kind is Kind.CARD
            and top.short in _TSMF_ARCHETYPES
        ):
            value = 0.0
        if p.game_arc() <= 1 and value >= 0.5:
            return 0
        return 1


# ---------------------------------------------------------------------------
# Combat intrigues: the Strength family
# ---------------------------------------------------------------------------


@port(_PA + "allied_armada")
class AlliedArmadaAbility(StrengthIntrigueAbility):
    """``AlliedArmadaAbility`` (Strength 7, CombatValue 8.0): the base ``Evaluate``."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasFactionAlliance(None)`` then
        (``CostAction.Then``) ``Spice >= 2``. ``InAlliance(None)``
 is any Alliance token."""

        me = p.ctx.me
        return bool(me.alliance_faction_ids) and me.resources.spice >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: the Early arc, else ``!InAlliance(None)``
        (``xor al, 1``)."""

        if p.game_arc() == 0:
            return True
        return not p.ctx.me.alliance_faction_ids


@port(_PA + "ambush")
class AmbushAbility(StrengthIntrigueAbility):
    """``AmbushAbility`` (Strength 4, CombatValue 5.0): the base ``Evaluate``; ``Cost``
    = NoCost; no ``IsBadIntrigue``."""


@port(_PA + "private_army")
class PrivateArmyAbility(StrengthIntrigueAbility):
    """``PrivateArmyAbility`` (Strength 5, CombatValue 7.0): the base ``Evaluate``,
    which dumps it at the literal 50.0 instead of ``100 - CombatValue`` in a decisive
    fight (``Owner.ArchID == PrivateArmy``,
    ``abilities/intrigue.StrengthIntrigueAbility``)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Spice, 2)``."""

        return p.ctx.me.resources.spice >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: the Early arc (``GetGameArc() == 0``)
        is bad, the Late arc (not 1) is not, the Mid arc reads
        ``IsSpiceShort``."""

        arc = p.game_arc()
        if arc == 0:
            return True
        if arc != 1:
            return False
        return p.is_spice_short()


@port(_PA + "tiebreaker")
class TiebreakerAbility(StrengthIntrigueAbility):
    """``TiebreakerAbility`` (Strength 2, CombatValue 2.5): the Combat half of
    Tiebreaker; the base ``Evaluate``; ``Cost`` = NoCost."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: ``GetGameArc() == 2``."""

        return p.game_arc() == 2


@port(_PA + "tiebreaker_ability2")
class TiebreakerAbility2(IntrigueAbility):
    """``TiebreakerAbility2``: the Endgame half of Tiebreaker. constructor stores timing
    4; ``Cost`` = NoCost; ``IsEndgamePlayable`` = false (no AI caller)."""

    ability_timing: ClassVar[int] = ENDGAME_TIMING

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TiebreakerAbility2.Evaluate``: ungated, the literal
        100.0 (the first non-combat ability ``MakeChoice`` finds on the card)."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("Tiebreaker | 100")


@port(_PA + "master_tactician")
class MasterTacticianAbility(StrengthIntrigueAbility):
    """``MasterTacticianAbility`` (Strength 3, CombatValue 4.0): gain the strength, or
    retreat troops (``Cost`` = NoCost; no ``IsBadIntrigue``)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MasterTacticianAbility.Evaluate``.

        ``StrengthIntrigueAbility.Evaluate`` is called non-virtually first; its value is
        stored with ``Int(0)`` ("gain the strength", even when it is 0 or less).
        Tactical Option's retreat test follows with Master Tactician's own numbers:
        ``cur = P.Strength``; ``nextBelow`` the highest opponent strength not above
        ``cur`` (``cur >= s``; 0 for none); some opponent from ``cur`` up to but
        excluding ``cur + 3`` blocks it, as does the climax or ``cur - nextBelow < 10``.
        Otherwise ``min(3, troops - 1)`` Conflict troops (the dependent targets of
        option
        1) retreat at the literal 150.0 when that is at least 1.
        """

        choice = _Choice()
        v = self._strength_choice(p).value
        choice.update_responses(v, ((0,),))
        cur = p.ctx.me.combat_strength
        opp = [o.combat_strength for o in p.ctx.opponents]
        next_below = max((s for s in opp if cur >= s), default=0)
        close = any(s - cur >= 0 and s - cur < 3 for s in opp)
        if p.is_climax() or close or cur - next_below < 10:
            return choice.answer("Master Tactician strength")
        troops = _options(request, 1)
        n = min(3, len(troops) - 1)
        if n <= 0:
            return choice.answer("Master Tactician strength")
        choice.update_responses(150.0, ((1,), tuple(troops[:n])))
        return choice.answer(f"Master Tactician| retreat {n} troops: 150")


# ---------------------------------------------------------------------------
# Combat intrigues: the rest
# ---------------------------------------------------------------------------


@port(_PA + "staged_incident")
class StagedIncidentAbility(IntrigueAbility):
    """``StagedIncidentAbility``: retreat troops from the Conflict for a reward.
    constructor stores timing 5 (Combat); not a ``StrengthIntrigueAbility`` (no Strength
    attribute)."""

    timing: ClassVar[Timing] = Timing.COMBAT
    ability_timing: ClassVar[int] = COMBAT_TIMING

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasUnitsDeployed<Troop>.AtLeast(3)``
        (Bloodlines Commanders are troops, D1)."""

        return p.conflict_troop_count() >= 3

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StagedIncidentAbility.Evaluate``: ``ShouldPlayRetreatIntrigue("Staged
        Incident", 6, 10, 3)``; a positive ``s`` is stored as ``(double) s`` with no
        sub-targets."""

        choice = _Choice()
        s = p.should_play_retreat_intrigue("Staged Incident", 6, 10, 3)
        if s > 0:
            choice.update_targets(float(s), None)
        return choice.answer("Staged Incident")


def _late_and_not_first(p: Profile) -> bool:
    """``IsBadIntrigue`` of Demand Respect and To the Victor (,
): in the Late arc (``GetGameArc() == 2``) the card is bad
    unless the seat leads now; ``CurrentConflictRank(0)`` null counts as bad, a rank of
    2 or more too. Any other arc: false."""

    if p.game_arc() != 2:
        return False
    rank = p.current_conflict_rank(0)
    return rank is None or rank >= 2


@port(_PA + "demand_respect")
class DemandRespectAbility(IntrigueAbility):
    """``DemandRespectAbility``: when you win a Conflict, one Influence, or pay 2 spice
    for two with one Faction. constructor stores timing 3 (CombatResolution); ``Cost`` =
    ``IsRewardPlace(1)`` (the engine offers it in the sole winner's reward window)."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION
    ability_timing: ClassVar[int] = COMBAT_RESOLUTION_TIMING

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` (``_late_and_not_first``)."""

        return _late_and_not_first(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DemandRespectAbility.Evaluate``.

        Away from the climax ``G(None, +1)`` must reach the literal 2.5. The prompt
        needs two target informations (``Dictionary.Count < 2`` returns); ``infos[0]``
        are the faction tracks. ``pay`` is 1 when the player holds 2 spice, one
        Influence is worth at most the literal 3.25 and two Influence at least the
        literal 7.0, else 0. Each track is priced ``G(track, pay + 1)`` and stored as
        ``value + 90.0`` with ``[Int(pay), [track]]``.
        """

        choice = _Choice()
        if (
            p.gain_influence_value(_ANY_FACTION, 1, -1, False).sum < 2.5
            and not p.is_climax()
        ):
            return choice.answer("Demand Respect")
        if len(request.infos) < 2:
            return choice.answer("Demand Respect")
        tracks = _targets(request, 0, Kind.TRACK)
        g2 = p.gain_influence_value(_ANY_FACTION, 2, -1, False)
        pay = 0
        if p.ctx.me.resources.spice >= 2:
            g1 = p.gain_influence_value(_ANY_FACTION, 1, -1, False)
            if g1.sum <= 3.25 and g2.sum >= 7.0:
                pay = 1
        for track in tracks:
            g = p.gain_influence_value(track.ref, pay + 1, -1, False)
            choice.update_responses(g.sum + 90.0, ((pay,), (track.ref,)))
        return choice.answer("Demand Respect")


@port(_PA + "to_the_victor")
class ToTheVictorAbility(IntrigueAbility):
    """``ToTheVictorAbility``: when you win a Conflict, 3 spice. constructor stores
    timing 3 (CombatResolution); ``Cost
`` = ``IsRewardPlace(1)``."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION
    ability_timing: ClassVar[int] = COMBAT_RESOLUTION_TIMING

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` (``_late_and_not_first``)."""

        return _late_and_not_first(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ToTheVictorAbility.Evaluate``: ungated, the literal
        100.0."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer("To the Victor | 100")


# ---------------------------------------------------------------------------
# Endgame intrigues
# ---------------------------------------------------------------------------


class _EndgameBaseSetAbility(IntrigueAbility):
    """The two original-game Endgame cards with an ``Evaluate`` (the app's classes
    derive from ``IntrigueAbility``; every constructor stores timing 4 and ``Cost`` is
    NoCost)."""

    ability_timing: ClassVar[int] = ENDGAME_TIMING

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``Evaluate`` of both classes (): ungated, the
        literal 100.0 (``EndgamePhase`` auto-plays them; no prompt)."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer(f"{type(self).__name__} | 100")


@port(_PA + "corner_the_market")
class CornerTheMarketAbility(_EndgameBaseSetAbility):
    """``CornerTheMarketAbility`` (Endgame). ``IsEndgamePlayable`` and
    ``GetConditionalEndgameVP`` have no AI caller."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: ``CountTheSpiceMustFlow == 0``
        (: the Spice Must Flow cards among ``AllImperiumCards``)."""

        return _count_the_spice_must_flow(p) == 0


@port(_PA + "plans_within_plans")
class PlansWithinPlansAbility(_EndgameBaseSetAbility):
    """``PlansWithinPlansAbility`` (Endgame). ``IsEndgamePlayable`` and
    ``GetConditionalEndgameVP`` have no AI caller."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: the Early arc is bad; the Late arc when fewer than 2
        Faction tracks hold the player at rank 3 or more (``Track.CurrentRank(player) >=
        3``); the Mid arc is not."""

        arc = p.game_arc()
        if arc == 0:
            return True
        if arc != 2:
            return False
        me = p.ctx.me
        return sum(1 for f in FACTIONS if _influence(me, f) >= 3) < 2


# ---------------------------------------------------------------------------
# Plots that read the board and the hand
# ---------------------------------------------------------------------------


def best_option(
    p: Profile, cards: Sequence[Entity] | None = None
) -> tuple[Entity | None, Entity | None, float]:
    """``AIProfile.GetBestOption(possibleCards)`` (05-agent-placement.md §10): over
    ``possibleCards`` (default the hand) and each card's ``Board.ValidSpaces`` in board
    order, ``AgentAbility. ValueForPlayer(P, [space]).Sum + Σ
    space.Abilities.ValueForPlayer(P, [card]).Sum`` (a Merge); a strict maximum from
    0.0, no ``CanBeRun`` filter. Returns ``(card, space, value)``; no option above 0.0
    leaves the card and space None. Its callers are Rise of Ix's (Glimpse the Path,
    Ixian Probe, Ilesa's One Step Ahead)."""

    hand = list(cards) if cards is not None else _hand_entities(p)
    cache: SpaceCache = {}
    best: tuple[Entity | None, Entity | None, float] = (None, None, 0.0)
    for card in hand:
        valid = valid_space_ids(p, card.ref, cache)
        for space in _board_spaces(p):
            if space.ref not in valid:
                continue
            value = _agent_card_value(p, card, space) + _space_value(p, space, (card,))
            if value > best[2]:
                best = (card, space, value)
    return best


def _board_spaces(p: Profile) -> list[Entity]:
    """``Match.BoardSpaces`` (``MatchExtensions.BoardSpaces``) in order."""

    board = p.ctx.board
    return [space_entity(space_id, board) for space_id in board_space_ids(board)]


def _can_pay_space(p: Profile, space: Entity) -> bool:
    """``HasResourceCost.CanBePaid`` for a space target.

    A positive ``SpiceCost`` / ``WaterCost`` must not exceed the player's
    spice / water; a positive ``SolariCost + SolariDiscount`` (the discount is
    added, as in ``CanAgentAbilityBePlayedWithSpace``) must not exceed the
    Solari. Judgement: the spice branch's ``Match.IsScenario`` AI shortcut
 never holds in a normal game, and the ``PersuasionCost`` test
    at the end only reads a card target.
    """

    resources = p.ctx.me.resources
    spice_cost = space.int_attr("SpiceCost")
    if spice_cost > 0 and spice_cost > resources.spice:
        return False
    water_cost = space.int_attr("WaterCost")
    if water_cost > 0 and water_cost > resources.water:
        return False
    solari_cost = space_solari_cost(p, space) + space.int_attr("SolariDiscount")
    return not (solari_cost > 0 and solari_cost > resources.solari)


def _has_agent(p: Profile, space: Entity) -> bool:
    """``Space.HasAgent``: some seat's Agent stands there."""

    return bool(p.ctx.space_occupants(space.ref))


def _space_value(p: Profile, space: Entity, with_entities: Sequence[Entity]) -> float:
    """``space.Abilities.Sum(a => a.ValueForPlayer(P, with).Sum)``
    (``Enumerable.Sum<double>``: left to right from 0.0)."""

    total = 0.0
    for ability in abilities_of(space):
        total += ability.value_for_player(p, with_entities).sum
    return total


def _agent_card_value(p: Profile, card: Entity, space: Entity) -> float:
    """``card.Abilities.OfType<AgentAbility>().Sum(a => a.ValueForPlayer(P,
    [space]).Sum)``."""

    total = 0.0
    for ability in abilities_of(card):
        if isinstance(ability, AgentAbility):
            total += ability.value_for_player(p, (space,)).sum
    return total


def _hand_entities(p: Profile) -> list[Entity]:
    """``P.Hand.children.OfType<ImperiumPlayable>()`` in hand order."""

    return [card_entity(ref, p.ctx.seat) for ref in p.ctx.hand]


@port(_PA + "rapid_mobilization")
class RapidMobilizationAbility(IntrigueAbility):
    """``RapidMobilizationAbility``: deploy garrison troops to the Conflict at once
    (``Cost`` = NoCost). The deploy search is
    ``abilities/intrigue.intrigue_deploy_troops``."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: the Early arc, else
        ``IsTroopShort``."""

        return p.game_arc() == 0 or p.is_troop_short()

    def troop_value(self, p: Profile) -> int:
        """``TroopValue``: twice the garrison in the Reveal turn
        (``IsInPlayerTurn(Reveal)``), else ``max(0, 2 * garrison - 3 *
        RemainingAgents)``."""

        garrison = p.garrison_troop_count()
        if _in_player_turn(p, _REVEAL_TURN):
            return 2 * garrison
        return max(0, 2 * garrison - 3 * p.ctx.me.agents_available)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RapidMobilizationAbility.Evaluate``: the deploy
        targets (``infos[0].options``, one index per garrison unit) go through
        ``IntrigueDeployTroops``; a positive count stores the first ``n`` at
        the literal 100.0."""

        choice = _Choice()
        troops = list(_options(request, 0))
        n = intrigue_deploy_troops(p, troops)
        if n > 0:
            choice.update_targets(100.0, tuple(troops[:n]))
        return choice.answer("Rapid Mobilization")


@port(_PA + "reinforcements")
class ReinforcementsAbility(IntrigueAbility):
    """``ReinforcementsAbility``: pay 3 Solari, recruit troops and deploy them in the
    Reveal turn."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Solari, 3)``."""

        return p.ctx.me.resources.solari >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: the Early arc, else
        ``IsSolariShort``."""

        return p.game_arc() == 0 or p.is_solari_short()

    def troop_value(self, p: Profile) -> int:
        """``TroopValue``: 0 below 3 Solari, else
        ``min(6, 2 * troops in the Supply)`` (``Supply.children.OfType<
        Troop>().Count()``; ``[+0x108]`` of the player)."""

        me = p.ctx.me
        if me.resources.solari < 3:
            return 0
        return min(6, 2 * me.troops_supply)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ReinforcementsAbility.Evaluate``.

        ``infos[0].options`` are the recruited troops the deploy may take.
        ``GetUnitsToDeploy(units, -1)`` picks how many; none returns. Only in
        the Reveal turn, and ``ShouldPlayTroopIntrigue("Reinforcements", 6, 4,
        3)`` must be positive; the value is ``(double) s`` with the chosen
        troops.
        """

        choice = _Choice()
        troops = list(_options(request, 0))
        n = p.units_to_deploy(len(troops), -1)
        ids = tuple(troops[:n])
        if not ids:
            return choice.answer("Reinforcements | would deploy 0 troops")
        if not _in_player_turn(p, _REVEAL_TURN):
            return choice.answer("Reinforcements")
        s = p.should_play_troop_intrigue("Reinforcements", 6, 4, 3)
        if s < 1:
            return choice.answer("Reinforcements")
        choice.update_targets(float(s), ids)
        return choice.answer("Reinforcements")


@port(_PA + "calculated_hire")
class CalculatedHireAbility(IntrigueAbility):
    """``CalculatedHireAbility``: pay a spice, take the Mentat."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``Spice >= 1`` then (``CostAction.Then``) a
        ``BoolAction`` that the Mentat piece is on its space
        (``Cost``: ``child.Is(EntityNames.Mentat)``), our
        ``AppContext.mentat_rests``."""

        return p.ctx.me.resources.spice >= 1 and p.ctx.mentat_rests

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: bad in the Mid arc (``GetGameArc() == 1``) and whenever it
        is not the final round; in the final round bad unless the Mentat piece still
        rests on its space. Judgement: the app reads the piece's ``Color != Black(1)``
        on the Mentat space's child; the neutral Mentat is Black, a taken or reserved
        one is not, which is ``AppContext.mentat_rests`` (``IsBadIntrigue`` / its
        filter: no child / the child named Mentat)."""

        if p.game_arc() == 1 or not p.is_final_round():
            return True
        return not p.ctx.mentat_rests

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CalculatedHireAbility.Evaluate``.

        The best space is the highest-valued (``OrderByDescending``, stable) of
        ``Distinct(SelectMany(hand, ValidSpaces))``, each valued
        ``space.Abilities.Sum(ValueForPlayer(P, []))``. With one, and the current
        Conflict interest at least the lower posture bound and ``Spice - best.SpiceCost
        > 0``, it plays at the literal 100.0.
        """

        choice = _Choice()
        best: Entity | None = None
        best_value = 0.0
        cache: SpaceCache = {}
        seen: set[str] = set()
        for ref in p.ctx.hand:
            valid = valid_space_ids(p, ref, cache)
            for space in _board_spaces(p):
                if space.ref not in valid or space.ref in seen:
                    continue
                seen.add(space.ref)
                value = _space_value(p, space, ())
                if best is None or value > best_value:
                    best, best_value = space, value
        if best is None:
            return choice.answer("Calculated Hire")
        if p.current_conflict_interest().sum >= p.conflict_posture_bounds()[0]:
            if p.ctx.me.resources.spice - best.int_attr("SpiceCost") > 0:
                choice.update_targets(100.0, None)
        return choice.answer("Calculated Hire")


@port(_PA + "urgent_mission")
class UrgentMissionAbility(IntrigueAbility):
    """``UrgentMissionAbility``: recall one of your Agents to the hand's reach.
    ``Evaluate``'s ``GetTargets<Agent>`` is ``request.infos[0].entities`` (AGENT,
    ``agent_entity(space, seat)``); the answer is ``((agent,),)``."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasDeployedAgents(1)``."""

        return len(p.ctx.me.agent_locations) >= 1

    def _a_card_is_worth_playing(self, p: Profile) -> bool:
        """``Evaluate``: some hand card has a valid space where the card's
        ``AgentAbility`` values with ``[space]`` plus the space's abilities' values with
        ``[]`` reach the literal 5.0."""

        cache: SpaceCache = {}
        for card in _hand_entities(p):
            valid = valid_space_ids(p, card.ref, cache)
            for space in _board_spaces(p):
                if space.ref not in valid:
                    continue
                total = _agent_card_value(p, card, space) + _space_value(p, space, ())
                if total >= 5.0:
                    return True
        return False

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``UrgentMissionAbility.Evaluate``.

        Only with no Agent left (``RemainingAgents`` not empty returns) at the
        turn start, with a hand card worth playing. Away from the climax the
        Conflict interest must pass the upper posture bound, or lie above the
        lower one with ``GetBuyValue`` at most the literal 8.5. Then the
        recalled Agent is ``GetRecallAgent(agents)``, at the literal 100.0.
        """

        choice = _Choice()
        if p.ctx.me.agents_available > 0:
            return choice.answer("Urgent Mission")
        if not _in_player_turn(p, _UNDETERMINED):
            return choice.answer("Urgent Mission")
        if not self._a_card_is_worth_playing(p):
            return choice.answer("Urgent Mission")
        if not p.is_climax():
            lower, upper = p.conflict_posture_bounds()
            interest = p.current_conflict_interest().sum
            if not interest > upper:
                if interest <= lower:
                    return choice.answer("Urgent Mission")
                if p.buy_value() > 8.5:
                    return choice.answer("Urgent Mission")
        agent = p.recall_agent(_targets(request, 0, Kind.AGENT))
        if agent is None:
            return choice.answer("Urgent Mission")
        choice.update_targets(100.0, (agent.ref,))
        return choice.answer("Urgent Mission | recall")


#: ``imperium.original.kwisatz_haderach`` (``InfiltrateAbility.Evaluate``: ``ArchID !=
#: KwisatzHaderach.archID``).
_KWISATZ_HADERACH: Final = "imperium.original.kwisatz_haderach"


@port(_PA + "infiltrate")
class InfiltrateAbility(IntrigueAbility):
    """``InfiltrateAbility``: enemy Agents do not block your next Agent this turn
    (``Cost`` = NoCost; ``IsBadIntrigue``
 = false)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``InfiltrateAbility.Evaluate``.

        Needs an Agent left, the turn start (``PlayerTurn == Undetermined``) and no
        Kwisatz Haderach in hand (``Hand.All(...)``). Then for each hand card and each
        board space that is *not* one of the card's ``ValidSpaces`` but has an Agent,
        none of the player's own, shows an Agent icon the card also shows
        (``ActionIcon`` in ``IconList``) and passes ``HasResourceCost``: the space's
        abilities valued with ``[card]`` plus the card's ``AgentAbility`` values with
        ``[space]`` (each an ``Aggregate`` of ``Merge``) less the literal 0.1
        ("Infiltrate penalty: -0.1") is stored with no sub-targets (strictly better
        replaces).
        """

        choice = _Choice()
        me = p.ctx.me
        if me.agents_available <= 0:
            return choice.answer("Infiltrate")
        if not _in_player_turn(p, _UNDETERMINED):
            return choice.answer("Infiltrate")
        hand = _hand_entities(p)
        if any(card.short == _KWISATZ_HADERACH for card in hand):
            return choice.answer("Infiltrate")
        cache: SpaceCache = {}
        for card in hand:
            valid = valid_space_ids(p, card.ref, cache)
            icons = card.list_attr("IconList")
            for space in _board_spaces(p):
                occupants = p.ctx.space_occupants(space.ref)
                if (
                    space.ref in valid
                    or not occupants
                    or p.ctx.seat in occupants
                    or space.attr("AgentIcon") not in icons
                    or not _can_pay_space(p, space)
                ):
                    continue
                agent_card = _agent_card_value(p, card, space)
                space_value = _space_value(p, space, (card,))
                choice.update_targets(space_value + agent_card + -0.1, None)
        return choice.answer("Infiltrate")


def _envoy_dispatched(p: Profile) -> bool:
    """``P.GetAttributeValue<bool>(EnvoyDispatched)``: Dispatch an Envoy was
    played this turn. Ours: all four Faction icons are among the card's
    granted ones (``PlayerState.granted_agent_icon_turn``; only Dispatch an
    Envoy grants them in the original game)."""

    granted = p.ctx.me.granted_agent_icon_turn.split(",")
    return all(icon in granted for icon in FACTIONS)


@port(_PA + "dispatch_an_envoy")
class DispatchAnEnvoyAbility(IntrigueAbility):
    """``DispatchAnEnvoyAbility``: the card played this turn shows the four Faction
    icons (``Cost`` = NoCost)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: false before the final round; in it,
        bad once no Agent is left (``ListUtil.IsEmpty(RemainingAgents)``)."""

        if not p.is_final_round():
            return False
        return p.ctx.me.agents_available == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DispatchAnEnvoyAbility.Evaluate``.

        Not after an envoy was dispatched this turn, with an Agent left, at the turn
        start. The best space is the highest-valued (abilities valued with ``[]``,
        stable) free space the player can pay (``!HasAgent && HasResourceCost``); the
        best hand card exists (ordered by agent value, only its existence is read). The
        envoy plays at the literal 100.0 when the best space belongs to a Faction
        (``Faction != None``) and no hand card already shows its icon
        (``!IconList.Contains(ActionIcon(best))``).
        """

        choice = _Choice()
        if _envoy_dispatched(p) or p.ctx.me.agents_available <= 0:
            return choice.answer("Dispatch an Envoy")
        if not _in_player_turn(p, _UNDETERMINED):
            return choice.answer("Dispatch an Envoy")
        best: Entity | None = None
        best_value = 0.0
        for space in _board_spaces(p):
            if _has_agent(p, space) or not _can_pay_space(p, space):
                continue
            value = _space_value(p, space, ())
            if best is None or value > best_value:
                best, best_value = space, value
        hand = _hand_entities(p)
        if best is None or not hand:
            return choice.answer("Dispatch an Envoy")
        if best.attr("Faction") not in FACTION_NAMES.values():
            return choice.answer("Dispatch an Envoy")
        icon = best.attr("AgentIcon")
        if all(icon not in card.list_attr("IconList") for card in hand):
            choice.update_targets(100.0, None)
        return choice.answer("Dispatch an Envoy | 100")


# ---------------------------------------------------------------------------
# Double Cross, Bypass Protocol, Bindu Suspension
# ---------------------------------------------------------------------------

#: ``space.original.*`` that ``BinduSuspensionAbility.Evaluate``
#: tests by ``ArchID`` (Mentat, Research Station, Conspire).
_BINDU_KEEP_SPACES: Final = frozenset(
    {
        "space.original.mentat",
        "space.original.research_station",
        "space.original.conspire",
    }
)


@port(_PA + "double_cross")
class DoubleCrossAbility(IntrigueAbility):
    """``DoubleCrossAbility``: pay a Solari to take one of an opponent's deployed
    troops. ``infos[0].options`` are the offered opponents' seats (the app's ``Player``
    targets); the answer is ``((seat,),)``."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``Solari >= 1`` then (``CostAction.Then``)
        ``OpponentHasUnitsDeployed<Troop>.Any()``."""

        return p.ctx.me.resources.solari >= 1 and any(
            p.conflict_troop_count(o) > 0 for o in p.ctx.opponents
        )

    def troop_value(self, p: Profile) -> int:
        """``TroopValue``: 0 without Solari, else ``min(4, 2 * troops in the Supply +
        2)``."""

        me = p.ctx.me
        if me.resources.solari <= 0:
            return 0
        return min(4, 2 * me.troops_supply + 2)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DoubleCrossAbility.Evaluate``.

        Outside the Reveal turn four held Intrigue cards are needed. With no troop of
        its own in the Conflict (``ConflictTroops < 1``) every opponent with exactly one
        troop there and exactly one Agent left is stored at its Victory points.
        Otherwise, when the expected winner (``GetExpectedCombatOrder().First``, not the
        player) would reach ``EndgameTriggerScore`` with the Conflict's Victory points
        (``VP + conflictVP >= trigger``) and is not behind the player (``VP + conflictVP
        >= VP(player)``), each opponent is stored at its ``EstOpponentStrength``. Else,
        with the Conflict interest above the lower posture bound, each opponent is
        stored at its estimated strength when that is within 4 of the player's, else at
        0.
        """

        choice = _Choice()
        seats = _options(request, 0)
        if not _hand_or_reveal(p):
            return choice.answer("Double Cross")
        me = p.ctx.me
        if p.conflict_troop_count() < 1:
            for seat in seats:
                opponent = p.ctx.player(seat)
                if p.conflict_troop_count(opponent) == 1 and (
                    opponent.agents_available == 1
                ):
                    choice.update_targets(float(p.ctx.vp(opponent)), (seat,))
            return choice.answer("Double Cross")
        order = p.expected_combat_order()
        first = order[0] if order else None
        conflict = _current_conflict(p)
        conflict_vp = conflict.int_attr("VictoryPoints") if conflict else 0
        if first is not None and first != p.ctx.seat:
            reach = p.ctx.vp(p.ctx.player(first)) + conflict_vp
            if reach >= p.ctx.endgame_trigger_score and reach >= p.ctx.vp(me):
                for seat in seats:
                    choice.update_targets(
                        float(p.est_opponent_strength(seat).sum), (seat,)
                    )
                return choice.answer("Double Cross | endgame")
        if not p.current_conflict_interest().sum > p.conflict_posture_bounds()[0]:
            return choice.answer("Double Cross")
        expected = p.est_strength().sum
        for seat in seats:
            strength = p.est_opponent_strength(seat).sum
            near = abs(strength - expected) < 5
            choice.update_targets(float(strength if near else 0), (seat,))
        return choice.answer("Double Cross")


@port(_PA + "bypass_protocol")
class BypassProtocolAbility(IntrigueAbility):
    """``BypassProtocolAbility``: acquire a card of cost 3 or less, or pay 2 spice for
    one of cost 5 or less to the top of the deck.

    Request: ``infos[0].entities`` the CARDs of the free option (cost 3 or
    less), ``infos[1].entities`` those of the paid option (cost 5 or less;
    ``GetBypassProtocolTargets(.., 3)`` / ``(.., 5)``). Answer:
    ``((option,), (card,), (0,))``: the option, the card and the destination
    picker's first option (judgement: the shared tail zeroes the third
    ``IntTargetResponse``).
    """

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: bad in the Late arc (at ``GetGameArc() == 2``),
        ``IsSpiceShort`` in the Early arc, good in the Mid arc."""

        arc = p.game_arc()
        if arc == 2:
            return True
        if arc == 0:
            return p.is_spice_short()
        return False

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BypassProtocolAbility.Evaluate``.

        Needs two target informations (``Dictionary.Count < 2`` returns). With 2 spice
        and a best paid-option card (``OrderByDescending(AcquireValue)``) worth at least
        the literal 5.4 the paid option is stored at the literal 100.0. Otherwise the
        best free-option card worth at least the literal 3.0 (returns) is stored at
        100.0.
        """

        choice = _Choice()
        if len(request.infos) < 2:
            return choice.answer("Bypass Protocol")
        free = _targets(request, 0, Kind.CARD)
        paid = _targets(request, 1, Kind.CARD)
        if p.ctx.me.resources.spice >= 2:
            best = _best_acquire(p, paid)
            if best is not None and p.acquire_value(best).sum >= 5.4:
                choice.update_responses(100.0, ((1,), (best.ref,), (0,)))
                return choice.answer("Bypass Protocol | pay 2 spice")
        best = _best_acquire(p, free)
        if best is None or p.acquire_value(best).sum < 3.0:
            return choice.answer("Bypass Protocol")
        choice.update_responses(100.0, ((0,), (best.ref,), (0,)))
        return choice.answer("Bypass Protocol | free")


def _best_acquire(p: Profile, cards: Sequence[Entity]) -> Entity | None:
    """``cards.OrderByDescending(c => c.AcquireValue(P).Sum).FirstOrDefault()``
    (stable: the first of the highest)."""

    best: Entity | None = None
    best_value = 0.0
    for card in cards:
        value = p.acquire_value(card).sum
        if best is None or value > best_value:
            best, best_value = card, value
    return best


@port(_PA + "bindu_suspension")
class BinduSuspensionAbility(IntrigueAbility):
    """``BinduSuspensionAbility``: draw a card at the turn start, then pass the turn or
    play it normally. ``Cost`` = ``IsTakingTurn`` (the engine offers it as the first
    action of a turn); no target information. The pass is chosen later by
    ``choose_pass``."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue``: always true."""

        return True

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BinduSuspensionAbility.Evaluate`` (every update is
        ``UpdateSelectionResponses(v, src, Array.Empty)``).

        At the climax it plays at the literal 100.0. Otherwise, with no Agent left and
        cards to draw (the draw pile, else the discard pile), the buy gains of the
        cards' rounded average Persuasion (``Convert.ToInt32``) reaching the literal 2.0
        play it at 100.0. Else the best space is the highest-valued (stable) of
        ``Distinct( SelectMany(hand, ValidSpaces))`` (abilities valued with ``[]``); the
        turn is passed at the literal 99.0 unless that space is the Swordmaster, the
        High Council, the Mentat, the Research Station or Conspire, or holds more than 1
        bonus spice, or belongs to a Faction whose Influence is worth ``1.75`` or more.
        """

        choice = _Choice()
        me = p.ctx.me
        if p.is_climax():
            choice.update_responses(100.0, ())
            return choice.answer("Bindu Suspension | Is Climax")
        cards = [*sorted(me.deck)] or [*me.discard_pile]
        if me.agents_available == 0 and cards:
            persuasion = [
                card_entity(i, p.ctx.seat).int_attr("Persuasion") for i in cards
            ]
            average = sum(persuasion) / len(persuasion)
            if p.buy_gains(round(average)) >= 2.0:
                choice.update_responses(100.0, ())
                return choice.answer("Bindu Suspension | no agents left")
        best: Entity | None = None
        best_value = 0.0
        cache: SpaceCache = {}
        seen: set[str] = set()
        for ref in p.ctx.hand:
            valid = valid_space_ids(p, ref, cache)
            for space in _board_spaces(p):
                if space.ref not in valid or space.ref in seen:
                    continue
                seen.add(space.ref)
                value = _space_value(p, space, ())
                if best is None or value > best_value:
                    best, best_value = space, value
        if best is None:
            return choice.answer("Bindu Suspension")
        if (
            best.short in SWORDMASTER_SPACE_ARCHETYPES
            or is_high_council_space(best)
            or best.short in _BINDU_KEEP_SPACES
            or _space_bonus_spice(p, best) > 1
        ):
            return choice.answer("Bindu Suspension")
        if best.attr("Faction") in FACTION_NAMES.values():
            faction = _APP_TO_FACTION[str(best.attr("Faction"))]
            if not 1.75 > p.gain_influence_value(faction, 1, -1, False).sum:
                return choice.answer("Bindu Suspension")
        choice.update_responses(99.0, ())
        return choice.answer("Bindu Suspension | pass")

    def choose_pass(self, p: Profile) -> int:
        """``BinduSuspensionAbility.ChoosePassEvaluator``: the ``AIChoiceCustom`` answer
        of "pass the turn?": 1 (pass) when the current Conflict's ``ConflictLevel``
        (default 1) is at most 2, else 0."""

        conflict = _current_conflict(p)
        level = conflict.int_attr("ConflictLevel", 1) if conflict else 1
        return 1 if level <= 2 else 0
