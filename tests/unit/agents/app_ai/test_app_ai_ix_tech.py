"""Ix Tech ports: spec/rix-tech.md §8 (Errata first), live terms §5.

Real original + Ix states; isolated profile prices pin each hook's branches,
thresholds and constants. These tests do not wire any decision windows.
"""

from collections.abc import Sequence
from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import testing as t
from dune_imperium.agents.app_ai.abilities import tech as at
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    UNPORTED,
    Ability,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.abilities.board import HighCouncilSpaceAbility
from dune_imperium.agents.app_ai.abilities.generic import (
    AgentAbility,
    ConflictAbility,
    DeferredAbility,
    RevealAbility,
    TriggeredAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    intrigue_entity,
    space_entity,
    tech_entity,
)
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
AA = "worm.canis.abilities.ActivatedAbilities."
TR = "worm.canis.abilities.TriggeredAbilities.RiseOfIx."
RIX = AA + "RiseOfIx."
CASES = (
    (TR + "ArtilleryAbility", "artillery", at.ArtilleryAbility, TriggeredAbility),
    (
        RIX + "DisposalFacilityAbility",
        "disposal_facility",
        at.DisposalFacilityAbility,
        DeferredAbility,
    ),
    (
        RIX + "DisposalFacilityTriggeredAbility",
        "disposal_facility",
        at.DisposalFacilityTriggeredAbility,
        TriggeredAbility,
    ),
    (RIX + "FlagshipAbility", "flagship", at.FlagshipAbility, DeferredAbility),
    (
        RIX + "HoloprojectorsAbility",
        "holoprojectors",
        at.HoloprojectorsAbility,
        DeferredAbility,
    ),
    (
        TR + "HoltzmanEngineAbility",
        "holtzman_engine",
        at.HoltzmanEngineAbility,
        TriggeredAbility,
    ),
    (
        RIX + "HoltzmanEngineEndgameAbility",
        "holtzman_engine",
        at.HoltzmanEngineEndgameAbility,
        DeferredAbility,
    ),
    (
        RIX + "InvasionShipsAbility",
        "invasion_ships",
        at.InvasionShipsAbility,
        DeferredAbility,
    ),
    (AA + "MemocordersAbility", "memocorders", at.MemocordersAbility, DeferredAbility),
    (
        TR + "RestrictedOrdnanceAbility",
        "restricted_ordnance",
        at.RestrictedOrdnanceAbility,
        TriggeredAbility,
    ),
    (
        TR + "ShuttleFleetAbility",
        "shuttle_fleet",
        at.ShuttleFleetAbility,
        TriggeredAbility,
    ),
    (
        RIX + "SonicSnoopersAbility",
        "sonic_snoopers",
        at.SonicSnoopersAbility,
        DeferredAbility,
    ),
    (
        RIX + "SpySatellitesAbility",
        "spy_satellites",
        at.SpySatellitesAbility,
        DeferredAbility,
    ),
    (
        AA + "SpySatellitesEndgameAbility",
        "spy_satellites",
        at.SpySatellitesEndgameAbility,
        DeferredAbility,
    ),
    (
        RIX + "TrainingDronesAbility",
        "training_drones",
        at.TrainingDronesAbility,
        DeferredAbility,
    ),
    (
        RIX + "TroopTransportsAbility",
        "troop_transports",
        at.TroopTransportsAbility,
        DeferredAbility,
    ),
    (
        "worm.canis.abilities.ConflictAbilities.RiseOfIx.WindtrapsAbility",
        "windtraps",
        at.WindtrapsAbility,
        ConflictAbility,
    ),
)


@cache
def state() -> GameState:
    return t.play_until(
        lambda s, owner: s.decision_stack[-1].kind == "turn", config=CONFIG
    )


def seat(s: GameState) -> int:
    decision = t.ENGINE.current_decision(s)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def make(*, held: str = "", turn: str = "turn", **changes: object) -> Profile:
    s = state()
    owner = seat(s)
    me = s.players[owner]
    if "troops_supply" in changes:
        changes["troops_garrison"] = (
            12
            - int(str(changes["troops_supply"]))
            - me.troops_conflict
            - me.memories
            - me.specimens
            - me.troops_parked
        )
    if changes.get("swordmaster_acquired"):
        changes["agents_available"] = me.agents_available + 1
    if changes.get("agents_available") == 0:
        changes["agent_locations"] = ("imperial_basin", "hagga_basin")
    changes["tech_ids"] = (held,) if held else ()
    if held:
        s = t.with_state(
            s,
            tech_stacks=tuple(
                tuple(tile for tile in stack if tile != held) for stack in s.tech_stacks
            ),
        )
    s = t.with_player(s, owner, **changes)
    # Only turn classification is relevant to these hooks; preserve a real
    # turn frame/decision and all player invariants.
    frame = replace(s.decision_stack[-1], kind=turn)
    s = t.with_state(s, decision_stack=(*s.decision_stack[:-1], frame))
    return t.make_profile(s, owner)


