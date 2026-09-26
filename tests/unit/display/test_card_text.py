"""Tests for personal_card_text() display lines."""

from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    IMPERIUM_CARDS_BY_ID,
    ImperiumCardEntry,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS, RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.starting_cards import (
    STARTING_CARDS_BY_ID,
    STARTING_DECK,
)
from dune_imperium.display.cards import personal_card_text

_ALL_ENTRIES = (*IMPERIUM_CARDS, *STARTING_DECK, *RESERVE_STACKS)


def test_covers_all_57_imperium_7_starting_2_reserve_entries() -> None:
    # Plus the 26 Bloodlines Imperium identities (M12), the Bloodlines
    # promo Ruthless Leadership, and the 25 Immortality identities.
    assert len(IMPERIUM_CARDS) == 57 + 26 + 1 + 25
    assert len(STARTING_DECK) == 7
    assert len(RESERVE_STACKS) == 2
    assert len(_ALL_ENTRIES) == 66 + 26 + 1 + 25


def test_every_entry_produces_a_non_empty_list() -> None:
    for entry in _ALL_ENTRIES:
        lines = personal_card_text(entry)

        assert lines, f"{entry.card.name} produced no display lines"
        assert all(isinstance(line, str) and line for line in lines)


def test_bene_gesserit_operative_golden() -> None:
    entry = IMPERIUM_CARDS_BY_ID["bene_gesserit_operative"]

    assert personal_card_text(entry) == [
        "Agent: Place a Spy",
        "Reveal: If you have placed 2 or more Spies: +2 Persuasion",
    ]


def test_reliable_informant_lists_its_spy_target_factions() -> None:
    entry = IMPERIUM_CARDS_BY_ID["reliable_informant"]

    # Re-read from the card face 2026-09-26: the third target icon is the
    # blue Fremen sietch badge, not the red Spacing Guild infinity symbol.
    assert personal_card_text(entry) == [
        "Agent: Place a Spy (Emperor, Bene Gesserit, or Fremen Spy)",
        "Reveal: Gain 1 solari",
    ]


def test_double_agent_spy_is_limited_to_the_visited_space() -> None:
    # "[Spy] spying on the board space you sent an Agent to this turn. You
    # may place this Spy on the same observation post as another player's
    # Spy." [Double Agent card]
    entry = IMPERIUM_CARDS_BY_ID["double_agent"]

    assert personal_card_text(entry)[0] == (
        "Agent: Place a Spy on a post connected to the space you sent an Agent "
        "to this turn (may share a post with another player's Spy)"
    )


def test_beguiling_pheromones_trash_is_not_optional() -> None:
    # "If you sent an Agent to a Faction board space this turn, trash one of
    # the grafted cards and gain an additional Influence with that Faction."
    # [Beguiling Pheromones card]: no "may" and no arrow [FAQ p. 3].
    entry = TLEILAXU_CARDS_BY_ID["beguiling_pheromones"]

    assert personal_card_text(entry)[0] == (
        "Agent: If you sent an Agent to a Faction space this turn: "
        "Trash one of the grafted cards, Gain 1 Influence with that Faction"
    )


def test_ghola_names_its_borrowed_agent_box() -> None:
    # "This card has the same Agent box as the other grafted card." [Ghola
    # card]. Its own data has no Agent effect (the rules borrow the
    # partner's at play time), so the text fell back to "(no additional
    # ability)" -- the opposite of what the card does.
    entry = TLEILAXU_CARDS_BY_ID["ghola"]

    assert personal_card_text(entry) == [
        "Agent: This card has the same Agent box as the other grafted card"
    ]


def test_long_reach_names_the_condition_on_its_greyed_icons() -> None:
    # "If you have another Bene Gesserit card in play, this has [Landsraad],
    # [City], and [Spice Trade]." [Long Reach card]: the icons are printed
    # greyed, so the text must say they need the condition.
    entry = IMPERIUM_CARDS_BY_ID["long_reach"]

    assert personal_card_text(entry)[:2] == [
        "If you have another Bene Gesserit card in play, this has Landsraad, "
        "City, and Spice Trade",
        "Agent: Choose two Factions: Gain 1 Influence with each",
    ]


def test_show_of_strength_names_the_condition_on_its_greyed_icons() -> None:
    # "If you have more deployed troops than each opponent, this has
    # [Landsraad] and [Spice Trade]." [Show of Strength card]
    entry = IMPERIUM_CARDS_BY_ID["show_of_strength"]

    assert personal_card_text(entry) == [
        "If you have more deployed troops than each opponent, this has "
        "Landsraad and Spice Trade",
        "Agent: Draw 2 cards",
    ]


def test_sardaukar_soldier_trash_trigger_only() -> None:
    entry = IMPERIUM_CARDS_BY_ID["sardaukar_soldier"]

    assert personal_card_text(entry) == ["When trashed: Draw 1 Intrigue card"]


def test_spacing_guilds_favor_agent_reveal_and_discard_lines() -> None:
    entry = IMPERIUM_CARDS_BY_ID["spacing_guild_s_favor"]

    assert personal_card_text(entry) == [
        "Agent: Draw 1 card",
        "Reveal: You may pay 3 spice → Gain 1 Influence with a chosen Faction",
        "On discard: Gain 2 spice",
    ]


def test_guild_spy_reveal_acquisition_line_names_the_spice_must_flow() -> None:
    entry = IMPERIUM_CARDS_BY_ID["guild_spy"]

    assert personal_card_text(entry) == [
        "Agent: You may discard a card → Draw 1 card "
        "(also Draw 1 Intrigue card if the discarded card has "
        "Spacing Guild affiliation)",
        "On acquire: Place a Spy",
        "Reveal, if you acquire The Spice Must Flow: "
        "Gain 1 Influence with each Faction you are spying on",
    ]


