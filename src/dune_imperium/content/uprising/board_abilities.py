"""Board spaces' printed icons as ability records (composed effects, A5c).

docs/composed-effects-plan.md 5 (A5c): what each board space gives when an
Agent is sent there is written here, keyed by (space id, cost option,
variant), one line per printed icon, each resolved on its own [Main p. 9]
(OQ-027). The variants are the printed alternatives a module or the visitor
selects: ``no_choam`` (Dutiful Service and Accept Contract print 2 Solari
where the CHOAM module's Contract icon stands), ``immortality`` (the
Research Station overlay) and ``seated`` (High Council once the visitor's
Councilor is seated). ``rules.board_effects`` reads the gains
(``static_board_effects``); the seat, the Swordmaster and the Contract are
icon keys of their own. Spaces resolved by their own choice (Sietch Tabr,
the Maker spaces, Tuek's Sietch) and the choice icons beside these lines
(Espionage's Spy, Desert Tactics' trash, Shipping's Influence, Imperial
Privilege's recall and trade) keep their code for now. The printed text is
``display/spaces.py``.
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
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainResources,
    RecruitTroops,
    Research,
    Reward,
    TakeContract,
    TakeHighCouncilSeat,
    TakeSwordmaster,
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


BOARD_SPACE_ABILITIES: Final[Mapping[tuple[str, int, str], Ability]] = (
    MappingProxyType(
        {
            # Dutiful Service: the Contract icon, 2 Solari without CHOAM.
            ("dutiful_service", 0, ""): _icons(TakeContract(1)),
            ("dutiful_service", 0, "no_choam"): _icons(GainResources(solari=2)),
            ("sardaukar", 0, ""): _icons(DrawIntrigueCards(1), RecruitTroops(4)),
            ("deliver_supplies", 0, ""): _icons(GainResources(water=1)),
            ("heighliner", 0, ""): _icons(RecruitTroops(5)),
            # Espionage: the draw beside its optional Spy (its own icon).
            ("espionage", 0, ""): _icons(DrawPersonalCards(1)),
            ("fremkit", 0, ""): _icons(DrawPersonalCards(1)),
            # Desert Tactics: the troop beside its optional trash.
            ("desert_tactics", 0, ""): _icons(RecruitTroops(1)),
            ("assembly_hall", 0, ""): _icons(DrawIntrigueCards(1)),
            # Secrets: the draw, then the steal printed after it (OQ-027).
            ("secrets", 0, ""): _icons(DrawIntrigueCards(1)),
            # High Council: the first visit seats the Councilor; later visits
            # "Gain 2 spice, Draw 1 Intrigue card, Recruit 3 troops".
            ("high_council", 0, ""): _icons(TakeHighCouncilSeat()),
            ("high_council", 0, "seated"): _icons(
                GainResources(spice=2), DrawIntrigueCards(1), RecruitTroops(3)
            ),
            # Swordmaster: two printed costs, one effect.
            ("swordmaster", 0, ""): _icons(TakeSwordmaster()),
            ("swordmaster", 1, ""): _icons(TakeSwordmaster()),
            ("arrakeen", 0, ""): _icons(RecruitTroops(1), DrawPersonalCards(1)),
            ("gather_support", 0, ""): _icons(RecruitTroops(2)),
            ("gather_support", 1, ""): _icons(RecruitTroops(2), GainResources(water=1)),
            ("research_station", 0, ""): _icons(RecruitTroops(2), DrawPersonalCards(2)),
            # The Research Station overlay: "Draw two cards and research"
            # [Immortality pp. 5, 16] [Main p. 18].
            ("research_station", 0, "immortality"): _icons(
                DrawPersonalCards(2), Research()
            ),
            ("spice_refinery", 0, ""): _icons(GainResources(solari=2)),
            ("spice_refinery", 1, ""): _icons(GainResources(solari=4)),
            # Shipping: the Solari beside its chosen Influence.
            ("shipping", 0, ""): _icons(GainResources(solari=5)),
            ("accept_contract", 0, ""): _icons(DrawPersonalCards(1), TakeContract(1)),
            ("accept_contract", 0, "no_choam"): _icons(
                DrawPersonalCards(1), GainResources(solari=2)
            ),
            # Imperial Privilege: "Recall one of your other Agents from the
            # board, and draw a card" -- the draw its own icon (OQ-027 (d)).
            ("imperial_privilege", 0, ""): _icons(DrawPersonalCards(1)),
        }
    )
)


def board_space_ability(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
    immortality: bool,
    seated: bool = False,
) -> Ability | None:
    """The record of one visit's printed icons, the printed alternative the
    modules and the visitor select first; None for a space resolved by its
    own choice."""

    for variant, applies in (
        ("no_choam", not choam_module),
        ("immortality", immortality),
        ("seated", seated),
    ):
        if applies and (space_id, cost_option, variant) in BOARD_SPACE_ABILITIES:
            return BOARD_SPACE_ABILITIES[space_id, cost_option, variant]
    return BOARD_SPACE_ABILITIES.get((space_id, cost_option, ""))
