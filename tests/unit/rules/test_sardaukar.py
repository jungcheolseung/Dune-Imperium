"""Tests for Bloodlines Sardaukar Commanders and their Skills.

Rule source: ``docs/rules/bloodlines.md`` section 3 [Bloodlines pp. 3-4] and
the Skill tile faces. The project convention for a Commander bought while no
face-up Skill is choosable is OQ-031.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    encode_player_view,
)
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_SETUP_SPACE_IDS,
    SKILL_FACE_UP,
    skill_for_instance,
    skill_tile_instance_ids,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
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
    RuleResult,
    observe_state,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.combat import finish_combat
from dune_imperium.rules.combat_deployment import (
    apply_combat_deployment,
    apply_commander_deployment,
    apply_commander_withdrawal,
    legal_combat_deployments,
    legal_commander_deployments,
    legal_commander_withdrawals,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.sardaukar import (
    apply_commander_recruit,
    apply_sardaukar_commander_action,
    apply_skill_trash,
    legal_commander_recruit_actions,
    legal_sardaukar_commander_actions,
    legal_skill_trash_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.rules.strength import refresh_pre_reveal_strength
from dune_imperium.simulation.sweep import run_checked_game

BLOODLINES = RulesetConfig(bloodlines=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
SKILLS = skill_tile_instance_ids()


def _skill(skill_id: str, copy: int = 0) -> str:
    return f"skill:{skill_id}:{copy}"


def _turn_state(
    owner: PlayerState,
    *,
    spaces: tuple[str, ...] = COMMANDER_SETUP_SPACE_IDS,
    face_up: tuple[str, ...] = tuple(SKILLS[:4]),
    stack: tuple[str, ...] = tuple(SKILLS[4:]),
    others: tuple[PlayerState, ...] | None = None,
) -> GameState:
    held = set(owner.skill_ids)
    face_up = tuple(skill for skill in face_up if skill not in held)
    stack = tuple(
        skill for skill in stack if skill not in held and skill not in face_up
    )
    return GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            *(others or tuple(PlayerState(player_id=seat) for seat in range(1, 4))),
        ),
        sardaukar_commander_space_ids=spaces,
        sardaukar_commanders_bank=1,
        skill_face_up=face_up,
        skill_stack=stack,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _owner(**overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "hand": starting_deck_instance_ids(0),
        "resources": Resources(solari=4, water=2),
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _agent_action_to(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )


def _visit(state: GameState, space_id: str) -> GameState:
    state = apply_agent_action(state, _agent_action_to(state, space_id)).state
    for action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, action).state
    return state


def _commander_actions(state: GameState) -> dict[str, DomainAction]:
    return {
        f"{action.action_id}:{dict(action.arguments).get('skill_id', '')}": action
        for action in legal_sardaukar_commander_actions(state, 0)
    }


# --- setup -----------------------------------------------------------------


def test_setup_places_six_commanders_and_deals_four_skills() -> None:
    state = create_initial_state(BLOODLINES, seed=3, leader_ids=LEADERS).state

    assert state.sardaukar_commander_space_ids == COMMANDER_SETUP_SPACE_IDS
    assert state.sardaukar_commanders_bank == 1
    assert len(state.skill_face_up) == SKILL_FACE_UP
    assert len(state.skill_stack) == len(SKILLS) - SKILL_FACE_UP
    assert set(state.skill_face_up) | set(state.skill_stack) == set(SKILLS)
    assert all(player.commanders_total == 0 for player in state.players)


def test_setup_without_bloodlines_has_no_commanders() -> None:
    state = create_initial_state(RulesetConfig(), seed=3, leader_ids=LEADERS).state

    assert state.sardaukar_commander_space_ids == ()
    assert state.skill_face_up == () and state.skill_stack == ()
    with pytest.raises(ValueError, match="require the Bloodlines expansion"):
        replace(state, sardaukar_commanders_bank=1)


def test_draft_setup_deals_the_skills_too() -> None:
    state = create_draft_initial_state(
        RulesetConfig(bloodlines=True, leader_draft=True), seed=5
    ).state

    assert state.sardaukar_commander_space_ids == COMMANDER_SETUP_SPACE_IDS
    assert len(state.skill_face_up) == SKILL_FACE_UP


# --- acquiring from a board space -------------------------------------------


def test_visiting_a_commander_space_offers_the_purchase_with_face_up_skills() -> None:
    state = _turn_state(_owner())
    state = _visit(state, "dutiful_service")

    actions = _commander_actions(state)
    assert "decline_sardaukar_commander:" in actions
    offered = {key.split(":")[1] for key in actions if key.startswith("acquire")}
    assert offered == {
        skill_for_instance(skill).skill_id for skill in state.skill_face_up
    }

    bought = apply_sardaukar_commander_action(
        state, actions["acquire_sardaukar_commander:canny"]
    )
    owner = bought.state.players[0]
    assert owner.resources.solari == 4 + 2 - 2
    assert owner.commanders_garrison == 1
    assert owner.skill_ids == (_skill("canny"),)
    assert "dutiful_service" not in bought.state.sardaukar_commander_space_ids
    assert len(bought.state.skill_face_up) == SKILL_FACE_UP
    assert _skill("canny") not in bought.state.skill_face_up
    assert len(bought.state.skill_stack) == len(SKILLS) - SKILL_FACE_UP - 1
    kinds = [event.kind for event in bought.events]
    assert kinds[:3] == [
        "sardaukar_commander_acquired",
        "skill_gained",
        "skill_revealed",
    ]
    # The offer is spent; the Emperor Influence of the space is still pending.
    assert legal_sardaukar_commander_actions(bought.state, 0) == ()
    assert bought.state.decision_stack[-1].kind == "agent_effects"


def test_a_held_skill_cannot_be_chosen_again() -> None:
    owner = _owner(skill_ids=(_skill("canny"),), commanders_supply=1)
    state = _turn_state(owner, face_up=(_skill("canny", 1), *SKILLS[2:5]))
    state = _visit(state, "dutiful_service")

    offered = {
        key.split(":")[1] for key in _commander_actions(state) if "acquire" in key
    }
    assert "canny" not in offered
    assert offered == {"charismatic", "desperate"}


def test_without_a_choosable_skill_the_commander_is_bought_alone() -> None:
    # OQ-031 project convention.
    owner = _owner(skill_ids=(_skill("canny"), _skill("charismatic")))
    state = _turn_state(
        owner,
        face_up=(_skill("canny", 1), _skill("charismatic", 1)),
        stack=(),
    )
    state = _visit(state, "dutiful_service")

    actions = _commander_actions(state)
    assert set(actions) == {
        "decline_sardaukar_commander:",
        "acquire_sardaukar_commander_without_skill:",
    }
    bought = apply_sardaukar_commander_action(
        state, actions["acquire_sardaukar_commander_without_skill:"]
    ).state
    assert bought.players[0].commanders_garrison == 1
    assert bought.players[0].skill_ids == (_skill("canny"), _skill("charismatic"))


def test_without_two_solari_only_the_refusal_is_offered() -> None:
    state = _turn_state(_owner(resources=Resources(solari=1, water=1)))
    state = _visit(state, "deliver_supplies")

    assert set(_commander_actions(state)) == {"decline_sardaukar_commander:"}
    declined = apply_sardaukar_commander_action(
        state, DomainAction(action_id="decline_sardaukar_commander", actor=0)
    )
    assert declined.events[0].kind == "sardaukar_commander_declined"
    assert "deliver_supplies" in declined.state.sardaukar_commander_space_ids


def test_a_space_without_a_commander_offers_nothing() -> None:
    state = _turn_state(_owner(), spaces=())
    state = _visit(state, "dutiful_service")

    assert legal_sardaukar_commander_actions(state, 0) == ()


# --- recruiting from the supply ---------------------------------------------


def test_paid_recruit_from_supply_once_per_turn() -> None:
    state = _turn_state(
        _owner(commanders_supply=2, resources=Resources(solari=6, water=2))
    )
    state = apply_agent_action(state, _agent_action_to(state, "research_station")).state

    (recruit,) = legal_commander_recruit_actions(state, 0)
    recruited = apply_commander_recruit(state, recruit).state
    owner = recruited.players[0]
    assert owner.commanders_supply == 1
    assert owner.commanders_garrison == 1
    assert owner.resources.solari == 4
    assert owner.commander_recruited_turn is True
    # "you can only recruit one Sardaukar Commander from your supply each turn".
    assert legal_commander_recruit_actions(recruited, 0) == ()
    # Recruited this turn at a Combat space: it may join the deployment.
    assert legal_commander_deployments(recruited, 0) != ()


def test_paid_recruit_is_offered_in_the_reveal_turn_to_the_garrison() -> None:
    state = _turn_state(_owner(commanders_supply=1, resources=Resources(solari=2)))
    state = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state

    (recruit,) = legal_commander_recruit_actions(state, 0)
    recruited = apply_commander_recruit(state, recruit).state
    assert recruited.players[0].commanders_garrison == 1
    assert recruited.players[0].commanders_conflict == 0
    assert recruited.decision_stack[-1].kind == "reveal"


def test_paid_recruit_needs_supply_solari_and_the_option() -> None:
    state = _turn_state(
        _owner(commanders_supply=0, resources=Resources(solari=6, water=2))
    )
    state = apply_agent_action(state, _agent_action_to(state, "research_station")).state
    assert legal_commander_recruit_actions(state, 0) == ()

    state = _turn_state(
        _owner(commanders_supply=1, resources=Resources(solari=1, water=2))
    )
    state = apply_agent_action(state, _agent_action_to(state, "research_station")).state
    assert legal_commander_recruit_actions(state, 0) == ()


# --- deployment and strength -----------------------------------------------


def test_commanders_share_the_two_from_garrison_limit_and_count_two_strength() -> None:
    state = _turn_state(_owner(commanders_garrison=2))
    state = _visit(state, "arrakeen")  # one recruited troop + two from garrison

    assert [
        dict(a.arguments)["count"] for a in legal_commander_deployments(state, 0)
    ] == [1, 2]
    deployed = apply_commander_deployment(
        state, DomainAction("deploy_commanders", 0, (("count", 2),))
    ).state
    owner = deployed.players[0]
    assert owner.commanders_conflict == 2 and owner.commanders_garrison == 0
    assert owner.units_deployed_turn == 2
    # The garrison share is used up; only the recruited troop may still go.
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(deployed, 0)
    ] == [1]
    assert legal_commander_deployments(deployed, 0) == ()
    # The running strength follows at once: 2 per Commander.
    refreshed = refresh_pre_reveal_strength(RuleResult(state=deployed)).state
    assert refreshed.players[0].combat_strength == 4

    withdrawn = apply_commander_withdrawal(
        deployed, DomainAction("withdraw_commanders", 0, (("count", 1),))
    ).state
    assert withdrawn.players[0].commanders_conflict == 1
    assert withdrawn.players[0].commanders_garrison == 1
    assert [
        dict(a.arguments)["count"] for a in legal_commander_withdrawals(withdrawn, 0)
    ] == [1]
    troop_first = apply_combat_deployment(
        withdrawn, DomainAction("deploy_troops", 0, (("count", 1),))
    ).state
    # A troop deployed this turn can be withdrawn, but not as a Commander.
    assert [
        dict(a.arguments)["count"] for a in legal_commander_withdrawals(troop_first, 0)
    ] == [1]


def _seat_with_skills(**overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "commanders_conflict": 1,
        "troops_supply": 8,
        "troops_conflict": 1,
        "agent_locations": ("high_council",),
        "agents_available": 1,
        "combat_strength": 4,
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def test_skill_strength_follows_its_conditions_while_a_commander_fights() -> None:
    owner = _seat_with_skills(
        skill_ids=(_skill("canny"), _skill("fierce"), _skill("loyal")),
        influence=Influence(emperor=3),
    )
    state = _turn_state(owner)
    refreshed = refresh_pre_reveal_strength(RuleResult(state=state)).state
    # troop 2 + Commander 2 + Canny 2 (Agent on High Council, Landsraad)
    # + Fierce 1 + Loyal 2 (Emperor Influence 3).
    assert refreshed.players[0].combat_strength == 9
    assert refreshed.players[0].skill_strength_applied == 5

    # An opponent's sandworm arrives: Fierce adds one more.
    opponent = replace(refreshed.players[1], sandworms_conflict=1)
    with_worm = replace(
        refreshed, players=(refreshed.players[0], opponent, *refreshed.players[2:])
    )
    assert (
        refresh_pre_reveal_strength(RuleResult(state=with_worm))
        .state.players[0]
        .combat_strength
        == 10
    )

    # Without a Commander in the Conflict no Skill is active.
    no_commander = replace(
        refreshed,
        players=(
            replace(refreshed.players[0], commanders_conflict=0, commanders_garrison=1),
            *refreshed.players[1:],
        ),
    )
    assert (
        refresh_pre_reveal_strength(RuleResult(state=no_commander))
        .state.players[0]
        .combat_strength
        == 2
    )


def test_reveal_bonuses_pay_once_and_keep_the_skill_strength() -> None:
    owner = _seat_with_skills(
        skill_ids=(
            _skill("charismatic"),
            _skill("driven"),
            _skill("hardy"),
            _skill("canny"),
        ),
        hand=starting_deck_instance_ids(0)[:5],
        resources=Resources(solari=0, spice=0, water=1),
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    assert state.players[0].combat_strength == 6  # 2 + 2 + Canny 2

    result = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    revealed = result.state.players[0]
    context = dict(result.state.decision_stack[0].context)
    bonus_events = [
        event for event in result.events if event.kind == "skill_reveal_bonus"
    ]
    assert len(bonus_events) == 3
    assert revealed.resources.spice == 1 and revealed.resources.water == 2
    sword_strength = context["sword_strength"]
    assert isinstance(sword_strength, int)
    assert context["persuasion"] == revealed_persuasion_without_skill(state) + 1
    assert revealed.combat_strength == 6 + sword_strength
    assert context["strength"] == revealed.combat_strength


def revealed_persuasion_without_skill(state: GameState) -> int:
    plain = replace(
        state,
        players=(replace(state.players[0], skill_ids=()), *state.players[1:]),
        skill_stack=(*state.skill_stack, _skill("charismatic")),
    )
    result = begin_reveal_turn(plain, DomainAction(action_id="reveal_turn", actor=0))
    persuasion = dict(result.state.decision_stack[0].context)["persuasion"]
    assert isinstance(persuasion, int)
    return persuasion


def test_reveal_bonuses_need_a_commander_in_the_conflict() -> None:
    owner = _seat_with_skills(
        skill_ids=(_skill("driven"),),
        commanders_conflict=0,
        commanders_garrison=1,
        hand=starting_deck_instance_ids(0)[:5],
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    result = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    assert result.state.players[0].resources.spice == 0
    assert not [event for event in result.events if event.kind == "skill_reveal_bonus"]


def test_desperate_trashes_for_three_swords_during_the_reveal() -> None:
    owner = _seat_with_skills(
        skill_ids=(_skill("desperate"),), hand=starting_deck_instance_ids(0)[:5]
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    state = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    before = state.players[0].combat_strength

    (trash,) = legal_skill_trash_actions(state, 0)
    assert dict(trash.arguments) == {"skill_id": "desperate"}
    result = apply_skill_trash(state, trash)
    owner = result.state.players[0]
    assert owner.skill_ids == ()
    assert result.state.skill_trash == (_skill("desperate"),)
    assert owner.combat_strength == before + 3
    assert dict(result.state.decision_stack[0].context)["strength"] == before + 3
    assert legal_skill_trash_actions(result.state, 0) == ()


def test_desperate_needs_a_commander_in_the_conflict() -> None:
    owner = _seat_with_skills(
        skill_ids=(_skill("desperate"),),
        commanders_conflict=0,
        commanders_garrison=1,
        hand=starting_deck_instance_ids(0)[:5],
    )
    state = begin_reveal_turn(
        _turn_state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert legal_skill_trash_actions(state, 0) == ()


def test_combat_cleanup_returns_commanders_to_the_supply() -> None:
    conflict_id = CONFLICTS[0].card.card_id
    owner = _seat_with_skills(
        skill_ids=(_skill("canny"),),
        has_revealed=True,
        skill_strength_applied=2,
        combat_strength=6,
    )
    state = replace(
        _turn_state(owner),
        phase=GamePhase.COMBAT,
        first_player=0,
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        combat_rewards_resolved=True,
        decision_stack=(),
        players=(
            owner,
            *(
                replace(seat, has_revealed=True)
                for seat in _turn_state(owner).players[1:]
            ),
        ),
    )

    cleaned = finish_combat(state).state.players[0]
    assert cleaned.commanders_conflict == 0
    assert cleaned.commanders_supply == 1
    assert cleaned.troops_conflict == 0
    assert cleaned.combat_strength == 0
    assert cleaned.skill_strength_applied == 0
    assert cleaned.skill_ids == (_skill("canny"),)


# --- state invariants -------------------------------------------------------


def test_two_copies_of_one_skill_cannot_be_held() -> None:
    with pytest.raises(ValueError, match="two copies of one Skill"):
        PlayerState(player_id=0, skill_ids=(_skill("canny"), _skill("canny", 1)))


def test_a_skill_tile_cannot_be_in_two_zones() -> None:
    with pytest.raises(ValueError, match="two zones"):
        GameState(
            config=BLOODLINES,
            seed=1,
            players=(
                _owner(skill_ids=(_skill("fierce"),)),
                *(PlayerState(player_id=seat) for seat in range(1, 4)),
            ),
            skill_face_up=(_skill("fierce"),),
        )


# --- observation, codec, soak ----------------------------------------------


def test_observation_shows_face_up_skills_but_hides_the_stack_order() -> None:
    state = create_initial_state(BLOODLINES, seed=3, leader_ids=LEADERS).state
    view = observe_state(state, 0)

    assert view.skill_face_up == state.skill_face_up
    assert view.skill_stack_size == len(state.skill_stack)
    assert not hasattr(view, "skill_stack")
    assert view.sardaukar_commander_space_ids == COMMANDER_SETUP_SPACE_IDS
    assert view.players[0].commanders_supply == 0
    assert len(encode_player_view(view)) == OBSERVATION_SIZE


def test_bloodlines_actions_round_trip_only_in_the_bloodlines_catalog() -> None:
    base = ActionCodec(RulesetConfig())
    codec = ActionCodec(BLOODLINES)
    assert base.size == 4354
    assert codec.size == base.size + 3 + 7 * 2 + 7 * 2

    actions = (
        DomainAction("acquire_sardaukar_commander", 2, (("skill_id", "loyal"),)),
        DomainAction("acquire_sardaukar_commander_without_skill", 2),
        DomainAction("decline_sardaukar_commander", 1),
        DomainAction("recruit_sardaukar_commander", 3),
        DomainAction("trash_skill_for_strength", 0, (("skill_id", "desperate"),)),
        DomainAction("deploy_commanders", 0, (("count", 7),)),
        DomainAction("withdraw_commanders", 1, (("count", 1),)),
    )
    for action in actions:
        assert codec.decode(codec.encode(action), action.actor) == action
        with pytest.raises(ValueError):
            base.encode(action)


@pytest.mark.parametrize("game_seed", [11, 12, 13])
def test_random_bloodlines_games_finish_under_every_check(game_seed: int) -> None:
    report = run_checked_game(
        BLOODLINES,
        game_seed=game_seed,
        policy_seed=900_000 + game_seed,
        privacy_interval=10,
        soundness_interval=10,
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.ruleset == "uprising-4p-base+bloodlines"
    assert report.rounds >= 1 and 0 <= report.winner < 4


def test_heuristic_bloodlines_game_buys_commanders() -> None:
    report = run_checked_game(
        RulesetConfig(bloodlines=True, choam_module=True),
        game_seed=21,
        policy_seed=900_021,
        privacy_interval=0,
        policy="heuristic",
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.ruleset == "uprising-4p-choam+bloodlines"
    assert report.rounds >= 1
