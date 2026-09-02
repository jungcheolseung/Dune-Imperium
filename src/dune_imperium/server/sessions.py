"""In-memory game sessions for the M11 local play server.

A session drives one game exclusively through the engine's public contract
(``reset``/``current_decision``/``legal_actions``/``apply``/``observe``) plus
the seeded ``ChanceResolver`` of the runner pattern; no rule logic lives
here. Humans only ever receive their own serialized ``PlayerView`` and their
own legal actions — both can carry private card identities, so AI seats
refuse them — keeping ``core.observation`` the single visibility authority.

Chance decisions and AI seats advance automatically after game creation and
after every human action, so a session always rests on a human decision or
on the finished game. Every applied step is recorded replay-style; saving
serializes that record (``persistence``), and loading replays it against
fresh seeded chance and agent streams so a loaded game continues exactly
like the unsaved session would have.
"""

import random
import threading
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Final

from dune_imperium.agents import Agent, HeuristicAgent, RandomAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView, disclose_hidden_zones
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.server.persistence import (
    JsonObject as JsonObject,
)
from dune_imperium.server.persistence import (
    JsonValue as JsonValue,
)
from dune_imperium.server.persistence import (
    SaveError,
    build_save_document,
    parse_save_document,
)

HUMAN_SEAT: Final = "human"
AGENT_SEATS: Final[dict[str, type[RandomAgent] | type[HeuristicAgent]]] = {
    "random": RandomAgent,
    "heuristic": HeuristicAgent,
}
# Matches the sweep's policy seed convention so one game seed names one game.
_DEFAULT_POLICY_OFFSET: Final = 700_000
_MAX_AUTO_STEPS: Final = 30_000


class SessionError(ValueError):
    """Base error for invalid game-session requests."""


class UnknownGameError(SessionError):
    """Raised when no session exists for a game ID."""


class SeatAccessError(SessionError):
    """Raised when a request touches a seat it may not read or act for."""


class StaleRevisionError(SessionError):
    """Raised when an action targets an outdated state revision."""


