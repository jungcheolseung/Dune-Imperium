"""The original Dune: Imperium's Imperium cards (stage P3, trial transcription).

docs/rules/imperium-base.md 7, 11, 13.2 and docs/base-game-and-ix-plan.md 16.
The cards are not in the original game's deck yet (plan 16.1), so each test
puts the card instance into seat 0's hand of an original-game round; the
printed values are the Steam app's attribute table (plan 2.4, D1).
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
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
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat_deployment import legal_combat_deployments

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)


def _start(seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _with_card(
    state: GameState, card_id: str, *, alone: bool = False
) -> tuple[GameState, str]:
    """Seat 0 with copy 0 of the Imperium card ``card_id`` in hand (the only
    card when ``alone``); returns the instance id too."""

    instance = f"imperium:{card_id}:0"
    owner = state.players[0]
    hand = (instance,) if alone else (*owner.hand, instance)
    return _seat(state, hand=hand), instance


def _place(
    engine: UprisingRulesEngine, state: GameState, space_id: str, card_id: str
) -> GameState:
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and f":{card_id}:" in str(dict(placement.arguments)["card_id"])
    )
    return apply_placement(engine, state, placement).state


def _wholes(engine: UprisingRulesEngine, state: GameState) -> tuple[DomainAction, ...]:
    return engine.whole_actions(state, 0)


def _ids(engine: UprisingRulesEngine, state: GameState) -> set[str]:
    return {action.action_id for action in _wholes(engine, state)}


def _do(
    engine: UprisingRulesEngine, state: GameState, action_id: str, **arguments: object
) -> GameState:
    action = next(
        action
        for action in _wholes(engine, state)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(engine, state, action).state


def _reveal(engine: UprisingRulesEngine, state: GameState) -> dict[str, object]:
    """The Reveal frame's context after seat 0 reveals its hand."""

    revealed = _do(engine, state, "reveal_turn")
    return dict(revealed.decision_stack[-1].context)


# --- Arrakis Recruiter ------------------------------------------------------------


def test_arrakis_recruiter_matches_the_app_table() -> None:
    # App attribute table: cost 2, 2 copies, City, no Faction, Reveal 1
    # Persuasion and 1 sword; AgentTroops 1.
    entry = IMPERIUM_CARDS_BY_ID["arrakis_recruiter"]
    assert entry.card.name == "Arrakis Recruiter"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is PersonalCardAgentEffect.RECRUIT_ONE_TROOP
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:arrakis_recruiter:1") is entry
    # The deck lists no original card until stage P3a (plan 16.1).
    assert not any("arrakis_recruiter" in card for card in _start()[1].imperium_deck)


def test_arrakis_recruiter_recruits_one_troop() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "arrakis_recruiter")
    state = _seat(state, resources=Resources(water=2))
    owner = state.players[0]
    placed = _place(engine, state, "imperium_research_station", "arrakis_recruiter")
    assert placed.players[0].troops_garrison == owner.troops_garrison
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = resolved.players[0]
    assert after.troops_garrison == owner.troops_garrison + 1
    assert after.troops_supply == owner.troops_supply - 1


def test_arrakis_recruiter_troop_deploys_at_a_combat_space() -> None:
    """"Combat 칸(사막 그림과 교차한 칼)에 Agent를 보내면 이번 turn에 recruit한
    troop 전부와 garrison의 troop 둘까지를 Conflict에 배치할 수 있다."
    [DI pp. 10, 17-18] (imperium-base.md 7); Research Station is a Combat
    space. The card prints no deployment of its own, so the recruited troop
    joins the garrison's two: three in all."""

    engine, state = _start()
    state, _ = _with_card(state, "arrakis_recruiter")
    state = _seat(state, resources=Resources(water=2))
    placed = _place(engine, state, "imperium_research_station", "arrakis_recruiter")
    before = {
        int(dict(action.arguments)["count"])
        for action in legal_combat_deployments(placed, 0)
    }
    assert max(before) == 2
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = {
        int(dict(action.arguments)["count"])
        for action in legal_combat_deployments(resolved, 0)
    }
    assert max(after) == 3
    deployed = _do(engine, resolved, "deploy_troops", count=3)
    assert deployed.players[0].troops_conflict == 3


def test_arrakis_recruiter_reveals_one_persuasion_and_one_sword() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "arrakis_recruiter", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 1
