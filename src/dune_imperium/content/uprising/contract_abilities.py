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
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquiredCard,
    AllConditions,
    AllianceTaken,
    AtBoardSpace,
    AtMakerSpace,
    Condition,
    ContractTaken,
    Cost,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecallAgent,
    RecruitTroops,
    Reward,
    TrashIntrigueCard,
)

_TAKEN = ContractTaken()


def _harvest(amount: int) -> AllConditions:
    """ "Send an Agent to a Maker space and gain N or more spice that turn"."""

    return AllConditions((AtMakerSpace(), GainedSpiceThisTurn(amount)))


def _terms(
    requirement: Condition, *rewards: Reward, costs: tuple[Cost, ...] = ()
) -> Ability:
    return Ability(
        timing=AbilityTiming.CONTRACT,
        sections=(EffectSection(rewards=rewards, costs=costs),),
        requirement=requirement,
    )


CONTRACT_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Acquire.
        "acquire": _terms(
            AcquiredCard("the_spice_must_flow"),
            GainResources(solari=3),
            GainInfluence(factions=(Faction.SPACING_GUILD,)),
        ),
        # Arrakeen I.
        "arrakeen_i": _terms(AtBoardSpace("arrakeen"), GainResources(water=1)),
        # Arrakeen II.
        "arrakeen_ii": _terms(AtBoardSpace("arrakeen"), RecruitTroops(1), PlaceSpy()),
        # Deliver Supplies.
        "deliver_supplies": _terms(
            AtBoardSpace("deliver_supplies"), GainResources(solari=3)
        ),
        # Espionage I.
        "espionage_i": _terms(AtBoardSpace("espionage"), GainResources(solari=3)),
        # Harvest 3+.
        "harvest_3": _terms(_harvest(3), GainResources(solari=3)),
        # Harvest 4+.
        "harvest_4": _terms(_harvest(4), GainResources(solari=4)),
        # Spice Refinery I. Two card backs: draw two cards [tile face].
        "spice_refinery_i": _terms(
            AtBoardSpace("spice_refinery"), DrawPersonalCards(2)
        ),
        # Heighliner I.
        "heighliner_i": _terms(AtBoardSpace("heighliner"), GainResources(water=2)),
        # Heighliner II.
        "heighliner_ii": _terms(AtBoardSpace("heighliner"), RecruitTroops(2)),
        # Spice Refinery II.
        "spice_refinery_ii": _terms(
            AtBoardSpace("spice_refinery"), GainResources(water=1)
        ),
        # High Council I.
        "high_council_i": _terms(
            AtBoardSpace("high_council"),
            GainInfluence(factions=(Faction.BENE_GESSERIT,)),
        ),
        # High Council II.
        "high_council_ii": _terms(
            AtBoardSpace("high_council"), GainResources(solari=3)
        ),
        # Immediate.
        "immediate": _terms(_TAKEN, GainResources(solari=2)),
        # Research Station I.
        "research_station_i": _terms(
            AtBoardSpace("research_station"), GainResources(solari=2), PlaceSpy()
        ),
        # Research Station II.
        "research_station_ii": _terms(
            AtBoardSpace("research_station"), GainResources(solari=3)
        ),
        # Sardaukar I.
        "sardaukar_i": _terms(AtBoardSpace("sardaukar"), DrawPersonalCards(2)),
        # Sardaukar II. The printed reward recalls one of the player's Agents;
        # per the general glossary the recalled Agent cannot be the one just
        # sent [Main p. 20].
        "sardaukar_ii": _terms(AtBoardSpace("sardaukar"), RecallAgent()),
        # Deliver Supplies.
        "bloodlines_deliver_supplies": _terms(
            AtBoardSpace("deliver_supplies"),
            GainResources(solari=1),
            PlaceSpy(shared_post=True),
        ),
        # Earn Any Alliance.
        "bloodlines_earn_any_alliance": _terms(
            AllianceTaken(), GainResources(solari=2), RecruitTroops(2)
        ),
        # Harvest 3+.
        "bloodlines_harvest_3": _terms(
            _harvest(3), GainResources(solari=2), PlaceSpy()
        ),
        # Harvest 4+.
        "bloodlines_harvest_4": _terms(
            _harvest(4), GainResources(solari=3), PlaceSpy()
        ),
        # High Council (Bloodlines). Recall one of your Agents; as with Sardaukar
        # II the Agent just sent is not a valid target [Main p. 20].
        "bloodlines_high_council": _terms(AtBoardSpace("high_council"), RecallAgent()),
        # Immediate.
        "bloodlines_immediate": _terms(
            _TAKEN,
            DrawIntrigueCards(1),
            DrawPersonalCards(1),
            costs=(TrashIntrigueCard(),),
        ),
        # Secrets.
        "bloodlines_secrets": _terms(
            AtBoardSpace("secrets"), GainResources(solari=2), DrawPersonalCards(1)
        ),
        # Spice Refinery.
        "bloodlines_spice_refinery": _terms(
            AtBoardSpace("spice_refinery"), RecruitTroops(2)
        ),
    }
)
