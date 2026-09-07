"""Tests for Steersman Y'rkoon and his Navigation cards (Bloodlines).

Rule sources: the Steersman Y'rkoon and Navigation card faces (transcribed
2026-09-07) and the rulebook clarification [Bloodlines p. 12]; project
conventions OQ-039 (trigger order, fizzling cards, slot bookkeeping).
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import (
    intrigue_deck_instance_ids,
    navigation_card_instance_ids,
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
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue import legal_intrigue_choice_actions
from dune_imperium.rules.navigation import (
    apply_navigation_play,
    apply_navigation_setup_action,
    begin_navigation_play,
    legal_navigation_play_actions,
    legal_navigation_setup_actions,
    navigation_play_is_queued,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.setup import create_initial_state

BLOODLINES = RulesetConfig(bloodlines=True)
ENGINE = UprisingRulesEngine()
NAV = navigation_card_instance_ids()
DAGGER = "player:0:starter:dagger:0"
RECON = "player:0:starter:reconnaissance:0"


def _card(number: int) -> str:
    return f"intrigue:navigation_card_{number}:0"


def _turn_state(owner: PlayerState, **overrides: object) -> GameState:
    values: dict[str, object] = {
        "config": BLOODLINES,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False)[:3],
        "reserve_stacks": (("prepare_the_way", 8), ("the_spice_must_flow", 10)),
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


def _steersman(slots: tuple[str, ...], **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "leader_id": "steersman_y_rkoon",
        "navigation_slots": slots,
        "resources": Resources(),
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _reach_two(state: GameState, faction: Faction) -> GameState:
    """Gain Influence to two and open the queued Navigation play."""

    gained = gain_faction_influence(state, 0, faction, 1, event_prefix="test")
    assert navigation_play_is_queued(gained.state)
    return begin_navigation_play(gained.state).state


def _play_option(state: GameState, option: int) -> GameState:
    actions = legal_navigation_play_actions(state, 0)
    chosen = next(a for a in actions if dict(a.arguments)["option"] == option)
    return apply_navigation_play(state, chosen).state


# --- setup ---------------------------------------------------------------------


def test_strange_form_and_the_navigation_setup_choice() -> None:
    setup = create_initial_state(
        BLOODLINES,
        seed=5,
        leader_ids=("steersman_y_rkoon", "gurney_halleck", "chani", "lady_jessica"),
    )
    state = setup.state
    seat = state.players[0]
    assert seat.resources.water == 0
    assert not any("signet_ring" in card for card in seat.deck)
    assert state.phase is GamePhase.SETUP
    assert state.decision_stack[-1].kind == "navigation_setup"
    assert len(seat.navigation_box) == 5
    hand = set(NAV) - set(seat.navigation_box)
    picks = legal_navigation_setup_actions(state, 0)
    assert {dict(a.arguments)["card_id"] for a in picks} == hand
    working = state
    for _ in range(4):
        options = legal_navigation_setup_actions(working, 0)
        working = apply_navigation_setup_action(working, options[0]).state
    seat = working.players[0]
    assert len(seat.navigation_slots) == 4
    assert len(seat.navigation_box) == 6
    assert working.phase is GamePhase.ROUND_START
    assert working.decision_stack == ()
    # Opponents see only the counts; the owner sees the slots.
    rival = observe_state(working, 1)
    assert rival.players[0].navigation_remaining == 4
    own = observe_state(working, 0).private
    assert own is not None and own.navigation_slots == seat.navigation_slots
    # The engine drives the same setup through its reset.
    engine = UprisingRulesEngine(
        leader_ids=("steersman_y_rkoon", "gurney_halleck", "chani", "lady_jessica")
    )
    started = engine.reset(BLOODLINES, seed=5)
    assert started.phase is GamePhase.SETUP
    assert {a.action_id for a in engine.legal_actions(started, 0)} == {
        "place_navigation_card"
    }


def test_hungry_for_spice_draws_once_per_turn() -> None:
    owner = _steersman((), deck=(DAGGER, RECON), spice_at_turn_start=0)
    state = _turn_state(owner)
    # A Plot that gains three spice: use the engine hook directly.
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.leader_abilities import grant_hungry_for_spice

    richer = replace(
        state,
        players=(
            replace(owner, resources=Resources(spice=3)),
            *state.players[1:],
        ),
    )
    fed = grant_hungry_for_spice(RuleResult(state=richer)).state
    assert fed.players[0].hand == (DAGGER,)
    assert fed.players[0].hungry_for_spice_granted_turn is True
    again = grant_hungry_for_spice(RuleResult(state=fed)).state
    assert again.players[0].hand == (DAGGER,)


# --- Navigation cards ----------------------------------------------------------


def test_reaching_two_influence_plays_the_next_slot_in_order() -> None:
    owner = _steersman((_card(6), _card(7)), influence=Influence(emperor=1))
    state = _turn_state(owner)
    opened = _reach_two(state, Faction.EMPEROR)
    frame = opened.decision_stack[-1]
    assert frame.kind == "navigation_choice"
    assert dict(frame.context)["card_id"] == _card(6)
    seat = opened.players[0]
    assert seat.navigation_active_slot == 1
    assert seat.navigation_trigger_faction == "emperor"
    options = legal_navigation_play_actions(opened, 0)
    # Card 6: one troop, or three Solari for three troops (unaffordable).
    assert [dict(a.arguments)["option"] for a in options] == [0]
    played = _play_option(opened, 0)
    seat = played.players[0]
    assert seat.troops_garrison == 3 + 1
    assert seat.navigation_slots == (_card(7),)
    assert seat.navigation_played == (_card(6),)
    assert seat.navigation_active_slot == 0
    assert played.decision_stack[-1].kind == "turn"


def test_card_one_gains_influence_with_a_different_faction_at_two() -> None:
    owner = _steersman(
        (_card(1),),
        influence=Influence(emperor=1, fremen=2),
        resources=Resources(solari=2),
    )
    opened = _reach_two(_turn_state(owner), Faction.EMPEROR)
    paid = _play_option(opened, 1)
    factions = legal_intrigue_choice_actions(paid, 0)
    assert [dict(a.arguments)["faction"] for a in factions] == ["fremen"]
    done = ENGINE.apply(paid, factions[0]).state
    assert done.players[0].influence.fremen == 3
    assert done.players[0].resources.solari == 0


def test_card_three_in_slot_four_adds_permanent_reveal_persuasion() -> None:
    slots = (_card(6), _card(7), _card(9), _card(3))
    owner = _steersman(slots, navigation_played=(), influence=Influence(fremen=1))
    played = replace(owner, navigation_slots=(_card(3),), navigation_played=slots[:3])
    opened = _reach_two(_turn_state(played), Faction.FREMEN)
    assert opened.players[0].navigation_active_slot == 4
    done = _play_option(opened, 0)
    seat = done.players[0]
    assert seat.resources.solari == 2
    assert seat.reveal_persuasion_bonus == 1
    revealed = begin_reveal_turn(
        replace(done, players=(replace(seat, hand=(DAGGER,)), *done.players[1:])),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == 1
    # In any other slot the card only pays the Solari.
    early = _reach_two(
        _turn_state(_steersman((_card(3),), influence=Influence(fremen=1))),
        Faction.FREMEN,
    )
    plain = _play_option(early, 0)
    assert plain.players[0].reveal_persuasion_bonus == 0


def test_card_four_in_slot_one_buys_the_spice_must_flow_for_water() -> None:
    owner = _steersman(
        (_card(4),), influence=Influence(emperor=1), resources=Resources(water=1)
    )
    opened = _reach_two(_turn_state(owner), Faction.EMPEROR)
    options = [
        dict(a.arguments)["option"] for a in legal_navigation_play_actions(opened, 0)
    ]
    assert options == [0, 1]
    bought = _play_option(opened, 1)
    seat = bought.players[0]
    assert seat.resources.water == 0
    assert any("the_spice_must_flow" in card for card in seat.discard_pile)
    # The seat's base point, Influence 2, and the acquisition.
    assert seat.victory_points == 1 + 1 + 1
    assert dict(bought.reserve_stacks)["the_spice_must_flow"] == 9


def test_card_eight_pays_spice_only_for_a_guild_trigger() -> None:
    owner = _steersman((_card(8),), influence=Influence(spacing_guild=1))
    guild = _play_option(_reach_two(_turn_state(owner), Faction.SPACING_GUILD), 0)
    assert guild.players[0].resources == Resources(spice=1, water=1 + 1)
    other = _steersman((_card(8),), influence=Influence(emperor=1))
    emperor = _play_option(_reach_two(_turn_state(other), Faction.EMPEROR), 0)
    assert emperor.players[0].resources == Resources(water=1 + 1)


def test_a_card_with_no_playable_option_is_spent_without_effect() -> None:
    # Card 10 loses one Influence: with the trigger Faction as the only
    # Influence, the loss is still possible; with none it cannot be.
    owner = _steersman((_card(10), _card(5)))
    lonely = replace(owner, influence=Influence())
    state = _turn_state(lonely)
    gained = gain_faction_influence(state, 0, Faction.FREMEN, 2, event_prefix="test")
    resolved = begin_navigation_play(gained.state)
    # Fremen 2 can be lost: the card resolves as a real play.
    assert resolved.state.decision_stack[-1].kind == "navigation_choice"
    played = _play_option(resolved.state, 0)
    lost = legal_intrigue_choice_actions(played, 0)
    assert [dict(a.arguments)["faction"] for a in lost] == ["fremen"]
    # A queued play with an empty slot list is dropped.
    empty = _steersman((), influence=Influence(emperor=1))
    gained_empty = gain_faction_influence(
        _turn_state(empty), 0, Faction.EMPEROR, 1, event_prefix="test"
    )
    dropped = begin_navigation_play(gained_empty.state)
    assert dropped.events[0].kind == "navigation_exhausted"


def test_card_five_pays_spice_for_trashing_a_costed_card() -> None:
    owner = _steersman(
        (_card(5),),
        influence=Influence(emperor=1),
        hand=(DAGGER, "imperium:guild_envoy:0"),
    )
    opened = _reach_two(_turn_state(owner), Faction.EMPEROR)
    trashing = _play_option(opened, 0)
    options = legal_intrigue_choice_actions(trashing, 0)
    guild = next(
        a
        for a in options
        if dict(a.arguments).get("card_id") == "imperium:guild_envoy:0"
    )
    paid = ENGINE.apply(trashing, guild).state
    assert paid.players[0].resources.spice == 2
    dagger = next(a for a in options if dict(a.arguments).get("card_id") == DAGGER)
    unpaid = ENGINE.apply(trashing, dagger).state
    assert unpaid.players[0].resources.spice == 0


def test_two_triggers_in_one_effect_open_one_play_at_a_time() -> None:
    # OQ-012 re-review / OQ-039: triggers queue in the order Influence
    # reached two and the engine opens them one by one; a second frame for
    # the same slot would play one card twice.
    owner = _steersman(
        (_card(6), _card(7)), influence=Influence(emperor=1, spacing_guild=1)
    )
    state = _turn_state(owner)
    first = gain_faction_influence(state, 0, Faction.EMPEROR, 1, event_prefix="a")
    second = gain_faction_influence(
        first.state, 0, Faction.SPACING_GUILD, 1, event_prefix="b"
    )
    assert len(second.state.pending_navigation_plays) == 2
    opened = begin_navigation_play(second.state).state
    assert dict(opened.decision_stack[-1].context)["card_id"] == _card(6)
    # The second trigger waits for the first card to finish.
    assert not navigation_play_is_queued(opened)
    played = _play_option(opened, 0)
    assert navigation_play_is_queued(played)
    reopened = begin_navigation_play(played).state
    assert dict(reopened.decision_stack[-1].context)["card_id"] == _card(7)
    finished = _play_option(reopened, 0)
    seat = finished.players[0]
    assert seat.navigation_played == (_card(6), _card(7))
    assert seat.navigation_slots == ()
    assert finished.pending_navigation_plays == ()
