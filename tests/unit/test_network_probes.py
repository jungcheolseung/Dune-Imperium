"""Probes of what a trained network reads (evaluation.network_probes)."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    OBSERVATION_SEGMENTS,
    encode_player_view,
)
from dune_imperium.evaluation.network_probes import (  # noqa: E402
    VALUE_CHANGES,
    ProbePosition,
    atomics_timing,
    row_sensitivity,
    sample_positions,
    value_sensitivity,
)
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.torch_policy import (  # noqa: E402
    NetworkAgent,
    load_network_agent,
)

CONFIG = RulesetConfig(immortality=True)


def _agent(tmp_path: Path, *, blind_to_row: bool = False) -> NetworkAgent:
    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(CONFIG).size, hidden=(16,))
    if blind_to_row:
        row = next(s for s in OBSERVATION_SEGMENTS if s.name == "imperium_row")
        first = network.body[0]
        assert isinstance(first, torch.nn.Linear)
        with torch.no_grad():
            first.weight[:, row.offset : row.offset + row.length] = 0.0
    path = tmp_path / "net.pt"
    save_checkpoint(path, network, ruleset=CONFIG.identifier, iteration=1)
    return load_network_agent(str(path), CONFIG, seed=0)


@pytest.fixture(scope="module")
def positions() -> list[ProbePosition]:
    return sample_positions(CONFIG, [1], every=25)


def test_positions_come_from_app_ai_games_with_a_choice(
    positions: list[ProbePosition],
) -> None:
    assert len(positions) > 5
    assert all(len(position.offered) >= 2 for position in positions)


def test_every_value_change_moves_only_the_observing_seat(
    positions: list[ProbePosition], tmp_path: Path
) -> None:
    report = value_sensitivity(_agent(tmp_path), positions)
    assert set(report) == set(VALUE_CHANGES)
    assert report["spice +3"].count == len(positions)
    held = sum(
        1
        for position in positions
        for player in position.view.players
        if player.player == position.view.player and player.family_atomics
    )
    assert report["family atomics spent"].count == held
    for change in VALUE_CHANGES.values():
        for position in positions:
            changed = change(position.view)
            if changed is None:
                continue
            before = np.asarray(encode_player_view(position.view))
            after = np.asarray(encode_player_view(changed))
            assert (before != after).any()
            others = [p for p in changed.players if p.player != position.view.player]
            assert others == [
                p for p in position.view.players if p.player != position.view.player
            ]


def test_a_network_blind_to_the_row_does_not_move_when_it_is_swapped(
    positions: list[ProbePosition], tmp_path: Path
) -> None:
    blind = row_sensitivity(_agent(tmp_path, blind_to_row=True), positions)
    assert blind["policy"].count > 0
    assert blind["value"].mean == pytest.approx(0.0, abs=1e-6)
    assert blind["policy"].mean == pytest.approx(0.0, abs=1e-6)
    seeing = row_sensitivity(_agent(tmp_path), positions)
    assert seeing["value"].mean > 0.0


def test_the_atomics_timing_counts_each_seat_s_spend() -> None:
    timing = atomics_timing("app_ai", CONFIG, [3])
    assert timing.seats == CONFIG.players
    assert timing.spent == len(timing.rounds) <= CONFIG.players
    assert timing.in_reveal <= timing.spent
    assert timing.round_one == sum(1 for r in timing.rounds if r == 1)
