"""Arrakeen Scouts: subcommittees and the Scouts effect frame (slice 4).

docs/rules/arrakeen-scouts.md 4: "원로회 자리(High Council seat)를 차지할 때
(High Council 칸, Corrinth City), 아직 아무도 가입하지 않은 소위원회 하나에
가입할 수 있다. 비용을 내고 보상을 한 번 받는다." [Scouts help]; the offer
lists only what the seat can pay for and may be declined for good (OQ-076).

OQ-076 alternative C (user ruling 2026-09-30, a project convention): the
join is one more effect of the turn the seat was taken in, taken whenever
the seat likes: "You may carry out all these effects in any order."
[Main p. 9]. The turn's frame offers ``choose_subcommittee`` (only when one
can be joined now) and ``decline_subcommittee``; choosing opens the list.
"""

import random
import sys
from dataclasses import replace
from pathlib import Path
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

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/support/turn_end.py's module docstring).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from turn_end import finish_agent_turn  # type: ignore[import-not-found]  # noqa: E402

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


def _visit_high_council(state: GameState, card_id: str = DAGGER) -> GameState:
    """Send a card (the Dagger) to the High Council; resolve its board icons."""

    state = _act(state, "agent_turn", card_id=card_id, space_id="high_council")
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


def _choose(state: GameState) -> GameState:
    """Open the new seat's subcommittee list from the turn's own frame."""

    assert state.decision_stack[-1].kind in (FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)
    state = _act(state, "choose_subcommittee")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_SUBCOMMITTEE
    return state


def _scouts_frames_done(state: GameState) -> bool:
    """The line resolved; the High Council was the turn's last effect, so only
    the owner's explicit turn end is left, and pressing it opens the next
    seat's turn (user ruling OQ-095 (1): every Agent turn ends only through
    its owner's ``finish_agent_turn``; (3): the line resolved inside it)."""

    top = state.decision_stack[-1]
    assert isinstance(top.decision, PlayerDecision)
    assert top.kind == FrameKind.AGENT_EFFECTS and top.decision.owner == 0
    assert ("finish_agent_turn", "") in _options(state)
    closed: GameState = finish_agent_turn(state)
    after = closed.decision_stack[-1]
    assert isinstance(after.decision, PlayerDecision)
    return after.kind == FrameKind.TURN and after.decision.owner == 1


def _options(state: GameState) -> set[tuple[str, str]]:
    top = state.decision_stack[-1].decision
    assert isinstance(top, PlayerDecision)
    return {
        (a.action_id, str(dict(a.arguments).get(next(iter(dict(a.arguments)), ""), "")))
        if a.arguments
        else (a.action_id, "")
        for a in ENGINE.legal_actions(state, top.owner)
    }


def _turn_count(state: GameState, key: str) -> int:
    """A count the owner's open Agent-turn effect frame keeps for the turn."""

    frame = next(f for f in state.decision_stack if f.kind == FrameKind.AGENT_EFFECTS)
    value = dict(frame.context).get(key, 0)
    assert isinstance(value, int)
    return value


def test_taking_the_high_council_seat_offers_the_payable_subcommittees() -> None:
    state = _visit_high_council(_state(_owner()))
    assert state.players[0].high_council
    # One more effect of the visit: the turn's frame stays open for it.
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _options(state) == {
        ("choose_subcommittee", ""),
        ("decline_subcommittee", ""),
    }
    state = _choose(state)
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
    assert _scouts_frames_done(state)


def test_readiness_recruits_a_troop_and_records_the_member() -> None:
    """User ruling OQ-095 (3): the join was the visit's last effect, yet its
    line resolves inside the still-open turn, so the troop is this turn's
    recruit: "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에
    deploy할 수 있다" [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md)."""
    state = _choose(_visit_high_council(_state(_owner())))
    garrison = state.players[0].troops_garrison
    recruited = _turn_count(state, "troops_recruited")
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert state.scouts_subcommittee_members == (("readiness", 0),)
    assert state.players[0].troops_garrison == garrison + 1
    assert _turn_count(state, "troops_recruited") == recruited + 1
    assert _scouts_frames_done(state)
    events = [e.kind for e in state.event_log]
    assert "scouts_subcommittee_joined" in events
    assert "scouts_effect_resolved" in events


