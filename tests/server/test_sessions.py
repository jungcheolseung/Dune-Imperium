"""Tests for the framework-neutral game sessions of the play server."""

import json
import logging
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

ALL_AI = ("heuristic", "random", "heuristic", "random")
HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def test_an_all_ai_game_finishes_during_creation() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(ALL_AI, game_seed=11)

    assert summary["finished"] is True
    assert summary["phase"] == "finished"
    assert summary["decision"] is None
    standings = _rows(summary["standings"])
    assert [entry["rank"] for entry in standings] == [1, 2, 3, 4]
    json.dumps(summary)


def test_the_same_seed_reproduces_an_all_ai_game() -> None:
    manager = GameSessionManager()

    first = manager.create_game(ALL_AI, game_seed=12)
    second = manager.create_game(ALL_AI, game_seed=12)

    assert first["standings"] == second["standings"]
    assert first["revision"] == second["revision"]


def test_a_human_game_pauses_on_the_human_decision() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(HUMAN_FIRST, game_seed=13)

    assert summary["finished"] is False
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["owner_is_human"] is True
    assert manager.summary(_text(summary["game_id"])) == summary


def test_only_human_seats_expose_views_and_actions() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    view = manager.view(game_id, 0)
    assert view["player"] == 0
    assert view["private"] is not None
    json.dumps(view)

    listing = manager.legal_actions(game_id, 0)
    assert listing["revision"] == summary["revision"]
    actions = _rows(listing["actions"])
    assert actions
    assert [entry["index"] for entry in actions] == list(range(len(actions)))
    json.dumps(listing)

    with pytest.raises(SeatAccessError):
        manager.view(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.legal_actions(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.view(game_id, 9)


def test_legal_actions_describe_the_board_icon_they_resolve() -> None:
    # Seat 0 opens seed 21 by sending a Dagger to Assembly Hall; the space's
    # single Intrigue icon is then offered with its printed effect text.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = _text(summary["game_id"])
    placements = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert all(entry["detail"] is None for entry in placements)
    assert all(entry["detail_ko"] is None for entry in placements)
    assert _obj(placements[0]["arguments"])["space_id"] == "assembly_hall"

    summary = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=0
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [
        (entry["action_id"], _obj(entry["arguments"])["effect"], entry["detail"])
        for entry in actions
        if entry["action_id"] == "resolve_board_effect"
    ] == [("resolve_board_effect", "intrigue", "Draw 1 Intrigue card")]
    # detail_ko: display.spaces.board_effect_action_text_ko (Step K4) renders
    # the same automatic-effect table English draws from, as its Korean twin
    # (display.spaces.automatic_effect_texts_ko).
    assert [
        entry["detail_ko"]
        for entry in actions
        if entry["action_id"] == "resolve_board_effect"
    ] == ["{intrigue:1}"]


def _play_until(
    manager: GameSessionManager, game_id: str, wanted: str, prefer: tuple[str, ...]
) -> list[dict[str, object]]:
    """Play seat 0 until it is offered ``wanted``; return that action list.

    A placement on one of the ``prefer`` spaces is taken when there is one,
    otherwise the first legal action.
    """

    for _ in range(400):
        summary = manager.summary(game_id)
        assert not summary["finished"], f"the game ended before {wanted}"
        if summary.get("confirmation") == 0:
            manager.confirm_turn(game_id, 0, _int(summary["revision"]))
            continue
        actions = _rows(manager.legal_actions(game_id, 0)["actions"])
        if any(entry["action_id"] == wanted for entry in actions):
            return actions
        chosen = next(
            (
                entry
                for entry in actions
                if entry["action_id"] == "agent_turn"
                and _obj(entry["arguments"]).get("space_id") in prefer
            ),
            actions[0],
        )
        manager.apply_action(
            game_id,
            seat=0,
            revision=_int(summary["revision"]),
            index=_int(chosen["index"]),
        )
    raise AssertionError(f"{wanted} was never offered")


def test_legal_actions_preview_the_strength_a_step_leads_to() -> None:
    # The preview is the engine's own figure from the dry run, not "2 per
    # troop" [Main p. 10] worked out in the browser: it is the running
    # strength the seat would have after the step, and it is only given
    # when the step changes it.
    manager = GameSessionManager()
    game_id = _text(manager.create_game(HUMAN_FIRST, game_seed=11)["game_id"])
    combat = ("hagga_basin", "imperial_basin", "arrakeen", "spice_refinery")
    actions = _play_until(manager, game_id, "deploy_troops", combat)
    before = _int(_rows(manager.view(game_id, 0)["players"])[0]["combat_strength"])
    deploys = [entry for entry in actions if entry["action_id"] == "deploy_troops"]
    assert deploys
    for entry in deploys:
        count = _int(_obj(entry["arguments"])["count"])
        assert entry["strength_after"] == before + 2 * count
    others = [entry for entry in actions if entry["action_id"] != "deploy_troops"]
    assert others and all(entry["strength_after"] is None for entry in others)

    # Taking the step leads exactly there, and taking it back is previewed too.
    chosen = deploys[-1]
    summary = manager.summary(game_id)
    manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=_int(chosen["index"])
    )
    after = _int(_rows(manager.view(game_id, 0)["players"])[0]["combat_strength"])
    assert after == chosen["strength_after"]
    withdraws = [
        entry
        for entry in _rows(manager.legal_actions(game_id, 0)["actions"])
        if entry["action_id"] == "withdraw_troops"
    ]
    assert withdraws
    for entry in withdraws:
        count = _int(_obj(entry["arguments"])["count"])
        assert entry["strength_after"] == after - 2 * count


def test_a_reveal_tells_the_table_the_persuasion_still_unspent() -> None:
    manager = GameSessionManager()
    game_id = _text(manager.create_game(HUMAN_FIRST, game_seed=11)["game_id"])
    assert "persuasion" not in _obj(manager.summary(game_id)["decision"])

    # Reveal at once: the starting hand's Persuasion, then less by each
    # card's cost as it is bought.
    summary = manager.summary(game_id)
    reveal = next(
        entry
        for entry in _rows(manager.legal_actions(game_id, 0)["actions"])
        if entry["action_id"] == "reveal_turn"
    )
    summary = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=_int(reveal["index"])
    )
    decision = _obj(summary["decision"])
    assert decision["kind"] == "reveal"
    unspent = _int(decision["persuasion"])
    assert unspent > 0

    buys = [
        entry
        for entry in _rows(manager.legal_actions(game_id, 0)["actions"])
        if entry["action_id"] == "acquire_reserve"
    ]
    assert buys
    summary = manager.apply_action(
        game_id,
        seat=0,
        revision=_int(summary["revision"]),
        index=_int(buys[0]["index"]),
    )
    # Prepare the Way costs 2 Persuasion.
    assert _obj(buys[0]["arguments"])["card_id"] == "prepare_the_way"
    assert _obj(summary["decision"])["persuasion"] == unspent - 2


