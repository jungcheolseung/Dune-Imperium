"""Enums shared by Uprising card manifests."""

from enum import IntEnum, StrEnum


class BattleIcon(StrEnum):
    """Icons paired by Objective and won Conflict cards."""

    CRYSKNIFE = "crysknife"
    DESERT_MOUSE = "desert_mouse"
    ORNITHOPTER = "ornithopter"


class ConflictTier(IntEnum):
    """The three Conflict deck backs."""

    ONE = 1
    TWO = 2
    THREE = 3
