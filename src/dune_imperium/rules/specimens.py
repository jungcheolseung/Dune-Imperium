"""Specimens: supply troops resting in the Axolotl tanks [Immortality p. 8].

Kept apart from ``rules.immortality`` so the Reveal turn can generate
specimens without importing the research modules (which import the card
draw, which imports the Reveal turn).
"""

from dataclasses import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import replace_player


def generate_specimens(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    """Move up to ``count`` troops from the supply into the Axolotl tanks.

    "take a troop from your supply and place it in the Axolotl tanks"
    [Immortality p. 8]; with an empty supply nothing is generated and the
    shortfall is a public event (OQ-049, the shape of OQ-030's recruit
    shortfall).
    """

    if count < 1:
        raise ValueError("specimen count must be positive")
    if not state.config.immortality:
        raise ValueError("specimens require Immortality")
    owner = state.players[player]
    generated = min(owner.troops_supply, count)
    next_owner = replace(
        owner,
        troops_supply=owner.troops_supply - generated,
        specimens=owner.specimens + generated,
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:specimens",
            kind="specimens_generated",
            payload=(("count", generated), ("player", player)),
        )
    ]
    if generated < count:
        events.append(
            GameEvent(
                event_id=f"{source}:specimens_short",
                kind="specimens_short",
                payload=(
                    ("generated", generated),
                    ("player", player),
                    ("requested", count),
                    ("short", count - generated),
                ),
            )
        )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=tuple(events),
    )


def spend_specimens(owner: PlayerState, count: int) -> PlayerState:
    """Return ``count`` specimens from the tanks to the supply.

    "Whenever you spend a specimen, return it to your supply" [Immortality
    p. 8]; a voluntary return uses the same move.
    """

    if count < 0 or owner.specimens < count:
        raise ValueError("not enough specimens to spend")
    return replace(
        owner,
        specimens=owner.specimens - count,
        troops_supply=owner.troops_supply + count,
    )
