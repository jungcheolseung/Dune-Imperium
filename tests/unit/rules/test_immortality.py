"""Tests for the Bene Tleilax board, specimens, and Family Atomics.

Rule source: ``docs/rules/immortality.md`` sections 2, 3, 6 and 7
[Immortality pp. 4-8, 12, 16] and the board artwork transcription in
``content/immortality/board.py``; open rulings OQ-048 to OQ-051.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.immortality.board import (
    RESEARCH_START_ID,
    TLEILAXU_TRACK_END,
    ResearchBonus,
)
from dune_imperium.content.immortality.tleilaxu import tleilaxu_deck_instance_ids
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.effect_dsl import DrawPersonalCards, Research
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules import turn_rows
from dune_imperium.rules.acquisition import (
    apply_imperium_acquisition,
    legal_imperium_acquisitions,
)
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    board_icons_for,
    legal_board_effect_actions,
    resolve_board_effect,
    static_board_effects,
)
from dune_imperium.rules.effect_steps import first_step, steps_for
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.immortality import (
    ResearchBonusBlock,
    advance_research,
    advance_tleilaxu,
    apply_family_atomics,
    apply_research_advance,
    apply_research_bonus,
    apply_research_icon,
    apply_specimen_return,
    generate_specimens,
    legal_family_atomics_actions,
    legal_research_advance_actions,
    legal_research_bonus_actions,
    legal_specimen_return_actions,
    pending_research_bonuses,
    pending_research_icons,
    research_bonus_block,
    window_icons,
)
from dune_imperium.rules.optional_trash import (
    apply_optional_trash,
    legal_optional_trash_actions,
)
from dune_imperium.rules.reveal_turn import (
    apply_reveal_gain,
    begin_reveal_turn,
    legal_reveal_gain_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.simulation.sweep import run_checked_game

IMMORTALITY = RulesetConfig(immortality=True)
# Seat 0's research track space c3r5 in round 1 (cleanup-2c-5).
TRACK_C3R5 = "round:1:player:0:research:c3r5"
GO_TO_11 = RulesetConfig(immortality=True, go_to_11=True)
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


def _icon(effect: str, space: str) -> DomainAction:
    """Seat 0's action resolving one research icon of the research space
    ``space`` that printed it (rule decision 5; one action per icon and space
    since stage B3e-1)."""

    return DomainAction(
        action_id="resolve_research_icon",
        actor=0,
        arguments=(("effect", effect), ("printed", space), ("source", "research")),
    )


def _owed_draw(state: GameState, action_id: str) -> DomainAction:
    """The row that takes seat 0's owed draw ``action_id`` of the research
    space c7r3 in ``state`` (the turn offers the draws by their effect rows,
    stage B3d-4, one action per entity that earned one, stage B3e-1)."""

    return first_step(
        state,
        DomainAction(
            action_id=action_id,
            actor=0,
            arguments=(("printed", "c7r3"), ("source", "research")),
        ),
    )


def _offered_icons(state: GameState) -> set[str]:
    """The icons seat 0 is offered a row for now, through the engine."""

    return {
        str(dict(action.arguments)["effect"])
        for action in UprisingRulesEngine().whole_actions(state, 0)
        if action.action_id == "resolve_research_icon"
    }


def _turn_end_offered(state: GameState) -> bool:
    return any(
        action.action_id == "finish_agent_turn"
        for action in UprisingRulesEngine().whole_actions(state, 0)
    )


def _agent_research(space_id: str, **overrides: object) -> GameState:
    """Seat 0's Agent turn at the Research Station with its draw spent and
    its Research icon resolved up to the fork: the token on ``space_id``
    waits for the next space to be chosen."""

    deck = starting_deck_instance_ids(0, immortality=True)
    reconnaissance = next(card for card in deck if "reconnaissance" in card)
    owner = _owner(
        hand=(reconnaissance,),
        deck=tuple(card for card in deck if card != reconnaissance),
        research_space=space_id,
        **overrides,
    )
    state = _turn_state(owner)
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "research_station"
    )
    state = apply_agent_action(state, placement).state
    for effect in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, effect).state
    assert state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    return state


def _out_of_turn(space_id: str, **overrides: object) -> GameState:
    """Seat 0 on ``space_id`` in Combat, which is no player's turn
    [Main p. 8]: a research space opens its window."""

    return replace(
        _at(space_id, **overrides), phase=GamePhase.COMBAT, decision_stack=()
    )


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


def test_go_to_11_starts_every_score_marker_on_zero() -> None:
    # "For a 4-player game, start at 0 and play to 10." [Immortality p. 12]
    # replaces the usual start on 1 [Main p. 5], on both setup paths.
    fixed = create_initial_state(GO_TO_11, 7, LEADERS)
    draft = create_draft_initial_state(replace(GO_TO_11, leader_draft=True), 3)
    for result in (fixed, draft):
        assert [player.victory_points for player in result.state.players] == [0] * 4

    plain = create_initial_state(IMMORTALITY, 7, LEADERS)
    assert [player.victory_points for player in plain.state.players] == [1] * 4
    # Nothing else moves: the same shuffles and the same chance record.
    assert fixed.chance_outcomes == plain.chance_outcomes
    assert (
        replace(
            fixed.state,
            config=IMMORTALITY,
            players=tuple(
                replace(player, victory_points=1) for player in fixed.state.players
            ),
        )
        == plain.state
    )


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


def test_trash_and_specimen_waits_on_the_turn_as_two_rows() -> None:
    # c3r3 prints a specimen and a black "[trash a card]" icon, optional
    # [FAQ p. 3]. The two icons are independent effects the owner resolves in
    # either order (user decision 2026-10-17, composed-effects plan 5, rule
    # decision 5; OQ-027 [Main p. 9]). In the owner's own turn the specimen
    # waits on the turn frame as a mandatory row and the trash as rows with no
    # refusal; the trash lapses unused at the turn-end press (user decision
    # 2026-10-17, cleanup-2b; OQ-095 (2)).
    state = _at("c2r2")
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c3r3"]
    )

    # The step that moved the token resolved neither icon.
    assert chosen.state.players[0].specimens == 0
    assert [event.kind for event in chosen.events] == ["research_advanced"]
    top = chosen.state.decision_stack[-1]
    assert top.kind == "turn"
    assert [(kind, value) for kind, _source, value in turn_rows.pending(top)] == [
        (turn_rows.RESEARCH_ICON, "specimen"),
        # The trash records the research space that printed it (B3c-2b).
        (turn_rows.OPTIONAL_TRASH, "research|c3r3"),
    ]
    assert pending_research_icons(chosen.state, 0) == ("specimen",)
    offered = legal_optional_trash_actions(chosen.state, 0)
    assert {a.action_id for a in offered} == {"trash_optional_card"}
    owner = chosen.state.players[0]
    assert {dict(a.arguments)["card_id"] for a in offered} == {
        *owner.hand,
        *owner.discard_pile,
    }
    # The specimen is mandatory, so it holds the end; taking it is its own
    # step and logs what the fixed-order step used to.
    assert turn_rows.holds_the_end(chosen.state, 0)
    taken = apply_whole(
        UprisingRulesEngine(), chosen.state, _icon("specimen", "c3r3")
    )
    assert taken.state.players[0].specimens == 1
    assert [(e.kind, dict(e.payload)) for e in taken.events] == [
        ("specimens_generated", {"count": 1, "player": 0})
    ]
    # The trash is optional: it holds no end, and the press lapses it with an
    # event.
    assert not turn_rows.holds_the_end(taken.state, 0)
    lapsed = turn_rows.lapse(taken.state, 0)
    assert [(e.kind, dict(e.payload)) for e in lapsed.events] == [
        ("optional_trash_lapsed", {"player": 0})
    ]
    assert turn_rows.pending(lapsed.state.decision_stack[-1]) == ()
    assert lapsed.state.players[0].trashed == ()


def _waits_on_the_turn(state: GameState, bonus: ResearchBonus) -> None:
    """Cleanup-2b (user decision 2026-10-17, OQ-095 (2)): inside the owner's
    own turn the bonus opens no window; it waits on the turn frame as rows
    with no refusal."""

    assert state.decision_stack[-1].kind == "turn"
    assert [waiting for waiting, _source in pending_research_bonuses(state, 0)] == [
        bonus
    ]
    legal = {a.action_id for a in UprisingRulesEngine().whole_actions(state, 0)}
    assert "decline_research_bonus" not in legal


def _lapses_unused(state: GameState, bonus: ResearchBonus) -> GameState:
    """Offering nothing now, the bonus waits and lapses at the turn end."""

    assert legal_research_bonus_actions(state, 0) == ()
    assert not turn_rows.holds_the_end(state, 0)
    lapsed = turn_rows.lapse(state, 0)
    assert [(e.kind, dict(e.payload)) for e in lapsed.events] == [
        ("research_bonus_lapsed", {"bonus": bonus.value, "player": 0})
    ]
    assert pending_research_bonuses(lapsed.state, 0) == ()
    return lapsed.state


def test_influence_bonus_asks_for_a_faction() -> None:
    state = _at("c5r5")
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c6r6"]
    )

    _waits_on_the_turn(chosen.state, ResearchBonus.INFLUENCE_ANY)
    # Mandatory: it holds the turn's end while a Faction can rise.
    assert turn_rows.holds_the_end(chosen.state, 0)
    actions = {
        str(dict(action.arguments)["faction"]): action
        for action in legal_research_bonus_actions(chosen.state, 0)
    }
    assert set(actions) == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    gained = apply_research_bonus(chosen.state, actions["fremen"])
    assert gained.state.players[0].influence.fremen == 1
    assert gained.state.decision_stack[-1].kind == "turn"
    assert pending_research_bonuses(gained.state, 0) == ()
    assert not turn_rows.holds_the_end(gained.state, 0)


def test_a_research_bonus_outside_the_owner_s_turn_still_opens_its_window() -> None:
    # Combat is no player's turn [Main p. 8]: the window opens as before,
    # with its decline (user ruling 2026-09-30).
    state = replace(_at("c5r5"), phase=GamePhase.COMBAT, decision_stack=())
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c6r6"]
    )
    assert chosen.state.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
    assert len(legal_research_bonus_actions(chosen.state, 0)) == 4


def test_influence_bonus_never_offers_a_faction_at_the_top() -> None:
    # "합법 행동 provider는 이미 6인 진영을 제시하지 않으므로" (OQ-060, user
    # ruling 2026-09-16); with a Faction left the gain is mandatory and no
    # decline is offered: "진영을 하나라도 고를 수 있으면 확인은 제시하지
    # 않는다(획득은 의무다)" (OQ-060, 2026-09-30 addition).
    state = _at("c5r5", influence=Influence(emperor=6, bene_gesserit=6, fremen=3))
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c6r6"]
    )
    assert [
        (action.action_id, dict(action.arguments))
        for action in legal_research_bonus_actions(chosen.state, 0)
    ] == [
        ("choose_research_influence", {"faction": "spacing_guild"}),
        ("choose_research_influence", {"faction": "fremen"}),
    ]


def test_influence_bonus_with_every_faction_at_the_top_waits_and_lapses() -> None:
    # c6r6 with every cube at 6 waits, like an Agent box's Influence, and
    # lapses at the turn end (cleanup-2b, OQ-057 (1)); it does not hold the
    # end.
    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _at("c5r5", influence=full)
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c6r6"]
    )
    _waits_on_the_turn(chosen.state, ResearchBonus.INFLUENCE_ANY)
    owner_before = chosen.state.players[0]
    lapsed = _lapses_unused(chosen.state, ResearchBonus.INFLUENCE_ANY)
    assert lapsed.players[0] == owner_before
    assert lapsed.players[0].influence == full


def test_trash_intrigue_for_card_and_intrigue_is_an_optional_arrow() -> None:
    # c7r3 prints "[Trash an Intrigue card] -> [card] [Intrigue card]": the
    # gold Intrigue card under an X, "Trash an Intrigue card" [Immortality
    # p. 16] -- one from the owner's hand, never a personal card (the grey
    # trash icon it was first transcribed as). Intrigue cards have no trash
    # pile: the trashed card joins the shared Intrigue discard (OQ-061, user
    # ruling 2026-10-04).
    held = "intrigue:ambush:1"
    state = _at("c6r2", intrigue_cards=(held,))
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c7r3"]
    )

    _waits_on_the_turn(
        chosen.state, ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
    )
    # Optional: it holds no end.
    assert not turn_rows.holds_the_end(chosen.state, 0)
    actions = legal_research_bonus_actions(chosen.state, 0)
    assert [(a.action_id, dict(a.arguments)) for a in actions] == [
        ("trash_intrigue_for_research_bonus", {"card_id": held}),
    ]
    owner_before = chosen.state.players[0]
    paid = apply_research_bonus(chosen.state, actions[0])
    owner = paid.state.players[0]
    assert owner.trashed == ()
    assert paid.state.intrigue_discard == (*chosen.state.intrigue_discard, held)
    assert held not in owner.intrigue_cards
    # Paying the arrow's cost is its own step. The card and the Intrigue card
    # are two independent icons the owner draws in either order (user decision
    # 2026-10-17, composed-effects plan 5, rule decision 5; OQ-027 [Main
    # p. 9]), so they wait as two owed draws and nothing is drawn yet.
    assert [event.kind for event in paid.events] == ["intrigue_card_trashed"]
    assert [(deck, origin) for deck, origin, _source in owner.owed_draws] == [
        ("intrigue", "research_c7r3"),
        ("card", "research_c7r3"),
    ]
    assert owner.intrigue_cards == () and owner.hand == owner_before.hand
    engine = UprisingRulesEngine()
    after_intrigue = engine.apply(
        paid.state, _owed_draw(paid.state, "draw_owed_intrigue")
    ).state
    drawn = engine.apply(
        after_intrigue, _owed_draw(after_intrigue, "draw_owed_card")
    ).state.players[0]
    # No personal card left the hand; one was drawn, and one Intrigue card.
    assert len(drawn.hand) == len(owner_before.hand) + 1
    assert len(drawn.intrigue_cards) == 1 and held not in drawn.intrigue_cards
    lapsed = turn_rows.lapse(chosen.state, 0)
    assert [e.kind for e in lapsed.events] == ["research_bonus_lapsed"]
    assert lapsed.state.players[0].intrigue_cards == (held,)
    assert held not in lapsed.state.intrigue_discard


def test_trash_intrigue_bonus_without_an_intrigue_card_waits_and_lapses() -> None:
    # The arrow's cost cannot be paid with an empty Intrigue hand, however
    # many personal cards the owner holds: the bonus waits on the turn,
    # offering nothing, and lapses at its end (cleanup-2b; a window with only
    # the decline, user ruling 2026-09-30, until codec v149).
    state = _at("c6r2")
    assert state.players[0].intrigue_cards == ()
    result = advance_research(state, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c7r3"]
    )

    block = research_bonus_block(
        chosen.state.players[0], ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
    )
    assert block is ResearchBonusBlock.NO_INTRIGUE
    owner_before = chosen.state.players[0]
    _waits_on_the_turn(
        chosen.state, ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
    )
    lapsed = _lapses_unused(
        chosen.state, ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
    )
    assert lapsed.decision_stack[-1].kind == "turn"
    assert lapsed.players[0] == owner_before


# --- paired research icons are independent effects ---------------------------
#
# User decision 2026-10-17, composed-effects plan 5, rule decision 5; OQ-027
# [Main p. 9]: "한 공간에 인쇄된 아이콘은 각각 독립된 효과이며, 소유자는 각
# 아이콘을 별개 행동으로 원하는 순서에 해결한다" ("그래도 순서를 고르게 하자.
# 원칙대로").


@pytest.mark.parametrize("order", [("specimen", "tleilaxu"), ("tleilaxu", "specimen")])
def test_specimen_and_tleilaxu_are_two_rows_taken_in_either_order(
    order: tuple[str, str],
) -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. c3r5 prints a specimen and a Tleilaxu advance: in the
    # owner's Agent turn each waits as a mandatory row, the step that moved
    # the token resolves neither, and the turn's end waits for both.
    engine = UprisingRulesEngine()
    fork = _agent_research("c2r4")
    entered = apply_research_advance(fork, _research_choices(fork)["c3r5"])
    state = entered.state
    owner = state.players[0]
    assert owner.research_space == "c3r5"
    assert (owner.specimens, owner.tleilaxu_space) == (0, 0)
    assert [event.kind for event in entered.events] == ["research_advanced"]
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    waiting = turn_rows.pending(frame)
    assert [(kind, value) for kind, _source, value in waiting] == [
        (turn_rows.RESEARCH_ICON, "specimen"),
        (turn_rows.RESEARCH_ICON, "tleilaxu"),
    ]
    source = waiting[0][1]
    assert pending_research_icons(state, 0) == ("specimen", "tleilaxu")
    assert _offered_icons(state) == {"specimen", "tleilaxu"}
    assert turn_rows.holds_the_end(state, 0) and not _turn_end_offered(state)

    events: list[GameEvent] = []
    for position, icon in enumerate(order):
        taken = apply_whole(engine, state, _icon(icon, "c3r5"))
        state = taken.state
        events.extend(taken.events)
        remaining = set(order[position + 1 :])
        # The taken icon is gone; the other one still holds the end.
        assert _offered_icons(state) == remaining
        assert turn_rows.holds_the_end(state, 0) == bool(remaining)
        assert _turn_end_offered(state) == (not remaining)

    owner = state.players[0]
    assert (owner.specimens, owner.tleilaxu_space) == (1, 1)
    # Each logs what the fixed-order step logged; the row keeps the name of
    # what moved the token, what the space gives the seat's track space's.
    assert source.endswith(":research:c3r5") and source != TRACK_C3R5
    assert sorted((e.kind, e.event_id, dict(e.payload)) for e in events) == [
        (
            "specimens_generated",
            f"{TRACK_C3R5}:specimens",
            {"count": 1, "player": 0},
        ),
        (
            # The Tleilaxu track names its own events (cleanup-2c-5).
            "tleilaxu_advanced",
            "round:1:player:0:tleilaxu:1",
            {"player": 0, "space": 1},
        ),
    ]


def test_specimen_and_trash_let_the_trash_come_first() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. c3r3 in the Agent turn: the specimen row and the
    # optional trash rows are both offered, the trash may be taken first, and
    # the specimen alone holds the turn's end.
    engine = UprisingRulesEngine()
    fork = _agent_research("c2r4")
    state = apply_research_advance(fork, _research_choices(fork)["c3r3"]).state
    waiting = turn_rows.pending(state.decision_stack[-1])
    assert [(kind, value) for kind, _source, value in waiting] == [
        (turn_rows.RESEARCH_ICON, "specimen"),
        # The trash records the research space that printed it (B3c-2b).
        (turn_rows.OPTIONAL_TRASH, "research|c3r3"),
    ]
    offered = {a.action_id for a in engine.whole_actions(state, 0)}
    assert {"resolve_research_icon", "trash_optional_card"} <= offered
    assert "decline_optional_trash" not in offered
    assert not _turn_end_offered(state)

    card = legal_optional_trash_actions(state, 0)[0]
    trashed = apply_whole(engine, state, card).state
    owner = trashed.players[0]
    assert owner.specimens == 0 and len(owner.trashed) == 1
    # The trash was taken before the specimen; the specimen still holds the end
    # and is still offered, the trash rows are gone.
    assert [kind for kind, _s, _v in turn_rows.pending(trashed.decision_stack[-1])] == [
        turn_rows.RESEARCH_ICON
    ]
    assert _offered_icons(trashed) == {"specimen"}
    assert not any(
        a.action_id == "trash_optional_card" for a in engine.whole_actions(trashed, 0)
    )
    assert turn_rows.holds_the_end(trashed, 0) and not _turn_end_offered(trashed)

    done = apply_whole(engine, trashed, _icon("specimen", "c3r3")).state
    assert done.players[0].specimens == 1
    assert _turn_end_offered(done)


def test_an_unused_trash_lapses_at_the_press_after_the_specimen() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. The pair's black trash icon is optional [FAQ p. 3]:
    # once the specimen is taken the turn may end, and the press lapses the
    # unused trash with an event, trashing nothing.
    engine = UprisingRulesEngine()
    fork = _agent_research("c2r4")
    state = apply_research_advance(fork, _research_choices(fork)["c3r3"]).state

    taken = apply_whole(engine, state, _icon("specimen", "c3r3")).state
    assert _turn_end_offered(taken)
    assert [kind for kind, _s, _v in turn_rows.pending(taken.decision_stack[-1])] == [
        turn_rows.OPTIONAL_TRASH
    ]
    pressed = engine.apply(taken, DomainAction(action_id="finish_agent_turn", actor=0))
    assert [
        (e.kind, dict(e.payload))
        for e in pressed.events
        if e.kind == "optional_trash_lapsed"
    ] == [("optional_trash_lapsed", {"player": 0})]
    owner = pressed.state.players[0]
    assert owner.trashed == () and owner.specimens == 1


@pytest.mark.parametrize(
    "order",
    [
        ("draw_owed_card", "draw_owed_intrigue"),
        ("draw_owed_intrigue", "draw_owed_card"),
    ],
)
def test_c7r3_holds_its_card_and_intrigue_draws_in_either_order(
    order: tuple[str, str],
) -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. c7r3's "[Trash an Intrigue card] -> [card]
    # [Intrigue card]" [Immortality p. 16]: in the Agent turn, paying the cost
    # holds the two rewards as owed draws of the research space, taken in the
    # owner's order; the turn's end waits for both.
    engine = UprisingRulesEngine()
    held = "intrigue:ambush:1"
    fork = _agent_research("c6r2", intrigue_cards=(held,))
    state = apply_research_advance(fork, _research_choices(fork)["c7r3"]).state
    pay = next(
        action
        for action in legal_research_bonus_actions(state, 0)
        if action.action_id == "trash_intrigue_for_research_bonus"
    )
    before = state.players[0]

    paid = apply_whole(engine, state, pay)
    state = paid.state
    owner = state.players[0]
    # The pick step's seat-only ``effect_picked`` (stage B3c-2a) left out.
    assert [
        event.kind for event in paid.events if event.kind != "effect_picked"
    ] == ["intrigue_card_trashed"]
    assert turn_rows.pending(state.decision_stack[-1]) == ()
    assert [(deck, origin) for deck, origin, _s in owner.owed_draws] == [
        ("intrigue", "research_c7r3"),
        ("card", "research_c7r3"),
    ]
    assert owner.intrigue_cards == () and owner.hand == before.hand
    # One action per deck and the entity that earned the draw (stage B3e-1).
    c7r3 = (("printed", "c7r3"), ("source", "research"))
    assert set(engine.whole_actions(state, 0)) >= {
        DomainAction("draw_owed_intrigue", 0, c7r3),
        DomainAction("draw_owed_card", 0, c7r3),
    }
    assert not _turn_end_offered(state)

    for position, action_id in enumerate(order):
        state = engine.apply(state, _owed_draw(state, action_id)).state
        # The other draw still waits and holds the end; the taken one is gone.
        assert len(state.players[0].owed_draws) == 1 - position
        assert _turn_end_offered(state) == (position == 1)
    owner = state.players[0]
    assert len(owner.hand) == len(before.hand) + 1
    assert len(owner.intrigue_cards) == 1 and held not in owner.intrigue_cards


@pytest.mark.parametrize("order", [("specimen", "tleilaxu"), ("tleilaxu", "specimen")])
def test_a_pair_outside_the_turn_opens_a_window_ordering_its_icons(
    order: tuple[str, str],
) -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. Combat is no player's turn [Main p. 8]: the pair
    # (c3r5: specimen and Tleilaxu) opens one window with a row per icon and
    # no decline; each row is taken once, in the owner's order, and the frame
    # pops after the last.
    fork = _out_of_turn("c2r4")
    advanced = advance_research(fork, 0, source="test").state
    state = apply_research_advance(advanced, _research_choices(advanced)["c3r5"]).state
    window = state.decision_stack[-1]
    assert window.kind == FrameKind.RESEARCH_BONUS
    assert window_icons(window) == ("specimen", "tleilaxu")
    assert state.players[0].specimens == 0 and state.players[0].tleilaxu_space == 0
    # One action per icon, naming the research space that printed it (stage
    # B3e-1).
    assert set(UprisingRulesEngine().whole_actions(state, 0)) == {
        _icon("specimen", "c3r5"),
        _icon("tleilaxu", "c3r5"),
    }

    first = apply_research_icon(state, _icon(order[0], "c3r5"))
    assert first.state.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
    assert window_icons(first.state.decision_stack[-1]) == (order[1],)
    assert [a.action_id for a in legal_research_bonus_actions(first.state, 0)] == [
        "resolve_research_icon"
    ]
    second = apply_research_icon(first.state, _icon(order[1], "c3r5"))
    assert second.state.decision_stack == ()
    owner = second.state.players[0]
    assert (owner.specimens, owner.tleilaxu_space) == (1, 1)
    assert {e.kind for e in (*first.events, *second.events)} == {
        "specimens_generated",
        "tleilaxu_advanced",
    }


def test_the_trash_icon_outside_the_turn_opens_its_own_window_over_the_rest() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. c3r3 outside the turn: taking the trash icon first
    # pushes the usual optional-trash window (with its decline) over the window
    # still ordering the specimen; declining returns to it, and the frame pops
    # after the last icon.
    fork = _out_of_turn("c2r4")
    advanced = advance_research(fork, 0, source="test").state
    state = apply_research_advance(advanced, _research_choices(advanced)["c3r3"]).state
    assert window_icons(state.decision_stack[-1]) == ("specimen", "trash")

    trash = apply_research_icon(state, _icon("trash", "c3r3"))
    assert [frame.kind for frame in trash.state.decision_stack] == [
        FrameKind.RESEARCH_BONUS,
        FrameKind.OPTIONAL_TRASH,
    ]
    assert window_icons(trash.state.decision_stack[0]) == ("specimen",)
    offered = {a.action_id for a in legal_optional_trash_actions(trash.state, 0)}
    assert offered == {"decline_optional_trash", "trash_optional_card"}
    declined = apply_optional_trash(
        trash.state, DomainAction(action_id="decline_optional_trash", actor=0)
    )
    assert [frame.kind for frame in declined.state.decision_stack] == [
        FrameKind.RESEARCH_BONUS
    ]
    assert [a.action_id for a in legal_research_bonus_actions(declined.state, 0)] == [
        "resolve_research_icon"
    ]
    done = apply_research_icon(declined.state, _icon("specimen", "c3r3"))
    assert done.state.decision_stack == ()
    assert done.state.players[0].specimens == 1


def test_the_trash_icon_last_outside_the_turn_leaves_only_its_own_window() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. Taking the specimen first leaves the window with the
    # trash alone; taking it pops the window and opens only the optional-trash
    # window, whose card is trashed.
    fork = _out_of_turn("c2r4")
    advanced = advance_research(fork, 0, source="test").state
    state = apply_research_advance(advanced, _research_choices(advanced)["c3r3"]).state

    specimen = apply_research_icon(state, _icon("specimen", "c3r3"))
    assert specimen.state.players[0].specimens == 1
    assert window_icons(specimen.state.decision_stack[-1]) == ("trash",)
    trash = apply_research_icon(specimen.state, _icon("trash", "c3r3"))
    assert [frame.kind for frame in trash.state.decision_stack] == [
        FrameKind.OPTIONAL_TRASH
    ]
    card = legal_optional_trash_actions(trash.state, 0)[-1]
    trashed = apply_optional_trash(trash.state, card)
    assert trashed.state.decision_stack == ()
    assert trashed.state.players[0].trashed == (dict(card.arguments)["card_id"],)


def test_c7r3_paid_in_its_window_opens_a_window_for_its_two_rewards() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]. c7r3 outside the turn: the arrow's window offers the
    # trash (and its decline); paying it pushes a window with the Intrigue card
    # and the card as two rows (no decline), each drawing one card under its
    # own source, in either order.
    held = "intrigue:ambush:1"
    fork = _out_of_turn("c6r2", intrigue_cards=(held,))
    advanced = advance_research(fork, 0, source="test").state
    state = apply_research_advance(advanced, _research_choices(advanced)["c7r3"]).state
    assert state.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
    assert window_icons(state.decision_stack[-1]) == ()
    before = state.players[0]
    pay = next(
        action
        for action in legal_research_bonus_actions(state, 0)
        if action.action_id == "trash_intrigue_for_research_bonus"
    )

    paid = apply_research_bonus(state, pay)
    assert [event.kind for event in paid.events] == ["intrigue_card_trashed"]
    window = paid.state.decision_stack[-1]
    assert [frame.kind for frame in paid.state.decision_stack] == [
        FrameKind.RESEARCH_BONUS
    ]
    assert window_icons(window) == ("intrigue", "cards")
    assert paid.state.players[0].owed_draws == ()
    assert paid.state.players[0].hand == before.hand
    assert list(legal_research_bonus_actions(paid.state, 0)) == [
        _icon("intrigue", "c7r3"),
        _icon("cards", "c7r3"),
    ]

    # Cards first, then the Intrigue card.
    cards = apply_research_icon(paid.state, _icon("cards", "c7r3"))
    assert window_icons(cards.state.decision_stack[-1]) == ("intrigue",)
    assert len(cards.state.players[0].hand) == len(before.hand) + 1
    assert cards.state.players[0].intrigue_cards == ()
    intrigue = apply_research_icon(cards.state, _icon("intrigue", "c7r3"))
    assert intrigue.state.decision_stack == ()
    assert len(intrigue.state.players[0].intrigue_cards) == 1
    # The window keeps the opener's name, the draw the track space's.
    assert dict(window.context)["source"] != "round:1:player:0:research:c7r3"
    (drawn,) = intrigue.events
    assert drawn.kind == "intrigue_card_drawn"
    assert drawn.event_id.startswith("round:1:player:0:research:c7r3:intrigue_draw:")

    # Intrigue card first, then the card.
    first = apply_research_icon(paid.state, _icon("intrigue", "c7r3"))
    assert window_icons(first.state.decision_stack[-1]) == ("cards",)
    assert len(first.state.players[0].intrigue_cards) == 1
    last = apply_research_icon(first.state, _icon("cards", "c7r3"))
    assert last.state.decision_stack == ()
    assert len(last.state.players[0].hand) == len(before.hand) + 1


def test_seven_solari_bonus_needs_the_solari_and_advances_twice() -> None:
    poor = _at("c7r5", resources=Resources(solari=6))
    result = advance_research(poor, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c8r6"]
    )
    block = research_bonus_block(
        chosen.state.players[0], ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
    )
    assert block is ResearchBonusBlock.SOLARI
    lapsed = _lapses_unused(chosen.state, ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU)
    assert lapsed.players[0].resources.solari == 6
    assert lapsed.players[0].tleilaxu_space == 0

    rich = _at("c7r5", resources=Resources(solari=7))
    result = advance_research(rich, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c8r6"]
    )
    _waits_on_the_turn(chosen.state, ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU)
    paid = apply_research_bonus(
        chosen.state, DomainAction(action_id="pay_research_bonus", actor=0)
    )
    owner = paid.state.players[0]
    assert owner.resources.solari == 0
    assert owner.tleilaxu_space == 2
    # The second space's Intrigue card waits as the owner's own step in its
    # turn (user ruling 2026-10-10, OQ-106).
    assert [entry[:2] for entry in owner.owed_draws] == [
        ("intrigue", "tleilaxu_track")
    ]


def test_seven_solari_bonus_is_not_offered_at_the_tleilaxu_track_end() -> None:
    # On the track's last space a further advance does nothing (OQ-048), so
    # the 7 Solari would buy nothing: "비용이 있는 줄은 보상 중 하나라도
    # 무언가를 바꿀 수 있을 때만 제시한다" (OQ-071, user decision
    # 2026-09-29). It waits unusable and lapses, as when the Solari are short.
    finished = _at("c7r5", resources=Resources(solari=9), tleilaxu_space=7)
    result = advance_research(finished, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c8r6"]
    )
    block = research_bonus_block(
        chosen.state.players[0], ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
    )
    assert block is ResearchBonusBlock.TLEILAXU_TRACK_END
    lapsed = _lapses_unused(chosen.state, ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU)
    assert lapsed.players[0].resources.solari == 9
    assert lapsed.players[0].tleilaxu_space == 7

    # One space short, the first advance still reaches the VP space.
    near = _at("c7r5", resources=Resources(solari=9), tleilaxu_space=6)
    result = advance_research(near, 0, source="test")
    chosen = apply_research_advance(
        result.state, _research_choices(result.state)["c8r6"]
    )
    paid = apply_research_bonus(
        chosen.state, DomainAction(action_id="pay_research_bonus", actor=0)
    )
    assert paid.state.players[0].tleilaxu_space == 7
    assert paid.state.players[0].resources.solari == 2


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

    first = advance_tleilaxu(state, 0, 4)
    owner = first.state.players[0]
    assert owner.tleilaxu_space == 4
    # Inside the seat's own turn the second space's Intrigue card waits as
    # its own step (user ruling 2026-10-10, OQ-106).
    assert owner.intrigue_cards == ()
    assert [entry[1] for entry in owner.owed_draws] == ["tleilaxu_track"]
    assert owner.victory_points == 2
    assert owner.resources.spice == 4
    assert first.state.tleilaxu_track_spice == 0

    # The second player to reach the space gains the point but no spice;
    # outside its own turn the Intrigue card is drawn at once.
    second = advance_tleilaxu(first.state, 1, 4)
    other = second.state.players[1]
    assert other.victory_points == 2 and other.resources.spice == 0
    assert len(other.intrigue_cards) == 1 and other.owed_draws == ()

    end = advance_tleilaxu(second.state, 0, 4)
    owner = end.state.players[0]
    assert owner.tleilaxu_space == TLEILAXU_TRACK_END
    assert owner.victory_points == 3
    assert [entry[1] for entry in owner.owed_draws] == ["tleilaxu_track"] * 2
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
        DrawPersonalCards(2),
        Research(),
    )
    assert static_board_effects(
        "research_station", 0, choam_module=False, immortality=True
    ) == (DrawPersonalCards(2), Research())
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
    # Two copies of the card are one action: one per entity that printed the
    # gain (stage B3e-1, by its type), each press taking one copy's.
    assert actions == (
        DomainAction(
            "generate_reveal_specimens",
            0,
            (("printed", "experimentation"), ("source", "reveal_card")),
        ),
    )
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


def test_family_atomics_on_a_short_deck_deals_what_is_left_for_good() -> None:
    # "remove all cards from the Imperium Row, then deal a new Imperium Row"
    # [Immortality p. 12]. OQ-051 (project convention 2026-09-08): the
    # removed cards leave the game, and "deck이 5장 미만이면 남은 만큼만 새
    # Row를 만든다" (OQ-004's exhausted deck: nothing reshuffles back).
    full = _at(RESEARCH_START_ID)
    state = replace(full, imperium_deck=full.imperium_deck[:3])
    old_row = state.imperium_row

    used = apply_family_atomics(state, legal_family_atomics_actions(state, 0)[0])

    assert used.state.imperium_row == state.imperium_deck
    assert used.state.imperium_deck == ()
    assert used.state.imperium_removed == old_row

    # A later acquisition from the Row finds the deck empty: the Row shrinks
    # instead of the removed cards coming back.
    revealed = begin_reveal_turn(
        used.state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    while gains := legal_reveal_gain_actions(revealed, 0):
        revealed = apply_reveal_gain(revealed, gains[0]).state
    acquire = next(
        action
        for action in legal_imperium_acquisitions(revealed, 0)
        if dict(action.arguments)["instance_id"] in revealed.imperium_row
    )
    taken = str(dict(acquire.arguments)["instance_id"])
    acquired = apply_imperium_acquisition(revealed, acquire).state
    assert acquired.imperium_row == tuple(
        card for card in used.state.imperium_row if card != taken
    )
    assert acquired.imperium_deck == ()
    assert acquired.imperium_removed == old_row
    assert not set(old_row) & {*acquired.imperium_row, *acquired.imperium_deck}


# --- integration -------------------------------------------------------------


def test_the_codec_holds_the_immortality_choices_only_with_the_option() -> None:
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    immortality = {template.action_id for template in ActionCodec(IMMORTALITY).catalog}
    added = {"return_specimen", "use_family_atomics"}
    assert added <= immortality
    assert not (added & base)
    # Stage B3d-2a: the research windows offer their choices by rows, so these
    # whole templates are in no catalog; the row that stands for each is
    # Immortality's alone (a research space's target row, and the effect row
    # of the bonus printed on that space). Stage B3d-3: the bonus's refusal is
    # the ``decline`` row naming the effect it answers and the space, so
    # ``decline_research_bonus`` is in no catalog either.
    # Stage B3e-1: so is ``generate_reveal_specimens``; the Reveal frame
    # offers its specimens by the entity that printed them, one row each.
    gone = {
        "choose_research_space",
        "choose_research_influence",
        "trash_intrigue_for_research_bonus",
        "pay_research_bonus",
        "decline_research_bonus",
        "generate_reveal_specimens",
    }
    assert not (gone & immortality)
    wholes = (
        DomainAction("choose_research_space", 0, (("space_id", "c4r2"),)),
        DomainAction("choose_research_influence", 0, (("faction", "fremen"),)),
        DomainAction(
            "trash_intrigue_for_research_bonus",
            0,
            (("card_id", "intrigue:crysknife:0"),),
        ),
        DomainAction("pay_research_bonus", 0),
        DomainAction("decline_research_bonus", 0),
        DomainAction(
            "generate_reveal_specimens",
            0,
            (("printed", "experimentation"), ("source", "reveal_card")),
        ),
    )
    plain = ActionCodec(RulesetConfig())
    with_option = ActionCodec(IMMORTALITY)
    for whole in wholes:
        with pytest.raises(ValueError, match="not present"):
            with_option.encode(whole)
        # The refusal names the space whose bonus it declines.
        printed = "c7r3" if whole.action_id == "decline_research_bonus" else None
        (row, *_) = steps_for(whole, printed)
        assert with_option.decode(with_option.encode(row), 0) == row
        with pytest.raises(ValueError, match="not present"):
            plain.encode(row)


def test_go_to_11_leaves_the_action_catalog_alone() -> None:
    # The variant adds no decision, so the codec only changed its version.
    assert ActionCodec(GO_TO_11).catalog == ActionCodec(IMMORTALITY).catalog


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_a_go_to_11_game_finishes_from_zero(policy: str) -> None:
    # Every Victory Point loss undoes an earlier gain [Main pp. 7, 17], so a
    # game started on 0 never trips the non-negative check.
    report = run_checked_game(
        GO_TO_11, 11, 900_011, policy=policy, soundness_interval=25
    )
    assert report.winner is not None


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
