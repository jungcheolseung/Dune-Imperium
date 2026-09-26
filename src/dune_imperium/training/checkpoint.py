"""Checkpoints that pin the observation and action-codec versions, and migrate.

A saved policy is only meaningful against the encoding it was trained on,
so every checkpoint records ``OBSERVATION_VERSION``, ``ACTION_CODEC_VERSION``,
the ruleset identifier (the catalog size differs between rulesets) and the
network shape. Format 1 refused any version mismatch. Format 2 (2026-09-18)
also stores what the versions stand for -- the action catalog as a list of
template identities (action id plus arguments) and the observation layout
as named segments -- so a checkpoint written under one version can be
**migrated** to the current one instead of being thrown away when a
catalog range or an observation segment changes: every policy-head row is
moved by template identity, every input column by (segment, offset),
templates or columns the current code no longer has are dropped, and new
ones start at zero (a zero input column leaves the network's outputs
untouched; a zero logit row makes the new action neither favoured nor
suppressed). The Adam moments move with them. What cannot be migrated
stays refused: a different hidden shape, and a format-1 checkpoint whose
versions no longer match (``stamp_checkpoint`` upgrades such a file while
the code that wrote it is still current).

Format 3 (2026-09-27) is format 2 plus the network architecture: an MLP
file is still written as format 2, byte for byte, and only another
architecture (``mlp_slots``) writes format 3 with an ``arch`` document and,
for ``mlp_slots``, the ``slot_keys`` its embedding rows stand for. A slot
file whose keys differ from the current table is refused (the rows would
silently mean other things). ``widen_checkpoint`` turns an MLP file into
an ``mlp_slots`` one computing the same function, Adam moments included.
"""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from dune_imperium.adapters.action_codec import (
    ACTION_CODEC_VERSION,
    ActionCodec,
    ActionTemplate,
)
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
)
from dune_imperium.config import RulesetConfig
from dune_imperium.training.network import (
    MlpSlotsNetwork,
    PolicyValueNetwork,
    build_network,
)
from dune_imperium.training.slots import SLOT_KEYS, SLOT_VERSION

# The format an MLP file is written in; other architectures write
# ARCH_CHECKPOINT_FORMAT.
CHECKPOINT_FORMAT = 2
ARCH_CHECKPOINT_FORMAT = 3
_READABLE_FORMATS = (1, 2, 3)
_SLOT_EMBEDDING = "slot_embed.weight"

type TemplateKey = tuple[str, tuple[tuple[str, bool | int | str], ...]]
type LayoutEntry = tuple[str, int, int]


@dataclass(frozen=True, slots=True)
class MigrationReport:
    """How a checkpoint was moved to the current encodings."""

    from_codec_version: int
    to_codec_version: int
    from_observation_version: int
    to_observation_version: int
    actions_kept: int
    actions_new: int
    actions_dropped: int
    observation_kept: int
    observation_new: int
    observation_dropped: int

    def describe(self) -> str:
        return (
            f"codec v{self.from_codec_version} -> v{self.to_codec_version}: "
            f"{self.actions_kept} actions kept, {self.actions_new} new, "
            f"{self.actions_dropped} dropped; observation "
            f"v{self.from_observation_version} -> v{self.to_observation_version}: "
            f"{self.observation_kept} columns kept, {self.observation_new} new, "
            f"{self.observation_dropped} dropped"
        )


@dataclass(frozen=True, slots=True)
class CheckpointInfo:
    """What a checkpoint file says about itself."""

    ruleset: str
    action_size: int
    hidden: tuple[int, ...]
    iteration: int
    metadata: Mapping[str, Any]
    # Optimizer state saved alongside the weights, if the writer had one.
    optimizer_state: dict[str, Any] | None = None
    format: int = CHECKPOINT_FORMAT
    action_codec_version: int = ACTION_CODEC_VERSION
    observation_version: int = OBSERVATION_VERSION
    # True when the file carries its template list and layout (format 2 with
    # a codec passed at save time, or a stamped file).
    migratable: bool = False
    # Set when the file was written under other versions and moved here.
    migration: MigrationReport | None = None
    # The network architecture's kind ("mlp" or "mlp_slots").
    arch: str = "mlp"


