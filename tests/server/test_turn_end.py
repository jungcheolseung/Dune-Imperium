"""Tests for the one-press turn-end convention (2026-09-23, OQ-095).

Every turn end of a human seat is exactly one press of "턴 종료" (project
convention, not a rule; see the module docstring of
``dune_imperium.server.turn_end``). Since user ruling OQ-095 an Agent turn
ends only through its owner's ``finish_agent_turn``, which is that press
itself, and so is a turn-passing card (Withdrawn, Litany Against Fear;
OQ-095 (6)); the server still holds the other unit ends (a Leader pick in
the OQ-007 draft, Conflict rewards, a Control defense, an Arrakeen Scouts
line) for ``confirm_turn`` -- since 2026-10-08 only while the seat has a
step to take back, before the chance outcomes after the unit; a step it
could not take back is sent with the browser's "확정 ▶" instead
(``sent_by_turn_end``). Which steps end a turn is a reading of the
engine's own decision stack, so these tests exercise the session layer
(``turn_end.py`` + ``sessions.py``), not any card or Main-rules behaviour --
the cards used to reach a scenario (Covert Operation, Holy War, Usurp) are
exercised for their card text elsewhere (``tests/unit/rules/
test_agent_effects.py``, ``tests/unit/rules/test_bloodlines_cards.py``,
``tests/unit/rules/test_immortality_tleilaxu_cards.py``); here they are only
a vehicle to reach a decision-stack shape.

Every seed below was found by a scratch search over seeds, not guessed.
"""

import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.registry import make_agent
from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.rules.combat import (
    _conflict_end_trigger_cards,
    _conflict_losses,
    rank_combat,
)
from dune_imperium.rules.combat_deployment import FINISHING_KEY
from dune_imperium.rules.engine import UprisingRulesEngine, _advance_automatic
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, FrameKind
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.persistence import SaveError
from dune_imperium.server.session_log import LoggedStep, live_steps, log_step
from dune_imperium.server.sessions import (
    AGENT_TURN_END_PROMPT,
    GameSession,
    GameSessionManager,
    JsonObject,
    SessionError,
)
from dune_imperium.server.turn_end import (
    EXPLICIT_TURN_ENDS,
    TURN_PASS_EVENTS,
    TURN_TAKING_EVENTS,
    agent_turn_end_ready,
    answers_another_unit,
    at_turn_start,
    finishing_seat,
    own_unit_outside_turns,
    turn_start_seat,
    unit_over,
    unit_seat,
)

# The AI seats play the rubric-priced 2026-09-10 table pinned in the registry,
# not ``heuristic`` (see tests/server/test_undo.py): the scripted seeds below
# follow that table's moves, and ``heuristic`` is retuned as the baseline
# improves.
HUMAN_FIRST = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
TWO_HUMANS = ("human", "human", "heuristic_uprising_table", "heuristic_uprising_table")
HUMAN_VS_RANDOM_AI = ("human", "random", "random", "random")
_PROMPTS_KO = Path(sessions_module.__file__).with_name("static") / "prompts_ko.js"


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _play_until(
    manager: GameSessionManager,
    game_id: str,
    summary: JsonObject,
    predicate: object,
) -> JsonObject:
    """Advance by the decision owner's first legal action, confirming any
    hold at once, until ``predicate(summary)`` holds. Used to walk a game
    forward to a scripted point with a deterministic, index-0 policy."""

    while not predicate(summary):  # type: ignore[operator]
        if summary["finished"]:
            raise AssertionError("the game finished before the condition was met")
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)
    return summary


def _play_until_seat0_offers(
    manager: GameSessionManager,
    game_id: str,
    summary: JsonObject,
    action_id: str,
    *,
    kind: str | None = None,
) -> tuple[JsonObject, int]:
    """Advance like ``_play_until``, stopping right before seat 0 would take
    its default (index-0) action, whenever ``action_id`` is one of its
    options (and, with ``kind``, the decision is of that frame kind).
    Returns the summary and that option's index."""

    while True:
        if summary["finished"]:
            raise AssertionError(f"the game finished before {action_id} was offered")
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        decision = _obj(summary["decision"])
        owner = _int(decision["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        if owner == 0 and (kind is None or decision["kind"] == kind):
            for entry in actions:
                if entry["action_id"] == action_id:
                    return summary, _int(entry["index"])
        summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)


# ------------------------------------------------------------- leader draft


def test_the_last_leader_pick_waits_for_an_explicit_end_before_round_one() -> None:
    # OQ-007 (2026-10-05): the last picker gets the same reversible choice
    # as the first three; its turn-end press precedes all hidden setup.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    assert summary["first_player"] == 0
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    assert summary["confirmation"] is None
    assert summary["phase"] == "setup"
    assert summary["undo"] == [{"seat": 0, "steps": 1}]
    assert _obj(summary["decision"])["kind"] == "leader_draft"
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [(a["action_id"], a["undoable"]) for a in actions] == [
        ("finish_leader_draft", False)
    ]
    assert manager.snapshot(game_id, 0)["actions"] is not None
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    assert summary["confirmation"] is None
    assert summary["undo"] == []
    assert _obj(summary["decision"])["kind"] == "turn"
    assert _rows(manager.legal_actions(game_id, 0)["actions"])
    with pytest.raises(SessionError, match="no turn end"):
        manager.confirm_turn(game_id, 0, _int(summary["revision"]))


def test_a_non_last_leader_pick_holds_before_the_next_picker() -> None:
    # Seed 1: seat 0 is not the First Player (first_player == 3), so at
    # least one seat still picks after it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = str(summary["game_id"])
    assert summary["first_player"] != 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    pick = actions[0]
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(pick["index"])
    )

    assert summary["confirmation"] == 0
    decision = _obj(summary["decision"])
    assert decision["kind"] == "leader_draft"
    assert decision["owner"] != 0
    assert manager.legal_actions(game_id, 0)["actions"] == []

    confirmed = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert confirmed["confirmation"] is None
    # Seat 0 is the only human seat, so every remaining pick belongs to an
    # AI seat: the confirmation's own auto-advance runs the whole rest of
    # the draft and opens straight onto seat 0's first round-1 turn.
    assert _obj(confirmed["decision"])["kind"] == "turn"
    assert _obj(confirmed["decision"])["owner"] == 0


# ------------------------------------------------------- explicit turn ends


def test_finish_agent_turn_is_the_press_itself() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "finish_agent_turn"
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "finish_agent_turn")
    assert entry["undoable"] is False

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert _int(summary["revision"]) > before_revision
    # No second step: this seed's finish_agent_turn hands over through the
    # other seats' turns and straight back to seat 0's own next turn,
    # already open -- never blocked behind a fresh hold.
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert manager.legal_actions(game_id, 0)["actions"] != []


def test_finish_reveal_is_the_press_itself() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "finish_reveal"
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "finish_reveal")
    assert entry["undoable"] is False
    # This scenario's seat 0 already holds an open (undoable) window from
    # earlier this turn: the seal below is a real one, not a no-op on an
    # already-empty window.
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] != []

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert _int(summary["revision"]) > before_revision


def test_pass_combat_intrigue_is_the_press_itself() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "pass_combat_intrigue"
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "pass_combat_intrigue")
    assert entry["undoable"] is False

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert _int(summary["revision"]) > before_revision


def _critical_moment_session() -> tuple[GameSessionManager, str]:
    """Four human seats, seat 0 about to call in Critical Moment (round 5)."""

    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, game_seed=17, arrakeen_scouts=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    engine = session.engine
    rich = Resources(solari=6, spice=6, water=2)
    state = replace(
        session.state,
        round_number=5,
        first_player=0,
        players=tuple(replace(p, resources=rich) for p in session.state.players),
        decision_stack=(),
        scouts_opening=True,
        scouts_secrets_round=5,
        scouts_mid_auction_round=5,
        scouts_late_auction_round=9,
    )
    while True:
        state = _advance_automatic(RuleResult(state=state)).state
        frame = state.decision_stack[-1]
        assert frame.kind == FrameKind.SCOUTS_DRAW
        decision = frame.decision
        assert isinstance(decision, ChanceDecision)
        wanted = [o for o in decision.options if o.startswith("critical_moment_mid")]
        value = wanted[0] if wanted else decision.options[0]
        state = engine.apply(
            state, ChanceOutcome(decision_id=decision.decision_id, values=(value,))
        ).state
        if wanted:
            break
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CALL
    session.state = state
    return manager, game_id


def test_an_open_auction_call_is_the_press_itself() -> None:
    """User request 2026-10-05: "아라킨 스카웃 경매 0 누르면 바로
    확정되버리네. 이거도 턴 종료를 눌러야 확정되게 해줘." The browser now
    stages the amount on the stepper and sends Critical Moment's open call
    with the turn-end press, so the call itself seals the seat's unit, like
    a sealed bid's ``confirm_scouts_bid``: no second press, nothing left to
    take back, and the next seat calls at once."""

    manager, game_id = _critical_moment_session()
    summary = manager.summary(game_id)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    index = next(
        _int(a["index"])
        for a in actions
        if a["action_id"] == "scouts_call" and _obj(a["arguments"])["count"] == 0
    )
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), index)

    assert summary["confirmation"] is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    decision = _obj(summary["decision"])
    assert decision["kind"] == "scouts_call" and decision["owner"] == 1


def test_an_explicit_end_handing_straight_to_a_human_still_seals_the_turn() -> None:
    # Seed 0, two human seats: seat 0's finish_agent_turn hands straight to
    # human seat 1 with nothing else logged in between (no chance outcome,
    # no other seat's step). The log alone only closes a seat's undo window
    # at the next chance outcome or other seat's step -- there is none here
    # before seat 1 must act -- so the explicit-end branch of
    # ``_settle_locked`` has to seal it itself
    # (``session.undo_floor = len(session.steps)``), same as ``confirm_turn``
    # does for a held turn (test_undo.py::
    # test_a_confirmed_turn_end_stays_handed_over_to_the_next_human).
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "finish_agent_turn"
    )
    steps_before = len(session.steps)

    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), index)

    # Exactly the one explicit-end step -- no chance outcome interposed.
    assert len(session.steps) == steps_before + 1
    decision = _obj(summary["decision"])
    assert decision["owner"] == 1
    assert decision["owner_is_human"] is True
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="at most 0 step"):
        manager.undo(game_id, 0, _int(summary["revision"]))


# ------------------------------------------------------- turn-passing cards

_STARTERS = starting_deck_instance_ids(0)
_DAGGER = next(card for card in _STARTERS if ":dagger:" in card)


def _turn_pass_game(owner: PlayerState) -> tuple[GameSessionManager, str]:
    """Seat 0's fresh turn holding a turn-passing card, human seat 1 next.

    The card-level setup of tests/unit/rules/test_bloodlines_cards.py::
    test_litany_against_fear_draws_and_passes_the_turn and
    tests/unit/rules/test_twisted_intrigue.py::
    test_withdrawn_passes_the_turn_and_only_at_its_start. Seats 2 and 3 (AI)
    have revealed, so the pass hands the turn straight to human seat 1 and
    nothing auto-plays past it.
    """

    state = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=(
            owner,
            PlayerState(player_id=1, hand=(_DAGGER.replace("player:0:", "player:1:"),)),
            PlayerState(player_id=2, has_revealed=True),
            PlayerState(player_id=3, has_revealed=True),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=0, bloodlines=True)
    game_id = str(summary["game_id"])
    manager._get(game_id).state = state
    return manager, game_id


@pytest.mark.parametrize(
    ("owner", "action_id", "event"),
    [
        pytest.param(
            PlayerState(
                player_id=0,
                hand=("imperium:litany_against_fear:0",),
                deck=_STARTERS[1:5],
            ),
            "play_turn_start_card",
            "turn_start_card_played",
            id="litany_against_fear",
        ),
        pytest.param(
            PlayerState(
                player_id=0,
                leader_id="piter_de_vries",
                intrigue_cards=("intrigue:twisted_withdrawn:0",),
                hand=(_DAGGER,),
            ),
            "play_intrigue",
            "turn_passed",
            id="withdrawn",
        ),
    ],
)
def test_a_turn_passing_card_is_the_press_itself(
    owner: PlayerState, action_id: str, event: str
) -> None:
    # OQ-095 (6): a turn-passing card is the seat's turn end itself -- "카드
    # 효과로 턴 넘김 버튼을 눌렀다면 그건 턴 종료를 누른거랑 같으니까", "카드
    # 사용이 곧 턴 종료" (user, 2026-10-01). The play is listed as one that
    # cannot be taken back (Withdrawn's play alone reveals nothing, so only
    # this rule seals it), seals the seat's steps and hands over at once:
    # no confirm_turn follows it.
    manager, game_id = _turn_pass_game(owner)
    session = manager._get(game_id)
    calls: list[str] = []
    manager.add_hand_over_listener(calls.append)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == action_id)
    assert entry["undoable"] is False

    log_before = len(session.log)
    summary = manager.apply_action(game_id, 0, 0, _int(entry["index"]))

    assert event in TURN_PASS_EVENTS
    assert event in {
        logged.kind
        for step in live_steps(session.log[log_before:])
        for logged in step.events
    }
    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn"
    assert decision["owner"] == 1 and decision["owner_is_human"] is True
    assert _rows(manager.legal_actions(game_id, 1)["actions"])
    assert calls == [game_id]
    assert 0 not in session.open_units
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="at most 0 step"):
        manager.undo(game_id, 0, _int(summary["revision"]))
    with pytest.raises(SessionError, match="no turn end to confirm"):
        manager.confirm_turn(game_id, 0, _int(summary["revision"]))


