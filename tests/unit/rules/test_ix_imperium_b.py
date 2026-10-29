"""Rise of Ix Imperium batch B: cards that print a Freighter or a trash.

Steam app attribute table, per-card UI pieces and English localization
(4.1.2.1808, dad97e20); rules: rise-of-ix.md 5 ("Freighter 아이콘마다
Freighter를 둘 가운데 하나로 움직일 수 있다("may"): 한 칸 위로(맨 위면 불가)
또는 맨 아래로 회수. 회수하면 지금 칸과 그 아래 모든 칸의 보상을 원하는
순서로 받는다." [Rise of Ix p. 5]), player-turns.md [Main p. 9] [FAQ p. 3],
imperium-base.md 11 ("Trash ... 비용이거나 카드가 자기를 trash하라고 할 때만
의무" [DI p. 16]). Every offered row round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache
from typing import Any

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
)
from dune_imperium.core.observation import ix_pending_of
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.optional_trash import optional_trash_frame, trash_printer

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
_BOX = PersonalCardAgentEffect


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_whole."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _start() -> tuple[_Engine, GameState]:
    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _rows(engine: _Engine, state: GameState) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, 0)
    return engine.whole_actions(state, 0)


def _ids(engine: _Engine, state: GameState) -> list[str]:
    return [row.action_id for row in _rows(engine, state)]


def _do(engine: _Engine, state: GameState, action_id: str, **args: object) -> GameState:
    row = next(
        row
        for row in _rows(engine, state)
        if row.action_id == action_id
        and all(dict(row.arguments).get(key) == value for key, value in args.items())
    )
    result = apply_whole(engine, state, row).state
    engine.legal_actions(result, 0)
    return result


def _events(engine: _Engine, state: GameState, action_id: str) -> list[str]:
    row = next(row for row in _rows(engine, state) if row.action_id == action_id)
    return [event.kind for event in apply_whole(engine, state, row).events]


# --- Landing Rights ------------------------------------------------------------

LANDING_RIGHTS = "imperium:landing_rights:0"
_ADVANCE = "advance_agent_card_freighter"
_RECALL = "recall_agent_card_freighter"
_FREIGHTER_ROWS = {_ADVANCE, _RECALL}


def _rights(engine: _Engine, state: GameState, space: int = 0) -> GameState:
    """Landing Rights sent to Arrakeen (its City icon) with the Freighter on
    ``space``, its box pending."""

    state = _seat(state, hand=(LANDING_RIGHTS,), freighter_space=space)
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == LANDING_RIGHTS
        and dict(row.arguments)["space_id"] == "arrakeen"
    )
    result = apply_placement(engine, state, placement).state
    engine.legal_actions(result, 0)
    return result


def _freighter_rows(engine: _Engine, state: GameState) -> set[str]:
    return set(_ids(engine, state)) & _FREIGHTER_ROWS


def test_landing_rights_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "Freighter" [Landing Rights card, Steam app screen pieces].

    App table: cost 4, one copy, Spacing Guild, the City icon, Reveal 2
    Persuasion and no swords; its Agent box is the one Freighter icon.
    """
    entry = IMPERIUM_CARDS_BY_ID["landing_rights"]
    assert (entry.copies, entry.acquisition_cost) == (1, 4)
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is _BOX.MAY_MOVE_FREIGHTER
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.play_data_complete
    assert LANDING_RIGHTS in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert LANDING_RIGHTS not in content_for(config).imperium_deck_instance_ids


def test_landing_rights_card_text_prints_the_freighter_icon() -> None:
    """ "you may move your Freighter in one of two ways" [Rise of Ix p. 5]."""
    entry = IMPERIUM_CARDS_BY_ID["landing_rights"]
    assert (
        "Agent: You may move your Freighter up one space or recall it"
        in personal_card_text(entry)
    )
    assert "에이전트 칸: 운송 트랙에서 화물선 1칸 전진 또는 귀환 가능" in (
        personal_card_text_ko(entry)
    )


