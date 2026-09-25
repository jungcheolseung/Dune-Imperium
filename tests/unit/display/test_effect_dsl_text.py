"""Tests for the Intrigue effect DSL English/Korean text renderers."""

import sys
from pathlib import Path

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    CompletedContractsAtLeast,
    EffectSection,
    GainCombatStrength,
    GainResources,
    InfluenceAtLeast,
    IntrigueTiming,
    LoseInfluence,
    OnRevealAcquisitionThisRound,
    OnUnitsDeployedInTurn,
    PayResources,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS, INTRIGUE_CARDS_BY_ID
from dune_imperium.display.effect_dsl_text import (
    condition_text,
    cost_text,
    intrigue_card_text,
    option_text,
    reward_text,
    section_text,
    trigger_text,
)
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    cost_text_ko,
    intrigue_card_text_ko,
    option_text_ko,
    reward_text_ko,
    section_text_ko,
    trigger_text_ko,
)

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_no_summon_for_sandworm,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)


def test_condition_text_renders_a_faction_influence_threshold() -> None:
    assert (
        condition_text(InfluenceAtLeast(Faction.EMPEROR, 3))
        == "you have 3 or more Emperor Influence"
    )


def test_condition_text_renders_completed_contracts() -> None:
    assert (
        condition_text(CompletedContractsAtLeast(2))
        == "you have completed 2 or more Contracts"
    )


def test_cost_text_renders_pay_resources() -> None:
    assert cost_text(PayResources(spice=2)) == "Pay 2 spice"


def test_cost_text_renders_lose_influence() -> None:
    assert cost_text(LoseInfluence(1)) == "Lose 1 Influence"


def test_reward_text_renders_gain_resources() -> None:
    assert reward_text(GainResources(solari=4)) == "Gain 4 solari"


def test_reward_text_renders_combat_strength_as_swords() -> None:
    assert reward_text(GainCombatStrength(1)) == "Gain 1 sword"
    assert reward_text(GainCombatStrength(4)) == "Gain 4 swords"


def test_trigger_text_renders_on_reveal_acquisition() -> None:
    assert (
        trigger_text(OnRevealAcquisitionThisRound())
        == "Whenever you acquire a card during your Reveal turn this round"
    )


def test_trigger_text_renders_on_units_deployed() -> None:
    assert (
        trigger_text(OnUnitsDeployedInTurn(3))
        == "When you deploy 3 or more units in a turn"
    )


def test_section_text_joins_cost_and_reward_with_an_arrow() -> None:
    section = EffectSection(
        costs=(LoseInfluence(1),),
        rewards=(GainResources(solari=4),),
    )

    assert section_text(section) == "Lose 1 Influence → Gain 4 solari"


def test_section_text_prefixes_a_condition() -> None:
    section = EffectSection(
        condition=CompletedContractsAtLeast(2),
        rewards=(GainCombatStrength(4),),
    )

    assert (
        section_text(section)
        == "If you have completed 2 or more Contracts: Gain 4 swords"
    )


def test_option_text_backed_by_choam_plot_option() -> None:
    entry = INTRIGUE_CARDS_BY_ID["backed_by_choam"]

    assert option_text(entry.options[0]) == "Plot — Lose 1 Influence → Gain 4 solari"
    assert entry.options[0].timing is IntrigueTiming.PLOT
    assert option_text(entry.options[1]) == (
        "Combat — If you have completed 2 or more Contracts: Gain 4 swords"
    )


def test_option_text_renders_a_reveal_acquisition_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["call_to_arms"]

    assert option_text(entry.options[0]) == (
        "Plot — Whenever you acquire a card during your Reveal turn this round: "
        "Recruit 1 troop"
    )


def test_option_text_renders_a_units_deployed_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["distraction"]

    assert option_text(entry.options[0]) == (
        "Plot — When you deploy 3 or more units in a turn: "
        "Place a Spy (sharing another player's Spy's post)"
    )


def test_option_text_joins_multiple_sections_with_a_semicolon() -> None:
    entry = INTRIGUE_CARDS_BY_ID["depart_for_arrakis"]

    assert option_text(entry.options[0]) == (
        "Plot — Pay 2 spice → Recruit 3 troops; "
        "If you have 3 or more Spacing Guild Influence: Draw 1 card"
    )


def test_intrigue_card_text_covers_every_card_with_non_empty_lines() -> None:
    for entry in INTRIGUE_CARDS:
        if not entry.play_data_complete:
            # Bloodlines cards awaiting transcription (M12) render no options.
            continue
        lines = intrigue_card_text(entry)

        assert lines, f"{entry.card.card_id} produced no option lines"
        for line in lines:
            assert isinstance(line, str)
            assert line.strip()


