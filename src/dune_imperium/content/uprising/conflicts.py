"""Uprising Conflict identities and tiers used to build the ten-card deck."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import Ability
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflict_abilities import (
    CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    TakeContract,
    TakeControl,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier


@dataclass(frozen=True, slots=True)
class ConflictReward:
    """One printed reward row; zero values mean that icon is absent."""

    solari: int = 0
    spice: int = 0
    water: int = 0
    intrigue: int = 0
    troops: int = 0
    place_spies: int = 0
    # Spy with Deep Cover: may ignore opponents' Spies [Bloodlines pp. 5, 12].
    deep_cover_spies: int = 0
    contracts: int = 0
    trash_cards: int = 0
    victory_points: int = 0
    choose_influence: int = 0
    choose_distinct_influence: int = 0
    faction_influence: int = 0
    influence_faction: Faction | None = None
    control_space_id: str | None = None
    optional_spice_cost: int = 0
    optional_solari_cost: int = 0
    optional_recall_spies: int = 0
    optional_victory_points: int = 0

    def __post_init__(self) -> None:
        values = (
            self.solari,
            self.spice,
            self.water,
            self.intrigue,
            self.troops,
            self.place_spies,
            self.deep_cover_spies,
            self.contracts,
            self.trash_cards,
            self.victory_points,
            self.choose_influence,
            self.choose_distinct_influence,
            self.faction_influence,
            self.optional_spice_cost,
            self.optional_solari_cost,
            self.optional_recall_spies,
            self.optional_victory_points,
        )
        if min(values) < 0:
            raise ValueError("Conflict reward quantities must not be negative")
        if (self.faction_influence > 0) != (self.influence_faction is not None):
            raise ValueError("fixed Influence requires both a faction and amount")
        # Each optional cost is its own arrow worth ``optional_victory_points``;
        # Economic Supremacy prints two (6 Solari and 4 spice) in one row.
        optional_costs = (
            self.optional_spice_cost,
            self.optional_solari_cost,
            self.optional_recall_spies,
        )
        if any(optional_costs) != (self.optional_victory_points > 0):
            raise ValueError("optional Conflict rewards require a cost and reward")
        if self.control_space_id == "":
            raise ValueError("control space ID must not be empty")
        if max(values) == 0 and self.control_space_id is None:
            raise ValueError("a Conflict reward row must contain a reward")


@dataclass(frozen=True, slots=True)
class ConflictDefinition:
    """Conflict identity, battle icon, and optional transcribed reward rows."""

    card: CardDefinition
    tier: ConflictTier
    # ``None``: the card prints no battle icon (Economic Supremacy; OQ-094).
    battle_icon: BattleIcon | None = None
    shield_wall_protected: bool = False
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward] | None = None
    # Added to the tier pool only with ``RulesetConfig(bloodlines=True)``
    # [Bloodlines p. 3].
    bloodlines_only: bool = False
    # Added to the tier pool only with ``RulesetConfig(epic_game=True)``
    # [Main p. 18].
    epic_only: bool = False


def _rewards(conflict_id: str) -> tuple[ConflictReward, ConflictReward, ConflictReward]:
    """The card's three reward rows, compiled from its records
    (``conflict_abilities``, composed A5b)."""

    first, second, third = CONFLICT_REWARD_ABILITIES[conflict_id]
    return _row(first), _row(second), _row(third)


def _put(
    fields: dict[str, int | str | Faction], key: str, value: int | str | Faction
) -> None:
    """One reward field, printed once on the row."""

    if key in fields:
        raise ValueError(f"a Conflict reward row prints {key} twice")
    fields[key] = value


def _row(ability: Ability) -> ConflictReward:
    fields: dict[str, int | str | Faction] = {}
    counted = {
        "place_spies": 0,
        "deep_cover_spies": 0,
        "trash_cards": 0,
        "choose_influence": 0,
    }
    arrow_points: set[int] = set()
    for line in ability.sections:
        if line.condition is not None:
            raise ValueError("a Conflict reward row prints no condition")
        if line.costs:
            # An optional "cost -> VP" arrow [FAQ p. 3]; the row's arrows share
            # one VP value (Economic Supremacy prints two).
            match line.costs, line.rewards:
                case (PayResources(solari=solari, spice=0, water=0),), (
                    GainVictoryPoints(amount=points),
                ) if solari:
                    _put(fields, "optional_solari_cost", solari)
                case (PayResources(solari=0, spice=spice, water=0),), (
                    GainVictoryPoints(amount=points),
                ) if spice:
                    _put(fields, "optional_spice_cost", spice)
                case (RecallSpy(count=count),), (GainVictoryPoints(amount=points),):
                    _put(fields, "optional_recall_spies", count)
                case _:
                    raise TypeError(f"{line!r} is not a Conflict reward arrow")
            arrow_points.add(points)
            continue
        for reward in line.rewards:
            match reward:
                case GainResources(solari=solari, spice=spice, water=water):
                    _put(fields, "solari", solari)
                    _put(fields, "spice", spice)
                    _put(fields, "water", water)
                case DrawIntrigueCards(count=count):
                    _put(fields, "intrigue", count)
                case RecruitTroops(count=count):
                    _put(fields, "troops", count)
                case PlaceSpy() if reward == PlaceSpy(shared_post=True):
                    counted["deep_cover_spies"] += 1
                case PlaceSpy() if reward == PlaceSpy():
                    counted["place_spies"] += 1
                case TakeContract(count=count):
                    _put(fields, "contracts", count)
                case TrashPersonalCard() if reward == TrashPersonalCard():
                    counted["trash_cards"] += 1
                case GainVictoryPoints(amount=amount):
                    _put(fields, "victory_points", amount)
                case GainInfluence() if reward == GainInfluence(
                    times=reward.times, distinct=True
                ):
                    _put(fields, "choose_distinct_influence", reward.times)
                case GainInfluence(times=times, factions=(faction,)) if (
                    reward == GainInfluence(times=times, factions=(faction,))
                ):
                    _put(fields, "faction_influence", times)
                    _put(fields, "influence_faction", faction)
                case GainInfluence() if reward == GainInfluence():
                    counted["choose_influence"] += 1
                case TakeControl(space_id=space_id):
                    _put(fields, "control_space_id", space_id)
                case _:
                    raise TypeError(f"{reward!r} is not a Conflict reward")
    if len(arrow_points) > 1:
        raise ValueError("a Conflict reward row's arrows share one VP value")
    if arrow_points:
        _put(fields, "optional_victory_points", arrow_points.pop())
    fields.update({key: value for key, value in counted.items() if value})
    return ConflictReward(**fields)  # type: ignore[arg-type]


MAIN_P3_P4: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
BLOODLINES_P3: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2, 3)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


def _conflict(
    card_id: int,
    content_id: str,
    name: str,
    tier: ConflictTier,
    *,
    battle_icon: BattleIcon | None = None,
    shield_wall_protected: bool = False,
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward] | None = None,
) -> ConflictDefinition:
    slug = f"uprising-{content_id.replace('_', '-')}"
    return ConflictDefinition(
        card=CardDefinition(
            content_id,
            name,
            MAIN_P3_P4,
            catalog_url=f"https://dunecardshub.com/cards/{card_id}/{slug}",
        ),
        tier=tier,
        battle_icon=battle_icon,
        shield_wall_protected=shield_wall_protected,
        rewards=rewards,
    )


CONFLICTS: Final = (
    _conflict(
        451,
        "skirmish_crysknife",
        "Skirmish (Crysknife)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.CRYSKNIFE,
        rewards=_rewards("skirmish_crysknife"),
    ),
    _conflict(
        452,
        "skirmish_ornithopter",
        "Skirmish (Ornithopter)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.ORNITHOPTER,
        rewards=_rewards("skirmish_ornithopter"),
    ),
    _conflict(
        453,
        "skirmish_desert_mouse",
        "Skirmish (Desert Mouse)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        rewards=_rewards("skirmish_desert_mouse"),
    ),
    _conflict(
        454,
        "choam_security",
        "CHOAM Security",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        rewards=_rewards("choam_security"),
    ),
    _conflict(
        455,
        "spice_freighters",
        "Spice Freighters",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        rewards=_rewards("spice_freighters"),
    ),
    _conflict(
        456,
        "siege_of_arrakeen",
        "Siege of Arrakeen",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        rewards=_rewards("siege_of_arrakeen"),
    ),
    _conflict(
        457,
        "seize_spice_refinery",
        "Seize Spice Refinery",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        rewards=_rewards("seize_spice_refinery"),
    ),
    _conflict(
        458,
        "test_of_loyalty",
        "Test of Loyalty",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        rewards=_rewards("test_of_loyalty"),
    ),
    _conflict(
        459,
        "shadow_contest",
        "Shadow Contest",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        rewards=_rewards("shadow_contest"),
    ),
    _conflict(
        460,
        "secure_imperial_basin",
        "Secure Imperial Basin",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        rewards=_rewards("secure_imperial_basin"),
    ),
    _conflict(
        461,
        "protect_the_sietches",
        "Protect the Sietches",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        rewards=_rewards("protect_the_sietches"),
    ),
    _conflict(
        462,
        "trade_dispute",
        "Trade Dispute",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        rewards=_rewards("trade_dispute"),
    ),
    _conflict(
        463,
        "propaganda",
        "Propaganda",
        ConflictTier.THREE,
        battle_icon=BattleIcon.WILD,
        rewards=_rewards("propaganda"),
    ),
    _conflict(
        464,
        "battle_for_imperial_basin",
        "Battle for Imperial Basin",
        ConflictTier.THREE,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        rewards=_rewards("battle_for_imperial_basin"),
    ),
    _conflict(
        465,
        "battle_for_arrakeen",
        "Battle for Arrakeen",
        ConflictTier.THREE,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        rewards=_rewards("battle_for_arrakeen"),
    ),
    _conflict(
        466,
        "battle_for_spice_refinery",
        "Battle for Spice Refinery",
        ConflictTier.THREE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        rewards=_rewards("battle_for_spice_refinery"),
    ),
    # Bloodlines adds one Conflict I and one Conflict II, both with a wild
    # battle icon [Bloodlines pp. 2-3]; rewards transcribed from the card
    # faces (asset repository ``cards/en/bloodlines/conflict/``).
    ConflictDefinition(
        card=CardDefinition(
            "skirmish_wild",
            "Skirmish (Wild)",
            BLOODLINES_P3,
            catalog_url="https://dunecardshub.com/images/bloodlines-conflict-skirmish.webp",
        ),
        tier=ConflictTier.ONE,
        battle_icon=BattleIcon.WILD,
        rewards=_rewards("skirmish_wild"),
        bloodlines_only=True,
    ),
    ConflictDefinition(
        card=CardDefinition(
            "storms_in_the_south",
            "Storms in the South",
            BLOODLINES_P3,
            catalog_url=(
                "https://dunecardshub.com/images/"
                "bloodlines-conflict-storms-in-the-south.webp"
            ),
        ),
        tier=ConflictTier.TWO,
        battle_icon=BattleIcon.WILD,
        rewards=_rewards("storms_in_the_south"),
        bloodlines_only=True,
    ),
    # Epic Game Mode needs a fifth Conflict III: "In this situation, you
    # should add Economic Supremacy" [Main p. 18] [Rise of Ix p. 10]. Rise of
    # Ix card face: no battle icon, no location; first place 1 VP plus two
    # optional arrows (6 Solari, 4 spice -> 1 VP each).
    ConflictDefinition(
        card=CardDefinition(
            "economic_supremacy",
            "Economic Supremacy",
            (
                SourceRef(SourceDocument.MAIN_RULEBOOK, (18,)),
                SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (10,)),
                SourceRef(SourceDocument.CARD_FACE, (1,)),
            ),
            catalog_url=(
                "https://dunecardshub.com/images/"
                "rise-of-ix-conflict-economic-supremacy.webp"
            ),
        ),
        tier=ConflictTier.THREE,
        rewards=_rewards("economic_supremacy"),
        epic_only=True,
    ),
)


def conflicts_by_tier(
    tier: ConflictTier, *, bloodlines: bool = False, epic_game: bool = False
) -> tuple[ConflictDefinition, ...]:
    """Return the physical Conflict cards with the requested back in the pool."""

    return tuple(
        conflict
        for conflict in CONFLICTS
        if conflict.tier is tier
        and (bloodlines or not conflict.bloodlines_only)
        and (epic_game or not conflict.epic_only)
    )


CONFLICTS_BY_ID: Final = {conflict.card.card_id: conflict for conflict in CONFLICTS}
