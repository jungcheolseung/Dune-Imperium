"""Tests for the standard Contract and Conflict English text renderer."""

import dataclasses

from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    ConflictDefinition,
    ConflictReward,
)
from dune_imperium.content.uprising.contracts import (
    CONTRACTS,
    CONTRACTS_BY_ID,
    ContractReward,
)
from dune_imperium.display.structs import (
    _HANDLED_CONFLICT_REWARD_FIELDS,
    _HANDLED_CONTRACT_REWARD_FIELDS,
    conflict_reward_text,
    conflict_rewards_texts,
    contract_condition_text,
    contract_reward_text,
)


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
