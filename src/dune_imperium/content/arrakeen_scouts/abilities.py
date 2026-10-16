"""The Arrakeen Scouts items as ability records (composed effects, A7b).

docs/composed-effects-plan.md 5 (A7b): every Scouts item is keyed by its id.
A subcommittee, a choice or shared event, a sale and a secret event print
cost -> reward lines (``SCOUTS`` timing, one section per line, structure
ONE_OF where the seat takes one), a sealed auction one reward per winning
place; the content tables compile them back into ``ScoutsOption`` /
``rank_rewards`` (``scouts_option``, ``scouts_options``,
``scouts_rank_rewards``), which the Scouts step and its line executor read
unchanged. Missions, automatic events, round modifiers, Mercenaries and
Critical Moment are mechanisms of the module, kept as engine code and named
by a record without lines (composed A7e); Rebuild Infrastructure's record
lists what each volunteer pays beside its hook. The rules and the app's
wording are in ``docs/rules/arrakeen-scouts.md``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.arrakeen_scouts.types import ScoutsOption
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireReserveCardToHand,
    AdvanceTleilaxu,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainLowestInfluence,
    GainResources,
    GainSpiceWithHelixBonus,
    GenerateSpecimens,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    PayResources,
    PaySpecimens,
    PlaceSpy,
    RecallOtherAgent,
    RecallSpy,
    RecruitToConflict,
    RecruitTroops,
    Research,
    Reward,
    TakeContract,
    TrashIntrigueCard,
    TrashPersonalCard,
)


def _influence(faction: Faction) -> GainInfluence:
    """One Influence with a named Faction."""

    return GainInfluence(factions=(faction,))


# "Trash a card from your hand", the price or loss of two events.
_TRASH_FROM_HAND: Final = TrashPersonalCard(hand_only=True, mandatory=True)


def _record(
    mark: AbilityMark, *lines: EffectSection, hook: str | None = None
) -> Ability:
    return Ability(
        timing=AbilityTiming.SCOUTS,
        sections=lines,
        mark=mark,
        structure=(
            AbilityStructure.ONE_OF if len(lines) > 1 else AbilityStructure.SEQUENCE
        ),
        hook=hook,
    )


def _places(*lines: EffectSection) -> Ability:
    """A sealed auction's rewards, one line per winning place."""

    return Ability(
        timing=AbilityTiming.SCOUTS,
        sections=lines,
        mark=AbilityMark.AUTOMATIC,
        structure=(
            AbilityStructure.SEPARATE if len(lines) > 1 else AbilityStructure.SEQUENCE
        ),
    )


def _mechanism(hook: str) -> Ability:
    return Ability(
        timing=AbilityTiming.SCOUTS, sections=(), mark=AbilityMark.AUTOMATIC, hook=hook
    )


