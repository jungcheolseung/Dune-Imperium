"""In-memory game sessions for the M11 local play server.

A session drives one game exclusively through the engine's public contract
(``reset``/``current_decision``/``legal_actions``/``apply``/``observe``) plus
the seeded ``ChanceResolver`` of the runner pattern; no rule logic lives
here. Humans only ever receive their own serialized ``PlayerView`` and their
own legal actions — both can carry private card identities, so AI seats
refuse them — keeping ``core.observation`` the single visibility authority.

Chance decisions and AI seats advance automatically after game creation and
after every human action, so a session always rests on a human decision or
on the finished game. Every applied step is recorded replay-style for the
upcoming save/load slice.
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
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]

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
        if len(seats) != config.players:
            raise SessionError("exactly one seat assignment per player is required")
        for assignment in seats:
            if assignment != HUMAN_SEAT and assignment not in AGENT_SEATS:
                raise SessionError(f"unknown seat assignment: {assignment!r}")
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
        """Return the serialized ``PlayerView`` of one human seat."""

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            view = session.engine.observe(session.state, seat)
        return _serialize_view(view)

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

    def _get(self, game_id: str) -> GameSession:
        with self._registry_lock:
            try:
                return self._sessions[game_id]
            except KeyError:
                raise UnknownGameError(f"unknown game: {game_id}") from None

    def _require_human(self, session: GameSession, seat: int) -> None:
        if not 0 <= seat < session.config.players:
            raise SeatAccessError("seat does not identify a configured player")
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


def _serialize_view(view: PlayerView) -> JsonObject:
    serialized = _jsonify(asdict(view))
    assert isinstance(serialized, dict)
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
