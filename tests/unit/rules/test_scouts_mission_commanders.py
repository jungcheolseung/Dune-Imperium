"""Arrakeen Scouts with Bloodlines: a garrison Sardaukar Commander may stand in
for the troop Send for Aid and Genetic Research move (OQ-166; cloud engine
review finding 3).

The ruling (project convention, user 2026-11-02, "가 로 하고"): "Commander는
Conflict에서 strength 2인 "troop"이다. troop을 대상으로 하는 효과(예: Go to
Ground의 retreat)는 Commander에도 적용된다." [Bloodlines p. 4] -- the
unification OQ-105 made for the troop-losing costs ("3은 그럼 통일해야지.
지휘관도 낼 수 있게 해야지"). The app's Scouts text says only "troop" and never
mentions Commanders: it is a companion that does not track them.

- A seat whose garrison holds a Commander may send it; with a troop and a
  Commander there it picks which; one with only a Commander may join.
- The parked Commander is the seat's own piece, in neither its supply nor its
  garrison, like a parked troop (OQ-077 (a)).
- Its visit puts it into the Conflict at once, a unit deployed this turn
  (OQ-077 note 2026-11-02); Send for Aid's "recruit" is its own piece
  re-entering (OQ-077 (d)). It returns to the supply at the Combat's
  clean-up like any Commander.
"""

from dataclasses import replace

from tests.unit.rules import test_scouts_missions as uprising
from tests.unit.rules import test_scouts_original_missions as original

from dune_imperium import RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    encode_player_view,
    segment_slice,
)
from dune_imperium.core.observation import observe_state
from dune_imperium.core.state import GameState, check_game_state
from dune_imperium.display.scouts import scouts_choice_lines
from dune_imperium.rules.frames import COMMANDERS_RECRUITED_KEY, FrameKind
from dune_imperium.simulation.invariants import CardCensus

BLOODLINES = uprising.BLOODLINES


def _with_garrison(state: GameState, troops: int, commanders: int) -> GameState:
    seat = state.players[0]
    seat = replace(
        seat,
        troops_garrison=troops,
        troops_supply=seat.troops_supply + seat.troops_garrison - troops,
        commanders_garrison=commanders,
    )
    return replace(state, players=(seat, *state.players[1:]))


def _send_for_aid(troops: int, commanders: int) -> GameState:
    base = _with_garrison(uprising._base(BLOODLINES), troops, commanders)
    return uprising._reveal(base, "send_for_aid")


def _targets(engine: object, state: GameState) -> list[object]:
    return [
        dict(action.arguments)["target"]
        for action in engine.whole_actions(state, 0)  # type: ignore[attr-defined]
        if action.action_id == "scouts_join_mission"
    ]


def _lines(state: GameState) -> list[tuple[object, object, object]]:
    info = scouts_choice_lines(state, 0, uprising.ENGINE.whole_actions(state, 0))
    assert info is not None
    lines = info["lines"]
    assert isinstance(lines, list)
    return [(line["key"], line["enabled"], line.get("reason")) for line in lines]


def test_a_garrison_commander_alone_may_join_send_for_aid() -> None:
    state = _send_for_aid(troops=0, commanders=1)
    assert uprising._owner(state) == 0
    assert _targets(uprising.ENGINE, state) == ["commander"]
    census = CardCensus.from_state(state).commanders
    joined = uprising._answer(state, {0: "commander"})
    seat = joined.players[0]
    assert (seat.commanders_garrison, seat.commanders_parked) == (0, 1)
    assert seat.commanders_supply == state.players[0].commanders_supply
    assert joined.scouts_parked_commanders == (("send_for_aid", 0, "gather_support"),)
    assert joined.scouts_parked == ()
    assert ("send_for_aid", "gather_support", "water", 1, 0) in joined.scouts_goods
    # The seven Commanders are still all counted [Bloodlines p. 3].
    assert CardCensus.from_state(joined).commanders == census
    check_game_state(joined)

    water = joined.players[0].resources.water
    visited = uprising._visit(uprising._turn_for(joined), "gather_support")
    seat = visited.players[0]
    assert (seat.commanders_parked, seat.commanders_conflict) == (0, 1)
    assert seat.commanders_garrison == 0
    assert seat.resources.water == water + 1
    # A unit deployed this turn (OQ-077 note 2026-11-02).
    assert (seat.units_deployed_turn, seat.units_deployed_peak) == (1, 1)
    assert visited.scouts_parked_commanders == ()
    (event,) = (e for e in visited.event_log if e.kind == "scouts_mission_commander")
    assert dict(event.payload)["to"] == "conflict"


def test_a_seat_with_a_troop_and_a_commander_picks_which_to_send() -> None:
    state = _send_for_aid(troops=2, commanders=1)
    assert _targets(uprising.ENGINE, state) == ["", "commander"]
    assert [(key, enabled) for key, enabled, _ in _lines(state)] == [
        ("target:", True),
        ("target:commander", True),
    ]
    by_troop = uprising._answer(state, {0: ""}).players[0]
    assert (by_troop.troops_garrison, by_troop.troops_parked) == (1, 1)
    assert (by_troop.commanders_garrison, by_troop.commanders_parked) == (1, 0)
    by_commander = uprising._answer(state, {0: "commander"}).players[0]
    assert (by_commander.troops_garrison, by_commander.troops_parked) == (2, 0)
    assert (by_commander.commanders_garrison, by_commander.commanders_parked) == (0, 1)


