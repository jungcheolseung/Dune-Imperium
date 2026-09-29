"""The ``mlp_slots`` network: its slot table, semantics and function preservation."""

import random
from collections import Counter
from collections.abc import Sequence

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    _AGENT_ICONS,
    _FRAME_KIND_INDEX,
    _FRAME_KINDS,
    _PHASES,
    CONFLICT_IDS,
    FEYD_TRACK_IDS,
    LEADER_IDS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
    RESEARCH_SPACE_IDS,
    SPACE_IDS,
    encode_player_view,
    segment_slice,
)
from dune_imperium.agents.registry import make_agent  # noqa: E402
from dune_imperium.content.bloodlines.tech import TECH_IDS  # noqa: E402
from dune_imperium.content.immortality.board import TLEILAXU_TRACK_END  # noqa: E402
from dune_imperium.content.immortality.tleilaxu import (  # noqa: E402
    TLEILAXU_CARDS_BY_ID,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID  # noqa: E402
from dune_imperium.content.uprising.intrigue import (  # noqa: E402
    INTRIGUE_CARDS_BY_ID,
    INTRIGUE_CARDS_BY_INSTANCE,
)
from dune_imperium.content.uprising.personal_cards import (  # noqa: E402
    personal_card_for_instance,
)
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.tactics import (  # noqa: E402
    TACTICS_TRACK_END,
    TACTICS_TRACK_START,
)
from dune_imperium.training import (  # noqa: E402
    AgentBatchPolicy,
    BatchPolicy,
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
)
from dune_imperium.training.network import (  # noqa: E402
    MlpSlotsNetwork,
    PolicyValueNetwork,
    build_network,
)
from dune_imperium.training.slots import (  # noqa: E402
    PAD_ROW,
    SLOT_FIELDS,
    SLOT_KEYS,
    SLOT_OBSERVATION_VERSION,
    VALUE_RANGE,
    SlotField,
    lookup_tables,
    slot_keys_digest,
)

# Changing the slot table must change this deliberately (with SLOT_VERSION):
# checkpoints store SLOT_KEYS and refuse a different table.
_GOLDEN_DIGEST = "c70f59660addf0139617b65f7f6cb5135b7c5aadb6a55db9572a0a7633d3ce31"
_FULL = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
)
# Chani (Tactics track), Kota, Feyd (Feyd track), Y'rkoon (Navigation); the
# Tleilaxu track and the research spaces come with Immortality.
_FORCED_LEADERS = (
    "chani",
    "kota_odax_of_ix",
    "feyd_rautha_harkonnen",
    "steersman_y_rkoon",
)


def _field(name: str) -> SlotField:
    return next(field for field in SLOT_FIELDS if field.name == name)


def _lookup_fields() -> list[tuple[SlotField, int, int | None]]:
    """(field, column, bit or None) of each lookup, in ``lookup_tables`` order."""

    lookups: list[tuple[SlotField, int, int | None]] = []
    for field in SLOT_FIELDS:
        for column in field.columns:
            if field.bitmask:
                lookups.extend((field, column, bit) for bit in field.values)
            else:
                lookups.append((field, column, None))
    return lookups


def _active_keys(network: MlpSlotsNetwork, observation: np.ndarray) -> Counter[str]:
    rows = network.slot_rows(torch.from_numpy(observation[None, :].astype(np.int32)))
    return Counter(SLOT_KEYS[int(row)] for row in rows[0] if int(row) != PAD_ROW)


def _game_views(
    seed: int, leaders: Sequence[str], *, heuristic: bool = False
) -> list[PlayerView]:
    """All four seats' views at every decision of one seeded full-expansion game.

    Random play covers the tracks; only the heuristic plays the Intrigue
    cards that grant Agent icons and sets Imperium cards aside.
    """

    engine = UprisingRulesEngine(leader_ids=tuple(leaders))
    state = engine.reset(_FULL, seed)
    chance = ChanceResolver(seed=seed)
    choices = random.Random(seed)
    agents = [make_agent("heuristic", seed + seat) for seat in range(4)]
    views: list[PlayerView] = []
    for _ in range(3_000):
        if engine.is_terminal(state):
            break
        decision = engine.current_decision(state)
        if decision is None:
            break
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        owner = decision.owner
        seat_views = [engine.observe(state, seat) for seat in range(4)]
        views.extend(seat_views)
        actions = engine.legal_actions(state, owner)
        if heuristic:
            action = agents[owner].choose_action(seat_views[owner], actions)
        else:
            action = choices.choice(actions)
        state = engine.apply(state, action).state
    return views


