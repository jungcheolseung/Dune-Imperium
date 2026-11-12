"""Where a specimen may be returned to the supply outside the owner's turn.

"You may return any of your specimens to your supply at any time"
[Immortality p. 8]. OQ-050 (user ruling 2026-10-04, "앱 구현 방식으로
가자", following the Steam app): besides every decision of the owner's own
Agent or Reveal turn, the engine offers the return at the owner's Combat
Intrigue priority and -- while the supply has no troop -- at the owner's
Round Start Control defense, so the defending troop can come from a
specimen. Since 2026-11-09 (user decision) also in the owner's own Conflict
reward window, right before a reward that recruits, and (user decisions
2026-11-09, "넓힘", "계약 + (가) + (나)") in every window of the owner's
outside its own turn whose rows can take troops from its supply
(``immortality.SPECIMEN_RETURN_WINDOWS``): a shortfall there is lost
(OQ-030), not made up later as in its own turn.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import StateAgent, make_agent
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core import (
    ChanceDecision,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import DecisionFrame
from dune_imperium.core.events import GameEvent
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import begin_combat_intrigue, resolve_combat_rewards
from dune_imperium.rules.engine import LEGAL_ACTION_PROVIDERS
from dune_imperium.rules.frames import FrameKind, turn_owner_of
from dune_imperium.rules.immortality import (
    SPECIMEN_RETURN_WINDOWS,
    legal_specimen_return_actions,
)
from dune_imperium.rules.phases import begin_round

IMMORTALITY = RulesetConfig(immortality=True)


def _ids(actions: tuple[DomainAction, ...]) -> list[str]:
    return [action.action_id for action in actions]


# Stage B3d-3: the window shows its refusal as the refusal row naming the
# deployment it declines and the board space that asks it.
_DECLINE_DEFENSE = DomainAction(
    action_id="decline",
    actor=2,
    arguments=(("of", "deploy"), ("printed", "arrakeen"), ("source", "board_space")),
)


def _controlled_round_start(
    *, troops_supply: int, specimens: int, config: RulesetConfig = IMMORTALITY
) -> GameState:
    # Seat 2 controls Arrakeen as its Conflict is revealed.
    players = tuple(
        PlayerState(
            player_id=player,
            deck=tuple(f"player:{player}:card:{index}" for index in range(5)),
            troops_supply=troops_supply if player == 2 else 9,
            troops_garrison=12 - troops_supply - specimens if player == 2 else 3,
            specimens=specimens if player == 2 else 0,
            control_space_ids=("arrakeen",) if player == 2 else (),
        )
        for player in range(4)
    )
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.ROUND_START,
        first_player=0,
        players=players,
        conflict_deck=("siege_of_arrakeen",),
    )
    return begin_round(state).state


def test_a_defender_with_only_specimens_may_return_one_for_the_troop() -> None:
    engine = UprisingRulesEngine()
    state = _controlled_round_start(troops_supply=0, specimens=2)
    assert state.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert _ids(engine.whole_actions(state, 2)) == [
        "decline_control_defense",
        "return_specimen",
    ]
    assert engine.legal_actions(state, 2) == (
        _DECLINE_DEFENSE,
        *legal_specimen_return_actions(state, 2),
    )

    (returned,) = legal_specimen_return_actions(state, 2)
    after_return = engine.apply(state, returned).state

    defender = after_return.players[2]
    assert defender.specimens == 1 and defender.troops_supply == 1
    assert after_return.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    # One specimen covers the one defending troop; no second return. (Stage
    # B3d-2a: the window shows its deployment as the ``deploy`` row; the rules
    # take it as ``deploy_control_defense``.)
    assert _ids(engine.whole_actions(after_return, 2)) == [
        "decline_control_defense",
        "deploy_control_defense",
    ]
    deploy = engine.whole_actions(after_return, 2)[1]
    deployed = apply_whole(engine, after_return, deploy).state
    assert deployed.players[2].troops_conflict == 1
    assert deployed.players[2].troops_supply == 0


def test_a_defender_with_supply_troops_is_not_offered_a_return() -> None:
    engine = UprisingRulesEngine()
    state = _controlled_round_start(troops_supply=3, specimens=2)

    assert _ids(engine.whole_actions(state, 2)) == [
        "decline_control_defense",
        "deploy_control_defense",
    ]


def test_a_defender_whose_supply_emptied_meanwhile_may_return_a_specimen() -> None:
    # An effect in the same step (an Earn Any Alliance completion) can empty
    # the supply after the frame opened; a specimen still covers the troop.
    engine = UprisingRulesEngine()
    state = _controlled_round_start(troops_supply=1, specimens=1)
    defender = state.players[2]
    emptied = replace(
        defender,
        troops_supply=0,
        troops_garrison=defender.troops_garrison + 1,
    )
    state = replace(state, players=(*state.players[:2], emptied, state.players[3]))

    assert _ids(engine.whole_actions(state, 2)) == [
        "decline_control_defense",
        "return_specimen",
    ]
    assert engine.legal_actions(state, 2) == (
        _DECLINE_DEFENSE,
        *legal_specimen_return_actions(state, 2),
    )


def test_no_defense_opens_without_a_troop_or_a_specimen() -> None:
    state = _controlled_round_start(troops_supply=0, specimens=0)

    assert all(
        frame.kind != FrameKind.CONTROL_DEFENSE for frame in state.decision_stack
    )


def _combat_intrigue(config: RulesetConfig = IMMORTALITY) -> GameState:
    players = tuple(
        PlayerState(
            player_id=player,
            troops_supply=4,
            troops_garrison=(4 if config.immortality else 6)
            if player in (0, 1)
            else 8,
            troops_conflict=2 if player in (0, 1) else 0,
            specimens=2 if player in (0, 1) and config.immortality else 0,
        )
        for player in range(4)
    )
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=players,
    )
    return begin_combat_intrigue(state).state


def test_the_seat_with_combat_intrigue_priority_may_return_a_specimen() -> None:
    engine = UprisingRulesEngine()
    state = _combat_intrigue()
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision) and decision.owner == 0

    actions = engine.legal_actions(state, 0)
    assert {"pass_combat_intrigue", "return_specimen"} <= set(_ids(actions))
    # Only the seat holding priority.
    assert legal_specimen_return_actions(state, 1) == ()

    (returned,) = legal_specimen_return_actions(state, 0)
    after = engine.apply(state, returned).state

    assert after.players[0].specimens == 1
    assert after.players[0].troops_supply == 5
    # Priority stays with the seat; the return is not a pass.
    assert after.decision_stack[-1] == state.decision_stack[-1]


def test_combat_intrigue_offers_no_return_without_immortality() -> None:
    state = _combat_intrigue(RulesetConfig())

    assert legal_specimen_return_actions(state, 0) == ()


def _reward_window(*, specimens: int) -> GameState:
    """CHOAM Security's first place opens its winner's reward window
    ("Recruit 1 troop, take a Contract, 1 Spacing Guild Influence"); the
    winner, seat 0, has no troop in its supply. Seat 1, second, holds a
    specimen too, so only the window's owner decides who is offered one."""

    players = tuple(
        PlayerState(
            player_id=player,
            combat_strength=(8, 6, 4, 0)[player],
            troops_supply=(0, 8, 9, 9)[player],
            troops_garrison=(12 - specimens, 3, 3, 3)[player],
            specimens=(specimens, 1, 0, 0)[player],
        )
        for player in range(4)
    )
    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=players,
        current_conflict_ids=("choam_security",),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1", "intrigue:2", "intrigue:3"),
    )
    opened = resolve_combat_rewards(state).state
    frame = opened.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_REWARD_ICONS
    assert isinstance(frame.decision, PlayerDecision) and frame.decision.owner == 0
    return opened


