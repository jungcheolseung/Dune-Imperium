"""Our content ids <-> app archetypes, and entity construction.

Every lookup the AI makes goes from one of our ids (card instance id, space
id, conflict id, contract id, leader id, post id, faction id) to the app
archetype whose attributes and abilities the app AI would read. The tables
are explicit (no fuzzy matching at runtime) and tests check that every id our
4-player Uprising content can deal maps to an archetype that is dealt in the
app's game with the same CHOAM setting, and that the Immortality, Epic Game
Mode and promo content maps to the app's archetypes of the same cards
(``ARCHETYPES`` holds every archetype the app defines).

Content the app does not have (Bloodlines with its Tech Module and the promo Ruthless
Leadership, Arrakeen Scouts) gets synthetic archetypes built by the app-data rules of
``docs/app-ai-plan.md`` §11.3 (``data/synthetic.py``, a generated file; short names
``<Kind>Archetypes.<Name>``). The same tables map our ids to them; ``archetype`` looks a
short name up in the app's data first, then in the synthetic set. New entity kinds: Tech
tiles (``tech_entity``), the Sardaukar Commander and its Skills (``commander_entity``,
``skill_entity``), Navigation cards (``navigation_entity``) and Scouts lines
(``scouts_line_entity``).

Board overlays (``space_entity``; all off without their option, so games
without Bloodlines or Scouts keep the app's archetypes as they are):
- ``Board.bloodlines``: ``AS.AcquireCommanderAbility`` on the six Commander
  spaces (bloodlines-systems.md §6);
- ``Board.tech_module``: the Rise of Ix ``AcquireTechAbility`` on the five
  Landsraad spaces (§6, the Ixian Embassy);
- ``Board.scouts``: ``MissionPiecesSpaceAbility`` on every space, the
  ``SubcommitteeOfferAbility`` on High Council, ``DesertRidingAbility`` in
  place of Hagga Basin's deferred ability (scouts.md §4.1, §4.2, §4.5, §4.8);
- ``Board.faction_spaces_combat`` (Eyes on Arrakis this round): the five
  Faction spaces that are not Combat spaces become Combat spaces with the
  app's ``DeployUnitsAbility`` (scouts.md §4.7).

Tuek's Sietch (Esmar Tuek's own space) has a synthetic archetype but stays out
of ``SPACE_ARCHETYPES``, which the profile reads as "every space of the
board": ``BLOODLINES_SPACE_ARCHETYPES`` holds it, ``space_entity`` resolves it,
and ``BLOODLINES_SPACE_ORDER`` is its place after the app's spaces.

Known content differences (``scratchpad R5`` / ``spec/archetypes.md``):
- The app's reserve holds Foldspace x6; our engine has no Foldspace.
- Our three Uprising promos and Piter, Genius Advisor are ``Promo``
  archetypes the app never deals; app_ai values them with those archetypes.
- Accept Contract, Dutiful Service, CHOAM Security and Trade Dispute have an
  ``...UP`` archetype (no CHOAM) and a ``...CHOAM`` one; pick by ``choam``.
"""

from functools import cache, lru_cache
from types import MappingProxyType
from typing import Final

from dune_imperium.agents.app_ai.context import Board, card_id
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.data.synthetic import SCOUTS_LINES, SYNTHETIC
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.config import BaseGame
from dune_imperium.content.bloodlines.sardaukar import commander_setup_space_ids
from dune_imperium.content.rulesets import UPRISING_IX_OVERLAID_SPACE_IDS


def _both(short: str) -> tuple[str, str]:
    """An archetype that is the same with and without the CHOAM module."""

    return (short, short)


# -- the original Dune: Imperium (``BaseGame.IMPERIUM``) ----------------------
#
# The app's archetypes of our original content (base set and base-game promos); merged
# into the tables below (no id collides with an Uprising one). The starting deck is the
# original one both games share.

# Reserve stacks, the 43 Imperium kinds and the three promos
# (``content.imperium.imperium.IMPERIUM_BASE_CARDS``).
ORIGINAL_CARD_ARCHETYPES: dict[str, str] = {
    "arrakis_liaison": "imperium.original.arrakis_liaison",
    "imperium_the_spice_must_flow": "imperium.original.the_spice_must_flow",
    "foldspace_card": "imperium.original.foldspace_imperium",
    "arrakis_recruiter": "imperium.original.arrakis_recruiter",
    "spice_smugglers": "imperium.original.spice_smugglers",
    "gun_thopter": "imperium.original.gun_thopter",
    "assassination_mission": "imperium.original.assassination_mission",
    "bene_gesserit_initiate": "imperium.original.bene_gesserit_initiate",
    "bene_gesserit_sister": "imperium.original.bene_gesserit_sister",
    "choam_directorship": "imperium.original.choam_directorship",
    "carryall": "imperium.original.carryall",
    "chani_card": "imperium.original.chani",
    "crysknife_card": "imperium.original.crysknife",
    "dr_yueh": "imperium.original.dr_yueh",
    "duncan_idaho_card": "imperium.original.duncan_idaho",
    "fedaykin_death_commando": "imperium.original.fedaykin_death_commando",
    "firm_grip": "imperium.original.firm_grip",
    "fremen_camp": "imperium.original.fremen_camp",
    "gene_manipulation": "imperium.original.gene_manipulation",
    "guild_administrator": "imperium.original.guild_administrator",
    "guild_ambassador": "imperium.original.guild_ambassador",
    "guild_bankers": "imperium.original.guild_bankers",
    "gurney_halleck_card": "imperium.original.gurney_halleck",
    "imperial_spy": "imperium.original.imperial_spy",
    "kwisatz_haderach": "imperium.original.kwisatz_haderach",
    "lady_jessica_card": "imperium.original.lady_jessica",
    "liet_kynes_card": "imperium.original.liet_kynes",
    "missionaria_protectiva": "imperium.original.missionaria_protectiva",
    "opulence": "imperium.original.opulence",
    "other_memory": "imperium.original.other_memory",
    "piter_de_vries_card": "imperium.original.piter_de_vries",
    "power_play": "imperium.original.power_play",
    "reverend_mother_mohiam": "imperium.original.reverend_mother_mohiam",
    "sardaukar_infantry": "imperium.original.sardaukar_infantry",
    "sardaukar_legion": "imperium.original.sardaukar_legion",
    "scout": "imperium.original.scout",
    "shifting_allegiances": "imperium.original.shifting_allegiances",
    "sietch_reverend_mother": "imperium.original.sietch_reverend_mother",
    "smugglers_thopter": "imperium.original.smugglers_thopter",
    "space_travel": "imperium.original.space_travel",
    "spice_hunter": "imperium.original.spice_hunter",
    "stilgar": "imperium.original.stilgar",
    "test_of_humanity": "imperium.original.test_of_humanity",
    "the_voice": "imperium.original.the_voice",
    "thufir_hawat": "imperium.original.thufir_hawat",
    "worm_riders": "imperium.original.worm_riders",
    "duncan_loyal_blade": "imperium.promo.duncan_loyal_blade",
    "jessica_of_arrakis": "imperium.promo.jessica_of_arrakis",
    "thumper": "imperium.promo.thumper",
}
# ``content.imperium.intrigue.IMPERIUM_INTRIGUE_CARDS``.
ORIGINAL_INTRIGUE_ARCHETYPES: dict[str, str] = {
    "bribery": "intrigue.original.bribery",
    "master_tactician": "intrigue.original.master_tactician",
    "allied_armada": "intrigue.original.allied_armada",
    "ambush": "intrigue.original.ambush",
    "bindu_suspension": "intrigue.original.bindu_suspension",
    "bypass_protocol": "intrigue.original.bypass_protocol",
    "choam_shares": "intrigue.original.choam_shares",
    "calculated_hire": "intrigue.original.calculated_hire",
    "charisma": "intrigue.original.charisma",
    "corner_the_market": "intrigue.original.corner_the_market",
    "councilors_dispensation": "intrigue.original.councilors_dispensation",
    "demand_respect": "intrigue.original.demand_respect",
    "dispatch_an_envoy": "intrigue.original.dispatchan_envoy",
    "double_cross": "intrigue.original.double_cross",
    "favored_subject": "intrigue.original.favored_subject",
    "guild_authorization": "intrigue.original.guild_authorization",
    "infiltrate": "intrigue.original.infiltrate",
    "know_their_ways": "intrigue.original.know_their_ways",
    "plans_within_plans": "intrigue.original.plans_within_plans",
    "poison_snooper": "intrigue.original.poison_snooper",
    "private_army": "intrigue.original.private_army",
    "rapid_mobilization": "intrigue.original.rapid_mobilization",
    "recruitment_mission": "intrigue.original.recruitment_mission",
    "refocus": "intrigue.original.refocus",
    "reinforcements": "intrigue.original.reinforcements",
    "secret_of_the_sisterhood": "intrigue.original.secretof_the_sisterhood",
    "staged_incident": "intrigue.original.staged_incident",
    "the_sleeper_must_awaken": "intrigue.original.the_sleeper_must_awaken",
    "tiebreaker": "intrigue.original.tiebreaker",
    "to_the_victor": "intrigue.original.to_the_victor",
    "urgent_mission": "intrigue.original.urgent_mission",
    "water_peddlers_union": "intrigue.original.water_peddlers_union",
    "water_of_life": "intrigue.original.water_of_life",
    "windfall": "intrigue.original.windfall",
}
# ``content.imperium.conflicts`` (no CHOAM variant).
ORIGINAL_CONFLICT_ARCHETYPES: dict[str, tuple[str, str]] = {
    "skirmish_a": _both("conflict.original.skirmish_a"),
    "skirmish_b": _both("conflict.original.skirmish_b"),
    "skirmish_c": _both("conflict.original.skirmish_c"),
    "skirmish_d": _both("conflict.original.skirmish_d"),
    "cloak_and_dagger": _both("conflict.original.cloakand_dagger"),
    "desert_power_conflict": _both("conflict.original.desert_power"),
    "guild_bank_raid": _both("conflict.original.guild_bank_raid"),
    "machinations": _both("conflict.original.machinations"),
    "raid_stockpiles": _both("conflict.original.raid_stockpiles"),
    "imperium_secure_imperial_basin": _both(
        "conflict.original.secure_imperial_basin"
    ),
    "imperium_siege_of_arrakeen": _both("conflict.original.siege_of_arrakeen"),
    "siege_of_carthag": _both("conflict.original.siege_of_carthag"),
    "sort_through_the_chaos": _both("conflict.original.sort_through_the_chaos"),
    "terrible_purpose": _both("conflict.original.terrible_purpose"),
    "imperium_battle_for_arrakeen": _both(
        "conflict.original.battle_for_arrakeen"
    ),
    "battle_for_carthag": _both("conflict.original.battle_for_carthag"),
    "imperium_battle_for_imperial_basin": _both(
        "conflict.original.battle_for_imperial_basin"
    ),
    "grand_vision": _both("conflict.original.grand_vision"),
}
# ``content.imperium.leaders``.
ORIGINAL_LEADER_ARCHETYPES: dict[str, str] = {
    "paul_atreides": "leader.original.paul_atreides",
    "duke_leto_atreides": "leader.original.duke_leto_atreides",
    "glossu_rabban": "leader.original.glossu_the_beast_rabban",
    "baron_vladimir_harkonnen": "leader.original.baron_vladimir_harkonnen",
    "count_ilban_richese": "leader.original.count_ilban_richese",
    "helena_richese": "leader.original.helena_richese",
    "earl_memnon_thorvald": "leader.original.earl_memnon_thorvald",
    "countess_ariana_thorvald": "leader.original.countess_ariana_thorvald",
}


