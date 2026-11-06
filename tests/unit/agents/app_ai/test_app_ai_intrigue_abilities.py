"""Intrigue ability ports: spec/intrigues.md (abilities/intrigue.py).

Every test builds a real ``GameState`` (``app_ai.testing``), adjusts the
fields the hook reads and stubs the ``Profile`` methods other areas own with
simple prices, so each expected value can be checked by hand.
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import pytest

from dune_imperium.agents.app_ai.abilities import PORTS, abilities_of
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import intrigue as I
from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    TargetInfo,
    Timing,
)
from dune_imperium.agents.app_ai.catalog import (
    INTRIGUE_ARCHETYPES,
    card_entity,
    conflict_entity,
    contract_entity,
    intrigue_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------

SEAT = 3  # the deciding seat of every fixture below (seed 1)
INFLUENCE = {
    "emperor": 2.0,
    "spacing_guild": 2.5,
    "bene_gesserit": 3.0,
    "fremen": 1.0,
    "none": 3.0,
}
AP = "worm.canis.abilities.PlayAbilities."
SWORDMASTER_POST = "landsraad-high-council-imperial-privilege-swordmaster"
CITY_POSTS = (
    "arrakis-research-station-sietch-tabr",
    "arrakis-research-station-spice-refinery",
    "arrakis-spice-refinery-arrakeen",
)


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "is_climax": lambda: False,
        "is_final_round": lambda: False,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "possible_persuasion": lambda: 5,
        "buy_gains": lambda n: 0.1 * n,
        "trash_card_value": lambda: 2.75,
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.66),
        "recall_spy": lambda spies: (spies[0], 0.0) if spies else (None, 0.0),
        "recall_spies": lambda spies, take: (list(spies[:take]), 0.0),
        "blow_wall_value": lambda: Summer(3.0),
        "intrigue_blow_wall": lambda: False,
        "acquire_value": lambda card: Summer(card.float_attr("TestValue", 3.0)),
        "acquire_cards_by_value": lambda persuasion: [],
        "best_contract": lambda cs, forced: (cs[0], 3.5) if cs else (None, 1.0),
        "best_influence_exchange": lambda lose, gain, lf=None, gf=None: (
            None,
            None,
            0.0,
        ),
        "should_play_retreat_intrigue": lambda name, nf, f, units: 1,
        "should_play_troop_intrigue": lambda name, nf, f, troops: 100,
        "troops_to_retreat": lambda m: min(2, m),
        "est_strength": lambda: IntSummer(5),
        "est_opponent_strength": lambda seat: IntSummer(5),
        "conflict_posture_bounds": lambda: (-2.5, 12.5),
        "current_conflict_interest": lambda: Summer(5.0),
        "estimated_conflict_rank": lambda bonus=0: 2,
        "discard_order": lambda cards, sg: list(cards),
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 3's first ``turn`` decision (round 1, CHOAM on, wall standing)."""

    return first_decision("turn")


@pytest.fixture(scope="module")
def effects_state() -> GameState:
    """Seat 3's first ``agent_effects`` (Arrakeen: deployment window open)."""

    return first_decision("agent_effects")


@pytest.fixture(scope="module")
def reveal_state() -> GameState:
    """Seat 3's first ``reveal`` frame (6 Persuasion)."""

    return first_decision("reveal")


