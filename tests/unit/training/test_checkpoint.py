"""Checkpoint formats 2 and 3: identities, migration, stamping, widening."""

from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import (  # noqa: E402
    ACTION_CODEC_VERSION,
    ActionCodec,
)
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    CONTRACT_IDS,
    CONTRACT_SEGMENTS,
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
)
from dune_imperium.cli.checkpoint import main as checkpoint_main  # noqa: E402
from dune_imperium.content.uprising.contracts import CONTRACTS_BY_ID  # noqa: E402
from dune_imperium.training import (  # noqa: E402
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
    stack_episodes,
)
from dune_imperium.training import checkpoint as checkpoint_module  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    _CONTRACT_IDS_BEFORE_V21,
    ARCH_CHECKPOINT_FORMAT,
    CHECKPOINT_FORMAT,
    load_checkpoint,
    save_checkpoint,
    stamp_checkpoint,
    widen_checkpoint,
)
from dune_imperium.training.learner import Learner, LearnerConfig  # noqa: E402
from dune_imperium.training.network import (  # noqa: E402
    MlpSlotsNetwork,
    PolicyValueNetwork,
)
from dune_imperium.training.slots import PAD_ROW, SLOT_KEYS  # noqa: E402

_CPU = torch.device("cpu")


def _trained(
    codec: ActionCodec, *, slots: bool = False
) -> tuple[PolicyValueNetwork, Learner]:
    """A base-ruleset network with Adam moments from one tiny update."""

    torch.manual_seed(0)
    network = (
        MlpSlotsNetwork(codec.size, hidden=(16,))
        if slots
        else PolicyValueNetwork(codec.size, hidden=(16,))
    )
    learner = Learner(network, _CPU, LearnerConfig(minibatch_size=256), seed=0)
    runner = SelfPlayRunner(codec.config, max_steps=24)
    result = runner.run(
        {"r": RandomBatchPolicy(seed=1)},
        (SelfPlaySpec(game_seed=2, lineup=("r",) * 4),),
    )
    learner.update(stack_episodes(result.episodes, action_size=runner.codec.size))
    return network, learner


def _forge_older(
    document: dict[str, Any], *, drop_action: int, drop_column: int
) -> dict[str, Any]:
    """Pretend the file predates one template and one observation column.

    The template at ``drop_action`` and the column ``drop_column`` (inside the
    first segment) are removed as if they never existed, a template the
    current code does not know is appended, and the codec version goes down
    by one. The observation version stays: the smaller size already forces
    the migration, and a version before 21 would also re-link the Contract
    columns by the v20 identities, which this file (the current network)
    does not have.
    """

    forged = dict(document)
    keep_rows = [i for i in range(int(document["action_size"])) if i != drop_action]
    keep_cols = [i for i in range(OBSERVATION_SIZE) if i != drop_column]
    rows = torch.tensor(keep_rows)
    cols = torch.tensor(keep_cols)
    state = dict(document["state_dict"])
    fake_row = torch.full((1, state["policy_head.weight"].shape[1]), 0.5)
    state["policy_head.weight"] = torch.cat(
        [state["policy_head.weight"][rows], fake_row]
    )
    state["policy_head.bias"] = torch.cat(
        [state["policy_head.bias"][rows], torch.tensor([0.5])]
    )
    state["body.0.weight"] = state["body.0.weight"][:, cols]
    forged["state_dict"] = state
    templates = list(document["action_templates"])
    forged["action_templates"] = [
        t for i, t in enumerate(templates) if i != drop_action
    ] + [("fake_action", ())]
    forged["action_size"] = len(forged["action_templates"])
    layout = []
    offset = 0
    for name, _, length in document["observation_layout"]:
        first = offset == 0 and name == OBSERVATION_SEGMENTS[0].name
        size = length - 1 if first else length
        layout.append((name, offset, size))
        offset += size
    forged["observation_layout"] = layout
    forged["observation_size"] = OBSERVATION_SIZE - 1
    forged["action_codec_version"] = ACTION_CODEC_VERSION - 1
    forged["observation_version"] = OBSERVATION_VERSION
    optimizer = document["optimizer_state"]
    if optimizer is not None:
        moved = {}
        for index, moments in optimizer["state"].items():
            entry = dict(moments)
            for key in ("exp_avg", "exp_avg_sq"):
                tensor = entry[key]
                if int(index) == 0:
                    entry[key] = tensor[:, cols]
                elif tensor.shape[0] == int(document["action_size"]):
                    extra = torch.zeros((1, *tensor.shape[1:]))
                    entry[key] = torch.cat([tensor[rows], extra])
            moved[index] = entry
        forged["optimizer_state"] = {**optimizer, "state": moved}
    return forged


