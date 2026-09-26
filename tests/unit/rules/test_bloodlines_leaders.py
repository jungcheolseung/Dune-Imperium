"""Tests for the Bloodlines Leaders (card faces, ``docs/rules/bloodlines.md`` §6).

Rule sources: the Leader card faces transcribed on 2026-09-07 and the
Bloodlines rulebook clarifications [Bloodlines p. 12]; project conventions
are OQ-037 (Into the Fray) and the Chani/Kynes readings recorded in the
Leader audit.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
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
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.leader_abilities import (
    apply_feyd_track_action,
    apply_leader_agent_deploy,
    apply_leader_card_trash,
    apply_leader_signet_payment,
    apply_leader_spy_action,
    apply_leader_troop_retreat,
    legal_feyd_track_actions,
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


def _cleanup_state(chani: PlayerState) -> GameState:
    return replace(
        _turn_state(chani),
        phase=GamePhase.COMBAT,
        first_player=0,
        combat_intrigue_complete=True,
        combat_rewards_resolved=True,
        decision_stack=(),
        players=(
            chani,
            *(PlayerState(player_id=seat, has_revealed=True) for seat in range(1, 4)),
        ),
    )


def test_tactician_advances_for_units_lost_at_combat_cleanup() -> None:
    # "Chani (Leader) -- When resolving combat, troops that return to your
    # supply are considered 'lost.' Each different source of retreating or
    # losing troops is handled separately" [FAQ p. 1]; Tactician advances
    # "that many spaces, earning rewards as you reach them" [Chani card].
    # Commanders are troops [Bloodlines p. 4].
    from dune_imperium.rules.combat import finish_combat

    chani = PlayerState(
        player_id=0,
        leader_id="chani",
        has_revealed=True,
        tactics_track_space=2,
        troops_supply=9,
        troops_garrison=0,
        troops_conflict=3,
        commanders_conflict=1,
        combat_strength=8,
    )
    result = finish_combat(_cleanup_state(chani))
    seat = result.state.players[0]
    assert seat.troops_conflict == 0 and seat.troops_supply == 12
    assert seat.tactics_track_space == 6
    assert seat.resources.spice == 1  # the sixth space
    assert any(
        event.kind == "tactics_token_advanced" and dict(event.payload)["count"] == 4
        for event in result.events
    )

    # The cleanup is one source: passing the end pays the water once and
    # resets without advancing for the extra troops [Bloodlines p. 12].
    near_end = replace(chani, tactics_track_space=8)
    seat = finish_combat(_cleanup_state(near_end)).state.players[0]
    assert seat.tactics_track_space == 2
    assert seat.resources.water == 1 + 1
    assert seat.resources.spice == 0


def test_tactician_advances_once_for_one_multi_troop_loss() -> None:
    # Gruesome Sacrifice's "lose two troops" is one source [FAQ p. 1]: "If
    # you lose or retreat enough troops that you would pass the end of the
    # Tactics track, you still reset at the starting space (and do not
    # advance for those extra troops)" [Bloodlines p. 12].
    from dune_imperium.content.immortality.board import RESEARCH_START_ID
    from dune_imperium.rules.combat import begin_combat_intrigue
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:gruesome_sacrifice:0"
    chani = PlayerState(
        player_id=0,
        leader_id="chani",
        has_revealed=True,
        research_space=RESEARCH_START_ID,
        tactics_track_space=9,
        intrigue_cards=(card,),
        troops_supply=9,
        troops_garrison=0,
        troops_conflict=3,
        combat_strength=6,
    )
    state = GameState(
        config=RulesetConfig(bloodlines=True, immortality=True),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=(
            chani,
            *(
                PlayerState(
                    player_id=seat, has_revealed=True, research_space=RESEARCH_START_ID
                )
                for seat in range(1, 4)
            ),
        ),
    )
    state = begin_combat_intrigue(state).state
    play = next(
        action
        for action in legal_intrigue_play_actions(state, 0)
        if dict(action.arguments).get("card_id") == card
    )
    played = apply_intrigue_play(state, play).state
    for _ in range(2):
        loss = next(
            action
            for action in legal_intrigue_choice_actions(played, 0)
            if action.action_id == "lose_intrigue_troop"
        )
        played = apply_intrigue_choice(played, loss).state
    seat = played.players[0]
    assert seat.troops_conflict == 1
    assert seat.tactics_track_space == 2  # not 3
    assert seat.resources.water == 1 + 1


def test_fedaykin_maneuver_retreats_any_number_or_draws_two_cards() -> None:
    # The paid half prints "2 Influence: [water] -> [two green card icons]";
    # the green card is the draw icon (assets/icons/draw.png), not a troop
    # cube [Chani card]. It was transcribed as two troops until 2026-09-25.
    owner = PlayerState(
        player_id=0,
        leader_id="chani",
        tactics_track_space=2,
        hand=(SIGNET,),
        deck=(DAGGER, DUNE, RECON),
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

    result = apply_leader_signet_payment(
        state, DomainAction(action_id="pay_leader_signet_water", actor=0)
    )
    paid = result.state
    seat = paid.players[0]
    assert seat.resources.water == 0
    assert len(seat.hand) == 2 and len(seat.deck) == 1
    assert sorted((*seat.hand, *seat.deck)) == sorted((DAGGER, DUNE, RECON))
    # No troop is recruited.
    assert seat.troops_supply == 7 and seat.troops_garrison == 3
    assert dict(paid.decision_stack[-1].context)["troops_recruited"] == 0
    resolved = next(e for e in result.events if e.kind == "leader_signet_resolved")
    assert dict(resolved.payload) == {"cards": 2, "player": 0, "water": 1}


def test_fedaykin_maneuver_draw_shuffles_the_discard_when_the_deck_is_short() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="chani",
        tactics_track_space=2,
        hand=(SIGNET,),
        deck=(DAGGER,),
        discard_pile=(DUNE, RECON),
        resources=Resources(water=1),
        influence=Influence(fremen=2),
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    paid = apply_leader_signet_payment(
        state, DomainAction(action_id="pay_leader_signet_water", actor=0)
    ).state
    reshuffle = paid.decision_stack[-1]
    assert reshuffle.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    assert isinstance(reshuffle.decision, ChanceDecision)
    assert dict(reshuffle.context)["count"] == 2
    assert paid.players[0].resources.water == 0


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


def test_corrino_liaison_spy_has_deep_cover() -> None:
    # The card prints the Spy with Deep Cover icon (a gold Spy behind a grey
    # one, as on Deliver Supplies), not the plain Spy of Mohiam's Listeners
    # [Count Hasimir Fenring card]. Deep Cover places a Spy by the normal
    # rules but may "ignore any opponents' Spies"; a post holding the
    # owner's own Spy stays closed [Bloodlines pp. 5, 12]
    # (docs/rules/bloodlines.md §4).
    emperor_post = "emperor-sardaukar-dutiful-service"
    other_post = "choam-shipping-accept-contract"
    owner = PlayerState(player_id=0, leader_id="count_hasimir_fenring", hand=(SIGNET,))
    rival = PlayerState(
        player_id=1, spies_supply=2, spy_post_ids=(emperor_post,)
    )
    base = _turn_state(owner)
    state = _play(
        replace(base, players=(owner, rival, *base.players[2:])), SIGNET, "arrakeen"
    )
    spies = [
        a
        for a in legal_leader_signet_actions(state, 0)
        if a.action_id == "place_leader_spy"
    ]
    assert [dict(a.arguments)["post_id"] for a in spies] == [emperor_post]
    placed = apply_leader_spy_action(state, spies[0]).state
    assert placed.players[0].spy_post_ids == (emperor_post,)
    assert placed.players[1].spy_post_ids == (emperor_post,)

    # With no Spy in supply, any Spy may first be recalled for no effect
    # [Main pp. 11, 20]; the rival's Spy on the post does not block.
    elsewhere = (other_post, "arrakis-deep-desert", "fremen-desert-tactics-fremkit")
    drained = replace(owner, spies_supply=0, spy_post_ids=elsewhere)
    state = _play(
        replace(base, players=(drained, rival, *base.players[2:])), SIGNET, "arrakeen"
    )
    recalls = {
        dict(a.arguments)["post_id"]
        for a in legal_leader_signet_actions(state, 0)
        if a.action_id == "recall_spy_for_leader_placement"
    }
    assert recalls == set(elsewhere)

    # His own Spy on the post blocks it.
    own = replace(owner, spies_supply=2, spy_post_ids=(emperor_post,))
    state = _play(replace(base, players=(own, *base.players[1:])), SIGNET, "arrakeen")
    assert not [
        a
        for a in legal_leader_signet_actions(state, 0)
        if a.action_id == "place_leader_spy"
    ]


_SPIES_ELSEWHERE = (
    "choam-shipping-accept-contract",
    "arrakis-deep-desert",
    "fremen-desert-tactics-fremkit",
)


def _recall_first(state: GameState) -> GameState:
    recall = next(
        a
        for a in legal_leader_signet_actions(state, 0)
        if a.action_id == "recall_spy_for_leader_placement"
    )
    return apply_leader_spy_action(state, recall).state


def test_corrino_liaison_recall_first_commits_to_the_spy() -> None:
    # "If you have no Spies in your supply when you need to place one, you
    # may first recall one of your Spies for no effect" [Main p. 11]: the
    # recall is the first step of the Spy half of "You may trash a card in
    # your play area. —OR— [Deep Cover Spy] on [Emperor]" [Count Hasimir
    # Fenring card], and "각각 recall한 뒤에는 배치만 남는다" (OQ-057 (14)).
    # Before, the decline and the trash half stayed on offer, so he could
    # keep a counted recall (spies_recalled_turn) and trash as well.
    owner = PlayerState(
        player_id=0,
        leader_id="count_hasimir_fenring",
        hand=(SIGNET, RECON),
        spies_supply=0,
        spy_post_ids=_SPIES_ELSEWHERE,
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    assert {a.action_id for a in legal_leader_signet_actions(state, 0)} == {
        "decline_leader_signet_payment",
        "recall_spy_for_leader_placement",
        "trash_leader_card",
    }
    recalled = _recall_first(state)
    assert recalled.players[0].spies_supply == 1
    assert [
        (a.action_id, dict(a.arguments)["post_id"])
        for a in legal_leader_signet_actions(recalled, 0)
    ] == [("place_leader_spy", "emperor-sardaukar-dutiful-service")]


def test_listeners_recall_first_leaves_only_the_spy_halves() -> None:
    # Listeners: "[Spy] on [Landsraad] —OR— [1 spice] → [Spy]" [Gaius Helen
    # Mohiam card]. Both halves place a Spy, so after the recall-first
    # [Main p. 11] either remains, but the recalled Spy must be placed
    # (OQ-057 (14)): no decline.
    owner = PlayerState(
        player_id=0,
        leader_id="gaius_helen_mohiam",
        hand=(SIGNET,),
        resources=Resources(spice=1),
        spies_supply=0,
        spy_post_ids=_SPIES_ELSEWHERE,
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    assert "decline_leader_signet_payment" in {
        a.action_id for a in legal_leader_signet_actions(state, 0)
    }
    recalled = _recall_first(state)
    actions = legal_leader_signet_actions(recalled, 0)
    assert {a.action_id for a in actions} == {
        "place_leader_spy",
        "pay_leader_signet_spice",
    }
    assert {
        dict(a.arguments)["post_id"]
        for a in actions
        if a.action_id == "place_leader_spy"
    } == {
        "landsraad-high-council-imperial-privilege-swordmaster",
        "landsraad-assembly-hall-gather-support",
    }
    # Paying after the recall still ends in a placement, never a decline.
    paid = apply_leader_signet_payment(
        recalled, DomainAction(action_id="pay_leader_signet_spice", actor=0)
    ).state
    assert {a.action_id for a in legal_leader_signet_actions(paid, 0)} == {
        "place_leader_spy"
    }


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




def test_into_the_fray_is_not_offered_once_the_agent_has_left_its_space() -> None:
    # Ghola's copy of the Signet box (or any second look at it) after the
    # Agent already deployed has nothing to move (heuristic soak seed 5006).
    owner = PlayerState(player_id=0, leader_id="duncan_idaho", hand=(SIGNET,))
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    deploy = next(
        action
        for action in legal_leader_signet_actions(state, 0)
        if action.action_id == "deploy_leader_agent"
    )
    fighting = apply_leader_agent_deploy(state, deploy).state
    assert fighting.players[0].agent_in_conflict == 1
    frame = fighting.decision_stack[-1]
    context = dict(frame.context)
    context["pending_agent_effect"] = True
    reopened = replace(
        fighting,
        decision_stack=(
            *fighting.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )
    assert [a.action_id for a in legal_leader_signet_actions(reopened, 0)] == [
        "decline_leader_signet_payment"
    ]

def test_imperial_privilege_may_recall_the_into_the_fray_agent() -> None:
    # Designer ruling (Message from designer, designer-rulings-audit.md): the
    # Agent Duncan sent into the Conflict is still one of his Agents, so a
    # later Imperial Privilege visit may recall it [Board Guide p. 2]
    # (OQ-037(d)).
    from dune_imperium.rules.board_effects import (
        apply_imperial_privilege_action,
        legal_imperial_privilege_actions,
    )

    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(DAGGER,),
        deck=(RECON,),
        resources=Resources(solari=3),
        influence=Influence(emperor=2),
        agents_available=1,
        agent_in_conflict=1,
    )
    state = _play(_turn_state(owner), DAGGER, "imperial_privilege")
    assert state.players[0].units_in_conflict == 1
    decline = next(
        action
        for action in legal_imperial_privilege_actions(state, 0)
        if action.action_id == "decline_imperial_privilege_intrigue"
    )
    declined = apply_imperial_privilege_action(state, decline).state
    recalls = legal_imperial_privilege_actions(declined, 0)
    assert [action.action_id for action in recalls] == [
        "recall_conflict_agent_for_imperial_privilege"
    ]

    result = apply_imperial_privilege_action(declined, recalls[0])
    seat = result.state.players[0]
    assert seat.agent_in_conflict == 0
    assert seat.units_in_conflict == 0
    assert seat.agents_available == 1
    assert seat.agent_locations == ("imperial_privilege",)
    assert seat.hand == (RECON,)
    recalled = next(event for event in result.events if event.kind == "agent_recalled")
    assert dict(recalled.payload)["space_id"] == "conflict"
    # The recall was available, so nothing was skipped.
    assert not any(
        event.kind == "imperial_privilege_recall_skipped" for event in result.events
    )
    engine = UprisingRulesEngine()
    assert result.state.players[0].combat_strength == 0
    assert engine.legal_actions(result.state, 0) == ()


def _signet_into_the_fray_at_imperial_privilege(earlier_in_conflict: int) -> GameState:
    from dune_imperium.rules.board_effects import (
        apply_imperial_privilege_action,
        legal_imperial_privilege_actions,
    )

    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(SIGNET,),
        deck=(RECON,),
        resources=Resources(solari=3),
        influence=Influence(emperor=2),
        agents_available=2 - earlier_in_conflict,
        agent_in_conflict=earlier_in_conflict,
    )
    state = _play(_turn_state(owner), SIGNET, "imperial_privilege")
    deploy = next(
        action
        for action in legal_leader_signet_actions(state, 0)
        if action.action_id == "deploy_leader_agent"
    )
    fighting = apply_leader_agent_deploy(state, deploy).state
    assert fighting.players[0].agent_locations == ()
    assert fighting.players[0].agent_in_conflict == earlier_in_conflict + 1
    decline = next(
        action
        for action in legal_imperial_privilege_actions(fighting, 0)
        if action.action_id == "decline_imperial_privilege_intrigue"
    )
    return apply_imperial_privilege_action(fighting, decline).state


def test_imperial_privilege_never_recalls_this_turns_into_the_fray_agent() -> None:
    # "Recall one of your other Agents from the board, and draw a card."
    # [Board Guide p. 2]; docs/rules/board-spaces.md: "이번 turn에 보낸
    # Agent가 아닌 자신의 다른 Agent 1개를 recall", and OQ-037 (d) allows
    # recalling an Into the Fray Agent only "뒤의 turn에" (on a later turn).
    # Resolving Into the Fray first moves this turn's Agent to the Conflict;
    # it used to be the only (forced) recall target, so Duncan got back the
    # Agent he had just sent. Now the recall is skipped and the card is still
    # drawn (OQ-023).
    from dune_imperium.rules.board_effects import legal_imperial_privilege_actions

    declined = _signet_into_the_fray_at_imperial_privilege(earlier_in_conflict=0)

    assert legal_imperial_privilege_actions(declined, 0) == ()
    seat = declined.players[0]
    assert seat.agent_in_conflict == 1
    assert seat.agents_available == 1
    assert seat.hand == (RECON,)


def test_imperial_privilege_recalls_an_earlier_into_the_fray_agent_only() -> None:
    # An Agent Into the Fray sent on an earlier turn (OQ-037 (e)) is one of
    # the "other Agents" [Board Guide p. 2]: one recall stays on offer and
    # this turn's Agent stays in the Conflict.
    from dune_imperium.rules.board_effects import (
        apply_imperial_privilege_action,
        legal_imperial_privilege_actions,
    )

    declined = _signet_into_the_fray_at_imperial_privilege(earlier_in_conflict=1)
    recalls = legal_imperial_privilege_actions(declined, 0)
    assert [action.action_id for action in recalls] == [
        "recall_conflict_agent_for_imperial_privilege"
    ]
    seat = apply_imperial_privilege_action(declined, recalls[0]).state.players[0]
    assert seat.agent_in_conflict == 1
    assert seat.agents_available == 1


def test_two_into_the_fray_agents_recall_one_at_a_time_and_return_at_cleanup() -> None:
    # A Servo-Receivers Signet can send a second "Agent you sent this turn"
    # into the Conflict [Duncan Idaho card] (OQ-037(e)). Imperial Privilege
    # recalls "one of your other Agents" [Board Guide p. 2] (OQ-037(d)), so
    # one of the two leaves; the Combat cleanup returns every Agent still
    # there.
    from dune_imperium.rules.board_effects import (
        apply_imperial_privilege_action,
        legal_imperial_privilege_actions,
    )
    from dune_imperium.rules.combat import finish_combat

    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(DAGGER,),
        deck=(RECON,),
        resources=Resources(solari=3),
        influence=Influence(emperor=2),
        swordmaster_acquired=True,
        agents_available=1,
        agent_in_conflict=2,
    )
    state = _play(_turn_state(owner), DAGGER, "imperial_privilege")
    assert units_strength(state.players[0]) == 3 + 3
    decline = next(
        action
        for action in legal_imperial_privilege_actions(state, 0)
        if action.action_id == "decline_imperial_privilege_intrigue"
    )
    declined = apply_imperial_privilege_action(state, decline).state
    recall = next(
        action
        for action in legal_imperial_privilege_actions(declined, 0)
        if action.action_id == "recall_conflict_agent_for_imperial_privilege"
    )
    seat = apply_imperial_privilege_action(declined, recall).state.players[0]
    assert seat.agent_in_conflict == 1
    assert seat.agents_available == 1
    assert units_strength(seat) == 3

    fighting = replace(
        owner, has_revealed=True, hand=(), agents_available=1, combat_strength=6
    )
    cleaned = finish_combat(_cleanup_state(fighting)).state.players[0]
    assert cleaned.agent_in_conflict == 0
    assert cleaned.agents_available == 3


def test_sardaukar_ii_recalls_an_earlier_into_the_fray_agent_instead_of_fizzling() -> (
    None
):
    # User ruling (2026-09-26, verbatim): "Duncan Idaho(Bloodlines) Into the
    # Fray의 Agent를 Imperial Privilege로 recall 가능 이니까 recall agent
    # 기능으로 되는건 모두 같게 동작해야지. 사다우카 계약 완료보상이나 원로회
    # 계약 완료보상에 있는 recall agent도 마찬가지겠지" (OQ-068): an earlier
    # turn's Into the Fray Agent in the Conflict is one of "your Agents"
    # [Main p. 20] Sardaukar II's reward may recall too, so it no longer
    # fizzles; this turn's own Agent, still on the board, is never offered.
    from dune_imperium.rules.contracts import (
        apply_contract_completion,
        apply_contract_recall_action,
        legal_contract_completion_actions,
        legal_contract_recall_actions,
    )

    truthtrance = next(
        card_id
        for card_id in imperium_deck_instance_ids(True)
        if ":truthtrance:" in card_id
    )
    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(truthtrance,),
        deck=(RECON,),
        resources=Resources(spice=4),
        agents_available=1,
        agent_in_conflict=1,
        active_contract_ids=("contract:sardaukar_ii",),
    )
    state = _turn_state(owner, config=RulesetConfig(bloodlines=True, choam_module=True))
    placed = _play(state, truthtrance, "sardaukar")
    completion = next(
        action
        for action in legal_contract_completion_actions(placed, 0)
        if dict(action.arguments)["instance_id"] == "contract:sardaukar_ii"
    )
    completed = apply_contract_completion(placed, completion).state

    recalls = legal_contract_recall_actions(completed, 0)
    assert [action.action_id for action in recalls] == [
        "recall_conflict_agent_for_contract"
    ]
    resolved = apply_contract_recall_action(completed, recalls[0]).state.players[0]
    assert resolved.agent_in_conflict == 0
    assert resolved.agents_available == 1
    assert resolved.agent_locations == ("sardaukar",)


def test_sardaukar_ii_conflict_recall_updates_combat_strength_through_the_engine() -> (
    None
):
    # Review round 1 blocker: recall_conflict_agent_for_contract must be
    # registered in engine.ACTION_HANDLERS
    # (src/dune_imperium/rules/engine.py) exactly like recall_agent_for_
    # contract, or choosing it through UprisingRulesEngine raises KeyError --
    # it is the only legal action once the reward opens with no board Agent
    # left to recall. The running Combat strength [Main p. 12] the engine
    # keeps current (refresh_pre_reveal_strength) is what a real turn
    # actually depends on.
    engine = UprisingRulesEngine()
    truthtrance = next(
        card_id
        for card_id in imperium_deck_instance_ids(True)
        if ":truthtrance:" in card_id
    )
    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(truthtrance,),
        deck=(RECON,),
        resources=Resources(spice=4),
        agents_available=1,
        agent_in_conflict=1,
        active_contract_ids=("contract:sardaukar_ii",),
    )
    state = _turn_state(owner, config=RulesetConfig(bloodlines=True, choam_module=True))
    placement = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("space_id") == "sardaukar"
    )
    placed = engine.apply(state, placement).state
    assert placed.players[0].combat_strength == 2

    completion = next(
        action
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "complete_contract"
        and dict(action.arguments)["instance_id"] == "contract:sardaukar_ii"
    )
    completed = engine.apply(placed, completion).state

    recall = next(
        action
        for action in engine.legal_actions(completed, 0)
        if action.action_id == "recall_conflict_agent_for_contract"
    )
    result = engine.apply(completed, recall)

    assert result.state.players[0].combat_strength == 0
    assert result.state.players[0].agent_in_conflict == 0
    assert result.state.players[0].agents_available == 1


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


# --- Esmar Tuek --------------------------------------------------------------


def _esmar_state(owner: PlayerState, **overrides: object) -> GameState:
    values: dict[str, object] = {
        "maker_bonus_spice": (
            ("deep_desert", 0),
            ("hagga_basin", 2),
            ("imperial_basin", 0),
            ("tuek_sietch", 1),
        )
    }
    values.update(overrides)
    return _turn_state(owner, **values)


def test_tueks_sietch_is_on_the_table_only_with_esmar_tuek() -> None:
    from dune_imperium.rules.board_effects import (
        apply_tuek_sietch_action,
        legal_tuek_sietch_actions,
    )

    absent = _turn_state(PlayerState(player_id=0, leader_id="chani", hand=(DUNE,)))
    assert not any(
        dict(a.arguments)["space_id"] == "tuek_sietch"
        for a in legal_agent_actions(absent, 0)
    )
    owner = PlayerState(
        player_id=0, leader_id="esmar_tuek", hand=(DUNE,), deck=(RECON,)
    )
    state = _esmar_state(owner)
    placed = _play(state, DUNE, "tuek_sietch")
    # Own visit: one Solari; the printed row then takes the bonus spice
    # plus one spice or a card.
    assert placed.players[0].resources.solari == 1
    actions = legal_tuek_sietch_actions(placed, 0)
    assert [a.action_id for a in actions] == [
        "take_tuek_sietch_spice",
        "take_tuek_sietch_card",
    ]
    spiced = apply_tuek_sietch_action(placed, actions[0]).state
    assert spiced.players[0].resources.spice == 1 + 1
    assert dict(spiced.maker_bonus_spice)["tuek_sietch"] == 0
    carded = apply_tuek_sietch_action(placed, actions[1]).state
    assert carded.players[0].resources.spice == 1
    assert len(carded.players[0].hand) == 1


def test_an_opponent_visiting_tueks_sietch_draws_esmar_an_intrigue_card() -> None:
    esmar = PlayerState(player_id=1, leader_id="esmar_tuek")
    owner = PlayerState(player_id=0, leader_id="chani", hand=(DUNE,))
    state = _esmar_state(owner)
    state = replace(state, players=(state.players[0], esmar, *state.players[2:]))
    placed = _play(state, DUNE, "tuek_sietch")
    assert len(placed.players[1].intrigue_cards) == 1
    assert placed.players[1].resources.solari == 0
    assert placed.players[0].resources.solari == 0


def test_smuggle_spice_moves_bonus_spice_on_or_off_maker_spaces() -> None:
    from dune_imperium.rules.leader_abilities import apply_leader_bonus_spice

    owner = PlayerState(player_id=0, leader_id="esmar_tuek", hand=(SIGNET,))
    state = _play(_esmar_state(owner), SIGNET, "arrakeen")
    actions = legal_leader_signet_actions(state, 0)
    # "Place 1 bonus spice on Tuek's Sietch. -OR- Take 1 bonus spice from a
    # Maker board space." prints no "may" [Esmar Tuek card]: "Most effects
    # from a board space or card you play are mandatory" [FAQ p. 3], so the
    # Signet offers no refusal.
    assert [tuple(a.arguments) for a in actions] == [
        (),
        (("space_id", "hagga_basin"),),
        (("space_id", "tuek_sietch"),),
    ]
    assert actions[0].action_id == "place_leader_bonus_spice"
    assert all(a.action_id != "decline_leader_signet_payment" for a in actions)
    placed = apply_leader_bonus_spice(state, actions[0]).state
    assert dict(placed.maker_bonus_spice)["tuek_sietch"] == 2
    taken = apply_leader_bonus_spice(state, actions[1]).state
    assert dict(taken.maker_bonus_spice)["hagga_basin"] == 1
    assert taken.players[0].resources.spice == 1


def test_makers_phase_feeds_tueks_sietch_like_the_other_maker_spaces() -> None:
    from dune_imperium.rules.phases import resolve_makers

    owner = PlayerState(player_id=0, leader_id="esmar_tuek")
    state = _esmar_state(owner, phase=GamePhase.MAKERS, decision_stack=())
    fed = resolve_makers(state).state
    assert dict(fed.maker_bonus_spice)["tuek_sietch"] == 2


# --- Signet trashes that recruit ---------------------------------------------
#
# Eliminate Allies: "When this card is trashed: 2 troops" [Eliminate Allies
# card]. "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할
# 수 있다" [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md). Trashed
# through a Signet Ring box, the two troops used to vanish from the Agent
# turn's allowance: the box wrote back the context it had read before the
# trash, overwriting the count the trash had added.

ELIMINATE_ALLIES = "imperium:eliminate_allies:0"


def _allowance(state: GameState) -> tuple[object, list[object]]:
    """Return the Agent turn's recruit count and the offered deploy counts."""

    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    counts: list[object] = [
        dict(a.arguments)["count"] for a in legal_combat_deployments(state, 0)
    ]
    return dict(frame.context)["troops_recruited"], counts


