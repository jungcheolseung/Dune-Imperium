"""Tests for the framework-neutral game sessions of the play server."""

import json

import pytest

from dune_imperium.server.sessions import (
    GameSessionManager,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

ALL_AI = ("heuristic", "random", "heuristic", "random")
HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def test_an_all_ai_game_finishes_during_creation() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(ALL_AI, game_seed=11)

    assert summary["finished"] is True
    assert summary["phase"] == "finished"
    assert summary["decision"] is None
    standings = _rows(summary["standings"])
    assert [entry["rank"] for entry in standings] == [1, 2, 3, 4]
    json.dumps(summary)


def test_the_same_seed_reproduces_an_all_ai_game() -> None:
    manager = GameSessionManager()

    first = manager.create_game(ALL_AI, game_seed=12)
    second = manager.create_game(ALL_AI, game_seed=12)

    assert first["standings"] == second["standings"]
    assert first["revision"] == second["revision"]


def test_a_human_game_pauses_on_the_human_decision() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(HUMAN_FIRST, game_seed=13)

    assert summary["finished"] is False
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["owner_is_human"] is True
    assert manager.summary(_text(summary["game_id"])) == summary


def test_only_human_seats_expose_views_and_actions() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    view = manager.view(game_id, 0)
    assert view["player"] == 0
    assert view["private"] is not None
    json.dumps(view)

    listing = manager.legal_actions(game_id, 0)
    assert listing["revision"] == summary["revision"]
    actions = _rows(listing["actions"])
    assert actions
    assert [entry["index"] for entry in actions] == list(range(len(actions)))
    json.dumps(listing)

    with pytest.raises(SeatAccessError):
        manager.view(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.legal_actions(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.view(game_id, 9)


def test_legal_actions_describe_the_board_icon_they_resolve() -> None:
    # Seat 0 opens seed 21 by sending a Dagger to Assembly Hall; the space's
    # single Intrigue icon is then offered with its printed effect text.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = _text(summary["game_id"])
    placements = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert all(entry["detail"] is None for entry in placements)
    assert _obj(placements[0]["arguments"])["space_id"] == "assembly_hall"

    summary = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=0
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [
        (entry["action_id"], _obj(entry["arguments"])["effect"], entry["detail"])
        for entry in actions
        if entry["action_id"] == "resolve_board_effect"
    ] == [("resolve_board_effect", "intrigue", "Draw 1 Intrigue card")]


def test_apply_guards_revision_owner_and_index() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    revision = _int(summary["revision"])

    with pytest.raises(StaleRevisionError):
        manager.apply_action(game_id, seat=0, revision=revision + 1, index=0)
    with pytest.raises(SessionError, match="out of range"):
        manager.apply_action(game_id, seat=0, revision=revision, index=999)
    with pytest.raises(SeatAccessError):
        manager.apply_action(game_id, seat=1, revision=revision, index=0)

    advanced = manager.apply_action(game_id, seat=0, revision=revision, index=0)
    assert advanced["revision"] != revision
    if not advanced["finished"]:
        # Either the seat still decides, or its turn ended and the hand-over
        # waits for confirmation while the steps are undoable.
        assert _obj(advanced["decision"])["owner"] == 0 or advanced["confirmation"] == 0


def test_a_human_game_can_be_played_to_the_end() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])

    for _ in range(2_000):
        if summary["finished"]:
            break
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
            continue
        summary = manager.apply_action(
            game_id,
            seat=0,
            revision=_int(summary["revision"]),
            index=0,
        )
    assert summary["finished"] is True
    standings = _rows(summary["standings"])
    assert sorted(_int(entry["rank"]) for entry in standings) == [1, 2, 3, 4]


def test_a_leader_draft_game_starts_on_the_pick_frame() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(
        ("human", "human", "human", "human"),
        leader_draft=True,
        game_seed=15,
    )

    decision = _obj(summary["decision"])
    assert decision["kind"] == "leader_draft"
    listing = manager.legal_actions(_text(summary["game_id"]), _int(decision["owner"]))
    actions = _rows(listing["actions"])
    assert len(actions) == 6
    assert {entry["action_id"] for entry in actions} == {"pick_leader"}


def test_registry_agents_take_seats_and_search_agents_get_the_state() -> None:
    from dune_imperium.agents import RolloutAgent

    manager = GameSessionManager()
    seats = ("human", "rollout", "heuristic", "random")

    summary = manager.create_game(seats, game_seed=14)

    assert summary["seats"] == list(seats)
    assert _obj(summary["decision"])["owner"] == 0
    session = manager._sessions[_text(summary["game_id"])]
    assert isinstance(session.agents[1], RolloutAgent)
    # The same seed reproduces the search agent's decisions too.
    again = manager.create_game(seats, game_seed=14)
    assert again["revision"] == summary["revision"]
    assert again["decision"] == summary["decision"]


def test_a_rollout_seat_acts_between_human_turns() -> None:
    manager = GameSessionManager()
    seats = ("human", "rollout", "heuristic", "random")
    summary = manager.create_game(seats, game_seed=15)
    game_id = _text(summary["game_id"])
    human_steps = 0
    # Play seat 0's first Agent turn: the AI seats, the rollout one included,
    # then take their turns until the decision returns to the human.
    for _ in range(40):
        if summary["finished"]:
            break
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
            if _obj(summary["decision"])["owner"] == 0 and human_steps > 0:
                break
            continue
        summary = manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )
        human_steps += 1
    assert _obj(summary["decision"])["owner"] == 0
    assert _int(summary["revision"]) > human_steps
    actors = {
        entry.get("actor")
        for entry in _rows(manager.log(game_id, 0)["entries"])
        if isinstance(entry.get("actor"), int)
    }
    assert {1, 2, 3} <= actors


