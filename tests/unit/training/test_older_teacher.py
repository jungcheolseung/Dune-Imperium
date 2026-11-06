"""An older codec's network answering current decisions (the stage B retrain)."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import (  # noqa: E402
    ActionCodec,
    _normalize_arguments,
)
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    encode_player_view,
)
from dune_imperium.agents.heuristic_agent import HeuristicAgent  # noqa: E402
from dune_imperium.agents.registry import is_agent_kind, make_agent  # noqa: E402
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision  # noqa: E402
from dune_imperium.core.state import GameState  # noqa: E402
from dune_imperium.rules.agent_turn import (  # noqa: E402
    CARD_PICK_ACTION,
    agent_card_pick_actions,
    executable_placements,
)
from dune_imperium.rules.engine import UprisingRulesEngine  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.collect import LEARNER  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.older_distill import older_shard  # noqa: E402
from dune_imperium.training.older_teacher import (  # noqa: E402
    FALLBACK,
    NETWORK,
    OlderNetwork,
    OlderNetworkAgent,
    OlderTeacher,
    TemplateKey,
    load_older_network,
    older_row,
)
from dune_imperium.training.selfplay import SelfPlaySpec  # noqa: E402

_RULES = RulesetConfig()
_ENGINE = UprisingRulesEngine()


def _first_turn() -> tuple[GameState, int]:
    """A base game's first Agent turn (its card pick) and the seat to move."""

    state = _ENGINE.reset(_RULES, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := _ENGINE.current_decision(state), ChanceDecision):
        state = _ENGINE.apply(state, chance.resolve(decision)).state
    assert decision is not None
    return state, decision.owner


def _key(action_id: str, arguments: tuple[tuple[str, object], ...]) -> TemplateKey:
    return action_id, arguments


def _older(rows: dict[TemplateKey, int]) -> OlderNetwork:
    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(_RULES).size, hidden=(16,)).eval()
    return OlderNetwork(
        network=network,
        weight=torch.randn(max(len(rows), 1), 16) * 3.0,
        bias=torch.zeros(max(len(rows), 1)),
        rows=rows,
        codec_version=147,
        path="memory",
    )


def _template(action: DomainAction) -> TemplateKey:
    """An action's catalog template (starting cards named without a seat)."""

    return action.action_id, _normalize_arguments(action.arguments, action.actor)


def _placement_rows(state: GameState, player: int) -> dict[TemplateKey, int]:
    """Rows for the seat's whole placements, as an older codec named them."""

    placements = executable_placements(state, player)
    return {_template(placement): row for row, placement in enumerate(placements)}


def test_a_whole_action_finds_its_row_as_named_or_without_its_new_names() -> None:
    rows = {
        _key("gain_reveal_resources", (("spice", 1),)): 0,
        _key("trash_reveal_card", (("card_id", "x"), ("source", "y"))): 1,
        _key("recruit_reveal_troops", ()): 2,
    }
    named = DomainAction(
        "trash_reveal_card", 0, (("card_id", "x"), ("printed", "p"), ("source", "y"))
    )
    assert older_row(rows, named) == 1  # without ``printed`` only
    bare = DomainAction(
        "recruit_reveal_troops", 0, (("printed", "p"), ("source", "s"))
    )
    assert older_row(rows, bare) == 2  # without both
    exact = DomainAction("gain_reveal_resources", 1, (("spice", 1),))
    assert older_row(rows, exact) == 0
    assert older_row(rows, DomainAction("place_agent", 0, ())) is None


def test_a_card_pick_gets_the_sum_of_its_placements() -> None:
    state, player = _first_turn()
    legal = _ENGINE.legal_actions(state, player)
    assert any(action.action_id == CARD_PICK_ACTION for action in legal)
    rows = _placement_rows(state, player)
    others = [action for action in legal if action.action_id != CARD_PICK_ACTION]
    for action in others:  # the turn's other rows (going to Reveal)
        rows[_template(action)] = len(rows)
    older = _older(rows)
    teacher = OlderTeacher(older)
    view = _ENGINE.observe(state, player)
    answer = teacher.answer(state, player, view, legal)
    assert answer.source == NETWORK
    assert answer.probabilities.sum() == pytest.approx(1.0)
    assert np.isfinite(answer.value)
    # The softmax over the placements, summed onto each one's card pick.
    observation = np.asarray(encode_player_view(view), dtype=np.int32)
    wholes = (*executable_placements(state, player), *others)
    logits, _ = older.scores(observation, [rows[_template(w)] for w in wholes])
    weights = np.exp(logits - logits.max())
    weights /= weights.sum()
    expected = np.zeros(len(legal))
    for whole, weight in zip(wholes, weights, strict=True):
        if whole.action_id == CARD_PICK_ACTION or whole in others:
            expected[legal.index(whole)] += weight
            continue
        (pick,) = agent_card_pick_actions(player, (whole,))
        expected[legal.index(pick)] += weight
    assert answer.probabilities == pytest.approx(expected)


