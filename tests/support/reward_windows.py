"""Answering stage B2's reward windows the way the engine paid them before.

Stage B2 (OQ-112) opens a window for each Conflict reward recipient and for
each completed Contract: a row per icon, resolved in any order. Since stage
B3b a Contract completed in its owner's own turn leaves its icons as rows of
that turn instead (OQ-112 (4)), offered while the turn frame is on top. A
test that paid a reward and looked at the result right after now answers the
window or those rows first. ``answer_reward_windows`` answers through the
engine (its automatic steps run between the rows, as in play);
``settle_reward_window`` answers one window, or the turn's Contract rows,
with the rule functions alone, for a test that drives those directly. Both
take the rows in the order the engine paid them before
(``rules.combat.legacy_combat_reward_icon``,
``rules.contracts.legacy_contract_reward_icon``,
``rules.contracts.legacy_contract_icon_row``) and stop at the first choice
an icon opens (an Influence, a Spy post, a trash...), which the test then
answers itself.
"""

from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import (
    apply_combat_reward_icon,
    legacy_combat_reward_icon,
)
from dune_imperium.rules.contracts import (
    apply_contract_reward_icon,
    legacy_contract_icon_row,
    legacy_contract_reward_icon,
)
from dune_imperium.rules.frames import FrameKind, top_frame


def _legacy(state: GameState) -> DomainAction | None:
    frame = top_frame(state)
    if frame is None or not isinstance(frame.decision, PlayerDecision):
        return None
    owner = frame.decision.owner
    return (
        legacy_combat_reward_icon(state, owner)
        or legacy_contract_reward_icon(state, owner)
        or legacy_contract_icon_row(state, owner)
    )


def answer_reward_windows(
    engine: UprisingRulesEngine, state: GameState, *, limit: int = 64
) -> GameState:
    """Answer every reward window row, and every Contract row waiting on
    its owner's turn, the engine offers next, in the older engine's order,
    through ``engine.apply`` (a row's effect steps where the frame offers
    effects effect first); stop at anything else."""

    for _ in range(limit):
        answer = _legacy(state)
        if answer is None or answer not in engine.whole_actions(state, answer.actor):
            return state
        state = apply_whole(engine, state, answer).state
    raise AssertionError("reward windows did not close")


def settle_reward_window(state: GameState, *, limit: int = 32) -> GameState:
    """Answer the reward window on top, or the Contract rows waiting on the
    turn frame on top, with the rule functions alone (no engine step between
    rows), up to the first choice an icon opens."""

    for _ in range(limit):
        frame = top_frame(state)
        if frame is None:
            return state
        if frame.kind not in (
            FrameKind.COMBAT_REWARD_ICONS,
            FrameKind.CONTRACT_REWARD_ICONS,
        ):
            if not isinstance(frame.decision, PlayerDecision):
                return state
            row = legacy_contract_icon_row(state, frame.decision.owner)
            if row is None:
                return state
            state = apply_contract_reward_icon(state, row).state
            continue
        answer = _legacy(state)
        assert answer is not None
        apply = (
            apply_combat_reward_icon
            if frame.kind == FrameKind.COMBAT_REWARD_ICONS
            else apply_contract_reward_icon
        )
        state = apply(state, answer).state
    raise AssertionError("the reward window did not close")
