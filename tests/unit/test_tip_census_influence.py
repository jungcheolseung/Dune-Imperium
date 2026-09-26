"""Regression tests for the influence tip-census module (infl/lands/spy)."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dune_imperium.agents.registry import make_agent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.evaluation import tournament as T
from dune_imperium.rules import UprisingRulesEngine

# ``tests/unit`` has no ``__init__.py``, so under the plain ``uv run pytest``
# invocation this project's docs prescribe (as opposed to ``python -m
# pytest``), the repo root never lands on ``sys.path`` and
# ``from tests.unit.test_tip_census import load_tip_census`` raises
# ``ModuleNotFoundError: No module named 'tests'`` -- confirmed by running
# the exact reporting command. Duplicating the tiny loader here (identical
# to ``tests/unit/test_tip_census.py``'s) avoids that import instead of
# adding ``tests/unit/__init__.py``, which would change collection for every
# test module in the directory, well outside this module's scope.
_TOOL = Path(__file__).resolve().parents[2] / "scripts" / "ab" / "tip_census.py"


def load_tip_census() -> ModuleType:
    """Import ``scripts/ab/tip_census.py`` (it puts ``scripts/ab`` on sys.path)."""

    if "tip_census" in sys.modules:
        return sys.modules["tip_census"]
    spec = importlib.util.spec_from_file_location("tip_census", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tip_census"] = module
    spec.loader.exec_module(module)
    return module


GAMES_PER_RULESET = 5


def _specs(full: bool) -> tuple[T.MatchSpec, ...]:
    return T.tournament_specs(
        agents=("heuristic",),
        games=GAMES_PER_RULESET,
        rulesets=(full,),
        start_seed=0,
        rotate_leaders=True,
        bloodlines=full,
        tech_module=full,
        immortality=full,
    )


def _spec(full: bool, seed: int) -> T.MatchSpec:
    """One game outside the ``_specs`` seed range, for a hand-traced pin."""

    return T.tournament_specs(
        agents=("heuristic",),
        games=1,
        rulesets=(full,),
        start_seed=seed,
        rotate_leaders=True,
        bloodlines=full,
        tech_module=full,
        immortality=full,
    )[0]


@pytest.fixture(scope="module")
def tip_census() -> ModuleType:
    return load_tip_census()


def _play_all(tip_census: ModuleType, full: bool) -> list[dict[str, Any]]:
    return [tip_census.play(spec, ("influence",)) for spec in _specs(full)]


@pytest.fixture(scope="module")
def base_games(tip_census: ModuleType) -> list[dict[str, Any]]:
    return _play_all(tip_census, full=False)


@pytest.fixture(scope="module")
def full_games(tip_census: ModuleType) -> list[dict[str, Any]]:
    return _play_all(tip_census, full=True)


def _seat_rows(games: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [seat for game in games for seat in game["seats"]]


@pytest.fixture(scope="module")
def all_seats(
    base_games: list[dict[str, Any]], full_games: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return _seat_rows(base_games) + _seat_rows(full_games)


@pytest.fixture(scope="module")
def influence_module(tip_census: ModuleType) -> ModuleType:
    """``scripts/ab/tipcensus/influence.py``, for its private helpers/classes.

    Depends on ``tip_census`` so ``scripts/ab`` is already on ``sys.path``
    (``load_tip_census``'s side effect) before this import runs.
    """

    return importlib.import_module("tipcensus.influence")


@pytest.fixture(scope="module")
def census_step_class(tip_census: ModuleType) -> Any:
    return importlib.import_module("tipcensus.base").Step


@pytest.fixture(scope="module")
def base_reset_state(tip_census: ModuleType) -> GameState:
    """A freshly reset base-ruleset ``GameState``, for hand-built ``Step``s.

    Only used as ``Step.pre``/``Step.post`` filler in tests that exercise
    ``InfluenceCollector.step`` directly on synthetic events/actions and
    never read anything from ``pre``/``post`` beyond what a fresh game
    already provides (``round_number``, each seat's ``agents_available``).
    """

    spec = _specs(False)[0]
    engine = (
        UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else UprisingRulesEngine()
    )
    return engine.reset(spec.config, spec.game_seed)


def test_every_column_is_prefixed_and_present(tip_census: ModuleType) -> None:
    classes = {cls.name for cls in tip_census.collector_classes(("influence",))}
    assert classes == {"infl", "lands", "spy"}


# --- InfluenceCollector ----------------------------------------------------


def test_final_tracks_equal_gained_minus_lost(all_seats: list[dict[str, Any]]) -> None:
    # Starting Influence is 0 on every track [uprising-systems.md:37], so the
    # final position on all 4 tracks combined must equal total gained minus
    # total lost, with no per-Faction bookkeeping needed to check it.
    for seat in all_seats:
        tracks = (
            seat["infl.emperor"]
            + seat["infl.guild"]
            + seat["infl.bene_gesserit"]
            + seat["infl.fremen"]
        )
        assert tracks == seat["infl.gained"] - seat["infl.lost"]


def test_sources_sum_to_gained(all_seats: list[dict[str, Any]]) -> None:
    for seat in all_seats:
        assert sum(seat["infl.sources"].values()) == seat["infl.gained"]


def test_tracks_0_1_and_ge2_partition_the_four_factions(
    all_seats: list[dict[str, Any]],
) -> None:
    for seat in all_seats:
        assert seat["infl.tracks_0_1"] + seat["infl.tracks_ge2"] == 4
        assert 0 <= seat["infl.tracks_ge4"] <= seat["infl.tracks_ge2"]
        assert 0 <= seat["infl.alliances"] <= 4


def test_fremen2_round_and_hooks_round_fall_within_the_game(
    base_games: list[dict[str, Any]], full_games: list[dict[str, Any]]
) -> None:
    for game in (*base_games, *full_games):
        rounds = game["game"]["rounds"]
        for seat in game["seats"]:
            for column in ("infl.fremen2_round", "infl.hooks_round"):
                value = seat[column]
                assert value is None or 1 <= value <= rounds


def test_early_reveal_buys_require_an_early_reveal(
    all_seats: list[dict[str, Any]],
) -> None:
    for seat in all_seats:
        assert seat["infl.early_reveals"] >= 0
        assert seat["infl.early_reveal_faction_buys"] >= 0
        if seat["infl.early_reveals"] == 0:
            assert seat["infl.early_reveal_faction_buys"] == 0


def test_track_threshold_columns_match_a_recomputation_from_the_tracks(
    all_seats: list[dict[str, Any]],
) -> None:
    # Independent of tracks_0_1/tracks_ge2/tracks_ge4's own implementation:
    # a wrong threshold (e.g. tracks_ge4 counting >= 3) still satisfies the
    # partition/ordering check above but disagrees with this recomputation
    # from the four track columns themselves.
    for seat in all_seats:
        tracks = (
            seat["infl.emperor"],
            seat["infl.guild"],
            seat["infl.bene_gesserit"],
            seat["infl.fremen"],
        )
        assert seat["infl.tracks_0_1"] == sum(1 for t in tracks if t <= 1)
        assert seat["infl.tracks_ge2"] == sum(1 for t in tracks if t >= 2)
        assert seat["infl.tracks_ge4"] == sum(1 for t in tracks if t >= 4)


def _play_with_faction_oracle(spec: T.MatchSpec) -> list[dict[str, int]]:
    """Replay ``spec`` once, tallying each seat's net Influence per Faction.

    Reads only ``influence_gained``/``influence_lost`` payloads' ``player``/
    ``faction``/``amount`` fields -- never an ``event_id`` -- so this shares
    no bucketing logic with ``InfluenceCollector``/``_source_category`` and
    cross-checks the final per-Faction track values independently. The loop
    itself mirrors ``tip_census.play`` (the only place it is otherwise
    written, per that module's docstring), trimmed to just this tally.
    """

    from dune_imperium.core.chance import ChanceResolver
    from dune_imperium.core.decisions import ChanceDecision
    from dune_imperium.core.state import GamePhase
    from dune_imperium.simulation.runner import _state_agents

    factions = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    config = spec.config
    engine = (
        UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else UprisingRulesEngine()
    )
    agents = tuple(
        make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    searchers = _state_agents(agents)
    net: list[dict[str, int]] = [
        dict.fromkeys(factions, 0) for _ in range(len(spec.seat_agents))
    ]
    state = engine.reset(config, spec.game_seed)
    chance = ChanceResolver(seed=spec.game_seed)
    for _ in range(spec.max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        assert decision is not None, "a non-FINISHED game always has a decision"
        if isinstance(decision, ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
        else:
            owner = decision.owner
            legal = engine.legal_actions(state, owner)
            observation = engine.observe(state, owner)
            searcher = searchers[owner]
            action = (
                searcher.choose_action_with_state(state, observation, legal)
                if searcher is not None
                else agents[owner].choose_action(observation, legal)
            )
            if action not in legal:
                action = legal[0]
            result = engine.apply(state, action, legal_actions=legal)
        for event in result.events:
            if event.kind not in ("influence_gained", "influence_lost"):
                continue
            data = dict(event.payload)
            player = data.get("player")
            faction = data.get("faction")
            if not isinstance(player, int) or faction not in net[0]:
                continue
            sign = 1 if event.kind == "influence_gained" else -1
            net[player][faction] += sign * int(data["amount"])
        state = result.state
    else:
        raise RuntimeError(f"step limit reached for seed {spec.game_seed}")
    return net


@pytest.fixture(scope="module")
def faction_oracle_nets(tip_census: ModuleType) -> list[dict[str, int]]:
    # Same specs, same order, as base_games + full_games (_seat_rows' flatten
    # of _specs(False) then _specs(True), each game's seats 0..3 in order).
    nets: list[dict[str, int]] = []
    for full in (False, True):
        for spec in _specs(full):
            nets.extend(_play_with_faction_oracle(spec))
    return nets


def test_final_track_equals_gained_minus_lost_per_faction(
    all_seats: list[dict[str, Any]], faction_oracle_nets: list[dict[str, int]]
) -> None:
    # test_final_tracks_equal_gained_minus_lost above only checks the 4
    # tracks' combined sum, which a bug that moves points between Factions
    # would still satisfy; this checks each Faction against an oracle that
    # never touches _source_category.
    assert len(all_seats) == len(faction_oracle_nets)
    columns = {
        "emperor": "infl.emperor",
        "spacing_guild": "infl.guild",
        "bene_gesserit": "infl.bene_gesserit",
        "fremen": "infl.fremen",
    }
    for seat, net in zip(all_seats, faction_oracle_nets, strict=True):
        for faction, column in columns.items():
            assert net[faction] == seat[column]


def test_source_category_routes_navigation_gains_to_leader(
    influence_module: ModuleType,
) -> None:
    category = influence_module._source_category
    # Bare visit: exactly "round:<r>:player:<p>:influence:<faction>:influence".
    assert category("round:5:player:1:influence:fremen:influence") == "visit"
    # Regression (full ruleset seed 6, round 5, seat 1 steersman_y_rkoon,
    # action choose_intrigue_faction): Plot Course's Navigation card,
    # triggered by reaching 2 Influence on a bare visit, keeps the visit's
    # own event shape with ":navigation:..." spliced into the middle -- must
    # not be misread as a second visit.
    assert (
        category(
            "round:5:player:1:influence:fremen:navigation:0:slot:1:gained:"
            "fremen:influence"
        )
        == "leader"
    )
    # A Navigation card triggered off a Conflict reward keeps that shape too,
    # and must not be misread as the reward itself.
    assert (
        category(
            "round:9:combat_reward:distinct_influence:3:2:fremen:navigation:"
            "0:slot:0:gained:fremen:influence"
        )
        == "leader"
    )
    assert (
        category("round:9:combat_reward:distinct_influence:3:2:fremen:influence")
        == "combat_reward"
    )
    # Immortality's Agent-box paid resource choice aliases to "agent_card",
    # not a stray "agent_card_payment" bucket.
    assert (
        category(
            "round:5:player:2:agent_card_payment:research:research:c1r1:"
            "influence:fremen:influence"
        )
        == "agent_card"
    )


def test_navigation_gain_is_bucketed_leader_in_a_real_game(
    tip_census: ModuleType,
) -> None:
    # A real game with the visit-triggered Navigation shape the mapping above
    # is quoted from, played end to end: the Navigation-card gain must land
    # under "leader", and every other resolve_faction_influence gain (8 of
    # them) must land under visit:*. Re-pinned 2026-09-26 for the
    # card-transcription audit's rules fixes (codec v108): seed 6 now diverges
    # at round 3's new Tech offer on a High Council visit and its Navigation
    # gain is Intrigue-triggered, so the pin is seed 27 seat 0, the first seat
    # in 1-200 whose bare visit (round 3, Emperor) triggers it; the
    # bare-visit, Navigation and total Influence events were checked against
    # the game's own events.
    game = tip_census.play(_spec(True, 27), ("influence",))
    seat0 = game["seats"][0]
    assert seat0["leader"] == "steersman_y_rkoon"
    sources = seat0["infl.sources"]
    assert sources.get("leader") == 1
    assert sources.get("visit:starter", 0) + sources.get("visit:bought", 0) == 8
    assert seat0["infl.gained"] == 14


def test_fremen2_round_uses_the_decision_round_not_a_folded_next_round(
    tip_census: ModuleType,
) -> None:
    # Base ruleset, seed 1, seat 2: Fremen Influence reaches 2 on the Conflict
    # reward paid by the round's last Combat Intrigue pass, which folds
    # straight through Makers, Recall and Round Start into the next round
    # within the same ``engine.apply``. ``s.post.round_number`` would
    # misreport this as round 4; the decision itself was taken in round 3.
    # Re-pinned 2026-09-26 for the card-transcription audit's rules fixes
    # (codec v108): seed 4 now diverges at round 6's Double Agent Spy (now
    # limited to the visited space) and seat 3 reaches Fremen 2 mid-round, so
    # the pin moved to seed 1 seat 2, the first base seed in 1-200 with the
    # fold; the step's Fremen reward event and its round 3 -> 4 transition
    # were checked.
    game = tip_census.play(_spec(False, 1), ("influence",))
    assert game["seats"][2]["infl.fremen2_round"] == 3


def test_pinned_influence_lands_and_spy_columns_for_two_traced_seats(
    tip_census: ModuleType,
) -> None:
    # Two full-ruleset seats pinning columns this module's fixes touch, plus
    # a cross-section of the rest, so a regression that does not break a
    # sum/partition invariant is still caught (mutation testing found 10 of
    # 11 mutants otherwise survive). The pin was a hand-traced seed 3, seat 1
    # until the 2026-09-25 Storms in the South correction changed that game
    # and left several pinned columns at zero; no single seat of seeds 1-200
    # now reaches every column that seat did, so two seats share them.
    # Re-pinned 2026-09-26 for the card-transcription audit's rules fixes
    # (codec v108): seeds 158 and 156 now diverge at round 3's new Tech offer
    # on a Swordmaster visit and neither seat 0 gains Maker Hooks any more, so
    # seed 158 seat 0 keeps its role with new values (Intrigue, Combat-reward,
    # Agent-card and Shipping board sources, a trashed Spy, other recalls,
    # two Infiltrates taken) and seed 3 seat 2 replaces seed 156 (Reveal-card
    # and acquisition sources, Maker Hooks, an Infiltrate offer declined,
    # Spies left on the board); the Influence events by source, Spies placed,
    # used, recalled and trashed, Infiltrate offers and the Reveal means were
    # checked against the games' own events.
    game = tip_census.play(_spec(True, 158), ("influence",))
    seat0 = game["seats"][0]
    assert seat0["infl.sources"] == {
        "visit:starter": 1,
        "visit:bought": 1,
        "board": 2,
        "combat_reward": 1,
        "agent_card": 2,
        "intrigue": 2,
    }
    assert seat0["infl.gained"] == 9
    assert seat0["infl.lost"] == 2
    assert seat0["infl.fremen2_round"] == 9
    assert seat0["infl.hooks_round"] is None
    assert seat0["lands.reveal_cards"] == pytest.approx(3.1)
    assert seat0["lands.reveal_persuasion"] == pytest.approx(5.6)
    assert seat0["spy.placed"] == 8
    assert seat0["spy.used_gather"] == 2
    assert seat0["spy.recalled_other"] == 2
    assert seat0["spy.trashed"] == 1
    assert seat0["spy.on_board_end"] == 1
    assert seat0["spy.use_lag"] == pytest.approx(1.75)
    assert seat0["spy.infiltrate_offered"] == 2
    assert seat0["spy.infiltrate_taken"] == 2

    game = tip_census.play(_spec(True, 3), ("influence",))
    seat2 = game["seats"][2]
    assert seat2["infl.sources"] == {
        "visit:starter": 3,
        "visit:bought": 3,
        "board": 1,
        "reveal_card": 1,
        "combat_reward": 2,
        "intrigue": 2,
        "acquisition": 1,
    }
    assert seat2["infl.gained"] == 13
    assert seat2["infl.lost"] == 0
    assert seat2["infl.fremen2_round"] == 4
    assert seat2["infl.hooks_round"] == 4
    assert seat2["lands.reveal_cards"] == pytest.approx(4.1)
    assert seat2["lands.reveal_persuasion"] == pytest.approx(4.9)
    assert seat2["spy.placed"] == 6
    assert seat2["spy.used_gather"] == 2
    assert seat2["spy.recalled_other"] == 1
    assert seat2["spy.on_board_end"] == 3
    assert seat2["spy.use_lag"] == pytest.approx(1.0)
    assert seat2["spy.infiltrate_offered"] == 2
    assert seat2["spy.infiltrate_taken"] == 0


def test_subversive_advisor_credits_the_visit_and_the_card_effect(
    influence_module: ModuleType,
    census_step_class: type,
    base_reset_state: GameState,
) -> None:
    # "일반 Influence 1 대신 해당 Faction Influence 2를 얻고 ... 총 3을 얻지
    # 않는다" [player-turns.md:103-107, Main pp. 9, 11, 20]: the card's Agent
    # box replaces the visit's own Influence, so its 2-point gain must not
    # land only in "agent_card" with nothing under "visit:*".
    collector = influence_module.InfluenceCollector(_specs(False)[0], 4)
    event = GameEvent(
        event_id=(
            "round:5:player:1:agent_card:imperium:subversive_advisor:3:"
            "influence:fremen:influence"
        ),
        kind="influence_gained",
        payload=(("amount", 2), ("faction", "fremen"), ("player", 1)),
    )
    step = census_step_class(
        pre=base_reset_state,
        post=base_reset_state,
        owner=None,
        action=None,
        legal=(),
        events=(event,),
    )
    collector.step(step)
    assert collector._gained[1] == 2
    assert dict(collector._sources[1]) == {"visit:bought": 1, "agent_card": 1}


def test_early_reveals_excludes_a_forced_reveal(
    influence_module: ModuleType,
    census_step_class: type,
    base_reset_state: GameState,
) -> None:
    collector = influence_module.InfluenceCollector(_specs(False)[0], 4)
    owner = 0
    reveal = DomainAction(action_id="reveal_turn", actor=owner)
    agent = DomainAction(
        action_id="agent_turn",
        actor=owner,
        arguments=(("card_id", "x"), ("space_id", "y")),
    )

    # Forced: no "agent_turn" is legal (e.g. an all-starter hand that cannot
    # afford any space), so Reveal is not a real choice -- not the tip's
    # "choose to Reveal early" [player-turns.md:6, Main p. 8].
    forced = census_step_class(
        pre=base_reset_state,
        post=base_reset_state,
        owner=owner,
        action=reveal,
        legal=(reveal,),
        events=(),
    )
    collector.step(forced)
    assert collector._early_reveals[owner] == 0
    assert collector._reveal_open[owner] is False

    # Chosen: an Agent turn was legal too, so Revealing instead is the tip's
    # choice and counts.
    chosen = census_step_class(
        pre=base_reset_state,
        post=base_reset_state,
        owner=owner,
        action=reveal,
        legal=(reveal, agent),
        events=(),
    )
    collector.step(chosen)
    assert collector._early_reveals[owner] == 1
    assert collector._reveal_open[owner] is True


def test_reveal_finished_closes_the_window_before_the_next_turn_action(
    influence_module: ModuleType,
    census_step_class: type,
    base_reset_state: GameState,
) -> None:
    owner = 0
    reveal = DomainAction(action_id="reveal_turn", actor=owner)
    agent = DomainAction(
        action_id="agent_turn",
        actor=owner,
        arguments=(("card_id", "x"), ("space_id", "y")),
    )
    opened = census_step_class(
        pre=base_reset_state,
        post=base_reset_state,
        owner=owner,
        action=reveal,
        legal=(reveal, agent),
        events=(),
    )
    finished_event = GameEvent(
        event_id=f"round:1:player:{owner}:reveal_finished",
        kind="reveal_finished",
        payload=(("player", owner),),
    )
    finished_step = census_step_class(
        pre=base_reset_state,
        post=base_reset_state,
        owner=None,
        action=None,
        legal=(),
        events=(finished_event,),
    )
    # bene_gesserit_operative prints a Faction (Bene Gesserit) Agent icon.
    acquired_event = GameEvent(
        event_id=f"round:1:player:{owner}:acquire:bene_gesserit_operative:0",
        kind="card_acquired",
        payload=(("card_id", "bene_gesserit_operative"), ("player", owner)),
    )
    late_step = census_step_class(
        pre=base_reset_state,
        post=base_reset_state,
        owner=None,
        action=None,
        legal=(),
        events=(acquired_event,),
    )

    # Sanity: the same acquisition, with the window left open (no
    # reveal_finished in between), is counted -- so the assertion below is
    # not vacuously true.
    open_collector = influence_module.InfluenceCollector(_specs(False)[0], 4)
    open_collector.step(opened)
    open_collector.step(late_step)
    assert open_collector._early_reveal_faction_buys[owner] == 1

    # A card bought after reveal_finished (Combat, Makers, ...) is not
    # "during" the Reveal, even though this seat's next top-level turn
    # choice is still a round away -- would have counted under the old
    # next-action-based close.
    collector = influence_module.InfluenceCollector(_specs(False)[0], 4)
    collector.step(opened)
    assert collector._reveal_open[owner] is True
    collector.step(finished_step)
    assert collector._reveal_open[owner] is False
    collector.step(late_step)
    assert collector._early_reveal_faction_buys[owner] == 0


# --- LandsraadCollector ------------------------------------------------------


def test_swordmaster_and_council_order_is_mutually_exclusive(
    all_seats: list[dict[str, Any]],
) -> None:
    for seat in all_seats:
        flags = (
            seat["lands.sm_first"],
            seat["lands.hc_first"],
            seat["lands.same_round"],
        )
        assert sum(flags) <= 1
        sm, hc = seat["lands.swordmaster_round"], seat["lands.council_round"]
        if sm is None and hc is None:
            assert flags == (False, False, False)
        if sm is not None:
            assert sm >= 1
        if hc is not None:
            assert hc >= 1


def test_reveal_persuasion_state_split_covers_the_overall_mean(
    all_seats: list[dict[str, Any]],
) -> None:
    for seat in all_seats:
        if seat["lands.reveal_cards"] is not None:
            per_state = (
                seat["lands.reveal_cards_none"],
                seat["lands.reveal_cards_sm"],
                seat["lands.reveal_cards_hc"],
                seat["lands.reveal_cards_both"],
            )
            assert any(value is not None for value in per_state)
        else:
            assert seat["lands.reveal_persuasion"] is None


# --- SpyCollector ------------------------------------------------------------


def test_spy_conservation_invariant(all_seats: list[dict[str, Any]]) -> None:
    # Every Spy this seat ever placed left the board through exactly one of
    # Infiltrate, Gather Intelligence, another recall, or being trashed --
    # or is still on the board at game end. No Spy starts on the board
    # (PlayerState defaults spy_post_ids=()), so no adjustment is needed.
    for seat in all_seats:
        assert seat["spy.placed"] == (
            seat["spy.used_infiltrate"]
            + seat["spy.used_gather"]
            + seat["spy.recalled_other"]
            + seat["spy.trashed"]
            + seat["spy.on_board_end"]
        )


def test_spy_used_counts_match_taken_counts(all_seats: list[dict[str, Any]]) -> None:
    for seat in all_seats:
        assert seat["spy.used_infiltrate"] == seat["spy.infiltrate_taken"]
        assert seat["spy.used_gather"] == seat["spy.gather_taken"]
        assert seat["spy.infiltrate_taken"] <= seat["spy.infiltrate_offered"]
        assert seat["spy.gather_taken"] <= seat["spy.gather_offered"]


def test_spy_use_lag_is_nonnegative(all_seats: list[dict[str, Any]]) -> None:
    for seat in all_seats:
        lag = seat["spy.use_lag"]
        assert lag is None or lag >= 0


def test_infiltrate_and_gather_are_exercised_across_the_sample(
    all_seats: list[dict[str, Any]],
) -> None:
    # A weak sanity check that the sample actually exercises both paths, so
    # the invariants above are not vacuously true.
    assert sum(seat["spy.infiltrate_taken"] for seat in all_seats) > 0
    assert sum(seat["spy.used_gather"] for seat in all_seats) > 0
    assert sum(seat["spy.placed"] for seat in all_seats) > 0
