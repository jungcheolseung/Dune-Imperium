"""Tests for the eleven Immortality Intrigue cards (effect DSL).

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md`` and ``docs/rules/immortality.md``
sections 3-4 [Immortality pp. 6-8].
"""

from dataclasses import replace

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.immortality.board import (
    RESEARCH_START_ID,
    TLEILAXU_TRACK_END,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    DeployFromGarrison,
    GenerateSpecimens,
    Research,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_ID,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import Transition
from dune_imperium.rules.action_shapes import Source, Verb
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.effect_interpreter import option_unplayable_reason
from dune_imperium.rules.effect_steps import STEP_SPECS, TARGET_SPECS, steps_for
from dune_imperium.rules.endgame import begin_endgame_intrigue
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue import (
    apply_intrigue_choice,
    apply_intrigue_play,
    legal_intrigue_choice_actions,
    legal_intrigue_play_actions,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn

IMMORTALITY = RulesetConfig(immortality=True)
CONTAMINATOR = "tleilaxu:contaminator:0"
SUBJECT = "tleilaxu:subject_x_137:0"
DECLINE_CONFLICT_END = DomainAction(action_id="decline_conflict_end_intrigue", actor=0)
FINISH_CONFLICT_END = DomainAction(action_id="finish_conflict_end_intrigue", actor=0)
DECLINE_ACQUIRE = DomainAction(action_id="decline_intrigue_tleilaxu", actor=0)
# Stage B3d-3: the rows a seat is shown for those refusals -- ``decline``
# naming the effect it answers (``of``) and the entity that printed it.
DECLINE_CONFLICT_END_ROW = DomainAction(
    "decline",
    0,
    (("of", "play"), ("printed", "conflict_end"), ("source", "intrigue")),
)
DECLINE_ACQUIRE_ROW = DomainAction(
    "decline",
    0,
    (("of", "acquire"), ("printed", "harvest_cells"), ("source", "intrigue")),
)


def _intrigue(card_id: str) -> str:
    return f"intrigue:{card_id}:0"


def _seat(seat: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": seat,
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _owner(**extra: object) -> PlayerState:
    deck = starting_deck_instance_ids(0, immortality=True)
    values: dict[str, object] = {"deck": deck[5:], "hand": deck[:5]}
    values.update(extra)
    return _seat(0, **values)


def _plot_state(owner: PlayerState, config: RulesetConfig = IMMORTALITY) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:4],
        tleilaxu_row=(CONTAMINATOR, SUBJECT),
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


def _fighter(troops: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "troops_supply": 12 - troops,
        "troops_garrison": 0,
        "troops_conflict": troops,
        "combat_strength": 2 * troops,
        "has_revealed": True,
    }
    values.update(extra)
    return _seat(0, **values)


def _combat_state(
    owner: PlayerState,
    *others: PlayerState,
    config: RulesetConfig = IMMORTALITY,
    first_player: int = 0,
) -> GameState:
    seats = [owner, *others]
    seats.extend(_seat(seat, has_revealed=True) for seat in range(len(seats), 4))
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=first_player,
        reveal_order=(0, 1, 2, 3),
        conflict_deck=(CONFLICTS[1].card.card_id,),
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        tleilaxu_row=(CONTAMINATOR, SUBJECT),
        tleilaxu_track_spice=2,
        players=tuple(seats),
    )
    return begin_combat_intrigue(state).state


def _endgame_window(owner: PlayerState) -> GameState:
    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        tleilaxu_track_spice=2,
        players=(owner, *(_seat(seat) for seat in range(1, 4))),
    )
    return begin_endgame_intrigue(state).state


def _play(card_id: str, option: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card_id), ("option", option)),
    )


def _playable(state: GameState, card_id: str) -> set[int]:
    return {
        int(dict(action.arguments)["option"])
        for action in legal_intrigue_play_actions(state, 0)
        if dict(action.arguments)["card_id"] == card_id
    }


def test_all_eleven_cards_are_transcribed_and_join_the_option_deck() -> None:
    ids = {
        "breakthrough",
        "counterattack",
        "disguised_bureaucrat",
        "economic_positioning",
        "gruesome_sacrifice",
        "harvest_cells",
        "illicit_dealings",
        "shadowy_bargain",
        "study_melange",
        "tleilaxu_puppet",
        "vicious_talents",
    }
    assert all(INTRIGUE_CARDS_BY_ID[card_id].play_data_complete for card_id in ids)
    dealt = {
        instance_id.split(":")[1]
        for instance_id in intrigue_deck_instance_ids(False, immortality=True)
    }
    assert ids <= dealt
    base = {
        instance_id.split(":")[1] for instance_id in intrigue_deck_instance_ids(False)
    }
    assert not ids & base


def test_breakthrough_and_illicit_dealings_move_the_tokens() -> None:
    breakthrough = _intrigue("breakthrough")
    state = _plot_state(_owner(intrigue_cards=(breakthrough,)))
    played = apply_intrigue_play(state, _play(breakthrough))
    assert played.state.players[0].research_space == "c1r3"
    assert played.state.players[0].specimens == 1

    dealings = _intrigue("illicit_dealings")
    state = _plot_state(_owner(intrigue_cards=(dealings,)))
    played = apply_intrigue_play(state, _play(dealings))
    assert played.state.players[0].tleilaxu_space == 1



def test_breakthrough_past_the_second_marker_needs_a_card_to_draw() -> None:
    # Past the second genetic marker Research draws a card instead
    # [Immortality p. 6]: with the deck and discard pile both empty it
    # changes nothing.
    card = _intrigue("breakthrough")
    option = INTRIGUE_CARDS_BY_ID["breakthrough"].options[0]
    everything = starting_deck_instance_ids(0, immortality=True)
    for space in ("c8r2", "c8r4", "c8r6"):
        dry = _plot_state(
            _owner(
                intrigue_cards=(card,), research_space=space, deck=(), hand=everything
            )
        )
        assert _playable(dry, card) == set()
        assert option_unplayable_reason(dry, 0, option) == Research()
        reshuffle = _plot_state(
            _owner(
                intrigue_cards=(card,),
                research_space=space,
                deck=(),
                hand=everything[1:],
                discard_pile=everything[:1],
            )
        )
        assert _playable(reshuffle, card) == {0}
    # Before the last column the token always has a space to move to.
    for space in (RESEARCH_START_ID, "c4r4", "c7r3"):
        moving = _plot_state(
            _owner(
                intrigue_cards=(card,), research_space=space, deck=(), hand=everything
            )
        )
        assert _playable(moving, card) == {0}


def test_illicit_dealings_is_not_offered_at_the_track_end() -> None:
    # "끝까지 가고 나면 뭐 없는 게 맞다" (OQ-048).
    card = _intrigue("illicit_dealings")
    option = INTRIGUE_CARDS_BY_ID["illicit_dealings"].options[0]
    finished = _plot_state(
        _owner(intrigue_cards=(card,), tleilaxu_space=TLEILAXU_TRACK_END)
    )
    assert _playable(finished, card) == set()
    assert option_unplayable_reason(finished, 0, option) == AdvanceTleilaxu(count=1)
    near = _plot_state(
        _owner(intrigue_cards=(card,), tleilaxu_space=TLEILAXU_TRACK_END - 1)
    )
    assert _playable(near, card) == {0}


def test_shadowy_bargain_endgame_advance_is_not_offered_at_the_track_end() -> None:
    bargain = _intrigue("shadowy_bargain")
    finished = _endgame_window(
        _owner(intrigue_cards=(bargain,), tleilaxu_space=TLEILAXU_TRACK_END)
    )
    assert _playable(finished, bargain) == set()
    near = _endgame_window(
        _owner(intrigue_cards=(bargain,), tleilaxu_space=TLEILAXU_TRACK_END - 1)
    )
    assert _playable(near, bargain) == {1}
    advanced = apply_intrigue_play(near, _play(bargain, 1)).state
    assert advanced.players[0].tleilaxu_space == TLEILAXU_TRACK_END
    assert advanced.players[0].victory_points > near.players[0].victory_points


