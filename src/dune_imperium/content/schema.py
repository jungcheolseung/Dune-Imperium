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
