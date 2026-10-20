"""Tests for official four-player Combat ranking and ties."""

from dataclasses import replace
from typing import cast

import pytest
from tests.support.pauses import answer_pause, pause_outcome
from tests.support.reward_windows import answer_reward_windows, settle_reward_window

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import (
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    RuleResult,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import (
    CombatInfluenceBlock,
    CombatRanking,
    CombatReward,
    RewardRank,
    apply_combat_influence_without_faction,
    apply_combat_intrigue_pass,
    apply_combat_reward_icon,
    apply_combat_reward_influence,
    apply_combat_reward_optional_payment,
    apply_combat_reward_spy,
    apply_combat_reward_spy_recall,
    apply_combat_reward_trash,
    apply_distinct_combat_reward_influence,
    begin_combat_intrigue,
    combat_reward_influence_block,
    finish_combat,
    legacy_combat_reward_icon,
    legal_combat_intrigue_actions,
    legal_combat_reward_influence_actions,
    legal_combat_reward_optional_payment_actions,
    legal_combat_reward_spy_actions,
    legal_combat_reward_spy_recall_actions,
    legal_combat_reward_trash_actions,
    legal_distinct_combat_reward_influence_actions,
    offer_conflict_end_triggers,
    rank_combat,
    resolve_combat_rewards,
)
from dune_imperium.rules.contracts import (
    apply_contract_action,
    legal_contract_actions,
)
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind, top_frame
from dune_imperium.rules.pauses import pause_is_pending
from dune_imperium.rules.spy_moves import (
    begin_track_spy_placement,
    track_spy_is_queued,
)


def _players(
    strengths: tuple[int, int, int, int],
    sandworm_players: tuple[int, ...] = (),
) -> tuple[PlayerState, ...]:
    return tuple(
        PlayerState(
            player_id=player,
            combat_strength=strength,
            sandworms_conflict=1 if player in sandworm_players else 0,
        )
        for player, strength in enumerate(strengths)
    )


def test_distinct_positive_strengths_receive_first_second_and_third() -> None:
    assert rank_combat(_players((8, 6, 4, 2))) == CombatRanking(
        rewards=(
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.SECOND),
            CombatReward(2, RewardRank.THIRD),
        ),
        winner=0,
    )


def test_zero_strength_never_receives_a_reward() -> None:
    assert rank_combat(_players((4, 2, 0, 0))) == CombatRanking(
        rewards=(
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.SECOND),
        ),
        winner=0,
    )
    assert rank_combat(_players((0, 0, 0, 0))) == CombatRanking((), None)


@pytest.mark.parametrize(
    ("strengths", "expected"),
    (
        (
            (8, 8, 4, 2),
            CombatRanking(
                (
                    CombatReward(0, RewardRank.SECOND),
                    CombatReward(1, RewardRank.SECOND),
                    CombatReward(2, RewardRank.THIRD),
                ),
                None,
            ),
        ),
        (
            (8, 8, 4, 4),
            CombatRanking(
                (
                    CombatReward(0, RewardRank.SECOND),
                    CombatReward(1, RewardRank.SECOND),
                ),
                None,
            ),
        ),
        (
            (8, 8, 8, 4),
            CombatRanking(
                tuple(CombatReward(player, RewardRank.SECOND) for player in range(3)),
                None,
            ),
        ),
        (
            (8, 8, 8, 8),
            CombatRanking(
                tuple(CombatReward(player, RewardRank.SECOND) for player in range(4)),
                None,
            ),
        ),
    ),
)
def test_first_place_ties_follow_four_player_reward_rules(
    strengths: tuple[int, int, int, int],
    expected: CombatRanking,
) -> None:
    assert rank_combat(_players(strengths)) == expected


def test_second_place_tie_gives_each_tied_player_third_reward() -> None:
    assert rank_combat(_players((9, 5, 5, 2))) == CombatRanking(
        (
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.THIRD),
            CombatReward(2, RewardRank.THIRD),
        ),
        winner=0,
    )


def test_third_place_tie_gives_no_third_reward() -> None:
    assert rank_combat(_players((9, 7, 4, 4))) == CombatRanking(
        (
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.SECOND),
        ),
        winner=0,
    )


def test_sandworm_doubles_only_its_owners_reward_assignment() -> None:
    ranking = rank_combat(_players((9, 7, 5, 3), sandworm_players=(1, 3)))

    assert ranking.rewards == (
        CombatReward(0, RewardRank.FIRST, multiplier=1),
        CombatReward(1, RewardRank.SECOND, multiplier=2),
        CombatReward(2, RewardRank.THIRD, multiplier=1),
    )


def test_combat_intrigue_priority_starts_at_first_eligible_clockwise_seat() -> None:
    players = _players((0, 3, 0, 5))
    players = tuple(
        replace(
            player,
            troops_supply=8 if player.player_id in (1, 3) else 9,
            troops_conflict=1 if player.player_id in (1, 3) else 0,
        )
        for player in players
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=2,
        players=players,
    )

    started = begin_combat_intrigue(state).state
    decision = started.decision_stack[-1].decision

    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 3
    assert legal_combat_intrigue_actions(started, 2) == ()


def test_all_participants_must_pass_consecutively() -> None:
    players = tuple(
        PlayerState(
            player_id=player,
            troops_supply=8 if player in (0, 2, 3) else 9,
            troops_conflict=1 if player in (0, 2, 3) else 0,
        )
        for player in range(4)
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=2,
        players=players,
    )
    state = begin_combat_intrigue(state).state

    visited: list[int] = []
    for player in (2, 3, 0):
        action = legal_combat_intrigue_actions(state, player)[0]
        visited.append(action.actor)
        state = apply_combat_intrigue_pass(state, action).state

    assert visited == [2, 3, 0]
    assert state.combat_intrigue_complete is True
    assert state.decision_stack == ()


def test_no_participant_closes_combat_intrigue_immediately() -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        first_player=0,
        players=_players((0, 0, 0, 0)),
    )

    result = begin_combat_intrigue(state)

    assert result.state.combat_intrigue_complete is True
    assert result.events[0].kind == "combat_intrigue_finished"


def test_intrigue_holders_can_pass_while_card_effects_are_deferred() -> None:
    player = PlayerState(
        player_id=0,
        troops_supply=8,
        troops_conflict=1,
        intrigue_cards=("intrigue:unknown",),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        first_player=0,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )

    started = begin_combat_intrigue(state).state

    assert legal_combat_intrigue_actions(started, 0) == (
        DomainAction(action_id="pass_combat_intrigue", actor=0),
    )


def test_unlisted_combat_intrigue_action_is_rejected() -> None:
    player = PlayerState(player_id=0, troops_supply=8, troops_conflict=1)
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        first_player=0,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )
    state = begin_combat_intrigue(state).state

    with pytest.raises(ValueError, match="not a legal"):
        apply_combat_intrigue_pass(
            state,
            DomainAction(action_id="play_unknown", actor=0),
        )


def _reward_state(
    conflict_id: str,
    strengths: tuple[int, int, int, int] = (8, 6, 4, 0),
    *,
    sandworm_players: tuple[int, ...] = (),
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=_players(strengths, sandworm_players),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1", "intrigue:2", "intrigue:3"),
    )


def _settle(state: GameState) -> GameState:
    """Pay the ranked recipients still owed, as the engine's dispatch does.

    Conflict rewards are paid one recipient at a time in rank order, each
    recipient's whole reward, choices included, answered before the next
    recipient is paid (user ruling 2026-10-07, "순위대로 (앱처럼)"). The
    engine calls ``resolve_combat_rewards`` again whenever the stack is
    empty and the rewards are not resolved, which pauses before the next
    recipient (rules/pauses.py) and pays it once the pause is answered;
    this does the same, stopping at the next recipient's choice. A queued
    step (an owed Intrigue draw, a track Spy) is left to the test, as the
    engine resolves it first.
    """

    while (
        not state.combat_rewards_resolved
        and not state.pending_intrigue_draws
        and not state.pending_track_spies
    ):
        frame = top_frame(state)
        if pause_is_pending(state):
            state = answer_pause(state).state
        elif not state.decision_stack:
            state = resolve_combat_rewards(state).state
        elif frame is not None and frame.kind == FrameKind.COMBAT_REWARD_ICONS:
            # v150 (stage B2, OQ-112): a recipient's reward is a window of
            # icon rows; the older engine's order answers them up to the
            # first choice an icon opens.
            state = settle_reward_window(state)
        else:
            break
    return state


def _paid(state: GameState) -> GameState:
    """Open the next recipient's reward window and answer it in the older
    engine's order, up to the first choice an icon opens (stage B2, OQ-112)."""

    return settle_reward_window(resolve_combat_rewards(state).state)


