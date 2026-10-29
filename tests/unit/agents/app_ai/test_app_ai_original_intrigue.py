"""The original game's Intrigue ports (abilities/original_intrigue.py, plan §12).

Every test builds a real original ``GameState`` (``app_ai.testing``), adjusts
the fields a hook reads and stubs the ``Profile`` prices other areas own with
simple linear ones, so each branch, literal and constant of the decompiled
method is pinned by hand (the addresses are in the port's docstrings).
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import (
    PORTS,
    Ability,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities import original_intrigue as oi
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo, Timing
from dune_imperium.agents.app_ai.abilities.intrigue import (
    IntrigueAbility,
    StrengthIntrigueAbility,
    ability_for_prompt,
)
from dune_imperium.agents.app_ai.catalog import (
    ORIGINAL_INTRIGUE_ARCHETYPES,
    card_entity,
    intrigue_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
BOARD = Board.of(ORIGINAL)
ENGINE = UprisingRulesEngine()
PA = "worm.canis.abilities.PlayAbilities.BaseSet."


def _stubs() -> dict[str, Callable[..., Any]]:
    return {
        "is_climax": lambda: False,
        "is_final_round": lambda: False,
        "game_arc": lambda: 1,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            {"none": 3.0}.get(f, 2.0) * n
        ),
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "persuasion_value": lambda n: 0.75 * n,
        "victory_point_value": lambda n: 10.0 * n,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "buy_gains": lambda n: 0.5 * n,
        "buy_value": lambda: 4.0,
        "acquire_value": lambda card: Summer(card.float_attr("TestValue", 3.0)),
        "possible_persuasion": lambda: 5,
        "should_play_retreat_intrigue": lambda name, a, b, units: 1,
        "should_play_troop_intrigue": lambda name, a, b, troops: 100,
        "units_to_deploy": lambda units, maximum: min(2, units),
        "est_strength": lambda: IntSummer(5),
        "est_opponent_strength": lambda seat: IntSummer(5 + seat),
        "conflict_posture_bounds": lambda: (2.0, 6.0),
        "current_conflict_interest": lambda: Summer(4.0),
        "current_conflict_rank": lambda bonus=0: 2,
        "expected_combat_order": lambda: [0, 1, 2, 3],
        "intrigue_blow_wall": lambda: False,
        "recall_agent": lambda agents: agents[0] if agents else None,
        "space_value_for_player": lambda space: Summer(1.0),
        "intrigue_value": lambda: 2.0,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """The first original ``turn`` decision (round 1)."""

    return first_decision("turn", config=ORIGINAL)


@pytest.fixture(scope="module")
def reveal_state() -> GameState:
    """The first original ``reveal`` decision."""

    return first_decision("reveal", config=ORIGINAL)


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


_FREE_SPACES = ("imperial_basin", "hagga_basin", "deep_desert", "the_great_flat")


def pl(state: GameState, seat: int, **changes: Any) -> GameState:
    """``with_player`` that keeps the player's invariants.

    Troop changes are balanced in the supply (or the garrison when the
    supply is given); a Swordmaster adds its Agent; fewer available Agents
    are placed on free spaces.
    """

    player = state.players[seat]
    if any(
        k in changes for k in ("troops_supply", "troops_garrison", "troops_conflict")
    ):
        rest = player.memories + player.specimens + player.troops_parked
        conflict = int(changes.get("troops_conflict", player.troops_conflict))
        if "troops_supply" in changes and "troops_garrison" not in changes:
            supply = int(changes["troops_supply"])
            changes["troops_garrison"] = 12 - supply - conflict - rest
        else:
            garrison = int(changes.get("troops_garrison", player.troops_garrison))
            changes["troops_supply"] = 12 - garrison - conflict - rest
    sword = bool(changes.get("swordmaster_acquired", player.swordmaster_acquired))
    if sword and not player.swordmaster_acquired and "agents_available" not in changes:
        changes["agents_available"] = player.agents_available + 1
    if "agents_available" in changes and "agent_locations" not in changes:
        needed = (3 if sword else 2) - int(changes["agents_available"])
        locations = list(player.agent_locations)
        for space in _FREE_SPACES:
            if len(locations) < needed and space not in locations:
                locations.append(space)
        changes["agent_locations"] = tuple(locations[:needed])
    return with_player(state, seat, **changes)


def me(state: GameState, **changes: Any) -> GameState:
    return pl(state, _seat(state), **changes)


def hand_intrigues(state: GameState, *names: str) -> GameState:
    """The deciding seat holding exactly these Intrigue cards (each name once
    or repeated: instances ``intrigue:<id>:0``, ``:1`` ... as the deck has
    them), taken out of the deck, the discard pile and every other hand."""

    seen: dict[str, int] = {}
    held: list[str] = []
    for name in names:
        held.append(f"intrigue:{name}:{seen.get(name, 0)}")
        seen[name] = seen.get(name, 0) + 1
    taken = set(held)
    state = with_state(
        state,
        intrigue_deck=tuple(c for c in state.intrigue_deck if c not in taken),
        intrigue_discard=tuple(c for c in state.intrigue_discard if c not in taken),
    )
    for seat, player in enumerate(state.players):
        if seat != _seat(state) and taken & set(player.intrigue_cards):
            state = with_player(
                state,
                seat,
                intrigue_cards=tuple(
                    c for c in player.intrigue_cards if c not in taken
                ),
            )
    return me(state, intrigue_cards=tuple(held))


def card(name: str, seat: int = 0) -> Entity:
    return intrigue_entity(f"intrigue:{name}:0", seat)


def ab[A: Ability](name: str, cls: type[A]) -> A:
    for candidate in abilities_of(card(name)):
        if isinstance(candidate, cls):
            return candidate
    raise AssertionError(f"{name} has no {cls.__name__}")


def first_ability(name: str) -> Ability:
    return abilities_of(card(name))[0]


def evaluate(p: Profile, name: str, *infos: TargetInfo) -> tuple[float, Any]:
    answer = first_ability(name).evaluate(p, Request(infos))
    return answer.value, answer.response


def tracks(*factions: str) -> TargetInfo:
    return TargetInfo(tuple(track_entity(f) for f in factions))


def options(*values: int) -> TargetInfo:
    return TargetInfo((), tuple(values))


EMPTY = ()  # "play it" with no sub-targets


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_every_original_intrigue_ability_resolves_to_a_port() -> None:
    for card_id in ORIGINAL_INTRIGUE_ARCHETYPES:
        for ability in abilities_of(card(card_id)):
            assert not isinstance(ability, UnportedAbility), (card_id, ability)
    assert len(ORIGINAL_INTRIGUE_ARCHETYPES) == 34


def test_every_port_here_is_an_intrigue_ability_of_its_app_class() -> None:
    ports = [
        cls
        for cls in vars(oi).values()
        if isinstance(cls, type)
        and issubclass(cls, Ability)
        and cls.__module__ == oi.__name__
        and cls.APP_CLASS in PORTS
        and PORTS[cls.APP_CLASS] is cls
    ]
    # 35 card classes (Tiebreaker has two) and the GainInfluence base.
    assert len(ports) == 36
    for port in ports:
        assert issubclass(port, IntrigueAbility), port


def test_timing_of_the_non_plot_cards() -> None:
    assert isinstance(ab("master_tactician", StrengthIntrigueAbility), Ability)
    for cid in ("allied_armada", "ambush", "master_tactician", "private_army"):
        assert first_ability(cid).timing is Timing.COMBAT
    staged = ab("staged_incident", oi.StagedIncidentAbility)
    assert staged.ability_timing == 5 and staged.timing is Timing.COMBAT
    for resolution in (
        ab("demand_respect", oi.DemandRespectAbility),
        ab("to_the_victor", oi.ToTheVictorAbility),
    ):
        assert resolution.ability_timing == 3
        assert resolution.timing is Timing.COMBAT_RESOLUTION
    assert ab("corner_the_market", oi.CornerTheMarketAbility).ability_timing == 4
    assert ab("plans_within_plans", oi.PlansWithinPlansAbility).ability_timing == 4
    assert ab("tiebreaker", oi.TiebreakerAbility2).ability_timing == 4
    assert ab("tiebreaker", oi.TiebreakerAbility).ability_timing == 5


def test_tiebreaker_halves_are_found_by_prompt() -> None:
    tiebreaker = card("tiebreaker")
    assert isinstance(ability_for_prompt(tiebreaker, True), oi.TiebreakerAbility)
    assert isinstance(ability_for_prompt(tiebreaker, False), oi.TiebreakerAbility2)


# ---------------------------------------------------------------------------
# Profile flags (profile-economy.md 4.5; @0x4912010 ...)
# ---------------------------------------------------------------------------


def test_short_and_long_flags(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    seat = _seat(turn_state)
    p = make_profile(me(turn_state, resources=Resources(solari=0, spice=3)), seat)
    monkeypatch.setattr(p, "resource_value", lambda attr, n, include=False: 0.7)
    assert p.is_solari_short() and not p.is_solari_long()  # >= 0.7
    monkeypatch.setattr(p, "resource_value", lambda attr, n, include=False: 0.69)
    assert not p.is_solari_short() and p.is_solari_long()
    # IsSpiceShort: the Swordmaster holder with spice <= 3.
    assert not p.is_spice_short()
    holder = make_profile(
        me(
            turn_state,
            swordmaster_acquired=True,
            resources=Resources(solari=0, spice=3),
        ),
        seat,
    )
    assert holder.is_spice_short()
    rich = make_profile(
        me(
            turn_state,
            swordmaster_acquired=True,
            resources=Resources(solari=0, spice=4),
        ),
        seat,
    )
    assert not rich.is_spice_short()
    # IsTroopShort: garrison <= 2.
    assert make_profile(me(turn_state, troops_garrison=2), seat).is_troop_short()
    assert not make_profile(me(turn_state, troops_garrison=3), seat).is_troop_short()
    # IsWaterLong: not Early and water >= 3.
    water3 = make_profile(me(turn_state, resources=Resources(water=3)), seat)
    water3.game_arc = lambda: 0  # type: ignore[method-assign]
    assert not water3.is_water_long()
    water3.game_arc = lambda: 1  # type: ignore[method-assign]
    assert water3.is_water_long()
    water2 = make_profile(me(turn_state, resources=Resources(water=2)), seat)
    water2.game_arc = lambda: 2  # type: ignore[method-assign]
    assert not water2.is_water_long()


# ---------------------------------------------------------------------------
# GainInfluenceIntrigueAbility and its four cards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cid", "cls", "faction"),
    [
        ("favored_subject", oi.FavoredSubjectAbility, "emperor"),
        ("guild_authorization", oi.GuildAuthorizationAbility, "spacing_guild"),
        ("know_their_ways", oi.KnowTheirWaysAbility, "fremen"),
        ("secret_of_the_sisterhood", oi.SecretOfTheSisterhoodAbility, "bene_gesserit"),
    ],
)
def test_gain_influence_cards_name_their_faction(
    cid: str, cls: type[Ability], faction: str
) -> None:
    ability = ab(cid, cls)
    assert isinstance(ability, oi.GainInfluenceIntrigueAbility)
    assert ability.specified_faction == faction


def test_gain_influence_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    state = hand_intrigues(turn_state, "favored_subject")
    # G(F, +1) = 2.0 < GainInfluenceValueThreshold (3.0): held.
    assert evaluate(prof(state), "favored_subject") == (0.0, None)
    # At the threshold (jae): played at the literal 100.0.
    reach = prof(
        state, gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(3.0)
    )
    assert evaluate(reach, "favored_subject") == (100.0, EMPTY)
    # Climax plays below it.
    assert evaluate(prof(state, is_climax=lambda: True), "favored_subject") == (
        100.0,
        EMPTY,
    )
    # Four held Intrigue cards play below it as well; three do not.
    four = hand_intrigues(turn_state, "favored_subject", "ambush", "ambush", "refocus")
    assert evaluate(prof(four), "favored_subject")[0] == 100.0
    three = hand_intrigues(turn_state, "favored_subject", "ambush", "ambush")
    assert evaluate(prof(three), "favored_subject")[0] == 0.0


def test_gain_influence_is_bad_intrigue(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    opponent = (seat + 1) % 4
    ability = ab("favored_subject", oi.FavoredSubjectAbility)

    def bad(mine: int, theirs: int) -> bool:
        state = me(turn_state, influence=Influence(emperor=mine))
        state = with_player(state, opponent, influence=Influence(emperor=theirs))
        return ability.is_bad_intrigue(prof(state))

    assert bad(0, 6)  # an opponent at 6: always bad
    assert bad(2, 4)  # at 2 and an opponent two above
    assert bad(4, 6)
    assert not bad(2, 3)  # only one above
    assert not bad(3, 5)  # the player stands at neither 2 nor 4
    assert not bad(1, 5)
    # Opponents at 6 count even when the player is the leader.
    assert bad(6, 6)


# ---------------------------------------------------------------------------
# Plots with simple gates
# ---------------------------------------------------------------------------


def test_bribery(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("bribery", oi.BriberyAbility)
    low = me(turn_state, resources=Resources(solari=1))
    assert not ability.meets_cost(prof(low))
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(solari=2))))
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    # At turn start (PlayerTurn Undetermined) nothing is answered.
    assert evaluate(prof(turn_state), "bribery", tracks("emperor", "fremen")) == (
        0.0,
        None,
    )
    # After the Reveal each track is priced G * 0.1 (away from the climax).
    keen = prof(
        reveal_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {"none": 4.0}.get(f, 2.0) * n
        ),
    )
    value, response = evaluate(keen, "bribery", tracks("emperor", "fremen"))
    assert value == pytest.approx(0.2)  # 2.0 * 0.1, the first strictly best
    assert response == (("emperor",),)
    # G(None, +1) = 3.0 is under BriberyInfluenceThreshold (3.75): held.
    held = prof(
        reveal_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(1.0 * n),
    )
    assert evaluate(held, "bribery", tracks("emperor")) == (0.0, None)
    # The climax skips both tests and the scaling.
    climax = prof(
        turn_state,
        is_climax=lambda: True,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(1.0 * n),
    )
    assert evaluate(climax, "bribery", tracks("fremen")) == (1.0, (("fremen",),))


def test_charisma_and_recruitment_mission(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    # Charisma: buy gains of 2 (1.0 here) against CharismaBuyGainsThreshold 2.5.
    four = hand_intrigues(turn_state, "charisma", "ambush", "ambush", "refocus")
    assert evaluate(prof(turn_state), "charisma") == (0.0, None)  # not Reveal, 1 card
    assert evaluate(prof(four), "charisma") == (0.0, None)  # below the threshold
    rich = prof(four, buy_gains=lambda n: 1.5 * n)
    assert evaluate(rich, "charisma") == (100.0, EMPTY)
    assert evaluate(prof(four, is_climax=lambda: True), "charisma")[0] == 100.0
    # The Reveal turn needs no hand size.
    assert (
        evaluate(prof(reveal_state, buy_gains=lambda n: 1.5 * n), "charisma")[0]
        == 100.0
    )
    # Recruitment Mission: gains of 1 against 1.33; the threshold is tested first.
    assert evaluate(prof(reveal_state), "recruitment_mission") == (0.0, None)
    ok = prof(reveal_state, buy_gains=lambda n: 1.5 * n)
    assert evaluate(ok, "recruitment_mission") == (100.0, EMPTY)
    assert (
        evaluate(prof(turn_state, buy_gains=lambda n: 1.5 * n), "recruitment_mission")[
            0
        ]
        == 0.0
    )


def test_climax_vp_plots(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    shares = ab("choam_shares", oi.ChoamSharesAbility)
    assert not shares.meets_cost(prof(me(turn_state, resources=Resources(solari=6))))
    assert shares.meets_cost(prof(me(turn_state, resources=Resources(solari=7))))
    assert shares.is_bad_intrigue(prof(turn_state, is_solari_short=lambda: True))
    assert not shares.is_bad_intrigue(prof(turn_state, is_solari_short=lambda: False))
    # Only at the climax; outside the Reveal turn four held Intrigue cards.
    assert evaluate(prof(reveal_state), "choam_shares") == (0.0, None)
    climax = prof(reveal_state, is_climax=lambda: True)
    value, response = evaluate(climax, "choam_shares")
    assert value == pytest.approx(-7 * 0.25 + 10.0) and response == EMPTY
    assert evaluate(prof(turn_state, is_climax=lambda: True), "choam_shares") == (
        0.0,
        None,
    )
    sleeper = ab("the_sleeper_must_awaken", oi.TheSleeperMustAwakenAbility)
    assert not sleeper.meets_cost(prof(me(turn_state, resources=Resources(spice=3))))
    assert sleeper.meets_cost(prof(me(turn_state, resources=Resources(spice=4))))
    value, response = evaluate(climax, "the_sleeper_must_awaken")
    assert value == pytest.approx(-4 * 0.5 + 10.0) and response == EMPTY
    assert evaluate(prof(reveal_state), "the_sleeper_must_awaken") == (0.0, None)


def test_councilors_dispensation(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("councilors_dispensation", oi.CouncilorsDispensationAbility)
    seatless = prof(turn_state)
    assert not ability.meets_cost(seatless) and ability.is_bad_intrigue(seatless)
    assert evaluate(seatless, "councilors_dispensation") == (0.0, None)
    seated = me(turn_state, high_council=True, resources=Resources(spice=5))
    assert ability.meets_cost(prof(seated)) and not ability.is_bad_intrigue(
        prof(seated)
    )
    # Spice <= CouncilorsDispensationSpiceThreshold (5.0): played.
    assert evaluate(prof(seated), "councilors_dispensation") == (100.0, EMPTY)
    # Above it four held Intrigue cards are needed.
    flush = me(seated, resources=Resources(spice=6))
    assert evaluate(prof(flush), "councilors_dispensation") == (0.0, None)
    hand = hand_intrigues(
        flush, "councilors_dispensation", "ambush", "ambush", "refocus"
    )
    assert evaluate(prof(hand), "councilors_dispensation")[0] == 100.0


def test_water_peddlers_union(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("water_peddlers_union", oi.WaterPeddlersUnionAbility)
    assert ability.is_bad_intrigue(prof(turn_state, is_water_long=lambda: True))
    # The hand-size/final-round helper plays at once.
    forced = prof(turn_state, play_intrigue_for_final_round_or_hand_size=lambda c: 100)
    assert evaluate(forced, "water_peddlers_union") == (100.0, EMPTY)
    low = me(turn_state, resources=Resources(water=1))
    none = prof(low, play_intrigue_for_final_round_or_hand_size=lambda c: -1)
    assert evaluate(none, "water_peddlers_union") == (100.0, EMPTY)  # water <= 1.0
    two = me(turn_state, resources=Resources(water=2))
    held = prof(two, play_intrigue_for_final_round_or_hand_size=lambda c: -1)
    assert evaluate(held, "water_peddlers_union") == (0.0, None)
    # Not at the turn start: nothing; and no Agent left: nothing.
    reveal = prof(reveal_state, play_intrigue_for_final_round_or_hand_size=lambda c: -1)
    assert evaluate(reveal, "water_peddlers_union") == (0.0, None)
    spent = me(low, agents_available=0)
    assert (
        evaluate(
            prof(spent, play_intrigue_for_final_round_or_hand_size=lambda c: -1),
            "water_peddlers_union",
        )[0]
        == 0.0
    )


def test_windfall(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("windfall", oi.WindfallAbility)
    assert ability.is_bad_intrigue(prof(turn_state, is_solari_long=lambda: True))
    none = {"play_intrigue_for_final_round_or_hand_size": lambda c: -1}

    def play(solari: int, **changes: object) -> float:
        state = me(turn_state, resources=Resources(solari=solari), **changes)
        return evaluate(prof(state, **none), "windfall")[0]

    assert play(3) == 100.0  # Solari <= WindfallSolariThreshold (3.0)
    assert play(5) == 100.0  # cannot pay the Swordmaster (8) and has none
    assert play(8) == 100.0  # Solari <= its SolariCost
    assert play(5, swordmaster_acquired=True) == 0.0  # has it: needs CHOAM Shares
    assert play(9) == 0.0  # above both: CHOAM Shares branch, none held
    # With CHOAM Shares: played up to WindfallChoamSharesThreshold (5.0).
    shares = hand_intrigues(
        me(turn_state, resources=Resources(solari=5), swordmaster_acquired=True),
        "windfall",
        "choam_shares",
    )
    assert evaluate(prof(shares, **none), "windfall")[0] == 100.0
    rich = hand_intrigues(
        me(turn_state, resources=Resources(solari=6), swordmaster_acquired=True),
        "windfall",
        "choam_shares",
    )
    assert evaluate(prof(rich, **none), "windfall")[0] == 0.0
    forced = prof(turn_state, play_intrigue_for_final_round_or_hand_size=lambda c: 100)
    assert evaluate(forced, "windfall")[0] == 100.0


def test_refocus_and_water_of_life(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    refocus = ab("refocus", oi.RefocusAbility)
    assert refocus.is_bad_intrigue(prof(turn_state))
    # An Agent left: played; none left: the average-Persuasion buy gains
    # (floor of the mean) must reach 1.0, or the climax / four Intrigue.
    assert evaluate(prof(turn_state), "refocus") == (100.0, EMPTY)
    spent = me(turn_state, agents_available=0)
    assert evaluate(prof(spent), "refocus") == (0.0, None)
    assert evaluate(prof(spent, is_climax=lambda: True), "refocus")[0] == 100.0
    assert evaluate(prof(spent, buy_gains=lambda n: 1.0), "refocus")[0] == 100.0
    seen: list[int] = []

    def gains(amount: int) -> float:
        seen.append(amount)
        return 0.0

    evaluate(prof(spent, buy_gains=gains), "refocus")
    assert len(seen) == 1 and isinstance(seen[0], int)
    empty = me(turn_state, deck=(), discard_pile=())
    assert evaluate(prof(empty), "refocus") == (0.0, None)
    water = ab("water_of_life", oi.WaterOfLifeAbility)
    assert not water.meets_cost(
        prof(me(turn_state, resources=Resources(water=0, spice=2)))
    )
    assert not water.meets_cost(
        prof(me(turn_state, resources=Resources(water=1, spice=0)))
    )
    assert water.meets_cost(prof(me(turn_state, resources=Resources(water=1, spice=1))))
    assert water.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    value, response = evaluate(prof(turn_state), "water_of_life")
    assert value == pytest.approx(-1.0 - 0.5 + 1.8 * 3.0) and response == EMPTY


def test_poison_snooper(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("poison_snooper", oi.PoisonSnooperAbility)
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert evaluate(prof(turn_state), "poison_snooper") == (100.0, EMPTY)
    # ChoosePoisonEvaluator: 0 trash, 1 draw.
    junk = card_entity("imperium:dagger:0", 0)  # TrashValue is read from the card
    p = prof(turn_state, game_arc=lambda: 0)
    assert ability.choose_poison(p, None) == 1
    valuable = Entity(
        Kind.CARD, "x", junk.archetype and replace_attrs(junk, TrashValue=0.5), 0
    )
    assert ability.choose_poison(p, valuable) == 0  # >= 0.5 in the Early arc
    assert ability.choose_poison(prof(turn_state, game_arc=lambda: 2), valuable) == 1
    weak = Entity(Kind.CARD, "y", replace_attrs(junk, TrashValue=0.49), 0)
    assert ability.choose_poison(p, weak) == 1


def replace_attrs(entity: Entity, **attrs: object) -> Any:
    """``entity``'s archetype with attributes overridden."""

    from types import MappingProxyType

    archetype = entity.archetype
    assert archetype is not None
    merged = {**archetype.attributes, **attrs}
    return replace(archetype, attributes=MappingProxyType(merged))


