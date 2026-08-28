"""Composable typed effects for card text that reads as condition/cost/reward.

The DSL deliberately stays small. Each primitive is an immutable record with
its own validation; the rules interpreter in ``rules/effect_interpreter.py``
decides what each primitive does to game state. Card-specific behaviour that
does not fit these primitives keeps using explicit custom hooks.
"""

from dataclasses import dataclass
from enum import StrEnum

from dune_imperium.content.uprising.board import Faction


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


type Condition = (
    InfluenceAtLeast
    | HasHighCouncil
    | SpiesPlacedAtLeast
    | CompletedContractsAtLeast
    | SandwormsInConflictAtLeast
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


type Cost = PayResources | LoseInfluence | DiscardFromHand | RecallSpy | RetreatTroops


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

    Optional per [Main p. 20]; the player may decline.
    """


@dataclass(frozen=True, slots=True)
class PlaceSpy:
    """Place a Spy on an empty Observation Post, limited to ``factions`` if set.

    Without a Spy in supply the player first recalls one [Main pp. 11, 20].
    """

    factions: tuple[Faction, ...] | None = None

    def __post_init__(self) -> None:
        if self.factions is not None:
            if not self.factions or len(self.factions) != len(set(self.factions)):
                raise ValueError("Spy target Factions must be unique and non-empty")
            if any(not isinstance(faction, Faction) for faction in self.factions):
                raise TypeError("Spy target Factions must use Faction")


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
)


# --- Triggers ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OnRevealAcquisitionThisRound:
    """During the owner's Reveal turn this round, whenever they acquire a card.

    A card played with this trigger stays face up in front of its owner until
    the effect applies [FAQ p. 2], fires once per card acquired during the
    owner's Reveal turn, and is discarded when that Reveal turn ends.
    """


type Trigger = OnRevealAcquisitionThisRound


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

    def __post_init__(self) -> None:
        if not isinstance(self.timing, IntrigueTiming):
            raise TypeError("Intrigue option timing must use IntrigueTiming")
        if not self.sections:
            raise ValueError("an Intrigue option needs at least one section")
        if self.trigger is not None:
            if self.timing is not IntrigueTiming.PLOT:
                raise ValueError("triggered Intrigue options must use Plot timing")
            for section in self.sections:
                if section.costs or section.condition is not None:
                    raise ValueError(
                        "triggered Intrigue sections must be free and unconditional"
                    )
