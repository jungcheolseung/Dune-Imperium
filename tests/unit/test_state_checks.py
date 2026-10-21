"""The GameState invariants' field table (``core.state.STATE_CHECKS``).

A copy runs only the checks whose fields it replaced (``_check_copy``), so the
table must name every field a check reads: the tests below read each check
through recording proxies over real games, break each check through a copy
and expect the constructor's own error, and count the checks a copy runs.
"""

import dataclasses
from copy import replace
from functools import cache
from typing import Any

import pytest

from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core import state as state_module
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import STATE_CHECKS, GameState, StateCheck
from dune_imperium.rules import UprisingRulesEngine

ENGINE = UprisingRulesEngine()
EVERY_OPTION = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)
GAME_FIELDS = frozenset(field.name for field in dataclasses.fields(GameState))
SEAT_FIELDS = frozenset(field.name for field in dataclasses.fields(PlayerState))


def _play(config: RulesetConfig, seed: int, every: int) -> list[GameState]:
    """Every ``every``-th state of one seeded heuristic game."""

    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", seed=seed + seat) for seat in range(4)]
    kept: list[GameState] = []
    for step in range(6000):
        if step % every == 0:
            kept.append(state)
        decision = ENGINE.current_decision(state)
        if decision is None:
            break
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = ENGINE.legal_actions(state, decision.owner)
        view = ENGINE.observe(state, decision.owner)
        action = agents[decision.owner].choose_action(view, actions)
        state = ENGINE.apply(state, action, legal_actions=actions).state
    kept.append(state)
    return kept


@cache
def _states() -> tuple[GameState, ...]:
    """States of a base game and an every-option game: each check's module-on
    and module-off branches, with the zones filled as play fills them."""

    return (*_play(RulesetConfig(), 3, 9), *_play(EVERY_OPTION, 4, 9))


class _SeatReads:
    __slots__ = ("_player", "_seen")

    def __init__(self, player: PlayerState, seen: set[str]) -> None:
        self._player = player
        self._seen = seen

    def __getattr__(self, name: str) -> Any:
        self._seen.add(name)
        return getattr(self._player, name)


class _StateReads:
    __slots__ = ("_state", "_seen", "_seat_seen")

    def __init__(self, state: GameState, seen: set[str], seat_seen: set[str]) -> None:
        self._state = state
        self._seen = seen
        self._seat_seen = seat_seen

    def __getattr__(self, name: str) -> Any:
        self._seen.add(name)
        value = getattr(self._state, name)
        if name == "players":
            return tuple(_SeatReads(player, self._seat_seen) for player in value)
        return value


def _seat_reads(names: set[str], player: PlayerState) -> set[str]:
    """``names`` with each property replaced by the fields its getter reads."""

    fields: set[str] = set()
    for name in names:
        member = getattr(PlayerState, name, None)
        if isinstance(member, property):
            assert member.fget is not None
            inner: set[str] = set()
            member.fget(_SeatReads(player, inner))
            fields |= _seat_reads(inner, player)
        else:
            fields.add(name)
    return fields


@pytest.mark.parametrize("check", STATE_CHECKS, ids=lambda c: c.check.__name__)
def test_a_check_reads_only_the_fields_its_table_row_names(check: StateCheck) -> None:
    seen: set[str] = set()
    seat_seen: set[str] = set()
    for state in _states():
        check.run(_StateReads(state, seen, seat_seen))  # type: ignore[arg-type]
    player = _states()[-1].players[0]
    seat_fields = _seat_reads(seat_seen, player)

    assert seen - {"players"} <= check.fields, sorted(seen - check.fields)
    assert seat_fields <= check.seat_fields, sorted(seat_fields - check.seat_fields)
    if "players" in seen:
        assert "players" in check.fields or check.seat_fields
    # The table names real fields only, and each a check really reads.
    assert check.fields <= GAME_FIELDS and check.seat_fields <= SEAT_FIELDS
    assert check.fields <= seen and check.seat_fields <= seat_fields


def _seat(state: GameState, seat: int, **changes: Any) -> GameState:
    """``state`` with seat ``seat``'s player changed, through a state copy."""

    players = list(state.players)
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _mid_game() -> GameState:
    """An every-option state with the Contract, Tech, Skill, Tleilaxu and
    Conflict zones filled."""

    state = next(
        s for s in _states() if s.config == EVERY_OPTION and s.round_number == 2
    )
    assert state.contract_bank and state.conflict_deck and state.tleilaxu_deck
    assert any(state.tech_stacks) and state.skill_stack
    return state


