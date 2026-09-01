"""Tests for personal draw and replayable discard reshuffling."""

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    DecisionFrame,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.card_draw import (
    apply_personal_draw_reshuffle,
    draw_or_request_personal_cards,
    personal_draw_is_pending,
)


def _state(owner: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )


def test_personal_draw_uses_existing_deck_without_chance() -> None:
    state = _state(PlayerState(player_id=0, deck=("a", "b")))

    result = draw_or_request_personal_cards(state, 0, 1, source="test:draw")

    assert result.state.players[0].hand == ("a",)
    assert result.state.players[0].deck == ("b",)
    assert personal_draw_is_pending(result.state) is False


def test_personal_draw_reshuffles_discard_beneath_remaining_deck() -> None:
    owner = PlayerState(
        player_id=0,
        deck=("top",),
        discard_pile=("discard_a", "discard_b"),
    )
    pending = draw_or_request_personal_cards(
        _state(owner),
        0,
        2,
        source="test:draw",
    ).state
    decision = pending.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)

    outcome = ChanceOutcome(decision.decision_id, ("discard_b", "discard_a"))
    result = apply_personal_draw_reshuffle(pending, outcome)

    assert result.state.players[0].hand == ("top", "discard_b")
    assert result.state.players[0].deck == ("discard_a",)
    assert result.state.players[0].discard_pile == ()
    assert tuple(event.kind for event in result.events) == (
        "personal_discard_shuffled",
    )


def test_personal_draw_takes_only_available_cards_without_discard() -> None:
    state = _state(PlayerState(player_id=0, deck=("only",)))

    result = draw_or_request_personal_cards(state, 0, 2, source="test:draw")

    assert result.state.players[0].hand == ("only",)
    assert result.state.players[0].deck == ()


def test_draw_lands_in_hand_when_the_players_own_reveal_is_not_open() -> None:
    # A draw during an Agent turn, or while a different player's Reveal is
    # open, behaves exactly as before the immediate-reveal rule [FAQ p. 3]:
    # the card stays in hand rather than being revealed.
    owner = PlayerState(player_id=0, deck=("a", "b"))
    other_players_reveal = PlayerState(player_id=1)
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(
            owner,
            other_players_reveal,
            PlayerState(player_id=2),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="reveal",
                frame_id="round:1:player:1:reveal",
                decision=PlayerDecision(
                    owner=1, prompt="Resolve Reveal effects and acquire cards"
                ),
                context=(
                    ("optional_sword_strength", 0),
                    ("persuasion", 0),
                    ("revealed_card_count", 0),
                    ("strength", 0),
                    ("sword_strength", 0),
                    ("turn_owner", 1),
                ),
            ),
        ),
    )

    result = draw_or_request_personal_cards(state, 0, 1, source="test:draw")

    assert result.state.players[0].hand == ("a",)
    assert result.state.players[0].in_play == ()
    assert result.state.players[0].deck == ("b",)
