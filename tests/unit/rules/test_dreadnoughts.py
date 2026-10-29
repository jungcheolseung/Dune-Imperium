"""Rise of Ix dreadnoughts in the Conflict and on Control spaces (stage P4b-1a).

Rules: docs/rules/rise-of-ix.md 6, ``[Rise of Ix p. 6]`` ``[FAQ p. 2]`` and
OQ-121 (rulings 1 and 2). Setup refuses ``rise_of_ix`` until stage P4c, so
every state here is built by hand: an original game's opening state
(``UprisingRulesEngine().reset``) with its config switched to
``rise_of_ix=True``, moved into the phase a test needs, and its seats given
the units by ``dataclasses.replace`` (the state checks accept them). The
winner's choice of a Control space for its dreadnought (stage P4b-1b) runs
through the engine from the Combat Intrigue passes; commissioning and
deploying a dreadnought (P4b-2) are a later stage, so the tests set
``dreadnought_control`` and the seat counts directly.
"""

from dataclasses import replace
from typing import Any

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec, ActionTemplate
from dune_imperium.agents import HeuristicAgent
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.app_ai.agent import AppAIAgent
from dune_imperium.agents.random_agent import RandomAgent
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import DomainAction, GamePhase, GameState, PlayerState
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import _apply_control_visit_bonus
from dune_imperium.rules.combat import (
    CombatReward,
    RewardRank,
    _dreadnought_control_frame,
    _reward_window,
    begin_combat_intrigue,
    conflict_end_loss,
    finish_combat,
    legacy_combat_reward_icon,
    offer_conflict_end_triggers,
)
from dune_imperium.rules.dreadnoughts import end_combat_dreadnoughts, space_controller
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.pauses import pause_is_pending
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


def _holding_both(state: GameState) -> GameState:
    """``state`` with each seat's supply holding the dreadnoughts it has not
    placed elsewhere: setup gives every seat its two [Rise of Ix p. 3], and
    the sweep's invariants count both (these states are built by hand)."""

    on_spaces = [seat for _, seat, _ in state.dreadnought_control]
    return replace(
        state,
        players=tuple(
            replace(
                player,
                dreadnoughts_supply=2
                - player.dreadnoughts_garrison
                - player.dreadnoughts_conflict
                - on_spaces.count(player.player_id),
            )
            for player in state.players
        ),
    )


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
    check_state_invariants(
        _holding_both(finished), CardCensus.from_state(_original())
    )


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
    check_state_invariants(
        _holding_both(finished.state), CardCensus.from_state(_original())
    )


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


# --- The winner sets a dreadnought on a Control space (stage P4b-1b) ---------

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
CHOICE = FrameKind.DREADNOUGHT_CONTROL_CHOICE
WINDOW = FrameKind.COMBAT_REWARD_ICONS


def _pass(seat: int) -> DomainAction:
    return DomainAction(action_id="pass_combat_intrigue", actor=seat)


def _icon(kind: str, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="resolve_combat_reward_icon",
        actor=actor,
        arguments=(("effect", kind),),
    )


def _place(space_id: str, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="place_combat_reward_dreadnought",
        actor=actor,
        arguments=(("space_id", space_id),),
    )


