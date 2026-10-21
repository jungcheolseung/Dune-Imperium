"""Positions from people's games where two searches agreed which move was right.

The human-game diagnosis (``scripts/records/human_diagnosis.py``,
docs/evaluation/human-games-2026-10-10.md) leaves decisions where the play
network's first choice and the person's move were judged twice, by two
networks' searches, with the same clear verdict: the person's move was
better (family ``human_right``) or the network's was (``network_right``).
A suite freezes those positions to score later agents on them. Like the
mined suite (``evaluation.problem_set``, docs/evaluation/problem-set.md) it
is an evaluation only, never a training target, and a disagreement is a
lead to investigate rather than a wrong answer. The ``network_right``
family is the control: an agent that learned people's moves wholesale
would lose it.

A third family, ``ai_mistake``, holds positions from the same kind of games
where an AI seat made a move people found baffling and the diagnosis agreed
was a mistake (docs/evaluation/search-atomics-2026-10-12.md section 1): its
``wrong`` move is the AI seat's recorded one and its ``right`` move a better
move there, chosen by hand with the evidence noted (``build_mistake_suite``).
Those suites are a yardstick for broad changes to the network
(docs/entity-network-plan.md section 4), not a list of moves to teach.

Unlike the mined suite, these positions cannot be mined again: they come
from people's games. So a suite carries its records -- each game's save
document without its undo log -- and resolves a position by migrating its
record onto this engine (``records.migration``). A position resolves when
its record migrates past it and both of its moves are legal there (the
person's move in its migrated form, as a bridge may have rewritten it);
otherwise ``resolve`` says why, and the position is left out of a score
instead of being scored on another game. "Another game" includes one that
an engine change made different before the position: every problem keeps
the seats' state it was judged in (``position_state``), and a position whose
state no longer matches it does not resolve.

Codec v150 (stage B1, OQ-111) asks an Agent turn as a card pick and then a
space pick. A problem whose moves were judged as whole placements is asked
where its two moves first part (docs/stage-b-plan.md 3a): at the card pick
when they send different cards (each move as its card pick), at the space
pick once the person's card is picked when they send the same one, and at
the card pick when only one of them is a placement (the other a Reveal or a
plot, say). Stage B3 asks a waiting effect before its target the same way:
a problem whose person's move is a whole action with a target is asked at
the effect when the network's move resolves another effect (or none), and
at the target once the person's effect is picked when it picks the same one.
"""

import dataclasses
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from dune_imperium.agents import StateAgent, make_agent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState
from dune_imperium.paths import LOCAL_DIR
from dune_imperium.records.migration import (
    GRAFT_BOXES_CODEC,
    graft_box_held,
    migrate_record,
    rewrite_step,
    walk,
)
from dune_imperium.records.saves import SavedGame
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    agent_card_pick,
    agent_card_pick_actions,
    agent_space_pick_actions,
)
from dune_imperium.rules.effect_steps import (
    STEP_SPECS,
    first_step,
    path_of,
    presents_steps,
    without_pick,
)
from dune_imperium.rules.graft_boxes import tagged
from dune_imperium.server.persistence import (
    deserialize_step,
    parse_save_document,
    serialize_step,
)

SUITE_FORMAT: Final = "dune-imperium-human-problems"
# Version 2 (2026-10-10): ``position_state`` keeps every seat field; version
# 1 kept a handful, and named four card zones wrongly so they were skipped.
SUITE_VERSION: Final = 2
FAMILIES: Final = ("human_right", "network_right", "ai_mistake")
# Kept with the machine's other lasting local files (git-ignored ``local/``):
# the suite holds people's games, which the public repository does not.
DEFAULT_SUITE: Final = LOCAL_DIR / "records" / "human-problems.json"
# The AI seats' mistakes in the same games (family ``ai_mistake``).
AI_MISTAKES_SUITE: Final = LOCAL_DIR / "records" / "ai-mistakes.json"
# The save fields a record keeps; the undo log and the session's turn-end
# state are not part of the game.
_RECORD_FIELDS: Final = (
    "ruleset",
    "game_seed",
    "policy_seed",
    "seats",
    "steps",
    "expected_state_hash",
    "ruleset_version",
    "content_version",
    "action_codec_version",
    "name",
    "saved_at",
    "source_game_id",
    "finished",
)
# Card zones whose order a newer engine may change without changing the game
# (a seat's draws taken in another order): compared as sorted lists.
_UNORDERED_ZONES: Final = frozenset(
    {"hand", "hand_public", "discard_pile", "in_play", "intrigue_cards"}
)