def _expected_keys(view: PlayerView) -> Counter[str]:
    """The rows a view should activate, decoded from the view alone.

    Written from the view's fields and the key naming, not from the slot
    table, so a column position or a value->row order that drifts from the
    encoder shows up as a mismatch.
    """

    observer = view.player

    def relative(seat: int) -> int:
        return (seat - observer) % 4

    def card(instance: str) -> str:
        return personal_card_for_instance(instance).card.card_id

    keys: Counter[str] = Counter()
    if view.phase is not GamePhase.PLAYER_TURNS:
        keys[f"phase:{view.phase.value}"] += 1
    if view.first_player is not None:
        keys[f"first_player:seat{relative(view.first_player)}"] += 1
    if view.turn_owner is not None:
        keys[f"turn_owner:seat{relative(view.turn_owner)}"] += 1
    if view.decision_kind is not None:
        keys[f"decision_kind:{view.decision_kind}"] += 1
    if view.current_conflict_ids:
        keys[f"conflict:{view.current_conflict_ids[-1]}"] += 1
    keys.update(f"imperium_row:{card(instance)}" for instance in view.imperium_row)
    for slot, seat in enumerate(view.reveal_order):
        keys[f"reveal_order{slot}:seat{relative(seat)}"] += 1
    keys.update(f"tech_face_up:{tech}" for tech in view.tech_face_up if tech)
    keys.update(f"tleilaxu_row:{card(instance)}" for instance in view.tleilaxu_row)
    private = view.private
    assert private is not None
    for slot, instance in enumerate(private.navigation_slots):
        intrigue = INTRIGUE_CARDS_BY_INSTANCE[instance].card.card_id
        keys[f"navigation{slot}:{intrigue}"] += 1
    if private.secret_project_tech_id:
        keys[f"secret_project:{private.secret_project_tech_id}"] += 1
    for k in range(4):
        player = view.players[(observer + k) % 4]
        for space in player.agent_locations:
            keys[f"occupancy:{space}"] += 1
            keys[f"seat{k}:agent_location:{space}"] += 1
        if player.leader_id is not None:
            keys[f"seat{k}:leader:{player.leader_id}"] += 1
        if player.feyd_track_space != FEYD_TRACK_IDS[0]:
            keys[f"seat{k}:feyd:{player.feyd_track_space}"] += 1
        if player.research_space:
            keys[f"seat{k}:research:{player.research_space}"] += 1
        for icon in player.granted_agent_icon_turn.split(","):
            if icon:
                keys[f"seat{k}:agent_icon:{icon}"] += 1
        if player.tactics_track_space:
            keys[f"seat{k}:tactics:{player.tactics_track_space}"] += 1
        if player.tleilaxu_space:
            keys[f"seat{k}:tleilaxu:{player.tleilaxu_space}"] += 1
        keys.update(
            f"seat{k}:set_aside:{card(instance)}"
            for instance in player.imperium_set_aside
        )
    return keys


def _selfplay_observations(
    seeds: Sequence[int], *, heuristic: bool = False
) -> np.ndarray:
    """Observations of seeded full-expansion games, the forced leaders rotated."""

    runner = SelfPlayRunner(_FULL, max_steps=3_000, record=True)
    specs = tuple(
        SelfPlaySpec(
            game_seed=seed,
            lineup=("r",) * 4,
            leader_ids=tuple(_FORCED_LEADERS[(seat + index) % 4] for seat in range(4)),
        )
        for index, seed in enumerate(seeds)
    )
    policy: BatchPolicy = (
        AgentBatchPolicy("heuristic", 1) if heuristic else RandomBatchPolicy(seed=11)
    )
    result = runner.run({"r": policy}, specs)
    return np.stack(
        [step.observation for episode in result.episodes for step in episode.steps]
    )