def _trash_by_signet(state: GameState, card_id: str) -> GameState:
    action = next(
        a
        for a in legal_leader_signet_actions(state, 0)
        if a.action_id == "trash_leader_card"
        and dict(a.arguments)["card_id"] == card_id
    )
    return apply_leader_card_trash(state, action).state


def test_chroniclers_insight_trash_keeps_eliminate_allies_troops_deployable() -> (
    None
):
    owner = PlayerState(
        player_id=0, leader_id="princess_irulan", hand=(SIGNET, ELIMINATE_ALLIES)
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    trashed = _trash_by_signet(state, ELIMINATE_ALLIES)
    assert trashed.players[0].troops_garrison == 3 + 2
    # Two recruited plus up to two more from the garrison [Main p. 10].
    assert _allowance(trashed) == (2, [1, 2, 3, 4])


def test_corrino_liaison_trash_keeps_eliminate_allies_troops_deployable() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="count_hasimir_fenring",
        hand=(SIGNET,),
        in_play=(ELIMINATE_ALLIES,),
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    trashed = _trash_by_signet(state, ELIMINATE_ALLIES)
    assert trashed.players[0].resources.solari == 1  # Assassin
    assert _allowance(trashed) == (2, [1, 2, 3, 4])


def test_personal_training_trash_keeps_eliminate_allies_troops_deployable() -> (
    None
):
    owner = PlayerState(
        player_id=0,
        leader_id="feyd_rautha_harkonnen",
        hand=(SIGNET, ELIMINATE_ALLIES),
        feyd_track_space="first_spy",
    )
    state = _play(_turn_state(owner), SIGNET, "arrakeen")
    (advance,) = legal_feyd_track_actions(state, 0)
    staged = apply_feyd_track_action(state, advance).state
    trash = next(
        a
        for a in legal_feyd_track_actions(staged, 0)
        if dict(a.arguments).get("card_id") == ELIMINATE_ALLIES
    )
    trashed = apply_feyd_track_action(staged, trash).state
    assert ELIMINATE_ALLIES in trashed.players[0].trashed
    assert _allowance(trashed) == (2, [1, 2, 3, 4])
