"""Tests for personal_card_text() display lines."""

import sys
from pathlib import Path

from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    TLEILAXU_CARDS_BY_ID,
)
from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    IMPERIUM_CARDS_BY_ID,
    ImperiumCardEntry,
)
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
from dune_imperium.content.uprising.reserve import RESERVE_STACKS, RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.starting_cards import (
    STARTING_CARDS_BY_ID,
    STARTING_DECK,
)
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)

_ALL_ENTRIES = (*IMPERIUM_CARDS, *STARTING_DECK, *RESERVE_STACKS)

# Adds the Tleilaxu deck and Reclaimed Forces (personal_card_text_ko's own
# scope, Step K2, also covers those) on top of _ALL_ENTRIES above, which
# several existing English tests size-check against the Imperium/starting/
# Reserve-only 66 + 26 + 1 + 25 total and must not change.
_ALL_ENTRIES_WITH_TLEILAXU: tuple[PersonalCardDefinition, ...] = (
    *_ALL_ENTRIES,
    *TLEILAXU_CARDS_BY_ID.values(),
    RECLAIMED_FORCES,
)


def test_covers_all_57_imperium_7_starting_2_reserve_entries() -> None:
    # Plus the 26 Bloodlines Imperium identities (M12), the Bloodlines
    # promo Ruthless Leadership, and the 25 Immortality identities.
    assert len(IMPERIUM_CARDS) == 57 + 26 + 1 + 25
    assert len(STARTING_DECK) == 7
    assert len(RESERVE_STACKS) == 2
    assert len(_ALL_ENTRIES) == 66 + 26 + 1 + 25


def test_every_entry_produces_a_list_of_non_empty_lines() -> None:
    # A card with no dynamic effect data (no Agent/Reveal/acquire/discard/
    # trash line beyond its printed Persuasion/strength) produces an empty
    # list, not a made-up placeholder line (ITEM 8f, 2026-09-25); every
    # entry the list does produce must still be real, non-empty text.
    for entry in _ALL_ENTRIES:
        lines = personal_card_text(entry)

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

    assert personal_card_text(entry) == []


def test_convincing_argument_starting_card_has_no_dynamic_effects() -> None:
    entry = STARTING_CARDS_BY_ID["convincing_argument"]

    assert personal_card_text(entry) == []


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
    # by test_every_entry_produces_a_list_of_non_empty_lines finding real
    # text for all 54), so this exercises the branch with a constructed
    # stand-in.
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


# ---------- Korean (``personal_card_text_ko``) ----------


def test_every_entry_ko_has_the_same_line_count_as_english() -> None:
    # A line dropped or added only in one language would otherwise never
    # surface: the client pairs cards[id].text[i] with text_ko[i] by index
    # (server/catalog.py, render.js effectLine).
    for entry in _ALL_ENTRIES_WITH_TLEILAXU:
        en_lines = personal_card_text(entry)
        ko_lines = personal_card_text_ko(entry)

        assert len(ko_lines) == len(en_lines), entry.card.card_id


def test_every_entry_ko_produces_valid_non_empty_lines() -> None:
    terms = terms_keys()
    for entry in _ALL_ENTRIES_WITH_TLEILAXU:
        en_lines = personal_card_text(entry)
        ko_lines = personal_card_text_ko(entry)

        for en, ko in zip(en_lines, ko_lines, strict=True):
            assert isinstance(ko, str) and ko.strip(), entry.card.card_id
            assert_placeholders_are_terms(ko, terms)
            assert_no_stray_latin(ko)
            assert_trash_and_discard_match(en, ko)


def test_bene_gesserit_operative_ko_golden() -> None:
    entry = IMPERIUM_CARDS_BY_ID["bene_gesserit_operative"]

    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {spy} 배치",
        "공개 칸: {spy}를 2 이상 배치했다면: +{persuasion:2}",
    ]


def test_reliable_informant_ko_lists_its_spy_target_factions() -> None:
    entry = IMPERIUM_CARDS_BY_ID["reliable_informant"]

    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {spy} 배치 (황제, 베네 게세리트 또는 우주 항행 길드 {spy})",
        "공개 칸: {solari:1}",
    ]


def test_sardaukar_soldier_ko_trash_trigger_only() -> None:
    entry = IMPERIUM_CARDS_BY_ID["sardaukar_soldier"]

    assert personal_card_text_ko(entry) == ["폐기되면: {intrigue:1}"]


def test_spacing_guilds_favor_ko_agent_reveal_and_discard_lines() -> None:
    entry = IMPERIUM_CARDS_BY_ID["spacing_guild_s_favor"]

    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {draw:1}",
        "공개 칸: {spice:3} 지불 가능 {arrow_right} {influence_any:1} 선택",
        "버리면: {spice:2}",
    ]


def test_guild_spy_ko_reveal_acquisition_line_names_the_spice_must_flow() -> None:
    entry = IMPERIUM_CARDS_BY_ID["guild_spy"]
    spice_must_flow_ko = KOREAN_CARD_NAMES["cards"]["the_spice_must_flow"]

    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 카드 1장 {discard} 가능 {arrow_right} {draw:1} "
        "(버린 카드가 우주 항행 길드 카드이면 {intrigue:1} 추가)",
        "획득 시: {spy} 배치",
        f"공개, {spice_must_flow_ko} 획득 시: "
        "정탐 중인 각 팩션마다 {influence_any:1}",
    ]


def test_undercover_asset_ko_ignores_influence_requirements_passive() -> None:
    entry = IMPERIUM_CARDS_BY_ID["undercover_asset"]

    assert personal_card_text_ko(entry) == [
        "영향력 요구 조건 무시",
        "공개 칸: 하나 선택: {spy} 배치 / {sword:2}",
    ]


def test_sardaukar_coordination_ko_recruited_troop_deployment_passive() -> None:
    entry = IMPERIUM_CARDS_BY_ID["sardaukar_coordination"]

    assert personal_card_text_ko(entry) == [
        "소집한 {troop}을 {conflict}에 배치 가능",
        "공개 칸: +{sword:1} (공개한 황제 카드마다)",
    ]


def test_truthtrance_ko_has_no_dynamic_effects() -> None:
    entry = IMPERIUM_CARDS_BY_ID["truthtrance"]

    assert personal_card_text_ko(entry) == []


def test_convincing_argument_ko_starting_card_has_no_dynamic_effects() -> None:
    entry = STARTING_CARDS_BY_ID["convincing_argument"]

    assert personal_card_text_ko(entry) == []


def test_signet_ring_ko_starting_card_agent_line() -> None:
    entry = STARTING_CARDS_BY_ID["signet_ring"]

    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 당신 {leader}의 {signet_ring} 능력",
    ]


def test_prepare_the_way_ko_reserve_agent_line() -> None:
    entry = RESERVE_STACKS_BY_ID["prepare_the_way"]

    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {influence_bene_gesserit} 2 이상이면: {draw:1}",
    ]


def test_the_spice_must_flow_ko_reserve_acquisition_vp() -> None:
    entry = RESERVE_STACKS_BY_ID["the_spice_must_flow"]

    assert personal_card_text_ko(entry) == ["획득 시: {victory_point:1}"]


def test_untranscribed_imperium_card_ko_reports_missing_play_data() -> None:
    sources = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3,)),)
    untranscribed = ImperiumCardEntry(
        card=CardDefinition("test_untranscribed", "Test Untranscribed", sources),
    )

    assert personal_card_text_ko(untranscribed) == ["(플레이 데이터 없음)"]
