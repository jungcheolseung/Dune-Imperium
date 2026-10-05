"""The app-style Arrakeen Scouts prices, abilities and evaluators.

Spec: docs/app-ai/scouts.md (§1 primitive prices, §2 machinery, §3 decision
answers, §4 valuation terms in the faithful ports, §6 accessors, §7
decisions), as revised by docs/app-ai-plan.md §11.7 (the forced hand trash
with no junk card). Each test builds a real Scouts game state, adjusts the
fields a formula reads, and pins the spec's formula against the existing
profile prices it is made of (the app has no Scouts to compare with: plan
§11.6 "verified against the rules of this section").
"""

from collections.abc import Callable
from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import testing as _conftest
from dune_imperium.agents.app_ai.abilities import (
    PORTS,
    Request,
    TargetInfo,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities import scouts as sc
from dune_imperium.agents.app_ai.abilities.base import SelectionMode
from dune_imperium.agents.app_ai.abilities.generic import (
    ContractAbility,
    DeferredAbility,
    contract_value_for_player,
    gain_any_influence_value,
)
from dune_imperium.agents.app_ai.abilities.immortality import (
    ReclaimedForcesAcquireAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    CorrinthCityRevealAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    DESERT_RIDING_ABILITY,
    MISSION_PIECES_ABILITY,
    SCOUTS_LINE_ARCHETYPES,
    SPACE_ARCHETYPES,
    SUBCOMMITTEE_OFFER_ABILITY,
    card_entity,
    contract_entity,
    post_entity,
    scouts_line_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import (
    FACTIONS,
    RECLAIMED_FORCES_REF,
    Board,
)
from dune_imperium.agents.app_ai.data.synthetic import SYNTHETIC
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.scouts import HELIX_SPICE, OwnSupplyContext
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState

SCOUTS = RulesetConfig(choam_module=True, immortality=True, arrakeen_scouts=True)
BASE = RulesetConfig(choam_module=True, immortality=True)


def close(value: float) -> object:
    """Equal up to float summation order (the spec writes the terms in
    another order than the summer adds them)."""

    return pytest.approx(value, rel=1e-12, abs=1e-12)


# -- states and profiles -------------------------------------------------------------


@cache
def scouts_state() -> GameState:
    """Round 1, the first Agent turn of a Scouts + Immortality + CHOAM game."""

    return _conftest.first_decision("turn", config=SCOUTS)


@cache
def base_state() -> GameState:
    return _conftest.first_decision("turn", config=BASE)


def owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


ME = 3  # the first seat to decide in round 1 with these seeds


def with_me(state: GameState, **changes: object) -> GameState:
    return _conftest.with_player(state, ME, **changes)


def with_state(state: GameState, **changes: object) -> GameState:
    return _conftest.with_state(state, **changes)


def stub(profile: Profile, **methods: object) -> Profile:
    """Replace methods on the instance; a non-callable becomes a constant."""

    for name, value in methods.items():
        if isinstance(value, Summer):
            total = value.sum
            setattr(profile, name, lambda *_a, _t=total, **_k: Summer(_t))
        elif isinstance(value, IntSummer):
            total_i = value.sum
            setattr(profile, name, lambda *_a, _t=total_i, **_k: IntSummer(_t))
        elif callable(value):
            setattr(profile, name, value)
        else:
            setattr(profile, name, lambda *_a, _v=value, **_k: _v)
    return profile


def prof(state: GameState | None = None, *, gate: int | None = 100) -> Profile:
    """Seat 3's profile; the Conflict gate pinned unless ``gate`` is None."""

    profile = _conftest.make_profile(scouts_state() if state is None else state, ME)
    if gate is not None:
        stub(profile, scouts_conflict_troops_gate=gate)
    return profile


def line(item: str, k: int) -> Entity:
    return scouts_line_entity(item, k, ME)


def L(p: Profile, item: str, k: int) -> float:
    return p.scouts_line_value(line(item, k)).sum


def with_parked(
    state: GameState,
    rows: tuple[tuple[str, int, str, int], ...],
    **changes: object,
) -> GameState:
    """Seat 3's fields and the parked rows changed together (their counts
    must match, ``GameState`` checks)."""

    players = list(state.players)
    players[ME] = replace(players[ME], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players), scouts_parked=rows)


def troops(garrison: int = 3, conflict: int = 0, parked: int = 0) -> dict[str, int]:
    """Troop fields that keep the 12-troop invariant (no specimens)."""

    return {
        "troops_garrison": garrison,
        "troops_conflict": conflict,
        "troops_parked": parked,
        "troops_supply": 12 - garrison - conflict - parked,
        "specimens": 0,
    }


# -- §0 prices ------------------------------------------------------------------------


class Prices:
    """The §0 notation, read off one profile."""

    def __init__(self, p: Profile) -> None:
        self.p = p

    def Sol(self, n: int) -> float:  # noqa: N802 (spec notation)
        return self.p.solari_value(n)

    def Spi(self, n: int) -> float:  # noqa: N802
        return self.p.spice_value(n)

    def Wat(self, n: int) -> float:  # noqa: N802
        return self.p.water_value(n)

    def Spec(self, n: int) -> float:  # noqa: N802
        return self.p.specimen_value(n)

    def Tr(self, n: int) -> float:  # noqa: N802
        return self.p.troop_value(n, False)

    def UTr(self, n: int) -> float:  # noqa: N802
        return self.p.uncapped_troop_value(n)

    def G(self, faction: str, n: int) -> float:  # noqa: N802
        return self.p.gain_influence_value(faction, n, -1, False).sum

    def TV(self, n: int) -> float:  # noqa: N802
        return self.p.tleilaxu_value(n).sum

    @property
    def Int(self) -> float:  # noqa: N802
        return self.p.intrigue_value()

    @property
    def Draw(self) -> float:  # noqa: N802
        p = self.p
        return 0.0 + p.card_draw_value() + p.buy_gains(p.possible_persuasion_gain())

    @property
    def CDV(self) -> float:  # noqa: N802
        return self.p.card_draw_value()

    @property
    def Spy(self) -> float:  # noqa: N802
        return self.p.spy_value().sum

    @property
    def RSpy(self) -> float:  # noqa: N802
        return self.p.recall_spy_value().sum

    @property
    def Gany(self) -> float:  # noqa: N802
        return gain_any_influence_value(self.p, 1).sum

    @property
    def K(self) -> float:  # noqa: N802
        return contract_value_for_player(self.p).sum

    @property
    def Trash(self) -> float:  # noqa: N802
        return 0.0 + self.p.trash_card_value() + self.p.trash_mod()

    @property
    def TI(self) -> float:  # noqa: N802
        return self.p.trash_intrigue_value()

    @property
    def Disc(self) -> float:  # noqa: N802
        return self.p.discard_value()

    @property
    def RA(self) -> float:  # noqa: N802
        return self.p.recall_agent_value()

    @property
    def RV(self) -> float:  # noqa: N802
        return self.p.research_value().sum

    @property
    def BWV(self) -> float:  # noqa: N802
        return self.p.blow_wall_value().sum


# -- coverage (B1's line archetypes, the overlays) -------------------------------------


def test_every_scouts_line_ability_is_ported() -> None:
    assert len(SCOUTS_LINE_ARCHETYPES) == 85
    for ref, short in SCOUTS_LINE_ARCHETYPES.items():
        ids = SYNTHETIC[short].attributes["WormAbilityIDs"]
        assert isinstance(ids, tuple)
        for ability_id in ids:
            assert ability_id in PORTS, (ref, ability_id)
        item, k = ref.split(":")
        entity = scouts_line_entity(item, int(k))
        assert not any(isinstance(a, UnportedAbility) for a in abilities_of(entity))


@pytest.mark.parametrize(
    "ability_id",
    [
        MISSION_PIECES_ABILITY,
        SUBCOMMITTEE_OFFER_ABILITY,
        DESERT_RIDING_ABILITY,
        "worm.canis.abilities.AppStyle.Scouts.CorrinthCityRevealScoutsAbility",
    ],
)
def test_scouts_board_abilities_are_ported(ability_id: str) -> None:
    assert ability_id in PORTS


def test_scouts_space_overlays_resolve_without_unported_scouts_classes() -> None:
    board = Board(True, True, scouts=True, faction_spaces_combat=True)
    for space_id in SPACE_ARCHETYPES:
        for ability in abilities_of(space_entity(space_id, board)):
            if isinstance(ability, UnportedAbility):
                assert "AppStyle.Scouts" not in ability.app_class


# -- §2.1 profile extensions ----------------------------------------------------------


def test_uncapped_troop_value_drops_only_the_supply_cap() -> None:
    state = with_me(scouts_state(), **troops(garrison=12))  # an empty supply
    p = prof(state)
    assert p.troop_value(2, False) == 0.0  # the app's cap
    unit = _conftest.make_profile(with_me(scouts_state(), **troops(garrison=3)), ME)
    # Same garrison abundance needs the same garrison: compare with the
    # notional supply context instead of a real state.
    notional = Profile(OwnSupplyContext(p.ctx, 5), p.C, p.rng)
    assert notional.ctx.me.troops_supply == 5
    assert notional.ctx.me.troops_garrison == 12
    assert p.uncapped_troop_value(2) == notional.troop_value(2, False)
    assert p.uncapped_troop_value(2) > 0.0
    # With the troops in the supply the cap does not bind: identical prices.
    assert unit.uncapped_troop_value(2) == unit.troop_value(2, False)


def test_uncapped_value_is_the_unit_price_times_n() -> None:
    p = prof(with_me(scouts_state(), **troops(garrison=12)))
    one = p.uncapped_troop_value(1)
    two = p.uncapped_troop_value(2)
    assert two == one + (2.0 * one - one)  # Multiply("Amount", 2)


def _gate_profile(**methods: object) -> Profile:
    p = prof(gate=None)
    defaults: dict[str, object] = {
        "_can_deploy": True,
        "conflict_posture_bounds": (2.0, 8.0),
        "current_conflict_interest": Summer(5.0),
        "is_climax": False,
        "est_strength": IntSummer(10),
    }
    defaults.update(methods)
    return stub(p, **defaults)


@pytest.mark.parametrize(
    ("methods", "expected"),
    [
        ({"_can_deploy": False, "is_climax": True}, 0),
        ({"is_climax": True}, 100),
        ({"current_conflict_interest": Summer(9.0)}, 100),
        ({"current_conflict_interest": Summer(2.0)}, 0),  # not > lb
        ({"est_opponent_strength": IntSummer(16)}, 100),  # d = 6: not > 6
        ({"est_opponent_strength": IntSummer(17)}, 0),  # d = 7 > 6
        ({"est_opponent_strength": IntSummer(6)}, 100),  # exp = opp + 4
        ({"est_opponent_strength": IntSummer(5)}, 0),  # exp > opp + 4
    ],
)
def test_scouts_conflict_troops_gate(methods: dict[str, object], expected: int) -> None:
    """ShouldPlayTroopIntrigue minus its supply line, (6, 4) (§2.1)."""

    methods.setdefault("est_opponent_strength", IntSummer(10))
    p = _gate_profile(**methods)
    assert p.scouts_conflict_troops_gate() == expected


def test_conflict_troop_prices_follow_the_gate() -> None:
    p = prof(gate=100)
    P = Prices(p)
    assert p.conflict_troop_value(2) == P.Tr(2)
    assert p.parked_conflict_troop_value(2) == P.UTr(2)
    closed = prof(gate=0)
    assert closed.conflict_troop_value(2) == 0.0
    assert closed.parked_conflict_troop_value(2) == 0.0


@pytest.mark.parametrize(
    ("final", "climax", "delay", "zero"),
    [
        (False, False, 2, False),
        (True, True, 0, False),
        (True, True, 1, True),
        (False, True, 1, False),
        (False, True, 2, True),
    ],
)
def test_scouts_later(final: bool, climax: bool, delay: int, zero: bool) -> None:
    """later(v, d) (§2.1, D13): no discount; 0 when the game may end first."""

    p = stub(prof(), is_final_round=final, is_climax=climax)
    assert p.scouts_later(3.5, delay) == (0.0 if zero else 3.5)


def test_track_bonus_values_are_block_c() -> None:
    p = prof()
    P = Prices(p)
    assert p.track_bonus_value("emperor") == P.Spy
    assert p.track_bonus_value("spacing_guild") == P.Sol(3)
    assert p.track_bonus_value("bene_gesserit") == P.Int
    assert p.track_bonus_value("fremen") == P.Wat(1)
    assert p.any_faction_four_bonus_value() == max(
        p.track_bonus_value(f) for f in FACTIONS
    )


# -- §2.2 line values (§5 V column) ---------------------------------------------------


LineCase = tuple[str, int, Callable[[Prices], float]]
LINES: list[LineCase] = [
    # §5.1 subcommittees
    ("appropriations", 0, lambda P: P.Wat(1) + P.Disc),
    ("intelligence", 0, lambda P: P.Spy),
    ("readiness", 0, lambda P: P.Tr(1)),
    ("choam_coordination", 0, lambda P: P.K),
    ("growth_project", 0, lambda P: P.Spec(1)),
    ("oversight", 0, lambda P: P.Spi(1) + P.RSpy + P.Trash),
    ("investigations", 0, lambda P: P.Sol(-1) + P.Int),
    ("forecasting", 0, lambda P: P.Spi(-1) + P.Draw + P.Draw),
    ("choam_management", 0, lambda P: P.Spi(-1) + P.K + P.K),
    ("analytics", 0, lambda P: P.Sol(-1) + P.RV),
    ("relations", 0, lambda P: P.Spi(-2) + P.Gany),
    ("contingencies", 0, lambda P: P.TI + P.RA),
    ("leverage", 0, lambda P: P.Int + P.RSpy + P.RSpy + P.Gany),
    ("tleilaxu_relations", 0, lambda P: P.Spi(-3) + P.TV(2)),
    # §5.2 mission joins (gate open)
    ("security_detail", 0, lambda P: P.UTr(1)),
    ("choam_escort", 0, lambda P: P.Tr(1)),
    ("choam_escort", 1, lambda P: P.Spi(1) + P.Sol(1)),
    ("prison_planet", 0, lambda P: P.Spi(2) + P.Tr(-1)),
    ("fedaykin_assistance", 0, lambda P: P.Spi(-1) + P.UTr(2)),
    ("weirding_warfare", 0, lambda P: P.Sol(-2) + P.UTr(2)),
    ("send_for_aid", 0, lambda P: P.Wat(1) + P.Tr(-1) + P.UTr(1)),
    ("coordinate_with_the_emperor", 0, lambda P: P.Spec(-1) + P.Sol(2) + P.UTr(1)),
    ("tleilaxu_offering", 0, lambda P: P.Spec(2)),
    # §5.3 events
    ("private_stock", 0, lambda P: P.Spi(1)),
    ("private_stock", 1, lambda P: P.Draw),
    ("market_research", 0, lambda P: P.Spi(2) + P.RSpy),
    ("smoke_and_mirrors", 0, lambda P: P.Spy),
    ("smoke_and_mirrors", 1, lambda P: P.Sol(-1) + P.Int),
    ("rotating_doors", 0, lambda P: P.Int + P.TI + P.Draw),
    ("water_discipline", 0, lambda P: P.Wat(-1) + P.Trash + P.Draw),
    ("royal_delegation", 0, lambda P: P.Sol(-2) + P.G("emperor", 1)),
    ("guild_negotiation", 0, lambda P: P.Spi(-1) + P.G("spacing_guild", 1) + P.Disc),
    ("covert_assistance", 0, lambda P: P.G("bene_gesserit", 1) + P.RSpy),
    ("gift_of_water", 0, lambda P: P.Wat(-1) + P.G("fremen", 1)),
    ("share_intelligence", 0, lambda P: P.Sol(-1) + P.TI + P.Gany),
    ("crackdown", 0, lambda P: P.RSpy),
    ("crackdown", 1, lambda P: P.G("emperor", -1)),
    ("water_for_spice_smugglers", 0, lambda P: P.Wat(-1)),
    ("water_for_spice_smugglers", 1, lambda P: P.G("spacing_guild", -1)),
    ("bene_gesserit_treachery", 0, lambda P: P.Tr(-1)),
    ("bene_gesserit_treachery", 1, lambda P: P.G("bene_gesserit", -1)),
    ("funeral_rites", 1, lambda P: P.G("fremen", -1)),
    ("covert_operation", 0, lambda P: P.Spy),
    ("covert_operation", 1, lambda P: P.Sol(2)),
    ("covert_operation", 2, lambda P: P.Tr(3) + P.Disc),
    ("covert_operation_choam", 1, lambda P: P.K),
    ("rebuild_infrastructure", 0, lambda P: P.Spi(-1) - P.BWV),
    ("choam_bargain", 0, lambda P: P.Draw),
    ("choam_bargain", 1, lambda P: P.K),
    ("ingratiate", 0, lambda P: P.Spec(-1) + P.Gany),
    ("betrayal", 0, lambda P: P.G("bene_gesserit", -1) + P.TV(1)),
    ("new_innovations", 0, lambda P: P.Sol(-1) + P.RV),
    ("new_innovations", 1, lambda P: P.Spi(-1) + P.RV),
    ("offworld_operation", 0, lambda P: P.Sol(2)),
    ("offworld_operation", 1, lambda P: P.Spi(HELIX_SPICE.spice)),
    ("offworld_operation", 2, lambda P: P.TV(1)),
    ("offworld_operation", 3, lambda P: P.Int),
    # §5.4 auctions (first-place and second-place lines)
    ("highest_bidder_mid", 0, lambda P: P.Draw),
    ("highest_bidder_late", 0, lambda P: P.Draw + P.Draw),
    ("highest_bidder_late", 1, lambda P: P.Draw),
    ("competitive_study_mid", 0, lambda P: P.Spec(1) + P.RV),
    ("competitive_study_late", 1, lambda P: P.RV),
    ("spies_for_hire_mid", 0, lambda P: P.Spy),
    ("spies_for_hire_late", 0, lambda P: P.Int + P.Spy),
    ("choam_negotiations_late", 0, lambda P: P.Int + P.K),
    ("choam_negotiations_late", 1, lambda P: P.K),
    # §5.5 sales (gate open)
    ("unravel_the_future", 0, lambda P: P.Spi(-1) + P.Draw),
    ("unravel_the_future", 1, lambda P: P.Spi(-3) + P.Draw + P.Draw),
    ("imperium_connections", 0, lambda P: P.Sol(-2) + P.Spy),
    ("imperium_connections", 1, lambda P: P.Sol(-2) + P.Wat(1)),
    ("secrets_for_sale", 0, lambda P: P.Spi(-1) + P.Int),
    ("secrets_for_sale", 1, lambda P: P.Spi(-3) + 2 * P.Int),
    ("shadow_warfare", 0, lambda P: P.Spi(1) + P.RSpy + P.Tr(1)),
    ("shadow_warfare", 1, lambda P: P.Spi(2) + P.RSpy + P.RSpy + P.Tr(3)),
]


def _rich_state() -> GameState:
    """Seat 3 with some of everything: resources, garrison, a Spy, Influence."""

    state = with_me(
        scouts_state(),
        resources=replace(scouts_state().players[ME].resources, solari=6, spice=5),
        **troops(garrison=4),
    )
    me = state.players[ME]
    return with_me(
        state,
        influence=replace(me.influence, emperor=2, bene_gesserit=1),
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
        spies_supply=me.spies_supply - 1,
    )


@pytest.mark.parametrize(("item", "k", "expected"), LINES)
def test_line_values_follow_the_spec(
    item: str, k: int, expected: Callable[[Prices], float]
) -> None:
    p = prof(_rich_state(), gate=100)
    assert L(p, item, k) == close(expected(Prices(p)))


@pytest.mark.parametrize(
    ("item", "k", "expected"),
    [
        ("security_detail", 0, 0.0),
        ("weirding_warfare", 0, None),  # only Sol(-2) remains
        ("shadow_warfare", 0, None),
    ],
)
def test_conflict_troop_lines_close_with_the_gate(
    item: str, k: int, expected: float | None
) -> None:
    p = prof(_rich_state(), gate=0)
    P = Prices(p)
    closed = {
        "security_detail": 0.0,
        "weirding_warfare": P.Sol(-2),
        "shadow_warfare": P.Spi(1) + P.RSpy,
    }[item]
    assert L(p, item, k) == close(closed)
    if expected is not None:
        assert L(p, item, k) == expected


def test_political_equilibrium_line_is_the_least_negative_highest_loss() -> None:
    p = prof(_rich_state())
    # Emperor 2 is the only highest track.
    assert L(p, "political_equilibrium", 0) == Prices(p).G("emperor", -1)
    nothing = prof()  # every track at 0
    assert L(nothing, "political_equilibrium", 0) == 0.0


def test_moment_of_revelation_prices_prepare_the_way_to_hand() -> None:
    p = prof(_rich_state())
    P = Prices(p)
    ptw = card_entity("reserve:prepare_the_way")
    expected = P.Spi(-2) + p.acquire_value(ptw).sum + P.CDV
    assert L(p, "moment_of_revelation", 0) == close(expected)
    empty = with_state(
        _rich_state(),
        reserve_stacks=tuple(
            (cid, 0 if cid == "prepare_the_way" else n)
            for cid, n in _rich_state().reserve_stacks
        ),
    )
    q = prof(empty)
    assert L(q, "moment_of_revelation", 0) == Prices(q).Spi(-2)


def test_helix_spice_reads_the_genetic_marker() -> None:
    p = stub(prof(), **{})
    P = Prices(p)
    assert L(p, "offworld_operation", 1) == P.Spi(HELIX_SPICE.spice)
    marked = prof(with_me(scouts_state(), research_space="c4r2"))
    assert L(marked, "offworld_operation", 1) == Prices(marked).Spi(
        HELIX_SPICE.helix_spice
    )


def test_covert_operation_lowest_track_line() -> None:
    p = prof(_rich_state())
    P = Prices(p)
    # Spacing Guild and Fremen tie at 0: the first maximum of G(f, 1).
    lowest = [P.G("spacing_guild", 1), P.G("fremen", 1)]
    assert L(p, "covert_operation", 3) == max(lowest)


def test_line_troops_can_be_priced_uncapped() -> None:
    state = with_me(scouts_state(), **troops(garrison=12))
    p = prof(state)
    entity = line("choam_escort", 0)
    assert p.scouts_line_value(entity).sum == 0.0
    assert p.scouts_line_value(entity, uncapped_troops=True).sum == (
        p.uncapped_troop_value(1)
    )


# -- the forced hand trash (D5, plan §11.7) -------------------------------------------


def _hand_state(*hand: str) -> GameState:
    state = scouts_state()
    deck = tuple(c for c in state.imperium_deck if c not in hand)
    old = state.players[ME].hand
    state = with_state(state, imperium_deck=deck)
    me = state.players[ME]
    return with_me(state, hand=hand, discard_pile=(*me.discard_pile, *old))


def test_forced_trash_with_junk_is_the_trash_card_value() -> None:
    p = prof()  # the starting hand holds Dagger (TrashValue 1.0)
    assert L(p, "funeral_rites", 0) == p.trash_card_value()
    assert L(p, "termination_request", 0) == close(
        p.specimen_value(1) + p.trash_card_value()
    )


def test_forced_trash_without_junk_costs_the_least_acquire_value() -> None:
    hand = ("imperium:subversive_advisor:0", "imperium:maker_keeper:1")
    p = prof(_hand_state(*hand))
    values = {c: p.acquire_value(card_entity(c)).sum for c in hand}
    assert L(p, "funeral_rites", 0) == -min(values.values())
    ability = abilities_of(line("funeral_rites", 0))[0]
    request = Request(
        infos=(TargetInfo(entities=tuple(card_entity(c, ME) for c in hand)),)
    )
    answer = ability.evaluate(p, request)
    least = min(hand, key=values.__getitem__)
    assert answer.response == ((least,),)
    assert answer.value == -values[least]


def test_forced_trash_evaluator_trashes_junk_first() -> None:
    p = prof()
    hand = p.ctx.hand
    ability = abilities_of(line("funeral_rites", 0))[0]
    request = Request(
        infos=(TargetInfo(entities=tuple(card_entity(c, ME) for c in hand)),)
    )
    answer = ability.evaluate(p, request)
    assert answer.response is not None
    chosen = card_entity(str(answer.response[0][0]))
    assert chosen.float_attr("TrashValue") > 0.0


# -- §2.3 line ability answers (§3.2) --------------------------------------------------


def test_recall_spy_cost_answers_the_worst_spy_plus_100() -> None:
    p = prof(_rich_state())
    spies = (spy_entity("emperor-sardaukar-dutiful-service", ME),)
    spy, value = p.recall_spy(list(spies))
    assert spy is not None
    ability = abilities_of(line("crackdown", 0))[0]
    answer = ability.evaluate(p, Request(infos=(TargetInfo(entities=spies),)))
    assert answer.response == ((spy.ref,),)
    assert answer.value == value + 100.0


def test_discard_cost_answers_the_first_of_the_discard_order() -> None:
    p = prof()
    cards = tuple(card_entity(c, ME) for c in p.ctx.hand)
    order = p.discard_order(cards, False)
    ability = abilities_of(line("appropriations", 0))[0]
    answer = ability.evaluate(p, Request(infos=(TargetInfo(entities=cards),)))
    assert answer.response == ((order[0].ref,),)
    assert answer.value == 1.0


def test_lose_highest_influence_is_least_loss() -> None:
    p = prof(
        with_me(
            scouts_state(),
            influence=replace(
                scouts_state().players[ME].influence, emperor=2, fremen=2
            ),
        )
    )
    tracks = (track_entity("emperor"), track_entity("fremen"))
    ability = abilities_of(line("political_equilibrium", 0))[0]
    answer = ability.evaluate(p, Request(infos=(TargetInfo(entities=tracks),)))
    losses = {
        f: p.gain_influence_value(f, -1, -1, False).sum for f in ("emperor", "fremen")
    }
    assert answer.response is not None
    picked = str(answer.response[0][0])
    assert losses[picked] == max(losses.values())
    assert sc.lose_influence_answer(p, ["fremen"]).response == (("fremen",),)


def test_gain_lowest_influence_uses_the_gain_picker() -> None:
    p = prof(_rich_state())
    tracks = (track_entity("spacing_guild"), track_entity("fremen"))
    ability = abilities_of(line("covert_operation", 3))[0]
    answer = ability.evaluate(p, Request(infos=(TargetInfo(entities=tracks),)))
    values = [p.gain_influence_value(t.ref, 1, -1, False).sum + 100.0 for t in tracks]
    best = tracks[0] if values[0] >= values[1] else tracks[1]
    assert answer.response == ((best.ref,),)


def test_line_abilities_run_immediately_and_are_never_post_action_keys() -> None:
    p = prof()
    for short in SCOUTS_LINE_ARCHETYPES:
        item, k = short.split(":")
        for ability in abilities_of(line(item, int(k))):
            if type(ability).__module__.endswith("abilities.scouts"):
                assert isinstance(ability, DeferredAbility)
                assert ability.can_run_immediately(p)
                assert ability.timing == 0


def test_line_top_up_takes_the_largest_count() -> None:
    assert sc.line_top_up_answer((0, 1, 2)).response == ((2,),)


# -- §4.1 mission pieces on spaces -----------------------------------------------------


def _space(space_id: str, state: GameState | None = None) -> Entity:
    return space_entity(space_id, Board.of(SCOUTS if state is None else state.config))


def _pieces(space_id: str) -> sc.MissionPiecesSpaceAbility:
    for ability in abilities_of(_space(space_id)):
        if isinstance(ability, sc.MissionPiecesSpaceAbility):
            return ability
    raise AssertionError("no mission pieces ability")


def test_mission_pieces_parked_troops() -> None:
    state = with_parked(
        scouts_state(),
        (
            ("security_detail", ME, "deliver_supplies", 1),
            ("fedaykin_assistance", ME, "desert_tactics", 2),
        ),
        **troops(garrison=3, parked=3),
    )
    p = prof(state, gate=100)
    assert _pieces("deliver_supplies").value_for_player(
        p
    ).sum == p.uncapped_troop_value(1)
    assert _pieces("desert_tactics").value_for_player(p).sum == p.uncapped_troop_value(
        2
    )
    closed = prof(state, gate=0)
    assert _pieces("deliver_supplies").value_for_player(closed).sum == 0.0
    assert _pieces("desert_tactics").value_for_player(closed).sum == (
        closed.uncapped_troop_value(2)
    )
    # Another seat's troops are not P's to collect.
    other = _conftest.make_profile(state, 0)
    assert _pieces("deliver_supplies").value_for_player(other).sum == 0.0


def test_mission_pieces_imperial_reserve_takes_the_better_good() -> None:
    state = with_state(
        scouts_state(),
        scouts_goods=(
            ("imperial_reserve", "imperial_privilege", "spice", 1, -1),
            ("imperial_reserve", "imperial_privilege", "solari", 2, -1),
        ),
    )
    p = prof(state)
    P = Prices(p)
    ability = _pieces("imperial_privilege")
    assert ability.value_for_player(p).sum == max(P.Spi(1), P.Sol(2))
    assert ability.selection_mode(p) == SelectionMode.EXPLICIT
    answer = ability.evaluate(p, Request())
    best = "spice" if P.Spi(1) >= P.Sol(2) else "solari"  # spice on ties
    assert answer.response == ((best,),)


def test_mission_pieces_prison_planet_spice_but_not_the_marker() -> None:
    state = with_state(
        scouts_state(),
        scouts_goods=(
            ("prison_planet", "sardaukar", "marker", 1, ME),
            ("prison_planet", "sardaukar", "spice", 2, ME),
        ),
    )
    p = prof(state)
    ability = _pieces("sardaukar")
    assert ability.value_for_player(p).sum == Prices(p).Spi(2)
    assert ability.selection_mode(p) == SelectionMode.IMPLICIT
    assert ability.evaluate(p, Request()).response == (("",),)
    assert ability.meets_cost(p)
    other = _conftest.make_profile(state, 0)
    assert ability.value_for_player(other).sum == 0.0


def test_mission_pieces_face_down_cards_are_priced_by_kind() -> None:
    state = scouts_state()
    contracts = state.contract_bank[:1]
    intrigues = state.intrigue_deck[:1]
    state = with_state(
        state,
        contract_bank=state.contract_bank[1:],
        intrigue_deck=state.intrigue_deck[1:],
        scouts_goods_cards=(
            ("choam_research", "research_station", contracts[0]),
            ("emperors_schemes", "sardaukar", intrigues[0]),
        ),
    )
    p = prof(state)
    assert _pieces("research_station").value_for_player(p).sum == (
        p.gain_contract_value().sum
    )
    assert _pieces("sardaukar").value_for_player(p).sum == p.intrigue_value()
    assert _pieces("arrakeen").value_for_player(p).sum == 0.0


def test_mission_pieces_join_the_space_value() -> None:
    state = with_state(
        scouts_state(),
        scouts_goods=(("imperial_reserve", "imperial_privilege", "solari", 2, -1),),
    )
    p = prof(state)
    space = _space("imperial_privilege")
    without = space_entity("imperial_privilege", Board(True, True))
    assert p.space_value_for_player(space).sum == close(
        p.space_value_for_player(without).sum + Prices(p).Sol(2)
    )


# -- §4.2 Desert Riding ----------------------------------------------------------------


def _desert_riding(p: Profile) -> sc.DesertRidingAbility:
    for ability in abilities_of(_space("hagga_basin")):
        if isinstance(ability, sc.DesertRidingAbility):
            return ability
    raise AssertionError("no Desert Riding ability")


def test_desert_riding_is_the_hooks_option_for_a_hookless_seat() -> None:
    token = with_state(
        scouts_state(),
        scouts_goods=(("desert_riding", "hagga_basin", "maker_hooks", 1, -1),),
    )
    for hooks_value, wins in ((50.0, True), (0.0, False)):
        p = stub(prof(token), maker_hooks_value=hooks_value)
        ability = _desert_riding(p)
        spice = p.spice_value(2)
        assert ability.value_for_player(p).sum == close(max(spice, hooks_value))
        answer = ability.evaluate(p, Request())
        assert answer.response == (((2,),) if wins else ((0,),))
    # Spice wins a tie.
    p = prof(token)
    stub(p, maker_hooks_value=p.spice_value(2))
    assert _desert_riding(p).evaluate(p, Request()).response == ((0,),)


def test_desert_riding_without_the_token_is_hagga_basin() -> None:
    p = stub(prof(), maker_hooks_value=50.0)
    ability = _desert_riding(p)
    assert ability.value_for_player(p).sum == p.spice_value(2)
    assert ability.evaluate(p, Request()).response == ((0,),)


# -- §4.3, §4.4 Valued Informants and CHOAM Escort -------------------------------------


def test_valued_informants_goods_join_the_post_value() -> None:
    post = "spacing-guild-heighliner-deliver-supplies"
    plain = prof()
    goods = prof(
        with_state(
            scouts_state(),
            scouts_goods=(("urban_surveillance", f"post:{post}", "solari", 1, -1),),
        )
    )
    entity = post_entity(post, ME)
    assert goods.post_value(entity) == close(
        plain.post_value(entity) + goods.solari_value(1)
    )


def test_choam_escort_goods_join_the_contract_completion() -> None:
    state = scouts_state()
    contract = state.face_up_contract_ids[0]
    state = with_state(state, face_up_contract_ids=state.face_up_contract_ids[1:])
    state = with_me(state, active_contract_ids=(contract,))
    loaded = with_state(
        state,
        scouts_goods=(
            ("choam_escort", f"contract:{contract}", "solari", 1, ME),
            ("choam_escort", f"contract:{contract}", "spice", 1, ME),
        ),
    )
    entity = contract_entity(contract, ME)
    ability = next(a for a in abilities_of(entity) if isinstance(a, ContractAbility))
    p = prof(state)
    q = prof(loaded)
    extra = q.solari_value(1) + q.spice_value(1)
    assert isinstance(ability, ContractAbility)
    assert ability.resource_value(q).sum == close(ability.resource_value(p).sum + extra)
    other = _conftest.make_profile(loaded, 0)
    assert other.choam_escort_contract_value(contract).sum == 0.0


# -- §4.5 the subcommittee opportunity -------------------------------------------------


def test_subcommittee_opportunity_is_the_best_joinable_line() -> None:
    p = prof()
    joinable = p.ctx.joinable_subcommittees("high_council")
    assert joinable  # Intelligence and Readiness need nothing
    best = max(L(p, s, 0) for s in joinable)
    assert p.subcommittee_opportunity("high_council") == max(0.0, best)
    seated = prof(with_me(scouts_state(), high_council=True))
    assert seated.subcommittee_opportunity("high_council") == 0.0


def test_subcommittee_offer_joins_the_high_council_value() -> None:
    p = prof()
    offer = next(
        a
        for a in abilities_of(_space("high_council"))
        if isinstance(a, sc.SubcommitteeOfferAbility)
    )
    assert offer.value_for_player(p).sum == p.subcommittee_opportunity("high_council")
    assert offer.selection_mode(p) == SelectionMode.OPTIONAL
    assert not offer.can_run_immediately(p)
    assert not offer.meets_cost(p)  # no offer is pending outside the seat's turn
    assert offer.evaluate(p, Request()).response is None
    seated = prof(with_me(scouts_state(), high_council=True))
    assert offer.value_for_player(seated).sum == 0.0


def test_corrinth_city_reveal_adds_the_opportunity_to_the_seat() -> None:
    """E adds ``subcommittee_opportunity("")`` to option 1 (§2.3, D24): here
    it turns the answer from the 5 Solari (7.15) to the seat (-7.15 + 10 +
    5); V is the base V."""

    state = with_me(
        scouts_state(),
        resources=replace(scouts_state().players[ME].resources, solari=7),
    )
    p = stub(prof(state), subcommittee_opportunity=5.0, high_council_value=10.0)
    card = card_entity("imperium:corrinth_city:0", ME)
    plain = CorrinthCityRevealAbility(card)
    scouts = sc.CorrinthCityRevealScoutsAbility(card)
    base = plain.evaluate(p, Request())
    assert base.response == ((0,),)
    assert base.value == p.solari_value(5)
    with_offer = scouts.evaluate(p, Request())
    assert with_offer.response == ((1,),)
    assert with_offer.value == p.solari_value(-5) + 10.0 + 5.0
    assert scouts.value_for_player(p).sum == plain.value_for_player(p).sum
    seated = stub(
        prof(with_me(state, high_council=True)),
        subcommittee_opportunity=5.0,
        high_council_value=10.0,
    )
    assert scouts.evaluate(seated, Request()) == plain.evaluate(seated, Request())


# -- §4.6 Immortality goods ------------------------------------------------------------


def test_sponsored_research_spice_on_the_first_marker_spaces() -> None:
    plain = prof()
    state = with_state(
        scouts_state(), scouts_goods=(("sponsored_research", "helix", "spice", 2, -1),)
    )
    p = prof(state)
    for space_id in ("c4r2", "c4r4", "c4r6"):
        assert p.research_space_value(space_id).sum == close(
            plain.research_space_value(space_id).sum + p.spice_value(2)
        )
    assert p.research_space_value("c3r3").sum == plain.research_space_value("c3r3").sum
    marked = prof(with_me(state, research_space="c4r2"))
    assert marked.sponsored_research_value("c5r1").sum == 0.0


def test_back_room_deal_solari_join_reclaimed_forces() -> None:
    state = with_state(
        scouts_state(),
        scouts_goods=(("back_room_deal", "reclaimed_forces", "solari", 2, -1),),
    )
    plain = prof()
    p = prof(state)
    rf = card_entity(RECLAIMED_FORCES_REF, ME)
    ability = ReclaimedForcesAcquireAbility(rf)
    a = ability.evaluate(plain, Request())
    b = ability.evaluate(p, Request())
    acquire = p.acquire_value(rf).sum
    assert acquire > 0.0  # no Reveal-turn clamp in play here
    assert a.value == acquire
    assert p.back_room_deal_value() == p.solari_value(2)
    assert b.value == acquire + p.solari_value(2)
    assert b.response == a.response


def test_tleilaxu_offering_specimens_when_the_token_reaches_the_third_space() -> None:
    state = with_parked(
        scouts_state(),
        (("tleilaxu_offering", ME, "tleilaxu_track", 2),),
        **troops(garrison=3, parked=2),
        tleilaxu_space=2,
    )
    p = prof(state)
    plain = prof(with_me(scouts_state(), tleilaxu_space=2))
    assert p.tleilaxu_offering_specimens(1) == 2
    assert p.tleilaxu_value(1).sum == close(
        plain.tleilaxu_value(1).sum + p.specimen_value(2)
    )
    assert p.tleilaxu_offering_specimens(0) == 0
    beyond = prof(with_state(with_me(state, tleilaxu_space=3)))
    assert beyond.tleilaxu_offering_specimens(1) == 0


# -- §4.7 round modifiers --------------------------------------------------------------


def test_friends_everywhere_prices_the_best_track_bonus() -> None:
    state = with_me(
        scouts_state(),
        influence=replace(scouts_state().players[ME].influence, fremen=3),
    )
    plain = prof(state)
    friends = prof(with_state(state, scouts_round_modifier="any_faction_four_bonus"))
    base = plain.gain_influence_value("fremen", 1).sum
    expected = base - plain.water_value(1) + friends.any_faction_four_bonus_value()
    assert friends.gain_influence_value("fremen", 1).sum == close(expected)


def test_market_opening_discounts_the_reserve_spice_must_flow() -> None:
    opening = with_state(
        scouts_state(), scouts_round_modifier="spice_must_flow_discount"
    )
    p = prof(opening)
    tsmf = next(c for c in p._row_cards() if c.ref == "reserve:the_spice_must_flow")
    assert tsmf.int_attr("PersuasionCost") == 7
    assert tsmf.short == "ImperiumArchetypes.Uprising.TheSpiceMustFlowUP"
    used = prof(with_state(opening, scouts_discount_used=True))
    tsmf = next(c for c in used._row_cards() if c.ref == "reserve:the_spice_must_flow")
    assert tsmf.int_attr("PersuasionCost") == 9
    ptw = next(c for c in p._row_cards() if c.ref == "reserve:prepare_the_way")
    assert ptw.int_attr("PersuasionCost") == card_entity(ptw.ref).int_attr(
        "PersuasionCost"
    )


def test_eyes_on_arrakis_overlay_is_read_from_the_public_modifier() -> None:
    p = prof(
        with_state(scouts_state(), scouts_round_modifier="faction_spaces_are_combat")
    )
    assert p.ctx.board.faction_spaces_combat
    space = space_entity("secrets", p.ctx.board)
    assert space.attr("CombatSpace") is True
    assert any(type(a).__name__ == "DeployUnitsAbility" for a in abilities_of(space))


# -- §2.4 evaluators -------------------------------------------------------------------


def test_scouts_choice_passable_passes_without_a_positive_line() -> None:
    p = stub(prof(), scouts_item_line_value=lambda item, k: -1.0)
    answer = sc.ScoutsChoiceEvaluator.evaluate(
        p, "royal_delegation", (0,), passable=True
    )
    assert answer.response is None
    p = stub(prof(), scouts_item_line_value=lambda item, k: 2.0)
    answer = sc.ScoutsChoiceEvaluator.evaluate(
        p, "royal_delegation", (0,), passable=True
    )
    assert answer.response == ((0,),)


def test_scouts_choice_mandatory_takes_the_best_positive_line() -> None:
    values = {0: 1.0, 1: 3.0}
    p = stub(prof(), scouts_item_line_value=lambda item, k: values[k])
    answer = sc.ScoutsChoiceEvaluator.evaluate(
        p, "private_stock", (0, 1), passable=False
    )
    assert answer.response == ((1,),)


def test_influence_reduction_is_least_loss() -> None:
    values = {0: -3.0, 1: -1.0}
    for seed in range(8):
        p = _conftest.make_profile(scouts_state(), ME, rng_seed=seed)
        stub(p, scouts_item_line_value=lambda item, k: values[k])
        answer = sc.ScoutsChoiceEvaluator.evaluate(
            p, "crackdown", (0, 1), passable=False
        )
        assert answer.response == ((1,),)


def test_other_mandatory_items_fall_back_to_a_random_line() -> None:
    picks = set()
    for seed in range(24):
        p = _conftest.make_profile(scouts_state(), ME, rng_seed=seed)
        stub(p, scouts_item_line_value=lambda item, k: -1.0)
        answer = sc.ScoutsChoiceEvaluator.evaluate(
            p, "smoke_and_mirrors", (0, 1), passable=False
        )
        assert answer.response is not None
        picks.add(answer.response[0][0])
    assert picks == {0, 1}


def test_subcommittee_evaluator() -> None:
    values = {"intelligence": 2.0, "readiness": 5.0}
    p = stub(prof(), scouts_item_line_value=lambda item, k: values[item])
    answer = sc.SubcommitteeEvaluator.evaluate(p, ("intelligence", "readiness"))
    assert answer.response == (("readiness",),)
    p = stub(prof(), scouts_item_line_value=lambda item, k: 0.0)
    assert sc.SubcommitteeEvaluator.evaluate(p, ("intelligence",)).response is None


def test_mission_join_evaluator_targets_and_lines() -> None:
    assert sc.mission_join_line("choam_escort", "recruit") == 0
    assert sc.mission_join_line("choam_escort", "contract:x") == 1
    assert sc.mission_join_line("security_detail", "") == 0
    p = prof(_rich_state(), gate=100)
    value = L(p, "fedaykin_assistance", 0)  # Spi(-1) + UTr(2) = 0.25 here
    assert value > 0.0
    answer = sc.MissionJoinEvaluator.evaluate(p, "fedaykin_assistance", ("",))
    assert answer.response == (("scouts_join_mission", ""),)
    assert answer.value == value
    closed = prof(_rich_state(), gate=0)
    # Weirding Warfare with the gate closed is only its Solari cost.
    answer = sc.MissionJoinEvaluator.evaluate(closed, "weirding_warfare", ("",))
    assert answer.response is None


def test_choam_escort_contract_target_is_random_among_equal_lines() -> None:
    """D45: every Contract target is the same line; ``mc`` picks at random."""

    picks = set()
    for seed in range(16):
        p = _conftest.make_profile(_rich_state(), ME, rng_seed=seed)
        stub(p, scouts_conflict_troops_gate=100)
        answer = sc.MissionJoinEvaluator.evaluate(
            p, "choam_escort", ("contract:a", "contract:b")
        )
        assert answer.response is not None
        picks.add(answer.response[0])
    assert picks == {
        ("scouts_join_mission", "contract:a"),
        ("scouts_join_mission", "contract:b"),
    }


def _no_supply_state() -> GameState:
    return with_me(
        scouts_state(),
        troops_garrison=3,
        troops_conflict=0,
        troops_supply=0,
        specimens=9,
        troops_parked=0,
    )


def test_mission_join_top_up_prices_the_specimens() -> None:
    """D25: the troop way at ``J(line, troops UTr) + Spec(-short)``; here
    ``UTr(1) + Spec(-1)`` is exactly 0, so the seat declines."""

    p = prof(_no_supply_state(), gate=100)
    assert p.uncapped_troop_value(1) + p.specimen_value(-1) == 0.0
    answer = sc.MissionJoinEvaluator.evaluate(p, "choam_escort", (), top_up=1)
    assert answer.response is None
    cheap = stub(prof(_no_supply_state()), specimen_value=lambda n: 0.5 * n)
    answer = sc.MissionJoinEvaluator.evaluate(cheap, "choam_escort", (), top_up=1)
    assert answer.response == (("scouts_return_specimens", 1),)
    assert answer.value == cheap.uncapped_troop_value(1) - 0.5


def test_secret_pick_delays_and_cost_lines() -> None:
    values = {0: 1.0, 1: 2.0, 2: -5.0, 3: 3.0}
    p = stub(prof(), scouts_item_line_value=lambda item, k: values[k])
    answer = sc.SecretPickEvaluator.evaluate(p, "covert_operation", (0, 1, 2, 3))
    assert answer.response == ((3,),)
    # In the climax a two-round pick is worth 0 (D13).
    stub(p, is_climax=True, is_final_round=False)
    answer = sc.SecretPickEvaluator.evaluate(p, "covert_operation", (0, 1, 2, 3))
    assert answer.response == ((1,),)
    # Final round: every pick 0, forced -> DefaultRandomChoice (D40).
    stub(p, is_final_round=True)
    answer = sc.SecretPickEvaluator.evaluate(p, "covert_operation", (0, 1, 2, 3))
    assert answer.response is not None
    assert answer.response[0][0] in (0, 1, 2, 3)


@pytest.mark.parametrize(
    ("worth", "cap", "bid"), [(2.5, 20, 1), (5.0, 20, 3), (5.0, 2, 2)]
)
def test_sealed_bid_is_the_largest_surplus_bid(
    worth: float, cap: int, bid: int
) -> None:
    """D19: ``b* = max{b in [1, cap] : V + Sol(-b) > 0}`` (Sol(1) = 1.43 here)."""

    p = stub(prof(), scouts_item_line_value=lambda item, k: worth)
    assert p.solari_value(1) == pytest.approx(1.43)
    assert sc.SealedBidEvaluator.best_bid(p, "highest_bidder_mid", cap) == bid
    answer = sc.SealedBidEvaluator.evaluate(p, "highest_bidder_mid", cap)
    assert answer.response == (("scouts_bid", bid),)


def test_sealed_bid_without_surplus_confirms_zero() -> None:
    p = stub(prof(), scouts_item_line_value=lambda item, k: 1.0)
    assert sc.SealedBidEvaluator.best_bid(p, "highest_bidder_mid", 20) == 0
    answer = sc.SealedBidEvaluator.evaluate(p, "highest_bidder_mid", 20)
    assert answer.response == (("confirm_scouts_bid",),)
    assert sc.SealedBidEvaluator.best_bid(p, "highest_bidder_mid", 0) == 0


def test_bid_confirms_once_the_bid_stands() -> None:
    p = prof()
    setattr(p.ctx, "own_scouts_bid", lambda: 3)  # noqa: B010 (the private bid)
    assert sc.bid_answer(p, 3, "x").response == (("confirm_scouts_bid",),)
    assert sc.bid_answer(p, 2, "x").response == (("scouts_bid", 2),)


def test_mercenaries_bid_value() -> None:
    state = with_me(
        scouts_state(),
        troops_supply=1,
        troops_garrison=3,
        specimens=8,
        troops_conflict=0,
        troops_parked=0,
    )
    p = prof(state, gate=100)
    for bid in (1, 2, 3):
        expected = p.uncapped_troop_value(bid) + p.spice_value(-bid)
        if bid > 1:
            expected += p.specimen_value(-(bid - 1))
        assert sc.MercenariesBidEvaluator.bid_value(p, bid) == close(expected)
    best = max(
        (b for b in (1, 2, 3) if sc.MercenariesBidEvaluator.bid_value(p, b) > 0.0),
        default=0,
    )
    assert sc.MercenariesBidEvaluator.best_bid(p, 3) == best
    closed = prof(state, gate=0)
    assert sc.MercenariesBidEvaluator.best_bid(closed, 3) == 0


def test_mercenaries_retreat_uses_get_troops_to_retreat() -> None:
    p = stub(prof(), troops_to_retreat=5)
    assert sc.MercenariesRetreatEvaluator.evaluate(p, 2).response == ((2,),)
    p = stub(prof(), troops_to_retreat=1)
    assert sc.MercenariesRetreatEvaluator.evaluate(p, 3).response == ((1,),)


def _market_state() -> GameState:
    state = scouts_state()
    cards = state.imperium_deck[:2]
    state = with_state(
        state, imperium_deck=state.imperium_deck[2:], scouts_market_cards=cards
    )
    return with_me(state, resources=replace(state.players[ME].resources, spice=6))


def test_critical_moment_call_is_the_largest_amount_under_the_reservation() -> None:
    """D22: V = 6.405 (Subversive Advisor to hand), Spi(-1) = -1: the
    reservation is 6; with 6 already called the largest legal amount <= 6 is
    5."""

    p = prof(_market_state())
    worth = max(
        p.acquire_to_hand_value(card_entity(c)) for c in p.ctx.scouts_market_cards
    )
    assert worth == pytest.approx(6.405)
    answer = sc.CriticalMomentCallEvaluator.evaluate(p, (0, 1, 2, 3, 4, 5, 6))
    assert answer.response == ((6,),)
    answer = sc.CriticalMomentCallEvaluator.evaluate(p, (0, 1, 2, 3, 4, 5))
    assert answer.response == ((5,),)
    poor = stub(prof(_market_state()), acquire_to_hand_value=0.5)
    assert sc.CriticalMomentCallEvaluator.evaluate(poor, (0, 1, 2)).response == ((0,),)


def test_critical_moment_take() -> None:
    """Values 4.3 and 6.405: first place takes slot 1; second place buys it
    iff ``6.405 + Spi(-amount) > 0``."""

    p = prof(_market_state())
    assert sc.CriticalMomentTakeEvaluator.evaluate(p, (0, 1), 3, 0).response == ((1,),)
    assert sc.CriticalMomentTakeEvaluator.evaluate(p, (0, 1), 6, 1).response == ((1,),)
    assert sc.CriticalMomentTakeEvaluator.evaluate(p, (0, 1), 7, 1).response is None
    nothing = stub(prof(_market_state()), acquire_to_hand_value=-1.0)
    first = sc.CriticalMomentTakeEvaluator.evaluate(nothing, (0, 1), 3, 0)
    assert first.response in (((0,),), ((1,),))  # forced: DefaultRandomChoice
    assert (
        sc.CriticalMomentTakeEvaluator.evaluate(nothing, (0, 1), 0, 1).response is None
    )


def test_four_bonus_takes_the_best_track_bonus() -> None:
    p = prof()
    answer = sc.FourBonusEvaluator.evaluate(p, FACTIONS)
    values = {f: p.track_bonus_value(f) for f in FACTIONS}
    assert answer.response is not None
    assert values[str(answer.response[0][0])] == max(values.values())


# -- §6 accessors and the base-game gates ----------------------------------------------


def test_scouts_accessors_read_the_public_view() -> None:
    state = scouts_state()
    p = prof(state)
    assert p.ctx.scouts
    assert p.ctx.scouts_subcommittees == state.scouts_subcommittees
    assert p.ctx.own_scouts_bid() == -1
    assert p.ctx.desert_riding_token() is None
    hidden = with_state(
        state,
        intrigue_deck=state.intrigue_deck[2:],
        scouts_goods_cards=(
            ("emperors_schemes", "sardaukar", state.intrigue_deck[0]),
            ("emperors_schemes", "sardaukar", state.intrigue_deck[1]),
        ),
    )
    assert prof(hidden).ctx.scouts_board_card_counts == (
        ("emperors_schemes", "sardaukar", 2),
    )


def test_games_without_scouts_read_no_scouts_term() -> None:
    p = _conftest.make_profile(base_state(), ME)
    assert not p.ctx.scouts
    assert not p.friends_everywhere_active()
    board = p.ctx.board
    assert not board.scouts and not board.faction_spaces_combat
    for space_id in SPACE_ARCHETYPES:
        ids = space_entity(space_id, board).ability_ids
        assert not any("AppStyle.Scouts" in i for i in ids)
    tsmf = next(c for c in p._row_cards() if c.ref == "reserve:the_spice_must_flow")
    assert tsmf.int_attr("PersuasionCost") == 9


def test_kinds_and_entities() -> None:
    entity = line("readiness", 0)
    assert entity.kind is Kind.SCOUTS
    assert entity.ref == "readiness:0"
    assert entity.attr("EntityType") == "ScoutsLine"
    assert Attr.TROOPS.value == "Troops"


# -- honesty (§6, plan §4.8): hidden Scouts state is never read -----------------------


def _hidden(card_pick: int, bids: tuple[tuple[int, int, bool], ...]) -> GameState:
    """The face-down mission cards and the other seats' sealed bids and
    secret picks dealt one way or another; seat 3's own bid (2) and pick
    stay put, so seat 3's view is the same."""

    state = scouts_state()
    contract = state.contract_bank[card_pick]
    intrigue = state.intrigue_deck[card_pick]
    return with_state(
        state,
        contract_bank=tuple(c for c in state.contract_bank if c != contract),
        intrigue_deck=tuple(c for c in state.intrigue_deck if c != intrigue),
        scouts_goods_cards=(
            ("choam_research", "research_station", contract),
            ("emperors_schemes", "sardaukar", intrigue),
        ),
        scouts_bids=(*bids, (ME, 2, False)),
        scouts_secret_picks=(
            (1, "covert_operation_choam", 0, card_pick),
            (1, "covert_operation_choam", ME, 3),
        ),
    )


def test_scouts_values_ignore_hidden_scouts_state() -> None:
    """§6: the identities of the face-down mission cards and the other seats'
    sealed bids and secret picks are never read (only the view's per-location
    card counts and the seat's own bid): re-dealing them changes nothing."""

    one = _hidden(0, ((0, 9, True), (1, 0, False)))
    two = _hidden(1, ((0, 1, False), (2, 7, True)))
    for state in (one, two):
        assert prof(state).ctx.own_scouts_bid() == 2

    def answers(state: GameState) -> tuple[object, ...]:
        p = _conftest.make_profile(state, ME, rng_seed=4)
        return (
            _pieces("research_station").value_for_player(p).sum,
            _pieces("sardaukar").value_for_player(p).sum,
            _pieces("research_station").meets_cost(p),
            p.ctx.scouts_board_card_counts,
            sc.SealedBidEvaluator.evaluate(p, "highest_bidder_mid", 6).response,
            sc.SecretPickEvaluator.evaluate(p, "offworld_operation", (0, 1, 2, 3)),
        )

    assert answers(one) == answers(two)


# -- real engine frames: the answers name legal actions -------------------------------


def _first_with(action_id: str, count: int, seed: int) -> GameState:
    """The first state of a heuristic Scouts game (``SCOUTS``) where the
    deciding seat has ``count`` or more ``action_id`` actions."""

    def offered(state: GameState, seat: int) -> bool:
        legal = _conftest.ENGINE.legal_actions(state, seat)
        return sum(1 for a in legal if a.action_id == action_id) >= count

    return _conftest.play_until(offered, config=SCOUTS, seed=seed)


def _legal(state: GameState, action_id: str) -> list[DomainAction]:
    return [
        a
        for a in _conftest.ENGINE.legal_actions(state, owner(state))
        if a.action_id == action_id
    ]


def test_imperial_reserve_collect_in_a_real_frame() -> None:
    """§3.5 (D26): both goods wait, so the visit offers ``spice`` and
    ``solari``; the ability is Explicit, its Cost holds, and its answer is the
    first strict best of ``Spi(1)``, ``Sol(2)`` in that order."""

    state = _first_with("scouts_collect_mission", 2, 3)
    seat = owner(state)
    choices = {
        dict(a.arguments)["choice"] for a in _legal(state, "scouts_collect_mission")
    }
    assert choices == {"spice", "solari"}
    p = _conftest.make_profile(state, seat)
    ability = _pieces("imperial_privilege")
    assert ability.meets_cost(p)
    assert ability.selection_mode(p) == SelectionMode.EXPLICIT
    spice, solari = p.spice_value(1), p.solari_value(2)
    best = "spice" if spice >= solari else "solari"
    assert ability.evaluate(p, Request()).response == ((best,),)


def test_subcommittee_offer_in_a_real_turn_frame() -> None:
    """§3.3 (D23): with ``choose_subcommittee`` legal the offer's Cost holds;
    its answer is ``mc`` over the joinable lines (the best, or a decline when
    none is worth more than 0), and a chosen id is then a legal join. The
    seat now holds the council seat, so the space's V is 0."""

    state = _first_with("choose_subcommittee", 1, 3)
    seat = owner(state)
    p = _conftest.make_profile(state, seat)
    offer = next(
        a
        for a in abilities_of(_space("high_council"))
        if isinstance(a, sc.SubcommitteeOfferAbility)
    )
    assert offer.meets_cost(p)
    exclude = p.ctx.pending_subcommittee_exclude()
    assert exclude is not None
    joinable = p.ctx.joinable_subcommittees(exclude)
    values = {s: p.scouts_item_line_value(s, 0) for s in joinable}
    answer = offer.evaluate(p, Request())
    if max(values.values()) > 0.0:
        assert answer.response is not None
        chosen = str(answer.response[0][0])
        assert values[chosen] == max(values.values())
        (choose,) = _legal(state, "choose_subcommittee")
        frame = _conftest.ENGINE.apply(state, choose).state
        joins = {
            dict(a.arguments)["subcommittee_id"]
            for a in _legal(frame, "join_subcommittee")
        }
        assert chosen in joins
    else:
        assert answer.response is None
    assert p.ctx.me.high_council
    assert offer.value_for_player(p).sum == 0.0


def test_forced_trash_takes_convincing_argument_when_it_is_no_junk() -> None:
    """Plan §11.7 (D5): Convincing Argument's TrashValue 0.25 is cancelled by
    the app's ``ConvincingArgumentTrashValueMod`` (-0.25 on every candidate),
    so ``GetCardToTrash(hand, 1.0)`` finds no junk in Convincing Argument +
    Diplomacy + Signet Ring; the forced loss is the least AcquireValue card,
    Convincing Argument (AcquireValue 0)."""

    me = scouts_state().players[ME]
    cards = (*me.hand, *me.deck)
    hand = tuple(
        next(c for c in cards if f":{name}:" in c)
        for name in ("convincing_argument", "diplomacy", "signet_ring")
    )
    state = with_me(
        scouts_state(), hand=hand, deck=tuple(c for c in cards if c not in hand)
    )
    entities = tuple(card_entity(c, ME) for c in hand)
    for seed in range(4):
        p = _conftest.make_profile(state, ME, rng_seed=seed)
        assert p.card_to_trash(list(entities), 1.0)[0] is None
        ability = abilities_of(line("funeral_rites", 0))[0]
        answer = ability.evaluate(p, Request(infos=(TargetInfo(entities=entities),)))
        assert answer.response == ((hand[0],),)


def test_scouts_bid_frame_dispatches_on_the_running_auction() -> None:
    """§3.7: the running auction (public ``scouts_item``) picks Mercenaries'
    M(b) rule or the sealed-auction surplus rule."""

    mercenaries = prof(with_state(scouts_state(), scouts_item="mercenaries"))
    assert sc.scouts_bid_evaluate(mercenaries, 3) == (
        sc.MercenariesBidEvaluator.evaluate(mercenaries, 3)
    )
    sealed = prof(with_state(scouts_state(), scouts_item="spies_for_hire_mid"))
    assert sc.scouts_bid_evaluate(sealed, 5) == (
        sc.SealedBidEvaluator.evaluate(sealed, "spies_for_hire_mid", 5)
    )


def test_two_tleilaxu_cost_is_can_gain_tleilaxu_influence() -> None:
    """§2.3: ``GainTwoTleilaxuAbility``'s Cost is CanGainTleilaxuInfluence
    (false at the track's end, rank 7); its V is not gated by it."""

    ability = abilities_of(line("tleilaxu_relations", 0))[0]
    assert isinstance(ability, sc.GainTwoTleilaxuAbility)
    assert ability.meets_cost(prof())
    top = prof(with_me(scouts_state(), tleilaxu_space=7))
    assert not ability.meets_cost(top)
    assert ability.value_for_player(top).sum == top.tleilaxu_value(2).sum


def test_desert_riding_for_a_seat_with_hooks_is_the_base_ability() -> None:
    """§2.3: the hooks option is only for a hookless seat."""

    token = with_state(
        scouts_state(),
        scouts_goods=(("desert_riding", "hagga_basin", "maker_hooks", 1, -1),),
    )
    hooked = stub(prof(with_me(token, maker_hooks=True)), maker_hooks_value=50.0)
    ability = _desert_riding(hooked)
    base = space_entity("hagga_basin", Board(True, True))
    plain = next(a for a in abilities_of(base) if type(a).__name__.startswith("Hagga"))
    assert ability.value_for_player(hooked).sum == plain.value_for_player(hooked).sum
    assert ability.evaluate(hooked, Request()) == plain.evaluate(hooked, Request())
