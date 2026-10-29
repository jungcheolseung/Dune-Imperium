"""The original game's Imperium cards (abilities/original_imperium.py, plan §12).

Every test builds a real original ``GameState`` (``app_ai.testing``),
adjusts the fields a formula reads and stubs the ``Profile`` prices with
simple linear ones, so each branch and literal of the decompiled method is
pinned by hand (addresses in the port's docstrings).
"""

from collections.abc import Callable, Sequence
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import generic as g
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
    ORIGINAL_CARD_ARCHETYPES,
    card_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
BOARD = Board.of(ORIGINAL)
SEAT = 1  # the first player of seed 1

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
}
INFLUENCE = {
    "emperor": 2.0,
    "spacing_guild": 2.5,
    "bene_gesserit": 3.0,
    "fremen": 1.0,
    "none": 3.5,
}
#: ``EstOpponentStrength`` by seat (the deciding seat is 1).
OPPONENT_STRENGTH = {0: 3, 2: 6, 3: 4}


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "persuasion_value": lambda n: 0.75 * n,
        "solari_value": lambda n: 0.25 * n,
        "spice_value": lambda n: 0.5 * n,
        "water_value": lambda n: 1.0 * n,
        "strength_value": lambda n, include=False: 0.66 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "intrigue_value": lambda: 2.25,
        "deploy_value": lambda owner: 1.25,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "best_influence_exchange": lambda lose, gain, lf=None, gf=None: (
            None,
            None,
            0.0,
        ),
        "can_agent_ability_be_played_with_space": lambda space, attr, amount: True,
        "est_strength": lambda: IntSummer(5),
        "est_opponent_strength": lambda seat: IntSummer(OPPONENT_STRENGTH[seat]),
        "current_conflict_interest": lambda: Summer(3.0),
        "conflict_posture_bounds": lambda: (2.0, 5.0),
        "relative_conflict_value": lambda: Summer(1.0),
        "troops_to_retreat": lambda n: n,
        "units_to_deploy": lambda units, max_units: max(
            0, min(units, max_units if max_units > 0 else units)
        ),
        "game_arc": lambda: 0,
        "is_climax": lambda: False,
        "is_final_round": lambda: False,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 1's first ``turn`` decision (round 1, the original game)."""

    return first_decision("turn", config=ORIGINAL)


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


def starter(name: str, copy: int = 0) -> Entity:
    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def space(space_id: str) -> Entity:
    return space_entity(space_id, BOARD)


def ability(cls: type[Ability], owner: Entity) -> Ability:
    return cls(owner)


def of(owner: Entity, app_class: str) -> Ability:
    """The port of ``app_class`` among the abilities of ``owner``."""

    (found,) = [a for a in abilities_of(owner) if a.APP_CLASS.endswith(app_class)][:1]
    return found


def req(
    *entities: Entity, options: tuple[int, ...] = (), max_select: int = 1
) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, max_select),))


_ZONES = ("deck", "hand", "discard_pile", "in_play")


def _into_zone(state: GameState, zone: str, cards: Sequence[Entity]) -> GameState:
    refs = tuple(c.ref for c in cards)
    me = state.players[SEAT]
    changes: dict[str, object] = {
        other: tuple(i for i in getattr(me, other) if i not in refs)
        for other in _ZONES
        if other != zone
    }
    changes[zone] = refs
    return with_player(state, SEAT, **changes)


def hand(state: GameState, *cards: Entity) -> GameState:
    return _into_zone(state, "hand", cards)


def in_play(state: GameState, *cards: Entity) -> GameState:
    return _into_zone(state, "in_play", cards)


def discard(state: GameState, *cards: Entity) -> GameState:
    return _into_zone(state, "discard_pile", cards)


def with_units(
    state: GameState, conflict: int = 0, garrison: int = 0, worms: int = 0
) -> GameState:
    """Troops in the Conflict and garrison (the rest in supply) and worms."""

    return with_player(
        state,
        SEAT,
        troops_conflict=conflict,
        troops_garrison=garrison,
        troops_supply=12 - conflict - garrison,
        sandworms_conflict=worms,
    )


def with_opponent(state: GameState, seat: int, **changes: object) -> GameState:
    return with_player(state, seat, **changes)


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_every_ability_of_every_original_card_resolves_to_a_port() -> None:
    assert len(ORIGINAL_CARD_ARCHETYPES) == 49
    for card_id in ORIGINAL_CARD_ARCHETYPES:
        entity = card_entity(f"imperium:{card_id}:0", SEAT)
        for found in abilities_of(entity):
            assert not isinstance(found, UnportedAbility), (card_id, found)


def test_every_new_class_is_registered_under_its_app_name() -> None:
    new = {
        cls.APP_CLASS
        for cls in vars(oi).values()
        if isinstance(cls, type)
        and issubclass(cls, Ability)
        and cls.__module__ == oi.__name__
        and "APP_CLASS" in vars(cls)
    }
    assert len(new) >= 47
    for app_class in new:
        assert PORTS[app_class].__module__ == oi.__name__


def test_the_original_cards_ability_chains_follow_the_app() -> None:
    def bases(cls: type[Ability]) -> list[str]:
        return [k.__name__ for k in cls.__mro__ if k.__name__.endswith("Ability")]

    assert oi.ScoutAbility.__mro__[1] is oi.OptionalRetreatAbility
    assert issubclass(oi.OptionalRetreatAbility, g.DeferredAbility)
    assert issubclass(oi.FirmGripAbility2, oi.AllianceAbility)
    assert issubclass(oi.AllianceAbility, g.TriggeredAbility)
    assert issubclass(oi.SpiceHunterAbility, g.BondAbility)
    assert issubclass(oi.GuildBankersAbility, g.RevealAbility)
    assert issubclass(oi.GeneManipulationAbility, g.AgentAbility)
    assert issubclass(oi.MissionariaProtectivaAbility, g.GainAnyInfluenceAbility)
    assert issubclass(oi.LadyJessicaAcquireAbility, g.AcquireAbility)
    assert issubclass(oi.DuncanLoyalBladeDeployAbility, g.DeployUnitsAbility)
    assert bases(oi.ChaniRevealAbility)[:2] == [
        "ChaniRevealAbility",
        "OptionalRetreatAbility",
    ]


