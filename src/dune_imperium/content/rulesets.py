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
transcribed, the Leaders offered take the new ones whose abilities are wired
(``IX_LEADER_IDS_OFFERED``, stage P4e) and the decks take the Ix
cards whose play data is complete. Setup takes the option on the original
game since stage P4c-5 (``rules.setup``) and on Uprising since stage P7f
(``_with_rise_of_ix``: the half overlay over Assembly Hall and Gather
Support, the two observation posts [Main p. 18], Rise of Ix's cards and
Leaders, and the original Foldspace stack for Ilesa Ecaz).

With ``ix_leaders`` (Rise of Ix's Leaders and Tech tiles beside the Tech
Module, docs/base-game-and-ix-plan.md 20.5 P8-1) either board offers the
four Rise of Ix Leaders who need no Ix board
(``IX_LEADER_IDS_WITHOUT_IX_BOARD``, OQ-165), and Uprising's Reserve takes
the Foldspace stack for Ilesa Ecaz as with all of Rise of Ix; nothing else
of Rise of Ix joins (``ix_tech_tiles`` is a Tech tile pool,
``content.bloodlines.tech.tech_tile_pool``).

With ``bloodlines`` (and its ``tech_module``) the original game takes the
Bloodlines cards and Leaders the rulebook keeps for it (stage P7c,
docs/rules/bloodlines.md 2a, [Bloodlines p. 3]) and Esmar Tuek's Tuek's
Sietch; no Bloodlines Conflict card and no CHOAM component.