def test_appropriations_discards_a_chosen_card_for_water() -> None:
    state = _choose(_visit_high_council(_state(_owner())))
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
    """User ruling OQ-095 (3): the cost is paid inside the still-open turn,
    so the Agent-turn frame books it as this turn's spice spent, not a later
    turn's, keeping the "spice gained" Harvest contracts read whole:
    "Harvest contract는 ... 그 turn에 모든 출처를 합쳐 contract에 표시된 양의
    spice를 얻으면 완료한다." [Main p. 16] (docs/rules/choam-module.md)."""
    state = _choose(_visit_high_council(_state(_owner())))
    spice = state.players[0].resources.spice
    spent = _turn_count(state, "spice_spent_after_placement")
    state = _act(state, "join_subcommittee", subcommittee_id="relations")
    assert state.players[0].resources.spice == spice - 2
    assert _turn_count(state, "spice_spent_after_placement") == spent + 2
    state = _act(state, "scouts_choose_faction", faction="fremen")
    assert state.players[0].influence.fremen == 1


def test_oversight_spice_as_the_last_effect_counts_for_hungry_for_spice() -> None:
    """User ruling OQ-095 (3), which lifts OQ-076's known limitation (1):
    Steersman Y'rkoon gained 2 spice earlier this turn and joins Oversight as
    the visit's last effect. Its spice resolves inside the still-open turn,
    so the turn's 3 spice earn the draw before the end is pressed: "Whenever
    you gain [spice 3] or more in a single turn: [draw]" [Steersman Y'rkoon
    card]; only his own turn's spice counts (OQ-063)."""
    second_dagger = "player:0:starter:dagger:1"
    owner = _owner(
        leader_id="steersman_y_rkoon",
        hand=(DAGGER,),
        deck=(second_dagger,),
        resources=Resources(solari=10, spice=5, water=1),
        spice_at_turn_start=3,
        spies_supply=2,
        spy_post_ids=("arrakis-deep-desert",),
    )
    state = _choose(_visit_high_council(_state(owner)))
    assert not state.players[0].hungry_for_spice_granted_turn
    state = _act(state, "join_subcommittee", subcommittee_id="oversight")
    state = _act(state, "scouts_recall_spy", post_id="arrakis-deep-desert")
    state = _act(state, "decline_optional_trash")
    seat = state.players[0]
    assert seat.resources.spice == 6
    assert seat.hungry_for_spice_granted_turn
    assert seat.hand == (second_dagger,)
    assert _scouts_frames_done(state)


def test_leverage_recalls_two_chosen_spies_then_gains() -> None:
    owner = _owner(
        spies_supply=1,
        spy_post_ids=("arrakis-deep-desert", "arrakis-hagga-basin"),
    )
    state = _choose(_visit_high_council(_state(owner)))
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
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    # Intrigue cards have no trash pile (OQ-061, user ruling 2026-10-04).
    assert "intrigue:9" in state.intrigue_discard
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
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {
        ("scouts_recall_agent", "imperial_basin"),
        ("scouts_recall_agent", "conflict"),
    }
    state = _act(state, "scouts_recall_agent", space_id="conflict")
    assert state.players[0].agent_in_conflict == 0
    assert state.players[0].agents_available == 1
    assert state.players[0].agent_locations == ("imperial_basin", "high_council")


def test_declining_in_the_list_ends_the_chance_and_a_claimed_one_is_gone() -> None:
    state = _choose(_visit_high_council(_state(_owner())))
    state = _act(state, "decline_subcommittee")
    assert not state.scouts_subcommittee_members
    assert _scouts_frames_done(state)
    assert [e.kind for e in state.event_log].count("scouts_subcommittee_declined") == 1
    # Another seat, later: Readiness is claimed by seat 2 meanwhile.
    claimed = _state(
        _owner(),
        scouts_subcommittee_members=(("readiness", 2),),
    )
    offered = _options(_choose(_visit_high_council(claimed)))
    assert ("join_subcommittee", "readiness") not in offered


def test_declining_at_the_turn_frame_ends_the_chance() -> None:
    """Joining is optional ("may", OQ-076): the decline sits beside the
    visit's other effects, and it retires the icon like any other."""
    state = _visit_high_council(_state(_owner()))
    state = _act(state, "decline_subcommittee")
    assert not state.scouts_subcommittee_members
    assert _scouts_frames_done(state)
    declined = [e for e in state.event_log if e.kind == "scouts_subcommittee_declined"]
    assert [dict(e.payload)["player"] for e in declined] == [0]


