"""Immortality on the original Dune: Imperium (stage P7b).

docs/base-game-and-ix-plan.md 19.2: "Immortality는 원본 Dune: Imperium의 두
번째 확장" (docs/rules/immortality.md), so the original game takes it, its Go
to 11 variant [Immortality p. 12] with it. Its setup steps (immortality.md 2)
are the rulebook's own, written for the original game: the 30 Imperium and
15 Intrigue cards shuffled into the decks [Immortality pp. 4-5], the Bene
Tleilax board with its tokens and 2 spice [Immortality p. 4], the Tleilaxu
Row [Immortality p. 4], the Research Station overlay "Research Station
overlay를 Research Station 위에 덮는다(Uprising의 Research Station도)"
[Immortality p. 5], Family Atomics and Experimentation [Immortality p. 5].
"""

from dataclasses import replace

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec, ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.core.effects import DrawPersonalCards, Research
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.immortality.tleilaxu import tleilaxu_deck_instance_ids
from dune_imperium.content.registry.imperium import imperium_deck_instance_ids
from dune_imperium.content.registry.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    Resources,
)
from dune_imperium.core.engine import Transition
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.agent_turn import (
    executable_placements,
    heighliner_partner_discount,
)
from dune_imperium.rules.board_effects import static_board_effects
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.effect_steps import steps_for
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.simulation.sweep import run_checked_game

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
IMMORTALITY = replace(ORIGINAL, immortality=True)
GO_TO_11 = replace(IMMORTALITY, go_to_11=True)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)


def _start(config: RulesetConfig = IMMORTALITY, seed: int = 3) -> GameState:
    """Round 1, seat 0's first turn (the hands drawn)."""

    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _with_card(state: GameState, card_id: str) -> GameState:
    """Seat 0 with its starting ``card_id`` in hand, from its deck if needed."""

    owner = state.players[0]
    if any(f":{card_id}:" in card for card in owner.hand):
        return state
    instance = next(card for card in owner.deck if f":{card_id}:" in card)
    return _seat(
        state,
        hand=(*owner.hand, instance),
        deck=tuple(card for card in owner.deck if card != instance),
    )


def _place(state: GameState, space_id: str) -> GameState:
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and not dict(placement.arguments).get("graft")
    )
    return apply_placement(ENGINE, state, placement).state


