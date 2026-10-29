"""Commissioning a Rise of Ix dreadnought (stage P4b-2).

"Dreadnought 아이콘마다 supply의 dreadnought 하나를 garrison에 commission할
수 있다("may"). ... 한 좌석은 동시에 둘까지; supply에 없으면 더 얻지 못한다.
Dreadnought 칸은 둘이 이미 있어도 갈 수 있고 그 아이콘만 불발한다 (디자이너
판정, BGG forum)." (docs/rules/rise-of-ix.md 6, [Rise of Ix p. 6]). The piece
is ``effect_dsl.CommissionDreadnought``: an optional ("may") icon the owner
takes or leaves, offered by whatever prints it (an Intrigue Plot through the
executor, ``ability_executor``; the Dreadnought space and the cards, stages
P4c and P4d). Its block is this module's ``commission_block``, which each of
them reads, so the icon is offered exactly when it can do something.

A dreadnought commissioned in the owner's own Agent turn is recorded on the
turn frame (``frames.DREADNOUGHTS_COMMISSIONED_KEY``), beside the Commanders
a turn recruited: "If you commissioned the dreadnought while sending an Agent
to a Combat space, you may deploy it to the Conflict" [Rise of Ix p. 6]
(``combat_deployment``).
"""

from copy import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import OptionalBlockKind, OptionalEffectBlock
from dune_imperium.rules.frames import credit_commissioned_dreadnoughts, replace_player


def commission_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why ``player``'s Dreadnought icon has no effect now, or None.

    "supply에 없으면 더 얻지 못한다" (docs/rules/rise-of-ix.md 6): with no
    dreadnought in the supply -- both are in the garrison, the Conflict or on
    a Control space -- the icon fizzles. It blocks only the icon, never the
    space or the card that prints it (designer ruling, BGG forum).
    """

    if state.players[player].dreadnoughts_supply >= 1:
        return None
    return OptionalEffectBlock(OptionalBlockKind.NO_DREADNOUGHT_TO_COMMISSION)


def commission_dreadnought(state: GameState, player: int, *, source: str) -> RuleResult:
    """Move one dreadnought of ``player`` from its supply to its garrison.

    "Dreadnought 아이콘마다 supply의 dreadnought 하나를 garrison에
    commission" [Rise of Ix p. 6]: one per icon, so the caller calls this once
    for each icon the owner takes. The commission is credited on the owner's
    own Agent turn (``frames.credit_commissioned_dreadnoughts``); in a Reveal
    turn or outside the owner's turn it still moves the dreadnought but
    opens no deployment. ``source`` names the event
    (``<source>:dreadnought_commissioned``).
    """

    if commission_block(state, player) is not None:
        raise ValueError("no dreadnought is left in the supply to commission")
    owner = state.players[player]
    commissioned = replace(
        owner,
        dreadnoughts_supply=owner.dreadnoughts_supply - 1,
        dreadnoughts_garrison=owner.dreadnoughts_garrison + 1,
    )
    working = replace(state, players=replace_player(state.players, commissioned))
    return RuleResult(
        state=credit_commissioned_dreadnoughts(working, player, 1),
        events=(
            GameEvent(
                event_id=f"{source}:dreadnought_commissioned",
                kind="dreadnought_commissioned",
                payload=(("player", player),),
            ),
        ),
    )
