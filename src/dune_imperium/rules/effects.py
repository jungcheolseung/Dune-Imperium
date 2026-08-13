"""Small typed effects shared by cards and board spaces."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GainResourcesEffect:
    """Gain public spendable resources from the bank."""

    solari: int = 0
    spice: int = 0
    water: int = 0

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("resource gains must not be negative")
        if self.solari == self.spice == self.water == 0:
            raise ValueError("a resource-gain effect must gain something")
