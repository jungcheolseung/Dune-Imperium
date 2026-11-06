"""A reopened Agent turn through the play server's undo, saves and replay.

OQ-095 (docs/rules/open-questions.md) (4): the turn-end press trashes the
card Usurp borrowed ("trash that card at the end of your turn" [Usurp
card], OQ-054); (5), user ruling 2026-10-01: "Usurp trash의 결과는 이 turn의
것이다 ... 그 결과로 조건을 만족한 Contract가 생기거나 ... Combat 배치가 가능한
turn에 새로 recruit한 유닛이 생기면 turn은 다시 열리고, 소유자가 그것을 처리한
뒤 \"턴 종료\"를 다시 누른다". An owed Unload acquisition reopens it too
(``combat_deployment.settle_finishing_agent_turn``; "Trashing a card with
Usurp does trigger effects like Replacement Eyes and cards with Unload"
[Immortality p. 14]).

The engine tests build both positions by editing a state
(tests/unit/rules/test_immortality_tleilaxu_cards.py::
test_usurped_eliminate_allies_troops_reopen_a_combat_turn and
tests/unit/rules/test_imperium_immortality.py::
test_a_usurped_boundless_ambition_acquires_after_the_row_refills), and
tests/server/test_turn_end.py hands the server such a state. The server's
undo, its saves and the records' replay rebuild every state from the seed's
setup and the recorded steps (``sessions._state_after``, ``restore_game``,
``core.replay.replay_game``), so an edited state never reaches them. Here
real games reach both positions: four human seats take a heuristic
self-play game's steps through ``apply_action`` (and ``confirm_turn`` where
a unit end waits for its press), as the page would.

* ``eliminate_allies``: Uprising with Bloodlines and Immortality, seed 187
  (Eliminate Allies is a Bloodlines card, so a real game needs Bloodlines).
  At the first turn start where seat 1 holds Usurp with Eliminate Allies in
  the Imperium Row, it grafts Usurp to that card at the Spice Refinery, a
  Combat space; the press trashes the card, its two troops are this turn's
  recruits, and the turn reopens for their deployment.
* ``boundless_ambition``: the original game with Rise of Ix, Immortality
  and the promos, seed 243. The self-play itself has seat 2 Usurp Boundless
  Ambition in round 5; the press trashes it, its Unload acquisition is owed
  inside the turn, and the turn reopens; the owner takes the acquisition in
  its window and presses again.
* ``freighter_fleet``: the original game with Rise of Ix, Immortality and
  the promos, seed 102. At the first turn start where seat 2 holds Usurp
  with Freighter Fleet in the Row (round 5), it grafts Usurp to that card at
  Smuggling; the press trashes it, and its Unload's "may" Freighter reopens
  the turn (OQ-160, user ruling 2026-10-31: "다시 열어 제시"). The Freighter
  is at the top, so the owner recalls it, takes the rewards and presses
  again.

Each case is checked at two boundaries -- ``reopened``, right after the
first press, and, for Boundless Ambition, ``acquisition_window`` -- for
undo, save/load and replay. The seeds come from searching heuristic
self-play games (policy seed 1000 + game seed + seat): one Ix game in 300
reopened a turn by itself (seed 243); no Uprising game with Bloodlines and
Immortality did in 300, and seed 187 is one of three in 400 where a seat
holding Usurp at a turn start could graft it to Eliminate Allies on a Combat
space and so reopen the turn; seed 102 is the shortest of four in 300 Ix
games (82, 100, 102, 106, on the engine of OQ-160) where a seat holding Usurp
at a turn start could graft it to Freighter Fleet. A change to the engine or
the heuristic seat
that moves these games fails the reach assertions below; search again by
the same criteria then. The seats play the heuristic the seeds were found
with, ``heuristic_before_original_twins`` (the original game's twin spaces
still priced 0; master's ``heuristic`` prices them since 2026-10-30, which
moved the two Ix games); at Uprising tables it plays as ``heuristic``.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Final

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.agents.base import StateAgent
from dune_imperium.agents.registry import make_agent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.replay import ReplayStep, replay_game
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.records.convert import verify_converted_save
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.persistence import parse_save_document
from dune_imperium.server.session_log import live_steps
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SessionError,
)

HUMANS: Final = ("human",) * 4
# The heuristic self-play seats: seat ``s`` of game ``g`` plays with policy
# seed 1000 + g + s.
POLICY_OFFSET: Final = 1000
MAX_SELF_PLAY_STEPS: Final = 3000
USURP: Final = "tleilaxu:usurp:0"
ELIMINATE_ALLIES: Final = "imperium:eliminate_allies:0"
BOUNDLESS_AMBITION: Final = "imperium:boundless_ambition:0"
FREIGHTER_FLEET: Final = "imperium:freighter_fleet:0"

REOPENED: Final = "reopened"
ACQUISITION_WINDOW: Final = "acquisition_window"

# A row to take: its action id and the arguments it must carry.
type Row = tuple[str, dict[str, object]]


def _int(value: object) -> int:
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _reload(document: JsonObject) -> JsonObject:
    """The document as a save file holds it."""

    loaded = json.loads(json.dumps(document))
    assert isinstance(loaded, dict)
    return loaded


# ------------------------------------------------------------- the two games

type Stop = Callable[[GameState, int, tuple[GameEvent, ...]], bool]


def _holds_usurp_beside_eliminate_allies(
    state: GameState, owner: int, events: tuple[GameEvent, ...]
) -> bool:
    """A turn start of a seat holding Usurp, Eliminate Allies in the Row."""

    del events
    return (
        state.decision_stack[-1].kind == FrameKind.TURN
        and USURP in state.players[owner].hand
        and ELIMINATE_ALLIES in state.imperium_row
    )


def _holds_usurp_beside_freighter_fleet(
    state: GameState, owner: int, events: tuple[GameEvent, ...]
) -> bool:
    """A turn start of a seat holding Usurp, Freighter Fleet in the Row."""

    del events
    return (
        state.decision_stack[-1].kind == FrameKind.TURN
        and USURP in state.players[owner].hand
        and FREIGHTER_FLEET in state.imperium_row
    )


def _reopens(state: GameState, owner: int, events: tuple[GameEvent, ...]) -> bool:
    """The step about to be taken is a press that reopens the turn."""

    del state, owner
    return any(event.kind == "agent_turn_reopened" for event in events)


@dataclass(frozen=True, slots=True)
class Case:
    """One real game that reaches a reopened turn."""

    name: str
    seed: int
    base_game: BaseGame
    bloodlines: bool
    rise_of_ix: bool
    # Every case plays with Immortality and the promos (Usurp, Boundless
    # Ambition). The self-play stops before the step at which this holds.
    stop: Stop
    # What the owner takes after the self-play and before the press: its
    # Usurp placement where the self-play did not make one. The first row
    # that is neither a deployment nor the end then resolves each effect
    # left until the end is offered.
    before_press: tuple[Row, ...]
    # The rest of the turn after the press, ending in the second press.
    rest: tuple[Row, ...]
    # Each boundary: how many rows of ``rest`` lead to it from the press,
    # and the undoable rows taken there and taken back.
    boundaries: dict[str, tuple[int, tuple[Row, ...]]]

    @property
    def config(self) -> RulesetConfig:
        return RulesetConfig(
            base_game=self.base_game,
            bloodlines=self.bloodlines,
            immortality=True,
            promo_cards=True,
            rise_of_ix=self.rise_of_ix,
        )


CASES: Final = {
    "eliminate_allies": Case(
        name="eliminate_allies",
        seed=187,
        base_game=BaseGame.UPRISING,
        bloodlines=True,
        rise_of_ix=False,
        stop=_holds_usurp_beside_eliminate_allies,
        before_press=(
            ("choose_agent_card", {"card_id": USURP, "graft": True}),
            ("place_agent", {"space_id": "spice_refinery", "cost_option": 0}),
            ("choose_graft_partner", {"card_id": ELIMINATE_ALLIES}),
        ),
        rest=(("deploy_troops", {"count": 2}), ("finish_agent_turn", {})),
        boundaries={REOPENED: (0, (("deploy_troops", {"count": 2}),))},
    ),
    "boundless_ambition": Case(
        name="boundless_ambition",
        seed=243,
        base_game=BaseGame.IMPERIUM,
        bloodlines=False,
        rise_of_ix=True,
        stop=_reopens,
        before_press=(),
        rest=(
            ("resolve_unload_icon", {"card_id": BOUNDLESS_AMBITION}),
            # The first Imperium Row card offered, as the self-play took:
            # the Row's refill shows the deck's top card, so it is never
            # undoable.
            ("acquire_unload_imperium_card", {}),
            ("finish_agent_turn", {}),
        ),
        boundaries={
            REOPENED: (
                0,
                (
                    ("resolve_unload_icon", {"card_id": BOUNDLESS_AMBITION}),
                    ("acquire_unload_reserve_card", {}),
                ),
            ),
            ACQUISITION_WINDOW: (1, (("acquire_unload_reserve_card", {}),)),
        },
    ),
    "freighter_fleet": Case(
        name="freighter_fleet",
        seed=102,
        base_game=BaseGame.IMPERIUM,
        bloodlines=False,
        rise_of_ix=True,
        stop=_holds_usurp_beside_freighter_fleet,
        before_press=(
            ("choose_agent_card", {"card_id": USURP, "graft": True}),
            ("place_agent", {"space_id": "smuggling"}),
            ("choose_graft_partner", {"card_id": FREIGHTER_FLEET}),
        ),
        # The Freighter is at the top, so it recalls (Shipping track spaces
        # 1-3's rewards, the optional Acquire Tech left to lapse).
        rest=(
            ("resolve_unload_icon", {"card_id": FREIGHTER_FLEET}),
            ("recall_freighter", {}),
            # Space 1's dividends and spice are one reward.
            ("resolve_shipping_reward", {"effect": "dividends"}),
            ("resolve_shipping_reward", {"effect": "recruit"}),
            ("resolve_shipping_reward", {"effect": "influence", "faction": "emperor"}),
            ("finish_agent_turn", {}),
        ),
        boundaries={
            REOPENED: (
                0,
                (
                    ("resolve_unload_icon", {"card_id": FREIGHTER_FLEET}),
                    ("recall_freighter", {}),
                ),
            ),
        },
    ),
}
BOUNDARY_CASES: Final = [
    pytest.param(name, boundary, id=f"{name}-{boundary}")
    for name, case in CASES.items()
    for boundary in case.boundaries
]


def _self_play(case: Case) -> tuple[tuple[ReplayStep, ...], int]:
    """The heuristic self-play's steps up to ``case.stop``, and its seat."""

    config = case.config
    engine = UprisingRulesEngine()
    agents = [
        make_agent(
            "heuristic_before_original_twins", POLICY_OFFSET + case.seed + seat, config
        )
        for seat in range(config.players)
    ]
    state = engine.reset(config, case.seed)
    chance = ChanceResolver(seed=case.seed)
    steps: list[ReplayStep] = []
    for _ in range(MAX_SELF_PLAY_STEPS):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            step: ReplayStep = chance.resolve(decision)
        else:
            assert isinstance(decision, PlayerDecision)
            owner = decision.owner
            legal = engine.legal_actions(state, owner)
            observation = engine.observe(state, owner)
            agent = agents[owner]
            step = (
                agent.choose_action_with_state(state, observation, legal)
                if isinstance(agent, StateAgent)
                else agent.choose_action(observation, legal)
            )
        result = engine.apply(state, step)
        if isinstance(decision, PlayerDecision) and case.stop(
            state, decision.owner, result.events
        ):
            return tuple(steps), decision.owner
        steps.append(step)
        state = result.state
    raise AssertionError(
        f"seed {case.seed} no longer reaches the {case.name} position; "
        "search the seed again"
    )


