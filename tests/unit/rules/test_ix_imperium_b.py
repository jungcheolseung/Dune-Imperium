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

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
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
from dune_imperium.rules.agent_turn import executable_placements

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
    assert "에이전트 칸: 운송 트랙에서 한 칸 위로 또는 회수 가능" in (
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
