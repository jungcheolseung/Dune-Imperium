"""Servo-Receivers' Signet Ring ability inside the owner's open turn (OQ-062).

Servo-Receivers' acquire box prints the Signet Ring icon: "you use the
Signet Ring ability (with the corresponding icon) on your Leader"
[Main p. 20] [Servo-Receivers Tech tile]. The ability resolves in its own
``leader_signet`` frame, and its "this turn" parts belong to the turn the
tile was acquired in (OQ-062 (b)). Rapid Engineering ("[discard] → [-1]
[Tech]" [Rapid Engineering card], a Plot) can acquire the tile at any point
of an Agent or Reveal turn, including before the Agent is placed.
"""

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind

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
