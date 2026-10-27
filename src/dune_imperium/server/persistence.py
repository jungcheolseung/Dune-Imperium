"""Versioned save documents and a local file store for the play server.

A save document is one serialized ``GameReplay`` (ruleset, seed, recorded
steps, final state hash, version stamps) plus the session facts needed to
resume play: the seat assignments, the policy seed, and (format version 2)
the session log with its undo history — undone steps and undo markers —
so a loaded game's live log and review still show what was taken back. The session layer
owns the load walk that replays those steps; this module only defines the
document schema, its version checks, and the JSON file store.

A document may also carry the play clock (``clock``: the game time and each
seat's time holding control). It is display only, so it adds no format
version, and a load reads it leniently (``read_saved_clock``).

Version stamps are strict: a save must match this build's format version,
ruleset/content versions, and ``ACTION_CODEC_VERSION`` exactly, so a stale
save fails up front with a nameable reason instead of a late hash mismatch.

Save documents embed hidden information (recorded shuffle outcomes spell
out deck orders), so anything served over HTTP goes through
``save_metadata`` while the full document stays on the server's disk.

An autosave (M14 slice 5) is an ordinary save document in the one slot its
game owns: the save ID is the game ID, and every write replaces the file.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypeGuard

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.paths import SAVES_DIR
from dune_imperium.server.pacing import AI_PACES
from dune_imperium.server.session_log import LogEntry, LoggedUndo

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]

SAVE_FORMAT: Final = "dune-imperium-save"
SAVE_FORMAT_VERSION: Final = 2
# Version 1 documents (before the session log existed) still load; their
# log is rebuilt from the recorded steps with no undo history.
_READABLE_FORMAT_VERSIONS: Final = frozenset({1, SAVE_FORMAT_VERSION})

type SavedLogEntry = tuple[ReplayStep, bool] | LoggedUndo

_SAVE_ID: Final = re.compile(r"^[0-9a-f]{32}$")


class SaveError(ValueError):
    """Raised when a save document cannot be parsed, verified, or replayed."""


class UnknownSaveError(SaveError):
    """Raised when no stored save matches a save ID."""


@dataclass(frozen=True, slots=True)
class SavedHandOver:
    """The turn-end state of a saved session (``server/turn_end.py``).

    ``confirmation`` is the seat whose "턴 종료" press the game waits for,
    ``sealed_steps`` how many steps a turn end has sealed, and
    ``open_units`` each human seat with an open unit and the index of the
    step that opened it.
    """

    confirmation: int | None
    sealed_steps: int
    open_units: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SavedClock:
    """The play clock a save recorded (``server/play_clock.py``).

    The game time and each seat's time holding control, in milliseconds,
    as of the save; ``known`` is False when they count only since a load of
    a save that recorded none. Display only: a load reads it leniently
    (``read_saved_clock``) and records never see it.
    """

    elapsed_ms: int
    seat_ms: tuple[int, ...]
    known: bool = True


@dataclass(frozen=True, slots=True)
class ParsedSave:
    """A validated save document ready for the session layer to replay."""

    replay: GameReplay
    seats: tuple[str, ...]
    policy_seed: int
    name: str | None
    # ``None`` for a version 1 document: the log is then just the live steps.
    log: tuple[SavedLogEntry, ...] | None = None
    # ``None`` for a document written before the turn-end state was
    # recorded (2026-09-23).
    hand_over: SavedHandOver | None = None
    # The game's AI pace (``pacing.AI_PACES``); ``None`` for a document
    # written before it was recorded (2026-10-08), which the server paces
    # at its default.
    ai_pace: str | None = None


def default_saves_directory() -> Path:
    """Save location used when the CLI does not override it: ``saves/`` in
    the project checkout (``dune_imperium.paths``), git-ignored."""

    return SAVES_DIR


def serialize_step(step: ReplayStep) -> JsonObject:
    """Encode one recorded step with an explicit type discriminator."""

    if isinstance(step, ChanceOutcome):
        return {
            "type": "chance",
            "decision_id": step.decision_id,
            "values": list(step.values),
        }
    return {
        "type": "action",
        "action_id": step.action_id,
        "actor": step.actor,
        "arguments": {key: value for key, value in step.arguments},
    }


def serialize_log_entry(entry: LogEntry) -> JsonObject:
    """Encode one session-log entry: a (possibly undone) step or an undo marker."""

    if isinstance(entry, LoggedUndo):
        return {"type": "undo", "seat": entry.seat, "count": entry.count}
    return {**serialize_step(entry.step), "undone": entry.undone}


def deserialize_log_entry(value: object, index: int) -> SavedLogEntry:
    """Decode one session-log entry, naming the entry index in every error."""

    if not isinstance(value, dict):
        raise SaveError(f"save log entry {index}: an entry must be an object")
    if value.get("type") == "undo":
        seat = value.get("seat")
        count = value.get("count")
        if (
            not isinstance(seat, int)
            or isinstance(seat, bool)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 1
        ):
            raise SaveError(
                f"save log entry {index}: an undo marker needs a seat and a count"
            )
        return LoggedUndo(seat=seat, count=count)
    undone = value.get("undone", False)
    if not isinstance(undone, bool):
        raise SaveError(f"save log entry {index}: undone must be a boolean")
    try:
        step = deserialize_step(value, index)
    except SaveError as error:
        raise SaveError(f"save log entry {index}: {error}") from None
    return (step, undone)


def deserialize_step(value: object, index: int) -> ReplayStep:
    """Decode one recorded step, naming the step index in every error."""

    if not isinstance(value, dict):
        raise _step_error(index, "a step must be an object")
    kind = value.get("type")
    if kind == "chance":
        decision_id = value.get("decision_id")
        raw_values = value.get("values")
        if (
            not isinstance(decision_id, str)
            or not isinstance(raw_values, list)
            or not all(isinstance(item, str) for item in raw_values)
        ):
            raise _step_error(
                index, "a chance step needs a decision_id and string values"
            )
        try:
            return ChanceOutcome(decision_id=decision_id, values=tuple(raw_values))
        except ValueError as error:
            raise _step_error(index, str(error)) from error
    if kind == "action":
        action_id = value.get("action_id")
        actor = value.get("actor")
        arguments = value.get("arguments")
        if (
            not isinstance(action_id, str)
            or not isinstance(actor, int)
            or isinstance(actor, bool)
            or not isinstance(arguments, dict)
        ):
            raise _step_error(
                index, "an action step needs an action_id, actor, and arguments"
            )
        items: list[tuple[str, ActionValue]] = []
        for key, argument in arguments.items():
            if not isinstance(key, str) or not isinstance(argument, bool | int | str):
                raise _step_error(index, "action arguments must map names to scalars")
            items.append((key, argument))
        try:
            return DomainAction(
                action_id=action_id, actor=actor, arguments=tuple(sorted(items))
            )
        except ValueError as error:
            raise _step_error(index, str(error)) from error
    raise _step_error(index, "the step type must be 'action' or 'chance'")


def build_save_document(
    *,
    config: RulesetConfig,
    game_seed: int,
    policy_seed: int,
    seats: tuple[str, ...],
    steps: tuple[ReplayStep, ...],
    expected_state_hash: str,
    source_game_id: str,
    round_number: int,
    phase: str,
    finished: bool,
    log: tuple[LogEntry, ...],
    name: str | None = None,
    confirmation: int | None = None,
    sealed_steps: int = 0,
    open_units: tuple[tuple[int, int], ...] = (),
    ai_pace: str = "instant",
    clock: SavedClock | None = None,
) -> JsonObject:
    """Serialize one resting session as a save document.

    ``clock`` is optional and display only, like ``ai_pace`` it needs no
    new format version: a build that does not know it reads past it.
    """

    replay = GameReplay(
        ruleset=config,
        seed=game_seed,
        steps=steps,
        expected_state_hash=expected_state_hash,
        action_codec_version=ACTION_CODEC_VERSION,
    )
    document: JsonObject = {
        "format": SAVE_FORMAT,
        "format_version": SAVE_FORMAT_VERSION,
        "ruleset": {
            "players": config.players,
            # The base game (docs/base-game-and-ix-plan.md 10.2); a document
            # without it is an Uprising game.
            "base_game": config.base_game.value,
            "choam_module": config.choam_module,
            "leader_draft": config.leader_draft,
            "promo_cards": config.promo_cards,
            "bloodlines": config.bloodlines,
            "tech_module": config.tech_module,
            "immortality": config.immortality,
            "go_to_11": config.go_to_11,
            "epic_game": config.epic_game,
            "arrakeen_scouts": config.arrakeen_scouts,
            "first_player_seat_zero": config.first_player_seat_zero,
            "rise_of_ix": config.rise_of_ix,
        },
        "game_seed": replay.seed,
        "policy_seed": policy_seed,
        "seats": list(seats),
        "steps": [serialize_step(step) for step in replay.steps],
        "log": [serialize_log_entry(entry) for entry in log],
        "expected_state_hash": replay.expected_state_hash,
        "ruleset_version": replay.ruleset_version,
        "content_version": replay.content_version,
        "action_codec_version": replay.action_codec_version,
        "name": name,
        "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_game_id": source_game_id,
        "round_number": round_number,
        "phase": phase,
        "finished": finished,
        "confirmation": confirmation,
        "sealed_steps": sealed_steps,
        "open_units": [[seat, opened] for seat, opened in open_units],
        "ai_pace": ai_pace,
    }
    if clock is not None:
        document["clock"] = {
            "elapsed_ms": clock.elapsed_ms,
            "seat_ms": list(clock.seat_ms),
            "known": clock.known,
        }
    return document


def parse_save_document(
    document: object, *, check_versions: bool = True
) -> ParsedSave:
    """Validate one save document against this build's versions.

    ``check_versions=False`` skips the version check and keeps the save's
    own version stamps on the replay. The server never does that: such a
    replay need not run on this engine as recorded. It is for reading a
    saved game as a record (``records.saves``), which brings the steps onto
    this engine itself (``records.migration``).
    """

    if not isinstance(document, dict):
        raise SaveError("a save document must be a JSON object")
    if document.get("format") != SAVE_FORMAT:
        raise SaveError("not a dune-imperium save document")
    format_version = document.get("format_version")
    if format_version not in _READABLE_FORMAT_VERSIONS:
        raise SaveError(
            f"unsupported save format version {format_version!r} "
            f"(this server reads versions {sorted(_READABLE_FORMAT_VERSIONS)})"
        )

    ruleset_value = document.get("ruleset")
    if not isinstance(ruleset_value, dict):
        raise SaveError("the save ruleset must be an object")
    players = ruleset_value.get("players")
    choam_module = ruleset_value.get("choam_module")
    leader_draft = ruleset_value.get("leader_draft")
    if (
        not isinstance(players, int)
        or isinstance(players, bool)
        or not isinstance(choam_module, bool)
        or not isinstance(leader_draft, bool)
    ):
        raise SaveError(
            "the save ruleset needs players, choam_module, and leader_draft"
        )
    # Optional module flags; documents written before they existed (or a
    # base game) leave them out, which means "off".
    modules: dict[str, bool] = {}
    for key in (
        "promo_cards",
        "bloodlines",
        "tech_module",
        "immortality",
        "go_to_11",
        "epic_game",
        "arrakeen_scouts",
        "first_player_seat_zero",
        "rise_of_ix",
    ):
        flag = ruleset_value.get(key, False)
        if not isinstance(flag, bool):
            raise SaveError(f"the save ruleset {key} must be a boolean")
        modules[key] = flag
    base_game = ruleset_value.get("base_game", BaseGame.UPRISING.value)
    if base_game not in tuple(BaseGame):
        raise SaveError(f"unknown save base game {base_game!r}")
    try:
        config = RulesetConfig(
            players=players,
            base_game=BaseGame(base_game),
            choam_module=choam_module,
            leader_draft=leader_draft,
            **modules,
        )
    except ValueError as error:
        raise SaveError(str(error)) from error

    game_seed = document.get("game_seed")
    policy_seed = document.get("policy_seed")
    if (
        not isinstance(game_seed, int)
        or isinstance(game_seed, bool)
        or not isinstance(policy_seed, int)
        or isinstance(policy_seed, bool)
        or policy_seed < 0
    ):
        raise SaveError("save seeds must be non-negative integers")

    seats_value = document.get("seats")
    if not isinstance(seats_value, list) or not all(
        isinstance(seat, str) for seat in seats_value
    ):
        raise SaveError("save seats must be a list of assignment names")

    raw_steps = document.get("steps")
    if not isinstance(raw_steps, list):
        raise SaveError("save steps must be a list")
    steps = tuple(
        deserialize_step(item, index) for index, item in enumerate(raw_steps)
    )

    log: tuple[SavedLogEntry, ...] | None = None
    if format_version == SAVE_FORMAT_VERSION:
        raw_log = document.get("log")
        if not isinstance(raw_log, list):
            raise SaveError("save log must be a list")
        log = tuple(
            deserialize_log_entry(item, index) for index, item in enumerate(raw_log)
        )

    expected_state_hash = document.get("expected_state_hash")
    if not isinstance(expected_state_hash, str) or not expected_state_hash:
        raise SaveError("the save needs a non-empty expected_state_hash")
    name = document.get("name")
    if name is not None and not isinstance(name, str):
        raise SaveError("the save name must be a string when present")

    # Optional: documents written before the turn-end state was recorded
    # leave it out and resume by the pause rule of their time.
    hand_over = _parse_hand_over(document)
    raw_pace = document.get("ai_pace")
    if raw_pace is not None and (
        not isinstance(raw_pace, str) or raw_pace not in AI_PACES
    ):
        raise SaveError(f"save ai_pace must be one of {list(AI_PACES)}")
    ai_pace = raw_pace if isinstance(raw_pace, str) else None

    try:
        replay = GameReplay(
            ruleset=config,
            seed=game_seed,
            steps=steps,
            expected_state_hash=expected_state_hash,
            action_codec_version=ACTION_CODEC_VERSION,
        )
        if not check_versions:
            replay = _with_recorded_versions(replay, document)
    except ValueError as error:
        raise SaveError(str(error)) from error
    if check_versions:
        for field in ("ruleset_version", "content_version", "action_codec_version"):
            recorded = document.get(field)
            current = getattr(replay, field)
            if recorded != current:
                raise SaveError(
                    f"save {field} {recorded!r} does not match "
                    f"this server's {current!r}"
                )

    return ParsedSave(
        replay=replay,
        seats=tuple(seats_value),
        policy_seed=policy_seed,
        name=name,
        log=log,
        hand_over=hand_over,
        ai_pace=ai_pace,
    )


def _with_recorded_versions(
    replay: GameReplay, document: dict[str, object]
) -> GameReplay:
    """``replay`` stamped with the versions its save document records."""

    ruleset_version = document.get("ruleset_version")
    content_version = document.get("content_version")
    codec_version = document.get("action_codec_version")
    if (
        not isinstance(ruleset_version, str)
        or not isinstance(content_version, str)
        or not isinstance(codec_version, int)
        or isinstance(codec_version, bool)
    ):
        raise SaveError("the save needs its ruleset, content and codec versions")
    return replace(
        replay,
        ruleset_version=ruleset_version,
        content_version=content_version,
        action_codec_version=codec_version,
    )


def _parse_hand_over(document: dict[str, object]) -> SavedHandOver | None:
    """Read the optional turn-end fields of a save document."""

    if "sealed_steps" not in document and "confirmation" not in document:
        return None
    sealed_steps = document.get("sealed_steps")
    if not _is_count(sealed_steps):
        raise SaveError("save sealed_steps must be a non-negative integer")
    confirmation = document.get("confirmation")
    if confirmation is not None and not _is_count(confirmation):
        raise SaveError("save confirmation must be a seat number or null")
    raw_units = document.get("open_units", [])
    if not isinstance(raw_units, list):
        raise SaveError("save open_units must be a list of [seat, step] pairs")
    open_units: list[tuple[int, int]] = []
    for pair in raw_units:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(_is_count(value) for value in pair)
        ):
            raise SaveError("save open_units must be a list of [seat, step] pairs")
        open_units.append((pair[0], pair[1]))
    return SavedHandOver(
        confirmation=confirmation,
        sealed_steps=sealed_steps,
        open_units=tuple(open_units),
    )


def read_saved_clock(document: object, seats: int) -> SavedClock | None:
    """Read a save's play clock, or ``None`` when it has none it can use.

    Lenient on purpose: the clock is display only, so a save without one (it
    predates 2026-10-10) or with a malformed one loads all the same, counting
    from the load. ``parse_save_document`` never looks at it, so neither do
    records (``records.saves``).
    """

    if not isinstance(document, dict):
        return None
    raw = document.get("clock")
    if not isinstance(raw, dict):
        return None
    elapsed = raw.get("elapsed_ms")
    seat_ms = raw.get("seat_ms")
    known = raw.get("known", True)
    if (
        not _is_clock_ms(elapsed)
        or not isinstance(seat_ms, list)
        or len(seat_ms) != seats
        or not all(_is_clock_ms(value) for value in seat_ms)
        or not isinstance(known, bool)
    ):
        return None
    return SavedClock(elapsed_ms=elapsed, seat_ms=tuple(seat_ms), known=known)


# The most milliseconds a saved clock may hold: the largest integer a
# browser's number keeps exact. A larger one (only an edited file has it)
# would not even convert to seconds, so it reads as no clock, never as a
# save that fails to load.
_MAX_CLOCK_MS = 2**53 - 1


def _is_clock_ms(value: object) -> TypeGuard[int]:
    return _is_count(value) and value <= _MAX_CLOCK_MS


def _is_count(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def save_metadata(
    document: JsonObject, *, hide_unfinished_seed: bool = False
) -> JsonObject:
    """Public listing entry for one save; never includes the recorded steps.

    ``hide_unfinished_seed`` is for a remote server (M14), whose host is a
    player too: the seed of a game still in progress would let them rebuild
    every hidden deck order, so it is served only once the game finished.
    """

    steps = document.get("steps")
    seed = document.get("game_seed")
    if hide_unfinished_seed and document.get("finished") is not True:
        seed = None
    return {
        "save_id": document.get("save_id"),
        "name": document.get("name"),
        "saved_at": document.get("saved_at"),
        "source_game_id": document.get("source_game_id"),
        "game_seed": seed,
        "seats": document.get("seats"),
        "ruleset": document.get("ruleset"),
        "round_number": document.get("round_number"),
        "phase": document.get("phase"),
        "finished": document.get("finished"),
        "step_count": len(steps) if isinstance(steps, list) else None,
        "autosave": document.get("autosave") is True,
    }


class SaveStore:
    """Read and write save documents as JSON files in one local directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(
        self, document: JsonObject, *, hide_unfinished_seed: bool = False
    ) -> JsonObject:
        """Persist one document under a fresh save ID; return its metadata."""

        stored: JsonObject = {**document, "save_id": uuid.uuid4().hex}
        self._store(stored)
        return save_metadata(stored, hide_unfinished_seed=hide_unfinished_seed)

    def write_autosave(
        self, game_id: str, document: JsonObject, *, hide_unfinished_seed: bool = False
    ) -> JsonObject:
        """Replace the one autosave of ``game_id``; return its metadata.

        The slot is named after the game (a game ID has the shape of a
        save ID), so a game never leaves more than one autosave behind
        and the file is swapped in atomically: a crash during the write
        leaves the previous autosave whole.
        """

        self._path(game_id)  # refuses anything that is not a plain ID
        stored: JsonObject = {**document, "save_id": game_id, "autosave": True}
        self._store(stored)
        return save_metadata(stored, hide_unfinished_seed=hide_unfinished_seed)

    def _store(self, stored: JsonObject) -> None:
        save_id = str(stored["save_id"])
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{save_id}.json"
        scratch = path.with_name(f"{save_id}.json.tmp")
        scratch.write_text(
            json.dumps(stored, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(scratch, path)

    def list(self, *, hide_unfinished_seed: bool = False) -> list[JsonObject]:
        """Metadata for every stored save, newest first."""

        entries: list[JsonObject] = []
        if not self._directory.is_dir():
            return entries
        for path in sorted(self._directory.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                document = None
            if isinstance(document, dict):
                entries.append(
                    save_metadata(document, hide_unfinished_seed=hide_unfinished_seed)
                )
            else:
                entries.append(
                    {"save_id": path.stem, "error": "unreadable save file"}
                )
        entries.sort(key=lambda entry: str(entry.get("saved_at") or ""), reverse=True)
        return entries

    def read(self, save_id: str) -> JsonObject:
        """Load one full save document."""

        path = self._path(save_id)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise UnknownSaveError(f"unknown save: {save_id}") from None
        except (OSError, json.JSONDecodeError) as error:
            raise SaveError(f"save {save_id} is unreadable: {error}") from error
        if not isinstance(document, dict):
            raise SaveError(f"save {save_id} is unreadable: not an object")
        return {str(key): item for key, item in document.items()}

    def delete(self, save_id: str) -> None:
        """Remove one stored save."""

        try:
            self._path(save_id).unlink()
        except FileNotFoundError:
            raise UnknownSaveError(f"unknown save: {save_id}") from None

    def _path(self, save_id: str) -> Path:
        if not _SAVE_ID.fullmatch(save_id):
            raise UnknownSaveError(f"unknown save: {save_id}")
        return self._directory / f"{save_id}.json"


def _step_error(index: int, message: str) -> SaveError:
    return SaveError(f"save step {index}: {message}")
