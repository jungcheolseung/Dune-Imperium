"""Codec v154's Navigation bridges (``records.migration``).

OQ-113 (C), user ruling 2026-10-24, which Navigation options follow
(OQ-039): a cost-free option is played even when it changes nothing, and is
then the card's mandatory play. An older engine spent such a card through
``decline_navigation`` (OQ-039 (b)); its record's decline is that option's
play, and the refusal its fizzle leaves follows it.
"""

from tests.unit.records.test_record_migration import _StartingAt, _v142_record
from tests.unit.rules.test_navigation import (
    _card,
    _reach_two,
    _steersman,
    _turn_state,
)

from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import DomainAction
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.records.migration import migrate_record
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import steps_for

ENGINE = UprisingRulesEngine()
DECLINE = DomainAction(action_id="decline_navigation", actor=0)
DECLINE_ROW = DomainAction(
    action_id="decline",
    actor=0,
    arguments=(("of", "play"), ("printed", "navigation_card_2"), ("source", "leader")),
)


def _card_two_with_nothing_to_do() -> GameState:
    """Navigation card 2 (place a Spy, or recall one for an Intrigue card and
    2 spice) with every Spy in the box: neither option can happen."""

    owner = _steersman(
        (_card(2), _card(5)),
        influence=Influence(emperor=1),
        spies_supply=0,
        spies_boxed=3,
    )
    tech = RulesetConfig(bloodlines=True, tech_module=True)
    opened = _reach_two(_turn_state(owner, config=tech), Faction.EMPEROR)
    assert opened.decision_stack[-1].kind == "navigation_choice"
    return opened


def test_a_recorded_navigation_decline_is_the_fizzling_free_option_s_play() -> None:
    start = _card_two_with_nothing_to_do()
    play = DomainAction(
        action_id="play_navigation", actor=0, arguments=(("option", 0),)
    )
    assert ENGINE.whole_actions(start, 0) == (play,)
    played = ENGINE.apply(start, ENGINE.legal_actions(start, 0)[0]).state
    (refusal,) = ENGINE.legal_actions(played, 0)
    done = ENGINE.apply(played, refusal).state

    for recorded in (DECLINE, DECLINE_ROW):
        record = migrate_record(
            _v142_record(start, recorded, codec=153), engine=_StartingAt(start)
        )
        assert record.complete, record.divergence
        assert record.bridge_counts() == {
            "navigation_fizzle_played": 1,
            "navigation_fizzle_confirmed": 1,
        }
        assert canonical_state_hash(record.state) == canonical_state_hash(done)
        assert record.state.players[0].navigation_played == (_card(2),)

    # A record of this codec never declined there: no bridge answers.
    current = migrate_record(
        _v142_record(start, DECLINE, codec=154), engine=_StartingAt(start)
    )
    assert current.divergence is not None and not current.bridge_counts()


def test_a_decline_this_engine_still_offers_is_taken_as_recorded() -> None:
    # Card 10's lone option has a cost (lose one Influence, gain one), so the
    # decline is still offered (OQ-058) and taken as recorded: neither bridge
    # fires.
    owner = _steersman(
        (_card(10), _card(5)),
        influence=Influence(emperor=1, fremen=1),
    )
    tech = RulesetConfig(bloodlines=True, tech_module=True)
    start = _reach_two(_turn_state(owner, config=tech), Faction.EMPEROR)
    assert DECLINE in ENGINE.whole_actions(start, 0)
    (row,) = steps_for(DECLINE, "navigation_card_10")
    record = migrate_record(
        _v142_record(start, row, codec=153), engine=_StartingAt(start)
    )
    assert record.complete, record.divergence
    assert not record.bridge_counts()
    assert canonical_state_hash(record.state) == canonical_state_hash(
        ENGINE.apply(start, row).state
    )
