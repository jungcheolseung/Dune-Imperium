"""Typed records for the Arrakeen Scouts module (``arrakeen_scouts`` option).

The module comes from the Dire Wolf Game Room companion app, not from a
rulebook (``docs/rules/arrakeen-scouts.md``, ``docs/rules/sources.md``). These
records carry the app's names and numbers and a structured reading of each
effect; the effect wording itself is paraphrased in the rules document and
never copied here.

Costs and rewards are effect DSL primitives (``content.uprising.effect_dsl``);
the few the Uprising cards never print (``LoseFactionInfluence`` and friends)
moved into the DSL with composed-effects stage A7b and are re-exported here.
The items' lines themselves are ability records (``abilities.py``).
``tests/unit/content/test_arrakeen_scouts_extraction.py`` audits every
record's app metadata against the local extraction.
"""

from dataclasses import dataclass
from enum import StrEnum

from dune_imperium.content.uprising.effect_dsl import (
    AcquireReserveCardToHand as AcquireReserveCardToHand,
)
from dune_imperium.content.uprising.effect_dsl import (
    Cost,
    EffectSection,
    GainResources,
    Reward,
)
from dune_imperium.content.uprising.effect_dsl import (
    GainLowestInfluence as GainLowestInfluence,
)
from dune_imperium.content.uprising.effect_dsl import (
    GainSpiceWithHelixBonus as GainSpiceWithHelixBonus,
)
from dune_imperium.content.uprising.effect_dsl import (
    LoseFactionInfluence as LoseFactionInfluence,
)
from dune_imperium.content.uprising.effect_dsl import (
    LoseGarrisonTroops as LoseGarrisonTroops,
)
from dune_imperium.content.uprising.effect_dsl import (
    LoseHighestInfluence as LoseHighestInfluence,
)
from dune_imperium.content.uprising.effect_dsl import (
    RecallOtherAgent as RecallOtherAgent,
)
from dune_imperium.content.uprising.effect_dsl import (
    RecruitToConflict as RecruitToConflict,
)


class ScoutsPool(StrEnum):
    """The app's schedule pools this project plays [Scouts schedule].

    The app picks the pool from the expansions in play. Uprising and
    Uprising+Ix share their Uprising lists, and Bloodlines changes nothing,
    so the engine needs only these two (``immortality`` picks the second).
    """

    UPRISING = "uprising"
    UPRISING_IMMORTALITY = "uprising_immortality"


BOTH_POOLS: tuple[ScoutsPool, ...] = (
    ScoutsPool.UPRISING,
    ScoutsPool.UPRISING_IMMORTALITY,
)
UPRISING_ONLY: tuple[ScoutsPool, ...] = (ScoutsPool.UPRISING,)
IMMORTALITY_ONLY: tuple[ScoutsPool, ...] = (ScoutsPool.UPRISING_IMMORTALITY,)


@dataclass(frozen=True, slots=True)
class AppDefinition:
    """The app asset that defines one item, for the extraction audit.

    ``family`` is the app's beatId (for a subcommittee, its subcommitteeId).
    It is not an identity: Desert Riding and Urban Surveillance share 15.0.
    It is the schedule's family key, because drawing an item removes every
    item of its family from the pool [Scouts schedule]. ``variant`` is the
    beatSubId.
    """

    asset_name: str
    family: int
    variant: int = 0

    def __post_init__(self) -> None:
        if not self.asset_name.startswith("Def_"):
            raise ValueError("app definitions are the Def_* assets")
        if self.family < 0 or self.variant < 0:
            raise ValueError("app beat ids are not negative")


def _check_rounds(rounds: tuple[int, int]) -> None:
    first, last = rounds
    if not 1 <= first <= last <= 10:
        raise ValueError("a round window lies within rounds 1-10")


def _check_pools(pools: tuple[ScoutsPool, ...]) -> None:
    if not pools or len(pools) != len(set(pools)):
        raise ValueError("an item belongs to one or more distinct pools")