def test_format_2_stores_template_identities_and_the_layout(tmp_path: Path) -> None:
    codec = ActionCodec(RulesetConfig())
    network, learner = _trained(codec)
    path = tmp_path / "net.pt"
    save_checkpoint(
        path,
        network,
        ruleset=codec.config.identifier,
        iteration=4,
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )

    loaded, info = load_checkpoint(path)
    assert info.format == CHECKPOINT_FORMAT == 2
    assert info.arch == "mlp"
    assert info.migratable and info.migration is None
    assert info.action_codec_version == ACTION_CODEC_VERSION
    document = torch.load(path, weights_only=True)
    assert len(document["action_templates"]) == codec.size
    assert document["action_templates"][0] == (
        codec.catalog[0].action_id,
        codec.catalog[0].arguments,
    )
    assert document["observation_layout"] == [
        (segment.name, segment.offset, segment.length)
        for segment in OBSERVATION_SEGMENTS
    ]
    assert torch.equal(loaded.policy_head.weight, network.policy_head.weight.detach())

    # A codec that does not fit the network is refused at save time.
    with pytest.raises(ValueError, match="does not match the codec"):
        save_checkpoint(
            tmp_path / "bad.pt",
            PolicyValueNetwork(11, hidden=(16,)),
            ruleset=codec.config.identifier,
            iteration=1,
            codec=codec,
        )
    # A file saved without a codec is not migratable but loads as before.
    save_checkpoint(
        tmp_path / "plain.pt", network, ruleset=codec.config.identifier, iteration=1
    )
    _, plain = load_checkpoint(tmp_path / "plain.pt")
    assert not plain.migratable



def test_a_file_without_templates_cannot_answer_for_another_ruleset(
    tmp_path: Path,
) -> None:
    # Moving a head onto another catalog needs the file's template list.
    codec = ActionCodec(RulesetConfig())
    network, _ = _trained(codec)
    path = tmp_path / "plain.pt"
    save_checkpoint(path, network, ruleset=codec.config.identifier, iteration=1)

    _, info = load_checkpoint(path, ruleset=RulesetConfig())
    assert info.migration is None
    with pytest.raises(ValueError, match="cannot answer for"):
        load_checkpoint(path, ruleset=RulesetConfig(epic_game=True))