def _wholes(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    return ENGINE.whole_actions(state, seat)


def _icons(state: GameState) -> list[str]:
    assert state.decision_stack[-1].kind == WINDOW
    text = str(dict(state.decision_stack[-1].context)["icons"])
    return text.split(",") if text else []


def _fight(
    units: dict[int, tuple[int, int]],
    *,
    control: tuple[tuple[str, int, bool], ...] = (),
    markers: dict[int, tuple[str, ...]] | None = None,
    conflict_id: str = "skirmish_a",
) -> GameState:
    """The Combat of ``units`` (seat -> troops, dreadnoughts in the Conflict)
    through its Combat Intrigue passes, to the first recipient's window."""

    state = _combat(
        intrigue_complete=False, dreadnought_control=control, conflict_id=conflict_id
    )
    for seat, (troops, dreadnoughts) in units.items():
        state = _in_conflict(state, seat, troops=troops, dreadnoughts=dreadnoughts)
    for seat, spaces in (markers or {}).items():
        state = _seat(state, seat, control_space_ids=spaces)
    state = begin_combat_intrigue(state).state
    while state.decision_stack and state.decision_stack[-1].kind == (
        FrameKind.COMBAT_INTRIGUE
    ):
        owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        state = apply_whole(ENGINE, state, _pass(owner)).state
    return state


def _winner_window(
    *,
    dreadnoughts: int = 1,
    control: tuple[tuple[str, int, bool], ...] = (),
    markers: dict[int, tuple[str, ...]] | None = None,
) -> GameState:
    """Seat 0 wins with ``dreadnoughts`` and a troop over seat 1's dreadnought;
    its window is on top."""

    state = _fight({0: (1, dreadnoughts), 1: (0, 1)}, control=control, markers=markers)
    assert state.decision_stack[-1].kind == WINDOW
    assert dict(state.decision_stack[-1].context)["rank"] == 1
    return state


def _continue(state: GameState) -> GameState:
    """Answer the pause between two recipients' windows."""

    assert pause_is_pending(state)
    return ENGINE.apply(state, pause_outcome(state)).state


def _play_out(state: GameState) -> tuple[GameState, list[str]]:
    """Answer every pause and every window row (the older engine's order)
    until the Combat phase is over; the kinds of the events on the way."""

    kinds: list[str] = []
    for _ in range(60):
        if state.phase is not GamePhase.COMBAT:
            return state, kinds
        if pause_is_pending(state):
            step = ENGINE.apply(state, pause_outcome(state))
        else:
            owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
            answer = legacy_combat_reward_icon(state, owner)
            assert answer is not None, state.decision_stack[-1].kind
            step = apply_whole(ENGINE, state, answer)
        state = step.state
        kinds.extend(event.kind for event in step.events)
    raise AssertionError("the Combat did not end")


def test_the_winner_with_a_dreadnought_has_one_row_to_set_it_on_a_space() -> None:
    """ "dreadnought가 하나라도 있는 Conflict를 이기면 Arrakeen·Carthag·Imperial
    Basin 가운데 dreadnought가 없는 칸 하나를 골라(의무, "must") 그 깃발에
    dreadnought를 놓는다" [Rise of Ix p. 6] and "지배 고르기의 자리 ... 승자의
    창(1위 보상과 같은 창)의 의무 줄" (OQ-121 ruling 6 (1)): the sole winner's
    window holds a ``dreadnought_control`` row among its icons, before the
    closing row, whether one or two dreadnoughts fought."""

    for dreadnoughts in (1, 2):
        state = _winner_window(dreadnoughts=dreadnoughts)

        assert _icons(state) == [
            "victory_points",
            "dreadnought_control",
            "winning_intrigue",
        ]
        assert _wholes(state) == (
            _icon("victory_points"),
            _icon("dreadnought_control"),
        )


def test_the_row_is_one_a_win_whatever_the_sandworm_multiplier() -> None:
    """ "dreadnought가 하나라도 있는 Conflict를 이기면 ... 칸 하나를 골라"
    [Rise of Ix p. 6]: one choice a win, not one a dreadnought and not doubled
    by a sandworm (a "double" reward, [Main p. 14]), since only one
    dreadnought goes to a space."""

    state = _in_conflict(_combat(), 0, dreadnoughts=2)
    for multiplier in (1, 2):
        frame = _reward_window(
            state, "skirmish_a", CombatReward(0, RewardRank.FIRST, multiplier)
        )
        icons = str(dict(frame.context)["icons"]).split(",")
        assert icons.count("dreadnought_control") == 1
        assert (
            str(dict(frame.context)["printed"]).split(",").count("dreadnought_control")
            == 1
        )


def test_no_row_without_a_sole_win_with_a_dreadnought_in_a_rise_of_ix_game() -> None:
    """ "이기지 못하면(공동 1위 포함)" [Rise of Ix p. 6] (OQ-121 ruling 2) and
    "dreadnought가 하나라도 있는 Conflict를 이기면 ..." [Rise of Ix p. 6]: a
    tie for first (second place's reward, [Main p. 14]), a winner with no
    dreadnought in the Conflict, a second or third place with one, and a game
    without the Rise of Ix option get no row."""

    # A tie for first: both take second place's reward.
    tied = _fight({0: (0, 1), 1: (0, 1)})
    assert dict(tied.decision_stack[-1].context)["rank"] == 2
    assert "dreadnought_control" not in _icons(tied)

    # A sole winner with troops only.
    troops = _fight({0: (2, 0), 1: (0, 1)})
    assert dict(troops.decision_stack[-1].context)["rank"] == 1
    assert "dreadnought_control" not in _icons(troops)
    # The second place, a dreadnought alone, gets none either: its window is
    # the next one.
    second = _continue(_close(troops))
    assert dict(second.decision_stack[-1].context)["rank"] == 2
    assert second.players[1].dreadnoughts_conflict == 1
    assert "dreadnought_control" not in _icons(second)

    # Second and third place directly.
    state = _in_conflict(_combat(), 0, dreadnoughts=1)
    for rank in (RewardRank.SECOND, RewardRank.THIRD):
        frame = _reward_window(state, "skirmish_a", CombatReward(0, rank))
        assert "dreadnought_control" not in str(dict(frame.context)["icons"])

    # Without the option, whatever a seat holds.
    plain = _in_conflict(_combat(_original(rise_of_ix=False)), 0, dreadnoughts=1)
    frame = _reward_window(plain, "skirmish_a", CombatReward(0, RewardRank.FIRST))
    assert "dreadnought_control" not in str(dict(frame.context)["icons"])


def _close(state: GameState) -> GameState:
    """Resolve the window on top row by row, to the pause after it."""

    while state.decision_stack[-1].kind == WINDOW:
        owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        answer = legacy_combat_reward_icon(state, owner)
        assert answer is not None
        state = apply_whole(ENGINE, state, answer).state
    return state


def test_the_choice_offers_the_spaces_without_a_dreadnought() -> None:
    """ "Arrakeen·Carthag·Imperial Basin 가운데 dreadnought가 없는 칸 하나"
    [Rise of Ix p. 6]: the winner's choice lists the base game's Control spaces
    holding no dreadnought, in board order, a Control marker or not; it is
    the winner's alone."""

    spaces = ("arrakeen", "carthag", "imperial_basin")
    assert tuple(content_for(IX).control_visit_bonuses) == spaces
    for held in (None, *spaces):
        control = () if held is None else ((held, 2, True),)
        state = _winner_window(control=control, markers={3: ("carthag",)})
        state = apply_whole(ENGINE, state, _icon("dreadnought_control")).state

        assert state.decision_stack[-1].kind == CHOICE
        assert _wholes(state) == tuple(
            _place(space) for space in spaces if space != held
        )
        assert _wholes(state, 1) == ()
        assert _wholes(state, 3) == ()


def test_the_choice_is_a_bug_when_every_space_holds_a_dreadnought() -> None:
    """ "한 번에 locations 위에 있는 dreadnought는 둘을 넘지 않는다(놓이는 것
    하나 + 다음 Combat 끝에 떠나는 것 하나)" (docs/rules/rise-of-ix.md 6): a
    third dreadnought on a space cannot happen, so no space left to choose
    is an error, not an empty choice."""

    full = replace(
        _combat(),
        dreadnought_control=(
            ("arrakeen", 1, True),
            ("carthag", 2, True),
            ("imperial_basin", 3, False),
        ),
    )
    with pytest.raises(RuntimeError, match="every Control space holds"):
        _dreadnought_control_frame(full, 0, 0)


def test_the_rulebook_example_seat_by_seat() -> None:
    """ "지난 라운드의 dreadnought가 아직 Arrakeen에 있어 새 승자는 Imperial
    Basin을 골랐고, 그 뒤 "as the Combat phase ends" 지난 dreadnought가 garrison
    으로 갔다" [Rise of Ix p. 6] (OQ-121 tests: "Frida는 Arrakeen을 고르지 못하고
    Imperial Basin에서 Ned의 marker를 덮는다. Ned의 dreadnought는 Combat 정리 때
    garrison으로 간다. Bodie의 dreadnought는 Combat 끝에 garrison으로 가고, Ned가
    Arrakeen 지배를 되찾는다."). Frida is seat 0, Ned 1, Bodie 2."""

    frida, ned, bodie = 0, 1, 2
    state = _fight(
        {frida: (1, 1), ned: (0, 1)},
        # Bodie's dreadnought from the last round, on Arrakeen over Ned's marker.
        control=(("arrakeen", bodie, True),),
        markers={ned: ("arrakeen", "imperial_basin")},
    )
    assert space_controller(state, "arrakeen") == bodie
    assert space_controller(state, "imperial_basin") == ned

    # Frida wins and sets her dreadnought: not on Arrakeen, which holds one.
    state = apply_whole(ENGINE, state, _icon("dreadnought_control")).state
    assert state.decision_stack[-1].kind == CHOICE
    assert _wholes(state, frida) == (_place("carthag"), _place("imperial_basin"))
    placed = apply_whole(ENGINE, state, _place("imperial_basin"))

    assert [event.kind for event in placed.events] == ["dreadnought_control_placed"]
    assert dict(placed.events[0].payload) == {
        "player": frida,
        "space_id": "imperial_basin",
    }
    state = placed.state
    assert state.players[frida].dreadnoughts_conflict == 0
    assert state.dreadnought_control == (
        ("arrakeen", bodie, True),
        ("imperial_basin", frida, False),
    )
    # Frida controls Imperial Basin now; Ned's marker under her dreadnought is
    # where it was.
    assert space_controller(state, "imperial_basin") == frida
    assert state.players[ned].control_space_ids == ("arrakeen", "imperial_basin")
    # Her window goes on with the rest of its rows, then Ned's second-place
    # window (no row) follows.
    assert state.decision_stack[-1].kind == WINDOW
    assert _icons(state) == ["victory_points", "winning_intrigue"]

    # Ned's dreadnought goes to his garrison in the cleanup, Bodie's as the
    # Combat phase ends, and Ned controls Arrakeen again; Frida's stays.
    state, kinds = _play_out(state)

    assert [seat.dreadnoughts_garrison for seat in state.players] == [0, 1, 1, 0]
    assert [seat.dreadnoughts_conflict for seat in state.players] == [0, 0, 0, 0]
    assert state.dreadnought_control == (("imperial_basin", frida, True),)
    assert space_controller(state, "arrakeen") == ned
    assert space_controller(state, "imperial_basin") == frida
    assert kinds.index("conflict_won") < kinds.index("combat_cleaned_up")
    assert kinds.count("dreadnought_returned") == 1
    assert kinds.index("combat_cleaned_up") < kinds.index("dreadnought_returned")
    assert "dreadnought_control_placed" not in kinds


def test_the_winner_with_two_dreadnoughts_sets_one_and_garrisons_the_other() -> None:
    """ "(If your second dreadnought was also in the Conflict, return it to your
    garrison.)" [Rise of Ix p. 6] ("두 번째 dreadnought도 Conflict에 있었으면
    garrison으로", docs/rules/rise-of-ix.md 6): the row sets one; the other stays
    in the Conflict and goes to the garrison at the cleanup, with the troops."""

    state = _winner_window(dreadnoughts=2)
    state = apply_whole(ENGINE, state, _icon("dreadnought_control")).state
    state = apply_whole(ENGINE, state, _place("carthag")).state

    assert state.players[0].dreadnoughts_conflict == 1
    assert state.players[0].dreadnoughts_garrison == 0
    assert state.dreadnought_control == (("carthag", 0, False),)

    state, _ = _play_out(state)

    winner = state.players[0]
    assert (winner.dreadnoughts_garrison, winner.dreadnoughts_conflict) == (1, 0)
    assert winner.dreadnoughts_supply == 0
    # The placed one stands on its space, leaving at the end of the next Combat.
    assert state.dreadnought_control == (("carthag", 0, True),)


def test_the_window_cannot_close_before_the_row_is_resolved() -> None:
    """ "의무, "must"" [Rise of Ix p. 6] and "안 내도 창이 닫힌다" (OQ-121
    ruling 6): the closing row comes last, and a mandatory row is no row to
    skip, so neither the window nor the choice offers a way past it."""

    state = _winner_window()
    assert _icon("winning_intrigue") not in _wholes(state)
    state = apply_whole(ENGINE, state, _icon("victory_points")).state
    # Only the dreadnought row is left, the close not yet offered.
    assert _wholes(state) == (_icon("dreadnought_control"),)

    chosen = apply_whole(ENGINE, state, _icon("dreadnought_control")).state
    # The choice sits on the window, which still holds the close; the choice
    # offers spaces alone, and the owner answers it before anything else.
    assert [frame.kind for frame in chosen.decision_stack[-2:]] == [WINDOW, CHOICE]
    assert "dreadnought_control" not in _icons(
        replace(chosen, decision_stack=chosen.decision_stack[:-1])
    )
    assert {action.action_id for action in _wholes(chosen)} == {
        "place_combat_reward_dreadnought"
    }

    placed = apply_whole(ENGINE, chosen, _place("carthag")).state
    assert _wholes(placed) == (_icon("winning_intrigue"),)
    closed = apply_whole(ENGINE, placed, _icon("winning_intrigue")).state
    assert closed.decision_stack[-1].kind == FrameKind.PAUSE


def test_the_winner_orders_the_row_with_the_printed_icon() -> None:
    """ "승자는 이 줄과 보상 아이콘, Windtraps 등 다른 줄의 순서를 고른다"
    (docs/rules/rise-of-ix.md 6, OQ-121 ruling 6 (1)): the row may be
    resolved before or after a printed icon, with the same result."""

    state = _winner_window()

    def run(first: str, second: str) -> GameState:
        current = state
        for kind in (first, second):
            current = apply_whole(ENGINE, current, _icon(kind)).state
            if current.decision_stack[-1].kind == CHOICE:
                current = apply_whole(ENGINE, current, _place("imperial_basin")).state
        return current

    before = run("dreadnought_control", "victory_points")
    after = run("victory_points", "dreadnought_control")

    for result in (before, after):
        assert result.players[0].victory_points == 1 + 1
        assert result.dreadnought_control == (("imperial_basin", 0, False),)
        assert _icons(result) == ["winning_intrigue"]
    assert before.players == after.players


def test_the_row_runs_through_the_engines_steps_and_the_codec() -> None:
    """ "그 깃발에 dreadnought를 놓는다" [Rise of Ix p. 6]: the engine offers the
    row and the space as step rows (the window picks an effect, then its
    target), each in the original game's Rise of Ix catalog, and an action
    the engine offers encodes and decodes to itself."""

    codec = ActionCodec(IX)
    state = _winner_window()

    def round_trip(actions: tuple[DomainAction, ...]) -> None:
        assert actions
        for action in actions:
            assert codec.decode(codec.encode(action), action.actor) == action

    window = ENGINE.legal_actions(state, 0)
    row = DomainAction(
        action_id="take",
        actor=0,
        arguments=(
            ("icon", "dreadnought_control"),
            ("printed", "skirmish_a"),
            ("source", "conflict"),
        ),
    )
    assert row in window
    round_trip(window)

    state = ENGINE.apply(state, row).state
    assert state.decision_stack[-1].kind == CHOICE
    spaces = ENGINE.legal_actions(state, 0)
    assert spaces == tuple(
        DomainAction(
            action_id="choose_space", actor=0, arguments=(("space_id", space),)
        )
        for space in ("arrakeen", "carthag", "imperial_basin")
    )
    round_trip(spaces)
    assert ENGINE.legal_actions(state, 1) == ()

    state = ENGINE.apply(state, spaces[1]).state
    assert state.dreadnought_control == (("carthag", 0, False),)
    assert state.players[0].dreadnoughts_conflict == 0
    assert state.decision_stack[-1].kind == WINDOW


def test_only_a_rise_of_ix_catalog_holds_the_row() -> None:
    """The row is Rise of Ix's ("dreadnought" [Rise of Ix p. 6]): its effect
    row, one for each Conflict that may be in play, is in the original game's
    Rise of Ix catalogs and in no other; the three spaces' target rows are
    the ones a space choice has everywhere."""

    ix = ActionCodec(IX).catalog
    conflicts = {c.card.card_id for c in content_for(IX).conflicts}
    rows = {t for t in ix if ("icon", "dreadnought_control") in t.arguments}
    assert rows == {
        ActionTemplate(
            "take",
            (
                ("icon", "dreadnought_control"),
                ("printed", conflict),
                ("source", "conflict"),
            ),
        )
        for conflict in conflicts
    }
    for space in ("arrakeen", "carthag", "imperial_basin"):
        assert ActionTemplate("choose_space", (("space_id", space),)) in ix

    for config in (
        RulesetConfig(base_game=BaseGame.IMPERIUM),
        RulesetConfig(base_game=BaseGame.IMPERIUM, promo_cards=True, epic_game=True),
        RulesetConfig(),
        RulesetConfig(bloodlines=True, immortality=True, epic_game=True),
    ):
        assert not any(
            ("icon", "dreadnought_control") in template.arguments
            or ("effect", "dreadnought_control") in template.arguments
            or template.action_id == "place_combat_reward_dreadnought"
            for template in ActionCodec(config).catalog
        ), config.identifier


def test_the_scripted_seats_answer_the_window_and_the_choice() -> None:
    """ "의무, "must"" [Rise of Ix p. 6]: a seat that cannot be asked for a
    space (the random, heuristic and app AI seats, which no Rise of Ix game
    reaches until stage P4c) still answers the winner's row and its choice
    with a legal action, and the Combat ends with its dreadnought set; the
    app AI answers the frame it does not mirror at random."""

    for agent in (RandomAgent(seed=1), HeuristicAgent(seed=1), AppAIAgent(seed=1)):
        state = _winner_window(dreadnoughts=2)
        for _ in range(40):
            if state.phase is not GamePhase.COMBAT:
                break
            if pause_is_pending(state):
                state = ENGINE.apply(state, pause_outcome(state)).state
                continue
            owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
            legal = ENGINE.legal_actions(state, owner)
            view = ENGINE.observe(state, owner)
            if isinstance(agent, RandomAgent):
                action = agent.choose_action(view, legal)
            else:
                action = agent.choose_action_with_state(state, view, legal)
            assert action in legal
            state = ENGINE.apply(state, action).state
        else:
            raise AssertionError(f"{type(agent).__name__} did not end the Combat")

        assert len(state.dreadnought_control) == 1
        (space_id, seat, leaving) = state.dreadnought_control[0]
        assert (seat, leaving) == (0, True)
        assert space_id in ("arrakeen", "carthag", "imperial_basin")
        assert state.players[0].dreadnoughts_garrison == 1