def test_nothing_joinable_now_offers_only_the_decline() -> None:
    """Every subcommittee left is open but none can be joined now (their
    costs are unpaid): no ``choose_subcommittee``, the decline stays, and
    the turn waits on it rather than dropping the chance."""
    poor = _owner(resources=Resources(solari=5, spice=0, water=1), hand=(DAGGER,))
    state = _visit_high_council(
        _state(poor, scouts_subcommittees=("oversight", "relations", "leverage"))
    )
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _options(state) == {("decline_subcommittee", "")}
    state = _act(state, "decline_subcommittee")
    assert _scouts_frames_done(state)


def test_an_offer_with_every_subcommittee_taken_offers_only_the_decline() -> None:
    """User ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정
    창을 연다" (OQ-076 (c)): with every subcommittee already taken the new
    seat's offer is still armed, the turn waits on it, and only the decline
    is offered; the page greys the choice out as "claimed" among the choices
    that cannot be taken. It used to lapse with the event
    ``scouts_subcommittee_unavailable``. Unreachable with four players (five
    subcommittees on display, at most three other members), so a synthetic
    three-strong display stands in."""
    from dune_imperium.display.unavailable import unavailable_choices

    # A seat joins once, so three other seats can hold a three-strong display.
    claimed = tuple((subcommittee, 1 + n) for n, subcommittee in enumerate(DISPLAY[:3]))
    state = _visit_high_council(
        _state(
            _owner(),
            scouts_subcommittees=DISPLAY[:3],
            scouts_subcommittee_members=claimed,
        )
    )
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _options(state) == {("decline_subcommittee", "")}
    found = unavailable_choices(state, 0, ENGINE.legal_actions(state, 0))
    assert found is not None
    listed = found["rows"]
    assert isinstance(listed, list)
    [row] = listed
    assert row["surface"] == "choice"
    assert row["code"] == "claimed"
    assert row["reason_ko"] == "모든 소위원회에 가입한 좌석이 있음"
    state = _act(state, "decline_subcommittee")
    assert _scouts_frames_done(state)

    # Corrinth City's seat taken in a Reveal: the Reveal waits the same way.
    reveal = _state(
        _owner(hand=(CORRINTH,)),
        scouts_subcommittees=DISPLAY[:3],
        scouts_subcommittee_members=claimed,
    )
    reveal = _act(_act(reveal, "reveal_turn"), "take_high_council_from_reveal")
    assert reveal.decision_stack[-1].kind == FrameKind.REVEAL
    offered = _options(reveal)
    assert ("decline_subcommittee", "") in offered
    assert ("choose_subcommittee", "") not in offered
    assert ("finish_reveal", "") not in offered
    reveal = _act(reveal, "decline_subcommittee")
    assert ("finish_reveal", "") in _options(reveal)


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
    state = _choose(_visit_high_council(_state(owner, config=config)))
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
    state = _choose(_visit_high_council(_state(owner)))
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
    state = _choose(_visit_high_council(_state(owner, config=config)))
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert _scouts_frames_done(state)
    assert state.players[0].troops_supply == 0
    assert state.players[0].troops_garrison == 11
    assert state.players[0].specimens == 1


def test_influence_choice_skips_tracks_at_the_top() -> None:
    # OQ-060: an Influence gain at the top of a track is lost; with only one
    # track below the top there is no choice to make.
    owner = _owner(influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6))
    state = _choose(_visit_high_council(_state(owner)))
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
    assert state.decision_stack[-1].kind == FrameKind.REVEAL
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="contingencies")
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
    joinable; with nothing else joinable only declining is offered."""
    owner = _owner(intrigue_cards=("intrigue:9",))
    state = _visit_high_council(
        _state(owner, scouts_subcommittees=(*DISPLAY[:4], "contingencies"))
    )
    assert ("join_subcommittee", "contingencies") not in _options(_choose(state))
    alone = _visit_high_council(_state(owner, scouts_subcommittees=("contingencies",)))
    assert _options(alone) == {("decline_subcommittee", "")}
    declined = _act(alone, "decline_subcommittee")
    assert _scouts_frames_done(declined)
    assert declined.players[0].intrigue_cards == ("intrigue:9",)


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
    state = _choose(state)
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
    assert ("join_subcommittee", "contingencies") not in _options(_choose(alone))
    with_other = _choose(_into_the_fray_then_the_seat(("imperial_basin",)))
    state = _act(with_other, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {("scouts_recall_agent", "imperial_basin")}


# --- OQ-076 alternative C: the join is taken any time in the turn ------------------

TECH_SCOUTS = RulesetConfig(arrakeen_scouts=True, bloodlines=True, tech_module=True)
TECH_STACKS = (
    ("glowglobes", "training_depot"),
    ("gene_locked_vault", "delivery_bay"),
    ("advanced_data_analysis", "plasteel_blades"),
)
GLOWGLOBES = (("tech_id", "glowglobes"),)


def _tech_visit(spice: int) -> GameState:
    """The Dagger at the High Council with the Tech Module on: the seat and
    the Ixian Embassy's Acquire Tech are both effects of the visit."""

    owner = _owner(hand=(DAGGER,), resources=Resources(solari=5, spice=spice, water=1))
    state = _state(
        owner,
        config=TECH_SCOUTS,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        tech_stacks=TECH_STACKS,
    )
    return _visit_high_council(state)