# The migration bridges that ask a recorded placement as its two steps
# (``records.migration``, codec v150).
_CARD_PICK_BRIDGE: Final = "agent_card_pick"
_SPACE_PICK_BRIDGE: Final = "agent_space_pick"
# Stage B3: the steps the migration takes toward a recorded whole action;
# the step that ends it names it (``MigratedStep.whole``).
_EFFECT_STEP_BRIDGE: Final = "effect_step"
_PLACEMENT: Final = "agent_turn"
_SPACE_PICK: Final = "place_agent"


def _plain(value: object) -> Any:
    """``value`` as JSON-ready data, nested dataclasses as field dicts."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=repr)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in sorted(value.items())}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def position_state(state: GameState) -> dict[str, Any]:
    """The round and every field of every seat, for telling positions apart.

    Every ``PlayerState`` field is kept, so nothing is left out by a
    misspelt name; ``_matches`` compares only the fields a snapshot holds,
    so a field a newer engine adds does not move a position.
    """

    players = []
    for player in state.players:
        entry = {
            field.name: _plain(getattr(player, field.name))
            for field in dataclasses.fields(player)
        }
        for zone in _UNORDERED_ZONES & entry.keys():
            entry[zone] = sorted(entry[zone], key=repr)
        players.append(entry)
    return {"round": state.round_number, "players": players}


def _matches(then: Any, now: Any) -> str | None:
    """Where ``now`` differs from the snapshot ``then`` (``None`` if nowhere).

    Dicts are compared on ``then``'s keys only: a key ``now`` adds is a field
    a newer engine added; a key it lacks is a field it removed, a difference.
    """

    if isinstance(then, Mapping):
        if not isinstance(now, Mapping):
            return f"{then} then, {now} now"
        for key, value in then.items():
            if key not in now:
                return f"{key} is gone"
            found = _matches(value, now[key])
            if found is not None:
                return f"{key}{'' if found.startswith('[') else ' '}{found}"
        return None
    if isinstance(then, list) and isinstance(now, list) and len(then) == len(now):
        for index, (a, b) in enumerate(zip(then, now, strict=True)):
            found = _matches(a, b)
            if found is not None:
                return f"[{index}] {found}"
        return None
    return None if then == now else f"{then} then, {now} now"


@dataclass(frozen=True, slots=True)
class HumanProblem:
    """One judged decision of a person."""

    problem_id: str
    game: str
    # The decision's index among the record's steps: the person's move.
    recorded_index: int
    seat: int
    round_number: int
    # ``agent_turn``, ``effect_order`` (an Agent turn's effect ordering), or
    # the person's action id.
    kind: str
    family: str
    right: DomainAction
    wrong: DomainAction
    evidence: Mapping[str, Any]
    # ``position_state`` of the position as it was judged.
    judged_state: Mapping[str, Any]

    @property
    def person(self) -> DomainAction:
        """The move the record holds: the person's, or an AI seat's mistake."""

        return self.right if self.family == "human_right" else self.wrong


@dataclass(frozen=True, slots=True)
class Suite:
    note: str
    records: Mapping[str, Mapping[str, Any]]
    problems: tuple[HumanProblem, ...]


@dataclass(frozen=True, slots=True)
class Resolved:
    """A problem's position on this engine."""

    problem: HumanProblem
    state: GameState
    legal: tuple[DomainAction, ...]
    right: DomainAction
    wrong: DomainAction


@dataclass(frozen=True, slots=True)
class HumanAnswer:
    problem_id: str
    family: str
    kind: str
    # ``right``, ``wrong`` (the other judged move) or ``neither``.
    outcome: str
    chosen: str
    # A network's probabilities (``None`` for other agents): on the right
    # move, on the wrong one, and the right move's share of the two.
    p_right: float | None
    p_wrong: float | None
    pair_share: float | None
    # The right move's place in the network's order (1 = its first choice).
    rank_right: int | None
    offered: int


