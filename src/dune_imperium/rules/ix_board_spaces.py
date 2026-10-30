"""Rise of Ix's four board spaces (stage P4c-4).

[Rise of Ix p. 12], docs/rules/rise-of-ix.md 8: Dreadnought (3 Solari) --
"dreadnought commission 그리고/또는 Acquire Tech"; Tech Negotiation -- "고르기:
Tech Discount 1로 Acquire Tech -OR- Negotiator 하나"; Interstellar Shipping
(Spacing Guild Influence 2 or more) -- "Freighter 두 번"; Smuggling -- "1
Solari, Freighter 한 번". The records are
``content.rise_of_ix.board_abilities``; this module offers and plays the
pieces they print, each an icon of the visit that the owner takes or leaves
("may"; one left unused lapses when the turn ends, OQ-095 (2)):

- ``commission`` -- ``CommissionDreadnought`` (``rules.dreadnought_commission``),
  offered while a dreadnought is in the supply.
- ``ix_tech`` -- the Dreadnought space's Acquire Tech at Tech Discount 0, which
  opens the Ix acquisition window (``rules.tech``, its refusal printed by the
  space); offered while a tile is within reach.
- ``tech_negotiation`` -- the "OR" box: Acquire Tech at Tech Discount 1, or a
  Negotiator (``rules.negotiators``); the icon is spent by whichever is taken.
- ``freighter`` -- one icon each (``rules.shipping_track``): up one space or
  recall; the recall's rewards wait on the turn like any Freighter recall.

The Freighter icon's rows are the visit's own (``advance_board_freighter``,
``recall_board_freighter``), beside the ``FREIGHTER_MOVE`` window's.
"""

from typing import Final

from dune_imperium.content.rise_of_ix.board import IX_SPACE_IDS
from dune_imperium.content.rise_of_ix.board_abilities import IX_BOARD_SPACE_ABILITIES
from dune_imperium.content.uprising.abilities import AbilityStructure
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTech,
    CommissionDreadnought,
    Freighter,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import GameState
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.dreadnought_commission import (
    commission_block,
    commission_dreadnought,
)
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    finish_board_icon,
    pending_board_icons,
)
from dune_imperium.rules.frames import context_str
from dune_imperium.rules.negotiators import negotiator_block, place_negotiator
from dune_imperium.rules.shipping_track import (
    freighter_can_advance,
    freighter_can_recall,
    move_freighter_up,
    recall_freighter,
)
from dune_imperium.rules.tech import push_tech_acquisition, tech_acquisition_possible

# The visit's icon keys (``effects.OPTIONAL_BOARD_ICONS`` spells them too).
BOARD_ICON_COMMISSION: Final = "commission"
BOARD_ICON_IX_TECH: Final = "ix_tech"
BOARD_ICON_TECH_NEGOTIATION: Final = "tech_negotiation"
BOARD_ICON_FREIGHTER: Final = "freighter"

COMMISSION_ACTION: Final = "commission_board_dreadnought"
IX_TECH_ACTION: Final = "acquire_board_tech"
NEGOTIATION_TECH_ACTION: Final = "acquire_negotiation_tech"
NEGOTIATOR_ACTION: Final = "place_board_negotiator"
ADVANCE_ACTION: Final = "advance_board_freighter"
RECALL_ACTION: Final = "recall_board_freighter"

# The icon each action answers.
ICON_OF_ACTION: Final = {
    COMMISSION_ACTION: BOARD_ICON_COMMISSION,
    IX_TECH_ACTION: BOARD_ICON_IX_TECH,
    NEGOTIATION_TECH_ACTION: BOARD_ICON_TECH_NEGOTIATION,
    NEGOTIATOR_ACTION: BOARD_ICON_TECH_NEGOTIATION,
    ADVANCE_ACTION: BOARD_ICON_FREIGHTER,
    RECALL_ACTION: BOARD_ICON_FREIGHTER,
}

_FRAME: Final = "Agent-turn effect frame"


