"""Trigger ability records of personal cards (composed effects, A4a, A4h).

docs/composed-effects-plan.md 5 (A4a): a personal card's "when acquired",
"when trashed" and "when discarded" boxes are written here as automatic
ability records, with Guild Spy's Reveal-acquisition box, keyed by the
card's id (docs/content-core-refactor-plan.md 8.3;
``content.registry.card_abilities`` merges every set's, Bloodlines'
turn-start box among them); the printed text is
``display/tokens.py`` (``ACQUISITION_EFFECT_TEXT``, ``TRASH_EFFECT_TEXT``,
``DISCARD_EFFECT_TEXT``). None of them offers a choice: the box pays when it
fires. The exception is the original game's Influence boxes (OQ-141): a box
of several Influence icons (CHOAM Directorship) or of one with a Faction of
the owner's choice (Lady Jessica) is paid icon by icon, a row each in the
owner's order (``rules.acquire_icons``).

- An acquire box is paid by ``rules.acquisition`` in three pieces whose order
  each purchase path keeps as it was: the owner's gains and Overthrow's draw
  (``resolve_acquisition_bonus``), a fixed Faction's Influence (or the rows
  of a box paid icon by icon), and the token tracks after the card has
  reached its zone; a Spy or a Contract is left to the path, which opens its
  choice.
- A trash box is paid inside ``rules.card_trash.trash_personal_card``,
  whatever trashed the card; a discard box by
  ``rules.card_discard.resolve_personal_card_discard_trigger`` (a deck
  discard included, OQ-013).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
    automatic_box,
)
from dune_imperium.content.core.effects import (
    DrawIntrigueCards,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecruitTroops,
    Reward,
    TakeContract,
)
from dune_imperium.content.core.icons import Faction

# The acquire boxes of the cards this package defines, by card id; the
# original game's, Rise of Ix's, Bloodlines', Immortality's and the Tleilaxu
# cards' are in their sets.
# A Spy or a Contract is left to the purchase path, which opens its choice.
_PLACE_SPY: Final = automatic_box(AbilityTiming.ACQUIRE, PlaceSpy())
_TAKE_CONTRACT: Final = automatic_box(AbilityTiming.ACQUIRE, TakeContract(1))


def _acquire(*rewards: Reward) -> Ability:
    return automatic_box(AbilityTiming.ACQUIRE, *rewards)


def _trash(*rewards: Reward) -> Ability:
    return automatic_box(AbilityTiming.TRASH, *rewards)


def _discard(*rewards: Reward) -> Ability:
    return automatic_box(AbilityTiming.DISCARD, *rewards)


UPRISING_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Overthrow: its own step right after the purchase inside the seat's
        # turn (OQ-106, OQ-042).
        "overthrow": _acquire(DrawIntrigueCards(1)),
        "price_is_no_object": _acquire(GainResources(solari=2)),
        "guild_spy": _PLACE_SPY,
        "in_high_places": _PLACE_SPY,
        "spy_network": _PLACE_SPY,
        "strike_fleet": _PLACE_SPY,
        "subversive_advisor": _PLACE_SPY,
        "steersman": _acquire(GainInfluence(factions=(Faction.SPACING_GUILD,))),
        "interstellar_trade": _TAKE_CONTRACT,
        "arrakis_revolt": _acquire(RecruitTroops(1)),
    }
)

# The trash boxes of Uprising's cards, by card id; the original game's
# Assassination Mission is ``content.imperium.trigger_abilities``.
UPRISING_TRASH_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # A free-order step inside the seat's turn (OQ-106).
        "sardaukar_soldier": _trash(DrawIntrigueCards(1)),
    }
)

UPRISING_DISCARD_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "spacing_guild_s_favor": _discard(GainResources(spice=2)),
    }
)


# A box whose flow stays code (composed A4h), with no line: the DSL cannot say
# it whole. Guild Spy: "Gain 1 Influence with each Faction you are spying on"
# once The Spice Must Flow is acquired during the owner's Reveal, once per
# copy, Spies counted then (OQ-057 designer rulings;
# ``reveal_turn.fire_guild_spy_on_spice_must_flow``). Bloodlines' Litany
# Against Fear is ``content.bloodlines.trigger_abilities``.
UPRISING_REVEAL_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "guild_spy": (
            Ability(
                timing=AbilityTiming.TRIGGERED,
                sections=(),
                mark=AbilityMark.AUTOMATIC,
                hook="guild_spy",
            )
        ),
    }
)
