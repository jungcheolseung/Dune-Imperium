"""What a seat may learn through the play server (cloud hidden-information
audit, 2026-11-02, docs/reviews/2026-11-cloud-hidden-info-audit.md).

docs/rules/information-visibility.md, Arrakeen Scouts: "**비밀 선택**(Covert
Operation, Offworld Operation). 고른 좌석만 자기 선택을 본다. 다른 좌석은 "누가
이미 골랐는가"만 본다. 공개 라운드의 Scouts 단계 맨 앞에서 전원에게 공개한다."
and "다음 라운드에 공개되지 않고 남은 선택은 두 라운드짜리 두 줄 가운데 하나임이
드러난다" -- so whether a pick falls due this round is hidden until that
Scouts step. OQ-103 places the engine's pauses before a reveal "공개된 사실로만",
so that a row's "undoable" and "sent_by_turn_end" marks never depend on what
another seat holds (``sessions._serialize_action``).

Each test plays a real remote game: four human seats, each claimed by its own
token, the moves chosen by seeded heuristic agents among the actions the
server offers the seat. Twins of one state that differ only in what one seat
may not know must give that seat the same payload.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium.agents import make_agent
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.observation import known_card_seats
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server import session_log
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.sessions import GameSession, GameSessionManager
from dune_imperium.simulation.invariants import _scramble_hidden_information

ADMIN_KEY = "hidden-info-audit-admin-key"
ADMIN = Credentials(admin_key=ADMIN_KEY)
ILESA = "ilesa_ecaz"
# Ilesa at seat 0 beside three Uprising Leaders.
LEADERS = (ILESA, "feyd_rautha_harkonnen", "gurney_halleck", "lady_jessica")


def _remote_table(
    options: dict[str, Any], seed: int, leaders: tuple[str, ...]
) -> tuple[GameSessionManager, str, dict[int, Credentials]]:
    """A remote game whose four human seats are claimed by four tokens, with
    ``leaders`` seated in order (the waiting room is started by the host)."""

    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    summary = manager.create_game(
        ("human",) * 4,
        game_seed=seed,
        seats_at_start=True,
        credentials=ADMIN,
        **options,
    )
    game_id = str(summary["game_id"])
    tokens = [manager.claim_seat(game_id, seat, f"P{seat}").token for seat in range(4)]
    session = manager._get(game_id)
    session.engine = UprisingRulesEngine(leader_ids=leaders)
    session.state = sessions_module._reset(
        session.engine, session.config, session.game_seed
    )
    manager.start_game(game_id, credentials=ADMIN)
    held = manager.held_seats(
        game_id, credentials=Credentials(seat_tokens=frozenset(tokens))
    )
    creds = {
        seat: Credentials(seat_tokens=frozenset({token}))
        for token, seat in held.items()
    }
    assert sorted(creds) == [0, 1, 2, 3]
    return manager, game_id, creds


def _play_until(
    manager: GameSessionManager,
    game_id: str,
    creds: dict[int, Credentials],
    seed: int,
    done: Any,
    limit: int = 2000,
) -> GameSession:
    """Play the seats' served actions with seeded heuristic agents until
    ``done(state)`` holds."""

    session = manager._get(game_id)
    agents = {
        seat: make_agent("heuristic", 7000 + seed * 10 + seat, session.config)
        for seat in range(4)
    }
    for _ in range(limit):
        state = session.state
        if done(state):
            return session
        if session.awaiting_confirmation is not None:
            seat = session.awaiting_confirmation
            manager.confirm_turn(
                game_id,
                seat,
                state.revision,
                undo_count=session.undo_count,
                credentials=creds[seat],
            )
            continue
        decision = session.engine.current_decision(state)
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        actions = session.engine.whole_actions(state, seat)
        chosen = sessions_module._choose(
            agents[seat], state, session.engine.observe(state, seat), actions
        )
        manager.apply_action(
            game_id,
            seat,
            state.revision,
            actions.index(chosen),
            undo_count=session.undo_count,
            credentials=creds[seat],
        )
    raise AssertionError("the game never reached the wanted state")


def _ilesa_sets_aside_after_round_one(state: GameState) -> bool:
    return (
        state.round_number >= 2
        and bool(state.decision_stack)
        and state.decision_stack[-1].kind == FrameKind.ROUND_START_SET_ASIDE
    )


def _marks(payload: dict[str, Any]) -> list[tuple[bool, bool]]:
    return [
        (bool(row["undoable"]), bool(row["sent_by_turn_end"]))
        for row in payload["actions"]
    ]


def test_ilesas_set_aside_rows_do_not_tell_whether_a_secret_pick_is_due() -> None:
    seed = 3
    manager, game_id, creds = _remote_table(
        {"rise_of_ix": True, "arrakeen_scouts": True}, seed, LEADERS
    )
    session = _play_until(
        manager, game_id, creds, seed, _ilesa_sets_aside_after_round_one
    )
    state = session.state
    round_number = state.round_number
    # Last round's Scouts step has run, this round's has not.
    assert state.scouts_secrets_round == round_number - 1

    # The one change made outside the rules: last round's Scouts item is
    # taken to have been Offworld Operation, every seat picking a line.
    # Lines 0 and 1 fall due one round later, lines 2 and 3 two
    # (``EVENTS_BY_ID["offworld_operation"]``). Ilesa (seat 0) and seats 1
    # and 3 picked line 2; seat 2 picked line 2 or line 0. Ilesa cannot tell
    # those apart: seat 2's pick is its own until it is due.
    def picks(seat_two: int) -> tuple[tuple[int, str, int, int], ...]:
        return tuple(
            (round_number - 1, "offworld_operation", seat, seat_two if seat == 2 else 2)
            for seat in range(4)
        )

    not_due = replace(state, scouts_secret_picks=picks(2))
    due = replace(state, scouts_secret_picks=picks(0))
    payloads: list[dict[str, Any]] = []
    for twin in (not_due, due):
        session.state = twin
        payloads.append(manager.legal_actions(game_id, 0, credentials=creds[0]))
    session.state = state
    assert [str(row["action_id"]) for row in payloads[0]["actions"]] == [
        "set_aside_leader_card"
    ] * len(payloads[0]["actions"])
    # The same rows, marked the same way, whichever line seat 2 picked: the
    # set-aside stops at the pause before the Scouts step (OQ-103 6), so each
    # row is a step she may take back until her turn end.
    assert _marks(payloads[0]) == _marks(payloads[1])
    assert set(_marks(payloads[0])) == {(True, False)}


def test_ilesas_set_aside_waits_for_her_turn_end_before_the_scouts_step() -> None:
    """The set-aside is "place -> 턴 종료" like any unit's last step outside
    the turns (OQ-103 6): the server holds it before the pause, she may take
    it back and choose again, and her press runs the round's Scouts step."""

    seed = 3
    manager, game_id, creds = _remote_table(
        {"rise_of_ix": True, "arrakeen_scouts": True}, seed, LEADERS
    )
    session = _play_until(
        manager, game_id, creds, seed, _ilesa_sets_aside_after_round_one
    )
    round_number = session.state.round_number
    hand = session.state.players[0].hand
    assert hand[0] != hand[-1]
    for card_id in (hand[0], hand[-1]):
        state = session.state
        payload: dict[str, Any] = manager.legal_actions(
            game_id, 0, credentials=creds[0]
        )
        index = next(
            index
            for index, row in enumerate(payload["actions"])
            if row["arguments"] == {"card_id": card_id}
        )
        manager.apply_action(
            game_id,
            0,
            state.revision,
            index,
            undo_count=session.undo_count,
            credentials=creds[0],
        )
        assert session.awaiting_confirmation == 0
        assert session.state.players[0].set_aside_card_id == card_id
        top = session.state.decision_stack[-1]
        assert top.frame_id == f"round:{round_number}:scouts_step:pause"
        # Nothing of the Scouts step has run yet.
        assert session.state.scouts_secrets_round == round_number - 1
        if card_id == hand[0]:
            manager.undo(
                game_id,
                0,
                session.state.revision,
                undo_count=session.undo_count,
                credentials=creds[0],
            )
            assert session.awaiting_confirmation is None
            assert session.state.players[0].set_aside_card_id == ""
            assert session.state.decision_stack[-1].kind == (
                FrameKind.ROUND_START_SET_ASIDE
            )
    manager.confirm_turn(
        game_id,
        0,
        session.state.revision,
        undo_count=session.undo_count,
        credentials=creds[0],
    )
    assert session.awaiting_confirmation is None
    assert session.state.players[0].set_aside_card_id == hand[-1]
    assert session.state.scouts_secrets_round == round_number


