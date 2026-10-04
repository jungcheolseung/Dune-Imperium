"""The Emperor track's Influence 4 Spy as a mandatory action of the turn.

"When you reach 4 Influence, you earn the bonus shown on that space of the
track" [Main p. 7]; the Emperor strip prints the Spy icon. User ruling
2026-10-04, overriding the adopted designer ruling OQ-057 (15) ("You need to
finish resolving that Spy placement before you move on to other 'player
initiated actions.'"): "엄연히 agent턴 내에 순서를 정해서 할 수 있는 의무
행동으로 보는거지". As in the Steam app, during the owner's own Agent or Reveal
turn the placement waits in the turn (``place_track_spy``), the owner may do
other things first, and the turn cannot end before it; anywhere else (another
seat's turn, Combat, the Endgame) it opens at once, as before. The placement
itself is the shared ``spy_placement`` frame: mandatory with a Spy in the
supply, with the recall-first or its decline without one [Main pp. 11, 20].
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    encode_player_view,
    segment_slice,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
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
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import observe_state
from dune_imperium.display.unavailable import unavailable_choices
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat_deployment import (
    FINISH_DEPLOYMENT_KEY,
    FINISH_RECRUITS_KEY,
    FINISHING_KEY,
    settle_finishing_agent_turn,
)
from dune_imperium.rules.effects import close_agent_turn, open_next_turn
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind, owes_track_spy, with_context
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.reveal_turn import finish_reveal_turn
from dune_imperium.server.turn_end import agent_turn_end_ready
from dune_imperium.simulation import InvariantViolation, check_track_spy_queue

ENGINE = UprisingRulesEngine()
STARTERS = starting_deck_instance_ids(0)
DIPLOMACY = next(card for card in STARTERS if ":diplomacy:" in card)
DAGGER = next(card for card in STARTERS if ":dagger:" in card)
CHANGE_ALLEGIANCES = "intrigue:change_allegiances:0"
IMPERIAL_PRIVILEGE_POST = "landsraad-high-council-imperial-privilege-swordmaster"
PLACE = DomainAction("place_track_spy", 0)


def _turn_state(
    owner: PlayerState,
    config: RulesetConfig | None = None,
    **fields: object,
) -> GameState:
    values: dict[str, object] = {
        "config": config or RulesetConfig(),
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
    values.update(fields)
    return GameState(**values)  # type: ignore[arg-type]


def _owed(state: GameState, *seats: int) -> GameState:
    """Queue one Emperor track Spy per seat, as an Influence gain would."""

    return replace(
        state,
        pending_track_spies=(
            *state.pending_track_spies,
            *(
                (seat, f"test:{seat}:{index}:track_bonus")
                for index, seat in enumerate(seats)
            ),
        ),
    )


def _ids(state: GameState, seat: int = 0) -> list[str]:
    return [action.action_id for action in ENGINE.legal_actions(state, seat)]


def _first(state: GameState, action_id: str, seat: int = 0) -> DomainAction:
    return next(
        action
        for action in ENGINE.legal_actions(state, seat)
        if action.action_id == action_id
    )


def _apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action).state


def _at_dutiful_service(emperor: int = 3) -> GameState:
    """Seat 0 sends Diplomacy to Dutiful Service from ``emperor`` Influence."""

    owner = PlayerState(
        player_id=0,
        hand=(DIPLOMACY,),
        deck=tuple(card for card in STARTERS if card != DIPLOMACY),
        influence=Influence(emperor=emperor),
    )
    state = _turn_state(owner)
    visit = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if dict(action.arguments).get("space_id") == "dutiful_service"
    )
    return _apply(state, visit)


def _reveal(owner: PlayerState | None = None) -> GameState:
    """Seat 0's Reveal turn with nothing to reveal."""

    state = _turn_state(owner or PlayerState(player_id=0))
    return _apply(state, DomainAction("reveal_turn", 0))


def _place_on(state: GameState, post_id: str, seat: int = 0) -> GameState:
    return _apply(
        state,
        DomainAction("place_spy_on_space", seat, (("post_id", post_id),)),
    )


# --- the Agent turn ---------------------------------------------------------------


