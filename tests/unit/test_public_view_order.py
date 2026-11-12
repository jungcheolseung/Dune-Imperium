"""The public seat view is built field by field as before (stage E).

``core.observation._public_player_view`` passes its 88 values positionally,
in ``PublicPlayerView``'s declared field order (2026-11-11 engine speed,
stage E), where it named each one before. A value in the wrong place would
build another view. The seat here holds a distinct value in every field --
an object of its own for every field the view copies, distinct lengths,
sums and flags for the ones it computes from -- so each view field must be
the very value the keyword construction of before (copied below) puts there.
"""

import dataclasses
from typing import Any

import pytest
from tests.unit.rules.test_kept_answers import FULL, played_states

from dune_imperium.core import observation
from dune_imperium.core.observation import PublicPlayerView
from dune_imperium.core.player import PlayerState

# Fields the view computes from (lengths, sums, flags, the deck pool); every
# other field is copied as it is and gets an object of its own below.
_SHAPED: dict[str, Any] = {
    "hand": ("h:a", "h:b", "h:c"),
    "deck": ("d:a", "d:b", "d:c", "d:d", "d:e"),
    "intrigue_cards": ("i:a", "i:b", "i:c", "i:d", "i:e", "i:f", "i:g"),
    "twisted_deck": ("t:a", "t:b"),
    "navigation_slots": ("n:a", "n:b", "n:c", "n:d"),
    "hand_public": ("h:b",),
    "ungained_troops": 100,
    "ungained_conflict_troops": 20,
}


def _seat(**flags: Any) -> PlayerState:
    seat = object.__new__(PlayerState)
    for field in dataclasses.fields(PlayerState):
        value = _SHAPED.get(field.name, flags.get(field.name, object()))
        object.__setattr__(seat, field.name, value)
    return seat


@pytest.mark.parametrize(
    "flags",
    [
        {
            "secret_project_tech_id": "tech:x",
            "set_aside_card_id": "",
            "masterstroke_factions": ("emperor",),
            "masterstroke_revealed": True,
        },
        {
            "secret_project_tech_id": "",
            "set_aside_card_id": "s:a",
            "masterstroke_factions": ("fremen",),
            "masterstroke_revealed": False,
        },
    ],
)
def test_every_field_holds_the_keyword_constructions_value(
    flags: dict[str, Any],
) -> None:
    seat = _seat(**flags)
    built = observation._public_player_view(seat)
    expected = _keyword_public_player_view(seat)
    for field in dataclasses.fields(PublicPlayerView):
        new, old = getattr(built, field.name), getattr(expected, field.name)
        assert new is old or (type(new) is type(old) and new == old), field.name


def test_real_seats_build_the_same_view() -> None:
    compared = 0
    for state in played_states(FULL, 51, 600):
        for seat in state.players:
            assert observation._public_player_view(seat) == (
                _keyword_public_player_view(seat)
            )
            compared += 1
    assert compared > 1000


def test_the_owed_spies_default_is_the_fields() -> None:
    (owed,) = (
        field
        for field in dataclasses.fields(PublicPlayerView)
        if field.name == "track_spies_owed"
    )
    assert observation._NO_TRACK_SPIES_OWED is owed.default


