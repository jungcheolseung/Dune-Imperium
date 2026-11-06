"""A Sardaukar Commander row's price in the actions payload.

Play feedback 2026-10-25: with Sardaukar High Command the recruit row still
read "(2 Solari)" while the engine took 1. The labels printed the base price
[Bloodlines p. 4]; the row now carries what it costs the seat
(``sessions._serialize_action`` ``solari_cost``, ``rules.sardaukar``
``commander_cost``: "Recruiting a Sardaukar Commander (including when you
acquire one) costs you 1 less" [Sardaukar High Command Tech tile]). Display
only: the legal actions and their effects are unchanged.
"""

from collections.abc import Mapping
from types import SimpleNamespace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_SETUP_SPACE_IDS,
    skill_tile_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.sardaukar import legal_sardaukar_commander_actions
from dune_imperium.server.sessions import _serialize_action

ENGINE = UprisingRulesEngine()
SKILLS = skill_tile_instance_ids()


def _state(*, tech_ids: tuple[str, ...] = (), discount: int = 0) -> GameState:
    owner = PlayerState(
        player_id=0,
        hand=starting_deck_instance_ids(0),
        resources=Resources(solari=4, water=2),
        commanders_supply=1,
        tech_ids=tech_ids,
        commander_discount_turn=discount,
    )
    return GameState(
        config=RulesetConfig(bloodlines=True, tech_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        sardaukar_commander_space_ids=COMMANDER_SETUP_SPACE_IDS,
        sardaukar_commanders_bank=1,
        skill_face_up=tuple(SKILLS[:4]),
        skill_stack=tuple(SKILLS[4:]),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _payload(state: GameState, action: DomainAction) -> Mapping[str, object]:
    session = SimpleNamespace(
        engine=ENGINE, state=state, game_id="test", awaiting_confirmation=None
    )
    legal = ENGINE.whole_actions(state, 0)
    assert action in legal
    return _serialize_action(legal.index(action), action, session)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tech_ids", "discount", "cost"),
    [
        ((), 0, 2),
        (("sardaukar_high_command",), 0, 1),
        # Honor Guard's discount for the turn stacks; never below zero.
        (("sardaukar_high_command",), 2, 0),
    ],
)
def test_the_reveal_recruit_row_carries_the_seats_price(
    tech_ids: tuple[str, ...], discount: int, cost: int
) -> None:
    state = begin_reveal_turn(
        _state(tech_ids=tech_ids, discount=discount), DomainAction("reveal_turn", 0)
    ).state
    recruit = DomainAction("recruit_sardaukar_commander", 0)

    payload = _payload(state, recruit)

    assert payload["solari_cost"] == cost
    paid = apply_whole(ENGINE, state, recruit).events
    (event,) = (e for e in paid if e.kind == "sardaukar_commander_recruited")
    assert dict(event.payload)["solari"] == cost


def test_a_visited_spaces_commander_row_carries_the_seats_price() -> None:
    state = _state(tech_ids=("sardaukar_high_command",))
    visit = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "dutiful_service"
    )
    state = apply_agent_action(state, visit).state
    for action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, action).state
    offers = [
        action
        for action in legal_sardaukar_commander_actions(state, 0)
        if action.action_id == "acquire_sardaukar_commander"
    ]
    assert offers

    for offer in offers:
        assert _payload(state, offer)["solari_cost"] == 1


def test_other_rows_carry_no_price() -> None:
    state = _state()

    for index, action in enumerate(ENGINE.whole_actions(state, 0)):
        session = SimpleNamespace(
            engine=ENGINE, state=state, game_id="test", awaiting_confirmation=None
        )
        payload = _serialize_action(index, action, session)  # type: ignore[arg-type]
        assert "solari_cost" not in payload
