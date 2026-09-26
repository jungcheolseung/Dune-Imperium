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


def _with_spice(state: GameState, spice: int) -> GameState:
    owner = state.players[0]
    return replace(
        state,
        players=(
            replace(owner, resources=replace(owner.resources, spice=spice)),
            *state.players[1:],
        ),
    )


def _opponent_turn(state: GameState) -> GameState:
    return replace(
        state,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:1",
                decision=PlayerDecision(owner=1, prompt="Choose a turn"),
            ),
        ),
    )


def test_hungry_for_spice_counts_only_y_rkoons_own_turn() -> None:
    # "Whenever you gain [3 spice] or more in a single turn: [draw]"
    # [Steersman Y'rkoon card]. Round phases are Round Start, Player Turns,
    # Combat, Makers and Recall [Main p. 8]: Combat is nobody's turn, and an
    # opponent's turn is not Y'rkoon's.
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.leader_abilities import grant_hungry_for_spice

    owner = _steersman((), deck=(DAGGER, RECON), spice_at_turn_start=0)
    own_turn = _turn_state(owner)

    # Three spice from a Conflict reward during Combat: no draw.
    combat = replace(_with_spice(own_turn, 3), phase=GamePhase.COMBAT)
    combat = replace(combat, decision_stack=())
    fed = grant_hungry_for_spice(RuleResult(state=combat), combat).state
    assert fed.players[0].hand == ()

    # One spice in his Reveal turn, two more once Combat has begun (the last
    # Reveal and the Combat rewards in one transition): still no draw.
    reveal = _with_spice(own_turn, 1)
    fed = grant_hungry_for_spice(RuleResult(state=combat), reveal).state
    assert fed.players[0].hand == ()

    # Three spice during an opponent's turn: no draw.
    theirs = _opponent_turn(own_turn)
    fed = grant_hungry_for_spice(
        RuleResult(state=_with_spice(theirs, 3)), theirs
    ).state
    assert fed.players[0].hand == ()

    # Three spice gained by the step that closed his own turn still draws.
    closed = _with_spice(_opponent_turn(own_turn), 3)
    fed = grant_hungry_for_spice(RuleResult(state=closed), own_turn).state
    assert fed.players[0].hand == (DAGGER,)


def test_hungry_for_spice_judges_a_turn_that_reopens_into_his_own() -> None:
    # "Whenever you gain [3 spice] or more in a single turn: [draw]"
    # [Steersman Y'rkoon card]; OQ-063: "그 turn의 마지막 단계에서 얻은
    # spice는 turn을 닫는 전이에서도 판정한다". With every opponent revealed,
    # the step that closes his Agent turn opens his own next turn at once,
    # and the new turn's snapshot used to erase the closed turn's gain
    # before the hook judged it: no card, where unrevealed opponents gave one.
    ambassador = "imperium:ixian_ambassador:0"
    owner = _steersman(
        (),
        hand=(ambassador,),
        deck=(DAGGER, RECON),
        resources=Resources(spice=2),
        spice_at_turn_start=0,
        agents_available=2,
    )
    others = tuple(PlayerState(player_id=seat, has_revealed=True) for seat in (1, 2, 3))
    state = _turn_state(
        owner,
        players=(owner, *others),
        config=RulesetConfig(bloodlines=True, tech_module=True),
    )

    def act(current: GameState, action_id: str, **arguments: object) -> GameState:
        action = next(
            action
            for action in ENGINE.legal_actions(current, 0)
            if action.action_id == action_id
            and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
        )
        return ENGINE.apply(current, action).state

    state = act(state, "agent_turn", card_id=ambassador, space_id="assembly_hall")
    state = act(state, "resolve_board_effect")
    state = act(state, "decline_tech")
    # Ixian Ambassador's box, one spice [Ixian Ambassador card], is the
    # turn's last step: two before it, three with it.
    closed = act(state, "resolve_agent_card_effect")
    frame = closed.decision_stack[-1]
    assert frame.kind == "turn"
    assert isinstance(frame.decision, PlayerDecision) and frame.decision.owner == 0
    seat = closed.players[0]
    assert seat.resources.spice == 3
    assert seat.hand == (DAGGER,)
    assert seat.hungry_for_spice_owed is False
    # The new turn is judged on its own.
    assert seat.hungry_for_spice_granted_turn is False
    assert seat.spice_at_turn_start == 3


