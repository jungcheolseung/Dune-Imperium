"""The content a ruleset puts on the table, looked up by its configuration.

docs/base-game-and-ix-plan.md 4.2 (items 2 and 7): the engine reads *which*
board spaces, observation posts, decks, Leaders, Conflicts and Objectives a
game uses, and the values its board prints (the Maker spaces, the Influence
4 bonuses), through ``content_for(config)`` instead of importing them as
module constants. A definition is still found by its id in its kind's table
(``BOARD_SPACES_BY_ID``, ``CONFLICTS_BY_ID``, ``personal_card_for_instance``
and the like): an id names one printing, so a space or card printed alike in
two base games shares its id and one printed differently takes its own.

Every ruleset is Uprising's for now, so this returns Uprising's tables.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Final

from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    BoardSpace,
    Faction,
    ObservationPost,
)
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    ConflictDefinition,
    conflicts_by_tier,
)
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    GainResources,
    PlaceSpy,
)
from dune_imperium.content.uprising.imperium import (
    ImperiumCardEntry,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.leaders import LeaderDefinition, leaders_for_choam
from dune_imperium.content.uprising.objectives import (
    ObjectiveDefinition,
    objectives_for_players,
)
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    ReserveStackDefinition,
)
from dune_imperium.content.uprising.starting_cards import (
    StartingCardEntry,
    starting_deck_entries,
    starting_deck_instance_ids,
    starting_discard_entries,
    starting_discard_instance_ids,
)
from dune_imperium.content.uprising.types import ConflictTier

# The bonus each Influence track prints on its 4 space (one icon each):
# "When you reach 4 Influence, you earn the bonus shown on that space of
# the track." [Main p. 7] The Uprising strips print the Spy icon (Emperor),
# a 3 on the Solari coin (Spacing Guild), the Intrigue card (Bene Gesserit)
# and the water drop (Fremen) -- read off the board scan against the
# rulebook icons on 2026-09-19 (docs/lessons.md).
InfluenceFourBonus = PlaceSpy | GainResources | DrawIntrigueCards
UPRISING_INFLUENCE_FOUR_BONUSES: Final[Mapping[Faction, InfluenceFourBonus]] = (
    MappingProxyType(
        {
            Faction.EMPEROR: PlaceSpy(),
            Faction.SPACING_GUILD: GainResources(solari=3),
            Faction.BENE_GESSERIT: DrawIntrigueCards(1),
            Faction.FREMEN: GainResources(water=1),
        }
    )
)

# The Maker board spaces in rules order [Main p. 13]; Tuek's Sietch joins
# them while Esmar Tuek plays [Bloodlines p. 12]. Deep Desert and Hagga
# Basin print "with Maker Hooks, summon sandworms" [Board Guide pp. 1-2].
UPRISING_MAKER_SPACE_IDS: Final = ("deep_desert", "hagga_basin", "imperial_basin")
UPRISING_SANDWORM_SPACE_IDS: Final = ("deep_desert", "hagga_basin")
TUEK_SIETCH: Final = "tuek_sietch"

# While a seat controls Arrakeen or Spice Refinery, any Agent sent there
# earns it 1 Solari; Imperial Basin's bonus is 1 spice [Main p. 10]. The
# resource each controlled space pays, by space.
UPRISING_CONTROL_VISIT_BONUSES: Final[Mapping[str, str]] = MappingProxyType(
    {"arrakeen": "solari", "spice_refinery": "solari", "imperial_basin": "spice"}
)


@dataclass(frozen=True, slots=True)
class RulesetContent:
    """What one configuration's game is played with.

    The ``*_universe`` style fields (``board_spaces``, ``conflicts``,
    ``reserve_stacks``) hold everything the base game prints, as the codec
    and the setup filter them by option themselves; the others are already
    filtered by the configuration's options.
    """

    config: RulesetConfig
    # Every board space the base game prints, Leader-only spaces included
    # (a game holds one only while its Leader plays).
    board_spaces: tuple[BoardSpace, ...]
    observation_posts: tuple[ObservationPost, ...]
    # Every Conflict card the base game prints, expansions' included.
    conflicts: tuple[ConflictDefinition, ...]
    reserve_stacks: tuple[ReserveStackDefinition, ...]
    maker_space_ids: tuple[str, ...]
    sandworm_space_ids: tuple[str, ...]
    control_visit_bonuses: Mapping[str, str]
    influence_four_bonuses: Mapping[Faction, InfluenceFourBonus]
    # Filtered by the configuration's options.
    leaders: tuple[LeaderDefinition, ...]
    imperium_cards: tuple[ImperiumCardEntry, ...]
    imperium_deck_instance_ids: tuple[str, ...]
    intrigue_deck_instance_ids: tuple[str, ...]
    contract_instance_ids: tuple[str, ...]
    objectives: tuple[ObjectiveDefinition, ...]
    starting_deck_entries: tuple[StartingCardEntry, ...]
    starting_discard_entries: tuple[StartingCardEntry, ...]

    def conflicts_by_tier(self, tier: ConflictTier) -> tuple[ConflictDefinition, ...]:
        """The tier's Conflict cards in this configuration's deck."""

        return conflicts_by_tier(
            tier, bloodlines=self.config.bloodlines, epic_game=self.config.epic_game
        )

    def starting_deck_instance_ids(self, player: int) -> tuple[str, ...]:
        """Seat ``player``'s starting deck, as instance ids."""

        return starting_deck_instance_ids(
            player, immortality=self.config.immortality, epic_game=self.config.epic_game
        )

    def starting_discard_instance_ids(self, player: int) -> tuple[str, ...]:
        """The starting cards seat ``player`` begins with in its discard pile."""

        return starting_discard_instance_ids(
            player, immortality=self.config.immortality, epic_game=self.config.epic_game
        )

    def maker_bonus_spice_for(
        self, leader_ids: tuple[str, ...]
    ) -> tuple[tuple[str, int], ...]:
        """The empty Maker spice ledger, with Tuek's Sietch while Esmar plays."""

        spaces = list(self.maker_space_ids)
        if "esmar_tuek" in leader_ids:
            # "During setup, place the Tuek's Sietch board space near the
            # game board. It is a Maker board space" [Bloodlines p. 12].
            spaces.append(TUEK_SIETCH)
        return tuple((space_id, 0) for space_id in spaces)


