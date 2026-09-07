"""A generic optional card trash decision ("[trash] icon" as a reward).

Liet Kynes' Arrakis Planetologist offers one per replaced sandworm: the
owner may trash a card from hand, discard pile or play area, or decline.
"""

from dataclasses import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.frames import FrameKind, context_str, owned_top_frame


def optional_trash_frame(player: int, source: str) -> DecisionFrame:
    """Return the decision frame offering one optional trash."""

    return DecisionFrame(
        kind=FrameKind.OPTIONAL_TRASH,
        frame_id=f"{source}:optional_trash",
        decision=PlayerDecision(owner=player, prompt="Trash a card or decline"),
        context=(("player", player), ("source", source)),
    )


def legal_optional_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every owned card in hand, discard pile or play, plus a decline."""

    frame = owned_top_frame(state, FrameKind.OPTIONAL_TRASH, player)
    if frame is None:
        return ()
    owner = state.players[player]
    return (
        DomainAction(action_id="decline_optional_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_optional_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in (*owner.hand, *owner.discard_pile, *owner.in_play)
        ),
    )


def apply_optional_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Trash the chosen card, or close the frame without trashing."""

    if action not in legal_optional_trash_actions(state, action.actor):
        raise ValueError("action is not a legal optional trash choice")
    frame = state.decision_stack[-1]
    source = context_str(dict(frame.context), "source", owner="Optional trash frame")
    popped = replace(state, decision_stack=state.decision_stack[:-1])
    if action.action_id == "decline_optional_trash":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:trash_declined",
                    kind="optional_trash_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    card_id = str(dict(action.arguments)["card_id"])
    return trash_personal_card(popped, action.actor, card_id, source=source)
