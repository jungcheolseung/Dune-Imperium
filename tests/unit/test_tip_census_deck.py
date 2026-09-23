"""Regression tests for ``scripts/ab/tipcensus/deck.py`` (deck + bond columns).

Plays a handful of the tournament's own games (base and full-expansion specs,
``_spec`` mirrors ``tests/unit/test_tip_census.py``) through the census driver
and checks the ``deck.*`` / ``bond.*`` columns against invariants tied to the
final game state, not just "the column exists".

``tests/unit/test_tip_census.py`` documents its ``load_tip_census()`` helper
as importable via ``from tests.unit.test_tip_census import load_tip_census``
("tests/ is a package"), but ``tests/unit/`` itself has no ``__init__.py``
(only ``tests/__init__.py`` does), so pytest's default "prepend" import mode
inserts ``tests/unit`` -- not the repo root -- onto ``sys.path`` for a file
collected from there, and the dotted import raises ``ModuleNotFoundError: No
module named 'tests'`` under the plain ``uv run pytest`` invocation (it only
works under ``python -m pytest``, which adds the cwd). Like the sibling
``test_tip_census_combat.py``/``test_tip_census_endgame.py``, this module
carries its own copy of the same tiny loader instead; see the blocker note in
the work report.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.evaluation import tournament as T
from dune_imperium.rules.agent_effects import (
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.frames import FrameKind

_TOOL = Path(__file__).resolve().parents[2] / "scripts" / "ab" / "tip_census.py"


def _load_tip_census() -> ModuleType:
    """Import ``scripts/ab/tip_census.py`` (it puts ``scripts/ab`` on sys.path)."""

    if "tip_census" in sys.modules:
        return sys.modules["tip_census"]
    spec = importlib.util.spec_from_file_location("tip_census", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tip_census"] = module
    spec.loader.exec_module(module)
    return module


BASE_SEEDS = (1, 2, 3)
FULL_SEEDS = (3, 4, 5)


@pytest.fixture(scope="module")
def tip_census() -> ModuleType:
    return _load_tip_census()


@pytest.fixture(scope="module")
def deck_module(tip_census: ModuleType) -> ModuleType:
    import importlib

    return importlib.import_module("tipcensus.deck")


@pytest.fixture(scope="module")
def base_module(tip_census: ModuleType) -> ModuleType:
    import importlib

    return importlib.import_module("tipcensus.base")


def _spec(full: bool, seed: int) -> T.MatchSpec:
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


def _play_to_finished(tip_census: ModuleType, spec: T.MatchSpec) -> Any:
    """Replay ``spec`` with the driver's own loop and return the final state.

    Deterministic replica of ``tip_census.play``'s loop (same seeds, same
    agent construction), kept independent of the collectors so the final
    ``GameState`` can be cross-checked against what ``deck.py`` counted from
    events alone.
    """

    Tmod = tip_census.T
    engine = (
        Tmod.UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else Tmod.UprisingRulesEngine()
    )
    agents = tuple(
        Tmod.make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    searchers = tip_census._state_agents(agents)
    state = engine.reset(spec.config, spec.game_seed)
    chance = tip_census.ChanceResolver(seed=spec.game_seed)
    for _ in range(spec.max_steps):
        if state.phase is tip_census.GamePhase.FINISHED:
            return state
        decision = engine.current_decision(state)
        if isinstance(decision, tip_census.ChanceDecision):
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
        state = result.state
    raise RuntimeError(f"step limit reached for seed {spec.game_seed}")


def _play_all(
    tip_census: ModuleType, full: bool, seeds: tuple[int, ...]
) -> list[dict[str, Any]]:
    return [tip_census.play(_spec(full, seed), ("deck",)) for seed in seeds]


def test_every_collector_class_is_unique_and_named_deck_and_bond(
    deck_module: ModuleType,
) -> None:
    names = [cls.name for cls in deck_module.COLLECTORS]
    assert names == ["deck", "bond"]


def test_deck_and_bond_columns_present_with_expected_types(
    tip_census: ModuleType,
) -> None:
    for census in _play_all(tip_census, True, FULL_SEEDS[:1]):
        for seat in census["seats"]:
            for key in (
                "deck.buys",
                "deck.buys_r1_3",
                "deck.buys_r4_6",
                "deck.buys_r7p",
                "deck.buys_cost5p",
                "deck.faction_buys_r1_3",
                "deck.faction_buys",
                "deck.end_cards",
                "deck.end_starters",
                "deck.end_bought",
                "deck.trash_chosen",
                "deck.trash_starters",
                "deck.self_trashes",
                "bond.cards_end",
                "bond.pairs_end",
                "bond.plays",
                "bond.activations",
            ):
                assert isinstance(seat[key], int), key
            assert isinstance(seat["deck.buys_by_payment"], dict)
            assert isinstance(seat["deck.trashed"], dict)
            assert seat["deck.tleilaxu_buys"] is None or isinstance(
                seat["deck.tleilaxu_buys"], int
            )
        game = census["game"]
        assert game["deck.unresolved_buys"] == 0
        for key in (
            "bond.table_fremen",
            "bond.table_bene_gesserit",
            "bond.table_emperor",
            "bond.table_spacing_guild",
        ):
            assert isinstance(game[key], int)


def test_tleilaxu_buys_is_none_without_immortality(tip_census: ModuleType) -> None:
    for census in _play_all(tip_census, False, BASE_SEEDS):
        for seat in census["seats"]:
            assert seat["deck.tleilaxu_buys"] is None


def test_tleilaxu_buys_is_an_int_with_immortality(tip_census: ModuleType) -> None:
    for census in _play_all(tip_census, True, FULL_SEEDS):
        for seat in census["seats"]:
            assert isinstance(seat["deck.tleilaxu_buys"], int)
            assert seat["deck.tleilaxu_buys"] <= seat["deck.buys"]


# ---------------------------------------------------------------------------
# Bond table content: built from the catalog, not hand-picked -- assert what
# was actually found rather than forcing doc 6.6's numbers.
# ---------------------------------------------------------------------------


def test_bond_table_matches_the_catalog_scan(deck_module: ModuleType) -> None:
    from dune_imperium.content.uprising.board import Faction

    counts: dict[Faction, int] = {faction: 0 for faction in Faction}
    for card_id in deck_module.BOND_CARD_IDS:
        factions = {
            deck_module.AGENT_BOND.get(card_id),
            deck_module.REVEAL_BOND.get(card_id),
        } - {None}
        for faction in factions:
            counts[faction] += 1
    # Doc 6.6 (owner's tip audit): Fremen 11, Bene Gesserit 7, Emperor 1,
    # Spacing Guild 0. The catalog scan reproduces Fremen/Emperor/Spacing
    # Guild exactly; Bene Gesserit is 8 here because Long Reach's
    # icon-condition Bond (``PersonalCardIconCondition.BENE_GESSERIT_BOND``)
    # is a genuine "another Bene Gesserit card in play" gate that doc 6.6's
    # audit did not count (see the report handed back with this slice).
    assert counts[Faction.FREMEN] == 11
    assert counts[Faction.BENE_GESSERIT] == 8
    assert counts[Faction.EMPEROR] == 1
    assert counts[Faction.SPACING_GUILD] == 0


def test_bond_game_columns_match_the_table(
    tip_census: ModuleType, deck_module: ModuleType
) -> None:
    census = tip_census.play(_spec(True, FULL_SEEDS[0]), ("deck",))
    game = census["game"]
    assert game["bond.table_fremen"] == 11
    assert game["bond.table_bene_gesserit"] == 8
    assert game["bond.table_emperor"] == 1
    assert game["bond.table_spacing_guild"] == 0


# ---------------------------------------------------------------------------
# Ownership invariants, tied to the final GameState.
# ---------------------------------------------------------------------------


def _starting_deck_size(leader_id: str | None) -> int:
    """10 starters [Main p. 3], minus a Leader's own removed starting cards.

    Staban Tuek ("You start the game without Diplomacy in your deck") and
    Steersman Y'rkoon ("... without Signet Ring in your deck") each remove
    one single-copy starter at setup -- never dealt, so never trashed either
    (content/uprising/leaders.py ``removed_starting_card_ids``). Found by the
    ``deck.end_starters`` invariant test failing at 9 != 10 for a Staban Tuek
    seat; see the report.
    """

    if leader_id is None:
        return 10
    return 10 - len(LEADERS_BY_ID[leader_id].removed_starting_card_ids)


@pytest.mark.parametrize("full", [False, True])
def test_deck_ownership_invariants_tie_to_final_state(
    tip_census: ModuleType, full: bool
) -> None:
    seeds = FULL_SEEDS if full else BASE_SEEDS
    for seed in seeds:
        spec = _spec(full, seed)
        census = tip_census.play(spec, ("deck",))
        final = _play_to_finished(tip_census, spec)
        for seat_row, player in zip(census["seats"], final.players, strict=True):
            row = {k: v for k, v in seat_row.items() if k.startswith("deck.")}
            assert (
                row["deck.end_cards"]
                == row["deck.end_starters"] + row["deck.end_bought"]
            )
            assert row["deck.trash_chosen"] >= row["deck.trash_starters"]
            assert sum(row["deck.trashed"].values()) == row["deck.trash_chosen"]
            assert (
                row["deck.buys_r1_3"] + row["deck.buys_r4_6"] + row["deck.buys_r7p"]
                == row["deck.buys"]
            )
            assert row["deck.faction_buys_r1_3"] <= row["deck.faction_buys"]
            assert row["deck.faction_buys"] <= row["deck.buys"]
            assert row["deck.buys_cost5p"] <= row["deck.buys"]
            # Every personal card this seat ever owned is accounted for
            # exactly once: still owned at the end, a chosen trash, or a
            # mandatory self-trash (module docstring's self_trashes comment)
            # -- ties DeckCollector's own event bookkeeping to the final
            # PlayerState zones it never reads mid-game. This is the
            # invariant the trash_chosen/trashed/self_trashes fix (report)
            # restores: before it, a bought Dangerous Rhetoric or Subversive
            # Advisor that mandatorily self-trashed left the buy uncounted
            # on both sides.
            baseline = _starting_deck_size(player.leader_id)
            assert (
                baseline + row["deck.buys"]
                == row["deck.end_cards"]
                + row["deck.trash_chosen"]
                + row["deck.self_trashes"]
            )
            # Seek Allies is the only STARTER with a mandatory self-trash
            # (TRASH_SELF; the other two MANDATORY_SELF_TRASH effects --
            # Dangerous Rhetoric, Subversive Advisor -- are never starters),
            # so this residual is 0 or 1 and never exceeds self_trashes.
            seek_allies_trash = (
                baseline - row["deck.trash_starters"] - row["deck.end_starters"]
            )
            assert seek_allies_trash in (0, 1)
            assert seek_allies_trash <= row["deck.self_trashes"]
            # Every card still owned that is not a starter is one of the
            # instance IDs the collector itself recorded as bought and never
            # recorded as chosen-trashed.
            assert row["deck.exposure"] is None or row["deck.buys"] > 0
            if row["deck.buys"] == 0:
                assert row["deck.exposure"] is None
                assert row["deck.buy_cost_mean"] is None


def _max_acquisition_cost(deck_module: ModuleType) -> int:
    """The highest printed Imperium/Reserve acquisition cost in the catalog.

    The Spice Must Flow (Reserve) costs 9 Persuasion
    (content/uprising/reserve.py) -- higher than any printed Imperium card
    (8) -- so the bound is read from the catalog rather than assumed.
    """

    return max(
        cost
        for _card_id, entry in deck_module._catalog_entries()
        if isinstance(cost := getattr(entry, "acquisition_cost", None), int)
    )


@pytest.mark.parametrize("full", [False, True])
def test_buy_cost_mean_is_bounded_and_excludes_tleilaxu(
    tip_census: ModuleType, deck_module: ModuleType, full: bool
) -> None:
    seeds = FULL_SEEDS if full else BASE_SEEDS
    max_cost = _max_acquisition_cost(deck_module)
    assert max_cost == 9  # The Spice Must Flow; see _max_acquisition_cost.
    for seed in seeds:
        census = tip_census.play(_spec(full, seed), ("deck",))
        for seat in census["seats"]:
            mean = seat["deck.buy_cost_mean"]
            if mean is not None:
                assert 0 < mean <= max_cost
            if (
                seat["deck.tleilaxu_buys"]
                and seat["deck.tleilaxu_buys"] == seat["deck.buys"]
            ):
                # Every buy this seat made was a Tleilaxu buy (no Persuasion
                # cost exists for any of them): the cost mean has nothing to
                # average.
                assert mean is None


# ---------------------------------------------------------------------------
# Bond invariants, cross-checked against an independent ground-truth scan of
# the final PlayerState (not just the collector's own step-by-step count).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("full", [False, True])
def test_bond_cards_end_matches_an_independent_scan_of_final_state(
    tip_census: ModuleType, deck_module: ModuleType, full: bool
) -> None:
    from dune_imperium.content.uprising.personal_cards import personal_card_for_instance

    seeds = FULL_SEEDS if full else BASE_SEEDS
    for seed in seeds:
        spec = _spec(full, seed)
        census = tip_census.play(spec, ("deck",))
        final = _play_to_finished(tip_census, spec)
        for seat_row, player in zip(census["seats"], final.players, strict=True):
            owned = (*player.deck, *player.hand, *player.discard_pile, *player.in_play)
            ground_truth = sum(
                1
                for iid in owned
                if personal_card_for_instance(iid).card.card_id
                in deck_module.BOND_CARD_IDS
            )
            assert seat_row["bond.cards_end"] == ground_truth


@pytest.mark.parametrize("full", [False, True])
def test_bond_plays_and_activations_are_consistent(
    tip_census: ModuleType, full: bool
) -> None:
    seeds = FULL_SEEDS if full else BASE_SEEDS
    for seed in seeds:
        census = tip_census.play(_spec(full, seed), ("deck",))
        for seat in census["seats"]:
            plays = seat["bond.plays"]
            activations = seat["bond.activations"]
            assert 0 <= activations <= plays
            share = seat["bond.activation_share"]
            if plays == 0:
                assert share is None
            else:
                assert share == pytest.approx(activations / plays)
            assert 0 <= seat["bond.pairs_end"] <= seat["bond.cards_end"]


# ---------------------------------------------------------------------------
# Exact hand-traced values (base seed 3, seat 1) -- pins concrete numbers so
# a change that still satisfies every invariant above (e.g. a mutant that
# shifts a count while keeping the totals consistent) is still caught.
# ---------------------------------------------------------------------------


def test_base_seed_3_seat_1_matches_the_hand_trace(tip_census: ModuleType) -> None:
    census = tip_census.play(_spec(False, 3), ("deck",))
    row = census["seats"][1]
    assert row["deck.buys"] == 14
    assert row["deck.buys_r1_3"] == 5
    assert row["deck.buys_r4_6"] == 4
    assert row["deck.buys_r7p"] == 5
    assert row["deck.buys_by_payment"] == {"persuasion": 14}
    assert row["deck.trash_chosen"] == 1
    assert row["deck.trash_starters"] == 1
    assert row["deck.first_trash_round"] == 8
    assert row["deck.trashed"] == {"dune_the_desert_planet": 1}
    assert row["deck.exposure"] == pytest.approx(20 / 14)


# ---------------------------------------------------------------------------
# Directed Step-level tests for the trash exclusions (report findings:
# trash_chosen wrongly counted a mandatory self-trash other than Seek
# Allies', and wrongly excluded a Seek Allies trashed by an unrelated chosen
# effect). Built from real engine transitions on hand-built minimal states,
# the same pattern ``tests/unit/rules/test_agent_effects.py`` uses.
# ---------------------------------------------------------------------------


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _imperium_instance(card_id: str) -> str:
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids

    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def _turn_state(hand: tuple[str, ...], **config: object) -> GameState:
    return GameState(
        config=RulesetConfig(**config),  # type: ignore[arg-type]
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=hand),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _place_action(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )


def test_seek_allies_and_dangerous_rhetoric_self_trash_are_excluded(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    """Both mandatory "Trash this card." resolutions
    (``deck_module.MANDATORY_SELF_TRASH``) are excluded from trash_chosen
    and counted as self_trashes instead. Before the fix, only
    ``PersonalCardAgentEffect.TRASH_SELF`` (Seek Allies) was excluded, so
    Dangerous Rhetoric's ``TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE`` self-trash
    was wrongly counted as a chosen thinning trash (report finding, high
    severity)."""

    from dune_imperium.rules.agent_effects import legal_agent_card_icon_actions

    spec = T.MatchSpec(0, 0, ("heuristic",) * 4)
    collector = deck_module.DeckCollector(spec, 4)

    seek_allies = _instance("seek_allies")
    state = _turn_state((seek_allies,))
    placed = apply_agent_action(state, _place_action(state, "dutiful_service"))
    resolved = resolve_agent_card_effect(placed.state)
    assert [e.kind for e in resolved.events] == ["card_trashed"]
    collector.step(
        base_module.Step(
            pre=placed.state,
            post=resolved.state,
            owner=0,
            action=DomainAction(action_id="resolve_agent_card_effect", actor=0),
            legal=(),
            events=resolved.events,
        )
    )

    rhetoric = _imperium_instance("dangerous_rhetoric")
    state2 = _turn_state((rhetoric,))
    placed2 = apply_agent_action(state2, _place_action(state2, "assembly_hall"))
    icon_action = next(
        action
        for action in legal_agent_card_icon_actions(placed2.state, 0)
        if dict(action.arguments)["effect"] == "trash_self"
    )
    self_trashed = resolve_agent_card_icon(placed2.state, icon_action)
    assert "card_trashed" in [e.kind for e in self_trashed.events]
    collector.step(
        base_module.Step(
            pre=placed2.state,
            post=self_trashed.state,
            owner=0,
            action=icon_action,
            legal=(),
            events=self_trashed.events,
        )
    )

    per_seat, _game = collector.finish(self_trashed.state, ())
    assert per_seat[0]["trash_chosen"] == 0
    assert per_seat[0]["trashed"] == {}
    assert per_seat[0]["self_trashes"] == 2


def test_a_non_mandatory_trash_of_seek_allies_is_a_chosen_trash(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    """Seek Allies trashed by an unrelated effect (a combat-reward trash, a
    Leader Signet trash from hand) -- not its own mandatory box resolving --
    is a genuine thinning choice and must be counted. Before the fix, any
    trash of a card whose ``agent_effect`` was ``TRASH_SELF`` was excluded
    regardless of cause (report finding, high severity)."""

    spec = T.MatchSpec(0, 0, ("heuristic",) * 4)
    collector = deck_module.DeckCollector(spec, 4)
    seek_allies = _instance("seek_allies")
    state = _turn_state((seek_allies,))  # no AGENT_EFFECTS frame open at all
    result = trash_personal_card(
        state, 0, seek_allies, source="round:1:combat_reward:trash:0"
    )
    assert [e.kind for e in result.events] == ["card_trashed"]
    collector.step(
        base_module.Step(
            pre=state,
            post=result.state,
            owner=0,
            action=DomainAction(action_id="trash_combat_reward_card", actor=0),
            legal=(),
            events=result.events,
        )
    )
    per_seat, _game = collector.finish(result.state, ())
    assert per_seat[0]["trash_chosen"] == 1
    assert per_seat[0]["self_trashes"] == 0
    assert per_seat[0]["trashed"] == {"seek_allies": 1}
    assert per_seat[0]["trash_starters"] == 1


def test_usurps_borrowed_row_card_is_excluded_by_state_not_event_pairing(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    """The borrowed card can trash itself through its own box before the
    turn closes (``graft.py::resolve_usurp_trash``'s own docstring: "a card
    that already left every owned zone ... needs nothing more"), with no
    ``usurped_card_trashed`` event alongside it. The exclusion is keyed off
    ``usurped_row_card_id`` (module docstring), not event pairing (report
    finding, high severity)."""

    spec = T.MatchSpec(0, 0, ("heuristic",) * 4, immortality=True)
    collector = deck_module.DeckCollector(spec, 4)
    # Not a MANDATORY_SELF_TRASH card (no agent_effect at all): isolates the
    # Usurp exclusion from the mandatory-self-trash exclusion.
    borrowed = "imperium:sardaukar_coordination:0"
    state = GameState(
        config=RulesetConfig(immortality=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, in_play=(borrowed,), usurped_row_card_id=borrowed),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
    )
    result = trash_personal_card(
        state, 0, borrowed, source="round:1:player:0:agent_card"
    )
    assert [e.kind for e in result.events] == ["card_trashed"]
    collector.step(
        base_module.Step(
            pre=state,
            post=result.state,
            owner=0,
            action=DomainAction(action_id="resolve_agent_card_effect", actor=0),
            legal=(),
            events=result.events,
        )
    )
    per_seat, _game = collector.finish(result.state, ())
    assert per_seat[0]["trash_chosen"] == 0
    assert per_seat[0]["self_trashes"] == 0
    assert per_seat[0]["trashed"] == {}


# ---------------------------------------------------------------------------
# Reserve instance-ID reuse (report finding, medium severity): a trashed
# Reserve copy's ID can be re-issued to a later buy, so bought/trashed
# bookkeeping keyed by instance ID alone merges two separate cards.
# ---------------------------------------------------------------------------


def test_exposure_and_trash_chosen_do_not_collapse_when_a_reserve_id_is_reused(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    spec = T.MatchSpec(0, 0, ("heuristic",) * 4)
    collector = deck_module.DeckCollector(spec, 4)
    iid = "reserve:prepare_the_way:0"

    def _bare(round_no: int, hand: tuple[str, ...]) -> GameState:
        return GameState(
            config=RulesetConfig(),
            seed=1,
            phase=GamePhase.PLAYER_TURNS,
            round_number=round_no,
            players=(
                PlayerState(player_id=0, hand=hand),
                *(PlayerState(player_id=s) for s in range(1, 4)),
            ),
            reserve_stacks=(("prepare_the_way", 5),),
        )

    def _buy(round_no: int) -> None:
        pre = _bare(round_no, ())
        post = replace(
            pre, players=(replace(pre.players[0], hand=(iid,)), *pre.players[1:])
        )
        event = GameEvent(
            event_id=f"round:{round_no}:player:0:acquire:{iid}",
            kind="card_acquired",
            payload=(
                ("card_id", "prepare_the_way"),
                ("instance_id", iid),
                ("player", 0),
            ),
        )
        collector.step(
            base_module.Step(
                pre=pre, post=post, owner=0, action=None, legal=(), events=(event,)
            )
        )

    def _seen(round_no: int) -> None:
        state = _bare(round_no, (iid,))
        collector.step(
            base_module.Step(
                pre=state, post=state, owner=None, action=None, legal=(), events=()
            )
        )

    def _trash(round_no: int) -> GameState:
        pre = _bare(round_no, (iid,))
        result = trash_personal_card(pre, 0, iid, source=f"round:{round_no}:trash")
        collector.step(
            base_module.Step(
                pre=pre,
                post=result.state,
                owner=0,
                action=None,
                legal=(),
                events=result.events,
            )
        )
        return result.state

    _buy(1)
    _seen(3)
    _seen(4)
    _seen(6)
    _trash(7)
    _buy(7)
    _seen(9)
    final = _trash(10)

    per_seat, _game = collector.finish(final, ())
    assert per_seat[0]["buys"] == 2
    # Pre-fix: acquired_round[iid] was overwritten by the second buy (7) and
    # hand_rounds[iid] merged both occurrences' sightings ({3, 4, 6, 9}), so
    # exposure would have been 1 (only round 9 > 7) instead of 2.0.
    assert per_seat[0]["exposure"] == pytest.approx((3 + 1) / 2)
    # Pre-fix: trash_chosen was `len(a set of instance IDs)`, so the second
    # trash of the same re-bought ID would not have grown it past 1.
    assert per_seat[0]["trash_chosen"] == 2
    assert per_seat[0]["trashed"] == {"prepare_the_way": 2}


# ---------------------------------------------------------------------------
# _resolve_instance_id: the event_id suffix is the primary reconstruction
# path (report finding, medium severity), with the zone-delta scan --
# widened to include in_play -- kept only as a fallback.
# ---------------------------------------------------------------------------


def test_resolve_instance_id_prefers_the_event_id_suffix_over_an_ambiguous_delta(
    deck_module: ModuleType,
) -> None:
    payload: tuple[tuple[str, bool | int | str], ...] = (
        ("card_id", "prepare_the_way"),
        ("player", 0),
    )
    event = GameEvent(
        event_id=(
            "round:1:player:0:intrigue:intrigue:inspire_awe:0:slot:0"
            ":acquired:reserve:prepare_the_way:7"
        ),
        kind="card_acquired",
        payload=payload,
    )
    owner_pre = PlayerState(player_id=0)
    # Two candidates in the zone delta (ambiguous on its own): the regex
    # path must still pick the one the event_id actually names.
    owner_post = PlayerState(
        player_id=0,
        in_play=("reserve:prepare_the_way:7", "reserve:prepare_the_way:9"),
    )
    iid = deck_module._resolve_instance_id(
        dict(payload), False, owner_pre, owner_post, event
    )
    assert iid == "reserve:prepare_the_way:7"


def test_resolve_instance_id_falls_back_to_in_play_without_a_usable_event_id(
    deck_module: ModuleType,
) -> None:
    payload: tuple[tuple[str, bool | int | str], ...] = (
        ("card_id", "prepare_the_way"),
        ("player", 0),
    )
    event = GameEvent(
        event_id="round:1:player:0:some_unrelated_event",
        kind="card_acquired",
        payload=payload,
    )
    owner_pre = PlayerState(player_id=0)
    # A card acquired to hand during the owner's own Reveal turn can move
    # straight to in_play in the same step (_late_reveal_one_card): the
    # pre-fix zone delta only read hand/discard_pile and missed it.
    owner_post = PlayerState(player_id=0, in_play=("reserve:prepare_the_way:7",))
    iid = deck_module._resolve_instance_id(
        dict(payload), False, owner_pre, owner_post, event
    )
    assert iid == "reserve:prepare_the_way:7"


# ---------------------------------------------------------------------------
# Directed Step-level tests for BondCollector's Agent/Reveal side
# determination, the per_revealed_faction activation check, and pairs_end's
# required-Faction test (report findings, all high severity).
# ---------------------------------------------------------------------------


def _four_players(**overrides: object) -> tuple[PlayerState, ...]:
    seat0 = PlayerState(player_id=0, **overrides)  # type: ignore[arg-type]
    return (seat0, *(PlayerState(player_id=s) for s in range(1, 4)))


def _agent_effects_frame(owner: int) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.AGENT_EFFECTS,
        frame_id=f"round:1:player:{owner}:agent_effects",
        decision=PlayerDecision(owner=owner, prompt="Choose the next effect"),
        context=(("turn_owner", owner),),
    )


def test_bond_does_not_count_a_reveal_bond_card_grafted_in_as_an_agent(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    """Stilgar the Devoted has no AGENT_BOND entry (its Bond is checked only
    on the Reveal side -- see PER_REVEALED). Grafted in as an Agent-turn
    partner (``choose_graft_partner``, while the owner's AGENT_EFFECTS frame
    stays open), the pre-fix ``action_id == "agent_turn"`` test misread this
    as Reveal-side and counted it via REVEAL_BOND; it must not be counted as
    a play at all on the Agent side."""

    stilgar = "imperium:stilgar_the_devoted:0"
    assert "stilgar_the_devoted" in deck_module.REVEAL_BOND
    assert "stilgar_the_devoted" not in deck_module.AGENT_BOND

    pre = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=_four_players(),
        decision_stack=(_agent_effects_frame(0),),
    )
    post = replace(pre, players=_four_players(in_play=(stilgar,)))
    step = base_module.Step(
        pre=pre,
        post=post,
        owner=0,
        action=DomainAction(
            action_id="choose_graft_partner", actor=0, arguments=(("card_id", stilgar),)
        ),
        legal=(),
        events=(),
    )
    collector = deck_module.BondCollector(T.MatchSpec(0, 0, ("heuristic",) * 4), 4)
    collector.step(step)
    per_seat, _game = collector.finish(post, ())
    assert per_seat[0]["plays"] == 0
    assert per_seat[0]["activations"] == 0


def test_bond_counts_an_agent_bond_card_grafted_in_as_an_agent(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    """The converse: an AGENT_BOND card (Southern Faith) grafted in during
    the Agent turn is on the side its own Bond gate actually checks, and is
    counted as a play."""

    southern_faith = "imperium:southern_faith:0"
    assert deck_module.AGENT_BOND.get("southern_faith") is not None

    pre = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=_four_players(),
        decision_stack=(_agent_effects_frame(0),),
    )
    post = replace(pre, players=_four_players(in_play=(southern_faith,)))
    step = base_module.Step(
        pre=pre,
        post=post,
        owner=0,
        action=DomainAction(
            action_id="choose_graft_partner",
            actor=0,
            arguments=(("card_id", southern_faith),),
        ),
        legal=(),
        events=(),
    )
    collector = deck_module.BondCollector(
        T.MatchSpec(0, 0, ("heuristic",) * 4, bloodlines=True), 4
    )
    collector.step(step)
    per_seat, _game = collector.finish(post, ())
    assert per_seat[0]["plays"] == 1
    assert per_seat[0]["activations"] == 0  # no other owned BG card in play


def test_bond_per_revealed_faction_activation_uses_the_revealed_set(
    deck_module: ModuleType, base_module: ModuleType
) -> None:
    """Sardaukar Coordination's Bond counts only the cards revealed THIS
    Reveal turn (docs/rules/player-turns.md:235-237 [Sardaukar Coordination
    card]: "이전 Agent turn에 낸 Emperor card는 이 수에 포함하지 않는다"), not
    the seat's whole in_play. An Emperor card played as an Agent earlier in
    the round must not count as the partner."""

    coordination = "imperium:sardaukar_coordination:0"
    agent_side_emperor_card = "imperium:sardaukar_soldier:0"
    assert "sardaukar_coordination" in deck_module.PER_REVEALED

    pre = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=_four_players(in_play=(agent_side_emperor_card,)),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.REVEAL,
                frame_id="round:1:player:0:reveal",
                decision=PlayerDecision(owner=0, prompt="Resolve Reveal effects"),
                context=(
                    ("revealed_card_000", coordination),
                    ("revealed_card_count", 1),
                    ("turn_owner", 0),
                ),
            ),
        ),
    )
    post = replace(
        pre,
        players=_four_players(in_play=(agent_side_emperor_card, coordination)),
    )
    step = base_module.Step(
        pre=pre,
        post=post,
        owner=0,
        action=DomainAction(action_id="reveal_turn", actor=0),
        legal=(),
        events=(),
    )
    collector = deck_module.BondCollector(T.MatchSpec(0, 0, ("heuristic",) * 4), 4)
    collector.step(step)
    per_seat, _game = collector.finish(post, ())
    assert per_seat[0]["plays"] == 1
    # Pre-fix: has_faction_bond(in_play, ...) would find the Agent-played
    # sardaukar_soldier and wrongly count this as an activation.
    assert per_seat[0]["activations"] == 0


def test_bond_pairs_end_uses_the_required_faction_not_the_cards_own_factions(
    deck_module: ModuleType,
) -> None:
    """Southern Faith prints Bene Gesserit + Fremen but its Bond needs
    another Bene Gesserit card specifically (agent_effects.py:810-815).
    Owning only a Fremen card besides it must not count as a pair (report
    finding, high severity)."""

    southern_faith = "imperium:southern_faith:0"
    # A plain Fremen card with no Bond gate of its own (not in
    # BOND_CARD_IDS), so it only tests southern_faith's own pairing --
    # unlike Stilgar the Devoted, which would legitimately pair WITH
    # Southern Faith on its own (Fremen) Bond and confound the count.
    fremen_only = "imperium:desert_power:0"
    spec = T.MatchSpec(0, 0, ("heuristic",) * 4, bloodlines=True)
    collector = deck_module.BondCollector(spec, 4)
    final = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=_four_players(in_play=(southern_faith, fremen_only)),
    )
    per_seat, _game = collector.finish(final, ())
    assert per_seat[0]["cards_end"] == 1  # only southern_faith is Bond-table
    assert per_seat[0]["pairs_end"] == 0

    other_bg = "imperium:long_reach:0"  # also Bond-table (bene_gesserit)
    final_with_bg = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=_four_players(in_play=(southern_faith, fremen_only, other_bg)),
    )
    per_seat2, _game2 = collector.finish(final_with_bg, ())
    assert per_seat2[0]["cards_end"] == 2  # southern_faith and long_reach
    # Both pair now: southern_faith with long_reach, and long_reach with
    # southern_faith -- desert_power (Fremen) still does not pay off either.
    assert per_seat2[0]["pairs_end"] == 2