@pytest.fixture(scope="module")
def combat_state() -> GameState:
    """Seat 3's first ``combat_intrigue`` (strengths 6, 7, 5, 7)."""

    return first_decision("combat_intrigue")


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **stub overrides) -> Profile`` for seat 3."""

    def build(state: GameState, **overrides: Callable[..., Any]) -> Profile:
        profile = make_profile(state, SEAT)
        stubs = _base_stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


_FREE_SPACES = ("imperial_basin", "hagga_basin", "deep_desert")


def pl(state: GameState, seat: int, **changes: Any) -> GameState:
    """``with_player`` that keeps the state's invariants.

    Troop changes are balanced in the supply (or the garrison when the
    supply is given), a Swordmaster adds its Agent, fewer available Agents
    are placed on desert spaces, and contracts / won Conflicts leave the
    shared zones.
    """

    p = state.players[seat]
    if any(
        k in changes for k in ("troops_supply", "troops_garrison", "troops_conflict")
    ):
        rest = p.memories + p.specimens + p.troops_parked
        conflict = int(changes.get("troops_conflict", p.troops_conflict))
        if "troops_supply" in changes and "troops_garrison" not in changes:
            supply = int(changes["troops_supply"])
            changes["troops_garrison"] = 12 - supply - conflict - rest
        else:
            garrison = int(changes.get("troops_garrison", p.troops_garrison))
            changes["troops_supply"] = 12 - garrison - conflict - rest
    sword = bool(changes.get("swordmaster_acquired", p.swordmaster_acquired))
    if sword and not p.swordmaster_acquired and "agents_available" not in changes:
        changes["agents_available"] = p.agents_available + 1
    if "agents_available" in changes and "agent_locations" not in changes:
        needed = (3 if sword else 2) - int(changes["agents_available"])
        locations = list(p.agent_locations)
        for space in _FREE_SPACES:
            if len(locations) < needed and space not in locations:
                locations.append(space)
        changes["agent_locations"] = tuple(locations[:needed])
    contracts = {
        *changes.get("completed_contract_ids", ()),
        *changes.get("active_contract_ids", ()),
    }
    if contracts:
        state = with_state(
            state,
            contract_bank=tuple(c for c in state.contract_bank if c not in contracts),
            face_up_contract_ids=tuple(
                c for c in state.face_up_contract_ids if c not in contracts
            ),
            sardaukar_contract_ids=tuple(
                c for c in state.sardaukar_contract_ids if c not in contracts
            ),
        )
    won = set(changes.get("won_conflict_ids", ()))
    if won:
        state = with_state(
            state,
            conflict_deck=tuple(c for c in state.conflict_deck if c not in won),
            unused_conflict_ids=tuple(
                c for c in state.unused_conflict_ids if c not in won
            ),
            current_conflict_ids=tuple(
                c for c in state.current_conflict_ids if c not in won
            ),
        )
    return with_player(state, seat, **changes)


def me(state: GameState, **changes: Any) -> GameState:
    return pl(state, SEAT, **changes)


def set_conflict(state: GameState, conflict_id: str | None) -> GameState:
    """``conflict_id`` face up (taken out of the other zones), or none."""

    current = () if conflict_id is None else (conflict_id,)
    return with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        current_conflict_ids=current,
    )


def synth(kind: Kind, ref: str, **attrs: object) -> Entity:
    archetype = Archetype(
        short=f"Test.{ref}",
        kind="test",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attrs)),
    )
    return Entity(kind, ref, archetype, SEAT)


def card(name: str) -> Entity:
    return intrigue_entity(f"intrigue:{name}:0", SEAT)


def ability[A](name: str, cls: type[A]) -> A:
    for candidate in abilities_of(card(name)):
        if isinstance(candidate, cls):
            return candidate
    raise AssertionError(f"{name} has no {cls.__name__}")


def req(*infos: TargetInfo) -> Request:
    return Request(tuple(infos))


def ents(*entities: Entity) -> TargetInfo:
    return TargetInfo(tuple(entities))


def opts(*options: int) -> TargetInfo:
    return TargetInfo((), tuple(options))


def tracks(*factions: str) -> TargetInfo:
    return ents(*(track_entity(f) for f in factions))


def hold(state: GameState, *names: str) -> GameState:
    return me(state, intrigue_cards=tuple(f"intrigue:{n}:0" for n in names))


def fixed_base(monkeypatch: pytest.MonkeyPatch, value: float | None) -> None:
    """Make ``StrengthIntrigueAbility``'s base Evaluate return ``value``
    (None: the untouched early exit)."""

    def strength_choice(self: I.StrengthIntrigueAbility, p: Profile) -> I._Choice:
        choice = I._Choice()
        if value is not None:
            choice.update_responses(value, ())
        return choice

    monkeypatch.setattr(I.StrengthIntrigueAbility, "_strength_choice", strength_choice)


def place_values(monkeypatch: pytest.MonkeyPatch, values: dict[int, float]) -> None:
    monkeypatch.setattr(
        I, "_placement_value", lambda p, conflict, place: values.get(place, 0.0)
    )


def none(answer: Answer) -> None:
    assert answer.value == 0.0
    assert answer.response is None


# ---------------------------------------------------------------------------
# Registration, coverage and shared machinery
# ---------------------------------------------------------------------------


def test_every_intrigue_ability_class_resolves_to_a_registered_port() -> None:
    for short in INTRIGUE_ARCHETYPES.values():
        if short not in ARCHETYPES:
            continue  # Bloodlines (app-style): test_app_ai_synthetic.py
        archetype = ARCHETYPES[short]
        if not (archetype.in_uprising or archetype.in_uprising_choam):
            continue  # Immortality: covered by the expansion ports.
        ids = archetype.attributes.get("WormAbilityIDs") or archetype.attributes.get(
            "CustomAbilityIDs"
        )
        assert isinstance(ids, tuple) and ids
        for app_class in ids:
            assert app_class in PORTS, (short, app_class)


def test_ports_mirror_the_app_class_chain() -> None:
    assert PORTS[AP + "IntrigueAbility"] is I.IntrigueAbility
    assert PORTS[AP + "StrengthIntrigueAbility"] is I.StrengthIntrigueAbility
    assert issubclass(I.IntrigueAbility, g.PlayAbility)
    assert issubclass(I.StrengthIntrigueAbility, I.IntrigueAbility)
    for cls in (
        I.WeirdingCombatAbility,
        I.TacticalOptionAbility,
        I.GoToGroundAbility,
        I.ReachAgreementAbility,
        I.BackedbyCHOAMCombatAbility,
    ):
        assert issubclass(cls, I.StrengthIntrigueAbility)
    assert not issubclass(I.BuyAccessAbility, I.StrengthIntrigueAbility)
    assert issubclass(I.CunningTrashAbility, g.TrashAbility)
    assert PORTS[AP + "Uprising.CunningTrashAbility"] is I.CunningTrashAbility
    assert I.WeirdingCombatAbility.timing is Timing.COMBAT
    assert I.WeirdingCombatAbility.ability_timing == I.COMBAT_TIMING
    assert I.BuyAccessAbility.ability_timing == I.PLOT_TIMING
    assert I.ShadowAllianceAbility.ability_timing == I.ENDGAME_TIMING
    assert I.CompleteBattleIconPairEndgameAbility.ability_timing == I.ENDGAME_TIMING


def test_choice_update_rules() -> None:
    choice = I._Choice()
    assert choice.answer("x") == Answer(0.0, None, "x")
    choice.update_responses(-1.0, ((0,),))  # first update sticks even when <= 0
    assert choice.answer("x").value == -1.0
    choice.update_responses(-1.0, ((1,),))  # equal: kept
    assert choice.answer("x").response == ((0,),)
    choice.update_responses(150.0, ((1,), (0, 1)))
    assert choice.answer("x") == Answer(150.0, ((1,), (0, 1)), "x")
    empty = I._Choice()
    empty.update_responses(5.0, ())  # stored with an empty response list
    empty.update_responses(1.0, ((2,),))  # an empty stored answer is replaced
    assert empty.answer("y") == Answer(1.0, ((2,),), "y")
    targets = I._Choice()
    targets.update_targets(1.0, ())  # one empty entity list: not empty
    targets.update_targets(1.0, ("emperor",))
    assert targets.answer("z").response == ((),)
    nothing = I._Choice()
    nothing.update_targets(100.0, None)
    assert nothing.answer("n") == Answer(100.0, (), "n")


def test_get_combinations_order_and_budget() -> None:
    assert I.get_combinations(["a", "b", "c"]) == [
        ("a",),
        ("b",),
        ("c",),
        ("a", "b"),
        ("a", "c"),
        ("b", "c"),
        ("a", "b", "c"),
    ]
    assert I.get_combinations(["a", "b", "c"], budget=4) == [
        ("a",),
        ("b",),
        ("c",),
        ("a", "b"),
    ]
    assert I.get_combinations([]) == []
    assert len(I.get_combinations(list(range(7)))) == 127


def test_player_turn_follows_the_own_turn_frame(
    turn_state: GameState,
    effects_state: GameState,
    reveal_state: GameState,
    combat_state: GameState,
) -> None:
    assert I._player_turn(make_profile(turn_state, SEAT)) == 0
    assert I._player_turn(make_profile(effects_state, SEAT)) == 1
    assert I._player_turn(make_profile(reveal_state, SEAT)) == 2
    assert I._player_turn(make_profile(combat_state, SEAT)) == 3
    assert I._player_turn(make_profile(turn_state, 0)) is None  # another seat's


def test_ability_for_prompt_routes_dual_cards() -> None:
    contingency = card("contingency_plan")
    plot = I.ability_for_prompt(contingency, combat_turn=False)
    combat = I.ability_for_prompt(contingency, combat_turn=True)
    assert isinstance(plot, I.ContingencyPlanPlotAbility)
    assert isinstance(combat, I.ContingencyPlanCombatAbility)
    assert isinstance(
        I.ability_for_prompt(card("crysknife"), False), I.GainSpiceIntrigueAbility
    )
    assert I.ability_for_prompt(card("crysknife"), True) is None
    assert I.ability_for_prompt(card("weirding_combat"), False) is None
    cunning = I.ability_for_prompt(card("cunning"), False)
    assert isinstance(cunning, I.CunningAbility)
    shadow = ability("shadow_alliance", I.ShadowAllianceAbility)
    assert shadow.has_matching_timing(4) and not shadow.has_matching_timing(0)


def test_ability_for_placement_reads_the_conflict_place() -> None:
    conflict = conflict_entity("battle_for_arrakeen", True)
    assert isinstance(
        I._ability_for_placement(conflict, 1), g.GenericConflictFirstAbility
    )
    assert isinstance(
        I._ability_for_placement(conflict, 3), g.GenericConflictThirdAbility
    )
    assert I._ability_for_placement(conflict, 4) is None


def test_profile_hooks_read_strength_and_junk_tests(
    combat_state: GameState,
) -> None:
    """Integration with the real profile (no stubs): IntrigueHandStrengthValue
    and GetBadIntrigueCardsInHand reach the ports."""

    state = hold(combat_state, "weirding_combat", "spring_the_trap", "contingency_plan")
    state = me(state, spy_post_ids=(), spies_supply=3)
    p = make_profile(state, SEAT)
    assert p.intrigue_hand_strength_value() == 3 + 0 + 3
    bad = p.bad_intrigue_cards_in_hand()
    assert [c.ref for c in bad] == ["intrigue:spring_the_trap:0"]
    assert p.trash_intrigue_value() == 0.0


# ---------------------------------------------------------------------------
# StrengthIntrigueAbility (spec §5)
# ---------------------------------------------------------------------------


def test_strength_value_and_combat_value_defaults(combat_state: GameState) -> None:
    p = make_profile(combat_state, SEAT)
    contingency = ability("contingency_plan", I.ContingencyPlanCombatAbility)
    assert contingency.strength_value(p) == 3
    assert contingency.combat_value(p) == 0.0  # attribute absent
    go = ability("go_to_ground", I.GoToGroundAbility)
    assert go.strength_value(p) == 0 and go.combat_value(p) == 0.0
    weirding = ability("weirding_combat", I.WeirdingCombatAbility)
    assert weirding.combat_value(p) == 3.0
    assert weirding.strength_value(p) == 3
    bg = make_profile(me(combat_state, influence=Influence(bene_gesserit=3)), SEAT)
    assert weirding.strength_value(bg) == 5
    backed = ability("backed_by_choam", I.BackedbyCHOAMCombatAbility)
    assert backed.strength_value(p) == 0 and not backed.can_be_run(p)
    two = make_profile(
        me(
            combat_state,
            completed_contract_ids=("contract:acquire", "contract:immediate"),
        ),
        SEAT,
    )
    assert backed.strength_value(two) == 4 and backed.can_be_run(two)
    assert not backed.is_bad_intrigue(p)


def test_strength_evaluate_early_exits(combat_state: GameState) -> None:
    weirding = ability("weirding_combat", I.WeirdingCombatAbility)
    no_conflict = set_conflict(combat_state, None)
    none(weirding.evaluate(make_profile(no_conflict, SEAT), req()))
    out = make_profile(me(combat_state, combat_strength=0), SEAT)
    none(weirding.evaluate(out, req()))
    trap = ability("spring_the_trap", I.SpringTheTrapAbility)  # sv 0 without spies
    none(trap.evaluate(make_profile(combat_state, SEAT), req()))


def test_strength_evaluate_holds_while_sole_first(combat_state: GameState) -> None:
    state = hold(me(combat_state, combat_strength=9), "weirding_combat")
    weirding = ability("weirding_combat", I.WeirdingCombatAbility)
    assert weirding.evaluate(make_profile(state, SEAT), req()).value == -1.0
    # Tied first (seat 1 also has 7) drops a place: not "sole first".
    tied = make_profile(hold(combat_state, "weirding_combat"), SEAT)
    assert tied.current_conflict_rank(0) == 2


def test_strength_evaluate_dumps_when_decisive(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    place_values(monkeypatch, {})  # no improving combination otherwise
    weirding = ability("weirding_combat", I.WeirdingCombatAbility)
    state = hold(combat_state, "weirding_combat")
    last = with_state(state, conflict_deck=())
    answer = weirding.evaluate(make_profile(last, SEAT), req())
    assert answer == Answer(97.0, (), "WeirdingCombatAbility strength")
    # The strongest player (seat 1 first among the 7s) has 10 VP.
    leader = pl(state, 1, victory_points=10)
    assert weirding.evaluate(make_profile(leader, SEAT), req()).value == 97.0
    # Seat 3 also has 7 but comes after seat 1: its own 10 VP do not count.
    own = me(state, victory_points=10)
    assert weirding.evaluate(make_profile(own, SEAT), req()).value == 0.0


def test_strength_evaluate_first_improving_combination(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    place_values(monkeypatch, {1: 10.0, 2: 5.0, 3: 2.0})
    state = hold(combat_state, "contingency_plan", "weirding_combat")
    p = make_profile(state, SEAT)
    contingency = ability("contingency_plan", I.ContingencyPlanCombatAbility)
    weirding = ability("weirding_combat", I.WeirdingCombatAbility)
    # (CP,) alone takes first place: 10 > 0 + 5.
    assert contingency.evaluate(p, req()).value == 10.0
    assert weirding.evaluate(p, req()).value == 0.0
    # Only the pair beats seat 1 at 12: 10 > (0 + 3) + 5, both members.
    behind = make_profile(pl(state, 1, combat_strength=12), SEAT)
    assert contingency.evaluate(behind, req()).value == 10.0
    assert weirding.evaluate(behind, req()).value == 7.0
    # The pair improves the place but costs too much: 7 > 3 + 5 fails.
    place_values(monkeypatch, {1: 7.0, 2: 5.0})
    assert weirding.evaluate(behind, req()).value == 0.0


def test_strength_evaluate_ignores_unplayable_or_absent_cards(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    place_values(monkeypatch, {1: 10.0, 2: 5.0})
    # Spring the Trap (sv 0 without spies) is dropped from the combinations;
    # an ability whose card is not in hand is never a member.
    state = hold(combat_state, "spring_the_trap", "contingency_plan")
    p = make_profile(state, SEAT)
    weirding = ability("weirding_combat", I.WeirdingCombatAbility)
    assert weirding.evaluate(p, req()).value == 0.0
    contingency = ability("contingency_plan", I.ContingencyPlanCombatAbility)
    assert contingency.evaluate(p, req()).value == 10.0


# ---------------------------------------------------------------------------
# Combat wrappers (spec §6)
# ---------------------------------------------------------------------------


def test_tactical_option(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    tactical = ability("tactical_option", I.TacticalOptionAbility)
    request = req(opts(0, 1), opts(0, 1, 2, 3))
    fixed_base(monkeypatch, 8.0)
    p = prof(combat_state)
    assert tactical.combat_value(p) == 2.0  # StrengthValue, not the 1.0 attribute
    assert tactical.evaluate(p, request).response == ((0,),)
    assert tactical.evaluate(p, request).value == 8.0
    lead = me(combat_state, combat_strength=20)
    answer = tactical.evaluate(prof(lead), request)
    assert answer.value == 150.0 and answer.response == ((1,), (0, 1))
    # A close opponent (exactly one sword ahead), climax, a lead under 10, or
    # no troop to pull keep the strength answer.
    close = pl(lead, 0, combat_strength=21)
    assert tactical.evaluate(prof(close), request).value == 8.0
    assert tactical.evaluate(prof(lead, is_climax=lambda: True), request).value == 8.0
    small = me(combat_state, combat_strength=16)  # 16 - 7 < 10
    assert tactical.evaluate(prof(small), request).value == 8.0
    stay = prof(lead, troops_to_retreat=lambda m: 0)
    assert tactical.evaluate(stay, request).value == 8.0
    fixed_base(monkeypatch, -1.0)
    sole = tactical.evaluate(prof(combat_state), request)
    assert sole == Answer(-1.0, ((0,),), sole.label)


def test_questionable_methods(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    qm = ability("questionable_methods", I.QuestionableMethodsAbility)
    p = prof(combat_state)
    assert qm.strength_value(p) == 1 and qm.combat_value(p) == 1.0
    some = prof(me(combat_state, influence=Influence(fremen=1)))
    assert qm.strength_value(some) == 5 and qm.combat_value(some) == 5.0
    fixed_base(monkeypatch, 5.0)
    answer = qm.evaluate(p, req(tracks("spacing_guild", "emperor")))
    assert answer.value == pytest.approx(4.8)  # 0.1 * -2.0 + 5 beats 4.75
    assert answer.response == (("emperor",),)
    assert qm.evaluate(p, req()) == Answer(5.0, ((),), "Questionable Methods")
    fixed_base(monkeypatch, 0.5)
    costly = prof(
        combat_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(-10.0)
    )
    baseline = qm.evaluate(costly, req(tracks("emperor")))
    assert baseline.value == 1.0 and baseline.response == ((),)
    fixed_base(monkeypatch, -1.0)
    assert qm.evaluate(p, req(tracks("emperor"))) == Answer(
        -1.0, (), "Questionable Methods base"
    )


def test_impress(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    impress = ability("impress", I.ImpressAbility)
    fixed_base(monkeypatch, -1.0)
    p = prof(combat_state)
    assert impress.evaluate(p, req()) == Answer(-1.0, (), "Impress no target")
    low = synth(Kind.CARD, "low", TestValue=2.0)
    high = synth(Kind.CARD, "high", TestValue=12.0)
    tie = synth(Kind.CARD, "tie", TestValue=12.0)
    answer = impress.evaluate(p, req(ents(low, high, tie)))
    assert answer.value == pytest.approx(0.2)  # 0.1 * 12 - 1: played while first
    assert answer.response == (("high",),)


def test_devour(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    devour = ability("devour", I.DevourAbility)
    fixed_base(monkeypatch, 0.0)
    p = prof(combat_state)
    assert devour.strength_value(p) == 2
    assert devour.evaluate(p, req()) == Answer(0.0, (), "Devour")
    worm = me(combat_state, sandworms_conflict=1)
    dagger = card_entity("player:3:starter:dagger:0", SEAT)
    trash = prof(worm, card_to_trash=lambda targets, m: (targets[0], 10.5))
    assert devour.strength_value(trash) == 4
    answer = devour.evaluate(trash, req(ents(dagger)))
    assert answer.value == 10.5 and answer.response == ((dagger.ref,),)
    assert devour.evaluate(prof(worm), req(ents(dagger))).response == ((),)
    assert not devour.is_bad_intrigue(prof(combat_state))
    assert devour.is_bad_intrigue(prof(combat_state, is_climax=lambda: True))
    hooks = me(combat_state, maker_hooks=True)
    assert not devour.is_bad_intrigue(prof(hooks, is_climax=lambda: True))


def test_find_weakness(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    weakness = ability("find_weakness", I.FindWeaknessAbility)
    p = prof(combat_state)
    assert weakness.strength_value(p) == 2
    fixed_base(monkeypatch, 0.0)
    none(weakness.evaluate(p, req(ents())))
    spied = me(combat_state, spy_post_ids=(SWORDMASTER_POST,), spies_supply=2)
    spy = spy_entity(SWORDMASTER_POST, SEAT)
    answer = weakness.evaluate(prof(spied), req(ents(spy)))
    assert answer.value == pytest.approx(0.1)
    assert answer.response == ((SWORDMASTER_POST,),)
    assert weakness.strength_value(prof(spied)) == 5
    fixed_base(monkeypatch, -1.0)
    assert weakness.evaluate(prof(spied), req(ents(spy))).value == pytest.approx(-0.9)


def test_spring_the_trap(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    trap = ability("spring_the_trap", I.SpringTheTrapAbility)
    posts = (SWORDMASTER_POST, CITY_POSTS[0])
    spied = me(combat_state, spy_post_ids=posts, spies_supply=1)
    p = prof(spied)
    assert trap.meets_cost(p) and trap.strength_value(p) == 7
    assert not trap.is_bad_intrigue(p)
    assert trap.is_bad_intrigue(prof(combat_state))
    spies = ents(*(spy_entity(post, SEAT) for post in posts))
    fixed_base(monkeypatch, 3.0)
    assert trap.evaluate(p, req(spies)) == Answer(3.0, (posts,), "Spring the Trap")
    none(trap.evaluate(p, req(ents(spy_entity(posts[0], SEAT)))))
    fixed_base(monkeypatch, 0.0)
    none(trap.evaluate(p, req(spies)))


def test_spice_is_power(
    combat_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    power = ability("spice_is_power", I.SpiceIsPowerAbility)
    fixed_base(monkeypatch, 4.0)
    poor = me(combat_state, resources=Resources(spice=0), troops_conflict=2)
    assert not power.meets_cost(prof(poor))
    rich = me(combat_state, resources=Resources(spice=3), troops_conflict=2)
    assert power.meets_cost(prof(rich)) and power.strength_value(prof(rich)) == 6
    assert power.evaluate(prof(rich), req()).response == ((1,),)
    both = me(combat_state, resources=Resources(spice=3), troops_conflict=3)
    assert power.evaluate(prof(both), req()) == Answer(150.0, ((0,),), "Spice Is Power")
    no = prof(both, should_play_retreat_intrigue=lambda *a: 0)
    assert power.evaluate(no, req()).value == 4.0
    troops = me(combat_state, resources=Resources(spice=0), troops_conflict=3)
    assert power.meets_cost(prof(troops))
    assert power.evaluate(prof(troops), req()).response == ((0,),)
    none(power.evaluate(prof(poor), req()))
    assert not power.is_bad_intrigue(prof(poor))


def test_go_to_ground(combat_state: GameState, prof: ProfileFactory) -> None:
    ground = ability("go_to_ground", I.GoToGroundAbility)
    request = req(opts(0, 1, 2), ents(), ents())
    answer = ground.evaluate(prof(combat_state), request)
    assert answer.value == 1.66 and answer.response == ((0, 1),)
    none(
        ground.evaluate(
            prof(combat_state, should_play_retreat_intrigue=lambda *a: 0), request
        )
    )
    none(ground.evaluate(prof(combat_state, troops_to_retreat=lambda m: 0), request))
    two = me(combat_state, spy_post_ids=CITY_POSTS[:2], spies_supply=1)
    assert ground.is_bad_intrigue(prof(two))
    assert not ground.is_bad_intrigue(prof(combat_state))


def test_reach_agreement(combat_state: GameState, prof: ProfileFactory) -> None:
    reach = ability("reach_agreement", I.ReachAgreementAbility)
    contract = contract_entity("contract:acquire")
    answer = reach.evaluate(prof(combat_state), req(opts(0, 1), ents(contract)))
    assert answer.value == 1.0 and answer.response == ((0, 1), ("contract:acquire",))
    bare = reach.evaluate(prof(combat_state), req(opts(0, 1), ents()))
    assert bare.value == 1.0 and bare.response == ((0, 1),)
    picky = prof(combat_state, best_contract=lambda cs, forced: (None, 0.0))
    none(reach.evaluate(picky, req(opts(0, 1), ents(contract))))
    none(
        reach.evaluate(prof(combat_state, troops_to_retreat=lambda m: 0), req(opts(0)))
    )
    none(
        reach.evaluate(
            prof(combat_state, should_play_retreat_intrigue=lambda *a: 0), req(opts(0))
        )
    )
    assert reach.is_bad_intrigue(prof(combat_state, is_climax=lambda: True))


# ---------------------------------------------------------------------------
# Plot intrigues (spec §7)
# ---------------------------------------------------------------------------


def test_backed_by_choam_plot(turn_state: GameState, prof: ProfileFactory) -> None:
    backed = ability("backed_by_choam", I.BackedByCHOAMPlotAbility)
    request = req(tracks("emperor", "fremen"))
    short = me(turn_state, resources=Resources(solari=4))  # Swordmaster 8: -4
    answer = backed.evaluate(prof(short), request)
    # The least painful loss: fremen (-1.0) + 100.
    assert answer.value == 99.0 and answer.response == (("fremen",),)
    assert "Swordmaster" in answer.label
    hc = me(turn_state, resources=Resources(solari=2))  # HC 5: -3
    assert "High Council" in backed.evaluate(prof(hc), request).label
    none(backed.evaluate(prof(turn_state), request))  # 8 and 5 Solari short
    seated = me(turn_state, resources=Resources(solari=2), high_council=True)
    none(backed.evaluate(prof(seated), request))  # no contract need either
    behind = pl(
        me(seated, influence=Influence(emperor=3)), 0, influence=Influence(emperor=5)
    )
    assert "No completed contracts" in backed.evaluate(prof(behind), request).label
    done = me(behind, completed_contract_ids=("contract:acquire",))
    none(backed.evaluate(prof(done), request))
    none(backed.evaluate(prof(me(short, swordmaster_acquired=True)), request))
    none(backed.evaluate(prof(me(effects_like(short), agents_available=1)), request))
    assert not backed.is_bad_intrigue(prof(turn_state))
    assert backed.is_bad_intrigue(prof(turn_state, is_climax=lambda: True))
    two = me(
        turn_state, completed_contract_ids=("contract:acquire", "contract:immediate")
    )
    assert not backed.is_bad_intrigue(prof(two, is_climax=lambda: True))


def effects_like(state: GameState) -> GameState:
    """``state`` with its top ``turn`` frame relabelled ``agent_effects``."""

    frame = state.decision_stack[-1]
    relabelled = replace(frame, kind=FrameKind.AGENT_EFFECTS)
    return with_state(state, decision_stack=(*state.decision_stack[:-1], relabelled))


def test_buy_access(turn_state: GameState, prof: ProfileFactory) -> None:
    buy = ability("buy_access", I.BuyAccessAbility)
    request = req(tracks("emperor", "spacing_guild", "bene_gesserit", "fremen"))
    none(buy.evaluate(prof(turn_state), req()))
    none(buy.evaluate(prof(turn_state), request))  # neither Swordmaster nor climax
    climax = buy.evaluate(prof(turn_state, is_climax=lambda: True), request)
    assert climax.value == 1.0
    assert climax.response == (("bene_gesserit", "spacing_guild"),)
    sword = me(turn_state, swordmaster_acquired=True)
    none(buy.evaluate(prof(sword), request))  # best +1 is 3.0 < 3.75
    weak = prof(sword, gain_influence_value=lambda f, n, r=-1, a=False: Summer(3.5))
    none(buy.evaluate(weak, request))
    assert buy.is_bad_intrigue(prof(turn_state))  # no Swordmaster, Solari 0 < 3
    rich = me(turn_state, resources=Resources(solari=5))
    assert not buy.is_bad_intrigue(prof(rich))  # 2.5 >= 3.0 fails
    low = prof(rich, gain_influence_value=lambda f, n, r=-1, a=False: Summer(2.5))
    assert buy.is_bad_intrigue(low)
    assert buy.meets_cost(prof(rich)) and not buy.meets_cost(prof(turn_state))


def test_buy_access_threshold_is_inclusive(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    buy = ability("buy_access", I.BuyAccessAbility)
    sword = me(turn_state, swordmaster_acquired=True)
    exact = prof(sword, gain_influence_value=lambda f, n, r=-1, a=False: Summer(3.75))
    answer = buy.evaluate(exact, req(tracks("emperor", "fremen")))
    assert answer.value == 1.0 and answer.response is not None
    assert sorted(str(ref) for ref in answer.response[0]) == ["emperor", "fremen"]


def test_call_to_arms(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    arms = ability("call_to_arms", I.CallToArmsAbility)
    none(arms.evaluate(prof(turn_state), req()))
    assert (
        arms.evaluate(prof(reveal_state, is_final_round=lambda: True), req()).value
        == 100.0
    )
    none(arms.evaluate(prof(reveal_state), req()))  # no affordable card
    cheap = synth(Kind.CARD, "cheap", PersuasionCost=4)
    dear = synth(Kind.CARD, "dear", PersuasionCost=5)
    good = prof(reveal_state, acquire_cards_by_value=lambda n: [cheap, dear])
    assert arms.evaluate(good, req()) == Answer(100.0, (), "Call to Arms| 100")
    tight = prof(reveal_state, acquire_cards_by_value=lambda n: [dear, cheap])
    none(arms.evaluate(tight, req()))  # 6 - 5 < 2
    assert arms.is_bad_intrigue(prof(me(turn_state, troops_garrison=6)))
    assert not arms.is_bad_intrigue(prof(turn_state))


def test_change_allegiances(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    change = ability("change_allegiances", I.ChangeAllegiancesAbility)
    request = req(tracks("emperor", "fremen"))
    swap = prof(
        turn_state, best_influence_exchange=lambda *a: ("fremen", "emperor", 2.0)
    )
    assert change.evaluate(swap, request) == Answer(
        2.0, (("fremen",),), "Change Allegiance"
    )
    weak = prof(
        turn_state, best_influence_exchange=lambda *a: ("fremen", "emperor", 1.9)
    )
    none(change.evaluate(weak, request))
    spice = me(reveal_state, resources=Resources(spice=3))
    climax = prof(
        spice,
        is_climax=lambda: True,
        best_influence_exchange=lambda *a: ("fremen", "emperor", 1.9),
    )
    assert change.evaluate(climax, request).value == 10.0
    assert change.evaluate(climax, request).response == (("fremen",),)
    final = prof(spice, is_final_round=lambda: True)
    assert change.evaluate(final, request).response == ((),)  # no lose track found
    assert change.evaluate(final, req()).response == ()
    none(change.evaluate(prof(reveal_state, is_climax=lambda: True), request))
    assert not change.meets_cost(prof(turn_state))
    assert change.meets_cost(prof(spice))
    assert change.meets_cost(prof(me(turn_state, influence=Influence(fremen=1))))


def test_choose_faction_influence(turn_state: GameState, prof: ProfileFactory) -> None:
    answer = I.choose_faction_influence(
        prof(turn_state), [track_entity("emperor"), track_entity("bene_gesserit")]
    )
    assert answer.value == 103.0 and answer.response == (("bene_gesserit",),)


def test_contingency_plan_plot(turn_state: GameState, prof: ProfileFactory) -> None:
    plan = ability("contingency_plan", I.ContingencyPlanPlotAbility)
    for solari in (6, 7):
        state = me(turn_state, resources=Resources(solari=solari))
        assert plan.evaluate(prof(state), req()) == Answer(
            100.0, (), "Contingency Plan (Swordmaster) | 100"
        )
    none(plan.evaluate(prof(me(turn_state, resources=Resources(solari=5))), req()))
    hc = me(turn_state, resources=Resources(solari=3))
    assert plan.evaluate(prof(hc), req()).label.endswith("(High Council) | 100")
    none(plan.evaluate(prof(me(hc, high_council=True)), req()))
    none(plan.evaluate(prof(with_state(hc, round_number=6)), req()))
    sm = me(turn_state, resources=Resources(solari=6))
    taken = pl(sm, 0, agent_locations=("swordmaster",), agents_available=1)
    none(plan.evaluate(prof(taken), req()))
    watched = me(taken, spy_post_ids=(SWORDMASTER_POST,), spies_supply=2)
    assert plan.evaluate(prof(watched), req()).value == 100.0
    after = pl(sm, 0, swordmaster_acquired=True)  # Swordmaster now 6
    none(plan.evaluate(prof(after), req()))  # 6 - 6 = 0
    none(plan.evaluate(prof(me(sm, swordmaster_acquired=True)), req()))
    none(plan.evaluate(prof(me(sm, agents_available=0)), req()))
    assert not plan.is_bad_intrigue(prof(turn_state))


def test_councilors_ambition(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    ambition = ability("councilor_s_ambition", I.CouncilorsAmbitionAbility)
    assert ambition.evaluate(prof(turn_state), req()).value == 2.0  # water(2)
    none(ambition.evaluate(prof(effects_state), req()))
    full = hold(
        effects_state, "councilor_s_ambition", "cunning", "detonation", "devour"
    )
    assert ambition.evaluate(prof(full), req()).value == 2.0
    final = prof(effects_state, is_final_round=lambda: True)
    assert ambition.evaluate(final, req()).value == 2.0
    seated = me(turn_state, high_council=True, resources=Resources(water=2))
    assert ambition.meets_cost(prof(seated)) and not ambition.meets_cost(
        prof(turn_state)
    )
    assert not ambition.is_bad_intrigue(prof(seated))
    assert ambition.is_bad_intrigue(prof(turn_state))
    assert ambition.is_bad_intrigue(prof(me(seated, resources=Resources(water=3))))
    assert ambition.is_bad_intrigue(prof(seated, is_climax=lambda: True))


def test_gain_spice_intrigue(turn_state: GameState, prof: ProfileFactory) -> None:
    crysknife = ability("crysknife", I.GainSpiceIntrigueAbility)
    mouse = ability("desert_mouse", I.GainSpiceIntrigueAbility)
    plain = me(turn_state, objective_ids=("objective_ornithopter_1_3p",))
    assert crysknife.battle_icon() == "Crysknife"
    assert crysknife.evaluate(prof(plain), req()) == Answer(
        100.0, (), "Intrigue Crysknife for Spice | 100"
    )
    # The current conflict (Skirmish: Desert Mouse) shows this icon: keep.
    none(mouse.evaluate(prof(plain), req()))
    paired = me(turn_state, objective_ids=("objective_crysknife_1",))
    none(crysknife.evaluate(prof(paired), req()))  # an owned match: keep
    wild = me(plain, won_conflict_ids=("propaganda",))
    none(crysknife.evaluate(prof(wild), req()))  # an owned wildcard: keep
    rich = me(plain, resources=Resources(spice=5))
    none(crysknife.evaluate(prof(rich), req()))
    assert (
        crysknife.evaluate(prof(rich, is_final_round=lambda: True), req()).value
        == 100.0
    )


def test_gain_spice_intrigue_is_bad(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    crysknife = ability("crysknife", I.GainSpiceIntrigueAbility)
    mouse = ability("desert_mouse", I.GainSpiceIntrigueAbility)
    plain = me(turn_state, objective_ids=("objective_ornithopter_1_3p",))
    assert not crysknife.is_bad_intrigue(prof(plain))  # not climax
    climax = {"is_climax": lambda: True}
    assert crysknife.is_bad_intrigue(prof(plain, **climax))
    paired = me(turn_state, objective_ids=("objective_crysknife_1",))
    assert not crysknife.is_bad_intrigue(prof(paired, **climax))
    first = {"estimated_conflict_rank": lambda bonus=0: 1, **climax}
    assert not mouse.is_bad_intrigue(
        prof(plain, **first)
    )  # conflict shows Desert Mouse
    assert crysknife.is_bad_intrigue(prof(plain, **first))
    wild = set_conflict(plain, "propaganda")
    assert not crysknife.is_bad_intrigue(prof(wild, **first))  # Wildcard accepted
    combat = ability("crysknife", I.CompleteBattleIconPairEndgameAbility)
    assert not combat.is_bad_intrigue(prof(plain, **climax))


def test_cunning(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    cunning = ability("cunning", I.CunningAbility)
    none(cunning.evaluate(prof(turn_state), req()))  # no spice at turn start
    spice = me(turn_state, resources=Resources(spice=1))
    answer = cunning.evaluate(prof(spice), req())
    assert answer.value == pytest.approx(1.8) and answer.response == ((0,),)
    dagger = card_entity("player:3:starter:dagger:0", SEAT)
    trash = prof(spice, card_to_trash=lambda targets, m: (dagger, 5.0))
    answer = cunning.evaluate(trash, req())
    assert answer.value == pytest.approx(5.0 + (2.75 + (1.8 - 0.5)))
    assert answer.response == ((1,),)
    cheap = prof(
        spice, card_to_trash=lambda t, m: (dagger, 5.0), trash_card_value=lambda: 0.5
    )
    assert cunning.evaluate(cheap, req()).response == ((0,),)  # 0.5 > 0.5 fails
    assert (
        cunning.evaluate(prof(reveal_state, buy_gains=lambda n: 1.0), req()).value
        == 2.5
    )
    none(cunning.evaluate(prof(reveal_state, buy_gains=lambda n: 0.99), req()))
    assert cunning.meets_cost(prof(turn_state))
    empty = me(turn_state, deck=(), discard_pile=(), hand=(), in_play=())
    assert not cunning.meets_cost(prof(empty))
    assert not cunning.is_bad_intrigue(prof(turn_state))


def test_cunning_trash_uses_the_trash_ability(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    trash = ability("cunning", I.CunningTrashAbility)
    dagger = card_entity("player:3:starter:dagger:0", SEAT)
    p = prof(turn_state, card_to_trash=lambda targets, m: (targets[0], 4.0))
    assert trash.evaluate(p, req(ents(dagger))).response == ((dagger.ref,),)


def test_depart_for_arrakis(
    effects_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    depart = ability("depart_for_arrakis", I.DepartForArrakisAbility)
    ready = me(
        effects_state,
        resources=Resources(spice=2),
        influence=Influence(spacing_guild=3),
    )
    assert depart.evaluate(prof(ready), req()).response == ((1,),)
    assert depart.evaluate(prof(ready), req()).value == 100.0
    none(depart.evaluate(prof(ready, should_play_troop_intrigue=lambda *a: 0), req()))
    final_deploy = prof(
        ready, should_play_troop_intrigue=lambda *a: 0, is_final_round=lambda: True
    )
    assert depart.evaluate(final_deploy, req()).response == ((1,),)
    guild = me(reveal_state, influence=Influence(spacing_guild=3))
    final = {"is_final_round": lambda: True}
    assert depart.evaluate(prof(guild, **final), req()) == Answer(
        100.0, (), "Depart For Arrakis | 100 | Draw only"
    )
    paid = me(guild, resources=Resources(spice=2))
    assert depart.evaluate(prof(paid, **final), req()).response == ((0,),)
    none(depart.evaluate(prof(guild), req()))
    no_guild = me(effects_state, resources=Resources(spice=4))
    none(depart.evaluate(prof(no_guild), req()))  # never without Guild 3
    assert depart.meets_cost(prof(no_guild)) and not depart.meets_cost(
        prof(effects_state)
    )


def test_intrigue_deploy_troops(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    troops = (0, 1, 2, 3)
    state = pl(reveal_state, 0, troops_conflict=2)
    state = pl(state, 1, troops_conflict=0, sandworms_conflict=0)
    state = pl(state, 2, troops_conflict=1)
    state = me(state, troops_garrison=4)
    strengths = {0: 8, 1: 20, 2: 1}  # est_strength (exp) is 5

    def build(**overrides: Callable[..., Any]) -> Profile:
        stubs: dict[str, Callable[..., Any]] = {
            "est_opponent_strength": lambda seat: IntSummer(strengths[seat])
        }
        stubs.update(overrides)
        return prof(state, **stubs)

    # Mid posture: the top (20) is more than 5 away; the second (8) is
    # within 3: ceil((8 - 5 + 4) * 0.5) = 4.
    assert I.intrigue_deploy_troops(build(), troops) == 4
    assert I.intrigue_deploy_troops(build(is_final_round=lambda: True), (0, 1)) == 2
    assert I.intrigue_deploy_troops(prof(turn_state), troops) == 0  # not Reveal
    assert I.intrigue_deploy_troops(prof(me(state, troops_garrison=0)), troops) == 0
    low = build(current_conflict_interest=lambda: Summer(-2.5))  # not > lb
    assert I.intrigue_deploy_troops(low, troops) == 0
    nan = build(current_conflict_interest=lambda: Summer(math.nan))
    assert I.intrigue_deploy_troops(nan, troops) == 0
    # One troop: seat 0 (8, in the Conflict) is more than 2 x 1 away.
    assert I.intrigue_deploy_troops(build(), (0,)) == 0
    strengths[1] = 0  # top 8 within 5: ceil((8 - 5 + 4) * 0.5) = 4
    assert I.intrigue_deploy_troops(build(), troops) == 4
    # High posture: ceil((8 - 5 + 7) * 0.5) = 5 > 4 troops -> the smallest k
    # improving EstimatedConflictRank (k passed as strength).
    high = build(
        current_conflict_interest=lambda: Summer(20.0),
        estimated_conflict_rank=lambda bonus=0: 3 if bonus < 2 else 2,
    )
    assert I.intrigue_deploy_troops(high, troops) == 2
    flat = build(
        current_conflict_interest=lambda: Summer(20.0),
        estimated_conflict_rank=lambda bonus=0: 3,
    )
    assert I.intrigue_deploy_troops(flat, troops) == 0
    strengths.update({0: 12, 1: 20, 2: 20})  # nobody within 6 / 5 / 3 of 5
    far = build(current_conflict_interest=lambda: Summer(20.0))
    assert I.intrigue_deploy_troops(far, troops) == 0
    assert I.intrigue_deploy_troops(build(), troops) == 0


def test_detonation(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    detonation = ability("detonation", I.DetonationAbility)
    blow = prof(turn_state, intrigue_blow_wall=lambda: True)
    assert detonation.evaluate(blow, req()) == Answer(
        100.0, ((0,),), "Detonation | 100 | Blow Wall"
    )
    monkeypatch.setattr(I, "intrigue_deploy_troops", lambda p, troops: 2)
    both = req(opts(0, 1), opts(0, 1, 2))
    assert detonation.evaluate(prof(turn_state), both).response == ((1,), (0, 1))
    no_wall = with_state(turn_state, shield_wall_present=False)
    answer = detonation.evaluate(prof(no_wall), req(opts(0, 1, 2)))
    assert answer.value == 100.0 and answer.response == ((0, 1),)
    none(detonation.evaluate(prof(me(turn_state, troops_garrison=0)), both))
    monkeypatch.setattr(I, "intrigue_deploy_troops", lambda p, troops: 0)
    none(detonation.evaluate(prof(turn_state), both))
    monkeypatch.setattr(I, "units_deployment_blocked", lambda state, seat: True)
    none(detonation.evaluate(prof(turn_state), both))
    assert detonation.meets_cost(prof(turn_state))  # the wall still stands
    assert not detonation.meets_cost(prof(no_wall))
    assert not detonation.is_bad_intrigue(prof(turn_state))  # garrison 3
    two = me(turn_state, troops_garrison=2)
    assert detonation.is_bad_intrigue(prof(two))  # no hooks
    assert not detonation.is_bad_intrigue(prof(me(two, maker_hooks=True)))


def test_distraction(effects_state: GameState, prof: ProfileFactory) -> None:
    distraction = ability("distraction", I.DistractionAbility)
    assert distraction.evaluate(prof(effects_state), req()) == Answer(
        1.66, (), "Distraction"
    )
    three = me(effects_state, spy_post_ids=CITY_POSTS, spies_supply=0)
    none(distraction.evaluate(prof(three), req()))
    assert distraction.is_bad_intrigue(prof(three))
    assert not distraction.is_bad_intrigue(prof(effects_state))
    assert not distraction.meets_cost(prof(effects_state))
    assert distraction.meets_cost(prof(me(effects_state, units_deployed_peak=3)))


def test_imperium_politics(turn_state: GameState, prof: ProfileFactory) -> None:
    politics = ability("imperium_politics", I.ImperiumPoliticsAbility)
    request = req(tracks("emperor", "spacing_guild"))
    answer = politics.evaluate(prof(turn_state), request)
    assert answer.value == 12.5 and answer.response == (("spacing_guild",),)
    awful = {"emperor": -8.0, "spacing_guild": -9.0}
    p = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(awful[f])
    )
    none(politics.evaluate(p, request))  # 10 - 8 < 3.0 threshold
    climax = prof(
        turn_state,
        is_climax=lambda: True,
        gain_influence_value=lambda f, n, r=-1, a=False: Summer(awful[f]),
    )
    assert politics.evaluate(climax, request).value == 2.0
    assert politics.meets_cost(prof(me(turn_state, resources=Resources(solari=1))))
    assert not politics.meets_cost(prof(turn_state))
    full = me(
        turn_state,
        resources=Resources(solari=1),
        influence=Influence(emperor=6, spacing_guild=6),
    )
    assert not politics.meets_cost(prof(full))


def test_inspire_awe(turn_state: GameState, prof: ProfileFactory) -> None:
    awe = ability("inspire_awe", I.InspireAweAbility)
    good = synth(Kind.CARD, "good", TestValue=3.0)
    meh = synth(Kind.CARD, "meh", TestValue=2.6)
    reserve = synth(Kind.CARD, "reserve", TestValue=2.6, ImperiumType="Reserve")
    answer = awe.evaluate(prof(turn_state), req(ents(meh, good)))
    assert answer.value == 3.0 and answer.response == (("good",), (0,))
    none(awe.evaluate(prof(turn_state), req(ents(meh, reserve))))
    worm = me(turn_state, sandworms_conflict=1)
    assert awe.evaluate(prof(worm), req(ents(meh, reserve))).response == (
        ("reserve",),
        (0,),
    )
    none(awe.evaluate(prof(turn_state), req()))
    assert awe.is_bad_intrigue(prof(turn_state, is_climax=lambda: True))
    assert not awe.is_bad_intrigue(
        prof(me(turn_state, maker_hooks=True), is_climax=lambda: True)
    )


def test_intelligence_report(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    report = ability("intelligence_report", I.IntelligenceReportAbility)
    none(report.evaluate(prof(turn_state), req()))  # fewer than 2 spies
    spies = me(turn_state, spy_post_ids=CITY_POSTS[:2], spies_supply=1)
    assert report.evaluate(prof(spies), req()).value == pytest.approx(0.3 * 2.0)
    one = me(reveal_state, spy_post_ids=CITY_POSTS[:1], spies_supply=2)
    assert report.evaluate(prof(one, buy_gains=lambda n: 1.2), req()).value == 1.2
    none(report.evaluate(prof(one, buy_gains=lambda n: 0.5), req()))
    assert report.is_bad_intrigue(prof(turn_state))
    assert not report.is_bad_intrigue(prof(one))
    assert report.meets_cost(prof(turn_state))
    assert not report.meets_cost(prof(me(turn_state, deck=(), discard_pile=())))


def test_leverage(turn_state: GameState, prof: ProfileFactory) -> None:
    leverage = ability("leverage", I.LeverageAbility)
    contract = contract_entity("contract:acquire")
    answer = leverage.evaluate(prof(turn_state), req(ents(contract)))
    assert answer.value == 3.5 and answer.response == (("contract:acquire",),)
    seen: list[bool] = []

    def best(cs: Sequence[Entity], forced: bool) -> tuple[Entity | None, float]:
        seen.append(forced)
        return None, 0.0

    none(leverage.evaluate(prof(turn_state, best_contract=best), req(ents(contract))))
    assert seen == [False]
    assert not leverage.meets_cost(prof(turn_state))
    assert leverage.meets_cost(prof(me(turn_state, spice_spent_turn=1)))
    assert leverage.is_bad_intrigue(prof(turn_state, is_climax=lambda: True))


def test_manipulate(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    manipulate = ability("manipulate", I.ManipulateUPAbility)
    cheap = synth(Kind.CARD, "cheap", TestValue=4.0, PersuasionCost=6)
    dear = synth(Kind.CARD, "dear", TestValue=9.0, PersuasionCost=7)
    request = req(ents(cheap, dear))
    gains = {"buy_gains": lambda n: 1.33}
    answer = manipulate.evaluate(prof(reveal_state, **gains), request)
    assert answer.value == 4.0 and answer.response == (("cheap",),)  # 7 > 5 + 1
    none(manipulate.evaluate(prof(reveal_state), request))  # 0.1 < 1.33
    assert (
        manipulate.evaluate(prof(reveal_state, is_climax=lambda: True), request).value
        == 4.0
    )
    none(manipulate.evaluate(prof(turn_state, **gains), request))
    full = hold(turn_state, "manipulate", "cunning", "detonation", "devour")
    assert manipulate.evaluate(prof(full, **gains), request).value == 4.0
    assert manipulate.is_bad_intrigue(prof(turn_state, is_climax=lambda: True))


def test_market_opportunity(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    market = ability("market_opportunity", I.MarketOpportunityAbility)
    rich = me(turn_state, resources=Resources(spice=7, solari=7))
    assert market.evaluate(prof(rich), req()).value == 100.0
    sword = me(turn_state, resources=Resources(spice=2, solari=8))
    assert market.evaluate(prof(sword), req()) == Answer(
        100.0, ((0,),), "Market Opportunity | !Swordmaster"
    )
    owned = me(sword, swordmaster_acquired=True)
    x = market.evaluate(prof(owned), req())  # 5 x 0.25 - (0.5 + 0.5)
    assert x.value == pytest.approx(0.25) and x.response == ((0,),)
    flip = prof(owned, solari_value=lambda n: 0.1 * n)  # x < 0 -> option 1
    y = market.evaluate(flip, req())
    assert y.value == pytest.approx(2.5 - 0.5) and y.response == ((1,),)
    none(
        market.evaluate(
            prof(
                me(owned, resources=Resources(spice=2, solari=4)),
                solari_value=lambda n: 0.1 * n,
            ),
            req(),
        )
    )
    none(market.evaluate(prof(me(effects_state, resources=Resources(spice=7))), req()))
    assert market.meets_cost(prof(sword)) and not market.meets_cost(prof(turn_state))


def test_mercenaries(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    mercenaries = ability("mercenaries", I.MercenariesAbility)
    assert mercenaries.evaluate(prof(effects_state), req()) == Answer(
        100.0, (), "Mercenaries"
    )
    none(
        mercenaries.evaluate(
            prof(effects_state, should_play_troop_intrigue=lambda *a: 0), req()
        )
    )
    none(mercenaries.evaluate(prof(turn_state), req()))  # no deploy window
    none(mercenaries.evaluate(prof(me(effects_state, troops_supply=0)), req()))
    closed = with_frame(effects_state, pending_combat_deployment=False)
    none(mercenaries.evaluate(prof(closed), req()))
    assert mercenaries.is_bad_intrigue(prof(turn_state))  # round 1 < 3
    assert not mercenaries.is_bad_intrigue(prof(with_state(turn_state, round_number=3)))
    assert mercenaries.meets_cost(prof(me(turn_state, resources=Resources(solari=3))))


def with_frame(state: GameState, **changes: str | int | bool) -> GameState:
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


def test_opportunism(reveal_state: GameState, prof: ProfileFactory) -> None:
    opportunism = ability("opportunism", I.OpportunismAbility)
    request = req(tracks("emperor", "spacing_guild"))
    ones = me(reveal_state, influence=Influence(emperor=1, spacing_guild=1))
    final = {"is_final_round": lambda: True}
    answer = opportunism.evaluate(prof(ones, **final), request)
    assert answer.value == pytest.approx(-2.0 - 2.5 + 100.0)
    assert answer.response == (("emperor",), ("spacing_guild",))
    twos = me(reveal_state, influence=Influence(emperor=2, spacing_guild=1))
    single = opportunism.evaluate(prof(twos, **final), request)
    assert single.value == 96.0 and single.response == (("emperor",), ("emperor",))
    lone = opportunism.evaluate(prof(ones, **final), req(tracks("emperor")))
    assert lone.value == 0.0 and lone.response is None  # 1 track: no 2-faction option
    p = prof(ones)
    state_before = p.rng.getstate()
    none(opportunism.evaluate(p, request))  # not the final round
    assert p.rng.getstate() != state_before  # shuffled before the gate
    none(opportunism.evaluate(prof(me(ones), **final), req()))
    level = me(reveal_state, influence=Influence(emperor=2, spacing_guild=2))
    none(opportunism.evaluate(prof(level, **final), request))  # no cheap track
    behind = pl(level, 0, influence=Influence(emperor=4))
    assert opportunism.evaluate(prof(behind, **final), request).value > 0.0
    assert opportunism.is_bad_intrigue(prof(reveal_state))
    assert not opportunism.is_bad_intrigue(
        prof(with_state(reveal_state, round_number=4))
    )
    assert not opportunism.meets_cost(
        prof(me(ones, resources=Resources(solari=2), influence=Influence(emperor=1)))
    )
    assert opportunism.meets_cost(prof(me(ones, resources=Resources(solari=2))))


def test_opportunism_needs_the_reveal_turn(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    opportunism = ability("opportunism", I.OpportunismAbility)
    ones = me(turn_state, influence=Influence(emperor=1, spacing_guild=1))
    none(
        opportunism.evaluate(
            prof(ones, is_final_round=lambda: True),
            req(tracks("emperor", "spacing_guild")),
        )
    )


def test_shaddams_favor(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    favor = ability("shaddam_s_favor", I.ShaddamsFavorAbility)
    loyal = me(turn_state, influence=Influence(emperor=3), troops_supply=0)
    assert favor.evaluate(prof(loyal), req()) == Answer(
        100.0, (), "Shaddam's Favor | 100"
    )
    none(favor.evaluate(prof(me(turn_state, troops_supply=0)), req()))
    none(favor.evaluate(prof(turn_state), req()))
    full = hold(turn_state, "shaddam_s_favor", "cunning", "detonation", "devour")
    assert favor.evaluate(prof(full), req()).value == 100.0
    assert favor.evaluate(prof(effects_state), req()).value == 100.0  # Emperor < 2
    two = me(effects_state, influence=Influence(emperor=2))
    none(favor.evaluate(prof(two), req()))
    hot = prof(two, current_conflict_interest=lambda: Summer(13.0))
    assert favor.evaluate(hot, req()).value == 100.0
    assert favor.is_bad_intrigue(prof(turn_state))
    assert not favor.is_bad_intrigue(prof(two))


def test_sietch_ritual(turn_state: GameState, prof: ProfileFactory) -> None:
    ritual = ability("sietch_ritual", I.SietchRitualAbility)
    dagger = card_entity("player:3:starter:dagger:0", SEAT)
    request = req(ents(dagger), tracks("bene_gesserit", "fremen"))
    none(ritual.evaluate(prof(turn_state), request))  # Fremen +1 = 1.0 < 3.0
    climax = ritual.evaluate(prof(turn_state, is_climax=lambda: True), request)
    assert climax.value == 11.0
    assert climax.response == ((dagger.ref,), ("bene_gesserit",))
    priced = {"fremen": 3.0, "bene_gesserit": 50.0}
    p = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(priced[f])
    )
    # Both tracks are priced as Fremen (3.0): the first track is kept.
    assert ritual.evaluate(p, request).value == 3.0
    assert ritual.evaluate(p, request).response == ((dagger.ref,), ("bene_gesserit",))
    none(ritual.evaluate(prof(turn_state, discard_order=lambda c, s: []), request))
    assert ritual.meets_cost(prof(turn_state))
    assert not ritual.meets_cost(prof(me(turn_state, hand=())))
    assert not ritual.is_bad_intrigue(prof(turn_state))
    maxed = me(turn_state, influence=Influence(bene_gesserit=6, fremen=6))
    assert ritual.is_bad_intrigue(prof(maxed))


def test_special_mission(turn_state: GameState, prof: ProfileFactory) -> None:
    mission = ability("special_mission", I.SpecialMissionAbility)
    assert mission.evaluate(prof(turn_state), req()) == Answer(
        1.66, (), "Special Mission Place Spy"
    )
    spy_post = "emperor-sardaukar-dutiful-service"
    spied = me(turn_state, spy_post_ids=(spy_post,), spies_supply=2)
    spy = spy_entity(spy_post, SEAT)
    assert mission.evaluate(prof(spied), req()).response == ((0,),)
    hooks = me(spied, maker_hooks=True)
    none(mission.evaluate(prof(hooks), req(opts(0, 1), ents(spy))))
    wall = prof(hooks, intrigue_blow_wall=lambda: True)
    answer = mission.evaluate(wall, req(opts(0, 1), ents(spy)))
    assert answer.value == pytest.approx(-1.66 + 3.0 + 1.0)
    assert answer.response == ((1,), (spy_post,))
    cheap_spy = prof(
        hooks, spy_value=lambda: Summer(0.1), spice_value=lambda n: 1.1 * n
    )
    assert mission.evaluate(cheap_spy, req(opts(0, 1), ents(spy))).response == (
        (1,),
        (spy_post,),
    )  # s1 - sv >= 1.0
    blocked = spied
    for seat, post in zip((0, 1, 2), CITY_POSTS, strict=True):
        blocked = pl(blocked, seat, spy_post_ids=(post,), spies_supply=2)
    recall = mission.evaluate(prof(blocked), req(ents(spy)))
    assert recall.response == ((spy_post,),)
    none(mission.evaluate(prof(me(blocked, spy_post_ids=(), spies_supply=3)), req()))
    assert mission.meets_cost(prof(turn_state))
    assert not mission.meets_cost(prof(me(blocked, spy_post_ids=(), spies_supply=3)))


def test_special_mission_without_a_recall_target(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    mission = ability("special_mission", I.SpecialMissionAbility)
    spy_post = "emperor-sardaukar-dutiful-service"
    hooks = me(turn_state, spy_post_ids=(spy_post,), spies_supply=2, maker_hooks=True)
    wall = prof(
        hooks, intrigue_blow_wall=lambda: True, recall_spy=lambda s: (None, 0.0)
    )
    none(mission.evaluate(wall, req(opts(0, 1), ents())))


def test_strategic_stockpiling(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    stock = ability("strategic_stockpiling", I.StrategicStockpilingAbility)
    none(stock.evaluate(prof(reveal_state), req()))
    climax = {"is_climax": lambda: True}
    assert stock.evaluate(prof(reveal_state, **climax), req()) == Answer(
        100.0, ((1,),), "Strategic Stockpiling | 100"
    )
    none(stock.evaluate(prof(turn_state, **climax), req()))
    full = hold(turn_state, "strategic_stockpiling", "cunning", "detonation", "devour")
    assert stock.evaluate(prof(full, **climax), req()).value == 100.0
    assert stock.choose_yes() == 1
    late = with_state(turn_state, round_number=4)
    assert stock.is_bad_intrigue(prof(turn_state))  # round 1 < 4
    assert not stock.is_bad_intrigue(prof(me(late, resources=Resources(spice=3))))
    assert stock.is_bad_intrigue(prof(me(late, resources=Resources(water=1))))
    watered = me(late, resources=Resources(water=2), influence=Influence(fremen=3))
    assert stock.is_bad_intrigue(prof(watered))  # reads Emperor (quirk)
    emperor = me(late, resources=Resources(water=2), influence=Influence(emperor=2))
    assert not stock.is_bad_intrigue(prof(emperor))
    assert stock.meets_cost(prof(me(turn_state, resources=Resources(spice=5))))
    assert stock.meets_cost(
        prof(
            me(turn_state, resources=Resources(water=3), influence=Influence(fremen=3))
        )
    )
    assert not stock.meets_cost(prof(me(turn_state, resources=Resources(water=3))))


class _OneOpponent(AppContext):
    @property
    def opponents(self) -> tuple[PlayerState, ...]:
        return super().opponents[:1]


def test_unexpected_allies(turn_state: GameState, prof: ProfileFactory) -> None:
    allies = ability("unexpected_allies", I.UnexpectedAlliesAbility)
    opponents = {0: 10, 1: 8, 2: 4}
    estimate = {"est_opponent_strength": lambda seat: IntSummer(opponents[seat])}
    for exp, value in ((8, 100.0), (6, 100.0), (9, 0.0), (5, 0.0)):
        p = prof(turn_state, est_strength=lambda e=exp: IntSummer(e), **estimate)
        assert allies.evaluate(p, req()).value == value
    p = prof(turn_state, est_strength=lambda: IntSummer(8), **estimate)
    assert allies.evaluate(p, req()).response == ()
    for interest in (-3.0, math.nan):
        cold = prof(
            turn_state,
            est_strength=lambda: IntSummer(8),
            current_conflict_interest=lambda i=interest: Summer(i),
            **estimate,
        )
        none(allies.evaluate(cold, req()))
    alone = prof(turn_state, est_strength=lambda: IntSummer(8), **estimate)
    alone.ctx = _OneOpponent(alone.ctx.state, SEAT, alone.ctx.view)
    none(allies.evaluate(alone, req()))
    assert allies.is_bad_intrigue(prof(me(turn_state, resources=Resources(water=0))))
    assert not allies.is_bad_intrigue(prof(turn_state))
    assert not allies.meets_cost(prof(turn_state))
    assert allies.meets_cost(prof(me(turn_state, resources=Resources(water=2))))


# ---------------------------------------------------------------------------
# Endgame intrigues and the Endgame window helpers (spec §2.3, §8)
# ---------------------------------------------------------------------------


def test_endgame_is_bad_intrigue_predicates(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    profits = ability("choam_profits", I.CHOAMProfitsAbility)
    assert profits.can_be_run(prof(turn_state))
    assert profits.is_bad_intrigue(prof(turn_state))
    two = me(
        turn_state, completed_contract_ids=("contract:acquire", "contract:immediate")
    )
    assert not profits.is_bad_intrigue(prof(two))
    assert profits.is_bad_intrigue(prof(two, is_climax=lambda: True))
    three = me(
        two,
        completed_contract_ids=(
            *two.players[SEAT].completed_contract_ids,
            "contract:harvest_3",
        ),
    )
    assert not profits.is_bad_intrigue(prof(three, is_climax=lambda: True))
    trade = ability("secure_spice_trade", I.SecureSpiceTradeAbility)
    assert trade.is_bad_intrigue(prof(turn_state)) and not trade.meets_cost(
        prof(turn_state)
    )
    one = me(turn_state, discard_pile=("reserve:the_spice_must_flow:0",))
    assert not trade.is_bad_intrigue(prof(one)) and not trade.meets_cost(prof(one))
    two_tsmf = me(one, deck=(*one.players[SEAT].deck, "reserve:the_spice_must_flow:1"))
    assert trade.meets_cost(prof(two_tsmf))
    shadow = ability("shadow_alliance", I.ShadowAllianceAbility)
    assert shadow.can_be_run(prof(turn_state))
    assert shadow.is_bad_intrigue(prof(turn_state))
    ally = pl(turn_state, 0, alliance_faction_ids=("emperor",))
    assert shadow.is_bad_intrigue(prof(ally))
    three_inf = me(ally, influence=Influence(emperor=3))
    assert not shadow.is_bad_intrigue(prof(three_inf))  # 3, although the card needs 4


def test_score_battle_icons_pairs() -> None:
    natural, left = I.score_battle_icons_pairs(
        [("a", "Crysknife"), ("b", "Ornithopter"), ("c", "Crysknife")],
        include_wildcards=False,
    )
    assert natural == (I.BattleIconSet("Crysknife", ("a", "c"), False),)
    assert left == (("b", "Ornithopter"),)
    icons = [
        ("w1", "Wildcard"),
        ("o", "Ornithopter"),
        ("d", "DesertMouse"),
        ("w2", "Wildcard"),
        ("w3", "Wildcard"),
    ]
    sets, left = I.score_battle_icons_pairs(icons, include_wildcards=True)
    assert sets == (
        I.BattleIconSet("Ornithopter", ("o", "w1"), True),
        I.BattleIconSet("DesertMouse", ("d", "w2"), True),
    )
    assert left == (("w3", "Wildcard"),)  # wildcards never pair with each other
    # The intrigue's icon: a natural match first, else one wildcard; an
    # unused icon is taken out again.
    match, _ = I.score_battle_icons_pairs(
        [("w", "Wildcard"), ("k", "Crysknife")],
        include_wildcards=True,
        additional=("intrigue", "Crysknife"),
    )
    assert match == (I.BattleIconSet("Crysknife", ("k", "intrigue"), False),)
    wild, left = I.score_battle_icons_pairs(
        [("w", "Wildcard"), ("o", "Ornithopter")],
        include_wildcards=True,
        additional=("intrigue", "Crysknife"),
    )
    assert wild == (I.BattleIconSet("Crysknife", ("intrigue", "w"), True),)
    assert left == (("o", "Ornithopter"),)  # only the intrigue's icon is standard
    unused, left = I.score_battle_icons_pairs(
        [("o", "Ornithopter")],
        include_wildcards=True,
        additional=("intrigue", "Crysknife"),
    )
    assert unused == () and left == (("o", "Ornithopter"),)


def test_endgame_auto_plays_and_battle_icon_pairs(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    state = hold(
        turn_state,
        "crysknife",
        "desert_mouse",
        "shadow_alliance",
        "secure_spice_trade",
        "buy_access",
    )
    state = me(state, objective_ids=("objective_crysknife_1",), won_conflict_ids=())
    p = prof(state)
    plays = I.endgame_auto_plays(p)
    assert [(c.ref, type(a).__name__) for c, a in plays] == [
        ("intrigue:crysknife:0", "CompleteBattleIconPairEndgameAbility"),
        ("intrigue:shadow_alliance:0", "ShadowAllianceAbility"),
    ]
    assert I.complete_battle_icon_pair_card(p, card("crysknife")) == (
        "objective_crysknife_1"
    )
    assert I.complete_battle_icon_pair_card(p, card("desert_mouse")) is None
    wild = me(state, won_conflict_ids=("propaganda",))
    pw = prof(wild)
    assert I.complete_battle_icon_pair_card(pw, card("desert_mouse")) == "propaganda"
    # A natural match beats the wildcard.
    assert I.complete_battle_icon_pair_card(pw, card("crysknife")) == (
        "objective_crysknife_1"
    )
    assert len(I.endgame_auto_plays(pw)) == 3  # Desert Mouse can use the wildcard
    assert I.endgame_wild_pairs(pw) == [("objective_crysknife_1", "propaganda")]
    assert I.endgame_wild_pairs(p) == []


def test_battle_icon_list_reads_face_up_cards(turn_state: GameState) -> None:
    state = me(
        turn_state,
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=("skirmish_ornithopter", "propaganda", "skirmish_crysknife"),
        face_down_battle_card_ids=("objective_crysknife_1", "skirmish_crysknife"),
    )
    assert I.battle_icon_list(state.players[SEAT]) == [
        ("skirmish_ornithopter", "Ornithopter"),
        ("propaganda", "Wildcard"),
    ]


def test_profile_shuffle_draws_from_the_agent_rng(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """Buy Access breaks ties with the profile's seeded RNG (no other RNG)."""

    buy = ability("buy_access", I.BuyAccessAbility)
    flat = {"gain_influence_value": lambda f, n, r=-1, a=False: Summer(1.0)}
    request = req(tracks("emperor", "spacing_guild", "bene_gesserit", "fremen"))
    first = prof(turn_state, is_climax=lambda: True, **flat)
    first.rng = random.Random(7)
    again = prof(turn_state, is_climax=lambda: True, **flat)
    again.rng = random.Random(7)
    assert buy.evaluate(first, request) == buy.evaluate(again, request)
