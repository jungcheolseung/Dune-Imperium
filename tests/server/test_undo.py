"""Tests for action undo and the session log (M11 slice 6, OQ-010 boundary)."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GameState, PlayerState
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.events import GameEvent
from dune_imperium.core.replay import ReplayStep
from dune_imperium.server.persistence import SAVE_FORMAT_VERSION
from dune_imperium.server.session_log import (
    LoggedStep,
    LoggedUndo,
    reveals_hidden_information,
    undo_history,
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

# The AI seats play the rubric-priced 2026-09-10 table pinned in the registry,
# not ``heuristic``: the scripted revisions below follow that table's moves,
# and ``heuristic`` is retuned as the baseline improves (2026-09-11 demoted
# three spaces and every scripted revision moved). The undo mechanics under
# test do not depend on which table the AI seats use.
HUMAN_FIRST = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _play_raw(
    manager: GameSessionManager, summary: JsonObject, index: int = 0
) -> JsonObject:
    """Apply one action of seat 0 without confirming a paused turn end."""

    return manager.apply_action(
        str(summary["game_id"]),
        seat=0,
        revision=_int(summary["revision"]),
        index=index,
    )


def _play(
    manager: GameSessionManager, summary: JsonObject, index: int = 0
) -> JsonObject:
    """Apply one action of seat 0 and confirm the turn end if it paused."""

    summary = _play_raw(manager, summary, index)
    if summary["confirmation"] == 0:
        summary = manager.confirm_turn(
            str(summary["game_id"]),
            seat=0,
            revision=_int(summary["revision"]),
            undo_count=_int(summary["undo_count"]),
        )
    return summary


def _action_index(manager: GameSessionManager, game_id: str, action_id: str) -> int:
    return next(
        _int(entry["index"])
        for entry in _rows(manager.legal_actions(game_id, 0)["actions"])
        if entry["action_id"] == action_id
    )


def _play_until_revision(
    manager: GameSessionManager, summary: JsonObject, revision: int
) -> JsonObject:
    while _int(summary["revision"]) < revision:
        summary = _play(manager, summary)
    assert summary["revision"] == revision
    return summary


def _play_until_window_closes(
    manager: GameSessionManager, summary: JsonObject
) -> JsonObject:
    """Play seat 0 until an AI seat's turn has closed its undo window."""

    for _ in range(40):
        summary = _play(manager, summary)
        if summary["undo"] == []:
            return summary
    raise AssertionError("the undo window never closed")


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


def test_a_starting_card_removed_by_a_leader_pick_is_not_a_reveal() -> None:
    # Limited Allies: "You start the game without Diplomacy in your deck"
    # [Staban Tuek card]. The pick takes the card out of a face-down deck
    # whose ten cards everybody knows, and shows nobody where it sat.
    diplomacy = "player:0:starter:diplomacy:0"
    dagger = "player:0:starter:dagger:0"
    before = _state(p0=PlayerState(player_id=0, deck=(dagger, diplomacy)))
    after = _state(
        p0=PlayerState(player_id=0, leader_id="staban_tuek", deck=(dagger,))
    )
    assert reveals_hidden_information(before, after, actor=0) is False

    # Only the card the printed rule names, and only as that Leader is picked.
    lost_dagger = _state(
        p0=PlayerState(player_id=0, leader_id="staban_tuek", deck=(diplomacy,))
    )
    assert reveals_hidden_information(before, lost_dagger, actor=0) is True
    other_leader = _state(
        p0=PlayerState(player_id=0, leader_id="lady_jessica", deck=(dagger,))
    )
    assert reveals_hidden_information(before, other_leader, actor=0) is True
    picked = _state(
        p0=PlayerState(
            player_id=0, leader_id="staban_tuek", deck=(dagger, diplomacy)
        )
    )
    assert reveals_hidden_information(picked, after, actor=0) is True
    # Drawing it instead is still the drawer learning their deck top.
    drawn = _state(
        p0=PlayerState(
            player_id=0, leader_id="staban_tuek", deck=(dagger,), hand=(diplomacy,)
        )
    )
    assert reveals_hidden_information(before, drawn, actor=0) is True