def req(*entities: Entity, maximum: int = 1) -> Request:
    return Request((TargetInfo(entities=entities, max_select=maximum),))


def synthetic(ref: str, **attrs: object) -> Entity:
    return Entity(
        Kind.CARD,
        ref,
        Archetype("Test." + ref, "card", ref, False, False, attrs),
    )


@pytest.mark.parametrize("name,tile,cls,base", CASES)
def test_registration_and_default_value(
    name: str, tile: str, cls: type[Ability], base: type[Ability]
) -> None:
    p = make(held=tile)
    before = UNPORTED.copy()
    ability = ability_for(name, tech_entity(tile, p.ctx.seat))
    assert PORTS[name] is cls
    assert type(ability) is cls and isinstance(ability, base)
    assert any(type(a) is cls for a in abilities_of(ability.owner))
    assert ability.value_for_player(p).sum == 0.0
    if "specific_acquire_value" not in cls.__dict__:
        assert ability.specific_acquire_value(p).sum == 0.0
    assert UNPORTED == before
    if isinstance(ability, DeferredAbility):
        explicit = cls in (
            at.HoltzmanEngineEndgameAbility,
            at.MemocordersAbility,
            at.SpySatellitesEndgameAbility,
        )
        assert ability.selection_mode(p) is (
            SelectionMode.EXPLICIT if explicit else SelectionMode.OPTIONAL
        )
        assert ability.always_run_immediately is explicit
        if explicit:
            assert ability.timing is Timing.ENDGAME
    else:
        assert ability.evaluate(p, Request()).response is None
    if isinstance(ability, at.TroopTransportsAbility):
        assert ability.is_unexhausted


