"""Types shared by Uprising card manifests."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AgentIcon(StrEnum):
    """Agent icons shared by cards and board spaces."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"
    LANDSRAAD = "landsraad"
    CITY = "city"
    SPICE_TRADE = "spice_trade"
    SPY = "spy"


class PersonalCardBond(StrEnum):
    """Faction affiliation required from another card in play."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"


class PersonalCardAgentEffect(StrEnum):
    """Typed Agent-box effects currently transcribed for personal cards."""

    GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF = (
        "gain_two_visited_faction_influence_and_trash_self"
    )
    LOOK_AT_TOP_THREE = "look_at_top_three"
    # "Trash this card." printed as a sentence (Seek Allies): mandatory
    # [Main p. 20]; the plain trash icon is TRASH_PERSONAL_CARD instead.
    TRASH_SELF = "trash_self"
    TRASH_PERSONAL_CARD = "trash_personal_card"
    TRASH_PERSONAL_CARD_TO_DRAW_ONE = "trash_personal_card_to_draw_one"
    TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND = (
        "trash_personal_card_to_draw_one_if_bene_gesserit_bond"
    )
    MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE = (
        "may_trash_for_intrigue_and_two_troops_if_bene_gesserit_alliance"
    )
    TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE = (
        "trash_self_and_emperor_from_hand_for_extra_influence"
    )
    TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE = (
        "trash_self_and_gain_chosen_influence"
    )
    GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN = (
        "gain_chosen_influence_if_spy_recalled_this_turn"
    )
    LEADER_SIGNET = "leader_signet"
    PAY_TWO_WATER_TO_DRAW_TWO = "pay_two_water_to_draw_two"
    MAY_PAY_FOUR_SPICE_FOR_VP = "may_pay_four_spice_for_vp"
    MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP = (
        "may_discard_two_and_pay_five_solari_for_vp"
    )
    MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE = (
        "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
    )
    ACQUIRE_WITH_SOLARI_TO_HAND = "acquire_with_solari_to_hand"
    TAKE_CONTRACT = "take_contract"
    MAY_DISCARD_TO_TAKE_CONTRACT = "may_discard_to_take_contract"
    DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO = (
        "draw_per_two_completed_contracts_up_to_two"
    )
    GAIN_CHOSEN_INFLUENCE = "gain_chosen_influence"
    DRAW_ONE_AND_RECALL_AGENT = "draw_one_and_recall_agent"
    DRAW_PERSONAL_CARD = "draw_personal_card"
    DRAW_PER_SANDWORM_IN_CONFLICT = "draw_per_sandworm_in_conflict"
    DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD = (
        "discard_to_draw_one_or_two_if_spacing_guild"
    )
    DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD = (
        "discard_one_draw_two_if_spacing_guild"
    )
    MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD = (
        "may_discard_to_draw_intrigue_and_personal_card"
    )
    MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD = (
        "may_discard_to_draw_one_and_intrigue_if_spacing_guild"
    )
    EACH_OPPONENT_DISCARDS_PERSONAL_CARD = "each_opponent_discards_personal_card"
    GAIN_SPICE_IF_MAKER_SPACE = "gain_spice_if_maker_space"
    GAIN_TWO_SPICE_IF_MAKER_SPACE = "gain_two_spice_if_maker_space"
    GAIN_TWO_SOLARI = "gain_two_solari"
    # Ixian Ambassador (Tech Module): "1 spice".
    GAIN_ONE_SPICE = "gain_one_spice"
    PLACE_SPY = "place_spy"
    PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE = (
        "place_spy_allow_shared_if_spying_on_visited_space"
    )
    RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_three_if_spy_recalled_this_turn"
    )
    RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_two_if_spy_recalled_this_turn"
    )
    # Uprising promo cards (card faces; see docs/rules/open-questions.md
    # OQ-024 to OQ-026 for the project rulings behind each).
    MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS = (
        "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks"
    )
    GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON = "gain_rewards_per_face_up_battle_icon"
    MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE = (
        "may_trash_self_for_troop_and_first_place_influence"
    )
    DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN = (
        "draw_intrigue_if_spy_recalled_this_turn"
    )
    DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT = (
        "draw_intrigue_if_three_units_in_conflict"
    )
    GAIN_WATER_IF_BENE_GESSERIT_BOND = "gain_water_if_bene_gesserit_bond"
    GAIN_VISITED_FACTION_INFLUENCE = "gain_visited_faction_influence"
    GAIN_WATER = "gain_water"
    GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO = (
        "gain_by_bene_gesserit_and_fremen_influence_two"
    )
    GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO = (
        "gain_by_emperor_and_spacing_guild_influence_two"
    )
    RECRUIT_ONE_IF_MAKER_SPACE = "recruit_one_if_maker_space"
    RECRUIT_TWO_TROOPS = "recruit_two_troops"
    RECRUIT_TWO_IF_BENE_GESSERIT_BOND = "recruit_two_if_bene_gesserit_bond"
    RETURN_SELF_IF_BENE_GESSERIT_BOND = "return_self_if_bene_gesserit_bond"
    DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO = (
        "draw_if_bene_gesserit_influence_two"
    )
    RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO = (
        "recruit_one_and_draw_if_bene_gesserit_influence_two"
    )
    # Bloodlines (card faces, 2026-09-07).
    DRAW_INTRIGUE_CARD = "draw_intrigue_card"
    RECRUIT_ONE_IF_EMPEROR_INFLUENCE_TWO = "recruit_one_if_emperor_influence_two"
    MAY_DISCARD_TO_DRAW_ONE = "may_discard_to_draw_one"
    DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT = "draw_intrigue_if_sandworm_in_conflict"
    DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN = "draw_one_if_gained_two_spice_this_turn"
    RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN = (
        "recruit_one_and_draw_one_if_gained_two_spice_this_turn"
    )
    TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN = (
        "take_contract_if_spy_recalled_this_turn"
    )
    DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN = (
        "draw_intrigue_if_contract_completed_this_turn"
    )
    # Elite Forces: "You may trash a card from your hand. If you trash an
    # Emperor card: Intrigue, troop, Combat icon".
    MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS = (
        "may_trash_hand_card_for_emperor_rewards"
    )
    # Disruption Tactics: "Force an enemy troop to retreat."
    FORCE_OPPONENT_TROOP_RETREAT = "force_opponent_troop_retreat"
    # Arrakis Observer: "[discard] -> Spy with Deep Cover; if you discarded a
    # Spacing Guild card: 2 spice".
    MAY_DISCARD_FOR_DEEP_COVER_SPY = "may_discard_for_deep_cover_spy"
    # Engineered Miracle: "[discard] -> water".
    MAY_DISCARD_FOR_WATER = "may_discard_for_water"
    # CHOAM Demands: "Complete one of your contracts."
    COMPLETE_ONE_CONTRACT = "complete_one_contract"
    # Urgent Shigawire: "The next Bene Gesserit card you play this round has
    # all Agent icons and, added to its Agent box: draw a card."
    BOOST_NEXT_BENE_GESSERIT_CARD_THIS_ROUND = (
        "boost_next_bene_gesserit_card_this_round"
    )
    # Holy War: "Each opponent loses one troop. Each opponent spying on the
    # board space where you sent an Agent this turn must move that Spy."
    EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY = (
        "each_opponent_loses_troop_and_moves_spy"
    )
    # Southern Faith: "draw a card OR, if another Bene Gesserit card is in
    # play, Bene Gesserit Influence".
    DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND = (
        "draw_one_or_bene_gesserit_influence_if_bond"
    )
    # Possible Futures: "Influence of your choice OR 2 troops; with another
    # Bene Gesserit card in play, get both".
    CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND = (
        "chosen_influence_or_two_troops_both_if_bond"
    )
    # Ruthless Leadership (Bloodlines promo, card face): "If you have one or
    # more Sardaukar Commanders in the Conflict:" two black trash icons —
    # each an optional trash of a card from hand, discard pile or in play
    # [Main p. 20]; the condition is judged when the box resolves (OQ-028).
    MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT = (
        "may_trash_two_cards_if_commander_in_conflict"
    )
    # Immortality (card faces, 2026-09-08). Experimentation: the Research
    # icon [Immortality pp. 6, 16].
    RESEARCH = "research"
    # Contaminator: the Tleilaxu icon [Immortality pp. 7, 16].
    ADVANCE_TLEILAXU = "advance_tleilaxu"
    # Subject X-137: "[one genetic marker]: Tleilaxu", judged when the box
    # resolves (OQ-028).
    ADVANCE_TLEILAXU_IF_ONE_MARKER = "advance_tleilaxu_if_one_marker"
    # Corrino Genes: "If grafted: Tleilaxu" [Immortality p. 11].
    ADVANCE_TLEILAXU_IF_GRAFTED = "advance_tleilaxu_if_grafted"
    # Unnatural Reflexes (Graft): "[one genetic marker]: draw two cards".
    DRAW_TWO_IF_ONE_MARKER = "draw_two_if_one_marker"
    # Tleilaxu Infiltrator (Graft): "Enemy Agents don't block your Agent this
    # turn. Draw a card —AND— [two genetic markers]: Intrigue".
    DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS = "draw_one_and_intrigue_if_two_markers"
    # Twisted Mentat (Graft): "You may recall the Agent you sent this turn."
    MAY_RECALL_AGENT_SENT_THIS_TURN = "may_recall_agent_sent_this_turn"
    # Immortality Imperium cards (card faces).
    # Bene Tleilax Lab: a specimen.
    GENERATE_SPECIMEN = "generate_specimen"
    # Clandestine Meeting: Bene Gesserit Influence and an Intrigue card.
    GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE = (
        "gain_bene_gesserit_influence_and_intrigue"
    )
    # Corrupt Smuggler: "If grafted: 2 spice".
    GAIN_TWO_SPICE_IF_GRAFTED = "gain_two_spice_if_grafted"
    # Keys to Power: "[Emperor] 2 Influence: 2 spice".
    GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO = "gain_two_spice_if_emperor_influence_two"
    # Lisan al Gaib: "If you have another Bene Gesserit card in play: Fremen
    # Influence".
    GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND = (
        "gain_fremen_influence_if_bene_gesserit_bond"
    )
    # Occupation: draw a card and the Combat icon.
    DRAW_ONE_AND_COMBAT_ICON = "draw_one_and_combat_icon"
    # Sardaukar Quartermaster: "If grafted: troop, draw a card".
    RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED = "recruit_one_and_draw_one_if_grafted"
    # Show of Strength: draw two cards.
    DRAW_TWO_CARDS = "draw_two_cards"
    # Stillsuit Manufacturer: water —AND— Fremen Alliance: return this card
    # from play to your hand.
    GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE = (
        "gain_water_and_return_self_if_fremen_alliance"
    )
    # Throne Room Politics: a troop and a (black, optional) trash icon.
    RECRUIT_ONE_AND_MAY_TRASH = "recruit_one_and_may_trash"
    # Long Reach: "Choose two:" of the four Faction Influences.
    GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE = "gain_two_distinct_chosen_influence"
    # Organ Merchants: "specimen -> 4 Solari".
    MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI = "may_pay_specimen_for_four_solari"
    # Dissecting Kit (Graft): "Trash the other grafted card -> a specimen".
    MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN = "may_trash_other_grafted_for_specimen"
    # High Priority Travel: "[Guild] 2 Influence: draw a card —OR— Combat".
    DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO = (
        "draw_one_or_combat_icon_if_spacing_guild_influence_two"
    )
    # Imperium Ceremony: "Look at the top two Intrigue cards. Keep one and
    # put the other back on top".
    PEEK_TWO_INTRIGUE_KEEP_ONE = "peek_two_intrigue_keep_one"
    # Interstellar Conspiracy (Graft): "1 spice —AND— If grafted with an
    # Emperor or Spacing Guild card: Influence of your choice".
    GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD = (
        "gain_spice_and_chosen_influence_if_grafted_with_emperor_or_guild"
    )
    # Tleilaxu Master: "[one marker]: you may acquire a card costing 6 or
    # less. [two markers]: put that card in your hand".
    MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER = (
        "may_acquire_card_up_to_six_if_one_marker"
    )
    # Tleilaxu Surgeon: "2 specimens -> Tleilaxu Tleilaxu".
    MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU = "may_pay_two_specimens_for_two_tleilaxu"
    # Tleilaxu deck (card faces). Industrial Espionage: "Draw a card. If
    # grafted: Research and a specimen".
    DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED = (
        "draw_one_and_research_and_specimen_if_grafted"
    )
    # Scientific Breakthrough: "Research. [two genetic markers]: trash this
    # card -> 1 Victory Point".
    RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS = (
        "research_and_may_trash_self_for_vp_if_two_markers"
    )
    # Guild Impersonator (Graft): "If you gained spice this turn: Spacing
    # Guild Influence".
    GAIN_SPACING_GUILD_INFLUENCE_IF_GAINED_SPICE_THIS_TURN = (
        "gain_spacing_guild_influence_if_gained_spice_this_turn"
    )
    # Slig Farmer (Graft): "1 Solari per Agent icon on the other grafted
    # card. 5 Solari -> Tleilaxu".
    GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU = (
        "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu"
    )
    # Stitched Horror (Graft): "Choose two: water, troop, trash, Tleilaxu".
    CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU = (
        "choose_two_of_water_troop_trash_tleilaxu"
    )
    # Beguiling Pheromones (Graft): "If you sent your Agent to a Faction
    # board space this turn: trash a grafted card -> 1 Influence with that
    # Faction".
    MAY_TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE = (
        "may_trash_grafted_card_for_visited_faction_influence"
    )
    # Piter, Genius Advisor (promo): "Lose a troop -> draw two cards and
    # Research".
    MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH = (
        "may_lose_troop_to_draw_two_and_research"
    )
    # Chairdog (Graft): "At the start of your Reveal turn, return the other
    # grafted card from play to your hand".
    RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START = (
        "return_other_grafted_to_hand_at_reveal_start"
    )


class PersonalCardTrashEffect(StrEnum):
    """Typed effects triggered when a personal card is trashed."""

    DRAW_INTRIGUE_CARD = "draw_intrigue_card"
    # Eliminate Allies (Bloodlines): "When this card is trashed: 2 troops".
    RECRUIT_TWO_TROOPS = "recruit_two_troops"
    # Sardaukar Standard (Bloodlines): "When this card is trashed: acquire
    # and recruit the Sardaukar Commander in the bank".
    ACQUIRE_BANK_COMMANDER = "acquire_bank_commander"
    # Replacement Eyes (Immortality): "When this card is trashed: Tleilaxu".
    ADVANCE_TLEILAXU = "advance_tleilaxu"


class PersonalCardIconCondition(StrEnum):
    """A printed condition under which greyed Agent icons become real.

    Long Reach: "If you have another Bene Gesserit card in play, this has
    [Landsraad], [City] and [Spice Trade]"; Show of Strength: "If you have
    more deployed troops than each opponent, this has [Landsraad] and
    [Spice Trade]" [card faces]. Judged when the card is played.
    """

    BENE_GESSERIT_BOND = "bene_gesserit_bond"
    MORE_DEPLOYED_TROOPS_THAN_EACH_OPPONENT = (
        "more_deployed_troops_than_each_opponent"
    )


class PersonalCardTurnStartEffect(StrEnum):
    """Printed alternatives a card offers at the start of its owner's turn."""

    # Litany Against Fear (Bloodlines): "At the start of your turn: put this
    # card into play -> draw a card and pass your turn."
    PLAY_TO_DRAW_AND_PASS = "play_to_draw_and_pass"


