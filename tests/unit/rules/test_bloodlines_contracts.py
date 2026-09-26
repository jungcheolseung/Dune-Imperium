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
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.contracts import (
    begin_contract_gain,
    complete_alliance_contracts,
    legal_contract_actions,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_triggers import (
    apply_trigger_contract_action,
    legal_trigger_contract_actions,
    offer_deployment_triggers,
)
from dune_imperium.rules.reveal_turn import legal_reveal_deployments
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
    # The trigger is mandatory [Coercive Negotiation card; FAQ p. 3], so
    # only the takeable Contracts are offered, with no decline.
    assert [
        dict(action.arguments).get("instance_id")
        for action in legal_trigger_contract_actions(without, 0)
    ] == ["contract:arrakeen_i", "contract:arrakeen_ii"]

    holding = offered(
        _owner(
            intrigue_faceup=(card,),
            intrigue_cards=INTRIGUE[:1],
            units_deployed_turn=3,
        )
    )
    actions = legal_trigger_contract_actions(holding, 0)
    assert dict(actions[0].arguments)["instance_id"] == IMMEDIATE
    taken = apply_trigger_contract_action(holding, actions[0]).state
    assert taken.decision_stack[-1].kind == "contract_intrigue_trash"
    assert taken.players[0].active_contract_ids == (IMMEDIATE,)
    assert taken.contract_trash == ("contract:arrakeen_i", "contract:arrakeen_ii")
    assert taken.contract_bank == ("contract:secrets",)


# OQ-064, user ruling 2026-09-26: "책략은 명백히 리필된다는 룰이 있지만,
# 계약은 리필되는 수단이 없으니 3장이 없으면 Coercive Negotiation을 아예 사용할
# 수 없는게 맞다고 보여진다. 사용 후 효과가 없는게 아니라 아예 사용을 못
# 하는거지". The card reads "Reveal three contracts from the bank. Take one
# and trash the other two." [Coercive Negotiation card]; Intrigue cards
# reshuffle when their deck runs out [FAQ p. 2], Contracts never do.

COERCIVE = next(card for card in INTRIGUE if ":coercive_negotiation:" in card)
THREE_BANK = ("contract:arrakeen_i", "contract:arrakeen_ii", "contract:espionage_i")


def _plays_coercive(state: GameState) -> bool:
    from dune_imperium.rules.intrigue import legal_intrigue_play_actions

    return any(
        dict(action.arguments)["card_id"] == COERCIVE
        for action in legal_intrigue_play_actions(state, 0)
    )


@pytest.mark.parametrize("bank", [(), (IMMEDIATE,), THREE_BANK[:2]])
def test_coercive_negotiation_cannot_be_played_with_fewer_than_three_contracts(
    bank: tuple[str, ...],
) -> None:
    held = _owner(intrigue_cards=(COERCIVE,))
    assert not _plays_coercive(_state(held, market=(), bank=bank))
    assert _plays_coercive(_state(held, market=(), bank=THREE_BANK))


def test_coercive_negotiation_face_up_never_triggers_with_fewer_than_three() -> None:
    # Played while the bank still held three, then the bank ran down: the
    # face-up card cannot be used, even with an Intrigue card in hand for
    # the Immediate token, and it stays face up.
    for bank in ((IMMEDIATE,), THREE_BANK[:2]):
        base = _state(
            _owner(
                intrigue_faceup=(COERCIVE,),
                intrigue_cards=INTRIGUE[:1],
                units_deployed_turn=3,
            ),
            market=(),
            bank=bank,
        )
        waiting = offer_deployment_triggers(RuleResult(state=base)).state
        assert waiting.decision_stack == base.decision_stack
        assert waiting.players[0].intrigue_faceup == (COERCIVE,)
        assert waiting.contract_bank == bank
    # With three in the bank one is always takeable (the single Immediate
    # token is the only Contract that needs an Intrigue card [Bloodlines
    # p. 2]), so the same deployment opens it at once.
    three = _state(
        _owner(intrigue_faceup=(COERCIVE,), units_deployed_turn=3),
        market=(),
        bank=(IMMEDIATE, *THREE_BANK[:2]),
    )
    opened = offer_deployment_triggers(RuleResult(state=three)).state
    assert opened.decision_stack[-1].kind == FrameKind.INTRIGUE_TRIGGER_CONTRACT
    assert [
        dict(action.arguments)["instance_id"]
        for action in legal_trigger_contract_actions(opened, 0)
    ] == list(THREE_BANK[:2])


def test_coercive_negotiation_with_three_contracts_opens_beside_distraction() -> None:
    # Coercive Negotiation is mandatory, so the offer record that stops a
    # declined Distraction from being offered again at the same count
    # (OQ-016 (c)) never holds it back; a pending frame is not pushed twice.
    distraction = next(card for card in INTRIGUE if ":distraction:" in card)
    base = _state(
        _owner(intrigue_faceup=(COERCIVE, distraction), units_deployed_turn=3),
        market=(),
        bank=THREE_BANK,
    )
    opened = offer_deployment_triggers(RuleResult(state=base)).state
    pushed = opened.decision_stack[len(base.decision_stack) :]
    assert FrameKind.INTRIGUE_TRIGGER_CONTRACT in [frame.kind for frame in pushed]
    again = offer_deployment_triggers(RuleResult(state=opened)).state
    assert again.decision_stack == opened.decision_stack


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
    # 3 starting troops + the tile's two; the Emperor track's Influence 4
    # bonus is a Spy [Main p. 7], placed at once in its own frame.
    assert owner.troops_garrison == 5
    assert result.state.decision_stack[-1].kind == "spy_placement"
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


def _closing_alliance_state() -> GameState:
    """Seat 0 is one Influence bump from completing Earn Any Alliance, and
    that bump is the Agent turn's last pending effect with every other seat
    already revealed -- ``advance_after_effect`` then reopens seat 0's own
    next "turn" frame in the same step."""

    return _state(
        _owner(
            influence=Influence(spacing_guild=3),
            active_contract_ids=(EARN_ALLIANCE,),
        ),
        market=(),
        opponents=(
            PlayerState(player_id=1, has_revealed=True),
            PlayerState(player_id=2, has_revealed=True),
            PlayerState(player_id=3, has_revealed=True),
        ),
    )


def test_earn_any_alliance_does_not_join_the_next_agent_turns_allowance() -> None:
    # "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수
    # 있다. 이미 garrison에 있던 troop을 다시 recruit한 것으로 취급해 두 개
    # 제한을 우회할 수는 없다" [Main p. 10] [FAQ p. 4]
    # (docs/rules/player-turns.md:137). Deliver Supplies is a Spacing Guild
    # space with no automatic troop recruit [Main p. 7], so its
    # ``resolve_faction_influence`` (Guild 3 -> 4) is the turn's very last
    # pending effect; with seats 1-3 already revealed,
    # ``next_unrevealed_player`` reopens seat 0's own next "turn" frame in
    # the same step Earn Any Alliance completes -- the engine used to let
    # ``complete_alliance_contracts`` credit that fresh frame with the
    # completion's 2 troops instead of leaving it uncredited there.
    engine = UprisingRulesEngine()
    placed = _place(_closing_alliance_state(), "deliver_supplies")
    with_water = engine.apply(placed, _board_effect(placed, engine, "resources")).state

    result = engine.apply(
        with_water, DomainAction(action_id="resolve_faction_influence", actor=0)
    ).state

    owner = result.players[0]
    assert owner.influence.spacing_guild == 4
    assert owner.alliance_faction_ids == ("spacing_guild",)
    assert owner.completed_contract_ids == (EARN_ALLIANCE,)
    assert owner.troops_garrison == 3 + 2
    top = result.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    assert dict(top.context)["turn_owner"] == 0
    assert dict(top.context).get("troops_recruited") in (None, 0)

    # Arrakeen recruits nothing on its own [Main p. 7]; the deploy window
    # opens on placement, before its printed icons resolve (OQ-027).
    next_placed = _place(result, "arrakeen")
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(next_placed, 0)
    ] == [1, 2]


