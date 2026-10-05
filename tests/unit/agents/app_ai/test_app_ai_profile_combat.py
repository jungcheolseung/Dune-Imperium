"""The combat part of the ``WormAIProfile`` port (``profile/combat.py``).

Spec: ``analysis/ai/spec/profile-combat.md`` (and ``intrigues.md`` §4 for the
Intrigue helpers). Each test builds a real game state, adjusts the fields the
formula reads, and stubs the methods other areas own (economy, influence and
the ability ports) on the ``Profile`` instance, so only this module's
arithmetic and branch order are under test.
"""

import math
from collections.abc import Callable, Sequence
from functools import cache
from typing import Any

import pytest

from dune_imperium.agents.app_ai import catalog
from dune_imperium.agents.app_ai import testing as _conftest
from dune_imperium.agents.app_ai.abilities import UnportedAbility
from dune_imperium.agents.app_ai.abilities.base import Ability
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile, combat
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState

ME = 0  # Feyd-Rautha in the default seating; Gurney Halleck sits at 1.


def first_decision(kind: str, *, choam: bool = True) -> GameState:
    return _conftest.first_decision(kind, choam=choam)


def make_profile(state: GameState, seat: int, *, level: int = 2) -> Profile:
    return _conftest.make_profile(state, seat, level=level)


def with_player(state: GameState, seat: int, **changes: object) -> GameState:
    return _conftest.with_player(state, seat, **changes)


def with_state(state: GameState, **changes: object) -> GameState:
    return _conftest.with_state(state, **changes)


# -- states --


@cache
def base_state(choam: bool = True) -> GameState:
    """Round 1, first Agent turn: every seat at 3 garrison troops, 2 Agents."""

    return first_decision("turn", choam=choam)


def troops(garrison: int = 0, conflict: int = 0) -> dict[str, int]:
    """Troop fields that keep the 12-troop invariant."""

    return {
        "troops_garrison": garrison,
        "troops_conflict": conflict,
        "troops_supply": 12 - garrison - conflict,
    }


def conflict(state: GameState, conflict_id: str) -> GameState:
    """``state`` with ``conflict_id`` face up (and nowhere else)."""

    return with_state(
        state,
        current_conflict_ids=(conflict_id,),
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
    )


def players(state: GameState, **seats: dict[str, Any]) -> GameState:
    """Apply ``with_player`` per seat: ``players(s, p1={...}, p2={...})``."""

    for key, changes in seats.items():
        state = with_player(state, int(key[1:]), **changes)
    return state


# -- stubs --


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


def real_ratio(profile: Profile) -> Callable[[Callable[[Any], bool]], float]:
    """``OpponentRatio``: ``Count(pred) / Count()`` over the opponents."""

    def ratio(condition: Callable[[Any], bool]) -> float:
        opponents = profile.ctx.opponents
        return sum(1 for op in opponents if condition(op)) / len(opponents)

    return ratio


def profile_for(state: GameState, seat: int = ME, level: int = 2) -> Profile:
    profile = make_profile(state, seat, level=level)
    return stub(profile, opponent_ratio=real_ratio(profile))


class FakeAbility(Ability):
    """An ability port with a fixed value and Intrigue strength."""

    def __init__(
        self, owner: Entity, value: float = 0.0, strength: int | None = None
    ) -> None:
        super().__init__(owner)
        self.value = value
        if strength is not None:
            self.strength = strength

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        return Summer(self.value)

    def strength_value(self, p: Profile) -> int:
        return self.strength


class NoStrengthPort(Ability):
    """A port that forgot ``strength_value``."""


def install(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, float] | None = None,
    strengths: dict[str, int] | None = None,
    bare: Sequence[str] = (),
) -> None:
    """Make ``abilities_of`` return fakes keyed by the app class's last name.

    ``values``: value_for_player; ``strengths``: strength_value; ``bare``:
    classes ported without ``strength_value``. Anything else is unported.
    """

    values = values or {}
    strengths = strengths or {}

    def abilities_of(owner: Entity) -> tuple[Ability, ...]:
        made: list[Ability] = []
        for ability_id in owner.ability_ids:
            name = ability_id.rsplit(".", 1)[1]
            if name in strengths:
                made.append(FakeAbility(owner, strength=strengths[name]))
            elif name in values:
                made.append(FakeAbility(owner, value=values[name]))
            elif name in bare:
                made.append(NoStrengthPort(owner))
            else:
                made.append(UnportedAbility(owner, ability_id))
        return tuple(made)

    monkeypatch.setattr(combat, "abilities_of", abilities_of)


def rv(attr: Attr, amount: int, include_combat_posture_mod: bool = False) -> float:
    """A resource price stub: distinct per attribute, linear in the amount."""

    return {Attr.WATER: 2.0, Attr.SPICE: 1.0, Attr.SOLARI: 0.5, Attr.TROOPS: 1.5}[
        attr
    ] * amount


INFLUENCE = {
    "fremen": 1.0,
    "bene_gesserit": 2.0,
    "emperor": 4.0,
    "spacing_guild": 8.0,
    combat.ANY_FACTION: 3.0,
}


def gi(faction: str, amount: int, rank: int = -1, alliance: bool = False) -> Summer:
    return Summer(INFLUENCE[faction] * amount)


def app_mul(total: float, mod: float) -> float:
    """``AIProfileAbsUtils::Multiply @0x9cd920``: ``Sum + (mod*Sum - Sum)``."""

    return total + (mod * total - total)


def rcv_profile(state: GameState) -> Profile:
    return stub(
        profile_for(state),
        resource_value=rv,
        victory_point_value=lambda n: 6.0 * n,
        intrigue_value=2.25,
        gain_influence_value=gi,
        control_solari_value=4.0,
        control_spice_value=6.0,
        spy_value=Summer(1.5),
    )


# -- GetUprisingConflicts --


def test_uprising_conflicts_catalogue_drops_choam_cards_and_is_cached() -> None:
    profile = profile_for(base_state())
    pool = profile.uprising_conflicts()
    levels = [int(str(a.attributes["ConflictLevel"])) for a in pool]
    assert (levels.count(1), levels.count(2), levels.count(3)) == (3, 7, 4)
    shorts = {a.short for a in pool}
    assert not any("CHOAMSecurity" in s or "TradeDispute" in s for s in shorts)
    assert profile_for(base_state(choam=False)).uprising_conflicts() is pool


def test_pool_rewards_carry_no_unpriced_resource() -> None:
    profile = profile_for(base_state())
    for conflict_archetype in profile.uprising_conflicts():
        for reward in combat._strings(conflict_archetype, "ConflictRewardArchetypes"):
            attributes = ARCHETYPES[reward].attributes
            assert "PossibleStrength" not in attributes
            assert "RevealStrength" not in attributes


