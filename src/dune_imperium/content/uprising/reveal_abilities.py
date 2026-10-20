"""Reveal automatic gains of personal cards as ability records (composed effects, A4c).

docs/composed-effects-plan.md 5 (A4c): what a personal card gains on its own
when it is revealed -- the Reveal box's printed gains, their conditions and
the counts that multiply them -- is written here as automatic ability
records keyed by the card's definition id, one line per printed effect
(each judged on its own). ``rules.reveal_turn`` reads these lines
(``rules.reveal_lines``, stage B3e-2) and pays them: Persuasion and swords at
once, the other gains as the owner's own steps (OQ-045), a condition met
later in the turn paying then (``grant_late_reveal_effects``). The card
manifests take their compiled ``reveal_effects`` from them
(``reveal_effects_of``) for the card text and the action catalog. The printed text is
``display/tokens.reveal_effect_text``. A card's printed Reveal Persuasion and
swords (``reveal_persuasion``, ``reveal_strength``) are card values, not
abilities; its Reveal choices are A4d's.
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
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AllConditions,
    CommandersInConflictAtLeast,
    CommandReached,
    Condition,
    DrawIntrigueCards,
    EffectSection,
    FactionBond,
    GainInfluence,
    GainResources,
    GarrisonedUnitsAtLeast,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    GrantCombatDeployment,
    HasHighCouncil,
    HasSwordmaster,
    RecruitTroops,
    Research,
    RevealCount,
    RevealCountKind,
    RevealPersuasion,
    RevealSwords,
    Reward,
    SpiesPlacedAtLeast,
    SpyingOnMakerSpace,
    TrashThisCard,
)
from dune_imperium.content.uprising.types import (
    PersonalCardBond,
    PersonalCardRevealEffect,
)

_COMMAND = CommandReached()
_PER_COMPLETED_CONTRACT = RevealCount(RevealCountKind.COMPLETED_CONTRACT)
_PER_OTHER_SWORD_CARD = RevealCount(RevealCountKind.OTHER_SWORD_CARD)


def _revealed(faction: Faction) -> RevealCount:
    return RevealCount(RevealCountKind.REVEALED_FACTION_CARD, faction)


def _in_play(faction: Faction) -> RevealCount:
    return RevealCount(RevealCountKind.FACTION_CARD_IN_PLAY, faction)


def _line(*rewards: Reward, condition: Condition | None = None) -> EffectSection:
    return EffectSection(rewards=rewards, condition=condition)


def _reveal(*lines: EffectSection) -> Ability:
    """A Reveal box's automatic gains, each printed line on its own."""

    return Ability(
        timing=AbilityTiming.REVEAL,
        sections=lines,
        mark=AbilityMark.AUTOMATIC,
        structure=(
            AbilityStructure.SEPARATE if len(lines) > 1 else AbilityStructure.SEQUENCE
        ),
    )


