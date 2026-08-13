"""Shared immutable schemas for rules-backed content records."""

from dataclasses import dataclass
from enum import StrEnum


class SourceDocument(StrEnum):
    """Official documents pinned by the rules source manifest."""

    MAIN_RULEBOOK = "main_rulebook"
    BOARD_SPACE_GUIDE = "board_space_guide"
    FAQ = "faq"


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


@dataclass(frozen=True, slots=True)
class DeckCardEntry:
    """One card definition and its physical quantity in a shared deck."""

    card: CardDefinition
    copies: int = 1
    choam_only: bool = False
    acquisition_cost: int | None = None

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("deck-card copies must be positive")
        if self.acquisition_cost is not None and self.acquisition_cost < 0:
            raise ValueError("acquisition cost must not be negative")
