"""The choices a seat cannot take right now, greyed out with the reason.

User request 2026-09-29: an option that cannot be taken right now is shown,
not selectable, with the reason, and becomes selectable as soon as it can be
taken (and the reverse), for the whole game. ``display.unavailable`` does it
for the Reveal shop, the seat's own Intrigue cards and effects waiting on
their condition; these tests pin each reason, and that a row goes away the
moment its action becomes legal. The legal actions themselves are the
engine's, untouched (``test_unavailable_consistency.py`` guards that).
"""

from dataclasses import replace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
    tleilaxu_deck_instance_ids,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.effect_dsl import (
    EffectSection,
    GainResources,
    IntrigueOption,
    IntrigueTiming,
    PayResources,
)
from dune_imperium.content.uprising.imperium import (
    imperium_card_for_instance,
    imperium_deck_instance_ids,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display import scouts
from dune_imperium.display.unavailable import (
    NOT_NOW_CODE,
    held_text,
    intrigue_option_reason,
    resource_reason,
    troops_reason,
    unavailable_choices,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_effect_frame import agent_box_is_waiting
from dune_imperium.rules.combat import resolve_combat_rewards
from dune_imperium.rules.effect_interpreter import OptionBlock
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.immortality import advance_research

ENGINE = UprisingRulesEngine()
BASE = RulesetConfig()
ROW = imperium_deck_instance_ids(False)[:5]  # five cards costing 3 Persuasion
TURN = DecisionFrame(
    kind="turn",
    frame_id="round:1:turn:0",
    decision=PlayerDecision(owner=0, prompt="Choose a turn"),
)


def _state(
    owner: PlayerState, *, config: RulesetConfig = BASE, **fields: Any
) -> GameState:
    values: dict[str, Any] = {
        "config": config,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "decision_stack": (TURN,),
    }
    values.update(fields)
    return GameState(**values)


def _reveal(state: GameState, persuasion: int) -> GameState:
    """Start seat 0's Reveal and give it ``persuasion`` to spend."""

    revealed = ENGINE.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    frame = revealed.state.decision_stack[-1]
    assert frame.kind == FrameKind.REVEAL
    context = {**dict(frame.context), "persuasion": persuasion}
    frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(
        revealed.state,
        decision_stack=(*revealed.state.decision_stack[:-1], frame),
    )


def _found(state: GameState, seat: int = 0) -> dict[str, Any]:
    found = unavailable_choices(state, seat, ENGINE.legal_actions(state, seat))
    assert isinstance(found, dict)
    return found


def _rows(found: dict[str, Any], surface: str) -> dict[str, dict[str, Any]]:
    return {row["key"]: row for row in found["rows"] if row["surface"] == surface}


def _legal(state: GameState, action_id: str) -> list[dict[str, Any]]:
    return [
        dict(action.arguments)
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == action_id
    ]


def test_the_reason_helpers_moved_and_display_scouts_re_exports_them() -> None:
    moved = vars(scouts)
    assert moved["_resource_reason"] is resource_reason
    assert moved["_troops_reason"] is troops_reason
    assert moved["_held"] is held_text
    assert resource_reason("spice", 3, 2) == (
        "Needs 3 spice (you have 2)",
        "{spice:3} 필요 (보유 2)",
        "cost",
    )


# --- The Reveal shop ---


def _shop(persuasion: int) -> GameState:
    return _reveal(
        _state(
            PlayerState(player_id=0),
            imperium_row=ROW,
            reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 0)),
        ),
        persuasion,
    )


def test_the_reveal_shop_greys_out_the_cards_the_seat_cannot_afford() -> None:
    state = _shop(2)
    found = _found(state)

    assert found["frame"] == "reveal"
    rows = _rows(found, "acquire")
    assert {row["action"]["action_id"] for row in rows.values()} == {
        "acquire_imperium",
        "acquire_reserve",
    }
    for instance_id in ROW:
        assert imperium_card_for_instance(instance_id).acquisition_cost == 3
        row = rows[f"acquire:{instance_id}"]
        assert row["action"] == {
            "action_id": "acquire_imperium",
            "arguments": {"instance_id": instance_id},
            "detail": None,
            "detail_ko": None,
        }
        assert (row["reason"], row["reason_ko"], row["code"]) == (
            "Needs 3 Persuasion (you have 2)",
            "{persuasion:3} 필요 (보유 2)",
            "cost",
        )
        assert found["refs"][instance_id]["code"] == "cost"
    empty = rows["acquire:the_spice_must_flow"]
    assert (empty["reason"], empty["code"]) == ("The Reserve stack is empty", "empty")
    # Prepare the Way costs 2: an ordinary buy, never greyed or dimmed.
    assert _legal(state, "acquire_reserve") == [{"card_id": "prepare_the_way"}]
    assert "acquire:prepare_the_way" not in rows
    assert "prepare_the_way" not in found["refs"]
    assert set(found["refs"]) == {*ROW, "the_spice_must_flow"}


