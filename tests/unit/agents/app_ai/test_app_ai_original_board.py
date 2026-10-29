"""The original board's space ports (abilities/original_board.py, plan §12).

Each test builds a real original ``GameState`` (``app_ai.testing``), stubs
the ``Profile`` prices with simple linear ones, and checks the subclass's
own terms against the generic ``SpaceAbility`` value of the same space, so
each branch of the decompiled method is pinned by hand.
"""

import logging
from collections.abc import Callable
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import original_board as ob
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Request,
    SelectionMode,
    TargetInfo,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.catalog import (
    ORIGINAL_SPACE_ARCHETYPES,
    card_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import agent_effects
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
BOARD = Board.of(ORIGINAL)
ENGINE = UprisingRulesEngine()


def _stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: 0.5 * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "persuasion_value": lambda n: 0.75 * n,
        "card_draw_value": lambda: 1.5,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "trash_card_value": lambda: 1.2,
        "trash_mod": lambda: 0.3,
        "mentat_value": lambda: 4.0,
        "swordmaster_value": lambda: 50.0,
        "foldspace_value": lambda: 2.5,
        "spice_for_sell_melange": lambda: 0,
        "game_arc": lambda: 0,
        "is_climax": lambda: False,
        "abundance_level": lambda attr: 1,
        "deploy_value": lambda owner: 1.25,
        "current_conflict_interest": lambda: Summer(3.0),
        "conflict_posture_bounds": lambda: (2.0, 5.0),
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """The first original ``turn`` decision (round 1)."""

    return first_decision("turn", config=ORIGINAL)


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **stub overrides) -> Profile`` for the deciding seat."""

    def build(state: GameState, **overrides: Callable[..., Any]) -> Profile:
        profile = make_profile(state, _seat(state))
        stubs = _stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def _one_more_agent(state: GameState, seat: int, **changes: object) -> GameState:
    """``seat`` with the Swordmaster or the Mentat: one Agent more."""

    available = state.players[seat].agents_available + 1
    return with_player(state, seat, agents_available=available, **changes)


def _space_value(p: Profile, space_id: str, cls: type[Ability]) -> float:
    space = space_entity(space_id, p.ctx.board)
    (ability,) = [a for a in abilities_of(space) if type(a) is cls]
    return ability.value_for_player(p).sum


def _generic(p: Profile, space_id: str) -> float:
    return g.SpaceAbility(space_entity(space_id, p.ctx.board)).value_for_player(p).sum


def test_every_original_space_ability_resolves_to_a_port() -> None:
    for space_id in ORIGINAL_SPACE_ARCHETYPES:
        for ability in abilities_of(space_entity(space_id, BOARD)):
            assert not isinstance(ability, UnportedAbility), (space_id, ability)


def test_conspire_adds_its_bonus_without_the_swordmaster_early_on(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    rich = with_player(turn_state, seat, resources=Resources(spice=4))
    p = prof(rich)
    bonus = p.C.ConspireSpaceBonus
    value = _space_value(p, "conspire", ob.ConspireSpaceAbility)
    assert value == pytest.approx(_generic(p, "conspire") + bonus)
    three = prof(with_player(turn_state, seat, resources=Resources(spice=3)))
    assert _space_value(three, "conspire", ob.ConspireSpaceAbility) == pytest.approx(
        _generic(three, "conspire")
    )
    mid = prof(rich, game_arc=lambda: 1)
    assert _space_value(mid, "conspire", ob.ConspireSpaceAbility) == pytest.approx(
        _generic(mid, "conspire") + bonus
    )
    late = prof(rich, game_arc=lambda: 2)
    assert _space_value(late, "conspire", ob.ConspireSpaceAbility) == pytest.approx(
        _generic(late, "conspire")
    )
    armed = prof(_one_more_agent(rich, seat, swordmaster_acquired=True))
    assert _space_value(armed, "conspire", ob.ConspireSpaceAbility) == pytest.approx(
        _generic(armed, "conspire")
    )


def test_mentat_space_values_the_mentat_only_while_it_rests(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    assert p.ctx.mentat_rests
    value = _space_value(p, "mentat", ob.MentatSpaceAbility)
    assert value == pytest.approx(_generic(p, "mentat") + 4.0)
    taken = prof(_one_more_agent(turn_state, (_seat(turn_state) + 1) % 4, mentat=True))
    assert not taken.ctx.mentat_rests
    assert _space_value(taken, "mentat", ob.MentatSpaceAbility) == pytest.approx(
        _generic(taken, "mentat")
    )
    owed = prof(with_state(turn_state, mentat_owed_to=_seat(turn_state)))
    assert _space_value(owed, "mentat", ob.MentatSpaceAbility) == pytest.approx(
        _generic(owed, "mentat")
    )


def test_swordmaster_space_adds_the_swordmaster_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    space = space_entity("imperium_swordmaster", p.ctx.board)
    assert space.int_attr("SolariCost") == 8
    value = _space_value(p, "imperium_swordmaster", ob.SwordmasterSpaceAbility)
    assert value == pytest.approx(_generic(p, "imperium_swordmaster") + 50.0)


def test_sell_melange_values_the_app_amount(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    none = prof(turn_state)
    base = _generic(none, "sell_melange")
    cls = ob.SellMelangeSpaceAbility
    assert _space_value(none, "sell_melange", cls) == pytest.approx(base)
    three = prof(turn_state, spice_for_sell_melange=lambda: 3)
    bonus = three.C.SellMelangeSpaceBonus
    # 3 spice for 8 Solari, plus the missing-Swordmaster bonus early on.
    expected = base + 0.5 * -3 + 0.25 * 8 + bonus
    assert _space_value(three, "sell_melange", cls) == pytest.approx(expected)
    late = prof(turn_state, spice_for_sell_melange=lambda: 3, game_arc=lambda: 2)
    assert _space_value(late, "sell_melange", cls) == pytest.approx(base - 1.5 + 2.0)
    assert [ob.sell_melange_solari(n) for n in (2, 3, 4, 5)] == [6, 8, 10, 12]


def test_sell_melange_evaluate_answers_the_spice_sold(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ob.SellMelangeSpaceAbility(space_entity("sell_melange", BOARD))
    assert ability.evaluate(prof(turn_state), Request()).response is None
    four = ability.evaluate(
        prof(turn_state, spice_for_sell_melange=lambda: 4), Request()
    )
    assert four.response == ((4,),)
    assert four.value == pytest.approx(0.25 * 10 - 0.5 * 4)
    # A non-positive sum is reset to the literal 1.0.
    dear = prof(
        turn_state, spice_for_sell_melange=lambda: 2, spice_value=lambda n: 5.0 * n
    )
    answer = ability.evaluate(dear, Request())
    assert (answer.value, answer.response) == (1.0, ((2,),))


def test_hall_of_oratory_is_the_generic_space_and_a_persuasion_trigger(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    space = space_entity("hall_of_oratory", p.ctx.board)
    kinds = [type(a) for a in abilities_of(space)]
    assert kinds == [ob.HallOfOratoryAbility2, ob.HallOfOratorySpaceAbility]
    assert _space_value(p, "hall_of_oratory", ob.HallOfOratorySpaceAbility) == (
        pytest.approx(_generic(p, "hall_of_oratory"))
    )
    trigger = ob.HallOfOratoryAbility2(space)
    assert trigger.value_for_player(p).sum == pytest.approx(0.75)
    assert not trigger.should_exhaust


def test_foldspace_gains_the_card_while_one_is_left(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    ability = ob.FoldspaceDeferredAbility(space_entity("foldspace", BOARD))
    assert ability.selection_mode(p) is SelectionMode.EXPLICIT
    assert ob.foldspace_in_reserve(p) and ability.meets_cost(p)
    assert ability.value_for_player(p).sum == pytest.approx(2.5)
    assert ability.evaluate(p, Request()).value == 100.0
    assert ability.evaluate(p, Request()).response == ((0,),)
    stacks = tuple(
        (card, 0 if card == ob.FOLDSPACE_CARD else n)
        for card, n in turn_state.reserve_stacks
    )
    empty = prof(with_state(turn_state, reserve_stacks=stacks))
    assert not ability.meets_cost(empty)
    assert ability.value_for_player(empty).sum == 0.0


def test_selective_breeding_trashes_junk_or_its_least_valued_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    p = prof(turn_state)
    space = space_entity("selective_breeding", BOARD)
    ability = ob.SelectiveBreedingDeferredAbility(space)
    assert ability.selection_mode(p) is SelectionMode.EXPLICIT
    assert ability.value_for_player(p).sum == pytest.approx(1.2 + 2 * 1.8 + 0.3)
    hand = [card_entity(ref, seat) for ref in turn_state.players[seat].hand]
    request = Request(infos=(TargetInfo(entities=tuple(hand)),))
    junk = prof(turn_state, card_to_trash=lambda targets, floor: (targets[-1], 2.0))
    answer = ability.evaluate(junk, request)
    assert answer.response == ((hand[-1].ref,),)
    assert answer.value == pytest.approx(2.0 + 2 * 1.8)
    values = {card.ref: float(i % 3) for i, card in enumerate(hand)}
    plain = prof(
        turn_state,
        card_to_trash=lambda targets, floor: (None, 1.0),
        acquire_value=lambda card: Summer(values[card.ref]),
    )
    least = min(hand, key=lambda card: values[card.ref])  # first of the least
    answer = ability.evaluate(plain, request)
    assert answer.response == ((least.ref,),)
    assert answer.value == pytest.approx(1.0 + 2 * 1.8)


_SPACE_REASONS = ("Maker space", "board ", "Desert Tactics trash")


def test_original_spaces_leave_no_agent_turn_unmapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every original space's Agent-turn effects are mirrored (census
    reasons of plan §12.2: Maker spaces, Foldspace, the Mentat, Selective
    Breeding), and Sell Melange's amount is the app's."""

    reasons: list[str] = []
    collect = agent_effects._collect

    def spy(t: Any) -> None:
        collect(t)
        reasons.extend(t.unmapped)

    monkeypatch.setattr(agent_effects, "_collect", spy)
    logging.getLogger("dune_imperium.agents.app_ai.agent").setLevel(logging.ERROR)
    for seed in (3, 4):
        agents = tuple(AppAIAgent(seed=seed * 10 + seat) for seat in range(4))
        run_policy_game(ENGINE, ORIGINAL, seed, agents)
    assert not [r for r in reasons if r.startswith(_SPACE_REASONS)]
