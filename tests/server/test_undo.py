"""Tests for action undo and the session log (M11 slice 6, OQ-010 boundary)."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GameState, PlayerState
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.events import GameEvent
from dune_imperium.server.persistence import SAVE_FORMAT_VERSION
from dune_imperium.server.session_log import (
    LoggedStep,
    LoggedUndo,
    reveals_hidden_information,
    undo_window,
)
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    _log_entry_json,
)

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


def _play(
    manager: GameSessionManager, summary: JsonObject, index: int = 0
) -> JsonObject:
    return manager.apply_action(
        str(summary["game_id"]),
        seat=0,
        revision=_int(summary["revision"]),
        index=index,
    )


def _play_until_revision(
    manager: GameSessionManager, summary: JsonObject, revision: int
) -> JsonObject:
    while _int(summary["revision"]) < revision:
        summary = _play(manager, summary)
    assert summary["revision"] == revision
    return summary


def _live_log(manager: GameSessionManager, game_id: str) -> list[LoggedStep]:
    return [
        entry
        for entry in manager._get(game_id).log
        if isinstance(entry, LoggedStep) and not entry.undone
    ]


# ---------------------------------------------------------------- boundary


def _state(**players: PlayerState) -> GameState:
    seats = tuple(
        players.get(f"p{seat}", PlayerState(player_id=seat)) for seat in range(4)
    )
    return GameState(config=RulesetConfig(), seed=1, players=seats)


def test_reveal_detection_follows_the_information_flow_rules() -> None:
    # Playing an Intrigue only discloses a card its owner alone knew: the
    # actor's own loss, so it does not close the undo window (user ruling).
    before = _state(p0=PlayerState(player_id=0, intrigue_cards=("intrigue:x",)))
    after = replace(
        _state(p0=PlayerState(player_id=0)), intrigue_discard=("intrigue:x",)
    )
    assert reveals_hidden_information(before, after, actor=0) is False
    # ...but for anyone else it is a reveal, and so it is for chance (no actor).
    assert reveals_hidden_information(before, after, actor=1) is True
    assert reveals_hidden_information(before, after, actor=None) is True

    # Drawing from the own deck reveals the deck top to the drawer: undoing
    # would let them choose again knowing it.
    before = _state(p0=PlayerState(player_id=0, deck=("a", "b")))
    after = _state(p0=PlayerState(player_id=0, deck=("b",), hand=("a",)))
    assert reveals_hidden_information(before, after, actor=0) is True

    # Revealing the hand (hand -> in play) is the actor's own disclosure.
    before = _state(p0=PlayerState(player_id=0, hand=("a", "b")))
    after = _state(p0=PlayerState(player_id=0, in_play=("a", "b")))
    assert reveals_hidden_information(before, after, actor=0) is False

    # An opponent's hidden card becoming public is a reveal for the actor.
    before = _state(p1=PlayerState(player_id=1, hand=("c",)))
    after = _state(p1=PlayerState(player_id=1, discard_pile=("c",)))
    assert reveals_hidden_information(before, after, actor=0) is True
    assert reveals_hidden_information(before, after, actor=1) is False

    # The Imperium Row refilling from the deck reveals a card to everyone.
    before = replace(_state(), imperium_deck=("imp:1", "imp:2"))
    after = replace(_state(), imperium_deck=("imp:2",), imperium_row=("imp:1",))
    assert reveals_hidden_information(before, after, actor=0) is True

    # A card entering a hand through a public move stays public: no reveal.
    before = replace(_state(), imperium_row=("imp:1",))
    after = _state(p0=PlayerState(player_id=0, hand=("imp:1",), hand_public=("imp:1",)))
    assert reveals_hidden_information(before, after, actor=0) is False


def test_undo_window_holds_own_consecutive_steps_and_closes_on_reveals() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = str(summary["game_id"])
    # Seat 0 is first player: nothing to undo before the first action.
    assert summary["first_player"] == 0
    assert summary["undo"] == []
    assert summary["log_count"] == len(manager._get(game_id).log)

    summary = _play(manager, summary)
    assert summary["undo"] == [{"seat": 0, "steps": 1}]

    # The AI seats act next, which closes the window; the human's next
    # three consecutive choices reopen and grow it.
    summary = _play_until_revision(manager, summary, 11)
    assert summary["undo"] == []
    summary = _play_until_revision(manager, summary, 14)
    assert summary["undo"] == [{"seat": 0, "steps": 3}]
    live = _live_log(manager, game_id)
    assert [entry.actor for entry in live[-3:]] == [0, 0, 0]
    assert not any(entry.reveals for entry in live[-3:])

    # The next step resolves a board effect that draws a card: the deck top
    # is now known to the drawer, so that step (and everything before it)
    # can no longer be taken back.
    summary = _play(manager, summary)
    assert summary["revision"] == 15
    live = _live_log(manager, game_id)
    assert live[-1].actor == 0
    assert isinstance(live[-1].step, DomainAction)
    assert live[-1].step.action_id == "resolve_board_effect"
    assert live[-1].reveals is True
    assert summary["undo"] == []
    assert undo_window(manager._get(game_id).log, 0) == 0


# ---------------------------------------------------------------- undo


def test_undo_rewinds_to_the_seats_earlier_decision_and_keeps_the_log() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 8)
    view_before = manager.view(game_id, 0)
    actions_before = manager.legal_actions(game_id, 0)
    steps_before = list(manager._get(game_id).steps)
    summary = _play(manager, summary)
    assert summary["revision"] == 9
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    undone_step = manager._get(game_id).steps[-1]

    with pytest.raises(StaleRevisionError):
        manager.undo(game_id, seat=0, revision=8, steps=1)
    with pytest.raises(SessionError, match="at most 2"):
        manager.undo(game_id, seat=0, revision=9, steps=3)
    with pytest.raises(SessionError, match="at most"):
        manager.undo(game_id, seat=0, revision=9, steps=0)
    with pytest.raises(SeatAccessError):
        manager.undo(game_id, seat=1, revision=9, steps=1)

    assert summary["undo_count"] == 0
    rewound = manager.undo(game_id, seat=0, revision=9, steps=1, undo_count=0)

    assert rewound["revision"] == 8
    assert rewound["undo_count"] == 1
    assert rewound["undo"] == [{"seat": 0, "steps": 1}]
    assert manager.view(game_id, 0) == view_before
    assert manager.legal_actions(game_id, 0) == actions_before
    session = manager._get(game_id)
    assert session.steps == steps_before
    # The taken-back step stays in the log, flagged, behind its marker.
    assert session.log[-1] == LoggedUndo(seat=0, count=1)
    flagged = session.log[-2]
    assert isinstance(flagged, LoggedStep)
    assert flagged.undone is True
    assert flagged.step == undone_step
    assert rewound["log_count"] == len(session.log)

    # A different choice continues the game from the rewound decision.
    assert len(_rows(actions_before["actions"])) >= 2
    resumed = _play(manager, rewound, index=1)
    assert _int(resumed["revision"]) >= 9
    assert manager._get(game_id).steps[len(steps_before)] != undone_step

    # The undo generation guards a stale client: a request carrying the
    # pre-undo generation is refused even when its revision matches again.
    stale_revision = _int(resumed["revision"])
    with pytest.raises(StaleRevisionError, match="undo generation"):
        manager.apply_action(
            game_id, seat=0, revision=stale_revision, index=0, undo_count=0
        )
    with pytest.raises(StaleRevisionError, match="undo generation"):
        manager.undo(game_id, seat=0, revision=stale_revision, undo_count=0)
    manager.apply_action(
        game_id, seat=0, revision=stale_revision, index=0, undo_count=1
    )

    # Log projection: the live steps are exactly the non-undone entries.
    live = _live_log(manager, game_id)
    assert [entry.step for entry in live] == manager._get(game_id).steps


def test_the_log_is_served_per_seat_with_undo_markers() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 9)
    summary = manager.undo(game_id, seat=0, revision=9, steps=1)

    log = manager.log(game_id, 0)
    entries = _rows(log["entries"])
    assert log["count"] == len(entries) == summary["log_count"]
    assert [entry["index"] for entry in entries] == list(range(len(entries)))
    assert entries[-1] == {
        "index": len(entries) - 1,
        "type": "undo",
        "seat": 0,
        "count": 1,
    }
    undone = entries[-2]
    assert undone["type"] == "action" and undone["undone"] is True
    assert undone["actor"] == 0
    assert all(entry["undone"] is False for entry in entries[:-2])
    kinds = {entry["type"] for entry in entries}
    assert kinds == {"action", "undo"}
    assert any(_rows(entry["events"]) for entry in entries if entry["type"] == "action")

    tail = manager.log(game_id, 0, after=len(entries) - 2)
    assert [entry["index"] for entry in _rows(tail["entries"])] == [
        len(entries) - 2,
        len(entries) - 1,
    ]
    with pytest.raises(SessionError, match="out of range"):
        manager.log(game_id, 0, after=len(entries) + 1)
    with pytest.raises(SeatAccessError):
        manager.log(game_id, 1)


def test_log_entries_redact_hidden_arguments_and_private_events() -> None:
    step = DomainAction(
        action_id="choose_intrigue_discard",
        actor=1,
        arguments=(("card_id", "imp:secret"),),
    )
    entry = LoggedStep(
        step=step,
        events=(
            GameEvent(event_id="e:public", kind="card_discarded", payload=()),
            GameEvent(event_id="e:private", kind="cards_drawn", visible_to=(1,)),
        ),
        reveals=False,
        hidden_arguments=frozenset({"imp:secret"}),
    )

    for_owner = _log_entry_json(3, entry, seat=1, finished=False)
    assert for_owner["arguments"] == {"card_id": "imp:secret"}
    assert [_obj(event)["kind"] for event in _rows(for_owner["events"])] == [
        "card_discarded",
        "cards_drawn",
    ]

    for_other = _log_entry_json(3, entry, seat=0, finished=False)
    assert for_other["arguments"] == {"card_id": "(비공개)"}
    assert [_obj(event)["kind"] for event in _rows(for_other["events"])] == [
        "card_discarded"
    ]

    # Post-game full disclosure (OQ-010 ruling 4) lifts every redaction.
    disclosed = _log_entry_json(3, entry, seat=0, finished=True)
    assert disclosed["arguments"] == {"card_id": "imp:secret"}
    assert len(_rows(disclosed["events"])) == 2

    chance = LoggedStep(
        step=ChanceOutcome("draw:1", ("a", "b")),
        events=(),
        reveals=True,
        hidden_arguments=frozenset(),
    )
    assert "values" not in _log_entry_json(0, chance, seat=0, finished=False)
    assert _log_entry_json(0, chance, seat=0, finished=True)["values"] == ["a", "b"]


# ---------------------------------------------------------------- saves


def _game_with_an_undo(manager: GameSessionManager) -> JsonObject:
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 9)
    summary = manager.undo(game_id, seat=0, revision=9, steps=1)
    return _play(manager, summary, index=1)


def test_saves_carry_the_undo_history_and_restore_the_same_log() -> None:
    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    game_id = str(summary["game_id"])

    document = manager.save_game(game_id)
    assert document["format_version"] == SAVE_FORMAT_VERSION == 2
    saved_log = _rows(document["log"])
    assert any(entry.get("type") == "undo" for entry in saved_log)
    assert any(entry.get("undone") is True for entry in saved_log)
    live_entries = [
        entry
        for entry in saved_log
        if entry.get("type") != "undo" and not entry["undone"]
    ]
    assert len(_rows(document["steps"])) == len(live_entries)

    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["revision"] == summary["revision"]
    assert restored["undo_count"] == summary["undo_count"] == 1
    assert restored["undo"] == summary["undo"]
    assert restored["log_count"] == summary["log_count"]
    original = manager.log(game_id, 0)["entries"]
    assert manager.log(restored_id, 0)["entries"] == original
    assert manager._get(restored_id).log == manager._get(game_id).log


def test_version_one_saves_still_load_without_undo_history() -> None:
    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    document = manager.save_game(str(summary["game_id"]))
    legacy = {key: value for key, value in document.items() if key != "log"}
    legacy["format_version"] = 1

    restored = manager.restore_game(legacy)

    session = manager._get(str(restored["game_id"]))
    assert restored["revision"] == summary["revision"]
    assert restored["undo_count"] == 0
    assert all(isinstance(entry, LoggedStep) for entry in session.log)
    assert [entry.step for entry in session.log if isinstance(entry, LoggedStep)] == (
        session.steps
    )


def test_tampered_logs_are_rejected() -> None:
    from dune_imperium.server.persistence import SaveError

    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    document = manager.save_game(str(summary["game_id"]))
    log = _rows(document["log"])

    marker_index = next(i for i, entry in enumerate(log) if entry.get("type") == "undo")
    wrong_count = list(log)
    wrong_count[marker_index] = {**log[marker_index], "count": 2}
    with pytest.raises(SaveError, match="undo marker count"):
        manager.restore_game({**document, "log": wrong_count})

    reordered = list(log)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(SaveError, match="does not match recorded step"):
        manager.restore_game({**document, "log": reordered})

    with pytest.raises(SaveError, match="save log must be a list"):
        manager.restore_game({**document, "log": None})


# ---------------------------------------------------------------- review


def test_review_reports_where_steps_were_taken_back() -> None:
    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    game_id = str(summary["game_id"])
    for _ in range(3_000):
        if summary["finished"]:
            break
        summary = _play(manager, summary)
    assert summary["finished"] is True

    review = manager.review(game_id, 0)
    history = _rows(review["undo_history"])
    assert len(history) == 1
    assert history[0]["seat"] == 0
    assert history[0]["count"] == 1
    # The undo rewound to live step 8 (revision 8 = eight steps applied).
    assert history[0]["step"] == 8
    undone = _rows(history[0]["undone"])
    assert len(undone) == 1
    assert undone[0]["type"] == "action" and undone[0]["actor"] == 0
    assert _rows(review["steps"])[8] != undone[0]