def test_shadowy_bargain_plot_specimen_needs_a_troop_in_the_supply() -> None:
    # A specimen is a troop from the supply put in the tanks [Immortality
    # p. 8]: with none there, a recorded shortfall does not count
    # (main-session decision on the user's ruling of 2026-10-06), and a held
    # specimen returned only to become one again changes nothing.
    bargain = _intrigue("shadowy_bargain")
    option = INTRIGUE_CARDS_BY_ID["shadowy_bargain"].options[0]
    empty = _plot_state(
        _owner(
            intrigue_cards=(bargain,), troops_supply=0, troops_garrison=10, specimens=2
        )
    )
    assert _playable(empty, bargain) == set()
    assert option_unplayable_reason(empty, 0, option) == GenerateSpecimens(count=1)


def test_disguised_bureaucrat_scales_with_the_genetic_markers() -> None:
    card = _intrigue("disguised_bureaucrat")
    unmarked = _plot_state(_owner(intrigue_cards=(card,)))
    assert _playable(unmarked, card) == set()
    one = _plot_state(_owner(intrigue_cards=(card,), research_space="c4r4"))
    played = apply_intrigue_play(one, _play(card))
    assert played.state.players[0].resources.spice == 1
    assert played.state.decision_stack[-1].kind == "turn"
    two = _plot_state(_owner(intrigue_cards=(card,), research_space="c8r2"))
    played = apply_intrigue_play(two, _play(card))
    assert played.state.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    choice = next(
        action
        for action in legal_intrigue_choice_actions(played.state, 0)
        if dict(action.arguments).get("faction") == "fremen"
    )
    done = apply_intrigue_choice(played.state, choice)
    assert done.state.players[0].influence.fremen == 1
    assert done.state.players[0].resources.spice == 1


def test_disguised_bureaucrat_confirms_an_influence_no_cube_can_take() -> None:
    """A cost-free "choose a Faction" gain with every cube at 6: the card
    stays playable through its spice, an effect that can change something
    (user ruling 2026-10-06), the picker offers no Faction at the top, and
    its owner confirms the lost gain as a Conflict reward's (OQ-060)."""

    card = _intrigue("disguised_bureaucrat")
    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _plot_state(
        _owner(intrigue_cards=(card,), research_space="c8r2", influence=full)
    )
    assert _playable(state, card) == {0}
    played = apply_intrigue_play(state, _play(card)).state
    confirm = DomainAction(
        action_id="resolve_intrigue_influence_without_faction", actor=0
    )
    assert [
        action
        for action in legal_intrigue_choice_actions(played, 0)
        if action.action_id != "resolve_intrigue_rewards"
    ] == [confirm]
    done = apply_intrigue_choice(played, confirm)
    assert done.state.players[0].influence == full
    assert done.state.players[0].resources.spice == 1
    assert card in done.state.intrigue_discard
    assert "intrigue_influence_unavailable" in {e.kind for e in done.events}
    # Stage B3d-3: the seat is shown the confirmation as ``confirm_empty``
    # naming the effect it answers and the card, and the codec holds that
    # row, not the whole template.
    codec = ActionCodec(IMMORTALITY)
    _round_trip(codec, confirm, "disguised_bureaucrat")
    assert [
        action
        for action in UprisingRulesEngine().legal_actions(played, 0)
        # (The card's automatic rewards are its ``resolve`` row.)
        if action.action_id != "resolve"
    ] == [
        DomainAction(
            "confirm_empty",
            0,
            (
                ("of", "gain_influence"),
                ("printed", "disguised_bureaucrat"),
                ("source", "intrigue"),
            ),
        )
    ]


def test_shadowy_bargain_and_study_melange_split_plot_and_endgame() -> None:
    bargain = _intrigue("shadowy_bargain")
    plot = _plot_state(_owner(intrigue_cards=(bargain,)))
    assert _playable(plot, bargain) == {0}
    assert apply_intrigue_play(plot, _play(bargain)).state.players[0].specimens == 1
    endgame = _endgame_window(_owner(intrigue_cards=(bargain,)))
    assert _playable(endgame, bargain) == {1}
    ended = apply_intrigue_play(endgame, _play(bargain, 1))
    assert ended.state.players[0].tleilaxu_space == 1

    melange = _intrigue("study_melange")
    poor = _endgame_window(_owner(intrigue_cards=(melange,), research_space="c8r2"))
    assert _playable(poor, melange) == set()
    rich = _endgame_window(
        _owner(
            intrigue_cards=(melange,),
            research_space="c8r2",
            resources=Resources(spice=3),
        )
    )
    assert _playable(rich, melange) == {1}
    assert (
        apply_intrigue_play(rich, _play(melange, 1)).state.players[0].victory_points
        == 2
    )
    unmarked = _endgame_window(
        _owner(intrigue_cards=(melange,), resources=Resources(spice=3))
    )
    assert _playable(unmarked, melange) == set()


def test_tleilaxu_puppet_adds_persuasion_this_round_only() -> None:
    puppet = _intrigue("tleilaxu_puppet")
    state = _plot_state(_owner(intrigue_cards=(puppet,)))
    played = apply_intrigue_play(state, _play(puppet)).state
    assert played.players[0].reveal_persuasion_round_bonus == 1
    revealed = begin_reveal_turn(played, DomainAction(action_id="reveal_turn", actor=0))
    persuasion = dict(revealed.state.decision_stack[-1].context)["persuasion"]
    # Starting hand Persuasion plus the Puppet's one.
    assert persuasion == 1 + sum(
        1 for card in played.players[0].hand if "convincing" not in card
    ) + sum(2 for card in played.players[0].hand if "convincing" in card) - sum(
        1
        for card in played.players[0].hand
        if "dagger" in card or "seek_allies" in card
    )
    council = _endgame_window(
        _owner(intrigue_cards=(puppet,), research_space="c8r2", high_council=True)
    )
    assert _playable(council, puppet) == {1}
    assert (
        apply_intrigue_play(council, _play(puppet, 1)).state.players[0].victory_points
        == 2
    )


def test_tleilaxu_puppet_played_in_the_owners_reveal_pays_that_reveal() -> None:
    # Tleilaxu Puppet: "Gain [1 Persuasion] during your Reveal turn this
    # round" [Tleilaxu Puppet card]; a Plot may be played at any time during
    # the owner's Agent or Reveal turn [Main p. 7] [Main p. 8]
    # (docs/rules/player-turns.md: "Plot Intrigue 카드는 자신의 Agent 턴 또는
    # 공개 턴 중 어느 때든 플레이할 수 있다"). Played after the Reveal began,
    # the Persuasion joins that Reveal; before the fix it was parked in the
    # round bonus that only a later Reveal start reads, and lost.
    puppet = _intrigue("tleilaxu_puppet")
    state = _plot_state(_owner(intrigue_cards=(puppet,)))
    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    persuasion = dict(revealed.decision_stack[-1].context)["persuasion"]
    assert isinstance(persuasion, int)
    assert _playable(revealed, puppet) == {0}
    played = apply_whole(UprisingRulesEngine(), revealed, _play(puppet)).state
    after = dict(played.decision_stack[-1].context)
    assert played.decision_stack[-1].kind == FrameKind.REVEAL
    assert after["persuasion"] == persuasion + 1
    assert after["persuasion_generated"] == persuasion + 1
    assert played.players[0].reveal_persuasion_round_bonus == 0
    # Kept face up through this Reveal turn and discarded as it ends
    # [FAQ p. 2] (docs/rules/player-turns.md).
    assert played.players[0].intrigue_faceup == (puppet,)
    assert puppet not in played.intrigue_discard
    finished = UprisingRulesEngine().apply(
        played, DomainAction(action_id="finish_reveal", actor=0)
    ).state
    assert finished.players[0].intrigue_faceup == ()
    assert puppet in finished.intrigue_discard