def _action(value: Mapping[str, Any], seat: int) -> DomainAction:
    arguments = tuple(sorted(dict(value["args"]).items()))
    return DomainAction(action_id=str(value["id"]), actor=seat, arguments=arguments)


# An Agent turn's two steps since codec v150 (stage B1) keep the kind of
# the one placement they replace.
_AGENT_TURN_STEPS: Final = frozenset({"choose_agent_card", "place_agent"})


def _kind(row: Mapping[str, Any]) -> str:
    if row.get("effect_order"):
        return "effect_order"
    human = row["human"]
    assert isinstance(human, Mapping)
    kind = str(human["id"])
    return _PLACEMENT if kind in _AGENT_TURN_STEPS else kind


def _paired(values: Sequence[Sequence[float]], human: int) -> tuple[float, float]:
    diffs = [world[human] - world[0] for world in values]
    mean = sum(diffs) / len(diffs)
    variance = sum((d - mean) ** 2 for d in diffs) / max(1, len(diffs) - 1)
    return mean, (variance / len(diffs)) ** 0.5


def build_suite(
    games: Iterable[SavedGame],
    judged: Iterable[Mapping[str, Any]],
    confirmed: Iterable[Mapping[str, Any]],
    note: str,
) -> Suite:
    """Freeze the positions both judges agreed on.

    ``judged`` and ``confirmed`` are the rows of the diagnosis tool's
    ``judge`` and ``confirm`` steps; ``games`` are the saves they judged
    (``records.saves.saved_games``), matched by the first eight characters
    of the game id as the tool writes them.
    """

    by_short = {game.game_id[:8]: game for game in games}
    first = {(row["game"], row["step"]): row for row in judged}
    agreed = [
        row
        for row in confirmed
        if row["first"] == row["second"] and row["second"] in ("human", "net")
    ]
    keys = [(row["game"], int(row["step"])) for row in agreed]
    if len(keys) != len(set(keys)):
        raise ValueError(
            "a decision is confirmed twice; remove stale confirm shards first"
        )
    wanted: dict[str, tuple[SavedGame, set[int]]] = {}
    for short, step in keys:
        game = by_short[short]
        wanted.setdefault(game.game_id, (game, set()))[1].add(step)
    positions = _judged_positions(wanted)
    problems: list[HumanProblem] = []
    records: dict[str, Mapping[str, Any]] = {}
    for row in agreed:
        game = by_short[row["game"]]
        index = int(row["step"])
        seat = int(row["seat"])
        # The judge saw the person's move as the migration replayed it (a
        # bridge may have rewritten the recorded step), or a recorded
        # placement whole when it was judged before codec v150.
        moves, judged_state = positions[(game.game_id, index)]
        person = _action(row["human"], seat)
        if person not in moves:
            raise ValueError(f"{row['game']} step {index} is not the judged move")
        network = _action(row["net_first"], seat)
        family = "human_right" if row["second"] == "human" else "network_right"
        judged_row = first[(row["game"], index)]
        first_mean, first_error = _paired(
            judged_row["values"], int(judged_row["human_col"])
        )
        problems.append(
            HumanProblem(
                problem_id=f"{row['game']}:{index}",
                game=game.game_id,
                recorded_index=index,
                seat=seat,
                round_number=int(row["round"]),
                kind=_kind(judged_row),
                family=family,
                right=person if family == "human_right" else network,
                wrong=network if family == "human_right" else person,
                evidence={
                    "first_mean": first_mean,
                    "first_error": first_error,
                    "second_mean": float(row["mean"]),
                    "second_error": float(row["error"]),
                    "p_person": float(row["p_human"]),
                },
                judged_state=judged_state,
            )
        )
        if game.game_id not in records:
            document = json.loads(game.path.read_text(encoding="utf-8"))
            records[game.game_id] = {
                "format": "dune-imperium-save",
                "format_version": 1,
                **{key: document[key] for key in _RECORD_FIELDS if key in document},
            }
    problems.sort(key=lambda problem: (problem.game, problem.recorded_index))
    return Suite(note=note, records=records, problems=tuple(problems))


