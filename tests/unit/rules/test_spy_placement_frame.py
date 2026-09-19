"""The generic Spy placement frame: mandatory with a Spy in the supply."""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core import GameState, PlayerState
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.spy_moves import (
    apply_spy_placement,
    legal_spy_placement_actions,
    spy_placement_frame,
)

ALL_POSTS = tuple(post.post_id for post in OBSERVATION_POSTS)


def _state(owner: PlayerState) -> GameState:
    turn = DecisionFrame(
        kind=FrameKind.TURN,
        frame_id="test:turn",
        decision=PlayerDecision(owner=0, prompt="turn"),
    )
    return GameState(
        config=RulesetConfig(),
        seed=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(turn,),
    )


def test_a_spy_in_the_supply_has_to_be_placed() -> None:
    # The designer's erratum to [Main p. 11] (Hidden Assets Discord; adopted
    # with OQ-057): "It is mandatory to place a Spy if you have at least one
    # Spy in your supply."
    state = spy_placement_frame(
        _state(PlayerState(player_id=0)), 0, ALL_POSTS, source="test"
    )

    offered = legal_spy_placement_actions(state, 0)
    assert {action.action_id for action in offered} == {"place_spy_on_space"}
    assert len(offered) == len(ALL_POSTS)


def test_with_an_empty_supply_the_recall_is_the_owners_choice() -> None:
    # "If you have no Spies in your supply when you need to place one, you
    # may first recall one of your Spies for no effect." [Main pp. 11, 20]
    posts = ALL_POSTS[:3]
    owner = PlayerState(player_id=0, spies_supply=0, spy_post_ids=posts)
    state = spy_placement_frame(_state(owner), 0, ALL_POSTS, source="test")

    offered = legal_spy_placement_actions(state, 0)
    assert offered[0].action_id == "decline_spy_placement"
    assert {
        dict(action.arguments)["post_id"]
        for action in offered
        if action.action_id == "recall_spy_for_placement"
    } == set(posts)

    passed = apply_spy_placement(state, offered[0])
    assert passed.state.decision_stack[-1].kind == "turn"
    assert passed.state.players[0].spy_post_ids == posts

    # Once recalled, the Spy is in the supply and has to be placed; the
    # vacated post is a legal target again.
    recalled = apply_spy_placement(state, offered[1]).state
    assert recalled.players[0].spies_supply == 1
    placements = legal_spy_placement_actions(recalled, 0)
    assert {action.action_id for action in placements} == {"place_spy_on_space"}
    assert dict(offered[1].arguments)["post_id"] in {
        dict(action.arguments)["post_id"] for action in placements
    }


def test_without_a_free_post_the_placement_is_passed() -> None:
    post = ALL_POSTS[0]
    rival = PlayerState(player_id=1, spies_supply=2, spy_post_ids=(post,))
    state = _state(PlayerState(player_id=0))
    state = replace(state, players=(state.players[0], rival, *state.players[2:]))
    state = spy_placement_frame(state, 0, (post,), source="test")

    assert [action.action_id for action in legal_spy_placement_actions(state, 0)] == [
        "decline_spy_placement"
    ]
