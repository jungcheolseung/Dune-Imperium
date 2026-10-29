"""Contract terms and Conflict reward rows as ability records (composed A5a, A5b)."""

import pytest

from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.conflict_abilities import CONFLICT_REWARD_ABILITIES
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contract_abilities import CONTRACT_ABILITIES
from dune_imperium.content.uprising.contracts import CONTRACTS
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
    for contract in CONTRACTS:
        # The definition holds the record itself (no compiled copy).
        record = CONTRACT_ABILITIES[contract.copy_of or contract.card.card_id]
        assert contract.terms is record
    assert len(CONTRACTS) == 28
    for ability in CONTRACT_ABILITIES.values():
        assert ability.timing is AbilityTiming.CONTRACT
        assert ability.requirement is not None
        assert len(ability.sections) == 1


def test_every_conflict_takes_its_three_rows_from_its_records() -> None:
    # The original game's cards share the table (docs/base-game-and-ix-plan.md
    # 4.2 item 7), and so do Rise of Ix's three (stage P4d-1).
    conflicts = (*CONFLICTS, *IMPERIUM_CONFLICTS, *IX_CONFLICTS)
    assert {
        conflict.card.card_id for conflict in conflicts if conflict.reward_rows
    } == set(CONFLICT_REWARD_ABILITIES)
    for conflict in conflicts:
        # The definition holds the records themselves (no compiled copy).
        rows = CONFLICT_REWARD_ABILITIES[conflict.card.card_id]
        assert conflict.reward_rows is not None
        assert all(a is b for a, b in zip(conflict.reward_rows, rows, strict=True))
    for rows in CONFLICT_REWARD_ABILITIES.values():
        assert len(rows) == 3
        for row in rows:
            assert row.timing is AbilityTiming.CONFLICT_REWARD


def test_the_new_contract_and_conflict_pieces_read_as_printed() -> None:
    """The completion conditions read as the tiles print them, and a
    Conflict's control as its row does, in both languages."""

    seen: set[type] = set()
    for contract in CONTRACTS:
        requirement = contract.requirement
        if isinstance(requirement, (AtBoardSpace, AcquiredCard, ContractTaken)) or (
            isinstance(requirement, AllianceTaken)
        ):
            if contract.requires_intrigue_trash:
                continue  # its own sentence names the trash; the cost is a piece
            seen.add(type(requirement))
            assert condition_text(requirement) == contract_condition_text(contract)
            assert condition_text_ko(requirement) == contract_condition_text_ko(
                contract
            )
    for conflict in CONFLICTS:
        for row in conflict.reward_rows or ():
            for piece in row.sections[0].rewards if row.sections else ():
                if isinstance(piece, TakeControl):
                    seen.add(TakeControl)
                    assert reward_text(piece) in conflict_reward_text(row)
                    assert reward_text_ko(piece) in conflict_reward_text_ko(row)
    assert seen == {
        AtBoardSpace,
        AcquiredCard,
        ContractTaken,
        AllianceTaken,
        TakeControl,
    }


def test_the_record_checks_refuse_what_the_readers_cannot_hold() -> None:
    """A record the payer and the card text cannot read fails loudly instead
    of being dropped (review of A5; the compilers' checks since the reward
    totals cleanup, 2026-10-21)."""

    from dune_imperium.content.uprising.abilities import Ability
    from dune_imperium.content.uprising.conflicts import check_conflict_reward_row
    from dune_imperium.content.uprising.contracts import check_contract_terms
    from dune_imperium.content.uprising.effect_dsl import (
        EffectSection,
        GainInfluence,
        GainResources,
        GainVictoryPoints,
        PayResources,
    )

    doubled = EffectSection(rewards=(GainResources(solari=2), GainResources(water=1)))
    with pytest.raises(ValueError, match="twice"):
        check_contract_terms(
            Ability(
                timing=AbilityTiming.CONTRACT,
                sections=(doubled,),
                requirement=AtBoardSpace("arrakeen"),
            )
        )
    with pytest.raises(TypeError, match="not a Contract condition"):
        check_contract_terms(
            Ability(
                timing=AbilityTiming.CONTRACT,
                sections=(EffectSection(rewards=(GainResources(solari=2),)),),
                requirement=TakeControl("arrakeen"),  # type: ignore[arg-type]
            )
        )
    with pytest.raises(ValueError, match="twice"):
        check_conflict_reward_row(
            Ability(timing=AbilityTiming.CONFLICT_REWARD, sections=(doubled,))
        )
    with pytest.raises(TypeError):
        check_conflict_reward_row(
            Ability(
                timing=AbilityTiming.CONFLICT_REWARD,
                sections=(EffectSection(rewards=(GainInfluence(times=2),)),),
            )
        )
    arrows = (
        EffectSection(rewards=(GainVictoryPoints(2),), costs=(PayResources(solari=6),)),
        EffectSection(rewards=(GainVictoryPoints(1),), costs=(PayResources(spice=4),)),
    )
    with pytest.raises(ValueError, match="one VP"):
        check_conflict_reward_row(
            Ability(timing=AbilityTiming.CONFLICT_REWARD, sections=arrows)
        )
