"""Read the play server's save files as records (docs/human-records.md).

A save written by any engine version is read with its own version stamps
(``parse_save_document(check_versions=False)``); ``migration`` then brings
its steps onto this engine. One game can leave several saves -- its
autosave slot, every save a player made, the saves of a session restored
from one of them -- so ``saved_games`` keeps one per game unless asked for
all of them (``one_save_per_game``).
"""

import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.records.migration import MigratedRecord, migrate_record, walk
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import ParsedSave, parse_save_document

# The seat assignment of a seat a person played (``server.sessions``).
HUMAN_SEAT = "human"


@dataclass(frozen=True, slots=True)
class SavedGame:
    """One save file read as a record."""

    path: Path
    # The game the save came from; saves of one game share it.
    game_id: str
    name: str | None
    saved_at: str | None
    finished: bool
    parsed: ParsedSave

    @property
    def human_seats(self) -> tuple[int, ...]:
        return tuple(
            seat for seat, kind in enumerate(self.parsed.seats) if kind == HUMAN_SEAT
        )


@dataclass(frozen=True, slots=True)
class HumanDecision:
    """A recorded answer of a person to a decision, in this engine's terms."""

    state: GameState
    seat: int
    legal_actions: tuple[DomainAction, ...]
    chosen: DomainAction
    recorded_index: int


def read_saved_game(path: Path) -> SavedGame:
    """Read one save file of any engine version (raises ``SaveError``)."""

    document = json.loads(path.read_text(encoding="utf-8"))
    parsed = parse_save_document(document, check_versions=False)
    game_id = document.get("source_game_id") or document.get("save_id") or path.stem
    name = document.get("name")
    saved_at = document.get("saved_at")
    return SavedGame(
        path=path,
        game_id=str(game_id),
        name=name if isinstance(name, str) else None,
        saved_at=saved_at if isinstance(saved_at, str) else None,
        finished=document.get("finished") is True,
        parsed=parsed,
    )


def saved_games(directory: Path, *, every_save: bool = False) -> list[SavedGame]:
    """Every readable save in ``directory``, oldest first.

    Unless ``every_save``, one save per game (``one_save_per_game``). Files
    that are not readable saves are skipped; ``dune-imperium-records
    check`` names them.
    """

    games: list[SavedGame] = []
    for path in sorted(directory.glob("*.json")):
        try:
            games.append(read_saved_game(path))
        except OSError, ValueError:
            continue
    return games if every_save else one_save_per_game(games)


def one_save_per_game(games: list[SavedGame]) -> list[SavedGame]:
    """One save per game played, oldest first.

    The saves of one game share its ruleset, seed and seat assignment: its
    autosave slot, every save a player made, and the saves of a session
    restored from one of them (a restored session gets a new game id but
    keeps the seats). Games of one ruleset and seed with other seats, such
    as a record corpus's seat mixes, are other games. The game's line runs
    through its newest finished save, or its newest save while it is
    unfinished; the saves on that line (one a prefix of the other) are the
    same game, and the one with the most steps is kept. A save off the line
    holds moves the players took back, or a continuation they left, and is
    dropped.
    """

    groups: dict[tuple[RulesetConfig, int, tuple[str, ...]], list[SavedGame]] = (
        defaultdict(list)
    )
    for game in games:
        replay = game.parsed.replay
        groups[(replay.ruleset, replay.seed, game.parsed.seats)].append(game)
    kept = []
    for group in groups.values():
        anchor = max(group, key=lambda game: (game.finished, game.saved_at or ""))
        line = [game for game in group if _one_line(game, anchor)]
        kept.append(max(line, key=lambda game: len(game.parsed.replay.steps)))
    return sorted(kept, key=lambda game: (game.saved_at or "", game.path.name))


def _one_line(first: SavedGame, second: SavedGame) -> bool:
    """Whether one save's steps begin the other's."""

    a, b = first.parsed.replay.steps, second.parsed.replay.steps
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer[: len(shorter)] == shorter


def human_decisions(
    game: SavedGame,
    record: MigratedRecord | None = None,
    engine: UprisingRulesEngine | None = None,
) -> Iterator[HumanDecision]:
    """Yield every recorded action of a person, with the state it answered.

    Only steps of the record count: a step a bridge supplied was never a
    person's choice. A record that diverged yields the decisions before the
    divergence.
    """

    engine = engine or UprisingRulesEngine()
    record = record or migrate_record(game.parsed.replay, engine)
    humans = set(game.human_seats)
    for state, migrated in walk(record, engine):
        step = migrated.step
        if (
            migrated.recorded_index is None
            or not isinstance(step, DomainAction)
            or step.actor not in humans
        ):
            continue
        yield HumanDecision(
            state=state,
            seat=step.actor,
            legal_actions=engine.legal_actions(state, step.actor),
            chosen=step,
            recorded_index=migrated.recorded_index,
        )
