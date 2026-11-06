"""The original game's Conflict cards in the app AI (plan §12, slice 3).

``abilities/original_conflicts.py`` ports the 54 ``ConflictAbilities.BaseSet``
classes; ``windows/combat.py`` answers their reward choices; ``profile/combat.py``
reads their values (``ConflictValue``, the literal ``RelativeConflictValue``
tables of a game without Uprising). Each test builds a real original
``GameState`` (``app_ai.testing``), stubs the ``Profile`` prices with simple
affine ones (so a price taken at 3 is not mistaken for three prices at 1) and
checks the terms against values worked out by hand from the decompiled code.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import replace
from functools import cache
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities import original_conflicts as oc
from dune_imperium.agents.app_ai.abilities.base import (
    Request,
    TargetInfo,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.board import (
    granted_reward_abilities,
    place_reward_ability,
)
from dune_imperium.agents.app_ai.abilities.generic import ConflictAbility
from dune_imperium.agents.app_ai.catalog import (
    ORIGINAL_CONFLICT_ARCHETYPES,
    card_entity,
    conflict_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import combat as W
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.combat import (
    REWARD_LINE_KINDS,
    chosen_reward_lines,
    legacy_combat_reward_icon,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
CA = "worm.canis.abilities.ConflictAbilities.BaseSet."

# ---------------------------------------------------------------------------
# Stubbed prices: affine, so ``spice_value(3)`` differs from
# ``3 * spice_value(1)`` and a literal multiplier is told from a larger amount
# ---------------------------------------------------------------------------

INFLUENCE = {"emperor": 2.0, "spacing_guild": 2.5, "bene_gesserit": 3.0, "fremen": 1.0}
INTRIGUE = 2.25
CONTROL_SOLARI = 4.0
CONTROL_SPICE = 5.5
MENTAT = 7.25
TRASH = 1.2
TRASH_MOD = 0.3


def vp(n: int) -> float:
    return 6.0 * n + 0.5


def water(n: int) -> float:
    return 1.0 * n + 0.04


def spice(n: int) -> float:
    return 0.5 * n + 0.02


def solari(n: int) -> float:
    return 0.25 * n + 0.03


def influence(faction: str, n: int) -> Summer:
    if faction == "none":  # ``Factions.None``: the best faction's summer
        return Summer(max(INFLUENCE[f] * n + 0.07 for f in INFLUENCE))
    return Summer(INFLUENCE[faction] * n + 0.07)


# ``GetGainInfluenceValue(Factions.None, n)``: the best faction (Bene Gesserit).
def any_influence(n: int) -> float:
    return INFLUENCE["bene_gesserit"] * n + 0.07


# The resource attribute -> price of ``GetResourceValue(attr, n)``.
RESOURCE = {Attr.SOLARI: solari, Attr.SPICE: spice, Attr.WATER: water}


def _resource_value(attr: Attr, n: int, include: bool = False) -> float:
    return {Attr.SOLARI: 0.5, Attr.SPICE: 1.0, Attr.WATER: 2.0}[attr] * n + 0.01


def _stubs() -> dict[str, Callable[..., Any]]:
    return {
        "victory_point_value": vp,
        "water_value": water,
        "spice_value": spice,
        "solari_value": solari,
        "intrigue_value": lambda: INTRIGUE,
        "control_solari_value": lambda: CONTROL_SOLARI,
        "control_spice_value": lambda: CONTROL_SPICE,
        "mentat_value": lambda: MENTAT,
        "trash_card_value": lambda: TRASH,
        "trash_mod": lambda: TRASH_MOD,
        "resource_value": _resource_value,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: influence(f, n),
        "game_arc": lambda: 0,
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


def _place(card_id: str, place: int) -> ConflictAbility:
    ability = abilities_of(conflict_entity(card_id, False))[place - 1]
    assert isinstance(ability, ConflictAbility)
    return ability


# ---------------------------------------------------------------------------
# The ports
# ---------------------------------------------------------------------------


def test_every_original_conflict_ability_resolves_to_a_port() -> None:
    count = 0
    for card_id in ORIGINAL_CONFLICT_ARCHETYPES:
        for choam in (False, True):
            card = conflict_entity(card_id, choam)
            abilities = abilities_of(card)
            assert len(abilities) == 3, card_id
            places = []
            for ability in abilities:
                assert not isinstance(ability, UnportedAbility), (card_id, ability)
                assert isinstance(ability, ConflictAbility)
                places.append(ability.place)
            assert places == [1, 2, 3], card_id
            assert [a.APP_CLASS for a in abilities] == list(
                card.list_attr("WormAbilityIDs")
            )
        count += 3
    assert count == 54


def test_the_ports_are_the_app_classes_under_conflict_ability() -> None:
    names = {
        type(ability).__name__
        for card_id in ORIGINAL_CONFLICT_ARCHETYPES
        for ability in abilities_of(conflict_entity(card_id, False))
    }
    assert len(names) == 54
    for card_id in ORIGINAL_CONFLICT_ARCHETYPES:
        for ability in abilities_of(conflict_entity(card_id, False)):
            assert ability.APP_CLASS.startswith(CA)
            assert type(ability).__mro__[1] is ConflictAbility


def test_no_original_place_ability_grants_a_custom_reward() -> None:
    for card_id in ORIGINAL_CONFLICT_ARCHETYPES:
        card = conflict_entity(card_id, False)
        for place in (1, 2, 3):
            found = place_reward_ability(card, place)
            assert type(found) is type(_place(card_id, place))
            assert granted_reward_abilities(card, place) == ()


# The ``VictoryPoints`` of the card at place 1 (``ConflictAbility::
# GetPossibleRewardVP @0x4b6ea00``, no BaseSet class overrides it).
CARD_VP = {
    "skirmish_a": 1,
    "skirmish_b": 1,
    "skirmish_c": 0,
    "skirmish_d": 0,
    "cloak_and_dagger": 0,
    "desert_power_conflict": 1,
    "guild_bank_raid": 0,
    "machinations": 0,
    "raid_stockpiles": 0,
    "imperium_secure_imperial_basin": 1,
    "imperium_siege_of_arrakeen": 1,
    "siege_of_carthag": 1,
    "sort_through_the_chaos": 0,
    "terrible_purpose": 1,
    "imperium_battle_for_arrakeen": 2,
    "battle_for_carthag": 2,
    "imperium_battle_for_imperial_basin": 2,
    "grand_vision": 0,
}


@pytest.mark.parametrize(("card_id", "points"), CARD_VP.items())
def test_possible_reward_vp_is_the_cards_victory_points_at_place_one(
    turn_state: GameState, prof: ProfileFactory, card_id: str, points: int
) -> None:
    p = prof(turn_state)
    assert set(CARD_VP) == set(ORIGINAL_CONFLICT_ARCHETYPES)
    for double_cost in (False, True):
        assert _place(card_id, 1).possible_reward_vp(p, double_cost) == points
        assert _place(card_id, 2).possible_reward_vp(p, double_cost) == 0
        assert _place(card_id, 3).possible_reward_vp(p, double_cost) == 0


# card -> the ``ValueForPlayer`` sums of its three places, worked out from the
# decompiled ``Add`` calls (``Conflict <Card> <Place> ...`` labels) with the
# stubbed prices above.
VALUES: dict[
    str, tuple[Callable[[], float], Callable[[], float], Callable[[], float]]
] = {
    "skirmish_a": (lambda: vp(1), lambda: water(1), lambda: spice(1)),
    "skirmish_b": (
        lambda: vp(1),
        lambda: solari(2) + INTRIGUE,
        lambda: solari(2),
    ),
    "skirmish_c": (
        lambda: spice(1) + any_influence(1),
        lambda: spice(1) + spice(1),
        lambda: spice(1),
    ),
    "skirmish_d": (
        lambda: solari(2) + any_influence(1),
        lambda: solari(3),
        lambda: solari(2),
    ),
    "cloak_and_dagger": (
        lambda: any_influence(1) + (INTRIGUE + INTRIGUE),
        lambda: spice(1) + INTRIGUE,
        lambda: max(INTRIGUE, spice(1)),
    ),
    "desert_power_conflict": (
        lambda: vp(1) + water(1),
        lambda: spice(1) + water(1),
        lambda: spice(1),
    ),
    "guild_bank_raid": (lambda: solari(6), lambda: solari(4), lambda: solari(2)),
    "machinations": (
        lambda: any_influence(1) + (INFLUENCE["spacing_guild"] + 0.07),
        lambda: water(1) + solari(2),
        lambda: water(1),
    ),
    "raid_stockpiles": (
        lambda: spice(1) * 3.0 + INTRIGUE,
        lambda: spice(1) + spice(1),
        lambda: spice(1),
    ),
    "imperium_secure_imperial_basin": (
        lambda: vp(1) + CONTROL_SPICE,
        lambda: water(1) + water(1),
        lambda: water(1),
    ),
    "imperium_siege_of_arrakeen": (
        lambda: vp(1) + CONTROL_SOLARI,
        lambda: solari(4),
        lambda: solari(2),
    ),
    "siege_of_carthag": (
        lambda: vp(1) + CONTROL_SOLARI,
        # The app prices 2 Solari where the card gains 1 Spice: kept.
        lambda: solari(2) + INTRIGUE,
        lambda: spice(1),
    ),
    "sort_through_the_chaos": (
        lambda: INTRIGUE + MENTAT + solari(2),
        lambda: INTRIGUE + solari(2),
        lambda: solari(2),
    ),
    "terrible_purpose": (
        lambda: vp(1) + TRASH + TRASH_MOD,
        lambda: water(1) + spice(1),
        lambda: spice(1),
    ),
    "imperium_battle_for_arrakeen": (
        lambda: vp(2) + CONTROL_SOLARI,
        lambda: max(INTRIGUE, max(spice(1) + spice(1), solari(3))),
        lambda: solari(2) + INTRIGUE,
    ),
    "battle_for_carthag": (
        lambda: vp(2) + CONTROL_SOLARI,
        lambda: spice(1) * 3.0 + INTRIGUE,
        lambda: spice(1) * 3.0,
    ),
    "imperium_battle_for_imperial_basin": (
        lambda: vp(2) + CONTROL_SPICE,
        lambda: spice(1) * 5.0,
        lambda: spice(1) * 3.0,
    ),
    "grand_vision": (
        lambda: any_influence(2) + INTRIGUE,
        lambda: spice(1) * 3.0 + INTRIGUE,
        lambda: spice(1) * 3.0,
    ),
}


@pytest.mark.parametrize(
    ("card_id", "place"),
    [(card_id, place) for card_id in VALUES for place in (1, 2, 3)],
)
def test_value_for_player_of_every_place(
    turn_state: GameState, prof: ProfileFactory, card_id: str, place: int
) -> None:
    assert set(VALUES) == set(ORIGINAL_CONFLICT_ARCHETYPES)
    p = prof(turn_state)
    value = _place(card_id, place).value_for_player(p)
    assert value.sum == pytest.approx(VALUES[card_id][place - 1](), rel=1e-12)


def test_battle_for_arrakeen_second_prices_the_best_of_three(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    second = _place("imperium_battle_for_arrakeen", 2)
    # 2 Spice doubles the Spice price; the Intrigue and Solari(3) compete.
    p = prof(turn_state, intrigue_value=lambda: 0.1, solari_value=lambda n: 0.2 * n)
    assert second.value_for_player(p).sum == pytest.approx(2 * spice(1))
    p = prof(
        turn_state,
        intrigue_value=lambda: 0.1,
        spice_value=lambda n: 0.01 * n,
        solari_value=lambda n: 0.2 * n,
    )
    assert second.value_for_player(p).sum == pytest.approx(0.2 * 3)
    p = prof(turn_state, spice_value=lambda n: 0.01 * n, solari_value=lambda n: 0.1)
    assert second.value_for_player(p).sum == pytest.approx(INTRIGUE)


def test_cloak_and_dagger_third_prices_the_better_resource(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    third = _place("cloak_and_dagger", 3)
    p = prof(turn_state, spice_value=lambda n: 9.0 * n)
    assert third.value_for_player(p).sum == pytest.approx(9.0)
    p = prof(turn_state)
    assert third.value_for_player(p).sum == pytest.approx(INTRIGUE)


def test_machinations_first_sums_the_two_best_factions(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    first = _place("machinations", 1)
    p = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {"emperor": 4.0, "spacing_guild": 1.0, "bene_gesserit": 2.0, "fremen": 3.0}[
                f
            ]
        ),
    )
    assert first.value_for_player(p).sum == 7.0


def test_grand_vision_first_asks_the_two_influence_price(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    amounts: list[int] = []

    def gain(f: str, n: int, rank: int = -1, alliance: bool = False) -> Summer:
        amounts.append(n)
        return Summer(float(n))

    p = prof(turn_state, gain_influence_value=gain)
    assert _place("grand_vision", 1).value_for_player(p).sum == 2.0 + INTRIGUE
    assert set(amounts) == {2}
    assert len(amounts) == len(FACTIONS)


# ---------------------------------------------------------------------------
# The choices a class asks through its own evaluator
# ---------------------------------------------------------------------------


def _tracks(*factions: str) -> Request:
    return Request((TargetInfo(entities=tuple(track_entity(f) for f in factions)),))


def test_dotnet_sort3_is_the_three_element_network_not_a_stable_sort() -> None:
    assert oc.dotnet_sort3([(1.0, 0), (2.0, 1), (3.0, 2)]) == [
        (3.0, 2),
        (2.0, 1),
        (1.0, 0),
    ]
    # Equal values: no swap, and a later larger value jumps over the first
    # of them but not the second (a stable sort would give 7, 5@0, 5@1).
    assert oc.dotnet_sort3([(5.0, 0), (5.0, 1), (7.0, 2)]) == [
        (7.0, 2),
        (5.0, 1),
        (5.0, 0),
    ]
    assert oc.dotnet_sort3([(4.0, 0), (4.0, 1), (4.0, 2)]) == [
        (4.0, 0),
        (4.0, 1),
        (4.0, 2),
    ]
    assert oc.dotnet_sort3([(2.0, 0), (9.0, 1), (9.0, 2)]) == [
        (9.0, 1),
        (9.0, 2),
        (2.0, 0),
    ]
    with pytest.raises(ValueError):
        oc.dotnet_sort3([(1.0, 0)])


def test_dotnet_double_compare_orders_nan_first() -> None:
    nan = float("nan")
    assert oc._double_compare(1.0, 2.0) == -1
    assert oc._double_compare(2.0, 1.0) == 1
    assert oc._double_compare(2.0, 2.0) == 0
    assert oc._double_compare(nan, 1.0) == -1
    assert oc._double_compare(1.0, nan) == 1
    assert oc._double_compare(nan, nan) == 0


@pytest.mark.parametrize(
    ("card_id", "evaluate", "amount"),
    [
        ("skirmish_c", "evaluate", 1),
        ("skirmish_d", "evaluate", 1),
        ("cloak_and_dagger", "evaluate_faction", 1),
        ("grand_vision", "evaluate_faction", 2),
    ],
)
def test_the_faction_prompts_pick_the_best_track_without_a_boost(
    turn_state: GameState,
    prof: ProfileFactory,
    card_id: str,
    evaluate: str,
    amount: int,
) -> None:
    seen: list[tuple[str, int]] = []

    def gain(f: str, n: int, rank: int = -1, alliance: bool = False) -> Summer:
        seen.append((f, n))
        return influence(f, n)

    p = prof(turn_state, gain_influence_value=gain)
    ability = _place(card_id, 1)
    answer = getattr(ability, evaluate)(p, _tracks(*FACTIONS))
    assert answer.response == (("bene_gesserit",),)
    assert answer.value == pytest.approx(3.0 * amount + 0.07)  # no +100
    # Each track in target order, valued for the card's own amount.
    assert seen == [(f, amount) for f in FACTIONS]
    assert oc.track_choice_answer(ability, p, _tracks(*FACTIONS)) == answer


def test_the_faction_prompt_keeps_the_first_strictly_best_track(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            2.0 if f in ("spacing_guild", "fremen") else 1.0
        ),
    )
    answer = _place("skirmish_c", 1).evaluate(p, _tracks("fremen", "spacing_guild"))
    assert answer.response == (("fremen",),)
    answer = _place("skirmish_c", 1).evaluate(p, _tracks("spacing_guild", "fremen"))
    assert answer.response == (("spacing_guild",),)


def test_the_faction_prompt_without_a_track_is_the_untouched_choice(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    answer = _place("skirmish_d", 1).evaluate(prof(turn_state), Request())
    assert answer.response is None
    assert answer.value == 0.0


def test_track_choice_answer_is_only_for_the_four_faction_prompts(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    assert oc.track_choice_answer(_place("skirmish_a", 1), p, Request()) is None
    assert oc.track_choice_answer(_place("machinations", 1), p, Request()) is None
    assert set(oc.TRACK_CHOICE_ABILITIES) == {
        type(_place("skirmish_c", 1)),
        type(_place("skirmish_d", 1)),
        type(_place("cloak_and_dagger", 1)),
        type(_place("grand_vision", 1)),
    }


def test_machinations_first_names_the_two_best_tracks(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    answer = _place("machinations", 1).evaluate(p, _tracks(*FACTIONS))
    assert answer.response is not None
    assert set(answer.response[0]) == {"bene_gesserit", "spacing_guild"}
    assert answer.value == pytest.approx(3.07 + 2.57)
    # ``Math.Max(0.5, sum)``: a worthless pair is still worth 0.5.
    p = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(-1.0),
    )
    answer = _place("machinations", 1).evaluate(p, _tracks(*FACTIONS))
    assert answer.value == 0.5


def test_terrible_purpose_first_trashes_the_best_junk_or_nothing(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = _place("terrible_purpose", 1)
    dagger = card_entity("player:0:starter:dagger:0", 0)
    request = Request((TargetInfo(entities=(dagger,), max_select=1),))
    asked: list[float] = []

    def junk(cards: Sequence[Entity], minimum: float) -> tuple[Entity | None, float]:
        asked.append(minimum)
        return dagger, 2.5

    p = prof(turn_state, card_to_trash=junk)
    answer = ability.evaluate(p, request)
    assert answer.response == ((dagger.ref,),)
    assert answer.value == 12.5  # the trash score + 10.0
    assert asked == [1.0]
    p = prof(turn_state, card_to_trash=lambda cards, minimum: (None, 0.0))
    answer = ability.evaluate(p, request)
    assert answer.response == ((),)  # an empty target array: trash nothing
    assert answer.value == 10.0


def test_cloak_and_dagger_third_takes_the_first_strictly_better_option(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = _place("cloak_and_dagger", 3)
    request = Request((TargetInfo(options=(0, 1), forced=True),), forced=True)
    answer = ability.evaluate(prof(turn_state), request)
    assert (answer.response, answer.value) == (((0,),), INTRIGUE)  # Intrigue 2.25
    p = prof(turn_state, spice_value=lambda n: 4.0)
    answer = ability.evaluate(p, request)
    assert (answer.response, answer.value) == (((1,),), 4.0)
    p = prof(turn_state, spice_value=lambda n: INTRIGUE)
    answer = ability.evaluate(p, request)
    assert answer.response == ((0,),)  # a tie keeps the Intrigue


def test_battle_for_arrakeen_second_names_two_of_three_options(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = _place("imperium_battle_for_arrakeen", 2)
    request = Request((TargetInfo(options=(0, 1, 2), min_select=2, max_select=2),))
    # Intrigue 2.25, 2 Spice 1.04, 3 Solari 0.78: Intrigue and 2 Spice.
    answer = ability.evaluate(prof(turn_state), request)
    assert answer.response == ((0, 1),)
    assert answer.value == pytest.approx(INTRIGUE + (spice(1) + spice(1)))
    # 3 Solari first, then Intrigue (the value is the sum of the two).
    p = prof(turn_state, solari_value=lambda n: 5.0)
    answer = ability.evaluate(p, request)
    assert answer.response == ((2, 0),)
    assert answer.value == pytest.approx(5.0 + INTRIGUE)
    # Equal values go through .NET's network: the later of two equal values
    # lands first (Intrigue 3.0, 2 Spice 3.0, 3 Solari 3.0 stay in order, but
    # 3.0 / 3.0 / 4.0 gives option 2, then option 1).
    p = prof(
        turn_state,
        intrigue_value=lambda: 3.0,
        spice_value=lambda n: 1.5,
        solari_value=lambda n: 4.0,
    )
    answer = ability.evaluate(p, request)
    assert answer.response == ((2, 1),)
    assert answer.value == 7.0


def test_the_other_places_have_no_evaluator() -> None:
    for card_id in ORIGINAL_CONFLICT_ARCHETYPES:
        for place in (1, 2, 3):
            ability = _place(card_id, place)
            has = {
                "evaluate": type(ability).evaluate is not ConflictAbility.evaluate,
                "evaluate_faction": hasattr(ability, "evaluate_faction"),
            }
            expected = {
                ("skirmish_c", 1): "evaluate",
                ("skirmish_d", 1): "evaluate",
                ("cloak_and_dagger", 1): "evaluate_faction",
                ("grand_vision", 1): "evaluate_faction",
                ("machinations", 1): "evaluate",
                ("terrible_purpose", 1): "evaluate",
                ("cloak_and_dagger", 3): "evaluate",
                ("imperium_battle_for_arrakeen", 2): "evaluate",
            }.get((card_id, place))
            assert {k for k, v in has.items() if v} == (
                set() if expected is None else {expected}
            ), (card_id, place)


# ---------------------------------------------------------------------------
# The profile: ConflictValue, the possible VP and the literal level average
# ---------------------------------------------------------------------------


def with_conflict(state: GameState, conflict_id: str) -> GameState:
    return with_state(
        state,
        current_conflict_ids=(conflict_id,),
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
    )


def test_uprising_is_the_base_game_of_the_config(turn_state: GameState) -> None:
    assert make_profile(turn_state, _seat(turn_state)).ctx.uprising is False
    uprising = first_decision("turn")
    assert make_profile(uprising, _seat(uprising)).ctx.uprising is True


def test_conflict_abilities_carry_the_place_of_the_port(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(with_conflict(turn_state, "machinations"))
    card = conflict_entity("machinations", False)
    assert [place for place, _ in p._conflict_abilities(card)] == [1, 2, 3]
    third = p._conflict_ability_for_place(3)
    assert type(third) is type(_place("machinations", 3))
    assert type(p._conflict_ability_for_place(1)) is type(_place("machinations", 1))


def test_conflict_value_adds_the_three_places_of_a_base_set_card(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = prof(with_conflict(turn_state, "skirmish_b"))
    card = conflict_entity("skirmish_b", False)
    # (the 1st: 1 VP; the 2nd: 2 Solari and an Intrigue; the 3rd: 2 Solari)
    expected = vp(1) + (solari(2) + INTRIGUE) + solari(2)
    assert p._conflict_value(card).sum == pytest.approx(expected)
    # Fewer than four players: the 3rd place is skipped.
    monkeypatch.setattr(p, "_is_four_player", lambda: False)
    assert p._conflict_value(card).sum == pytest.approx(expected - solari(2))


@pytest.mark.parametrize(("card_id", "points"), CARD_VP.items())
def test_possible_combat_reward_vp_is_the_cards_victory_points(
    turn_state: GameState, prof: ProfileFactory, card_id: str, points: int
) -> None:
    p = prof(with_conflict(turn_state, card_id))
    for player in p.ctx.players:
        for double_cost in (False, True):
            got = p._possible_combat_reward_vp(card_id, player, double_cost)
            assert got == points  # whatever the player holds


def test_possible_end_of_round_score_adds_the_cards_points(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    state = with_conflict(turn_state, "imperium_battle_for_arrakeen")
    p = prof(state, current_combat_order=lambda: [0, 1, 2, 3])
    for seat in range(4):
        assert p.possible_end_of_round_score(seat) == p.ctx.vp(p.ctx.player(seat)) + 2


# Each level's table, worked out from the decompiled ``GetResourceValue`` /
# ``Add`` / ``Multiply`` calls of ``RelativeConflictValue @0x4900490``
# (``je 0x4900ee5``), with the stubbed prices above: the sum of the table
# scaled by 0.25 / 0.1 / 0.25 (``Multiply(avg, mod)``).

S, SP, WA = Attr.SOLARI, Attr.SPICE, Attr.WATER
LITERAL_TABLES: dict[tuple[int, bool], Callable[[], float]] = {
    (1, True): lambda: (
        0.25
        * (
            _resource_value(S, 11)
            + _resource_value(SP, 1) * 5.0
            + _resource_value(WA, 1)
            + INTRIGUE
            + (vp(1) + vp(1))
            + (any_influence(1) + any_influence(1))
        )
    ),
    (1, False): lambda: (
        0.25
        * (
            _resource_value(S, 7)
            + _resource_value(SP, 1) * 3.0
            + _resource_value(WA, 1)
            + INTRIGUE
            + (vp(1) + vp(1))
            + (any_influence(1) + any_influence(1))
        )
    ),
    (2, True): lambda: (
        0.1
        * (
            _resource_value(S, 26)
            + _resource_value(SP, 1) * 13.0
            + _resource_value(WA, 1) * 8.0
            + INTRIGUE * 8.0
            + vp(1) * 5.0
            + any_influence(1) * 3.0
            + (CONTROL_SOLARI + CONTROL_SOLARI)
            + CONTROL_SPICE
            + MENTAT
            + TRASH
        )
    ),
    (2, False): lambda: (
        0.1
        * (
            _resource_value(S, 20)
            + _resource_value(SP, 1) * 9.0
            + _resource_value(WA, 1) * 6.0
            + INTRIGUE * 7.0
            + vp(1) * 5.0
            + any_influence(1) * 3.0
            + (CONTROL_SOLARI + CONTROL_SOLARI)
            + CONTROL_SPICE
            + MENTAT
            + TRASH
        )
    ),
    # Level III prices Solari(2) and Spice(1) under the "Control..." labels.
    (3, True): lambda: (
        0.25
        * (
            _resource_value(S, 2)
            + _resource_value(SP, 1) * 22.0
            + INTRIGUE * 5.0
            + vp(1) * 6.0
            + (any_influence(1) + any_influence(1))
            + _resource_value(S, 2)
            + _resource_value(SP, 1)
        )
    ),
    (3, False): lambda: (
        0.25
        * (
            _resource_value(SP, 1) * 13.0
            + INTRIGUE * 4.0
            + vp(1) * 6.0
            + (any_influence(1) + any_influence(1))
            + _resource_value(S, 2)
            + _resource_value(SP, 1)
        )
    ),
}


@pytest.mark.parametrize(("level", "four"), LITERAL_TABLES)
def test_the_literal_level_average_of_a_game_without_uprising(
    turn_state: GameState, prof: ProfileFactory, level: int, four: bool
) -> None:
    p = prof(turn_state)
    avg = Summer()
    p._literal_conflict_average(avg, level, four)
    assert avg.sum == pytest.approx(LITERAL_TABLES[(level, four)](), rel=1e-12)


def test_an_unknown_level_adds_nothing_to_the_literal_average(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    for level in (0, 4):
        avg = Summer()
        p._literal_conflict_average(avg, level, True)
        assert avg.sum == 0.0


@pytest.mark.parametrize(
    ("card_id", "level"),
    [("skirmish_a", 1), ("cloak_and_dagger", 2), ("grand_vision", 3)],
)
def test_relative_conflict_value_divides_by_the_literal_table_in_the_original_game(
    turn_state: GameState, prof: ProfileFactory, card_id: str, level: int
) -> None:
    p = prof(with_conflict(turn_state, card_id))
    ccv = sum(VALUES[card_id][place]() for place in (0, 1, 2))
    expected = ccv / LITERAL_TABLES[(level, True)]()
    assert p.relative_conflict_value().sum == pytest.approx(expected, rel=1e-12)


def test_relative_conflict_value_keeps_the_uprising_pool_in_an_uprising_game(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = first_decision("turn")
    p = make_profile(state, _seat(state))
    assert p.ctx.uprising
    called: list[str] = []
    monkeypatch.setattr(
        p, "_literal_conflict_average", lambda *a: called.append("literal")
    )
    p.relative_conflict_value()
    assert called == []


def test_demand_respect_and_to_the_victor_add_to_the_relative_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    state = with_conflict(turn_state, "guild_bank_raid")
    base = prof(state).relative_conflict_value().sum
    respect = "intrigue:demand_respect:0"
    victor = "intrigue:to_the_victor:0"
    held = with_player(state, seat, intrigue_cards=(respect,))
    assert prof(held).relative_conflict_value().sum == pytest.approx(
        base + (any_influence(1) + 1.0)
    )
    held = with_player(state, seat, intrigue_cards=(victor,))
    assert prof(held).relative_conflict_value().sum == pytest.approx(
        base + _resource_value(SP, 1) * 3.0
    )
    held = with_player(state, seat, intrigue_cards=(respect, victor))
    assert prof(held).relative_conflict_value().sum == pytest.approx(
        base + (any_influence(1) + 1.0) + _resource_value(SP, 1) * 3.0
    )


# ---------------------------------------------------------------------------
# The reward windows (windows/combat.py)
# ---------------------------------------------------------------------------


@cache
def _combat_state() -> GameState:
    """The first original ``combat_intrigue`` decision (round 1)."""

    return play_until(
        lambda state, owner: state.decision_stack[-1].kind == "combat_intrigue",
        config=ORIGINAL,
        seed=1,
    )


def _is_line_pick(state: GameState) -> bool:
    frame = state.decision_stack[-1]
    if frame.kind != "combat_reward_icons":
        return False
    legacy = legacy_combat_reward_icon(state, _seat(state))
    return legacy is not None and dict(legacy.arguments)["effect"] in REWARD_LINE_KINDS


def _reward_window(
    conflict_id: str,
    strengths: tuple[int, int, int, int],
    until: Callable[[GameState], bool],
) -> GameState:
    """The first state satisfying ``until`` once ``conflict_id`` is resolved
    with ``strengths`` (combatants pass; reward rows are answered in the
    engine's older order, any other frame by its first action)."""

    state = with_conflict(_combat_state(), conflict_id)
    for seat, strength in enumerate(strengths):
        state = with_player(state, seat, combat_strength=strength)
    for _ in range(200):
        if until(state):
            return state
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):  # the pause between recipients
            state = ENGINE.apply(state, ChanceResolver(seed=1).resolve(decision)).state
            continue
        seat = _seat(state)
        kind = state.decision_stack[-1].kind
        if kind == "combat_intrigue":
            action = DomainAction("pass_combat_intrigue", seat)
        elif kind == "combat_reward_icons":
            assert not _is_line_pick(state)
            legacy = legacy_combat_reward_icon(state, seat)
            assert legacy is not None
            action = legacy
        else:
            action = ENGINE.whole_actions(state, seat)[0]
        state = apply_whole(ENGINE, state, action).state
    raise AssertionError(f"{conflict_id} never reached the window")


