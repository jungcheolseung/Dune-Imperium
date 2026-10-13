"""The ``entity`` policy/value network (docs/entity-network-plan.md section 3).

It reads the same flat observation (v31) and answers through the same three
calls as the MLP -- ``trunk``, ``action_logits``, ``value_head`` -- so
collection, the learner, the search seat and checkpoints use it unchanged.
What changes is how it reads and scores:

- **Entities by their features.** Every card, space, Conflict, contract,
  Leader, Tech tile, Skill, Observation Post and research space has an
  embedding computed from its content features (``training.entity_features``)
  plus a learned vector of its own that starts at zero.
- **Zones as sums.** A count zone (a hand, a discard pile, the Intrigue
  discard, held contracts, ...) is the count-weighted sum of its entities'
  embeddings, so a card it never saw still reads like its look-alikes.
- **Slots by identity.** The identity columns (the Imperium Row, the current
  Conflict, Agent locations, each Leader, ...) are read through the slot
  table of ``training.slots``: each key has a learned vector, plus its
  entity's embedding when the key names one.
- **Seats share one encoder.** Each seat's columns, zones and slots go
  through the same seat encoder (relative seat 0 is the observer), then a
  torso mixes them with the board and the private view.
- **Actions by their parts.** A catalog action's vector is built from its
  kind and its arguments -- an entity argument through the entity embedding,
  a label through a learned vector per (argument, value), a number scaling a
  learned vector per argument -- and scored against the state by a dot
  product, plus a learned bias per action that starts at zero. A new action
  (a rule change) gets a sensible score from its parts at once.
- **Optional own action vectors** (``own_actions``): a learned vector per
  catalog action, zero at the start, added to the vector built from its
  parts. The parts alone lost about 2pp of agreement with network Y in the
  distillation of 2026-10-13 (docs/entity-network-plan.md section 10); an
  action never trained still scores from its parts.
- **Optional auxiliary head** (``aux_vp``): each relative seat's final
  Victory Points, a denser target than the win (section 3.5).

``arch_spec`` stores the ruleset the catalog comes from and the feature
table's digest; ``training.checkpoint`` refuses a file under another table.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final, NamedTuple

import torch
from torch import Tensor, nn

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    CONTRACT_SEGMENTS,
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
)
from dune_imperium.config import RulesetConfig
from dune_imperium.training.entity_features import (
    FEATURE_DIGEST,
    SLOT_HINTS,
    resolve,
    resolve_argument,
    vocabularies,
)
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.slots import (
    SLOT_FIELDS,
    SLOT_KEYS,
    VALUE_RANGE,
    lookup_tables,
)

MASKED_LOGIT: Final = -1.0e9
DEFAULT_ENTITY_WIDTH: Final = 64
DEFAULT_SEAT_WIDTH: Final = 256
DEFAULT_ACTION_WIDTH: Final = 128
_SEATS: Final = 4
# The vocabulary each count zone counts, by segment name (seat segments by
# their suffix after ``seat<k>_``).
_ZONE_VOCABULARY: Final = {
    "hand_public": "personal",
    "in_play": "personal",
    "discard": "personal",
    "trashed": "personal",
    "private_hand": "personal",
    "private_peeked_card": "personal",
    "imperium_removed": "personal",
    "intrigue_resolving": "intrigue",
    "intrigue_discard": "intrigue",
    "intrigue_faceup": "intrigue",
    "private_intrigue": "intrigue",
    "private_peeked_intrigue": "intrigue",
    "tech_trash": "tech",
    "tech": "tech",
    "skills": "skill",
    "skill_face_up": "skill",
    "battle_cards": "battle",
    "spy_posts": "post",
    "alliances": "faction",
    **{
        name.split("_", 1)[1] if name.startswith("seat") else name: "contract"
        for name in CONTRACT_SEGMENTS
    },
}


class _Tables(NamedTuple):
    entities: Tensor  # [N + 1, E]
    keys: Tensor  # [K + 1, E], the pad row zero


# A catalog template's identity: its action id and its arguments.
TemplateKey = tuple[str, tuple[tuple[str, object], ...]]


class ActionVocabulary(NamedTuple):
    """The parts a catalog's actions are scored from, in table order.

    Row ``0`` of the argument-key and label tables is the pad, so ``keys[i]``
    and ``labels[i]`` are rows ``i + 1``. Another catalog (another ruleset or
    codec version) has other parts; a checkpoint moves its rows by these
    names (``retarget_action_parts``).
    """

    kinds: tuple[str, ...]
    keys: tuple[str, ...]
    labels: tuple[tuple[str, object], ...]


def _argument_label(
    action_id: str, key: str, value: object
) -> tuple[str, object] | None:
    """The label an argument value is embedded by, if it is not an entity."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return (key, value)
    if isinstance(value, str) and resolve_argument(action_id, key, value) is None:
        return (key, value)
    return None


