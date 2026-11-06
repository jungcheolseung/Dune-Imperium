"""Contract tiles' terms as ability records (composed effects, A5a).

docs/composed-effects-plan.md 5 (A5a): what each Contract tile asks and gives
is written here, keyed by the tile's id (a second copy shares its first
copy's record). ``requirement`` is the completion condition: a visit to a
board space (judged by the placement's snapshot), a Maker-space visit with
enough spice gained that turn, an acquisition of a named card, taking the
tile itself (the Immediate tiles; the Bloodlines one costs an Intrigue card
trashed from hand), or an Alliance taken; the line is the reward, its choice
part (a recall, a Spy) answered on its own frame. Each tile's definition
holds its record (``ContractDefinition.terms``), which the rules, the codec
and the card text (``display/structs.contract_condition_text`` /
``contract_reward_text``) read; the compiled ``ContractCondition`` /
``ContractReward`` copies are gone since the reward totals cleanup
(2026-10-21), and ``contracts.check_contract_terms`` checks each record.

This module holds the 18 faces of Uprising's 20 standard tiles; Bloodlines'
and the Rise of Ix tiles' records are in their own packages and
``content.registry.contract_abilities`` merges the three (stage 4,
docs/content-core-refactor-plan.md 8.3).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    contract_terms,
    maker_harvest,
)
from dune_imperium.content.core.effects import (
    AcquiredCard,
    AtBoardSpace,
    ContractTaken,
    DrawPersonalCards,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecallAgent,
    RecruitTroops,
)
from dune_imperium.content.core.icons import Faction

_TAKEN = ContractTaken()


UPRISING_CONTRACT_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Acquire.
        "acquire": contract_terms(
            AcquiredCard("the_spice_must_flow"),
            GainResources(solari=3),
            GainInfluence(factions=(Faction.SPACING_GUILD,)),
        ),
        # Arrakeen I.
        "arrakeen_i": contract_terms(AtBoardSpace("arrakeen"), GainResources(water=1)),
        # Arrakeen II.
        "arrakeen_ii": contract_terms(
            AtBoardSpace("arrakeen"), RecruitTroops(1), PlaceSpy()
        ),
        # Deliver Supplies.
        "deliver_supplies": contract_terms(
            AtBoardSpace("deliver_supplies"), GainResources(solari=3)
        ),
        # Espionage I.
        "espionage_i": contract_terms(
            AtBoardSpace("espionage"), GainResources(solari=3)
        ),
        # Harvest 3+.
        "harvest_3": contract_terms(maker_harvest(3), GainResources(solari=3)),
        # Harvest 4+.
        "harvest_4": contract_terms(maker_harvest(4), GainResources(solari=4)),
        # Spice Refinery I. Two card backs: draw two cards [tile face].
        "spice_refinery_i": contract_terms(
            AtBoardSpace("spice_refinery"), DrawPersonalCards(2)
        ),
        # Heighliner I.
        "heighliner_i": contract_terms(
            AtBoardSpace("heighliner"), GainResources(water=2)
        ),
        # Heighliner II.
        "heighliner_ii": contract_terms(AtBoardSpace("heighliner"), RecruitTroops(2)),
        # Spice Refinery II.
        "spice_refinery_ii": contract_terms(
            AtBoardSpace("spice_refinery"), GainResources(water=1)
        ),
        # High Council I.
        "high_council_i": contract_terms(
            AtBoardSpace("high_council"),
            GainInfluence(factions=(Faction.BENE_GESSERIT,)),
        ),
        # High Council II.
        "high_council_ii": contract_terms(
            AtBoardSpace("high_council"), GainResources(solari=3)
        ),
        # Immediate.
        "immediate": contract_terms(_TAKEN, GainResources(solari=2)),
        # Research Station I.
        "research_station_i": contract_terms(
            AtBoardSpace("research_station"), GainResources(solari=2), PlaceSpy()
        ),
        # Research Station II.
        "research_station_ii": contract_terms(
            AtBoardSpace("research_station"), GainResources(solari=3)
        ),
        # Sardaukar I.
        "sardaukar_i": contract_terms(AtBoardSpace("sardaukar"), DrawPersonalCards(2)),
        # Sardaukar II. The printed reward recalls one of the player's Agents;
        # per the general glossary the recalled Agent cannot be the one just
        # sent [Main p. 20].
        "sardaukar_ii": contract_terms(AtBoardSpace("sardaukar"), RecallAgent()),
    }
)