def test_undercover_asset_ignores_influence_requirements_passive() -> None:
    entry = IMPERIUM_CARDS_BY_ID["undercover_asset"]

    assert personal_card_text(entry) == [
        "Ignores Influence requirements",
        "Reveal: Choose one: Place a Spy / +2 swords",
    ]


def test_sardaukar_coordination_recruited_troop_deployment_passive() -> None:
    entry = IMPERIUM_CARDS_BY_ID["sardaukar_coordination"]

    assert personal_card_text(entry) == [
        "Recruited troops may be deployed to the Conflict",
        "Reveal: +1 sword per revealed Emperor card",
    ]


def test_truthtrance_has_no_dynamic_effects() -> None:
    # Truthtrance has no Agent-box effect and no Reveal effect beyond its
    # printed (not duplicated here) Persuasion value.
    entry = IMPERIUM_CARDS_BY_ID["truthtrance"]

    assert personal_card_text(entry) == ["(no additional ability)"]


def test_convincing_argument_starting_card_has_no_dynamic_effects() -> None:
    entry = STARTING_CARDS_BY_ID["convincing_argument"]

    assert personal_card_text(entry) == ["(no additional ability)"]


def test_signet_ring_starting_card_agent_line() -> None:
    entry = STARTING_CARDS_BY_ID["signet_ring"]

    assert personal_card_text(entry) == ["Agent: Your Leader's Signet Ring ability"]


def test_prepare_the_way_reserve_agent_line() -> None:
    entry = RESERVE_STACKS_BY_ID["prepare_the_way"]

    assert personal_card_text(entry) == [
        "Agent: If you have 2 or more Bene Gesserit Influence: Draw 1 card",
    ]


def test_the_spice_must_flow_reserve_acquisition_vp() -> None:
    entry = RESERVE_STACKS_BY_ID["the_spice_must_flow"]

    # The Reveal box prints an orange spice hexagon "1" [Main p. 20] (icon
    # guide: spice, not a sword), not the previously transcribed sword.
    assert personal_card_text(entry) == [
        "Reveal: Gain 1 spice",
        "On acquire: Gain 1 VP",
    ]


def test_tread_in_darkness_bene_gesserit_bond_has_no_arrow() -> None:
    # Card face: two icons side by side with no arrow (OQ-058); the draw
    # happens even if the trash is declined [Tread in Darkness card face].
    entry = IMPERIUM_CARDS_BY_ID["tread_in_darkness"]

    assert personal_card_text(entry) == [
        "Agent: If Bene Gesserit Bond: You may trash a card, Draw 1 card"
    ]


def test_delivery_logistics_lists_its_contract_agent_icons() -> None:
    # Card face Agent box: "This has the Agent icons shown on all your
    # incomplete contracts." [Delivery Logistics card face].
    entry = IMPERIUM_CARDS_BY_ID["delivery_logistics"]

    assert personal_card_text(entry) == [
        "Has the Agent icons shown on all your incomplete contracts",
        "Reveal: Choose one: 1 Persuasion / Contract",
    ]


def test_litany_against_fear_renders_its_turn_start_box() -> None:
    # Red box: "At the start of your turn: Put this card into play -> draw a
    # card and pass your turn." [Litany Against Fear card face].
    entry = IMPERIUM_CARDS_BY_ID["litany_against_fear"]

    assert personal_card_text(entry) == [
        "At the start of your turn: Put this card into play → "
        "Draw 1 card and pass your turn"
    ]
    assert "(no additional ability)" not in personal_card_text(entry)


def test_blank_slate_renders_its_grafted_agent_icons() -> None:
    # Agent box: "If grafted: This has [Emperor], [Spacing Guild], [Bene
    # Gesserit], and [Fremen]." [Blank Slate card face].
    entry = IMPERIUM_CARDS_BY_ID["blank_slate"]

    lines = personal_card_text(entry)
    assert lines != ["(no additional ability)"]
    assert lines == [
        "If grafted: This has Emperor, Spacing Guild, Bene Gesserit, "
        "and Fremen Agent icons"
    ]


def test_usurp_renders_its_graft_box() -> None:
    # GRAFT box: "You may graft this to a card in the Imperium Row without
    # acquiring it. If you do, trash that card at the end of your turn."
    # [Usurp card face].
    entry = TLEILAXU_CARDS_BY_ID["usurp"]

    assert personal_card_text(entry) == [
        "Graft: You may graft this to a card in the Imperium Row without "
        "acquiring it. If you do, trash that card at the end of your turn",
        "Reveal: Generate 1 specimen",
    ]


def test_untranscribed_imperium_card_reports_missing_play_data() -> None:
    # No current IMPERIUM_CARDS entry has play_data_complete=False (verified
    # by test_every_entry_produces_a_non_empty_list finding real text for
    # all 54), so this exercises the branch with a constructed stand-in.
    sources = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3,)),)
    untranscribed = ImperiumCardEntry(
        card=CardDefinition("test_untranscribed", "Test Untranscribed", sources),
    )

    assert personal_card_text(untranscribed) == ["(play data not transcribed)"]


def test_no_imperium_card_currently_has_incomplete_play_data() -> None:
    # Bloodlines cards are transcribed slice by slice (M12) and stay out of
    # the deck until complete; every Uprising card is complete.
    assert all(
        entry.play_data_complete
        for entry in IMPERIUM_CARDS
        if not entry.bloodlines_only and not entry.immortality_only
    )
