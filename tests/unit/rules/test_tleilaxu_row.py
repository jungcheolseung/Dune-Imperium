"""Tests for the Tleilaxu Row, Reclaimed Forces, and the first Tleilaxu cards.

Rule source: ``docs/rules/immortality.md`` section 4 [Immortality pp. 6, 8-9]
and the card faces of Contaminator, From the Tanks, and Subject X-137.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.immortality.tleilaxu import (
    tleilaxu_card_for_instance,
    tleilaxu_deck_instance_ids,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.setup import create_initial_state
from dune_imperium.rules.tleilaxu_row import (
    apply_tleilaxu_acquisition,
    legal_tleilaxu_acquisitions,
)
from dune_imperium.simulation.sweep import run_checked_game

IMMORTALITY = RulesetConfig(immortality=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
CONTAMINATOR = "tleilaxu:contaminator:0"
FROM_THE_TANKS = "tleilaxu:from_the_tanks:0"
SUBJECT = "tleilaxu:subject_x_137:0"


def _owner(**overrides: object) -> PlayerState:
    deck = starting_deck_instance_ids(0, immortality=True)
    values: dict[str, object] = {
        "player_id": 0,
        "hand": deck[:5],
        "deck": deck[5:],
        "resources": Resources(solari=4, spice=2, water=2),
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
        "specimens": 3,
        "troops_supply": 6,
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _seat(seat: int) -> PlayerState:
    return PlayerState(
        player_id=seat, research_space=RESEARCH_START_ID, family_atomics=True
    )


def _reveal_state(owner: PlayerState, **overrides: object) -> GameState:
    imperium = imperium_deck_instance_ids(False)
    values: dict[str, object] = {
        "config": IMMORTALITY,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False)[:6],
        "imperium_row": imperium[:5],
        "imperium_deck": imperium[5:20],
        "tleilaxu_row": (CONTAMINATOR, SUBJECT),
        "tleilaxu_deck": (FROM_THE_TANKS,),
        "tleilaxu_track_spice": 2,
        "players": (owner, *(_seat(seat) for seat in range(1, 4))),
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(overrides)
    state = GameState(**values)  # type: ignore[arg-type]
    return begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state


def _actions(state: GameState) -> dict[str, DomainAction]:
    keyed: dict[str, DomainAction] = {}
    for action in legal_tleilaxu_acquisitions(state, 0):
        arguments = dict(action.arguments)
        if action.action_id == "acquire_reclaimed_forces":
            keyed[f"reclaimed:{arguments['choice']}"] = action
        else:
            suffix = ":top" if arguments.get("to_deck_top") else ""
            keyed[f"{arguments['instance_id']}{suffix}"] = action
    return keyed


def test_the_three_cards_have_the_printed_data_and_join_the_deck() -> None:
    assert {CONTAMINATOR, FROM_THE_TANKS, SUBJECT} <= set(tleilaxu_deck_instance_ids())
    contaminator = tleilaxu_card_for_instance(CONTAMINATOR)
    assert contaminator.specimen_cost == 1 and contaminator.reveal_persuasion == 1
    subject = tleilaxu_card_for_instance(SUBJECT)
    assert subject.has_acquisition_bonus and subject.specimen_cost == 2


def test_setup_shuffles_the_deck_and_deals_two_to_the_row() -> None:
    state = create_initial_state(IMMORTALITY, 7, LEADERS).state
    assert len(state.tleilaxu_row) == 2
    assert len(state.tleilaxu_deck) == len(tleilaxu_deck_instance_ids()) - 2
    assert set(state.tleilaxu_row) | set(state.tleilaxu_deck) == set(
        tleilaxu_deck_instance_ids()
    )


def test_acquisitions_need_the_specimens_and_the_deck_top_needs_a_marker() -> None:
    poor = _reveal_state(_owner(specimens=1, troops_supply=8))
    assert set(_actions(poor)) == {CONTAMINATOR}
    rich = _reveal_state(_owner())
    assert set(_actions(rich)) == {
        CONTAMINATOR,
        SUBJECT,
        "reclaimed:troops",
        "reclaimed:tleilaxu",
    }
    marked = _reveal_state(_owner(research_space="c4r4"))
    assert f"{CONTAMINATOR}:top" in _actions(marked)
    # Nobody else may buy during this Reveal.
    assert legal_tleilaxu_acquisitions(marked, 1) == ()


def test_acquiring_pays_specimens_refills_the_row_and_pays_the_acquire_box() -> None:
    state = _reveal_state(_owner())

    result = apply_tleilaxu_acquisition(state, _actions(state)[SUBJECT])

    owner = result.state.players[0]
    assert owner.specimens == 1 and owner.troops_supply == 8
    assert owner.discard_pile[-1] == SUBJECT
    assert owner.tleilaxu_space == 1  # the acquire box
    assert result.state.tleilaxu_row == (CONTAMINATOR, FROM_THE_TANKS)
    assert result.state.tleilaxu_deck == ()
    assert result.events[0].kind == "tleilaxu_card_acquired"


def test_past_the_first_marker_the_card_may_go_on_top_of_the_deck() -> None:
    state = _reveal_state(_owner(research_space="c4r4"))

    result = apply_tleilaxu_acquisition(state, _actions(state)[f"{CONTAMINATOR}:top"])

    owner = result.state.players[0]
    assert owner.deck[0] == CONTAMINATOR
    assert CONTAMINATOR not in owner.discard_pile


def test_reclaimed_forces_stays_and_offers_troops_or_tleilaxu() -> None:
    state = _reveal_state(_owner())

    troops = apply_tleilaxu_acquisition(state, _actions(state)["reclaimed:troops"])
    owner = troops.state.players[0]
    assert owner.specimens == 0
    assert owner.troops_garrison == 5 and owner.troops_supply == 7
    assert troops.state.tleilaxu_row == (CONTAMINATOR, SUBJECT)
    assert dict(troops.state.decision_stack[-1].context)["reveal_troops_recruited"] == 2

    tleilaxu = apply_tleilaxu_acquisition(state, _actions(state)["reclaimed:tleilaxu"])
    assert tleilaxu.state.players[0].tleilaxu_space == 1


def _agent_turn(card_id: str, space_id: str, **overrides: object) -> GameState:
    deck = starting_deck_instance_ids(0, immortality=True)
    owner = _owner(hand=(card_id,), deck=deck, **overrides)
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        players=(owner, *(_seat(seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_agent_action(state, placement).state


def test_contaminator_advances_the_tleilaxu_token() -> None:
    state = _agent_turn(CONTAMINATOR, "fremkit")
    result = resolve_agent_card_effect(state)
    assert result.state.players[0].tleilaxu_space == 1


def test_from_the_tanks_recruits_two_troops() -> None:
    state = _agent_turn(FROM_THE_TANKS, "assembly_hall")
    result = resolve_agent_card_effect(state)
    assert result.state.players[0].troops_garrison == 5


def test_subject_x_137_needs_the_first_genetic_marker() -> None:
    unmarked = resolve_agent_card_effect(_agent_turn(SUBJECT, "assembly_hall"))
    assert unmarked.state.players[0].tleilaxu_space == 0
    assert unmarked.events[0].kind == "agent_card_effect_unavailable"
    marked = resolve_agent_card_effect(
        _agent_turn(SUBJECT, "assembly_hall", research_space="c4r2")
    )
    assert marked.state.players[0].tleilaxu_space == 1


def test_the_codec_holds_row_and_reclaimed_forces_choices() -> None:
    codec = ActionCodec(IMMORTALITY)
    state = _reveal_state(_owner(research_space="c4r4"))
    for action in legal_tleilaxu_acquisitions(state, 0):
        assert codec.decode(codec.encode(action), action.actor) == action
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    assert not {"acquire_tleilaxu", "acquire_reclaimed_forces"} & base


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_checked_games_buy_from_the_row(policy: str) -> None:
    acquired = 0
    for seed in range(3):
        report = run_checked_game(
            IMMORTALITY,
            seed,
            900_000 + seed,
            policy=policy,
            soundness_interval=25,
            collect_coverage=True,
        )
        assert report.winner is not None
        assert report.coverage is not None
        acquired += report.coverage["event_kinds"].get("tleilaxu_card_acquired", 0)
    assert acquired > 0


def test_the_engine_deals_the_row_and_plays_a_game() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(IMMORTALITY, seed=9)
    assert len(state.tleilaxu_row) == 2
    assert all(isinstance(replace(seat).research_space, str) for seat in state.players)