def test_a_greyed_out_card_lights_up_as_soon_as_the_seat_can_afford_it() -> None:
    state = _shop(3)
    found = _found(state)

    assert {row["key"] for row in found["rows"]} == {"acquire:the_spice_must_flow"}
    assert set(found["refs"]) == {"the_spice_must_flow"}
    assert [item["instance_id"] for item in _legal(state, "acquire_imperium")] == [*ROW]


def test_set_aside_and_tleilaxu_cards_name_their_own_cost() -> None:
    config = RulesetConfig(immortality=True)
    tleilaxu = tleilaxu_deck_instance_ids()[:2]
    set_aside = ROW[0]
    supply = PlayerState(player_id=0).troops_supply
    owner = PlayerState(
        player_id=0,
        troops_supply=supply - 1,
        specimens=1,
        research_space=RESEARCH_START_ID,
        imperium_set_aside=(set_aside,),
    )
    state = _reveal(
        _state(owner, config=config, tleilaxu_row=tleilaxu),
        1,
    )
    rows = _rows(_found(state), "acquire")

    manipulated = rows[f"acquire:{set_aside}"]
    assert manipulated["action"]["action_id"] == "acquire_manipulated_imperium"
    # One Persuasion less than printed [Manipulate card].
    assert manipulated["reason"] == "Needs 2 Persuasion (you have 1)"
    for instance_id in tleilaxu:
        cost = tleilaxu_card_for_instance(instance_id).specimen_cost
        assert cost > 1  # Beguiling Pheromones 3, Chairdog 2
        key = f"acquire:{instance_id}"
        assert rows[key]["action"]["action_id"] == "acquire_tleilaxu"
        assert rows[key]["reason"] == f"Needs {cost} specimens (you have 1)"
        assert rows[key]["reason_ko"] == f"{{specimen:{cost}}} 필요 (보유 1)"
    reclaimed = [
        row
        for row in rows.values()
        if row["action"]["action_id"] == "acquire_reclaimed_forces"
    ]
    assert [row["action"]["arguments"] for row in reclaimed] == [
        {"choice": "troops"},
        {"choice": "tleilaxu"},
    ]
    assert {row["reason"] for row in reclaimed} == {
        f"Needs {RECLAIMED_FORCES.specimen_cost} specimens (you have 1)"
    }


# --- Intrigue cards ---


def _intrigue_state(*cards: str, **owner_fields: Any) -> GameState:
    owner = PlayerState(
        player_id=0,
        intrigue_cards=tuple(f"intrigue:{card}:0" for card in cards),
        **owner_fields,
    )
    return _state(owner, config=RulesetConfig(choam_module=True))


def test_an_intrigue_card_greys_out_with_its_failing_cost_or_condition() -> None:
    cards = (
        "imperium_politics",
        "councilor_s_ambition",
        "sietch_ritual",
        "backed_by_choam",
        "change_allegiances",
        "false_orders",
        "coercive_negotiation",
    )
    found = _found(_intrigue_state(*cards))
    rows = {
        row["action"]["arguments"]["card_id"]: row
        for row in _rows(found, "intrigue").values()
    }

    expected = {
        "imperium_politics": ("Needs 1 solari (you have 0)", "cost"),
        "councilor_s_ambition": ("Only if you hold a High Council seat", "condition"),
        "sietch_ritual": ("Needs 1 card in hand (you have 0)", "cost"),
        "backed_by_choam": ("Needs 1 Influence to lose (you have 0)", "cost"),
        "change_allegiances": ("None of its lines can be used now", "no_line"),
        "false_orders": ("Only after you send an Agent this turn", "reward"),
        "coercive_negotiation": (
            "Needs 3 Contracts in the bank (there are 0)",
            "contract_bank",
        ),
    }
    assert {
        card.split(":")[1]: (row["reason"], row["code"]) for card, row in rows.items()
    } == expected
    for card_id, row in rows.items():
        assert row["action"]["action_id"] == "play_intrigue"
        assert row["action"]["arguments"] == {"card_id": card_id, "option": 0}
        assert row["reason_ko"]
        # The card in the Intrigue hand is dimmed with the same reason.
        assert found["refs"][card_id]["reason"] == row["reason"]


def test_an_intrigue_card_for_another_window_is_only_dimmed() -> None:
    """No row for a Combat card during a Plot turn (it would show every
    turn), only its card dimmed with when it is played."""

    found = _found(_intrigue_state("spice_is_power", "imperium_politics"))

    assert [row["action"]["arguments"]["card_id"] for row in found["rows"]] == [
        "intrigue:imperium_politics:0"
    ]
    assert found["refs"]["intrigue:spice_is_power:0"] == {
        "reason": "Combat Intrigue: played during combat",
        "reason_ko": "전투 책략 카드: 전투 중에 사용",
        "code": "timing",
    }


