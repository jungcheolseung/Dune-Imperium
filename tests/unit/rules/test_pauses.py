"""The engine's pauses before a reveal that follows a seat's choices.

A project convention for the play server's undo, not a rule (OQ-103,
rules/pauses.py): a one-outcome chance decision before each Conflict reward
recipient after the first (tests/unit/rules/test_combat.py), after a Control
defense (tests/unit/rules/test_phases.py) and before every Round Start after
the first (here). A pause draws nothing from the random stream, and every
step it holds back runs as before, in the same order. The one exception is
Earn Any Alliance's completion: it runs at the end of the step that took the
Alliance, also when that step stopped at a pause (OQ-056, OQ-103, user
decision 2026-10-09).
"""

from dataclasses import replace

from tests.support.pauses import answer_pause, pause_outcome
from tests.unit.rules.test_combat import _reward_state

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.core.chance import FIXED_OUTCOME_SUFFIX, is_fixed_outcome
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.core.events import GameEvent
from dune_imperium.rules.combat import begin_combat_intrigue, resolve_combat_rewards
from dune_imperium.rules.engine import UprisingRulesEngine, _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.pauses import CONTINUE, ROUND_START, push_pause
from dune_imperium.rules.setup import create_initial_state
from dune_imperium.simulation import run_random_round

SELECTED_LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "staban_tuek",
)
CHOAM_BLOODLINES = RulesetConfig(bloodlines=True, choam_module=True)
EARN_ANY_ALLIANCE = "contract:bloodlines_earn_any_alliance"
INTRIGUE = intrigue_deck_instance_ids(True, bloodlines=True)


def test_the_resolver_answers_a_pause_without_drawing() -> None:
    shuffle = ChanceDecision(
        decision_id="round:2:player:0:discard_shuffle",
        prompt="Shuffle",
        options=("a", "b", "c", "d", "e"),
        count=5,
    )
    plain = ChanceResolver(seed=7)
    paused = ChanceResolver(seed=7)
    state = create_initial_state(RulesetConfig(), seed=7, leader_ids=SELECTED_LEADERS)
    pause = push_pause(state.state, ROUND_START, "round:2").state.decision_stack[-1]
    assert isinstance(pause.decision, ChanceDecision)
    assert is_fixed_outcome(pause.decision)
    assert pause.decision.decision_id == f"round:2:{ROUND_START}{FIXED_OUTCOME_SUFFIX}"

    answered = paused.resolve(pause.decision)

    assert answered == ChanceOutcome(pause.decision.decision_id, (CONTINUE,))
    assert paused.resolve(shuffle) == plain.resolve(shuffle)


def test_a_reshuffle_of_one_card_still_draws() -> None:
    # Only a pause is a fixed outcome: a one-card shuffle keeps drawing, as
    # every seeded game recorded before the pauses did.
    one = ChanceDecision(
        decision_id="round:2:player:0:discard_shuffle", prompt="x", options=("a",)
    )
    assert not is_fixed_outcome(one)


def test_every_round_start_after_the_first_pauses_before_the_reveal() -> None:
    engine = UprisingRulesEngine()
    finished = run_random_round(engine, RulesetConfig(), 0, 1000)
    pauses = [
        step.decision_id
        for step in finished.replay.steps
        if isinstance(step, ChanceOutcome)
        and step.decision_id.endswith(FIXED_OUTCOME_SUFFIX)
    ]
    # Round 1 opens with the setup; the pause stands before round 2's
    # reshuffles and reveal (and before reward recipients after the first).
    assert f"round:2:{ROUND_START}{FIXED_OUTCOME_SUFFIX}" in pauses


