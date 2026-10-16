"""Acquire, trash and discard boxes as ability records (composed effects, A4a)."""

from collections.abc import Mapping
from dataclasses import replace
from enum import StrEnum
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import GainResources
from dune_imperium.content.uprising.trigger_abilities import (
    ACQUISITION_ABILITIES,
    DISCARD_ABILITIES,
    TRASH_ABILITIES,
    single_resource,
)
from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardDiscardEffect,
    PersonalCardTrashEffect,
)
from dune_imperium.core import GamePhase, GameState, PlayerState
from dune_imperium.display.effect_dsl_text import reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko
from dune_imperium.display.tokens import (
    ACQUISITION_EFFECT_TEXT,
    DISCARD_EFFECT_TEXT,
    TRASH_EFFECT_TEXT,
)
from dune_imperium.display.tokens_ko import (
    ACQUISITION_EFFECT_TEXT_KO,
    DISCARD_EFFECT_TEXT_KO,
    TRASH_EFFECT_TEXT_KO,
)
from dune_imperium.rules.intrigue_deck import triggered_intrigue_draw

_TABLES: tuple[
    tuple[
        Mapping[Any, Ability],
        type[StrEnum],
        AbilityTiming,
        Mapping[Any, str],
        Mapping[Any, str],
    ],
    ...,
] = (
    (
        ACQUISITION_ABILITIES,
        PersonalCardAcquisitionEffect,
        AbilityTiming.ACQUIRE,
        ACQUISITION_EFFECT_TEXT,
        ACQUISITION_EFFECT_TEXT_KO,
    ),
    (
        TRASH_ABILITIES,
        PersonalCardTrashEffect,
        AbilityTiming.TRASH,
        TRASH_EFFECT_TEXT,
        TRASH_EFFECT_TEXT_KO,
    ),
    (
        DISCARD_ABILITIES,
        PersonalCardDiscardEffect,
        AbilityTiming.DISCARD,
        DISCARD_EFFECT_TEXT,
        DISCARD_EFFECT_TEXT_KO,
    ),
)


def test_every_trigger_box_is_an_automatic_record() -> None:
    """Every acquire, trash and discard box has its record: one line, no cost,
    nothing to choose, at its own timing."""

    for table, members, timing, _, _ in _TABLES:
        assert set(table) == set(members)
        for ability in table.values():
            assert ability.timing is timing
            assert ability.mark is AbilityMark.AUTOMATIC
            (line,) = ability.sections
            assert line.costs == () and line.condition is None
            assert len(line.rewards) == 1


def test_trigger_records_read_as_the_cards_print_them() -> None:
    """The record's reward renders as the box's printed text, in both
    languages -- except "Take 1 face-up Contract", whose shared piece does
    not print "face-up" (every Contract taken is a face-up one)."""

    for table, _, _, english, korean in _TABLES:
        for effect, ability in table.items():
            (reward,) = ability.sections[0].rewards
            if effect is PersonalCardAcquisitionEffect.TAKE_CONTRACT:
                assert reward_text(reward) == "Take 1 Contract"
                continue
            assert reward_text(reward) == english[effect], effect
            assert reward_text_ko(reward) == korean[effect], effect


def test_a_trigger_gain_names_its_one_resource() -> None:
    assert single_resource(GainResources(solari=2)) == ("solari", 2)
    assert single_resource(GainResources(water=1)) == ("water", 1)
    for table, _, _, _, _ in _TABLES:
        for ability in table.values():
            (reward,) = ability.sections[0].rewards
            if isinstance(reward, GainResources):
                single_resource(reward)


def _game(owner: PlayerState, deck: tuple[str, ...]) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=deck,
    )


def test_a_triggered_intrigue_draw_outside_a_turn_draws_or_queues() -> None:
    """Outside its owner's turn the box draws the deck's top card at once,
    or with an empty deck returns the draw to queue [FAQ p. 2]."""

    owner = PlayerState(player_id=0)
    state = _game(owner, ("intrigue:bribery:0", "intrigue:bypass_protocol:0"))
    drawn, deck, events, pending = triggered_intrigue_draw(
        state, owner, 0, origin="card:x", source="src"
    )
    assert drawn.intrigue_cards == ("intrigue:bribery:0",)
    assert deck == ("intrigue:bypass_protocol:0",)
    assert [(event.event_id, event.kind) for event in events] == [
        ("src", "intrigue_card_drawn")
    ]
    assert pending is None
    empty = replace(state, intrigue_deck=())
    kept, deck, events, pending = triggered_intrigue_draw(
        empty, owner, 0, origin="card:x", source="src"
    )
    assert kept == owner and deck == () and events == ()
    assert pending == (0, 1, "src")
