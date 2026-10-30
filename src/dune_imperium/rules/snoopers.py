"""Tessia Vernius' Careful Observation (Rise of Ix, stage P4e).

docs/rules/rise-of-ix.md 10: "Careful Observation: 시작에 Snooper token을 각 track의
Influence 2 칸에. 그 token에 도달할 때마다 Snooper track의 맨 위 덮이지 않은 보상을
받는다(① discard → spice 1, ② 그 track의 4칸 보너스, ③ 그 track에 Influence 1, ④ ②와
③) | ... | 디자이너 판정 9.3. "도달"은 Influence를 한꺼번에 얻으며 지나가도 도달
(Uprising과 같다). 한 효과가 여러 진영을 함께 올리면 소유자가 순서를 고르고(Quid Pro
Quo는 진영마다 줄, "Choose two:"는 고른 순서) ... (OQ-153)"; 9.3: "Tessia: 버릴 카드가
없을 때 첫 Snooper를 얻어도 token은 가져가 맨 위 칸을 덮고, spice는 못 받음(BGG
Forum) | 채택"; 13: Snooper tokens are public.

- **Setup.** A token on each track's Influence 2 space
  (``PlayerState.snooper_faction_ids``), set with the seat's Leader
  (``place_snooper_tokens``).
- **Reaching a token** is judged inside every Influence gain
  (``influence._reach_snooper``): the token is taken and its reward is the
  top uncovered one -- the count of tokens already taken says which.
  Rewards (2), (3) and (4) are paid with the gain.
- **Reward (1)**, "[discard] -> 1 spice", is an arrow, so optional
  [FAQ p. 3]. Its discard is a hand card's [FAQ p. 2] and the arrow's cost:
  an Unload card pays its box before the spice (``unload_at_once``,
  rise-of-ix.md 7), and a box holding a decision holds the spice until it is
  answered (``rules.unload``'s hold, the payer ``snooper_discard``). The gain
  only announces it (``SNOOPER_REACHED_EVENT``);
  it is offered once the action's handler is done
  (``settle_snooper_discards``): a row of her own turn
  (``turn_rows.SNOOPER_DISCARD``, no refusal, lapsing at the turn-end press,
  OQ-095 (2)), or outside it the ``OPTIONAL_DISCARD`` window with a refusal.
  With no card in hand outside her turn no window opens: the token still
  covers the reward, and no spice comes (the BGG ruling above).
"""

from collections.abc import Iterable, Mapping
from copy import replace
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.frames import FrameKind, context_str, owned_top_frame
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.influence import (
    SNOOPER_DISCARD_REWARD,
    SNOOPER_REACHED_EVENT,
)
from dune_imperium.rules.unload import hold_payer, push_unload_hold, unload_holds

TESSIA: Final = "tessia_vernius"
DISCARD_ACTION: Final = "discard_snooper_card"
DECLINE_ACTION: Final = "decline_snooper_discard"
SNOOPER_DISCARD_SPICE: Final = 1
DISCARD_PROMPT: Final = "Snooper reward: discard a card for 1 spice, or decline"
_FRAME: Final = "Snooper discard frame"


def place_snooper_tokens(state: GameState) -> GameState:
    """Tessia Vernius' Snooper tokens, one on each Influence track's 2 space
    ("Game Start: Put a Snooper token at 2 Influence on each Influence
    track" [Tessia Vernius card, app text]); a game without her is
    returned itself."""

    if not any(seat.leader_id == TESSIA for seat in state.players):
        return state
    return replace(
        state,
        players=tuple(
            replace(
                seat,
                snooper_faction_ids=tuple(faction.value for faction in Faction),
            )
            if seat.leader_id == TESSIA
            else seat
            for seat in state.players
        ),
    )


def snooper_event_ids(events: Iterable[GameEvent]) -> frozenset[str]:
    """The ids of the reached tokens among ``events``, for ``skip``."""

    return frozenset(
        event.event_id for event in events if event.kind == SNOOPER_REACHED_EVENT
    )


def _window(player: int, source: str, faction: str) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.OPTIONAL_DISCARD,
        frame_id=f"{source}:optional_discard",
        decision=PlayerDecision(owner=player, prompt=DISCARD_PROMPT),
        context=(("faction", faction), ("player", player), ("source", source)),
    )


