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

With ``rise_of_ix`` the original game's content takes Rise of Ix's board
axis (stage P4a, docs/base-game-and-ix-plan.md 17.1 and 17.7;
``content.rise_of_ix``): the CHOAM overlay swaps four board spaces, the
Conflicts take Economic Supremacy and the new cards whose rewards are
transcribed, the Leaders offered take the six new ones and the decks take
the Ix cards whose play data is complete. The overlay's spaces have no
effects yet, so setup still refuses the option (``rules.setup``).
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
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
from dune_imperium.content.rise_of_ix.board import IX_BOARD_SPACES
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    BoardSpace,
    Faction,
    ObservationPost,
)
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    CONFLICTS_BY_ID,
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
from dune_imperium.content.uprising.intrigue import (
    IntrigueCardEntry,
    intrigue_deck_instance_ids,
)
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
    "paul_atreides",
    "duke_leto_atreides",
    "glossu_rabban",
    "baron_vladimir_harkonnen",
    "count_ilban_richese",
    "helena_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)

# Rise of Ix's Leaders the engine plays end to end (their setup deviation and
# both abilities wired, stage P4e). A Leader joins the offer -- the fixed
# roster, the rotation and the draft pool of an original + Rise of Ix game --
# only once it is on this list, as a deck card joins its deck only once its
# play data is complete: a Leader with no setup or abilities would make a
# wrong game (Yuna would start with water 1, where docs/rules/rise-of-ix.md 3
# prints 0). ``content.rise_of_ix.leaders.IX_LEADERS`` keeps all six (by-id
# lookups and the observation vocabulary read them), and P4e adds each id
# here as its Leader's abilities land.
IX_LEADER_IDS_OFFERED: Final[frozenset[str]] = frozenset()

# The four original board spaces the CHOAM overlay covers: "Place the CHOAM
# board overlay on top of the upper right corner of your original game board
# (covering the original Landsraad and CHOAM sections)" [Rise of Ix p. 3]
# (docs/rules/rise-of-ix.md 3 item 1). The Steam app removes these four from
# the set (``RemovedFromSetList``) and the overlay prints Rise of Ix's four
# [Rise of Ix p. 12] (``content.rise_of_ix.board``); Mentat, Swordmaster and
# High Council stay.
IX_OVERLAID_SPACE_IDS: Final = (
    "hall_of_oratory",
    "rally_troops",
    "secure_contract",
    "sell_melange",
)
# Rise of Ix's Conflict III is Economic Supremacy, which Uprising's table
# already holds as its Epic card (``content.uprising.conflicts``).
_IX_CONFLICT_THREE_ID: Final = "economic_supremacy"


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
    # Every Conflict card the engine plays with this base game, expansions'
    # included; and the ones this configuration's tiers are drawn from. An
    # original-game Conflict from Rise of Ix joins both only once its reward
    # rows are transcribed (``reward_rows``), as a deck card joins its deck
    # only once its play data is complete.
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

    def conflicts_in_play(self) -> tuple[ConflictDefinition, ...]:
        """The ``conflicts`` this configuration's deck can draw, in their
        order: Uprising's Bloodlines and Epic cards only with their option,
        and Economic Supremacy in every original game with Rise of Ix [Rise
        of Ix p. 3] (docs/rules/rise-of-ix.md 3 item 3), which the pool holds
        and the Uprising flags would not."""

        in_pool = {conflict.card.card_id for conflict in self.conflict_pool}
        return tuple(
            conflict for conflict in self.conflicts if conflict.card.card_id in in_pool
        )

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
    Contracts or sandworms Uprising prints; its Imperium and Intrigue decks
    hold the cards transcribed so far (stage P3). With ``rise_of_ix`` the
    board, Conflicts, Leaders and decks take Rise of Ix's (stage P4a)."""

    rise_of_ix = config.rise_of_ix
    conflicts = _imperium_conflicts(rise_of_ix)
    imperium_cards = _imperium_deck_cards(config.promo_cards, rise_of_ix)
    return RulesetContent(
        config=config,
        base_game=BaseGame.IMPERIUM,
        board_spaces=_imperium_board_spaces(rise_of_ix),
        observation_posts=(),
        conflicts=conflicts,
        conflict_pool=conflicts,
        reserve_stacks=IMPERIUM_RESERVE_STACKS,
        maker_space_ids=IMPERIUM_MAKER_SPACE_IDS,
        sandworm_space_ids=(),
        control_visit_bonuses=IMPERIUM_CONTROL_VISIT_BONUSES,
        influence_four_bonuses=IMPERIUM_INFLUENCE_FOUR_BONUSES,
        card_ids=_imperium_card_ids(rise_of_ix),
        leaders=_imperium_leaders(rise_of_ix),
        imperium_cards=imperium_cards,
        imperium_deck_instance_ids=tuple(
            f"imperium:{entry.card.card_id}:{copy}"
            for entry in imperium_cards
            for copy in range(entry.copies)
        ),
        intrigue_deck_instance_ids=tuple(
            f"intrigue:{entry.card.card_id}:{copy}"
            for entry in _imperium_intrigue_cards(rise_of_ix)
            for copy in range(entry.copies)
        ),
        contract_instance_ids=(),
        objectives=(),
        starting_deck_entries=starting_deck_entries(),
        starting_discard_entries=(),
    )


