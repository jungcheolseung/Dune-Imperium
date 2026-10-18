"""Entity vocabularies and their content features for the ``entity`` network.

The MLP reads a card as one column of counts, or as ``index + 1`` in a slot,
so nothing it learns about one card carries to another, and it reads a Row
card's identity as a magnitude (docs/entity-network-plan.md section 1).
The ``entity`` network instead embeds every card, space, Conflict, contract,
Leader, Tech tile, Skill and research space from **features read off the
content data** -- costs, factions, Agent icons, effect kinds, reward
amounts -- plus a learned vector of its own (section 3.2).

Features are read by reflection (``featurize``): numbers as they are,
booleans as 0/1, an enum member as a one-hot column named after it, a tuple
as the sum of its items' features (and its length), and a dataclass field by
field, with a column marking its class (so ``GainResources`` and
``GainCombatStrength`` rewards are told apart). Names, ids and sources carry
no feature. Each vocabulary keeps the columns some member uses, scaled by
the column's largest magnitude so every feature lies in ``[-1, 1]``.

Where cleanup 2e dropped a compiled copy of a record (a Skill's effect
fields, ...), the record itself is read instead (``_records``): the same
reflection over the ``Ability``, its columns prefixed by its timing
(docs/composed-effects-plan.md 4.4; A8 extends this to every vocabulary).

``FEATURE_DIGEST`` covers every vocabulary's ids, columns and values; an
``entity`` checkpoint stores it and is refused under another table, like the
slot table (``training.slots``). Change the reflection only with
``FEATURE_VERSION``.

``resolve`` maps an action argument or a slot key's id onto a vocabulary
member (a card instance id, a card id, a space, ...), or ``None`` when the
value names no entity (a count, a choice label). Some ids name members of
two vocabularies (a space and a contract tile share ``arrakeen``), so the
argument's or key's name says which to try first (``ARGUMENT_HINTS``,
``SLOT_HINTS``).
"""

import dataclasses
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Any, Final

import numpy as np

from dune_imperium.adapters.observation_encoding import (
    BATTLE_CARD_IDS,
    CONFLICT_IDS,
    CONTRACT_IDS,
    FACTION_IDS,
    INTRIGUE_IDS,
    LEADER_IDS,
    PERSONAL_CARD_IDS,
    POST_IDS,
    RESEARCH_SPACE_IDS,
    SKILL_IDS,
    SPACE_IDS,
)
from dune_imperium.content.bloodlines.sardaukar import SKILLS_BY_ID
from dune_imperium.content.bloodlines.tech import TECH_IDS, TECH_TILES_BY_ID
from dune_imperium.content.bloodlines.tech_abilities import TECH_ACQUIRE_ABILITIES
from dune_imperium.content.immortality.board import RESEARCH_SPACES_BY_ID
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.uprising.abilities import Ability
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, OBSERVATION_POSTS
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.contracts import (
    CONTRACTS_BY_ID,
    contract_for_instance,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_ID,
    INTRIGUE_CARDS_BY_INSTANCE,
)
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    STARTING_CARDS_BY_ID,
)

FEATURE_VERSION: Final = 2
# Fields that name or cite an entity rather than describe what it does.
_SKIPPED_FIELDS: Final = frozenset(
    {"card", "name", "title", "sources", "source", "catalog_url", "required_leader_id"}
)


def featurize(value: object, prefix: str = "") -> dict[str, float]:
    """A value's features by reflection (module docstring)."""

    features: dict[str, float] = {}

    def add(other: Mapping[str, float]) -> None:
        for key, amount in other.items():
            features[key] = features.get(key, 0.0) + amount

    if isinstance(value, Enum):
        # Before ``str``: most of the content's enums are ``StrEnum``.
        features[f"{prefix}={value.value}"] = 1.0
        return features
    if value is None or isinstance(value, str):
        return features
    if isinstance(value, bool):
        features[prefix] = float(value)
    elif isinstance(value, int | float):
        features[prefix] = float(value)
    elif isinstance(value, tuple | list | frozenset):
        features[f"{prefix}#"] = float(len(value))
        for item in value:
            add(featurize(item, prefix))
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        features[f"{prefix}:{type(value).__name__}"] = 1.0
        for field in dataclasses.fields(value):
            if field.name in _SKIPPED_FIELDS:
                continue
            name = f"{prefix}.{field.name}" if prefix else field.name
            add(featurize(getattr(value, field.name), name))
    return features


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """One kind of entity: its ids in the observation's order and features."""

    name: str
    ids: tuple[str, ...]
    columns: tuple[str, ...]
    # ``[len(ids), len(columns)]``, every value in [-1, 1].
    features: np.ndarray

    @property
    def size(self) -> int:
        return len(self.ids)