def test_the_reveal_step_previews_what_the_hand_is_worth_right_now() -> None:
    # "지금 공개하면 Persuasion N": a Reveal sums the revealed Persuasion and
    # swords as it starts [Main p. 12], so the dry run of ``reveal_turn``
    # already holds both figures. Only that step carries the preview.
    manager = GameSessionManager()
    game_id = _text(manager.create_game(HUMAN_FIRST, game_seed=11)["game_id"])
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    reveal = next(entry for entry in actions if entry["action_id"] == "reveal_turn")
    preview = _obj(reveal["reveal_preview"])
    assert all(
        "reveal_preview" not in entry
        for entry in actions
        if entry["action_id"] != "reveal_turn"
    )

    # Taking the step opens the Reveal with exactly that Persuasion and
    # leaves the seat at exactly that strength (no units in the Conflict
    # yet, so the swords do not count: 0).
    summary = manager.summary(game_id)
    summary = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=_int(reveal["index"])
    )
    assert _obj(summary["decision"])["persuasion"] == preview["persuasion"]
    assert _int(preview["persuasion"]) > 0
    own = _rows(manager.view(game_id, 0)["players"])[0]
    assert own["combat_strength"] == preview["strength"] == 0

    # With units in the Conflict the revealed swords count at once.
    other = GameSessionManager()
    other_id = _text(other.create_game(HUMAN_FIRST, game_seed=11)["game_id"])
    combat = ("hagga_basin", "imperial_basin", "arrakeen", "spice_refinery")
    deploys = [
        entry
        for entry in _play_until(other, other_id, "deploy_troops", combat)
        if entry["action_id"] == "deploy_troops"
    ]
    summary = other.summary(other_id)
    other.apply_action(
        other_id,
        seat=0,
        revision=_int(summary["revision"]),
        index=_int(deploys[-1]["index"]),
    )
    later = _play_until(other, other_id, "reveal_turn", ())
    later_reveal = next(e for e in later if e["action_id"] == "reveal_turn")
    later_preview = _obj(later_reveal["reveal_preview"])
    summary = other.summary(other_id)
    summary = other.apply_action(
        other_id,
        seat=0,
        revision=_int(summary["revision"]),
        index=_int(later_reveal["index"]),
    )
    assert _obj(summary["decision"])["persuasion"] == later_preview["persuasion"]
    own = _rows(other.view(other_id, 0)["players"])[0]
    assert own["combat_strength"] == later_preview["strength"]


def test_apply_guards_revision_owner_and_index() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    revision = _int(summary["revision"])

    with pytest.raises(StaleRevisionError):
        manager.apply_action(game_id, seat=0, revision=revision + 1, index=0)
    with pytest.raises(SessionError, match="out of range"):
        manager.apply_action(game_id, seat=0, revision=revision, index=999)
    with pytest.raises(SeatAccessError):
        manager.apply_action(game_id, seat=1, revision=revision, index=0)

    advanced = manager.apply_action(game_id, seat=0, revision=revision, index=0)
    assert advanced["revision"] != revision
    if not advanced["finished"]:
        # Either the seat still decides, or its turn ended and the hand-over
        # waits for confirmation while the steps are undoable.
        assert _obj(advanced["decision"])["owner"] == 0 or advanced["confirmation"] == 0


def test_a_human_game_can_be_played_to_the_end() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])

    for _ in range(2_000):
        if summary["finished"]:
            break
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
            continue
        summary = manager.apply_action(
            game_id,
            seat=0,
            revision=_int(summary["revision"]),
            index=0,
        )
    assert summary["finished"] is True
    standings = _rows(summary["standings"])
    assert sorted(_int(entry["rank"]) for entry in standings) == [1, 2, 3, 4]