# -- T1: the table ---------------------------------------------------------------
def test_slot_table_sizes_match_the_identity_universes() -> None:
    navigation = [c for c, entry in INTRIGUE_CARDS_BY_ID.items() if entry.navigation]
    expected = {
        "phase": len(_PHASES) - 1,
        "first_player": 4,
        "turn_owner": 4,
        "decision_kind": len(_FRAME_KINDS),
        "conflict": len(CONFLICT_IDS),
        "imperium_row": len(IMPERIUM_CARDS_BY_ID),
        "tech_face_up": len(TECH_IDS),
        "tleilaxu_row": len(TLEILAXU_CARDS_BY_ID),
        "secret_project": len(TECH_IDS),
        "occupancy": len(SPACE_IDS),
        **{f"reveal_order{slot}": 4 for slot in range(4)},
        **{f"navigation{slot}": len(navigation) for slot in range(4)},
    }
    for seat in range(4):
        expected |= {
            f"seat{seat}_leader": len(LEADER_IDS),
            f"seat{seat}_feyd": len(FEYD_TRACK_IDS) - 1,
            f"seat{seat}_research": len(RESEARCH_SPACE_IDS),
            f"seat{seat}_agent_icons": len(_AGENT_ICONS),
            f"seat{seat}_tactics": TACTICS_TRACK_END - TACTICS_TRACK_START,
            f"seat{seat}_tleilaxu": TLEILAXU_TRACK_END,
            f"seat{seat}_agent_locations": len(SPACE_IDS),
            f"seat{seat}_set_aside": len(IMPERIUM_CARDS_BY_ID),
        }
    assert {field.name: len(field.keys) for field in SLOT_FIELDS} == expected
    assert len(SLOT_KEYS) == sum(expected.values()) == PAD_ROW == 1_139
    assert len(set(SLOT_KEYS)) == len(SLOT_KEYS)
    assert len(navigation) == 10

    columns, table = lookup_tables()
    assert columns.shape == (108,)
    assert table.shape == (108 * VALUE_RANGE,)
    assert int(table.max()) == PAD_ROW
    # Every trainable row is reachable from exactly the values its field lists.
    assert set(table.tolist()) == set(range(PAD_ROW + 1))

    for field in SLOT_FIELDS:
        allowed = set()
        for segment in field.segments:
            part = segment_slice(segment)
            allowed |= set(range(part.start, part.stop))
        assert set(field.columns) <= allowed, field.name
    assert _field("imperium_row").columns == tuple(
        range(*segment_slice("imperium_row").indices(OBSERVATION_SIZE))
    )
    assert len(_field("occupancy").columns) == 12


def test_slot_keys_are_pinned_by_a_golden_digest() -> None:
    assert slot_keys_digest() == _GOLDEN_DIGEST
    assert "seat1:leader:chani" in SLOT_KEYS
    assert "imperium_row:" + next(iter(IMPERIUM_CARDS_BY_ID)) in SLOT_KEYS
    assert "decision_kind:turn" in SLOT_KEYS
    assert f"phase:{GamePhase.PLAYER_TURNS.value}" not in SLOT_KEYS
    # A new observation version must revisit training/slots.py.
    assert OBSERVATION_VERSION == SLOT_OBSERVATION_VERSION


# -- T2: semantics on real views ---------------------------------------------------
def test_slot_rows_name_what_the_view_shows() -> None:
    network = MlpSlotsNetwork(8, hidden=(16,))
    # The heuristic game (seed 43) grants Agent icons and sets Imperium cards
    # aside; the random one covers the tracks (both measured 2026-09-27).
    views = _game_views(21, _FORCED_LEADERS) + _game_views(
        43, _FORCED_LEADERS, heuristic=True
    )
    observations = np.stack(
        [np.asarray(encode_player_view(view), dtype=np.int32) for view in views]
    )
    rows = network.slot_rows(torch.from_numpy(observations)).numpy()
    kind_column = _field("decision_kind").columns[0]
    hits: Counter[str] = Counter()
    for view, observation, view_rows in zip(views, observations, rows, strict=True):
        active = Counter(SLOT_KEYS[row] for row in view_rows if row != PAD_ROW)
        expected = _expected_keys(view)
        assert active == expected, (
            view.player,
            view.decision_kind,
            active - expected,
            expected - active,
        )
        hits.update({key.rsplit(":", 1)[0] for key in active})

        # The raw columns the table reads hold what the encoder wrote there.
        assert view.decision_kind is not None
        assert observation[kind_column] == _FRAME_KIND_INDEX[view.decision_kind] + 1
        for k in range(4):
            player = view.players[(view.player + k) % 4]

            def column(
                name: str, k: int = k, observation: np.ndarray = observation
            ) -> int:
                return int(observation[_field(f"seat{k}_{name}").columns[0]])

            assert player.leader_id is not None
            assert column("leader") == LEADER_IDS.index(player.leader_id) + 1
            assert column("feyd") == FEYD_TRACK_IDS.index(player.feyd_track_space)
            assert column("research") == (
                RESEARCH_SPACE_IDS.index(player.research_space) + 1
                if player.research_space
                else 0
            )
            assert column("agent_icons") == sum(
                1 << _AGENT_ICONS.index(icon)
                for icon in player.granted_agent_icon_turn.split(",")
                if icon
            )
            assert column("tactics") == player.tactics_track_space
            assert column("tleilaxu") == player.tleilaxu_space

    # Every field was compared on real values, for every egocentric seat.
    families = {key.rsplit(":", 1)[0] for field in SLOT_FIELDS for key in field.keys}
    assert families - set(hits) == set()