def test_a_start_of_turn_card_is_played_then_only_dimmed_after_that_point() -> None:
    state = _intrigue_state("twisted_withdrawn")
    withdrawn = {"card_id": "intrigue:twisted_withdrawn:0", "option": 0}

    assert _legal(state, "play_intrigue") == [withdrawn]
    assert unavailable_choices(state, 0, ENGINE.legal_actions(state, 0)) is None
    revealed = _reveal(state, 0)
    found = _found(revealed)
    assert found["rows"] == []
    assert found["refs"]["intrigue:twisted_withdrawn:0"]["reason"] == (
        "Only at the start of your turn"
    )


def _detonation(troops: int, undeployable: int) -> GameState:
    """Seat 0 at its turn start with Detonation, ``troops`` in its garrison
    and ``undeployable`` of them barred from deploying this turn."""

    owner = PlayerState(
        player_id=0,
        intrigue_cards=("intrigue:detonation:0",),
        troops_garrison=troops,
        troops_supply=12 - troops,
    )
    turn = replace(TURN, context=(("undeployable_troops", undeployable),))
    return _state(owner, decision_stack=(turn,))


def test_a_garrison_troop_that_cannot_deploy_this_turn_is_named() -> None:
    """Detonation's "deploy from your garrison" line (option 1) is judged on
    the troops that may deploy this turn: Harkonnen Advisor's troop "can't
    deploy ... this turn" [Piter De Vries card] (OQ-038). With it the only
    troop in the garrison the reason says so, not that the garrison is
    empty."""

    def reason(state: GameState) -> tuple[str, str, str]:
        rows = _rows(_found(state), "intrigue")
        row = rows["intrigue:intrigue:detonation:0:1"]
        assert _legal(state, "play_intrigue") == [
            {"card_id": "intrigue:detonation:0", "option": 0}
        ]
        return row["reason"], row["reason_ko"], row["code"]

    assert reason(_detonation(1, 1)) == (
        "Your garrison troop cannot be deployed this turn",
        "{garrison}의 {troop}은 이번 차례에 {conflict}에 배치할 수 없음",
        "reward",
    )
    assert reason(_detonation(2, 2))[0] == (
        "Your garrison troops cannot be deployed this turn"
    )
    assert reason(_detonation(0, 0)) == (
        "No unit in your garrison to deploy",
        "{garrison}에 배치할 유닛 없음",
        "reward",
    )
    # One deployable troop beside the barred one: an ordinary play.
    assert {"card_id": "intrigue:detonation:0", "option": 1} in _legal(
        _detonation(2, 1), "play_intrigue"
    )


def test_an_intrigue_row_becomes_a_play_as_soon_as_the_seat_can_pay() -> None:
    poor = _intrigue_state("imperium_politics")
    rich = _intrigue_state("imperium_politics", resources=Resources(solari=1))
    politics = {"card_id": "intrigue:imperium_politics:0", "option": 0}

    assert _legal(poor, "play_intrigue") == []
    assert [row["key"] for row in _found(poor)["rows"]] == [
        "intrigue:intrigue:imperium_politics:0:0"
    ]
    assert _legal(rich, "play_intrigue") == [politics]
    assert unavailable_choices(rich, 0, ENGINE.legal_actions(rich, 0)) is None


# --- Effects waiting on their condition ---