def test_a_leader_draft_game_starts_on_the_pick_frame() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(
        ("human", "human", "human", "human"),
        leader_draft=True,
        game_seed=15,
    )

    decision = _obj(summary["decision"])
    assert decision["kind"] == "leader_draft"
    listing = manager.legal_actions(_text(summary["game_id"]), _int(decision["owner"]))
    actions = _rows(listing["actions"])
    assert len(actions) == 6
    assert {entry["action_id"] for entry in actions} == {"pick_leader"}


def test_registry_agents_take_seats_and_search_agents_get_the_state() -> None:
    from dune_imperium.agents import RolloutAgent

    manager = GameSessionManager()
    seats = ("human", "rollout", "heuristic", "random")

    summary = manager.create_game(seats, game_seed=14)

    assert summary["seats"] == list(seats)
    assert _obj(summary["decision"])["owner"] == 0
    session = manager._sessions[_text(summary["game_id"])]
    assert isinstance(session.agents[1], RolloutAgent)
    # The same seed reproduces the search agent's decisions too.
    again = manager.create_game(seats, game_seed=14)
    assert again["revision"] == summary["revision"]
    assert again["decision"] == summary["decision"]


def test_a_rollout_seat_acts_between_human_turns() -> None:
    manager = GameSessionManager()
    seats = ("human", "rollout", "heuristic", "random")
    summary = manager.create_game(seats, game_seed=15)
    game_id = _text(summary["game_id"])
    human_steps = 0
    # Play seat 0's first Agent turn: the AI seats, the rollout one included,
    # then take their turns until the decision returns to the human.
    for _ in range(40):
        if summary["finished"]:
            break
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
            if _obj(summary["decision"])["owner"] == 0 and human_steps > 0:
                break
            continue
        summary = manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )
        human_steps += 1
    assert _obj(summary["decision"])["owner"] == 0
    assert _int(summary["revision"]) > human_steps
    actors = {
        entry.get("actor")
        for entry in _rows(manager.log(game_id, 0)["entries"])
        if isinstance(entry.get("actor"), int)
    }
    assert {1, 2, 3} <= actors


APP_AI_SEATS = ("human", "app_ai", "app_ai_medium", "app_ai_easy")


def _ui_default_game(
    manager: GameSessionManager,
    seats: tuple[str, ...],
    game_seed: int,
    *,
    scouts: bool = False,
) -> JsonObject:
    """A game with the rule options the browser's setup screen starts with
    checked (CHOAM, the leader draft, the promo cards, Bloodlines, the Tech
    Module, Immortality, Go to 11, Epic Game Mode), Arrakeen Scouts if asked."""

    return manager.create_game(
        seats,
        game_seed=game_seed,
        choam_module=True,
        leader_draft=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        arrakeen_scouts=scouts,
    )


def _play_seat_zero(
    manager: GameSessionManager, summary: JsonObject, steps: int
) -> JsonObject:
    """Seat 0 confirms its turn ends and otherwise takes legal action 0."""

    game_id = _text(summary["game_id"])
    for _ in range(steps):
        if summary["finished"]:
            break
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, seat=0, revision=revision)
        else:
            summary = manager.apply_action(
                game_id, seat=0, revision=revision, index=0
            )
    return summary


def test_app_ai_seats_build_the_app_agent_at_each_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.agents.app_ai import AppAIAgent
    from dune_imperium.agents.base import StateAgent

    def view_only(*_: object) -> None:
        raise AssertionError("the server must hand app_ai the game state")

    # Without the state app_ai cannot mirror the app and plays at random.
    monkeypatch.setattr(AppAIAgent, "choose_action", view_only)
    manager = GameSessionManager()

    summary = manager.create_game(APP_AI_SEATS, game_seed=14, policy_seed=500)

    assert summary["seats"] == list(APP_AI_SEATS)
    session = manager._sessions[_text(summary["game_id"])]
    assert sorted(session.agents) == [1, 2, 3]
    for seat, level in ((1, 2), (2, 1), (3, 0)):
        agent = session.agents[seat]
        assert isinstance(agent, AppAIAgent)
        assert isinstance(agent, StateAgent)
        assert (agent.level, agent.seed) == (level, 500 + seat)
    # The browser sends no policy seed: it defaults to the offset + game seed.
    default = manager.create_game(APP_AI_SEATS, game_seed=14)
    default_agents = manager._sessions[_text(default["game_id"])].agents
    seeds = []
    for seat in (1, 2, 3):
        agent = default_agents[seat]
        assert isinstance(agent, AppAIAgent)
        seeds.append(agent.seed)
    assert seeds == [700_014 + seat for seat in (1, 2, 3)]

    _play_seat_zero(manager, summary, 60)
    for seat in (1, 2, 3):
        agent = session.agents[seat]
        assert isinstance(agent, AppAIAgent)
        assert sum(agent.mirrored.values()) > 0
        assert not agent.fallbacks


