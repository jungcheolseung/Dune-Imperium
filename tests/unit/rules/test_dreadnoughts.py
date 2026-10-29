"""Rise of Ix dreadnoughts in the Conflict and on Control spaces (stage P4b-1a).

Rules: docs/rules/rise-of-ix.md 6, ``[Rise of Ix p. 6]`` ``[FAQ p. 2]`` and
OQ-121 (rulings 1 and 2). Setup refuses ``rise_of_ix`` until stage P4c, so
every state here is built by hand: an original game's opening state
(``UprisingRulesEngine().reset``) with its config switched to
``rise_of_ix=True``, moved into the phase a test needs, and its seats given
the units by ``dataclasses.replace`` (the state checks accept them). Placing
a dreadnought on a Control space (P4b-1b) and commissioning and deploying one
(P4b-2) are later stages; the tests set ``dreadnought_control`` and the seat
counts directly.
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.core import GamePhase, GameState, PlayerState
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import _apply_control_visit_bonus
from dune_imperium.rules.combat import (
    begin_combat_intrigue,
    conflict_end_loss,
    finish_combat,
    offer_conflict_end_triggers,
)
from dune_imperium.rules.dreadnoughts import end_combat_dreadnoughts, space_controller
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.phases import (
    begin_round,
    legal_control_defense_actions,
    turn_frame,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn, legal_reveal_actions
from dune_imperium.rules.strength import (
    DREADNOUGHT_STRENGTH,
    dreadnought_strength,
    refresh_pre_reveal_strength,
    units_strength,
)
from dune_imperium.rules.units import retreat_units
from dune_imperium.simulation.invariants import CardCensus, check_state_invariants

ENGINE = UprisingRulesEngine()
DAGGER = "player:0:starter:dagger:0"


def _original(*, rise_of_ix: bool = True) -> GameState:
    """An original game's opening state, with or without Rise of Ix."""

    state = ENGINE.reset(RulesetConfig(base_game=BaseGame.IMPERIUM), 3)
    return replace(state, config=replace(state.config, rise_of_ix=rise_of_ix))


def _seat(state: GameState, seat: int, **changes: Any) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _pulled(state: GameState, conflict_id: str) -> GameState:
    """The state without ``conflict_id`` in the Conflict decks (a card is in
    one zone)."""

    return replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
    )


def _combat(
    state: GameState | None = None,
    *,
    dreadnought_control: tuple[tuple[str, int, bool], ...] = (),
    intrigue_complete: bool = True,
    conflict_id: str = "skirmish_a",
    round_number: int = 1,
) -> GameState:
    """The Combat phase with the rewards paid, the Conflict revealed and no
    unit anywhere; ``_in_conflict`` puts units and strength in."""

    state = _pulled(_original() if state is None else state, conflict_id)
    return replace(
        state,
        phase=GamePhase.COMBAT,
        round_number=round_number,
        first_player=0,
        decision_stack=(),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=intrigue_complete,
        combat_rewards_resolved=intrigue_complete,
        combat_end_triggers_offered=False,
        dreadnought_control=dreadnought_control,
    )


def _in_conflict(
    state: GameState, seat: int, *, troops: int = 0, dreadnoughts: int = 0
) -> GameState:
    """Move ``troops`` and ``dreadnoughts`` of ``seat`` into the Conflict, at
    the strength the engine keeps for them (2 a troop, 3 a dreadnought)."""

    owner = state.players[seat]
    return _seat(
        state,
        seat,
        troops_garrison=owner.troops_garrison - troops,
        troops_conflict=troops,
        dreadnoughts_conflict=dreadnoughts,
        combat_strength=2 * troops + 3 * dreadnoughts,
    )


