"""The ``entity`` network: feature tables, wiring, caches, checkpoints, seats.

docs/entity-network-plan.md stage P1. The MLP files must keep loading and
playing next to it (the user's requirement of 2026-10-12), so the seat test
plays both kinds in one game.
"""

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from tests.support.observation_growth import NEW_SEGMENTS, growth_since_v34

torch = pytest.importorskip("torch")

from torch import Tensor  # noqa: E402

from dune_imperium import BaseGame, RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    BATTLE_CARD_IDS,
    CONFLICT_IDS,
    CONTRACT_IDS,
    FACTION_IDS,
    IMPERIUM_IDENTITIES,
    INTRIGUE_IDS,
    LEADER_IDS,
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
    PERSONAL_CARD_IDS,
    POST_IDS,
    RESEARCH_SPACE_IDS,
    SKILL_IDS,
    SPACE_IDS,
    segment_slice,
)
from dune_imperium.agents import StateAgent  # noqa: E402
from dune_imperium.agents.network_search_agent import NetworkSearchAgent  # noqa: E402
from dune_imperium.agents.registry import CHECKPOINT_PREFIX, make_agent  # noqa: E402
from dune_imperium.content.bloodlines.tech import TECH_IDS  # noqa: E402
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS  # noqa: E402
from dune_imperium.content.imperium.leaders import IMPERIUM_LEADERS  # noqa: E402
from dune_imperium.content.rulesets import content_for  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.action_shapes import Source, Verb  # noqa: E402
from dune_imperium.simulation.runner import run_policy_game  # noqa: E402
from dune_imperium.training import (  # noqa: E402
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
    entity_features,  # noqa: E402
)
from dune_imperium.training import checkpoint as checkpoint_module  # noqa: E402
from dune_imperium.training import entity_network as entity_network_module  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    observation_layout,
    save_checkpoint,
    template_keys,
)
from dune_imperium.training.distill import legal_log_probs  # noqa: E402
from dune_imperium.training.entity_features import (  # noqa: E402
    _LEADER_OF_FACE,
    FEATURE_DIGEST,
    Vocabulary,
    resolve,
    resolve_argument,
    vocabularies,
)
from dune_imperium.training.entity_network import (  # noqa: E402
    EntityNetwork,
    action_parts,
    action_vocabulary,
    legacy_inputs,
)
from dune_imperium.training.network import (  # noqa: E402
    PolicyValueNetwork,
    build_network,
)
from dune_imperium.training.slots import SLOT_KEYS  # noqa: E402

# Changing the feature table or how ids are read must change this
# deliberately (with FEATURE_VERSION when the reflection changes): an entity
# checkpoint stores the digest and is refused under another one, so a card
# data fix also retires every entity file written before it.
# Stage B3b-2: a Commander's Skill prints the Reveal's Skill trash (the
# ``printed`` hint reads the skill vocabulary too). Stage B3c-1: the Endgame
# wild match's target row reads its card as a battle or Conflict card.
# Stage B3c-2a: a research space prints its icons and bonuses (``printed``).
# Stage B3d-1: so do the Conflict card of a reward window and the Intrigue
# card of a lines window. Stage B3d-2a: and the Faction whose Influence
# track opens a Spy window (the Emperor's); a Scouts line's printed item is
# a label (``SCOUTS_ITEM_IDS``; a Scouts mission's too, stage B3d-2b).
# Stage B3d-3: a refusal's ``of`` is a label. Engine audit 2026-10-22, P4:
# Interstellar Conspiracy's record is two icons; P6: Guild Envoy's draw is
# an armed icon; OQ-128: Overthrow gains two Influence instead of one.
# Observation v35 (stage P2a, user approval 2026-10-27): the original game's
# entities join the personal, Conflict, space and Leader vocabularies at
# their end, with the columns only they use; every Uprising row and the
# scale of every column an Uprising entity uses stay those of 12294215
# (405 rows compared; ``entity_features._table``). Stage P2b: each original
# Leader's records join its row as the stage brings them (Duke Leto, Helena
# Richese, Paul Atreides, Baron Harkonnen). Observation v37 (stage P3a): the
# original game's 46 Imperium cards join the personal vocabulary and its 34
# Intrigue cards the Intrigue one, each card's records as it is transcribed;
# Uprising's 405 rows unchanged (compared 2026-10-28). The digest moves with
# every original card transcribed in stage P3.
_GOLDEN_DIGEST = "5d70ea7f4d5413fb0c08f7fe70d30911bd0e0db91226393a30ecc2c5cf383151"
_BASE = RulesetConfig()
_FULL = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
)
# Every option: the catalog with every argument kind (Subcommittees, Scouts).
_EVERY_OPTION = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
    leader_draft=True,
)


def _network(
    config: RulesetConfig, seed: int = 0, *, own_actions: bool = False
) -> EntityNetwork:
    """A small network whose zero-initialised parts carry values too."""

    torch.manual_seed(seed)
    network = EntityNetwork(
        config,
        hidden=(32,),
        entity_width=16,
        seat_width=32,
        action_width=16,
        own_actions=own_actions,
    )
    with torch.no_grad():
        for parameter in (
            *network.entity_own.values(),
            network.slot_key_own,
            network.action_bias,
        ):
            parameter.normal_(0.0, 0.5)
        if network.action_own is not None:
            network.action_own.normal_(0.0, 0.5)
    return network.eval()


