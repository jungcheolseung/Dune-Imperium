"""Ilesa Ecaz's One Step Ahead (Rise of Ix, stage P4e).

docs/rules/rise-of-ix.md 10: "One Step Ahead: Round Start에 손의 카드 하나를
따로 둔다. 라운드의 둘째 turn을 시작할 때 공개해 손으로 되돌린다. 그 turn에 그 카드로
Agent를 보내면 Agent 아이콘이 정확히 하나면 spice 1, 아니면 1 Solari | `[Rise of Ix
p. 10]` `[FAQ p. 2]`; Agent 없는 pass와 Weirding Way 추가 turn 모두 센다(OQ-119 사용자
확정)"; 9.1: "Ilesa Ecaz — 라운드 첫 turn에 Reveal을 하면 따로 둔 카드를 공개 카드에
더한다; 그때 spice·Solari는 없다"; 9.2: ""otherwise"는 따로 둔 카드로 Agent를
보냈지만 Agent 아이콘이 정확히 하나가 아닐 때; 그 카드를 쓰지 않으면 아무것도 없음";
9.3: "Ilesa가 따로 둔 카드는 trash·discard 대상이 아니다(BGG Forum)", "Ilesa의
두 번째 Agent에 Dispatch an Envoy를 쓰면 아이콘이 넷 더해져 1 Solari(Agent를 보내기
전에 쓴 경우)".

- **The set-aside.** OQ-122 (user ruling 2026-10-23): Round Start's last
  step, after every seat's five cards, the flipped Tech's return and the
  Round Start lines that decide nothing (Piter's Twisted card, Holtzman
  Engine's card, Shuttle Fleet's Solari), from a hand that holds Holtzman
  Engine's card, and before the first turn. The draw opens the first turn's
  frame in the same step (``phases.draw_round_hands``), so the choice is a
  ``ROUND_START_SET_ASIDE`` frame laid right above that turn frame -- below a
  personal reshuffle Holtzman Engine's card may still wait on, which is
  resolved first. Face down (``PlayerState.set_aside_card_id``): every seat
  sees that she set a card aside, only she which (rise-of-ix.md 13); it is in
  no zone a trash or a discard reaches.
- **The second turn.** Her turns are counted as they end
  (``PlayerState.turns_finished_round``; a pass without an Agent counts,
  OQ-119), so the turn that opens after one finished turn is the second: at
  its start, before she acts, the card is revealed and returns to her hand,
  public from then on (``hand_public``, OQ-010), and the turn frame names it
  for the placement's bonus (``ONE_STEP_AHEAD_CARD_KEY``).
- **The bonus.** An Agent sent with that card in that turn gains a spice if
  the card has exactly one Agent icon then -- its printed ones and those
  granted to the card played this turn (Dispatch an Envoy's four when played
  before the Agent, the designer ruling; OQ-055: added icons count) -- and a
  Solari otherwise (``agent_turn.apply_agent_action``).
- **A first-turn Reveal.** The set-aside card joins the revealed cards (as a
  card returned to the hand at the Reveal's start, like Chairdog's), with no
  bonus (``reveal_turn.begin_reveal_turn``).
"""

from collections.abc import Callable, Mapping
from copy import replace
from typing import Final

from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind, owned_top_frame, replace_player

ILESA: Final = "ilesa_ecaz"
SET_ASIDE_ACTION: Final = "set_aside_leader_card"
# The turn frame's key naming the card that returned at its start.
ONE_STEP_AHEAD_CARD_KEY: Final = "one_step_ahead_card"
ONE_STEP_AHEAD_SPICE: Final = 1
ONE_STEP_AHEAD_SOLARI: Final = 1


def push_set_aside(state: GameState) -> GameState:
    """Lay Ilesa's set-aside choice right above the round's first turn frame
    (module docstring); no choice with an empty hand."""

    seat = next(
        (
            player
            for player in state.players
            if player.leader_id == ILESA and player.hand
        ),
        None,
    )
    if seat is None:
        return state
    turn_index = next(
        (
            index
            for index, frame in enumerate(state.decision_stack)
            if frame.kind == FrameKind.TURN
        ),
        None,
    )
    if turn_index is None:
        raise RuntimeError("One Step Ahead's set-aside needs the first turn's frame")
    frame = DecisionFrame(
        kind=FrameKind.ROUND_START_SET_ASIDE,
        frame_id=f"round:{state.round_number}:player:{seat.player_id}:set_aside",
        decision=PlayerDecision(
            owner=seat.player_id,
            prompt="One Step Ahead: set aside a card from your hand",
        ),
        context=(("player", seat.player_id),),
    )
    stack = state.decision_stack
    return replace(
        state,
        decision_stack=(*stack[: turn_index + 1], frame, *stack[turn_index + 1 :]),
    )