def test_migration_moves_rows_and_columns_by_identity(tmp_path: Path) -> None:
    codec = ActionCodec(RulesetConfig())
    network, learner = _trained(codec)
    current = tmp_path / "current.pt"
    save_checkpoint(
        current,
        network,
        ruleset=codec.config.identifier,
        iteration=7,
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )
    drop_action = next(
        i for i, t in enumerate(codec.catalog) if t.action_id == "finish_agent_turn"
    )
    drop_column = OBSERVATION_SEGMENTS[0].length - 1
    older = tmp_path / "older.pt"
    torch.save(
        _forge_older(
            torch.load(current, weights_only=True),
            drop_action=drop_action,
            drop_column=drop_column,
        ),
        older,
    )

    migrated, info = load_checkpoint(older)

    assert info.migration is not None
    report = info.migration
    assert (report.from_codec_version, report.to_codec_version) == (
        ACTION_CODEC_VERSION - 1,
        ACTION_CODEC_VERSION,
    )
    assert (report.actions_kept, report.actions_new, report.actions_dropped) == (
        codec.size - 1,
        1,
        1,
    )
    assert (
        report.observation_kept,
        report.observation_new,
        report.observation_dropped,
    ) == (OBSERVATION_SIZE - 1, 1, 0)
    assert migrated.action_size == codec.size
    assert info.iteration == 7

    original = network.policy_head.weight.detach()
    weight = migrated.policy_head.weight.detach()
    keep = torch.tensor([i for i in range(codec.size) if i != drop_action])
    assert torch.equal(weight[keep], original[keep])
    assert torch.equal(weight[drop_action], torch.zeros(weight.shape[1]))
    assert float(migrated.policy_head.bias.detach()[drop_action]) == 0.0
    first_layer = migrated.body[0]
    assert isinstance(first_layer, torch.nn.Linear)
    first = first_layer.weight.detach()
    columns = torch.tensor([i for i in range(OBSERVATION_SIZE) if i != drop_column])
    original_first = network.body[0]
    assert isinstance(original_first, torch.nn.Linear)
    assert torch.equal(first[:, columns], original_first.weight.detach()[:, columns])
    assert torch.equal(first[:, drop_column], torch.zeros(first.shape[0]))

    # With the new column at zero, every kept action scores exactly as before
    # and the new one is neutral rather than masked.
    observations = torch.randint(0, 5, (3, OBSERVATION_SIZE), dtype=torch.int32)
    observations[:, drop_column] = 0
    masks = torch.ones(3, codec.size, dtype=torch.int8)
    expected, expected_values = network(observations, masks)
    actual, actual_values = migrated(observations, masks)
    assert torch.allclose(actual[:, keep], expected[:, keep])
    assert torch.allclose(actual_values, expected_values)
    assert torch.allclose(actual[:, drop_action], torch.zeros(3))

    # The Adam moments moved with the rows and columns and can be restored.
    assert info.optimizer_state is not None
    resumed = Learner(migrated, _CPU, LearnerConfig(minibatch_size=256), seed=0)
    resumed.restore_optimizer(info.optimizer_state)
    moments = resumed.optimizer.state_dict()["state"]
    before = learner.optimizer.state_dict()["state"]
    head_index = 2 * len(network.hidden)
    assert torch.equal(
        moments[head_index]["exp_avg"][keep], before[head_index]["exp_avg"][keep]
    )
    assert torch.equal(
        moments[head_index]["exp_avg"][drop_action], torch.zeros(weight.shape[1])
    )
    assert torch.equal(
        moments[0]["exp_avg_sq"][:, columns], before[0]["exp_avg_sq"][:, columns]
    )
    assert int(moments[0]["step"]) == int(before[0]["step"])


def test_a_format_1_mismatch_is_refused_and_stamping_fixes_it(tmp_path: Path) -> None:
    codec = ActionCodec(RulesetConfig())
    network, _ = _trained(codec)
    path = tmp_path / "old.pt"
    save_checkpoint(path, network, ruleset=codec.config.identifier, iteration=2)
    document = torch.load(path, weights_only=True)
    document["format"] = 1
    del document["action_templates"]
    del document["observation_layout"]
    torch.save(document, path)
    _, info = load_checkpoint(path)
    assert info.format == 1 and not info.migratable

    stale = tmp_path / "stale.pt"
    document["action_codec_version"] -= 1
    torch.save(document, stale)
    with pytest.raises(ValueError, match="stamp"):
        load_checkpoint(stale)
    with pytest.raises(ValueError, match="current codec"):
        stamp_checkpoint(stale)

    stamped = stamp_checkpoint(path)
    assert stamped.format == 2 and stamped.migratable
    document = torch.load(path, weights_only=True)
    assert len(document["action_templates"]) == codec.size
    document["action_codec_version"] -= 1
    torch.save(document, stale)
    _, migrated = load_checkpoint(stale)
    assert migrated.migration is not None
    assert migrated.migration.actions_kept == codec.size

    # A file whose action size is not its ruleset's catalog cannot be stamped.
    odd = tmp_path / "odd.pt"
    save_checkpoint(
        odd,
        PolicyValueNetwork(11, hidden=(16,)),
        ruleset="uprising-4p-base",
        iteration=1,
    )
    with pytest.raises(ValueError, match="catalog"):
        stamp_checkpoint(odd)