def settle_snooper_discards(
    result: RuleResult, *, skip: frozenset[str] = frozenset()
) -> RuleResult:
    """Offer reward (1) of each token ``result``'s events reached
    (``skip``: event ids already settled earlier in the transition)."""

    owed = [
        event
        for event in result.events
        if event.kind == SNOOPER_REACHED_EVENT
        and event.event_id not in skip
        and dict(event.payload).get("reward") == SNOOPER_DISCARD_REWARD
    ]
    if not owed:
        return result
    state = result.state
    for event in owed:
        payload = dict(event.payload)
        player, faction = payload["player"], payload["faction"]
        assert isinstance(player, int) and isinstance(faction, str)
        queued = turn_rows.queue(
            state, player, (turn_rows.SNOOPER_DISCARD, event.event_id, faction)
        )
        if queued is not None:
            state = queued
        elif state.players[player].hand:
            state = state.push_decision(_window(player, event.event_id, faction))
    return RuleResult(state=state, events=result.events)


def _discard_rows(state: GameState, player: int) -> tuple[DomainAction, ...]:
    return tuple(
        DomainAction(
            action_id=DISCARD_ACTION, actor=player, arguments=(("card_id", card_id),)
        )
        for card_id in dict.fromkeys(state.players[player].hand)
    )


def legal_snooper_window_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """The ``OPTIONAL_DISCARD`` window: each hand card, or the refusal."""

    if owned_top_frame(state, FrameKind.OPTIONAL_DISCARD, player) is None:
        return ()
    return (
        *_discard_rows(state, player),
        DomainAction(action_id=DECLINE_ACTION, actor=player),
    )


def legal_snooper_row_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Reward (1) waiting on her own turn: each hand card, no refusal."""

    frame = turn_rows.rows_frame(state, player)
    if frame is None or not any(
        kind == turn_rows.SNOOPER_DISCARD for kind, _, _ in turn_rows.pending(frame)
    ):
        return ()
    return _discard_rows(state, player)


def apply_snooper_discard(state: GameState, action: DomainAction) -> RuleResult:
    """Discard the chosen hand card for 1 spice, or refuse the window."""

    player = action.actor
    window = owned_top_frame(state, FrameKind.OPTIONAL_DISCARD, player)
    if window is not None:
        if action not in legal_snooper_window_actions(state, player):
            raise ValueError("action is not a legal Snooper discard choice")
        source = context_str(dict(window.context), "source", owner=_FRAME)
        working = state.pop_decision()
        if action.action_id == DECLINE_ACTION:
            return RuleResult(
                state=working,
                events=(
                    GameEvent(
                        event_id=f"{source}:snooper_discard_declined",
                        kind="snooper_discard_declined",
                        payload=(("player", player),),
                    ),
                ),
            )
    else:
        if action not in legal_snooper_row_actions(state, player):
            raise ValueError("action is not a legal Snooper discard row")
        frame = turn_rows.rows_frame(state, player)
        assert frame is not None
        item = next(
            item
            for item in turn_rows.pending(frame)
            if item[0] == turn_rows.SNOOPER_DISCARD
        )
        source = item[1]
        working = turn_rows.take(state, player, item)
    card_id = str(dict(action.arguments)["card_id"])
    discarded = discard_personal_card_from_hand(
        working, player, card_id, source=f"{source}:snooper", unload_at_once=True
    )
    if unload_holds(discarded.events):
        # The discarded card's box holds a decision (a Freighter, a Tech
        # Negotiation, an acquisition): the spice waits for it, "비용 → 효과
        # 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤 오른쪽으로
        # 간다" (docs/rules/rise-of-ix.md 7, ``rules.unload``).
        return RuleResult(
            state=push_unload_hold(
                discarded.state,
                player,
                source=f"{source}:snooper",
                payer=_SNOOPER_PAYER,
                values={"source": source},
            ),
            events=discarded.events,
        )
    paid = _snooper_spice(discarded.state, player, source)
    return RuleResult(state=paid.state, events=(*discarded.events, *paid.events))


_SNOOPER_PAYER: Final = "snooper_discard"


def _snooper_spice(state: GameState, player: int, source: str) -> RuleResult:
    """Reward (1)'s right side: the 1 spice its discard buys."""

    owner = state.players[player]
    paid = replace(
        owner,
        resources=replace(
            owner.resources, spice=owner.resources.spice + SNOOPER_DISCARD_SPICE
        ),
    )
    players = tuple(
        paid if seat.player_id == player else seat for seat in state.players
    )
    return RuleResult(
        state=replace(state, players=players),
        events=(
            resources_gained_event(
                f"{source}:snooper", player, spice=SNOOPER_DISCARD_SPICE
            ),
        ),
    )


@hold_payer(_SNOOPER_PAYER)
def _pay_held_snooper_spice(
    state: GameState, player: int, values: Mapping[str, ActionValue]
) -> RuleResult:
    """The spice once the discarded card's Unload is decided, in her own
    turn's row or the out-of-turn window alike."""

    return _snooper_spice(state, player, str(values["source"]))