def _wholes(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.whole_actions(state, 0)


def _board_effects(state: GameState) -> list[object]:
    return [
        dict(action.arguments).get("effect")
        for action in _wholes(state)
        if action.action_id == "resolve_board_effect"
    ]


def _do(state: GameState, action_id: str, **arguments: object) -> GameState:
    action = next(
        action
        for action in _wholes(state)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(ENGINE, state, action).state


# --- Setup [Immortality pp. 4-5] -------------------------------------------------


def test_the_decks_take_immortality_s_thirty_imperium_and_fifteen_intrigue() -> None:
    """ "Imperium 카드 30장을 Imperium Deck에 섞는다(Imperium Row를 만들기
    전에)" [Immortality p. 4] and "Intrigue 15장을 Intrigue Deck에 섞는다"
    [Immortality p. 5] (immortality.md 2 items 1 and 6): the original decks
    gain Immortality's cards after their own, the Tleilaxu deck and
    Experimentation join the base game's card ids, and the game without the
    option keeps its tables."""

    plain = content_for(ORIGINAL)
    content = content_for(IMMORTALITY)
    added_imperium = [
        card
        for card in content.imperium_deck_instance_ids
        if card not in plain.imperium_deck_instance_ids
    ]
    added_intrigue = [
        card
        for card in content.intrigue_deck_instance_ids
        if card not in plain.intrigue_deck_instance_ids
    ]
    assert content.imperium_deck_instance_ids == (
        *plain.imperium_deck_instance_ids,
        *added_imperium,
    )
    assert content.intrigue_deck_instance_ids == (
        *plain.intrigue_deck_instance_ids,
        *added_intrigue,
    )
    assert (len(added_imperium), len(added_intrigue)) == (30, 15)
    assert {"imperium:tleilaxu_master:1", "imperium:dissecting_kit:1"} <= set(
        added_imperium
    )
    assert {"intrigue:harvest_cells:1", "intrigue:breakthrough:0"} <= set(
        added_intrigue
    )
    assert {"experimentation", "ghola", "piter_genius_advisor", "usurp"} <= (
        content.card_ids - plain.card_ids
    )
    # The Uprising starting deck the original game uses [DI p. 3], both Dune,
    # the Desert Planet turned into Experimentation [Immortality p. 5].
    identities = {
        entry.card.card_id: entry.copies for entry in content.starting_deck_entries
    }
    assert identities["experimentation"] == 2
    assert "dune_the_desert_planet" not in identities
    assert sum(identities.values()) == 10
    assert content.starting_discard_entries == ()


def test_setup_places_the_bene_tleilax_board_on_the_original_game() -> None:
    """ "bank의 spice 2를 Tleilaxu track의 네 번째 칸에 놓는다 … 하나를
    Tleilaxu token으로 … 맨 왼쪽 칸에, 하나를 research token으로 research
    track의 맨 왼쪽 칸에" [Immortality p. 4]; the Tleilaxu Row shows two
    cards [Immortality p. 4]; each player keeps a Family Atomics token
    [Immortality p. 5]. Both setup paths, fixed Leaders and the draft."""

    fixed = create_initial_state(IMMORTALITY, 7, LEADERS).state
    draft = create_draft_initial_state(replace(IMMORTALITY, leader_draft=True), 3).state
    for state in (fixed, draft):
        assert state.tleilaxu_track_spice == 2
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
    # Piter, Genius Advisor joins the Tleilaxu deck with the promos only
    # (immortality.md 1).
    promo = create_initial_state(replace(IMMORTALITY, promo_cards=True), 7, LEADERS)
    piter = "tleilaxu:piter_genius_advisor:0"
    assert piter in (*promo.state.tleilaxu_row, *promo.state.tleilaxu_deck)
    assert piter not in (*fixed.tleilaxu_row, *fixed.tleilaxu_deck)
    # The original game without the option has no Bene Tleilax pieces.
    plain = create_initial_state(ORIGINAL, 7, LEADERS).state
    assert plain.tleilaxu_track_spice == 0
    assert plain.tleilaxu_row == ()
    assert all(player.research_space == "" for player in plain.players)


def test_go_to_11_starts_every_score_marker_on_zero_on_the_original_game() -> None:
    """ "For a 4-player game, start at 0 and play to 10." [Immortality p. 12]
    (immortality.md 8): the Score markers start on 0, the Endgame stays at 10,
    and nothing else of the setup moves."""

    assert (GO_TO_11.starting_victory_points, GO_TO_11.endgame_victory_points) == (
        0,
        10,
    )
    fixed = create_initial_state(GO_TO_11, 7, LEADERS)
    draft = create_draft_initial_state(replace(GO_TO_11, leader_draft=True), 3)
    for result in (fixed, draft):
        assert [player.victory_points for player in result.state.players] == [0] * 4
    plain = create_initial_state(IMMORTALITY, 7, LEADERS)
    assert [player.victory_points for player in plain.state.players] == [1] * 4
    assert fixed.chance_outcomes == plain.chance_outcomes
    assert ActionCodec(GO_TO_11).catalog == ActionCodec(IMMORTALITY).catalog


# --- The Research Station overlay [Immortality pp. 5, 16] ------------------------


def test_the_overlay_covers_the_original_research_station() -> None:
    """ "Research Station overlay를 Research Station 위에 덮는다(Uprising의
    Research Station도)" [Immortality p. 5]: the overlay prints "Draw two
    cards and research" [Immortality pp. 5, 16] (immortality.md 6) over the
    original space's three cards [DI p. 18]; Uprising's Research Station
    takes the same overlay."""

    assert (
        static_board_effects("imperium_research_station", 0, choam_module=False)
        == (DrawPersonalCards(1),) * 3
    )
    overlay = static_board_effects(
        "imperium_research_station", 0, choam_module=False, immortality=True
    )
    assert overlay == (DrawPersonalCards(2), Research())
    assert overlay == static_board_effects(
        "research_station", 0, choam_module=False, immortality=True
    )


def test_visiting_the_covered_research_station_draws_two_and_researches() -> None:
    """The overlay's space keeps the original one's cost and City icon (2
    water [DI p. 18], immortality.md 6), draws two cards and advances the
    research token once (c1r3's specimen [Immortality p. 3 board artwork])."""

    state = _seat(_with_card(_start(), "reconnaissance"), resources=Resources(water=2))
    hand = len(state.players[0].hand)
    placed = _place(state, "imperium_research_station")
    assert placed.players[0].resources.water == 0
    assert sorted(map(str, _board_effects(placed))) == ["cards", "research"]
    researched = _do(placed, "resolve_board_effect", effect="research")
    owner = researched.players[0]
    assert owner.research_space == "c1r3"
    assert owner.specimens == 1
    drawn = _do(researched, "resolve_board_effect", effect="cards")
    # The placed card left the hand; the overlay's two cards came in at once.
    assert len(drawn.players[0].hand) == hand - 1 + 2
    assert "cards" not in _board_effects(drawn)


def test_the_original_catalog_takes_the_research_row_with_immortality_only() -> None:
    """The original board prints no research icon (imperium-base.md 2); the
    overlay brings it with the option (stage P7b)."""

    research = ActionTemplate(
        "advance",
        (
            ("icon", "research"),
            ("printed", "imperium_research_station"),
            ("source", "board_space"),
        ),
    )
    assert research in ActionCodec(IMMORTALITY).catalog
    assert research not in ActionCodec(ORIGINAL).catalog


def test_the_immortality_rows_name_the_original_game_s_cards() -> None:
    """The original game's Imperium and Intrigue ids are not Uprising's, so
    the Immortality rows that name a deck card read its own decks: Tleilaxu
    Master's "비용 6 이하 카드 1장을 acquire" and Imperium Ceremony's keep of
    a peeked Intrigue card (immortality audit) round-trip for every original
    card, and its catalog holds no Uprising-only card for them."""

    codec = ActionCodec(IMMORTALITY)
    content = content_for(IMMORTALITY)
    for instance_id in content.imperium_deck_instance_ids:
        whole = DomainAction(
            "acquire_imperium_by_card", 0, (("instance_id", instance_id),)
        )
        for row in steps_for(whole, "tleilaxu_master"):
            assert codec.decode(codec.encode(row), 0) == row
    for instance_id in content.intrigue_deck_instance_ids:
        whole = DomainAction("keep_peeked_intrigue", 0, (("instance_id", instance_id),))
        for row in steps_for(whole, "imperium_ceremony"):
            assert codec.decode(codec.encode(row), 0) == row
    named = {
        value
        for template in codec.catalog
        for _, value in template.arguments
        if isinstance(value, str)
    }
    uprising = {
        *imperium_deck_instance_ids(
            True, True, bloodlines=True, tech_module=True, immortality=True
        ),
        *intrigue_deck_instance_ids(
            True, bloodlines=True, tech_module=True, immortality=True
        ),
    }
    original = {
        *content.imperium_deck_instance_ids,
        *content.intrigue_deck_instance_ids,
    }
    assert not named & (uprising - original)


@pytest.mark.parametrize(
    "config",
    [
        RulesetConfig(imperium_cards=True, immortality=True, promo_cards=True),
        RulesetConfig(rise_of_ix=True, immortality=True, promo_cards=True),
    ],
    ids=["uprising-original-cards", "uprising-ix"],
)
def test_the_immortality_rows_name_every_card_of_a_mixed_uprising_deck(
    config: RulesetConfig,
) -> None:
    # The same two rows on an Uprising deck that holds the original cards
    # (stage P7e) or Rise of Ix's (P7f): every card of the game's own decks
    # round-trips as Tleilaxu Master's acquisition and Imperium Ceremony's
    # keep (stage P7 lane B asked whether the original cards were missing).
    codec = ActionCodec(config)
    content = content_for(config)
    for instance_id in content.imperium_deck_instance_ids:
        whole = DomainAction(
            "acquire_imperium_by_card", 0, (("instance_id", instance_id),)
        )
        for row in steps_for(whole, "tleilaxu_master"):
            assert codec.decode(codec.encode(row), 0) == row
    for instance_id in content.intrigue_deck_instance_ids:
        whole = DomainAction("keep_peeked_intrigue", 0, (("instance_id", instance_id),))
        for row in steps_for(whole, "imperium_ceremony"):
            assert codec.decode(codec.encode(row), 0) == row


# --- Rise of Ix with Immortality on the original board (plan 17.5 3) ------------

IX_IMMORTALITY = replace(IMMORTALITY, rise_of_ix=True)
MASTER = "imperium:tleilaxu_master:0"
# Spiritual Fervor costs 3, For Humanity 7 [card faces] (immortality audit).
CHEAP = "imperium:spiritual_fervor:0"
DEAR = "imperium:for_humanity:0"


def _master_turn(*, research_space: str, tech_ids: tuple[str, ...]) -> GameState:
    """Seat 0's original + Rise of Ix + Immortality turn with Tleilaxu Master
    played to Imperial Basin (Spice Trade) and its Agent box waiting, the
    Imperium Row holding a card of cost 3 and one of cost 7."""

    state = _start(IX_IMMORTALITY)
    pinned = (MASTER, CHEAP, DEAR)
    deck = [card for card in (*state.imperium_row, *state.imperium_deck)]
    rest = [card for card in deck if card not in pinned]
    state = replace(
        state,
        imperium_row=(CHEAP, DEAR, *rest[:3]),
        imperium_deck=tuple(rest[3:]),
        # The seat's tiles leave the Ix board's stacks.
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile not in tech_ids)
            for stack in state.tech_stacks
        ),
    )
    owner = state.players[0]
    state = _seat(
        state,
        hand=(*owner.hand, MASTER),
        research_space=research_space,
        tech_ids=tech_ids,
    )
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == "imperial_basin"
        and dict(placement.arguments)["card_id"] == MASTER
        and not dict(placement.arguments).get("graft")
    )
    return apply_placement(ENGINE, state, placement).state


def _acquisitions(state: GameState) -> list[DomainAction]:
    return [
        action
        for action in _wholes(state)
        if action.action_id in ("acquire_imperium_by_card", "acquire_reserve_by_card")
    ]


def _round_trips(state: GameState) -> None:
    codec = ActionCodec(IX_IMMORTALITY)
    for action in ENGINE.legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action


def test_tleilaxu_master_takes_spaceport_s_deck_top_with_one_marker() -> None:
    """Spaceport "얻는 카드를 덱 위에 놓을 수 있다" (docs/rules/rise-of-ix.md 4)
    meets Tleilaxu Master's "(1M): 비용 6 이하 카드 1장을 acquire할 수 있다"
    (docs/implementation-audits/immortality.md): each card in reach is offered
    to the discard pile and, beside it, on top of the deck, where every seat
    knows it until it is drawn (OQ-145). Plan 17 "P7 점검 목록": the Agent
    box's acquisition had no such twin."""

    state = _master_turn(research_space="c4r2", tech_ids=("spaceport",))
    rows = {
        (dict(a.arguments).get("instance_id"), dict(a.arguments).get("to_deck_top"))
        for a in _acquisitions(state)
        if a.action_id == "acquire_imperium_by_card"
    }
    assert {(CHEAP, None), (CHEAP, True)} <= rows
    assert not {(DEAR, None), (DEAR, True)} & rows
    reserve = {
        (dict(a.arguments)["card_id"], dict(a.arguments).get("to_deck_top"))
        for a in _acquisitions(state)
        if a.action_id == "acquire_reserve_by_card"
    }
    assert {("arrakis_liaison", None), ("arrakis_liaison", True)} <= reserve
    _round_trips(state)
    twin = next(
        a
        for a in _acquisitions(state)
        if dict(a.arguments).get("instance_id") == CHEAP
        and dict(a.arguments).get("to_deck_top") is True
    )
    taken = apply_whole(ENGINE, state, twin).state
    owner = taken.players[0]
    assert owner.deck[0] == CHEAP
    assert owner.deck_public_top == (CHEAP,)
    assert CHEAP not in owner.discard_pile
    assert CHEAP not in taken.imperium_row