def test_earn_any_alliance_does_not_join_a_later_reveals_allowance() -> None:
    # Same closed-turn scenario as above, but seat 0 picks a Reveal turn
    # next instead of another Agent turn. The fresh "turn" frame correctly
    # holds no troops_recruited (previous test), and
    # ``reveal_turn._begin_reveal_turn``'s carry of a closing turn frame's
    # recruits into the Reveal (``2d2fa81``, OQ-062) must carry that
    # (correct) zero, not the completion's 2 troops: Combat 아이콘 "이번
    # turn에 recruit한 유닛 전부와 garrison에서 최대 두 개 ... Reveal
    # turn에서도 쓸 수 있다" [Bloodlines pp. 5, 12].
    engine = UprisingRulesEngine()
    placed = _place(_closing_alliance_state(), "deliver_supplies")
    with_water = engine.apply(placed, _board_effect(placed, engine, "resources")).state
    result = engine.apply(
        with_water, DomainAction(action_id="resolve_faction_influence", actor=0)
    ).state
    assert result.decision_stack[-1].kind == FrameKind.TURN

    # The Combat icon is granted only now, after the turn has already
    # closed: setting it before placement would keep the deployment window
    # (and so the Agent-turn effect frame) open through this whole step.
    combat_icon_owner = replace(result.players[0], combat_icon_turn=True)
    with_combat_icon = replace(
        result, players=(combat_icon_owner, *result.players[1:])
    )
    revealed = engine.apply(
        with_combat_icon, DomainAction(action_id="reveal_turn", actor=0)
    ).state

    reveal_frame = next(
        frame for frame in revealed.decision_stack if frame.kind == FrameKind.REVEAL
    )
    assert dict(reveal_frame.context)["reveal_troops_recruited"] == 0
    assert [
        dict(a.arguments)["count"]
        for a in legal_reveal_deployments(revealed, 0)
        if a.action_id == "deploy_troops"
    ] == [1, 2]


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


