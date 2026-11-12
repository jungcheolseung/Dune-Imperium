"""What each printed card face shows, for the redrawn faces.

``card_faces.json`` beside this module holds, per catalog card id, the
printed content of the card's boxes (``agent``, ``reveal``, ``static``; an
Intrigue card's ``parts`` with their timings) by language (``en``, and
``ko`` where every box has the Korean edition's wording), in the project's
notation: ``{icon}`` / ``{icon:N}`` with our icon
names (``display.icons``; ``N`` printed inside Persuasion, Solari and spice),
newlines as printed, ``<i>``/``<b>`` as printed. A private tool writes it
from the printed faces' English text and layouts and the Korean edition's
transcription; printed card-face
content may be public (user decisions 2026-11-10, docs/card-data-sources.md,
docs/own-pictures-plan.md).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any, Final

CARD_FACES_PATH: Final = Path(__file__).with_name("card_faces.json")
FACE_BOXES: Final = ("static", "agent", "reveal")
FACE_LANGUAGES: Final = ("en", "ko")
INTRIGUE_TIMINGS: Final = ("plot", "combat", "endgame", "navigation")


@cache
def card_faces() -> Mapping[str, Mapping[str, Mapping[str, str]]]:
    """Return ``{card id: {box: {language: text}}}``."""

    data = json.loads(CARD_FACES_PATH.read_text(encoding="utf-8"))
    cards = data["cards"]
    if not isinstance(cards, dict):
        raise ValueError("card_faces.json: 'cards' is not an object")
    return cards


@cache
def intrigue_faces() -> Mapping[str, Mapping[str, list[Mapping[str, str]]]]:
    """Return ``{Intrigue id: {"parts": [{"timing", "en", "ko"?}, ...]}}``.

    An Intrigue card's printed text split where an "—OR—" frame lies: one
    part per timing of a two-timing card, or per choice of one timing.
    """

    data = json.loads(CARD_FACES_PATH.read_text(encoding="utf-8"))
    intrigue = data.get("intrigue", {})
    if not isinstance(intrigue, dict):
        raise ValueError("card_faces.json: 'intrigue' is not an object")
    return intrigue


@cache
def _sections() -> Mapping[str, object]:
    data = json.loads(CARD_FACES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("card_faces.json is not an object")
    return data


def conflict_faces() -> Mapping[str, Mapping[str, list[Mapping[str, str]]]]:
    """Return ``{Conflict id: {"rewards": [first, second, third]}}``, each
    reward ``{"en", "ko"?}`` as printed beside its place."""

    conflicts = _sections().get("conflicts", {})
    if not isinstance(conflicts, dict):
        raise ValueError("card_faces.json: 'conflicts' is not an object")
    return conflicts


def contract_faces() -> Mapping[str, Mapping[str, object]]:
    """Return ``{contract id: {"tile", "frame", "condition", "reward"}}``:
    the tile's colour, the space its condition frame shows, and the
    condition's and reward's printed content by language."""

    contracts = _sections().get("contracts", {})
    if not isinstance(contracts, dict):
        raise ValueError("card_faces.json: 'contracts' is not an object")
    return contracts


def tech_faces() -> Mapping[str, Mapping[str, Any]]:
    """Return ``{Tech id: {"strip": {...}, "body": {...}, "tone"?}}``: the
    acquire strip's icons top to bottom and the tile's body, by language;
    ``tone`` ``"bloodlines"`` for a tile Bloodlines prints (grey-green)."""

    tech = _sections().get("tech", {})
    if not isinstance(tech, dict):
        raise ValueError("card_faces.json: 'tech' is not an object")
    return tech


def leader_faces() -> Mapping[str, Mapping[str, Any]]:
    """Return ``{leader face id: {...}}``: complexity ``pips``, an optional
    ``mark`` before the name (``choam``, ``tech``) and ``house`` line, the
    ``abilities`` (``title``, ``text``, ``tone``?), the ``signet`` box
    (``kind`` ``navigation`` for Steersman Y'rkoon's Plot Course) and the
    ``track`` its art prints (``feyd``, ``chani``, ``snooper``), texts by
    language."""

    leaders = _sections().get("leaders", {})
    if not isinstance(leaders, dict):
        raise ValueError("card_faces.json: 'leaders' is not an object")
    return leaders


def objective_faces() -> Mapping[str, Mapping[str, Any]]:
    """Return ``{Objective id: {"kind": "objective", "text": {...}, ...}}``:
    each Uprising Objective card's printed line by language, with its player
    count (``players``) or First Player mark (``first_player``)."""

    objectives = _sections().get("objectives", {})
    if not isinstance(objectives, dict):
        raise ValueError("card_faces.json: 'objectives' is not an object")
    return objectives


def skill_faces() -> Mapping[str, Mapping[str, Any]]:
    """Return ``{Skill id: {"kind": "skill", "body": {...}}}``: what each
    Sardaukar Commander Skill tile prints under its name, by language."""

    skills = _sections().get("skills", {})
    if not isinstance(skills, dict):
        raise ValueError("card_faces.json: 'skills' is not an object")
    return skills