def _expansion(
    engine: UprisingRulesEngine, state: GameState, whole: DomainAction
) -> list[ReplayStep]:
    """The steps ``apply_action`` takes for ``whole``."""

    taken: list[ReplayStep] = []
    for _ in range(steps_after(state, whole)):
        step = first_step(state, whole)
        taken.append(step)
        state = engine.apply(state, step).state
    taken.append(first_step(state, whole))
    return taken


class Table:
    """One server game of four human seats."""

    def __init__(self, manager: GameSessionManager, game_id: str) -> None:
        self.manager = manager
        self.game_id = game_id

    @property
    def session_state(self) -> GameState:
        return self.manager._get(self.game_id).state

    def summary(self) -> JsonObject:
        return self.manager.summary(self.game_id)

    def state_hash(self) -> str:
        return canonical_state_hash(self.session_state)

    def rows(self, seat: int) -> list[dict[str, object]]:
        return _rows(self.manager.legal_actions(self.game_id, seat)["actions"])

    def take_index(self, seat: int, index: int) -> JsonObject:
        summary = self.summary()
        return self.manager.apply_action(
            self.game_id,
            seat,
            _int(summary["revision"]),
            index,
            undo_count=_int(summary["undo_count"]),
        )

    def take(self, seat: int, row: Row) -> JsonObject:
        """Take the first legal row with ``row``'s id and arguments."""

        action_id, arguments = row
        for offered in self.rows(seat):
            given = _obj(offered["arguments"])
            if offered["action_id"] == action_id and all(
                given.get(key) == value for key, value in arguments.items()
            ):
                return self.take_index(seat, _int(offered["index"]))
        raise AssertionError(f"seat {seat} is not offered {row}")

    def take_all(self, seat: int, rows: Sequence[Row]) -> JsonObject:
        summary = self.summary()
        for row in rows:
            summary = self.take(seat, row)
        return summary

    def resolve_to_the_end(self, seat: int) -> None:
        """Take the first row that is neither a deployment nor the end
        until the seat is offered its turn end."""

        for _ in range(20):
            rows = self.rows(seat)
            if any(row["action_id"] == "finish_agent_turn" for row in rows):
                return
            row = next(
                row for row in rows if not str(row["action_id"]).startswith("deploy")
            )
            self.take_index(seat, _int(row["index"]))
        raise AssertionError(f"seat {seat} was never offered its turn end")

    def undo(self, seat: int, steps: int) -> JsonObject:
        summary = self.summary()
        return self.manager.undo(
            self.game_id,
            seat,
            _int(summary["revision"]),
            steps,
            undo_count=_int(summary["undo_count"]),
        )

    def undo_window(self, seat: int) -> int:
        return sum(
            _int(row["steps"])
            for row in _rows(self.summary()["undo"])
            if row["seat"] == seat
        )

    def save(self) -> JsonObject:
        return self.manager.save_document(self.game_id)

    def play_recorded(self, steps: Sequence[ReplayStep]) -> None:
        """Take ``steps`` as the seats would: every player step through the
        whole action whose steps they are, every unit end it holds pressed.
        The chance steps are the server's own and must match the record."""

        session = self.manager._get(self.game_id)
        engine = session.engine
        while len(session.steps) < len(steps):
            assert session.steps == list(steps[: len(session.steps)])
            summary = self.summary()
            held = summary["confirmation"]
            if held is not None:
                self.manager.confirm_turn(
                    self.game_id,
                    _int(held),
                    _int(summary["revision"]),
                    undo_count=_int(summary["undo_count"]),
                )
                continue
            at = len(session.steps)
            step = steps[at]
            assert isinstance(step, DomainAction), at
            wholes = engine.whole_actions(session.state, step.actor)
            index = next(
                index
                for index, whole in enumerate(wholes)
                if (taken := _expansion(engine, session.state, whole))
                == list(steps[at : at + len(taken)])
            )
            self.take_index(step.actor, index)
        assert session.steps == list(steps)