# -- Rise of Ix on the original board (``rise_of_ix``, docs/app-ai-plan.md §13) ------
#
# The app's ``RiseOfIx`` (and Ix ``Promo``) archetypes of our Ix content
# (``content.rise_of_ix``); merged into the tables below (no id collides).

# ``content.rise_of_ix.imperium.IX_IMPERIUM_CARDS``.
IX_CARD_ARCHETYPES: dict[str, str] = {
    "appropriate": "imperium.ix.appropriate",
    "bounty_hunter": "imperium.ix.bounty_hunter",
    "choam_delegate": "imperium.ix.choam_delegate",
    "court_intrigue": "imperium.ix.court_intrigue",
    "desert_ambush": "imperium.ix.desert_ambush",
    "embedded_agent": "imperium.ix.embedded_agent",
    "esmar_tuek_card": "imperium.ix.esmar_tuek",
    "freighter_fleet": "imperium.ix.freighter_fleet",
    "full_scale_assault": "imperium.ix.full_scale_assault",
    "guild_accord": "imperium.ix.guild_accord",
    "guild_chief_administrator": "imperium.ix.guild_chief_administrator",
    "imperial_bashar": "imperium.ix.imperial_bashar",
    "imperial_shock_trooper": "imperium.ix.imperial_shock_trooper",
    "in_the_shadows": "imperium.ix.in_the_shadows",
    "ix_guild_compact": "imperium.ix.ix_guild_compact",
    "ixian_engineer": "imperium.ix.ixian_engineer",
    "jamis": "imperium.ix.jamis",
    "landing_rights": "imperium.ix.landing_rights",
    "local_fence": "imperium.ix.local_fence",
    "negotiated_withdrawal": "imperium.ix.negotiated_withdrawal",
    "satellite_ban": "imperium.ix.satellite_ban",
    "sayyadina": "imperium.ix.sayyadina",
    "shai_hulud": "imperium.ix.shai_hulud",
    "spice_trader": "imperium.ix.spice_trader",
    "treachery": "imperium.ix.treachery",
    "truthsayer": "imperium.ix.truthsayer",
    "water_peddler": "imperium.ix.water_peddler",
    "web_of_power": "imperium.ix.web_of_power",
    "weirding_way": "imperium.ix.weirding_way",
    "boundless_ambition": "imperium.promo.boundless_ambition",
}
# ``content.rise_of_ix.intrigue``.
IX_INTRIGUE_ARCHETYPES: dict[str, str] = {
    "advanced_weaponry": "intrigue.ix.advanced_weaponry",
    "blackmail": "intrigue.ix.blackmail",
    "cannon_turrets": "intrigue.ix.cannon_turrets",
    "cull": "intrigue.ix.cull",
    "diversion": "intrigue.ix.diversion",
    "expedite": "intrigue.ix.expedite",
    "finesse": "intrigue.ix.finesse",
    "glimpse_the_path": "intrigue.ix.glimpse_the_path",
    "grand_conspiracy": "intrigue.ix.grand_conspiracy",
    "ixian_probe": "intrigue.ix.ixian_probe",
    "machine_culture": "intrigue.ix.machine_culture",
    "quid_pro_quo": "intrigue.ix.quid_pro_quo",
    "second_wave": "intrigue.ix.second_wave",
    "secret_forces": "intrigue.ix.secret_forces",
    "strategic_push": "intrigue.ix.strategic_push",
    "strongarm": "intrigue.ix.strongarm",
    "war_chest": "intrigue.ix.war_chest",
}
# ``content.rise_of_ix.conflicts`` (Economic Supremacy is in the Epic table).
IX_CONFLICT_ARCHETYPES: dict[str, tuple[str, str]] = {
    "skirmish_e": _both("conflict.ix.skirmish_e"),
    "skirmish_f": _both("conflict.ix.skirmish_f"),
    "trade_monopoly": _both("conflict.ix.trade_monopoly"),
}
# ``content.rise_of_ix.leaders``.
IX_LEADER_ARCHETYPES: dict[str, str] = {
    "archduke_armand_ecaz": "leader.ix.archduke_armand_ecaz",
    "ilesa_ecaz": "leader.ix.ilesa_ecaz",
    "prince_rhombur_vernius": "leader.ix.prince_rhombur_vernius",
    "princess_yuna_moritani": "leader.ix.princess_yuna_moritani",
    "tessia_vernius": "leader.ix.tessia_vernius",
    "viscount_hundro_moritani": "leader.ix.viscount_hundro_moritani",
}
# ``content.rise_of_ix.tech``: the app's own tiles (the Bloodlines ones are
# app-style, ``TECH_ARCHETYPES`` above them).
IX_TECH_ARCHETYPES: dict[str, str] = {
    "artillery": "tech_tile.ix.artillery",
    "chaumurky": "tech_tile.ix.chaumurky",
    "detonation_devices": "tech_tile.ix.detonation_devices",
    "disposal_facility": "tech_tile.ix.disposal_facility",
    "flagship": "tech_tile.ix.flagship",
    "holoprojectors": "tech_tile.ix.holoprojectors",
    "holtzman_engine": "tech_tile.ix.holtzman_engine",
    "invasion_ships": "tech_tile.ix.invasion_ships",
    "memocorders": "tech_tile.ix.memocorders",
    "minimic_film": "tech_tile.ix.minimic_film",
    "restricted_ordnance": "tech_tile.ix.restricted_ordnance",
    "shuttle_fleet": "tech_tile.ix.shuttle_fleet",
    "sonic_snoopers": "tech_tile.ix.sonic_snoopers",
    "spaceport": "tech_tile.ix.spaceport",
    "spy_satellites": "tech_tile.ix.spy_satellites",
    "training_drones": "tech_tile.ix.training_drones",
    "troop_transports": "tech_tile.ix.troop_transports",
    "windtraps": "tech_tile.ix.windtraps",
}

