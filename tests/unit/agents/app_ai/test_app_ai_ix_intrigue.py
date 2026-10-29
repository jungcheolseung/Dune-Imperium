"""Rise of Ix's Intrigue ports (abilities/ix_intrigue.py, plan §13.4 slice 7).

Every test builds a real original + Rise of Ix ``GameState``
(``app_ai.testing``), adjusts the fields a hook reads and stubs the
``Profile`` prices other areas own with simple ones, so each branch, literal
and constant of the decompiled method is pinned by hand (the addresses are in
the port's docstrings).
"""

from collections.abc import Callable
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import (
    PORTS,
    Ability,
    Pile,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities import ix_intrigue as ix
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo, Timing
from dune_imperium.agents.app_ai.abilities.intrigue import (
    IntrigueAbility,
    StrengthIntrigueAbility,
    _Choice,
    ability_for_prompt,
)
from dune_imperium.agents.app_ai.catalog import (
    IX_INTRIGUE_ARCHETYPES,
    card_entity,
    intrigue_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
BOARD = Board.of(IX)
ENGINE = UprisingRulesEngine()
PA = "worm.canis.abilities.PlayAbilities.RiseOfIx."
EMPTY = ()  # "play it" with no sub-targets

#: A combat space and a Faction-less non-combat space of the Ix board.
COMBAT_SPACE = "arrakeen"
PLAIN_SPACE = "mentat"


def _stubs() -> dict[str, Callable[..., Any]]:
    return {
        "is_climax": lambda: False,
        "is_final_round": lambda: False,
        "game_arc": lambda: 1,
        "is_spice_short": lambda: False,
        "is_solari_short": lambda: False,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(2.0 * n),
        "solari_value": lambda n: 0.25 * n,
        "dreadnought_value": lambda n, include=False: 2.0 * n,
        "freighter_value": lambda: 4.2,
        "freighter_selections": lambda space=-1: (1, 0, "Level 3"),
        "current_combat_order": lambda: [0, 1, 2, 3],
        "estimated_conflict_rank": lambda bonus=0: 2,
        "units_to_deploy": lambda units, maximum: min(2, units),
        "units_to_deploy_split": lambda troops, dreads, maximum: (dreads, troops),
        "has_turn_before_opponent_next_round": lambda seat: False,
        "tech_tile_to_acquire": lambda discount, allow: None,
        "tech_tile_acquire_value": lambda tile: Summer(
            {"sonic_snoopers": 5.0}.get(tile.ref, 3.0)
        ),
        "card_to_trash": lambda targets, minimum: (
            (targets[0], 1.5) if targets else (None, minimum)
        ),
        "best_influence_exchange": lambda lose, gain, lf=None, gf=None: (
            "emperor",
            "fremen",
            2.0,
        ),
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """The first original + Ix ``turn`` decision (round 1, seat 0)."""

    return first_decision("turn", config=IX)


@pytest.fixture(scope="module")
def reveal_state() -> GameState:
    """The first original + Ix ``reveal`` decision."""

    return first_decision("reveal", config=IX)


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


_FREE_SPACES = ("imperial_basin", "the_great_flat", "carthag")


def pl(state: GameState, seat: int, **changes: Any) -> GameState:
    """``with_player`` that keeps the player's invariants.

    Troop changes are balanced in the supply (or the garrison when the
    supply is given), dreadnought changes in the supply; a Swordmaster adds
    its Agent; placed Agents and available ones are kept to the active
    count (fewer available ones are placed on free spaces).
    """

    player = state.players[seat]
    troop_keys = ("troops_supply", "troops_garrison", "troops_conflict")
    if any(k in changes for k in troop_keys):
        rest = (
            player.memories
            + player.specimens
            + player.troops_parked
            + player.negotiators
        )
        conflict = int(changes.get("troops_conflict", player.troops_conflict))
        if "troops_supply" in changes and "troops_garrison" not in changes:
            supply = int(changes["troops_supply"])
            changes["troops_garrison"] = 12 - supply - conflict - rest
        else:
            garrison = int(changes.get("troops_garrison", player.troops_garrison))
            changes["troops_supply"] = 12 - garrison - conflict - rest
    if "dreadnoughts_supply" not in changes and (
        "dreadnoughts_garrison" in changes or "dreadnoughts_conflict" in changes
    ):
        garrison = int(
            changes.get("dreadnoughts_garrison", player.dreadnoughts_garrison)
        )
        conflict = int(
            changes.get("dreadnoughts_conflict", player.dreadnoughts_conflict)
        )
        changes["dreadnoughts_supply"] = 2 - garrison - conflict
    active = player.agents_available + len(player.agent_locations)
    if changes.get("swordmaster_acquired") and not player.swordmaster_acquired:
        active += 1
        if "agents_available" not in changes and "agent_locations" not in changes:
            changes["agents_available"] = player.agents_available + 1
    if "agent_locations" in changes and "agents_available" not in changes:
        changes["agents_available"] = active - len(changes["agent_locations"])
    if "agents_available" in changes and "agent_locations" not in changes:
        needed = active - int(changes["agents_available"])
        locations = list(player.agent_locations)
        for space in _FREE_SPACES:
            if len(locations) < needed and space not in locations:
                locations.append(space)
        changes["agent_locations"] = tuple(locations[:needed])
    return with_player(state, seat, **changes)


def me(state: GameState, **changes: Any) -> GameState:
    return pl(state, _seat(state), **changes)


#: Three Tech tiles from the bottoms of the stacks (never face up here).
OWNED_TECH = ("memocorders", "flagship", "disposal_facility")


def with_tech(state: GameState, count: int, **changes: Any) -> GameState:
    """The deciding seat owning the first ``count`` of ``OWNED_TECH``, taken
    off the Ix board's stacks (a tile is in one zone only)."""

    owned = OWNED_TECH[:count]
    stacks = tuple(
        tuple(t for t in stack if t not in owned) for stack in state.tech_stacks
    )
    return me(with_state(state, tech_stacks=stacks), tech_ids=owned, **changes)


def card(name: str, seat: int = 0) -> Entity:
    return intrigue_entity(f"intrigue:{name}:0", seat)


def ab[A: Ability](name: str, cls: type[A]) -> A:
    for candidate in abilities_of(card(name)):
        if isinstance(candidate, cls):
            return candidate
    raise AssertionError(f"{name} has no {cls.__name__}")


def tracks(*factions: str) -> TargetInfo:
    return TargetInfo(tuple(track_entity(f) for f in factions))


def options(*values: int, max_select: int = 1) -> TargetInfo:
    return TargetInfo((), tuple(values), max_select=max_select)


def run(ability: Ability, p: Profile, *infos: TargetInfo) -> tuple[float, Any]:
    answer = ability.evaluate(p, Request(infos))
    return answer.value, answer.response


def at_space(monkeypatch: pytest.MonkeyPatch, space_id: str | None) -> None:
    """The Agent turn's space (``ActiveSpace``) the ports read."""

    space = None if space_id is None else space_entity(space_id, BOARD)
    monkeypatch.setattr(ix, "_active_space", lambda p: space)


def strength(monkeypatch: pytest.MonkeyPatch, ability: Ability, v: float) -> None:
    """``StrengthIntrigueAbility::Evaluate``'s value, as the wrappers read it."""

    choice = _Choice()
    choice.update_responses(v, ())
    monkeypatch.setattr(ability, "_strength_choice", lambda p: choice)


# ---------------------------------------------------------------------------
# Coverage, registration and timing
# ---------------------------------------------------------------------------

#: card id -> (port class, its app base port) for every ported ability.
PORTED: dict[str, list[tuple[type[Ability], type[Ability]]]] = {
    "advanced_weaponry": [
        (ix.AdvancedWeaponryPlotAbility, IntrigueAbility),
        (ix.AdvancedWeaponryCombatAbility, StrengthIntrigueAbility),
    ],
    "blackmail": [(ix.BlackmailAbility, StrengthIntrigueAbility)],
    "cannon_turrets": [(ix.CannonTurretsAbility, StrengthIntrigueAbility)],
    "cull": [(ix.CullAbility, IntrigueAbility)],
    "diversion": [(ix.DiversionAbility, IntrigueAbility)],
    "expedite": [(ix.ExpediteAbility, IntrigueAbility)],
    "finesse": [
        (ix.FinessePlotAbility, IntrigueAbility),
        (ix.FinesseCombatAbility, StrengthIntrigueAbility),
    ],
    "grand_conspiracy": [(ix.GrandConspiracyAbility, IntrigueAbility)],
    "machine_culture": [
        (ix.MachineCulturePlotAbility, IntrigueAbility),
        (ix.MachineCultureEndgameAbility, IntrigueAbility),
    ],
    "quid_pro_quo": [(ix.QuidProQuoAbility, IntrigueAbility)],
    "second_wave": [(ix.SecondWaveAbility, StrengthIntrigueAbility)],
    "secret_forces": [(ix.SecretForcesAbility, IntrigueAbility)],
    "strategic_push": [(ix.StrategicPushAbility, StrengthIntrigueAbility)],
    "strongarm": [(ix.StrongarmAbility, IntrigueAbility)],
    "war_chest": [
        (ix.WarChestCombatAbility, StrengthIntrigueAbility),
        (ix.WarChestEndgameAbility, IntrigueAbility),
    ],
    "glimpse_the_path": [(ix.GlimpseThePathAbility, IntrigueAbility)],
    "ixian_probe": [(ix.IxianProbeAbility, IntrigueAbility)],
}


#: Their ``Evaluate`` reads ``GetBestOption``, which the profile lacks.
def test_every_ix_intrigue_card_resolves_to_its_ports() -> None:
    assert len(IX_INTRIGUE_ARCHETYPES) == 17
    assert set(PORTED) == set(IX_INTRIGUE_ARCHETYPES)
    for card_id, expected in PORTED.items():
        found = abilities_of(card(card_id))
        assert [type(a) for a in found] == [cls for cls, _ in expected], card_id
        assert not any(isinstance(a, UnportedAbility) for a in found), card_id


@pytest.mark.parametrize(
    ("cls", "base"), [pair for pairs in PORTED.values() for pair in pairs]
)
def test_each_port_is_registered_under_its_app_class(
    cls: type[Ability], base: type[Ability]
) -> None:
    assert cls.APP_CLASS == PA + cls.__name__
    assert PORTS[cls.APP_CLASS] is cls
    assert issubclass(cls, base)
    # A PlayAbility, not a DeferredAbility: no SelectionMode to port.
    assert not hasattr(cls, "selection_mode")


def test_every_port_of_the_module_is_listed() -> None:
    ports = {
        cls
        for cls in vars(ix).values()
        if isinstance(cls, type)
        and issubclass(cls, Ability)
        and cls.__module__ == ix.__name__
        and PORTS.get(cls.APP_CLASS) is cls
    }
    assert ports == {cls for pairs in PORTED.values() for cls, _ in pairs}
    assert len(ports) == 21


#: The raw ``AbilityTiming`` of each port: 5 Combat (``StrengthIntrigueAbility``'s
#: ``.ctor``), 4 Endgame (``mov esi, 4`` in each ``.ctor``), 0 Plot.
TIMINGS: dict[type[IntrigueAbility], int] = {
    ix.AdvancedWeaponryCombatAbility: 5,
    ix.BlackmailAbility: 5,
    ix.CannonTurretsAbility: 5,
    ix.FinesseCombatAbility: 5,
    ix.SecondWaveAbility: 5,
    ix.StrategicPushAbility: 5,
    ix.WarChestCombatAbility: 5,
    ix.GrandConspiracyAbility: 4,
    ix.MachineCultureEndgameAbility: 4,
    ix.WarChestEndgameAbility: 4,
    ix.AdvancedWeaponryPlotAbility: 0,
    ix.CullAbility: 0,
    ix.DiversionAbility: 0,
    ix.ExpediteAbility: 0,
    ix.FinessePlotAbility: 0,
    ix.MachineCulturePlotAbility: 0,
    ix.QuidProQuoAbility: 0,
    ix.SecretForcesAbility: 0,
    ix.StrongarmAbility: 0,
    ix.GlimpseThePathAbility: 0,
    ix.IxianProbeAbility: 0,
}


def test_timings() -> None:
    assert set(TIMINGS) == {cls for pairs in PORTED.values() for cls, _ in pairs}
    for cls, timing in TIMINGS.items():
        assert cls.ability_timing == timing, cls
        assert (cls.timing is Timing.COMBAT) == (timing == 5), cls


@pytest.mark.parametrize(
    ("card_id", "combat", "plot"),
    [
        (
            "advanced_weaponry",
            ix.AdvancedWeaponryCombatAbility,
            ix.AdvancedWeaponryPlotAbility,
        ),
        ("finesse", ix.FinesseCombatAbility, ix.FinessePlotAbility),
        ("war_chest", ix.WarChestCombatAbility, ix.WarChestEndgameAbility),
        ("machine_culture", None, ix.MachineCulturePlotAbility),
    ],
)
def test_two_timing_cards_are_found_by_prompt(
    card_id: str, combat: type[Ability] | None, plot: type[Ability]
) -> None:
    entity = card(card_id)
    if combat is not None:
        assert isinstance(ability_for_prompt(entity, True), combat)
    assert isinstance(ability_for_prompt(entity, False), plot)


# ---------------------------------------------------------------------------
# Advanced Weaponry
# ---------------------------------------------------------------------------


def test_advanced_weaponry_plot_cost_and_flags(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("advanced_weaponry", ix.AdvancedWeaponryPlotAbility)
    rich = me(turn_state, resources=Resources(solari=3), dreadnoughts_supply=1)
    assert ability.meets_cost(prof(rich))
    assert not ability.meets_cost(
        prof(me(turn_state, resources=Resources(solari=2), dreadnoughts_supply=1))
    )
    assert not ability.meets_cost(
        prof(me(turn_state, resources=Resources(solari=3), dreadnoughts_supply=0))
    )
    # IsBadIntrigue: more than one Tech tile is never bad; else < 2 in Supply.
    assert not ability.is_bad_intrigue(
        prof(with_tech(turn_state, 2, dreadnoughts_supply=0))
    )
    one_tile = with_tech(turn_state, 1, dreadnoughts_supply=1)
    assert ability.is_bad_intrigue(prof(one_tile))
    assert not ability.is_bad_intrigue(prof(me(turn_state, dreadnoughts_supply=2)))
    # TroopValue: the next Supply dreadnought's Strength, else 0.
    assert ability.troop_value(prof(me(turn_state, dreadnoughts_supply=1))) == 3
    assert ability.troop_value(prof(me(turn_state, dreadnoughts_supply=0))) == 0


def test_advanced_weaponry_plot_evaluate(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ab("advanced_weaponry", ix.AdvancedWeaponryPlotAbility)
    # GetSolariValue(1) * 3.0 + 1.0 = 1.75 is the bar (jb: equal plays).
    at_space(monkeypatch, None)
    assert run(ability, prof(turn_state)) == (0.0, None)
    at_space(monkeypatch, PLAIN_SPACE)
    assert run(ability, prof(turn_state)) == (0.0, None)
    at_space(monkeypatch, COMBAT_SPACE)
    reach = prof(turn_state, dreadnought_value=lambda n, include=False: 1.75)
    assert run(ability, reach) == (1.0, EMPTY)
    short = prof(turn_state, dreadnought_value=lambda n, include=False: 1.7499)
    assert run(ability, short) == (0.0, None)


def test_advanced_weaponry_combat_needs_three_tech_tiles(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("advanced_weaponry", ix.AdvancedWeaponryCombatAbility)
    assert ability.meets_cost(prof(with_tech(turn_state, 3)))
    assert ability.strength_value(prof(with_tech(turn_state, 3))) == 4
    assert not ability.meets_cost(prof(with_tech(turn_state, 2)))
    assert ability.strength_value(prof(with_tech(turn_state, 2))) == 0
    assert ability.combat_value(prof(turn_state)) == 5.0


# ---------------------------------------------------------------------------
# The other Combat intrigues
# ---------------------------------------------------------------------------


def test_blackmail(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ab("blackmail", ix.BlackmailAbility)
    assert not ability.meets_cost(prof(me(turn_state, influence=Influence())))
    some = me(turn_state, influence=Influence(fremen=1))
    assert ability.meets_cost(prof(some))
    assert ability.strength_value(prof(some)) == 5
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    losses = {"emperor": -3.0, "fremen": -0.5, "bene_gesserit": -0.5}
    p = prof(
        some,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(losses[f]),
    )
    # A Strength value of 0 or less keeps the card.
    strength(monkeypatch, ability, 0.0)
    assert run(ability, p, tracks("emperor", "fremen")) == (0.0, None)
    strength(monkeypatch, ability, -1.0)
    assert run(ability, p, tracks("emperor", "fremen")) == (0.0, None)
    # Otherwise the cheapest loss, stored at the Strength value.
    strength(monkeypatch, ability, 7.0)
    assert run(ability, p, tracks("emperor", "fremen")) == (7.0, (("fremen",),))
    # Ties keep the first in shuffled order (ListUtil.Shuffle, p.rng).
    monkeypatch.setattr(p.rng, "shuffle", lambda items: items.reverse())
    tie = tracks("fremen", "bene_gesserit", "emperor")
    assert run(ability, p, tie) == (7.0, (("bene_gesserit",),))
    assert run(ability, p) == (0.0, None)


def test_cannon_turrets(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("cannon_turrets", ix.CannonTurretsAbility)
    assert ability.meets_cost(prof(turn_state))
    assert ability.combat_value(prof(turn_state)) == 4.0
    # Seat 0 first in the order: nobody ahead, All() holds -> Strength + 3.
    assert ability.strength_value(prof(turn_state)) == 5
    behind = {"current_combat_order": lambda: [1, 2, 0, 3]}
    assert ability.strength_value(prof(turn_state, **behind)) == 2
    state = pl(turn_state, 1, dreadnoughts_conflict=1)
    assert ability.strength_value(prof(state, **behind)) == 2  # seat 2 has none
    state = pl(state, 2, dreadnoughts_conflict=1)
    assert ability.strength_value(prof(state, **behind)) == 5
    # IsBadIntrigue: every opponent still holds both dreadnoughts.
    assert ability.is_bad_intrigue(prof(turn_state))
    out = pl(turn_state, 2, dreadnoughts_supply=1, dreadnoughts_garrison=1)
    assert not ability.is_bad_intrigue(prof(out))


def test_second_wave(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ab("second_wave", ix.SecondWaveAbility)
    assert ability.meets_cost(prof(turn_state))
    assert ability.combat_value(prof(turn_state)) == 7.0
    # Strength + 2 * Min(2, GarrisonTroops); no MeetsCost.
    for garrison, expected in ((0, 2), (1, 4), (2, 6), (5, 6)):
        state = me(turn_state, troops_garrison=garrison)
        assert ability.strength_value(prof(state)) == expected
    strength(monkeypatch, ability, 3.5)
    state = me(turn_state, troops_garrison=2, dreadnoughts_garrison=1)
    calls: list[tuple[int, int, int]] = []

    def split(troops: int, dreads: int, maximum: int) -> tuple[int, int]:
        calls.append((troops, dreads, maximum))
        return (1, 1)

    p = prof(state, units_to_deploy_split=split)
    assert run(ability, p) == (0.0, None)  # no target information
    # Units 0 (the dreadnought), 1 and 2 (troops); NumberToSelect 2.
    assert run(ability, p, options(0, 1, 2, max_select=2)) == (3.5, ((0, 1),))
    assert calls == [(2, 1, 2)]
    # Nothing to deploy still stores an empty list, and v is not tested.
    strength(monkeypatch, ability, 0.0)
    none = prof(state, units_to_deploy_split=lambda t, d, m: (0, 0))
    assert run(ability, none, options(0, 1, 2, max_select=2)) == (0.0, ((),))


def test_strategic_push_and_war_chest_combat(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    push = ab("strategic_push", ix.StrategicPushAbility)
    assert push.meets_cost(prof(turn_state))
    assert push.strength_value(prof(turn_state)) == 2
    assert push.combat_value(prof(turn_state)) == 0.5
    assert push.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2))
    assert not push.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    chest = ab("war_chest", ix.WarChestCombatAbility)
    assert chest.meets_cost(prof(me(turn_state, resources=Resources(solari=2))))
    assert not chest.meets_cost(prof(me(turn_state, resources=Resources(solari=1))))
    assert chest.strength_value(prof(me(turn_state, resources=Resources(solari=2))))
    finesse = ab("finesse", ix.FinesseCombatAbility)
    assert finesse.meets_cost(prof(turn_state))
    assert finesse.strength_value(prof(turn_state)) == 2


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def test_cull(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("cull", ix.CullAbility)
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(solari=1))))
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources())))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    seat = _seat(turn_state)
    dune = f"player:{seat}:starter:dune_the_desert_planet:0"  # TrashValue 1.0
    argument = f"player:{seat}:starter:convincing_argument:0"  # TrashValue 0.25
    player = turn_state.players[seat]
    # Every zone a test card may sit in starts without it: the engine allows
    # one zone per instance.
    zones = {
        zone: tuple(c for c in getattr(player, zone) if c not in (dune, argument))
        for zone in ("hand", "deck", "discard_pile", "in_play")
    }
    junk = me(
        turn_state, resources=Resources(solari=2), **{**zones, "discard_pile": (dune,)}
    )
    targets = TargetInfo((card_entity(dune, seat),))
    assert run(ability, prof(junk), targets) == (1.5, ((dune,),))
    # Only a card worth 1.0 or more in the discard pile or in play counts.
    weak = me(junk, discard_pile=(argument,))
    assert run(ability, prof(weak), targets) == (0.0, None)
    in_play = me(junk, discard_pile=(), in_play=(dune,))
    assert run(ability, prof(in_play), targets) == (1.5, ((dune,),))
    # Exactly 5 Solari, or exactly 8 without the Swordmaster, keeps it.
    for solari in (5, 8):
        held = me(junk, resources=Resources(solari=solari))
        assert run(ability, prof(held), targets) == (0.0, None)
    sword = me(junk, resources=Resources(solari=8), swordmaster_acquired=True)
    assert run(ability, prof(sword), targets) == (1.5, ((dune,),))
    # GetCardToTrash finds nothing.
    nothing = prof(junk, card_to_trash=lambda targets, minimum: (None, minimum))
    assert run(ability, nothing, targets) == (0.0, None)


def test_diversion(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("diversion", ix.DiversionAbility)
    assert ability.meets_cost(prof(me(turn_state, units_deployed_turn=4)))
    assert ability.meets_cost(prof(me(turn_state, units_deployed_peak=4)))
    assert not ability.meets_cost(prof(me(turn_state, units_deployed_turn=3)))
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    # Ungated: GetFreighterSelections' Item1 at FreighterValue.
    assert run(ability, prof(turn_state)) == (4.2, ((1,),))
    advance = prof(turn_state, freighter_selections=lambda space=-1: (0, 0, "L0"))
    assert run(ability, advance) == (4.2, ((0,),))


def test_expedite(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("expedite", ix.ExpediteAbility)
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(spice=1))))
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources())))
    late = {"game_arc": lambda: 2}
    assert ability.is_bad_intrigue(prof(me(turn_state, freighter_space=1), **late))
    assert not ability.is_bad_intrigue(prof(me(turn_state, freighter_space=2), **late))
    assert not ability.is_bad_intrigue(prof(me(turn_state, freighter_space=0)))
    # Only a recall (Item1 == 1) plays it, at FreighterValue.
    assert run(ability, prof(turn_state)) == (4.2, ((1,),))
    advance = prof(turn_state, freighter_selections=lambda space=-1: (0, 0, "L1"))
    assert run(ability, advance) == (0.0, None)


