"""Rise of Ix's Imperium cards (abilities/ix_imperium.py, plan §13.4 slice 6).

Every test builds a real original + Rise of Ix ``GameState``
(``app_ai.testing``), adjusts the fields a formula reads and stubs the
``Profile`` prices with simple linear ones, so each branch and literal of the
decompiled method is pinned by hand (addresses in the port's docstrings).
"""

from collections.abc import Callable, Sequence
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import ix_imperium as ix
from dune_imperium.agents.app_ai.abilities import original_imperium as oi
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Ability,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.catalog import (
    IX_CARD_ARCHETYPES,
    card_entity,
    intrigue_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.tech import tech_tile_entity
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
BOARD = Board.of(IX)
SEAT = 0  # the first player of seed 1

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------

PRICES = {
    Attr.WATER: 1.0,
    Attr.SPICE: 0.5,
    Attr.SOLARI: 0.25,
    Attr.PERSUASION: 0.75,
    Attr.STRENGTH: 0.66,
    Attr.TROOPS: 0.9,
    Attr.SPECIMEN: 0.4,
}
INFLUENCE = {
    "emperor": 2.0,
    "spacing_guild": 2.5,
    "bene_gesserit": 3.0,
    "fremen": 1.0,
    "none": 3.5,
}


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "persuasion_value": lambda n: 0.75 * n,
        "solari_value": lambda n: 0.25 * n,
        "spice_value": lambda n: 0.5 * n,
        "water_value": lambda n: 1.0 * n,
        "strength_value": lambda n, include=False: 0.66 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "dreadnought_value": lambda n, include=False: 2.4 * n,
        "victory_point_value": lambda n: 7.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "deploy_value": lambda owner: 1.25,
        "discard_value": lambda: -0.6,
        "trash_card_value": lambda: 1.1,
        "trash_mod": lambda: 0.2,
        "freighter_value": lambda: 4.2,
        "negotiate_tech_value": lambda: 0.45,
        "buy_tech_value": lambda discount, allow_solari: 3.3,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "can_agent_ability_be_played_with_space": lambda space, attr, amount: True,
        "current_conflict_interest": lambda: Summer(3.0),
        "conflict_posture_bounds": lambda: (2.0, 5.0),
        "bad_intrigue_cards_in_hand": lambda: [],
        "discard_order": lambda cards, sg=False: list(cards),
        "card_to_trash": lambda targets, minimum: (
            (targets[0], 0.8) if targets else (None, 0.0)
        ),
        "game_arc": lambda: 0,
        "is_climax": lambda: False,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 0's first ``turn`` decision (round 1, original + Rise of Ix)."""

    return first_decision("turn", config=IX)


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **overrides) -> Profile``; an override of None keeps the
    real method."""

    def build(
        state: GameState,
        seat: int = SEAT,
        rng_seed: int = 0,
        **overrides: Callable[..., Any] | None,
    ) -> Profile:
        profile = make_profile(state, seat, rng_seed=rng_seed)
        stubs: dict[str, Callable[..., Any] | None] = dict(_base_stubs())
        stubs.update(overrides)
        for name, fn in stubs.items():
            if fn is not None:
                monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def imperium(name: str, copy: int = 0) -> Entity:
    return card_entity(f"imperium:{name}:{copy}", SEAT)


def space(space_id: str) -> Entity:
    return space_entity(space_id, BOARD)


def req(
    *entities: Entity, options: tuple[int, ...] = (), max_select: int = 1
) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, max_select),))


def infos(*items: TargetInfo) -> Request:
    return Request(tuple(items))


def me(state: GameState, **changes: object) -> GameState:
    return with_player(state, SEAT, **changes)


def answer_of(answer: Any) -> tuple[Any, Any]:
    return (answer.value, answer.response)


def placed(state: GameState, seat: int, *space_ids: str) -> GameState:
    """Seat ``seat`` with its Agents on ``space_ids`` (of its two)."""

    return with_player(
        state, seat, agents_available=2 - len(space_ids), agent_locations=space_ids
    )


def units(
    state: GameState,
    seat: int = SEAT,
    conflict: int = 0,
    garrison: int = 0,
    **changes: object,
) -> GameState:
    """Seat ``seat``'s troops in the Conflict and garrison (the rest in
    supply)."""

    return with_player(
        state,
        seat,
        troops_conflict=conflict,
        troops_garrison=garrison,
        troops_supply=12 - conflict - garrison,
        **changes,
    )


def with_tech(state: GameState, *tech_ids: str) -> GameState:
    """The seat holding ``tech_ids``, taken out of the tile stacks."""

    stacks = tuple(
        tuple(t for t in stack if t not in tech_ids) for stack in state.tech_stacks
    )
    return me(with_state(state, tech_stacks=stacks), tech_ids=tech_ids)


# ---------------------------------------------------------------------------
# Coverage, chains, constructors
# ---------------------------------------------------------------------------


def test_every_ability_of_every_ix_card_resolves_to_a_port() -> None:
    assert len(IX_CARD_ARCHETYPES) == 30
    for card_id in IX_CARD_ARCHETYPES:
        entity = card_entity(f"imperium:{card_id}:0", SEAT)
        for found in abilities_of(entity):
            assert not isinstance(found, UnportedAbility), (card_id, found)


def test_the_47_classes_are_registered_under_their_app_names() -> None:
    new = {
        cls.APP_CLASS: cls
        for cls in vars(ix).values()
        if isinstance(cls, type)
        and issubclass(cls, Ability)
        and cls.__module__ == ix.__name__
        and "APP_CLASS" in vars(cls)
    }
    # The 46 card classes and the playmat's Boundless Ambition custom ability.
    assert len(new) == 47
    for app_class, cls in new.items():
        assert PORTS[app_class] is cls
    assert "worm.canis.abilities.ActivatedAbilities.BaseSet.EmbeddedAgentAbility" in new
    assert "worm.canis.abilities.TriggeredAbilities.RiseOfIx.UnloadAbility" in new


def test_the_ix_class_chains_follow_the_app() -> None:
    for cls in (
        ix.BoundlessAmbitionUnloadAbility,
        ix.BoundlessAmbitionUnloadOppAbility,
        ix.UnloadAbility,
        ix.FreighterFleetOppTrackPositive,
        ix.FreighterFleetOppTrackZero,
        ix.FreighterFleetUnloadAbility,
        ix.FullScaleAssaultAbility,
        ix.GuildAccordUnloadAbility,
        ix.InTheShadowsUnloadAbility,
    ):
        assert cls.__mro__[1] is g.TriggeredAbility
    assert ix.GuildAccordAllianceAbility.__mro__[1] is oi.AllianceAbility
    assert ix.SayyadinaBondAbility.__mro__[1] is g.BondAbility
    assert ix.ShaiHuludBondAbility.__mro__[1] is g.BondAbility
    reveals: tuple[type[Ability], ...] = (
        ix.FullScaleAssaultRevealAbility,
        ix.ImperialShockTrooperAbility,
        ix.InTheShadowsRevealPreviewAbility,
        ix.IxGuildCompactRevealAbility,
        ix.SayyadinaRevealAbility,
        ix.ShaiHuludRevealAbility,
        ix.TreacheryRevealAbility,
    )
    for reveal in reveals:
        assert reveal.__mro__[1] is g.RevealAbility
    assert ix.SatelliteBanRevealAbility.__mro__[1] is oi.OptionalRetreatAbility
    assert ix.WebOfPowerSpacingGuildAbility.__mro__[1] is g.DrawAbility
    assert ix.WebOfPowerRevealAbility.__mro__[1] is g.GainAnyInfluenceAbility
    assert ix.ShaiHuludAcquireAbility.__mro__[1] is g.AcquireAbility


#: (class, timing, selection mode, AlwaysRunImmediately) of the deferred
#: classes: the constructor's ``AbilityTiming`` and the ``SelectionMode``.
_DEFERRED_TABLE: tuple[
    tuple[type[g.DeferredAbility], Timing, SelectionMode, bool], ...
] = (
    (ix.BoundlessAmbitionRevealAbility, Timing.REVEAL, SelectionMode.EXPLICIT, True),
    (ix.AppropriateAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.BountyHunterAbility, Timing.AGENT, SelectionMode.EXPLICIT, True),
    (ix.CourtIntrigueAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.DesertAmbushAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.EmbeddedAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT, True),
    (ix.EsmarTuekAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.GuildChiefAdministratorAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.ImperialBasharAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (ix.InTheShadowsAgentAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.IxGuildCompactAgentAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.IxianEngineerAbility, Timing.REVEAL, SelectionMode.OPTIONAL, False),
    (ix.LocalFenceAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.NegotiatedWithdrawalAbility, Timing.REVEAL, SelectionMode.OPTIONAL, False),
    (ix.SatelliteBanAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.SatelliteBanRevealAbility, Timing.REVEAL, SelectionMode.OPTIONAL, False),
    (ix.SayyadinaAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.ShaiHuludAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.SpiceTraderAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.TreacheryTrashSelfAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (ix.TruthsayerAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (ix.WebOfPowerEmperorAbility, Timing.AGENT, SelectionMode.EXPLICIT, True),
    (ix.WebOfPowerSpacingGuildAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (ix.WebOfPowerFremenAbility, Timing.AGENT, SelectionMode.EXPLICIT, True),
    (ix.WebOfPowerRevealAbility, Timing.REVEAL, SelectionMode.EXPLICIT, False),
    (ix.WeirdingWayAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
)


@pytest.mark.parametrize(
    ("cls", "timing", "mode", "runs"),
    _DEFERRED_TABLE,
    ids=lambda x: getattr(x, "__name__", str(x)),
)
def test_deferred_classes_keep_the_constructor_timing_and_selection_mode(
    cls: type[g.DeferredAbility],
    timing: Timing,
    mode: SelectionMode,
    runs: bool,
    turn_state: GameState,
    prof: ProfileFactory,
) -> None:
    owner = imperium("appropriate")
    assert cls.timing is timing
    assert cls(owner).selection_mode(prof(turn_state)) is mode
    assert cls.always_run_immediately is runs


def test_triggered_and_reveal_classes_keep_the_constructor_timing() -> None:
    owner = imperium("guild_accord")
    plain: tuple[type[g.TriggeredAbility], ...] = (
        ix.BoundlessAmbitionUnloadAbility,
        ix.BoundlessAmbitionUnloadOppAbility,
        ix.UnloadAbility,
        ix.FreighterFleetOppTrackPositive,
        ix.FreighterFleetOppTrackZero,
        ix.FreighterFleetUnloadAbility,
        ix.GuildAccordUnloadAbility,
        ix.InTheShadowsUnloadAbility,
    )
    for cls in plain:
        assert cls.timing is Timing.NONE
        assert vars(cls)["should_exhaust"] is False  # get_ShouldExhaust
        assert cls(owner).value_for_player.__func__ is Ability.value_for_player  # type: ignore[attr-defined]
    reveal_timed: tuple[type[Ability], ...] = (
        ix.FullScaleAssaultAbility,
        ix.GuildAccordAllianceAbility,
        ix.SayyadinaBondAbility,
        ix.ShaiHuludBondAbility,
        ix.FullScaleAssaultRevealAbility,
        ix.ImperialShockTrooperAbility,
        ix.TreacheryRevealAbility,
    )
    for timed in reveal_timed:
        assert timed.timing is Timing.REVEAL
    assert ix.GuildAccordAllianceAbility.alliance_faction == "spacing_guild"
    assert ix.SayyadinaBondAbility.bond_faction == "Fremen"
    assert ix.ShaiHuludBondAbility.bond_faction == "Fremen"
    assert ix.ShaiHuludAcquireAbility.timing is Timing.NONE


# ---------------------------------------------------------------------------
# Triggered abilities with a value
# ---------------------------------------------------------------------------


def test_guild_accord_alliance_pays_three_spice_in_the_guild_alliance(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    alliance = ix.GuildAccordAllianceAbility(imperium("guild_accord"))
    assert alliance.value_for_player(prof(turn_state)).sum == 0.0
    allied = me(turn_state, alliance_faction_ids=("spacing_guild",))
    assert alliance.value_for_player(prof(allied)).sum == pytest.approx(0.5 * 3.0)
    other = me(turn_state, alliance_faction_ids=("emperor",))
    assert alliance.value_for_player(prof(other)).sum == 0.0


def test_the_fremen_bonds_want_another_fremen_card_in_hand_or_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    sayyadina = imperium("sayyadina")
    shai_hulud = imperium("shai_hulud")
    bonds: tuple[tuple[g.BondAbility, float], ...] = (
        (ix.SayyadinaBondAbility(sayyadina), 0.75 * 3),
        (ix.ShaiHuludBondAbility(shai_hulud), 0.66 * 5.0),
    )
    # Most Ix cards have no engine play data on this branch: zones hold
    # original cards only; the owner itself never needs to be in a zone.
    fremen = imperium("chani_card")  # FactionList Fremen
    for bond, value in bonds:
        alone = me(turn_state, hand=(), in_play=())
        assert bond.value_for_player(prof(alone)).sum == 0.0
        with_hand = me(turn_state, hand=(fremen.ref,), in_play=())
        assert bond.value_for_player(prof(with_hand)).sum == pytest.approx(value)
        with_play = me(turn_state, hand=(), in_play=(fremen.ref,))
        assert bond.value_for_player(prof(with_play)).sum == pytest.approx(value)
        assert bond.timing is Timing.REVEAL


# ---------------------------------------------------------------------------
# Reveal boxes
# ---------------------------------------------------------------------------


def test_full_scale_assault_reveal_adds_three_swords_per_dreadnought(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("full_scale_assault")
    reveal = ix.FullScaleAssaultRevealAbility(owner)
    plain = g.RevealAbility(owner).value_for_player(prof(turn_state)).sum
    assert reveal.value_for_player(prof(turn_state)).sum == pytest.approx(plain)
    two = me(turn_state, dreadnoughts_conflict=2, dreadnoughts_supply=0)
    assert reveal.value_for_player(prof(two)).sum == pytest.approx(plain + 0.66 * 6)


def test_imperial_shock_trooper_wants_an_agent_on_an_emperor_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("imperial_shock_trooper")
    shock = ix.ImperialShockTrooperAbility(owner)
    plain = g.RevealAbility(owner).value_for_player(prof(turn_state)).sum
    assert shock.value_for_player(prof(turn_state)).sum == pytest.approx(plain)
    conspire = placed(turn_state, SEAT, "conspire")
    assert shock.value_for_player(prof(conspire)).sum == pytest.approx(
        plain + 0.66 * 3.0
    )
    arrakeen = placed(turn_state, SEAT, "arrakeen")
    assert shock.value_for_player(prof(arrakeen)).sum == pytest.approx(plain)
    # An opponent's Agent on an Emperor space does not count.
    other = placed(turn_state, 1, "wealth")
    assert shock.value_for_player(prof(other)).sum == pytest.approx(plain)


def test_ix_guild_compact_reveal_doubles_the_negotiate_tech_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("ix_guild_compact")
    reveal = ix.IxGuildCompactRevealAbility(owner)
    plain = g.RevealAbility(owner).value_for_player(prof(turn_state)).sum
    assert reveal.value_for_player(prof(turn_state)).sum == pytest.approx(plain + 0.9)


def test_treachery_reveal_adds_two_troops_and_the_deploy_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("treachery")
    reveal = ix.TreacheryRevealAbility(owner)
    plain = g.RevealAbility(owner).value_for_player(prof(turn_state)).sum
    seen: list[Entity] = []

    def deploy(card: Entity) -> float:
        seen.append(card)
        return 1.25

    p = prof(turn_state, deploy_value=deploy)
    assert reveal.value_for_player(p).sum == pytest.approx(plain + 1.8 + 1.25)
    assert seen == [owner]


def test_preview_only_reveal_boxes_keep_the_generic_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    for cls, name in (
        (ix.InTheShadowsRevealPreviewAbility, "in_the_shadows"),
        (ix.SayyadinaRevealAbility, "sayyadina"),
        (ix.ShaiHuludRevealAbility, "shai_hulud"),
    ):
        owner = imperium(name)
        p = prof(turn_state)
        assert "value_for_player" not in vars(cls)
        expected = g.RevealAbility(owner).value_for_player(p).sum
        assert cls(owner).value_for_player(p).sum == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Boundless Ambition
# ---------------------------------------------------------------------------


def test_boundless_ambition_reveal_reads_the_playmat_custom_ability(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    reveal = ix.BoundlessAmbitionRevealAbility(imperium("boundless_ambition"))
    p = prof(turn_state)
    custom = ix.BoundlessAmbitionCustomAbility(imperium("boundless_ambition"))
    assert reveal.value_for_player(p).sum == pytest.approx(
        custom.value_for_player(p).sum
    )
    assert answer_of(reveal.evaluate(p, Request())) == (100.0, ())


def test_boundless_ambition_custom_takes_the_best_row_card_costing_five_or_less(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    custom = ix.BoundlessAmbitionCustomAbility(imperium("boundless_ambition"))
    row = [card_entity(ref) for ref in p.ctx.imperium_row]
    cheap = [c for c in row if c.int_attr("PersuasionCost", 0) < 6]
    expected = max((p.acquire_value(c).sum for c in cheap), default=None)
    got = custom.value_for_player(p).sum
    assert got == pytest.approx(expected if expected is not None else 0.0)
    answer = custom.evaluate(p, Request(infos=(TargetInfo(entities=tuple(cheap)),)))
    if cheap:
        # ``Evaluate`` @0x4c5d750: the card first, then the picker's option 0.
        best = max(cheap, key=lambda c: p.acquire_value(c).sum)
        assert answer.response == ((best.ref,), (0,))
    assert custom.meets_cost(p) == bool(cheap)


# ---------------------------------------------------------------------------
# Appropriate, Bounty Hunter, Court Intrigue
# ---------------------------------------------------------------------------


def test_appropriate_values_a_solari_tech_buy_with_two_emperor_influence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    appropriate = ix.AppropriateAbility(imperium("appropriate"))
    asked: list[tuple[int, bool]] = []

    def buy(discount: int, allow_solari: bool) -> float:
        asked.append((discount, allow_solari))
        return 3.3

    low = prof(me(turn_state, influence=Influence(emperor=1)), buy_tech_value=buy)
    assert appropriate.value_for_player(low).sum == 0.0
    two = prof(me(turn_state, influence=Influence(emperor=2)), buy_tech_value=buy)
    assert appropriate.value_for_player(two).sum == pytest.approx(3.3)
    assert asked == [(0, True)]


def test_appropriate_evaluate_answers_the_best_tile_with_payment_option_zero(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    appropriate = ix.AppropriateAbility(imperium("appropriate"))
    tiles = [
        tech_tile_entity("TechTileArchetypes.RiseOfIx.Windtraps", "windtraps"),
        tech_tile_entity("TechTileArchetypes.RiseOfIx.Flagship", "flagship"),
        tech_tile_entity("TechTileArchetypes.RiseOfIx.Memocorders", "memocorders"),
    ]
    values = {"windtraps": 2.0, "flagship": 5.0, "memocorders": 5.0}
    p = prof(turn_state, tech_tile_acquire_value=lambda tile: Summer(values[tile.ref]))
    answer = appropriate.evaluate(p, req(*tiles, space("arrakeen")))
    assert answer_of(answer) == (5.0, (("flagship",), (ix.APPROPRIATE_PAY_SOLARI,)))
    negative = prof(turn_state, tech_tile_acquire_value=lambda tile: Summer(-1.0))
    answer = appropriate.evaluate(negative, req(*tiles))
    assert answer_of(answer) == (-1.0, (("windtraps",), (0,)))  # the first sticks
    assert appropriate.evaluate(p, Request()).response is None


def test_bounty_hunter_values_two_solari_beside_an_opponents_agent(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    hunter = ix.BountyHunterAbility(imperium("bounty_hunter"))
    p = prof(turn_state)
    assert hunter.value_for_player(p).sum == 0.0
    assert hunter.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    taken = placed(turn_state, 2, "arrakeen")
    assert hunter.value_for_player(prof(taken), (space("arrakeen"),)).sum == 0.5
    own = placed(turn_state, SEAT, "arrakeen")
    assert hunter.value_for_player(prof(own), (space("arrakeen"),)).sum == 0.0
    assert hunter.evaluate(p, Request()).value == 1.0  # DeferValue (Explicit)


def test_court_intrigue_trades_a_bad_intrigue_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    court = ix.CourtIntrigueAbility(imperium("court_intrigue"))
    p = prof(turn_state)
    assert court.value_for_player(p).sum == 0.0
    assert court.evaluate(p, Request()).response is None
    bad = [intrigue_entity(f"intrigue:{n}:0", SEAT) for n in ("private_army", "ambush")]
    q = prof(turn_state, bad_intrigue_cards_in_hand=lambda: list(bad), rng_seed=3)
    assert court.value_for_player(q).sum == q.C.CourtIntrigueValue == 2.0
    answer = court.evaluate(q, Request())
    assert answer.value == 2.0
    assert answer.response is not None
    assert answer.response[0][0] in {c.ref for c in bad}
    assert not court.meets_cost(p)


# ---------------------------------------------------------------------------
# Desert Ambush
# ---------------------------------------------------------------------------


def test_desert_ambush_value_needs_garrison_and_low_interest(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ambush = ix.DesertAmbushAbility(imperium("desert_ambush"))
    opposed = units(turn_state, 1, conflict=1, garrison=3)
    garrison = units(opposed, SEAT, garrison=2)
    # interest 3.0 above the lower bound 2.0: no value.
    assert ambush.value_for_player(prof(garrison)).sum == 0.0
    low = prof(garrison, current_conflict_interest=lambda: Summer(2.0))
    assert ambush.value_for_player(low).sum == low.C.DesertAmbushValue == 3.0
    nan = prof(garrison, current_conflict_interest=lambda: Summer(float("nan")))
    assert ambush.value_for_player(nan).sum == 0.0
    interested = {"current_conflict_interest": lambda: Summer(1.0)}
    one = units(opposed, SEAT, garrison=1)
    assert ambush.value_for_player(prof(one, **interested)).sum == 0.0
    # A dreadnought is a garrison unit too.
    dreadnought = units(
        opposed, SEAT, garrison=1, dreadnoughts_garrison=1, dreadnoughts_supply=1
    )
    assert ambush.value_for_player(prof(dreadnought, **interested)).sum == 3.0
    alone = prof(units(turn_state, SEAT))
    penalty = alone.C.DesertAmbushNoOppositionPenalty
    assert ambush.value_for_player(alone).sum == penalty == -2.0


def _ambush_units() -> list[ix.ConflictUnit]:
    return [
        ix.ConflictUnit(0, 1, 2),
        ix.ConflictUnit(1, 1, 3),
        ix.ConflictUnit(2, 2, 2),
        ix.ConflictUnit(3, 2, 2),
        ix.ConflictUnit(4, 3, 2),
    ]


def _ambush(
    prof: ProfileFactory,
    state: GameState,
    order: Sequence[tuple[int, int]],
    n: int,
) -> tuple[float, Any]:
    ambush = ix.DesertAmbushAbility(imperium("desert_ambush"), _ambush_units())
    p = prof(state, expected_combat_order_with_strength=lambda: list(order))
    info = TargetInfo(options=(0, 1, 2, 3, 4), max_select=n)
    return answer_of(ambush.evaluate(p, infos(info)))


def test_desert_ambush_retreats_the_highest_expected_strength_by_default(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    # Nobody drops below the player's 1 and everybody has Agents left.
    order = [(1, 9), (0, 1), (2, 8), (3, 7)]
    assert _ambush(prof, turn_state, order, 1) == (0.5, ((1,),))  # strongest first
    assert _ambush(prof, turn_state, order, 2) == (0.5, ((1, 0),))


def test_desert_ambush_takes_any_opponent_it_can_reduce_below_the_player(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    # Seat 1: 9 - 3 = 6, not below 4; seat 2: 5 - 2 = 3 < 4 (strict >).
    order = [(1, 9), (0, 4), (2, 5), (3, 2)]
    assert _ambush(prof, turn_state, order, 1) == (0.5, ((2,),))
    assert _ambush(prof, turn_state, order, 2) == (0.5, ((2, 3),))
    exact = [(1, 9), (0, 3), (2, 5), (3, 1)]  # seat 2: 5 - 2 = 3, not below 3
    # Seat 3 (1 - 2 = -1 < 3) is the first entry b__4 accepts.
    assert _ambush(prof, turn_state, exact, 1) == (0.5, ((4,),))


def test_desert_ambush_prefers_an_opponent_that_can_lose_every_unit(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    order = [(1, 12), (0, 1), (2, 9), (3, 8)]
    spent = placed(
        units(turn_state, 3, conflict=1, garrison=3), 3, "arrakeen", "carthag"
    )
    assert _ambush(prof, spent, order, 1) == (0.5, ((4,),))
    # With an Agent left the third seat is not "retreat all": seat 1 again.
    assert _ambush(prof, units(turn_state, 3, conflict=1), order, 1) == (
        0.5,
        ((1,),),
    )


def test_desert_ambush_keeps_the_expected_winner_near_the_end(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    order = [(1, 12), (0, 4), (2, 5), (3, 2)]
    assert _ambush(prof, turn_state, order, 1) == (0.5, ((2,),))  # reduce seat 2
    late = with_player(turn_state, 1, victory_points=10)
    # VP 10 (+ the Conflict's) reach the trigger and the player's VP:
    # "Expected First" keeps seat 1.
    assert _ambush(prof, late, order, 1) == (0.5, ((1,),))
    behind = me(late, victory_points=12)
    assert _ambush(prof, behind, order, 1) == (0.5, ((2,),))


def test_desert_ambush_counts_the_whole_retreat_list_against_the_number(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    order = [(3, 9), (0, 1), (2, 8), (1, 7)]
    # n 3: seat 3 gives one unit (3 - 1 = 2), seat 2 two (2 - 3 < 0): stop.
    assert _ambush(prof, turn_state, order, 3) == (0.5, ((4, 2, 3),))
    # n 4: 4 - 1 = 3, then 3 - 3 (the whole list) = 0: seat 1 is not reached.
    assert _ambush(prof, turn_state, order, 4) == (0.5, ((4, 2, 3),))
    assert _ambush(prof, turn_state, order, 5) == (0.5, ((4, 2, 3, 1),))


def test_desert_ambush_without_targets_leaves_the_choice_untouched(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ambush = ix.DesertAmbushAbility(imperium("desert_ambush"), _ambush_units())
    p = prof(turn_state, expected_combat_order_with_strength=lambda: [(0, 3)])
    info = TargetInfo(options=(0, 1), max_select=2)
    assert ambush.evaluate(p, infos(info)).response is None  # no opponent entry
    assert ambush.evaluate(p, Request()).response is None
    unknown = TargetInfo(options=(7, 8), max_select=2)
    q = prof(turn_state, expected_combat_order_with_strength=lambda: [(1, 3), (0, 1)])
    assert ambush.evaluate(q, infos(unknown)).response is None  # not units


# ---------------------------------------------------------------------------
# Embedded Agent, Esmar Tuek
# ---------------------------------------------------------------------------


def test_embedded_agent_doubles_the_freighter_with_another_bg_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("embedded_agent")
    agent = ix.EmbeddedAgentAbility(owner)
    alone = prof(me(turn_state, in_play=()))
    assert agent.value_for_player(alone).sum == 0.0
    assert not agent.meets_cost(alone)
    bg = imperium("bene_gesserit_initiate")
    both = prof(me(turn_state, in_play=(bg.ref,)))
    assert agent.value_for_player(both).sum == pytest.approx(8.4)
    assert agent.meets_cost(both)
    assert answer_of(agent.evaluate(both, Request())) == (100.0, ())


def test_embedded_agent_pile_value_is_the_bg_played_pattern(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    agent = ix.EmbeddedAgentAbility(imperium("embedded_agent"))
    bg = imperium("bene_gesserit_initiate")
    other = imperium("bounty_hunter")
    p = prof(me(turn_state, in_play=(), agents_available=2))
    assert agent.value_in_pile_for_other_play(p, Pile.PLAY_AREA, bg).sum == (
        pytest.approx(4.2 * 1.5)
    )
    assert agent.value_in_pile_for_other_play(p, Pile.PLAY_AREA, other).sum == 0.0
    one_agent = prof(placed(me(turn_state, in_play=()), SEAT, "wealth"))
    assert agent.value_in_pile_for_other_play(one_agent, Pile.PLAY_AREA, bg).sum == 0.0
    played = prof(me(turn_state, in_play=(bg.ref,), agents_available=2))
    assert agent.value_in_pile_for_other_play(played, Pile.PLAY_AREA, bg).sum == 0.0
    deck = agent.value_in_pile_for_other_play(p, Pile.DECK, bg).sum
    assert deck == p.C.SynergyBeneGesseritWithBondInDeck
    climax = prof(turn_state, is_climax=lambda: True)
    assert agent.value_in_pile_for_other_play(climax, Pile.DECK, bg).sum == 0.0


def test_esmar_tuek_pays_one_spice_for_influence_and_a_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    esmar = ix.EsmarTuekAbility(imperium("esmar_tuek_card"))
    p = prof(turn_state)
    expected = -0.5 + 2.5 + 1.5 + 0.3
    assert esmar.value_for_player(p).sum == pytest.approx(expected)
    assert esmar.value_for_player(p, (space("arrakeen"),)).sum == pytest.approx(
        expected
    )
    blocked = prof(
        turn_state, can_agent_ability_be_played_with_space=lambda s, a, n: False
    )
    v = esmar.value_for_player(blocked, (space("arrakeen"),))
    assert v.sum == 0.0
    assert answer_of(esmar.evaluate(p, Request())) == (pytest.approx(expected), ())
    assert not esmar.meets_cost(p)
    assert esmar.meets_cost(prof(me(turn_state, resources=Resources(spice=1))))


# ---------------------------------------------------------------------------
# Discard-for-something agent boxes
# ---------------------------------------------------------------------------


def _hand_cards(state: GameState) -> tuple[Entity, ...]:
    return tuple(card_entity(i, SEAT) for i in state.players[SEAT].hand)


def test_guild_chief_administrator_discards_then_trashes(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gca = ix.GuildChiefAdministratorAbility(imperium("guild_chief_administrator"))
    p = prof(turn_state)
    assert gca.value_for_player(p).sum == pytest.approx(-0.6 + 1.1 + 0.2)
    single = me(turn_state, hand=turn_state.players[SEAT].hand[:1])
    assert gca.value_for_player(prof(single)).sum == 0.0
    hand = _hand_cards(turn_state)
    pools: list[list[str]] = []

    def trash(targets: Sequence[Entity], minimum: float) -> tuple[Entity, float]:
        pools.append([t.ref for t in targets])
        return targets[-1], 0.8

    q = prof(turn_state, card_to_trash=trash)
    answer = gca.evaluate(q, req(*hand))
    assert answer_of(answer) == (pytest.approx(0.5), ((hand[0].ref,),))
    assert pools == [list(turn_state.players[SEAT].hand)]
    assert gca.evaluate(q, Request()).response is None  # nothing to discard
    none = prof(turn_state, card_to_trash=lambda t, m: (None, 0.0))
    assert gca.evaluate(none, req(*hand)).response is None
    assert answer_of(gca.evaluate_trash(q, req(*hand))) == (0.8, ((hand[-1].ref,),))
    assert answer_of(gca.evaluate_trash(none, req(*hand))) == (1.0, ((),))


def test_in_the_shadows_agent_trades_a_card_for_another_faction(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    shadows = ix.InTheShadowsAgentAbility(imperium("in_the_shadows"))
    p = prof(turn_state)
    assert shadows.value_for_player(p).sum == 0.0
    bg = prof(me(turn_state, influence=Influence(bene_gesserit=2)))
    assert shadows.value_for_player(bg).sum == pytest.approx(-0.6 + 2.5)
    hand = _hand_cards(turn_state)
    tracks = tuple(track_entity(f) for f in ("emperor", "spacing_guild", "fremen"))
    request = infos(TargetInfo(hand), TargetInfo(tracks))
    answer = shadows.evaluate(p, request)
    assert answer_of(answer) == (
        pytest.approx(-0.6 + 2.5),
        ((hand[0].ref,), ("spacing_guild",)),
    )
    assert shadows.evaluate(p, infos(TargetInfo(hand))).response is None
    empty = infos(TargetInfo(()), TargetInfo(tracks))
    assert shadows.evaluate(p, empty).response is None


def test_ix_guild_compact_agent_discards_two_for_a_dreadnought(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    compact = ix.IxGuildCompactAgentAbility(imperium("ix_guild_compact"))
    p = prof(turn_state)
    assert compact.value_for_player(p).sum == pytest.approx(-1.2 + 2.4)
    costly = prof(turn_state, discard_value=lambda: -1.3)
    assert compact.value_for_player(costly).sum == 0.0  # -2.6 + 2.4 <= 0
    two = me(turn_state, hand=turn_state.players[SEAT].hand[:2])
    assert compact.value_for_player(prof(two)).sum == 0.0
    hand = _hand_cards(turn_state)
    answer = compact.evaluate(p, req(*hand))
    assert answer_of(answer) == (
        pytest.approx(-1.2 + 2.4),
        ((hand[0].ref, hand[1].ref),),
    )
    late = prof(turn_state, game_arc=lambda: 2)
    assert compact.evaluate(late, req(*hand)).response is None
    assert compact.meets_cost(p)  # 5 cards, 2 dreadnoughts in supply


def test_satellite_ban_spice_trader_and_truthsayer_discard_for_resources(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    hand = _hand_cards(turn_state)
    p = prof(turn_state)
    ban = ix.SatelliteBanAbility(imperium("satellite_ban"))
    assert ban.value_for_player(p).sum == pytest.approx(-0.6 + 0.5 + 1.0)
    assert answer_of(ban.evaluate(p, req(*hand))) == (
        pytest.approx(0.9),
        ((hand[0].ref,),),
    )
    trader = ix.SpiceTraderAbility(imperium("spice_trader"))
    assert trader.value_for_player(p).sum == 0.0
    fremen = prof(me(turn_state, influence=Influence(fremen=2)))
    assert trader.value_for_player(fremen).sum == pytest.approx(-0.6 + 1.0)
    assert answer_of(trader.evaluate(p, req(*hand))) == (
        pytest.approx(0.4),
        ((hand[0].ref,),),
    )
    truth = ix.TruthsayerAbility(imperium("truthsayer"))
    assert truth.value_for_player(p).sum == pytest.approx(-0.6 + 1.5 + 0.3)
    assert answer_of(truth.evaluate(p, req(*hand))) == (
        pytest.approx(1.2),
        ((hand[0].ref,),),
    )
    single = prof(me(turn_state, hand=turn_state.players[SEAT].hand[:1]))
    for ability in (ban, truth):
        assert ability.value_for_player(single).sum == 0.0
        assert ability.evaluate(p, Request()).response is None


# ---------------------------------------------------------------------------
# Imperial Bashar
# ---------------------------------------------------------------------------


def test_imperial_bashar_values_the_better_of_troop_and_trash(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    bashar = ix.ImperialBasharAgentAbility(imperium("imperial_bashar"))
    p = prof(turn_state)
    assert bashar.value_for_player(p).sum == pytest.approx(1.3)
    troop = prof(turn_state, troop_value=lambda n, include=False: 2.0)
    assert bashar.value_for_player(troop).sum == pytest.approx(2.0)


def test_imperial_bashar_sword_bonus_counts_owned_strength_cards(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    bashar = ix.ImperialBasharAgentAbility(imperium("imperial_bashar"))
    p = prof(turn_state)
    starters = bashar.specific_acquire_value(p).sum
    swords = imperium("sardaukar_infantry")  # Strength 2
    armed = prof(me(turn_state, discard_pile=(swords.ref,)))
    assert bashar.specific_acquire_value(armed).sum == pytest.approx(
        starters + p.C.ImperialBasharSwordValue
    )


def test_imperial_bashar_evaluate_takes_troop_then_trash_then_fallback(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    bashar = ix.ImperialBasharAgentAbility(imperium("imperial_bashar"))
    hand = _hand_cards(turn_state)
    choose = TargetInfo(options=(0, 1))
    p = prof(turn_state)
    # Troop 0.9 vs trash 0.8 + 1.1: the trash.
    answer = bashar.evaluate(p, infos(choose, TargetInfo(hand)))
    assert answer_of(answer) == (pytest.approx(1.9), ((1,), (hand[0].ref,)))
    rich = prof(turn_state, troop_value=lambda n, include=False: 5.0)
    answer = bashar.evaluate(rich, infos(choose, TargetInfo(hand)))
    assert answer_of(answer) == (5.0, ((0,),))
    assert answer_of(bashar.evaluate(rich, infos(choose))) == (5.0, ((0,),))
    nothing = prof(
        turn_state,
        troop_value=lambda n, include=False: 0.0,
        card_to_trash=lambda t, m: (None, 0.0),
    )
    answer = bashar.evaluate(nothing, infos(choose, TargetInfo(hand)))
    assert answer_of(answer) == (0.5, ((1,),))
    # Without the option-1 result the troop answer stands, even at 0.
    assert answer_of(bashar.evaluate(nothing, infos(choose))) == (0.0, ((0,),))


# ---------------------------------------------------------------------------
# Ixian Engineer, Local Fence
# ---------------------------------------------------------------------------


def test_ixian_engineer_wants_three_tech_tiles(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    engineer = ix.IxianEngineerAbility(imperium("ixian_engineer"))
    two = prof(with_tech(turn_state, "memocorders", "flagship"))
    assert engineer.value_for_player(two).sum == 0.0
    assert engineer.specific_acquire_value(two).sum == two.C.IxianEngineerValue
    assert not engineer.meets_cost(two)
    three = prof(with_tech(turn_state, "memocorders", "flagship", "artillery"))
    assert engineer.value_for_player(three).sum == 7.0
    assert engineer.meets_cost(three)
    one = prof(with_tech(turn_state, "memocorders"))
    assert engineer.specific_acquire_value(one).sum == 0.0
    assert answer_of(engineer.evaluate(one, Request())) == (100.0, ())


def test_local_fence_values_the_better_open_trade(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    fence = ix.LocalFenceAbility(imperium("local_fence"))
    poor = prof(turn_state)
    assert fence.value_for_player(poor).sum == 0.0
    spice = prof(me(turn_state, resources=Resources(spice=2)))
    # 5 Solari (1.25) - 2 spice (1.0) = 0.25.
    assert fence.value_for_player(spice).sum == pytest.approx(0.25)
    solari = prof(me(turn_state, resources=Resources(solari=5)))
    # 4 spice (0.5 * 4) - 5 Solari (1.25) = 0.75.
    assert fence.value_for_player(solari).sum == pytest.approx(0.75)
    rich = prof(me(turn_state, resources=Resources(solari=5, spice=2)))
    assert fence.value_for_player(rich).sum == pytest.approx(0.75)
    dear = prof(
        me(turn_state, resources=Resources(spice=2)),
        solari_value=lambda n: 0.1 * n,
    )
    assert fence.value_for_player(dear).sum == 0.0  # Math.Max(0.0, ...)
    blocked = prof(
        me(turn_state, resources=Resources(solari=5, spice=2)),
        can_agent_ability_be_played_with_space=lambda s, a, n: a is Attr.SPICE,
    )
    v = fence.value_for_player(blocked, (space("arrakeen"),))
    assert v.sum == pytest.approx(0.25)  # only the spice trade stays open
    closed = prof(
        me(turn_state, resources=Resources(solari=5, spice=2)),
        can_agent_ability_be_played_with_space=lambda s, a, n: False,
    )
    assert fence.value_for_player(closed, (space("arrakeen"),)).sum == 0.0
    assert fence.meets_cost(spice) and fence.meets_cost(solari)
    assert not fence.meets_cost(poor)


def test_local_fence_evaluate_picks_the_better_trade(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    fence = ix.LocalFenceAbility(imperium("local_fence"))
    p = prof(turn_state)
    # Option 0: -1.0 + 1.25 = 0.25; option 1: -1.25 + 2.0 = 0.75.
    assert answer_of(fence.evaluate(p, Request())) == (0.75, ((1,),))
    cheap = prof(turn_state, spice_value=lambda n: 0.1 * n)
    assert answer_of(fence.evaluate(cheap, Request())) == (
        pytest.approx(1.05),
        ((0,),),
    )


# ---------------------------------------------------------------------------
# Negotiated Withdrawal
# ---------------------------------------------------------------------------


def test_negotiated_withdrawal_value_needs_two_units(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    withdrawal = ix.NegotiatedWithdrawalAbility(imperium("negotiated_withdrawal"))
    none = prof(units(turn_state, SEAT))
    assert withdrawal.value_for_player(none).sum == 0.0
    split = prof(units(turn_state, SEAT, conflict=1, garrison=1))
    assert withdrawal.value_for_player(split).sum == 2.5


def test_negotiated_withdrawal_reads_units_and_tracks_from_the_first_info(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    units = [
        ix.ConflictUnit(0, SEAT, 3),
        ix.ConflictUnit(1, SEAT, 2),
        ix.ConflictUnit(2, SEAT, 2),
        ix.ConflictUnit(3, SEAT, 2),
    ]
    withdrawal = ix.NegotiatedWithdrawalAbility(
        imperium("negotiated_withdrawal"), units
    )
    tracks = tuple(track_entity(f) for f in ("emperor", "spacing_guild", "fremen"))
    retreat = TargetInfo(options=(0, 1, 2, 3), max_select=3)
    p = prof(turn_state, estimated_conflict_rank=lambda bonus=0: 1)
    # The app's order: factions first; the retreat list read there is empty.
    answer = withdrawal.evaluate(p, infos(TargetInfo(tracks), retreat))
    assert answer_of(answer) == (2.5, (("spacing_guild",), ()))
    assert withdrawal.evaluate(p, infos(TargetInfo(tracks))).response is None
    # Units and tracks in the first info: the 3 weakest units (stable).
    both = TargetInfo(tracks, (0, 1, 2, 3), 0, 3)
    answer = withdrawal.evaluate(p, infos(both, retreat))
    assert answer_of(answer) == (2.5, (("spacing_guild",), (1, 2, 3)))
    ranks = {0: 2, -6: 3}
    losing = prof(turn_state, estimated_conflict_rank=lambda bonus=0: ranks[bonus])
    assert withdrawal.evaluate(losing, infos(both, retreat)).response is None
    unranked = {0: None, -6: 1}
    far = prof(turn_state, estimated_conflict_rank=lambda bonus=0: unranked[bonus])
    assert withdrawal.evaluate(far, infos(both, retreat)).response is not None


# ---------------------------------------------------------------------------
# Satellite Ban's Reveal, Sayyadina, Shai-Hulud
# ---------------------------------------------------------------------------


def test_satellite_ban_reveal_values_half_a_point_per_unit_up_to_one(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    reveal = ix.SatelliteBanRevealAbility(imperium("satellite_ban"))
    assert reveal.MAX_RETREAT == 2
    for troops, dreadnoughts, expected in (
        (0, 0, 0.0),
        (1, 0, 0.5),
        (0, 1, 0.5),
        (1, 1, 1.0),
        (3, 0, 1.0),
    ):
        state = units(
            turn_state,
            SEAT,
            conflict=troops,
            dreadnoughts_conflict=dreadnoughts,
            dreadnoughts_supply=2 - dreadnoughts,
        )
        assert reveal.value_for_player(prof(state)).sum == pytest.approx(expected)


def test_sayyadina_values_three_water_and_a_point_with_three_water(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    sayyadina = ix.SayyadinaAbility(imperium("sayyadina"))
    dry = prof(me(turn_state, resources=Resources(water=2)))
    assert sayyadina.value_for_player(dry).sum == 0.0
    assert not sayyadina.meets_cost(dry)
    wet = prof(me(turn_state, resources=Resources(water=3)))
    assert sayyadina.value_for_player(wet).sum == pytest.approx(3.0 + 7.0)
    assert sayyadina.meets_cost(wet)
    assert answer_of(sayyadina.evaluate(wet, Request())) == (100.0, ())


def test_shai_hulud_trashes_for_two_troops(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    shai = ix.ShaiHuludAbility(imperium("shai_hulud"))
    p = prof(turn_state)
    assert shai.value_for_player(p).sum == pytest.approx(1.1 + 0.2 + 1.8)
    hand = _hand_cards(turn_state)
    assert answer_of(shai.evaluate(p, req(*hand))) == (0.8, ((hand[0].ref,),))
    values = {c.ref: float(i) for i, c in enumerate(hand)}
    values[hand[2].ref] = -1.0
    fallback = prof(
        turn_state,
        card_to_trash=lambda t, m: (None, 0.3),
        acquire_value=lambda card: Summer(values[card.ref]),
    )
    assert answer_of(shai.evaluate(fallback, req(*hand))) == (0.3, ((hand[2].ref,),))
    assert shai.evaluate(fallback, Request()).response is None


def test_shai_hulud_acquire_trashes_the_trash_pick(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    acquire = ix.ShaiHuludAcquireAbility(imperium("shai_hulud"))
    hand = _hand_cards(turn_state)
    p = prof(turn_state)
    assert answer_of(acquire.evaluate(p, req(*hand))) == (0.8, ((hand[0].ref,),))
    assert acquire.evaluate(p, Request()).response is None
    kinds = [type(a).__name__ for a in abilities_of(imperium("shai_hulud"))]
    assert kinds.index("ShaiHuludAcquireAbility") < kinds.index("AcquireAbility")


# ---------------------------------------------------------------------------
# Treachery, Web of Power, Weirding Way
# ---------------------------------------------------------------------------


def test_treachery_trash_self_defers_with_its_explicit_default(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    trash = ix.TreacheryTrashSelfAbility(imperium("treachery"))
    assert answer_of(trash.evaluate(prof(turn_state), Request())) == (1.0, ())


def test_web_of_power_lines_want_two_influence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("web_of_power")
    emperor = ix.WebOfPowerEmperorAbility(owner)
    fremen = ix.WebOfPowerFremenAbility(owner)
    guild = ix.WebOfPowerSpacingGuildAbility(owner)
    p = prof(turn_state)
    for ability in (emperor, fremen, guild):
        assert ability.value_for_player(p).sum == 0.0
        assert not ability.meets_cost(p)
    two = prof(
        me(turn_state, influence=Influence(emperor=2, spacing_guild=2, fremen=2))
    )
    assert emperor.value_for_player(two).sum == 0.5
    assert fremen.value_for_player(two).sum == 1.0
    assert guild.value_for_player(two).sum == pytest.approx(1.5 + 0.3)
    assert emperor.evaluate(two, Request()).value == 1.0  # DeferValue 1
    reveal = ix.WebOfPowerRevealAbility(owner)
    assert reveal.value_for_player(p).sum == 3.0  # the best of the four tracks
    tracks = tuple(track_entity(f) for f in ("emperor", "fremen"))
    assert answer_of(reveal.evaluate(p, req(*tracks))) == (102.0, (("emperor",),))


def test_weirding_way_follows_the_conflict_interest(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    way = ix.WeirdingWayAbility(imperium("weirding_way"))
    p = prof(turn_state)  # interest 3.0 above the lower bound 2.0
    assert way.value_for_player(p).sum == 0.0
    assert answer_of(way.evaluate(p, Request())) == (1.0, ((0,),))
    low = prof(turn_state, current_conflict_interest=lambda: Summer(2.0))
    assert way.value_for_player(low).sum == low.C.WeirdingWayValue == 1.5
    assert answer_of(way.evaluate(low, Request())) == (1.0, ((1,),))
    nan = prof(turn_state, current_conflict_interest=lambda: Summer(float("nan")))
    assert way.value_for_player(nan).sum == 0.0
    assert answer_of(way.evaluate(nan, Request())) == (1.0, ((0,),))