def _table(name: str, ids: tuple[str, ...], rows: list[dict[str, float]]) -> Vocabulary:
    columns = sorted({key for row in rows for key, amount in row.items() if amount})
    matrix = np.zeros((len(ids), len(columns)), dtype=np.float32)
    position = {column: index for index, column in enumerate(columns)}
    for index, row in enumerate(rows):
        for key, amount in row.items():
            if key in position:
                matrix[index, position[key]] = amount
    scale = np.abs(matrix).max(axis=0)
    keep = scale > 0
    matrix = matrix[:, keep] / scale[keep]
    kept = tuple(column for column, used in zip(columns, keep, strict=True) if used)
    return Vocabulary(name=name, ids=ids, columns=kept, features=matrix)


def _personal_entry(card_id: str) -> object:
    if card_id == CONTROL_THE_SPICE.card.card_id:
        return CONTROL_THE_SPICE
    for table in (STARTING_CARDS_BY_ID, IMPERIUM_CARDS_BY_ID, TLEILAXU_CARDS_BY_ID):
        if card_id in table:
            return table[card_id]
    return next(stack for stack in RESERVE_STACKS if stack.card.card_id == card_id)


def _kind(card_id: str) -> dict[str, float]:
    """Which deck a personal card comes from (a feature of its own)."""

    if card_id == CONTROL_THE_SPICE.card.card_id or card_id in STARTING_CARDS_BY_ID:
        return {"deck=starting": 1.0}
    if card_id in TLEILAXU_CARDS_BY_ID:
        return {"deck=tleilaxu": 1.0}
    if card_id in IMPERIUM_CARDS_BY_ID:
        return {"deck=imperium": 1.0}
    return {"deck=reserve": 1.0}


def _with(base: dict[str, float], extra: Mapping[str, float]) -> dict[str, float]:
    return {**base, **extra}


def _records(*abilities: Ability) -> dict[str, float]:
    """Printed ability records' features, each prefixed by its timing; a
    hook (a flow kept as code, a ``str`` the reflection skips) is a column
    of its own."""

    features: dict[str, float] = {}
    for ability in abilities:
        prefix = ability.timing.value
        record = featurize(ability, prefix)
        if ability.hook is not None:
            record[f"{prefix}.hook={ability.hook}"] = 1.0
        for key, amount in record.items():
            features[key] = features.get(key, 0.0) + amount
    return features


@cache
def vocabularies() -> dict[str, Vocabulary]:
    """Every vocabulary the ``entity`` network embeds, by name."""

    battle_rows = []
    for card_id in BATTLE_CARD_IDS:
        entry: object = CONFLICTS_BY_ID.get(card_id) or OBJECTIVES_BY_ID.get(card_id)
        battle_rows.append(featurize(entry))
    tables = (
        _table(
            "personal",
            PERSONAL_CARD_IDS,
            [
                _with(featurize(_personal_entry(card_id)), _kind(card_id))
                for card_id in PERSONAL_CARD_IDS
            ],
        ),
        _table(
            "intrigue",
            INTRIGUE_IDS,
            [featurize(INTRIGUE_CARDS_BY_ID[card_id]) for card_id in INTRIGUE_IDS],
        ),
        _table(
            "contract",
            CONTRACT_IDS,
            [featurize(CONTRACTS_BY_ID[card_id]) for card_id in CONTRACT_IDS],
        ),
        _table(
            "conflict",
            CONFLICT_IDS,
            [featurize(CONFLICTS_BY_ID[card_id]) for card_id in CONFLICT_IDS],
        ),
        _table("battle", BATTLE_CARD_IDS, battle_rows),
        _table(
            "space",
            SPACE_IDS,
            [featurize(BOARD_SPACES_BY_ID[space_id]) for space_id in SPACE_IDS],
        ),
        _table(
            "post",
            POST_IDS,
            [
                {f"space={space_id}": 1.0 for space_id in post.connected_space_ids}
                for post in OBSERVATION_POSTS
            ],
        ),
        _table(
            "leader",
            LEADER_IDS,
            [featurize(LEADERS_BY_ID[leader_id]) for leader_id in LEADER_IDS],
        ),
        _table(
            "tech",
            TECH_IDS,
            [
                _with(
                    featurize(TECH_TILES_BY_ID[tech_id]),
                    _records(
                        *(
                            ()
                            if (acquire := TECH_ACQUIRE_ABILITIES.get(tech_id)) is None
                            else (acquire,)
                        )
                    ),
                )
                for tech_id in TECH_IDS
            ],
        ),
        _table(
            "skill",
            SKILL_IDS,
            [
                _with(
                    featurize(SKILLS_BY_ID[skill_id]),
                    _records(SKILLS_BY_ID[skill_id].ability),
                )
                for skill_id in SKILL_IDS
            ],
        ),
        _table(
            "research",
            RESEARCH_SPACE_IDS,
            [
                featurize(RESEARCH_SPACES_BY_ID[space_id])
                for space_id in RESEARCH_SPACE_IDS
            ],
        ),
        _table(
            "faction",
            FACTION_IDS,
            [{f"faction={faction}": 1.0} for faction in FACTION_IDS],
        ),
    )
    return {table.name: table for table in tables}


@cache
def _indexes() -> dict[str, dict[str, int]]:
    return {
        name: {identity: index for index, identity in enumerate(table.ids)}
        for name, table in vocabularies().items()
    }


