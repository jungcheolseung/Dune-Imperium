"""The actions payload's Reveal choices: ``reveal_choices`` and each row's card.

User ruling 2026-10-14 (OQ-095 (7) addition, codec v147): "You may resolve
Reveal effects in any order you like" [Main p. 12], so every choice of a
revealed card waits on the Reveal frame and is offered beside the purchases
and gains. The decision panel sets each choice's rows under a header naming
its card and what the choice does, as it does an Agent turn's boxes: the
server lists the pending choices and says which one each row takes, and
names the card on the row (``detail_title``), so the ``source`` argument's
definition id is never what the page prints. Display only: the legal rows
stay exactly the engine's, and a failure leaves the keys out.
"""

import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import SOURCED_REVEAL_ACTION_IDS
from dune_imperium.server import sessions
from dune_imperium.server.sessions import GameSessionManager, JsonObject

ENGINE = UprisingRulesEngine()
CONFIG = RulesetConfig(bloodlines=True, choam_module=True)
POSTS = tuple(post.post_id for post in OBSERVATION_POSTS)
OBSERVER = "imperium:arrakis_observer:0"
DESERT_POWER = "imperium:desert_power:0"
POINTING = "imperium:pointing_the_way:0"
FAVOR = "imperium:spacing_guild_s_favor:0"
FAVOR_2 = "imperium:spacing_guild_s_favor:1"
WHEELS = "imperium:wheels_within_wheels:0"