def test_poison_snooper_keeps_spice_must_flow_cards_with_corner_the_market(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("poison_snooper", oi.PoisonSnooperAbility)
    tsmf = card_entity("reserve:the_spice_must_flow:0", 0)
    wanted = Entity(Kind.CARD, tsmf.ref, replace_attrs(tsmf, TrashValue=1.0), 0)
    p = prof(turn_state, game_arc=lambda: 0)
    assert ability.choose_poison(p, wanted) == 0
    corner = prof(hand_intrigues(turn_state, "corner_the_market"), game_arc=lambda: 0)
    assert ability.choose_poison(corner, wanted) == 1  # TSMF worth 0 to trash


# ---------------------------------------------------------------------------
# Strength family and the other Combat cards
# ---------------------------------------------------------------------------


def test_strength_cards_costs_and_junk_flags(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    sword = {
        "allied_armada": 7,
        "ambush": 4,
        "private_army": 5,
        "tiebreaker": 2,
        "master_tactician": 3,
    }
    for cid, strength in sword.items():
        assert card(cid).int_attr("Strength") == strength
    armada = ab("allied_armada", oi.AlliedArmadaAbility)
    plain = me(turn_state, resources=Resources(spice=2), alliance_faction_ids=())
    allied = me(plain, alliance_faction_ids=("emperor",))
    assert (
        not armada.meets_cost(prof(plain)) and armada.strength_value(prof(plain)) == 0
    )
    assert armada.meets_cost(prof(allied)) and armada.strength_value(prof(allied)) == 7
    assert not armada.meets_cost(prof(me(allied, resources=Resources(spice=1))))
    assert armada.is_bad_intrigue(prof(allied, game_arc=lambda: 0))
    assert not armada.is_bad_intrigue(prof(allied))
    assert armada.is_bad_intrigue(prof(plain))
    ambush = ab("ambush", oi.AmbushAbility)
    assert ambush.meets_cost(prof(turn_state)) and not ambush.is_bad_intrigue(
        prof(turn_state)
    )
    army = ab("private_army", oi.PrivateArmyAbility)
    assert not army.meets_cost(prof(me(turn_state, resources=Resources(spice=1))))
    assert army.meets_cost(prof(me(turn_state, resources=Resources(spice=2))))
    short = {"is_spice_short": lambda: True}
    assert army.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert army.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1, **short))
    assert not army.is_bad_intrigue(
        prof(turn_state, game_arc=lambda: 1, is_spice_short=lambda: False)
    )
    assert not army.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2, **short))
    tie = ab("tiebreaker", oi.TiebreakerAbility)
    assert tie.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2))
    assert not tie.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))


