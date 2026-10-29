"""Rise of Ix Imperium batch E: Bounty Hunter, Web of Power and Ixian Engineer.

Steam app attribute table, per-card UI pieces and English localization
(4.1.2.1808, dad97e20); rules: rise-of-ix.md 7 ("Agent의 옆얼굴이 든 Agent
아이콘은 그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게
한다. 자기 Agent가 이미 있는 칸에는 못 보낸다." [Rise of Ix p. 7]),
player-turns.md [Main p. 9] [FAQ p. 3]. Every offered row round-trips through
``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.agent_abilities import AGENT_BOX_ABILITIES
from dune_imperium.content.uprising.effect_dsl import AtSpaceWithEnemyAgent
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
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    enemy_agent_on_space,
    executable_placements,
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


def _clean(state: GameState, named: set[str]) -> GameState:
    """``state`` without the named cards in any seat's zones, the Imperium deck
    and Row (seeded decks may hold the card a test then puts in a hand)."""

    return replace(
        state,
        players=tuple(
            replace(
                player,
                deck=tuple(c for c in player.deck if c not in named),
                hand=tuple(c for c in player.hand if c not in named),
                discard_pile=tuple(c for c in player.discard_pile if c not in named),
                in_play=tuple(c for c in player.in_play if c not in named),
            )
            for player in state.players
        ),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    hand = changes.get("hand")
    if isinstance(hand, tuple):
        named = {card for card in hand if card not in state.players[seat].hand}
        state = _clean(state, named)
    players = list(state.players)
    owner = players[seat]
    if "agent_locations" in changes:
        locations = changes["agent_locations"]
        assert isinstance(locations, tuple)
        changes["agents_available"] = 2 - len(locations)
    if "troops_conflict" in changes or "troops_garrison" in changes:
        # The supply makes up the 12 troops a seat always accounts for.
        garrison = changes.get("troops_garrison", owner.troops_garrison)
        conflict = changes.get("troops_conflict", owner.troops_conflict)
        assert isinstance(garrison, int) and isinstance(conflict, int)
        changes["troops_supply"] = (
            12
            - garrison
            - conflict
            - owner.memories
            - owner.specimens
            - owner.troops_parked
            - owner.negotiators
        )
    players[seat] = replace(owner, **changes)  # type: ignore[arg-type]
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


def _spaces(state: GameState, card_id: str) -> set[str]:
    return {
        str(dict(row.arguments)["space_id"])
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == card_id
    }


def _send(engine: _Engine, state: GameState, card_id: str, space_id: str) -> GameState:
    """``card_id`` (already in hand) sent to ``space_id``, its box pending."""

    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == card_id
        and dict(row.arguments)["space_id"] == space_id
    )
    result = apply_placement(engine, state, placement).state
    engine.legal_actions(result, 0)
    return result


# --- Bounty Hunter --------------------------------------------------------------

HUNTER = "imperium:bounty_hunter:0"
_HUNTER_BOX = _BOX.GAIN_TWO_SOLARI_IF_ENEMY_AGENT_ON_SPACE


def _hunter(
    engine: _Engine,
    state: GameState,
    space: str,
    *enemies: tuple[int, tuple[str, ...]],
    **changes: object,
) -> GameState:
    """Bounty Hunter sent to ``space`` while each ``(seat, spaces)`` pair has
    its Agents there; its box is pending when it is judged to be."""

    for seat, locations in enemies:
        state = _seat(state, seat, agent_locations=locations)
    state = _seat(state, 0, hand=(HUNTER,), **changes)
    return _send(engine, state, HUNTER, space)


def test_bounty_hunter_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "If used to send an Agent to a board space with an enemy Agent:
    [2 Solari]" and Reveal 1 Persuasion, 1 sword [Steam app screen pieces and
    text].

    App table: cost 1, one copy, no Faction, the City icon (also its
    Infiltration icon, ``InfiltrationIconList``), Reveal 1 Persuasion and
    1 sword.
    """
    entry = IMPERIUM_CARDS_BY_ID["bounty_hunter"]
    assert (entry.copies, entry.acquisition_cost) == (1, 1)
    assert entry.factions == ()
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is _HUNTER_BOX
    assert entry.reveal_choice_effects == ()
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert HUNTER in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert HUNTER not in content_for(config).imperium_deck_instance_ids


def test_bounty_hunter_card_text_prints_the_condition_and_the_gain() -> None:
    """ "If used to send an Agent to a board space with an enemy Agent:
    [2 Solari]" [Steam app screen pieces and text]; Korean words: an opponent
    is "다른 플레이어" (docs/rules/glossary-ko.md)."""
    entry = IMPERIUM_CARDS_BY_ID["bounty_hunter"]
    assert personal_card_text(entry) == [
        "Agent: If used to send an Agent to a board space with an enemy Agent: "
        "Gain 2 solari",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 다른 플레이어의 {agent}가 있는 장소로 {agent}를 보냈다면: "
        "{solari:2}",
    ]


