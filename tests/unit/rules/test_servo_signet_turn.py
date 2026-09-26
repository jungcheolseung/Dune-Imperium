"""Servo-Receivers' Signet Ring ability inside the owner's open turn (OQ-062).

Servo-Receivers' acquire box prints the Signet Ring icon: "you use the
Signet Ring ability (with the corresponding icon) on your Leader"
[Main p. 20] [Servo-Receivers Tech tile]. The ability resolves in its own
``leader_signet`` frame, and its "this turn" parts belong to the turn the
tile was acquired in (OQ-062 (b)). Rapid Engineering ("[discard] → [-1]
[Tech]" [Rapid Engineering card], a Plot) can acquire the tile at any point
of an Agent or Reveal turn, including before the Agent is placed.
"""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
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
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.leader_abilities import IMPLEMENTED_ABILITY_LEADER_IDS

TECH = RulesetConfig(bloodlines=True, tech_module=True)
ENGINE = UprisingRulesEngine()
RAPID_ENGINEERING = "intrigue:rapid_engineering:0"
ELIMINATE_ALLIES = "imperium:eliminate_allies:0"
DAGGER = "player:0:starter:dagger:0"
DIPLOMACY = "player:0:starter:diplomacy:0"


def _owner(leader_id: str, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "leader_id": leader_id,
        "hand": (DIPLOMACY, DAGGER),
        "deck": (
            "player:0:starter:reconnaissance:0",
            "player:0:starter:seek_allies:0",
            "player:0:starter:convincing_argument:0",
        ),
        "intrigue_cards": (RAPID_ENGINEERING,),
        "resources": Resources(solari=4, spice=6, water=2),
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _turn_state(owner: PlayerState) -> GameState:
    return GameState(
        config=TECH,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:4],
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        tech_stacks=(("servo_receivers",), (), ()),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _act(state: GameState, action_id: str, **arguments: object) -> GameState:
    """Apply the owner's legal action with ``action_id`` and ``arguments``."""

    action = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return ENGINE.apply(state, action).state


def _send_agent(state: GameState, space_id: str) -> GameState:
    return _act(state, "agent_turn", card_id=DIPLOMACY, space_id=space_id)


def _acquire_servo(state: GameState) -> GameState:
    """Play Rapid Engineering, discarding the Dagger, and buy the tile."""

    state = _act(state, "play_intrigue", card_id=RAPID_ENGINEERING)
    state = _act(state, "choose_intrigue_discard", card_id=DAGGER)
    return _act(state, "acquire_tech", tech_id="servo_receivers")


def _deploy_counts(state: GameState) -> list[object]:
    return [
        dict(action.arguments)["count"]
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "deploy_troops"
    ]


def _agent_frame(state: GameState) -> dict[str, object]:
    frame = next(
        frame
        for frame in state.decision_stack
        if frame.kind == FrameKind.AGENT_EFFECTS
    )
    return dict(frame.context)


def test_servo_signet_trash_keeps_eliminate_allies_troops_deployable() -> None:
    # Eliminate Allies: "When this card is trashed: 2 troops" [Eliminate
    # Allies card]; "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에
    # deploy할 수 있다" [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md).
    # Chronicler's Insight trashes it from the Servo frame during an Agent
    # turn at Heighliner: before, the leader_signet frame on top kept the
    # trash from counting the troops, so the Agent turn lost them.
    owner = _owner(
        "princess_irulan", hand=(DIPLOMACY, DAGGER, ELIMINATE_ALLIES), deck=()
    )
    placed = _send_agent(_turn_state(owner), "heighliner")
    assert _deploy_counts(placed) == [1, 2]
    signet = _acquire_servo(placed)
    assert signet.decision_stack[-1].kind == FrameKind.LEADER_SIGNET
    trashed = ENGINE.apply(
        signet,
        DomainAction(
            action_id="trash_leader_card",
            actor=0,
            arguments=(("card_id", ELIMINATE_ALLIES),),
        ),
    ).state
    assert trashed.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert trashed.players[0].troops_garrison == 3 + 2
    assert _agent_frame(trashed)["troops_recruited"] == 2
    assert _deploy_counts(trashed) == [1, 2, 3, 4]


# --- Before the Agent is placed ----------------------------------------------
#
# A Plot played from the turn frame belongs to the Agent turn that follows:
# "You may play a Plot Intrigue card any time during one of your Agent or
# Reveal turns" [Main p. 7], and troops it recruits join that turn's
# deployment (frames.update_turn_recruits). OQ-062 (b): in the owner's Agent
# turn "Emperor의 배치 금지가 그 turn에 걸리며, recruit한 troop은 그 turn의
# 배치 몫에 들어가고 Harkonnen Advisor의 troop은 배치 불가로 남는다". Before,
# the Servo frame folded its counters only into an Agent-turn effect frame,
# so all three were lost when the tile came before the placement.


def _servo_before_placement(owner: PlayerState, pick: str = "") -> GameState:
    state = _acquire_servo(_turn_state(owner))
    while state.decision_stack[-1].kind == FrameKind.LEADER_SIGNET:
        state = _act(state, pick)
    assert [frame.kind for frame in state.decision_stack] == [FrameKind.TURN]
    return state


@pytest.mark.parametrize("spies_supply", [3, 0])
@pytest.mark.parametrize("leader_id", sorted(IMPLEMENTED_ABILITY_LEADER_IDS))
def test_every_servo_signet_choice_before_placement_returns_to_the_turn(
    leader_id: str, spies_supply: int
) -> None:
    # Every choice path closes the leader_signet frame and leaves only the
    # owner's turn frame, waiting for the Agent placement (merge guard, like
    # the Landsraad and Reveal walk in test_tech.py).
    codec = ActionCodec(TECH)
    owner = _owner(
        leader_id,
        influence=Influence(emperor=2, fremen=2),
        troops_conflict=2,
        troops_supply=7,
        spies_supply=spies_supply,
        spy_post_ids=()
        if spies_supply
        else (
            "arrakis-deep-desert",
            "fremen-desert-tactics-fremkit",
            "emperor-sardaukar-dutiful-service",
        ),
    )
    pending = [_acquire_servo(_turn_state(owner))]
    leaves = 0
    while pending:
        current = pending.pop()
        if all(f.kind != FrameKind.LEADER_SIGNET for f in current.decision_stack):
            leaves += 1
            assert [f.kind for f in current.decision_stack] == [FrameKind.TURN]
            continue
        decision = current.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        actions = ENGINE.legal_actions(current, decision.owner)
        assert actions, "a leader_signet frame must offer a choice"
        for action in actions:
            assert codec.decode(codec.encode(action), action.actor) == action
            pending.append(ENGINE.apply(current, action).state)
        assert leaves + len(pending) < 400, "Signet choices must terminate"
    assert leaves >= 1


def test_harkonnen_advisor_troop_from_the_turn_frame_stays_undeployable() -> None:
    # "1 troop. You can't deploy this troop to the Conflict this turn."
    # [Piter De Vries card]; "garrison에 그 troop만 있으면 이번 turn에는
    # 아무것도 배치할 수 없다" (OQ-038 (b)).
    from dune_imperium.rules.combat_deployment import undeployable_troops_this_turn

    owner = _owner("piter_de_vries", troops_garrison=0, troops_supply=12)
    before = _servo_before_placement(owner)
    assert before.players[0].troops_garrison == 1
    assert undeployable_troops_this_turn(before, 0) == 1
    placed = _send_agent(before, "heighliner")
    assert _agent_frame(placed)["undeployable_troops"] == 1
    assert _deploy_counts(placed) == []


def test_emperor_ban_from_the_turn_frame_blocks_the_agent_turn() -> None:
    # "Units can't be deployed to the Conflict this turn" [Shaddam Corrino
    # IV card]; the ability "affects only the turn in which it is
    # triggered" [FAQ p. 3] and takes effect at once [Main p. 17].
    from dune_imperium.rules.leader_abilities import units_deployment_blocked

    owner = _owner("shaddam_corrino_iv")
    before = _servo_before_placement(owner, "gain_leader_signet_troop")
    assert units_deployment_blocked(before, 0)
    placed = _send_agent(before, "heighliner")
    context = _agent_frame(placed)
    assert context["units_deploy_blocked"] is True
    assert context["pending_combat_deployment"] is False
    assert _deploy_counts(placed) == []


def test_warmaster_troop_from_the_turn_frame_joins_the_allowance() -> None:
    # "You may deploy any or all units recruited during your current turn
    # ... plus up to two more units from your garrison" [Main p. 10].
    owner = _owner("gurney_halleck", troops_garrison=2, troops_supply=10)
    before = _servo_before_placement(owner)
    assert before.players[0].troops_garrison == 3
    placed = _send_agent(before, "heighliner")
    assert _agent_frame(placed)["troops_recruited"] == 1
    assert _deploy_counts(placed) == [1, 2, 3]


def test_harkonnen_troop_from_turn_frame_stays_undeployable_in_a_reveal() -> None:
    # Servo-Receivers used before the Agent is placed folds Harkonnen
    # Advisor's undeployable troop into the bare "turn" frame (OQ-062 (b)).
    # Choosing Reveal instead of an Agent turn must carry that troop's
    # undeployability into the Reveal, not drop it: "You can't deploy this
    # troop to the Conflict this turn" [Piter De Vries card] (OQ-038 (b)),
    # and the Combat 아이콘 deploys "이번 turn에 recruit한 유닛 전부와
    # garrison에서 최대 두 개" [Bloodlines pp. 5, 12] regardless of whether
    # the turn opened as an Agent or a Reveal turn (docs/rules/player-turns.
    # md:137 [Main p. 10] [FAQ p. 4], OQ-062 2026-09-26 보강 2). Before,
    # ``begin_reveal_turn`` always started at ``reveal_troops_recruited = 0``
    # with no ``undeployable_troops``, discarding the turn frame's own troop.
    owner = _owner(
        "piter_de_vries", troops_garrison=0, troops_supply=12, combat_icon_turn=True
    )
    before = _servo_before_placement(owner)
    assert before.players[0].troops_garrison == 1
    assert dict(before.decision_stack[-1].context)["undeployable_troops"] == 1

    revealed = _act(before, "reveal_turn")

    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL
    reveal_context = dict(revealed.decision_stack[-1].context)
    assert reveal_context["combat_deployment"] is True
    assert reveal_context["undeployable_troops"] == 1
    assert _deploy_counts(revealed) == []


# --- In a Reveal turn --------------------------------------------------------


def _reveal_with_servo(owner: PlayerState) -> GameState:
    """Reveal with a Combat icon open, then acquire Servo-Receivers."""

    from dune_imperium.rules.tech import push_tech_acquisition

    revealed = _act(_turn_state(owner), "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["combat_deployment"] is True
    opened = push_tech_acquisition(revealed, 0, discount=1, source="test").state
    bought = _act(opened, "acquire_tech", tech_id="servo_receivers")
    assert bought.decision_stack[-1].kind == FrameKind.REVEAL
    return bought


def test_harkonnen_advisor_troop_stays_undeployable_in_a_reveal_turn() -> None:
    # A Combat icon gained earlier this turn opens the Reveal deployment:
    # "You may deploy any units you recruit this turn and up to two more
    # from your garrison" [Bloodlines p. 5]. Piter's troop still "can't be
    # deployed to the Conflict this turn" [Piter De Vries card] (OQ-038);
    # before, the Reveal offered deploy_troops(1) for it.
    owner = _owner(
        "piter_de_vries", troops_garrison=0, troops_supply=12, combat_icon_turn=True
    )
    bought = _reveal_with_servo(owner)
    assert bought.players[0].troops_garrison == 1
    assert _deploy_counts(bought) == []

    # Warmaster's troop is recruited this turn and deploys.
    gurney = _owner(
        "gurney_halleck", troops_garrison=0, troops_supply=12, combat_icon_turn=True
    )
    assert _deploy_counts(_reveal_with_servo(gurney)) == [1]