# -- AIProfileAbsUtils::Multiply --


def test_multiply_adds_the_difference_like_the_app() -> None:
    # mulsd; subsd; Add: the new sum is Sum + (mod*Sum - Sum), which differs
    # from mod*Sum in the last bit here.
    s = Summer(22.91323856929842)
    combat._multiply(s, "Avg Conflict Value", 0.08789875323860101)
    assert s.sum == 2.0140451028999564
    assert 22.91323856929842 * 0.08789875323860101 == 2.0140451028999573
    # Infinity times an empty sum is NaN, as in C#.
    s = Summer()
    combat._multiply(s, "Avg Conflict Value", math.inf)
    assert math.isnan(s.sum)


# -- RelativeConflictValue --


def test_relative_conflict_value_level_one(monkeypatch: pytest.MonkeyPatch) -> None:
    # Skirmish G/H/I: Spice 2, Solari 10, Intrigue 4, any-influence x1, 3 cards.
    install(
        monkeypatch,
        values={
            "GenericConflictFirstAbility": 7.0,
            "GenericConflictSecondAbility": 4.0,
            "GenericConflictThirdAbility": 3.0,
        },
    )
    profile = rcv_profile(conflict(base_state(), "skirmish_crysknife"))
    avg = 0.0
    for term in (2.0, 5.0, 2.25 * 4, 9.0, 1 * 3.0):
        avg += term
    avg = app_mul(avg, 1.0 / 3)
    assert profile.relative_conflict_value().sum == app_mul(14.0, 1.0 / avg)


def test_relative_conflict_value_level_two(monkeypatch: pytest.MonkeyPatch) -> None:
    # Water 5, Spice 16, Solari 18, Intrigue 3, influence Fr/BG/Emp 1 each,
    # Troops 14, 21 battle icon points, any-influence x1, Take Control x3,
    # Spy x2, one costed ability (Pay 3 Spice), 7 cards.
    install(
        monkeypatch,
        values={
            "GenericConflictFirstAbility": 10.0,
            "GenericConflictSecondAbility": 5.0,
            "GenericConflictThirdAbility": 2.0,
        },
    )
    profile = rcv_profile(conflict(base_state(), "siege_of_arrakeen"))
    avg = 0.0
    for term in (
        10.0,  # Water 5
        16.0,  # Spice 16
        9.0,  # Solari 18
        2.25 * 3,  # Intrigue
        1.0 + 2.0 + 4.0,  # Specific influence
        21.0,  # Troops 14
        21.0,  # Battle icons
        1 * 3.0,  # any influence
        3 * ((4.0 + 4.0 + 6.0) / 3.0),  # Take Control
        2 * 1.5,  # Place Spy
        6.0 * 1 * 0.5,  # Costed
    ):
        avg += term
    avg = app_mul(avg, 1.0 / 7)
    expected = app_mul(17.0, 1.0 / avg)
    assert expected == 1.046153846153846
    assert expected != 17.0 * (1.0 / avg)  # the app's Multiply, not Sum*mod
    assert profile.relative_conflict_value().sum == expected


def test_relative_conflict_value_level_three_counts_card_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Spice 23, Solari 5, VP 3, Intrigue 3, any-influence x2 (Propaganda),
    # Take Control x3, costed x3, 12 battle points, 4 cards; the current card's
    # value merges its card-level Recall2SpiesVP ability too.
    install(
        monkeypatch,
        values={
            "GenericConflictFirstAbility": 20.0,
            "GenericConflictSecondAbility": 6.0,
            "GenericConflictThirdAbility": 4.0,
            "Recall2SpiesVPAbility": 1.5,
        },
    )
    profile = rcv_profile(conflict(base_state(), "battle_for_arrakeen"))
    avg = 0.0
    for term in (
        23.0,
        2.5,
        3 * 6.0,
        2.25 * 3,
        12.0,
        2 * 3.0,
        3 * ((4.0 + 4.0 + 6.0) / 3.0),
        6.0 * 3 * 0.5,
    ):
        avg += term
    avg = app_mul(avg, 1.0 / 4)
    expected = app_mul(31.5, 1.0 / avg)
    assert expected == 1.3808219178082197
    assert expected != 31.5 * (1.0 / avg)  # the app's Multiply, not Sum*mod
    assert profile.relative_conflict_value().sum == expected


def test_relative_conflict_value_trash_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    # Trade Dispute is never in the real pool. In a pool that holds it, its
    # TrashConflictCustom IDs are not TrashCustomAbility's: they count as
    # "costed" abilities (0.5 x VP); only TrashCustomAbility's own ID is priced
    # with SpyValue.
    trade = ARCHETYPES["ConflictArchetypes.Uprising.TradeDisputeUP"]
    reward = Archetype(
        short="Fake.TrashReward",
        kind="conflict_reward",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes={"CustomAbilityIDs": (combat._TRASH_CUSTOM,)},
    )
    fake = Archetype(
        short="Fake.TrashConflict",
        kind="conflict",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes={
            "ConflictLevel": 2,
            "ConflictRewardArchetypes": ("Fake.TrashReward",) * 3,
        },
    )
    monkeypatch.setattr(
        combat, "ARCHETYPES", {**ARCHETYPES, "Fake.TrashReward": reward}
    )
    install(monkeypatch, values={"GenericConflictFirstAbility": 10.0})
    profile = stub(
        rcv_profile(conflict(base_state(), "siege_of_arrakeen")),
        uprising_conflicts=[trade],
    )
    # Trade Dispute UP: Solari 2, Water 3, Spice 1, Troops 1, 3 icon points,
    # two TrashConflictCustom IDs -> 2 costed.
    avg = 0.0
    for term in (6.0, 1.0, 1.0, 1.5, 3.0, 6.0 * 2 * 0.5):
        avg += term
    avg = app_mul(avg, 1.0 / 1)
    assert profile.relative_conflict_value().sum == app_mul(10.0, 1.0 / avg)
    profile = stub(
        rcv_profile(conflict(base_state(), "siege_of_arrakeen")),
        uprising_conflicts=[fake],
    )
    assert profile.relative_conflict_value().sum == app_mul(
        10.0, 1.0 / app_mul(3.0 + 3 * 1.5, 1.0)
    )


def test_relative_conflict_value_without_conflict_is_nan() -> None:
    state = with_state(base_state(), current_conflict_ids=())
    assert math.isnan(rcv_profile(state).relative_conflict_value().sum)


# -- posture --


