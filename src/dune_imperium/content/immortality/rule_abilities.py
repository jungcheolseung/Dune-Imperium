"""Immortality's printed rule changes as standing ability records (composed
effects, A7d).

docs/composed-effects-plan.md 5 (A7d): three Tleilaxu cards and the Family
Atomics token print a change to a rule rather than an effect with a moment
of its own, so each record names the engine branch that applies it (the
A6 ``STANDING`` convention): Ghola "has the same Agent box as the other
grafted card" [Immortality p. 14] (``rules.effects.borrowed_agent_card``);
Usurp may graft to an Imperium Row card without acquiring it, which is
trashed at the end of the turn (OQ-054; ``card_is_usurp``); Tleilaxu
Infiltrator's "Enemy Agents don't block your Agent this turn"
(``rules.agent_turn.is_tleilaxu_infiltrator``; the rest of its box is an A2
record); Family Atomics, once per game in its owner's turn, replaces the
Imperium Row [Immortality p. 12] (OQ-051; ``rules.immortality``). Keyed by
card id (``family_atomics`` for the token).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)


def _standing(hook: str) -> Ability:
    return Ability(
        timing=AbilityTiming.STANDING,
        sections=(),
        mark=AbilityMark.AUTOMATIC,
        hook=hook,
    )


IMMORTALITY_STANDING_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "ghola": _standing("ghola_copies_agent_box"),
        "usurp": _standing("usurp_grafts_row_card"),
        "tleilaxu_infiltrator": _standing("infiltrator_ignores_enemy_agents"),
        "family_atomics": _standing("family_atomics"),
    }
)