def test_a_dreadnought_in_the_conflict_has_three_strength() -> None:
    """ "Conflict의 dreadnought 하나는 strength 3" [Rise of Ix p. 6]
    (docs/rules/rise-of-ix.md 6)."""

    alone = PlayerState(player_id=0, dreadnoughts_supply=1, dreadnoughts_conflict=1)
    both = PlayerState(player_id=0, dreadnoughts_conflict=2)

    assert DREADNOUGHT_STRENGTH == 3
    assert dreadnought_strength(alone) == 3
    assert alone.units_in_conflict == 1
    assert units_strength(alone) == 3
    assert units_strength(both) == 6


def test_a_dreadnought_adds_its_strength_to_the_troops() -> None:
    """ "Conflict의 dreadnought 하나는 strength 3" and a troop 2 [Rise of Ix
    p. 6] [Main p. 12]: the units' strength is the sum of the units in the
    Conflict."""

    seat = PlayerState(
        player_id=0, troops_supply=7, troops_conflict=2, dreadnoughts_conflict=1
    )
    troops_only = replace(seat, dreadnoughts_conflict=0)

    assert seat.units_in_conflict == 3
    assert units_strength(seat) == 7
    assert units_strength(troops_only) == 4


def test_the_running_strength_before_the_reveal_counts_the_dreadnought() -> None:
    """ "Conflict의 dreadnought 하나는 strength 3 ... troop이 없어도 dreadnought가
    있으면 strength가 0이 되지 않고" [Rise of Ix p. 6]: the strength the engine
    keeps current between steps (``refresh_pre_reveal_strength``) is the
    units' sum, a dreadnought alone included."""

    state = _original()
    state = replace(
        state, phase=GamePhase.PLAYER_TURNS, round_number=1, decision_stack=()
    )
    state = _seat(state, 1, dreadnoughts_conflict=1)
    state = _seat(
        state, 2, troops_garrison=1, troops_conflict=2, dreadnoughts_conflict=1
    )

    refreshed = refresh_pre_reveal_strength(RuleResult(state=state)).state

    assert [seat.combat_strength for seat in refreshed.players] == [0, 3, 7, 0]


def test_a_garrison_dreadnought_does_nothing() -> None:
    """ "garrison의 dreadnought는 아무것도 하지 않는다" [FAQ p. 2]
    (docs/rules/rise-of-ix.md 6): it is no unit in the Conflict, gives no
    strength and does not make its seat a Combat Intrigue participant."""

    garrison = PlayerState(player_id=0, dreadnoughts_garrison=2)
    assert garrison.units_in_conflict == 0
    assert units_strength(garrison) == 0

    state = _combat(intrigue_complete=False)
    state = _seat(state, 3, dreadnoughts_garrison=2)
    begun = begin_combat_intrigue(state)

    assert [event.kind for event in begun.events] == ["combat_intrigue_finished"]
    assert begun.state.combat_intrigue_complete


def test_a_dreadnought_alone_keeps_its_strength_after_the_troops_retreat() -> None:
    """ "troop이 없어도 dreadnought가 있으면 strength가 0이 되지 않고"
    [Rise of Ix p. 6]: the strength 0 rule ("마지막 unit이 제거되면 sword가 남아
    있어도 strength는 0이다" [Main p. 12]) is for a seat with no unit, and the
    dreadnought is one. Retreating the troops takes their 2 strength each and
    leaves the dreadnought's 3 and the swords."""

    state = _original()
    # Two troops, the dreadnought and two swords: 4 + 3 + 2.
    state = _seat(
        state,
        0,
        troops_garrison=1,
        troops_conflict=2,
        dreadnoughts_conflict=1,
        combat_strength=9,
    )

    retreated = retreat_units(state, 0, "round:1:test", troops=2).state.players[0]

    assert retreated.troops_conflict == 0
    assert retreated.troops_garrison == 3
    assert retreated.dreadnoughts_conflict == 1
    assert retreated.combat_strength == 5

    # The same retreat without the dreadnought leaves no unit: strength 0.
    bare = _seat(
        _original(), 0, troops_garrison=1, troops_conflict=2, combat_strength=6
    )
    assert (
        retreat_units(bare, 0, "round:1:test", troops=2)
        .state.players[0]
        .combat_strength
        == 0
    )


