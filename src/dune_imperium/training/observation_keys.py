"""Exact short keys of observations (2026-11-11 engine speed, seat stage).

A search seat keys two things by a playout step's observation: the trunk a
network read of it (``TrunkCache``) and the moves already made at that
decision (``_Taken``, the cycle guard). Both keyed it by the int32 array's
``tobytes()``: 42.7 KB an observation, copied and hashed (about 23 us)
twice a playout step, and kept as keys (a decision's 4,096 trunk keys at
most: 175 MB). Every value of an observation fits a byte, its counts and
flags, so the encoder writes the same values as 10.7 KB of bytes
(``encode_player_view_bytes``), and the array is those bytes widened.

``bytes_key`` maps a byte string one-to-one to a short key: bytes that read
as native int32 values all within 0..255 become those values as one byte
each, any other bytes stay themselves, and each key is tagged with its
form. Two byte strings have equal keys exactly when they are equal, so a
table keyed by ``bytes_key(array.tobytes())`` tells observations apart
exactly as one keyed by ``array.tobytes()``: the same hits and misses, the
same trunks, the same moves.

``EncodedObservation`` is a view's encoding as ``encoded_view`` builds it,
kept as the encoder's bytes when it has them. Its key is then those bytes
(the very key ``bytes_key`` gives the widened array's bytes), and the int32
array is built only when a network reads it: on a trunk-cache miss, and
straight into the rows of the batch (``stacked``).
"""

from collections.abc import Sequence
from typing import Final

import numpy as np

from dune_imperium.adapters.observation_encoding import (
    encode_player_view,
    encode_player_view_bytes,
)
from dune_imperium.core.observation import PlayerView

_INT32: Final = np.dtype(np.int32)
_UINT8: Final = np.dtype(np.uint8)

# A key's form: int32 values that fit a byte, held one byte each; or the
# bytes themselves.
PACKED: Final = "int32 values as bytes"
RAW: Final = "bytes"

type BytesKey = tuple[str, bytes]


def bytes_key(raw: bytes) -> BytesKey:
    """A key of ``raw``, equal to another's exactly when the bytes are."""

    if len(raw) % _INT32.itemsize == 0:
        values = np.frombuffer(raw, dtype=_INT32)
        if not values.size or (int(values.min()) >= 0 and int(values.max()) <= 255):
            return PACKED, values.astype(_UINT8).tobytes()
    return RAW, raw


class EncodedObservation:
    """A view's observation encoding, an int32 array as ``encoded_view``
    builds it, with its key (``bytes_key`` of the array's bytes)."""

    __slots__ = ("_array", "_dtype", "_key", "packed")

    def __init__(self, packed: bytes | None, array: np.ndarray | None) -> None:
        # Exactly one of the two: use ``of_bytes`` or ``of_array``.
        self.packed = packed
        self._array = array
        self._key: BytesKey | None = None if packed is None else (PACKED, packed)
        self._dtype: str | None = None if packed is None else _INT32.str

    @classmethod
    def of_bytes(cls, packed: bytes) -> EncodedObservation:
        """The observation whose int32 values are ``packed``'s bytes."""

        return cls(packed, None)

    @classmethod
    def of_array(cls, array: np.ndarray) -> EncodedObservation:
        """The observation ``array`` (handed back as it is)."""

        return cls(None, array)

    def array(self) -> np.ndarray:
        """The observation as ``encoded_view`` returns it: from bytes, a new
        int32 array each time; else the array it was made of."""

        if self.packed is not None:
            return np.frombuffer(self.packed, dtype=np.uint8).astype(np.int32)
        assert self._array is not None
        return self._array

    def key(self) -> BytesKey:
        """``bytes_key`` of the array's bytes."""

        if self._key is None:
            assert self._array is not None
            self._key = bytes_key(self._array.tobytes())
        return self._key

    def dtype(self) -> str:
        """The array's ``dtype.str``."""

        if self._dtype is None:
            assert self._array is not None
            self._dtype = self._array.dtype.str
        return self._dtype


def encoded_observation(view: PlayerView) -> EncodedObservation:
    """``encoded_view(view)``, kept as bytes when its values fit a byte.

    The same steps as ``encoded_view``: the encoder's bytes when it writes
    them, else the encoding's tuple as bytes, else NumPy's conversion of the
    tuple (a value outside a byte), so each raises what it raised there.
    """

    packed_now = encode_player_view_bytes(view)
    if packed_now is not None:
        return EncodedObservation.of_bytes(bytes(packed_now))
    values = encode_player_view(view)
    try:
        packed = bytes(values)
    except (TypeError, ValueError):
        return EncodedObservation.of_array(np.asarray(values, dtype=np.int32))
    return EncodedObservation.of_bytes(packed)


def stacked(observations: Sequence[EncodedObservation]) -> np.ndarray:
    """``np.stack`` of the observations' arrays, ``[B, N]`` int32: widened
    from their bytes in one pass when every one is held as bytes of one
    length (half the time of widening each and stacking the copies)."""

    packed: list[bytes] = []
    for observation in observations:
        if observation.packed is None:
            break
        packed.append(observation.packed)
    else:
        if packed and len({len(data) for data in packed}) == 1:
            joined = np.frombuffer(b"".join(packed), dtype=np.uint8)
            return joined.reshape(len(packed), len(packed[0])).astype(np.int32)
    return np.stack([observation.array() for observation in observations])