#: (class, timing, selection mode): the constructor's ``AbilityTiming`` and
#: ``SelectionMode`` of each deferred class.
_DEFERRED_TABLE: tuple[tuple[type[g.DeferredAbility], Timing, SelectionMode], ...] = (
    (oi.ScoutAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.ChaniRevealAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.DuncanLoyalBladeAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.GunThopterRevealAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.SpiceSmugglersAbility, Timing.AGENT, SelectionMode.OPTIONAL),
    (oi.BeneGesseritSisterAbility, Timing.REVEAL, SelectionMode.EXPLICIT),
    (oi.FremenCampAbility, Timing.AGENT, SelectionMode.OPTIONAL),
    (oi.DuncanIdahoAbility, Timing.AGENT, SelectionMode.OPTIONAL),
    (oi.FirmGripAgentAbility, Timing.AGENT, SelectionMode.OPTIONAL),
    (oi.GuildAmbassadorRevealAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.GuildAmbassadorAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT),
    (oi.ImperialSpyAbility, Timing.AGENT, SelectionMode.OPTIONAL),
    (oi.OpulenceAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.SmugglersThopterAbility, Timing.AGENT, SelectionMode.EXPLICIT),
    (oi.SardaukarLegionAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.GurneyHalleckAbility, Timing.REVEAL, SelectionMode.OPTIONAL),
    (oi.ShiftingAllegiancesAbility, Timing.AGENT, SelectionMode.OPTIONAL),
    (oi.OtherMemoryAbility, Timing.AGENT, SelectionMode.EXPLICIT),
    (oi.TheVoiceAbility, Timing.AGENT, SelectionMode.EXPLICIT),
    (oi.ReverendMotherMohiamDeferredAbility, Timing.AGENT, SelectionMode.EXPLICIT),
    (oi.TestOfHumanityDeferredAbility, Timing.AGENT, SelectionMode.EXPLICIT),
    (oi.MissionariaProtectivaAbility, Timing.AGENT, SelectionMode.EXPLICIT),
)


@pytest.mark.parametrize(
    ("cls", "timing", "mode"),
    _DEFERRED_TABLE,
    ids=lambda x: getattr(x, "__name__", str(x)),
)
def test_deferred_classes_keep_the_constructor_timing_and_selection_mode(
    cls: type[g.DeferredAbility],
    timing: Timing,
    mode: SelectionMode,
    turn_state: GameState,
    prof: ProfileFactory,
) -> None:
    owner = imperium("scout")
    assert cls.timing is timing
    assert cls(owner).selection_mode(prof(turn_state)) is mode


def test_triggered_classes_keep_the_constructor_timing() -> None:
    owner = imperium("firm_grip")
    for cls in (
        oi.FirmGripAbility2,
        oi.WormRidersAllianceAbility,
        oi.WormRidersInfluenceAbility,
        oi.FedaykinDeathCommandoAbility,
        oi.SietchReverendMotherAbility,
        oi.SpiceHunterAbility,
    ):
        assert cls.timing is Timing.REVEAL
        assert not cls(owner).should_exhaust
    assert oi.AssassinationMissionAbility.timing is Timing.NONE
    assert oi.FirmGripAbility2.alliance_faction == "emperor"
    assert oi.WormRidersAllianceAbility.alliance_faction == "fremen"
    for cls in (
        oi.FedaykinDeathCommandoAbility,
        oi.SietchReverendMotherAbility,
        oi.SpiceHunterAbility,
    ):
        assert cls.bond_faction == "Fremen"


# ---------------------------------------------------------------------------
# Optional retreat: Scout, Chani, Duncan Idaho's Loyal Blade
# ---------------------------------------------------------------------------