def _new_table(case: Case) -> Table:
    manager = GameSessionManager()
    summary = manager.create_game(
        HUMANS,
        base_game=case.base_game.value,
        bloodlines=case.bloodlines,
        rise_of_ix=case.rise_of_ix,
        immortality=True,
        promo_cards=True,
        game_seed=case.seed,
    )
    return Table(manager, str(summary["game_id"]))


def _load(document: JsonObject) -> Table:
    manager = GameSessionManager()
    summary = manager.restore_game(_reload(document))
    return Table(manager, str(summary["game_id"]))


# --------------------------------------------------------- the original run


@dataclass(frozen=True, slots=True)
class Boundary:
    """The owner's position at one boundary of the original run."""

    state_hash: str
    rows: list[dict[str, object]]
    summary: JsonObject
    document: JsonObject


@dataclass(frozen=True, slots=True)
class Original:
    """A case's run straight through its reopened turn."""

    owner: int
    # Saved just before the first press.
    before_press: JsonObject
    press_events: tuple[str, ...]
    boundaries: dict[str, Boundary]
    # The next seat's turn, after the second press.
    next_hash: str
    next_owner: int
    next_summary: JsonObject
    next_document: JsonObject


def _next_seat(table: Table) -> tuple[str, int]:
    """The state hash and turn owner where the game rests after the press."""

    top = table.session_state.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    owner = dict(top.context)["turn_owner"]
    assert isinstance(owner, int)
    return table.state_hash(), owner