def _corruptions() -> list[tuple[str, Any]]:
    mid = _mid_game()
    base = next(s for s in _states() if s.config == RulesetConfig() and s.round_number)
    zero = mid.players[0]
    return [
        ("round", lambda: replace(mid, round_number=-1)),
        ("first player", lambda: replace(mid, first_player=4)),
        ("reveal twice", lambda: replace(mid, reveal_order=(1, 1))),
        ("seats", lambda: replace(mid, players=mid.players[:3])),
        ("row", lambda: replace(mid, imperium_row=("a", "b", "c", "d", "e", "f"))),
        (
            "seat contract in the bank",
            lambda: _seat(mid, 0, active_contract_ids=(mid.contract_bank[0],)),
        ),
        (
            "won Conflict still in the deck",
            lambda: _seat(mid, 1, won_conflict_ids=(mid.conflict_deck[0],)),
        ),
        (
            "two Alliance owners",
            lambda: _seat(
                _seat(mid, 0, alliance_faction_ids=("fremen",)),
                1,
                alliance_faction_ids=("fremen",),
            ),
        ),
        ("Reserve twice", lambda: replace(mid, reserve_stacks=(("a", 1), ("a", 2)))),
        (
            "held Skill still stacked",
            lambda: _seat(mid, 2, skill_ids=(mid.skill_stack[0],)),
        ),
        (
            "held Tech still stacked",
            lambda: _seat(
                mid,
                3,
                tech_ids=(next(t for stack in mid.tech_stacks for t in stack),),
                tech_flipped=(),
            ),
        ),
        ("Tleilaxu twice", lambda: replace(mid, tleilaxu_row=(mid.tleilaxu_deck[0],))),
        (
            "specimens without Immortality",
            lambda: _seat(
                base,
                0,
                troops_supply=base.players[0].troops_supply - 1,
                specimens=1,
            ),
        ),
        (
            "parked troops without a row",
            lambda: _seat(
                mid,
                0,
                troops_supply=zero.troops_supply - 1,
                troops_parked=zero.troops_parked + 1,
            ),
        ),
        (
            "Makers out of order",
            lambda: replace(
                mid, maker_bonus_spice=tuple(reversed(mid.maker_bonus_spice))
            ),
        ),
    ]


@pytest.mark.parametrize("name", [name for name, _ in _corruptions()])
def test_a_copy_that_breaks_a_check_fails_like_the_constructor(name: str) -> None:
    make = dict(_corruptions())[name]
    with pytest.raises(ValueError) as fast:
        make()
    with pytest.raises(ValueError) as standard:
        _through_constructor(make)
    assert str(fast.value) == str(standard.value)


def _through_constructor(make: Any) -> None:
    """Run ``make`` with every GameState copy built by its constructor
    (``dataclasses.replace`` calls ``__init__``, so every check runs)."""

    def standard(self: GameState, /, **changes: Any) -> GameState:
        return dataclasses.replace(self, **changes)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(GameState, "__replace__", standard)
        make()


def _counting(check: StateCheck, runs: list[str]) -> StateCheck:
    def run(state: GameState) -> None:
        runs.append(check.check.__name__)
        check.run(state)

    return StateCheck(run, check.fields, check.seat_fields)


def test_a_copy_runs_only_the_checks_of_what_it_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[str] = []
    monkeypatch.setattr(
        state_module, "STATE_CHECKS", tuple(_counting(c, runs) for c in STATE_CHECKS)
    )
    state = _mid_game()

    replace(
        state, decision_stack=state.decision_stack[:-1], revision=state.revision + 1
    )
    assert runs == []
    _seat(state, 1, control_space_ids=("spice_refinery",))
    # The seat copy changes one field, which only the Scouts check reads; the
    # seat-order check reads ``players`` itself.
    assert sorted(runs) == ["_check_scouts", "_check_seats"]
    runs.clear()
    GameState(**{f.name: getattr(state, f.name) for f in dataclasses.fields(state)})
    assert runs == [check.check.__name__ for check in STATE_CHECKS]