def test_tleilaxu_puppet_stays_face_up_until_its_owners_reveal_turn_ends() -> None:
    """ "다음 공개 턴까지 적용되지 않는 Plot 효과는 카드를 앞면으로 자신의
    앞에 두었다가 그 공개 턴에 사용한 뒤 버린다. [FAQ p. 2]"
    (docs/rules/player-turns.md). [FAQ p. 2]: "If the card does something
    that won't apply until your next Reveal turn (for example: Charisma,
    Recruitment Mission), keep it face up in front of you until then, then
    use and discard it." Tleilaxu Puppet: "Gain [1 Persuasion] during your
    Reveal turn this round" [Tleilaxu Puppet card]. Played before the
    Reveal, it waits face up, pays its Persuasion when the Reveal begins,
    and is discarded when that Reveal turn ends. Until 2026-10-07 it went
    straight to the Intrigue discard. Its Endgame option is used at once and
    discarded as before."""

    puppet = _intrigue("tleilaxu_puppet")
    state = _plot_state(_owner(intrigue_cards=(puppet,)))
    engine = UprisingRulesEngine()
    result = apply_whole(engine, state, _play(puppet))
    played = result.state
    assert played.players[0].intrigue_cards == ()
    assert played.players[0].intrigue_faceup == (puppet,)
    assert puppet not in played.intrigue_discard
    assert "intrigue_kept_faceup" in [event.kind for event in result.events]
    assert played.players[0].reveal_persuasion_round_bonus == 1

    without = _plot_state(_owner())
    base = dict(
        begin_reveal_turn(
            without, DomainAction(action_id="reveal_turn", actor=0)
        ).state.decision_stack[-1].context
    )["persuasion"]
    assert isinstance(base, int)
    revealed = engine.apply(
        played, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == base + 1
    assert revealed.players[0].intrigue_faceup == (puppet,)

    finished = engine.apply(
        revealed, DomainAction(action_id="finish_reveal", actor=0)
    )
    after = finished.state
    assert after.players[0].intrigue_faceup == ()
    assert puppet in after.intrigue_discard
    expired = [e for e in finished.events if e.kind == "intrigue_expired"]
    assert [dict(e.payload)["card_id"] for e in expired] == [puppet]

    council = _endgame_window(
        _owner(intrigue_cards=(puppet,), research_space="c8r2", high_council=True)
    )
    ended = apply_intrigue_play(council, _play(puppet, 1)).state
    assert ended.players[0].intrigue_faceup == ()
    assert puppet in ended.intrigue_discard


def test_vicious_talents_adds_swords_per_marker() -> None:
    card = _intrigue("vicious_talents")
    engine = UprisingRulesEngine()
    for space, expected in ((RESEARCH_START_ID, 2), ("c4r2", 4), ("c8r6", 6)):
        state = _combat_state(_fighter(1, intrigue_cards=(card,), research_space=space))
        played = apply_whole(engine, state, _play(card)).state
        assert played.players[0].combat_strength == 2 + expected


def test_counterattack_needs_an_opponents_combat_intrigue() -> None:
    card = _intrigue("counterattack")
    rival = _intrigue("vicious_talents")
    owner = _fighter(1, intrigue_cards=(card,))
    other = _fighter(1, intrigue_cards=(rival,), player_id=1)
    state = _combat_state(owner, other)
    assert _playable(state, card) == set()
    # The opponent plays a Combat Intrigue card first.
    engine = UprisingRulesEngine()
    passed = engine.apply(
        state, DomainAction(action_id="pass_combat_intrigue", actor=0)
    )
    rival_played = apply_whole(
        engine,
        passed.state,
        DomainAction(
            action_id="play_intrigue",
            actor=1,
            arguments=(("card_id", rival), ("option", 0)),
        ),
    ).state
    assert 1 in rival_played.combat_intrigue_players
    # Back to the owner: the swords are now available.
    back = engine.apply(
        rival_played, DomainAction(action_id="pass_combat_intrigue", actor=1)
    ).state
    if back.decision_stack and back.decision_stack[-1].decision.owner == 0:  # type: ignore[union-attr]
        assert _playable(back, card) == {1}
        swung = apply_whole(engine, back, _play(card, 1)).state
        assert swung.players[0].combat_strength == 2 + 4
    # Plot: deploy up to two garrison troops.
    plot = _plot_state(_owner(intrigue_cards=(card,), troops_garrison=3))
    played = apply_intrigue_play(plot, _play(card))
    assert played.state.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE


def _deploy(count: int) -> DomainAction:
    return DomainAction(
        action_id="deploy_intrigue_troops", actor=0, arguments=(("count", count),)
    )


def _count_row(count: int, **extra: int) -> DomainAction:
    """The row that shows ``_deploy(count)`` (stage B3d-2a)."""

    return DomainAction(
        action_id="choose_count",
        actor=0,
        arguments=tuple(sorted((("count", count), *extra.items()))),
    )


def test_counterattack_plot_deploys_up_to_two_including_none() -> None:
    # "Deploy up to two troops from your garrison to the Conflict."
    # [Counterattack card face]: once played, zero is a choice. With nothing
    # to deploy the card changes nothing and is not offered: "Intrigue 카드를
    # 플레이하려면 카드의 모든 조건을 충족하고 모든 비용을 지불해야 한다.
    # [FAQ p. 2]", with the user's ruling of 2026-10-06 that an Intrigue
    # option needs an effect that can change something.
    card = _intrigue("counterattack")
    engine = UprisingRulesEngine()

    stocked = _plot_state(
        _owner(intrigue_cards=(card,), troops_garrison=3, troops_supply=9)
    )
    opened = apply_whole(engine, stocked, _play(card)).state
    assert engine.whole_actions(opened, 0) == (_deploy(0), _deploy(1), _deploy(2))
    # Stage B3d-2a: the seat is shown the counts by their target rows.
    assert engine.legal_actions(opened, 0) == (
        _count_row(0),
        _count_row(1),
        _count_row(2),
    )
    two = apply_whole(engine, opened, _deploy(2)).state
    assert (two.players[0].troops_garrison, two.players[0].troops_conflict) == (1, 2)
    none = apply_whole(engine, opened, _deploy(0))
    assert "troops_deployed" not in [event.kind for event in none.events]
    assert none.state.players[0].troops_conflict == 0
    assert card in none.state.intrigue_discard
    assert none.state.decision_stack[-1].kind == "turn"

    empty = _plot_state(
        _owner(intrigue_cards=(card,), troops_garrison=0, troops_supply=12)
    )
    assert _playable(empty, card) == set()


def _with_turn_context(state: GameState, **context: object) -> GameState:
    """The owner's turn frame with ``context`` (a deployment block, say)."""

    frame = state.decision_stack[-1]
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),  # type: ignore[arg-type]
        ),
    )


def test_counterattack_plot_needs_a_deployable_garrison_unit() -> None:
    # Nothing it may deploy: an empty garrison, Emperor of the Known
    # Universe's block for the turn [Main p. 17] (here the Servo-Receivers
    # form in the turn frame, OQ-062 (b)), or only Harkonnen Advisor's troop
    # (OQ-038). A Commander in the garrison is a troop for it [Bloodlines
    # p. 4], and a second troop besides the Advisor's can go.
    card = _intrigue("counterattack")
    option = INTRIGUE_CARDS_BY_ID["counterattack"].options[0]
    engine = UprisingRulesEngine()

    def plot(**extra: object) -> GameState:
        return _plot_state(
            _owner(intrigue_cards=(card,), **extra),
            RulesetConfig(immortality=True, bloodlines=True),
        )

    empty = plot(troops_garrison=0, troops_supply=12)
    blocked = _with_turn_context(
        plot(troops_garrison=3, troops_supply=9), units_deploy_blocked=True
    )
    advisor = _with_turn_context(
        plot(troops_garrison=1, troops_supply=11), undeployable_troops=1
    )
    for state in (empty, blocked, advisor):
        assert _playable(state, card) == set()
        assert option_unplayable_reason(state, 0, option) == DeployFromGarrison(
            up_to=2
        )

    commander = plot(troops_garrison=0, troops_supply=12, commanders_garrison=1)
    opened = apply_whole(engine, commander, _play(card)).state
    assert engine.whole_actions(opened, 0) == (
        _deploy(0),
        DomainAction(
            action_id="deploy_intrigue_troops",
            actor=0,
            arguments=(("commanders", 1), ("count", 1)),
        ),
    )
    # Stage B3d-2a: the seat is shown the counts by their target rows.
    assert engine.legal_actions(opened, 0) == (
        _count_row(0),
        _count_row(1, commanders=1),
    )
    second = _with_turn_context(
        plot(troops_garrison=2, troops_supply=10), undeployable_troops=1
    )
    opened = apply_whole(engine, second, _play(card)).state
    assert engine.whole_actions(opened, 0) == (_deploy(0), _deploy(1))
    assert engine.legal_actions(opened, 0) == (_count_row(0), _count_row(1))