@cache
def _original(name: str) -> Original:
    case = CASES[name]
    steps, owner = _self_play(case)
    table = _new_table(case)
    table.play_recorded(steps)
    table.take_all(owner, case.before_press)
    table.resolve_to_the_end(owner)
    before_press = table.save()
    session = table.manager._get(table.game_id)
    logged = len(session.log)
    table.take(owner, ("finish_agent_turn", {}))
    press_events = tuple(
        event.kind for step in live_steps(session.log[logged:]) for event in step.events
    )
    boundaries: dict[str, Boundary] = {}
    taken = 0
    for boundary, (lead, _detour) in sorted(
        case.boundaries.items(), key=lambda item: item[1][0]
    ):
        table.take_all(owner, case.rest[taken:lead])
        taken = lead
        boundaries[boundary] = Boundary(
            state_hash=table.state_hash(),
            rows=table.rows(owner),
            summary=table.summary(),
            document=table.save(),
        )
    table.take_all(owner, case.rest[taken:])
    next_hash, next_owner = _next_seat(table)
    assert next_owner != owner
    return Original(
        owner=owner,
        before_press=before_press,
        press_events=press_events,
        boundaries=boundaries,
        next_hash=next_hash,
        next_owner=next_owner,
        next_summary=table.summary(),
        next_document=table.save(),
    )


