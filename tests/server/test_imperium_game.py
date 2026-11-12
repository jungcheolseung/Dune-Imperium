"""A whole original game through the play server (stage P5a of
docs/base-game-and-ix-plan.md).

The browser draws each step from the server's snapshot: the view, the log
and every legal action row with its words (``_serialize_action``, which
asks ``display`` for an effect's text). An original game reaches rows no
Uprising game does (the Mentat's take, the Foldspace card, Earl Memnon's
Connections), and a row without words was a server error on screen
(2026-10-29, the Mentat). So one human seat plays an original game to the
end here, taking a varied row each time, and every snapshot along the way
must serialize.
"""

import json
from typing import Any

import pytest

from dune_imperium.config import BaseGame
from dune_imperium.server.seat_kinds import seat_kind_allowed, seat_kinds_payload
from dune_imperium.server.sessions import GameSessionManager, SessionError


def _play(**options: Any) -> tuple[int, dict[str, Any]]:
    manager = GameSessionManager()
    summary: dict[str, Any] = manager.create_game(
        ("human", "heuristic", "heuristic", "heuristic"),
        base_game="imperium",
        **options,
    )
    game_id = str(summary["game_id"])
    steps = 0
    while not summary["finished"] and steps < 2000:
        json.dumps(manager.snapshot(game_id, 0))
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(
                game_id, 0, summary["revision"], undo_count=summary["undo_count"]
            )
        else:
            listed: Any = manager.legal_actions(game_id, 0)
            rows: list[dict[str, Any]] = listed["actions"]
            assert rows
            # A varied row, never a troop or dreadnought withdrawal: it only
            # undoes a deployment, and taking both in turn never ends the
            # turn (seed 9 with Rise of Ix did so with a dreadnought).
            picks = [
                row
                for row in rows
                if row["action_id"] not in ("withdraw_troops", "withdraw_dreadnoughts")
            ] or rows
            row = picks[(steps * 7) % len(picks)]
            summary = manager.apply_action(
                game_id,
                0,
                summary["revision"],
                row["index"],
                undo_count=summary["undo_count"],
            )
        steps += 1
    return steps, summary


@pytest.mark.parametrize(
    "options",
    [
        {"game_seed": 31},
        # The human seat drafts its Leader and plays the promo cards.
        {"game_seed": 5, "leader_draft": True, "promo_cards": True},
        # Rise of Ix on the original game (stage P5f): its spaces, cards and
        # pieces in every view to the end.
        {"game_seed": 9, "rise_of_ix": True},
    ],
    ids=["fixed-leaders", "draft-promo", "rise-of-ix"],
)
def test_an_original_game_serializes_every_step_to_its_end(
    options: dict[str, Any],
) -> None:
    steps, summary = _play(**options)
    assert summary["finished"], (steps, summary["round_number"])
    assert summary["base_game"] == "imperium"
    assert summary["rise_of_ix"] is bool(options.get("rise_of_ix"))


def test_an_original_table_takes_only_the_seats_of_its_row() -> None:
    # server/seat_kinds.py: the original game seats the human, heuristic and
    # random seats; since its port to the original game (stage P6), the app
    # AI at its three levels; and since 2026-11-08 the search AI, on its own
    # network. The rollout seats and a bare checkpoint stay off it.
    manager = GameSessionManager()
    for refused in ("rollout", "rollout_strong", "checkpoint:x.pt"):
        with pytest.raises(SessionError, match="cannot seat"):
            manager.create_game(
                ("human", refused, "heuristic", "heuristic"), base_game="imperium"
            )
    # The bare kind needs the server's original-game network, and an Uprising
    # one is not it (tests/server/test_search_seats.py plays the seat).
    for uprising in (None, "uprising.pt"):
        with pytest.raises(SessionError, match="no search AI"):
            GameSessionManager(search_checkpoint=uprising).create_game(
                ("human", "search", "heuristic", "heuristic"), base_game="imperium"
            )
    summary = manager.create_game(
        ("human", "app_ai", "app_ai_medium", "app_ai_easy"),
        base_game="imperium",
        game_seed=3,
    )
    assert summary["base_game"] == "imperium"
    assert summary["seats"] == ["human", "app_ai", "app_ai_medium", "app_ai_easy"]
    # Uprising takes every kind.
    assert manager.create_game(("human", "rollout", "app_ai", "app_ai"))
    payload = seat_kinds_payload()
    assert payload == {
        "uprising": None,
        "imperium": [
            "app_ai",
            "app_ai_easy",
            "app_ai_medium",
            "heuristic",
            "human",
            "random",
            "search",
        ],
    }
    kinds = ("human", "heuristic", "random", "app_ai", "rollout", "search:x.pt")
    assert all(
        seat_kind_allowed(kind, BaseGame.IMPERIUM)
        == (kind.split(":", 1)[0] in allowed)
        for kind in (*kinds, "checkpoint:x.pt")
        for allowed in [payload["imperium"]]
        if isinstance(allowed, list)
    )


def test_a_save_the_engine_cannot_set_up_is_refused_not_a_fault() -> None:
    # A save of the original game with an option it never takes (the CHOAM
    # module, plan 19.4 P7-1; Bloodlines opened in P7c, Arrakeen Scouts in P8b)
    # is refused the way a new game's setup is: a SessionError (HTTP 400),
    # never a server error.
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, base_game="imperium", game_seed=4)
    document: Any = manager.save_document(str(summary["game_id"]))
    document["ruleset"] = {**document["ruleset"], "choam_module": True}
    with pytest.raises(SessionError, match="choam_module"):
        manager.restore_game(document)
    # A save whose seats the original table does not take is refused too.
    seated: Any = manager.save_document(str(summary["game_id"]))
    seated["seats"] = ["human", "rollout", "human", "human"]
    with pytest.raises(SessionError, match="cannot seat"):
        manager.restore_game(seated)