def test_a_deferred_reveal_choice_waits_greyed_out_until_its_condition_holds() -> None:
    """In High Places' two-Spy recall waits while one Spy is out; once Wheels
    Within Wheels' Reveal Spy is placed it becomes an ordinary resume row
    (the fixture of test_reveal_turn.py's
    test_an_unavailable_choice_opens_once_its_condition_holds) [Main p. 12]."""

    def instance(card_id: str) -> str:
        return next(i for i in imperium_deck_instance_ids(False) if f":{card_id}:" in i)

    in_high_places = instance("in_high_places")
    wheels = instance("wheels_within_wheels")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, wheels),
            spies_supply=2,
            spy_post_ids=("arrakis-hagga-basin",),
        )
    )
    revealed = ENGINE.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    assert revealed.state.decision_stack[-1].kind == FrameKind.REVEAL_CHOICE
    deferred = ENGINE.apply(
        revealed.state, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    assert deferred.decision_stack[-1].kind == FrameKind.REVEAL

    rows = _rows(_found(deferred), "waiting")
    recall = "may_recall_two_spies_for_three_persuasion"
    assert list(rows) == [f"waiting:{in_high_places}:{recall}"]
    row = rows[f"waiting:{in_high_places}:{recall}"]
    assert row["action"]["action_id"] == "resume_reveal_choice"
    assert row["action"]["arguments"] == {"effect": recall}
    assert row["action"]["detail"]  # the engine's prompt, as on a legal row
    assert row["card_id"] == in_high_places
    assert row["code"] == "waiting"
    assert "lapses" in row["reason"]
    assert {"effect": "place_spy"} in _legal(deferred, "resume_reveal_choice")

    resumed = ENGINE.apply(
        deferred,
        DomainAction(
            action_id="resume_reveal_choice",
            actor=0,
            arguments=(("effect", "place_spy"),),
        ),
    ).state
    placement = next(
        action
        for action in ENGINE.legal_actions(resumed, 0)
        if action.action_id == "place_reveal_spy"
    )
    placed = ENGINE.apply(resumed, placement).state
    assert placed.decision_stack[-1].kind == FrameKind.REVEAL
    assert _legal(placed, "resume_reveal_choice") == [{"effect": recall}]
    found = unavailable_choices(placed, 0, ENGINE.legal_actions(placed, 0))
    assert found is None or not _rows(found, "waiting")


def test_a_withheld_agent_box_waits_greyed_out_until_its_condition_holds() -> None:
    """Prepare the Way's "draw a card with 2 Bene Gesserit Influence" is
    withheld while the Influence is short (OQ-057) and offered once it holds."""

    card = "reserve:prepare_the_way:0"
    state = _state(PlayerState(player_id=0, hand=(card,)))
    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
    )
    placed = ENGINE.apply(state, placement).state
    assert placed.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _legal(placed, "resolve_agent_card_effect") == []

    rows = list(_rows(_found(placed), "waiting").values())
    assert [row["action"]["action_id"] for row in rows] == ["resolve_agent_card_effect"]
    assert rows[0]["card_id"] == card
    assert rows[0]["code"] == "waiting"

    owner = placed.players[0]
    influence = Influence(bene_gesserit=2)
    met = replace(
        placed, players=(replace(owner, influence=influence), *placed.players[1:])
    )
    assert _legal(met, "resolve_agent_card_effect") == [{}]
    found = unavailable_choices(met, 0, ENGINE.legal_actions(met, 0))
    assert found is None or not _rows(found, "waiting")


def test_no_waiting_row_while_gather_intelligence_is_the_only_choice() -> None:
    """Gather Intelligence replaces the whole Agent-effect list while it is
    pending (``legal_agent_effect_frame_actions``), so the withheld box is
    not shown beside it; it is, greyed out, once the seat has declined."""

    card = "reserve:prepare_the_way:0"
    post = next(
        post
        for post in OBSERVATION_POSTS
        if "assembly_hall" in post.connected_space_ids
    )
    owner = PlayerState(
        player_id=0, hand=(card,), spy_post_ids=(post.post_id,), spies_supply=2
    )
    placed = ENGINE.apply(
        _state(owner),
        DomainAction(
            action_id="agent_turn",
            actor=0,
            arguments=(("card_id", card), ("space_id", "assembly_hall")),
        ),
    ).state
    legal = ENGINE.legal_actions(placed, 0)

    assert [action.action_id for action in legal] == ["decline_gather_intelligence"]
    assert agent_box_is_waiting(placed, 0)  # withheld (OQ-057), behind the choice
    assert unavailable_choices(placed, 0, legal) is None
    declined = ENGINE.apply(
        placed, DomainAction(action_id="decline_gather_intelligence", actor=0)
    ).state
    rows = list(_rows(_found(declined), "waiting").values())
    assert [row["key"] for row in rows] == [f"waiting:agent_box:{card}"]
    assert not agent_box_is_waiting(declined, 1)  # only the box's owner's


# --- A branch of an open choice that cannot be taken now ---


def _desert_power(
    *, owner_fields: dict[str, Any] | None = None, **fields: Any
) -> GameState:
    """Seat 0 reveals Desert Power: its choice window is on top."""

    desert_power = next(
        i for i in imperium_deck_instance_ids(False) if ":desert_power:" in i
    )
    owner = replace(
        PlayerState(
            player_id=0,
            hand=(desert_power,),
            maker_hooks=True,
            resources=Resources(water=1),
        ),
        **(owner_fields or {}),
    )
    state = _state(owner, **{"current_conflict_ids": ("propaganda",), **fields})
    revealed = ENGINE.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    assert revealed.state.decision_stack[-1].kind == FrameKind.REVEAL_CHOICE
    return revealed.state


def test_desert_power_without_maker_hooks_greys_out_the_sandworm_branch() -> None:
    """Option (B), user ruling 2026-09-30: "REVEAL_CHOICE 창을 열어 '설득 2'만
    고르게, 모래벌레 줄은 '메이커 작살 없음' 회색". The row sits on the new
    "choice" surface and names the card; the Persuasion branch is legal."""

    state = _desert_power(owner_fields={"maker_hooks": False})
    found = _found(state)
    assert found["frame"] == FrameKind.REVEAL_CHOICE
    assert [row["surface"] for row in found["rows"]] == ["choice"]
    row = _rows(found, "choice")["choice:pay_reveal_water_for_sandworm"]
    assert row["action"]["action_id"] == "pay_reveal_water_for_sandworm"
    assert row["action"]["arguments"] == {}
    assert row["card_id"] == dict(state.decision_stack[-1].context)["reveal_card_id"]
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "No Maker Hooks",
        "{maker_hooks} 없음",
        "maker_hooks",
    )
    assert _legal(state, "decline_reveal_sandworm") == [{}]
    assert found["refs"] == {}


