"""The original game's leader ports (abilities/original_leaders.py, plan §12).

Real original ``GameState`` plus stubbed ``Profile`` prices, as in
``test_app_ai_original_intrigue.py``: each branch, literal and constant of the
decompiled methods is pinned by hand.
"""

from collections.abc import Callable
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import (
    PORTS,
    Ability,
    SelectionMode,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities import leaders as leaders_module
from dune_imperium.agents.app_ai.abilities import original_leaders as ol
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.generic import DrawAbility
from dune_imperium.agents.app_ai.catalog import (
    ORIGINAL_LEADER_ARCHETYPES,
    card_entity,
    leader_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Attr
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
BOARD = Board.of(ORIGINAL)
ENGINE = UprisingRulesEngine()
AA = "worm.canis.abilities.ActivatedAbilities."
TA = "worm.canis.abilities.TriggeredAbilities.BaseSet."


def _stubs() -> dict[str, Callable[..., Any]]:
    return {
        "is_climax": lambda: False,
        "game_arc": lambda: 1,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            {"none": 2.5}.get(f, 2.0) * n
        ),
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "persuasion_value": lambda n: 0.8 * n,
        "intrigue_value": lambda: 2.5,
        "acquire_value": lambda card: Summer(card.float_attr("TestValue", 3.0)),
        "possible_persuasion": lambda: 5,
        "can_agent_ability_be_played_with_space": lambda space, attr, n: True,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    return first_decision("turn", config=ORIGINAL)


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    def build(state: GameState, **overrides: Callable[..., Any]) -> Profile:
        profile = make_profile(state, _seat(state))
        stubs = _stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def me(state: GameState, **changes: Any) -> GameState:
    return with_player(state, _seat(state), **changes)


def ab[A: Ability](leader_id: str, cls: type[A]) -> A:
    for candidate in abilities_of(leader_entity(leader_id)):
        if isinstance(candidate, cls):
            return candidate
    raise AssertionError(f"{leader_id} has no {cls.__name__}")


def tracks(*factions: str) -> TargetInfo:
    return TargetInfo(tuple(track_entity(f) for f in factions))


def test_every_original_leader_ability_resolves_to_a_port() -> None:
    assert len(ORIGINAL_LEADER_ARCHETYPES) == 8
    for leader_id in ORIGINAL_LEADER_ARCHETYPES:
        for ability in abilities_of(leader_entity(leader_id)):
            assert not isinstance(ability, UnportedAbility), (leader_id, ability)


def test_the_eighteen_classes_are_registered_once() -> None:
    names = {
        cls.APP_CLASS
        for cls in vars(ol).values()
        if isinstance(cls, type)
        and issubclass(cls, Ability)
        and cls.__module__ == ol.__name__
        and cls.APP_CLASS in PORTS
        and PORTS[cls.APP_CLASS] is cls
    }
    assert len(names) == 18
    assert AA + "LeaderDrawAbility" in names
    assert AA + "BaseSet.SchemeAbility" in names
    assert TA + "MasterstrokeAbility1" in names


def test_triggered_abilities_have_no_ai_member() -> None:
    for name, leader in (
        ("PrescienceAbility", "paul_atreides"),
        ("LandsraadPopularityAbility", "duke_leto_atreides"),
        ("ArrakisFiefdomAbility", "glossu_rabban"),
        ("MasterstrokeAbility2", "baron_vladimir_harkonnen"),
        ("RuthlessNegotiatorAbility", "count_ilban_richese"),
        ("ConnectionsAbility", "earl_memnon_thorvald"),
        ("SpiceAddictAbility1", "countess_ariana_thorvald"),
        ("SpiceAddictAbility2", "countess_ariana_thorvald"),
    ):
        ability = ab(leader, PORTS[TA + name])
        # Nothing overrides the ``WormAbilityDefinition`` defaults.
        assert type(ability).evaluate is Ability.evaluate
        assert type(ability).value_for_player is Ability.value_for_player


def test_signets_inherit_the_signet_base() -> None:
    signet = PORTS[AA + "SignetAbility"]
    for name in (
        "BrutalityAbility",
        "HiddenReservoirAbility",
        "ManipulateAbility",
        "ManufacturingAbility",
        "PrudentDiplomacyAbility",
        "SchemeAbility",
        "SpiceHoardAbility",
    ):
        assert issubclass(PORTS[AA + "BaseSet." + name], signet)
    assert issubclass(PORTS[AA + "LeaderDrawAbility"], DrawAbility)
    assert issubclass(
        PORTS[AA + "BaseSet.ConnectionsInfluenceAbility"],
        PORTS[AA + "DeferredAbility"],
    )


def test_one_resource_signets(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    for leader, cls, expected in (
        ("count_ilban_richese", ol.ManufacturingAbility, 0.25),
        ("earl_memnon_thorvald", ol.SpiceHoardAbility, 0.5),
        ("countess_ariana_thorvald", ol.HiddenReservoirAbility, 1.0),
    ):
        ability = ab(leader, cls)
        assert ability.value_for_player(p).sum == expected
        assert ability.always_run_immediately  # get_AlwaysRunImmediately: true


def test_brutality_counts_the_alliance(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("glossu_rabban", ol.BrutalityAbility)
    assert ability.value_for_player(
        prof(me(turn_state, alliance_faction_ids=()))
    ).sum == (pytest.approx(0.9))
    allied = me(turn_state, alliance_faction_ids=("emperor",))
    assert ability.value_for_player(prof(allied)).sum == pytest.approx(1.8)


def test_prudent_diplomacy(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    foe = (seat + 1) % 4
    ability = ab("duke_leto_atreides", ol.PrudentDiplomacyAbility)
    assert ability.selection_mode(prof(turn_state)) is SelectionMode.OPTIONAL
    # Cost: the Signet, a spice and a track an opponent leads.
    monkeypatch.setattr(leaders_module, "_has_signet_icon", lambda p: True)
    behind = with_player(
        me(turn_state, resources=Resources(spice=1)),
        foe,
        influence=Influence(emperor=2),
    )
    assert ability.meets_cost(prof(behind))
    assert not ability.meets_cost(prof(me(behind, resources=Resources(spice=0))))
    level = me(behind, influence=Influence(emperor=2))
    assert not ability.meets_cost(prof(level))  # nobody leads on any track
    monkeypatch.setattr(leaders_module, "_has_signet_icon", lambda p: False)
    assert not ability.meets_cost(prof(behind))
    # ValueForPlayer: spice needed; the space's own cost may leave none.
    assert (
        ability.value_for_player(prof(me(turn_state, resources=Resources(spice=0)))).sum
        == 0.0
    )
    spicy = me(turn_state, resources=Resources(spice=1))
    # G(None, +1) = 2.5 >= 2.4 (the Duke Leto threshold): influence - spice.
    assert ability.value_for_player(prof(spicy)).sum == pytest.approx(2.5 - 0.5)
    # Below it only the Early arc counts.
    low = {
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(2.39 * n)
    }
    assert ability.value_for_player(prof(spicy, **low)).sum == 0.0  # Mid arc
    early = prof(spicy, game_arc=lambda: 0, **low)
    assert ability.value_for_player(early).sum == pytest.approx(2.39 - 0.5)
    arrakeen = space_entity("arrakeen", BOARD)
    cannot = prof(spicy, can_agent_ability_be_played_with_space=lambda s, a, n: False)
    assert ability.value_for_player(cannot, (arrakeen,)).sum == 0.0
    seen: list[tuple[str, Attr, int]] = []

    def check(space: Any, attr: Attr, amount: int) -> bool:
        seen.append((space.ref, attr, amount))
        return True

    ability.value_for_player(
        prof(spicy, can_agent_ability_be_played_with_space=check), (arrakeen,)
    )
    assert seen == [("arrakeen", Attr.SPICE, 1)]
    # Evaluate: each track at G(track, +1) when >= 2.4 or in the Early arc.
    infos = tracks("emperor", "fremen")
    keen = prof(
        spicy,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {"fremen": 3.0}.get(f, 2.4) * n
        ),
    )
    answer = ability.evaluate(keen, Request((infos,)))
    assert (answer.value, answer.response) == (3.0, (("fremen",),))
    dull = ability.evaluate(prof(spicy, **low), Request((infos,)))
    assert (dull.value, dull.response) == (0.0, None)
    early_answer = ability.evaluate(early, Request((infos,)))
    assert (early_answer.value, early_answer.response) == (2.39, (("emperor",),))


def test_scheme(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    ability = ab("baron_vladimir_harkonnen", ol.SchemeAbility)
    assert ability.selection_mode(prof(turn_state)) is SelectionMode.OPTIONAL
    monkeypatch.setattr(leaders_module, "_has_signet_icon", lambda p: True)
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(solari=1))))
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(solari=0))))
    # ValueForPlayer: the Intrigue card, less a Solari; nothing without Solari.
    rich = me(turn_state, resources=Resources(solari=1))
    assert ability.value_for_player(prof(rich)).sum == pytest.approx(2.5 - 0.25)
    assert (
        ability.value_for_player(
            prof(me(turn_state, resources=Resources(solari=0)))
        ).sum
        == 0.0
    )

    # Evaluate: the owner's DeferValue (1) with an empty target array.
    def evaluate(state: GameState) -> tuple[float, Any]:
        answer = ability.evaluate(prof(state), Request())
        return answer.value, answer.response

    assert evaluate(rich) == (1.0, ((),))
    # Exactly 8 Solari and no Swordmaster: the Solari are kept.
    saving = me(turn_state, resources=Resources(solari=8))
    assert evaluate(saving) == (0.0, None)
    sword = me(
        saving,
        swordmaster_acquired=True,
        agents_available=saving.players[_seat(saving)].agents_available + 1,
    )
    assert evaluate(sword) == (1.0, ((),))
    assert evaluate(me(turn_state, resources=Resources(solari=9))) == (1.0, ((),))
    # More than two Intrigue cards: not played.
    held = me(rich, intrigue_cards=("intrigue:x:0", "intrigue:y:0", "intrigue:z:0"))
    assert evaluate(held) == (0.0, None)


