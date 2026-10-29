"""Ix Discard costs reuse the hand-card cost and public discard transition.

Card values: Steam attribute table, screen pieces and English log strings.
Rules: docs/rules/rise-of-ix.md 7 [Rise of Ix p. 7] [FAQ p. 2], and its
OQ-071 application: costs need a live reward, including a cost-fed draw.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import observe_state
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
TRUTHSAYER = "imperium:truthsayer:0"
PROBE = "intrigue:ixian_probe:0"
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
CODEC = ActionCodec(IX)


def _rows(state: GameState) -> tuple[DomainAction, ...]:
    rows = ENGINE.legal_actions(state, 0)
    for row in rows:
        assert CODEC.decode(CODEC.encode(row), 0) == row
    return rows


def _seat(state: GameState, **changes: object) -> GameState:
    owner = replace(state.players[0], **changes)  # type: ignore[arg-type]
    return replace(state, players=(owner, *state.players[1:]))


def _start() -> GameState:
    state = ENGINE.reset(IX, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    _rows(state)
    return state


def _do(state: GameState, action_id: str, **arguments: object) -> RuleResult:
    whole = next(
        row
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    while True:
        rows = _rows(state)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            if not isinstance(ENGINE.current_decision(state), ChanceDecision):
                _rows(state)
            return RuleResult(state=state, events=tuple(events))


def _truthsayer(state: GameState) -> GameState:
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    return _do(state, "place_agent", space_id="wealth").state


def _probe(state: GameState) -> GameState:
    return _do(state, "play_intrigue", card_id=PROBE, option=0).state


def test_card_data_matches_the_app_and_only_joins_the_ix_decks() -> None:
    """Truthsayer: "Discard -> draw a card"."""
    card = IMPERIUM_CARDS_BY_ID["truthsayer"]
    assert card.play_data_complete
    assert (card.copies, card.acquisition_cost) == (2, 3)
    assert card.factions == (Faction.EMPEROR, Faction.BENE_GESSERIT)
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.LANDSRAAD,
    )
    assert (card.reveal_persuasion, card.reveal_strength) == (1, 1)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        content = content_for(config)
        assert (TRUTHSAYER in content.imperium_deck_instance_ids) == config.rise_of_ix


def test_truthsayer_discards_the_payers_choice_publicly_before_drawing() -> None:
    """ "손의 카드 하나(Intrigue 아님)를 discard pile로" [Rise of Ix p. 7];
    Truthsayer: "draw a card"."""
    state = _start()
    paid, kept = state.players[0].hand[:2]
    top = state.players[0].deck[0]
    state = _seat(state, hand=(TRUTHSAYER, paid, kept), intrigue_cards=(PROBE,))
    state = _truthsayer(state)
    result = _do(state, "discard_agent_card", card_id=paid)
    owner = result.state.players[0]
    assert owner.hand == (kept, top)
    assert paid in owner.discard_pile
    assert owner.intrigue_cards == (PROBE,)
    assert TRUTHSAYER in owner.in_play
    assert paid in observe_state(result.state, 1).players[0].discard_pile
    event = next(event for event in result.events if event.kind == "card_discarded")
    assert event.visible_to is None and dict(event.payload)["card_id"] == paid


def test_truthsayer_does_not_offer_payment_with_no_hand_card() -> None:
    """ "내지 않으면 효과도 없다" [Rise of Ix p. 7].

    The played Truthsayer cannot pay itself.
    """
    state = _seat(_start(), hand=(TRUTHSAYER,), intrigue_cards=(PROBE,))
    state = _truthsayer(state)
    assert not any(
        row.action_id == "discard_agent_card" for row in ENGINE.whole_actions(state, 0)
    )
    assert state.players[0].hand == ()


def test_truthsayer_cost_can_be_left_unpaid() -> None:
    """ "손의 카드 하나(Intrigue 아님) -OR- 내지 않음" [Rise of Ix p. 7]."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _truthsayer(_seat(state, hand=(TRUTHSAYER, kept)))
    deck = state.players[0].deck
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    result = _do(state, "finish_agent_turn")
    assert result.state.players[0].hand == (kept,)
    assert result.state.players[0].deck == deck
    assert not any(event.kind == "cards_drawn" for event in result.events)


def test_truthsayer_reveals_for_one_persuasion_and_one_sword() -> None:
    """Truthsayer Reveal: "Persuasion 1 + 1 sword" (Steam screen pieces)."""
    state = _seat(_start(), hand=(TRUTHSAYER,))
    state = _do(state, "reveal_turn").state
    assert state.players[0].combat_strength == 0  # No Conflict troop [DI p. 11].
    context = dict(state.decision_stack[-1].context)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == 1
    assert state.players[0].hand == ()
