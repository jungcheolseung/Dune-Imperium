"""Composable typed effects for card text that reads as condition/cost/reward.

The DSL deliberately stays small. Each primitive is an immutable record with
its own validation; the rules interpreter in ``rules/effect_interpreter.py``
decides what each primitive does to game state. Card-specific behaviour that
does not fit these primitives keeps using explicit custom hooks.
"""

from dataclasses import dataclass
from enum import StrEnum

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
    """The player holds any Faction Alliance (Twisted Intrigue, Navigation)."""


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
    | SpiceMustFlowCardsAtLeast
    | OpponentAllianceInfluenceAtLeast
    | WaterAtLeast
    | CommandersInConflictAtLeast
    | TechTilesAtLeast
    | GeneticMarkersAtLeast
    | SolariAtLeast
    | SpiceAtLeast
    | OpponentPlayedCombatIntrigue
    | AllConditions
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


@dataclass(frozen=True, slots=True)
class LoseInfluence:
    """Lose ``count`` Influence, choosing a Faction for each step.

    Each step is a player choice among Factions where the player still has
    Influence; the same Faction may be chosen more than once.
    """

    count: int = 1

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

    During Combat the retreated troops' strength leaves the total at once and
    a player left without units drops out of the priority loop (OQ-003).
    """

    minimum: int = 1
    maximum: int | None = None

    def __post_init__(self) -> None:
        if self.minimum < 1:
            raise ValueError("retreat minimum must be positive")
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

    def __post_init__(self) -> None:
        if self.times < 1:
            raise ValueError("Influence gain times must be positive")
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

    Without a Spy in supply the player first recalls one [Main pp. 11, 20].
    ``shared_post`` inverts the target rule for card text that places the Spy
    on the same post as another player's Spy.
    """

    factions: tuple[Faction, ...] | None = None
    shared_post: bool = False

    def __post_init__(self) -> None:
        if self.factions is not None:
            if not self.factions or len(self.factions) != len(set(self.factions)):
                raise ValueError("Spy target Factions must be unique and non-empty")
            if any(not isinstance(faction, Faction) for faction in self.factions):
                raise TypeError("Spy target Factions must use Faction")
        if not isinstance(self.shared_post, bool):
            raise TypeError("shared_post must be a boolean")
        if self.shared_post and self.factions is not None:
            raise ValueError("a shared-post placement cannot limit Factions")


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
    five Row cards and the Reserve stacks [Main p. 13]. The card lands in the
    owner's discard pile [Main pp. 6, 13] unless ``to_hand_if`` holds when the
    acquisition resolves, in which case the card text puts it in hand.
    """

    max_cost: int
    to_hand_if: Condition | None = None

    def __post_init__(self) -> None:
        if self.max_cost < 1:
            raise ValueError("acquisition cost cap must be positive")


@dataclass(frozen=True, slots=True)
class SetAsideImperiumRowCard:
    """Remove and replace one Imperium Row card, setting it aside for the owner.

    Until the owner's Reveal turn this round ends, only they may acquire the
    set-aside card, for ``discount`` less Persuasion; opponents never can, and
    an unacquired card leaves the game with that Reveal turn [FAQ p. 3].
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
    bank, take one and trash the others. Resolved by its deployment
    trigger (``rules.intrigue_triggers``)."""

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
    (Harvest Cells) [Immortality p. 8]."""


@dataclass(frozen=True, slots=True)
class RevealPersuasionThisRound:
    """Gain ``amount`` Persuasion during the owner's Reveal turn this round
    (Tleilaxu Puppet)."""

    amount: int = 1

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("Persuasion bonus must be positive")


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
class OnUnitsDeployedInTurn:
    """When the owner deploys ``minimum`` or more units to the Conflict in a
    single turn.

    Troops and sandworms are both units [Main p. 12] and a summoned sandworm
    is immediately deployed [Main p. 20], so both count. The card waits face
    up until a qualifying turn [FAQ p. 2].
    """

    minimum: int = 3

    def __post_init__(self) -> None:
        if self.minimum < 1:
            raise ValueError("deployment trigger minimum must be positive")


@dataclass(frozen=True, slots=True)
class OnTroopsLostAtConflictEnd:
    """When the owner loses ``minimum`` or more troops at the end of a
    Conflict (Harvest Cells).

    Troops (and Sardaukar Commanders, being troops) that return to the
    supply at Combat cleanup are "lost" [FAQ p. 1, Chani]; the card waits
    face up through the Combat and expires at cleanup if the loss is short.
    """

    minimum: int = 3

    def __post_init__(self) -> None:
        if self.minimum < 1:
            raise ValueError("loss trigger minimum must be positive")


type Trigger = (
    OnRevealAcquisitionThisRound | OnUnitsDeployedInTurn | OnTroopsLostAtConflictEnd
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
        if not self.rewards:
            raise ValueError("an effect section must produce at least one reward")
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
    # "At the start of your turn": playable only from the turn frame, before
    # the Agent or Reveal choice (Withdrawn).
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