def test_gruesome_sacrifice_trades_two_conflict_troops() -> None:
    card = _intrigue("gruesome_sacrifice")
    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    played = apply_intrigue_play(state, _play(card)).state
    for _ in range(2):
        loss = next(
            action
            for action in legal_intrigue_choice_actions(played, 0)
            if action.action_id == "lose_intrigue_troop"
        )
        played = apply_intrigue_choice(played, loss).state
    owner = played.players[0]
    assert owner.troops_conflict == 1
    assert owner.tleilaxu_space == 1
    assert owner.specimens == 2
    assert owner.troops_supply == 12 - 1 - 2



def test_gruesome_sacrifice_needs_a_troop_or_a_track_space_to_change() -> None:
    # Two Commanders the only units in the Conflict, no troop in the supply,
    # the Tleilaxu token at the track's end: the lost Commanders return to
    # their own supply [Bloodlines p. 4], so no specimen can be made and the
    # advance does nothing (OQ-048); the card changes nothing.
    card = _intrigue("gruesome_sacrifice")
    option = INTRIGUE_CARDS_BY_ID["gruesome_sacrifice"].options[0]

    def combat(**extra: object) -> GameState:
        values: dict[str, object] = {
            "intrigue_cards": (card,),
            "troops_supply": 0,
            "troops_garrison": 12,
            "troops_conflict": 0,
            "commanders_conflict": 2,
            "combat_strength": 4,
            "tleilaxu_space": TLEILAXU_TRACK_END,
        }
        values.update(extra)
        return _combat_state(
            _fighter(0, **values),
            config=RulesetConfig(immortality=True, bloodlines=True),
        )

    finished = combat()
    assert _playable(finished, card) == set()
    # The advance is named first.
    assert option_unplayable_reason(finished, 0, option) == AdvanceTleilaxu(count=1)
    # The advance can still move, a troop in the supply can become a
    # specimen, or a troop lost from the Conflict returns to the supply.
    for state in (
        combat(tleilaxu_space=3),
        combat(troops_supply=1, troops_garrison=11),
        combat(troops_garrison=11, troops_conflict=1, combat_strength=6),
    ):
        assert _playable(state, card) == {0}


def test_economic_positioning_retreats_or_scores() -> None:
    card = _intrigue("economic_positioning")
    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    played = apply_intrigue_play(state, _play(card)).state
    retreat = next(
        action
        for action in legal_intrigue_choice_actions(played, 0)
        if action.action_id == "retreat_intrigue_troops"
    )
    done = apply_intrigue_choice(played, retreat).state
    assert done.players[0].troops_conflict == 1
    assert done.players[0].resources.solari == 3
    poor = _endgame_window(
        _owner(intrigue_cards=(card,), resources=Resources(solari=9))
    )
    assert _playable(poor, card) == set()
    rich = _endgame_window(
        _owner(intrigue_cards=(card,), resources=Resources(solari=10))
    )
    assert (
        apply_intrigue_play(rich, _play(card, 1)).state.players[0].victory_points == 2
    )


def test_harvest_cells_is_never_played_in_combat_intrigue() -> None:
    """User ruling 2026-10-06 (OQ-057 (11)): "This card is played after
    combat resolves." (designer), and "To play an Intrigue card, you must
    meet its conditions and pay its costs." [FAQ p. 2]. Harvest Cells used
    to go face up during Combat Intrigue (restarting the passes) and expire
    at cleanup when the loss fell short; now neither the Combat Intrigue
    round nor a Plot turn offers it, only the Conflict-end window."""

    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE
    assert _playable(state, card) == set()
    assert all(
        action.action_id != "play_intrigue" for action in engine.whole_actions(state, 0)
    )
    try:
        apply_intrigue_play(state, _play(card))
    except ValueError:
        pass
    else:
        raise AssertionError("Harvest Cells was played in Combat Intrigue")
    plot = _plot_state(
        _owner(intrigue_cards=(card,), troops_supply=6, troops_conflict=3)
    )
    assert _playable(plot, card) == set()


def test_harvest_cells_is_never_offered_below_three_troops_in_the_conflict() -> None:
    # "When you lose at least three troops at the end of a Conflict:"
    # [Harvest Cells card]: two troops in the Conflict never open the window
    # and the card stays in hand -- it no longer waits face up to expire.
    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(2, intrigue_cards=(card,), specimens=0))
    assert _playable(state, card) == set()
    done = _pass_through_combat(engine, state)
    assert done.phase is not GamePhase.COMBAT
    assert all(
        frame.kind != FrameKind.CONFLICT_END_TRIGGER for frame in done.decision_stack
    )
    owner = done.players[0]
    assert card in owner.intrigue_cards
    assert card not in owner.intrigue_faceup
    assert card not in done.intrigue_discard
    assert owner.specimens == 0
    assert all(event.kind != "intrigue_expired" for event in done.event_log)


def test_harvest_cells_resolves_when_played_after_three_troops_are_lost() -> None:
    # The troops are back in the supply when the window opens, so the card
    # gives its two specimens at once and only the Tleilaxu acquisition is
    # asked (user decision 2026-10-18, design in
    # docs/rules/combat-and-round-end.md).
    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(3, intrigue_cards=(card,), specimens=0))
    window = _pass_through_combat(engine, state)
    assert window.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    played = apply_whole(
        engine,
        window,
        DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", card),),
        ),
    ).state
    owner = played.players[0]
    assert card not in owner.intrigue_faceup
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    # The specimens are the card's automatic reward, already taken; nothing
    # is left to resolve.
    assert owner.specimens == 2
    offers = {a.action_id for a in legal_intrigue_choice_actions(played, 0)}
    assert offers == {"acquire_intrigue_tleilaxu", "decline_intrigue_tleilaxu"}
    bought = apply_whole(
        engine,
        played,
        next(
            a
            for a in legal_intrigue_choice_actions(played, 0)
            if a.action_id == "acquire_intrigue_tleilaxu"
            and dict(a.arguments)["instance_id"] == CONTAMINATOR
        ),
    ).state
    assert CONTAMINATOR in bought.players[0].discard_pile
    assert bought.players[0].specimens == 1
    assert card in bought.intrigue_discard


def _pass_through_combat(engine: UprisingRulesEngine, state: GameState) -> GameState:
    while state.phase is GamePhase.COMBAT and state.decision_stack:
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.PAUSE:
            # The engine's pause between reward recipients (rules/pauses.py)
            # has one outcome, which a chance resolver gives at once.
            state = engine.apply(state, pause_outcome(state)).state
            continue
        if not isinstance(frame.decision, PlayerDecision):
            break
        if frame.kind == FrameKind.CONFLICT_END_TRIGGER:
            break
        actions = engine.legal_actions(state, frame.decision.owner)
        passing = next(
            (a for a in actions if a.action_id.startswith("pass_")), actions[0]
        )
        state = engine.apply(state, passing).state
    return state