def test_swords_count_with_only_a_dreadnought_in_the_conflict() -> None:
    """ "sword가 세지고" with a dreadnought and no troop [Rise of Ix p. 6]
    [FAQ p. 2]: a Reveal turn's swords add to the dreadnought's 3, where a
    seat with no unit has strength 0 ("Conflict에 unit이 하나도 없으면 sword가
    있어도 strength는 0이다" [Main p. 12])."""

    def revealed_strength(dreadnoughts: int) -> int:
        state = _original()
        owner = state.players[0]
        state = replace(
            state,
            phase=GamePhase.PLAYER_TURNS,
            round_number=1,
            decision_stack=(turn_frame(1, 0),),
        )
        state = _seat(
            state,
            0,
            hand=(DAGGER,),
            deck=tuple(card for card in owner.deck if card != DAGGER),
            dreadnoughts_conflict=dreadnoughts,
        )
        action = legal_reveal_actions(state, 0)[0]
        return begin_reveal_turn(state, action).state.players[0].combat_strength

    assert revealed_strength(0) == 0
    # The Dagger's one sword and the dreadnought's three.
    assert revealed_strength(1) == 4


def test_a_dreadnought_alone_may_play_combat_intrigue() -> None:
    """ "troop이 없어도 dreadnought가 있으면 ... Combat Intrigue를 낼 수 있다"
    [Rise of Ix p. 6] [FAQ p. 2]: a seat with only a dreadnought in the
    Conflict gets Combat Intrigue priority."""

    state = _combat(intrigue_complete=False)
    state = _in_conflict(state, 3, dreadnoughts=1)

    begun = begin_combat_intrigue(state)

    assert [event.kind for event in begun.events] == ["combat_intrigue_started"]
    frame = begun.state.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_INTRIGUE
    assert dict(begun.events[0].payload) == {"player": 3}

    nobody = begin_combat_intrigue(_combat(intrigue_complete=False))
    assert [event.kind for event in nobody.events] == ["combat_intrigue_finished"]


def test_the_cleanup_sends_conflict_dreadnoughts_to_the_garrison() -> None:
    """ "끈질김. Combat이 해결되면 Conflict의 dreadnought는 supply로 가지 않는다
    ... garrison으로 — troop을 supply로 돌리는 정리 단계에서 함께" [Rise of Ix
    p. 6] (OQ-121 ruling 2): the winner's and the loser's dreadnoughts go to
    their garrisons while the troops go to the supply."""

    state = _combat()
    state = _in_conflict(state, 0, troops=2, dreadnoughts=1)
    state = _in_conflict(state, 1, dreadnoughts=1)

    offered = offer_conflict_end_triggers(state).state

    for seat in (0, 1):
        owner = offered.players[seat]
        assert owner.dreadnoughts_conflict == 0
        assert owner.dreadnoughts_garrison == 1
        # Never the supply.
        assert owner.dreadnoughts_supply == 0
    assert offered.players[0].troops_supply == 9 + 2
    assert offered.players[0].troops_conflict == 0

    finished = finish_combat(offered).state
    assert [seat.dreadnoughts_garrison for seat in finished.players] == [1, 1, 0, 0]
    assert [seat.combat_strength for seat in finished.players] == [0, 0, 0, 0]
    check_state_invariants(finished, CardCensus.from_state(_original()))


def test_a_dreadnought_is_not_a_lost_troop() -> None:
    """ "troops that return to your supply are considered 'lost.'" [FAQ p. 1]
    and a dreadnought goes to the garrison, not the supply [Rise of Ix p. 6]
    (OQ-121 ruling 2): the loss a Conflict-end window reads counts troops (and
    Commanders) only."""

    state = _combat()
    state = _in_conflict(state, 0, troops=2, dreadnoughts=1)
    state = _in_conflict(state, 1, dreadnoughts=2)

    assert conflict_end_loss(state, 0) == 2
    assert conflict_end_loss(state, 1) == 0