def legal_set_aside_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Each card of her hand ("Set aside a card from your hand" [Ilesa Ecaz
    card]): the set-aside is mandatory."""

    if owned_top_frame(state, FrameKind.ROUND_START_SET_ASIDE, player) is None:
        return ()
    return tuple(
        DomainAction(
            action_id=SET_ASIDE_ACTION,
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in dict.fromkeys(state.players[player].hand)
    )


def apply_set_aside(state: GameState, action: DomainAction) -> RuleResult:
    """Set the chosen card aside face down: everyone sees that she did, only
    she which card (docs/rules/rise-of-ix.md 13)."""

    if action not in legal_set_aside_actions(state, action.actor):
        raise ValueError("action is not a legal One Step Ahead set-aside")
    player = action.actor
    card_id = str(dict(action.arguments)["card_id"])
    owner = state.players[player]
    hand = list(owner.hand)
    hand.remove(card_id)
    # The other seats cannot tell which card left the hand, so a hand card
    # they knew (``hand_public``, OQ-010) is no longer known to be there:
    # keeping it, or dropping only the card set aside, would tell them which
    # card it was (rise-of-ix.md 13 keeps it hers alone).
    aside = replace(owner, hand=tuple(hand), hand_public=(), set_aside_card_id=card_id)
    source = f"round:{state.round_number}:player:{player}:leader:{ILESA}:set_aside"
    return RuleResult(
        state=replace(
            state.pop_decision(), players=replace_player(state.players, aside)
        ),
        events=(
            GameEvent(
                event_id=source,
                kind="leader_ability_resolved",
                payload=(("leader_id", ILESA), ("player", player)),
            ),
            GameEvent(
                event_id=f"{source}:card",
                kind="leader_ability_resolved",
                payload=(
                    ("card_id", card_id),
                    ("leader_id", ILESA),
                    ("player", player),
                ),
                visible_to=(player,),
            ),
        ),
    )


def finish_turn_count(player: PlayerState) -> PlayerState:
    """Count one more finished turn of Ilesa's this round (OQ-119: a pass
    counts), ending the turn's wait for the returned card's bonus. Other
    Leaders keep the fields at their defaults."""

    if player.leader_id != ILESA:
        return player
    return replace(
        player,
        turns_finished_round=player.turns_finished_round + 1,
        set_aside_returned_turn=False,
    )


def return_set_aside_card(result: RuleResult) -> RuleResult:
    """At the start of her second turn, reveal the set-aside card and return
    it to her hand (module docstring); a transition that opens no such turn
    is returned itself."""

    state = result.state
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return result
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.TURN or not isinstance(frame.decision, PlayerDecision):
        return result
    owner = state.players[frame.decision.owner]
    if (
        owner.leader_id != ILESA
        or not owner.set_aside_card_id
        or owner.turns_finished_round != 1
    ):
        return result
    card_id = owner.set_aside_card_id
    returned = replace(
        owner,
        hand=(*owner.hand, card_id),
        hand_public=(*owner.hand_public, card_id),
        set_aside_card_id="",
        set_aside_returned_turn=True,
    )
    context = {**dict(frame.context), ONE_STEP_AHEAD_CARD_KEY: card_id}
    turn = replace(frame, context=tuple(sorted(context.items())))
    source = (
        f"round:{state.round_number}:player:{owner.player_id}:leader:{ILESA}:returned"
    )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, returned),
            decision_stack=(*state.decision_stack[:-1], turn),
        ),
        events=(
            *result.events,
            GameEvent(
                event_id=source,
                kind="card_returned_to_hand",
                payload=(("card_id", card_id), ("player", owner.player_id)),
            ),
        ),
    )


def reveal_set_aside_card(state: GameState, player: int) -> RuleResult:
    """A first-turn Reveal: the set-aside card joins the revealed hand, with
    no bonus ("라운드 첫 turn에 Reveal을 하면 따로 둔 카드를 공개 카드에 더한다; 그때
    spice·Solari는 없다" [Rise of Ix p. 10])."""

    owner = state.players[player]
    if owner.leader_id != ILESA or not owner.set_aside_card_id:
        return RuleResult(state=state)
    card_id = owner.set_aside_card_id
    revealed = replace(
        owner,
        hand=(*owner.hand, card_id),
        hand_public=(*owner.hand_public, card_id),
        set_aside_card_id="",
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, revealed)),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:leader:{ILESA}:"
                    "revealed"
                ),
                kind="card_returned_to_hand",
                payload=(("card_id", card_id), ("player", player)),
            ),
        ),
    )


def one_step_ahead_bonus(
    owner: PlayerState,
    turn_context: Mapping[str, ActionValue],
    card_instance_id: str,
    icon_count: Callable[[], int],
) -> tuple[int, int]:
    """The (spice, Solari) an Agent sent with ``card_instance_id`` earns:
    the returned card in the turn it returned, a spice for exactly one Agent
    icon (``icon_count``, the card's icons as it is played) and a Solari
    otherwise; (0, 0) for any other placement."""

    if (
        owner.leader_id != ILESA
        or not owner.set_aside_returned_turn
        or turn_context.get(ONE_STEP_AHEAD_CARD_KEY) != card_instance_id
    ):
        return 0, 0
    if icon_count() == 1:
        return ONE_STEP_AHEAD_SPICE, 0
    return 0, ONE_STEP_AHEAD_SOLARI
