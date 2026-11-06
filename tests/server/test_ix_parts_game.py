"""Part of Rise of Ix beside the Tech Module through the play server
(docs/base-game-and-ix-plan.md 20.5 P8-1, OQ-165).

The server takes ``ix_tech_tiles`` and ``ix_leaders`` on a new game, names
them in the summary and keeps them in a save; it answers the combinations
``RulesetConfig`` refuses -- the Tech tiles alone with Arrakeen Scouts (user
ruling 2026-11-01), either part with all of Rise of Ix or without the Tech
Module -- as a bad request, never a server error.
"""

import json
from typing import Any

import pytest

from dune_imperium.server.persistence import parse_save_document
from dune_imperium.server.sessions import GameSessionManager, SessionError

TECH: dict[str, Any] = {"bloodlines": True, "tech_module": True}


@pytest.mark.parametrize("base_game", ["uprising", "imperium"])
def test_a_save_keeps_the_leaders_and_tech_mode(base_game: str) -> None:
    manager = GameSessionManager()
    summary: Any = manager.create_game(
        ("human",) * 4,
        base_game=base_game,
        ix_tech_tiles=True,
        ix_leaders=True,
        arrakeen_scouts=True,
        game_seed=8,
        **TECH,
    )
    assert summary["rise_of_ix"] is False
    assert summary["ix_tech_tiles"] is True
    assert summary["ix_leaders"] is True
    game_id = str(summary["game_id"])
    document: Any = json.loads(json.dumps(manager.save_document(game_id)))
    assert document["ruleset"]["ix_tech_tiles"] is True
    assert document["ruleset"]["ix_leaders"] is True
    ruleset = parse_save_document(document).replay.ruleset
    assert ruleset.ix_tech_tiles and ruleset.ix_leaders and not ruleset.rise_of_ix
    restored: Any = manager.restore_game(document)
    assert restored["ix_leaders"] is True
    assert (
        manager.snapshot(str(restored["game_id"]), 0)["view"]
        == manager.snapshot(game_id, 0)["view"]
    )


def test_a_save_without_the_new_keys_restores_as_before() -> None:
    # A save written before the options existed has neither key: it is a
    # game without them, restored to the same state (its replay reproduces
    # its recorded state hash; the options are left out of the hash at their
    # default).
    manager = GameSessionManager()
    summary: Any = manager.create_game(
        ("human",) * 4, rise_of_ix=True, arrakeen_scouts=True, game_seed=8, **TECH
    )
    game_id = str(summary["game_id"])
    document: Any = json.loads(json.dumps(manager.save_document(game_id)))
    legacy = {
        key: value
        for key, value in document["ruleset"].items()
        if key not in ("ix_tech_tiles", "ix_leaders")
    }
    old: Any = {**document, "ruleset": legacy}
    ruleset = parse_save_document(old).replay.ruleset
    assert not ruleset.ix_tech_tiles and not ruleset.ix_leaders
    restored: Any = manager.restore_game(old)
    assert restored["ix_tech_tiles"] is False
    assert (
        manager.snapshot(str(restored["game_id"]), 0)["view"]
        == manager.snapshot(game_id, 0)["view"]
    )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({**TECH, "ix_tech_tiles": True, "arrakeen_scouts": True}, "Arrakeen Scouts"),
        ({**TECH, "ix_tech_tiles": True, "rise_of_ix": True}, "all of Rise of Ix"),
        ({"bloodlines": True, "ix_tech_tiles": True}, "Tech Module"),
        ({**TECH, "ix_leaders": True}, "only its Tech tiles"),
    ],
    ids=["tiles-with-scouts", "with-all-of-ix", "without-tech", "leaders-alone"],
)
def test_a_refused_part_is_a_bad_request(options: dict[str, Any], message: str) -> None:
    manager = GameSessionManager()
    with pytest.raises(SessionError, match=message):
        manager.create_game(("human",) * 4, **options)
