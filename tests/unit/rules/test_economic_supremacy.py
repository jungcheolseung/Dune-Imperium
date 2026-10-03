"""Economic Supremacy, the Epic Game Mode's fifth Conflict III.

Rule source: ``docs/rules/epic-game-mode.md`` section 6 and OQ-094
(``docs/rules/open-questions.md``). The card face prints no battle icon and no
location; first place gains 1 VP plus two independent optional arrows (6
Solari -> 1 VP, 4 spice -> 1 VP), second place 1 VP, third place 2 spice and
2 Solari. "두 화살표는 서로 독립이라 둘 다, 하나만, 또는 하나도 안 낼 수 있다(각
화살표는 한 번씩) [Main p. 9] [FAQ p. 3]"; "sandworm으로 보상이 두 배가 되면 각
화살표 비용도 두 번째로 내고 효과를 한 번 더 얻을 수 있다 [Main p. 14]".
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS_BY_ID,
    ConflictReward,
    conflicts_by_tier,
)
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.combat import (
    apply_combat_reward_optional_payment,
    face_up_battle_icons,
    finish_combat,
    legal_combat_reward_optional_payment_actions,
    resolve_combat_rewards,
)
from dune_imperium.rules.effect_interpreter import (
    face_up_conflict_card_ids,
    flippable_battle_card_ids,
)
from dune_imperium.rules.endgame import (
    begin_endgame_intrigue,
    can_finish_endgame_automatically,
    legal_endgame_intrigue_actions,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.ornithopter import match_all_battle_icons

EPIC = RulesetConfig(epic_game=True)
EPIC_BLOODLINES = RulesetConfig(bloodlines=True, epic_game=True)
EPIC_TECH = RulesetConfig(bloodlines=True, tech_module=True, epic_game=True)
EPIC_PROMO = RulesetConfig(promo_cards=True, epic_game=True)
ES = "economic_supremacy"
DECLINE_ONLY = ("decline_combat_reward",)
DECLINE_OR_PAY = ("decline_combat_reward", "pay_combat_reward")


def _combat_state(
    *,
    solari: int = 0,
    spice: int = 0,
    sandworm: bool = False,
    config: RulesetConfig = EPIC,
    conflict_id: str = ES,
    **winner: object,
) -> GameState:
    """Seat 0 first (8), seat 1 second (6), seat 2 third (4), seat 3 out."""

    players = [
        PlayerState(player_id=seat, combat_strength=strength)
        for seat, strength in enumerate((8, 6, 4, 0))
    ]
    players[0] = replace(
        players[0],
        resources=Resources(solari=solari, spice=spice),
        sandworms_conflict=1 if sandworm else 0,
        **winner,  # type: ignore[arg-type]
    )
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=tuple(players),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
    )


def _top_resource(state: GameState) -> object:
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_REWARD_OPTIONAL
    return dict(frame.context)["resource"]


def _answer(state: GameState, *, pay: bool) -> GameState:
    action_id = "pay_combat_reward" if pay else "decline_combat_reward"
    action = DomainAction(action_id=action_id, actor=0)
    assert action in legal_combat_reward_optional_payment_actions(state, 0)
    return apply_combat_reward_optional_payment(state, action).state


def _offered(state: GameState) -> tuple[str, ...]:
    return tuple(
        action.action_id
        for action in legal_combat_reward_optional_payment_actions(state, 0)
    )


# ------------------------------------------------------------- transcription


def test_economic_supremacy_is_transcribed_from_the_card_face() -> None:
    conflict = CONFLICTS_BY_ID[ES]

    assert conflict.tier is ConflictTier.THREE
    # "battle icon 없음, location 없음(control 보상 없음, Shield Wall 보호
    # 없음)" (epic-game-mode.md section 6, card face).
    assert conflict.battle_icon is None
    assert conflict.shield_wall_protected is False
    assert conflict.epic_only is True
    assert conflict.rewards == (
        ConflictReward(
            victory_points=1,
            optional_solari_cost=6,
            optional_spice_cost=4,
            optional_victory_points=1,
        ),
        ConflictReward(victory_points=1),
        ConflictReward(spice=2, solari=2),
    )
    assert all(reward.control_space_id is None for reward in conflict.rewards)


def test_economic_supremacy_joins_the_tier_three_pool_only_in_epic_games() -> None:
    # "Epic Game Mode를 하려면 Conflict III가 한 장 더 필요하므로 Economic
    # Supremacy를 더하라고 지시한다 [Main p. 18]".
    assert ES not in {c.card.card_id for c in conflicts_by_tier(ConflictTier.THREE)}
    epic = conflicts_by_tier(ConflictTier.THREE, epic_game=True)
    assert ES in {conflict.card.card_id for conflict in epic}
    assert len(epic) == 5


# ------------------------------------------------------------ reward arrows


def test_every_place_gains_its_printed_row() -> None:
    before = _combat_state()
    rewarded = resolve_combat_rewards(before).state

    first, second, third, fourth = rewarded.players
    assert first.victory_points == before.players[0].victory_points + 1
    assert second.victory_points == before.players[1].victory_points + 1
    assert (third.resources.spice, third.resources.solari) == (2, 2)
    assert third.victory_points == before.players[2].victory_points
    assert fourth == before.players[3]
    # No location: nobody takes control of anything.
    assert all(player.control_space_ids == () for player in rewarded.players)


def test_first_place_is_offered_the_solari_arrow_then_the_spice_arrow() -> None:
    rewarded = resolve_combat_rewards(_combat_state(solari=6, spice=4)).state

    # Two separate choices, in the printed order (6 Solari above 4 spice).
    assert [frame.kind for frame in rewarded.decision_stack] == [
        FrameKind.COMBAT_REWARD_OPTIONAL,
        FrameKind.COMBAT_REWARD_OPTIONAL,
    ]
    assert _top_resource(rewarded) == "solari"
    assert rewarded.combat_rewards_resolved is False
    after_first = _answer(rewarded, pay=False)
    assert _top_resource(after_first) == "spice"
    assert after_first.combat_rewards_resolved is False


@pytest.mark.parametrize(
    ("pay_solari", "pay_spice", "solari_left", "spice_left", "gained"),
    (
        (True, True, 0, 0, 3),
        (True, False, 0, 4, 2),
        (False, True, 6, 0, 2),
        (False, False, 6, 4, 1),
    ),
)
def test_first_place_may_take_both_either_or_neither_arrow(
    pay_solari: bool,
    pay_spice: bool,
    solari_left: int,
    spice_left: int,
    gained: int,
) -> None:
    before = _combat_state(solari=6, spice=4)
    state = resolve_combat_rewards(before).state

    state = _answer(state, pay=pay_solari)
    state = _answer(state, pay=pay_spice)

    winner = state.players[0]
    assert winner.resources.solari == solari_left
    assert winner.resources.spice == spice_left
    assert winner.victory_points == before.players[0].victory_points + gained
    assert state.decision_stack == ()
    assert state.combat_rewards_resolved is True


def test_the_paid_arrows_are_logged_one_event_each() -> None:
    state = resolve_combat_rewards(_combat_state(solari=6, spice=4)).state
    action = DomainAction(action_id="pay_combat_reward", actor=0)

    solari = apply_combat_reward_optional_payment(state, action)
    spice = apply_combat_reward_optional_payment(solari.state, action)

    assert [dict(event.payload) for event in (*solari.events, *spice.events)] == [
        {"cost": 6, "player": 0, "resource": "solari", "victory_points": 1},
        {"cost": 4, "player": 0, "resource": "spice", "victory_points": 1},
    ]
    assert solari.events[0].event_id != spice.events[0].event_id


@pytest.mark.parametrize(
    ("solari", "spice", "solari_offer", "spice_offer"),
    (
        (5, 4, DECLINE_ONLY, DECLINE_OR_PAY),
        (6, 3, DECLINE_OR_PAY, DECLINE_ONLY),
        (5, 3, DECLINE_ONLY, DECLINE_ONLY),
    ),
)
def test_an_unaffordable_arrow_can_only_be_declined(
    solari: int,
    spice: int,
    solari_offer: tuple[str, ...],
    spice_offer: tuple[str, ...],
) -> None:
    # Like Battle for Imperial Basin's single arrow: "pay" is offered only
    # when the resource covers the cost.
    before = _combat_state(solari=solari, spice=spice)
    state = resolve_combat_rewards(before).state

    assert _offered(state) == solari_offer
    state = _answer(state, pay=False)
    assert _offered(state) == spice_offer
    state = _answer(state, pay=False)

    assert state.players[0].resources == before.players[0].resources
    assert state.players[0].victory_points == before.players[0].victory_points + 1


def test_a_sandworm_offers_each_arrow_a_second_time() -> None:
    # "보상에 '비용을 내고 효과를 얻기' 선택지가 있으면, 두 번째 효과를 얻기
    # 위해 비용도 두 번째로 낼 수 있다" [Main p. 14].
    before = _combat_state(solari=12, spice=8, sandworm=True)
    state = resolve_combat_rewards(before).state

    assert state.players[0].victory_points == before.players[0].victory_points + 2
    order = []
    while state.decision_stack:
        order.append(_top_resource(state))
        state = _answer(state, pay=True)

    assert order == ["solari", "spice", "solari", "spice"]
    winner = state.players[0]
    assert (winner.resources.solari, winner.resources.spice) == (0, 0)
    # 2 doubled base VP + 4 paid arrows.
    assert winner.victory_points == before.players[0].victory_points + 6
    assert state.combat_rewards_resolved is True


def test_a_sandworm_s_second_arrow_is_judged_on_what_is_left() -> None:
    before = _combat_state(solari=6, spice=8, sandworm=True)
    state = resolve_combat_rewards(before).state

    state = _answer(state, pay=True)  # Solari, 6 of 6
    state = _answer(state, pay=True)  # spice, 4 of 8
    assert _top_resource(state) == "solari"
    assert _offered(state) == DECLINE_ONLY
    state = _answer(state, pay=False)
    assert _offered(state) == DECLINE_OR_PAY
    state = _answer(state, pay=True)

    winner = state.players[0]
    assert (winner.resources.solari, winner.resources.spice) == (0, 0)
    assert winner.victory_points == before.players[0].victory_points + 2 + 3


def test_a_single_arrow_card_still_offers_one_choice() -> None:
    # Battle for Spice Refinery (6 Solari) and Battle for Imperial Basin (4
    # spice) keep their one arrow each.
    for conflict_id, resource in (
        ("battle_for_spice_refinery", "solari"),
        ("battle_for_imperial_basin", "spice"),
    ):
        base = _combat_state(
            solari=6, spice=4, config=RulesetConfig(), conflict_id=conflict_id
        )
        state = resolve_combat_rewards(base).state
        assert len(state.decision_stack) == 1
        assert _top_resource(state) == resource


# ------------------------------------------------- arrival: no icon, no match


@pytest.mark.parametrize(
    ("objective_ids", "won_conflict_ids"),
    (
        (("objective_crysknife_1",), ()),
        (("objective_desert_mouse",), ()),
        (("objective_crysknife_1",), ("skirmish_ornithopter",)),
        ((), ("propaganda",)),
    ),
)
def test_winning_it_pairs_with_no_face_up_card(
    objective_ids: tuple[str, ...], won_conflict_ids: tuple[str, ...]
) -> None:
    # OQ-094 (a): "이긴 플레이어는 카드를 supply에 앞면으로 두지만 icon이
    # 없으므로 도착 즉시 매칭도 ... 되지 않는다".
    before = replace(
        _combat_state(objective_ids=objective_ids, won_conflict_ids=won_conflict_ids),
        combat_rewards_resolved=True,
    )

    result = finish_combat(before)
    winner = result.state.players[0]

    assert winner.won_conflict_ids == (*won_conflict_ids, ES)
    assert winner.face_down_battle_card_ids == ()
    assert winner.victory_points == before.players[0].victory_points
    assert [event.kind for event in result.events] == [
        "conflict_won",
        "combat_cleaned_up",
    ]


def test_a_later_win_matches_its_own_icon_and_leaves_it_face_up() -> None:
    before = replace(
        _combat_state(
            conflict_id="skirmish_crysknife",
            objective_ids=("objective_crysknife_1",),
            won_conflict_ids=(ES,),
        ),
        combat_rewards_resolved=True,
    )

    winner = finish_combat(before).state.players[0]

    assert winner.face_down_battle_card_ids == (
        "objective_crysknife_1",
        "skirmish_crysknife",
    )
    assert winner.victory_points == before.players[0].victory_points + 1
    assert face_up_conflict_card_ids(winner) == (ES,)


# ------------------------------------------------------------------ Endgame


def _endgame(owner: PlayerState, config: RulesetConfig = EPIC) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )


def test_a_wild_card_cannot_pair_with_it_in_the_endgame() -> None:
    # OQ-094 (a): "Endgame의 wild 매칭 상대도 되지 않는다" [Main p. 20].
    state = _endgame(PlayerState(player_id=0, won_conflict_ids=("propaganda", ES)))

    assert can_finish_endgame_automatically(state) is True
    opened = begin_endgame_intrigue(state).state
    assert legal_endgame_intrigue_actions(opened, 0) == (
        DomainAction(action_id="pass_endgame_intrigue", actor=0),
    )


def test_a_wild_card_still_pairs_with_a_printed_icon_beside_it() -> None:
    state = _endgame(
        PlayerState(
            player_id=0,
            objective_ids=("objective_crysknife_1",),
            won_conflict_ids=("propaganda", ES),
        )
    )

    opened = begin_endgame_intrigue(state).state
    matches = [
        dict(action.arguments)
        for action in legal_endgame_intrigue_actions(opened, 0)
        if action.action_id == "match_endgame_wild_icon"
    ]
    assert matches == [
        {"matching_card_id": "objective_crysknife_1", "wild_card_id": "propaganda"}
    ]


@pytest.mark.parametrize("icon", list(BattleIcon))
def test_no_icon_flip_can_target_it(icon: BattleIcon) -> None:
    # OQ-094 (b): "Crysknife·Desert Mouse·Ornithopter Intrigue의 Endgame
    # 뒤집기 대상이 아니다".
    seat = PlayerState(player_id=0, won_conflict_ids=(ES,))

    assert flippable_battle_card_ids(seat, icon) == ()


@pytest.mark.parametrize(
    ("intrigue_id", "same_icon_conflict"),
    (
        ("crysknife", "battle_for_arrakeen"),
        ("desert_mouse", "battle_for_spice_refinery"),
        ("ornithopter", "battle_for_imperial_basin"),
    ),
)
def test_the_icon_intrigue_endgame_half_ignores_it(
    intrigue_id: str, same_icon_conflict: str
) -> None:
    engine = UprisingRulesEngine()
    card = f"intrigue:{intrigue_id}:0"
    alone = begin_endgame_intrigue(
        _endgame(
            PlayerState(player_id=0, intrigue_cards=(card,), won_conflict_ids=(ES,))
        )
    ).state

    # Only the Economic Supremacy is face up: the flip half is not offered.
    assert [action.action_id for action in engine.legal_actions(alone, 0)] == [
        "pass_endgame_intrigue"
    ]

    both = begin_endgame_intrigue(
        _endgame(
            PlayerState(
                player_id=0,
                intrigue_cards=(card,),
                won_conflict_ids=(ES, same_icon_conflict),
            )
        )
    ).state
    play = DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card), ("option", 1)),
    )
    opened = engine.apply(both, play).state
    targets = {
        dict(action.arguments)["card_id"]
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "flip_battle_card"
    }
    assert targets == {same_icon_conflict}


def test_grasp_arrakis_may_flip_it() -> None:
    # OQ-094 (e): "Grasp Arrakis는 icon이 아니라 Conflict 카드를 세므로 이
    # 카드도 뒤집을 수 있다" (card face: "face-up Conflict cards").
    engine = UprisingRulesEngine()
    card = "intrigue:grasp_arrakis:0"
    state = begin_endgame_intrigue(
        _endgame(
            PlayerState(
                player_id=0,
                intrigue_cards=(card,),
                won_conflict_ids=(ES, "skirmish_ornithopter"),
            ),
            config=EPIC_BLOODLINES,
        )
    ).state
    play = DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card), ("option", 1)),
    )

    opened = engine.apply(state, play).state
    first = [
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "flip_battle_card"
    ]
    assert {dict(a.arguments)["card_id"] for a in first} == {
        ES,
        "skirmish_ornithopter",
    }
    flip_es = next(a for a in first if dict(a.arguments)["card_id"] == ES)
    flipped_one = engine.apply(opened, flip_es).state
    (second,) = engine.legal_actions(flipped_one, 0)
    done = engine.apply(flipped_one, second).state

    assert done.players[0].victory_points == state.players[0].victory_points + 1
    assert set(done.players[0].face_down_battle_card_ids) == {
        ES,
        "skirmish_ornithopter",
    }


# -------------------------------------------------------- Ornithopter Fleet


def test_ornithopter_fleet_does_not_make_it_an_ornithopter() -> None:
    # OQ-094 (c): "Ornithopter Fleet은 '가진 battle icon'만 바꾸므로 이
    # 카드를 Ornithopter로 만들지 않는다(매칭과 Ornithopter 뒤집기 대상에서
    # 빠진다)" [Bloodlines p. 12].
    seat = PlayerState(
        player_id=0,
        tech_ids=("ornithopter_fleet",),
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=(ES,),
    )

    matched, events = match_all_battle_icons(seat, source="test")
    assert matched == seat
    assert events == ()
    # The face-up Objective counts as a won Conflict card [Objective card]
    # and its icon is an Ornithopter under the Fleet (OQ-005, 2026-10-04);
    # Economic Supremacy, with no icon, still never is.
    assert flippable_battle_card_ids(seat, BattleIcon.ORNITHOPTER) == (
        "objective_crysknife_1",
    )
    assert face_up_battle_icons(seat) == {BattleIcon.ORNITHOPTER}
    alone = replace(seat, objective_ids=())
    assert face_up_battle_icons(alone) == frozenset()


def test_ornithopter_fleet_winning_it_pairs_nothing() -> None:
    before = replace(
        _combat_state(
            config=EPIC_TECH,
            tech_ids=("ornithopter_fleet",),
            objective_ids=("objective_crysknife_1",),
        ),
        combat_rewards_resolved=True,
    )

    result = finish_combat(before)
    winner = result.state.players[0]

    assert winner.face_down_battle_card_ids == ()
    assert winner.victory_points == before.players[0].victory_points
    assert "battle_icons_matched" not in [event.kind for event in result.events]


def test_ornithopter_fleet_pairs_the_next_win_past_it() -> None:
    before = replace(
        _combat_state(
            config=EPIC_TECH,
            conflict_id="skirmish_desert_mouse",
            tech_ids=("ornithopter_fleet",),
            objective_ids=("objective_crysknife_1",),
            won_conflict_ids=(ES,),
        ),
        combat_rewards_resolved=True,
    )

    winner = finish_combat(before).state.players[0]

    assert winner.face_down_battle_card_ids == (
        "objective_crysknife_1",
        "skirmish_desert_mouse",
    )
    assert winner.victory_points == before.players[0].victory_points + 1
    assert face_up_conflict_card_ids(winner) == (ES,)
    assert flippable_battle_card_ids(winner, BattleIcon.ORNITHOPTER) == ()


# -------------------------------------------------------- The Beast's Spoils


def test_face_up_icons_skip_it() -> None:
    # OQ-094 (d): "The Beast's Spoils처럼 face-up battle icon 종류를 세는
    # 효과에 아무것도 더하지 않는다".
    assert face_up_battle_icons(PlayerState(player_id=0, won_conflict_ids=(ES,))) == (
        frozenset()
    )
    assert face_up_battle_icons(
        PlayerState(player_id=0, won_conflict_ids=(ES, "skirmish_desert_mouse"))
    ) == {BattleIcon.DESERT_MOUSE}


def test_the_beasts_spoils_gains_nothing_for_it() -> None:
    spoils = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False, True)
        if ":the_beast_s_spoils:" in instance_id
    )
    owner = PlayerState(player_id=0, hand=(spoils,), won_conflict_ids=(ES,))
    state = GameState(
        config=EPIC_PROMO,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        current_conflict_ids=("propaganda",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    place = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, place).state

    resolved = resolve_agent_card_effect(placed)

    after = resolved.state.players[0]
    assert after.resources.spice == 0
    assert after.troops_garrison == owner.troops_garrison
    assert resolved.events[0].kind == "agent_card_effect_unavailable"
