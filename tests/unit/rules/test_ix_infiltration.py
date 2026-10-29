"""Rise of Ix's printed Infiltration icons and Jamis, from the Steam app.

Placement: docs/rules/rise-of-ix.md 7 [Rise of Ix p. 7] [FAQ p. 2].
Jamis: app table Fremen / Fremen Infiltration, cost 2, one copy; card screen
pieces Agent TrashPersonalCard(), Reveal Persuasion(1) GainCombatStrength(2).
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import BoardSpace, Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    executable_placements,
    opponents_do_not_block,
)

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
JAMIS = "imperium:jamis:0"
ENVOY = "intrigue:dispatch_an_envoy:0"
VICTIM = "player:0:starter:convincing_argument:0"
CARDS = {entry.card.card_id: entry for entry in IX_IMPERIUM_CARDS}


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class CheckedEngine(UprisingRulesEngine):
    """Round-trip every offered step, including effect and target choices."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _start() -> tuple[CheckedEngine, GameState]:
    engine = CheckedEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    # Move the named cards from the shuffled pools into this test hand.
    state = replace(
        state,
        imperium_row=tuple(card for card in state.imperium_row if card != JAMIS),
        imperium_deck=tuple(card for card in state.imperium_deck if card != JAMIS),
    )
    state = _seat(
        state,
        hand=(JAMIS, VICTIM),
        deck=tuple(card for card in state.players[0].deck if card != VICTIM),
        resources=Resources(water=2, spice=2, solari=5),
    )
    return engine, state


def _placements(engine: CheckedEngine, state: GameState) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, 0)
    return tuple(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == JAMIS
    )


def _spaces(engine: CheckedEngine, state: GameState) -> set[str]:
    return {str(dict(row.arguments)["space_id"]) for row in _placements(engine, state)}


def _place(
    engine: CheckedEngine, state: GameState, space: str = "stillsuits"
) -> GameState:
    row = next(
        row
        for row in _placements(engine, state)
        if dict(row.arguments)["space_id"] == space
    )
    placed = apply_placement(engine, state, row).state
    engine.legal_actions(placed, 0)
    return placed


def _do(
    engine: CheckedEngine, state: GameState, action_id: str, **arguments: object
) -> GameState:
    engine.legal_actions(state, 0)
    row = next(
        row
        for row in engine.whole_actions(state, 0)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    result = apply_whole(engine, state, row).state
    engine.legal_actions(result, 0)
    return result


def test_jamis_play_data() -> None:
    """Jamis: Fremen Infiltration; Agent 'Trash a card'; Reveal 1P, 2 swords."""
    entry = IMPERIUM_CARDS_BY_ID["jamis"]
    assert (entry.copies, entry.acquisition_cost) == (1, 2)
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.FREMEN,)
    assert entry.agent_effect is PersonalCardAgentEffect.TRASH_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 2)
    assert entry.play_data_complete
    assert entry in content_for(CONFIG).imperium_cards


def _space(icon: AgentIcon) -> BoardSpace:
    return next(
        space for space in content_for(CONFIG).board_spaces if space.agent_icon is icon
    )


def test_a_printed_infiltration_icon_ignores_enemy_agents_at_that_icon_only() -> None:
    """'그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시' [Rise of Ix p. 7]."""
    owner = UprisingRulesEngine(leader_ids=LEADERS).reset(CONFIG, 3).players[0]
    bounty_hunter = CARDS["bounty_hunter"]  # City Infiltration
    assert bounty_hunter.infiltration_icons == (AgentIcon.CITY,)
    assert opponents_do_not_block(owner, _space(AgentIcon.CITY), card=bounty_hunter)
    assert not opponents_do_not_block(
        owner, _space(AgentIcon.LANDSRAAD), card=bounty_hunter
    )
    # A card with no printed Infiltration icon, or no card at all (an icon
    # granted by Dispatch an Envoy), gets no bypass.
    assert not opponents_do_not_block(
        owner, _space(AgentIcon.CITY), card=CARDS["desert_ambush"]
    )
    assert not opponents_do_not_block(owner, _space(AgentIcon.CITY))


@pytest.mark.parametrize("opponents", (1, 2, 3))
def test_infiltration_ignores_every_enemy_agent(opponents: int) -> None:
    """'상대 Agent(여럿이어도)를 무시하고 보낼 수 있게 한다.' [Rise of Ix p. 7]."""
    engine, state = _start()
    for seat in range(1, opponents + 1):
        state = _seat(state, seat, agent_locations=("stillsuits",), agents_available=1)
    assert "stillsuits" in _spaces(engine, state)
    placed = _place(engine, state)
    assert placed.players[0].agent_locations == ("stillsuits",)
    assert placed.players[0].agents_available == state.players[0].agents_available - 1
    assert not placed.players[0].enemy_agents_ignored_turn
    assert all(placed.players[seat] == state.players[seat] for seat in range(1, 4))