def test_tleilaxu_master_without_spaceport_or_with_two_markers_has_no_twin() -> None:
    """Without the tile the card goes to the discard pile only; with the
    second marker "(2M): 그 카드를 hand에 둔다" sends it to the hand, which
    takes no deck-top twin (as the other cap acquisitions,
    ``ability_executor.acquires_to_hand``)."""

    plain = _master_turn(research_space="c4r2", tech_ids=())
    assert _acquisitions(plain)
    assert not any(dict(a.arguments).get("to_deck_top") for a in _acquisitions(plain))
    two = _master_turn(research_space="c8r4", tech_ids=("spaceport",))
    assert _acquisitions(two)
    assert not any(dict(a.arguments).get("to_deck_top") for a in _acquisitions(two))
    acquire = next(
        a for a in _acquisitions(two) if dict(a.arguments).get("instance_id") == CHEAP
    )
    owner = apply_whole(ENGINE, two, acquire).state.players[0]
    assert CHEAP in owner.hand and CHEAP in owner.hand_public


def _reveal_with_specimens(
    config: RulesetConfig, *, tech_ids: tuple[str, ...] = (), **changes: object
) -> GameState:
    """Seat 0's Reveal turn on the original board with six specimens and the
    Tleilaxu Row (Contaminator, Subject X-137) in front of it."""

    state = _start(config)
    row = ("tleilaxu:contaminator:0", "tleilaxu:subject_x_137:0")
    rest = tuple(
        card for card in (*state.tleilaxu_row, *state.tleilaxu_deck) if card not in row
    )
    state = replace(
        state,
        tleilaxu_row=row,
        tleilaxu_deck=rest,
        # The seat's tiles leave the Ix board's stacks.
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile not in tech_ids)
            for stack in state.tech_stacks
        ),
    )
    owner = state.players[0]
    state = _seat(
        state,
        0,
        specimens=6,
        troops_supply=owner.troops_supply - 6,
        tech_ids=tech_ids,
        **changes,
    )
    return _do(state, "reveal_turn")


def _tleilaxu_rows(state: GameState) -> set[tuple[object, object]]:
    return {
        (dict(a.arguments)["instance_id"], dict(a.arguments).get("to_deck_top"))
        for a in _wholes(state)
        if a.action_id == "acquire_tleilaxu"
    }


def test_spaceport_lets_a_tleilaxu_card_top_the_deck_before_the_marker() -> None:
    """ "첫 genetic marker에 도달하면 … acquire한 Tleilaxu 카드를 deck 맨 위에
    둘 수 있다" [Immortality pp. 6, 16] (immortality.md 3), and the rulebook's
    own clarification: "Spaceport — This Tech tile (from RISE OF IX) allows
    you to put Tleilaxu cards you acquire on top of your deck, even if your
    research token hasn't reached the first genetic marker." [Immortality
    p. 14] (plan 17.5 3): before the first marker the tile alone offers the
    deck top, where every seat knows the card (OQ-145)."""

    contaminator = "tleilaxu:contaminator:0"
    plain = _reveal_with_specimens(IX_IMMORTALITY)
    assert (contaminator, True) not in _tleilaxu_rows(plain)
    state = _reveal_with_specimens(IX_IMMORTALITY, tech_ids=("spaceport",))
    assert {(contaminator, None), (contaminator, True)} <= _tleilaxu_rows(state)
    _round_trips(state)
    taken = _do(state, "acquire_tleilaxu", instance_id=contaminator, to_deck_top=True)
    owner = taken.players[0]
    assert owner.deck[0] == contaminator
    assert owner.deck_public_top == (contaminator,)


def test_recruitment_mission_lets_a_tleilaxu_card_top_the_deck() -> None:
    """Recruitment Mission "You may put cards you acquire on top of your
    deck" -- "카드 전체가 이번 라운드 Reveal turn에만; 획득마다 덱 위/discard를
    따로 고름" [FAQ p. 3] (imperium-base.md 13.2) -- covers a Tleilaxu card
    on the original board before the first genetic marker (plan 17.5 3; the
    Uprising game's test with the flag set is
    ``test_a_tleilaxu_card_may_top_the_deck_without_a_genetic_marker``)."""

    mission = "intrigue:recruitment_mission:0"
    contaminator = "tleilaxu:contaminator:0"
    state = _reveal_with_specimens(IMMORTALITY, intrigue_cards=(mission,))
    assert (contaminator, True) not in _tleilaxu_rows(state)
    played = _do(state, "play_intrigue", card_id=mission)
    while not _tleilaxu_rows(played):
        played = apply_whole(ENGINE, played, _wholes(played)[0]).state
    assert {(contaminator, None), (contaminator, True)} <= _tleilaxu_rows(played)
    taken = _do(played, "acquire_tleilaxu", instance_id=contaminator, to_deck_top=True)
    assert taken.players[0].deck[0] == contaminator
    assert taken.players[0].deck_public_top == (contaminator,)


BOUNDLESS = "imperium:boundless_ambition:0"
USURP = "tleilaxu:usurp:0"
REFILL = CHEAP  # Spiritual Fervor, cost 3, the Imperium deck's top card
TURN_END_SKIPS = ("finish_agent_turn", "use_family_atomics", "return_specimen")


def _rows_round_trip(state: GameState) -> None:
    codec = ActionCodec(state.config)
    for action in ENGINE.legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action


def test_a_usurped_boundless_ambition_acquires_after_the_row_refills() -> None:
    """Rise of Ix's promo with Immortality on the original board.

    Official: "Trashing a card with Usurp does trigger effects like
    Replacement Eyes and cards with Unload (from RISE OF IX)." [Immortality
    p. 14] -- the turn-end trash of the Usurped Row card ("trash that card at
    the end of your turn", OQ-054) gives Boundless Ambition's Unload, "Acquire
    a card that costs [5] or less" (rise-of-ix.md 7).

    Not official, the timing only: asked whether the card is acquired before
    or after the Imperium Row is refilled to 5, "After. You immediately refill
    to 5 and can acquire that new card" if it costs 5 or less (Dire Wolf
    Discord, via the community compilation elessar 2026-06-07; not the
    official FAQ, the speaker is not named). Neither the official FAQ
    (2025-01-13) nor the Immortality rulebook orders the refill against the
    Unload.

    The engine already meets it: the graft refills the Row from the deck's
    top at once (OQ-054, no chance step -- the deck was shuffled at setup), so
    the new card is in the Row when the press trashes Boundless Ambition. The
    Unload is owed inside its owner's turn, so it waits on the turn as a
    mandatory row and the turn reopens (OQ-095 (5)); the owner takes it, its
    window offers the refilled card, and the owner's next press opens the next
    seat's turn."""

    state = _start(replace(IX_IMMORTALITY, promo_cards=True))
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card not in (BOUNDLESS, REFILL)
    ]
    owner = state.players[0]
    state = _seat(
        replace(
            state,
            imperium_row=(BOUNDLESS, *others[:4]),
            imperium_deck=(REFILL, *others[4:]),
            tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != USURP),
            tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != USURP),
        ),
        hand=(*owner.hand, USURP),
    )
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == USURP
        and dict(placement.arguments)["space_id"] == "wealth"
    )
    state = apply_placement(ENGINE, state, placement).state
    state = _do(state, "choose_graft_partner", card_id=BOUNDLESS)
    # The Row refilled from the deck's top as the card was borrowed.
    assert state.imperium_row[0] == REFILL
    assert state.players[0].usurped_row_card_id == BOUNDLESS
    while not any(a.action_id == "finish_agent_turn" for a in _wholes(state)):
        step = next(a for a in _wholes(state) if a.action_id not in TURN_END_SKIPS)
        state = apply_whole(ENGINE, state, step).state

    pressed = apply_whole(
        ENGINE,
        state,
        next(a for a in _wholes(state) if a.action_id == "finish_agent_turn"),
    )
    kinds = [event.kind for event in pressed.events]
    assert kinds.index("usurped_card_trashed") < kinds.index("card_unloaded")
    assert kinds[-1] == "agent_turn_reopened"
    state = pressed.state
    assert BOUNDLESS in state.players[0].trashed
    # The Unload holds the turn's end until the owner takes it.
    rows = [(a.action_id, dict(a.arguments)) for a in _wholes(state)]
    assert ("finish_agent_turn", {}) not in rows
    assert (
        "resolve_unload_icon",
        {"card_id": BOUNDLESS, "effect": "acquisition"},
    ) in rows
    state = _do(state, "resolve_unload_icon", card_id=BOUNDLESS)
    window = state.decision_stack[-1]
    assert isinstance(window.decision, PlayerDecision)
    assert window.decision.owner == 0
    assert dict(window.context)["max_cost"] == 5
    _rows_round_trip(state)
    offered = {
        dict(a.arguments)["instance_id"]
        for a in _wholes(state)
        if a.action_id == "acquire_unload_imperium_card"
    }
    assert REFILL in offered and BOUNDLESS not in offered
    state = _do(state, "acquire_unload_imperium_card", instance_id=REFILL)
    assert REFILL in state.players[0].discard_pile
    assert REFILL not in state.imperium_row
    # Spiritual Fervor's acquire box (Research) was the turn's own; the next
    # press opens the next seat's turn.
    while not any(a.action_id == "finish_agent_turn" for a in _wholes(state)):
        step = next(a for a in _wholes(state) if a.action_id not in TURN_END_SKIPS)
        state = apply_whole(ENGINE, state, step).state
    state = _do(state, "finish_agent_turn")
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.TURN
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 1