# --- Scouts-only cost and reward primitives -----------------------------------------
# They live in the effect DSL since composed-effects stage A7b (re-exported
# here); a Scouts line is a DSL line.
type ScoutsCost = Cost
type ScoutsReward = Reward


# --- Subcommittees ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Subcommittee:
    """A subcommittee: joined once, optionally, on taking a High Council seat.

    ``tier`` is the app's subcommitteeType. The app draws one of each tier
    0, 1 and 2, then the rest from the whole pool [Scouts schedule].
    """

    subcommittee_id: str
    name: str
    tier: int
    option: EffectSection
    pools: tuple[ScoutsPool, ...]
    app: AppDefinition
    choam_only: bool = False

    def __post_init__(self) -> None:
        if not self.subcommittee_id or not self.name:
            raise ValueError("subcommittees need an id and a name")
        if self.tier not in (0, 1, 2):
            raise ValueError("subcommittee tiers are 0, 1 and 2")
        _check_pools(self.pools)


# --- Missions ----------------------------------------------------------------------


class MissionKind(StrEnum):
    """Each mission's mechanism; the engine implements one hook per kind."""

    SECURITY_DETAIL = "security_detail"
    IMPERIAL_RESERVE = "imperial_reserve"
    DESERT_RIDING = "desert_riding"
    URBAN_SURVEILLANCE = "urban_surveillance"
    PLANETARY_EXPLORATION = "planetary_exploration"
    CHOAM_RESEARCH = "choam_research"
    CHOAM_ESCORT = "choam_escort"
    PRISON_PLANET = "prison_planet"
    EMPERORS_SCHEMES = "emperors_schemes"
    FEDAYKIN_ASSISTANCE = "fedaykin_assistance"
    WEIRDING_WARFARE = "weirding_warfare"
    SEND_FOR_AID = "send_for_aid"
    COORDINATE_WITH_THE_EMPEROR = "coordinate_with_the_emperor"
    SPONSORED_RESEARCH = "sponsored_research"
    BACK_ROOM_DEAL = "back_room_deal"
    TLEILAXU_OFFERING = "tleilaxu_offering"


class TroopSource(StrEnum):
    """Where a mission's parked troops come from."""

    SUPPLY = "supply"
    GARRISON = "garrison"
    # A troop in the Axolotl Tanks [Immortality p. 8].
    SPECIMENS = "specimens"


@dataclass(frozen=True, slots=True)
class Mission:
    """A mission: revealed in round 2 or 3, its pieces stay until claimed.

    ``mission_type`` is the app's missionType (0 or 1). The last of the three
    missions must differ in type from the one before it [Scouts schedule].
    ``space_id`` is the board space the pieces go to, when there is one.

    What each seat may do at the reveal (always optional): pay
    ``participation_cost`` and park ``parked_troops`` troops from
    ``troop_source`` on the space, with ``seat_goods`` from the bank beside
    them; or, for a mission with ``choices``, pick one of those lines.
    ``goods`` and ``goods_cards`` come from the bank at the reveal
    (``goods_cards`` face-down Contracts or Intrigue cards). Where they go
    and who takes them is the kind's hook: once on the space, or on each
    empty Observation Post the kind names (Valued Informants), and Imperial
    Reserve's visitor takes one of its two goods, not both.
    """

    mission_id: str
    name: str
    kind: MissionKind
    mission_type: int
    rounds: tuple[int, int]
    pools: tuple[ScoutsPool, ...]
    app: AppDefinition
    choam_only: bool = False
    space_id: str | None = None
    participation_cost: tuple[ScoutsCost, ...] = ()
    parked_troops: int = 0
    troop_source: TroopSource | None = None
    seat_goods: GainResources | None = None
    choices: tuple[EffectSection, ...] = ()
    goods: GainResources | None = None
    goods_cards: int = 0

    def __post_init__(self) -> None:
        if not self.mission_id or not self.name:
            raise ValueError("missions need an id and a name")
        if self.mission_type not in (0, 1):
            raise ValueError("mission types are 0 and 1")
        _check_rounds(self.rounds)
        if not 2 <= self.rounds[0] <= self.rounds[1] <= 3:
            raise ValueError("missions are revealed in rounds 2-3")
        _check_pools(self.pools)
        if (self.parked_troops > 0) != (self.troop_source is not None):
            raise ValueError("parked troops need a source, and only they do")
        if self.parked_troops < 0 or self.goods_cards < 0:
            raise ValueError("mission counts are not negative")


