"""Tessia's Snooper discard holds its spice while the discarded card's Unload
is decided.

Rule: docs/rules/rise-of-ix.md 7, the designer ruling "비용 → 효과 줄의
왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤 오른쪽으로 간다".
Tessia Vernius' Snooper reward ① is "discard → spice 1" (rise-of-ix.md 10):
the discard is the arrow's cost, the spice its right side. A discarded card
whose Unload box holds a decision (Boundless Ambition's acquisition, Freighter
Fleet's Freighter) holds the spice until it is answered (``rules.unload``'s
hold, the payer ``snooper_discard``), in her own turn's row and in the
``OPTIONAL_DISCARD`` window outside it alike; a plain box (Water Peddler's
water) is still paid inside the discard, before the spice. The hold also
opens above another seat's waiting frame and gives it back unchanged. Reached
inside a cost's own hold in her turn, the reward waits as a turn row until
that hold has closed (OQ-112 (4)); two holds stacked by hand still pay each
side once, the inner first.

The two measurement games that crashed before the payer existed ("a cost's
Unload holds a decision but its path pushed no hold") are replayed whole too.
"""

import json
import logging
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    Resources,
    RuleResult,
    Transition,
)
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine, turn_rows, unload
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.frames import FrameKind, is_unload_hold
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.snoopers import settle_snooper_discards
from dune_imperium.server.persistence import deserialize_step, serialize_step
from dune_imperium.simulation.invariants import check_observation_privacy
from dune_imperium.simulation.runner import run_policy_game

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM,
    rise_of_ix=True,
    promo_cards=True,
    first_player_seat_zero=True,
)
LEADERS = (
    "tessia_vernius",
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
CODEC = ActionCodec(CONFIG)
AMBITION = "imperium:boundless_ambition:0"
FLEET = "imperium:freighter_fleet:0"
PEDDLER = "imperium:water_peddler:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
SNOOPER_ROW = "discard_snooper_card"
LIAISON = "arrakis_liaison"
TRUTHSAYER = "imperium:truthsayer:0"
NONE = Resources(solari=0, spice=0, water=0)
TESSIA_SECOND = (
    "glossu_rabban",
    "tessia_vernius",
    "count_ilban_richese",
    "earl_memnon_thorvald",
)


def _start(leaders: tuple[str, ...] = LEADERS) -> GameState:
    """Seed 3 dealt with ``leaders`` (the engine's Leaders only seat the
    game; every later step goes through ``ENGINE``)."""

    state = UprisingRulesEngine(leader_ids=leaders).reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return state


def _give(
    state: GameState, seat: int, hand: tuple[str, ...], **fields: object
) -> GameState:
    """``seat`` holds ``hand`` (taken out of every other zone first), with
    ``fields`` changed."""

    named = set(hand)
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(held for held in player.deck if held not in named),
            hand=tuple(held for held in player.hand if held not in named),
            discard_pile=tuple(
                held for held in player.discard_pile if held not in named
            ),
        )
        if player.player_id == seat:
            cleaned = replace(cleaned, hand=hand, **fields)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(held for held in state.imperium_deck if held not in named),
        imperium_row=tuple(held for held in state.imperium_row if held not in named),
    )


def _tessia(card: str) -> GameState:
    """Seat 0 (Tessia) holds Diplomacy and ``card``, one Emperor Influence
    short of her Snooper token, with no resources."""

    return _give(
        _start(),
        0,
        (DIPLOMACY, card),
        influence=Influence(emperor=1),
        resources=NONE,
    )


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert CODEC.decode(CODEC.encode(row), seat) == row
    return rows


def _steps_of(
    state: GameState, action_id: str, **arguments: object
) -> tuple[RuleResult, tuple[DomainAction, ...]]:
    """Seat 0's whole action taken by its steps (``_seat_steps``)."""

    return _seat_steps(state, 0, action_id, **arguments)