def test_private_army_is_dumped_at_50_in_a_decisive_fight(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    state = me(
        turn_state,
        resources=Resources(spice=2),
        intrigue_cards=("intrigue:private_army:0", "intrigue:ambush:0"),
        combat_strength=4,
    )
    conflict_id = state.current_conflict_ids[0] if state.current_conflict_ids else None
    assert conflict_id is not None
    state = with_state(state, conflict_deck=())  # the last conflict: decisive
    p = prof(state, current_conflict_rank=lambda bonus=0: 3)
    answer = ab("private_army", oi.PrivateArmyAbility).evaluate(p, Request())
    assert answer.value == 50.0 and answer.response == ()
    # Ambush is dumped at 100 - CombatValue (5.0) in the same fight.
    answer = ab("ambush", oi.AmbushAbility).evaluate(p, Request())
    assert answer.value == 95.0
    assert seat >= 0
    del monkeypatch


def test_master_tactician_retreat_option(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    state = me(turn_state, combat_strength=14)
    for other in range(4):
        if other != seat:
            state = with_player(state, other, combat_strength=2)
    state = with_state(state, conflict_deck=())  # decisive: strength branch is 100 - 4
    p = prof(state, current_conflict_rank=lambda bonus=0: 3)
    troops = options(0, 1, 2, 3, 4)
    value, response = evaluate(p, "master_tactician", options(0, 1), troops)
    assert (value, response) == (150.0, ((1,), (0, 1, 2)))  # min(3, 5 - 1)
    # Climax, a close opponent (strictly below cur + 3) or a lead under 10 hold it.
    assert evaluate(
        prof(state, is_climax=lambda: True), "master_tactician", options(0, 1), troops
    )[1] == ((0,),)
    near = with_player(state, (seat + 1) % 4, combat_strength=16)
    assert evaluate(
        prof(near, current_conflict_rank=lambda bonus=0: 3),
        "master_tactician",
        options(0, 1),
        troops,
    )[1] == ((0,),)
    far = with_player(state, (seat + 1) % 4, combat_strength=17)
    assert evaluate(
        prof(far, current_conflict_rank=lambda bonus=0: 3),
        "master_tactician",
        options(0, 1),
        troops,
    )[1] == ((1,), (0, 1, 2))
    lead = with_player(state, (seat + 2) % 4, combat_strength=5)
    assert evaluate(
        prof(lead, current_conflict_rank=lambda bonus=0: 3),
        "master_tactician",
        options(0, 1),
        troops,
    )[1] == ((0,),)
    # One troop only: min(3, 0) < 1.
    assert evaluate(p, "master_tactician", options(0, 1), options(0))[1] == ((0,),)


def test_staged_incident(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("staged_incident", oi.StagedIncidentAbility)
    assert not ability.meets_cost(prof(me(turn_state, troops_conflict=2)))
    assert ability.meets_cost(prof(me(turn_state, troops_conflict=3)))
    seen: list[tuple[str, int, int, int]] = []

    def should(name: str, a: int, b: int, units: int) -> int:
        seen.append((name, a, b, units))
        return 1

    assert evaluate(
        prof(turn_state, should_play_retreat_intrigue=should), "staged_incident"
    ) == (1.0, EMPTY)
    assert seen == [("Staged Incident", 6, 10, 3)]
    assert evaluate(
        prof(turn_state, should_play_retreat_intrigue=lambda *a: 0), "staged_incident"
    ) == (0.0, None)


def test_demand_respect_and_to_the_victor(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    for cid, cls in (
        ("demand_respect", oi.DemandRespectAbility),
        ("to_the_victor", oi.ToTheVictorAbility),
    ):
        ability = ab(cid, cls)
        assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
        late = {"game_arc": lambda: 2}
        assert ability.is_bad_intrigue(
            prof(turn_state, current_conflict_rank=lambda b=0: None, **late)
        )
        assert ability.is_bad_intrigue(
            prof(turn_state, current_conflict_rank=lambda b=0: 2, **late)
        )
        assert not ability.is_bad_intrigue(
            prof(turn_state, current_conflict_rank=lambda b=0: 1, **late)
        )
    assert evaluate(prof(turn_state), "to_the_victor") == (100.0, EMPTY)
    all_tracks = tracks("emperor", "spacing_guild", "bene_gesserit", "fremen")
    choices = options(0, 1)
    # Away from the climax G(None, +1) must reach 2.5; two infos are needed.
    low = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(1.0 * n),
    )
    assert evaluate(low, "demand_respect", all_tracks, choices) == (0.0, None)
    assert evaluate(prof(turn_state), "demand_respect", all_tracks) == (0.0, None)
    # One influence: value + 90, the first strictly best track, option 0.
    value, response = evaluate(prof(turn_state), "demand_respect", all_tracks, choices)
    assert value == pytest.approx(2.0 + 90.0) and response == ((0,), ("emperor",))
    # Paying: spice >= 2, G(None, 1) <= 3.25 and G(None, 2) >= 7.0.
    paid = me(turn_state, resources=Resources(spice=2))
    rich = prof(
        paid,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {1: 3.25, 2: 7.0}[n] if f == "none" else 3.0 * n
        ),
    )
    value, response = evaluate(rich, "demand_respect", all_tracks, choices)
    assert value == pytest.approx(6.0 + 90.0) and response == ((1,), ("emperor",))
    too_good = prof(
        paid,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {1: 3.26, 2: 7.0}[n] if f == "none" else 3.0 * n
        ),
    )
    assert evaluate(too_good, "demand_respect", all_tracks, choices)[1] == (
        (0,),
        ("emperor",),
    )


# ---------------------------------------------------------------------------
# Endgame cards
# ---------------------------------------------------------------------------


def test_endgame_cards(turn_state: GameState, prof: ProfileFactory) -> None:
    answer = ab("tiebreaker", oi.TiebreakerAbility2).evaluate(
        prof(turn_state), Request()
    )
    assert (answer.value, answer.response) == (100.0, EMPTY)
    corner = ab("corner_the_market", oi.CornerTheMarketAbility)
    assert corner.is_bad_intrigue(
        prof(me(turn_state, hand=(), deck=(), discard_pile=(), in_play=()))
    )
    with_tsmf = me(turn_state, discard_pile=("reserve:the_spice_must_flow:0",))
    assert not corner.is_bad_intrigue(prof(with_tsmf))
    answer = corner.evaluate(prof(turn_state), Request())
    assert (answer.value, answer.response) == (100.0, EMPTY)
    plans = ab("plans_within_plans", oi.PlansWithinPlansAbility)
    deep = me(turn_state, influence=Influence(3, 3, 0, 0))
    shallow = me(turn_state, influence=Influence(3, 2, 0, 0))
    assert plans.is_bad_intrigue(prof(shallow, game_arc=lambda: 0))
    assert not plans.is_bad_intrigue(prof(deep, game_arc=lambda: 1))
    assert plans.is_bad_intrigue(prof(shallow, game_arc=lambda: 2))  # < 2 at rank 3
    assert not plans.is_bad_intrigue(prof(deep, game_arc=lambda: 2))
    answer = plans.evaluate(prof(turn_state), Request())
    assert (answer.value, answer.response) == (100.0, EMPTY)


# ---------------------------------------------------------------------------
# Troops: Rapid Mobilization, Reinforcements, Double Cross
# ---------------------------------------------------------------------------


def test_rapid_mobilization(
    turn_state: GameState,
    reveal_state: GameState,
    monkeypatch: pytest.MonkeyPatch,
    prof: ProfileFactory,
) -> None:
    ability = ab("rapid_mobilization", oi.RapidMobilizationAbility)
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert ability.is_bad_intrigue(prof(turn_state, is_troop_short=lambda: True))
    assert not ability.is_bad_intrigue(prof(turn_state, is_troop_short=lambda: False))
    # TroopValue: twice the garrison in the Reveal turn, else minus 3 per Agent.
    state = me(turn_state, troops_garrison=5, agents_available=2)
    assert ability.troop_value(prof(state)) == 4  # max(0, 10 - 6)
    assert (
        ability.troop_value(prof(me(turn_state, troops_garrison=1, agents_available=2)))
        == 0
    )
    reveal = pl(reveal_state, _seat(reveal_state), troops_garrison=5)
    assert ability.troop_value(prof(reveal)) == 10
    # Evaluate hands the troops to IntrigueDeployTroops (the literal 100.0).
    monkeypatch.setattr(oi, "intrigue_deploy_troops", lambda p, troops: 2)
    assert evaluate(prof(turn_state), "rapid_mobilization", options(0, 1, 2, 3)) == (
        100.0,
        ((0, 1),),
    )
    monkeypatch.setattr(oi, "intrigue_deploy_troops", lambda p, troops: 0)
    assert evaluate(prof(turn_state), "rapid_mobilization", options(0, 1)) == (
        0.0,
        None,
    )


def test_reinforcements(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("reinforcements", oi.ReinforcementsAbility)
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(solari=2))))
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(solari=3))))
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 0))
    assert ability.is_bad_intrigue(prof(turn_state, is_solari_short=lambda: True))
    assert not ability.is_bad_intrigue(prof(turn_state, is_solari_short=lambda: False))
    rich = me(turn_state, resources=Resources(solari=3), troops_supply=1)
    assert ability.troop_value(prof(rich)) == 2  # min(6, 2 * 1)
    assert (
        ability.troop_value(
            prof(me(turn_state, resources=Resources(solari=3), troops_supply=9))
        )
        == 6
    )
    assert ability.troop_value(prof(me(turn_state, resources=Resources(solari=2)))) == 0
    # Evaluate: Reveal turn only, units_to_deploy, ShouldPlayTroopIntrigue.
    calls: list[tuple[str, int, int, int]] = []

    def should(name: str, a: int, b: int, troops: int) -> int:
        calls.append((name, a, b, troops))
        return 100

    value, response = evaluate(
        prof(reveal_state, should_play_troop_intrigue=should),
        "reinforcements",
        options(0, 1, 2),
    )
    assert (value, response) == (100.0, ((0, 1),)) and calls == [
        ("Reinforcements", 6, 4, 3)
    ]
    assert evaluate(prof(turn_state), "reinforcements", options(0, 1, 2)) == (0.0, None)
    none = prof(reveal_state, units_to_deploy=lambda units, maximum: 0)
    assert evaluate(none, "reinforcements", options(0, 1, 2)) == (0.0, None)
    assert evaluate(
        prof(reveal_state, should_play_troop_intrigue=lambda *a: 0),
        "reinforcements",
        options(0, 1),
    ) == (0.0, None)