def test_bounty_hunter_record_is_a_placement_requirement() -> None:
    """The space is fixed by the placement, so the record holds it as the
    box's ``requirement`` (judged when the card is played, OQ-028 (a)), not as
    a line condition judged when the box resolves."""
    ability = AGENT_BOX_ABILITIES[_HUNTER_BOX]
    assert ability.requirement == AtSpaceWithEnemyAgent()
    assert all(section.condition is None for section in ability.sections)


def test_bounty_hunter_infiltrates_a_city_space_and_gains_two_solari() -> None:
    """ "그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게
    한다" [Rise of Ix p. 7]: the printed City Infiltration icon sends the Agent
    to a City space an opponent holds, and the space then "with an enemy
    Agent" pays the 2 Solari."""
    engine, state = _start()
    placed = _hunter(engine, state, "carthag", (1, ("carthag",)))
    assert placed.players[0].agent_locations == ("carthag",)
    assert placed.players[1].agent_locations == ("carthag",)
    assert "resolve_agent_card_effect" in _ids(engine, placed)
    solari = placed.players[0].resources.solari
    paid = _do(engine, placed, "resolve_agent_card_effect")
    assert paid.players[0].resources.solari == solari + 2
    assert "resolve_agent_card_effect" not in _ids(engine, paid)


def test_bounty_hunter_pays_once_for_several_enemy_agents() -> None:
    """ "상대 Agent(여럿이어도)" [Rise of Ix p. 7]: the box prints one 2 Solari,
    however many enemy Agents the space holds."""
    engine, state = _start()
    placed = _hunter(
        engine,
        state,
        "carthag",
        (1, ("carthag",)),
        (2, ("carthag",)),
        (3, ("carthag",)),
    )
    solari = placed.players[0].resources.solari
    paid = _do(engine, placed, "resolve_agent_card_effect")
    assert paid.players[0].resources.solari == solari + 2
    assert "resolve_agent_card_effect" not in _ids(engine, paid)


@pytest.mark.parametrize("space", ["arrakeen", "carthag"])
def test_bounty_hunter_pays_nothing_on_an_empty_space(space: str) -> None:
    """ "If used to send an Agent to a board space with an enemy Agent": an
    ordinary placement on an empty space ("잠입은 선택이다(빈 칸에 보통처럼
    보내도 된다)" [FAQ p. 2]) opens no box, so no row waits and the turn's end
    gives nothing."""
    engine, state = _start()
    enemy = _seat(state, 1, agent_locations=("wealth",))
    placed = _hunter(engine, enemy, space)
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    solari = placed.players[0].resources.solari
    assert not dict(placed.decision_stack[-1].context)["pending_agent_effect"]
    assert placed.players[0].resources.solari == solari


def test_bounty_hunter_ignores_an_enemy_agent_on_another_space() -> None:
    """The condition is about "a board space" the Agent is sent to: an enemy
    Agent on a different space does not open the box."""
    engine, state = _start()
    placed = _hunter(engine, state, "arrakeen", (1, ("carthag",)), (2, ("wealth",)))
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    assert not dict(placed.decision_stack[-1].context)["pending_agent_effect"]


def test_bounty_hunter_own_agent_still_blocks_the_space() -> None:
    """ "자기 Agent가 이미 있는 칸에는 못 보낸다." [Rise of Ix p. 7]: an own
    Agent there blocks the space, an enemy Agent beside it or not."""
    engine, state = _start()
    mine = _seat(state, 0, agent_locations=("carthag",))
    both = _seat(mine, 1, agent_locations=("carthag",))
    for held in (mine, both):
        held = _seat(held, 0, hand=(HUNTER,))
        assert "carthag" not in _spaces(held, HUNTER)
        assert "arrakeen" in _spaces(held, HUNTER)


def test_bounty_hunter_judges_the_space_the_agent_goes_to() -> None:
    """``enemy_agent_on_space``: an opponent's Agent on that space, whoever
    owns it, and never the sender's own."""
    _, state = _start()
    state = _seat(state, 0, agent_locations=("arrakeen",))
    state = _seat(state, 2, agent_locations=("carthag",))
    assert enemy_agent_on_space(state, 0, "carthag")
    assert not enemy_agent_on_space(state, 0, "arrakeen")
    assert not enemy_agent_on_space(state, 0, "wealth")
    assert enemy_agent_on_space(state, 1, "arrakeen")


def test_bounty_hunter_reveals_one_persuasion_and_a_sword() -> None:
    """App table: Reveal 1 Persuasion and 1 sword; its box is Agent-only. A
    sword counts with a troop in the Conflict ("troop 2, sword 1; Conflict에
    troop이 하나도 없으면 0" [DI p. 11])."""
    engine, state = _start()
    state = _seat(state, hand=(HUNTER,), troops_conflict=1, resources=Resources())
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (1, 1)
    assert revealed.players[0].combat_strength == 2 + 1
    assert revealed.players[0].resources.solari == 0