def test_a_turn_start_card_goes_once_the_seat_acted() -> None:
    # "At the start of your turn" [Litany Against Fear card]: only the
    # turn's first action (OQ-095 (6), user ruling 2026-10-04). A Plot at
    # the turn start leaves the seat on the same turn frame, with no hold,
    # and without Litany (greyed out with the reason). (Undo rebuilds by
    # replaying the engine's steps, which set the same mark; this injected
    # state cannot be rebuilt from the session's seed, so it is not undone.)
    plot = "intrigue:contingency_plan:0"
    owner = PlayerState(
        player_id=0,
        hand=("imperium:litany_against_fear:0",),
        deck=_STARTERS[1:5],
        intrigue_cards=(plot,),
    )
    manager, game_id = _turn_pass_game(owner)

    def offered() -> set[str]:
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        return {str(action["action_id"]) for action in actions}

    assert "play_turn_start_card" in offered()
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    entry = next(a for a in actions if a["action_id"] == "play_intrigue")
    summary = manager.apply_action(game_id, 0, 0, _int(entry["index"]))

    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn" and decision["owner"] == 0
    assert "play_turn_start_card" not in offered()
    assert "reveal_turn" in offered()
    payload = _obj(manager.legal_actions(game_id, 0)["unavailable"])
    (row,) = [
        row
        for row in _rows(payload["rows"])
        if _obj(row["action"])["action_id"] == "play_turn_start_card"
    ]
    assert row["code"] == "turn_started"


# --------------------------------------------------- Usurp's finishing press

_IMMORTALITY_STARTERS = starting_deck_instance_ids(0, immortality=True)
_USURP = "tleilaxu:usurp:0"
_STANDARD = "imperium:sardaukar_standard:0"