# --- Events ------------------------------------------------------------------------


class EventKind(StrEnum):
    """How an event resolves."""

    # Each seat in turn order picks one option (or passes when ``passable``).
    CHOICE = "choice"
    # Applies with no choice beyond a tie (Political Equilibrium, Mating
    # Season, Clear the Market).
    AUTOMATIC = "automatic"
    # Changes a rule until the end of the round.
    ROUND_MODIFIER = "round_modifier"
    # Each seat secretly picks one delayed reward (Covert Operation,
    # Offworld Operation).
    SECRET = "secret"
    # Rebuild Infrastructure: two seats share the cost of one effect.
    SHARED = "shared"


class AutomaticEffect(StrEnum):
    """The automatic events' effects."""

    # Every player loses one Influence on their highest track (ties chosen).
    POLITICAL_EQUILIBRIUM = "political_equilibrium"
    # One more spice on each Maker space.
    MATING_SEASON = "mating_season"
    # Replace the Imperium Row.
    CLEAR_THE_MARKET = "clear_the_market"
    # Replace the Imperium Row and the two face-up Contracts.
    CLEAR_THE_MARKET_CONTRACTS = "clear_the_market_contracts"


class RoundModifier(StrEnum):
    """Rules an event changes until the end of the round."""

    IGNORE_INFLUENCE_REQUIREMENTS = "ignore_influence_requirements"
    FACTION_SPACES_ARE_COMBAT = "faction_spaces_are_combat"
    SPICE_MUST_FLOW_DISCOUNT = "spice_must_flow_discount"
    ANY_FACTION_FOUR_BONUS = "any_faction_four_bonus"


@dataclass(frozen=True, slots=True)
class SecretChoice:
    """One secret pick: its reward resolves ``delay`` rounds later, right
    after that round's Scout step starts. ``grouped`` picks resolve together
    in turn order; the others one seat at a time (the app's screens)."""

    option: EffectSection
    delay: int
    grouped: bool = False

    def __post_init__(self) -> None:
        if self.delay not in (1, 2):
            raise ValueError("secret rewards come one or two rounds later")