@cache
def _imperium_board_spaces(rise_of_ix: bool) -> tuple[BoardSpace, ...]:
    """The original board; with Rise of Ix the original order with the four
    overlaid spaces removed, then the overlay's four as it prints them
    (Dreadnought, Tech Negotiation, Interstellar Shipping, Smuggling)."""

    if not rise_of_ix:
        return IMPERIUM_BOARD_SPACES
    return (
        *(
            space
            for space in IMPERIUM_BOARD_SPACES
            if space.space_id not in IX_OVERLAID_SPACE_IDS
        ),
        *IX_BOARD_SPACES,
    )


@cache
def _imperium_conflicts(rise_of_ix: bool) -> tuple[ConflictDefinition, ...]:
    """The Conflict cards the game draws its tiers from: the original 18
    (I 4, II 10, III 4 [DI p. 3]); with Rise of Ix its four more are added
    "to those you already have", I 6, II 11, III 5, and the deck keeps the
    shape I 1, II 5, III 4 with one III returned to the box [Rise of Ix
    p. 3] (docs/rules/rise-of-ix.md 3 item 3). Economic Supremacy, Rise of
    Ix's Conflict III, is in every such game, Epic or not; the two Skirmishes
    and Trade Monopoly join once their reward rows are transcribed (stage
    P4c/P4d), as the decks take a card only once its play data is complete.
    Tier by tier: the original cards, then Rise of Ix's in printed order."""

    if not rise_of_ix:
        return IMPERIUM_CONFLICTS
    added = (
        *(conflict for conflict in IX_CONFLICTS if conflict.reward_rows is not None),
        CONFLICTS_BY_ID[_IX_CONFLICT_THREE_ID],
    )
    return tuple(
        conflict
        for tier in ConflictTier
        for conflict in (*IMPERIUM_CONFLICTS, *added)
        if conflict.tier is tier
    )


@cache
def _imperium_leaders(rise_of_ix: bool) -> tuple[LeaderDefinition, ...]:
    """The Leaders the engine plays; with Rise of Ix the new ones follow
    ("players may choose any combination of new or existing Leaders" [Rise
    of Ix p. 3]) as they are complete (``IX_LEADER_IDS_OFFERED``; none
    yet, so the offer is the original eight)."""

    original = tuple(LEADERS_BY_ID[leader_id] for leader_id in IMPERIUM_LEADER_IDS)
    if not rise_of_ix:
        return original
    return (
        *original,
        *(
            leader
            for leader in IX_LEADERS
            if leader.leader_id in IX_LEADER_IDS_OFFERED
        ),
    )


@cache
def _imperium_intrigue_cards(rise_of_ix: bool) -> tuple[IntrigueCardEntry, ...]:
    """The Intrigue cards whose play data is complete; with Rise of Ix its
    17 are "shuffled into the Intrigue Deck" [Rise of Ix p. 3] as they
    land (none yet)."""

    entries = (
        (*IMPERIUM_INTRIGUE_CARDS, *IX_INTRIGUE_CARDS)
        if rise_of_ix
        else IMPERIUM_INTRIGUE_CARDS
    )
    return tuple(entry for entry in entries if entry.play_data_complete)


# Stage P3 (plan 16.1): the original decks hold the cards transcribed so far,
# so a soak plays each one as it lands; the three promos (Duncan, Loyal Blade;
# Jessica of Arrakis; Thumper) are shuffled in only with ``promo_cards`` (plan
# 9 8), as Uprising's promos are (``imperium_cards_for_choam``). With Rise of
# Ix its 35 Imperium cards are shuffled in before the Row is formed [Rise of
# Ix p. 3], those transcribed so far, and its promo (Boundless Ambition)
# behind ``promo_cards`` too (plan 9 8).
@cache
def _imperium_deck_cards(
    promo_cards: bool, rise_of_ix: bool = False
) -> tuple[ImperiumCardEntry, ...]:
    entries = (
        (*IMPERIUM_BASE_CARDS, *IX_IMPERIUM_CARDS)
        if rise_of_ix
        else IMPERIUM_BASE_CARDS
    )
    return tuple(
        entry
        for entry in entries
        if entry.play_data_complete and (promo_cards or not entry.promo)
    )


# Every personal card id the base game prints, the promos' whatever the
# options (as ``_UPRISING_CARD_IDS``); Rise of Ix's with its option.
@cache
def _imperium_card_ids(rise_of_ix: bool) -> frozenset[str]:
    return frozenset(
        {
            *(entry.card.card_id for entry in starting_deck_entries()),
            *(stack.card.card_id for stack in IMPERIUM_RESERVE_STACKS),
            *(entry.card.card_id for entry in _imperium_deck_cards(True, rise_of_ix)),
        }
    )