def _usurp_seat(seat: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": seat,
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _usurp_game(manager: GameSessionManager) -> str:
    """Seat 0's fresh turn holding Usurp, Sardaukar Standard in the Row.

    The engine-level setup of tests/unit/rules/
    test_immortality_tleilaxu_cards.py::
    test_usurped_sardaukar_standard_commander_is_this_turns_and_reopens_it:
    every other seat has revealed, so seat 0's own next turn follows its
    turn end and no AI seat plays.
    """

    experimentation = next(
        card for card in _IMMORTALITY_STARTERS if "experimentation:0" in card
    )
    imperium = imperium_deck_instance_ids(False)
    skills = skill_tile_instance_ids()
    hand = (_USURP, experimentation)
    owner = _usurp_seat(
        0,
        hand=hand,
        deck=tuple(card for card in _IMMORTALITY_STARTERS if card not in hand),
        resources=Resources(solari=4, spice=2, water=2),
    )
    state = GameState(
        config=RulesetConfig(bloodlines=True, immortality=True, promo_cards=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=(_STANDARD, *imperium[1:5]),
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        sardaukar_commanders_bank=1,
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
        players=(
            owner,
            *(_usurp_seat(seat, has_revealed=True) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    summary = manager.create_game(
        HUMAN_FIRST, game_seed=0, bloodlines=True, immortality=True, promo_cards=True
    )
    game_id = str(summary["game_id"])
    manager._get(game_id).state = state
    return game_id


@pytest.mark.parametrize(
    ("space_id", "reopens"),
    [
        # A Combat space: the Commander the trash recruits may deploy, so
        # the turn reopens for it [Main p. 10] (OQ-095 (5)).
        pytest.param("arrakeen", True, id="combat_space_reopens"),
        # No Combat deployment window: the turn closes after the choice.
        pytest.param("dutiful_service", False, id="other_space_hands_over"),
    ],
)
def test_a_usurp_trash_after_the_press_is_part_of_that_press(
    space_id: str, reopens: bool
) -> None:
    # OQ-095 (4)-(5): the press trashes the Usurped Sardaukar Standard, and
    # its Skill choice resolves on top of the owner's waiting ("finishing")
    # frame. Answering it is still that one press (turn_end.finishing_seat):
    # it is not held, cannot be taken back, and the turn then either hands
    # over or reopens (agent_turn_reopened) for a second press of its own --
    # never a confirm_turn.
    manager = GameSessionManager()
    game_id = _usurp_game(manager)
    session = manager._get(game_id)
    summary = manager.summary(game_id)

    def take(entry: dict[str, object]) -> JsonObject:
        taken = manager.apply_action(
            game_id, 0, _int(manager.summary(game_id)["revision"]), _int(entry["index"])
        )
        assert taken["confirmation"] is None
        return taken

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    take(
        next(
            a
            for a in actions
            if a["action_id"] == "agent_turn"
            and _obj(a["arguments"]).get("card_id") == _USURP
            and _obj(a["arguments"]).get("space_id") == space_id
            and _obj(a["arguments"]).get("graft") is True
            and "infiltrate_post_id" not in _obj(a["arguments"])
        )
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    summary = take(
        next(
            a
            for a in actions
            if a["action_id"] == "choose_graft_partner"
            and _obj(a["arguments"])["card_id"] == _STANDARD
        )
    )
    for _ in range(20):
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        if any(a["action_id"] == "finish_agent_turn" for a in actions):
            break
        assert _obj(summary["decision"])["turn_end_ready"] is False
        summary = take(
            next(a for a in actions if not str(a["action_id"]).startswith("deploy"))
        )
    else:
        raise AssertionError("the turn end was never offered")
    assert _obj(summary["decision"])["turn_end_ready"] is True
    assert session.state.players[0].usurped_row_card_id == _STANDARD
    press = next(a for a in actions if a["action_id"] == "finish_agent_turn")
    assert press["undoable"] is False

    summary = take(press)

    # The trash left its Skill choice above the waiting frame.
    decision = _obj(summary["decision"])
    assert decision["kind"] == "skill_choice" and decision["owner"] == 0
    assert decision["turn_end_ready"] is False
    assert finishing_seat(session.state) == 0
    assert agent_turn_end_ready(session.state) is None
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    choices = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert choices and all(a["undoable"] is False for a in choices)
    log_before = len(session.log)

    summary = take(choices[0])

    assert finishing_seat(session.state) is None
    owner = session.state.players[0]
    assert _STANDARD in owner.trashed and owner.usurped_row_card_id == ""
    assert owner.commanders_garrison == 1
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="at most 0 step"):
        manager.undo(game_id, 0, _int(summary["revision"]))
    reopened = "agent_turn_reopened" in {
        logged.kind
        for step in live_steps(session.log[log_before:])
        for logged in step.events
    }
    assert reopened is reopens
    decision = _obj(summary["decision"])
    if reopens:
        # The reopened turn waits for its own second press, with the new
        # Commander's deployment offered beside it.
        assert decision["kind"] == "agent_effects" and decision["owner"] == 0
        assert decision["turn_end_ready"] is True
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        offered = {str(a["action_id"]) for a in actions}
        assert {"deploy_commanders", "finish_agent_turn"} <= offered
        summary = take(
            next(a for a in actions if a["action_id"] == "finish_agent_turn")
        )
        decision = _obj(summary["decision"])
    # Every other seat has revealed: seat 0's own fresh turn, open at once.
    assert decision["kind"] == "turn" and decision["owner"] == 0
    assert 0 not in session.open_units
    assert _rows(manager.legal_actions(game_id, 0)["actions"])
    with pytest.raises(SessionError, match="no turn end to confirm"):
        manager.confirm_turn(game_id, 0, _int(summary["revision"]))


# ------------------------------------------------------------- interrupts


def test_a_human_answering_an_opponent_interrupt_is_not_held() -> None:
    # Seed 22 (bloodlines, three "random" AI opponents): a Holy War-like
    # effect from an AI seat forces seat 0 to lose one unit while that AI's
    # own turn is still open. Answering it is not a turn end of seat 0's.
    # (Re-searched 2026-09-26: the card-transcription audit's rules fixes
    # moved the old seed 12 off this shape. Re-searched again 2026-10-01:
    # every Agent turn now waits for its owner's finish_agent_turn (OQ-095),
    # which moved seed 7 off it; seed 12 was the only one of 0-39 reaching
    # it under this index-0 walk. Re-searched 2026-10-14 -- v146: optional
    # Agent-turn effects offer no refusal (OQ-095 (2), 2026-10-14), which
    # moved seed 12 off it; of 0-79 seeds 22, 56 and 72 reach it.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_VS_RANDOM_AI, game_seed=22, bloodlines=True)
    game_id = str(summary["game_id"])
    summary = _play_until(
        manager,
        game_id,
        summary,
        lambda s: _obj(s["decision"])["kind"] == "opponent_unit_loss"
        and _obj(s["decision"])["owner"] == 0,
    )
    assert summary["confirmation"] is None
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert actions

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, 0)
    assert summary["confirmation"] is None


_HOLY_WAR = "imperium:holy_war:0"


def _holy_war_game(loser: PlayerState) -> tuple[GameSessionManager, str]:
    """Human seat 0 has sent Holy War to Assembly Hall, its Agent box still
    to resolve; human seat 1 is ``loser``, AI seats 2 and 3 hold three
    garrison troops each. The card-level setup of
    tests/unit/rules/test_bloodlines_cards.py::
    test_holy_war_makes_each_opponent_lose_a_unit_and_move_its_spy."""

    owner = PlayerState(player_id=0, hand=(_HOLY_WAR,), deck=_STARTERS[:4])
    state = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=(owner, loser, PlayerState(player_id=2), PlayerState(player_id=3)),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=0, bloodlines=True)
    game_id = str(summary["game_id"])
    manager._get(game_id).state = state
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    send = next(
        a
        for a in actions
        if a["action_id"] == "agent_turn"
        and _obj(a["arguments"]).get("card_id") == _HOLY_WAR
        and _obj(a["arguments"]).get("space_id") == "assembly_hall"
    )
    summary = manager.apply_action(game_id, 0, 0, _int(send["index"]))
    # Assembly Hall's own Intrigue card first, so only the box is left.
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    board = next(a for a in actions if a["action_id"] == "resolve_board_effect")
    manager.apply_action(game_id, 0, _int(summary["revision"]), _int(board["index"]))
    return manager, game_id


@pytest.mark.parametrize(
    ("loser", "answer", "event"),
    [
        pytest.param(
            PlayerState(player_id=1), "lose_unit", "unit_lost", id="one_option"
        ),
        pytest.param(
            PlayerState(player_id=1, troops_supply=12, troops_garrison=0),
            "resolve_unit_loss_without_unit",
            "unit_loss_unavailable",
            id="no_unit",
        ),
    ],
)
def test_the_holy_war_owner_waits_for_a_human_opponents_unit_loss(
    loser: PlayerState, answer: str, event: str
) -> None:
    # User ruling 2026-09-30 (OQ-036 (a)): every opponent is asked, even
    # with a single option or none ("선택지가 단 하나여도 어쨌든 확인을
    # 거치는 걸로 통일하는게 깔끔해"). The window sits above the owner's
    # still-open Agent turn (OQ-095), so the owner's turn end is not offered
    # until the human opponent has answered (``agent_turn_end_ready``), and
    # that answer is an interrupt, not a turn end of the opponent's own: it
    # is not held for confirm_turn.
    manager, game_id = _holy_war_game(loser)
    session = manager._get(game_id)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [a["action_id"] for a in actions] == ["resolve_agent_card_effect"]
    box = actions[0]
    summary = manager.apply_action(
        game_id, 0, _int(manager.summary(game_id)["revision"]), _int(box["index"])
    )

    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["kind"] == "opponent_unit_loss"
    assert decision["owner"] == 1 and decision["owner_is_human"] is True
    assert decision["turn_end_ready"] is False
    assert agent_turn_end_ready(session.state) is None
    assert manager.legal_actions(game_id, 0)["actions"] == []
    with pytest.raises(SessionError, match="no turn end to confirm"):
        manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    payload = manager.legal_actions(game_id, 1)
    offered = _rows(payload["actions"])
    assert [a["action_id"] for a in offered] == [answer]
    # The zones it cannot lose from are shown greyed out with the reason.
    greyed = _rows(_obj(payload["unavailable"])["rows"])
    assert {row["surface"] for row in greyed} == {"choice"}
    assert {row["reason_ko"] for row in greyed} == (
        {"잃을 유닛 없음"} if answer != "lose_unit" else {"{conflict}에 {troop} 없음"}
    )

    log_before = len(session.log)
    summary = manager.apply_action(
        game_id, 1, _int(summary["revision"]), _int(offered[0]["index"])
    )

    assert summary["confirmation"] is None
    assert 1 not in session.open_units
    with pytest.raises(SessionError, match="no turn end to confirm"):
        manager.confirm_turn(game_id, 1, _int(summary["revision"]))
    logged = [
        (entry.kind, dict(entry.payload).get("player"))
        for step in live_steps(session.log[log_before:])
        for entry in step.events
    ]
    # Seat 1's own answer, then AI seats 2 and 3 answer theirs at once.
    assert (event, 1) in logged
    assert ("unit_lost", 2) in logged and ("unit_lost", 3) in logged
    # Every opponent has answered: the owner's turn end is offered now.
    decision = _obj(summary["decision"])
    assert decision["kind"] == "agent_effects" and decision["owner"] == 0
    assert decision["turn_end_ready"] is True
    offered = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert "finish_agent_turn" in {a["action_id"] for a in offered}


def _covert_operation_instance(card_id: str) -> str:
    return next(i for i in imperium_deck_instance_ids(False) if f":{card_id}:" in i)


def _starter_instance(card_id: str) -> str:
    return next(i for i in starting_deck_instance_ids(0) if f":{card_id}:" in i)


def test_a_humans_own_covert_operation_does_not_hold_it_mid_turn() -> None:
    # The Covert Operation mechanic (each opponent with cards in hand
    # discards one) is already exercised for its card text in
    # tests/unit/rules/test_agent_effects.py::
    # test_covert_operation_makes_opponents_with_cards_discard_clockwise,
    # whose fixture is reused here to reach the decision-stack shape
    # directly (an organic search across 250+ seeds never got the card
    # acquired, cycled back into hand, and played before the opponents'
    # hands emptied in the same game -- see the report).
    covert_operation = _covert_operation_instance("covert_operation")
    first_discard = _starter_instance("dagger").replace("player:0:", "player:1:")
    second_discard = _covert_operation_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(covert_operation,),
        resources=Resources(solari=10, spice=10, water=10),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            PlayerState(player_id=1, hand=(first_discard,)),
            PlayerState(player_id=2, hand=(second_discard,)),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    session.state = state

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    agent_turn = next(
        a
        for a in actions
        if a["action_id"] == "agent_turn"
        and _obj(a["arguments"])["space_id"] == "assembly_hall"
    )
    summary = manager.apply_action(game_id, 0, 0, _int(agent_turn["index"]))
    assert summary["confirmation"] is None

    # Assembly Hall's own Gather Intelligence choice comes first and must be
    # cleared before the personal-card effect is offered.
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    decline = next(
        a for a in actions if a["action_id"] == "decline_gather_intelligence"
    )
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(decline["index"])
    )
    assert summary["confirmation"] is None

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    resolve = next(a for a in actions if a["action_id"] == "resolve_agent_card_effect")
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(resolve["index"])
    )

    # The AI seats' discards happened inside this one call; the decision is
    # back with seat 0's own still-open turn, never held.
    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["kind"] == "agent_effects"
    session = manager._get(game_id)
    assert session.state.players[1].discard_pile == (first_discard,)
    assert session.state.players[2].discard_pile == (second_discard,)


def _covert_operation_game(
    manager: GameSessionManager,
) -> tuple[str, str, str]:
    """Seat 0's open Covert Operation turn at Assembly Hall, its last effect
    pending: the fixture of
    test_a_humans_own_covert_operation_does_not_hold_it_mid_turn, with the
    board's own Intrigue-draw icon resolved BEFORE the personal card effect
    so nothing else is left once the last opponent discards (probe:
    scratchpad/probe2.py, 2026-09-24 session). Returns the game id and the
    two cards the AI opponents will discard."""

    covert_operation = _covert_operation_instance("covert_operation")
    first_discard = _starter_instance("dagger").replace("player:0:", "player:1:")
    second_discard = _covert_operation_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(covert_operation,),
        resources=Resources(solari=10, spice=10, water=10),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            PlayerState(player_id=1, hand=(first_discard,)),
            PlayerState(player_id=2, hand=(second_discard,)),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    manager._get(game_id).state = state
    summary = manager.summary(game_id)
    for wanted in ("agent_turn", "decline_gather_intelligence", "resolve_board_effect"):
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        entry = next(
            a
            for a in actions
            if a["action_id"] == wanted
            and _obj(a["arguments"]).get("space_id", "assembly_hall") == "assembly_hall"
        )
        summary = manager.apply_action(
            game_id, 0, _int(summary["revision"]), _int(entry["index"])
        )
        assert summary["confirmation"] is None
    return game_id, first_discard, second_discard


def test_an_owed_emperor_track_spy_holds_the_turn_end_ready_flag() -> None:
    # The Emperor track's Influence 4 Spy [Main p. 7] waits in the owner's
    # turn and must be placed before it ends (user ruling 2026-10-04,
    # overriding OQ-057 (15)): until then the page is not told that only
    # optional steps are left.
    diplomacy = _starter_instance("diplomacy")
    owner = PlayerState(
        player_id=0,
        hand=(diplomacy,),
        deck=tuple(c for c in starting_deck_instance_ids(0) if c != diplomacy),
        influence=Influence(emperor=3),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    session.state = state

    def take(action_id: str, space_id: str | None = None) -> JsonObject:
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        chosen = next(
            a
            for a in actions
            if a["action_id"] == action_id
            and (space_id is None or _obj(a["arguments"]).get("space_id") == space_id)
        )
        revision = _int(manager.summary(game_id)["revision"])
        return manager.apply_action(game_id, 0, revision, _int(chosen["index"]))

    take("agent_turn", "dutiful_service")
    take("resolve_faction_influence")
    summary = take("resolve_board_effect")
    assert session.state.players[0].influence.emperor == 4
    decision = _obj(summary["decision"])
    assert decision["kind"] == "agent_effects"
    assert decision["turn_end_ready"] is False
    assert agent_turn_end_ready(session.state) is None
    offered = {
        a["action_id"] for a in _rows(manager.legal_actions(game_id, 0)["actions"])
    }
    assert offered == {"place_track_spy"}

    take("place_track_spy")
    summary = take("place_spy_on_space")
    decision = _obj(summary["decision"])
    assert decision["kind"] == "agent_effects"
    assert decision["turn_end_ready"] is True
    assert agent_turn_end_ready(session.state) == 0


def test_a_pending_tech_acquire_effect_holds_the_turn_end_ready_flag() -> None:
    # A Tech tile's acquire effects wait in the turn for the owner's free
    # order (OQ-098) and must be resolved before it ends
    # (``combat_deployment.legal_agent_turn_finish_actions``): bought at an
    # Assembly Hall visit with nothing else left, Glowglobes' Influence
    # keeps the page from being told that only optional steps are left.
    tech = RulesetConfig(bloodlines=True, tech_module=True)
    starters = starting_deck_instance_ids(0)
    owner = PlayerState(
        player_id=0,
        hand=starters[:5],
        deck=starters[5:],
        resources=Resources(spice=6),
    )
    state = GameState(
        config=tech,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:4],
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        tech_stacks=(
            ("glowglobes", "training_depot", "panopticon"),
            ("gene_locked_vault", "delivery_bay", "servo_receivers"),
            ("advanced_data_analysis", "plasteel_blades", "spy_drones"),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    def take(state: GameState, action_id: str, **arguments: object) -> GameState:
        action = next(
            action
            for action in _ENGINE.legal_actions(state, 0)
            if action.action_id == action_id
            and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
        )
        return _ENGINE.apply(state, action).state

    visited = take(
        take(state, "agent_turn", space_id="assembly_hall"), "resolve_board_effect"
    )
    assert agent_turn_end_ready(visited) == 0
    bought = take(visited, "acquire_tech", tech_id="glowglobes")
    assert bought.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert dict(bought.decision_stack[-1].context)[TECH_ACQUIRE_PENDING_KEY]
    assert {action.action_id for action in _ENGINE.legal_actions(bought, 0)} == {
        "resolve_tech_acquire_effect"
    }
    assert agent_turn_end_ready(bought) is None

    resolved = take(bought, "resolve_tech_acquire_effect", faction="emperor")
    assert agent_turn_end_ready(resolved) == 0
    assert DomainAction("finish_agent_turn", 0) in _ENGINE.legal_actions(resolved, 0)


_ENGINE = UprisingRulesEngine()
_SIGNET = "player:0:starter:signet_ring:0"
_GHOLA = "tleilaxu:ghola:0"
_RESOLVING: Final = (
    "decline_gather_intelligence",
    "resolve_agent_card_effect",
    "resolve_board_effect",
    "resolve_faction_influence",
)


def _resolve_what_is_offered(
    hand: tuple[str, ...],
    space_id: str,
    *,
    graft_partner: str | None = None,
    **owner: object,
) -> GameState:
    """Seat 0 sends ``hand[0]`` (grafted to ``graft_partner``) to
    ``space_id`` and resolves every effect the engine offers, both graft
    boxes included, until only what waits is left."""

    imperium = imperium_deck_instance_ids(True)
    state = GameState(
        config=RulesetConfig(choam_module=True, immortality=True, promo_cards=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=(
            _usurp_seat(
                0,
                hand=hand,
                deck=tuple(c for c in _IMMORTALITY_STARTERS if c not in hand),
                resources=Resources(solari=4, spice=2, water=2),
                **owner,
            ),
            *(_usurp_seat(seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    place = next(
        action
        for action in _ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments).get("card_id") == hand[0]
        and dict(action.arguments).get("space_id") == space_id
        and (dict(action.arguments).get("graft") is True) == bool(graft_partner)
        and "cost_option" not in dict(action.arguments)
    )
    state = _ENGINE.apply(state, place).state
    if graft_partner is not None:
        partner = DomainAction(
            action_id="choose_graft_partner",
            actor=0,
            arguments=(("card_id", graft_partner),),
        )
        state = _ENGINE.apply(state, partner).state
    switched = False
    while True:
        legal = _ENGINE.legal_actions(state, 0)
        step = next((a for a in legal if a.action_id in _RESOLVING), None)
        if step is None and not switched:
            step = next((a for a in legal if a.action_id == "switch_graft_card"), None)
            switched = True
        if step is None:
            return state
        if step.action_id != "switch_graft_card":
            switched = False
        state = _ENGINE.apply(state, step).state


@pytest.mark.parametrize(
    ("hand", "space_id", "graft_partner", "owner", "waiting"),
    [
        # FILL COFFERS' spice "If you have an Alliance" [Lady Amber Metulli
        # card], no Alliance held.
        pytest.param(
            (_SIGNET,),
            "arrakeen",
            None,
            {"leader_id": "lady_amber_metulli"},
            {"spice"},
            id="signet_without_alliance",
        ),
        # Industrial Espionage's "If grafted:" line on an ungrafted play.
        pytest.param(
            ("tleilaxu:industrial_espionage:0",),
            "assembly_hall",
            None,
            {},
            {"research"},
            id="industrial_espionage_ungrafted",
        ),
        # Both graft boxes keep only the blocked Alliance spice: Ghola
        # copies the Signet's box [Immortality p. 14].
        pytest.param(
            (_SIGNET, _GHOLA),
            "arrakeen",
            _GHOLA,
            {"leader_id": "lady_amber_metulli"},
            {"spice"},
            id="grafted_signet_and_ghola",
        ),
    ],
)
def test_a_box_keeping_only_blocked_icons_is_ready_to_end(
    hand: tuple[str, ...],
    space_id: str,
    graft_partner: str | None,
    owner: dict[str, object],
    waiting: set[str],
) -> None:
    # The box keeps an icon whose printed condition is false: it is not
    # offered and fizzles at the press (OQ-057 (1)), while finish_agent_turn
    # is already legal. Every icon condition is public, so the page may say
    # the turn is ready to end; before, the pending box held the banner off.
    state = _resolve_what_is_offered(
        hand, space_id, graft_partner=graft_partner, **owner
    )
    context = dict(state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert set(str(context["pending_agent_icons"]).split(",")) == waiting
    if graft_partner is not None:
        assert context["graft_pending_effect"] is True
        assert set(str(context["graft_pending_icons"]).split(",")) == waiting
    offered = {action.action_id for action in _ENGINE.legal_actions(state, 0)}
    assert "finish_agent_turn" in offered
    assert offered.isdisjoint({*_RESOLVING, "switch_graft_card"})

    assert agent_turn_end_ready(state) == 0

    manager = GameSessionManager()
    game_id = str(
        manager.create_game(
            HUMAN_FIRST,
            game_seed=0,
            choam_module=True,
            immortality=True,
            promo_cards=True,
        )["game_id"]
    )
    manager._get(game_id).state = state
    decision = _obj(manager.summary(game_id)["decision"])
    assert decision["turn_end_ready"] is True
    assert decision["prompt"] == AGENT_TURN_END_PROMPT


def test_a_waiting_single_effect_box_still_holds_the_ready_flag() -> None:
    # Interstellar Trade's "choose a Faction" box with every cube at 6 waits
    # for the turn's end (OQ-057 (1), OQ-060) and finish_agent_turn is
    # legal, but a single-effect box's stall is a dry run that can depend
    # on the owner's hand, so the public flag stays off for it.
    card = "imperium:interstellar_trade:0"
    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _resolve_what_is_offered((card,), "assembly_hall", influence=full)
    context = dict(state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert not context.get("pending_agent_icons")
    assert "finish_agent_turn" in {
        action.action_id for action in _ENGINE.legal_actions(state, 0)
    }

    assert agent_turn_end_ready(state) is None


def test_a_humans_own_last_effect_answered_by_ai_seats_keeps_its_turn() -> None:
    # The other half of the same clause: Covert Operation is the human
    # seat's LAST pending effect, and the AI opponents' discards are the
    # last steps of its effects. Before OQ-095 those AI steps closed the
    # human's unit and held the game for it; now an Agent turn ends only
    # through its owner's finish_agent_turn, even with nothing left to
    # resolve, so the decision comes straight back to the human's own open
    # turn, unheld, and its one press hands over -- no confirm_turn.
    manager = GameSessionManager()
    game_id, first_discard, second_discard = _covert_operation_game(manager)
    session = manager._get(game_id)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [a["action_id"] for a in actions] == ["resolve_agent_card_effect"]

    summary = manager.apply_action(
        game_id,
        0,
        _int(manager.summary(game_id)["revision"]),
        _int(actions[0]["index"]),
    )

    # Both AI opponents discarded inside this one call; the decision is back
    # with the human's still-open Agent turn, which only its press ends.
    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["kind"] == "agent_effects"
    assert decision["turn_end_ready"] is True
    assert session.state.players[1].discard_pile == (first_discard,)
    assert session.state.players[2].discard_pile == (second_discard,)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [a["action_id"] for a in actions] == ["finish_agent_turn"]
    assert actions[0]["undoable"] is False

    steps_before = len(session.steps)
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(actions[0]["index"])
    )

    # The press handed over at once: the AI seats played their turns, and
    # the decision is seat 0's next turn, open to it without a second press.
    assert summary["confirmation"] is None
    assert {
        step.actor
        for step in session.steps[steps_before + 1 :]
        if isinstance(step, DomainAction)
    } >= {1, 2, 3}
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0 and decision["kind"] == "turn"
    assert _rows(manager.legal_actions(game_id, 0)["actions"])
    with pytest.raises(SessionError, match="no turn end to confirm"):
        manager.confirm_turn(game_id, 0, _int(summary["revision"]))


def test_the_summary_says_when_only_the_turn_end_and_optional_steps_remain() -> None:
    # OQ-095: once nothing mandatory is left in an Agent turn, the decision
    # carries ``turn_end_ready`` and the prompt asks for the press (its
    # Korean twin is in static/prompts_ko.js); while a mandatory effect is
    # still pending it does not. Public facts only, so it is the same
    # summary for every seat.
    manager = GameSessionManager()
    game_id, _, _ = _covert_operation_game(manager)
    summary = manager.summary(game_id)
    decision = _obj(summary["decision"])
    assert decision["kind"] == "agent_effects" and decision["owner"] == 0
    assert decision["turn_end_ready"] is False
    assert decision["prompt"] == "Choose the next Agent-turn effect to resolve"
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert "finish_agent_turn" not in {a["action_id"] for a in actions}

    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(actions[0]["index"])
    )
    decision = _obj(summary["decision"])
    assert decision["turn_end_ready"] is True
    assert decision["prompt"] == AGENT_TURN_END_PROMPT
    assert f'"{AGENT_TURN_END_PROMPT}": "' in _PROMPTS_KO.read_text(encoding="utf-8")

    # A seat choosing its turn is never "ready to end" it.
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(actions[0]["index"])
    )
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn"
    assert decision["turn_end_ready"] is False
    assert decision["prompt"] != AGENT_TURN_END_PROMPT


def test_a_ready_turn_end_still_offers_the_optional_steps() -> None:
    # Seed 0: seat 0's first Agent turn reaches the point where only the
    # Combat deployment (OQ-029) and the end are left. The deployment stays
    # offered beside finish_agent_turn, after which the end is listed, and
    # the summary already says the turn is ready to end.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary, _ = _play_until_seat0_offers(
        manager, game_id, summary, "finish_agent_turn"
    )
    decision = _obj(summary["decision"])
    assert decision["turn_end_ready"] is True
    assert decision["prompt"] == AGENT_TURN_END_PROMPT
    offered = [
        str(a["action_id"]) for a in _rows(manager.legal_actions(game_id, 0)["actions"])
    ]
    assert set(offered) == {"deploy_troops", "finish_agent_turn"}
    assert offered[-1] == "finish_agent_turn"


# ------------------------------------------------------- hand-over listener


def test_an_explicit_end_into_the_same_seats_next_turn_still_hands_over() -> None:
    # ``apply_action``'s ``passed = ended or _turn_passed(...)`` only ever
    # disagrees with ``_turn_passed`` alone for an explicit end
    # (EXPLICIT_TURN_ENDS) whose very next decision, with nothing else
    # logged, is the SAME seat's own fresh turn again -- every other seat
    # already revealed this round. ``_turn_passed`` alone reads that as
    # "still my turn" and would never announce the hand-over a human
    # server's autosave relies on (``add_hand_over_listener``); ``ended``
    # is exactly what still fires it. Seed 21, three random AI opponents,
    # found by a scratch random walk (rng seed 21 * 9973 + 1): seed 18 of
    # scratchpad/verify_item4.py (2026-09-24 session) no longer reaches it
    # once every Agent turn waits for its finish_agent_turn (OQ-095).
    # Seed 33 reached it until Tactical Option's zero retreat (2026-10-06)
    # added a legal option that moves the random walk; re-searched then,
    # seed 21 was the first of 0-39 whose end is a finish_agent_turn. Seed
    # 21 stopped reaching it at 5654d7f8 (a Combat Intrigue pass right after
    # a card play no longer counts as a consecutive pass, 2026-10-07), which
    # changes the random walk's games; re-searched then, seed 14 was the
    # first of 0-39 (round 8; 16, 20, 23, 28 and 36 reached it too). v146:
    # optional Agent-turn effects offer no refusal (OQ-095 (2), 2026-10-14),
    # which changes the random walk's legal lists; re-searched then, seed 2
    # is the first of 0-59 (27 and 59 reach it too).
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_VS_RANDOM_AI, game_seed=2)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    calls: list[str] = []
    manager.add_hand_over_listener(calls.append)
    rng = random.Random(2 * 9973 + 1)

    found = False
    for _ in range(6000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        choice = rng.choice(actions)
        steps_before = len(session.steps)
        calls_before = len(calls)
        summary = manager.apply_action(
            game_id, owner, _int(summary["revision"]), _int(choice["index"])
        )
        if (
            owner == 0
            and choice["action_id"] == "finish_agent_turn"
            and not summary["finished"]
        ):
            decision = _obj(summary["decision"])
            if (
                decision["owner"] == 0
                and decision["kind"] == "turn"
                and len(session.steps) == steps_before + 1
            ):
                found = True
                assert len(calls) == calls_before + 1, (
                    "the explicit end into the same seat's fresh turn must "
                    "still announce a hand-over"
                )
                break
    assert found, "the same-seat, zero-step hand-over was not reached"


# ------------------------------------------------------------- own turns


def test_a_seat_taking_consecutive_turns_presses_once_between_them() -> None:
    # Seed 16 (re-searched 2026-10-01, of 0-29 the only seed this index-0
    # walk brings there): at some point seat 0 is the only seat left
    # unrevealed this round, so its finish_agent_turn opens its own next
    # turn with no other seat's step in between. That press is the turn's
    # one press (OQ-095): the next turn is open to it at once, never held.
    # (Before OQ-095 the engine closed the turn on its last effect and the
    # server held here, telling this from a Plot Intrigue return by the
    # log; the hold into a seat's own next turn now comes only from units
    # without an explicit end, e.g. test_a_non_last_leader_pick_holds_before_the_
    # own_next_turn.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=16)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    for _ in range(3000):
        assert not summary["finished"], "seat 0 never took consecutive turns"
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        first = _rows(manager.legal_actions(game_id, owner)["actions"])[0]
        steps_before = len(session.steps)
        summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)
        if owner != 0 or first["action_id"] != "finish_agent_turn":
            continue
        if summary["finished"]:
            continue
        decision = _obj(summary["decision"])
        others = [
            step
            for step in session.steps[steps_before:]
            if isinstance(step, DomainAction) and step.actor != 0
        ]
        if decision["owner"] == 0 and decision["kind"] == "turn" and not others:
            break
    else:
        raise AssertionError("seat 0 never took consecutive turns")

    assert summary["confirmation"] is None
    assert _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="no turn end to confirm"):
        manager.confirm_turn(game_id, 0, _int(summary["revision"]))


def test_a_plot_intrigue_at_turn_start_returns_without_a_hold() -> None:
    # Seed 6: seat 0 holds Buy Access (a Plot-timed Intrigue card) and can
    # play it right from the "turn" frame, before choosing an Agent or
    # Reveal turn. Playing it, and resolving its own choice, returns to the
    # very same turn start -- not a fresh turn, so no hold. (Re-searched
    # 2026-10-01: Plots are offered after the Agent-turn effects too since
    # OQ-095, so this index-0 walk plays seed 0's Imperium Politics inside
    # an Agent turn; the walk now looks for the offer at a "turn" frame
    # only, and seed 6 is the first of 0-29 to keep a Plot until then.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=6)
    game_id = str(summary["game_id"])
    summary, index = _play_until_seat0_offers(
        manager, game_id, summary, "play_intrigue", kind="turn"
    )
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn"
    assert decision["owner"] == 0

    before_revision = _int(summary["revision"])
    summary = manager.apply_action(game_id, 0, before_revision, index)
    assert summary["confirmation"] is None

    while _obj(summary["decision"])["kind"] != "turn":
        assert summary["confirmation"] is None
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert _int(summary["revision"]) > before_revision


def test_undoing_back_to_the_turn_start_closes_the_unit() -> None:
    # An open unit belongs to the steps that opened it: take every one of
    # them back and the seat is left with nothing pending, exactly as if
    # its turn had never started (``undo``'s own "a unit whose opening step
    # was taken back is not open any more"). A different Agent turn played
    # afterwards then ends with exactly one press, its finish_agent_turn,
    # and is never held (OQ-095; before it, the turn held exactly once --
    # the held twin is the Leader-pick test below).
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    turn_start_revision = _int(summary["revision"])

    summary = manager.apply_action(game_id, 0, turn_start_revision, 0)
    assert session.open_units.get(0) == 0
    window = next(row for row in _rows(summary["undo"]) if row["seat"] == 0)

    summary = manager.undo(
        game_id, 0, _int(summary["revision"]), _int(window["steps"])
    )

    assert 0 not in session.open_units
    assert _int(summary["revision"]) == turn_start_revision
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn" and decision["owner"] == 0

    # A different board space (index 1, not index 0) played to its natural
    # end: the unit opens again, never holds, and the press closes it.
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 1)
    assert session.open_units.get(0) == 0
    presses = 0
    for _ in range(60):
        assert summary["confirmation"] is None
        first = _rows(manager.legal_actions(game_id, 0)["actions"])[0]
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
        if first["action_id"] == "finish_agent_turn":
            presses += 1
            break
    assert presses == 1
    assert summary["confirmation"] is None
    assert 0 not in session.open_units


def test_undoing_a_leader_pick_closes_its_unit_and_a_new_pick_holds_once() -> None:
    # The held twin of the test above, on a unit that still ends with a
    # hold (OQ-095 left the Leader draft's hold in place): seed 1, seat 0
    # picks before an AI seat (test_a_non_last_leader_pick_holds_before_the_
    # next_picker). Taking the held pick back closes its unit and the hold;
    # a different pick then holds exactly once.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    pick_revision = _int(summary["revision"])

    summary = manager.apply_action(game_id, 0, pick_revision, 0)
    assert summary["confirmation"] == 0
    assert 0 in session.open_units

    summary = manager.undo(game_id, 0, _int(summary["revision"]))
    assert summary["confirmation"] is None
    assert 0 not in session.open_units
    assert _int(summary["revision"]) == pick_revision
    decision = _obj(summary["decision"])
    assert decision["kind"] == "leader_draft" and decision["owner"] == 0

    summary = manager.apply_action(game_id, 0, pick_revision, 1)
    assert summary["confirmation"] == 0
    summary = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert summary["confirmation"] is None
    assert 0 not in session.open_units


# ------------------------------------------- chance outcomes after a unit
#
# "전투 보상으로 받은 스파이 둘 위치를 골랐다가, 혹시 맘에 안 들면 확정 전에
# 다른 곳에 두고 싶을 수 있잖아. 그니까 되돌리기 기회를 줘야하는데, 지금 그
# 기회도 없는데, 턴 종료 버튼은 또 남아버려서 이상해진거네" (user,
# 2026-10-08, the saved game "1007"): the press is the seat's confirmation, so
# a held unit end comes before the chance outcomes that follow the unit, and a
# unit end with nothing left to take back is not held at all. The seeds were
# found by a scratch search under each test's own rng.Random(seed).choice
# policy for seat 0. v146: optional Agent-turn effects offer no refusal
# (OQ-095 (2), 2026-10-14), which moved the reward-Spy seed 19 off its
# shape; re-searched then, seed 20 is the first of 0-59 (23, 26, 35, 43
# and 46 reach it too).


def _walk_to_held_end_before_chance(
    manager: GameSessionManager,
    game_id: str,
    summary: JsonObject,
    seed: int,
    action_id: str,
) -> tuple[JsonObject, dict[str, object], int]:
    """Play seat 0 by ``rng.Random(seed).choice`` until its ``action_id``
    ends its unit with a chance outcome pending; return the summary, that
    choice's row, and the log length before it."""

    session = manager._get(game_id)
    rng = random.Random(seed)
    for _ in range(40_000):
        assert not summary["finished"], f"no held {action_id} before a chance outcome"
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        assert _int(_obj(summary["decision"])["owner"]) == 0
        choice = rng.choice(_rows(manager.legal_actions(game_id, 0)["actions"]))
        logged = len(session.log)
        summary = manager.apply_action(
            game_id, 0, _int(summary["revision"]), _int(choice["index"])
        )
        if (
            choice["action_id"] == action_id
            and summary["confirmation"] == 0
            and isinstance(
                session.engine.current_decision(session.state), ChanceDecision
            )
        ):
            return summary, choice, logged
    raise AssertionError(f"no held {action_id} before a chance outcome")


def _seat0_undo(summary: JsonObject) -> list[dict[str, object]]:
    return [row for row in _rows(summary["undo"]) if row["seat"] == 0]


def test_a_conflict_reward_spy_holds_before_the_next_rounds_reshuffle() -> None:
    # Seed 20, base game: seat 0's Conflict reward Spy is its unit's last
    # step, and the next round opens by reshuffling seat 0's discard pile
    # (the "1007" shape). The press comes before that reshuffle, so the Spy
    # can still be taken back and put on another post.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=20)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    summary, choice, logged = _walk_to_held_end_before_chance(
        manager, game_id, summary, 20, "place_combat_reward_spy"
    )

    # The row told the seat it could take the Spy back, and it can: nothing
    # was logged after the Spy, the reshuffle waits, and no seat owns a
    # decision yet. So the browser sends it at once, not with the press.
    # Its dry run ran on through the round's end, which resets every seat's
    # strength: no strength preview is drawn from it.
    assert choice["undoable"] is True
    assert choice["sent_by_turn_end"] is False
    assert choice["strength_after"] is None
    # Held at the engine's pause before the next round (rules/pauses.py),
    # whose answer asks for the reshuffle.
    assert session.state.decision_stack[-1].kind == FrameKind.PAUSE
    assert len(session.log) == logged + 1
    assert summary["decision"] is None
    assert _seat0_undo(summary) == [{"seat": 0, "steps": 1}]
    assert manager.legal_actions(game_id, 0)["actions"] == []

    summary = manager.undo(game_id, 0, _int(summary["revision"]), 1)
    assert summary["confirmation"] is None
    decision = _obj(summary["decision"])
    assert (decision["kind"], decision["owner"]) == ("combat_reward_spy", 0)
    posts = [
        row
        for row in _rows(manager.legal_actions(game_id, 0)["actions"])
        if row["action_id"] == "place_combat_reward_spy"
        and row["arguments"] != choice["arguments"]
    ]
    assert posts, "seed 20 offers the reward Spy another post"
    assert all(row["strength_after"] is None for row in posts)
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(posts[0]["index"])
    )
    assert summary["confirmation"] == 0
    assert summary["decision"] is None

    # The press resolves the reshuffle and hands the game on.
    pressed_at = len(session.log)
    summary = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert summary["confirmation"] is None
    assert any(
        isinstance(entry, LoggedStep) and isinstance(entry.step, ChanceOutcome)
        for entry in session.log[pressed_at:]
    )
    assert _seat0_undo(summary) == []


