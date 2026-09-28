"""Arrakeen Scouts: subcommittees and the Scouts effect frame (slice 4).

docs/rules/arrakeen-scouts.md 4: "원로회 자리(High Council seat)를 차지할 때
(High Council 칸, Corrinth City), 아직 아무도 가입하지 않은 소위원회 하나에
가입할 수 있다. 비용을 내고 보상을 한 번 받는다." [Scouts help]; the offer
lists only what the seat can pay for and may be declined for good (OQ-076).
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind

SCOUTS = RulesetConfig(arrakeen_scouts=True)
STARTERS = starting_deck_instance_ids(0)
DAGGER = "player:0:starter:dagger:0"
DISPLAY = ("readiness", "oversight", "relations", "appropriations", "leverage")
ENGINE = UprisingRulesEngine()


def _state(
    owner: PlayerState, *, config: RulesetConfig = SCOUTS, **fields: Any
) -> GameState:
    values: dict[str, Any] = {
        "config": config,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 2,
        "first_player": 0,
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "scouts_subcommittees": DISPLAY if config.arrakeen_scouts else (),
        "intrigue_deck": ("intrigue:0", "intrigue:1", "intrigue:2"),
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:2:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(fields)
    return GameState(**values)


def _owner(**overrides: Any) -> PlayerState:
    values: dict[str, Any] = {
        "player_id": 0,
        "hand": STARTERS,
        "resources": Resources(solari=10, spice=5, water=1),
    }
    values.update(overrides)
    return PlayerState(**values)


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    top = state.decision_stack[-1].decision
    assert isinstance(top, PlayerDecision)
    action = DomainAction(
        action_id=action_id,
        actor=top.owner,
        arguments=tuple(sorted(arguments.items())),
    )
    legal = ENGINE.legal_actions(state, top.owner)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def _visit_high_council(state: GameState) -> GameState:
    """Send the Dagger to the High Council and resolve its board icons."""

    state = _act(state, "agent_turn", card_id=DAGGER, space_id="high_council")
    while state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS:
        board = [
            a
            for a in ENGINE.legal_actions(state, 0)
            if a.action_id == "resolve_board_effect"
        ]
        if not board:
            break
        state = ENGINE.apply(state, board[0]).state
    return state


def _scouts_frames_done(state: GameState) -> bool:
    """The line resolved; the High Council was the turn's last effect, so the
    next seat's turn is open (the offer was marked ``turn_closed``)."""

    top = state.decision_stack[-1]
    assert isinstance(top.decision, PlayerDecision)
    return top.kind == FrameKind.TURN and top.decision.owner == 1


def _options(state: GameState) -> set[tuple[str, str]]:
    top = state.decision_stack[-1].decision
    assert isinstance(top, PlayerDecision)
    return {
        (a.action_id, str(dict(a.arguments).get(next(iter(dict(a.arguments)), ""), "")))
        if a.arguments
        else (a.action_id, "")
        for a in ENGINE.legal_actions(state, top.owner)
    }


def test_taking_the_high_council_seat_offers_the_payable_subcommittees() -> None:
    state = _visit_high_council(_state(_owner()))
    assert state.players[0].high_council
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_SUBCOMMITTEE
    offered = _options(state)
    # Oversight needs a Spy to recall and Leverage two; the seat has none.
    assert offered == {
        ("decline_subcommittee", ""),
        ("join_subcommittee", "readiness"),
        ("join_subcommittee", "relations"),
        ("join_subcommittee", "appropriations"),
    }


def test_without_the_option_no_offer_is_queued() -> None:
    state = _visit_high_council(_state(_owner(), config=RulesetConfig()))
    assert state.players[0].high_council
    assert state.decision_stack[-1].kind != FrameKind.SCOUTS_SUBCOMMITTEE
    assert not state.scouts_subcommittee_offers


def test_readiness_recruits_a_troop_and_records_the_member() -> None:
    state = _visit_high_council(_state(_owner()))
    garrison = state.players[0].troops_garrison
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert state.scouts_subcommittee_members == (("readiness", 0),)
    assert state.players[0].troops_garrison == garrison + 1
    assert _scouts_frames_done(state)
    events = [e.kind for e in state.event_log]
    assert "scouts_subcommittee_joined" in events
    assert "scouts_effect_resolved" in events