def test_a_v20_file_reads_its_contract_columns_by_identity(tmp_path: Path) -> None:
    # Observation v21 put Spice Refinery I/II and the second Espionage I and
    # Harvest 3+ where four Rise of Ix tiles were [Main p. 16]. A v20 file's
    # Contract columns follow the v20 identities: a kept tile keeps its
    # column, a second copy reads its first copy's, a new tile starts at zero.
    codec = ActionCodec(RulesetConfig())
    network, _ = _trained(codec)
    current = tmp_path / "current.pt"
    save_checkpoint(
        current, network, ruleset=codec.config.identifier, iteration=3, codec=codec
    )
    document = torch.load(current, weights_only=True)
    v20 = list(_CONTRACT_IDS_BEFORE_V21)
    mark = {contract_id: float(index + 1) for index, contract_id in enumerate(v20)}
    state = dict(document["state_dict"])
    weight = state["body.0.weight"].clone()
    segments = [s for s in OBSERVATION_SEGMENTS if s.name in CONTRACT_SEGMENTS]
    assert len(segments) == 11
    for segment in segments:
        for index, contract_id in enumerate(v20):
            weight[:, segment.offset + index] = mark[contract_id]
    state["body.0.weight"] = weight
    document["state_dict"] = state
    document["observation_version"] = 20
    document["action_codec_version"] = ACTION_CODEC_VERSION - 1
    older = tmp_path / "v20.pt"
    torch.save(document, older)

    migrated, info = load_checkpoint(older)

    assert info.migration is not None
    report = info.migration
    assert (report.observation_new, report.observation_dropped) == (2 * 11, 4 * 11)
    first_layer = migrated.body[0]
    assert isinstance(first_layer, torch.nn.Linear)
    first = first_layer.weight.detach()
    for segment in segments:
        for index, contract_id in enumerate(CONTRACT_IDS):
            column = first[:, segment.offset + index]
            printed = CONTRACTS_BY_ID[contract_id].copy_of or contract_id
            expected = mark.get(printed, 0.0)
            assert torch.all(column == expected), (segment.name, contract_id)


# Observation v28 (Epic Game Mode; v26 on the epic-game-mode branch)
# appended Control the Spice to every personal-card segment, Economic
# Supremacy to every battle-card segment, and the one-column ``epic_game``
# segment after all the others. v27 has v25's layout (v26's frame kind was
# removed again), so the previous layout is 4,587 columns wide.
_V28_GROWN_SEGMENTS = frozenset(
    {"imperium_removed", "private_hand", "private_peeked_card"}
    | {
        f"seat{seat}_{zone}"
        for seat in range(4)
        for zone in ("hand_public", "in_play", "discard", "trashed", "battle_cards")
    }
)


def test_a_v27_file_migrates_to_v28_and_computes_the_same_outputs(
    tmp_path: Path,
) -> None:
    # A file written under v27 knows neither card nor the flag: each v27
    # segment's columns keep their place at its start, the 24 new columns
    # start at zero, and a game without the option (every new column 0)
    # scores exactly as the v27 network did.
    codec = ActionCodec(RulesetConfig())
    network, _ = _trained(codec)
    current = tmp_path / "current.pt"
    save_checkpoint(
        current, network, ruleset=codec.config.identifier, iteration=4, codec=codec
    )
    document = torch.load(current, weights_only=True)
    kept: list[int] = []
    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        if segment.name == "epic_game":
            continue
        length = segment.length - int(segment.name in _V28_GROWN_SEGMENTS)
        kept.extend(range(segment.offset, segment.offset + length))
        layout.append((segment.name, offset, length))
        offset += length
    assert offset == 4_587 == OBSERVATION_SIZE - 24
    state = dict(document["state_dict"])
    state["body.0.weight"] = state["body.0.weight"][:, torch.tensor(kept)]
    older = tmp_path / "v27.pt"
    torch.save(
        {
            **document,
            "state_dict": state,
            "observation_layout": layout,
            "observation_size": offset,
            "observation_version": 27,
            "action_codec_version": ACTION_CODEC_VERSION - 1,
        },
        older,
    )

    migrated, info = load_checkpoint(older)

    assert info.migration is not None
    report = info.migration
    assert (report.from_observation_version, report.to_observation_version) == (
        27,
        OBSERVATION_VERSION,
    )
    assert (
        report.observation_kept,
        report.observation_new,
        report.observation_dropped,
    ) == (4_587, 24, 0)
    assert (report.actions_kept, report.actions_new, report.actions_dropped) == (
        codec.size,
        0,
        0,
    )
    new = torch.tensor(sorted(set(range(OBSERVATION_SIZE)) - set(kept)))
    first_layer = migrated.body[0]
    original_first = network.body[0]
    assert isinstance(first_layer, torch.nn.Linear)
    assert isinstance(original_first, torch.nn.Linear)
    first = first_layer.weight.detach()
    assert torch.equal(
        first[:, torch.tensor(kept)],
        original_first.weight.detach()[:, torch.tensor(kept)],
    )
    assert float(first[:, new].abs().sum()) == 0.0

    runner = SelfPlayRunner(codec.config, max_steps=80, record=True)
    result = runner.run(
        {"r": RandomBatchPolicy(seed=5)},
        (SelfPlaySpec(game_seed=6, lineup=("r",) * 4),),
    )
    observations = torch.stack(
        [
            torch.as_tensor(step.observation, dtype=torch.int32)
            for episode in result.episodes
            for step in episode.steps
        ]
    )
    assert observations.shape[1] == OBSERVATION_SIZE
    # Every new column of a game without the option is 0, so the network the
    # v27 file was cut from computes the v27 file's function on it.
    assert not bool(observations[:, new].any())
    masks = torch.ones(observations.shape[0], codec.size, dtype=torch.int8)
    expected, expected_values = network(observations, masks)
    actual, actual_values = migrated(observations, masks)
    assert torch.equal(actual, expected)
    assert torch.equal(actual_values, expected_values)