def test_a_decision_with_no_row_goes_to_the_heuristic() -> None:
    state, player = _first_turn()
    legal = _ENGINE.legal_actions(state, player)
    view = _ENGINE.observe(state, player)
    answer = OlderTeacher(_older({}), seed=5).answer(state, player, view, legal)
    assert answer.source == FALLBACK
    choice = HeuristicAgent(seed=5).choose_action_with_state(state, view, legal)
    assert answer.probabilities[legal.index(choice)] == 1.0
    assert np.isfinite(answer.value)


def test_the_greedy_seat_plays_its_best_placement_in_two_steps() -> None:
    state, player = _first_turn()
    rows = _placement_rows(state, player)
    agent = OlderNetworkAgent(_older(rows))
    view = _ENGINE.observe(state, player)
    legal = _ENGINE.legal_actions(state, player)
    pick = agent.choose_action_with_state(state, view, legal)
    observation = np.asarray(encode_player_view(view), dtype=np.int32)
    placements = executable_placements(state, player)
    logits, _ = agent.teacher.older.scores(
        observation, [rows[_template(p)] for p in placements]
    )
    best = placements[int(np.argmax(logits))]
    assert (pick,) == agent_card_pick_actions(player, (best,))
    picked = _ENGINE.apply(state, pick, legal_actions=legal).state
    space = agent.choose_action_with_state(
        picked, _ENGINE.observe(picked, player), _ENGINE.legal_actions(picked, player)
    )
    assert dict(space.arguments)["space_id"] == dict(best.arguments)["space_id"]


def test_a_file_keeps_its_own_rows_and_enters_as_an_older_seat(
    tmp_path: Path,
) -> None:
    codec = ActionCodec(_RULES)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    path = tmp_path / "net.pt"
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    older = load_older_network(path)
    assert len(older.rows) == codec.size
    assert torch.equal(older.weight, network.policy_head.weight.detach())
    assert is_agent_kind(f"older:{path}")
    assert isinstance(make_agent(f"older:{path}", 0), OlderNetworkAgent)


def test_an_older_shard_keeps_every_learner_decision_with_its_answer(
    tmp_path: Path,
) -> None:
    codec = ActionCodec(_RULES)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    path = tmp_path / "net.pt"
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    specs = (
        SelfPlaySpec(game_seed=11, lineup=(LEARNER, "heuristic") * 2),
        SelfPlaySpec(game_seed=12, lineup=(LEARNER,) * 4),
    )
    data = older_shard(
        None,
        path,
        _RULES,
        specs,
        first_game=40,
        workers=2,
        opponent="heuristic",
        seed=3,
        max_steps=120,
    )
    assert data.rows > 0
    assert set(np.unique(data.games).tolist()) == {40, 41}
    sums = np.add.reduceat(data.teacher.astype(np.float64), data.legal_offsets[:-1])
    assert sums == pytest.approx(np.ones(data.rows), abs=2e-3)
    index, valid, target = data.legal(np.arange(data.rows))
    played = (index == data.actions[:, None]) & valid
    assert played.any(axis=1).all()
    assert ((target * played).sum(axis=1) > 0).all()
    assert np.isfinite(data.values).all()
    assert (np.diff(data.games) >= 0).all()


def test_the_greedy_seat_does_not_repeat_a_choice_at_the_same_observation() -> None:
    """A Scouts bid set again and again looped a game to 30,000 actions."""

    state, player = _first_turn()
    rows = _placement_rows(state, player)
    agent = OlderNetworkAgent(_older(rows))
    view = _ENGINE.observe(state, player)
    legal = _ENGINE.legal_actions(state, player)
    agent.choose_action_with_state(state, view, legal)
    agent.choose_action_with_state(state, view, legal)
    # The guard is over whole actions (placements): the second pick is another
    # placement, though its first step, the card pick, may name the same card
    # (with codec v155's catalog this untrained network's two best placements
    # both play the Dagger).
    (taken,) = agent._taken.values()
    assert len(taken) == 2