REVEAL_GAIN_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Bene Gesserit Operative.
        "bene_gesserit_operative": _reveal(
            _line(RevealPersuasion(2), condition=SpiesPlacedAtLeast(2))
        ),
        # Chani, Clever Tactician.
        "chani_clever_tactician": _reveal(
            _line(RevealPersuasion(2), condition=FactionBond(Faction.FREMEN))
        ),
        # Delivery Agreement.
        "delivery_agreement": _reveal(_line(GainResources(spice=1))),
        # Ecological Testing Station.
        "ecological_testing_station": _reveal(
            _line(GainResources(water=1), condition=FactionBond(Faction.FREMEN))
        ),
        # Fedaykin Stilltent.
        "fedaykin_stilltent": _reveal(_line(GainResources(water=1))),
        # Interstellar Trade.
        "interstellar_trade": _reveal(
            _line(RevealPersuasion(1, per=_PER_COMPLETED_CONTRACT))
        ),
        # Junction Headquarters.
        "junction_headquarters": _reveal(
            _line(GainResources(water=1), RecruitTroops(1))
        ),
        # Leadership.
        "leadership": _reveal(_line(RevealSwords(1, per=_PER_OTHER_SWORD_CARD))),
        # Northern Watermaster.
        "northern_watermaster": _reveal(
            _line(GainResources(spice=2), condition=FactionBond(Faction.FREMEN))
        ),
        # Overthrow.
        "overthrow": _reveal(_line(RecruitTroops(1))),
        # Paracompass.
        "paracompass": _reveal(
            _line(RevealPersuasion(2), condition=HasHighCouncil()),
            _line(
                RevealPersuasion(1),
                condition=AllConditions((HasHighCouncil(), HasSwordmaster())),
            ),
        ),
        # Price is No Object.
        "price_is_no_object": _reveal(_line(GainResources(solari=2))),
        # Priority Contracts.
        "priority_contracts": _reveal(_line(GainResources(spice=2))),
        # Rebel Supplier.
        "rebel_supplier": _reveal(_line(GainResources(spice=1))),
        # Reliable Informant.
        "reliable_informant": _reveal(_line(GainResources(solari=1))),
        # Sardaukar Coordination.
        "sardaukar_coordination": _reveal(
            _line(RevealSwords(1, per=_revealed(Faction.EMPEROR)))
        ),
        # Shishakli.
        "shishakli": _reveal(
            _line(
                GainInfluence(factions=(Faction.FREMEN,)),
                condition=FactionBond(Faction.FREMEN),
            )
        ),
        # Smuggler's Haven.
        "smuggler_s_haven": _reveal(
            _line(GainResources(spice=2), condition=SpyingOnMakerSpace())
        ),
        # Southern Elders.
        "southern_elders": _reveal(
            _line(GainResources(water=1)),
            _line(RevealPersuasion(2), condition=FactionBond(Faction.FREMEN)),
        ),
        # Steersman.
        "steersman": _reveal(_line(GainResources(spice=2))),
        # Stilgar, The Devoted.
        "stilgar_the_devoted": _reveal(
            _line(RevealPersuasion(2, per=_in_play(Faction.FREMEN)))
        ),
        # Treacherous Maneuver.
        "treacherous_maneuver": _reveal(_line(DrawIntrigueCards(1))),
        # Unswerving Loyalty.
        "unswerving_loyalty": _reveal(_line(RecruitTroops(1))),
        # Ruthless Leadership.
        "ruthless_leadership": _reveal(
            _line(GrantCombatDeployment(), condition=_COMMAND)
        ),
        # Bombast.
        "bombast": _reveal(
            _line(GainResources(solari=3), TrashThisCard(), condition=_COMMAND)
        ),
        # Fremen War Name.
        "fremen_war_name": _reveal(
            _line(RevealSwords(2), condition=FactionBond(Faction.FREMEN))
        ),
        # Holy War.
        "holy_war": _reveal(
            _line(RevealPersuasion(1), RecruitTroops(1)),
            _line(GrantCombatDeployment(), condition=FactionBond(Faction.FREMEN)),
        ),
        # I Believe.
        "i_believe": _reveal(_line(RecruitTroops(2), condition=_COMMAND)),
        # Imperial Throneship.
        "imperial_throneship": _reveal(
            _line(
                RevealPersuasion(1),
                GainResources(solari=3),
                condition=GarrisonedUnitsAtLeast(4),
            )
        ),
        # Possible Futures.
        "possible_futures": _reveal(_line(GainResources(water=1))),
        # Quash Rebellion.
        "quash_rebellion": _reveal(
            _line(RevealPersuasion(2), condition=CommandersInConflictAtLeast(1))
        ),
        # Sandwalk.
        "sandwalk": _reveal(
            _line(RevealPersuasion(1), condition=FactionBond(Faction.FREMEN))
        ),
        # Sardaukar Standard.
        "sardaukar_standard": _reveal(_line(RecruitTroops(1))),
        # Southern Faith.
        "southern_faith": _reveal(_line(GainResources(spice=2), condition=_COMMAND)),
        # Bene Tleilax Lab.
        "bene_tleilax_lab": _reveal(
            _line(GainResources(spice=1), condition=GeneticMarkersAtLeast(1))
        ),
        # Bene Tleilax Researcher.
        "bene_tleilax_researcher": _reveal(
            _line(RevealPersuasion(1), condition=GeneticMarkersAtLeast(1)),
            _line(RevealPersuasion(1), condition=GeneticMarkersAtLeast(2)),
        ),
        # Dissecting Kit.
        "dissecting_kit": _reveal(
            _line(AdvanceTleilaxu(1), condition=GeneticMarkersAtLeast(1))
        ),
        # High Priority Travel.
        "high_priority_travel": _reveal(_line(GainResources(solari=1))),
        # Lisan al Gaib.
        "lisan_al_gaib": _reveal(
            _line(RevealSwords(2), condition=FactionBond(Faction.FREMEN))
        ),
        # Long Reach.
        "long_reach": _reveal(_line(DrawIntrigueCards(1))),
        # Occupation.
        "occupation": _reveal(_line(GainResources(spice=1, water=1), RecruitTroops(1))),
        # Organ Merchants.
        "organ_merchants": _reveal(_line(GainResources(solari=1))),
        # Spiritual Fervor.
        "spiritual_fervor": _reveal(_line(GenerateSpecimens(1))),
        # Stillsuit Manufacturer.
        "stillsuit_manufacturer": _reveal(
            _line(GainResources(spice=2), condition=FactionBond(Faction.FREMEN))
        ),
        # Throne Room Politics.
        "throne_room_politics": _reveal(
            _line(GainInfluence(factions=(Faction.BENE_GESSERIT,)))
        ),
        # Tleilaxu Master.
        "tleilaxu_master": _reveal(_line(Research(), Research())),
        # Experimentation.
        "experimentation": _reveal(_line(GenerateSpecimens(1))),
        # Control the Spice.
        "control_the_spice": _reveal(_line(GainResources(spice=1))),
        # The Spice Must Flow.
        "the_spice_must_flow": _reveal(_line(GainResources(spice=1))),
        # Twisted Mentat.
        "twisted_mentat": _reveal(_line(GenerateSpecimens(1))),
        # Usurp.
        "usurp": _reveal(_line(GenerateSpecimens(1))),
    }
)