def test_landing_rights_from_the_bottom_can_only_move_up() -> None:
    """ "한 칸 위로(맨 위면 불가) 또는 맨 아래로 회수" [Rise of Ix p. 5]: from
    the bottom a recall moves nothing and pays nothing, so only the move up is
    offered; the one icon is spent by it."""
    engine, state = _start()
    placed = _rights(engine, state, 0)
    assert _freighter_rows(engine, placed) == {_ADVANCE}

    moved = _do(engine, placed, _ADVANCE)
    assert moved.players[0].freighter_space == 1
    assert _freighter_rows(engine, moved) == set()


def test_landing_rights_in_the_middle_offers_the_move_up_and_the_recall() -> None:
    """ "Freighter를 둘 가운데 하나로 움직일 수 있다" [Rise of Ix p. 5]: both
    moves are offered, and only one is taken for the one icon."""
    engine, state = _start()
    placed = _rights(engine, state, 1)
    assert _freighter_rows(engine, placed) == _FREIGHTER_ROWS

    moved = _do(engine, placed, _ADVANCE)
    assert moved.players[0].freighter_space == 2
    assert _freighter_rows(engine, moved) == set()
    assert [event for event in _events(engine, placed, _ADVANCE)] == [
        "freighter_moved",
        "agent_card_effect_resolved",
    ]


def test_landing_rights_at_the_top_can_only_recall() -> None:
    """ "한 칸 위로(맨 위면 불가)" [Rise of Ix p. 5]: from the top space only
    the recall is offered, and it owes the rewards of all three spaces, each
    its own row ("회수하면 지금 칸과 그 아래 모든 칸의 보상을 원하는 순서로
    받는다")."""
    engine, state = _start()
    placed = _rights(engine, state, 3)
    assert _freighter_rows(engine, placed) == {_RECALL}

    recalled = _do(engine, placed, _RECALL)
    assert recalled.players[0].freighter_space == 0
    assert ix_pending_of(recalled, 0).shipping_rewards == (1, 2, 3)
    assert [event for event in _events(engine, placed, _RECALL)] == [
        "freighter_recalled",
        "agent_card_effect_resolved",
    ]


def test_landing_rights_recall_pays_the_space_it_leaves_and_those_below() -> None:
    """ "회수하면 지금 칸과 그 아래 모든 칸의 보상" [Rise of Ix p. 5]: from
    space 1 the recall owes space 1's choice, "Dividends(5 Solari, 상대마다 1
    Solari) -OR- spice 2"; the reward rows wait on the turn beside the rest of
    its effects and the Freighter ends on the bottom."""
    engine, state = _start()
    placed = _rights(engine, state, 1)
    before = placed.players[0].resources
    recalled = _do(engine, placed, _RECALL)
    assert recalled.players[0].freighter_space == 0
    assert ix_pending_of(recalled, 0).shipping_rewards == (1,)
    assert {
        dict(row.arguments)["effect"]
        for row in _rows(engine, recalled)
        if row.action_id == "resolve_shipping_reward"
    } == {"dividends", "spice"}

    paid = _do(engine, recalled, "resolve_shipping_reward", effect="spice")
    assert paid.players[0].resources.spice == before.spice + 2
    assert ix_pending_of(paid, 0).shipping_rewards == ()


def test_landing_rights_has_no_refusal_and_its_icon_lapses_at_the_turn_end() -> None:
    """ "you may move your Freighter" [Rise of Ix p. 5]: an unused optional
    icon needs no refusal, the turn's end lapses it (OQ-095 (2), the user
    ruling 2026-10-14 in open-questions.md). The seat finishes the turn with
    the icon unused, and the Freighter stays where it was."""
    engine, state = _start()
    placed = _rights(engine, state, 1)
    resolved = _do(engine, placed, "resolve_board_effect", effect="troops")
    resolved = _do(engine, resolved, "resolve_board_effect", effect="cards")
    ids = _ids(engine, resolved)
    assert _FREIGHTER_ROWS <= set(ids)
    assert "finish_agent_turn" in ids
    assert not any(row.startswith("decline_") for row in ids)

    events = _events(engine, resolved, "finish_agent_turn")
    assert events == ["agent_card_effect_lapsed", "agent_turn_finished"]
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].freighter_space == 1