def test_manipulate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("helena_richese", ol.ManipulateAbility)
    assert ability.selection_mode(prof(turn_state)) is SelectionMode.EXPLICIT
    # 1 Persuasion * 1.5 ("f64=1.5") and, with 2+ Agents, count * 1.5.
    assert ability.value_for_player(prof(me(turn_state, agents_available=2))).sum == (
        pytest.approx(0.8 * 1.5 + 2 * 1.5)
    )
    one = prof(me(turn_state, agents_available=1, agent_locations=("arrakeen",)))
    assert ability.value_for_player(one).sum == pytest.approx(0.8 * 1.5)
    # Evaluate: each Row card within PossiblePersuasion + 1 at its AcquireValue;
    # nothing positive stores the 0.5 fallback with an empty array.
    cheap = card_entity("imperium:thufir_hawat:0", 0)
    p = prof(turn_state, acquire_value=lambda c: Summer(3.5))
    answer = ability.evaluate(p, Request((TargetInfo((cheap,)),)))
    assert (answer.value, answer.response) == (3.5, ((cheap.ref,),))
    far = prof(
        turn_state,
        acquire_value=lambda c: Summer(3.5),
        possible_persuasion=lambda: cheap.int_attr("PersuasionCost") - 2,
    )
    answer = ability.evaluate(far, Request((TargetInfo((cheap,)),)))
    assert (answer.value, answer.response) == (0.5, ((),))
    nothing = prof(turn_state, acquire_value=lambda c: Summer(-1.0))
    answer = ability.evaluate(nothing, Request((TargetInfo((cheap,)),)))
    assert (answer.value, answer.response) == (0.5, ((),))


