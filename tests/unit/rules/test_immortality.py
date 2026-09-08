"""Tests for the Bene Tleilax board, specimens, and Family Atomics.

Rule source: ``docs/rules/immortality.md`` sections 2, 3, 6 and 7
[Immortality pp. 4-8, 12, 16] and the board artwork transcription in
``content/immortality/board.py``; open rulings OQ-048 to OQ-051.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.immortality.board import (
    RESEARCH_START_ID,
    TLEILAXU_TRACK_END,
)
from dune_imperium.content.immortality.tleilaxu import tleilaxu_deck_instance_ids
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    board_icons_for,
    legal_board_effect_actions,
    resolve_board_effect,
    static_board_effects,
)
from dune_imperium.rules.effects import DrawImperiumCardsEffect, ResearchEffect
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.immortality import (
    advance_research,
    advance_tleilaxu,
    apply_family_atomics,
    apply_research_advance,
    apply_research_bonus,
    apply_specimen_return,
    generate_specimens,
    legal_family_atomics_actions,
    legal_research_advance_actions,
    legal_research_bonus_actions,
    legal_specimen_return_actions,
)
from dune_imperium.rules.optional_trash import legal_optional_trash_actions
from dune_imperium.rules.reveal_turn import (
    apply_reveal_gain,
    begin_reveal_turn,
    legal_reveal_gain_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.simulation.sweep import run_checked_game

IMMORTALITY = RulesetConfig(immortality=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


def _owner(**overrides: object) -> PlayerState:
    deck = starting_deck_instance_ids(0, immortality=True)
    values: dict[str, object] = {
        "player_id": 0,
        "hand": deck[:5],
        "deck": deck[5:],
        "resources": Resources(solari=4, spice=2, water=2),
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _seat(seat: int) -> PlayerState:
    return PlayerState(
        player_id=seat, research_space=RESEARCH_START_ID, family_atomics=True
    )


def _turn_state(owner: PlayerState, **overrides: object) -> GameState:
    imperium = imperium_deck_instance_ids(False)
    values: dict[str, object] = {
        "config": IMMORTALITY,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False)[:6],
        "imperium_row": imperium[:5],
        "imperium_deck": imperium[5:20],
        "tleilaxu_track_spice": 2,
        "players": (owner, *(_seat(seat) for seat in range(1, 4))),
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


def _at(space_id: str, **overrides: object) -> GameState:
    return _turn_state(_owner(research_space=space_id, **overrides))


def _research_choices(state: GameState) -> dict[str, DomainAction]:
    return {
        str(dict(action.arguments)["space_id"]): action
        for action in legal_research_advance_actions(state, 0)
    }


# --- setup -------------------------------------------------------------------


def test_setup_places_tokens_spice_experimentation_and_family_atomics() -> None:
    state = create_initial_state(IMMORTALITY, 7, LEADERS).state

    assert state.tleilaxu_track_spice == 2
    # The Row shows two cards; the rest of the transcribed deck waits.
    assert len(state.tleilaxu_row) == 2
    assert len(state.tleilaxu_deck) == len(tleilaxu_deck_instance_ids()) - 2
    for player in state.players:
        assert player.research_space == RESEARCH_START_ID
        assert player.tleilaxu_space == 0
        assert player.specimens == 0
        assert player.family_atomics is True
        identities = [card.split(":")[3] for card in player.deck]
        assert identities.count("experimentation") == 2
        assert "dune_the_desert_planet" not in identities
        assert len(player.deck) == 10

    base = create_initial_state(RulesetConfig(), 7, LEADERS).state
    assert base.tleilaxu_track_spice == 0
    assert all(player.research_space == "" for player in base.players)
    assert all(
        "experimentation" not in card for player in base.players for card in player.deck
    )


def test_draft_setup_places_the_board_too() -> None:
    state = create_draft_initial_state(
        RulesetConfig(immortality=True, leader_draft=True), 3
    ).state
    assert state.tleilaxu_track_spice == 2
    assert all(player.family_atomics for player in state.players)


def test_board_state_requires_the_option() -> None:
    with pytest.raises(ValueError, match="Immortality"):
        GameState(
            config=RulesetConfig(),
            seed=1,
            players=(
                PlayerState(player_id=0, specimens=1, troops_supply=8),
                *(PlayerState(player_id=seat) for seat in range(1, 4)),
            ),
        )
    with pytest.raises(ValueError, match="all 12 troops"):
        PlayerState(player_id=0, specimens=1)


# --- research track ----------------------------------------------------------


def test_a_single_direction_moves_at_once_and_pays_the_specimen() -> None:
    state = _at(RESEARCH_START_ID)

    result = advance_research(state, 0, source="test")

    owner = result.state.players[0]
    assert owner.research_space == "c1r3"
    assert owner.specimens == 1 and owner.troops_supply == 8
    assert not result.state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    assert [event.kind for event in result.events] == [
        "research_advanced",
        "specimens_generated",
    ]


def test_two_directions_open_a_choice_frame() -> None:
    state = _at("c1r3")

    result = advance_research(state, 0, source="test")

    assert result.state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    assert set(_research_choices(result.state)) == {"c2r2", "c2r4"}
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c2r4"]
    )
    owner = chosen.state.players[0]
    assert owner.research_space == "c2r4"
    assert owner.tleilaxu_space == 1
    assert chosen.state.decision_stack[-1].kind == "turn"


def test_a_research_space_advances_again_and_reaches_the_first_marker() -> None:
    state = _at("c2r2")
    result = advance_research(state, 0, source="test")
    # Up-right to the research icon [Immortality p. 6]: it advances again,
    # and from c3r1 the only way is c4r2 (the first genetic marker column).
    chained = apply_research_advance(
        result.state, _research_choices(result.state)["c3r1"]
    )

    owner = chained.state.players[0]
    assert owner.research_space == "c4r2"
    assert owner.tleilaxu_space == 1
    assert "genetic_marker_reached" in {event.kind for event in chained.events}


def test_trash_and_specimen_pays_the_specimen_then_offers_the_trash() -> None:
    state = _at("c2r2")
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c3r3"]
    )

    assert chosen.state.players[0].specimens == 1
    assert chosen.state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    assert any(
        action.action_id == "decline_optional_trash"
        for action in legal_optional_trash_actions(chosen.state, 0)
    )


def test_influence_bonus_asks_for_a_faction() -> None:
    state = _at("c5r5")
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c6r6"]
    )

    assert chosen.state.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
    actions = {
        str(dict(action.arguments)["faction"]): action
        for action in legal_research_bonus_actions(chosen.state, 0)
    }
    assert set(actions) == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    gained = apply_research_bonus(chosen.state, actions["fremen"])
    assert gained.state.players[0].influence.fremen == 1
    assert gained.state.decision_stack[-1].kind == "turn"


def test_trash_for_card_and_intrigue_is_an_optional_arrow() -> None:
    state = _at("c6r2")
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c7r3"]
    )

    actions = legal_research_bonus_actions(chosen.state, 0)
    ids = {action.action_id for action in actions}
    assert ids == {"decline_research_bonus", "trash_for_research_bonus"}
    trash = next(
        action for action in actions if action.action_id == "trash_for_research_bonus"
    )
    owner_before = chosen.state.players[0]
    paid = apply_research_bonus(chosen.state, trash)
    owner = paid.state.players[0]
    assert len(owner.trashed) == 1
    assert len(owner.intrigue_cards) == 1
    # One card trashed from the hand, one drawn to replace it.
    assert len(owner.hand) + len(owner.deck) == (
        len(owner_before.hand) + len(owner_before.deck) - 1
    )
    declined = apply_research_bonus(
        chosen.state, DomainAction(action_id="decline_research_bonus", actor=0)
    )
    assert declined.state.players[0].trashed == ()


def test_seven_solari_bonus_needs_the_solari_and_advances_twice() -> None:
    poor = _at("c7r5", resources=Resources(solari=3))
    result = advance_research(poor, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c8r6"]
    )
    assert chosen.state.decision_stack[-1].kind == "turn"
    assert "research_bonus_unavailable" in {event.kind for event in chosen.events}

    rich = _at("c7r5", resources=Resources(solari=7))
    result = advance_research(rich, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c8r6"]
    )
    assert chosen.state.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
    paid = apply_research_bonus(
        chosen.state, DomainAction(action_id="pay_research_bonus", actor=0)
    )
    owner = paid.state.players[0]
    assert owner.resources.solari == 0
    assert owner.tleilaxu_space == 2
    assert len(owner.intrigue_cards) == 1  # the second space's Intrigue


def test_past_the_second_marker_research_draws_a_card() -> None:
    state = _at("c8r2")

    result = advance_research(state, 0, source="test")

    owner = result.state.players[0]
    assert owner.research_space == "c8r2"
    assert len(owner.hand) == 6
    assert result.events[0].kind == "research_drew_card"


# --- Tleilaxu track ----------------------------------------------------------


def test_tleilaxu_track_pays_intrigue_victory_points_and_the_first_spice() -> None:
    state = _at(RESEARCH_START_ID)

    first = advance_tleilaxu(state, 0, 4, source="test")
    owner = first.state.players[0]
    assert owner.tleilaxu_space == 4
    assert len(owner.intrigue_cards) == 1
    assert owner.victory_points == 2
    assert owner.resources.spice == 4
    assert first.state.tleilaxu_track_spice == 0

    # The second player to reach the space gains the point but no spice.
    second = advance_tleilaxu(first.state, 1, 4, source="test")
    other = second.state.players[1]
    assert other.victory_points == 2 and other.resources.spice == 0

    end = advance_tleilaxu(second.state, 0, 4, source="test")
    owner = end.state.players[0]
    assert owner.tleilaxu_space == TLEILAXU_TRACK_END
    assert owner.victory_points == 3
    assert len(owner.intrigue_cards) == 2
    # OQ-048: an advance on the last space does nothing.
    assert "tleilaxu_track_end" in {event.kind for event in end.events}


# --- specimens ---------------------------------------------------------------


def test_specimens_come_from_the_supply_and_the_shortfall_is_public() -> None:
    state = _at(RESEARCH_START_ID, troops_supply=1, troops_garrison=11)

    result = generate_specimens(state, 0, 2, source="test")

    owner = result.state.players[0]
    assert owner.specimens == 1 and owner.troops_supply == 0
    assert [event.kind for event in result.events] == [
        "specimens_generated",
        "specimens_short",
    ]


def test_a_specimen_can_be_returned_during_the_owners_turn() -> None:
    state = _at(RESEARCH_START_ID, specimens=2, troops_supply=7)

    actions = legal_specimen_return_actions(state, 0)
    assert [action.action_id for action in actions] == ["return_specimen"]
    assert legal_specimen_return_actions(state, 1) == ()
    returned = apply_specimen_return(state, actions[0])
    owner = returned.state.players[0]
    assert owner.specimens == 1 and owner.troops_supply == 8
    # Not during Combat.
    combat = replace(state, phase=GamePhase.COMBAT, decision_stack=())
    assert legal_specimen_return_actions(combat, 0) == ()


# --- Research Station and Experimentation ------------------------------------


def test_the_overlay_replaces_the_research_station_effects() -> None:
    assert static_board_effects("research_station", 0, choam_module=False) != (
        DrawImperiumCardsEffect(2),
        ResearchEffect(),
    )
    assert static_board_effects(
        "research_station", 0, choam_module=False, immortality=True
    ) == (DrawImperiumCardsEffect(2), ResearchEffect())
    state = _at(RESEARCH_START_ID)
    assert board_icons_for(state, 0, "research_station", 0) == ("cards", "research")


def test_visiting_the_research_station_draws_and_advances_research() -> None:
    deck = starting_deck_instance_ids(0, immortality=True)
    reconnaissance = next(card for card in deck if "reconnaissance" in card)
    owner = _owner(
        hand=(reconnaissance,), deck=tuple(c for c in deck if c != reconnaissance)
    )
    state = _turn_state(owner)
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "research_station"
    )
    state = apply_agent_action(state, placement).state
    research = next(
        action
        for action in legal_board_effect_actions(state, 0)
        if dict(action.arguments)["effect"] == "research"
    )

    result = resolve_board_effect(state, research)

    owner = result.state.players[0]
    assert owner.research_space == "c1r3"
    assert owner.specimens == 1


def test_experimentation_researches_on_the_agent_turn() -> None:
    deck = starting_deck_instance_ids(0, immortality=True)
    experimentation = next(card for card in deck if "experimentation" in card)
    owner = _owner(
        hand=(experimentation,), deck=tuple(c for c in deck if c != experimentation)
    )
    state = _turn_state(owner)
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "hagga_basin"
    )
    state = apply_agent_action(state, placement).state

    result = resolve_agent_card_effect(state)

    assert result.state.players[0].research_space == "c1r3"


def test_experimentation_reveal_specimen_is_the_owners_timing() -> None:
    deck = starting_deck_instance_ids(0, immortality=True)
    experimentation = tuple(card for card in deck if "experimentation" in card)
    owner = _owner(
        hand=experimentation, deck=tuple(c for c in deck if c not in experimentation)
    )
    state = _turn_state(owner)

    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    actions = legal_reveal_gain_actions(revealed.state, 0)
    assert [action.action_id for action in actions] == ["generate_reveal_specimens"]
    first = apply_reveal_gain(revealed.state, actions[0])
    assert first.state.players[0].specimens == 1
    second = apply_reveal_gain(first.state, actions[0])
    assert second.state.players[0].specimens == 2
    assert legal_reveal_gain_actions(second.state, 0) == ()
    assert dict(second.state.decision_stack[-1].context)["persuasion"] == 2


# --- Family Atomics ----------------------------------------------------------


def test_family_atomics_redeals_the_row_once_per_game() -> None:
    state = _at(RESEARCH_START_ID)
    old_row = state.imperium_row
    actions = legal_family_atomics_actions(state, 0)
    assert [action.action_id for action in actions] == ["use_family_atomics"]

    result = apply_family_atomics(state, actions[0])

    assert result.state.imperium_removed == old_row
    assert result.state.imperium_row == state.imperium_deck[:5]
    assert result.state.imperium_deck == state.imperium_deck[5:]
    assert result.state.players[0].family_atomics is False
    assert legal_family_atomics_actions(result.state, 0) == ()


# --- integration -------------------------------------------------------------


def test_the_codec_holds_the_immortality_choices_only_with_the_option() -> None:
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    immortality = {template.action_id for template in ActionCodec(IMMORTALITY).catalog}
    added = {
        "choose_research_space",
        "choose_research_influence",
        "trash_for_research_bonus",
        "pay_research_bonus",
        "decline_research_bonus",
        "return_specimen",
        "use_family_atomics",
        "generate_reveal_specimens",
    }
    assert added <= immortality
    assert not (added & base)


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_checked_games_finish_with_the_board_in_play(policy: str) -> None:
    report = run_checked_game(
        IMMORTALITY,
        11,
        900_011,
        policy=policy,
        soundness_interval=25,
        collect_coverage=True,
    )
    assert report.winner is not None
    assert report.coverage is not None
    events = report.coverage["event_kinds"]
    assert events.get("research_advanced", 0) > 0
    assert events.get("specimens_generated", 0) > 0


def test_the_engine_round_trips_an_immortality_game_through_the_codec() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(IMMORTALITY, seed=5)
    codec = ActionCodec(IMMORTALITY)
    for _ in range(40):
        frame = state.decision_stack[-1]
        if not isinstance(frame.decision, PlayerDecision):
            break
        actions = engine.legal_actions(state, frame.decision.owner)
        assert actions
        for action in actions:
            assert codec.decode(codec.encode(action), action.actor) == action
        state = engine.apply(state, actions[0]).state
