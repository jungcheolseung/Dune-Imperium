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

What an entity *does* is read from its printed ability records
(docs/composed-effects-plan.md 4.4, stage A8): the same reflection over each
``Ability`` -- timing, mark, structure, requirement, and per line its
condition, costs and rewards with their numbers -- under a prefix naming the
box it fills (``agent``, ``reveal``, ``first`` for a Conflict's first-place
row, ``board0`` for a space's first cost option, ...), plus a column for a
hook (a flow kept as code, which a records-only reading would see as an
empty box). The definition's own fields that only name or tally those
records (an Agent box's effect key, the Reveal gains, a Contract's condition
and reward, a Conflict's reward rows, a Tech tile's ability key, a research
space's bonus) are left out, so two cards that print the same thing read the
same.

``FEATURE_DIGEST`` covers every vocabulary's ids, columns and values. An
``entity`` checkpoint stores it and the tables' names (``feature_tables``:
each vocabulary's ids, columns and the scale each column was divided by), so
a file written under another table -- a card record fixed, a card added --
is moved by name on load (``entity_network.retarget_entities``): a column or
entity the file never had starts at zero, and every entity whose own
features did not change computes exactly what it did. Change the reflection
only with ``FEATURE_VERSION``.

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
    IMPERIUM_IDENTITIES,
    INTRIGUE_IDS,
    LEADER_IDS,
    PERSONAL_CARD_IDS,
    POST_IDS,
    RESEARCH_SPACE_IDS,
    SCOUTS_ITEM_IDS,
    SKILL_IDS,
    SPACE_IDS,
)
from dune_imperium.content.bloodlines.sardaukar import SKILLS_BY_ID
from dune_imperium.content.bloodlines.tech import TECH_IDS, TECH_TILES_BY_ID
from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ABILITIES,
    TECH_ACQUIRE_ABILITIES,
)
from dune_imperium.content.immortality.board import RESEARCH_SPACES_BY_ID
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.immortality.track_abilities import RESEARCH_SPACE_ABILITIES
from dune_imperium.content.uprising.abilities import Ability
from dune_imperium.content.uprising.agent_abilities import agent_box_ability
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, OBSERVATION_POSTS
from dune_imperium.content.uprising.board_abilities import (
    BOARD_CHOICE_ABILITIES,
    BOARD_SPACE_ABILITIES,
)
from dune_imperium.content.uprising.conflict_abilities import CONFLICT_REWARD_ABILITIES
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.contract_abilities import CONTRACT_ABILITIES
from dune_imperium.content.uprising.contracts import (
    CONTRACTS_BY_ID,
    contract_for_instance,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_ID,
    INTRIGUE_CARDS_BY_INSTANCE,
)
from dune_imperium.content.uprising.leader_abilities import (
    LEADER_ABILITIES,
    SIGNET_ABILITIES,
)
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.reveal_abilities import REVEAL_GAIN_ABILITIES
from dune_imperium.content.uprising.reveal_choice_abilities import (
    reveal_choice_ability,
)
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    STARTING_CARDS_BY_ID,
)
from dune_imperium.content.uprising.trigger_abilities import (
    REVEAL_ACQUISITION_ABILITIES,
    TURN_START_ABILITIES,
    acquisition_ability,
    discard_ability,
    trash_ability,
)

FEATURE_VERSION: Final = 2
# Fields that name or cite an entity rather than describe what it does.
_SKIPPED_FIELDS: Final = frozenset(
    {"card", "name", "title", "sources", "source", "catalog_url", "required_leader_id"}
)


def featurize(
    value: object, prefix: str = "", skip: frozenset[str] = frozenset()
) -> dict[str, float]:
    """A value's features by reflection (module docstring); ``skip`` names
    top-level fields left out."""

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
            if field.name in _SKIPPED_FIELDS or field.name in skip:
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
    # The largest magnitude each column was divided by.
    scales: tuple[float, ...] = ()

    @property
    def size(self) -> int:
        return len(self.ids)


