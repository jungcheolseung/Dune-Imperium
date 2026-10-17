"""Tests for action undo and the session log (M11 slice 6, OQ-010 boundary)."""

import random
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GameState, PlayerState
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Resources
from dune_imperium.core.replay import ReplayStep
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.persistence import SAVE_FORMAT_VERSION
from dune_imperium.server.session_log import (
    LoggedStep,
    LoggedUndo,
    reveals_hidden_information,
    undo_history,
    undo_window,
)
from dune_imperium.server.sessions import (
    GameSession,
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    _log_entry_json,
)

# The AI seats play the rubric-priced 2026-09-10 table pinned in the registry,
# not ``heuristic``: the scripted revisions below follow that table's moves,
# and ``heuristic`` is retuned as the baseline improves (2026-09-11 demoted
# three spaces and every scripted revision moved). The undo mechanics under
# test do not depend on which table the AI seats use.
HUMAN_FIRST = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
# Seed 14's scripted revisions moved one step earlier with codec v146:
# optional Agent-turn effects offer no refusal (OQ-095 (2), 2026-10-14), so
# seat 3 no longer declines its optional Signet Ring step before ending its
# first turn; the press lapses it. Seat 0's first Agent turn now opens at
# revision 10 and its Dutiful Service visit is served at revision 11.


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _play_raw(
    manager: GameSessionManager, summary: JsonObject, index: int = 0
) -> JsonObject:
    """Apply one action of seat 0 without confirming a paused turn end."""

    return manager.apply_action(
        str(summary["game_id"]),
        seat=0,
        revision=_int(summary["revision"]),
        index=index,
    )


def _play(
    manager: GameSessionManager, summary: JsonObject, index: int = 0
) -> JsonObject:
    """Apply one action of seat 0 and confirm the turn end if it paused."""

    summary = _play_raw(manager, summary, index)
    if summary["confirmation"] == 0:
        summary = manager.confirm_turn(
            str(summary["game_id"]),
            seat=0,
            revision=_int(summary["revision"]),
            undo_count=_int(summary["undo_count"]),
        )
    return summary


def _play_until_revision(
    manager: GameSessionManager, summary: JsonObject, revision: int
) -> JsonObject:
    while _int(summary["revision"]) < revision:
        summary = _play(manager, summary)
    assert summary["revision"] == revision
    return summary


def _play_until_window_closes(
    manager: GameSessionManager, summary: JsonObject
) -> JsonObject:
    """Play seat 0 until an AI seat's turn has closed its undo window."""

    for _ in range(40):
        summary = _play(manager, summary)
        if summary["undo"] == []:
            return summary
    raise AssertionError("the undo window never closed")


def _live_log(manager: GameSessionManager, game_id: str) -> list[LoggedStep]:
    return [
        entry
        for entry in manager._get(game_id).log
        if isinstance(entry, LoggedStep) and not entry.undone
    ]


# ---------------------------------------------------------------- boundary


def _state(**players: PlayerState) -> GameState:
    seats = tuple(
        players.get(f"p{seat}", PlayerState(player_id=seat)) for seat in range(4)
    )
    return GameState(config=RulesetConfig(), seed=1, players=seats)


def test_playing_coercive_negotiation_is_a_reveal() -> None:
    # "Reveal three contracts from the bank" [Coercive Negotiation card]: the
    # bank's top three become known to every seat as the card resolves, so
    # the play step closes the undo window (the actor saw the bank).
    # Since codec v129 the card is played once three units were deployed
    # this turn and resolves at once (OQ-016), so the play itself is the
    # reveal step.
    from dune_imperium.core import GamePhase
    from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
    from dune_imperium.rules import UprisingRulesEngine

    card = "intrigue:coercive_negotiation:0"
    config = RulesetConfig(choam_module=True, bloodlines=True)
    owner = PlayerState(player_id=0, intrigue_cards=(card,), units_deployed_turn=3)
    before = GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        sardaukar_commander_space_ids=(),
        sardaukar_commanders_bank=1,
        contract_bank=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:secrets",
            "contract:espionage_i",
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    play = DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card), ("option", 0)),
    )
    after = UprisingRulesEngine().apply(before, play).state
    assert after.decision_stack[-1].kind == "intrigue_trigger_contract"
    assert reveals_hidden_information(before, after, actor=0) is True


def test_reveal_detection_follows_the_information_flow_rules() -> None:
    # Playing an Intrigue only discloses a card its owner alone knew: the
    # actor's own loss, so it does not close the undo window (user ruling).
    before = _state(p0=PlayerState(player_id=0, intrigue_cards=("intrigue:x",)))
    after = replace(
        _state(p0=PlayerState(player_id=0)), intrigue_discard=("intrigue:x",)
    )
    assert reveals_hidden_information(before, after, actor=0) is False
    # ...but for anyone else it is a reveal, and so it is for chance (no actor).
    assert reveals_hidden_information(before, after, actor=1) is True
    assert reveals_hidden_information(before, after, actor=None) is True

    # Drawing from the own deck reveals the deck top to the drawer: undoing
    # would let them choose again knowing it.
    before = _state(p0=PlayerState(player_id=0, deck=("a", "b")))
    after = _state(p0=PlayerState(player_id=0, deck=("b",), hand=("a",)))
    assert reveals_hidden_information(before, after, actor=0) is True

    # Revealing the hand (hand -> in play) is the actor's own disclosure.
    before = _state(p0=PlayerState(player_id=0, hand=("a", "b")))
    after = _state(p0=PlayerState(player_id=0, in_play=("a", "b")))
    assert reveals_hidden_information(before, after, actor=0) is False

    # An opponent's hidden card becoming public is a reveal for the actor.
    before = _state(p1=PlayerState(player_id=1, hand=("c",)))
    after = _state(p1=PlayerState(player_id=1, discard_pile=("c",)))
    assert reveals_hidden_information(before, after, actor=0) is True
    assert reveals_hidden_information(before, after, actor=1) is False

    # The Imperium Row refilling from the deck reveals a card to everyone.
    before = replace(_state(), imperium_deck=("imp:1", "imp:2"))
    after = replace(_state(), imperium_deck=("imp:2",), imperium_row=("imp:1",))
    assert reveals_hidden_information(before, after, actor=0) is True

    # A card entering a hand through a public move stays public: no reveal.
    before = replace(_state(), imperium_row=("imp:1",))
    after = _state(p0=PlayerState(player_id=0, hand=("imp:1",), hand_public=("imp:1",)))
    assert reveals_hidden_information(before, after, actor=0) is False


def test_a_starting_card_removed_by_a_leader_pick_is_not_a_reveal() -> None:
    # Limited Allies: "You start the game without Diplomacy in your deck"
    # [Staban Tuek card]. The pick takes the card out of a face-down deck
    # whose ten cards everybody knows, and shows nobody where it sat.
    diplomacy = "player:0:starter:diplomacy:0"
    dagger = "player:0:starter:dagger:0"
    before = _state(p0=PlayerState(player_id=0, deck=(dagger, diplomacy)))
    after = _state(p0=PlayerState(player_id=0, leader_id="staban_tuek", deck=(dagger,)))
    assert reveals_hidden_information(before, after, actor=0) is False

    # Only the card the printed rule names, and only as that Leader is picked.
    lost_dagger = _state(
        p0=PlayerState(player_id=0, leader_id="staban_tuek", deck=(diplomacy,))
    )
    assert reveals_hidden_information(before, lost_dagger, actor=0) is True
    other_leader = _state(
        p0=PlayerState(player_id=0, leader_id="lady_jessica", deck=(dagger,))
    )
    assert reveals_hidden_information(before, other_leader, actor=0) is True
    picked = _state(
        p0=PlayerState(player_id=0, leader_id="staban_tuek", deck=(dagger, diplomacy))
    )
    assert reveals_hidden_information(picked, after, actor=0) is True
    # Drawing it instead is still the drawer learning their deck top.
    drawn = _state(
        p0=PlayerState(
            player_id=0, leader_id="staban_tuek", deck=(dagger,), hand=(diplomacy,)
        )
    )
    assert reveals_hidden_information(before, drawn, actor=0) is True


def test_every_draft_pick_but_the_last_can_be_taken_back() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])
    picker = _int(_obj(summary["decision"])["owner"])
    deck_before = manager._get(game_id).state.players[picker].deck

    actions = _rows(manager.legal_actions(game_id, picker)["actions"])
    leaders = [_obj(entry["arguments"])["leader_id"] for entry in actions]
    assert "staban_tuek" in leaders
    assert all(entry["undoable"] is True for entry in actions)

    summary = manager.apply_action(
        game_id,
        seat=picker,
        revision=_int(summary["revision"]),
        index=leaders.index("staban_tuek"),
    )
    assert summary["undo"] == [{"seat": picker, "steps": 1}]
    assert len(manager._get(game_id).state.players[picker].deck) == 9

    rewound = manager.undo(game_id, seat=picker, revision=_int(summary["revision"]))
    assert _obj(rewound["decision"])["owner"] == picker
    assert manager._get(game_id).state.players[picker].deck == deck_before