@pytest.fixture(scope="module")
def recorded() -> list[tuple[np.ndarray, np.ndarray, int]]:
    """``(observation, legal, action)`` of every 20th decision of a random game."""

    runner = SelfPlayRunner(_FULL, max_steps=3_000, record=True)
    result = runner.run(
        {"r": RandomBatchPolicy(seed=3)},
        (SelfPlaySpec(game_seed=5, lineup=("r",) * 4),),
    )
    steps = [step for episode in result.episodes for step in episode.steps]
    return [(step.observation, step.legal, step.action) for step in steps[::20]]


def _observations(recorded: list[tuple[np.ndarray, np.ndarray, int]]) -> Tensor:
    stacked: Tensor = torch.from_numpy(
        np.stack([row[0] for row in recorded]).astype(np.int32)
    )
    return stacked


# -- the feature tables ---------------------------------------------------------
def test_feature_tables_follow_the_observation_and_are_pinned() -> None:
    tables = vocabularies()
    # Each vocabulary lists its ids in the order the observation counts them.
    expected = {
        "personal": PERSONAL_CARD_IDS,
        "intrigue": INTRIGUE_IDS,
        "contract": CONTRACT_IDS,
        "conflict": CONFLICT_IDS,
        "battle": BATTLE_CARD_IDS,
        "space": SPACE_IDS,
        "post": POST_IDS,
        "leader": LEADER_IDS,
        "tech": TECH_IDS,
        "skill": SKILL_IDS,
        "research": RESEARCH_SPACE_IDS,
        "faction": FACTION_IDS,
    }
    assert {name: table.ids for name, table in tables.items()} == expected
    for name, table in tables.items():
        assert table.features.shape == (table.size, len(table.columns)), name
        assert np.all(np.isfinite(table.features)), name
        # Uprising's entities set the scales (v35): an original entity may
        # read past 1 in a column an Uprising one uses.
        uprising = [
            index
            for index, entity in enumerate(table.ids)
            if entity not in IMPERIUM_IDENTITIES
        ]
        assert np.abs(table.features[uprising]).max() <= 1.0, name
        # A column no member uses is dropped.
        assert np.all(np.abs(table.features).max(axis=0) > 0), name
    # Costs, effects and kinds are features (two cards share what they share).
    personal = tables["personal"]
    assert {"acquisition_cost", ":ImperiumCardEntry"} <= set(personal.columns)
    assert FEATURE_DIGEST == _GOLDEN_DIGEST


def test_what_an_entity_does_is_read_from_its_records() -> None:
    """Stage A8 (docs/composed-effects-plan.md 4.4): the effect columns come
    from the printed ability records, under the box each fills, and the
    definition fields that only name or tally them are left out."""

    tables = vocabularies()
    personal = set(tables["personal"].columns)
    assert {"agent:Ability", "reveal:Ability", "reveal_choice:Ability"} <= personal
    assert "agent.hook=beasts_spoils" in personal  # a flow kept as code
    assert not any(
        column.startswith(("agent_effect", "reveal_effects", "reveal_choice_effects"))
        for column in personal
    )
    assert {"first:Ability", "third:Ability"} <= set(tables["conflict"].columns)
    assert not any(c.startswith("rewards") for c in tables["conflict"].columns)
    assert "contract:Ability" in tables["contract"].columns
    assert "board0:Ability" in tables["space"].columns
    assert {"signet:Ability", "alternate_signet:Ability"} <= set(
        tables["leader"].columns
    )
    assert not any(c.startswith("ability=") for c in tables["tech"].columns)
    assert not any(c.startswith("bonus=") for c in tables["research"].columns)
    # The records tell every card, Leader and tile apart (copies aside),
    # the original game's eight Leaders too (stage P2b).
    assert {leader.leader_id for leader in IMPERIUM_LEADERS} == {
        leader.leader_id
        for leader in content_for(RulesetConfig(base_game=BaseGame.IMPERIUM)).leaders
    }
    # An original card not yet transcribed (stage P3) has only its identity
    # entry, no record to tell it apart.
    untranscribed = {
        entry.card.card_id
        for entry in IMPERIUM_BASE_CARDS
        if not entry.play_data_complete
    }
    for name in ("personal", "leader", "tech", "space", "conflict"):
        table = tables[name]
        rows = [
            row.tobytes()
            for entity, row in zip(table.ids, table.features, strict=True)
            if entity not in untranscribed
        ]
        assert len(set(rows)) == len(rows), name


def test_an_action_is_built_from_its_shape() -> None:
    """Two actions with one verb share its part, whichever effect they answer."""

    trash_agent = set(action_parts("trash_agent_card"))
    trash_reveal = set(action_parts("trash_reveal_card"))
    assert "verb=trash" in trash_agent & trash_reveal
    assert trash_agent != trash_reveal
    catalog = ActionCodec(_EVERY_OPTION).catalog
    vocabulary = action_vocabulary(template_keys(catalog))
    assert len({action_parts(kind) for kind in vocabulary.kinds}) == len(
        vocabulary.kinds
    )


def test_ids_resolve_by_the_argument_that_names_them() -> None:
    def vocabulary(found: tuple[str, int] | None) -> str | None:
        return None if found is None else found[0]

    # ``deliver_supplies`` is a space and a contract tile.
    assert vocabulary(resolve("deliver_supplies", ("space",))) == "space"
    assert vocabulary(resolve("deliver_supplies", ("contract",))) == "contract"
    # The codec writes a starting card relative to its owner.
    assert resolve("starter:dagger:0") == (
        "personal",
        PERSONAL_CARD_IDS.index("dagger"),
    )
    # A battle card's id is often a Conflict's id too.
    assert (
        vocabulary(resolve_argument("flip_battle_card", "card_id", "propaganda"))
        == "battle"
    )
    assert vocabulary(resolve("propaganda")) == "conflict"
    # A Subcommittee shares an Intrigue card's id but names a choice.
    assert vocabulary(resolve("leverage")) == "intrigue"
    assert resolve_argument("join_subcommittee", "subcommittee_id", "leverage") is None
    assert resolve("no_such_id") is None


