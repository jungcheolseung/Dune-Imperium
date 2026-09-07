"""Tests for Piter De Vries and his Twisted Intrigue deck (Bloodlines).

Rule sources: the Piter De Vries and Twisted Intrigue card faces
(transcribed 2026-09-07); project conventions OQ-038 (the loser picks the
zone and kind of a lost troop; the Signet troop is simply not counted as
recruited this turn).
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import (
    intrigue_deck_instance_ids,
    twisted_intrigue_instance_ids,
)
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
from dune_imperium.core.observation import observe_state
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.intrigue import (
    legal_intrigue_choice_actions,
    legal_intrigue_play_actions,
)
from dune_imperium.rules.leader_abilities import resolve_leader_signet
from dune_imperium.rules.setup import create_initial_state

BLOODLINES = RulesetConfig(bloodlines=True)
SIGNET = "player:0:starter:signet_ring:0"
DAGGER = "player:0:starter:dagger:0"
RECON = "player:0:starter:reconnaissance:0"
ENGINE = UprisingRulesEngine()


def _twisted(slug: str) -> str:
    return f"intrigue:twisted_{slug}:0"


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


def _play(card_id: str, option: int = 0, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=actor,
        arguments=(("card_id", card_id), ("option", option)),
    )


def _placed(state: GameState, card_id: str, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == card_id
    )
    return apply_agent_action(state, action).state


def _combat_state(owner: PlayerState) -> GameState:
    from dune_imperium.rules.combat import begin_combat_intrigue

    seats = (owner, *(PlayerState(player_id=seat) for seat in range(1, 4)))
    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=tuple(replace(seat, has_revealed=True) for seat in seats),
    )
    return begin_combat_intrigue(state).state


# --- Piter De Vries ----------------------------------------------------------


def test_piter_is_dealt_the_twisted_deck_and_draws_one_each_round() -> None:
    setup = create_initial_state(
        BLOODLINES,
        seed=3,
        leader_ids=("piter_de_vries", "gurney_halleck", "chani", "lady_jessica"),
    )
    piter = setup.state.players[0]
    assert set(piter.twisted_deck) == set(twisted_intrigue_instance_ids())
    assert setup.state.twisted_deck_stock == ()
    assert all(not seat.twisted_deck for seat in setup.state.players[1:])
    from dune_imperium.rules.phases import begin_round, prepare_round_start

    begun = prepare_round_start(setup.state).state
    if begun.phase is GamePhase.ROUND_START:
        begun = begin_round(begun).state
    piter = begun.players[0]
    assert len(piter.twisted_deck) == 11
    assert len(piter.intrigue_cards) == 1
    assert piter.intrigue_cards[0].startswith("intrigue:twisted_")
    # Nobody else could learn the deck order or the drawn card.
    view = observe_state(begun, 1)
    assert view.players[0].twisted_deck_size == 11


def test_harkonnen_advisor_troop_is_not_deployable_this_turn() -> None:
    owner = PlayerState(player_id=0, leader_id="piter_de_vries", hand=(SIGNET,))
    state = _placed(_turn_state(owner), SIGNET, "arrakeen")
    resolved = resolve_leader_signet(state).state
    seat = resolved.players[0]
    # Arrakeen's own troop is still pending; the Signet troop arrived.
    assert seat.troops_garrison == 3 + 1
    context = dict(resolved.decision_stack[-1].context)
    assert context["troops_recruited"] == 0
    assert context["undeployable_troops"] == 1
    # Arrakeen is a Combat space: two garrison troops may deploy, but the
    # Signet troop is not one of them, so only three are available.
    from dune_imperium.rules.combat_deployment import legal_combat_deployments

    counts = {dict(a.arguments)["count"] for a in legal_combat_deployments(resolved, 0)}
    assert counts == {1, 2}
    thin = replace(
        resolved,
        players=(
            replace(seat, troops_supply=seat.troops_supply + 3, troops_garrison=1),
            *resolved.players[1:],
        ),
    )
    assert legal_combat_deployments(thin, 0) == ()


# --- Twisted Intrigue --------------------------------------------------------


def test_ambitious_loses_three_troops_for_influence_where_an_opponent_leads() -> None:
    card = _twisted("ambitious")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(card,),
        troops_supply=6,
        troops_garrison=2,
        troops_conflict=4,
        combat_strength=8,
    )
    rival = replace(PlayerState(player_id=1), influence=Influence(fremen=2))
    state = _turn_state(owner)
    state = replace(state, players=(state.players[0], rival, *state.players[2:]))
    assert _play(card) in legal_intrigue_play_actions(state, 0)
    played = ENGINE.apply(state, _play(card)).state
    losses = legal_intrigue_choice_actions(played, 0)
    assert {tuple(a.arguments) for a in losses} == {
        (("zone", "garrison"),),
        (("zone", "conflict"),),
    }
    working = played
    for zone in ("garrison", "garrison", "conflict"):
        working = ENGINE.apply(
            working,
            DomainAction(
                action_id="lose_intrigue_troop", actor=0, arguments=(("zone", zone),)
            ),
        ).state
    factions = legal_intrigue_choice_actions(working, 0)
    assert [dict(a.arguments)["faction"] for a in factions] == ["fremen"]
    done = ENGINE.apply(working, factions[0]).state
    seat = done.players[0]
    assert seat.influence.fremen == 1
    assert (seat.troops_garrison, seat.troops_conflict, seat.troops_supply) == (0, 3, 9)
    assert card in done.intrigue_discard

    # Without a leading opponent the card cannot be played.
    lonely = _turn_state(owner)
    assert _play(card) not in legal_intrigue_play_actions(lonely, 0)


def test_calculating_pays_per_unit_type_in_the_conflict() -> None:
    card = _twisted("calculating")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(card,),
        troops_supply=8,
        troops_conflict=1,
        commanders_supply=0,
        commanders_conflict=1,
        sandworms_conflict=1,
        combat_strength=7,
    )
    done = ENGINE.apply(_turn_state(owner), _play(card)).state
    assert done.players[0].resources.solari == 3


def test_controlled_peeks_the_top_card_privately() -> None:
    card = _twisted("controlled")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(card,),
        deck=(DAGGER, RECON),
        resources=Resources(solari=1, water=1),
    )
    state = _turn_state(owner)
    peeking = ENGINE.apply(state, _play(card)).state
    own_view = observe_state(peeking, 0).private
    rival_view = observe_state(peeking, 1).private
    assert own_view is not None and own_view.peeked_card_id == DAGGER
    assert rival_view is not None and rival_view.peeked_card_id == ""
    choices = {a.action_id for a in legal_intrigue_choice_actions(peeking, 0)}
    assert choices == {
        "put_back_top_card",
        "discard_top_card",
        "draw_top_card_for_solari",
    }
    drawn = ENGINE.apply(
        peeking, DomainAction(action_id="draw_top_card_for_solari", actor=0)
    ).state
    assert drawn.players[0].hand == (DAGGER,)
    assert drawn.players[0].resources.solari == 0
    discarded = ENGINE.apply(
        peeking, DomainAction(action_id="discard_top_card", actor=0)
    ).state
    assert discarded.players[0].discard_pile == (DAGGER,)
    kept = ENGINE.apply(
        peeking, DomainAction(action_id="put_back_top_card", actor=0)
    ).state
    assert kept.players[0].deck == (DAGGER, RECON)
    # The Combat half is one sword.
    fighter = replace(owner, troops_supply=8, troops_conflict=1, combat_strength=2)
    combat = _combat_state(fighter)
    struck = ENGINE.apply(combat, _play(card, 1)).state
    assert struck.players[0].combat_strength == 3


def test_devious_trashes_from_hand_without_a_decline_or_deploys_two() -> None:
    card = _twisted("devious")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(card,),
        hand=(DAGGER,),
        discard_pile=(RECON,),
    )
    state = _turn_state(owner)
    trashing = ENGINE.apply(state, _play(card, 0)).state
    options = legal_intrigue_choice_actions(trashing, 0)
    assert [dict(a.arguments)["card_id"] for a in options] == [DAGGER]
    assert all(a.action_id == "trash_intrigue_card" for a in options)
    deployed = ENGINE.apply(state, _play(card, 1)).state
    counts = {
        dict(a.arguments)["count"] for a in legal_intrigue_choice_actions(deployed, 0)
    }
    assert counts == {1, 2}


def test_discerning_discards_to_draw_or_draws_with_an_alliance() -> None:
    card = _twisted("discerning")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(card,),
        hand=(DAGGER,),
        deck=(RECON,),
    )
    state = _turn_state(owner)
    assert [
        dict(a.arguments)["option"] for a in legal_intrigue_play_actions(state, 0)
    ] == [0]
    discarding = ENGINE.apply(state, _play(card, 0)).state
    done = ENGINE.apply(
        discarding,
        DomainAction(
            action_id="choose_intrigue_discard",
            actor=0,
            arguments=(("card_id", DAGGER),),
        ),
    ).state
    assert done.players[0].hand == (RECON,)
    allied = _turn_state(replace(owner, alliance_faction_ids=("fremen",)))
    assert [
        dict(a.arguments)["option"] for a in legal_intrigue_play_actions(allied, 0)
    ] == [
        0,
        1,
    ]
    drew = ENGINE.apply(allied, _play(card, 1)).state
    assert drew.players[0].hand == (DAGGER, RECON)


def test_insidious_gives_a_card_and_pays_extra_for_a_regular_one() -> None:
    card = _twisted("insidious")
    regular = intrigue_deck_instance_ids(False)[5]
    twisted_gift = _twisted("sadistic")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(card, regular, twisted_gift),
    )
    state = _turn_state(owner)
    giving = ENGINE.apply(state, _play(card)).state
    gifts = legal_intrigue_choice_actions(giving, 0)
    assert {dict(a.arguments)["card_id"] for a in gifts} == {regular, twisted_gift}
    assert {dict(a.arguments)["player"] for a in gifts} == {1, 2, 3}
    gave_regular = ENGINE.apply(
        giving,
        DomainAction(
            action_id="give_intrigue_card",
            actor=0,
            arguments=(("card_id", regular), ("player", 2)),
        ),
    ).state
    assert regular in gave_regular.players[2].intrigue_cards
    assert gave_regular.players[0].resources.spice == 2
    gave_twisted = ENGINE.apply(
        giving,
        DomainAction(
            action_id="give_intrigue_card",
            actor=0,
            arguments=(("card_id", twisted_gift), ("player", 1)),
        ),
    ).state
    assert gave_twisted.players[0].resources.spice == 1
    # With no other Intrigue card the gift cannot be paid.
    alone = _turn_state(replace(owner, intrigue_cards=(card,)))
    assert _play(card) not in legal_intrigue_play_actions(alone, 0)


def test_resourceful_grants_three_icons_to_the_card_played_this_turn() -> None:
    card = _twisted("resourceful")
    owner = PlayerState(
        player_id=0, leader_id="piter_de_vries", intrigue_cards=(card,), hand=(DAGGER,)
    )
    state = ENGINE.apply(_turn_state(owner), _play(card)).state
    assert state.players[0].granted_agent_icon_turn == "landsraad,city,spice_trade"
    spaces = {dict(a.arguments)["space_id"] for a in legal_agent_actions(state, 0)}
    assert {"arrakeen", "accept_contract", "assembly_hall"} <= spaces


def test_sadistic_shrewd_and_sinister_trade_troops_for_rewards() -> None:
    sadistic = _twisted("sadistic")
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        intrigue_cards=(sadistic,),
        deck=(RECON,),
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
        combat_strength=2,
    )
    losing = ENGINE.apply(_turn_state(owner), _play(sadistic)).state
    drew = ENGINE.apply(
        losing,
        DomainAction(
            action_id="lose_intrigue_troop", actor=0, arguments=(("zone", "garrison"),)
        ),
    ).state
    assert drew.players[0].troops_garrison == 2
    assert drew.players[0].hand == (RECON,)

    shrewd = _twisted("shrewd")
    sinister = _twisted("sinister")
    fighter = replace(owner, intrigue_cards=(shrewd, sinister), deck=())
    combat = _combat_state(fighter)
    shrewd_played = ENGINE.apply(combat, _play(shrewd)).state
    assert [
        tuple(a.arguments) for a in legal_intrigue_choice_actions(shrewd_played, 0)
    ] == [(("zone", "conflict"),)]
    spiced = ENGINE.apply(
        shrewd_played,
        DomainAction(
            action_id="lose_intrigue_troop", actor=0, arguments=(("zone", "conflict"),)
        ),
    ).state
    assert spiced.players[0].resources.spice == 1
    assert spiced.players[0].troops_conflict == 0
    assert spiced.players[0].combat_strength == 0

    sinister_played = ENGINE.apply(combat, _play(sinister)).state
    working = sinister_played
    for zone in ("garrison", "garrison"):
        working = ENGINE.apply(
            working,
            DomainAction(
                action_id="lose_intrigue_troop", actor=0, arguments=(("zone", zone),)
            ),
        ).state
    assert working.players[0].troops_garrison == 1
    assert working.players[0].resources.solari == 1
    assert len(working.players[0].intrigue_cards) == 1 + 1


def test_unnatural_trashes_an_intrigue_card_and_recruits_for_a_regular_one() -> None:
    card = _twisted("unnatural")
    regular = intrigue_deck_instance_ids(False)[5]
    owner = PlayerState(
        player_id=0, leader_id="piter_de_vries", intrigue_cards=(card, regular)
    )
    state = _turn_state(owner)
    trashing = ENGINE.apply(state, _play(card)).state
    options = legal_intrigue_choice_actions(trashing, 0)
    assert [dict(a.arguments)["card_id"] for a in options] == [regular]
    done = ENGINE.apply(trashing, options[0]).state
    seat = done.players[0]
    assert regular in done.intrigue_trash
    assert seat.troops_garrison == 3 + 1
    assert len(seat.intrigue_cards) == 1  # the drawn replacement


def test_withdrawn_passes_the_turn_and_only_at_its_start() -> None:
    card = _twisted("withdrawn")
    owner = PlayerState(
        player_id=0, leader_id="piter_de_vries", intrigue_cards=(card,), hand=(DAGGER,)
    )
    state = _turn_state(owner)
    assert _play(card) in legal_intrigue_play_actions(state, 0)
    passed = ENGINE.apply(state, _play(card)).state
    frame = passed.decision_stack[-1]
    assert frame.kind == "turn"
    assert dict(frame.context)["turn_owner"] == 1
    assert passed.players[0].has_revealed is False
    assert card in passed.intrigue_discard
    # After an Agent placement the turn has started: not playable.
    placed = _placed(state, DAGGER, "assembly_hall")
    assert _play(card) not in legal_intrigue_play_actions(placed, 0)
