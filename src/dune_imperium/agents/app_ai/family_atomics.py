"""The app AI's Family Atomics rule, for seats that otherwise play a network.

The trained network uses the once-per-game token on its first Agent turn in
every game (160 of 160 seats over 40 deals of the play rules, 2026-10-12): the
token is offered at every Agent-turn effect choice, which the search seat
leaves to the network unsearched, and a search would only compare using it
now with using it a step later in the same turn. The app AI uses it in its
own Reveal turn, when the Imperium Row offers poor buys for the Persuasion it
has (``FamilyAtomicsAbility``; 131 of 160 seats, in every round). The search
seat borrows that rule (``NetworkSearchAgent``, ``family_atomics="app"``),
and so can the network's own seats in training self-play
(``SelfPlayRunner(family_atomics_rule=...)``, ``--family-atomics app``).
"""

import random

from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.immortality import FamilyAtomicsAbility
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState

FAMILY_ATOMICS_ACTION = "use_family_atomics"
# Who decides when a network seat spends the token: "app" (this rule) or
# "network" (the network, as every other decision).
FAMILY_ATOMICS_DECIDERS = ("app", "network")
# The app builds the ability on the player's playmat; nothing reads its owner.
_PLAYMAT = Entity(Kind.LEADER, "playmat")
_HARD = 2


def app_uses_family_atomics(state: GameState, observation: PlayerView) -> bool:
    """Whether the app AI (Hard) would use the observing seat's token now.

    ``FamilyAtomicsAbility.evaluate``: only in the seat's own Reveal turn
    with 4-8 Persuasion, and only when the buys the app predicts are worth at
    most 1 acquire value per Persuasion (or there are none). The app never
    takes an optional answer worth 0 or less, so the rule fires when the
    value is positive. The answer reads only what the seat may know
    (``AppContext``) and draws no random numbers, so a caller's RNG streams
    stay where they were.
    """

    context = AppContext(state, observation.player, observation)
    profile = Profile(context, TABLES[_HARD], random.Random(0))
    answer = FamilyAtomicsAbility(_PLAYMAT).evaluate(
        profile, Request((TargetInfo(options=(0, 1)),))
    )
    return answer.value > 0 and answer.response is not None


def without_family_atomics(
    offered: tuple[DomainAction, ...],
) -> tuple[DomainAction, ...]:
    """``offered`` without the Family Atomics token (never empty: the token is
    optional, so a decision offering it always offers something else)."""

    kept = tuple(a for a in offered if a.action_id != FAMILY_ATOMICS_ACTION)
    return kept or offered