def test_harvest_cells_in_hand_may_be_played_after_the_rewards() -> None:
    # Designer ruling (BGG, OQ-057): Harvest Cells received as a Combat
    # reward can be played in that same Combat. After the rewards and before
    # the cleanup, a seat holding the card with enough troops to lose gets a
    # window to play it (or decline).
    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(
        _fighter(3, intrigue_cards=(card,), specimens=0),
        _seat(
            1, troops_supply=7, troops_conflict=2, combat_strength=4, has_revealed=True
        ),
    )
    window = _pass_through_combat(engine, state)
    frame = window.decision_stack[-1]
    assert frame.kind == FrameKind.CONFLICT_END_TRIGGER
    assert isinstance(frame.decision, PlayerDecision) and frame.decision.owner == 0
    assert window.combat_rewards_resolved and window.combat_end_triggers_offered
    # Seat 1 loses only two troops: no window of its own.
    assert len(window.decision_stack) == 1
    actions = engine.whole_actions(window, 0)
    assert [(a.action_id, dict(a.arguments).get("card_id")) for a in actions] == [
        ("decline_conflict_end_intrigue", None),
        ("play_conflict_end_intrigue", card),
    ]

    played = apply_whole(engine, window, actions[1]).state
    assert card not in played.players[0].intrigue_faceup
    # The troops went back as the window opened (they are "lost" there
    # [FAQ p. 1]), so the card resolved at its play: its specimens are
    # taken and only the acquisition is left to ask.
    assert played.phase is GamePhase.COMBAT
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    assert played.players[0].specimens == 2
    finished = apply_whole(engine, played, DECLINE_ACQUIRE).state
    assert card in finished.intrigue_discard
    assert finished.phase is not GamePhase.COMBAT
    assert finished.players[0].troops_conflict == 0

    declined = apply_whole(engine, window, actions[0]).state
    assert declined.phase is not GamePhase.COMBAT
    assert card in declined.players[0].intrigue_cards
    assert declined.players[0].specimens == 0

    # Two troops lost: no window at all, straight to the cleanup.
    short = _pass_through_combat(
        engine, _combat_state(_fighter(2, intrigue_cards=(card,)))
    )
    assert short.phase is not GamePhase.COMBAT
    assert card in short.players[0].intrigue_cards


def test_harvest_cells_from_hand_takes_its_specimens_after_the_loss() -> None:
    # "When you lose at least three troops at the end of a Conflict: [2
    # specimens]" [Harvest Cells card]; "When resolving combat, troops that
    # return to your supply are considered 'lost.'" [FAQ p. 1]; a specimen
    # is "a troop from your supply" [Immortality p. 8]. The Conflict's
    # troops go back before the window opens (user decision 2026-10-18), so
    # a seat whose supply was empty has the four troops to make its two
    # specimens from the moment it plays the card.
    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(
        _fighter(
            4,
            intrigue_cards=(card,),
            specimens=0,
            troops_supply=0,
            troops_garrison=8,
        )
    )
    window = _pass_through_combat(engine, state)
    assert window.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    # The four troops are already back in the supply.
    assert window.players[0].troops_conflict == 0
    assert window.players[0].troops_supply == 4
    played = apply_whole(
        engine,
        window,
        DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", card),),
        ),
    ).state
    assert played.phase is GamePhase.COMBAT
    assert played.players[0].troops_conflict == 0
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    assert played.players[0].specimens == 2
    assert played.players[0].troops_supply == 4 - 2


def _harvest_cells_offer(specimens: int, **extra: object) -> GameState:
    """Harvest Cells played in the Conflict-end window, its specimens taken
    at the play: the "acquire a Tleilaxu card" slot is open."""

    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    owner = _fighter(
        3,
        intrigue_cards=(card,),
        specimens=specimens,
        troops_supply=9 - specimens,
        **extra,
    )
    window = _pass_through_combat(engine, _combat_state(owner))
    return apply_whole(
        engine,
        window,
        DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", card),),
        ),
    ).state


def _round_trip(
    codec: ActionCodec, action: DomainAction, printed: str = "harvest_cells"
) -> None:
    """A window opened for one effect offers its whole action by the target
    rows that stand for it (stage B3d-2a), so the rows round-trip through the
    codec and the whole template is in no catalog; a refusal or empty
    confirmation is the ``decline`` / ``confirm_empty`` row naming the effect
    it answers and ``printed``, the card (stage B3d-3); any other action
    round-trips as it is."""

    spec = STEP_SPECS.get(action.action_id)
    if action.action_id in TARGET_SPECS:
        rows = steps_for(action, effect_row=False)
    elif spec is not None and spec.verb in (Verb.DECLINE, Verb.CONFIRM_EMPTY):
        rows = steps_for(action, printed, Source.INTRIGUE)
    else:
        assert codec.decode(codec.encode(action), 0) == action
        return
    for row in rows:
        assert codec.decode(codec.encode(row), 0) == row
    with pytest.raises(ValueError, match="not present"):
        codec.encode(action)


def _reclaimed_forces(state: GameState) -> list[str]:
    return [
        str(dict(action.arguments)["choice"])
        for action in legal_intrigue_choice_actions(state, 0)
        if action.action_id == "acquire_intrigue_reclaimed_forces"
    ]


def test_harvest_cells_may_take_reclaimed_forces_troops() -> None:
    # "The Tleilaxu Row must always have two cards plus Reclaimed Forces
    # ... When a player 'acquires' it, they choose one of its effects (to
    # recruit two troops, or advance their Tleilaxu token one space on the
    # Tleilaxu track), but leave the card in place" [Immortality p. 9]
    # (docs/rules/immortality.md 4); Harvest Cells' "You may also acquire a
    # Tleilaxu card (paying its normal cost)" may take it (user ruling
    # 2026-10-06). One specimen held plus the two harvested pays its three.
    card = _intrigue("harvest_cells")
    offer = _harvest_cells_offer(1)
    assert offer.players[0].specimens == 3
    assert _reclaimed_forces(offer) == ["troops", "tleilaxu"]
    codec = ActionCodec(IMMORTALITY)
    for action in legal_intrigue_choice_actions(offer, 0):
        _round_trip(codec, action)
    garrison = offer.players[0].troops_garrison
    taken = apply_whole(
        UprisingRulesEngine(),
        offer,
        DomainAction(
            action_id="acquire_intrigue_reclaimed_forces",
            actor=0,
            arguments=(("choice", "troops"),),
        ),
    )
    owner = taken.state.players[0]
    assert owner.specimens == 0
    assert owner.troops_garrison == garrison + 2
    assert owner.troops_conflict == 0
    # The card stays in place; the two dealt cards are untouched.
    assert taken.state.tleilaxu_row == offer.tleilaxu_row
    assert card in taken.state.intrigue_discard
    assert [
        dict(event.payload)["choice"]
        for event in taken.events
        if event.kind == "reclaimed_forces_acquired"
    ] == ["troops"]


def test_harvest_cells_may_take_reclaimed_forces_tleilaxu_step() -> None:
    offer = _harvest_cells_offer(1)
    taken = apply_whole(
        UprisingRulesEngine(),
        offer,
        DomainAction(
            action_id="acquire_intrigue_reclaimed_forces",
            actor=0,
            arguments=(("choice", "tleilaxu"),),
        ),
    ).state
    owner = taken.players[0]
    assert owner.specimens == 0
    assert owner.tleilaxu_space == 1
    assert taken.tleilaxu_row == offer.tleilaxu_row


def test_harvest_cells_offers_reclaimed_forces_only_when_paid_and_useful() -> None:
    # No specimen held: the two harvested ones are below its printed three.
    assert _reclaimed_forces(_harvest_cells_offer(0)) == []
    # The Reveal shop's block: an advance from the track's last space buys
    # nothing (OQ-048, OQ-071), so only the troops are offered.
    assert _reclaimed_forces(
        _harvest_cells_offer(1, tleilaxu_space=TLEILAXU_TRACK_END)
    ) == ["troops"]