@pytest.mark.parametrize(
    ("units", "climax", "bounds"),
    [
        ((0, 0, 0), False, (-10.0, 5.0)),
        ((1, 0, 1), False, (-10.0, 5.0)),  # 1 unit < level II
        ((2, 0, 1), False, (-2.5, 12.5)),
        ((2, 3, 0), False, (5.0, 20.0)),
        ((2, 3, 2), True, (10.0, 15.0)),
    ],
)
def test_conflict_posture_bounds(
    units: tuple[int, int, int], climax: bool, bounds: tuple[float, float]
) -> None:
    state = conflict(base_state(), "siege_of_arrakeen")
    state = players(
        state,
        p1=troops(0, units[0]),
        p2=troops(0, units[1]),
        p3=troops(0, units[2]),
    )
    profile = stub(profile_for(state), is_climax=climax)
    assert profile.conflict_posture_bounds() == bounds
    competitors = sum(1 for u in units if u >= 2)
    assert profile.conflict_competitors() == competitors / 3


def test_conflict_posture_bounds_half_is_some_competitors() -> None:
    # Unreachable with three opponents (ratios 0, 1/3, 2/3, 1), but 0.5 is
    # inclusive in the binary.
    profile = stub(profile_for(base_state()), opponent_ratio=0.5, is_climax=False)
    assert profile.conflict_posture_bounds() == (-2.5, 12.5)
    profile = stub(profile, opponent_ratio=0.51)
    assert profile.conflict_posture_bounds() == (5.0, 20.0)


@pytest.mark.parametrize(
    ("level", "interest", "expected"),
    [
        (2, 20.1, 1.8),
        (2, 20.0, 1.4),  # strict > ub
        (2, 5.1, 1.4),
        (2, 5.0, 1.0),  # strict > lb
        (1, 20.1, 1.05),
        (0, 6.0, 0.85),
    ],
)
def test_combat_posture_mod(level: int, interest: float, expected: float) -> None:
    profile = stub(
        profile_for(base_state(), level=level),
        current_conflict_interest=Summer(interest),
        conflict_posture_bounds=(5.0, 20.0),
    )
    assert profile.combat_posture_mod() == expected


@pytest.mark.parametrize(
    ("interest", "expected"), [(20.5, 3.0), (20.0, 2.0), (5.5, 2.0), (5.0, 0.0)]
)
def test_combat_positioning(interest: float, expected: float) -> None:
    # Opponents with at least as many Agents left as me (1): seats 1 and 3
    # (seat 3 has exactly as many).
    state = players(
        base_state(),
        p0={"agents_available": 1, "agent_locations": ("secrets",)},
        p2={"agents_available": 0, "agent_locations": ("sardaukar", "espionage")},
        p3={"agents_available": 1, "agent_locations": ("espionage",)},
    )
    profile = stub(
        profile_for(state),
        current_conflict_interest=Summer(interest),
        conflict_posture_bounds=(5.0, 20.0),
    )
    assert profile.combat_positioning() == expected


# -- CurrentConflictInterest --


@pytest.mark.parametrize(
    ("heighliner", "worm", "bonus"),
    [(ME, False, 5.0), (2, False, 0.0), (None, True, 3.0), (ME, True, 8.0)],
)
def test_current_conflict_interest(
    heighliner: int | None, worm: bool, bonus: float
) -> None:
    state = players(
        base_state(),
        p0={
            **troops(4, 0),
            "hand": ("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
            "deck": (),
        },
        p2={"agents_available": 0, "agent_locations": ("sardaukar", "espionage")},
    )
    profile = stub(
        profile_for(state),
        relative_conflict_value=Summer(1.25),
        intrigue_hand_strength_value=3,
        heighliner_potential_player=heighliner,
        has_worm_potential=worm,
    )
    expected = (1.25 - 1.0) * 40.0 + 2.5 * 4 - 1.5 * 2 + 1.0 * 2 + 0.5 * 3 + bonus
    assert profile.current_conflict_interest().sum == pytest.approx(expected)


def test_intrigue_hand_strength_value(monkeypatch: pytest.MonkeyPatch) -> None:
    install(
        monkeypatch,
        strengths={
            "WeirdingCombatAbility": 5,
            "ContingencyPlanCombatAbility": 3,
            "ContingencyPlanPlotAbility": 100,  # not a StrengthIntrigueAbility
            "BuyAccessAbility": 100,
        },
    )
    state = with_player(
        base_state(),
        ME,
        intrigue_cards=(
            "intrigue:weirding_combat:0",
            "intrigue:contingency_plan:0",
            "intrigue:buy_access:0",
            "intrigue:devour:0",  # unported: worth 0
        ),
    )
    assert profile_for(state).intrigue_hand_strength_value() == 8


def test_intrigue_hand_strength_value_needs_the_port_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, bare=("DevourAbility",))
    state = with_player(base_state(), ME, intrigue_cards=("intrigue:devour:0",))
    with pytest.raises(TypeError):
        profile_for(state).intrigue_hand_strength_value()


# -- DeployValue --


def deploy_profile(
    state: GameState, interest: float, arc: int = 0, lb: float = 5.0, ub: float = 20.0
) -> Profile:
    return stub(
        profile_for(state),
        game_arc=arc,
        conflict_posture_bounds=(lb, ub),
        current_conflict_interest=Summer(interest),
    )


SPACE = catalog.space_entity("sardaukar", Board(True))


@pytest.mark.parametrize(
    ("arc", "opponents_in", "interest", "garrison", "expected"),
    [
        (0, 3, 4.0, 3, 0.0),  # Low and every paid slot contested
        (0, 2, 4.0, 3, 0.75 * 1.5),  # Low with a free slot
        (2, 2, 10.0, 3, 1.25 * 1.5),  # Mid with a free slot (Late)
        (0, 3, 10.0, 3, 0.75),  # Mid, no free slot
        (0, 3, 20.0, 3, 1.5),  # High with garrison troops
        (0, 3, 20.0, 0, 0.75),  # High, empty garrison (and no space rule)
        (0, 3, 20.0, 6, 1.5 + 0.99),  # garrison overflow (6 - 3) * 0.33
        (0, 3, 20.0, 10, 1.5 + 2.0),  # overflow capped at 2.0
    ],
)
def test_deploy_value_posture(
    arc: int, opponents_in: int, interest: float, garrison: int, expected: float
) -> None:
    contested = {**troops(0, 1)}
    state = players(
        base_state(),
        p0=troops(garrison, 0),
        p1=contested if opponents_in >= 1 else troops(0, 0),
        p2=contested if opponents_in >= 2 else troops(0, 0),
        p3=contested if opponents_in >= 3 else troops(0, 0),
    )
    profile = deploy_profile(state, interest, arc=arc)
    assert profile.deploy_value(SPACE) == pytest.approx(expected)