def test_finesse_plot(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("finesse", ix.FinessePlotAbility)
    assert not ability.meets_cost(prof(me(turn_state, influence=Influence())))
    assert ability.meets_cost(prof(me(turn_state, influence=Influence(emperor=1))))
    assert not ability.is_bad_intrigue(prof(turn_state))
    calls: list[tuple[Any, ...]] = []

    def exchange(lose: int, gain: int, lf: Any = None, gf: Any = None) -> Any:
        calls.append((lose, gain, lf, gf))
        return ("emperor", "fremen", 2.0)

    p = prof(turn_state, best_influence_exchange=exchange)
    lose = tracks("emperor", "spacing_guild")
    gain = tracks("emperor", "fremen")
    assert run(ability, p, lose, gain) == (2.0, (("emperor",), ("fremen",)))
    assert calls == [(-1, 1, ["emperor", "spacing_guild"], ["emperor", "fremen"])]
    # Both infos are needed; the winning tracks must be offered.
    assert run(ability, p, lose) == (0.0, None)
    assert run(ability, p, lose, tracks("emperor")) == (0.0, None)
    # The exchange must reach the literal 2.0.
    low = prof(
        turn_state,
        best_influence_exchange=lambda a, b, c=None, d=None: (
            "emperor",
            "fremen",
            1.99,
        ),
    )
    assert run(ability, low, lose, gain) == (0.0, None)


def test_machine_culture_plot(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("machine_culture", ix.MachineCulturePlotAbility)
    assert ability.meets_cost(prof(turn_state))
    late = {"game_arc": lambda: 2}
    assert ability.is_bad_intrigue(prof(with_tech(turn_state, 1), **late))
    assert not ability.is_bad_intrigue(prof(with_tech(turn_state, 2), **late))
    assert not ability.is_bad_intrigue(prof(turn_state))
    tiles = make_profile(turn_state).tech_face_up_tiles()
    offered = TargetInfo((*tiles, track_entity("emperor")))
    found = {"tech_tile_to_acquire": lambda discount, allow: tiles[0]}
    # 0 or 1 tile with a tile to acquire: each offered tile at its value.
    assert run(ability, prof(turn_state, **found), offered) == (
        5.0,
        (("sonic_snoopers",),),
    )
    # No tile to acquire with fewer than 2 tiles.
    assert run(ability, prof(turn_state), offered) == (0.0, None)
    # More than 2 tiles: never.
    three = with_tech(turn_state, 3)
    assert run(ability, prof(three, **found), offered) == (0.0, None)
    # Exactly 2: the Reveal turn of the final round, with a tile to acquire.
    final = {"is_final_round": lambda: True}
    turn_two = with_tech(turn_state, 2)
    assert run(ability, prof(turn_two, **found, **final), offered) == (0.0, None)
    reveal_two = with_tech(reveal_state, 2)
    assert run(ability, prof(reveal_two, **found), offered) == (0.0, None)
    assert run(ability, prof(reveal_two, **final), offered) == (0.0, None)
    assert run(ability, prof(reveal_two, **found, **final), offered) == (
        5.0,
        (("sonic_snoopers",),),
    )


def _agents_on(state: GameState, *spaces: str) -> GameState:
    return me(state, agent_locations=spaces)


def test_quid_pro_quo_cost_and_flags(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("quid_pro_quo", ix.QuidProQuoAbility)
    rich = me(turn_state, resources=Resources(spice=2))
    assert not ability.meets_cost(prof(rich))  # no Agent on a Faction space
    assert not ability.meets_cost(prof(_agents_on(rich, "mentat")))
    assert ability.meets_cost(prof(_agents_on(rich, "conspire")))
    poor = me(turn_state, resources=Resources(spice=1))
    assert not ability.meets_cost(prof(_agents_on(poor, "conspire")))
    # Board order, distinct, Factions only.
    both = _agents_on(rich, "secrets", "conspire")
    assert ix._agent_space_factions(prof(both)) == ["emperor", "bene_gesserit"]
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert not ability.is_bad_intrigue(prof(turn_state))
    assert ability.is_bad_intrigue(prof(turn_state, is_spice_short=lambda: True))


def test_quid_pro_quo_evaluate(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("quid_pro_quo", ix.QuidProQuoAbility)
    seat = _seat(turn_state)
    rival = (seat + 1) % 4
    one = _agents_on(turn_state, "conspire")
    # Nothing holds at a plain turn start.
    assert run(ability, prof(one)) == (0.0, None)
    # "Close Opponent": at 3+ with an opponent level who still has an Agent.
    close = me(one, influence=Influence(emperor=3))
    close = pl(close, rival, influence=Influence(emperor=3))
    assert run(ability, prof(close)) == (1.0, EMPTY)
    spent = pl(close, rival, agents_available=0)
    assert run(ability, prof(spent)) == (0.0, None)
    later = prof(spent, has_turn_before_opponent_next_round=lambda s: s == rival)
    assert run(ability, later) == (1.0, EMPTY)
    below = me(close, influence=Influence(emperor=2))
    below = pl(below, rival, influence=Influence(emperor=2))
    assert run(ability, prof(below)) == (0.0, None)
    # "Multiple Factions": the Reveal turn, more than one track to gain on.
    reveal_seat = _seat(reveal_state)
    two = pl(reveal_state, reveal_seat, agent_locations=("conspire", "secrets"))
    assert run(ability, prof(two)) == (1.0, EMPTY)
    capped = pl(two, reveal_seat, influence=Influence(bene_gesserit=6))
    assert run(ability, prof(capped)) == (0.0, None)
    # "Single Faction": the final round and G(F, +1) above 3.5.
    final = {"is_final_round": lambda: True}
    keen = {"gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(3.51)}
    assert run(ability, prof(one, **final, **keen)) == (1.0, EMPTY)
    flat = {"gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(3.5)}
    assert run(ability, prof(one, **final, **flat)) == (0.0, None)
    assert run(ability, prof(one, **keen)) == (0.0, None)


def test_secret_forces(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ab("secret_forces", ix.SecretForcesAbility)
    seated = me(turn_state, high_council=True)
    assert ability.meets_cost(prof(seated))
    assert not ability.meets_cost(prof(turn_state))
    assert ability.is_bad_intrigue(prof(turn_state))
    assert not ability.is_bad_intrigue(prof(seated))
    assert ability.troop_value(prof(seated)) == 4
    assert ability.troop_value(prof(turn_state)) == 0
    at_space(monkeypatch, COMBAT_SPACE)
    assert run(ability, prof(seated)) == (1.0, EMPTY)
    calls: list[tuple[int, int]] = []

    def deploy(units: int, maximum: int) -> int:
        calls.append((units, maximum))
        return 0

    assert run(ability, prof(seated, units_to_deploy=deploy)) == (0.0, None)
    assert calls == [(2, 2)]
    short = me(seated, troops_supply=1)
    assert run(ability, prof(short)) == (0.0, None)
    at_space(monkeypatch, PLAIN_SPACE)
    assert run(ability, prof(seated)) == (0.0, None)
    at_space(monkeypatch, None)
    assert run(ability, prof(seated)) == (0.0, None)


def test_strongarm(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ab("strongarm", ix.StrongarmAbility)
    both = me(turn_state, troops_garrison=2, troops_conflict=1)
    at_space(monkeypatch, "conspire")
    assert ability.meets_cost(prof(both))
    assert not ability.meets_cost(prof(me(both, troops_garrison=0, troops_conflict=0)))
    at_space(monkeypatch, PLAIN_SPACE)
    assert not ability.meets_cost(prof(both))
    assert run(ability, prof(both)) == (0.0, None)
    at_space(monkeypatch, None)
    assert not ability.meets_cost(prof(both))
    at_space(monkeypatch, "conspire")
    # G(F, +1) must reach the literal 3.5.
    keen = {"gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(3.5)}
    weak = {"gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(3.49)}
    assert run(ability, prof(both, **weak)) == (0.0, None)
    # Ranked: lose a garrison troop, unless the garrison is empty.
    assert run(ability, prof(both, **keen)) == (1.0, ((ix.STRONGARM_GARRISON,),))
    bare = me(both, troops_garrison=0)
    assert run(ability, prof(bare, **keen)) == (1.0, ((ix.STRONGARM_DEPLOYED,),))
    # Unranked: lose a deployed troop when there is one.
    unranked = {"estimated_conflict_rank": lambda bonus=0: None}
    assert run(ability, prof(both, **keen, **unranked)) == (
        1.0,
        ((ix.STRONGARM_DEPLOYED,),),
    )
    home = me(both, troops_conflict=0)
    assert run(ability, prof(home, **keen, **unranked)) == (
        1.0,
        ((ix.STRONGARM_GARRISON,),),
    )


# ---------------------------------------------------------------------------
# Endgame intrigues
# ---------------------------------------------------------------------------

_TSMF = "reserve:imperium_the_spice_must_flow:0"


def test_grand_conspiracy(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("grand_conspiracy", ix.GrandConspiracyAbility)
    assert ability.meets_cost(prof(turn_state))
    assert run(ability, prof(turn_state)) == (100.0, EMPTY)
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    late = {"game_arc": lambda: 2}
    # Late: bad with a Supply dreadnought, no seat and no Spice Must Flow.
    assert ability.is_bad_intrigue(prof(turn_state, **late))
    assert not ability.is_bad_intrigue(prof(me(turn_state, high_council=True), **late))
    assert not ability.is_bad_intrigue(
        prof(me(turn_state, dreadnoughts_supply=0), **late)
    )
    hand = (*turn_state.players[_seat(turn_state)].hand, _TSMF)
    assert not ability.is_bad_intrigue(prof(me(turn_state, hand=hand), **late))


def test_grand_conspiracy_value_in_pile_overrides_the_tag_synergy(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("grand_conspiracy", ix.GrandConspiracyAbility)
    p = prof(turn_state)
    tsmf = card_entity(_TSMF, 0)
    # The base hook would add "TSMF CardValue" for the WantTSMF tag.
    assert "WantTSMF" in ability.owner.list_attr("Tags")
    assert Ability.value_in_pile_for_other_play(ability, p, Pile.DECK, tsmf).sum > 0
    # The override multiplies an empty summer: its sum stays 0.
    assert ability.value_in_pile_for_other_play(p, Pile.DECK, tsmf).sum == 0.0
    other = card_entity(f"player:{_seat(turn_state)}:starter:dagger:0", 0)
    assert ability.value_in_pile_for_other_play(p, Pile.DECK, other).sum == 0.0
    assert ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, tsmf).sum == 0.0


def test_machine_culture_endgame(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("machine_culture", ix.MachineCultureEndgameAbility)
    assert not ability.meets_cost(prof(turn_state))
    for phase in (GamePhase.ENDGAME, GamePhase.FINISHED):
        assert ability.meets_cost(prof(with_state(turn_state, phase=phase)))
    assert not ability.is_bad_intrigue(prof(turn_state))
    assert run(ability, prof(turn_state)) == (100.0, EMPTY)
    tsmf = card_entity(_TSMF, 0)
    pile = ability.value_in_pile_for_other_play(prof(turn_state), Pile.DECK, tsmf)
    assert pile.sum == 0.0


def test_war_chest_endgame(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("war_chest", ix.WarChestEndgameAbility)
    assert ability.meets_cost(prof(turn_state))
    assert run(ability, prof(turn_state)) == (100.0, EMPTY)
    short = {"is_solari_short": lambda: True}
    assert ability.is_bad_intrigue(prof(turn_state, **short))
    assert not ability.is_bad_intrigue(prof(turn_state))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2, **short))
    tsmf = card_entity(_TSMF, 0)
    pile = ability.value_in_pile_for_other_play(prof(turn_state), Pile.DECK, tsmf)
    assert pile.sum == 0.0


def test_best_option_is_the_strict_maximum_over_hand_and_valid_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.agents.app_ai.abilities import original_intrigue as oi
    from dune_imperium.agents.app_ai.abilities.immortality import valid_space_ids

    p = make_profile(first_decision("turn", config=IX))
    hand = oi._hand_entities(p)
    assert hand
    monkeypatch.setattr(oi, "_agent_card_value", lambda p, card, space: 1.0)
    monkeypatch.setattr(
        oi,
        "_space_value",
        lambda p, space, with_: 2.0 if space.ref == "arrakeen" else 0.5,
    )
    card, space, value = oi.best_option(p)
    valid = valid_space_ids(p, card.ref, {}) if card is not None else frozenset()
    if "arrakeen" in valid:
        assert space is not None and space.ref == "arrakeen" and value == 3.0
    monkeypatch.setattr(oi, "_agent_card_value", lambda p, card, space: -5.0)
    assert oi.best_option(p) == (None, None, 0.0)


def test_ixian_probe_discards_the_first_two_of_the_discard_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make_profile(first_decision("turn", config=IX))
    cards = [Entity(Kind.CARD, f"c{i}", None, p.ctx.seat) for i in range(3)]
    monkeypatch.setattr(p, "is_climax", lambda: True)
    monkeypatch.setattr(p, "discard_value", lambda: 1.0)
    monkeypatch.setattr(p, "card_draw_value", lambda: 2.0)
    monkeypatch.setattr(p, "buy_gains", lambda n: 0.5)
    monkeypatch.setattr(p, "possible_persuasion_gain", lambda: 3)
    monkeypatch.setattr(p, "discard_order", lambda cs, sg: list(reversed(list(cs))))
    request = Request(infos=(TargetInfo(entities=tuple(cards)),))
    answer = ix.IxianProbeAbility(card("ixian_probe")).evaluate(p, request)
    assert answer.value == pytest.approx(2 * 1.0 + 2 * 2.0 + 2 * 0.5)
    assert answer.response == (("c2", "c1"),)


def test_strongarm_returns_on_a_nan_influence_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ucomisd G, 3.5; jb`` @0x4bfa5f3 takes NaN as the early return."""

    p = make_profile(first_decision("turn", config=IX))
    monkeypatch.setattr(
        ix, "_active_space", lambda p: space_entity("imperium_hagga_basin", p.ctx.board)
    )
    monkeypatch.setattr(ix, "_space_faction", lambda space: "fremen")
    high = Summer()
    high.add("high", 10.0)
    monkeypatch.setattr(p, "gain_influence_value", lambda *a, **k: high)
    played = ix.StrongarmAbility(card("strongarm")).evaluate(p, Request())
    assert played.response is not None  # the gate passes on a real value
    nan = Summer()
    nan.add("nan", float("nan"))
    monkeypatch.setattr(p, "gain_influence_value", lambda *a, **k: nan)
    answer = ix.StrongarmAbility(card("strongarm")).evaluate(p, Request())
    assert answer.response is None
