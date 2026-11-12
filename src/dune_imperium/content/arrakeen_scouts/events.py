"""Arrakeen Scouts events [Scouts event: <name>].

``weight`` is the app's baseWeight x subWeight: 1 for a single event, 1/2
for each variant of Spice Gain and Intrigue Bonus (1.0 x 0.5), and 3/5 for
each of the five Uprising variants of the two Influence families (3.0 x
0.2); a draw counts it in tickets (``ScoutsEvent.tickets``, x 10 in the
Uprising pools). Covert Operation and Clear the Market have a CHOAM and a
no-CHOAM variant at 1 each; the CHOAM filter keeps one of them.
Variants share an ``AppDefinition.family``; the schedule draws at most one
event per family. Effects are paraphrased in ``docs/rules/arrakeen-scouts.md``.

The Uprising pools' events come first; the original game's own follow them
(stage P8b), with the weights of its three Influence families: 3/4 for each
Influence Gain variant, 6/5 for Political Equilibrium and 9/20 for each other
Influence Reduction variant (baseWeight 3 x subWeight 0.25, 0.4 and 0.15; a
draw counts them in twentieths, ``EVENT_TICKET_SCALE``).
"""

from fractions import Fraction
from typing import Final

from dune_imperium.content.arrakeen_scouts.abilities import (
    scouts_option,
    scouts_options,
    scouts_passable,
)
from dune_imperium.content.arrakeen_scouts.types import (
    IMMORTALITY_POOLS,
    IMPERIUM_POOLS,
    UPRISING_POOLS,
    AppDefinition,
    AutomaticEffect,
    EventKind,
    RoundModifier,
    ScoutsEvent,
    SecretChoice,
)

_ROUNDS: Final = (4, 7)
# The app's baseWeight x subWeight.
_SINGLE: Final = Fraction(1)
_HALF: Final = Fraction(1, 2)
_UPRISING_INFLUENCE: Final = Fraction(3) * Fraction(1, 5)
# The original game's: 3 x 0.25 (Influence Gain), 3 x 0.4 (Political
# Equilibrium) and 3 x 0.15 (the other Influence Reductions).
_IMPERIUM_GAIN: Final = Fraction(3) * Fraction(1, 4)
_IMPERIUM_EQUILIBRIUM: Final = Fraction(3) * Fraction(2, 5)
_IMPERIUM_REDUCTION: Final = Fraction(3) * Fraction(3, 20)