def test_landing_rights_freighter_can_be_taken_after_the_visited_space() -> None:
    """The box's icon and the visited space's effects are separate effects of
    the turn, taken in any order [Main p. 9]."""
    engine, state = _start()
    placed = _rights(engine, state, 0)
    resolved = _do(engine, placed, "resolve_board_effect", effect="troops")
    resolved = _do(engine, resolved, "resolve_board_effect", effect="cards")
    moved = _do(engine, resolved, _ADVANCE)
    assert moved.players[0].freighter_space == 1
    assert "finish_agent_turn" in _ids(engine, moved)


def test_landing_rights_reveals_two_persuasion() -> None:
    """App table: Reveal 2 Persuasion; its Freighter icon is Agent-box only."""
    engine, state = _start()
    state = _seat(state, hand=(LANDING_RIGHTS,), freighter_space=1)
    revealed = _do(engine, state, "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2
    assert _freighter_rows(engine, revealed) == set()


def test_the_agent_box_freighter_rows_are_in_the_ix_catalog_only() -> None:
    """The two moves are shown by effect rows naming the card that prints them
    (``effect_steps``), in the original game with Rise of Ix only; no other
    catalog holds them [Rise of Ix p. 2]."""
    engine, state = _start()
    placed = _rights(engine, state, 1)
    rows = [
        row
        for row in engine.legal_actions(placed, 0)
        if dict(row.arguments).get("printed") == "landing_rights"
    ]
    assert {(row.action_id, dict(row.arguments)["icon"]) for row in rows} == {
        ("advance", "freighter"),
        ("collect", "freighter"),
    }
    plain = ActionCodec(replace(CONFIG, rise_of_ix=False)).catalog
    ix = set(_codec(CONFIG).catalog) - set(plain)
    for row in rows:
        assert ActionTemplate(row.action_id, row.arguments) in ix
    assert RulesetConfig().rise_of_ix is False
    assert not any(
        dict(template.arguments).get("printed") == "landing_rights"
        for template in ActionCodec(RulesetConfig()).catalog
    )


# --- Shai-Hulud ----------------------------------------------------------------

SHAI_HULUD = "imperium:shai_hulud:0"
CRYSKNIFE = "imperium:crysknife_card:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
DAGGER = "player:0:starter:dagger:0"
SEEK_ALLIES = "player:0:starter:seek_allies:0"
_TRASH_BOX = "trash_agent_card"
_ACQUIRE_TRASH = "trash_optional_card"


def _held(state: GameState, hand: tuple[str, ...], **changes: Any) -> GameState:
    """Seat 0 holding exactly ``hand`` and ``discard_pile`` (a card sits in
    one zone only: the named ones leave the deck, whose shuffle depends on how
    many Ix cards the Imperium deck holds)."""

    discard_pile: tuple[str, ...] = changes.pop("discard_pile", ())
    named = {*hand, *discard_pile}
    deck = tuple(card for card in state.players[0].deck if card not in named)
    return _seat(
        state, hand=hand, discard_pile=discard_pile, deck=deck, in_play=(), **changes
    )


def _shai_hulud_turn(
    engine: _Engine, state: GameState, *hand: str, **changes: Any
) -> GameState:
    """Shai-Hulud sent to Imperial Basin (its Spice Trade icon) with ``hand``
    left behind, its box pending."""

    state = _held(state, (SHAI_HULUD, *hand), **changes)
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == SHAI_HULUD
        and dict(row.arguments)["space_id"] == "imperial_basin"
    )
    result = apply_placement(engine, state, placement).state
    engine.legal_actions(result, 0)
    return result