def test_undo_window_holds_own_consecutive_steps_and_closes_on_reveals() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = str(summary["game_id"])
    # Seat 0 is first player: nothing to undo before the first action.
    assert summary["first_player"] == 0
    assert summary["undo"] == []
    assert summary["log_count"] == len(manager._get(game_id).log)

    summary = _play(manager, summary)
    assert summary["undo"] == [{"seat": 0, "steps": 1}]

    # From here the window is checked as a property of the log rather than at
    # scripted revisions: it must always equal the trailing run of seat 0's own
    # steps that revealed nothing. The AI seats are heuristics, so retuning
    # their preferences changes how many steps their turns take and which
    # choices seat 0 is offered next -- but never this invariant.
    widest = 0
    closed_by_a_reveal = False
    for _ in range(60):
        summary = _play(manager, summary)
        live = _live_log(manager, game_id)
        expected = 0
        for entry in reversed(live):
            if entry.actor != 0 or entry.reveals:
                break
            expected += 1
        assert summary["undo"] == (
            [] if expected == 0 else [{"seat": 0, "steps": expected}]
        )
        assert undo_window(manager._get(game_id).log, 0) == expected
        widest = max(widest, expected)
        if expected == 0 and live[-1].actor == 0 and live[-1].reveals:
            closed_by_a_reveal = True

    # The run has to have exercised both halves, or the invariant above held
    # only because the window never opened.
    assert widest >= 2, "seat 0 never accumulated consecutive undoable steps"
    assert closed_by_a_reveal, "no revealing step ever closed the window"


# ---------------------------------------------------------------- turn end


def test_turn_end_waits_for_confirmation_while_steps_are_undoable() -> None:
    # Seed 1 with the Leader draft (OQ-007): seat 0 picks before an AI seat,
    # so its pick reveals nothing and can still be taken back; the unit is
    # over, so the session pauses instead of letting the next picker act.
    # (Moved 2026-10-01 from seed 14's Agent turn: an Agent turn now ends
    # only through its explicit finish_agent_turn, which is the press itself
    # and never pauses (OQ-095); a Leader pick still ends with the pause.)
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = str(summary["game_id"])
    pick_revision = _int(summary["revision"])
    assert _obj(summary["decision"])["kind"] == "leader_draft"
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert actions[0]["action_id"] == "pick_leader"
    assert actions[0]["undoable"] is True
    summary = _play_raw(manager, summary)

    revision = pick_revision + 1
    assert summary["revision"] == revision
    assert summary["confirmation"] == 0
    assert _obj(summary["decision"])["owner"] != 0
    assert summary["undo"] == [{"seat": 0, "steps": 1}]
    assert len(manager._get(game_id).steps) == revision
    assert manager.legal_actions(game_id, 0)["actions"] == []
    with pytest.raises(SessionError, match="another seat"):
        manager.apply_action(game_id, seat=0, revision=revision, index=0)
    with pytest.raises(StaleRevisionError):
        manager.confirm_turn(game_id, seat=0, revision=pick_revision)

    # Taking a step back reopens the seat's own decision.
    rewound = manager.undo(game_id, seat=0, revision=revision, steps=1)
    assert rewound["confirmation"] is None
    assert _obj(rewound["decision"])["owner"] == 0
    assert rewound["revision"] == pick_revision

    # Redo the same step and confirm: only now do the other seats act.
    summary = _play_raw(manager, rewound)
    assert summary["confirmation"] == 0
    confirmed = manager.confirm_turn(
        game_id, seat=0, revision=revision, undo_count=_int(summary["undo_count"])
    )
    assert confirmed["confirmation"] is None
    assert _int(confirmed["revision"]) > revision
    assert confirmed["undo"] == []
    with pytest.raises(SessionError, match="no turn end"):
        manager.confirm_turn(game_id, seat=0, revision=_int(confirmed["revision"]))


def test_a_turn_ending_in_a_reveal_still_waits_for_its_press() -> None:
    # Seed 21's opening turn resolves Assembly Hall's Intrigue draw last,
    # which reveals the deck top to the drawer and closes the undo window --
    # but the turn still waits for its own press, even with nothing left to
    # protect. Since OQ-095 that press is the explicit finish_agent_turn:
    # the turn stays open after its last effect, and here the seat could
    # still play the Plot Intrigue it just drew before pressing. The press
    # hands over at once, with no confirm_turn after it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = str(summary["game_id"])
    summary = _play_raw(manager, summary)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [(entry["action_id"], entry["undoable"]) for entry in actions] == [
        ("resolve_board_effect", False)
    ]
    summary = _play_raw(manager, summary)

    assert summary["confirmation"] is None
    assert summary["undo"] == []
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0 and decision["kind"] == "agent_effects"
    assert decision["turn_end_ready"] is True
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [(entry["action_id"], entry["undoable"]) for entry in actions] == [
        ("play_intrigue", True),
        ("finish_agent_turn", False),
    ]

    pressed = _play_raw(manager, summary, index=1)
    assert pressed["confirmation"] is None
    assert _int(pressed["revision"]) > _int(summary["revision"])
    with pytest.raises(SessionError, match="no turn end"):
        manager.confirm_turn(game_id, 0, _int(pressed["revision"]))


@pytest.mark.parametrize("remote", (False, True))
@pytest.mark.parametrize("epic_game", (False, True))
@pytest.mark.parametrize("expansions", (False, True))
def test_every_leader_pick_can_be_undone_before_its_turn_end(
    epic_game: bool,
    expansions: bool,
    remote: bool,
) -> None:
    # docs/rules/open-questions.md OQ-007: "draft에서는 그 카드를 마지막
    # pick 뒤에 나눈다" [Rise of Ix p. 10]. The 2026-10-05 user correction
    # keeps that hidden deal after the last pick's turn-end press as well.
    # OQ-010's hidden-information boundary itself must remain unchanged.
    manager = GameSessionManager(
        access=AccessMode.REMOTE if remote else AccessMode.OPEN,
        admin_key="draft-test" if remote else None,
    )
    credentials = Credentials(admin_key="draft-test" if remote else None)
    summary = manager.create_game(
        ("human",) * 4,
        credentials=credentials,
        leader_draft=True,
        game_seed=9,
        epic_game=epic_game,
        choam_module=expansions,
        bloodlines=expansions,
        tech_module=expansions,
        immortality=expansions,
        arrakeen_scouts=expansions,
    )
    game_id = str(summary["game_id"])
    if remote:
        tokens = frozenset(
            manager.claim_seat(game_id, seat, f"Player {seat}").token
            for seat in range(4)
        )
        credentials = Credentials(seat_tokens=tokens, admin_key="draft-test")
    for position in range(4):
        seat = _int(_obj(summary["decision"])["owner"])
        before = manager._get(game_id).state
        actions = _rows(
            manager.legal_actions(game_id, seat, credentials=credentials)["actions"]
        )
        assert actions and all(action["undoable"] is True for action in actions)
        summary = manager.apply_action(
            game_id, seat, _int(summary["revision"]), 0, credentials=credentials
        )
        assert summary["undo"] == [{"seat": seat, "steps": 1}]
        assert summary["phase"] == "setup"
        after = manager._get(game_id).state
        assert all(not p.hand and not p.intrigue_cards for p in after.players)
        assert not reveals_hidden_information(before, after, seat)
        assert after.face_up_contract_ids == ()
        # Every client's view is still pre-deal, including the
        # last picker's. Replaying an undo restores the exact draft state.
        for viewer in range(4):
            snapshot = manager.snapshot(game_id, viewer, credentials=credentials)
            assert _obj(_obj(snapshot["view"])["private"])["hand"] == []
            assert _obj(_obj(snapshot["view"])["private"])["intrigue_cards"] == []
        summary = manager.undo(
            game_id, seat, _int(summary["revision"]), credentials=credentials
        )
        assert manager._get(game_id).state == before
        assert summary["confirmation"] is None
        summary = manager.apply_action(
            game_id, seat, _int(summary["revision"]), 1, credentials=credentials
        )
        if position < 3:
            assert summary["confirmation"] == seat
            summary = manager.confirm_turn(
                game_id, seat, _int(summary["revision"]), credentials=credentials
            )
        else:
            finish = _rows(
                manager.legal_actions(game_id, seat, credentials=credentials)["actions"]
            )
            assert [(a["action_id"], a["undoable"]) for a in finish] == [
                ("finish_leader_draft", False)
            ]
            summary = manager.apply_action(
                game_id, seat, _int(summary["revision"]), 0, credentials=credentials
            )
        assert summary["undo"] == []
        with pytest.raises(SessionError, match="at most 0"):
            manager.undo(
                game_id, seat, _int(summary["revision"]), credentials=credentials
            )
    assert all(p.leader_id is not None for p in manager._get(game_id).state.players)
    assert summary["confirmation"] is None


def test_legal_actions_report_whether_each_step_can_be_taken_back() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 11)
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])

    # Dutiful Service's Solari icon and the Emperor Influence reveal nothing.
    assert {entry["action_id"]: entry["undoable"] for entry in actions} == {
        "resolve_board_effect": True,
        "resolve_faction_influence": True,
    }


def test_a_save_taken_during_the_pause_restores_the_pause() -> None:
    # The pause of test_turn_end_waits_for_confirmation_while_steps_are_
    # undoable (seed 1, Leader draft; moved 2026-10-01 from seed 14's Agent
    # turn, which OQ-095 ends with finish_agent_turn instead of a pause).
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = str(summary["game_id"])
    summary = _play_raw(manager, summary)
    assert summary["confirmation"] == 0
    assert summary["undo"] == [{"seat": 0, "steps": 1}]

    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    assert restored["confirmation"] == 0
    assert restored["revision"] == summary["revision"]
    assert restored["undo"] == [{"seat": 0, "steps": 1}]


