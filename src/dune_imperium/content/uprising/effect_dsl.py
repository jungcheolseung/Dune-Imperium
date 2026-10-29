"""Composable typed effects for card text that reads as condition/cost/reward.

The DSL deliberately stays small. Each primitive is an immutable record with
its own validation; the rules interpreter in ``rules/effect_interpreter.py``
decides what each primitive does to game state. Card-specific behaviour that
does not fit these primitives keeps using explicit custom hooks.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import AgentIcon, BattleIcon


class IntrigueTiming(StrEnum):
    """When an Intrigue option may be played."""

    PLOT = "plot"
    COMBAT = "combat"
    ENDGAME = "endgame"


# --- Conditions -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InfluenceAtLeast:
    """The player has at least ``amount`` Influence with ``faction``."""

    faction: Faction
    amount: int

    def __post_init__(self) -> None:
        if not isinstance(self.faction, Faction):
            raise TypeError("Influence condition requires a Faction")
        if self.amount < 1:
            raise ValueError("Influence condition amount must be positive")


@dataclass(frozen=True, slots=True)
class InfluenceAtLeastOnTracks:
    """The player has at least ``influence`` Influence on at least ``tracks``
    of the four Faction tracks (Plans Within Plans: "3 Influence (or more)
    on three Faction tracks", imperium-base.md 13.2: Influence 3 is the space
    just above the Victory Point space)."""

    influence: int
    tracks: int

    def __post_init__(self) -> None:
        if self.influence < 1:
            raise ValueError("Influence condition amount must be positive")
        if not 1 <= self.tracks <= len(Faction):
            raise ValueError("Influence tracks must be between one and the four")


@dataclass(frozen=True, slots=True)
class HasHighCouncil:
    """The player holds a High Council seat."""


@dataclass(frozen=True, slots=True)
class HasAlliance:
    """The player holds a Faction Alliance: any one (Twisted Intrigue,
    Navigation), or ``faction``'s ("[Fremen] Alliance:" [Stillsuit
    Manufacturer card])."""

    faction: Faction | None = None


@dataclass(frozen=True, slots=True)
class InNavigationSlot:
    """The Navigation card being played sits in slot ``slot`` (1-4)."""

    slot: int

    def __post_init__(self) -> None:
        if not 1 <= self.slot <= 4:
            raise ValueError("Navigation slots run from 1 to 4")


@dataclass(frozen=True, slots=True)
class TriggeredByFaction:
    """The Navigation card was played for reaching two Influence with ``faction``."""

    faction: Faction

    def __post_init__(self) -> None:
        if not isinstance(self.faction, Faction):
            raise TypeError("trigger Faction condition requires a Faction")


@dataclass(frozen=True, slots=True)
class SpiesPlacedAtLeast:
    """The player has at least ``count`` Spies on Observation Posts."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Spy condition count must be positive")


@dataclass(frozen=True, slots=True)
class CompletedContractsAtLeast:
    """The player has completed at least ``count`` Contracts (CHOAM Module)."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("completed-Contract condition count must be positive")


@dataclass(frozen=True, slots=True)
class SandwormsInConflictAtLeast:
    """The player has at least ``count`` sandworms in the current Conflict."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("sandworm condition count must be positive")


@dataclass(frozen=True, slots=True)
class GainedSpiceThisTurn:
    """The player has gained at least ``amount`` Spice during their turn.

    Every source counts and spending Spice does not reduce the total; the
    condition holds at the moment the card is played.
    """

    amount: int = 1

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Spice-gained condition amount must be positive")


@dataclass(frozen=True, slots=True)
class UnitsDeployedThisTurnAtLeast:
    """The player has deployed ``count`` or more units to the Conflict this
    turn: "When you deploy three or more units to the Conflict in a single
    turn:" [Distraction card; Coercive Negotiation card].

    It is a condition for playing the card [FAQ p. 2], met once the units
    are deployed ("Gurney decides to commit these troops plus two more from
    his garrison to the Conflict. Muad'Dib may play Distraction because he
    shared in the deployment of these units." [Board Guide p. 10]), not a
    trigger the card waits face up for (user ruling 2026-10-03). "You need
    to have a moment in time when there are 3 units in the conflict that
    were deployed to the conflict this turn, then that requirement becomes
    true." (Message from designer, adopted per OQ-057's rule): it reads the
    turn's peak, so a later retreat keeps it true, while an OQ-029
    withdrawal undoes the deployment and lowers the peak. Troops, Sardaukar
    Commanders and sandworms are all units [Main p. 12] [Bloodlines p. 4].

    ``dreadnoughts``: Rise of Ix's Diversion ("When you deploy four or more
    units to the Conflict in a single turn:" [Diversion card, Steam app
    text]) counts the dreadnoughts of the turn's deployment as well, for a
    dreadnought is a unit, though no troop [Rise of Ix p. 6]
    (docs/rules/rise-of-ix.md 6, table row "unit"; 15: the same judgment as
    Distraction's). The turn's unit count (``units_deployed_turn``) never
    holds one, so the condition adds the dreadnoughts the turn's frame says
    its deployment moved (``combat_deployment.dreadnoughts_deployed_this_turn``).
    """

    count: int = 3
    dreadnoughts: bool = False

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("deployed-units condition count must be positive")


@dataclass(frozen=True, slots=True)
class SpiceMustFlowCardsAtLeast:
    """The player owns at least ``count`` copies of The Spice Must Flow.

    Copies in the deck, hand, discard pile and play area count; a trashed
    copy has left the game. Uprising's card and the original game's both
    count.
    """

    count: int = 2

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("The Spice Must Flow count must be positive")


@dataclass(frozen=True, slots=True)
class MoreSpiceMustFlowThanEachOpponent:
    """The player owns more copies of The Spice Must Flow than each opponent.

    Each opponent is compared separately and an opponent with as many
    copies fails the condition (Corner the Market, imperium-base.md 13.2,
    ``[FAQ p. 2]``). The copies counted are those of
    ``SpiceMustFlowCardsAtLeast`` (OQ-123).
    """


@dataclass(frozen=True, slots=True)
class OpponentAllianceInfluenceAtLeast:
    """The player has ``amount`` or more Influence on a Faction track whose
    Alliance token an opponent holds."""

    amount: int = 4

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Influence condition amount must be positive")


@dataclass(frozen=True, slots=True)
class WaterAtLeast:
    """The player has at least ``amount`` water (Sacred Pools, Bloodlines)."""

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("water condition amount must be positive")


@dataclass(frozen=True, slots=True)
class CommandersInConflictAtLeast:
    """The player has ``count`` or more Sardaukar Commanders in the Conflict
    (Bloodlines)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Commander condition count must be positive")


@dataclass(frozen=True, slots=True)
class TechTilesAtLeast:
    """The player holds ``count`` or more Tech tiles (Tech Module)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Tech tile condition count must be positive")


@dataclass(frozen=True, slots=True)
class GeneticMarkersAtLeast:
    """The owner's research token has reached ``count`` genetic markers
    [Immortality pp. 6, 16]."""

    count: int

    def __post_init__(self) -> None:
        if self.count not in (1, 2):
            raise ValueError("there are two genetic markers")


@dataclass(frozen=True, slots=True)
class SolariAtLeast:
    """The owner holds at least ``amount`` Solari (Economic Positioning)."""

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Solari threshold must be positive")


@dataclass(frozen=True, slots=True)
class SpiceAtLeast:
    """The owner holds at least ``amount`` spice (Study Melange)."""

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("spice threshold must be positive")


@dataclass(frozen=True, slots=True)
class OpponentPlayedCombatIntrigue:
    """An opponent played a Combat Intrigue card in this Conflict
    (Counterattack)."""


@dataclass(frozen=True, slots=True)
class AtMakerSpace:
    """The Agent was sent to a Maker space ("If you are at a Maker space:"
    [Desert Power card]): fixed by the placement, so an Agent box judges it
    when the card is played (OQ-028 (a))."""


@dataclass(frozen=True, slots=True)
class AtFactionSpace:
    """The Agent was sent to a Faction space: fixed by the placement, so an
    Agent box judges it when the card is played (OQ-028 (a)). A box reached
    off one through a granted Spy or Agent icon (Clandestine, Resourceful,
    Urgent Shigawire) has no visited Faction to gain with (OQ-046)."""


@dataclass(frozen=True, slots=True)
class FactionBond:
    """Another card of ``faction`` is in play: that Faction's Bond ("Fremen
    Bond | 프레멘의 유대감" [Main p. 20])."""

    faction: Faction

    def __post_init__(self) -> None:
        if not isinstance(self.faction, Faction):
            raise TypeError("a Bond names a Faction")


@dataclass(frozen=True, slots=True)
class SpyRecalledThisTurn:
    """The player recalled one of their Spies this turn, by any means ("If
    you recalled a Spy this turn:" [Strike Fleet card])."""


