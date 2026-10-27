"""Ruleset configuration for supported games."""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final


class BaseGame(StrEnum):
    """The base game a ruleset is built on (docs/base-game-and-ix-plan.md 4.2).

    ``UPRISING`` is Dune: Imperium - Uprising; ``IMPERIUM`` the original Dune:
    Imperium (2020), whose boards, cards and Leaders arrive in stages P2-P4
    of that plan.
    """

    UPRISING = "uprising"
    IMPERIUM = "imperium"


# The expansion options each base game may combine with (plan 4.2 item 1,
# 9 items 8-9). CHOAM, Bloodlines and Arrakeen Scouts are Uprising's; Rise
# of Ix is the original game's for now (Uprising + Ix is stage P7, the
# original game's Scouts P8, Immortality with the original game P7), and
# its Epic Game Mode needs Rise of Ix there [Rise of Ix p. 10].
_OPTIONS_BY_BASE_GAME: Final = {
    BaseGame.UPRISING: frozenset(
        {
            "choam_module",
            "promo_cards",
            "bloodlines",
            "tech_module",
            "immortality",
            "go_to_11",
            "epic_game",
            "arrakeen_scouts",
        }
    ),
    BaseGame.IMPERIUM: frozenset({"promo_cards", "rise_of_ix", "epic_game"}),
}
_EXPANSION_OPTIONS: Final = frozenset().union(*_OPTIONS_BY_BASE_GAME.values())
_IDENTIFIER_PREFIXES: Final = {
    BaseGame.UPRISING: "uprising-4p-",
    BaseGame.IMPERIUM: "imperium-4p-",
}
# Option tokens of an identifier, in the order they are written.
_IDENTIFIER_TOKENS: Final = (
    ("promo", "promo_cards"),
    ("ix", "rise_of_ix"),
    ("bloodlines", "bloodlines"),
    ("tech", "tech_module"),
    ("immortality", "immortality"),
    ("go11", "go_to_11"),
    ("epic", "epic_game"),
    ("scouts", "arrakeen_scouts"),
)