def _troops_row(engine: UprisingRulesEngine, state: GameState) -> DomainAction:
    (row,) = (
        action
        for action in engine.whole_actions(state, 0)
        if action.action_id == "resolve_combat_reward_icon"
        and dict(action.arguments)["effect"] == "troops"
    )
    return row


def test_a_reward_recipient_may_return_a_specimen_before_its_reward_recruits() -> None:
    """"You may return any of your specimens to your supply at any time.
    (This could be useful if you need to recruit troops but have no more in
    your supply.)" [Immortality p. 8]: the recipient's own reward window
    offers the return (OQ-050, user decision 2026-11-09 -- "보상 받을 때 그때
    표본을 반환하면 되는거 아니야?"), so a reward that recruits with an empty
    supply can take the troop from a specimen. Combat makes up no recruit
    shortfall later (OQ-030)."""

    engine = UprisingRulesEngine()
    state = _reward_window(specimens=2)

    assert "return_specimen" in _ids(engine.legal_actions(state, 0))
    # Only the window's owner.
    assert legal_specimen_return_actions(state, 1) == ()

    (returned,) = legal_specimen_return_actions(state, 0)
    after = engine.apply(state, returned).state
    assert (after.players[0].specimens, after.players[0].troops_supply) == (1, 1)
    # The window stays open; the return answers none of its rows.
    assert after.decision_stack[-1] == state.decision_stack[-1]

    recruited = apply_whole(engine, after, _troops_row(engine, after)).state
    assert recruited.players[0].troops_garrison == 11
    assert recruited.players[0].troops_supply == 0

    # Not returned first, the recruit finds no troop and is lost.
    lost = apply_whole(engine, state, _troops_row(engine, state)).state
    assert lost.players[0].troops_garrison == 10
    assert lost.players[0].specimens == 2


