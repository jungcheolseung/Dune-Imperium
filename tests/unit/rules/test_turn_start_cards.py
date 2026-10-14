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

User ruling 2026-10-14 (OQ-095 (6), "그렇게 하자"): the start is asked first
and alone. While the seat can play either card, its turn frame offers just
those plays and ``decline_turn_start`` (``engine.turn_start_window_actions``);
the refusal ends the start and the turn's usual choices follow. So the other
actions that end the start meet a seat that held no playable card when its
turn opened, and the tests below check them by handing it the cards
afterwards (``_arm``): a card that arrives once the start is over is not
offered.
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
from dune_imperium.rules.engine import turn_start_window_actions
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
DECLINE = DomainAction("decline_turn_start", 0)


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


def _unarmed(*intrigue_cards: str, **fields: object) -> PlayerState:
    """The owner holding neither turn-start card: no window opens."""

    return replace(
        _owner(*intrigue_cards, **fields),
        hand=(DAGGER,),
        intrigue_cards=intrigue_cards,
    )


def _arm(state: GameState) -> GameState:
    """Hand seat 0 both turn-start cards, as a draw in the turn could."""

    owner = state.players[0]
    armed = replace(
        owner,
        hand=(LITANY, *owner.hand),
        intrigue_cards=(WITHDRAWN, *owner.intrigue_cards),
    )
    return replace(state, players=(armed, *state.players[1:]))


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


def test_the_turn_opens_with_both_cards_and_the_refusal_alone() -> None:
    state = _turn_state(_owner(CONTINGENCY_PLAN))

    assert _starts_open(state)
    assert TURN_START_OVER_KEY not in dict(state.decision_stack[-1].context)
    # Asked first and alone (user ruling 2026-10-14): no Agent or Reveal
    # turn, no Plot, until the start is answered.
    assert _offered(state) == (LITANY_PLAY, WITHDRAWN_PLAY, DECLINE)
    assert turn_start_window_actions(state, 0) == _offered(state)


@pytest.mark.parametrize(
    ("hand", "intrigue_cards", "play"),
    [
        pytest.param((LITANY, DAGGER), (), LITANY_PLAY, id="litany"),
        pytest.param((DAGGER,), (WITHDRAWN,), WITHDRAWN_PLAY, id="withdrawn"),
    ],
)
def test_either_card_alone_opens_the_window(
    hand: tuple[str, ...], intrigue_cards: tuple[str, ...], play: DomainAction
) -> None:
    owner = replace(_owner(), hand=hand, intrigue_cards=intrigue_cards)
    state = _turn_state(owner)

    assert _offered(state) == (play, DECLINE)
    played = ENGINE.apply(state, play)
    # The play is the start's own answer: it passes the turn to seat 1.
    turn = played.state.decision_stack[-1]
    assert turn.kind == FrameKind.TURN
    assert isinstance(turn.decision, PlayerDecision) and turn.decision.owner == 1
    assert "turn_start_declined" not in {event.kind for event in played.events}


def test_the_refusal_ends_the_start_and_the_usual_choices_follow() -> None:
    state = _turn_state(_owner(CONTINGENCY_PLAN))

    declined = ENGINE.apply(state, DECLINE)

    (event,) = declined.events
    assert event.kind == "turn_start_declined"
    assert event.payload == (("player", 0),)
    after = declined.state
    # The same turn frame, marked as any other owner action marks it.
    assert after.decision_stack == end_turn_start(state, 0).decision_stack
    assert not _starts_open(after)
    assert DECLINE not in _offered(after)
    ids = {action.action_id for action in _offered(after)}
    assert {"agent_turn", "reveal_turn"} <= ids
    assert _plot(CONTINGENCY_PLAN) in _offered(after)
    # Exactly what a seat that never held the cards is offered.
    unarmed = end_turn_start(_turn_state(_unarmed(CONTINGENCY_PLAN)), 0)
    assert _offered(after) == _offered(unarmed)
    # Neither card's state moved: both stay in hand, unplayed.
    assert after.players[0].hand == state.players[0].hand
    assert after.players[0].intrigue_cards == state.players[0].intrigue_cards


def test_no_window_opens_without_a_playable_card() -> None:
    # Neither card held: the turn opens on its usual choices, its start
    # still open for a card that a first action could bring.
    bare = _turn_state(_unarmed(CONTINGENCY_PLAN))
    assert turn_start_window_actions(bare, 0) == ()
    assert turn_start_is_open(bare, 0)
    ids = {action.action_id for action in _offered(bare)}
    assert {"agent_turn", "reveal_turn", "play_intrigue"} <= ids
    assert "decline_turn_start" not in ids

    # Withdrawn alone with every other seat revealed changes nothing, so it
    # is not playable (``test_withdrawn_is_not_offered_when_every_other_
    # seat_has_revealed``) and no window opens either.
    withdrawn_only = replace(_owner(), hand=(DAGGER,))
    alone = _turn_state(withdrawn_only, others_revealed=True)
    assert turn_start_window_actions(alone, 0) == ()
    assert DECLINE not in _offered(alone)
    assert WITHDRAWN_PLAY not in _offered(alone)
    # Litany Against Fear still draws, so it still opens the window there.
    both = _turn_state(_owner(), others_revealed=True)
    assert _offered(both) == (LITANY_PLAY, DECLINE)