def test_every_catalog_argument_is_an_entity_of_its_kind_or_a_label() -> None:
    hinted = {
        "space_id": {"space", "research"},
        "post_id": {"post"},
        "infiltrate_post_id": {"post"},
        "tech_id": {"tech"},
        "leader_id": {"leader"},
        "intrigue_card_id": {"intrigue"},
        "matching_card_id": {"battle"},
        "card_id": {"personal", "intrigue", "battle", "conflict"},
        "instance_id": {"personal", "intrigue", "contract"},
        # Stage B3: an effect row's printed entity.
        "printed": {
            "personal",
            "space",
            "leader",
            "tech",
            "contract",
            "skill",
            # A research space (stage B3c-2a).
            "research",
            # A reward window's Conflict card, a lines window's Intrigue card
            # (stage B3d-1).
            "conflict",
            "intrigue",
            # The Emperor's Influence track, opening a Spy window (B3d-2a).
            "faction",
        },
    }
    seen: dict[str, set[str | None]] = {}
    labels: set[str] = set()
    for template in ActionCodec(_EVERY_OPTION).catalog:
        source = dict(template.arguments).get("source")
        for key, value in template.arguments:
            if isinstance(value, str):
                found = resolve_argument(template.action_id, key, value, source)
                seen.setdefault(key, set()).add(None if found is None else found[0])
                if key == "printed" and found is None:
                    labels.add(value)
    for key, allowed in hinted.items():
        # Stage B3 shows the Agent boxes' Intrigue payments by their target
        # rows, so a catalog may hold no ``intrigue_card_id`` any more.
        assert seen.get(key, set()) - {None} <= allowed, key
    # Every printed entity of an effect row is an entity (stage B3), but the
    # Reveal's markets, which no card or space prints (stage B3b-2), the
    # windows a card is played in (stage B3c-1), and the Scouts lines that
    # open a Spy window (stage B3d-2a) and the Scouts missions whose plain
    # way is an effect row (stage B3d-2b), which have no vocabulary; since
    # stage B3d-3 the Contract market a confirmation names, and the Scouts
    # items whose trash, choice or market a refusal answers; since stage
    # B3d-4 the Tleilaxu track's space that owes a draw (its trigger) and the
    # Sardaukar Commander a recruit takes.
    from dune_imperium.content.arrakeen_scouts import (
        AUCTIONS,
        EVENTS,
        SALES,
        missions_for,
        scouts_pool,
    )
    from dune_imperium.rules.scouts_effects import scouts_spy_items, scouts_trash_items

    missions = missions_for(scouts_pool(immortality=True), choam=True)
    assert labels == {
        "imperium_row",
        "reserve",
        "set_aside",
        "tleilaxu_row",
        "plot",
        "combat",
        "endgame",
        "conflict_end",
        "turn_start",
        "wild_icon",
        *scouts_spy_items(),
        *(mission.mission_id for mission in missions),
        "contract_market",
        *scouts_trash_items(),
        *(event.event_id for event in EVENTS),
        *(sale.sale_id for sale in SALES),
        *(auction.auction_id for auction in AUCTIONS),
        "tleilaxu_track",
        "sardaukar_commander",
    }
    # Every Imperium card a seat can play or buy is an entity, not a label.
    assert "personal" in seen["card_id"]
    assert seen["subcommittee_id"] == {None}


def test_actions_built_from_the_same_parts_are_copies_of_one_card() -> None:
    """Two catalog rows only the per-action bias tells apart name two copies
    of the same card (``imperium:x:0`` and ``imperium:x:1``), never two
    different choices."""

    network = EntityNetwork(_EVERY_OPTION, hidden=(8,))
    catalog = ActionCodec(_EVERY_OPTION).catalog

    def without_copy(index: int) -> object:
        # A leader's two faces are one leader card; only one is up at a
        # time, so their effect rows never meet (stage B3).
        template = catalog[index]
        return template.action_id, tuple(
            (
                key,
                _LEADER_OF_FACE.get(value, re.sub(r":\d+$", "", value))
                if isinstance(value, str)
                else value,
            )
            for key, value in template.arguments
        )

    twins = network.twin_actions()
    assert twins  # the copies are there
    different = [
        [catalog[index] for index in rows]
        for rows in twins
        if len({without_copy(index) for index in rows}) > 1
    ]
    assert not different


# -- the network's wiring ------------------------------------------------------
# What each count segment counts, written here from the observation's
# meaning (``observation_encoding`` writes a count at its id's index in the
# vocabulary's id list); seat segments by their name after ``seat<k>_``.
_COUNTED = {
    **dict.fromkeys(
        (
            "hand_public",
            "deck_pool",
            # v38 (OQ-145): the depth of each public deck-top card.
            "deck_public_top",
            "in_play",
            "discard",
            "trashed",
            "private_hand",
            "private_peeked_card",
            "private_agent_card_pick",
            "private_effect_pick_card",
            "imperium_removed",
        ),
        "personal",
    ),
    **dict.fromkeys(
        (
            "intrigue_resolving",
            "intrigue_discard",
            "intrigue_faceup",
            "private_intrigue",
            "private_peeked_intrigue",
            "private_effect_pick_intrigue",
        ),
        "intrigue",
    ),
    **dict.fromkeys(
        (
            "face_up_contracts",
            "sardaukar_contracts",
            "contract_trash",
            "active_contracts",
            "completed_contracts",
        ),
        "contract",
    ),
    "tech": "tech",
    "tech_trash": "tech",
    "skills": "skill",
    "skill_face_up": "skill",
    "battle_cards": "battle",
    "spy_posts": "post",
    "alliances": "faction",
    # Stage B3: the targets picked so far (the B3c-1 review).
    "private_effect_pick_faction": "faction",
    "private_effect_pick_post": "post",
    "private_effect_pick_tech": "tech",
    "private_effect_pick_battle": "battle",
    "private_effect_pick_second_faction": "faction",
    # Stage B3d-2a: Long Live the Fighters' card to draw.
    "private_effect_pick_personal": "personal",
}