def test_an_agent_turn_owes_the_spy_and_places_it_after_its_other_effects() -> None:
    start = _at_dutiful_service()
    reached = _apply(start, _first(start, "resolve_faction_influence"))
    assert reached.players[0].influence.emperor == 4
    assert owes_track_spy(reached, 0)
    assert reached.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    # Offered after the pending groups, never the turn end before it.
    assert _ids(reached) == ["resolve_board_effect", "place_track_spy"]

    effects_done = _apply(reached, _first(reached, "resolve_board_effect"))
    assert _ids(effects_done) == ["place_track_spy"]
    opened = _apply(effects_done, PLACE)
    assert opened.decision_stack[-1].kind == FrameKind.SPY_PLACEMENT
    assert not owes_track_spy(opened, 0)
    placed = _place_on(opened, IMPERIAL_PRIVILEGE_POST)
    assert placed.players[0].spy_post_ids == (IMPERIAL_PRIVILEGE_POST,)
    assert _ids(placed) == ["finish_agent_turn"]


def test_the_spy_may_also_come_first_in_the_agent_turn() -> None:
    start = _at_dutiful_service()
    reached = _apply(start, _first(start, "resolve_faction_influence"))
    placed = _place_on(_apply(reached, PLACE), IMPERIAL_PRIVILEGE_POST)
    assert placed.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _ids(placed) == ["resolve_board_effect"]


# --- the Reveal turn --------------------------------------------------------------


def test_a_reveal_turn_cannot_end_before_the_spy_is_placed() -> None:
    revealed = _reveal()
    assert _ids(revealed) == ["finish_reveal"]
    owing = _owed(revealed, 0)
    assert _ids(owing) == ["place_track_spy"]
    opened = _apply(owing, PLACE)
    assert opened.decision_stack[-1].kind == FrameKind.SPY_PLACEMENT
    placed = _place_on(opened, IMPERIAL_PRIVILEGE_POST)
    assert placed.decision_stack[-1].kind == FrameKind.REVEAL
    assert _ids(placed) == ["finish_reveal"]


# --- a Plot on the turn frame, and the designer's own example ------------------------


def _change_allegiances_to_four(owner: PlayerState) -> GameState:
    """From Emperor 2: both Change Allegiances lines reach 4 (OQ-057 (15))."""

    card = CHANGE_ALLEGIANCES
    state = _turn_state(owner)
    state = _apply(
        state, DomainAction("play_intrigue", 0, (("card_id", card), ("option", 0)))
    )
    for line, choices in ((0, ("fremen", "emperor")), (1, ("emperor",))):
        state = _apply(
            state, DomainAction("use_intrigue_effect", 0, (("section", line),))
        )
        for faction in choices:
            state = _apply(
                state,
                DomainAction("choose_intrigue_faction", 0, (("faction", faction),)),
            )
    return state


