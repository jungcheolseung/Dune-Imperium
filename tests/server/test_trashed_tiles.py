"""Each seat's trashed Skill and Tech tiles, for the seat panel's details.

The state keeps one trash of each for the table; the view names whose tile
each was from the public ``skill_trashed`` and ``tech_trashed`` events
(sessions.py ``_trashed_tiles``, play feedback 2026-10-26), a Skill by its
copy. An event shown to some seats only is never projected, and a real
trash names the seat that owned the tile.
"""

from dataclasses import replace
from typing import Any, cast

from tests.unit.rules import test_tech as tech

from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.events import GameEvent
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.server.sessions import GameSessionManager, _serialize_view


def _players(
    manager: GameSessionManager, game_id: str, seat: int
) -> dict[int, dict[str, Any]]:
    players = cast(list[dict[str, Any]], manager.view(game_id, seat)["players"])
    return {int(p["player"]): p for p in players}


def _event(
    kind: str,
    player: int,
    field: str,
    tile: str,
    visible_to: tuple[int, ...] | None = None,
) -> GameEvent:
    return GameEvent(
        event_id=f"test:{kind}:{player}:{tile}",
        kind=kind,
        payload=(("player", player), (field, tile)),
        visible_to=visible_to,
    )


def test_each_seat_lists_the_tiles_it_trashed_in_order() -> None:
    manager = GameSessionManager()
    game = manager.create_game(
        ("human",) * 4, game_seed=13, bloodlines=True, tech_module=True
    )
    game_id = str(game["game_id"])
    for seat in range(4):
        for p in _players(manager, game_id, seat).values():
            assert p["trashed_skill_ids"] == p["trashed_tech_ids"] == []

    session = manager._get(game_id)
    session.state = replace(
        session.state,
        event_log=(
            *session.state.event_log,
            _event("skill_trashed", 1, "skill_instance_id", "skill:canny:0"),
            _event("tech_trashed", 2, "tech_id", "forbidden_weapons"),
            _event("tech_trashed", 2, "tech_id", "plasteel_blades"),
            _event("skill_trashed", 1, "skill_instance_id", "skill:canny:1"),
            # Shown to one seat only: never in anyone's view.
            _event("tech_trashed", 3, "tech_id", "glowglobes", visible_to=(3,)),
        ),
    )
    for seat in range(4):
        players = _players(manager, game_id, seat)
        assert players[1]["trashed_skill_ids"] == ["skill:canny:0", "skill:canny:1"]
        assert players[2]["trashed_tech_ids"] == [
            "forbidden_weapons",
            "plasteel_blades",
        ]
        assert players[1]["trashed_tech_ids"] == []
        assert players[0]["trashed_skill_ids"] == players[0]["trashed_tech_ids"] == []
        assert players[3]["trashed_tech_ids"] == []


def test_a_real_forbidden_weapons_trash_names_its_owner() -> None:
    owner = tech._tech_owner(
        "forbidden_weapons", hand=starting_deck_instance_ids(0)[:5]
    )
    state = tech._reveal(tech._turn_state(owner, stacks=((), (), ()))).state
    engine = UprisingRulesEngine()
    # Forbidden Weapons' "lose all spice and trash this tile", as the engine
    # serves it.
    trash = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("option") == "trash"
    )
    after = engine.apply(state, trash).state
    assert after.tech_trash == ("forbidden_weapons",)
    for seat in range(4):
        view = _serialize_view(engine.observe(after, seat), after)
        players = cast(list[dict[str, Any]], view["players"])
        assert [p["trashed_tech_ids"] for p in players] == [
            ["forbidden_weapons"],
            [],
            [],
            [],
        ]
