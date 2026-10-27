"""Uprising Conflict identities and tiers used to build the ten-card deck."""

from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import Ability, AbilityStructure
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
    TakeMentat,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier

type RewardRows = tuple[Ability, Ability, Ability]


@dataclass(frozen=True, slots=True)
class ConflictDefinition:
    """Conflict identity, battle icon, and optional transcribed reward rows."""

    card: CardDefinition
    tier: ConflictTier
    # ``None``: the card prints no battle icon (Economic Supremacy; OQ-094).
    battle_icon: BattleIcon | None = None
    shield_wall_protected: bool = False
    # The first, second and third place rows as their ability records
    # (``conflict_abilities``): what the payer, the card text and the codec
    # read. ``None``: the rows are not transcribed.
    reward_rows: RewardRows | None = None
    # Added to the tier pool only with ``RulesetConfig(bloodlines=True)``
    # [Bloodlines p. 3].
    bloodlines_only: bool = False
    # Added to the tier pool only with ``RulesetConfig(epic_game=True)``
    # [Main p. 18].
    epic_only: bool = False

    def __post_init__(self) -> None:
        for row in self.reward_rows or ():
            check_conflict_reward_row(row)

    @property
    def control_space_id(self) -> str | None:
        """The board space the first place takes control of, if it does."""

        if self.reward_rows is None:
            return None
        for line in self.reward_rows[0].sections:
            for reward in line.rewards:
                if isinstance(reward, TakeControl):
                    return reward.space_id
        return None


def _rewards(conflict_id: str) -> RewardRows:
    """The card's three reward rows: its records (``conflict_abilities``,
    composed A5b)."""

    first, second, third = CONFLICT_REWARD_ABILITIES[conflict_id]
    return first, second, third


def check_conflict_reward_row(row: Ability) -> None:
    """Refuse a reward row the payer and the card text cannot read.

    A row's lines print no condition. A line with a cost is an optional
    "cost -> VP" arrow [FAQ p. 3] (Solari, spice, or Spies recalled), and a
    row's arrows share one VP value (Economic Supremacy prints two). The other
    lines give resources, Intrigue cards, troops, Spies (with or without Deep
    Cover), Contracts, trashes, VP, chosen, distinct or one Faction's
    Influence, or control of a space; each is printed once on the row but
    Spies, trashes and chosen Influence, which may repeat. A row gives
    something. (The checks the compiled ``ConflictReward`` ran until the
    reward totals cleanup, 2026-10-21.)

    The original game adds the Mentat icon, one Faction's two Influence and
    rows of alternatives: a printed "-OR-" (``ONE_OF``) or "Choose two:"
    (``CHOOSE_TWO``) row's lines are each checked as a row of their own, with
    no arrow, and offer at least as many lines as are taken.
    """

    if row.structure in (AbilityStructure.ONE_OF, AbilityStructure.CHOOSE_TWO):
        taken = 2 if row.structure is AbilityStructure.CHOOSE_TWO else 1
        if len(row.sections) <= taken:
            raise ValueError("a Conflict reward row of alternatives offers too few")
        for line in row.sections:
            if line.costs:
                raise ValueError("a Conflict reward alternative prints no arrow")
            check_conflict_reward_row(
                replace(row, sections=(line,), structure=AbilityStructure.SEQUENCE)
            )
        return
    if row.structure is not AbilityStructure.SEQUENCE:
        raise ValueError(f"a Conflict reward row is not {row.structure}")
    printed: set[str] = set()

    def once(key: str) -> None:
        if key in printed:
            raise ValueError(f"a Conflict reward row prints {key} twice")
        printed.add(key)

    arrow_points: set[int] = set()
    gives = False
    for line in row.sections:
        if line.condition is not None:
            raise ValueError("a Conflict reward row prints no condition")
        if line.costs:
            match line.costs, line.rewards:
                case (PayResources(solari=solari, spice=0, water=0),), (
                    GainVictoryPoints(amount=points),
                ) if solari:
                    once("optional_solari_cost")
                case (PayResources(solari=0, spice=spice, water=0),), (
                    GainVictoryPoints(amount=points),
                ) if spice:
                    once("optional_spice_cost")
                case (RecallSpy(),), (GainVictoryPoints(amount=points),):
                    once("optional_recall_spies")
                case _:
                    raise TypeError(f"{line!r} is not a Conflict reward arrow")
            arrow_points.add(points)
            gives = True
            continue
        for reward in line.rewards:
            match reward:
                case GainResources(solari=solari, spice=spice, water=water):
                    once("resources")
                    if min(solari, spice, water) < 0:
                        raise ValueError(
                            "Conflict reward quantities must not be negative"
                        )
                case DrawIntrigueCards():
                    once("intrigue")
                case RecruitTroops():
                    once("troops")
                case PlaceSpy() if reward in (PlaceSpy(), PlaceSpy(shared_post=True)):
                    pass
                case TakeContract():
                    once("contracts")
                case TrashPersonalCard() if reward == TrashPersonalCard():
                    pass
                case GainVictoryPoints():
                    once("victory_points")
                case GainInfluence(one_faction=True) if reward == replace(
                    reward, factions=None, distinct=False
                ) and reward.times > 1 and not reward.where_opponent_leads:
                    once("one_faction_influence")
                case GainInfluence() if reward == GainInfluence(
                    times=reward.times, distinct=True
                ):
                    once("choose_distinct_influence")
                case TakeMentat():
                    once("mentat")
                case GainInfluence(times=times, factions=(faction,)) if (
                    reward == GainInfluence(times=times, factions=(faction,))
                ):
                    once("faction_influence")
                case GainInfluence() if reward == GainInfluence():
                    pass
                case TakeControl(space_id=space_id):
                    if not space_id:
                        raise ValueError("control space ID must not be empty")
                    once("control")
                case _:
                    raise TypeError(f"{reward!r} is not a Conflict reward")
            gives = True
    if len(arrow_points) > 1:
        raise ValueError("a Conflict reward row's arrows share one VP value")
    if not gives:
        raise ValueError("a Conflict reward row must contain a reward")


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
    reward_rows: RewardRows | None = None,
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
        reward_rows=reward_rows,
    )