def test_checkpoint_cli_inspects_stamps_and_migrates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codec = ActionCodec(RulesetConfig())
    network, _ = _trained(codec)
    path = tmp_path / "cli.pt"
    save_checkpoint(path, network, ruleset=codec.config.identifier, iteration=9)
    document = torch.load(path, weights_only=True)
    document["format"] = 1
    del document["action_templates"]
    del document["observation_layout"]
    torch.save(document, path)

    assert checkpoint_main(["inspect", str(path)]) == 0
    assert "format 1" in capsys.readouterr().out
    assert checkpoint_main(["stamp", str(path)]) == 0
    assert "migratable yes" in capsys.readouterr().out

    stale = tmp_path / "stale.pt"
    document = torch.load(path, weights_only=True)
    document["action_codec_version"] -= 1
    torch.save(document, stale)
    target = tmp_path / "migrated.pt"
    assert checkpoint_main(["migrate", str(stale), str(target)]) == 0
    out = capsys.readouterr().out
    assert f"v{ACTION_CODEC_VERSION - 1} -> v{ACTION_CODEC_VERSION}" in out
    _, info = load_checkpoint(target)
    assert info.migration is None and info.migratable and info.iteration == 9
    assert checkpoint_main(["inspect", str(tmp_path / "missing.pt")]) == 1


# An MLP file keeps exactly the format-2 document it had before format 3.
_FORMAT_2_KEYS = {
    "format",
    "observation_version",
    "observation_size",
    "observation_layout",
    "action_codec_version",
    "action_templates",
    "ruleset",
    "action_size",
    "hidden",
    "iteration",
    "metadata",
    "state_dict",
    "optimizer_state",
}


def test_a_slot_network_writes_format_3_and_an_mlp_stays_format_2(
    tmp_path: Path,
) -> None:
    codec = ActionCodec(RulesetConfig())
    mlp, _ = _trained(codec)
    network, learner = _trained(codec, slots=True)
    assert isinstance(network, MlpSlotsNetwork)
    embedding = network.slot_embed.weight.detach()
    assert float(embedding.abs().sum()) > 0.0  # the update trained some rows

    save_checkpoint(
        tmp_path / "mlp.pt", mlp, ruleset=codec.config.identifier, iteration=1
    )
    mlp_document = torch.load(tmp_path / "mlp.pt", weights_only=True)
    assert set(mlp_document) == _FORMAT_2_KEYS
    assert mlp_document["format"] == CHECKPOINT_FORMAT == 2

    path = tmp_path / "slots.pt"
    save_checkpoint(
        path,
        network,
        ruleset=codec.config.identifier,
        iteration=5,
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )
    document = torch.load(path, weights_only=True)
    assert set(document) == _FORMAT_2_KEYS | {"arch", "slot_keys"}
    assert document["format"] == ARCH_CHECKPOINT_FORMAT == 3
    assert document["arch"] == {"kind": "mlp_slots", "hidden": [16], "slot_version": 1}
    assert document["slot_keys"] == list(SLOT_KEYS)
    # Only weights are persisted; the lookup tables are rebuilt.
    assert set(document["state_dict"]) == set(mlp.state_dict()) | {"slot_embed.weight"}

    loaded, info = load_checkpoint(path)
    assert isinstance(loaded, MlpSlotsNetwork)
    assert (info.format, info.arch, info.migratable) == (3, "mlp_slots", True)
    assert torch.equal(loaded.slot_embed.weight.detach(), embedding)
    observations = torch.randint(0, 6, (3, OBSERVATION_SIZE), dtype=torch.int32)
    masks = torch.ones(3, codec.size, dtype=torch.int8)
    with torch.no_grad():
        expected = network(observations, masks)[0]
        assert torch.equal(loaded(observations, masks)[0], expected)

    # A slot table whose keys do not fit the embedding, or whose meaning
    # changed (another slot_version), is refused, not read with shifted rows.
    for change, message in (
        ({"slot_keys": list(SLOT_KEYS[:-1])}, "slot keys"),
        ({"slot_keys": [*SLOT_KEYS[1:], SLOT_KEYS[1]]}, "slot keys"),
        ({"arch": {**document["arch"], "slot_version": 0}}, "slot table"),
        ({"arch": {**document["arch"], "hidden": [32]}}, "hidden shape"),
    ):
        forged = tmp_path / "forged.pt"
        torch.save({**document, **change}, forged)
        with pytest.raises(ValueError, match=message):
            load_checkpoint(forged)
        with pytest.raises(ValueError, match=message):
            stamp_checkpoint(forged)