def _at_boundary(case: Case, original: Original, boundary: str) -> Table:
    """A loaded copy of the game before the press, pressed and led on to
    ``boundary`` as the original run was."""

    table = _load(original.before_press)
    table.take(original.owner, ("finish_agent_turn", {}))
    lead, _ = case.boundaries[boundary]
    table.take_all(original.owner, case.rest[:lead])
    assert table.state_hash() == original.boundaries[boundary].state_hash
    return table


def _finish_turn(case: Case, original: Original, table: Table, boundary: str) -> None:
    """Play the rest of the turn from ``boundary`` and check the next seat."""

    lead, _ = case.boundaries[boundary]
    summary = table.take_all(original.owner, case.rest[lead:])
    assert summary["decision"] == original.next_summary["decision"]
    assert summary["confirmation"] is None
    assert _next_seat(table) == (original.next_hash, original.next_owner)


# ------------------------------------------------------------------ the tests


@pytest.mark.parametrize("name", list(CASES))
def test_the_press_reopens_the_turn_in_a_real_server_game(name: str) -> None:
    # OQ-095 (5): the press's trash leaves something the turn owes, so the
    # owner's turn reopens instead of handing over, and the press sealed
    # what came before it (an explicit turn end, ``_settle_locked``).
    case = CASES[name]
    original = _original(name)
    assert "usurped_card_trashed" in original.press_events
    assert original.press_events[-1] == "agent_turn_reopened"
    reopened = original.boundaries[REOPENED]
    decision = _obj(reopened.summary["decision"])
    assert decision["owner"] == original.owner
    assert decision["kind"] == "agent_effects"
    assert reopened.summary["confirmation"] is None
    assert all(row["seat"] != original.owner for row in _rows(reopened.summary["undo"]))
    offered = {str(row["action_id"]) for row in reopened.rows}
    if name == "eliminate_allies":
        # The two troops are this turn's recruits on a Combat space.
        assert {"deploy_troops", "finish_agent_turn"} <= offered
        assert decision["turn_end_ready"] is True
    elif name == "freighter_fleet":
        # The Unload's "may" Freighter, offered in the reopened turn (OQ-160,
        # user ruling 2026-10-31): it holds no turn end.
        assert {"resolve_unload_icon", "finish_agent_turn"} <= offered
        assert decision["turn_end_ready"] is True
    else:
        # The Unload is owed: it holds the turn's end.
        assert "resolve_unload_icon" in offered
        assert "finish_agent_turn" not in offered
        assert decision["turn_end_ready"] is False
        window = original.boundaries[ACQUISITION_WINDOW]
        assert _obj(window.summary["decision"])["kind"] == "unload_icons"
        acquisitions = [
            row
            for row in window.rows
            if row["action_id"] == "acquire_unload_imperium_card"
        ]
        assert acquisitions and all(row["undoable"] is False for row in acquisitions)
    table = _at_boundary(case, original, REOPENED)
    with pytest.raises(SessionError, match="at most 0 step"):
        table.undo(original.owner, 1)


