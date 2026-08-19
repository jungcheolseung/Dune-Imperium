"""Development-time normalization of the external DIU card dataset.

This module never locates or loads DIU implicitly. Callers must provide an
explicit source path, and the game runtime continues to use only the typed
content manifests under :mod:`dune_imperium.content.uprising`.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import STARTING_DECK
from dune_imperium.content.uprising.types import AgentIcon

DIU_EFFECT_FIELDS = (
    "agent_effects",
    "reveal_effects",
    "fremen_bond_effects",
    "on_acquire_effects",
    "on_discard_effects",
    "on_trash_effects",
)
DIU_NAME_ALIASES = {"branchingpaths": "branchingpath"}
DIU_AGENT_ICONS = {
    "blue": AgentIcon.CITY,
    "green": AgentIcon.LANDSRAAD,
    "yellow": AgentIcon.SPICE_TRADE,
    "emperor": AgentIcon.EMPEROR,
    "spacing_guild": AgentIcon.SPACING_GUILD,
    "bene_gesserit": AgentIcon.BENE_GESSERIT,
    "fremen": AgentIcon.FREMEN,
    "spy": AgentIcon.SPY,
}
DIU_FACTIONS = {
    "emperor": Faction.EMPEROR,
    "spacing_guild": Faction.SPACING_GUILD,
    "bene_gesserit": Faction.BENE_GESSERIT,
    "fremen": Faction.FREMEN,
}


class DiuDataError(ValueError):
    """The supplied DIU data cannot be normalized without guessing."""


class DiuCardGroup(StrEnum):
    """Physical source group represented by one DIU Imperium record."""

    STARTING = "starting"
    RESERVE = "reserve"
    IMPERIUM = "imperium"


@dataclass(frozen=True, slots=True)
class ExpectedImperiumCard:
    """Current authoritative identity used to match one DIU record."""

    card_id: str
    name: str
    group: DiuCardGroup
    copies: int
    choam_only: bool = False


@dataclass(frozen=True, slots=True)
class DiuImperiumCard:
    """Normalized audit metadata for one DIU Imperium record."""

    source_id: int
    source_name: str
    card_id: str
    group: DiuCardGroup
    declared_copies: int | None
    expected_copies: int
    choam_only: bool
    agent_icons: tuple[AgentIcon, ...]
    factions: tuple[Faction, ...]
    effect_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiuCopyMismatch:
    """A non-authoritative DIU quantity that differs from the local manifest."""

    card_id: str
    declared: int
    expected: int


@dataclass(frozen=True, slots=True)
class DiuImperiumAudit:
    """Complete identity and effect-shape audit of one DIU source file."""

    source_path: Path
    cards: tuple[DiuImperiumCard, ...]
    copy_mismatches: tuple[DiuCopyMismatch, ...]
    effect_type_counts: tuple[tuple[str, int], ...]

    def card(self, card_id: str) -> DiuImperiumCard:
        """Return one normalized record by the project's stable card ID."""

        try:
            return next(card for card in self.cards if card.card_id == card_id)
        except StopIteration as error:
            raise KeyError(card_id) from error


def expected_imperium_cards() -> tuple[ExpectedImperiumCard, ...]:
    """Return the 63 identities expected from DIU's combined card source."""

    starting = tuple(
        ExpectedImperiumCard(
            card_id=entry.card.card_id,
            name=entry.card.name,
            group=DiuCardGroup.STARTING,
            copies=entry.copies,
        )
        for entry in STARTING_DECK
    )
    reserve = tuple(
        ExpectedImperiumCard(
            card_id=entry.card.card_id,
            name=entry.card.name,
            group=DiuCardGroup.RESERVE,
            copies=entry.copies,
        )
        for entry in RESERVE_STACKS
    )
    shared = tuple(
        ExpectedImperiumCard(
            card_id=entry.card.card_id,
            name=entry.card.name,
            group=DiuCardGroup.IMPERIUM,
            copies=entry.copies,
            choam_only=entry.choam_only,
        )
        for entry in IMPERIUM_CARDS
    )
    return (*starting, *reserve, *shared)


def audit_diu_imperium(path: Path) -> DiuImperiumAudit:
    """Load DIU's combined Imperium source and match every expected identity."""

    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DiuDataError(f"cannot read DIU Imperium data {path}: {error}") from error
    if not isinstance(raw, list):
        raise DiuDataError("DIU Imperium data must be a top-level array")

    expected = expected_imperium_cards()
    expected_by_name = {_name_key(card.name): card for card in expected}
    if len(expected_by_name) != len(expected):
        raise RuntimeError("local Imperium identities have duplicate normalized names")

    cards: list[DiuImperiumCard] = []
    source_ids: set[int] = set()
    matched_ids: set[str] = set()
    effect_counts: Counter[str] = Counter()
    for index, value in enumerate(raw):
        record = _object(value, f"card[{index}]")
        source_id = _integer(record.get("id"), f"card[{index}].id")
        source_name = _string(record.get("name"), f"card[{index}].name")
        if source_id in source_ids:
            raise DiuDataError(f"duplicate DIU card id: {source_id}")
        source_ids.add(source_id)

        try:
            expected_card = expected_by_name[_name_key(source_name)]
        except KeyError as error:
            raise DiuDataError(f"unmatched DIU card name: {source_name}") from error
        if expected_card.card_id in matched_ids:
            raise DiuDataError(f"duplicate DIU card identity: {source_name}")
        matched_ids.add(expected_card.card_id)

        group = _card_group(record, source_name)
        if group is not expected_card.group:
            raise DiuDataError(
                f"{source_name}: DIU group {group.value} does not match "
                f"local group {expected_card.group.value}"
            )
        effect_types = _effect_types(record, source_name)
        effect_counts.update(effect_types)
        cards.append(
            DiuImperiumCard(
                source_id=source_id,
                source_name=source_name,
                card_id=expected_card.card_id,
                group=group,
                declared_copies=_declared_copies(record, group, source_name),
                expected_copies=expected_card.copies,
                choam_only=expected_card.choam_only,
                agent_icons=_agent_icons(record, source_name),
                factions=_factions(record, source_name),
                effect_types=effect_types,
            )
        )

    missing = tuple(
        card.card_id for card in expected if card.card_id not in matched_ids
    )
    if missing:
        raise DiuDataError("DIU source is missing cards: " + ", ".join(missing))

    ordered_cards = tuple(sorted(cards, key=lambda card: card.source_id))
    mismatches = tuple(
        DiuCopyMismatch(
            card_id=card.card_id,
            declared=card.declared_copies,
            expected=card.expected_copies,
        )
        for card in ordered_cards
        if card.declared_copies is not None
        and card.declared_copies != card.expected_copies
    )
    return DiuImperiumAudit(
        source_path=path,
        cards=ordered_cards,
        copy_mismatches=mismatches,
        effect_type_counts=tuple(sorted(effect_counts.items())),
    )


