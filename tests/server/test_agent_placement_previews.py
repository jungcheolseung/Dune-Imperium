"""The staged turn's placements say what their two steps together do.

Stage B1 (OQ-111) asks an Agent turn as a card pick and then a space pick,
and the page sends both for one placement (static/turn.js applyPlacement).
The legal-actions payload lists every placement the card picks lead to
(``agent_placements``) with the dry run of both steps: whether the move can
be taken back, its shortfalls and its previews are those the space pick has
once its card is picked, not the card pick's own (which reveals nothing and
moves nothing). A placement itself rarely changes them (it places the Agent
and opens the turn's effects), but the page shows the whole move's badges,
as it did when a placement was one row.
"""

from typing import Any

import pytest

from dune_imperium.server.sessions import GameSessionManager

HUMANS = ("human",) * 4
# What a row says about its dry run (sessions._dry_run_fields).
DRY_RUN_FIELDS = (
    "undoable",
    "sent_by_turn_end",
    "warning",
    "shortfall",
    "strength_after",
    "reveal_preview",
    "subcommittee_preview",
)
_CARD_PICK_ARGUMENTS = ("card_id", "graft")


def _space_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in arguments.items() if k not in _CARD_PICK_ARGUMENTS}


def _payload(manager: GameSessionManager, game_id: str, seat: int) -> Any:
    """The seat's legal-actions payload, read as plain JSON data."""

    return manager.legal_actions(game_id, seat)


def _owner(manager: GameSessionManager, game_id: str) -> int:
    summary: Any = manager.summary(game_id)
    return int(summary["decision"]["owner"])


def _first_card_pick(
    seed: int, options: dict[str, bool]
) -> tuple[GameSessionManager, str]:
    """A four-human game at its first decision that offers card picks."""

    manager = GameSessionManager()
    create: Any = manager.create_game
    created: Any = create(HUMANS, game_seed=seed, **options)
    game_id = str(created["game_id"])
    for _ in range(40):
        owner = _owner(manager, game_id)
        payload = _payload(manager, game_id, owner)
        if payload["agent_placements"]:
            return manager, game_id
        manager.apply_action(
            game_id, seat=owner, revision=payload["revision"], index=0
        )
    raise AssertionError("no card pick within 40 steps")


@pytest.mark.parametrize(
    ("seed", "options"),
    [(0, {}), (3, {"bloodlines": True, "tech_module": True, "immortality": True})],
)
def test_each_placement_carries_its_space_picks_dry_run(
    seed: int, options: dict[str, bool]
) -> None:
    manager, game_id = _first_card_pick(seed, options)
    owner = _owner(manager, game_id)
    payload = _payload(manager, game_id, owner)
    rows = payload["actions"]
    entries = payload["agent_placements"]
    assert [entry["placement"] for entry in entries] == list(range(len(entries)))
    by_row: dict[int, list[dict[str, Any]]] = {}
    for entry in entries:
        assert rows[entry["index"]]["action_id"] == "choose_agent_card"
        by_row.setdefault(entry["index"], []).append(entry)
    compared = 0
    for row, of_card in by_row.items():
        pick = rows[row]
        assert pick["undoable"] is True, "a card pick reveals nothing"
        summary: Any = manager.apply_action(
            game_id, seat=owner, revision=payload["revision"], index=row
        )
        spaces = _payload(manager, game_id, owner)["actions"]
        assert {r["action_id"] for r in spaces} == {"place_agent"}
        assert len(spaces) == len(of_card)
        for entry in of_card:
            assert entry["arguments"]["card_id"] == pick["arguments"]["card_id"]
            space = next(
                r
                for r in spaces
                if r["arguments"] == _space_arguments(entry["arguments"])
            )
            for field in DRY_RUN_FIELDS:
                assert entry.get(field) == space.get(field), (field, entry, space)
            compared += 1
        manager.undo(game_id, owner, int(summary["revision"]))
    assert compared == len(entries)



@pytest.mark.parametrize("graft", [False, True])
def test_another_seat_s_log_hides_the_whole_card_pick(graft: bool) -> None:
    """OQ-111 (1): only the picking seat sees its Agent card. Other seats'
    log entries redact the pick whole -- a card the table already knows in
    hand, and the graft choice, whose key alone would say it is a graft."""

    from dune_imperium.core.actions import DomainAction
    from dune_imperium.server.session_log import LoggedStep
    from dune_imperium.server.sessions import _log_entry_json

    arguments: tuple[tuple[str, object], ...] = (
        ("card_id", "player:0:starter:dagger:0"),
    )
    if graft:
        arguments = (*arguments, ("graft", True))
    entry = LoggedStep(
        step=DomainAction("choose_agent_card", 0, arguments),  # type: ignore[arg-type]
        events=(),
        reveals=False,
        hidden_arguments=frozenset(),
        sealed=True,
    )
    own: Any = _log_entry_json(0, entry, 0, finished=False)
    assert own["arguments"] == dict(arguments)
    for seat in (1, 2, 3):
        other: Any = _log_entry_json(0, entry, seat, finished=False)
        assert other["arguments"] == {"card_id": "(비공개)"}
    review: Any = _log_entry_json(0, entry, 1, finished=True)
    assert review["arguments"] == dict(arguments)


def test_the_card_pick_is_logged_sealed() -> None:
    manager, game_id = _first_card_pick(0, {})
    owner = _owner(manager, game_id)
    payload = _payload(manager, game_id, owner)
    entry = payload["agent_placements"][0]
    manager.apply_action(
        game_id, seat=owner, revision=payload["revision"], index=entry["index"]
    )
    session = manager._get(game_id)
    logged: Any = session.log[-1]
    assert logged.step.action_id == "choose_agent_card"
    assert logged.sealed