# card_id -> app archetype short name (starters, reserve, Imperium incl. CHOAM
# and promos).
CARD_ARCHETYPES: dict[str, str] = {
    # Starting deck (the original starters).
    "convincing_argument": "imperium.original.convincing_argument",
    "dagger": "imperium.original.dagger",
    "diplomacy": "imperium.original.diplomacy",
    "dune_the_desert_planet": "imperium.original.dune_the_desert_planet",
    "reconnaissance": "imperium.original.reconnaissance",
    "seek_allies": "imperium.original.seek_allies",
    "signet_ring": "imperium.original.signet_ring",
    # Reserve stacks.
    "prepare_the_way": "imperium.uprising.prepare_the_way",
    "the_spice_must_flow": "imperium.uprising.the_spice_must_flow_up",
    # Imperium deck: base cards and the four CHOAM-only cards.
    "bene_gesserit_operative": "imperium.uprising.bene_gesserit_operative",
    "branching_path": "imperium.uprising.branching_path",
    "calculus_of_power": "imperium.uprising.calculus_of_power",
    "captured_mentat": "imperium.uprising.captured_mentat",
    "cargo_runner": "imperium.uprising.cargo_runner",
    "chani_clever_tactician": "imperium.uprising.chani_clever_tactician",
    "corrinth_city": "imperium.uprising.corrinth_city",
    "covert_operation": "imperium.uprising.covert_operation",
    "dangerous_rhetoric": "imperium.uprising.dangerous_rhetoric",
    "delivery_agreement": "imperium.uprising.delivery_agreement",
    "desert_power": "imperium.uprising.desert_power_imperium",
    "desert_survival": "imperium.uprising.desert_survival",
    "double_agent": "imperium.uprising.double_agent",
    "ecological_testing_station": (
        "imperium.uprising.ecological_testing_station"
    ),
    "fedaykin_stilltent": "imperium.uprising.fedaykin_stilltent",
    "guild_envoy": "imperium.uprising.guild_envoy",
    "guild_spy": "imperium.uprising.guild_spy",
    "hidden_missive": "imperium.uprising.hidden_missive",
    "imperial_spymaster": "imperium.uprising.imperial_spymaster",
    "in_high_places": "imperium.uprising.in_high_places",
    "interstellar_trade": "imperium.uprising.interstellar_trade",
    "junction_headquarters": "imperium.uprising.junction_headquarters",
    "leadership": "imperium.uprising.leadership",
    "long_live_the_fighters": "imperium.uprising.long_live_the_fighters",
    "maker_keeper": "imperium.uprising.maker_keeper",
    "maula_pistol": "imperium.uprising.maula_pistol",
    "northern_watermaster": "imperium.uprising.northern_watermaster",
    "overthrow": "imperium.uprising.overthrow",
    "paracompass": "imperium.uprising.paracompass",
    "price_is_no_object": "imperium.uprising.price_is_no_object",
    "priority_contracts": "imperium.uprising.priority_contracts",
    "public_spectacle": "imperium.uprising.public_spectacle",
    "rebel_supplier": "imperium.uprising.rebel_supplier",
    "reliable_informant": "imperium.uprising.reliable_informant",
    "sardaukar_coordination": "imperium.uprising.sardaukar_coordination",
    "sardaukar_soldier": "imperium.uprising.sardaukar_soldier",
    "shishakli": "imperium.uprising.shishakli",
    "smuggler_s_harvester": "imperium.uprising.smugglers_harvester",
    "smuggler_s_haven": "imperium.uprising.smugglers_haven",
    "southern_elders": "imperium.uprising.southern_elders",
    "space_time_folding": "imperium.uprising.spacetime_folding",
    "spacing_guild_s_favor": "imperium.uprising.spacing_guilds_favor",
    "spy_network": "imperium.uprising.spy_network",
    "steersman": "imperium.uprising.steersman",
    "stilgar_the_devoted": "imperium.uprising.stilgar_the_devoted",
    "strike_fleet": "imperium.uprising.strike_fleet",
    "subversive_advisor": "imperium.uprising.subversive_advisor",
    "treacherous_maneuver": "imperium.uprising.treacherous_maneuver",
    "tread_in_darkness": "imperium.uprising.treadin_darkness",
    "truthtrance": "imperium.uprising.truthtrance",
    "undercover_asset": "imperium.uprising.undercover_asset",
    "unswerving_loyalty": "imperium.uprising.unswerving_loyalty",
    "weirding_woman": "imperium.uprising.weirding_woman",
    "wheels_within_wheels": "imperium.uprising.wheels_within_wheels",
    # Uprising promos. The app deals none of them (``ImperiumType = Promo``);
    # they map to the app's own archetypes of the same cards.
    "arrakis_revolt": "imperium.promo.arrakis_revolt",
    "pivotal_gambit": "imperium.promo.pivotal_gambit",
    "the_beast_s_spoils": "imperium.promo.the_beasts_spoils",
    # Immortality: the starter that replaces Dune, the Desert Planet, and the
    # 25 Imperium kinds (``imperium_cards_for_choam(..., immortality=True)``).
    "experimentation": "imperium.immortality.experimentation",
    "bene_tleilax_lab": "imperium.immortality.bene_tleilax_lab",
    "bene_tleilax_researcher": "imperium.immortality.bene_tleilax_researcher",
    "blank_slate": "imperium.immortality.blank_slate",
    "clandestine_meeting": "imperium.immortality.clandestine_meeting",
    "corrupt_smuggler": "imperium.immortality.corrupt_smuggler",
    "dissecting_kit": "imperium.immortality.dissecting_kit",
    "for_humanity": "imperium.immortality.for_humanity",
    "high_priority_travel": "imperium.immortality.high_priority_travel",
    "imperium_ceremony": "imperium.immortality.imperium_ceremony",
    "interstellar_conspiracy": "imperium.immortality.interstellar_conspiracy",
    "keys_to_power": "imperium.immortality.keys_to_power",
    "lisan_al_gaib": "imperium.immortality.lisanal_gaib",
    "long_reach": "imperium.immortality.long_reach",
    "occupation": "imperium.immortality.occupation",
    "organ_merchants": "imperium.immortality.organ_merchants",
    "planned_coupling": "imperium.immortality.planned_coupling",
    "replacement_eyes": "imperium.immortality.replacement_eyes",
    "sardaukar_quartermaster": "imperium.immortality.sardaukar_quartermaster",
    "shadout_mapes": "imperium.immortality.shadout_mapes",
    "show_of_strength": "imperium.immortality.show_of_strength",
    "spiritual_fervor": "imperium.immortality.spiritual_fervor",
    "stillsuit_manufacturer": "imperium.immortality.stillsuit_manufacturer",
    "throne_room_politics": "imperium.immortality.throne_room_politics",
    "tleilaxu_master": "imperium.immortality.tleilaxu_master",
    "tleilaxu_surgeon": "imperium.immortality.tleilaxu_surgeon",
    # Immortality Tleilaxu cards (instance ids ``tleilaxu:<id>:<n>``): the 18
    # deck cards, the fixed Reclaimed Forces slot and the promo Piter.
    "beguiling_pheromones": "tleilaxu.immortality.beguiling_pheromones",
    "chairdog": "tleilaxu.immortality.chairdog",
    "contaminator": "tleilaxu.immortality.contaminator",
    "corrino_genes": "tleilaxu.immortality.corrino_genes",
    "face_dancer": "tleilaxu.immortality.face_dancer",
    "face_dancer_initiate": "tleilaxu.immortality.face_dancer_initiate",
    "from_the_tanks": "tleilaxu.immortality.from_the_tanks",
    "ghola": "tleilaxu.immortality.ghola",
    "guild_impersonator": "tleilaxu.immortality.guild_impersonator",
    "industrial_espionage": "tleilaxu.immortality.industrial_espionage",
    "scientific_breakthrough": "tleilaxu.immortality.scientific_breakthrough",
    "slig_farmer": "tleilaxu.immortality.slig_farmer",
    "stitched_horror": "tleilaxu.immortality.stitched_horror",
    "subject_x_137": "tleilaxu.immortality.subject_x137",
    "tleilaxu_infiltrator": "tleilaxu.immortality.tleilaxu_infiltrator",
    "twisted_mentat": "tleilaxu.immortality.twisted_mentat",
    "unnatural_reflexes": "tleilaxu.immortality.unnatural_reflexes",
    "usurp": "tleilaxu.immortality.usurp",
    "reclaimed_forces": "tleilaxu.immortality.reclaimed_forces",
    "piter_genius_advisor": "tleilaxu.promo.piter_genius_advisor",
    # Epic Game Mode starter (the app's ``Decks.EpicStarterDeck``).
    "control_the_spice": "imperium.ix.control_the_spice",
    # Bloodlines (app-style, bloodlines-cards.md §3): the 25 retail cards, the
    # CHOAM-only and Tech-only cards, and the promo Ruthless Leadership.
    "ruthless_leadership": "imperium.app_style.ruthless_leadership",
    "arrakis_observer": "imperium.app_style.arrakis_observer",
    "bombast": "imperium.app_style.bombast",
    "choam_demands": "imperium.app_style.choam_demands",
    "command_center": "imperium.app_style.command_center",
    "corrupt_bureaucrat": "imperium.app_style.corrupt_bureaucrat",
    "delivery_logistics": "imperium.app_style.delivery_logistics",
    "disruption_tactics": "imperium.app_style.disruption_tactics",
    "eliminate_allies": "imperium.app_style.eliminate_allies",
    "elite_forces": "imperium.app_style.elite_forces",
    "engineered_miracle": "imperium.app_style.engineered_miracle",
    "fremen_war_name": "imperium.app_style.fremen_war_name",
    "holy_war": "imperium.app_style.holy_war",
    "i_believe": "imperium.app_style.i_believe",
    "imperial_throneship": "imperium.app_style.imperial_throneship",
    "intelligence_training": "imperium.app_style.intelligence_training",
    "ixian_ambassador": "imperium.app_style.ixian_ambassador",
    "litany_against_fear": "imperium.app_style.litany_against_fear",
    "mercantile_affairs": "imperium.app_style.mercantile_affairs",
    "pointing_the_way": "imperium.app_style.pointing_the_way",
    "possible_futures": "imperium.app_style.possible_futures",
    "quash_rebellion": "imperium.app_style.quash_rebellion",
    "sandwalk": "imperium.app_style.sandwalk",
    "sardaukar_standard": "imperium.app_style.sardaukar_standard",
    "shrouded_counsel": "imperium.app_style.shrouded_counsel",
    "southern_faith": "imperium.app_style.southern_faith",
    "urgent_shigawire": "imperium.app_style.urgent_shigawire",
    # The original game.
    **ORIGINAL_CARD_ARCHETYPES,
    **IX_CARD_ARCHETYPES,
}
# intrigue card_id -> app archetype short name.
INTRIGUE_ARCHETYPES: dict[str, str] = {
    "backed_by_choam": "intrigue.uprising.backed_by_choam",
    "buy_access": "intrigue.uprising.buy_access",
    "call_to_arms": "intrigue.uprising.call_to_arms",
    "change_allegiances": "intrigue.uprising.change_allegiances",
    "choam_profits": "intrigue.uprising.choam_profits",
    "contingency_plan": "intrigue.uprising.contingency_plan",
    "councilor_s_ambition": "intrigue.uprising.councilors_ambition",
    "crysknife": "intrigue.uprising.crysknife_intrigue",
    "cunning": "intrigue.uprising.cunning",
    "depart_for_arrakis": "intrigue.uprising.depart_for_arrakis",
    "desert_mouse": "intrigue.uprising.desert_mouse",
    "detonation": "intrigue.uprising.detonation",
    "devour": "intrigue.uprising.devour",
    "distraction": "intrigue.uprising.distraction",
    "find_weakness": "intrigue.uprising.find_weakness",
    "go_to_ground": "intrigue.uprising.go_to_ground",
    "imperium_politics": "intrigue.uprising.imperium_politics",
    "impress": "intrigue.uprising.impress",
    "inspire_awe": "intrigue.uprising.inspire_awe",
    "intelligence_report": "intrigue.uprising.intelligence_report",
    "leverage": "intrigue.uprising.leverage",
    "manipulate": "intrigue.uprising.manipulate_intrigue",
    "market_opportunity": "intrigue.uprising.market_opportunity",
    "mercenaries": "intrigue.uprising.mercenaries",
    "opportunism": "intrigue.uprising.opportunism",
    "ornithopter": "intrigue.uprising.ornithopter",
    "questionable_methods": "intrigue.uprising.questionable_methods",
    "reach_agreement": "intrigue.uprising.reach_agreement",
    "secure_spice_trade": "intrigue.uprising.secure_spice_trade",
    "shaddam_s_favor": "intrigue.uprising.shaddams_favor",
    "shadow_alliance": "intrigue.uprising.shadow_alliance",
    "sietch_ritual": "intrigue.uprising.sietch_ritual",
    "special_mission": "intrigue.uprising.special_mission",
    "spice_is_power": "intrigue.uprising.spice_is_power",
    "spring_the_trap": "intrigue.uprising.spring_the_trap",
    "strategic_stockpiling": "intrigue.uprising.strategic_stockpiling",
    "tactical_option": "intrigue.uprising.tactical_option",
    "unexpected_allies": "intrigue.uprising.unexpected_allies",
    "weirding_combat": "intrigue.uprising.weirding_combat",
    # Immortality (``intrigue_cards_for_choam(..., immortality=True)``).
    "breakthrough": "intrigue.immortality.breakthrough",
    "counterattack": "intrigue.immortality.counterattack",
    "disguised_bureaucrat": "intrigue.immortality.disguised_bureaucrat",
    "economic_positioning": "intrigue.immortality.economic_positioning",
    "gruesome_sacrifice": "intrigue.immortality.gruesome_sacrifice",
    "harvest_cells": "intrigue.immortality.harvest_cells",
    "illicit_dealings": "intrigue.immortality.illicit_dealings",
    "shadowy_bargain": "intrigue.immortality.shadowy_bargain",
    "study_melange": "intrigue.immortality.study_melange",
    "tleilaxu_puppet": "intrigue.immortality.tleilaxu_puppet",
    "vicious_talents": "intrigue.immortality.vicious_talents",
    # Bloodlines (app-style, bloodlines-cards.md §4), CHOAM-only and
    # Tech-only cards included.
    "adaptive_tactics": "intrigue.app_style.adaptive_tactics",
    "battlefield_research": "intrigue.app_style.battlefield_research",
    "coercive_negotiation": "intrigue.app_style.coercive_negotiation",
    "desert_support": "intrigue.app_style.desert_support",
    "emperor_s_invitation": "intrigue.app_style.emperors_invitation",
    "false_orders": "intrigue.app_style.false_orders",
    "grasp_arrakis": "intrigue.app_style.grasp_arrakis",
    "honor_guard": "intrigue.app_style.honor_guard",
    "insider_information": "intrigue.app_style.insider_information",
    "rapid_engineering": "intrigue.app_style.rapid_engineering",
    "return_the_favor": "intrigue.app_style.return_the_favor",
    "ripples_in_the_sand": "intrigue.app_style.ripplesin_the_sand",
    "sacred_pools": "intrigue.app_style.sacred_pools",
    "seize_production": "intrigue.app_style.seize_production",
    "sleeper_unit": "intrigue.app_style.sleeper_unit",
    "tenuous_bond": "intrigue.app_style.tenuous_bond",
    "the_strong_survive": "intrigue.app_style.the_strong_survive",
    "withdrawal_agreement": "intrigue.app_style.withdrawal_agreement",
    # Piter De Vries' Twisted Intrigue (bloodlines-cards.md §5): ordinary
    # Intrigue cards once held (instance ids ``intrigue:twisted_<id>:0``).
    "twisted_ambitious": "intrigue.app_style.twisted_ambitious",
    "twisted_calculating": "intrigue.app_style.twisted_calculating",
    "twisted_controlled": "intrigue.app_style.twisted_controlled",
    "twisted_devious": "intrigue.app_style.twisted_devious",
    "twisted_discerning": "intrigue.app_style.twisted_discerning",
    "twisted_insidious": "intrigue.app_style.twisted_insidious",
    "twisted_resourceful": "intrigue.app_style.twisted_resourceful",
    "twisted_sadistic": "intrigue.app_style.twisted_sadistic",
    "twisted_shrewd": "intrigue.app_style.twisted_shrewd",
    "twisted_sinister": "intrigue.app_style.twisted_sinister",
    "twisted_unnatural": "intrigue.app_style.twisted_unnatural",
    "twisted_withdrawn": "intrigue.app_style.twisted_withdrawn",
    # The original game.
    **ORIGINAL_INTRIGUE_ARCHETYPES,
    **IX_INTRIGUE_ARCHETYPES,
}
# Navigation card_id -> archetype (Steersman Y'rkoon's ten cards; not Intrigue
# cards, bloodlines-systems.md §5; instance ids ``intrigue:navigation_card_<n>:0``).
NAVIGATION_ARCHETYPES: dict[str, str] = {
    f"navigation_card_{n}": f"navigation.app_style.navigation_card{n}"
    for n in range(1, 11)
}
# space_id -> (archetype without CHOAM, archetype with CHOAM).
SPACE_ARCHETYPES: dict[str, tuple[str, str]] = {
    "dutiful_service": (
        "space.uprising.dutiful_service_up",
        "space.uprising.dutiful_service_choam",
    ),
    "sardaukar": _both("space.uprising.sardaukar"),
    "deliver_supplies": _both("space.uprising.deliver_supplies"),
    "heighliner": _both("space.uprising.heighliner_up"),
    "espionage": _both("space.uprising.espionage"),
    "secrets": _both("space.original.secrets"),
    "desert_tactics": _both("space.uprising.desert_tactics"),
    "fremkit": _both("space.uprising.fremkit"),
    "assembly_hall": _both("space.uprising.assembly_hall"),
    "gather_support": _both("space.uprising.gather_support"),
    "high_council": _both("space.uprising.high_council_up"),
    "imperial_privilege": _both("space.uprising.imperial_privilege"),
    "swordmaster": _both("space.uprising.swordmaster_up"),
    "arrakeen": _both("space.original.arrakeen"),
    "research_station": _both("space.uprising.research_station_up"),
    "sietch_tabr": _both("space.uprising.sietch_tabr_up"),
    "spice_refinery": _both("space.uprising.spice_refinery"),
    "accept_contract": (
        "space.uprising.accept_contract_up",
        "space.uprising.accept_contract_choam",
    ),
    "deep_desert": _both("space.uprising.deep_desert"),
    "hagga_basin": _both("space.uprising.hagga_basin_up"),
    "imperial_basin": _both("space.original.imperial_basin"),
    "shipping": _both("space.uprising.shipping"),
}
# space_id -> the archetype that replaces it when Immortality is on (spec
# immortality.md §1.1: ``ResearchStationUP`` has ``RemovedFromSetList =
# [Immortality]``).
IMMORTALITY_SPACE_ARCHETYPES: dict[str, str] = {
    "research_station": "space.immortality.research_station_immortality",
}
# The same replacement on the original board (P7b): ``ResearchStation`` has
# ``RemovedFromSetList = [Immortality]`` too, and our engine keeps the original space's
# id for the Immortality space that stands there.
ORIGINAL_IMMORTALITY_SPACE_ARCHETYPES: dict[str, str] = {
    "imperium_research_station": IMMORTALITY_SPACE_ARCHETYPES["research_station"],
}
# The original Dune: Imperium board (``Board.original``): space_id -> the app's
# original-board archetype, in our board order. Secrets, Arrakeen and Imperial Basin are
# the archetypes the Uprising board shares; the other ids that name an Uprising space
# too carry ``imperium_``. No CHOAM variant: the original game takes no CHOAM module yet
# (``rules.setup``).
ORIGINAL_SPACE_ARCHETYPES: dict[str, str] = {
    "conspire": "space.original.conspire",
    "wealth": "space.original.wealth",
    "imperium_heighliner": "space.original.heighliner",
    "foldspace": "space.original.foldspace_space",
    "selective_breeding": "space.original.selective_breeding",
    "secrets": "space.original.secrets",
    "hardy_warriors": "space.original.hardy_warriors",
    "stillsuits": "space.original.stillsuits",
    "hall_of_oratory": "space.original.hall_of_oratory",
    "rally_troops": "space.original.rally_troops",
    "mentat": "space.original.mentat",
    "imperium_swordmaster": "space.original.swordmaster",
    "imperium_high_council": "space.original.high_council",
    "arrakeen": "space.original.arrakeen",
    "carthag": "space.original.carthag",
    "imperium_research_station": "space.original.research_station",
    "imperium_sietch_tabr": "space.original.sietch_tabr",
    "imperial_basin": "space.original.imperial_basin",
    "imperium_hagga_basin": "space.original.hagga_basin",
    "the_great_flat": "space.original.the_great_flat",
    "secure_contract": "space.original.secure_contract",
    "sell_melange": "space.original.sell_melange",
}
#: Rise of Ix's four spaces (``content.rise_of_ix.board.IX_SPACE_IDS``) and the
#: four original spaces its CHOAM overlay covers (their ``RemovedFromSetList``
#: holds ``RiseOfIx``).
IX_SPACE_ARCHETYPES: dict[str, str] = {
    "dreadnought": "space.ix.dreadnought_space",
    "tech_negotiation": "space.ix.tech_negotiation",
    "interstellar_shipping": "space.ix.interstellar_shipping",
    "smuggling": "space.ix.smuggling",
}
IX_COVERED_SPACE_IDS: Final = frozenset(
    {"hall_of_oratory", "rally_troops", "secure_contract", "sell_melange"}
)
# Bloodlines spaces with no app archetype (bloodlines-systems.md §6). Kept out
# of ``SPACE_ARCHETYPES``: Tuek's Sietch is on the board only while Esmar Tuek
# plays (``BoardSpace.required_leader_id``), and the profile reads
# ``SPACE_ARCHETYPES`` as every space of every game.
BLOODLINES_SPACE_ARCHETYPES: dict[str, str] = {
    "tuek_sietch": "space.app_style.tueks_sietch",
}
#: Where a Bloodlines space goes in the app's space order: after every app
#: space. ``BeginSetup`` appends each further enabled set's spaces after the
#: board set's (``windows/turn.board_space_order``), and a synthetic archetype
#: comes after every app type (spec silent on the order; app-style choice).
BLOODLINES_SPACE_ORDER: tuple[str, ...] = ("tuek_sietch",)