CONFLICTS: Final = (
    _conflict(
        451,
        "skirmish_crysknife",
        "Skirmish (Crysknife)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.CRYSKNIFE,
        reward_rows=_rewards("skirmish_crysknife"),
    ),
    _conflict(
        452,
        "skirmish_ornithopter",
        "Skirmish (Ornithopter)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.ORNITHOPTER,
        reward_rows=_rewards("skirmish_ornithopter"),
    ),
    _conflict(
        453,
        "skirmish_desert_mouse",
        "Skirmish (Desert Mouse)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        reward_rows=_rewards("skirmish_desert_mouse"),
    ),
    _conflict(
        454,
        "choam_security",
        "CHOAM Security",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        reward_rows=_rewards("choam_security"),
    ),
    _conflict(
        455,
        "spice_freighters",
        "Spice Freighters",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        reward_rows=_rewards("spice_freighters"),
    ),
    _conflict(
        456,
        "siege_of_arrakeen",
        "Siege of Arrakeen",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        reward_rows=_rewards("siege_of_arrakeen"),
    ),
    _conflict(
        457,
        "seize_spice_refinery",
        "Seize Spice Refinery",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        reward_rows=_rewards("seize_spice_refinery"),
    ),
    _conflict(
        458,
        "test_of_loyalty",
        "Test of Loyalty",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        reward_rows=_rewards("test_of_loyalty"),
    ),
    _conflict(
        459,
        "shadow_contest",
        "Shadow Contest",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        reward_rows=_rewards("shadow_contest"),
    ),
    _conflict(
        460,
        "secure_imperial_basin",
        "Secure Imperial Basin",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        reward_rows=_rewards("secure_imperial_basin"),
    ),
    _conflict(
        461,
        "protect_the_sietches",
        "Protect the Sietches",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        reward_rows=_rewards("protect_the_sietches"),
    ),
    _conflict(
        462,
        "trade_dispute",
        "Trade Dispute",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        reward_rows=_rewards("trade_dispute"),
    ),
    _conflict(
        463,
        "propaganda",
        "Propaganda",
        ConflictTier.THREE,
        battle_icon=BattleIcon.WILD,
        reward_rows=_rewards("propaganda"),
    ),
    _conflict(
        464,
        "battle_for_imperial_basin",
        "Battle for Imperial Basin",
        ConflictTier.THREE,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        reward_rows=_rewards("battle_for_imperial_basin"),
    ),
    _conflict(
        465,
        "battle_for_arrakeen",
        "Battle for Arrakeen",
        ConflictTier.THREE,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        reward_rows=_rewards("battle_for_arrakeen"),
    ),
    _conflict(
        466,
        "battle_for_spice_refinery",
        "Battle for Spice Refinery",
        ConflictTier.THREE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        reward_rows=_rewards("battle_for_spice_refinery"),
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
        reward_rows=_rewards("skirmish_wild"),
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
        reward_rows=_rewards("storms_in_the_south"),
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
        reward_rows=_rewards("economic_supremacy"),
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


# One table for both base games (docs/base-game-and-ix-plan.md 4.2 item 7):
# the original game's cards follow Uprising's. Imported last, as they are
# built from ``ConflictDefinition`` (``content.imperium``).
from dune_imperium.content.imperium.conflicts import (  # noqa: E402
    IMPERIUM_CONFLICTS,
)

CONFLICTS_BY_ID: Final = {
    conflict.card.card_id: conflict for conflict in (*CONFLICTS, *IMPERIUM_CONFLICTS)
}