# A column some Uprising entity uses keeps the scale Uprising's entities give
# it, so every Uprising row reads exactly as before the original game's own
# entities joined (observation v35, ``IMPERIUM_IDENTITIES``; user approval
# 2026-10-27: Uprising rows byte-identical, scales included); an original
# entity may then read past 1 in such a column.


def _table(name: str, ids: tuple[str, ...], rows: list[dict[str, float]]) -> Vocabulary:
    columns = sorted({key for row in rows for key, amount in row.items() if amount})
    matrix = np.zeros((len(ids), len(columns)), dtype=np.float32)
    position = {column: index for index, column in enumerate(columns)}
    for index, row in enumerate(rows):
        for key, amount in row.items():
            if key in position:
                matrix[index, position[key]] = amount
    scale = np.abs(matrix).max(axis=0)
    uprising = [
        index for index, entity in enumerate(ids) if entity not in IMPERIUM_IDENTITIES
    ]
    if len(uprising) < len(ids):
        own = np.abs(matrix[uprising]).max(axis=0) if uprising else np.zeros_like(scale)
        scale = np.where(own > 0, own, scale)
    keep = scale > 0
    matrix = matrix[:, keep] / scale[keep]
    kept = tuple(column for column, used in zip(columns, keep, strict=True) if used)
    return Vocabulary(
        name=name,
        ids=ids,
        columns=kept,
        features=matrix,
        scales=tuple(float(value) for value in scale[keep]),
    )


def _personal_entry(card_id: str) -> object:
    if card_id == CONTROL_THE_SPICE.card.card_id:
        return CONTROL_THE_SPICE
    for table in (STARTING_CARDS_BY_ID, IMPERIUM_CARDS_BY_ID, TLEILAXU_CARDS_BY_ID):
        if card_id in table:
            return table[card_id]
    # Both base games' Reserve stacks (one id, one printing).
    return RESERVE_STACKS_BY_ID[card_id]


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


def _records(*records: tuple[str, Ability | None]) -> dict[str, float]:
    """Printed ability records' features, each under its prefix (module
    docstring); a hook is a column of its own."""

    features: dict[str, float] = {}
    for prefix, ability in records:
        if ability is None:
            continue
        row = featurize(ability, prefix)
        if ability.hook is not None:
            row[f"{prefix}.hook={ability.hook}"] = 1.0
        for key, amount in row.items():
            features[key] = features.get(key, 0.0) + amount
    return features


# A personal card's fields that name or tally its records.
_PERSONAL_RECORD_FIELDS: Final = frozenset(
    {
        "agent_effect",
        "acquisition_effect",
        "discard_effect",
        "reveal_acquisition_effect",
        "trash_effect",
        "reveal_choice_effects",
        "turn_start_effect",
    }
)


def _personal_records(entry: Any) -> dict[str, float]:
    agent = entry.agent_effect
    reveal_acquire = entry.reveal_acquisition_effect
    turn_start = getattr(entry, "turn_start_effect", None)
    features = _records(
        ("agent", agent_box_ability(agent)),
        ("reveal", REVEAL_GAIN_ABILITIES.get(entry.card.card_id)),
        *(
            ("reveal_choice", reveal_choice_ability(effect))
            for effect in entry.reveal_choice_effects
        ),
        ("acquire", acquisition_ability(getattr(entry, "acquisition_effect", None))),
        ("trash", trash_ability(getattr(entry, "trash_effect", None))),
        ("discard", discard_ability(entry.discard_effect)),
        (
            "reveal_acquire",
            None
            if reveal_acquire is None
            else REVEAL_ACQUISITION_ABILITIES[reveal_acquire],
        ),
        (
            "turn_start",
            None if turn_start is None else TURN_START_ABILITIES[turn_start],
        ),
    )
    if agent is not None and agent_box_ability(agent) is None:
        # The Signet Ring card: its box is the Leader's Signet Ring.
        features[f"agent.effect={agent.value}"] = 1.0
    return features