def test_intrigue_card_text_renders_every_option_of_every_card() -> None:
    for entry in INTRIGUE_CARDS:
        assert len(intrigue_card_text(entry)) == len(entry.options)


# ---------- Korean (``*_ko``) ----------


def test_condition_text_ko_renders_a_faction_influence_threshold() -> None:
    assert (
        condition_text_ko(InfluenceAtLeast(Faction.EMPEROR, 3))
        == "{influence_emperor} 3 이상이면"
    )


def test_condition_text_ko_renders_completed_contracts_with_a_native_numeral() -> None:
    """"당신이 계약을 둘 이상 완수했다면:" (Backed by CHOAM) / "…넷 이상…"
    (CHOAM Profits) — two independent Korean card scans, both native
    numerals, never a digit, for this exact condition."""

    assert (
        condition_text_ko(CompletedContractsAtLeast(2))
        == "당신이 {contract}을 둘 이상 완수했다면"
    )
    assert (
        condition_text_ko(CompletedContractsAtLeast(4))
        == "당신이 {contract}을 넷 이상 완수했다면"
    )


def test_cost_text_ko_renders_pay_resources() -> None:
    assert cost_text_ko(PayResources(spice=2)) == "{spice:2} 지불"


def test_cost_text_ko_renders_lose_influence() -> None:
    assert cost_text_ko(LoseInfluence(1)) == "{influence_lose:1}"


def test_reward_text_ko_renders_gain_resources() -> None:
    assert reward_text_ko(GainResources(solari=4)) == "{solari:4}"


def test_reward_text_ko_renders_combat_strength_as_swords() -> None:
    assert reward_text_ko(GainCombatStrength(1)) == "{sword:1}"
    assert reward_text_ko(GainCombatStrength(4)) == "{sword:4}"


def test_trigger_text_ko_renders_on_reveal_acquisition() -> None:
    assert (
        trigger_text_ko(OnRevealAcquisitionThisRound())
        == "이번 라운드에 자기 {reveal_turn} 동안 카드를 획득할 때마다"
    )


def test_trigger_text_ko_renders_on_units_deployed() -> None:
    assert (
        trigger_text_ko(OnUnitsDeployedInTurn(3)) == "한 차례에 부대를 3 이상 배치할 때"
    )


def test_section_text_ko_joins_cost_and_reward_with_the_arrow_term() -> None:
    section = EffectSection(
        costs=(LoseInfluence(1),),
        rewards=(GainResources(solari=4),),
    )

    assert section_text_ko(section) == "{influence_lose:1} {arrow_right} {solari:4}"


def test_section_text_ko_prefixes_a_condition_with_a_colon_not_if() -> None:
    section = EffectSection(
        condition=CompletedContractsAtLeast(2),
        rewards=(GainCombatStrength(4),),
    )

    assert section_text_ko(section) == (
        "당신이 {contract}을 둘 이상 완수했다면: {sword:4}"
    )


def test_option_text_ko_backed_by_choam_plot_option() -> None:
    """Matches the Korean card scans of Backed by CHOAM (`[KO card: Backed
    by CHOAM]`): "초암 공사의 후원" — 4 solari for 1 Influence, then 4 swords
    if 2+ Contracts completed, timing footer "음모 / 전투"."""

    entry = INTRIGUE_CARDS_BY_ID["backed_by_choam"]

    assert option_text_ko(entry.options[0]) == (
        "음모 — {influence_lose:1} {arrow_right} {solari:4}"
    )
    assert option_text_ko(entry.options[1]) == (
        "전투 — 당신이 {contract}을 둘 이상 완수했다면: {sword:4}"
    )


def test_option_text_ko_renders_a_reveal_acquisition_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["call_to_arms"]

    assert option_text_ko(entry.options[0]) == (
        "음모 — 이번 라운드에 자기 {reveal_turn} 동안 카드를 획득할 때마다: {troop:1}"
    )


def test_option_text_ko_renders_a_units_deployed_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["distraction"]

    assert option_text_ko(entry.options[0]) == (
        "음모 — 한 차례에 부대를 3 이상 배치할 때: "
        "{spy} 배치 (다른 플레이어의 {spy}와 관측소 공유 가능)"
    )


def test_option_text_ko_joins_multiple_sections_with_a_semicolon() -> None:
    entry = INTRIGUE_CARDS_BY_ID["depart_for_arrakis"]

    assert option_text_ko(entry.options[0]) == (
        "음모 — {spice:2} 지불 {arrow_right} {troop:3}; "
        "{influence_spacing_guild} 3 이상이면: {draw:1}"
    )


