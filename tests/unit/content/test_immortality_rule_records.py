"""Immortality's printed rule changes as standing records (composed A7d)."""

from dune_imperium.content.immortality.rule_abilities import (
    IMMORTALITY_STANDING_ABILITIES,
)
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.personal_cards import (
    card_is_ghola,
    card_is_usurp,
)
from dune_imperium.rules import agent_turn, effects, immortality


def test_each_rule_change_names_a_branch_the_engine_has() -> None:
    """Every record is a standing record without a line; its card exists
    and the branch it names is the one the engine applies."""

    for card_id, record in IMMORTALITY_STANDING_ABILITIES.items():
        assert record.timing is AbilityTiming.STANDING
        assert not record.sections and record.hook
        if card_id != "family_atomics":
            assert card_id in TLEILAXU_CARDS_BY_ID
    assert card_is_ghola(TLEILAXU_CARDS_BY_ID["ghola"])
    assert card_is_usurp(TLEILAXU_CARDS_BY_ID["usurp"])
    assert callable(effects.borrowed_agent_card)
    assert callable(agent_turn.is_tleilaxu_infiltrator)
    assert callable(immortality.apply_family_atomics)