def test_a_slot_checkpoint_relinks_its_embedding_rows_by_key(
    tmp_path: Path,
) -> None:
    # Observation v22 added the Arrakeen Scouts frame kind, hence the row
    # ``decision_kind:scouts_draw``: a file written before it has one row
    # fewer. Its rows move by key, the new row starts at zero, and Adam's
    # moments move with the rows.
    codec = ActionCodec(RulesetConfig())
    network, learner = _trained(codec, slots=True)
    assert isinstance(network, MlpSlotsNetwork)
    path = tmp_path / "slots.pt"
    save_checkpoint(
        path,
        network,
        ruleset=codec.config.identifier,
        iteration=5,
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )
    document = torch.load(path, weights_only=True)
    new_key = "decision_kind:scouts_draw"
    dropped = SLOT_KEYS.index(new_key)
    embedding = document["state_dict"]["slot_embed.weight"]
    keep = [row for row in range(embedding.shape[0]) if row != dropped]
    old_keys = [key for key in SLOT_KEYS if key != new_key]
    # Shuffle the old order too: rows are found by key, not by position.
    old_keys = [*old_keys[5:], *old_keys[:5]]
    old_rows = [*keep[5:-1], *keep[:5], keep[-1]]
    state = dict(document["optimizer_state"]["state"])
    embed_index = next(
        index
        for index, moments in state.items()
        if moments["exp_avg"].shape == embedding.shape
    )
    moments = dict(state[embed_index])
    moments["exp_avg"] = moments["exp_avg"][old_rows]
    moments["exp_avg_sq"] = moments["exp_avg_sq"][old_rows]
    state[embed_index] = moments
    forged = {
        **document,
        "slot_keys": old_keys,
        "state_dict": {
            **document["state_dict"],
            "slot_embed.weight": embedding[old_rows],
        },
        "optimizer_state": {**document["optimizer_state"], "state": state},
    }
    old_path = tmp_path / "old_slots.pt"
    torch.save(forged, old_path)

    loaded, info = load_checkpoint(old_path)
    assert isinstance(loaded, MlpSlotsNetwork)
    relinked = loaded.slot_embed.weight.detach()
    assert torch.equal(relinked[keep], embedding[keep])
    assert float(relinked[dropped].abs().sum()) == 0.0
    assert info.optimizer_state is not None
    moved = info.optimizer_state["state"][embed_index]["exp_avg"]
    assert torch.equal(
        moved[keep], document["optimizer_state"]["state"][embed_index]["exp_avg"][keep]
    )
    assert float(moved[dropped].abs().sum()) == 0.0