class PersonalCardDiscardEffect(StrEnum):
    """Typed effects triggered when a personal card is discarded from hand."""

    GAIN_TWO_SPICE = "gain_two_spice"
    # Corrupt Bureaucrat (Bloodlines): "When this card is discarded: 3 Solari".
    GAIN_THREE_SOLARI = "gain_three_solari"


class PersonalCardAcquisitionEffect(StrEnum):
    """Typed effects resolved immediately after acquiring an Imperium card."""

    DRAW_INTRIGUE_CARD = "draw_intrigue_card"
    GAIN_TWO_SOLARI = "gain_two_solari"
    PLACE_SPY = "place_spy"
    GAIN_SPACING_GUILD_INFLUENCE = "gain_spacing_guild_influence"
    TAKE_CONTRACT = "take_contract"
    RECRUIT_ONE_TROOP = "recruit_one_troop"
    # Imperial Throneship (Bloodlines): one Emperor Influence on acquisition.
    GAIN_EMPEROR_INFLUENCE = "gain_emperor_influence"
    # Possible Futures (Bloodlines): one water on acquisition.
    GAIN_ONE_WATER = "gain_one_water"
    # Immortality acquire boxes: Spiritual Fervor researches, Subject X-137
    # advances the Tleilaxu token, Lisan al Gaib gains a spice, Occupation
    # recruits three troops [card faces].
    RESEARCH = "research"
    ADVANCE_TLEILAXU = "advance_tleilaxu"
    GAIN_ONE_SPICE = "gain_one_spice"
    RECRUIT_THREE_TROOPS = "recruit_three_troops"