def board_space_ids(board: Board) -> tuple[str, ...]:
    """Every board space of this game, in catalog order (``BoardSpaces``).

    The app's spaces, then Tuek's Sietch when Esmar Tuek is in the game
    (``Board.tueks_sietch``, plan §11.8); the original board's spaces on
    ``Board.original``.
    """

    tuek = BLOODLINES_SPACE_ORDER if board.tueks_sietch else ()
    if board.original and board.ix:
        return (
            *(s for s in ORIGINAL_SPACE_ARCHETYPES if s not in IX_COVERED_SPACE_IDS),
            *IX_SPACE_ARCHETYPES,
            *tuek,
        )
    if board.original:
        return (*ORIGINAL_SPACE_ARCHETYPES, *tuek)
    if board.ix:
        # Rise of Ix on the Uprising board (P7f): the half overlay covers
        # Assembly Hall, Gather Support, Shipping and Accept Contract, the
        # four Ix spaces come after (``rulesets.UPRISING_IX_OVERLAID_SPACE_IDS``,
        # the app's ``RemovedFromSetList`` of RiseOfIx).
        return (
            *(s for s in SPACE_ARCHETYPES if s not in UPRISING_IX_OVERLAID_SPACE_IDS),
            *IX_SPACE_ARCHETYPES,
            *tuek,
        )
    return (*SPACE_ARCHETYPES, *tuek)