def test_every_draft_pick_but_the_last_can_be_taken_back() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    picker = _int(_obj(summary["decision"])["owner"])
    deck_before = manager._get(game_id).state.players[picker].deck

    actions = _rows(manager.legal_actions(game_id, picker)["actions"])
    leaders = [_obj(entry["arguments"])["leader_id"] for entry in actions]
    assert "staban_tuek" in leaders
    assert all(entry["undoable"] is True for entry in actions)

    summary = manager.apply_action(
        game_id,
        seat=picker,
        revision=_int(summary["revision"]),
        index=leaders.index("staban_tuek"),
    )
    assert summary["undo"] == [{"seat": picker, "steps": 1}]
    assert len(manager._get(game_id).state.players[picker].deck) == 9

    rewound = manager.undo(game_id, seat=picker, revision=_int(summary["revision"]))
    assert _obj(rewound["decision"])["owner"] == picker
    assert manager._get(game_id).state.players[picker].deck == deck_before


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

    # From here the window is checked as a property of the log rather than at
    # scripted revisions: it must always equal the trailing run of seat 0's own
    # steps that revealed nothing. The AI seats are heuristics, so retuning
    # their preferences changes how many steps their turns take and which
    # choices seat 0 is offered next -- but never this invariant.
    widest = 0
    closed_by_a_reveal = False
    for _ in range(60):
        summary = _play(manager, summary)
        live = _live_log(manager, game_id)
        expected = 0
        for entry in reversed(live):
            if entry.actor != 0 or entry.reveals:
                break
            expected += 1
        assert summary["undo"] == (
            [] if expected == 0 else [{"seat": 0, "steps": expected}]
        )
        assert undo_window(manager._get(game_id).log, 0) == expected
        widest = max(widest, expected)
        if expected == 0 and live[-1].actor == 0 and live[-1].reveals:
            closed_by_a_reveal = True

    # The run has to have exercised both halves, or the invariant above held
    # only because the window never opened.
    assert widest >= 2, "seat 0 never accumulated consecutive undoable steps"
    assert closed_by_a_reveal, "no revealing step ever closed the window"


# ---------------------------------------------------------------- turn end


def test_turn_end_waits_for_confirmation_while_steps_are_undoable() -> None:
    # Seat 0 (seed 14) sends Diplomacy to Dutiful Service, takes the Solari
    # icon and then the Emperor Influence: the turn is over, nothing was
    # revealed, so the session pauses instead of letting the AI seats act.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 12)
    summary = _play_raw(manager, summary)
    assert summary["confirmation"] is None
    influence = _action_index(manager, game_id, "resolve_faction_influence")
    summary = _play_raw(manager, summary, index=influence)

    assert summary["revision"] == 14
    assert summary["confirmation"] == 0
    assert _obj(summary["decision"])["owner"] != 0
    assert summary["undo"] == [{"seat": 0, "steps": 3}]
    assert len(manager._get(game_id).steps) == 14
    assert manager.legal_actions(game_id, 0)["actions"] == []
    with pytest.raises(SessionError, match="another seat"):
        manager.apply_action(game_id, seat=0, revision=14, index=0)
    with pytest.raises(StaleRevisionError):
        manager.confirm_turn(game_id, seat=0, revision=13)

    # Taking a step back reopens the seat's own decision.
    rewound = manager.undo(game_id, seat=0, revision=14, steps=1)
    assert rewound["confirmation"] is None
    assert _obj(rewound["decision"])["owner"] == 0
    assert rewound["revision"] == 13

    # Redo the same step and confirm: only now do the other seats act.
    summary = _play_raw(manager, rewound, index=influence)
    assert summary["confirmation"] == 0
    confirmed = manager.confirm_turn(
        game_id, seat=0, revision=14, undo_count=_int(summary["undo_count"])
    )
    assert confirmed["confirmation"] is None
    assert _int(confirmed["revision"]) > 14
    assert confirmed["undo"] == []
    with pytest.raises(SessionError, match="no turn end"):
        manager.confirm_turn(game_id, seat=0, revision=_int(confirmed["revision"]))


def test_a_turn_ending_in_a_reveal_still_waits_for_its_press() -> None:
    # Seed 21's opening turn ends with Assembly Hall's Intrigue draw, which
    # reveals the deck top to the drawer and closes the undo window -- but
    # every turn end of a human seat still waits for its own press
    # (2026-09-23): ``resolve_board_effect`` is not one of the four
    # explicit turn-end actions (``EXPLICIT_TURN_ENDS``), so it holds like
    # any other step that ends the seat's unit, even with nothing left to
    # protect.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = str(summary["game_id"])
    summary = _play_raw(manager, summary)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [(entry["action_id"], entry["undoable"]) for entry in actions] == [
        ("resolve_board_effect", False)
    ]
    summary = _play_raw(manager, summary)

    assert summary["confirmation"] == 0
    assert summary["undo"] == []
    assert _obj(summary["decision"])["owner"] != 0
    assert manager.legal_actions(game_id, 0)["actions"] == []

    confirmed = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert confirmed["confirmation"] is None
    assert _int(confirmed["revision"]) > _int(summary["revision"])