def test_double_cross(
    turn_state: GameState, reveal_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("double_cross", oi.DoubleCrossAbility)
    seat = _seat(turn_state)
    foe = (seat + 1) % 4
    assert not ability.meets_cost(prof(turn_state))  # nobody deployed
    foes = me(pl(turn_state, foe, troops_conflict=1), resources=Resources(solari=1))
    assert ability.meets_cost(prof(foes))
    assert not ability.meets_cost(prof(me(foes, resources=Resources(solari=0))))
    assert ability.troop_value(prof(me(turn_state, resources=Resources(solari=0)))) == 0
    assert (
        ability.troop_value(
            prof(me(turn_state, troops_supply=0, resources=Resources(solari=1)))
        )
        == 2
    )
    assert (
        ability.troop_value(
            prof(me(turn_state, troops_supply=1, resources=Resources(solari=1)))
        )
        == 4
    )
    assert (
        ability.troop_value(
            prof(me(turn_state, troops_supply=9, resources=Resources(solari=1)))
        )
        == 4
    )
    seats = options(*[s for s in range(4) if s != seat])
    # The turn start needs four held Intrigue cards.
    assert evaluate(prof(foes), "double_cross", seats) == (0.0, None)
    # No own troop in the Conflict: opponents with exactly one troop and one
    # Agent are valued by their Victory points.
    reveal = reveal_state
    rseat = _seat(reveal)
    rfoe = (rseat + 1) % 4
    state = pl(reveal, rfoe, troops_conflict=1, agents_available=1, victory_points=4)
    state = pl(
        state, (rseat + 2) % 4, troops_conflict=2, agents_available=1, victory_points=9
    )
    state = me(state, troops_conflict=0)
    other = [s for s in range(4) if s != rseat]
    assert evaluate(prof(state), "double_cross", options(*other)) == (4.0, ((rfoe,),))
    # With troops of its own and no endgame threat: the interest must pass
    # the lower bound, then each opponent's estimated strength counts when
    # within 4 of the player's (else 0); the strictly best is kept.
    own = me(state, troops_conflict=2)
    strengths = {s: 12 for s in other}
    strengths[other[0]] = 9
    p = prof(
        own,
        est_strength=lambda: IntSummer(10),
        est_opponent_strength=lambda s: IntSummer(strengths[s]),
        expected_combat_order=lambda: [rseat],
    )
    assert evaluate(p, "double_cross", options(*other)) == (12.0, ((other[1],),))
    far = prof(
        own,
        est_strength=lambda: IntSummer(10),
        est_opponent_strength=lambda s: IntSummer(15),
        expected_combat_order=lambda: [rseat],
    )
    assert evaluate(far, "double_cross", options(*other))[0] == 0.0
    flat = prof(
        own,
        current_conflict_interest=lambda: Summer(2.0),
        expected_combat_order=lambda: [rseat],
    )
    assert evaluate(flat, "double_cross", options(*other)) == (0.0, None)
    # The expected winner would end the game (VP + conflict VP >= trigger and
    # not behind the player): every opponent is valued by its strength.
    leader = rfoe
    ahead = pl(own, leader, victory_points=10)
    threat = prof(
        ahead,
        est_opponent_strength=lambda s: IntSummer(7 + s),
        expected_combat_order=lambda: [leader, rseat],
    )
    best = max(other, key=lambda s: 7 + s)
    assert evaluate(threat, "double_cross", options(*other)) == (
        float(7 + best),
        ((best,),),
    )


# ---------------------------------------------------------------------------
# Plots that read the board and the hand
# ---------------------------------------------------------------------------


def synth_card(ref: str, **attrs: object) -> Entity:
    """A hand card with the given archetype attributes."""

    from types import MappingProxyType

    from dune_imperium.agents.app_ai.data.archetypes import Archetype

    archetype = Archetype(
        short=f"Test.{ref}",
        kind="test",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attrs)),
    )
    return Entity(Kind.CARD, ref, archetype, 0)