def test_disposal_trashes_only_a_selected_card(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    card = card_entity(p.ctx.hand[0])
    ability = at.DisposalFacilityAbility(tech_entity("disposal_facility"))
    seen: list[tuple[Sequence[Entity], float]] = []

    def trash(cards: Sequence[Entity], minimum: float) -> tuple[Entity | None, float]:
        seen.append((cards, minimum))
        return card, 37.0

    monkeypatch.setattr(p, "card_to_trash", trash)
    answer = ability.evaluate(p, req(card, tech_entity("flagship")))
    assert (answer.value, answer.response) == (37.0, ((card.ref,),))
    assert seen == [([card], 1.0)]
    monkeypatch.setattr(p, "card_to_trash", lambda cards, minimum: (None, minimum))
    answer = ability.evaluate(p, req(card))
    assert (answer.value, answer.response) == (0.0, None)


@pytest.mark.parametrize(
    "cls,needed", [(at.FlagshipAbility, 2), (at.TrainingDronesAbility, 1)]
)
@pytest.mark.parametrize("supply", [0, 1, 2])
@pytest.mark.parametrize("combat,deploy", [(False, 0), (True, 0), (True, 1)])
def test_combat_activation_requires_supply_and_deployment(
    monkeypatch: pytest.MonkeyPatch,
    cls: type[DeferredAbility],
    needed: int,
    supply: int,
    combat: bool,
    deploy: int,
) -> None:
    p = make(troops_supply=supply)
    monkeypatch.setattr(at, "_active_combat_space", lambda p: combat)
    calls: list[tuple[int, int]] = []

    def units(count: int, maximum: int) -> int:
        calls.append((count, maximum))
        return deploy

    monkeypatch.setattr(p, "units_to_deploy", units)
    answer = cls(tech_entity("flagship")).evaluate(p, Request())
    expected = supply >= needed and combat and deploy > 0
    assert (answer.value, answer.response) == ((100.0, ()) if expected else (0.0, None))
    assert calls == ([(needed, -1)] if supply >= needed and combat else [])


@pytest.mark.parametrize("solari", [5, 6, 7])
@pytest.mark.parametrize("turn", ["turn", "reveal"])
def test_flagship_reveal_six_solari_gate(solari: int, turn: str) -> None:
    p = make(resources=Resources(solari=solari), turn=turn)
    a = at.FlagshipAbility(tech_entity("flagship")).evaluate(p, Request())
    assert a.value == (100.0 if solari >= 6 and turn == "reveal" else 0.0)


@pytest.mark.parametrize("turn", ["turn", "reveal"])
def test_training_drones_reveal_has_no_solari_gate(turn: str) -> None:
    p = make(resources=Resources(solari=0), turn=turn)
    a = at.TrainingDronesAbility(tech_entity("training_drones")).evaluate(p, Request())
    assert a.value == (100.0 if turn == "reveal" else 0.0)


def test_active_combat_space_reads_own_agent_frame() -> None:
    p = make()
    assert not at._active_combat_space(p)
    for space, expected in [("imperial_basin", True), ("conspire", False)]:
        frame = DecisionFrame(
            "agent_effects",
            "test-agent",
            PlayerDecision(p.ctx.seat, "test"),
            context=(("space_id", space),),
        )
        s = t.with_state(p.ctx.state, decision_stack=(frame,))
        assert at._active_combat_space(t.make_profile(s, p.ctx.seat)) is expected


@pytest.mark.parametrize("buy", [5.9, 6.0, 6.1])
@pytest.mark.parametrize("turn", ["turn", "reveal"])
def test_holoprojectors_turn_and_buy_gate(
    monkeypatch: pytest.MonkeyPatch, buy: float, turn: str
) -> None:
    p = make(
        turn=turn, deck=("imperium:the_spice_must_flow:0",), hand=("imperium:dagger:0",)
    )
    card = card_entity(p.ctx.hand[0])
    monkeypatch.setattr(p, "buy_value", lambda: buy)
    monkeypatch.setattr(
        at, "_first_reveal_value", lambda p, c: 4.0 if c.ref in p.ctx.me.deck else 1.0
    )
    monkeypatch.setattr(p, "discard_order", lambda cards, force: [card])
    a = at.HoloprojectorsAbility(tech_entity("holoprojectors")).evaluate(p, req(card))
    assert (a.value, a.response) == (
        (100.0, ((card.ref,),)) if turn == "turn" and buy <= 6.0 else (0.0, None)
    )


@pytest.mark.parametrize(
    "deck,discard,hand_value,targets,expected",
    [
        (("imperium:the_spice_must_flow:0",), ("imperium:dagger:1",), 2.0, True, 100.0),
        ((), ("imperium:the_spice_must_flow:0",), 2.0, True, 100.0),
        ((), (), 0.0, True, 0.0),
        (("imperium:the_spice_must_flow:0",), (), 4.0, True, 0.0),
        (("imperium:the_spice_must_flow:0",), (), 2.0, False, 0.0),
    ],
)
def test_holoprojectors_average_and_strict_comparison(
    monkeypatch: pytest.MonkeyPatch,
    deck: tuple[str, ...],
    discard: tuple[str, ...],
    hand_value: float,
    targets: bool,
    expected: float,
) -> None:
    p = make(deck=deck, discard_pile=discard, hand=("imperium:dagger:0",))
    card = card_entity(p.ctx.hand[0])
    monkeypatch.setattr(p, "buy_value", lambda: 0.0)

    def reveal_value(p: Profile, c: Entity) -> float:
        if c.ref == card.ref:
            return hand_value
        return 4.0 if "the_spice" in c.ref else -4.0

    monkeypatch.setattr(at, "_first_reveal_value", reveal_value)
    monkeypatch.setattr(
        p, "discard_order", lambda cards, force: [card] if cards else []
    )
    a = at.HoloprojectorsAbility(tech_entity("holoprojectors")).evaluate(
        p, req(card) if targets else Request()
    )
    assert a.value == expected


def test_holoprojectors_reveal_default_and_first_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    card = synthetic("no-reveal")
    assert at._first_reveal_value(p, card) == 0.0
    first, second = RevealAbility(card), RevealAbility(card)
    monkeypatch.setattr(at, "abilities_of", lambda c: (Ability(c), first, second))
    monkeypatch.setattr(first, "value_for_player", lambda p, companions: Summer(2.25))
    monkeypatch.setattr(
        second, "value_for_player", lambda *args: pytest.fail("second Reveal read")
    )
    assert at._first_reveal_value(p, card) == 2.25


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_holtzman_endgame_two_tsmf(n: int) -> None:
    p = make(hand=tuple(f"imperium:the_spice_must_flow:{i}" for i in range(n)))
    a = at.HoltzmanEngineEndgameAbility(tech_entity("holtzman_engine"))
    assert a.is_endgame_playable(p) is (n >= 2)
    answer = a.evaluate(p, Request())
    assert (answer.value, answer.response) == (0.0, None)


@pytest.mark.parametrize(
    "ranks", [(3, 3, 3, 3), (2, 3, 3, 3), (3, 3, 3, 2), (4, 5, 6, 3)]
)
def test_memocorders_endgame_all_four(ranks: tuple[int, ...]) -> None:
    p = make(influence=Influence(*ranks))
    a = at.MemocordersAbility(tech_entity("memocorders"))
    assert a.is_endgame_playable(p) is all(n >= 3 for n in ranks)
    answer = a.evaluate(p, Request())
    assert (answer.value, answer.response) == (100.0, ())


@pytest.mark.parametrize(
    "ranks", [(2, 2, 2, 2), (1, 2, 2, 2), (2, 2, 2, 1), (0, 0, 0, 0)]
)
def test_spy_satellites_endgame_errata_any_low_faction(ranks: tuple[int, ...]) -> None:
    p = make(influence=Influence(*ranks))
    a = at.SpySatellitesEndgameAbility(tech_entity("spy_satellites"))
    assert a.is_endgame_playable(p) is any(n < 2 for n in ranks)
    answer = a.evaluate(p, Request())
    assert (answer.value, answer.response) == (0.0, None)


@pytest.mark.parametrize(
    "bad_count,climax,engineer,expected",
    [
        (0, False, False, 0.0),
        (0, True, False, 0.0),
        (1, False, False, 0.0),
        (1, True, False, 1.0),
        (2, False, False, 1.0),
        (2, True, True, 0.0),
    ],
)
def test_sonic_snoopers_bad_intrigue_threshold(
    monkeypatch: pytest.MonkeyPatch,
    bad_count: int,
    climax: bool,
    engineer: bool,
    expected: float,
) -> None:
    p = make(hand=())
    monkeypatch.setattr(
        p,
        "_all_imperium_cards",
        lambda: [card_entity("imperium:ixian_engineer:0")] if engineer else [],
    )
    cards = [intrigue_entity(f"intrigue:ambush:{i}") for i in range(bad_count)]
    monkeypatch.setattr(p, "bad_intrigue_cards_in_hand", lambda: cards)
    monkeypatch.setattr(p, "is_climax", lambda: climax)
    a = at.SonicSnoopersAbility(tech_entity("sonic_snoopers")).evaluate(p, Request())
    assert a.value == expected
    assert a.response == ((tuple(c.ref for c in cards),) if expected else None)


@pytest.mark.parametrize(
    "low,climax,turn,engineer,final,expected",
    [
        (False, True, "reveal", False, False, 100.0),
        (True, True, "reveal", False, False, 0.0),
        (False, False, "reveal", False, False, 0.0),
        (False, True, "turn", False, False, 0.0),
        (False, True, "reveal", True, False, 0.0),
        (False, True, "reveal", True, True, 100.0),
    ],
)
def test_spy_satellites_activation_all_gates(
    monkeypatch: pytest.MonkeyPatch,
    low: bool,
    climax: bool,
    turn: str,
    engineer: bool,
    final: bool,
    expected: float,
) -> None:
    p = make(turn=turn, influence=Influence(1 if low else 2, 2, 2, 2), hand=())
    monkeypatch.setattr(
        p,
        "_all_imperium_cards",
        lambda: [card_entity("imperium:ixian_engineer:0")] if engineer else [],
    )
    monkeypatch.setattr(p, "is_climax", lambda: climax)
    monkeypatch.setattr(p, "is_final_round", lambda: final)
    a = at.SpySatellitesAbility(tech_entity("spy_satellites")).evaluate(p, Request())
    assert (a.value, a.response) == ((100.0, ()) if expected else (0.0, None))


@pytest.mark.parametrize("count,maximum,deploy", [(3, 2, 2), (3, 1, 0), (0, 2, 0)])
def test_troop_transports_first_info_limit_and_order(
    monkeypatch: pytest.MonkeyPatch, count: int, maximum: int, deploy: int
) -> None:
    p = make()
    units = tuple(synthetic(f"unit{i}") for i in range(count))
    calls: list[tuple[int, int]] = []

    def select(n: int, cap: int) -> int:
        calls.append((n, cap))
        return deploy

    monkeypatch.setattr(p, "units_to_deploy", select)
    ability = at.TroopTransportsAbility(tech_entity("troop_transports"))
    a = ability.evaluate(p, req(*units, maximum=maximum))
    assert calls == [(count, maximum)]
    assert (a.value, a.response) == (
        (0.5, (tuple(u.ref for u in units[:deploy]),)) if deploy else (0.0, None)
    )
    assert ability.evaluate(p, Request()).response is None


@pytest.fixture
def factors(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Observe multiplication factors, including the app's zero-valued SAVs."""
    seen: list[float] = []
    original = Summer.multiply

    def multiply(s: Summer, reason: str, factor: float) -> Summer:
        seen.append(factor)
        return original(s, reason, factor)

    monkeypatch.setattr(Summer, "multiply", multiply)
    return seen


@pytest.mark.parametrize("pile", [Pile.DECK, Pile.PLAY_AREA])
@pytest.mark.parametrize("strength", [0, 1])
def test_artillery_vip_and_sav_constants(
    monkeypatch: pytest.MonkeyPatch,
    factors: list[float],
    pile: Pile,
    strength: int,
) -> None:
    p = make()
    a = at.ArtilleryAbility(tech_entity("artillery"))
    card = synthetic("sword", Strength=strength)
    assert a.value_in_pile_for_other_play(p, pile, card).sum == 0.0
    assert factors == ([1.2] if pile is Pile.DECK and strength else [])
    factors.clear()
    monkeypatch.setattr(
        p,
        "_all_imperium_cards",
        lambda: [
            synthetic("a", Strength=1),
            synthetic("b", Strength=2),
            synthetic("c", Strength=0),
        ],
    )
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == [1.1**2]


@pytest.mark.parametrize(
    "cls,tile",
    [
        (at.HoloprojectorsAbility, "holoprojectors"),
        (at.InvasionShipsAbility, "invasion_ships"),
    ],
)
@pytest.mark.parametrize("pile", [Pile.DECK, Pile.PLAY_AREA])
@pytest.mark.parametrize("tagged", [False, True])
def test_discard_tile_zero_modifiers(
    monkeypatch: pytest.MonkeyPatch,
    factors: list[float],
    cls: type[Ability],
    tile: str,
    pile: Pile,
    tagged: bool,
) -> None:
    p = make()
    a = cls(tech_entity(tile))
    card = synthetic("discard", Tags=("IncentiveDiscard",) if tagged else ())
    assert a.value_in_pile_for_other_play(p, pile, card).sum == 0.0
    assert factors == ([1.2] if pile is Pile.DECK and tagged else [])
    factors.clear()
    monkeypatch.setattr(
        p,
        "_all_imperium_cards",
        lambda: [
            synthetic("a", Tags=("IncentiveDiscard",)),
            synthetic("b", Tags=("IncentiveDiscard",)),
            synthetic("c", IconList=("Emperor",)),
        ],
    )
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == [1.2**2]


@pytest.mark.parametrize(
    "short,persuasion,expected",
    [
        ("ImperiumArchetypes.BaseSet.TheSpiceMustFlow", 0, [1.33]),
        ("ImperiumArchetypes.BaseSet.LietKynes", 0, [1.25]),
        ("Test.Card", 2, [1.25]),
        ("Test.Card", 0, [0.75]),
        ("Test.Card", 1, []),
    ],
)
@pytest.mark.parametrize("pile", [Pile.DECK, Pile.PLAY_AREA])
def test_holtzman_vip_branches(
    factors: list[float],
    short: str,
    persuasion: int,
    expected: list[float],
    pile: Pile,
) -> None:
    p = make()
    a = at.HoltzmanEngineAbility(tech_entity("holtzman_engine"))
    card = synthetic("persuasion", Persuasion=persuasion)
    assert card.archetype is not None
    card = replace(card, archetype=replace(card.archetype, short=short))
    assert a.value_in_pile_for_other_play(p, pile, card).sum == 0.0
    assert factors == (expected if pile is Pile.DECK else [])


@pytest.mark.parametrize("n,expected", [(0, 0.0), (1, 1.5), (2, 3.0), (3, 3.0)])
def test_holtzman_sav_multiplies_not_pow(
    factors: list[float],
    n: int,
    expected: float,
) -> None:
    p = make(
        hand=tuple(f"imperium:the_spice_must_flow:{i}" for i in range(n)),
        deck=(),
        discard_pile=(),
        in_play=(),
    )
    a = at.HoltzmanEngineAbility(tech_entity("holtzman_engine"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == [expected]


@pytest.mark.parametrize(
    "final,sword,council,solari,expected",
    [
        (True, False, False, 0, [1.25]),
        (False, False, True, 7, []),
        (False, True, False, 7, [1.25]),
        (False, True, False, 6, []),
        (False, True, True, 5, [1.25]),
        (False, True, True, 4, []),
    ],
)
def test_flagship_sav_gates(
    monkeypatch: pytest.MonkeyPatch,
    factors: list[float],
    final: bool,
    sword: bool,
    council: bool,
    solari: int,
    expected: list[float],
) -> None:
    p = make(
        swordmaster_acquired=sword,
        high_council=council,
        resources=Resources(solari=solari),
    )
    monkeypatch.setattr(p, "is_final_round", lambda: final)
    a = at.FlagshipAbility(tech_entity("flagship"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == expected


@pytest.mark.parametrize(
    "gain,final,expected",
    [
        (2.99, True, []),
        (3.0, False, []),
        (3.0, True, [1.33]),
        (3.749, False, []),
        (3.75, False, [1.33]),
    ],
)
def test_memocorders_sav_rank_and_conditional_constants(
    monkeypatch: pytest.MonkeyPatch,
    factors: list[float],
    gain: float,
    final: bool,
    expected: list[float],
) -> None:
    p = make(influence=Influence(1, 2, 3, 4))
    monkeypatch.setattr(p, "is_final_round", lambda: final)
    monkeypatch.setattr(at, "gain_any_influence_value", lambda p, n: Summer(gain))
    a = at.MemocordersAbility(tech_entity("memocorders"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == [1.1, 1.25, 1.25, *expected]


@pytest.mark.parametrize("council", [False, True])
def test_restricted_ordnance_sav_high_council(
    factors: list[float],
    council: bool,
) -> None:
    p = make(high_council=council)
    a = at.RestrictedOrdnanceAbility(tech_entity("restricted_ordnance"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == ([1.33] if council else [])


@pytest.mark.parametrize("rank", [1, 2, 3])
def test_troop_transports_sav_guild_threshold(factors: list[float], rank: int) -> None:
    p = make(influence=Influence(spacing_guild=rank))
    a = at.TroopTransportsAbility(tech_entity("troop_transports"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == ([1.5] if rank >= 2 else [])


@pytest.mark.parametrize("arc,mod", [(0, 1.1), (1, 1.25), (2, 1.5)])
@pytest.mark.parametrize("final", [False, True])
@pytest.mark.parametrize("spice", [6, 7, 8])
def test_spy_satellites_sav_per_low_faction(
    monkeypatch: pytest.MonkeyPatch,
    factors: list[float],
    arc: int,
    mod: float,
    final: bool,
    spice: int,
) -> None:
    # §8.13 UNTRACED SAV body: cmp eax,7; jl @0x4de617f-0x4de6182.
    p = make(influence=Influence(0, 1, 2, 3), resources=Resources(spice=spice))
    monkeypatch.setattr(p, "game_arc", lambda: arc)
    monkeypatch.setattr(p, "is_final_round", lambda: final)
    a = at.SpySatellitesAbility(tech_entity("spy_satellites"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == [mod, mod, *([1.25] if final and spice >= 7 else [])]


def test_sonic_snoopers_sav_good_and_bad(
    monkeypatch: pytest.MonkeyPatch,
    factors: list[float],
) -> None:
    from dune_imperium.agents.app_ai.abilities.intrigue import IntrigueAbility

    p = make(intrigue_cards=("intrigue:ambush:0", "intrigue:ambush:1"))
    monkeypatch.setattr(
        IntrigueAbility, "is_bad_intrigue", lambda a, p: a.owner.ref.endswith(":0")
    )
    a = at.SonicSnoopersAbility(tech_entity("sonic_snoopers"))
    assert a.specific_acquire_value(p).sum == 0.0
    assert factors == [1.25, 1.1]


@pytest.mark.parametrize("gate", ["none", "no-target", "no-agent", "reveal", "kwisatz"])
def test_invasion_ships_gates_and_value(
    monkeypatch: pytest.MonkeyPatch,
    gate: str,
) -> None:
    from dune_imperium.agents.app_ai.abilities import immortality as im
    from dune_imperium.agents.app_ai.abilities import original_intrigue as oi

    hand: tuple[str, ...] = ("imperium:dagger:0",)
    if gate == "kwisatz":
        hand += ("imperium:kwisatz_haderach:0",)
    p = make(
        hand=hand,
        agents_available=0 if gate == "no-agent" else 2,
        turn="reveal" if gate == "reveal" else "turn",
    )
    card = card_entity(hand[0])
    space = space_entity("mentat", p.ctx.board)
    monkeypatch.setattr(oi, "_board_spaces", lambda p: [space])
    monkeypatch.setattr(oi, "_can_pay_space", lambda p, s: True)
    monkeypatch.setattr(
        type(p.ctx), "space_occupants", lambda ctx, sid: ((p.ctx.seat + 1) % 4,)
    )
    monkeypatch.setattr(im, "valid_space_ids", lambda p, ref, cache: frozenset())
    monkeypatch.setattr(
        p, "discard_order", lambda cards, force: [card] if cards else []
    )
    monkeypatch.setattr(p, "discard_value", lambda: -1.0)
    agent = AgentAbility(card)
    seen: list[Sequence[Entity]] = []

    def value(p: Profile, companions: Sequence[Entity]) -> Summer:
        seen.append(companions)
        return Summer(5.0)

    monkeypatch.setattr(agent, "value_for_player", value)
    monkeypatch.setattr(at, "abilities_of", lambda c: (agent,))
    monkeypatch.setattr(oi, "_space_value", lambda p, s, companions: 8.0)
    a = at.InvasionShipsAbility(tech_entity("invasion_ships")).evaluate(
        p, Request() if gate == "no-target" else req(card)
    )
    if gate == "none":
        assert (a.value, a.response) == (11.9, ((card.ref,),))
        assert seen == [()]
    else:
        assert (a.value, a.response) == (0.0, None)
        assert not seen


@pytest.mark.parametrize("rejected", ["valid", "empty", "own", "icon", "cost"])
def test_invasion_ships_exact_space_filter(
    monkeypatch: pytest.MonkeyPatch,
    rejected: str,
) -> None:
    from dune_imperium.agents.app_ai.abilities import immortality as im
    from dune_imperium.agents.app_ai.abilities import original_intrigue as oi

    p = make(hand=("imperium:dagger:0",))
    card = card_entity(p.ctx.hand[0])
    space = space_entity("conspire" if rejected == "icon" else "mentat", p.ctx.board)
    monkeypatch.setattr(oi, "_board_spaces", lambda p: [space])
    monkeypatch.setattr(oi, "_can_pay_space", lambda p, s: rejected != "cost")
    occupants = (
        ()
        if rejected == "empty"
        else ((p.ctx.seat,) if rejected == "own" else ((p.ctx.seat + 1) % 4,))
    )
    monkeypatch.setattr(type(p.ctx), "space_occupants", lambda ctx, sid: occupants)
    monkeypatch.setattr(
        im,
        "valid_space_ids",
        lambda p, ref, cache: (
            frozenset((space.ref,)) if rejected == "valid" else frozenset()
        ),
    )
    monkeypatch.setattr(p, "discard_order", lambda cards, force: [card])
    a = at.InvasionShipsAbility(tech_entity("invasion_ships")).evaluate(p, req(card))
    assert (a.value, a.response) == (0.0, None)


@pytest.mark.parametrize(
    "tile,attr,mod",
    [
        ("shuttle_fleet", Attr.SOLARI, 0.66),
        ("flagship", Attr.SOLARI, 1.5),
        ("training_drones", Attr.TROOPS, 0.9),
        ("flagship", Attr.TROOPS, 0.9),  # slot 304, NOT FlagshipTroopMod 0.75
        ("spy_satellites", Attr.SPICE, 1.1),
        ("detonation_devices", Attr.DREADNOUGHT, 1.5),
    ],
)
@pytest.mark.parametrize("held", [False, True])
def test_resource_tile_terms_require_holdings(
    tile: str,
    attr: Attr,
    mod: float,
    held: bool,
) -> None:
    base = make(influence=Influence())
    p = make(held=tile if held else "", influence=Influence())
    value = base.resource_value(attr, 1, False)
    assert value > 0.0
    assert p.resource_value(attr, 1, False) == pytest.approx(
        value * (mod if held else 1.0)
    )


@pytest.mark.parametrize("low", [2, 3, 4])
def test_spy_satellites_spice_requires_three_low_factions(low: int) -> None:
    ranks = [0] * low + [2] * (4 - low)
    p = make(held="spy_satellites", influence=Influence(*ranks))
    base = make(influence=Influence(*ranks))
    assert p.spice_value(1) == pytest.approx(
        base.spice_value(1) * (1.1 if low >= 3 else 1.0)
    )


@pytest.mark.parametrize("held", [False, True])
def test_sonic_snoopers_intrigue_value(held: bool) -> None:
    base = make()
    p = make(held="sonic_snoopers" if held else "")
    assert p.intrigue_value() == pytest.approx(
        base.intrigue_value() * (1.2 if held else 1.0)
    )


@pytest.mark.parametrize("held", [False, True])
@pytest.mark.parametrize("turn", ["turn", "reveal"])
def test_minimic_film_persuasion_preview(held: bool, turn: str) -> None:
    p = make(held="minimic_film" if held else "", turn=turn)
    base = make(turn=turn)
    assert p.possible_persuasion() == (
        base.possible_persuasion() + int(held and turn != "reveal")
    )


@pytest.mark.parametrize("held", [False, True])
def test_holtzman_protects_tsmf_from_trash(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
) -> None:
    p = make(held="holtzman_engine" if held else "")
    card = synthetic("tsmf", TrashValue=4.0)
    assert card.archetype is not None
    card = replace(
        card,
        archetype=replace(
            card.archetype, short="ImperiumArchetypes.BaseSet.TheSpiceMustFlow"
        ),
    )
    monkeypatch.setattr(p, "_own_cards", lambda *zones: [card])
    assert p.trash_mod() == (-1.0 if held else 1.5)
    chosen, value = p.card_to_trash([card], 1.0)
    assert chosen == (None if held else card)
    assert value == (1.0 if held else 140.09)


@pytest.mark.parametrize("held", [False, True])
def test_memocorders_new_icons_bonus(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
) -> None:
    p = make(held="memocorders" if held else "")
    monkeypatch.setattr(p, "is_climax", lambda: False)
    monkeypatch.setattr(p, "deck_agent_icons", dict)
    monkeypatch.setattr(Summer, "tracing", True)
    # No acquire effects, abilities or factions; isolate the new-icon line.
    card = synthetic("icon", IconList=("Emperor",), AcquireValue=4.0)
    result = p.acquire_value(card)
    assert result.reasons is not None
    icons = [value for op, reason, value in result.reasons if reason == "New Icons"]
    assert icons == [pytest.approx(p.C.AcquireNewIconsBonus * (1.33 if held else 1.0))]


@pytest.mark.parametrize("held", [False, True])
def test_memocorders_influence_crossing_three(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
) -> None:
    p = make(held="memocorders" if held else "", influence=Influence(2, 0, 0, 0))
    monkeypatch.setattr(Summer, "tracing", True)
    s = p.gain_influence_value("emperor", 1, -1, False)
    assert s.reasons is not None
    lines = [r for r in s.reasons if r[1] == "Memocorders"]
    assert len(lines) == int(held)
    base = make(influence=Influence(2, 0, 0, 0))
    assert s.sum == pytest.approx(
        base.gain_influence_value("emperor", 1, -1, False).sum * (1.5 if held else 1.0)
    )


@pytest.mark.parametrize("held", [False, True])
def test_memocorders_suppresses_alliance_unlikely(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
) -> None:
    p = make(held="memocorders" if held else "", influence=Influence(2, 0, 0, 0))
    foe = (p.ctx.seat + 1) % 4
    s = t.with_player(p.ctx.state, foe, influence=Influence(5, 0, 0, 0))
    p = t.make_profile(s, p.ctx.seat)
    monkeypatch.setattr(Summer, "tracing", True)
    value = p.gain_influence_value("emperor", 1, -1, False)
    assert value.reasons is not None
    assert any(r[1] == "Alliance Unlikely" for r in value.reasons) is (not held)


@pytest.mark.parametrize("held", [False, True])
@pytest.mark.parametrize("low", [1, 2])
def test_spy_satellites_influence_vp_suppression(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
    low: int,
) -> None:
    ranks = [1] * low + [2] * (4 - low)
    p = make(held="spy_satellites" if held else "", influence=Influence(*ranks))
    monkeypatch.setattr(Summer, "tracing", True)
    value = p.gain_influence_value("emperor", 1, -1, False)
    assert value.reasons is not None
    suppress = held and low >= 2
    assert any(r[1] == "Spy Satellites" for r in value.reasons) is suppress
    if suppress:
        assert value.sum == 0.0
    else:
        assert value.sum > 0.0


@pytest.mark.parametrize("held", [False, True])
def test_windtraps_relative_conflict_value(held: bool) -> None:
    base = make()
    p = make(held="windtraps" if held else "")
    assert p.relative_conflict_value().sum == pytest.approx(
        base.relative_conflict_value().sum + (p.water_value(1) if held else 0.0)
    )


@pytest.mark.parametrize("held", [False, True])
@pytest.mark.parametrize("strength", [0, 1])
def test_artillery_reveal_penalty_order(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
    strength: int,
) -> None:
    from dune_imperium.agents.app_ai.abilities import generic as g

    p = make(held="artillery" if held else "")
    card = synthetic("agent", Strength=strength)
    monkeypatch.setattr(g, "value_for_reveal_abilities", lambda c, p: Summer(10.0))
    # AgentAbility's other lines add no value for this synthetic card.
    result = AgentAbility(card).value_for_player(p)
    expected = Summer(10.0)
    if held and strength > 0:
        expected.multiply("Artillery", 1.66)
    expected.multiply("Reveal Scale", -0.5)
    assert result.sum == expected.sum


@pytest.mark.parametrize("held", [False, True])
def test_restricted_ordnance_high_council_modifier(
    monkeypatch: pytest.MonkeyPatch,
    held: bool,
) -> None:
    p = make(held="restricted_ordnance" if held else "", resources=Resources(solari=20))
    base = make(resources=Resources(solari=20))
    monkeypatch.setattr(p, "high_council_value", lambda: 8.0)
    monkeypatch.setattr(base, "high_council_value", lambda: 8.0)
    space = space_entity("imperium_high_council", p.ctx.board)
    assert HighCouncilSpaceAbility(space).value_for_player(p).sum == pytest.approx(
        HighCouncilSpaceAbility(space).value_for_player(base).sum
        * (1.5 if held else 1.0)
    )