# ``_public_player_view`` as it was before stage E.
def _keyword_public_player_view(player: PlayerState) -> PublicPlayerView:
    return PublicPlayerView(
        player=player.player_id,
        leader_id=player.leader_id,
        leader_face_id=player.leader_face_id,
        victory_points=player.victory_points,
        resources=player.resources,
        influence=player.influence,
        hand_size=len(player.hand),
        deck_size=len(player.deck),
        intrigue_card_count=len(player.intrigue_cards),
        hand_public=player.hand_public,
        deck_pool=observation._deck_pool(player),
        agents_available=player.agents_available,
        agent_locations=player.agent_locations,
        swordmaster_acquired=player.swordmaster_acquired,
        troops_supply=player.troops_supply,
        troops_garrison=player.troops_garrison,
        troops_conflict=player.troops_conflict,
        memories=player.memories,
        sandworms_conflict=player.sandworms_conflict,
        spies_supply=player.spies_supply,
        spy_post_ids=player.spy_post_ids,
        alliance_faction_ids=player.alliance_faction_ids,
        control_space_ids=player.control_space_ids,
        combat_strength=player.combat_strength,
        has_revealed=player.has_revealed,
        high_council=player.high_council,
        maker_hooks=player.maker_hooks,
        feyd_track_space=player.feyd_track_space,
        commanders_supply=player.commanders_supply,
        commanders_garrison=player.commanders_garrison,
        commanders_conflict=player.commanders_conflict,
        skill_ids=player.skill_ids,
        commander_recruited_turn=player.commander_recruited_turn,
        contracts_completed_turn=player.contracts_completed_turn,
        held_contract_icons=player.held_contract_icons,
        # Troops owed to the Conflict (Suspensor Suits, OQ-042) wait like a
        # recruit shortfall; the encoding keeps one troop slot per seat.
        ungained_troops=player.ungained_troops + player.ungained_conflict_troops,
        ungained_specimens=player.ungained_specimens,
        commander_discount_turn=player.commander_discount_turn,
        ignores_influence_requirements_turn=player.ignores_influence_requirements_turn,
        granted_agent_icon_turn=player.granted_agent_icon_turn,
        combat_icon_turn=player.combat_icon_turn,
        bene_gesserit_boost_pending=player.bene_gesserit_boost_pending,
        tactics_track_space=player.tactics_track_space,
        agent_in_conflict=player.agent_in_conflict,
        twisted_deck_size=len(player.twisted_deck),
        navigation_remaining=len(player.navigation_slots),
        navigation_played=player.navigation_played,
        reveal_persuasion_bonus=player.reveal_persuasion_bonus,
        tech_ids=player.tech_ids,
        tech_flipped=player.tech_flipped,
        has_secret_project=bool(player.secret_project_tech_id),
        spies_boxed=player.spies_boxed,
        spies_recalled_turn=player.spies_recalled_turn,
        research_space=player.research_space,
        tleilaxu_space=player.tleilaxu_space,
        specimens=player.specimens,
        family_atomics=player.family_atomics,
        reveal_persuasion_round_bonus=player.reveal_persuasion_round_bonus,
        chairdog_return_card_ids=player.chairdog_return_card_ids,
        usurped_row_card_id=player.usurped_row_card_id,
        in_play=player.in_play,
        discard_pile=player.discard_pile,
        trashed=player.trashed,
        intrigue_faceup=player.intrigue_faceup,
        imperium_set_aside=player.imperium_set_aside,
        objective_ids=player.objective_ids,
        won_conflict_ids=player.won_conflict_ids,
        face_down_battle_card_ids=player.face_down_battle_card_ids,
        active_contract_ids=player.active_contract_ids,
        completed_contract_ids=player.completed_contract_ids,
        mentat=player.mentat,
        masterstroke_secret=bool(player.masterstroke_factions)
        and not player.masterstroke_revealed,
        masterstroke_revealed_factions=(
            player.masterstroke_factions if player.masterstroke_revealed else ()
        ),
        deck_public_top=player.deck_public_top,
        voice_blocked_space_ids=player.voice_blocked_space_ids,
        enemy_agents_ignored_turn=player.enemy_agents_ignored_turn,
        acquire_to_deck_top_round=player.acquire_to_deck_top_round,
        dreadnoughts_supply=player.dreadnoughts_supply,
        dreadnoughts_garrison=player.dreadnoughts_garrison,
        dreadnoughts_conflict=player.dreadnoughts_conflict,
        freighter_space=player.freighter_space,
        negotiators=player.negotiators,
        snooper_faction_ids=player.snooper_faction_ids,
        has_set_aside_card=bool(player.set_aside_card_id),
        set_aside_returned_turn=player.set_aside_returned_turn,
        turns_finished_round=player.turns_finished_round,
        strategic_push_solari=player.strategic_push_solari,
    )