def test_a_plot_ends_the_start_on_the_still_open_turn_frame() -> None:
    # The seat held no turn-start card when its turn opened, so the Plot is
    # its first action; a card it holds afterwards is not offered.
    state = _turn_state(_unarmed(CONTINGENCY_PLAN))
    assert _starts_open(_arm(state))

    plotted = _apply(state, _plot(CONTINGENCY_PLAN))

    turn = plotted.decision_stack[-1]
    assert turn.kind == FrameKind.TURN
    assert dict(turn.context)[TURN_START_OVER_KEY] is True
    assert not _starts_open(_arm(plotted))
    # Only the two cards go: the Agent and Reveal turns are still the choice.
    ids = {action.action_id for action in _offered(_arm(plotted))}
    assert {"agent_turn", "reveal_turn"} <= ids
    assert "decline_turn_start" not in ids
    # The mark is part of the state (hashed, kept by undo and replay).
    unmarked = replace(
        plotted,
        decision_stack=(replace(turn, context=(("round", 1), ("turn_owner", 0))),),
    )
    assert canonical_state_hash(unmarked) != canonical_state_hash(plotted)
    assert end_turn_start(unmarked, 0) == plotted


def test_a_plots_own_choice_frame_keeps_the_start_over() -> None:
    state = _turn_state(_unarmed(IMPERIUM_POLITICS))

    opened = _apply(state, _plot(IMPERIUM_POLITICS))

    # The choice sits above the turn frame, which already carries the mark.
    assert opened.decision_stack[-1].kind != FrameKind.TURN
    assert opened.decision_stack[0].kind == FrameKind.TURN
    assert not turn_start_is_open(opened, 0)
    done = _apply(opened, _offered(opened)[0])
    assert done.decision_stack[-1].kind == FrameKind.TURN
    assert not _starts_open(_arm(done))


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
    state = _turn_state(_unarmed(**fields), immortality)
    assert _starts_open(_arm(state))

    acted = act(state)

    assert acted.decision_stack[-1].kind == FrameKind.TURN
    assert not _starts_open(_arm(acted))


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

    # An answer following the owner's refusal and Plot leaves the start
    # over.
    plotted = _apply(_apply(state, DECLINE), _plot(CONTINGENCY_PLAN))
    answered_after = _answer_every_opponent(plotted)
    assert not _starts_open(answered_after)
    assert answered_after.decision_stack == plotted.decision_stack


def test_a_turn_passed_to_the_seat_itself_starts_afresh() -> None:
    # Every other seat has revealed: Litany Against Fear's pass opens the
    # seat's own next turn, whose start is open again -- playing a
    # turn-start card is the start's own action, not one that ends it.
    state = _turn_state(_owner(CONTINGENCY_PLAN), others_revealed=True)
    assert _offered(state) == (LITANY_PLAY, DECLINE)

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


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="base"),
        pytest.param({"choam_module": True}, id="choam"),
        pytest.param({"promo_cards": True}, id="promo"),
        pytest.param({"immortality": True, "choam_module": True}, id="immortality"),
        pytest.param({"arrakeen_scouts": True, "epic_game": True}, id="scouts-epic"),
    ],
)
def test_no_window_opens_outside_bloodlines(options: dict[str, bool]) -> None:
    # Both cards are Bloodlines cards -- Litany Against Fear in the Imperium
    # deck, Withdrawn among Piter De Vries' Twisted Intrigue cards -- so no
    # other game deals one, and its catalog has no ``decline_turn_start``
    # template to encode the window's refusal with (codec v146).
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
    from dune_imperium.content.uprising.leaders import leaders_for_choam
    from dune_imperium.rules.agent_turn import turn_start_cards

    config = RulesetConfig(**options)
    imperium = imperium_deck_instance_ids(
        config.choam_module, config.promo_cards, immortality=config.immortality
    )
    intrigue = intrigue_deck_instance_ids(
        config.choam_module, immortality=config.immortality
    )
    assert LITANY not in imperium
    every_card = PlayerState(player_id=0, hand=(*imperium, *STARTERS))
    assert turn_start_cards(every_card) == ()
    assert not any(
        option.turn_start_only
        for card in intrigue
        for option in intrigue_card_for_instance(card).options
    )
    assert "piter_de_vries" not in {
        leader.leader_id for leader in leaders_for_choam(config.choam_module)
    }
    templates = {template.action_id for template in ActionCodec(config).catalog}
    assert "decline_turn_start" not in templates

    # The Bloodlines game deals both and encodes the refusal.
    bloodlines = replace(config, bloodlines=True)
    assert LITANY in imperium_deck_instance_ids(
        bloodlines.choam_module, bloodlines.promo_cards, bloodlines=True
    )
    assert "piter_de_vries" in {
        leader.leader_id
        for leader in leaders_for_choam(bloodlines.choam_module, bloodlines=True)
    }
    codec = ActionCodec(bloodlines)
    assert codec.decode(codec.encode(DECLINE), actor=0) == DECLINE