def test_harvest_cells_window_skips_a_copy_that_would_change_nothing() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." [FAQ p. 2], with the user's ruling of 2026-10-06 that an
    # Intrigue option needs an effect that can change something. Its
    # specimens come from troops back in the supply as the window opens
    # [FAQ p. 1]; lost Sardaukar Commanders return to their own supply
    # [Bloodlines p. 4] and make none.
    first, second = _intrigue("harvest_cells"), "intrigue:harvest_cells:1"
    engine = UprisingRulesEngine()
    blood = RulesetConfig(immortality=True, bloodlines=True)
    pricey = ("tleilaxu:twisted_mentat:0", "tleilaxu:usurp:0")  # four each

    def window(*cards: str, **extra: object) -> GameState:
        values: dict[str, object] = {
            "intrigue_cards": cards,
            "troops_supply": 0,
            "troops_garrison": 12,
            "troops_conflict": 0,
            "commanders_conflict": 3,
            "combat_strength": 6,
            "specimens": 0,
        }
        values.update(extra)
        state = replace(
            _combat_state(_fighter(0, **values), config=blood), tleilaxu_row=pricey
        )
        return _pass_through_combat(engine, state)

    def offered(state: GameState) -> list[object]:
        if state.decision_stack[-1].kind != FrameKind.CONFLICT_END_TRIGGER:
            return []
        return [
            dict(action.arguments).get("card_id")
            for action in engine.whole_actions(state, 0)
            if action.action_id == "play_conflict_end_intrigue"
        ]

    def play(state: GameState, card_id: str) -> GameState:
        return apply_whole(
            engine,
            state,
            DomainAction(
                action_id="play_conflict_end_intrigue",
                actor=0,
                arguments=(("card_id", card_id),),
            ),
        ).state

    # Case A: three Commanders lost, no troop to make a specimen of, and no
    # Tleilaxu card the specimens could pay for: the window opens on its
    # public facts (OQ-103) but offers only the decline.
    lost_commanders = window(first)
    assert lost_commanders.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert engine.whole_actions(lost_commanders, 0) == (DECLINE_CONFLICT_END,)
    assert engine.legal_actions(lost_commanders, 0) == (DECLINE_CONFLICT_END_ROW,)
    assert offered(lost_commanders) == []
    assert first in lost_commanders.players[0].intrigue_cards
    # A troop in the supply, or three specimens for Reclaimed Forces, opens it.
    assert offered(window(first, troops_supply=1, troops_garrison=11)) == [first]
    assert offered(window(first, specimens=3, troops_garrison=9)) == [first]

    # Case C: two troops and a Commander lost. The first copy makes its
    # specimens from both troops at its play; the second could make no
    # specimen, and the two specimens buy no Tleilaxu card (the first copy's
    # acquisition slot offers only its decline), so once the first is played
    # the window, still open while the seat holds an Intrigue card (OQ-103),
    # offers only to finish.
    mixed = {"troops_garrison": 10, "troops_conflict": 2, "commanders_conflict": 1}
    both = window(first, second, **mixed)
    assert offered(both) == [first, second]
    played = play(both, first)
    assert played.players[0].specimens == 2
    assert played.players[0].troops_supply == 0
    assert engine.whole_actions(played, 0) == (DECLINE_ACQUIRE,)
    assert engine.legal_actions(played, 0) == (DECLINE_ACQUIRE_ROW,)
    played = apply_whole(engine, played, DECLINE_ACQUIRE).state
    assert played.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert engine.legal_actions(played, 0) == (FINISH_CONFLICT_END,)
    assert offered(played) == []
    assert second in played.players[0].intrigue_cards
    # A third troop lost leaves the second copy a specimen to make.
    three = window(
        first, second, troops_garrison=9, troops_conflict=3, commanders_conflict=0
    )
    staged = apply_whole(engine, play(three, first), DECLINE_ACQUIRE).state
    assert offered(staged) == [second]


HARVEST_CELLS = ("intrigue:harvest_cells:0", "intrigue:harvest_cells:1")
# An Intrigue card with no Conflict-end trigger.
PLAIN = _intrigue("backed_by_choam")


def _offer(engine: UprisingRulesEngine, state: GameState) -> Transition:
    """Pass Combat Intrigue, answer the pauses and the reward choices: the
    transition that offers the Conflict-end windows."""

    while True:
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.PAUSE:
            transition = engine.apply(state, pause_outcome(state))
        else:
            assert isinstance(frame.decision, PlayerDecision)
            actions = engine.legal_actions(state, frame.decision.owner)
            passing = (a for a in actions if a.action_id.startswith("pass_"))
            transition = engine.apply(state, next(passing, actions[0]))
        if transition.state.combat_end_triggers_offered:
            return transition
        state = transition.state


def _windows(state: GameState) -> list[object]:
    return [
        dict(frame.context)["player"]
        for frame in state.decision_stack
        if frame.kind == FrameKind.CONFLICT_END_TRIGGER
    ]


def test_the_conflict_end_window_opens_on_public_facts_only() -> None:
    # OQ-103, user decision 2026-10-09 ("1번은 A안으로 가자"): the window
    # opens with Immortality for a seat with at least three units in the
    # Conflict (the smallest loss Harvest Cells names) and an Intrigue card
    # in hand, unless both Harvest Cells copies are already public -- facts
    # every seat sees. A seat that can play nothing gets only the decline.
    engine = UprisingRulesEngine()
    offered = _offer(engine, _combat_state(_fighter(3, intrigue_cards=(PLAIN,))))
    assert _windows(offered.state) == [0]
    assert engine.whole_actions(offered.state, 0) == (DECLINE_CONFLICT_END,)
    assert engine.legal_actions(offered.state, 0) == (DECLINE_CONFLICT_END_ROW,)
    # The step awards the Conflict card first (OQ-108, user decision
    # 2026-10-18), then opens the window.
    assert [(event.kind, dict(event.payload)) for event in offered.events] == [
        (
            "conflict_won",
            {"conflict_id": CONFLICTS[0].card.card_id, "player": 0},
        ),
        ("conflict_end_trigger_offered", {"player": 0}),
    ]

    declined = apply_whole(engine, offered.state, DECLINE_CONFLICT_END)
    assert [event.kind for event in declined.events][0] == (
        "conflict_end_trigger_declined"
    )
    assert declined.state.phase is not GamePhase.COMBAT
    assert declined.state.players[0].intrigue_cards == (PLAIN,)

    def opens(
        owner: PlayerState, *others: PlayerState, discard: tuple[str, ...] = ()
    ) -> bool:
        state = replace(_combat_state(owner, *others), intrigue_discard=discard)
        return _windows(_offer(engine, state).state) == [0]

    # Without Immortality: the same seat and hand, no window.
    base = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        conflict_deck=(CONFLICTS[1].card.card_id,),
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=(
            PlayerState(
                player_id=0,
                troops_supply=9,
                troops_garrison=0,
                troops_conflict=3,
                combat_strength=6,
                has_revealed=True,
                intrigue_cards=(PLAIN,),
            ),
            *(PlayerState(player_id=seat, has_revealed=True) for seat in (1, 2, 3)),
        ),
    )
    assert _windows(_offer(engine, begin_combat_intrigue(base).state).state) == []
    assert not opens(_fighter(2, intrigue_cards=(PLAIN,)))
    assert not opens(_fighter(3, intrigue_cards=()))
    holding = _fighter(3, intrigue_cards=(PLAIN,))
    assert not opens(holding, discard=HARVEST_CELLS)
    # Face up counts as public too (here a copy another seat with three
    # troops in the Conflict holds face up).
    other = _seat(
        1,
        has_revealed=True,
        troops_supply=6,
        troops_garrison=3,
        troops_conflict=3,
        combat_strength=2,
        intrigue_faceup=(HARVEST_CELLS[1],),
    )
    assert not opens(holding, other, discard=HARVEST_CELLS[:1])
    # One copy still unseen (the deck, a hand) keeps it open.
    assert opens(holding, discard=HARVEST_CELLS[:1])


def test_the_conflict_end_window_looks_the_same_with_and_without_harvest_cells() -> (
    None
):
    # The same frame, prompt and event for a seat holding a playable Harvest
    # Cells and one holding another card, so neither the window nor the
    # other seats' view tells them apart; only the owner's actions differ.
    engine = UprisingRulesEngine()
    holder = _offer(
        engine, _combat_state(_fighter(3, intrigue_cards=(HARVEST_CELLS[0],)))
    )
    other = _offer(engine, _combat_state(_fighter(3, intrigue_cards=(PLAIN,))))

    assert holder.state.decision_stack == other.state.decision_stack
    assert holder.events == other.events
    frame = holder.state.decision_stack[-1]
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.prompt == (
        "Play an Intrigue card that triggers at this Conflict's end, or decline"
    )
    for seat in (1, 2, 3):
        assert engine.observe(holder.state, seat) == engine.observe(other.state, seat)
    assert engine.whole_actions(other.state, 0) == (DECLINE_CONFLICT_END,)
    assert engine.whole_actions(holder.state, 0) == (
        DECLINE_CONFLICT_END,
        DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", HARVEST_CELLS[0]),),
        ),
    )


