"""Contract terms and Conflict reward rows as ability records (composed A5a, A5b)."""

from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.conflict_abilities import CONFLICT_REWARD_ABILITIES
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contract_abilities import CONTRACT_ABILITIES
from dune_imperium.content.uprising.contracts import (
    CONTRACTS,
    ContractConditionKind,
)
from dune_imperium.content.uprising.effect_dsl import (
    AcquiredCard,
    AllianceTaken,
    AtBoardSpace,
    ContractTaken,
    TakeControl,
)
from dune_imperium.display.effect_dsl_text import condition_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    reward_text_ko,
)
from dune_imperium.display.structs import (
    conflict_reward_text,
    conflict_reward_text_ko,
    contract_condition_text,
    contract_condition_text_ko,
)


def test_every_contract_tile_takes_its_terms_from_its_record() -> None:
    """A tile's record is keyed by its id; a second copy shares its first
    copy's."""

    ids = {contract.copy_of or contract.card.card_id for contract in CONTRACTS}
    assert ids == set(CONTRACT_ABILITIES)
    assert len(CONTRACTS) == 28
    for ability in CONTRACT_ABILITIES.values():
        assert ability.timing is AbilityTiming.CONTRACT
        assert ability.requirement is not None
        assert len(ability.sections) == 1


def test_every_conflict_takes_its_three_rows_from_its_records() -> None:
    assert {
        conflict.card.card_id for conflict in CONFLICTS if conflict.rewards
    } == set(CONFLICT_REWARD_ABILITIES)
    for rows in CONFLICT_REWARD_ABILITIES.values():
        assert len(rows) == 3
        for row in rows:
            assert row.timing is AbilityTiming.CONFLICT_REWARD


def test_the_new_contract_and_conflict_pieces_read_as_printed() -> None:
    """The completion conditions read as the tiles print them, and a
    Conflict's control as its row does, in both languages."""

    seen: set[type] = set()
    for contract in CONTRACTS:
        requirement = CONTRACT_ABILITIES[
            contract.copy_of or contract.card.card_id
        ].requirement
        if isinstance(requirement, (AtBoardSpace, AcquiredCard, ContractTaken)) or (
            isinstance(requirement, AllianceTaken)
        ):
            trash = ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH
            if contract.condition.kind is trash:
                continue  # its own sentence names the trash; the cost is a piece
            seen.add(type(requirement))
            assert condition_text(requirement) == contract_condition_text(
                contract.condition
            )
            assert condition_text_ko(requirement) == contract_condition_text_ko(
                contract.condition
            )
    for conflict in CONFLICTS:
        for row, reward in zip(
            CONFLICT_REWARD_ABILITIES.get(conflict.card.card_id, ()),
            conflict.rewards or (),
            strict=False,
        ):
            for piece in row.sections[0].rewards if row.sections else ():
                if isinstance(piece, TakeControl):
                    seen.add(TakeControl)
                    assert reward_text(piece) in conflict_reward_text(reward)
                    assert reward_text_ko(piece) in conflict_reward_text_ko(reward)
    assert seen == {
        AtBoardSpace,
        AcquiredCard,
        ContractTaken,
        AllianceTaken,
        TakeControl,
    }