def space_values(
    values: dict[str, float], default: float = 0.0
) -> Callable[..., float]:
    return lambda p, space, with_entities: values.get(space.ref, default)


def test_calculated_hire(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    ability = ab("calculated_hire", oi.CalculatedHireAbility)
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(spice=0))))
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(spice=1))))
    # IsBadIntrigue: the Mid arc and every round before the last are bad; in
    # the final round only a Mentat that does not rest on its space is.
    mid = prof(turn_state, game_arc=lambda: 1, is_final_round=lambda: True)
    assert ability.is_bad_intrigue(mid)
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2))
    final = prof(turn_state, game_arc=lambda: 2, is_final_round=lambda: True)
    assert not ability.is_bad_intrigue(final)
    monkeypatch.setattr(type(final.ctx), "mentat_rests", property(lambda self: False))
    assert ability.is_bad_intrigue(final)
    monkeypatch.undo()
    # Evaluate: the best valid space of the hand, then the posture and spice.
    hand = me(turn_state, resources=Resources(spice=5))
    refs = hand.players[_seat(hand)].hand
    spaces = frozenset({"conspire", "wealth"})
    monkeypatch.setattr(oi, "valid_space_ids", lambda p, ref, cache: spaces)
    assert refs
    monkeypatch.setattr(
        oi, "_space_value", space_values({"conspire": 5.0, "wealth": 1.0})
    )
    # Conspire (SpiceCost 4) is best: 5 - 4 > 0 -> played.
    assert evaluate(prof(hand), "calculated_hire") == (100.0, EMPTY)
    four = me(hand, resources=Resources(spice=4))
    assert evaluate(prof(four), "calculated_hire") == (0.0, None)
    # Wealth best (no spice cost): played with a single spice.
    monkeypatch.setattr(
        oi, "_space_value", space_values({"conspire": 1.0, "wealth": 5.0})
    )
    assert (
        evaluate(prof(me(hand, resources=Resources(spice=1))), "calculated_hire")[0]
        == 100.0
    )
    assert evaluate(
        prof(me(hand, resources=Resources(spice=0))), "calculated_hire"
    ) == (
        0.0,
        None,
    )
    # Interest below the lower posture bound (2.0): held.
    low = prof(hand, current_conflict_interest=lambda: Summer(1.9))
    assert evaluate(low, "calculated_hire") == (0.0, None)
    monkeypatch.setattr(oi, "valid_space_ids", lambda p, ref, cache: frozenset())
    assert evaluate(prof(hand), "calculated_hire") == (0.0, None)


