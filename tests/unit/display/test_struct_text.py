"""Tests for the standard Contract and Conflict English/Korean text renderers."""

import dataclasses
import sys
from pathlib import Path

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    ConflictDefinition,
    ConflictReward,
)
from dune_imperium.content.uprising.contracts import (
    CONTRACTS,
    CONTRACTS_BY_ID,
    ContractConditionKind,
    ContractReward,
)
from dune_imperium.display.structs import (
    _HANDLED_CONFLICT_REWARD_FIELDS,
    _HANDLED_CONTRACT_REWARD_FIELDS,
    _card_name,
    _card_name_ko,
    conflict_reward_text,
    conflict_reward_text_ko,
    conflict_rewards_texts,
    conflict_rewards_texts_ko,
    contract_condition_text,
    contract_condition_text_ko,
    contract_reward_text,
    contract_reward_text_ko,
)

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (neither tests/unit/ nor tests/unit/display/ has an __init__.py, so pytest
# never puts the repo root on sys.path for a test file here); reached by
# path instead, shared by every generator's test file this way.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)

# Every board space's English name may appear, untranslated, inside a
# Korean condition/reward line (glossary "공간 이름" row).
_SPACE_NAMES = frozenset(space.name for space in BOARD_SPACES_BY_ID.values())


def _allowed_latin_for_condition(
    kind: ContractConditionKind, target: str
) -> frozenset[str]:
    """English names a Korean condition line may legitimately still carry."""

    if kind is ContractConditionKind.BOARD_SPACE:
        return frozenset({BOARD_SPACES_BY_ID[target].name})
    if kind is ContractConditionKind.ACQUIRE_CARD:
        english, korean = _card_name(target), _card_name_ko(target)
        return frozenset({english}) if english == korean else frozenset()
    return frozenset()


def _conflict_by_id(card_id: str) -> ConflictDefinition:
    return next(conflict for conflict in CONFLICTS if conflict.card.card_id == card_id)


def test_every_contract_condition_and_reward_render_non_empty_text() -> None:
    for contract in CONTRACTS:
        condition = contract_condition_text(contract.condition)
        reward = contract_reward_text(contract.reward)

        assert isinstance(condition, str) and condition.strip()
        assert isinstance(reward, str) and reward.strip()


def test_every_conflict_with_rewards_renders_three_non_empty_lines() -> None:
    for conflict in CONFLICTS:
        lines = conflict_rewards_texts(conflict)

        if conflict.rewards is None:
            assert lines is None
            continue
        assert lines is not None
        assert len(lines) == 3
        for label, line in zip(("1st: ", "2nd: ", "3rd: "), lines, strict=True):
            assert line.startswith(label)
            assert line.strip() != label.strip()


def test_contract_condition_text_resolves_a_board_space_name() -> None:
    contract = CONTRACTS_BY_ID["arrakeen_i"]

    assert contract_condition_text(contract.condition) == "Send an Agent to Arrakeen"


def test_contract_condition_text_renders_harvest_spice() -> None:
    contract = CONTRACTS_BY_ID["harvest_3"]

    assert contract_condition_text(contract.condition) == (
        "Send an Agent to a Maker space and gain 3 or more spice that turn"
    )


def test_contract_condition_text_resolves_an_acquired_card_name() -> None:
    contract = CONTRACTS_BY_ID["acquire"]

    assert contract_condition_text(contract.condition) == "Acquire The Spice Must Flow"


def test_contract_condition_text_renders_immediate() -> None:
    contract = CONTRACTS_BY_ID["immediate"]

    assert (
        contract_condition_text(contract.condition) == "Complete immediately when taken"
    )


def test_contract_reward_text_renders_solari_and_faction_influence() -> None:
    contract = CONTRACTS_BY_ID["acquire"]

    assert contract_reward_text(contract.reward) == (
        "Gain 3 solari, Gain 1 Spacing Guild Influence"
    )


def test_contract_reward_text_renders_recall_agents() -> None:
    contract = CONTRACTS_BY_ID["sardaukar_ii"]

    assert contract_reward_text(contract.reward) == "Recall 1 Agent"


def test_conflict_reward_text_renders_a_control_space_row() -> None:
    conflict = _conflict_by_id("siege_of_arrakeen")
    assert conflict.rewards is not None

    assert conflict_reward_text(conflict.rewards[0]) == (
        "Gain 2 solari, Recruit 2 troops, Take control of Arrakeen"
    )


def test_conflict_reward_text_renders_an_optional_trade() -> None:
    conflict = _conflict_by_id("battle_for_arrakeen")
    assert conflict.rewards is not None

    assert conflict_reward_text(conflict.rewards[0]) == (
        "Gain 1 VP, Take control of Arrakeen, You may recall 2 Spies → Gain 1 VP"
    )


def test_conflict_reward_text_renders_choose_distinct_influence() -> None:
    conflict = _conflict_by_id("propaganda")
    assert conflict.rewards is not None

    assert conflict_reward_text(conflict.rewards[0]) == (
        "Gain 2 Influence (choose a different Faction each time)"
    )


def test_conflict_rewards_texts_skirmish_crysknife() -> None:
    conflict = _conflict_by_id("skirmish_crysknife")

    assert conflict_rewards_texts(conflict) == [
        "1st: Gain 1 Influence (choose a Faction)",
        "2nd: Gain 1 spice, Draw 1 Intrigue card",
        "3rd: Gain 1 spice",
    ]


def test_handled_contract_reward_fields_cover_every_field() -> None:
    assert _HANDLED_CONTRACT_REWARD_FIELDS == {
        field.name for field in dataclasses.fields(ContractReward)
    }


def test_handled_conflict_reward_fields_cover_every_field() -> None:
    assert _HANDLED_CONFLICT_REWARD_FIELDS == {
        field.name for field in dataclasses.fields(ConflictReward)
    }


# ---------- Korean (``*_ko``) ----------


def test_card_name_ko_falls_back_to_english_when_untranslated() -> None:
    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
    from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

    untranslated = next(
        card_id
        for card_id in IMPERIUM_CARDS_BY_ID
        if card_id not in KOREAN_CARD_NAMES["cards"]
    )
    assert _card_name_ko(untranslated) == _card_name(untranslated)


def test_every_contract_condition_ko_renders_non_empty_valid_text() -> None:
    terms = terms_keys()
    for contract in CONTRACTS:
        text = contract_condition_text_ko(contract.condition)
        assert isinstance(text, str) and text.strip()
        assert_placeholders_are_terms(text, terms)
        allowed = _allowed_latin_for_condition(
            contract.condition.kind, contract.condition.target
        )
        assert_no_stray_latin(text, allowed)


def test_every_contract_reward_ko_renders_non_empty_valid_text() -> None:
    terms = terms_keys()
    for contract in CONTRACTS:
        text = contract_reward_text_ko(contract.reward)
        assert isinstance(text, str) and text.strip()
        assert_placeholders_are_terms(text, terms)
        assert_no_stray_latin(text)


def test_every_conflict_reward_ko_line_matches_the_english_count_and_terms() -> None:
    terms = terms_keys()
    for conflict in CONFLICTS:
        lines_en = conflict_rewards_texts(conflict)
        lines_ko = conflict_rewards_texts_ko(conflict)
        if lines_en is None:
            assert lines_ko is None
            continue
        assert lines_ko is not None
        assert len(lines_ko) == len(lines_en) == 3
        for label, line in zip(("1등: ", "2등: ", "3등: "), lines_ko, strict=True):
            assert line.startswith(label)
            assert line.strip() != label.strip()
            assert_placeholders_are_terms(line, terms)
            assert_no_stray_latin(line, _SPACE_NAMES)


def test_ko_reward_lines_never_mix_trash_and_discard() -> None:
    for conflict in CONFLICTS:
        if conflict.rewards is None:
            continue
        for reward in conflict.rewards:
            assert_trash_and_discard_match(
                conflict_reward_text(reward), conflict_reward_text_ko(reward)
            )


def test_ko_contract_reward_lines_never_mix_trash_and_discard() -> None:
    """Same check as above, extended to Contract rewards (2026-09-25 review:
    the reusable helper was only exercised by Conflict rewards, so a
    trash/discard mix in a Contract reward line went unchecked)."""

    for contract in CONTRACTS:
        assert_trash_and_discard_match(
            contract_reward_text(contract.reward),
            contract_reward_text_ko(contract.reward),
        )


def test_ko_contract_reward_text_has_the_same_part_count_as_english() -> None:
    """A dropped field would change how many comma-parts one language has.

    Not a substitute for ``_HANDLED_CONTRACT_REWARD_FIELDS`` (which only
    checks that set of field *names* is complete) — this instead checks
    that both renderers actually emit a part for every field a real
    Contract's reward carries, so a future field added to English but
    silently missed in the Korean renderer's ``if`` chain fails here
    (2026-09-25 review).
    """

    for contract in CONTRACTS:
        en_parts = contract_reward_text(contract.reward).split(", ")
        ko_parts = contract_reward_text_ko(contract.reward).split(", ")
        assert len(en_parts) == len(ko_parts), (
            contract.card.card_id,
            en_parts,
            ko_parts,
        )


def test_ko_conflict_reward_text_has_the_same_part_count_as_english() -> None:
    """Conflict-reward twin of the Contract check above."""

    for conflict in CONFLICTS:
        if conflict.rewards is None:
            continue
        for reward in conflict.rewards:
            en_parts = conflict_reward_text(reward).split(", ")
            ko_parts = conflict_reward_text_ko(reward).split(", ")
            assert len(en_parts) == len(ko_parts), (
                conflict.card.card_id,
                en_parts,
                ko_parts,
            )


def test_contract_condition_text_ko_resolves_a_board_space_name() -> None:
    contract = CONTRACTS_BY_ID["arrakeen_i"]

    assert contract_condition_text_ko(contract.condition) == (
        "Arrakeen 장소로 {agent}를 보냄"
    )


def test_contract_condition_text_ko_renders_harvest_spice() -> None:
    contract = CONTRACTS_BY_ID["harvest_3"]

    assert contract_condition_text_ko(contract.condition) == (
        "메이커 게임판 장소로 {agent}를 보내고, 그 차례에 {spice} 3 이상 얻음"
    )


def test_contract_condition_text_ko_resolves_an_acquired_card_name() -> None:
    contract = CONTRACTS_BY_ID["acquire"]

    assert contract_condition_text_ko(contract.condition) == (
        "스파이스는 흘러야 한다 획득"
    )


def test_contract_condition_text_ko_renders_immediate() -> None:
    contract = CONTRACTS_BY_ID["immediate"]

    assert contract_condition_text_ko(contract.condition) == "가져오는 즉시 완수"


def test_contract_condition_text_ko_renders_earn_alliance() -> None:
    contract = CONTRACTS_BY_ID["bloodlines_earn_any_alliance"]

    assert contract_condition_text_ko(contract.condition) == (
        "아무 팩션과 {alliance}이 됨"
    )


def test_contract_condition_text_ko_renders_immediate_intrigue_trash() -> None:
    contract = CONTRACTS_BY_ID["bloodlines_immediate"]

    assert contract_condition_text_ko(contract.condition) == (
        "{intrigue} 1장 필요, {trash} 후 가져오는 즉시 완수"
    )


def test_contract_reward_text_ko_renders_solari_and_faction_influence() -> None:
    contract = CONTRACTS_BY_ID["acquire"]

    assert contract_reward_text_ko(contract.reward) == (
        "{solari:3}, {influence_spacing_guild:1}"
    )


def test_contract_reward_text_ko_renders_recall_agents() -> None:
    contract = CONTRACTS_BY_ID["sardaukar_ii"]

    assert contract_reward_text_ko(contract.reward) == "{agent} 소환"


def test_conflict_reward_text_ko_renders_a_control_space_row() -> None:
    conflict = _conflict_by_id("siege_of_arrakeen")
    assert conflict.rewards is not None

    assert conflict_reward_text_ko(conflict.rewards[0]) == (
        "{solari:2}, {troop:2}, Arrakeen 지배"
    )


def test_conflict_reward_text_ko_renders_an_optional_trade() -> None:
    conflict = _conflict_by_id("battle_for_arrakeen")
    assert conflict.rewards is not None

    assert conflict_reward_text_ko(conflict.rewards[0]) == (
        "{victory_point:1}, Arrakeen 지배, "
        "{spy} 2 소환 가능 {arrow_right} {victory_point:1}"
    )


def test_conflict_reward_text_ko_renders_choose_distinct_influence() -> None:
    conflict = _conflict_by_id("propaganda")
    assert conflict.rewards is not None

    assert conflict_reward_text_ko(conflict.rewards[0]) == (
        "{influence_any:2} (매번 각기 다른 팩션 중 하나 선택)"
    )


def test_conflict_rewards_texts_ko_skirmish_crysknife() -> None:
    conflict = _conflict_by_id("skirmish_crysknife")

    assert conflict_rewards_texts_ko(conflict) == [
        "1등: {influence_any:1} (4개의 팩션 중 하나 선택)",
        "2등: {spice:1}, {intrigue:1}",
        "3등: {spice:1}",
    ]