BOUNTY_HUNTER = "imperium:bounty_hunter:0"  # City, its Infiltration icon too


def _usurp_turn(row_card: str | None) -> GameState:
    """Seat 0 with Usurp in hand and seat 1's Agent on Carthag (City), the
    Imperium Row led by ``row_card`` (original + Rise of Ix + Immortality)."""

    state = _start(IX_IMMORTALITY)
    pinned = {USURP, BOUNTY_HUNTER}
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card not in pinned
    ]
    lead = () if row_card is None else (row_card,)
    state = replace(
        state,
        imperium_row=(*lead, *others[: 5 - len(lead)]),
        imperium_deck=tuple(others[5 - len(lead) :]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != USURP),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != USURP),
    )
    seat = state.players[1]
    state = _seat(
        state,
        1,
        agent_locations=("carthag",),
        agents_available=seat.agents_available - 1,
    )
    owner = state.players[0]
    return _seat(state, 0, hand=(*owner.hand, USURP))


def _usurp_to(state: GameState, space_id: str) -> list[DomainAction]:
    return [
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == USURP
        and dict(placement.arguments)["space_id"] == space_id
    ]


def test_usurp_enters_an_occupied_space_on_its_row_partner_s_infiltration() -> None:
    """ "어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다. 어느 아이콘을 썼든
    두 카드 모두 Agent를 \"보낸\" 것으로 취급한다" [Immortality p. 10]
    (immortality.md 5), and "Agent의 옆얼굴이 든 Agent 아이콘은 그 아이콘의
    칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게 한다" [Rise of Ix
    p. 7] (rise-of-ix.md 7): Usurp grafted to Bounty Hunter from the Imperium
    Row may go to Carthag past seat 1's Agent, and only an infiltrating card
    may then be its partner. Without one in reach the occupied space is
    closed, as before."""

    assert not _usurp_to(_usurp_turn(None), "carthag")
    state = _usurp_turn(BOUNTY_HUNTER)
    (placement,) = _usurp_to(state, "carthag")
    sent = apply_placement(ENGINE, state, placement).state
    _rows_round_trip(sent)
    partners = [
        dict(action.arguments)["card_id"]
        for action in _wholes(sent)
        if action.action_id == "choose_graft_partner"
    ]
    assert partners == [BOUNTY_HUNTER]
    grafted = _do(sent, "choose_graft_partner", card_id=BOUNTY_HUNTER)
    assert "carthag" in grafted.players[0].agent_locations
    assert "carthag" in grafted.players[1].agent_locations
    assert grafted.players[0].usurped_row_card_id == BOUNTY_HUNTER


DISSECTING_KIT = "imperium:dissecting_kit:0"  # a Graft card: Landsraad, City


def test_a_hand_graft_enters_an_occupied_space_on_either_card_s_infiltration() -> (
    None
):
    """ "어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다" [Immortality p. 10]
    (immortality.md 5) with "Agent의 옆얼굴이 든 Agent 아이콘은 그 아이콘의
    칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게 한다" [Rise of Ix
    p. 7] (rise-of-ix.md 7): Dissecting Kit grafted to Bounty Hunter (City
    Infiltration) goes to Carthag past seat 1's Agent whichever card is
    placed, and with the Kit placed only Bounty Hunter may be its partner
    (Codex review of P7b, 2026-10-30: the Kit placed first was refused)."""

    state = _usurp_turn(None)
    pinned = {BOUNTY_HUNTER, DISSECTING_KIT}
    owner = state.players[0]
    state = _seat(
        replace(
            state,
            imperium_row=tuple(c for c in state.imperium_row if c not in pinned),
            imperium_deck=tuple(c for c in state.imperium_deck if c not in pinned),
        ),
        0,
        hand=(*(c for c in owner.hand if c != USURP), BOUNTY_HUNTER, DISSECTING_KIT),
    )

    def to_carthag(card_id: str) -> list[DomainAction]:
        return [
            placement
            for placement in executable_placements(state, 0)
            if dict(placement.arguments)["card_id"] == card_id
            and dict(placement.arguments)["space_id"] == "carthag"
            and dict(placement.arguments).get("graft") is True
        ]

    assert to_carthag(BOUNTY_HUNTER)
    (placement,) = to_carthag(DISSECTING_KIT)
    sent = apply_placement(ENGINE, state, placement).state
    _rows_round_trip(sent)
    partners = [
        dict(action.arguments)["card_id"]
        for action in _wholes(sent)
        if action.action_id == "choose_graft_partner"
    ]
    assert partners == [BOUNTY_HUNTER]
    grafted = _do(sent, "choose_graft_partner", card_id=BOUNTY_HUNTER)
    assert "carthag" in grafted.players[0].agent_locations
    assert "carthag" in grafted.players[1].agent_locations


KWISATZ = "imperium:kwisatz_haderach:0"


def _usurp_beside_row_kwisatz(**seat: object) -> GameState:
    """Seat 0 with Usurp in hand and Kwisatz Haderach leading the Imperium
    Row (original + Immortality)."""

    state = _start(IMMORTALITY)
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card != KWISATZ
    ]
    state = replace(
        state,
        imperium_row=(KWISATZ, *others[:4]),
        imperium_deck=tuple(others[4:]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != USURP),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != USURP),
    )
    owner = state.players[0]
    return _seat(state, 0, hand=(*owner.hand, USURP), **seat)


def test_usurp_sends_the_kwisatz_way_with_the_row_s_kwisatz_haderach() -> None:
    """ "어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다" [Immortality
    p. 10] (immortality.md 5) and Usurp grafts "with a card from the
    Imperium Row" [Usurp card]: the Row's Kwisatz Haderach -- "Send one of
    your Agents from anywhere to ANY board space (even if occupied)"
    [Kwisatz Haderach card], "Agent가 남지 않아도 낼 수 있다(이미 칸에 있는
    Agent를 보낸다)" (imperium-base.md 13.1) -- may be Usurp's partner, and
    an Agent sent its way off the board takes only that partner (Codex
    review of P7e, 2026-10-30: the iconless Kwisatz was never a partner)."""

    state = _usurp_beside_row_kwisatz(
        agent_locations=("conspire", "wealth"), agents_available=0
    )
    moves = [
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == USURP
    ]
    assert moves
    assert {dict(move.arguments).get("from_space") for move in moves} == {
        "conspire",
        "wealth",
    }
    (move,) = [
        m
        for m in moves
        if dict(m.arguments)["space_id"] == "foldspace"
        and dict(m.arguments)["from_space"] == "conspire"
    ]
    sent = apply_placement(ENGINE, state, move).state
    _rows_round_trip(sent)
    partners = [
        dict(action.arguments)["card_id"]
        for action in _wholes(sent)
        if action.action_id == "choose_graft_partner"
    ]
    assert partners == [KWISATZ]
    grafted = _do(sent, "choose_graft_partner", card_id=KWISATZ)
    seat = grafted.players[0]
    assert sorted(seat.agent_locations) == ["foldspace", "wealth"]
    assert seat.agents_available == 0
    assert seat.usurped_row_card_id == KWISATZ