def test_the_conflict_end_window_stays_open_while_the_seat_holds_intrigue() -> None:
    # After a play the window stays open while the seat still holds an
    # Intrigue card, a public fact, and closes with an empty hand; closing it
    # only when no other copy could be played told the table whether a
    # second Harvest Cells was in the hand (OQ-103). The played card has
    # resolved by then, so the one press left in the window finishes it.
    # Whether the hand is empty is judged when the window comes back on top,
    # after the card's acquisition is answered (OQ-109, user decision
    # 2026-10-18), not at the play.
    engine = UprisingRulesEngine()
    play = DomainAction(
        action_id="play_conflict_end_intrigue",
        actor=0,
        arguments=(("card_id", HARVEST_CELLS[0]),),
    )
    window = _offer(
        engine,
        _combat_state(_fighter(3, intrigue_cards=(HARVEST_CELLS[0], PLAIN))),
    ).state

    played = apply_whole(engine, window, play).state

    assert _windows(played) == [0]
    # The card resolved at its play: it is not left face up and its
    # acquisition choice (the specimens are already taken) sits on the window.
    assert played.players[0].intrigue_faceup == ()
    assert played.players[0].specimens == 2
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    answered = apply_whole(engine, played, DECLINE_ACQUIRE).state
    assert answered.phase is GamePhase.COMBAT
    assert answered.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert engine.legal_actions(answered, 0) == (FINISH_CONFLICT_END,)
    finished = engine.apply(answered, FINISH_CONFLICT_END).state
    assert finished.phase is not GamePhase.COMBAT
    assert PLAIN in finished.players[0].intrigue_cards
    assert HARVEST_CELLS[0] in finished.intrigue_discard

    # The last card played: the window stays under its acquisition choice and
    # closes once that is answered (OQ-109), with no press of its own.
    alone = _offer(
        engine, _combat_state(_fighter(3, intrigue_cards=(HARVEST_CELLS[0],)))
    ).state
    closed = apply_whole(engine, alone, play).state
    assert _windows(closed) == [0]
    assert closed.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    done = apply_whole(engine, closed, DECLINE_ACQUIRE).state
    assert _windows(done) == []
    assert done.phase is not GamePhase.COMBAT


def test_a_spent_conflict_end_window_closes_without_a_press_or_an_event() -> None:
    # OQ-109, user decision 2026-10-18 ("그래 둘다 B가 맞겠다"): after a play
    # the window always stays (marked played) and closes automatically only
    # when it comes back on top with its seat holding no Intrigue card. A seat
    # that played its only card needs no "finish" press, and the engine's
    # close leaves no event of its own, as the close at the play never had one.
    engine = UprisingRulesEngine()
    play = DomainAction(
        action_id="play_conflict_end_intrigue",
        actor=0,
        arguments=(("card_id", HARVEST_CELLS[0]),),
    )
    # Seat 1, the second window (under seat 0's on the stack), holds a card
    # too; seat 0 is the First Player.
    state = _combat_state(
        _fighter(3, intrigue_cards=(HARVEST_CELLS[0],), specimens=0),
        _seat(
            1,
            has_revealed=True,
            troops_supply=9,
            troops_garrison=0,
            troops_conflict=3,
            combat_strength=2,
            intrigue_cards=(PLAIN,),
        ),
    )
    window = _offer(engine, state).state
    assert _windows(window) == [1, 0]  # bottom to top: seat 0's is on top
    top = window.decision_stack[-1]
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 0

    played = apply_whole(engine, window, play).state
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    assert _windows(played) == [1, 0]

    declined = apply_whole(engine, played, DECLINE_ACQUIRE)

    # Seat 0's window is gone without a press and without an event of its
    # own; the next seat's window is the one open.
    assert _windows(declined.state) == [1]
    assert declined.state.players[0].intrigue_cards == ()
    assert declined.state.phase is GamePhase.COMBAT
    top = declined.state.decision_stack[-1]
    assert top.kind == FrameKind.CONFLICT_END_TRIGGER
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert not {
        "conflict_end_trigger_declined",
        "conflict_end_trigger_finished",
    } & {event.kind for event in declined.events}
    assert engine.legal_actions(declined.state, 0) == ()
    assert engine.whole_actions(declined.state, 1) == (
        DomainAction(action_id="decline_conflict_end_intrigue", actor=1),
    )
    assert engine.legal_actions(declined.state, 1) == (
        DomainAction(
            "decline",
            1,
            (("of", "play"), ("printed", "conflict_end"), ("source", "intrigue")),
        ),
    )

    # With no other window, the cleanup follows the acquisition answer.
    alone = _offer(
        engine,
        _combat_state(_fighter(3, intrigue_cards=(HARVEST_CELLS[0],), specimens=0)),
    ).state
    closed = apply_whole(
        engine, apply_whole(engine, alone, play).state, DECLINE_ACQUIRE
    )
    assert closed.state.phase is not GamePhase.COMBAT
    assert _windows(closed.state) == []
    assert not {
        "conflict_end_trigger_declined",
        "conflict_end_trigger_finished",
    } & {event.kind for event in closed.events}


def test_harvest_cells_played_in_its_window_resolves_in_the_same_step() -> None:
    # User decision 2026-10-18: "세포 수확은 내는 즉시 표본 2를 주고 획득
    # 여부만 묻게 해줘 ... 낸 뒤의 '쓰지 않음'은 '끝내기'로 보이게 하고".
    # The troops are back in the supply when the window opens ("troops that
    # return to your supply are considered 'lost.'" [FAQ p. 1]), so the
    # card's two specimens ("take a troop from your supply" [Immortality
    # p. 8]) come with the play and only "You may also acquire a Tleilaxu
    # card" is asked [Harvest Cells card].
    engine = UprisingRulesEngine()
    play = DomainAction(
        action_id="play_conflict_end_intrigue",
        actor=0,
        arguments=(("card_id", HARVEST_CELLS[0]),),
    )
    window = _offer(
        engine,
        _combat_state(
            _fighter(3, intrigue_cards=(HARVEST_CELLS[0], PLAIN), specimens=0)
        ),
    ).state
    assert window.players[0].specimens == 0

    transition = apply_whole(engine, window, play)
    played = transition.state

    # The specimens come in the play's own step, as one event.
    assert [event.kind for event in transition.events].count("specimens_generated") == 1
    generated = next(e for e in transition.events if e.kind == "specimens_generated")
    assert dict(generated.payload)["player"] == 0
    # (The steps' seat-only pick events are not the play's events.)
    kinds = [e.kind for e in transition.events if e.kind != "effect_picked"]
    assert kinds[0] == "intrigue_played"
    assert played.players[0].specimens == 2
    assert played.players[0].troops_supply == 12 - 2
    # The acquisition choice is on top of the window; the card is not left
    # face up and nothing waits to be "resolved".
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    assert _windows(played) == [0]
    assert played.players[0].intrigue_faceup == ()
    assert all(event.kind != "intrigue_trigger_fired" for event in transition.events)
    offers = {action.action_id for action in engine.whole_actions(played, 0)}
    assert offers == {"acquire_intrigue_tleilaxu", "decline_intrigue_tleilaxu"}
    # Stage B3d-2a: the seat is shown the Tleilaxu cards by target rows.
    # (Stage B3d-3: the refusal is the ``decline`` row.)
    assert {action.action_id for action in engine.legal_actions(played, 0)} == {
        "choose_tleilaxu_card",
        "decline",
    }
    assert DECLINE_ACQUIRE_ROW in engine.legal_actions(played, 0)

    bought = apply_whole(
        engine,
        played,
        next(
            action
            for action in engine.whole_actions(played, 0)
            if action.action_id == "acquire_intrigue_tleilaxu"
            and dict(action.arguments)["instance_id"] == CONTAMINATOR
        ),
    ).state
    assert CONTAMINATOR in bought.players[0].discard_pile
    assert bought.players[0].specimens == 1
    assert HARVEST_CELLS[0] in bought.intrigue_discard

    # The seat still holds an Intrigue card: the window stays open, and its
    # one press reads as finishing, not declining.
    assert bought.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    actions = engine.legal_actions(bought, 0)
    assert actions == (FINISH_CONFLICT_END,)
    assert DECLINE_CONFLICT_END not in actions
    finished = engine.apply(bought, FINISH_CONFLICT_END)
    assert [event.kind for event in finished.events][0] == (
        "conflict_end_trigger_finished"
    )
    assert _windows(finished.state) == []
    assert finished.state.phase is not GamePhase.COMBAT
    assert PLAIN in finished.state.players[0].intrigue_cards