def _name_key(name: str) -> str:
    key = "".join(character for character in name.casefold() if character.isalnum())
    return DIU_NAME_ALIASES.get(key, key)


def _card_group(record: dict[str, object], name: str) -> DiuCardGroup:
    starting = _optional_boolean(record, "starting_deck", name)
    reserve = _optional_boolean(record, "reserve", name)
    if starting and reserve:
        raise DiuDataError(f"{name}: card cannot be both starting and Reserve")
    if starting:
        return DiuCardGroup.STARTING
    if reserve:
        return DiuCardGroup.RESERVE
    return DiuCardGroup.IMPERIUM


def _declared_copies(
    record: dict[str, object],
    group: DiuCardGroup,
    name: str,
) -> int | None:
    field = "amount" if group is DiuCardGroup.STARTING else "quantity"
    value = record.get(field)
    if value is None and group is DiuCardGroup.IMPERIUM:
        value = record.get("amount")
    if value is None:
        return None
    copies = _integer(value, f"{name}.{field}")
    if copies < 1:
        raise DiuDataError(f"{name}.{field} must be positive")
    return copies


def _agent_icons(
    record: dict[str, object],
    name: str,
) -> tuple[AgentIcon, ...]:
    raw = _aliased_field(record, "agent_icon", "agent_icons", name)
    values = _string_sequence(raw, f"{name}.agent_icon")
    icons: list[AgentIcon] = []
    for value in values:
        key = _enum_key(value)
        if key == "reveal":
            continue
        try:
            icon = DIU_AGENT_ICONS[key]
        except KeyError as error:
            raise DiuDataError(f"{name}: unknown DIU Agent icon {value!r}") from error
        if icon not in icons:
            icons.append(icon)
    return tuple(icons)


def _factions(record: dict[str, object], name: str) -> tuple[Faction, ...]:
    raw = _aliased_field(record, "faction", "factions", name)
    values = _string_sequence(raw, f"{name}.faction")
    factions: list[Faction] = []
    for value in values:
        try:
            faction = DIU_FACTIONS[_enum_key(value)]
        except KeyError as error:
            raise DiuDataError(f"{name}: unknown DIU faction {value!r}") from error
        if faction not in factions:
            factions.append(faction)
    return tuple(factions)


def _effect_types(record: dict[str, object], name: str) -> tuple[str, ...]:
    effect_types: list[str] = []
    for field in DIU_EFFECT_FIELDS:
        raw = record.get(field)
        if raw is None:
            continue
        if not isinstance(raw, list):
            raise DiuDataError(f"{name}.{field} must be an array")
        _collect_effect_types(raw, f"{name}.{field}", effect_types)
    return tuple(effect_types)


def _collect_effect_types(
    value: object,
    location: str,
    effect_types: list[str],
) -> None:
    if isinstance(value, list):
        for index, child in enumerate(value):
            _collect_effect_types(child, f"{location}[{index}]", effect_types)
        return
    if isinstance(value, dict):
        record = _object(value, location)
        effect_type = record.get("type")
        if effect_type is not None:
            effect_types.append(_string(effect_type, f"{location}.type"))
        for key, child in record.items():
            if key != "type":
                _collect_effect_types(child, f"{location}.{key}", effect_types)


def _aliased_field(
    record: dict[str, object],
    singular: str,
    plural: str,
    name: str,
) -> object | None:
    if singular in record and plural in record:
        raise DiuDataError(f"{name}: both {singular} and {plural} are present")
    return record.get(singular, record.get(plural))


def _optional_boolean(record: dict[str, object], field: str, name: str) -> bool:
    value = record.get(field, False)
    if not isinstance(value, bool):
        raise DiuDataError(f"{name}.{field} must be a boolean")
    return value


def _string_sequence(value: object, location: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise DiuDataError(f"{location} must be a string or array of strings")
    return tuple(_string(item, f"{location}[]") for item in value)


def _enum_key(value: str) -> str:
    return value.strip().casefold().replace(" ", "_").replace("-", "_")


def _object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise DiuDataError(f"{location} must be an object with string keys")
    return cast(dict[str, object], value)


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise DiuDataError(f"{location} must be a non-empty string")
    return value


def _integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DiuDataError(f"{location} must be an integer")
    return value