def test_the_designers_imperial_privilege_example_is_now_allowed() -> None:
    # The designer's question: "Can you delay the Spy bonus from the Emperor
    # track earlier, to put it back down on the Imperial Privilege
    # observation post? -- No." Under the user ruling it may wait: the Spy
    # on that post is recalled by Gather Intelligence at Imperial Privilege,
    # and the track's Spy is then placed on the emptied post.
    owner = PlayerState(
        player_id=0,
        hand=(DAGGER,),
        deck=tuple(card for card in STARTERS if card != DAGGER),
        intrigue_cards=(CHANGE_ALLEGIANCES,),
        influence=Influence(emperor=2, fremen=1),
        resources=Resources(spice=3, solari=3),
        spies_supply=2,
        spy_post_ids=(IMPERIAL_PRIVILEGE_POST,),
    )
    reached = _change_allegiances_to_four(owner)
    assert reached.players[0].influence.emperor == 4
    assert reached.decision_stack[-1].kind == FrameKind.TURN
    assert owes_track_spy(reached, 0)
    assert "place_track_spy" in _ids(reached)

    visit = next(
        action
        for action in ENGINE.legal_actions(reached, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "imperial_privilege"
    )
    sent = _apply(reached, visit)
    # Gather Intelligence comes first, alone (its early return stays ahead).
    assert set(_ids(sent)) == {"decline_gather_intelligence", "gather_intelligence"}
    recalled = _apply(sent, _first(sent, "gather_intelligence"))
    assert recalled.players[0].spy_post_ids == ()
    assert "place_track_spy" in _ids(recalled)
    assert "finish_agent_turn" not in _ids(recalled)

    opened = _apply(recalled, PLACE)
    posts = {
        dict(action.arguments)["post_id"] for action in ENGINE.legal_actions(opened, 0)
    }
    assert IMPERIAL_PRIVILEGE_POST in posts
    placed = _place_on(opened, IMPERIAL_PRIVILEGE_POST)
    assert placed.players[0].spy_post_ids == (IMPERIAL_PRIVILEGE_POST,)
    assert not owes_track_spy(placed, 0)


def test_two_reaches_owe_two_spies_and_take_two_presses() -> None:
    # Each reach of 4 earns the bonus [Main p. 7]: reaching it, dropping to
    # 3 and reaching it again in one turn owes two Spies.
    state = _turn_state(PlayerState(player_id=0, influence=Influence(emperor=3)))
    first = gain_faction_influence(state, 0, Faction.EMPEROR, 1, event_prefix="a")
    back = replace(first.state.players[0], influence=Influence(emperor=3))
    dropped = replace(first.state, players=(back, *first.state.players[1:]))
    second = gain_faction_influence(dropped, 0, Faction.EMPEROR, 1, event_prefix="b")
    state = _advance_automatic(second).state
    assert state.players[0].influence.emperor == 4
    assert [seat for seat, _ in state.pending_track_spies] == [0, 0]
    assert state.decision_stack[-1].kind == FrameKind.TURN
    assert observe_state(state, 1).players[0].track_spies_owed == 2

    # One press opens one placement; the second waits for its own press.
    assert _ids(state).count("place_track_spy") == 1
    once = _place_on(_apply(state, PLACE), IMPERIAL_PRIVILEGE_POST)
    assert len(once.pending_track_spies) == 1
    assert _ids(once).count("place_track_spy") == 1
    twice = _place_on(_apply(once, PLACE), "landsraad-assembly-hall-gather-support")
    assert twice.pending_track_spies == ()
    assert "place_track_spy" not in _ids(twice)
    assert twice.players[0].spies_supply == 1


# --- an empty supply ----------------------------------------------------------------


def test_with_an_empty_supply_the_press_offers_the_recall_first_or_its_decline() -> (
    None
):
    posts = (
        IMPERIAL_PRIVILEGE_POST,
        "landsraad-assembly-hall-gather-support",
        "arrakis-deep-desert",
    )
    owner = PlayerState(player_id=0, spies_supply=0, spy_post_ids=posts)
    owing = _owed(_turn_state(owner), 0)
    assert "place_track_spy" in _ids(owing)
    opened = _apply(owing, PLACE)
    actions = ENGINE.legal_actions(opened, 0)
    assert actions[0] == DomainAction("decline_spy_placement", 0)
    assert {dict(a.arguments)["post_id"] for a in actions[1:]} == set(posts)
    declined = _apply(opened, actions[0])
    assert declined.decision_stack[-1].kind == FrameKind.TURN
    assert not owes_track_spy(declined, 0)

    # No Spy anywhere (all boxed by the Tech Module's Advanced Data
    # Analysis): only the decline, but the press is still the owner's own
    # (nothing lapses unasked).
    boxed = PlayerState(player_id=0, spies_supply=0, spies_boxed=3)
    tech = RulesetConfig(bloodlines=True, tech_module=True)
    nothing = _apply(_owed(_turn_state(boxed, tech), 0), PLACE)
    assert ENGINE.legal_actions(nothing, 0) == (
        DomainAction("decline_spy_placement", 0),
    )


# --- entries that do not wait --------------------------------------------------------


def test_another_seats_spy_opens_at_once_even_behind_the_owners() -> None:
    start = _at_dutiful_service()
    reached = _apply(start, _first(start, "resolve_faction_influence"))
    # Seat 2 reached 4 during seat 0's turn, after seat 0 did.
    behind = _owed(reached, 2)
    advanced = _advance_automatic(RuleResult(state=behind)).state
    top = advanced.decision_stack[-1]
    assert top.kind == FrameKind.SPY_PLACEMENT
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 2
    # Seat 0's own entry still waits.
    assert [seat for seat, _ in advanced.pending_track_spies] == [0]
    check_track_spy_queue(advanced)

    answered = _place_on(advanced, "arrakis-deep-desert", seat=2)
    assert answered.players[2].spy_post_ids == ("arrakis-deep-desert",)
    assert answered.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert "place_track_spy" in _ids(answered)


@pytest.mark.parametrize(
    ("phase", "kind"),
    [
        (GamePhase.COMBAT, FrameKind.COMBAT_INTRIGUE),
        (GamePhase.ENDGAME, FrameKind.ENDGAME_INTRIGUE),
    ],
)
def test_outside_a_player_turn_the_spy_opens_at_once(
    phase: GamePhase, kind: FrameKind
) -> None:
    window = DecisionFrame(
        kind=kind,
        frame_id="test:window",
        decision=PlayerDecision(owner=1, prompt="Play an Intrigue card"),
    )
    state = _owed(
        _turn_state(PlayerState(player_id=0), phase=phase, decision_stack=(window,)),
        1,
    )
    advanced = _advance_automatic(RuleResult(state=state)).state
    top = advanced.decision_stack[-1]
    assert top.kind == FrameKind.SPY_PLACEMENT
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert advanced.pending_track_spies == ()


def test_friends_everywhere_emperor_pick_leaves_the_spy_owed_in_the_turn() -> None:
    # Arrakeen Scouts' Friends Everywhere (OQ-081 (a)): reaching Fremen 4 in
    # the seat's own turn and picking the Emperor bonus owes its Spy there.
    owner = PlayerState(player_id=0, influence=Influence(fremen=3))
    state = _turn_state(
        owner,
        RulesetConfig(arrakeen_scouts=True),
        scouts_round_modifier="any_faction_four_bonus",
    )
    gained = gain_faction_influence(state, 0, Faction.FREMEN, 1, event_prefix="t")
    opened = _advance_automatic(gained).state
    assert opened.decision_stack[-1].kind == FrameKind.SCOUTS_FOUR_BONUS
    emperor = next(
        action
        for action in ENGINE.legal_actions(opened, 0)
        if dict(action.arguments)["faction"] == "emperor"
    )
    chosen = _apply(opened, emperor)
    assert chosen.decision_stack[-1].kind == FrameKind.TURN
    assert [seat for seat, _ in chosen.pending_track_spies] == [0]
    assert "place_track_spy" in _ids(chosen)


# --- the turn cannot pass or close over it --------------------------------------------


def test_litany_against_fear_and_withdrawn_wait_for_the_spy() -> None:
    litany = "imperium:litany_against_fear:0"
    withdrawn = "intrigue:twisted_withdrawn:0"
    owner = PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        hand=(litany, DAGGER),
        intrigue_cards=(withdrawn,),
    )
    free = _turn_state(owner, RulesetConfig(bloodlines=True))
    assert {"play_turn_start_card", "play_intrigue"} <= set(_ids(free))

    owing = _owed(free, 0)
    legal = ENGINE.legal_actions(owing, 0)
    offered = {action.action_id for action in legal}
    assert "place_track_spy" in offered
    assert "play_turn_start_card" not in offered
    assert "play_intrigue" not in offered
    # The page greys Withdrawn out with the reason.
    greyed = unavailable_choices(owing, 0, legal)
    assert greyed is not None
    rows = greyed["rows"]
    assert isinstance(rows, list)
    (row,) = [row for row in rows if row["surface"] == "intrigue"]
    assert row["code"] == "track_spy"
    assert "{influence_emperor} 4" in str(row["reason_ko"])

    placed = _place_on(_apply(owing, PLACE), IMPERIAL_PRIVILEGE_POST)
    assert {"play_turn_start_card", "play_intrigue"} <= set(_ids(placed))


