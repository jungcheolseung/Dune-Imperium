"""Tests for shared discard transitions and discard triggers.

A deck discard fires the trigger too (OQ-013, user ruling 2026-10-04).
"""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import GameState, PlayerState, Resources
from dune_imperium.rules.card_discard import (
    discard_personal_card_from_hand,
    resolve_personal_card_discard_trigger,
)


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def _state(owner: PlayerState, config: RulesetConfig | None = None) -> GameState:
    return GameState(
        config=config or RulesetConfig(),
        seed=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )


def test_spacing_guilds_favor_gains_spice_when_discarded_from_hand() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(player_id=0, hand=(favor,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )

    result = discard_personal_card_from_hand(
        state,
        0,
        favor,
        source="test:discard",
    )

    assert result.state.players[0].hand == ()
    assert result.state.players[0].discard_pile == (favor,)
    assert result.state.players[0].resources.spice == 2
    assert [event.kind for event in result.events] == [
        "card_discarded",
        "personal_card_discard_effect_resolved",
    ]


def test_discard_trigger_pays_favor_already_in_the_discard_pile() -> None:
    # A deck discard (Long Live the Fighters, Controlled) moves the card
    # itself and then calls the trigger (OQ-013, user ruling 2026-10-04).
    favor = _imperium_instance("spacing_guild_s_favor")
    state = _state(PlayerState(player_id=0, discard_pile=(favor,)))

    result = resolve_personal_card_discard_trigger(
        state, 0, favor, source="test:deck"
    )

    owner = result.state.players[0]
    assert owner.discard_pile == (favor,)
    assert owner.resources == Resources(spice=2)
    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == f"test:deck:discard:{favor}:effect"
    assert event.kind == "personal_card_discard_effect_resolved"
    assert event.payload == (("card_id", favor), ("player", 0), ("spice", 2))
    assert result.state.players[1:] == state.players[1:]


def test_discard_trigger_pays_corrupt_bureaucrat_three_solari() -> None:
    # Bloodlines with the CHOAM module; not in the base Imperium deck ids.
    bureaucrat = "imperium:corrupt_bureaucrat:0"
    state = _state(
        PlayerState(player_id=0, discard_pile=(bureaucrat,)),
        RulesetConfig(bloodlines=True, choam_module=True),
    )

    result = resolve_personal_card_discard_trigger(
        state, 0, bureaucrat, source="test:deck"
    )

    assert result.state.players[0].resources == Resources(solari=3)
    assert [event.payload for event in result.events] == [
        (("card_id", bureaucrat), ("player", 0), ("solari", 3))
    ]


def test_discard_trigger_without_a_discard_effect_changes_nothing() -> None:
    dagger = next(
        card for card in starting_deck_instance_ids(0) if ":dagger:" in card
    )
    state = _state(PlayerState(player_id=0, discard_pile=(dagger,)))

    result = resolve_personal_card_discard_trigger(
        state, 0, dagger, source="test:deck"
    )

    assert result.state is state
    assert result.events == ()


def test_discard_trigger_requires_the_card_in_the_discard_pile() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    in_deck = _state(PlayerState(player_id=0, deck=(favor,)))
    with pytest.raises(ValueError, match="discard pile"):
        resolve_personal_card_discard_trigger(in_deck, 0, favor, source="test")
    in_discard = _state(PlayerState(player_id=0, discard_pile=(favor,)))
    with pytest.raises(ValueError, match="source"):
        resolve_personal_card_discard_trigger(in_discard, 0, favor, source="")
    with pytest.raises(ValueError, match="seat"):
        resolve_personal_card_discard_trigger(in_discard, 4, favor, source="test")


def test_hand_discard_events_keep_their_ids_and_payloads() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    state = _state(PlayerState(player_id=0, hand=(favor,)))

    result = discard_personal_card_from_hand(state, 0, favor, source="src")

    assert [(e.event_id, e.kind, e.payload) for e in result.events] == [
        (
            f"src:discard:{favor}",
            "card_discarded",
            (("card_id", favor), ("player", 0)),
        ),
        (
            f"src:discard:{favor}:effect",
            "personal_card_discard_effect_resolved",
            (("card_id", favor), ("player", 0), ("spice", 2)),
        ),
    ]
