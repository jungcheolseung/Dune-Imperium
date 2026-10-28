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
record onto this engine (``records.migration``): the position is the state
before the problem's recorded step, and it resolves when its record
migrates past it and both of its moves are legal there (the person's move
in its migrated form, the network's through the same rewrite bridges);
otherwise ``resolve`` says why, and the position is left out of a score
instead of being scored on another game. "Another game" includes one that
an engine change made different before the position: every problem keeps
the seats' state it was judged in (``position_state``), and a position whose
state no longer matches it does not resolve.

A suite is converted to the current codec at each codec bump with the
other kept records (``records.convert``, docs/human-records.md): its records
then replay here as recorded and its moves are this engine's steps. The
conversion to codec v156 (2026-10-29) moved every problem judged on an older
engine -- a whole placement, a whole action with a target, a refusal the
turn's end lapses now -- to the step where this engine asks it.
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
from dune_imperium.records.migration import migrate_record, rewrite_step, walk
from dune_imperium.records.saves import SavedGame
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step, presents_steps
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
_PLACEMENT: Final = "agent_turn"
# Why a problem does not resolve when the engine reaches its position with
# other seat fields than it was judged with (``_matches``).
POSITION_DIFFERS: Final = "the position differs from the judged one"


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


def judged_differences(judged: Mapping[str, Any], state: GameState) -> tuple[str, ...]:
    """Every field of the snapshot ``judged`` that ``state`` no longer holds.

    ``round`` or ``players[i].<field>``, each once, in the snapshot's order;
    like ``_matches`` only the snapshot's own keys count. Where ``_matches``
    stops at the first difference, this names them all, so a conversion
    (``records.convert``) can tell a difference it was asked to take
    (OQ-145's ``hand_public``) from any other."""

    now = position_state(state)
    found: list[str] = []
    for key, value in judged.items():
        if key != "players":
            if key not in now or _matches(value, now[key]) is not None:
                found.append(key)
            continue
        seats = now.get("players")
        for seat, fields in enumerate(value):
            if not isinstance(seats, list) or seat >= len(seats):
                found.append(f"players[{seat}]")
                continue
            for name, item in fields.items():
                if (
                    name not in seats[seat]
                    or _matches(item, seats[seat][name]) is not None
                ):
                    found.append(f"players[{seat}].{name}")
    return tuple(found)


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
        # bridge may have rewritten the recorded step).
        move, judged_state = positions[(game.game_id, index)]
        person = _action(row["human"], seat)
        if person != move:
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
        recorded, judged_state = positions[(game.game_id, index)]
        right = _action(pick["right"], recorded.actor)
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
) -> dict[tuple[str, int], tuple[DomainAction, dict[str, Any]]]:
    """The person's migrated move and the public state at each wanted step."""

    engine = UprisingRulesEngine()
    found: dict[tuple[str, int], tuple[DomainAction, dict[str, Any]]] = {}
    for game, steps in wanted.values():
        record = migrate_record(game.parsed.replay, engine)
        for state, migrated in walk(record, engine):
            if migrated.recorded_index in steps and isinstance(
                migrated.step, DomainAction
            ):
                found[(game.game_id, migrated.recorded_index)] = (
                    migrated.step,
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
    path.write_text(suite_text(suite), encoding="utf-8")


def suite_text(suite: Suite) -> str:
    """The suite file's text (``save_suite``)."""

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
    return json.dumps(document, ensure_ascii=False)


def load_suite(path: Path = DEFAULT_SUITE) -> Suite:
    document = json.loads(path.read_text(encoding="utf-8"))
    try:
        return suite_from_document(document)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from None


def suite_from_document(document: Mapping[str, Any]) -> Suite:
    """A suite file's parsed JSON as a ``Suite`` (``load_suite``)."""

    if document.get("format") != SUITE_FORMAT or document.get("version") != (
        SUITE_VERSION
    ):
        raise ValueError(f"not a version {SUITE_VERSION} human problem suite")
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
        for state, migrated in walk(record, engine):
            if migrated.recorded_index not in wanted:
                continue
            asked = wanted[migrated.recorded_index]
            resolved[asked.problem_id] = _position(
                engine, asked, state, migrated.step, replay.action_codec_version
            )
        for problem in problems:
            if problem.problem_id in resolved:
                continue
            divergence = record.divergence
            resolved[problem.problem_id] = (
                f"the record stops at step {divergence.recorded_index} on this "
                f"engine: {divergence.reason}"
                if divergence is not None
                else "the record never reaches the position"
            )
    return resolved


def _position(
    engine: UprisingRulesEngine,
    problem: HumanProblem,
    state: GameState,
    migrated: ReplayStep,
    codec: int,
) -> Resolved | str:
    decision = engine.current_decision(state)
    if getattr(decision, "owner", None) != problem.seat:
        return f"seat {problem.seat} does not decide here on this engine"
    moved = _matches(problem.judged_state, position_state(state))
    if moved is not None:
        return f"{POSITION_DIFFERS}: {moved}"
    legal = engine.legal_actions(state, problem.seat)
    # The person's move as the migration replayed it, and the network's move
    # through the same rewrite bridges (either may have been renamed).
    person = migrated if isinstance(migrated, DomainAction) else problem.person
    network = problem.wrong if problem.family == "human_right" else problem.right
    if network not in legal:
        rewritten = rewrite_step(engine, state, network, codec)
        if isinstance(rewritten, DomainAction):
            network = rewritten
    return _resolved(problem, state, legal, person, network)


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
