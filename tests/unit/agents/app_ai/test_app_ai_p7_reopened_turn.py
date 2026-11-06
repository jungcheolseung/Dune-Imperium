"""The app AI in a turn the turn-end press reopened (OQ-160, the P7g app
comparison's A3): the press trashes the card Usurp borrowed from the
Imperium Row, and its Unload's optional effect reopens the turn.

The app runs Usurp's trash inside the turn (``UsurpTrashAbility``,
``AlwaysRunImmediately``), so the Unload's ``FreighterCustomAbility`` or
Negotiators come before the turn's end there as well; the AI answers the
reopened rows with the same classes."""

from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.core import ChanceDecision, ChanceResolver, GamePhase
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements

ENGINE = UprisingRulesEngine(
    leader_ids=(
        "glossu_rabban",
        "count_ilban_richese",
        "earl_memnon_thorvald",
        "countess_ariana_thorvald",
    )
)
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM,
    first_player_seat_zero=True,
    immortality=True,
    rise_of_ix=True,
)
USURP = "tleilaxu:usurp:0"
FREIGHTER_FLEET = "imperium:freighter_fleet:0"
IX_GUILD_COMPACT = "imperium:ix_guild_compact:0"
_SKIPS = ("finish_agent_turn", "use_family_atomics", "return_specimen")


def _wholes(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.whole_actions(state, 0)


def _reopened(partner: str) -> GameState:
    """Seat 0 Usurps ``partner`` from the Row (original + Ix + Immortality),
    takes every other effect of its turn and presses the turn end."""

    state = ENGINE.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    others = [c for c in (*state.imperium_row, *state.imperium_deck) if c != partner]
    owner = state.players[0]
    players = list(state.players)
    players[0] = replace(owner, hand=(*owner.hand, USURP))
    state = replace(
        state,
        players=tuple(players),
        imperium_row=(partner, *others[:4]),
        imperium_deck=tuple(others[4:]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != USURP),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != USURP),
    )
    for placement in executable_placements(state, 0):
        if dict(placement.arguments)["card_id"] != USURP:
            continue
        sent = apply_placement(ENGINE, state, placement).state
        graft = next(
            (
                a
                for a in _wholes(sent)
                if a.action_id == "choose_graft_partner"
                and dict(a.arguments)["card_id"] == partner
            ),
            None,
        )
        if graft is not None:
            state = apply_whole(ENGINE, sent, graft).state
            break
    else:
        raise AssertionError(f"no space takes Usurp with {partner}")
    while not any(a.action_id == "finish_agent_turn" for a in _wholes(state)):
        step = next(a for a in _wholes(state) if a.action_id not in _SKIPS)
        state = apply_whole(ENGINE, state, step).state
    press = next(a for a in _wholes(state) if a.action_id == "finish_agent_turn")
    pressed = apply_whole(ENGINE, state, press)
    assert "agent_turn_reopened" in [event.kind for event in pressed.events]
    return pressed.state


@pytest.mark.parametrize(
    ("partner", "effect"),
    [(FREIGHTER_FLEET, "freighter"), (IX_GUILD_COMPACT, "negotiator")],
)
def test_the_reopened_turn_takes_the_unload_by_its_app_class(
    partner: str, effect: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Unload box is a triggered ability with no AI hook, taken first;
    its effect is then answered by the app class (the Freighter by
    ``FreighterCustomAbility``'s ``FreighterAbility::Evaluate``,
    Ix-Guild Compact's Negotiators placed as the app places them). No
    decision of the reopened turn falls to ``DefaultRandomChoice``."""

    def no_fallback(self: AppAIAgent, key: str, legal: object) -> DomainAction:
        raise AssertionError(f"fallback {key}")

    monkeypatch.setattr(AppAIAgent, "_random_answer", no_fallback)
    state = _reopened(partner)
    ai = AppAIAgent(seed=7, level=2)
    legal = ENGINE.legal_actions(state, 0)
    action = ai.choose_action_with_state(state, ENGINE.observe(state, 0), legal)
    assert action.action_id == "resolve_unload_icon"
    assert dict(action.arguments) == {"card_id": partner, "effect": effect}
    for _ in range(20):  # the rest of the reopened turn, to its second press
        state = ENGINE.apply(state, action, legal_actions=legal).state
        if state.decision_stack[-1].decision.owner != 0:  # type: ignore[union-attr]
            break
        legal = ENGINE.legal_actions(state, 0)
        action = ai.choose_action_with_state(state, ENGINE.observe(state, 0), legal)
    else:
        raise AssertionError("the reopened turn did not end")
