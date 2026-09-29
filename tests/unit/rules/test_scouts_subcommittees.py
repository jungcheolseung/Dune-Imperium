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
from dune_imperium.content.uprising.conflicts import CONFLICTS
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


def test_the_conflict_agent_is_recallable_during_the_seats_reveal() -> None:
    """User ruling 2026-09-29 (OQ-075): Contingencies joined through Corrinth
    City's Reveal-turn seat may recall any of the seat's other Agents,
    including an Into the Fray Agent in the Conflict, so the Conflict Agent
    is offered while the seat's own REVEAL frame is open too."""
    from dune_imperium.content.arrakeen_scouts import SUBCOMMITTEES_BY_ID
    from dune_imperium.rules.scouts_effects import _recallable_spaces, line_is_offered

    owner = _owner(
        intrigue_cards=("intrigue:9",),
        agent_locations=("imperial_basin",),
        agent_in_conflict=1,
        agents_available=0,
    )
    assert _recallable_spaces(owner, "") == ("imperial_basin", "conflict")
    only_conflict = replace(owner, agent_locations=(), agents_available=1)
    reveal = replace(
        _state(only_conflict),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.REVEAL,
                frame_id="round:2:reveal:0",
                decision=PlayerDecision(owner=0, prompt="Reveal"),
            ),
        ),
    )
    assert _recallable_spaces(only_conflict, "") == ("conflict",)
    contingencies = SUBCOMMITTEES_BY_ID["contingencies"].option
    assert line_is_offered(reveal, 0, contingencies)


CORRINTH = "imperium:corrinth_city:0"


