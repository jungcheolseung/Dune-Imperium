"""The original board's printed icons as ability records.

Written like Uprising's (``content.uprising.board_abilities``): keyed by
(space id, cost option, variant), one line per printed icon, each resolved
on its own [DI p. 9] (OQ-027). The Faction spaces' Influence comes from the
space's icon itself, not a line. Arrakeen, Imperial Basin and Secrets are
Uprising's records. The values are docs/rules/imperium-base.md 8's table
[DI pp. 17-18] and the Steam app's ``SpaceArchetypes.BaseSet`` (Sell Melange's
Solari per spice, docs/base-game-and-ix-plan.md 15.3).

- Mentat: "Draw a card. If the Mentat is here, take it" [DI p. 18]; the take
  is its own icon, offered only while the Mentat rests on the space.
- Foldspace: Foldspace acquires a Foldspace card from the Reserve [DI p. 17].
- High Council and Swordmaster: "only once per game" [DI pp. 17-18]; a seated
  or Swordmaster-holding seat cannot send an Agent there.
- Selective Breeding: "Trash one card to draw two cards" [DI p. 18] -- the
  trash is the arrow's cost, never forced [DI p. 9], and the two cards are
  its own step after it (OQ-106): the line's record is a choice, and the
  draw a gain it arms (``rules.board_effects``).
- Hall of Oratory: its Reveal-turn Persuasion "if you have an Agent here"
  [DI p. 17] is read by the Reveal turn (``rules.reveal_turn``).
- The two Maker spaces of its own are the Maker flow without sandworms
  (``maker``), like Imperial Basin.
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
    AcquireReserveCard,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainResources,
    RecruitTroops,
    Reward,
    TakeHighCouncilSeat,
    TakeMentat,
    TakeSwordmaster,
    TrashCard,
)


def _icons(*rewards: Reward) -> Ability:
    """A space's printed icons, one line each."""

    return Ability(
        timing=AbilityTiming.BOARD_SPACE,
        sections=tuple(EffectSection(rewards=(reward,)) for reward in rewards),
        mark=AbilityMark.AUTOMATIC,
        structure=(
            AbilityStructure.SEPARATE if len(rewards) > 1 else AbilityStructure.SEQUENCE
        ),
    )


# Sell Melange: spice 2, 3, 4 or 5 for 6, 8, 10 or 12 Solari (cost options
# 0-3 of ``content.imperium.board``).
_SELL_MELANGE_SOLARI: Final = (6, 8, 10, 12)

IMPERIUM_BOARD_SPACE_ABILITIES: Final[Mapping[tuple[str, int, str], Ability]] = (
    MappingProxyType(
        {
            ("conspire", 0, ""): _icons(
                GainResources(solari=5), RecruitTroops(2), DrawIntrigueCards(1)
            ),
            ("wealth", 0, ""): _icons(GainResources(solari=2)),
            ("imperium_heighliner", 0, ""): _icons(
                RecruitTroops(5), GainResources(water=2)
            ),
            ("foldspace", 0, ""): _icons(AcquireReserveCard("foldspace_card")),
            # The two cards its trash buys (``IMPERIUM_BOARD_CHOICE_ABILITIES``).
            ("selective_breeding", 0, ""): _icons(DrawPersonalCards(2)),
            ("hardy_warriors", 0, ""): _icons(RecruitTroops(2)),
            ("stillsuits", 0, ""): _icons(GainResources(water=1)),
            ("hall_of_oratory", 0, ""): _icons(RecruitTroops(1)),
            ("rally_troops", 0, ""): _icons(RecruitTroops(4)),
            ("mentat", 0, ""): _icons(DrawPersonalCards(1), TakeMentat()),
            ("imperium_swordmaster", 0, ""): _icons(TakeSwordmaster()),
            ("imperium_high_council", 0, ""): _icons(TakeHighCouncilSeat()),
            ("carthag", 0, ""): _icons(RecruitTroops(1), DrawIntrigueCards(1)),
            # "Draw three cards" one at a time, three icons, each its own step
            # in the owner's order: user ruling 2026-10-29 "연구 기지는 한 장씩
            # 뽑아야지" (the app lists the space's DrawAbility three times;
            # plan 16.12, OQ-147).
            ("imperium_research_station", 0, ""): _icons(
                DrawPersonalCards(1), DrawPersonalCards(1), DrawPersonalCards(1)
            ),
            ("imperium_sietch_tabr", 0, ""): _icons(
                RecruitTroops(1), GainResources(water=1)
            ),
            ("secure_contract", 0, ""): _icons(GainResources(solari=3)),
            **{
                ("sell_melange", option, ""): _icons(GainResources(solari=solari))
                for option, solari in enumerate(_SELL_MELANGE_SOLARI)
            },
        }
    )
)


def _choice(
    *lines: EffectSection, mark: AbilityMark, hook: str | None = None
) -> Ability:
    return Ability(
        timing=AbilityTiming.BOARD_SPACE, sections=lines, mark=mark, hook=hook
    )


IMPERIUM_BOARD_CHOICE_ABILITIES: Final[Mapping[tuple[str, str], Ability]] = (
    MappingProxyType(
        {
            # Selective Breeding: "Trash one card to draw two cards".
            ("selective_breeding", "trash"): _choice(
                EffectSection(rewards=(DrawPersonalCards(2),), costs=(TrashCard(),)),
                mark=AbilityMark.OPTIONAL,
            ),
            # The Maker spaces: "Take all bonus spice here", then the printed
            # spice [DI p. 17] [FAQ p. 1] (no sandworm: the original board
            # prints none); ``board_effects.MAKER_BASE_SPICE`` pays the line.
            ("imperium_hagga_basin", "maker"): _choice(
                EffectSection(rewards=(GainResources(spice=2),)),
                mark=AbilityMark.MANDATORY,
                hook="maker",
            ),
            ("the_great_flat", "maker"): _choice(
                EffectSection(rewards=(GainResources(spice=3),)),
                mark=AbilityMark.MANDATORY,
                hook="maker",
            ),
        }
    )
)