def _bond(faction: Faction) -> PersonalCardBond:
    return PersonalCardBond(faction.value)


def _conditions(condition: Condition | None) -> tuple[Condition, ...]:
    if condition is None:
        return ()
    if isinstance(condition, AllConditions):
        return condition.conditions
    return (condition,)


def reveal_effect(line: EffectSection) -> PersonalCardRevealEffect:
    """One recorded line's compiled totals (``PersonalCardRevealEffect``),
    which the card text and the action catalog read; the Reveal turn reads
    the line itself (``rules.reveal_lines``, stage B3e-2)."""

    fields: dict[str, object] = {}
    for condition in _conditions(line.condition):
        match condition:
            case FactionBond(faction=faction):
                _set(fields, "required_faction_bond", _bond(faction))
            case HasHighCouncil():
                _set(fields, "requires_high_council", True)
            case HasSwordmaster():
                _set(fields, "requires_swordmaster", True)
            case SpiesPlacedAtLeast(count=count):
                _set(fields, "minimum_spies_placed", count)
            case SpyingOnMakerSpace():
                _set(fields, "requires_spying_on_maker_space", True)
            case CommandersInConflictAtLeast(count=1):
                _set(fields, "requires_commander_in_conflict", True)
            case GeneticMarkersAtLeast(count=count):
                _set(fields, "minimum_genetic_markers", count)
            case GarrisonedUnitsAtLeast(count=count):
                _set(fields, "minimum_garrisoned_units", count)
            case CommandReached():
                _set(fields, "requires_command", True)
            case _:
                raise TypeError(f"{condition!r} is not a Reveal gain condition")
    research = 0
    for reward in line.rewards:
        match reward:
            case RevealPersuasion(amount=amount, per=per):
                if per is None:
                    _set(fields, "persuasion", amount)
                elif per.kind is RevealCountKind.COMPLETED_CONTRACT:
                    _set(fields, "persuasion_per_completed_contract", amount)
                else:
                    _set(fields, "persuasion", amount)
                    _per_faction(fields, per)
            case RevealSwords(amount=amount, per=per):
                if per is None:
                    _set(fields, "strength", amount)
                elif per.kind is RevealCountKind.OTHER_SWORD_CARD:
                    _set(fields, "strength_per_other_sword_card", amount)
                else:
                    _set(fields, "strength", amount)
                    _per_faction(fields, per)
            case GainResources(solari=solari, spice=spice, water=water):
                _set(fields, "solari", solari)
                _set(fields, "spice", spice)
                _set(fields, "water", water)
            case DrawIntrigueCards(count=count):
                _set(fields, "draw_intrigue", count)
            case RecruitTroops(count=count):
                _set(fields, "recruit_troops", count)
            case GainInfluence(times=times, factions=(faction,)):
                _set(fields, "influence", times)
                _set(fields, "influence_faction", _bond(faction))
            case TrashThisCard():
                _set(fields, "trashes_self", True)
            case GrantCombatDeployment():
                _set(fields, "grants_combat_icon", True)
            case GenerateSpecimens(count=count):
                _set(fields, "specimens", count)
            case AdvanceTleilaxu(count=count):
                _set(fields, "tleilaxu", count)
            case Research():
                # One research icon each (Tleilaxu Master prints two).
                research += 1
            case _:
                raise TypeError(f"{reward!r} is not a Reveal gain")
    if research:
        _set(fields, "research", research)
    return PersonalCardRevealEffect(**fields)  # type: ignore[arg-type]


def _set(fields: dict[str, object], key: str, value: object) -> None:
    """One field of the compiled gain, printed once on its line."""

    if key in fields:
        raise ValueError(f"a Reveal gain line prints {key} twice")
    fields[key] = value


def _per_faction(fields: dict[str, object], per: RevealCount) -> None:
    assert per.faction is not None
    key = (
        "per_revealed_faction"
        if per.kind is RevealCountKind.REVEALED_FACTION_CARD
        else "per_in_play_faction"
    )
    _set(fields, key, _bond(per.faction))


def reveal_effects_of(card_id: str) -> tuple[PersonalCardRevealEffect, ...]:
    """The Reveal gains of the card ``card_id`` (a definition id), from its
    record; a card without one gains nothing on its own."""

    ability = REVEAL_GAIN_ABILITIES.get(card_id)
    if ability is None:
        return ()
    return tuple(reveal_effect(line) for line in ability.sections)