# ------------------------------------------------ piles of the expansions


def _play_seat0_until(
    manager: GameSessionManager, summary: JsonObject, action_id: str
) -> tuple[JsonObject, dict[str, object]]:
    """Play seat 0 at random (pressing its turn ends) until ``action_id`` is legal."""

    game_id = str(summary["game_id"])
    rng = random.Random(_int(summary["revision"]))
    for _ in range(3_000):
        assert not summary["finished"], f"{action_id} never became legal"
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id,
                seat=0,
                revision=_int(summary["revision"]),
                undo_count=_int(summary["undo_count"]),
            )
            continue
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        wanted = [entry for entry in actions if entry["action_id"] == action_id]
        if wanted:
            return summary, wanted[0]
        summary = _play_raw(manager, summary, index=_int(rng.choice(actions)["index"]))
    raise AssertionError(f"{action_id} never became legal")


@pytest.mark.parametrize(
    ("action_id", "expansion", "game_seed"),
    [
        # The Row refills from the face-down Tleilaxu deck [Immortality p. 9].
        # Seed 1: since every Agent turn waits for its finish_agent_turn
        # (OQ-095), seed 0's random walk never makes the purchase legal
        # before the game ends (re-searched 2026-10-01; seeds 1 and 3 of 0-5
        # reach it).
        ("acquire_tleilaxu", "immortality", 1),
        # The stack's next tile turns face up [Bloodlines p. 6].
        ("acquire_tech", "tech_module", 0),
    ],
)
def test_a_purchase_that_turns_up_a_hidden_card_cannot_be_taken_back(
    action_id: str, expansion: str, game_seed: int
) -> None:
    # 2026-09-24, found in play: buying from the Tleilaxu Row could be taken
    # back after the refill had shown the deck's next card, because the
    # Tleilaxu deck (and the Skill and Tech stacks) were missing from the
    # hidden piles the undo boundary reads (OQ-010: what left a hidden pile
    # cannot be taken back).
    manager = GameSessionManager()
    summary = manager.create_game(
        HUMAN_FIRST,
        game_seed=game_seed,
        immortality=expansion == "immortality",
        bloodlines=expansion == "tech_module",
        tech_module=expansion == "tech_module",
    )
    summary, action = _play_seat0_until(manager, summary, action_id)
    assert action["undoable"] is False

    game_id = str(summary["game_id"])
    bought = _play_raw(manager, summary, index=_int(action["index"]))
    assert [row for row in _rows(bought["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="at most 0"):
        manager.undo(
            game_id,
            seat=0,
            revision=_int(bought["revision"]),
            undo_count=_int(bought["undo_count"]),
        )


def test_reveal_detection_covers_the_expansion_piles() -> None:
    config = RulesetConfig(
        choam_module=True, bloodlines=True, tech_module=True, immortality=True
    )
    base = GameState(
        config=config,
        seed=1,
        players=tuple(PlayerState(player_id=seat) for seat in range(4)),
    )

    # Tleilaxu Row refill: the deck's top card turns face up.
    before = replace(base, tleilaxu_deck=("t:next", "t:after"), tleilaxu_row=("t:a",))
    after = replace(base, tleilaxu_deck=("t:after",), tleilaxu_row=("t:a", "t:next"))
    assert reveals_hidden_information(before, after, actor=0) is True

    # A Skill is refilled from the face-down stack [Bloodlines p. 4].
    before = replace(base, skill_stack=("s:next",), skill_face_up=("s:a",))
    after = replace(base, skill_face_up=("s:a", "s:next"))
    assert reveals_hidden_information(before, after, actor=0) is True

    # The tile under an acquired Tech tile turns face up.
    before = replace(base, tech_stacks=(("tech:top", "tech:next", "tech:last"),))
    after = replace(base, tech_stacks=(("tech:next", "tech:last"),))
    assert reveals_hidden_information(before, after, actor=0) is True
    # ...but nothing is revealed while it stays under the top.
    shuffled = replace(base, tech_stacks=(("tech:top", "tech:last", "tech:next"),))
    assert reveals_hidden_information(before, shuffled, actor=0) is False


# ---------------------------------------------------------------- undo


def test_undo_rewinds_to_the_seats_earlier_decision_and_keeps_the_log() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 11)
    view_before = manager.view(game_id, 0)
    actions_before = manager.legal_actions(game_id, 0)
    steps_before = list(manager._get(game_id).steps)
    summary = _play(manager, summary)
    assert summary["revision"] == 12
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    undone_step = manager._get(game_id).steps[-1]

    with pytest.raises(StaleRevisionError):
        manager.undo(game_id, seat=0, revision=11, steps=1)
    with pytest.raises(SessionError, match="at most 2"):
        manager.undo(game_id, seat=0, revision=12, steps=3)
    with pytest.raises(SessionError, match="at most"):
        manager.undo(game_id, seat=0, revision=12, steps=0)
    with pytest.raises(SeatAccessError):
        manager.undo(game_id, seat=1, revision=12, steps=1)

    assert summary["undo_count"] == 0
    rewound = manager.undo(game_id, seat=0, revision=12, steps=1, undo_count=0)

    assert rewound["revision"] == 11
    assert rewound["undo_count"] == 1
    assert rewound["undo"] == [{"seat": 0, "steps": 1}]
    assert manager.view(game_id, 0) == view_before
    assert manager.legal_actions(game_id, 0) == actions_before
    session = manager._get(game_id)
    assert session.steps == steps_before
    # The taken-back step stays in the log, flagged, behind its marker.
    assert session.log[-1] == LoggedUndo(seat=0, count=1)
    flagged = session.log[-2]
    assert isinstance(flagged, LoggedStep)
    assert flagged.undone is True
    assert flagged.step == undone_step
    assert rewound["log_count"] == len(session.log)

    # A different choice continues the game from the rewound decision.
    assert len(_rows(actions_before["actions"])) >= 2
    resumed = _play(manager, rewound, index=1)
    assert _int(resumed["revision"]) >= 12
    assert manager._get(game_id).steps[len(steps_before)] != undone_step

    # The undo generation guards a stale client: a request carrying the
    # pre-undo generation is refused even when its revision matches again.
    stale_revision = _int(resumed["revision"])
    with pytest.raises(StaleRevisionError, match="undo generation"):
        manager.apply_action(
            game_id, seat=0, revision=stale_revision, index=0, undo_count=0
        )
    with pytest.raises(StaleRevisionError, match="undo generation"):
        manager.undo(game_id, seat=0, revision=stale_revision, undo_count=0)
    manager.apply_action(
        game_id, seat=0, revision=stale_revision, index=0, undo_count=1
    )

    # Log projection: the live steps are exactly the non-undone entries.
    live = _live_log(manager, game_id)
    assert [entry.step for entry in live] == manager._get(game_id).steps


def test_the_log_is_served_per_seat_with_undo_markers() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 11)
    summary = manager.undo(game_id, seat=0, revision=11, steps=1)

    log = manager.log(game_id, 0)
    entries = _rows(log["entries"])
    assert log["count"] == len(entries) == summary["log_count"]
    assert [entry["index"] for entry in entries] == list(range(len(entries)))
    assert entries[-1] == {
        "index": len(entries) - 1,
        "type": "undo",
        "seat": 0,
        "count": 1,
    }
    undone = entries[-2]
    assert undone["type"] == "action" and undone["undone"] is True
    assert undone["actor"] == 0
    assert all(entry["undone"] is False for entry in entries[:-2])
    kinds = {entry["type"] for entry in entries}
    assert kinds == {"action", "undo"}
    assert any(_rows(entry["events"]) for entry in entries if entry["type"] == "action")

    tail = manager.log(game_id, 0, after=len(entries) - 2)
    assert [entry["index"] for entry in _rows(tail["entries"])] == [
        len(entries) - 2,
        len(entries) - 1,
    ]
    with pytest.raises(SessionError, match="out of range"):
        manager.log(game_id, 0, after=len(entries) + 1)
    with pytest.raises(SeatAccessError):
        manager.log(game_id, 1)


def test_log_entries_redact_hidden_arguments_and_private_events() -> None:
    step = DomainAction(
        action_id="choose_intrigue_discard",
        actor=1,
        arguments=(("card_id", "imp:secret"),),
    )
    entry = LoggedStep(
        step=step,
        events=(
            GameEvent(event_id="e:public", kind="card_discarded", payload=()),
            GameEvent(event_id="e:private", kind="cards_drawn", visible_to=(1,)),
        ),
        reveals=False,
        hidden_arguments=frozenset({"imp:secret"}),
    )

    for_owner = _log_entry_json(3, entry, seat=1, finished=False)
    assert for_owner["arguments"] == {"card_id": "imp:secret"}
    assert [_obj(event)["kind"] for event in _rows(for_owner["events"])] == [
        "card_discarded",
        "cards_drawn",
    ]

    for_other = _log_entry_json(3, entry, seat=0, finished=False)
    assert for_other["arguments"] == {"card_id": "(비공개)"}
    assert [_obj(event)["kind"] for event in _rows(for_other["events"])] == [
        "card_discarded"
    ]

    # Post-game full disclosure (OQ-010 ruling 4) lifts every redaction.
    disclosed = _log_entry_json(3, entry, seat=0, finished=True)
    assert disclosed["arguments"] == {"card_id": "imp:secret"}
    assert len(_rows(disclosed["events"])) == 2

    chance = LoggedStep(
        step=ChanceOutcome("draw:1", ("a", "b")),
        events=(),
        reveals=True,
        hidden_arguments=frozenset(),
    )
    assert "values" not in _log_entry_json(0, chance, seat=0, finished=False)
    assert _log_entry_json(0, chance, seat=0, finished=True)["values"] == ["a", "b"]


# ---------------------------------------------------------------- saves


def _game_with_an_undo(manager: GameSessionManager) -> JsonObject:
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 11)
    summary = manager.undo(game_id, seat=0, revision=11, steps=1)
    return _play(manager, summary, index=1)


