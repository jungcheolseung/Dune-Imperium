"""Tests for Bloodlines Sardaukar Commanders and their Skills.

Rule source: ``docs/rules/bloodlines.md`` section 3 [Bloodlines pp. 3-4] and
the Skill tile faces. A Commander is bought without a Skill while no face-up
Skill is choosable (OQ-031, user decision).
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
    apply_troop_withdrawal,
    legal_combat_deployments,
    legal_commander_deployments,
    legal_commander_withdrawals,
    reconcile_deployment_after_retreat,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import (
    apply_reveal_deployment,
    apply_reveal_gain,
    begin_reveal_turn,
    legal_reveal_deployments,
    legal_reveal_gain_actions,
)
from dune_imperium.rules.sardaukar import (
    apply_commander_recruit,
    apply_sardaukar_commander_action,
    apply_skill_choice,
    apply_skill_trash,
    begin_skill_choice,
    legal_commander_recruit_actions,
    legal_sardaukar_commander_actions,
    legal_skill_choice_actions,
    legal_skill_trash_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.rules.strength import refresh_pre_reveal_strength
from dune_imperium.rules.units import retreat_units
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


def test_a_first_high_council_visit_may_buy_its_commander() -> None:
    # "During one of your turns, if you send an Agent to a board space that
    # has a Sardaukar Commander, you may spend 2 Solari to acquire and then
    # immediately recruit that Sardaukar Commander" [Bloodlines p. 4]; setup
    # puts one on High Council [Bloodlines p. 3], and taking the seat on the
    # same visit does not hide it.
    state = _turn_state(_owner(resources=Resources(solari=7, water=2)))
    placed = apply_agent_action(state, _agent_action_to(state, "high_council")).state
    assert dict(placed.decision_stack[-1].context)["pending_board_icons"] == (
        "high_council,sardaukar_commander"
    )
    state = _visit(state, "high_council")
    assert state.players[0].high_council
    bought = apply_sardaukar_commander_action(
        state, _commander_actions(state)["acquire_sardaukar_commander:canny"]
    )
    owner = bought.state.players[0]
    assert owner.resources.solari == 0
    assert owner.commanders_garrison == 1
    assert "high_council" not in bought.state.sardaukar_commander_space_ids


def test_a_held_skill_cannot_be_chosen_again() -> None:
    owner = _owner(skill_ids=(_skill("canny"),), commanders_supply=1)
    state = _turn_state(owner, face_up=(_skill("canny", 1), *SKILLS[2:5]))
    state = _visit(state, "dutiful_service")

    offered = {
        key.split(":")[1] for key in _commander_actions(state) if "acquire" in key
    }
    assert "canny" not in offered
    assert offered == {"charismatic", "desperate"}


def test_without_a_choosable_skill_the_commander_is_bought_without_one() -> None:
    # OQ-031 (user decision 2026-09-07): the Commander still comes, the
    # Skill does not.
    owner = _owner(skill_ids=(_skill("canny"), _skill("charismatic")))
    state = _turn_state(
        owner,
        face_up=(_skill("canny", 1), _skill("charismatic", 1)),
        stack=(),
    )
    state = _visit(state, "dutiful_service")

    assert set(_commander_actions(state)) == {
        "decline_sardaukar_commander:",
        "acquire_sardaukar_commander:",
    }
    with pytest.raises(ValueError, match="not a legal Sardaukar Commander choice"):
        apply_sardaukar_commander_action(
            state,
            DomainAction("acquire_sardaukar_commander", 0, (("skill_id", "canny"),)),
        )
    bought = apply_sardaukar_commander_action(
        state, DomainAction(action_id="acquire_sardaukar_commander", actor=0)
    )
    owner = bought.state.players[0]
    assert owner.commanders_garrison == 1
    assert owner.resources.solari == state.players[0].resources.solari - 2
    assert len(owner.skill_ids) == 2
    assert bought.state.skill_face_up == state.skill_face_up
    assert [event.kind for event in bought.events] == ["sardaukar_commander_acquired"]


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
    # Finding 2's Reveal branch (``turn_owner_of(next_state) == player``)
    # must not double-credit this Agent-turn recruit, which the in-place
    # update already counts once -- as a Commander, never as a troop, so
    # its deploy slot stays a Commander's (user ruling OQ-070).
    context = dict(recruited.decision_stack[-1].context)
    assert context["commanders_recruited"] == 1
    assert context["troops_recruited"] == 0


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


def test_paid_recruit_in_reveal_counts_as_a_commander() -> None:
    # Finding 2 (2026-09-26 review round 3): ``apply_commander_recruit``
    # only credited an owned AGENT_EFFECTS frame's ``troops_recruited``; in
    # a Reveal turn no such frame sits on top, so this once-per-turn
    # recruit reached the garrison without ever joining the Combat
    # 아이콘's shared deploy allowance. "Once per turn, Agent or Reveal"
    # [Bloodlines p. 4]; "이번 turn에 recruit한 유닛 전부와 garrison에서
    # 최대 두 개" [Bloodlines pp. 5, 12] applies to either alike
    # (docs/rules/player-turns.md:137) [Main p. 10] [FAQ p. 4].
    state = _turn_state(_owner(commanders_supply=1, resources=Resources(solari=2)))
    state = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state

    (recruit,) = legal_commander_recruit_actions(state, 0)
    recruited = apply_commander_recruit(state, recruit).state

    assert recruited.decision_stack[-1].kind == "reveal"
    # Counted as a Commander, apart from the troops: its slot is a
    # Commander's (user ruling OQ-070).
    context = dict(recruited.decision_stack[-1].context)
    assert context["reveal_commanders_recruited"] == 1
    assert context["reveal_troops_recruited"] == 0


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


# --- a recruited Commander's deploy slot (OQ-070) ---------------------------
#
# User ruling 2026-09-26 (OQ-070), verbatim: "commander 소집했으면 커맨더를
# 배치해야지, troop이 그 배치 몫을 차지하면 안 되지". Rules: "Combat space에
# 들어간 turn에는 그 turn에 recruit한 troop을 원하는 수만큼 deploy하고, 그와
# 별도로 garrison의 troop을 최대 두 개 더 deploy할 수 있다. [Main p. 10]"
# (docs/rules/player-turns.md:136); the Combat icon deploys "이번 turn에
# recruit한 유닛 전부와 garrison에서 최대 두 개" [Bloodlines pp. 5, 12]
# (docs/rules/bloodlines.md); a Commander is a "troop" worth 2 strength
# [Bloodlines p. 4]. Each recruited unit reserves a slot for its own kind and
# the garrison extra is shared: legal iff
# max(0, t - R_t) + max(0, c - R_c) <= existing limit.


def _counts(actions: tuple[DomainAction, ...], action_id: str) -> list[int]:
    counts: list[int] = []
    for action in actions:
        if action.action_id != action_id:
            continue
        count = dict(action.arguments)["count"]
        assert isinstance(count, int)
        counts.append(count)
    return counts


def _recruited_commander_at_research_station(**overrides: object) -> GameState:
    """Research Station (a Combat space, no troop icon) + a paid Commander."""

    values: dict[str, object] = {
        "commanders_supply": 1,
        "troops_garrison": 5,
        "troops_supply": 7,
        "resources": Resources(solari=2, water=2),
    }
    values.update(overrides)
    state = _turn_state(_owner(**values), spaces=())
    state = apply_agent_action(state, _agent_action_to(state, "research_station")).state
    (recruit,) = legal_commander_recruit_actions(state, 0)
    return apply_commander_recruit(state, recruit).state


def test_a_recruited_commanders_slot_is_not_a_garrison_troops() -> None:
    # The reviewer's probe in an Agent turn: one Commander recruited, five
    # troops in the garrison. Three troops used to deploy while the new
    # Commander stayed home.
    state = _recruited_commander_at_research_station()

    assert _counts(legal_combat_deployments(state, 0), "deploy_troops") == [1, 2]
    assert _counts(legal_commander_deployments(state, 0), "deploy_commanders") == [1]

    # Two garrison troops first: the Commander's own slot is still open.
    troops = apply_combat_deployment(
        state, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    assert legal_combat_deployments(troops, 0) == ()
    assert _counts(legal_commander_deployments(troops, 0), "deploy_commanders") == [1]
    both = apply_commander_deployment(
        troops, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    owner = both.players[0]
    assert (owner.commanders_conflict, owner.troops_conflict) == (1, 2)
    assert legal_combat_deployments(both, 0) == ()
    assert legal_commander_deployments(both, 0) == ()

    # The Commander first: the two garrison troops still follow it.
    commander = apply_commander_deployment(
        state, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(commander, 0), "deploy_troops") == [1, 2]


def test_a_space_commander_bought_under_a_combat_icon_keeps_its_slot() -> None:
    # "During one of your turns, if you send an Agent to a board space that
    # has a Sardaukar Commander, you may spend 2 Solari to acquire and then
    # immediately recruit that Sardaukar Commander" [Bloodlines p. 4]. Every
    # Commander setup space is a non-Combat space, so its slot matters under
    # a Combat icon opened this turn [Bloodlines pp. 5, 12]; the bought
    # Commander is credited as a Commander, never as a troop (OQ-070).
    state = _turn_state(
        _owner(troops_garrison=5, troops_supply=7, combat_icon_turn=True)
    )
    state = _visit(state, "dutiful_service")
    bought = apply_sardaukar_commander_action(
        state, _commander_actions(state)["acquire_sardaukar_commander:canny"]
    ).state

    context = dict(bought.decision_stack[-1].context)
    assert context["commanders_recruited"] == 1
    assert context["troops_recruited"] == 0
    assert _counts(legal_combat_deployments(bought, 0), "deploy_troops") == [1, 2]
    assert _counts(legal_commander_deployments(bought, 0), "deploy_commanders") == [1]
    commander = apply_commander_deployment(
        bought, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(commander, 0), "deploy_troops") == [1, 2]


def test_a_commander_slot_survives_a_deployment_split_over_several_actions() -> None:
    state = _recruited_commander_at_research_station()

    one = apply_combat_deployment(
        state, DomainAction("deploy_troops", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(one, 0), "deploy_troops") == [1]
    two = apply_combat_deployment(
        one, DomainAction("deploy_troops", 0, (("count", 1),))
    ).state
    assert legal_combat_deployments(two, 0) == ()
    # A withdrawal (OQ-029) reopens exactly the troop share it returns.
    back = apply_troop_withdrawal(
        two, DomainAction("withdraw_troops", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(back, 0), "deploy_troops") == [1]
    assert _counts(legal_commander_deployments(back, 0), "deploy_commanders") == [1]
    commander = apply_commander_deployment(
        back, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(commander, 0), "deploy_troops") == [1]
    # Withdrawing the Commander gives its own slot back, not a troop's.
    withdrawn = apply_commander_withdrawal(
        commander, DomainAction("withdraw_commanders", 0, (("count", 1),))
    ).state
    offered = (
        *legal_combat_deployments(withdrawn, 0),
        *legal_commander_deployments(withdrawn, 0),
    )
    assert _counts(offered, "deploy_troops") == [1]
    assert _counts(offered, "deploy_commanders") == [1]


def test_a_recruited_troops_slot_is_not_a_garrison_commanders() -> None:
    # Arrakeen recruits one troop; three Commanders wait in the garrison.
    # Only the garrison two may be Commanders -- the troop's slot is a
    # troop's.
    state = _turn_state(
        _owner(commanders_garrison=3, troops_garrison=0, troops_supply=12), spaces=()
    )
    state = _visit(state, "arrakeen")
    assert state.players[0].troops_garrison == 1

    assert _counts(legal_commander_deployments(state, 0), "deploy_commanders") == [1, 2]
    commanders = apply_commander_deployment(
        state, DomainAction("deploy_commanders", 0, (("count", 2),))
    ).state
    assert legal_commander_deployments(commanders, 0) == ()
    assert _counts(legal_combat_deployments(commanders, 0), "deploy_troops") == [1]


def test_sardaukar_coordination_deploys_only_the_recruited_commander() -> None:
    # "You may deploy any troops you recruit this turn to the Conflict"
    # [Sardaukar Coordination card] grants no garrison extra (limit 0): the
    # recruited Commander deploys, a garrison troop may not take its slot.
    card = "imperium:sardaukar_coordination:0"
    state = _turn_state(
        _owner(
            hand=(card,),
            commanders_supply=1,
            troops_garrison=3,
            troops_supply=9,
            resources=Resources(solari=2),
        ),
        spaces=(),
    )
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["card_id"] == card
        and dict(action.arguments)["space_id"] == "dutiful_service"
    )
    state = apply_agent_action(state, action).state
    (recruit,) = legal_commander_recruit_actions(state, 0)
    state = apply_commander_recruit(state, recruit).state

    assert legal_combat_deployments(state, 0) == ()
    assert _counts(legal_commander_deployments(state, 0), "deploy_commanders") == [1]


def test_elite_forces_combat_icon_keeps_the_commander_slot() -> None:
    # Elite Forces' Combat icon: "never more than two units from the
    # garrison" [Bloodlines p. 5] at a non-Combat space, plus its troop
    # icon; a paid Commander keeps its own slot.
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_trash,
        legal_agent_card_icon_actions,
        legal_agent_card_trash_actions,
        resolve_agent_card_icon,
    )

    card = "imperium:elite_forces:0"
    emperor = "imperium:quash_rebellion:0"
    state = _turn_state(
        _owner(
            hand=(card, emperor),
            commanders_supply=1,
            troops_garrison=3,
            troops_supply=9,
            resources=Resources(solari=2),
        ),
        spaces=(),
    )
    state = _visit(state, "dutiful_service")
    (recruit,) = legal_commander_recruit_actions(state, 0)
    state = apply_commander_recruit(state, recruit).state
    trash = next(
        action
        for action in legal_agent_card_trash_actions(state, 0)
        if dict(action.arguments).get("card_id") == emperor
    )
    state = apply_agent_card_trash(state, trash).state
    troop_icon = next(
        action
        for action in legal_agent_card_icon_actions(state, 0)
        if dict(action.arguments)["effect"] == "troops"
    )
    state = resolve_agent_card_icon(state, troop_icon).state
    assert state.players[0].troops_garrison == 4

    # One recruited troop plus the garrison two; the Commander's slot is
    # its own.
    assert _counts(legal_combat_deployments(state, 0), "deploy_troops") == [1, 2, 3]
    deployed = apply_combat_deployment(
        state, DomainAction("deploy_troops", 0, (("count", 3),))
    ).state
    assert legal_combat_deployments(deployed, 0) == ()
    assert _counts(legal_commander_deployments(deployed, 0), "deploy_commanders") == [1]


def test_a_commander_recruited_in_the_reveal_keeps_its_slot() -> None:
    # The reviewer's probe: Bloodlines, a Combat icon earlier this turn, five
    # garrison troops, Reveal, recruit_sardaukar_commander. deploy_troops
    # used to go up to three while the new Commander stayed home.
    state = _turn_state(
        _owner(
            commanders_supply=1,
            troops_garrison=5,
            troops_supply=7,
            combat_icon_turn=True,
            resources=Resources(solari=2),
        ),
        spaces=(),
    )
    state = begin_reveal_turn(state, DomainAction("reveal_turn", 0)).state
    (recruit,) = legal_commander_recruit_actions(state, 0)
    state = apply_commander_recruit(state, recruit).state

    offered = legal_reveal_deployments(state, 0)
    assert _counts(offered, "deploy_troops") == [1, 2]
    assert _counts(offered, "deploy_commanders") == [1]
    troops = apply_reveal_deployment(
        state, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    assert _counts(legal_reveal_deployments(troops, 0), "deploy_troops") == []
    assert _counts(legal_reveal_deployments(troops, 0), "deploy_commanders") == [1]
    both = apply_reveal_deployment(
        troops, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    owner = both.players[0]
    assert (owner.commanders_conflict, owner.troops_conflict) == (1, 2)
    assert legal_reveal_deployments(both, 0) == ()

    # The Commander first: the Reveal keeps its Commander share apart
    # (``reveal_commanders_deployed``), so the garrison two still follow.
    commander = apply_reveal_deployment(
        state, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert dict(commander.decision_stack[-1].context)[
        "reveal_commanders_deployed"
    ] == 1
    assert _counts(legal_reveal_deployments(commander, 0), "deploy_troops") == [1, 2]


def test_a_reveal_troops_slot_is_not_a_garrison_commanders() -> None:
    # Sardaukar Standard's own Reveal box recruits a troop [card face]; of
    # three garrison Commanders only the garrison two may deploy.
    card = "imperium:sardaukar_standard:0"
    state = _turn_state(
        _owner(
            hand=(card,),
            commanders_garrison=3,
            troops_garrison=0,
            troops_supply=12,
            combat_icon_turn=True,
        ),
        spaces=(),
    )
    state = begin_reveal_turn(state, DomainAction("reveal_turn", 0)).state
    while gains := legal_reveal_gain_actions(state, 0):
        state = apply_reveal_gain(state, gains[0]).state
    assert state.players[0].troops_garrison == 1

    offered = legal_reveal_deployments(state, 0)
    assert _counts(offered, "deploy_commanders") == [1, 2]
    assert _counts(offered, "deploy_troops") == [1]


def _queued_bank_commander(state: GameState, *, turn_closed: bool) -> GameState:
    """Acquire Sardaukar Standard's bank Commander from the queued choice."""

    queued = replace(
        state,
        pending_skill_choices=(
            (0, "imperium:sardaukar_standard:0", "test:standard", turn_closed),
        ),
    )
    opened = begin_skill_choice(queued).state
    return apply_skill_choice(opened, legal_skill_choice_actions(opened, 0)[0]).state


