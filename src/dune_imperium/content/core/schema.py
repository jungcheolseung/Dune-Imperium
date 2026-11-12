"""Shared immutable schemas for rules-backed content records."""

from dataclasses import dataclass
from enum import StrEnum


class SourceDocument(StrEnum):
    """Official documents pinned by the rules source manifest."""

    MAIN_RULEBOOK = "main_rulebook"
    BOARD_SPACE_GUIDE = "board_space_guide"
    FAQ = "faq"
    # The Bloodlines expansion rulebook (``official-rule-sources.json`` key
    # ``bloodlines``); cited as ``[Bloodlines p. N]`` with PDF page numbers.
    BLOODLINES_RULEBOOK = "bloodlines_rulebook"
    # The Immortality expansion rulebook (``official-rule-sources.json`` key
    # ``immortality``); cited as ``[Immortality p. N]`` with PDF page numbers.
    IMMORTALITY_RULEBOOK = "immortality_rulebook"
    # The Rise of Ix expansion rulebook (``official-rule-sources.json`` key
    # ``rise-of-ix``); only its Epic Game Mode is used, cited as
    # ``[Rise of Ix p. N]`` with PDF page numbers.
    RISE_OF_IX_RULEBOOK = "rise_of_ix_rulebook"
    # The original Dune: Imperium rulebook (``official-rule-sources.json``
    # key ``imperium``); cited as ``[DI p. N]`` with PDF page numbers. Its
    # Player Aid prints the same text as pp. 16-18.
    IMPERIUM_RULEBOOK = "imperium_rulebook"
    # A card that no official document describes (the Uprising promo cards):
    # the printed card face itself is the source, cited as page 1.
    CARD_FACE = "card_face"
    # The Arrakeen Scouts mode of the Dire Wolf Game Room companion app, which
    # has no rulebook (``docs/rules/sources.md``); cited as page 1 like
    # ``CARD_FACE``, with the app asset in ``content.arrakeen_scouts``.
    ARRAKEEN_SCOUTS_APP = "arrakeen_scouts_app"


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A page-level reference to an official source document."""

    document: SourceDocument
    pages: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.pages or any(page < 1 for page in self.pages):
            raise ValueError("source pages must contain positive page numbers")
        if len(self.pages) != len(set(self.pages)):
            raise ValueError("source pages must be unique")


@dataclass(frozen=True, slots=True)
class CardDefinition:
    """Identity and provenance shared by all future card schemas."""

    card_id: str
    name: str
    sources: tuple[SourceRef, ...]
    catalog_url: str | None = None

    def __post_init__(self) -> None:
        if not self.card_id or not self.name:
            raise ValueError("cards require stable IDs and names")
        if not self.sources:
            raise ValueError("cards require official source references")
        if self.catalog_url is not None and not self.catalog_url.startswith("https://"):
            raise ValueError("card catalog URLs must use HTTPS")


class GameOption(StrEnum):
    """A ``RulesetConfig`` option a card, Leader, Conflict, Contract or Tech
    tile needs on to join a game (each value names the config field).

    One ``requires`` set per piece replaces its per-option flags (stage 4 of
    docs/content-core-refactor-plan.md, user decision 2026-11-03): a piece
    joins when every option it requires is on.
    """

    CHOAM_MODULE = "choam_module"
    PROMO_CARDS = "promo_cards"
    BLOODLINES = "bloodlines"
    TECH_MODULE = "tech_module"
    IMMORTALITY = "immortality"
    EPIC_GAME = "epic_game"


def check_requires(requires: frozenset[GameOption], what: str) -> None:
    """A ``requires`` set holds options only, and the Tech Module's needs
    Bloodlines' [Bloodlines p. 6]."""

    if not all(isinstance(option, GameOption) for option in requires):
        raise TypeError(f"{what} requirements must be GameOption members")
    if GameOption.TECH_MODULE in requires and GameOption.BLOODLINES not in requires:
        raise ValueError(f"Tech Module {what} belong to the Bloodlines set")


@dataclass(frozen=True, slots=True)
class DeckCardEntry:
    """One card definition and its physical quantity in a shared deck."""

    card: CardDefinition
    copies: int = 1
    # The options the card needs on to be dealt: the CHOAM Module, the promo
    # cards (outside the retail deck), Bloodlines [Bloodlines p. 3] and its
    # Tech Module as well [Bloodlines p. 6], Immortality [Immortality pp. 3-5].
    requires: frozenset[GameOption] = frozenset()
    acquisition_cost: int | None = None
    has_acquisition_bonus: bool = False

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("deck-card copies must be positive")
        check_requires(self.requires, "cards")
        if {GameOption.IMMORTALITY, GameOption.BLOODLINES} <= self.requires:
            raise ValueError("a card belongs to one expansion set")
        if self.acquisition_cost is not None and self.acquisition_cost < 0:
            raise ValueError("acquisition cost must not be negative")
