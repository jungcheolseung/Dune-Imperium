"""The two "At the start of your turn" cards are only the turn's first action.

"At the start of your turn: Put this card into play -> Draw a card and pass
your turn." [Litany Against Fear card]; "At the start of your turn: Pass your
turn." [Withdrawn card]. User ruling 2026-10-04 (OQ-095 (6)): "턴을 넘기는
카드(Litany Against Fear, Withdrawn)는 근데 조건 보면 at the start of your
turn 이잖아. 턴 시작 후 이 카드를 사용하는 것 말고 다른 행동을 했으면 이제 턴
시작이 끝났으니 이 카드를 사용할 수 없게 되는게 맞다고 봐." Any action of the
turn's owner while its turn frame is open ends the start of the turn
(``frames.TURN_START_OVER_KEY`` on that frame, set by the engine); another
seat's answer and the engine's automatic steps do not. The Emperor track Spy
case is in ``test_track_spy.py``.
"""

from collections.abc import Callable
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import (
    TURN_START_OVER_KEY,
    FrameKind,
    end_turn_start,
    turn_start_is_open,
)
from dune_imperium.rules.unit_loss import opponent_unit_loss_frames

ENGINE = UprisingRulesEngine()
STARTERS = starting_deck_instance_ids(0)
DAGGER = next(card for card in STARTERS if ":dagger:" in card)
LITANY = "imperium:litany_against_fear:0"
WITHDRAWN = "intrigue:twisted_withdrawn:0"
CONTINGENCY_PLAN = "intrigue:contingency_plan:0"  # Plot: +2 Solari
IMPERIUM_POLITICS = "intrigue:imperium_politics:0"  # Plot: a Faction choice
LITANY_PLAY = DomainAction("play_turn_start_card", 0, (("card_id", LITANY),))


def _plot(card_id: str) -> DomainAction:
    return DomainAction("play_intrigue", 0, (("card_id", card_id), ("option", 0)))


WITHDRAWN_PLAY = _plot(WITHDRAWN)


def _owner(*intrigue_cards: str, **fields: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "leader_id": "piter_de_vries",
        "hand": (LITANY, DAGGER),
        "deck": tuple(card for card in STARTERS if card != DAGGER)[:4],
        "intrigue_cards": (WITHDRAWN, *intrigue_cards),
        "resources": Resources(solari=1),
    }
    values.update(fields)
    return PlayerState(**values)  # type: ignore[arg-type]


def _turn_state(
    owner: PlayerState,
    config: RulesetConfig | None = None,
    *,
    others_revealed: bool = False,
) -> GameState:
    others = tuple(
        PlayerState(player_id=seat, has_revealed=others_revealed)
        for seat in range(1, 4)
    )
    return GameState(
        config=config or RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        imperium_row=imperium_deck_instance_ids(False)[:5],
        imperium_deck=imperium_deck_instance_ids(False)[5:15],
        players=(owner, *others),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.TURN,
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
                context=(("round", 1), ("turn_owner", 0)),
            ),
        ),
    )


def _offered(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    return ENGINE.legal_actions(state, seat)


def _apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action).state


def _starts_open(state: GameState) -> bool:
    """Both cards are offered exactly while the start of the turn is open."""

    offered = _offered(state)
    litany = LITANY_PLAY in offered
    withdrawn = WITHDRAWN_PLAY in offered
    assert litany == withdrawn == turn_start_is_open(state, 0)
    return litany


def test_both_cards_are_offered_as_the_turns_first_action() -> None:
    state = _turn_state(_owner())

    assert _starts_open(state)
    assert TURN_START_OVER_KEY not in dict(state.decision_stack[-1].context)


def test_a_plot_ends_the_start_on_the_still_open_turn_frame() -> None:
    state = _turn_state(_owner(CONTINGENCY_PLAN))

    plotted = _apply(state, _plot(CONTINGENCY_PLAN))

    turn = plotted.decision_stack[-1]
    assert turn.kind == FrameKind.TURN
    assert dict(turn.context)[TURN_START_OVER_KEY] is True
    assert not _starts_open(plotted)
    # Only the two cards go: the Agent and Reveal turns are still the choice.
    ids = {action.action_id for action in _offered(plotted)}
    assert {"agent_turn", "reveal_turn"} <= ids
    # The mark is part of the state (hashed, kept by undo and replay).
    unmarked = replace(
        plotted,
        decision_stack=(replace(turn, context=(("round", 1), ("turn_owner", 0))),),
    )
    assert canonical_state_hash(unmarked) != canonical_state_hash(plotted)
    assert end_turn_start(unmarked, 0) == plotted