class PersonalCardRevealChoiceEffect(StrEnum):
    """Reveal effects that require a player-owned serial decision."""

    RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED = (
        "recall_spy_to_draw_intrigue_if_two_placed"
    )
    MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION = (
        "may_recall_two_spies_for_two_persuasion"
    )
    PLACE_SPY = "place_spy"
    PLACE_SPY_OR_GAIN_TWO_STRENGTH = "place_spy_or_gain_two_strength"
    MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE = (
        "may_lose_influence_to_gain_influence"
    )
    MAY_PAY_THREE_SPICE_FOR_INFLUENCE = "may_pay_three_spice_for_influence"
    MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH = (
        "may_trash_other_emperor_for_three_strength"
    )
    MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH = (
        "may_retreat_two_troops_for_four_strength"
    )
    GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL = (
        "gain_five_solari_or_take_high_council"
    )
    MAY_PAY_WATER_FOR_SANDWORM = "may_pay_water_for_sandworm"
    KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS = (
        "keep_spice_or_trash_self_for_vp_if_four_contracts"
    )
    # Bloodlines. "Command (6+)" choices open only in a Reveal turn that
    # generates six or more Persuasion [Bloodlines pp. 5, 12].
    COMMAND_MAY_TRASH_CARD = "command_may_trash_card"
    COMMAND_PLACE_SPY = "command_place_spy"
    COMMAND_GAIN_CHOSEN_INFLUENCE = "command_gain_chosen_influence"
    MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION = (
        "may_retreat_two_troops_for_two_persuasion"
    )
    # Disruption Tactics: "Trash this card -> Combat icon".
    MAY_TRASH_SELF_FOR_COMBAT_ICON = "may_trash_self_for_combat_icon"
    # Arrakis Observer: "[recall a Spy] -> 3 swords".
    MAY_RECALL_SPY_FOR_THREE_STRENGTH = "may_recall_spy_for_three_strength"
    # Engineered Miracle: "Command: Trash this card -> Acquire a card from
    # the Imperium Row".
    COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD = (
        "command_may_trash_self_to_acquire_row_card"
    )
    # CHOAM Demands: "If you have completed four or more contracts: trash
    # this card -> one Influence with each Faction".
    MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS = (
        "may_trash_self_for_four_influence_if_four_contracts"
    )
    # Delivery Logistics: "1 Persuasion OR a contract".
    PERSUASION_OR_CONTRACT = "persuasion_or_contract"
    # Ixian Ambassador (Tech Module): "If you have two or more Tech tiles:
    # gain 1 Influence of your choice".
    GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH = "gain_chosen_influence_if_two_tech"
    # Immortality (card faces). For Humanity: "Bene Gesserit Alliance: lose
    # one Influence -> 1 Victory Point".
    MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE = (
        "may_lose_influence_for_vp_if_bene_gesserit_alliance"
    )
    # Shadout Mapes: "You may deploy or retreat one troop".
    MAY_DEPLOY_OR_RETREAT_ONE_TROOP = "may_deploy_or_retreat_one_troop"
    # Tleilaxu Surgeon: "Lose two troops -> two specimens".
    MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS = "may_lose_two_troops_for_two_specimens"