def test_appropriations_discards_a_chosen_card_for_water() -> None:
    state = _visit_high_council(_state(_owner()))
    state = _act(state, "join_subcommittee", subcommittee_id="appropriations")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    discard = next(iter(state.players[0].hand))
    offered = {dict(a.arguments)["card_id"] for a in ENGINE.legal_actions(state, 0)}
    assert offered == set(state.players[0].hand)
    state = _act(state, "scouts_discard", card_id=discard)
    assert discard in state.players[0].discard_pile
    assert state.players[0].resources.water == 2
    assert _scouts_frames_done(state)


def test_relations_pays_spice_and_lets_the_seat_choose_a_faction() -> None:
    state = _visit_high_council(_state(_owner()))
    spice = state.players[0].resources.spice
    state = _act(state, "join_subcommittee", subcommittee_id="relations")
    assert state.players[0].resources.spice == spice - 2
    state = _act(state, "scouts_choose_faction", faction="fremen")
    assert state.players[0].influence.fremen == 1


def test_leverage_recalls_two_chosen_spies_then_gains() -> None:
    owner = _owner(
        spies_supply=1,
        spy_post_ids=("arrakis-deep-desert", "arrakis-hagga-basin"),
    )
    state = _visit_high_council(_state(owner))
    state = _act(state, "join_subcommittee", subcommittee_id="leverage")
    state = _act(state, "scouts_recall_spy", post_id="arrakis-hagga-basin")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    state = _act(state, "scouts_recall_spy", post_id="arrakis-deep-desert")
    assert state.players[0].spy_post_ids == ()
    assert state.players[0].spies_supply == 3
    intrigue = len(state.players[0].intrigue_cards)
    state = _act(state, "scouts_choose_faction", faction="emperor")
    assert state.players[0].influence.emperor == 1
    assert len(state.players[0].intrigue_cards) == intrigue + 1


