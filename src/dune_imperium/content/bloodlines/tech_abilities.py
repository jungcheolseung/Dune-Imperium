"""Tech tiles' acquire effects as ability records (composed effects, A6a).

docs/composed-effects-plan.md 5 (A6a): what a Tech tile gives when it is
acquired [Bloodlines p. 7] is written here, keyed by tile id, one line per
printed icon; each icon is resolved on its own in the owner's order
(OQ-098). ``content.bloodlines.tech`` compiles the records back into the
``TechTile`` acquire fields, which ``rules.tech`` reads unchanged. Advanced
Data Analysis prints a purchase prerequisite instead -- "To acquire this,
you must trash one of your Spies from the board (return it to the box)" --
a hook record whose flow stays in ``rules.tech``. The printed text is
``display/bloodlines.py``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import (
    DestroyShieldWall,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    PlaceSpy,
    RecruitTroops,
    Reward,
    TakeContract,
    TrashPersonalCard,
    UseSignetAbility,
)

# Advanced Data Analysis' prerequisite (``rules.tech`` checks and pays it
# with the purchase).
TRASH_SPY_TO_ACQUIRE: Final = "trash_spy_to_acquire"


def _icons(*rewards: Reward) -> Ability:
    """A tile's acquire icons, one line each."""

    return Ability(
        timing=AbilityTiming.ACQUIRE,
        sections=tuple(EffectSection(rewards=(reward,)) for reward in rewards),
        structure=(
            AbilityStructure.SEPARATE if len(rewards) > 1 else AbilityStructure.SEQUENCE
        ),
    )


TECH_ACQUIRE_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "advanced_data_analysis": Ability(
            timing=AbilityTiming.ACQUIRE, sections=(), hook=TRASH_SPY_TO_ACQUIRE
        ),
        "choam_transports": _icons(TakeContract(1)),
        "delivery_bay": _icons(DrawPersonalCards(1)),
        # Forbidden Weapons: a troop and the Shield Wall detonation icon,
        # which the owner may use [Main pp. 10, 20].
        "forbidden_weapons": _icons(RecruitTroops(1), DestroyShieldWall()),
        # Gene-Locked Vault: "an Intrigue card -OR- a drawn card".
        "gene_locked_vault": Ability(
            timing=AbilityTiming.ACQUIRE,
            sections=(
                EffectSection(rewards=(DrawIntrigueCards(1),)),
                EffectSection(rewards=(DrawPersonalCards(1),)),
            ),
            structure=AbilityStructure.ONE_OF,
        ),
        "glowglobes": _icons(GainInfluence()),
        "navigation_chamber": _icons(GainInfluence()),
        "ornithopter_fleet": _icons(RecruitTroops(2)),
        # Planetary Array: the black trash icon, optional [FAQ p. 3].
        "planetary_array": _icons(TrashPersonalCard()),
        "plasteel_blades": _icons(GainResources(solari=4)),
        "rapid_dropships": _icons(RecruitTroops(2)),
        "sardaukar_high_command": _icons(GainVictoryPoints(1)),
        "self_destroying_messages": _icons(DrawIntrigueCards(2)),
        # Servo-Receivers: the Signet Ring icon [Servo-Receivers Tech tile].
        "servo_receivers": _icons(UseSignetAbility()),
        # Spy Drones: two Spies with Deep Cover [Bloodlines p. 5].
        "spy_drones": _icons(PlaceSpy(shared_post=True), PlaceSpy(shared_post=True)),
    }
)