def test_deploy_value_empty_garrison_spaces() -> None:
    state = players(base_state(), p0=troops(0, 0), p1=troops(0, 1), p2=troops(0, 1))
    profile = deploy_profile(state, 10.0)
    basin = catalog.space_entity("imperial_basin", Board(True))
    refinery = catalog.space_entity("spice_refinery", Board(True))
    hagga = catalog.space_entity("hagga_basin", Board(True))  # HaggaBasinUP: not listed
    assert profile.deploy_value(basin) == 0.0
    assert profile.deploy_value(refinery) == 0.0
    assert profile.deploy_value(hagga) == pytest.approx(1.125)


def test_deploy_value_heighliner_with_units_in() -> None:
    state = players(base_state(), p0=troops(0, 2), p1=troops(0, 1), p2=troops(0, 1))
    profile = deploy_profile(state, 10.0)
    heighliner = catalog.space_entity("heighliner", Board(True))
    assert profile.deploy_value(heighliner) == pytest.approx(1.125 - 1.0)
    # With no unit anywhere the Heighliner keeps the plain value.
    state = players(state, p0=troops(0, 0))
    assert deploy_profile(state, 10.0).deploy_value(heighliner) == pytest.approx(1.125)


def test_deploy_value_guaranteed_third_place(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, values={"GenericConflictThirdAbility": 2.0})
    # Nobody else can still enter: one opponent in, two without Agents.
    no_agents = {"agents_available": 0, "agent_locations": ("sardaukar", "secrets")}
    state = players(
        base_state(),
        p0=troops(3, 0),
        p1=troops(0, 1),
        p2={**troops(0, 0), **no_agents},
        p3={**troops(0, 0), **no_agents},
    )
    profile = deploy_profile(state, 10.0)
    assert profile.deploy_value(SPACE) == pytest.approx(1.125 + 1.25 * 2.0)
    # An opponent who could still enter (an Agent left, no units) blocks it.
    state = players(state, p3={**troops(0, 0)})
    state = with_player(state, 3, agents_available=1, agent_locations=("secrets",))
    assert deploy_profile(state, 10.0).deploy_value(SPACE) == pytest.approx(1.125)


@pytest.mark.parametrize(
    ("units_in", "garrison", "interest", "mod"),
    [
        (1, 2, 10.0, 1.33),
        (2, 1, 10.0, 1.33),
        (3, 1, 10.0, 1.0),  # ConflictUnits - 1 > 1
        (1, 1, 10.0, 1.0),  # fewer than 3 units in all
        (1, 2, 5.0, 1.0),  # interest not above lb
    ],
)
def test_deploy_value_chani(
    units_in: int, garrison: int, interest: float, mod: float
) -> None:
    state = players(
        base_state(),
        p0={
            **troops(garrison, units_in),
            "in_play": ("imperium:chani_clever_tactician:0",),
        },
        p1=troops(0, 1),
        p2=troops(0, 1),
        p3=troops(0, 1),
    )
    profile = deploy_profile(state, interest)
    assert profile.deploy_value(SPACE) == pytest.approx(0.75 * mod)


# -- strength estimates --


def opponent_state(**changes: Any) -> GameState:
    """Seat 1 with a known Hand ∪ Deck: 2 Daggers (1 sword) of 4 cards."""

    fields: dict[str, Any] = {
        "hand": (
            "player:1:starter:dagger:0",
            "player:1:starter:dagger:1",
            "player:1:starter:diplomacy:0",
        ),
        "deck": ("player:1:starter:signet_ring:0",),
        "intrigue_cards": ("intrigue:impress:0", "intrigue:devour:0"),
        "combat_strength": 4,
        **troops(5, 2),
    }
    fields.update(changes)
    return with_player(base_state(), 1, **fields)


def est_profile(state: GameState, **stubs: object) -> Profile:
    defaults: dict[str, object] = {
        "heighliner_potential_player": None,
        "_worm_potential_a_player": None,
        "_worm_potential_b_player": None,
        "relative_conflict_value": Summer(1.0),
    }
    defaults.update(stubs)
    return stub(profile_for(state), **defaults)


def test_est_opponent_strength_with_agents_left() -> None:
    # k = 1.2 (2 units in); hand 3 x avg 0.5 x 1.2 = 1.8 -> 2; intrigue
    # 2 x 0.75 x 1.2 = 1.8 -> 2; agents 2 -> +4; min(6, garrison 5) = 5.
    profile = est_profile(opponent_state())
    assert profile.est_opponent_strength(1).sum == 4 + 2 + 2 + 4 + 5


def test_est_opponent_strength_rounds_half_to_even() -> None:
    # k = 1.0 (1 unit in): hand 1 x avg 0.5 = 0.5 -> 0; intrigue 6 x 0.75 = 4.5
    # -> 4 (Convert.ToInt32 rounds half to even).
    state = opponent_state(
        hand=("player:1:starter:dagger:0",),
        deck=("player:1:starter:diplomacy:0",),
        intrigue_cards=tuple(f"intrigue:impress:{i}" for i in range(6)),
        **troops(5, 1),
    )
    assert est_profile(state).est_opponent_strength(1).sum == 4 + 4 + 0 + 4 + 5
    # Two units in: k = 1.2; 6 x 0.75 x 1.2 = 5.4 -> 5; 0.5 x 1.2 = 0.6 -> 1.
    state = with_player(state, 1, **troops(5, 2))
    assert est_profile(state).est_opponent_strength(1).sum == 4 + 5 + 1 + 4 + 5


@pytest.mark.parametrize(
    ("heighliner", "rcv", "worm_a", "worm_b", "bonus"),
    [
        (1, 1.0, None, None, 7),
        (1, 0.99, None, None, 0),  # the Heighliner bonus needs RCV >= 1.0
        (2, 1.0, None, None, 0),
        (None, 0.5, 1, 1, 2 + 5),  # the worm terms are independent ifs
        (None, 0.5, 1, 3, 2),
    ],
)
def test_est_opponent_strength_potentials(
    heighliner: int | None,
    rcv: float,
    worm_a: int | None,
    worm_b: int | None,
    bonus: int,
) -> None:
    profile = est_profile(
        opponent_state(),
        heighliner_potential_player=heighliner,
        relative_conflict_value=Summer(rcv),
        _worm_potential_a_player=worm_a,
        _worm_potential_b_player=worm_b,
    )
    assert profile.est_opponent_strength(1).sum == 17 + bonus