def _obj(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _turn(owner: PlayerState, config: RulesetConfig = CONFIG) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        reserve_stacks=(("prepare_the_way", 7),),
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _reveal(owner: PlayerState, config: RulesetConfig = CONFIG) -> GameState:
    start = DomainAction(action_id="reveal_turn", actor=0)
    revealed = ENGINE.apply(_turn(owner, config), start)
    assert revealed.state.decision_stack[-1].kind == FrameKind.REVEAL
    return revealed.state


def _payload(state: GameState, seat: int = 0) -> JsonObject:
    session = SimpleNamespace(
        engine=ENGINE, state=state, game_id="test", awaiting_confirmation=None
    )
    return GameSessionManager()._legal_actions_locked(
        session,  # type: ignore[arg-type]
        seat,
    )


def _mixed() -> GameState:
    """An optional choice (Arrakis Observer's recall) and a mandatory one
    (Desert Power, no Maker Hooks) offered; Pointing the Way's Command and
    Spacing Guild's Favor's spice arrow waiting."""

    return _reveal(
        PlayerState(
            player_id=0,
            hand=(OBSERVER, DESERT_POWER, POINTING, FAVOR),
            spies_supply=1,
            spy_post_ids=POSTS[:2],
            resources=Resources(spice=1),
        )
    )


def test_the_pending_choices_are_listed_with_their_cards_in_pending_order() -> None:
    payload = _payload(_mixed())
    json.dumps(payload)

    entries = _rows(payload["reveal_choices"])
    assert [
        (entry["card_id"], entry["effect"], entry["optional"], entry["offered"])
        for entry in entries
    ] == [
        (OBSERVER, "may_recall_spy_for_three_strength", True, True),
        (DESERT_POWER, "may_pay_water_for_sandworm", False, True),
        (POINTING, "command_gain_chosen_influence", False, False),
        (FAVOR, "may_pay_three_spice_for_influence", True, False),
    ]
    observer = entries[0]
    assert observer == {
        "key": f"{OBSERVER}:may_recall_spy_for_three_strength",
        "card_id": OBSERVER,
        "name": "Arrakis Observer",
        "name_ko": "아라키스 관찰자",
        "effect": "may_recall_spy_for_three_strength",
        # The card's own words (display.tokens), as its popover reads.
        "text": "You may recall a Spy → +3 swords",
        "text_ko": "{spy} 소환 가능 {arrow_right} {sword:3}",
        "optional": True,
        "offered": True,
    }


def test_each_choice_row_names_its_choice_and_card_and_no_other_row_does() -> None:
    payload = _payload(_mixed())
    observer = f"{OBSERVER}:may_recall_spy_for_three_strength"
    desert = f"{DESERT_POWER}:may_pay_water_for_sandworm"
    rows = _rows(payload["actions"])
    by_id = {row["action_id"]: row for row in rows}

    recalls = [row for row in rows if row["action_id"] == "recall_spy_for_reveal"]
    assert len(recalls) == 2
    for row in recalls:
        # The shared id names its card with ``source`` (codec v147); the page
        # leads the row with the card's name instead of that id.
        assert row["arguments"]["source"] == "arrakis_observer"
        assert row["reveal_choice"] == observer
        assert (row["detail_title"], row["detail_title_ko"]) == (
            "Arrakis Observer",
            "아라키스 관찰자",
        )
    assert by_id["decline_reveal_sandworm"]["reveal_choice"] == desert
    others = [
        row
        for row in rows
        if row["action_id"] not in ("recall_spy_for_reveal", "decline_reveal_sandworm")
    ]
    assert others and all("reveal_choice" not in row for row in others)
    assert "acquire_reserve" in by_id
    # Desert Power is mandatory and offers its branch: no turn end yet.
    assert "finish_reveal" not in by_id
    assert [row["index"] for row in rows] == list(range(len(rows)))
    # The payload lists whole actions (the Reveal frame's effect rows stand
    # for them since stage B3b-2).
    assert len(rows) == len(ENGINE.whole_actions(_mixed(), 0))


def test_greyed_rows_name_their_choice_card_and_why() -> None:
    unavailable = _obj(_payload(_mixed())["unavailable"])
    rows = {row["key"]: row for row in _rows(unavailable["rows"])}

    sandworm = rows["choice:pay_reveal_water_for_sandworm"]
    assert sandworm["reveal_choice"] == f"{DESERT_POWER}:may_pay_water_for_sandworm"
    assert sandworm["reason_ko"] == "{maker_hooks} 없음"

    command = rows[f"waiting:{POINTING}:command_gain_chosen_influence"]
    assert _obj(command["action"])["detail_title_ko"] == "길을 가리키다"
    assert _obj(command["action"])["detail_ko"] == (
        "{command} ({persuasion} 6 이상): {influence_any:1} 선택"
    )
    assert command["reason_ko"].startswith("{command}: 이번 {reveal_turn}에 만든")
    assert command["reason_ko"].endswith(
        " — {reveal_turn}를 끝낼 때까지 못 채우면 사라짐"
    )

    favor = rows[f"waiting:{FAVOR}:may_pay_three_spice_for_influence"]
    assert _obj(favor["action"])["detail_title"] == "Spacing Guild's Favor"
    assert (favor["reason"], favor["reason_ko"]) == (
        "Needs 3 spice (you have 1); it lapses unused when the Reveal turn ends",
        "{spice:3} 필요 (보유 1) — {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
    )
    # No row prints an engine prompt or the deferred-choice wording.
    text = json.dumps(unavailable, ensure_ascii=False)
    assert "Resume" not in text and "재개" not in text


def test_two_copies_offer_one_row_which_takes_the_older_copys_choice() -> None:
    """The engine opens the first pending entry that offers a shared row
    (``reveal_turn._open_pending``), so the row is the older copy's."""

    owner = PlayerState(
        player_id=0, hand=(FAVOR, FAVOR_2), resources=Resources(spice=6)
    )
    payload = _payload(_reveal(owner))
    keys = [entry["key"] for entry in _rows(payload["reveal_choices"])]
    assert keys == [
        f"{FAVOR}:may_pay_three_spice_for_influence",
        f"{FAVOR_2}:may_pay_three_spice_for_influence",
    ]
    pays = [
        row
        for row in _rows(payload["actions"])
        if row["action_id"] == "pay_reveal_spice_influence"
    ]
    assert pays and {row["reveal_choice"] for row in pays} == {keys[0]}


def test_the_placement_after_a_recall_is_its_own_window_without_headers() -> None:
    """A Spy icon with an empty supply may first recall a Spy; once it did,
    the placement must follow at once on the choice's own frame (OQ-057
    (14)), whose prompt names it. That window lists no Reveal choices; its
    rows still name the card with ``source``."""

    state = _reveal(
        PlayerState(player_id=0, hand=(WHEELS,), spies_supply=0, spy_post_ids=POSTS[:3])
    )
    recall = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )
    committed = apply_whole(ENGINE, state, recall).state
    top = committed.decision_stack[-1]
    assert top.kind == FrameKind.REVEAL_CHOICE
    assert isinstance(top.decision, PlayerDecision)
    assert top.decision.prompt == "Choose where to place a Spy for this Reveal effect"
    payload = _payload(committed)
    assert payload["reveal_choices"] is None
    rows = _rows(payload["actions"])
    assert {row["action_id"] for row in rows} == {"place_reveal_spy"}
    assert all(
        row["arguments"]["source"] == "wheels_within_wheels"
        and "reveal_choice" not in row
        for row in rows
    )


