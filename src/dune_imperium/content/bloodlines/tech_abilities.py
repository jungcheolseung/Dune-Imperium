"""Tech tiles' acquire effects as ability records (composed effects, A6a).

docs/composed-effects-plan.md 5 (A6a): what a Tech tile gives when it is
acquired [Bloodlines p. 7] is written here, keyed by tile id, one line per
printed icon; each icon is resolved on its own in the owner's order
(OQ-098). ``content.bloodlines.tech`` compiles the records back into the
``TechTile`` acquire fields, which ``rules.tech`` reads unchanged. Advanced
Data Analysis prints a purchase prerequisite instead -- "To acquire this,
you must trash one of your Spies from the board (return it to the box)" --
a hook record whose flow stays in ``rules.tech``.

Each tile's printed ability is ``TECH_ABILITIES`` (composed A6b), keyed by
tile id: the Flip lines (``rules.tech`` offers and resolves them from the
records), the automatic Reveal Turn lines (``tech.tech_reveal_line``,
which the Reveal reads), the Endgame lines
(``rules.tech.apply_endgame_tech_effects``); the flows kept as code are hook
records (``rules.tech.TECH_HOOKS``), lines listed only where the DSL says
the whole ability, and the rule changes in force while the tile is held are
``STANDING`` records naming the engine branch. The printed text is
``display/bloodlines.py``.
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
    CommandReached,
    CompletedContractsAtLeast,
    DestroyShieldWall,
    DrawIntrigueCards,
    DrawPersonalCards,
    DuringAgentTurn,
    EffectSection,
    GainInfluence,
    GainInfluenceWhereAtMost,
    GainResources,
    GainVictoryPoints,
    GrantCombatDeployment,
    OnConflictWon,
    OnContractCompleted,
    PlaceSpy,
    RecruitTroops,
    RevealPersuasion,
    RevealSwords,
    Reward,
    SpyRecalledThisTurn,
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


def _flip(*lines: EffectSection, requirement: DuringAgentTurn | None = None) -> Ability:
    """A Flip ability: once a round, in one of the owner's turns."""

    return Ability(
        timing=AbilityTiming.FLIP,
        sections=lines,
        mark=AbilityMark.OPTIONAL,
        requirement=requirement,
    )


def _automatic(timing: AbilityTiming, line: EffectSection) -> Ability:
    return Ability(timing=timing, sections=(line,), mark=AbilityMark.AUTOMATIC)


def _hook(
    timing: AbilityTiming,
    hook: str,
    *lines: EffectSection,
    mark: AbilityMark = AbilityMark.AUTOMATIC,
) -> Ability:
    return Ability(
        timing=timing,
        sections=lines,
        mark=mark,
        structure=(
            AbilityStructure.SEPARATE if len(lines) > 1 else AbilityStructure.SEQUENCE
        ),
        hook=hook,
    )


def _drawn_on(trigger: OnContractCompleted | OnConflictWon) -> Ability:
    """A tile's trigger drawing one card, owed to the engine's post-step
    draw or held as the owner's own step (OQ-106)."""

    return Ability(
        timing=AbilityTiming.TRIGGERED,
        sections=(EffectSection(rewards=(DrawPersonalCards(1),)),),
        mark=AbilityMark.AUTOMATIC,
        trigger=trigger,
    )


def _standing(hook: str) -> Ability:
    return Ability(
        timing=AbilityTiming.STANDING,
        sections=(),
        mark=AbilityMark.AUTOMATIC,
        hook=hook,
    )


