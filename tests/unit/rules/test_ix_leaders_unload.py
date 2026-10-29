"""Rise of Ix's Leaders with Unload (stage P4e beside P4d's Unload).

docs/rules/rise-of-ix.md 7: "Unload 표시가 있는 Reveal box는 ... 그 카드를 **discard할
때**와 **trash할 때** 얻는다"; 9.3: "Ilesa가 따로 둔 카드는 trash·discard 대상이
아니다(BGG Forum)"; 10: Yuna's "자기 turn에 Solari를 얻을 때마다 1 더" and Armand's
Coordination ("in play 카드 하나를 trash할 수 있다"). CHOAM Delegate's Unload box
is its 3 Solari (Steam app screen pieces, ``rules.unload``). Every offered row
round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.agents.random_agent import RandomAgent
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
OTHERS = ("glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")
JAMIS = "imperium:jamis:0"
DELEGATE = "imperium:choam_delegate:0"
UNLOAD_ROW = "resolve_unload_icon"


@cache
def _codec() -> ActionCodec:
    return ActionCodec(IX)


def _start(leader: str, seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    engine = UprisingRulesEngine(leader_ids=(leader, *OTHERS))
    state = engine.reset(IX, seed)
    chance = ChanceResolver(seed=seed)
    while state.phase is GamePhase.SETUP or isinstance(
        engine.current_decision(state), ChanceDecision
    ):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
        else:
            assert isinstance(decision, PlayerDecision)
            state = engine.apply(
                state, engine.legal_actions(state, decision.owner)[0]
            ).state
    return engine, state


def _rows(engine: UprisingRulesEngine, state: GameState) -> tuple[DomainAction, ...]:
    rows = engine.legal_actions(state, 0)
    for row in rows:
        assert _codec().decode(_codec().encode(row), 0) == row
    return rows


def _do(
    engine: UprisingRulesEngine, state: GameState, action_id: str, **arguments: object
) -> RuleResult:
    whole = next(
        row
        for row in engine.whole_actions(state, 0)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    while True:
        rows = _rows(engine, state)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = engine.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            return RuleResult(state=state, events=tuple(events))


def _give(state: GameState, **zones: object) -> GameState:
    """Seat 0's zones holding the named cards, taken out of every other
    zone, the Imperium deck and the Row first."""

    named = {
        card for cards in zones.values() if isinstance(cards, tuple) for card in cards
    }
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
            discard_pile=tuple(c for c in player.discard_pile if c not in named),
            in_play=tuple(c for c in player.in_play if c not in named),
        )
        if player.player_id == 0:
            cleaned = replace(cleaned, **zones)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def test_yunas_smuggling_operation_adds_one_to_an_unload_solari_gain() -> None:
    """CHOAM Delegate trashed in her own turn (Jamis: "Trash a card") gains
    its Unload box's 3 Solari as a row of the turn (rise-of-ix.md 7); taken in
    her turn it is a Solari gain like any other, one more (rise-of-ix.md 10)."""

    engine, state = _start("princess_yuna_moritani")
    state = _give(state, hand=(JAMIS, DELEGATE))
    state = _do(engine, state, "choose_agent_card", card_id=JAMIS).state
    state = _do(engine, state, "place_agent", space_id="stillsuits").state
    state = _do(engine, state, "trash_agent_card", card_id=DELEGATE).state
    solari = state.players[0].resources.solari
    taken = _do(engine, state, UNLOAD_ROW, card_id=DELEGATE, effect="solari")
    assert taken.state.players[0].resources.solari == solari + 3 + 1


def test_armands_coordination_trash_unloads_the_card() -> None:
    """Coordination trashes one of his cards in play in his Reveal turn
    (rise-of-ix.md 10); a trashed Unload card gains its box again, even
    revealed this turn (OQ-120), as a row of his turn."""

    engine, state = _start("archduke_armand_ecaz")
    owner = state.players[0]
    state = _give(
        state,
        hand=owner.hand[1:],
        in_play=(owner.hand[0], DELEGATE),
        agent_locations=("tech_negotiation", "arrakeen"),
        agents_available=0,
    )
    revealed = _do(engine, state, "reveal_turn").state
    trashed = _do(engine, revealed, "trash_leader_reveal_card", card_id=DELEGATE)
    assert DELEGATE in trashed.state.players[0].trashed
    assert "card_unloaded" in [event.kind for event in trashed.events]
    solari = trashed.state.players[0].resources.solari
    taken = _do(engine, trashed.state, UNLOAD_ROW, card_id=DELEGATE, effect="solari")
    assert taken.state.players[0].resources.solari == solari + 3


def test_no_row_ever_names_ilesas_set_aside_card() -> None:
    """ "Ilesa가 따로 둔 카드는 trash·discard 대상이 아니다" (rise-of-ix.md 9.3): it
    is in no hand, discard pile or play area. Through random games with her
    seated, no offered row of any seat names it while it is aside."""

    seen = 0
    for seed in (3, 11):
        engine = UprisingRulesEngine(leader_ids=("ilesa_ecaz", *OTHERS))
        state = engine.reset(IX, seed)
        agents = [RandomAgent(seed=seed * 10 + seat) for seat in range(4)]
        chance = ChanceResolver(seed=seed)
        for _ in range(900):
            if state.phase is GamePhase.FINISHED:
                break
            decision = engine.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = engine.apply(state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            rows = engine.legal_actions(state, decision.owner)
            aside = state.players[0].set_aside_card_id
            if aside:
                seen += 1
                for row in (*rows, *engine.whole_actions(state, decision.owner)):
                    assert aside not in {str(value) for _, value in row.arguments}
            pick = agents[decision.owner].choose_action(
                engine.observe(state, decision.owner), rows
            )
            state = engine.apply(state, pick).state
    assert seen > 50