def test_a_slot_checkpoint_migrates_its_head_and_keeps_its_embedding(
    tmp_path: Path,
) -> None:
    codec = ActionCodec(RulesetConfig())
    network, learner = _trained(codec, slots=True)
    assert isinstance(network, MlpSlotsNetwork)
    current = tmp_path / "current.pt"
    save_checkpoint(
        current,
        network,
        ruleset=codec.config.identifier,
        iteration=7,
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )
    drop_action = next(
        i for i, t in enumerate(codec.catalog) if t.action_id == "finish_agent_turn"
    )
    drop_column = OBSERVATION_SEGMENTS[0].length - 1
    older = tmp_path / "older.pt"
    torch.save(
        _forge_older(
            torch.load(current, weights_only=True),
            drop_action=drop_action,
            drop_column=drop_column,
        ),
        older,
    )

    migrated, info = load_checkpoint(older)
    assert isinstance(migrated, MlpSlotsNetwork)
    assert info.migration is not None and info.arch == "mlp_slots"
    keep = torch.tensor([i for i in range(codec.size) if i != drop_action])
    weight = migrated.policy_head.weight.detach()
    assert torch.equal(weight[keep], network.policy_head.weight.detach()[keep])
    assert torch.equal(weight[drop_action], torch.zeros(weight.shape[1]))
    assert torch.equal(
        migrated.slot_embed.weight.detach(), network.slot_embed.weight.detach()
    )

    assert info.optimizer_state is not None
    resumed = Learner(migrated, _CPU, LearnerConfig(minibatch_size=256), seed=0)
    resumed.restore_optimizer(info.optimizer_state)
    moments = resumed.optimizer.state_dict()["state"]
    before = learner.optimizer.state_dict()["state"]
    head_index = 2 * len(network.hidden)
    slot_index = head_index + 4
    assert torch.equal(
        moments[head_index]["exp_avg"][keep], before[head_index]["exp_avg"][keep]
    )
    for name in ("exp_avg", "exp_avg_sq"):
        assert torch.equal(moments[slot_index][name], before[slot_index][name])
    assert float(before[slot_index]["exp_avg"].abs().sum()) > 0.0

    # Migrating through the CLI writes the result as format 3 again.
    target = tmp_path / "migrated.pt"
    save_checkpoint(
        target,
        migrated,
        ruleset=info.ruleset,
        iteration=info.iteration,
        optimizer_state=info.optimizer_state,
    )
    assert torch.load(target, weights_only=True)["action_templates"] is None
    stamped = stamp_checkpoint(target)
    assert (stamped.format, stamped.arch, stamped.migratable) == (3, "mlp_slots", True)
    document = torch.load(target, weights_only=True)
    assert document["slot_keys"] == list(SLOT_KEYS)
    assert checkpoint_main(["migrate", str(older), str(tmp_path / "cli.pt")]) == 0
    _, cli = load_checkpoint(tmp_path / "cli.pt")
    assert (cli.format, cli.arch, cli.migration) == (3, "mlp_slots", None)