@dataclass(frozen=True, slots=True)
class ScoutsEvent:
    """An event: one per round in rounds 4-7, drawn by weight.

    ``weight_tickets`` is the app's baseWeight x subWeight x 10, the number
    of equal outcomes the event gets in a round's draw (the engine's chance
    frames are uniform).
    """

    event_id: str
    name: str
    kind: EventKind
    rounds: tuple[int, int]
    weight_tickets: int
    pools: tuple[ScoutsPool, ...]
    app: AppDefinition
    choam_only: bool = False
    no_choam_only: bool = False
    options: tuple[EffectSection, ...] = ()
    passable: bool = False
    automatic: AutomaticEffect | None = None
    modifier: RoundModifier | None = None
    secret_choices: tuple[SecretChoice, ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id or not self.name:
            raise ValueError("events need an id and a name")
        _check_rounds(self.rounds)
        if not 4 <= self.rounds[0] <= self.rounds[1] <= 7:
            raise ValueError("events are revealed in rounds 4-7")
        if self.weight_tickets < 1:
            raise ValueError("an event needs at least one ticket")
        _check_pools(self.pools)
        if self.choam_only and self.no_choam_only:
            raise ValueError("an event cannot need CHOAM both on and off")
        shape = {
            EventKind.CHOICE: bool(self.options),
            EventKind.SHARED: bool(self.options),
            EventKind.AUTOMATIC: self.automatic is not None,
            EventKind.ROUND_MODIFIER: self.modifier is not None,
            EventKind.SECRET: bool(self.secret_choices),
        }
        if not shape[self.kind]:
            raise ValueError("an event's fields must match its kind")
        if self.kind is not EventKind.CHOICE and self.passable:
            raise ValueError("only choice events can be passed")


# --- Auctions and sales ------------------------------------------------------------


class AuctionSlot(StrEnum):
    """Which auction draw can pick the item."""

    MID = "mid"
    LATE = "late"
    # Mercenaries has one definition for rounds 5-9, so either draw.
    EITHER = "either"


class AuctionKind(StrEnum):
    """How the bids decide the rewards."""

    # Sealed bids; ranked winners pay and take ``rank_rewards``.
    SEALED = "sealed"
    # Mercenaries: sealed bids of 0-3 spice, everyone pays and deploys.
    MERCENARIES = "mercenaries"
    # Critical Moment: one open bid each over revealed Imperium cards.
    OPEN_CARDS = "open_cards"


@dataclass(frozen=True, slots=True)
class ScoutsAuction:
    """An auction: the mid one in round 5 or 6, the late one in 8 or 9.

    ``places`` is how many places win (the length of the app's rewardRanks).
    ``rank_rewards[0]`` is a sealed auction's first-place reward, ``[1]``
    second place's. ``currency`` is what bids are paid in. ``revealed_cards``
    is how many Imperium deck cards an open auction reveals: first place
    takes one into hand, and a second place may buy another (OQ-087).
    """

    auction_id: str
    name: str
    kind: AuctionKind
    slot: AuctionSlot
    rounds: tuple[int, int]
    currency: str
    max_bid: int
    pools: tuple[ScoutsPool, ...]
    app: AppDefinition
    choam_only: bool = False
    places: int = 1
    rank_rewards: tuple[tuple[ScoutsReward, ...], ...] = ()
    revealed_cards: int = 0

    def __post_init__(self) -> None:
        if not self.auction_id or not self.name:
            raise ValueError("auctions need an id and a name")
        _check_rounds(self.rounds)
        _check_pools(self.pools)
        if self.currency not in ("solari", "spice"):
            raise ValueError("bids are paid in Solari or spice")
        if self.max_bid < 1:
            raise ValueError("the bid cap must be positive")
        if self.places not in (1, 2):
            raise ValueError("one or two places win")
        if self.kind is AuctionKind.SEALED:
            if len(self.rank_rewards) != self.places or not all(self.rank_rewards):
                raise ValueError("a sealed auction rewards each winning place")
        elif self.rank_rewards:
            raise ValueError("only sealed auctions list rank rewards")
        if (self.kind is AuctionKind.OPEN_CARDS) != (self.revealed_cards > 0):
            raise ValueError("open auctions, and only they, reveal cards")
        if self.kind is AuctionKind.OPEN_CARDS and self.revealed_cards <= self.places:
            raise ValueError("an open auction reveals more cards than places")


@dataclass(frozen=True, slots=True)
class ScoutsSale:
    """A sale: in round 8 or 9 (whichever has no late auction), each seat in
    turn order may buy one of the options."""

    sale_id: str
    name: str
    options: tuple[EffectSection, ...]
    pools: tuple[ScoutsPool, ...]
    app: AppDefinition

    def __post_init__(self) -> None:
        if not self.sale_id or not self.name:
            raise ValueError("sales need an id and a name")
        if not self.options:
            raise ValueError("a sale offers at least one option")
        _check_pools(self.pools)