def test_two_harvest_cells_each_resolve_at_their_own_play_in_window_order() -> None:
    # Two seats play a Harvest Cells in the same Conflict-end step. "Each
    # seat, in turn order from the First Player" (designer ruling, OQ-002):
    # seat 1 is the First Player, so its window is first. Each card resolves
    # at its own play, so seat 1's specimens and acquisition are done before
    # seat 0's window is answered, and the Intrigue discard holds the copies
    # in the order they were played.
    engine = UprisingRulesEngine()
    first_copy, second_copy = HARVEST_CELLS

    def play(card_id: str, seat: int) -> DomainAction:
        return DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=seat,
            arguments=(("card_id", card_id),),
        )

    state = _combat_state(
        _fighter(3, intrigue_cards=(first_copy,), specimens=0),
        _seat(
            1,
            has_revealed=True,
            troops_supply=9,
            troops_garrison=0,
            troops_conflict=3,
            combat_strength=6,
            specimens=0,
            intrigue_cards=(second_copy,),
        ),
        first_player=1,
    )
    window = _offer(engine, state).state
    assert _windows(window) == [0, 1]
    # The First Player's window is on top.
    top = window.decision_stack[-1]
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1

    played_first = apply_whole(engine, window, play(second_copy, 1)).state
    assert played_first.players[1].specimens == 2
    assert played_first.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    # Seat 0 has not been asked yet and has taken nothing.
    assert played_first.players[0].specimens == 0
    assert first_copy in played_first.players[0].intrigue_cards

    bought = apply_whole(
        engine,
        played_first,
        next(
            action
            for action in engine.whole_actions(played_first, 1)
            if action.action_id == "acquire_intrigue_tleilaxu"
            and dict(action.arguments)["instance_id"] == CONTAMINATOR
        ),
    ).state
    assert CONTAMINATOR in bought.players[1].discard_pile
    assert bought.players[1].specimens == 1
    assert bought.intrigue_discard == (second_copy,)
    # Seat 1 holds another Intrigue card (a Conflict reward), so its window
    # stays open until it finishes; seat 0's is the one below it.
    assert bought.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert engine.legal_actions(bought, 1) == (
        DomainAction(action_id="finish_conflict_end_intrigue", actor=1),
    )
    assert _windows(bought) == [0, 1]
    bought = engine.apply(
        bought, DomainAction(action_id="finish_conflict_end_intrigue", actor=1)
    ).state
    # Now seat 0's window is the one open, with its card still in hand.
    assert _windows(bought) == [0]
    assert bought.players[0].specimens == 0
    assert first_copy in bought.players[0].intrigue_cards

    played_second = apply_whole(engine, bought, play(first_copy, 0)).state
    assert played_second.players[0].specimens == 2
    assert played_second.players[1].specimens == 1
    assert played_second.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    answered = apply_whole(engine, played_second, DECLINE_ACQUIRE).state
    assert _windows(answered) == [0]
    done = engine.apply(
        answered, DomainAction(action_id="finish_conflict_end_intrigue", actor=0)
    ).state
    assert done.phase is not GamePhase.COMBAT
    assert done.intrigue_discard == (second_copy, first_copy)
    assert done.players[0].intrigue_faceup == ()
    assert done.players[1].intrigue_faceup == ()
    assert [
        dict(event.payload)["player"]
        for event in done.event_log
        if event.kind == "specimens_generated"
    ] == [1, 0]


def test_immortality_intrigue_choices_round_trip_through_the_codec() -> None:
    codec = ActionCodec(IMMORTALITY)
    card = _intrigue("gruesome_sacrifice")
    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    played = apply_intrigue_play(state, _play(card)).state
    for action in legal_intrigue_choice_actions(played, 0):
        _round_trip(codec, action)
    assert replace(state).combat_intrigue_players == ()


def test_a_card_drawn_in_the_acquisition_can_be_played_in_the_same_window() -> None:
    # OQ-109, decided (b) by the user on 2026-10-18 ("그래 둘다 B가 맞겠다"):
    # Harvest Cells resolves at its play, so the Tleilaxu card its acquisition
    # buys can draw an Intrigue card while the seat's window is still open --
    # here Subject X-137's acquire box moves the Tleilaxu track onto its
    # Intrigue space, which draws the other Harvest Cells. The window always
    # stays after a play and closes only when it comes back on top with the
    # seat holding no Intrigue card, so the drawn copy can be played in it
    # whether or not the seat held another card at the first play.
    engine = UprisingRulesEngine()
    first, second = HARVEST_CELLS

    def play(card_id: str) -> DomainAction:
        return DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", card_id),),
        )

    def after_acquisition(hand: tuple[str, ...]) -> GameState:
        owner = _fighter(4, intrigue_cards=hand, specimens=0, tleilaxu_space=1)
        state = _combat_state(owner)
        state = replace(state, intrigue_deck=(second, *state.intrigue_deck))
        window = _offer(engine, state).state
        played = apply_whole(engine, window, play(first)).state
        acquire = next(
            action
            for action in engine.whole_actions(played, 0)
            if action.action_id == "acquire_intrigue_tleilaxu"
            and dict(action.arguments)["instance_id"] == SUBJECT
        )
        return apply_whole(engine, played, acquire).state

    # A seat holding another card sees the window with the drawn copy.
    holding = after_acquisition((first, PLAIN))
    assert holding.players[0].intrigue_cards == (PLAIN, second)
    assert holding.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert engine.whole_actions(holding, 0) == (FINISH_CONFLICT_END, play(second))
    finished = engine.apply(holding, FINISH_CONFLICT_END).state
    assert finished.phase is not GamePhase.COMBAT
    assert finished.players[0].intrigue_cards == (PLAIN, second)

    # A seat whose hand the play emptied sees the very same window: the
    # drawn copy is the only card it holds, and it may be played.
    alone = after_acquisition((first,))
    assert alone.players[0].intrigue_cards == (second,)
    assert alone.phase is GamePhase.COMBAT
    assert _windows(alone) == [0]
    assert alone.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert engine.whole_actions(alone, 0) == (FINISH_CONFLICT_END, play(second))
    assert engine.whole_actions(alone, 0) == engine.whole_actions(holding, 0)

    specimens = alone.players[0].specimens
    again = apply_whole(engine, alone, play(second))
    picked = [e.kind for e in again.events if e.kind != "effect_picked"]
    assert picked[0] == "intrigue_played"
    assert again.state.players[0].specimens == specimens + 2
    assert again.state.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    assert _windows(again.state) == [0]

    # Everything answered and the hand empty: the window closes with no
    # press and no event of its own, and the cleanup follows.
    done = apply_whole(engine, again.state, DECLINE_ACQUIRE)
    assert done.state.players[0].intrigue_cards == ()
    assert _windows(done.state) == []
    assert done.state.phase is not GamePhase.COMBAT
    assert not {
        "conflict_end_trigger_declined",
        "conflict_end_trigger_finished",
    } & {event.kind for event in done.events}
    assert first in done.state.intrigue_discard
    assert second in done.state.intrigue_discard