def build_mistake_suite(
    games: Iterable[SavedGame], picks: Iterable[Mapping[str, Any]], note: str
) -> Suite:
    """Freeze AI seats' recorded mistakes as ``ai_mistake`` problems.

    Each pick names a game by the first eight characters of its id, the
    recorded ``step`` of the mistake, the ``right`` move (``{"id", "args"}``),
    a ``kind`` and the ``evidence`` behind the verdict. The recorded move,
    as the migration replays it, is the problem's ``wrong`` move.
    """

    by_short = {game.game_id[:8]: game for game in games}
    picks = list(picks)
    keys = [(pick["game"], int(pick["step"])) for pick in picks]
    if len(keys) != len(set(keys)):
        raise ValueError("a mistake is picked twice")
    wanted: dict[str, tuple[SavedGame, set[int]]] = {}
    for short, step in keys:
        game = by_short[short]
        wanted.setdefault(game.game_id, (game, set()))[1].add(step)
    positions = _judged_positions(wanted)
    problems: list[HumanProblem] = []
    records: dict[str, Mapping[str, Any]] = {}
    for pick in picks:
        game = by_short[pick["game"]]
        index = int(pick["step"])
        moves, judged_state = positions[(game.game_id, index)]
        right = _action(pick["right"], moves[0].actor)
        # A recorded placement in the terms its right move names: its space
        # pick against a space pick, the whole placement otherwise; a
        # recorded whole action taken as steps (stage B3) likewise its last
        # step against a step, the whole action against a whole action.
        recorded = (
            moves[0]
            if right.action_id == _SPACE_PICK
            or (
                moves[-1].action_id in STEP_SPECS
                and right.action_id not in STEP_SPECS
            )
            else moves[-1]
        )
        if right == recorded:
            raise ValueError(f"{pick['game']} step {index}: right is the recorded move")
        problems.append(
            HumanProblem(
                problem_id=f"{pick['game']}:{index}",
                game=game.game_id,
                recorded_index=index,
                seat=recorded.actor,
                round_number=int(judged_state["round"]),
                kind=str(pick["kind"]),
                family="ai_mistake",
                right=right,
                wrong=recorded,
                evidence=dict(pick.get("evidence", {})),
                judged_state=judged_state,
            )
        )
        if game.game_id not in records:
            document = json.loads(game.path.read_text(encoding="utf-8"))
            records[game.game_id] = {
                "format": "dune-imperium-save",
                "format_version": 1,
                **{key: document[key] for key in _RECORD_FIELDS if key in document},
            }
    problems.sort(key=lambda problem: (problem.game, problem.recorded_index))
    return Suite(note=note, records=records, problems=tuple(problems))


def merge_suites(base: Suite, added: Suite) -> Suite:
    """Add a later diagnosis run's problems to a suite.

    A run judges its own games. A game already in ``base`` is refused: its
    positions were judged once, and some may have been dropped by hand since
    (a rule change that made one of the two moves illegal), so freezing it
    again would bring those back.
    """

    again = sorted(game[:8] for game in set(base.records) & set(added.records))
    if again:
        raise ValueError(f"games already in the suite: {', '.join(again)}")
    problems = sorted(
        (*base.problems, *added.problems),
        key=lambda problem: (problem.game, problem.recorded_index),
    )
    return Suite(
        note=f"{base.note}; {added.note}" if base.note else added.note,
        records={**base.records, **added.records},
        problems=tuple(problems),
    )


def _judged_positions(
    wanted: Mapping[str, tuple[SavedGame, set[int]]],
) -> dict[tuple[str, int], tuple[tuple[DomainAction, ...], dict[str, Any]]]:
    """The person's migrated move and the public state at each wanted step.

    A recorded placement (before codec v150) also comes whole, as recorded,
    after its migrated space pick, and so does a recorded whole action after
    its last effect step (stage B3): a judge before codec v150 saw it whole,
    and which of this engine's steps a problem is asked at depends on the
    other move (``resolve``)."""

    engine = UprisingRulesEngine()
    found: dict[tuple[str, int], tuple[tuple[DomainAction, ...], dict[str, Any]]] = {}
    for game, steps in wanted.values():
        record = migrate_record(game.parsed.replay, engine)
        for state, migrated in walk(record, engine):
            if migrated.recorded_index in steps and isinstance(
                migrated.step, DomainAction
            ):
                moves: tuple[DomainAction, ...] = (migrated.step,)
                if migrated.bridge == _SPACE_PICK_BRIDGE or migrated.whole is not None:
                    recorded = game.parsed.replay.steps[migrated.recorded_index]
                    assert isinstance(recorded, DomainAction)
                    moves = (migrated.step, recorded)
                found[(game.game_id, migrated.recorded_index)] = (
                    moves,
                    position_state(state),
                )
        missing = steps - {step for game_id, step in found if game_id == game.game_id}
        if missing:
            raise ValueError(
                f"{game.game_id[:8]} does not reach steps {sorted(missing)} here"
            )
    return found


