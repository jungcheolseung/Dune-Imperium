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
- **Optional auxiliary head** (``aux_vp``): each relative seat's final
  Victory Points, a denser target than the win (section 3.5).

``arch_spec`` stores the ruleset the catalog comes from and the feature
table's digest; ``training.checkpoint`` refuses a file under another table.
"""

import math
from collections.abc import Sequence
from typing import Any, Final

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
    ARGUMENT_HINTS,
    FEATURE_DIGEST,
    SLOT_HINTS,
    resolve,
    vocabularies,
)
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.slots import (
    PAD_ROW,
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
        self.observation_size = OBSERVATION_SIZE
        catalog = ActionCodec(config).catalog
        self.action_size = len(catalog)
        self._build_entities()
        self._build_observation_tables()
        self._build_encoders()
        self._build_action_tables(catalog)
        self._cache_key: tuple[int, ...] | None = None
        self._cache_value: Tensor | None = None

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
        groups = ("board", "private", *(f"seat{seat}" for seat in range(_SEATS)))
        slot_columns = {column for field in SLOT_FIELDS for column in field.columns}
        sizes = {name: table.size for name, table in vocabularies().items()}
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
        self.zone_specs = zones
        for group in groups:
            self.register_buffer(
                f"raw_{group}",
                torch.tensor(raw[group], dtype=torch.long),
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
        self.slot_key_own = nn.Parameter(
            torch.zeros(len(SLOT_KEYS) + 1, self.entity_width)
        )
        field_groups = []
        for field in SLOT_FIELDS:
            owners = {_group(segment) for segment in field.segments}
            field_groups.append(owners.pop() if len(owners) == 1 else "board")
        self.slot_field_groups = tuple(field_groups)
        self.groups = groups

    def _group_width(self, group: str) -> int:
        raw: Tensor = getattr(self, f"raw_{group}")
        zones = len(self.zone_specs[group])
        fields = sum(1 for owner in self.slot_field_groups if owner == group)
        return int(raw.shape[0]) + (zones + fields) * self.entity_width

    # -- the encoders -----------------------------------------------------------
    def _build_encoders(self) -> None:
        seat_input = self._group_width("seat0")
        for seat in range(1, _SEATS):
            if self._group_width(f"seat{seat}") != seat_input:
                raise ValueError("every seat must have the same columns")
        self.seat_encoder = nn.Sequential(
            nn.Linear(seat_input, self.seat_width), nn.ReLU()
        )
        self.board_encoder = nn.Sequential(
            nn.Linear(self._group_width("board"), self.seat_width), nn.ReLU()
        )
        self.private_encoder = nn.Sequential(
            nn.Linear(self._group_width("private"), self.seat_width), nn.ReLU()
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

    def _group_vector(
        self, group: str, observations: Tensor, entities: Tensor, fields: Tensor
    ) -> Tensor:
        raw: Tensor = getattr(self, f"raw_{group}")
        parts = [torch.log1p(observations.index_select(1, raw).clamp(min=0.0))]
        for offset, length, vocabulary in self.zone_specs[group]:
            start = self.entity_offsets[vocabulary]
            counts = observations[:, offset : offset + length]
            parts.append(counts @ entities[start : start + length])
        for index, owner in enumerate(self.slot_field_groups):
            if owner == group:
                parts.append(fields[:, index])
        return torch.cat(parts, dim=1)

    def _slot_fields(self, observations: Tensor, entities: Tensor) -> Tensor:
        """Each slot field's summed key vectors ``[B, F, E]``."""

        values = observations.index_select(1, self.slot_columns).long()
        values = values.clamp(0, VALUE_RANGE - 1)
        rows = self.slot_table[values + self.slot_bases]  # [B, C]
        keys = self.slot_key_own + entities[self.slot_key_entity]  # [K + 1, E]
        keys = keys.clone()
        keys[PAD_ROW] = 0.0
        vectors = keys[rows]  # [B, C, E]
        fields = torch.zeros(observations.shape[0], len(SLOT_FIELDS), self.entity_width)
        return fields.index_add(1, self.slot_lookup_field, vectors)

    def trunk(self, observations: Tensor) -> Tensor:
        """The hidden features ``[B, H]`` both heads read."""

        observations = observations.to(torch.float32)
        entities = self.entity_table()
        fields = self._slot_fields(observations, entities)
        seats = [
            self.seat_encoder(
                self._group_vector(f"seat{seat}", observations, entities, fields)
            )
            for seat in range(_SEATS)
        ]
        board = self.board_encoder(
            self._group_vector("board", observations, entities, fields)
        )
        private = self.private_encoder(
            self._group_vector("private", observations, entities, fields)
        )
        hidden: Tensor = self.body(torch.cat([board, private, *seats], dim=1))
        return hidden

    # -- the actions ------------------------------------------------------------
    def _build_action_tables(self, catalog: Sequence[Any]) -> None:
        kinds = sorted({template.action_id for template in catalog})
        kind_index = {kind: index for index, kind in enumerate(kinds)}
        keys = sorted({key for template in catalog for key, _ in template.arguments})
        key_index = {key: index + 1 for index, key in enumerate(keys)}
        labels: dict[tuple[str, object], int] = {}
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
                label_key: tuple[str, object] | None = None
                if isinstance(value, bool):
                    number = float(value)
                elif isinstance(value, int):
                    number = math.log1p(abs(value)) * (1 if value >= 0 else -1)
                    label_key = (key, value)
                elif isinstance(value, str):
                    found = resolve(value, ARGUMENT_HINTS.get(key, ()))
                    if found is None:
                        label_key = (key, value)
                    else:
                        entity = self.entity_offsets[found[0]] + found[1]
                label = 0
                if label_key is not None:
                    label = labels.setdefault(label_key, len(labels) + 1)
                row_entity.append(entity)
                row_label.append(label)
                row_number.append(number)
            padding = width - len(row_key)
            arg_key.append(row_key + [0] * padding)
            arg_entity.append(row_entity + [self.entity_count] * padding)
            arg_label.append(row_label + [0] * padding)
            arg_number.append(row_number + [0.0] * padding)
        self.action_kinds = tuple(kinds)
        self.argument_keys = tuple(keys)
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
        return vectors

    def action_logits(self, hidden: Tensor, actions: Tensor) -> Tensor:
        """Unmasked logits ``[B, K]`` of the catalog indices ``actions``."""

        vectors = self.action_vectors(actions)
        logits: Tensor = self.query(hidden) @ vectors.T + self.action_bias[actions]
        return logits

    def _all_actions(self) -> Tensor:
        """Every catalog action's vector, cached while no gradient is taken."""

        everything = torch.arange(self.action_size)
        if torch.is_grad_enabled():
            return self.action_vectors(everything)
        key = tuple(int(parameter._version) for parameter in self.parameters()) + (
            id(self),
        )
        if self._cache_key != key or self._cache_value is None:
            self._cache_value = self.action_vectors(everything)
            self._cache_key = key
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
            "ruleset": self.config.identifier,
            "feature_digest": FEATURE_DIGEST,
        }
