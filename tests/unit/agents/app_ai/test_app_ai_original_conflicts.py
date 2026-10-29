"""The original game's Conflict cards in the app AI (plan §12, slice 3).

``abilities/original_conflicts.py`` ports the 54 ``ConflictAbilities.BaseSet``
classes; ``windows/combat.py`` answers their reward choices; ``profile/combat.py``
reads their values (``ConflictValue``, the literal ``RelativeConflictValue``
tables of a game without Uprising). Each test builds a real original
``GameState`` (``app_ai.testing``), stubs the ``Profile`` prices with simple
affine ones (so a price taken at 3 is not mistaken for three prices at 1) and
checks the terms against values worked out by hand from the decompiled code.
"""

from collections.abc import Callable, Sequence
from typing import Any

import pytest

from dune_imperium import RulesetConfig
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
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState

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