def test_a_reward_recipient_without_specimens_is_offered_no_return() -> None:
    state = _reward_window(specimens=0)

    assert legal_specimen_return_actions(state, 0) == ()


# --- the windows outside the owner's turn ---------------------------------


def _window(
    kind: str,
    *,
    specimens: int = 1,
    phase: GamePhase = GamePhase.COMBAT,
    turn_of: int | None = None,
) -> GameState:
    """Seat 0's window of ``kind`` on top of the stack, outside its own turn
    unless ``turn_of`` names it: the predicate reads only the stack."""

    players = tuple(
        PlayerState(
            player_id=player,
            troops_supply=0 if player == 0 else 9,
            troops_garrison=12 - specimens if player == 0 else 3,
            specimens=specimens if player == 0 else 0,
        )
        for player in range(4)
    )
    frames: list[DecisionFrame] = []
    if turn_of is not None:
        frames.append(
            DecisionFrame(
                kind=FrameKind.AGENT_EFFECTS,
                frame_id=f"round:1:player:{turn_of}:agent_effects",
                decision=PlayerDecision(owner=turn_of, prompt="Agent turn"),
            )
        )
    frames.append(
        DecisionFrame(
            kind=kind,
            frame_id=f"round:1:test:{kind}",
            decision=PlayerDecision(owner=0, prompt="A window"),
        )
    )
    return GameState(
        config=IMMORTALITY,
        seed=1,
        phase=phase,
        first_player=0,
        players=players,
        decision_stack=tuple(frames),
    )


def test_every_window_outside_the_turn_lists_the_return() -> None:
    providers = LEGAL_ACTION_PROVIDERS
    missing = [
        kind
        for kind in SPECIMEN_RETURN_WINDOWS
        if legal_specimen_return_actions not in providers[kind]
    ]
    assert missing == []


@pytest.mark.parametrize("kind", sorted(SPECIMEN_RETURN_WINDOWS))
def test_the_owner_of_a_window_outside_its_turn_may_return_a_specimen(
    kind: str,
) -> None:
    returned = DomainAction(action_id="return_specimen", actor=0)
    for phase in (GamePhase.COMBAT, GamePhase.PLAYER_TURNS, GamePhase.ROUND_START):
        assert legal_specimen_return_actions(_window(kind, phase=phase), 0) == (
            returned,
        )
    # Another seat's turn is not the owner's: still outside its own.
    assert legal_specimen_return_actions(
        _window(kind, phase=GamePhase.PLAYER_TURNS, turn_of=2), 0
    ) == (returned,)
    # No specimen, or another seat's: nothing.
    assert legal_specimen_return_actions(_window(kind, specimens=0), 0) == ()
    assert legal_specimen_return_actions(_window(kind), 1) == ()