def test_the_round_start_pause_holds_back_the_reveal_and_the_draw() -> None:
    setup = create_initial_state(
        RulesetConfig(), seed=71, leader_ids=SELECTED_LEADERS
    ).state
    after_round = replace(
        setup, round_number=1, phase=GamePhase.ROUND_START, decision_stack=()
    )

    paused = _advance_automatic(RuleResult(state=after_round)).state

    top = paused.decision_stack[-1]
    assert top.kind == FrameKind.PAUSE
    assert isinstance(top.decision, ChanceDecision)
    assert paused.conflict_deck == after_round.conflict_deck
    assert paused.current_conflict_ids == after_round.current_conflict_ids
    assert [player.hand for player in paused.players] == [
        player.hand for player in after_round.players
    ]
    # Nobody has an action while the pause waits.
    engine = UprisingRulesEngine()
    assert all(engine.legal_actions(paused, seat) == () for seat in range(4))

    revealed = engine.apply(
        paused, ChanceOutcome(top.decision.decision_id, (CONTINUE,))
    ).state

    assert revealed.round_number == 2
    assert revealed.current_conflict_ids == (
        *after_round.current_conflict_ids,
        after_round.conflict_deck[0],
    )
    assert revealed.phase is GamePhase.PLAYER_TURNS
    top = revealed.decision_stack[-1]
    assert isinstance(top.decision, PlayerDecision)


def test_the_first_round_start_does_not_pause() -> None:
    setup = create_initial_state(
        RulesetConfig(), seed=71, leader_ids=SELECTED_LEADERS
    ).state
    before = replace(
        setup, round_number=0, phase=GamePhase.ROUND_START, decision_stack=()
    )

    started = _advance_automatic(RuleResult(state=before)).state

    assert started.round_number == 1
    assert all(frame.kind != FrameKind.PAUSE for frame in started.decision_stack)


def test_the_rewards_end_at_a_pause_before_the_conflict_end_windows() -> None:
    # The last recipient's choice stops here, so it can still be taken back
    # before the Conflict-end windows open, like the earlier recipients'
    # choices -- in every round, the last one too (2026-10-08 review).
    paid = resolve_combat_rewards(_reward_state("skirmish_desert_mouse")).state
    assert paid.combat_rewards_resolved and not paid.decision_stack

    paused = _advance_automatic(RuleResult(state=paid)).state

    top = paused.decision_stack[-1]
    assert top.kind == FrameKind.PAUSE
    assert isinstance(top.decision, ChanceDecision)
    assert top.decision.decision_id == f"round:1:conflict_end{FIXED_OUTCOME_SUFFIX}"
    assert not paused.combat_end_triggers_offered
    # Its answer offers the windows (none here) and nothing else.
    offered = answer_pause(paused).state
    assert offered.combat_end_triggers_offered
    assert offered.phase is GamePhase.COMBAT


def _alliance_combat(
    conflict_id: str,
    influence: Influence,
    *others: PlayerState,
    config: RulesetConfig = CHOAM_BLOODLINES,
    **extra: object,
) -> GameState:
    """Seat 0 wins ``conflict_id`` holding Earn Any Alliance (2 Solari and 2
    troops), one Influence short of an Alliance, with an empty supply and
    four troops in the Conflict; everyone is to pass Combat Intrigue."""

    values: dict[str, object] = {
        "player_id": 0,
        "active_contract_ids": (EARN_ANY_ALLIANCE,),
        "influence": influence,
        "troops_supply": 0,
        "troops_garrison": 8,
        "troops_conflict": 4,
        "combat_strength": 8,
        "has_revealed": True,
    }
    values.update(extra)
    seats = {seat.player_id: seat for seat in others}
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=2,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        conflict_deck=("skirmish_desert_mouse",),
        current_conflict_ids=(conflict_id,),
        intrigue_deck=INTRIGUE[:6],
        face_up_contract_ids=("contract:arrakeen_i",),
        sardaukar_commander_space_ids=(),
        players=(
            PlayerState(**values),  # type: ignore[arg-type]
            *(
                seats.get(seat, PlayerState(player_id=seat, has_revealed=True))
                for seat in range(1, 4)
            ),
        ),
    )
    return begin_combat_intrigue(state).state


