"""A revealed card's Reveal lines read off its ability record (stage B3e-2).

docs/stage-b-plan.md decision E-2 (user decision 2026-10-20, "e-2는
추천대로"): the Reveal turn reads each printed line from the card's record
(``rules.reveal_lines``) instead of the compiled totals
(``PersonalCardRevealEffect``), which the card text and the action catalog
still read; the two must say the same of every card.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.immortality.tleilaxu import tleilaxu_cards_for
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    Condition,
    EffectSection,
    FactionBond,
    GainResources,
    GarrisonedUnitsAtLeast,
    HasSwordmaster,
    SpyingOnMakerSpace,
)
from dune_imperium.content.uprising.imperium import imperium_cards_for_choam
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.reveal_abilities import reveal_effect
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    EXPERIMENTATION,
    STARTING_DECK,
)
from dune_imperium.core.player import PlayerState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.conditions import owner_condition_holds
from dune_imperium.rules.reveal_lines import (
    COMMAND_PERSUASION,
    RevealLine,
    line_conditions_hold,
    reveal_lines,
)

_CARDS: tuple[PersonalCardDefinition, ...] = (
    *STARTING_DECK,
    # Immortality's starting card and Epic Game Mode's.
    EXPERIMENTATION,
    CONTROL_THE_SPICE,
    *RESERVE_STACKS,
    *imperium_cards_for_choam(
        True, True, bloodlines=True, tech_module=True, immortality=True
    ),
    *tleilaxu_cards_for(True),
)


def test_every_cards_record_lines_say_what_its_compiled_totals_say() -> None:
    # The rules read the record; the card text and the codec read the
    # totals compiled from it: one line each, in the same order (the Reveal
    # frame's ``card#index`` keys).
    for card in _CARDS:
        lines = reveal_lines(card)
        compiled = tuple(reveal_effect(line.section) for line in lines)
        assert compiled == card.reveal_effects, card.card.card_id


def _line(card_id: str, index: int = 0) -> RevealLine:
    return reveal_lines(personal_card_for_instance(card_id))[index]


def test_a_counted_line_counts_its_own_cards() -> None:
    # Stilgar, The Devoted: 2 Persuasion for each Fremen card in play [card
    # face]; Sardaukar Coordination: a sword for each revealed Emperor card;
    # Interstellar Trade: a Persuasion for each completed Contract (OQ-028
    # (c)); Leadership: a sword for each other revealed sword card.
    fremen = personal_card_for_instance("imperium:stilgar_the_devoted:0")
    emperor = personal_card_for_instance("imperium:sardaukar_coordination:0")
    stilgar = _line("imperium:stilgar_the_devoted:0")
    assert stilgar.persuasion_over((), 0, (fremen, fremen, emperor)) == 4
    assert stilgar.arrival_gains(fremen) == (2, 0)
    assert stilgar.arrival_gains(emperor) == (0, 0)
    coordination = _line("imperium:sardaukar_coordination:0")
    assert coordination.strength_over((emperor, emperor, fremen)) == 2
    assert coordination.arrival_gains(emperor) == (0, 1)
    trade = _line("imperium:interstellar_trade:0")
    assert trade.persuasion_per_completed_contract == 1
    assert trade.persuasion_over((), 3, ()) == 3
    leadership = _line("imperium:leadership:0")
    assert leadership.strength_per_other_sword_card == 1
    assert leadership.strength_over((emperor,)) == 0


# A dealt seat of a base game (its own quantities consistent).
_SEAT = UprisingRulesEngine().reset(RulesetConfig(), 0).players[0]
_SPICE = GainResources(spice=1)
_MAKER_POST = tuple(
    post.post_id
    for post in OBSERVATION_POSTS
    if "deep_desert" in post.connected_space_ids
)[:1]


@pytest.mark.parametrize(
    ("condition", "unmet", "met"),
    [
        (
            HasSwordmaster(),
            _SEAT,
            # The Swordmaster is a third Agent.
            replace(
                _SEAT,
                swordmaster_acquired=True,
                agents_available=_SEAT.agents_available + 1,
            ),
        ),
        (
            GarrisonedUnitsAtLeast(_SEAT.troops_garrison + 1),
            _SEAT,
            # A Commander in the garrison counts too [Bloodlines p. 12].
            replace(_SEAT, commanders_garrison=1),
        ),
        (
            SpyingOnMakerSpace(),
            _SEAT,
            replace(_SEAT, spies_supply=2, spy_post_ids=_MAKER_POST),
        ),
    ],
)
def test_a_reveal_lines_seat_condition_is_judged_with_every_other(
    condition: Condition, unmet: PlayerState, met: PlayerState
) -> None:
    # Stage B3e-2: the Reveal-only seat conditions joined the one place that
    # judges a seat's conditions (``conditions.owner_condition_holds``).
    assert owner_condition_holds(unmet, condition) is False
    assert owner_condition_holds(met, condition) is True


def test_a_bond_and_command_are_judged_with_the_reveal() -> None:
    # A Faction Bond counts another card in play [Main p. 20]; "Command
    # (6+)" reads the Reveal turn's Persuasion, None (not known yet) never
    # meeting it [Bloodlines pp. 5, 12].
    seat = _SEAT
    bond = RevealLine(
        EffectSection(rewards=(_SPICE,), condition=FactionBond(Faction.FREMEN))
    )
    card = "imperium:stilgar_the_devoted:0"
    other = "imperium:shishakli:0"
    assert not line_conditions_hold(seat, (card,), card, bond)
    assert line_conditions_hold(seat, (card, other), card, bond)
    command = RevealLine(EffectSection(rewards=(_SPICE,), condition=CommandReached()))
    assert not line_conditions_hold(seat, (), card, command)
    assert not line_conditions_hold(
        seat, (), card, command, persuasion=COMMAND_PERSUASION - 1
    )
    assert line_conditions_hold(seat, (), card, command, persuasion=COMMAND_PERSUASION)