def test_the_seat_buys_a_tech_tile_at_its_discount_then_joins() -> None:
    """The user's example (2026-09-30): take the High Council seat, buy a
    Tech tile 1 spice cheaper for it ("if you have a High Council seat, each
    Tech tile costs you 1 less spice" [Bloodlines p. 7]), and only then
    choose the subcommittee, paying its cost from what is left."""
    from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID

    state = _tech_visit(spice=4)
    assert ("choose_subcommittee", "") in _options(state)
    assert ("decline_tech", "") in _options(state)
    state = ENGINE.apply(
        state, DomainAction(action_id="acquire_tech", actor=0, arguments=GLOWGLOBES)
    ).state
    assert state.players[0].tech_ids == ("glowglobes",)
    discounted = TECH_TILES_BY_ID["glowglobes"].cost - 1
    assert state.players[0].resources.spice == 4 - discounted
    # The choice waited for its turn; Relations' 2 spice is still payable.
    assert _options(state) == {
        ("choose_subcommittee", ""),
        ("decline_subcommittee", ""),
        ("resolve_tech_acquire_effect", "influence"),
    }
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="relations")
    assert state.players[0].resources.spice == 4 - discounted - 2
    state = _act(state, "scouts_choose_faction", faction="fremen")
    assert state.scouts_subcommittee_members == (("relations", 0),)
    assert state.players[0].influence.fremen == 1
    state = _act(
        state, "resolve_tech_acquire_effect",
        effect="influence", faction="emperor", tech_id="glowglobes",
    )
    assert _scouts_frames_done(state)


def test_the_seat_joins_first_then_buys_its_tech_tile() -> None:
    """The other order [Main p. 9]: the line resolves above the still-open
    turn, which then offers the Tech tile at the seat's discount."""
    state = _choose(_tech_visit(spice=4))
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert state.scouts_subcommittee_members == (("readiness", 0),)
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    offered = _options(state)
    assert ("choose_subcommittee", "") not in offered
    assert ("decline_subcommittee", "") not in offered
    assert ("acquire_tech", "glowglobes") in offered
    state = ENGINE.apply(
        state, DomainAction(action_id="acquire_tech", actor=0, arguments=GLOWGLOBES)
    ).state
    assert state.players[0].tech_ids == ("glowglobes",)
    state = _act(
        state, "resolve_tech_acquire_effect",
        effect="influence", faction="emperor", tech_id="glowglobes",
    )
    assert _scouts_frames_done(state)


STEERSMAN = "imperium:steersman:0"


def _steersman_visit(display: tuple[str, ...]) -> GameState:
    """Steersman at the High Council: its Agent box draws a card, a
    freely ordered effect beside the seat's choice [Main p. 9]."""

    owner = _owner(
        hand=(STEERSMAN,),
        deck=(DAGGER,),
        resources=Resources(solari=5, spice=0, water=1),
    )
    return _visit_high_council(_state(owner, scouts_subcommittees=display), STEERSMAN)


def test_the_card_effect_first_then_the_subcommittee() -> None:
    state = _steersman_visit(DISPLAY)
    assert {("choose_subcommittee", ""), ("decline_subcommittee", "")} <= _options(
        state
    )
    state = _act(state, "resolve_agent_card_effect", effect="cards")
    assert state.players[0].hand == (DAGGER,)
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="readiness")
    assert state.scouts_subcommittee_members == (("readiness", 0),)
    # Only Steersman's recall is left, with no other Agent to bring back: it
    # waits for the explicit turn end (OQ-057).
    assert _options(state) == {("finish_agent_turn", "")}