def test_urgent_mission(
    turn_state: GameState,
    reveal_state: GameState,
    monkeypatch: pytest.MonkeyPatch,
    prof: ProfileFactory,
) -> None:
    from dune_imperium.agents.app_ai.catalog import agent_entity

    ability = ab("urgent_mission", oi.UrgentMissionAbility)
    seat = _seat(turn_state)
    assert not ability.meets_cost(prof(me(turn_state, agents_available=2)))
    spent = me(turn_state, agents_available=0)
    assert ability.meets_cost(prof(spent))
    agents = TargetInfo((agent_entity("arrakeen", seat), agent_entity("carthag", seat)))
    monkeypatch.setattr(
        oi, "valid_space_ids", lambda p, ref, cache: frozenset({"arrakeen"})
    )
    monkeypatch.setattr(oi, "_agent_card_value", lambda p, card, space: 2.0)
    monkeypatch.setattr(oi, "_space_value", space_values({"arrakeen": 3.0}))
    # 2.0 + 3.0 reaches the literal 5.0; interest 4.0 is between the bounds
    # (2.0, 6.0) and GetBuyValue 4.0 <= 8.5: the recalled Agent is played.
    value, response = evaluate(prof(spent), "urgent_mission", agents)
    assert (value, response) == (100.0, (("arrakeen",),))
    # Agents left, or not the turn start: nothing.
    one = me(turn_state, agents_available=1)
    assert evaluate(prof(one), "urgent_mission", agents)[1] is None
    reveal = me(reveal_state, agents_available=0)
    assert evaluate(prof(reveal), "urgent_mission", agents)[1] is None
    # Below the literal 5.0: nothing.
    monkeypatch.setattr(oi, "_space_value", space_values({"arrakeen": 2.9}))
    assert evaluate(prof(spent), "urgent_mission", agents)[1] is None
    monkeypatch.setattr(oi, "_space_value", space_values({"arrakeen": 3.0}))
    # Posture: at or below the lower bound nothing; above the upper bound it
    # plays whatever the buys are worth; in between GetBuyValue <= 8.5.
    flat = prof(spent, current_conflict_interest=lambda: Summer(2.0))
    assert evaluate(flat, "urgent_mission", agents)[1] is None
    hot = prof(
        spent, current_conflict_interest=lambda: Summer(6.1), buy_value=lambda: 9.0
    )
    assert evaluate(hot, "urgent_mission", agents)[0] == 100.0
    assert (
        evaluate(prof(spent, buy_value=lambda: 8.51), "urgent_mission", agents)[1]
        is None
    )
    assert (
        evaluate(prof(spent, buy_value=lambda: 8.5), "urgent_mission", agents)[0]
        == 100.0
    )
    climax = prof(
        spent, is_climax=lambda: True, current_conflict_interest=lambda: Summer(0.0)
    )
    assert evaluate(climax, "urgent_mission", agents)[0] == 100.0
    # No recallable Agent: nothing.
    assert (
        evaluate(prof(spent, recall_agent=lambda a: None), "urgent_mission", agents)[1]
        is None
    )


def test_infiltrate(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    foe = (seat + 1) % 4
    # An opponent Agent on Arrakeen (Circle icon) the card cannot reach alone.
    state = with_player(
        turn_state, foe, agent_locations=("arrakeen",), agents_available=1
    )
    circle = synth_card("circle", IconList=("Circle", "Triangle"))
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [circle])
    monkeypatch.setattr(
        oi, "valid_space_ids", lambda p, ref, cache: frozenset({"imperial_basin"})
    )
    monkeypatch.setattr(oi, "_agent_card_value", lambda p, card, space: 1.5)
    monkeypatch.setattr(
        oi,
        "_space_value",
        lambda p, space, with_entities: 2.0 if space.ref == "arrakeen" else 0.0,
    )
    # (space value + agent card value) - 0.1; Triangle spaces have no Agent.
    value, response = evaluate(prof(state), "infiltrate")
    assert value == pytest.approx(3.4) and response == EMPTY
    # A space the card reaches itself, an own Agent there, a missing icon, an
    # unaffordable cost, no Agent left or a later turn removes it.
    monkeypatch.setattr(
        oi, "valid_space_ids", lambda p, ref, cache: frozenset({"arrakeen"})
    )
    assert evaluate(prof(state), "infiltrate") == (0.0, None)
    monkeypatch.setattr(oi, "valid_space_ids", lambda p, ref, cache: frozenset())
    square = synth_card("square", IconList=("Pentagon",))
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [square])
    assert evaluate(prof(state), "infiltrate") == (0.0, None)
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [circle])
    mine = pl(state, seat, agents_available=1)
    mine = with_player(mine, seat, agent_locations=("arrakeen",))
    assert evaluate(prof(mine), "infiltrate") == (0.0, None)
    spent = me(state, agents_available=0)
    assert evaluate(prof(spent), "infiltrate") == (0.0, None)
    monkeypatch.setattr(oi, "_can_pay_space", lambda p, space: False)
    assert evaluate(prof(state), "infiltrate") == (0.0, None)


def test_infiltrate_is_blocked_by_kwisatz_haderach(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    seat = _seat(turn_state)
    foe = (seat + 1) % 4
    state = with_player(
        turn_state, foe, agent_locations=("arrakeen",), agents_available=1
    )
    real = card_entity("imperium:kwisatz_haderach:0", seat)
    assert real.short == oi._KWISATZ_HADERACH
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [real])
    monkeypatch.setattr(oi, "valid_space_ids", lambda p, ref, cache: frozenset())
    assert evaluate(prof(state), "infiltrate") == (0.0, None)


