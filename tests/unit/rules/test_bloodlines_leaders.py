"""Tests for the Bloodlines Leaders (card faces, ``docs/rules/bloodlines.md`` §6).

Rule sources: the Leader card faces transcribed on 2026-09-07 and the
Bloodlines rulebook clarifications [Bloodlines p. 12]; project conventions
are OQ-037 (Into the Fray) and the Chani/Kynes readings recorded in the
Leader audit.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
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
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    apply_maker_space_action,
    legal_board_effect_actions,
    legal_maker_space_actions,
    resolve_board_effect,
)
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.leader_abilities import (
    apply_leader_agent_deploy,
    apply_leader_card_trash,
    apply_leader_signet_payment,
    apply_leader_spy_action,
    apply_leader_troop_retreat,
    legal_leader_signet_actions,
    resolve_leader_signet,
)
from dune_imperium.rules.optional_trash import (
    apply_optional_trash,
    legal_optional_trash_actions,
)
from dune_imperium.rules.spies import legal_gather_intelligence_actions
from dune_imperium.rules.strength import units_strength
from dune_imperium.rules.units import retreat_units

BLOODLINES = RulesetConfig(bloodlines=True)
SIGNET = "player:0:starter:signet_ring:0"
DAGGER = "player:0:starter:dagger:0"
RECON = "player:0:starter:reconnaissance:0"
DUNE = "player:0:starter:dune_the_desert_planet:0"


def _turn_state(owner: PlayerState, **overrides: object) -> GameState:
    values: dict[str, object] = {
        "config": BLOODLINES,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False)[:3],
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(overrides)
    return GameState(**values)  # type: ignore[arg-type]


def _play(state: GameState, card_id: str, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == card_id
    )
    return apply_agent_action(state, action).state


def _resolve_board(state: GameState) -> GameState:
    for action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, action).state
    return state


# --- Chani -------------------------------------------------------------------


def test_tactician_advances_per_retreated_troop_and_resets_at_the_end() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="chani",
        tactics_track_space=2,
        troops_supply=1,
        troops_garrison=0,
        troops_conflict=11,
        combat_strength=22,
    )
    state = _turn_state(owner)
    first = retreat_units(state, 0, "test", troops=3)
    seat = first.state.players[0]
    assert seat.tactics_track_space == 5
    assert seat.resources.spice == 1
    assert first.events[-1].kind == "tactics_token_advanced"
    # Six more would pass the end: water once, reset, no extra advance.
    second = retreat_units(first.state, 0, "test", troops=6)
    seat = second.state.players[0]
    assert seat.tactics_track_space == 2
    assert seat.resources.water == 1 + 1
    assert seat.resources.spice == 1


def test_fedaykin_maneuver_retreats_any_number_or_buys_two_troops() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="chani",
        tactics_track_space=2,
        hand=(SIGNET,),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
        commanders_supply=0,
        commanders_conflict=1,
        combat_strength=6,
        influence=Influence(fremen=2),
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    actions = legal_leader_signet_actions(state, 0)
    ids = {a.action_id for a in actions}
    assert ids == {
        "decline_leader_signet_payment",
        "retreat_leader_troops",
        "pay_leader_signet_water",
    }
    retreat_all = next(
        a
        for a in actions
        if a.action_id == "retreat_leader_troops"
        and dict(a.arguments) == {"commanders": 1, "count": 3}
    )
    retreated = apply_leader_troop_retreat(state, retreat_all).state
    seat = retreated.players[0]
    assert seat.troops_conflict == 0 and seat.commanders_conflict == 0
    assert seat.tactics_track_space == 5 and seat.resources.spice == 1

    paid = apply_leader_signet_payment(
        state, DomainAction(action_id="pay_leader_signet_water", actor=0)
    ).state
    seat = paid.players[0]
    assert seat.resources.water == 0
    assert seat.troops_garrison == 3 + 2
    assert dict(paid.decision_stack[-1].context)["troops_recruited"] == 2


# --- Count Hasimir Fenring ---------------------------------------------------


def test_assassin_pays_one_solari_per_trashed_card() -> None:
    owner = PlayerState(player_id=0, leader_id="count_hasimir_fenring", hand=(DAGGER,))
    result = trash_personal_card(_turn_state(owner), 0, DAGGER, source="test")
    assert result.state.players[0].resources.solari == 1
    assert result.events[-1].kind == "leader_ability_resolved"


def test_corrino_liaison_trashes_a_played_card_or_spies_on_the_emperor() -> None:
    owner = PlayerState(
        player_id=0, leader_id="count_hasimir_fenring", hand=(SIGNET, RECON)
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    actions = legal_leader_signet_actions(state, 0)
    trash = [a for a in actions if a.action_id == "trash_leader_card"]
    assert [dict(a.arguments)["card_id"] for a in trash] == [SIGNET]
    spies = [a for a in actions if a.action_id == "place_leader_spy"]
    assert {dict(a.arguments)["post_id"] for a in spies} == {
        "emperor-sardaukar-dutiful-service"
    }
    trashed = apply_leader_card_trash(state, trash[0]).state
    assert SIGNET in trashed.players[0].trashed
    assert trashed.players[0].resources.solari == 1
    placed = apply_leader_spy_action(state, spies[0]).state
    assert placed.players[0].spy_post_ids == ("emperor-sardaukar-dutiful-service",)


# --- Duncan Idaho ------------------------------------------------------------


def test_ginaz_swordmaster_discounts_the_swordmaster_space() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(DAGGER,),
        resources=Resources(solari=6, water=1),
    )
    state = _turn_state(owner)
    swordmaster = [
        a
        for a in legal_agent_actions(state, 0)
        if dict(a.arguments)["space_id"] == "swordmaster"
    ]
    assert swordmaster
    bought = apply_agent_action(state, swordmaster[0]).state
    assert bought.players[0].resources.solari == 0
    other = replace(
        state, players=(replace(owner, leader_id="gurney_halleck"), *state.players[1:])
    )
    assert not [
        a
        for a in legal_agent_actions(other, 0)
        if dict(a.arguments)["space_id"] == "swordmaster"
    ]


def test_into_the_fray_sends_the_agent_to_fight() -> None:
    owner = PlayerState(player_id=0, leader_id="duncan_idaho", hand=(SIGNET,))
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    actions = legal_leader_signet_actions(state, 0)
    assert [a.action_id for a in actions] == [
        "decline_leader_signet_payment",
        "deploy_leader_agent",
    ]
    fighting = apply_leader_agent_deploy(state, actions[1]).state
    seat = fighting.players[0]
    assert seat.agent_in_conflict == 1
    assert seat.agent_locations == ()
    assert seat.units_in_conflict == 1
    assert units_strength(seat) == 2
    assert (
        units_strength(replace(seat, swordmaster_acquired=True, agents_available=2))
        == 3
    )
    # The vacated space is open to the others again (OQ-037).
    rival_hand = "player:1:starter:reconnaissance:0"
    rival = replace(fighting.players[1], hand=(rival_hand,))
    reopened = replace(
        fighting,
        players=(fighting.players[0], rival, *fighting.players[2:]),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:1",
                decision=PlayerDecision(owner=1, prompt="Choose a turn"),
            ),
        ),
    )
    assert any(
        dict(a.arguments)["space_id"] == "arrakeen"
        for a in legal_agent_actions(reopened, 1)
    )


# --- Gaius Helen Mohiam ------------------------------------------------------


def test_clandestine_gives_every_card_the_spy_icon_and_forces_gathering() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gaius_helen_mohiam",
        hand=(DAGGER,),
        deck=(RECON,),
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    state = _turn_state(owner)
    # Dagger prints only Landsraad; the Spy next to Arrakeen opens it.
    assert any(
        dict(a.arguments)["space_id"] == "arrakeen"
        for a in legal_agent_actions(state, 0)
    )
    placed = _play(state, DAGGER, "arrakeen")
    gather = legal_gather_intelligence_actions(placed, 0)
    assert [a.action_id for a in gather] == ["gather_intelligence"]


def test_listeners_places_next_to_the_landsraad_or_pays_spice_for_anywhere() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gaius_helen_mohiam",
        hand=(SIGNET,),
        resources=Resources(spice=1, water=1),
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    actions = legal_leader_signet_actions(state, 0)
    posts = {
        dict(a.arguments)["post_id"]
        for a in actions
        if a.action_id == "place_leader_spy"
    }
    assert posts == {
        "landsraad-high-council-imperial-privilege-swordmaster",
        "landsraad-assembly-hall-gather-support",
    }
    paid = apply_leader_signet_payment(
        state, DomainAction(action_id="pay_leader_signet_spice", actor=0)
    ).state
    assert paid.players[0].resources.spice == 0
    anywhere = legal_leader_signet_actions(paid, 0)
    assert all(a.action_id == "place_leader_spy" for a in anywhere)
    assert len(anywhere) == 13
    placed = apply_leader_spy_action(paid, anywhere[0]).state
    assert len(placed.players[0].spy_post_ids) == 1
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


# --- Liet Kynes --------------------------------------------------------------


def test_arrakis_planetologist_ignores_sietch_tabr_and_replaces_sandworms() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="liet_kynes",
        hand=(RECON, DUNE),
        maker_hooks=True,
        resources=Resources(water=2),
    )
    state = _turn_state(owner)
    assert any(
        dict(a.arguments)["space_id"] == "sietch_tabr"
        for a in legal_agent_actions(state, 0)
    )
    placed = _play(state, DUNE, "hagga_basin")
    maker = legal_maker_space_actions(placed, 0)
    summon = next(a for a in maker if a.action_id == "summon_maker_sandworms")
    replaced = apply_maker_space_action(placed, summon)
    seat = replaced.state.players[0]
    assert seat.sandworms_conflict == 0
    assert seat.resources.spice == 1
    assert len(seat.intrigue_cards) == 1
    assert "sandworms_replaced" in {event.kind for event in replaced.events}
    frame = replaced.state.decision_stack[-1]
    assert frame.kind == "optional_trash"
    options = legal_optional_trash_actions(replaced.state, 0)
    assert options[0].action_id == "decline_optional_trash"
    trash_recon = next(a for a in options[1:] if dict(a.arguments)["card_id"] == RECON)
    trashed = apply_optional_trash(replaced.state, trash_recon).state
    assert RECON in trashed.players[0].trashed
    assert trashed.decision_stack[-1].kind != "optional_trash"


def test_judge_of_the_change_rewards_the_visited_space_kind() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="liet_kynes",
        hand=(SIGNET,),
        influence=Influence(emperor=2),
    )
    engine = UprisingRulesEngine()
    for space_id, expected in (
        ("assembly_hall", Resources(water=2)),
        ("arrakeen", Resources(solari=1, water=1)),
        ("accept_contract", Resources(spice=1, water=1)),
    ):
        placed = _play(_turn_state(owner), SIGNET, space_id)
        resolved = resolve_leader_signet(placed).state
        assert resolved.players[0].resources == expected, space_id
    del engine
