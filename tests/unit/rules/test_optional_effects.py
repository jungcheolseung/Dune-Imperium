"""Optional effects of the Agent turn: no refusal, lapse at the turn end.

Effects are mandatory unless they say "may", pay an arrow's cost or show the
black trash icon [FAQ p. 3] (docs/rules/official-rulings-index.md "optional
effects"), and the turn end is offered once every mandatory effect is done
(OQ-095 (2)). User ruling 2026-10-14: an optional effect left unused needs no
refusal and does not hold the end back; the press lapses it.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.board_effects import (
    BOARD_ICON_IMPERIAL_PRIVILEGE,
    BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
    BOARD_ICON_TRASH,
)
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    BOARD_ICON_TECH,
    OPTIONAL_BOARD_ICONS,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.scouts_offers import BOARD_ICON_SUBCOMMITTEE

ENGINE = UprisingRulesEngine()
FINISH = DomainAction(action_id="finish_agent_turn", actor=0)
# The space's own steps every test resolves before looking at the box.
MANDATORY_SPACE_STEPS = ("resolve_board_effect", "resolve_faction_influence")


def _imperium(card_id: str) -> str:
    return next(
        instance
        for instance in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance
    )


def _state(hand: tuple[str, ...], **owner: object) -> GameState:
    values: dict[str, object] = {"player_id": 0, "hand": hand}
    values.update(owner)
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        players=(
            PlayerState(**values),  # type: ignore[arg-type]
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


def _send(state: GameState, space_id: str, card_id: str | None = None) -> GameState:
    """Send an Agent to ``space_id``, then resolve the space's own steps."""

    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == space_id
        and (card_id is None or dict(action.arguments)["card_id"] == card_id)
        and len(action.arguments) == 2
    )
    state = ENGINE.apply(state, placement).state
    while True:
        step = next(
            (
                action
                for action in ENGINE.legal_actions(state, 0)
                if action.action_id in MANDATORY_SPACE_STEPS
            ),
            None,
        )
        if step is None:
            return state
        state = ENGINE.apply(state, step).state


def _ids(state: GameState) -> set[str]:
    return {action.action_id for action in ENGINE.legal_actions(state, 0)}


def test_an_unaffordable_optional_box_lapses_at_the_turn_end() -> None:
    """Smuggler's Haven, "You may pay 4 spice -> Gain 1 VP", with 3 spice:
    nothing to answer, so the end is offered at once and the press lapses
    the box. Before codec v146 only its refusal was offered and the end
    waited for it."""

    haven = _imperium("smuggler_s_haven")
    state = _send(_state((haven,), resources=Resources(spice=3)), "deliver_supplies")
    legal = _ids(state)
    assert "decline_agent_card_payment" not in legal
    assert "pay_agent_card_spice" not in legal
    assert FINISH.action_id in legal
    before = state.players[0]
    finished = ENGINE.apply(state, FINISH)
    lapsed = [
        event for event in finished.events if event.kind == "agent_card_effect_lapsed"
    ]
    assert [dict(event.payload)["card_id"] for event in lapsed] == [haven]
    owner = finished.state.players[0]
    assert (owner.resources.spice, owner.victory_points) == (
        3,
        before.victory_points,
    )


def test_an_affordable_optional_box_is_offered_beside_the_turn_end() -> None:
    """With 5 spice the payment is offered, and so is the end: the box is
    optional, so the owner answers it by paying or by ending the turn."""

    haven = _imperium("smuggler_s_haven")
    state = _send(_state((haven,), resources=Resources(spice=5)), "deliver_supplies")
    legal = _ids(state)
    assert {"pay_agent_card_spice", FINISH.action_id} <= legal
    assert "decline_agent_card_payment" not in legal
    paid = ENGINE.apply(state, DomainAction("pay_agent_card_spice", 0)).state
    assert paid.players[0].victory_points == state.players[0].victory_points + 1
    finished = ENGINE.apply(paid, FINISH)
    assert "agent_card_effect_lapsed" not in {event.kind for event in finished.events}