def test_option_text_ko_navigation_card_3_matches_its_korean_print() -> None:
    """"이 카드가 운항 구획 4에 놓여 있었다면: 이제부터 매 라운드의 자기 공개
    차례 동안 [1]." — Navigation Card 3's own Korean scan (`[KO card:
    Navigation Card 3]`)."""

    entry = INTRIGUE_CARDS_BY_ID["navigation_card_3"]

    assert option_text_ko(entry.options[0]) == (
        "음모 — {solari:2}; 이 카드가 운항 구획 4에 놓여 있었다면: "
        "이제부터 매 라운드의 자기 {reveal_turn} 동안 {persuasion:1}"
    )


def test_option_text_ko_navigation_card_4_resolves_the_korean_card_name() -> None:
    """"스파이스는 흘러야 한다 획득." — Navigation Card 4's own Korean scan
    (`[KO card: Navigation Card 4]`)."""

    entry = INTRIGUE_CARDS_BY_ID["navigation_card_4"]

    assert option_text_ko(entry.options[1]) == (
        "음모 — 이 카드가 운항 구획 1에 놓여 있었다면: "
        "{water:1} 지불 {arrow_right} 스파이스는 흘러야 한다 {acquire}"
    )


def test_option_text_ko_navigation_card_8_matches_its_korean_print() -> None:
    """"우주 항행 길드에 대한 영향력이 2에 도달한 결과로 이 카드를
    플레이했다면:" — Navigation Card 8's own Korean scan (`[KO card:
    Navigation Card 8]`)."""

    entry = INTRIGUE_CARDS_BY_ID["navigation_card_8"]

    assert option_text_ko(entry.options[0]) == (
        "음모 — {water:1}; 우주 항행 길드에 대한 {influence_any:2}에 도달한 "
        "결과로 이 카드를 플레이했다면: {spice:1}"
    )


def test_option_text_ko_emperors_invitation_matches_its_korean_print() -> None:
    """"이번 차례에 당신이 플레이하는 카드는 [Agent icon] 아이콘 보유." —
    Emperor's Invitation's own Korean scan (`[KO card: Emperor's
    Invitation]`)."""

    entry = INTRIGUE_CARDS_BY_ID["emperor_s_invitation"]

    assert option_text_ko(entry.options[1]) == (
        "음모 — 이번 차례에 당신이 플레이하는 카드는 황제 아이콘 보유"
    )


def test_option_text_ko_choam_profits_matches_its_korean_print() -> None:
    """"당신이 계약을 넷 이상 완수했다면:" — CHOAM Profits' own Korean scan
    (`[KO card: CHOAM Profits]`), Endgame timing."""

    entry = INTRIGUE_CARDS_BY_ID["choam_profits"]

    assert option_text_ko(entry.options[0]) == (
        "종료 단계 — 당신이 {contract}을 넷 이상 완수했다면: {victory_point:1}"
    )


def test_intrigue_card_text_ko_renders_every_option_of_every_card() -> None:
    for entry in INTRIGUE_CARDS:
        assert len(intrigue_card_text_ko(entry)) == len(entry.options)


def test_intrigue_card_text_ko_matches_the_english_line_count() -> None:
    """``intrigue[id].text_ko`` must align index-for-index with ``text`` —
    the client resolves a ``play_intrigue``/``play_navigation`` option's
    Korean line by the same numeric index (``core.js``
    ``intrigueOptionBody()``)."""

    for entry in INTRIGUE_CARDS:
        assert len(intrigue_card_text_ko(entry)) == len(intrigue_card_text(entry))


def test_every_intrigue_option_ko_line_uses_the_em_dash_timing_separator() -> None:
    """``core.js`` ``intrigueOptionBody()`` strips the timing prefix by
    finding " — "; every Korean line must carry it too."""

    for entry in INTRIGUE_CARDS:
        for line in intrigue_card_text_ko(entry):
            assert " — " in line, (entry.card.card_id, line)


def test_every_intrigue_option_ko_line_is_valid_korean_text() -> None:
    terms = terms_keys()
    for entry in INTRIGUE_CARDS:
        en_lines = intrigue_card_text(entry)
        ko_lines = intrigue_card_text_ko(entry)
        for en_line, ko_line in zip(en_lines, ko_lines, strict=True):
            assert isinstance(ko_line, str) and ko_line.strip(), entry.card.card_id
            assert_placeholders_are_terms(ko_line, terms)
            assert_no_stray_latin(ko_line)
            assert_trash_and_discard_match(en_line, ko_line)
            assert_no_summon_for_sandworm(en_line, ko_line)
