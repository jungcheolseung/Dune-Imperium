"""Tests for the eight Bloodlines contract tokens (CHOAM Module).

The tokens shuffle into the standard bank; Earn Any Alliance completes on
the next new Alliance token and the new Immediate needs an Intrigue card
to trash [Bloodlines p. 2]. Faces are transcribed in
``docs/rules/bloodlines.md``.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.contracts import contract_instance_ids
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
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.contracts import (
    begin_contract_gain,
    complete_alliance_contracts,
    legal_contract_actions,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_triggers import (
    apply_trigger_contract_action,
    legal_trigger_contract_actions,
    offer_deployment_triggers,
)
from dune_imperium.rules.setup import create_initial_state

CHOAM_BLOODLINES = RulesetConfig(bloodlines=True, choam_module=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
STARTERS = starting_deck_instance_ids(0)
INTRIGUE = intrigue_deck_instance_ids(True, bloodlines=True)
IMMEDIATE = "contract:bloodlines_immediate"
EARN_ALLIANCE = "contract:bloodlines_earn_any_alliance"
DELIVER_SUPPLIES = "contract:bloodlines_deliver_supplies"


def _owner(**overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "resources": Resources(solari=10, spice=10, water=10),
        "deck": STARTERS[:3],
        "hand": STARTERS[3:],
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(
    owner: PlayerState,
    *,
    market: tuple[str, ...] = ("contract:arrakeen_i", "contract:high_council_ii"),
    bank: tuple[str, ...] = (),
    intrigue_deck: tuple[str, ...] = (),
    opponents: tuple[PlayerState, ...] = (),
) -> GameState:
    others = {seat.player_id: seat for seat in opponents}
    return GameState(
        config=CHOAM_BLOODLINES,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            *(others.get(seat, PlayerState(player_id=seat)) for seat in range(1, 4)),
        ),
        sardaukar_commander_space_ids=(),
        sardaukar_commanders_bank=1,
        contract_bank=bank,
        face_up_contract_ids=market,
        intrigue_deck=intrigue_deck,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _place(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_agent_action(state, action).state


def _board_effect(
    state: GameState, engine: UprisingRulesEngine, key: str
) -> DomainAction:
    return next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "resolve_board_effect"
        and key in str(dict(action.arguments)["effect"])
    )


def _take(state: GameState, engine: UprisingRulesEngine, instance_id: str) -> GameState:
    action = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "take_contract"
        and dict(action.arguments)["instance_id"] == instance_id
    )
    return engine.apply(state, action).state


def test_bloodlines_setup_shuffles_the_eight_tokens_into_the_same_bank() -> None:
    first = create_initial_state(CHOAM_BLOODLINES, seed=7, leader_ids=LEADERS)
    replayed = create_initial_state(
        CHOAM_BLOODLINES,
        seed=999,
        leader_ids=LEADERS,
        recorded_outcomes=first.chance_outcomes,
    )

    assert len(first.state.face_up_contract_ids) == 2
    assert len(first.state.contract_bank) == 26
    assert set((*first.state.face_up_contract_ids, *first.state.contract_bank)) == set(
        contract_instance_ids(bloodlines=True)
    )
    assert replace(replayed.state, seed=first.state.seed) == first.state

    standard = create_initial_state(
        RulesetConfig(choam_module=True), seed=7, leader_ids=LEADERS
    ).state
    assert set((*standard.face_up_contract_ids, *standard.contract_bank)) == set(
        contract_instance_ids()
    )


def test_immediate_cannot_be_taken_without_an_intrigue_card_in_hand() -> None:
    without = begin_contract_gain(
        _state(_owner(), market=(IMMEDIATE, "contract:arrakeen_i")),
        0,
        1,
        source="round:1:test",
    ).state
    assert [
        dict(action.arguments)["instance_id"]
        for action in legal_contract_actions(without, 0)
    ] == ["contract:arrakeen_i"]

    holding = begin_contract_gain(
        _state(
            _owner(intrigue_cards=INTRIGUE[:1]),
            market=(IMMEDIATE, "contract:arrakeen_i"),
        ),
        0,
        1,
        source="round:1:test",
    ).state
    assert [
        dict(action.arguments)["instance_id"]
        for action in legal_contract_actions(holding, 0)
    ] == [IMMEDIATE, "contract:arrakeen_i"]


def test_immediate_trashes_a_chosen_intrigue_card_then_draws_both_rewards() -> None:
    engine = UprisingRulesEngine()
    state = begin_contract_gain(
        _state(
            _owner(intrigue_cards=INTRIGUE[:2]),
            market=(IMMEDIATE, "contract:arrakeen_i"),
            bank=("contract:secrets",),
            intrigue_deck=INTRIGUE[5:8],
        ),
        0,
        1,
        source="round:1:test",
    ).state

    taken = _take(state, engine, IMMEDIATE)
    owner = taken.players[0]
    assert taken.decision_stack[-1].kind == "contract_intrigue_trash"
    # The tile waits in the active zone only while the trash is chosen.
    assert owner.active_contract_ids == (IMMEDIATE,)
    assert owner.completed_contract_ids == ()
    assert taken.face_up_contract_ids == ("contract:secrets", "contract:arrakeen_i")
    trashes = engine.legal_actions(taken, 0)
    assert [action.action_id for action in trashes] == [
        "trash_intrigue_for_contract",
        "trash_intrigue_for_contract",
    ]
    assert [dict(action.arguments)["card_id"] for action in trashes] == list(
        INTRIGUE[:2]
    )

    result = engine.apply(taken, trashes[1])
    owner = result.state.players[0]
    assert owner.active_contract_ids == ()
    assert owner.intrigue_cards == (INTRIGUE[0], INTRIGUE[5])
    assert result.state.intrigue_trash == (INTRIGUE[1],)
    assert result.state.intrigue_deck == INTRIGUE[6:8]
    assert len(owner.hand) == len(STARTERS[3:]) + 1
    assert owner.deck == STARTERS[1:3]
    assert owner.completed_contract_ids == (IMMEDIATE,)
    assert owner.contracts_completed_turn == 1
    assert result.state.decision_stack[-1].kind == "turn"
    assert [event.kind for event in result.events][:2] == [
        "intrigue_card_trashed",
        "contract_completed",
    ]


def test_coercive_negotiation_offers_the_immediate_only_with_hand_intrigue() -> None:
    card = next(card for card in INTRIGUE if ":coercive_negotiation:" in card)
    bank = (
        IMMEDIATE,
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
        "contract:secrets",
    )

    def offered(owner: PlayerState) -> GameState:
        base = _state(owner, market=(), bank=bank)
        return offer_deployment_triggers(RuleResult(state=base)).state

    without = offered(_owner(intrigue_faceup=(card,), units_deployed_turn=3))
    assert [
        dict(action.arguments).get("instance_id")
        for action in legal_trigger_contract_actions(without, 0)
    ] == [None, "contract:arrakeen_i", "contract:arrakeen_ii"]

    holding = offered(
        _owner(
            intrigue_faceup=(card,),
            intrigue_cards=INTRIGUE[:1],
            units_deployed_turn=3,
        )
    )
    actions = legal_trigger_contract_actions(holding, 0)
    assert dict(actions[1].arguments)["instance_id"] == IMMEDIATE
    taken = apply_trigger_contract_action(holding, actions[1]).state
    assert taken.decision_stack[-1].kind == "contract_intrigue_trash"
    assert taken.players[0].active_contract_ids == (IMMEDIATE,)
    assert taken.contract_trash == ("contract:arrakeen_i", "contract:arrakeen_ii")
    assert taken.contract_bank == ("contract:secrets",)


def test_earn_any_alliance_taken_this_turn_completes_on_this_turns_bump() -> None:
    # The designer's ruling (BGG): a contract taken this turn can complete on
    # this turn's Influence bump; the Agent-visit snapshot [Main p. 16] does
    # not apply because the condition is the Alliance itself.
    engine = UprisingRulesEngine()
    state = _state(
        _owner(influence=Influence(emperor=3)),
        market=(EARN_ALLIANCE, "contract:arrakeen_i"),
        bank=("contract:secrets",),
    )
    placed = _place(state, "dutiful_service")

    with_contract = engine.apply(
        placed, _board_effect(placed, engine, "contract")
    ).state
    with_contract = _take(with_contract, engine, EARN_ALLIANCE)
    assert with_contract.players[0].active_contract_ids == (EARN_ALLIANCE,)

    result = engine.apply(
        with_contract,
        DomainAction(action_id="resolve_faction_influence", actor=0),
    )
    owner = result.state.players[0]
    assert owner.influence.emperor == 4
    assert owner.alliance_faction_ids == ("emperor",)
    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == (EARN_ALLIANCE,)
    assert owner.resources.solari == 12
    # 3 starting troops + the Emperor track's two at 4 Influence + the tile's two.
    assert owner.troops_garrison == 7
    assert [
        event.kind for event in result.events if event.kind.startswith("contract")
    ] == ["contract_completed"]


def test_earn_any_alliance_recruits_join_the_turn_owners_deployment_allowance() -> None:
    state = _state(_owner(active_contract_ids=(EARN_ALLIANCE,)), market=())
    placed = _place(state, "dutiful_service")
    effects = placed.decision_stack[-1]
    assert effects.kind == "agent_effects"
    assert dict(effects.context)["troops_recruited"] == 0
    alliance = GameEvent(
        event_id="test:alliance",
        kind="alliance_gained",
        payload=(("faction", "fremen"), ("from_player", -1), ("to_player", 0)),
    )

    completed = complete_alliance_contracts(
        RuleResult(state=placed, events=(alliance,))
    )
    owner = completed.state.players[0]
    assert owner.completed_contract_ids == (EARN_ALLIANCE,)
    assert owner.troops_garrison == 3 + 2
    assert dict(completed.state.decision_stack[-1].context)["troops_recruited"] == 2

    # Another seat's Alliance never touches the turn owner's allowance.
    other = GameEvent(
        event_id="test:alliance:2",
        kind="alliance_gained",
        payload=(("faction", "fremen"), ("from_player", -1), ("to_player", 2)),
    )
    rival = _place(
        _state(
            _owner(),
            market=(),
            opponents=(PlayerState(player_id=2, active_contract_ids=(EARN_ALLIANCE,)),),
        ),
        "dutiful_service",
    )
    rival_done = complete_alliance_contracts(RuleResult(state=rival, events=(other,)))
    assert rival_done.state.players[2].completed_contract_ids == (EARN_ALLIANCE,)
    assert rival_done.state.players[2].troops_garrison == 3 + 2
    assert dict(rival_done.state.decision_stack[-1].context)["troops_recruited"] == 0


def test_earn_any_alliance_waits_for_a_new_alliance_token() -> None:
    held = _state(
        _owner(
            influence=Influence(emperor=4),
            alliance_faction_ids=("emperor",),
            victory_points=2,
            active_contract_ids=(EARN_ALLIANCE,),
        ),
        market=(),
    )
    gained = gain_faction_influence(held, 0, Faction.EMPEROR, 1, event_prefix="test")
    unchanged = complete_alliance_contracts(gained)
    assert unchanged.state.players[0].active_contract_ids == (EARN_ALLIANCE,)
    assert unchanged.state.players[0].influence.emperor == 5

    # Taking the token from its current holder counts: the holder loses it
    # and the challenger "takes an Alliance token" they did not have.
    contested = _state(
        _owner(influence=Influence(emperor=4), active_contract_ids=(EARN_ALLIANCE,)),
        market=(),
        opponents=(
            PlayerState(
                player_id=2,
                influence=Influence(emperor=4),
                alliance_faction_ids=("emperor",),
                victory_points=2,
            ),
        ),
    )
    taken = complete_alliance_contracts(
        gain_faction_influence(contested, 0, Faction.EMPEROR, 1, event_prefix="test")
    )
    owner = taken.state.players[0]
    assert owner.alliance_faction_ids == ("emperor",)
    assert taken.state.players[2].alliance_faction_ids == ()
    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == (EARN_ALLIANCE,)
    assert owner.resources.solari == 12
    assert owner.troops_garrison == 3 + 2
    assert [event.kind for event in taken.events] == [
        "influence_gained",
        "alliance_transferred",
        "contract_completed",
    ]


def test_deliver_supplies_places_its_spy_with_deep_cover_over_an_opponent() -> None:
    engine = UprisingRulesEngine()
    post = next(
        post.post_id
        for post in OBSERVATION_POSTS
        if "deliver_supplies" in post.connected_space_ids
    )
    state = _state(
        _owner(spies_supply=3, active_contract_ids=(DELIVER_SUPPLIES,)),
        opponents=(PlayerState(player_id=1, spies_supply=2, spy_post_ids=(post,)),),
    )
    placed = _place(state, "dutiful_service")
    assert not any(
        action.action_id == "complete_contract"
        for action in engine.legal_actions(placed, 0)
    )

    placed = _place(state, "deliver_supplies")
    completion = next(
        action
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "complete_contract"
    )
    completed = engine.apply(placed, completion).state
    frame = completed.decision_stack[-1]
    assert frame.kind == "contract_reward_spy"
    assert dict(frame.context)["deep_cover"] is True
    assert completed.players[0].resources.solari == 11
    targets = {
        dict(action.arguments)["post_id"]
        for action in engine.legal_actions(completed, 0)
        if action.action_id == "place_contract_spy"
    }
    assert targets == {post.post_id for post in OBSERVATION_POSTS}
    assert post in targets

    spied = engine.apply(
        completed,
        DomainAction(
            action_id="place_contract_spy", actor=0, arguments=(("post_id", post),)
        ),
    ).state
    assert spied.players[0].spy_post_ids == (post,)
    assert spied.players[1].spy_post_ids == (post,)
    assert spied.players[0].completed_contract_ids == (DELIVER_SUPPLIES,)


@pytest.mark.parametrize(
    ("instance_id", "expected"),
    [
        ("contract:bloodlines_harvest_3", "Send an Agent to a Maker space"),
        ("contract:bloodlines_secrets", "Send an Agent to Secrets"),
    ],
)
def test_bloodlines_tiles_render_their_printed_conditions(
    instance_id: str, expected: str
) -> None:
    from dune_imperium.content.uprising.contracts import contract_for_instance
    from dune_imperium.display.structs import (
        contract_condition_text,
        contract_reward_text,
    )

    definition = contract_for_instance(instance_id)
    assert contract_condition_text(definition.condition).startswith(expected)
    assert contract_reward_text(definition.reward)
    assert contract_reward_text(
        contract_for_instance(IMMEDIATE).reward
    ) == "Draw 1 card, Draw 1 Intrigue card"
    assert contract_reward_text(contract_for_instance(DELIVER_SUPPLIES).reward) == (
        "Gain 1 solari, Place a Spy with Deep Cover"
    )


def test_an_unreachable_market_holds_the_icon_instead_of_paying_solari() -> None:
    # The market is not empty, so the printed conversion does not apply: "If
    # all contracts have been taken by players, the icon reverts to giving you
    # 2 Solari" [Main p. 16]. But the only token left is the Immediate, which
    # "cannot be taken without an Intrigue card to trash" [Bloodlines p. 2].
    # The icon waits for the turn instead of blocking it, and it pays nothing
    # (OQ-059, user ruling 2026-09-10).
    from dune_imperium.rules.contracts import (
        contract_icons_must_be_held,
        hold_contract_icons,
    )

    owner = _owner(intrigue_cards=())
    state = _state(owner, market=(IMMEDIATE,))
    opened = begin_contract_gain(state, 0, 1, source="probe").state

    assert legal_contract_actions(opened, 0) == ()
    assert contract_icons_must_be_held(opened)

    held = hold_contract_icons(opened)
    seat = held.state.players[0]
    assert seat.held_contract_icons == 1
    # No Solari, and the market is untouched.
    assert seat.resources.solari == owner.resources.solari
    assert held.state.face_up_contract_ids == (IMMEDIATE,)
    assert held.state.decision_stack[-1].kind != "contract_market"
    assert held.events[0].kind == "contract_icons_held"


def test_a_held_icon_reopens_when_an_intrigue_card_arrives() -> None:
    # Taking is not optional, so the icon must resolve if the turn makes it
    # possible (OQ-057(1)).
    from dune_imperium.rules.contracts import (
        held_contract_icons_can_open,
        open_held_contract_icons,
    )

    without = _owner(held_contract_icons=1, intrigue_cards=())
    state = _state(without, market=(IMMEDIATE,))
    assert not held_contract_icons_can_open(state, 0)

    gained = replace(
        state,
        players=(
            replace(without, intrigue_cards=(INTRIGUE[0],)),
            *state.players[1:],
        ),
    )
    assert held_contract_icons_can_open(gained, 0)

    reopened = open_held_contract_icons(gained, 0)
    assert reopened.state.players[0].held_contract_icons == 0
    assert reopened.state.decision_stack[-1].kind == "contract_market"
    assert dict(reopened.state.decision_stack[-1].context)["remaining"] == 1
    assert [a.action_id for a in legal_contract_actions(reopened.state, 0)] == [
        "take_contract"
    ]


def test_a_held_icon_fizzles_with_the_turn_and_pays_nothing() -> None:
    from dune_imperium.rules.contracts import fizzle_held_contract_icons

    owner = _owner(held_contract_icons=2, intrigue_cards=())
    state = _state(owner, market=(IMMEDIATE,))

    fizzled = fizzle_held_contract_icons(state, 0, source="probe")
    seat = fizzled.state.players[0]

    assert seat.held_contract_icons == 0
    assert seat.resources.solari == owner.resources.solari
    assert fizzled.events[0].kind == "contract_icons_fizzled"
    assert dict(fizzled.events[0].payload)["count"] == 2
    # Nothing to do when none are held.
    assert fizzle_held_contract_icons(fizzled.state, 0, source="probe").events == ()


def test_an_empty_market_still_converts_to_two_solari() -> None:
    # The held path must not swallow the printed conversion [Main p. 16].
    from dune_imperium.rules.contracts import contract_icons_must_be_held

    owner = _owner(intrigue_cards=())
    state = _state(owner, market=())
    result = begin_contract_gain(state, 0, 2, source="probe")

    assert result.state.players[0].resources.solari == owner.resources.solari + 4
    assert result.state.players[0].held_contract_icons == 0
    assert not contract_icons_must_be_held(result.state)
