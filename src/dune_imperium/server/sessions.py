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

Who may do what is judged here too (``access``, M14). An open manager — the
default, the local server — trusts every caller as before. A remote manager
reads or acts for a human seat only for the client holding the token minted
when that seat was claimed, keeps host operations (creating, listing,
saving, loading and deleting games, releasing seats) behind the admin key,
and keeps the game seed out of every summary until the game has finished:
the engine is deterministic, so the seed plus the public actions would
spell out every hidden deck order.

Every change rings a doorbell (M14 slice 3): listeners get a small payload
of public fields, built under the session lock but delivered after it is
released, so a listener may read the session again. The payload says *that*
something changed and carries nothing a seat could not see; a client that
hears it fetches its own snapshot through the judged calls above. Open
event streams register as connections, which is all presence is: a human
seat is online while some connection holds its current token.
"""

import itertools
import logging
import random
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Final

from dune_imperium.agents import Agent, StateAgent, make_agent
from dune_imperium.agents.registry import CHECKPOINT_PREFIX, is_agent_kind
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import PlayerView, disclose_hidden_zones
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.display import effect_action_text
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.server.access import (
    ANONYMOUS,
    AccessMode,
    Credentials,
    new_token,
    token_matches,
)
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
from dune_imperium.server.session_log import (
    LogEntry,
    LoggedStep,
    LoggedUndo,
    live_steps,
    log_step,
    mark_undone,
    reveals_hidden_information,
    undo_history,
    undo_window,
)

_LOGGER: Final = logging.getLogger(__name__)

HUMAN_SEAT: Final = "human"
# Every other seat names an agent of the evaluation registry
# (``dune_imperium.agents.make_agent``): ``random``, ``heuristic``, the
# determinized-search ``rollout``, or a trained policy ``checkpoint:<path>``.
# Search agents receive the authoritative state like the tournament runner
# does; their contract keeps them from reading hidden zones.
# Matches the sweep's policy seed convention so one game seed names one game.
_DEFAULT_POLICY_OFFSET: Final = 700_000
_MAX_AUTO_STEPS: Final = 30_000
# Names are shown to every player at the table; the limit keeps them on one
# line of a seat panel.
PLAYER_NAME_MAX_LENGTH: Final = 20

# A doorbell listener gets the game ID and the public payload, or ``None``
# once the game is gone. It runs on the thread that made the change, after
# the session lock was released.
type ChangeListener = Callable[[str, JsonObject | None], None]
# A hand-over listener gets the ID of a game whose turn has just passed on
# (or which has just finished). Same thread, same moment: after the lock.
type HandOverListener = Callable[[str], None]


class SessionError(ValueError):
    """Base error for invalid game-session requests."""


class UnknownGameError(SessionError):
    """Raised when no session exists for a game ID."""


class SeatAccessError(SessionError):
    """Raised when a request touches a seat it may not read or act for."""


class AdminAccessError(SessionError):
    """Raised when a host-only operation comes without the admin key."""


class SeatTakenError(SessionError):
    """Raised when a claim loses to the client that already holds the seat."""


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
    # Append-only session log: every applied step (undone ones included)
    # and every undo marker; ``steps`` is its live projection.
    log: list[LogEntry] = field(default_factory=list)
    # How many undos happened. Revisions count applied steps, so after an
    # undo and a different choice the same revision names a different
    # state; a client that also sends this generation number can never act
    # on a state that has been taken back under it.
    undo_count: int = 0
    # Seat whose turn has ended but whose steps are still undoable: the
    # session waits for that seat's explicit confirmation before the next
    # seat (AI or human) acts, so a turn is never handed over while it can
    # still be taken back.
    awaiting_confirmation: int | None = None
    # How many live steps a turn-end confirmation has sealed. The log alone
    # closes a seat's undo window at the next chance outcome or other
    # seat's step; when the next seat is a human who has not moved yet
    # there is no such step, and without this floor the seat that confirmed
    # could still pull the turn back from under them.
    undo_floor: int = 0
    # Remote access (M14): the token minted when a human seat was claimed
    # and the name its player gave; both stay empty on an open server.
    # Like everything above they change only under ``lock``.
    seat_tokens: dict[int, str] = field(default_factory=dict)
    seat_names: dict[int, str] = field(default_factory=dict)
    # Doorbell sequence (M14 slice 3): bumped by every rung change so a
    # listener can drop a payload that arrives after a newer one.
    event_seq: int = 0
    # Open event streams: connection ID -> the seat tokens it presented.
    # A seat is online while one of them still matches the seat's token.
    connections: dict[int, frozenset[str]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass(frozen=True, slots=True)
class SeatClaim:
    """A successful claim: the seat's token and the summary after it.

    The token is the seat's whole proof of ownership, so it goes to the
    claiming client alone (the HTTP layer sets it as an HttpOnly cookie)
    and never appears in a summary.
    """

    token: str
    summary: JsonObject


class GameSessionManager:
    """Create, look up, and advance in-memory game sessions."""

    def __init__(
        self,
        *,
        access: AccessMode = AccessMode.OPEN,
        admin_key: str | None = None,
    ) -> None:
        if access is AccessMode.REMOTE and not admin_key:
            raise ValueError("remote access needs an admin key")
        if access is AccessMode.OPEN and admin_key is not None:
            raise ValueError("an admin key only applies to remote access")
        self._access = access
        self._admin_key = admin_key
        self._sessions: dict[str, GameSession] = {}
        self._registry_lock = threading.Lock()
        self._listeners: list[ChangeListener] = []
        self._hand_over_listeners: list[HandOverListener] = []
        self._connection_ids = itertools.count(1)

    @property
    def access(self) -> AccessMode:
        """The access mode every request to this manager is judged under."""

        return self._access

    def is_admin(self, credentials: Credentials = ANONYMOUS) -> bool:
        """Return whether the credentials carry the host's admin key.

        An open server has no admin: every caller may do everything.
        """

        if self._admin_key is None:
            return True
        presented = credentials.admin_key
        return presented is not None and token_matches(self._admin_key, (presented,))

    def require_admin(self, credentials: Credentials = ANONYMOUS) -> None:
        """Refuse a host-only operation that comes without the admin key."""

        if not self.is_admin(credentials):
            raise AdminAccessError("this operation needs the host's admin key")

    def admin_login(self, key: str) -> None:
        """Check an admin key a client wants to keep presenting."""

        if self._access is AccessMode.OPEN:
            raise SessionError("an open server has no admin key to log in with")
        self.require_admin(Credentials(admin_key=key))

    def add_change_listener(self, listener: ChangeListener) -> None:
        """Ring ``listener`` after every change to any game of this manager.

        It is called on the thread that made the change, once the session
        lock is released, with the game ID and the doorbell payload
        (``doorbell``), or ``None`` when the game was deleted. It must not
        raise and should return quickly; the play server's listener only
        hands the payload to its event loop.
        """

        self._listeners.append(listener)

    def add_hand_over_listener(self, listener: HandOverListener) -> None:
        """Tell ``listener`` whenever a turn has passed on or a game has ended.

        That is the moment an autosave is worth its write (M14 slice 5): the
        game rests on a human decision (or is over), the seat that acted can
        no longer take anything back, and what a crash would lose from here
        is one turn. A step inside a turn, a turn end still awaiting its
        confirmation, an undo, a claim: none of these calls it.

        Like a change listener it runs on the thread that made the change,
        after the session lock was released and after the doorbell rang, so
        it may read the session (``save_document``) without deadlocking.
        An exception it raises is logged and goes no further: the step it
        follows has already been applied and its player must get an answer.
        """

        self._hand_over_listeners.append(listener)

    def doorbell(self, game_id: str) -> JsonObject:
        """Return the current doorbell payload of one game without ringing.

        The payload is public by construction: a revision, counters, whose
        decision it is, and the ``players`` list every summary carries. It
        needs no credentials beyond knowing the game ID.
        """

        session = self._get(game_id)
        with session.lock:
            return _doorbell(session, self._summary_locked(session))

    def connect(self, game_id: str, *, credentials: Credentials = ANONYMOUS) -> int:
        """Register one open event stream and return its connection ID.

        A connection is what presence is made of: a human seat is online
        while some connection presented its current token (on an open
        server, while any connection exists). The doorbell only rings if
        that changed somebody's ``online`` flag.
        """

        session = self._get(game_id)
        connection_id = next(self._connection_ids)
        with session.lock:
            before = self._online_seats_locked(session)
            session.connections[connection_id] = credentials.seat_tokens
            bell = (
                self._ring_locked(session)
                if self._online_seats_locked(session) != before
                else None
            )
        if bell is not None:
            self._publish(game_id, bell)
        return connection_id

    def disconnect(self, game_id: str, connection_id: int) -> None:
        """Forget one event stream; unknown games and IDs are tolerated.

        A stream outlives neither its game nor a server that is shutting
        down, and both may go first.
        """

        try:
            session = self._get(game_id)
        except UnknownGameError:
            return
        with session.lock:
            before = self._online_seats_locked(session)
            session.connections.pop(connection_id, None)
            bell = (
                self._ring_locked(session)
                if self._online_seats_locked(session) != before
                else None
            )
        if bell is not None:
            self._publish(game_id, bell)

    def create_game(
        self,
        seats: tuple[str, ...],
        *,
        choam_module: bool = False,
        leader_draft: bool = False,
        promo_cards: bool = False,
        bloodlines: bool = False,
        tech_module: bool = False,
        immortality: bool = False,
        game_seed: int | None = None,
        policy_seed: int | None = None,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Start one game and advance it to the first human decision.

        Host-only on a remote server: a ``checkpoint:<path>`` seat makes the
        server open a file, and search seats spend its CPU.
        """

        self.require_admin(credentials)
        try:
            config = RulesetConfig(
                choam_module=choam_module,
                leader_draft=leader_draft,
                promo_cards=promo_cards,
                bloodlines=bloodlines,
                tech_module=tech_module,
                immortality=immortality,
            )
        except ValueError as error:
            # RulesetConfig rejects unsupported combinations (the Tech Module
            # without Bloodlines [Bloodlines pp. 6-7], a non-four-player game).
            # That is a bad request, not a server fault, so it must not reach
            # the client as a bare 500.
            raise SessionError(str(error)) from error
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
            agents=_build_agents(seats, policy_seed),
        )
        with session.lock:
            self._advance_locked(session)
            summary = self._summary_locked(session)
        with self._registry_lock:
            self._sessions[session.game_id] = session
        return summary

    def list_games(self, *, credentials: Credentials = ANONYMOUS) -> list[JsonObject]:
        """Return the summary of every open session.

        Host-only on a remote server, where knowing a game ID is what lets
        a client into that game's room.
        """

        self.require_admin(credentials)
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

    def identify(
        self, game_id: str, *, credentials: Credentials = ANONYMOUS
    ) -> JsonObject:
        """Return which seats of one game the credentials prove, and admin.

        An open server answers with every human seat: there, one browser
        plays all of them, switching to whoever owns the decision.
        """

        session = self._get(game_id)
        with session.lock:
            return self._identify_locked(session, credentials)

    def snapshot(
        self,
        game_id: str,
        seat: int | None = None,
        *,
        log_after: int = 0,
        log_epoch: str | None = None,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Return everything one client needs to redraw, read from one state.

        One request replaces the summary, view, legal-action and log calls a
        refresh used to make in sequence (M14 slice 2): over a WAN the round
        trips cost more than the bytes, and four separate reads could
        straddle another seat's step. Without ``seat`` — a client that knows
        the game but holds no seat — only ``summary`` and ``you`` come back.

        ``actions`` is ``None`` unless the seat owns the pending decision.
        ``log`` is the tail from ``log_after`` on, provided the client's
        ``log_epoch`` still names this log; otherwise the whole log is sent
        again (``from`` 0), because entries the client already holds have
        changed: an undo flags earlier entries, and the end of the game
        lifts every redaction. The client never has to know which happened.
        """

        session = self._get(game_id)
        if seat is not None:
            self._require_human(session, seat)
        if log_after < 0:
            raise SessionError("log cursor is out of range")
        with session.lock:
            summary = self._summary_locked(session)
            you = self._identify_locked(session, credentials)
            if seat is None:
                return {"summary": summary, "you": you}
            self._authorize_seat_locked(session, seat, credentials)
            state = session.state
            view = session.engine.observe(state, seat)
            decision = session.engine.current_decision(state)
            actions = (
                self._legal_actions_locked(session, seat)
                if isinstance(decision, PlayerDecision)
                and decision.owner == seat
                and not self._turn_is_held_locked(session)
                else None
            )
            entries = tuple(session.log)
            epoch = _log_epoch(session, seat)
        finished = _is_finished(state)
        start = log_after if log_epoch == epoch else 0
        if start > len(entries):
            raise SessionError("log cursor is out of range")
        return {
            "summary": summary,
            "you": you,
            "view": _serialize_view(view, state if finished else None),
            "actions": actions,
            "log": {
                "seat": seat,
                "epoch": epoch,
                "from": start,
                "count": len(entries),
                "entries": _log_entries_json(entries, seat, finished, start),
            },
        }

    def claim_seat(
        self,
        game_id: str,
        seat: int,
        name: str,
        *,
        credentials: Credentials = ANONYMOUS,
    ) -> SeatClaim:
        """Sit down at one unclaimed human seat of a remote game.

        Knowing the game ID is the ticket into the room; the first claim of
        a seat wins and mints its token. Claiming again with that token is
        a rename and keeps the token; anyone else gets ``SeatTakenError``
        until the seat is released.
        """

        session = self._get(game_id)
        self._require_remote("claiming a seat")
        self._require_human(session, seat)
        cleaned = _clean_player_name(name)
        with session.lock:
            token = session.seat_tokens.get(seat)
            if token is None:
                token = new_token()
                session.seat_tokens[seat] = token
            elif not token_matches(token, credentials.seat_tokens):
                raise SeatTakenError(f"seat {seat} is already taken")
            session.seat_names[seat] = cleaned
            claim = SeatClaim(token=token, summary=self._summary_locked(session))
            bell = self._ring_locked(session, claim.summary)
        self._publish(game_id, bell)
        return claim

    def release_seat(
        self, game_id: str, seat: int, *, credentials: Credentials = ANONYMOUS
    ) -> JsonObject:
        """Vacate one human seat: its token dies and anyone may claim it.

        Only the seat's holder or the host may do this. It is how a player
        moves to another browser, and how the host frees the seat of a
        player who lost the cookie or left for good.
        """

        session = self._get(game_id)
        self._require_remote("releasing a seat")
        self._require_human(session, seat)
        with session.lock:
            token = session.seat_tokens.get(seat)
            holds = token is not None and token_matches(
                token, credentials.seat_tokens
            )
            if not holds and not self.is_admin(credentials):
                raise SeatAccessError(
                    f"only seat {seat}'s holder or the host may release it"
                )
            session.seat_tokens.pop(seat, None)
            session.seat_names.pop(seat, None)
            summary = self._summary_locked(session)
            bell = self._ring_locked(session, summary)
        self._publish(game_id, bell)
        return summary

    def view(
        self, game_id: str, seat: int, *, credentials: Credentials = ANONYMOUS
    ) -> JsonObject:
        """Return the serialized ``PlayerView`` of one human seat.

        Once the game has finished the payload also carries ``disclosure``
        with every hidden zone (OQ-010 ruling 4: post-game full disclosure).
        """

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            self._authorize_seat_locked(session, seat, credentials)
            state = session.state
            view = session.engine.observe(state, seat)
        return _serialize_view(view, state if _is_finished(state) else None)

    def legal_actions(
        self, game_id: str, seat: int, *, credentials: Credentials = ANONYMOUS
    ) -> JsonObject:
        """Return the indexed legal actions of one human seat."""

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            self._authorize_seat_locked(session, seat, credentials)
            return self._legal_actions_locked(session, seat)

    def apply_action(
        self,
        game_id: str,
        seat: int,
        revision: int,
        index: int,
        *,
        undo_count: int | None = None,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Apply one indexed human action, then auto-advance the game.

        ``undo_count``, when given, must equal the session's undo
        generation as well: it protects a stale client whose revision
        happens to match again after an undo and a different choice.
        """

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            self._authorize_seat_locked(session, seat, credentials)
            _require_current(session, revision, undo_count)
            decision = session.engine.current_decision(session.state)
            if (
                not isinstance(decision, PlayerDecision)
                or decision.owner != seat
            ):
                raise SessionError("the current decision belongs to another seat")
            if self._turn_is_held_locked(session):
                raise SessionError(
                    f"seat {session.awaiting_confirmation} has not confirmed "
                    "its turn end yet"
                )
            actions = session.engine.legal_actions(session.state, seat)
            if not 0 <= index < len(actions):
                raise SessionError("action index is out of range")
            action = actions[index]
            _apply_step(session, action)
            own_steps = len(session.steps)
            self._settle_locked(session, seat)
            passed = _turn_passed(session, seat, own_steps)
            summary = self._summary_locked(session)
            bell = self._ring_locked(session, summary)
        self._publish(game_id, bell)
        if passed:
            self._announce_hand_over(game_id)
        return summary

    def confirm_turn(
        self,
        game_id: str,
        seat: int,
        revision: int,
        *,
        undo_count: int | None = None,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Hand the turn over after the seat's last undoable steps.

        A human seat's turn end pauses while its trailing steps could still
        be taken back (``undo_window``); only this confirmation lets the
        chance stream and the other seats advance, closing that window.
        """

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            self._authorize_seat_locked(session, seat, credentials)
            _require_current(session, revision, undo_count)
            if session.awaiting_confirmation != seat:
                raise SessionError(f"seat {seat} has no turn end to confirm")
            session.awaiting_confirmation = None
            session.undo_floor = len(session.steps)
            self._advance_locked(session)
            summary = self._summary_locked(session)
            bell = self._ring_locked(session, summary)
        self._publish(game_id, bell)
        # A confirmation is the hand-over itself.
        self._announce_hand_over(game_id)
        return summary

    def undo(
        self,
        game_id: str,
        seat: int,
        revision: int,
        steps: int = 1,
        *,
        undo_count: int | None = None,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Take back the seat's own latest ``steps`` steps (M11 slice 6).

        The window (``undo_window``) holds only the seat's consecutive
        latest actions and closes at any chance outcome, any other seat's
        action, or any step that revealed hidden information — so the
        removed steps never touched the chance or AI streams and the
        rebuilt state is again this seat's decision. The taken-back steps
        stay in the session log, flagged ``undone``, behind an undo marker
        (OQ-010: what was shown stays re-checkable).
        """

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            self._authorize_seat_locked(session, seat, credentials)
            _require_current(session, revision, undo_count)
            window = _open_undo_window(session, seat)
            if steps < 1 or steps > window:
                raise SessionError(
                    f"seat {seat} may take back at most {window} step(s) now"
                )
            keep = len(session.steps) - steps
            session.state = _state_after(session, keep)
            del session.steps[keep:]
            mark_undone(session.log, seat, steps)
            session.undo_count += 1
            # The rewound state is again this seat's own decision.
            session.awaiting_confirmation = None
            summary = self._summary_locked(session)
            bell = self._ring_locked(session, summary)
        self._publish(game_id, bell)
        return summary

    def log(
        self,
        game_id: str,
        seat: int,
        *,
        after: int = 0,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Return the session log from entry ``after`` on, as ``seat`` may see it.

        Each entry carries the events its step produced, filtered by
        ``visible_to``; action arguments naming a card the seat cannot
        identify are redacted for other seats; chance values stay hidden.
        Once the game has finished nothing is redacted (OQ-010 ruling 4).
        Undone steps remain, flagged, followed by their undo marker.
        """

        session = self._get(game_id)
        self._require_human(session, seat)
        with session.lock:
            self._authorize_seat_locked(session, seat, credentials)
            entries = tuple(session.log)
            finished = _is_finished(session.state)
        if not 0 <= after <= len(entries):
            raise SessionError("log cursor is out of range")
        return {
            "game_id": session.game_id,
            "seat": seat,
            "count": len(entries),
            "entries": _log_entries_json(entries, seat, finished, after),
        }

    def delete(self, game_id: str, *, credentials: Credentials = ANONYMOUS) -> None:
        """Forget one session (host-only on a remote server)."""

        self.require_admin(credentials)
        with self._registry_lock:
            if game_id not in self._sessions:
                raise UnknownGameError(f"unknown game: {game_id}")
            del self._sessions[game_id]
        self._publish(game_id, None)

    def save_game(
        self,
        game_id: str,
        *,
        name: str | None = None,
        credentials: Credentials = ANONYMOUS,
    ) -> JsonObject:
        """Serialize one session into a versioned save document.

        Sessions only rest on a human decision or on the finished game, so
        the recorded steps always end on a state a load can resume from.

        Host-only on a remote server, like ``restore_game``: a loaded save
        is a second session holding the same hidden state with every seat
        unclaimed, so whoever may save and load could read every hand of
        the game in progress off that clone.
        """

        self.require_admin(credentials)
        return self.save_document(game_id, name=name)

    def save_document(self, game_id: str, *, name: str | None = None) -> JsonObject:
        """Serialize one session for the server's own use (the autosave).

        No credentials are asked for, so this is never routed: a save
        document spells out every hidden deck order. ``save_game`` is the
        host's door to the same document.
        """

        session = self._get(game_id)
        with session.lock:
            return build_save_document(
                config=session.config,
                game_seed=session.game_seed,
                policy_seed=session.policy_seed,
                seats=session.seats,
                steps=tuple(session.steps),
                log=tuple(session.log),
                expected_state_hash=canonical_state_hash(session.state),
                source_game_id=session.game_id,
                round_number=session.state.round_number,
                phase=str(session.state.phase),
                finished=session.state.phase is GamePhase.FINISHED,
                name=name,
            )

    def restore_game(
        self, document: object, *, credentials: Credentials = ANONYMOUS
    ) -> JsonObject:
        """Rebuild a saved game as a new session and return its summary.

        Host-only on a remote server (see ``save_game``). The new session
        starts with every human seat unclaimed: a save records neither
        tokens nor names, so the players claim their seats again.

        The recorded steps replay against a fresh seeded ``ChanceResolver``
        and fresh seeded agents: chance and AI decisions are regenerated
        and must match the record, human actions apply as recorded. That
        restores every RNG stream to its saved position, so the loaded game
        continues exactly like the unsaved session would have; a divergence
        (an edited file, or code that no longer reproduces the record)
        fails with the offending step index. The final canonical state hash
        is verified like ``replay_game`` does.
        """

        self.require_admin(credentials)
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
            agents=_build_agents(parsed.seats, parsed.policy_seed),
        )
        with session.lock:
            _replay_recorded_steps(session, parsed.replay.steps)
            actual_hash = canonical_state_hash(session.state)
            if actual_hash != parsed.replay.expected_state_hash:
                raise SaveError(
                    "the replayed save does not reproduce its recorded state hash"
                )
            if parsed.log is not None:
                session.log = _rebuild_log(session, parsed.log)
                session.undo_count = sum(
                    1 for entry in session.log if isinstance(entry, LoggedUndo)
                )
            # A game saved while a human's turn end awaited confirmation
            # resumes at that pause instead of handing the turn over.
            live = live_steps(session.log)
            last_actor = live[-1].actor if live else None
            if last_actor is not None and session.seats[last_actor] == HUMAN_SEAT:
                self._settle_locked(session, last_actor)
            else:
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
        seat — human or AI — can be reviewed. ``log`` is the whole session
        log with nothing redacted, so a client without a seat (a game of AI
        seats only has none to take) can still show what each step did.
        """

        session = self._get(game_id)
        self._require_seat(session, seat)
        with session.lock:
            _require_finished(session)
            steps = tuple(session.steps)
            entries = tuple(session.log)
        return {
            "game_id": session.game_id,
            "seat": seat,
            "step_count": len(steps),
            "steps": [_review_step_label(step) for step in steps],
            "log": _log_entries_json(entries, seat, True, 0),
            # Where steps were taken back (M11 slice 6): the live step index
            # the undo rewound to, who undid, and what was undone.
            "undo_history": [
                {
                    "step": position,
                    "seat": marker.seat,
                    "count": marker.count,
                    "undone": [_review_step_label(entry.step) for entry in undone],
                }
                for position, marker, undone in undo_history(session.log)
            ],
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
        engine = session.engine
        state = _state_after(session, step)
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

    def _identify_locked(
        self, session: GameSession, credentials: Credentials
    ) -> JsonObject:
        if self._access is AccessMode.OPEN:
            seats = [
                seat
                for seat, assignment in enumerate(session.seats)
                if assignment == HUMAN_SEAT
            ]
        else:
            seats = sorted(
                seat
                for seat, token in session.seat_tokens.items()
                if token_matches(token, credentials.seat_tokens)
            )
        return {
            "game_id": session.game_id,
            "access": str(self._access),
            "seats": list(seats),
            "admin": self.is_admin(credentials),
        }

    def _legal_actions_locked(self, session: GameSession, seat: int) -> JsonObject:
        """Serialize the seat's legal actions; each one costs a dry run."""

        actions = session.engine.legal_actions(session.state, seat)
        return {
            "game_id": session.game_id,
            "revision": session.state.revision,
            "seat": seat,
            "actions": [
                _serialize_action(index, action, session)
                for index, action in enumerate(actions)
            ],
        }

    def _online_seats_locked(self, session: GameSession) -> frozenset[int]:
        """Return the human seats some open event stream currently holds."""

        humans = [
            seat
            for seat, assignment in enumerate(session.seats)
            if assignment == HUMAN_SEAT
        ]
        if self._access is AccessMode.OPEN:
            # One browser plays every human seat there, so presence only
            # says whether a browser has the table open at all.
            return frozenset(humans) if session.connections else frozenset()
        return frozenset(
            seat
            for seat in humans
            if (token := session.seat_tokens.get(seat)) is not None
            and any(
                token_matches(token, presented)
                for presented in session.connections.values()
            )
        )

    def _turn_is_held_locked(self, session: GameSession) -> bool:
        """Whether a pending turn-end confirmation still blocks the next seat.

        The engine names the next decision owner as soon as a turn ends, but
        while that turn's steps can be taken back the hand-over waits for
        the seat's confirmation. On an open server the one shared browser
        holds the table for the confirming seat, and the API has always let
        the next seat act regardless. Separate browsers cannot mediate, so a
        remote server does: acting early would close the previous seat's
        undo window behind its back.
        """

        return (
            self._access is AccessMode.REMOTE
            and session.awaiting_confirmation is not None
        )

    def _ring_locked(
        self, session: GameSession, summary: JsonObject | None = None
    ) -> JsonObject:
        """Bump the doorbell sequence and build the payload to publish.

        The caller holds the session lock and publishes after releasing it;
        ``summary`` spares a second summary when the caller just made one.
        """

        session.event_seq += 1
        if summary is None:
            summary = self._summary_locked(session)
        return _doorbell(session, summary)

    def _publish(self, game_id: str, payload: JsonObject | None) -> None:
        """Hand one payload to every listener; never call this under a lock."""

        for listener in tuple(self._listeners):
            listener(game_id, payload)

    def _announce_hand_over(self, game_id: str) -> None:
        """Tell the hand-over listeners; never call this under a lock."""

        for listener in tuple(self._hand_over_listeners):
            try:
                listener(game_id)
            except Exception:
                _LOGGER.exception("a hand-over listener failed for game %s", game_id)

    def _require_remote(self, operation: str) -> None:
        if self._access is not AccessMode.REMOTE:
            raise SessionError(f"{operation} only applies to a remote server")

    def _authorize_seat_locked(
        self, session: GameSession, seat: int, credentials: Credentials
    ) -> None:
        """Refuse a remote client that does not hold the seat's token.

        The caller holds the session lock and has checked that the seat is
        human. The admin key deliberately opens nothing here: the host is a
        player too and must not reach another seat's view through the API.
        """

        if self._access is AccessMode.OPEN:
            return
        token = session.seat_tokens.get(seat)
        if token is None or not token_matches(token, credentials.seat_tokens):
            raise SeatAccessError(f"this client does not hold seat {seat}")

    def _settle_locked(self, session: GameSession, seat: int) -> None:
        """After a human step, pause at a turn hand-over or auto-advance.

        The pause happens only when the next decision belongs to another
        seat and the seat's trailing steps are still undoable; a step that
        revealed hidden information (or a pending chance outcome) already
        closed the undo window, so there is nothing left to protect.
        """

        decision = session.engine.current_decision(session.state)
        if (
            isinstance(decision, PlayerDecision)
            and decision.owner != seat
            and _open_undo_window(session, seat) > 0
        ):
            session.awaiting_confirmation = seat
            return
        session.awaiting_confirmation = None
        self._advance_locked(session)

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
                _apply_step(session, outcome)
                continue
            if not isinstance(decision, PlayerDecision):
                raise RuntimeError(f"unknown decision type: {decision!r}")
            if session.seats[decision.owner] == HUMAN_SEAT:
                return
            if not engine.legal_actions(session.state, decision.owner):
                raise RuntimeError(
                    f"seat {decision.owner} has no legal action to auto-play"
                )
            _apply_step(session, _agent_action(session, decision.owner))
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
            # The Persuasion still unspent in a Reveal, for the buyer's
            # panel. It is table knowledge: the reveal and every purchase
            # are public, and this is their difference.
            remaining = dict(frame.context).get("persuasion")
            if str(frame.kind) == "reveal" and type(remaining) is int:
                decision["persuasion"] = remaining
        finished = state.phase is GamePhase.FINISHED
        undo: list[JsonValue] = []
        for seat, assignment in enumerate(session.seats):
            if assignment != HUMAN_SEAT:
                continue
            window = _open_undo_window(session, seat)
            if window > 0:
                undo.append({"seat": seat, "steps": window})
        remote = self._access is AccessMode.REMOTE
        kinds = [
            _public_seat_kind(assignment, hide_path=remote)
            for assignment in session.seats
        ]
        online = self._online_seats_locked(session)
        players: list[JsonValue] = [
            {
                "seat": seat,
                "kind": kind,
                "name": session.seat_names.get(seat),
                "claimed": seat in session.seat_tokens,
                "online": seat in online,
            }
            for seat, kind in enumerate(kinds)
        ]
        return {
            "game_id": session.game_id,
            "access": str(self._access),
            "revision": state.revision,
            "undo_count": session.undo_count,
            "log_count": len(session.log),
            "undo": undo,
            "confirmation": session.awaiting_confirmation,
            "phase": str(state.phase),
            "round_number": state.round_number,
            "first_player": state.first_player,
            # The engine is deterministic: the seed plus the public actions
            # reproduce every shuffle, so a remote game keeps it to itself
            # until the finished game discloses everything (OQ-010 ruling 4).
            "game_seed": session.game_seed if finished or not remote else None,
            "choam_module": session.config.choam_module,
            "leader_draft": session.config.leader_draft,
            "promo_cards": session.config.promo_cards,
            "bloodlines": session.config.bloodlines,
            "tech_module": session.config.tech_module,
            "immortality": session.config.immortality,
            "seats": list(kinds),
            "players": players,
            "decision": decision,
            "finished": finished,
            "standings": (
                [_jsonify(asdict(standing)) for standing in final_standings(state)]
                if finished
                else None
            ),
        }


def _public_seat_kind(assignment: str, *, hide_path: bool) -> str:
    """Return a seat assignment as the players of the game may see it.

    A ``checkpoint:<path>`` seat names a file on the host's disk; remote
    players get the file name only.
    """

    if hide_path and assignment.startswith(CHECKPOINT_PREFIX):
        path = assignment[len(CHECKPOINT_PREFIX) :]
        return CHECKPOINT_PREFIX + re.split(r"[\\/]", path)[-1]
    return assignment


def _clean_player_name(name: str) -> str:
    """Normalize a player name: printable, single-spaced, 1 to 20 characters.

    Names are shown to every player, so control and format characters are
    dropped here; the browser still renders them as text, never as markup.
    """

    printable = "".join(character for character in name if character.isprintable())
    cleaned = " ".join(printable.split())
    if not cleaned:
        raise SessionError("a player name must not be empty")
    if len(cleaned) > PLAYER_NAME_MAX_LENGTH:
        raise SessionError(
            f"a player name may have at most {PLAYER_NAME_MAX_LENGTH} characters"
        )
    return cleaned


def _validate_seats(seats: tuple[str, ...], config: RulesetConfig) -> None:
    if len(seats) != config.players:
        raise SessionError("exactly one seat assignment per player is required")
    for assignment in seats:
        if assignment != HUMAN_SEAT and not is_agent_kind(assignment):
            raise SessionError(f"unknown seat assignment: {assignment!r}")


def _build_agents(seats: tuple[str, ...], policy_seed: int) -> dict[int, Agent]:
    """Instantiate one registry agent per non-human seat.

    A checkpoint seat loads its network here, so a missing file, a foreign
    observation or codec version, or an absent ``train`` extra surfaces as
    a session error instead of a crash while the game advances.
    """

    agents: dict[int, Agent] = {}
    for seat, assignment in enumerate(seats):
        if assignment == HUMAN_SEAT:
            continue
        try:
            agents[seat] = make_agent(assignment, policy_seed + seat)
        except (ValueError, OSError, ImportError, RuntimeError) as error:
            raise SessionError(
                f"cannot build seat {seat} agent {assignment!r}: {error}"
            ) from error
    return agents


def _agent_action(session: GameSession, seat: int) -> DomainAction:
    """Ask the seat's agent for its move, branching from the state if it can."""

    engine = session.engine
    actions = engine.legal_actions(session.state, seat)
    observation = engine.observe(session.state, seat)
    agent = session.agents[seat]
    if isinstance(agent, StateAgent):
        return agent.choose_action_with_state(session.state, observation, actions)
    return agent.choose_action(observation, actions)


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
                regenerated = _agent_action(session, recorded.actor)
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
            _apply_step(session, regenerated)
        except Exception as error:
            raise SaveError(
                f"save step {index} ({_step_summary(recorded)}) failed to "
                f"apply: {error}"
            ) from error


def _open_undo_window(session: GameSession, seat: int) -> int:
    """How many steps ``seat`` may take back now; the caller holds the lock.

    The log's window (``undo_window``), cut off at the last confirmed turn
    end: what a seat has handed over stays handed over.
    """

    unsealed = len(session.steps) - session.undo_floor
    return max(0, min(undo_window(session.log, seat), unsealed))


def _turn_passed(session: GameSession, seat: int, own_steps: int) -> bool:
    """Whether ``seat``'s step ended in a hand-over; the caller holds the lock.

    ``own_steps`` is the live step count right after the seat's own step.
    The turn has passed when the game is over, when another player's step
    followed (AI seats played on, even if the decision is back with the
    same seat now), or when the decision rests with another seat. It has
    not while the turn end still awaits the seat's confirmation, nor when a
    chance outcome alone followed and the seat simply goes on with its turn.
    """

    if session.awaiting_confirmation is not None:
        return False
    if _is_finished(session.state):
        return True
    if any(
        isinstance(step, DomainAction) and step.actor != seat
        for step in session.steps[own_steps:]
    ):
        return True
    decision = session.engine.current_decision(session.state)
    return isinstance(decision, PlayerDecision) and decision.owner != seat


def _require_current(
    session: GameSession, revision: int, undo_count: int | None
) -> None:
    """Reject requests made against a state the session has moved past."""

    if revision != session.state.revision:
        raise StaleRevisionError("the game advanced past the submitted revision")
    if undo_count is not None and undo_count != session.undo_count:
        raise StaleRevisionError(
            "the game was taken back since the submitted undo generation"
        )


def _apply_step(session: GameSession, step: ReplayStep) -> None:
    """Apply one step to the session and record it in steps and log."""

    before = session.state
    transition = session.engine.apply(before, step)
    session.state = transition.state
    session.steps.append(step)
    session.log.append(log_step(before, transition.state, step, transition.events))


def _state_after(session: GameSession, count: int) -> GameState:
    """Rebuild the state after the first ``count`` live steps.

    Steps replay deterministically, so this never touches the session's
    chance or AI streams; the caller holds the session lock.
    """

    engine = session.engine
    state = engine.reset(session.config, session.game_seed)
    for recorded in session.steps[:count]:
        state = engine.apply(state, recorded).state
    return state


def _rebuild_log(
    session: GameSession,
    saved: tuple[tuple[ReplayStep, bool] | LoggedUndo, ...],
) -> list[LogEntry]:
    """Rebuild the session log of a save, replaying its undone branches.

    Caller holds the session lock and has already replayed the live steps
    into ``session.log``. Live entries must match the record in order;
    undone steps re-apply on the state their branch forked from (they
    never include chance or AI decisions, see ``undo``), so their events
    and reveal flags come back exactly.
    """

    live = [entry for entry in session.log if isinstance(entry, LoggedStep)]
    rebuilt: list[LogEntry] = []
    live_position = 0
    branch: GameState | None = None
    pending_undone = 0
    for index, item in enumerate(saved):
        if isinstance(item, LoggedUndo):
            if pending_undone != item.count:
                raise SaveError(
                    f"save log entry {index}: undo marker count {item.count} does "
                    f"not match the {pending_undone} undone step(s) before it"
                )
            rebuilt.append(item)
            branch = None
            pending_undone = 0
            continue
        step, undone = item
        if not undone:
            if pending_undone:
                raise SaveError(
                    f"save log entry {index}: undone steps must be followed by "
                    "an undo marker"
                )
            if live_position >= len(live) or live[live_position].step != step:
                raise SaveError(
                    f"save log entry {index} does not match recorded step "
                    f"{live_position}"
                )
            rebuilt.append(live[live_position])
            live_position += 1
            continue
        if branch is None:
            branch = _state_after(session, live_position)
        try:
            transition = session.engine.apply(branch, step)
        except Exception as error:
            raise SaveError(
                f"save log entry {index} (undone {_step_summary(step)}) failed "
                f"to apply: {error}"
            ) from error
        logged = log_step(branch, transition.state, step, transition.events)
        rebuilt.append(replace(logged, undone=True))
        branch = transition.state
        pending_undone += 1
    if pending_undone:
        raise SaveError("the save log ends with undone steps but no undo marker")
    if live_position != len(live):
        raise SaveError("the save log does not cover every recorded step")
    return rebuilt


def _doorbell(session: GameSession, summary: JsonObject) -> JsonObject:
    """Build the doorbell payload from a summary of the same state.

    Only what every client at the table may see goes in, and only what a
    client needs to decide whether its picture is stale: the counters a
    snapshot is identified by, whose move it is, and the public ``players``
    list (names, claims, presence), which a client may adopt as it stands.
    """

    decision = summary["decision"]
    return {
        "seq": session.event_seq,
        "revision": summary["revision"],
        "undo_count": summary["undo_count"],
        "log_count": summary["log_count"],
        "decision_owner": decision["owner"] if isinstance(decision, dict) else None,
        "confirmation": summary["confirmation"],
        "finished": summary["finished"],
        "players": summary["players"],
    }


def _log_epoch(session: GameSession, seat: int) -> str:
    """Name the log one seat has been served, as far as old entries go.

    Entries a client already holds stay valid while this value stays the
    same. It changes when an undo flags earlier entries, when the game
    finishes (or an undo un-finishes it) and redaction changes for every
    entry, and with the seat, whose redaction differs. The caller holds the
    session lock.
    """

    finished = 1 if _is_finished(session.state) else 0
    return f"{seat}:{session.undo_count}:{finished}"


def _log_entries_json(
    entries: tuple[LogEntry, ...], seat: int, finished: bool, after: int
) -> list[JsonValue]:
    return [
        _log_entry_json(index, entry, seat, finished)
        for index, entry in enumerate(entries)
        if index >= after
    ]


def _log_entry_json(
    index: int, entry: LogEntry, seat: int, finished: bool
) -> JsonObject:
    if isinstance(entry, LoggedUndo):
        return {
            "index": index,
            "type": "undo",
            "seat": entry.seat,
            "count": entry.count,
        }
    events: list[JsonValue] = [
        {"kind": event.kind, "payload": _jsonify(dict(event.payload))}
        for event in entry.events
        if finished or event.visible_to is None or seat in event.visible_to
    ]
    step = entry.step
    if isinstance(step, ChanceOutcome):
        payload: JsonObject = {
            "index": index,
            "type": "chance",
            "decision_id": step.decision_id,
            "undone": entry.undone,
            "events": events,
        }
        if finished:
            payload["values"] = list(step.values)
        return payload
    redact = not finished and step.actor != seat
    arguments = {
        key: ("(비공개)" if redact and value in entry.hidden_arguments else value)
        for key, value in step.arguments
    }
    return {
        "index": index,
        "type": "action",
        "actor": step.actor,
        "action_id": step.action_id,
        "arguments": _jsonify(arguments),
        "undone": entry.undone,
        "events": events,
    }


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


def _serialize_action(
    index: int, action: DomainAction, session: GameSession
) -> JsonObject:
    """Serialize one legal action.

    ``detail`` names a keyed icon's printed effect; ``undoable`` says whether
    the step could still be taken back afterwards (it could not once it
    reveals hidden information or hands the game to a chance outcome);
    ``strength_after`` is the acting seat's running combat strength once the
    step is taken, when the step changes it (``strength_preview``).
    """

    outcome = _dry_run(session, action)
    undoable = _action_is_undoable(session, action, outcome)
    serialized: JsonObject = {
        "index": index,
        "action_id": action.action_id,
        "arguments": _jsonify(dict(action.arguments)),
        "detail": effect_action_text(session.state, action),
        "undoable": undoable,
        "warning": shortfall_warning(outcome),
        "strength_after": strength_preview(session.state, action, outcome, undoable),
    }
    revealed = reveal_preview(action, outcome)
    if revealed is not None:
        serialized["reveal_preview"] = revealed
    return serialized


def reveal_preview(
    action: DomainAction, outcome: RuleResult | None
) -> JsonObject | None:
    """Return what revealing the hand right now would give the acting seat.

    For ``reveal_turn`` only: the Persuasion the Reveal would open with and
    the seat's combat strength once its revealed swords count, read off the
    same dry run as the rest (a Reveal sums Persuasion and swords as it
    starts [Main p. 12]; effects the owner resolves later in the Reveal are
    not in these figures). The listing goes to the seat that owns the hand,
    so the preview shows that seat nothing it cannot work out itself.
    """

    if action.action_id != "reveal_turn" or outcome is None:
        return None
    for frame in reversed(outcome.state.decision_stack):
        persuasion = dict(frame.context).get("persuasion")
        if str(frame.kind) == "reveal" and type(persuasion) is int:
            return {
                "persuasion": persuasion,
                "strength": outcome.state.players[action.actor].combat_strength,
            }
    return None


def strength_preview(
    before: GameState,
    action: DomainAction,
    outcome: RuleResult | None,
    undoable: bool,
) -> int | None:
    """Return the actor's combat strength after the step, if the step moves it.

    Read off the same dry run as the rest, so it is the engine's own figure
    (a first unit in the Conflict switches the seat's swords on, a last one
    off) rather than "2 per troop" worked out in the browser. Steps that
    cannot be taken back are left out: they reveal hidden information or
    hand over to chance, and their outcome is not the player's to preview.
    """

    if outcome is None or not undoable:
        return None
    after = outcome.state.players[action.actor].combat_strength
    return after if after != before.players[action.actor].combat_strength else None


def _dry_run(session: GameSession, action: DomainAction) -> RuleResult | None:
    """Apply ``action`` to a copy of the state; None when the engine refuses."""

    try:
        transition = session.engine.apply(session.state, action)
    except Exception:  # noqa: BLE001 - a failing dry run is reported as such
        return None
    return RuleResult(state=transition.state, events=transition.events)


def _action_is_undoable(
    session: GameSession, action: DomainAction, outcome: RuleResult | None
) -> bool:
    """Apply the undo-window rules to a dry run's outcome."""

    if outcome is None:
        return False
    after = outcome.state
    if reveals_hidden_information(session.state, after, action.actor):
        return False
    return not isinstance(session.engine.current_decision(after), ChanceDecision)


def shortfall_warning(outcome: RuleResult | None) -> str | None:
    """Describe a supply shortfall the action would run into, if any.

    Specimens and recruits come from the troop supply and a short supply
    simply yields fewer (OQ-030, OQ-049); the choice stays legal, so the
    player is told beforehand what the action will actually do.
    """

    if outcome is None:
        return None
    notes: list[str] = []
    for event in outcome.events:
        payload = dict(event.payload)
        if event.kind == "specimens_short":
            notes.append(
                "supply 부족: specimen "
                f"{payload.get('requested')}개 중 {payload.get('generated')}개만 생성"
            )
        elif event.kind == "troops_recruit_short":
            requested, recruited = payload.get("requested"), payload.get("recruited")
            notes.append(f"supply 부족: troop {requested}개 중 {recruited}개만 recruit")
    return " · ".join(notes) if notes else None


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
