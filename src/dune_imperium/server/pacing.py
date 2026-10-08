"""How a game's AI seats pace their answers for the tables watching.

A heuristic or app AI seat answers in milliseconds, so the server used to
play a whole run of AI decisions inside the request that handed them the
game: the browsers received the board after every AI turn at once and
narrated it afterwards. A paced game instead hands every AI decision to the
game's worker (as it always did a search seat's), which applies it once
the tables have had the time to show what came before ("진짜 게임처럼",
user, 2026-10-08; the default "normal" is the user's choice of the
recommended plan).

What the tables show is read off the public events alone: a seat's timing
must never tell another seat anything the log does not. The seconds below
are the browser's own cue lengths (``static/effects.js``) at full length.
"""

from typing import Final

from dune_imperium.core.events import GameEvent

# "normal" shows every cue at full length, "fast" at 0.6 of it (the browser
# shortens its own cues by the same factor), "instant" answers inside the
# request as every non-search seat always did.
AI_PACES: Final = ("normal", "fast", "instant")
PACE_SCALE: Final[dict[str, float]] = {"normal": 1.0, "fast": 0.6, "instant": 0.0}

# A card-use cue (effects.js CARD_PLAY_EVENTS), a phase banner, the Combat
# result board (one per step, however many seats it lists), and an AI seat's
# turn banner, shown while it waits at its turn start.
CARD_CUE_EVENTS: Final = frozenset(
    {
        "agent_placed",
        "turn_start_card_played",
        "card_grafted",
        "intrigue_played",
        "navigation_card_played",
    }
)
BANNER_EVENTS: Final = frozenset(
    {
        "conflict_revealed",
        "combat_intrigue_started",
        "scouts_item_revealed",
        "endgame_started",
    }
)
CARD_CUE_SECONDS: Final = 2.2
BANNER_SECONDS: Final = 1.6
RESULT_SECONDS: Final = 3.2
TURN_BANNER_SECONDS: Final = 1.6
# However much piled up, one AI answer waits no longer than this.
MAX_WAIT_SECONDS: Final = 8.0


def cue_seconds(events: tuple[GameEvent, ...]) -> float:
    """How long the tables take to show a step's public events, full length."""

    kinds = [event.kind for event in events if event.visible_to is None]
    seconds = CARD_CUE_SECONDS * sum(kind in CARD_CUE_EVENTS for kind in kinds)
    seconds += BANNER_SECONDS * sum(kind in BANNER_EVENTS for kind in kinds)
    if "combat_standing" in kinds:
        seconds += RESULT_SECONDS
    return seconds