def test_the_same_seed_reproduces_an_app_ai_game() -> None:
    manager = GameSessionManager()
    all_app = ("app_ai", "app_ai_medium", "app_ai_easy", "app_ai")

    first = _ui_default_game(manager, all_app, 12)
    second = _ui_default_game(manager, all_app, 12)

    assert first["finished"] is True
    assert first["standings"] == second["standings"]
    assert first["revision"] == second["revision"]

    paused = _ui_default_game(manager, APP_AI_SEATS, 19)
    again = _ui_default_game(manager, APP_AI_SEATS, 19)
    assert again["revision"] == paused["revision"]
    assert again["decision"] == paused["decision"]
    paused = _play_seat_zero(manager, paused, 40)
    again = _play_seat_zero(manager, again, 40)
    assert again["revision"] == paused["revision"]
    assert again["decision"] == paused["decision"]
    assert (
        manager._sessions[_text(again["game_id"])].steps
        == manager._sessions[_text(paused["game_id"])].steps
    )


@pytest.mark.parametrize("scouts", [False, True], ids=["ui-default", "scouts"])
def test_a_human_plays_three_app_ai_seats_to_the_end(
    scouts: bool, caplog: pytest.LogCaptureFixture
) -> None:
    from dune_imperium.agents.app_ai import AppAIAgent

    manager = GameSessionManager()
    with caplog.at_level(logging.WARNING, logger="dune_imperium.agents.app_ai"):
        summary = _ui_default_game(
            manager,
            ("human", "app_ai", "app_ai", "app_ai"),
            3 if scouts else 1,
            scouts=scouts,
        )
        summary = _play_seat_zero(manager, summary, 2_000)

    assert summary["finished"] is True
    standings = _rows(summary["standings"])
    assert sorted(_int(entry["rank"]) for entry in standings) == [1, 2, 3, 4]
    session = manager._sessions[_text(summary["game_id"])]
    for seat in (1, 2, 3):
        agent = session.agents[seat]
        assert isinstance(agent, AppAIAgent)
        # Every decision the app AI met was the app's: none was answered at
        # random (unmirrored, or a window that failed).
        assert dict(agent.fallbacks) == {}
        assert sum(agent.mirrored.values()) > 100
    assert caplog.records == []


def test_creation_validates_seats_and_seeds() -> None:
    manager = GameSessionManager()

    with pytest.raises(SessionError, match="one seat assignment"):
        manager.create_game(("human", "heuristic"))
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.create_game(("human", "alien", "random", "random"))
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.create_game(("human", "checkpoint:", "random", "random"))
    # A checkpoint seat loads its file when the game is created.
    with pytest.raises(SessionError, match="cannot build seat 1"):
        manager.create_game(("human", "checkpoint:/nonexistent.pt", "random", "random"))
    with pytest.raises(SessionError, match="not be negative"):
        manager.create_game(ALL_AI, game_seed=-1)


def test_arrakeen_scouts_game_seats_checkpoint_and_search_seats(
    tmp_path: Path,
) -> None:
    # Design D6 (user decision 2026-09-30): trained seats may sit at an
    # Arrakeen Scouts table. The file below was trained without Scouts, so
    # its policy head is moved onto the Scouts catalog (as for Epic,
    # OQ-092), and each seat plays its decisions up to the human's turn.
    torch = pytest.importorskip("torch")
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.core.actions import DomainAction
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    base = RulesetConfig()
    codec = ActionCodec(base)
    torch.manual_seed(0)
    path = tmp_path / "policy.pt"
    save_checkpoint(
        path,
        PolicyValueNetwork(codec.size, hidden=(32,)),
        ruleset=base.identifier,
        iteration=1,
        codec=codec,
    )
    manager = GameSessionManager()

    # Seeds whose first round lets the trained seat act before the human.
    for seats, trained_seat, game_seed in (
        ((f"checkpoint:{path}", "random", "random", "human"), 0, 22),
        (("human", f"search:{path}", "random", "random"), 1, 27),
    ):
        summary = manager.create_game(
            seats, game_seed=game_seed, arrakeen_scouts=True
        )
        assert summary["arrakeen_scouts"] is True
        session = manager._sessions[_text(summary["game_id"])]
        from dune_imperium.agents.network_search_agent import NetworkSearchAgent
        from dune_imperium.training.torch_policy import NetworkAgent

        agent = session.agents[trained_seat]
        greedy = agent.greedy if isinstance(agent, NetworkSearchAgent) else agent
        assert isinstance(greedy, NetworkAgent)
        assert greedy.codec.config.arrakeen_scouts
        assert greedy.untrained
        played = [
            step
            for step in session.steps
            if isinstance(step, DomainAction) and step.actor == trained_seat
        ]
        assert played, f"seat {trained_seat} never decided before the human"


def test_arrakeen_scouts_game_is_created_with_random_and_heuristic_seats() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(ALL_AI, game_seed=17, arrakeen_scouts=True)

    assert summary["arrakeen_scouts"] is True


def test_go_to_11_is_summarized_and_keeps_every_seat_kind() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(
        ALL_AI, game_seed=17, immortality=True, go_to_11=True
    )
    assert summary["go_to_11"] is True
    assert manager.create_game(ALL_AI, game_seed=17)["go_to_11"] is False
    with pytest.raises(SessionError, match="requires the Immortality"):
        manager.create_game(ALL_AI, game_seed=17, go_to_11=True)
    # Unlike Arrakeen Scouts, trained policies may sit at a Go to 11 table
    # (user decision, OQ-091): the seat passes validation and fails only
    # when its (here absent) file is loaded.
    for kind in ("checkpoint", "search"):
        with pytest.raises(SessionError, match="cannot build seat 1"):
            manager.create_game(
                ("human", f"{kind}:/nonexistent.pt", "random", "random"),
                immortality=True,
                go_to_11=True,
            )