def test_contingencies_recalls_another_agent_not_the_high_council_one() -> None:
    # OQ-075: "다른 Agent" is not the Agent that just took the seat.
    owner = _owner(
        intrigue_cards=("intrigue:9",),
        agent_locations=("imperial_basin",),
        agents_available=1,
    )
    state = _visit_high_council(
        _state(
            owner,
            scouts_subcommittees=(*DISPLAY[:4], "contingencies"),
        )
    )
    state = _act(state, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert "intrigue:9" in state.intrigue_trash
    assert _options(state) == {("scouts_recall_agent", "imperial_basin")}
    state = _act(state, "scouts_recall_agent", space_id="imperial_basin")
    assert state.players[0].agent_locations == ("high_council",)
    assert state.players[0].agents_available == 1


def test_contingencies_can_recall_an_agent_sent_into_the_conflict() -> None:
    """Into the Fray, OQ-068, OQ-075 (D): ``_recallable_spaces`` also offers
    the pseudo space "conflict" when the seat has an Agent there, alongside
    its other board Agents; choosing it calls ``effects.recall_conflict_agent``."""
    owner = _owner(
        intrigue_cards=("intrigue:9",),
        agent_locations=("imperial_basin",),
        agent_in_conflict=1,
        agents_available=1,
        swordmaster_acquired=True,
    )
    state = _visit_high_council(
        _state(
            owner,
            scouts_subcommittees=(*DISPLAY[:4], "contingencies"),
        )
    )
    state = _act(state, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {
        ("scouts_recall_agent", "imperial_basin"),
        ("scouts_recall_agent", "conflict"),
    }
    state = _act(state, "scouts_recall_agent", space_id="conflict")
    assert state.players[0].agent_in_conflict == 0
    assert state.players[0].agents_available == 1
    assert state.players[0].agent_locations == ("imperial_basin", "high_council")


def test_declining_ends_the_chance_and_a_claimed_one_is_gone() -> None:
    state = _visit_high_council(_state(_owner()))
    state = _act(state, "decline_subcommittee")
    assert not state.scouts_subcommittee_members
    assert _scouts_frames_done(state)
    # Another seat, later: Readiness is claimed by seat 2 meanwhile.
    claimed = _state(
        _owner(),
        scouts_subcommittee_members=(("readiness", 2),),
    )
    offered = _options(_visit_high_council(claimed))
    assert ("join_subcommittee", "readiness") not in offered


def test_an_offer_with_nothing_payable_lapses_without_a_frame() -> None:
    poor = _owner(resources=Resources(solari=5, spice=0, water=1), hand=(DAGGER,))
    state = _visit_high_council(
        _state(poor, scouts_subcommittees=("oversight", "relations", "leverage"))
    )
    assert state.decision_stack[-1].kind != FrameKind.SCOUTS_SUBCOMMITTEE
    assert any(e.kind == "scouts_subcommittee_unavailable" for e in state.event_log)


def test_members_are_unique() -> None:
    with pytest.raises(ValueError, match="one member"):
        _state(
            _owner(),
            scouts_subcommittee_members=(("readiness", 0), ("readiness", 1)),
        )
    with pytest.raises(ValueError, match="revealed"):
        _state(_owner(), scouts_subcommittee_members=(("forecasting", 0),))
    base = _state(_owner())
    assert replace(base, scouts_subcommittee_members=(("readiness", 0),))


def test_specimen_top_up_offers_the_shortfall_before_readiness_recruits() -> None:
    """Immortality p. 8, user ruling 2026-09-29 (OQ-050, OQ-074): Readiness's
    RecruitTroops(1) offers 0..min(short, specimens) first when the seat's
    supply is short; the recruit then resolves with the enlarged supply."""
    config = RulesetConfig(arrakeen_scouts=True, immortality=True)
    owner = _owner(troops_supply=0, troops_garrison=11, specimens=1)
    state = _visit_high_council(_state(owner, config=config))
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    counts = sorted(
        dict(a.arguments)["count"]
        for a in ENGINE.legal_actions(state, 0)
        if a.action_id == "scouts_return_specimens"
    )
    assert counts == [0, 1]
    state = _act(state, "scouts_return_specimens", count=1)
    assert state.players[0].troops_supply == 0
    assert state.players[0].troops_garrison == 12
    assert state.players[0].specimens == 0
    assert _scouts_frames_done(state)


def test_specimen_top_up_needs_immortality() -> None:
    """Immortality p. 8: without Immortality, Readiness just recruits what
    the supply holds; no specimen choice appears."""
    owner = _owner(troops_supply=0, troops_garrison=12)
    state = _visit_high_council(_state(owner))
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert _scouts_frames_done(state)
    assert state.players[0].troops_supply == 0
    assert state.players[0].troops_garrison == 12


def test_specimen_top_up_is_skipped_with_enough_supply() -> None:
    """Immortality p. 8, user ruling 2026-09-29: the top-up only appears when
    the seat's supply is short of the recruit; with enough supply Readiness
    just recruits and the specimens stay untouched."""
    config = RulesetConfig(arrakeen_scouts=True, immortality=True)
    owner = _owner(troops_supply=1, troops_garrison=10, specimens=1)
    state = _visit_high_council(_state(owner, config=config))
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert _scouts_frames_done(state)
    assert state.players[0].troops_supply == 0
    assert state.players[0].troops_garrison == 11
    assert state.players[0].specimens == 1


def test_influence_choice_skips_tracks_at_the_top() -> None:
    # OQ-060: an Influence gain at the top of a track is lost; with only one
    # track below the top there is no choice to make.
    owner = _owner(influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6))
    state = _visit_high_council(_state(owner))
    state = _act(state, "join_subcommittee", subcommittee_id="relations")
    assert state.players[0].influence.fremen == 1
    assert _scouts_frames_done(state)


def test_the_conflict_agent_is_not_recallable_during_the_seats_reveal() -> None:
    """Review 2026-09-29 (OQ-075, pending): Corrinth City's seat is taken in
    the Reveal turn, while the seat's strength is being counted, so the Into
    the Fray Agent is not offered then; its board Agents still are."""
    from dune_imperium.rules.scouts_effects import _recallable_spaces

    owner = _owner(
        agent_locations=("imperial_basin",),
        agent_in_conflict=1,
        agents_available=0,
    )
    agent_turn = _state(owner)
    assert _recallable_spaces(agent_turn, owner, "") == ("imperial_basin", "conflict")
    reveal = replace(
        agent_turn,
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.REVEAL,
                frame_id="round:2:reveal:0",
                decision=PlayerDecision(owner=0, prompt="Reveal"),
            ),
        ),
    )
    assert _recallable_spaces(reveal, owner, "") == ("imperial_basin",)