def test_est_opponent_strength_revealed_or_out() -> None:
    revealed = opponent_state(has_revealed=True)
    assert est_profile(revealed).est_opponent_strength(1).sum == 4 + 2 + 2
    empty_hand = opponent_state(
        has_revealed=True, hand=(), deck=("player:1:starter:dagger:0",)
    )
    assert est_profile(empty_hand).est_opponent_strength(1).sum == 4 + 2
    out = opponent_state(has_revealed=True, **troops(5, 0))
    assert est_profile(out).est_opponent_strength(1).sum == 0


def own_state(**changes: Any) -> GameState:
    fields: dict[str, Any] = {
        "hand": ("player:0:starter:dagger:0", "player:0:starter:diplomacy:0"),
        "deck": (),
        "combat_strength": 3,
        **troops(2, 1),
    }
    fields.update(changes)
    return with_player(base_state(), ME, **fields)


@pytest.mark.parametrize(
    ("interest", "heighliner", "worm_a", "worm_b", "expected"),
    [
        (4.9, ME, ME, ME, 1 + 3),  # below lb: hand and current only
        (5.0, None, None, None, 1 + 3 + 2 + 6),
        (5.0, ME, ME, ME, 1 + 3 + 2 + 6 + 7),
        (5.0, 2, ME, ME, 1 + 3 + 2 + 6 + 2),
        (5.0, None, 2, ME, 1 + 3 + 2 + 6 + 5),
    ],
)
def test_est_strength(
    interest: float,
    heighliner: int | None,
    worm_a: int | None,
    worm_b: int | None,
    expected: int,
) -> None:
    profile = est_profile(
        own_state(),
        current_conflict_interest=Summer(interest),
        conflict_posture_bounds=(5.0, 20.0),
        intrigue_hand_strength_value=2,
        heighliner_potential_player=heighliner,
        _worm_potential_a_player=worm_a,
        _worm_potential_b_player=worm_b,
    )
    assert profile.est_strength().sum == expected


def test_est_strength_agents_bonus_needs_a_garrison() -> None:
    profile = est_profile(
        own_state(**troops(0, 3)),
        current_conflict_interest=Summer(10.0),
        conflict_posture_bounds=(5.0, 20.0),
        intrigue_hand_strength_value=0,
    )
    assert profile.est_strength().sum == 1 + 3


@pytest.mark.parametrize(
    ("max_units", "heighliner", "worm", "expected"),
    [
        (2, ME, True, 3 + 1 + 2 + 4 + 0 + 4 + 10),  # min(2 - 2, 4) = 0
        (1, None, True, 3 + 1 + 2 + 2 + 1 + 4 + 2),
        (1, 2, False, 3 + 1 + 2 + 2 + 1 + 4),
    ],
)
def test_potential_strength(
    max_units: int, heighliner: int | None, worm: bool, expected: int
) -> None:
    profile = est_profile(
        own_state(),
        intrigue_hand_strength_value=2,
        heighliner_potential_player=heighliner,
        has_worm_potential=worm,
    )
    assert profile.potential_strength(max_units).sum == expected


def test_potential_strength_caps_the_undeployable_units() -> None:
    # Garrison 8, max 1: min(8 - 1, 2 x 2 Agents) = 4.
    profile = est_profile(
        own_state(**troops(8, 1)),
        intrigue_hand_strength_value=0,
        has_worm_potential=False,
    )
    assert profile.potential_strength(1).sum == 3 + 1 + 0 + 2 + 4 + 4


# -- GetUnitsToDeploy --


def deploy_units_profile(
    *,
    interest: float,
    my_exp: int,
    my_pot: int,
    opp: tuple[int, int, int],
    climax: bool = False,
    seat: int = ME,
    state: GameState | None = None,
) -> Profile:
    state = base_state() if state is None else state
    estimates = {
        s: e for s, e in zip([x for x in range(4) if x != seat], opp, strict=True)
    }
    return stub(
        profile_for(state, seat),
        current_conflict_interest=Summer(interest),
        conflict_posture_bounds=(5.0, 20.0),
        est_strength=IntSummer(my_exp),
        potential_strength=IntSummer(my_pot),
        est_opponent_strength=lambda s: IntSummer(estimates[s]),
        is_climax=climax,
    )


@pytest.mark.parametrize(
    ("interest", "my_exp", "my_pot", "opp", "garrison", "max_units", "expected"),
    [
        # Mid can win: all = [6, 5, 3, 0], req = 6 - 6 + 1 = 1 -> one troop.
        (10.0, 6, 9, (5, 3, 0), 3, 2, 1),
        # Mid can win as the expected leader still asks for 1.
        (10.0, 9, 12, (5, 3, 0), 3, 2, 1),
        # Mid can win: req = 8 - 4 + 1 = 5 -> three troops, capped by max 2.
        (10.0, 4, 9, (8, 3, 0), 3, 2, 2),
        (10.0, 4, 9, (8, 3, 0), 3, 3, 3),
        # Mid can get 2nd: myPot <= 8, > 5: req = 5 - 4 + 1 = 2 -> one troop.
        (10.0, 4, 8, (8, 5, 0), 3, 2, 1),  # myPot == o0 is not "can win"
        (10.0, 4, 6, (8, 5, 0), 3, 2, 1),
        # Mid can get 2nd while expected first: req = 8 - 9 + 1 = 0 -> none.
        (10.0, 9, 7, (8, 5, 0), 3, 2, 0),
        # Mid Avoid Unit Saturation: 2 x 7 - 8 = 6 -> three troops.
        (10.0, 1, 2, (8, 5, 2), 7, 5, 3),
        # High can win: req = 6 - 6 + 3 = 3 -> two troops.
        (20.0, 6, 9, (5, 3, 0), 3, 3, 2),
        # High can get second: req = 5 - 4 + 3 = 4 -> two troops.
        (20.0, 4, 8, (8, 5, 0), 3, 3, 2),  # myPot == o0 is not "can win"
        (20.0, 4, 6, (8, 5, 0), 3, 3, 2),
        # High can get third: all = [8, 7, 4, 2], req = 4 - 4 + 3 = 3.
        (20.0, 4, 5, (8, 7, 2), 3, 3, 2),
        # High None.
        (20.0, 1, 2, (8, 7, 2), 3, 3, 0),
        # max 0 means "all offered units": req = 8 - 4 + 3 = 7.
        (20.0, 4, 9, (12, 8, 0), 3, 0, 3),
        (20.0, 4, 9, (12, 8, 0), 3, 2, 2),
        # A NaN interest is neither Low, Mid nor High.
        (math.nan, 4, 9, (12, 3, 0), 3, 2, 0),
    ],
)
def test_units_to_deploy_requests(
    interest: float,
    my_exp: int,
    my_pot: int,
    opp: tuple[int, int, int],
    garrison: int,
    max_units: int,
    expected: int,
) -> None:
    state = players(
        base_state(), p0=troops(garrison, 1), p1=troops(0, 1), p2=troops(0, 1)
    )
    profile = deploy_units_profile(
        interest=interest, my_exp=my_exp, my_pot=my_pot, opp=opp, state=state
    )
    assert profile.units_to_deploy(garrison, max_units) == expected


