"""Tests for the eleven Immortality Intrigue cards (effect DSL).

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md`` and ``docs/rules/immortality.md``
sections 3-4 [Immortality pp. 6-8].
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
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
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.effect_interpreter import option_unplayable_reason
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
    owner: PlayerState, *others: PlayerState, config: RulesetConfig = IMMORTALITY
) -> GameState:
    seats = [owner, *others]
    seats.extend(_seat(seat, has_revealed=True) for seat in range(len(seats), 4))
    state = GameState(
        config=config,
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
    assert ActionCodec(IMMORTALITY).decode(
        ActionCodec(IMMORTALITY).encode(confirm), 0
    ) == confirm


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
    played = UprisingRulesEngine().apply(revealed, _play(puppet)).state
    after = dict(played.decision_stack[-1].context)
    assert played.decision_stack[-1].kind == FrameKind.REVEAL
    assert after["persuasion"] == persuasion + 1
    assert after["persuasion_generated"] == persuasion + 1
    assert played.players[0].reveal_persuasion_round_bonus == 0
    assert puppet in played.intrigue_discard


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


def _deploy(count: int) -> DomainAction:
    return DomainAction(
        action_id="deploy_intrigue_troops", actor=0, arguments=(("count", count),)
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
    opened = engine.apply(stocked, _play(card)).state
    assert engine.legal_actions(opened, 0) == (_deploy(0), _deploy(1), _deploy(2))
    two = engine.apply(opened, _deploy(2)).state
    assert (two.players[0].troops_garrison, two.players[0].troops_conflict) == (1, 2)
    none = engine.apply(opened, _deploy(0))
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
    opened = engine.apply(commander, _play(card)).state
    assert engine.legal_actions(opened, 0) == (
        _deploy(0),
        DomainAction(
            action_id="deploy_intrigue_troops",
            actor=0,
            arguments=(("commanders", 1), ("count", 1)),
        ),
    )
    second = _with_turn_context(
        plot(troops_garrison=2, troops_supply=10), undeployable_troops=1
    )
    opened = engine.apply(second, _play(card)).state
    assert engine.legal_actions(opened, 0) == (_deploy(0), _deploy(1))


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
        action.action_id != "play_intrigue" for action in engine.legal_actions(state, 0)
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


def test_harvest_cells_fires_at_cleanup_when_three_troops_are_lost() -> None:
    card = _intrigue("harvest_cells")
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(3, intrigue_cards=(card,), specimens=0))
    window = _pass_through_combat(engine, state)
    assert window.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    played = engine.apply(
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


def _pass_through_combat(engine: UprisingRulesEngine, state: GameState) -> GameState:
    while state.phase is GamePhase.COMBAT and state.decision_stack:
        frame = state.decision_stack[-1]
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
    actions = engine.legal_actions(window, 0)
    assert [(a.action_id, dict(a.arguments).get("card_id")) for a in actions] == [
        ("decline_conflict_end_intrigue", None),
        ("play_conflict_end_intrigue", card),
    ]

    played = engine.apply(window, actions[1]).state
    assert card not in played.players[0].intrigue_faceup
    # The card waited for the cleanup's troop return (it is "lost" there
    # [FAQ p. 1]); its choice opens after it, not straight after the play.
    assert played.phase is not GamePhase.COMBAT
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    rewarded = engine.apply(
        played, DomainAction(action_id="resolve_intrigue_rewards", actor=0)
    ).state
    assert rewarded.players[0].specimens == 2
    finished = engine.apply(
        rewarded, DomainAction(action_id="decline_intrigue_tleilaxu", actor=0)
    ).state
    assert card in finished.intrigue_discard
    assert finished.phase is not GamePhase.COMBAT
    assert finished.players[0].troops_conflict == 0

    declined = engine.apply(window, actions[0]).state
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
    # is "a troop from your supply" [Immortality p. 8]. Played in the window
    # (OQ-057), the card used to resolve before the cleanup, so an empty
    # supply gave no specimens although the same card waiting face up gets
    # two. It now waits for the cleanup like that face-up card.
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
    played = engine.apply(
        window,
        DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", card),),
        ),
    ).state
    # The cleanup ran first: the four troops are back in the supply.
    assert played.phase is not GamePhase.COMBAT
    assert played.players[0].troops_conflict == 0
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    rewarded = engine.apply(
        played, DomainAction(action_id="resolve_intrigue_rewards", actor=0)
    ).state
    assert rewarded.players[0].specimens == 2
    assert rewarded.players[0].troops_supply == 4 - 2


def _harvest_cells_offer(specimens: int, **extra: object) -> GameState:
    """Harvest Cells played in the Conflict-end window, its specimens taken:
    the "acquire a Tleilaxu card" slot is open."""

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
    played = engine.apply(
        window,
        DomainAction(
            action_id="play_conflict_end_intrigue",
            actor=0,
            arguments=(("card_id", card),),
        ),
    ).state
    return engine.apply(
        played, DomainAction(action_id="resolve_intrigue_rewards", actor=0)
    ).state


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
        assert codec.decode(codec.encode(action), 0) == action
    garrison = offer.players[0].troops_garrison
    taken = UprisingRulesEngine().apply(
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
    taken = UprisingRulesEngine().apply(
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


def test_immortality_intrigue_choices_round_trip_through_the_codec() -> None:
    codec = ActionCodec(IMMORTALITY)
    card = _intrigue("gruesome_sacrifice")
    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    played = apply_intrigue_play(state, _play(card)).state
    for action in legal_intrigue_choice_actions(played, 0):
        assert codec.decode(codec.encode(action), 0) == action
    assert replace(state).combat_intrigue_players == ()