def test_legal_actions_report_whether_each_step_can_be_taken_back() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 12)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])

    # Dutiful Service's Solari icon and the Emperor Influence reveal nothing.
    assert {entry["action_id"]: entry["undoable"] for entry in actions} == {
        "resolve_board_effect": True,
        "resolve_faction_influence": True,
    }


def test_a_save_taken_during_the_pause_restores_the_pause() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 12)
    summary = _play_raw(manager, summary)
    influence = _action_index(manager, game_id, "resolve_faction_influence")
    summary = _play_raw(manager, summary, index=influence)
    assert summary["confirmation"] == 0

    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    assert restored["confirmation"] == 0
    assert restored["revision"] == 14
    assert restored["undo"] == [{"seat": 0, "steps": 3}]


# ---------------------------------------------------------------- undo


def test_undo_rewinds_to_the_seats_earlier_decision_and_keeps_the_log() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 12)
    view_before = manager.view(game_id, 0)
    actions_before = manager.legal_actions(game_id, 0)
    steps_before = list(manager._get(game_id).steps)
    summary = _play(manager, summary)
    assert summary["revision"] == 13
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    undone_step = manager._get(game_id).steps[-1]

    with pytest.raises(StaleRevisionError):
        manager.undo(game_id, seat=0, revision=12, steps=1)
    with pytest.raises(SessionError, match="at most 2"):
        manager.undo(game_id, seat=0, revision=13, steps=3)
    with pytest.raises(SessionError, match="at most"):
        manager.undo(game_id, seat=0, revision=13, steps=0)
    with pytest.raises(SeatAccessError):
        manager.undo(game_id, seat=1, revision=13, steps=1)

    assert summary["undo_count"] == 0
    rewound = manager.undo(game_id, seat=0, revision=13, steps=1, undo_count=0)

    assert rewound["revision"] == 12
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
    assert _int(resumed["revision"]) >= 13
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
    summary = _play_until_revision(manager, summary, 12)
    summary = manager.undo(game_id, seat=0, revision=12, steps=1)

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
    summary = _play_until_revision(manager, summary, 12)
    summary = manager.undo(game_id, seat=0, revision=12, steps=1)
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


def _game_with_two_single_step_undos(
    manager: GameSessionManager,
) -> tuple[JsonObject, list[ReplayStep]]:
    """Seed 14 at revision 13: seat 0 takes back its two steps one at a time.

    The second undo flags a step logged before the first undo's marker, so
    the log ends ``A(undone), B(undone), undo(1), undo(1)``: a marker takes
    back the latest live steps when it is logged, not the entries right
    before it.
    """

    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 12)
    summary = _play(manager, summary)
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    taken_back = list(manager._get(game_id).steps[-2:])
    summary = manager.undo(game_id, seat=0, revision=13, steps=1, undo_count=0)
    summary = manager.undo(game_id, seat=0, revision=12, steps=1, undo_count=1)
    return summary, taken_back


def test_two_single_step_undos_in_a_row_save_and_restore() -> None:
    manager = GameSessionManager()
    summary, (first, second) = _game_with_two_single_step_undos(manager)
    game_id = str(summary["game_id"])
    tail = manager._get(game_id).log[-4:]
    assert [entry.step for entry in tail if isinstance(entry, LoggedStep)] == [
        first,
        second,
    ]
    assert all(entry.undone for entry in tail if isinstance(entry, LoggedStep))
    assert tail[2:] == [LoggedUndo(seat=0, count=1), LoggedUndo(seat=0, count=1)]

    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["revision"] == summary["revision"] == 11
    assert restored["undo_count"] == summary["undo_count"] == 2
    assert restored["undo"] == summary["undo"]
    assert manager._get(restored_id).log == manager._get(game_id).log

    # Both copies go on the same way from the rewound decision.
    assert _play(manager, restored, index=1)["revision"] == (
        _play(manager, summary, index=1)["revision"]
    )


