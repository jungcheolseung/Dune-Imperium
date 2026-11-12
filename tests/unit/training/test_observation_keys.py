"""Exact short observation keys (2026-11-11 engine speed, seat stage).

The search seat keys its trunk cache and its cycle guard by
``observation_keys.bytes_key`` instead of the int32 array's bytes, and keeps
a playout step's view as the encoder's bytes until a network reads it. None
of it may change what a seat reads or plays: a key must be equal exactly
when the bytes were, an array the same as ``encoded_view``'s, a batch the
same as ``np.stack``'s, and the cache and the guard must answer every call
as master's did (the reference copies below).
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from itertools import combinations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from tests.unit.training.test_trunk_cache import _EVERYTHING, _views  # noqa: E402
from torch import Tensor  # noqa: E402

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    _DecisionKey,
    _Taken,
)
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.training import observation_keys, policy, trunk_cache  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.observation_keys import (  # noqa: E402
    PACKED,
    RAW,
    EncodedObservation,
    bytes_key,
    encoded_observation,
    stacked,
)
from dune_imperium.training.policy import encoded_view  # noqa: E402
from dune_imperium.training.trunk_cache import TrunkCache  # noqa: E402


def _byte_strings() -> list[bytes]:
    """Bytes of int32 arrays in and out of a byte's range, of other dtypes
    with the same bytes, of other lengths, and empty."""

    ints = [
        np.array(values, dtype=np.int32)
        for values in (
            [0, 1, 2, 255],
            [0, 1, 2, 254],
            [0, 1, 2, 256],
            [0, -1, 2, 255],
            [255, 255, 255, 255],
            [1 << 24, 0, 0, 0],
            [7],
            [],
        )
    ]
    strings = [array.tobytes() for array in ints]
    strings += [array.view(np.float32).tobytes() for array in ints]
    strings += [array.astype(np.uint8).tobytes() for array in ints]
    strings += [b"\x01", b"\x01\x00\x00", b"\x01\x00\x00\x00\x00", b"\xff" * 8]
    strings += [np.array([3.5, -0.0], dtype=np.float32).tobytes()]
    return strings


def test_two_byte_strings_have_equal_keys_exactly_when_they_are_equal() -> None:
    strings = _byte_strings()
    for first, second in combinations(strings + strings, 2):
        assert (bytes_key(first) == bytes_key(second)) is (first == second)
        assert bytes_key(first) == bytes_key(bytes(first))


def test_int32_values_within_a_byte_are_kept_as_one_byte_each() -> None:
    array = np.array([0, 9, 255, 3], dtype=np.int32)
    assert bytes_key(array.tobytes()) == (PACKED, bytes([0, 9, 255, 3]))
    assert bytes_key(b"") == (PACKED, b"")
    for raw in (
        np.array([0, 256], dtype=np.int32).tobytes(),
        np.array([-1], dtype=np.int32).tobytes(),
        b"\x01\x00\x00",
    ):
        assert bytes_key(raw) == (RAW, raw)


@pytest.mark.parametrize("config", [RulesetConfig(), _EVERYTHING])
def test_an_encoded_observation_is_encoded_view_s_array(config: RulesetConfig) -> None:
    for view in _views(config, seed=4, decisions=40):
        expected = encoded_view(view)
        observed = encoded_observation(view)
        assert observed.packed is not None
        for array in (observed.array(), observed.array()):
            assert array.dtype == expected.dtype and array.shape == expected.shape
            assert array.strides == expected.strides
            assert array.flags.c_contiguous and array.flags.writeable
            assert array.flags.owndata == expected.flags.owndata
            assert array.tobytes() == expected.tobytes()
        assert observed.array() is not observed.array()
        assert observed.key() == bytes_key(expected.tobytes())
        assert observed.dtype() == expected.dtype.str


@pytest.mark.parametrize(
    "values",
    [(1, 300, 0), (2, -1, 7), (0, 255, 1), (1, 2.0, 3), (True, 4, 5), (2**31, 1)],
)
def test_without_the_encoder_s_bytes_it_takes_encoded_view_s_steps(
    monkeypatch: pytest.MonkeyPatch, values: tuple[object, ...]
) -> None:
    view = _views(RulesetConfig(), seed=4, decisions=1)[0]
    for module in (policy, observation_keys):
        monkeypatch.setattr(module, "encode_player_view_bytes", lambda _: None)
        monkeypatch.setattr(module, "encode_player_view", lambda _, v=values: v)
    try:
        expected = encoded_view(view)
    except Exception as error:  # noqa: BLE001 - the same must be raised
        with pytest.raises(type(error), match=str(error)):
            encoded_observation(view)
        return
    observed = encoded_observation(view)
    array = observed.array()
    assert array.dtype == expected.dtype and array.shape == expected.shape
    assert array.tobytes() == expected.tobytes()
    assert observed.key() == bytes_key(expected.tobytes())
    assert observed.dtype() == expected.dtype.str


def test_an_encoder_failure_raises_as_encoded_view_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _views(RulesetConfig(), seed=4, decisions=1)[0]

    def broken(_: PlayerView) -> tuple[int, ...]:
        raise ValueError("the observation encoding requires the private view")

    for module in (policy, observation_keys):
        monkeypatch.setattr(module, "encode_player_view_bytes", lambda _: None)
        monkeypatch.setattr(module, "encode_player_view", broken)
    for build in (encoded_view, encoded_observation):
        with pytest.raises(ValueError, match="requires the private view"):
            build(view)


def _same_array(first: np.ndarray, second: np.ndarray) -> None:
    assert first.dtype == second.dtype and first.shape == second.shape
    assert first.strides == second.strides
    assert first.flags.c_contiguous == second.flags.c_contiguous
    assert first.flags.writeable == second.flags.writeable
    assert first.tobytes() == second.tobytes()


def test_a_stack_of_encoded_observations_is_numpy_s_stack() -> None:
    views = _views(_EVERYTHING, seed=4, decisions=3)
    observed = [encoded_observation(view) for view in views]
    arrays = [encoded_view(view) for view in views]
    _same_array(stacked(observed), np.stack(arrays))
    _same_array(stacked(observed[:1]), np.stack(arrays[:1]))
    # Held as an array, an observation is stacked as it is.
    mixed = [observed[0], EncodedObservation.of_array(arrays[1]), observed[2]]
    _same_array(stacked(mixed), np.stack(arrays[:3]))
    wide = EncodedObservation.of_array(np.array([1, 300], dtype=np.int32))
    narrow = EncodedObservation.of_array(np.array([1, 3], dtype=np.int32))
    _same_array(stacked([wide, narrow]), np.stack([wide.array(), narrow.array()]))
    # What NumPy refuses is refused alike.
    short = EncodedObservation.of_bytes(b"\x01\x02")
    for refused in ([], [observed[0], short], [observed[0], narrow]):
        with pytest.raises(ValueError):
            np.stack([observation.array() for observation in refused])
        with pytest.raises(ValueError):
            stacked(refused)


class _MasterTrunkCache:
    """``TrunkCache`` as master 7bd1effb wrote it (keys: the bytes)."""

    def __init__(self) -> None:
        self._hidden: dict[tuple[int, str, bytes], Tensor] = {}
        self._depth = 0
        self.hits = 0
        self.misses = 0

    @contextmanager
    def decision(self) -> Iterator[None]:
        if not self._depth:
            self._hidden.clear()
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            if not self._depth:
                self._hidden.clear()

    def hidden(self, network: PolicyValueNetwork, observation: np.ndarray) -> Tensor:
        if not self._depth:
            with torch.no_grad():
                return network.trunk(torch.from_numpy(observation).unsqueeze(0))
        key = (id(network), observation.dtype.str, observation.tobytes())
        found = self._hidden.get(key)
        if found is not None:
            self.hits += 1
            return found
        self.misses += 1
        with torch.no_grad():
            found = network.trunk(torch.from_numpy(observation).unsqueeze(0))
        if len(self._hidden) < trunk_cache.LIMIT:
            self._hidden[key] = found
        return found

    def hidden_batch(
        self, network: PolicyValueNetwork, observations: Sequence[np.ndarray]
    ) -> Tensor:
        rows: list[Tensor | None] = []
        missing: dict[tuple[int, str, bytes], list[int]] = {}
        for position, observation in enumerate(observations):
            key = (id(network), observation.dtype.str, observation.tobytes())
            found = self._hidden.get(key) if self._depth else None
            if found is not None:
                self.hits += 1
            else:
                missing.setdefault(key, []).append(position)
            rows.append(found)
        if missing:
            first = [positions[0] for positions in missing.values()]
            stacked_rows = torch.from_numpy(np.stack([observations[i] for i in first]))
            with torch.no_grad():
                computed = network.trunk(stacked_rows)
            for index, (key, positions) in enumerate(missing.items()):
                row = computed[index : index + 1]
                if self._depth:
                    self.misses += 1
                    if len(self._hidden) < trunk_cache.LIMIT:
                        self._hidden[key] = row
                for position in positions:
                    rows[position] = row
        filled = [row for row in rows if row is not None]
        joined: Tensor = torch.cat(filled)
        return joined


def _network(seed: int) -> PolicyValueNetwork:
    torch.manual_seed(seed)
    return PolicyValueNetwork(ActionCodec(RulesetConfig()).size, hidden=(16,))


@pytest.mark.parametrize("limit", [4096, 3])
def test_the_trunk_cache_answers_every_call_as_master_s_did(
    monkeypatch: pytest.MonkeyPatch, limit: int
) -> None:
    """The same calls, master's cache given arrays and the new one the same
    observations as arrays or encoded, alike: the same tensors (bit for
    bit), the same ones handed back again, the same hits and misses; also
    once the decision has kept ``LIMIT`` trunks (read afresh after that)."""

    monkeypatch.setattr(trunk_cache, "LIMIT", limit)

    views = _views(RulesetConfig(), seed=4, decisions=4)
    arrays = [encoded_view(view) for view in views][:6]
    arrays.append(arrays[0].view(np.float32))  # the same bytes, another dtype
    arrays.append(np.array([1, 300] * (arrays[0].size // 2), dtype=np.int32))
    networks = [_network(0), _network(1)]
    plan: list[tuple[str, int, list[int]]] = [
        ("one", 0, [0]),
        ("batch", 0, [1, 0, 2, 1]),
        ("one", 1, [0]),
        ("batch", 1, [0, 3, 3]),
        ("one", 0, [2]),
        ("batch", 0, [4, 5, 0, 6, 7]),
        ("one", 0, [6]),
        ("one", 0, [7]),
        ("batch", 0, [7, 6, 5, 4]),
    ]

    for decision in (False, True):
        master = _MasterTrunkCache()
        reference: list[list[Tensor]] = []
        mine = TrunkCache()
        answers: list[list[Tensor]] = []
        with master.decision() if decision else _nothing():
            for kind, net, indices in plan:
                network = networks[net]
                if kind == "one":
                    reference.append([master.hidden(network, arrays[indices[0]])])
                else:
                    batch = master.hidden_batch(network, [arrays[i] for i in indices])
                    reference.append([batch[i : i + 1] for i in range(len(indices))])
        with mine.decision() if decision else _nothing():
            for step, (kind, net, indices) in enumerate(plan):
                network = networks[net]
                # Alternate the forms: an array, the encoder's bytes.
                forms = [_form(arrays[i], step + n) for n, i in enumerate(indices)]
                if kind == "one":
                    form = forms[0]
                    if isinstance(form, np.ndarray):
                        answers.append([mine.hidden(network, form)])
                    else:
                        answers.append([mine.hidden_of(network, form)])
                else:
                    if step % 2:
                        batch = mine.hidden_batch_of(
                            network,
                            [
                                f
                                if isinstance(f, EncodedObservation)
                                else EncodedObservation.of_array(f)
                                for f in forms
                            ],
                        )
                    else:
                        batch = mine.hidden_batch(network, [arrays[i] for i in indices])
                    answers.append([batch[i : i + 1] for i in range(len(indices))])
            assert (mine.hits, mine.misses) == (master.hits, master.misses)
        flat_reference = [t for row in reference for t in row]
        flat_answers = [t for row in answers for t in row]
        for got, want in zip(flat_answers, flat_reference, strict=True):
            assert torch.equal(got, want)
        assert (mine.hits, mine.misses) == (master.hits, master.misses)


@contextmanager
def _nothing() -> Iterator[None]:
    yield


def _form(array: np.ndarray, turn: int) -> np.ndarray | EncodedObservation:
    """``array``, or (every other turn, when it has them) its bytes."""

    if turn % 2 and array.dtype == np.int32 and array.min() >= 0 and array.max() <= 255:
        return EncodedObservation.of_bytes(array.astype(np.uint8).tobytes())
    return array


class _MasterTaken:
    """``_Taken`` as master 7bd1effb wrote it (keys: the bytes)."""

    def __init__(self) -> None:
        self._round = -1
        self._taken: dict[tuple[object, ...], set[DomainAction]] = {}
        self.breaks = 0

    def untried(
        self,
        round_number: int,
        seat: int,
        encoded: np.ndarray,
        offered: Sequence[DomainAction],
    ) -> tuple[tuple[object, ...], Sequence[DomainAction]]:
        if round_number != self._round:
            self._round = round_number
            self._taken.clear()
        key = (seat, encoded.tobytes(), tuple(offered))
        taken = self._taken.get(key)
        if not taken:
            return key, offered
        fresh = [action for action in offered if action not in taken]
        if not fresh:
            return key, offered
        self.breaks += 1
        return key, fresh

    def record(self, key: tuple[object, ...], action: DomainAction) -> None:
        self._taken.setdefault(key, set()).add(action)


def test_the_cycle_guard_answers_every_call_as_master_s_did() -> None:
    views = _views(RulesetConfig(), seed=4, decisions=2)
    arrays = [encoded_view(view) for view in views[:3]]
    arrays.append(arrays[0].view(np.float32))  # the same bytes
    arrays.append(np.array([5, 300, 1], dtype=np.int32))
    # Values that fit a byte, each one a byte of the array above: its key's
    # bytes are that array's bytes, told apart only by the key's form.
    arrays.append(np.frombuffer(arrays[-1].tobytes(), dtype=np.uint8).astype(np.int32))
    moves = [DomainAction(name, seat) for name in "xyz" for seat in (0, 1)]
    offers = [tuple(moves[:3]), tuple(moves[1:4]), tuple(moves[3:5])]
    rng = np.random.default_rng(7)
    master, mine = _MasterTaken(), _Taken()
    for step in range(600):
        round_number = int(rng.integers(1, 3)) + step // 200
        seat = int(rng.integers(0, 2))
        observation = arrays[int(rng.integers(0, len(arrays)))]
        offered = offers[int(rng.integers(0, len(offers)))]
        given: np.ndarray | EncodedObservation = observation
        if step % 2 and observation.dtype == np.int32 and observation.max() <= 255:
            given = EncodedObservation.of_bytes(observation.astype(np.uint8).tobytes())
        want_key, want = master.untried(round_number, seat, observation, offered)
        got_key, got = mine.untried(round_number, seat, given, offered)
        assert tuple(got) == tuple(want) and master.breaks == mine.breaks
        choice = want[int(rng.integers(0, len(want)))]
        master.record(want_key, choice)
        mine.record(got_key, choice)
    assert mine.breaks > 0


def test_a_decision_key_is_its_parts_hashed_once() -> None:
    parts = (0, (PACKED, b"\x01"), (DomainAction("x", 0),))
    key = _DecisionKey(parts)
    assert hash(key) == hash(parts)
    assert key == _DecisionKey((0, (PACKED, b"\x01"), (DomainAction("x", 0),)))
    assert key != _DecisionKey((1, (PACKED, b"\x01"), (DomainAction("x", 0),)))
    assert key != parts
    assert {key: 1}[_DecisionKey(parts)] == 1