def _corrinth_contingencies(owner: PlayerState) -> GameState:
    """Reveal Corrinth City, take the seat, join Contingencies and pay it;
    the recall choice is next (OQ-075: joined means the recall is made)."""

    state = _state(owner, scouts_subcommittees=(*DISPLAY[:4], "contingencies"))
    state = _act(state, "reveal_turn")
    state = _act(state, "take_high_council_from_reveal")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_SUBCOMMITTEE
    state = _act(state, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {("scouts_recall_agent", "conflict")}
    return state


def _reveal_strength(state: GameState) -> int:
    frame = next(f for f in state.decision_stack if f.kind == FrameKind.REVEAL)
    strength = dict(frame.context)["strength"]
    assert isinstance(strength, int)
    return strength


@pytest.mark.parametrize("swordmaster", [False, True])
def test_corrinth_contingencies_recalls_the_conflict_agent_and_its_strength(
    swordmaster: bool,
) -> None:
    """User ruling 2026-09-29 (OQ-075): the Corrinth City seat's Contingencies
    may recall the Into the Fray Agent, and its strength is recomputed.
    Into the Fray: "deploy it to the Conflict as a 2 strength unit ... If you
    have your Swordmaster, it has 3 strength instead." [Duncan Idaho card];
    "Reveal turn 중 효과가 unit 수나 strength를 바꾸면 Combat marker도 그에
    맞게 갱신한다." [Main p. 13] (docs/rules/player-turns.md)."""
    owner = _owner(
        hand=(CORRINTH,),
        intrigue_cards=("intrigue:9",),
        agent_in_conflict=1,
        agents_available=2 if swordmaster else 1,
        swordmaster_acquired=swordmaster,
        troops_supply=7,
        troops_conflict=2,
    )
    agent = 3 if swordmaster else 2
    state = _corrinth_contingencies(owner)
    before = state.players[0]
    assert before.combat_strength == _reveal_strength(state) == 4 + agent
    state = _act(state, "scouts_recall_agent", space_id="conflict")
    seat = state.players[0]
    assert seat.agent_in_conflict == 0
    assert seat.agents_available == before.agents_available + 1
    assert seat.combat_strength == 4
    assert _reveal_strength(state) == seat.combat_strength
    assert state.decision_stack[-1].kind == FrameKind.REVEAL


def test_recalling_the_only_unit_drops_strength_to_zero_until_a_troop_arrives() -> None:
    """ "Conflict에 unit이 하나 이상 있어야 strength를 가질 수 있다. 마지막
    unit이 제거되면 sword가 남아 있어도 strength는 0이 된다." [Main p. 12]
    (docs/rules/player-turns.md): the Into the Fray Agent was the seat's only
    unit, so the Dagger's revealed sword stops counting; a troop that enters
    later in the same Reveal brings the swords back [Main p. 13]."""
    from dune_imperium.rules.reveal_turn import add_units_to_reveal

    owner = _owner(
        hand=(CORRINTH, DAGGER),
        intrigue_cards=("intrigue:9",),
        agent_in_conflict=1,
        agents_available=1,
    )
    state = _corrinth_contingencies(owner)
    assert state.players[0].combat_strength == _reveal_strength(state) == 2 + 1
    state = _act(state, "scouts_recall_agent", space_id="conflict")
    assert state.players[0].units_in_conflict == 0
    assert state.players[0].combat_strength == 0
    assert _reveal_strength(state) == 0
    state = add_units_to_reveal(state, 0, troops=1).state
    assert state.players[0].combat_strength == 2 + 1
    assert _reveal_strength(state) == 2 + 1


def test_the_corrinth_seat_gets_no_further_agent_turn_after_the_recall() -> None:
    """User ruling 2026-09-29 (OQ-075): having revealed, the seat takes no
    Agent turn with the recalled Agent; the other seats reveal and Combat
    follows without a TURN frame for seat 0."""
    owner = _owner(
        hand=(CORRINTH,),
        intrigue_cards=("intrigue:9",),
        agent_in_conflict=1,
        agents_available=1,
        troops_supply=7,
        troops_conflict=2,
    )
    state = _corrinth_contingencies(owner)
    state = _act(state, "scouts_recall_agent", space_id="conflict")
    state = _act(state, "finish_reveal")
    assert state.players[0].has_revealed
    assert state.players[0].agents_available == 2
    turn_owners = []
    while state.phase is GamePhase.PLAYER_TURNS:
        top = state.decision_stack[-1]
        assert isinstance(top.decision, PlayerDecision)
        if top.kind == FrameKind.TURN:
            turn_owners.append(top.decision.owner)
        legal = ENGINE.legal_actions(state, top.decision.owner)
        pick = next(a for a in legal if a.action_id in ("reveal_turn", "finish_reveal"))
        state = ENGINE.apply(state, pick, legal_actions=legal).state
    assert turn_owners == [1, 2, 3]
    assert state.phase is GamePhase.COMBAT


def test_contingencies_is_not_offered_without_another_agent_to_recall() -> None:
    """User principle 2026-09-29 (OQ-071): a white-arrow line whose effect
    cannot happen cannot be paid for, and joining a subcommittee with a cost
    means paying it (docs/rules/arrakeen-scouts.md 4, OQ-075). The seat's
    only Agent out is the one that took the seat, so Contingencies is not
    joinable; with nothing else joinable the offer lapses."""
    owner = _owner(intrigue_cards=("intrigue:9",))
    state = _visit_high_council(
        _state(owner, scouts_subcommittees=(*DISPLAY[:4], "contingencies"))
    )
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_SUBCOMMITTEE
    assert ("join_subcommittee", "contingencies") not in _options(state)
    lapsed = _visit_high_council(_state(owner, scouts_subcommittees=("contingencies",)))
    assert lapsed.decision_stack[-1].kind != FrameKind.SCOUTS_SUBCOMMITTEE
    assert any(e.kind == "scouts_subcommittee_unavailable" for e in lapsed.event_log)
    assert lapsed.players[0].intrigue_cards == ("intrigue:9",)


def test_contingencies_is_offered_for_an_into_the_fray_agent_alone() -> None:
    """Into the Fray (OQ-068, OQ-075 (D)): an earlier turn's Conflict Agent is
    one of the seat's other Agents, so Contingencies stays joinable when it
    is the only one, and the recall offers exactly that Agent."""
    owner = _owner(
        intrigue_cards=("intrigue:9",), agent_in_conflict=1, agents_available=1
    )
    state = _visit_high_council(
        _state(owner, scouts_subcommittees=(*DISPLAY[:4], "contingencies"))
    )
    assert ("join_subcommittee", "contingencies") in _options(state)
    state = _act(state, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {("scouts_recall_agent", "conflict")}
    state = _act(state, "scouts_recall_agent", space_id="conflict")
    assert state.players[0].agent_in_conflict == 0
    assert state.players[0].agents_available == 1


def _into_the_fray_then_the_seat(extra_locations: tuple[str, ...]) -> GameState:
    """Duncan Idaho's Signet Ring at the High Council: Into the Fray moves the
    Agent into the Conflict first, then the seat is taken."""
    signet = "player:0:starter:signet_ring:0"
    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(signet,),
        intrigue_cards=("intrigue:9",),
        resources=Resources(solari=10, spice=0, water=0),
        agent_locations=extra_locations,
        agents_available=2 - len(extra_locations),
    )
    state = _state(
        owner,
        config=RulesetConfig(arrakeen_scouts=True, bloodlines=True),
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        scouts_subcommittees=(*DISPLAY[:4], "contingencies"),
    )
    state = _act(state, "agent_turn", card_id=signet, space_id="high_council")
    state = _act(state, "deploy_leader_agent")
    assert state.players[0].agent_in_conflict == 1
    board = [
        a
        for a in ENGINE.legal_actions(state, 0)
        if a.action_id == "resolve_board_effect"
    ]
    return ENGINE.apply(state, board[0]).state


def test_contingencies_never_recalls_the_seat_taker_moved_by_into_the_fray() -> None:
    """Review 2026-09-29: "not the Agent you sent during this turn"
    [Main p. 20] (OQ-068, OQ-075). The Agent that took the seat and then
    went into the Conflict is not "another Agent"."""
    alone = _into_the_fray_then_the_seat(())
    assert ("join_subcommittee", "contingencies") not in _options(alone)
    with_other = _into_the_fray_then_the_seat(("imperial_basin",))
    state = _act(with_other, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {("scouts_recall_agent", "imperial_basin")}