def test_a_scouts_line_holds_before_the_next_scouts_card() -> None:
    # Seed 11, Arrakeen Scouts: seat 0 is the last to answer a mission, and
    # the next item of the schedule is drawn right after (the "1007" shape
    # of the second press). The press comes before that draw.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=11, arrakeen_scouts=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    summary, choice, logged = _walk_to_held_end_before_chance(
        manager, game_id, summary, 11, "scouts_join_mission"
    )

    assert choice["undoable"] is True
    assert session.state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW
    assert len(session.log) == logged + 1
    assert _seat0_undo(summary) == [{"seat": 0, "steps": 1}]

    summary = manager.undo(game_id, 0, _int(summary["revision"]), 1)
    decision = _obj(summary["decision"])
    assert (decision["kind"], decision["owner"]) == ("scouts_mission", 0)
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(choice["index"])
    )
    assert summary["confirmation"] == 0
    pressed_at = len(session.log)
    summary = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert summary["confirmation"] is None
    assert any(
        isinstance(entry, LoggedStep) and isinstance(entry.step, ChanceOutcome)
        for entry in session.log[pressed_at:]
    )


def test_a_hold_before_a_chance_outcome_survives_save_and_restore() -> None:
    # The save of a game held before its chance outcome resumes at that
    # hold, and pressing there plays on exactly as the live game does: the
    # reshuffle and every AI answer after it come out the same.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=20)
    game_id = str(summary["game_id"])
    summary, _choice, _logged = _walk_to_held_end_before_chance(
        manager, game_id, summary, 20, "place_combat_reward_spy"
    )

    restored = manager.restore_game(manager.save_game(game_id))
    restored_id = str(restored["game_id"])
    assert restored["confirmation"] == 0
    assert restored["decision"] is None
    assert _seat0_undo(restored) == [{"seat": 0, "steps": 1}]

    live = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    twin = manager.confirm_turn(restored_id, 0, _int(restored["revision"]))
    assert twin["decision"] == live["decision"]
    assert canonical_state_hash(manager._get(restored_id).state) == (
        canonical_state_hash(manager._get(game_id).state)
    )


