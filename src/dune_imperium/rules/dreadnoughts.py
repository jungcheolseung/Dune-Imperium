"""Rise of Ix dreadnoughts on Control spaces (leaf: no rule imports).

A Conflict won with a dreadnought puts one on a Control space; it controls
the space "until the end of the next Combat phase" and then returns to its
garrison, and the Control marker it covered controls the space again
[Rise of Ix p. 6] (docs/rules/rise-of-ix.md 6, OQ-121 ruling 1). The state
holds them as ``GameState.dreadnought_control`` (stage P4a); this module
reads who controls a space and ends the Combat phase's turn of them (stage
P4b-1a). Placing one is stage P4b-1b.
"""

from copy import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState


def space_controller(state: GameState, space_id: str) -> int | None:
    """Return the seat that controls ``space_id``, or None.

    A dreadnought on a Control space controls it ahead of the Control marker
    it covers [Rise of Ix p. 6] (the app's ``WormSpace::get_ControllingPlayer``,
    docs/base-game-and-ix-plan.md 17.5 item 5): the space's visit bonus and
    its defence deploy go to the dreadnought's owner. Otherwise the seat
    holding a Control marker there controls it, and nobody does when no
    marker is on the space either. Whoever controls a space is read here;
    a rule about the marker itself (taking control as a Conflict reward,
    the three-marker limit, the observation) reads ``control_space_ids``.
    """

    for dreadnought_space, seat, _ in state.dreadnought_control:
        if dreadnought_space == space_id:
            return seat
    holders = tuple(
        player.player_id
        for player in state.players
        if space_id in player.control_space_ids
    )
    if len(holders) > 1:
        raise RuntimeError("a critical location cannot have multiple controllers")
    return holders[0] if holders else None


def end_combat_dreadnoughts(state: GameState) -> RuleResult:
    """End the Combat phase's turn of the dreadnoughts on Control spaces.

    "지배는 다음 Combat 단계 끝까지이고, 그때 dreadnought는 garrison으로
    돌아가며 덮였던 marker의 주인이 다시 지배한다." [Rise of Ix p. 6]: each
    one marked ``leaving`` goes back to its owner's garrison, and every
    other one now becomes ``leaving``, to return at the end of the next
    Combat phase. This is the Combat phase's last act, with or without a
    winner (OQ-121 ruling 1, docs/rules/rise-of-ix.md 6). One
    ``dreadnought_returned`` event per dreadnought that went back. A game
    without a dreadnought on a Control space is left exactly as it is.
    """

    if not state.dreadnought_control:
        return RuleResult(state=state)
    players = list(state.players)
    staying: list[tuple[str, int, bool]] = []
    events: list[GameEvent] = []
    for space_id, seat, leaving in state.dreadnought_control:
        if not leaving:
            staying.append((space_id, seat, True))
            continue
        owner = players[seat]
        players[seat] = replace(
            owner, dreadnoughts_garrison=owner.dreadnoughts_garrison + 1
        )
        events.append(
            GameEvent(
                event_id=f"round:{state.round_number}:dreadnought_returned:{space_id}",
                kind="dreadnought_returned",
                payload=(("player", seat), ("space_id", space_id)),
            )
        )
    return RuleResult(
        state=replace(
            state, players=tuple(players), dreadnought_control=tuple(staying)
        ),
        events=tuple(events),
    )