def test_epic_game_is_summarized_and_keeps_every_seat_kind() -> None:
    manager = GameSessionManager()

    # An independent option (OQ-092): no other option is required.
    summary = manager.create_game(ALL_AI, game_seed=17, epic_game=True)
    assert summary["epic_game"] is True
    assert manager.create_game(ALL_AI, game_seed=17)["epic_game"] is False
    # Trained policies may sit at an Epic table (user decision, OQ-092): the
    # seat passes validation and fails only when its (here absent) file is
    # loaded.
    for kind in ("checkpoint", "search"):
        with pytest.raises(SessionError, match="cannot build seat 1"):
            manager.create_game(
                ("human", f"{kind}:/nonexistent.pt", "random", "random"),
                epic_game=True,
            )


def test_unknown_games_and_deletion() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(ALL_AI, game_seed=16)
    game_id = _text(summary["game_id"])

    assert [entry["game_id"] for entry in manager.list_games()] == [game_id]
    manager.delete(game_id)
    assert manager.list_games() == []
    with pytest.raises(UnknownGameError):
        manager.summary(game_id)
    with pytest.raises(UnknownGameError):
        manager.delete(game_id)


def test_shortfall_warning_reports_short_supply_outcomes() -> None:
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.core.events import GameEvent
    from dune_imperium.server.sessions import shortfall_details, shortfall_warning

    assert shortfall_warning(None) is None
    quiet = RuleResult(state=None, events=())  # type: ignore[arg-type]
    assert shortfall_warning(quiet) is None
    short = RuleResult(
        state=None,  # type: ignore[arg-type]
        events=(
            GameEvent(
                event_id="x:specimens_short",
                kind="specimens_short",
                payload=(
                    ("generated", 1),
                    ("player", 0),
                    ("requested", 2),
                    ("short", 1),
                ),
            ),
            GameEvent(
                event_id="x:recruit_short",
                kind="troops_recruit_short",
                payload=(
                    ("player", 0),
                    ("recruited", 0),
                    ("requested", 2),
                    ("short", 2),
                ),
            ),
        ),
    )
    assert shortfall_warning(short) == (
        "supply 부족: specimen 2개 중 1개만 생성"
        " · supply 부족: troop 2개 중 0개만 recruit"
    )
    # The same, as data a client can word in its own language.
    assert shortfall_details(short) == [
        {"kind": "specimens", "requested": 2, "made": 1},
        {"kind": "troops", "requested": 2, "made": 0},
    ]


def test_shortfall_warning_reports_shortfalls_with_nothing_to_choose() -> None:
    """User ruling 2026-10-02 (L2-Q4, "로그 + 클릭 전 경고"): a short Intrigue
    draw, Suspensor Suits troops that cannot deploy and held Contract icons
    that fizzle with the turn open no window; the step that causes them
    warns before the click, from their public events (counts only)."""

    from dune_imperium.core.engine import RuleResult
    from dune_imperium.core.events import GameEvent
    from dune_imperium.server.sessions import shortfall_details, shortfall_warning

    def event(kind: str, *payload: tuple[str, int]) -> GameEvent:
        return GameEvent(event_id=f"x:{kind}", kind=kind, payload=payload)

    short = RuleResult(
        state=None,  # type: ignore[arg-type]
        events=(
            event(
                "intrigue_draw_short",
                ("drawn", 1),
                ("player", 0),
                ("requested", 3),
                ("short", 2),
            ),
            event(
                "suspensor_deployment_unavailable",
                ("deployed", 1),
                ("player", 0),
                ("troops", 2),
            ),
            event("contract_icons_fizzled", ("count", 1), ("player", 0)),
            # Another seat's shortfall is not this step's warning.
            event(
                "troops_recruit_short",
                ("player", 1),
                ("recruited", 0),
                ("requested", 2),
                ("short", 2),
            ),
        ),
    )
    assert shortfall_warning(short, 0) == (
        "책략 카드 더미와 버림 더미를 합쳐도 2장 모자람"
        " · 반중력 의복: 병력 3개 중 1개만 배치"
        " · 계약 아이콘 1개 소멸 — 가져갈 수 있는 계약 없음"
    )
    assert shortfall_details(short, 0) == [
        {"kind": "intrigue", "requested": 3, "made": 1},
        {"kind": "suspensor", "requested": 3, "made": 1},
        {"kind": "contract", "requested": 1, "made": 0},
    ]
    assert shortfall_details(short, 1) == [
        {"kind": "troops", "requested": 2, "made": 0},
    ]
    assert shortfall_details(short, 2) is None
    # Without a seat every shortfall counts.
    details = shortfall_details(short)
    assert details is not None and len(details) == 4