def save_suite(path: Path, suite: Suite) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "format": SUITE_FORMAT,
        "version": SUITE_VERSION,
        "note": suite.note,
        "records": suite.records,
        "problems": [
            {
                "problem_id": problem.problem_id,
                "game": problem.game,
                "recorded_index": problem.recorded_index,
                "seat": problem.seat,
                "round": problem.round_number,
                "kind": problem.kind,
                "family": problem.family,
                "right": serialize_step(problem.right),
                "wrong": serialize_step(problem.wrong),
                "evidence": dict(problem.evidence),
                "judged_state": dict(problem.judged_state),
            }
            for problem in suite.problems
        ],
    }
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def load_suite(path: Path = DEFAULT_SUITE) -> Suite:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format") != SUITE_FORMAT or document.get("version") != (
        SUITE_VERSION
    ):
        raise ValueError(f"{path} is not a version {SUITE_VERSION} human problem suite")
    problems = []
    for index, item in enumerate(document["problems"]):
        right = deserialize_step(item["right"], index)
        wrong = deserialize_step(item["wrong"], index)
        if not isinstance(right, DomainAction) or not isinstance(wrong, DomainAction):
            raise ValueError(f"problem {item['problem_id']} needs two actions")
        if item["family"] not in FAMILIES:
            raise ValueError(f"problem {item['problem_id']} has no known family")
        problems.append(
            HumanProblem(
                problem_id=item["problem_id"],
                game=item["game"],
                recorded_index=int(item["recorded_index"]),
                seat=int(item["seat"]),
                round_number=int(item["round"]),
                kind=item["kind"],
                family=item["family"],
                right=right,
                wrong=wrong,
                evidence=item["evidence"],
                judged_state=item["judged_state"],
            )
        )
    return Suite(
        note=str(document.get("note", "")),
        records=document["records"],
        problems=tuple(problems),
    )


def resolve(
    suite: Suite, engine: UprisingRulesEngine | None = None
) -> dict[str, Resolved | str]:
    """Each problem's position on this engine, or why it has none."""

    engine = engine or UprisingRulesEngine()
    by_game: dict[str, list[HumanProblem]] = defaultdict(list)
    for problem in suite.problems:
        by_game[problem.game].append(problem)
    resolved: dict[str, Resolved | str] = {}
    for game, problems in by_game.items():
        replay = parse_save_document(
            dict(suite.records[game]), check_versions=False
        ).replay
        record = migrate_record(replay, engine)
        wanted = {problem.recorded_index: problem for problem in problems}
        # The state before a card pick the migration put in front of a
        # recorded placement (codec v150): the position is asked there when
        # the problem's moves send different cards.
        before_pick: GameState | None = None
        # The steps toward a waiting effect the migration put in front of a
        # recorded whole action (stage B3), each with the state it was taken
        # in: the position is asked where the problem's moves first part.
        picks: list[tuple[GameState, DomainAction]] = []
        for state, migrated in walk(record, engine):
            if migrated.recorded_index is None and migrated.bridge == _CARD_PICK_BRIDGE:
                before_pick = state
                continue
            if (
                migrated.recorded_index is None
                and migrated.bridge == _EFFECT_STEP_BRIDGE
                and isinstance(migrated.step, DomainAction)
            ):
                picks.append((state, migrated.step))
                continue
            if migrated.recorded_index not in wanted:
                before_pick = None
                picks = []
                continue
            problem = wanted[migrated.recorded_index]
            # A step that ends a recorded whole action: the last effect step,
            # or a held turn-row step taken effect first (stage B3c-2a).
            effect_path = (
                (*picks, (state, migrated.step))
                if migrated.whole is not None
                and isinstance(migrated.step, DomainAction)
                else ()
            )
            resolved[problem.problem_id] = _position(
                engine,
                problem,
                state,
                migrated.step,
                replay.action_codec_version,
                migrated.graft_box,
                migrated.reveal_source,
                before_pick if migrated.bridge == _SPACE_PICK_BRIDGE else None,
                effect_path,
            )
            before_pick = None
            picks = []
        dropped = dict(record.dropped)
        for problem in problems:
            if problem.problem_id in resolved:
                continue
            if problem.recorded_index in dropped:
                # Codec v143 offers both grafted boxes at once: the person's
                # ``switch_graft_card`` has no counterpart here.
                resolved[problem.problem_id] = (
                    f"the person's move at step {problem.recorded_index} has no "
                    f"counterpart on this engine ({dropped[problem.recorded_index]})"
                )
                continue
            divergence = record.divergence
            resolved[problem.problem_id] = (
                f"the record stops at step {divergence.recorded_index} on this "
                f"engine: {divergence.reason}"
                if divergence is not None
                else "the record never reaches the position"
            )
    return resolved