def test_widening_keeps_the_function_and_the_adam_moments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codec = ActionCodec(RulesetConfig())
    network, learner = _trained(codec)
    source = tmp_path / "mlp.pt"
    save_checkpoint(
        source,
        network,
        ruleset=codec.config.identifier,
        iteration=11,
        metadata={"tag": "champion"},
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )
    destination = tmp_path / "slots.pt"

    info = widen_checkpoint(source, destination)

    assert (info.format, info.arch, info.iteration) == (3, "mlp_slots", 11)
    assert info.migratable and info.migration is None
    assert info.metadata["widened_from"] == str(source)
    assert info.metadata["tag"] == "champion"
    widened, _ = load_checkpoint(destination)
    assert isinstance(widened, MlpSlotsNetwork)
    assert float(widened.slot_embed.weight.detach().abs().sum()) == 0.0
    observations = torch.randint(0, 9, (4, OBSERVATION_SIZE), dtype=torch.int32)
    masks = torch.ones(4, codec.size, dtype=torch.int8)
    with torch.no_grad():
        expected = network(observations, masks)
        actual = widened(observations, masks)
    assert torch.equal(actual[0], expected[0]) and torch.equal(actual[1], expected[1])

    assert info.optimizer_state is not None
    slot_index = 2 * len(network.hidden) + 4
    assert info.optimizer_state["param_groups"][0]["params"] == list(
        range(slot_index + 1)
    )
    resumed = Learner(widened, _CPU, LearnerConfig(minibatch_size=256), seed=0)
    resumed.restore_optimizer(info.optimizer_state)
    moments = resumed.optimizer.state_dict()["state"]
    before = learner.optimizer.state_dict()["state"]
    assert set(moments) == set(before) == set(range(slot_index))
    for index in before:
        for name in ("exp_avg", "exp_avg_sq", "step"):
            assert torch.equal(
                torch.as_tensor(moments[index][name]),
                torch.as_tensor(before[index][name]),
            )
    assert widened.slot_embed.weight not in resumed.optimizer.state

    runner = SelfPlayRunner(codec.config, max_steps=24)
    result = runner.run(
        {"r": RandomBatchPolicy(seed=3)},
        (SelfPlaySpec(game_seed=4, lineup=("r",) * 4),),
    )
    resumed.update(stack_episodes(result.episodes, action_size=codec.size))
    state = resumed.optimizer.state[widened.slot_embed.weight]
    assert int(state["step"]) >= 1
    assert float(widened.slot_embed.weight.detach().abs().sum()) > 0.0
    assert float(widened.slot_embed.weight.detach()[PAD_ROW].abs().sum()) == 0.0

    # A slot file cannot be widened again; the CLI widens and prints the arch.
    with pytest.raises(ValueError, match="already"):
        widen_checkpoint(destination, tmp_path / "again.pt")
    assert (
        checkpoint_main(
            ["widen", "--arch", "mlp_slots", str(source), str(tmp_path / "cli.pt")]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "arch mlp_slots" in out and "format 3" in out
    assert checkpoint_main(["inspect", str(source)]) == 0
    assert "arch mlp" in capsys.readouterr().out


def test_widening_an_older_file_records_the_migration_done_on_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codec = ActionCodec(RulesetConfig())
    network, learner = _trained(codec)
    current = tmp_path / "current.pt"
    save_checkpoint(
        current,
        network,
        ruleset=codec.config.identifier,
        iteration=3,
        optimizer_state=learner.optimizer_state(),
        codec=codec,
    )
    drop_action = next(
        i for i, t in enumerate(codec.catalog) if t.action_id == "finish_agent_turn"
    )
    older = tmp_path / "older.pt"
    torch.save(
        _forge_older(
            torch.load(current, weights_only=True),
            drop_action=drop_action,
            drop_column=OBSERVATION_SEGMENTS[0].length - 1,
        ),
        older,
    )
    migrated, loaded = load_checkpoint(older)
    assert loaded.migration is not None
    described = loaded.migration.describe()

    info = widen_checkpoint(older, tmp_path / "slots.pt")

    # The widened file is at the current versions; the move is not lost.
    assert info.migration is None
    assert info.metadata["widened_migration"] == described
    widened, _ = load_checkpoint(tmp_path / "slots.pt")
    observations = torch.randint(0, 9, (4, OBSERVATION_SIZE), dtype=torch.int32)
    masks = torch.ones(4, codec.size, dtype=torch.int8)
    with torch.no_grad():
        assert torch.equal(
            widened(observations, masks)[0], migrated(observations, masks)[0]
        )
    # A current-version source records nothing.
    plain = widen_checkpoint(current, tmp_path / "plain.pt")
    assert "widened_migration" not in plain.metadata

    assert (
        checkpoint_main(
            ["widen", "--arch", "mlp_slots", str(older), str(tmp_path / "cli.pt")]
        )
        == 0
    )
    assert f"{older}: {described}" in capsys.readouterr().out


class _ExtraParameterSlots(MlpSlotsNetwork):
    """A widened class with one more new weight than the embedding."""

    def __init__(self, action_size: int, **kwargs: Any) -> None:
        super().__init__(action_size, **kwargs)
        self.extra = torch.nn.Parameter(torch.zeros(1))


class _MissingBiasSlots(MlpSlotsNetwork):
    """A widened class that cannot hold one of the source's weights."""

    def __init__(self, action_size: int, **kwargs: Any) -> None:
        super().__init__(action_size, **kwargs)
        self.value_head = torch.nn.Linear(self.hidden[-1], 1, bias=False)


@pytest.mark.parametrize(
    ("widened_class", "reported"),
    [
        (_ExtraParameterSlots, r"missing \[[^]]*'extra'[^]]*\] and unexpected \[\]"),
        (_MissingBiasSlots, r"unexpected \['value_head\.bias'\]"),
    ],
    ids=["extra-parameter", "missing-bias"],
)
def test_widening_refuses_anything_but_the_embedding_being_new(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    widened_class: type[MlpSlotsNetwork],
    reported: str,
) -> None:
    codec = ActionCodec(RulesetConfig())
    torch.manual_seed(0)
    source = tmp_path / "mlp.pt"
    save_checkpoint(
        source,
        PolicyValueNetwork(codec.size, hidden=(16,)),
        ruleset=codec.config.identifier,
        iteration=1,
        codec=codec,
    )
    monkeypatch.setattr(checkpoint_module, "MlpSlotsNetwork", widened_class)
    destination = tmp_path / "slots.pt"
    with pytest.raises(
        RuntimeError, match=f"widening expected only slot_embed.weight(?s:.*){reported}"
    ):
        widen_checkpoint(source, destination)
    assert not destination.exists()