# -- T3: nothing real hides behind the pad or the clamp -----------------------------
def test_every_non_pad_value_of_real_games_has_a_row() -> None:
    # Random play covers the tracks; only the heuristic plays the Intrigue
    # cards that grant Agent icons (seed 39 does, measured 2026-09-27).
    observations = np.concatenate(
        [
            _selfplay_observations((31, 32, 33, 34)),
            _selfplay_observations((39,), heuristic=True),
        ]
    )
    network = MlpSlotsNetwork(8, hidden=(16,))
    rows = network.slot_rows(torch.from_numpy(observations.astype(np.int32))).numpy()
    lookups = _lookup_fields()
    assert rows.shape == (observations.shape[0], len(lookups))
    for index, (field, column, bit) in enumerate(lookups):
        raw = observations[:, column]
        assert int(raw.max()) < VALUE_RANGE, field.name  # the clamp hides nothing
        assert int(raw.min()) >= 0, field.name
        if bit is not None:
            carrying = (raw >> bit) & 1 == 1
        else:
            carrying = ~np.isin(raw, field.pad_values)
        assert np.all(rows[carrying, index] != PAD_ROW), (
            field.name,
            sorted(set(raw[carrying][rows[carrying, index] == PAD_ROW].tolist())),
        )
        assert np.all(rows[~carrying, index] == PAD_ROW), field.name

    # The forced leaders really exercised the rare fields.
    def seen(name: str) -> set[int]:
        field = _field(name)
        values = observations[:, list(field.columns)].ravel().tolist()
        return set(values) - set(field.pad_values)

    tactics = set().union(*(seen(f"seat{k}_tactics") for k in range(4)))
    assert tactics and tactics <= set(range(TACTICS_TRACK_START, TACTICS_TRACK_END))
    assert set().union(*(seen(f"seat{k}_feyd") for k in range(4)))
    assert set().union(*(seen(f"seat{k}_tleilaxu") for k in range(4)))
    assert set().union(*(seen(f"seat{k}_research") for k in range(4)))
    assert set().union(*(seen(f"seat{k}_agent_icons") for k in range(4)))
    assert set().union(*(seen(f"navigation{slot}") for slot in range(4)))
    assert seen("tleilaxu_row") and seen("tech_face_up")


# -- T4-T6: the network ---------------------------------------------------------------
def _widened(network: PolicyValueNetwork) -> MlpSlotsNetwork:
    widened = MlpSlotsNetwork(network.action_size, hidden=network.hidden)
    result = widened.load_state_dict(network.state_dict(), strict=False)
    assert list(result.missing_keys) == ["slot_embed.weight"]
    assert not result.unexpected_keys
    return widened.eval()


def test_a_widened_network_computes_the_same_function_bit_for_bit() -> None:
    torch.manual_seed(3)
    mlp = PolicyValueNetwork(40, hidden=(32, 16)).eval()
    widened = _widened(mlp)
    real = torch.from_numpy(_selfplay_observations((41,))[::5].astype(np.int32))
    noise = torch.randint(0, 400, (64, OBSERVATION_SIZE), dtype=torch.int32)
    actions = torch.tensor([39, 0, 7, 7, 21])
    for observations in (real, noise):
        masks = (torch.rand(observations.shape[0], 40) < 0.5).to(torch.int8)
        with torch.no_grad():
            expected_logits, expected_values = mlp(observations, masks)
            logits, values = widened(observations, masks)
            expected_hidden = mlp.trunk(observations)
            hidden = widened.trunk(observations)
            assert (widened.slot_rows(observations) != PAD_ROW).any()
            assert torch.equal(logits, expected_logits)
            assert torch.equal(values, expected_values)
            assert torch.equal(hidden, expected_hidden)
            assert torch.equal(
                widened.action_logits(hidden, actions),
                mlp.action_logits(expected_hidden, actions),
            )
    assert widened.arch_spec() == {
        "kind": "mlp_slots",
        "hidden": [32, 16],
        "slot_version": 1,
    }
    assert mlp.arch_spec() == {"kind": "mlp", "hidden": [32, 16]}
    rebuilt = build_network(widened.arch_spec(), 40)
    assert isinstance(rebuilt, MlpSlotsNetwork)
    assert type(build_network(mlp.arch_spec(), 40)) is PolicyValueNetwork
    with pytest.raises(ValueError, match="slot table"):
        build_network({**widened.arch_spec(), "slot_version": 0}, 40)
    with pytest.raises(ValueError, match="architecture"):
        build_network({"kind": "transformer", "hidden": [8]}, 40)
    # The embedding is parameter 2 * len(hidden) + 4, after the heads.
    names = [name for name, _ in widened.named_parameters()]
    assert names.index("slot_embed.weight") == 2 * len(widened.hidden) + 4 == 8
    assert set(widened.state_dict()) == set(mlp.state_dict()) | {"slot_embed.weight"}


