"""Tests for shared hand-discard transitions and triggers."""

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.core import GameState, PlayerState
from dune_imperium.rules.card_discard import discard_personal_card_from_hand


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
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