def test_scout_values_half_a_point_per_unit_up_to_one(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    scout = oi.ScoutAbility(imperium("scout"))
    assert scout.MAX_RETREAT == 2
    for units, expected in ((0, 0.0), (1, 0.5), (2, 1.0), (3, 1.0)):
        p = prof(with_units(turn_state, conflict=units))
        assert scout.value_for_player(p).sum == pytest.approx(expected)
    worms = prof(with_units(turn_state, conflict=1, worms=1))
    assert scout.value_for_player(worms).sum == pytest.approx(1.0)  # units, not troops


def test_chani_values_the_units_home_when_the_rivals_are_weaker(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    chani = oi.ChaniRevealAbility(imperium("chani_card"))
    assert chani.MAX_RETREAT == -1
    four = with_units(turn_state, conflict=4)
    # EstStrength 5: the opponents at 3 and 4 are no stronger (2 of 3 > 0.5).
    assert chani.value_for_player(prof(four)).sum == 4.0
    # EstStrength 4: still two of three (3 <= 4, 4 <= 4).
    mid = prof(four, est_strength=lambda: IntSummer(4))
    assert chani.value_for_player(mid).sum == 4.0
    # EstStrength 3: one of three, not more than half.
    weak = prof(four, est_strength=lambda: IntSummer(3))
    assert chani.value_for_player(weak).sum == 0.0
    # Fewer than 3 units in the Conflict.
    few = prof(with_units(turn_state, conflict=2))
    assert chani.value_for_player(few).sum == 0.0
    both = prof(with_units(turn_state, conflict=2, worms=1))
    assert chani.value_for_player(both).sum == 3.0  # worms count as units


def test_optional_retreat_evaluate_retreats_the_first_n_troops(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    seen: list[int] = []

    def retreat(n: int) -> int:
        seen.append(n)
        return min(n, 2)

    state = with_units(turn_state, conflict=4)
    p = prof(state, troops_to_retreat=retreat)
    options = (0, 1, 2, 3)
    chani = oi.ChaniRevealAbility(imperium("chani_card"))
    answer = chani.evaluate(p, req(options=options, max_select=4))
    assert (answer.value, answer.response) == (1.0, ((0, 1),))
    assert seen == [4]  # unlimited: every troop in the Conflict
    scout = oi.ScoutAbility(imperium("scout"))
    seen.clear()
    answer = scout.evaluate(p, req(options=options, max_select=2))
    assert (answer.value, answer.response) == (1.0, ((0, 1),))
    assert seen == [2]  # MaxRetreat
    none = prof(state, troops_to_retreat=lambda n: 0)
    assert scout.evaluate(none, req(options=options)).response is None
    assert scout.evaluate(p, Request()).response is None
    entities = oi.ChaniRevealAbility(imperium("chani_card")).evaluate(
        prof(state), req(space("arrakeen"), space("carthag"), max_select=4)
    )
    assert entities.response == (("arrakeen", "carthag"),)


def test_optional_retreat_cost_needs_a_troop_in_the_conflict(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    scout = oi.ScoutAbility(imperium("scout"))
    assert not scout.meets_cost(prof(with_units(turn_state)))
    assert scout.meets_cost(prof(with_units(turn_state, conflict=1)))
    assert not scout.meets_cost(prof(with_units(turn_state, worms=2)))


def test_duncan_loyal_blade_values_the_better_of_deploy_and_retreat(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    duncan = oi.DuncanLoyalBladeAbility(imperium("duncan_loyal_blade"))
    p = prof(with_units(turn_state, conflict=1, garrison=3))
    assert duncan.value_for_player(p).sum == pytest.approx(1.25)  # DeployValue
    crowded = prof(with_units(turn_state, conflict=4, garrison=3))
    assert duncan.value_for_player(crowded).sum == pytest.approx(4.0)  # retreat
    rich = prof(with_units(turn_state, conflict=4), deploy_value=lambda owner: 9.0)
    assert duncan.value_for_player(rich).sum == pytest.approx(9.0)
    weak = prof(with_units(turn_state, conflict=4), est_strength=lambda: IntSummer(2))
    assert duncan.value_for_player(weak).sum == pytest.approx(1.25)


def test_duncan_loyal_blade_evaluate_deploys_first_then_retreats(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    duncan = oi.DuncanLoyalBladeAbility(imperium("duncan_loyal_blade"))
    asked: list[tuple[int, int]] = []

    def deploy(units: int, max_units: int) -> int:
        asked.append((units, max_units))
        return 1

    some = with_units(turn_state, conflict=2, garrison=9)
    answer = duncan.evaluate(prof(some, units_to_deploy=deploy), Request())
    assert (answer.value, answer.response) == (100.0, ((0,),))
    assert asked == [(9, -1)]  # GetNextGarrisonTroops(12) of 9 troops
    asked.clear()
    all12 = with_units(turn_state, garrison=12)
    duncan.evaluate(prof(all12, units_to_deploy=deploy), Request())
    assert asked == [(12, -1)]
    nothing = prof(
        with_units(turn_state, conflict=2, garrison=3),
        units_to_deploy=lambda units, max_units: 0,
    )
    answer = duncan.evaluate(nothing, Request())
    assert (answer.value, answer.response) == (100.0, ((1,),))
    stuck = prof(
        with_units(turn_state, conflict=2, garrison=3),
        units_to_deploy=lambda units, max_units: 0,
        troops_to_retreat=lambda n: 0,
    )
    answer = duncan.evaluate(stuck, Request())
    assert (answer.value, answer.response) == (0.0, ())
    empty = prof(with_units(turn_state))
    assert duncan.evaluate(empty, Request()).response == ()
    assert duncan.meets_cost(prof(with_units(turn_state, garrison=1)))
    assert duncan.meets_cost(prof(with_units(turn_state, conflict=1)))
    assert not duncan.meets_cost(prof(with_units(turn_state)))


def test_duncan_halves_are_never_payable_on_their_own(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(with_units(turn_state, conflict=2, garrison=3))
    retreat = oi.DuncanLoyalBladeRetreatAbility(imperium("duncan_loyal_blade"))
    deploy = oi.DuncanLoyalBladeDeployAbility(imperium("duncan_loyal_blade"))
    assert retreat.MAX_RETREAT == -1
    assert not retreat.meets_cost(p)
    assert not deploy.meets_cost(p)
    kinds = [type(a) for a in abilities_of(imperium("duncan_loyal_blade"))]
    assert kinds[-3:] == [
        oi.DuncanLoyalBladeAbility,
        oi.DuncanLoyalBladeDeployAbility,
        oi.DuncanLoyalBladeRetreatAbility,
    ]


# ---------------------------------------------------------------------------
# Triggered abilities and bonds
# ---------------------------------------------------------------------------


def test_firm_grip_alliance_values_four_persuasion_in_the_emperor_alliance(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    firm_grip = oi.FirmGripAbility2(imperium("firm_grip"))
    assert firm_grip.value_for_player(prof(turn_state)).sum == 0.0
    allied = with_player(turn_state, SEAT, alliance_faction_ids=("emperor",))
    assert firm_grip.value_for_player(prof(allied)).sum == pytest.approx(0.75 * 4)
    other = with_player(turn_state, SEAT, alliance_faction_ids=("fremen",))
    assert firm_grip.value_for_player(prof(other)).sum == 0.0


def test_worm_riders_values_the_fremen_alliance_and_influence_bonuses(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("worm_riders")
    alliance = oi.WormRidersAllianceAbility(owner)
    p = prof(turn_state)
    assert alliance.value_for_player(p).sum == 0.0
    allied = prof(with_player(turn_state, SEAT, alliance_faction_ids=("fremen",)))
    bonus = allied.C.WormRidersAllianceRevealBonus
    assert alliance.value_for_player(allied).sum == bonus == 4.0
    influence = oi.WormRidersInfluenceAbility(owner)
    low = prof(with_player(turn_state, SEAT, influence=Influence(fremen=1)))
    assert influence.value_for_player(low).sum == 0.0
    two = prof(with_player(turn_state, SEAT, influence=Influence(fremen=2)))
    bonus = two.C.WormRidersInfluenceRevealBonus
    assert influence.value_for_player(two).sum == bonus == 4.0


def test_the_fremen_bonds_want_another_fremen_card_in_hand_or_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    bonds = (
        (oi.SpiceHunterAbility(imperium("spice_hunter")), 0.5),
        (
            oi.FedaykinDeathCommandoAbility(imperium("fedaykin_death_commando")),
            0.66 * 3,
        ),
        (
            oi.SietchReverendMotherAbility(imperium("sietch_reverend_mother")),
            0.75 * 3 + 0.5,
        ),
    )
    fremen = imperium("fremen_camp")
    elsewhere = imperium("scout")  # not a Fremen card
    for bond, expected in bonds:
        owner = bond.owner
        alone = prof(hand(turn_state, owner))
        assert bond.value_for_player(alone).sum == 0.0  # only itself
        wrong = prof(hand(turn_state, owner, elsewhere))
        assert bond.value_for_player(wrong).sum == 0.0
        held = prof(hand(turn_state, owner, fremen))
        assert bond.value_for_player(held).sum == pytest.approx(expected)
        played = prof(in_play(hand(turn_state, owner), fremen))
        assert bond.value_for_player(played).sum == pytest.approx(expected)


def test_assassination_mission_has_no_ai_hook(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    trigger = oi.AssassinationMissionAbility(imperium("assassination_mission"))
    assert trigger.value_for_player(prof(turn_state)).sum == 0.0
    assert not trigger.should_exhaust
    assert trigger.timing is Timing.NONE


# ---------------------------------------------------------------------------
# Reveal boxes: the Persuasion forecast and Guild Bankers
# ---------------------------------------------------------------------------


def test_reveal_previews_feed_the_persuasion_forecast(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    allied = prof(with_player(turn_state, SEAT, alliance_faction_ids=("emperor",)))
    pre = "worm.canis.abilities.PlayAbilities.BaseSet."
    cases = (
        ("bene_gesserit_sister", "BeneGesseritSisterRevealAbility", 0, 0),
        ("worm_riders", "WormRidersRevealAbility", 0, 0),
        ("fedaykin_death_commando", "FedaykinDeathCommandoRevealAbility", 1, 1),
        ("firm_grip", "FirmGripRevealAbility", 0, 4),
        ("guild_bankers", "GuildBankersAbility", 0, 0),
    )
    for card, cls, plain, with_alliance in cases:
        entity = imperium(card)
        assert pre + cls in entity.ability_ids
        assert p._reveal_preview_value(pre + cls, entity) == plain, cls
        assert allied._reveal_preview_value(pre + cls, entity) == with_alliance, cls
    sietch = imperium("sietch_reverend_mother")
    reveal = pre + "SietchReverendMotherRevealAbility"
    assert p._reveal_preview_value(reveal, sietch) == 0
    held = prof(hand(turn_state, sietch, imperium("fremen_camp")))
    assert held._reveal_preview_value(reveal, sietch) == 3
    alone = prof(hand(turn_state, sietch, imperium("scout")))
    assert alone._reveal_preview_value(reveal, sietch) == 0


def test_the_forecast_reads_the_new_reveal_boxes_of_the_hand(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    base = prof(hand(turn_state, imperium("gun_thopter"))).possible_persuasion()
    assert prof(hand(turn_state, imperium("scout"))).possible_persuasion() == base + 1
    # Firm Grip's only RevealAbility is FirmGripRevealAbility: +4 with the alliance.
    firm_grip = hand(turn_state, imperium("firm_grip"))
    assert prof(firm_grip).possible_persuasion() == base
    allied = with_player(firm_grip, SEAT, alliance_faction_ids=("emperor",))
    assert prof(allied).possible_persuasion() == base + 4
    # Guild Bankers' only Reveal box keeps the base preview (no Persuasion).
    bankers = prof(hand(turn_state, imperium("guild_bankers")))
    assert bankers.possible_persuasion() == base
    # Fedaykin: the literal 1.
    fedaykin = prof(hand(turn_state, imperium("fedaykin_death_commando")))
    assert fedaykin.possible_persuasion() == base + 1


def test_guild_bankers_pays_five_when_both_tracks_are_cheap(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("guild_bankers")
    bankers = oi.GuildBankersAbility(owner)
    plain = g.RevealAbility(owner).value_for_player(prof(turn_state)).sum

    def cheap(guild: float, emperor: float) -> Callable[..., Summer]:
        values = {"spacing_guild": guild, "emperor": emperor}
        return lambda f, n, rank=-1, alliance=False: Summer(values.get(f, 9.0))

    both = prof(turn_state, gain_influence_value=cheap(1.0, 1.0))
    assert bankers.value_for_player(both).sum == pytest.approx(plain + 5.0)
    exact = prof(turn_state, gain_influence_value=cheap(1.25, 1.0))
    assert bankers.value_for_player(exact).sum == pytest.approx(plain)  # strict <
    emperor = prof(turn_state, gain_influence_value=cheap(1.0, 1.25))
    assert bankers.value_for_player(emperor).sum == pytest.approx(plain)
    assert bankers.value_for_player(prof(turn_state)).sum == pytest.approx(plain)
    assert bankers.timing is Timing.REVEAL
    # No tag synergy: the empty DefaultValueSummer even for the deck.
    p = prof(turn_state)
    assert bankers.value_in_pile_for_other_play(p, Pile.DECK, owner).sum == 0.0
    assert bankers.value_in_pile_for_other_play(p, Pile.PLAY_AREA, owner).sum == 0.0


# ---------------------------------------------------------------------------
# Agent boxes: Carryall, Gun Thopter, Gene Manipulation
# ---------------------------------------------------------------------------


def test_carryall_adds_the_doubled_spice_of_its_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("carryall")
    carryall = oi.CarryAllAgentAbility(owner)
    p = prof(turn_state, spice_value=lambda n: 0.5 * n * n)  # nonlinear
    hagga = space("imperium_hagga_basin")  # Spice 2
    base = g.AgentAbility(owner).value_for_player(p, (hagga,)).sum
    # GetSpiceValue(4) - GetSpiceValue(2) = 8.0 - 2.0
    assert carryall.value_for_player(p, (hagga,)).sum == pytest.approx(base + 6.0)
    flat = space("wealth")  # no Spice attribute: 0 - 0
    assert carryall.value_for_player(p, (flat,)).sum == pytest.approx(
        g.AgentAbility(owner).value_for_player(p, (flat,)).sum
    )
    assert carryall.value_for_player(p, ()).sum == pytest.approx(
        g.AgentAbility(owner).value_for_player(p, ()).sum
    )
    assert carryall.timing is Timing.AGENT


def test_gun_thopter_reveal_values_the_troops_it_can_hit(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("gun_thopter")
    thopter = oi.GunThopterRevealAbility(owner)
    state = with_units(turn_state, garrison=3)
    for hit, bonus in ((0, 0.0), (1, 6.0), (2, 3.0), (3, 2.0)):
        s = state
        for seat in (0, 2, 3)[:hit]:
            s = with_player(s, seat, troops_conflict=1, troops_supply=8)
        p = prof(s)
        expected = bonus + p.C.GunThopterTroopRevealBonus  # a troop is garrisoned
        assert thopter.value_for_player(p).sum == pytest.approx(expected)
    assert prof(state).C.GunThopterTroopRevealBonus == 1.0
    empty = prof(with_units(turn_state, garrison=0))
    assert thopter.value_for_player(empty).sum == 0.0
    assert thopter.meets_cost(prof(state))
    assert not thopter.meets_cost(empty)


def test_gun_thopter_reveal_deploys_a_supply_troop_at_one_hundred(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    thopter = oi.GunThopterRevealAbility(imperium("gun_thopter"))
    asked: list[tuple[int, int]] = []

    def deploy(units: int, max_units: int) -> int:
        asked.append((units, max_units))
        return units

    answer = thopter.evaluate(prof(turn_state, units_to_deploy=deploy), Request())
    assert (answer.value, answer.response) == (100.0, ())
    assert asked == [(1, -1)]  # GetNextTroops(1)
    asked.clear()
    bare = with_player(
        turn_state, SEAT, troops_supply=0, troops_garrison=12, troops_conflict=0
    )
    answer = thopter.evaluate(prof(bare, units_to_deploy=deploy), Request())
    assert (answer.value, answer.response) == (0.0, None)
    assert asked == [(0, -1)]


def test_gene_manipulation_wants_another_bene_gesserit_card_in_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("gene_manipulation")
    gene = oi.GeneManipulationAbility(owner)
    plain = prof(turn_state)
    base = g.AgentAbility(owner).value_for_player(plain, ()).sum
    assert gene.value_for_player(plain, ()).sum == pytest.approx(base)
    helped = prof(in_play(turn_state, imperium("bene_gesserit_initiate")))
    base = g.AgentAbility(owner).value_for_player(helped, ()).sum
    assert gene.value_for_player(helped, ()).sum == pytest.approx(base + 1.0)
    # The card itself in play does not count (AllCardsInPlay.Except(owner)).
    itself = prof(in_play(turn_state, owner))
    base = g.AgentAbility(owner).value_for_player(itself, ()).sum
    assert gene.value_for_player(itself, ()).sum == pytest.approx(base)


def test_gene_manipulation_pile_synergy_is_the_bene_gesserit_pattern(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gene = oi.GeneManipulationAbility(imperium("gene_manipulation"))
    candidate = imperium("bene_gesserit_initiate")
    plain = prof(turn_state)
    played = gene.value_in_pile_for_other_play(plain, Pile.PLAY_AREA, candidate).sum
    assert played == pytest.approx((0.5 + 0.5) * 0.75)
    deck = gene.value_in_pile_for_other_play(plain, Pile.DECK, candidate).sum
    assert deck == pytest.approx(plain.C.SynergyBeneGesseritWithBondInDeck)
    busy = prof(in_play(turn_state, imperium("test_of_humanity")))  # BG in play
    assert gene.value_in_pile_for_other_play(busy, Pile.PLAY_AREA, candidate).sum == 0.0
    last = prof(
        with_player(turn_state, SEAT, agents_available=1, agent_locations=("wealth",))
    )
    assert gene.value_in_pile_for_other_play(last, Pile.PLAY_AREA, candidate).sum == 0.0
    other = imperium("scout")
    assert gene.value_in_pile_for_other_play(plain, Pile.PLAY_AREA, other).sum == 0.0
    climax = prof(turn_state, is_climax=lambda: True)
    assert gene.value_in_pile_for_other_play(climax, Pile.DECK, candidate).sum == 0.0


# ---------------------------------------------------------------------------
# Spice, water and Solari boxes
# ---------------------------------------------------------------------------


def _steep_spice(n: int) -> float:
    """A spice price that is not linear: ``GetSpiceValue(-2)`` differs from
    ``-2 * GetSpiceValue(1)``."""

    return 0.5 * n if n > 0 else 0.7 * n


def _steep_water(n: int) -> float:
    return 1.0 * n if n > 0 else 1.3 * n


def test_spice_smugglers_pays_two_spice_for_influence_and_solari(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    smugglers = oi.SpiceSmugglersAbility(imperium("spice_smugglers"))
    asked: list[tuple[str, Attr, int]] = []

    def playable(sp: Entity | None, attr: Attr, amount: int) -> bool:
        asked.append((sp.ref if sp else "", attr, amount))
        return True

    p = prof(
        turn_state,
        spice_value=_steep_spice,
        can_agent_ability_be_played_with_space=playable,
    )
    wealth = space("wealth")
    # -2.0 * GetSpiceValue(1) + influence(Spacing Guild, 1) + GetSolariValue(3)
    assert smugglers.value_for_player(p, (wealth,)).sum == pytest.approx(
        -1.0 + 2.5 + 0.75
    )
    assert asked == [("wealth", Attr.SPICE, 2)]
    assert smugglers.value_for_player(p, ()).sum == pytest.approx(2.25)  # no space
    stuck = prof(
        turn_state, can_agent_ability_be_played_with_space=lambda s, a, n: False
    )
    assert smugglers.value_for_player(stuck, (wealth,)).sum == 0.0
    # GetSpiceValue(-2) is read at its own price.
    answer = smugglers.evaluate(p, Request())
    assert answer.value == pytest.approx(-1.4 + 2.5 + 0.75)
    assert answer.response == ()
    rich = with_player(turn_state, SEAT, resources=Resources(spice=2))
    assert smugglers.meets_cost(prof(rich))
    assert not smugglers.meets_cost(
        prof(with_player(rich, SEAT, resources=Resources(spice=1)))
    )


def test_fremen_camp_pays_two_spice_for_three_troops(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    camp = oi.FremenCampAbility(imperium("fremen_camp"))
    p = prof(turn_state, spice_value=_steep_spice)
    wealth = space("wealth")
    assert camp.value_for_player(p, (wealth,)).sum == pytest.approx(-1.0 + 2.7)
    stuck = prof(
        turn_state, can_agent_ability_be_played_with_space=lambda s, a, n: False
    )
    assert camp.value_for_player(stuck, (wealth,)).sum == 0.0
    answer = camp.evaluate(p, Request())
    assert answer.value == pytest.approx(-1.4 + 2.7)
    assert answer.response == ()
    rich = with_player(turn_state, SEAT, resources=Resources(spice=2))
    assert camp.meets_cost(prof(rich))
    no_troops = with_player(rich, SEAT, troops_supply=0, troops_garrison=12)
    assert not camp.meets_cost(prof(no_troops))
    assert not camp.meets_cost(
        prof(with_player(rich, SEAT, resources=Resources(spice=1)))
    )


def test_duncan_idaho_pays_a_water_for_a_troop_and_a_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    duncan = oi.DuncanIdahoAbility(imperium("duncan_idaho_card"))
    p = prof(turn_state, water_value=_steep_water)
    wealth = space("wealth")
    # -GetWaterValue(1) + GetTroopValue(1) + CardDrawValue + GetBuyGains(3)
    assert duncan.value_for_player(p, (wealth,)).sum == pytest.approx(
        -1.0 + 0.9 + 1.5 + 0.3
    )
    answer = duncan.evaluate(p, Request())  # GetWaterValue(-1) at its own price
    assert answer.value == pytest.approx(-1.3 + 0.9 + 1.5 + 0.3)
    assert answer.response == ()
    stuck = prof(
        turn_state, can_agent_ability_be_played_with_space=lambda s, a, n: False
    )
    assert duncan.value_for_player(stuck, (wealth,)).sum == 0.0
    assert duncan.meets_cost(
        prof(with_player(turn_state, SEAT, resources=Resources(water=1)))
    )
    assert not duncan.meets_cost(
        prof(with_player(turn_state, SEAT, resources=Resources(water=0)))
    )


def test_firm_grip_agent_gains_an_influence_for_two_solari(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    firm_grip = oi.FirmGripAgentAbility(imperium("firm_grip"))
    p = prof(turn_state)
    wealth = space("wealth")
    # GetSolariValue(-2) + the best faction (Factions.None, Emperor included)
    assert firm_grip.value_for_player(p, (wealth,)).sum == pytest.approx(-0.5 + 3.0)
    stuck = prof(
        turn_state, can_agent_ability_be_played_with_space=lambda s, a, n: False
    )
    assert firm_grip.value_for_player(stuck, (wealth,)).sum == 0.0
    tracks = Request(
        (
            TargetInfo(
                tuple(
                    track_entity(f)
                    for f in ("spacing_guild", "bene_gesserit", "fremen")
                )
            ),
        )
    )
    # Early without the Swordmaster: the untouched choice.
    assert firm_grip.evaluate(p, tracks).response is None
    armed = with_player(turn_state, SEAT, swordmaster_acquired=True, agents_available=3)
    answer = firm_grip.evaluate(prof(armed), tracks)
    # GetGainInfluenceValue(F, 1) + 100 ("Static Boost"): Bene Gesserit is best.
    assert (answer.value, answer.response) == (103.0, (("bene_gesserit",),))
    late = prof(with_state(turn_state, round_number=4))
    assert firm_grip.evaluate(late, tracks).response == (("bene_gesserit",),)
    assert (
        firm_grip.evaluate(
            prof(with_state(turn_state, round_number=3)), tracks
        ).response
        is None
    )
    assert firm_grip.evaluate(late, Request()).response is None


# ---------------------------------------------------------------------------
# Guild Ambassador
# ---------------------------------------------------------------------------


def test_guild_ambassador_reveal_is_worth_its_bonus_in_the_guild_alliance(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("guild_ambassador")
    reveal = oi.GuildAmbassadorRevealAbility(owner)
    allied = with_player(turn_state, SEAT, alliance_faction_ids=("spacing_guild",))
    p = prof(allied)
    assert reveal.value_for_player(p).sum == p.C.GuildAmbassadorRevealBonus == 4.0
    assert reveal.value_for_player(prof(turn_state)).sum == 0.0  # no alliance
    last = with_player(allied, SEAT, agents_available=1, agent_locations=("wealth",))
    assert reveal.value_for_player(prof(last)).sum == 0.0  # one Agent, 0 spice
    spice2 = with_player(last, SEAT, resources=Resources(spice=2))
    assert reveal.value_for_player(prof(spice2)).sum == 0.0  # not more than 2
    spice3 = with_player(last, SEAT, resources=Resources(spice=3))
    assert reveal.value_for_player(prof(spice3)).sum == 4.0
    answer = reveal.evaluate(p, Request())
    assert (answer.value, answer.response) == (100.0, ())
    assert reveal.meets_cost(
        prof(with_player(allied, SEAT, resources=Resources(spice=3)))
    )
    assert not reveal.meets_cost(prof(allied))


def test_guild_ambassador_agent_picks_influence_or_double_spice(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    agent = oi.GuildAmbassadorAgentAbility(imperium("guild_ambassador"))
    p = prof(turn_state)
    assert agent.value_for_player(p).sum == pytest.approx(max(2.5, 2 * 0.5))
    answer = agent.evaluate(p, Request())
    assert (answer.value, answer.response) == (2.5, ((0,),))
    dear = prof(turn_state, spice_value=lambda n: 2.0 * n)
    assert agent.value_for_player(dear).sum == pytest.approx(4.0)
    answer = agent.evaluate(dear, Request())
    assert (answer.value, answer.response) == (4.0, ((1,),))
    tie = prof(turn_state, spice_value=lambda n: 1.25 * n)  # 2.5: the first sticks
    answer = agent.evaluate(tie, Request())
    assert (answer.value, answer.response) == (2.5, ((0,),))


# ---------------------------------------------------------------------------
# Imperial Spy, Opulence, Smuggler's Thopter, Sardaukar Legion
# ---------------------------------------------------------------------------


def test_imperial_spy_takes_the_intrigue_by_arc_and_hand_size(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    spy = oi.ImperialSpyAbility(imperium("imperial_spy"))
    three = with_player(turn_state, SEAT, intrigue_cards=("a", "b", "c"))
    two = with_player(turn_state, SEAT, intrigue_cards=("a", "b"))
    for arc, state, expected in (
        (0, two, 0.0),
        (0, three, 0.0),
        (1, two, 2.25),
        (1, three, 0.0),
        (2, two, 2.25),
        (2, three, 2.25),
    ):
        p = prof(state, game_arc=lambda arc=arc: arc)
        assert spy.value_for_player(p).sum == expected, (arc, state is three)
    # Evaluate: from round 3 with fewer than 3 cards, or from round 8.
    for rounds, state, takes in (
        (2, two, False),
        (3, two, True),
        (3, three, False),
        (7, three, False),
        (8, three, True),
    ):
        p = prof(with_state(state, round_number=rounds))
        answer = spy.evaluate(p, Request())
        assert (
            (answer.response, answer.value) == ((), 2.25)
            if takes
            else (
                None,
                0.0,
            )
        ), (rounds, takes)


def test_opulence_pays_six_solari_when_rich_enough(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    opulence = oi.OpulenceAbility(imperium("opulence"))

    def solari(n: int, agents: int = 2) -> Profile:
        state = with_player(turn_state, SEAT, resources=Resources(solari=n))
        if agents == 1:
            state = with_player(
                state, SEAT, agents_available=1, agent_locations=("wealth",)
            )
        return prof(state)

    bonus = solari(0).C.OpulenceRevealBonus
    assert bonus == 5.0
    assert opulence.value_for_player(solari(6)).sum == bonus
    assert opulence.value_for_player(solari(6, agents=1)).sum == bonus  # > 5
    assert opulence.value_for_player(solari(5)).sum == bonus  # >= 4, 2 Agents
    assert opulence.value_for_player(solari(4)).sum == bonus
    assert opulence.value_for_player(solari(5, agents=1)).sum == 0.0
    assert opulence.value_for_player(solari(3)).sum == 0.0
    assert opulence.meets_cost(solari(6))
    assert not opulence.meets_cost(solari(5))
    answer = opulence.evaluate(solari(6), Request())
    assert (answer.value, answer.response) == (100.0, ())


def test_smugglers_thopter_draws_with_two_guild_influence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    thopter = oi.SmugglersThopterAbility(imperium("smugglers_thopter"))
    two = prof(with_player(turn_state, SEAT, influence=Influence(spacing_guild=2)))
    assert thopter.value_for_player(two).sum == pytest.approx(1.5 + 0.3)
    one = prof(with_player(turn_state, SEAT, influence=Influence(spacing_guild=1)))
    assert thopter.value_for_player(one).sum == 0.0
    assert thopter.meets_cost(two)
    assert not thopter.meets_cost(one)
    # Both ability objects of the card count in the Agent value.
    kinds = [type(a) for a in abilities_of(imperium("smugglers_thopter"))]
    assert kinds.count(oi.SmugglersThopterAbility) == 2
    answer = thopter.evaluate(two, Request())  # DeferredAbility's: DeferValue 2
    assert (answer.value, answer.response) == (2.0, ())


def test_sardaukar_legion_deploys_when_the_garrison_overflows(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    legion = oi.SardaukarLegionAbility(imperium("sardaukar_legion"))
    bonus = 3.0
    # 2 Agents left: more than 2 * 2 + 2 = 6 units in the garrison.
    assert prof(turn_state).C.SardaukarLegionRevealBonus == bonus
    for garrison, expected in ((3, 0.0), (6, 0.0), (7, bonus), (12, bonus)):
        p = prof(with_units(turn_state, garrison=garrison))
        assert legion.value_for_player(p).sum == expected, garrison
    full = with_units(turn_state, garrison=9)
    calm = prof(full, current_conflict_interest=lambda: Summer(2.0))  # == lower
    assert legion.value_for_player(calm).sum == 0.0  # strict
    last = with_player(full, SEAT, agents_available=1, agent_locations=("wealth",))
    assert legion.value_for_player(prof(last)).sum == bonus  # 9 > 2 * 1 + 2
    assert legion.meets_cost(prof(full))
    assert not legion.meets_cost(prof(with_units(turn_state, garrison=0)))


def test_sardaukar_legion_deploys_the_units_the_profile_picks(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    legion = oi.SardaukarLegionAbility(imperium("sardaukar_legion"))
    asked: list[tuple[int, int]] = []

    def deploy(units: int, max_units: int) -> int:
        asked.append((units, max_units))
        return 2

    p = prof(with_units(turn_state, garrison=5), units_to_deploy=deploy)
    answer = legion.evaluate(p, req(options=(0, 1, 2), max_select=3))
    assert (answer.value, answer.response) == (1.0, ((0, 1),))
    assert asked == [(3, 3)]  # the 3 troops Targets offers, NumberToSelect 3
    none = prof(turn_state, units_to_deploy=lambda units, max_units: 0)
    assert legion.evaluate(none, req(options=(0, 1, 2))).response is None
    assert legion.evaluate(p, Request()).response is None


def test_missionaria_protectiva_counts_the_influence_twice_with_a_bg_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("missionaria_protectiva")
    missionaria = oi.MissionariaProtectivaAbility(owner)
    plain = prof(turn_state)
    assert missionaria.value_for_player(plain).sum == pytest.approx(3.0)  # best faction
    helped = prof(in_play(turn_state, imperium("bene_gesserit_initiate")))
    assert missionaria.value_for_player(helped).sum == pytest.approx(3.0 + 3.0)
    itself = prof(in_play(turn_state, owner))
    assert missionaria.value_for_player(itself).sum == pytest.approx(3.0)
    candidate = imperium("bene_gesserit_initiate")
    played = missionaria.value_in_pile_for_other_play(plain, Pile.PLAY_AREA, candidate)
    assert played.sum == pytest.approx(3.0 * 0.75)
    deck = missionaria.value_in_pile_for_other_play(plain, Pile.DECK, candidate)
    assert deck.sum == pytest.approx(plain.C.SynergyBeneGesseritWithBondInDeck)
    busy = prof(in_play(turn_state, imperium("test_of_humanity")))
    assert (
        missionaria.value_in_pile_for_other_play(busy, Pile.PLAY_AREA, candidate).sum
        == 0.0
    )
    tracks = Request(
        (TargetInfo(tuple(track_entity(f) for f in ("emperor", "spacing_guild"))),)
    )
    answer = missionaria.evaluate(plain, tracks)  # GainAnyInfluenceAbility's
    assert (answer.value, answer.response) == (102.5, (("spacing_guild",),))


# ---------------------------------------------------------------------------
# Acquire boxes
# ---------------------------------------------------------------------------


def test_the_directorship_and_lady_jessica_price_their_acquire_icons(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    directorship = imperium("choam_directorship")
    assert directorship.list_attr("AcquireEffectList") == (
        "RankE",
        "RankSG",
        "RankBG",
        "RankF",
    )
    assert p.acquire_effects_value(directorship).sum == pytest.approx(
        2.0 + 2.5 + 3.0 + 1.0
    )
    jessica = imperium("lady_jessica_card")
    assert jessica.list_attr("AcquireEffectList") == ("AnyRank",)
    assert p.acquire_effects_value(jessica).sum == pytest.approx(3.5)  # Factions.None
    assert isinstance(
        of(directorship, "ChoamDirectorshipAcquireAbility"), g.AcquireAbility
    )


def test_lady_jessica_acquire_takes_the_best_faction_track(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    acquire = oi.LadyJessicaAcquireAbility(imperium("lady_jessica_card"))
    p = prof(turn_state)
    factions = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    info = TargetInfo(tuple(track_entity(f) for f in factions))
    answer = acquire.evaluate(p, Request((info,)))
    assert (answer.value, answer.response) == (3.0, (("bene_gesserit",),))
    # A first prompt of the acquire itself: the responses are (1, faction).
    other = TargetInfo(options=(0, 1))
    answer = acquire.evaluate(p, Request((other, info)))
    assert answer.response == ((1,), ("bene_gesserit",))
    tie = prof(turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(2.0))
    assert acquire.evaluate(tie, Request((info,))).response == (("emperor",),)
    assert acquire.evaluate(p, Request()).response is None
