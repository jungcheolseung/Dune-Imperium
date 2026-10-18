"""The Agent box's own event (cleanup-2c-2, ``rules/box_events.py``).

docs/composed-effects-plan.md 5, "정리-2c 사건 문법", 2c-2: an Agent box that
ends leaves exactly one event saying how it ended, named ``<box>:<outcome>``.
"""

from collections import Counter

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import RandomAgent
from dune_imperium.core import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.box_events import BoxOutcome, agent_box_event
from dune_imperium.rules.effects import agent_card_source
from dune_imperium.rules.frames import FrameKind

_BOX = agent_card_source(3, 1, "imperium:long_reach:0")
_BOX_KINDS = frozenset(f"agent_card_effect_{outcome}" for outcome in BoxOutcome)


def test_a_box_event_names_the_box_and_its_outcome() -> None:
    event = agent_box_event(_BOX, "imperium:long_reach:0", 1, BoxOutcome.DECLINED)

    assert event.event_id == f"{_BOX}:declined"
    assert _BOX == "round:3:player:1:agent_card:imperium:long_reach:0"
    assert event.kind == "agent_card_effect_declined"
    assert event.payload == (("card_id", "imperium:long_reach:0"), ("player", 1))


def test_an_icon_s_event_names_the_icon_too() -> None:
    event = agent_box_event(
        _BOX, "imperium:long_reach:0", 1, BoxOutcome.UNAVAILABLE, effect="cards"
    )

    assert event.event_id == f"{_BOX}:cards:unavailable"
    assert event.kind == "agent_card_effect_unavailable"
    assert event.payload == (
        ("card_id", "imperium:long_reach:0"),
        ("effect", "cards"),
        ("player", 1),
    )


def test_every_outcome_has_its_own_kind() -> None:
    kinds = {
        agent_box_event(_BOX, "imperium:long_reach:0", 1, outcome).kind
        for outcome in BoxOutcome
    }

    assert kinds == _BOX_KINDS


def _waiting_boxes(state: GameState) -> set[str]:
    """The cards whose Agent box waits in any seat's Agent-turn frame (the
    active box and a grafted partner's)."""

    waiting: set[str] = set()
    for frame in state.decision_stack:
        if frame.kind != FrameKind.AGENT_EFFECTS:
            continue
        context = dict(frame.context)
        if context.get("pending_agent_effect") is True:
            waiting.add(str(context["card_id"]))
        if context.get("graft_pending_effect") is True and context.get(
            "graft_card_id"
        ):
            waiting.add(str(context["graft_card_id"]))
    return waiting


@pytest.mark.parametrize("seed", [3, 11])
def test_a_box_that_stops_waiting_leaves_its_event_once(seed: int) -> None:
    """Random all-option games with Immortality: a step after which a box no
    longer waits logs that box's event, and no step logs one box's (or one
    icon's) event twice. The Signet Ring's box is left out: its events are
    the Leader's (stage 2c-4)."""

    engine = UprisingRulesEngine()
    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
    )
    state = engine.reset(config, seed)
    agents = [RandomAgent(seed=100 * seed + seat) for seat in range(4)]
    chance = ChanceResolver(seed=seed)
    closed_boxes = 0
    for _ in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        move: DomainAction | ChanceOutcome
        if isinstance(decision, ChanceDecision):
            move = chance.resolve(decision)
        else:
            assert isinstance(decision, PlayerDecision)
            legal = engine.legal_actions(state, decision.owner)
            move = agents[decision.owner].choose_action(
                engine.observe(state, decision.owner), legal
            )
        result = engine.apply(state, move)
        logged = [
            dict(event.payload)
            for event in result.events
            if event.kind in _BOX_KINDS
        ]
        units = Counter((entry["card_id"], entry.get("effect")) for entry in logged)
        assert all(count == 1 for count in units.values()), (move, units)
        for card in _waiting_boxes(state) - _waiting_boxes(result.state):
            if ":signet_ring:" in card:
                continue
            closed_boxes += 1
            assert any(entry["card_id"] == card for entry in logged), (move, card)
        state = result.state
    assert state.phase is GamePhase.FINISHED
    assert closed_boxes