def test_saves_carry_the_undo_history_and_restore_the_same_log() -> None:
    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    game_id = str(summary["game_id"])

    document = manager.save_game(game_id)
    assert document["format_version"] == SAVE_FORMAT_VERSION == 2
    saved_log = _rows(document["log"])
    assert any(entry.get("type") == "undo" for entry in saved_log)
    assert any(entry.get("undone") is True for entry in saved_log)
    live_entries = [
        entry
        for entry in saved_log
        if entry.get("type") != "undo" and not entry["undone"]
    ]
    assert len(_rows(document["steps"])) == len(live_entries)

    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["revision"] == summary["revision"]
    assert restored["undo_count"] == summary["undo_count"] == 1
    assert restored["undo"] == summary["undo"]
    assert restored["log_count"] == summary["log_count"]
    original = manager.log(game_id, 0)["entries"]
    assert manager.log(restored_id, 0)["entries"] == original
    assert manager._get(restored_id).log == manager._get(game_id).log


def _game_with_two_single_step_undos(
    manager: GameSessionManager,
) -> tuple[JsonObject, list[ReplayStep]]:
    """Seed 14 at revision 12: seat 0 takes back its two steps one at a time.

    The second undo flags a step logged before the first undo's marker, so
    the log ends ``A(undone), B(undone), undo(1), undo(1)``: a marker takes
    back the latest live steps when it is logged, not the entries right
    before it.
    """

    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 11)
    summary = _play(manager, summary)
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    taken_back = list(manager._get(game_id).steps[-2:])
    summary = manager.undo(game_id, seat=0, revision=12, steps=1, undo_count=0)
    summary = manager.undo(game_id, seat=0, revision=11, steps=1, undo_count=1)
    return summary, taken_back


def test_two_single_step_undos_in_a_row_save_and_restore() -> None:
    manager = GameSessionManager()
    summary, (first, second) = _game_with_two_single_step_undos(manager)
    game_id = str(summary["game_id"])
    tail = manager._get(game_id).log[-4:]
    assert [entry.step for entry in tail if isinstance(entry, LoggedStep)] == [
        first,
        second,
    ]
    assert all(entry.undone for entry in tail if isinstance(entry, LoggedStep))
    assert tail[2:] == [LoggedUndo(seat=0, count=1), LoggedUndo(seat=0, count=1)]

    document = manager.save_game(game_id)
    restored = manager.restore_game(document)
    restored_id = str(restored["game_id"])
    assert restored["revision"] == summary["revision"] == 10
    assert restored["undo_count"] == summary["undo_count"] == 2
    assert restored["undo"] == summary["undo"]
    assert manager._get(restored_id).log == manager._get(game_id).log

    # Both copies go on the same way from the rewound decision.
    assert _play(manager, restored, index=1)["revision"] == (
        _play(manager, summary, index=1)["revision"]
    )


def test_undo_history_names_each_single_step_undo_separately() -> None:
    manager = GameSessionManager()
    summary, (first, second) = _game_with_two_single_step_undos(manager)
    history = undo_history(manager._get(str(summary["game_id"])).log)

    # Both undos rewound the timeline that stands to its tenth live step:
    # the first took back the later step, the second the earlier one.
    assert [(position, marker.count) for position, marker, _ in history] == [
        (10, 1),
        (10, 1),
    ]
    assert [[entry.step for entry in undone] for _, _, undone in history] == [
        [second],
        [first],
    ]


def test_an_undo_across_a_new_step_restores_with_its_own_steps() -> None:
    # Undo one step, take a different one, then undo both live steps of the
    # window at once: the marker takes back the step logged before the
    # earlier marker and the new one after it.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = str(summary["game_id"])
    summary = _play_until_revision(manager, summary, 11)
    summary = _play(manager, summary)
    first = manager._get(game_id).steps[-2]
    summary = manager.undo(game_id, seat=0, revision=12, steps=1, undo_count=0)
    summary = _play_raw(manager, summary, index=1)
    replacement = manager._get(game_id).steps[-1]
    assert summary["undo"] == [{"seat": 0, "steps": 2}]
    summary = manager.undo(
        game_id,
        seat=0,
        revision=_int(summary["revision"]),
        steps=2,
        undo_count=_int(summary["undo_count"]),
    )

    history = undo_history(manager._get(game_id).log)
    assert [[entry.step for entry in undone] for _, _, undone in history][-1] == [
        first,
        replacement,
    ]
    restored = manager.restore_game(manager.save_game(game_id))
    assert manager._get(str(restored["game_id"])).log == manager._get(game_id).log


def test_version_one_saves_still_load_without_undo_history() -> None:
    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    document = manager.save_game(str(summary["game_id"]))
    legacy = {key: value for key, value in document.items() if key != "log"}
    legacy["format_version"] = 1

    restored = manager.restore_game(legacy)

    session = manager._get(str(restored["game_id"]))
    assert restored["revision"] == summary["revision"]
    assert restored["undo_count"] == 0
    assert all(isinstance(entry, LoggedStep) for entry in session.log)
    assert [entry.step for entry in session.log if isinstance(entry, LoggedStep)] == (
        session.steps
    )


def test_tampered_logs_are_rejected() -> None:
    from dune_imperium.server.persistence import SaveError

    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    document = manager.save_game(str(summary["game_id"]))
    log = _rows(document["log"])

    marker_index = next(i for i, entry in enumerate(log) if entry.get("type") == "undo")
    wrong_count = list(log)
    wrong_count[marker_index] = {**log[marker_index], "count": 2}
    with pytest.raises(SaveError, match="undo marker count"):
        manager.restore_game({**document, "log": wrong_count})

    wrong_seat = list(log)
    wrong_seat[marker_index] = {**log[marker_index], "seat": 1}
    with pytest.raises(SaveError, match="takes back another seat's step"):
        manager.restore_game({**document, "log": wrong_seat})

    reordered = list(log)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(SaveError, match="does not match recorded step"):
        manager.restore_game({**document, "log": reordered})

    with pytest.raises(SaveError, match="save log must be a list"):
        manager.restore_game({**document, "log": None})


# ---------------------------------------------------------------- review


def test_review_reports_where_steps_were_taken_back() -> None:
    manager = GameSessionManager()
    summary = _game_with_an_undo(manager)
    game_id = str(summary["game_id"])
    for _ in range(3_000):
        if summary["finished"]:
            break
        summary = _play(manager, summary)
    assert summary["finished"] is True

    review = manager.review(game_id, 0)
    history = _rows(review["undo_history"])
    assert len(history) == 1
    assert history[0]["seat"] == 0
    assert history[0]["count"] == 1
    # The undo rewound to live step 10 (revision 10 = ten steps applied).
    assert history[0]["step"] == 10
    undone = _rows(history[0]["undone"])
    assert len(undone) == 1
    assert undone[0]["type"] == "action" and undone[0]["actor"] == 0
    assert _rows(review["steps"])[10] != undone[0]


# ------------------------------------------------- a confirmed hand-over


def test_a_confirmed_turn_end_stays_handed_over_to_the_next_human() -> None:
    # ``confirm_turn`` promises to close the seat's undo window. The log
    # closes it at the next chance outcome or other seat's step, but when
    # the next seat is a human who has not moved yet there is no such step:
    # the seat that confirmed could take the turn back from under them
    # (found by the slice 5 review; two browsers make it visible).
    #
    # A hold's undo window was not always open to begin with (2026-09-23:
    # every turn end waited for its press, whether or not it left anything
    # undoable); since 2026-10-08 every hold leaves its seat a step to take
    # back (test_turn_end's sweep). The skip below stays harmless.
    #
    # Seed 0 with the Leader draft (moved 2026-10-01 from seed 7's held
    # Agent turns, which OQ-095 ends with the explicit finish_agent_turn
    # instead): human seat 1 picks right before human seat 0
    # (draft_pick_order, OQ-007), and a pick that is not the last one can
    # still be taken back.
    manager = GameSessionManager()
    seats = ("human", "human", HUMAN_FIRST[1], HUMAN_FIRST[1])
    summary = manager.create_game(seats, leader_draft=True, game_seed=0)
    game_id = str(summary["game_id"])

    checked = 0
    for _ in range(400):
        if summary["finished"] or checked >= 3:
            break
        revision = _int(summary["revision"])
        held = summary["confirmation"]
        if not isinstance(held, int):
            owner = _int(_obj(summary["decision"])["owner"])
            summary = manager.apply_action(game_id, owner, revision, 0)
            continue
        before = [row for row in _rows(summary["undo"]) if row["seat"] == held]
        summary = manager.confirm_turn(game_id, held, revision)
        if not before:
            continue
        successor = _int(_obj(summary["decision"])["owner"])
        if seats[successor] != "human" or _int(summary["revision"]) != revision:
            # AI seats (or a chance outcome) followed: the log closed the
            # window by itself, which the tests above cover.
            continue
        # The decision went straight to the other human: nothing was logged
        # after the confirmation, and still the confirmed steps are sealed.
        assert successor != held
        assert [row for row in _rows(summary["undo"]) if row["seat"] == held] == []
        with pytest.raises(SessionError, match="at most 0 step"):
            manager.undo(game_id, held, _int(summary["revision"]))
        assert manager.summary(game_id)["undo_count"] == summary["undo_count"]
        checked += 1
        # The successor's own steps open a window of their own as before.
        summary = manager.apply_action(
            game_id, successor, _int(summary["revision"]), 0
        )
        own = [row for row in _rows(summary["undo"]) if row["seat"] == successor]
        if not summary["finished"] and own:
            assert _int(own[0]["steps"]) == 1
    assert checked >= 1, "no human-to-human confirmation was reached"