def test_the_cleanup_refuses_a_dreadnought_still_in_the_conflict() -> None:
    """ "Combat이 해결되면 Conflict의 dreadnought는 supply로 가지 않는다 ... garrison
    으로" [Rise of Ix p. 6]: the cleanup that follows the return of the units
    does not run with a dreadnought left in the Conflict."""

    state = _in_conflict(_combat(), 0, dreadnoughts=1)

    with pytest.raises(RuntimeError, match="units return before the cleanup"):
        finish_combat(state)


def test_a_dreadnought_controls_a_space_ahead_of_the_control_marker() -> None:
    """ "지배는 다음 Combat 단계 끝까지이고, 그때 dreadnought는 garrison으로
    돌아가며 덮였던 marker의 주인이 다시 지배한다" [Rise of Ix p. 6]: while the
    dreadnought is on the space it controls it, ahead of the marker it covers
    (the app's ``WormSpace::get_ControllingPlayer``, plan 17.5 item 5)."""

    state = _seat(_original(), 1, control_space_ids=("arrakeen", "carthag"))
    state = replace(state, dreadnought_control=(("arrakeen", 2, False),))

    assert space_controller(state, "arrakeen") == 2
    # The marker still controls the space that holds no dreadnought.
    assert space_controller(state, "carthag") == 1
    assert space_controller(state, "imperial_basin") is None

    # A dreadnought that leaves at this Combat phase's end still controls
    # the space until then.
    leaving = replace(state, dreadnought_control=(("arrakeen", 2, True),))
    assert space_controller(leaving, "arrakeen") == 2

    # A dreadnought on a space no marker covers controls it too.
    bare = replace(_original(), dreadnought_control=(("imperial_basin", 3, False),))
    assert space_controller(bare, "imperial_basin") == 3

    # Back in the garrison, the dreadnought no longer controls the space.
    returned = replace(state, dreadnought_control=())
    assert space_controller(returned, "arrakeen") == 1


def test_the_marker_controls_a_space_in_a_game_without_rise_of_ix() -> None:
    """The Control marker controls a space where no dreadnought is (the
    default: ``dreadnought_control`` is empty in a game without
    ``rise_of_ix``), for the Uprising game as for the original [Main p. 10]
    [DI p. 10]."""

    for state in (
        ENGINE.reset(RulesetConfig(), 3),
        _original(rise_of_ix=False),
    ):
        assert state.dreadnought_control == ()
        marked = _seat(state, 2, control_space_ids=("arrakeen",))
        assert space_controller(marked, "arrakeen") == 2
        assert space_controller(marked, "imperial_basin") is None


def test_the_visit_bonus_goes_to_the_dreadnoughts_owner() -> None:
    """ "그 칸의 Control 보너스 ... 를 받는다" [Rise of Ix p. 6]
    (docs/rules/rise-of-ix.md 6): the owner of the dreadnought on the space
    takes its visit bonus, not the owner of the marker under it."""

    state = _seat(_original(), 1, control_space_ids=("arrakeen",))
    state = replace(state, round_number=1)
    base = [seat.resources for seat in state.players]

    marker = _apply_control_visit_bonus(state, "arrakeen")
    covered = replace(state, dreadnought_control=(("arrakeen", 2, False),))
    covering, event = _apply_control_visit_bonus(covered, "arrakeen")

    # Without the dreadnought the marker's owner gets the bonus.
    assert marker[0].players[1].resources.solari == base[1].solari + 1
    # With it, the dreadnought's owner does and the marker's owner does not.
    assert covering.players[2].resources.solari == base[2].solari + 1
    assert covering.players[1].resources == base[1]
    assert event is not None
    assert dict(event.payload)["player"] == 2

    basin = replace(state, dreadnought_control=(("imperial_basin", 3, True),))
    gained, _ = _apply_control_visit_bonus(basin, "imperial_basin")
    assert gained.players[3].resources.spice == base[3].spice + 1


