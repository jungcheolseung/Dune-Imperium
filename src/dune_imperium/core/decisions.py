"""Serializable decision points and nested decision frames."""

from copy import replace
from dataclasses import dataclass
from operator import itemgetter
from typing import Final

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.dataclass_copy import (
    positional_dataclass_replace,
    slot_initializer,
)


@slot_initializer
@dataclass(frozen=True, slots=True)
class PlayerDecision:
    """A decision that must be answered by one player."""

    owner: int
    prompt: str

    def __post_init__(self) -> None:
        if self.owner < 0:
            raise ValueError("decision owner must not be negative")
        if not self.prompt:
            raise ValueError("decision prompt must not be empty")


@slot_initializer
@dataclass(frozen=True, slots=True)
class ChanceDecision:
    """A uniform sample resolved by a chance stream.

    Options are stable instance IDs rather than hidden Python object references.
    An ordered sample without replacement also represents a shuffle.
    """

    decision_id: str
    prompt: str
    options: tuple[str, ...]
    count: int = 1
    with_replacement: bool = False

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("chance decision_id must not be empty")
        if not self.prompt:
            raise ValueError("decision prompt must not be empty")
        if not self.options:
            raise ValueError("chance decision options must not be empty")
        if len(self.options) != len(set(self.options)):
            raise ValueError("chance decision options must be unique")
        if self.count < 1:
            raise ValueError("chance decision count must be positive")
        if not self.with_replacement and self.count > len(self.options):
            raise ValueError("chance decision count exceeds available options")


type Decision = PlayerDecision | ChanceDecision


# Copied with ``copy.replace`` whenever a frame's context changes
# (``rules.frames.with_context``): the compiled copy skips dataclasses'
# metadata walk.
@positional_dataclass_replace
@slot_initializer
@dataclass(frozen=True, slots=True)
class DecisionFrame:
    """One resumable frame in a nested decision stack.

    ``kind`` names the rule boundary that owns the frame so dispatch never has
    to parse ``frame_id``. ``frame_id`` stays a unique, human-readable label.
    """

    kind: str
    frame_id: str
    decision: Decision
    context: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("frame kind must not be empty")
        if not self.frame_id:
            raise ValueError("frame_id must not be empty")

        keys = tuple(key for key, _ in self.context)
        if len(keys) != len(set(keys)):
            raise ValueError("decision context names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("decision context must be sorted by name")


_FRAME_SLOTS = tuple(
    vars(DecisionFrame)[name].__set__
    for name in ("kind", "frame_id", "decision", "context")
)


def frame_with_dict_context(
    frame: DecisionFrame, context: dict[str, ActionValue]
) -> DecisionFrame:
    """``frame`` carrying ``context``'s items in sorted order, as
    ``copy.replace(frame, context=tuple(sorted(context.items())))`` builds it.

    The copy runs ``__post_init__``'s checks of the kind and the id as the
    constructor would, and skips only its two context checks, which a dict
    with ``str`` names passes by construction: its names are unique and its
    items sort by name, a total order. The copy is written straight into its
    slots (2026-11-11 engine speed, stage B: frames are rebuilt this way
    about 340,000 times a search seat's game). Only an exact
    ``DecisionFrame`` and an exact ``dict`` whose every name is an exact
    ``str`` take this path; anything else is copied through the constructor
    (Codex review r1-r2).
    """

    items = tuple(sorted(context.items()))
    if (
        type(frame) is not DecisionFrame
        or type(context) is not dict
        # The names of the items captured (Codex review r4: a name's own
        # comparison could have changed the dict while it was sorted).
        or not {*map(type, map(_name_of, items))} <= _STR_NAMES
    ):
        return replace(frame, context=items)
    if not frame.kind:
        raise ValueError("frame kind must not be empty")
    if not frame.frame_id:
        raise ValueError("frame_id must not be empty")
    copy = object.__new__(DecisionFrame)
    set_kind, set_frame_id, set_decision, set_context = _FRAME_SLOTS
    set_kind(copy, frame.kind)
    set_frame_id(copy, frame.frame_id)
    set_decision(copy, frame.decision)
    set_context(copy, items)
    return copy


_STR_NAMES: Final = frozenset({str})
_name_of: Final = itemgetter(0)
