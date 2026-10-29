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

from dune_imperium.server.sessions import GameSessionManager


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
            # A varied row, never a troop withdrawal: it only undoes a
            # deployment, and taking both in turn never ends the turn.
            picks = [
                row for row in rows if row["action_id"] != "withdraw_troops"
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
    ],
    ids=["fixed-leaders", "draft-promo"],
)
def test_an_original_game_serializes_every_step_to_its_end(
    options: dict[str, Any],
) -> None:
    steps, summary = _play(**options)
    assert summary["finished"], (steps, summary["round_number"])
    assert summary["base_game"] == "imperium"