def _round_start(
    conflict_id: str, *, markers: dict[int, str], dreadnoughts: dict[str, int]
) -> GameState:
    state = _pulled(_original(), conflict_id)
    state = replace(
        state,
        phase=GamePhase.ROUND_START,
        decision_stack=(),
        conflict_deck=(conflict_id, *state.conflict_deck),
    )
    for seat, space_id in markers.items():
        state = _seat(state, seat, control_space_ids=(space_id,))
    return replace(
        state,
        dreadnought_control=tuple(
            (space_id, seat, False) for space_id, seat in dreadnoughts.items()
        ),
    )


def test_the_control_defense_goes_to_the_dreadnoughts_owner() -> None:
    """ "그 칸의 Control 보너스(... 방어 배치 troop 1)를 받는다" [Rise of Ix
    p. 6]: when the Conflict is revealed for a space a dreadnought controls,
    its owner may deploy the defending troop, not the owner of the covered
    marker."""

    siege = "imperium_siege_of_arrakeen"
    covered = begin_round(
        _round_start(siege, markers={1: "arrakeen"}, dreadnoughts={"arrakeen": 2})
    ).state
    frame = covered.decision_stack[-1]

    assert frame.kind == FrameKind.CONTROL_DEFENSE
    assert legal_control_defense_actions(covered, 2) != ()
    assert legal_control_defense_actions(covered, 1) == ()

    # A dreadnought on another space leaves the marker's owner the defender.
    elsewhere = begin_round(
        _round_start(siege, markers={1: "arrakeen"}, dreadnoughts={"carthag": 2})
    ).state
    assert elsewhere.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert legal_control_defense_actions(elsewhere, 1) != ()
    assert legal_control_defense_actions(elsewhere, 2) == ()

    # No marker and no dreadnought: nobody defends and the first turn opens.
    nobody = begin_round(_round_start(siege, markers={}, dreadnoughts={})).state
    assert nobody.decision_stack[-1].kind == FrameKind.TURN


def test_the_combat_phases_end_returns_the_leaving_dreadnoughts() -> None:
    """ "지배는 다음 Combat 단계 끝까지이고, 그때 dreadnought는 garrison으로
    돌아가며" [Rise of Ix p. 6] and "지난 지배 dreadnought는 Combat 단계의
    마지막 일로 garrison에 돌아간다" (OQ-121 ruling 1): at the Combat
    cleanup each dreadnought marked leaving goes back to its owner's garrison
    and leaves ``dreadnought_control``, and the one placed this phase turns
    leaving, to return at the end of the next Combat phase."""

    state = _combat(
        dreadnought_control=(("arrakeen", 1, True), ("carthag", 2, False)),
    )
    state = _seat(state, 1, dreadnoughts_garrison=1)

    finished = finish_combat(offer_conflict_end_triggers(state).state)

    assert finished.state.phase is GamePhase.MAKERS
    assert finished.state.dreadnought_control == (("carthag", 2, True),)
    assert [seat.dreadnoughts_garrison for seat in finished.state.players] == [
        0,
        2,
        0,
        0,
    ]
    # The cleanup's own event, then one event per dreadnought that went back.
    assert [event.kind for event in finished.events] == [
        "combat_cleaned_up",
        "dreadnought_returned",
    ]
    assert dict(finished.events[1].payload) == {"player": 1, "space_id": "arrakeen"}
    check_state_invariants(finished.state, CardCensus.from_state(_original()))


def test_a_dreadnought_stays_through_the_next_combat_phase() -> None:
    """ "지배는 다음 Combat 단계 끝까지이고" [Rise of Ix p. 6]: one placed
    during a Combat phase survives that phase's end, controlling its space,
    and goes back at the end of the next Combat phase."""

    state = _combat(dreadnought_control=(("imperial_basin", 3, False),))

    first = finish_combat(offer_conflict_end_triggers(state).state)

    assert first.state.dreadnought_control == (("imperial_basin", 3, True),)
    assert space_controller(first.state, "imperial_basin") == 3
    assert [event.kind for event in first.events] == ["combat_cleaned_up"]

    # The next round's Combat.
    second_start = _combat(
        first.state,
        dreadnought_control=first.state.dreadnought_control,
        conflict_id="skirmish_b",
        round_number=2,
    )
    second = finish_combat(offer_conflict_end_triggers(second_start).state)

    assert second.state.dreadnought_control == ()
    assert second.state.players[3].dreadnoughts_garrison == 1
    assert space_controller(second.state, "imperial_basin") is None
    assert dict(second.events[1].payload) == {
        "player": 3,
        "space_id": "imperial_basin",
    }