# Choice effects added by Bloodlines: their action templates join only the
# option's catalogs so the retail catalogs keep their size.
BLOODLINES_REVEAL_CHOICE_EFFECTS: frozenset[PersonalCardRevealChoiceEffect] = frozenset(
    {
        PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD,
        PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY,
        PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE,
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON,
        PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH,
        PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS,
        PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT,
        PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH,
    }
)

# Choice effects added by Immortality; like the Bloodlines set their
# templates join only the option's catalogs.
IMMORTALITY_REVEAL_CHOICE_EFFECTS: frozenset[PersonalCardRevealChoiceEffect] = (
    frozenset(
        {
            PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE,
            PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP,
            PersonalCardRevealChoiceEffect.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS,
        }
    )
)


class PersonalCardRevealAcquisitionEffect(StrEnum):
    """Typed effects triggered by an acquisition during the current Reveal."""

    GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW = (
        "gain_influence_for_each_spied_faction_on_spice_must_flow"
    )


@dataclass(frozen=True, slots=True)
class PersonalCardRevealEffect:
    """Automatic public gains produced when a personal card is revealed."""

    solari: int = 0
    spice: int = 0
    water: int = 0
    persuasion: int = 0
    recruit_troops: int = 0
    strength: int = 0
    strength_per_other_sword_card: int = 0
    draw_intrigue: int = 0
    influence: int = 0
    influence_faction: PersonalCardBond | None = None
    required_faction_bond: PersonalCardBond | None = None
    requires_high_council: bool = False
    requires_swordmaster: bool = False
    minimum_spies_placed: int = 0
    requires_spying_on_maker_space: bool = False
    per_revealed_faction: PersonalCardBond | None = None
    persuasion_per_completed_contract: int = 0
    # Bloodlines conditions: a Sardaukar Commander in the Conflict (Quash
    # Rebellion), a garrison size (Imperial Throneship: "four or more
    # garrisoned units", troops and Commanders), and "Command (6+)": the
    # Reveal turn generates six or more Persuasion [Bloodlines pp. 5, 12].
    requires_commander_in_conflict: bool = False
    minimum_garrisoned_units: int = 0
    requires_command: bool = False
    # Bombast: "Command: 3 Solari and trash this card" — the card leaves
    # play when the effect pays out.
    trashes_self: bool = False
    # Holy War: "Fremen Bond: Combat icon" — deploy in this Reveal as though
    # at a Combat space [Bloodlines p. 5].
    grants_combat_icon: bool = False
    # Immortality: specimens generated from the supply [Immortality p. 8]
    # (Experimentation, Spiritual Fervor, Twisted Mentat, Usurp), and the
    # genetic markers a marked Reveal line needs [Immortality pp. 6, 16].
    specimens: int = 0
    minimum_genetic_markers: int = 0
    # Tleilaxu advances (Dissecting Kit) and Research icons (Tleilaxu
    # Master) printed in a Reveal box; owner-timed like the other gains.
    tleilaxu: int = 0
    research: int = 0

    def __post_init__(self) -> None:
        if self.required_faction_bond is not None and not isinstance(
            self.required_faction_bond,
            PersonalCardBond,
        ):
            raise TypeError("Faction Bond requirement must use PersonalCardBond")
        if self.per_revealed_faction is not None and not isinstance(
            self.per_revealed_faction,
            PersonalCardBond,
        ):
            raise TypeError("counted Reveal Faction must use PersonalCardBond")
        if (
            self.per_revealed_faction is not None
            and self.persuasion == 0
            and self.strength == 0
        ):
            raise ValueError("counted Reveal Faction requires Persuasion or strength")
        if self.influence_faction is not None and not isinstance(
            self.influence_faction,
            PersonalCardBond,
        ):
            raise TypeError("Reveal Influence Faction must use PersonalCardBond")
        if (self.influence == 0) != (self.influence_faction is None):
            raise ValueError("Reveal Influence amount and Faction must be paired")
        if (
            not isinstance(self.requires_high_council, bool)
            or not isinstance(self.requires_swordmaster, bool)
            or not isinstance(self.requires_spying_on_maker_space, bool)
        ):
            raise TypeError("Reveal state requirements must be booleans")
        if self.requires_swordmaster and not self.requires_high_council:
            raise ValueError("Swordmaster Reveal requirement also needs High Council")
        gains = (
            self.solari,
            self.spice,
            self.water,
            self.persuasion,
            self.recruit_troops,
            self.strength,
            self.strength_per_other_sword_card,
            self.draw_intrigue,
            self.influence,
            self.persuasion_per_completed_contract,
            self.specimens,
            self.tleilaxu,
            self.research,
        )
        if (
            min(
                (
                    *gains,
                    self.minimum_spies_placed,
                    self.minimum_garrisoned_units,
                    self.minimum_genetic_markers,
                )
            )
            < 0
        ):
            raise ValueError("personal-card Reveal gains must not be negative")
        if max(gains) == 0 and not self.grants_combat_icon:
            raise ValueError("personal-card Reveal effect must gain something")
        if self.requires_command and self.persuasion:
            # The Persuasion total that satisfies Command must not depend on
            # the Command reward itself.
            raise ValueError("a Command effect cannot grant Persuasion")


class BattleIcon(StrEnum):
    """Icons paired by Objective and won Conflict cards."""

    CRYSKNIFE = "crysknife"
    DESERT_MOUSE = "desert_mouse"
    ORNITHOPTER = "ornithopter"
    WILD = "wild"


class ConflictTier(IntEnum):
    """The three Conflict deck backs."""

    ONE = 1
    TWO = 2
    THREE = 3
