"""The Immortality tracks' printed bonuses and Reclaimed Forces as ability
records (composed effects, A7c).

docs/composed-effects-plan.md 5 (A7c): each research space prints a bonus
its reacher takes [Immortality pp. 3, 6, 16], keyed by space id, and four
Tleilaxu track spaces print a reward [Immortality pp. 4, 7], keyed by
space; Reclaimed Forces prints "choose one: recruit two troops, or advance
Tleilaxu once" [Immortality p. 9]. ``content.immortality.board`` checks the
track records on load and compiles the research records back into
``ResearchBonus``, which ``rules.immortality`` reads (the bonuses' order of
resolution stays theirs: a specimen before the trash, the Intrigue card
before the card); the Tleilaxu track and Reclaimed Forces are read from the
records themselves (cleanup 2e), ``TleilaxuBonus`` staying only as the
board's label key. The rules around them -- the move, the windows, the
Tleilaxu loop and end, the held draws -- stay engine code.
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
    AdvanceTleilaxu,
    Cost,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    PayResources,
    RecruitTroops,
    Research,
    Reward,
    TakeSetupSpice,
    TrashIntrigueCard,
    TrashPersonalCard,
)


def _icons(*rewards: Reward) -> Ability:
    """A space's printed icons, one line each, taken without a choice."""

    return Ability(
        timing=AbilityTiming.TRACK_SPACE,
        sections=tuple(EffectSection(rewards=(reward,)) for reward in rewards),
        mark=AbilityMark.AUTOMATIC,
        structure=(
            AbilityStructure.SEPARATE if len(rewards) > 1 else AbilityStructure.SEQUENCE
        ),
    )


def _arrow(cost: Cost, *rewards: Reward) -> Ability:
    """An optional arrow: its cost buys its rewards."""

    return Ability(
        timing=AbilityTiming.TRACK_SPACE,
        sections=(EffectSection(rewards=rewards, costs=(cost,)),),
        mark=AbilityMark.OPTIONAL,
    )


_SPECIMEN: Final = _icons(GenerateSpecimens(1))
_TLEILAXU: Final = _icons(AdvanceTleilaxu(1))
_RESEARCH: Final = _icons(Research())
# The black trash icon is optional [Main p. 20]; the specimen is not.
_TRASH_AND_SPECIMEN: Final = _icons(TrashPersonalCard(), GenerateSpecimens(1))

RESEARCH_SPACE_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # The start space (c0r3) prints nothing.
        "c1r3": _SPECIMEN,
        "c2r2": _SPECIMEN,
        "c2r4": _TLEILAXU,
        # Another research icon: advance again at once [Immortality p. 6].
        "c3r1": _RESEARCH,
        "c3r3": _TRASH_AND_SPECIMEN,
        "c3r5": _icons(AdvanceTleilaxu(1), GenerateSpecimens(1)),
        "c4r2": _TLEILAXU,
        "c4r4": _SPECIMEN,
        "c4r6": _RESEARCH,
        "c5r1": _RESEARCH,
        "c5r3": _SPECIMEN,
        "c5r5": _icons(GainResources(solari=1)),
        "c6r2": _icons(GainResources(spice=1)),
        "c6r4": _TLEILAXU,
        # One Influence of the owner's choice (OQ-060).
        "c6r6": Ability(
            timing=AbilityTiming.TRACK_SPACE,
            sections=(EffectSection(rewards=(GainInfluence(),)),),
        ),
        "c7r1": _TLEILAXU,
        # "[Trash an Intrigue card] -> draw a card, Intrigue card"
        # [Immortality p. 16] (OQ-061).
        "c7r3": _arrow(TrashIntrigueCard(), DrawPersonalCards(1), DrawIntrigueCards(1)),
        "c7r5": _TRASH_AND_SPECIMEN,
        "c8r2": _icons(GainResources(spice=2)),
        "c8r4": _TLEILAXU,
        # "7 Solari -> two Tleilaxu advances" (withheld at the track end,
        # OQ-071).
        "c8r6": _arrow(PayResources(solari=7), AdvanceTleilaxu(2)),
    }
)

TLEILAXU_SPACE_ABILITIES: Final[Mapping[int, Ability]] = MappingProxyType(
    {
        # An Intrigue card, held as the owner's own step in their turn
        # (OQ-106).
        2: _icons(DrawIntrigueCards(1)),
        # "Each player gains a Victory Point when they reach this space. The
        # first player to reach it takes an additional bonus: the 2 spice
        # that was placed here during setup" [Immortality p. 7].
        4: _icons(GainVictoryPoints(1), TakeSetupSpice()),
        6: _icons(DrawIntrigueCards(1)),
        7: _icons(GainVictoryPoints(1)),
    }
)

# Reclaimed Forces: "choose one" -- the Tleilaxu advance withheld at the
# track end (OQ-071); the card stays in the Row (OQ-066).
RECLAIMED_FORCES_ABILITY: Final = Ability(
    timing=AbilityTiming.ACQUIRE,
    sections=(
        EffectSection(rewards=(RecruitTroops(2),)),
        EffectSection(rewards=(AdvanceTleilaxu(1),)),
    ),
    structure=AbilityStructure.ONE_OF,
)