@pytest.mark.parametrize("enemy_also", (False, True))
def test_own_agent_still_blocks(enemy_also: bool) -> None:
    """'자기 Agent가 이미 있는 칸에는 못 보낸다.' [Rise of Ix p. 7]."""
    engine, state = _start()
    state = _seat(state, agent_locations=("stillsuits",), agents_available=1)
    if enemy_also:
        state = _seat(state, 1, agent_locations=("stillsuits",), agents_available=1)
    assert "stillsuits" not in _spaces(engine, state)
    assert "hardy_warriors" in _spaces(engine, state)


@pytest.mark.parametrize("occupied", (False, True))
def test_the_voice_still_blocks(occupied: bool) -> None:
    """'The Voice는 넘지 못한다.' [Rise of Ix p. 7]."""
    engine, state = _start()
    state = _seat(state, voice_blocked_space_ids=("stillsuits",))
    if occupied:
        state = _seat(state, 1, agent_locations=("stillsuits",), agents_available=1)
    assert "stillsuits" not in _spaces(engine, state)
    assert "hardy_warriors" in _spaces(engine, state)


def test_dispatch_an_envoy_does_not_add_infiltration() -> None:
    """'Dispatch an Envoy로 더한 아이콘은 잠입하지 못한다.' [Rise of Ix p. 7]."""
    engine, state = _start()
    state = replace(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != ENVOY)
    )
    state = _seat(state, intrigue_cards=(ENVOY,))
    state = _seat(
        state, 1, agent_locations=("wealth", "stillsuits"), agents_available=0
    )
    played = _do(engine, state, "play_intrigue", card_id=ENVOY, option=0)
    spaces = _spaces(engine, played)
    assert "stillsuits" in spaces  # Printed Fremen retains Infiltration.
    assert "wealth" not in spaces  # Granted Emperor cannot bypass the enemy.
    assert {"foldspace", "secrets"} <= spaces  # Empty granted spaces are legal.
    placed = _place(engine, played, "foldspace")
    assert placed.players[0].agent_locations == ("foldspace",)


def test_normal_placement_is_offered_and_does_not_require_an_enemy() -> None:
    """'잠입은 선택이다(빈 칸에 보통처럼 보내도 된다).' [FAQ p. 2]."""
    engine, state = _start()
    assert _spaces(engine, state) == {"stillsuits", "hardy_warriors"}
    assert all(
        "infiltrate_post_id" not in dict(row.arguments)
        for row in _placements(engine, state)
    )
    placed = _place(engine, state, "hardy_warriors")
    assert placed.players[0].resources.water == state.players[0].resources.water - 1


@pytest.mark.parametrize("victim", (VICTIM, JAMIS))
def test_jamis_agent_trashes_a_hand_card_or_itself(victim: str) -> None:
    """Jamis Agent: 'Trash a card'; trash icon [DI p. 16], imperium-base.md 11."""
    engine, state = _start()
    placed = _place(engine, state)
    trashed = _do(engine, placed, "trash_agent_card", card_id=victim)
    owner = trashed.players[0]
    assert victim in owner.trashed
    assert victim not in owner.hand and victim not in owner.in_play
    assert not any(
        row.action_id == "trash_agent_card" for row in engine.whole_actions(trashed, 0)
    )


def test_jamis_reveal() -> None:
    """Jamis Reveal: '1 Persuasion, 2 swords' (Steam card screen pieces)."""
    engine, state = _start()
    state = _seat(
        state,
        hand=(JAMIS,),
        troops_conflict=1,
        troops_garrison=state.players[0].troops_garrison - 1,
    )
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == 2
    assert revealed.players[0].in_play == (JAMIS,)


def test_jamis_trash_may_be_skipped() -> None:
    """'비용이거나 카드가 자기를 trash하라고 할 때만 의무' [DI p. 16]."""
    engine, state = _start()
    placed = _place(engine, state)
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    resolved = _do(engine, resolved, "resolve_faction_influence")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].trashed == placed.players[0].trashed
    assert JAMIS in finished.players[0].in_play
    assert VICTIM in finished.players[0].hand


def test_infiltration_belongs_to_the_played_card() -> None:
    """'그 아이콘의 칸에서 상대 Agent ... 무시' [Rise of Ix p. 7]."""
    engine, state = _start()
    diplomacy = "player:0:starter:diplomacy:0"
    state = _seat(state, hand=(JAMIS, diplomacy))
    state = _seat(state, 1, agent_locations=("stillsuits",), agents_available=1)
    engine.legal_actions(state, 0)
    occupied_rows = [
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["space_id"] == "stillsuits"
    ]
    assert {dict(row.arguments)["card_id"] for row in occupied_rows} == {JAMIS}