def test_serialized_actions_warn_about_shortfalls_with_nothing_to_choose() -> None:
    """L2-Q4 through the dry run of the real steps: the Assembly Hall draw
    with both Intrigue piles empty, the same draw paying Suspensor Suits'
    troop from an empty supply, and the turn-end press over a held Contract
    icon (the press itself confirms the fizzle, OQ-059; this is only the
    warning). The warning reads nothing hidden: a seat-0 determinization
    of the state words it the same."""

    import random
    from dataclasses import replace
    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.agents.determinize import determinize
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
    from dune_imperium.content.uprising.starting_cards import (
        starting_deck_instance_ids,
    )
    from dune_imperium.core import (
        DecisionFrame,
        GamePhase,
        GameState,
        PlayerDecision,
        PlayerState,
    )
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.server.sessions import _serialize_action

    engine = UprisingRulesEngine()
    starters = starting_deck_instance_ids(0)

    def placed(config: RulesetConfig, owner: PlayerState, **zones: object) -> GameState:
        values: dict[str, object] = {
            "config": config,
            "seed": 1,
            "phase": GamePhase.PLAYER_TURNS,
            "round_number": 1,
            "current_conflict_ids": (CONFLICTS[0].card.card_id,),
            "players": (owner, *(PlayerState(player_id=s) for s in range(1, 4))),
            "sardaukar_commander_space_ids": (),
            "face_up_contract_ids": ("contract:bloodlines_immediate",),
            "decision_stack": (
                DecisionFrame(
                    kind="turn",
                    frame_id="round:1:turn:0",
                    decision=PlayerDecision(owner=0, prompt="Choose a turn"),
                ),
            ),
        }
        values.update(zones)
        state = GameState(**values)  # type: ignore[arg-type]
        place = next(
            action
            for action in engine.legal_actions(state, 0)
            if dict(action.arguments).get("space_id") == "assembly_hall"
        )
        return engine.apply(state, place).state

    def warnings(state: GameState) -> dict[str, tuple[object, object]]:
        session = SimpleNamespace(engine=engine, state=state)
        entries = (
            _serialize_action(index, action, session)  # type: ignore[arg-type]
            for index, action in enumerate(engine.legal_actions(state, 0))
        )
        return {
            str(entry["action_id"]): (entry["warning"], entry["shortfall"])
            for entry in entries
        }

    def same_when_determinized(state: GameState) -> None:
        for seed in range(3):
            hidden = determinize(state, 0, random.Random(seed))
            assert warnings(hidden) == warnings(state)

    choam = RulesetConfig(choam_module=True, bloodlines=True)
    owner = PlayerState(
        player_id=0, hand=starters[:5], deck=starters[5:], held_contract_icons=1
    )
    empty = placed(choam, owner, intrigue_deck=(), intrigue_discard=())
    assert warnings(empty)["resolve_board_effect"] == (
        "책략 카드 더미와 버림 더미를 합쳐도 1장 모자람",
        [{"kind": "intrigue", "requested": 1, "made": 0}],
    )
    same_when_determinized(empty)
    drawn = engine.apply(
        empty,
        next(
            action
            for action in engine.legal_actions(empty, 0)
            if action.action_id == "resolve_board_effect"
        ),
    )
    assert "intrigue_draw_short" in [event.kind for event in drawn.events]
    assert warnings(drawn.state)["finish_agent_turn"] == (
        "계약 아이콘 1개 소멸 — 가져갈 수 있는 계약 없음",
        [{"kind": "contract", "requested": 1, "made": 0}],
    )
    same_when_determinized(drawn.state)

    tech = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
    suits = PlayerState(
        player_id=0,
        hand=starters[:5],
        deck=starters[5:],
        tech_ids=("suspensor_suits",),
        troops_supply=0,
        troops_garrison=12,
    )
    intrigue = intrigue_deck_instance_ids(True, bloodlines=True)
    no_troops = placed(tech, suits, intrigue_deck=intrigue[:3], intrigue_discard=())
    assert warnings(no_troops)["resolve_board_effect"] == (
        "반중력 의복: 병력 1개 중 0개만 배치",
        [{"kind": "suspensor", "requested": 1, "made": 0}],
    )
    same_when_determinized(no_troops)

    # A draw that needs a reshuffle: the step stops at the chance frame and
    # the troop is lost in that chance step's hook, yet it is still warned
    # on the step that asks for the shuffle (sessions.shortfall_outcome);
    # the discard is public, so a determinization words it the same.
    reshuffle = placed(tech, suits, intrigue_deck=(), intrigue_discard=intrigue[:2])
    assert warnings(reshuffle)["resolve_board_effect"] == (
        "반중력 의복: 병력 1개 중 0개만 배치",
        [{"kind": "suspensor", "requested": 1, "made": 0}],
    )
    same_when_determinized(reshuffle)
    shuffled = engine.apply(
        reshuffle,
        next(
            action
            for action in engine.legal_actions(reshuffle, 0)
            if action.action_id == "resolve_board_effect"
        ),
    )
    assert "suspensor_deployment_unavailable" not in [
        event.kind for event in shuffled.events
    ]
    assert shuffled.state.decision_stack[-1].kind == "intrigue_reshuffle"
    # With a troop in the supply the same reshuffled draw warns of nothing.
    one_troop = replace(suits, troops_supply=1, troops_garrison=11)
    covered = placed(tech, one_troop, intrigue_deck=(), intrigue_discard=intrigue[:2])
    assert warnings(covered)["resolve_board_effect"] == (None, None)


