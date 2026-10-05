"""Conflict history is public server presentation, outside the observation codec.

The initial deck order is an independent oracle for the round labels. The
payload must include reset's reveal, but never the still-hidden deck tail or
reveals after a review cursor. Saving and undoing need no additional storage.
"""

from dataclasses import replace

import pytest

from dune_imperium.core.events import GameEvent
from dune_imperium.server.session_log import LoggedStep
from dune_imperium.server.sessions import GameSessionManager


def test_initial_reveal_is_present_even_when_it_predates_the_session_log() -> None:
    manager = GameSessionManager()
    game = manager.create_game(("human",) * 4, game_seed=13)
    game_id = str(game["game_id"])
    session = manager._get(game_id)
    initial = session.engine.reset(session.config, session.game_seed)
    expected = [{"round": 1, "conflict_id": initial.current_conflict_ids[0]}]
    assert not any(
        event.kind == "conflict_revealed"
        for entry in session.log
        if isinstance(entry, LoggedStep)
        for event in entry.events
    )

    view = manager.view(game_id, 0)
    assert view["conflict_history"] == expected
    assert manager.snapshot(game_id, 1)["view"] == manager.view(game_id, 1)
    assert manager.view(game_id, 1)["conflict_history"] == expected
    assert "disclosure" not in view
    # Metadata is a narrow projection; no private payload rides along.
    assert all(
        card not in str(view["conflict_history"]) for card in initial.conflict_deck
    )

    session.state = replace(
        session.state,
        event_log=(
            *session.state.event_log,
            GameEvent(
                event_id="test:private",
                kind="conflict_revealed",
                payload=(("conflict_id", initial.conflict_deck[0]), ("round", 2)),
                visible_to=(0,),
            ),
        ),
    )
    assert manager.view(game_id, 0)["conflict_history"] == expected


def test_draft_and_undo_do_not_invent_a_first_round_conflict() -> None:
    manager = GameSessionManager()
    game = manager.create_game(("human",) * 4, game_seed=13, leader_draft=True)
    game_id = str(game["game_id"])
    assert manager.view(game_id, 0)["conflict_history"] == []
    decision = game["decision"]
    assert isinstance(decision, dict)
    owner = decision["owner"]
    assert isinstance(owner, int)
    revision = game["revision"]
    assert isinstance(revision, int)
    chosen = manager.apply_action(game_id, owner, revision, 0)
    assert manager.view(game_id, owner)["conflict_history"] == []
    revision = chosen["revision"]
    assert isinstance(revision, int)
    manager.undo(game_id, owner, revision)
    assert manager.snapshot(game_id, owner)["view"] == manager.view(game_id, owner)
    assert manager.view(game_id, owner)["conflict_history"] == []


@pytest.mark.parametrize("leader_draft,epic_game", [(False, False), (True, True)])
def test_round_history_survives_awards_replay_and_save_restore(
    leader_draft: bool, epic_game: bool
) -> None:
    manager = GameSessionManager()
    game = manager.create_game(
        ("heuristic",) * 4,
        game_seed=13,
        leader_draft=leader_draft,
        epic_game=epic_game,
    )
    game_id = str(game["game_id"])
    assert game["phase"] == "finished"
    session = manager._get(game_id)
    initial = session.engine.reset(session.config, session.game_seed)
    deck = (*initial.current_conflict_ids, *initial.conflict_deck)
    expected = [
        {"round": number, "conflict_id": card}
        for number, card in enumerate(deck, start=1)
    ]
    final = manager.review_state(game_id, 0, len(session.steps))["view"]
    assert isinstance(final, dict)
    assert final["conflict_history"] == expected[: session.state.round_number]
    # Awarded cards leave the board; they retain their original round here.
    assert len(session.state.current_conflict_ids) < len(expected)

    # Find the exact step preceding and revealing round 3 independently
    # from the serialized history. No future reveal may pass the cursor.
    step = next(
        i
        for i, entry in enumerate(
            (e for e in session.log if isinstance(e, LoggedStep)), start=1
        )
        if any(
            event.kind == "conflict_revealed" and dict(event.payload)["round"] == 3
            for event in entry.events
        )
    )
    before = manager.review_state(game_id, 1, step - 1)["view"]
    after = manager.review_state(game_id, 1, step)["view"]
    assert isinstance(before, dict) and isinstance(after, dict)
    assert before["conflict_history"] == expected[:2]
    assert after["conflict_history"] == expected[:3]
    first = manager.review_state(game_id, 0, 0)["view"]
    assert isinstance(first, dict)
    assert first["conflict_history"] == ([] if leader_draft else expected[:1])

    restored = manager.restore_game(manager.save_game(game_id))
    restored_id = str(restored["game_id"])
    assert manager.review_state(restored_id, 0, len(session.steps))["view"] == final


def test_live_history_is_complete_with_an_incremental_log() -> None:
    manager = GameSessionManager()
    game = manager.create_game(
        ("human", "heuristic", "heuristic", "heuristic"), game_seed=13
    )
    game_id = str(game["game_id"])
    session = manager._get(game_id)
    deck = (*session.state.current_conflict_ids, *session.state.conflict_deck)
    initial = manager.snapshot(game_id, 0)["log"]
    assert isinstance(initial, dict)
    for _ in range(500):
        if session.state.round_number >= 3:
            break
        revision = game["revision"]
        assert isinstance(revision, int)
        game = (
            manager.confirm_turn(game_id, 0, revision)
            if game["confirmation"] == 0
            else manager.apply_action(game_id, 0, revision, 0)
        )
    else:
        raise AssertionError("the human seat never reached round 3")
    count, epoch = initial["count"], initial["epoch"]
    assert isinstance(count, int) and isinstance(epoch, str)
    snapshot = manager.snapshot(game_id, 0, log_after=count, log_epoch=epoch)
    view = snapshot["view"]
    assert isinstance(view, dict)
    assert view["conflict_history"] == [
        {"round": number, "conflict_id": card}
        for number, card in enumerate(deck[:3], start=1)
    ]
    assert "disclosure" not in view
    assert manager.view(game_id, 0) == view
    restored_id = str(manager.restore_game(manager.save_game(game_id))["game_id"])
    assert manager.view(restored_id, 0) == view