def test_desert_tactics_trash_is_offered_without_a_refusal() -> None:
    """Desert Tactics' black trash icon is optional [Main p. 20]: the trash
    rows stand beside the end, and the press lapses the unused icon."""

    hand = starting_deck_instance_ids(0)
    state = _send(_state(hand, resources=Resources(water=1)), "desert_tactics")
    legal = _ids(state)
    assert "trash_card_for_desert_tactics" in legal
    assert "resolve_desert_tactics_without_trash" not in legal
    assert FINISH.action_id in legal
    finished = ENGINE.apply(state, FINISH)
    lapsed = [event for event in finished.events if event.kind == "board_effect_lapsed"]
    assert [dict(event.payload)["effect"] for event in lapsed] == [BOARD_ICON_TRASH]


def test_imperial_privilege_offers_its_trade_and_its_recall_together() -> None:
    """The Intrigue trade (an arrow) and the recall are separate printed
    effects in any order [Main p. 9]: both are offered from the start, the
    trade without a refusal. Before codec v146 the trade (or its refusal)
    came first and gated the recall."""

    hand = starting_deck_instance_ids(0)
    intrigue = intrigue_deck_instance_ids(False)[0]
    state = _state(
        hand,
        resources=Resources(solari=3),
        influence=Influence(emperor=2),
        intrigue_cards=(intrigue,),
        agent_locations=("arrakeen",),
        agents_available=1,
    )
    state = replace(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != intrigue)
    )
    state = _send(state, "imperial_privilege")
    legal = _ids(state)
    assert {
        "trash_intrigue_for_imperial_privilege",
        "recall_agent_for_imperial_privilege",
    } <= legal
    assert "decline_imperial_privilege_intrigue" not in legal
    # The recall is mandatory: the end waits for it.
    assert FINISH.action_id not in legal
    recalled = ENGINE.apply(
        state,
        DomainAction(
            "recall_agent_for_imperial_privilege", 0, (("space_id", "arrakeen"),)
        ),
    ).state
    assert "trash_intrigue_for_imperial_privilege" in _ids(recalled)
    finished = ENGINE.apply(recalled, FINISH)
    lapsed = [event for event in finished.events if event.kind == "board_effect_lapsed"]
    assert [dict(event.payload)["effect"] for event in lapsed] == [
        BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE
    ]
    assert finished.state.players[0].intrigue_cards == (intrigue,)


def test_a_spy_placement_passed_up_keeps_its_refusal() -> None:
    """A Spy placement is mandatory; with an empty supply only the recall
    that would refill it is optional, and passing it up is decided when the
    box resolves (OQ-057 (14)): the refusal stays and the end waits."""

    operative = _imperium("bene_gesserit_operative")
    start = _state(
        (operative,),
        spies_supply=0,
        spy_post_ids=(
            "emperor-sardaukar-dutiful-service",
            "landsraad-assembly-hall-gather-support",
            "choam-shipping-accept-contract",
        ),
    )
    space_id = next(
        dict(action.arguments)["space_id"]
        for action in ENGINE.legal_actions(start, 0)
        if action.action_id == "agent_turn" and len(action.arguments) == 2
    )
    state = _send(start, str(space_id))
    legal = _ids(state)
    assert "decline_agent_card_spy" in legal
    assert FINISH.action_id not in legal


def _lapses(events: tuple[GameEvent, ...]) -> list[str]:
    """The lapse events' ids, in order."""

    return [event.event_id for event in events if event.kind.endswith("_lapsed")]