def _second() -> PlayerState:
    """Seat 1, second in the Conflict with one troop."""

    return PlayerState(
        player_id=1,
        troops_supply=8,
        troops_conflict=1,
        combat_strength=2,
        has_revealed=True,
    )


def _pass_combat_intrigue(engine: UprisingRulesEngine, state: GameState) -> Transition:
    """Every seat passes Combat Intrigue; the last pass pays the rewards."""

    transition = None
    while state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE:
        decision = state.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        passing = next(
            action
            for action in engine.legal_actions(state, decision.owner)
            if action.action_id.startswith("pass_")
        )
        transition = engine.apply(state, passing)
        state = transition.state
    assert transition is not None
    return transition


def _completions(events: tuple[GameEvent, ...]) -> list[dict[str, object]]:
    return [
        dict(event.payload)
        for event in events
        if event.kind == "contract_completed"
        and dict(event.payload)["contract_id"] == EARN_ANY_ALLIANCE
    ]


def _troops(state: GameState) -> tuple[int, int, int]:
    seat = state.players[0]
    return seat.troops_supply, seat.troops_garrison, seat.troops_conflict


def _to_round_start(engine: UprisingRulesEngine, state: GameState) -> RuleResult:
    """Answer the pauses and decline the windows up to the next Round Start."""

    events: list[GameEvent] = []
    while state.phase is GamePhase.COMBAT:
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.PAUSE:
            transition = engine.apply(state, pause_outcome(state))
        else:
            assert frame.kind == FrameKind.CONFLICT_END_TRIGGER
            assert isinstance(frame.decision, PlayerDecision)
            transition = engine.apply(
                state,
                DomainAction(
                    action_id="decline_conflict_end_intrigue",
                    actor=frame.decision.owner,
                ),
            )
        state = transition.state
        events.extend(transition.events)
    return RuleResult(state=state, events=tuple(events))


# "Earn any Alliance is completed the next time you take an Alliance token
# you do not already have" [Bloodlines p. 2]; "Once all rewards have been
# given, each player takes their troops from the Conflict and puts them in
# their supply" [Main p. 14]; a recruit takes only what the supply holds
# [Main p. 10] [FAQ p. 4], and outside a turn a shortfall is dropped (OQ-030,
# re-ruled 2026-10-04). User decision 2026-10-09 ("2번-A: 늘 정리 전"): the
# Contract completes at the end of the step that took the Alliance, a pause
# included, so in Combat always before the cleanup (OQ-056, OQ-103). It used
# to ride on a pause to where the run of automatic steps ended, after the
# cleanup, and then took its troops from the ones the Conflict gave back.


def test_earn_any_alliance_completes_at_the_conflict_end_pause() -> None:
    # Protect the Sietches' first place: a troop, water and Fremen 3 -> 4.
    # Seat 1's second place is paid in the same step, which stops at the
    # pause before the Conflict-end windows.
    engine = UprisingRulesEngine()
    state = _alliance_combat(
        "protect_the_sietches", Influence(fremen=3), _second()
    )

    paid = _pass_combat_intrigue(engine, state)

    top = paid.state.decision_stack[-1]
    assert top.kind == FrameKind.PAUSE
    assert top.frame_id == f"round:2:conflict_end{FIXED_OUTCOME_SUFFIX}"
    # The pause frame carries nothing but its point.
    assert top.context == (("point", "conflict_end"),)
    assert [completed["troops"] for completed in _completions(paid.events)] == [0]
    shortfalls = [
        dict(event.payload)
        for event in paid.events
        if event.kind == "troops_recruit_short"
    ]
    assert shortfalls[-1] == {"player": 0, "recruited": 0, "requested": 2, "short": 2}
    seat = paid.state.players[0]
    assert seat.completed_contract_ids == (EARN_ANY_ALLIANCE,)
    assert seat.resources.solari == 2
    assert _troops(paid.state) == (0, 8, 4)

    # The four troops the cleanup gives back do not make it up.
    after = _to_round_start(engine, paid.state)
    assert _completions(after.events) == []
    assert _troops(after.state) == (4, 8, 0)