def test_each_count_zone_feeds_its_own_entities() -> None:
    network = _network(_BASE)
    sizes = {name: table.size for name, table in vocabularies().items()}
    found = set()
    with torch.no_grad():
        entities = network.entity_table()
        for segment in OBSERVATION_SEGMENTS:
            name = segment.name
            if name.startswith("seat") and name[4].isdigit():
                name = name.split("_", 1)[1]
            vocabulary = _COUNTED.get(name)
            members = (
                {0, segment.length // 2, segment.length - 1} if vocabulary else {0}
            )
            for member in members:
                observation = torch.zeros(1, OBSERVATION_SIZE)
                observation[0, segment.offset + member] = 2.0
                vectors = network._zone_vectors(observation, entities)[0]
                live = vectors.abs().sum(dim=1).nonzero().flatten()
                if vocabulary is None:
                    assert not len(live), segment.name
                    continue
                assert segment.length == sizes[vocabulary], segment.name
                assert len(live) == 1, (segment.name, member)
                expected = entities[network.entity_offsets[vocabulary] + member]
                assert torch.equal(vectors[live[0]], 2.0 * expected), segment.name
                found.add(name)
    assert found == set(_COUNTED)


def test_inference_and_training_paths_compute_the_same_function(
    recorded: list[tuple[np.ndarray, np.ndarray, int]],
) -> None:
    network = _network(_FULL)
    observations = _observations(recorded)
    actions = torch.tensor([0, 17, network.action_size - 1, 17, 905])
    masks = torch.zeros(len(recorded), network.action_size, dtype=torch.int8)
    for row, (_, legal, _) in enumerate(recorded):
        masks[row, torch.from_numpy(legal.astype(np.int64))] = 1
    with torch.no_grad():
        hidden = network.trunk(observations)
        logits = network.action_logits(hidden, actions)
        full, values = network(observations, torch.ones_like(masks))
        masked, _ = network(observations, masks)
        cached_again = network.action_logits(network.trunk(observations), actions)
    assert torch.equal(logits, cached_again)
    trained_hidden = network.trunk(observations)
    trained_logits = network.action_logits(trained_hidden, actions)
    torch.testing.assert_close(trained_hidden.detach(), hidden)
    torch.testing.assert_close(trained_logits.detach(), logits)
    torch.testing.assert_close(full[:, actions], logits)
    torch.testing.assert_close(values, network.value_head(hidden).squeeze(-1))
    assert torch.all(masked[masks == 0] < -1e8)
    assert torch.equal(masked[masks == 1], full[masks == 1])

    # Per-row index lists (distillation's padded legal sets).
    index = torch.stack([actions.roll(row) for row in range(len(recorded))])
    with torch.no_grad():
        rows = network.row_action_logits(hidden, index)
        for row in range(len(recorded)):
            torch.testing.assert_close(
                rows[row], network.action_logits(hidden[row : row + 1], index[row])[0]
            )
        valid = torch.ones_like(index, dtype=torch.bool)
        valid[:, -1] = False
        log_probs = legal_log_probs(network, hidden, index, valid)
    torch.testing.assert_close(
        log_probs[:, :-1].exp().sum(dim=1), torch.ones(len(recorded))
    )


def test_the_inference_cache_follows_every_weight_change(
    recorded: list[tuple[np.ndarray, np.ndarray, int]],
) -> None:
    network = _network(_FULL)
    observations = _observations(recorded)
    actions = torch.arange(0, network.action_size, 997)

    def outputs() -> tuple[Tensor, Tensor]:
        with torch.no_grad():
            hidden = network.trunk(observations)
            return hidden, network.action_logits(hidden, actions)

    before = outputs()
    optimizer = torch.optim.SGD(network.parameters(), lr=0.1)
    hidden = network.trunk(observations)
    loss = network.action_logits(hidden, actions).square().mean() + hidden.mean()
    loss.backward()  # type: ignore[no-untyped-call]
    optimizer.step()
    stepped = outputs()
    assert not torch.equal(before[1], stepped[1])
    with torch.enable_grad():
        hidden = network.trunk(observations)
        expected = network.action_logits(hidden, actions).detach()
    torch.testing.assert_close(stepped[1], expected)

    # Copied into place, and assigned (new parameter objects).
    for seed, assign in ((7, False), (8, True)):
        other = _network(_FULL, seed=seed)
        with torch.no_grad():
            hidden = other.trunk(observations)
            expected = other.action_logits(hidden, actions)
        network.load_state_dict(other.state_dict(), assign=assign)
        loaded = outputs()
        assert torch.equal(loaded[0], hidden), assign
        assert torch.equal(loaded[1], expected), assign


def test_a_small_batch_is_learned(
    recorded: list[tuple[np.ndarray, np.ndarray, int]],
) -> None:
    """The policy and value can fit a batch (gradients reach every encoder)."""

    torch.manual_seed(0)
    network = EntityNetwork(
        _FULL, hidden=(64,), entity_width=16, seat_width=32, action_width=32
    ).train()
    observations = _observations(recorded)
    legal = [torch.from_numpy(row[1].astype(np.int64)) for row in recorded]
    width = max(len(row) for row in legal)
    index = torch.zeros(len(legal), width, dtype=torch.long)
    valid = torch.zeros(len(legal), width, dtype=torch.bool)
    for row, actions in enumerate(legal):
        index[row, : len(actions)] = actions
        valid[row, : len(actions)] = True
    chosen = valid.sum(dim=1) - 1  # the last legal action of each row
    keep = chosen > 0
    targets = torch.where(torch.arange(len(legal)) % 2 == 0, 1.0, -1.0)
    optimizer = torch.optim.Adam(network.parameters(), lr=3e-3)

    def losses() -> tuple[Tensor, Tensor]:
        hidden = network.trunk(observations)
        log_probs = legal_log_probs(network, hidden, index, valid)
        policy = -log_probs[keep, chosen[keep]].mean()
        value = (network.value_head(hidden).squeeze(-1) - targets).square().mean()
        return policy, value

    first = [loss.item() for loss in losses()]
    for _ in range(120):
        policy, value = losses()
        optimizer.zero_grad()
        (policy + value).backward()  # type: ignore[no-untyped-call]
        optimizer.step()
    last = [loss.item() for loss in losses()]
    assert last[0] < 0.1 * first[0]
    assert last[1] < 0.1 * first[1]
    for name, parameter in network.named_parameters():
        if name.startswith(("seat_encoder", "board_encoder", "private_encoder")):
            assert parameter.grad is not None and parameter.grad.abs().sum() > 0, name


# -- checkpoints ------------------------------------------------------------------
def _saved(
    tmp_path: Path,
    config: RulesetConfig,
    name: str = "entity.pt",
    *,
    own_actions: bool = False,
) -> Path:
    path = tmp_path / name
    save_checkpoint(
        path,
        _network(config, own_actions=own_actions),
        ruleset=config.identifier,
        iteration=3,
        codec=ActionCodec(config),
    )
    return path


def test_an_entity_file_loads_as_written(
    tmp_path: Path, recorded: list[tuple[np.ndarray, np.ndarray, int]]
) -> None:
    path = _saved(tmp_path, _FULL)
    network, info = load_checkpoint(path)
    assert isinstance(network, EntityNetwork)
    assert info.arch == "entity" and info.iteration == 3 and info.migration is None
    assert network.arch_spec() == _network(_FULL).arch_spec()
    observations = _observations(recorded)
    original = _network(_FULL)
    with torch.no_grad():
        assert torch.equal(network.trunk(observations), original.trunk(observations))
        hidden = original.trunk(observations)
        actions = torch.arange(0, original.action_size, 101)
        assert torch.equal(
            network.action_logits(hidden, actions),
            original.action_logits(hidden, actions),
        )


@pytest.mark.parametrize("own_actions", [False, True])
@pytest.mark.parametrize(("own", "target"), [(_BASE, _FULL), (_FULL, _BASE)])
def test_another_ruleset_keeps_every_shared_action_score(
    tmp_path: Path,
    recorded: list[tuple[np.ndarray, np.ndarray, int]],
    own: RulesetConfig,
    target: RulesetConfig,
    own_actions: bool,
) -> None:
    path = _saved(tmp_path, own, own_actions=own_actions)
    network, info = load_checkpoint(path, ruleset=target)
    again, _ = load_checkpoint(path, ruleset=target)
    assert isinstance(network, EntityNetwork)
    assert network.action_size == ActionCodec(target).size
    assert info.ruleset == own.identifier
    assert info.migration is not None and info.optimizer_state is None
    # Loading is deterministic: a part the file never had starts at zero.
    for (name, left), right in zip(
        network.state_dict().items(), again.state_dict().values(), strict=True
    ):
        assert torch.equal(left, right), name

    original = _network(own, own_actions=own_actions)
    old_keys = template_keys(ActionCodec(own).catalog)
    new_keys = template_keys(ActionCodec(target).catalog)
    old_index = {key: index for index, key in enumerate(old_keys)}
    shared = [
        (index, old_index[key])
        for index, key in enumerate(new_keys)
        if key in old_index
    ]
    fresh = [index for index, key in enumerate(new_keys) if key not in old_index]
    assert shared and (fresh or len(new_keys) < len(old_keys))
    observations = _observations(recorded)
    with torch.no_grad():
        hidden = original.trunk(observations)
        torch.testing.assert_close(network.trunk(observations), hidden)
        new, old = (torch.tensor(column) for column in zip(*shared, strict=True))
        torch.testing.assert_close(
            network.action_logits(hidden, new), original.action_logits(hidden, old)
        )
        if fresh:
            assert not network.action_bias[torch.tensor(fresh)].any()
            if network.action_own is not None:
                assert not network.action_own[torch.tensor(fresh)].any()
            # A new action is still scored from its parts.
            assert network.action_logits(hidden, torch.tensor(fresh)).abs().sum() > 0
    new_parts = action_vocabulary(new_keys)
    old_parts = action_vocabulary(old_keys)
    # Shape parts move by name (row 0 is the pad).
    for position, part in enumerate(new_parts.parts):
        row = network.part_embed.weight[position + 1]
        if part in old_parts.parts:
            assert torch.equal(
                row, original.part_embed.weight[old_parts.parts.index(part) + 1]
            )
        else:
            assert not row.any()


def test_own_action_vectors_start_at_zero_and_train(
    recorded: list[tuple[np.ndarray, np.ndarray, int]],
) -> None:
    """A fresh network with own action vectors computes what one without does
    (they start at zero), and the vectors receive gradient."""

    torch.manual_seed(5)
    plain = EntityNetwork(_BASE, hidden=(32,), entity_width=16, seat_width=32)
    torch.manual_seed(5)
    owning = EntityNetwork(
        _BASE, hidden=(32,), entity_width=16, seat_width=32, own_actions=True
    )
    assert plain.action_own is None and owning.action_own is not None
    assert owning.arch_spec() == {**plain.arch_spec(), "own_actions": True}
    rebuilt = build_network(owning.arch_spec(), owning.action_size)
    assert isinstance(rebuilt, EntityNetwork) and rebuilt.action_own is not None
    observations = torch.zeros(3, OBSERVATION_SIZE, dtype=torch.int32)
    actions = torch.tensor([0, 7, owning.action_size - 1])
    with torch.no_grad():
        assert torch.equal(
            plain.action_logits(plain.trunk(observations), actions),
            owning.action_logits(owning.trunk(observations), actions),
        )
    owning.action_logits(owning.trunk(observations), actions).sum().backward()  # type: ignore[no-untyped-call]
    grad = owning.action_own.grad
    assert grad is not None
    assert grad[actions].abs().sum() > 0
    others = torch.ones(owning.action_size, dtype=torch.bool)
    others[actions] = False
    assert not grad[others].any()


def test_an_entity_file_is_refused_under_another_feature_table(tmp_path: Path) -> None:
    arch = _network(_BASE).arch_spec()
    with pytest.raises(ValueError, match="feature table"):
        build_network({**arch, "feature_digest": "0" * 64}, ActionCodec(_BASE).size)
    # A file that stores no input names is named only for observation v31.
    path = _saved(tmp_path, _BASE)
    document = checkpoint_module._read(path)
    del document["entity_inputs"]
    document["observation_version"] = 30
    torch.save(document, path)
    with pytest.raises(ValueError, match="carries no input names"):
        load_checkpoint(path)


def test_a_changed_feature_table_moves_an_entity_file_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A card record fixed after a file was written (stage A8): the file is
    moved by name instead of refused. Every entity whose own features did not
    change computes exactly what it did, even where a column's scale moved; a
    new column starts at zero."""

    path = _saved(tmp_path, _BASE)
    original, _ = load_checkpoint(path)
    assert isinstance(original, EntityNetwork)
    with torch.no_grad():
        before = original.entity_table()
    tables = dict(vocabularies())
    tech = tables["tech"]
    raw = tech.features * np.array(tech.scales, dtype=np.float32)
    # Tile 1's first column grows past every other tile's (that column's
    # scale moves for all of them), the last column goes, and a new column
    # names tile 2 only.
    raw[1, 0] = np.abs(raw[:, 0]).max() * 2
    last = len(tech.columns) - 1
    touched = {1, 2} | set(np.nonzero(raw[:, last])[0].tolist())
    extra = np.zeros((tech.size, 1), dtype=np.float32)
    extra[2, 0] = 3.0
    raw = np.concatenate([raw[:, :last], extra], axis=1)
    scales = np.abs(raw).max(axis=0)
    tables["tech"] = Vocabulary(
        name="tech",
        ids=tech.ids,
        columns=(*tech.columns[:last], "test.new_column"),
        features=raw / scales,
        scales=tuple(float(value) for value in scales),
    )
    for module in (entity_features, entity_network_module):
        monkeypatch.setattr(module, "vocabularies", lambda: tables)
        monkeypatch.setattr(module, "FEATURE_DIGEST", "1" * 64)

    moved, info = load_checkpoint(path)
    assert isinstance(moved, EntityNetwork)
    assert info.migration is not None and info.migration.features_moved
    assert (
        info.migration.feature_columns_new,
        info.migration.feature_columns_dropped,
        info.migration.entities_new,
    ) == (1, 1, 0)
    assert "entity features" in info.migration.describe()
    assert not moved.state_dict()["entity_project.tech.weight"][:, -1].any()
    with torch.no_grad():
        after = moved.entity_table()
    start = moved.entity_offsets["tech"]
    for row in range(after.shape[0]):
        index = row - start
        if 0 <= index < tech.size and index in touched:
            continue
        torch.testing.assert_close(after[row], before[row])
    assert not torch.allclose(after[start + 1], before[start + 1])


def test_an_entity_file_without_its_feature_table_is_refused_under_another(
    tmp_path: Path,
) -> None:
    """A file written before files stored their feature table cannot be moved
    by name, so another table still refuses it."""

    path = _saved(tmp_path, _BASE)
    document = checkpoint_module._read(path)
    del document["entity_tables"]
    document["arch"]["feature_digest"] = "0" * 64
    torch.save(document, path)
    with pytest.raises(ValueError, match="feature table"):
        load_checkpoint(path)


def _after_v31(segment: str) -> bool:
    """Whether an observation segment was appended after v31: v32's deck pools,
    v33's picked Agent card (stage B1) and picked effect (stage B3), and v34's
    base-game flag."""

    return (
        segment.endswith("_deck_pool")
        or segment.startswith(("private_agent_card_pick", "private_effect_pick"))
        or segment == "base_game"
        or segment in NEW_SEGMENTS
    )


def test_the_v31_input_names_are_pinned() -> None:
    """``legacy_inputs`` names a v31 file's inputs from today's tables; pinned
    so that a later change of the slot table or the zone list cannot change
    what "v31" means. The digests were checked against master's real v31
    network (independent review 2026-10-14: every board, private and seat
    input and the 1,140 slot keys identical, in order); the keys' digest is
    the v31 slot table's own golden digest."""

    # Today's layout without the later segments and v35's columns.
    grown = {
        segment.name: growth_since_v34(segment) for segment in OBSERVATION_SEGMENTS
    }
    layout = [
        (name, offset, length - grown[name])
        for name, offset, length in observation_layout()
        if not _after_v31(name)
    ]
    names, keys = legacy_inputs(31, layout, 64)

    def digest(rows: Sequence[str]) -> str:
        return hashlib.sha256("\n".join(rows).encode()).hexdigest()

    assert {encoder: len(rows) for encoder, rows in names.items()} == {
        "seat": 1_329,
        "board": 1_659,
        "private": 576,
    }
    assert digest(names["board"]) == (
        "636b4dbc0a46475cf6b69d9d7d656e8728183cdefce6beee8f24baa544a396c2"
    )
    assert digest(names["private"]) == (
        "e7fae9c7a8eca45cdc03351a97f25e2bb0cd16be3e5c0425d5cc1f0778ed81d7"
    )
    assert digest(names["seat"]) == (
        "cbd15c29f653067823b54dcc7fe0bca8569da2ea0aba4ee820f7283a87112cca"
    )
    assert len(keys) == 1_140
    assert digest(keys) == (
        "53913e6515a83e29c0e835d6277841b143fcaa07a5012645d650d91f9e7a774d"
    )
    with pytest.raises(ValueError, match="carries no input names"):
        legacy_inputs(30, layout, 64)


def test_a_v31_entity_file_moves_onto_v32_and_computes_the_same_function(
    tmp_path: Path, recorded: list[tuple[np.ndarray, np.ndarray, int]]
) -> None:
    """A file written before observation v32 (no stored input names, no deck
    pool zones, no v33 picked Agent card, no v32 slot fields) loads with every
    old input in its new place and the new ones at zero: on observations whose
    deck pools and picked card are empty it scores exactly as before (the v32
    slot fields' columns are still read as numbers too,
    ``FIELDS_KEPT_RAW``)."""

    network = _network(_FULL)
    path = _saved(tmp_path, _FULL)
    document = checkpoint_module._read(path)
    # Cut the file down to what v31 code wrote (without v35's columns).
    grown = {
        segment.name: growth_since_v34(segment) for segment in OBSERVATION_SEGMENTS
    }
    old_layout = []
    offset = 0
    for name, _, length in document["observation_layout"]:
        if not _after_v31(name):
            old_layout.append((name, offset, length - grown[name]))
            offset += length - grown[name]
    old_names, old_keys = legacy_inputs(31, old_layout, network.entity_width)
    state = dict(document["state_dict"])
    for encoder, key in (
        ("seat", "seat_encoder.0.weight"),
        ("board", "board_encoder.0.weight"),
        ("private", "private_encoder.0.weight"),
    ):
        where = {name: index for index, name in enumerate(network.input_names[encoder])}
        state[key] = state[key][:, [where[name] for name in old_names[encoder]]]
    key_index = {key: index for index, key in enumerate(SLOT_KEYS)}
    state["slot_key_own"] = state["slot_key_own"][
        [*(key_index[key] for key in old_keys), len(SLOT_KEYS)]
    ]
    del document["entity_inputs"]
    document.pop("slot_keys", None)
    document.update(
        state_dict=state,
        observation_version=31,
        observation_layout=old_layout,
        observation_size=old_layout[-1][1] + old_layout[-1][2],
    )
    torch.save(document, path)

    moved, info = load_checkpoint(path)
    assert isinstance(moved, EntityNetwork)
    assert info.migration is not None
    assert info.migration.from_observation_version == 31
    # Four deck-pool zones (v32), the picked Agent card's zone and graft
    # flag (v33, stage B1), the picked effect's card zone, verb, source,
    # box and target count (v33, stage B3) and the seven zones of its picked
    # targets (v33, the B3c-1 review; a personal card, the B3d-2a review),
    # the base-game flag (v34, a raw board input), and v35's raw columns
    # (Carthag's Control in the seat encoder; three Reserve stacks, two Maker
    # spaces and the Mentat's resting flag on the board) and its two Mentat
    # seat fields, v36's raw Masterstroke columns (four seats on the board,
    # four Factions private) and v38's: the public deck-top zone of a seat,
    # the 42 barred spaces and two turn flags of four seats (raw, on the
    # board) are the inputs the file never had.
    assert info.migration.observation_new == network.entity_width * (1 + 3) + (
        network.entity_width + 1
    ) + network.entity_width + len(Verb) + len(Source) + 2 + 7 * (
        network.entity_width
    ) + 1 + (1 + 3 + 2 + 1) + 2 * network.entity_width + (4 + 4) + (
        network.entity_width + 4 * 42 + 4 * 2
    )
    assert info.migration.observation_dropped == 0
    observations = _observations(recorded).clone()
    pools = slice(segment_slice("seat0_deck_pool").start, OBSERVATION_SIZE)
    observations[:, pools] = 0
    actions = torch.arange(0, moved.action_size, 211)
    with torch.no_grad():
        # The original with its v32-only weights cleared is the v31 file.
        original = _network(_FULL)
        for encoder, layer in (
            ("seat", original.seat_encoder[0]),
            ("board", original.board_encoder[0]),
            ("private", original.private_encoder[0]),
        ):
            assert isinstance(layer, torch.nn.Linear)
            new = [
                index
                for index, name in enumerate(original.input_names[encoder])
                if name not in set(old_names[encoder])
            ]
            layer.weight[:, new] = 0.0
        # Slot keys of an embedded field the file never had (the v33
        # decision kinds of stage B2's reward windows) start at zero too.
        unknown = [
            SLOT_KEYS.index(f"decision_kind:{kind}")
            for kind in ("combat_reward_icons", "contract_reward_icons")
        ]
        assert not {SLOT_KEYS[index] for index in unknown} & set(old_keys)
        original.slot_key_own[unknown] = 0.0
        hidden = original.trunk(observations)
        assert torch.equal(moved.trunk(observations), hidden)
        assert torch.equal(
            moved.action_logits(hidden, actions),
            original.action_logits(hidden, actions),
        )


_V38_SEGMENTS = (
    *(f"seat{seat}_deck_public_top" for seat in range(4)),
    "voice_blocks",
    "card_turn_flags",
)


def test_a_v37_entity_file_moves_onto_v38_with_the_new_inputs_at_zero(
    tmp_path: Path, recorded: list[tuple[np.ndarray, np.ndarray, int]]
) -> None:
    """A file written under observation v37 knows none of v38's inputs (the
    public deck-top zone of a seat, the Voice's barred spaces and the card turn
    flags): every older input keeps its place by name, the new ones start at
    zero, so the file computes its own function whatever they read."""

    path = _saved(tmp_path, _FULL)
    document = checkpoint_module._read(path)
    state = dict(document["state_dict"])
    inputs: dict[str, list[str]] = {}
    for encoder, key in (
        ("seat", "seat_encoder.0.weight"),
        ("board", "board_encoder.0.weight"),
        ("private", "private_encoder.0.weight"),
    ):
        names = document["entity_inputs"][encoder]
        kept = [
            index
            for index, name in enumerate(names)
            if not name.startswith(
                ("zone:deck_public_top:", "raw:voice_blocks:", "raw:card_turn_flags:")
            )
        ]
        state[key] = state[key][:, kept]
        inputs[encoder] = [names[index] for index in kept]
    layout = [
        row for row in document["observation_layout"] if row[0] not in _V38_SEGMENTS
    ]
    document.update(
        state_dict=state,
        entity_inputs=inputs,
        observation_version=37,
        observation_layout=layout,
        observation_size=layout[-1][1] + layout[-1][2],
    )
    torch.save(document, path)

    moved, info = load_checkpoint(path)
    assert isinstance(moved, EntityNetwork)
    assert info.migration is not None
    assert info.migration.from_observation_version == 37
    assert info.migration.to_observation_version == OBSERVATION_VERSION
    # One zone of a seat, 42 spaces and two flags for each of four seats.
    assert info.migration.observation_new == moved.entity_width + 4 * 42 + 4 * 2
    assert info.migration.observation_dropped == 0
    assert layout[-1][0] == "private_masterstroke"

    observations = _observations(recorded).clone()
    new = torch.cat(
        [
            torch.arange(segment_slice(name).start, segment_slice(name).stop)
            for name in _V38_SEGMENTS
        ]
    )
    # Uprising's own columns: a game without a public top has none of them.
    cut = observations.clone()
    cut[:, new] = 0
    noisy = observations.clone()
    noisy[:, new] = 3
    original = _network(_FULL)
    actions = torch.arange(0, moved.action_size, 211)
    with torch.no_grad():
        hidden = original.trunk(cut)
        assert torch.equal(moved.trunk(cut), hidden)
        assert torch.equal(moved.trunk(noisy), hidden)
        assert torch.equal(
            moved.action_logits(moved.trunk(noisy), actions),
            original.action_logits(hidden, actions),
        )


# -- seats ------------------------------------------------------------------------
def test_entity_and_mlp_files_play_a_game_together(tmp_path: Path) -> None:
    entity = _saved(tmp_path, _BASE)
    torch.manual_seed(0)
    mlp = tmp_path / "mlp.pt"
    save_checkpoint(
        mlp,
        PolicyValueNetwork(ActionCodec(_BASE).size, hidden=(32,)),
        ruleset=_BASE.identifier,
        iteration=1,
        codec=ActionCodec(_BASE),
    )
    agents = [
        make_agent(f"{CHECKPOINT_PREFIX}{entity}", 0, _BASE),
        make_agent(f"{CHECKPOINT_PREFIX}{mlp}", 1, _BASE),
        make_agent(f"{CHECKPOINT_PREFIX}{entity}", 2, _BASE),
        make_agent("heuristic", 3),
    ]
    game = run_policy_game(UprisingRulesEngine(), _BASE, 4, agents)
    assert game.state.phase is GamePhase.FINISHED


def test_a_search_seat_reads_an_entity_file(tmp_path: Path) -> None:
    path = str(_saved(tmp_path, _FULL))
    agent = NetworkSearchAgent(path, seed=0, config=_BASE, rollouts=2, candidates=2)
    assert isinstance(agent, StateAgent)
    assert isinstance(agent.greedy.network, EntityNetwork)
    engine = UprisingRulesEngine()
    state = engine.reset(_BASE, 2)
    chance = ChanceResolver(seed=2)
    heuristics = [make_agent("heuristic", seat) for seat in range(4)]
    searched = 0
    while searched < 3 and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        view = engine.observe(state, decision.owner)
        if decision.owner == 0 and len(actions) > 1:
            choice = agent.choose_action_with_state(state, view, actions)
            searched += 1
        else:
            choice = heuristics[decision.owner].choose_action(view, actions)
        assert choice in actions
        state = engine.apply(state, choice).state
    assert searched == 3