@pytest.mark.parametrize(
    "troops", [(3, 2, 1, 0), (3, 3, 1, 0), (0, 0, 0, 0)], ids=["won", "tied", "empty"]
)
def test_the_return_happens_whether_or_not_the_combat_has_a_winner(
    troops: tuple[int, int, int, int],
) -> None:
    """ "그 Combat에 승자가 없어도 돌아간다" (OQ-121 ruling 1,
    docs/rules/rise-of-ix.md 6): a Combat won by one seat, tied for first
    (no winner) or with nobody in the Conflict still ends with the leaving
    dreadnought home and the other one turned leaving."""

    state = _combat(
        dreadnought_control=(("arrakeen", 1, True), ("carthag", 2, False)),
    )
    for seat, count in enumerate(troops):
        if count:
            state = _in_conflict(state, seat, troops=count)

    finished = finish_combat(offer_conflict_end_triggers(state).state)

    assert finished.state.dreadnought_control == (("carthag", 2, True),)
    assert finished.state.players[1].dreadnoughts_garrison == 1
    assert finished.events[-1].kind == "dreadnought_returned"
    assert dict(finished.events[-1].payload) == {"player": 1, "space_id": "arrakeen"}


def test_each_returned_dreadnought_has_its_event() -> None:
    """ "지난 지배 dreadnought는 Combat 단계의 마지막 일로 garrison에 돌아간다"
    (OQ-121 ruling 1): two dreadnoughts leaving at once each return to their
    own owner's garrison, with one ``dreadnought_returned`` event apiece."""

    state = _combat(
        dreadnought_control=(("arrakeen", 0, True), ("imperial_basin", 3, True)),
    )

    ended = end_combat_dreadnoughts(state)

    assert ended.state.dreadnought_control == ()
    assert [seat.dreadnoughts_garrison for seat in ended.state.players] == [1, 0, 0, 1]
    assert [(event.kind, event.event_id) for event in ended.events] == [
        ("dreadnought_returned", "round:1:dreadnought_returned:arrakeen"),
        ("dreadnought_returned", "round:1:dreadnought_returned:imperial_basin"),
    ]
    assert [dict(event.payload) for event in ended.events] == [
        {"player": 0, "space_id": "arrakeen"},
        {"player": 3, "space_id": "imperial_basin"},
    ]


def test_a_game_without_rise_of_ix_is_left_as_it_was() -> None:
    """The original and the Uprising game have no dreadnought
    (``dreadnought_control`` empty, every seat count 0): the Combat cleanup
    changes nothing there and emits no dreadnought event, so their state and
    event log are what they were before stage P4b (docs/rules/rise-of-ix.md
    6 applies to the ``rise_of_ix`` option only)."""

    for base in (_original(rise_of_ix=False), ENGINE.reset(RulesetConfig(), 3)):
        state = _combat(base, conflict_id=base.conflict_deck[0])
        state = _in_conflict(state, 0, troops=2)
        # Two troops, 2 strength each.
        assert units_strength(state.players[0]) == 4

        finished = finish_combat(offer_conflict_end_triggers(state).state)

        assert [event.kind for event in finished.events] == ["combat_cleaned_up"]
        assert finished.state.dreadnought_control == ()
        for seat in finished.state.players:
            assert (
                seat.dreadnoughts_supply,
                seat.dreadnoughts_garrison,
                seat.dreadnoughts_conflict,
            ) == (0, 0, 0)
        assert end_combat_dreadnoughts(finished.state) == RuleResult(
            state=finished.state
        )