def test_a_commander_recruited_before_the_placement_keeps_its_slot() -> None:
    state = _turn_state(
        _owner(troops_garrison=5, troops_supply=7, resources=Resources(water=2)),
        spaces=(),
    )
    acquired = _queued_bank_commander(state, turn_closed=False)
    turn = acquired.decision_stack[-1]
    assert turn.kind == "turn"
    assert dict(turn.context)["commanders_recruited"] == 1
    assert dict(turn.context).get("troops_recruited") in (None, 0)

    placed = apply_agent_action(
        acquired, _agent_action_to(acquired, "research_station")
    ).state
    assert dict(placed.decision_stack[-1].context)["commanders_recruited"] == 1
    assert _counts(legal_combat_deployments(placed, 0), "deploy_troops") == [1, 2]
    commander = apply_commander_deployment(
        placed, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(commander, 0), "deploy_troops") == [1, 2]


def test_a_commander_recruited_before_the_reveal_keeps_its_slot() -> None:
    state = _turn_state(
        _owner(troops_garrison=5, troops_supply=7, combat_icon_turn=True), spaces=()
    )
    acquired = _queued_bank_commander(state, turn_closed=False)
    revealed = begin_reveal_turn(acquired, DomainAction("reveal_turn", 0)).state
    context = dict(revealed.decision_stack[-1].context)
    assert context["reveal_commanders_recruited"] == 1
    assert context["reveal_troops_recruited"] == 0

    offered = legal_reveal_deployments(revealed, 0)
    assert _counts(offered, "deploy_troops") == [1, 2]
    assert _counts(offered, "deploy_commanders") == [1]