def test_can_pay_space_follows_has_resource_cost(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    def pay(space: str, **resources: int) -> bool:
        base = {"solari": 0, "spice": 0, "water": 0}
        base.update(resources)
        p = prof(me(turn_state, resources=Resources(**base)))
        return oi._can_pay_space(p, space_entity(space, BOARD))

    assert pay("arrakeen")
    assert not pay("conspire", spice=3) and pay("conspire", spice=4)
    assert not pay("imperium_hagga_basin") and pay("imperium_hagga_basin", water=1)
    assert not pay("rally_troops", solari=3) and pay("rally_troops", solari=4)
    assert not pay("imperium_swordmaster", solari=7)
    assert pay("imperium_swordmaster", solari=8)


def test_dispatch_an_envoy(
    turn_state: GameState,
    reveal_state: GameState,
    monkeypatch: pytest.MonkeyPatch,
    prof: ProfileFactory,
) -> None:
    ability = ab("dispatch_an_envoy", oi.DispatchAnEnvoyAbility)
    assert not ability.is_bad_intrigue(prof(turn_state))
    final = {"is_final_round": lambda: True}
    assert ability.is_bad_intrigue(prof(me(turn_state, agents_available=0), **final))
    assert not ability.is_bad_intrigue(prof(turn_state, **final))
    # The best free affordable space is a Faction space no hand card reaches.
    monkeypatch.setattr(oi, "_can_pay_space", lambda p, space: True)
    monkeypatch.setattr(
        oi,
        "_space_value",
        space_values({"wealth": 4.0, "secrets": 3.0, "arrakeen": 1.0}, -9.0),
    )
    blue = synth_card("blue", IconList=("SpacingGuild", "Circle"))
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [blue])
    assert evaluate(prof(turn_state), "dispatch_an_envoy") == (100.0, EMPTY)
    # A card that already shows the Emperor icon (wealth's): held.
    emperor = synth_card("emperor", IconList=("Emperor",))
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [blue, emperor])
    assert evaluate(prof(turn_state), "dispatch_an_envoy") == (0.0, None)
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [blue])
    # The best space is not a Faction space (Circle): held.
    monkeypatch.setattr(oi, "_space_value", space_values({"arrakeen": 9.0}, -9.0))
    assert evaluate(prof(turn_state), "dispatch_an_envoy") == (0.0, None)
    # An Agent on the best space removes it: the next best is not a Faction.
    seat = _seat(turn_state)
    blocked = with_player(
        turn_state, (seat + 1) % 4, agent_locations=("wealth",), agents_available=1
    )
    monkeypatch.setattr(
        oi, "_space_value", space_values({"wealth": 4.0, "arrakeen": 0.0}, -9.0)
    )
    assert evaluate(prof(blocked), "dispatch_an_envoy") == (0.0, None)
    # No Agent left, not the turn start, an envoy already dispatched, no hand.
    spent = me(turn_state, agents_available=0)
    assert evaluate(prof(spent), "dispatch_an_envoy")[1] is None
    assert evaluate(prof(reveal_state), "dispatch_an_envoy")[1] is None
    four = "emperor,spacing_guild,bene_gesserit,fremen"
    dispatched = me(turn_state, granted_agent_icon_turn=four)
    assert evaluate(prof(dispatched), "dispatch_an_envoy")[1] is None
    monkeypatch.setattr(oi, "_hand_entities", lambda p: [])
    assert evaluate(prof(turn_state), "dispatch_an_envoy")[1] is None


def test_bypass_protocol(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("bypass_protocol", oi.BypassProtocolAbility)
    assert ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 2))
    assert not ability.is_bad_intrigue(prof(turn_state, game_arc=lambda: 1))
    short = prof(turn_state, game_arc=lambda: 0, is_spice_short=lambda: True)
    assert ability.is_bad_intrigue(short)
    long = prof(turn_state, game_arc=lambda: 0, is_spice_short=lambda: False)
    assert not ability.is_bad_intrigue(long)
    cheap = synth_card("cheap", TestValue=3.0)
    dear = synth_card("dear", TestValue=5.4)
    free = TargetInfo((cheap, synth_card("meh", TestValue=2.9)))
    paid = TargetInfo((dear, cheap))
    rich = me(turn_state, resources=Resources(spice=2))
    assert evaluate(prof(rich), "bypass_protocol", free, paid) == (
        100.0,
        ((1,), ("dear",), (0,)),
    )
    # Under 5.4 the free option takes over (the best of cost 3 or less).
    almost = TargetInfo((synth_card("d2", TestValue=5.39),))
    assert evaluate(prof(rich), "bypass_protocol", TargetInfo((cheap,)), almost) == (
        100.0,
        ((0,), ("cheap",), (0,)),
    )
    # Without 2 spice only the free option is considered; it needs 3.0.
    poor = me(turn_state, resources=Resources(spice=1))
    assert evaluate(prof(poor), "bypass_protocol", free, paid) == (
        100.0,
        ((0,), ("cheap",), (0,)),
    )
    meh = TargetInfo((synth_card("meh", TestValue=2.99),))
    assert evaluate(prof(poor), "bypass_protocol", meh, paid) == (0.0, None)
    assert evaluate(prof(poor), "bypass_protocol", TargetInfo(()), paid) == (0.0, None)
    # Two target informations are needed.
    assert evaluate(prof(poor), "bypass_protocol", free) == (0.0, None)


def test_valid_spaces_of_the_original_starting_hand(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """``WormBoard::ValidSpaces`` as the engine's placement enumeration gives
    it, on the original board (the Calculated Hire, Urgent Mission, Infiltrate
    and Bindu Suspension readers)."""

    p = prof(turn_state)
    found = {ref.split(":")[3]: oi.valid_space_ids(p, ref, {}) for ref in p.ctx.hand}
    assert found["reconnaissance"] == {"arrakeen", "carthag"}
    assert found["dagger"] == {"hall_of_oratory"}
    assert found["dune_the_desert_planet"] >= {"imperial_basin"}
    assert found["convincing_argument"] == frozenset()


def synth_conflict(level: int) -> Entity:
    entity = synth_card("conflict", ConflictLevel=level)
    return Entity(Kind.CONFLICT, "c", entity.archetype, None)


def test_bindu_suspension(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    ability = ab("bindu_suspension", oi.BinduSuspensionAbility)
    assert ability.is_bad_intrigue(prof(turn_state))
    climax = prof(turn_state, is_climax=lambda: True)
    assert evaluate(climax, "bindu_suspension") == (100.0, ())
    valid = frozenset(
        {
            "arrakeen",
            "wealth",
            "mentat",
            "imperium_swordmaster",
            "imperium_high_council",
            "conspire",
            "imperium_research_station",
        }
    )
    monkeypatch.setattr(oi, "valid_space_ids", lambda p, ref, cache: valid)
    values = {"arrakeen": 1.0}
    monkeypatch.setattr(
        oi, "_space_value", lambda p, space, with_entities: values.get(space.ref, 0.0)
    )
    # A plain best space: the turn is passed at the literal 99.0.
    assert evaluate(prof(turn_state), "bindu_suspension") == (99.0, ())
    for special in (
        "mentat",
        "imperium_swordmaster",
        "imperium_high_council",
        "conspire",
        "imperium_research_station",
    ):
        values.clear()
        values[special] = 5.0
        assert evaluate(prof(turn_state), "bindu_suspension") == (0.0, None), special
    # A Faction space: only when its Influence is worth under 1.75.
    values.clear()
    values["wealth"] = 5.0
    under = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(1.74),
    )
    assert evaluate(under, "bindu_suspension") == (99.0, ())
    over = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(1.75),
    )
    assert evaluate(over, "bindu_suspension") == (0.0, None)
    # More than 1 bonus spice on the best space keeps the player in.
    values.clear()
    values["arrakeen"] = 5.0
    monkeypatch.setattr(oi, "_space_bonus_spice", lambda p, space: 2)
    assert evaluate(prof(turn_state), "bindu_suspension") == (0.0, None)
    monkeypatch.undo()
    # No Agent left: the buy gains of the rounded average Persuasion reach 2.0.
    spent = me(turn_state, agents_available=0)
    monkeypatch.setattr(oi, "valid_space_ids", lambda p, ref, cache: frozenset())
    assert evaluate(prof(spent, buy_gains=lambda n: 2.0), "bindu_suspension") == (
        100.0,
        (),
    )
    assert evaluate(prof(spent, buy_gains=lambda n: 1.99), "bindu_suspension") == (
        0.0,
        None,
    )
    # ChoosePassEvaluator: pass in Conflicts of level 1-2 only.
    for level, answer in ((1, 1), (2, 1), (3, 0)):
        monkeypatch.setattr(
            oi, "_current_conflict", lambda p, level=level: synth_conflict(level)
        )
        assert ability.choose_pass(prof(turn_state)) == answer


# ---------------------------------------------------------------------------
# Profile branches the original cards and leaders make live
# ---------------------------------------------------------------------------


def as_leader(state: GameState, leader_id: str, **changes: Any) -> GameState:
    """The deciding seat playing ``leader_id`` (a single-sided leader)."""

    return me(state, leader_id=leader_id, leader_face_id=leader_id, **changes)


def real_profile(state: GameState) -> Profile:
    return make_profile(state, _seat(state))