def test_the_turn_closing_paths_refuse_an_owed_spy() -> None:
    with pytest.raises(RuntimeError, match="owed"):
        open_next_turn(_owed(_turn_state(PlayerState(player_id=0)), 0), 0)

    start = _at_dutiful_service()
    reached = _apply(start, _first(start, "resolve_faction_influence"))
    with pytest.raises(RuntimeError, match="owed"):
        close_agent_turn(reached, 0)

    owing = _owed(_reveal(), 0)
    with pytest.raises(RuntimeError, match="owed"):
        finish_reveal_turn(owing, DomainAction("finish_reveal", 0))


def test_a_finishing_turn_that_owes_a_spy_reopens() -> None:
    # OQ-095 (5): what the turn end's Usurp trash produced is the turn's own;
    # an owed Spy reopens the turn like a Contract or a recruit would.
    start = _at_dutiful_service()
    reached = _apply(start, _first(start, "resolve_faction_influence"))
    done = _apply(reached, _first(reached, "resolve_board_effect"))
    done = _place_on(_apply(done, PLACE), IMPERIAL_PRIVILEGE_POST)
    assert _ids(done) == ["finish_agent_turn"]
    frame = done.decision_stack[-1]
    context = {
        **dict(frame.context),
        FINISHING_KEY: True,
        FINISH_DEPLOYMENT_KEY: False,
        FINISH_RECRUITS_KEY: 0,
    }
    finishing = replace(
        done,
        decision_stack=(*done.decision_stack[:-1], with_context(frame, context)),
    )
    owing = _owed(finishing, 0)

    settled = settle_finishing_agent_turn(RuleResult(state=owing))
    assert [event.kind for event in settled.events] == ["agent_turn_reopened"]
    assert settled.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _ids(settled.state) == ["place_track_spy"]

    # Without the Spy the same finishing turn closes.
    closed = settle_finishing_agent_turn(RuleResult(state=finishing)).state
    assert closed.decision_stack[-1].kind == FrameKind.TURN
    top = closed.decision_stack[-1].decision
    assert isinstance(top, PlayerDecision) and top.owner == 1


