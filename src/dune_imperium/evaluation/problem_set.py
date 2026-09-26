"""Evaluation problem set: real positions where one family of answers is right.

A tactics suite for a policy (docs/player-tips-for-training.md section 3,
route 2; design note docs/evaluation/problem-set.md). Win rates need thousands
of games to resolve a few points; a fixed set of positions with a known right
answer is scored in minutes and has no game-outcome noise. It is an
evaluation, never a training target: a policy trained on these positions would
pass them without having learned anything.

Each ``Problem`` pairs a detector (is this decision an instance?) with a judge
(is this legal action a right answer?). Many decisions are effect-ordering
windows -- the seat may resolve another effect first and make the choice
later in the same turn -- so a problem may name its ``scored`` actions, the
ones that commit the answer; any other action only defers it (see
``answer``).

Positions are mined from seeded games of any registry agent and stored as the
game spec plus the index of every player choice up to the decision, so the
engine alone rebuilds them: chance outcomes follow from the seed and the order
of chance decisions. A fingerprint of the legal set, and the detector itself,
are re-checked on every restore; a position the engine no longer reaches is an
error that asks for the suite to be re-mined.

``confidence`` separates two kinds of problem. ``"clear"``: the right answer
follows from the rules (the summary cites them). ``"tip"``: the answer is
players' advice, with the cases where the advice provably fails excluded. A
policy that disagrees with a problem is a lead to investigate, not an
automatic error.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, replace
from functools import cache
from pathlib import Path
from typing import Any

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.adapters.observation_encoding import OBSERVATION_VERSION
from dune_imperium.agents import Agent, StateAgent
from dune_imperium.agents.registry import make_agent
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.contracts import (
    ContractConditionKind,
    contract_for_instance,
)
from dune_imperium.content.uprising.effect_dsl import (
    FlipFaceUpConflictCard,
    GainedSpiceThisTurn,
    IntrigueTiming,
)
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_interpreter import flippable_battle_card_ids
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.ornithopter import has_ornithopter_fleet
from dune_imperium.rules.planetologist import replaces_sandworms

SUITE_FORMAT = 1
DEFAULT_SUITE = Path(__file__).with_name("problem_sets") / "tips-v1.json"

# The three Intrigue cards whose Plot option is "1 spice" and whose Endgame
# option is "flip a face-up card with this battle icon: 1 Victory Point"
# (content/uprising/intrigue.py ``_spice_or_endgame_flip``).
_ICON_INTRIGUE = {
    "crysknife": BattleIcon.CRYSKNIFE,
    "desert_mouse": BattleIcon.DESERT_MOUSE,
    "ornithopter": BattleIcon.ORNITHOPTER,
}
# Secrets takes an Intrigue from each opponent holding 4 or more [Board Guide
# p. 2]; a seat at 4 may lose the card it holds for the Endgame.
_SECRETS_THRESHOLD = 4

Detector = Callable[[GameState, int, tuple[DomainAction, ...]], bool]
Judge = Callable[[GameState, int, DomainAction], bool]
Scored = Callable[[DomainAction], bool]


@dataclass(frozen=True, slots=True)
class Problem:
    problem_id: str
    source: str
    confidence: str
    summary: str
    detect: Detector
    right: Judge
    # The actions that commit the answer; None means every action does.
    scored: Scored | None = None


# --- shared helpers ----------------------------------------------------------


def _intrigue_play(action: DomainAction) -> tuple[str, int] | None:
    if action.action_id != "play_intrigue":
        return None
    arguments = dict(action.arguments)
    return str(arguments["card_id"]), int(arguments["option"])


def _icon_play(action: DomainAction, timing: IntrigueTiming) -> BattleIcon | None:
    """The battle icon of a battle-icon Intrigue played with ``timing``."""

    play = _intrigue_play(action)
    if play is None:
        return None
    card_id, option = play
    entry = intrigue_card_for_instance(card_id)
    icon = _ICON_INTRIGUE.get(entry.card.card_id)
    if icon is None or entry.options[option].timing is not timing:
        return None
    return icon


def _held_icon_cards(state: GameState, seat: int, icon: BattleIcon) -> int:
    return sum(
        1
        for card_id in state.players[seat].intrigue_cards
        if _ICON_INTRIGUE.get(intrigue_card_for_instance(card_id).card.card_id) is icon
    )


def _flips_face_up_conflicts(card_id: str) -> bool:
    """Whether an Intrigue can flip face-up Conflict cards whatever their icon.

    Grasp Arrakis (Bloodlines) competes with the battle-icon cards for the
    same face-up cards.
    """

    entry = intrigue_card_for_instance(card_id)
    return any(
        isinstance(cost, FlipFaceUpConflictCard)
        for option in entry.options
        for section in option.sections
        for cost in section.costs
    )


def _face_up_icons(state: GameState, seat: int) -> list[BattleIcon]:
    """Battle icons of the seat's face-up won Conflicts and Objectives."""

    player = state.players[seat]
    face_down = set(player.face_down_battle_card_ids)
    icons: list[BattleIcon | None] = [
        CONFLICTS_BY_ID[card_id].battle_icon
        for card_id in player.won_conflict_ids
        if card_id not in face_down
    ]
    icons += [
        OBJECTIVES_BY_ID[card_id].battle_icon
        for card_id in player.objective_ids
        if card_id not in face_down
    ]
    return [icon for icon in icons if icon is not None]