@dataclass
class GameSession:
    """One running game and everything needed to advance it."""

    game_id: str
    config: RulesetConfig
    game_seed: int
    policy_seed: int
    seats: tuple[str, ...]
    engine: UprisingRulesEngine
    state: GameState
    chance: ChanceResolver
    agents: dict[int, Agent]
    steps: list[ReplayStep] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class GameSessionManager:
    """Create, look up, and advance in-memory game sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._registry_lock = threading.Lock()

    def create_game(
        self,
        seats: tuple[str, ...],
        *,
        choam_module: bool = False,
        leader_draft: bool = False,
        game_seed: int | None = None,
        policy_seed: int | None = None,
    ) -> JsonObject:
        """Start one game and advance it to the first human decision."""

        config = RulesetConfig(
            choam_module=choam_module, leader_draft=leader_draft
        )
        _validate_seats(seats, config)
        if game_seed is None:
            game_seed = random.SystemRandom().randrange(2**31)
        if game_seed < 0:
            raise SessionError("game seed must not be negative")
        if policy_seed is None:
            policy_seed = _DEFAULT_POLICY_OFFSET + game_seed
        if policy_seed < 0:
            raise SessionError("policy seed must not be negative")

        engine = UprisingRulesEngine()
        session = GameSession(
            game_id=uuid.uuid4().hex,
            config=config,
            game_seed=game_seed,
            policy_seed=policy_seed,
            seats=tuple(seats),
            engine=engine,
            state=engine.reset(config, game_seed),
            chance=ChanceResolver(seed=game_seed),
            agents={
                seat: AGENT_SEATS[assignment](seed=policy_seed + seat)
                for seat, assignment in enumerate(seats)
                if assignment in AGENT_SEATS
            },
        )
        with session.lock:
            self._advance_locked(session)
            summary = self._summary_locked(session)
        with self._registry_lock:
            self._sessions[session.game_id] = session
        return summary

    def list_games(self) -> list[JsonObject]:
        """Return the summary of every open session."""

        with self._registry_lock:
            sessions = tuple(self._sessions.values())
        summaries = []
        for session in sessions:
            with session.lock:
                summaries.append(self._summary_locked(session))
        return summaries

    def summary(self, game_id: str) -> JsonObject:
        """Return the public snapshot of one game."""

        session = self._get(game_id)
        with session.lock:
            return self._summary_locked(session)

    def view(self, game_id: str, seat: int) -> JsonObject:
        """Return the serialized ``PlayerView`` of one human seat.

        Once the game has finished the payload also carries ``disclosure``
        with every hidden zone (OQ-010 ruling 4: post-game full disclosure).
        """

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            state = session.state
            view = session.engine.observe(state, seat)
        return _serialize_view(view, state if _is_finished(state) else None)

    def legal_actions(self, game_id: str, seat: int) -> JsonObject:
        """Return the indexed legal actions of one human seat."""

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            actions = session.engine.legal_actions(session.state, seat)
            return {
                "game_id": session.game_id,
                "revision": session.state.revision,
                "seat": seat,
                "actions": [
                    _serialize_action(index, action)
                    for index, action in enumerate(actions)
                ],
            }

    def apply_action(
        self,
        game_id: str,
        seat: int,
        revision: int,
        index: int,
    ) -> JsonObject:
        """Apply one indexed human action, then auto-advance the game."""

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            if revision != session.state.revision:
                raise StaleRevisionError(
                    "the game advanced past the submitted revision"
                )
            decision = session.engine.current_decision(session.state)
            if (
                not isinstance(decision, PlayerDecision)
                or decision.owner != seat
            ):
                raise SessionError("the current decision belongs to another seat")
            actions = session.engine.legal_actions(session.state, seat)
            if not 0 <= index < len(actions):
                raise SessionError("action index is out of range")
            action = actions[index]
            session.state = session.engine.apply(session.state, action).state
            session.steps.append(action)
            self._advance_locked(session)
            return self._summary_locked(session)

    def delete(self, game_id: str) -> None:
        """Forget one session."""

        with self._registry_lock:
            if game_id not in self._sessions:
                raise UnknownGameError(f"unknown game: {game_id}")
            del self._sessions[game_id]

    def save_game(self, game_id: str, *, name: str | None = None) -> JsonObject:
        """Serialize one session into a versioned save document.

        Sessions only rest on a human decision or on the finished game, so
        the recorded steps always end on a state a load can resume from.
        """

        session = self._get(game_id)
        with session.lock:
            return build_save_document(
                config=session.config,
                game_seed=session.game_seed,
                policy_seed=session.policy_seed,
                seats=session.seats,
                steps=tuple(session.steps),
                expected_state_hash=canonical_state_hash(session.state),
                source_game_id=session.game_id,
                round_number=session.state.round_number,
                phase=str(session.state.phase),
                finished=session.state.phase is GamePhase.FINISHED,
                name=name,
            )

    def restore_game(self, document: object) -> JsonObject:
        """Rebuild a saved game as a new session and return its summary.

        The recorded steps replay against a fresh seeded ``ChanceResolver``
        and fresh seeded agents: chance and AI decisions are regenerated
        and must match the record, human actions apply as recorded. That
        restores every RNG stream to its saved position, so the loaded game
        continues exactly like the unsaved session would have; a divergence
        (an edited file, or code that no longer reproduces the record)
        fails with the offending step index. The final canonical state hash
        is verified like ``replay_game`` does.
        """

        parsed = parse_save_document(document)
        config = parsed.replay.ruleset
        _validate_seats(parsed.seats, config)
        engine = UprisingRulesEngine()
        session = GameSession(
            game_id=uuid.uuid4().hex,
            config=config,
            game_seed=parsed.replay.seed,
            policy_seed=parsed.policy_seed,
            seats=parsed.seats,
            engine=engine,
            state=engine.reset(config, parsed.replay.seed),
            chance=ChanceResolver(seed=parsed.replay.seed),
            agents={
                seat: AGENT_SEATS[assignment](seed=parsed.policy_seed + seat)
                for seat, assignment in enumerate(parsed.seats)
                if assignment in AGENT_SEATS
            },
        )
        with session.lock:
            _replay_recorded_steps(session, parsed.replay.steps)
            actual_hash = canonical_state_hash(session.state)
            if actual_hash != parsed.replay.expected_state_hash:
                raise SaveError(
                    "the replayed save does not reproduce its recorded state hash"
                )
            self._advance_locked(session)
            summary = self._summary_locked(session)
        with self._registry_lock:
            self._sessions[session.game_id] = session
        return summary

    def review(self, game_id: str, seat: int) -> JsonObject:
        """Return the step timeline of one finished game.

        A finished game is fully disclosed (OQ-010 ruling 4): every recorded
        action is labelled in full whoever acted, chance outcomes carry their
        values (a shuffle's order is no longer a secret), and any configured
        seat — human or AI — can be reviewed.
        """

        session = self._get(game_id)
        self._require_seat(session, seat)
        with session.lock:
            _require_finished(session)
            steps = tuple(session.steps)
        return {
            "game_id": session.game_id,
            "seat": seat,
            "step_count": len(steps),
            "steps": [_review_step_label(step) for step in steps],
        }

    def review_state(self, game_id: str, seat: int, step: int) -> JsonObject:
        """Return the reviewed seat's view after the first ``step`` steps.

        The payload also carries ``disclosure`` — every hidden zone at that
        step — because the game is over (OQ-010 ruling 4).
        """

        session = self._get(game_id)
        self._require_seat(session, seat)
        with session.lock:
            _require_finished(session)
            steps = tuple(session.steps)
        if not 0 <= step <= len(steps):
            raise SessionError("review step is out of range")
        # A fresh engine re-applies the record so the live session's RNG
        # streams stay untouched.
        engine = UprisingRulesEngine()
        state = engine.reset(session.config, session.game_seed)
        for recorded in steps[:step]:
            state = engine.apply(state, recorded).state
        return {
            "game_id": session.game_id,
            "seat": seat,
            "step": step,
            "round_number": state.round_number,
            "phase": str(state.phase),
            "view": _serialize_view(engine.observe(state, seat), state),
        }

    def _get(self, game_id: str) -> GameSession:
        with self._registry_lock:
            try:
                return self._sessions[game_id]
            except KeyError:
                raise UnknownGameError(f"unknown game: {game_id}") from None

    def _require_seat(self, session: GameSession, seat: int) -> None:
        if not 0 <= seat < session.config.players:
            raise SeatAccessError("seat does not identify a configured player")

    def _require_human(self, session: GameSession, seat: int) -> None:
        self._require_seat(session, seat)
        if session.seats[seat] != HUMAN_SEAT:
            # Views and legal actions can carry private card identities.
            raise SeatAccessError("only a human seat may be read or acted for")

    def _advance_locked(self, session: GameSession) -> None:
        """Resolve chance and AI decisions until a human must act or the end."""

        engine = session.engine
        for _ in range(_MAX_AUTO_STEPS):
            if session.state.phase is GamePhase.FINISHED:
                return
            decision = engine.current_decision(session.state)
            if decision is None:
                raise RuntimeError("an unfinished game has no pending decision")
            if isinstance(decision, ChanceDecision):
                outcome = session.chance.resolve(decision)
                session.steps.append(outcome)
                session.state = engine.apply(session.state, outcome).state
                continue
            if not isinstance(decision, PlayerDecision):
                raise RuntimeError(f"unknown decision type: {decision!r}")
            if session.seats[decision.owner] == HUMAN_SEAT:
                return
            actions = engine.legal_actions(session.state, decision.owner)
            if not actions:
                raise RuntimeError(
                    f"seat {decision.owner} has no legal action to auto-play"
                )
            observation = engine.observe(session.state, decision.owner)
            action = session.agents[decision.owner].choose_action(
                observation, actions
            )
            session.steps.append(action)
            session.state = engine.apply(session.state, action).state
        raise RuntimeError("auto-advance exceeded the step limit")

    def _summary_locked(self, session: GameSession) -> JsonObject:
        state = session.state
        decision: JsonObject | None = None
        pending = session.engine.current_decision(state)
        if isinstance(pending, PlayerDecision):
            frame = state.decision_stack[-1]
            decision = {
                "kind": str(frame.kind),
                "owner": pending.owner,
                "owner_is_human": session.seats[pending.owner] == HUMAN_SEAT,
                "prompt": pending.prompt,
            }
        finished = state.phase is GamePhase.FINISHED
        return {
            "game_id": session.game_id,
            "revision": state.revision,
            "phase": str(state.phase),
            "round_number": state.round_number,
            "first_player": state.first_player,
            "game_seed": session.game_seed,
            "choam_module": session.config.choam_module,
            "leader_draft": session.config.leader_draft,
            "seats": list(session.seats),
            "decision": decision,
            "finished": finished,
            "standings": (
                [_jsonify(asdict(standing)) for standing in final_standings(state)]
                if finished
                else None
            ),
        }


def _validate_seats(seats: tuple[str, ...], config: RulesetConfig) -> None:
    if len(seats) != config.players:
        raise SessionError("exactly one seat assignment per player is required")
    for assignment in seats:
        if assignment != HUMAN_SEAT and assignment not in AGENT_SEATS:
            raise SessionError(f"unknown seat assignment: {assignment!r}")


def _replay_recorded_steps(
    session: GameSession, recorded_steps: tuple[ReplayStep, ...]
) -> None:
    """Re-apply a save's steps, regenerating chance and AI decisions.

    Caller holds the session lock. Every regenerated step must equal the
    record; that check both validates the save and proves the fresh RNG
    streams sit exactly where the saved session left them.
    """

    engine = session.engine
    for index, recorded in enumerate(recorded_steps):
        decision = engine.current_decision(session.state)
        regenerated: ReplayStep
        if isinstance(recorded, ChanceOutcome):
            if not isinstance(decision, ChanceDecision):
                raise SaveError(
                    f"save step {index} records {_step_summary(recorded)} but "
                    "the game is not at a chance decision"
                )
            regenerated = session.chance.resolve(decision)
        elif (
            isinstance(decision, PlayerDecision) and decision.owner == recorded.actor
        ):
            if recorded.actor in session.agents:
                observation = engine.observe(session.state, recorded.actor)
                actions = engine.legal_actions(session.state, recorded.actor)
                regenerated = session.agents[recorded.actor].choose_action(
                    observation, actions
                )
            else:
                regenerated = recorded
        else:
            raise SaveError(
                f"save step {index} records {_step_summary(recorded)} but "
                "the game expects a different decision owner"
            )
        if regenerated != recorded:
            raise SaveError(
                f"save step {index} ({_step_summary(recorded)}) does not "
                "replay as recorded"
            )
        try:
            session.state = engine.apply(session.state, regenerated).state
        except Exception as error:
            raise SaveError(
                f"save step {index} ({_step_summary(recorded)}) failed to "
                f"apply: {error}"
            ) from error
        session.steps.append(recorded)


def _step_summary(step: ReplayStep) -> str:
    if isinstance(step, ChanceOutcome):
        return f"chance {step.decision_id}"
    return f"action {step.action_id} by seat {step.actor}"


def _is_finished(state: GameState) -> bool:
    return state.phase is GamePhase.FINISHED


def _require_finished(session: GameSession) -> None:
    if not _is_finished(session.state):
        raise SessionError("replay review opens after the game finishes")


def _review_step_label(step: ReplayStep) -> JsonObject:
    """Label one recorded step of a finished game in full (OQ-010 ruling 4)."""

    if isinstance(step, ChanceOutcome):
        return {
            "type": "chance",
            "decision_id": step.decision_id,
            "values": list(step.values),
        }
    return {
        "type": "action",
        "actor": step.actor,
        "action_id": step.action_id,
        "arguments": _jsonify(dict(step.arguments)),
    }


def _serialize_view(view: PlayerView, disclosed: GameState | None) -> JsonObject:
    """Serialize a view, adding every hidden zone of ``disclosed`` if given.

    ``disclosed`` must only be passed for a game that has finished (OQ-010
    ruling 4); it may be an earlier state of that finished game.
    """

    serialized = _jsonify(asdict(view))
    assert isinstance(serialized, dict)
    if disclosed is not None:
        serialized["disclosure"] = _jsonify(asdict(disclose_hidden_zones(disclosed)))
    return serialized


def _serialize_action(index: int, action: DomainAction) -> JsonObject:
    return {
        "index": index,
        "action_id": action.action_id,
        "arguments": _jsonify(dict(action.arguments)),
    }


def _jsonify(value: object) -> JsonValue:
    """Convert nested dataclass output into plain JSON-ready values."""

    if isinstance(value, StrEnum):
        return str(value)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonify(item) for item in value]
    raise TypeError(f"cannot serialize value of type {type(value)!r}")