def test_the_server_reads_the_turn_end_as_not_ready_while_the_spy_is_owed() -> None:
    start = _at_dutiful_service()
    reached = _apply(start, _first(start, "resolve_faction_influence"))
    done = _apply(reached, _first(reached, "resolve_board_effect"))
    assert agent_turn_end_ready(done) is None
    placed = _place_on(_apply(done, PLACE), IMPERIAL_PRIVILEGE_POST)
    assert agent_turn_end_ready(placed) == 0


# --- observation, codec and the soak invariant ---------------------------------------


def test_the_owed_spies_are_public_per_seat() -> None:
    state = _owed(_turn_state(PlayerState(player_id=0)), 0, 0, 2)
    for observer in range(4):
        view = observe_state(state, observer)
        assert [seat.track_spies_owed for seat in view.players] == [2, 0, 1, 0]
    # Relative seats, the observer first (like the shortfall segment).
    columns = segment_slice("track_spies_owed")
    assert encode_player_view(observe_state(state, 0))[columns] == (2, 0, 1, 0)
    assert encode_player_view(observe_state(state, 1))[columns] == (0, 1, 0, 2)
    assert encode_player_view(
        observe_state(_turn_state(PlayerState(player_id=0)), 0)
    )[columns] == (0, 0, 0, 0)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"choam_module": True},
        {"promo_cards": True},
        {"bloodlines": True},
        {"bloodlines": True, "tech_module": True},
        {"immortality": True},
        {"arrakeen_scouts": True},
        {"leader_draft": True},
        {
            "choam_module": True,
            "promo_cards": True,
            "bloodlines": True,
            "tech_module": True,
            "immortality": True,
            "arrakeen_scouts": True,
        },
    ],
)
def test_place_track_spy_round_trips_in_every_catalog(options: dict[str, bool]) -> None:
    codec = ActionCodec(RulesetConfig(**options))
    for seat in range(4):
        action = DomainAction("place_track_spy", seat)
        assert codec.decode(codec.encode(action), actor=seat) == action


def test_the_soak_invariant_accepts_only_the_turn_owners_waiting_entries() -> None:
    state = _turn_state(PlayerState(player_id=0))
    check_track_spy_queue(_owed(state, 0, 0))
    with pytest.raises(InvariantViolation, match="outside their turn"):
        check_track_spy_queue(_owed(state, 0, 1))
    # A Conflict's own reward choices come first (track_spy_is_queued).
    reward = DecisionFrame(
        kind=FrameKind.COMBAT_REWARD_SPY,
        frame_id="test:reward",
        decision=PlayerDecision(owner=1, prompt="Place a Spy"),
    )
    combat = replace(state, phase=GamePhase.COMBAT, decision_stack=(reward,))
    check_track_spy_queue(_owed(combat, 1))
    with pytest.raises(InvariantViolation):
        check_track_spy_queue(
            _owed(replace(state, phase=GamePhase.COMBAT, decision_stack=()), 1)
        )