def _waiting_rows(state: GameState) -> dict[str, dict[str, Any]]:
    """The seat's greyed-out rows (``display.unavailable``), by key."""
    from dune_imperium.display.unavailable import unavailable_choices

    found = unavailable_choices(state, 0, ENGINE.legal_actions(state, 0))
    if found is None:
        return {}
    rows = found["rows"]
    assert isinstance(rows, list)
    return {str(row["key"]): row for row in rows}


def test_a_subcommittee_becomes_choosable_once_the_turn_pays_for_it() -> None:
    """Appropriations discards a card from hand; the seat played its only
    card, so nothing is joinable until Steersman's draw fills the hand. The
    greyed-out row says why meanwhile (``display.unavailable``)."""
    state = _steersman_visit(("appropriations", "oversight", "leverage"))
    assert state.players[0].hand == ()
    offered = _options(state)
    assert ("choose_subcommittee", "") not in offered
    assert ("decline_subcommittee", "") in offered
    assert _waiting_rows(state)["waiting:choose_subcommittee"]["code"] == (
        "subcommittee"
    )
    state = _act(state, "resolve_agent_card_effect", effect="cards")
    assert ("choose_subcommittee", "") in _options(state)
    assert "waiting:choose_subcommittee" not in _waiting_rows(state)
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="appropriations")
    state = _act(state, "scouts_discard", card_id=DAGGER)
    assert state.players[0].resources.water == 2
    assert _options(state) == {("finish_agent_turn", "")}


SARDAUKAR_COORDINATION = "imperium:sardaukar_coordination:0"


def _coordination_visit() -> GameState:
    """Sardaukar Coordination lets this turn's recruits deploy, so the High
    Council visit keeps a deployment window open to the explicit turn end."""

    owner = _owner(
        hand=(SARDAUKAR_COORDINATION,),
        resources=Resources(solari=5, spice=0, water=1),
    )
    state = _state(owner, current_conflict_ids=(CONFLICTS[0].card.card_id,))
    return _visit_high_council(state, SARDAUKAR_COORDINATION)


def test_the_turn_cannot_end_while_the_choice_is_pending() -> None:
    """The turn ends only once the choice is made or declined: the explicit
    turn end waits like it does for every other pending effect."""
    state = _coordination_visit()
    assert _options(state) == {
        ("choose_subcommittee", ""),
        ("decline_subcommittee", ""),
    }
    declined = _act(state, "decline_subcommittee")
    assert _options(declined) == {("finish_agent_turn", "")}


def test_a_readiness_troop_joins_the_still_open_turn() -> None:
    """Chosen inside the turn, the line's recruit is this turn's recruit
    [Main p. 10] and may deploy with the turn's deployment."""
    state = _choose(_coordination_visit())
    state = _act(state, "join_subcommittee", subcommittee_id="readiness")
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert ("deploy_troops", "1") in _options(state)
    state = _act(state, "deploy_troops", count=1)
    assert state.players[0].troops_conflict == 1


def _seat_then_into_the_fray(extra_locations: tuple[str, ...]) -> GameState:
    """Duncan Idaho's Signet Ring at the High Council: the seat is taken
    first, then Into the Fray moves the seat-taker into the Conflict."""
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
    state = _act(state, "resolve_board_effect", effect="high_council")
    state = _act(state, "deploy_leader_agent")
    assert state.players[0].agent_in_conflict == 1
    return state


def test_into_the_fray_after_the_seat_still_excludes_the_seat_taker() -> None:
    """OQ-068, OQ-075: "not the Agent you sent during this turn" [Main p. 20].
    The Agent that took the seat is worked out when the list opens, so one
    moved into the Conflict after the seat but before the choice is still
    not "another Agent"."""
    alone = _choose(_seat_then_into_the_fray(()))
    assert ("join_subcommittee", "contingencies") not in _options(alone)
    with_other = _choose(_seat_then_into_the_fray(("imperial_basin",)))
    state = _act(with_other, "join_subcommittee", subcommittee_id="contingencies")
    state = _act(state, "scouts_trash_intrigue", card_id="intrigue:9")
    assert _options(state) == {("scouts_recall_agent", "imperial_basin")}


