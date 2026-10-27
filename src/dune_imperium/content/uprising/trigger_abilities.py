"""Trigger ability records of personal cards (composed effects, A4a, A4h).

docs/composed-effects-plan.md 5 (A4a): a personal card's "when acquired",
"when trashed" and "when discarded" boxes are written here as automatic
ability records, keyed by the card's ``acquisition_effect`` /
``trash_effect`` / ``discard_effect`` value; the printed text is
``display/tokens.py`` (``ACQUISITION_EFFECT_TEXT``, ``TRASH_EFFECT_TEXT``,
``DISCARD_EFFECT_TEXT``). None of them offers a choice: the box pays when it
fires.

- An acquire box is paid by ``rules.acquisition`` in three pieces whose order
  each purchase path keeps as it was: the owner's gains and Overthrow's draw
  (``resolve_acquisition_bonus``), a fixed Faction's Influence, and the token
  tracks after the card has reached its zone; a Spy or a Contract is left to
  the path, which opens its choice.
- A trash box is paid inside ``rules.card_trash.trash_personal_card``,
  whatever trashed the card; a discard box by
  ``rules.card_discard.resolve_personal_card_discard_trigger`` (a deck
  discard included, OQ-013).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireBankCommander,
    AdvanceTleilaxu,
    DrawIntrigueCards,
    EffectSection,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecruitTroops,
    Research,
    Reward,
    TakeContract,
)
from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardTrashEffect,
    PersonalCardTurnStartEffect,
)

_ACQUIRE = PersonalCardAcquisitionEffect
_TRASH = PersonalCardTrashEffect
_DISCARD = PersonalCardDiscardEffect
_GUILD_SPY = (
    PersonalCardRevealAcquisitionEffect.GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
)


def _when(timing: AbilityTiming, *rewards: Reward) -> Ability:
    """A box paid as it fires: its rewards on one line, nothing to choose."""

    return Ability(
        timing=timing,
        sections=(EffectSection(rewards=rewards),),
        mark=AbilityMark.AUTOMATIC,
    )


ACQUISITION_ABILITIES: Final[Mapping[PersonalCardAcquisitionEffect, Ability]] = (
    MappingProxyType(
        {
            # Overthrow: its own step right after the purchase inside the
            # seat's turn (OQ-106, OQ-042).
            _ACQUIRE.DRAW_INTRIGUE_CARD: _when(
                AbilityTiming.ACQUIRE, DrawIntrigueCards(1)
            ),
            # Price is No Object, Corrino Genes.
            _ACQUIRE.GAIN_TWO_SOLARI: _when(
                AbilityTiming.ACQUIRE, GainResources(solari=2)
            ),
            # Guild Spy, In High Places, Spy Network, Strike Fleet, Subversive
            # Advisor, Intelligence Training: the path opens the Spy's choice.
            _ACQUIRE.PLACE_SPY: _when(AbilityTiming.ACQUIRE, PlaceSpy()),
            # Steersman.
            _ACQUIRE.GAIN_SPACING_GUILD_INFLUENCE: _when(
                AbilityTiming.ACQUIRE,
                GainInfluence(factions=(Faction.SPACING_GUILD,)),
            ),
            # Interstellar Trade, Mercantile Affairs: the path opens the
            # Contract market.
            _ACQUIRE.TAKE_CONTRACT: _when(AbilityTiming.ACQUIRE, TakeContract(1)),
            # Arrakis Revolt.
            _ACQUIRE.RECRUIT_ONE_TROOP: _when(AbilityTiming.ACQUIRE, RecruitTroops(1)),
            # Imperial Throneship.
            _ACQUIRE.GAIN_EMPEROR_INFLUENCE: _when(
                AbilityTiming.ACQUIRE, GainInfluence(factions=(Faction.EMPEROR,))
            ),
            # Possible Futures.
            _ACQUIRE.GAIN_ONE_WATER: _when(
                AbilityTiming.ACQUIRE, GainResources(water=1)
            ),
            # Spiritual Fervor.
            _ACQUIRE.RESEARCH: _when(AbilityTiming.ACQUIRE, Research()),
            # Subject X-137.
            _ACQUIRE.ADVANCE_TLEILAXU: _when(AbilityTiming.ACQUIRE, AdvanceTleilaxu(1)),
            # Lisan al Gaib.
            _ACQUIRE.GAIN_ONE_SPICE: _when(
                AbilityTiming.ACQUIRE, GainResources(spice=1)
            ),
            # Occupation.
            _ACQUIRE.RECRUIT_THREE_TROOPS: _when(
                AbilityTiming.ACQUIRE, RecruitTroops(3)
            ),
        }
    )
)

TRASH_ABILITIES: Final[Mapping[PersonalCardTrashEffect, Ability]] = MappingProxyType(
    {
        # Sardaukar Soldier: a free-order step inside the seat's turn (OQ-106).
        _TRASH.DRAW_INTRIGUE_CARD: _when(AbilityTiming.TRASH, DrawIntrigueCards(1)),
        # Eliminate Allies.
        _TRASH.RECRUIT_TWO_TROOPS: _when(AbilityTiming.TRASH, RecruitTroops(2)),
        # Sardaukar Standard.
        _TRASH.ACQUIRE_BANK_COMMANDER: _when(
            AbilityTiming.TRASH, AcquireBankCommander()
        ),
        # Replacement Eyes.
        _TRASH.ADVANCE_TLEILAXU: _when(AbilityTiming.TRASH, AdvanceTleilaxu(1)),
        # Assassination Mission (original game): 4 Solari.
        _TRASH.GAIN_FOUR_SOLARI: _when(AbilityTiming.TRASH, GainResources(solari=4)),
    }
)

DISCARD_ABILITIES: Final[Mapping[PersonalCardDiscardEffect, Ability]] = (
    MappingProxyType(
        {
            # Spacing Guild's Favor.
            _DISCARD.GAIN_TWO_SPICE: _when(
                AbilityTiming.DISCARD, GainResources(spice=2)
            ),
            # Corrupt Bureaucrat.
            _DISCARD.GAIN_THREE_SOLARI: _when(
                AbilityTiming.DISCARD, GainResources(solari=3)
            ),
        }
    )
)


# The two personal-card boxes whose flow stays code (composed A4h), with no
# line: the DSL cannot say them whole. Guild Spy: "Gain 1 Influence with each
# Faction you are spying on" once The Spice Must Flow is acquired during the
# owner's Reveal, once per copy, Spies counted then (OQ-057 designer rulings;
# ``reveal_turn.fire_guild_spy_on_spice_must_flow``). Litany Against Fear:
# "Put this card into play -> Draw 1 card and pass your turn", only as the
# turn's first action (OQ-095 (6); ``agent_turn``).
REVEAL_ACQUISITION_ABILITIES: Final[
    Mapping[PersonalCardRevealAcquisitionEffect, Ability]
] = MappingProxyType(
    {
        _GUILD_SPY: (
            Ability(
                timing=AbilityTiming.TRIGGERED,
                sections=(),
                mark=AbilityMark.AUTOMATIC,
                hook="guild_spy",
            )
        ),
    }
)
TURN_START_ABILITIES: Final[Mapping[PersonalCardTurnStartEffect, Ability]] = (
    MappingProxyType(
        {
            PersonalCardTurnStartEffect.PLAY_TO_DRAW_AND_PASS: Ability(
                timing=AbilityTiming.TURN_START,
                sections=(),
                mark=AbilityMark.OPTIONAL,
                hook="litany_against_fear",
            ),
        }
    )
)


def acquisition_ability(
    effect: PersonalCardAcquisitionEffect | None,
) -> Ability | None:
    """The record of a card's acquire box, if it has one."""

    return None if effect is None else ACQUISITION_ABILITIES[effect]


def trash_ability(effect: PersonalCardTrashEffect | None) -> Ability | None:
    """The record of a card's trash box, if it has one."""

    return None if effect is None else TRASH_ABILITIES[effect]


def discard_ability(effect: PersonalCardDiscardEffect | None) -> Ability | None:
    """The record of a card's discard box, if it has one."""

    return None if effect is None else DISCARD_ABILITIES[effect]


def single_resource(reward: GainResources) -> tuple[str, int]:
    """The one resource a trigger's gain prints, with its amount (its event
    names it): every acquire and discard box gains a single kind."""

    gained = [
        (name, amount)
        for name, amount in (
            ("solari", reward.solari),
            ("spice", reward.spice),
            ("water", reward.water),
        )
        if amount
    ]
    if len(gained) != 1:
        raise ValueError(f"{reward!r} does not gain a single resource")
    return gained[0]
