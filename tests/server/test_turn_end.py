"""Tests for the one-press turn-end convention (2026-09-23, OQ-095).

Every turn end of a human seat is exactly one press of "턴 종료" (project
convention, not a rule; see the module docstring of
``dune_imperium.server.turn_end``). Since user ruling OQ-095 an Agent turn
ends only through its owner's ``finish_agent_turn``, which is that press
itself, and so is a turn-passing card (Withdrawn, Litany Against Fear;
OQ-095 (6)); the server still holds the other unit ends (a Leader pick in
the OQ-007 draft, Conflict rewards, a Control defense, an Arrakeen Scouts
line) for ``confirm_turn``. Which steps end a turn is a reading of the
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
from dataclasses import dataclass
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.combat_deployment import FINISHING_KEY
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.persistence import SaveError
from dune_imperium.server.session_log import live_steps
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
    turn_start_seat,
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


def test_the_last_leader_pick_holds_for_its_own_next_turn() -> None:
    # Seed 0: seat 0 (human) is the First Player, so it picks last (OQ-007,
    # draft_pick_order). The pick crosses straight from Leader-draft setup
    # into seat 0's own round-1 turn -- a phase/round change, and per
    # ``_unit_ended_locked`` that alone ends the unit even though the next
    # decision is again seat 0's own.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    assert summary["first_player"] == 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0

    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    pick = actions[0]
    summary = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(pick["index"])
    )

    assert summary["confirmation"] == 0
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["kind"] == "turn"
    assert manager.legal_actions(game_id, 0)["actions"] == []
    assert manager.snapshot(game_id, 0)["actions"] is None
    with pytest.raises(SessionError, match="has not confirmed"):
        manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    confirmed = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    assert confirmed["confirmation"] is None
    assert _rows(manager.legal_actions(game_id, 0)["actions"])


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
    # Seed 12 (bloodlines, three "random" AI opponents): a Holy War-like
    # effect from an AI seat forces seat 0 to lose one unit while that AI's
    # own turn is still open. Answering it is not a turn end of seat 0's.
    # (Re-searched 2026-09-26: the card-transcription audit's rules fixes
    # moved the old seed 12 off this shape. Re-searched again 2026-10-01:
    # every Agent turn now waits for its owner's finish_agent_turn (OQ-095),
    # which moved seed 7 off it; seed 12 is the only one of 0-39 reaching
    # it under this index-0 walk.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_VS_RANDOM_AI, game_seed=12, bloodlines=True)
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
    # is exactly what still fires it. Seed 33, three random AI opponents,
    # found by a scratch random walk (rng seed 33 * 9973 + 1): seed 18 of
    # scratchpad/verify_item4.py (2026-09-24 session) no longer reaches it
    # once every Agent turn waits for its finish_agent_turn (OQ-095), and
    # seed 33 is the first of 0-39 whose end is a finish_agent_turn.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_VS_RANDOM_AI, game_seed=33)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    calls: list[str] = []
    manager.add_hand_over_listener(calls.append)
    rng = random.Random(33 * 9973 + 1)

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
    # without an explicit end, e.g. test_the_last_leader_pick_holds_for_its_
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


# ------------------------------------------------------------------- saves


def test_a_hold_with_an_empty_undo_window_survives_save_and_restore() -> None:
    # Seed 0 with the Leader draft: seat 0 is the First Player and picks
    # last (test_the_last_leader_pick_holds_for_its_own_next_turn), and its
    # pick runs into the round-1 draw, which closes the undo window to
    # nothing -- but the hold and its empty window both round-trip through
    # save/restore. (Moved 2026-10-01 from seed 21's Agent turn ending in an
    # Intrigue draw: an Agent turn now ends only through finish_agent_turn,
    # which is the press itself and never holds (OQ-095).)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    assert _obj(summary["decision"])["kind"] == "leader_draft"
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    assert summary["confirmation"] == 0
    assert summary["undo"] == []

    document = manager.save_game(game_id)
    assert document["confirmation"] == 0
    assert document["sealed_steps"] == 0
    restored = manager.restore_game(document)
    assert restored["confirmation"] == 0
    assert restored["undo"] == []
    assert restored["revision"] == summary["revision"]


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
    # rewards: seed 15's index-0 walk, two Influence picks of one reward.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=15)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    summary = _play_until(
        manager,
        game_id,
        summary,
        lambda s: (
            s["confirmation"] is None
            and _obj(s["decision"])["kind"] == "combat_reward_distinct_influence"
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
    # 12, 22 and 23 of 0-39 reach it too). The Control defense is one of
    # the holds OQ-095 keeps.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(0)

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


def test_a_remote_hold_with_an_empty_window_still_blocks_the_next_seat() -> None:
    # Seed 3, two claimed human seats: an empty-undo-window hold like the
    # save/restore test above, checked here for the REMOTE-only block on the
    # next seat's own client (open servers let it act regardless,
    # unchanged: test_access.py::
    # test_an_open_server_still_lets_the_next_seat_act_without_the_confirmation).
    # (Re-searched 2026-10-01: seed 6's hold was an Agent turn's, which
    # OQ-095 ends with finish_agent_turn instead. In seed 3 the held unit is
    # seat 1's Conflict reward (placing the reward's Spy), whose end runs
    # into the next round's chance outcomes, and the next decision is human
    # seat 0's turn.)
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="key")
    admin = Credentials(admin_key="key")
    summary = manager.create_game(TWO_HUMANS, game_seed=3, credentials=admin)
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
        held = summary["confirmation"]
        decision = _obj(summary["decision"])
        owner = _int(decision["owner"])
        if isinstance(held, int) and owner != held and owner in creds:
            undo_rows = [row for row in _rows(summary["undo"]) if row["seat"] == held]
            if not undo_rows:
                break
        if isinstance(held, int):
            summary = manager.confirm_turn(
                game_id, held, _int(summary["revision"]), credentials=creds[held]
            )
        else:
            summary = manager.apply_action(
                game_id, owner, _int(summary["revision"]), 0, credentials=creds[owner]
            )
    else:
        raise AssertionError("no empty-window hold blocking a human seat was reached")

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
    _SweepConfig(HUMAN_FIRST, (0,), ("leader_draft",)),
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
            continue
        decision = _obj(summary["decision"])
        owner = _int(decision["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        if not actions:
            tally.violations.append(f"seat {owner}'s {decision['kind']} has no action")
            break
        choice = rng.choice(actions)
        before = session.state
        finishing = finishing_seat(before) == owner
        summary = manager.apply_action(
            game_id,
            owner,
            _int(summary["revision"]),
            _int(choice["index"]),
            undo_count=_int(summary["undo_count"]),
        )
        if choice["action_id"] == "finish_agent_turn":
            tally.agent_turn_presses += 1
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
