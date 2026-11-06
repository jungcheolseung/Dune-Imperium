"""Spy rules from docs/rules that had no regression test (2026-11 audit).

Each test quotes the docs/rules sentence it pins, with its citation.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.spies import (
    apply_gather_intelligence_action,
    legal_gather_intelligence_actions,
)

# Research Station is directly connected to two observation posts
# (docs/rules/observation-posts.md: "`Research Station`과 `Spice Refinery`는
# 각각 서로 다른 observation post 두 곳에 직접 연결된다." [Main pp. 4-5 board
# artwork]).
REFINERY_POST = "arrakis-research-station-spice-refinery"
TABR_POST = "arrakis-research-station-sietch-tabr"


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _state(owner: PlayerState, *, occupied_by_opponent: bool) -> GameState:
    opponent = PlayerState(player_id=1)
    if occupied_by_opponent:
        opponent = replace(
            opponent, agents_available=1, agent_locations=("research_station",)
        )
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(
            owner,
            opponent,
            *(PlayerState(player_id=seat) for seat in range(2, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _owner_with_two_research_station_spies() -> PlayerState:
    return PlayerState(
        player_id=0,
        hand=(_instance("reconnaissance"),),
        deck=(_instance("dagger"), _instance("diplomacy")),
        resources=Resources(water=2),
        spies_supply=1,
        spy_post_ids=(REFINERY_POST, TABR_POST),
    )


def _to_research_station(
    state: GameState, infiltrate_post_id: str | None = None
) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "research_station"
        and dict(action.arguments).get("infiltrate_post_id") == infiltrate_post_id
    )


def test_two_connected_spies_gather_intelligence_only_once() -> None:
    """Two Spies on one visit cannot both Gather Intelligence.

    docs/rules/player-turns.md: "같은 Spy를 Infiltrate와 Gather Intelligence에
    함께 사용할 수 없다. 서로 다른 Spy 두 개를 한 turn에 recall해 하나는
    Infiltrate, 하나는 Gather Intelligence에 사용할 수 있지만, 둘을 모두
    Gather Intelligence에 사용할 수는 없다." [Main p. 11] [FAQ p. 4]
    """

    state = _state(_owner_with_two_research_station_spies(), occupied_by_opponent=False)
    placed = apply_agent_action(state, _to_research_station(state)).state

    offered = legal_gather_intelligence_actions(placed, 0)
    assert {
        dict(action.arguments).get("post_id")
        for action in offered
        if action.action_id == "gather_intelligence"
    } == {REFINERY_POST, TABR_POST}

    gather = next(
        action
        for action in offered
        if dict(action.arguments).get("post_id") == REFINERY_POST
    )
    gathered = apply_gather_intelligence_action(placed, gather).state

    # The other connected Spy stays on its post and is not offered a second
    # Gather Intelligence.
    assert gathered.players[0].spy_post_ids == (TABR_POST,)
    assert len(gathered.players[0].hand) == 1
    assert legal_gather_intelligence_actions(gathered, 0) == ()


def test_one_spy_infiltrates_and_another_gathers_intelligence() -> None:
    """One Spy may Infiltrate and a different one Gather Intelligence.

    docs/rules/uprising-systems.md: "You may recall two Spies in one turn if
    each is used for a different effect. For example: … you can recall one to
    Infiltrate and one to Gather Intelligence, but not both to Gather
    Intelligence." `[FAQ p. 4]` `[Main p. 11]`
    """

    state = _state(_owner_with_two_research_station_spies(), occupied_by_opponent=True)
    infiltrate = _to_research_station(state, infiltrate_post_id=REFINERY_POST)
    placed = apply_agent_action(state, infiltrate).state

    assert placed.players[0].spy_post_ids == (TABR_POST,)
    offered = legal_gather_intelligence_actions(placed, 0)
    # Only the Spy that did not Infiltrate may Gather Intelligence.
    assert [
        dict(action.arguments).get("post_id")
        for action in offered
        if action.action_id == "gather_intelligence"
    ] == [TABR_POST]

    gather = next(
        action for action in offered if action.action_id == "gather_intelligence"
    )
    gathered = apply_gather_intelligence_action(placed, gather).state

    assert gathered.players[0].spy_post_ids == ()
    assert gathered.players[0].spies_supply == 3
    assert len(gathered.players[0].hand) == 1