_ORDER: Final = (
    "personal",
    "intrigue",
    "contract",
    "conflict",
    "battle",
    "space",
    "post",
    "leader",
    "tech",
    "skill",
    "research",
    "faction",
)
# The vocabularies an action argument's values belong to, tried first.
ARGUMENT_HINTS: Final[Mapping[str, tuple[str, ...]]] = {
    "space_id": ("space",),
    "post_id": ("post",),
    "infiltrate_post_id": ("post",),
    "first_post_id": ("post",),
    "second_post_id": ("post",),
    "tech_id": ("tech",),
    "leader_id": ("leader",),
    "skill_id": ("skill",),
    "faction": ("faction",),
    "gained_faction": ("faction",),
    "lost_faction": ("faction",),
    "matching_card_id": ("battle", "conflict"),
    "wild_card_id": ("battle", "conflict"),
    "intrigue_card_id": ("intrigue",),
    "target": ("contract",),
}
# The vocabulary of a slot key's id, by the key's prefix (``training.slots``).
SLOT_HINTS: Final[Mapping[str, tuple[str, ...]]] = {
    "conflict": ("conflict",),
    "imperium_row": ("personal",),
    "tleilaxu_row": ("personal",),
    "tech_face_up": ("tech",),
    "secret_project": ("tech",),
    "occupancy": ("space",),
    **{f"navigation{slot}": ("intrigue",) for slot in range(4)},
    **{
        f"seat{seat}_{field}": hint
        for seat in range(4)
        for field, hint in (
            ("leader", ("leader",)),
            ("research", ("research",)),
            ("agent_locations", ("space",)),
            ("set_aside", ("personal",)),
        )
    },
}


# Arguments that name a choice, never an entity, even where a value equals
# some id (the Subcommittee ``leverage`` is also an Intrigue card's id).
LABEL_ARGUMENTS: Final = frozenset(
    {"choice", "effect", "reward", "subcommittee_id", "zone", "zones"}
)
# Where an argument's vocabulary depends on the action: a battle card's id
# is often a Conflict card's id too.
ACTION_ARGUMENT_HINTS: Final[Mapping[tuple[str, str], tuple[str, ...]]] = {
    ("flip_battle_card", "card_id"): ("battle",),
}


def _digest() -> str:
    digest = hashlib.sha256(f"entity-features v{FEATURE_VERSION}".encode())
    for name, table in sorted(vocabularies().items()):
        digest.update(repr((name, table.ids, table.columns)).encode())
        digest.update(np.ascontiguousarray(table.features).tobytes())
    # How ids are read decides which entity an action or a slot points at.
    for hints in (ARGUMENT_HINTS, SLOT_HINTS, ACTION_ARGUMENT_HINTS):
        digest.update(repr(sorted(hints.items())).encode())
    digest.update(repr(sorted(LABEL_ARGUMENTS)).encode())
    return digest.hexdigest()


FEATURE_DIGEST: Final = _digest()


def resolve_argument(action_id: str, key: str, value: str) -> tuple[str, int] | None:
    """The entity an action argument names, or ``None`` for a label."""

    if key in LABEL_ARGUMENTS:
        return None
    prefer = ACTION_ARGUMENT_HINTS.get((action_id, key), ARGUMENT_HINTS.get(key, ()))
    return resolve(value, prefer)


@cache
def resolve(value: str, prefer: tuple[str, ...] = ()) -> tuple[str, int] | None:
    """The vocabulary member a string names, or ``None`` (module docstring).

    Card instance ids resolve to their card. Plain ids are tried in
    ``prefer``'s vocabularies first, then in a fixed order.
    """

    index = _indexes()
    if not value:
        return None
    for name in prefer:
        if value in index[name]:
            return name, index[name][value]
    if value in INTRIGUE_CARDS_BY_INSTANCE:
        return "intrigue", index["intrigue"][
            INTRIGUE_CARDS_BY_INSTANCE[value].card.card_id
        ]
    if value.startswith("contract:"):
        try:
            return "contract", index["contract"][
                contract_for_instance(value).card.card_id
            ]
        except KeyError, ValueError:
            pass
    if value.startswith("starter:"):
        # The action codec writes a starting card relative to its owner
        # (``starter:<card>:<copy>``, ``action_codec._normalize_arguments``).
        starter = value.split(":")[1]
        if starter in index["personal"]:
            return "personal", index["personal"][starter]
    if ":" in value:
        card_id: str | None
        try:
            card_id = personal_card_for_instance(value).card.card_id
        except KeyError, ValueError, NotImplementedError, StopIteration:
            card_id = None
        if card_id is not None and card_id in index["personal"]:
            return "personal", index["personal"][card_id]
    for name in _ORDER:
        if value in index[name]:
            return name, index[name][value]
    return None


def describe() -> dict[str, Any]:
    """Sizes of every vocabulary (rows, feature columns), for reports."""

    return {
        name: {"entities": table.size, "features": len(table.columns)}
        for name, table in vocabularies().items()
    }
