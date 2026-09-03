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
    # OQ-007 project convention (not an official rule): deal six random
    # Leaders face up after First Player is known, then pick in reverse
    # round-1 turn order. Off by default so fixed-Leader test and sweep
    # setups stay reproducible.
    leader_draft: bool = False
    # Shuffle the three Uprising promo Imperium cards (Arrakis Revolt, The
    # Beast's Spoils, Pivotal Gambit) into the Imperium deck. They are printed
    # in the Uprising layout but are not part of the retail deck, so they stay
    # out unless a table opts in.
    promo_cards: bool = False

    def __post_init__(self) -> None:
        if self.players != 4:
            message = "only four-player Uprising is currently supported"
            raise ValueError(message)

    @property
    def identifier(self) -> str:
        """Return a stable, human-readable ruleset identifier."""

        module = "choam" if self.choam_module else "base"
        promo = "+promo" if self.promo_cards else ""
        return f"uprising-4p-{module}{promo}"
