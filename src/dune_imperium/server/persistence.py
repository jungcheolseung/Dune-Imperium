"""Versioned save documents and a local file store for the play server.

A save document is one serialized ``GameReplay`` (ruleset, seed, recorded
steps, final state hash, version stamps) plus the session facts needed to
resume play: the seat assignments and the policy seed. The session layer
owns the load walk that replays those steps; this module only defines the
document schema, its version checks, and the JSON file store.

Version stamps are strict: a save must match this build's format version,
ruleset/content versions, and ``ACTION_CODEC_VERSION`` exactly, so a stale
save fails up front with a nameable reason instead of a late hash mismatch.

Save documents embed hidden information (recorded shuffle outcomes spell
out deck orders), so anything served over HTTP goes through
``save_metadata`` while the full document stays on the server's disk.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.replay import GameReplay, ReplayStep

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]

SAVE_FORMAT: Final = "dune-imperium-save"
SAVE_FORMAT_VERSION: Final = 1

_SAVE_ID: Final = re.compile(r"^[0-9a-f]{32}$")


class SaveError(ValueError):
    """Raised when a save document cannot be parsed, verified, or replayed."""


class UnknownSaveError(SaveError):
    """Raised when no stored save matches a save ID."""


@dataclass(frozen=True, slots=True)
class ParsedSave:
    """A validated save document ready for the session layer to replay."""

    replay: GameReplay
    seats: tuple[str, ...]
    policy_seed: int
    name: str | None


def default_saves_directory() -> Path:
    """Per-user save location used when the CLI does not override it."""

    return Path.home() / ".dune-imperium" / "saves"


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
    name: str | None = None,
) -> JsonObject:
    """Serialize one resting session as a save document."""

    replay = GameReplay(
        ruleset=config,
        seed=game_seed,
        steps=steps,
        expected_state_hash=expected_state_hash,
        action_codec_version=ACTION_CODEC_VERSION,
    )
    return {
        "format": SAVE_FORMAT,
        "format_version": SAVE_FORMAT_VERSION,
        "ruleset": {
            "players": config.players,
            "choam_module": config.choam_module,
            "leader_draft": config.leader_draft,
        },
        "game_seed": replay.seed,
        "policy_seed": policy_seed,
        "seats": list(seats),
        "steps": [serialize_step(step) for step in replay.steps],
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
    }


def parse_save_document(document: object) -> ParsedSave:
    """Validate one save document against this build's versions."""

    if not isinstance(document, dict):
        raise SaveError("a save document must be a JSON object")
    if document.get("format") != SAVE_FORMAT:
        raise SaveError("not a dune-imperium save document")
    if document.get("format_version") != SAVE_FORMAT_VERSION:
        raise SaveError(
            f"unsupported save format version {document.get('format_version')!r} "
            f"(this server reads version {SAVE_FORMAT_VERSION})"
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
    try:
        config = RulesetConfig(
            players=players, choam_module=choam_module, leader_draft=leader_draft
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

    expected_state_hash = document.get("expected_state_hash")
    if not isinstance(expected_state_hash, str) or not expected_state_hash:
        raise SaveError("the save needs a non-empty expected_state_hash")
    name = document.get("name")
    if name is not None and not isinstance(name, str):
        raise SaveError("the save name must be a string when present")

    try:
        replay = GameReplay(
            ruleset=config,
            seed=game_seed,
            steps=steps,
            expected_state_hash=expected_state_hash,
            action_codec_version=ACTION_CODEC_VERSION,
        )
    except ValueError as error:
        raise SaveError(str(error)) from error
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
    )


def save_metadata(document: JsonObject) -> JsonObject:
    """Public listing entry for one save; never includes the recorded steps."""

    steps = document.get("steps")
    return {
        "save_id": document.get("save_id"),
        "name": document.get("name"),
        "saved_at": document.get("saved_at"),
        "source_game_id": document.get("source_game_id"),
        "game_seed": document.get("game_seed"),
        "seats": document.get("seats"),
        "ruleset": document.get("ruleset"),
        "round_number": document.get("round_number"),
        "phase": document.get("phase"),
        "finished": document.get("finished"),
        "step_count": len(steps) if isinstance(steps, list) else None,
    }


class SaveStore:
    """Read and write save documents as JSON files in one local directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(self, document: JsonObject) -> JsonObject:
        """Persist one document under a fresh save ID; return its metadata."""

        save_id = uuid.uuid4().hex
        stored: JsonObject = {**document, "save_id": save_id}
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{save_id}.json"
        scratch = path.with_name(f"{save_id}.json.tmp")
        scratch.write_text(
            json.dumps(stored, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(scratch, path)
        return save_metadata(stored)

    def list(self) -> list[JsonObject]:
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
                entries.append(save_metadata(document))
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