#: ``ArchetypeExtensions.Is…Space`` ( Swordmaster
#: High Council Research Station Heighliner; the
#: ``EntityExtensions`` overloads read the same archetype ids): the space
#: archetypes each app predicate accepts, of every board.
SWORDMASTER_SPACE_ARCHETYPES: Final = frozenset(
    {"space.original.swordmaster", "space.uprising.swordmaster_up"}
)
HIGH_COUNCIL_SPACE_ARCHETYPES: Final = frozenset(
    {"space.original.high_council", "space.uprising.high_council_up"}
)
HEIGHLINER_SPACE_ARCHETYPES: Final = frozenset(
    {"space.original.heighliner", "space.uprising.heighliner_up"}
)


@cache
def board_space_where(board: Board, archetypes: frozenset[str]) -> str | None:
    """``BoardSpaces.FirstOrDefault(pred)``: our id of this board's first
    space whose archetype ``archetypes`` holds (None: the board has none)."""

    for space_id in board_space_ids(board):
        if space_archetype(space_id, board) in archetypes:
            return space_id
    return None


def board_space_of(board: Board, archetypes: frozenset[str]) -> str:
    """``board_space_where`` for a space every board has."""

    space_id = board_space_where(board, archetypes)
    if space_id is None:
        raise KeyError(f"no space of {sorted(archetypes)} on {board}")
    return space_id