def test_each_sandworm_block_has_its_own_reason() -> None:
    """Water, a Conflict and the Shield Wall, in the block's order."""

    cases = [
        (
            _desert_power(owner_fields={"resources": Resources(water=0)}),
            ("Needs 1 water (you have 0)", "{water:1} 필요 (보유 0)", "cost"),
        ),
        (
            _desert_power(current_conflict_ids=()),
            ("No Conflict this round", "이번 라운드에 교전 없음", "no_conflict"),
        ),
        (
            _desert_power(
                current_conflict_ids=("siege_of_arrakeen",), shield_wall_present=True
            ),
            (
                "The Shield Wall protects this Conflict",
                "{shield_wall}이 이번 교전을 보호함",
                "shield_wall",
            ),
        ),
    ]
    for state, reason in cases:
        row = _rows(_found(state), "choice")["choice:pay_reveal_water_for_sandworm"]
        assert (row["reason"], row["reason_ko"], row["code"]) == reason


def test_no_sandworm_row_while_the_sandworm_branch_is_legal() -> None:
    state = _desert_power()
    assert _legal(state, "pay_reveal_water_for_sandworm") == [{}]
    assert unavailable_choices(state, 0, ENGINE.legal_actions(state, 0)) is None


def test_a_deferred_desert_power_shows_no_waiting_row() -> None:
    """The old "waiting" row (a deferred choice whose condition could still
    come true) is gone: without Maker Hooks the choice is always resumable,
    since its Persuasion branch can always be taken."""

    deferred = ENGINE.apply(
        _desert_power(owner_fields={"maker_hooks": False}),
        DomainAction(action_id="defer_reveal_choice", actor=0),
    ).state
    assert deferred.decision_stack[-1].kind == FrameKind.REVEAL
    assert _legal(deferred, "resume_reveal_choice") == [
        {"effect": "may_pay_water_for_sandworm"}
    ]
    found = unavailable_choices(deferred, 0, ENGINE.legal_actions(deferred, 0))
    assert found is None or not _rows(found, "waiting")


# --- A recall with no other Agent to recall ---

_NO_OTHER_AGENT = (
    "No other Agent of yours to recall (not the one sent this turn)",
    "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외)",
    "no_target",
)


def _place(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == space_id
    )
    return ENGINE.apply(state, action).state


def _imperial_owner(**owner_fields: Any) -> PlayerState:
    return PlayerState(
        player_id=0,
        hand=("player:0:starter:dagger:0",),
        resources=Resources(solari=3),
        influence=Influence(emperor=2),
        **owner_fields,
    )


def _imperial_privilege(**owner_fields: Any) -> GameState:
    """Seat 0 at Imperial Privilege, its Intrigue slot declined."""

    placed = _place(_state(_imperial_owner(**owner_fields)), "imperial_privilege")
    return ENGINE.apply(
        placed, DomainAction(action_id="decline_imperial_privilege_intrigue", actor=0)
    ).state


def test_imperial_privilege_with_no_other_agent_greys_out_the_recall() -> None:
    """OQ-023: with no other Agent only the recall is skipped and the card
    still drawn; user ruling 2026-09-30 ("결정 창 없이 자동으로 넘어가는
    곳도 모두 결정 창을 연다") makes the owner confirm it, with the recall
    greyed out beside the confirm on the "choice" surface."""

    state = _imperial_privilege()
    assert _legal(state, "resolve_imperial_privilege_without_recall") == [{}]
    found = _found(state)
    assert found["frame"] == FrameKind.AGENT_EFFECTS
    row = _rows(found, "choice")["choice:imperial_privilege_recall"]
    assert row["action"]["action_id"] == "recall_agent_for_imperial_privilege"
    assert row["action"]["arguments"] == {}
    assert (row["reason"], row["reason_ko"], row["code"]) == _NO_OTHER_AGENT
    assert row["refs"] == []

    # The confirm draws the card and the row goes with the pending recall.
    confirmed = ENGINE.apply(
        state,
        DomainAction(action_id="resolve_imperial_privilege_without_recall", actor=0),
    ).state
    after = unavailable_choices(confirmed, 0, ENGINE.legal_actions(confirmed, 0))
    assert after is None or not _rows(after, "choice")


def test_no_recall_row_while_imperial_privilege_has_a_target() -> None:
    state = _imperial_privilege(agents_available=1, agent_locations=("arrakeen",))
    assert _legal(state, "recall_agent_for_imperial_privilege") == [
        {"space_id": "arrakeen"}
    ]
    assert _legal(state, "resolve_imperial_privilege_without_recall") == []
    found = unavailable_choices(state, 0, ENGINE.legal_actions(state, 0))
    assert found is None or not _rows(found, "choice")
    # Nor before the Intrigue slot, while the recall is not yet the step.
    slot = _place(_state(_imperial_owner()), "imperial_privilege")
    found = unavailable_choices(slot, 0, ENGINE.legal_actions(slot, 0))
    assert found is None or not _rows(found, "choice")


