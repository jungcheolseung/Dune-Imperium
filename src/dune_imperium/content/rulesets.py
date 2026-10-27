"""The content a ruleset puts on the table, looked up by its configuration.

docs/base-game-and-ix-plan.md 4.2 (items 2 and 7): the engine reads *which*
board spaces, observation posts, decks, Leaders, Conflicts and Objectives a
game uses, and the values its board prints (the Maker spaces, the Influence
4 bonuses), through ``content_for(config)`` instead of importing them as
module constants. A definition is still found by its id in its kind's table
(``BOARD_SPACES_BY_ID``, ``CONFLICTS_BY_ID``, ``personal_card_for_instance``
and the like): an id names one printing, so a space or card printed alike in
two base games shares its id and one printed differently takes its own.

The original Dune: Imperium (``BaseGame.IMPERIUM``) plays on its own board,
Conflicts, Reserve and Leaders (stage P2, ``content.imperium``); its
Imperium and Intrigue decks arrive in stage P3 and are empty until then. Its
starting deck is Uprising's printing [DI p. 3] (docs/rules/imperium-base.md
2).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Final

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS
from dune_imperium.content.imperium.board import (
    IMPERIUM_BOARD_SPACES,
    IMPERIUM_MAKER_SPACE_IDS,
)
from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
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
    RecruitTroops,
)
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    ImperiumCardEntry,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.leaders import (
    LEADERS_BY_ID,
    LeaderDefinition,
    leaders_for_choam,
)
from dune_imperium.content.uprising.objectives import (
    ObjectiveDefinition,
    objectives_for_players,
)
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    ReserveStackDefinition,
)
from dune_imperium.content.uprising.starting_cards import (
    STARTING_CARDS_BY_ID,
    StartingCardEntry,
    starting_deck_entries,
    starting_discard_entries,
    starting_instance_ids,
)
from dune_imperium.content.uprising.types import ConflictTier

# The bonus each Influence track prints on its 4 space (one icon each):
# "When you reach 4 Influence, you earn the bonus shown on that space of
# the track." [Main p. 7] The Uprising strips print the Spy icon (Emperor),
# a 3 on the Solari coin (Spacing Guild), the Intrigue card (Bene Gesserit)
# and the water drop (Fremen) -- read off the board scan against the
# rulebook icons on 2026-09-19 (docs/lessons.md).
InfluenceFourBonus = PlaceSpy | GainResources | DrawIntrigueCards | RecruitTroops
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

# The original board's Influence 4 bonuses [DI p. 7], which only its picture
# prints: two troops (Emperor), 3 Solari (Spacing Guild), an Intrigue card
# (Bene Gesserit) and a water (Fremen) -- the Steam app's
# ``WormFactionTrack::FactionTrackBonusAction``, whose Emperor case places a
# Spy only while the Uprising set is in play (user decision D3, 2026-10-23;
# docs/base-game-and-ix-plan.md 15.3).
IMPERIUM_INFLUENCE_FOUR_BONUSES: Final[Mapping[Faction, InfluenceFourBonus]] = (
    MappingProxyType(
        {
            Faction.EMPEROR: RecruitTroops(2),
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
# The original game's: Arrakeen and Carthag 1 Solari, Imperial Basin 1 spice
# [DI p. 10] (docs/rules/imperium-base.md 7).
IMPERIUM_CONTROL_VISIT_BONUSES: Final[Mapping[str, str]] = MappingProxyType(
    {"arrakeen": "solari", "carthag": "solari", "imperial_basin": "spice"}
)
# The original game's Leaders whose abilities the engine plays, in printed
# order (docs/base-game-and-ix-plan.md 15.1: stage P2a has four, P2b the
# other four).
IMPERIUM_LEADER_IDS: Final = (
    "duke_leto_atreides",
    "glossu_rabban",
    "count_ilban_richese",
    "helena_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
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
    base_game: BaseGame
    # Every board space the base game prints, Leader-only spaces included
    # (a game holds one only while its Leader plays).
    board_spaces: tuple[BoardSpace, ...]
    observation_posts: tuple[ObservationPost, ...]
    # Every Conflict card the base game prints, expansions' included; and
    # the ones this configuration's tiers are drawn from.
    conflicts: tuple[ConflictDefinition, ...]
    conflict_pool: tuple[ConflictDefinition, ...]
    reserve_stacks: tuple[ReserveStackDefinition, ...]
    maker_space_ids: tuple[str, ...]
    sandworm_space_ids: tuple[str, ...]
    control_visit_bonuses: Mapping[str, str]
    influence_four_bonuses: Mapping[Faction, InfluenceFourBonus]
    # Every personal card id the base game prints, whatever the options:
    # starting, Reserve, Imperium and Tleilaxu cards.
    card_ids: frozenset[str]
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
        """The tier's Conflict cards this configuration's deck is drawn from."""

        return tuple(
            conflict for conflict in self.conflict_pool if conflict.tier is tier
        )

    def starting_deck_instance_ids(self, player: int) -> tuple[str, ...]:
        """Seat ``player``'s starting deck, as instance ids."""

        return starting_instance_ids(player, self.starting_deck_entries)

    def starting_discard_instance_ids(self, player: int) -> tuple[str, ...]:
        """The starting cards seat ``player`` begins with in its discard pile."""

        return starting_instance_ids(player, self.starting_discard_entries)

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

    if config.base_game is BaseGame.UPRISING:
        return _uprising_content(config)
    return _imperium_content(config)