# ------------------------------------------------ Imperial Privilege


def _play_seat0_to_imperial_privilege(
    manager: GameSessionManager, summary: JsonObject
) -> JsonObject:
    """Play seat 0 by its first action, sending an Agent to Imperial
    Privilege whenever it can while another of its Agents is on the board,
    until that visit's choices are served."""

    game_id = str(summary["game_id"])
    for _ in range(1_000):
        assert not summary["finished"], "Imperial Privilege was never reached"
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id,
                seat=0,
                revision=_int(summary["revision"]),
                undo_count=_int(summary["undo_count"]),
            )
            continue
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        if any(
            row["action_id"] == "recall_agent_for_imperial_privilege" for row in actions
        ):
            return summary
        index = 0
        if manager._get(game_id).state.players[0].agent_locations:
            index = next(
                (
                    _int(row["index"])
                    for row in actions
                    if row["action_id"] == "agent_turn"
                    and _obj(row["arguments"]).get("space_id") == "imperial_privilege"
                ),
                0,
            )
        summary = _play_raw(manager, summary, index=index)
    raise AssertionError("Imperial Privilege was never reached")


def test_imperial_privilege_recall_can_be_taken_back_and_its_draw_cannot() -> None:
    """ "4번은 소환과 뽑기가 당연히 두 단계로 나눠야지. 이건 정말 기본적인
    원칙인데" (user ruling 2026-10-10, OQ-027 (d)): Imperial Privilege's
    recall is a step of its own, which reveals nothing and so stays in the
    seat's undo window, while the card draw beside it comes from the hidden
    deck and closes the window (OQ-010). Before the split the recall drew
    the card in the same step and could never be taken back. Since codec
    v146 the recall is offered at once beside the optional Intrigue trade,
    with no slot to decline first (OQ-095 (2), user ruling 2026-10-14).

    Seed 0: seat 0, playing its first action, reaches Imperial Privilege
    with another Agent on the board; the placement itself is the one step
    its undo window holds there.
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    summary = _play_seat0_to_imperial_privilege(manager, summary)

    def served() -> dict[str, dict[str, object]]:
        return {
            str(row["action_id"]): row
            for row in _rows(manager.legal_actions(game_id, 0)["actions"])
        }

    rows = served()
    draw = rows["resolve_board_effect"]
    assert draw["arguments"] == {"effect": "cards"}
    assert draw["undoable"] is False
    assert "decline_imperial_privilege_intrigue" not in rows
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 1}]

    recall = rows["recall_agent_for_imperial_privilege"]
    assert recall["undoable"] is True
    assert rows["resolve_board_effect"]["undoable"] is False
    space = str(_obj(recall["arguments"])["space_id"])
    hand_before = manager._get(game_id).state.players[0].hand
    actions_before = manager.legal_actions(game_id, 0)

    summary = _play_raw(manager, summary, index=_int(recall["index"]))
    owner = manager._get(game_id).state.players[0]
    assert space not in owner.agent_locations
    assert owner.hand == hand_before  # the recall draws nothing
    # The placement and the recall.
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]

    rewound = manager.undo(
        game_id,
        seat=0,
        revision=_int(summary["revision"]),
        undo_count=_int(summary["undo_count"]),
    )
    assert space in manager._get(game_id).state.players[0].agent_locations
    assert manager.legal_actions(game_id, 0) == actions_before
    assert _rows(rewound["undo"]) == [{"seat": 0, "steps": 1}]

    # Recalled again, then drawn: the draw seals the window.
    rows = served()
    summary = _play_raw(
        manager,
        rewound,
        index=_int(rows["recall_agent_for_imperial_privilege"]["index"]),
    )
    summary = _play_raw(
        manager, summary, index=_int(served()["resolve_board_effect"]["index"])
    )
    assert len(manager._get(game_id).state.players[0].hand) == len(hand_before) + 1
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    with pytest.raises(SessionError, match="at most 0"):
        manager.undo(
            game_id,
            seat=0,
            revision=_int(summary["revision"]),
            undo_count=_int(summary["undo_count"]),
        )


# ------------------------------------------------ Urgent Shigawire


def test_urgent_shigawire_placement_can_be_taken_back_and_its_draw_cannot() -> None:
    """ "그 외에는 전부 나누자. 특히 카드 드로우는 나눠야하는게, 드로우 하기
    전에 버림더미 카드를 폐기하고 싶을 수 있잖아." (user ruling 2026-10-10,
    OQ-106): the draw Urgent Shigawire adds to the boosted card's Agent box
    [Urgent Shigawire card] is its own step, so the placement reveals
    nothing and stays in the seat's undo window, while the draw from the
    hidden deck closes it (OQ-010). Before the split the placement drew the
    card in the same step and could never be taken back.

    Seed 0 with Bloodlines: seat 0's first turn, given Truthtrance and a
    boost waiting from an Urgent Shigawire played earlier in the round.
    Truthtrance prints no Agent box, so the added draw is its only one. The
    state is set by hand, so the served flags and the window are checked
    but not an actual undo, which replays the log from the game's start.
    """

    truthtrance = "imperium:truthtrance:0"
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0, bloodlines=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        players=(
            replace(
                owner,
                hand=(*owner.hand, truthtrance),
                bene_gesserit_boost_pending=True,
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)

    def served() -> list[dict[str, object]]:
        return _rows(manager.legal_actions(game_id, 0)["actions"])

    placement = next(
        row
        for row in served()
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]).get("card_id") == truthtrance
        and _obj(row["arguments"]).get("space_id") == "gather_support"
    )
    assert placement["undoable"] is True
    hand_before = manager._get(game_id).state.players[0].hand

    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    placed = manager._get(game_id).state.players[0]
    assert placed.hand == tuple(c for c in hand_before if c != truthtrance)
    assert placed.bene_gesserit_boost_pending is False
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 1}]
    draw = next(
        row
        for row in served()
        if row["action_id"] == "resolve_agent_card_effect"
        and row["arguments"] == {"effect": "cards"}
    )
    assert draw["undoable"] is False

    # The draw seals the window.
    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    assert len(manager._get(game_id).state.players[0].hand) == len(hand_before)
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


# ------------------------------------------------ Cunning


def test_cunning_trash_can_be_taken_back_and_its_draw_cannot() -> None:
    """ "그 외에는 전부 나누자." (user ruling 2026-10-10, OQ-106; OQ-015 (d)):
    Cunning's "1 spice -> [draw 1] [trash a card]" [Cunning card] trashed
    first leaves the draw as its own step. The trash is the seat's own
    choice and stays in its undo window; the draw from the hidden deck
    closes it (OQ-010). Before the split the trash drew in the same step.

    Seed 0: seat 0's first turn, given Cunning and one spice by hand (the
    served flags and the window are checked, not an actual undo, which
    replays the log from the game's start).
    """

    cunning = "intrigue:cunning:0"
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        intrigue_deck=tuple(c for c in session.state.intrigue_deck if c != cunning),
        players=(
            replace(
                owner,
                intrigue_cards=(cunning,),
                resources=replace(owner.resources, spice=1),
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)

    def served() -> list[dict[str, object]]:
        return _rows(manager.legal_actions(game_id, 0)["actions"])

    play = next(
        row
        for row in served()
        if row["action_id"] == "play_intrigue"
        and row["arguments"] == {"card_id": cunning, "option": 1}
    )
    summary = _play_raw(manager, summary, index=_int(play["index"]))
    rows = served()
    rewards = next(
        row for row in rows if row["action_id"] == "resolve_intrigue_rewards"
    )
    assert rewards["undoable"] is False
    trash = next(row for row in rows if row["action_id"] == "trash_intrigue_card")
    assert trash["undoable"] is True
    hand_before = manager._get(game_id).state.players[0].hand

    summary = _play_raw(manager, summary, index=_int(trash["index"]))
    trashed = manager._get(game_id).state.players[0]
    assert len(trashed.hand) == len(hand_before) - 1  # nothing drawn
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    rows = served()
    assert [row["action_id"] for row in rows] == ["resolve_intrigue_rewards"]
    assert rows[0]["undoable"] is False

    summary = _play_raw(manager, summary, index=_int(rows[0]["index"]))
    assert len(manager._get(game_id).state.players[0].hand) == len(hand_before)
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


# ------------------------------------------------ Arrakis Planetologist


def test_planetologist_summon_can_be_taken_back_and_its_intrigue_cannot() -> None:
    """ "그 외에는 전부 나누자." (user ruling 2026-10-10, OQ-106): Liet Kynes'
    replacement "[trash a card] [1 spice] [1 Intrigue]" [Liet Kynes card]
    holds its Intrigue card as its own step, so the summon at a Maker space
    reveals nothing and stays in the seat's undo window; the Intrigue draw
    closes it (OQ-010). Before the split the summon drew it at once.

    Seed 0 with Bloodlines: seat 0's first turn, given Liet Kynes, Maker
    hooks and a water by hand (the served flags and the window are checked,
    not an actual undo, which replays the log from the game's start).
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0, bloodlines=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        players=(
            replace(
                owner,
                leader_id="liet_kynes",
                leader_face_id="liet_kynes",
                maker_hooks=True,
                resources=replace(owner.resources, water=1),
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)

    def served() -> list[dict[str, object]]:
        return _rows(manager.legal_actions(game_id, 0)["actions"])

    placement = next(
        row
        for row in served()
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]).get("space_id") == "hagga_basin"
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    summon = next(
        row for row in served() if row["action_id"] == "summon_maker_sandworms"
    )
    assert summon["undoable"] is True
    intrigue_before = manager._get(game_id).state.players[0].intrigue_cards

    summary = _play_raw(manager, summary, index=_int(summon["index"]))
    assert manager._get(game_id).state.players[0].intrigue_cards == intrigue_before
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    rows = served()
    draw = next(
        row for row in rows if row["action_id"] == "draw_planetologist_intrigue"
    )
    assert draw["undoable"] is False
    # The trash waits beside the draw as rows on the Agent turn, with no
    # refusal (cleanup-2b, OQ-095 (2)); trashing a card reveals nothing, so it
    # stays inside the undo window too.
    assert "decline_optional_trash" not in {row["action_id"] for row in rows}
    trash = [row for row in rows if row["action_id"] == "trash_optional_card"]
    assert trash
    assert all(row["undoable"] is True for row in trash)

    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    held = manager._get(game_id).state.players[0].intrigue_cards
    assert len(held) == len(intrigue_before) + 1
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


# ------------------------------------------------ arrow costs (OQ-027 (b))


def _served(manager: GameSessionManager, game_id: str) -> list[dict[str, object]]:
    return _rows(manager.legal_actions(game_id, 0)["actions"])


def test_piter_troop_cost_can_be_taken_back_and_its_draw_cannot() -> None:
    """ "그 외에는 전부 나누자." (user ruling 2026-10-10, OQ-106): Piter,
    Genius Advisor's "Lose a troop -> draw two cards and Research" pays the
    troop as one step and arms the rewards as their own steps (OQ-027 (b)),
    so the cost stays in the seat's undo window and the draw closes it
    (OQ-010). Before, the cost drew the cards in the same step.

    Seed 0 with Immortality and promo cards: seat 0's first turn, given
    Piter by hand (served flags and the window, not an actual undo, which
    replays the log from the game's start).
    """

    piter = "tleilaxu:piter_genius_advisor:0"
    manager = GameSessionManager()
    summary = manager.create_game(
        HUMAN_FIRST, game_seed=0, immortality=True, promo_cards=True
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        tleilaxu_deck=tuple(c for c in session.state.tleilaxu_deck if c != piter),
        tleilaxu_row=tuple(c for c in session.state.tleilaxu_row if c != piter),
        players=(
            replace(owner, hand=(*owner.hand, piter)),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)
    placement = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]).get("card_id") == piter
        and _obj(row["arguments"]).get("space_id") == "assembly_hall"
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    cost = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "lose_agent_card_troop"
        and row["arguments"] == {"zone": "garrison"}
    )
    assert cost["undoable"] is True
    hand_before = manager._get(game_id).state.players[0].hand

    summary = _play_raw(manager, summary, index=_int(cost["index"]))
    assert manager._get(game_id).state.players[0].hand == hand_before
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    draw = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "resolve_agent_card_effect"
        and row["arguments"] == {"effect": "cards"}
    )
    assert draw["undoable"] is False

    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    assert len(manager._get(game_id).state.players[0].hand) == len(hand_before) + 2
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