@pytest.mark.parametrize(("name", "boundary"), BOUNDARY_CASES)
def test_an_undo_back_to_the_boundary_replays_to_the_same_next_seat(
    name: str, boundary: str
) -> None:
    case = CASES[name]
    original = _original(name)
    expected = original.boundaries[boundary]
    table = _at_boundary(case, original, boundary)
    _, detour = case.boundaries[boundary]
    window = table.undo_window(original.owner)
    table.take_all(original.owner, detour)
    assert table.state_hash() != expected.state_hash
    assert table.undo_window(original.owner) == window + len(detour)

    summary = table.undo(original.owner, len(detour))

    assert table.state_hash() == expected.state_hash
    assert table.rows(original.owner) == expected.rows
    assert summary["decision"] == expected.summary["decision"]
    assert summary["confirmation"] == expected.summary["confirmation"]
    assert summary["undo"] == expected.summary["undo"]
    _finish_turn(case, original, table, boundary)
    # The game with the undo in its log saves, loads and replays to the
    # same next seat.
    document = table.save()
    loaded = _load(document)
    assert loaded.state_hash() == original.next_hash
    assert loaded.summary()["undo_count"] == 1
    verify_converted_save(_reload(document))


@pytest.mark.parametrize(("name", "boundary"), BOUNDARY_CASES)
def test_a_save_at_the_boundary_loads_and_finishes_the_same_turn(
    name: str, boundary: str
) -> None:
    case = CASES[name]
    original = _original(name)
    expected = original.boundaries[boundary]

    table = _load(expected.document)

    assert table.state_hash() == expected.state_hash
    assert table.rows(original.owner) == expected.rows
    summary = table.summary()
    for key in ("decision", "confirmation", "undo", "revision", "round_number"):
        assert summary[key] == expected.summary[key], key
    _finish_turn(case, original, table, boundary)


@pytest.mark.parametrize(("name", "boundary"), BOUNDARY_CASES)
def test_a_save_at_the_boundary_replays_to_its_state_hash(
    name: str, boundary: str
) -> None:
    original = _original(name)
    expected = original.boundaries[boundary]
    for document, state_hash in (
        (expected.document, expected.state_hash),
        (original.next_document, original.next_hash),
    ):
        replay = parse_save_document(_reload(document)).replay
        assert replay.expected_state_hash == state_hash
        assert canonical_state_hash(replay_game(UprisingRulesEngine(), replay)) == (
            state_hash
        )
        # The records check: loads as the server loads it, replays here to
        # its hash with no bridge.
        verify_converted_save(_reload(document))