def test_usurp_from_the_leader_may_take_the_row_s_kwisatz_haderach() -> None:
    # An Agent from the Leader is one "from anywhere" too: beside the other
    # Row partners whose icons reach the space, the Kwisatz may follow.
    state = _usurp_beside_row_kwisatz()
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == USURP
        and dict(placement.arguments)["space_id"] == "wealth"
        and "from_space" not in dict(placement.arguments)
    )
    sent = apply_placement(ENGINE, state, placement).state
    _rows_round_trip(sent)
    partners = {
        dict(action.arguments)["card_id"]
        for action in _wholes(sent)
        if action.action_id == "choose_graft_partner"
    }
    assert KWISATZ in partners


@pytest.mark.parametrize(
    ("blocked", "seat"),
    [
        ("foldspace", {"voice_blocked_space_ids": ("foldspace",)}),
        ("imperium_high_council", {"high_council": True}),
        (
            "imperium_swordmaster",
            {
                "swordmaster_acquired": True,
                "agent_locations": ("conspire", "wealth", "carthag"),
            },
        ),
    ],
)
def test_usurp_s_kwisatz_way_still_stops_at_the_voice_and_once_a_game_spaces(
    blocked: str, seat: dict[str, object]
) -> None:
    """Kwisatz Haderach "게임에 한 번인 칸(High Council, Swordmaster)에 두 번
    보낼 수 없고, The Voice를 넘지 못한다" (imperium-base.md 13.1 [DI p. 13]),
    and Usurp's pair sends its one Agent the Kwisatz way with the same limits
    ("어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다" [Immortality p. 10],
    immortality.md 5). With no Agent left at the Leader every Usurp placement
    is a Kwisatz move of a placed Agent; the space the seat's Voice block,
    High Council seat or Swordmaster rules out is the only one missing.
    Coverage gap 2026-11-12: the three exclusions in
    ``agent_turn._usurp_kwisatz_placements`` had no test."""

    def spaces(**changes: object) -> set[str]:
        changes.setdefault("agent_locations", ("conspire", "wealth"))
        state = _usurp_beside_row_kwisatz(
            agents_available=0,
            resources=Resources(solari=20, spice=10, water=5),
            **changes,
        )
        moves = [
            placement
            for placement in executable_placements(state, 0)
            if dict(placement.arguments)["card_id"] == USURP
        ]
        assert all("from_space" in dict(move.arguments) for move in moves)
        return {str(dict(move.arguments)["space_id"]) for move in moves}

    free = spaces()
    assert blocked in free
    assert free - spaces(**seat) == {blocked}


def test_a_usurped_power_play_that_trashed_itself_is_not_trashed_again() -> None:
    """Usurp: "If you do, trash that card at the end of your turn." [Usurp
    card], and OQ-054 확정 (2026-09-08): at the turn's end the card goes as an
    ordinary trash, but "turn 중 다른 효과로 이미 소유 존(hand·deck·discard·
    play)을 떠났으면 더 할 일이 없다". Power Play is a card that trashes
    itself (imperium-base.md 13.1, "자기를 trash하는 카드(Seek Allies,
    Foldspace, Power Play, …)"): borrowed from the Row on Secrets, its box
    pays and trashes it, so the end only clears the borrow -- one
    ``usurped_card_trashed``, no second ``card_trashed``, one copy in the
    trash pile. Coverage gap 2026-11-12: a soak game (Uprising with the
    original cards, Bloodlines and Immortality, seed 4) reached
    ``graft.trash_usurped_card``'s left-every-zone branch; no test did."""

    power_play = "imperium:power_play:0"
    state = _start(IMMORTALITY)
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card != power_play
    ]
    state = replace(
        state,
        imperium_row=(power_play, *others[:4]),
        imperium_deck=tuple(others[4:]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != USURP),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != USURP),
    )
    state = _seat(state, 0, hand=(*state.players[0].hand, USURP))
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == USURP
        and dict(placement.arguments)["space_id"] == "secrets"
        and "from_space" not in dict(placement.arguments)
    )
    sent = apply_placement(ENGINE, state, placement).state
    grafted = _do(sent, "choose_graft_partner", card_id=power_play)
    assert grafted.players[0].usurped_row_card_id == power_play
    played = _do(grafted, "resolve_agent_card_effect", box=1)
    assert played.players[0].trashed.count(power_play) == 1
    assert played.players[0].usurped_row_card_id == power_play
    while any(
        action.action_id == "resolve_board_effect" for action in _wholes(played)
    ):
        played = _do(played, "resolve_board_effect")

    finished = ENGINE.apply(played, DomainAction("finish_agent_turn", 0))
    seat = finished.state.players[0]
    assert seat.usurped_row_card_id == ""
    assert seat.trashed.count(power_play) == 1
    kinds = [event.kind for event in finished.events]
    assert kinds.count("usurped_card_trashed") == 1
    assert "card_trashed" not in kinds


FREIGHTER_FLEET = "imperium:freighter_fleet:0"  # Spice Trade, Unload Freighter
IX_GUILD_COMPACT = "imperium:ix_guild_compact:0"  # Unload, two Negotiators


def _usurp_to_the_press(partner: str) -> GameState:
    """Seat 0 Usurps ``partner`` from the Imperium Row on the original board
    with Rise of Ix and Immortality and takes every other effect of its turn,
    up to the turn-end press."""

    state = _start(IX_IMMORTALITY)
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card != partner
    ]
    owner = state.players[0]
    state = _seat(
        replace(
            state,
            imperium_row=(partner, *others[:4]),
            imperium_deck=tuple(others[4:]),
            tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != USURP),
            tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != USURP),
        ),
        hand=(*owner.hand, USURP),
    )
    for placement in executable_placements(state, 0):
        if dict(placement.arguments)["card_id"] != USURP:
            continue
        sent = apply_placement(ENGINE, state, placement).state
        if any(
            action.action_id == "choose_graft_partner"
            and dict(action.arguments)["card_id"] == partner
            for action in _wholes(sent)
        ):
            state = _do(sent, "choose_graft_partner", card_id=partner)
            break
    else:
        raise AssertionError(f"no space takes Usurp with {partner}")
    assert state.players[0].usurped_row_card_id == partner
    while not any(a.action_id == "finish_agent_turn" for a in _wholes(state)):
        step = next(a for a in _wholes(state) if a.action_id not in TURN_END_SKIPS)
        state = apply_whole(ENGINE, state, step).state
    return state


def _press(state: GameState) -> Transition:
    return apply_whole(
        ENGINE,
        state,
        next(a for a in _wholes(state) if a.action_id == "finish_agent_turn"),
    )


def _unload_rows(state: GameState) -> list[tuple[str, str]]:
    return [
        (str(dict(a.arguments)["card_id"]), str(dict(a.arguments)["effect"]))
        for a in _wholes(state)
        if a.action_id == "resolve_unload_icon"
    ]


def _next_seat_s_turn(state: GameState) -> bool:
    frame = state.decision_stack[-1]
    return (
        frame.kind == FrameKind.TURN
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == 1
    )