def action_vocabulary(templates: Iterable[TemplateKey]) -> ActionVocabulary:
    """The action parts of ``templates`` (``checkpoint.template_keys``)."""

    rows = list(templates)
    labels: dict[tuple[str, object], None] = {}
    for action_id, arguments in rows:
        for key, value in arguments:
            label = _argument_label(action_id, key, value)
            if label is not None:
                labels.setdefault(label, None)
    return ActionVocabulary(
        kinds=tuple(sorted({action_id for action_id, _ in rows})),
        keys=tuple(sorted({key for _, arguments in rows for key, _ in arguments})),
        labels=tuple(labels),
    )


def _moved_rows(
    old: Tensor, old_names: Sequence[object], new_names: Sequence[object], pad: bool
) -> Tensor:
    """``old``'s rows reordered to ``new_names``; a name it lacks is zero."""

    offset = 1 if pad else 0
    rows = old.new_zeros((len(new_names) + offset, *old.shape[1:]))
    where = {name: index + offset for index, name in enumerate(old_names)}
    for index, name in enumerate(new_names):
        found = where.get(name)
        if found is not None:
            rows[index + offset] = old[found]
    return rows


def retarget_action_parts(
    state_dict: dict[str, Tensor], old: ActionVocabulary, new: ActionVocabulary
) -> dict[str, Tensor]:
    """Move a state dict's action-part rows from ``old`` to ``new``.

    A part the old catalog never had starts at zero (deterministic: loading
    a file twice gives the same network); the action is still scored from
    its other parts.
    """

    moved = dict(state_dict)
    moved["kind_embed.weight"] = _moved_rows(
        state_dict["kind_embed.weight"], old.kinds, new.kinds, pad=False
    )
    for name in ("key_number.weight", "key_entity"):
        moved[name] = _moved_rows(state_dict[name], old.keys, new.keys, pad=True)
    moved["label_embed.weight"] = _moved_rows(
        state_dict["label_embed.weight"], old.labels, new.labels, pad=True
    )
    return moved


def _group(segment: str) -> str:
    if segment.startswith("seat") and segment[4].isdigit():
        return f"seat{segment[4]}"
    if segment.startswith("private_"):
        return "private"
    return "board"


def _zone_name(segment: str) -> str:
    return segment.split("_", 1)[1] if _group(segment).startswith("seat") else segment