def test_connections_influence(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    ability = ab("earl_memnon_thorvald", ol.ConnectionsInfluenceAbility)
    assert ability.selection_mode(prof(turn_state)) is SelectionMode.EXPLICIT
    assert ability.contextually_deferred
    assert ability.meets_cost(prof(me(turn_state, high_council=True)))
    assert not ability.meets_cost(prof(turn_state))
    full = Influence(6, 6, 6, 6)
    assert not ability.meets_cost(
        prof(me(turn_state, high_council=True, influence=full))
    )
    # CanRunImmediately: the generic "not past the deferral threshold" test.
    monkeypatch.setattr(ol, "_runs_unless_threshold", lambda p: False)
    assert not ability.can_run_immediately(prof(turn_state))
    monkeypatch.undo()
    # Evaluate: G(track, +1) when above 0.0, else the literal 0.5.
    infos = Request((tracks("emperor", "fremen"),))
    answer = ability.evaluate(prof(turn_state), infos)
    assert (answer.value, answer.response) == (2.0, (("emperor",),))
    flat = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(0.0),
    )
    answer = ability.evaluate(flat, infos)
    assert (answer.value, answer.response) == (0.5, (("emperor",),))
    mixed = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {"fremen": -1.0}.get(f, 0.0)
        ),
    )
    answer = ability.evaluate(mixed, infos)
    assert (answer.value, answer.response) == (0.5, (("emperor",),))  # first stays


def test_masterstroke_picks_two_shuffled_factions(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("baron_vladimir_harkonnen", ol.MasterstrokeAbility1)
    request = Request((tracks("emperor", "spacing_guild", "bene_gesserit", "fremen"),))
    picks = set()
    for seed in range(8):
        p = prof(turn_state)
        p.rng.seed(seed)
        answer = ability.evaluate(p, request)
        assert answer.value == 1.0 and answer.response is not None
        (pair,) = answer.response
        assert len(pair) == 2 and len(set(pair)) == 2
        picks.add(pair)
    assert len(picks) > 1  # the order is the profile's shuffle
    # The shuffle consumes the profile's own RNG, like ListUtil.Shuffle.
    first = prof(turn_state)
    first.rng.seed(3)
    second = prof(turn_state)
    second.rng.seed(3)
    assert (
        ability.evaluate(first, request).response
        == ability.evaluate(second, request).response
    )


def test_leader_draw_is_the_draw_ability(turn_state: GameState) -> None:
    ability = ab("count_ilban_richese", ol.LeaderDrawAbility)
    assert isinstance(ability, DrawAbility)
    assert ability.timing == PORTS[AA + "DrawAbility"].timing
    assert ability.selection_mode(make_profile(turn_state)) is SelectionMode.EXPLICIT