def test_units_to_deploy_climax_commits_up_to_max() -> None:
    profile = deploy_units_profile(
        interest=-50.0, my_exp=0, my_pot=0, opp=(0, 0, 0), climax=True
    )
    assert profile.units_to_deploy(3, 2) == 2
    assert profile.units_to_deploy(3, 5) == 3


@pytest.mark.parametrize(
    ("mine_in", "opponents_in", "expected"), [(0, 2, 1), (1, 2, 0), (0, 3, 0)]
)
def test_units_to_deploy_low_deploys_one_to_a_free_slot(
    mine_in: int, opponents_in: int, expected: int
) -> None:
    contested = troops(0, 1)
    state = players(
        base_state(),
        p0=troops(3, mine_in),
        p1=contested,
        p2=contested,
        p3=contested if opponents_in == 3 else troops(0, 0),
    )
    profile = deploy_units_profile(
        interest=4.0, my_exp=0, my_pot=20, opp=(0, 0, 0), state=state
    )
    assert profile.units_to_deploy(3, 2) == expected


def test_units_to_deploy_mid_deploys_one_without_gurney() -> None:
    gurney = 1
    state = players(base_state(), p1=troops(3, 0), p0=troops(0, 1))
    profile = deploy_units_profile(
        interest=10.0, my_exp=0, my_pot=1, opp=(8, 5, 2), seat=gurney, state=state
    )
    assert profile.units_to_deploy(3, 3) == 1  # "Mid Deploy 1": no 6-strength target


def test_units_to_deploy_gurney_reaches_six() -> None:
    gurney = 1
    state = players(base_state(), p1=troops(3, 0))
    profile = deploy_units_profile(
        interest=10.0, my_exp=1, my_pot=9, opp=(2, 1, 0), seat=gurney, state=state
    )
    # Mid can win: req = 2 - 1 + 1 = 2, raised to 6 - 1 = 5 -> three troops.
    assert profile.units_to_deploy(3, 3) == 3
    feyd = deploy_units_profile(interest=10.0, my_exp=1, my_pot=9, opp=(2, 1, 0))
    assert feyd.units_to_deploy(3, 3) == 1


def test_units_to_deploy_go_to_ground_keeps_one_troop_in() -> None:
    state = players(
        base_state(),
        p0={**troops(3, 0), "intrigue_cards": ("intrigue:go_to_ground:0",)},
    )
    profile = deploy_units_profile(
        interest=20.0, my_exp=1, my_pot=2, opp=(8, 7, 2), state=state
    )
    assert profile.units_to_deploy(3, 2) == 1
    assert profile.units_to_deploy(0, 2) == 0
    with_troop_in = players(
        base_state(),
        p0={**troops(3, 1), "intrigue_cards": ("intrigue:go_to_ground:0",)},
    )
    profile = deploy_units_profile(
        interest=20.0, my_exp=1, my_pot=2, opp=(8, 7, 2), state=with_troop_in
    )
    assert profile.units_to_deploy(3, 2) == 0


# -- GetTroopsToRetreat --


def retreat_profile(
    state: GameState,
    *,
    estimates: dict[int, int],
    rcv: float = 1.0,
    climax: bool = False,
    intrigue: int = 0,
) -> Profile:
    return stub(
        profile_for(state),
        est_strength=IntSummer(estimates[ME]),
        est_opponent_strength=lambda s: IntSummer(estimates[s]),
        relative_conflict_value=Summer(rcv),
        is_climax=climax,
        intrigue_hand_strength_value=intrigue,
    )


def strengths(state: GameState, values: tuple[int, int, int, int]) -> GameState:
    for seat, value in enumerate(values):
        state = with_player(state, seat, combat_strength=value)
    return state


@pytest.mark.parametrize(
    ("garrison", "values", "rcv", "max_troops", "expected"),
    [
        (4, (12, 2, 0, 0), 0.5, 5, 0),  # garrison not below the threshold
        (3, (12, 2, 0, 0), 0.5, 5, 3),  # excess 10: 10 // 2 - 2
        (3, (12, 2, 0, 0), 0.5, 2, 2),  # capped
        (3, (7, 2, 0, 0), 0.5, 5, 0),  # excess 5 < 6
        (3, (12, 2, 0, 0), 0.9, 5, 3),  # RCV <= 0.9 keeps the 4 margin
        (3, (12, 2, 0, 0), 0.91, 5, 1),  # excess 10: 10 // 2 - 4
        (3, (9, 2, 0, 0), 0.91, 5, 0),  # excess 7 < 8
        (3, (12, 14, 13, 2), 0.5, 5, 3),  # below = first opponent at or under
        (3, (6, 14, 13, 9), 0.5, 5, 1),  # beaten by all: below 0, excess 6
        (3, (12, 12, 2, 0), 0.5, 5, 0),  # a tied opponent is "at or below"
    ],
)
def test_troops_to_retreat_margin(
    garrison: int,
    values: tuple[int, int, int, int],
    rcv: float,
    max_troops: int,
    expected: int,
) -> None:
    state = strengths(players(base_state(), p0=troops(garrison, 3)), values)
    estimates = {0: 9, 1: 5, 2: 4, 3: 3}
    profile = retreat_profile(state, estimates=estimates, rcv=rcv)
    assert profile.troops_to_retreat(max_troops) == expected


def endgame_state(values: tuple[int, int, int, int]) -> GameState:
    state = strengths(base_state(), values)
    state = with_player(state, 2, victory_points=10)
    return players(state, p0=troops(0, 3), p1=troops(0, 2), p2=troops(0, 2))


def test_troops_to_retreat_endgame_branch() -> None:
    estimates = {0: 1, 1: 2, 2: 9, 3: 3}  # seat 2 (10 VP) is expected in the top 2
    # Climax: hold everything.
    profile = retreat_profile(
        endgame_state((2, 5, 6, 7)), estimates=estimates, climax=True
    )
    assert profile.troops_to_retreat(3) == 0
    # Beaten by all three: hopeless unless the Intrigue swords close the gap.
    hopeless = endgame_state((2, 5, 6, 7))
    assert retreat_profile(hopeless, estimates=estimates).troops_to_retreat(3) == 3
    assert (
        retreat_profile(hopeless, estimates=estimates, intrigue=5).troops_to_retreat(3)
        == 0
    )
    # Third now and every opponent either in or out of Agents: keep one unit.
    third = players(
        endgame_state((4, 5, 6, 0)),
        p3={"agents_available": 0, "agent_locations": ("secrets", "espionage")},
    )
    assert retreat_profile(third, estimates=estimates).troops_to_retreat(5) == 2
    # Someone could still enter: no retreat.
    open_seat = endgame_state((4, 5, 6, 0))
    assert retreat_profile(open_seat, estimates=estimates).troops_to_retreat(5) == 0
    # Below the trigger the margin rule applies instead.
    calm = with_player(endgame_state((4, 5, 6, 0)), 2, victory_points=9)
    assert retreat_profile(calm, estimates=estimates).troops_to_retreat(5) == 0


