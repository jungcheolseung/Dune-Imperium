"""Rise of Ix Imperium batch F: the last eight Imperium cards (stage P4d).

Card values: the Steam app's attribute table, per-card UI pieces and English
text (4.1.2.1808, dad97e20). Rules: docs/rules/rise-of-ix.md -- each test's
docstring quotes the line it applies. Every offered row round-trips through
``ActionCodec``.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import ix_pending_of
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
CODEC = ActionCodec(IX)
WATER_PEDDLER = "imperium:water_peddler:0"
UNLOAD_ROW = "resolve_unload_icon"


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert CODEC.decode(CODEC.encode(row), seat) == row
    return rows


def _give(state: GameState, seat: int, **zones: object) -> GameState:
    """Put the named cards in ``seat``'s zones, taking them out of the
    Imperium deck and Row and of every seat's zones first (seeded decks);
    other keyword arguments set the seat's fields."""

    named = {
        card
        for cards in zones.values()
        if isinstance(cards, tuple)
        for card in cards
        if isinstance(card, str)
    }
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
            discard_pile=tuple(c for c in player.discard_pile if c not in named),
            in_play=tuple(c for c in player.in_play if c not in named),
        )
        if player.player_id == seat:
            cleaned = replace(cleaned, **zones)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _start(seed: int = 3) -> GameState:
    state = ENGINE.reset(IX, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    _rows(state)
    return state


def _whole(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> DomainAction | None:
    return next(
        (
            row
            for row in ENGINE.whole_actions(state, seat)
            if row.action_id == action_id
            and all(
                dict(row.arguments).get(key) == value
                for key, value in arguments.items()
            )
        ),
        None,
    )


def _offered(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> bool:
    _rows(state, seat)
    return _whole(state, action_id, seat, **arguments) is not None


def _do(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> RuleResult:
    whole = _whole(state, action_id, seat, **arguments)
    assert whole is not None, (action_id, arguments)
    events: list[GameEvent] = []
    while True:
        rows = _rows(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            if not isinstance(ENGINE.current_decision(state), ChanceDecision):
                _rows(state, seat)
            return RuleResult(state=state, events=tuple(events))


def _kinds(events: tuple[GameEvent, ...]) -> list[str]:
    return [event.kind for event in events]


# --- Guild Chief Administrator ----------------------------------------------

GCA = "imperium:guild_chief_administrator:0"
_ADVANCE = "advance_reveal_freighter"
_RECALL = "recall_reveal_freighter"


def _placed(state: GameState, *hand: str) -> GameState:
    """Guild Chief Administrator sent to Arrakeen (its City icon), its box
    pending; ``hand`` is the rest of the hand."""

    state = _give(state, 0, hand=(GCA, *hand))
    state = _do(state, "choose_agent_card", card_id=GCA).state
    return _do(state, "place_agent", space_id="arrakeen").state


def _space_done(state: GameState) -> GameState:
    """Arrakeen's troop and card (the visited space's own effects)."""

    state = _do(state, "resolve_board_effect", effect="troops").state
    return _do(state, "resolve_board_effect", effect="cards").state


def test_guild_chief_administrator_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Spacing Guild, cost 4, one copy; Spacing Guild, City and
    Spice Trade icons; Reveal 1 Persuasion. Screen pieces: Agent "[Discard] ->
    [Trash a card]"; Reveal "[1 Persuasion] [Freighter]"."""
    entry = IMPERIUM_CARDS_BY_ID["guild_chief_administrator"]
    assert (entry.copies, entry.acquisition_cost) == (1, 4)
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (
        AgentIcon.SPACING_GUILD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.MAY_DISCARD_TO_TRASH_A_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_MOVE_FREIGHTER,
    )
    assert entry.play_data_complete
    assert GCA in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert GCA not in content_for(config).imperium_deck_instance_ids


def test_guild_chief_administrator_card_text() -> None:
    """The box's discard arrow and the Reveal's Freighter, in both languages."""
    entry = IMPERIUM_CARDS_BY_ID["guild_chief_administrator"]
    english = personal_card_text(entry)
    korean = personal_card_text_ko(entry)
    assert "Agent: You may discard a card → You may trash a card" in english
    assert any(
        "You may move your Freighter up one space or recall it" in line
        for line in english
    )
    assert any("운송 트랙에서 한 칸 위로 또는 회수 가능" in line for line in korean)
    assert len(english) == len(korean)


def test_the_discard_pays_for_a_trash_of_any_card_including_the_discarded_one() -> None:
    """ "Discard 아이콘. 손의 카드 하나(Intrigue 아님)를 discard pile로. 대개
    비용이고, 내지 않으면 효과도 없다" (rise-of-ix.md 7, [Rise of Ix p. 7]); the
    trash takes a card "from hand, discard or play" (``TrashPersonalCard``):
    the card just discarded is in the discard pile, so it may be trashed."""
    state = _start()
    paid, kept = state.players[0].hand[:2]
    state = _placed(state, paid, kept)
    discarded = _do(state, "discard_agent_card", card_id=paid).state
    owner = discarded.players[0]
    assert paid in owner.discard_pile and paid not in owner.hand
    targets = {
        dict(row.arguments)["card_id"]
        for row in ENGINE.whole_actions(discarded, 0)
        if row.action_id == "trash_optional_card"
    }
    assert {paid, kept, GCA} <= targets
    trashed = _do(discarded, "trash_optional_card", card_id=paid).state
    assert paid in trashed.players[0].trashed
    assert paid not in trashed.players[0].discard_pile
    assert not _offered(trashed, "trash_optional_card")


def test_the_trash_stays_optional_once_the_discard_is_paid() -> None:
    """ "검은색 trash 아이콘으로 trash하는 효과는 선택이다" (uprising-systems.md,
    [FAQ p. 3]): no refusal row; the turn ends with it unused and it lapses
    (OQ-095 (2))."""
    state = _start()
    paid = state.players[0].hand[0]
    state = _placed(state, paid)
    state = _do(state, "discard_agent_card", card_id=paid).state
    state = _space_done(state)
    assert not _offered(state, "decline_optional_trash")
    assert _offered(state, "trash_optional_card")
    finished = _do(state, "finish_agent_turn")
    assert "optional_trash_lapsed" in _kinds(finished.events)
    assert paid in finished.state.players[0].discard_pile
    assert not finished.state.players[0].trashed


def test_the_discard_can_be_left_unpaid_and_needs_a_hand_card() -> None:
    """ "Discard 비용 | 낸 좌석 | 손의 카드 하나(Intrigue 아님) -OR- 내지 않음"
    (rise-of-ix.md 14): an optional arrow offers no refusal in its owner's
    turn and lapses at the turn's end (OQ-095 (2)) with nothing trashed; with
    no other hand card no discard is offered (the played card cannot pay
    itself)."""
    state = _start()
    paid = state.players[0].hand[0]
    state = _space_done(_placed(state, paid))
    assert not _offered(state, "decline_agent_card_discard")
    assert not _offered(state, "trash_optional_card")
    finished = _do(state, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in _kinds(finished.events)
    assert paid in finished.state.players[0].hand
    assert not finished.state.players[0].trashed

    alone = _placed(_start())
    assert not _offered(alone, "discard_agent_card")


def test_a_discarded_unload_card_pays_before_the_trash_and_again_if_trashed() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한
    뒤 오른쪽으로 간다" and "trash할 때 얻는다" (rise-of-ix.md 7, [Rise of Ix
    p. 7]): Water Peddler's water comes with the discard, and trashing it
    from the discard pile gives the box again."""
    state = _start()
    state = _placed(state, WATER_PEDDLER)
    water = state.players[0].resources.water
    discarded = _do(state, "discard_agent_card", card_id=WATER_PEDDLER).state
    assert discarded.players[0].resources.water == water + 1
    assert not _offered(discarded, UNLOAD_ROW)
    trashed = _do(discarded, "trash_optional_card", card_id=WATER_PEDDLER)
    assert "card_unloaded" in _kinds(trashed.events)
    again = _do(trashed.state, UNLOAD_ROW, card_id=WATER_PEDDLER, effect="water")
    assert again.state.players[0].resources.water == water + 2


def _revealed(state: GameState, space: int) -> GameState:
    state = _give(state, 0, hand=(GCA,), freighter_space=space)
    return _do(state, "reveal_turn").state


def _freighter_rows(state: GameState) -> set[str]:
    _rows(state)
    return {
        row.action_id
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id in (_ADVANCE, _RECALL)
    }


def test_the_reveal_freighter_moves_up_from_the_bottom_only() -> None:
    """ "Freighter 아이콘마다 Freighter를 둘 가운데 하나로 움직일 수 있다
    ("may"): 한 칸 위로(맨 위면 불가) 또는 맨 아래로 회수" (rise-of-ix.md 5,
    [Rise of Ix p. 5]): from the bottom a recall moves nothing, so only the
    move up; the Reveal's 1 Persuasion beside it."""
    state = _revealed(_start(), 0)
    assert dict(state.decision_stack[-1].context)["persuasion"] == 1
    assert _freighter_rows(state) == {_ADVANCE}
    moved = _do(state, _ADVANCE).state
    assert moved.players[0].freighter_space == 1
    assert _freighter_rows(moved) == set()


def test_the_reveal_freighter_recall_owes_its_rewards_on_the_reveal() -> None:
    """ "회수하면 지금 칸과 그 아래 모든 칸의 보상을 원하는 순서로 받는다"
    (rise-of-ix.md 5): from space 2 both moves; the recall owes space 1's
    choice and space 2's recruit and Influence as rows of the Reveal, which
    hold its end until taken."""
    state = _revealed(_start(), 2)
    assert _freighter_rows(state) == {_ADVANCE, _RECALL}
    recalled = _do(state, _RECALL)
    assert "freighter_recalled" in _kinds(recalled.events)
    state = recalled.state
    assert state.players[0].freighter_space == 0
    assert ix_pending_of(state, 0).shipping_rewards == (1, 2)
    assert _freighter_rows(state) == set()
    assert not _offered(state, "finish_reveal")
    spice = state.players[0].resources.spice
    state = _do(state, "resolve_shipping_reward", effect="spice").state
    assert state.players[0].resources.spice == spice + 2
    state = _do(state, "resolve_shipping_reward", effect="recruit").state
    state = _do(
        state, "resolve_shipping_reward", effect="influence", faction="emperor"
    ).state
    assert ix_pending_of(state, 0).shipping_rewards == ()
    assert _offered(state, "finish_reveal")


def test_the_reveal_freighter_has_no_refusal_and_lapses_with_the_reveal() -> None:
    """ "you may move" (rise-of-ix.md 14, "Freighter 아이콘 하나 | 받은 좌석 |
    위로 한 칸 -OR- 회수 -OR- 쓰지 않음"): an optional Reveal choice offers no
    refusal and lapses when the Reveal ends (OQ-095 (7) addition)."""
    state = _revealed(_start(), 1)
    assert not any(
        row.action_id.startswith("decline_") for row in ENGINE.whole_actions(state, 0)
    )
    assert _offered(state, "finish_reveal")
    finished = _do(state, "finish_reveal")
    assert "reveal_choice_lapsed" in _kinds(finished.events)
    assert finished.state.players[0].freighter_space == 1


def test_the_reveal_freighter_rows_are_in_the_ix_catalog_only() -> None:
    """The two moves are shown by effect rows naming the card that prints them
    (``effect_steps``), in the original game with Rise of Ix only [Rise of Ix
    p. 2]."""
    state = _revealed(_start(), 1)
    rows = [
        row
        for row in ENGINE.legal_actions(state, 0)
        if dict(row.arguments).get("printed") == "guild_chief_administrator"
    ]
    assert {(row.action_id, dict(row.arguments).get("icon")) for row in rows} == {
        ("advance", "freighter"),
        ("collect", "freighter"),
    }
    plain = set(ActionCodec(replace(IX, rise_of_ix=False)).catalog)
    for row in rows:
        template = ActionTemplate(row.action_id, row.arguments)
        assert template in set(CODEC.catalog) - plain
    assert not any(
        dict(template.arguments).get("printed") == "guild_chief_administrator"
        for template in ActionCodec(RulesetConfig()).catalog
    )