def test_imperial_privilege_trash_then_draw_is_not_warned_short() -> None:
    """Intrigue cards have no trash pile (OQ-061, user ruling 2026-10-04):
    Imperial Privilege's trashed card joins the Intrigue discard before the
    slot's draw, so with both Intrigue piles empty the draw reshuffles that
    card alone and is not short. The L2-Q4 warning used to say "1장
    모자람" here; it now says nothing."""

    import random
    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.agents.determinize import determinize
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
    from dune_imperium.content.uprising.starting_cards import (
        starting_deck_instance_ids,
    )
    from dune_imperium.core import (
        ChanceDecision,
        DecisionFrame,
        GamePhase,
        GameState,
        Influence,
        PlayerDecision,
        PlayerState,
        Resources,
    )
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.rules.frames import FrameKind
    from dune_imperium.server.sessions import _serialize_action

    engine = UprisingRulesEngine()
    starters = starting_deck_instance_ids(0)
    held = intrigue_deck_instance_ids(False)[0]
    owner = PlayerState(
        player_id=0,
        hand=starters[:5],
        deck=starters[5:],
        influence=Influence(emperor=2),
        resources=Resources(solari=3),
        intrigue_cards=(held,),
    )
    turn = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        players=(owner, *(PlayerState(player_id=s) for s in range(1, 4))),
        intrigue_deck=(),
        intrigue_discard=(),
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
        for action in engine.legal_actions(turn, 0)
        if dict(action.arguments).get("space_id") == "imperial_privilege"
    )
    state = engine.apply(turn, place).state

    def warnings(state: GameState) -> dict[str, tuple[object, object]]:
        session = SimpleNamespace(engine=engine, state=state)
        entries = (
            _serialize_action(index, action, session)  # type: ignore[arg-type]
            for index, action in enumerate(engine.legal_actions(state, 0))
        )
        return {
            str(entry["action_id"]): (entry["warning"], entry["shortfall"])
            for entry in entries
        }

    shown = warnings(state)
    assert shown["trash_intrigue_for_imperial_privilege"] == (None, None)
    assert shown["decline_imperial_privilege_intrigue"] == (None, None)
    for seed in range(3):
        assert warnings(determinize(state, 0, random.Random(seed))) == shown

    trash = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "trash_intrigue_for_imperial_privilege"
    )
    trashed = engine.apply(state, trash)
    assert "intrigue_draw_short" not in [event.kind for event in trashed.events]
    assert trashed.state.decision_stack[-1].kind == FrameKind.INTRIGUE_RESHUFFLE
    decision = trashed.next_decision
    assert isinstance(decision, ChanceDecision)
    assert decision.options == (held,)


def test_a_trashed_twisted_card_is_warned_short() -> None:
    """Twisted cards stay in the discard when it is reshuffled (OQ-097, user
    ruling 2026-10-04, "다른 사람이 twisted 카드를 뽑는 일은 없도록"): with
    both Intrigue piles empty, Imperial Privilege trashing a Twisted card
    cannot draw it back, so the step is warned short before the click (L2-Q4)
    and a seat-0 determinization words it the same."""

    import random
    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.agents.determinize import determinize
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.starting_cards import (
        starting_deck_instance_ids,
    )
    from dune_imperium.core import (
        DecisionFrame,
        GamePhase,
        GameState,
        Influence,
        PlayerDecision,
        PlayerState,
        Resources,
    )
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.server.sessions import _serialize_action

    engine = UprisingRulesEngine()
    starters = starting_deck_instance_ids(0)
    twisted = "intrigue:twisted_withdrawn:0"
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        hand=starters[:5],
        deck=starters[5:],
        influence=Influence(emperor=2),
        resources=Resources(solari=3),
        intrigue_cards=(twisted,),
    )
    turn = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        players=(owner, *(PlayerState(player_id=s) for s in range(1, 4))),
        intrigue_deck=(),
        intrigue_discard=(),
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
        for action in engine.legal_actions(turn, 0)
        if dict(action.arguments).get("space_id") == "imperial_privilege"
    )
    state = engine.apply(turn, place).state

    def warnings(state: GameState) -> dict[str, tuple[object, object]]:
        session = SimpleNamespace(engine=engine, state=state)
        entries = (
            _serialize_action(index, action, session)  # type: ignore[arg-type]
            for index, action in enumerate(engine.legal_actions(state, 0))
        )
        return {
            str(entry["action_id"]): (entry["warning"], entry["shortfall"])
            for entry in entries
        }

    shown = warnings(state)
    # The trashed Twisted card sits in the discard but is never reshuffled
    # (OQ-097); the warning says so (user request 2026-10-04).
    assert shown["trash_intrigue_for_imperial_privilege"] == (
        "책략 카드 더미와 버림 더미를 합쳐도 1장 모자람"
        " (버림 더미의 뒤틀린 책략 1장은 섞지 않음)",
        [{"kind": "intrigue", "requested": 1, "made": 0, "twisted": 1}],
    )
    assert shown["decline_imperial_privilege_intrigue"] == (None, None)
    for seed in range(3):
        assert warnings(determinize(state, 0, random.Random(seed))) == shown