class EntityNetwork(PolicyValueNetwork):
    """Policy and value over entity embeddings (module docstring).

    A ``PolicyValueNetwork`` by type, so every caller that holds one (the
    learner, collection, the search seat) takes it as is. It skips that
    class's constructor: it has no catalog-sized ``policy_head`` (the MLP's
    18 million weights), so a caller that reads that head directly (the
    MLP checkpoint migration, expert iteration's distillation) does not
    apply to it.
    """

    # Buffers (``register_buffer``), typed for mypy.
    slot_columns: Tensor
    slot_table: Tensor
    slot_bases: Tensor
    slot_lookup_field: Tensor
    slot_key_entity: Tensor
    slot_key_live: Tensor
    action_kind: Tensor
    arg_key: Tensor
    arg_entity: Tensor
    arg_label: Tensor
    arg_number: Tensor

    def __init__(
        self,
        config: RulesetConfig,
        *,
        hidden: Sequence[int] = (512, 512),
        entity_width: int = DEFAULT_ENTITY_WIDTH,
        seat_width: int = DEFAULT_SEAT_WIDTH,
        action_width: int = DEFAULT_ACTION_WIDTH,
        aux_vp: bool = False,
        own_actions: bool = False,
    ) -> None:
        nn.Module.__init__(self)
        if not hidden or any(width < 1 for width in hidden):
            raise ValueError("hidden widths must be positive")
        self.config = config
        self.hidden = tuple(hidden)
        self.entity_width = entity_width
        self.seat_width = seat_width
        self.action_width = action_width
        self.aux_vp = aux_vp
        self.own_actions = own_actions
        self.observation_size = OBSERVATION_SIZE
        catalog = ActionCodec(config).catalog
        self.action_size = len(catalog)
        self._build_entities()
        self._build_observation_tables()
        self._build_encoders()
        self._build_action_tables(catalog)
        self._cache_key: tuple[int, ...] | None = None
        self._cache_value: Tensor | None = None
        self._tables_key: tuple[int, ...] | None = None
        self._tables_value: _Tables | None = None
        self._weights: tuple[nn.Parameter, ...] = tuple(self.parameters())

    # -- entities -------------------------------------------------------------
    def _build_entities(self) -> None:
        tables = vocabularies()
        self.vocabulary_names = tuple(sorted(tables))
        self.entity_project = nn.ModuleDict()
        self.entity_own = nn.ParameterDict()
        offsets: dict[str, int] = {}
        total = 0
        for name in self.vocabulary_names:
            table = tables[name]
            self.register_buffer(
                f"features_{name}",
                torch.from_numpy(table.features.copy()),
                persistent=False,
            )
            self.entity_project[name] = nn.Linear(
                max(1, len(table.columns)), self.entity_width
            )
            self.entity_own[name] = nn.Parameter(
                torch.zeros(table.size, self.entity_width)
            )
            offsets[name] = total
            total += table.size
        self.entity_offsets = offsets
        # One row past the last entity: the zero vector of "no entity".
        self.entity_count = total

    def entity_table(self) -> Tensor:
        """Every entity's embedding ``[N + 1, E]`` (the last row is zero)."""

        parts = []
        for name in self.vocabulary_names:
            features: Tensor = getattr(self, f"features_{name}")
            if features.shape[1] == 0:
                features = torch.zeros(features.shape[0], 1)
            parts.append(
                torch.tanh(self.entity_project[name](features)) + self.entity_own[name]
            )
        parts.append(torch.zeros(1, self.entity_width))
        return torch.cat(parts)

    # -- the observation ------------------------------------------------------
    def _build_observation_tables(self) -> None:
        slot_columns = {column for field in SLOT_FIELDS for column in field.columns}
        sizes = {name: table.size for name, table in vocabularies().items()}
        groups = ("board", "private", *(f"seat{seat}" for seat in range(_SEATS)))
        zones: dict[str, list[tuple[int, int, str]]] = {group: [] for group in groups}
        raw: dict[str, list[int]] = {group: [] for group in groups}
        for segment in OBSERVATION_SEGMENTS:
            group = _group(segment.name)
            vocabulary = _ZONE_VOCABULARY.get(_zone_name(segment.name))
            if vocabulary is not None:
                if sizes[vocabulary] != segment.length:
                    raise ValueError(
                        f"segment {segment.name} has {segment.length} columns, "
                        f"vocabulary {vocabulary} {sizes[vocabulary]}"
                    )
                zones[group].append((segment.offset, segment.length, vocabulary))
                continue
            raw[group].extend(
                column
                for column in range(segment.offset, segment.offset + segment.length)
                if column not in slot_columns
            )
        field_groups = []
        for field in SLOT_FIELDS:
            owners = {_group(segment) for segment in field.segments}
            field_groups.append(owners.pop() if len(owners) == 1 else "board")
        fields = {
            group: [index for index, owner in enumerate(field_groups) if owner == group]
            for group in groups
        }

        seat_vocabularies = {
            tuple(vocabulary for _, _, vocabulary in zones[f"seat{seat}"])
            for seat in range(_SEATS)
        }
        seat_shapes = {
            (len(raw[f"seat{seat}"]), len(fields[f"seat{seat}"]))
            for seat in range(_SEATS)
        }
        if len(seat_vocabularies) != 1 or len(seat_shapes) != 1:
            raise ValueError("every seat must have the same columns")
        # Zones are read one vocabulary at a time (every hand and discard pile
        # of every seat against the personal-card embeddings in one product):
        # a block-diagonal product over all of them would be mostly zeros.
        # ``zone_columns_<vocabulary>`` holds each zone's columns ``[Zv, n]``;
        # the results are concatenated in vocabulary order, and each encoder
        # finds its zones there by ``zone_positions_<encoder>``.
        self.zone_vocabulary_order = tuple(
            sorted(
                {vocabulary for group in groups for _, _, vocabulary in zones[group]}
            )
        )
        position: dict[tuple[str, int], int] = {}
        placed = 0
        for vocabulary in self.zone_vocabulary_order:
            columns_of = []
            for group in groups:
                for index, (offset, length, owner) in enumerate(zones[group]):
                    if owner == vocabulary:
                        columns_of.append(list(range(offset, offset + length)))
                        position[(group, index)] = placed
                        placed += 1
            self.register_buffer(
                f"zone_columns_{vocabulary}",
                torch.tensor(columns_of, dtype=torch.long),
                persistent=False,
            )
        for group in ("board", "private"):
            self.register_buffer(
                f"raw_{group}",
                torch.tensor(raw[group], dtype=torch.long),
                persistent=False,
            )
            self.register_buffer(
                f"zone_positions_{group}",
                torch.tensor(
                    [position[(group, index)] for index in range(len(zones[group]))],
                    dtype=torch.long,
                ),
                persistent=False,
            )
            self.register_buffer(
                f"fields_{group}",
                torch.tensor(fields[group], dtype=torch.long),
                persistent=False,
            )
        seats = [f"seat{seat}" for seat in range(_SEATS)]
        self.register_buffer(
            "raw_seat", torch.tensor([raw[seat] for seat in seats]), persistent=False
        )
        self.register_buffer(
            "zone_positions_seat",
            torch.tensor(
                [
                    [position[(seat, index)] for index in range(len(zones[seat]))]
                    for seat in seats
                ],
                dtype=torch.long,
            ),
            persistent=False,
        )
        self.register_buffer(
            "fields_seat",
            torch.tensor([fields[seat] for seat in seats]),
            persistent=False,
        )
        # Slot lookups (training.slots): which field each lookup feeds, and
        # each key's entity (or the zero row).
        columns, table = lookup_tables()
        lookup_field: list[int] = []
        for field_index, field in enumerate(SLOT_FIELDS):
            per_column = len(field.values) if field.bitmask else 1
            lookup_field.extend([field_index] * (len(field.columns) * per_column))
        if len(lookup_field) != columns.shape[0]:
            raise ValueError("slot lookups and fields disagree")
        self.register_buffer("slot_columns", columns, persistent=False)
        self.register_buffer("slot_table", table, persistent=False)
        self.register_buffer(
            "slot_bases",
            torch.arange(columns.shape[0], dtype=torch.long) * VALUE_RANGE,
            persistent=False,
        )
        self.register_buffer(
            "slot_lookup_field",
            torch.tensor(lookup_field, dtype=torch.long),
            persistent=False,
        )
        key_entity = []
        for key in SLOT_KEYS:
            prefix, _, identity = key.partition(":")
            found = resolve(identity, SLOT_HINTS.get(prefix, ()))
            key_entity.append(
                self.entity_count
                if found is None
                else self.entity_offsets[found[0]] + found[1]
            )
        key_entity.append(self.entity_count)  # PAD_ROW
        self.register_buffer(
            "slot_key_entity",
            torch.tensor(key_entity, dtype=torch.long),
            persistent=False,
        )
        self.register_buffer(
            "slot_key_live",
            torch.tensor([1.0] * len(SLOT_KEYS) + [0.0]).unsqueeze(1),
            persistent=False,
        )
        self.slot_key_own = nn.Parameter(
            torch.zeros(len(SLOT_KEYS) + 1, self.entity_width)
        )

    def _encoder_width(self, encoder: str) -> int:
        raw: Tensor = getattr(self, f"raw_{encoder}")
        fields: Tensor = getattr(self, f"fields_{encoder}")
        positions: Tensor = getattr(self, f"zone_positions_{encoder}")
        zones = int(positions.shape[-1])
        return int(raw.shape[-1]) + (zones + int(fields.shape[-1])) * self.entity_width

    # -- the encoders -----------------------------------------------------------
    def _build_encoders(self) -> None:
        self.seat_encoder = nn.Sequential(
            nn.Linear(self._encoder_width("seat"), self.seat_width), nn.ReLU()
        )
        self.board_encoder = nn.Sequential(
            nn.Linear(self._encoder_width("board"), self.seat_width), nn.ReLU()
        )
        self.private_encoder = nn.Sequential(
            nn.Linear(self._encoder_width("private"), self.seat_width), nn.ReLU()
        )
        layers: list[nn.Module] = []
        width = self.seat_width * (2 + _SEATS)
        for next_width in self.hidden:
            layers.append(nn.Linear(width, next_width))
            layers.append(nn.ReLU())
            width = next_width
        self.body = nn.Sequential(*layers)
        self.value_head = nn.Linear(width, 1)
        self.query = nn.Linear(width, self.action_width)
        self.vp_head: nn.Linear | None = (
            nn.Linear(width, _SEATS) if self.aux_vp else None
        )

    # -- the tables an observation is read with ----------------------------------
    def _weights_version(self) -> tuple[int, ...]:
        # In-place updates (optimizer steps, load_state_dict copies) bump a
        # tensor's version; walking ``self.parameters()`` on every call costs
        # more than the batch-1 forward pass, so the list is kept and only
        # rebuilt when the parameters themselves are replaced.
        return tuple(parameter._version for parameter in self._weights)

    def _refresh_weights(self) -> None:
        self._weights = tuple(self.parameters())
        self._cache_key = self._tables_key = None
        self._cache_value = None
        self._tables_value = None

    def _apply(self, fn: Any, recurse: bool = True) -> EntityNetwork:
        super()._apply(fn, recurse)  # type: ignore[no-untyped-call]
        self._refresh_weights()
        return self

    def load_state_dict(
        self, state_dict: Mapping[str, Any], strict: bool = True, assign: bool = False
    ) -> Any:
        result = super().load_state_dict(state_dict, strict=strict, assign=assign)
        self._refresh_weights()
        return result

    def _compute_tables(self) -> _Tables:
        entities = self.entity_table()
        keys = (self.slot_key_own + entities[self.slot_key_entity]) * self.slot_key_live
        return _Tables(entities=entities, keys=keys)

    def _tables(self) -> _Tables:
        """The entity and slot-key tables; cached while no gradient is taken
        (inference does not change the weights)."""

        if torch.is_grad_enabled():
            return self._compute_tables()
        version = self._weights_version()
        if self._tables_key != version or self._tables_value is None:
            self._tables_value = self._compute_tables()
            self._tables_key = version
        return self._tables_value

    def _slot_fields(self, observations: Tensor, keys: Tensor) -> Tensor:
        """Each slot field's summed key vectors ``[B, F, E]``."""

        values = observations.index_select(1, self.slot_columns).long()
        values = values.clamp(0, VALUE_RANGE - 1)
        rows = self.slot_table[values + self.slot_bases]  # [B, C]
        vectors = keys[rows]  # [B, C, E]
        fields = torch.zeros(observations.shape[0], len(SLOT_FIELDS), self.entity_width)
        return fields.index_add(1, self.slot_lookup_field, vectors)

    def _zone_vectors(self, observations: Tensor, entities: Tensor) -> Tensor:
        """Every zone's count-weighted entity sum ``[B, Z, E]``."""

        vectors = []
        for vocabulary in self.zone_vocabulary_order:
            columns: Tensor = getattr(self, f"zone_columns_{vocabulary}")
            start = self.entity_offsets[vocabulary]
            table = entities[start : start + int(columns.shape[1])]
            vectors.append(observations[:, columns] @ table)
        return torch.cat(vectors, dim=1)

    def _encode(
        self, encoder: str, observations: Tensor, fields: Tensor, zones: Tensor
    ) -> Tensor:
        """One encoder's input: raw columns, zone sums and slot fields."""

        raw: Tensor = getattr(self, f"raw_{encoder}")
        positions: Tensor = getattr(self, f"zone_positions_{encoder}")
        chosen: Tensor = getattr(self, f"fields_{encoder}")
        parts = [
            torch.log1p(observations[:, raw].clamp(min=0.0)),
            zones[:, positions].flatten(-2),
            fields[:, chosen].flatten(-2),
        ]
        return torch.cat(parts, dim=-1)

    def trunk(self, observations: Tensor) -> Tensor:
        """The hidden features ``[B, H]`` both heads read."""

        observations = observations.to(torch.float32)
        tables = self._tables()
        fields = self._slot_fields(observations, tables.keys)
        zones = self._zone_vectors(observations, tables.entities)
        # Seats ``[B, 4, ...]``: one shared encoder for the four of them.
        seats = self.seat_encoder(
            self._encode("seat", observations, fields, zones)
        ).flatten(1)
        board = self.board_encoder(self._encode("board", observations, fields, zones))
        private = self.private_encoder(
            self._encode("private", observations, fields, zones)
        )
        hidden: Tensor = self.body(torch.cat([board, private, seats], dim=1))
        return hidden

    # -- the actions ------------------------------------------------------------
    def _build_action_tables(self, catalog: Sequence[Any]) -> None:
        vocabulary = action_vocabulary(
            (template.action_id, template.arguments) for template in catalog
        )
        kinds, keys = vocabulary.kinds, vocabulary.keys
        kind_index = {kind: index for index, kind in enumerate(kinds)}
        key_index = {key: index + 1 for index, key in enumerate(keys)}
        labels = {label: index + 1 for index, label in enumerate(vocabulary.labels)}
        width = max((len(template.arguments) for template in catalog), default=0)
        width = max(width, 1)
        action_kind = []
        arg_key = []
        arg_entity = []
        arg_label = []
        arg_number = []
        for template in catalog:
            action_kind.append(kind_index[template.action_id])
            row_key, row_entity, row_label, row_number = [], [], [], []
            for key, value in template.arguments:
                row_key.append(key_index[key])
                entity = self.entity_count
                number = 0.0
                label_key = _argument_label(template.action_id, key, value)
                if isinstance(value, bool):
                    number = float(value)
                elif isinstance(value, int):
                    number = math.log1p(abs(value)) * (1 if value >= 0 else -1)
                elif isinstance(value, str) and label_key is None:
                    found = resolve_argument(template.action_id, key, value)
                    assert found is not None
                    entity = self.entity_offsets[found[0]] + found[1]
                label = 0 if label_key is None else labels[label_key]
                row_entity.append(entity)
                row_label.append(label)
                row_number.append(number)
            padding = width - len(row_key)
            arg_key.append(row_key + [0] * padding)
            arg_entity.append(row_entity + [self.entity_count] * padding)
            arg_label.append(row_label + [0] * padding)
            arg_number.append(row_number + [0.0] * padding)
        self.action_vocabulary = vocabulary
        self.register_buffer("action_kind", torch.tensor(action_kind), persistent=False)
        self.register_buffer("arg_key", torch.tensor(arg_key), persistent=False)
        self.register_buffer("arg_entity", torch.tensor(arg_entity), persistent=False)
        self.register_buffer("arg_label", torch.tensor(arg_label), persistent=False)
        self.register_buffer(
            "arg_number",
            torch.tensor(arg_number, dtype=torch.float32),
            persistent=False,
        )
        a = self.action_width
        self.kind_embed = nn.Embedding(len(kinds), a)
        self.key_number = nn.Embedding(len(keys) + 1, a, padding_idx=0)
        self.label_embed = nn.Embedding(len(labels) + 1, a, padding_idx=0)
        # One projection of an entity per argument (a card to play and a card
        # to trash are different roles).
        self.key_entity = nn.Parameter(
            torch.randn(len(keys) + 1, self.entity_width, a)
            / math.sqrt(self.entity_width)
        )
        with torch.no_grad():
            self.key_entity[0].zero_()
        self.action_mlp = nn.Sequential(nn.ReLU(), nn.Linear(a, a))
        self.action_bias = nn.Parameter(torch.zeros(self.action_size))
        self.action_own: nn.Parameter | None = (
            nn.Parameter(torch.zeros(self.action_size, a)) if self.own_actions else None
        )

    def twin_actions(self) -> list[list[int]]:
        """Groups of catalog rows built from the same parts.

        Only their per-action bias tells them apart (the plan's section 7:
        what the features miss is listed, not hidden).
        """

        groups: dict[tuple[object, ...], list[int]] = {}
        parts = zip(
            self.action_kind.tolist(),
            self.arg_key.tolist(),
            self.arg_entity.tolist(),
            self.arg_label.tolist(),
            self.arg_number.tolist(),
            strict=True,
        )
        for index, (kind, keys, entities, labels, numbers) in enumerate(parts):
            key = (kind, tuple(keys), tuple(entities), tuple(labels), tuple(numbers))
            groups.setdefault(key, []).append(index)
        return [rows for rows in groups.values() if len(rows) > 1]

    def action_vectors(self, actions: Tensor, entities: Tensor | None = None) -> Tensor:
        """The vectors ``[K, A]`` of catalog indices ``actions``."""

        if entities is None:
            entities = self.entity_table()
        keys = self.arg_key[actions]  # [K, M]
        vector = self.kind_embed(self.action_kind[actions])
        vector = vector + (
            self.key_number(keys) * self.arg_number[actions].unsqueeze(-1)
        ).sum(dim=1)
        vector = vector + self.label_embed(self.arg_label[actions]).sum(dim=1)
        # Project each distinct (argument, entity) pair once: gathering a
        # projection per action and argument would hold K * M * E * A floats.
        rows = self.entity_count + 1
        pairs = keys * rows + self.arg_entity[actions]  # [K, M]
        unique, inverse = torch.unique(pairs, return_inverse=True)
        projected = torch.bmm(
            entities[unique % rows].unsqueeze(1), self.key_entity[unique // rows]
        ).squeeze(1)  # [P, A]
        vector = vector + projected[inverse].sum(dim=1)
        vectors: Tensor = self.action_mlp(vector)
        if self.action_own is not None:
            vectors = vectors + self.action_own[actions]
        return vectors

    def action_logits(self, hidden: Tensor, actions: Tensor) -> Tensor:
        """Unmasked logits ``[B, K]`` of the catalog indices ``actions``."""

        if torch.is_grad_enabled():
            vectors = self.action_vectors(actions, self._tables().entities)
        else:
            vectors = self._all_actions()[actions]
        logits: Tensor = self.query(hidden) @ vectors.T + self.action_bias[actions]
        return logits

    def row_action_logits(self, hidden: Tensor, actions: Tensor) -> Tensor:
        """Unmasked logits ``[B, L]``; row ``b`` scores ``actions[b]``."""

        unique, inverse = torch.unique(actions, return_inverse=True)
        logits = self.action_logits(hidden, unique)  # [B, U]
        return torch.gather(logits, 1, inverse.reshape(actions.shape))

    def _all_actions(self) -> Tensor:
        """Every catalog action's vector, cached while no gradient is taken."""

        everything = torch.arange(self.action_size)
        if torch.is_grad_enabled():
            return self.action_vectors(everything, self._tables().entities)
        version = self._weights_version()
        if self._cache_key != version or self._cache_value is None:
            self._cache_value = self.action_vectors(everything, self._tables().entities)
            self._cache_key = version
        return self._cache_value

    def forward(self, observations: Tensor, masks: Tensor) -> tuple[Tensor, Tensor]:
        """Masked logits ``[B, A]`` over the whole catalog and values ``[B]``."""

        hidden = self.trunk(observations)
        logits = self.query(hidden) @ self._all_actions().T + self.action_bias
        logits = logits.masked_fill(masks == 0, MASKED_LOGIT)
        values = self.value_head(hidden).squeeze(-1)
        return logits, values

    def arch_spec(self) -> dict[str, Any]:
        return {
            "kind": "entity",
            "hidden": list(self.hidden),
            "entity_width": self.entity_width,
            "seat_width": self.seat_width,
            "action_width": self.action_width,
            "aux_vp": self.aux_vp,
            "own_actions": self.own_actions,
            "ruleset": self.config.identifier,
            "feature_digest": FEATURE_DIGEST,
        }