def _card_of(move: DomainAction) -> tuple[str, bool] | None:
    """A whole placement's card and graft choice; None for any other move."""

    if move.action_id != _PLACEMENT:
        return None
    arguments = dict(move.arguments)
    card = arguments.get("card_id")
    return (card, arguments.get("graft") is True) if isinstance(card, str) else None


def _card_pick(seat: int, card: str, graft: bool) -> DomainAction:
    whole = DomainAction(
        _PLACEMENT, seat, (("card_id", card), *((("graft", True),) if graft else ()))
    )
    (pick,) = agent_card_pick_actions(seat, (whole,))
    return pick


def _placement_position(
    problem: HumanProblem,
    state: GameState,
    person: DomainAction,
    network: DomainAction,
    before_pick: GameState | None,
) -> tuple[GameState, DomainAction, DomainAction]:
    """Where a problem with a placement in it is asked, and its two moves
    there (codec v150, module docstring). ``person`` is the migrated move at
    ``state``: after the migration's card pick a space pick when the
    recorded move was a placement, ``before_pick`` the state before that
    pick. ``network`` is the other move, in the recording engine's terms."""

    seat = problem.seat
    if network.action_id == _SPACE_PICK:
        # Judged at this engine's space pick already (codec v150 on).
        return state, person, network
    theirs = _card_of(network)
    if before_pick is None:
        assert theirs is not None  # only a placement's move is asked here
        return state, person, _card_pick(seat, *theirs)
    picked = agent_card_pick(state, seat)
    assert picked is not None  # the space-pick bridge answers only then
    if theirs == picked:
        (space,) = agent_space_pick_actions(seat, (network,), *picked)
        return state, person, space
    other = network if theirs is None else _card_pick(seat, *theirs)
    return before_pick, _card_pick(seat, *picked), other


