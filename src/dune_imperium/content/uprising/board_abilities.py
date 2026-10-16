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
icon keys of their own. The spaces resolved by their own choice (Sietch
Tabr, the Maker spaces, Tuek's Sietch) and the choice icons beside these
lines (Espionage's Spy, Desert Tactics' trash, Shipping's Influence,
Imperial Privilege's recall and trade, Secrets' steal) are
``BOARD_CHOICE_ABILITIES``, flows kept as code (A5d). The printed text is
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
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecruitTroops,
    Research,
    Reward,
    TakeContract,
    TakeHighCouncilSeat,
    TakeSwordmaster,
    TrashIntrigueCard,
    TrashPersonalCard,
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


BOARD_SPACE_ABILITIES: Final[Mapping[tuple[str, int, str], Ability]] = MappingProxyType(
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


def _choice(*lines: EffectSection, mark: AbilityMark, hook: str) -> Ability:
    return Ability(
        timing=AbilityTiming.BOARD_SPACE, sections=lines, mark=mark, hook=hook
    )


# The spaces' choice icons and special flows, keyed by (space id, icon key)
# (composed A5d). Each keeps its flow as code in ``rules.board_effects``
# (``BOARD_SPACE_HOOKS``): their rows match shared shapes, but each handler
# names its events its own way -- left for the cleanup stage, which unifies
# the events. A record lists its line only where the DSL can say the whole
# icon (the A3g rule); its mark matches ``effects.OPTIONAL_BOARD_ICONS``.
BOARD_CHOICE_ABILITIES: Final[Mapping[tuple[str, str], Ability]] = MappingProxyType(
    {
        # Espionage: "Place a Spy" -- mandatory with a Spy in supply,
        # recall-first otherwise (OQ-057 (14)).
        ("espionage", "spy"): _choice(
            EffectSection(rewards=(PlaceSpy(),)),
            mark=AbilityMark.MANDATORY,
            hook="espionage_spy",
        ),
        # Desert Tactics: "You may trash a card".
        ("desert_tactics", "trash"): _choice(
            EffectSection(rewards=(TrashPersonalCard(),)),
            mark=AbilityMark.OPTIONAL,
            hook="desert_tactics_trash",
        ),
        # Shipping: "Gain 1 Influence with a Faction of your choice".
        ("shipping", "influence"): _choice(
            EffectSection(rewards=(GainInfluence(),)),
            mark=AbilityMark.MANDATORY,
            hook="shipping_influence",
        ),
        # Imperial Privilege: "You may trash an Intrigue card -> Draw 1
        # Intrigue card", its own icon beside the recall (OQ-027 (d)).
        ("imperial_privilege", "imperial_privilege_intrigue"): _choice(
            EffectSection(
                rewards=(DrawIntrigueCards(1),), costs=(TrashIntrigueCard(),)
            ),
            mark=AbilityMark.OPTIONAL,
            hook="imperial_privilege_trade",
        ),
        # Imperial Privilege: "Recall one of your other Agents" -- a
        # Conflict Agent too (OQ-068's sibling), which no piece says.
        ("imperial_privilege", "imperial_privilege"): _choice(
            mark=AbilityMark.MANDATORY, hook="imperial_privilege_recall"
        ),
        # Sietch Tabr: "Choose one: take the Maker Hooks token (if you lack
        # it), Recruit 1 troop and Gain 1 water -- or Gain 1 water,
        # optionally destroying the Shield Wall".
        ("sietch_tabr", "sietch_tabr"): _choice(
            mark=AbilityMark.MANDATORY, hook="sietch_tabr"
        ),
        # The Maker spaces: "Take all bonus spice here, then choose: Gain N
        # spice -- or, with Maker Hooks, summon sandworms into the
        # Conflict" (Imperial Basin: the spice alone).
        ("deep_desert", "maker"): _choice(mark=AbilityMark.MANDATORY, hook="maker"),
        ("hagga_basin", "maker"): _choice(mark=AbilityMark.MANDATORY, hook="maker"),
        ("imperial_basin", "maker"): _choice(mark=AbilityMark.MANDATORY, hook="maker"),
        # Tuek's Sietch (Esmar Tuek's Maker space): "Take all bonus spice
        # here, then choose: Gain 1 spice -- or Draw 1 card".
        ("tuek_sietch", "tuek_sietch"): _choice(
            mark=AbilityMark.MANDATORY, hook="tuek_sietch"
        ),
        # Secrets: "Each opponent holding 4 or more Intrigue cards gives you
        # one at random", the text after its Intrigue draw (OQ-027).
        ("secrets", "intrigue"): _choice(
            mark=AbilityMark.AUTOMATIC, hook="secrets_steal"
        ),
    }
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
