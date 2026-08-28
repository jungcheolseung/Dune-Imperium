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


type Condition = (
    InfluenceAtLeast | HasHighCouncil | SpiesPlacedAtLeast | CompletedContractsAtLeast
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


type Cost = PayResources | LoseInfluence | DiscardFromHand


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


type Reward = (
    GainResources
    | GainVictoryPoints
    | RecruitTroops
    | DrawPersonalCards
    | DrawIntrigueCards
    | GainCombatStrength
    | GainInfluence
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
    """One way to play an Intrigue card (the halves of an ``—OR—`` card)."""

    timing: IntrigueTiming
    sections: tuple[EffectSection, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.timing, IntrigueTiming):
            raise TypeError("Intrigue option timing must use IntrigueTiming")
        if not self.sections:
            raise ValueError("an Intrigue option needs at least one section")
