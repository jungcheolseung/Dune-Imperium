"""app_ai counts Ilesa Ecaz's set-aside card as the table must count it
(hidden-information sweep 2026-11-11, finding 2; user decision 2026-11-11
"2번 앱식 AI 수정을 1번 누출 수정과 함께 넣자").

docs/rules/rise-of-ix.md 13 ("숨은 정보"): "Ilesa Ecaz의 따로 둔 카드 | Ilesa
좌석 | 둘째 turn에 공개" -- until her second turn only her seat knows which
card she set aside. Every seat does know the seat's deck composition, the set
-aside card in it (``PublicPlayerView.deck_pool``, OQ-010 ruling 6). The app's
opponent-strength estimate reads an opponent's ``Hand ∪ Deck``
(``AppContext.hidden_pool``); without the set-aside card that union, set
against the public composition, names the card. It is now the public
composition plus the hand cards everyone can identify.
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.context import AppContext, card_id
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine

ILESA = "ilesa_ecaz"
SEAT = 0
CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
LEADERS = (ILESA, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


def _public_pool(state: GameState, observer: int) -> Counter[str]:
    """Ilesa's seat as ``observer`` sees it: the public deck composition and
    the hand cards everyone can identify."""

    seen = UprisingRulesEngine().observe(state, observer).players[SEAT]
    return Counter(seen.deck_pool) + Counter(card_id(c) for c in seen.hand_public)


def _twin(state: GameState) -> GameState | None:
    """``state`` with Ilesa's set-aside card swapped for a deck card of
    another card id: her deck composition, sizes and every other seat's view
    stay the same. None when no such deck card exists."""

    ilesa = state.players[SEAT]
    aside = ilesa.set_aside_card_id
    if not aside:
        return None
    other = next(
        (i for i, card in enumerate(ilesa.deck) if card_id(card) != card_id(aside)),
        None,
    )
    if other is None:
        return None
    deck = list(ilesa.deck)
    deck[other], swapped = aside, deck[other]
    players = list(state.players)
    players[SEAT] = replace(ilesa, deck=tuple(deck), set_aside_card_id=swapped)
    return replace(state, players=tuple(players))


@pytest.mark.parametrize("game_seed", [1, 2, 3])
def test_app_ai_reads_ilesa_s_pool_as_the_table_does(game_seed: int) -> None:
    """In app_ai games with Ilesa at seat 0, at every decision of another
    seat (before her set-aside, while her card is set aside, after it
    returns) that seat's ``hidden_pool`` of her is her public composition;
    while the card is set aside, on a twin whose set-aside card is another of
    her deck's cards, the pool and the seat's choice are the same."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    agents = [AppAIAgent(seed=300 + seat, level=seat % 3) for seat in range(4)]
    state = engine.reset(CONFIG, game_seed)
    chance = ChanceResolver(seed=game_seed)
    pools = twins = 0
    for _ in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        actions = engine.legal_actions(state, seat)
        view = engine.observe(state, seat)
        if seat != SEAT:
            pool = AppContext(state, seat, view).hidden_pool(SEAT)
            assert pool == _public_pool(state, seat)
        if seat != SEAT and state.players[SEAT].set_aside_card_id:
            pools += 1
            twin = _twin(state)
            if twin is not None and len(actions) > 1:
                assert engine.observe(twin, seat) == view
                assert AppContext(twin, seat, view).hidden_pool(SEAT) == pool
                on_twin = copy.deepcopy(agents[seat]).choose_action_with_state(
                    twin, view, actions
                )
                on_state = copy.deepcopy(agents[seat]).choose_action_with_state(
                    state, view, actions
                )
                assert on_twin == on_state
                twins += 1
        action = agents[seat].choose_action_with_state(state, view, actions)
        state = engine.apply(state, action, legal_actions=actions).state
    assert state.phase is GamePhase.FINISHED
    assert pools > 20 and twins > 5, (pools, twins)
    for agent in agents:
        assert not agent.fallbacks