def _play_out_rewards(
    engine: UprisingRulesEngine, state: GameState
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Answer the reward windows and the pauses between recipients through
    the engine until the rewards are resolved or another decision is due,
    with the events those steps produced (stage B2, OQ-112)."""

    events: list[GameEvent] = []
    for _ in range(64):
        frame = top_frame(state)
        if state.combat_rewards_resolved or frame is None:
            break
        if frame.kind == FrameKind.PAUSE:
            result = engine.apply(state, pause_outcome(state))
        elif frame.kind == FrameKind.COMBAT_REWARD_ICONS:
            assert isinstance(frame.decision, PlayerDecision)
            legacy = legacy_combat_reward_icon(state, frame.decision.owner)
            assert legacy is not None
            # Stage B3d-1: the window offers the icon as its steps.
            result = apply_whole(engine, state, legacy)
        else:
            break
        state = result.state
        events.extend(result.events)
    return state, tuple(events)


def _answer_window(state: GameState) -> RuleResult:
    """``settle_reward_window`` with the events it produced collected."""

    events: list[GameEvent] = []
    while (frame := top_frame(state)) is not None and (
        frame.kind == FrameKind.COMBAT_REWARD_ICONS
    ):
        assert isinstance(frame.decision, PlayerDecision)
        answer = legacy_combat_reward_icon(state, frame.decision.owner)
        assert answer is not None
        result = apply_combat_reward_icon(state, answer)
        state = result.state
        events.extend(result.events)
    return RuleResult(state=state, events=tuple(events))


def test_desert_mouse_rewards_apply_by_rank() -> None:
    # v150 (stage B2, OQ-112): each recipient answers a window of reward
    # icons; _settle answers them in the older engine's order.
    state = _settle(
        resolve_combat_rewards(_reward_state("skirmish_desert_mouse")).state
    )

    assert tuple(player.resources.solari for player in state.players) == (
        2,
        3,
        2,
        0,
    )
    assert state.combat_rewards_resolved is True
    assert state.decision_stack == ()


def test_combat_reward_event_records_the_reward_s_victory_points() -> None:
    # ITEM 5 (UI): the log line reporting a Conflict's outcome reads the
    # reward events, so the payload must carry the Victory Points a reward
    # row grants, not just the resources resolve_combat_rewards applies to
    # the player above. Battle for Arrakeen's first-place row grants 1
    # Victory Point alongside its Control space.
    #
    # v150 (stage B2, OQ-112): the reward is paid icon by icon. The header
    # (combat_reward_gained) carries the rank and multiplier, and each icon
    # row logs combat_reward_icon_resolved with what it gave.
    opened = resolve_combat_rewards(_reward_state("battle_for_arrakeen"))
    events = (*opened.events, *_answer_window(opened.state).events)
    first_place = next(
        event
        for event in events
        if event.kind == "combat_reward_gained" and dict(event.payload)["rank"] == 1
    )
    assert dict(first_place.payload) == {"multiplier": 1, "player": 0, "rank": 1}
    icons = {
        dict(event.payload)["effect"]: dict(event.payload)
        for event in events
        if event.kind == "combat_reward_icon_resolved"
    }
    # Zero amounts are left out (cleanup-2c-3, the event grammar).
    assert icons["control"] == {
        "effect": "control",
        "player": 0,
        "rank": 1,
        "space_id": "arrakeen",
    }
    assert icons["victory_points"] == {
        "effect": "victory_points",
        "player": 0,
        "rank": 1,
        "victory_points": 1,
    }


def test_combat_reward_event_doubles_victory_points_for_a_sandworm() -> None:
    opened = resolve_combat_rewards(
        _reward_state("battle_for_arrakeen", sandworm_players=(0,))
    )
    events = (*opened.events, *_answer_window(opened.state).events)
    first_place = next(
        event
        for event in events
        if event.kind == "combat_reward_gained" and dict(event.payload)["rank"] == 1
    )
    assert dict(first_place.payload)["multiplier"] == 2
    # v150 (stage B2, OQ-112): the doubled Victory Points ride on the icon row.
    points = next(
        dict(event.payload)
        for event in events
        if event.kind == "combat_reward_icon_resolved"
        and dict(event.payload)["effect"] == "victory_points"
    )
    assert points["victory_points"] == 2


def _standing(events: tuple[GameEvent, ...]) -> list[tuple[int, int, int, int]]:
    """(player, rank, strength, multiplier) of each combat_standing event."""

    rows = []
    for event in events:
        if event.kind != "combat_standing":
            continue
        payload = dict(event.payload)
        assert event.visible_to is None
        rows.append(
            (
                cast(int, payload["player"]),
                cast(int, payload["rank"]),
                cast(int, payload["strength"]),
                cast(int, payload["multiplier"]),
            )
        )
    return rows


def test_the_rewards_open_with_the_whole_public_standing() -> None:
    # UI (user request 2026-10-08, "전투 단계 종료 때 전투 최종 순위도 그렇게
    # 보여지면 좋겠고"): the rewards are paid one recipient at a time and the
    # strengths are cleared at cleanup, so the standing is logged once, up
    # front. A fourth seat with strength but no reward row comes after the
    # recipients with rank 0.
    state = _reward_state("skirmish_desert_mouse", strengths=(8, 6, 4, 2))

    result = resolve_combat_rewards(state)

    assert _standing(result.events) == [
        (0, 1, 8, 1),
        (1, 2, 6, 1),
        (2, 3, 4, 1),
        (3, 0, 2, 1),
    ]
    first = next(event for event in result.events if event.kind == "combat_standing")
    assert dict(first.payload)["conflict_id"] == "skirmish_desert_mouse"
    assert result.events.index(first) == 0


def test_the_standing_follows_ties_sandworms_and_units_without_strength() -> None:
    # A first-place tie shares the second reward and the next seat takes the
    # third (rank_combat, [Main p. 14]); tied recipients are listed in turn
    # order from the First Player (OQ-002). A sandworm's doubled row says so,
    # a seat with units but no strength is in the standing with rank 0, and
    # a seat with neither is not.
    players = list(_players((5, 7, 7, 0), sandworm_players=(2,)))
    for seat, troops in ((0, 2), (3, 1)):
        players[seat] = replace(
            players[seat],
            troops_conflict=troops,
            troops_supply=players[seat].troops_supply - troops,
        )
    state = replace(
        _reward_state("skirmish_desert_mouse"), players=tuple(players), first_player=2
    )

    assert _standing(resolve_combat_rewards(state).events) == [
        (2, 2, 7, 2),
        (1, 2, 7, 1),
        (0, 3, 5, 1),
        (3, 0, 0, 1),
    ]

    nobody = replace(state, players=_players((0, 0, 0, 0)))
    assert _standing(resolve_combat_rewards(nobody).events) == []


def test_the_standing_is_logged_once_however_the_rewards_are_paid() -> None:
    # Skirmish (Crysknife) stops at its winner's Influence choice; the
    # engine's next call pays the others without a second standing.
    engine = UprisingRulesEngine()
    state = replace(
        _reward_state("skirmish_crysknife", strengths=(8, 6, 4, 0)),
        conflict_deck=("skirmish_desert_mouse",),
    )

    opened = _advance_automatic(RuleResult(state=state))
    # v150 (stage B2, OQ-112): the winner's Influence icon is a row of its
    # reward window; answering it opens the choice.
    windowed = answer_reward_windows(engine, opened.state)
    answered = apply_whole(
        engine,
        windowed,
        DomainAction(
            action_id="choose_combat_reward_influence",
            actor=0,
            arguments=(("faction", "emperor"),),
        ),
    )

    assert _standing(opened.events) == [(0, 1, 8, 1), (1, 2, 6, 1), (2, 3, 4, 1)]
    assert _standing(answered.events) == []


def test_the_engine_pays_the_next_recipient_only_after_the_winner_answers() -> None:
    """Rewards go one recipient at a time, the winner's choice first.

    "The player with the highest strength wins the Conflict and gains the
    first reward on the Conflict card. The player with the second highest
    strength gains the second reward." [Main p. 14] is silent on the order
    between recipients. User ruling 2026-10-07 ("순위대로 (앱처럼)"): each
    recipient's whole reward, choices included, before the next recipient
    is paid. Skirmish (Crysknife) gives its winner an Influence choice and
    its 2nd place 1 spice and an Intrigue card, its 3rd place 1 spice.
    """

    engine = UprisingRulesEngine()
    state = replace(
        _reward_state("skirmish_crysknife", strengths=(8, 6, 4, 0)),
        conflict_deck=("skirmish_desert_mouse",),
    )

    opened = _advance_automatic(RuleResult(state=state))

    # v150 (stage B2, OQ-112): the winner's reward is a window of icon rows;
    # its Influence row opens the choice.
    assert opened.state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_ICONS
    windowed = answer_reward_windows(engine, opened.state)
    assert windowed.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE
    assert [
        dict(event.payload)["player"]
        for event in opened.events
        if event.kind == "combat_reward_gained"
    ] == [0]
    assert opened.state.combat_rewards_paid == 1
    assert opened.state.combat_rewards_resolved is False
    assert opened.state.players[1] == state.players[1]
    assert opened.state.players[2] == state.players[2]
    assert opened.state.intrigue_deck == state.intrigue_deck

    answered = apply_whole(
        engine,
        windowed,
        DomainAction(
            action_id="choose_combat_reward_influence",
            actor=0,
            arguments=(("faction", "emperor"),),
        ),
    )

    # The winner's answer stops at a pause before the 2nd place is paid
    # (rules/pauses.py): that payment draws an Intrigue card, a reveal, and
    # the play server lets the winner take its choice back until then.
    assert answered.state.players[0].influence.emperor == 1
    assert answered.state.decision_stack[-1].kind == FrameKind.PAUSE
    assert answered.state.players[1] == state.players[1]
    assert answered.state.intrigue_deck == state.intrigue_deck
    # The 2nd and the 3rd place each answer a window (a pause in between).
    paid_state, paid_events = _play_out_rewards(engine, answered.state)

    kinds = [
        (event.kind, dict(event.payload).get("player"))
        for event in (*answered.events, *paid_events)
        if event.kind in ("influence_gained", "combat_reward_gained")
    ]
    assert kinds == [
        ("influence_gained", 0),
        ("combat_reward_gained", 1),
        ("combat_reward_gained", 2),
    ]
    assert paid_state.players[1].resources.spice == 1
    assert paid_state.players[1].intrigue_cards == ("intrigue:0",)
    assert paid_state.players[2].resources.spice == 1


def test_ornithopter_rewards_draw_intrigue_in_rank_order() -> None:
    result = _settle(
        resolve_combat_rewards(_reward_state("skirmish_ornithopter")).state
    )

    assert result.players[0].intrigue_cards == ("intrigue:0",)
    assert result.players[1].intrigue_cards == ("intrigue:1",)
    assert result.players[2].intrigue_cards == ("intrigue:2",)
    assert result.intrigue_deck == ("intrigue:3",)


def test_tied_reward_group_resolves_in_turn_order_from_the_first_player() -> None:
    # OQ-002 (designer ruling, 2026-09-09): when the order of Combat rewards
    # can matter, tied recipients resolve in turn order from the First
    # Player. The shared Intrigue deck split pins it here.
    tied = replace(
        _reward_state("skirmish_ornithopter", strengths=(8, 8, 4, 0)),
        first_player=1,
    )

    result = _settle(resolve_combat_rewards(tied).state)

    assert result.players[1].intrigue_cards == ("intrigue:0",)
    assert result.players[0].intrigue_cards == ("intrigue:1",)
    assert result.players[2].intrigue_cards == ("intrigue:2",)
    assert result.intrigue_deck == ("intrigue:3",)


def test_tied_trash_choices_open_one_seat_at_a_time_from_the_first_player() -> None:
    """The tied seats' trash choices open one seat at a time.

    "The player with the highest strength wins the Conflict and gains the
    first reward on the Conflict card. The player with the second highest
    strength gains the second reward." [Main p. 14] gives each rank its row
    but not the order between recipients. User ruling 2026-10-07 ("순위대로
    (앱처럼)"): each recipient's whole reward, choices included, is answered
    before the next recipient is paid; tied recipients go in turn order from
    the First Player (OQ-002, designer ruling). Both tied seats' frames used
    to open together.
    """

    tied = _reward_state("trade_dispute", strengths=(8, 8, 4, 0))
    players = tuple(
        replace(player, hand=(f"p{player.player_id}:hand",))
        if player.player_id in (0, 1)
        else player
        for player in tied.players
    )
    tied = replace(tied, players=players, first_player=1)

    state = _paid(tied)

    # The First Player's second-place row is paid and its trash is open;
    # the other tied seat and the third place wait.
    assert [dict(frame.context)["player"] for frame in state.decision_stack] == [1]
    assert state.players[1].resources.spice == 1
    assert state.players[0].resources.spice == 0
    assert state.players[2] == tied.players[2]
    state = apply_combat_reward_trash(
        state, legal_combat_reward_trash_actions(state, 1)[0]
    ).state

    state = _settle(state)

    assert [dict(frame.context)["player"] for frame in state.decision_stack] == [0]
    assert state.players[0].resources.spice == 1
    assert state.players[2] == tied.players[2]
    state = apply_combat_reward_trash(
        state, legal_combat_reward_trash_actions(state, 0)[0]
    ).state

    state = _settle(state)

    assert state.players[2].troops_garrison == tied.players[2].troops_garrison + 1
    assert state.decision_stack == ()
    assert state.combat_rewards_resolved is True


def test_rank_combat_lists_tied_recipients_from_the_first_player() -> None:
    from dune_imperium.rules.combat import rank_combat

    players = _players((8, 8, 4, 0))
    assert [reward.player for reward in rank_combat(players).rewards] == [0, 1, 2]
    assert [
        reward.player for reward in rank_combat(players, first_player=1).rewards
    ] == [1, 0, 2]
    assert [
        reward.player for reward in rank_combat(players, first_player=3).rewards
    ] == [0, 1, 2]


def test_sandworm_doubles_the_assigned_reward_row() -> None:
    result = _settle(
        resolve_combat_rewards(
            _reward_state("skirmish_ornithopter", sandworm_players=(1,))
        ).state
    )

    assert result.players[1].resources.solari == 4
    assert result.players[1].intrigue_cards == (
        "intrigue:1",
        "intrigue:2",
    )
    assert result.players[2].intrigue_cards == ("intrigue:3",)


def test_crysknife_queues_and_applies_influence_choice() -> None:
    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(players[0], influence=Influence(emperor=1))
    state = replace(state, players=tuple(players))

    rewarded = _paid(state)
    actions = legal_combat_reward_influence_actions(rewarded, 0)

    assert rewarded.combat_rewards_resolved is False
    assert {dict(action.arguments)["faction"] for action in actions} == {
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    }
    emperor = next(
        action for action in actions if dict(action.arguments)["faction"] == "emperor"
    )
    resolved = _settle(apply_combat_reward_influence(rewarded, emperor).state)

    assert resolved.players[0].influence.emperor == 2
    assert resolved.players[0].victory_points == 2
    assert resolved.combat_rewards_resolved is True


def test_combat_influence_choice_resolves_track_bonus_and_alliance() -> None:
    """The winner's Influence-choice draw comes before the 2nd place's draw.

    [Main p. 14] gives the rewards by rank ("The player with the highest
    strength wins the Conflict and gains the first reward on the Conflict
    card. The player with the second highest strength gains the second
    reward.") but not the order between recipients. User ruling 2026-10-07
    ("순위대로 (앱처럼)"): each recipient's whole reward, choices included,
    before the next recipient is paid. So Bene Gesserit 4's Intrigue card
    [Main p. 7] takes the deck's top card, and the 2nd place's printed
    Intrigue card the next one; the 2nd place used to draw first.
    """

    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(players[0], influence=Influence(bene_gesserit=3))
    state = replace(
        state,
        players=tuple(players),
        intrigue_deck=("track_bonus_intrigue", *state.intrigue_deck),
    )
    rewarded = _paid(state)
    assert rewarded.players[1].intrigue_cards == ()
    action = next(
        candidate
        for candidate in legal_combat_reward_influence_actions(rewarded, 0)
        if dict(candidate.arguments)["faction"] == "bene_gesserit"
    )

    resolved = apply_combat_reward_influence(rewarded, action).state

    assert resolved.players[0].influence.bene_gesserit == 4
    assert resolved.players[0].intrigue_cards == ("track_bonus_intrigue",)
    assert resolved.players[0].alliance_faction_ids == ("bene_gesserit",)
    assert resolved.players[0].victory_points == 2
    assert resolved.players[1].intrigue_cards == ()

    settled = _settle(resolved)

    assert settled.players[1].intrigue_cards == ("intrigue:0",)
    assert settled.combat_rewards_resolved is True


def test_the_winner_s_influence_draw_takes_the_last_intrigue_card_first() -> None:
    """With one Intrigue card left, the winner's choice draws it.

    User ruling 2026-10-07 ("순위대로 (앱처럼)"): each recipient's whole
    reward, choices included, before the next recipient is paid; [Main
    p. 14] ("The player with the highest strength wins the Conflict and
    gains the first reward on the Conflict card. The player with the second
    highest strength gains the second reward.") is silent on that order.
    Skirmish (Crysknife)'s winner reaches Bene Gesserit 4 and draws the last
    card [Main p. 7]; the 2nd place's printed Intrigue card then finds the
    deck empty and the discard is reshuffled [FAQ p. 2].
    """

    state = replace(
        _with_influence(
            _reward_state("skirmish_crysknife"), 0, Influence(bene_gesserit=3)
        ),
        intrigue_deck=("intrigue:last",),
        intrigue_discard=("intrigue:discarded",),
    )
    rewarded = _paid(state)
    bene_gesserit = next(
        action
        for action in legal_combat_reward_influence_actions(rewarded, 0)
        if dict(action.arguments)["faction"] == "bene_gesserit"
    )

    chosen = apply_combat_reward_influence(rewarded, bene_gesserit).state

    assert chosen.players[0].intrigue_cards == ("intrigue:last",)
    assert chosen.intrigue_deck == ()
    assert chosen.pending_intrigue_draws == ()
    assert chosen.players[1].resources.spice == 0

    second = _settle(chosen)

    assert second.players[1].resources.spice == 1
    assert [(player, count) for player, count, _ in second.pending_intrigue_draws] == [
        (1, 1)
    ]
    drawn = _reshuffle_and_draw(second)
    assert drawn.players[1].intrigue_cards == ("intrigue:discarded",)
    assert _settle(drawn).combat_rewards_resolved is True


def _bene_gesserit_three_with_an_empty_deck(conflict_id: str) -> GameState:
    # The first-place winner (Bene Gesserit 3) chooses with the deck empty
    # and one card in the discard. The winner's reward is answered before
    # the 2nd place's Intrigue card is drawn (user ruling 2026-10-07,
    # "순위대로 (앱처럼)"), so the deck starts empty.
    state = _with_influence(
        _reward_state(conflict_id), 0, Influence(bene_gesserit=3)
    )
    return replace(
        state,
        intrigue_deck=(),
        intrigue_discard=("intrigue:discarded",),
    )


def _reshuffle_and_draw(state: GameState) -> GameState:
    from dune_imperium.core import ChanceDecision, ChanceResolver
    from dune_imperium.rules.intrigue_deck import (
        apply_intrigue_reshuffle,
        intrigue_draw_is_queued,
        resolve_pending_intrigue_draw,
    )

    assert intrigue_draw_is_queued(state)
    opened = resolve_pending_intrigue_draw(state).state
    assert opened.decision_stack[-1].kind == "intrigue_reshuffle"
    decision = UprisingRulesEngine().current_decision(opened)
    assert isinstance(decision, ChanceDecision)
    return apply_intrigue_reshuffle(
        opened, ChanceResolver(seed=1).resolve(decision)
    ).state


def test_bene_gesserit_stays_a_choice_when_the_intrigue_deck_is_empty() -> None:
    # Skirmish (Crysknife) 1st place prints the choose-Influence icon:
    # "Choose any one of the four Factions" [Main p. 20]. Reaching Bene
    # Gesserit 4 draws an Intrigue card, and "In the rare case that you
    # exhaust the Intrigue deck, shuffle the discarded Intrigue cards to form
    # a new deck" [FAQ p. 2]; an empty deck used to hide the Faction.
    #
    # The winner's whole reward is answered before the 2nd place is paid
    # (user ruling 2026-10-07, "순위대로 (앱처럼)": each recipient's whole
    # reward, choices included, before the next recipient is paid; [Main
    # p. 14] "The player with the highest strength wins the Conflict and
    # gains the first reward on the Conflict card. The player with the
    # second highest strength gains the second reward." is silent on that
    # order), so the reshuffled card is the winner's and the 2nd place's
    # Intrigue card comes up short afterwards.
    rewarded = _paid(_bene_gesserit_three_with_an_empty_deck("skirmish_crysknife"))
    assert rewarded.intrigue_deck == ()
    assert rewarded.players[1].resources.spice == 0
    actions = legal_combat_reward_influence_actions(rewarded, 0)
    assert {dict(action.arguments)["faction"] for action in actions} == {
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    }
    bene_gesserit = next(
        action
        for action in actions
        if dict(action.arguments)["faction"] == "bene_gesserit"
    )

    chosen = apply_combat_reward_influence(rewarded, bene_gesserit).state

    assert chosen.players[0].influence.bene_gesserit == 4
    assert chosen.players[0].alliance_faction_ids == ("bene_gesserit",)
    assert [(player, count) for player, count, _ in chosen.pending_intrigue_draws] == [
        (0, 1)
    ]
    drawn = _reshuffle_and_draw(chosen)
    assert drawn.players[0].intrigue_cards == ("intrigue:discarded",)
    assert drawn.intrigue_discard == ()
    assert drawn.players[1].resources.spice == 0

    from dune_imperium.rules.intrigue_deck import resolve_pending_intrigue_draw

    second = _settle(drawn)
    assert second.players[1].resources.spice == 1
    short = resolve_pending_intrigue_draw(second)
    assert [
        dict(event.payload)
        for event in short.events
        if event.kind == "intrigue_draw_short"
    ] == [{"drawn": 0, "player": 1, "requested": 1, "short": 1}]
    assert short.state.players[1].intrigue_cards == ()
    assert _settle(short.state).combat_rewards_resolved is True


def test_bene_gesserit_is_chosen_with_both_intrigue_piles_empty() -> None:
    # With nothing to reshuffle the Influence and the Alliance still apply;
    # only the Intrigue card is missing [Main p. 20] [FAQ p. 2]. The winner's
    # draw comes up short before the 2nd place is paid, and the 2nd place's
    # printed Intrigue card comes up short after it (user ruling 2026-10-07,
    # "순위대로 (앱처럼)": each recipient's whole reward, choices included,
    # before the next recipient is paid; [Main p. 14] "The player with the
    # highest strength wins the Conflict and gains the first reward on the
    # Conflict card. The player with the second highest strength gains the
    # second reward." is silent on that order).
    state = replace(
        _bene_gesserit_three_with_an_empty_deck("skirmish_crysknife"),
        intrigue_discard=(),
    )
    rewarded = _paid(state)
    bene_gesserit = next(
        action
        for action in legal_combat_reward_influence_actions(rewarded, 0)
        if dict(action.arguments)["faction"] == "bene_gesserit"
    )

    chosen = apply_combat_reward_influence(rewarded, bene_gesserit).state
    from dune_imperium.rules.intrigue_deck import resolve_pending_intrigue_draw

    resolved = resolve_pending_intrigue_draw(chosen)
    drawn = resolved.state

    # The missing card is logged (user ruling 2026-10-02, L2-Q4).
    assert [
        dict(event.payload)
        for event in resolved.events
        if event.kind == "intrigue_draw_short"
    ] == [{"drawn": 0, "player": 0, "requested": 1, "short": 1}]
    assert drawn.decision_stack == ()
    assert drawn.pending_intrigue_draws == ()
    assert drawn.players[0].influence.bene_gesserit == 4
    assert drawn.players[0].alliance_faction_ids == ("bene_gesserit",)
    assert drawn.players[0].intrigue_cards == ()
    assert drawn.players[1].resources.spice == 0

    second = resolve_pending_intrigue_draw(_settle(drawn))
    assert [
        dict(event.payload)
        for event in second.events
        if event.kind == "intrigue_draw_short"
    ] == [{"drawn": 0, "player": 1, "requested": 1, "short": 1}]
    assert second.state.players[1].resources.spice == 1
    assert _settle(second.state).combat_rewards_resolved is True


def test_bene_gesserit_is_the_last_faction_left_with_an_empty_deck() -> None:
    # Spice Freighters 1st place (choose-Influence icon [Main p. 20]) with
    # every other track at the top: Bene Gesserit is still offered, so the
    # confirm without a Faction is not (OQ-060 covers only a full track).
    # No Intrigue card is drawn below 1st place here, so the deck starts empty.
    state = replace(
        _bene_gesserit_three_with_an_empty_deck("spice_freighters"),
        intrigue_deck=(),
    )
    state = _with_influence(
        state, 0, Influence(emperor=6, spacing_guild=6, bene_gesserit=3, fremen=6)
    )
    rewarded = _paid(state)

    actions = legal_combat_reward_influence_actions(rewarded, 0)

    assert [action.action_id for action in actions] == [
        "choose_combat_reward_influence"
    ]
    assert [dict(action.arguments)["faction"] for action in actions] == [
        "bene_gesserit"
    ]


def test_propaganda_offers_bene_gesserit_when_the_intrigue_deck_is_empty() -> None:
    # Propaganda 1st place: "Choose two:" of the four Faction icons [Propaganda
    # card], with no condition on the Intrigue deck [Main p. 20] [FAQ p. 2].
    # The winner's two picks, and the Intrigue card Bene Gesserit 4 draws,
    # come before the 2nd place's reward (user ruling 2026-10-07, "순위대로
    # (앱처럼)": each recipient's whole reward, choices included, before the
    # next recipient is paid; [Main p. 14] "The player with the highest
    # strength wins the Conflict and gains the first reward on the Conflict
    # card. The player with the second highest strength gains the second
    # reward." is silent on that order).
    rewarded = _paid(_bene_gesserit_three_with_an_empty_deck("propaganda"))
    assert rewarded.intrigue_deck == ()
    assert rewarded.players[1].resources.spice == 0
    first = legal_distinct_combat_reward_influence_actions(rewarded, 0)
    assert "bene_gesserit" in {dict(action.arguments)["faction"] for action in first}
    named = apply_distinct_combat_reward_influence(
        rewarded,
        next(
            action
            for action in first
            if dict(action.arguments)["faction"] == "bene_gesserit"
        ),
    ).state
    fremen = next(
        action
        for action in legal_distinct_combat_reward_influence_actions(named, 0)
        if dict(action.arguments)["faction"] == "fremen"
    )

    chosen = apply_distinct_combat_reward_influence(named, fremen).state

    assert chosen.players[0].influence.bene_gesserit == 4
    assert chosen.players[0].influence.fremen == 1
    assert chosen.decision_stack == ()
    assert chosen.combat_rewards_resolved is False
    drawn = _reshuffle_and_draw(chosen)
    assert drawn.players[0].intrigue_cards == ("intrigue:discarded",)
    assert drawn.players[1].resources.spice == 0

    from dune_imperium.rules.intrigue_deck import resolve_pending_intrigue_draw

    second = _settle(drawn)
    assert second.players[1].resources.spice == 3
    short = resolve_pending_intrigue_draw(second).state
    assert short.players[1].intrigue_cards == ()
    settled = _settle(short)
    assert settled.players[2].resources.spice == 3
    assert settled.combat_rewards_resolved is True


def test_combat_rewards_require_completed_intrigue_and_only_resolve_once() -> None:
    state = _reward_state("skirmish_desert_mouse")

    with pytest.raises(ValueError, match="Intrigue must finish"):
        resolve_combat_rewards(replace(state, combat_intrigue_complete=False))

    resolved = _settle(resolve_combat_rewards(state).state)
    assert resolved.combat_rewards_resolved is True
    with pytest.raises(ValueError, match="already resolved"):
        resolve_combat_rewards(resolved)


def test_propaganda_requires_two_distinct_factions() -> None:
    state = _paid(_reward_state("propaganda"))
    first_actions = legal_distinct_combat_reward_influence_actions(state, 0)
    emperor = next(
        action
        for action in first_actions
        if dict(action.arguments)["faction"] == "emperor"
    )
    state = apply_distinct_combat_reward_influence(state, emperor).state
    # "Choose two": nothing moves until both Factions are named (designer
    # ruling, OQ-057), so the second pick cannot follow the first's Intrigue.
    assert state.players[0].influence.emperor == 0

    second_actions = legal_distinct_combat_reward_influence_actions(state, 0)

    assert "emperor" not in {
        dict(action.arguments)["faction"] for action in second_actions
    }
    state = apply_distinct_combat_reward_influence(state, second_actions[0]).state
    assert state.players[0].influence.emperor == 1
    assert (
        sum(
            (
                state.players[0].influence.emperor,
                state.players[0].influence.spacing_guild,
                state.players[0].influence.bene_gesserit,
                state.players[0].influence.fremen,
            )
        )
        == 2
    )
    assert _settle(state).combat_rewards_resolved is True


def test_sandworm_restarts_propaganda_distinct_group() -> None:
    state = _paid(_reward_state("propaganda", sandworm_players=(0,)))

    chosen: list[str] = []
    for faction in ("emperor", "spacing_guild", "emperor", "spacing_guild"):
        # v150 (stage B2, OQ-112): the window offers the doubled set's second
        # copy once the first copy's pair is answered.
        state = settle_reward_window(state)
        actions = legal_distinct_combat_reward_influence_actions(state, 0)
        action = next(
            candidate
            for candidate in actions
            if dict(candidate.arguments)["faction"] == faction
        )
        chosen.append(faction)
        state = apply_distinct_combat_reward_influence(state, action).state

    assert chosen == ["emperor", "spacing_guild", "emperor", "spacing_guild"]
    assert state.players[0].influence.emperor == 2
    assert state.players[0].influence.spacing_guild == 2
    assert state.players[0].victory_points == 3
    assert _settle(state).combat_rewards_resolved is True


def _with_influence(state: GameState, player: int, influence: Influence) -> GameState:
    players = list(state.players)
    players[player] = replace(players[player], influence=influence)
    return replace(state, players=tuple(players))


_INFLUENCE_CONFIRM = DomainAction(
    action_id="resolve_combat_influence_without_faction", actor=0
)


def test_influence_choice_with_no_faction_below_the_top_asks_for_a_confirm() -> None:
    # OQ-060: a cube at the top of its track cannot rise, so Skirmish
    # (Crysknife)'s "choose a Faction" has nothing to offer once every track
    # is at 6, and the choice is lost like a plain gain at the top. The
    # engine no longer drops it unasked: the window opens and its owner
    # confirms the loss (user ruling 2026-09-30, "결정 창 없이 자동으로
    # 넘어가는 곳도 모두 결정 창을 연다").
    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _with_influence(_reward_state("skirmish_crysknife"), 0, full)

    resolved = settle_reward_window(_advance_automatic(RuleResult(state=state)).state)

    frame = resolved.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_REWARD_INFLUENCE
    assert resolved.combat_rewards_resolved is False
    assert UprisingRulesEngine().legal_actions(resolved, 0) == (_INFLUENCE_CONFIRM,)
    assert {
        combat_reward_influence_block(frame, resolved.players[0], faction)
        for faction in Faction
    } == {CombatInfluenceBlock.TOP}
    result = apply_combat_influence_without_faction(resolved, _INFLUENCE_CONFIRM)
    assert result.state.decision_stack == ()
    assert _settle(result.state).combat_rewards_resolved is True
    assert result.state.players[0].influence == full
    assert [(event.event_id, event.kind) for event in result.events] == [
        (
            "round:1:combat_reward:influence_unavailable:0:0",
            "combat_reward_influence_unavailable",
        )
    ]
    with pytest.raises(ValueError, match="confirm without a Faction"):
        apply_combat_influence_without_faction(result.state, _INFLUENCE_CONFIRM)


def test_the_influence_confirm_is_never_offered_beside_a_faction() -> None:
    # The gain is mandatory while a Faction can take it: one track below 6
    # is offered alone, and the confirm cannot be pressed instead.
    state = _with_influence(
        _reward_state("skirmish_crysknife"),
        0,
        Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=2),
    )
    resolved = _paid(state)

    actions = legal_combat_reward_influence_actions(resolved, 0)

    assert [dict(action.arguments)["faction"] for action in actions] == ["fremen"]
    with pytest.raises(ValueError, match="confirm without a Faction"):
        apply_combat_influence_without_faction(resolved, _INFLUENCE_CONFIRM)


def test_propaganda_with_one_faction_below_the_top_pays_that_one() -> None:
    # "Choose two" with only one Faction left below 6: the first pick is
    # named, the second frame has no Faction to offer, and its confirm still
    # pays the named pick (OQ-060 with OQ-057's choose-two atomicity).
    state = _with_influence(
        _reward_state("propaganda"),
        0,
        Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=1),
    )
    resolved = _paid(state)

    actions = legal_distinct_combat_reward_influence_actions(resolved, 0)
    assert [dict(action.arguments)["faction"] for action in actions] == ["fremen"]
    named = apply_distinct_combat_reward_influence(resolved, actions[0]).state
    assert named.players[0].influence.fremen == 1
    assert legal_distinct_combat_reward_influence_actions(named, 0) == (
        _INFLUENCE_CONFIRM,
    )
    frame = named.decision_stack[-1]
    assert {
        faction: combat_reward_influence_block(frame, named.players[0], faction)
        for faction in Faction
    } == {
        Faction.EMPEROR: CombatInfluenceBlock.TOP,
        Faction.SPACING_GUILD: CombatInfluenceBlock.TOP,
        Faction.BENE_GESSERIT: CombatInfluenceBlock.TOP,
        Faction.FREMEN: CombatInfluenceBlock.NAMED,
    }

    result = apply_combat_influence_without_faction(named, _INFLUENCE_CONFIRM)

    assert result.state.players[0].influence.fremen == 2
    # One Victory Point for the tier-III win, one for reaching Fremen 2.
    assert result.state.players[0].victory_points == 2
    assert _settle(result.state).combat_rewards_resolved is True
    assert result.events[0].kind == "combat_reward_influence_unavailable"


def test_sandworm_propaganda_second_set_is_confirmed_once_the_tracks_fill() -> None:
    # The second set of a doubled Propaganda is judged after the first set
    # moved the cubes: with Emperor and Guild at 5 and the others at 6, the
    # first set fills both tracks and the second set has nothing left, so
    # each of its two picks is a confirm.
    state = _with_influence(
        _reward_state("propaganda", sandworm_players=(0,)),
        0,
        Influence(emperor=5, spacing_guild=5, bene_gesserit=6, fremen=6),
    )
    working = _paid(state)
    # v150 (stage B2, OQ-112): the window holds the doubled set's second
    # copy back; the first copy's two picks are open above it.
    assert [frame.kind for frame in working.decision_stack] == [
        FrameKind.COMBAT_REWARD_ICONS,
        FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE,
        FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE,
    ]
    for faction in ("emperor", "spacing_guild"):
        action = next(
            candidate
            for candidate in legal_distinct_combat_reward_influence_actions(
                working, 0
            )
            if dict(candidate.arguments)["faction"] == faction
        )
        working = apply_distinct_combat_reward_influence(working, action).state
    assert working.players[0].influence.emperor == 6
    assert working.players[0].influence.spacing_guild == 6
    # The second copy's two picks open when the window is answered again,
    # judged on the cubes the first copy moved.
    working = settle_reward_window(working)
    assert len(working.decision_stack) == 2

    for _ in range(2):
        assert legal_distinct_combat_reward_influence_actions(working, 0) == (
            _INFLUENCE_CONFIRM,
        )
        working = apply_combat_influence_without_faction(
            working, _INFLUENCE_CONFIRM
        ).state

    assert working.decision_stack == ()
    assert _settle(working).combat_rewards_resolved is True
    assert legal_distinct_combat_reward_influence_actions(working, 0) == ()


def test_tier_two_resources_troops_and_fixed_influence_resolve() -> None:
    state = _reward_state("protect_the_sietches")
    players = list(state.players)
    players[0] = replace(players[0], influence=Influence(fremen=1))
    state = replace(state, players=tuple(players))

    result = _settle(resolve_combat_rewards(state).state)

    assert result.players[0].resources.water == 2
    assert result.players[0].troops_garrison == 4
    assert result.players[0].influence.fremen == 2
    assert result.players[0].victory_points == 2
    assert result.players[1].resources.spice == 3
    assert result.players[1].troops_garrison == 4
    assert result.players[2].resources.spice == 2


def test_contract_icons_become_two_solari_when_choam_is_off() -> None:
    result = _settle(resolve_combat_rewards(_reward_state("choam_security")).state)

    assert result.players[0].resources.solari == 2
    assert result.players[0].influence.spacing_guild == 1
    assert result.players[1].resources.solari == 2
    assert result.players[1].resources.water == 2
    assert result.players[2].intrigue_cards == ("intrigue:0",)


def test_control_reward_replaces_an_opponents_marker() -> None:
    state = _reward_state("siege_of_arrakeen")
    players = list(state.players)
    players[1] = replace(players[1], control_space_ids=("arrakeen",))
    state = replace(state, players=tuple(players))

    result = _settle(resolve_combat_rewards(state).state)

    assert result.players[0].control_space_ids == ("arrakeen",)
    assert result.players[1].control_space_ids == ()


def test_sandworm_does_not_double_control_marker() -> None:
    result = _settle(
        resolve_combat_rewards(
            _reward_state("siege_of_arrakeen", sandworm_players=(0,))
        ).state
    )

    assert result.players[0].control_space_ids == ("arrakeen",)
    assert result.players[0].resources.solari == 4
    assert result.players[0].troops_garrison == 7


def test_seize_spice_refinery_skips_spy_choice_when_first_place_is_tied() -> None:
    tied = _reward_state(
        "seize_spice_refinery",
        strengths=(8, 8, 4, 0),
    )
    result = _settle(resolve_combat_rewards(tied).state)

    assert result.players[0].resources.spice == 1
    assert result.players[1].resources.spice == 1
    assert result.players[2].resources.spice == 2


def test_conflict_spy_reward_lists_empty_observation_posts() -> None:
    state = _reward_state("seize_spice_refinery")
    occupied_post = "emperor-sardaukar-dutiful-service"
    opponent = replace(
        state.players[1],
        spies_supply=2,
        spy_post_ids=(occupied_post,),
    )
    state = replace(
        state,
        players=(state.players[0], opponent, *state.players[2:]),
    )

    rewarded = _paid(state)
    actions = legal_combat_reward_spy_actions(rewarded, 0)

    assert len(actions) == 12
    assert occupied_post not in {
        dict(action.arguments)["post_id"] for action in actions
    }
    placed = apply_combat_reward_spy(rewarded, actions[0]).state
    assert placed.players[0].spies_supply == 2
    assert placed.players[0].spy_post_ids == (dict(actions[0].arguments)["post_id"],)
    assert placed.players[0].resources.spice == 2
    assert placed.players[0].control_space_ids == ("spice_refinery",)
    assert _settle(placed).combat_rewards_resolved is True


def test_sandworm_repeats_spy_placement_but_not_control() -> None:
    state = _paid(_reward_state("seize_spice_refinery", sandworm_players=(0,)))

    for _ in range(2):
        # v150 (stage B2, OQ-112): the doubled Spy icon is two rows of the
        # window, each opening its own placement.
        state = settle_reward_window(state)
        action = legal_combat_reward_spy_actions(state, 0)[0]
        state = apply_combat_reward_spy(state, action).state

    assert state.players[0].spies_supply == 1
    assert len(state.players[0].spy_post_ids) == 2
    assert len(set(state.players[0].spy_post_ids)) == 2
    assert state.players[0].resources.spice == 4
    assert state.players[0].control_space_ids == ("spice_refinery",)
    assert _settle(state).combat_rewards_resolved is True


def test_the_emperor_tracks_spy_follows_the_conflicts_own_spy_rewards() -> None:
    # Test of Loyalty pays a Spy and one Emperor Influence. From Influence 3
    # that reaches the Emperor track's Spy icon [Main p. 7] while the
    # Conflict's own Spy is still waiting: the reward Spy is placed first
    # and the track's Spy opens after it, in the generic
    # placement frame (a sweep deadlock, seed 92, before the ordering: the
    # track's Spy took the last supply Spy and left the reward frame
    # without a legal action).
    engine = UprisingRulesEngine()
    state = _with_influence(_reward_state("test_of_loyalty"), 0, Influence(emperor=3))
    winner = replace(
        state.players[0],
        spies_supply=1,
        spy_post_ids=("arrakis-hagga-basin", "arrakis-deep-desert"),
    )
    state = replace(state, players=(winner, *state.players[1:]))

    paid = _paid(state)
    assert paid.players[0].influence.emperor == 4
    assert paid.pending_track_spies != ()
    assert paid.decision_stack[-1].kind == "combat_reward_spy"
    assert not track_spy_is_queued(paid)

    placed = apply_combat_reward_spy(
        paid, legal_combat_reward_spy_actions(paid, 0)[0]
    ).state
    assert placed.players[0].spies_supply == 0
    assert placed.decision_stack == ()
    assert track_spy_is_queued(placed)

    opened = begin_track_spy_placement(placed).state
    assert opened.pending_track_spies == ()
    assert opened.decision_stack[-1].kind == "spy_placement"
    # With the supply empty the owner may recall a Spy first, or pass
    # ("you may first recall one of your Spies" [Main pp. 11, 20]).
    assert {action.action_id for action in engine.whole_actions(opened, 0)} == {
        "decline_spy_placement",
        "recall_spy_for_placement",
    }
    # Stage B3d-2a: the seat is shown the recall as one effect row, naming what
    # opened the window, ahead of the post it recalls.
    assert engine.legal_actions(opened, 0) == (
        DomainAction(action_id="decline_spy_placement", actor=0),
        DomainAction(
            action_id="recall_spy",
            actor=0,
            arguments=(("printed", "emperor"), ("source", "influence_track")),
        ),
    )


_ALL_SPIES_PLACED = (
    "arrakis-hagga-basin",
    "arrakis-deep-desert",
    "arrakis-imperial-basin",
)


def _winner_spies(
    state: GameState, supply: int, posts: tuple[str, ...], boxed: int = 0
) -> GameState:
    winner = replace(
        state.players[0], spies_supply=supply, spy_post_ids=posts, spies_boxed=boxed
    )
    return replace(state, players=(winner, *state.players[1:]))


@pytest.mark.parametrize("conflict_id", ("seize_spice_refinery", "test_of_loyalty"))
def test_a_conflict_reward_spy_without_supply_may_recall_first(
    conflict_id: str,
) -> None:
    # Seize Spice Refinery and Test of Loyalty print a plain Spy in their
    # first-place reward [Seize Spice Refinery card] [Test of Loyalty card].
    # "If you have no Spies in your supply, you may first recall one of your
    # Spies for no effect" [Main pp. 11, 20]; the recall stays optional
    # (docs/rules/uprising-systems.md, OQ-057 (14)). With all three Spies on
    # the board the reward used to open no frame at all.
    engine = UprisingRulesEngine()
    state = _winner_spies(_reward_state(conflict_id), 0, _ALL_SPIES_PLACED)

    paid = _paid(state)

    assert paid.decision_stack[-1].kind == "combat_reward_spy"
    actions = engine.whole_actions(paid, 0)
    assert [action.action_id for action in actions] == [
        "decline_combat_reward_spy",
        *("recall_spy_for_combat_reward",) * 3,
    ]
    # Stage B3d-2a: the seat is shown the recall as one effect row, naming the
    # Conflict that paid the Spy, ahead of the post it recalls.
    assert engine.legal_actions(paid, 0) == (
        DomainAction(action_id="decline_combat_reward_spy", actor=0),
        DomainAction(
            action_id="recall_spy",
            actor=0,
            arguments=(("printed", conflict_id), ("source", "conflict")),
        ),
    )

    declined = apply_combat_reward_spy(paid, actions[0])
    assert declined.state.decision_stack == ()
    assert _settle(declined.state).combat_rewards_resolved is True
    assert declined.state.players[0].spy_post_ids == _ALL_SPIES_PLACED
    assert [event.kind for event in declined.events] == [
        "combat_reward_spy_unavailable"
    ]

    # Once recalled the Spy is in the supply and must be placed, the post it
    # left included.
    recalled = apply_combat_reward_spy(paid, actions[1]).state
    assert recalled.players[0].spies_supply == 1
    assert recalled.combat_rewards_resolved is False
    after = legal_combat_reward_spy_actions(recalled, 0)
    assert {action.action_id for action in after} == {"place_combat_reward_spy"}
    open_posts = {dict(action.arguments)["post_id"] for action in after}
    assert _ALL_SPIES_PLACED[0] in open_posts
    placed = apply_combat_reward_spy(
        recalled,
        next(
            action
            for action in after
            if dict(action.arguments)["post_id"] == "arrakis-spice-refinery-arrakeen"
        ),
    ).state
    assert placed.players[0].spy_post_ids == (
        *_ALL_SPIES_PLACED[1:],
        "arrakis-spice-refinery-arrakeen",
    )
    assert _settle(placed).combat_rewards_resolved is True


def test_a_doubled_reward_spy_is_not_capped_by_the_supply_at_payment() -> None:
    # A sandworm doubles Seize Spice Refinery's Spy [Main p. 14]. With one
    # Spy in the supply both frames open; the second may recall first
    # [Main pp. 11, 20] instead of being lost.
    state = _winner_spies(
        _reward_state("seize_spice_refinery", sandworm_players=(0,)),
        1,
        _ALL_SPIES_PLACED[:2],
    )
    paid = _paid(state)
    # v150 (stage B2, OQ-112): the doubled Spy is two rows of the reward
    # window; the second placement opens once the first is answered, and the
    # window offers it whatever the supply holds by then.
    assert [frame.kind for frame in paid.decision_stack] == [
        FrameKind.COMBAT_REWARD_ICONS,
        "combat_reward_spy",
    ]

    first = legal_combat_reward_spy_actions(paid, 0)
    assert {action.action_id for action in first} == {"place_combat_reward_spy"}
    placed = apply_combat_reward_spy(paid, first[0]).state
    assert placed.players[0].spies_supply == 0
    placed = settle_reward_window(placed)
    assert [frame.kind for frame in placed.decision_stack] == ["combat_reward_spy"]

    second = legal_combat_reward_spy_actions(placed, 0)
    assert [action.action_id for action in second] == [
        "decline_combat_reward_spy",
        *("recall_spy_for_combat_reward",) * 3,
    ]


def test_a_conflict_reward_spy_with_no_spy_to_recall_offers_only_the_decline() -> None:
    # No Spy in the supply and none on the board: nothing can be placed, so
    # the decline is the only choice ("놓을 post가 없으면 거절만 남는다",
    # OQ-057 (14)) and the Spy is lost publicly when its owner answers --
    # the engine no longer drops the frame unasked (user ruling 2026-09-30).
    # Synthetic: a four-player game never gets here (thirteen posts for
    # twelve Spies, and Advanced Data Analysis boxes at most one Spy).
    state = _winner_spies(
        replace(
            _reward_state("seize_spice_refinery"),
            config=RulesetConfig(bloodlines=True, tech_module=True),
        ),
        0,
        (),
        boxed=3,
    )
    paid = settle_reward_window(_advance_automatic(RuleResult(state=state)).state)
    assert paid.decision_stack[-1].kind == "combat_reward_spy"

    decline = DomainAction(action_id="decline_combat_reward_spy", actor=0)
    assert legal_combat_reward_spy_actions(paid, 0) == (decline,)
    assert UprisingRulesEngine().legal_actions(paid, 0) == (decline,)
    dropped = apply_combat_reward_spy(paid, decline)
    assert dropped.state.decision_stack == ()
    assert _settle(dropped.state).combat_rewards_resolved is True
    assert [event.kind for event in dropped.events] == [
        "combat_reward_spy_unavailable"
    ]


def test_choam_conflict_reward_opens_and_resolves_contract_selection() -> None:
    state = _reward_state("choam_security")
    state = replace(
        state,
        config=RulesetConfig(choam_module=True),
        contract_bank=("contract:research_station_i",),
        face_up_contract_ids=(
            "contract:arrakeen_i",
            "contract:high_council_ii",
        ),
    )

    rewarded = _paid(state)
    actions = legal_contract_actions(rewarded, 0)
    resolved = apply_contract_action(rewarded, actions[1]).state

    assert len(actions) == 2
    assert resolved.players[0].active_contract_ids == ("contract:high_council_ii",)
    assert resolved.face_up_contract_ids == (
        "contract:arrakeen_i",
        "contract:research_station_i",
    )
    assert _settle(resolved).combat_rewards_resolved is True


def test_spice_freighters_reward_can_be_paid_after_influence_choice() -> None:
    state = _reward_state("spice_freighters")
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=3),
    )
    state = replace(state, players=(owner, *state.players[1:]))

    rewarded = _paid(state)
    influence = legal_combat_reward_influence_actions(rewarded, 0)[0]
    rewarded = settle_reward_window(
        apply_combat_reward_influence(rewarded, influence).state
    )
    actions = legal_combat_reward_optional_payment_actions(rewarded, 0)

    assert tuple(action.action_id for action in actions) == (
        "decline_combat_reward",
        "pay_combat_reward",
    )
    paid = apply_combat_reward_optional_payment(rewarded, actions[1]).state
    assert paid.players[0].resources.spice == 0
    assert paid.players[0].victory_points == 2
    assert _settle(paid).combat_rewards_resolved is True


def test_unaffordable_spice_freighters_reward_can_only_be_declined() -> None:
    state = _paid(_reward_state("spice_freighters"))
    influence = legal_combat_reward_influence_actions(state, 0)[0]
    state = settle_reward_window(apply_combat_reward_influence(state, influence).state)

    actions = legal_combat_reward_optional_payment_actions(state, 0)

    assert tuple(action.action_id for action in actions) == ("decline_combat_reward",)
    declined = apply_combat_reward_optional_payment(state, actions[0])
    assert declined.state.players[0].victory_points == 1
    assert _settle(declined.state).combat_rewards_resolved is True
    assert declined.events[0].kind == "combat_reward_declined"


def test_sandworm_repeats_spice_freighters_payment_choice() -> None:
    state = _reward_state("spice_freighters", sandworm_players=(0,))
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=6),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = _paid(state)

    for _ in range(2):
        state = settle_reward_window(state)
        influence = legal_combat_reward_influence_actions(state, 0)[0]
        state = settle_reward_window(
            apply_combat_reward_influence(state, influence).state
        )
        payment = legal_combat_reward_optional_payment_actions(state, 0)[1]
        state = apply_combat_reward_optional_payment(state, payment).state

    assert state.players[0].resources.spice == 0
    assert state.players[0].influence.emperor == 2
    assert state.players[0].victory_points == 4
    assert _settle(state).combat_rewards_resolved is True


def test_trade_dispute_trashes_from_hand_discard_and_in_play() -> None:
    state = _reward_state("trade_dispute")
    players = list(state.players)
    players[0] = replace(
        players[0],
        hand=("p0:hand",),
        discard_pile=("p0:discard",),
        in_play=("p0:played",),
    )
    players[1] = replace(players[1], discard_pile=("p1:discard",))
    state = replace(state, players=tuple(players))
    state = _paid(state)

    first_actions = legal_combat_reward_trash_actions(state, 0)
    assert tuple(action.action_id for action in first_actions) == (
        "decline_combat_reward_trash",
        "trash_combat_reward_card",
        "trash_combat_reward_card",
        "trash_combat_reward_card",
    )
    assert tuple(dict(action.arguments)["card_id"] for action in first_actions[1:]) == (
        "p0:hand",
        "p0:discard",
        "p0:played",
    )
    state = apply_combat_reward_trash(state, first_actions[2]).state
    # The 2nd place is paid once the winner's trash is answered (user ruling
    # 2026-10-07, "순위대로 (앱처럼)").
    assert legal_combat_reward_trash_actions(state, 1) == ()
    state = _settle(state)

    second_actions = legal_combat_reward_trash_actions(state, 1)
    state = apply_combat_reward_trash(state, second_actions[1]).state
    state = _settle(state)

    assert state.players[0].hand == ("p0:hand",)
    assert state.players[0].discard_pile == ()
    assert state.players[0].in_play == ("p0:played",)
    assert state.players[0].trashed == ("p0:discard",)
    assert state.players[1].discard_pile == ()
    assert state.players[1].trashed == ("p1:discard",)
    assert state.players[0].resources.solari == 2
    assert state.players[0].resources.water == 2
    assert state.combat_rewards_resolved is True


def _confirm_trash_without_card(state: GameState, seat: int) -> GameState:
    # v150 (stage B2, OQ-112): a doubled trash opens its second window row
    # only after the first is answered.
    state = settle_reward_window(state)
    confirm = DomainAction(action_id="resolve_combat_trash_without_card", actor=seat)
    assert legal_combat_reward_trash_actions(state, seat) == (confirm,)
    result = apply_combat_reward_trash(state, confirm)
    assert [event.kind for event in result.events] == [
        "combat_reward_trash_unavailable"
    ]
    return _settle(result.state)


def test_trade_dispute_trash_without_a_card_is_confirmed() -> None:
    # With no card to trash the reward still opens its window, which offers
    # only the confirm (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는
    # 곳도 모두 결정 창을 연다"; cleanup-2f), the 2nd place's after the 1st.
    state = _paid(_reward_state("trade_dispute"))
    state = _confirm_trash_without_card(state, 0)
    state = _confirm_trash_without_card(state, 1)

    assert state.decision_stack == ()
    assert state.combat_rewards_resolved is True


def test_sandworm_trash_reward_is_limited_by_available_cards() -> None:
    state = _reward_state("trade_dispute", sandworm_players=(0,))
    owner = replace(state.players[0], hand=("only_card",))
    state = replace(state, players=(owner, *state.players[1:]))
    state = _paid(state)

    actions = legal_combat_reward_trash_actions(state, 0)
    state = apply_combat_reward_trash(state, actions[1]).state

    # The second trash finds no card: its window offers only the confirm
    # (cleanup-2f), and so does the cardless 2nd place's.
    state = _confirm_trash_without_card(state, 0)
    state = _confirm_trash_without_card(state, 1)

    assert state.players[0].trashed == ("only_card",)
    assert state.decision_stack == ()
    assert state.combat_rewards_resolved is True


def test_trade_dispute_trash_can_be_declined_with_cards_available() -> None:
    state = _reward_state("trade_dispute")
    owner = replace(state.players[0], discard_pile=("keep_me",))
    state = replace(state, players=(owner, *state.players[1:]))
    state = _paid(state)

    declined = legal_combat_reward_trash_actions(state, 0)[0]
    result = apply_combat_reward_trash(state, declined)

    assert result.state.players[0].discard_pile == ("keep_me",)
    assert result.state.players[0].trashed == ()
    assert result.events[0].kind == "optional_trash_declined"
    # The cardless 2nd place confirms its own (cleanup-2f).
    state = _confirm_trash_without_card(_settle(result.state), 1)
    assert state.combat_rewards_resolved is True


def test_trade_dispute_returns_trashed_reserve_card_to_its_stack() -> None:
    state = _reward_state("trade_dispute")
    reserve_card = "reserve:prepare_the_way:7"
    owner = replace(state.players[0], discard_pile=(reserve_card,))
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        reserve_stacks=(("prepare_the_way", 7), ("the_spice_must_flow", 10)),
    )
    state = _paid(state)
    action = legal_combat_reward_trash_actions(state, 0)[1]

    result = apply_combat_reward_trash(state, action).state

    assert result.players[0].discard_pile == ()
    assert result.players[0].trashed == ()
    assert dict(result.reserve_stacks)["prepare_the_way"] == 8


def test_trashing_sardaukar_soldier_draws_an_intrigue_card() -> None:
    state = _reward_state("trade_dispute")
    sardaukar = "imperium:sardaukar_soldier:0"
    owner = replace(state.players[0], discard_pile=(sardaukar,))
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        intrigue_deck=("intrigue:test:0",),
    )
    state = _paid(state)
    action = next(
        action
        for action in legal_combat_reward_trash_actions(state, 0)
        if dict(action.arguments).get("card_id") == sardaukar
    )

    result = apply_combat_reward_trash(state, action)

    assert result.state.players[0].trashed == (sardaukar,)
    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert tuple(event.kind for event in result.events) == (
        "card_trashed",
        "intrigue_card_drawn",
    )


def test_tier_three_base_vp_control_and_spice_payment_resolve() -> None:
    state = _reward_state("battle_for_imperial_basin")
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=4),
    )
    state = replace(state, players=(owner, *state.players[1:]))

    rewarded = _paid(state)

    assert rewarded.players[0].victory_points == 2
    assert rewarded.players[0].control_space_ids == ("imperial_basin",)
    actions = legal_combat_reward_optional_payment_actions(rewarded, 0)
    paid = apply_combat_reward_optional_payment(rewarded, actions[1]).state
    assert paid.players[0].resources.spice == 0
    assert paid.players[0].victory_points == 3
    # The 2nd and 3rd places are paid after the winner's payment choice
    # (user ruling 2026-10-07, "순위대로 (앱처럼)").
    settled = _settle(paid)
    assert settled.players[1].resources.spice == 5
    assert settled.players[2].resources.spice == 3
    assert settled.combat_rewards_resolved is True


def test_tier_three_solari_payment_uses_solari_not_spice() -> None:
    state = _reward_state("battle_for_spice_refinery")
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, solari=6, spice=2),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    rewarded = _paid(state)

    paid = apply_combat_reward_optional_payment(
        rewarded,
        legal_combat_reward_optional_payment_actions(rewarded, 0)[1],
    ).state

    assert paid.players[0].resources.solari == 0
    assert paid.players[0].resources.spice == 2
    assert paid.players[0].victory_points == 3


def test_sandworm_doubles_tier_three_vp_and_payment_opportunities() -> None:
    state = _reward_state(
        "battle_for_imperial_basin",
        sandworm_players=(0,),
    )
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=8),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = _paid(state)

    for _ in range(2):
        state = settle_reward_window(state)
        action = legal_combat_reward_optional_payment_actions(state, 0)[1]
        state = apply_combat_reward_optional_payment(state, action).state

    assert state.players[0].victory_points == 5
    assert state.players[0].resources.spice == 0
    assert state.players[0].control_space_ids == ("imperial_basin",)


def test_arrakeen_reward_recalls_two_selected_placed_spies() -> None:
    state = _reward_state("battle_for_arrakeen")
    owner = replace(
        state.players[0],
        spies_supply=0,
        spy_post_ids=("post_a", "post_b", "post_c"),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = _paid(state)

    actions = legal_combat_reward_spy_recall_actions(state, 0)

    assert len(actions) == 4
    paid = apply_combat_reward_spy_recall(state, actions[2]).state
    assert paid.players[0].spies_supply == 2
    assert len(paid.players[0].spy_post_ids) == 1
    assert paid.players[0].victory_points == 3
    assert _settle(paid).combat_rewards_resolved is True


def test_arrakeen_spy_recall_can_be_declined_when_unaffordable() -> None:
    state = _reward_state("battle_for_arrakeen")
    owner = replace(
        state.players[0],
        spies_supply=2,
        spy_post_ids=("only_post",),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = _paid(state)

    actions = legal_combat_reward_spy_recall_actions(state, 0)

    assert actions == (DomainAction(action_id="decline_combat_reward", actor=0),)
    declined = apply_combat_reward_spy_recall(state, actions[0]).state
    assert declined.players[0].spy_post_ids == ("only_post",)
    assert declined.players[0].victory_points == 2

    tied = _reward_state("battle_for_arrakeen", strengths=(8, 8, 4, 0))
    result = _settle(resolve_combat_rewards(tied).state)
    assert result.players[0].resources.spice == 1
    assert result.players[0].resources.solari == 3


def test_combat_winner_takes_conflict_matches_icon_and_units_are_cleaned_up() -> None:
    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(
        players[0],
        objective_ids=("objective_crysknife_1",),
        troops_supply=7,
        troops_conflict=2,
        sandworms_conflict=1,
    )
    players[1] = replace(players[1], troops_supply=8, troops_conflict=1)
    state = replace(
        state,
        players=tuple(players),
        current_conflict_ids=("older_tied_conflict", "skirmish_crysknife"),
        combat_rewards_resolved=True,
    )

    # "모든 순위 보상을 처리한 뒤, 승자는 Conflict 카드를 face-up 상태로 자신의
    # supply에 놓고 battle icon 일치를 확인한다." [Main p. 14] -- the card is
    # awarded as the Conflict-end step opens (OQ-108, user decision
    # 2026-10-18), and the Conflict's units go back to the supply in the same
    # step, before the windows (here none opens). The sandworm and the markers
    # wait for the cleanup.
    offered = offer_conflict_end_triggers(state)
    assert offered.state.decision_stack == ()
    assert offered.state.players[0].troops_supply == 9
    assert offered.state.current_conflict_ids == ("older_tied_conflict",)
    assert offered.state.players[0].won_conflict_ids == ("skirmish_crysknife",)
    assert offered.state.players[0].face_down_battle_card_ids == (
        "objective_crysknife_1",
        "skirmish_crysknife",
    )
    assert offered.state.players[0].victory_points == 2
    assert tuple(event.kind for event in offered.events) == (
        "conflict_won",
        "battle_icons_matched",
    )
    result = finish_combat(offered.state)
    winner = result.state.players[0]

    assert result.state.phase is GamePhase.MAKERS
    assert result.state.current_conflict_ids == ("older_tied_conflict",)
    assert winner.won_conflict_ids == ("skirmish_crysknife",)
    assert winner.face_down_battle_card_ids == (
        "objective_crysknife_1",
        "skirmish_crysknife",
    )
    assert winner.victory_points == 2
    assert winner.troops_supply == 9
    assert all(player.troops_conflict == 0 for player in result.state.players)
    assert all(player.sandworms_conflict == 0 for player in result.state.players)
    assert all(player.combat_strength == 0 for player in result.state.players)
    # The cleanup awards nothing any more: only its own event.
    assert tuple(event.kind for event in result.events) == ("combat_cleaned_up",)


def test_the_conflict_card_is_awarded_before_the_units_return() -> None:
    # "모든 순위 보상을 처리한 뒤, 승자는 Conflict 카드를 face-up 상태로 자신의
    # supply에 놓고 battle icon 일치를 확인한다." [Main p. 14] -- the winner
    # takes the card first (OQ-108, user decision 2026-10-18); then "each
    # player takes their troops from the Conflict and puts them in their
    # supply" [Main p. 14], a lost Sardaukar Commander to its own supply
    # [Bloodlines p. 4]. That return opens the Conflict-end windows; the
    # cleanup after them returns the sandworms and zeroes the Combat markers.
    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(
        players[0],
        troops_supply=7,
        troops_conflict=2,
        commanders_supply=2,
        commanders_conflict=1,
        sandworms_conflict=1,
    )
    players[1] = replace(
        players[1],
        troops_supply=8,
        troops_conflict=1,
        commanders_supply=1,
        commanders_conflict=2,
    )
    state = replace(
        state,
        config=RulesetConfig(bloodlines=True),
        players=tuple(players),
        combat_rewards_resolved=True,
    )

    offered = offer_conflict_end_triggers(state)

    after = offered.state
    assert after.combat_end_triggers_offered
    for seat, troops, commanders in ((0, 9, 3), (1, 9, 3)):
        assert after.players[seat].troops_supply == troops
        assert after.players[seat].commanders_supply == commanders
    assert all(
        player.troops_conflict == 0 and player.commanders_conflict == 0
        for player in after.players
    )
    # The Conflict card is already the winner's, before the units returned
    # (the event order is the step order); the sandworm and the Combat
    # markers still stand until the cleanup.
    assert after.current_conflict_ids == ()
    assert after.players[0].won_conflict_ids == ("skirmish_crysknife",)
    assert after.players[0].sandworms_conflict == 1
    assert [player.combat_strength for player in after.players] == [8, 6, 4, 0]
    assert [event.kind for event in offered.events][0] == "conflict_won"

    cleaned = finish_combat(after)

    assert cleaned.state.players[0].won_conflict_ids == ("skirmish_crysknife",)
    assert cleaned.state.current_conflict_ids == ()
    assert cleaned.state.players[0].sandworms_conflict == 0
    assert all(player.combat_strength == 0 for player in cleaned.state.players)
    assert [event.kind for event in cleaned.events] == ["combat_cleaned_up"]


def test_finish_combat_refuses_units_still_in_the_conflict() -> None:
    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(players[0], troops_supply=7, troops_conflict=2)
    state = replace(state, players=tuple(players), combat_rewards_resolved=True)

    with pytest.raises(RuntimeError, match="units return before the cleanup"):
        finish_combat(state)


def test_first_place_tie_leaves_conflict_on_board_during_cleanup() -> None:
    state = replace(
        _reward_state("skirmish_desert_mouse", strengths=(8, 8, 4, 0)),
        combat_rewards_resolved=True,
    )

    offered = offer_conflict_end_triggers(state)
    result = finish_combat(offered.state)

    assert offered.state.current_conflict_ids == ("skirmish_desert_mouse",)
    assert offered.events == ()
    assert result.state.current_conflict_ids == ("skirmish_desert_mouse",)
    assert all(player.won_conflict_ids == () for player in result.state.players)
    assert tuple(event.kind for event in result.events) == ("combat_cleaned_up",)


def test_combat_cleanup_requires_resolved_rewards() -> None:
    with pytest.raises(ValueError, match="rewards must resolve"):
        finish_combat(_reward_state("skirmish_desert_mouse"))