def ix_space_icons(space_id: str) -> tuple[str, ...]:
    """The icons of one visit to a Rise of Ix space, read off its record in
    printed order; a space's Solari is the visit's automatic resources icon,
    not one of these."""

    ability = IX_BOARD_SPACE_ABILITIES[space_id, 0, ""]
    if ability.structure is AbilityStructure.ONE_OF:
        # "-OR-": one icon the owner answers with either half.
        return (BOARD_ICON_TECH_NEGOTIATION,)
    keys: list[str] = []
    for section in ability.sections:
        for reward in section.rewards:
            match reward:
                case CommissionDreadnought():
                    keys.append(BOARD_ICON_COMMISSION)
                case AcquireTech():
                    keys.append(BOARD_ICON_IX_TECH)
                case Freighter():
                    keys.append(BOARD_ICON_FREIGHTER)
                case _:
                    pass
    return tuple(keys)


def _tech_discount(space_id: str) -> int:
    """The Tech Discount the space's record prints on its Acquire Tech
    (Dreadnought 0, Tech Negotiation 1)."""

    for section in IX_BOARD_SPACE_ABILITIES[space_id, 0, ""].sections:
        for reward in section.rewards:
            if isinstance(reward, AcquireTech):
                return reward.discount
    raise ValueError(f"{space_id} prints no Acquire Tech")


def _own_context(state: GameState, player: int) -> dict[str, ActionValue] | None:
    """``player``'s Agent-turn effect frame's context, while it is on top."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    return context


def legal_ix_space_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """The rows of the visit's pending Rise of Ix icons."""

    if not state.config.rise_of_ix:
        return ()
    context = _own_context(state, player)
    if context is None:
        return ()
    space_id = context.get("space_id")
    if space_id not in IX_SPACE_IDS:
        return ()
    assert isinstance(space_id, str)
    pending = pending_board_icons(context)
    owner = state.players[player]
    rows: list[str] = []
    if BOARD_ICON_COMMISSION in pending and commission_block(state, player) is None:
        rows.append(COMMISSION_ACTION)
    if BOARD_ICON_IX_TECH in pending and tech_acquisition_possible(
        state, owner, _tech_discount(space_id)
    ):
        rows.append(IX_TECH_ACTION)
    if BOARD_ICON_TECH_NEGOTIATION in pending:
        if tech_acquisition_possible(state, owner, _tech_discount(space_id)):
            rows.append(NEGOTIATION_TECH_ACTION)
        if negotiator_block(state, player) is None:
            rows.append(NEGOTIATOR_ACTION)
    if BOARD_ICON_FREIGHTER in pending:
        if freighter_can_advance(state, player):
            rows.append(ADVANCE_ACTION)
        if freighter_can_recall(state, player):
            rows.append(RECALL_ACTION)
    return tuple(DomainAction(action_id=row, actor=player) for row in rows)


def ix_icon_offered(state: GameState, player: int, key: str) -> bool:
    """Whether the visit's pending icon ``key`` offers a row now (the page
    greys an icon out with this, ``display.unavailable``)."""

    return any(
        ICON_OF_ACTION[action.action_id] == key
        for action in legal_ix_space_actions(state, player)
    )


def apply_ix_space_action(state: GameState, action: DomainAction) -> RuleResult:
    """Take one icon of the visited Rise of Ix space.

    The icon is retired and the frame written back first, so the piece's own
    effects (a dreadnought credited to the turn, a recall's rewards queued on
    it, the acquisition window) land on the state the frame belongs to."""

    player = action.actor
    if action not in legal_ix_space_actions(state, player):
        raise ValueError("action is not a legal Rise of Ix board space choice")
    _, context = current_agent_effect_context(state)
    space_id = context_str(context, "space_id", owner=_FRAME)
    source = f"round:{state.round_number}:player:{player}:board:{space_id}"
    finish_board_icon(context, ICON_OF_ACTION[action.action_id])
    working = advance_after_effect(state, context)
    match action.action_id:
        case "commission_board_dreadnought":
            return commission_dreadnought(
                working, player, source=f"{source}:commission"
            )
        case "place_board_negotiator":
            return place_negotiator(working, player, source=f"{source}:negotiator")
        case "acquire_board_tech" | "acquire_negotiation_tech":
            return push_tech_acquisition(
                working,
                player,
                discount=_tech_discount(space_id),
                source=f"{source}:ix_tech",
                printer=printer_value(Source.BOARD_SPACE, space_id),
            )
        case "advance_board_freighter":
            return move_freighter_up(working, player, source=f"{source}:freighter")
        case "recall_board_freighter":
            return recall_freighter(working, player, source=f"{source}:freighter")
    raise ValueError(f"{action.action_id} is no Rise of Ix board space choice")