@cache
def content_for(config: RulesetConfig) -> RulesetContent:
    """The content ``config``'s game is played with (built once per config)."""

    return RulesetContent(
        config=config,
        board_spaces=BOARD_SPACES,
        observation_posts=OBSERVATION_POSTS,
        conflicts=CONFLICTS,
        reserve_stacks=RESERVE_STACKS,
        maker_space_ids=UPRISING_MAKER_SPACE_IDS,
        sandworm_space_ids=UPRISING_SANDWORM_SPACE_IDS,
        control_visit_bonuses=UPRISING_CONTROL_VISIT_BONUSES,
        influence_four_bonuses=UPRISING_INFLUENCE_FOUR_BONUSES,
        leaders=leaders_for_choam(
            config.choam_module,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
        ),
        imperium_cards=imperium_cards_for_choam(
            config.choam_module,
            config.promo_cards,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=config.immortality,
        ),
        imperium_deck_instance_ids=imperium_deck_instance_ids(
            config.choam_module,
            config.promo_cards,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=config.immortality,
        ),
        intrigue_deck_instance_ids=intrigue_deck_instance_ids(
            config.choam_module,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=config.immortality,
        ),
        contract_instance_ids=contract_instance_ids(bloodlines=config.bloodlines),
        objectives=objectives_for_players(config.players),
        starting_deck_entries=starting_deck_entries(
            immortality=config.immortality, epic_game=config.epic_game
        ),
        starting_discard_entries=starting_discard_entries(
            immortality=config.immortality, epic_game=config.epic_game
        ),
    )