TECH_ABILITIES: Final[Mapping[str, tuple[Ability, ...]]] = MappingProxyType(
    {
        # "Flip -> Draw 1 Intrigue card".
        "advanced_data_analysis": (
            _flip(EffectSection(rewards=(DrawIntrigueCards(1),))),
        ),
        # "When you complete a contract: Draw 1 card" (a held immediate draw
        # in the owner's turn, owed otherwise, ``rules.contract_tiles``).
        # "Endgame: 1 VP if you have completed four or more contracts"
        # (OQ-040).
        "choam_transports": (
            _drawn_on(OnContractCompleted()),
            _automatic(
                AbilityTiming.ENDGAME,
                EffectSection(
                    rewards=(GainVictoryPoints(1),),
                    condition=CompletedContractsAtLeast(4),
                ),
            ),
        ),
        # "Reveal Turn: Command (6+): Gain 2 solari".
        "delivery_bay": (
            _automatic(
                AbilityTiming.REVEAL,
                EffectSection(
                    rewards=(GainResources(solari=2),), condition=CommandReached()
                ),
            ),
        ),
        # "You must choose: +3 swords and lose 1 Influence -OR- lose all your
        # spice and trash this" (OQ-044 (a)): no piece loses all spice.
        "forbidden_weapons": (
            _hook(
                AbilityTiming.REVEAL, "forbidden_weapons", mark=AbilityMark.MANDATORY
            ),
        ),
        "gene_locked_vault": (_standing("gene_locked_vault"),),
        "glowglobes": (_standing("glowglobes"),),
        # OQ-104: the discount is mandatory and paid with the space's cost.
        "navigation_chamber": (_standing("navigation_chamber"),),
        "ornithopter_fleet": (_standing("ornithopter_fleet"),),
        # "Reveal Turn: Place a Spy, Gain 1 troop" -- each waits for the
        # owner's order on the Reveal (OQ-044, OQ-045). "Endgame: Gain 1
        # Influence with each Faction where you have 1 or less Influence".
        "panopticon": (
            _hook(
                AbilityTiming.REVEAL,
                "panopticon_reveal",
                EffectSection(rewards=(PlaceSpy(),)),
                EffectSection(rewards=(RecruitTroops(1),)),
                mark=AbilityMark.MANDATORY,
            ),
            _automatic(
                AbilityTiming.ENDGAME,
                EffectSection(rewards=(GainInfluenceWhereAtMost(1),)),
            ),
        ),
        # "When you win a Conflict: Draw 1 card" (the sole winner).
        "planetary_array": (_drawn_on(OnConflictWon()),),
        # "Whenever you recruit a Sardaukar Commander: Trash this -> Gain an
        # additional Sardaukar Commander Skill" (OQ-044 (c)).
        "plasteel_blades": (
            _hook(
                AbilityTiming.TRIGGERED, "plasteel_blades", mark=AbilityMark.OPTIONAL
            ),
        ),
        # "Agent Turn: Flip -> Combat icon".
        "rapid_dropships": (
            _flip(
                EffectSection(rewards=(GrantCombatDeployment(),)),
                requirement=DuringAgentTurn(),
            ),
        ),
        "sardaukar_high_command": (_standing("sardaukar_high_command"),),
        # "Reveal Turn: +1 Persuasion".
        "self_destroying_messages": (
            _automatic(
                AbilityTiming.REVEAL, EffectSection(rewards=(RevealPersuasion(1),))
            ),
        ),
        "servo_receivers": (_standing("servo_receivers"),),
        # "Flip -> Gain 1 solari, and if you recalled a Spy this turn: trash a
        # card" (OQ-101).
        "spy_drones": (
            _flip(
                EffectSection(rewards=(GainResources(solari=1),)),
                EffectSection(
                    rewards=(TrashPersonalCard(),), condition=SpyRecalledThisTurn()
                ),
            ),
        ),
        # "For each Intrigue card you draw or steal during your turn: Gain 1
        # troop, deploy it to the Conflict" (OQ-042).
        "suspensor_suits": (_hook(AbilityTiming.TRIGGERED, "suspensor_suits"),),
        # "Reveal Turn: Command (6+): +2 swords".
        "training_depot": (
            _automatic(
                AbilityTiming.REVEAL,
                EffectSection(rewards=(RevealSwords(2),), condition=CommandReached()),
            ),
        ),
    }
)


def tech_draws_on(
    tech_ids: tuple[str, ...], kind: type[OnContractCompleted] | type[OnConflictWon]
) -> int:
    """Cards the held tiles draw when a ``kind`` trigger fires (CHOAM
    Transports, Planetary Array; composed A6e)."""

    return sum(
        reward.count
        for tech_id in tech_ids
        for record in TECH_ABILITIES[tech_id]
        if isinstance(record.trigger, kind)
        for line in record.sections
        for reward in line.rewards
        if isinstance(reward, DrawPersonalCards)
    )
