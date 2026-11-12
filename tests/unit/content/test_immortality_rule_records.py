"""Immortality's printed rule changes as standing records (composed A7d)."""

from dune_imperium.content.core.abilities import AbilityTiming
from dune_imperium.content.immortality.rule_abilities import (
    IMMORTALITY_STANDING_ABILITIES,
)
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.registry.card_abilities import card_standing_hook
from dune_imperium.content.registry.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.registry.personal_cards import (
    card_copies_partner_box,
    card_grafts_row_card,
)
from dune_imperium.content.registry.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.rules import agent_turn, effects, immortality


def test_each_rule_change_names_a_branch_the_engine_has() -> None:
    """Every record is a standing record without a line; its card exists
    and the branch it names is the one the engine applies."""

    for card_id, record in IMMORTALITY_STANDING_ABILITIES.items():
        assert record.timing is AbilityTiming.STANDING
        assert not record.sections and record.hook
        if card_id != "family_atomics":
            assert card_id in TLEILAXU_CARDS_BY_ID
    assert callable(effects.borrowed_agent_card)
    assert callable(agent_turn.ignores_enemy_agents)
    assert callable(immortality.apply_family_atomics)


def test_the_engine_tells_these_cards_by_their_records() -> None:
    """Plan 8.3, step 3d: the engine asks a card's standing record, not its
    id. Among every personal card, Ghola alone copies its partner's box,
    Usurp alone grafts a Row card and Tleilaxu Infiltrator alone ignores the
    enemy Agents."""

    cards = {
        **STARTING_CARDS_BY_ID,
        **RESERVE_STACKS_BY_ID,
        **IMPERIUM_CARDS_BY_ID,
        **TLEILAXU_CARDS_BY_ID,
    }

    def picked(question: object) -> set[str]:
        assert callable(question)
        return {card_id for card_id, card in cards.items() if question(card)}

    assert picked(card_copies_partner_box) == {"ghola"}
    assert picked(card_grafts_row_card) == {"usurp"}
    assert picked(
        lambda card: card_standing_hook(card) == "infiltrator_ignores_enemy_agents"
    ) == {"tleilaxu_infiltrator"}
