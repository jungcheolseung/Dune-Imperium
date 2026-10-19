"""The one resource-gain event (cleanup-2c, rule decisions 3 and 4)."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.effect_dsl import (
    GainResources,
    GainVictoryPoints,
    RecruitTroops,
)
from dune_imperium.core import PlayerState
from dune_imperium.rules.effect_interpreter import apply_rewards
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.gain_events import resources_gained_event


def test_a_gain_event_names_its_source_and_only_what_was_gained() -> None:
    source = "round:3:player:1:intrigue:intrigue:market_opportunity:0"
    event = resources_gained_event(source, 1, spice=5)

    assert event.kind == "resources_gained"
    assert event.event_id == f"{source}:resources"
    assert dict(event.payload) == {"player": 1, "source": source, "spice": 5}
    assert event.visible_to is None
    both = resources_gained_event(source, 1, water=1, victory_points=1)
    assert dict(both.payload) == {
        "player": 1,
        "source": source,
        "victory_points": 1,
        "water": 1,
    }


def test_a_gain_event_must_gain_something_and_nothing_negative() -> None:
    with pytest.raises(ValueError):
        resources_gained_event("round:1:player:0:x", 0)
    with pytest.raises(ValueError):
        resources_gained_event("round:1:player:0:x", 0, spice=-1)


def test_a_lines_gains_are_one_event_where_its_first_gain_stands() -> None:
    # An Intrigue or Arrakeen Scouts line gains through the shared
    # interpreter: its resources and its Victory Points ride on one event,
    # at the place of its first gain (decisions 3 and 4); before, the
    # resources left no event and the point a ``victory_points_gained``.
    state = UprisingRulesEngine().reset(RulesetConfig(), 1)
    seat = state.players[0]
    # An empty supply, so the recruit between the gains leaves its event.
    owner = replace(
        seat, troops_supply=0, troops_garrison=seat.troops_garrison + seat.troops_supply
    )
    state = replace(state, players=(owner, *state.players[1:]))
    source = "round:1:player:0:intrigue:intrigue:opportunism:0"

    outcome = apply_rewards(
        state,
        0,
        (GainResources(spice=2), RecruitTroops(count=1), GainVictoryPoints(amount=1)),
        source=source,
    )

    events = outcome.result.events
    assert [event.kind for event in events] == [
        "resources_gained",
        "troops_recruit_short",
    ]
    assert dict(events[0].payload) == {
        "player": 0,
        "source": source,
        "spice": 2,
        "victory_points": 1,
    }
    after: PlayerState = outcome.result.state.players[0]
    assert after.resources.spice == state.players[0].resources.spice + 2
    assert after.victory_points == state.players[0].victory_points + 1
