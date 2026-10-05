"""Rise of Ix tech machinery: ``profile/tech.py`` and ``abilities/tech.py``.

Spec: ``analysis/ai/spec/rix-tech.md`` (§3 tile valuation, §4 the profile
methods, §6.1-6.3 acquisition sources, §8 tile ability classes; the Errata
override the body). The tiles are the app's Rise of Ix archetypes built
catalog-free (``tech_tile_entity``); the board reads ``AppContext`` does not
map yet (face-up tiles, negotiators, dreadnoughts) are stubbed on the
``Profile``. Numbers are the Hard constants unless a test is about levels.
"""

import math
import random
from collections.abc import Sequence
from dataclasses import replace
from functools import cache
from types import MappingProxyType

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import testing as _t
from dune_imperium.agents.app_ai.abilities import tech as at
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.catalog import card_entity, track_entity
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile import tech as pt
from dune_imperium.agents.app_ai.profile.influence import NO_FACTION
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.state import GameState

_TILE = "TechTileArchetypes.RiseOfIx."
_AA = "worm.canis.abilities.ActivatedAbilities."
_IC_ABILITY = _AA + "Immortality.InterstellarConspiracyAbility"

TILE_SHORTS = tuple(
    sorted(
        short
        for short, arch in ARCHETYPES.items()
        if arch.attributes.get("EntityType") == "TechTile"
    )
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@cache
def base_state() -> GameState:
    """Round 1, the first Agent turn: Uprising + CHOAM, starters only."""

    return _t.first_decision("turn")


def seat_of(state: GameState) -> int:
    decision = _t.ENGINE.current_decision(state)
    owner = getattr(decision, "owner", None)
    assert isinstance(owner, int)
    return owner


def make(
    state: GameState | None = None, *, level: int = 2, rng_seed: int = 0
) -> Profile:
    state = base_state() if state is None else state
    return _t.make_profile(state, seat_of(state), level=level, rng_seed=rng_seed)


def tile(name: str) -> Entity:
    return pt.tech_tile_entity(_TILE + name)


def at_arc(p: Profile, monkeypatch: pytest.MonkeyPatch, arc: int) -> None:
    monkeypatch.setattr(p, "game_arc", lambda: arc)


def offer(p: Profile, monkeypatch: pytest.MonkeyPatch, *tiles: Entity) -> None:
    monkeypatch.setattr(p, "tech_face_up_tiles", lambda: list(tiles))


def with_resources(spice: int = 0, solari: int = 0) -> GameState:
    state = base_state()
    seat = seat_of(state)
    me = state.players[seat]
    return _t.with_player(
        state, seat, resources=replace(me.resources, spice=spice, solari=solari)
    )


def request(*entities: Entity) -> Request:
    return Request(infos=(TargetInfo(entities=tuple(entities)),))


def stub_values(
    p: Profile, monkeypatch: pytest.MonkeyPatch, values: dict[str, float]
) -> None:
    """``tech_tile_acquire_value`` returns ``values[tile.ref]``."""

    monkeypatch.setattr(p, "tech_tile_acquire_value", lambda t: Summer(values[t.ref]))


def stub_influence(
    p: Profile, monkeypatch: pytest.MonkeyPatch, values: dict[str, float]
) -> None:
    """``gain_influence_value(f, ...)`` returns ``values[f]``."""

    def gain(
        faction: str, amount: int, current_rank: int = -1, has_alliance: bool = False
    ) -> Summer:
        return Summer(values[faction])

    monkeypatch.setattr(p, "gain_influence_value", gain)


def synthetic_tile(**attributes: object) -> Entity:
    """An app-style tile archetype (docs/app-ai-plan.md §11.3 shape)."""

    attrs: dict[str, object] = {"EntityType": "TechTile", "AcquireValue": 4.0}
    attrs.update(attributes)
    arch = Archetype(
        short="TechTileArchetypes.AppStyle.Test",
        kind="other",
        title="Test",
        in_uprising=False,
        in_uprising_choam=False,
        attributes=MappingProxyType(attrs),
    )
    return pt.tech_tile_entity(arch)


# =================================================================================
# §2 Tile data
# =================================================================================


def test_eighteen_rise_of_ix_tiles_cost_twice_their_spice() -> None:
    assert len(TILE_SHORTS) == 18
    for short in TILE_SHORTS:
        t = pt.tech_tile_entity(short)
        assert at.is_tech_tile(t)
        assert t.float_attr("AcquireValue") == 2.0 * pt.spice_cost(t)


def test_early_buyable_tiles_are_those_with_early_mod_above_one() -> None:
    early = {
        short.removeprefix(_TILE)
        for short in TILE_SHORTS
        if pt.tech_tile_entity(short).float_attr("EarlyMod", 0.0) > 1.0
    }
    assert early == {
        "DisposalFacility",
        "Holoprojectors",
        "HoltzmanEngine",
        "MinimicFilm",
        "ShuttleFleet",
        "Spaceport",
        "TrainingDrones",
        "Windtraps",
    }


# =================================================================================
# §3 Tile valuation
# =================================================================================


def closed_form(p: Profile, t: Entity, arc: int) -> float:
    """Spec §3.5, with the effect values the profile itself prices."""

    name = (t.short or "").removeprefix(_TILE)
    effects = {
        "Flagship": lambda: p.victory_point_value(1),
        "InvasionShips": lambda: p.resource_value(Attr.TROOPS, 4, False),
        "Memocorders": lambda: p.gain_influence_value(NO_FACTION, 1, -1, False).sum,
        "Windtraps": lambda: p.resource_value(Attr.WATER, 1, False),
    }.get(name, lambda: 0.0)()
    bonus = 2.0 * p.intrigue_value() if name == "Chaumurky" else 0.0
    raw = 2.0 * pt.spice_cost(t) + effects + bonus
    early = t.opt_float_attr("EarlyMod")
    late = t.opt_float_attr("LateMod")
    mod = (
        1.0 if early is None else early,
        1.0,
        1.0 if late is None else late,
    )[arc]
    value = raw + (mod * raw - raw)
    if p.minimum_acquire_value() > value:
        return 0.0
    if arc == 0 and (early is None or early <= 1.0):
        return 0.0
    return value


@pytest.mark.parametrize("arc", [0, 1, 2])
def test_tile_value_closed_form(arc: int, monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    at_arc(p, monkeypatch, arc)
    for short in TILE_SHORTS:
        t = pt.tech_tile_entity(short)
        assert p.tech_tile_acquire_value(t).sum == closed_form(p, t, arc), short


def test_tile_value_pinned_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    """A few hand values (Hard): Holoprojectors 6 x 1.1 early, Spaceport
    10 x 1.2 early, Training Drones 6 x 0.75 late, Disposal Facility 0 late
    (LateMod 0.0 < 2.2), Artillery 0 early (no EarlyMod) and late (2.0 <
    2.2)."""

    p = make()
    at_arc(p, monkeypatch, 0)
    assert p.tech_tile_acquire_value(tile("Holoprojectors")).sum == pytest.approx(6.6)
    assert p.tech_tile_acquire_value(tile("Spaceport")).sum == pytest.approx(12.0)
    assert p.tech_tile_acquire_value(tile("Artillery")).sum == 0.0
    at_arc(p, monkeypatch, 1)
    assert p.tech_tile_acquire_value(tile("Artillery")).sum == 2.0
    at_arc(p, monkeypatch, 2)
    assert p.tech_tile_acquire_value(tile("TrainingDrones")).sum == 4.5
    assert p.tech_tile_acquire_value(tile("DisposalFacility")).sum == 0.0
    assert p.tech_tile_acquire_value(tile("Artillery")).sum == 0.0


def test_minimum_acquire_value_is_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    """``MinimumAcquireValue > Sum`` zeroes; a value equal to it is kept."""

    p = make()
    at_arc(p, monkeypatch, 1)
    monkeypatch.setattr(p, "minimum_acquire_value", lambda: 2.0)
    assert p.tech_tile_acquire_value(tile("Artillery")).sum == 2.0
    monkeypatch.setattr(p, "minimum_acquire_value", lambda: math.nextafter(2.0, 3.0))
    assert p.tech_tile_acquire_value(tile("Artillery")).sum == 0.0


def test_minimum_acquire_value_by_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard 1.2/1.7/2.2, Easy 0.5: Artillery (2.0) survives Late only on Easy."""

    hard = make()
    assert (
        hard.C.MinimumAcquireValueEarly,
        hard.C.MinimumAcquireValueMid,
        hard.C.MinimumAcquireValueLate,
    ) == (1.2, 1.7, 2.2)
    at_arc(hard, monkeypatch, 2)
    assert hard.tech_tile_acquire_value(tile("Artillery")).sum == 0.0
    easy = make(level=0)
    assert easy.C.MinimumAcquireValueLate == 0.5
    at_arc(easy, monkeypatch, 2)
    assert easy.tech_tile_acquire_value(tile("Artillery")).sum == 2.0


def test_not_early_tech_needs_early_mod_strictly_above_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    at_arc(p, monkeypatch, 0)
    assert p.tech_tile_acquire_value(synthetic_tile(EarlyMod=1.0)).sum == 0.0
    assert p.tech_tile_acquire_value(synthetic_tile()).sum == 0.0
    early = p.tech_tile_acquire_value(synthetic_tile(EarlyMod=1.25)).sum
    assert early == 5.0
    at_arc(p, monkeypatch, 1)
    assert p.tech_tile_acquire_value(synthetic_tile(EarlyMod=1.0)).sum == 4.0


def test_game_arc_multiply_replays_the_summer(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Multiply`` adds ``m*Sum - Sum``; LateMod 0.75 on Troop Transports."""

    p = make()
    at_arc(p, monkeypatch, 2)
    s = p.tech_tile_acquire_value(tile("TroopTransports")).sum
    assert s == 4.0 + (0.75 * 4.0 - 4.0) == 3.0


# -- §3.2 GetSynergyMod -------------------------------------------------------------


def test_tile_value_merges_synergy_mod(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    at_arc(p, monkeypatch, 1)
    seen: list[str | None] = []

    def synergy(card: Entity) -> Summer:
        seen.append(card.short)
        return Summer(1.25)

    monkeypatch.setattr(p, "synergy_mod", synergy)
    assert p.tech_tile_acquire_value(tile("Artillery")).sum == 3.25
    assert seen == [_TILE + "Artillery"]


def test_synergy_is_zero_for_every_tile_in_uprising() -> None:
    p = make()
    for short in TILE_SHORTS:
        assert p.synergy_mod(pt.tech_tile_entity(short)).sum == 0.0, short


def owning_the_whole_row_deck(config: RulesetConfig | None) -> GameState:
    """The deciding seat owns every Imperium Row card of the game (deck).

    Interstellar Conspiracy (Immortality) is left out: its VIP is the one
    Errata exception (``test_interstellar_conspiracy_gives_tiles_synergy``).
    """

    state = base_state() if config is None else _t.first_decision("turn", config=config)
    seat = seat_of(state)
    owned = tuple(c for c in state.imperium_deck if "interstellar_conspiracy" not in c)
    me = state.players[seat]
    return _t.with_player(state, seat, deck=(*me.deck, *owned))


@pytest.mark.parametrize(
    "config", [None, RulesetConfig(immortality=True)], ids=["uprising", "immortality"]
)
def test_no_owned_card_gives_a_tile_synergy(
    config: RulesetConfig | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§3.2: every card VIP except Interstellar Conspiracy's needs a candidate
    ``FactionsList`` or tag no tile has, so with every Row card owned (every
    ported VIP override reached through ``GetSynergyMod``'s Deck pile) a
    tile's synergy stays 0 in every arc."""

    state = owning_the_whole_row_deck(config)
    assert len(state.players[seat_of(state)].deck) > 30
    p = make(state)
    for arc in (0, 1, 2):
        at_arc(p, monkeypatch, arc)
        for short in TILE_SHORTS:
            assert p.synergy_mod(pt.tech_tile_entity(short)).sum == 0.0, (arc, short)


@cache
def conspiracy_state() -> GameState:
    """Immortality: the deciding seat holds Interstellar Conspiracy in its deck."""

    state = _t.first_decision("turn", config=RulesetConfig(immortality=True))
    seat = seat_of(state)
    me = state.players[seat]
    ic = tuple(c for c in state.imperium_deck if "interstellar_conspiracy" in c)
    assert ic
    state = _t.with_state(
        state, imperium_deck=tuple(c for c in state.imperium_deck if c not in ic)
    )
    return _t.with_player(state, seat, deck=(*me.deck, *ic))


@pytest.mark.skipif(
    _IC_ABILITY not in PORTS,
    reason="InterstellarConspiracyAbility is ported by abilities/immortality.py",
)
def test_interstellar_conspiracy_gives_tiles_synergy() -> None:
    """Errata §3.2: Interstellar Conspiracy's VIP adds ``GetSpiceValue(1)``
    for any candidate, tiles included; ``GetSynergyMod`` caps the sum at
    ``SynergyModMaxValue`` (2.0) and skips it in climax."""

    p = make(conspiracy_state())
    cap = p.C.SynergyModMaxValue
    spice = p.spice_value(1)
    expected = cap if spice > cap else spice
    for short in TILE_SHORTS:
        assert p.synergy_mod(pt.tech_tile_entity(short)).sum == expected, short
    climax = make(conspiracy_state())
    climax._is_climax = True
    assert climax.synergy_mod(tile("Spaceport")).sum == 0.0


# -- §3.3 GetAcquireEffectsValue ------------------------------------------------------


def test_invasion_ships_values_four_troops_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    calls: list[tuple[Attr, int, bool]] = []

    def resource_value(attr: Attr, amount: int, posture: bool = False) -> float:
        calls.append((attr, amount, posture))
        return 7.5

    monkeypatch.setattr(p, "resource_value", resource_value)
    assert p.tech_tile_acquire_effects_value(tile("InvasionShips")).sum == 7.5
    assert calls == [(Attr.TROOPS, 4, False)]


@pytest.mark.parametrize(
    "name",
    ["Chaumurky", "DisposalFacility", "ShuttleFleet", "SonicSnoopers", "Spaceport"],
)
def test_unvalued_acquire_effects(name: str) -> None:
    """Intrigue, Trash, Imperium and AnyTwoDifferentRanks are worth 0."""

    assert make().tech_tile_acquire_effects_value(tile(name)).sum == 0.0


def test_valued_acquire_effects() -> None:
    p = make()
    assert p.tech_tile_acquire_effects_value(tile("Flagship")).sum == (
        p.victory_point_value(1)
    )
    assert p.tech_tile_acquire_effects_value(tile("Windtraps")).sum == (
        p.resource_value(Attr.WATER, 1, False)
    )
    assert p.tech_tile_acquire_effects_value(tile("Memocorders")).sum == (
        p.gain_influence_value(NO_FACTION, 1, -1, False).sum
    )


# -- §3.4 GetSpecificAcquireBonus -----------------------------------------------------


def test_chaumurky_bonus_is_two_intrigue_values() -> None:
    p = make()
    value = p.intrigue_value()
    assert p.tech_tile_specific_acquire_bonus(tile("Chaumurky")).sum == value + value


@pytest.mark.parametrize(("dreadnoughts", "bonus"), [(2, -2.0), (1, 0.0), (0, 0.0)])
def test_detonation_devices_bonus(
    dreadnoughts: int, bonus: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """-2.0 with both dreadnoughts in the supply; else ``Pow`` multiplies an
    empty summer (0)."""

    p = make()
    assert p.C.DetonationDevicesValueNoDreadnoughtMod == -2.0
    monkeypatch.setattr(p, "tech_dreadnoughts_in_supply", lambda: dreadnoughts)
    assert p.tech_tile_specific_acquire_bonus(tile("DetonationDevices")).sum == bonus


def test_other_specific_bonuses_are_zero() -> None:
    p = make()
    for short in TILE_SHORTS:
        if short.endswith(("Chaumurky", "DetonationDevices")):
            continue
        assert p.tech_tile_specific_acquire_bonus(pt.tech_tile_entity(short)).sum == 0.0


# =================================================================================
# §4 WormAIProfile tech methods
# =================================================================================


def test_targets_affordability_boundary() -> None:
    tiles = [tile("Artillery"), tile("Chaumurky"), tile("Flagship")]  # 1, 4, 8
    targets = pt.acquire_tech_tile_targets(
        tiles, spice=3, solari=0, negotiators=0, discount=1, allow_solari=False
    )
    assert [t.ref for t in targets] == [_TILE + "Artillery", _TILE + "Chaumurky"]


def test_targets_take_the_larger_of_spice_and_solari() -> None:
    tiles = [tile("Memocorders"), tile("Spaceport"), tile("ShuttleFleet")]  # 2, 5, 6
    with_solari = pt.acquire_tech_tile_targets(
        tiles, spice=2, solari=5, negotiators=0, discount=0, allow_solari=True
    )
    assert [t.ref for t in with_solari] == [_TILE + "Memocorders", _TILE + "Spaceport"]
    spice_only = pt.acquire_tech_tile_targets(
        tiles, spice=2, solari=5, negotiators=0, discount=0, allow_solari=False
    )
    assert [t.ref for t in spice_only] == [_TILE + "Memocorders"]


def test_targets_count_negotiators_and_skip_non_tiles() -> None:
    card = card_entity("player:0:starter:dagger:0", 0)
    targets = pt.acquire_tech_tile_targets(
        [card, tile("ShuttleFleet")],
        spice=3,
        solari=0,
        negotiators=2,
        discount=1,
        allow_solari=False,
    )
    assert [t.ref for t in targets] == [_TILE + "ShuttleFleet"]


def test_profile_targets_read_the_seats_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(with_resources(spice=4, solari=9))
    offer(p, monkeypatch, tile("Chaumurky"), tile("Spaceport"))
    assert [t.ref for t in p.tech_acquire_targets(0, False)] == [_TILE + "Chaumurky"]
    assert len(p.tech_acquire_targets(0, True)) == 2
    assert len(p.tech_acquire_targets(1, False)) == 2


def test_tile_to_acquire_takes_the_first_best(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(with_resources(spice=10))
    a, b, c = tile("Artillery"), tile("Chaumurky"), tile("Memocorders")
    offer(p, monkeypatch, a, b, c)
    stub_values(p, monkeypatch, {a.ref: 3.0, b.ref: 5.0, c.ref: 5.0})
    assert p.tech_tile_to_acquire(0, False) is b
    stub_values(p, monkeypatch, {a.ref: 0.0, b.ref: -1.0, c.ref: 0.0})
    assert p.tech_tile_to_acquire(0, False) is a  # worth 0, still returned


def test_tile_to_acquire_none_when_nothing_affordable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(with_resources(spice=0))
    offer(p, monkeypatch, tile("Flagship"))
    assert p.tech_tile_to_acquire(0, False) is None
    assert p.tech_options_mod(0, False) == 0.0
    assert p.buy_tech_value(0, False) == 0.0


def test_tech_options_mod(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Math.Max(2.0, 0.5 * printed cost)``; the discount only widens the
    choice."""

    p = make(with_resources(spice=6))
    offer(p, monkeypatch, tile("Flagship"))  # cost 8
    stub_values(p, monkeypatch, {_TILE + "Flagship": 9.0, _TILE + "Artillery": 9.0})
    assert p.tech_options_mod(0, False) == 0.0
    assert p.tech_options_mod(2, False) == 4.0
    offer(p, monkeypatch, tile("Artillery"))  # cost 1
    assert p.tech_options_mod(0, False) == 2.0


def test_tech_options_mod_with_machine_culture(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(with_resources(spice=8))
    offer(p, monkeypatch, tile("Flagship"))
    stub_values(p, monkeypatch, {_TILE + "Flagship": 9.0})
    held: list[str] = []

    def has_intrigue_card(ctx: object, archetype: str) -> bool:
        held.append(archetype)
        return True

    monkeypatch.setattr(pt, "has_intrigue_card", has_intrigue_card)
    assert p.C.MachineCultureTechValueMod == 1.2
    assert p.tech_options_mod(0, False) == 4.0 * 1.2
    assert held == ["IntrigueArchetypes.RiseOfIx.MachineCulture"]


def test_machine_culture_is_never_held_in_our_games() -> None:
    p = make()
    assert not pt.has_intrigue_card(p.ctx, pt.MACHINE_CULTURE)


@pytest.mark.parametrize(("arc", "mod"), [(0, 1.0), (1, 0.5), (2, 0.0)])
def test_buy_tech_value_by_arc(
    arc: int, mod: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make(with_resources(spice=8))
    offer(p, monkeypatch, tile("Flagship"))
    stub_values(p, monkeypatch, {_TILE + "Flagship": 9.0})
    at_arc(p, monkeypatch, arc)
    c = p.C
    assert (c.BuyTechEarly, c.BuyTechMid, c.BuyTechLate)[arc] == mod
    assert p.buy_tech_value(0, False) == 4.0 * mod


@pytest.mark.parametrize(("arc", "mod"), [(0, 0.9), (1, 0.8), (2, 0.7)])
def test_negotiate_tech_value_by_arc(
    arc: int, mod: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make()
    at_arc(p, monkeypatch, arc)
    monkeypatch.setattr(p, "resource_value", lambda attr, amount, posture=False: 2.5)
    assert p.negotiate_tech_value() == 2.5 * mod


def test_no_tile_is_offered_until_the_mapping_stage() -> None:
    p = make(with_resources(spice=20))
    assert p.tech_face_up_tiles() == []
    assert p.tech_negotiator_count() == 0
    assert p.tech_dreadnoughts_in_supply() == 0
    assert p.buy_tech_value(0, False) == 0.0


# =================================================================================
# §6.1 AcquireTechAbility
# =================================================================================

OWNER = Entity(Kind.CARD, "owner")


def acquire(cls_name: str = "AcquireTechAbility") -> at.AcquireTechAbility:
    ability = ability_for(_AA + "RiseOfIx." + cls_name, OWNER)
    assert isinstance(ability, at.AcquireTechAbility)
    return ability


def test_acquire_tech_members() -> None:
    p = make()
    base = acquire()
    assert base.selection_mode(p) is SelectionMode.EXPLICIT
    assert not base.can_run_immediately(p)
    assert base.tech_discount == 0
    assert acquire("AcquireTechAbilityDiscount1").tech_discount == 1
    agent = acquire("AcquireTechAgentAbility")
    assert agent.timing is Timing.AGENT
    assert agent.tech_discount == 0


def test_acquire_tech_value_is_buy_tech_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """``BuyTechValue(TechDiscount, false)``: with 3 spice Chaumurky (4) is
    affordable only with the discount of 1."""

    p = make(with_resources(spice=3))
    at_arc(p, monkeypatch, 0)
    offer(p, monkeypatch, tile("Chaumurky"))
    assert acquire().value_for_player(p).sum == 0.0
    assert not acquire().meets_cost(p)
    discount = acquire("AcquireTechAbilityDiscount1")
    assert discount.meets_cost(p)
    assert discount.value_for_player(p).sum == 2.0  # Max(2.0, 0.5 * 4) * 1.0


def test_shipping_track2_members() -> None:
    """§6.1 subclass table: ``AcquireTechAbilityShippingTrack2`` has
    ``TechDiscount`` 2 (@0x4d99850), ``IsCustomAbility`` and ``IsUnexhausted``
    true, no timing, and inherits Explicit / not run immediately."""

    p = make()
    assert _AA + "RiseOfIx.AcquireTechAbilityShippingTrack2" in PORTS
    track2 = acquire("AcquireTechAbilityShippingTrack2")
    assert isinstance(track2, at.AcquireTechAbilityShippingTrack2)
    assert track2.tech_discount == 2
    assert track2.is_custom_ability
    assert track2.is_unexhausted
    assert not acquire().is_custom_ability
    assert track2.timing is Timing.NONE
    assert track2.selection_mode(p) is SelectionMode.EXPLICIT
    assert not track2.can_run_immediately(p)


def test_shipping_track2_value_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """V = ``BuyTechValue(2, false)``, not gated on the cost: with 6 spice
    Flagship (8) is affordable only with the discount of 2, ``Max(2.0, 0.5 *
    8) * BuyTechEarly 1.0 = 4.0``. ``Cost`` = ``HasCustomAbility(this)``
    first, and no frame of ours grants the Shipping-track reward."""

    p = make(with_resources(spice=6))
    at_arc(p, monkeypatch, 0)
    offer(p, monkeypatch, tile("Flagship"))
    track2 = acquire("AcquireTechAbilityShippingTrack2")
    assert isinstance(track2, at.AcquireTechAbilityShippingTrack2)
    assert acquire().value_for_player(p).sum == 0.0
    assert acquire("AcquireTechAbilityDiscount1").value_for_player(p).sum == 0.0
    assert track2.value_for_player(p).sum == 4.0
    assert not track2.has_custom_ability(p)
    assert not track2.meets_cost(p)
    monkeypatch.setattr(track2, "has_custom_ability", lambda p: True)
    assert track2.meets_cost(p)
    offer(p, monkeypatch)
    assert not track2.meets_cost(p)


def test_acquire_tech_evaluate_first_strictly_best(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    a, b, c = tile("Artillery"), tile("Chaumurky"), tile("Memocorders")
    stub_values(p, monkeypatch, {a.ref: 3.0, b.ref: 5.0, c.ref: 5.0})
    answer = acquire().evaluate(p, request(a, b, c))
    assert (answer.value, answer.response) == (5.0, ((b.ref,),))


def test_acquire_tech_evaluate_declines_at_half(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No tile worth > 0: the empty target list at 0.5 (``!(0.0 < value)``)."""

    p = make()
    a, b = tile("Artillery"), tile("Chaumurky")
    stub_values(p, monkeypatch, {a.ref: 0.0, b.ref: -2.0})
    answer = acquire().evaluate(p, request(a, b))
    assert (answer.value, answer.response) == (0.5, ())
    empty = acquire().evaluate(p, request())
    assert (empty.value, empty.response) == (0.5, ())
    stub_values(p, monkeypatch, {a.ref: 0.25, b.ref: -2.0})
    low = acquire().evaluate(p, request(a, b))
    assert (low.value, low.response) == (0.25, ((a.ref,),))


def test_acquire_tech_evaluate_ignores_non_tiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    a = tile("Spaceport")
    stub_values(p, monkeypatch, {a.ref: 4.0})
    card = card_entity("player:0:starter:dagger:0", 0)
    answer = acquire().evaluate(p, request(card, a))
    assert answer.response == ((a.ref,),)


# =================================================================================
# §6.2-6.3 negotiate-or-buy sources
# =================================================================================


@pytest.mark.parametrize(
    ("name", "discount"),
    [("TechNegotiationDeferredAbility", 1), ("IxianTechnologyAbility", 0)],
)
def test_negotiate_or_buy_value(
    name: str, discount: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make()
    buys: list[tuple[int, bool]] = []

    def buy(d: int, allow: bool) -> float:
        buys.append((d, allow))
        return 1.5

    monkeypatch.setattr(p, "buy_tech_value", buy)
    monkeypatch.setattr(p, "negotiate_tech_value", lambda: 2.0)
    ability = ability_for(_AA + "RiseOfIx." + name, OWNER)
    assert ability.value_for_player(p).sum == 2.0
    monkeypatch.setattr(p, "negotiate_tech_value", lambda: 1.0)
    assert ability.value_for_player(p).sum == 1.5
    assert buys == [(discount, False), (discount, False)]


@pytest.mark.parametrize(
    "name", ["TechNegotiationDeferredAbility", "IxianTechnologyAbility"]
)
def test_negotiate_or_buy_buys_only_above_one(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make()
    a, b = tile("Artillery"), tile("Spaceport")
    ability = ability_for(_AA + "RiseOfIx." + name, OWNER)
    stub_values(p, monkeypatch, {a.ref: 1.0, b.ref: 0.5})
    answer = ability.evaluate(p, request(a, b))
    assert (answer.value, answer.response) == (1.0, ((at.TECH_NEGOTIATION_AREA,),))
    stub_values(p, monkeypatch, {a.ref: math.nextafter(1.0, 2.0), b.ref: 3.0})
    answer = ability.evaluate(p, request(a, b))
    assert (answer.value, answer.response) == (3.0, ((b.ref,),))


def test_tech_negotiation_members() -> None:
    p = make()
    ability = ability_for(_AA + "RiseOfIx.TechNegotiationDeferredAbility", OWNER)
    assert isinstance(ability, at.TechNegotiationDeferredAbility)
    assert ability.timing is Timing.AGENT
    assert ability.selection_mode(p) is SelectionMode.EXPLICIT


# =================================================================================
# §8 Tile ability classes
# =================================================================================

_SHARED = {
    "Chaumurky": [_AA + "ChaumurkyAbility"],
    "MinimicFilm": [
        "worm.canis.abilities.TriggeredAbilities.RiseOfIx.MinimicFilmAbility"
    ],
    "Memocorders": [
        "worm.canis.abilities.ConflictAbilities.BaseSet.MemocordersAcquiredAbility"
    ],
    "DisposalFacility": [_AA + "DisposalFacilityAcquiredAbility"],
    "ShuttleFleet": [
        "worm.canis.abilities.ConflictAbilities.BaseSet.ShuttleFleetAcquiredAbility"
    ],
    "Spaceport": [  # x2 (WormAbilityIDs)
        "worm.canis.abilities.ConflictAbilities.BaseSet.DrawImperiumAcquiredAbility"
    ]
    * 2,
    "SonicSnoopers": [
        "worm.canis.abilities.ConflictAbilities.BaseSet.GainIntrigueAcquiredAbility"
    ],
}


@pytest.mark.parametrize("name", sorted(_SHARED))
def test_shared_tile_abilities_are_ported(name: str) -> None:
    ported = [
        type(a).APP_CLASS
        for a in abilities_of(tile(name))
        if not isinstance(a, UnportedAbility)
    ]
    assert ported == _SHARED[name]


def acquired(name: str) -> at.TechTileAcquiredAbility:
    for a in abilities_of(tile(name)):
        if isinstance(a, at.TechTileAcquiredAbility):
            return a
    raise AssertionError(name)


def test_tech_tile_acquired_ability_defaults() -> None:
    p = make()
    base = ability_for(
        _AA + "RiseOfIx.TechTileAcquiredAbilities.TechTileAcquiredAbility", OWNER
    )
    assert isinstance(base, at.TechTileAcquiredAbility)
    assert base.selection_mode(p) is SelectionMode.EXPLICIT
    assert base.can_run_immediately(p)
    assert base.value_for_player(p).sum == 0.0
    answer = base.evaluate(p, request())
    assert (answer.value, answer.response) == (0.0, None)
    spaceport = acquired("Spaceport")
    answer = spaceport.evaluate(p, request())
    assert (answer.value, answer.response) == (0.0, None)


def test_draw_imperium_acquired_value() -> None:
    p = make()
    expected = p.card_draw_value() + p.buy_gains(p.possible_persuasion_gain())
    assert acquired("Spaceport").value_for_player(p).sum == expected


def test_gain_intrigue_acquired_value() -> None:
    p = make()
    assert acquired("SonicSnoopers").value_for_player(p).sum == p.intrigue_value()


INFLUENCE = {
    "emperor": 1.0,
    "spacing_guild": 2.0,
    "bene_gesserit": 2.0,
    "fremen": 0.5,
}


def tracks() -> list[Entity]:
    return [track_entity(f) for f in FACTIONS]


def test_memocorders_acquired_value(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    stub_influence(p, monkeypatch, INFLUENCE)
    assert acquired("Memocorders").value_for_player(p).sum == p.spice_value(1) + 2.0


def test_memocorders_acquired_evaluate(monkeypatch: pytest.MonkeyPatch) -> None:
    """+100.0 per faction track, first strictly best (Spacing Guild before
    the tied Bene Gesserit)."""

    p = make()
    stub_influence(p, monkeypatch, INFLUENCE)
    answer = acquired("Memocorders").evaluate(p, request(*tracks()))
    assert (answer.value, answer.response) == (102.0, (("spacing_guild",),))


def test_shuttle_fleet_acquired_value(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    stub_influence(
        p,
        monkeypatch,
        {"emperor": 1.0, "spacing_guild": 4.0, "bene_gesserit": 2.0, "fremen": 3.0},
    )
    assert acquired("ShuttleFleet").value_for_player(p).sum == 7.0


def test_shuttle_fleet_acquired_evaluate(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    stub_influence(
        p,
        monkeypatch,
        {"emperor": 1.0, "spacing_guild": 4.0, "bene_gesserit": 2.0, "fremen": 3.0},
    )
    answer = acquired("ShuttleFleet").evaluate(p, request(*tracks()))
    assert (answer.value, answer.response) == (7.0, (("spacing_guild", "fremen"),))


@pytest.mark.parametrize("seed", range(6))
def test_shuttle_fleet_ties_follow_the_shuffle(
    seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ListUtil.Shuffle`` then a stable ``OrderByDescending``: tied factions
    keep the shuffled order (drawn from the profile's rng)."""

    values = {"emperor": 3.0, "spacing_guild": 1.0, "bene_gesserit": 3.0, "fremen": 3.0}
    p = make(rng_seed=seed)
    stub_influence(p, monkeypatch, values)
    answer = acquired("ShuttleFleet").evaluate(p, request(*tracks()))
    order = list(FACTIONS)
    random.Random(seed).shuffle(order)
    expected = tuple(f for f in order if values[f] == 3.0)[:2]
    assert (answer.value, answer.response) == (6.0, (expected,))


def test_shuttle_fleet_acquired_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Math.Max(0.5, sum)``; no track: 0.5 with the empty target list."""

    p = make()
    stub_influence(p, monkeypatch, dict.fromkeys(FACTIONS, 0.125))
    answer = acquired("ShuttleFleet").evaluate(p, request(*tracks()))
    assert answer.value == 0.5
    assert answer.response is not None and len(answer.response[0]) == 2
    empty = acquired("ShuttleFleet").evaluate(p, request())
    assert (empty.value, empty.response) == (0.5, ())


def test_disposal_facility_acquired_value() -> None:
    p = make()
    expected = p.trash_card_value() + p.trash_mod()
    assert acquired("DisposalFacility").value_for_player(p).sum == expected


def test_disposal_facility_acquired_evaluate(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    seat = p.ctx.seat
    cards = [card_entity(i, seat) for i in p.ctx.hand]
    seen: list[tuple[list[str], float]] = []

    def card_to_trash(
        targets: Sequence[Entity], minimum: float
    ) -> tuple[Entity | None, float]:
        seen.append(([t.ref for t in targets], minimum))
        return cards[1], 3.0

    monkeypatch.setattr(p, "card_to_trash", card_to_trash)
    ability = acquired("DisposalFacility")
    answer = ability.evaluate(p, request(*cards, track_entity("fremen")))
    assert (answer.value, answer.response) == (13.0, ((cards[1].ref,),))
    assert seen == [([c.ref for c in cards], 1.0)]

    def nothing(
        targets: Sequence[Entity], minimum: float
    ) -> tuple[Entity | None, float]:
        return None, 1.0

    monkeypatch.setattr(p, "card_to_trash", nothing)
    answer = ability.evaluate(p, request(*cards))
    assert (answer.value, answer.response) == (10.0, ())


def test_chaumurky_ability() -> None:
    p = make()
    (ability,) = abilities_of(tile("Chaumurky"))
    assert isinstance(ability, at.ChaumurkyAbility)
    assert ability.selection_mode(p) is SelectionMode.EXPLICIT
    assert ability.can_run_immediately(p)
    assert ability.is_endgame_playable(p)
    value = p.intrigue_value()
    assert ability.specific_acquire_value(p).sum == value + value
    assert ability.evaluate(p, request()) == Answer(
        100.0, (), "Chaumurky | always play"
    )


def test_minimic_film_has_no_ai_hook() -> None:
    p = make()
    (ability,) = abilities_of(tile("MinimicFilm"))
    assert isinstance(ability, at.MinimicFilmAbility)
    assert ability.value_for_player(p).sum == 0.0
    assert ability.specific_acquire_value(p).sum == 0.0
    assert ability.evaluate(p, request()).value == 0.0