def swordmaster_space_id(board: Board) -> str:
    """Our id of the Swordmaster space (``IsSwordmasterSpace``)."""

    return board_space_of(board, SWORDMASTER_SPACE_ARCHETYPES)


def high_council_space_id(board: Board) -> str:
    """Our id of the High Council space (``IsHighCouncilSpace``)."""

    return board_space_of(board, HIGH_COUNCIL_SPACE_ARCHETYPES)


def heighliner_space_id(board: Board) -> str:
    """Our id of the Heighliner space (``IsHeighlinerSpace``)."""

    return board_space_of(board, HEIGHLINER_SPACE_ARCHETYPES)


def is_high_council_space(space: Entity) -> bool:
    """``IsHighCouncilSpace`` of a space entity."""

    return space.short in HIGH_COUNCIL_SPACE_ARCHETYPES


def is_board_space(space_id: str) -> bool:
    """Whether ``space_id`` names a board space of any game (app or Bloodlines)."""

    return (
        space_id in SPACE_ARCHETYPES
        or space_id in ORIGINAL_SPACE_ARCHETYPES
        or space_id in IX_SPACE_ARCHETYPES
        or space_id in BLOODLINES_SPACE_ARCHETYPES
    )


# -- board overlays (see the module docstring) ------------------------------------

_AS_BLOODLINES = "ability.app_style.bloodlines."
_AS_SCOUTS = "ability.app_style.scouts."
#: bloodlines-systems.md §6: the six spaces a Sardaukar Commander is set on
#: (``content/bloodlines/sardaukar.py`` ``COMMANDER_SETUP_SPACE_IDS``).
COMMANDER_SPACES: tuple[str, ...] = (
    "sardaukar",
    "dutiful_service",
    "deliver_supplies",
    "high_council",
    "gather_support",
    "assembly_hall",
)
ACQUIRE_COMMANDER_ABILITY: Final = _AS_BLOODLINES + "acquire_commander"


def commander_spaces(board: Board) -> tuple[str, ...]:
    """The spaces a Sardaukar Commander is set on in this game: Uprising's
    six (``COMMANDER_SPACES``), the original board's (P7c,
    ``ORIGINAL_COMMANDER_SETUP_SPACE_IDS`` [Bloodlines p. 3]), and with Rise
    of Ix the two its overlay covers moved to Dreadnought and Tech
    Negotiation [Bloodlines p. 7] -- the engine's
    ``commander_setup_space_ids``."""

    return commander_setup_space_ids(
        BaseGame.IMPERIUM if board.original else BaseGame.UPRISING,
        rise_of_ix=board.ix,
    )


#: bloodlines-systems.md §6: the Ixian Embassy's Acquire Tech on a Landsraad
#: visit (the five Landsraad-icon spaces).
TECH_SPACES: tuple[str, ...] = (
    "high_council",
    "imperial_privilege",
    "swordmaster",
    "assembly_hall",
    "gather_support",
)
#: The original board's five Landsraad-icon spaces, where the Ixian Embassy
#: opens the same Acquire Tech (P7c, docs/rules/bloodlines.md section 5).
ORIGINAL_TECH_SPACES: tuple[str, ...] = (
    "hall_of_oratory",
    "rally_troops",
    "mentat",
    "imperium_swordmaster",
    "imperium_high_council",
)


def tech_spaces(board: Board) -> tuple[str, ...]:
    """The spaces whose visit offers the Ixian Embassy's Acquire Tech: none
    with Rise of Ix, whose Ix board replaces the Embassy [Bloodlines p. 7]
    (the engine's ``ixian_embassy_in_play``)."""

    if not board.tech_module or board.ix:
        return ()
    return ORIGINAL_TECH_SPACES if board.original else TECH_SPACES