@dataclass(frozen=True, slots=True)
class UnitsInConflictAtLeast:
    """The player has ``count`` or more units in the Conflict, an Agent there
    included ("If you have 3 or more units in the Conflict:" [Chani, Clever
    Tactician card])."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("unit threshold must be positive")


@dataclass(frozen=True, slots=True)
class ContractCompletedThisTurn:
    """The player completed a Contract this turn ("If you completed a
    Contract this turn:" [Mercantile Affairs card])."""


@dataclass(frozen=True, slots=True)
class DiscardedCardHasFaction:
    """The card discarded for the arrow's cost has ``faction``'s affiliation
    ("2 if the discarded card has Spacing Guild affiliation" [Space-time
    Folding card]): judged on that card once the cost is paid."""

    faction: Faction


@dataclass(frozen=True, slots=True)
class TrashedCardHasFaction:
    """The card trashed for the arrow's cost has ``faction``'s affiliation
    ("If you trash an Emperor card:" [Elite Forces card]): judged on that
    card once the cost is paid."""

    faction: Faction


@dataclass(frozen=True, slots=True)
class GraftedWithFaction:
    """The card was played grafted with a card of one of ``factions`` ("If
    grafted with an Emperor or Spacing Guild card:" [Interstellar Conspiracy
    card]): the other grafted card's printed affiliation, either Faction."""

    factions: tuple[Faction, ...]

    def __post_init__(self) -> None:
        if not self.factions or len(set(self.factions)) != len(self.factions):
            raise ValueError("graft partner Factions must be unique and non-empty")


@dataclass(frozen=True, slots=True)
class Grafted:
    """The card was played grafted with another ("If grafted:" [Corrupt
    Smuggler card]) [Immortality p. 10]."""


@dataclass(frozen=True, slots=True)
class HasSwordmaster:
    """The player has its Swordmaster ("High Council and Swordmaster:"
    [Paracompass card])."""


@dataclass(frozen=True, slots=True)
class SpyingOnMakerSpace:
    """One of the player's Spies watches a Maker space ("If you are spying on
    a Maker space:" [Smuggler's Haven card])."""


@dataclass(frozen=True, slots=True)
class GarrisonedUnitsAtLeast:
    """The player has ``count`` or more units -- troops and Sardaukar
    Commanders -- in its garrison [Imperial Throneship card]."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("garrison condition count must be positive")


@dataclass(frozen=True, slots=True)
class DreadnoughtsAtLeast:
    """The player has ``count`` or more dreadnoughts of its own -- the ones
    commissioned out of its supply, wherever they stand: its garrison, the
    Conflict or a Control space ("2 dreadnoughts" [Grand Conspiracy card,
    Steam app text]; docs/rules/open-questions.md OQ-121: "Grand Conspiracy의
    '2 dreadnoughts'는 가진 수이고", no position is read)."""

    count: int

    def __post_init__(self) -> None:
        if not 1 <= self.count <= 2:
            raise ValueError("a seat has one or two dreadnoughts to count")


@dataclass(frozen=True, slots=True)
class CommandReached:
    """Command (6+): the player's Reveal turn generates six or more
    Persuasion [Bloodlines pp. 5, 12], the others' first so the order does
    not matter (``rules.reveal_turn``)."""


@dataclass(frozen=True, slots=True)
class AtBoardSpace:
    """The player sent an Agent to ``space_id`` (a Contract: "Send an Agent
    to Arrakeen"), judged on the placement's snapshot."""

    space_id: str


@dataclass(frozen=True, slots=True)
class AcquiredCard:
    """The player acquired a copy of ``card_id`` (a Contract: "Acquire The
    Spice Must Flow")."""

    card_id: str


@dataclass(frozen=True, slots=True)
class ContractTaken:
    """The Contract was just taken: an Immediate tile completes at once
    [Main p. 16]."""


@dataclass(frozen=True, slots=True)
class AllianceTaken:
    """The player took an Alliance token it did not already hold (the
    Bloodlines "Earn Any Alliance" Contract, OQ-056)."""


@dataclass(frozen=True, slots=True)
class AgentOnSpaceWithIcon:
    """The player has an Agent on a board space with ``icon`` ("If you have
    an Agent on a [Landsraad] board space" [Canny Skill tile])."""

    icon: AgentIcon

    def __post_init__(self) -> None:
        if not isinstance(self.icon, AgentIcon):
            raise TypeError("an Agent-space icon must use AgentIcon")


@dataclass(frozen=True, slots=True)
class OpponentSandwormInConflict:
    """Any opponent has a sandworm in the Conflict [Fierce Skill tile]."""


@dataclass(frozen=True, slots=True)
class OpponentHasTroopInConflict:
    """An opponent has a troop in the Conflict: "Double Cross | 상대 하나
    이상이 Conflict에 troop이 있어야 낸다" `[FAQ p. 2]` (imperium-base.md
    13.2), an official condition of playing the card. A Sardaukar Commander
    is a troop for a card effect [Bloodlines p. 4] (OQ-036 (a))."""


@dataclass(frozen=True, slots=True)
class StrengthInConflictAtLeast:
    """The player has ``amount`` or more strength in the Conflict ("If you
    have 6 or more strength in the Conflict" [Gurney Halleck card])."""

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("a strength threshold must be positive")


@dataclass(frozen=True, slots=True)
class VisitedSpaceHasIcon:
    """The player sent an Agent this turn to a board space with ``icon``
    ("If you sent an Agent this turn to a Landsraad space" [Liet Kynes
    card])."""

    icon: AgentIcon

    def __post_init__(self) -> None:
        if not isinstance(self.icon, AgentIcon):
            raise TypeError("a visited-space icon must use AgentIcon")


@dataclass(frozen=True, slots=True)
class DuringAgentTurn:
    """Agent Turn: only after the owner's Agent placement this turn
    [Rapid Dropships Tech tile] [Bloodlines p. 7]."""


@dataclass(frozen=True, slots=True)
class AllConditions:
    """Every listed condition holds (Study Melange: spice and two markers)."""

    conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        if len(self.conditions) < 2:
            raise ValueError("a conjunction needs at least two conditions")


@dataclass(frozen=True, slots=True)
class AtLeastOfConditions:
    """At least ``count`` of the listed conditions hold (Grand Conspiracy:
    "If you have any three:" of its four items). ``count`` is fewer than the
    items; all of them is ``AllConditions``."""

    count: int
    conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        if len(self.conditions) < 3:
            raise ValueError("a count of conditions needs at least three")
        if not 1 < self.count < len(self.conditions):
            raise ValueError("the count is more than one and less than all")


type Condition = (
    InfluenceAtLeast
    | InfluenceAtLeastOnTracks
    | HasHighCouncil
    | HasAlliance
    | InNavigationSlot
    | TriggeredByFaction
    | SpiesPlacedAtLeast
    | CompletedContractsAtLeast
    | SandwormsInConflictAtLeast
    | GainedSpiceThisTurn
    | UnitsDeployedThisTurnAtLeast
    | SpiceMustFlowCardsAtLeast
    | MoreSpiceMustFlowThanEachOpponent
    | OpponentAllianceInfluenceAtLeast
    | WaterAtLeast
    | CommandersInConflictAtLeast
    | TechTilesAtLeast
    | GeneticMarkersAtLeast
    | SolariAtLeast
    | SpiceAtLeast
    | OpponentPlayedCombatIntrigue
    | AtMakerSpace
    | AtFactionSpace
    | FactionBond
    | SpyRecalledThisTurn
    | UnitsInConflictAtLeast
    | ContractCompletedThisTurn
    | DiscardedCardHasFaction
    | TrashedCardHasFaction
    | GraftedWithFaction
    | Grafted
    | AllConditions
    | AtLeastOfConditions
    | HasSwordmaster
    | SpyingOnMakerSpace
    | GarrisonedUnitsAtLeast
    | DreadnoughtsAtLeast
    | CommandReached
    | AtBoardSpace
    | AcquiredCard
    | ContractTaken
    | AllianceTaken
    | DuringAgentTurn
    | VisitedSpaceHasIcon
    | StrengthInConflictAtLeast
    | AgentOnSpaceWithIcon
    | OpponentSandwormInConflict
    | OpponentHasTroopInConflict
)


# --- Costs ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PayResources:
    """Spend public resources from the player's supply."""

    solari: int = 0
    spice: int = 0
    water: int = 0

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("resource costs must not be negative")
        if self.solari == self.spice == self.water == 0:
            raise ValueError("a resource cost must spend something")

    def __add__(self, other: PayResources) -> PayResources:
        return PayResources(
            solari=self.solari + other.solari,
            spice=self.spice + other.spice,
            water=self.water + other.water,
        )


class GraftedTrash(StrEnum):
    """Which grafted card a trash takes: "the other grafted card" [Dissecting
    Kit card], "one of the grafted cards" [Beguiling Pheromones card]."""

    OTHER = "other"
    EITHER = "either"


@dataclass(frozen=True, slots=True)
class TrashCard:
    """Trash one of the player's cards as an arrow's cost: one in hand, in
    the discard pile or in play ("You may trash a card -> Draw 1 card"
    [Shishakli card]; a Row card borrowed with Usurp is not in play, OQ-054).
    ``hand_only``: "a card from your hand"; ``this_card``: "You may trash this
    card ->" [Pivotal Gambit card] -- or the tile printing it, Desperate's
    "Trash this ->" [Desperate Skill tile]; ``other_in_play``: "another
    <Faction> card in play" [Calculus of Power card]."""

    hand_only: bool = False
    this_card: bool = False
    other_in_play: Faction | None = None
    # "an Emperor card from your hand" [Treacherous Maneuver card].
    faction: Faction | None = None
    # A card of the graft pair (``GraftedTrash``).
    grafted: GraftedTrash | None = None

    def __post_init__(self) -> None:
        if (
            int(self.hand_only)
            + int(self.this_card)
            + int(self.other_in_play is not None)
            > 1
        ):
            raise ValueError("a trash cost names one place to take the card from")
        if self.faction is not None and not self.hand_only:
            raise ValueError("a trash cost names a Faction only for a card in hand")
        if self.grafted is not None and (
            self.hand_only or self.this_card or self.other_in_play is not None
        ):
            raise ValueError("a grafted card's trash names no other place")


@dataclass(frozen=True, slots=True)
class SpendSpecimens:
    """Spend ``count`` of the player's specimens: they return to the supply
    as troops [Immortality p. 8] ("You may spend 1 specimen" [Organ
    Merchants card]; an Arrakeen Scouts line's specimen cost, Ingratiate,
    since cleanup-1)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("specimen spend must be positive")


@dataclass(frozen=True, slots=True)
class LoseInfluence:
    """Lose ``count`` Influence, choosing a Faction for each step.

    Each step is a player choice among Factions where the player still has
    Influence; the same Faction may be chosen more than once.
    """

    count: int = 1
    # "lose 2 Influence with one Faction" [For Humanity card]: every step
    # from the same Faction.
    one_faction: bool = False

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Influence loss count must be positive")


@dataclass(frozen=True, slots=True)
class DiscardFromHand:
    """Discard ``count`` personal cards chosen from hand.

    Also the Rise of Ix Discard cost icon: each icon costs one hand card,
    never an Intrigue card [Rise of Ix p. 7] [FAQ p. 2]. Repeated icons on
    one line are written as one counted cost (Ixian Probe: ``count=2``).
    """

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("hand discard count must be positive")


@dataclass(frozen=True, slots=True)
class LoseTroops:
    """Lose ``count`` of the player's troops (each to the supply).

    The player picks the zone of every troop, garrison or Conflict, and may
    give up a Sardaukar Commander as a troop [Bloodlines p. 4] (OQ-038);
    ``from_conflict`` limits the choice to units in the Conflict (Shrewd).
    """

    count: int = 1
    from_conflict: bool = False
    # Troops only, from either zone: no Sardaukar Commander [Tleilaxu
    # Surgeon card] (OQ-053).
    troops_only: bool = False

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("troop loss count must be positive")


@dataclass(frozen=True, slots=True)
class GiveIntrigueToOpponent:
    """Give an opponent an Intrigue card from hand (Insidious).

    ``bonus_spice_if_not_twisted`` pays extra when the gift is a regular
    Intrigue card rather than a Twisted one.
    """

    bonus_spice_if_not_twisted: int = 0


@dataclass(frozen=True, slots=True)
class TrashIntrigueCard:
    """Trash an Intrigue card of the player's choice from hand [Bloodlines p. 11].

    ``troops_if_not_twisted`` recruits when the trashed card is a regular
    Intrigue card rather than a Twisted one (Unnatural).
    """

    troops_if_not_twisted: int = 0


@dataclass(frozen=True, slots=True)
class PutIntrigueOnDeckBottom:
    """Put one of the player's Intrigue cards on the bottom of the Intrigue
    deck: "Put an Intrigue card on the bottom of the deck" [Court Intrigue
    card, Steam app text]. The other seats do not see which card ("Court
    Intrigue·Sonic Snoopers — Intrigue를 덱 맨 아래에 놓을 때 상대에게 보이지
    않는다", docs/rules/rise-of-ix.md 9.1, [Rise of Ix p. 10]); the seat that
    put it knows it until it is drawn or the deck is shuffled (rise-of-ix.md
    13, OQ-149, ``rules.intrigue_knowledge``). A Twisted Intrigue card never
    reaches the common deck (OQ-097)."""


@dataclass(frozen=True, slots=True)
class RecallSpy:
    """Return ``count`` of the player's placed Spies to supply (player choice)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Spy recall count must be positive")


@dataclass(frozen=True, slots=True)
class RetreatTroops:
    """Move between ``minimum`` and ``maximum`` of the player's Conflict troops
    back to the garrison (player choice). ``maximum=None`` means any number.

    A printed "any number" retreat takes ``minimum=0``: "효과가 `any number`의
    troop을 retreat하게 하면 0개도 선택할 수 있다. `[Main p. 20]` `[FAQ p. 3]`"
    (docs/rules/uprising-systems.md). During Combat the retreated troops'
    strength leaves the total at once and a player left without units drops
    out of the priority loop (OQ-003).

    ``units``: "Retreat three of your units" [Negotiated Withdrawal card,
    Steam app text] -- a unit is a troop or a dreadnought [Rise of Ix p. 6]
    (docs/rules/rise-of-ix.md 6, its table's "unit" row), so the owner's
    Conflict dreadnoughts are among what it may retreat. Without it a card's
    "troop" never reaches a dreadnought.
    """

    minimum: int = 1
    maximum: int | None = None
    units: bool = False

    def __post_init__(self) -> None:
        if self.minimum < 0:
            raise ValueError("retreat minimum must not be negative")
        if self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("retreat maximum must not be below the minimum")


@dataclass(frozen=True, slots=True)
class FlipBattleCard:
    """Flip one of the player's face-up won Conflict cards face down.

    The card text names one printed battle icon; a card bearing that icon or
    the wild icon may be chosen. Objective cards are not valid targets.
    """

    icon: BattleIcon

    def __post_init__(self) -> None:
        if not isinstance(self.icon, BattleIcon):
            raise TypeError("battle-card flip requires a BattleIcon")
        if self.icon is BattleIcon.WILD:
            raise ValueError("the wild icon is always an alternative target")


@dataclass(frozen=True, slots=True)
class TrashDiscardPileCard:
    """Trash one card from the player's discard pile costing ``minimum_cost``
    or more (Tenuous Bond, Bloodlines). Starting cards have no cost and never
    qualify."""

    minimum_cost: int = 1

    def __post_init__(self) -> None:
        if self.minimum_cost < 0:
            raise ValueError("trash cost floor must not be negative")


@dataclass(frozen=True, slots=True)
class FlipFaceUpConflictCard:
    """Flip ``count`` of the player's face-up won Conflict cards face down,
    whatever their icons (Grasp Arrakis, Bloodlines); one choice per card."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("flip count must be positive")


# Arrakeen Scouts' own costs (composed A7b; ``content.arrakeen_scouts.types``
# re-exports them).


@dataclass(frozen=True, slots=True)
class LoseFactionInfluence:
    """Lose ``count`` Influence with one named Faction (Crackdown's Emperor
    loss, Betrayal's Bene Gesserit cost). The DSL's ``LoseInfluence`` lets
    the player pick the Faction, so it does not fit."""

    faction: Faction
    count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.faction, Faction):
            raise TypeError("Influence loss needs a Faction")
        if self.count < 1:
            raise ValueError("Influence loss count must be positive")


@dataclass(frozen=True, slots=True)
class LoseHighestInfluence:
    """Lose one Influence on the player's highest track, choosing among tied
    tracks (Political Equilibrium); nothing with no Influence at all."""


@dataclass(frozen=True, slots=True)
class LoseGarrisonTroops:
    """Lose ``count`` troops from the garrison to the supply (Bene Gesserit
    Treachery, Prison Planet). The DSL's ``LoseTroops`` also allows the
    Conflict, which these items do not."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("garrison loss count must be positive")


type Cost = (
    PayResources
    | LoseInfluence
    | DiscardFromHand
    | LoseTroops
    | GiveIntrigueToOpponent
    | TrashIntrigueCard
    | PutIntrigueOnDeckBottom
    | RecallSpy
    | RetreatTroops
    | FlipBattleCard
    | TrashDiscardPileCard
    | FlipFaceUpConflictCard
    | SpendSpecimens
    | TrashCard
    | LoseFactionInfluence
    | LoseHighestInfluence
    | LoseGarrisonTroops
)


# --- Rewards ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GainResources:
    """Gain public resources from the bank."""

    solari: int = 0
    spice: int = 0
    water: int = 0

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("resource gains must not be negative")
        if self.solari == self.spice == self.water == 0:
            raise ValueError("a resource gain must gain something")


@dataclass(frozen=True, slots=True)
class GainVictoryPoints:
    """Gain Victory Points."""

    amount: int = 1

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Victory Point gain must be positive")


@dataclass(frozen=True, slots=True)
class RecruitTroops:
    """Move up to ``count`` troops from supply to garrison."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("troop recruit count must be positive")


@dataclass(frozen=True, slots=True)
class DrawPersonalCards:
    """Draw from the player's personal deck, reshuffling if required."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("personal card draw count must be positive")


@dataclass(frozen=True, slots=True)
class ShuffleDiscardIntoDeck:
    """Refocus (the original game): shuffle the discard pile into the deck,
    then draw ``draw`` cards "Shuffle your discard pile into your deck, then:
    [draw 1]" [Refocus card, app text].

    The deck is shuffled along with the discard pile, so an empty discard
    pile still shuffles the deck [FAQ p. 3]; with both empty there is nothing
    to shuffle or draw. Nobody learns an order: the shuffle is a chance step
    (docs/rules/imperium-base.md 14).
    """

    draw: int = 1

    def __post_init__(self) -> None:
        if self.draw < 1:
            raise ValueError("a shuffle then draws at least one card")


@dataclass(frozen=True, slots=True)
class DrawIntrigueCards:
    """Draw from the shared Intrigue deck, reshuffling if required."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Intrigue draw count must be positive")


@dataclass(frozen=True, slots=True)
class GainCombatStrength:
    """Add strength to the player's Combat total for the current Conflict."""

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Combat strength gain must be positive")


@dataclass(frozen=True, slots=True)
class GainInfluence:
    """Gain one Influence ``times`` times with a chosen Faction each time.

    ``factions`` limits the choice; ``None`` allows any Faction. When exactly
    one Faction is allowed there is no choice. ``distinct`` forbids choosing
    the same Faction twice within one card.
    """

    times: int = 1
    factions: tuple[Faction, ...] | None = None
    distinct: bool = False
    # Ambitious (Twisted Intrigue): only a Faction where some opponent has
    # more Influence than the player.
    where_opponent_leads: bool = False
    # Navigation card 1: a Faction other than the one whose second Influence
    # played the card, where the player already has ``minimum_own``.
    different_from_trigger: bool = False
    minimum_own: int = 0
    # "Gain N Influence with the visited Faction" [Overthrow card]
    # [Subversive Advisor card]: the Faction of the space the Agent was sent
    # to, no choice; ``replaces_space``: the N replace the space's own 1 --
    # "기본 1 대신 총 2", never 2 + 1 [Main pp. 9, 11, 20]
    # (docs/rules/player-turns.md).
    visited_space: bool = False
    replaces_space: bool = False
    # "Gain two Influence with one Faction of your choice" (the original
    # game's two-chevron icon [DI p. 16], Grand Vision): one Faction chosen
    # once, gaining all ``times``.
    one_faction: bool = False

    def __post_init__(self) -> None:
        if self.times < 1:
            raise ValueError("Influence gain times must be positive")
        if self.one_faction and (self.distinct or self.times < 2):
            raise ValueError("a one-Faction gain repeats on that Faction")
        if self.visited_space and self.factions is not None:
            raise ValueError("the visited Faction is the only one a visited gain names")
        if self.replaces_space and not self.visited_space:
            raise ValueError("only a visited Faction's gain replaces the space's")
        if self.factions is not None:
            if not self.factions or len(self.factions) != len(set(self.factions)):
                raise ValueError("Influence gain Factions must be unique and non-empty")
            if any(not isinstance(faction, Faction) for faction in self.factions):
                raise TypeError("Influence gain Factions must use Faction")
            if self.distinct and self.times > len(self.factions):
                raise ValueError("distinct Influence gains exceed the allowed Factions")
        if not isinstance(self.distinct, bool):
            raise TypeError("distinct must be a boolean")

    @property
    def requires_choice(self) -> bool:
        """Return whether the player must pick a Faction."""

        if self.visited_space:
            return False
        return self.factions is None or len(self.factions) > 1


@dataclass(frozen=True, slots=True)
class DestroyShieldWall:
    """The Shield Wall detonation icon: the player may remove the token.

    Offered as a choice while the Shield Wall is present [Main pp. 10, 20];
    it does nothing once the token is gone.
    """


@dataclass(frozen=True, slots=True)
class SummonSandworm:
    """Take ``count`` sandworms from the bank straight into the Conflict.

    Does nothing while the current Conflict is protected by the Shield Wall
    [Main p. 20]. Cards that require Maker Hooks set ``requires_maker_hooks``.
    """

    count: int = 1
    requires_maker_hooks: bool = False

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("sandworm count must be positive")
        if not isinstance(self.requires_maker_hooks, bool):
            raise TypeError("requires_maker_hooks must be a boolean")


@dataclass(frozen=True, slots=True)
class DeployFromGarrison:
    """Deploy up to ``up_to`` garrison troops to the Conflict (player choice).

    ``up_to=None`` is a printed "any number" [Rapid Mobilization card]: as
    for a retreat, zero is a choice too [FAQ p. 3].

    ``dreadnoughts``: "Deploy up to two units from your garrison to the
    Conflict." [Second Wave card, Steam app text] -- a unit is a troop or a
    dreadnought [Rise of Ix p. 6], so the garrison dreadnoughts are among
    what the owner may deploy, within the same ``up_to``. Without it a card's
    "troop" never reaches a dreadnought.
    """

    up_to: int | None
    dreadnoughts: bool = False

    def __post_init__(self) -> None:
        if self.up_to is not None and self.up_to < 1:
            raise ValueError("deployment limit must be positive")


@dataclass(frozen=True, slots=True)
class TrashPersonalCard:
    """The black trash icon: optionally trash one card from hand, discard, or play.

    Optional per [Main p. 20]; the player may decline. ``hand_only`` and
    ``mandatory`` carry printed text such as Devious's "Trash a card from
    your hand".
    """

    hand_only: bool = False
    mandatory: bool = False
    # Navigation card 5: spice when the trashed card is printed with a cost
    # of at least ``bonus_minimum_cost`` Persuasion.
    bonus_spice: int = 0
    bonus_minimum_cost: int = 0


@dataclass(frozen=True, slots=True)
class PlaceSpy:
    """Place a Spy on an empty Observation Post, limited to ``factions`` if set.

    ``agent_icons`` limits it instead to posts connected to a board space
    with one of those Agent icons: "'[Spy] on [City]' means the observation
    post must connect to a [City] board space" [Main p. 20].

    Without a Spy in supply the player first recalls one [Main pp. 11, 20].
    ``shared_post`` adds the posts held only by other players' Spies to the
    normal empty-post targets, for card text that says the Spy *may* go on
    the same post as another player's Spy [Distraction card] -- the Spy with
    Deep Cover set [Bloodlines p. 5]; the owner's own posts never qualify.
    ``visited_space`` limits it to the posts connected to the board space the
    owner sent an Agent to this turn [Double Agent card], and may share one.
    """

    factions: tuple[Faction, ...] | None = None
    shared_post: bool = False
    agent_icons: tuple[AgentIcon, ...] | None = None
    visited_space: bool = False

    def __post_init__(self) -> None:
        if self.factions is not None:
            if not self.factions or len(self.factions) != len(set(self.factions)):
                raise ValueError("Spy target Factions must be unique and non-empty")
            if any(not isinstance(faction, Faction) for faction in self.factions):
                raise TypeError("Spy target Factions must use Faction")
        if self.agent_icons is not None:
            if not self.agent_icons or len(self.agent_icons) != len(
                set(self.agent_icons)
            ):
                raise ValueError("Spy target Agent icons must be unique and non-empty")
            if any(not isinstance(icon, AgentIcon) for icon in self.agent_icons):
                raise TypeError("Spy target Agent icons must use AgentIcon")
            if self.factions is not None:
                raise ValueError("a Spy target is Factions or Agent icons, not both")
        if not isinstance(self.shared_post, bool):
            raise TypeError("shared_post must be a boolean")
        if self.shared_post and (
            self.factions is not None or self.agent_icons is not None
        ):
            raise ValueError("a shared-post placement cannot limit its posts")
        if not isinstance(self.visited_space, bool):
            raise TypeError("visited_space must be a boolean")
        if self.visited_space and (
            self.factions is not None or self.agent_icons is not None
        ):
            raise ValueError("a visited-space placement names no other limit")


@dataclass(frozen=True, slots=True)
class TakeContract:
    """The Contract icon: take ``count`` face-up Contracts (CHOAM Module)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Contract count must be positive")


@dataclass(frozen=True, slots=True)
class AcquireCardUpTo:
    """Acquire one Imperium Row or Reserve card costing at most ``max_cost``.

    No Persuasion is spent; the printed cost cap limits the choice among the
    five Row cards and the Reserve stacks [Main p. 13] (OQ-125, user ruling
    2026-10-23: Arrakis Liaison and The Spice Must Flow, never Foldspace
    [FAQ p. 2]), plus the owner's own Manipulate set-aside card at its
    printed cost [FAQ p. 3]. The card lands
    in the owner's discard pile [Main pp. 6, 13] unless ``to_hand_if`` holds
    when the acquisition resolves, in which case the card text puts it in
    hand, or ``to_deck_top`` says the card goes on top of the owner's deck
    (Bypass Protocol's "[2 spice] -> Acquire a card that costs [Persuasion 5]
    or less to the top of your deck", docs/rules/open-questions.md OQ-125).
    """

    max_cost: int
    to_hand_if: Condition | None = None
    to_deck_top: bool = False

    def __post_init__(self) -> None:
        if self.max_cost < 1:
            raise ValueError("acquisition cost cap must be positive")
        if self.to_deck_top and self.to_hand_if is not None:
            raise ValueError("a card goes to the deck top or to the hand, not both")


@dataclass(frozen=True, slots=True)
class AcquireCardForSolari:
    """Acquire an Imperium Row or Reserve card to hand, paying its cost in
    solari [Price is No Object card] -- the owner's own Manipulate set-aside
    card too, at its printed cost [FAQ p. 3]. Only an Agent box offers it
    (``rules.acquisition.agent_box_acquisition``); the A1 executor does not."""


@dataclass(frozen=True, slots=True)
class SetAsideImperiumRowCard:
    """Remove and replace one Imperium Row card, setting it aside for the owner.

    Until the owner's Reveal turn this round ends, only they may acquire the
    set-aside card, for ``discount`` less Persuasion; their other acquire
    effects reach it at its printed cost, opponents never can, and an
    unacquired card leaves the game with that Reveal turn [FAQ p. 3].
    """

    discount: int = 1

    def __post_init__(self) -> None:
        if self.discount < 1:
            raise ValueError("set-aside discount must be positive")


@dataclass(frozen=True, slots=True)
class CommanderDiscountThisTurn:
    """Recruiting a Sardaukar Commander (including when acquiring one) costs
    ``amount`` less Solari for the rest of this turn (Honor Guard, Bloodlines)."""

    amount: int = 1

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Commander discount must be positive")


@dataclass(frozen=True, slots=True)
class IgnoreInfluenceRequirementsThisTurn:
    """Board-space Influence requirements are ignored when sending an Agent
    this turn (Insider Information, Bloodlines)."""


@dataclass(frozen=True, slots=True)
class GrantCombatDeployment:
    """The Combat icon: this turn the owner may deploy to the Conflict as
    though an Agent had been sent to a Combat space [Bloodlines pp. 5, 12]."""


@dataclass(frozen=True, slots=True)
class DeployTheseTroops:
    """"You may deploy these troops to the Conflict" after a recruit in the
    same line (the original game's Gurney Halleck Reveal box, Reinforcements:
    "If it's your Reveal turn, you may deploy any of these troops"). In a
    Reveal turn the troops the line recruited may be deployed, any number of
    them (Gurney: "Yes. It's indeed 0, 1, or 2.", the designer), and a troop
    it owed for an empty supply once it is refilled later in the turn
    (OQ-140, ``combat_deployment.recruit_room``); other effects' recruits do
    not. In an Agent turn it adds nothing, as troops recruited then deploy
    by the Combat space rule [DI p. 10] [FAQ p. 4]."""


@dataclass(frozen=True, slots=True)
class GrantAgentIconThisTurn:
    """The card the owner plays this turn has ``icon`` as well (Emperor's
    Invitation, Bloodlines)."""

    icon: AgentIcon

    def __post_init__(self) -> None:
        if not isinstance(self.icon, AgentIcon):
            raise TypeError("granted Agent icon must use AgentIcon")


@dataclass(frozen=True, slots=True)
class PermanentRevealPersuasion:
    """Navigation card 3 in slot 4: ``amount`` Persuasion at every later Reveal."""

    amount: int = 1

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("permanent Persuasion must be positive")


@dataclass(frozen=True, slots=True)
class AcquireReserveCard:
    """Acquire one named Reserve card to the discard pile (Navigation card 4)."""

    card_id: str

    def __post_init__(self) -> None:
        if not self.card_id:
            raise ValueError("Reserve acquisition needs a card")


@dataclass(frozen=True, slots=True)
class AcquireTech:
    """The Acquire Tech icon with a ``discount`` (Tech Module): open the
    owner's choice of a face-up Tech tile at ``discount`` spice off
    [Bloodlines pp. 7, 12].

    In a Rise of Ix game it is the Ix board's Acquire Tech icon
    ("아이콘마다 ... 하나를 얻을 수 있다("may")", [Rise of Ix p. 4],
    docs/rules/rise-of-ix.md 4): the same piece, one per icon, opening the
    choice of an Ix tile that the owner may also decline, at ``discount`` off
    and with any Negotiators returned (``rules.tech``)."""

    discount: int = 1

    def __post_init__(self) -> None:
        if self.discount < 0:
            raise ValueError("Tech discount must not be negative")


@dataclass(frozen=True, slots=True)
class GainSolariPerUnitType:
    """Calculating (Twisted Intrigue): one Solari per kind of unit in the
    Conflict (troops, sandworms, Sardaukar Commanders, a fighting Agent)."""


@dataclass(frozen=True, slots=True)
class PeekTopCard:
    """Controlled (Twisted Intrigue): look at the top card of the deck and
    put it back, discard it, or pay one Solari to draw it (player choice).

    ``draw_or_trash``: Poison Snooper (the original game), "Look at the top
    card of your deck. Draw or trash it." [Poison Snooper card, app text]:
    the look is the same, but the card is drawn (free) or trashed, never put
    back or discarded; it is mandatory once the card is played."""

    draw_or_trash: bool = False


@dataclass(frozen=True, slots=True)
class GrantAgentIconsThisTurn:
    """Resourceful (Twisted Intrigue): the card played this turn has these
    Agent icons as well."""

    icons: tuple[AgentIcon, ...]

    def __post_init__(self) -> None:
        if not self.icons or len(self.icons) != len(set(self.icons)):
            raise ValueError("granted Agent icons must be unique and non-empty")
        if any(not isinstance(icon, AgentIcon) for icon in self.icons):
            raise TypeError("granted Agent icons must use AgentIcon")


@dataclass(frozen=True, slots=True)
class PassTurn:
    """Withdrawn (Twisted Intrigue): "At the start of your turn: pass your
    turn" — the option is playable only from the turn frame.

    ``optional``: Bindu Suspension (the original game), "[draw 1]. You may
    pass your turn." [Bindu Suspension card, app text] -- after the draw the
    owner chooses to pass or to play the turn normally (OQ-117), so it is a
    choice of the card's frame, taken after the rest of the line resolved."""

    optional: bool = False


@dataclass(frozen=True, slots=True)
class RedirectSpiesOnTurnSpace:
    """False Orders (Bloodlines): each opponent spying on the board space the
    owner sent an Agent to this turn must move that Spy; then the owner
    places a Spy on that space. Needs an Agent placement this turn."""


@dataclass(frozen=True, slots=True)
class RevealContractsTakeOne:
    """Coercive Negotiation (Bloodlines): reveal ``count`` Contracts from the
    bank, take one and trash the others. Resolved in the
    ``intrigue_trigger_contract`` frame (``rules.intrigue_triggers``) that
    playing the card opens once it has left the hand."""

    count: int = 3

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("revealed Contract count must be positive")


@dataclass(frozen=True, slots=True)
class Research:
    """Trigger one Research icon [Immortality pp. 6, 16]."""


@dataclass(frozen=True, slots=True)
class AdvanceTleilaxu:
    """Advance the Tleilaxu token ``count`` spaces [Immortality pp. 7, 16]."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Tleilaxu advance must be positive")


@dataclass(frozen=True, slots=True)
class GenerateSpecimens:
    """Generate ``count`` specimens from the supply [Immortality pp. 8, 16]."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("specimen count must be positive")


@dataclass(frozen=True, slots=True)
class AcquireTleilaxuCard:
    """You may acquire a Tleilaxu Row card, paying its specimen cost
    (Harvest Cells) [Immortality p. 8]: a dealt card, or Reclaimed Forces
    for one of its effects, the card left in place [Immortality p. 9] (user
    ruling 2026-10-06)."""


@dataclass(frozen=True, slots=True)
class RevealPersuasionThisRound:
    """Gain ``amount`` Persuasion during the owner's Reveal turn this round
    (Tleilaxu Puppet)."""

    amount: int = 1

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Persuasion bonus must be positive")


@dataclass(frozen=True, slots=True)
class AcquireToDeckTopThisRound:
    """You may put cards you acquire on top of your deck, during the owner's
    Reveal turn this round (Recruitment Mission): "for each card acquired the
    owner chooses top of deck or discard pile" [FAQ p. 3]
    (docs/rules/imperium-base.md 13.2). Not retroactive: cards acquired
    before the card is played are unaffected (13.3). The whole card waits for
    the owner's Reveal turn [FAQ p. 2]."""


@dataclass(frozen=True, slots=True)
class ReturnThisCardToHand:
    """Return this card from play to its owner's hand, face up so far so it
    stays known (OQ-010) [Weirding Woman card]. Only a card counted in play
    can return: a Row card borrowed with Usurp is not in play (OQ-054)."""


@dataclass(frozen=True, slots=True)
class BoostNextBeneGesseritCard:
    """The next Bene Gesserit card the owner plays this round has all Agent
    icons and adds "Draw 1 card" to its Agent box [Urgent Shigawire card]."""


@dataclass(frozen=True, slots=True)
class DrawPerSandwormInConflict:
    """Draw 1 card for each of the owner's sandworms in the Conflict
    [Leadership card]."""


@dataclass(frozen=True, slots=True)
class TrashThisCard:
    """Trash this card, as a printed effect of its own ("Trash this card."
    [Dangerous Rhetoric card], [Seek Allies card]): mandatory [Main p. 20];
    the card's other effects still pay once it is gone (OQ-022)."""


@dataclass(frozen=True, slots=True)
class RecallAgent:
    """Recall one of the player's Agents from a board space: any but the one
    sent this turn ("Recall 1 Agent" [Steersman card]), or with
    ``sent_this_turn`` exactly that one ("You may recall the Agent you sent
    this turn" [Twisted Mentat card], ``optional``)."""

    sent_this_turn: bool = False
    optional: bool = False


@dataclass(frozen=True, slots=True)
class RecallYourAgent:
    """Recall one of the player's own Agents ("Recall one of your Agents"
    [Urgent Mission card, app text]): any of them, the one sent this turn
    included -- the exclusion belongs to Uprising's Recall Agent icon [Main
    p. 20], not to this card (docs/rules/imperium-base.md 13.3).

    The owner names a board space with its Agent, or the Conflict for an
    Agent Into the Fray left there (OQ-068); the Agent returns to its Leader
    (``agents_available`` + 1). The Mentat is one of the seat's Agents, and
    the engine does not tell its piece from the others (OQ-139, user ruling
    (가) 2026-10-28). Without an Agent on the board the effect fizzles."""


@dataclass(frozen=True, slots=True)
class EachOpponentDiscardsCard:
    """Each opponent discards a card [Covert Operation card]: every opponent
    holding a card picks one, clockwise from the next seat.

    ``count``: "each opponent discards two cards" [Reverend Mother Mohiam
    card] -- each opponent picks that many, as many as the hand holds
    (OQ-118), one opponent after the other. None is one card, so a record
    printed with one (Covert Operation) carries no count (an entity feature
    column only the original game's card fills).
    """

    count: int | None = None

    def __post_init__(self) -> None:
        if self.count is not None and self.count < 2:
            raise ValueError("a one-card discard carries no count")

    @property
    def cards(self) -> int:
        """How many cards each opponent discards."""

        return self.count or 1


@dataclass(frozen=True, slots=True)
class OpponentLosesTroop:
    """An opponent of the owner's choice loses one troop in the Conflict
    ("An opponent of your choice loses one troop in the Conflict" [Double
    Cross card, app text]; the troop goes back to its supply [DI p. 16]).

    The owner names the opponent -- only one with a troop in the Conflict
    (``OpponentHasTroopInConflict``, the card's official condition) -- and
    that seat chooses the troop it loses in the same window Holy War opens,
    limited to the Conflict (OQ-036 (a): the loser chooses the unit, a
    Sardaukar Commander being a troop for a card effect [Bloodlines p. 4]).
    """


@dataclass(frozen=True, slots=True)
class DeployFromSupply:
    """Deploy ``count`` troops from the owner's supply to the Conflict
    ("you deploy one troop from your supply to the Conflict" [Double Cross
    card, app text]): a deployment, not a recruit, so it needs no Combat icon.
    With an empty supply nothing deploys [FAQ p. 2] and the shortfall is
    recorded as Suspensor Suits' is (OQ-042 ruling (2): "Double Cross ...
    같은 기록을 쓴다"); while deployment is banned (Emperor of the Known
    Universe, [Main p. 17]) nothing deploys.
    """

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("a deployment moves at least one troop")


@dataclass(frozen=True, slots=True)
class EachOpponentLosesTroop:
    """Each opponent loses one troop [Holy War card]: every opponent is
    asked, clockwise from the next seat, even with nothing to lose (OQ-036
    (a)).

    ``garrison_only``: "Each opponent loses one garrisoned troop" [Gun
    Thopter card] -- the loser's choice is limited to its garrison; one with
    no garrisoned troop is unaffected [FAQ p. 2] (and still confirms it,
    OQ-036 (a)).
    """

    garrison_only: bool = False


@dataclass(frozen=True, slots=True)
class EachOpponentDiscardsOrLosesDeployedTroop:
    """Each opponent chooses: discard a card -OR- lose a deployed troop
    ("Each opponent chooses: Discard a card -OR- Lose a deployed troop" [Test
    of Humanity card]).

    Every opponent is asked, clockwise from the next seat; each must choose
    what it can -- the discard needs a card in hand, the loss a troop in the
    Conflict ("손이 비면 버리기 불가, 배치한 troop이 없으면 잃기 불가"
    [DI p. 13], imperium-base.md 13.1) -- and the discarder picks the card.
    One with neither is unaffected and confirms it (OQ-138). A lost troop
    goes to the supply [DI p. 16]. A Sardaukar Commander in the Conflict is a
    deployed troop too [Bloodlines p. 4] (OQ-115), so with Bloodlines the
    loss may name one.
    """


@dataclass(frozen=True, slots=True)
class TakeCardFromDiscard:
    """Put a card of ``faction``'s affiliation of the player's choice from
    their own discard pile into their hand ("Draw a Bene Gesserit card from
    your discard pile" [Other Memory card]).

    Only a card there can be taken: the choice is not offered with none
    (imperium-base.md 15). The pile is face up, so the card reaches the hand
    by a public path and every seat knows it (imperium-base.md 14, OQ-010).
    """

    faction: Faction

    def __post_init__(self) -> None:
        if not isinstance(self.faction, Faction):
            raise TypeError("a discard-pile card is taken by a Faction")


@dataclass(frozen=True, slots=True)
class BlockChosenSpaceForOpponentsNextAgent:
    """Choose any board space; no opponent may send their next Agent there
    this round ("Opponents can't send their next Agents there this round"
    [The Voice card]).

    The space is the owner's mandatory choice among every board space on the
    table, occupied or not, the owner's own included (imperium-base.md 15).
    Each opponent's block lasts until that opponent's next Agent placement of
    the round (OQ-116, 2026-10-22 user ruling B): a turn passed without an
    Agent does not use it up, and the end of the round clears it. It is no
    Agent, so nothing that lets a seat ignore occupying Agents beats it
    (``PlayerState.voice_blocked_space_ids``).
    """


@dataclass(frozen=True, slots=True)
class IgnoreEnemyAgentsNextPlacement:
    """Enemy Agents don't block the owner's next Agent at board spaces this
    turn ("Enemy Agents don't block your next Agent at board spaces this
    turn" [Infiltrate card, app text]).

    Every opponent Agent -- an opponent's Mentat is one -- is treated as not
    occupying the space, as Helena's Eyes Everywhere does; the owner's own
    Agent, Influence requirements, once-per-game limits, costs and The Voice
    still stop the placement. Set for this turn
    (``PlayerState.enemy_agents_ignored_turn``) and spent by the turn's
    Agent placement.
    """


@dataclass(frozen=True, slots=True)
class OpponentsMoveSpiesFromVisitedSpace:
    """Each opponent spying on the board space where the player sent an
    Agent this turn must move that Spy [Holy War card] (OQ-036 (b))."""


class PrintedRevealValue(StrEnum):
    """A revealed card's own printed value a choice holds back."""

    PERSUASION = "persuasion"
    SPICE = "spice"


@dataclass(frozen=True, slots=True)
class KeepPrintedReveal:
    """"Keep the Persuasion" [Desert Power card] / "Keep the spice" [Priority
    Contracts card]: the card's own printed Reveal value, held from every
    total until this line is chosen (OQ-069; OQ-028 (b) addition)."""

    value: PrintedRevealValue


@dataclass(frozen=True, slots=True)
class GainSolariPerPartnerAgentIcon:
    """Gain 1 Solari per Agent icon on the other grafted card [Slig Farmer
    card]: borrowed and conditional icons count too -- Blank Slate's grafted
    Faction icons, Servo-Receivers' Signet icons, a met Long Reach condition
    -- since the card carries them (OQ-055, user ruling 2026-09-08)."""


@dataclass(frozen=True, slots=True)
class ReturnOtherGraftedCardAtRevealStart:
    """At the start of the owner's Reveal turn, the other grafted card goes
    from play back to the hand [Chairdog card]. The return is noted on the
    seat when the pair is grafted (adopted designer ruling,
    ``graft.apply_graft_partner``) and carried out by ``begin_reveal_turn``;
    nothing returns once that card has left play."""


@dataclass(frozen=True, slots=True)
class AcquireBankCommander:
    """Acquire and recruit the Sardaukar Commander in the bank [Sardaukar
    Standard card]: with a face-up Skill choice, or without a Skill when none
    is choosable (OQ-031); nothing with an empty bank (OQ-035)."""


class RevealCountKind(StrEnum):
    """What a Reveal gain is counted per (``RevealCount``)."""

    # Each card of ``faction`` revealed this turn (Sardaukar Coordination).
    REVEALED_FACTION_CARD = "revealed_faction_card"
    # Each card of ``faction`` the player has in play, Agent turns included
    # [Main p. 20 "In Play"] (Stilgar, The Devoted).
    FACTION_CARD_IN_PLAY = "faction_card_in_play"
    # Each Contract the player has completed, later ones included (OQ-028
    # (c), Interstellar Trade).
    COMPLETED_CONTRACT = "completed_contract"
    # Each other revealed card with swords (Leadership).
    OTHER_SWORD_CARD = "other_sword_card"
    # Each of the player's dreadnoughts in the Conflict when the line resolves
    # (Rise of Ix's Full-Scale Assault); the swords stay if one leaves later
    # (rise-of-ix.md 9.3, designer ruling; [DI p. 11]).
    DREADNOUGHT_IN_CONFLICT = "dreadnought_in_conflict"


@dataclass(frozen=True, slots=True)
class RevealCount:
    """The count a Reveal gain is multiplied by; ``faction`` for the two
    Faction-card counts."""

    kind: RevealCountKind
    faction: Faction | None = None

    def __post_init__(self) -> None:
        by_faction = self.kind in (
            RevealCountKind.REVEALED_FACTION_CARD,
            RevealCountKind.FACTION_CARD_IN_PLAY,
        )
        if by_faction != (self.faction is not None):
            raise ValueError("only a Faction-card count names a Faction")


@dataclass(frozen=True, slots=True)
class RevealPersuasion:
    """+``amount`` Persuasion on the Reveal, spent this turn and counted for
    Command [Main p. 9]; ``per`` multiplies it."""

    amount: int
    per: RevealCount | None = None

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Reveal Persuasion must be positive")
        if self.per is not None and self.per.kind is RevealCountKind.OTHER_SWORD_CARD:
            raise ValueError("Persuasion is not counted per sword card")


@dataclass(frozen=True, slots=True)
class RevealSwords:
    """+``amount`` swords on the Reveal, counted as strength only with a unit
    in the Conflict [Main p. 9]; ``per`` multiplies them."""

    amount: int
    per: RevealCount | None = None

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Reveal swords must be positive")
        if self.per is not None and self.per.kind in (
            RevealCountKind.FACTION_CARD_IN_PLAY,
            RevealCountKind.COMPLETED_CONTRACT,
        ):
            raise ValueError("swords are counted per revealed card only")


@dataclass(frozen=True, slots=True)
class TakeHighCouncilSeat:
    """Take the High Council seat [Corrinth City card]: its +2 Persuasion on
    each Reveal from now [Main p. 10]."""


@dataclass(frozen=True, slots=True)
class TakeControl:
    """Take control of ``space_id`` [Main p. 10] [Main p. 20]: the player's
    control marker goes there, an opponent's moves off."""

    space_id: str


@dataclass(frozen=True, slots=True)
class TakeMentat:
    """The Mentat icon: "Take the Mentat from its space on the board (if it's
    there; you can't take it from another player or another space)" [DI p. 16]
    -- used as one of the taker's Agents for the round [DI p. 18] (the
    original game; docs/rules/imperium-base.md 9)."""


@dataclass(frozen=True, slots=True)
class TakeSwordmaster:
    """Once per game, take the player's third Agent [Main p. 20], usable from
    this round [Board Guide p. 2] (the Swordmaster space)."""


@dataclass(frozen=True, slots=True)
class RecruitUndeployableTroops:
    """Recruit ``count`` troops that can't be deployed to the Conflict this
    turn [Piter De Vries card] (OQ-038)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("troop recruit count must be positive")


@dataclass(frozen=True, slots=True)
class TakeSetupSpice:
    """The first player to reach the space takes the spice placed there
    during setup [Immortality pp. 4, 7] (the Tleilaxu track's fourth
    space)."""


@dataclass(frozen=True, slots=True)
class DrawTwistedIntrigueCards:
    """Draw ``count`` cards from the player's own Twisted Intrigue deck
    [Piter De Vries card] (OQ-072, OQ-097)."""

    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("draw count must be positive")


@dataclass(frozen=True, slots=True)
class TroopToMemory:
    """Move 1 troop from the supply to the Bene Gesserit board area as a
    memory [Lady Jessica card]; nothing moves with the supply empty."""


@dataclass(frozen=True, slots=True)
class GainInfluenceWhereAtMost:
    """Gain 1 Influence with each Faction where the player has ``maximum``
    or less Influence [Panopticon Tech tile]."""

    maximum: int = 1

    def __post_init__(self) -> None:
        if self.maximum < 0:
            raise ValueError("an Influence ceiling must not be negative")


@dataclass(frozen=True, slots=True)
class GainInfluenceWhereAgent:
    """Gain one Influence with each Faction that has at least one of the
    player's Agents on its board spaces [Quid Pro Quo card]: each such
    Faction once, however many of the player's Agents are on its spaces."""


@dataclass(frozen=True, slots=True)
class UseSignetAbility:
    """The Signet Ring icon off the Signet Ring card: "you use the Signet
    Ring ability (with the corresponding icon) on your Leader" [Main p. 20]
    (Servo-Receivers' acquire icon [Bloodlines p. 7])."""


@dataclass(frozen=True, slots=True)
class PledgeFirstPlaceInfluence:
    """Add 1 Influence of the player's choice to this Conflict's first-place
    reward [Pivotal Gambit card]: chosen with that reward (OQ-025)."""


@dataclass(frozen=True, slots=True)
class ForceEnemyRetreat:
    """Force an enemy troop to retreat [Disruption Tactics card]: one unit of
    an opponent's in the Conflict goes back to its garrison. A Sardaukar
    Commander is a troop [Bloodlines p. 4]; the acting player picks the
    opponent and, where both kinds are there, the kind (OQ-034).

    Desert Ambush (Rise of Ix): "For each troop you deploy this turn, you may
    force an enemy unit to retreat." [Steam app text]. ``units``: an enemy
    *unit*, so a dreadnought too ("unit | ... Desert Ambush(enemy unit) |
    예", docs/rules/rise-of-ix.md 6, [Rise of Ix p. 6]), the player of the
    card picking it (rise-of-ix.md 9.3, designer ruling; sandworms are P7).
    ``per_troop_deployed``: one retreat for each troop the owner deploys this
    turn, counted as OQ-029 counts the turn's deployment ("같은 큐브를
    retreat했다 다시 배치해도 두 번 세지 않음", rise-of-ix.md 15), each a
    "may".
    """

    units: bool = False
    per_troop_deployed: bool = False


@dataclass(frozen=True, slots=True)
class CompleteContract:
    """Complete one of your contracts [CHOAM Demands card]: an active
    Contract of the owner's, whatever its printed condition."""


@dataclass(frozen=True, slots=True)
class LookAtIntrigueKeepOne:
    """Look at the Intrigue deck's top ``count`` cards, keep 1 and put the
    rest back on top [Imperium Ceremony card]."""

    count: int = 2

    def __post_init__(self) -> None:
        if self.count < 2:
            raise ValueError("a peek to keep one looks at two or more cards")


# Arrakeen Scouts' own rewards (composed A7b).


@dataclass(frozen=True, slots=True)
class RecallOtherAgent:
    """Return one of the player's Agents from a board space to their supply,
    other than the Agent that just took the High Council seat
    (Contingencies; which Agent counts is an open question)."""


@dataclass(frozen=True, slots=True)
class RecruitToConflict:
    """Recruit ``count`` troops from the supply straight into the Conflict
    (Shadow Warfare: troops recruited during the sale are deployed at once)."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("recruit count must be positive")


@dataclass(frozen=True, slots=True)
class AcquireReserveCardToHand:
    """Acquire one named Reserve card into the hand instead of the discard
    pile (Moment of Revelation: Prepare the Way)."""

    card_id: str

    def __post_init__(self) -> None:
        if not self.card_id:
            raise ValueError("Reserve acquisition needs a card")


@dataclass(frozen=True, slots=True)
class GainLowestInfluence:
    """Gain one Influence with the Faction where the player has the least,
    choosing among tied Factions (Covert Operation's delayed choice)."""


@dataclass(frozen=True, slots=True)
class GainSpiceWithHelixBonus:
    """Gain ``spice`` spice, or ``helix_spice`` instead when the player's
    research has reached the Helix (Offworld Operation's first-round choice;
    what "reached the Helix" means is an open question)."""

    spice: int = 1
    helix_spice: int = 2

    def __post_init__(self) -> None:
        if not 1 <= self.spice < self.helix_spice:
            raise ValueError("the Helix amount must beat the plain amount")


@dataclass(frozen=True, slots=True)
class DoubleBaseHarvestSpice:
    """Double the base (not bonus) spice the Agent harvests this turn
    ("Double the base (not bonus) spice you harvest with this Agent"
    [Carryall card]).

    A modifier of the Maker space's harvest, not a step of its own: the box
    never opens (``AbilityMark.AUTOMATIC``), the harvest reads it. The base
    is the spice the space prints beside its bonus -- 1, 2 or 3 at Imperial
    Basin, Hagga Basin and The Great Flat [FAQ p. 1]; nothing at a space that
    is not a harvest (Secure Contract, Sell Melange, Imperial Basin's control
    bonus).
    """


@dataclass(frozen=True, slots=True)
class DoubleBonusHarvestSpice:
    """Double the bonus spice the Agent harvests this turn ("Double the bonus
    spice you harvest with this Agent" [Thumper card, app text]).

    A modifier of the Maker space's harvest, not a step of its own, like
    ``DoubleBaseHarvestSpice``: the box never opens (``AbilityMark.AUTOMATIC``),
    the harvest reads it. The bonus is the spice the space has gathered
    [DI p. 13]; the base spice does not double, the extra comes from the bank,
    and nothing doubles at a space that is not a harvest. Countess Ariana's one
    less comes off the whole harvest once, after the doubling
    (docs/rules/imperium-base.md 16).
    """


@dataclass(frozen=True, slots=True)
class ReserveCostDiscount:
    """Every copy of the named Reserve card acquired during this Reveal turn
    costs ``amount`` less ("The Spice Must Flow costs {Persuasion_3} less to
    acquire this turn" [Guild Bankers card]).

    ``card_ids`` lists the printings the sentence names: the Reserve card's
    id in each game ("the_spice_must_flow", the original game's
    "imperium_the_spice_must_flow"). It holds for each copy, not the first
    only ("마다 할인", [FAQ p. 2]); it is read as the card's cost anywhere
    (``reserve_cost``), so the cost check and the payment agree.
    """

    card_ids: tuple[str, ...]
    amount: int

    def __post_init__(self) -> None:
        if not self.card_ids:
            raise ValueError("a Reserve discount names a Reserve card")
        if self.amount < 1:
            raise ValueError("a Reserve discount must be positive")


@dataclass(frozen=True, slots=True)
class CommissionDreadnought:
    """Commission one of the owner's dreadnoughts: one from its supply to its
    garrison for each Dreadnought icon ("you may commission", [Rise of Ix
    p. 6], docs/rules/rise-of-ix.md 6).

    An optional piece ("may"): the owner takes the icon or leaves it. With
    no dreadnought in the supply -- a seat has two at most, and "supply에
    없으면 더 얻지 못한다" -- the icon has no effect and the space or card
    that prints it is still played (designer ruling, BGG forum). A second
    icon is a second piece; the piece has no field.
    """


@dataclass(frozen=True, slots=True)
class EachOpponentRetreatsDreadnought:
    """Each opponent retreats one dreadnought ("Each opponent retreats one
    dreadnought." [Cannon Turrets card, Steam app text]): every opponent with
    a dreadnought in the Conflict sends one back to its garrison, clockwise
    from the next seat; one without is unaffected.

    A dreadnought is a unit and the card names it, so unlike a card's "troop"
    it is reached [Rise of Ix p. 6] (docs/rules/rise-of-ix.md 6, the table
    row "dreadnought"). The dreadnoughts of a seat are alike, so the
    opponent has nothing to choose and the retreat is automatic.
    """


@dataclass(frozen=True, slots=True)
class PledgeConflictWinSolari:
    """"If you win this Conflict:" ``solari`` Solari [Strategic Push card,
    Steam app text; its log: "If they win the Conflict they will gain" the
    Solari], pledged as the Combat card resolves and gained only by the
    Conflict's sole winner.

    The pledge waits on the seat (``PlayerState.strategic_push_solari``) and
    is paid as an automatic row of the sole winner's window, in the order
    the winner chooses among that window's rows (OQ-121 ruling 6 (1):
    "Strategic Push의 'If you win this Conflict' 몫(Solari 2)은 고를 것 없는
    자동 줄이다"). A tie for first has no win effect row [FAQ p. 4], and a
    pledge that is not paid lapses when the Conflict ends.
    """

    solari: int = 2

    def __post_init__(self) -> None:
        if self.solari < 1:
            raise ValueError("a pledged Solari amount must be positive")


@dataclass(frozen=True, slots=True)
class PlaceNegotiator:
    """Tech Negotiation: send one of the owner's troops from its supply to
    the Ix board as a Negotiator, for each Tech Negotiation icon ("you may
    take a troop", [Rise of Ix p. 4], docs/rules/rise-of-ix.md 4).

    An optional piece ("may"): the owner takes the icon or leaves it. With
    no troop in the supply the icon has no effect ("supply가 비면 아무 일도
    없다") and the space or card that prints it is still played. A later
    Acquire Tech may return any number of Negotiators for one spice off
    each (``rules.tech``). A second icon is a second piece; the piece has
    no field.
    """


@dataclass(frozen=True, slots=True)
class Freighter:
    """The Freighter icon: move the owner's Freighter on the Shipping track,
    one choice for each icon ("Freighter 아이콘마다 Freighter를 둘 가운데
    하나로 움직일 수 있다("may"): 한 칸 위로(맨 위면 불가) 또는 맨 아래로
    회수", [Rise of Ix p. 5], docs/rules/rise-of-ix.md 5).

    An optional piece: the owner moves up one space (never from the top),
    recalls the Freighter to the bottom -- taking the rewards of its space and
    of every space below, in the order it chooses (``rules.shipping_track``)
    -- or neither. A second icon is a second piece; the piece has no field.
    """


@dataclass(frozen=True, slots=True)
class TakeAnotherTurn:
    """"You may take another turn immediately after this one." [Weirding Way
    card, Steam app text]: the owner's next turn follows this one at once,
    an Agent or a Reveal turn [DI p. 8]; then play goes on clockwise from
    the owner. Optional ("may"). The Voice does not block it ("Weirding Way의
    둘째 turn은 The Voice에 막히지 않음", docs/rules/rise-of-ix.md 9.3;
    imperium-base.md 13.1, OQ-116), and Ilesa Ecaz counts it as a turn
    (OQ-119)."""


type Reward = (
    GainResources
    | GainVictoryPoints
    | RecruitTroops
    | DrawPersonalCards
    | ShuffleDiscardIntoDeck
    | DrawIntrigueCards
    | GainCombatStrength
    | GainInfluence
    | DestroyShieldWall
    | SummonSandworm
    | DeployFromGarrison
    | TrashPersonalCard
    | PlaceSpy
    | RetreatTroops
    | TakeContract
    | AcquireCardUpTo
    | SetAsideImperiumRowCard
    | CommanderDiscountThisTurn
    | IgnoreInfluenceRequirementsThisTurn
    | GrantAgentIconThisTurn
    | GrantCombatDeployment
    | DeployTheseTroops
    | RedirectSpiesOnTurnSpace
    | RevealContractsTakeOne
    | GainSolariPerUnitType
    | PeekTopCard
    | GrantAgentIconsThisTurn
    | PassTurn
    | PermanentRevealPersuasion
    | AcquireReserveCard
    | AcquireTech
    | Research
    | AdvanceTleilaxu
    | GenerateSpecimens
    | AcquireTleilaxuCard
    | RevealPersuasionThisRound
    | AcquireToDeckTopThisRound
    | ReturnThisCardToHand
    | BoostNextBeneGesseritCard
    | DrawPerSandwormInConflict
    | LookAtIntrigueKeepOne
    | ForceEnemyRetreat
    | CompleteContract
    | PledgeFirstPlaceInfluence
    | AcquireCardForSolari
    | TrashThisCard
    | RecallAgent
    | RecallYourAgent
    | EachOpponentDiscardsCard
    | EachOpponentLosesTroop
    | EachOpponentDiscardsOrLosesDeployedTroop
    | OpponentLosesTroop
    | DeployFromSupply
    | TakeCardFromDiscard
    | BlockChosenSpaceForOpponentsNextAgent
    | IgnoreEnemyAgentsNextPlacement
    | OpponentsMoveSpiesFromVisitedSpace
    | ReturnOtherGraftedCardAtRevealStart
    | GainSolariPerPartnerAgentIcon
    | KeepPrintedReveal
    | AcquireBankCommander
    | RevealPersuasion
    | RevealSwords
    | TakeHighCouncilSeat
    | TakeControl
    | TakeSwordmaster
    | TakeMentat
    | UseSignetAbility
    | GainInfluenceWhereAtMost
    | GainInfluenceWhereAgent
    | RecruitUndeployableTroops
    | TroopToMemory
    | DrawTwistedIntrigueCards
    | TakeSetupSpice
    | RecallOtherAgent
    | RecruitToConflict
    | AcquireReserveCardToHand
    | GainLowestInfluence
    | GainSpiceWithHelixBonus
    | ReserveCostDiscount
    | DoubleBaseHarvestSpice
    | DoubleBonusHarvestSpice
    | CommissionDreadnought
    | EachOpponentRetreatsDreadnought
    | PledgeConflictWinSolari
    | PlaceNegotiator
    | Freighter
    | TakeAnotherTurn
)


# --- Triggers ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OnRevealAcquisitionThisRound:
    """During the owner's Reveal turn this round, whenever they acquire a card.

    A card played with this trigger stays face up in front of its owner until
    the effect applies [FAQ p. 2], fires once per card acquired during the
    owner's Reveal turn, and is discarded when that Reveal turn ends.
    """


@dataclass(frozen=True, slots=True)
class OnTroopsLostAtConflictEnd:
    """When the owner loses ``minimum`` or more troops at the end of a
    Conflict (Harvest Cells).

    Troops (and Sardaukar Commanders, being troops) that return to the
    supply at Combat cleanup are "lost" [FAQ p. 1, Chani]. The card is
    played only in the window after the Conflict's rewards and only when
    the loss will meet ``minimum`` (user ruling 2026-10-06, OQ-057 (11)),
    then waits face up until the cleanup returns the troops.
    """

    minimum: int = 3

    def __post_init__(self) -> None:
        if self.minimum < 1:
            raise ValueError("loss trigger minimum must be positive")


@dataclass(frozen=True, slots=True)
class OnReachInfluence:
    """When the player reaches ``amount`` Influence with ``faction``
    [Lady Margot Fenring card] [Princess Irulan card]; like the Victory Point,
    passing it in one multi-step gain counts and re-reaching after a loss
    counts again [Main pp. 7, 17]."""

    faction: Faction
    amount: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.faction, Faction):
            raise TypeError("an Influence trigger names a Faction")
        if self.amount < 1:
            raise ValueError("an Influence trigger amount must be positive")


@dataclass(frozen=True, slots=True)
class OnOpponentAgentAtSpiedMakerSpace:
    """Whenever another player sends an Agent to a Maker board space the
    player is spying on [Staban Tuek card]."""


@dataclass(frozen=True, slots=True)
class OnCardTrashed:
    """Whenever the player trashes a card -- a personal card, not an
    Intrigue card [Count Hasimir Fenring card] [Bloodlines p. 12]."""


@dataclass(frozen=True, slots=True)
class OnAgentSentTo:
    """Whenever the player -- or with ``opponent`` another player -- sends
    an Agent to ``space_id`` [Esmar Tuek card]."""

    space_id: str
    opponent: bool = False


@dataclass(frozen=True, slots=True)
class OnRoundStart:
    """At Round Start, with the round's hand (OQ-072) [Piter De Vries
    card]."""


@dataclass(frozen=True, slots=True)
class OnSpiceGainedInTurnAtLeast:
    """Whenever the player gains ``amount`` or more spice in a single turn
    of theirs, once per turn (OQ-063) [Steersman Y'rkoon card]."""

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("a spice threshold must be positive")


@dataclass(frozen=True, slots=True)
class OnContractCompleted:
    """When the player completes a Contract [CHOAM Transports Tech
    tile]."""


@dataclass(frozen=True, slots=True)
class OnConflictWon:
    """When the player wins a Conflict -- alone [FAQ p. 4] [Planetary Array
    Tech tile]."""


@dataclass(frozen=True, slots=True)
class OnBoardSpaceSolariPaid:
    """Whenever the player pays Solari for the printed cost of a board space
    (the original game's Count Ilban Richese [FAQ p. 2];
    docs/rules/imperium-base.md 12)."""


@dataclass(frozen=True, slots=True)
class OnHighCouncilSeatTaken:
    """When the player takes a seat on the High Council (the original game's
    Earl Memnon Thorvald; docs/rules/imperium-base.md 12)."""


@dataclass(frozen=True, slots=True)
class OnMakerSpiceHarvested:
    """Whenever the player harvests spice at a Maker board space, and only
    there (the original game's Countess Ariana Thorvald [FAQ p. 2];
    docs/rules/imperium-base.md 12)."""


type Trigger = (
    OnRevealAcquisitionThisRound
    | OnTroopsLostAtConflictEnd
    | OnReachInfluence
    | OnOpponentAgentAtSpiedMakerSpace
    | OnCardTrashed
    | OnAgentSentTo
    | OnRoundStart
    | OnSpiceGainedInTurnAtLeast
    | OnContractCompleted
    | OnConflictWon
    | OnBoardSpaceSolariPaid
    | OnHighCouncilSeatTaken
    | OnMakerSpiceHarvested
)


# --- Composition ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EffectSection:
    """One printed line: an optional condition gating a cost and its rewards.

    When the condition holds the section is *applicable*. Applicable costs on
    an Intrigue card are mandatory once the card is played.
    """

    rewards: tuple[Reward, ...]
    condition: Condition | None = None
    costs: tuple[Cost, ...] = ()

    def __post_init__(self) -> None:
        # An Arrakeen Scouts line may only take something away (Crackdown).
        if not self.rewards and not self.costs:
            raise ValueError("an effect section must produce or exact something")
        if len(self.costs) != len(set(self.costs)):
            raise ValueError("an effect section cannot repeat the same cost")


@dataclass(frozen=True, slots=True)
class IntrigueOption:
    """One way to play an Intrigue card (the halves of an ``—OR—`` card).

    An option with a ``trigger`` does nothing when played; the card waits
    face up and its sections resolve each time the trigger fires. Two
    triggers name the moment the card is *played* instead, so the card is
    played from the hand then and resolves at once (``OnTroopsLostAtConflictEnd``,
    Harvest Cells' Conflict-end window; ``OnConflictWon``, a winning Intrigue
    in the winner's reward window, which may carry a cost and a condition).
    """

    timing: IntrigueTiming
    sections: tuple[EffectSection, ...]
    trigger: Trigger | None = None
    # "At the start of your turn": playable only from the turn frame, as the
    # turn's first action (Withdrawn; OQ-095 (6), user ruling 2026-10-04,
    # ``frames.turn_start_is_open``).
    turn_start_only: bool = False
    # Separate printed lines with no ``—OR—`` between them (Change
    # Allegiances, Strategic Stockpiling, Find Weakness): playing the card
    # opens its lines, cost-free lines resolve at once, and each arrow line
    # is used separately, paid when it is used (OQ-058, user ruling).
    separate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.timing, IntrigueTiming):
            raise TypeError("Intrigue option timing must use IntrigueTiming")
        if not self.sections:
            raise ValueError("an Intrigue option needs at least one section")
        if self.trigger is not None:
            # A Conflict-end loss trigger and a Conflict win are played during
            # Combat (Harvest Cells; To the Victor..., Demand Respect); every
            # other trigger card is a Plot card.
            expected = (
                IntrigueTiming.COMBAT
                if isinstance(self.trigger, OnTroopsLostAtConflictEnd | OnConflictWon)
                else IntrigueTiming.PLOT
            )
            if self.timing is not expected:
                raise ValueError(
                    f"this trigger's Intrigue options must use {expected.value} timing"
                )
            for section in self.sections:
                # A winning Intrigue is played from the hand once the win has
                # happened, so it may carry the cost and the condition its
                # play needs [FAQ p. 2]; a card waiting face up may not.
                if (section.costs or section.condition is not None) and not isinstance(
                    self.trigger, OnConflictWon
                ):
                    raise ValueError(
                        "triggered Intrigue sections must be free and unconditional"
                    )


# The Arrakeen Scouts module's own pieces (composed A7b): only a Scouts record
# prints them (``abilities.Ability``).
SCOUTS_ONLY_PIECES: Final = (
    LoseFactionInfluence,
    LoseHighestInfluence,
    LoseGarrisonTroops,
    RecallOtherAgent,
    RecruitToConflict,
    AcquireReserveCardToHand,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
)