@cache
def _legal_engine() -> UprisingRulesEngine:
    # legal_actions reads only the state; the Leader roster matters at reset.
    return UprisingRulesEngine()


def _spice_opens_actions(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> bool:
    """Whether one more spice changes what the seat may do right now."""

    player = state.players[seat]
    richer = replace(
        player, resources=replace(player.resources, spice=player.resources.spice + 1)
    )
    players = tuple(richer if p.player_id == seat else p for p in state.players)
    bumped = replace(state, players=players)
    return set(_legal_engine().legal_actions(bumped, seat)) != set(legal)


def _spice_this_turn_matters(state: GameState, seat: int) -> bool:
    """Whether spice gained this turn can pay off for the seat this turn.

    The Plot's spice counts toward every "gained spice this turn" test
    (``rules.agent_effects.spice_gained_this_turn``): Agent boxes such as
    Guild Impersonator, Fremen War Name and Sandwalk (their effect names end
    in ``spice_this_turn``), a Harvest-spice Contract while the Agent turn
    resolves, Steersman Y'rkoon's Hungry for Spice, and Intrigue lines with
    ``GainedSpiceThisTurn``.
    """

    player = state.players[seat]
    for card_id in (*player.hand, *player.in_play):
        effect = personal_card_for_instance(card_id).agent_effect
        if effect is not None and "spice_this_turn" in effect.value:
            return True
    # A Harvest-spice Contract counts the spice gained after the Agent was
    # placed (rules/effects.py, ``spice_at_placement``), so it is at risk only
    # while that Agent turn's effects are resolving.
    placing = any(
        frame.kind == FrameKind.AGENT_EFFECTS
        and dict(frame.context).get("turn_owner") == seat
        for frame in state.decision_stack
    )
    if placing and any(
        contract_for_instance(c).condition.kind is ContractConditionKind.HARVEST_SPICE
        for c in player.active_contract_ids
    ):
        return True
    if player.leader_id == "steersman_y_rkoon" and not (
        player.hungry_for_spice_granted_turn
    ):
        return True
    return any(
        isinstance(section.condition, GainedSpiceThisTurn)
        for card_id in player.intrigue_cards
        for option in intrigue_card_for_instance(card_id).options
        for section in option.sections
    )


# --- endgame_battle_icon_vp ---------------------------------------------------


def _detect_endgame_icon_vp(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> bool:
    ids = {action.action_id for action in legal}
    if "pass_endgame_intrigue" not in ids or "match_endgame_wild_icon" in ids:
        return False
    if any(_flips_face_up_conflicts(c) for c in state.players[seat].intrigue_cards):
        return False
    return any(
        _icon_play(action, IntrigueTiming.ENDGAME) is not None for action in legal
    )


def _right_endgame_icon_vp(state: GameState, seat: int, action: DomainAction) -> bool:
    return action.action_id != "pass_endgame_intrigue"


# --- last_round_hold_battle_icon ---------------------------------------------


def _hold_icons(state: GameState, seat: int) -> set[BattleIcon]:
    """Icons whose Intrigue card is worth an Endgame VP if held this round.

    The round is certainly the last: the Conflict deck is empty, and the
    Endgame starts when a round ends with it empty [Main p. 15]. The seat
    holds exactly one Intrigue card of the icon and a face-up card its
    Endgame option can flip. Excluded, because there holding can be worth
    nothing (all found in mined positions, docs/evaluation/problem-set.md):
    any face-up wild card -- an Endgame wild match can score the same card
    anyway [Main p. 20]; a wild or same-icon current Conflict, whose win can
    match the card first [Main p. 14]; Ornithopter Fleet, under which every
    icon is an Ornithopter [Bloodlines p. 12]; a held Grasp Arrakis, which
    flips the same cards; and four or more Intrigue cards, which Secrets can
    steal from [Board Guide p. 2].
    """

    if state.conflict_deck or not state.current_conflict_ids:
        return set()
    player = state.players[seat]
    current = CONFLICTS_BY_ID[state.current_conflict_ids[-1]].battle_icon
    if (
        current is BattleIcon.WILD
        or has_ornithopter_fleet(player)
        or BattleIcon.WILD in _face_up_icons(state, seat)
        or len(player.intrigue_cards) >= _SECRETS_THRESHOLD
        or any(_flips_face_up_conflicts(c) for c in player.intrigue_cards)
    ):
        return set()
    return {
        icon
        for icon in _ICON_INTRIGUE.values()
        if icon is not current
        and _held_icon_cards(state, seat, icon) == 1
        and flippable_battle_card_ids(player, icon)
    }


def _detect_hold_icon(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> bool:
    if state.phase is not GamePhase.PLAYER_TURNS:
        return False
    icons = _hold_icons(state, seat)
    if not any(_icon_play(action, IntrigueTiming.PLOT) in icons for action in legal):
        return False
    # The Plot's spice must buy nothing now: no action it would open, and no
    # "gained spice this turn" test it could meet (Guild Impersonator made
    # the Plot worth a VP in a mined position).
    return not _spice_this_turn_matters(state, seat) and not _spice_opens_actions(
        state, seat, legal
    )


def _right_hold_icon(state: GameState, seat: int, action: DomainAction) -> bool:
    return _icon_play(action, IntrigueTiming.PLOT) not in _hold_icons(state, seat)


# --- deep_desert_summon_into_contest -----------------------------------------


def _placement(strength: int, others: Sequence[int]) -> int:
    """Provisional Conflict placement: 0 without strength, else 1 + stronger."""

    return 0 if strength == 0 else 1 + sum(other > strength for other in others)


def _is_deep_desert_choice(action: DomainAction) -> bool:
    return (
        action.action_id in ("summon_maker_sandworms", "harvest_maker_spice")
        and dict(action.arguments).get("space_id") == "deep_desert"
    )


def _detect_summon(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> bool:
    choice = {action.action_id for action in legal if _is_deep_desert_choice(action)}
    if choice != {"summon_maker_sandworms", "harvest_maker_spice"}:
        return False
    if not state.current_conflict_ids:
        return False
    player = state.players[seat]
    # Arrakis Planetologist's summon puts no sandworm in the Conflict.
    if replaces_sandworms(player) or player.sandworms_conflict:
        return False
    if CONFLICTS_BY_ID[state.current_conflict_ids[-1]].tier is ConflictTier.ONE:
        return False
    own = player.combat_strength
    others = [p.combat_strength for p in state.players if p.player_id != seat]
    before = _placement(own, others)
    after = _placement(own + 6, others)  # two sandworms, 3 each [Main p. 12]
    return after == 1 or (after <= 3 and (before == 0 or after < before))


def _right_summon(state: GameState, seat: int, action: DomainAction) -> bool:
    return action.action_id == "summon_maker_sandworms"


PROBLEMS: dict[str, Problem] = {
    problem.problem_id: problem
    for problem in (
        Problem(
            "endgame_battle_icon_vp",
            "C8.3 (docs/evaluation/community-tips-2026-09-22.md)",
            "clear",
            "Endgame window with a Crysknife/Desert Mouse/Ornithopter Endgame "
            "play legal: it flips a face-up Conflict card of its icon for 1 VP "
            "[card faces]; Endgame Intrigue resolves before scores are compared "
            "[Main p. 15] and VP ranks first; passing closes the seat's window "
            "for good (OQ-001, project convention). Excluded: a legal wild match "
            "or a held Grasp Arrakis, which can take the same cards. Right: "
            "anything but pass.",
            _detect_endgame_icon_vp,
            _right_endgame_icon_vp,
        ),
        Problem(
            "last_round_hold_battle_icon",
            "C8.3; player-tips 7.7 (5081 spends a third of these Plots here)",
            "tip",
            "Certain last round (empty Conflict deck [Main p. 15]), the only "
            "copy of a battle-icon Intrigue in hand and a "
            "face-up non-wild card it could flip at Endgame: the Endgame option "
            "is 1 VP, the Plot 1 spice. Advice: hold it. Cases where holding "
            "can be worth nothing are excluded (see _hold_icons), and so are "
            "decisions where one more spice opens an action or can meet a "
            "'gained spice this turn' test; spice can still matter later in "
            "the round, so this stays a tip.",
            _detect_hold_icon,
            _right_hold_icon,
        ),
        Problem(
            "deep_desert_summon_into_contest",
            "owner's tip 1 (player-tips 6.3), C2.3",
            "tip",
            "Deep Desert with Maker Hooks on a tier II/III Conflict, no own "
            "sandworm there yet, and two sandworms (strength 3 each [Main p. "
            "12]) would take the seat to 1st or to a better rewarded place: "
            "summon rather than take spice 4 [Board Guide p. 1]; the seat's "
            "rewards double except control and battle icons [Main p. 14]. "
            "Arrakis Planetologist is excluded. Only the summon/spice choice is "
            "scored; resolving another effect first defers it.",
            _detect_summon,
            _right_summon,
            _is_deep_desert_choice,
        ),
    )
}


# --- positions ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Position:
    position_id: str
    problem_id: str
    spec: dict[str, Any]
    choices: tuple[int, ...]
    owner: int
    fingerprint: str


def _spec_to_json(spec: MatchSpec) -> dict[str, Any]:
    data = asdict(spec)
    data["seat_agents"] = list(spec.seat_agents)
    data["leader_ids"] = None if spec.leader_ids is None else list(spec.leader_ids)
    return data


def _spec_from_json(data: dict[str, Any]) -> MatchSpec:
    fields = dict(data)
    fields["seat_agents"] = tuple(fields["seat_agents"])
    if fields.get("leader_ids") is not None:
        fields["leader_ids"] = tuple(fields["leader_ids"])
    return MatchSpec(**fields)


def _seating(spec: MatchSpec) -> str:
    """The table in seat order (``checkpoint:<path>`` -> the file's stem)."""

    names = [
        Path(kind.partition(":")[2]).stem if ":" in kind else kind
        for kind in spec.seat_agents
    ]
    return names[0] if len(set(names)) == 1 else ".".join(names)


def _engine(spec: MatchSpec) -> UprisingRulesEngine:
    return (
        UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else UprisingRulesEngine()
    )


def fingerprint(state: GameState, owner: int, legal: Sequence[DomainAction]) -> str:
    text = repr((state.round_number, owner, tuple(legal)))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _require_unique(positions: Sequence[Position]) -> None:
    seen: set[str] = set()
    for position in positions:
        if position.position_id in seen:
            raise ValueError(f"duplicate position id {position.position_id}")
        seen.add(position.position_id)


def mine(
    specs: Iterable[MatchSpec],
    problem_ids: Sequence[str] | None = None,
    *,
    workers: int = 1,
    max_per_problem: int | None = None,
) -> list[Position]:
    """Play each spec with its registry agents and keep every first instance.

    At most one position per problem and seat in a game: later instances of
    the same seat are nearly the same position. ``max_per_problem`` keeps the
    first positions in spec order, so a cap is deterministic.
    """

    ids = tuple(problem_ids or PROBLEMS)
    specs = tuple(specs)
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor

        from dune_imperium.evaluation.tournament import _single_threaded_worker

        with ProcessPoolExecutor(
            max_workers=workers, initializer=_single_threaded_worker
        ) as pool:
            per_spec = list(pool.map(_mine_spec, specs, [ids] * len(specs)))
    else:
        per_spec = [_mine_spec(spec, ids) for spec in specs]
    positions: list[Position] = []
    counts: dict[str, int] = {}
    for found in per_spec:
        for position in found:
            count = counts.get(position.problem_id, 0)
            if max_per_problem is not None and count >= max_per_problem:
                continue
            counts[position.problem_id] = count + 1
            positions.append(position)
    _require_unique(positions)
    return positions


def _mine_spec(spec: MatchSpec, problem_ids: Sequence[str]) -> list[Position]:
    """One game's positions (module-level so a worker process can run it)."""

    problems = [PROBLEMS[p] for p in problem_ids]
    positions: list[Position] = []
    engine = _engine(spec)
    agents = tuple(
        make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    state = engine.reset(spec.config, spec.game_seed)
    chance = ChanceResolver(seed=spec.game_seed)
    choices: list[int] = []
    seen: set[tuple[str, int]] = set()
    for _ in range(spec.max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        if decision is None:
            raise RuntimeError(f"no decision before FINISHED, seed {spec.game_seed}")
        owner = decision.owner
        legal = engine.legal_actions(state, owner)
        for problem in problems:
            key = (problem.problem_id, owner)
            if key in seen or not problem.detect(state, owner, legal):
                continue
            seen.add(key)
            positions.append(
                Position(
                    position_id=(
                        f"{problem.problem_id}/{_seating(spec)}"
                        f"/{spec.config.identifier}/s{spec.game_seed}/p{owner}"
                    ),
                    problem_id=problem.problem_id,
                    spec=_spec_to_json(spec),
                    choices=tuple(choices),
                    owner=owner,
                    fingerprint=fingerprint(state, owner, legal),
                )
            )
        agent = agents[owner]
        view = engine.observe(state, owner)
        action = (
            agent.choose_action_with_state(state, view, legal)
            if isinstance(agent, StateAgent)
            else agent.choose_action(view, legal)
        )
        choices.append(legal.index(action))
        state = engine.apply(state, action, legal_actions=legal).state
    else:
        raise RuntimeError(f"step limit reached for seed {spec.game_seed}")
    return positions


@dataclass(slots=True)
class _Replay:
    engine: UprisingRulesEngine
    state: GameState
    legal: tuple[DomainAction, ...]
    chance: ChanceResolver


def _replay(position: Position) -> _Replay:
    moved = ValueError(
        f"{position.position_id}: the engine no longer reaches this position; "
        "re-mine the suite"
    )
    spec = _spec_from_json(position.spec)
    engine = _engine(spec)
    state = engine.reset(spec.config, spec.game_seed)
    chance = ChanceResolver(seed=spec.game_seed)
    remaining = list(position.choices)
    while True:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        if decision is None:
            raise moved
        owner = decision.owner
        legal = engine.legal_actions(state, owner)
        if not remaining:
            break
        index = remaining.pop(0)
        if index >= len(legal):
            raise moved
        state = engine.apply(state, legal[index], legal_actions=legal).state
    if owner != position.owner or fingerprint(state, owner, legal) != (
        position.fingerprint
    ):
        raise moved
    if not PROBLEMS[position.problem_id].detect(state, owner, legal):
        raise ValueError(
            f"{position.position_id}: no longer an instance of "
            f"{position.problem_id}; re-mine the suite"
        )
    return _Replay(engine, state, legal, chance)


def restore(
    position: Position,
) -> tuple[UprisingRulesEngine, GameState, tuple[DomainAction, ...]]:
    """Rebuild a position; raises ValueError if the engine no longer reaches it."""

    replay = _replay(position)
    return replay.engine, replay.state, replay.legal


def unrestorable(positions: Sequence[Position]) -> list[str]:
    """Restore every position; return why each one that no longer restores fails.

    The ``check`` command and the test suite's guard over the committed suite
    both use this, so an engine change that moves a stored position is caught
    the same way in both places.
    """

    failures = []
    for position in positions:
        try:
            restore(position)
        except ValueError as error:
            failures.append(str(error))
    return failures


# --- suites ------------------------------------------------------------------


def save_suite(path: Path, positions: Sequence[Position], note: str) -> None:
    _require_unique(positions)
    data = {
        "format": SUITE_FORMAT,
        "action_codec_version": ACTION_CODEC_VERSION,
        "observation_version": OBSERVATION_VERSION,
        "note": note,
        "positions": [
            {**asdict(position), "choices": list(position.choices)}
            for position in positions
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n")


def load_suite(path: Path = DEFAULT_SUITE) -> list[Position]:
    data = json.loads(path.read_text())
    if data["format"] != SUITE_FORMAT:
        raise ValueError(f"unsupported suite format {data['format']}")
    return [
        Position(**{**entry, "choices": tuple(entry["choices"])})
        for entry in data["positions"]
    ]


def suite_note(path: Path = DEFAULT_SUITE) -> str:
    return str(json.loads(path.read_text()).get("note", ""))


# --- scoring -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Answer:
    position_id: str
    problem_id: str
    right: bool
    # The network's probability on the right answers among the scored ones.
    p_right: float | None
    chosen: str
    legal: int
    right_actions: int
    # Reorder-only choices the agent made before committing (0 if none).
    deferred: int
    # False if the agent never reached a scored action (counted as wrong).
    resolved: bool


def policy_probabilities(
    agent: Agent, view: Any, legal: tuple[DomainAction, ...]
) -> dict[DomainAction, float] | None:
    """A network agent's softmax over the legal actions it may choose.

    ``None`` for agents without a network (heuristic, random, search): they
    are scored on their chosen action only. The logits are the ones greedy
    play takes its argmax over (``training.torch_policy.NetworkAgent``):
    undo actions get no mass, as there.
    """

    network = getattr(agent, "network", None)
    codec = getattr(agent, "codec", None)
    if network is None or codec is None:
        return None
    import numpy as np
    import torch

    from dune_imperium.adapters.observation_encoding import encode_player_view
    from dune_imperium.training.policy import without_undo_actions

    offered = without_undo_actions(legal)
    index = [codec.encode(action) for action in offered]
    mask = np.zeros(codec.size, dtype=np.int8)
    mask[index] = 1
    observation = np.asarray(encode_player_view(view), dtype=np.int32)
    with torch.no_grad():
        logits, _ = network(
            torch.from_numpy(observation).unsqueeze(0),
            torch.from_numpy(mask).unsqueeze(0),
        )
    scores = [float(value) for value in logits[0, index]]
    top = max(scores)
    weights = [math.exp(score - top) for score in scores]
    total = sum(weights)
    return {
        action: weight / total for action, weight in zip(offered, weights, strict=True)
    }


def agent_seed(position: Position, seed: int) -> int:
    """A per-position agent seed: one shared seed would give a seeded agent
    (random, the heuristic's tie-breaks) the same first draw everywhere."""

    digest = hashlib.sha256(position.position_id.encode()).hexdigest()
    return seed + int(digest[:8], 16) % 1_000_000


def _choose(
    agent: Agent,
    engine: UprisingRulesEngine,
    state: GameState,
    owner: int,
    legal: tuple[DomainAction, ...],
) -> DomainAction:
    view = engine.observe(state, owner)
    if isinstance(agent, StateAgent):
        return agent.choose_action_with_state(state, view, legal)
    return agent.choose_action(view, legal)


def answer(
    position: Position, kind: str, seed: int = 0, max_deferrals: int = 40
) -> Answer:
    """Ask a fresh ``kind`` agent for the position's decision.

    When the problem names its scored actions and the agent picks another
    one (it resolves some other effect first), the same agent plays on from
    there until it commits, for as long as the decisions stay the seat's.
    ``p_right`` is taken at the position itself, renormalized over the
    scored actions.
    """

    problem = PROBLEMS[position.problem_id]
    replay = _replay(position)
    engine, state, legal, chance = (
        replay.engine,
        replay.state,
        replay.legal,
        replay.chance,
    )
    owner = position.owner
    right_actions = sum(problem.right(state, owner, action) for action in legal)
    agent = make_agent(kind, agent_seed(position, seed))
    probabilities = policy_probabilities(agent, engine.observe(state, owner), legal)
    p_right = None
    if probabilities is not None:
        scored = [
            action
            for action in probabilities
            if problem.scored is None or problem.scored(action)
        ]
        mass = sum(probabilities[action] for action in scored)
        if mass > 0:
            p_right = (
                sum(
                    probabilities[action]
                    for action in scored
                    if problem.right(state, owner, action)
                )
                / mass
            )
    deferred = 0
    chosen: DomainAction | None = None
    while True:
        action = _choose(agent, engine, state, owner, legal)
        if problem.scored is None or problem.scored(action):
            chosen = action
            break
        deferred += 1
        if deferred > max_deferrals:
            break
        state = engine.apply(state, action, legal_actions=legal).state
        decision = engine.current_decision(state)
        while isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            decision = engine.current_decision(state)
        if decision is None or decision.owner != owner:
            break
        legal = engine.legal_actions(state, owner)
    return Answer(
        position_id=position.position_id,
        problem_id=position.problem_id,
        right=chosen is not None and problem.right(state, owner, chosen),
        p_right=p_right,
        chosen=(
            "unresolved"
            if chosen is None
            else f"{chosen.action_id}{dict(chosen.arguments)}"
        ),
        legal=len(replay.legal),
        right_actions=right_actions,
        deferred=deferred,
        resolved=chosen is not None,
    )


def summarize_answers(answers: Sequence[Answer]) -> dict[str, dict[str, Any]]:
    """Per problem: positions, share answered right, mean P(right)."""

    out: dict[str, dict[str, Any]] = {}
    for problem_id in sorted({a.problem_id for a in answers}):
        group = [a for a in answers if a.problem_id == problem_id]
        probabilities = [a.p_right for a in group if a.p_right is not None]
        out[problem_id] = {
            "confidence": PROBLEMS[problem_id].confidence,
            "positions": len(group),
            "right": sum(a.right for a in group) / len(group),
            "mean_p_right": (
                sum(probabilities) / len(probabilities) if probabilities else None
            ),
            "unresolved": sum(not a.resolved for a in group),
            "wrong": [a.position_id for a in group if not a.right],
        }
    return out