ACQUIRE_TECH_ABILITY: Final = (
    "ability.activated.ix.acquire_tech"
)
#: scouts.md §4.1, §4.5, §4.2.
MISSION_PIECES_ABILITY: Final = _AS_SCOUTS + "mission_pieces_space"
SUBCOMMITTEE_OFFER_ABILITY: Final = _AS_SCOUTS + "subcommittee_offer"
#: The High Council of either board (the original game's, stage P8): a new
#: seat there opens the subcommittee offer.
SUBCOMMITTEE_SPACES: tuple[str, ...] = ("high_council", "imperium_high_council")
HAGGA_BASIN_DEFERRED: Final = (
    "ability.space.uprising.hagga_basin_uprising_deferred"
)
DESERT_RIDING_ABILITY: Final = _AS_SCOUTS + "desert_riding"
#: scouts.md §4.7 (Eyes on Arrakis): the Faction spaces that are not Combat
#: spaces (``rules/scouts_modifiers.py`` ``space_is_combat``).
EYES_ON_ARRAKIS_SPACES: tuple[str, ...] = (
    "dutiful_service",
    "sardaukar",
    "deliver_supplies",
    "espionage",
    "secrets",
)
DEPLOY_UNITS_ABILITY: Final = (
    "ability.activated.deploy_units"
)
# conflict card_id -> (archetype without CHOAM, archetype with CHOAM).
CONFLICT_ARCHETYPES: dict[str, tuple[str, str]] = {
    "skirmish_crysknife": _both("conflict.uprising.skirmish_h"),
    "skirmish_ornithopter": _both("conflict.uprising.skirmish_g"),
    "skirmish_desert_mouse": _both("conflict.uprising.skirmish_i"),
    "choam_security": (
        "conflict.uprising.choam_security_up",
        "conflict.uprising.choam_security_choam",
    ),
    "spice_freighters": _both("conflict.uprising.spice_freighters_up"),
    "siege_of_arrakeen": _both("conflict.uprising.siege_of_arrakeen_up"),
    "seize_spice_refinery": _both("conflict.uprising.seize_spice_refinery_up"),
    "test_of_loyalty": _both("conflict.uprising.test_of_loyalty_up"),
    "shadow_contest": _both("conflict.uprising.shadow_contest_up"),
    "secure_imperial_basin": _both("conflict.uprising.secure_imperial_basin_up"),
    "protect_the_sietches": _both("conflict.uprising.protect_the_sietches_up"),
    "trade_dispute": (
        "conflict.uprising.trade_dispute_up",
        "conflict.uprising.trade_dispute_choam",
    ),
    "propaganda": _both("conflict.uprising.propaganda_up"),
    "battle_for_imperial_basin": _both(
        "conflict.uprising.battle_for_imperial_basin_up"
    ),
    "battle_for_arrakeen": _both("conflict.uprising.battle_for_arrakeen_up"),
    "battle_for_spice_refinery": _both(
        "conflict.uprising.battle_for_spice_refinery_up"
    ),
    # Epic Game Mode's Conflict III (the app's Rise of Ix card).
    "economic_supremacy": _both("conflict.ix.economic_supremacy"),
    # Bloodlines' Conflict I and II (app-style, bloodlines-cards.md §6).
    "skirmish_wild": _both("conflict.app_style.skirmish_wild"),
    "storms_in_the_south": _both("conflict.app_style.stormsin_the_south"),
    # The original game.
    **ORIGINAL_CONFLICT_ARCHETYPES,
    **IX_CONFLICT_ARCHETYPES,
}
# contract card_id -> app archetype short name.
CONTRACT_ARCHETYPES: dict[str, str] = {
    "acquire": "contract.uprising.contract_base_20",
    "arrakeen_i": "contract.uprising.contract_base_5",
    "arrakeen_ii": "contract.uprising.contract_base_4",
    "deliver_supplies": "contract.uprising.contract_base_14",
    "espionage_i": "contract.uprising.contract_base_17",
    "espionage_i_copy_2": "contract.uprising.contract_base_17",
    "harvest_3": "contract.uprising.contract_base_1",
    "harvest_3_copy_2": "contract.uprising.contract_base_1",
    "harvest_4": "contract.uprising.contract_base_3",
    "spice_refinery_i": "contract.uprising.contract_base_6",
    "heighliner_i": "contract.uprising.contract_base_16",
    "heighliner_ii": "contract.uprising.contract_base_15",
    "spice_refinery_ii": "contract.uprising.contract_base_7",
    "high_council_i": "contract.uprising.contract_base_10",
    "high_council_ii": "contract.uprising.contract_base_11",
    "immediate": "contract.uprising.contract_base_19",
    "research_station_i": "contract.uprising.contract_base_9",
    "research_station_ii": "contract.uprising.contract_base_8",
    "sardaukar_i": "contract.uprising.contract_base_12",
    "sardaukar_ii": "contract.uprising.contract_base_13",
    # Bloodlines' eight tokens (app-style, bloodlines-cards.md §7).
    "bloodlines_deliver_supplies": (
        "contract.app_style.bloodlines_deliver_supplies"
    ),
    "bloodlines_earn_any_alliance": (
        "contract.app_style.bloodlines_earn_any_alliance"
    ),
    "bloodlines_harvest_3": "contract.app_style.bloodlines_harvest3",
    "bloodlines_harvest_4": "contract.app_style.bloodlines_harvest4",
    "bloodlines_high_council": "contract.app_style.bloodlines_high_council",
    "bloodlines_immediate": "contract.app_style.bloodlines_immediate",
    "bloodlines_secrets": "contract.app_style.bloodlines_secrets",
    "bloodlines_spice_refinery": "contract.app_style.bloodlines_spice_refinery",
    # Rise of Ix's ten, with the CHOAM module on the Uprising board (P7f-2,
    # [Main p. 16]): the app's ``ContractRoI_n`` (``SetList`` Uprising +
    # RiseOfIx), matched by the space and reward each one names.
    "ix_smuggling": "contract.uprising.contract_ro_i_1",
    "ix_harvest_3": "contract.uprising.contract_ro_i_2",
    "ix_interstellar_shipping": "contract.uprising.contract_ro_i_3",
    "ix_harvest_4": "contract.uprising.contract_ro_i_4",
    "ix_tech_negotiation": "contract.uprising.contract_ro_i_5",
    "ix_dreadnought": "contract.uprising.contract_ro_i_6",
    "ix_high_council": "contract.uprising.contract_ro_i_7",
    "ix_heighliner": "contract.uprising.contract_ro_i_8",
    "ix_secrets": "contract.uprising.contract_ro_i_9",
    "ix_espionage": "contract.uprising.contract_ro_i_10",
}
# leader_id -> app archetype short name (incl. Lady Jessica's flipped face).
LEADER_ARCHETYPES: dict[str, str] = {
    "feyd_rautha_harkonnen": "leader.uprising.feyd_rautha_harkonnen",
    "gurney_halleck": "leader.uprising.gurney_halleck_leader",
    "lady_amber_metulli": "leader.uprising.lady_amber_metulli",
    "lady_jessica": "leader.uprising.lady_jessica_leader",
    "lady_margot_fenring": "leader.uprising.lady_margot_fenring",
    "muad_dib": "leader.uprising.muad_dib",
    "princess_irulan": "leader.uprising.princess_irulan",
    "staban_tuek": "leader.uprising.staban_tuek",
    "shaddam_corrino_iv": "leader.uprising.shaddam_corrino_iv",
    # Lady Jessica's flipped face (``PublicPlayerView.leader_face_id``).
    "reverend_mother_jessica": "leader.uprising.reverend_mother_jessica",
    # Bloodlines leaders (app-style, bloodlines-systems.md §4; none has a
    # second face).
    "chani": "leader.app_style.chani_leader",
    "count_hasimir_fenring": "leader.app_style.count_hasimir_fenring",
    "duncan_idaho": "leader.app_style.duncan_idaho_leader",
    "esmar_tuek": "leader.app_style.esmar_tuek_leader",
    "gaius_helen_mohiam": "leader.app_style.gaius_helen_mohiam",
    "piter_de_vries": "leader.app_style.piter_de_vries_leader",
    "steersman_y_rkoon": "leader.app_style.steersman_yrkoon_leader",
    "liet_kynes": "leader.app_style.liet_kynes_leader",
    "kota_odax_of_ix": "leader.app_style.kota_odax_of_ix",
    # The original game.
    **ORIGINAL_LEADER_ARCHETYPES,
    **IX_LEADER_ARCHETYPES,
}
# tech_id -> Tech tile archetype (app-style, bloodlines-systems.md §3.2).
TECH_ARCHETYPES: dict[str, str] = {
    "advanced_data_analysis": "tech_tile.app_style.advanced_data_analysis",
    "choam_transports": "tech_tile.app_style.choam_transports",
    "delivery_bay": "tech_tile.app_style.delivery_bay",
    "forbidden_weapons": "tech_tile.app_style.forbidden_weapons",
    "gene_locked_vault": "tech_tile.app_style.gene_locked_vault",
    "glowglobes": "tech_tile.app_style.glowglobes",
    "navigation_chamber": "tech_tile.app_style.navigation_chamber",
    "ornithopter_fleet": "tech_tile.app_style.ornithopter_fleet",
    "panopticon": "tech_tile.app_style.panopticon",
    "planetary_array": "tech_tile.app_style.planetary_array",
    "plasteel_blades": "tech_tile.app_style.plasteel_blades",
    "rapid_dropships": "tech_tile.app_style.rapid_dropships",
    "sardaukar_high_command": "tech_tile.app_style.sardaukar_high_command",
    "self_destroying_messages": "tech_tile.app_style.self_destroying_messages",
    "servo_receivers": "tech_tile.app_style.servo_receivers",
    "spy_drones": "tech_tile.app_style.spy_drones",
    "suspensor_suits": "tech_tile.app_style.suspensor_suits",
    "training_depot": "tech_tile.app_style.training_depot",
    # Rise of Ix: the app's own tiles.
    **IX_TECH_ARCHETYPES,
}
# The Sardaukar Commander and skill_id -> Skill archetype (app-style,
# bloodlines-systems.md §2.1).
COMMANDER_ARCHETYPE: Final = "commander.app_style.sardaukar_commander"
SKILL_ARCHETYPES: dict[str, str] = {
    "canny": "skill.app_style.canny",
    "charismatic": "skill.app_style.charismatic",
    "desperate": "skill.app_style.desperate",
    "driven": "skill.app_style.driven",
    "fierce": "skill.app_style.fierce",
    "hardy": "skill.app_style.hardy",
    "loyal": "skill.app_style.loyal",
}
# "<Scouts item id>:<line index>" -> line archetype (app-style, scouts.md §2.2,
# §5): the generated table. Line index = our option index (the event's
# options, then its secret choices; a sealed auction's place - 1; a mission's
# join line).
SCOUTS_LINE_ARCHETYPES: Final = SCOUTS_LINES
# post_id -> the app's observation post index (1-13).
POST_INDEX: dict[str, int] = {
    "emperor-sardaukar-dutiful-service": 1,
    "spacing-guild-heighliner-deliver-supplies": 2,
    "bene-gesserit-espionage-secrets": 3,
    "fremen-desert-tactics-fremkit": 4,
    "landsraad-high-council-imperial-privilege-swordmaster": 5,
    "landsraad-assembly-hall-gather-support": 6,
    "choam-shipping-accept-contract": 7,
    "arrakis-research-station-sietch-tabr": 8,
    "arrakis-research-station-spice-refinery": 9,
    "arrakis-spice-refinery-arrakeen": 10,
    "arrakis-deep-desert": 11,
    "arrakis-hagga-basin": 12,
    "arrakis-imperial-basin": 13,
    # Rise of Ix on the Uprising board (P7f): the half overlay covers the
    # Assembly Hall - Gather Support and Shipping - Accept Contract posts
    # with their spaces, and its own two take their indices, as the app's
    # Ix archetypes do (Tech Negotiation and Dreadnought 6, Interstellar
    # Shipping and Smuggling 7).
    "landsraad-tech-negotiation-dreadnought": 6,
    "choam-interstellar-shipping-smuggling": 7,
}
# our faction id -> the app's Factions enum name.
FACTION_NAMES: dict[str, str] = {
    "emperor": "Emperor",
    "spacing_guild": "SpacingGuild",
    "bene_gesserit": "BeneGesserit",
    "fremen": "Fremen",
}


def archetype(short: str) -> Archetype:
    """The archetype of a short name: the app's, else the app-style one."""

    found = ARCHETYPES.get(short)
    return SYNTHETIC[short] if found is None else found