def test_undo_history_names_each_single_step_undo_separately() -> None:
    manager = GameSessionManager()
    summary, (first, second) = _game_with_two_single_step_undos(manager)
    history = undo_history(manager._get(str(summary["game_id"])).log)

    # Both undos rewound the timeline that stands to its eleventh live step:
    # the first took back the later step, the second the earlier one.
    assert [(position, marker.count) for position, marker, _ in history] == [
        (11, 1),
        (11, 1),
    ]
    assert [[entry.step for entry in undone] for _, _, undone in history] == [
        [second],
        [first],
    ]


def test_an_undo_across_a_new_step_restores_with_its_own_steps() -> None:
    # Undo one step, take a different one, then undo both live steps of the
    # window at once: the marker takes back the step logged before the
    # earlier marker and the new one after it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 12)
    summary = _play(manager, summary)
    first = manager._get(game_id).steps[-2]
    summary = manager.undo(game_id, seat=0, revision=13, steps=1, undo_count=0)
    summary = _play_raw(manager, summary, index=1)
    replacement = manager._get(game_id).steps[-1]
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    summary = manager.undo(
        game_id,
        seat=0,
        revision=_int(summary["revision"]),
        steps=2,
        undo_count=_int(summary["undo_count"]),
    )

    history = undo_history(manager._get(game_id).log)
    assert [[entry.step for entry in undone] for _, _, undone in history][-1] == [
        first,
        replacement,
    ]
    restored = manager.restore_game(manager.save_game(game_id))
    assert manager._get(str(restored["game_id"])).log == manager._get(game_id).log


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

    wrong_seat = list(log)
    wrong_seat[marker_index] = {**log[marker_index], "seat": 1}
    with pytest.raises(SaveError, match="takes back another seat's step"):
        manager.restore_game({**document, "log": wrong_seat})

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
    # The undo rewound to live step 11 (revision 11 = eleven steps applied).
    assert history[0]["step"] == 11
    undone = _rows(history[0]["undone"])
    assert len(undone) == 1
    assert undone[0]["type"] == "action" and undone[0]["actor"] == 0
    assert _rows(review["steps"])[11] != undone[0]


# ------------------------------------------------- a confirmed hand-over


def test_a_confirmed_turn_end_stays_handed_over_to_the_next_human() -> None:
    # ``confirm_turn`` promises to close the seat's undo window. The log
    # closes it at the next chance outcome or other seat's step, but when
    # the next seat is a human who has not moved yet there is no such step:
    # the seat that confirmed could take the turn back from under them
    # (found by the slice 5 review; two browsers make it visible).
    #
    # A hold's undo window is not always open to begin with (2026-09-23:
    # every turn end waits for its press, whether or not it left anything
    # undoable) -- only a hold that *does* start with an open window
    # exercises the sealing this test is about, so the others are skipped
    # rather than asserted on.
    manager = GameSessionManager()
    seats = ("human", "human", HUMAN_FIRST[1], HUMAN_FIRST[1])
    summary = manager.create_game(seats, game_seed=7)
    game_id = str(summary["game_id"])

    checked = 0
    for _ in range(400):
        if summary["finished"] or checked >= 3:
            break
        revision = _int(summary["revision"])
        held = summary["confirmation"]
        if not isinstance(held, int):
            owner = _int(_obj(summary["decision"])["owner"])
            summary = manager.apply_action(game_id, owner, revision, 0)
            continue
        before = [row for row in _rows(summary["undo"]) if row["seat"] == held]
        summary = manager.confirm_turn(game_id, held, revision)
        if not before:
            continue
        successor = _int(_obj(summary["decision"])["owner"])
        if seats[successor] != "human" or _int(summary["revision"]) != revision:
            # AI seats (or a chance outcome) followed: the log closed the
            # window by itself, which the tests above cover.
            continue
        # The decision went straight to the other human: nothing was logged
        # after the confirmation, and still the confirmed steps are sealed.
        assert successor != held
        assert [row for row in _rows(summary["undo"]) if row["seat"] == held] == []
        with pytest.raises(SessionError, match="at most 0 step"):
            manager.undo(game_id, held, _int(summary["revision"]))
        assert manager.summary(game_id)["undo_count"] == summary["undo_count"]
        checked += 1
        # The successor's own steps open a window of their own as before.
        summary = manager.apply_action(
            game_id, successor, _int(summary["revision"]), 0
        )
        own = [row for row in _rows(summary["undo"]) if row["seat"] == successor]
        if not summary["finished"] and own:
            assert _int(own[0]["steps"]) == 1
    assert checked >= 1, "no human-to-human confirmation was reached"
