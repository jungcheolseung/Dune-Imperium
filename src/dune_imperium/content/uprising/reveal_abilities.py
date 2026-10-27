"""Reveal automatic gains of personal cards as ability records (composed effects, A4c).

docs/composed-effects-plan.md 5 (A4c): what a personal card gains on its own
when it is revealed -- the Reveal box's printed gains, their conditions and
the counts that multiply them -- is written here as automatic ability
records keyed by the card's definition id, one line per printed effect
(each judged on its own). ``rules.reveal_turn`` reads these lines
(``rules.reveal_lines``, stage B3e-2) and pays them: Persuasion and swords at
once, the other gains as the owner's own steps (OQ-045), a condition met
later in the turn paying then (``grant_late_reveal_effects``); the card text
(``display/tokens.reveal_effect_text``) and the action catalog read the same
lines. Until the Reveal totals cleanup (2026-10-21) the card manifests also
kept a compiled copy of every line (``PersonalCardRevealEffect``); its checks
now run on the records themselves (``check_reveal_gain_line``). A card's
printed Reveal Persuasion and swords (``reveal_persuasion``,
``reveal_strength``) are card values, not abilities; its Reveal choices are
A4d's.
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
        # Crysknife (original game): "Fremen Bond: 1 Fremen Influence".
        "crysknife_card": _reveal(
            _line(
                GainInfluence(factions=(Faction.FREMEN,)),
                condition=FactionBond(Faction.FREMEN),
            )
        ),
        # Fedaykin Death Commando (original game): "Fremen Bond: 3 swords".
        "fedaykin_death_commando": _reveal(
            _line(RevealSwords(3), condition=FactionBond(Faction.FREMEN))
        ),
        # Duncan Idaho (original game): "1 water" beside its printed swords.
        "duncan_idaho_card": _reveal(_line(GainResources(water=1))),
        # CHOAM Directorship (original game): "3 Solari".
        "choam_directorship": _reveal(_line(GainResources(solari=3))),
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
        # The original game's The Spice Must Flow (Reserve): 1 spice
        # (``ImperiumArchetypes.BaseSet``, docs/base-game-and-ix-plan.md 15.3).
        "imperium_the_spice_must_flow": _reveal(_line(GainResources(spice=1))),
        # Twisted Mentat.
        "twisted_mentat": _reveal(_line(GenerateSpecimens(1))),
        # Usurp.
        "usurp": _reveal(_line(GenerateSpecimens(1))),
    }
)


# What a Reveal line may hold; the card text renders each of them
# (``display.tokens.HANDLED_REVEAL_CONDITIONS`` and ``_REWARDS``).
REVEAL_LINE_CONDITIONS: Final[frozenset[type]] = frozenset(
    {
        FactionBond,
        HasHighCouncil,
        HasSwordmaster,
        SpiesPlacedAtLeast,
        SpyingOnMakerSpace,
        CommandersInConflictAtLeast,
        GeneticMarkersAtLeast,
        GarrisonedUnitsAtLeast,
        CommandReached,
    }
)
REVEAL_LINE_REWARDS: Final[frozenset[type]] = frozenset(
    {
        RevealPersuasion,
        RevealSwords,
        GainResources,
        DrawIntrigueCards,
        RecruitTroops,
        GainInfluence,
        TrashThisCard,
        GrantCombatDeployment,
        GenerateSpecimens,
        AdvanceTleilaxu,
        Research,
    }
)


def _conditions(condition: Condition | None) -> tuple[Condition, ...]:
    if condition is None:
        return ()
    if isinstance(condition, AllConditions):
        return condition.conditions
    return (condition,)


def check_reveal_gain_line(line: EffectSection) -> None:
    """Refuse a Reveal line the card text and the Reveal turn cannot read.

    Each condition and gain is of a kind a Reveal line holds, and printed at
    most once on its line (a Persuasion or a sword amount counts once whether
    flat or per Faction card; a count per Faction card scales one gain); a
    Commander condition asks for one Commander; a Swordmaster condition comes
    with High Council; the line gains something (a Combat icon counts); and a
    Command line grants no Persuasion -- the total that opens Command must
    not depend on it [Bloodlines p. 5].
    """

    printed: set[str] = set()

    def once(key: str) -> None:
        if key in printed:
            raise ValueError(f"a Reveal gain line prints {key} twice")
        printed.add(key)

    for condition in _conditions(line.condition):
        if type(condition) not in REVEAL_LINE_CONDITIONS:
            raise TypeError(f"{condition!r} is not a Reveal gain condition")
        if isinstance(condition, CommandersInConflictAtLeast) and condition.count != 1:
            raise TypeError(f"{condition!r} is not a Reveal gain condition")
        once(type(condition).__name__)
    if "HasSwordmaster" in printed and "HasHighCouncil" not in printed:
        raise ValueError("Swordmaster Reveal requirement also needs High Council")
    gains = 0
    for reward in line.rewards:
        if type(reward) not in REVEAL_LINE_REWARDS:
            raise TypeError(f"{reward!r} is not a Reveal gain")
        match reward:
            case RevealPersuasion(amount=amount, per=per) | RevealSwords(
                amount=amount, per=per
            ):
                persuasion = isinstance(reward, RevealPersuasion)
                kind = "persuasion" if persuasion else "swords"
                if per is not None and per.faction is None:
                    once(f"{kind} per {per.kind}")
                else:
                    once(kind)
                    if per is not None:
                        once("count per Faction card")
                gains += amount
            case GainResources(solari=solari, spice=spice, water=water):
                once("resources")
                if min(solari, spice, water) < 0:
                    raise ValueError("personal-card Reveal gains must not be negative")
                gains += solari + spice + water
            case GainInfluence(times=times, factions=factions):
                if factions is None or len(factions) != 1:
                    raise TypeError(f"{reward!r} is not a Reveal gain")
                once("influence")
                gains += times
            case DrawIntrigueCards(count=count) | RecruitTroops(count=count):
                once(type(reward).__name__)
                gains += count
            case GenerateSpecimens(count=count) | AdvanceTleilaxu(count=count):
                once(type(reward).__name__)
                gains += count
            case Research():
                # One Research icon each (Tleilaxu Master prints two).
                gains += 1
            case TrashThisCard() | GrantCombatDeployment():
                once(type(reward).__name__)
    if gains <= 0 and not any(
        isinstance(reward, GrantCombatDeployment) for reward in line.rewards
    ):
        raise ValueError("personal-card Reveal effect must gain something")
    if "CommandReached" in printed and any(
        isinstance(reward, RevealPersuasion) for reward in line.rewards
    ):
        raise ValueError("a Command effect cannot grant Persuasion")


for _ability in REVEAL_GAIN_ABILITIES.values():
    for _section in _ability.sections:
        check_reveal_gain_line(_section)