def template_keys(catalog: Sequence[ActionTemplate]) -> list[TemplateKey]:
    """Identity of every catalog template, in catalog order."""

    return [(template.action_id, template.arguments) for template in catalog]


def observation_layout() -> list[LayoutEntry]:
    """The current observation layout as (segment, offset, length) rows."""

    return [
        (segment.name, segment.offset, segment.length)
        for segment in OBSERVATION_SEGMENTS
    ]


def save_checkpoint(
    path: Path,
    network: PolicyValueNetwork,
    *,
    ruleset: str,
    iteration: int,
    metadata: Mapping[str, Any] | None = None,
    optimizer_state: Mapping[str, Any] | None = None,
    codec: ActionCodec | None = None,
) -> None:
    """Write the weights (and optionally optimizer state) with versions.

    Pass the ``codec`` the network was trained against to store its template
    identities; only then can the file be migrated across codec versions.
    """

    templates: list[TemplateKey] | None = None
    if codec is not None:
        if codec.size != network.action_size:
            raise ValueError(
                f"network action size {network.action_size} does not match the "
                f"codec catalog ({codec.size})"
            )
        if codec.config.identifier != ruleset:
            raise ValueError("the codec belongs to a different ruleset")
        templates = template_keys(codec.catalog)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "format": CHECKPOINT_FORMAT,
        "observation_version": OBSERVATION_VERSION,
        "observation_size": OBSERVATION_SIZE,
        "observation_layout": observation_layout(),
        "action_codec_version": ACTION_CODEC_VERSION,
        "action_templates": templates,
        "ruleset": ruleset,
        "action_size": network.action_size,
        "hidden": list(network.hidden),
        "iteration": iteration,
        "metadata": dict(metadata or {}),
        "state_dict": {
            key: value.detach().cpu() for key, value in network.state_dict().items()
        },
        "optimizer_state": (
            None if optimizer_state is None else _to_cpu(dict(optimizer_state))
        ),
    }
    arch = network.arch_spec()
    if arch["kind"] != "mlp":
        document["format"] = ARCH_CHECKPOINT_FORMAT
        document["arch"] = arch
        if arch["kind"] == "mlp_slots":
            document["slot_keys"] = list(SLOT_KEYS)
    _write(document, path)


def _write(document: Mapping[str, Any], path: Path) -> None:
    """Save through a sibling temporary file so a crash never leaves a torn file.

    ``latest.pt`` is rewritten every training iteration; a process killed
    mid-write would otherwise destroy the only resumable checkpoint.
    """

    temporary = path.with_name(path.name + ".tmp")
    torch.save(dict(document), temporary)
    os.replace(temporary, path)