def _corrinth_seat(**owner_fields: Any) -> GameState:
    """Reveal Corrinth City and take the seat: the Reveal goes on."""
    owner = _owner(hand=(CORRINTH, DAGGER), **owner_fields)
    state = _act(_state(owner), "reveal_turn")
    state = _act(state, "take_high_council_from_reveal")
    assert state.decision_stack[-1].kind == FrameKind.REVEAL
    return state


def test_the_corrinth_seat_chooses_during_the_rest_of_its_reveal() -> None:
    state = _corrinth_seat()
    offered = _options(state)
    assert {("choose_subcommittee", ""), ("decline_subcommittee", "")} <= offered
    # The Reveal cannot end with the choice unanswered (OQ-076).
    assert ("finish_reveal", "") not in offered
    state = _act(_choose(state), "join_subcommittee", subcommittee_id="readiness")
    assert state.scouts_subcommittee_members == (("readiness", 0),)
    assert not state.scouts_subcommittee_offers
    assert state.decision_stack[-1].kind == FrameKind.REVEAL
    offered = _options(state)
    assert ("choose_subcommittee", "") not in offered
    assert ("decline_subcommittee", "") not in offered


def test_the_corrinth_reveal_cannot_end_before_the_choice_is_answered() -> None:
    """User rulings 2026-09-30 (OQ-076): nothing lapses unasked; the seat
    joins or declines before its Reveal ends, as at the High Council board
    space, and declining is always there, so the Reveal never gets stuck."""
    state = _corrinth_seat()
    legal = {a.action_id for a in ENGINE.legal_actions(state, 0)}
    assert "finish_reveal" not in legal
    assert "decline_subcommittee" in legal


def test_the_corrinth_offer_can_be_declined_before_the_reveal_ends() -> None:
    state = _act(_corrinth_seat(), "decline_subcommittee")
    assert not state.scouts_subcommittee_offers
    assert state.decision_stack[-1].kind == FrameKind.REVEAL
    assert _options(state) == {("finish_reveal", "")}
    finished = _act(state, "finish_reveal")
    kinds = [e.kind for e in finished.event_log]
    assert kinds.count("scouts_subcommittee_declined") == 1


def test_the_choice_joins_the_pending_icons_once() -> None:
    """The choice is an effect of the visit, not a printed icon: it joins
    ``pending_board_icons`` only (so a repeat of the printed effects never
    re-arms it) and cannot be queued twice (``effects.add_board_icon``)."""
    from dune_imperium.rules.effects import add_board_icon
    from dune_imperium.rules.scouts_offers import BOARD_ICON_SUBCOMMITTEE

    context: dict[str, bool | int | str] = {
        "pending_board_icons": "",
        "pending_board_effect": False,
    }
    add_board_icon(context, BOARD_ICON_SUBCOMMITTEE)
    assert context == {
        "pending_board_icons": BOARD_ICON_SUBCOMMITTEE,
        "pending_board_effect": True,
    }
    with pytest.raises(ValueError, match="already pending"):
        add_board_icon(context, BOARD_ICON_SUBCOMMITTEE)


def test_the_heuristic_joins_a_subcommittee_and_ends_its_turn() -> None:
    """The heuristic chooses when a subcommittee can be joined, never loops,
    and a random pick always terminates: the list always holds the decline."""
    from dune_imperium.agents import HeuristicAgent
    from dune_imperium.core.observation import observe_state

    state = _act(
        _state(_owner()), "agent_turn", card_id=DAGGER, space_id="high_council"
    )
    agent = HeuristicAgent(seed=5)
    steps = 0
    while state.decision_stack[-1].kind != FrameKind.TURN:
        legal = ENGINE.legal_actions(state, 0)
        action = agent.choose_action(observe_state(state, 0), legal)
        state = ENGINE.apply(state, action, legal_actions=legal).state
        steps += 1
        assert steps < 20
    assert [seat for _, seat in state.scouts_subcommittee_members] == [0]
    for seed in range(8):
        rng = random.Random(seed)
        state = _visit_high_council(_state(_owner()))
        steps = 0
        while state.decision_stack[-1].kind != FrameKind.TURN:
            top = state.decision_stack[-1].decision
            assert isinstance(top, PlayerDecision)
            legal = ENGINE.legal_actions(state, top.owner)
            state = ENGINE.apply(state, rng.choice(legal), legal_actions=legal).state
            steps += 1
            assert steps < 20