def test_reverse_engineering_tile_can_be_taken_back_and_its_draws_cannot() -> None:
    """Kota Odax's Reverse Engineering "trash one of your Tech tiles ->
    [Intrigue] [draw 1]" [Kota Odax of Ix card] pays the tile as one step
    and leaves the two rewards as their own steps (user ruling 2026-10-10,
    OQ-106), so the tile stays in the seat's undo window and either draw
    closes it (OQ-010).

    Seed 0 with Bloodlines and the Tech Module: seat 0's first turn, given
    Kota Odax and a Tech tile by hand (served flags and the window only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(
        HUMAN_FIRST, game_seed=0, bloodlines=True, tech_module=True
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    signet = "player:0:starter:signet_ring:0"
    session.state = replace(
        session.state,
        tech_stacks=tuple(
            tuple(t for t in stack if t != "glowglobes")
            for stack in session.state.tech_stacks
        ),
        players=(
            replace(
                owner,
                leader_id="kota_odax_of_ix",
                leader_face_id="kota_odax_of_ix",
                tech_ids=("glowglobes",),
                hand=(signet, *(c for c in owner.hand if c != signet)),
                deck=tuple(c for c in owner.deck if c != signet),
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)
    placement = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]).get("card_id") == signet
        and _obj(row["arguments"]).get("space_id") == "assembly_hall"
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    trash = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "trash_leader_tech"
    )
    assert trash["undoable"] is True
    summary = _play_raw(manager, summary, index=_int(trash["index"]))
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    rewards = [
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "resolve_agent_card_effect"
    ]
    assert [row["arguments"] for row in rewards] == [
        {"effect": "intrigue"},
        {"effect": "cards"},
    ]
    assert all(row["undoable"] is False for row in rewards)
    summary = _play_raw(manager, summary, index=_int(rewards[1]["index"]))
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


# ------------------------------------------------ triggered draws (OQ-106)


def _replay_from(
    monkeypatch: pytest.MonkeyPatch, session: GameSession, start: GameState
) -> None:
    """Make an undo replay from ``start``, a position set up by hand.

    The server rebuilds an undone state by replaying the session's steps
    from ``engine.reset`` (``_state_after``); a test that edited the opening
    state by hand has that reset return its edit, so the undo is real.
    """

    assert not session.steps
    monkeypatch.setattr(session.engine, "reset", lambda config, seed: start)


def test_influence_choice_reaching_a_bonus_can_be_taken_back_and_its_card_cannot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "그 외에는 전부 나누자." (user ruling 2026-10-10, OQ-106): a draw a
    trigger earns is not drawn inside the step that triggered it. Change
    Allegiances' "3 spice -> +1 Influence" [Change Allegiances card] raised
    to Bene Gesserit 4 earns the track's Intrigue card [Main p. 7]; the
    Faction choice stays in the seat's undo window, and the card is the
    seat's own ``draw_owed_intrigue``, which closes it (OQ-010). It is the
    very next step, before the card's own finish: "faction bonuses (such as
    drawing an Intrigue on the BG track) may interrupt this flow" (Message
    from designer; user decision 2026-10-10, "가 로 가자"). Before the split
    the choice drew the card in the same step.

    Seed 0: seat 0's first turn, given the card, three spice and Bene
    Gesserit 3 by hand; the undo replays from that position.
    """

    card = "intrigue:change_allegiances:0"
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        intrigue_deck=tuple(c for c in session.state.intrigue_deck if c != card),
        players=(
            replace(
                owner,
                intrigue_cards=(card,),
                resources=replace(owner.resources, spice=3),
                influence=replace(owner.influence, bene_gesserit=3),
            ),
            *session.state.players[1:],
        ),
    )
    _replay_from(monkeypatch, session, session.state)
    summary = manager.summary(game_id)
    play = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "play_intrigue"
        and _obj(row["arguments"]).get("card_id") == card
    )
    summary = _play_raw(manager, summary, index=_int(play["index"]))
    line = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "use_intrigue_effect"
        and _obj(row["arguments"]).get("section") == 1
    )
    summary = _play_raw(manager, summary, index=_int(line["index"]))

    def choose(summary: JsonObject) -> JsonObject:
        choice = next(
            row
            for row in _served(manager, game_id)
            if row["action_id"] == "choose_intrigue_faction"
            and _obj(row["arguments"]).get("faction") == "bene_gesserit"
        )
        assert choice["undoable"] is True
        return _play_raw(manager, summary, index=_int(choice["index"]))

    before = manager._get(game_id).state
    summary = choose(summary)
    chosen = manager._get(game_id).state.players[0]
    assert chosen.influence.bene_gesserit == 4
    assert chosen.intrigue_cards == before.players[0].intrigue_cards  # no draw
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 3}]
    rows = _served(manager, game_id)
    # The draw is all the seat may do now: not the card's finish, not the
    # turn's end.
    assert [row["action_id"] for row in rows] == ["draw_owed_intrigue"]
    assert rows[0]["undoable"] is False
    assert rows[0]["detail"] == "Bene Gesserit Influence 4"

    # The Faction choice is taken back to the exact position before it.
    summary = manager.undo(game_id, seat=0, revision=_int(summary["revision"]))
    assert manager._get(game_id).state == before
    summary = choose(summary)

    (draw,) = _served(manager, game_id)
    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    drawn = manager._get(game_id).state.players[0]
    assert len(drawn.intrigue_cards) == len(before.players[0].intrigue_cards) + 1
    assert drawn.owed_draws == ()
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    assert any(
        row["action_id"] == "finish_intrigue_effects"
        for row in _served(manager, game_id)
    )