With ``imperium_cards`` an Uprising game takes the original game's Imperium
and Intrigue cards and Leaders (stage P7e, docs/rules/imperium-base.md 13.4):
``_with_original_cards``; ``RulesetContent.original_cards`` tells the codec and
the rules a game holds them, whichever board it is played on.
"""

from collections.abc import Mapping
from copy import replace
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Final

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.core.board import BoardSpace, ObservationPost
from dune_imperium.content.core.cards import (
    ConflictDefinition,
    ImperiumCardEntry,
    IntrigueCardEntry,
    LeaderDefinition,
    ReserveStackDefinition,
    StartingCardEntry,
)
from dune_imperium.content.core.effects import (
    DrawIntrigueCards,
    GainResources,
    PlaceSpy,
    RecruitTroops,
)
from dune_imperium.content.core.icons import ConflictTier, Faction
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS
from dune_imperium.content.imperium.board import IMPERIUM_MAKER_SPACE_IDS
from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
from dune_imperium.content.registry.board import (
    BOARD_SPACES_BY_ID,
    IMPERIUM_BOARD_SPACES,
)
from dune_imperium.content.registry.conflicts import (
    CONFLICTS,
    CONFLICTS_BY_ID,
    conflicts_by_tier,
)
from dune_imperium.content.registry.contracts import (
    contract_instance_ids,
    ix_contract_instance_ids,
)
from dune_imperium.content.registry.imperium import (
    IMPERIUM_CARDS,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.registry.intrigue import (
    INTRIGUE_CARDS,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.registry.leaders import (
    LEADERS,
    LEADERS_BY_ID,
    leaders_for_choam,
)
from dune_imperium.content.rise_of_ix.board import (
    IX_BOARD_SPACES,
    IX_OBSERVATION_POSTS,
)
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.uprising.board import BOARD_SPACES, OBSERVATION_POSTS
from dune_imperium.content.uprising.objectives import (
    ObjectiveDefinition,
    objectives_for_players,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    EXPERIMENTATION,
    STARTING_CARDS_BY_ID,
    starting_deck_entries,
    starting_discard_entries,
    starting_instance_ids,
)

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
# (Bene Gesserit) and a water (Fremen) -- as the Steam app gives them; its
# Emperor bonus places a Spy only while the Uprising set is in play (user
# decision D3, 2026-10-23; docs/base-game-and-ix-plan.md 15.3).
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
IX_LEADER_IDS_OFFERED: Final[frozenset[str]] = frozenset(
    {
        "princess_yuna_moritani",
        "prince_rhombur_vernius",
        "archduke_armand_ecaz",
        "viscount_hundro_moritani",
        "ilesa_ecaz",
        "tessia_vernius",
    }
)

# Rise of Ix's Leaders a game without the Ix board offers (``ix_leaders``,
# the Game Room app's "I'm using only the Leaders and Tech tiles from Rise of
# Ix."): OQ-165, user ruling 2026-11-01 (project convention -- no official
# document plays Rise of Ix's Leaders without its board, docs/base-game-and-
# ix-plan.md 20.5). Viscount Hundro Moritani (Couriers: spice 1 -> Freighter,
# with no Shipping track) and Prince Rhombur Vernius (Heavy Lasgun Cannons'
# dreadnoughts, Ixian Technology's Tech Negotiation, with no Ix board) are
# left out; the four here call no Ix component (docs/rules/rise-of-ix.md 10).
IX_LEADER_IDS_WITHOUT_IX_BOARD: Final[frozenset[str]] = frozenset(
    {
        "princess_yuna_moritani",
        "archduke_armand_ecaz",
        "ilesa_ecaz",
        "tessia_vernius",
    }
)


def ix_leader_ids(config: RulesetConfig) -> frozenset[str]:
    """Rise of Ix's Leaders ``config``'s game offers: all six with all of
    Rise of Ix, the four that need no Ix board with ``ix_leaders``, none
    otherwise."""

    if config.rise_of_ix:
        return IX_LEADER_IDS_OFFERED
    if config.ix_leaders:
        return IX_LEADER_IDS_WITHOUT_IX_BOARD
    return frozenset()


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
# On Uprising's board the overlay is "folded in half" and covers "only the
# top-right corner of the UPRISING board. This will create a new CHOAM
# section and cover the Assembly Hall and Gather Support board spaces in the
# Landsraad, while leaving the rest of the Landsraad board spaces in UPRISING
# unchanged." [Main p. 18] (docs/rules/rise-of-ix.md 17, stage P7f). The new
# CHOAM section lies over Uprising's in that corner, Shipping and Accept
# Contract: "The RISE OF IX expansion replaces one of the locations on the
# UPRISING board where you can take a new contract." [Main p. 16] (Accept
# Contract; the other is Dutiful Service), and House Hagal with Rise of Ix
# "Remove these 5 UPRISING cards: Accept Contract/Shipping (2 copies), Gather
# Support (2 copies), and Assembly Hall." [Supplements p. 6] (user
# 2026-10-30 "shipping / accept contract 도 가려지잖아").
UPRISING_IX_OVERLAID_SPACE_IDS: Final = (
    "assembly_hall",
    "gather_support",
    "shipping",
    "accept_contract",
)
# The original game's Foldspace stack: "Using Ilesa Ecaz requires the
# Foldspace cards from DUNE: IMPERIUM. (Allow Ilesa Ecaz to acquire Foldspace
# cards, even though they can't be acquired by anyone else.)" [Main p. 18].
# The stack is ``icon_only`` (no Reserve purchase reaches it) and only her
# Guild Contacts acquires it on Uprising's board, which prints no Foldspace
# space.
_FOLDSPACE_STACK_ID: Final = "foldspace_card"


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
    # The Contract bank's tiles (standard, and Bloodlines' with its option).
    contract_instance_ids: tuple[str, ...]
    objectives: tuple[ObjectiveDefinition, ...]
    starting_deck_entries: tuple[StartingCardEntry, ...]
    starting_discard_entries: tuple[StartingCardEntry, ...]
    # Whether the original game's Imperium and Intrigue cards and its Leaders
    # are in the game: every original game, and an Uprising game with
    # ``RulesetConfig.imperium_cards`` (docs/rules/imperium-base.md 13.4).
    # What the original *board* prints is ``base_game``'s.
    original_cards: bool = False
    # The ten Rise of Ix Contract tiles an Uprising game with Rise of Ix deals
    # at setup when the CHOAM Module is on [Main p. 16] -- never in the bank
    # (stage P7f-2, ``rules.starting_contracts``); () in every other game.
    ix_contract_instance_ids: tuple[str, ...] = ()

    @property
    def all_contract_instance_ids(self) -> tuple[str, ...]:
        """Every Contract tile a seat may hold: the bank's, then the Rise of
        Ix tiles dealt at setup."""

        return (*self.contract_instance_ids, *self.ix_contract_instance_ids)

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
    """Uprising's content; with ``imperium_cards`` the original game's
    Imperium and Intrigue cards (Calculated Hire left out) and its Leaders
    follow Uprising's own (``_with_original_cards``)."""

    content = RulesetContent(
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
    if config.imperium_cards:
        content = _with_original_cards(content)
    if config.rise_of_ix:
        return _with_rise_of_ix(content)
    if config.ix_leaders:
        return _with_ix_leaders(content)
    return content


def uprising_ix_observation_posts() -> tuple[ObservationPost, ...]:
    """Uprising's posts on its board with Rise of Ix: those the half overlay
    leaves, then the two [Main p. 18] counts on the overlay and the Ix board.

    "keep the CHOAM board overlay folded in half and cover only the top-right
    corner of the UPRISING board" and "Play as if there is one observation
    post on each of those boards" [Main p. 18] (OQ-159, resolved by the
    rulebook, user 2026-10-30): the corner covered holds the Landsraad post
    ``landsraad-assembly-hall-gather-support`` and the CHOAM post
    ``choam-shipping-accept-contract``, each connecting to covered spaces
    alone (``display.board_layout`` draws them there), and the one post left
    in that corner is the overlay's own. The engine drops a
    post whose every space the overlay covers; a post the overlay covers only
    in part would need a ruling, and none does."""

    covered = frozenset(UPRISING_IX_OVERLAID_SPACE_IDS)
    kept = []
    for post in OBSERVATION_POSTS:
        spaces = set(post.connected_space_ids)
        if spaces <= covered:
            continue
        if spaces & covered:
            message = f"the overlay covers part of {post.post_id}"
            raise AssertionError(message)
        kept.append(post)
    return (*kept, *IX_OBSERVATION_POSTS)


def _with_rise_of_ix(content: RulesetContent) -> RulesetContent:
    """An Uprising game with Rise of Ix (stage P7f, docs/rules/rise-of-ix.md
    17, docs/base-game-and-ix-plan.md 19.2 P7f).

    The board loses the two spaces the half overlay covers and takes Rise of
    Ix's four after Uprising's (as the original game takes them after its
    own, ``_imperium_board_spaces``); the posts are
    ``uprising_ix_observation_posts``. Rise of Ix's Imperium and Intrigue
    cards and Leaders follow the deck's others in their printed order
    ("Shuffle the Rise of Ix Imperium cards into the Imperium Deck" and its
    Intrigue cards [Rise of Ix p. 3], the Leaders as they are complete,
    ``IX_LEADER_IDS_OFFERED``), Boundless Ambition with ``promo_cards``. The
    Conflict cards stay Uprising's: "We recommend that you do not add the
    Conflict cards from RISE OF IX" [Main p. 18] and the user chose not to
    (plan 19.4 P7-3 (가)); Epic Game Mode's Economic Supremacy is Uprising's
    Epic card already (``conflicts_by_tier``). The Reserve takes the original
    Foldspace stack for Ilesa Ecaz [Main p. 18] (``_FOLDSPACE_STACK_ID``).
    Control the Spice, the Epic starting card, is in Uprising's ids
    already."""

    config = content.config
    imperium_cards = tuple(
        entry
        for entry in IX_IMPERIUM_CARDS
        if entry.play_data_complete
        and (config.promo_cards or GameOption.PROMO_CARDS not in entry.requires)
    )
    intrigue_cards = tuple(
        entry for entry in IX_INTRIGUE_CARDS if entry.play_data_complete
    )
    covered = frozenset(UPRISING_IX_OVERLAID_SPACE_IDS)
    foldspace = _foldspace_stack()
    return replace(
        content,
        board_spaces=(
            *(
                space
                for space in content.board_spaces
                if space.space_id not in covered
            ),
            *IX_BOARD_SPACES,
        ),
        observation_posts=uprising_ix_observation_posts(),
        ix_contract_instance_ids=ix_contract_instance_ids(rise_of_ix=True),
        reserve_stacks=(*content.reserve_stacks, foldspace),
        card_ids=content.card_ids
        | {entry.card.card_id for entry in IX_IMPERIUM_CARDS}
        | {_FOLDSPACE_STACK_ID},
        leaders=(
            *content.leaders,
            *(
                leader
                for leader in IX_LEADERS
                if leader.leader_id in IX_LEADER_IDS_OFFERED
            ),
        ),
        imperium_cards=(*content.imperium_cards, *imperium_cards),
        imperium_deck_instance_ids=(
            *content.imperium_deck_instance_ids,
            *(
                f"imperium:{entry.card.card_id}:{copy}"
                for entry in imperium_cards
                for copy in range(entry.copies)
            ),
        ),
        intrigue_deck_instance_ids=(
            *content.intrigue_deck_instance_ids,
            *(
                f"intrigue:{entry.card.card_id}:{copy}"
                for entry in intrigue_cards
                for copy in range(entry.copies)
            ),
        ),
    )


def _with_ix_leaders(content: RulesetContent) -> RulesetContent:
    """An Uprising game with Rise of Ix's Leaders and Tech tiles but no Ix
    board (``ix_leaders``, docs/base-game-and-ix-plan.md 20.5 P8-1): the four
    Leaders of ``IX_LEADER_IDS_WITHOUT_IX_BOARD`` follow the others, as with
    all of Rise of Ix (``_with_rise_of_ix``), and the Reserve takes the
    original Foldspace stack for Ilesa Ecaz -- "Using Ilesa Ecaz requires the
    Foldspace cards from DUNE: IMPERIUM" [Main p. 18] (docs/rules/rise-of-ix.md
    17). Board, posts, decks, Conflicts and contracts stay Uprising's: the
    option takes nothing else of Rise of Ix (OQ-165)."""

    return replace(
        content,
        reserve_stacks=(*content.reserve_stacks, _foldspace_stack()),
        card_ids=content.card_ids | {_FOLDSPACE_STACK_ID},
        leaders=(
            *content.leaders,
            *(
                leader
                for leader in IX_LEADERS
                if leader.leader_id in IX_LEADER_IDS_WITHOUT_IX_BOARD
            ),
        ),
    )


def _foldspace_stack() -> ReserveStackDefinition:
    """The original game's Foldspace Reserve stack, which Uprising lacks."""

    return next(
        stack
        for stack in IMPERIUM_RESERVE_STACKS
        if stack.card.card_id == _FOLDSPACE_STACK_ID
    )


# Docs/rules/imperium-base.md 13.4 ([Main p. 18] "COMBINING WITH BASE DUNE:
# IMPERIUM"): "Uprising에는 Mentat가 없으므로 Calculated Hire Intrigue를 뺀다".
# Sort Through the Chaos, the other card the paragraph names, is an original
# Conflict card, and those stay out (P7-3 (가)).
ORIGINAL_CARDS_LEFT_OUT_OF_UPRISING: Final = frozenset({"calculated_hire"})


def _with_original_cards(content: RulesetContent) -> RulesetContent:
    """An Uprising game with the original game's cards and Leaders.

    "나머지 Intrigue·Imperium 카드는 Uprising 카드와 모두 섞거나 골라 섞는다. —
    사용자 결정(2026-10-30, 계획 19.4 P7-2 (가), OQ-155): 옵션 하나로 원판
    Imperium·Intrigue 전부(Calculated Hire 빼고)를 섞고 원판 지도자 여덟도 고를 수
    있게 한다. 원판 프로모는 promo_cards일 때 함께." (docs/rules/imperium-base.md
    13.4). Each joins after Uprising's own, in the original tables' order:
    the decks shuffle them in at setup, the Leaders join the fixed rosters'
    choices and the draft pool. The original game's own promos (Duncan, Loyal
    Blade; Jessica of Arrakis; Thumper) need ``promo_cards`` as in an original
    game (``_imperium_deck_cards``). Uprising's board, Reserve, starting
    decks, Objectives and Conflicts stay as they are.
    """

    config = content.config
    imperium_cards = _imperium_deck_cards(config.promo_cards)
    intrigue_cards = tuple(
        entry
        for entry in _imperium_intrigue_cards(False)
        if entry.card.card_id not in ORIGINAL_CARDS_LEFT_OUT_OF_UPRISING
    )
    return replace(
        content,
        card_ids=content.card_ids
        | {entry.card.card_id for entry in _imperium_deck_cards(True)},
        leaders=(
            *content.leaders,
            *(LEADERS_BY_ID[leader_id] for leader_id in IMPERIUM_LEADER_IDS),
        ),
        imperium_cards=(*content.imperium_cards, *imperium_cards),
        imperium_deck_instance_ids=(
            *content.imperium_deck_instance_ids,
            *(
                f"imperium:{entry.card.card_id}:{copy}"
                for entry in imperium_cards
                for copy in range(entry.copies)
            ),
        ),
        intrigue_deck_instance_ids=(
            *content.intrigue_deck_instance_ids,
            *(
                f"intrigue:{entry.card.card_id}:{copy}"
                for entry in intrigue_cards
                for copy in range(entry.copies)
            ),
        ),
        original_cards=True,
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
    board, Conflicts, Leaders and decks take Rise of Ix's (stage P4a).

    Epic Game Mode with Rise of Ix (stage P4e) reuses Uprising's: "좌석마다
    Dune, the Desert Planet 하나를 Control the Spice로 바꾸고" [Rise of Ix
    p. 10] (docs/rules/rise-of-ix.md 11) -- the original starting deck is
    Uprising's printing, two Dune, the Desert Planet among its ten [DI p. 3]
    (docs/rules/imperium-base.md 3). Setup refuses the mode on the original
    game without Rise of Ix (``rules.setup``), so that configuration keeps the
    plain starting deck.

    Immortality is the original game's own expansion (stage P7b,
    docs/base-game-and-ix-plan.md 19.2): "Immortality는 원본 Dune: Imperium의
    두 번째 확장" (docs/rules/immortality.md). Its 30 Imperium and 15
    Intrigue cards are shuffled into the decks, both Dune, the Desert Planet
    become Experimentation, and in Epic Game Mode Control the Spice starts in
    the discard pile instead [Immortality pp. 4-5, 12] (immortality.md 2,
    9) -- the starting-card rules Uprising's table already applies
    (``starting_deck_entries``)."""

    rise_of_ix = config.rise_of_ix
    immortality = config.immortality
    bloodlines = config.bloodlines
    tech_module = config.tech_module
    epic_game = config.epic_game and rise_of_ix
    conflicts = _imperium_conflicts(rise_of_ix)
    imperium_cards = _imperium_deck_cards(
        config.promo_cards,
        rise_of_ix,
        immortality,
        bloodlines=bloodlines,
        tech_module=tech_module,
    )
    return RulesetContent(
        config=config,
        base_game=BaseGame.IMPERIUM,
        board_spaces=_imperium_board_spaces(rise_of_ix, bloodlines=bloodlines),
        observation_posts=(),
        conflicts=conflicts,
        conflict_pool=conflicts,
        reserve_stacks=IMPERIUM_RESERVE_STACKS,
        maker_space_ids=IMPERIUM_MAKER_SPACE_IDS,
        sandworm_space_ids=(),
        control_visit_bonuses=IMPERIUM_CONTROL_VISIT_BONUSES,
        influence_four_bonuses=IMPERIUM_INFLUENCE_FOUR_BONUSES,
        card_ids=_imperium_card_ids(rise_of_ix, immortality, bloodlines=bloodlines),
        leaders=_imperium_leaders(
            ix_leader_ids(config), bloodlines=bloodlines, tech_module=tech_module
        ),
        imperium_cards=imperium_cards,
        imperium_deck_instance_ids=tuple(
            f"imperium:{entry.card.card_id}:{copy}"
            for entry in imperium_cards
            for copy in range(entry.copies)
        ),
        intrigue_deck_instance_ids=tuple(
            f"intrigue:{entry.card.card_id}:{copy}"
            for entry in _imperium_intrigue_cards(
                rise_of_ix, immortality, bloodlines=bloodlines, tech_module=tech_module
            )
            for copy in range(entry.copies)
        ),
        contract_instance_ids=(),
        objectives=(),
        starting_deck_entries=starting_deck_entries(
            immortality=immortality, epic_game=epic_game
        ),
        starting_discard_entries=starting_discard_entries(
            immortality=immortality, epic_game=epic_game
        ),
        original_cards=True,
    )


@cache
def _imperium_board_spaces(
    rise_of_ix: bool, *, bloodlines: bool = False
) -> tuple[BoardSpace, ...]:
    """The original board; with Rise of Ix the original order with the four
    overlaid spaces removed, then the overlay's four as it prints them
    (Dreadnought, Tech Negotiation, Interstellar Shipping, Smuggling). With
    Bloodlines, Esmar Tuek's Tuek's Sietch last: "During setup, place the
    Tuek's Sietch board space near the game board" [Bloodlines p. 12], a
    space of his own that the original board's box leaves in
    (docs/rules/bloodlines.md 2a and 6; it is on the table only while he
    plays, ``BoardSpace.required_leader_id``)."""

    board = (
        IMPERIUM_BOARD_SPACES
        if not rise_of_ix
        else (
            *(
                space
                for space in IMPERIUM_BOARD_SPACES
                if space.space_id not in IX_OVERLAID_SPACE_IDS
            ),
            *IX_BOARD_SPACES,
        )
    )
    if not bloodlines:
        return board
    return (*board, BOARD_SPACES_BY_ID[TUEK_SIETCH])


@cache
def _imperium_conflicts(rise_of_ix: bool) -> tuple[ConflictDefinition, ...]:
    """The Conflict cards the game draws its tiers from: the original 18
    (I 4, II 10, III 4 [DI p. 3]); with Rise of Ix its four more are added
    "to those you already have", I 6, II 11, III 5, and the deck keeps the
    shape I 1, II 5, III 4 with one III returned to the box [Rise of Ix
    p. 3] (docs/rules/rise-of-ix.md 3 item 3). Economic Supremacy, Rise of
    Ix's Conflict III, is in every such game, Epic or not. The two Skirmishes
    and Trade Monopoly are in it since their reward rows are transcribed (stage
    P4d-1), so the pool is the printed I 6, II 11, III 5; a card without
    ``reward_rows`` would stay out, as the decks take a card only once its play
    data is complete. Tier by tier: the original cards, then Rise of Ix's in
    printed order."""

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
def _imperium_leaders(
    ix_leaders: frozenset[str],
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[LeaderDefinition, ...]:
    """The Leaders the engine plays; Rise of Ix's ``ix_leaders``
    (``ix_leader_ids``) follow ("players may choose any combination of new
    or existing Leaders" [Rise of Ix p. 3]), in printed order. With
    Bloodlines its Leaders follow those, less the three the original game
    leaves out (``BLOODLINES_LEADERS_LEFT_OUT_OF_ORIGINAL``), Kota Odax of
    Ix only with the Tech Module [Bloodlines p. 6]."""

    original = tuple(LEADERS_BY_ID[leader_id] for leader_id in IMPERIUM_LEADER_IDS)
    return (
        *original,
        *(leader for leader in IX_LEADERS if leader.leader_id in ix_leaders),
        *(
            (
                leader
                for leader in LEADERS
                if (GameOption.BLOODLINES in leader.requires)
                and leader.leader_id not in BLOODLINES_LEADERS_LEFT_OUT_OF_ORIGINAL
                and (tech_module or GameOption.TECH_MODULE not in leader.requires)
            )
            if bloodlines
            else ()
        ),
    )


@cache
def _imperium_intrigue_cards(
    rise_of_ix: bool,
    immortality: bool = False,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[IntrigueCardEntry, ...]:
    """The Intrigue cards whose play data is complete; with Rise of Ix its
    17 are "shuffled into the Intrigue Deck" [Rise of Ix p. 3] as they
    land (stage P4d), with Bloodlines the ten the original game keeps of its
    15 (and the Tech Module's two, ``_original_bloodlines_intrigue_cards``),
    and with Immortality its 15 ("Intrigue 15장을 Intrigue Deck에 섞는다"
    [Immortality p. 5]) after them."""

    entries = (
        *IMPERIUM_INTRIGUE_CARDS,
        *(IX_INTRIGUE_CARDS if rise_of_ix else ()),
        *(_original_bloodlines_intrigue_cards(tech_module) if bloodlines else ()),
        *(_IMMORTALITY_INTRIGUE_CARDS if immortality else ()),
    )
    return tuple(entry for entry in entries if entry.play_data_complete)


# "When playing BLOODLINES with DUNE: IMPERIUM" [Bloodlines p. 3]
# (docs/rules/bloodlines.md 2a): "4단계: CHOAM 모듈 구성물을 모두 빼고, Intrigue
# 다섯(False Orders, Grasp Arrakis, Insider Information, Ripples in the Sand,
# Sleeper Unit), Imperium 일곱(Arrakis Observer, Eliminate Allies, Holy War,
# Intelligence Training 둘, Pointing the Way, Shrouded Counsel), 지도자 셋(Count
# Hasimir Fenring, Gaius Helen Mohiam, Liet Kynes)을 뺀다". Intelligence
# Training is one entry of two copies.
BLOODLINES_IMPERIUM_LEFT_OUT_OF_ORIGINAL: Final = frozenset(
    {
        "arrakis_observer",
        "eliminate_allies",
        "holy_war",
        "intelligence_training",
        "pointing_the_way",
        "shrouded_counsel",
    }
)
BLOODLINES_INTRIGUE_LEFT_OUT_OF_ORIGINAL: Final = frozenset(
    {
        "false_orders",
        "grasp_arrakis",
        "insider_information",
        "ripples_in_the_sand",
        "sleeper_unit",
    }
)
BLOODLINES_LEADERS_LEFT_OUT_OF_ORIGINAL: Final = frozenset(
    {"count_hasimir_fenring", "gaius_helen_mohiam", "liet_kynes"}
)


@cache
def _original_bloodlines_imperium_cards(
    tech_module: bool,
) -> tuple[ImperiumCardEntry, ...]:
    """Bloodlines' Imperium cards an original game shuffles in (2a): every
    one in Uprising's table order but the CHOAM Module's and the seven above;
    the Tech Module's two only with it [Bloodlines p. 6]; the promo Ruthless
    Leadership stays behind ``promo_cards`` (``_imperium_deck_cards``)."""

    return tuple(
        entry
        for entry in IMPERIUM_CARDS
        if (GameOption.BLOODLINES in entry.requires)
        and GameOption.CHOAM_MODULE not in entry.requires
        and (tech_module or GameOption.TECH_MODULE not in entry.requires)
        and entry.card.card_id not in BLOODLINES_IMPERIUM_LEFT_OUT_OF_ORIGINAL
    )


@cache
def _original_bloodlines_intrigue_cards(
    tech_module: bool,
) -> tuple[IntrigueCardEntry, ...]:
    """Bloodlines' Intrigue deck cards an original game shuffles in (2a), as
    ``_original_bloodlines_imperium_cards``; Piter's Twisted Intrigue and
    Steersman's Navigation cards are not deck cards."""

    return tuple(
        entry
        for entry in INTRIGUE_CARDS
        if (GameOption.BLOODLINES in entry.requires)
        and not entry.twisted
        and not entry.navigation
        and GameOption.CHOAM_MODULE not in entry.requires
        and (tech_module or GameOption.TECH_MODULE not in entry.requires)
        and entry.card.card_id not in BLOODLINES_INTRIGUE_LEFT_OUT_OF_ORIGINAL
    )


# Immortality's own Imperium and Intrigue cards, which Uprising's tables hold
# (``immortality_only``) in their printed order; the Tleilaxu deck is
# ``content.immortality.tleilaxu`` whatever the base game.
_IMMORTALITY_IMPERIUM_CARDS: Final = tuple(
    entry for entry in IMPERIUM_CARDS if (GameOption.IMMORTALITY in entry.requires)
)
_IMMORTALITY_INTRIGUE_CARDS: Final = tuple(
    entry for entry in INTRIGUE_CARDS if (GameOption.IMMORTALITY in entry.requires)
)


# Stage P3 (plan 16.1): the original decks hold the cards transcribed so far,
# so a soak plays each one as it lands; the three promos (Duncan, Loyal Blade;
# Jessica of Arrakis; Thumper) are shuffled in only with ``promo_cards`` (plan
# 9 8), as Uprising's promos are (``imperium_cards_for_choam``). With Rise of
# Ix its 35 Imperium cards are shuffled in before the Row is formed [Rise of
# Ix p. 3], those transcribed so far, and its promo (Boundless Ambition)
# behind ``promo_cards`` too (plan 9 8). Bloodlines' follow with the option
# (stage P7c, ``_original_bloodlines_imperium_cards``), its promo Ruthless
# Leadership behind ``promo_cards``. With Immortality its 30 follow
# ("Imperium 카드 30장을 Imperium Deck에 섞는다(Imperium Row를 만들기 전에)"
# [Immortality p. 4], stage P7b).
@cache
def _imperium_deck_cards(
    promo_cards: bool,
    rise_of_ix: bool = False,
    immortality: bool = False,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[ImperiumCardEntry, ...]:
    entries = (
        *IMPERIUM_BASE_CARDS,
        *(IX_IMPERIUM_CARDS if rise_of_ix else ()),
        *(_original_bloodlines_imperium_cards(tech_module) if bloodlines else ()),
        *(_IMMORTALITY_IMPERIUM_CARDS if immortality else ()),
    )
    return tuple(
        entry
        for entry in entries
        if entry.play_data_complete
        and (promo_cards or GameOption.PROMO_CARDS not in entry.requires)
    )


# Every personal card id the base game prints, the promos' whatever the
# options (as ``_UPRISING_CARD_IDS``); Rise of Ix's with its option, its
# starting card Control the Spice (Epic Game Mode's [Rise of Ix p. 2],
# docs/rules/rise-of-ix.md 2) among them; Immortality's with its own: the
# Imperium cards, the Tleilaxu deck (its promo Piter among them) and the
# starting card Experimentation [Immortality p. 3]; Bloodlines' with its own,
# its Tech Module's and promo's included.
@cache
def _imperium_card_ids(
    rise_of_ix: bool, immortality: bool = False, *, bloodlines: bool = False
) -> frozenset[str]:
    return frozenset(
        {
            *(entry.card.card_id for entry in starting_deck_entries()),
            *((CONTROL_THE_SPICE.card.card_id,) if rise_of_ix else ()),
            *((EXPERIMENTATION.card.card_id,) if immortality else ()),
            *(stack.card.card_id for stack in IMPERIUM_RESERVE_STACKS),
            *(
                entry.card.card_id
                for entry in _imperium_deck_cards(
                    True,
                    rise_of_ix,
                    immortality,
                    bloodlines=bloodlines,
                    tech_module=bloodlines,
                )
            ),
            *(
                (card.card.card_id for card in TLEILAXU_CARDS)
                if immortality
                else ()
            ),
        }
    )
