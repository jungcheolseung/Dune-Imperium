"""The original game's Imperium cards and its three promos (stage P3).

docs/base-game-and-ix-plan.md 16: 43 Imperium kinds, 67 cards [DI p. 3], and
the promos Duncan, Loyal Blade, Jessica of Arrakis and Thumper behind
``promo_cards`` (plan 9 8). Per D1 (plan 2.4) every value comes from the
Steam app: the attribute table for cost, copies, Factions, Agent icons and
the printed Reveal values, the card's screen pieces and English text for its
boxes; the rules behind them are docs/rules/imperium-base.md.

A name the original prints like another set's card keeps that card's id;
one printed otherwise takes the ``imperium_`` prefix (plan 4.2 7, 16.2).
Their ability records sit in the same tables as Uprising's
(``agent_abilities``, ``reveal_abilities``, ...).

Every card has an entry from stage P3a on; one not yet transcribed holds
only its identity (name, copies, cost: ``play_data_complete`` False). The
original game's deck takes the transcribed ones (``rulesets``), and the
observation lists them all from v37 (plan 16.1, 16.4).
``content.uprising.imperium.IMPERIUM_CARDS_BY_ID`` resolves them; code that
lists Uprising's own cards iterates ``IMPERIUM_CARDS`` instead.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardTrashEffect,
)

# The rulebook lists the deck [DI p. 3]; the printed values are the app's
# (plan 2.4, D1).
IMPERIUM_SOURCES: Final = (SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3,)),)


def imperium_card(card_id: str, name: str) -> CardDefinition:
    """The identity of an original Imperium card (no Dune Cards Hub URL:
    the original's faces are not read, D1)."""

    return CardDefinition(card_id=card_id, name=name, sources=IMPERIUM_SOURCES)


# Typed: ``content.uprising.imperium`` reads it while both modules load.
IMPERIUM_BASE_CARDS: Final[tuple[ImperiumCardEntry, ...]] = (
    # App table: cost 2, 2 copies, City, Reveal 1 Persuasion and 1 sword.
    # Agent: the troop icon alone; a Combat space lets the owner deploy the
    # recruited troop and up to two from the garrison [DI pp. 10, 17-18]
    # [FAQ p. 4] -- no card text grants it, so the card sets nothing.
    ImperiumCardEntry(
        card=imperium_card("arrakis_recruiter", "Arrakis Recruiter"),
        copies=2,
        acquisition_cost=2,
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.RECRUIT_ONE_TROOP,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # App table: cost 2, 2 copies, Spacing Guild, City, Reveal 1 Persuasion and
    # 1 sword. Agent: "[2 spice] -> [Spacing Guild Influence] [3 Solari]", an
    # optional arrow cost paid once [DI p. 9] [FAQ p. 3].
    ImperiumCardEntry(
        card=imperium_card("spice_smugglers", "Spice Smugglers"),
        copies=2,
        acquisition_cost=2,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=(
            PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_SPACING_GUILD_INFLUENCE_AND_THREE_SOLARI
        ),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # App table: cost 4, 2 copies, City and Spice Trade, Reveal 3 swords (no
    # Persuasion). Agent: "Each opponent loses one garrisoned troop"; Reveal:
    # "You may deploy a troop from your garrison to the Conflict".
    ImperiumCardEntry(
        card=imperium_card("gun_thopter", "Gun Thopter"),
        copies=2,
        acquisition_cost=4,
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.EACH_OPPONENT_LOSES_GARRISON_TROOP,
        reveal_strength=3,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.MAY_DEPLOY_ONE_TROOP,),
        play_data_complete=True,
    ),
    # --- Identities only (stage P3a, plan 16.1): name, copies and cost from the
    # app's attribute table (scripts/dwgr/imperium_entries.py skeleton); each
    # card's play data replaces its entry when it is transcribed. ---
    # App table: cost 1, 2 copies, no Faction, no Agent icons, Reveal 1 sword
    # (Solari 1 beside it). No Agent icon: a Reveal-only card [DI p. 9]. Reveal:
    # "[1 Solari] [S1]". Trashed (banner "When this card is trashed: 4
    # Solari"): whatever trashes it -- the card has no way to trash itself, so
    # another effect must [FAQ p. 1].
    ImperiumCardEntry(
        card=imperium_card("assassination_mission", "Assassination Mission"),
        copies=2,
        acquisition_cost=1,
        agent_icons=(),
        reveal_strength=1,
        trash_effect=PersonalCardTrashEffect.GAIN_FOUR_SOLARI,
        play_data_complete=True,
    ),
    # App table: cost 3, 2 copies, Bene Gesserit, Landsraad, City and Spice
    # Trade, Reveal 1 Persuasion. Agent: "Draw 1 card" (the card-draw icon
    # alone; its own step, OQ-106).
    ImperiumCardEntry(
        card=imperium_card("bene_gesserit_initiate", "Bene Gesserit Initiate"),
        copies=2,
        acquisition_cost=3,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # App table: cost 3, 3 copies, Bene Gesserit, Bene Gesserit and Landsraad,
    # no fixed Reveal values. Agent: no box (the icons only). Reveal: "[2
    # Persuasion] -OR- [2 swords]", a printed -OR- the owner must settle.
    ImperiumCardEntry(
        card=imperium_card("bene_gesserit_sister", "Bene Gesserit Sister"),
        copies=3,
        acquisition_cost=3,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.LANDSRAAD),
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.CHOOSE_TWO_PERSUASION_OR_TWO_STRENGTH,
        ),
        play_data_complete=True,
    ),
    # App table: cost 8, 1 copy, no Faction, no Agent icons, no fixed Reveal
    # values. No Agent box and no icon: Reveal only [DI p. 9]. Acquire: four
    # separate Influence icons, one with each of the four Factions, "once,
    # when acquired" [DI p. 16], each a row in the owner's order (OQ-141, the
    # principle of OQ-027 and OQ-112); a track at 6 gains nothing (OQ-060).
    # Reveal: "3 Solari".
    ImperiumCardEntry(
        card=imperium_card("choam_directorship", "CHOAM Directorship"),
        copies=1,
        acquisition_cost=8,
        has_acquisition_bonus=True,
        acquisition_effect=(
            PersonalCardAcquisitionEffect.GAIN_INFLUENCE_WITH_EACH_FACTION
        ),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("carryall", "Carryall"),
        copies=1,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=imperium_card("chani_card", "Chani"),
        copies=1,
        acquisition_cost=5,
    ),
    # App table: cost 3, 1 copy, Fremen, Fremen and Spice Trade, Reveal 1 sword,
    # AgentSolari 1. Agent: "1 Solari". Reveal: "Fremen Bond: 1 Fremen
    # Influence" -- another Fremen card in play [DI p. 16], judged at
    # resolution (OQ-028).
    ImperiumCardEntry(
        card=imperium_card("crysknife_card", "Crysknife"),
        copies=1,
        acquisition_cost=3,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.GAIN_ONE_SOLARI,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # App table: cost 1, 1 copy, no Faction, City, Reveal 1 Persuasion. Agent:
    # "Draw 1 card" (its own step, OQ-106).
    ImperiumCardEntry(
        card=imperium_card("dr_yueh", "Dr. Yueh"),
        copies=1,
        acquisition_cost=1,
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # App table: cost 4, 1 copy, no Faction, City, Reveal 2 swords and 1 water
    # (the app's 2 swords, not the Dune Cards Hub scan's 3; P0 sweep, user
    # ruling). Agent: "[1 water] -> [troop] [draw 1 card]", an optional arrow
    # paid once [DI p. 9] [FAQ p. 3]; the troop and the draw are separate
    # steps (OQ-027, OQ-106).
    ImperiumCardEntry(
        card=imperium_card("duncan_idaho_card", "Duncan Idaho"),
        copies=1,
        acquisition_cost=4,
        agent_icons=(AgentIcon.CITY,),
        agent_effect=(
            PersonalCardAgentEffect.MAY_PAY_ONE_WATER_FOR_TROOP_AND_DRAW_ONE
        ),
        reveal_strength=2,
        play_data_complete=True,
    ),
    # App table: cost 3, 2 copies, Fremen, City and Spice Trade, Reveal 1
    # Persuasion (tag ConditionalStrength). Agent: the black trash icon, "You
    # may trash a card" (hand, discard pile or in play, itself included; an
    # optional icon, [DI p. 16] [FAQ p. 3]). Reveal: "Fremen Bond: 3 swords" --
    # another Fremen card in play [DI p. 16], judged at resolution (OQ-028).
    ImperiumCardEntry(
        card=imperium_card("fedaykin_death_commando", "Fedaykin Death Commando"),
        copies=2,
        acquisition_cost=3,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("firm_grip", "Firm Grip"),
        copies=1,
        acquisition_cost=4,
    ),
    # App table: cost 4, 2 copies, Fremen, Spice Trade, Reveal 2 Persuasion and
    # 1 sword. Agent: "[2 spice] -> [3 troops]", an optional arrow paid once
    # [DI p. 9] [FAQ p. 3] (the rulebook's own arrow example).
    ImperiumCardEntry(
        card=imperium_card("fremen_camp", "Fremen Camp"),
        copies=2,
        acquisition_cost=4,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_THREE_TROOPS,
        reveal_persuasion=2,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # App table: cost 3, 2 copies, Bene Gesserit, Landsraad and City, Reveal 2
    # Persuasion (tag WantBG). Agent: "[trash] AND If you have another Bene
    # Gesserit card in play: [2 spice]" -- two separate icons (OQ-027), the black
    # trash icon optional [DI p. 16] [FAQ p. 3], the Bond judged when the spice
    # resolves (OQ-028).
    ImperiumCardEntry(
        card=imperium_card("gene_manipulation", "Gene Manipulation"),
        copies=2,
        acquisition_cost=3,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        agent_effect=(
            PersonalCardAgentEffect.MAY_TRASH_AND_GAIN_TWO_SPICE_IF_BENE_GESSERIT_BOND
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # App table: cost 2, 2 copies, Spacing Guild, Spacing Guild and Spice
    # Trade, Reveal 1 Persuasion. Agent: the black trash icon, "You may trash
    # a card" (an optional icon, [DI p. 16] [FAQ p. 3]).
    ImperiumCardEntry(
        card=imperium_card("guild_administrator", "Guild Administrator"),
        copies=2,
        acquisition_cost=2,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # App table: cost 4, 1 copy, Spacing Guild, Landsraad, no fixed Reveal
    # values (tag SpacingGuildAlliance). Agent: "[Spacing Guild Influence] -OR-
    # [2 spice]", a printed -OR- the owner must settle (P0 sweep). Reveal:
    # "Spacing Guild Alliance: [3 spice] -> [1 Victory Point]" -- an optional
    # arrow paid once [DI p. 9] [FAQ p. 3], the Alliance judged at resolution
    # (OQ-028).
    ImperiumCardEntry(
        card=imperium_card("guild_ambassador", "Guild Ambassador"),
        copies=1,
        acquisition_cost=4,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD,),
        agent_effect=PersonalCardAgentEffect.GAIN_SPACING_GUILD_INFLUENCE_OR_TWO_SPICE,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_VICTORY_POINT_IF_SPACING_GUILD_ALLIANCE,
        ),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("guild_bankers", "Guild Bankers"),
        copies=1,
        acquisition_cost=3,
    ),
    # App table: cost 6, 1 copy, no Faction, City, Reveal 2 Persuasion, AgentTroops
    # 2. Agent: "[2 troops] [draw 1 card]" -- separate icons (OQ-027), the draw
    # a hidden step of its own (OQ-106). Reveal: "[P2] AND [3 Solari] -> [2
    # troops] + may deploy these troops" -- an optional arrow paid once [DI p.
    # 9] [FAQ p. 3]; in the Reveal turn the two recruits may deploy
    # (``DeployTheseTroops``).
    ImperiumCardEntry(
        card=imperium_card("gurney_halleck_card", "Gurney Halleck"),
        copies=1,
        acquisition_cost=6,
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.RECRUIT_TWO_AND_DRAW_ONE,
        reveal_persuasion=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SOLARI_FOR_TWO_TROOPS_AND_DEPLOY,
        ),
        play_data_complete=True,
    ),
    # App table: cost 2, 2 copies, Emperor, Emperor, Reveal 1 Persuasion and 1
    # sword. Agent: "Trash this card -> [Intrigue card]" -- an arrow cost, optional
    # [DI p. 9] [FAQ p. 3]; the card must trash itself to draw [FAQ p. 2],
    # and trashed by another effect it draws nothing. Reveal: "[P1][S1]" ([DI
    # p. 11] example).
    ImperiumCardEntry(
        card=imperium_card("imperial_spy", "Imperial Spy"),
        copies=2,
        acquisition_cost=2,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR,),
        agent_effect=PersonalCardAgentEffect.MAY_TRASH_SELF_TO_DRAW_INTRIGUE,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("kwisatz_haderach", "Kwisatz Haderach"),
        copies=1,
        acquisition_cost=8,
    ),
    # App table: cost 7, 1 copy, Bene Gesserit, Bene Gesserit, Landsraad, City
    # and Spice Trade, Reveal 3 Persuasion and 1 sword. Agent: "Draw 2 cards",
    # the card-draw icon printed twice -- one draw of two, its own step
    # (OQ-106). Acquire: Influence with a Faction of the owner's choice, "once,
    # when acquired" [DI p. 16], a row (OQ-141); a Faction at 6 is not offered
    # (OQ-060).
    ImperiumCardEntry(
        card=imperium_card("lady_jessica_card", "Lady Jessica"),
        copies=1,
        acquisition_cost=7,
        has_acquisition_bonus=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(
            AgentIcon.BENE_GESSERIT,
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=PersonalCardAgentEffect.DRAW_TWO_CARDS,
        acquisition_effect=(
            PersonalCardAcquisitionEffect.GAIN_INFLUENCE_WITH_CHOSEN_FACTION
        ),
        reveal_persuasion=3,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # App table: cost 5, 1 copy, Emperor and Fremen, Fremen and City, no fixed
    # Reveal values, AcquireEffect RankE. Acquire: "1 Emperor Influence".
    # Reveal: "[P2] for each Fremen card you have in play (including this one)"
    # -- the cards played on this round's Agent turns and this Reveal turn's
    # [FAQ p. 2], counted when it resolves (OQ-028); it counts as a Fremen card
    # itself.
    ImperiumCardEntry(
        card=imperium_card("liet_kynes_card", "Liet Kynes"),
        copies=1,
        acquisition_cost=5,
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR, Faction.FREMEN),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        acquisition_effect=PersonalCardAcquisitionEffect.GAIN_EMPEROR_INFLUENCE,
        play_data_complete=True,
    ),
    # App table: cost 1, 2 copies, Bene Gesserit (the errata's faction, [FAQ p.
    # 1]), City, Reveal 1 Persuasion (tag WantBG). Agent: "If you have another
    # Bene Gesserit card in play: [Influence of your choice]", judged at
    # resolution (OQ-028); a track at 6 is not offered (OQ-060).
    ImperiumCardEntry(
        card=imperium_card("missionaria_protectiva", "Missionaria Protectiva"),
        copies=2,
        acquisition_cost=1,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=(
            PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_BENE_GESSERIT_BOND
        ),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # App table: cost 6, 1 copy, Emperor, Emperor, Reveal 1 Persuasion,
    # AgentSolari 3. Agent: "3 Solari". Reveal: "1 Persuasion AND [6 Solari]
    # -> [1 Victory Point]" -- an optional arrow, paid once [DI p. 9] [FAQ p. 3].
    ImperiumCardEntry(
        card=imperium_card("opulence", "Opulence"),
        copies=1,
        acquisition_cost=6,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR,),
        agent_effect=PersonalCardAgentEffect.GAIN_THREE_SOLARI,
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_PAY_SIX_SOLARI_FOR_VICTORY_POINT,
        ),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("other_memory", "Other Memory"),
        copies=1,
        acquisition_cost=4,
    ),
    # App table: cost 5, 1 copy, no Faction, Landsraad and City, Reveal 3
    # Persuasion and 1 sword. Agent: "Draw 1 Intrigue card" (the Intrigue-draw
    # icon alone; a hidden draw, its own step, OQ-106).
    ImperiumCardEntry(
        card=imperium_card("piter_de_vries_card", "Piter De Vries"),
        copies=1,
        acquisition_cost=5,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.DRAW_INTRIGUE_CARD,
        reveal_persuasion=3,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("power_play", "Power Play"),
        copies=3,
        acquisition_cost=5,
    ),
    # App table: cost 6, 1 copy, Emperor and Bene Gesserit, Emperor and Bene
    # Gesserit, Reveal 2 Persuasion and 2 spice (tags NamedCharacter, WantBG).
    # Agent: "If you have another Bene Gesserit card in play, each opponent
    # discards two cards" -- judged at resolution (OQ-028); each opponent
    # picks, clockwise from the player's left, as many as the hand holds
    # [FAQ p. 3] (OQ-118). Reveal: "[P2] [2 spice]".
    ImperiumCardEntry(
        card=imperium_card("reverend_mother_mohiam", "Reverend Mother Mohiam"),
        copies=1,
        acquisition_cost=6,
        factions=(Faction.EMPEROR, Faction.BENE_GESSERIT),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.BENE_GESSERIT),
        agent_effect=(
            PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_TWO_IF_BENE_GESSERIT_BOND
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # App table: cost 1, 2 copies, Emperor, no Agent icons, Reveal 1 Persuasion
    # and 2 swords. A card with no Agent icon is a Reveal-only card [DI p. 9]:
    # no Agent box either.
    ImperiumCardEntry(
        card=imperium_card("sardaukar_infantry", "Sardaukar Infantry"),
        copies=2,
        acquisition_cost=1,
        factions=(Faction.EMPEROR,),
        agent_icons=(),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("sardaukar_legion", "Sardaukar Legion"),
        copies=2,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=imperium_card("scout", "Scout"),
        copies=2,
        acquisition_cost=1,
    ),
    ImperiumCardEntry(
        card=imperium_card("shifting_allegiances", "Shifting Allegiances"),
        copies=2,
        acquisition_cost=3,
    ),
    # App table: cost 4, 1 copy, Bene Gesserit and Fremen, Bene Gesserit and
    # Fremen, no fixed Reveal values (tag FremenBond). Agent: the black trash
    # icon, "You may trash a card" (an optional icon, [DI p. 16] [FAQ p. 3]).
    # Reveal: "Fremen Bond: [P3] [1 spice]" -- another Fremen card in play
    # [DI p. 16], judged at resolution (OQ-028); nothing unconditional.
    ImperiumCardEntry(
        card=imperium_card("sietch_reverend_mother", "Sietch Reverend Mother"),
        copies=1,
        acquisition_cost=4,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        play_data_complete=True,
    ),
    # App table: cost 4, 2 copies, Spacing Guild, Spice Trade, Reveal 1
    # Persuasion and 1 spice (tag SpacingGuildInfluence). Agent: "Spacing
    # Guild Influence 2: [draw] [draw]" -- two icons, each judged when it
    # resolves (OQ-027, OQ-028; the P0 sweep's "two icons"). Reveal: "[P1]
    # [1 spice]" ([DI p. 11] example).
    ImperiumCardEntry(
        card=imperium_card("smugglers_thopter", "Smuggler's Thopter"),
        copies=2,
        acquisition_cost=4,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.DRAW_TWO_IF_SPACING_GUILD_INFLUENCE_TWO,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # App table: cost 3, 2 copies, Spacing Guild, Spacing Guild, Reveal 2
    # Persuasion. Agent: "Draw 1 card" (the card-draw icon alone; its own step,
    # OQ-106).
    ImperiumCardEntry(
        card=imperium_card("space_travel", "Space Travel"),
        copies=2,
        acquisition_cost=3,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD,),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # App table: cost 2, 2 copies, Fremen, Fremen and Spice Trade, Reveal 1
    # Persuasion and 1 sword (tag FremenBond). Agent: no box (the icons only).
    # Reveal: "Fremen Bond: 1 spice" -- another Fremen card in play [DI p. 16],
    # judged at resolution (OQ-028).
    ImperiumCardEntry(
        card=imperium_card("spice_hunter", "Spice Hunter"),
        copies=2,
        acquisition_cost=2,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # App table: cost 5, 1 copy, Fremen, Fremen, City and Spice Trade, Reveal 2
    # Persuasion and 3 swords, AgentWater 1. Agent: "1 water", a plain gain.
    ImperiumCardEntry(
        card=imperium_card("stilgar", "Stilgar"),
        copies=1,
        acquisition_cost=5,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.GAIN_WATER,
        reveal_persuasion=2,
        reveal_strength=3,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("test_of_humanity", "Test of Humanity"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=imperium_card("the_voice", "The Voice"),
        copies=2,
        acquisition_cost=2,
    ),
    # App table: cost 5, 1 copy, no Faction, six Agent icons (every one but
    # Landsraad), Reveal 1 Persuasion. Agent: "Draw 1 card" (its own step,
    # OQ-106). Reveal: "[P1] [Intrigue card]" -- the Intrigue draw is a step of
    # the owner's own (OQ-045, OQ-106).
    ImperiumCardEntry(
        card=imperium_card("thufir_hawat", "Thufir Hawat"),
        copies=1,
        acquisition_cost=5,
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # App table: cost 6, 2 copies, Fremen, City and Spice Trade, no fixed Reveal
    # values (tags FremenInfluence, FremenAlliance, ConditionalStrength),
    # AgentSpice 2. Agent: "2 spice", a plain gain. Reveal: "Fremen Influence 2:
    # [4 swords]" and, on its own line, "Fremen Alliance: [2 swords]" -- two
    # independent lines, each judged when resolved (OQ-028); nothing
    # unconditional.
    ImperiumCardEntry(
        card=imperium_card("worm_riders", "Worm Riders"),
        copies=2,
        acquisition_cost=6,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.GAIN_TWO_SPICE,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("duncan_loyal_blade", "Duncan, Loyal Blade"),
        copies=1,
        acquisition_cost=5,
        promo=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("jessica_of_arrakis", "Jessica of Arrakis"),
        copies=1,
        acquisition_cost=3,
        promo=True,
    ),
    ImperiumCardEntry(
        card=imperium_card("thumper", "Thumper"),
        copies=1,
        acquisition_cost=3,
        promo=True,
    ),
)
