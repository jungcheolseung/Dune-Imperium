"""Each seat's chance of winning, round by round: a finished game's "형세 흐름".

The numbers come from ``evaluation.win_odds``: the server's search network
reads every seat's value at a round's opening over worlds that re-deal what
the whole table cannot see, so they are the same for every seat. The user's
rulings: 2026-11-07, every seat's numbers from public information, read at
each round's opening from round 1; 2026-11-08, none during play -- the game's
course is shown once it has ended, as a chart under the result table and
beside the review's slider, which marks the cursor's round
(``GameSessionManager.win_odds`` refuses a running game).

Like the Victory Point ledger (``vp_ledger``), the game is walked from its
opening along the live steps, as a review rebuilds a state, and the walk
keeps the state at each round's opening (``opens_round``) with the log index
of the step that reached it, which a review's cursor is measured against.

Each opening's numbers are computed once (about 30 ms on the Mac mini, 16
worlds) and kept on the session by the opening's round and log index, which
name it for good. They are never saved: the computation is deterministic, so
a restored game gets the same numbers back.
"""

import logging
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from dune_imperium.config import RulesetConfig
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.win_odds import (
    network_unavailable_reason,
    opens_round,
    unavailable_reason,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import JsonObject, JsonValue

if TYPE_CHECKING:
    from dune_imperium.training.network import PolicyValueNetwork

_LOGGER: Final = logging.getLogger(__name__)

# One round's numbers: one chance per seat, or None when a private pick was
# open at the opening (``evaluation.win_odds.private_choice_open``).
RoundOdds = tuple[float, ...] | None


@dataclass(frozen=True, slots=True)
class RoundOpening:
    """The state at one round's opening and the step that reached it."""

    round: int
    # The log index of the live step whose result is this state; -1 for the
    # game's opening state itself.
    index: int
    state: GameState

    @property
    def key(self) -> tuple[int, int]:
        """What names this opening for good: its round and log index."""

        return (self.round, self.index)


@dataclass(frozen=True, slots=True)
class OddsLedger:
    """The round openings of a game's first ``steps`` live steps."""

    steps: int
    # The log index of the last live step walked; -1 before any.
    last_index: int
    # The state after those steps, where the walk goes on from.
    state: GameState
    openings: tuple[RoundOpening, ...]

    @property
    def reached(self) -> int:
        """The last round whose opening the walk has passed (0 before any)."""

        return self.openings[-1].round if self.openings else 0

    def extends(self, live: Sequence[tuple[int, ReplayStep]]) -> bool:
        """Whether every step walked is still the same live step of ``live``."""

        if self.steps > len(live):
            return False
        return self.steps == 0 or live[self.steps - 1][0] == self.last_index


def start_ledger(state: GameState) -> OddsLedger:
    """The ledger of a game whose opening state is ``state``."""

    openings: tuple[RoundOpening, ...] = ()
    if opens_round(state, 0):
        openings = (RoundOpening(state.round_number, -1, state),)
    return OddsLedger(steps=0, last_index=-1, state=state, openings=openings)


def extend_ledger(
    engine: UprisingRulesEngine,
    ledger: OddsLedger,
    live: Sequence[tuple[int, ReplayStep]],
) -> OddsLedger:
    """Walk the live steps the ledger has not walked yet.

    ``live`` is every live step of the game in order, each with its log
    index, and must extend the ledger (``OddsLedger.extends``).
    """

    if not ledger.extends(live):
        raise ValueError("the live steps do not extend this ledger")
    if ledger.steps == len(live):
        return ledger
    state = ledger.state
    openings = list(ledger.openings)
    reached = ledger.reached
    for index, step in live[ledger.steps :]:
        state = engine.apply(state, step).state
        if opens_round(state, reached):
            reached = state.round_number
            openings.append(RoundOpening(reached, index, state))
    return OddsLedger(
        steps=len(live),
        last_index=live[-1][0],
        state=state,
        openings=tuple(openings),
    )


def odds_network(
    checkpoint: Path | None, config: RulesetConfig
) -> tuple[PolicyValueNetwork | None, str | None]:
    """The network whose values give a ``config`` game's odds, or the reason
    there is none: the game is not of the network's family, the server has
    no search network, or its file cannot give calibrated values."""

    reason = unavailable_reason(config)
    if reason is not None:
        return None, reason
    if checkpoint is None:
        return None, "no_network"
    try:
        from dune_imperium.training.older_teacher import reads_older_rows
        from dune_imperium.training.torch_policy import load_network_agent

        if reads_older_rows(checkpoint):
            return None, "network"
        # The search seats' own cached network (``_cached_network``), so
        # the odds hold no second copy of the weights.
        network = load_network_agent(str(checkpoint), config).network
    except (
        ImportError,
        OSError,
        EOFError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        RuntimeError,
        pickle.UnpicklingError,
    ) as error:
        _LOGGER.warning("win odds: the search network does not load (%s)", error)
        return None, "network"
    reason = network_unavailable_reason(network)
    if reason is not None:
        return None, reason
    return network, None


def odds_json(
    ledger: OddsLedger, computed: dict[tuple[int, int], RoundOdds]
) -> JsonObject:
    """The public payload: every round opening walked and its numbers."""

    rounds: list[JsonValue] = []
    for opening in ledger.openings:
        odds = computed.get(opening.key)
        rounds.append(
            {
                "round": opening.round,
                "index": opening.index,
                "odds": None if odds is None else [round(p, 4) for p in odds],
            }
        )
    return {"step_count": ledger.steps, "rounds": rounds}