def _seat_steps(
    state: GameState, seat: int, action_id: str, **arguments: object
) -> tuple[RuleResult, tuple[DomainAction, ...]]:
    """``seat``'s whole action taken by its steps, each offered row
    round-tripped through the codec: the result and the steps."""

    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    steps: list[DomainAction] = []
    while True:
        rows = _rows(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        steps.append(row)
        state = result.state
        if left == 0:
            return RuleResult(state=state, events=tuple(events)), tuple(steps)


def _loaded(start: GameState, steps: tuple[DomainAction, ...]) -> GameState:
    """A save writes the steps from its start as JSON (``server.persistence``)
    and a load replays them; an undo replays the steps before the one it
    takes back."""

    saved = json.dumps([serialize_step(step) for step in steps])
    state = start
    for index, value in enumerate(json.loads(saved)):
        state = ENGINE.apply(state, deserialize_step(value, index)).state
    return state


def _top(state: GameState) -> str:
    return state.decision_stack[-1].kind


def _holds(state: GameState) -> int:
    return sum(1 for frame in state.decision_stack if is_unload_hold(frame))


def _snooper_spice(events: tuple[GameEvent, ...]) -> list[int]:
    """Where, among ``events``, the Snooper reward's spice is."""

    return [
        index
        for index, event in enumerate(events)
        if event.kind == "resources_gained"
        and ":snooper" in event.event_id
        and dict(event.payload).get("spice") == 1
    ]


def _closed(state: GameState) -> None:
    """The out-of-turn window and everything the discard opened are gone (the
    hand-built Combat phase then moves on by itself)."""

    assert _holds(state) == 0
    assert not {
        FrameKind.OPTIONAL_DISCARD,
        FrameKind.UNLOAD_ICONS,
        FrameKind.FREIGHTER_MOVE,
    } & {frame.kind for frame in state.decision_stack}


def _after(events: tuple[GameEvent, ...], kind: str) -> None:
    """The spice comes once, after the first ``kind`` event."""

    kinds = [event.kind for event in events]
    (spice,) = _snooper_spice(events)
    assert kind in kinds and kinds.index(kind) < spice


# --- Her own turn: the row -----------------------------------------------------


def _in_turn(card: str) -> tuple[GameState, GameState, tuple[DomainAction, ...]]:
    """Tessia sends Diplomacy to Wealth; its Emperor Influence reaches her
    token, so reward ① waits as a row of her turn. Returns the start, the
    state with the row waiting, and the steps between them."""

    start = _tessia(card)
    state = start
    steps: tuple[DomainAction, ...] = ()
    for action_id, arguments in (
        ("choose_agent_card", {"card_id": DIPLOMACY}),
        ("place_agent", {"space_id": "wealth"}),
        ("resolve_faction_influence", {}),
    ):
        result, taken = _steps_of(state, action_id, **arguments)
        state, steps = result.state, (*steps, *taken)
    assert state.players[0].influence.emperor == 2
    assert {
        dict(row.arguments)["card_id"]
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == SNOOPER_ROW
    } == {card}
    return start, state, steps


def test_in_her_turn_boundless_ambition_holds_the_spice_until_it_acquires() -> None:
    """Boundless Ambition discarded for reward ①: its acquisition opens above
    a hold and the spice comes once, after the card. Saved and loaded inside
    the hold the game is the same, and finishing it pays once; undoing the
    discard leaves no hold, and taking it again opens the same one."""

    start, reached, before = _in_turn(AMBITION)
    opened, discard = _steps_of(reached, SNOOPER_ROW, card_id=AMBITION)
    held = opened.state
    assert _holds(held) == 1
    top = held.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert dict(top.context)[unload.UNLOAD_ACQUIRE_KEY] == AMBITION
    assert AMBITION in held.players[0].discard_pile
    assert held.players[0].resources.spice == 0
    assert not _snooper_spice(opened.events)
    check_observation_privacy(held)
    steps = (*before, *discard)
    loaded = _loaded(start, steps)
    assert canonical_state_hash(loaded) == canonical_state_hash(held)
    undone = _loaded(start, before)
    assert canonical_state_hash(undone) == canonical_state_hash(reached)
    assert _holds(undone) == 0
    again, _ = _steps_of(undone, SNOOPER_ROW, card_id=AMBITION)
    assert canonical_state_hash(again.state) == canonical_state_hash(held)
    acquired, answer = _steps_of(loaded, "acquire_unload_reserve_card", card_id=LIAISON)
    after = acquired.state
    assert after.players[0].resources.spice == 1
    assert any(LIAISON in card for card in after.players[0].discard_pile)
    assert _holds(after) == 0
    _after(acquired.events, "card_acquired")
    assert after.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS
    replayed = _loaded(start, (*steps, *answer))
    assert canonical_state_hash(replayed) == canonical_state_hash(after)


def test_in_her_turn_freighter_fleet_holds_the_spice_until_it_moves() -> None:
    """Freighter Fleet discarded for reward ①: the Freighter's window opens
    above the hold and the spice comes once, after the move."""

    _, reached, _ = _in_turn(FLEET)
    opened, _ = _steps_of(reached, SNOOPER_ROW, card_id=FLEET)
    state = opened.state
    assert state.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    assert _holds(state) == 1
    assert state.players[0].resources.spice == 0
    assert not _snooper_spice(opened.events)
    moved, _ = _steps_of(state, "advance_freighter")
    assert moved.state.players[0].freighter_space == 1
    assert moved.state.players[0].resources.spice == 1
    assert _holds(moved.state) == 0
    _after(moved.events, "freighter_moved")
    assert moved.state.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS


def test_in_her_turn_water_peddler_pays_its_box_inside_the_discard() -> None:
    """Water Peddler's box needs no decision: its water, then the spice, in
    the discard's own step, with no hold."""

    _, reached, _ = _in_turn(PEDDLER)
    paid, _ = _steps_of(reached, SNOOPER_ROW, card_id=PEDDLER)
    owner = paid.state.players[0]
    assert (owner.resources.water, owner.resources.spice) == (1, 1)
    assert _holds(paid.state) == 0
    gains = [
        dict(event.payload) for event in paid.events if event.kind == "resources_gained"
    ]
    assert [(gain.get("water", 0), gain.get("spice", 0)) for gain in gains] == [
        (1, 0),
        (0, 1),
    ]


# --- Reached inside a cost's hold in her turn: a row after the hold -----------


def _drawn(events: tuple[GameEvent, ...]) -> list[GameEvent]:
    """Truthsayer's right side, its draw: the effect resolved."""

    return [event for event in events if event.kind == "agent_card_effect_resolved"]


class _Play:
    """Seat 0's steps from ``start``, with every event since ``events`` was
    last cleared."""

    def __init__(self, start: GameState) -> None:
        self.start = start
        self.state = start
        self.steps: tuple[DomainAction, ...] = ()
        self.events: tuple[GameEvent, ...] = ()

    def clear(self) -> None:
        self.events = ()

    def take(self, action_id: str, **arguments: object) -> GameState:
        result, taken = _steps_of(self.state, action_id, **arguments)
        self.state, self.steps = result.state, (*self.steps, *taken)
        self.events = (*self.events, *result.events)
        return self.state


def _recalled_into_her_token() -> _Play:
    """Truthsayer's "[Discard] -> [draw 1 card]" paid with Freighter Fleet
    holds the draw (rise-of-ix.md 153: "Unload를 끝까지 해결한 뒤 오른쪽으로
    간다"); its Freighter recalled from space 2 owes that space's Influence,
    and raising Fremen to 2 reaches Tessia's first Snooper token
    (rise-of-ix.md 235: "① discard → spice 1") inside the hold."""

    play = _Play(
        _give(
            _start(),
            0,
            (TRUTHSAYER, FLEET, AMBITION),
            influence=Influence(fremen=1),
            resources=NONE,
            freighter_space=2,
        )
    )
    play.take("choose_agent_card", card_id=TRUTHSAYER)
    play.take("place_agent", space_id="wealth")
    play.take("discard_agent_card", card_id=FLEET)
    assert _holds(play.state) == 1
    play.take("recall_freighter")
    play.take("resolve_shipping_reward", effect="influence", faction="fremen")
    state = play.state
    assert state.players[0].influence.fremen == 2
    assert "snooper_token_reached" in [event.kind for event in play.events]
    return play


def _snooper_rows(state: GameState) -> set[str]:
    return {
        str(dict(row.arguments)["card_id"])
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == SNOOPER_ROW
    }


def _row_after_the_hold() -> tuple[_Play, int]:
    """The first reward waits on her turn frame, not in a window: "차례 안의
    효과는 차례의 줄이라는 원칙(OQ-095 (2), 정리-2b)과 같다. 차례 밖(...)은
    완수한 자리의 창 그대로다" (open-questions.md OQ-112 (4)). The recall's
    rewards are the hold's Unload and come first; once the hold closes, the
    draw is paid once and the row is offered. Returns the play there and the
    hand size before the draw."""

    play = _recalled_into_her_token()
    state = play.state
    stack = state.decision_stack
    assert not any(frame.kind is FrameKind.OPTIONAL_DISCARD for frame in stack)
    assert [frame.kind for frame in stack] == [
        FrameKind.AGENT_EFFECTS,
        FrameKind.UNLOAD_ICONS,
        FrameKind.SHIPPING_REWARD_ICONS,
    ]
    assert _holds(state) == 1
    assert turn_rows.SNOOPER_DISCARD in [
        kind for kind, _, _ in turn_rows.pending(stack[0])
    ]
    assert not _snooper_rows(state)
    assert {row.action_id for row in _rows(state)} == {"resolve_shipping_reward"}
    hand = len(state.players[0].hand)
    play.take("resolve_shipping_reward", effect="dividends")
    assert _holds(play.state) == 1 and not _drawn(play.events)
    assert not _snooper_rows(play.state)
    play.take("resolve_shipping_reward", effect="recruit")
    state = play.state
    assert _holds(state) == 0
    assert _top(state) is FrameKind.AGENT_EFFECTS
    assert len(state.players[0].hand) == hand + 1
    assert len(_drawn(play.events)) == 1
    assert _snooper_rows(state) == set(state.players[0].hand)
    assert AMBITION in state.players[0].hand
    assert not _snooper_spice(play.events)
    return play, hand


def test_a_first_reward_reached_inside_her_cost_s_hold_waits_as_a_turn_row() -> None:
    """Taken after the hold, the row with Boundless Ambition holds the spice
    in a hold of its own (not nested: the cost's hold is closed), and the
    spice comes once, after the acquisition. Saved and loaded inside that
    hold the game is the same; undoing the discard gives the row back, and
    taking it again opens the same hold."""

    play, hand = _row_after_the_hold()
    offered = play.state
    before = play.steps
    play.clear()
    play.take(SNOOPER_ROW, card_id=AMBITION)
    held = play.state
    assert _holds(held) == 1
    assert [frame.kind for frame in held.decision_stack] == [
        FrameKind.AGENT_EFFECTS,
        FrameKind.UNLOAD_ICONS,
        FrameKind.UNLOAD_ICONS,
    ]
    assert dict(held.decision_stack[-1].context)[unload.UNLOAD_ACQUIRE_KEY] == (
        AMBITION
    )
    assert held.players[0].resources.spice == 0
    assert not _snooper_spice(play.events)
    check_observation_privacy(held)
    loaded = _loaded(play.start, play.steps)
    assert canonical_state_hash(loaded) == canonical_state_hash(held)
    undone = _loaded(play.start, before)
    assert canonical_state_hash(undone) == canonical_state_hash(offered)
    assert _holds(undone) == 0 and AMBITION in _snooper_rows(undone)
    again, _ = _steps_of(undone, SNOOPER_ROW, card_id=AMBITION)
    assert canonical_state_hash(again.state) == canonical_state_hash(held)
    play.state = loaded
    play.take("acquire_unload_reserve_card", card_id=LIAISON)
    after = play.state
    assert _holds(after) == 0
    assert _top(after) is FrameKind.AGENT_EFFECTS
    assert after.players[0].resources.spice == 1
    _after(play.events, "card_acquired")
    assert not _snooper_rows(after)
    assert len(after.players[0].hand) == hand
    replayed = _loaded(play.start, play.steps)
    assert canonical_state_hash(replayed) == canonical_state_hash(after)


def test_a_first_reward_reached_inside_her_cost_s_hold_lapses_unused() -> None:
    """Not taken, the row holds no turn end back and the turn-end press
    lapses it (OQ-095 (2)): no spice, the card stays in her hand."""

    play, _ = _row_after_the_hold()
    play.take("resolve_board_effect", effect="resources")
    play.take("resolve_faction_influence")
    assert _snooper_rows(play.state)
    play.clear()
    play.take("finish_agent_turn")
    kinds = [event.kind for event in play.events]
    assert kinds.count("snooper_discard_lapsed") == 1
    assert not _snooper_spice(play.events)
    assert play.state.players[0].resources.spice == 0
    assert AMBITION in play.state.players[0].hand
    assert not _snooper_rows(play.state)


def test_two_holds_stacked_by_construction_pay_each_side_once_in_order() -> None:
    """No legal play found nests a Snooper hold today: in her own turn the
    reward waits as a row (above); outside it the costs paid at once are her
    turn's (Agent boxes, Tech flips, Ixian Probe's Plot) or the Snooper
    window itself, whose recall can only reach a later token. Stacked by
    hand inside the
    cost's hold -- Boundless Ambition discarded for the Snooper payer above
    the recall's rewards -- the inner hold closes first and pays its spice
    once, after the acquisition; the outer draw is neither paid early nor
    lost: once, after the recall's last reward. A save and load with both
    holds open is the same game."""

    play = _Play(
        _give(
            _start(),
            0,
            (TRUTHSAYER, FLEET, AMBITION),
            influence=Influence(),
            resources=NONE,
            freighter_space=2,
        )
    )
    play.take("choose_agent_card", card_id=TRUTHSAYER)
    play.take("place_agent", space_id="wealth")
    play.take("discard_agent_card", card_id=FLEET)
    play.take("recall_freighter")
    play.take("resolve_shipping_reward", effect="influence", faction="fremen")
    source = "test:snooper"
    discarded = discard_personal_card_from_hand(
        play.state, 0, AMBITION, source=source, unload_at_once=True
    )
    assert unload.unload_holds(discarded.events)
    held = unload.push_unload_hold(
        discarded.state,
        0,
        source=source,
        payer="snooper_discard",
        values={"source": "test"},
    )
    nested = unload.settle_unloads(
        RuleResult(state=held, events=discarded.events)
    ).state
    assert [frame.kind for frame in nested.decision_stack] == [
        FrameKind.AGENT_EFFECTS,
        FrameKind.UNLOAD_ICONS,
        FrameKind.SHIPPING_REWARD_ICONS,
        FrameKind.UNLOAD_ICONS,
        FrameKind.UNLOAD_ICONS,
    ]
    assert [is_unload_hold(frame) for frame in nested.decision_stack] == [
        False,
        True,
        False,
        True,
        False,
    ]
    hand = len(nested.players[0].hand)
    check_observation_privacy(nested)
    play = _Play(nested)
    play.take("acquire_unload_reserve_card", card_id=LIAISON)
    assert _holds(play.state) == 1
    assert _top(play.state) is FrameKind.SHIPPING_REWARD_ICONS
    assert play.state.players[0].resources.spice == 1
    _after(play.events, "card_acquired")
    loaded = _loaded(nested, play.steps)
    assert canonical_state_hash(loaded) == canonical_state_hash(play.state)
    play.take("resolve_shipping_reward", effect="spice")
    assert _holds(play.state) == 1
    assert len(play.state.players[0].hand) == hand and not _drawn(play.events)
    play.take("resolve_shipping_reward", effect="recruit")
    state = play.state
    assert _holds(state) == 0
    assert _top(state) is FrameKind.AGENT_EFFECTS
    assert len(state.players[0].hand) == hand + 1
    assert state.players[0].resources.spice == 3
    kinds = [event.kind for event in play.events]
    (drawn,) = _drawn(play.events)
    assert kinds.index("shipping_troops_recruited") < play.events.index(drawn)
    assert len(_snooper_spice(play.events)) == 1


# --- Outside her turn: the OPTIONAL_DISCARD window -----------------------------


def _outside(card: str) -> GameState:
    """Seat 0's token ① reached in the Combat phase (no turn [Main p. 8]):
    the ``OPTIONAL_DISCARD`` window, a hand card or the refusal."""

    combat = replace(_tessia(card), phase=GamePhase.COMBAT, decision_stack=())
    gained = gain_faction_influence(
        combat, 0, Faction.EMPEROR, 1, event_prefix="test:emperor"
    )
    window = settle_snooper_discards(gained).state
    assert window.decision_stack[-1].kind is FrameKind.OPTIONAL_DISCARD
    return window


def test_outside_her_turn_boundless_ambition_holds_the_spice() -> None:
    """The same in the out-of-turn window: the window gives way to the hold
    under the acquisition, and the spice follows the card once. Saved and
    loaded inside the hold the game is the same; undoing the discard
    reopens the window."""

    start = _outside(AMBITION)
    opened, discard = _steps_of(start, SNOOPER_ROW, card_id=AMBITION)
    held = opened.state
    assert _holds(held) == 1
    assert dict(held.decision_stack[-1].context)[unload.UNLOAD_ACQUIRE_KEY] == AMBITION
    assert not any(
        frame.kind is FrameKind.OPTIONAL_DISCARD for frame in held.decision_stack
    )
    assert held.players[0].resources.spice == 0
    check_observation_privacy(held)
    loaded = _loaded(start, discard)
    assert canonical_state_hash(loaded) == canonical_state_hash(held)
    undone = _loaded(start, ())
    assert undone.decision_stack[-1].kind is FrameKind.OPTIONAL_DISCARD
    again, _ = _steps_of(undone, SNOOPER_ROW, card_id=AMBITION)
    assert canonical_state_hash(again.state) == canonical_state_hash(held)
    acquired, answer = _steps_of(loaded, "acquire_unload_reserve_card", card_id=LIAISON)
    assert acquired.state.players[0].resources.spice == 1
    _after(acquired.events, "card_acquired")
    _closed(acquired.state)
    replayed = _loaded(start, (*discard, *answer))
    assert canonical_state_hash(replayed) == canonical_state_hash(acquired.state)


def test_outside_her_turn_freighter_fleet_holds_the_spice() -> None:
    """Declining the Freighter's "may" still answers it: the spice follows
    once."""

    opened, _ = _steps_of(_outside(FLEET), SNOOPER_ROW, card_id=FLEET)
    assert opened.state.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    assert _holds(opened.state) == 1
    assert opened.state.players[0].resources.spice == 0
    declined, _ = _steps_of(opened.state, "decline_freighter")
    assert declined.state.players[0].resources.spice == 1
    _after(declined.events, "freighter_declined")
    _closed(declined.state)


def test_outside_her_turn_water_peddler_pays_its_box_inside_the_discard() -> None:
    paid, _ = _steps_of(_outside(PEDDLER), SNOOPER_ROW, card_id=PEDDLER)
    owner = paid.state.players[0]
    assert (owner.resources.water, owner.resources.spice) == (1, 1)
    _closed(paid.state)


def test_above_another_seat_s_turn_the_hold_is_hers_and_gives_its_frame_back() -> None:
    """Tessia at seat 1 reaches her first Snooper token (rise-of-ix.md 235:
    "그 token에 도달할 때마다 ... ① discard → spice 1") inside seat 0's turn,
    whose Agent effects wait below: a seat's decision arising inside another
    seat's turn (imperium-base.md 359: "상대 좌석의 결정이 내 turn 안에
    생긴다"), built here by hand. While her hold is open the decision is hers
    and only her Unload rows are offered; when it closes, the frame below is
    seat 0's own, unchanged, and the spice came once."""

    state = _start(TESSIA_SECOND)
    assert state.players[1].leader_id == "tessia_vernius"
    state = _give(state, 0, (DIPLOMACY,))
    state = _give(state, 1, (AMBITION,), influence=Influence(emperor=1), resources=NONE)
    state = _steps_of(state, "choose_agent_card", card_id=DIPLOMACY)[0].state
    state = _steps_of(state, "place_agent", space_id="wealth")[0].state
    below = state.decision_stack
    assert below[-1].kind is FrameKind.AGENT_EFFECTS
    assert isinstance(below[-1].decision, PlayerDecision)
    assert below[-1].decision.owner == 0
    offered = _rows(state, 0)
    assert offered
    gained = gain_faction_influence(
        state, 1, Faction.EMPEROR, 1, event_prefix="test:emperor"
    )
    window = settle_snooper_discards(gained).state
    assert window.decision_stack[:-1] == below
    assert window.decision_stack[-1].kind is FrameKind.OPTIONAL_DISCARD
    opened, _ = _seat_steps(window, 1, SNOOPER_ROW, card_id=AMBITION)
    held = opened.state
    assert _holds(held) == 1
    assert held.decision_stack[: len(below)] == below
    decision = ENGINE.current_decision(held)
    assert isinstance(decision, PlayerDecision) and decision.owner == 1
    rows = _rows(held, 1)
    assert rows
    assert {row.action_id for row in rows} <= {
        "acquire_unload_imperium_card",
        "acquire_unload_reserve_card",
    }
    for seat in (0, 2, 3):
        assert not _rows(held, seat)
    assert held.players[1].resources.spice == 0
    check_observation_privacy(held)
    acquired, _ = _seat_steps(held, 1, "acquire_unload_reserve_card", card_id=LIAISON)
    after = acquired.state
    assert after.decision_stack == below
    assert after.players[1].resources.spice == 1
    _after(acquired.events, "card_acquired")
    assert _rows(after, 0) == offered


# --- The two measurement games -------------------------------------------------

_MEASURED = RulesetConfig(
    base_game=BaseGame.IMPERIUM, promo_cards=True, leader_draft=True, rise_of_ix=True
)


@pytest.mark.parametrize(
    ("seed", "flip", "held"),
    [
        (80205, 0, (AMBITION, "acquisition")),
        (80212, 1, ("imperium:ix_guild_compact:0", "negotiator,negotiator")),
    ],
)
def test_the_measurement_games_that_crashed_play_to_the_end(
    seed: int, flip: int, held: tuple[str, str]
) -> None:
    """P6's measurement (the original game with Rise of Ix and its promo,
    Leader draft, the app AI at level 2 against the heuristic) crashed in
    these two games when Tessia's reward ① discarded an Unload card holding
    a decision. Replayed whole, each passes that discard through the hold
    and finishes."""

    lineup = ("A", "B", "A", "B") if flip == 0 else ("B", "A", "B", "A")
    agents = tuple(
        AppAIAgent(seed=900_000 + seed * 10 + seat, level=2)
        if kind == "A"
        else HeuristicAgent(seed=900_000 + seed * 10 + seat)
        for seat, kind in enumerate(lineup)
    )
    engine = UprisingRulesEngine()
    seen: list[tuple[str, str]] = []
    apply = engine.apply

    def recording(
        state: GameState, action: DomainAction, **kwargs: object
    ) -> Transition:
        result = apply(state, action, **kwargs)  # type: ignore[arg-type]
        for event in result.events:
            payload = dict(event.payload)
            if (
                event.kind == unload.UNLOADED_EVENT
                and "held" in payload
                and ":snooper" in event.event_id
            ):
                seen.append((str(payload["card_id"]), str(payload["held"])))
        return result

    engine.apply = recording  # type: ignore[method-assign,assignment]
    logging.disable(logging.CRITICAL)
    try:
        played = run_policy_game(engine, _MEASURED, seed, agents)
    finally:
        logging.disable(logging.NOTSET)
    assert played.state.phase is GamePhase.FINISHED
    assert seen == [held]