def test_slot_gradients_reach_active_rows_only_and_train_the_output() -> None:
    torch.manual_seed(5)
    network = MlpSlotsNetwork(30, hidden=(16,))
    observations = torch.from_numpy(
        _selfplay_observations((51,))[::11].astype(np.int32)
    )
    rows = network.slot_rows(observations)
    active = set(rows.flatten().tolist()) - {PAD_ROW}
    assert len(active) > 50

    hidden = network.trunk(observations)
    loss = (
        network.value_head(hidden).square().mean()
        + network.policy_head(hidden).logsumexp(-1).mean()
    )
    loss.backward()
    gradient = network.slot_embed.weight.grad
    assert gradient is not None
    touched = set(torch.nonzero(gradient.abs().sum(dim=1)).flatten().tolist())
    assert touched == active
    assert float(gradient[PAD_ROW].abs().sum()) == 0.0

    with torch.no_grad():
        before = network.trunk(observations).clone()
    optimizer = torch.optim.Adam([network.slot_embed.weight], lr=1e-2)
    optimizer.step()
    with torch.no_grad():
        after = network.trunk(observations)
    assert not torch.equal(before, after)
    assert float(network.slot_embed.weight.detach()[PAD_ROW].abs().sum()) == 0.0


def test_the_slot_path_adds_summed_rows_before_the_first_activation() -> None:
    torch.manual_seed(7)
    network = MlpSlotsNetwork(30, hidden=(32, 16)).eval()
    with torch.no_grad():
        network.slot_embed.weight.normal_(std=0.05)
        network.slot_embed.weight[PAD_ROW] = 0.0
    observations = torch.cat(
        [
            torch.from_numpy(_selfplay_observations((71,))[::29].astype(np.int32)),
            torch.randint(0, 300, (16, OBSERVATION_SIZE), dtype=torch.int32),
        ]
    )
    rows = network.slot_rows(observations)
    assert ((rows != PAD_ROW).sum(dim=1) > 1).all()  # sum and mean differ
    with torch.no_grad():
        features = torch.log1p(observations.float().clamp(min=0.0))
        embedded = network.slot_embed.weight[rows].sum(dim=1)
        pre_activation = network.body[0](features) + embedded
        expected = network.body[1:](pre_activation)
        actual = network.trunk(observations)
        # The embedding really moves the pre-activation across zero, so a
        # placement after the first ReLU would not match either.
        without = network.body[0](features)
        assert (torch.sign(pre_activation) != torch.sign(without)).any()
    assert torch.allclose(actual, expected, atol=1e-6, rtol=0.0)


def test_single_row_trunk_matches_the_batched_trunk() -> None:
    torch.manual_seed(6)
    network = MlpSlotsNetwork(30, hidden=(32, 16)).eval()
    with torch.no_grad():
        # About the scale a trained embedding reaches; unit-normal rows make
        # the trunk ~30x larger and float32 rounding alone exceeds 1e-6.
        network.slot_embed.weight.normal_(std=0.05)
        network.slot_embed.weight[PAD_ROW] = 0.0
    observations = torch.from_numpy(
        _selfplay_observations((61,))[::37].astype(np.int32)
    )
    with torch.no_grad():
        batched = network.trunk(observations)
        for index in range(observations.shape[0]):
            single = network.trunk(observations[index : index + 1])
            assert torch.allclose(single[0], batched[index], atol=1e-6, rtol=0.0)