def _position(
    engine: UprisingRulesEngine,
    problem: HumanProblem,
    state: GameState,
    migrated: ReplayStep,
    codec: int,
    graft_box: int = 0,
    reveal_source: str | None = None,
    before_pick: GameState | None = None,
    effect_path: Sequence[tuple[GameState, DomainAction]] = (),
) -> Resolved | str:
    decision = engine.current_decision(state)
    if getattr(decision, "owner", None) != problem.seat:
        return f"seat {problem.seat} does not decide here on this engine"
    moved = _matches(problem.judged_state, position_state(state))
    if moved is not None:
        return f"the position differs from the judged one: {moved}"
    legal = engine.legal_actions(state, problem.seat)
    # The person's move as the migration replayed it, and the network's move
    # through the same rewrite bridges (either may have been renamed).
    person = migrated if isinstance(migrated, DomainAction) else problem.person
    network = problem.wrong if problem.family == "human_right" else problem.right
    if before_pick is not None or (
        _card_of(network) is not None and agent_card_pick(state, problem.seat) is None
    ):
        if effect_path and before_pick is None:
            # The person's move is a whole action taken as steps (a Plot
            # Intrigue card, a turn-start card) and the other is a placement:
            # the two part at its first step, where this engine offers the
            # card picks beside it. At its last step only its own target is
            # offered (the Insider Information mistakes, Litany Against Fear
            # against a grafted Stilgar; codec v150).
            state, person = effect_path[0]
        state, person, network = _placement_position(
            problem, state, person, network, before_pick
        )
        legal = engine.legal_actions(state, problem.seat)
        if network not in legal:
            rewritten = rewrite_step(engine, state, network, codec)
            if isinstance(rewritten, DomainAction):
                network = rewritten
        return _resolved(problem, state, legal, person, network)
    if effect_path:
        return _effect_position(
            engine, problem, effect_path, network, codec, graft_box, reveal_source
        )
    # Judged in the recording engine's terms: before codec v143 with the
    # graft box that engine had active there (``MigratedStep.graft_box``).
    if codec < GRAFT_BOXES_CODEC:
        held = graft_box_held(engine, state, network, graft_box)
        if held is not None:
            return f"the network's move {network.action_id}: {held}"
    boxed = (
        codec < GRAFT_BOXES_CODEC
        and graft_box == 1
        and tagged(network, 1) in legal
    )
    if network not in legal or boxed:
        rewritten = rewrite_step(
            engine, state, network, codec, graft_box, reveal_source
        )
        if isinstance(rewritten, DomainAction):
            network = rewritten
    return _resolved(problem, state, legal, person, network)


def _effect_position(
    engine: UprisingRulesEngine,
    problem: HumanProblem,
    effect_path: Sequence[tuple[GameState, DomainAction]],
    network: DomainAction,
    codec: int,
    graft_box: int,
    reveal_source: str | None,
) -> Resolved | str:
    """A problem whose person's move is a whole action taken as steps
    (stage B3): asked at the first step where the two moves part -- the
    effect when they resolve different effects (or the network's move is no
    effect at all), the target once the person's effect is picked when they
    pick the same one. ``effect_path`` holds each of the person's steps with
    the state it was taken in; ``network`` is in the recording engine's
    terms, so it is read at the state before the first step."""

    seat = problem.seat
    base = effect_path[0][0]
    if codec < GRAFT_BOXES_CODEC:
        held = graft_box_held(engine, base, network, graft_box)
        if held is not None:
            return f"the network's move {network.action_id}: {held}"
    mine = tuple(row for _, row in effect_path)
    stepped = next(
        (
            index
            for index, (state, _) in enumerate(effect_path)
            if network in engine.legal_actions(state, seat)
        ),
        None,
    )
    if stepped is not None:
        # Named as a step of this engine already (a mistake picked by hand
        # since stage B3): asked where that step is offered.
        state = effect_path[stepped][0]
        legal = engine.legal_actions(state, seat)
        return _resolved(problem, state, legal, mine[stepped], network)
    wholes = engine.whole_actions(base, seat)
    if network not in wholes or (
        codec < GRAFT_BOXES_CODEC and graft_box == 1 and tagged(network, 1) in wholes
    ):
        rewritten = rewrite_step(engine, base, network, codec, graft_box, reveal_source)
        if isinstance(rewritten, DomainAction):
            network = rewritten
    try:
        theirs = path_of(without_pick(base), network) or (network,)
    except ValueError:
        # A move whose printer this state does not hold has no steps here:
        # an in-turn ``decline_optional_trash``, which this engine no longer
        # offers since codec v149 (the turn's end lapses the trash), names a
        # window this state is not in. It is asked as it is, and
        # ``_resolved`` reports it is not legal (as before codec v150).
        theirs = (network,)
    parted = next(
        (
            index
            for index in range(min(len(mine), len(theirs)))
            if mine[index] != theirs[index]
        ),
        min(len(mine), len(theirs)) - 1,
    )
    state = effect_path[parted][0]
    legal = engine.legal_actions(state, seat)
    return _resolved(problem, state, legal, mine[parted], theirs[parted])


# The whole actions of a decision come from the rules' providers alone.
_ENGINE: Final = UprisingRulesEngine()


