"""Dissecting Kit's graft trash holds its specimen while the trashed card's
Unload is decided (Immortality with Rise of Ix).

Rule: docs/rules/rise-of-ix.md 7, the designer ruling "비용 → 효과 줄의
왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤 오른쪽으로 간다", and
"trash되는 카드의 Unload는 trash되는 중에 일어난다(OQ-022의 예외가 아니다)";
an Unload box is gained "그 카드를 discard할 때와 trash할 때" `[Rise of Ix
p. 7]`. Dissecting Kit's box is "Trash the other grafted card -> a
specimen" (docs/rules/immortality.md, slice 5b-2). Freighter Fleet's Unload
box is the Freighter's move, "you may move your Freighter in one of two
ways" `[Rise of Ix p. 5]`, a decision of its owner: the trash is paid, the
Freighter is asked under a hold (``rules.unload``'s payer
``agent_box_graft_trash``), and the specimen follows the answer.

Coverage gap 2026-11-12: real games (the Immortality + Rise of Ix soaks)
reached ``agent_effects._pay_held_graft_trash`` and the hold branch of
``_apply_graft_trash``; no test did.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    PlayerDecision,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.frames import is_unload_hold

CONFIG = RulesetConfig(immortality=True, rise_of_ix=True, first_player_seat_zero=True)
ENGINE = UprisingRulesEngine()
DISSECTING = "imperium:dissecting_kit:0"
FLEET = "imperium:freighter_fleet:0"
PEDDLER = "imperium:water_peddler:0"


def _start(seed: int = 3) -> GameState:
    state = ENGINE.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _hand(state: GameState, cards: tuple[str, ...]) -> GameState:
    """Seat 0 holds ``cards`` in place of its first hand cards; the cards are
    taken out of every other zone they were in."""

    named = set(cards)
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
        )
        if player.player_id == 0:
            cleaned = replace(cleaned, hand=(*cards, *cleaned.hand[len(cards) :]))
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _grafted(partner: str) -> GameState:
    """Seat 0's Dissecting Kit grafted with ``partner`` on Arrakeen, the
    space's own effects settled."""

    state = _hand(_start(), (DISSECTING, partner))
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == DISSECTING
        and dict(action.arguments)["space_id"] == "arrakeen"
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = apply_placement(ENGINE, state, placement).state
    choice = DomainAction("choose_graft_partner", 0, arguments=(("card_id", partner),))
    state = apply_whole(ENGINE, state, choice).state
    while True:
        legal = ENGINE.whole_actions(state, 0)
        rows = [
            action
            for action in legal
            if action.action_id in ("resolve_board_effect", "resolve_faction_influence")
        ]
        if not rows:
            return state
        state = apply_whole(ENGINE, state, rows[0], legal_actions=legal).state


def _trash_partner(state: GameState) -> GameState:
    row = DomainAction("trash_grafted_card_for_specimen", 0)
    assert row in ENGINE.whole_actions(state, 0)
    return apply_whole(ENGINE, state, row).state


@pytest.mark.parametrize("answer", ["advance_freighter", "decline_freighter"])
def test_the_specimen_waits_for_the_trashed_card_s_freighter(answer: str) -> None:
    """The trash is paid and Freighter Fleet's Unload asks the Freighter
    under a hold; no specimen yet. Either answer -- moving the Freighter or
    not ("you may") -- closes the hold and pays the specimen once."""

    state = _grafted(FLEET)
    before = state.players[0]
    trashed = _trash_partner(state)
    owner = trashed.players[0]
    assert FLEET in owner.trashed
    assert FLEET not in owner.in_play
    assert owner.specimens == before.specimens
    assert [is_unload_hold(frame) for frame in trashed.decision_stack].count(True) == 1
    decision = ENGINE.current_decision(trashed)
    assert isinstance(decision, PlayerDecision) and decision.owner == 0
    assert {row.action_id for row in ENGINE.legal_actions(trashed, 0)} == {
        "advance_freighter",
        "decline_freighter",
    }

    answered = ENGINE.apply(trashed, DomainAction(answer, 0))
    owner = answered.state.players[0]
    assert owner.specimens == before.specimens + 1
    assert not any(is_unload_hold(frame) for frame in answered.state.decision_stack)
    assert [event.kind for event in answered.events].count("specimens_generated") == 1
    assert ("freighter_moved" in {event.kind for event in answered.events}) is (
        answer == "advance_freighter"
    )
    # Back in the Agent turn, with the turn end offered again.
    assert DomainAction("finish_agent_turn", 0) in ENGINE.legal_actions(
        answered.state, 0
    )


def test_a_partner_whose_unload_asks_nothing_pays_inside_the_trash() -> None:
    """Water Peddler's Unload box is "[1 water]" with no decision: it is paid
    inside the trash and the specimen follows at once, with no hold."""

    state = _grafted(PEDDLER)
    before = state.players[0]
    trashed = _trash_partner(state)
    owner = trashed.players[0]
    assert PEDDLER in owner.trashed
    assert owner.resources.water == before.resources.water + 1
    assert owner.specimens == before.specimens + 1
    assert not any(is_unload_hold(frame) for frame in trashed.decision_stack)