def _buyer(
    engine: _Engine, state: GameState, *hand: str, **changes: Any
) -> GameState:
    """Seat 0 mid-Reveal holding ``hand`` with 20 Persuasion to spend and
    Shai-Hulud first in the Imperium Row."""

    held = _held(state, hand, **changes)
    others = tuple(card for card in held.imperium_row if card != SHAI_HULUD)
    held = replace(
        held,
        imperium_row=(SHAI_HULUD, *others[:4]),
        imperium_deck=tuple(c for c in held.imperium_deck if c != SHAI_HULUD),
    )
    revealed = _do(engine, held, "reveal_turn")
    frame = revealed.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = 20
    frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(revealed, decision_stack=(*revealed.decision_stack[:-1], frame))


def _trash_rows(engine: _Engine, state: GameState, action_id: str) -> set[str]:
    return {
        str(dict(row.arguments)["card_id"])
        for row in _rows(engine, state)
        if row.action_id == action_id
    }


def test_shai_hulud_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "Acquire: Trash a card | Reveal: Fremen Bond 5 swords | Agent: Trash a
    card -> 2 troops" [Shai-Hulud card, Steam app screen pieces].

    App table: cost 7, one copy, Fremen, the Spice Trade icon, an acquire
    effect Trash and no fixed Reveal values (the swords are a Reveal record).
    """
    entry = IMPERIUM_CARDS_BY_ID["shai_hulud"]
    assert (entry.copies, entry.acquisition_cost) == (1, 7)
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is _BOX.TRASH_PERSONAL_CARD_TO_RECRUIT_TWO
    assert entry.has_acquisition_bonus
    assert entry.acquisition_effect is PersonalCardAcquisitionEffect.MAY_TRASH_A_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.play_data_complete
    assert SHAI_HULUD in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert SHAI_HULUD not in content_for(config).imperium_deck_instance_ids


def test_shai_hulud_card_text_prints_its_three_boxes() -> None:
    """The three boxes of the card, in English and in Korean."""
    entry = IMPERIUM_CARDS_BY_ID["shai_hulud"]
    assert personal_card_text(entry) == [
        "Agent: You may trash a card → Recruit 2 troops",
        "Reveal: If Fremen Bond: +5 swords",
        "On acquire: Trash a card",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 카드 1장 {trash} 가능 {arrow_right} {troop:2}",
        "공개 칸: 프레멘의 유대감이면: +{sword:5}",
        "획득 시: 카드 1장 {trash}",
    ]


def test_shai_hulud_agent_box_trashes_a_card_for_two_troops() -> None:
    """ "Trash a card -> 2 troops": an arrow whose cost is a trashed card from
    the hand, the discard pile or play (imperium-base.md 11 [DI p. 16]);
    the two troops go to the garrison, and a troop recruited this turn may be
    deployed by a Combat space ("그 turn에 어떤 출처에서 recruit했든 새 troop은
    Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4], player-turns.md)."""
    engine, state = _start()
    placed = _shai_hulud_turn(
        engine, state, DIPLOMACY, DAGGER, discard_pile=(SEEK_ALLIES,)
    )
    assert {DIPLOMACY, DAGGER, SEEK_ALLIES, SHAI_HULUD} == _trash_rows(
        engine, placed, _TRASH_BOX
    )
    before = placed.players[0]
    deployable = max(
        int(dict(row.arguments)["count"])
        for row in _rows(engine, placed)
        if row.action_id == "deploy_troops"
    )

    paid = _do(engine, placed, _TRASH_BOX, card_id=SEEK_ALLIES)
    after = paid.players[0]
    assert SEEK_ALLIES in after.trashed
    assert after.discard_pile == ()
    assert (after.troops_garrison, after.troops_supply) == (
        before.troops_garrison + 2,
        before.troops_supply - 2,
    )
    assert _trash_rows(engine, paid, _TRASH_BOX) == set()
    assert max(
        int(dict(row.arguments)["count"])
        for row in _rows(engine, paid)
        if row.action_id == "deploy_troops"
    ) == deployable + 2


def test_shai_hulud_agent_trash_is_an_optional_arrow_the_turn_end_lapses() -> None:
    """ "화살표 비용을 지불하지 않거나 ... 그 효과를 생략할 수 있다"
    (player-turns.md [Main p. 9] [FAQ p. 3]): no refusal is offered in the
    owner's turn (OQ-095 (2)), the turn's end lapses the unused arrow, and no
    troop comes."""
    engine, state = _start()
    placed = _shai_hulud_turn(engine, state, DIPLOMACY)
    resolved = _do(engine, placed, "harvest_maker_spice", space_id="imperial_basin")
    ids = _ids(engine, resolved)
    assert _TRASH_BOX in ids and "finish_agent_turn" in ids
    assert "decline_agent_card_trash" not in ids

    events = _events(engine, resolved, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in events
    finished = _do(engine, resolved, "finish_agent_turn")
    assert (finished.players[0].troops_garrison, finished.players[0].trashed) == (
        placed.players[0].troops_garrison,
        (),
    )


def test_shai_hulud_agent_box_waits_while_no_troop_can_join() -> None:
    """ "비용이 있는 줄은 보상 중 하나라도 무언가를 바꿀 수 있을 때만
    제시한다" (OQ-071, open-questions.md): with no troop in the supply the two
    troops change nothing, so the trash is not offered as their cost."""
    engine, state = _start()
    placed = _shai_hulud_turn(
        engine, state, DIPLOMACY, troops_garrison=12, troops_supply=0
    )
    assert _trash_rows(engine, placed, _TRASH_BOX) == set()


def test_shai_hulud_reveals_five_swords_with_another_fremen_card() -> None:
    """ "Fremen Bond: [5 swords]" (Reveal): another Fremen card in play
    ([Main p. 20], official-rulings-index.md "Fremen Bond / In Play"); alone,
    the card is its own and only Fremen card and gives nothing."""
    engine, state = _start()
    alone = _do(engine, _held(state, (SHAI_HULUD,)), "reveal_turn")
    assert dict(alone.decision_stack[-1].context)["sword_strength"] == 0

    # Crysknife prints 1 sword and its own Bond, an Influence.
    bonded = _do(engine, _held(state, (SHAI_HULUD, CRYSKNIFE)), "reveal_turn")
    assert dict(bonded.decision_stack[-1].context)["sword_strength"] == 5 + 1
    assert dict(bonded.decision_stack[-1].context)["persuasion"] == 0


def test_shai_hulud_bought_in_a_reveal_offers_an_optional_trash() -> None:
    """ "When you acquire a card, you immediately resolve its acquire box,
    once" [Main p. 20] (player-turns.md); the black Trash icon is optional
    ("비용이거나 카드가 자기를 trash하라고 할 때만 의무" [DI p. 16],
    imperium-base.md 11). The purchase puts the card in the discard pile first;
    the trash is a row of the Reveal turn, from the hand, the discard pile or
    play, the acquired card included, with no refusal: the turn's end lapses
    it."""
    engine, state = _start()
    revealed = _buyer(engine, state, DIPLOMACY, DAGGER, discard_pile=(SEEK_ALLIES,))
    bought = _do(engine, revealed, "acquire_imperium", instance_id=SHAI_HULUD)
    assert bought.players[0].discard_pile[-1] == SHAI_HULUD
    # Revealed cards are in play, the others in the hand and the discard pile.
    offered = _trash_rows(engine, bought, _ACQUIRE_TRASH)
    assert {SHAI_HULUD, SEEK_ALLIES} <= offered
    assert offered == set(bought.players[0].in_play) | {
        *bought.players[0].hand,
        *bought.players[0].discard_pile,
    }
    ids = _ids(engine, bought)
    assert "finish_reveal" in ids
    assert "decline_optional_trash" not in ids

    trashed = _do(engine, bought, _ACQUIRE_TRASH, card_id=SEEK_ALLIES)
    assert SEEK_ALLIES in trashed.players[0].trashed
    assert _trash_rows(engine, trashed, _ACQUIRE_TRASH) == set()

    events = _events(engine, bought, "finish_reveal")
    assert events == ["optional_trash_lapsed", "reveal_finished"]


def test_shai_hulud_acquire_trash_may_take_the_card_just_acquired() -> None:
    """The acquire box resolves after the card has reached its zone, and the
    Trash icon takes "a card" of the hand, the discard pile or play
    ([DI p. 16]): the acquired Shai-Hulud sits in the discard pile and is one
    of them. (The documents do not say otherwise; the engine's generic trash
    is kept.)"""
    engine, state = _start()
    bought = _do(
        engine,
        _buyer(engine, state, DIPLOMACY),
        "acquire_imperium",
        instance_id=SHAI_HULUD,
    )
    trashed = _do(engine, bought, _ACQUIRE_TRASH, card_id=SHAI_HULUD)
    assert SHAI_HULUD in trashed.players[0].trashed
    assert SHAI_HULUD not in trashed.players[0].discard_pile


def test_shai_hulud_acquire_trash_is_not_repeated_when_the_card_is_played() -> None:
    """ "나중에 hand에서 그 card를 낼 때는 얻지 않는다" [Main p. 20]
    (player-turns.md): played from the hand its Agent box offers its own trash
    for troops, not the acquire box's."""
    engine, state = _start()
    placed = _shai_hulud_turn(engine, state, DIPLOMACY)
    assert _ACQUIRE_TRASH not in _ids(engine, placed)
    assert _TRASH_BOX in _ids(engine, placed)