def test_research_direction_reaching_a_tleilaxu_intrigue_can_be_taken_back() -> None:
    """A research space's Tleilaxu icon [Immortality pp. 6, 16] that moves
    the Tleilaxu token onto an Intrigue space ("칸 2: Intrigue 1"
    [Immortality pp. 4, 7]) holds that card as the seat's own step (user
    ruling 2026-10-10, OQ-106), so the public direction choice stays in the
    undo window and only the draw closes it (OQ-010).

    Seed 0 with Immortality: seat 0's first turn, its research token on
    c1r3 and Tleilaxu token on 1, Reconnaissance and two water given by hand
    for the Research Station (served flags and the window only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0, immortality=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    city = next(card for card in owner.deck if ":reconnaissance:" in card)
    session.state = replace(
        session.state,
        players=(
            replace(
                owner,
                research_space="c1r3",
                tleilaxu_space=1,
                resources=replace(owner.resources, water=2),
                hand=(city, *owner.hand),
                deck=tuple(card for card in owner.deck if card != city),
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)
    placement = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]) == {"card_id": city, "space_id": "research_station"}
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    research = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "resolve_board_effect"
        and _obj(row["arguments"]) == {"effect": "research"}
    )
    summary = _play_raw(manager, summary, index=_int(research["index"]))
    direction = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "choose_research_space"
        and _obj(row["arguments"]) == {"space_id": "c2r4"}
    )
    assert direction["undoable"] is True
    summary = _play_raw(manager, summary, index=_int(direction["index"]))
    moved = manager._get(game_id).state.players[0]
    assert moved.tleilaxu_space == 2 and moved.intrigue_cards == ()
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 3}]
    draw = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "draw_owed_intrigue"
    )
    assert draw["undoable"] is False
    assert draw["detail"] == "Tleilaxu track"

    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    assert len(manager._get(game_id).state.players[0].intrigue_cards) == 1
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


def test_trashing_sardaukar_soldier_can_be_taken_back_and_its_card_cannot() -> None:
    """Sardaukar Soldier draws an Intrigue card "when trashed" [card face]:
    a separate printed trigger, so the trash choice (here Desert Tactics'
    "trash a card" [Board Guide p. 1]) stays undoable and the card waits as
    the seat's own step (user ruling 2026-10-10, OQ-106; OQ-010).

    Seed 0: seat 0's first turn, a Sardaukar Soldier put in its discard pile
    by hand (served flags and the window only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    soldier = next(
        card for card in session.state.imperium_deck if ":sardaukar_soldier:" in card
    )
    session.state = replace(
        session.state,
        imperium_deck=tuple(c for c in session.state.imperium_deck if c != soldier),
        players=(replace(owner, discard_pile=(soldier,)), *session.state.players[1:]),
    )
    summary = manager.summary(game_id)
    placement = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]).get("space_id") == "desert_tactics"
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    trash = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "trash_card_for_desert_tactics"
        and _obj(row["arguments"]).get("card_id") == soldier
    )
    assert trash["undoable"] is True
    summary = _play_raw(manager, summary, index=_int(trash["index"]))
    trashed = manager._get(game_id).state.players[0]
    assert trashed.trashed == (soldier,) and trashed.intrigue_cards == ()
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    draw = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "draw_owed_intrigue"
    )
    assert draw["undoable"] is False
    assert draw["detail"] == "Sardaukar Soldier"

    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    assert len(manager._get(game_id).state.players[0].intrigue_cards) == 1
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


def test_a_harvest_can_be_taken_back_before_its_hungry_for_spice_card() -> None:
    """Steersman Y'rkoon's Hungry for Spice ("Whenever you gain 3 or more
    spice in a single turn: draw a card" [Steersman Y'rkoon card]) holds its
    card as his own ``draw_owed_card`` step (user ruling 2026-10-10, OQ-106:
    "특히 카드 드로우는 나눠야하는게"), so the Deep Desert harvest that
    earned it stays in the undo window and only the draw closes it (OQ-010).

    Seed 0 with Bloodlines: seat 0's first turn, made Y'rkoon with Dune and
    three water by hand (served flags and the window only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0, bloodlines=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    desert = next(
        card
        for card in (*owner.hand, *owner.deck)
        if ":dune_the_desert_planet:" in card
    )
    session.state = replace(
        session.state,
        players=(
            replace(
                owner,
                leader_id="steersman_y_rkoon",
                leader_face_id="steersman_y_rkoon",
                hand=(desert, *(c for c in owner.hand if c != desert)),
                deck=tuple(c for c in owner.deck if c != desert),
                resources=replace(owner.resources, water=3),
                spice_at_turn_start=owner.resources.spice,
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)
    placement = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]) == {"card_id": desert, "space_id": "deep_desert"}
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    spice = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "harvest_maker_spice"
    )
    assert spice["undoable"] is True
    hand_before = manager._get(game_id).state.players[0].hand
    summary = _play_raw(manager, summary, index=_int(spice["index"]))
    seat = manager._get(game_id).state.players[0]
    assert seat.hand == hand_before  # nothing drawn yet
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    rows = _served(manager, game_id)
    assert all(row["action_id"] != "finish_agent_turn" for row in rows)
    draw = next(row for row in rows if row["action_id"] == "draw_owed_card")
    assert draw["undoable"] is False
    assert draw["detail"] == "Hungry for Spice"

    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []
    seat = manager._get(game_id).state.players[0]
    assert len(seat.hand) == len(hand_before) + 1 and seat.owed_draws == ()


def test_a_contract_completion_can_be_taken_back_before_its_transports_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CHOAM Transports: "When you complete a contract: draw a card" [Tech
    tile]; "The card draw from CHOAM Transports is triggered as soon as the
    contract is completed and can't be deferred." (Message from designer;
    docs/rules/designer-rulings-audit.md). The card is the seat's own
    ``draw_owed_card`` step, the one right after the completion with nothing
    else of the seat's in between (user decision 2026-10-10, OQ-106: "가 로
    가자"), so the completion stays in the undo window and the draw closes
    it (OQ-010). Before, the completion drew the card in its own step.

    Seed 1 with CHOAM, Bloodlines and Tech: seat 0's first turn, given CHOAM
    Transports and the Arrakeen I Contract by hand; the undo replays from
    that position.
    """

    contract = "contract:arrakeen_i"
    manager = GameSessionManager()
    summary = manager.create_game(
        HUMAN_FIRST, game_seed=1, choam_module=True, bloodlines=True, tech_module=True
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    state = session.state
    session.state = replace(
        state,
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c != contract
        ),
        contract_bank=tuple(c for c in state.contract_bank if c != contract),
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile != "choam_transports")
            for stack in state.tech_stacks
        ),
        players=(
            replace(
                state.players[0],
                tech_ids=("choam_transports",),
                active_contract_ids=(contract,),
            ),
            *state.players[1:],
        ),
    )
    _replay_from(monkeypatch, session, session.state)
    summary = manager.summary(game_id)
    placement = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "agent_turn"
        and _obj(row["arguments"]).get("space_id") == "arrakeen"
    )
    summary = _play_raw(manager, summary, index=_int(placement["index"]))
    complete = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "complete_contract"
    )
    assert complete["undoable"] is True
    before = manager._get(game_id).state
    summary = _play_raw(manager, summary, index=_int(complete["index"]))
    seat = manager._get(game_id).state.players[0]
    assert seat.completed_contract_ids == (contract,)
    assert seat.hand == before.players[0].hand  # nothing drawn yet
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 2}]
    rows = _served(manager, game_id)
    assert [row["action_id"] for row in rows] == ["draw_owed_card"]
    assert rows[0]["undoable"] is False
    assert rows[0]["detail"] == "CHOAM Transports"
    assert rows[0]["detail_ko"] == "초암 수송선"

    summary = manager.undo(game_id, seat=0, revision=_int(summary["revision"]))
    assert manager._get(game_id).state == before

    complete = next(
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "complete_contract"
    )
    summary = _play_raw(manager, summary, index=_int(complete["index"]))
    (draw,) = _served(manager, game_id)
    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    seat = manager._get(game_id).state.players[0]
    assert len(seat.hand) == len(before.players[0].hand) + 1
    assert seat.owed_draws == ()
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