@dataclass(frozen=True, slots=True)
class RulesetConfig:
    """Immutable selection of rules used to create a game.

    The first implementation target is specifically the four-player Uprising
    ruleset.  Keeping this restriction explicit prevents unsupported player
    counts from silently entering engine state. ``base_game`` selects the
    original Dune: Imperium instead (docs/base-game-and-ix-plan.md); each
    base game allows its own expansion options.
    """

    players: int = 4
    base_game: BaseGame = BaseGame.UPRISING
    choam_module: bool = False
    # OQ-007 project convention (not an official rule): deal six random
    # Leaders face up after First Player is known, then pick in reverse
    # round-1 turn order. Off by default so fixed-Leader test and sweep
    # setups stay reproducible.
    leader_draft: bool = False
    # Shuffle the promo cards into their decks: the three Uprising promos
    # (Arrakis Revolt, The Beast's Spoils, Pivotal Gambit) into the Imperium
    # deck, the Bloodlines promo Ruthless Leadership with ``bloodlines``, and
    # the Immortality promo Piter, Genius Advisor into the Tleilaxu deck with
    # ``immortality``. They are not part of the retail decks, so they stay
    # out unless a table opts in.
    promo_cards: bool = False
    # The Bloodlines expansion (``docs/rules/bloodlines.md``): Sardaukar
    # Commanders and their Skills, the new Imperium/Intrigue/Conflict cards
    # and Leaders. Off by default so the retail Uprising game stays the
    # baseline.
    bloodlines: bool = False
    # The Tech Module mini-expansion packaged with Bloodlines (Ixian Embassy
    # board, Tech tiles, its two Imperium and two Intrigue cards, Kota Odax
    # of Ix) [Bloodlines pp. 6-7]. Requires ``bloodlines``.
    tech_module: bool = False
    # The Immortality expansion (``docs/rules/immortality.md``): the Bene
    # Tleilax board (research and Tleilaxu tracks, specimens), the Tleilaxu
    # Row, Graft, the revised Research Station, Experimentation starting
    # cards, Family Atomics, and its Imperium/Intrigue cards. Off by default;
    # independent of ``bloodlines`` (the two may be combined) [Main p. 18].
    immortality: bool = False
    # The Immortality rulebook's "Go to 11" variant [Immortality p. 12]: a
    # four-player table starts every Score marker at 0 instead of 1
    # [Main p. 5] and still plays to 10 [Main p. 15]. Offered only with
    # ``immortality`` (user decision, OQ-091). Off by default.
    go_to_11: bool = False
    # Rise of Ix's Epic Game Mode [Rise of Ix p. 10]
    # (``docs/rules/epic-game-mode.md``): play to 12, a Conflict deck of
    # five II over five III (Economic Supremacy the fifth III [Main p. 18]),
    # Control the Spice for one Dune, the Desert Planet (into the discard
    # pile with ``immortality`` [Immortality p. 12]), one Intrigue card and
    # five garrison troops. Needs no other option: the rest of Rise of Ix is
    # not implemented (user decision, OQ-092). Off by default.
    epic_game: bool = False
    # The Arrakeen Scouts module of the Dire Wolf Game Room companion app
    # (docs/rules/arrakeen-scouts.md): subcommittees, missions, events,
    # auctions and sales revealed round by round. Off by default; combines
    # with every other option.
    arrakeen_scouts: bool = False
    # OQ-132 project convention (not an official rule; user decision
    # 2026-10-25): seat 0 ("Player 1") takes the Objective with the First
    # Player marker and so starts round 1; the other three Objectives are
    # dealt at random to seats 1-3. The rulebook deals all four at random
    # and whoever gets the marker starts [Main p. 5]; with the seats
    # themselves assigned at random the odds are the same. Off by default
    # (the engine, CLIs and training keep the printed deal).
    first_player_seat_zero: bool = False
    # The Rise of Ix expansion (docs/rules/rise-of-ix.md) on the original
    # base game: its board overlay, Tech tiles, Dreadnoughts, Shipping
    # track and cards (stage P4). Off by default.
    rise_of_ix: bool = False

    # Options added after saves and records already held state hashes: the
    # canonical state hash leaves each one out while it holds its default,
    # so every game without it keeps the hash it was saved with
    # (core.state.canonical_state_hash).
    HASH_OMITTED_AT_DEFAULT: ClassVar[frozenset[str]] = frozenset(
        {"first_player_seat_zero", "base_game", "rise_of_ix"}
    )

    def __post_init__(self) -> None:
        if self.players != 4:
            message = "only four-player games are currently supported"
            raise ValueError(message)
        base_game = BaseGame(self.base_game)
        if base_game is not self.base_game:
            # A plain string names its base game too (a save or a CLI).
            object.__setattr__(self, "base_game", base_game)
        allowed = _OPTIONS_BY_BASE_GAME[base_game]
        for option in sorted(_EXPANSION_OPTIONS - allowed):
            if getattr(self, option):
                message = f"{option} is not offered with the {base_game} base game"
                raise ValueError(message)
        if base_game is BaseGame.IMPERIUM and self.epic_game and not self.rise_of_ix:
            message = "Epic Game Mode on the original game requires Rise of Ix"
            raise ValueError(message)
        if self.tech_module and not self.bloodlines:
            message = "the Tech Module requires the Bloodlines expansion"
            raise ValueError(message)
        if self.go_to_11 and not self.immortality:
            message = "the Go to 11 variant requires the Immortality expansion"
            raise ValueError(message)

    @property
    def starting_victory_points(self) -> int:
        """Return the Score track space every player starts on.

        Four-player setup puts the Score marker on 1 [Main p. 5]; the Go to
        11 variant starts it on 0 [Immortality p. 12].
        """

        return 0 if self.go_to_11 else 1

    @property
    def endgame_victory_points(self) -> int:
        """Return the score that opens the Endgame at a round's end.

        Ten [Main p. 15]; twelve in Epic Game Mode [Rise of Ix p. 10]. With
        ``go_to_11`` as well, the game runs from 0 to 12 (OQ-093).
        """

        return 12 if self.epic_game else 10

    @property
    def starting_garrison_troops(self) -> int:
        """Return the troops each player starts with in their garrison.

        Three [Main p. 5]; five in Epic Game Mode [Rise of Ix p. 10]. The rest
        of the twelve start in the supply.
        """

        return 5 if self.epic_game else 3

    @property
    def identifier(self) -> str:
        """Return a stable, human-readable ruleset identifier."""

        module = "choam" if self.choam_module else "base"
        options = "".join(
            f"+{token}" for token, option in _IDENTIFIER_TOKENS if getattr(self, option)
        )
        # Like the Leader draft, ``first_player_seat_zero`` changes only who
        # gets which Objective, not the cards or the action catalog, so it
        # is left out: a trained network answers for either deal. An Uprising
        # identifier is unchanged by the base-game axis (``uprising-4p-``).
        return f"{_IDENTIFIER_PREFIXES[self.base_game]}{module}{options}"

    @classmethod
    def from_identifier(cls, identifier: str) -> RulesetConfig:
        """Rebuild the configuration behind an ``identifier`` string.

        Checkpoints and reports carry only the identifier; the inverse lets
        them rebuild their ruleset (and so their action catalog) later.
        ``leader_draft`` and ``first_player_seat_zero`` are not part of the
        identifier and stay off.
        """

        games = [
            (base_game, prefix)
            for base_game, prefix in _IDENTIFIER_PREFIXES.items()
            if identifier.startswith(prefix)
        ]
        if not games:
            raise ValueError(f"unknown ruleset identifier: {identifier!r}")
        ((base_game, prefix),) = games
        module, *options = identifier.removeprefix(prefix).split("+")
        if module not in ("base", "choam"):
            raise ValueError(f"unknown ruleset identifier: {identifier!r}")
        order = tuple(token for token, _ in _IDENTIFIER_TOKENS)
        if len(set(options)) != len(options) or any(o not in order for o in options):
            raise ValueError(f"unknown ruleset identifier: {identifier!r}")
        if options != [o for o in order if o in options]:
            raise ValueError(f"unknown ruleset identifier: {identifier!r}")
        return cls(
            base_game=base_game,
            choam_module=module == "choam",
            **{option: token in options for token, option in _IDENTIFIER_TOKENS},
        )