def test_other_memories_offers_no_refusal_and_waits_any_time_in_the_turn() -> None:
    """Other Memories, "you may return all your memories" [Lady Jessica
    card] after a Bene Gesserit placement: used whenever the owner likes in
    the turn (user ruling 2026-10-14, "기존대로 턴 중에 원할 때"), with no
    refusal and no hold on the end (OQ-095 (2)). Used last, beside the end,
    it still flips and draws, and the Reverend Mother repeat it opens lapses
    at the press when it cannot be paid; left unused, it lapses itself."""

    diplomacy = "player:0:starter:diplomacy:0"
    deck = ("player:0:starter:dagger:0", "player:0:starter:dagger:1")
    jessica = {
        "leader_id": "lady_jessica",
        "leader_face_id": "lady_jessica",
        "resources": Resources(spice=1, water=0),
        "memories": 2,
        "troops_supply": 7,
        "deck": deck,
    }
    state = _send(_state((diplomacy,), **jessica), "espionage", diplomacy)
    # Espionage's Spy is mandatory; the ability is offered throughout.
    while FINISH.action_id not in _ids(state):
        assert "use_other_memories" in _ids(state)
        state = ENGINE.apply(
            state,
            next(
                action
                for action in ENGINE.legal_actions(state, 0)
                if action.action_id == "resolve_espionage_place_spy"
            ),
        ).state
    assert _ids(state) == {"use_other_memories", FINISH.action_id}

    unused = ENGINE.apply(state, FINISH)
    assert _lapses(unused.events) == [
        "round:1:player:0:board:espionage:other_memories:lapsed"
    ]
    assert unused.state.players[0].leader_face_id == "lady_jessica"

    used = ENGINE.apply(state, DomainAction("use_other_memories", 0)).state
    owner = used.players[0]
    assert (owner.leader_face_id, owner.memories) == ("reverend_mother_jessica", 0)
    assert set(deck) <= set(owner.hand)
    # The repeat costs one water, which the seat lacks: nothing to answer.
    assert _ids(used) == {FINISH.action_id}
    finished = ENGINE.apply(used, FINISH)
    assert _lapses(finished.events) == [
        "round:1:player:0:board:espionage:board_repeat:lapsed"
    ]
    assert {
        event.payload for event in finished.events if event.kind.endswith("_lapsed")
    } == {(("player", 0),)}


def test_the_repeat_lapses_an_unused_desert_tactics_trash_first() -> None:
    """Reverend Mother's repeat ("Once during each turn" … water 1 → repeat
    [Reverend Mother Jessica card]) paid while Desert Tactics' optional
    trash is unused: that trash lapses (``board_effect_lapsed``) before the
    repeat arms the printed icons again, so the turn shows one trash
    unused, then a second one -- as declining it before the repeat did
    before codec v146 (OQ-095 (2), user ruling 2026-10-14)."""

    hand = starting_deck_instance_ids(0)
    reverend = {
        "leader_id": "lady_jessica",
        "leader_face_id": "reverend_mother_jessica",
        "resources": Resources(water=2),
    }
    state = _send(_state(hand, **reverend), "desert_tactics")
    pay = DomainAction("pay_leader_board_repeat", 0)
    assert {pay.action_id, "trash_card_for_desert_tactics", FINISH.action_id} <= (
        _ids(state)
    )

    repeated = ENGINE.apply(state, pay)

    assert [event.kind for event in repeated.events] == [
        "board_effect_lapsed",
        "leader_board_repeat_paid",
    ]
    assert dict(repeated.events[0].payload) == {
        "effect": BOARD_ICON_TRASH,
        "player": 0,
        "space_id": "desert_tactics",
    }
    # The repeated troop is mandatory; the re-armed trash is optional again.
    again = repeated.state
    assert "trash_card_for_desert_tactics" in _ids(again)
    assert FINISH.action_id not in _ids(again)
    again = _send_steps(again)
    finished = ENGINE.apply(again, FINISH)
    assert _lapses(finished.events) == [
        "round:1:player:0:board:desert_tactics:trash:lapsed"
    ]
    assert finished.state.players[0].trashed == ()


def _send_steps(state: GameState) -> GameState:
    """Resolve the space's own mandatory steps still pending."""

    while step := next(
        (
            action
            for action in ENGINE.legal_actions(state, 0)
            if action.action_id in MANDATORY_SPACE_STEPS
        ),
        None,
    ):
        state = ENGINE.apply(state, step).state
    return state


def test_the_optional_board_icons_name_their_modules_constants() -> None:
    assert OPTIONAL_BOARD_ICONS == {
        BOARD_ICON_TRASH,
        BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
        BOARD_ICON_COMMANDER,
        BOARD_ICON_TECH,
        BOARD_ICON_SUBCOMMITTEE,
    }
    assert BOARD_ICON_IMPERIAL_PRIVILEGE not in OPTIONAL_BOARD_ICONS