EVENTS: Final[tuple[ScoutsEvent, ...]] = (
    # --- Spice Gain (family 13) -----------------------------------------------------
    ScoutsEvent(
        event_id="private_stock",
        name="Private Stock",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_HALF,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_SpiceGain_PrivateStock", 13),
        options=scouts_options("private_stock"),
        passable=scouts_passable("private_stock"),
    ),
    ScoutsEvent(
        event_id="market_research",
        name="Market Research",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_HALF,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_SpiceGain_MarketResearch", 13, 1),
        options=scouts_options("market_research"),
        passable=scouts_passable("market_research"),
    ),
    # --- Intrigue Bonus (family 14) -------------------------------------------------
    ScoutsEvent(
        event_id="smoke_and_mirrors",
        name="Smoke and Mirrors",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_HALF,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_IntrigueBonus_SmokeAndMirrors", 14),
        options=scouts_options("smoke_and_mirrors"),
        passable=scouts_passable("smoke_and_mirrors"),
    ),
    ScoutsEvent(
        event_id="rotating_doors",
        name="Rotating Doors",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_HALF,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_IntrigueBonus_RotatingDoors2", 14, 1),
        options=scouts_options("rotating_doors"),
        passable=scouts_passable("rotating_doors"),
    ),
    # --- Single-event families ------------------------------------------------------
    ScoutsEvent(
        event_id="moment_of_revelation",
        name="Moment of Revelation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_MomentOfRevelation", 15),
        options=scouts_options("moment_of_revelation"),
        passable=scouts_passable("moment_of_revelation"),
    ),
    ScoutsEvent(
        event_id="water_discipline",
        name="Water Discipline",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_WaterDiscipline", 16),
        options=scouts_options("water_discipline"),
        passable=scouts_passable("water_discipline"),
    ),
    # --- Influence Gain (family 17) -------------------------------------------------
    ScoutsEvent(
        event_id="royal_delegation",
        name="Royal Delegation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_RoyalDelegation", 17),
        options=scouts_options("royal_delegation"),
        passable=scouts_passable("royal_delegation"),
    ),
    ScoutsEvent(
        event_id="guild_negotiation",
        name="Guild Negotiation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_Negotiation2", 17, 1),
        options=scouts_options("guild_negotiation"),
        passable=scouts_passable("guild_negotiation"),
    ),
    ScoutsEvent(
        event_id="covert_assistance",
        name="Covert Assistance",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_CovertAssistance", 17, 2),
        options=scouts_options("covert_assistance"),
        passable=scouts_passable("covert_assistance"),
    ),
    ScoutsEvent(
        event_id="gift_of_water",
        name="Gift of Water",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_GiftOfWater", 17, 3),
        options=scouts_options("gift_of_water"),
        passable=scouts_passable("gift_of_water"),
    ),
    ScoutsEvent(
        event_id="share_intelligence",
        name="Share Intelligence",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_ShareIntelligence", 17, 4),
        options=scouts_options("share_intelligence"),
        passable=scouts_passable("share_intelligence"),
    ),
    # --- Influence Reduction (family 18) ----------------------------------------------
    ScoutsEvent(
        event_id="political_equilibrium",
        name="Political Equilibrium",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Equilibrium2", 18),
        automatic=AutomaticEffect.POLITICAL_EQUILIBRIUM,
    ),
    ScoutsEvent(
        event_id="crackdown",
        name="Crackdown",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Crackdown", 18, 1),
        options=scouts_options("crackdown"),
        passable=scouts_passable("crackdown"),
    ),
    ScoutsEvent(
        event_id="water_for_spice_smugglers",
        name="Water for Spice Smugglers",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Smugglers2", 18, 2),
        options=scouts_options("water_for_spice_smugglers"),
        passable=scouts_passable("water_for_spice_smugglers"),
    ),
    ScoutsEvent(
        event_id="bene_gesserit_treachery",
        name="Bene Gesserit Treachery",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Treachery2", 18, 3),
        options=scouts_options("bene_gesserit_treachery"),
        passable=scouts_passable("bene_gesserit_treachery"),
    ),
    ScoutsEvent(
        event_id="funeral_rites",
        name="Funeral Rites",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_UPRISING_INFLUENCE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_FuneralRites", 18, 4),
        options=scouts_options("funeral_rites"),
        passable=scouts_passable("funeral_rites"),
    ),
    # --- Covert Operation (family 19): secret picks -----------------------------------
    ScoutsEvent(
        event_id="covert_operation",
        name="Covert Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_CovertOperation2", 19),
        no_choam_only=True,
        secret_choices=(
            SecretChoice(scouts_option("covert_operation", 0), delay=1, grouped=True),
            SecretChoice(scouts_option("covert_operation", 1), delay=1),
            SecretChoice(
                scouts_option("covert_operation", 2),
                delay=2,
            ),
            SecretChoice(
                scouts_option("covert_operation", 3), delay=2, grouped=True
            ),
        ),
    ),
    ScoutsEvent(
        event_id="covert_operation_choam",
        name="Covert Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_CovertOperation3", 19, 1),
        choam_only=True,
        secret_choices=(
            SecretChoice(
                scouts_option("covert_operation_choam", 0), delay=1, grouped=True
            ),
            SecretChoice(
                scouts_option("covert_operation_choam", 1), delay=1, grouped=True
            ),
            SecretChoice(
                scouts_option("covert_operation_choam", 2),
                delay=2,
            ),
            SecretChoice(
                scouts_option("covert_operation_choam", 3), delay=2, grouped=True
            ),
        ),
    ),
    # --- Automatic and round-long events ----------------------------------------------
    ScoutsEvent(
        event_id="mating_season",
        name="Mating Season",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_MatingSeason", 20),
        automatic=AutomaticEffect.MATING_SEASON,
    ),
    ScoutsEvent(
        event_id="unlikely_allies",
        name="Unlikely Allies",
        kind=EventKind.ROUND_MODIFIER,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_UnlikelyAllies", 21),
        modifier=RoundModifier.IGNORE_INFLUENCE_REQUIREMENTS,
    ),
    ScoutsEvent(
        event_id="clear_the_market",
        name="Clear the Market",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_ClearTheMarket", 22),
        no_choam_only=True,
        automatic=AutomaticEffect.CLEAR_THE_MARKET,
    ),
    ScoutsEvent(
        event_id="clear_the_market_choam",
        name="Clear the Market",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_ClearTheMarket2", 22, 1),
        choam_only=True,
        automatic=AutomaticEffect.CLEAR_THE_MARKET_CONTRACTS,
    ),
    ScoutsEvent(
        event_id="market_opening",
        name="Market Opening",
        kind=EventKind.ROUND_MODIFIER,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_MarketOpening", 23),
        modifier=RoundModifier.SPICE_MUST_FLOW_DISCOUNT,
    ),
    ScoutsEvent(
        event_id="eyes_on_arrakis",
        name="Eyes on Arrakis",
        kind=EventKind.ROUND_MODIFIER,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_EyesOnArrakis", 24),
        modifier=RoundModifier.FACTION_SPACES_ARE_COMBAT,
    ),
    ScoutsEvent(
        event_id="friends_everywhere",
        name="Friends Everywhere",
        kind=EventKind.ROUND_MODIFIER,
        rounds=(5, 7),
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_FriendsEverywhere", 25),
        modifier=RoundModifier.ANY_FACTION_FOUR_BONUS,
    ),
    ScoutsEvent(
        event_id="rebuild_infrastructure",
        name="Rebuild Infrastructure",
        kind=EventKind.SHARED,
        rounds=(7, 7),
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_RebuildInfrastructure", 26),
        # Two seats' spice returns the Shield Wall token, if it was removed.
        options=scouts_options("rebuild_infrastructure"),
    ),
    ScoutsEvent(
        event_id="choam_bargain",
        name="CHOAM Bargain",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Event_CHOAMBargain", 27),
        choam_only=True,
        options=scouts_options("choam_bargain"),
        passable=scouts_passable("choam_bargain"),
    ),
    # --- The Immortality pools (Uprising and the original game) ---------------------
    ScoutsEvent(
        event_id="ingratiate",
        name="Ingratiate",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Event_Ingratiate", 8),
        options=scouts_options("ingratiate"),
        passable=scouts_passable("ingratiate"),
    ),
    ScoutsEvent(
        event_id="betrayal",
        name="Betrayal",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Event_Betrayal", 9),
        options=scouts_options("betrayal"),
        passable=scouts_passable("betrayal"),
    ),
    ScoutsEvent(
        event_id="new_innovations",
        name="New Innovations",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Event_NewInnovations", 10),
        options=scouts_options("new_innovations"),
        passable=scouts_passable("new_innovations"),
    ),
    ScoutsEvent(
        event_id="termination_request",
        name="Termination Request",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Event_TerminationRequest", 11),
        options=scouts_options("termination_request"),
        passable=scouts_passable("termination_request"),
    ),
    ScoutsEvent(
        event_id="offworld_operation",
        name="Offworld Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Event_OffworldOperation", 12),
        secret_choices=(
            SecretChoice(scouts_option("offworld_operation", 0), delay=1),
            SecretChoice(scouts_option("offworld_operation", 1), delay=1),
            SecretChoice(
                scouts_option("offworld_operation", 2), delay=2, grouped=True
            ),
            SecretChoice(
                scouts_option("offworld_operation", 3), delay=2, grouped=True
            ),
        ),
    ),
    # --- The original game's own events (stage P8b) -----------------------------------
    # Spice Gain (family 0) and Intrigue Bonus (family 1).
    ScoutsEvent(
        event_id="assassination",
        name="Assassination",
        kind=EventKind.CHOICE,
        rounds=(6, 7),
        weight=_HALF,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_SpiceGain_Assassination", 0, 1),
        options=scouts_options("assassination"),
        passable=scouts_passable("assassination"),
    ),
    ScoutsEvent(
        event_id="imperium_secrets_for_sale",
        name="Secrets for Sale",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_HALF,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_IntrigueBonus_Secrets", 1),
        options=scouts_options("imperium_secrets_for_sale"),
        passable=scouts_passable("imperium_secrets_for_sale"),
    ),
    # Single events (families 2 and 5).
    ScoutsEvent(
        event_id="change_of_plans",
        name="Change of Plans",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_ChangeOfPlans", 2),
        options=scouts_options("change_of_plans"),
        passable=scouts_passable("change_of_plans"),
    ),
    ScoutsEvent(
        event_id="imperium_gift_of_water",
        name="Gift of Water",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_GiftOfWater", 5),
        options=scouts_options("imperium_gift_of_water"),
        passable=scouts_passable("imperium_gift_of_water"),
    ),
    # Influence Gain (family 6).
    ScoutsEvent(
        event_id="test_of_loyalty",
        name="Test of Loyalty",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_IMPERIUM_GAIN,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_Loyalty", 6),
        options=scouts_options("test_of_loyalty"),
        passable=scouts_passable("test_of_loyalty"),
    ),
    ScoutsEvent(
        event_id="imperium_guild_negotiation",
        name="Guild Negotiation",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_IMPERIUM_GAIN,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_Negotiation", 6, 1),
        options=scouts_options("imperium_guild_negotiation"),
        passable=scouts_passable("imperium_guild_negotiation"),
    ),
    # Influence Reduction (family 7), from round 5.
    ScoutsEvent(
        event_id="imperium_political_equilibrium",
        name="Political Equilibrium",
        kind=EventKind.AUTOMATIC,
        rounds=(5, 7),
        weight=_IMPERIUM_EQUILIBRIUM,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Equilibrium", 7),
        automatic=AutomaticEffect.POLITICAL_EQUILIBRIUM,
    ),
    ScoutsEvent(
        event_id="emperors_tax",
        name="The Emperor's Tax",
        kind=EventKind.CHOICE,
        rounds=(5, 7),
        weight=_IMPERIUM_REDUCTION,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Tax", 7, 1),
        options=scouts_options("emperors_tax"),
        passable=scouts_passable("emperors_tax"),
    ),
    ScoutsEvent(
        event_id="imperium_water_for_spice_smugglers",
        name="Water for Spice Smugglers",
        kind=EventKind.CHOICE,
        rounds=(5, 7),
        weight=_IMPERIUM_REDUCTION,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Smugglers", 7, 2),
        options=scouts_options("imperium_water_for_spice_smugglers"),
        passable=scouts_passable("imperium_water_for_spice_smugglers"),
    ),
    ScoutsEvent(
        event_id="imperium_bene_gesserit_treachery",
        name="Bene Gesserit Treachery",
        kind=EventKind.CHOICE,
        rounds=(5, 7),
        weight=_IMPERIUM_REDUCTION,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Treachery", 7, 3),
        options=scouts_options("imperium_bene_gesserit_treachery"),
        passable=scouts_passable("imperium_bene_gesserit_treachery"),
    ),
    # Stage P8c: the troop lost from where its seat picks (OQ-163).
    ScoutsEvent(
        event_id="fremen_exchange",
        name="Fremen Exchange",
        kind=EventKind.CHOICE,
        rounds=(5, 7),
        weight=_IMPERIUM_REDUCTION,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceReduction_Exchange", 7, 4),
        options=scouts_options("fremen_exchange"),
        passable=scouts_passable("fremen_exchange"),
    ),
    # Stage P8c: the original game's own Covert Operation (family 4), secret
    # picks of which two name their Faction when picked (9a). Its return beat
    # (``Def_Event_CovertOperation_Return``) is no pool item, as the Uprising
    # ones' are not.
    ScoutsEvent(
        event_id="imperium_covert_operation",
        name="Covert Operation",
        kind=EventKind.SECRET,
        rounds=_ROUNDS,
        weight=_SINGLE,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_CovertOperation", 4),
        secret_choices=(
            SecretChoice(scouts_option("imperium_covert_operation", 0), delay=1),
            SecretChoice(
                scouts_option("imperium_covert_operation", 1),
                delay=1,
                names_faction=True,
            ),
            SecretChoice(scouts_option("imperium_covert_operation", 2), delay=2),
            SecretChoice(
                scouts_option("imperium_covert_operation", 3),
                delay=2,
                names_faction=True,
            ),
        ),
    ),
    # Stage P8c, the last of the original game's events (9a): Tap into Spice
    # Reserves (Spice Gain, family 0), Rotating Doors (Intrigue Bonus, family
    # 1), No Coming Back (a family of its own, round 4 only) and the two
    # Influence Gain variants that discard (family 6, variants 2 and 3).
    ScoutsEvent(
        event_id="tap_into_spice_reserves",
        name="Tap into Spice Reserves",
        kind=EventKind.AUTOMATIC,
        rounds=_ROUNDS,
        weight=_HALF,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_SpiceGain_Reserves", 0),
        automatic=AutomaticEffect.TAP_INTO_SPICE_RESERVES,
    ),
    ScoutsEvent(
        event_id="no_coming_back",
        name="No Coming Back",
        kind=EventKind.CHOICE,
        rounds=(4, 4),
        weight=_SINGLE,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_NoComingBack", 3),
        options=scouts_options("no_coming_back"),
        passable=scouts_passable("no_coming_back"),
    ),
    ScoutsEvent(
        event_id="imperium_rotating_doors",
        name="Rotating Doors",
        kind=EventKind.CHOICE,
        rounds=(6, 7),
        weight=_HALF,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_IntrigueBonus_RotatingDoors", 1, 1),
        options=scouts_options("imperium_rotating_doors"),
        passable=scouts_passable("imperium_rotating_doors"),
    ),
    ScoutsEvent(
        event_id="intriguing_gift",
        name="Intriguing Gift",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_IMPERIUM_GAIN,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_IntriguingGift", 6, 2),
        options=scouts_options("intriguing_gift"),
        passable=scouts_passable("intriguing_gift"),
    ),
    ScoutsEvent(
        event_id="desert_gift",
        name="Desert Gift",
        kind=EventKind.CHOICE,
        rounds=_ROUNDS,
        weight=_IMPERIUM_GAIN,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Event_InfluenceGain_DesertGift", 6, 3),
        options=scouts_options("desert_gift"),
        passable=scouts_passable("desert_gift"),
    ),
)

EVENTS_BY_ID: Final = {entry.event_id: entry for entry in EVENTS}