def test_creation_validates_seats_and_seeds() -> None:
    manager = GameSessionManager()

    with pytest.raises(SessionError, match="one seat assignment"):
        manager.create_game(("human", "heuristic"))
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.create_game(("human", "alien", "random", "random"))
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.create_game(("human", "checkpoint:", "random", "random"))
    # A checkpoint seat loads its file when the game is created.
    with pytest.raises(SessionError, match="cannot build seat 1"):
        manager.create_game(("human", "checkpoint:/nonexistent.pt", "random", "random"))
    with pytest.raises(SessionError, match="not be negative"):
        manager.create_game(ALL_AI, game_seed=-1)


def test_unknown_games_and_deletion() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(ALL_AI, game_seed=16)
    game_id = _text(summary["game_id"])

    assert [entry["game_id"] for entry in manager.list_games()] == [game_id]
    manager.delete(game_id)
    assert manager.list_games() == []
    with pytest.raises(UnknownGameError):
        manager.summary(game_id)
    with pytest.raises(UnknownGameError):
        manager.delete(game_id)


def test_shortfall_warning_reports_short_supply_outcomes() -> None:
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.core.events import GameEvent
    from dune_imperium.server.sessions import shortfall_warning

    assert shortfall_warning(None) is None
    quiet = RuleResult(state=None, events=())  # type: ignore[arg-type]
    assert shortfall_warning(quiet) is None
    short = RuleResult(
        state=None,  # type: ignore[arg-type]
        events=(
            GameEvent(
                event_id="x:specimens_short",
                kind="specimens_short",
                payload=(
                    ("generated", 1),
                    ("player", 0),
                    ("requested", 2),
                    ("short", 1),
                ),
            ),
            GameEvent(
                event_id="x:recruit_short",
                kind="troops_recruit_short",
                payload=(
                    ("player", 0),
                    ("recruited", 0),
                    ("requested", 2),
                    ("short", 2),
                ),
            ),
        ),
    )
    assert shortfall_warning(short) == (
        "supply 부족: specimen 2개 중 1개만 생성"
        " · supply 부족: troop 2개 중 0개만 recruit"
    )


def test_serialized_actions_warn_about_a_short_troop_supply() -> None:
    """OQ-049 (user request): a specimen the supply cannot provide is flagged
    on the action itself, while the action stays legal."""

    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.content.immortality.board import RESEARCH_START_ID
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.core import (
        DecisionFrame,
        GamePhase,
        GameState,
        PlayerDecision,
        PlayerState,
    )
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
    from dune_imperium.server.sessions import _serialize_action

    lab = "imperium:bene_tleilax_lab:0"
    seats = [
        PlayerState(
            player_id=0,
            hand=(lab,),
            research_space=RESEARCH_START_ID,
            troops_supply=0,
            troops_garrison=12,
        ),
        *(
            PlayerState(player_id=seat, research_space=RESEARCH_START_ID)
            for seat in range(1, 4)
        ),
    ]
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=RulesetConfig(immortality=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=tuple(seats),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, placement).state
    engine = UprisingRulesEngine()
    session = SimpleNamespace(engine=engine, state=placed)
    serialized = {
        entry["action_id"]: entry
        for entry in (
            _serialize_action(index, action, session)  # type: ignore[arg-type]
            for index, action in enumerate(engine.legal_actions(placed, 0))
        )
    }
    # Bene Tleilax Lab's specimen has no troop to take from the supply.
    assert serialized["resolve_agent_card_effect"]["warning"] == (
        "supply 부족: specimen 1개 중 0개만 생성"
    )
    assert serialized["resolve_board_effect"]["warning"] is None
