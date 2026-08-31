"""Tests for personal_card_text() display lines."""

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


def test_covers_all_54_imperium_7_starting_2_reserve_entries() -> None:
    assert len(IMPERIUM_CARDS) == 54
    assert len(STARTING_DECK) == 7
    assert len(RESERVE_STACKS) == 2
    assert len(_ALL_ENTRIES) == 63


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

    assert personal_card_text(entry) == [
        "Agent: Place a Spy (Emperor, Bene Gesserit, or Spacing Guild Spy)",
        "Reveal: Gain 1 solari",
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

    assert personal_card_text(entry) == ["On acquire: Gain 1 VP"]


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
    assert all(entry.play_data_complete for entry in IMPERIUM_CARDS)