def test_without_a_garrison_commander_the_commander_way_is_greyed() -> None:
    state = _send_for_aid(troops=2, commanders=0)
    assert _targets(uprising.ENGINE, state) == [""]
    troop, commander = _lines(state)
    assert troop[1] and not commander[1]
    assert commander[2] == "Needs 1 Sardaukar Commander in your garrison (you have 0)"


def test_without_bloodlines_send_for_aid_offers_the_troop_only() -> None:
    state = uprising._reveal(uprising._base(), "send_for_aid")
    assert _targets(uprising.ENGINE, state) == [""]
    assert [key for key, _, _ in _lines(state)] == ["target:"]


def test_the_parked_commander_is_public_in_every_seats_view() -> None:
    joined = uprising._answer(_send_for_aid(troops=0, commanders=1), {0: "commander"})
    for seat in range(4):
        view = observe_state(joined, seat)
        assert view.scouts_parked_commanders == (("send_for_aid", 0, "gather_support"),)
        values = encode_player_view(view)
        column = values[segment_slice("scouts_parked_commanders")]
        # Send for Aid's row, the parking seat relative to the observer.
        assert sum(column) == 1
        assert column[(0 - seat) % 4] == 1


def test_a_turn_that_cannot_deploy_keeps_the_commander_in_the_garrison() -> None:
    # "Units can't be deployed to the Conflict this turn." [Shaddam Corrino IV
    # card] [Main p. 17]: as the troop (OQ-130), the Commander goes to the
    # garrison, a Commander recruited this turn (OQ-077 (b), OQ-070).
    joined = uprising._answer(_send_for_aid(troops=0, commanders=1), {0: "commander"})
    turn = uprising._turn_for(joined)
    banned = replace(
        turn,
        decision_stack=(
            replace(
                turn.decision_stack[-1], context=(("units_deploy_blocked", True),)
            ),
        ),
    )
    visited = uprising._visit(banned, "gather_support")
    seat = visited.players[0]
    assert (seat.commanders_conflict, seat.commanders_garrison) == (0, 1)
    assert seat.units_deployed_turn == 0
    frame = visited.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    assert dict(frame.context)[COMMANDERS_RECRUITED_KEY] == 1


def _original_bloodlines(troops: int, commanders: int) -> GameState:
    base = original._base(original.ORIGINAL_BLOODLINES)
    seat = replace(
        base.players[0],
        troops_garrison=troops,
        troops_supply=base.players[0].troops_supply
        + base.players[0].troops_garrison
        - troops,
        commanders_garrison=commanders,
    )
    return original._reveal(
        replace(base, players=(seat, *base.players[1:])), "genetic_research"
    )


def test_genetic_research_takes_a_garrison_commander_on_the_original_board() -> None:
    state = _original_bloodlines(troops=0, commanders=1)
    assert _targets(original.ENGINE, state) == ["commander"]
    joined = original._answer(state, {0: "commander"})
    seat = joined.players[0]
    assert (seat.commanders_garrison, seat.commanders_parked) == (0, 1)
    assert joined.scouts_parked_commanders == (
        ("genetic_research", 0, "selective_breeding"),
    )
    solari = seat.resources.solari
    visited = original._visit(joined, "selective_breeding")
    seat = visited.players[0]
    assert (seat.commanders_parked, seat.commanders_conflict) == (0, 1)
    assert seat.resources.solari == solari + 2
    assert seat.units_deployed_turn == 1
    assert visited.scouts_parked_commanders == ()


def test_the_commander_way_is_in_the_original_bloodlines_scouts_catalog() -> None:
    """Genetic Research brings the Commander way in to the original game's
    Bloodlines Scouts catalogs (Prison Planet held it on Uprising's only):
    every action offered for it encodes."""

    from dune_imperium.adapters.action_codec import _scouts_templates

    state = _original_bloodlines(troops=1, commanders=1)
    codec = ActionCodec(original.ORIGINAL_BLOODLINES)
    legal = original.ENGINE.legal_actions(state, 0)
    assert len(legal) == 3
    for action in legal:
        assert codec.decode(codec.encode(action), 0) == action

    def targets(config: RulesetConfig) -> set[object]:
        return {
            dict(template.arguments).get("target")
            for template in _scouts_templates(config)
            if template.action_id == "scouts_join_mission"
        }

    assert "commander" in targets(original.ORIGINAL_BLOODLINES)
    assert "commander" not in targets(original.ORIGINAL)
    # The Uprising + Immortality pool trades Prison Planet for Coordinate With
    # The Emperor (docs/rules/arrakeen-scouts.md 5): Send for Aid brings the
    # way in there.
    assert "commander" in targets(
        RulesetConfig(arrakeen_scouts=True, bloodlines=True, immortality=True)
    )
    # Uprising with Rise of Ix drops Send for Aid; Prison Planet keeps the
    # way in there (OQ-105).
    assert "commander" in targets(
        RulesetConfig(arrakeen_scouts=True, bloodlines=True, rise_of_ix=True)
    )