# ------------------------------------------------- turn_end.py decision stacks


def _frame(kind: FrameKind, owner: int, frame_id: str) -> DecisionFrame:
    return DecisionFrame(
        kind=kind, frame_id=frame_id, decision=PlayerDecision(owner=owner, prompt="x")
    )


def _stack_state(*frames: DecisionFrame) -> GameState:
    return GameState(config=RulesetConfig(), seed=1, decision_stack=frames)


def test_unit_seat_reads_a_holy_war_shaped_stack() -> None:
    # [turn(C), opponent_unit_loss(X), opponent_unit_loss(C)]: C's own turn
    # is still the running unit even though the top of the stack is C's own
    # answer to X's Holy War. Holy War no longer stacks its windows above
    # the next seat's turn (they sit above the card player's open Agent turn
    # since OQ-095), but interrupts are recognised by kind wherever they sit
    # (``INTERRUPT_KINDS``), which this synthetic stack still pins.
    state = _stack_state(
        _frame(FrameKind.TURN, 2, "turn:2"),
        _frame(FrameKind.OPPONENT_UNIT_LOSS, 1, "loss:1"),
        _frame(FrameKind.OPPONENT_UNIT_LOSS, 2, "loss:2"),
    )
    assert unit_seat(state) == 2
    assert answers_another_unit(state, 2) is True
    assert at_turn_start(state, 2) is True


def test_unit_seat_reads_an_agent_effects_stack_with_a_foreign_answer() -> None:
    # [agent_effects(3), opponent_spy_move(0)]: seat 0 moves its Spy for
    # seat 3's False Orders inside seat 3's still-running Agent turn. (This
    # used Distraction's face-up trigger frame until codec v129, OQ-016.)
    state = _stack_state(
        _frame(FrameKind.AGENT_EFFECTS, 3, "agent_effects:3"),
        _frame(FrameKind.OPPONENT_SPY_MOVE, 0, "spy_move:0"),
    )
    assert unit_seat(state) == 3
    assert answers_another_unit(state, 0) is True


def test_unit_seat_reads_a_trailing_leftover_above_a_fresh_turn_start() -> None:
    # [turn(1), contract_market(0)]: seat 1's turn has started but a
    # leftover Contract pick from seat 0's previous turn is offered first.
    state = _stack_state(
        _frame(FrameKind.TURN, 1, "turn:1"),
        _frame(FrameKind.CONTRACT_MARKET, 0, "market:0"),
    )
    assert unit_seat(state) == 0
    assert at_turn_start(state, 0) is False
    assert at_turn_start(state, 1) is True


def test_turn_start_seat_reads_a_plain_turn_frame() -> None:
    state = _stack_state(_frame(FrameKind.TURN, 2, "turn:2"))
    assert turn_start_seat(state) == 2


def test_finishing_seat_reads_a_pressed_end_below_its_follow_up() -> None:
    # [agent_effects(2, finishing), skill_choice(2)]: seat 2 pressed its
    # end and the Usurp trash left a Skill choice above the waiting frame
    # (OQ-095 (4)); the whole stack is read, not only its top. Nothing is
    # "ready to end" while the follow-up is pending.
    waiting = DecisionFrame(
        kind=FrameKind.AGENT_EFFECTS,
        frame_id="agent_effects:2",
        decision=PlayerDecision(owner=2, prompt="x"),
        context=((FINISHING_KEY, True),),
    )
    follow_up = _frame(FrameKind.SKILL_CHOICE, 2, "skill:2")
    assert finishing_seat(_stack_state(waiting, follow_up)) == 2
    assert agent_turn_end_ready(_stack_state(waiting, follow_up)) is None
    assert agent_turn_end_ready(_stack_state(waiting)) is None
    unpressed = _frame(FrameKind.AGENT_EFFECTS, 2, "agent_effects:2")
    assert finishing_seat(_stack_state(unpressed, follow_up)) is None


def _chance_frame(kind: FrameKind, frame_id: str) -> DecisionFrame:
    return DecisionFrame(
        kind=kind,
        frame_id=frame_id,
        decision=ChanceDecision(decision_id=frame_id, prompt="x", options=("a",)),
    )


def test_unit_over_reads_only_the_stack_below_a_chance_outcome() -> None:
    # A reshuffle in the middle of seat 0's Agent turn belongs to the turn,
    # whose frame waits below it; the next round's reshuffle, or the next
    # Arrakeen Scouts card, comes after every unit and waits for the press.
    reshuffle = _chance_frame(FrameKind.PERSONAL_DRAW_RESHUFFLE, "draw:0")
    turn = _frame(FrameKind.AGENT_EFFECTS, 0, "agent_effects:0")
    mid_turn = _stack_state(turn, reshuffle)
    assert unit_over(mid_turn, 0) is False
    next_round = _stack_state(_chance_frame(FrameKind.ROUND_START_RESHUFFLE, "round:0"))
    assert unit_over(next_round, 0) is True
    scouts = _stack_state(_chance_frame(FrameKind.SCOUTS_DRAW, "scouts:draw"))
    assert unit_over(scouts, 2) is True


def test_unit_over_reads_a_player_decision_as_before() -> None:
    # Another seat's decision, or the seat's own next turn, ends the unit;
    # its own further decision does not; nothing pending is no end.
    assert unit_over(_stack_state(_frame(FrameKind.TURN, 1, "turn:1")), 0) is True
    assert unit_over(_stack_state(_frame(FrameKind.TURN, 0, "turn:0")), 0) is True
    reward = _frame(FrameKind.COMBAT_REWARD_SPY, 0, "reward:0")
    assert unit_over(_stack_state(reward), 0) is False
    assert unit_over(_stack_state(), 0) is False


# ------------------------------------------------------------------- saves


def test_the_last_leader_pick_survives_save_restore_and_undo() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["confirmation"] is None
    assert restored["phase"] == "setup"
    assert restored["undo"] == [{"seat": 0, "steps": 1}]
    assert restored["revision"] == summary["revision"]
    assert manager.view(restored_id, 0) == manager.view(game_id, 0)
    restored = manager.undo(restored_id, 0, _int(restored["revision"]))
    assert all(
        action["action_id"] == "pick_leader"
        for action in _rows(manager.legal_actions(restored_id, 0)["actions"])
    )
    restored = manager.apply_action(restored_id, 0, _int(restored["revision"]), 1)
    restored = manager.apply_action(restored_id, 0, _int(restored["revision"]), 0)
    assert restored["phase"] == "player_turns"
    assert restored["undo"] == []
    assert (
        manager.restore_game(manager.save_game(restored_id))["phase"] == "player_turns"
    )


def test_a_confirmed_hand_over_to_a_human_stays_unheld_after_restore() -> None:
    # Seed 0, two human seats, Leader draft: confirming a hold that hands
    # straight to the other human (nothing else gets logged in between) used
    # to re-hold on restore, since the log alone could not tell the window
    # was sealed. The found hand-over must itself still carry an open undo
    # window right before the press, or this would not exercise the sealing
    # at all: an already-empty window (closed by the log alone) looks the
    # same whether or not ``sealed_steps`` is restored correctly (m3:
    # restoring ``session.undo_floor = 0`` instead of the saved value).
    # (Moved 2026-10-01 from seed 7's held Agent turns, which OQ-095 ends
    # with finish_agent_turn instead: seat 1 picks right before seat 0
    # (draft_pick_order, OQ-007), and a pick that is not the last one can
    # still be taken back.)
    manager = GameSessionManager()
    seats = ("human", "human", *HUMAN_FIRST[1:3])
    summary = manager.create_game(seats, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])

    found = False
    held_seat = -1
    for _ in range(400):
        held = summary["confirmation"]
        if not isinstance(held, int):
            owner = _int(_obj(summary["decision"])["owner"])
            summary = manager.apply_action(game_id, owner, _int(summary["revision"]), 0)
            continue
        revision = _int(summary["revision"])
        before = [row for row in _rows(summary["undo"]) if row["seat"] == held]
        summary = manager.confirm_turn(game_id, held, revision)
        if not before:
            # The log alone already closed the window; this confirmation
            # would pass even under a broken restore (m3), so it does not
            # count as the scenario this test needs.
            continue
        successor = _int(_obj(summary["decision"])["owner"])
        if seats[successor] == "human" and _int(summary["revision"]) == revision:
            found = True
            held_seat = held
            break
    assert found, (
        "no direct human-to-human hand-over with an open undo window was reached"
    )
    assert summary["confirmation"] is None

    document = manager.save_game(game_id)
    assert document["confirmation"] is None
    restored = manager.restore_game(document)
    assert restored["confirmation"] is None
    held_seat_undo = [
        row for row in _rows(restored["undo"]) if row["seat"] == held_seat
    ]
    assert held_seat_undo == []


def test_a_document_without_the_new_fields_restores_by_the_old_rule() -> None:
    # A known hold under both the old rule and the new one: seed 1 with the
    # Leader draft, seat 0's pick (not the last, so still undoable) ends its
    # unit while the next pick belongs to another seat. Stripping the new
    # fields and restoring must still reproduce it. (Moved 2026-10-01 from
    # seed 14's held Agent turn, which OQ-095 ends with finish_agent_turn.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = str(summary["game_id"])
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    assert summary["confirmation"] == 0
    assert summary["undo"] != []
    assert _obj(summary["decision"])["owner"] != 0

    document = manager.save_game(game_id)
    legacy = {
        key: value
        for key, value in document.items()
        if key not in ("confirmation", "sealed_steps")
    }
    restored = manager.restore_game(legacy)
    assert restored["confirmation"] == 0
    assert restored["revision"] == summary["revision"]


def test_a_legacy_document_saved_mid_turn_restores_with_an_open_unit() -> None:
    # A save written before the turn-end state was recorded (no
    # "confirmation"/"sealed_steps"/"open_units" at all) taken well before
    # any hold, mid-unit: the old rule's own live-log scan
    # (``_restore_legacy_hand_over_locked``) has to reopen the seat's unit
    # itself, or the unit's eventual end would never hold at all. It must
    # hold exactly once, not zero times and not twice. (Moved 2026-10-01
    # from the middle of seed 0's first Agent turn, which OQ-095 ends with
    # finish_agent_turn and never holds, to the middle of seat 0's Conflict
    # rewards: seed 15's index-0 walk, two Influence picks of one reward.
    # Seed 15 stopped reaching it at 5654d7f8, a Combat Intrigue pass right
    # after a card play no longer counting as a consecutive pass, 2026-10-07;
    # seed 58 was the first of 0-199 whose walk has seat 0 between the two
    # picks of Propaganda's reward, round 8. Since 2026-10-08 a unit end
    # with nothing left to take back is not held, and seed 58's reward ends
    # in the Spy of an Alliance whose placement runs straight into the Round
    # Start draw; seed 36 is the first of 0-59 whose walk has seat 0 inside
    # its Conflict rewards (an optional reward, round 2) with an end that
    # still holds.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=36)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    summary = _play_until(
        manager,
        game_id,
        summary,
        lambda s: (
            s["confirmation"] is None
            and _obj(s["decision"])["kind"] == "combat_reward_optional"
            and _obj(s["decision"])["owner"] == 0
            and 0 in session.open_units
        ),
    )

    document = manager.save_game(game_id)
    legacy = {
        key: value
        for key, value in document.items()
        if key not in ("confirmation", "sealed_steps", "open_units")
    }
    restored = manager.restore_game(legacy)
    restored_id = str(restored["game_id"])
    rsession = manager._get(restored_id)
    assert restored["confirmation"] is None
    assert rsession.open_units.get(0) == 0

    holds = 0
    for _ in range(200):
        if restored["finished"]:
            break
        held: object = restored["confirmation"]
        if isinstance(held, int):
            holds += 1
            assert held == 0
            restored = manager.confirm_turn(restored_id, 0, _int(restored["revision"]))
            assert restored["confirmation"] is None
            break
        owner = _int(_obj(restored["decision"])["owner"])
        restored = manager.apply_action(
            restored_id, owner, _int(restored["revision"]), 0
        )
    assert holds == 1


