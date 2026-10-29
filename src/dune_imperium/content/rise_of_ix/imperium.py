"""Rise of Ix's Imperium cards and its promo (stage P4a).

docs/base-game-and-ix-plan.md 17.1 and 17.7: 29 Imperium kinds, 35 cards
shuffled into the Imperium deck, and the promo Boundless Ambition kept apart
behind ``promo_cards`` (plan 9 8) [Rise of Ix p. 2]
(docs/rules/rise-of-ix.md 2). Per D1 (plan 2.4) every value comes from the
Steam app: the attribute table for cost and copies now, the card's screen
pieces and English text when its play data is transcribed; the rules behind
them are docs/rules/rise-of-ix.md.

These began as stage P4a identity entries (name, copies and cost), generated
by ``scripts/dwgr/imperium_entries.py --set ix skeleton``. Incomplete entries
keep ``play_data_complete`` False and expose no partial play data; printed
Infiltration icons are identity metadata. With ``rise_of_ix`` the original
game's deck takes only completed cards (CHOAM Delegate, Jamis, Landing
Rights, Sayyadina, Shai-Hulud, Truthsayer, Imperial Shock Trooper, Local
Fence, Water Peddler, Guild Chief Administrator, Negotiated Withdrawal,
Desert Ambush, Full-Scale Assault, Embedded Agent, Court Intrigue, Weirding
Way, Satellite Ban, Spice Trader, Imperial Bashar, Bounty Hunter, Web of
Power, Ixian Engineer and Esmar Tuek so far), while the observation lists
every identity from v39. Setup takes Rise of Ix on the original game since
stage P4c-5.
from v39. Setup takes Rise of Ix on the original game since stage P4c-5.
``content.uprising.imperium``'s
``IMPERIUM_CARDS_BY_ID`` resolves them; code that lists Uprising's own
cards iterates ``IMPERIUM_CARDS`` instead, and the original game's
``IMPERIUM_BASE_CARDS`` does not hold them.
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
)

# The component table lists the cards [Rise of Ix p. 2]; the printed values
# are the app's (plan 2.4, D1).
IX_IMPERIUM_SOURCES: Final = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),)
_LOCAL_FENCE = (
    PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_FIVE_SOLARI_OR_FIVE_SOLARI_FOR_FOUR_SPICE
)
_BOUNTY_HUNTER = PersonalCardAgentEffect.GAIN_TWO_SOLARI_IF_ENEMY_AGENT_ON_SPACE
_WEB_OF_POWER = (
    PersonalCardAgentEffect.GAIN_BY_EMPEROR_SPACING_GUILD_AND_FREMEN_INFLUENCE_TWO
)
_SPICE_TRADER = (
    PersonalCardAgentEffect.MAY_DISCARD_FOR_TWO_SPICE_IF_FREMEN_INFLUENCE_TWO
)
_ESMAR_TUEK = (
    PersonalCardAgentEffect.MAY_PAY_ONE_SPICE_FOR_SPACING_GUILD_INFLUENCE_AND_DRAW_ONE
)


def ix_imperium_card(card_id: str, name: str) -> CardDefinition:
    """The identity of a Rise of Ix Imperium card (no Dune Cards Hub URL:
    the faces are not read, D1)."""

    return CardDefinition(card_id=card_id, name=name, sources=IX_IMPERIUM_SOURCES)


# Typed: ``content.uprising.imperium`` reads it while both modules load.
IX_IMPERIUM_CARDS: Final[tuple[ImperiumCardEntry, ...]] = (
    ImperiumCardEntry(
        card=ix_imperium_card("appropriate", "Appropriate"),
        copies=1,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("bounty_hunter", "Bounty Hunter"),
        copies=1,
        acquisition_cost=1,
        infiltration_icons=(AgentIcon.CITY,),
        # App table: no Faction, the City icon (also its Infiltration icon),
        # Reveal 1 Persuasion and 1 sword. Agent: "If used to send an Agent to
        # a board space with an enemy Agent: [2 Solari]" [Steam app screen
        # pieces and text] -- a condition on the space the Agent goes to, fixed
        # by the placement, so the box is judged when the card is played.
        agent_icons=(AgentIcon.CITY,),
        agent_effect=_BOUNTY_HUNTER,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("choam_delegate", "CHOAM Delegate"),
        copies=1,
        acquisition_cost=1,
        infiltration_icons=(AgentIcon.SPICE_TRADE,),
        # App table: no Faction, Agent icon Spice Trade (its Infiltration
        # icon, ``InfiltrationIconList``), Reveal 3 Solari; no Agent box.
        # Screen pieces: Reveal "[Unload] [3 Solari]" -- the box is gained
        # also when the card is discarded or trashed [Rise of Ix p. 7]
        # (``rules.unload``); its record is ``REVEAL_GAIN_ABILITIES``.
        agent_icons=(AgentIcon.SPICE_TRADE,),
        unload=True,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("court_intrigue", "Court Intrigue"),
        copies=1,
        acquisition_cost=2,
        infiltration_icons=(AgentIcon.EMPEROR,),
        # App table: Emperor; the Emperor icon, its Infiltration icon
        # (``InfiltrationIconList``); Reveal 1 Persuasion, 1 sword. Text and
        # screen pieces: Agent "Put an Intrigue card on the bottom of the
        # deck -> [Intrigue card]", unseen by the others [Rise of Ix p. 10].
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR,),
        agent_effect=PersonalCardAgentEffect.MAY_PUT_INTRIGUE_ON_BOTTOM_TO_DRAW_INTRIGUE,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("desert_ambush", "Desert Ambush"),
        copies=1,
        acquisition_cost=3,
        # App table: Fremen, the Spice Trade icon; Reveal 1 Persuasion, 1
        # sword. Text: Agent "For each troop you deploy this turn, you may
        # force an enemy unit to retreat." -- an enemy troop or dreadnought
        # [Rise of Ix p. 6], the player of the card picking it.
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=(
            PersonalCardAgentEffect.MAY_FORCE_ENEMY_UNIT_RETREAT_FOR_EACH_TROOP_DEPLOYED
        ),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("embedded_agent", "Embedded Agent"),
        copies=1,
        acquisition_cost=5,
        infiltration_icons=(AgentIcon.LANDSRAAD,),
        # App table: Bene Gesserit; the Landsraad icon, its Infiltration icon
        # (``InfiltrationIconList``); Reveal 1 Persuasion. Screen pieces and
        # text: Agent "If you have another Bene Gesserit card in play:
        # [Freighter] [Freighter]"; Reveal "[1 Persuasion] [Intrigue card]"
        # (its Reveal record, Thufir Hawat's line).
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD,),
        agent_effect=PersonalCardAgentEffect.MAY_MOVE_FREIGHTER_TWICE_IF_BENE_GESSERIT_BOND,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("esmar_tuek_card", "Esmar Tuek"),
        copies=1,
        acquisition_cost=5,
        # Not Bloodlines' Leader Esmar Tuek (``esmar_tuek``): the card id
        # carries ``_card`` (plan 17.2). App table: Spacing Guild, the City
        # and Spice Trade icons (``Circle``, ``Triangle``), Reveal 2 spice and
        # 2 Solari. Screen pieces: Agent "[1 spice] -> [Spacing Guild
        # Influence] [draw 1 card]", an optional arrow [DI p. 9] [FAQ p. 3];
        # Reveal "[Unload] [2 spice] [2 Solari]" -- the box is gained also
        # when the card is discarded or trashed [Rise of Ix p. 7]
        # (``rules.unload``); its record is ``REVEAL_GAIN_ABILITIES``. Trashed
        # before its Agent box resolves, the box expires and the Unload's
        # spice cannot pay it (OQ-022, docs/rules/rise-of-ix.md 7).
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=_ESMAR_TUEK,
        unload=True,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("freighter_fleet", "Freighter Fleet"),
        copies=2,
        acquisition_cost=2,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("full_scale_assault", "Full-Scale Assault"),
        copies=1,
        acquisition_cost=8,
        # App table: Emperor; Emperor and City icons; AgentTroops 2;
        # AcquireEffectList Dreadnought; Reveal 2 Persuasion. Screen pieces
        # and text: Agent "[troop] [troop]"; Reveal "[3 swords] for each of
        # your dreadnoughts in the Conflict." (its Reveal record); acquire
        # the Dreadnought icon, "you may commission" [Rise of Ix p. 6].
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.RECRUIT_TWO_TROOPS,
        acquisition_effect=PersonalCardAcquisitionEffect.MAY_COMMISSION_DREADNOUGHT,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("guild_accord", "Guild Accord"),
        copies=1,
        acquisition_cost=6,
        infiltration_icons=(AgentIcon.SPACING_GUILD,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("guild_chief_administrator", "Guild Chief Administrator"),
        copies=1,
        acquisition_cost=4,
        # App table: Spacing Guild; Spacing Guild, City and Spice Trade icons;
        # Reveal 1 Persuasion. Screen pieces: Agent "[Discard] -> [Trash a
        # card]", an optional arrow whose trash stays optional [FAQ p. 3];
        # Reveal "[1 Persuasion] [Freighter]", the Freighter a "may" [Rise of
        # Ix p. 5] -- its Reveal choice record.
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_TO_TRASH_A_CARD,
        reveal_persuasion=1,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.MAY_MOVE_FREIGHTER,),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("imperial_bashar", "Imperial Bashar"),
        copies=1,
        acquisition_cost=4,
        # App table: Emperor, the City icon, Reveal 1 Persuasion and 2 swords.
        # Reveal: "+[sword] for each other revealed card that provides one or
        # more [sword] this turn" -- Leadership's, a Reveal record
        # (``reveal_abilities``) [Steam app text; Rise of Ix p. 10]. Agent:
        # "[Troop] -OR- [Trash a card]" [Steam app screen pieces and text], a
        # recruit beside a black trash icon, which is optional ("Trash ...
        # 비용이거나 카드가 자기를 trash하라고 할 때만 의무", imperium-base.md 11,
        # [DI p. 16]), so the box is optional too and lapses unused at the
        # turn's end (OQ-095 (2)).
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.RECRUIT_ONE_OR_MAY_TRASH_A_CARD,
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("imperial_shock_trooper", "Imperial Shock Trooper"),
        copies=1,
        acquisition_cost=3,
        # App table: Emperor, no Agent icon; Reveal 1 Persuasion, 2 swords.
        # "If you have an Agent on an [Emperor] board space," [+3 swords] is
        # its Reveal record (``reveal_abilities``) [Steam app text].
        factions=(Faction.EMPEROR,),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("in_the_shadows", "In The Shadows"),
        copies=2,
        acquisition_cost=2,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("ix_guild_compact", "Ix-Guild Compact"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("ixian_engineer", "Ixian Engineer"),
        copies=2,
        acquisition_cost=5,
        # App table: no Faction, the Spice Trade icon, no fixed Reveal values.
        # Agent: the Acquire Tech icon, which the screen pieces print without a
        # Tech Discount sprite, so a discount of 0 -- the plain icon of the
        # Dreadnought space (``AcquireTechAgentAbility`` sets no discount)
        # [Steam app screen pieces]. Reveal: "If you have three or more Techs:
        # Trash this card -> 1 Victory Point" [Steam app text], an optional
        # arrow (a Reveal choice) whose cost is the card's own trash.
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.MAY_ACQUIRE_TECH,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_VICTORY_POINT_IF_THREE_TECH_TILES,
        ),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("jamis", "Jamis"),
        copies=1,
        acquisition_cost=2,
        infiltration_icons=(AgentIcon.FREMEN,),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN,),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("landing_rights", "Landing Rights"),
        copies=1,
        acquisition_cost=4,
        # App table: Spacing Guild, City icon; Reveal 2 Persuasion. Agent: the
        # Freighter icon [Steam app screen pieces], "you may move your Freighter"
        # [Rise of Ix p. 5] (docs/rules/rise-of-ix.md 5).
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.MAY_MOVE_FREIGHTER,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("local_fence", "Local Fence"),
        copies=1,
        acquisition_cost=3,
        # App table: no Faction, City icon; Reveal 2 Persuasion. Agent: "[2
        # spice] -> [5 Solari] -OR- [5 Solari] -> [4 spice]" [Steam app
        # screen pieces and text], two optional arrows of which one is paid.
        agent_icons=(AgentIcon.CITY,),
        agent_effect=_LOCAL_FENCE,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("negotiated_withdrawal", "Negotiated Withdrawal"),
        copies=2,
        acquisition_cost=4,
        # App table: no Faction; Landsraad, City and Spice Trade icons, no
        # Agent box; AcquireEffectList Troop; Reveal 2 Persuasion. Text and
        # screen pieces: Reveal "Retreat three of your units -> [Influence
        # with any Faction]", an optional arrow -- its Reveal choice record;
        # a unit is a troop or a dreadnought [Rise of Ix p. 6].
        has_acquisition_bonus=True,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        acquisition_effect=PersonalCardAcquisitionEffect.RECRUIT_ONE_TROOP,
        reveal_persuasion=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_RETREAT_THREE_UNITS_FOR_INFLUENCE,
        ),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("satellite_ban", "Satellite Ban"),
        copies=1,
        acquisition_cost=5,
        # App table: Spacing Guild and Fremen, their two Agent icons, Reveal 1
        # Persuasion, no fixed swords. Agent: "[Discard] -> [1 spice] [1
        # water]", an optional arrow [Rise of Ix p. 7]. Reveal: "Retreat up to
        # two of your troops." [Steam app screen pieces and text] -- Scout's
        # sentence, so the same choice (0 to 2 troops, none included).
        factions=(Faction.SPACING_GUILD, Faction.FREMEN),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.FREMEN),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_FOR_ONE_SPICE_AND_ONE_WATER,
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_RETREAT_UP_TO_TWO_TROOPS,
        ),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("sayyadina", "Sayyadina"),
        copies=1,
        acquisition_cost=3,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN),
        # App pieces: "[3 water] -> [1 Victory Point]"; the arrow is
        # optional [DI p. 9] [FAQ p. 3]. Reveal: "Fremen Bond: [P3]",
        # another Fremen card in play [DI p. 16], no fixed Persuasion.
        agent_effect=PersonalCardAgentEffect.MAY_PAY_THREE_WATER_FOR_VP,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("shai_hulud", "Shai-Hulud"),
        copies=1,
        acquisition_cost=7,
        # App table: Fremen, Spice Trade icon, AcquireEffectList Trash; no
        # fixed Reveal values. Acquire: the black Trash icon, optional like any
        # Trash icon [DI p. 16] and resolved at once [Main p. 20]. Agent: "[Trash
        # a card] -> [2 troops]". Reveal: "Fremen Bond: [5 swords]" (a Reveal
        # record), another Fremen card in play [DI p. 16].
        has_acquisition_bonus=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_RECRUIT_TWO,
        acquisition_effect=PersonalCardAcquisitionEffect.MAY_TRASH_A_CARD,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("spice_trader", "Spice Trader"),
        copies=1,
        acquisition_cost=4,
        # App table: Fremen, City and Spice Trade icons, Reveal 2 Persuasion and
        # 1 sword. Agent: "[Fremen] 2 Influence : [Discard] -> [2 spice]" [Steam
        # app screen pieces and text] -- the Influence threshold of High
        # Priority Travel's words over an optional Discard arrow
        # [Rise of Ix p. 7], judged when the cost is paid (OQ-028).
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=_SPICE_TRADER,
        reveal_persuasion=2,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("treachery", "Treachery"),
        copies=2,
        acquisition_cost=6,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("truthsayer", "Truthsayer"),
        copies=2,
        acquisition_cost=3,
        # App screen pieces: Discard -> draw 1; Reveal 1 Persuasion, 1 sword.
        # The hand-card cost uses the same optional arrow as other cards
        # [Rise of Ix p. 7] [FAQ p. 2].
        factions=(Faction.EMPEROR, Faction.BENE_GESSERIT),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.BENE_GESSERIT, AgentIcon.LANDSRAAD),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("water_peddler", "Water Peddler"),
        copies=1,
        acquisition_cost=1,
        # App table: no Faction, no Agent icon (a Reveal-only card [DI p. 9]),
        # AcquireEffect Water, Reveal 1 water. Screen pieces: acquire
        # "[1 water]"; Reveal "[Unload] [1 water]" -- the box is gained also
        # when the card is discarded or trashed [Rise of Ix p. 7]
        # (``rules.unload``); its record is ``REVEAL_GAIN_ABILITIES``.
        has_acquisition_bonus=True,
        acquisition_effect=PersonalCardAcquisitionEffect.GAIN_ONE_WATER,
        unload=True,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("web_of_power", "Web of Power"),
        copies=1,
        acquisition_cost=4,
        infiltration_icons=(AgentIcon.BENE_GESSERIT,),
        # App table: Bene Gesserit, the Bene Gesserit icon (also its
        # Infiltration icon), Reveal 1 Persuasion. Reveal: the wild Influence
        # icon, "Choose a Faction to gain 1 Influence with" [Steam app text]
        # (a Reveal choice, mandatory). Agent: "[Emperor] 2 Influence: [2
        # Solari]", "[Spacing Guild] 2 Influence: [draw 1]" and "[Fremen] 2
        # Influence: [1 water]" [Steam app screen pieces and text] -- three
        # Influence thresholds, each its own icon judged when it resolves.
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT,),
        agent_effect=_WEB_OF_POWER,
        reveal_persuasion=1,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE,),
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("weirding_way", "Weirding Way"),
        copies=1,
        acquisition_cost=3,
        # App table: Bene Gesserit; City and Spice Trade icons; Reveal 1
        # Persuasion, 2 swords. Text: Agent "You may take another turn
        # immediately after this one."
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.MAY_TAKE_ANOTHER_TURN,
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("boundless_ambition", "Boundless Ambition"),
        copies=1,
        acquisition_cost=5,
        promo=True,
    ),
)