def _to_cpu(value: Any) -> Any:
    """Move every tensor inside a nested optimizer state to the CPU."""

    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {key: _to_cpu(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_cpu(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_cpu(item) for item in value)
    return value


def _read(path: Path) -> dict[str, Any]:
    document = torch.load(path, map_location="cpu", weights_only=True)
    if document.get("format") not in _READABLE_FORMATS:
        raise ValueError(f"unsupported checkpoint format: {document.get('format')!r}")
    return dict(document)


def _document_arch(document: Mapping[str, Any]) -> dict[str, Any]:
    """The file's architecture, refusing a slot table that is not current."""

    hidden = [int(width) for width in document["hidden"]]
    arch = document.get("arch")
    if arch is None:
        return {"kind": "mlp", "hidden": hidden}
    arch = dict(arch)
    if [int(width) for width in arch.get("hidden", ())] != hidden:
        raise ValueError("checkpoint architecture does not match its hidden shape")
    if arch.get("kind") == "mlp_slots":
        if arch.get("slot_version") != SLOT_VERSION:
            raise ValueError(
                f"checkpoint slot table v{arch.get('slot_version')} does not match "
                f"the current v{SLOT_VERSION}"
            )
        if list(document.get("slot_keys") or ()) != list(SLOT_KEYS):
            raise ValueError(
                "checkpoint slot keys differ from the current slot table "
                "(training/slots.py); its embedding rows cannot be read by name yet"
            )
    return arch


def _format_for(arch: Mapping[str, Any]) -> int:
    return CHECKPOINT_FORMAT if arch["kind"] == "mlp" else ARCH_CHECKPOINT_FORMAT


def _versions_match(document: Mapping[str, Any]) -> bool:
    return bool(
        document["observation_version"] == OBSERVATION_VERSION
        and document["action_codec_version"] == ACTION_CODEC_VERSION
        and document["observation_size"] == OBSERVATION_SIZE
    )


def load_checkpoint(path: Path) -> tuple[PolicyValueNetwork, CheckpointInfo]:
    """Rebuild the network on the CPU, migrating it to the current encodings.

    A file written under the current versions loads as is. One written under
    other versions is migrated when it carries its template list and
    layout, and refused otherwise.
    """

    document = _read(path)
    arch = _document_arch(document)
    migration: MigrationReport | None = None
    state_dict = dict(document["state_dict"])
    optimizer_state = document.get("optimizer_state")
    hidden = tuple(int(width) for width in document["hidden"])
    if _versions_match(document):
        action_size = int(document["action_size"])
    else:
        templates = document.get("action_templates")
        layout = document.get("observation_layout")
        if templates is None or layout is None:
            raise ValueError(
                f"checkpoint codec v{document['action_codec_version']} / observation "
                f"v{document['observation_version']} does not match the current "
                f"v{ACTION_CODEC_VERSION} / v{OBSERVATION_VERSION}, and the file "
                "carries no template list to migrate by (stamp it with the code "
                "that wrote it: dune-imperium-checkpoint stamp)"
            )
        codec = ActionCodec(RulesetConfig.from_identifier(str(document["ruleset"])))
        state_dict, optimizer_state, migration = _migrate(
            document, state_dict, optimizer_state, codec, hidden
        )
        action_size = codec.size
    # Migration moves the head rows and first-layer columns only; the slot
    # embedding is keyed by SLOT_KEYS (checked above) and passes through.
    network = build_network(arch, action_size)
    network.load_state_dict(state_dict)
    network.eval()
    info = CheckpointInfo(
        ruleset=str(document["ruleset"]),
        action_size=network.action_size,
        hidden=network.hidden,
        iteration=int(document["iteration"]),
        metadata=dict(document.get("metadata", {})),
        optimizer_state=optimizer_state,
        format=int(document["format"]),
        action_codec_version=int(document["action_codec_version"]),
        observation_version=int(document["observation_version"]),
        migratable=document.get("action_templates") is not None
        and document.get("observation_layout") is not None,
        migration=migration,
        arch=str(arch["kind"]),
    )
    return network, info


def _key(entry: Sequence[Any]) -> TemplateKey:
    action_id, arguments = entry
    return (str(action_id), tuple((str(name), value) for name, value in arguments))


def _migrate(
    document: Mapping[str, Any],
    state_dict: dict[str, torch.Tensor],
    optimizer_state: dict[str, Any] | None,
    codec: ActionCodec,
    hidden: tuple[int, ...],
) -> tuple[dict[str, torch.Tensor], dict[str, Any] | None, MigrationReport]:
    """Move rows and columns by identity; zero what is new; drop what is gone."""

    old_index = {
        _key(entry): index for index, entry in enumerate(document["action_templates"])
    }
    if len(old_index) != int(document["action_size"]):
        raise ValueError("checkpoint template list does not match its action size")
    # Policy-head row for each current template: the old row, or -1 for new.
    action_source = torch.tensor(
        [old_index.get((t.action_id, t.arguments), -1) for t in codec.catalog],
        dtype=torch.long,
    )
    old_columns = {
        str(name): (int(offset), int(length))
        for name, offset, length in document["observation_layout"]
    }
    column_source = torch.full((OBSERVATION_SIZE,), -1, dtype=torch.long)
    for segment in OBSERVATION_SEGMENTS:
        if segment.name not in old_columns:
            continue
        offset, length = old_columns[segment.name]
        shared = min(length, segment.length)
        column_source[segment.offset : segment.offset + shared] = torch.arange(
            offset, offset + shared
        )
    old_observation_size = int(document["observation_size"])
    if sum(length for _, length in old_columns.values()) != old_observation_size:
        raise ValueError("checkpoint layout does not match its observation size")

    first_weight = "body.0.weight"
    policy_weight, policy_bias = "policy_head.weight", "policy_head.bias"
    migrated = dict(state_dict)
    migrated[first_weight] = _gather_columns(state_dict[first_weight], column_source)
    migrated[policy_weight] = _gather_rows(state_dict[policy_weight], action_source)
    migrated[policy_bias] = _gather_rows(state_dict[policy_bias], action_source)

    if optimizer_state is not None:
        optimizer_state = _migrate_optimizer(
            optimizer_state, hidden, column_source, action_source
        )
    kept_actions = int((action_source >= 0).sum())
    kept_columns = int((column_source >= 0).sum())
    report = MigrationReport(
        from_codec_version=int(document["action_codec_version"]),
        to_codec_version=ACTION_CODEC_VERSION,
        from_observation_version=int(document["observation_version"]),
        to_observation_version=OBSERVATION_VERSION,
        actions_kept=kept_actions,
        actions_new=codec.size - kept_actions,
        actions_dropped=len(old_index) - kept_actions,
        observation_kept=kept_columns,
        observation_new=OBSERVATION_SIZE - kept_columns,
        observation_dropped=old_observation_size - kept_columns,
    )
    return migrated, optimizer_state, report


def _gather_rows(tensor: torch.Tensor, source: torch.Tensor) -> torch.Tensor:
    """Rows of ``tensor`` in ``source`` order; a source of -1 gives zeros."""

    result = torch.zeros((source.shape[0], *tensor.shape[1:]), dtype=tensor.dtype)
    present = source >= 0
    result[present] = tensor[source[present]]
    return result


def _gather_columns(tensor: torch.Tensor, source: torch.Tensor) -> torch.Tensor:
    """Columns (dimension 1) of ``tensor`` in ``source`` order; -1 gives zeros."""

    result = torch.zeros((tensor.shape[0], source.shape[0]), dtype=tensor.dtype)
    present = source >= 0
    result[:, present] = tensor[:, source[present]]
    return result


def _migrate_optimizer(
    optimizer_state: dict[str, Any],
    hidden: tuple[int, ...],
    column_source: torch.Tensor,
    action_source: torch.Tensor,
) -> dict[str, Any]:
    """Move the Adam moments of the resized parameters the same way.

    Parameters are numbered in ``PolicyValueNetwork.parameters()`` order:
    ``body.0.weight`` first, then the rest of the body, then
    ``policy_head.weight``, ``policy_head.bias``, ``value_head.weight``,
    ``value_head.bias`` (and, for ``mlp_slots``, ``slot_embed.weight``,
    which keeps its shape and moments). A moment whose shape does not fit its parameter
    afterwards is dropped so Adam simply restarts it.
    """

    body_parameters = 2 * len(hidden)
    resized = {
        0: ("columns", column_source),
        body_parameters: ("rows", action_source),
        body_parameters + 1: ("rows", action_source),
    }
    state = {}
    for raw_index, moments in dict(optimizer_state.get("state", {})).items():
        index = int(raw_index)
        moved = dict(moments)
        if index in resized:
            axis, source = resized[index]
            for name in ("exp_avg", "exp_avg_sq", "max_exp_avg_sq"):
                tensor = moved.get(name)
                if not isinstance(tensor, torch.Tensor):
                    continue
                moved[name] = (
                    _gather_columns(tensor, source)
                    if axis == "columns"
                    else _gather_rows(tensor, source)
                )
        state[raw_index] = moved
    return {**optimizer_state, "state": state}


def stamp_checkpoint(path: Path) -> CheckpointInfo:
    """Rewrite a checkpoint in the current format with its template list.

    Only a file whose versions match the running code can be stamped: the
    template list written is the one this code builds for the file's
    ruleset, which is exactly the catalog the file was trained against.
    """

    document = _read(path)
    arch = _document_arch(document)
    if not _versions_match(document):
        raise ValueError(
            "only a checkpoint written under the current codec and observation "
            "versions can be stamped; migrate it with the code that wrote it first"
        )
    codec = ActionCodec(RulesetConfig.from_identifier(str(document["ruleset"])))
    if codec.size != int(document["action_size"]):
        raise ValueError(
            f"checkpoint action size {document['action_size']} does not match the "
            f"{document['ruleset']} catalog ({codec.size})"
        )
    # Never a downgrade: an architecture file stays format 3 with its arch.
    document["format"] = _format_for(arch)
    document["action_templates"] = template_keys(codec.catalog)
    document["observation_layout"] = observation_layout()
    _write(document, path)
    _, info = load_checkpoint(path)
    return info


def widen_checkpoint(
    source: Path, destination: Path, *, arch: str = "mlp_slots"
) -> CheckpointInfo:
    """Write ``source`` (an MLP) as an ``mlp_slots`` file computing the same function.

    The file is loaded (and migrated) like any other, its weights go into a
    ``MlpSlotsNetwork`` whose zero embedding leaves every output unchanged,
    and the Adam state gains the embedding as one more parameter with no
    moments yet (Adam starts them on its first step). The iteration number
    is kept, so a widened run replays the same game seeds as its source.
    When the source was written under older encodings, the migration done on
    load is recorded as ``metadata["widened_migration"]`` (the widened file
    itself is at the current versions, so its own ``migration`` is None).
    """

    if arch != "mlp_slots":
        raise ValueError(f"cannot widen to architecture {arch!r}")
    network, info = load_checkpoint(source)
    if info.arch != "mlp":
        raise ValueError(f"{source} is already a {info.arch} checkpoint")
    widened = MlpSlotsNetwork(info.action_size, hidden=info.hidden)
    result = widened.load_state_dict(network.state_dict(), strict=False)
    if list(result.missing_keys) != [_SLOT_EMBEDDING] or result.unexpected_keys:
        raise RuntimeError(
            f"widening expected only {_SLOT_EMBEDDING} to be new, got missing "
            f"{result.missing_keys} and unexpected {result.unexpected_keys}"
        )
    widened.eval()
    optimizer_state = info.optimizer_state
    if optimizer_state is not None:
        optimizer_state = _widen_optimizer(optimizer_state, info.hidden)
    config = RulesetConfig.from_identifier(info.ruleset)
    metadata: dict[str, Any] = {
        **info.metadata,
        "arch": widened.arch_spec(),
        "widened_from": str(source),
    }
    if info.migration is not None:
        metadata["widened_migration"] = info.migration.describe()
    save_checkpoint(
        destination,
        widened,
        ruleset=info.ruleset,
        iteration=info.iteration,
        metadata=metadata,
        optimizer_state=optimizer_state,
        codec=ActionCodec(config),
    )
    _, widened_info = load_checkpoint(destination)
    return widened_info


def _widen_optimizer(
    optimizer_state: Mapping[str, Any], hidden: tuple[int, ...]
) -> dict[str, Any]:
    """Append the embedding's parameter index to Adam's only group, stateless."""

    new_index = 2 * len(hidden) + 4
    groups = list(optimizer_state.get("param_groups", ()))
    if len(groups) != 1:
        raise ValueError("widening expects an optimizer with one parameter group")
    params = [int(index) for index in groups[0]["params"]]
    if params != list(range(new_index)):
        raise ValueError(
            f"widening expects MLP optimizer parameters 0..{new_index - 1}, "
            f"got {params}"
        )
    if any(int(index) >= new_index for index in optimizer_state.get("state", {})):
        raise ValueError("optimizer state already holds a parameter past the MLP")
    return {
        **optimizer_state,
        "param_groups": [{**groups[0], "params": [*params, new_index]}],
    }


__all__ = [
    "ARCH_CHECKPOINT_FORMAT",
    "CHECKPOINT_FORMAT",
    "CheckpointInfo",
    "MigrationReport",
    "load_checkpoint",
    "observation_layout",
    "save_checkpoint",
    "stamp_checkpoint",
    "template_keys",
    "widen_checkpoint",
]