SCOUTS_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Subcommittee appropriations
        "appropriations": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(GainResources(water=1),), costs=(DiscardFromHand(1),)
            ),
        ),
        # Subcommittee intelligence
        "intelligence": _record(
            AbilityMark.OPTIONAL, EffectSection(rewards=(PlaceSpy(),))
        ),
        # Subcommittee readiness
        "readiness": _record(
            AbilityMark.OPTIONAL, EffectSection(rewards=(RecruitTroops(1),))
        ),
        # Subcommittee choam_coordination
        "choam_coordination": _record(
            AbilityMark.OPTIONAL, EffectSection(rewards=(TakeContract(1),))
        ),
        # Subcommittee growth_project
        "growth_project": _record(
            AbilityMark.OPTIONAL, EffectSection(rewards=(GenerateSpecimens(1),))
        ),
        # Subcommittee oversight
        "oversight": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(TrashPersonalCard(), GainResources(spice=1)),
                costs=(RecallSpy(1),),
            ),
        ),
        # Subcommittee investigations
        "investigations": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(DrawIntrigueCards(1),), costs=(PayResources(solari=1),)
            ),
        ),
        # Subcommittee forecasting
        "forecasting": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(DrawPersonalCards(2),), costs=(PayResources(spice=1),)
            ),
        ),
        # Subcommittee choam_management
        "choam_management": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(TakeContract(2),), costs=(PayResources(spice=1),)),
        ),
        # Subcommittee analytics
        "analytics": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(Research(),), costs=(PayResources(solari=1),)),
        ),
        # Subcommittee relations
        "relations": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(GainInfluence(),), costs=(PayResources(spice=2),)),
        ),
        # Subcommittee contingencies
        "contingencies": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(RecallOtherAgent(),), costs=(TrashIntrigueCard(),)),
        ),
        # Subcommittee leverage
        "leverage": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(GainInfluence(), DrawIntrigueCards(1)), costs=(RecallSpy(2),)
            ),
        ),
        # Subcommittee tleilaxu_relations
        "tleilaxu_relations": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(AdvanceTleilaxu(2),), costs=(PayResources(spice=3),)
            ),
        ),
        # ScoutsEvent private_stock
        "private_stock": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(GainResources(spice=1),)),
            EffectSection(rewards=(DrawPersonalCards(1),)),
        ),
        # ScoutsEvent market_research
        "market_research": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(GainResources(spice=2),), costs=(RecallSpy(1),)),
        ),
        # ScoutsEvent smoke_and_mirrors
        "smoke_and_mirrors": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(PlaceSpy(),)),
            EffectSection(
                rewards=(DrawIntrigueCards(1),), costs=(PayResources(solari=1),)
            ),
        ),
        # ScoutsEvent rotating_doors
        "rotating_doors": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(DrawIntrigueCards(1), DrawPersonalCards(1)),
                costs=(TrashIntrigueCard(),),
            ),
        ),
        # ScoutsEvent moment_of_revelation
        "moment_of_revelation": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(AcquireReserveCardToHand("prepare_the_way"),),
                costs=(PayResources(spice=2),),
            ),
        ),
        # ScoutsEvent water_discipline
        "water_discipline": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(TrashPersonalCard(), DrawPersonalCards(1)),
                costs=(PayResources(water=1),),
            ),
        ),
        # ScoutsEvent royal_delegation
        "royal_delegation": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(_influence(Faction.EMPEROR),), costs=(PayResources(solari=2),)
            ),
        ),
        # ScoutsEvent guild_negotiation
        "guild_negotiation": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(_influence(Faction.SPACING_GUILD),),
                costs=(PayResources(spice=1), DiscardFromHand(1)),
            ),
        ),
        # ScoutsEvent covert_assistance
        "covert_assistance": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(_influence(Faction.BENE_GESSERIT),), costs=(RecallSpy(1),)
            ),
        ),
        # ScoutsEvent gift_of_water
        "gift_of_water": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(_influence(Faction.FREMEN),), costs=(PayResources(water=1),)
            ),
        ),
        # ScoutsEvent share_intelligence
        "share_intelligence": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(GainInfluence(),),
                costs=(TrashIntrigueCard(), PayResources(solari=1)),
            ),
        ),
        # ScoutsEvent political_equilibrium: AutomaticEffect.POLITICAL_EQUILIBRIUM
        "political_equilibrium": _mechanism("scouts_political_equilibrium"),
        # ScoutsEvent crackdown
        "crackdown": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(), costs=(RecallSpy(1),)),
            EffectSection(rewards=(), costs=(LoseFactionInfluence(Faction.EMPEROR),)),
        ),
        # ScoutsEvent water_for_spice_smugglers
        "water_for_spice_smugglers": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(), costs=(PayResources(water=1),)),
            EffectSection(
                rewards=(), costs=(LoseFactionInfluence(Faction.SPACING_GUILD),)
            ),
        ),
        # ScoutsEvent bene_gesserit_treachery
        "bene_gesserit_treachery": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(), costs=(LoseGarrisonTroops(1),)),
            EffectSection(
                rewards=(), costs=(LoseFactionInfluence(Faction.BENE_GESSERIT),)
            ),
        ),
        # ScoutsEvent funeral_rites
        "funeral_rites": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(), costs=(_TRASH_FROM_HAND,)),
            EffectSection(rewards=(), costs=(LoseFactionInfluence(Faction.FREMEN),)),
        ),
        # ScoutsEvent covert_operation (secret picks)
        "covert_operation": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(PlaceSpy(),)),
            EffectSection(rewards=(GainResources(solari=2),)),
            EffectSection(rewards=(RecruitTroops(3),), costs=(DiscardFromHand(1),)),
            EffectSection(rewards=(GainLowestInfluence(),)),
        ),
        # ScoutsEvent covert_operation_choam (secret picks)
        "covert_operation_choam": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(PlaceSpy(),)),
            EffectSection(rewards=(TakeContract(1),)),
            EffectSection(rewards=(RecruitTroops(3),), costs=(DiscardFromHand(1),)),
            EffectSection(rewards=(GainLowestInfluence(),)),
        ),
        # ScoutsEvent mating_season: AutomaticEffect.MATING_SEASON
        "mating_season": _mechanism("scouts_mating_season"),
        # ScoutsEvent unlikely_allies: RoundModifier.IGNORE_INFLUENCE_REQUIREMENTS
        "unlikely_allies": _mechanism("scouts_unlikely_allies"),
        # ScoutsEvent clear_the_market: AutomaticEffect.CLEAR_THE_MARKET
        "clear_the_market": _mechanism("scouts_clear_the_market"),
        # ScoutsEvent clear_the_market_choam: AutomaticEffect.CLEAR_THE_MARKET_CONTRACTS
        "clear_the_market_choam": _mechanism("scouts_clear_the_market_choam"),
        # ScoutsEvent market_opening: RoundModifier.SPICE_MUST_FLOW_DISCOUNT
        "market_opening": _mechanism("scouts_market_opening"),
        # ScoutsEvent eyes_on_arrakis: RoundModifier.FACTION_SPACES_ARE_COMBAT
        "eyes_on_arrakis": _mechanism("scouts_eyes_on_arrakis"),
        # ScoutsEvent friends_everywhere: RoundModifier.ANY_FACTION_FOUR_BONUS
        "friends_everywhere": _mechanism("scouts_friends_everywhere"),
        # ScoutsEvent rebuild_infrastructure
        "rebuild_infrastructure": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(), costs=(PayResources(spice=1),)),
            hook="scouts_rebuild_infrastructure",
        ),
        # ScoutsEvent choam_bargain
        "choam_bargain": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(DrawPersonalCards(1),)),
            EffectSection(rewards=(TakeContract(1),)),
        ),
        # ScoutsEvent ingratiate
        "ingratiate": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(GainInfluence(),), costs=(PaySpecimens(1),)),
        ),
        # ScoutsEvent betrayal
        "betrayal": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(AdvanceTleilaxu(1),),
                costs=(LoseFactionInfluence(Faction.BENE_GESSERIT),),
            ),
        ),
        # ScoutsEvent new_innovations
        "new_innovations": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(Research(),), costs=(PayResources(solari=1),)),
            EffectSection(rewards=(Research(),), costs=(PayResources(spice=1),)),
        ),
        # ScoutsEvent termination_request
        "termination_request": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(GenerateSpecimens(1),), costs=(_TRASH_FROM_HAND,)),
        ),
        # ScoutsEvent offworld_operation (secret picks)
        "offworld_operation": _record(
            AbilityMark.MANDATORY,
            EffectSection(rewards=(GainResources(solari=2),)),
            EffectSection(rewards=(GainSpiceWithHelixBonus(),)),
            EffectSection(rewards=(AdvanceTleilaxu(1),)),
            EffectSection(rewards=(DrawIntrigueCards(1),)),
        ),
        # ScoutsAuction highest_bidder_mid (one line per winning place)
        "highest_bidder_mid": _places(EffectSection(rewards=(DrawPersonalCards(1),))),
        # ScoutsAuction highest_bidder_late (one line per winning place)
        "highest_bidder_late": _places(
            EffectSection(rewards=(DrawPersonalCards(2),)),
            EffectSection(rewards=(DrawPersonalCards(1),)),
        ),
        # ScoutsAuction mercenaries: AuctionKind.MERCENARIES
        "mercenaries": _mechanism("scouts_mercenaries"),
        # ScoutsAuction competitive_study_mid (one line per winning place)
        "competitive_study_mid": _places(
            EffectSection(rewards=(Research(), GenerateSpecimens(1)))
        ),
        # ScoutsAuction competitive_study_late (one line per winning place)
        "competitive_study_late": _places(
            EffectSection(rewards=(Research(), GenerateSpecimens(1))),
            EffectSection(rewards=(Research(),)),
        ),
        # ScoutsAuction spies_for_hire_mid (one line per winning place)
        "spies_for_hire_mid": _places(EffectSection(rewards=(PlaceSpy(),))),
        # ScoutsAuction spies_for_hire_late (one line per winning place)
        "spies_for_hire_late": _places(
            EffectSection(rewards=(PlaceSpy(), DrawIntrigueCards(1))),
            EffectSection(rewards=(PlaceSpy(),)),
        ),
        # ScoutsAuction critical_moment_mid: AuctionKind.OPEN_CARDS
        "critical_moment_mid": _mechanism("scouts_critical_moment_mid"),
        # ScoutsAuction critical_moment_late: AuctionKind.OPEN_CARDS
        "critical_moment_late": _mechanism("scouts_critical_moment_late"),
        # ScoutsAuction choam_negotiations_mid (one line per winning place)
        "choam_negotiations_mid": _places(EffectSection(rewards=(TakeContract(1),))),
        # ScoutsAuction choam_negotiations_late (one line per winning place)
        "choam_negotiations_late": _places(
            EffectSection(rewards=(TakeContract(1), DrawIntrigueCards(1))),
            EffectSection(rewards=(TakeContract(1),)),
        ),
        # ScoutsSale unravel_the_future
        "unravel_the_future": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(DrawPersonalCards(1),), costs=(PayResources(spice=1),)
            ),
            EffectSection(
                rewards=(DrawPersonalCards(2),), costs=(PayResources(spice=3),)
            ),
        ),
        # ScoutsSale imperium_connections
        "imperium_connections": _record(
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(PlaceSpy(),), costs=(PayResources(solari=2),)),
            EffectSection(
                rewards=(GainResources(water=1),), costs=(PayResources(solari=2),)
            ),
        ),
        # ScoutsSale secrets_for_sale
        "secrets_for_sale": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(DrawIntrigueCards(1),), costs=(PayResources(spice=1),)
            ),
            EffectSection(
                rewards=(DrawIntrigueCards(2),), costs=(PayResources(spice=3),)
            ),
        ),
        # ScoutsSale shadow_warfare
        "shadow_warfare": _record(
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(RecruitToConflict(1), GainResources(spice=1)),
                costs=(RecallSpy(1),),
            ),
            EffectSection(
                rewards=(RecruitToConflict(3), GainResources(spice=2)),
                costs=(RecallSpy(2),),
            ),
        ),
        # Mission security_detail: MissionKind.SECURITY_DETAIL
        "security_detail": _mechanism("scouts_security_detail"),
        # Mission imperial_reserve: MissionKind.IMPERIAL_RESERVE
        "imperial_reserve": _mechanism("scouts_imperial_reserve"),
        # Mission desert_riding: MissionKind.DESERT_RIDING
        "desert_riding": _mechanism("scouts_desert_riding"),
        # Mission urban_surveillance: MissionKind.URBAN_SURVEILLANCE
        "urban_surveillance": _mechanism("scouts_urban_surveillance"),
        # Mission planetary_exploration: MissionKind.PLANETARY_EXPLORATION
        "planetary_exploration": _mechanism("scouts_planetary_exploration"),
        # Mission choam_research: MissionKind.CHOAM_RESEARCH
        "choam_research": _mechanism("scouts_choam_research"),
        # Mission choam_escort: MissionKind.CHOAM_ESCORT
        "choam_escort": _mechanism("scouts_choam_escort"),
        # Mission sponsored_research: MissionKind.SPONSORED_RESEARCH
        "sponsored_research": _mechanism("scouts_sponsored_research"),
        # Mission back_room_deal: MissionKind.BACK_ROOM_DEAL
        "back_room_deal": _mechanism("scouts_back_room_deal"),
        # Mission prison_planet: MissionKind.PRISON_PLANET
        "prison_planet": _mechanism("scouts_prison_planet"),
        # Mission emperors_schemes: MissionKind.EMPERORS_SCHEMES
        "emperors_schemes": _mechanism("scouts_emperors_schemes"),
        # Mission fedaykin_assistance: MissionKind.FEDAYKIN_ASSISTANCE
        "fedaykin_assistance": _mechanism("scouts_fedaykin_assistance"),
        # Mission weirding_warfare: MissionKind.WEIRDING_WARFARE
        "weirding_warfare": _mechanism("scouts_weirding_warfare"),
        # Mission send_for_aid: MissionKind.SEND_FOR_AID
        "send_for_aid": _mechanism("scouts_send_for_aid"),
        # Mission coordinate_with_the_emperor: MissionKind.COORDINATE_WITH_THE_EMPEROR
        "coordinate_with_the_emperor": _mechanism("scouts_coordinate_with_the_emperor"),
        # Mission tleilaxu_offering: MissionKind.TLEILAXU_OFFERING
        "tleilaxu_offering": _mechanism("scouts_tleilaxu_offering"),
    }
)


def _line(item_id: str, index: int) -> EffectSection:
    ability = SCOUTS_ABILITIES[item_id]
    line = ability.sections[index]
    if line.condition is not None or ability.requirement is not None:
        raise ValueError(f"{item_id}: a Scouts line has no condition")
    return line


def scouts_option(item_id: str, index: int = 0) -> ScoutsOption:
    """The item's ``index``-th line as the Scouts executor reads it."""

    line = _line(item_id, index)
    return ScoutsOption(costs=line.costs, rewards=line.rewards)


def scouts_options(item_id: str) -> tuple[ScoutsOption, ...]:
    """Every line of a choice or shared event, or a sale."""

    return tuple(
        scouts_option(item_id, index)
        for index in range(len(SCOUTS_ABILITIES[item_id].sections))
    )


def scouts_rank_rewards(item_id: str) -> tuple[tuple[Reward, ...], ...]:
    """A sealed auction's rewards per winning place."""

    places = []
    for index in range(len(SCOUTS_ABILITIES[item_id].sections)):
        line = _line(item_id, index)
        if line.costs:
            raise ValueError(f"{item_id}: an auction place is paid by the bid")
        places.append(line.rewards)
    return tuple(places)