def test_shai_hulud_acquire_trash_outside_a_turn_opens_a_window() -> None:
    """Outside its owner's turn the icon opens a window of its own with a
    refusal (``optional_trash``), as Disposal Facility's acquire icon does;
    its rows and the refusal round-trip through the Rise of Ix catalog."""
    engine, state = _start()
    held = _held(state, (DIPLOMACY, DAGGER))
    printer = trash_printer(Source.ACQUISITION, "shai_hulud")
    window = held.push_decision(optional_trash_frame(0, "s", printer=printer))
    assert window.decision_stack[-1].kind is FrameKind.OPTIONAL_TRASH
    legal = engine.legal_actions(window, 0)
    assert {action.action_id for action in legal} == {"decline", "choose_personal_card"}
    declined = engine.apply(
        window, next(a for a in legal if a.action_id == "decline")
    ).state
    assert declined.decision_stack[-1].kind is not FrameKind.OPTIONAL_TRASH
    assert declined.players[0].trashed == ()


def test_the_acquisition_trash_rows_are_in_the_ix_catalog_only() -> None:
    """The acquire box's trash is shown by effect rows naming Shai-Hulud as the
    acquisition that prints them, in the original game with Rise of Ix only;
    no other catalog holds them [Rise of Ix p. 2]."""
    engine, state = _start()
    bought = _do(
        engine,
        _buyer(engine, state, DIPLOMACY),
        "acquire_imperium",
        instance_id=SHAI_HULUD,
    )
    rows = [
        row
        for row in engine.legal_actions(bought, 0)
        if dict(row.arguments).get("source") == "acquisition"
    ]
    assert {row.action_id for row in rows} == {"trash"}
    plain = ActionCodec(replace(CONFIG, rise_of_ix=False)).catalog
    ix = set(_codec(CONFIG).catalog) - set(plain)
    for row in rows:
        assert ActionTemplate(row.action_id, row.arguments) in ix
    assert not any(
        dict(template.arguments).get("printed") == "shai_hulud"
        for template in ActionCodec(RulesetConfig()).catalog
    )