def test_a_control_defense_restore_gives_the_same_confirmation_as_live() -> None:
    # Base game: seat 0 eventually faces its own Control-defense decision
    # (it controls a critical location with troops in supply). Save+restore
    # right there and take the same choice in both sessions: both must hold
    # for seat 0. Found the way scratchpad/restore_control_defense.py found
    # its own seed -- an rng.Random(seed).choice policy that reaches a
    # seat-0 control_defense decision -- but at seed 0, round 7: that
    # reviewer script used the bare "heuristic" agent, which is retuned as
    # the baseline improves (see HUMAN_FIRST's own comment above), so its
    # seed 10 does not reproduce against this suite's pinned
    # "heuristic_uprising_table" table. Re-searched 2026-09-26 with this same
    # rng.Random(seed).choice policy: the s1-card-data icon fixes (Maker
    # Keeper, Calculus of Power, Chani, Undercover Asset [card faces]) moved
    # this path enough that the old seed 0 no longer reaches a seat-0
    # control_defense decision; seed 13 does. Re-searched again 2026-10-01:
    # every Agent turn now waits for its owner's finish_agent_turn
    # (OQ-095), which moved seed 13 off it and seed 0 back on (round 7; 7,
    # 12, 22 and 23 of 0-39 reached it too). Re-searched 2026-10-14 -- v146:
    # optional Agent-turn effects offer no refusal (OQ-095 (2), 2026-10-14),
    # which moved seed 0 off it; seed 2 is the first of 0-59 (20, 26, 35,
    # 43 and 46 reach it too). Since the engine pauses before the Round
    # Start draw (rules/pauses.py, codec v140) the answer is held there for
    # the defender's press, as every unit end with something left to take
    # back. Live and restored sessions must agree.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=2)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(2)

    found = False
    choice: dict[str, object] = {}
    for _ in range(40_000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        choice = rng.choice(actions)
        top = session.state.decision_stack[-1] if session.state.decision_stack else None
        if top is not None and str(top.kind) == "control_defense" and owner == 0:
            found = True
            break
        summary = manager.apply_action(
            game_id, owner, _int(summary["revision"]), _int(choice["index"])
        )
    assert found, "no seat-0 control_defense decision was reached"

    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["decision"] == summary["decision"]

    live = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(choice["index"])
    )
    twin = manager.apply_action(
        restored_id, 0, _int(restored["revision"]), _int(choice["index"])
    )
    assert live["confirmation"] == 0
    assert twin["confirmation"] == 0
    assert twin["decision"] == live["decision"]
    assert live["undo"] == twin["undo"]
    assert 0 in session.open_units
    assert 0 in manager._get(restored_id).open_units


def test_bad_hand_over_fields_are_rejected_on_restore() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    document = manager.save_game(game_id)

    with pytest.raises(SaveError, match="sealed_steps"):
        manager.restore_game({**document, "sealed_steps": -1})
    with pytest.raises(SaveError, match="sealed_steps"):
        manager.restore_game({**document, "sealed_steps": "3"})
    with pytest.raises(SaveError, match="confirmation"):
        manager.restore_game({**document, "confirmation": "x"})
    # "confirmation" present without "sealed_steps" at all (not merely a bad
    # value) must still be rejected, not read as a legacy document.
    without_sealed_steps = {
        key: value for key, value in document.items() if key != "sealed_steps"
    }
    assert "confirmation" in without_sealed_steps
    with pytest.raises(SaveError, match="sealed_steps"):
        manager.restore_game(without_sealed_steps)


def test_open_units_fields_are_rejected_on_restore() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    document = manager.save_game(game_id)
    step_count = len(_rows(document["steps"]))
    assert step_count > 0

    with pytest.raises(SaveError, match="open_units"):
        manager.restore_game({**document, "open_units": "not-a-list"})
    with pytest.raises(SaveError, match="open_units"):
        manager.restore_game({**document, "open_units": [[0]]})
    with pytest.raises(SaveError, match="open_units"):
        manager.restore_game({**document, "open_units": [[0, 1, 2]]})
    # Seat 1 is an AI seat in HUMAN_FIRST: it can never hold an open unit.
    with pytest.raises(SaveError, match="seat 1"):
        manager.restore_game({**document, "open_units": [[1, 0]]})
    # A step index past every recorded step cannot have opened anything.
    with pytest.raises(SaveError, match="seat 0"):
        manager.restore_game({**document, "open_units": [[0, step_count]]})


# -------------------------------------------------------------------- remote


def test_a_remote_hold_blocks_the_next_human_seat() -> None:
    # Seed 3, two claimed human seats: a hold whose next decision is the
    # other human's, checked for the REMOTE-only block on that seat's own
    # client (open servers let it act regardless, unchanged: test_access.py::
    # test_an_open_server_still_lets_the_next_seat_act_without_the_confirmation).
    # Until 2026-10-08 this was an empty-undo-window hold (seat 1's Conflict
    # reward Spy, whose end ran into the next round's chance outcomes); a
    # hold now always leaves its seat something to take back, before any
    # chance outcome after the unit (``_hold_unit_end_locked``), and seed 3
    # has no hold left whose next decision is seat 0's. The Leader draft has
    # one: seat 1's pick holds before seat 0 picks.
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="key")
    admin = Credentials(admin_key="key")
    summary = manager.create_game(
        TWO_HUMANS, game_seed=3, leader_draft=True, credentials=admin
    )
    game_id = str(summary["game_id"])
    creds = {
        seat: Credentials(
            seat_tokens=frozenset({manager.claim_seat(game_id, seat, f"P{seat}").token})
        )
        for seat in (0, 1)
    }

    held = None
    owner = None
    for _ in range(2000):
        assert not summary["finished"], "no hold blocking the other human seat"
        held = summary["confirmation"]
        decision = summary["decision"]
        if isinstance(held, int):
            if decision is not None:
                owner = _int(_obj(decision)["owner"])
                if owner != held and owner in creds:
                    undo_rows = [
                        row for row in _rows(summary["undo"]) if row["seat"] == held
                    ]
                    assert undo_rows, "a hold leaves its seat a step to take back"
                    break
            summary = manager.confirm_turn(
                game_id, held, _int(summary["revision"]), credentials=creds[held]
            )
        else:
            owner = _int(_obj(decision)["owner"])
            summary = manager.apply_action(
                game_id, owner, _int(summary["revision"]), 0, credentials=creds[owner]
            )
    else:
        raise AssertionError("no hold blocking the other human seat was reached")

    assert held is not None and owner is not None
    blocked = manager.snapshot(game_id, owner, credentials=creds[owner])
    assert blocked["actions"] is None
    with pytest.raises(SessionError, match="has not confirmed"):
        manager.apply_action(
            game_id, owner, _int(summary["revision"]), 0, credentials=creds[owner]
        )

    confirmed = manager.confirm_turn(
        game_id, held, _int(summary["revision"]), credentials=creds[held]
    )
    assert confirmed["confirmation"] is None
    released = manager.snapshot(game_id, owner, credentials=creds[owner])
    assert released["actions"] is not None


# -------------------------------------------------------------- property sweep


@dataclass(frozen=True)
class _SweepConfig:
    seats: tuple[str, ...]
    game_seeds: tuple[int, ...]
    options: tuple[str, ...] = ()


# The rulesets the OQ-095 acceptance invariants are pinned on
# (docs/explicit-turn-end-plan.md section 5, S4): the base game, the Leader
# draft (whose picks still hold), Bloodlines with the Tech module,
# Immortality, Arrakeen Scouts, and every option at once with two humans.
_SWEEP_CONFIGS = (
    _SweepConfig(HUMAN_FIRST, (0, 1)),
    _SweepConfig(HUMAN_FIRST, (0, 1), ("leader_draft",)),
    _SweepConfig(HUMAN_FIRST, (0,), ("bloodlines", "tech_module")),
    _SweepConfig(HUMAN_FIRST, (0,), ("immortality",)),
    _SweepConfig(HUMAN_FIRST, (0,), ("arrakeen_scouts",)),
    _SweepConfig(
        TWO_HUMANS,
        (0,),
        (
            "leader_draft",
            "choam_module",
            "bloodlines",
            "tech_module",
            "immortality",
            "arrakeen_scouts",
        ),
    ),
)


@dataclass
class _SweepTally:
    violations: list[str]
    holds: int = 0
    agent_turn_presses: int = 0
    server_declines: int = 0


def _agent_turn_owners(state: GameState) -> set[int]:
    """The seats whose Agent-turn effect frame is on the stack."""

    return {
        frame.decision.owner
        for frame in state.decision_stack
        if frame.kind == FrameKind.AGENT_EFFECTS
        and isinstance(frame.decision, PlayerDecision)
    }


def _agent_turn_violations(session: GameSession) -> list[str]:
    """Replay the game; list every Agent turn not ended by its own press.

    The OQ-095 census (docs/explicit-turn-end-plan.md section 6), for every
    seat, human or AI: an Agent turn's frame leaves the stack only through
    its owner's finish_agent_turn, or a step answering that press's own
    follow-up (a Usurp trash's Skill choice or reshuffle,
    ``finishing_seat``); and once an Agent goes out, every other seat's step
    until that seat's finish_agent_turn answers inside its still-open turn.
    """

    engine = session.engine
    state = engine.reset(session.config, session.game_seed)
    awaiting: set[int] = set()
    violations: list[str] = []
    for index, step in enumerate(session.steps):
        result = engine.apply(state, step)
        action = step if isinstance(step, DomainAction) else None
        before = _agent_turn_owners(state)
        after = _agent_turn_owners(result.state)
        for seat in sorted(before - after):
            pressed = (
                action is not None
                and action.actor == seat
                and action.action_id == "finish_agent_turn"
            )
            if not pressed and finishing_seat(state) != seat:
                violations.append(
                    f"step {index} ({step}) closed seat {seat}'s Agent turn"
                )
        if action is not None:
            for seat in sorted(awaiting - before - {action.actor}):
                violations.append(
                    f"step {index}: seat {action.actor} acted before seat "
                    f"{seat}'s finish_agent_turn"
                )
        for event in result.events:
            if event.kind == "agent_placed":
                seat = _int(dict(event.payload)["player"])
                awaiting.add(seat)
                if seat not in after:
                    violations.append(
                        f"step {index}: seat {seat}'s Agent went out with no turn"
                    )
        if action is not None and action.action_id == "finish_agent_turn":
            awaiting.discard(action.actor)
        state = result.state
    assert state == session.state, "the replay must reproduce the live game"
    return violations


