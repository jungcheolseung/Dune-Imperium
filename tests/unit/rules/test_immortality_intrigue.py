"""Tests for the eleven Immortality Intrigue cards (effect DSL).

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md`` and ``docs/rules/immortality.md``
sections 3-4 [Immortality pp. 6-8].
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
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
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.combat import begin_combat_intrigue
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


def _plot_state(owner: PlayerState) -> GameState:
    return GameState(
        config=IMMORTALITY,
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


def _combat_state(owner: PlayerState, *others: PlayerState) -> GameState:
    seats = [owner, *others]
    seats.extend(_seat(seat, has_revealed=True) for seat in range(len(seats), 4))
    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
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


def test_vicious_talents_adds_swords_per_marker() -> None:
    card = _intrigue("vicious_talents")
    engine = UprisingRulesEngine()
    for space, expected in ((RESEARCH_START_ID, 2), ("c4r2", 4), ("c8r6", 6)):
        state = _combat_state(_fighter(1, intrigue_cards=(card,), research_space=space))
        played = engine.apply(state, _play(card)).state
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
    rival_played = engine.apply(
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
        swung = engine.apply(back, _play(card, 1)).state
        assert swung.players[0].combat_strength == 2 + 4
    # Plot: deploy up to two garrison troops.
    plot = _plot_state(_owner(intrigue_cards=(card,), troops_garrison=3))
    played = apply_intrigue_play(plot, _play(card))
    assert played.state.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE


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


def test_harvest_cells_fires_at_cleanup_when_three_troops_are_lost() -> None:
    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(3, intrigue_cards=(card,), specimens=0))
    played = engine.apply(state, _play(card)).state
    assert card in played.players[0].intrigue_faceup
    # Everyone passes; rewards resolve; cleanup fires the trigger.
    while played.phase is GamePhase.COMBAT and played.decision_stack:
        frame = played.decision_stack[-1]
        if not isinstance(frame.decision, PlayerDecision):
            break
        actions = engine.legal_actions(played, frame.decision.owner)
        passing = next(
            (a for a in actions if a.action_id.startswith("pass_")), actions[0]
        )
        played = engine.apply(played, passing).state
    owner = played.players[0]
    assert card not in owner.intrigue_faceup
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    # The specimens are the card's automatic reward, taken at the owner's
    # chosen point (OQ-015); before them nothing is affordable.
    offers = {a.action_id for a in legal_intrigue_choice_actions(played, 0)}
    assert offers == {"decline_intrigue_tleilaxu", "resolve_intrigue_rewards"}
    rewarded = engine.apply(
        played, DomainAction(action_id="resolve_intrigue_rewards", actor=0)
    ).state
    assert rewarded.players[0].specimens == 2
    offers = {a.action_id for a in legal_intrigue_choice_actions(rewarded, 0)}
    assert offers == {"acquire_intrigue_tleilaxu", "decline_intrigue_tleilaxu"}
    bought = engine.apply(
        rewarded,
        next(
            a
            for a in legal_intrigue_choice_actions(rewarded, 0)
            if a.action_id == "acquire_intrigue_tleilaxu"
            and dict(a.arguments)["instance_id"] == CONTAMINATOR
        ),
    ).state
    assert CONTAMINATOR in bought.players[0].discard_pile
    assert bought.players[0].specimens == 1
    assert card in bought.intrigue_discard

    short = _combat_state(_fighter(2, intrigue_cards=(card,)))
    played = engine.apply(short, _play(card)).state
    while played.phase is GamePhase.COMBAT and played.decision_stack:
        frame = played.decision_stack[-1]
        if not isinstance(frame.decision, PlayerDecision):
            break
        actions = engine.legal_actions(played, frame.decision.owner)
        passing = next(
            (a for a in actions if a.action_id.startswith("pass_")), actions[0]
        )
        played = engine.apply(played, passing).state
    assert played.players[0].specimens == 0
    assert card in played.intrigue_discard


def test_immortality_intrigue_choices_round_trip_through_the_codec() -> None:
    codec = ActionCodec(IMMORTALITY)
    card = _intrigue("gruesome_sacrifice")
    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    played = apply_intrigue_play(state, _play(card)).state
    for action in legal_intrigue_choice_actions(played, 0):
        assert codec.decode(codec.encode(action), 0) == action
    assert replace(state).combat_intrigue_players == ()