def test_hungry_for_spice_draws_after_a_reshuffle_left_by_the_closing_step() -> (
    None
):
    # OQ-063 judges the closing step's gain in the transition that closed
    # the turn. When that step also left a reshuffle pending, the draw waits
    # for it; before, the next transition started in the opponent's turn and
    # never judged Y'rkoon again, so the draw was lost.
    from dune_imperium.core import ChanceDecision
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.leader_abilities import grant_hungry_for_spice

    owner = _steersman((), deck=(DAGGER, RECON), spice_at_turn_start=0)
    own_turn = _turn_state(owner)
    reshuffle = DecisionFrame(
        kind="personal_draw_reshuffle",
        frame_id="test:reshuffle",
        decision=ChanceDecision(
            decision_id="test:reshuffle", prompt="Shuffle", options=(RECON,)
        ),
    )
    theirs = _with_spice(_opponent_turn(own_turn), 3)
    pending = replace(theirs, decision_stack=(*theirs.decision_stack, reshuffle))
    waited = grant_hungry_for_spice(RuleResult(state=pending), own_turn).state
    assert waited.players[0].hand == ()
    assert waited.players[0].hungry_for_spice_owed is True
    # The reshuffle resolved: the owed card is drawn once.
    resolved = replace(waited, decision_stack=theirs.decision_stack)
    fed = grant_hungry_for_spice(RuleResult(state=resolved), waited).state
    assert fed.players[0].hand == (DAGGER,)
    assert fed.players[0].hungry_for_spice_owed is False
    again = grant_hungry_for_spice(RuleResult(state=fed), fed).state
    assert again.players[0].hand == (DAGGER,)


def test_round_start_clears_the_hungry_for_spice_flag() -> None:
    from dune_imperium.rules.phases import begin_round

    owner = _steersman((), deck=(DAGGER, RECON), hungry_for_spice_granted_turn=True)
    state = replace(
        _turn_state(owner),
        phase=GamePhase.ROUND_START,
        decision_stack=(),
        conflict_deck=(CONFLICTS[1].card.card_id,),
        first_player=0,
    )
    started = begin_round(state).state
    assert started.players[0].hungry_for_spice_granted_turn is False


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


def test_card_ten_arrow_cost_may_be_declined_and_the_card_is_spent() -> None:
    # Card 10 prints "[lose 1 Influence] -> [gain 1 Influence]" with an
    # arrow; "You do not have to pay such a cost on a card." [Main p. 20]
    # (OQ-058). Plot Course still plays the card, so declining spends it
    # without effect (OQ-039 (b)). It used to force the loss.
    owner = _steersman(
        (_card(10), _card(5)), influence=Influence(fremen=1), victory_points=1
    )
    opened = _reach_two(_turn_state(owner), Faction.FREMEN)
    actions = legal_navigation_play_actions(opened, 0)
    decline = DomainAction(action_id="decline_navigation", actor=0)
    assert [a.action_id for a in actions] == ["play_navigation", "decline_navigation"]
    declined = apply_navigation_play(opened, decline)
    seat = declined.state.players[0]
    assert seat.influence.fremen == 2
    assert seat.victory_points == 1 + 1
    assert seat.navigation_played == (_card(10),)
    assert seat.navigation_slots == (_card(5),)
    assert seat.navigation_active_slot == 0
    assert declined.state.pending_navigation_plays == ()
    assert declined.state.decision_stack[-1].kind == "turn"
    assert dict(declined.events[0].payload)["declined"] == 1
    # A card with a cost-free option has no decline: its play is mandatory.
    free = _reach_two(
        _turn_state(_steersman((_card(9),), influence=Influence(fremen=1))),
        Faction.FREMEN,
    )
    assert "decline_navigation" not in {
        a.action_id for a in legal_navigation_play_actions(free, 0)
    }


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