def _sardaukar_ii(**owner_fields: Any) -> GameState:
    """Seat 0 completes Sardaukar II at the Sardaukar space."""

    truthtrance = next(
        i for i in imperium_deck_instance_ids(True) if ":truthtrance:" in i
    )
    owner = PlayerState(
        player_id=0,
        hand=(truthtrance,),
        resources=Resources(solari=10, spice=10, water=10),
        active_contract_ids=("contract:sardaukar_ii",),
        **owner_fields,
    )
    placed = _place(
        _state(owner, config=RulesetConfig(choam_module=True)), "sardaukar"
    )
    complete = next(
        action
        for action in ENGINE.legal_actions(placed, 0)
        if action.action_id == "complete_contract"
    )
    completed = ENGINE.apply(placed, complete).state
    assert completed.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_RECALL
    return completed


def test_a_contract_recall_with_no_other_agent_greys_out_the_recall() -> None:
    """Sardaukar II's reward "simply fizzles" with no other Agent (the
    designer's ruling, OQ-057); its window now opens with only the confirm
    and the recall greyed out (user ruling 2026-09-30)."""

    state = _sardaukar_ii()
    assert [
        action.action_id for action in ENGINE.legal_actions(state, 0)
    ] == ["resolve_contract_without_recall"]
    found = _found(state)
    assert found["frame"] == FrameKind.CONTRACT_REWARD_RECALL
    assert [row["key"] for row in found["rows"]] == ["choice:contract_recall"]
    row = found["rows"][0]
    assert row["action"]["action_id"] == "recall_agent_for_contract"
    assert row["action"]["arguments"] == {}
    assert (row["reason"], row["reason_ko"], row["code"]) == _NO_OTHER_AGENT


def test_no_contract_recall_row_while_the_reward_has_a_target() -> None:
    state = _sardaukar_ii(agents_available=1, agent_locations=("arrakeen",))
    assert _legal(state, "recall_agent_for_contract") == [{"space_id": "arrakeen"}]
    assert unavailable_choices(state, 0, ENGINE.legal_actions(state, 0)) is None


# --- A research bonus whose cost cannot be paid ---


def _research_bonus(origin: str, target: str, **owner_fields: Any) -> GameState:
    """Seat 0 advances its research token from ``origin`` to ``target``,
    whose arrow bonus window is then on top (Immortality)."""

    owner = PlayerState(player_id=0, research_space=origin, **owner_fields)
    state = _state(owner, config=RulesetConfig(immortality=True))
    advanced = advance_research(state, 0, source="test").state
    choice = next(
        action
        for action in ENGINE.legal_actions(advanced, 0)
        if action.action_id == "choose_research_space"
        and dict(action.arguments)["space_id"] == target
    )
    chosen = ENGINE.apply(advanced, choice).state
    assert chosen.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
    return chosen


def test_a_research_bonus_without_an_intrigue_card_greys_out_the_trash() -> None:
    """c7r3's "Trash an Intrigue card" arrow [Immortality p. 16] with an
    empty Intrigue hand: the window opens anyway with only the decline
    (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정
    창을 연다"), and the trash shows greyed out on the "choice" surface,
    naming no card."""

    state = _research_bonus("c6r2", "c7r3")
    assert [action.action_id for action in ENGINE.legal_actions(state, 0)] == [
        "decline_research_bonus"
    ]
    found = _found(state)
    assert found["frame"] == FrameKind.RESEARCH_BONUS
    assert [row["key"] for row in found["rows"]] == ["choice:research_bonus_trash"]
    row = found["rows"][0]
    assert row["action"]["action_id"] == "trash_intrigue_for_research_bonus"
    assert row["action"]["arguments"] == {}
    assert row["refs"] == []
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "No Intrigue card to trash",
        "{trash}할 {intrigue} 없음",
        "cost",
    )
    assert found["refs"] == {}


def test_a_research_bonus_short_of_solari_greys_out_the_payment() -> None:
    """c8r6's "7 Solari -> two Tleilaxu" arrow with 3 Solari."""

    state = _research_bonus("c7r5", "c8r6", resources=Resources(solari=3))
    assert [action.action_id for action in ENGINE.legal_actions(state, 0)] == [
        "decline_research_bonus"
    ]
    found = _found(state)
    assert [row["key"] for row in found["rows"]] == ["choice:research_bonus_pay"]
    row = found["rows"][0]
    assert row["action"]["action_id"] == "pay_research_bonus"
    assert row["action"]["arguments"] == {}
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Needs 7 solari (you have 3)",
        "{solari:7} 필요 (보유 3)",
        "cost",
    )


