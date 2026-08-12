"""Ruleset configuration for supported games."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RulesetConfig:
    """Immutable selection of rules used to create a game.

    The first implementation target is specifically the four-player Uprising
    ruleset.  Keeping this restriction explicit prevents unsupported player
    counts from silently entering engine state.
    """

    players: int = 4
    choam_module: bool = False

    def __post_init__(self) -> None:
        if self.players != 4:
            message = "only four-player Uprising is currently supported"
            raise ValueError(message)

    @property
    def identifier(self) -> str:
        """Return a stable, human-readable ruleset identifier."""

        module = "choam" if self.choam_module else "base"
        return f"uprising-4p-{module}"