# -- ranks and orders --


@pytest.mark.parametrize(
    ("values", "bonus", "rank"),
    [
        ((8, 5, 3, 0), 0, 1),
        ((5, 5, 3, 0), 0, 2),  # tied first: 2nd
        ((3, 5, 3, 0), 0, 3),  # tied second: 3rd
        ((3, 5, 4, 3), 0, None),  # tied third: no reward
        ((0, 0, 0, 0), 0, 2),  # all zero: a four-way "tie"
        ((1, 5, 4, 3), 0, None),
        ((1, 5, 4, 3), 5, 1),
    ],
)
def test_current_conflict_rank(
    values: tuple[int, int, int, int], bonus: int, rank: int | None
) -> None:
    profile = profile_for(strengths(base_state(), values))
    assert profile.current_conflict_rank(bonus) == rank


def test_estimated_conflict_rank_uses_estimates() -> None:
    state = strengths(base_state(), (6, 9, 9, 9))
    profile = stub(
        profile_for(state),
        est_opponent_strength=lambda s: IntSummer({1: 7, 2: 6, 3: 2}[s]),
    )
    assert profile.estimated_conflict_rank() == 3  # tied with seat 2 for 2nd
    assert profile.estimated_conflict_rank(2) == 1


def test_combat_orders() -> None:
    state = strengths(base_state(), (3, 5, 3, 7))
    profile = stub(
        profile_for(state),
        est_strength=IntSummer(4),
        est_opponent_strength=lambda s: IntSummer({1: 4, 2: 6, 3: 1}[s]),
    )
    assert profile.current_combat_order() == [3, 1, 0, 2]
    assert profile.expected_combat_order_with_strength() == [
        (2, 6),
        (1, 4),
        (0, 4),
        (3, 1),
    ]
    assert profile.expected_combat_order() == [2, 1, 0, 3]


# -- Heighliner and worm potentials --


def potential_state(**seats: dict[str, Any]) -> GameState:
    """No Guild-icon card anywhere unless a seat's changes add one."""

    state = base_state()
    for seat in range(4):
        prefix = f"player:{seat}:starter"
        state = with_player(
            state,
            seat,
            hand=(f"{prefix}:dagger:0",),
            deck=(f"{prefix}:reconnaissance:0",),
        )
    return players(state, **seats)


def rich(seat: int, *, guild: bool, spice: int = 5, water: int = 1) -> dict[str, Any]:
    prefix = f"player:{seat}:starter"
    hand = (f"{prefix}:diplomacy:0",) if guild else (f"{prefix}:dagger:0",)
    return {"resources": Resources(spice=spice, water=water), "hand": hand}


def test_heighliner_potential_player() -> None:
    order = [1, 2, 3, 0]
    # Nobody qualifies.
    profile = stub(profile_for(potential_state()), ordered_players=order)
    assert profile.heighliner_potential_player() is None
    # The AI with 5 spice and a Guild-icon card in hand.
    state = potential_state(p0=rich(0, guild=True))
    profile = stub(profile_for(state), ordered_players=order)
    assert profile.heighliner_potential_player() == ME
    assert profile.has_highliner_potential()
    assert not profile.has_highliner_potential(2)
    # An opponent earlier in the order, with a Guild card in Hand ∪ Deck.
    state = potential_state(
        p0=rich(0, guild=True),
        p2={**rich(2, guild=False), "deck": ("player:2:starter:seek_allies:0",)},
    )
    profile = stub(profile_for(state), ordered_players=order)
    assert profile.heighliner_potential_player() == 2
    # Spice short, or no Agent left: skipped.
    state = potential_state(p0=rich(0, guild=True), p2=rich(2, guild=True, spice=4))
    assert (
        stub(profile_for(state), ordered_players=order).heighliner_potential_player()
        == 0
    )
    state = potential_state(
        p0={
            **rich(0, guild=True),
            "agents_available": 0,
            "agent_locations": ("secrets", "espionage"),
        }
    )
    assert (
        stub(profile_for(state), ordered_players=order).heighliner_potential_player()
        is None
    )


def test_heighliner_potential_needs_the_space_free_or_observed() -> None:
    order = [0, 1, 2, 3]
    blocker = {"agents_available": 1, "agent_locations": ("heighliner",)}
    state = potential_state(p0=rich(0, guild=True), p3=blocker)
    assert (
        stub(profile_for(state), ordered_players=order).heighliner_potential_player()
        is None
    )
    spy = {
        "spy_post_ids": ("spacing-guild-heighliner-deliver-supplies",),
        "spies_supply": 2,
    }
    state = potential_state(p0={**rich(0, guild=True), **spy}, p3=blocker)
    assert (
        stub(profile_for(state), ordered_players=order).heighliner_potential_player()
        == 0
    )


def hooks(**changes: Any) -> dict[str, Any]:
    return {"maker_hooks": True, "resources": Resources(water=3), **changes}


def test_can_play_to_desert_space_with_hooks() -> None:
    state = players(base_state(), p0=hooks(), p1=hooks(resources=Resources(water=1)))
    profile = profile_for(state)
    assert profile.can_play_to_desert_space_with_hooks(0, "deep_desert")
    assert not profile.can_play_to_desert_space_with_hooks(
        1, "deep_desert"
    )  # water 1 < 3
    assert profile.can_play_to_desert_space_with_hooks(1, "hagga_basin")
    assert not profile.can_play_to_desert_space_with_hooks(2, "hagga_basin")  # no hooks
    occupied = players(
        state, p3={"agents_available": 1, "agent_locations": ("deep_desert",)}
    )
    assert not profile_for(occupied).can_play_to_desert_space_with_hooks(
        0, "deep_desert"
    )
    watching = players(
        occupied, p0={"spy_post_ids": ("arrakis-deep-desert",), "spies_supply": 2}
    )
    assert profile_for(watching).can_play_to_desert_space_with_hooks(0, "deep_desert")
    no_agents = players(
        state, p0={"agents_available": 0, "agent_locations": ("secrets", "espionage")}
    )
    assert not profile_for(no_agents).can_play_to_desert_space_with_hooks(
        0, "hagga_basin"
    )