def test_muad_dibs_reveal_can_be_taken_back_before_its_intrigue_card() -> None:
    """Muad'Dib's Unpredictable Foe ("Reveal Turn: If you have one or more
    sandworms in the Conflict: [Intrigue 1 draw]." [Muad'Dib card]) puts its
    card on the Reveal's pending gains as his own ``draw_reveal_intrigue``
    (OQ-045; user ruling 2026-10-10, OQ-106), so the Reveal itself stays in
    the undo window, where it used to draw the card and close it (OQ-010).

    Seed 0: seat 0's first turn, made Muad'Dib with a sandworm in the
    Conflict by hand (served flags and the window only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        players=(
            replace(
                owner,
                leader_id="muad_dib",
                leader_face_id="muad_dib",
                sandworms_conflict=1,
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)
    reveal = next(
        row for row in _served(manager, game_id) if row["action_id"] == "reveal_turn"
    )
    assert reveal["undoable"] is True
    intrigue_before = manager._get(game_id).state.players[0].intrigue_cards
    summary = _play_raw(manager, summary, index=_int(reveal["index"]))
    assert manager._get(game_id).state.players[0].intrigue_cards == intrigue_before
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 1}]
    rows = _served(manager, game_id)
    assert all(row["action_id"] != "finish_reveal" for row in rows)
    draw = next(row for row in rows if row["action_id"] == "draw_reveal_intrigue")
    assert draw["undoable"] is False

    summary = _play_raw(manager, summary, index=_int(draw["index"]))
    assert len(manager._get(game_id).state.players[0].intrigue_cards) == (
        len(intrigue_before) + 1
    )
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


# ------------------------------------------------ Arrakeen Scouts lines (OQ-106)

_ENGINE = UprisingRulesEngine()


def _scouts_draw(state: GameState, item_id: str) -> GameState:
    """Answer the Scouts step's draws until ``item_id`` is revealed."""

    while True:
        state = _advance_automatic(RuleResult(state=state)).state
        frame = state.decision_stack[-1]
        if frame.kind != FrameKind.SCOUTS_DRAW:
            return state
        decision = frame.decision
        assert isinstance(decision, ChanceDecision)
        wanted = [o for o in decision.options if o.split("#")[0] == item_id]
        value = wanted[0] if wanted else decision.options[0]
        state = _ENGINE.apply(
            state, ChanceOutcome(decision.decision_id, (value,))
        ).state
        if wanted:
            return state


def _scouts_act(
    state: GameState, action_id: str, **arguments: str | int
) -> GameState:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    action = DomainAction(
        action_id=action_id,
        actor=decision.owner,
        arguments=tuple(sorted(arguments.items())),
    )
    legal = _ENGINE.legal_actions(state, decision.owner)
    assert action in legal, (action, legal)
    return _ENGINE.apply(state, action, legal_actions=legal).state


def test_leverage_faction_can_be_taken_back_and_its_intrigue_cannot() -> None:
    """ "그 외에는 전부 나누자." (user ruling 2026-10-10, OQ-106): Leverage's
    "Spy 2 회수 → 원하는 Faction Influence +1 + Intrigue 1장"
    (docs/rules/arrakeen-scouts.md 4) no longer draws its card in the
    Faction step, so the choice stays in the seat's undo window and the
    line's own ``scouts_rewards_first`` draws and closes it (OQ-010).

    Seed 0 with Arrakeen Scouts: seat 0's first turn, given two posted Spies,
    Solari and Leverage on the display by hand; the visit, the join and the
    recalls are played through the server.
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0, arrakeen_scouts=True)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    owner = session.state.players[0]
    session.state = replace(
        session.state,
        scouts_subcommittees=(
            *session.state.scouts_subcommittees[:-1],
            "leverage",
        ),
        players=(
            replace(
                owner,
                resources=Resources(solari=10, spice=5, water=1),
                spies_supply=1,
                spy_post_ids=("arrakis-deep-desert", "arrakis-hagga-basin"),
            ),
            *session.state.players[1:],
        ),
    )
    summary = manager.summary(game_id)

    def first(action_id: str, **arguments: object) -> dict[str, object]:
        return next(
            row
            for row in _served(manager, game_id)
            if row["action_id"] == action_id
            and all(_obj(row["arguments"]).get(k) == v for k, v in arguments.items())
        )

    steps: tuple[tuple[str, dict[str, object]], ...] = (
        (
            "agent_turn",
            {"card_id": "player:0:starter:dagger:0", "space_id": "high_council"},
        ),
        ("resolve_board_effect", {"effect": "high_council"}),
        ("choose_subcommittee", {}),
        ("join_subcommittee", {"subcommittee_id": "leverage"}),
        ("scouts_recall_spy", {}),
        ("scouts_recall_spy", {}),
    )
    for action_id, arguments in steps:
        row = first(action_id, **arguments)
        summary = _play_raw(manager, summary, index=_int(row["index"]))
    choice = first("scouts_choose_faction", faction="emperor")
    assert choice["undoable"] is True
    intrigue_before = manager._get(game_id).state.players[0].intrigue_cards
    summary = _play_raw(manager, summary, index=_int(choice["index"]))
    assert manager._get(game_id).state.players[0].intrigue_cards == intrigue_before
    assert _rows(summary["undo"]) == [{"seat": 0, "steps": 7}]
    rows = _served(manager, game_id)
    assert [row["action_id"] for row in rows] == ["scouts_rewards_first"]
    assert rows[0]["undoable"] is False

    summary = _play_raw(manager, summary, index=_int(rows[0]["index"]))
    assert len(manager._get(game_id).state.players[0].intrigue_cards) == (
        len(intrigue_before) + 1
    )
    assert [row for row in _rows(summary["undo"]) if row["seat"] == 0] == []


def _scouts_step(
    manager: GameSessionManager, game_id: str, round_number: int, **fields: object
) -> GameState:
    """The session's state turned into ``round_number``'s Scouts step about
    to draw, seat 0 the First Player and every seat rich."""

    state = manager._get(game_id).state
    rich = Resources(solari=6, spice=6, water=2)
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        players=tuple(replace(p, resources=rich) for p in state.players),
        decision_stack=(),
        scouts_opening=True,
        **fields,  # type: ignore[arg-type]
    )


def test_water_discipline_trash_can_be_taken_back_and_its_draw_cannot() -> None:
    """Water Discipline's "물 1 → 카드 1장 trash + 카드 1장 draw"
    (docs/rules/arrakeen-scouts.md 6, OQ-100): outside the turns the trash
    used to draw the card in the same step, so it was served irreversible and
    held only by the browser's "확정 ▶". Now the trash is undoable and the
    draw is its own step, served irreversible (user ruling 2026-10-10,
    OQ-106).

    Seed 0 with Arrakeen Scouts, made round 4's Scouts step with Water
    Discipline drawn by hand (served flags only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=0, arrakeen_scouts=True)
    game_id = str(summary["game_id"])
    state = _scouts_draw(_scouts_step(manager, game_id, 4), "water_discipline")
    state = _scouts_act(state, "scouts_choose_option", option=0)
    session = manager._get(game_id)
    session.state = state
    rows = _served(manager, game_id)
    trashes = [row for row in rows if row["action_id"] == "trash_optional_card"]
    assert trashes and all(row["undoable"] is True for row in trashes)
    assert all(row["sent_by_turn_end"] is False for row in trashes)
    decline = next(row for row in rows if row["action_id"] == "decline_optional_trash")
    assert decline["undoable"] is True

    card = str(_obj(trashes[0]["arguments"])["card_id"])
    session.state = _scouts_act(state, "trash_optional_card", card_id=card)
    rows = _served(manager, game_id)
    assert [row["action_id"] for row in rows] == ["scouts_rewards_first"]
    assert rows[0]["undoable"] is False
    assert rows[0]["sent_by_turn_end"] is True


def test_competitive_study_direction_can_be_taken_back_before_the_next_card() -> (
    None
):
    """Competitive Study's late second place, researching past the second
    genetic marker, draws a card [Immortality p. 6]; that card came out in
    the first place's Research-direction step, so the direction was served
    irreversible. A pause now stands before the second place's reward
    (rules/pauses.py; user ruling 2026-10-10, OQ-106), and the direction is
    served undoable, held by the server until seat 0's press (OQ-103).

    Seed 0 with Arrakeen Scouts and Immortality, made round 8's Scouts step
    with the late Competitive Study drawn by hand (served flags only).
    """

    manager = GameSessionManager()
    summary = manager.create_game(
        HUMAN_FIRST, game_seed=0, arrakeen_scouts=True, immortality=True
    )
    game_id = str(summary["game_id"])
    state = _scouts_step(
        manager,
        game_id,
        8,
        scouts_mid_auction_round=5,
        scouts_late_auction_round=8,
        scouts_secrets_round=8,
    )
    research = {0: "c1r3", 2: "c8r2"}
    state = replace(
        state,
        players=tuple(
            replace(p, research_space=research.get(p.player_id, p.research_space))
            for p in state.players
        ),
    )
    state = _scouts_draw(state, "competitive_study_late")
    bids = {0: 4, 1: 0, 2: 2, 3: 0}
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_BID:
        decision = state.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        state = _scouts_act(state, "scouts_bid", count=bids[decision.owner])
        state = _scouts_act(state, "confirm_scouts_bid")
    assert state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    manager._get(game_id).state = state
    rows = [
        row
        for row in _served(manager, game_id)
        if row["action_id"] == "choose_research_space"
    ]
    assert len(rows) == 2
    assert all(row["undoable"] is True for row in rows)
    assert all(row["sent_by_turn_end"] is False for row in rows)
