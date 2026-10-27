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
    """

    count: int = 3

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("deployed-units condition count must be positive")


@dataclass(frozen=True, slots=True)
class SpiceMustFlowCardsAtLeast:
    """The player owns at least ``count`` copies of The Spice Must Flow.

    Copies in the deck, hand, discard pile and play area count; a trashed
    copy has left the game.
    """

    count: int = 2

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("The Spice Must Flow count must be positive")


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


type Condition = (
    InfluenceAtLeast
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
    | HasSwordmaster
    | SpyingOnMakerSpace
    | GarrisonedUnitsAtLeast
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
    """Discard ``count`` personal cards chosen from hand."""

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
    """

    minimum: int = 1
    maximum: int | None = None

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
    """Deploy up to ``up_to`` garrison troops to the Conflict (player choice)."""

    up_to: int

    def __post_init__(self) -> None:
        if self.up_to < 1:
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
    five Row cards and the Reserve stacks [Main p. 13], plus the owner's own
    Manipulate set-aside card at its printed cost [FAQ p. 3]. The card lands
    in the owner's discard pile [Main pp. 6, 13] unless ``to_hand_if`` holds
    when the acquisition resolves, in which case the card text puts it in
    hand.
    """

    max_cost: int
    to_hand_if: Condition | None = None

    def __post_init__(self) -> None:
        if self.max_cost < 1:
            raise ValueError("acquisition cost cap must be positive")


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
    Reveal turn the troops the line recruited may be deployed, any of them;
    in an Agent turn it adds nothing, as troops recruited then deploy by the
    Combat space rule [DI p. 10] [FAQ p. 4]."""


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
    [Bloodlines pp. 7, 12]."""

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
    put it back, discard it, or pay one Solari to draw it (player choice)."""


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
    turn" — the option is playable only from the turn frame."""


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
class EachOpponentDiscardsCard:
    """Each opponent discards a card [Covert Operation card]: every opponent
    holding a card picks one, clockwise from the next seat."""


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
    opponent and, where both kinds are there, the kind (OQ-034)."""


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


type Reward = (
    GainResources
    | GainVictoryPoints
    | RecruitTroops
    | DrawPersonalCards
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
    | EachOpponentDiscardsCard
    | EachOpponentLosesTroop
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
    | RecruitUndeployableTroops
    | TroopToMemory
    | DrawTwistedIntrigueCards
    | TakeSetupSpice
    | RecallOtherAgent
    | RecruitToConflict
    | AcquireReserveCardToHand
    | GainLowestInfluence
    | GainSpiceWithHelixBonus
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
    face up and its sections resolve each time the trigger fires.
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
            # A Conflict-end loss trigger is played during Combat (Harvest
            # Cells); every other trigger card is a Plot card.
            expected = (
                IntrigueTiming.COMBAT
                if isinstance(self.trigger, OnTroopsLostAtConflictEnd)
                else IntrigueTiming.PLOT
            )
            if self.timing is not expected:
                raise ValueError("triggered Intrigue options must use Plot timing")
            for section in self.sections:
                if section.costs or section.condition is not None:
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
