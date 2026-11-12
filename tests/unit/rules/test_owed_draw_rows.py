"""An immediate triggered draw is offered by its step on every frame (OQ-106).

Stage B's invariant (docs/stage-b-plan.md): no frame offers a whole action
of ``STEP_SPECS`` as it is, so the codec keeps only its step rows. Rise of
Ix's Shipping rewards window is not a step frame, nor is the Unload hold
under it. Their Influence reward can reach a Bene Gesserit bonus inside the
owner's turn (Uprising's at 4, the original game's at 2), and the immediate
Intrigue draw then waited there as the whole ``draw_owed_intrigue``, which no
catalog encodes. The original-board re-adaptation run (2026-11-07) stopped on
it. The first tests build the window directly; the last replays an app AI
game of the original board that reaches it.
"""

from dataclasses import replace

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.effect_steps import picked_rows
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.owed_draws import immediate_owed_draw_actions
from dune_imperium.rules.shipping_track import recall_freighter
from dune_imperium.rules.unload import push_unload_hold
from dune_imperium.simulation.runner import run_policy_game

ENGINE = UprisingRulesEngine()
UPRISING_IX = RulesetConfig(rise_of_ix=True)
BENE_GESSERIT_DRAW_ROW = DomainAction(
    "draw",
    0,
    (
        ("icon", "intrigue"),
        ("printed", "bene_gesserit"),
        ("source", "influence_track"),
    ),
)


def _recalled_from_space_two() -> GameState:
    """Seed 0 of Uprising + Rise of Ix: seat 0's first turn, its Freighter
    recalled from the second space with Bene Gesserit Influence 3, under an
    Unload hold, so the Shipping rewards open their own window."""

    state = ENGINE.reset(UPRISING_IX, 0)
    owner = state.players[0]
    owner = replace(
        owner,
        freighter_space=2,
        influence=replace(owner.influence, bene_gesserit=3),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    held = push_unload_hold(state, 0, source="test")
    return recall_freighter(held, 0, source="test").state


def _take(state: GameState, **arguments: str) -> GameState:
    legal = ENGINE.legal_actions(state, 0)
    (action,) = (
        a
        for a in legal
        if all(dict(a.arguments).get(k) == v for k, v in arguments.items())
    )
    return ENGINE.apply(state, action, legal_actions=legal).state


def _the_draw_is_its_step_row(state: GameState) -> GameState:
    """Assert the decision offers only the Bene Gesserit draw, by its step
    row, and take it; return the state after."""

    (whole,) = ENGINE.whole_actions(state, 0)
    assert whole.action_id == "draw_owed_intrigue"
    legal = ENGINE.legal_actions(state, 0)
    assert legal == (BENE_GESSERIT_DRAW_ROW,)
    ActionCodec(UPRISING_IX).encode(BENE_GESSERIT_DRAW_ROW)
    after = ENGINE.apply(state, BENE_GESSERIT_DRAW_ROW, legal_actions=legal).state
    owner, before = after.players[0], state.players[0]
    assert len(owner.intrigue_cards) == len(before.intrigue_cards) + 1
    assert not owner.owed_draws
    assert picked_rows(after) == ()
    return after


def test_the_shipping_window_offers_the_immediate_draw_by_its_step() -> None:
    state = _take(_recalled_from_space_two(), faction="bene_gesserit")
    assert state.decision_stack[-1].kind == FrameKind.SHIPPING_REWARD_ICONS

    after = _the_draw_is_its_step_row(state)

    # The window's own rewards come back once the draw is taken.
    assert after.decision_stack[-1].kind == FrameKind.SHIPPING_REWARD_ICONS
    left = {dict(a.arguments)["effect"] for a in ENGINE.legal_actions(after, 0)}
    assert left == {"dividends", "spice", "recruit"}


def test_the_unload_hold_offers_the_immediate_draw_by_its_step() -> None:
    # The Influence last: the window closes first, and the draw waits on the
    # Unload hold under it.
    state = _recalled_from_space_two()
    state = _take(state, effect="spice")
    state = _take(state, effect="recruit")
    state = _take(state, faction="bene_gesserit")
    assert state.decision_stack[-1].kind == FrameKind.UNLOAD_ICONS

    after = _the_draw_is_its_step_row(state)

    assert after.decision_stack[-1].kind == FrameKind.TURN


ORIGINAL_IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, leader_draft=True
)
# Four app AI Hard seats; this seed reaches the window in round 4. Any seed
# of the 2026-11-07 scan (seeds 10000-11999, five of them) would do; the
# tests above do not depend on the app AI's moves.
SEED = 10429


class _Reached(Exception):
    def __init__(self, state: GameState) -> None:
        super().__init__("reached")
        self.state = state


def test_an_original_board_game_reaches_the_window_with_an_encodable_draw() -> None:
    agents = tuple(
        make_agent("app_ai", 900000 + SEED + seat, ORIGINAL_IX) for seat in range(4)
    )

    def stop_there(state: GameState) -> None:
        decision = ENGINE.current_decision(state)
        if (
            isinstance(decision, PlayerDecision)
            and state.decision_stack[-1].kind == FrameKind.SHIPPING_REWARD_ICONS
            and immediate_owed_draw_actions(state, decision.owner)
        ):
            raise _Reached(state)

    try:
        run_policy_game(ENGINE, ORIGINAL_IX, SEED, agents, on_state=stop_there)
    except _Reached as reached:
        state = reached.state
    else:
        raise AssertionError(
            f"seed {SEED} no longer reaches the Shipping rewards window with an "
            "immediate draw waiting; pick another seed of the scan"
        )
    seat = ENGINE.current_decision(state).owner  # type: ignore[union-attr]
    (row,) = ENGINE.legal_actions(state, seat)
    assert row.action_id == "draw"
    assert dict(row.arguments) == {
        "icon": "intrigue",
        "printed": "bene_gesserit",
        "source": "influence_track",
    }
    ActionCodec(ORIGINAL_IX).encode(row)