def test_serialized_actions_warn_about_a_short_troop_supply() -> None:
    """OQ-049 (user request): a specimen the supply cannot provide is flagged
    on the action itself, while the action stays legal."""

    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.content.immortality.board import RESEARCH_START_ID
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.core import (
        DecisionFrame,
        GamePhase,
        GameState,
        PlayerDecision,
        PlayerState,
    )
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
    from dune_imperium.server.sessions import _serialize_action

    lab = "imperium:bene_tleilax_lab:0"
    seats = [
        PlayerState(
            player_id=0,
            hand=(lab,),
            research_space=RESEARCH_START_ID,
            troops_supply=0,
            troops_garrison=12,
        ),
        *(
            PlayerState(player_id=seat, research_space=RESEARCH_START_ID)
            for seat in range(1, 4)
        ),
    ]
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=RulesetConfig(immortality=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=tuple(seats),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, placement).state
    engine = UprisingRulesEngine()
    session = SimpleNamespace(engine=engine, state=placed)
    serialized = {
        entry["action_id"]: entry
        for entry in (
            _serialize_action(index, action, session)  # type: ignore[arg-type]
            for index, action in enumerate(engine.legal_actions(placed, 0))
        )
    }
    # Bene Tleilax Lab's specimen has no troop to take from the supply.
    assert serialized["resolve_agent_card_effect"]["warning"] == (
        "supply 부족: specimen 1개 중 0개만 생성"
    )
    assert serialized["resolve_agent_card_effect"]["shortfall"] == [
        {"kind": "specimens", "requested": 1, "made": 0}
    ]
    assert serialized["resolve_board_effect"]["warning"] is None
    assert serialized["resolve_board_effect"]["shortfall"] is None


def test_serialized_actions_carry_the_agent_box_icon_detail_ko() -> None:
    """Step K2 (2026-09-25): a personal card's own keyed Agent-box icon
    (OQ-027) now carries a real Korean ``detail_ko``, not just English
    ``detail`` (``display.actions.agent_card_icon_text_ko``) — the same as
    ``resolve_board_effect``'s own ``detail_ko`` since Step K4
    (test_legal_actions_describe_the_board_icon_they_resolve, above)."""

    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.core import (
        DecisionFrame,
        GamePhase,
        GameState,
        PlayerDecision,
        PlayerState,
    )
    from dune_imperium.core.player import Influence
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
    from dune_imperium.server.sessions import _serialize_action

    # Hidden Missive: RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, a
    # two-icon Agent box (Recruit 1 troop, Draw 1 card, each conditioned on
    # 2+ Bene Gesserit Influence) resolved as two separate
    # resolve_agent_card_effect actions, one per icon (OQ-027).
    hidden_missive = "imperium:hidden_missive:0"
    seats = [
        PlayerState(
            player_id=0,
            hand=(hidden_missive,),
            influence=Influence(bene_gesserit=2),
        ),
        *(PlayerState(player_id=seat) for seat in range(1, 4)),
    ]
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=tuple(seats),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    # Assembly Hall: a free Landsraad space, matching Hidden Missive's own
    # printed Agent icon.
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "assembly_hall"
    )
    placed = apply_agent_action(state, placement).state
    engine = UprisingRulesEngine()
    session = SimpleNamespace(engine=engine, state=placed)
    actions = [
        _serialize_action(index, action, session)  # type: ignore[arg-type]
        for index, action in enumerate(engine.legal_actions(placed, 0))
    ]
    agent_card_details = {
        _obj(entry["arguments"])["effect"]: (entry["detail"], entry["detail_ko"])
        for entry in actions
        if entry["action_id"] == "resolve_agent_card_effect"
    }
    assert agent_card_details == {
        "troops": (
            "Recruit 1 troop (at 2 Bene Gesserit Influence)",
            "{troop:1} ({influence_bene_gesserit:2}일 때)",
        ),
        "cards": (
            "Draw 1 card (at 2 Bene Gesserit Influence)",
            "{draw:1} ({influence_bene_gesserit:2}일 때)",
        ),
    }


def test_serialized_control_the_spice_payment_says_what_it_buys() -> None:
    """Control the Spice (Epic Game Mode) pays with Smuggler's Haven's
    ``pay_agent_card_spice``, whose client label only says a card effect's
    cost is paid; its ``detail``/``detail_ko`` say what this card's payment buys
    (``display.actions.agent_card_payment_text``), and the client shows it
    in place of the label (``static/core.js`` ``describeAction``)."""

    from types import SimpleNamespace

    from dune_imperium import RulesetConfig
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
    from dune_imperium.core import (
        DecisionFrame,
        GamePhase,
        GameState,
        PlayerDecision,
        PlayerState,
        Resources,
    )
    from dune_imperium.rules import UprisingRulesEngine
    from dune_imperium.server.sessions import _serialize_action

    control = "player:0:starter:control_the_spice:0"
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=RulesetConfig(epic_game=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=("choam_security",),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=(
            PlayerState(player_id=0, hand=(control,), resources=Resources(spice=2)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    engine = UprisingRulesEngine()
    # Accept Contract: a Spice Trade space, Control the Spice's Agent icon.
    placement = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)
        == {"card_id": control, "space_id": "accept_contract"}
    )
    placed = engine.apply(state, placement).state
    session = SimpleNamespace(engine=engine, state=placed)
    details = {
        entry["action_id"]: (entry["detail"], entry["detail_ko"])
        for entry in (
            _serialize_action(index, action, session)  # type: ignore[arg-type]
            for index, action in enumerate(engine.legal_actions(placed, 0))
        )
        if entry["action_id"]
        in ("pay_agent_card_spice", "decline_agent_card_payment")
    }
    assert details == {
        "pay_agent_card_spice": (
            "Pay 1 spice → Trash a card (optional) + Recruit 1 troop",
            "{spice:1} 지불 {arrow_right} 카드 {trash} (선택) + {troop:1}",
        ),
        "decline_agent_card_payment": (None, None),
    }
