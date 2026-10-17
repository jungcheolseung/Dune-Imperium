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
    # the game's own events. Re-pinned 2026-09-27 for OQ-070 (a recruited
    # Commander's deploy slot is kept for a Commander): seed 27 now diverges
    # at round 6, where seat 1's recruited Commander takes the slot a troop
    # used to fill; seat 0 keeps its round-3 Navigation gain and 8 visit
    # gains, but the game now runs to round 10 and its total is 15 (two
    # Reveal gains and two Agent-box gains, was one each; one Panopticon
    # Endgame gain, was two), checked against the game's own events.
    # Re-derived 2026-10-01 for OQ-095 (every Agent turn ends only through its
    # owner's finish_agent_turn; codec v125): the games differ from the first
    # Agent turn on and seed 27 seat 0's Navigation gain is now triggered by
    # a Reveal gain. A scratch replay of full seeds 1-200 listing every
    # Influence gain with a "navigation" token gives seed 61 seat 0 as the
    # first seat whose bare visit triggers it (round 8, an Espionage visit
    # takes Bene Gesserit from 1 to 2; the Navigation card's slot 1 gains a
    # Fremen). Its other gains are 7 bare visits (resolve_faction_influence
    # steps) and one Agent-box Research gain, 9 in all, checked against the
    # game's own events.
    # Re-derived 2026-10-03 for codec v129 (Distraction and Coercive
    # Negotiation play only after 3+ units were deployed this turn, OQ-016):
    # seed 61 diverges in round 1 at seat 3's Distraction (it used to be played
    # at once and wait face up; now seat 3 resolves its Spice Refinery effect
    # instead), so seat 0's whole game changed, but it still fills the role: in
    # round 8 a Spacing Guild visit with a starter Diplomacy takes Spacing Guild
    # from 1 to 2 and the Navigation card's slot 1 gains a Bene Gesserit, so the
    # seed stays. (A scratch replay of full seeds 1-200 again lists seed 27
    # seat 0, round 6, as an earlier bare-visit trigger; seed 61 is kept
    # because it still fills the role.) Its other gains are now 11 bare visits
    # (resolve_faction_influence steps, 5 on starter cards and 6 on bought
    # ones) and one Agent-box Research gain, 13 in all (was 7 and 9). A scratch
    # replay that does not import the collector recounted them from the game's
    # own events.
    # Re-derived 2026-10-04 for the Emperor track Spy as an in-turn action
    # (user ruling 2026-10-04, overriding OQ-057 (15)): seed 61 diverges in
    # round 6 at seat 1's place_track_spy (one more heuristic decision, so its
    # random tie-break then picks another post) and seat 0 no longer has a
    # visit-triggered Navigation gain. A scratch replay of full seeds 1-200
    # listing every Influence gain with a "navigation" token gives seed 27
    # seat 0 first again (round 6, an Emperor visit; the Navigation card's
    # slot 1 gains a Fremen); that game diverges only in round 7. Its other
    # gains were 9 bare visits and 20 in all; since the 2026-10-04
    # deployment-allowance ruling (OQ-029) seat 2's Leader retreat no longer
    # lets it deploy two more troops in round 7, and the game now ends with
    # 10 bare visits and 18 gains (the round-6 Navigation gain is unchanged).
    # Re-traced for OQ-098 (codec v135): the separate Tech reward decisions
    # change later choices. Seed 27 seat 0 still exercises a bare Emperor
    # visit triggering Navigation, now in round 3. Its own events contain
    # 2 starter + 6 bought visits, 1 Navigation, 2 Intrigue, 1 Agent-card
    # and 2 Tech gains: 14 total (independent replay, no collector imports).
    # Re-derived 2026-10-06 for d5512ad0 (the heuristic plays Harvest Cells
    # only after the Conflict resolves; codec v137): seed 27 seat 0 is still
    # the first seat in full seeds 1-200 whose bare visit triggers
    # Navigation (round 3, an Emperor visit with Sardaukar Coordination;
    # slot 1 gains an Emperor). Its own events now contain 2 starter + 5
    # bought visits, 1 Navigation, 1 Intrigue, 1 Agent-card and 2 Endgame
    # Panopticon gains: 12 total (independent replay, no collector imports).
    # Re-derived 2026-10-07 for 5654d7f8 (a Combat Intrigue pass right after
    # a card play no longer counts as a consecutive pass; codec v139): seed
    # 27 seat 0 is still the first seat in full seeds 1-200 whose bare visit
    # triggers Navigation, with the same round-3 Emperor visit and the same
    # gains through round 8, but the two Endgame Panopticon gains are gone:
    # 2 starter + 5 bought visits, 1 Navigation, 1 Intrigue (Tenuous Bond)
    # and 1 Agent-card (Scientific Breakthrough's research step) gain, 10
    # total (independent replay, no collector imports).
    # Re-counted 2026-10-10 for Imperial Privilege's card draw as its own
    # icon (user ruling 2026-10-10, OQ-027 (d), codec v142): seed 27 first
    # diverges at round 4, seat 1's Imperial Privilege visit, after seat 0's
    # round-3 Emperor visit has triggered Navigation, so seat 0 is still the
    # first seat in full seeds 1-200 whose bare visit triggers it (seed 6
    # seat 1's Navigation gain comes from a Conflict reward). Its own events
    # now contain 2 starter + 6 bought visits, 1 Navigation, 3 Intrigue,
    # 4 Conflict-reward and 1 Agent-card gain: 17 total (independent replay,
    # no collector imports; the previous commit's engine gives the values
    # pinned before).
    # Re-counted 2026-10-10 for a triggered draw held as the owner's own step
    # (user ruling 2026-10-10, OQ-106, codec v142): seed 27 first diverges at
    # round 6, seat 0's research direction (c3r5), whose Tleilaxu track
    # Intrigue card is now its own step, after its round-3 Emperor visit has
    # triggered Navigation; no earlier full seed has a bare visit trigger it
    # (a scan of seeds 1-27's "navigation" gains). Its own events now contain
    # 8 visits, 1 Navigation, 1 Intrigue (Tenuous Bond), 1 Conflict reward of
    # 2, 1 Agent-card (Scientific Breakthrough's research step) and 1 Tech
    # (Navigation Chamber's acquire icon) gain: 14 total (independent replay,
    # no collector imports; the previous commit's engine gives the values
    # pinned before).
    # Re-counted 2026-10-12 for both grafted Agent boxes offered from the
    # start (codec v143, docs/graft-boxes-plan.md: no ``switch_graft_card``,
    # box 1's rows tagged ``box=1``): seed 27 first diverges at round 4,
    # seat 1's grafted Agent turn at Hagga Basin, whose legal list no longer
    # holds the switch, after seat 0's round-3 Emperor visit has triggered
    # Navigation. Its own events now contain 7 visits (rounds 1, 2, 3, 3, 5,
    # 5, 7), 1 Navigation, 2 Intrigue (Tenuous Bond, Withdrawal Agreement)
    # and 1 acquisition (Spiritual Fervor's Research bonus) gain: 11 total
    # (independent replay, no collector imports; the previous commit's
    # engine gives the values pinned before).
    # Re-derived 2026-10-14 -- v146: optional Agent-turn effects offer no
    # refusal (OQ-095 (2), 2026-10-14): seed 27 first diverges at round 1,
    # seat 3's Secrets visit (Reverend Mother's repeat offers no
    # ``decline_leader_board_repeat``), and seat 0's Navigation gain is now
    # triggered by an Agent-card gain (Public Spectacle, round 7). A scan of
    # full seeds 1-200 listing every Influence gain with a "navigation"
    # token gives seed 31 seat 1 (Steersman Y'rkoon) as the first seat whose
    # bare visit triggers it: in round 6 a Bene Gesserit visit takes Bene
    # Gesserit from 1 to 2 and the Navigation card's slot 1 gains an
    # Emperor. Its own events contain 9 visits (rounds 1, 1, 3, 6, 6, 7, 8, 8
    # and 9), 1 Navigation, 2 Intrigue (Imperium Politics, Tenuous Bond), 1
    # Agent-card (Experimentation's research step) and 1 acquisition
    # (Imperial Throneship) gain: 14 total (independent replay, no collector
    # imports; the previous commit's engine gives the values pinned before).
    # Re-derived 2026-10-18 for cleanup-2b (codec v149: in-turn research
    # bonuses and optional trashes as turn rows, a research space's two
    # icons as their own steps in the owner's order, no Influence offered at
    # the top for Shipping and Tech acquire): seed 31 first diverges at
    # round 4, seat 1's Experimentation research step (c3r5, step 273 of the
    # game), whose Specimens and Tleilaxu-track icons are now offered as two
    # ``resolve_research_icon`` rows instead of resolving in that one move
    # (step 274 no longer offers ``draw_owed_intrigue``). Seat 1 still fills
    # the role: a scan of full seeds 1-200 listing every Influence gain with
    # a "navigation" token whose id prefix is the bare-visit shape gives seed
    # 31 seat 1 first on this engine and on a ``git archive`` export of the
    # previous commit (a1b692f0), then seeds 53, 61 and 83, so the seed
    # stays. Its round-6 Bene Gesserit visit still takes Bene Gesserit from
    # 1 to 2, but the Navigation card's slot 1 now gains a Fremen (was an
    # Emperor) and the later gains differ: 7 visits (rounds 1, 1, 3, 6, 6, 7
    # and 8; 5 on starter cards, 2 on bought ones), 1 Navigation, 4 Intrigue
    # (Imperium Politics, Tenuous Bond, Withdrawal Agreement, Sietch
    # Ritual), 2 Agent-card (Experimentation's research step in round 5 and
    # a starter Diplomacy trashed for an Emperor in round 8) and 2 Endgame
    # Panopticon Tech gains: 16 total (independent replay, no collector
    # imports; on the previous commit's engine it recounts the values pinned
    # before).
    # Re-counted 2026-10-18 for the Conflict-end order (user decision
    # 2026-10-18, codec v149: the Conflict's troops and Commanders go back to
    # the supply before the Conflict-end windows, and Harvest Cells resolves
    # the moment it is played): seed 31 first diverges at round 8, seat 3's
    # Conflict-end window (step 792 of the game, counting chance steps from
    # 0). Seat 3 plays Harvest Cells at step 791 on both engines, but now its
    # 2 specimens come with the play, so step 792 offers its Tleilaxu
    # acquisition (seat 3 takes Subject X-137) where the previous engine
    # offered ``decline_conflict_end_intrigue`` and only then the
    # acquisition. Seat 1 still fills the role: a scan of full seeds 1-200
    # listing every Influence gain with a "navigation" token whose id prefix
    # is the bare-visit shape gives seed 31 seat 1 first again, on this
    # engine and on a ``git archive`` export of the previous commit
    # (7ae17717), then seeds 53, 61 and 83, so the seed stays. Its round-6
    # Navigation gain (a Bene Gesserit visit on the bought Branching Path,
    # slot 1 gains a Fremen) comes at step 476, long before the divergence,
    # and so do its visits through round 7; the game now reaches Endgame in
    # round 9, when seat 2's Conflict win takes it to 10 Victory Points (it
    # ended in round 10 with the Conflict deck empty).
    # Seat 1's own events now contain 7 visits (rounds 1, 1, 3, 6, 6, 7 and
    # 8; 5 on starter cards, 2 on bought ones), 1 Navigation, 2 Intrigue
    # (Imperium Politics, Tenuous Bond), 2 Agent-card (Experimentation's
    # research step in round 5 and a starter Diplomacy trashed for an Emperor
    # in round 8) and 2 Endgame Panopticon Tech gains (Spacing Guild and
    # Fremen, was Spacing Guild and Bene Gesserit): 14 total (independent
    # replay, no collector imports; was 16 with two more Intrigue gains,
    # Withdrawal Agreement in round 9 and Sietch Ritual in round 10, which
    # the shorter game no longer reaches; on the previous commit's engine it
    # recounts the values pinned before).
    game = tip_census.play(_spec(True, 31), ("influence",))
    seat = game["seats"][1]
    assert seat["leader"] == "steersman_y_rkoon"
    sources = seat["infl.sources"]
    assert sources.get("leader") == 1
    assert sources.get("visit:starter", 0) + sources.get("visit:bought", 0) == 7
    assert seat["infl.gained"] == 14


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
    # Re-pinned 2026-09-27 for OQ-070 (a recruited Commander's deploy slot is
    # kept for a Commander): seeds 158 and 3 now diverge where a recruited
    # Commander takes the deploy slot a troop used to fill (seed 158 round 7,
    # seat 0's own; seed 3 round 6, seat 1's), after which seed 158 seat 0
    # gains no board Influence and is offered no Infiltrate, and seed 3 seat 2
    # gains nothing from an acquisition and is offered no Infiltrate. Seed 177
    # seat 1 is now the only seat in 1-200 in the first role (Intrigue,
    # Combat-reward, Agent-card and board -- here Glowglobes -- sources, a
    # trashed Spy, other recalls, two or more Infiltrates taken; it adds
    # Reveal-card, Reveal-gain and Navigation sources). Seed 161 seat 0 takes
    # the second (Reveal-card and acquisition sources, Maker Hooks, an
    # Infiltrate offer declined, Spies left on the board): seed 10 seat 1 is
    # the first such seat, but its Spy use lag and seed 177's are both a whole
    # 1.0, and seed 161 seat 0 is the first with a fractional one (0.8), so
    # the mean's division stays pinned as seed 158's 1.75 kept it. The
    # Influence events by source, Spies placed, used, recalled and trashed,
    # Infiltrate offers and the Reveal means were checked against the games'
    # own events.
    # Re-pinned 2026-09-27 for observation v21 (the four Rise of Ix Contract
    # tiles out, the four standard ones in [Main p. 16]): seed 177 seat 1 and
    # seed 161 seat 0 no longer fill their roles, and no seat of seeds 1-200
    # does. Seeds 201-600 give seed 240 seat 2 as the only seat in the first
    # role (with Reveal-gain sources and Maker Hooks too) and seed 287 seat 3
    # as the first in the second (a fractional Spy use lag, 4/7). The
    # Influence gained and lost, Spies placed and trashed and Infiltrates
    # taken were recounted from the games' own events.
    # Re-derived 2026-10-01 for OQ-095 (every Agent turn ends only through its
    # owner's finish_agent_turn; codec v125): the games differ from the first
    # Agent turn on: seed 240 seat 2 has no board or Agent-card source, no
    # trashed Spy and one Infiltrate, and seed 287 seat 3 no acquisition
    # source, so neither fills its role any more. Seeds 1-200 now give five
    # seats in the first role (seeds 7, 88, 128, 145, 199) and three in the
    # second (19, 171, 172); the pins are the first of each. Seed 7 seat 1
    # (Lady Margot Fenring) takes the first (here the board source is a
    # Navigation Chamber bought on a High Council visit; it adds Maker Hooks
    # and nine Forbidden Weapons Influence losses, and its five Spy uses
    # average a whole 1.0 lag). Seed 19 seat 1 (Liet Kynes) takes the second
    # (Spice Must Flow's Contract reward is the acquisition source), with a
    # fractional Spy use lag (1/2). A scratch
    # replay recounted from the games' own events and legal action sets: the
    # Influence events by source, the fremen >= 2 and Maker Hooks rounds,
    # the reveal_started cards and Persuasion, every Spy placement, use,
    # recall and trash with its rounds, and the Infiltrate offers and takes.
    # Re-derived 2026-10-02 for L2 group A decision windows: seed 7 now
    # diverges in round 5 (seat 3's Imperial Privilege recall with no target
    # opens its confirm window) and seat 1 has no board source and no trashed
    # Spy; seed 19 diverges in round 3 (seat 2's Desert Power without Maker
    # Hooks opens its choice window) and seat 1 has no acquisition source and
    # takes every Infiltrate it is offered. Neither fills its role any more.
    # Full seeds 1-200 now give two seats in the first role (seeds 145 and
    # 199) and none in the second; seeds 201-600 give one more in the first
    # (531) and seed 390 seat 1 as the only seat in the second. Seed 145
    # seat 3 (Staban Tuek) takes the first (the board source is again a
    # Navigation Chamber bought on a High Council visit; no Maker Hooks, and
    # its three Spy uses average a whole 1.0 lag). Seed 390 seat 1 (Liet
    # Kynes) takes the second (a Steersman buy is the acquisition source),
    # with a fractional Spy use lag (2/3). Neither seat gains Reveal
    # Persuasion after its reveal_started event (no reveal_persuasion_gained
    # event, so no Desert Power Persuasion branch either). The same scratch
    # replay recounted every column below from the games' own events, state
    # and legal action sets.
    # Re-derived 2026-10-02 for codec v127 (a Combat Intrigue card whose own
    # window sits above the loop restarts the consecutive passes [Main p. 14]
    # and the loop drops a seat left with no unit, OQ-003): seed 145 diverges
    # in round 4 at seat 1's Reach Agreement (its Contract market used to
    # leave one pass counted) and seat 3 takes one Infiltrate, so it no
    # longer fills the first role. Seeds 1-200 now give seeds 128 and 199 in
    # the first role; seeds 201-600 add 204 and 531. Seed 390 seat 1 is
    # unchanged and keeps the second. Seed 128 seat 2 (Duncan Idaho) takes
    # the first (the board source is again a Navigation Chamber bought on a
    # High Council visit, the acquisition a Steersman; Maker Hooks in round
    # 10; five Spy uses at a 6/5 mean lag; no Persuasion gained after a
    # reveal_started event). A separate scratch replay, not importing the
    # collector, recounted every column below from the game's own events,
    # state and legal action sets.
    # Re-derived 2026-10-03 for codec v129 (Distraction and Coercive Negotiation
    # play only after 3+ units were deployed this turn, OQ-016): seed 128
    # diverges in round 4 at seat 1's Distraction (played at once and kept face
    # up before; now seat 1 declines the Tech at the Assembly Hall) and seat 2
    # has no Intrigue or board source, no trashed Spy and no Maker Hooks, and
    # takes every Infiltrate it is offered; seed 390 diverges in round 3 at
    # seat 0's Coercive Negotiation (now it resolves its Arrakeen troops
    # effect) and seat 1 has no Agent-card or acquisition source, no recall
    # and one Infiltrate offer, taken. Neither fills its role any more. Full
    # seeds 1-600 now give no seat in the first role; seeds 601-1800 give seed
    # 787 seat 0 (Chani) as the only one. Seeds 1-200 give no seat in the
    # second and seeds 201-600 give seeds 280, 476, 478, 481 and 528; the pin
    # is the first, seed 280 seat 0 (Chani), whose game is identical to what it
    # was before (neither Distraction nor Coercive Negotiation is played in
    # it), so it was already a seat in the second role: the same scan on the
    # pre-v129 engine gives seeds 128 and 199 in the first role and seeds 280,
    # 390, 478 and 481 in the second over seeds 1-600 (no 204 or 531). Seed 787
    # seat 0 takes the first (the board sources are a Navigation Chamber bought
    # on a High Council visit and Glowglobes bought on a Swordmaster visit; an
    # Endgame Panopticon Tech source; Maker Hooks in round 6; its Distraction,
    # played in round 10, places a Spy). Seed 280 seat 0 takes the second
    # (Spice Must Flow's Contract reward is the acquisition source, a Spacing
    # Guild's Favor Reveal gain the Reveal-card source), with a fractional Spy
    # use lag (5/2) and two Infiltrate offers declined in round 7. Neither seat
    # gains Reveal Persuasion after its reveal_started event (no
    # reveal_persuasion_gained event). A separate scratch replay, not importing
    # the collector, recounted every column below from the games' own events,
    # state and legal action sets; on the pre-v129 engine it first reproduced
    # the previous pins (seed 128 seat 2, seed 390 seat 1, seed 61 seat 0).
    # Re-derived 2026-10-04 for the Emperor track Spy as an in-turn action
    # (user ruling 2026-10-04, overriding OQ-057 (15)): seed 787 diverges in
    # round 7 at seat 1's place_track_spy (one more heuristic decision, so its
    # random tie-break then picks another post) and seat 0 no longer trashes
    # a Spy or recalls one otherwise. Full seeds 1-1800 now give seeds 1187
    # and 1740 (seat 2 each) in the first role; the same scan on the
    # pre-change engine gives seed 787 seat 0 alone, as above. Seed 280 seat 0
    # keeps the second: its game is identical (no seat reaches Emperor 4 in
    # its own turn there). Seed 1187 seat 2 (Shaddam Corrino IV), first
    # diverging in round 5 at seat 0's place_track_spy, takes the first: the
    # board source is a Navigation Chamber bought on a Swordmaster visit, the
    # Intrigue source Tenuous Bond, the Agent-card source a Guild
    # Impersonator; its Spy is trashed for Advanced Data Analysis, Insider
    # Information and an Espionage visit recall two more, and it takes three
    # of five Infiltrate offers; Maker Hooks in round 9; five Spy uses at a
    # whole 1.0 mean lag. Its reveal_started means leave out the 2 Persuasion
    # Command Center's Reveal choice adds afterwards in round 7. A scratch
    # replay that does not import the collector recounted every column below
    # from the game's own events, state and legal action sets.
    # Re-traced for OQ-098 (codec v135): queued Tech rewards carry their
    # own "tech" source. Independent engine replays over full seeds 1-200
    # find seed 16 seat 2 covering Tech/Intrigue/Agent-card/Conflict gains,
    # Spy trash/other recalls and both accepted and declined Infiltrates.
    # Seed 25 seat 0 covers acquisition/Reveal-card gains, Maker Hooks and
    # fractional Spy lag. Values below are recounted from game events,
    # decision action sets and state, without using the census collectors.
    # Re-derived 2026-10-06 for d5512ad0 (the heuristic plays Harvest Cells
    # only after the Conflict resolves; codec v137): seed 16 seat 2 has no
    # Agent-card source any more, and no seat of full seeds 1-200 fills the
    # first role. Seeds 201-600 give seed 415 seat 0 and seed 547 seat 3;
    # the pin is the first, seed 415 seat 0 (Count Hasimir Fenring: Tech
    # from Navigation Chamber's queued acquire icon, Intrigue from Sietch
    # Ritual, Agent-card from Possible Futures, one Conflict reward; a
    # trashed Spy and one other recall; Infiltrates taken in rounds 3 and 8,
    # declined in rounds 8 and 9; no Maker Hooks). Seed 25 seat 0 (Esmar
    # Tuek) still fills the second role (acquisition and Reveal-card gains,
    # Maker Hooks, a fractional Spy use lag of 5/4), so it stays, with new
    # values. An independent replay recounted every column below from the
    # games' own events, decision action sets and state.
    # Re-derived 2026-10-06 for 52007a8b (an Intrigue option is playable only
    # when at least one of its effects can change something, FAQ p. 2, user
    # ruling 2026-10-06; codec v138): seed 25 first diverges in round 3 at
    # seat 3's Twisted Calculating (now played after its first troop deploy,
    # not before), and seat 0 has one Reveal-card gain and places one Spy,
    # used at a whole 1.0 lag, so it no longer fills the second role. Seed
    # 415 seat 0 still fills the first with every column unchanged, so it
    # stays. Full seeds 1-200 give seeds 12, 91, 109 and 131 (seats 1, 1, 3
    # and 1) in the second role. Seed 12 seat 1 is the first, but it never
    # uses Gather Intelligence or recalls a Spy otherwise and takes all four
    # Infiltrates it is offered, which would pin those columns at zero or at
    # offered == taken; the pin is the next, seed 91 seat 1 (Muad'Dib: a
    # Steersman buy is the acquisition source, Captured Mentat's Influence
    # exchange the Reveal-card source and its one loss; Maker Hooks in round
    # 8; five Spy uses at a fractional 6/5 lag; five other recalls (Special
    # Mission, Insider Information and three placement recalls) and two
    # Spies left on the board; three Infiltrate offers in round 7, one
    # declined). An independent replay, not importing the collectors,
    # recounted every column below from the games' own events, decision
    # action sets and state; on the pre-change engine (c100ef29) it first
    # reproduced the previous seed 25 seat 0 values.
    # Re-derived 2026-10-07 for 5654d7f8 (a Combat Intrigue pass right after
    # a card play no longer counts as a consecutive pass; codec v139): seed
    # 415 seat 0 has no Agent-card source and no trashed Spy any more, and
    # seed 91 seat 1 no acquisition or Reveal-card source and no Maker
    # Hooks, so neither fills its role (no later commit of the batch moves
    # either game). No seat of full seeds 1-200 fills the first role; seeds
    # 201-600 give seed 287 seat 3 alone (Lady Margot Fenring: two Endgame
    # Panopticon Tech gains, Intrigue from Breakthrough's research step,
    # Agent-card from For Humanity, one Conflict reward; the Spy on the
    # Research Station is trashed for Advanced Data Analysis, and six are
    # recalled otherwise -- three by Panopticon's placements, one each by
    # the Signet Ring, an Espionage visit and Find Weakness; Infiltrates
    # taken in rounds 4, 7 and 8, declined in rounds 2 and 8; no Maker
    # Hooks; four Spy uses at a 5/4 lag). Seed 64 seat 3 (Shaddam Corrino
    # IV) is the first seat of seeds 1-600 in the second role (213 and 581
    # follow): Imperial Throneship's acquisition bonus and Pointing the
    # Way's Reveal are the acquisition and Reveal-card sources; Maker Hooks
    # in round 4; Gather Intelligence used three times and Infiltrate once
    # at a fractional 7/4 lag; one Spy moved off by seat 1's False Orders;
    # Infiltrate declined in round 5, taken in round 7. An independent
    # replay, not importing the collectors, recounted every column below
    # from the games' own events, decision action sets and state, and
    # matched the collectors exactly.
    # Re-derived 2026-10-09 for the Conflict-end window on public facts
    # (OQ-103, codec v141: a seat with at least three units in the Conflict
    # and an Intrigue card gets the window even when it can only decline,
    # and a heuristic seat draws for that one-action decision): seed 287
    # first diverges at round 4's Conflict end (seat 3 gets a decline-only
    # window) and seed 64 at round 1's (seat 0 does), and neither seat fills
    # its role any more; with the previous window rule patched back in, the
    # same recount reproduces the values pinned before. No seat of full
    # seeds 1-200 fills either role. Seeds 201-600 give seeds 264 (seat 3)
    # and 597 (seat 0) in the first role and seed 345 seat 2 alone in the
    # second; the pins are the first of each. Seed 264 seat 3 (Steersman
    # Y'rkoon): two Endgame Panopticon Tech gains, Intrigue from Buy Access,
    # Agent-card from Dangerous Rhetoric, two Conflict-reward gains; its
    # Landsraad Spy is trashed for Advanced Data Analysis (bought with Rapid
    # Engineering) and two are recalled by Spring the Trap; Infiltrates
    # taken in rounds 7, 8 and 10, declined in round 8; Maker Hooks in round
    # 10; three Spy uses at a 2/3 lag. Seed 345 seat 2 (Muad'Dib): Spiritual
    # Fervor's acquisition research step is the acquisition source and
    # Captured Mentat's Influence exchange (three times) the Reveal-card
    # source; Maker Hooks in round 3; Gather Intelligence and Infiltrate
    # used twice each at a fractional 1/2 lag; one Spy recalled by Sleeper
    # Unit; Infiltrate declined in round 7, taken in rounds 4 and 9; no Spy
    # left on the board. An independent replay, not importing the
    # collectors, recounted every column below from the games' own events,
    # decision action sets and state, and matched the collectors exactly.
    # Re-derived 2026-10-10 for Imperial Privilege's card draw as its own
    # icon (user ruling 2026-10-10, OQ-027 (d), codec v142): seed 264 first
    # diverges at round 7, seat 0's Imperial Privilege visit, and seed 345 at
    # round 6, seat 3's; seed 264 seat 3 no longer has an Intrigue or
    # Conflict-reward source, and seed 345 seat 2 no longer has an
    # acquisition source, so neither fills its role (the previous commit's
    # engine gives the values pinned before). Full seeds 1-600 give seeds
    # 486 (seat 3), 494 (seat 0) and 555 (seat 2) in the first role and
    # seeds 56 (seat 2), 67 (seat 2), 478
    # (seat 1) and 509 (seat 3) in the second; the pins are the first of
    # each. Seed 486 seat 3 (Lady Margot Fenring): an Endgame Panopticon
    # Tech gain, Intrigue from Change Allegiances (its one loss too),
    # Agent-card from Interstellar Conspiracy (twice) and Subversive
    # Advisor, two Conflict-reward gains; its Spice Refinery Spy is trashed
    # for Advanced Data Analysis, and Insider Information and Panopticon's
    # placement recall two more; Infiltrates taken in rounds 1, 6 and 8,
    # declined in rounds 4, 8 and 9; Gather Intelligence in rounds 7 and 8;
    # no Maker Hooks; five Spy uses at a whole 1.0 lag. Seed 56 seat 2
    # (Steersman Y'rkoon): Imperial Throneship's acquisition bonus is the
    # acquisition source, Ixian Ambassador's Reveal the Reveal-card source,
    # Navigation Chamber's queued acquire icon the Tech source; Maker Hooks
    # in round 10; Infiltrate in rounds 7 and 9 and Gather Intelligence in
    # round 10 at a fractional 10/3 lag; one Spy moved off by seat 1's Holy
    # War; Infiltrate declined once in round 7. An independent replay, not
    # importing the collectors, recounted every column below from the
    # games' own events, decision action sets and state, and matched the
    # collectors exactly.
    # Re-derived 2026-10-10 for Cunning's and Insider Information's draw as
    # its own step after their trash (OQ-106, codec v142): seed 486 first
    # diverges at round 4, seat 3's Insider Information trash, and seed 56
    # at round 5, seat 3's Cunning trash; seed 486 seat 3 no longer has an
    # Agent-card or Conflict-reward source and seed 56 seat 2 no longer has
    # a Reveal-card source, so neither fills its role (the previous commit's
    # engine gives the values pinned before). Full seeds 1-600 give seeds 26
    # (seat 1), 494 (seat 0) and 555 (seat 2) in the first role and seeds 54
    # (seat 2), 67 (seat 2), 478 (seat 1) and 509 (seat 3) in the second
    # (Reveal-card and acquisition sources, Maker Hooks, a fractional Spy use
    # lag, an Infiltrate taken and one declined); the pins are the first of
    # each, and the later splits of the same batch (Arrakis Planetologist,
    # Piter's and Reverse Engineering's rewards) leave both seats' columns
    # unchanged. Seed 26 seat 1 (Kota Odax of Ix): Tech (twice), Intrigue,
    # Agent-card (twice), acquisition and Conflict-reward sources, one loss;
    # a trashed Spy and one other recall; Infiltrate taken once and declined
    # once; Gather Intelligence twice; no Maker Hooks; a 4/3 Spy use lag.
    # Seed 54 seat 2 (Chani): acquisition and Reveal-card sources, five
    # Conflict-reward gains; Maker Hooks in round 6; Infiltrate taken once
    # and declined once, Gather Intelligence once, at a 1/2 lag; one Spy left
    # on the board. The values below are the collectors' own on a scratch
    # replay (not recounted independently this time).
    # Re-derived 2026-10-10 for a triggered draw held as the owner's own step
    # (OQ-106, codec v142): seed 26 first diverges at round 4, seat 2's
    # Reveal, where the Tleilaxu track's Intrigue card its Subject X-137
    # purchase reached is now its own step; seat 1 no longer has an Intrigue
    # source, so it no longer fills the first role (the previous commit's
    # engine gives the values pinned before). Full seeds 1-600 give seed 209
    # (seat 0) alone in the first role and seeds 54 (seat 2), 248 (seat 2),
    # 478 (seat 1) and 515 (seat 1) in the second; seed 54 seat 2 keeps its
    # role with every column unchanged. Seed 209 seat 0 (Kota Odax of Ix):
    # Tech, Intrigue, Agent-card (twice) and Conflict-reward sources, one
    # loss; a trashed Spy and one other recall; two of three Infiltrates
    # taken; Gather Intelligence twice; no Maker Hooks; a 7/4 Spy use lag;
    # one Spy left on the board. The values below are the collectors' own on
    # a scratch replay (not recounted independently).
    # Re-derived 2026-10-10 for Muad'Dib's Reveal Intrigue card as a pending
    # Reveal gain (OQ-106, OQ-045): seed 209 first diverges at round 7, seat
    # 2's Reveal, where Unpredictable Foe's card is now its own step; seat 0
    # no longer has an Intrigue source, so it no longer fills the first role
    # (the previous commit's engine gives the values pinned before). No seat
    # of full seeds 1-600 fills it now; seeds 601-1200 give seeds 788 (seat
    # 1) and 859 (seat 0), and the second role stays seed 54 seat 2 (every
    # column unchanged; 248, 478, 515 and nine seats of 601-1200 follow).
    # Seed 788 seat 1 (Feyd-Rautha Harkonnen): Tech, Intrigue (twice),
    # Agent-card and Conflict-reward (twice) sources, one loss; Maker Hooks
    # in round 3; a trashed Spy and five other recalls; one of three
    # Infiltrates taken; Gather Intelligence twice at a 2/3 lag; no Spy left
    # on the board. The values below are the collectors' own on a scratch
    # replay (not recounted independently).
    # Re-derived 2026-10-12 for both grafted Agent boxes offered from the
    # start (codec v143, docs/graft-boxes-plan.md: no ``switch_graft_card``,
    # box 1's rows tagged ``box=1``): seed 788 first diverges at round 4,
    # seat 1's grafted Agent turn at Hagga Basin, and seed 54 at round 3,
    # seat 1's grafted Agent turn (the switch is gone from both legal
    # lists); seat 1 of 788 no longer trashes a Spy or declines an
    # Infiltrate and seat 2 of 54 no longer has an acquisition or
    # Reveal-card source, so neither fills its role (the previous commit's
    # engine gives the values pinned before). Full seeds 1-1200 give seeds
    # 268 (seat 2), 334 (seat 0) and 974 (seat 0) in the first role and
    # seed 37 seat 0 first of eleven in the second (74, 358, 478, 481, ...);
    # the pins are the first of each. Seed 268 seat 2 (Gurney Halleck):
    # Tech (twice), Intrigue (twice), Agent-card and Conflict-reward (twice)
    # sources, one loss; a trashed Spy and five other recalls; one of two
    # Infiltrates taken; Gather Intelligence five times at a 7/6 lag; no
    # Fremen 2, no Maker Hooks; two Spies left on the board. Seed 37 seat 0
    # (Lady Amber Metulli): acquisition, Reveal-card (twice) and Tech
    # sources; Maker Hooks in round 9; one of four Infiltrates taken and
    # Gather Intelligence three times at a 3/4 lag; six other recalls; two
    # Spies left on the board. The values below are the collectors' own on a
    # scratch replay (not recounted independently).
    # Re-derived 2026-10-14 -- v146: optional Agent-turn effects offer no
    # refusal (OQ-095 (2), 2026-10-14): seed 268 first diverges at round 1,
    # seat 3's Dutiful Service visit (no ``decline_sardaukar_commander``),
    # and seed 37 at round 1, seat 3's Assembly Hall visit (no
    # ``decline_sardaukar_commander`` or ``decline_tech``); seed 268 seat 2
    # no longer has an Agent-card or Conflict-reward source or a declined
    # Infiltrate, and seed 37 seat 0 no acquisition source or Infiltrate
    # offer, so neither fills its role (the previous commit's engine gives
    # the values pinned before). Full seeds 1-1200 (543-600 left out: seed
    # 543 stops on a Signet Spy placement with no legal action, an engine
    # defect reported separately) give seeds 295 (seat 2), 441, 824, 849,
    # 953 and 1125 in the first role and seeds 24 (seat 3), 90, 400, 412,
    # 651, 663, 744 and 1041 in the second; the pins are the first of each.
    # Seed 295 seat 2 (Count Hasimir Fenring): Tech (Navigation Chamber's
    # acquire icon), Intrigue (Withdrawal Agreement, Imperium Politics),
    # Agent-card (Experimentation's research step and Public Spectacle four
    # times), Reveal-gain (Shishakli) and four Conflict-reward gains; its
    # Fremkit Spy is trashed for Advanced Data Analysis, and Spy Drones'
    # placement and Public Spectacle's Reveal recall two more; three of four
    # Infiltrates taken; Gather Intelligence three times at a 3/2 lag;
    # Fremen 2 in round 4, Maker Hooks in round 6; two Spies left on the
    # board. Seed 24 seat 3 (Lady Amber Metulli): Imperial Throneship's
    # acquisition bonus is the acquisition source and Pointing the Way's
    # Reveal the Reveal-card source; Maker Hooks in round 7; five of six
    # Infiltrates taken and Gather Intelligence twice at a fractional 12/7
    # lag; five other recalls; three Spies left on the board. An independent
    # replay (no collector imports) recounted both seats' Influence events
    # by source; the Spy and Reveal columns are the collectors' own.
    # Re-derived 2026-10-14 -- v147: personal-card Reveal choices are rows
    # on the Reveal frame beside the purchases (OQ-095 (7) addition: no
    # defer/resume, no refusal; the heuristic still takes the choices it
    # would take before anything else): seed 295 first diverges at round 4,
    # seat 2's Reveal, whose Contract spice keep is now such a row, and
    # seed 24 at round 3, seat 3's Reveal, whose Spy placement is; seed 295
    # seat 2 no longer has a Conflict-reward source and seed 24 seat 3 no
    # Reveal-card source, so neither fills its role (the previous commit's
    # engine gives the values pinned before). Full seeds 1-559 give seeds
    # 201 (seat 1) and 441 (seat 3) in the first role and seeds 36 (seat 1),
    # 90 (seat 2), 400 (seat 3) and 412 (seat 1) in the second; the pins
    # are the first of each. None of the four seats in the second role both
    # uses Gather Intelligence and recalls a Spy otherwise (36 and 400
    # neither, 90 only recalls, 412 only gathers), so the 2026-10-06
    # pass-over (seed 12) has no candidate in 1-559: seed 36 seat 1 pins
    # those two columns at zero, and seed 201 seat 1 pins both non-zero.
    # Seed 201 seat 1 (Count Hasimir Fenring): Tech (Panopticon's Endgame
    # Emperor gain), Intrigue (Change Allegiances, also its one loss),
    # Agent-card (Guild Impersonator) and one Conflict-reward gain; a
    # trashed Spy and four other recalls; two of three Infiltrates taken;
    # Gather Intelligence three times at a 6/5 lag; Fremen 2 in round 6,
    # Maker Hooks in round 10; two Spies left on the board. Seed 36 seat 1
    # (Gurney Halleck): Imperial Throneship's acquisition bonus is the
    # acquisition source and Pointing the Way's Reveal the Reveal-card
    # source, beside Intrigue (Tenuous Bond, also its one loss), Agent-card
    # (Dangerous Rhetoric) and four Conflict-reward gains; Fremen 2 in round
    # 8, Maker Hooks in round 9; four of five Infiltrates taken at a
    # fractional 3/4 lag, no Gather Intelligence and no other recall; two
    # Spies left on the board. An independent replay (no collector imports)
    # recounted both seats' Influence events by source; the Spy and Reveal
    # columns are the collectors' own.
    # Re-derived 2026-10-18 for cleanup-2b (codec v149: in-turn research
    # bonuses and optional trashes as turn rows, a research space's two
    # icons as their own steps in the owner's order, no Influence offered at
    # the top for Shipping and Tech acquire): seed 201 first diverges at
    # round 8, seat 3's Scientific Breakthrough research step (c7r3, step 669
    # of the game), whose Intrigue trash for the research bonus is now
    # followed by the owed card as its own ``draw_owed_intrigue`` /
    # ``draw_owed_card`` rows instead of drawing at once (step 670 no longer
    # offers ``finish_agent_turn``); seed 36 at round 5, seat 3's
    # Experimentation research step (c3r5, step 331), whose two icons are now
    # two ``resolve_research_icon`` rows (step 332 no longer offers
    # ``draw_owed_intrigue``). Seed 201 seat 1 keeps its Influence sources,
    # gains, loss and Fremen 2 round but trashes no Spy, holds no Maker
    # Hooks and has three Spies left on the board, and seed 36 seat 1 has no
    # Reveal-card source, Fremen 2 or Maker Hooks, so neither fills its role
    # any more (on a ``git archive`` export of the previous commit, a1b692f0,
    # the independent replay below recounts every column pinned before).
    # Full seeds 1-200 now give seed 51 seat 2 alone in the first role (the
    # same in seeds 1-559; seeds 980 and 1144 follow in 1-1200) and seeds
    # 112 (seat 0) and 162 (seat 2) in the second (335 follows in 1-559); on
    # the previous commit's engine the same scan gives seeds 201 (seat 1)
    # and 441 (seat 3) and seeds 36 (seat 1) and 412 (seat 1) over seeds
    # 1-559. The pins are the first of each. Seed 112 seat 0 also passes the
    # 2026-10-06 pass-over (it uses Gather Intelligence, recalls a Spy
    # otherwise and declines an Infiltrate), so its Gather Intelligence and
    # other-recall columns are non-zero, which seed 36's were not. Seed 51
    # seat 2 (Muad'Dib): Tech (Panopticon's Endgame Spacing Guild gain),
    # Intrigue (Sietch Ritual, Imperium Politics), Agent-card (Guild
    # Impersonator) and four Conflict-reward gains (two Distinct Influence
    # rewards), two losses (Backed by CHOAM, Questionable Methods); its Spy
    # is trashed for Advanced Data Analysis (a High Council buy in round 9)
    # and five are recalled otherwise (Insider Information, Spy Network
    # twice, Panopticon's placement and an Emperor track bonus placement);
    # one of three Infiltrates taken (round 10, two declined before it);
    # Gather Intelligence four times (rounds 2, 3, 8, 10) and Infiltrate
    # once at a 6/5 lag; Fremen 2 in round 7, Maker Hooks in round 8; one
    # Spy left on the board. Seed 112 seat 0 (Steersman Y'rkoon): Imperial
    # Throneship's acquisition bonus is the acquisition source and Pointing the
    # Way's Reveal the Reveal-card source, beside a Navigation gain (a round-5
    # Bene Gesserit visit; its slot 0 loss is one of the eight losses, the
    # others Forbidden Weapons' Reveal), two Tech gains (Navigation Chamber's
    # and Glowglobes' acquire icons) and eight visits; Fremen 2 and Maker Hooks
    # both in round 8; Gather Intelligence in rounds 9 and 10 and an Infiltrate
    # in round 10 (one of two taken) at a fractional 7/3 lag; two other recalls
    # (Arrakeen II's Contract and a Navigation card); two Spies left on the
    # board. An independent replay (no collector imports) recounted every
    # column below from the games' own events, decision action sets and the
    # state after each step, and matched the collectors exactly.
    game = tip_census.play(_spec(True, 51), ("influence",))
    seat = game["seats"][2]
    assert seat["infl.sources"] == {
        "visit:starter": 5,
        "visit:bought": 5,
        "intrigue": 2,
        "combat_reward": 4,
        "agent_card": 1,
        "tech": 1,
    }
    assert seat["infl.gained"] == 18
    assert seat["infl.lost"] == 2
    assert seat["infl.fremen2_round"] == 7
    assert seat["infl.hooks_round"] == 8
    assert seat["lands.reveal_cards"] == pytest.approx(3.4)
    assert seat["lands.reveal_persuasion"] == pytest.approx(6.9)
    assert seat["spy.placed"] == 12
    assert seat["spy.used_gather"] == 4
    assert seat["spy.recalled_other"] == 5
    assert seat["spy.trashed"] == 1
    assert seat["spy.on_board_end"] == 1
    assert seat["spy.use_lag"] == pytest.approx(6 / 5)
    assert seat["spy.infiltrate_offered"] == 3
    assert seat["spy.infiltrate_taken"] == 1

    game = tip_census.play(_spec(True, 112), ("influence",))
    seat = game["seats"][0]
    assert seat["infl.sources"] == {
        "visit:starter": 4,
        "visit:bought": 4,
        "leader": 1,
        "reveal_card": 1,
        "acquisition": 1,
        "tech": 2,
    }
    assert seat["infl.gained"] == 13
    assert seat["infl.lost"] == 8
    assert seat["infl.fremen2_round"] == 8
    assert seat["infl.hooks_round"] == 8
    assert seat["lands.reveal_cards"] == pytest.approx(3.4)
    assert seat["lands.reveal_persuasion"] == pytest.approx(5.9)
    assert seat["spy.placed"] == 7
    assert seat["spy.used_gather"] == 2
    assert seat["spy.recalled_other"] == 2
    assert seat["spy.on_board_end"] == 2
    assert seat["spy.use_lag"] == pytest.approx(7 / 3)
    assert seat["spy.infiltrate_offered"] == 2
    assert seat["spy.infiltrate_taken"] == 1


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