def _resolved(
    problem: HumanProblem,
    state: GameState,
    legal: tuple[DomainAction, ...],
    person: DomainAction,
    network: DomainAction,
) -> Resolved | str:
    if network not in legal and presents_steps(state):
        # A move the network weighed whole (an effect with its target) is
        # asked at the step it starts (stage B3, ``rules.effect_steps``).
        if network in _ENGINE.whole_actions(state, problem.seat):
            network = first_step(state, network)
    right, wrong = (
        (person, network) if problem.family == "human_right" else (network, person)
    )
    if right == wrong:
        return "the right and the wrong move are one move here"
    for move, name in ((right, "right"), (wrong, "wrong")):
        if move not in legal:
            return (
                f"the {name} move {move.action_id}{dict(move.arguments)} is not legal"
            )
    return Resolved(problem, state, legal, right, wrong)


def _agent_seed(problem_id: str, seed: int) -> int:
    digest = hashlib.sha256(problem_id.encode()).hexdigest()
    return seed + int(digest[:8], 16) % 1_000_000


def answer(
    position: Resolved,
    kind: str,
    seed: int = 0,
    engine: UprisingRulesEngine | None = None,
) -> HumanAnswer:
    """Ask a fresh ``kind`` agent for the position's decision."""

    # Imported here: the mined suite's helper pulls torch only for networks.
    from dune_imperium.evaluation.problem_set import policy_probabilities

    engine = engine or UprisingRulesEngine()
    problem, state, legal = position.problem, position.state, position.legal
    agent = make_agent(kind, _agent_seed(problem.problem_id, seed), state.config)
    view = engine.observe(state, problem.seat)
    probabilities = policy_probabilities(agent, view, legal)
    untrained_only = getattr(agent, "untrained_only", None)
    if probabilities is not None and untrained_only is not None:
        codec = getattr(agent, "codec")  # noqa: B009 - a network agent's
        if untrained_only([codec.encode(action) for action in probabilities]):
            # The network was never trained on any offered action; its choice
            # comes from its heuristic fallback, so its flat logits say nothing.
            probabilities = None
    if isinstance(agent, StateAgent):
        chosen = agent.choose_action_with_state(state, view, legal)
    else:
        chosen = agent.choose_action(view, legal)
    outcome = (
        "right"
        if chosen == position.right
        else "wrong"
        if chosen == position.wrong
        else "neither"
    )
    p_right = p_wrong = pair_share = None
    rank_right = None
    if probabilities is not None:
        p_right = probabilities.get(position.right, 0.0)
        p_wrong = probabilities.get(position.wrong, 0.0)
        pair = p_right + p_wrong
        pair_share = p_right / pair if pair > 0 else None
        rank_right = 1 + sum(1 for value in probabilities.values() if value > p_right)
    return HumanAnswer(
        problem_id=problem.problem_id,
        family=problem.family,
        kind=problem.kind,
        outcome=outcome,
        chosen=f"{chosen.action_id}{dict(chosen.arguments)}",
        p_right=p_right,
        p_wrong=p_wrong,
        pair_share=pair_share,
        rank_right=rank_right,
        offered=len(legal),
    )


def summarize(answers: Sequence[HumanAnswer]) -> dict[str, dict[str, Any]]:
    """Per family, and per family and kind group: shares and mean probabilities.

    The kind groups are ``agent_turn``, ``effect_order`` and ``other``; an
    ``ai_mistake`` problem keeps its own kind, which names the mistake.
    """

    groups: dict[str, list[HumanAnswer]] = defaultdict(list)
    for item in answers:
        named = item.kind in ("agent_turn", "effect_order")
        group = item.kind if named or item.family == "ai_mistake" else "other"
        groups[item.family].append(item)
        groups[f"{item.family}/{group}"].append(item)
    summary: dict[str, dict[str, Any]] = {}
    for name in sorted(groups):
        items = groups[name]
        p_right = [item.p_right for item in items if item.p_right is not None]
        shares = [item.pair_share for item in items if item.pair_share is not None]
        summary[name] = {
            "n": len(items),
            "right": sum(item.outcome == "right" for item in items) / len(items),
            "wrong": sum(item.outcome == "wrong" for item in items) / len(items),
            "neither": sum(item.outcome == "neither" for item in items) / len(items),
            "mean_p_right": sum(p_right) / len(p_right) if p_right else None,
            "mean_pair_share": sum(shares) / len(shares) if shares else None,
        }
    return summary
