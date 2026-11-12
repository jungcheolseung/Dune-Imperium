"""Placing a Rise of Ix Negotiator (stage P4c-1).

"Tech Negotiation(협상가): 아이콘마다 supply의 troop 하나를 Ix board에
Negotiator로 놓을 수 있다("may"; supply가 비면 아무 일도 없다). 나중에
Acquire Tech 때 원하는 만큼("any number") Negotiator를 supply로 돌려 하나에
spice 1씩 깎는다. ... Negotiator는 recruit할 수 없다(Ix board의 troop을
garrison으로 데려오는 것이 아니다) [FAQ p. 4]." (docs/rules/rise-of-ix.md 4,
[Rise of Ix p. 4]). The piece is ``effect_dsl.PlaceNegotiator``: an optional
("may") icon the owner takes or leaves, offered by whatever prints it (an
Intrigue Plot through the executor, ``ability_executor``; the Tech Negotiation
space and the cards, stages P4c-4 and P4d). Its block is this module's
``negotiator_block``, which each of them reads, so the icon is offered exactly
when it can do something.

A Negotiator is one of the seat's 12 troops (``PlayerState.negotiators``): it
leaves the supply here and returns to it in an Acquire Tech
(``rules.tech``). It is never recruited or deployed -- no row moves it to the
garrison -- so it is in no unit count of a turn.
"""

from copy import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import OptionalBlockKind, OptionalEffectBlock
from dune_imperium.rules.frames import replace_player


def negotiator_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why ``player``'s Tech Negotiation icon has no effect now, or None.

    "supply가 비면 아무 일도 없다" (docs/rules/rise-of-ix.md 4): with no
    troop in the supply -- every one is in the garrison, the Conflict or on
    the Ix board already -- the icon fizzles. It blocks only the icon, never
    the space or the card that prints it. A specimen or a memory is no troop
    of the supply (it is not recruited from it), so only the supply counts.
    """

    if state.players[player].troops_supply >= 1:
        return None
    return OptionalEffectBlock(OptionalBlockKind.NO_TROOP_FOR_NEGOTIATOR)


def place_negotiator(state: GameState, player: int, *, source: str) -> RuleResult:
    """Move one troop of ``player`` from its supply to the Ix board.

    "Tech Negotiation 아이콘마다 supply의 troop 하나를 Ix board에
    Negotiator로" [Rise of Ix p. 4]: one per icon, so the caller calls this
    once for each icon the owner takes. ``source`` names the event
    (``<source>:negotiator_placed``).
    """

    if negotiator_block(state, player) is not None:
        raise ValueError("no troop is left in the supply to place as a Negotiator")
    owner = state.players[player]
    placed = replace(
        owner,
        troops_supply=owner.troops_supply - 1,
        negotiators=owner.negotiators + 1,
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, placed)),
        events=(
            GameEvent(
                event_id=f"{source}:negotiator_placed",
                kind="negotiator_placed",
                payload=(("player", player),),
            ),
        ),
    )