def test_deferral_threshold_reads_the_original_leaders(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``DeferredThresholdReached`` @0x482c8a0: Bribery's DeferValue 2 plus the
    leader's extra reaches the threshold 3 (engine-order §4.1)."""

    from dune_imperium.agents.app_ai.abilities import generic as g

    base = hand_intrigues(turn_state, "bribery")
    secret = {"masterstroke_factions": ("emperor", "fremen")}

    def reached(state: GameState, *space_ids: str) -> bool:
        spaces = [space_entity(space, BOARD) for space in space_ids]
        monkeypatch.setattr(g, "_this_turn_agent", lambda p: ([], spaces))
        return g.deferred_threshold_reached(real_profile(state))

    plain = as_leader(base, "duke_leto_atreides")
    assert not reached(plain, "stillsuits")
    # The Baron: +2 while his secret Factions are held, none after Masterstroke.
    baron = as_leader(base, "baron_vladimir_harkonnen", **secret)
    assert reached(baron, "stillsuits")
    assert not reached(as_leader(base, "baron_vladimir_harkonnen"), "stillsuits")
    revealed = as_leader(
        base, "baron_vladimir_harkonnen", masterstroke_revealed=True, **secret
    )
    assert not reached(revealed, "stillsuits")
    # Earl Memnon: +2 at the High Council; Count Ilban: +1 at a Landsraad
    # (Pentagon) space; Countess Ariana: +1 at a Maker space with spice.
    memnon = as_leader(base, "earl_memnon_thorvald")
    assert reached(memnon, "imperium_high_council")
    assert not reached(memnon, "stillsuits")
    ilban = as_leader(base, "count_ilban_richese")
    assert reached(ilban, "rally_troops")
    assert not reached(ilban, "stillsuits")
    ariana = as_leader(base, "countess_ariana_thorvald")
    assert reached(ariana, "imperium_hagga_basin")
    assert not reached(ariana, "stillsuits")


def test_baron_secret_factions_value_a_two_troop_combat_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """``SpaceAbility::ValueForPlayer`` @0x4bafaf0: the Baron holding his
    secret Factions adds ``BaronVladimirHarkonnenGetTroopsBonus`` (0.75) at a
    Combat space with two or more troops."""

    from dune_imperium.agents.app_ai.abilities import generic as g

    def value(state: GameState, space_id: str) -> float:
        p = prof(state)
        return g.SpaceAbility(space_entity(space_id, BOARD)).value_for_player(p).sum

    secret = as_leader(
        turn_state,
        "baron_vladimir_harkonnen",
        masterstroke_factions=("emperor", "fremen"),
    )
    open_baron = as_leader(turn_state, "baron_vladimir_harkonnen")
    assert value(secret, "hardy_warriors") - value(open_baron, "hardy_warriors") == (
        pytest.approx(0.75)
    )
    for space in ("arrakeen", "conspire", "wealth"):  # one troop / not Combat
        assert value(secret, space) == value(open_baron, space)
    revealed = as_leader(
        turn_state,
        "baron_vladimir_harkonnen",
        masterstroke_factions=("emperor", "fremen"),
        masterstroke_revealed=True,
    )
    assert value(revealed, "hardy_warriors") == value(open_baron, "hardy_warriors")


def test_paul_atreides_reads_the_top_of_his_deck(
    turn_state: GameState,
) -> None:
    """``get_CardDrawValue`` @0x4908cc0: Paul's draw is worth ``v * (PersuasionCost
    of his top card / 10 + 1)`` (his Prescience shows the card, ``PlayerView
    .private.peeked_card_id``); everyone else ``v * 1.0``."""

    paul = as_leader(turn_state, "paul_atreides")
    p = real_profile(paul)
    top = p.ctx.view.private.peeked_card_id if p.ctx.view.private else ""
    assert top == paul.players[_seat(paul)].deck[0]
    cost = card_entity(top).int_attr("PersuasionCost")
    base = p.C.CardDrawValue
    assert p.card_draw_value() == pytest.approx(base * (cost / 10.0 + 1.0))
    expensive = me(
        paul,
        deck=("imperium:arrakis_liaison:0", *paul.players[_seat(paul)].deck[1:]),
    )
    dear = real_profile(expensive)
    cost = card_entity("imperium:arrakis_liaison:0").int_attr("PersuasionCost")
    assert dear.card_draw_value() == pytest.approx(base * (cost / 10.0 + 1.0))
    empty = real_profile(me(paul, deck=()))
    assert empty.card_draw_value() == base
    other = real_profile(as_leader(turn_state, "duke_leto_atreides"))
    assert other.card_draw_value() == base


def test_deploy_value_scales_with_rapid_mobilization_and_staged_incident(
    turn_state: GameState,
) -> None:
    """``DeployValue`` @0x4912c50 (spec §6): ``w * (r * s)`` with ``r =
    RapidMobilizationDeployMod`` (0.5) and ``s = StagedIncidentDeployMod`` (1.2)
    while ``StagedIncidentDeployedTroopThreshold`` (4.0) >= ConflictTroops."""

    arrakeen = space_entity("arrakeen", BOARD)
    plain = real_profile(turn_state).deploy_value(arrakeen)
    assert plain != 0.0

    def deploy(state: GameState) -> float:
        return real_profile(state).deploy_value(arrakeen)

    rapid = hand_intrigues(turn_state, "rapid_mobilization")
    assert deploy(rapid) == pytest.approx(plain * 0.5)
    staged = hand_intrigues(turn_state, "staged_incident")
    assert deploy(staged) == pytest.approx(plain * 1.2)
    both = hand_intrigues(turn_state, "rapid_mobilization", "staged_incident")
    assert deploy(both) == pytest.approx(plain * 0.5 * 1.2)
    # Five troops in the Conflict: Staged Incident's term is off (4.0 < 5).
    crowded = pl(staged, _seat(staged), troops_conflict=5)
    reference = hand_intrigues(
        pl(turn_state, _seat(turn_state), troops_conflict=5), "ambush"
    )
    assert deploy(crowded) == pytest.approx(deploy(reference))
    assert deploy(pl(staged, _seat(staged), troops_conflict=4)) != pytest.approx(
        deploy(
            hand_intrigues(
                pl(turn_state, _seat(turn_state), troops_conflict=4), "ambush"
            )
        )
    )


def test_reinforcements_raises_the_conflict_interest(turn_state: GameState) -> None:
    """``CurrentConflictInterest`` @0x4902f80: ``ReinforcementsConflictInterestBonus``
    (3.0) while the card is held and the player has 3 Solari."""

    def interest(state: GameState) -> float:
        return real_profile(state).current_conflict_interest().sum

    rich = me(turn_state, resources=Resources(solari=3))
    poor = me(turn_state, resources=Resources(solari=2))
    plain = interest(hand_intrigues(rich, "windfall"))
    assert interest(hand_intrigues(rich, "reinforcements")) == pytest.approx(
        plain + 3.0
    )
    assert interest(hand_intrigues(poor, "reinforcements")) == pytest.approx(
        interest(hand_intrigues(poor, "windfall"))
    )


def test_heighliner_potential_with_the_original_intrigue(
    turn_state: GameState,
) -> None:
    """``GetHeighlinerPotentialPlayer`` @0x49189a0 (spec §9.1): Infiltrate lets
    the AI count an occupied Heighliner, Urgent Mission an empty Agent supply,
    Dispatch an Envoy the Guild icon it lacks."""

    seat = _seat(turn_state)
    foe = (seat + 1) % 4
    state = turn_state
    for other in range(4):
        state = with_player(state, other, resources=Resources(solari=0, spice=0))
    state = me(state, resources=Resources(solari=0, spice=6))
    # No Guild-icon card in hand and no Dispatch an Envoy: no potential.
    no_guild = me(state, hand=())
    assert (
        real_profile(hand_intrigues(no_guild, "ambush")).heighliner_potential_player()
        is None
    )
    dispatch = hand_intrigues(no_guild, "dispatch_an_envoy")
    assert real_profile(dispatch).heighliner_potential_player() == seat
    # An Agent on the Heighliner blocks it unless the AI holds Infiltrate.
    blocked = pl(dispatch, foe, agents_available=1)
    blocked = with_player(blocked, foe, agent_locations=("imperium_heighliner",))
    assert real_profile(blocked).heighliner_potential_player() is None
    both = hand_intrigues(blocked, "dispatch_an_envoy", "infiltrate")
    assert real_profile(both).heighliner_potential_player() == seat
    # No Agent left: only with Urgent Mission.
    spent = hand_intrigues(pl(no_guild, seat, agents_available=0), "dispatch_an_envoy")
    assert real_profile(spent).heighliner_potential_player() is None
    urgent = hand_intrigues(
        pl(no_guild, seat, agents_available=0), "dispatch_an_envoy", "urgent_mission"
    )
    assert real_profile(urgent).heighliner_potential_player() == seat