def _kind(kind: str) -> Callable[[GameState], bool]:
    return lambda state: state.decision_stack[-1].kind == kind


def _run(
    state: GameState, *, memory: Memory | None = None, rng_seed: int = 0
) -> DecisionRun:
    seat = _seat(state)
    profile = make_profile(state, seat, rng_seed=rng_seed)
    legal = tuple(ENGINE.whole_actions(state, seat))
    return DecisionRun(profile.ctx, profile, legal, profile.rng, memory or Memory())


def _args(action: DomainAction | None) -> tuple[str, dict[str, object]]:
    assert action is not None
    return action.action_id, dict(action.arguments)


@pytest.fixture
def linear_influence(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Real profiles with ``GetGainInfluenceValue`` replaced by strict weights
    (Bene Gesserit > Spacing Guild > Emperor > Fremen); returns the calls."""

    calls: list[tuple[str, int]] = []

    def gain(
        self: Profile, f: str, n: int, rank: int = -1, alliance: bool = False
    ) -> Summer:
        calls.append((f, n))
        return influence(f, n)

    monkeypatch.setattr(Profile, "gain_influence_value", gain)
    return calls


@pytest.mark.parametrize(
    ("card_id", "amount"),
    [
        ("skirmish_c", 1),
        ("skirmish_d", 1),
        ("cloak_and_dagger", 1),
        ("grand_vision", 2),
    ],
)
def test_the_faction_reward_takes_the_best_track_for_the_cards_amount(
    linear_influence: list[tuple[str, int]], card_id: str, amount: int
) -> None:
    state = _reward_window(card_id, (9, 5, 3, 1), _kind("combat_reward_influence"))
    run = _run(state)
    assert [dict(a.arguments)["faction"] for a in run.legal] == list(FACTIONS)
    del linear_influence[:]
    assert _args(W.combat_reward_influence(run)) == (
        "choose_combat_reward_influence",
        {"faction": "bene_gesserit"},
    )
    assert {n for _, n in linear_influence} == {amount}
    assert {f for f, _ in linear_influence} == set(FACTIONS)


def test_the_faction_reward_skips_a_track_the_frame_does_not_offer(
    linear_influence: list[tuple[str, int]],
) -> None:
    state = _reward_window("skirmish_c", (9, 5, 3, 1), _kind("combat_reward_influence"))
    seat = _seat(state)
    full = with_player(
        state,
        seat,
        influence=replace(state.players[seat].influence, bene_gesserit=6),
    )
    run = _run(full)
    assert [dict(a.arguments)["faction"] for a in run.legal] == [
        "emperor",
        "spacing_guild",
        "fremen",
    ]
    assert _args(W.combat_reward_influence(run))[1] == {"faction": "spacing_guild"}


def test_machinations_names_both_tracks_in_one_answer(
    linear_influence: list[tuple[str, int]],
) -> None:
    state = _reward_window(
        "machinations", (9, 5, 3, 1), _kind("combat_reward_distinct_influence")
    )
    memory = Memory()
    first = W.combat_reward_distinct_influence(_run(state, memory=memory))
    context = dict(state.decision_stack[-1].context)
    key = (
        W.DISTINCT_INFLUENCE_INTENT,
        state.round_number,
        _seat(state),
        context["group"],
    )
    assert memory.intents[key] == ("bene_gesserit", "spacing_guild")
    assert _args(first) == (
        "choose_distinct_combat_reward_influence",
        {"faction": "bene_gesserit"},
    )
    assert first is not None
    second_state = apply_whole(ENGINE, state, first).state
    assert second_state.decision_stack[-1].kind == "combat_reward_distinct_influence"
    second = W.combat_reward_distinct_influence(_run(second_state, memory=memory))
    assert _args(second) == (
        "choose_distinct_combat_reward_influence",
        {"faction": "spacing_guild"},
    )
    assert key not in memory.intents


def _trash_state(*starters: str) -> GameState:
    state = _reward_window(
        "terrible_purpose", (9, 5, 3, 1), _kind("combat_reward_trash")
    )
    seat = _seat(state)
    cards = tuple(f"player:{seat}:starter:{name}:0" for name in starters)
    deck = tuple(c for c in state.players[seat].deck if c not in cards)
    return with_player(state, seat, deck=deck, hand=(), in_play=(), discard_pile=cards)


def test_terrible_purpose_trashes_the_junk_card() -> None:
    state = _trash_state("diplomacy", "dagger", "signet_ring")
    seat = _seat(state)
    assert _args(W.combat_reward_trash(_run(state))) == (
        "trash_combat_reward_card",
        {"card_id": f"player:{seat}:starter:dagger:0"},
    )


def test_terrible_purpose_trashes_nothing_without_junk() -> None:
    state = _trash_state("diplomacy", "signet_ring")
    assert _args(W.combat_reward_trash(_run(state))) == (
        "decline_combat_reward_trash",
        {},
    )


@pytest.fixture
def prices(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace ``Profile`` prices by constants (a method's new value)."""

    def install(**values: float) -> None:
        for name, value in values.items():
            if name in ("spice_value", "solari_value"):
                monkeypatch.setattr(Profile, name, lambda self, n, _v=value: _v * n)
            else:
                monkeypatch.setattr(Profile, name, lambda self, _v=value: _v)

    return install


def _line(action: DomainAction | None) -> str:
    assert action is not None
    assert action.action_id == "resolve_combat_reward_icon"
    return str(dict(action.arguments)["effect"])


@pytest.mark.parametrize(
    ("prices_", "line"),
    [
        ({"intrigue_value": 3.0, "spice_value": 1.0}, "line_0"),
        ({"intrigue_value": 1.0, "spice_value": 3.0}, "line_1"),
        ({"intrigue_value": 2.0, "spice_value": 2.0}, "line_0"),
    ],
)
def test_cloak_and_dagger_third_takes_the_better_of_the_two(
    prices: Callable[..., None], prices_: dict[str, float], line: str
) -> None:
    state = _reward_window("cloak_and_dagger", (9, 5, 3, 0), _is_line_pick)
    prices(**prices_)
    run = _run(state)
    assert sorted(_line(a) for a in run.legal if a.action_id.startswith("resolve")) == [
        "line_0",
        "line_1",
    ]
    assert _line(W.combat_reward_icons(run)) == line


def test_battle_for_arrakeen_second_names_two_lines_in_the_apps_order(
    prices: Callable[..., None],
) -> None:
    state = _reward_window("imperium_battle_for_arrakeen", (9, 5, 0, 0), _is_line_pick)
    prices(intrigue_value=1.0, spice_value=2.0, solari_value=1.0)
    # Intrigue 1.0, 2 Spice 4.0, 3 Solari 3.0: option 1, then option 2.
    memory = Memory()
    first = W.combat_reward_icons(_run(state, memory=memory))
    assert _line(first) == "line_1"
    context = dict(state.decision_stack[-1].context)
    key = (W.REWARD_LINES_INTENT, state.round_number, _seat(state), context["rank"])
    assert memory.intents[key] == (1, 2)
    assert first is not None
    second_state = apply_whole(ENGINE, state, first).state
    assert chosen_reward_lines(second_state.decision_stack[-1]) == (1,)
    second = W.combat_reward_icons(_run(second_state, memory=memory))
    assert _line(second) == "line_2"
    assert key not in memory.intents
    # Without the plan the second pick asks the ability again.
    again = W.combat_reward_icons(_run(second_state, memory=Memory()))
    assert _line(again) == "line_2"


def test_the_agent_asks_the_line_window_instead_of_the_engine_order(
    prices: Callable[..., None],
) -> None:
    state = _reward_window("cloak_and_dagger", (9, 5, 3, 0), _is_line_pick)
    seat = _seat(state)
    legacy = legacy_combat_reward_icon(state, seat)
    assert legacy is not None and dict(legacy.arguments)["effect"] == "line_0"
    prices(intrigue_value=1.0, spice_value=3.0)
    legal = ENGINE.legal_actions(state, seat)
    action = AppAIAgent(seed=1).choose_action_with_state(
        state, ENGINE.observe(state, seat), legal
    )
    after = ENGINE.apply(state, action, legal_actions=legal).state
    assert chosen_reward_lines(after.decision_stack[-1]) == (1,)


def test_the_agent_still_pays_the_other_rows_in_the_engine_order() -> None:
    state = _reward_window(
        "cloak_and_dagger", (9, 5, 3, 0), _kind("combat_reward_icons")
    )
    seat = _seat(state)
    legal = ENGINE.legal_actions(state, seat)
    agent = AppAIAgent(seed=1)
    action = agent.choose_action_with_state(state, ENGINE.observe(state, seat), legal)
    assert action == engine_order_answer(state, seat, legal)
    assert not agent.fallbacks


def test_original_games_answer_every_conflict_reward_window() -> None:
    """Eight original games, four app_ai seats: no reward window falls back or
    fails (the line windows, the faction, two-faction and trash choices)."""

    engine = UprisingRulesEngine()
    config = RulesetConfig(base_game=BaseGame.IMPERIUM, leader_draft=True)
    mirrored: Counter[str] = Counter()
    fallbacks: Counter[str] = Counter()
    for seed in range(3000, 3008):
        agents = tuple(AppAIAgent(seed=seed * 10 + s, level=s % 3) for s in range(4))
        result = run_policy_game(engine, config, seed, agents)
        assert result.state.phase is GamePhase.FINISHED
        for agent in agents:
            mirrored.update(agent.mirrored)
            fallbacks.update(agent.fallbacks)
    assert not {k: n for k, n in fallbacks.items() if k.startswith("combat_reward")}
    assert not {k: n for k, n in fallbacks.items() if k.startswith("error:")}
    assert "combat_reward_influence" in mirrored