# --- The general guarantee, swept over a game ---------------------------------

# Frames whose context names a card only their owner was shown (a peeked deck
# top, Long Live the Fighters' three, Imperium Ceremony's or Hundro's two
# Intrigue cards, Kota Odax's bottom Tech tiles). ``_scramble_hidden_information``
# keeps the cards themselves in place for their owner only, so while one of
# these is up a twin may not be a state the rules can reach.
_GLIMPSE_FRAMES = frozenset(
    {
        FrameKind.LONG_LIVE_FIGHTERS,
        FrameKind.INTRIGUE_PEEK,
        FrameKind.TECH_SECRET_PROJECT,
    }
)
_EVERYONE = frozenset(range(4))


def _scrambled_twin_is_reachable(state: GameState) -> bool:
    if not state.decision_stack:
        return True
    frame = state.decision_stack[-1]
    return frame.kind not in _GLIMPSE_FRAMES and "peeked_card_id" not in dict(
        frame.context
    )


def _payloads(
    manager: GameSessionManager, session: GameSession, seat: int, owner: bool
) -> dict[str, Any]:
    state = session.state
    view = session.engine.observe(state, seat)
    served: dict[str, Any] = {
        "view": sessions_module._serialize_view(view, state),
        "summary": manager._summary_locked(session),
    }
    if owner:
        served["actions"] = manager._legal_actions_locked(session, seat)
    return served


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list | tuple):
        return [text for item in value for text in _strings(item)]
    return []