def test_no_reveal_choices_outside_a_reveal() -> None:
    payload = _payload(_turn(PlayerState(player_id=0, hand=(OBSERVER,))))
    assert payload["reveal_choices"] is None
    assert all("reveal_choice" not in row for row in _rows(payload["actions"]))


def test_a_reveal_without_choices_lists_none() -> None:
    payload = _payload(_reveal(PlayerState(player_id=0, hand=())))
    assert payload["reveal_choices"] is None


def test_a_failure_is_logged_and_leaves_the_keys_out(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*_: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(sessions, "reveal_choice_headers", broken)
    state = _mixed()
    with caplog.at_level(logging.ERROR, logger=sessions.__name__):
        payload = _payload(state)
    assert "Reveal choice groups failed" in caplog.text
    assert payload["reveal_choices"] is None
    rows = _rows(payload["actions"])
    assert all("reveal_choice" not in row for row in rows)
    assert len(rows) == len(ENGINE.whole_actions(state, 0))


def test_a_rows_card_comes_from_the_server_not_the_source_id() -> None:
    """Spy Network and Arrakis Observer both recall with
    ``recall_spy_for_reveal``: their rows differ only by ``source`` and sit
    under different headers."""

    network = "imperium:spy_network:0"
    state = _reveal(
        PlayerState(
            player_id=0,
            hand=(network, OBSERVER),
            spies_supply=1,
            spy_post_ids=POSTS[:2],
        )
    )
    rows = [
        row
        for row in _rows(_payload(state)["actions"])
        if row["action_id"] == "recall_spy_for_reveal"
    ]
    assert {
        (row["arguments"]["source"], row["reveal_choice"], row["detail_title"])
        for row in rows
    } == {
        (
            "spy_network",
            f"{network}:recall_spy_to_draw_intrigue_if_two_placed",
            "Spy Network",
        ),
        (
            "arrakis_observer",
            f"{OBSERVER}:may_recall_spy_for_three_strength",
            "Arrakis Observer",
        ),
    }


def test_two_cards_sharing_an_id_each_head_their_own_rows() -> None:
    """Pointing the Way's Command and Ixian Ambassador both gain one
    Influence of the owner's choice: each card's rows carry its ``source``,
    so both headers show, each over its own four rows (before, the shared
    rows sat under the first card and the second card's header was left
    out while it offered them)."""

    ambassador = "imperium:ixian_ambassador:0"
    owner = PlayerState(
        player_id=0,
        hand=(
            POINTING,
            ambassador,
            "player:0:starter:convincing_argument:0",
            "player:0:starter:convincing_argument:1",
        ),
        tech_ids=("glowglobes", "training_depot"),
    )
    state = _reveal(owner, replace(CONFIG, tech_module=True))
    payload = _payload(state)
    entries = _rows(payload["reveal_choices"])
    assert [(entry["card_id"], entry["offered"]) for entry in entries] == [
        (POINTING, True),
        (ambassador, True),
    ]
    gains = [
        row
        for row in _rows(payload["actions"])
        if row["action_id"] == "gain_reveal_influence"
    ]
    by_choice: dict[str, set[str]] = {}
    for row in gains:
        by_choice.setdefault(row["reveal_choice"], set()).add(
            row["arguments"]["source"]
        )
    assert by_choice == {
        f"{POINTING}:command_gain_chosen_influence": {"pointing_the_way"},
        f"{ambassador}:gain_chosen_influence_if_two_tech": {"ixian_ambassador"},
    }
    assert len(gains) == 8


def test_the_page_knows_every_sourced_reveal_id() -> None:
    """The page leaves a Reveal choice row's ``source`` out of its label and
    leads a logged step with the card it names (core.js
    REVEAL_SOURCE_ACTIONS); its list is the engine's."""

    core_js = (
        Path(__file__).resolve().parents[2] / "src/dune_imperium/server/static/core.js"
    ).read_text(encoding="utf-8")
    listed = re.search(
        r"const REVEAL_SOURCE_ACTIONS = new Set\(\[(.*?)\]\);", core_js, re.S
    )
    assert listed is not None
    assert set(re.findall(r'"(\w+)"', listed.group(1))) == SOURCED_REVEAL_ACTION_IDS