def test_a_plots_own_choice_frame_keeps_the_start_over() -> None:
    state = _turn_state(_owner(IMPERIUM_POLITICS))

    opened = _apply(state, _plot(IMPERIUM_POLITICS))

    # The choice sits above the turn frame, which already carries the mark.
    assert opened.decision_stack[-1].kind != FrameKind.TURN
    assert opened.decision_stack[0].kind == FrameKind.TURN
    assert not turn_start_is_open(opened, 0)
    done = _apply(opened, _offered(opened)[0])
    assert done.decision_stack[-1].kind == FrameKind.TURN
    assert not _starts_open(done)


def _return_specimen(state: GameState) -> GameState:
    return _apply(state, DomainAction("return_specimen", 0))


def _use_family_atomics(state: GameState) -> GameState:
    return _apply(state, DomainAction("use_family_atomics", 0))


@pytest.mark.parametrize(
    ("fields", "act"),
    [
        pytest.param(
            {"specimens": 1, "troops_supply": 8},
            _return_specimen,
            id="return_specimen",
        ),
        pytest.param(
            {"family_atomics": True}, _use_family_atomics, id="family_atomics"
        ),
    ],
)
def test_any_other_owner_action_on_the_turn_frame_ends_the_start(
    fields: dict[str, object], act: Callable[[GameState], GameState]
) -> None:
    immortality = RulesetConfig(bloodlines=True, immortality=True)
    state = _turn_state(_owner(**fields), immortality)
    assert _starts_open(state)

    acted = act(state)

    assert acted.decision_stack[-1].kind == FrameKind.TURN
    assert not _starts_open(acted)


def _answer_every_opponent(state: GameState) -> GameState:
    """Seats 1-3 each answer a unit-loss window stacked on seat 0's turn."""

    state = opponent_unit_loss_frames(state, 0, source="test").state
    for seat in (1, 2, 3):
        top = state.decision_stack[-1]
        assert isinstance(top.decision, PlayerDecision)
        assert top.decision.owner == seat
        state = _apply(state, _offered(state, seat)[0])
    assert state.decision_stack[-1].kind == FrameKind.TURN
    return state


def test_another_seats_answer_neither_ends_nor_reopens_the_start() -> None:
    state = _turn_state(_owner(CONTINGENCY_PLAN))

    # Other seats' actions on frames stacked on the turn are not the
    # owner's: the start stays open.
    answered = _answer_every_opponent(state)
    assert _starts_open(answered)
    assert answered.decision_stack == state.decision_stack

    # An answer following the owner's Plot leaves the start over.
    plotted = _apply(state, _plot(CONTINGENCY_PLAN))
    answered_after = _answer_every_opponent(plotted)
    assert not _starts_open(answered_after)
    assert answered_after.decision_stack == plotted.decision_stack


def test_a_turn_passed_to_the_seat_itself_starts_afresh() -> None:
    # Every other seat has revealed: Litany Against Fear's pass opens the
    # seat's own next turn, whose start is open again -- playing a
    # turn-start card is the start's own action, not one that ends it.
    state = _turn_state(_owner(CONTINGENCY_PLAN), others_revealed=True)
    assert LITANY_PLAY in _offered(state)

    passed = _apply(state, LITANY_PLAY)
    turn = passed.decision_stack[-1]
    assert turn.kind == FrameKind.TURN
    assert isinstance(turn.decision, PlayerDecision) and turn.decision.owner == 0
    assert TURN_START_OVER_KEY not in dict(turn.context)
    assert turn_start_is_open(passed, 0)
    assert LITANY in passed.players[0].in_play


def test_withdrawn_is_not_offered_when_every_other_seat_has_revealed() -> None:
    # "Pass your turn." [Withdrawn card] with every other seat revealed hands
    # the turn straight back [Main p. 8]: its only effect changes nothing, so
    # it is not offered ("To play an Intrigue card, you must meet its
    # conditions and pay its costs." [FAQ p. 2], with the user's ruling of
    # 2026-10-06 that an Intrigue option needs an effect that can change
    # something). Litany Against Fear is an Imperium card and keeps its pass.
    from dune_imperium.content.uprising.effect_dsl import PassTurn
    from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
    from dune_imperium.rules.effect_interpreter import option_unplayable_reason

    option = intrigue_card_for_instance(WITHDRAWN).options[0]
    alone = _turn_state(_owner(), others_revealed=True)
    assert WITHDRAWN_PLAY not in _offered(alone)
    assert LITANY_PLAY in _offered(alone)
    assert option_unplayable_reason(alone, 0, option) == PassTurn()
    # One seat still to reveal is enough.
    waiting = replace(
        alone,
        players=(
            *alone.players[:2],
            replace(alone.players[2], has_revealed=False),
            alone.players[3],
        ),
    )
    assert WITHDRAWN_PLAY in _offered(waiting)