def _run_property_sweep_game(
    manager: GameSessionManager, config: _SweepConfig, game_seed: int
) -> _SweepTally:
    """Play one game, the human seats at random; tally every violation.

    The OQ-095 acceptance invariants (docs/explicit-turn-end-plan.md
    section 5, S4) and the one-press rule's own:

    - a human seat takes at most one turn between two presses;
    - no hold follows a unit in which the seat sent an Agent
      (``agent_placed``): an Agent turn ends only through its own
      finish_agent_turn;
    - an explicit end, a turn-passing card and a step answering a pressed
      end's follow-up never leave their seat held or with an undo window (no
      second press), and a hold needs a step of the seat's own unit since
      its last press;
    - every human decision has at least one legal action;
    - a hold always leaves its seat a step to take back, and exactly the
      steps outside the turns that cannot be taken back are sent with the
      browser's "확정 ▶" instead (``sent_by_turn_end``; user, 2026-10-08);
    - a unit outside the turns never closes unconfirmed: by a hold, or by
      a step sent with "확정 ▶";
    - a Conflict-end decline the server takes for a human seat (a lone
      human's decline-only window, OQ-103) is sealed like a press, holds
      nothing, and never happens with two human seats;
    - the replayed game passes ``_agent_turn_violations``.
    """

    options = set(config.options)
    summary = manager.create_game(
        config.seats,
        game_seed=game_seed,
        leader_draft="leader_draft" in options,
        choam_module="choam_module" in options,
        bloodlines="bloodlines" in options,
        tech_module="tech_module" in options,
        immortality="immortality" in options,
        arrakeen_scouts="arrakeen_scouts" in options,
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(game_seed * 7 + 1)
    humans = [seat for seat, kind in enumerate(config.seats) if kind == "human"]
    since_press = dict.fromkeys(humans, 0)
    sent_agent = dict.fromkeys(humans, False)
    # A hold for seat S requires a non-answer step of S since S's last
    # press (a step whose pre-step state has
    # ``not answers_another_unit(state, S)``): that is exactly what opens
    # ``session.open_units[S]`` in the first place, so nothing else could
    # ever make S's unit "over" for ``_unit_ended_locked`` to hold on.
    has_unit_step = dict.fromkeys(humans, False)
    tally = _SweepTally(violations=[])
    logged = len(live_steps(session.log))
    # The steps the walker's own requests sent; any other human step is the
    # server's Conflict-end decline (``_auto_decline_locked``).
    sent: set[int] = set()
    checked = 0

    def check_server_declines() -> None:
        nonlocal checked
        for index in range(checked, len(session.steps)):
            step = session.steps[index]
            if index in sent or not isinstance(step, DomainAction):
                continue
            if step.actor not in humans:
                continue
            if step.action_id != "decline_conflict_end_intrigue":
                tally.violations.append(f"step {index} ({step}) was sent by nobody")
                continue
            tally.server_declines += 1
            if len(humans) != 1:
                tally.violations.append(
                    f"the server declined for seat {step.actor} beside another human"
                )
            if session.undo_floor <= index:
                tally.violations.append(f"the server's decline at {index} is unsealed")
            if summary["confirmation"] == step.actor:
                tally.violations.append(f"the server's decline at {index} holds")
        checked = len(session.steps)

    def scan() -> set[int]:
        """Count the turns in the newly logged steps; return who pressed."""

        nonlocal logged
        live = live_steps(session.log)
        pressed: set[int] = set()
        for entry in live[logged:]:
            actor = entry.actor
            step_id = getattr(entry.step, "action_id", None)
            if step_id in ("reveal_turn", "pick_leader") and actor in humans:
                since_press[actor] += 1
            for event in entry.events:
                player = dict(event.payload).get("player")
                if event.kind in TURN_TAKING_EVENTS and player in humans:
                    assert isinstance(player, int)
                    since_press[player] += 1
                    if event.kind == "agent_placed":
                        sent_agent[player] = True
            for seat in humans:
                if since_press[seat] > 1:
                    tally.violations.append(
                        f"seat {seat} took two turns without a press ({step_id})"
                    )
                    since_press[seat] = 1
            if actor in humans and (
                step_id in EXPLICIT_TURN_ENDS
                or any(
                    event.kind in TURN_PASS_EVENTS
                    and dict(event.payload).get("player") == actor
                    for event in entry.events
                )
            ):
                assert actor is not None
                pressed.add(actor)
                since_press[actor] = 0
                sent_agent[actor] = False
        logged = len(live)
        return pressed

    for _ in range(6000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            tally.holds += 1
            if manager.legal_actions(game_id, held)["actions"] != []:
                tally.violations.append(f"held seat {held} was offered actions")
            if not has_unit_step[held]:
                tally.violations.append(
                    f"seat {held} held without a step of its own since its press"
                )
            if sent_agent[held]:
                tally.violations.append(f"seat {held} held after an Agent turn")
            # The press is a confirmation: a hold always leaves its seat a
            # step to take back, so no chance outcome or other seat's step
            # came after it (user, 2026-10-08).
            if not [row for row in _rows(summary["undo"]) if row["seat"] == held]:
                tally.violations.append(f"seat {held} held with nothing to take back")
            summary = manager.confirm_turn(
                game_id,
                held,
                _int(summary["revision"]),
                undo_count=_int(summary["undo_count"]),
            )
            since_press[held] = 0
            sent_agent[held] = False
            has_unit_step[held] = False
            scan()
            check_server_declines()
            continue
        decision = _obj(summary["decision"])
        owner = _int(decision["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        if not actions:
            tally.violations.append(f"seat {owner}'s {decision['kind']} has no action")
            break
        # Only a step outside the turns that cannot be taken back waits in
        # the browser for the press (user, 2026-10-08).
        outside = own_unit_outside_turns(session.state, owner)
        for row in actions:
            if row["sent_by_turn_end"] and (
                row["undoable"] or row["action_id"] in EXPLICIT_TURN_ENDS or not outside
            ):
                tally.violations.append(
                    f"seat {owner}'s {row['action_id']} waits for a press it need not"
                )
            if outside and not row["undoable"] and row["action_id"] not in (
                EXPLICIT_TURN_ENDS
            ) and not row["sent_by_turn_end"]:
                tally.violations.append(
                    f"seat {owner}'s {row['action_id']} is sent unconfirmed"
                )
        choice = rng.choice(actions)
        before = session.state
        finishing = finishing_seat(before) == owner
        sent.add(len(session.steps))
        summary = manager.apply_action(
            game_id,
            owner,
            _int(summary["revision"]),
            _int(choice["index"]),
            undo_count=_int(summary["undo_count"]),
        )
        if choice["action_id"] == "finish_agent_turn":
            tally.agent_turn_presses += 1
        check_server_declines()
        if owner in scan() or finishing:
            if summary["confirmation"] == owner:
                tally.violations.append(
                    f"seat {owner} must press again after {choice['action_id']}"
                )
            if [row for row in _rows(summary["undo"]) if row["seat"] == owner]:
                tally.violations.append(
                    f"seat {owner}'s {choice['action_id']} left an undo window"
                )
            has_unit_step[owner] = False
        elif not answers_another_unit(before, owner):
            has_unit_step[owner] = True
        # A unit outside the turns never closes unconfirmed: its end is a
        # hold (the press, with a step to take back), or its last step went
        # out with the browser's "확정 ▶" (sent_by_turn_end; user, 2026-10-08).
        if (
            own_unit_outside_turns(before, owner)
            and owner not in session.open_units
            and summary["confirmation"] != owner
            and choice["action_id"] not in EXPLICIT_TURN_ENDS
            and not choice["sent_by_turn_end"]
        ):
            tally.violations.append(
                f"seat {owner}'s unit closed unconfirmed after {choice['action_id']}"
            )
    else:
        raise AssertionError(f"seed {game_seed} did not finish within the step budget")
    tally.violations.extend(_agent_turn_violations(session))
    return tally


@pytest.mark.parametrize(
    "config",
    _SWEEP_CONFIGS,
    ids=lambda config: "+".join(config.options) or "base",
)
def test_property_sweep_a_human_seat_is_always_pressed_between_turns(
    config: _SweepConfig,
) -> None:
    manager = GameSessionManager()
    tallies = [
        _run_property_sweep_game(manager, config, seed) for seed in config.game_seeds
    ]
    violations = [
        f"seed {seed}: {violation}"
        for seed, tally in zip(config.game_seeds, tallies, strict=True)
        for violation in tally.violations
    ]
    assert violations == []
    # The sweep must have exercised the explicit Agent-turn end, and with
    # the Leader draft the holds OQ-095 keeps (its picks) as well.
    assert sum(tally.agent_turn_presses for tally in tallies) > 0
    if "leader_draft" in config.options:
        assert sum(tally.holds for tally in tallies) > 0


def test_every_copy_of_the_explicit_turn_end_ids_matches_the_server() -> None:
    """The client draws an explicit turn-end action as the banner's one
    turn-end row (``render.js`` ``EXPLICIT_TURN_END_IDS``), and two e2e
    scripts mirror the set to find such decisions. A copy that misses an id
    renders that end as a plain action -- the e2e copies lacked
    ``confirm_scouts_bid`` until 2026-10-01 -- so every copy must equal
    ``EXPLICIT_TURN_ENDS``."""

    import re

    root = Path(sessions_module.__file__).resolve().parents[3]
    copies = {
        "render.js": root / "src/dune_imperium/server/static/render.js",
        "turn_end.py": root / "scripts/e2e/turn_end.py",
        "remote_fresh.py": root / "scripts/e2e/remote_fresh.py",
    }
    for name, path in copies.items():
        source = path.read_text(encoding="utf-8")
        match = re.search(
            r"EXPLICIT_TURN_END_IDS\s*=\s*(?:new Set\(\[|\{)(.*?)(?:\]\)|\})",
            source,
            re.S,
        )
        assert match, name
        ids = set(re.findall(r'"([a-z_]+)"', match.group(1)))
        assert ids == set(EXPLICIT_TURN_ENDS), name


# --- the pauses tell no seat anything (rules/pauses.py) ---------------------


def _reward_marks(manager: GameSessionManager, game_id: str, seat: int) -> list[object]:
    return [
        (row["undoable"], row["sent_by_turn_end"], row["strength_after"])
        for row in _rows(manager.legal_actions(game_id, seat)["actions"])
    ]


def test_a_reward_rows_marks_do_not_depend_on_another_seats_hidden_hand() -> None:
    # Seed 79, Immortality, seats 0 and 1 human: seat 0 chooses its optional
    # Conflict reward while another seat has enough troops in the Conflict
    # for Harvest Cells. Before the engine's pauses, whether seat 0's rows
    # were marked "can't be taken back, send with 확정 ▶" depended on
    # whether that seat secretly held a playable Harvest Cells: with one,
    # the dry run stopped at its Conflict-end window, which then opened only
    # for a seat that could play one; without, it ran on into the next
    # round's reveal. The pauses (after the rewards, before the next round)
    # stand whatever the seats hold, and since 2026-10-09 the window opens
    # on public facts too (OQ-103), so the marks, previews included, are the
    # same whether the seat's first Intrigue card is a Harvest Cells or the
    # card it really holds (the same count either way); also when this is
    # the last round (a seat at the endgame score), which has no Round Start
    # and ran on into the Endgame Intrigue windows (2026-10-08 review).
    # Seed 79 since 2026-10-10: Cunning's draw after its trash became its own
    # step (OQ-106), so seed 70's walk no longer meets such a reward choice
    # (it does on the previous commit's engine); 79 is the first seed after
    # it whose walk does (round 9, seat 0's reward beside seat 3). Seed 81
    # since a triggered Intrigue draw waits as the owner's own step (OQ-106):
    # 79's walk no longer meets one (it does on the previous commit's
    # engine); 81 is the first seed after it whose walk does (round 9, seat
    # 1's reward beside seat 2). Seed 87 since both grafted Agent boxes are
    # offered from the start (codec v143, docs/graft-boxes-plan.md): 81's
    # walk meets a grafted Agent turn (walk step 235, no switch row any
    # more) before its case (step 363 on the previous commit's engine) and
    # no longer meets one; 87 is the first seed after it whose walk does.
    manager = GameSessionManager()
    summary = manager.create_game(
        ("human", "human", "heuristic_uprising_table", "heuristic_uprising_table"),
        game_seed=87,
        immortality=True,
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(87)
    compared = 0
    for _ in range(9000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(
                game_id, held, _int(summary["revision"]), undo_count=_int(
                    summary["undo_count"]
                )
            )
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        live = session.state
        top = live.decision_stack[-1]
        harvest = [card for card in live.intrigue_deck if "harvest" in card]
        fighters = [
            player.player_id
            for player in live.players
            if player.player_id != owner
            and player.troops_conflict >= 3
            and player.intrigue_cards
            and not any("harvest" in card for card in player.intrigue_cards)
        ]
        if str(top.kind).startswith("combat_reward") and harvest and fighters:
            seat = fighters[0]
            card = live.players[seat].intrigue_cards[0]
            fake = _holding(live, seat, harvest[0], (*live.intrigue_deck, card))
            leader = max(
                (p for p in live.players if p.player_id != owner),
                key=lambda p: p.victory_points,
            )
            ending = list(live.players)
            ending[leader.player_id] = replace(leader, victory_points=10)
            last = replace(live, players=tuple(ending))
            ending_fake = list(fake.players)
            ending_fake[leader.player_id] = replace(
                fake.players[leader.player_id], victory_points=10
            )
            last_fake = replace(fake, players=tuple(ending_fake))
            marks = []
            for world in (live, fake, last, last_fake):
                session.state = world
                try:
                    marks.append(_reward_marks(manager, game_id, owner))
                finally:
                    session.state = live
            assert marks[0] == marks[1], (live.round_number, owner, seat)
            assert marks[2] == marks[3], ("last round", live.round_number, owner, seat)
            compared += 1
        rows = _rows(manager.legal_actions(game_id, owner)["actions"])
        summary = manager.apply_action(
            game_id,
            owner,
            _int(summary["revision"]),
            _int(rng.choice(rows)["index"]),
            undo_count=_int(summary["undo_count"]),
        )
    assert compared >= 1, "the walk met a reward choice beside a Harvest Cells seat"


def _last_recipient_rows(session: GameSession, owner: int) -> list[object]:
    rows: list[object] = []
    for index, action in enumerate(session.engine.legal_actions(session.state, owner)):
        row = sessions_module._serialize_action(index, action, session)
        dry = sessions_module._dry_run(session, action)
        held = dry is not None and unit_over(dry.state, owner)
        rows.append(
            (row["undoable"], row["sent_by_turn_end"], row["strength_after"], held)
        )
    return rows


def _holding(
    state: GameState, seat: int, card: str, deck: tuple[str, ...]
) -> GameState:
    """``seat`` holds ``card`` in place of its first Intrigue card; the deck
    holds every other card of ``deck``."""

    players = list(state.players)
    players[seat] = replace(
        players[seat], intrigue_cards=(card, *players[seat].intrigue_cards[1:])
    )
    return replace(
        state,
        players=tuple(players),
        intrigue_deck=tuple(c for c in deck if c != card),
    )


def _at_endgame_score(state: GameState, seat: int) -> GameState:
    """The same state with ``seat`` at the endgame score: the last round."""

    players = list(state.players)
    players[seat] = replace(
        players[seat], victory_points=state.config.endgame_victory_points
    )
    return replace(state, players=tuple(players))


def test_the_last_recipients_rows_do_not_depend_on_a_hidden_harvest_cells() -> None:
    # The 2026-10-08 review's construction: seed 12 (now 22), Immortality, four human
    # seats answered by the pinned table heuristic. At the last reward
    # recipient's choice, another seat with three units in the Conflict
    # holds one Intrigue card: a Harvest Cells in one world, another card in
    # the other (the same count either way). Without the pause after the
    # rewards, and while the Conflict-end window opened only for a seat that
    # could play one, the dry run stopped at that seat's window in one world
    # and ran on in the other; in the last round (no Round Start) it ran
    # into the Endgame, so the rows' strength previews and whether the seat
    # was held differed. Now both worlds stop at the pause, and past it the
    # window opens in both, on public facts (OQ-103, 2026-10-09). Seed 22
    # since both grafted Agent boxes are offered from the start (codec v143,
    # docs/graft-boxes-plan.md): seed 12's walk meets a grafted Agent turn
    # (walk step 154, no switch row any more) before its case (step 439 on
    # the previous commit's engine) and no longer meets one; 22 is the first
    # seed after it whose walk does.
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, game_seed=22, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    config = session.state.config
    agents = [
        make_agent("heuristic_uprising_table", 120 + seat, config) for seat in range(4)
    ]
    checked = 0
    for _ in range(20_000):
        if summary["finished"] or checked:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(
                game_id,
                held,
                _int(summary["revision"]),
                undo_count=_int(summary["undo_count"]),
            )
            continue
        live = session.state
        owner = _int(_obj(summary["decision"])["owner"])
        ranking = rank_combat(live.players, first_player=live.first_player)
        recipients = len(ranking.rewards)
        harvest = [card for card in live.intrigue_deck if "harvest_cells" in card]
        if (
            str(live.decision_stack[-1].kind).startswith("combat_reward")
            and live.combat_rewards_paid == recipients
            and harvest
        ):
            for seat, player in enumerate(live.players):
                units = player.troops_conflict + player.commanders_conflict
                if seat == owner or units < 3:
                    continue
                if any("harvest_cells" in card for card in player.intrigue_cards):
                    continue
                # The seat holds one Intrigue card either way: its own first
                # card (or one from the deck) in the plain world, a Harvest
                # Cells in the other; the deck holds the card it does not.
                if player.intrigue_cards:
                    card = player.intrigue_cards[0]
                    deck = live.intrigue_deck
                else:
                    card = next(
                        c for c in live.intrigue_deck if "harvest_cells" not in c
                    )
                    deck = (*live.intrigue_deck, card)
                plain = _holding(live, seat, card, deck)
                swapped = _holding(live, seat, harvest[0], deck)
                if not _conflict_end_trigger_cards(
                    swapped, seat, _conflict_losses(swapped)[seat]
                ):
                    continue
                bystander = next(s for s in range(4) if s not in (owner, seat))
                worlds = []
                for state in (
                    plain,
                    swapped,
                    _at_endgame_score(plain, bystander),
                    _at_endgame_score(swapped, bystander),
                ):
                    session.state = state
                    try:
                        worlds.append(_last_recipient_rows(session, owner))
                    finally:
                        session.state = live
                assert worlds[0] == worlds[1], (live.round_number, owner, seat)
                assert worlds[2] == worlds[3], ("last", live.round_number, owner, seat)
                checked += 1
                break
        actions = session.engine.legal_actions(live, owner)
        action = sessions_module._choose(
            agents[owner], live, session.engine.observe(live, owner), actions
        )
        summary = manager.apply_action(
            game_id,
            owner,
            _int(summary["revision"]),
            actions.index(action),
            undo_count=_int(summary["undo_count"]),
        )
    assert checked, "the walk met a last recipient beside a Harvest Cells seat"


# --- the Conflict-end window (OQ-103, user decision 2026-10-09) ------------
#
# The window opens on public facts: every seat with at least three units in
# the Conflict and an Intrigue card is asked, and one that can play nothing
# gets only "쓰지 않음" ("1번은 A안으로 가자", user, 2026-10-09). The decline
# is the seat's press itself, like a Combat Intrigue pass; a lone human
# seat's decline-only window is answered by the server, but never with two
# human seats at the table, where the wait itself would tell.

_DECLINE: Final = "decline_conflict_end_intrigue"
_PLAY: Final = "play_conflict_end_intrigue"
_WINDOW_PROMPT: Final = (
    "Play an Intrigue card that triggers at this Conflict's end, or decline"
)


def _server_declines(session: GameSession, sent: set[int]) -> list[int]:
    """The live decline steps of human seats that no request sent."""

    return [
        index
        for index, step in enumerate(session.steps)
        if isinstance(step, DomainAction)
        and step.action_id == _DECLINE
        and session.seats[step.actor] == "human"
        and index not in sent
    ]


def _window_actions(session: GameSession, seat: int) -> list[str] | None:
    """The seat's legal action ids when its Conflict-end window is on top."""

    state = session.state
    if not state.decision_stack:
        return None
    top = state.decision_stack[-1]
    if top.kind != FrameKind.CONFLICT_END_TRIGGER:
        return None
    return [action.action_id for action in session.engine.legal_actions(state, seat)]


def _walk_first_actions(
    manager: GameSessionManager,
    game_id: str,
    summary: JsonObject,
    sent: set[int],
    stop: object,
) -> JsonObject:
    """Answer each human decision with its first legal action, confirming
    any hold at once, until ``stop(summary)`` holds. The index of every step
    a request sent goes into ``sent``. A lone human seat is never shown a
    decline-only Conflict-end window."""

    session = manager._get(game_id)
    alone = sum(1 for kind in session.seats if kind == "human") == 1
    while not stop(summary):  # type: ignore[operator]
        if summary["finished"]:
            raise AssertionError("the game finished before the condition was met")
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(
                game_id,
                held,
                _int(summary["revision"]),
                undo_count=_int(summary["undo_count"]),
            )
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        if alone:
            assert _window_actions(session, owner) != [_DECLINE], len(session.steps)
        sent.add(len(session.steps))
        summary = manager.apply_action(
            game_id,
            owner,
            _int(summary["revision"]),
            0,
            undo_count=_int(summary["undo_count"]),
        )
    return summary


def test_a_lone_human_seats_decline_only_window_is_answered_for_it() -> None:
    # Seed 7, Immortality, one human seat: in round 2 seat 0 has three units
    # in the Conflict and an Intrigue card it cannot play there. The server
    # declines for it, exactly as the seat's own press would have: the same
    # step and log entry, sealed (nothing to take back, no hold, no unit).
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=7, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()
    summary = _walk_first_actions(
        manager, game_id, summary, sent, lambda _: _server_declines(session, sent)
    )
    [index] = _server_declines(session, sent)
    step = session.steps[index]
    assert step == DomainAction(action_id=_DECLINE, actor=0)
    before = sessions_module._state_after(session, index)
    assert before.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert session.engine.legal_actions(before, 0) == (step,)
    transition = session.engine.apply(before, step)
    entry = live_steps(session.log)[index]
    assert entry == log_step(before, transition.state, step, transition.events)
    assert [event.kind for event in entry.events][0] == "conflict_end_trigger_declined"
    assert session.undo_floor > index
    assert summary["confirmation"] is None
    assert _rows(summary["undo"]) == []
    assert 0 not in session.open_units
    # The game moved on to the next human decision past the Combat.
    assert _obj(summary["decision"])["owner"] == 0
    assert session.state.round_number > before.round_number


def test_an_auto_decline_replays_and_stays_sealed_after_a_load() -> None:
    # The same seed 7 game, saved right before the request that runs into
    # the auto-decline and right after it: a load of the first regenerates
    # the decline when that request is repeated, a load of the second
    # replays it as recorded and keeps it sealed.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=7, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()
    saves: list[tuple[JsonObject, JsonObject]] = []

    def stop(current: JsonObject) -> bool:
        if _server_declines(session, sent):
            return True
        saves.append((manager.save_game(game_id), current))
        return False

    summary = _walk_first_actions(manager, game_id, summary, sent, stop)
    [index] = _server_declines(session, sent)
    document, earlier = saves[-1]
    assert earlier["confirmation"] is None

    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    replayed = manager._get(restored_id)
    owner = _int(_obj(restored["decision"])["owner"])
    restored = manager.apply_action(
        restored_id,
        owner,
        _int(restored["revision"]),
        0,
        undo_count=_int(restored["undo_count"]),
    )
    assert replayed.steps == session.steps
    assert replayed.undo_floor == session.undo_floor
    assert restored["revision"] == summary["revision"]
    assert restored["undo"] == summary["undo"]

    again = manager.restore_game(manager.save_game(game_id))
    reloaded = manager._get(str(again["game_id"]))
    assert reloaded.steps == session.steps
    assert reloaded.undo_floor == session.undo_floor > index
    assert again["confirmation"] is None
    assert again["undo"] == summary["undo"] == []
    assert canonical_state_hash(reloaded.state) == canonical_state_hash(session.state)


def test_undo_never_reaches_back_to_an_auto_declined_window() -> None:
    # After the seed 7 auto-decline, seat 0's next steps can be taken back,
    # but never past the decline: the window is not offered again.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=7, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()
    summary = _walk_first_actions(
        manager, game_id, summary, sent, lambda _: _server_declines(session, sent)
    )
    [index] = _server_declines(session, sent)
    summary = _walk_first_actions(
        manager, game_id, summary, sent, lambda current: _rows(current["undo"])
    )
    [row] = _rows(summary["undo"])
    window = _int(row["steps"])
    assert row["seat"] == 0
    with pytest.raises(SessionError):
        manager.undo(
            game_id,
            0,
            _int(summary["revision"]),
            window + 1,
            undo_count=_int(summary["undo_count"]),
        )
    summary = manager.undo(
        game_id,
        0,
        _int(summary["revision"]),
        window,
        undo_count=_int(summary["undo_count"]),
    )
    assert len(session.steps) > index
    assert _window_actions(session, 0) is None
    assert session.steps[index] == DomainAction(action_id=_DECLINE, actor=0)


def test_with_two_humans_a_decline_only_window_waits_for_one_press() -> None:
    # Seed 7, Immortality, seats 0 and 1 human: in round 1 seat 0 has three
    # units in the Conflict and an Intrigue card it cannot play there. Two
    # humans share the table, so the server never answers for either: the
    # window waits, offering only "쓰지 않음", whose one press ends the
    # seat's part (no hold, nothing to take back, no second press).
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=7, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()

    def decline_only(current: JsonObject) -> bool:
        if current["finished"] or isinstance(current["confirmation"], int):
            return False
        owner = _int(_obj(current["decision"])["owner"])
        return _window_actions(session, owner) == [_DECLINE]

    summary = _walk_first_actions(manager, game_id, summary, sent, decline_only)
    assert _server_declines(session, sent) == []
    decision = _obj(summary["decision"])
    owner = _int(decision["owner"])
    assert decision["kind"] == "conflict_end_trigger"
    assert decision["prompt"] == _WINDOW_PROMPT
    [row] = _rows(manager.legal_actions(game_id, owner)["actions"])
    assert row["action_id"] == _DECLINE
    assert row["undoable"] is False
    assert row["sent_by_turn_end"] is False

    index = len(session.steps)
    summary = manager.apply_action(
        game_id,
        owner,
        _int(summary["revision"]),
        _int(row["index"]),
        undo_count=_int(summary["undo_count"]),
    )
    assert session.steps[index] == DomainAction(action_id=_DECLINE, actor=owner)
    assert summary["confirmation"] is None
    assert [r for r in _rows(summary["undo"]) if r["seat"] == owner] == []
    assert owner not in session.open_units
    assert session.undo_floor > index
    with pytest.raises(SessionError):
        manager.confirm_turn(
            game_id,
            owner,
            _int(summary["revision"]),
            undo_count=_int(summary["undo_count"]),
        )
    assert _server_declines(session, sent | {index}) == []


def test_a_holder_sees_its_play_beside_the_decline() -> None:
    # Seed 18, one human seat: in round 2 seat 0 holds a playable Harvest
    # Cells. The window offers the play and "쓰지 않음" (the press itself),
    # and the server does not answer it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=18, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()
    summary = _walk_first_actions(
        manager,
        game_id,
        summary,
        sent,
        lambda current: not isinstance(current["confirmation"], int)
        and _window_actions(session, _int(_obj(current["decision"])["owner"]))
        is not None,
    )
    assert _server_declines(session, sent) == []
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["prompt"] == _WINDOW_PROMPT
    rows = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [row["action_id"] for row in rows] == [_DECLINE, _PLAY]
    assert rows[0]["undoable"] is False
    assert rows[0]["sent_by_turn_end"] is False
    assert "harvest_cells" in str(_obj(rows[1]["arguments"])["card_id"])


def test_a_play_in_the_window_is_confirmed_by_the_seats_own_decline() -> None:
    # Seed 11, one human seat: seat 0 plays its Harvest Cells and still
    # holds another Intrigue card, so the window stays open with only
    # "쓰지 않음" (a public fact, OQ-103). The play can still be taken back,
    # so the server does not answer the window: the seat's own decline is
    # the press that confirms the play, and seals it. (v146: optional
    # Agent-turn effects offer no refusal (OQ-095 (2), 2026-10-14), which
    # moved seed 33 off this shape; re-searched then, seed 11 is the first
    # of 0-79 under this first-action walk.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=11, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()
    summary = _walk_first_actions(
        manager,
        game_id,
        summary,
        sent,
        lambda current: not isinstance(current["confirmation"], int)
        and _PLAY
        in (_window_actions(session, _int(_obj(current["decision"])["owner"])) or ()),
    )
    rows = _rows(manager.legal_actions(game_id, 0)["actions"])
    play = next(row for row in rows if row["action_id"] == _PLAY)
    played = len(session.steps)
    summary = manager.apply_action(
        game_id,
        0,
        _int(summary["revision"]),
        _int(play["index"]),
        undo_count=_int(summary["undo_count"]),
    )
    assert len(session.steps) == played + 1
    assert _window_actions(session, 0) == [_DECLINE]
    assert summary["confirmation"] is None
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 1}]
    [row] = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert row["action_id"] == _DECLINE
    summary = manager.apply_action(
        game_id,
        0,
        _int(summary["revision"]),
        _int(row["index"]),
        undo_count=_int(summary["undo_count"]),
    )
    assert session.steps[played + 1] == DomainAction(action_id=_DECLINE, actor=0)
    assert summary["confirmation"] is None
    assert _rows(summary["undo"]) == []
    assert session.undo_floor > played + 1