@pytest.mark.parametrize("kind", sorted(SPECIMEN_RETURN_WINDOWS))
def test_inside_its_own_turn_the_window_adds_no_return(kind: str) -> None:
    # The turn makes up a shortfall once a specimen frees a troop (OQ-030),
    # and the turn's own frames offer the return.
    state = _window(kind, phase=GamePhase.PLAYER_TURNS, turn_of=0)
    assert legal_specimen_return_actions(state, 0) == ()


_UPRISING_FULL = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)
_UPRISING_IX = RulesetConfig(
    rise_of_ix=True,
    choam_module=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    arrakeen_scouts=True,
    leader_draft=True,
)


def _short_recruit(config: RulesetConfig, seed: int, kind: str) -> tuple[
    GameState, DomainAction
]:
    """The first decision of ``kind`` in a seeded four-heuristic game where its
    owner, holding a specimen outside its turn, recruits short (the position
    the specimen return there is for)."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    agents = [make_agent("heuristic", seed * 10 + seat, config) for seat in range(4)]
    chance = ChanceResolver(seed=seed)
    for _ in range(30_000):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        owner = decision.owner
        legal = engine.legal_actions(state, owner)
        agent = agents[owner]
        view = engine.observe(state, owner)
        action = (
            agent.choose_action_with_state(state, view, legal)
            if isinstance(agent, StateAgent)
            else agent.choose_action(view, legal)
        )
        result = engine.apply(state, action, legal_actions=legal)
        if (
            state.decision_stack[-1].kind == kind
            and state.players[owner].specimens
            and turn_owner_of(state) != owner
            and any(
                event.kind == "troops_recruit_short"
                and dict(event.payload)["player"] == owner
                for event in result.events
            )
        ):
            return state, action
        state = result.state
    raise AssertionError("the game never met the shortfall")


def _troops(player: PlayerState) -> int:
    return player.troops_garrison + player.troops_conflict


@pytest.mark.parametrize(
    ("config", "seed", "kind"),
    [
        # Uprising with Rise of Ix, round 8: a Conflict reward's Influence
        # completes a Contract whose reward recruits (supply 1, 1 specimen).
        (_UPRISING_IX, 9150005, FrameKind.CONTRACT_REWARD_ICONS),
        # Uprising with every expansion, round 7: a Tech bought in Combat,
        # Rapid Dropships, recruits (supply 0, 1 specimen). Re-searched
        # 2026-11-10 on the engine merged with the printed-effects audit, where
        # seed 9110046's game (Ornithopter Fleet) no longer meets it: 9110385
        # is the first of 9110000-9110630 (9110631 meets it too).
        (_UPRISING_FULL, 9110385, FrameKind.TECH_ACQUISITION),
    ],
    ids=["contract", "tech"],
)
def test_a_specimen_returned_first_covers_the_recruit(
    config: RulesetConfig, seed: int, kind: str
) -> None:
    engine = UprisingRulesEngine()
    state, recruit = _short_recruit(config, seed, kind)
    owner = recruit.actor
    returned = DomainAction(action_id="return_specimen", actor=owner)
    assert returned in engine.legal_actions(state, owner)

    short = engine.apply(state, recruit)
    after_return = engine.apply(state, returned).state
    # The window waits: the return answers none of its rows.
    assert after_return.decision_stack[-1] == state.decision_stack[-1]
    covered = engine.apply(after_return, recruit)
    # The specimen became the troop the recruit lacked: one troop more, one
    # short less.
    assert _troops(covered.state.players[owner]) == (
        _troops(short.state.players[owner]) + 1
    )
    assert _short(covered.events, owner) == _short(short.events, owner) - 1


def _short(events: tuple[GameEvent, ...], owner: int) -> int:
    total = 0
    for event in events:
        payload = dict(event.payload)
        if event.kind == "troops_recruit_short" and payload["player"] == owner:
            short = payload["short"]
            assert isinstance(short, int)
            total += short
    return total