def test_a_usurped_freighter_fleet_s_optional_unload_reopens_the_turn() -> None:
    """The press trashes the Usurped Row card ("trash that card at the end of
    your turn", OQ-054), and that trash gives Freighter Fleet's Unload
    ("Trashing a card with Usurp does trigger effects like Replacement Eyes
    and cards with Unload" [Immortality p. 14]) -- "you may move your
    Freighter" [Rise of Ix p. 5], an optional row the owner never saw before
    the press. Its result is this turn's (OQ-095 (5)), and the turn reopens
    to offer it: "다시 열어 제시" (OQ-160, user ruling 2026-10-31). The owner
    takes it and presses again (before 2026-10-31 the press lapsed it, after
    the Codex review of P7b)."""

    pressed = _press(_usurp_to_the_press(FREIGHTER_FLEET))
    kinds = [event.kind for event in pressed.events]
    assert kinds.index("usurped_card_trashed") < kinds.index("agent_turn_reopened")
    assert "unload_icon_lapsed" not in kinds
    state = pressed.state
    assert FREIGHTER_FLEET in state.players[0].trashed
    assert state.players[0].usurped_row_card_id == ""
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 0
    assert _unload_rows(state) == [(FREIGHTER_FLEET, "freighter")]
    assert any(a.action_id == "finish_agent_turn" for a in _wholes(state))
    _rows_round_trip(state)

    before = state.players[0].freighter_space
    state = _do(state, "resolve_unload_icon", card_id=FREIGHTER_FLEET)
    while not any(a.action_id == "finish_agent_turn" for a in _wholes(state)):
        step = next(a for a in _wholes(state) if a.action_id not in TURN_END_SKIPS)
        state = apply_whole(ENGINE, state, step).state
    assert state.players[0].freighter_space == before + 1
    again = _press(state)
    assert "agent_turn_reopened" not in [event.kind for event in again.events]
    assert _next_seat_s_turn(again.state)


def test_pressing_the_reopened_turn_again_lapses_the_freighter() -> None:
    """Unused, the press-made "may" Freighter lapses at the reopened turn's
    press, as every optional effect does (OQ-095 (2)), and the next seat's
    turn opens: no second Usurp trash, no second reopen (OQ-160)."""

    reopened = _press(_usurp_to_the_press(FREIGHTER_FLEET)).state
    before = reopened.players[0].freighter_space
    again = _press(reopened)
    kinds = [event.kind for event in again.events]
    assert "unload_icon_lapsed" in kinds
    assert "usurped_card_trashed" not in kinds
    assert "agent_turn_reopened" not in kinds
    assert again.state.players[0].freighter_space == before
    assert _next_seat_s_turn(again.state)


def test_a_usurped_ix_guild_compact_s_negotiators_reopen_the_turn() -> None:
    """Ix-Guild Compact's Unload is two Tech Negotiation icons, each "you may
    take a troop" [Rise of Ix p. 4]: trashed by the press, they reopen the
    turn as rows (OQ-160) and lapse at its next press if unused."""

    pressed = _press(_usurp_to_the_press(IX_GUILD_COMPACT))
    kinds = [event.kind for event in pressed.events]
    assert "agent_turn_reopened" in kinds
    assert "unload_icon_lapsed" not in kinds
    assert _unload_rows(pressed.state) == [(IX_GUILD_COMPACT, "negotiator")]
    again = _press(pressed.state)
    assert [e.kind for e in again.events].count("unload_icon_lapsed") == 2
    assert _next_seat_s_turn(again.state)


def test_a_press_made_row_with_nothing_to_take_does_not_reopen() -> None:
    """A press-made "may" row that offers nothing -- a Tech Negotiation icon
    with no troop in the supply, "supply가 비면 아무 일도 없다"
    (docs/rules/rise-of-ix.md 4) -- reopens nothing: the reopened turn would
    offer nothing for it, so it lapses with the press (OQ-160)."""

    state = _usurp_to_the_press(IX_GUILD_COMPACT)
    owner = state.players[0]
    state = _seat(
        state,
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    pressed = _press(state)
    kinds = [event.kind for event in pressed.events]
    assert "agent_turn_reopened" not in kinds
    assert kinds.count("unload_icon_lapsed") == 2
    assert _next_seat_s_turn(pressed.state)


def test_an_optional_row_held_before_the_press_still_lapses_with_it() -> None:
    """Only the rows the press's own steps made reopen the turn (OQ-160): an
    optional row the owner left on the turn before pressing lapses with the
    press, "남아 있어도 \\"턴 종료\\"를 막지 않으며, 누르면 쓰지 않은 채
    사라진다" (OQ-095 (2), user ruling 2026-10-14) -- here Ix-Guild
    Compact's Unload Negotiator, put on the turn by hand -- while Freighter
    Fleet's, made by the press's Usurp trash, reopens it alone."""

    state = _usurp_to_the_press(FREIGHTER_FLEET)
    held = turn_rows.queue(
        state, 0, (turn_rows.UNLOAD_ICON, "test:held", f"{IX_GUILD_COMPACT}|negotiator")
    )
    assert held is not None
    pressed = _press(held)
    lapsed = [
        dict(event.payload)["card_id"]
        for event in pressed.events
        if event.kind == "unload_icon_lapsed"
    ]
    assert lapsed == [IX_GUILD_COMPACT]
    assert "agent_turn_reopened" in [event.kind for event in pressed.events]
    assert _unload_rows(pressed.state) == [(FREIGHTER_FLEET, "freighter")]


# --- The original game's cards with Immortality's -----------------------------


def _combat(config: RulesetConfig = IMMORTALITY, **fighter: object) -> GameState:
    """Combat Intrigue on the original board, seat 0 the only fighter (the
    other seats revealed with no unit in the Conflict)."""

    state = _start(config)
    players = tuple(replace(player, has_revealed=True) for player in state.players)
    held = fighter.get("intrigue_cards", ())
    assert isinstance(held, tuple)
    deck = tuple(card for card in state.intrigue_deck if card not in held)
    state = replace(
        _seat(replace(state, players=players, intrigue_deck=deck), 0, **fighter),
        phase=GamePhase.COMBAT,
        reveal_order=(0, 1, 2, 3),
        decision_stack=(),
    )
    return begin_combat_intrigue(state).state


def _to_conflict_end(state: GameState) -> GameState:
    """Pass every Combat step until the Conflict-end window or the round's
    next phase."""

    while state.phase is GamePhase.COMBAT and state.decision_stack:
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.PAUSE:
            state = ENGINE.apply(state, pause_outcome(state)).state
            continue
        if not isinstance(frame.decision, PlayerDecision):
            break
        if frame.kind == FrameKind.CONFLICT_END_TRIGGER:
            break
        actions = ENGINE.legal_actions(state, frame.decision.owner)
        passing = next(
            (a for a in actions if a.action_id.startswith("pass_")), actions[0]
        )
        state = ENGINE.apply(state, passing).state
    return state


HARVEST_CELLS = "intrigue:harvest_cells:0"
STAGED_INCIDENT = "intrigue:staged_incident:0"


def test_troops_lost_to_staged_incident_do_not_count_for_harvest_cells() -> None:
    """ "Harvest Cells가 세는 것은 엔진 그대로: Conflict 끝 반환에서 supply로
    간 troop과 Sardaukar Commander다 … Combat 도중에 잃거나 retreat한 troop …
    은 세지 않는다. 사용자가 짚은 정리본 문장 'Harvest Cells may not be played
    based off troops lost from Staged Incident' … 와 같다" (OQ-121 ruling 5
    (1); imperium-base.md 13.3 left this to the Immortality combination).
    Four troops in the Conflict open the Conflict-end window; Staged
    Incident's "Lose three of your troops in the Conflict" leaves one to
    return at the end, so no window opens and Harvest Cells stays in hand."""

    fighter: dict[str, object] = {
        "troops_supply": 8,
        "troops_garrison": 0,
        "troops_conflict": 4,
        "combat_strength": 8,
        "intrigue_cards": (HARVEST_CELLS, STAGED_INCIDENT),
    }
    kept = _to_conflict_end(_combat(IMMORTALITY, **fighter))
    assert kept.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert any(
        dict(a.arguments).get("card_id") == HARVEST_CELLS
        for a in ENGINE.whole_actions(kept, 0)
    )

    state = _combat(IMMORTALITY, **fighter)
    play = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "play_intrigue"
        and dict(action.arguments).get("card_id") == STAGED_INCIDENT
    )
    staged = apply_whole(ENGINE, state, play).state
    while staged.decision_stack[-1].kind != FrameKind.COMBAT_INTRIGUE:
        staged = apply_whole(ENGINE, staged, ENGINE.whole_actions(staged, 0)[0]).state
    owner = staged.players[0]
    assert owner.troops_conflict == 1
    assert owner.victory_points == state.players[0].victory_points + 1
    ended = _to_conflict_end(staged)
    assert all(
        frame.kind != FrameKind.CONFLICT_END_TRIGGER for frame in ended.decision_stack
    )
    assert HARVEST_CELLS in ended.players[0].intrigue_cards
    assert ended.players[0].specimens == 0