def _uprising_content(config: RulesetConfig) -> RulesetContent:
    return RulesetContent(
        config=config,
        base_game=BaseGame.UPRISING,
        board_spaces=BOARD_SPACES,
        observation_posts=OBSERVATION_POSTS,
        conflicts=CONFLICTS,
        conflict_pool=tuple(
            conflict
            for tier in ConflictTier
            for conflict in conflicts_by_tier(
                tier, bloodlines=config.bloodlines, epic_game=config.epic_game
            )
        ),
        reserve_stacks=RESERVE_STACKS,
        maker_space_ids=UPRISING_MAKER_SPACE_IDS,
        sandworm_space_ids=UPRISING_SANDWORM_SPACE_IDS,
        control_visit_bonuses=UPRISING_CONTROL_VISIT_BONUSES,
        influence_four_bonuses=UPRISING_INFLUENCE_FOUR_BONUSES,
        card_ids=_UPRISING_CARD_IDS,
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


_UPRISING_CARD_IDS: Final = frozenset(
    {
        *STARTING_CARDS_BY_ID,
        *(stack.card.card_id for stack in RESERVE_STACKS),
        *(card.card.card_id for card in IMPERIUM_CARDS),
        *(card.card.card_id for card in TLEILAXU_CARDS),
    }
)


def _imperium_content(config: RulesetConfig) -> RulesetContent:
    """The original game's content (module docstring): its board, Conflicts,
    Reserve and Leaders, none of the Objectives, observation posts,
    Contracts or sandworms Uprising prints, and no Imperium or Intrigue deck
    until stage P3."""

    return RulesetContent(
        config=config,
        base_game=BaseGame.IMPERIUM,
        board_spaces=IMPERIUM_BOARD_SPACES,
        observation_posts=(),
        conflicts=IMPERIUM_CONFLICTS,
        conflict_pool=IMPERIUM_CONFLICTS,
        reserve_stacks=IMPERIUM_RESERVE_STACKS,
        maker_space_ids=IMPERIUM_MAKER_SPACE_IDS,
        sandworm_space_ids=(),
        control_visit_bonuses=IMPERIUM_CONTROL_VISIT_BONUSES,
        influence_four_bonuses=IMPERIUM_INFLUENCE_FOUR_BONUSES,
        card_ids=_IMPERIUM_CARD_IDS,
        leaders=tuple(LEADERS_BY_ID[leader_id] for leader_id in IMPERIUM_LEADER_IDS),
        imperium_cards=(),
        imperium_deck_instance_ids=(),
        intrigue_deck_instance_ids=(),
        contract_instance_ids=(),
        objectives=(),
        starting_deck_entries=starting_deck_entries(),
        starting_discard_entries=(),
    )


_IMPERIUM_CARD_IDS: Final = frozenset(
    {
        *(entry.card.card_id for entry in starting_deck_entries()),
        *(stack.card.card_id for stack in IMPERIUM_RESERVE_STACKS),
    }
)
