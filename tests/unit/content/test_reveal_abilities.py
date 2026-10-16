"""Reveal automatic gains as ability records (composed effects, A4c)."""

from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS
from dune_imperium.content.uprising.abilities import AbilityMark, AbilityTiming
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    GarrisonedUnitsAtLeast,
    HasSwordmaster,
    RevealPersuasion,
    RevealSwords,
    SpyingOnMakerSpace,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.reveal_abilities import (
    REVEAL_GAIN_ABILITIES,
    reveal_effect,
    reveal_effects_of,
)
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    EXPERIMENTATION,
    STARTING_DECK,
)
from dune_imperium.content.uprising.types import PersonalCardRevealEffect
from dune_imperium.display.effect_dsl_text import condition_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    reward_text_ko,
)
from dune_imperium.display.tokens import reveal_effect_text
from dune_imperium.display.tokens_ko import reveal_effect_text_ko


def _manifests() -> dict[str, tuple[PersonalCardRevealEffect, ...]]:
    """Every personal card's Reveal gains, by definition id."""

    gains = {
        entry.card.card_id: entry.reveal_effects
        for entry in (*IMPERIUM_CARDS, *TLEILAXU_CARDS)
    }
    for starter in (CONTROL_THE_SPICE, EXPERIMENTATION, *STARTING_DECK):
        gains[starter.card.card_id] = starter.reveal_effects
    for stack in RESERVE_STACKS:
        gains[stack.card.card_id] = stack.reveal_effects
    return gains


def test_every_card_takes_its_reveal_gains_from_its_record() -> None:
    """The manifests hold no Reveal gain of their own: a card's gains are its
    record's lines, and every record names a card that has them."""

    cards = _manifests()
    assert set(REVEAL_GAIN_ABILITIES) <= set(cards)
    for card_id, gains in cards.items():
        assert gains == reveal_effects_of(card_id), card_id
        assert bool(gains) == (card_id in REVEAL_GAIN_ABILITIES), card_id
    assert len(REVEAL_GAIN_ABILITIES) == 51
    assert sum(len(a.sections) for a in REVEAL_GAIN_ABILITIES.values()) == 55


def test_reveal_gain_records_are_automatic_lines() -> None:
    for ability in REVEAL_GAIN_ABILITIES.values():
        assert ability.timing is AbilityTiming.REVEAL
        assert ability.mark is AbilityMark.AUTOMATIC
        for line in ability.sections:
            assert line.costs == ()
            reveal_effect(line)


def test_the_new_reveal_pieces_read_as_the_cards_print_them() -> None:
    """Command, the Maker-space Spy, the garrison size and the Reveal
    Persuasion and swords (with what they are counted per) render as the
    card's Reveal line does, in both languages; the Swordmaster half reads
    whole in Korean, while English prints it inside "High Council and
    Swordmaster"."""

    seen: set[type] = set()
    for ability in REVEAL_GAIN_ABILITIES.values():
        for line in ability.sections:
            compiled = reveal_effect(line)
            english = reveal_effect_text(compiled)
            korean = reveal_effect_text_ko(compiled)
            for reward in line.rewards:
                if isinstance(reward, (RevealPersuasion, RevealSwords)):
                    seen.add(type(reward))
                    assert reward_text(reward) in english, english
                    assert reward_text_ko(reward) in korean, korean
            conditions = getattr(line.condition, "conditions", (line.condition,))
            for condition in conditions:
                if isinstance(
                    condition,
                    (CommandReached, SpyingOnMakerSpace, GarrisonedUnitsAtLeast),
                ):
                    seen.add(type(condition))
                    assert condition_text(condition) in english, english
                    assert condition_text_ko(condition) in korean, korean
                if isinstance(condition, HasSwordmaster):
                    seen.add(HasSwordmaster)
                    assert "Swordmaster" in english
                    assert condition_text_ko(condition) in korean, korean
    assert seen == {
        RevealPersuasion,
        RevealSwords,
        CommandReached,
        SpyingOnMakerSpace,
        GarrisonedUnitsAtLeast,
        HasSwordmaster,
    }