def _contract_record(definition: Any) -> Ability:
    return CONTRACT_ABILITIES[definition.copy_of or definition.card.card_id]


def _conflict_records(conflict_id: str) -> dict[str, float]:
    rows = CONFLICT_REWARD_ABILITIES.get(conflict_id, ())
    return _records(*zip(("first", "second", "third"), rows, strict=False))


def _space_records(space_id: str) -> dict[str, float]:
    return _records(
        *(
            (f"board{option}" + (f".{variant}" if variant else ""), ability)
            for (space, option, variant), ability in BOARD_SPACE_ABILITIES.items()
            if space == space_id
        ),
        *(
            (f"choice.{key}", ability)
            for (space, key), ability in BOARD_CHOICE_ABILITIES.items()
            if space == space_id
        ),
    )


def _leader_records(leader: Any) -> dict[str, float]:
    records: list[tuple[str, Ability | None]] = []
    # A one-faced Leader's records are keyed by its own id.
    for face, side in (
        (leader.setup_face_id or leader.leader_id, ""),
        (leader.alternate_face_id, "alternate_"),
    ):
        if face is None:
            continue
        records.append((f"{side}signet", SIGNET_ABILITIES.get(face)))
        records.extend(
            (f"{side}leader_{ability.timing.value}", ability)
            for ability in LEADER_ABILITIES.get(face, ())
        )
    return _records(*records)


def _tech_records(tech_id: str) -> dict[str, float]:
    return _records(
        ("acquire", TECH_ACQUIRE_ABILITIES.get(tech_id)),
        *(
            (f"tile_{ability.timing.value}", ability)
            for ability in TECH_ABILITIES[tech_id]
        ),
    )


_CONTRACT_RECORD_FIELDS: Final = frozenset({"terms"})


def _conflict_row(conflict_id: str) -> dict[str, float]:
    return _with(
        featurize(CONFLICTS_BY_ID[conflict_id], skip=frozenset({"reward_rows"})),
        _conflict_records(conflict_id),
    )