def test_earn_any_alliance_takes_only_what_the_supply_holds() -> None:
    # Two troops in the supply: the reward's troop takes one, the Contract
    # the other of its two.
    engine = UprisingRulesEngine()
    state = _alliance_combat(
        "protect_the_sietches",
        Influence(fremen=3),
        troops_supply=2,
        troops_garrison=6,
    )

    paid = _pass_combat_intrigue(engine, state)

    assert paid.state.decision_stack[-1].kind == FrameKind.PAUSE
    assert [completed["troops"] for completed in _completions(paid.events)] == [1]
    assert _troops(paid.state) == (0, 8, 4)
    after = _to_round_start(engine, paid.state)
    assert _troops(after.state) == (4, 8, 0)


def test_earn_any_alliance_completes_at_the_pause_before_the_next_recipient() -> (
    None
):
    # Skirmish (Crysknife)'s first place: Influence of the seat's choice. The
    # step that takes Fremen stops at the pause before seat 1 is paid.
    engine = UprisingRulesEngine()
    state = _alliance_combat("skirmish_crysknife", Influence(fremen=3), _second())
    choice = _pass_combat_intrigue(engine, state).state
    assert choice.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE

    chosen = engine.apply(
        choice,
        DomainAction(
            action_id="choose_combat_reward_influence",
            actor=0,
            arguments=(("faction", "fremen"),),
        ),
    )

    top = chosen.state.decision_stack[-1]
    assert top.kind == FrameKind.PAUSE
    assert top.frame_id == f"round:2:reward:1:rewards{FIXED_OUTCOME_SUFFIX}"
    assert top.context == (("point", "rewards"),)
    assert [completed["troops"] for completed in _completions(chosen.events)] == [0]
    assert _troops(chosen.state) == (0, 8, 4)
    after = _to_round_start(engine, chosen.state)
    assert _completions(after.events) == []
    assert _troops(after.state) == (4, 8, 0)


def test_earn_any_alliance_completes_before_the_seat_s_reward_choice() -> None:
    # CHOAM Security's first place: a troop, a Contract and Spacing Guild
    # 3 -> 4. The step stops at the seat's own Contract choice, still before
    # the cleanup, as it did before the pauses. (Only first places give
    # Influence, and no printed second or third place that follows one
    # opens a choice, so a later recipient's choice cannot end that step.)
    engine = UprisingRulesEngine()
    state = _alliance_combat(
        "choam_security", Influence(spacing_guild=3), _second()
    )

    paid = _pass_combat_intrigue(engine, state)

    assert paid.state.decision_stack[-1].kind == FrameKind.CONTRACT_MARKET
    assert [completed["troops"] for completed in _completions(paid.events)] == [0]
    assert _troops(paid.state) == (0, 8, 4)


def test_earn_any_alliance_completes_before_a_conflict_end_window_opens() -> None:
    # With Immortality, four units in the Conflict and an Intrigue card, the
    # seat gets a Conflict-end window once the pause is answered (OQ-103).
    # The Contract completed in the step that took the Alliance; neither the
    # window nor the cleanup after it completes it again. The held card is
    # one the Intrigue deck (INTRIGUE[:6]) does not also hold.
    engine = UprisingRulesEngine()
    state = _alliance_combat(
        "protect_the_sietches",
        Influence(fremen=3),
        config=RulesetConfig(bloodlines=True, choam_module=True, immortality=True),
        intrigue_cards=(INTRIGUE[6],),
    )

    paid = _pass_combat_intrigue(engine, state)
    assert paid.state.decision_stack[-1].kind == FrameKind.PAUSE
    assert [completed["troops"] for completed in _completions(paid.events)] == [0]

    window = engine.apply(paid.state, pause_outcome(paid.state))
    assert window.state.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert _completions(window.events) == []
    assert _troops(window.state) == (0, 8, 4)
    after = _to_round_start(engine, window.state)
    assert _completions(after.events) == []
    assert _troops(after.state) == (4, 8, 0)