def test_a_closed_turns_commander_credit_goes_nowhere() -> None:
    # OQ-044 (d): a Commander whose Skill choice was queued by a turn that
    # already closed must not join the fresh turn frame underneath, even
    # the same player's own [Main p. 10] [FAQ p. 4].
    state = _turn_state(
        _owner(troops_garrison=5, troops_supply=7, resources=Resources(water=2)),
        spaces=(),
    )
    acquired = _queued_bank_commander(state, turn_closed=True)
    assert acquired.players[0].commanders_garrison == 1
    assert dict(acquired.decision_stack[-1].context).get("commanders_recruited") in (
        None,
        0,
    )
    placed = apply_agent_action(
        acquired, _agent_action_to(acquired, "research_station")
    ).state
    # A plain garrison Commander: it takes one of the garrison two.
    commander = apply_commander_deployment(
        placed, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert _counts(legal_combat_deployments(commander, 0), "deploy_troops") == [1]


def test_a_retreated_earlier_troop_leaves_the_commander_share_alone() -> None:
    # "그와 별도로 garrison의 troop을 최대 두 개 더 deploy할 수 있다"
    # [Main p. 10] (docs/rules/player-turns.md:136) and the recruited
    # Commander's own slot (user ruling OQ-070). A retreat of a troop that
    # was already in the Conflict before this turn (an Intrigue retreat,
    # Fedaykin Maneuver) used to shrink the unit total below the deployed
    # Commander share, so the troop share read back short and three garrison
    # troops deployed beside the recruited Commander.
    state = _recruited_commander_at_research_station(
        troops_garrison=5, troops_conflict=2, troops_supply=5, combat_strength=4
    )
    state = apply_commander_deployment(
        state, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    retreated = retreat_units(state, 0, "test:retreat", troops=1).state
    retreated = reconcile_deployment_after_retreat(retreated, 0, troops=1)

    context = dict(retreated.decision_stack[-1].context)
    assert (
        context["combat_troops_deployed"],
        context["combat_commanders_deployed"],
    ) == (1, 1)
    assert _counts(legal_combat_deployments(retreated, 0), "deploy_troops") == [1, 2]
    troops = apply_combat_deployment(
        retreated, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    assert legal_combat_deployments(troops, 0) == ()


def test_a_retreated_earlier_commander_leaves_the_troop_share_alone() -> None:
    # The mirror case: a Commander that was in the Conflict before this
    # turn retreats after two garrison troops deployed; those two still
    # fill the garrison extra [Main p. 10] (OQ-070).
    state = _turn_state(
        _owner(
            commanders_conflict=1,
            troops_garrison=5,
            troops_supply=7,
            combat_strength=2,
        ),
        spaces=(),
    )
    state = apply_agent_action(state, _agent_action_to(state, "research_station")).state
    state = apply_combat_deployment(
        state, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    retreated = retreat_units(state, 0, "test:retreat", troops=0, commanders=1).state
    retreated = reconcile_deployment_after_retreat(
        retreated, 0, troops=0, commanders=1
    )

    context = dict(retreated.decision_stack[-1].context)
    assert context["combat_troops_deployed"] == 2
    assert legal_combat_deployments(retreated, 0) == ()


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

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    result = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    bonus_events = [
        event for event in result.events if event.kind == "skill_reveal_bonus"
    ]
    assert len(bonus_events) == 3
    # Driven's spice and Hardy's troop are the owner's own Reveal actions
    # (OQ-045); Charismatic's Persuasion is totalled at once. Hardy prints
    # "Reveal Turn: [troop]" -- a recruit, not water [Hardy Skill tile].
    taken = result.state
    while gains := legal_reveal_gain_actions(taken, 0):
        taken = apply_reveal_gain(taken, gains[0]).state
    revealed = taken.players[0]
    context = dict(taken.decision_stack[0].context)
    assert revealed.resources.spice == 1 and revealed.resources.water == 1
    assert revealed.troops_garrison == state.players[0].troops_garrison + 1
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


def test_hardy_recruits_one_troop_in_the_reveal_turn() -> None:
    # Hardy's tile prints "Reveal Turn: [troop]" -- the grey cube is the troop
    # icon, "Troop. Recruit one troop" [Main p. 20] [Hardy Skill tile]. The
    # recruit is the owner's own Reveal action like any other (OQ-045).
    owner = _seat_with_skills(
        skill_ids=(_skill("hardy"),),
        hand=starting_deck_instance_ids(0)[:5],
        resources=Resources(solari=0, spice=0, water=1),
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    result = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    (bonus,) = [e for e in result.events if e.kind == "skill_reveal_bonus"]
    assert dict(bonus.payload)["troops"] == 1
    assert "water" not in dict(bonus.payload)

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    gains = legal_reveal_gain_actions(result.state, 0)
    assert [action.action_id for action in gains] == ["recruit_reveal_troops"]
    recruited = apply_reveal_gain(result.state, gains[0])
    seat = recruited.state.players[0]
    assert seat.resources.water == 1
    assert seat.troops_garrison == owner.troops_garrison + 1
    assert seat.troops_supply == owner.troops_supply - 1
    assert legal_reveal_gain_actions(recruited.state, 0) == ()

    # With an empty supply the troop is lost (OQ-030), not turned into water.
    drained = replace(
        owner,
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    empty = replace(state, players=(drained, *state.players[1:]))
    started = begin_reveal_turn(empty, DomainAction(action_id="reveal_turn", actor=0))
    (recruit,) = legal_reveal_gain_actions(started.state, 0)
    short = apply_reveal_gain(started.state, recruit)
    assert short.state.players[0].troops_garrison == drained.troops_garrison
    assert short.state.players[0].resources.water == 1
    assert any(event.kind == "troops_recruit_short" for event in short.events)


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


def test_a_commander_deployed_during_the_reveal_pays_the_reveal_bonuses() -> None:
    # "While you have any number of Sardaukar Commanders in the Conflict, the
    # effects of all your Sardaukar Commander Skills are active. Each one
    # either gives you a bonus when taking your Reveal turn ... Each one
    # works only once each round" [Bloodlines p. 4]; Charismatic "Reveal
    # Turn: [1 Persuasion]", Driven "Reveal Turn: [1 spice]" [Skill tile
    # faces]. A Commander deployed with a Combat icon during the Reveal
    # [Bloodlines p. 5] switches them on then, and the bonus is paid late
    # like any late-met Reveal gain (OQ-028 (c)) -- once.
    from dune_imperium.rules.combat_deployment import grant_combat_icon
    from dune_imperium.rules.reveal_turn import (
        legal_reveal_gain_actions,
        reveal_pending_gains,
    )

    owner = _seat_with_skills(
        skill_ids=(_skill("charismatic"), _skill("driven")),
        commanders_conflict=0,
        commanders_garrison=1,
        combat_strength=2,
        hand=starting_deck_instance_ids(0)[:5],
        resources=Resources(solari=0, spice=0, water=1),
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    persuasion = dict(revealed.decision_stack[-1].context)["persuasion"]
    assert isinstance(persuasion, int)
    assert legal_reveal_gain_actions(revealed, 0) == ()
    opened = grant_combat_icon(revealed, 0)

    engine = UprisingRulesEngine()
    deploy = DomainAction("deploy_commanders", 0, (("count", 1),))
    result = engine.apply(opened, deploy)
    deployed = result.state
    context = dict(deployed.decision_stack[-1].context)
    assert deployed.players[0].commanders_conflict == 1
    assert context["persuasion"] == persuasion + 1
    assert context["persuasion_generated"] == persuasion + 1
    assert ("resources", "0/1/0", "skill:driven") in reveal_pending_gains(context)
    assert {
        dict(event.payload)["skill_id"]
        for event in result.events
        if event.kind == "skill_reveal_bonus"
    } == {"charismatic", "driven"}

    # Once each round: taking the spice (another transition) pays nothing more.
    (gain,) = legal_reveal_gain_actions(deployed, 0)
    taken = engine.apply(deployed, gain).state
    assert taken.players[0].resources.spice == 1
    assert dict(taken.decision_stack[-1].context)["persuasion"] == persuasion + 1
    assert legal_reveal_gain_actions(taken, 0) == ()


def test_a_commander_deployed_during_the_reveal_pays_hardys_troop() -> None:
    # Hardy prints "Reveal Turn: [troop]" [Hardy Skill tile] (a recruit, not
    # water); a Commander deployed with a Combat icon during the Reveal
    # switches it on then [Bloodlines pp. 4, 5] and the recruit waits for the
    # owner's order like the Reveal-start one (OQ-028 (c), OQ-045).
    from dune_imperium.rules.combat_deployment import grant_combat_icon
    from dune_imperium.rules.reveal_turn import (
        legal_reveal_gain_actions,
        reveal_pending_gains,
    )

    owner = _seat_with_skills(
        skill_ids=(_skill("hardy"),),
        commanders_conflict=0,
        commanders_garrison=1,
        combat_strength=2,
        hand=starting_deck_instance_ids(0)[:5],
        resources=Resources(solari=0, spice=0, water=1),
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert legal_reveal_gain_actions(revealed, 0) == ()
    engine = UprisingRulesEngine()
    result = engine.apply(
        grant_combat_icon(revealed, 0),
        DomainAction("deploy_commanders", 0, (("count", 1),)),
    )
    deployed = result.state
    context = dict(deployed.decision_stack[-1].context)
    assert ("troops", "1", "skill:hardy") in reveal_pending_gains(context)
    (bonus,) = (e for e in result.events if e.kind == "skill_reveal_bonus")
    assert dict(bonus.payload)["troops"] == 1
    assert "water" not in dict(bonus.payload)
    supply = deployed.players[0].troops_supply
    (recruit,) = legal_reveal_gain_actions(deployed, 0)
    recruited = engine.apply(deployed, recruit).state
    assert recruited.players[0].troops_supply == supply - 1
    assert recruited.players[0].resources.water == 1


def test_reveal_bonuses_paid_at_the_start_are_not_paid_again_late() -> None:
    # A Commander already in the Conflict paid the bonuses when the Reveal
    # began [Bloodlines p. 4]; a second Commander deployed later adds none.
    from dune_imperium.rules.combat_deployment import grant_combat_icon
    from dune_imperium.rules.reveal_turn import legal_reveal_gain_actions

    owner = _seat_with_skills(
        skill_ids=(_skill("charismatic"), _skill("driven")),
        commanders_garrison=1,
        hand=starting_deck_instance_ids(0)[:5],
        resources=Resources(solari=0, spice=0, water=1),
    )
    state = refresh_pre_reveal_strength(RuleResult(state=_turn_state(owner))).state
    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    persuasion = dict(revealed.decision_stack[-1].context)["persuasion"]
    engine = UprisingRulesEngine()
    deployed = engine.apply(
        grant_combat_icon(revealed, 0),
        DomainAction("deploy_commanders", 0, (("count", 1),)),
    ).state
    assert deployed.players[0].commanders_conflict == 2
    assert dict(deployed.decision_stack[-1].context)["persuasion"] == persuasion
    assert len(legal_reveal_gain_actions(deployed, 0)) == 1  # Driven's, from start


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
    # v97 Occupation's Reveal bundle; v100 skip + Change Allegiances' third option.
    # v103 separate lines. v106: trash_intrigue_for_agent_card joins one
    # template per Intrigue instance (+40), and Branching Path's corrected
    # City icon shifts its agent_turn space coverage by +1 (see
    # test_action_codec.test_catalog_is_fixed_and_versioned_for_a_ruleset).
    # v107: +27, the generic Spy placement frame in every catalog.
    # v108 (2026-09-26 card-transcription audit, net per catalog without
    # Bloodlines): Maker Keeper's single City icon and Undercover Asset's
    # missing Spy icon [card faces] drop 36 agent_turn placements; a Conflict
    # reward Spy may recall first or decline [Main pp. 11, 20] (+13 recalls,
    # +1 decline) and so may a Leader Spy (+1); Covert Operation's two Reveal
    # Spies (+1 resume) and Unswerving Loyalty's Fremen Bond troop move (+1
    # resume, and Shadout Mapes' deploy/retreat/decline join every catalog,
    # +3).
    # decline_acquisition_spy: an acquisition-bonus Spy may pass up the
    # recall-first without a Spy in supply [Main pp. 11, 20] (+1).
    assert base.size == 4354 + 12 + 1 + 1 + 2 + 1 + 40 + 1 + 27 - 36 + 15 + 5 + 1

    actions = (
        DomainAction("acquire_sardaukar_commander", 2, (("skill_id", "loyal"),)),
        DomainAction("decline_sardaukar_commander", 1),
        DomainAction("recruit_sardaukar_commander", 3),
        DomainAction("trash_skill_for_strength", 0, (("skill_id", "desperate"),)),
        DomainAction("deploy_commanders", 0, (("count", 7),)),
        DomainAction("withdraw_commanders", 1, (("count", 1),)),
        DomainAction("retreat_intrigue_troops", 0, (("commanders", 2), ("count", 5))),
        DomainAction("deploy_intrigue_troops", 0, (("commanders", 1), ("count", 1))),
        DomainAction("retreat_two_troops_for_reveal", 0, (("commanders", 2),)),
        DomainAction("retreat_leader_commander", 3),
        DomainAction("flip_battle_card", 0, (("card_id", "skirmish_wild"),)),
    )
    for action in actions:
        assert codec.decode(codec.encode(action), action.actor) == action
        with pytest.raises(ValueError):
            base.encode(action)


def test_every_reachable_unit_retreat_is_encodable() -> None:
    # A Commander is its own component, not one of the twelve troops
    # [Bloodlines p. 4], so a seat's units in the Conflict reach 12 + 7 and
    # Tactical Option retreats "any number" of them (RetreatTroops(1, None)).
    # The catalog stopped at the troop total, so a 2026-09-10 collection run
    # reached retreat_intrigue_troops(commanders=1, count=13) -- legal for the
    # engine, unencodable for the codec.
    from dune_imperium.adapters.action_codec import (
        MAX_COMMANDER_DEPLOYMENT,
        MAX_DEPLOYMENT_COUNT,
    )
    from dune_imperium.rules.intrigue import _unit_count_arguments

    codec = ActionCodec(BLOODLINES)
    reachable = _unit_count_arguments(
        minimum=1,
        maximum=None,
        troops=MAX_DEPLOYMENT_COUNT,
        commanders=MAX_COMMANDER_DEPLOYMENT,
    )

    counts = [dict(arguments)["count"] for arguments in reachable]
    assert max(counts) == MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT
    for arguments in reachable:
        action = DomainAction("retreat_intrigue_troops", 0, arguments)
        assert codec.decode(codec.encode(action), 0) == action


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


# --- Commanders as troops in existing effects (slice 3) ---------------------


def test_intrigue_retreat_offers_the_commander_share() -> None:
    from dune_imperium.rules.combat import begin_combat_intrigue
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:go_to_ground:0"
    owner = _seat_with_skills(
        commanders_conflict=1,
        troops_conflict=1,
        troops_supply=8,
        agent_locations=(),
        agents_available=2,
        combat_strength=4,
        has_revealed=True,
        intrigue_cards=(card,),
    )
    state = replace(
        _turn_state(owner),
        phase=GamePhase.COMBAT,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        decision_stack=(),
        players=(
            owner,
            *(
                replace(seat, has_revealed=True)
                for seat in _turn_state(owner).players[1:]
            ),
        ),
    )
    opened = begin_combat_intrigue(state).state
    play = next(
        action
        for action in legal_intrigue_play_actions(opened, 0)
        if dict(action.arguments).get("card_id") == card
    )
    playing = apply_intrigue_play(opened, play).state

    retreats = legal_intrigue_choice_actions(playing, 0)
    assert {
        (dict(a.arguments).get("count"), dict(a.arguments).get("commanders"))
        for a in retreats
    } == {
        (1, None),
        (1, 1),
        (2, 1),
    }
    both = next(
        a for a in retreats if dict(a.arguments) == {"commanders": 1, "count": 2}
    )
    done = apply_intrigue_choice(playing, both).state.players[0]
    assert done.troops_conflict == 0 and done.commanders_conflict == 0
    assert done.commanders_garrison == 1 and done.troops_garrison == 4
    assert done.combat_strength == 0


def test_reveal_two_troop_retreat_may_include_commanders() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_troop_retreat,
        legal_reveal_troop_retreat_actions,
    )

    chani = next(
        instance_id
        for instance_id in __import__(
            "dune_imperium.content.uprising.imperium", fromlist=["x"]
        ).imperium_deck_instance_ids(False)
        if ":chani_clever_tactician:" in instance_id
    )
    owner = _seat_with_skills(
        hand=(chani,),
        commanders_conflict=1,
        troops_conflict=1,
        troops_supply=8,
        agent_locations=(),
        agents_available=2,
        combat_strength=4,
    )
    revealed = begin_reveal_turn(
        _turn_state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    actions = legal_reveal_troop_retreat_actions(revealed, 0)
    # One troop and one Commander: only the mixed pair reaches two units.
    assert [dict(a.arguments) for a in actions] == [{}, {"commanders": 1}]
    result = apply_reveal_troop_retreat(revealed, actions[1]).state.players[0]
    assert result.troops_conflict == 0 and result.commanders_conflict == 0
    assert result.commanders_garrison == 1
    assert result.combat_strength == 0


def test_desert_scouts_may_retreat_a_commander() -> None:
    from dune_imperium.rules.leader_abilities import (
        apply_leader_reveal_action,
        legal_leader_reveal_actions,
    )

    owner = _seat_with_skills(
        leader_id="lady_amber_metulli",
        hand=starting_deck_instance_ids(0)[:1],
        commanders_conflict=1,
        troops_conflict=1,
        troops_supply=8,
        agent_locations=(),
        agents_available=2,
        combat_strength=4,
    )
    revealed = begin_reveal_turn(
        _turn_state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    actions = legal_leader_reveal_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "retreat_leader_troop",
        "retreat_leader_commander",
    ]
    result = apply_leader_reveal_action(revealed, actions[1]).state.players[0]
    assert result.commanders_conflict == 0 and result.commanders_garrison == 1
    assert result.troops_conflict == 1
    sword_strength = dict(revealed.decision_stack[-1].context)["sword_strength"]
    assert isinstance(sword_strength, int)
    assert result.combat_strength == 2 + sword_strength


# --- wild battle icons (Bloodlines Conflicts) ------------------------------


def test_a_won_wild_conflict_is_not_matched_on_arrival() -> None:
    owner = _seat_with_skills(
        skill_ids=(),
        commanders_conflict=0,
        troops_conflict=1,
        troops_supply=11,
        troops_garrison=0,
        agent_locations=(),
        agents_available=2,
        has_revealed=True,
        combat_strength=2,
        objective_ids=("propaganda",),
    )
    state = replace(
        _turn_state(owner),
        phase=GamePhase.COMBAT,
        first_player=0,
        current_conflict_ids=("skirmish_wild",),
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
    winner = finish_combat(state).state.players[0]
    assert winner.won_conflict_ids == ("skirmish_wild",)
    # Wild icons are matched during the Endgame only [Main p. 20] [Bloodlines p. 5].
    assert winner.face_down_battle_card_ids == ()
    assert winner.victory_points == 1


def test_two_wild_icons_pair_with_each_other_in_the_endgame() -> None:
    from dune_imperium.rules.endgame import (
        apply_endgame_intrigue_action,
        begin_endgame_intrigue,
        legal_endgame_intrigue_actions,
    )

    owner = PlayerState(
        player_id=0,
        objective_ids=("propaganda",),
        won_conflict_ids=("storms_in_the_south", "skirmish_wild"),
    )
    state = replace(
        _turn_state(owner),
        phase=GamePhase.ENDGAME,
        first_player=0,
        decision_stack=(),
    )
    opened = begin_endgame_intrigue(state).state
    pairs = {
        (dict(a.arguments)["wild_card_id"], dict(a.arguments)["matching_card_id"])
        for a in legal_endgame_intrigue_actions(opened, 0)
        if a.action_id == "match_endgame_wild_icon"
    }
    assert pairs == {
        ("propaganda", "skirmish_wild"),
        ("propaganda", "storms_in_the_south"),
        ("skirmish_wild", "storms_in_the_south"),
    }
    match = DomainAction(
        "match_endgame_wild_icon",
        0,
        (("matching_card_id", "storms_in_the_south"), ("wild_card_id", "propaganda")),
    )
    codec = ActionCodec(BLOODLINES)
    assert codec.decode(codec.encode(match), 0) == match
    result = apply_endgame_intrigue_action(opened, match).state.players[0]
    assert result.victory_points == 2
    assert set(result.face_down_battle_card_ids) == {
        "propaganda",
        "storms_in_the_south",
    }
    # The third wild has no partner left.
    assert [
        a.action_id
        for a in legal_endgame_intrigue_actions(
            replace(opened, players=(result, *opened.players[1:])), 0
        )
    ] == ["pass_endgame_intrigue"]