def test_no_research_bonus_row_while_its_cost_can_be_paid() -> None:
    held = "intrigue:ambush:0"
    cases = [
        (_research_bonus("c6r2", "c7r3", intrigue_cards=(held,)), "trash"),
        (
            _research_bonus("c7r5", "c8r6", resources=Resources(solari=7)),
            "pay_research_bonus",
        ),
    ]
    for state, offered in cases:
        legal = ENGINE.legal_actions(state, 0)
        assert any(offered in action.action_id for action in legal), offered
        assert unavailable_choices(state, 0, legal) is None
    # Nor for the Influence bonus, which has no cost.
    influence = _research_bonus("c5r5", "c6r6")
    assert unavailable_choices(influence, 0, ENGINE.legal_actions(influence, 0)) is None


# --- A Conflict reward's Faction already at the top ---

_AT_THE_TOP = ("Already at the top", "이미 최고치", "top")
_INFLUENCE_CONFIRM = DomainAction(
    action_id="resolve_combat_influence_without_faction", actor=0
)


def _combat_reward(conflict_id: str, influence: Influence) -> GameState:
    """Seat 0 alone wins ``conflict_id``: its reward windows are open."""

    owner = PlayerState(player_id=0, combat_strength=8, influence=influence)
    state = _state(
        owner,
        phase=GamePhase.COMBAT,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        decision_stack=(),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
    )
    return resolve_combat_rewards(state).state


