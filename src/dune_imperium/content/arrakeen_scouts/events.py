"""Arrakeen Scouts events [Scouts event: <name>].

``weight_tickets`` is the app's baseWeight x subWeight x 10: 10 for a
single event, 5 for each variant of Spice Gain and Intrigue Bonus (1.0 x
0.5), and 6 for each of the five variants of the two Influence families
(3.0 x 0.2). Covert Operation and Clear the Market have a CHOAM and a
no-CHOAM variant at 10 each; the CHOAM filter keeps one of them.
Variants share an ``AppDefinition.family``; the schedule draws at most one
event per family. Effects are paraphrased in ``docs/rules/arrakeen-scouts.md``.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.types import (
    BOTH_POOLS,
    IMMORTALITY_ONLY,
    AcquireReserveCardToHand,
    AppDefinition,
    AutomaticEffect,
    EventKind,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    PaySpecimens,
    RoundModifier,
    ScoutsEvent,
    ScoutsOption,
    SecretChoice,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    GainInfluence,
    GainResources,
    GenerateSpecimens,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    Research,
    TakeContract,
    TrashIntrigueCard,
    TrashPersonalCard,
)

_ROUNDS: Final = (4, 7)
_TRASH_FROM_HAND: Final = TrashPersonalCard(hand_only=True, mandatory=True)


def _influence(faction: Faction) -> GainInfluence:
    return GainInfluence(factions=(faction,))


EVENTS: Final[tuple[ScoutsEvent, ...]] = (
    # --- Spice Gain (family 13) -----------------------------------------------------
    ScoutsEvent(
        event_id="private_stock",
        name="Private Stock",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=5,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_SpiceGain_PrivateStock", 13),
        options=(
            ScoutsOption(rewards=(GainResources(spice=1),)),
            ScoutsOption(rewards=(DrawPersonalCards(1),)),
        ),
    ),
    ScoutsEvent(
        event_id="market_research",
        name="Market Research",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=5,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_SpiceGain_MarketResearch", 13, 1),
        options=(
            ScoutsOption(costs=(RecallSpy(1),), rewards=(GainResources(spice=2),)),
        ),
        passable=True,
    ),
    # --- Intrigue Bonus (family 14) -------------------------------------------------
    ScoutsEvent(
        event_id="smoke_and_mirrors",
        name="Smoke and Mirrors",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=5,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_IntrigueBonus_SmokeAndMirrors", 14),
        options=(
            ScoutsOption(rewards=(PlaceSpy(),)),
            ScoutsOption(
                costs=(PayResources(solari=1),), rewards=(DrawIntrigueCards(1),)
            ),
        ),
    ),
    ScoutsEvent(
        event_id="rotating_doors",
        name="Rotating Doors",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=5,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_IntrigueBonus_RotatingDoors2", 14, 1),
        options=(
            ScoutsOption(
                costs=(TrashIntrigueCard(),),
                rewards=(DrawIntrigueCards(1), DrawPersonalCards(1)),
            ),
        ),
        passable=True,
    ),
    # --- Single-event families ------------------------------------------------------
    ScoutsEvent(
        event_id="moment_of_revelation",
        name="Moment of Revelation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_MomentOfRevelation", 15),
        options=(
            ScoutsOption(
                costs=(PayResources(spice=2),),
                rewards=(AcquireReserveCardToHand("prepare_the_way"),),
            ),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="water_discipline",
        name="Water Discipline",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_WaterDiscipline", 16),
        options=(
            ScoutsOption(
                costs=(PayResources(water=1),),
                rewards=(TrashPersonalCard(), DrawPersonalCards(1)),
            ),
        ),
        passable=True,
    ),
    # --- Influence Gain (family 17) -------------------------------------------------
    ScoutsEvent(
        event_id="royal_delegation",
        name="Royal Delegation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_RoyalDelegation", 17),
        options=(
            ScoutsOption(
                costs=(PayResources(solari=2),),
                rewards=(_influence(Faction.EMPEROR),),
            ),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="guild_negotiation",
        name="Guild Negotiation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_Negotiation2", 17, 1),
        options=(
            ScoutsOption(
                costs=(PayResources(spice=1), DiscardFromHand(1)),
                rewards=(_influence(Faction.SPACING_GUILD),),
            ),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="covert_assistance",
        name="Covert Assistance",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_CovertAssistance", 17, 2),
        options=(
            ScoutsOption(
                costs=(RecallSpy(1),), rewards=(_influence(Faction.BENE_GESSERIT),)
            ),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="gift_of_water",
        name="Gift of Water",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_GiftOfWater", 17, 3),
        options=(
            ScoutsOption(
                costs=(PayResources(water=1),), rewards=(_influence(Faction.FREMEN),)
            ),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="share_intelligence",
        name="Share Intelligence",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_ShareIntelligence", 17, 4),
        options=(
            ScoutsOption(
                costs=(TrashIntrigueCard(), PayResources(solari=1)),
                rewards=(GainInfluence(),),
            ),
        ),
        passable=True,
    ),
    # --- Influence Reduction (family 18) ----------------------------------------------
    ScoutsEvent(
        event_id="political_equilibrium",
        name="Political Equilibrium",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Equilibrium2", 18),
        automatic=AutomaticEffect.POLITICAL_EQUILIBRIUM,
    ),
    ScoutsEvent(
        event_id="crackdown",
        name="Crackdown",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Crackdown", 18, 1),
        options=(
            ScoutsOption(costs=(RecallSpy(1),)),
            ScoutsOption(costs=(LoseFactionInfluence(Faction.EMPEROR),)),
        ),
    ),
    ScoutsEvent(
        event_id="water_for_spice_smugglers",
        name="Water for Spice Smugglers",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Smugglers2", 18, 2),
        options=(
            ScoutsOption(costs=(PayResources(water=1),)),
            ScoutsOption(costs=(LoseFactionInfluence(Faction.SPACING_GUILD),)),
        ),
    ),
    ScoutsEvent(
        event_id="bene_gesserit_treachery",
        name="Bene Gesserit Treachery",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Treachery2", 18, 3),
        options=(
            ScoutsOption(costs=(LoseGarrisonTroops(1),)),
            ScoutsOption(costs=(LoseFactionInfluence(Faction.BENE_GESSERIT),)),
        ),
    ),
    ScoutsEvent(
        event_id="funeral_rites",
        name="Funeral Rites",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=6,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_FuneralRites", 18, 4),
        options=(
            ScoutsOption(costs=(_TRASH_FROM_HAND,)),
            ScoutsOption(costs=(LoseFactionInfluence(Faction.FREMEN),)),
        ),
    ),
    # --- Covert Operation (family 19): secret picks -----------------------------------
    ScoutsEvent(
        event_id="covert_operation",
        name="Covert Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_CovertOperation2", 19),
        no_choam_only=True,
        secret_choices=(
            SecretChoice(ScoutsOption(rewards=(PlaceSpy(),)), delay=1, grouped=True),
            SecretChoice(ScoutsOption(rewards=(GainResources(solari=2),)), delay=1),
            SecretChoice(
                ScoutsOption(costs=(DiscardFromHand(1),), rewards=(RecruitTroops(3),)),
                delay=2,
            ),
            SecretChoice(
                ScoutsOption(rewards=(GainLowestInfluence(),)), delay=2, grouped=True
            ),
        ),
    ),
    ScoutsEvent(
        event_id="covert_operation_choam",
        name="Covert Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_CovertOperation3", 19, 1),
        choam_only=True,
        secret_choices=(
            SecretChoice(ScoutsOption(rewards=(PlaceSpy(),)), delay=1, grouped=True),
            SecretChoice(
                ScoutsOption(rewards=(TakeContract(1),)), delay=1, grouped=True
            ),
            SecretChoice(
                ScoutsOption(costs=(DiscardFromHand(1),), rewards=(RecruitTroops(3),)),
                delay=2,
            ),
            SecretChoice(
                ScoutsOption(rewards=(GainLowestInfluence(),)), delay=2, grouped=True
            ),
        ),
    ),
    # --- Automatic and round-long events ----------------------------------------------
    ScoutsEvent(
        event_id="mating_season",
        name="Mating Season",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_MatingSeason", 20),
        automatic=AutomaticEffect.MATING_SEASON,
    ),
    ScoutsEvent(
        event_id="unlikely_allies",
        name="Unlikely Allies",
        kind=EventKind.ROUND_MODIFIER,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_UnlikelyAllies", 21),
        modifier=RoundModifier.IGNORE_INFLUENCE_REQUIREMENTS,
    ),
    ScoutsEvent(
        event_id="clear_the_market",
        name="Clear the Market",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_ClearTheMarket", 22),
        no_choam_only=True,
        automatic=AutomaticEffect.CLEAR_THE_MARKET,
    ),
    ScoutsEvent(
        event_id="clear_the_market_choam",
        name="Clear the Market",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_ClearTheMarket2", 22, 1),
        choam_only=True,
        automatic=AutomaticEffect.CLEAR_THE_MARKET_CONTRACTS,
    ),
    ScoutsEvent(
        event_id="market_opening",
        name="Market Opening",
        kind=EventKind.ROUND_MODIFIER,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_MarketOpening", 23),
        modifier=RoundModifier.SPICE_MUST_FLOW_DISCOUNT,
    ),
    ScoutsEvent(
        event_id="eyes_on_arrakis",
        name="Eyes on Arrakis",
        kind=EventKind.ROUND_MODIFIER,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_EyesOnArrakis", 24),
        modifier=RoundModifier.FACTION_SPACES_ARE_COMBAT,
    ),
    ScoutsEvent(
        event_id="friends_everywhere",
        name="Friends Everywhere",
        kind=EventKind.ROUND_MODIFIER,
        rounds=(5, 7),
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_FriendsEverywhere", 25),
        modifier=RoundModifier.ANY_FACTION_FOUR_BONUS,
    ),
    ScoutsEvent(
        event_id="rebuild_infrastructure",
        name="Rebuild Infrastructure",
        kind=EventKind.SHARED,
        rounds=(7, 7),
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_RebuildInfrastructure", 26),
        # Two seats' spice returns the Shield Wall token, if it was removed.
        options=(ScoutsOption(costs=(PayResources(spice=1),)),),
    ),
    ScoutsEvent(
        event_id="choam_bargain",
        name="CHOAM Bargain",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Event_CHOAMBargain", 27),
        choam_only=True,
        options=(
            ScoutsOption(rewards=(DrawPersonalCards(1),)),
            ScoutsOption(rewards=(TakeContract(1),)),
        ),
    ),
    # --- Uprising+Immortality pool ---------------------------------------------------
    ScoutsEvent(
        event_id="ingratiate",
        name="Ingratiate",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Event_Ingratiate", 8),
        options=(ScoutsOption(costs=(PaySpecimens(1),), rewards=(GainInfluence(),)),),
        passable=True,
    ),
    ScoutsEvent(
        event_id="betrayal",
        name="Betrayal",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Event_Betrayal", 9),
        options=(
            ScoutsOption(
                costs=(LoseFactionInfluence(Faction.BENE_GESSERIT),),
                rewards=(AdvanceTleilaxu(1),),
            ),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="new_innovations",
        name="New Innovations",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Event_NewInnovations", 10),
        options=(
            ScoutsOption(costs=(PayResources(solari=1),), rewards=(Research(),)),
            ScoutsOption(costs=(PayResources(spice=1),), rewards=(Research(),)),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="termination_request",
        name="Termination Request",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Event_TerminationRequest", 11),
        options=(
            ScoutsOption(costs=(_TRASH_FROM_HAND,), rewards=(GenerateSpecimens(1),)),
        ),
        passable=True,
    ),
    ScoutsEvent(
        event_id="offworld_operation",
        name="Offworld Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight_tickets=10,
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Event_OffworldOperation", 12),
        secret_choices=(
            SecretChoice(ScoutsOption(rewards=(GainResources(solari=2),)), delay=1),
            SecretChoice(ScoutsOption(rewards=(GainSpiceWithHelixBonus(),)), delay=1),
            SecretChoice(
                ScoutsOption(rewards=(AdvanceTleilaxu(1),)), delay=2, grouped=True
            ),
            SecretChoice(
                ScoutsOption(rewards=(DrawIntrigueCards(1),)), delay=2, grouped=True
            ),
        ),
    ),
)

EVENTS_BY_ID: Final = {entry.event_id: entry for entry in EVENTS}