_archetype = archetype


_CARD_ENTITY_CACHE_LIMIT: Final = 4096


@lru_cache(maxsize=_CARD_ENTITY_CACHE_LIMIT)
def _static_card_entity(instance_id: str, owner: int | None, short: str) -> Entity:
    """Reuse a static content lookup; no decision-dependent data is stored."""

    return Entity(Kind.CARD, instance_id, _archetype(short), owner)


def card_entity(instance_id: str, owner: int | None = None) -> Entity:
    """A personal card (starter, reserve or Imperium) by instance id."""

    short = CARD_ARCHETYPES[card_id(instance_id)]
    definition = _archetype(short)
    cached = _static_card_entity(instance_id, owner, short)
    if cached.archetype is definition:
        return cached
    # Caller-modified catalogs are read fresh, even if a pure lookup for
    # this name was cached before its definition changed.
    return Entity(Kind.CARD, instance_id, definition, owner)


def intrigue_entity(instance_id: str, owner: int | None = None) -> Entity:
    """An Intrigue card by instance id."""

    return Entity(
        Kind.INTRIGUE,
        instance_id,
        _archetype(INTRIGUE_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def contract_entity(instance_id: str, owner: int | None = None) -> Entity:
    """A CHOAM contract by instance id (``contract:<id>``)."""

    return Entity(
        Kind.CONTRACT,
        instance_id,
        _archetype(CONTRACT_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def space_archetype(space_id: str, board: Board) -> str:
    """The app archetype short name of a board space in this game."""

    if board.ix and space_id in IX_SPACE_ARCHETYPES:
        return IX_SPACE_ARCHETYPES[space_id]
    if board.original:
        if board.immortality and space_id in ORIGINAL_IMMORTALITY_SPACE_ARCHETYPES:
            return ORIGINAL_IMMORTALITY_SPACE_ARCHETYPES[space_id]
        if space_id in BLOODLINES_SPACE_ARCHETYPES:
            return BLOODLINES_SPACE_ARCHETYPES[space_id]
        return ORIGINAL_SPACE_ARCHETYPES[space_id]
    if board.immortality and space_id in IMMORTALITY_SPACE_ARCHETYPES:
        return IMMORTALITY_SPACE_ARCHETYPES[space_id]
    if space_id in BLOODLINES_SPACE_ARCHETYPES:
        return BLOODLINES_SPACE_ARCHETYPES[space_id]
    without, with_choam = SPACE_ARCHETYPES[space_id]
    return with_choam if board.choam else without


def _space_overlay(space_id: str, board: Board) -> tuple[tuple[str, ...], bool]:
    """The ability ids a board option adds to a space, and whether it makes
    the space a Combat space (see the module docstring)."""

    added: list[str] = []
    if board.bloodlines and space_id in commander_spaces(board):
        added.append(ACQUIRE_COMMANDER_ABILITY)
    if space_id in tech_spaces(board):
        added.append(ACQUIRE_TECH_ABILITY)
    if board.scouts:
        if space_id in SUBCOMMITTEE_SPACES:
            added.append(SUBCOMMITTEE_OFFER_ABILITY)
        added.append(MISSION_PIECES_ABILITY)
    combat = board.faction_spaces_combat and space_id in EYES_ON_ARRAKIS_SPACES
    if combat:
        added.append(DEPLOY_UNITS_ABILITY)
    return tuple(added), combat


# A pure function of hashable immutable arguments with an immutable result
# (frozen Archetype, MappingProxyType attributes): ``functools.cache`` is
# thread-safe, and concurrent games at worst compute an equal value twice.
@cache
def _space_archetype(space_id: str, board: Board) -> Archetype:
    """The space's archetype with this game's overlays (the app's own object
    when no option changes it)."""

    base = _archetype(space_archetype(space_id, board))
    added, combat = _space_overlay(space_id, board)
    ids = base.attributes.get("AbilityIDs", ())
    assert isinstance(ids, tuple)
    swap = board.scouts and HAGGA_BASIN_DEFERRED in ids
    if not (added or combat or swap):
        return base
    if swap:
        ids = tuple(
            DESERT_RIDING_ABILITY if i == HAGGA_BASIN_DEFERRED else i for i in ids
        )
    attributes = dict(base.attributes)
    attributes["AbilityIDs"] = (*ids, *added)
    if combat:
        attributes["CombatSpace"] = True
    return Archetype(
        short=base.short,
        kind=base.kind,
        title=base.title,
        in_uprising=base.in_uprising,
        in_uprising_choam=base.in_uprising_choam,
        attributes=MappingProxyType(attributes),
    )


def space_entity(space_id: str, board: Board) -> Entity:
    """A board space (with the board overlays of this game's options)."""

    return Entity(Kind.SPACE, space_id, _space_archetype(space_id, board))


def conflict_entity(conflict_id: str, choam: bool) -> Entity:
    """A Conflict card."""

    without, with_choam = CONFLICT_ARCHETYPES[conflict_id]
    return Entity(
        Kind.CONFLICT, conflict_id, _archetype(with_choam if choam else without)
    )


def conflict_reward_entities(conflict_id: str, choam: bool) -> tuple[Entity, ...]:
    """The 1st/2nd/3rd reward archetypes of a Conflict card, in place order.

    Read from the card archetype's ``ConflictRewardArchetypes``.
    """

    card = conflict_entity(conflict_id, choam)
    return tuple(
        Entity(Kind.CONFLICT, conflict_id, _archetype(short))
        for short in card.list_attr("ConflictRewardArchetypes")
    )


def leader_entity(leader_id: str, face_id: str | None = None) -> Entity:
    """A leader (the flipped face when ``face_id`` names one)."""

    key = face_id if face_id and face_id in LEADER_ARCHETYPES else leader_id
    return Entity(Kind.LEADER, leader_id, _archetype(LEADER_ARCHETYPES[key]))


def post_entity(post_id: str, owner: int | None = None) -> Entity:
    """An observation post (the app's ``ObservationPost``)."""

    return Entity(Kind.POST, post_id, None, owner)


def spy_entity(post_id: str, owner: int) -> Entity:
    """A spy standing on ``post_id``."""

    return Entity(Kind.SPY, post_id, None, owner)


def agent_entity(space_id: str, owner: int) -> Entity:
    """An agent standing on ``space_id``."""

    return Entity(Kind.AGENT, space_id, None, owner)


def track_entity(faction: str) -> Entity:
    """A faction influence track (our faction id)."""

    return Entity(Kind.TRACK, faction, None)


# -- app-style entities (docs/app-ai-plan.md §11.3) --------------------------------


def tech_entity(tech_id: str, owner: int | None = None) -> Entity:
    """A Bloodlines Tech tile by our ``tech_id`` (``Kind.TECH``; the same
    entity ``profile.tech.tech_tile_entity`` builds from the archetype)."""

    return Entity(Kind.TECH, tech_id, _archetype(TECH_ARCHETYPES[tech_id]), owner)


def commander_entity(
    ref: str = "sardaukar_commander", owner: int | None = None
) -> Entity:
    """A Sardaukar Commander. Commanders have no id in our engine; ``ref``
    names where it stands (a space id, ``"bank"``) when that matters."""

    return Entity(Kind.COMMANDER, ref, _archetype(COMMANDER_ARCHETYPE), owner)


def skill_id_of(skill: str) -> str:
    """The skill id of a Skill tile instance id (``skill:<id>:<copy>``) or of
    a bare skill id."""

    return skill.split(":")[1] if skill.startswith("skill:") else skill


def skill_entity(skill: str, owner: int | None = None) -> Entity:
    """A Skill tile, by skill id or tile instance id (the ``ref``)."""

    return Entity(
        Kind.SKILL, skill, _archetype(SKILL_ARCHETYPES[skill_id_of(skill)]), owner
    )


def navigation_entity(instance_id: str, owner: int | None = None) -> Entity:
    """One of Steersman Y'rkoon's Navigation cards (instance id
    ``intrigue:navigation_card_<n>:0``, or the bare card id)."""

    return Entity(
        Kind.NAVIGATION,
        instance_id,
        _archetype(NAVIGATION_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def scouts_line_entity(item_id: str, line: int, owner: int | None = None) -> Entity:
    """One Arrakeen Scouts cost -> reward line (``ref = "<item id>:<line>"``)."""

    ref = f"{item_id}:{line}"
    return Entity(Kind.SCOUTS, ref, _archetype(SCOUTS_LINE_ARCHETYPES[ref]), owner)