def _influence_rows(found: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    rows = _rows(found, "choice")
    for key, row in rows.items():
        faction = row["action"]["arguments"]["faction"]
        assert key == f"choice:combat_reward_influence:{faction}"
    return {
        row["action"]["arguments"]["faction"]: (
            row["reason"],
            row["reason_ko"],
            row["code"],
        )
        for row in rows.values()
    }


def test_a_reward_with_every_faction_at_the_top_greys_them_beside_a_confirm() -> None:
    """OQ-060: the "choose a Faction" reward is lost when every track is at
    6, but the window opens (user ruling 2026-09-30, "결정 창 없이 자동으로
    넘어가는 곳도 모두 결정 창을 연다") with only the confirm, and every
    Faction greyed out "이미 최고치" on the "choice" surface."""

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _combat_reward("skirmish_crysknife", full)
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE
    assert ENGINE.legal_actions(state, 0) == (_INFLUENCE_CONFIRM,)
    found = _found(state)
    assert found["frame"] == FrameKind.COMBAT_REWARD_INFLUENCE
    assert {row["action"]["action_id"] for row in found["rows"]} == {
        "choose_combat_reward_influence"
    }
    assert _influence_rows(found) == {
        "emperor": _AT_THE_TOP,
        "spacing_guild": _AT_THE_TOP,
        "bene_gesserit": _AT_THE_TOP,
        "fremen": _AT_THE_TOP,
    }
    assert found["refs"] == {}

    confirmed = ENGINE.apply(state, _INFLUENCE_CONFIRM)
    assert "combat_reward_influence_unavailable" in {
        event.kind for event in confirmed.events
    }
    assert confirmed.state.players[0].influence == full


def test_a_faction_at_the_top_is_greyed_beside_the_ones_it_can_take() -> None:
    """A track at 6 can come down again (an Influence loss), so it shows
    greyed out in any reward window, not only the empty one (plan section 4,
    row 14)."""

    state = _combat_reward("spice_freighters", Influence(emperor=6, fremen=2))
    offered = _legal(state, "choose_combat_reward_influence")
    assert [args["faction"] for args in offered] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    assert _legal(state, "resolve_combat_influence_without_faction") == []
    assert _influence_rows(_found(state)) == {"emperor": _AT_THE_TOP}


def test_choose_two_greys_the_faction_it_already_named() -> None:
    """Propaganda's "Choose two" names two different Factions: after the
    first pick its second window greys that Faction out as named, and the
    tracks at 6 as at the top; the confirm then pays the named one."""

    state = _combat_reward(
        "propaganda", Influence(emperor=6, spacing_guild=6, bene_gesserit=6)
    )
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE
    first = _found(state)
    assert {row["action"]["action_id"] for row in first["rows"]} == {
        "choose_distinct_combat_reward_influence"
    }
    assert set(_influence_rows(first)) == {"emperor", "spacing_guild", "bene_gesserit"}
    named = ENGINE.apply(
        state,
        DomainAction(
            action_id="choose_distinct_combat_reward_influence",
            actor=0,
            arguments=(("faction", "fremen"),),
        ),
    ).state
    assert ENGINE.legal_actions(named, 0) == (_INFLUENCE_CONFIRM,)
    assert _influence_rows(_found(named)) == {
        "emperor": _AT_THE_TOP,
        "spacing_guild": _AT_THE_TOP,
        "bene_gesserit": _AT_THE_TOP,
        "fremen": (
            "Already named for this reward",
            "이 보상에서 이미 고른 진영",
            "named",
        ),
    }


def test_no_influence_row_while_every_faction_can_be_taken() -> None:
    state = _combat_reward("skirmish_crysknife", Influence())
    assert len(_legal(state, "choose_combat_reward_influence")) == 4
    assert unavailable_choices(state, 0, ENGINE.legal_actions(state, 0)) is None


# --- Whose decision ---


def test_nothing_is_greyed_out_for_a_seat_that_does_not_decide() -> None:
    state = _shop(0)

    assert unavailable_choices(state, 1, ENGINE.legal_actions(state, 1)) is None
    assert unavailable_choices(state, 0, ()) is not None  # the seat's own
    empty = _state(PlayerState(player_id=0))
    assert unavailable_choices(empty, 0, ENGINE.legal_actions(empty, 0)) is None


def test_no_reason_is_the_generic_fallback() -> None:
    state = _intrigue_state(
        "imperium_politics", "councilor_s_ambition", "sietch_ritual", "spice_is_power"
    )
    for found in (_found(state), _found(_shop(0))):
        whys = [*found["rows"], *found["refs"].values()]
        assert whys
        assert all(why["code"] != NOT_NOW_CODE for why in whys)


def test_the_text_fallbacks_carry_the_fallback_code() -> None:
    """The "Cannot pay: ..." and "Nothing to do now: ..." texts are fallbacks
    for a block no specific reason covers yet. They carry ``NOT_NOW_CODE``,
    so the check above and the seeded sweep in
    test_unavailable_consistency.py fail on them. None is reachable from a
    printed card today, so blocks the provider never returns drive them."""

    pay = PayResources(solari=1)
    gain = GainResources(solari=1)
    option = IntrigueOption(
        timing=IntrigueTiming.PLOT,
        sections=(EffectSection(rewards=(gain,), costs=(pay,)),),
    )
    rich = _intrigue_state(resources=Resources(solari=1))

    cost = intrigue_option_reason(rich, 0, option, pay)
    assert cost[0].startswith("Cannot pay: ") and cost[2] == NOT_NOW_CODE
    reward = intrigue_option_reason(rich, 0, option, gain)
    assert reward[0].startswith("Nothing to do now: ") and reward[2] == NOT_NOW_CODE
    # The resource check blocked, yet nothing is short.
    short = intrigue_option_reason(rich, 0, option, OptionBlock.COST)
    assert short[0].startswith("Cannot pay: ") and short[2] == NOT_NOW_CODE
    for english, korean, _ in (cost, reward, short):
        assert korean and english != korean


# --- Arrakeen Scouts: the new High Council seat's subcommittee choice -------------

DAGGER = "player:0:starter:dagger:0"


def _council_seat(spice: int, display: tuple[str, ...]) -> GameState:
    """Seat 0 sent the Dagger to the High Council and took the seat: its
    subcommittee choice is one more effect of the visit (OQ-076)."""

    owner = PlayerState(
        player_id=0,
        hand=(DAGGER,),
        resources=Resources(solari=5, spice=spice, water=1),
    )
    state = _state(
        owner,
        config=RulesetConfig(arrakeen_scouts=True),
        round_number=2,
        scouts_subcommittees=display,
    )
    for action in (
        DomainAction(
            action_id="agent_turn",
            actor=0,
            arguments=(("card_id", DAGGER), ("space_id", "high_council")),
        ),
        DomainAction(
            action_id="resolve_board_effect",
            actor=0,
            arguments=(("effect", "high_council"),),
        ),
    ):
        state = ENGINE.apply(state, action).state
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    return state


def test_a_subcommittee_choice_nothing_can_meet_waits_greyed_out() -> None:
    """``choose_subcommittee`` is offered exactly when a subcommittee can be
    joined now; while none can, the row says why and the decline stays."""
    several = _council_seat(0, ("oversight", "relations", "leverage"))
    assert _legal(several, "choose_subcommittee") == []
    assert _legal(several, "decline_subcommittee") == [{}]
    row = _rows(_found(several), "waiting")["waiting:choose_subcommittee"]
    assert row["action"]["action_id"] == "choose_subcommittee"
    assert row["reason"] == "No subcommittee you can join now"
    assert row["reason_ko"] == "지금 가입할 수 있는 소위원회 없음"
    assert row["code"] == "subcommittee"
    # One subcommittee left: its own reason, by name.
    one = _council_seat(1, ("relations",))
    row = _rows(_found(one), "waiting")["waiting:choose_subcommittee"]
    assert row["reason"] == "Relations: Needs 2 spice (you have 1)"
    assert row["reason_ko"].startswith("외교: ")
    assert row["code"] == "cost"


def test_the_subcommittee_row_goes_once_one_can_be_joined() -> None:
    state = _council_seat(2, ("relations",))
    assert _legal(state, "choose_subcommittee") == [{}]
    found = unavailable_choices(state, 0, ENGINE.legal_actions(state, 0))
    rows = found["rows"] if found is not None else []
    assert isinstance(rows, list)
    assert "waiting:choose_subcommittee" not in {row["key"] for row in rows}