@cache
def vocabularies() -> dict[str, Vocabulary]:
    """Every vocabulary the ``entity`` network embeds, by name."""

    battle_rows = []
    for card_id in BATTLE_CARD_IDS:
        if card_id in CONFLICTS_BY_ID:
            battle_rows.append(_conflict_row(card_id))
        else:
            battle_rows.append(featurize(OBJECTIVES_BY_ID[card_id]))
    tables = (
        _table(
            "personal",
            PERSONAL_CARD_IDS,
            [
                {
                    **featurize(
                        _personal_entry(card_id), skip=_PERSONAL_RECORD_FIELDS
                    ),
                    **_personal_records(_personal_entry(card_id)),
                    **_kind(card_id),
                }
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
            [
                _with(
                    featurize(CONTRACTS_BY_ID[card_id], skip=_CONTRACT_RECORD_FIELDS),
                    _records(("contract", _contract_record(CONTRACTS_BY_ID[card_id]))),
                )
                for card_id in CONTRACT_IDS
            ],
        ),
        _table(
            "conflict",
            CONFLICT_IDS,
            [_conflict_row(card_id) for card_id in CONFLICT_IDS],
        ),
        _table("battle", BATTLE_CARD_IDS, battle_rows),
        _table(
            "space",
            SPACE_IDS,
            [
                _with(featurize(BOARD_SPACES_BY_ID[space_id]), _space_records(space_id))
                for space_id in SPACE_IDS
            ],
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
            [
                _with(
                    featurize(LEADERS_BY_ID[leader_id]),
                    _leader_records(LEADERS_BY_ID[leader_id]),
                )
                for leader_id in LEADER_IDS
            ],
        ),
        _table(
            "tech",
            TECH_IDS,
            [
                _with(
                    featurize(TECH_TILES_BY_ID[tech_id], skip=frozenset({"ability"})),
                    _tech_records(tech_id),
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
                    _records(
                        (
                            SKILLS_BY_ID[skill_id].ability.timing.value,
                            SKILLS_BY_ID[skill_id].ability,
                        )
                    ),
                )
                for skill_id in SKILL_IDS
            ],
        ),
        _table(
            "research",
            RESEARCH_SPACE_IDS,
            [
                _with(
                    featurize(
                        RESEARCH_SPACES_BY_ID[space_id], skip=frozenset({"bonus"})
                    ),
                    _records(("track", RESEARCH_SPACE_ABILITIES.get(space_id))),
                )
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
    # The board space Kwisatz Haderach's Agent comes off (the original game;
    # a space's id may be a Contract's too, as ``deliver_supplies`` is).
    "from_space": ("space",),
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
    # Stage B3: the entity that printed a waiting effect -- a card type, the
    # visited space, a leader face, a Tech tile, a Commander's Skill (B3b-2),
    # a research space (B3c-2a), the Conflict card whose reward row pays and
    # the Intrigue card whose lines are played (B3d-1), the Faction whose
    # Influence track opened a Spy window (B3d-2a); a Contract by its
    # instance; a market is a label.
    "printed": (
        "personal",
        "space",
        "leader",
        "tech",
        "skill",
        "research",
        "conflict",
        "intrigue",
        "faction",
    ),
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
    # Stage B3: an effect row's printed ``icon`` and the ``option`` of an
    # alternative or of a target row are labels too.
    {
        "choice",
        "effect",
        "icon",
        # Stage B3d-3: the verb of the effect a refusal answers.
        "of",
        "option",
        "reward",
        "subcommittee_id",
        "zone",
        "zones",
    }
)
# The Arrakeen Scouts items a Scouts effect row's ``printed`` may name (a
# Spy window's line, B3d-2a; a mission, B3d-2b): no vocabulary holds them,
# and an item's id may be a card's too (Covert Operation).
_SCOUTS_PRINTED: Final = frozenset(SCOUTS_ITEM_IDS)
# Where an argument's vocabulary depends on the action: a battle card's id
# is often a Conflict card's id too.
ACTION_ARGUMENT_HINTS: Final[Mapping[tuple[str, str], tuple[str, ...]]] = {
    ("flip_battle_card", "card_id"): ("battle",),
    # Stage B3's target rows name their target by its kind.
    ("choose_intrigue_card", "card_id"): ("intrigue",),
    # The Endgame wild match's two cards (stage B3c-1), as its arguments.
    ("choose_conflict_card", "card_id"): ("battle", "conflict"),
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
    digest.update(repr(sorted(_SCOUTS_PRINTED)).encode())
    return digest.hexdigest()


FEATURE_DIGEST: Final = _digest()


def feature_tables() -> dict[str, dict[str, list[Any]]]:
    """Each vocabulary's ids, columns and column scales, as a checkpoint
    stores them (module docstring)."""

    return {
        name: {
            "ids": list(table.ids),
            "columns": list(table.columns),
            "scales": list(table.scales),
        }
        for name, table in vocabularies().items()
    }


_LEADER_OF_FACE: Final = {
    leader.alternate_face_id: leader_id
    for leader_id, leader in LEADERS_BY_ID.items()
    if leader.alternate_face_id is not None
}


def resolve_argument(
    action_id: str, key: str, value: str, source: object = None
) -> tuple[str, int] | None:
    """The entity an action argument names, or ``None`` for a label;
    ``source`` is the row's own ``source`` argument (an effect row's)."""

    if key in LABEL_ARGUMENTS or (
        key == "printed" and source == "scouts" and value in _SCOUTS_PRINTED
    ):
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
    # A leader's other face (Reverend Mother Jessica) is its leader card.
    value = _LEADER_OF_FACE.get(value, value)
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
