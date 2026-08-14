"""Security and fidelity tests for player-scoped observations."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GameState, PlayerState, observe_state


def _state() -> GameState:
    players = tuple(
        PlayerState(
            player_id=seat,
            leader_id=f"leader_{seat}",
            deck=(f"p{seat}:deck:0", f"p{seat}:deck:1"),
            hand=(f"p{seat}:hand",),
            discard_pile=(f"p{seat}:discard",),
            intrigue_cards=(f"p{seat}:intrigue",),
            objective_ids=(f"objective_{seat}",),
        )
        for seat in range(4)
    )
    return GameState(
        config=RulesetConfig(),
        seed=17,
        round_number=1,
        first_player=2,
        players=players,
        conflict_deck=("conflict_hidden_1", "conflict_hidden_2"),
        unused_conflict_ids=("conflict_unused",),
        current_conflict_ids=("conflict_public",),
        imperium_deck=("imperium_hidden_1", "imperium_hidden_2"),
        imperium_row=("imperium_public",),
        intrigue_deck=("intrigue_hidden",),
        intrigue_discard=("intrigue_public",),
        reserve_stacks=(("prepare_the_way", 8),),
    )


def test_view_contains_public_state_and_only_observers_private_cards() -> None:
    state = _state()

    view = observe_state(state, player=0)

    assert view.first_player == 2
    assert view.current_conflict_ids == ("conflict_public",)
    assert view.combat_intrigue_complete is False
    assert view.combat_rewards_resolved is False
    assert view.imperium_row == ("imperium_public",)
    assert view.maker_bonus_spice == (
        ("deep_desert", 0),
        ("hagga_basin", 0),
        ("imperial_basin", 0),
    )
    assert view.intrigue_discard == ("intrigue_public",)
    assert view.players[1].objective_ids == ("objective_1",)
    assert view.players[1].won_conflict_ids == ()
    assert view.players[1].face_down_battle_card_ids == ()
    assert view.players[1].alliance_faction_ids == ()
    assert view.players[1].has_revealed is False
    assert view.private is not None
    assert view.private.deck_size == 2
    assert view.private.hand == ("p0:hand",)
    assert view.private.discard_pile == ("p0:discard",)
    assert view.private.intrigue_cards == ("p0:intrigue",)


def test_opponent_secrets_and_hidden_deck_orders_do_not_change_view() -> None:
    state = _state()
    opponent = state.players[1]
    changed_opponent = replace(
        opponent,
        deck=tuple(reversed(opponent.deck)),
        hand=("different_hand",),
        intrigue_cards=("different_intrigue",),
    )
    hidden_variant = replace(
        state,
        players=(state.players[0], changed_opponent, *state.players[2:]),
        conflict_deck=tuple(reversed(state.conflict_deck)),
        imperium_deck=tuple(reversed(state.imperium_deck)),
    )

    assert observe_state(state, 0) == observe_state(hidden_variant, 0)


def test_each_player_receives_their_own_private_cards() -> None:
    state = _state()

    first = observe_state(state, 0)
    second = observe_state(state, 1)

    assert first.private != second.private
    assert second.private is not None
    assert second.private.hand == ("p1:hand",)
    assert all(not hasattr(player, "hand") for player in second.players)
    assert all(not hasattr(player, "intrigue_cards") for player in second.players)
    assert all(not hasattr(player, "hand_size") for player in second.players)


def test_observation_is_pure_and_rejects_invalid_seats() -> None:
    state = _state()

    assert observe_state(state, 3) == observe_state(state, 3)
    assert state == _state()
    with pytest.raises(ValueError, match="configured player"):
        observe_state(state, 4)


def test_game_state_rejects_duplicate_hidden_and_public_conflicts() -> None:
    with pytest.raises(ValueError, match="Conflict card"):
        replace(
            _state(),
            conflict_deck=("same",),
            current_conflict_ids=("same",),
        )


def test_game_state_rejects_conflict_in_board_and_player_supply() -> None:
    state = _state()
    winner = replace(state.players[0], won_conflict_ids=("conflict_public",))

    with pytest.raises(ValueError, match="Conflict card"):
        replace(state, players=(winner, *state.players[1:]))


def test_game_state_rejects_two_spies_on_one_observation_post() -> None:
    state = _state()
    first = replace(
        state.players[0],
        spies_supply=2,
        spy_post_ids=("same_post",),
    )
    second = replace(
        state.players[1],
        spies_supply=2,
        spy_post_ids=("same_post",),
    )

    with pytest.raises(ValueError, match="only one Spy"):
        replace(state, players=(first, second, *state.players[2:]))


def test_game_state_rejects_two_owners_of_one_alliance() -> None:
    state = _state()
    first = replace(state.players[0], alliance_faction_ids=("fremen",))
    second = replace(state.players[1], alliance_faction_ids=("fremen",))

    with pytest.raises(ValueError, match="only one owner"):
        replace(state, players=(first, second, *state.players[2:]))