def test_dreadnoughts_do_not_count_for_harvest_cells() -> None:
    """Rise of Ix with Immortality on the original board: "Harvest Cells가
    세는 것은 엔진 그대로: Conflict 끝 반환에서 supply로 간 troop과 Sardaukar
    Commander다 … 그리고 dreadnought는 세지 않는다" (OQ-121 ruling 5 (1)); a
    dreadnought goes to the garrison, not the supply (ruling 5 (2)). Two
    troops and two dreadnoughts open no window; three troops do, whatever
    dreadnought fights beside them."""

    def window_opens(troops: int, dreadnoughts: int) -> bool:
        state = _combat(
            IX_IMMORTALITY,
            troops_supply=12 - troops,
            troops_garrison=0,
            troops_conflict=troops,
            dreadnoughts_supply=2 - dreadnoughts,
            dreadnoughts_conflict=dreadnoughts,
            combat_strength=2 * troops + 3 * dreadnoughts,
            intrigue_cards=(HARVEST_CELLS,),
        )
        ended = _to_conflict_end(state)
        return any(
            frame.kind == FrameKind.CONFLICT_END_TRIGGER
            for frame in ended.decision_stack
        )

    assert not window_opens(2, 2)
    assert window_opens(3, 1)
    assert window_opens(3, 0)


KWISATZ = "imperium:kwisatz_haderach:0"
GHOLA = "tleilaxu:ghola:0"


def test_ghola_grafted_to_kwisatz_sends_one_agent_and_draws_two() -> None:
    """ "When grafted to Kwisatz Haderach, you still send only one Agent on
    your turn (though you draw two cards)." [FAQ p. 2] (Ghola), on the
    original board: Kwisatz Haderach, the placed card, sends the pair's one
    Agent and Ghola copies its box, so the two boxes draw a card each. Every
    row the engine offers on the way round-trips through the original +
    Immortality catalog, which holds the Kwisatz graft rows since the P7
    merge (stage P7e put them in Uprising's)."""

    state = _start()
    state = replace(
        state,
        imperium_row=tuple(c for c in state.imperium_row if c != KWISATZ),
        imperium_deck=tuple(c for c in state.imperium_deck if c != KWISATZ),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != GHOLA),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != GHOLA),
    )
    owner = state.players[0]
    state = _seat(state, 0, hand=(*owner.hand, KWISATZ, GHOLA))
    _rows_round_trip(state)
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == KWISATZ
        and dict(placement.arguments)["space_id"] == "arrakeen"
        and dict(placement.arguments).get("graft") is True
        and "from_space" not in dict(placement.arguments)
    )
    sent = apply_placement(ENGINE, state, placement).state
    _rows_round_trip(sent)
    grafted = _do(sent, "choose_graft_partner", card_id=GHOLA)
    _rows_round_trip(grafted)
    seat = grafted.players[0]
    assert seat.agents_available == owner.agents_available - 1
    assert seat.agent_locations == (*owner.agent_locations, "arrakeen")
    hand = len(seat.hand)
    drawn = grafted
    for box in ((), (("box", 1),)):
        drawn = apply_whole(
            ENGINE, drawn, DomainAction("resolve_agent_card_effect", 0, box)
        ).state
        _rows_round_trip(drawn)
    assert len(drawn.players[0].hand) == hand + 2
    assert drawn.players[0].agent_locations == seat.agent_locations


# --- Whole games ---------------------------------------------------------------


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_checked_games_play_the_bene_tleilax_board_on_the_original_game(
    policy: str,
) -> None:
    """A short game under the sweep's checks (card conservation, specimens
    among the 12 troops, observation privacy, the codec round trip of every
    advertised action, the replay) moves the research and Tleilaxu tokens,
    makes specimens and acquires a Tleilaxu card on the original board."""

    config = RulesetConfig(base_game=BaseGame.IMPERIUM, immortality=True)
    report = run_checked_game(
        config, 11, 900_011, policy=policy, soundness_interval=25, collect_coverage=True
    )
    assert report.winner is not None
    assert report.coverage is not None
    events = report.coverage["event_kinds"]
    for kind in (
        "research_advanced",
        "specimens_generated",
        "tleilaxu_advanced",
        "tleilaxu_card_acquired",
    ):
        assert events.get(kind, 0) > 0, kind


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_a_go_to_11_game_finishes_from_zero_on_the_original_game(policy: str) -> None:
    """Every Victory Point loss undoes an earlier gain [Main pp. 7, 17]
    (immortality.md 8), so a game started on 0 never trips the non-negative
    check."""

    config = RulesetConfig(base_game=BaseGame.IMPERIUM, immortality=True, go_to_11=True)
    report = run_checked_game(config, 11, 900_011, policy=policy, soundness_interval=25)
    assert report.winner is not None


# --- Guild Accord's Heighliner cut in a graft (stage P7g, OQ-158) ---------------

GUILD_ACCORD = "imperium:guild_accord:0"  # "It costs [2 spice] less ... Heighliner"
HEIGHLINER = "imperium_heighliner"  # 6 spice [DI p. 17]


def _guild_accord_table(
    *, row: tuple[str, ...] = (), hand: tuple[str, ...] = (), spice: int = 6
) -> GameState:
    """Original + Rise of Ix + Immortality, seat 0 at its first turn with
    ``row`` leading the Imperium Row, ``hand`` added to its hand and
    ``spice`` spice."""

    state = _start(IX_IMMORTALITY)
    moved = {*row, *hand}
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card not in moved
    ]
    keep = 5 - len(row)
    state = replace(
        state,
        imperium_row=(*row, *others[:keep]),
        imperium_deck=tuple(others[keep:]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c not in moved),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c not in moved),
    )
    owner = state.players[0]
    return _seat(
        state,
        0,
        hand=(*owner.hand, *hand),
        resources=replace(owner.resources, spice=spice),
    )


def _heighliner_placements(state: GameState, card_id: str) -> dict[int, DomainAction]:
    """``card_id``'s graft placements on the Heighliner by the cut they
    promise for the partner (0: none)."""

    return {
        int(dict(placement.arguments).get("partner_discount", 0)): placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == card_id
        and dict(placement.arguments).get("graft") is True
        and dict(placement.arguments)["space_id"] == HEIGHLINER
        and "infiltrate_post_id" not in dict(placement.arguments)
    }


def _partners(state: GameState) -> list[str]:
    return [
        str(dict(action.arguments)["card_id"])
        for action in _wholes(state)
        if action.action_id == "choose_graft_partner"
    ]


def test_usurp_with_the_row_s_guild_accord_promises_its_cut() -> None:
    """ "Both played cards are considered to have “sent” the Agent, no matter
    which card’s icon you use." [Immortality p. 10]: Usurp's Row partner
    Guild Accord cuts the Heighliner's cost "with this card" (2 spice, no
    "may"). The cost is paid as the Agent goes and the partner is chosen
    next, so the placement promises the cut and the partner choice keeps
    only Guild Accord (OQ-158's design note; the app's partner window keeps
    the cards that keep the chosen space payable, P7g app comparison 2)."""

    state = _guild_accord_table(row=(GUILD_ACCORD,), hand=(USURP,), spice=4)
    placements = _heighliner_placements(state, USURP)
    assert set(placements) == {2}
    _rows_round_trip(state)
    sent = apply_placement(ENGINE, state, placements[2]).state
    assert sent.players[0].resources.spice == 0
    assert _partners(sent) == [GUILD_ACCORD]
    grafted = _do(sent, "choose_graft_partner", card_id=GUILD_ACCORD)
    assert grafted.players[0].usurped_row_card_id == GUILD_ACCORD


