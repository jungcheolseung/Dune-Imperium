"""Each seat's chance of winning from a round's opening, read from public information.

The user asked (2026-11-07) for every player's chance of winning in the current
position, and chose: the four seats' numbers computed from public information
only, from round 1 on, read at each round's opening. On 2026-11-08 they ruled
that no number is shown during play: a finished game shows its course, round
by round, on the result screen and in its review (``server.win_odds``).

**What the number is.** The search seat's network has a value: one number per
seat, read from that seat's own view, the graded reward of its final place
(1 for the winner, -1/6, -1/3, -1/2 for second to fourth) it expects when the
network plays every seat greedily from here (``training.round_values``). The
four values become the chance of first place by ``softmax(BETA * value)``.
BETA was fitted by likelihood on the 2026-11-03 and 2026-11-04 playout test
sets (80 games each, rounds 1-5 and 7, the E3 network
``selfplay-s1-e3.pt``): 2.7-3.1 on either set, the same in every round, and
checked on the other set (shown 25% won 25-26%, shown 69% won 69-72%). It is
"the network's chance of first place if four copies of it played on from
here"; how human tables differ is not measured.

**Public information only.** A seat's value reads its own hand, Intrigue cards
and other things only it sees, so a number from its real view would tell the
table about them (by 1.3-1.5 percentage points on average, 4-5 at the 95th
percentile, on those test sets). Each seat's value is therefore averaged over
``WORLDS`` worlds that re-deal everything hidden from a spectator
(``determinize`` with no observer), seeded by the round alone: the numbers are
a function of what the whole table sees, the same for every seat and on every
recomputation. On the test sets this kept 97-100% of the own-view numbers'
gain over a flat 25% (Brier difference -0.0004 [-0.007, +0.006] and
+0.003 [-0.001, +0.008]); 8-16 worlds are as good as 32. The open frames of a
round's opening hold nothing private; ``private_choice_open`` refuses a state
where one does (an owner-only pick the worlds would not re-deal).

**Only at a round's opening.** The value was fitted on the first state of each
round past its Round Start, and read in the middle of a round it predicts the
winner worse than the round's opening value kept on (Brier +0.03 early in the
turns, up to +0.19 late) and jumps by up to 55 points. So a round's number is
read once, at that state (``opens_round``), and holds for the round.

**Where it is shown.** Only games of the network's own family: the Uprising
board without any Rise of Ix part or the original game's cards
(``unavailable_reason``). Measurements: ``docs/win-odds.md``.
"""

import random
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from dune_imperium.agents.determinize import determinize
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.core.observation import NO_IX_PENDING, observe_state
from dune_imperium.core.state import GamePhase, GameState

if TYPE_CHECKING:
    from dune_imperium.training.network import PolicyValueNetwork

# softmax temperature over the four seats' values (module docstring).
BETA: Final = 2.9
# Worlds each round's numbers average over.
WORLDS: Final = 16
# The graded reward the calibration was fitted for (training.round_values).
REWARD_STEP: Final = 1 / 6

_NOT_ROUND: Final = frozenset(
    {GamePhase.SETUP, GamePhase.ROUND_START, GamePhase.FINISHED}
)


def opens_round(state: GameState, reached: int) -> bool:
    """Whether ``state`` is the opening of a round after round ``reached``.

    The first state of a round past its Round Start: where the value was
    fitted and a search leaf reads it (``training.round_values``).
    """

    return state.round_number > reached and state.phase not in _NOT_ROUND


def unavailable_reason(config: RulesetConfig) -> str | None:
    """Why a game of ``config`` shows no win odds, or None when it does.

    The calibrated network learned the Uprising board with its own
    expansions; Rise of Ix (all or part) and the original game's cards and
    board are content it never saw.
    """

    if config.players != 4:
        return "players"
    if config.base_game is not BaseGame.UPRISING:
        return "base_game"
    if config.rise_of_ix or config.ix_tech_tiles or config.ix_leaders:
        return "rise_of_ix"
    if config.imperium_cards:
        return "imperium_cards"
    return None


def network_unavailable_reason(network: PolicyValueNetwork) -> str | None:
    """Why ``network``'s values do not fit ``BETA``, or None when they do."""

    step = float(getattr(network, "reward_step", 0.0) or 0.0)
    if abs(step - REWARD_STEP) > 1e-9:
        return "reward_step"
    return None


def private_choice_open(state: GameState) -> bool:
    """Whether some seat's view shows a pick the public worlds keep.

    ``determinize`` with no observer re-deals hands, decks, Intrigue cards
    and the other standing secrets, so a card a seat may always look at
    (Glowglobes' and Prescience's top card) is dealt again with its deck,
    and what a seat knows of another's Intrigue cards (OQ-149: Imperium
    Ceremony, Viscount Hundro Moritani) is forgotten. What an open frame shows
    its owner is not: Controlled's peeked card, a card picked for an Agent
    turn and not placed yet, rows picked toward an effect, Imperium
    Ceremony's cards while their owner chooses, and Rise of Ix's pending
    choices. A round's opening holds none of these; a state that does gets
    no numbers.
    """

    if state.decision_stack and dict(state.decision_stack[-1].context).get(
        "peeked_card_id"
    ):
        return True
    for seat in range(len(state.players)):
        private = observe_state(state, seat).private
        if private is None:
            continue
        if (
            private.peeked_intrigue_ids
            or private.agent_card_pick
            or private.effect_pick
            or private.ix_pending != NO_IX_PENDING
        ):
            return True
    return False


def public_values(
    network: PolicyValueNetwork, state: GameState, worlds: int = WORLDS
) -> tuple[float, ...]:
    """Each seat's value averaged over ``worlds`` public worlds of ``state``."""

    import numpy as np
    import torch

    from dune_imperium.training.policy import encoded_view

    seats = len(state.players)
    rows: list[np.ndarray] = []
    for index in range(worlds):
        world = determinize(
            state, None, random.Random(f"win-odds:{state.round_number}:{index}")
        )
        rows.extend(encoded_view(observe_state(world, seat)) for seat in range(seats))
    with torch.no_grad():
        values = network.values(torch.from_numpy(np.stack(rows))).numpy()
    means = values.reshape(worlds, seats).mean(axis=0)
    return tuple(float(value) for value in means)


def odds_from_values(values: Sequence[float], beta: float = BETA) -> tuple[float, ...]:
    """The chance of first place of each seat: ``softmax(beta * values)``."""

    import math

    top = max(values)
    weights = [math.exp(beta * (value - top)) for value in values]
    total = sum(weights)
    return tuple(weight / total for weight in weights)


def round_odds(
    network: PolicyValueNetwork, state: GameState, worlds: int = WORLDS
) -> tuple[float, ...] | None:
    """The win odds at a round's opening ``state``, or None if a private pick
    is open (``private_choice_open``)."""

    if private_choice_open(state):
        return None
    return odds_from_values(public_values(network, state, worlds))