def test_worm_potentials_follow_the_ordered_players() -> None:
    state = players(base_state(), p0=hooks(), p2=hooks(resources=Resources(water=1)))
    profile = stub(profile_for(state), ordered_players=[2, 3, 0, 1])
    assert profile.worm_potential_player("hagga_basin") == 2
    assert profile.worm_potential_player("deep_desert") == 0
    assert profile.has_worm_potential()  # B only
    assert not profile.has_worm_potential_a()
    assert profile.has_worm_potential_b()
    assert profile.has_worm_potential_a(2)
    assert profile.has_worm_potential(2)
    assert not profile.has_worm_potential(3)


# -- intrigue helpers --


def retreat_intrigue_profile(
    values: tuple[int, int, int, int],
    estimates: dict[int, int],
    units: int = 3,
) -> Profile:
    state = strengths(players(base_state(), p0=troops(0, units)), values)
    return stub(
        profile_for(state),
        est_strength=IntSummer(estimates[ME]),
        est_opponent_strength=lambda s: IntSummer(estimates[s]),
        victory_point_value=lambda n: 6.0 * n,
    )


@pytest.mark.parametrize(
    ("values", "estimates", "name", "units", "expected"),
    [
        # Expected first, strictly ahead, margin firstExtra 6 over next below.
        ((12, 6, 2, 0), {0: 9, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 1),
        ((11, 6, 2, 0), {0: 9, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 0),
        ((12, 6, 2, 0), {0: 9, 1: 9, 2: 3, 3: 0}, "Go To Ground", 2, 0),
        ((12, 12, 2, 0), {0: 9, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 0),
        # Strictly ahead now but not expected first: notFirstExtra 2 + 1.
        ((9, 6, 2, 0), {0: 5, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 1),
        ((8, 6, 2, 0), {0: 5, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 0),
        # Caught now and expected below second.
        ((5, 6, 2, 0), {0: 2, 1: 9, 2: 3, 3: 0}, "Reach Agreement", 3, 1),
        ((5, 6, 2, 0), {0: 2, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 1),  # rank 2
        ((1, 6, 4, 2), {0: 2, 1: 9, 2: 3, 3: 0}, "Go To Ground", 3, 0),  # no rank
    ],
)
def test_should_play_retreat_intrigue(
    values: tuple[int, int, int, int],
    estimates: dict[int, int],
    name: str,
    units: int,
    expected: int,
) -> None:
    profile = retreat_intrigue_profile(values, estimates, units)
    assert profile.should_play_retreat_intrigue(name, 2, 6, 2) == expected


@pytest.mark.parametrize(
    ("second_value", "name", "expected"),
    [(5.9, "Reach Agreement", 1), (6.0, "Spice Is Power", 0), (1.0, "Go To Ground", 0)],
)
def test_should_play_retreat_intrigue_expected_second(
    monkeypatch: pytest.MonkeyPatch, second_value: float, name: str, expected: int
) -> None:
    install(monkeypatch, values={"GenericConflictSecondAbility": second_value})
    profile = retreat_intrigue_profile((5, 6, 2, 0), {0: 5, 1: 9, 2: 3, 3: 0})
    assert profile.should_play_retreat_intrigue(name, 2, 6, 2) == expected


def troop_intrigue_profile(
    interest: float,
    *,
    climax: bool = False,
    exp: int = 5,
    opp: tuple[int, int, int] = (0, 0, 0),
    supply: int = 9,
) -> Profile:
    state = with_player(
        base_state(), ME, troops_supply=supply, troops_garrison=12 - supply
    )
    estimates = dict(zip((1, 2, 3), opp, strict=True))
    return stub(
        profile_for(state),
        current_conflict_interest=Summer(interest),
        conflict_posture_bounds=(5.0, 20.0),
        is_climax=climax,
        est_strength=IntSummer(exp),
        est_opponent_strength=lambda s: IntSummer(estimates[s]),
    )


@pytest.mark.parametrize(
    ("interest", "climax", "exp", "opp", "supply", "expected"),
    [
        (0.0, True, 5, (0, 0, 0), 9, 100),
        (20.5, False, 5, (0, 0, 0), 9, 100),
        (20.0, False, 5, (30, 0, 0), 9, 0),  # Mid, far behind
        (5.0, False, 5, (0, 0, 0), 9, 0),  # interest <= lb
        (math.nan, False, 5, (0, 0, 0), 9, 0),
        (10.0, False, 5, (11, 3, 0), 9, 100),  # 6 behind: within notFirstExtra
        (10.0, False, 5, (12, 3, 0), 9, 0),
        (10.0, False, 9, (5, 3, 0), 9, 100),  # 4 ahead: within firstExtra
        (10.0, False, 10, (5, 3, 0), 9, 0),
        (30.0, False, 5, (0, 0, 0), 0, 0),  # supply 0 < troops - 1
        (30.0, False, 5, (0, 0, 0), 1, 100),
    ],
)
def test_should_play_troop_intrigue(
    interest: float,
    climax: bool,
    exp: int,
    opp: tuple[int, int, int],
    supply: int,
    expected: int,
) -> None:
    profile = troop_intrigue_profile(
        interest, climax=climax, exp=exp, opp=opp, supply=supply
    )
    assert profile.should_play_troop_intrigue("Mercenaries", 6, 4, 2) == expected


def test_should_play_troop_intrigue_needs_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(combat, "units_deployment_blocked", lambda state, seat: True)
    profile = troop_intrigue_profile(30.0)
    assert profile.should_play_troop_intrigue("Depart For Arrakis", 6, 4, 3) == 0


@pytest.mark.parametrize(
    ("final", "held", "expected"), [(True, 0, 100), (False, 3, -1), (False, 4, 100)]
)
def test_play_intrigue_for_final_round_or_hand_size(
    final: bool, held: int, expected: int
) -> None:
    cards = tuple(f"intrigue:impress:{i}" for i in range(held))
    state = with_player(base_state(), ME, intrigue_cards=cards)
    profile = stub(profile_for(state), is_final_round=final)
    card = catalog.intrigue_entity("intrigue:impress:0", ME)
    assert profile.play_intrigue_for_final_round_or_hand_size(card) == expected


def test_trash_intrigue_value() -> None:
    bad = catalog.intrigue_entity("intrigue:impress:0", ME)
    profile = stub(profile_for(base_state()), bad_intrigue_cards_in_hand=[bad])
    assert profile.trash_intrigue_value() == 0.0
    profile = stub(profile_for(base_state()), bad_intrigue_cards_in_hand=[])
    assert profile.trash_intrigue_value() == -1.25