def test_deliver_supplies_spy_without_supply_may_pass_up_the_recall_first() -> None:
    # A Spy with Deep Cover is still a Spy icon: "If you have no Spies in
    # your supply, you may first recall one of your Spies for no effect"
    # [Main pp. 11, 20] (optional, docs/rules/uprising-systems.md, OQ-057
    # (14)); "Spy with Deep Cover: 일반 규칙대로 Spy 하나를 놓되, 놓을 때
    # 상대의 Spy를 무시할 수 있다" [Bloodlines pp. 5, 12].
    engine = UprisingRulesEngine()
    watched = "arrakis-hagga-basin"
    own_posts = (
        "emperor-sardaukar-dutiful-service",
        "arrakis-deep-desert",
        "arrakis-imperial-basin",
    )
    state = _state(
        _owner(
            spies_supply=0,
            spy_post_ids=own_posts,
            active_contract_ids=(DELIVER_SUPPLIES,),
        ),
        opponents=(
            PlayerState(player_id=1, spies_supply=2, spy_post_ids=(watched,)),
        ),
    )
    placed = _place(state, "deliver_supplies")
    completion = next(
        action
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "complete_contract"
    )
    completed = engine.apply(placed, completion).state
    actions = engine.legal_actions(completed, 0)
    assert [action.action_id for action in actions] == [
        "decline_contract_spy",
        *("recall_spy_for_contract",) * 3,
    ]

    declined = engine.apply(completed, actions[0]).state
    assert declined.players[0].spy_post_ids == own_posts
    assert declined.decision_stack[-1].kind == "agent_effects"

    recalled = engine.apply(completed, actions[1]).state
    targets = {
        dict(action.arguments)["post_id"]
        for action in engine.legal_actions(recalled, 0)
        if action.action_id == "place_contract_spy"
    }
    assert {action.action_id for action in engine.legal_actions(recalled, 0)} == {
        "place_contract_spy"
    }
    # Deep Cover: the opponent's post is open, the owner's own are not.
    assert watched in targets
    assert own_posts[0] in targets
    assert not targets & set(own_posts[1:])


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
