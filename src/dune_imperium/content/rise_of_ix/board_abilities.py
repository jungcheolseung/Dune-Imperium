"""Rise of Ix's four board spaces' printed icons as ability records (stage P4c-4).

Written like the original board's (``content.imperium.board_abilities``):
keyed by (space id, cost option, variant), one line per printed icon, each
resolved on its own [Rise of Ix p. 12] (docs/rules/rise-of-ix.md 8):

- Dreadnought (Landsraad, 3 Solari): "dreadnought commission 그리고/또는
  Acquire Tech" -- a Dreadnought icon and an Acquire Tech icon at Tech
  Discount 0, each "may", in the owner's order.
- Tech Negotiation (Landsraad): "고르기: Tech Discount 1로 Acquire Tech -OR-
  Negotiator 하나" -- the two halves of an "OR" box (``ONE_OF``). Its
  Reveal-turn Persuasion for an Agent there is read by the Reveal turn
  (``rules.reveal_turn``), like Hall of Oratory's.
- Interstellar Shipping (Spice Trade, Spacing Guild Influence 2): "Freighter
  두 번" -- two Freighter icons.
- Smuggling (Spice Trade): "1 Solari, Freighter 한 번".

The pieces are Rise of Ix's own and each is inherently a "may"
(``CommissionDreadnought``, ``AcquireTech``, ``PlaceNegotiator``,
``Freighter``): the owner takes an icon or leaves it, and one left unused
lapses when the turn ends (OQ-095 (2)). So a record's mark is automatic and
its lines carry no cost. ``AcquireTech`` always states its discount
(Bloodlines' default of 1 is not Rise of Ix's Dreadnought space's).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTech,
    CommissionDreadnought,
    EffectSection,
    Freighter,
    GainResources,
    PlaceNegotiator,
    Reward,
)


def _icons(*rewards: Reward, one_of: bool = False) -> Ability:
    """A space's printed icons, one line each; ``one_of`` for an "OR" box."""

    return Ability(
        timing=AbilityTiming.BOARD_SPACE,
        sections=tuple(EffectSection(rewards=(reward,)) for reward in rewards),
        mark=AbilityMark.AUTOMATIC,
        structure=(
            AbilityStructure.ONE_OF
            if one_of
            else AbilityStructure.SEPARATE
            if len(rewards) > 1
            else AbilityStructure.SEQUENCE
        ),
    )


IX_BOARD_SPACE_ABILITIES: Final[Mapping[tuple[str, int, str], Ability]] = (
    MappingProxyType(
        {
            # "dreadnought commission 그리고/또는 Acquire Tech" (Tech Discount 0).
            ("dreadnought", 0, ""): _icons(
                CommissionDreadnought(), AcquireTech(discount=0)
            ),
            # "Tech Discount 1로 Acquire Tech -OR- Negotiator 하나".
            ("tech_negotiation", 0, ""): _icons(
                AcquireTech(discount=1), PlaceNegotiator(), one_of=True
            ),
            # "Freighter 두 번".
            ("interstellar_shipping", 0, ""): _icons(Freighter(), Freighter()),
            # "1 Solari, Freighter 한 번".
            ("smuggling", 0, ""): _icons(GainResources(solari=1), Freighter()),
        }
    )
)