def _names(text: str, card_id: str) -> bool:
    """Whether ``text`` is ``card_id`` or carries it as a ``:`` part."""

    return (
        text == card_id
        or text.startswith(f"{card_id}:")
        or text.endswith(f":{card_id}")
        or f":{card_id}:" in text
    )


SWEEPS: dict[str, tuple[dict[str, Any], tuple[str, ...]]] = {
    "uprising_everything": (
        {
            "choam_module": True,
            "bloodlines": True,
            "tech_module": True,
            "immortality": True,
            "rise_of_ix": True,
            "arrakeen_scouts": True,
            "promo_cards": True,
        },
        (ILESA, "viscount_hundro_moritani", "kota_odax_of_ix", "tessia_vernius"),
    ),
    "original_everything": (
        {
            "base_game": "imperium",
            "bloodlines": True,
            "tech_module": True,
            "immortality": True,
            "rise_of_ix": True,
            "arrakeen_scouts": True,
            "promo_cards": True,
        },
        (
            "baron_vladimir_harkonnen",
            "paul_atreides",
            ILESA,
            "viscount_hundro_moritani",
        ),
    ),
}


@pytest.mark.parametrize("name", sorted(SWEEPS))
def test_what_each_seat_is_served_reads_nothing_it_may_not_know(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every seat's view, the summary and the owner's actions with their dry
    runs are the same on a twin that moves only what that seat may not know
    (``_scramble_hidden_information``, the engine sweep's privacy check), and
    every log entry served to a seat other than its actor names only cards
    that seat can identify before or after the step (``known_card_seats``;
    "before" covers a card the seat gave away or had stolen). Played up to
    revision 260 (round 3 or later) with Ilesa, Hundro, Kota and Tessia on
    Uprising, the Baron, Paul, Ilesa and Hundro on the original game."""

    options, leaders = SWEEPS[name]
    seed = 5
    manager, game_id, creds = _remote_table(options, seed, leaders)
    session = manager._get(game_id)
    logged: list[tuple[Any, GameState, GameState]] = []
    log_step = session_log.log_step

    def spy(before: GameState, after: GameState, step: Any, events: Any) -> Any:
        entry = log_step(before, after, step, events)
        logged.append((entry, before, after))
        return entry

    checked = 0

    def check(state: GameState) -> bool:
        nonlocal checked
        decision = session.engine.current_decision(state)
        owner = decision.owner if isinstance(decision, PlayerDecision) else None
        if _scrambled_twin_is_reachable(state):
            for seat in range(4):
                acts = (
                    owner == seat
                    and session.awaiting_confirmation != seat
                    and not manager._turn_is_held_locked(session)
                )
                real = _payloads(manager, session, seat, acts)
                twin = copy.copy(session)
                twin.state = _scramble_hidden_information(state, seat)
                assert _payloads(manager, twin, seat, acts) == real, (name, seat)
        for entry, before, after in logged[checked:]:
            known_before, known_after = (
                known_card_seats(before),
                known_card_seats(after),
            )
            for seat in range(4):
                if entry.actor == seat:
                    continue
                hidden = [
                    card_id
                    for card_id, seats in known_after.items()
                    if seat not in seats
                    and seat not in known_before.get(card_id, _EVERYONE)
                ]
                served = sessions_module._log_entry_json(0, entry, seat, False)
                for text in _strings(
                    [served.get(key) for key in ("arguments", "events", "decision_id")]
                ):
                    assert not any(_names(text, card) for card in hidden), (
                        name,
                        seat,
                        text,
                    )
        checked = len(logged)
        return state.revision >= 260

    monkeypatch.setattr(sessions_module, "log_step", spy)
    _play_until(manager, game_id, creds, seed, check)
    assert session.state.round_number >= 3