def test_usurp_with_guild_accord_in_hand_promises_its_cut() -> None:
    """The same with Guild Accord as a hand partner of Usurp's Graft."""

    state = _guild_accord_table(hand=(USURP, GUILD_ACCORD), spice=4)
    placements = _heighliner_placements(state, USURP)
    assert set(placements) == {2}
    sent = apply_placement(ENGINE, state, placements[2]).state
    assert sent.players[0].resources.spice == 0
    assert _partners(sent) == [GUILD_ACCORD]


def test_ghola_with_guild_accord_takes_four_spice_off() -> None:
    """Ghola "copies the entire Agent box" [Immortality p. 14], Guild Accord's
    cut included (OQ-158, user ruling 2026-10-30 "베낌"): the pair takes 4
    off the Heighliner (the app's ``GetSpiceReduction``: 4 with Ghola, in
    either order). A hand graft goes where the placed card's icons reach,
    so this pair goes there with Guild Accord placed (Ghola's own icon is
    City): its own 2, and 2 more promised for Ghola."""

    state = _guild_accord_table(hand=(GHOLA, GUILD_ACCORD), spice=2)
    assert not _heighliner_placements(state, GHOLA)
    placements = _heighliner_placements(state, GUILD_ACCORD)
    assert set(placements) == {2}
    sent = apply_placement(ENGINE, state, placements[2]).state
    assert sent.players[0].resources.spice == 0
    assert _partners(sent) == [GHOLA]


def test_a_placement_without_the_promise_takes_no_partner_that_cuts() -> None:
    """The cut has no "may": a placement that paid the full cost may not take
    a partner that cuts it, and one that promised the cut takes only such a
    partner. Guild Accord placed with Usurp (no cut) or Ghola (2 more)."""

    state = _guild_accord_table(hand=(GUILD_ACCORD, GHOLA, USURP), spice=6)
    placements = _heighliner_placements(state, GUILD_ACCORD)
    assert set(placements) == {0, 2}
    _rows_round_trip(state)
    full = apply_placement(ENGINE, state, placements[0]).state
    assert full.players[0].resources.spice == 2
    assert _partners(full) == [USURP]
    cut = apply_placement(ENGINE, state, placements[2]).state
    assert cut.players[0].resources.spice == 4
    assert _partners(cut) == [GHOLA]


def test_no_cut_is_promised_off_the_heighliner() -> None:
    state = _guild_accord_table(row=(GUILD_ACCORD,), hand=(USURP,), spice=6)
    assert not any(
        "partner_discount" in dict(placement.arguments)
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] != HEIGHLINER
    )


def test_the_partner_cut_of_each_pair() -> None:
    """The Heighliner cut a partner adds to the placed card's own: Guild
    Accord's 2 as either card, Ghola's copy of it 2 more (4 with Ghola
    placed), nothing for any other pair or off the Heighliner."""

    assert heighliner_partner_discount(HEIGHLINER, USURP, GUILD_ACCORD) == 2
    assert heighliner_partner_discount(HEIGHLINER, GUILD_ACCORD, USURP) == 0
    assert heighliner_partner_discount(HEIGHLINER, GUILD_ACCORD, GHOLA) == 2
    assert heighliner_partner_discount(HEIGHLINER, GHOLA, GUILD_ACCORD) == 4
    assert heighliner_partner_discount(HEIGHLINER, GHOLA, USURP) == 0
    assert heighliner_partner_discount("foldspace", USURP, GUILD_ACCORD) == 0


UPRISING_IX_IMMORTALITY = RulesetConfig(
    rise_of_ix=True, immortality=True, first_player_seat_zero=True
)
UPRISING_ENGINE = UprisingRulesEngine()
HEIGHLINER_POST = "spacing-guild-heighliner-deliver-supplies"


def _uprising_guild_accord_table(
    *, hand: tuple[str, ...], spice: int, mohiam_spy: bool = False
) -> GameState:
    """Uprising + Rise of Ix + Immortality, seat 0 at its first turn with
    ``hand`` added and ``spice`` spice; with ``mohiam_spy`` its Leader is
    Gaius Helen Mohiam ("Each card you play has the [Spy] icon" [Gaius Helen
    Mohiam card]) with a Spy on the Heighliner's post."""

    state = UPRISING_ENGINE.reset(UPRISING_IX_IMMORTALITY, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(
        decision := UPRISING_ENGINE.current_decision(state), ChanceDecision
    ):
        state = UPRISING_ENGINE.apply(state, chance.resolve(decision)).state
    moved = set(hand)
    others = [
        card
        for card in (*state.imperium_row, *state.imperium_deck)
        if card not in moved
    ]
    state = replace(
        state,
        imperium_row=tuple(others[:5]),
        imperium_deck=tuple(others[5:]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c not in moved),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c not in moved),
    )
    owner = state.players[0]
    changes: dict[str, object] = {
        "hand": (*owner.hand, *hand),
        "resources": replace(owner.resources, spice=spice),
    }
    if mohiam_spy:
        changes |= {
            "leader_id": "gaius_helen_mohiam",
            "spy_post_ids": (HEIGHLINER_POST,),
            "spies_supply": owner.spies_supply - 1,
        }
    return _seat(state, 0, **changes)


def _promised_space_rows(
    engine: UprisingRulesEngine, state: GameState, card_id: str, space_id: str
) -> list[DomainAction]:
    """Pick ``card_id`` to graft, round-trip every row then offered through
    the codec, and return the space picks that promise a partner cut."""

    picked = engine.apply(
        state,
        DomainAction("choose_agent_card", 0, (("card_id", card_id), ("graft", True))),
    ).state
    codec = ActionCodec(picked.config)
    rows = engine.legal_actions(picked, 0)
    for row in rows:
        assert codec.decode(codec.encode(row), 0) == row
    return [
        row
        for row in rows
        if row.action_id == "place_agent"
        and dict(row.arguments)["space_id"] == space_id
        and "partner_discount" in dict(row.arguments)
    ]


def test_the_promised_space_pick_is_in_the_codec_on_both_boards() -> None:
    """The codec holds the promised Heighliner picks (Codex review of P7g):
    the original board's with Usurp and the Row's Guild Accord, Uprising's
    with Usurp and Guild Accord in hand, and the 4 of Ghola placed with
    Guild Accord -- Ghola reaching the Heighliner on Mohiam's Spy icon."""

    original = _guild_accord_table(row=(GUILD_ACCORD,), hand=(USURP,), spice=4)
    (row,) = _promised_space_rows(ENGINE, original, USURP, HEIGHLINER)
    assert dict(row.arguments)["partner_discount"] == 2

    uprising = _uprising_guild_accord_table(hand=(USURP, GUILD_ACCORD), spice=3)
    (row,) = _promised_space_rows(UPRISING_ENGINE, uprising, USURP, "heighliner")
    assert dict(row.arguments)["partner_discount"] == 2

    mohiam = _uprising_guild_accord_table(
        hand=(GHOLA, GUILD_ACCORD), spice=1, mohiam_spy=True
    )
    rows = _promised_space_rows(UPRISING_ENGINE, mohiam, GHOLA, "heighliner")
    assert [dict(row.arguments)["partner_discount"] for row in rows] == [4]
    picked = UPRISING_ENGINE.apply(
        mohiam,
        DomainAction("choose_agent_card", 0, (("card_id", GHOLA), ("graft", True))),
    ).state
    sent = UPRISING_ENGINE.apply(picked, rows[0]).state
    assert sent.players[0].resources.spice == 0
    assert [
        dict(action.arguments)["card_id"]
        for action in UPRISING_ENGINE.whole_actions(sent, 0)
        if action.action_id == "choose_graft_partner"
    ] == [GUILD_ACCORD]
